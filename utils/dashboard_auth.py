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
* `get_user_guilds(token)` calls GET /users/@me/guilds. That response
  already includes the caller's `owner` flag and computed `permissions`
  bitmask for every guild, so `verify_guild_permission()` can answer
  "does this user have manage_guild in guild X?" WITHOUT a second API
  call. Guild lists are cached for 5 minutes (per spec).

Implementation notes
--------------------
* Uses only the Python stdlib (urllib.request) — no new dependencies on
  Render. All calls have a 10s timeout and NEVER raise; any failure maps
  to None / False so callers can return a clean 401/403.
* Thread safety: these run inside Flask worker threads (and potentially
  the bot loop via the action queue). A threading.Lock guards the caches.
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
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger('cyn.dashboard_auth')

DISCORD_API = "https://discord.com/api/v10"
_HTTP_TIMEOUT = 10

# MANAGE_GUILD is permission bit 0x20 (1 << 5).
PERM_MANAGE_GUILD = 1 << 5

# Cache TTLs (seconds) — per spec: guild list 5 minutes; the tiny
# /users/@me payload gets 2 minutes.
USER_CACHE_TTL = 120
GUILDS_CACHE_TTL = 300

_lock = threading.Lock()
# bearer-hash -> (payload, expiry)
_user_cache: dict = {}
# bearer-hash -> (guild_list, expiry)
_guilds_cache: dict = {}


def _token_key(token: str) -> str:
    """Stable, non-reversible key for cache maps (tokens never at rest)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _discord_get(path: str, token: str) -> Optional[dict | list]:
    """GET a Discord API path with a Bearer token. Never raises.

    Returns parsed JSON on 2xx, None on anything else (401, network,
    timeout, malformed JSON). 401s invalidate nothing here — callers
    simply treat None as "unauthenticated".
    """
    url = f"{DISCORD_API}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "AureliaDashboard (https://aurelia.pages.dev)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return None
    except Exception as e:
        logger.debug(f"[dashboard_auth] {path} failed: {type(e).__name__}: {e}")
        return None


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

    data = _discord_get("/users/@me", token)
    if not isinstance(data, dict) or not data.get("id"):
        # negative result cached briefly so a flood of bad tokens
        # doesn't hammer the Discord API
        with _lock:
            _user_cache[key] = (None, time.time() + 15)
        return None

    with _lock:
        _user_cache[key] = (data, time.time() + USER_CACHE_TTL)
    return data


def get_user_guilds(token: str) -> Optional[list]:
    """Fetch the token owner's guild list. Cached 5 minutes.

    Returns a list of partial guild objects:
      {id, name, icon, owner, permissions, features}
    or None if the call failed / token invalid.
    """
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    key = _token_key(token)

    with _lock:
        cached = _guilds_cache.get(key)
        if cached and time.time() < cached[1]:
            return cached[0]

    data = _discord_get("/users/@me/guilds", token)
    if not isinstance(data, list):
        with _lock:
            _guilds_cache[key] = (None, time.time() + 15)
        return None

    with _lock:
        _guilds_cache[key] = (data, time.time() + GUILDS_CACHE_TTL)
    return data


def verify_guild_permission(token: str, guild_id,
                            required_perm: int = PERM_MANAGE_GUILD) -> bool:
    """Does the token owner hold `required_perm` in `guild_id`?

    True when the user owns the guild OR the permission bit is set in
    the bitmask Discord computed for them. Unknown guild / failed fetch
    -> False (fail closed).
    """
    guilds = get_user_guilds(token)
    if not guilds:
        return False
    gid = str(guild_id)
    for g in guilds:
        if not isinstance(g, dict) or str(g.get("id")) != gid:
            continue
        if g.get("owner"):
            return True
        try:
            perms = int(str(g.get("permissions", "0")))
        except (TypeError, ValueError):
            return False
        return bool(perms & required_perm)
    return False


def invalidate_token_caches(token: str) -> None:
    """Drop cached data for a bearer (used on logout / 401 feedback)."""
    key = _token_key(token)
    with _lock:
        _user_cache.pop(key, None)
        _guilds_cache.pop(key, None)


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
