"""
utils/cache.py — Shared in-memory TTL cache for hot-path Supabase reads.

PHASE 1 / PART 1 — Every message used to trigger 6+ Supabase REST calls
(mod_settings, leveling_settings, prefix_settings, log_settings,
server_personality, user_facts). A short-lived cache eliminates ~99% of
those round-trips, cutting latency and PostgREST quota usage.

Design notes (deviation from the original spec, on purpose):
  * The spec drafted the store behind `asyncio.Lock`. That cannot work
    here: the cached read functions in utils/db.py are SYNC functions that
    also execute inside `asyncio.to_thread()` worker threads (via the
    *_async wrappers). An asyncio.Lock cannot be acquired from a plain
    thread — it would deadlock or raise "attached to a different loop".
  * The cache operations are tiny in-memory dict tweaks (microseconds), so
    a `threading.RLock` is safe to acquire from BOTH the event loop and
    worker threads with no measurable blocking.
  * The public async API from the spec is preserved exactly (get / set /
    invalidate / invalidate_prefix / cleanup are `async def`), so async
    callers can `await cache.get(...)` unchanged. Sync callers use the
    `*_sync` twins.

Usage:
    from utils.cache import cache

    # async context
    val = await cache.get("gs:mod_settings:123")
    await cache.set("gs:mod_settings:123", {...}, ttl=60)

    # sync context (threads, background tasks)
    val = cache.get_sync("gs:mod_settings:123")
    cache.set_sync("gs:mod_settings:123", {...}, ttl=60)
    cache.invalidate_sync("gs:mod_settings:123")

    cache.stats()   # {"size", "hits", "misses", "hit_rate"} — /botinfo
"""
import time
import threading
from typing import Any, Optional
from collections import OrderedDict


class TTLCache:
    """Thread-safe LRU-ish TTL cache.

    * max_size bounds memory: when full, the least-recently-USED entry is
      evicted first (OrderedDict move_to_end on both get and set).
    * Entries expire individually by their own TTL.
    * get() returns None on a miss (stored values are never None — the
      db layer stores {} / [] for "no data", which are valid cache hits).
    """

    def __init__(self, max_size: int = 1000):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        # threading.RLock (NOT asyncio.Lock): the cached db functions run
        # inside asyncio.to_thread() worker threads as well as on the loop.
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # ─── sync core (safe from event loop AND threads) ─────────────

    def get_sync(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._store:
                value, expiry = self._store[key]
                if time.time() < expiry:
                    self._store.move_to_end(key)
                    self._hits += 1
                    return value
                else:
                    del self._store[key]
            self._misses += 1
            return None

    def set_sync(self, key: str, value: Any, ttl: int = 60):
        with self._lock:
            expiry = time.time() + ttl
            self._store[key] = (value, expiry)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate_sync(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix_sync(self, prefix: str):
        with self._lock:
            keys_to_del = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_del:
                del self._store[k]

    def cleanup_sync(self) -> int:
        """Drop every expired entry. Returns how many were pruned."""
        with self._lock:
            now = time.time()
            expired = [k for k, (_, exp) in self._store.items() if now >= exp]
            for k in expired:
                del self._store[k]
            return len(expired)

    # ─── async facade (spec API — await from coroutines) ──────────

    async def get(self, key: str) -> Optional[Any]:
        return self.get_sync(key)

    async def set(self, key: str, value: Any, ttl: int = 60):
        self.set_sync(key, value, ttl)

    async def invalidate(self, key: str):
        self.invalidate_sync(key)

    async def invalidate_prefix(self, prefix: str):
        self.invalidate_prefix_sync(prefix)

    async def cleanup(self) -> int:
        return self.cleanup_sync()

    # ─── stats (sync — used by /botinfo and the cleanup task) ─────

    def size(self) -> int:
        return len(self._store)

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return round((self._hits / total * 100), 1) if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size": self.size(),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate(),
        }


# Singleton — every cog / db helper shares this instance.
cache = TTLCache()
