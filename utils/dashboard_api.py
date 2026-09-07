"""
utils/dashboard_api.py — Flask blueprint for the Aurelia web dashboard.

PART 1 / 1.2 of the dashboard spec. Registered onto the existing Flask
app in main.py:

    from utils.dashboard_api import init_dashboard_api
    init_dashboard_api(app)   # registers the blueprint

Endpoints (all JSON, all under /api/dashboard):

  GET    /user                                   -> profile + manageable Aurelia guilds
  GET    /csrf                                   -> CSRF token bound to the bearer
  GET    /guild/<gid>/overview                   -> name, members, active features, 7d stats
  GET    /guild/<gid>/settings/<module>          -> full settings object (defaults merged)
  PATCH  /guild/<gid>/settings/<module>          -> validated partial update (Supabase write)
  POST   /guild/<gid>/action/<action>            -> enqueue a live bot action ({queued: true})
  GET    /guild/<gid>/module/<module>/data       -> list data (warnings, custom_commands,
                                                    giveaways, achievements, level_rewards,
                                                    qotd_queue, confessions, audit)
  DELETE /guild/<gid>/data/<type>/<id>           -> delete one row
  GET    /guild/<gid>/resources                  -> channels + roles for the pickers
  GET    /guild/<gid>/audit                      -> recent dashboard_audit rows
  GET    /oauth/callback                         -> Discord code exchange (server-side flow)
  GET    /owner/logs                             -> tail of bot.log (OWNER_ID only)
  POST   /owner/<action>                         -> reload_cog / sync_commands /
                                                    blacklist_add / blacklist_remove /
                                                    purge_all_caches (OWNER_ID only)

Security (PART 4 of the spec):
  * Every request needs a valid Discord OAuth Bearer token.
  * Every guild-scoped route verifies the caller holds manage_guild
    (or owns the guild) on the target guild AND that Aurelia is in it.
  * Mutations (PATCH/POST/DELETE) additionally require an X-CSRF-Token
    header issued by GET /csrf and bound to the bearer token.
  * CORS is locked to DASHBOARD_URL (+ localhost origins for dev).
  * Rate limit: 60 requests/minute/IP, sliding window, in-memory.

Implementation notes / deviations (documented):
  * Rate limiting uses a small in-process sliding-window limiter
    instead of flask-limiter. flask-limiter's default storage is also
    in-memory, and Render free tier runs a single process, so the
    guarantee is identical with zero new dependencies. (Swap-in
    instructions are in dashboard/ARCHITECTURE.md.)
  * The bot object is reached through keep_alive.bot_ref (set in
    on_ready) — importing main.py from here would be circular.
  * Supabase calls run in Flask worker threads using the SAME sync
    client the cogs use via asyncio.to_thread; that client is already
    used concurrently from worker threads, so this is safe.
  * Guild settings reads/writes go through utils.db get/set_guild_setting
    so the shared TTL cache + invalidation semantics are preserved.
"""
import asyncio
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, redirect, request
from utils import db as _db
from utils.dashboard_auth import (
    PERM_MANAGE_GUILD,
    get_user_guilds,
    public_user,
    verify_discord_token,
    verify_guild_permission,
)
from utils.dashboard_actions import enqueue_action

logger = logging.getLogger('cyn.dashboard_api')

dashboard_bp = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")

OWNER_ID = os.getenv("OWNER_ID", "")
DASHBOARD_URL = (os.getenv("DASHBOARD_URL") or "").rstrip("/")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")

DISCORD_API = "https://discord.com/api/v10"

# ─── CORS origins: production dashboard + localhost dev servers ─────
_ALLOWED_ORIGINS = set()
if DASHBOARD_URL:
    _ALLOWED_ORIGINS.add(DASHBOARD_URL)
_ALLOWED_ORIGINS.update({
    "http://localhost:3000", "http://127.0.0.1:3000",
})

# ─── Rate limiting: 60 req/min/IP, sliding window ───────────────────
_RATE_LIMIT = 60
_RATE_WINDOW = 60
_rl_lock = threading.Lock()
_rl_map: dict = {}


def _rate_ok(ip: str) -> bool:
    now = time.time()
    with _rl_lock:
        window = _rl_map.setdefault(ip, deque())
        while window and now - window[0] > _RATE_WINDOW:
            window.popleft()
        if len(window) >= _RATE_LIMIT:
            return False
        window.append(now)
        return True


# ─── CSRF: tokens bound to a hash of the bearer, 1h expiry ──────────
_csrf_lock = threading.Lock()
_csrf_store: dict = {}   # token -> (bearer_hash, expiry)


def _bearer_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_csrf(token: str) -> str:
    bh = _bearer_hash(token)
    now = time.time()
    with _csrf_lock:
        for tok, (h, exp) in list(_csrf_store.items()):
            if exp < now:
                _csrf_store.pop(tok, None)
            elif h == bh and now < exp:
                return tok
        tok = secrets.token_urlsafe(32)
        _csrf_store[tok] = (bh, now + 3600)
        return tok


def _csrf_ok(token: str, supplied: str) -> bool:
    if not supplied:
        return False
    bh = _bearer_hash(token)
    with _csrf_lock:
        entry = _csrf_store.get(supplied)
        if not entry:
            return False
        h, exp = entry
        return h == bh and time.time() < exp


# ─── Audit log (Supabase dashboard_audit, JSON fallback) ────────────
def _audit(user_id, guild_id, action, details=None):
    row = {
        "user_id": str(user_id),
        "guild_id": str(guild_id or ""),
        "action": str(action),
        "details": json.dumps(details, default=str) if details else None,
        "ip_address": _client_ip(),
        "user_agent": (request.headers.get("User-Agent") or "")[:256],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        sb = _db.get_supabase()
        if sb:
            sb.table("dashboard_audit").insert(row).execute()
            return
    except Exception as e:
        logger.debug(f"[dashboard] audit supabase insert failed: {e}")
    # JSON fallback — bounded append-only list
    try:
        path = "data/dashboard_audit.json"
        data = _db._read_json(path)
        rows = data.get("rows", [])
        rows.append(row)
        data["rows"] = rows[-500:]
        _db._write_json(path, data)
    except Exception as e:
        logger.debug(f"[dashboard] audit json fallback failed: {e}")


# ─── Helpers ────────────────────────────────────────────────────────
def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _run_async(coro):
    """Run an async-only db helper inside a Flask worker thread.

    Flask threads have no event loop, so asyncio.run() creates a fresh
    one. The bot's loop runs in a different thread — they never meet.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # A loop is somehow running in this thread — fallback: run the
        # underlying sync work directly where possible.
        coro.close()
        return None


def _bot():
    import keep_alive as kl
    return kl.bot_ref


def _get_guild(guild_id: str):
    b = _bot()
    if b is None or not getattr(b, "is_ready", lambda: False)():
        return None, (503, {"error": "bot is still starting, try again shortly"})
    try:
        gid = int(guild_id)
    except (TypeError, ValueError):
        return None, (400, {"error": "invalid guild id"})
    guild = b.get_guild(gid)
    if guild is None:
        return None, (404, {"error": "aurelia is not in that guild"})
    return guild, None


# ─── Module registry: slug -> settings table + defaults ─────────────
DASHBOARD_MODULES = {
    "welcome": {
        "table": "welcome_settings",
        "defaults": {
            "enabled": False, "channel_id": None,
            "message": "Welcome {user} to {server}! You are member #{membercount}.",
            "goodbye_enabled": False, "goodbye_channel_id": None,
            "goodbye_message": "Goodbye {user}, we'll miss you.",
            "autorole_id": None, "welcome_reward": 500,
            "welcomer_reward": 1000, "embed_mode": "embed",
            "dm_message": "", "welcome_image": None,
            "welcome_color": "#FFC0CB", "welcome_title": "",
            "welcome_thumbnail": "avatar",
        },
    },
    "leveling": {
        "table": "leveling_settings",
        "defaults": {
            "enabled": True, "channel_id": None, "rate": 1.0,
            "rewards": {},
            "level_up_message": None,   # None = cog default
            "level_up_channel_mode": "active",
        },
    },
    "qotd": {
        "table": "qotd_settings",
        "defaults": {
            "channel_id": None, "enabled": False, "post_hour_utc": 14,
            "auto_thread": True, "last_post_date": None,
        },
    },
    "anniversary": {
        "table": "anniversary_settings",
        "defaults": {
            "channel_id": None, "enabled": False, "last_run_date": None,
        },
    },
    "ai_automod": {
        "table": "ai_automod_settings",
        "defaults": {
            "enabled": False, "alert_channel_id": None,
            "timeout_minutes": 10, "min_severity": "medium",
        },
    },
    "starboard": {
        "table": "starboard_settings",
        "defaults": {
            "enabled": False, "channel_id": None, "emoji": "⭐",
            "threshold": 5,
        },
    },
    "log": {
        "table": "log_settings",
        "defaults": {
            "enabled": False, "channel_id": None,
            "message_delete": True, "message_edit": True,
            "member_join": True, "member_leave": True,
            "member_ban": True, "member_unban": True,
            "role_change": True, "nickname_change": True,
            "voice_join": True, "voice_leave": True,
        },
    },
    "moderation": {
        "table": "mod_settings",
        "defaults": {
            "log_channel_id": None, "admin_role_id": None,
            "max_warns_before_ban": 3, "warn_threshold_count": 3,
            "warn_threshold_action": "timeout",
            "antilink_channels": None, "antispam_enabled": False,
        },
    },
    "self_roles": {
        "table": "self_role_panels",
        "defaults": {"panels": []},
    },
    "custom_commands": {
        "table": "custom_commands",
        "defaults": {"commands": []},
    },
    "proactive": {
        "table": "proactive_settings",
        "defaults": {"enabled": False, "channel_ids": []},
    },
    "onboarding": {
        "table": "onboarding_settings",
        "defaults": {"enabled": False, "welcome_text": "", "roles": []},
    },
    "nick": {
        "table": "nick_settings",
        "defaults": {
            "channel_id": None, "auto_approve": False, "cooldown_hours": 24,
        },
    },
    "birthdays": {
        "table": "birthday_settings",
        "defaults": {"channel_id": None},
    },
    "bump_reminder": {
        "table": "bump_reminder_state",
        "defaults": {"channel_id": None},
    },
    "confess": {
        "table": "confess_settings",
        "defaults": {"channel_id": None, "count": 0},
    },
    "rules": {
        "table": "server_rules",
        "defaults": {
            "rules": "", "agree_role_id": None, "announcement_channel_id": None,
        },
    },
    "prefix": {
        "table": "prefix_settings",
        "defaults": {"prefix": "!"},
    },
    "autorole": {   # JSON-only cog: data/autorole.json {guild: {role_id}}
        "table": None, "json": "data/autorole.json",
        "defaults": {"role_id": None},
    },
    "colors": {
        "table": None, "data_only": True,
        "note": "color roles are per-user; see module data endpoint",
    },
    "giveaways": {
        "table": None, "data_only": True,
        "note": "giveaway rows; see module data endpoint",
    },
}

# Light type validation for known settings fields (beyond the
# _TABLE_COLUMNS allow-list). Anything not listed passes through.
_FIELD_TYPES = {
    "enabled": bool, "goodbye_enabled": bool, "auto_thread": bool,
    "antispam_enabled": bool, "auto_approve": bool,
    "message_delete": bool, "message_edit": bool, "member_join": bool,
    "member_leave": bool, "member_ban": bool, "member_unban": bool,
    "role_change": bool, "nickname_change": bool, "voice_join": bool,
    "voice_leave": bool,
    "post_hour_utc": int, "timeout_minutes": int, "threshold": int,
    "warn_threshold_count": int, "max_warns_before_ban": int,
    "welcome_reward": int, "welcomer_reward": int,
    "cooldown_hours": int, "count": int,
    "rate": (int, float),
}

# channel-id list style fields -> must be list/None
_LIST_FIELDS = {"channel_ids", "antilink_channels", "roles", "panels", "commands"}

VALID_ACTIONS = {
    "qotd_post_now", "qotd_add", "welcome_test", "giveaway_end",
    "purge_cache",
}
OWNER_ACTIONS = {
    "reload_cog", "sync_commands", "blacklist_add", "blacklist_remove",
    "purge_all_caches",
}


# ─── Decorators ─────────────────────────────────────────────────────
def _auth_error(code, msg):
    return jsonify({"error": msg}), code


def require_api(fn):
    """Auth + rate limit + CSRF wrapper for user-level endpoints."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _rate_ok(_client_ip()):
            return _auth_error(429, "rate limit exceeded (60/min)")
        token = _bearer_token()
        if not token:
            return _auth_error(401, "missing Authorization: Bearer token")
        user = verify_discord_token(token)
        if not user:
            return _auth_error(401, "invalid or expired token")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not _csrf_ok(token, request.headers.get("X-CSRF-Token", "")):
                return _auth_error(403, "missing or invalid CSRF token (GET /api/dashboard/csrf)")
        g.token = token
        g.user = user
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"[dashboard] {request.path} failed: {e}", exc_info=True)
            return _auth_error(500, "internal error")
    return wrapper


def require_guild_api(fn):
    """require_api + guild lookup + manage_guild permission check."""
    from functools import wraps

    @wraps(fn)
    @require_api
    def wrapper(*args, **kwargs):
        guild_id = str(kwargs.get("guild_id", "") or "")
        guild, err = _get_guild(guild_id)
        if err:
            return _auth_error(err[0], err[1]["error"])
        if not verify_guild_permission(g.token, guild_id, PERM_MANAGE_GUILD):
            return _auth_error(403, "you need the Manage Server permission in this guild")
        g.guild = guild
        return fn(*args, **kwargs)
    return wrapper


def require_owner_api(fn):
    """require_api + OWNER_ID match."""
    from functools import wraps

    @wraps(fn)
    @require_api
    def wrapper(*args, **kwargs):
        if not OWNER_ID or str(g.user.get("id")) != OWNER_ID:
            return _auth_error(403, "owner-only endpoint")
        return fn(*args, **kwargs)
    return wrapper


# ─── CORS ───────────────────────────────────────────────────────────
@dashboard_bp.after_request
def _cors(resp):
    origin = request.headers.get("Origin", "")
    if origin and origin in _ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-CSRF-Token"
        )
        resp.headers["Access-Control-Allow-Methods"] = (
            "GET, PATCH, POST, DELETE, OPTIONS"
        )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# ─── 1. GET /user ───────────────────────────────────────────────────
@dashboard_bp.route("/user", methods=["GET"])
@require_api
def get_user():
    guilds = get_user_guilds(g.token) or []
    b = _bot()
    bot_guild_ids = set()
    if b is not None:
        bot_guild_ids = {str(gu.id) for gu in b.guilds}

    manageable = []
    member_counts = {}
    if b is not None:
        member_counts = {str(gu.id): gu.member_count for gu in b.guilds}
    for gu in guilds:
        if not isinstance(gu, dict):
            continue
        gid = str(gu.get("id", ""))
        if gid not in member_counts:
            continue  # aurelia not present
        owner = bool(gu.get("owner"))
        try:
            perms = int(str(gu.get("permissions", "0")))
        except (TypeError, ValueError):
            continue
        if not (owner or perms & PERM_MANAGE_GUILD):
            continue
        icon = gu.get("icon")
        manageable.append({
            "id": gid,
            "name": gu.get("name", "unknown"),
            "icon": (
                f"https://cdn.discordapp.com/icons/{gid}/{icon}.png?size=128"
                if icon else None
            ),
            "owner": owner,
            "member_count": member_counts.get(gid),
        })

    return jsonify({"user": public_user(g.user), "guilds": manageable})


# ─── 2. GET /csrf ───────────────────────────────────────────────────
@dashboard_bp.route("/csrf", methods=["GET"])
@require_api
def get_csrf():
    return jsonify({"csrf_token": _issue_csrf(g.token)})


# ─── 3. GET /guild/<gid>/overview ───────────────────────────────────
_OVERVIEW_FEATURE_TABLES = [
    ("welcome", "welcome_settings", "enabled"),
    ("leveling", "leveling_settings", "enabled"),
    ("qotd", "qotd_settings", "enabled"),
    ("ai_automod", "ai_automod_settings", "enabled"),
    ("starboard", "starboard_settings", "enabled"),
    ("logging", "log_settings", "enabled"),
    ("proactive", "proactive_settings", "enabled"),
    ("onboarding", "onboarding_settings", "enabled"),
    ("nick", "nick_settings", None),
    ("birthdays", "birthday_settings", None),
    ("confessions", "confess_settings", None),
]


def _feature_flags(guild) -> dict:
    flags = {}
    for name, table, enabled_key in _OVERVIEW_FEATURE_TABLES:
        try:
            cfg = _db.get_guild_setting(guild.id, table) or {}
            if enabled_key:
                flags[name] = bool(cfg.get(enabled_key))
            else:
                flags[name] = bool(cfg.get("channel_id"))
        except Exception:
            flags[name] = False
    # count-based flags
    try:
        cc = _db.get_guild_setting(guild.id, "custom_commands") or {}
        flags["custom_commands"] = bool(cc.get("commands"))
    except Exception:
        flags["custom_commands"] = False
    try:
        panels = _db.get_guild_setting(guild.id, "self_role_panels") or {}
        flags["self_roles"] = bool(panels.get("panels"))
    except Exception:
        flags["self_roles"] = False
    try:
        active = _db.get_active_giveaways() or []
        flags["giveaways"] = any(
            str(gw.get("guild_id")) == str(guild.id) for gw in active
        )
    except Exception:
        flags["giveaways"] = False
    return flags


def _usage_stats(guild_id) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = []
    try:
        sb = _db.get_supabase()
        if sb:
            res = sb.table("command_usage").select(
                "user_id, command_name"
            ).eq("guild_id", str(guild_id)).gte("timestamp", since).execute()
            rows = res.data or []
    except Exception:
        rows = []
    users = set()
    commands = {}
    for r in rows:
        users.add(r.get("user_id"))
        name = r.get("command_name", "unknown")
        commands[name] = commands.get(name, 0) + 1
    top = sorted(commands.items(), key=lambda kv: -kv[1])[:5]
    return {
        "commands_used_7d": len(rows),
        "active_users_7d": len(users),
        "top_commands": [{"command": k, "count": v} for k, v in top],
    }


@dashboard_bp.route("/guild/<guild_id>/overview", methods=["GET"])
@require_guild_api
def guild_overview(guild_id):
    guild = g.guild
    icon_url = None
    if guild.icon:
        icon_url = (
            f"https://cdn.discordapp.com/icons/{guild.id}/{guild.icon}.png?size=256"
        )
    joined_at = None
    try:
        if guild.me and guild.me.joined_at:
            joined_at = guild.me.joined_at.isoformat()
    except Exception:
        pass

    online = None
    try:
        import discord
        if guild.member_count and guild.member_count <= 5000:
            online = sum(1 for m in guild.members
                         if m.status != discord.Status.offline)
    except Exception:
        online = None

    return jsonify({
        "id": str(guild.id),
        "name": guild.name,
        "icon": icon_url,
        "member_count": guild.member_count,
        "online_count": online,
        "boost_count": getattr(guild, "premium_subscription_count", 0) or 0,
        "bot_joined_at": joined_at,
        "active_features": _feature_flags(guild),
        "stats": _usage_stats(guild.id),
    })


# ─── 4. GET /guild/<gid>/settings/<module> ──────────────────────────
def _module_settings(guild, module_slug) -> dict:
    mod = DASHBOARD_MODULES.get(module_slug)
    if mod is None:
        return None
    defaults = mod.get("defaults", {})
    if mod.get("table"):
        raw = _db.get_guild_setting(guild.id, mod["table"]) or {}
    elif mod.get("json"):
        raw = _db._read_json(mod["json"]).get(str(guild.id), {}) or {}
    else:
        raw = {}
    merged = dict(defaults)
    merged.update({k: v for k, v in raw.items() if v is not None or k not in merged})
    merged["guild_id"] = str(guild.id)
    return merged


@dashboard_bp.route("/guild/<guild_id>/settings/<module>", methods=["GET"])
@require_guild_api
def get_settings(guild_id, module):
    if module not in DASHBOARD_MODULES:
        return _auth_error(404, f"unknown module '{module}'")
    mod = DASHBOARD_MODULES[module]
    if mod.get("data_only"):
        return jsonify({
            "module": module,
            "settings": {},
            "note": mod.get("note", ""),
            "data_endpoint": f"/api/dashboard/guild/{guild_id}/module/{module}/data",
        })
    return jsonify({"module": module, "settings": _module_settings(g.guild, module)})


# ─── 5. PATCH /guild/<gid>/settings/<module> ────────────────────────
def _validate_patch(mod, body) -> tuple:
    """Returns (ok, sanitized) — sanitized is the merged full settings."""
    if not isinstance(body, dict) or not body:
        return False, {"error": "body must be a non-empty JSON object"}
    table = mod.get("table")
    json_path = mod.get("json")

    if mod.get("data_only"):
        return False, {"error": "module is data-only; use the data endpoints"}

    # field allow-list
    if table:
        allowed = _db._TABLE_COLUMNS.get(table)
        if allowed is not None:
            unknown = [k for k in body if k not in allowed and k != "guild_id"]
            if unknown:
                return False, {
                    "error": f"unknown fields for {table}: {', '.join(sorted(unknown))}",
                    "allowed": sorted(allowed - {"guild_id"}),
                }
    elif json_path:
        allowed = set(mod.get("defaults", {}).keys())
        unknown = [k for k in body if k not in allowed]
        if unknown:
            return False, {
                "error": f"unknown fields: {', '.join(sorted(unknown))}",
                "allowed": sorted(allowed),
            }

    # type validation on known fields
    for key, value in body.items():
        if key == "guild_id":
            continue
        expected = _FIELD_TYPES.get(key)
        if expected is not None and value is not None:
            if isinstance(expected, tuple):
                ok_type = isinstance(value, expected) and not isinstance(value, bool)
            else:
                ok_type = isinstance(value, expected)
            if not ok_type:
                return False, {"error": f"field '{key}' has the wrong type (expected {expected})"}
        if key in _LIST_FIELDS and value is not None and not isinstance(value, list):
            return False, {"error": f"field '{key}' must be a list"}
        if key == "commands" and isinstance(value, list):
            if len(value) > 100:
                return False, {"error": "too many custom commands (max 100)"}
            for entry in value:
                if not isinstance(entry, dict) \
                        or not isinstance(entry.get("trigger"), str) \
                        or not isinstance(entry.get("response"), str):
                    return False, {"error": "each command needs trigger + response strings"}
                if not entry["trigger"].strip() or len(entry["response"]) > 2000:
                    return False, {"error": "invalid trigger or response over 2000 chars"}
        if key == "rewards" and value is not None:
            if not isinstance(value, dict):
                return False, {"error": "rewards must be {level: role_id}"}
            for k, v in value.items():
                if not str(k).isdigit() or not str(v).isdigit():
                    return False, {"error": "rewards keys/values must be numeric ids"}

    return True, body


@dashboard_bp.route("/guild/<guild_id>/settings/<module>", methods=["PATCH"])
@require_guild_api
def patch_settings(guild_id, module):
    if module not in DASHBOARD_MODULES:
        return _auth_error(404, f"unknown module '{module}'")
    mod = DASHBOARD_MODULES[module]

    try:
        body = request.get_json(force=False, silent=True)
    except Exception:
        body = None
    if body is None:
        return _auth_error(400, "body must be valid JSON")

    ok, result = _validate_patch(mod, body)
    if not ok:
        if "allowed" in result:
            return jsonify(result), 400
        return _auth_error(400, result["error"])

    # merge with current settings then write
    current = _module_settings(g.guild, module)
    current.pop("guild_id", None)
    current.update(result)

    if mod.get("table"):
        _db.set_guild_setting(g.guild.id, mod["table"], current)
    elif mod.get("json"):
        data = _db._read_json(mod["json"])
        data[str(g.guild.id)] = current
        _db._write_json(mod["json"], data)

    _audit(g.user.get("id"), guild_id, "settings_patch",
           {"module": module, "fields": sorted(result.keys())})
    logger.info("[dashboard] %s patched %s fields: %s",
                g.user.get("id"), module, sorted(result.keys()))

    return jsonify({
        "module": module,
        "settings": _module_settings(g.guild, module),
    })


# ─── 6. POST /guild/<gid>/action/<action> ───────────────────────────
@dashboard_bp.route("/guild/<guild_id>/action/<action>", methods=["POST"])
@require_guild_api
def guild_action(guild_id, action):
    if action not in VALID_ACTIONS:
        return _auth_error(404, f"unknown action '{action}' (valid: {sorted(VALID_ACTIONS)})")

    params = {}
    if request.content_length:
        try:
            params = request.get_json(force=False, silent=True) or {}
        except Exception:
            params = {}
    if not isinstance(params, dict):
        return _auth_error(400, "params must be a JSON object")

    # action-specific validation
    if action == "welcome_test" and params.get("type") not in (
            None, "welcome", "goodbye"):
        return _auth_error(400, "type must be 'welcome' or 'goodbye'")
    if action == "giveaway_end" and not (params.get("giveaway_id") or "").strip():
        return _auth_error(400, "giveaway_id required")
    if action == "qotd_add":
        q = str(params.get("question", "") or "").strip()
        if not q or len(q) > 300:
            return _auth_error(400, "question required (max 300 chars)")
        params["question"] = q

    queued = enqueue_action({
        "type": action,
        "guild_id": str(guild_id),
        "user_id": str(g.user.get("id")),
        "params": params,
    })
    if not queued:
        return _auth_error(503, "action queue is full — try again shortly")

    _audit(g.user.get("id"), guild_id, f"action_{action}",
           {"params": params})
    return jsonify({"queued": True, "action": action})


# ─── 7. GET /guild/<gid>/module/<module>/data ───────────────────────
def _sb_query(table, guild_id, order_desc=None, columns="*"):
    sb = _db.get_supabase()
    if not sb:
        return None
    q = sb.table(table).select(columns).eq("guild_id", str(guild_id))
    if order_desc:
        q = q.order(order_desc, desc=True)
    return q.execute().data or []


def _member_name(guild, user_id):
    m = guild.get_member(int(user_id)) if str(user_id).isdigit() else None
    if m:
        return m.display_name
    return f"user {user_id}"


def _data_warnings(guild, params) -> dict:
    page = max(1, int(params.get("page", 1) or 1))
    per_page = min(50, max(5, int(params.get("per_page", 20) or 20)))
    user_filter = params.get("user") or None
    sb = _db.get_supabase()
    rows, total = [], 0
    if sb:
        try:
            q = sb.table("warnings").select("*", count="exact").eq(
                "guild_id", str(guild.id))
            if user_filter:
                q = q.eq("user_id", str(user_filter))
            q = q.order("timestamp", desc=True).range(
                (page - 1) * per_page, page * per_page - 1)
            res = q.execute()
            rows = res.data or []
            total = getattr(res, "count", None) or len(rows)
        except Exception as e:
            logger.debug(f"[dashboard] warnings query failed: {e}")
            rows, total = [], 0
    if not rows and not sb:
        # JSON fallback — flatten nested structure
        data = _db._read_json("data/warnings.json").get(str(guild.id), {}) or {}
        flat = []
        for uid, cases in data.items():
            for w in (cases if isinstance(cases, list) else []):
                if isinstance(w, dict):
                    w = dict(w)
                    w["user_id"] = uid
                    flat.append(w)
        if user_filter:
            flat = [w for w in flat if str(w.get("user_id")) == str(user_filter)]
        flat.sort(key=lambda w: str(w.get("timestamp", "")), reverse=True)
        total = len(flat)
        rows = flat[(page - 1) * per_page: page * per_page]
    return {
        "warnings": rows, "total": total,
        "page": page, "per_page": per_page,
    }


def _data_custom_commands(guild) -> dict:
    cfg = _db.get_guild_setting(guild.id, "custom_commands") or {}
    cmds = cfg.get("commands") or []
    return {"custom_commands": cmds if isinstance(cmds, list) else []}


def _data_giveaways(guild) -> dict:
    sb = _db.get_supabase()
    rows = []
    if sb:
        try:
            rows = _sb_query("giveaways", guild.id, order_desc="created_at") or []
        except Exception:
            rows = []
    if not rows:
        data = _db._read_json("data/giveaways.json")
        rows = [gw for gw in data.values()
                if isinstance(gw, dict) and str(gw.get("guild_id")) == str(guild.id)]
        rows.sort(key=lambda gw: str(gw.get("created_at", "")), reverse=True)
    active = [gw for gw in rows if not gw.get("ended")]
    past = [gw for gw in rows if gw.get("ended")]
    return {"active": active, "past": past[:30]}


def _data_achievements(guild) -> dict:
    sb = _db.get_supabase()
    counts: dict = {}
    if sb:
        try:
            rows = _sb_query("user_achievements", guild.id,
                             order_desc="unlocked_at") or []
            for r in rows:
                uid = str(r.get("user_id"))
                counts.setdefault(uid, {"user_id": uid, "achievements": 0, "latest": ""})
                counts[uid]["achievements"] += 1
                counts[uid]["latest"] = max(counts[uid]["latest"],
                                            str(r.get("unlocked_at", "")))
        except Exception:
            counts = {}
    leaderboard = sorted(counts.values(),
                         key=lambda c: -c["achievements"])[:20]
    for c in leaderboard:
        c["display_name"] = _member_name(guild, c["user_id"])
    return {"leaderboard": leaderboard}


def _data_level_rewards(guild) -> dict:
    cfg = _db.get_guild_setting(guild.id, "leveling_settings") or {}
    rewards = cfg.get("rewards") or {}
    items = []
    if isinstance(rewards, dict):
        for level, role_id in sorted(rewards.items(), key=lambda kv: int(kv[0])):
            role = guild.get_role(int(role_id)) if str(role_id).isdigit() else None
            items.append({
                "level": int(level),
                "role_id": str(role_id),
                "role_name": role.name if role else None,
                "role_color": str(role.color) if role else None,
            })
    return {"rewards": items}


def _data_qotd_queue(guild) -> dict:
    rows = _run_async(_db.get_qotd_queue_async(str(guild.id))) or []
    for r in rows:
        if isinstance(r, dict):
            r.setdefault("used", False)
    return {"queue": rows}


def _data_stats(guild) -> dict:
    sb = _db.get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = []
    if sb:
        try:
            res = sb.table("command_usage").select(
                "user_id, command_name, timestamp"
            ).eq("guild_id", str(guild.id)).gte("timestamp", since).execute()
            rows = res.data or []
        except Exception:
            rows = []
    daily: dict = {}
    users_daily: dict = {}
    commands: dict = {}
    for r in rows:
        day = str(r.get("timestamp", ""))[:10]
        daily[day] = daily.get(day, 0) + 1
        users_daily.setdefault(day, set()).add(r.get("user_id"))
        commands[r.get("command_name", "?")] = \
            commands.get(r.get("command_name", "?"), 0) + 1
    series = [
        {"date": d, "commands": daily[d], "active_users": len(users_daily[d])}
        for d in sorted(daily)
    ]
    top = sorted(commands.items(), key=lambda kv: -kv[1])[:10]
    # leveling leaderboard via the cog's storage
    levels = []
    try:
        leveling = _bot().get_cog("Leveling")
        if leveling:
            levels = leveling.get_leaderboard(guild.id, limit=10) or []
    except Exception:
        levels = []
    for row in levels:
        if isinstance(row, dict):
            row["display_name"] = _member_name(guild, row.get("user_id"))
    return {
        "series": series,
        "top_commands": [{"command": k, "count": v} for k, v in top],
        "leveling_leaderboard": levels,
        "total_30d": sum(s["commands"] for s in series),
    }


@dashboard_bp.route("/guild/<guild_id>/module/<module>/data", methods=["GET"])
@require_guild_api
def module_data(guild_id, module):
    params = request.args
    if module == "warnings":
        return jsonify(_data_warnings(g.guild, params))
    if module == "custom_commands":
        return jsonify(_data_custom_commands(g.guild))
    if module == "giveaways":
        return jsonify(_data_giveaways(g.guild))
    if module == "achievements":
        return jsonify(_data_achievements(g.guild))
    if module == "level_rewards":
        return jsonify(_data_level_rewards(g.guild))
    if module == "qotd":
        return jsonify(_data_qotd_queue(g.guild))
    if module == "stats":
        return jsonify(_data_stats(g.guild))
    if module == "colors":
        rows = _run_async(_db.get_guild_color_roles_async(str(guild.id))) or []
        for r in rows:
            if isinstance(r, dict):
                r["display_name"] = _member_name(guild, r.get("user_id"))
        return jsonify({"color_roles": rows})
    if module == "nick":
        rows = _run_async(
            _db.get_pending_nick_requests_async(guild_id)) or []
        return jsonify({"pending": rows})
    return _auth_error(404, f"unknown data module '{module}'")


# ─── 8. DELETE /guild/<gid>/data/<type>/<id> ────────────────────────
@dashboard_bp.route("/guild/<guild_id>/data/<data_type>/<data_id>",
                    methods=["DELETE"])
@require_guild_api
def delete_data(guild_id, data_type, data_id):
    guild = g.guild
    gid = str(guild.id)
    sb = _db.get_supabase()

    if data_type == "warnings":
        deleted = False
        if sb:
            try:
                sb.table("warnings").delete().eq("guild_id", gid).eq(
                    "id", str(data_id)).execute()
                deleted = True
            except Exception:
                deleted = False
        if not deleted:
            # JSON fallback / case_id match
            data = _db._read_json("data/warnings.json")
            gkey = data.get(gid, {})
            removed = False
            for uid, cases in gkey.items():
                keep = []
                for w in (cases if isinstance(cases, list) else []):
                    if str(w.get("id", "")) == str(data_id) \
                            or str(w.get("case_id", "")) == str(data_id):
                        removed = True
                    else:
                        keep.append(w)
                gkey[uid] = keep
            if removed:
                data[gid] = gkey
                _db._write_json("data/warnings.json", data)
            deleted = removed
        if not deleted:
            return _auth_error(404, "warning not found")

    elif data_type == "custom_commands":
        cfg = _db.get_guild_setting(guild.id, "custom_commands") or {}
        cmds = [c for c in (cfg.get("commands") or [])
                if str(c.get("trigger", "")).lower() != str(data_id).lower()]
        if len(cmds) == len(cfg.get("commands") or []):
            return _auth_error(404, "custom command not found")
        _db.set_guild_setting(guild.id, "custom_commands", {"commands": cmds})

    elif data_type == "giveaways":
        gw = _db.get_giveaway(str(data_id))
        if not gw or str(gw.get("guild_id")) != gid:
            return _auth_error(404, "giveaway not found")
        if not gw.get("ended"):
            return _auth_error(409, "end the giveaway before deleting it")
        if sb:
            try:
                sb.table("giveaways").delete().eq("id", str(data_id)).execute()
            except Exception as e:
                logger.debug(f"[dashboard] giveaway delete failed: {e}")
        data = _db._read_json("data/giveaways.json")
        data.pop(str(data_id), None)
        _db._write_json("data/giveaways.json", data)

    elif data_type == "qotd_queue":
        removed = False
        if sb:
            try:
                sb.table("qotd_queue").delete().eq("id", str(data_id)).eq(
                    "guild_id", gid).execute()
                removed = True
            except Exception:
                removed = False
        if not removed:
            rows = _run_async(_db.get_qotd_queue_async(gid)) or []
            rows = [r for r in rows
                    if str(r.get("id", "")) != str(data_id)
                    and str(r.get("question", "")) != str(data_id)]
            # persist remaining queue back (JSON path)
            data = _db._read_json("data/qotd_queue.json")
            data[gid] = rows
            _db._write_json("data/qotd_queue.json", data)

    else:
        return _auth_error(404, f"unknown data type '{data_type}'")

    _audit(g.user.get("id"), guild_id, "data_delete",
           {"type": data_type, "id": str(data_id)})
    return jsonify({"deleted": True, "type": data_type, "id": str(data_id)})


# ─── 9. GET /guild/<gid>/resources (pickers) ────────────────────────
@dashboard_bp.route("/guild/<guild_id>/resources", methods=["GET"])
@require_guild_api
def guild_resources(guild_id):
    guild = g.guild
    channels = []
    for ch in guild.channels:
        try:
            channels.append({
                "id": str(ch.id),
                "name": ch.name,
                "type": int(ch.type),
                "type_name": str(ch.type),
                "category": (str(ch.category_id) if getattr(ch, "category_id", None) else None),
                "position": getattr(ch, "position", 0),
            })
        except Exception:
            continue
    channels.sort(key=lambda c: (c.get("category") or "", c.get("name", "")))

    roles = []
    for r in guild.roles:
        if r.is_default() or getattr(r, "managed", False):
            continue
        roles.append({
            "id": str(r.id),
            "name": r.name,
            "color": f"#{r.color.value:06x}" if r.color.value else None,
            "position": r.position,
        })
    roles.sort(key=lambda r: -r["position"])

    me = guild.me
    my_perms = me.guild_permissions if me else None
    return jsonify({
        "channels": channels,
        "roles": roles,
        "member_count": guild.member_count,
        "boost_count": getattr(guild, "premium_subscription_count", 0) or 0,
        "bot_permissions": {
            "manage_roles": bool(my_perms and my_perms.manage_roles),
            "manage_channels": bool(my_perms and my_perms.manage_channels),
            "moderate_members": bool(my_perms and my_perms.moderate_members),
            "send_messages": bool(my_perms and my_perms.send_messages),
            "embed_links": bool(my_perms and my_perms.embed_links),
        },
    })


# ─── 10. GET /guild/<gid>/audit ─────────────────────────────────────
@dashboard_bp.route("/guild/<guild_id>/audit", methods=["GET"])
@require_guild_api
def guild_audit(guild_id):
    sb = _db.get_supabase()
    rows = []
    if sb:
        try:
            rows = sb.table("dashboard_audit").select("*").eq(
                "guild_id", str(guild_id)).order(
                "timestamp", desc=True).limit(50).execute().data or []
        except Exception:
            rows = []
    if not rows:
        data = _db._read_json("data/dashboard_audit.json")
        rows = [r for r in data.get("rows", [])
                if str(r.get("guild_id")) == str(guild_id)][-50:][::-1]
    return jsonify({"entries": rows})


# ─── 11. GET /oauth/callback ────────────────────────────────────────
@dashboard_bp.route("/oauth/callback", methods=["GET"])
def oauth_callback():
    """Server-side Discord code exchange (alternative to the Next.js
    exchange route). Redirects to DASHBOARD_URL#token=... on success.

    The primary flow (used by the dashboard UI) exchanges the code in
    the Next.js route handler app/api/auth/exchange/route.ts so the
    token lands in an httpOnly cookie on the dashboard's own domain.
    This endpoint exists for the spec's curl/CLI flow and for setups
    where the dashboard is static-only.
    """
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error", "")
    base = DASHBOARD_URL or request.args.get("dashboard", "")

    if error:
        target = f"{base}/oauth/callback#error={urllib.parse.quote(error)}"
        return redirect(target) if base else jsonify({"error": error}), 400
    if not code:
        return _auth_error(400, "missing ?code")
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET):
        return _auth_error(500, "server missing DISCORD_CLIENT_ID/SECRET")
    redirect_uri = OAUTH_REDIRECT_URI or \
        f"{request.url_root.rstrip('/')}/api/dashboard/oauth/callback"

    data = urllib.parse.urlencode({
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{DISCORD_API}/oauth2/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        logger.warning(f"[dashboard] oauth exchange failed: {e.code} {detail}")
        if base:
            return redirect(f"{base}/oauth/callback#error=exchange_failed")
        return _auth_error(400, f"token exchange failed: {e.code}")
    except Exception as e:
        logger.warning(f"[dashboard] oauth exchange error: {e}")
        return _auth_error(500, "token exchange error")

    token = payload.get("access_token", "")
    if not token:
        return _auth_error(400, "no access_token in response")
    actor = verify_discord_token(token)
    _audit((actor or {}).get("id", "unknown"), None, "oauth_login",
           {"via": "flask"})
    if base:
        # fragment, not query — never logged by proxies/servers
        return redirect(f"{base}/oauth/callback#token={urllib.parse.quote(token)}")
    # local/CLI testing without DASHBOARD_URL: return JSON
    return jsonify({
        "access_token": token,
        "token_type": payload.get("token_type", "Bearer"),
        "expires_in": payload.get("expires_in"),
        "scope": payload.get("scope"),
        "refresh_token": payload.get("refresh_token"),
    })


# ─── 12/13. Owner endpoints ─────────────────────────────────────────
@dashboard_bp.route("/owner/logs", methods=["GET"])
@require_owner_api
def owner_logs():
    try:
        lines = min(500, max(10, int(request.args.get("lines", 200))))
    except ValueError:
        lines = 200
    try:
        with open("bot.log", "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 256 * 1024))
            chunk = f.read().decode("utf-8", "replace")
        tail = chunk.splitlines()[-lines:]
    except Exception as e:
        return _auth_error(500, f"could not read bot.log: {e}")
    return jsonify({"lines": tail})


@dashboard_bp.route("/owner/<action>", methods=["POST"])
@require_owner_api
def owner_action(action):
    if action not in OWNER_ACTIONS:
        return _auth_error(404, f"unknown owner action (valid: {sorted(OWNER_ACTIONS)})")
    params = {}
    if request.content_length:
        try:
            params = request.get_json(force=False, silent=True) or {}
        except Exception:
            params = {}
    if not isinstance(params, dict):
        return _auth_error(400, "params must be a JSON object")

    if action in ("reload_cog",) and not str(params.get("cog", "")).strip():
        return _auth_error(400, "cog name required")

    # map dashboard action names -> executor action types
    atype = {
        "blacklist_add": "blacklist_user",
        "blacklist_remove": "blacklist_user",
    }.get(action, action)
    if action == "blacklist_add":
        params = {"user_id": str(params.get("user_id", "")), "remove": False}
        if not params["user_id"].isdigit():
            return _auth_error(400, "user_id required")
    elif action == "blacklist_remove":
        params = {"user_id": str(params.get("user_id", "")), "remove": True}
        if not params["user_id"].isdigit():
            return _auth_error(400, "user_id required")

    queued = enqueue_action({
        "type": atype,
        "guild_id": str(params.get("guild_id", "") or ""),
        "user_id": str(g.user.get("id")),
        "params": params,
    })
    if not queued:
        return _auth_error(503, "action queue is full")
    _audit(g.user.get("id"), None, f"owner_{action}", {"params": params})
    return jsonify({"queued": True, "action": action})


# ─── registration hook (called from main.py) ────────────────────────
def init_dashboard_api(app):
    app.register_blueprint(dashboard_bp)

    # ── CORS for the public health endpoints ──────────────────────
    # `/health` and `/stats` live on the main Flask app (main.py), NOT
    # on this blueprint, so the blueprint's after_request CORS hook
    # never runs for them. The dashboard's landing-page status card
    # fetches GET /health cross-origin from the browser every 30s,
    # so these two public read-only metrics routes need the SAME
    # origin allow-list. App-level hook, additive only — no bot
    # behavior change, no rate limiting implications (the limiter
    # only guards /api/dashboard/* via require_api).
    @app.after_request
    def _public_metrics_cors(resp):
        if request.path in ("/health", "/stats"):
            origin = request.headers.get("Origin", "")
            if origin and origin in _ALLOWED_ORIGINS:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"
                resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
                resp.headers["Access-Control-Max-Age"] = "300"
        return resp

    logger.info(
        "✅ Dashboard API registered under /api/dashboard (CORS: %s)",
        ", ".join(sorted(_ALLOWED_ORIGINS)) or "dev (localhost)",
    )
