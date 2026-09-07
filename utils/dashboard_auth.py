"""
utils/dashboard_auth.py — Discord OAuth helpers for the web dashboard.

PART 1 / 1.1 of the dashboard spec. Every /api/dashboard/* endpoint uses
these three functions to authenticate the caller and authorize guild
mutations.

How it works
------------
* The dashboard frontend holds a Discord OAuth2 *user* access token
  (scopes: identify + guilds) in an httpOnly cookie on the dashboard
  domain. Every API call carries it as `Authorization: Bearer <token>`.
* `verify_discord_token(token)` calls GET /users/@me on the Discord API
  to prove the token is live and returns the user object. Results are
  cached for 120s so hot dashboards don't burn Discord quota.
* `get_user_guilds(token)` calls GET /users/@me/guilds (ALL pages —
  Discord caps each response at 200 guilds, so the target guild can sit
  on page 2+ for members of many servers). That response already
  includes the caller's `owner` flag and computed `permissions` bitmask
  for every guild, so `verify_guild_permission()` can answer "does this
  user have manage_guild in guild X?" WITHOUT a second API call. Guild
  lists are cached for 5 minutes (per spec).

Failure taxonomy (v2 — fixes the flaky "you need Manage Server" 403)
--------------------------------------------------------------------
Live testing showed 5 parallel dashboard requests racing on a cold
guild-list cache: each thread fired its own Discord API call, and any
transient failure (Render network blip, Discord 429, 10s timeout)
fail-closed as a 403 that confused owners. The API now distinguishes:

  * 'auth'      — Discord answered 401/403: the token really is dead.
  * 'transient' — network error / timeout / 429 / 5xx: retryable, and
                  cached negatively for only ~3 seconds.
  * 'not_found' — the guild list loaded fine but the target guild
                  isn't in it (user left, or no access).

`verify_guild_permission_detailed()` returns (allowed, reason) so the
Flask layer can answer 503 (retryable) instead of a misleading 403, and
the frontend can show "verifying permissions..." and retry. The old
boolean `verify_guild_permission()` is kept as a thin wrapper.

Implementation notes
--------------------
* Uses only the Python stdlib (urllib.request) — no new dependencies on
  Render. All calls have a 10s timeout and NEVER raise; failures map to
  (None, error_kind) so callers return clean 401/403/503.
* Thread safety: these run inside Flask worker threads. A threading.Lock
  guards the caches, and a per-token in-flight registry collapses
  concurrent identical fetches into ONE Discord API call (single-flight),
  which is what killed the herd-of-5 race above.
* Design deviation from the spec (documented, same spirit as
  utils/cache.py's asyncio.Lock -> RLock note): the spec drafted
  `verify_guild_permission(user_id, guild_id, required_perm)` which would
  require fetching the guild member with the BOT token (an extra REST
  call per check). The OAuth /users/@me/guilds response already ships the
  caller's permission bitmask, so we verify from the (cached) guild list
  instead — same security guarantee, one API call per 5 minutes instead
  of one per request.
"""
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger('cyn.dashboard_auth')

DISCORD_API = "https://discord.com/api/v10"
_HTTP_TIMEOUT = 10

# Dashboard origin (env-driven — NEVER hardcoded, so changing the deployed
# domain only requires updating DASHBOARD_URL on Render). Used only for the
# descriptive User-Agent sent to the Discord API.
DASHBOARD_URL = (os.getenv("DASHBOARD_URL") or "").rstrip("/")


def _user_agent() -> str:
    """Identify this integration to Discord without a hardcoded domain."""
    return f"AureliaDashboard ({DASHBOARD_URL})" if DASHBOARD_URL else "AureliaDashboard"

# MANAGE_GUILD is permission bit 0x20 (1 << 5).
PERM_MANAGE_GUILD = 1 << 5

# Cache TTLs (seconds) — per spec: guild list 5 minutes; the tiny
# /users/@me payload gets 2 minutes. Negative (failure) TTLs differ:
# a dead token stays dead (15s), a transient blip is retried almost
# immediately (3s).
USER_CACHE_TTL = 120
GUILDS_CACHE_TTL = 300
NEGATIVE_TTL_AUTH = 15
NEGATIVE_TTL_TRANSIENT = 3

# /users/@me/guilds is paginated: 200 guilds per page. Members of very
# many servers need the follow-up pages for accurate permission checks.
_GUILDS_PAGE_SIZE = 200
_GUILDS_MAX_PAGES = 4

# Reasons returned by verify_guild_permission_detailed:
#   ok            -> allowed
#   no_permission -> guild found, bitmask/owner says no   -> 403
#   not_found     -> guild not in the caller's guild list -> 403 (fail closed)
#   transient     -> Discord unreachable / rate limited   -> 503 (retry)
#   auth          -> bearer rejected by Discord           -> 401
VERIFY_OK = "ok"
VERIFY_NO_PERMISSION = "no_permission"
VERIFY_NOT_FOUND = "not_found"
VERIFY_TRANSIENT = "transient"
VERIFY_AUTH = "auth"

_lock = threading.Lock()
# bearer-hash -> (payload, expiry)
_user_cache: dict = {}
# bearer-hash -> (guild_list, expiry)  |  (None, expiry) while negative
_guilds_cache: dict = {}
# bearer-hash -> threading.Event for the in-flight guild fetch (single-flight)
_guilds_inflight: dict = {}


def _token_key(token: str) -> str:
    """Stable, non-reversible key for cache maps (tokens never at rest)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _discord_get_raw(path: str, token: str) -> Tuple[Optional[dict | list], Optional[str]]:
    """GET a Discord API path with a Bearer token. Never raises.

    Returns (data, None) on 2xx, (None, error_kind) otherwise, where
    error_kind is:
      'auth'      — 401/403 from Discord (token revoked / expired)
      'transient' — 429, 5xx, network error, timeout, bad JSON
    """
    url = f"{DISCORD_API}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": _user_agent(),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return None, "transient"
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, "auth"
        # 429 / 5xx / anything else — worth another attempt shortly
        return None, "transient"
    except Exception as e:
        logger.debug(f"[dashboard_auth] {path} failed: {type(e).__name__}: {e}")
        return None, "transient"


def _discord_get(path: str, token: str) -> Optional[dict | list]:
    """Backward-compatible wrapper: data or None."""
    data, _err = _discord_get_raw(path, token)
    return data


def verify_discord_token(token: str) -> Optional[dict]:
    """Verify a Discord OAuth bearer token.

    Returns the user object {id, username, global_name, avatar, ...}
    or None if the token is missing/invalid/expired. Cached 2 minutes.
    """
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    key = _token_key(token)

    with _lock:
        cached = _user_cache.get(key)
        if cached and time.time() < cached[1]:
            return cached[0]

    data, err = _discord_get_raw("/users/@me", token)
    if err or not isinstance(data, dict) or not data.get("id"):
        # negative result cached briefly so a flood of bad tokens
        # doesn't hammer the Discord API
        with _lock:
            _user_cache[key] = (None, time.time() + NEGATIVE_TTL_AUTH)
        return None

    with _lock:
        _user_cache[key] = (data, time.time() + USER_CACHE_TTL)
    return data


def _fetch_guild_pages(token: str) -> Tuple[Optional[list], Optional[str]]:
    """Fetch every page of /users/@me/guilds (200 per page, capped)."""
    guilds: list = []
    after = None
    for _page in range(_GUILDS_MAX_PAGES):
        path = "/users/@me/guilds?limit=200"
        if after:
            path += f"&after={after}"
        data, err = _discord_get_raw(path, token)
        if err or not isinstance(data, list):
            if _page == 0:
                return None, err or "transient"
            # partial pages beat no data: the first page already arrived
            return guilds, None
        guilds.extend(g for g in data if isinstance(g, dict))
        if len(data) < _GUILDS_PAGE_SIZE:
            break
        last_id = data[-1].get("id")
        if not last_id:
            break
        after = str(last_id)
    return guilds, None


def get_user_guilds_detailed(token: str) -> Tuple[Optional[list], Optional[str]]:
    """Fetch the token owner's FULL guild list (all pages). Cached 5 min.

    Returns (guilds, None) on success — a list of partial guild objects:
      {id, name, icon, owner, permissions, features}
    or (None, error_kind) when Discord couldn't be reached ('transient')
    or the bearer was rejected ('auth').

    Single-flight: concurrent callers for the same token share ONE
    in-flight request (Event-based) — the thundering herd that used to
    trip transient failures on page load is gone.
    """
    if not token or not isinstance(token, str):
        return None, "auth"
    token = token.strip()
    key = _token_key(token)

    for _attempt in range(3):
        event: Optional[threading.Event]
        owner = False
        with _lock:
            cached = _guilds_cache.get(key)
            if cached and time.time() < cached[1]:
                guilds, err = cached[0], _negative_kinds.get(key)
                if guilds is not None:
                    return guilds, None            # positive hit
                return None, err or "auth"         # live negative hit

            event = _guilds_inflight.get(key)
            if event is None:
                event = threading.Event()
                _guilds_inflight[key] = event
                owner = True
            # else: another thread owns the fetch — wait below

        if not owner:
            # join the in-flight fetch, then re-read the cache
            event.wait(timeout=_HTTP_TIMEOUT + 5)
            with _lock:
                _guilds_inflight.pop(key, None)
            continue

        # we own the fetch — run it exactly once for everyone
        try:
            guilds, err = _fetch_guild_pages(token)
            if guilds is None:
                ttl = NEGATIVE_TTL_AUTH if err == "auth" else NEGATIVE_TTL_TRANSIENT
                with _lock:
                    _guilds_cache[key] = (None, time.time() + ttl)
                    _negative_kinds[key] = err or "transient"
                return None, err or "transient"
            with _lock:
                _guilds_cache[key] = (guilds, time.time() + GUILDS_CACHE_TTL)
            return guilds, None
        finally:
            with _lock:
                _guilds_inflight.pop(key, None)
            event.set()

    # extremely unlikely: three loops without a cache answer
    return None, "transient"


# side map: bearer-hash -> error kind of the cached negative entry
_negative_kinds: dict = {}


def get_user_guilds(token: str) -> Optional[list]:
    """Backward-compatible wrapper: the guild list or None."""
    guilds, _err = get_user_guilds_detailed(token)
    return guilds


def verify_guild_permission_detailed(
    token: str, guild_id, required_perm: int = PERM_MANAGE_GUILD
) -> Tuple[bool, str]:
    """Does the token owner hold `required_perm` in `guild_id`?

    Returns (allowed, reason). reason is one of:
      ok | no_permission | not_found | transient | auth

    - True only when the user owns the guild OR the permission bit is
      set in the bitmask Discord computed for them.
    - 'transient' means "we could not check — retry", NOT "no".
    - Unknown guild / rejected bearer fail closed (not_found / auth).
    """
    guilds, err = get_user_guilds_detailed(token)
    if guilds is None:
        return False, err or "transient"
    gid = str(guild_id)
    for g in guilds:
        if not isinstance(g, dict) or str(g.get("id")) != gid:
            continue
        if g.get("owner"):
            return True, VERIFY_OK
        try:
            perms = int(str(g.get("permissions", "0")))
        except (TypeError, ValueError):
            return False, VERIFY_NO_PERMISSION
        return bool(perms & required_perm), (
            VERIFY_OK if perms & required_perm else VERIFY_NO_PERMISSION
        )
    return False, VERIFY_NOT_FOUND


def verify_guild_permission(token: str, guild_id,
                            required_perm: int = PERM_MANAGE_GUILD) -> bool:
    """Boolean wrapper (kept for compatibility with older callers)."""
    allowed, _reason = verify_guild_permission_detailed(token, guild_id, required_perm)
    return allowed


def invalidate_token_caches(token: str) -> None:
    """Drop cached data for a bearer (used on logout / 401 feedback)."""
    key = _token_key(token)
    with _lock:
        _user_cache.pop(key, None)
        _guilds_cache.pop(key, None)
        _negative_kinds.pop(key, None)


def public_user(user: dict) -> dict:
    """Shape a /users/@me payload for the dashboard /user endpoint."""
    uid = str(user.get("id", ""))
    avatar = user.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png?size=128"
        if avatar else None
    )
    return {
        "id": uid,
        "username": user.get("username", ""),
        "global_name": user.get("global_name"),
        "display_name": user.get("global_name") or user.get("username", ""),
        "avatar": avatar_url,
    }
