"""
utils/usage_logger.py — Batched command-usage analytics.

PHASE 1 / PART 3 — Every slash command invocation is appended to an
in-memory buffer by main.py's on_app_command_completion hook. The buffer
is flushed to the Supabase `command_usage` table when either:
  * 10 invocations have queued (batch_size), or
  * 30 seconds have passed (periodic flush task started in setup_hook).

One INSERT per 10 commands instead of one per command keeps us far away
from PostgREST rate limits and adds zero latency to command handling —
logging is fire-and-forget (asyncio.create_task) and can never break a
command. If Supabase is down the batch is simply dropped with a warning:
analytics must never affect the user experience.

Supabase table (see the SQL comment block at the top of utils/db.py):

    CREATE TABLE IF NOT EXISTS command_usage (
        id BIGSERIAL PRIMARY KEY,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        command_name TEXT NOT NULL,
        timestamp TIMESTAMPTZ DEFAULT NOW()
    );
"""
import asyncio
import logging
from datetime import datetime

# Late-bound import (module attribute access at flush time): keeps this
# module consistent with utils.db in tests and hot-reload scenarios.
from utils import db as _db

log = logging.getLogger("cyn.usage")


class UsageLogger:
    def __init__(self, batch_size: int = 10, flush_interval: int = 30):
        self._buffer = []
        self._lock = asyncio.Lock()
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._task = None

    async def log(self, guild_id: str, user_id: str, command_name: str):
        """Record one command invocation. Flushes immediately when the
        batch is full. Never raises — analytics must not break commands."""
        try:
            async with self._lock:
                self._buffer.append({
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "command_name": command_name,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                if len(self._buffer) >= self._batch_size:
                    await self._flush_locked()
        except Exception as e:
            log.warning(f"[USAGE] log() failed: {e}")

    async def _flush_locked(self):
        """Send everything in the buffer. Caller must hold self._lock."""
        if not self._buffer:
            return
        to_send = self._buffer[:]
        self._buffer.clear()
        try:
            sb = _db.get_supabase()
            if sb:
                await asyncio.to_thread(
                    lambda: sb.table("command_usage").insert(to_send).execute()
                )
        except Exception as e:
            log.warning(f"[USAGE] flush failed: {e}")

    async def flush(self):
        """Explicit flush (used by the periodic task and shutdown paths)."""
        async with self._lock:
            await self._flush_locked()

    async def start_periodic_flush(self):
        """Background coroutine: flush every flush_interval seconds.
        Started once from main.py setup_hook via asyncio.create_task."""
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush()
            except Exception as e:
                log.warning(f"[USAGE] periodic flush error: {e}")

    def pending(self) -> int:
        """How many invocations are queued but not yet flushed."""
        return len(self._buffer)


# Singleton — main.py's hook and any future /usage stats read this.
usage_logger = UsageLogger()
