"""
utils/db.py — Single database utility file.

Tries to use Supabase (PostgreSQL) if SUPABASE_URL and SUPABASE_KEY
are set in env. Falls back to local JSON files otherwise.

Every cog imports from here. This protects data from being wiped on
Render free-tier redeploys.

SUPABASE TABLE SCHEMAS
Run these SQL commands in your Supabase SQL editor:

CREATE TABLE warnings (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  case_id INT,
  type TEXT DEFAULT 'warn',
  reason TEXT,
  mod_id TEXT,
  mod_name TEXT,
  timestamp TEXT
);

CREATE TABLE reminders (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  text TEXT,
  end_time FLOAT,
  channel_id TEXT,
  fired BOOLEAN DEFAULT FALSE
);

CREATE TABLE welcome_settings (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  message TEXT,
  enabled BOOLEAN DEFAULT TRUE,
  goodbye_channel_id TEXT,
  goodbye_message TEXT,
  goodbye_enabled BOOLEAN DEFAULT TRUE,
  autorole_id TEXT
);

CREATE TABLE log_settings (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  enabled BOOLEAN DEFAULT TRUE,
  message_delete BOOLEAN DEFAULT TRUE,
  message_edit BOOLEAN DEFAULT TRUE,
  member_join BOOLEAN DEFAULT TRUE,
  member_leave BOOLEAN DEFAULT TRUE,
  member_ban BOOLEAN DEFAULT TRUE,
  member_unban BOOLEAN DEFAULT TRUE,
  role_change BOOLEAN DEFAULT TRUE,
  nickname_change BOOLEAN DEFAULT TRUE,
  voice_join BOOLEAN DEFAULT TRUE,
  voice_leave BOOLEAN DEFAULT TRUE
);

CREATE TABLE mod_settings (
  guild_id TEXT PRIMARY KEY,
  log_channel_id TEXT,
  admin_role_id TEXT,
  max_warns_before_ban INT DEFAULT 5
);

CREATE TABLE server_settings (
  guild_id TEXT PRIMARY KEY,
  autorole_id TEXT,
  custom_status TEXT,
  custom_status_type TEXT
);
"""
import os
import json
import logging
from typing import Any

logger = logging.getLogger('cyn.db')

# Try to use Supabase if configured, fall back to JSON files
_supabase = None
_use_supabase = False

# FIX 3 — Track which Supabase errors have been logged so we don't spam
# the logs every 30 seconds (e.g. reminder background task polling).
# Each error is logged ONCE, then we silently fall back to JSON.
_supabase_error_logged = set()


def init_db():
    """Initialize the database connection. Call this in main.py on_ready."""
    global _supabase, _use_supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if url and key:
        try:
            from supabase import create_client
            _supabase = create_client(url, key)
            _use_supabase = True
            logger.info("[DB] Connected to Supabase")
        except ImportError:
            logger.warning("[DB] supabase package not installed, using JSON files")
            _use_supabase = False
        except Exception as e:
            logger.warning(f"[DB] Supabase failed, using JSON: {e}")
            _use_supabase = False
    else:
        logger.info("[DB] No Supabase config, using JSON files")
        _use_supabase = False


def using_supabase() -> bool:
    return _use_supabase


# ─── JSON fallback helpers ─────────────────────────────────────

def _read_json(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: str, data: dict):
    import os as _os
    dirname = _os.path.dirname(path) if '/' in path else 'data'
    _os.makedirs(dirname, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ─── Guild settings (welcome, logs, autorole, bot config) ──────

def get_guild_setting(guild_id: int, table: str) -> dict:
    """Get settings for a guild from a specific table/file."""
    if _use_supabase:
        try:
            result = _supabase.table(table).select("*").eq(
                "guild_id", str(guild_id)
            ).execute()
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            error_key = f"get_guild_setting_{table}"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_guild_setting ({table}) error: {e}")
                logger.warning(
                    f"[DB] Supabase permission issue for table '{table}'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json(f"data/{table}.json")
            return data.get(str(guild_id), {})
    else:
        data = _read_json(f"data/{table}.json")
        return data.get(str(guild_id), {})


def set_guild_setting(guild_id: int, table: str, settings: dict):
    """Save settings for a guild."""
    if _use_supabase:
        try:
            existing = _supabase.table(table).select("guild_id").eq(
                "guild_id", str(guild_id)
            ).execute()
            if existing.data:
                _supabase.table(table).update(settings).eq(
                    "guild_id", str(guild_id)
                ).execute()
            else:
                _supabase.table(table).insert({
                    "guild_id": str(guild_id), **settings
                }).execute()
        except Exception as e:
            error_key = f"set_guild_setting_{table}"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_guild_setting ({table}) error: {e}")
                logger.warning(
                    f"[DB] Supabase permission issue for table '{table}'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json(f"data/{table}.json")
            data[str(guild_id)] = settings
            _write_json(f"data/{table}.json", data)
    else:
        data = _read_json(f"data/{table}.json")
        data[str(guild_id)] = settings
        _write_json(f"data/{table}.json", data)


# ─── Warnings ──────────────────────────────────────────────────

def get_warnings(guild_id: int, user_id: int) -> list:
    """Get all warnings for a user in a guild."""
    if _use_supabase:
        try:
            result = _supabase.table("warnings").select("*").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            return result.data or []
        except Exception as e:
            error_key = "get_warnings"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_warnings error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'warnings'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/warnings.json")
            return data.get(str(guild_id), {}).get(str(user_id), [])
    else:
        data = _read_json("data/warnings.json")
        return data.get(str(guild_id), {}).get(str(user_id), [])


def add_warning(guild_id: int, user_id: int, warning: dict) -> int:
    """Add a warning and return the case ID."""
    if _use_supabase:
        try:
            warning["guild_id"] = str(guild_id)
            warning["user_id"] = str(user_id)
            result = _supabase.table("warnings").insert(warning).execute()
            return result.data[0].get("case_id", 0) if result.data else 0
        except Exception as e:
            error_key = "add_warning"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] add_warning error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'warnings'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/warnings.json")
            g = str(guild_id)
            u = str(user_id)
            if g not in data:
                data[g] = {}
            if u not in data[g]:
                data[g][u] = []
            all_cases = [
                w.get("case_id", 0)
                for cases in data[g].values()
                for w in cases
                if isinstance(w, dict)
            ]
            case_id = max(all_cases, default=0) + 1
            warning["case_id"] = case_id
            data[g][u].append(warning)
            _write_json("data/warnings.json", data)
            return case_id
    else:
        data = _read_json("data/warnings.json")
        g = str(guild_id)
        u = str(user_id)
        if g not in data:
            data[g] = {}
        if u not in data[g]:
            data[g][u] = []
        all_cases = [
            w.get("case_id", 0)
            for cases in data[g].values()
            for w in cases
            if isinstance(w, dict)
        ]
        case_id = max(all_cases, default=0) + 1
        warning["case_id"] = case_id
        data[g][u].append(warning)
        _write_json("data/warnings.json", data)
        return case_id


def clear_warnings(guild_id: int, user_id: int):
    """Clear all warnings for a user."""
    if _use_supabase:
        try:
            _supabase.table("warnings").delete().eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
        except Exception as e:
            error_key = "clear_warnings"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] clear_warnings error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'warnings'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/warnings.json")
            g = str(guild_id)
            u = str(user_id)
            if g in data and u in data[g]:
                data[g][u] = []
            _write_json("data/warnings.json", data)
    else:
        data = _read_json("data/warnings.json")
        g = str(guild_id)
        u = str(user_id)
        if g in data and u in data[g]:
            data[g][u] = []
        _write_json("data/warnings.json", data)


# ─── Reminders ─────────────────────────────────────────────────

def get_all_reminders() -> list:
    """Get all pending reminders across all users."""
    if _use_supabase:
        try:
            result = _supabase.table("reminders").select("*").eq(
                "fired", False
            ).execute()
            return result.data or []
        except Exception as e:
            error_key = "get_all_reminders"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_all_reminders error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'reminders'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON for reminders."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/reminders.json")
            all_reminders = []
            for user_id, reminders in data.items():
                if not isinstance(reminders, list):
                    continue
                for r in reminders:
                    if isinstance(r, dict):
                        r["user_id"] = user_id
                        r["id"] = r.get("id", f"{user_id}_{r.get('end_time', 0)}")
                        all_reminders.append(r)
            return all_reminders
    else:
        data = _read_json("data/reminders.json")
        all_reminders = []
        for user_id, reminders in data.items():
            if not isinstance(reminders, list):
                continue
            for r in reminders:
                if isinstance(r, dict):
                    r["user_id"] = user_id
                    r["id"] = r.get("id", f"{user_id}_{r.get('end_time', 0)}")
                    all_reminders.append(r)
        return all_reminders


def add_reminder(user_id: int, reminder: dict):
    """Add a reminder for a user."""
    if _use_supabase:
        try:
            reminder["user_id"] = str(user_id)
            reminder["fired"] = False
            _supabase.table("reminders").insert(reminder).execute()
        except Exception as e:
            error_key = "add_reminder"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] add_reminder error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'reminders'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON for reminders."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/reminders.json")
            u = str(user_id)
            if u not in data:
                data[u] = []
            if not isinstance(data[u], list):
                data[u] = []
            if "id" not in reminder:
                reminder["id"] = f"{u}_{reminder.get('end_time', 0)}_{len(data[u])}"
            data[u].append(reminder)
            _write_json("data/reminders.json", data)
    else:
        data = _read_json("data/reminders.json")
        u = str(user_id)
        if u not in data:
            data[u] = []
        if not isinstance(data[u], list):
            data[u] = []
        if "id" not in reminder:
            reminder["id"] = f"{u}_{reminder.get('end_time', 0)}_{len(data[u])}"
        data[u].append(reminder)
        _write_json("data/reminders.json", data)


def remove_reminder(user_id: int, reminder_id: str):
    """Remove a reminder after it fires."""
    if _use_supabase:
        try:
            _supabase.table("reminders").delete().eq(
                "id", reminder_id
            ).execute()
        except Exception as e:
            error_key = "remove_reminder"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] remove_reminder error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'reminders'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON for reminders."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/reminders.json")
            u = str(user_id)
            if u in data and isinstance(data[u], list):
                data[u] = [
                    r for r in data[u]
                    if r.get("id") != reminder_id
                ]
                _write_json("data/reminders.json", data)
    else:
        data = _read_json("data/reminders.json")
        u = str(user_id)
        if u in data and isinstance(data[u], list):
            data[u] = [
                r for r in data[u]
                if r.get("id") != reminder_id
            ]
            _write_json("data/reminders.json", data)


def get_user_reminders(user_id: int) -> list:
    """Get all pending reminders for a specific user."""
    if _use_supabase:
        try:
            result = _supabase.table("reminders").select("*").eq(
                "user_id", str(user_id)
            ).eq("fired", False).execute()
            return result.data or []
        except Exception as e:
            error_key = "get_user_reminders"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_reminders error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'reminders'. "
                    "Run GRANT SQL in your Supabase SQL editor. "
                    "Falling back to JSON for reminders."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/reminders.json")
            u = str(user_id)
            reminders = data.get(u, [])
            if not isinstance(reminders, list):
                return []
            for r in reminders:
                if isinstance(r, dict):
                    r["user_id"] = u
                    if "id" not in r:
                        r["id"] = f"{u}_{r.get('end_time', 0)}"
            return reminders
    else:
        data = _read_json("data/reminders.json")
        u = str(user_id)
        reminders = data.get(u, [])
        if not isinstance(reminders, list):
            return []
        for r in reminders:
            if isinstance(r, dict):
                r["user_id"] = u
                if "id" not in r:
                    r["id"] = f"{u}_{r.get('end_time', 0)}"
        return reminders
