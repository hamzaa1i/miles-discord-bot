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

-- PHASE 2A — Persistent conversation memory per user per guild
CREATE TABLE conversation_memory (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL
);

-- PHASE 2B — Per-server personality notes
CREATE TABLE server_personality (
  guild_id TEXT PRIMARY KEY,
  personality_note TEXT,
  set_by TEXT,
  updated_at TEXT
);

-- PHASE 3 — NEW TABLES, run in Supabase SQL editor:
--
-- CREATE TABLE IF NOT EXISTS user_profiles (
--   user_id TEXT PRIMARY KEY,
--   bio TEXT,
--   pronouns TEXT,
--   timezone TEXT,
--   updated_at TEXT
-- );
-- GRANT ALL ON public.user_profiles TO anon;
--
-- CREATE TABLE IF NOT EXISTS birthdays (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   month INT NOT NULL,
--   day INT NOT NULL,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.birthdays TO anon;
--
-- CREATE TABLE IF NOT EXISTS server_rules (
--   guild_id TEXT PRIMARY KEY,
--   rules TEXT,
--   agree_role_id TEXT,
--   announcement_channel_id TEXT
-- );
-- GRANT ALL ON public.server_rules TO anon;
--
-- CREATE TABLE IF NOT EXISTS tempbans (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   unban_time FLOAT NOT NULL,
--   reason TEXT
-- );
-- GRANT ALL ON public.tempbans TO anon;
-- GRANT ALL ON SEQUENCE tempbans_id_seq TO anon;
--
-- ALTER TABLE mod_settings ADD COLUMN IF NOT EXISTS warn_threshold_count INT DEFAULT 5;
-- ALTER TABLE mod_settings ADD COLUMN IF NOT EXISTS warn_threshold_action TEXT DEFAULT 'timeout_1h';
-- ALTER TABLE mod_settings ADD COLUMN IF NOT EXISTS antilink_channels TEXT[] DEFAULT '{}';
--
-- CREATE TABLE IF NOT EXISTS confess_settings (
--   guild_id TEXT PRIMARY KEY,
--   channel_id TEXT
-- );
-- GRANT ALL ON public.confess_settings TO anon;
-- ALTER TABLE public.confess_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS prefix_settings (
--   guild_id TEXT PRIMARY KEY,
--   prefix TEXT
-- );
-- GRANT ALL ON public.prefix_settings TO anon;
-- ALTER TABLE public.prefix_settings DISABLE ROW LEVEL SECURITY;
--
-- ALTER TABLE conversation_memory ADD COLUMN IF NOT EXISTS channel_id TEXT DEFAULT '0';
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


# ─── PHASE 2A: Persistent Conversation Memory ──────────────────

def get_conversation_history(guild_id: int, user_id: int, channel_id: int = 0,
                              limit: int = 20) -> list:
    """Get recent conversation history for a user in a guild+channel.
    FIX 6 — Now scoped to channel_id for per-channel memory."""
    if _use_supabase:
        try:
            query = _supabase.table("conversation_memory").select("*").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id))
            # FIX 6 — Filter by channel_id if provided
            if channel_id:
                query = query.eq("channel_id", str(channel_id))
            result = query.order("id", desc=True).limit(limit).execute()
            return list(reversed(result.data or []))
        except Exception as e:
            error_key = "get_conversation_history"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_conversation_history error: {e}")
                _supabase_error_logged.add(error_key)
            data = _read_json("data/conversation_memory.json")
            key = f"{guild_id}_{user_id}_{channel_id}"
            entries = data.get(key, [])
            if not isinstance(entries, list):
                return []
            return entries[-limit:]
    else:
        data = _read_json("data/conversation_memory.json")
        key = f"{guild_id}_{user_id}_{channel_id}"
        entries = data.get(key, [])
        if not isinstance(entries, list):
            return []
        return entries[-limit:]


def save_conversation_message(guild_id: int, user_id: int, role: str,
                               content: str, timestamp: str = None,
                               channel_id: int = 0):
    """Save a message into conversation history.
    FIX 6 — Now scoped to channel_id for per-channel memory."""
    if timestamp is None:
        from datetime import datetime as _dt
        timestamp = _dt.utcnow().isoformat()

    if _use_supabase:
        try:
            _supabase.table("conversation_memory").insert({
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "channel_id": str(channel_id),
                "role": role,
                "content": content,
                "timestamp": timestamp,
            }).execute()
            # Trim old entries: keep only the most recent 20 per user+guild+channel
            all_entries = _supabase.table("conversation_memory").select("id").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).eq(
                "channel_id", str(channel_id)
            ).order("id", desc=True).execute()
            if all_entries.data and len(all_entries.data) > 20:
                ids_to_delete = [e["id"] for e in all_entries.data[20:]]
                for eid in ids_to_delete:
                    _supabase.table("conversation_memory").delete().eq("id", eid).execute()
            return
        except Exception as e:
            error_key = "save_conversation_message"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] save_conversation_message error: {e}")
                _supabase_error_logged.add(error_key)
            data = _read_json("data/conversation_memory.json")
            key = f"{guild_id}_{user_id}_{channel_id}"
            if key not in data or not isinstance(data[key], list):
                data[key] = []
            data[key].append({
                "role": role,
                "content": content,
                "timestamp": timestamp,
            })
            if len(data[key]) > 20:
                data[key] = data[key][-20:]
            _write_json("data/conversation_memory.json", data)
    else:
        data = _read_json("data/conversation_memory.json")
        key = f"{guild_id}_{user_id}_{channel_id}"
        if key not in data or not isinstance(data[key], list):
            data[key] = []
        data[key].append({
            "role": role,
            "content": content,
            "timestamp": timestamp,
        })
        if len(data[key]) > 20:
            data[key] = data[key][-20:]
        _write_json("data/conversation_memory.json", data)


def clear_conversation_history(guild_id: int, user_id: int, channel_id: int = 0):
    """Clear conversation history for a user in a guild.
    FIX 6 — If channel_id=0, clears all channels. If >0, clears only that channel."""
    if _use_supabase:
        try:
            query = _supabase.table("conversation_memory").delete().eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id))
            if channel_id:
                query = query.eq("channel_id", str(channel_id))
            query.execute()
        except Exception as e:
            error_key = "clear_conversation_history"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] clear_conversation_history error: {e}")
                _supabase_error_logged.add(error_key)
            data = _read_json("data/conversation_memory.json")
            if channel_id:
                key = f"{guild_id}_{user_id}_{channel_id}"
                if key in data:
                    data[key] = []
            else:
                # Clear all channels for this user+guild
                prefix = f"{guild_id}_{user_id}_"
                for key in list(data.keys()):
                    if key.startswith(prefix):
                        data[key] = []
            _write_json("data/conversation_memory.json", data)
    else:
        data = _read_json("data/conversation_memory.json")
        if channel_id:
            key = f"{guild_id}_{user_id}_{channel_id}"
            if key in data:
                data[key] = []
        else:
            prefix = f"{guild_id}_{user_id}_"
            for key in list(data.keys()):
                if key.startswith(prefix):
                    data[key] = []
        _write_json("data/conversation_memory.json", data)


# ─── PHASE 2B: Per-Server Personality Notes ────────────────────

def get_server_personality(guild_id: int) -> dict:
    """Get the personality note for a guild.
    Returns {"personality_note": str, "set_by": str, "updated_at": str} or {}."""
    if _use_supabase:
        try:
            result = _supabase.table("server_personality").select("*").eq(
                "guild_id", str(guild_id)
            ).execute()
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            error_key = "get_server_personality"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_server_personality error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'server_personality'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/server_personality.json")
            return data.get(str(guild_id), {})
    else:
        data = _read_json("data/server_personality.json")
        return data.get(str(guild_id), {})


def set_server_personality(guild_id: int, note: str, set_by: str,
                            updated_at: str = None):
    """Set or update the personality note for a guild."""
    if updated_at is None:
        from datetime import datetime as _dt
        updated_at = _dt.utcnow().isoformat()

    if _use_supabase:
        try:
            existing = _supabase.table("server_personality").select("guild_id").eq(
                "guild_id", str(guild_id)
            ).execute()
            payload = {
                "personality_note": note,
                "set_by": str(set_by),
                "updated_at": updated_at,
            }
            if existing.data:
                _supabase.table("server_personality").update(payload).eq(
                    "guild_id", str(guild_id)
                ).execute()
            else:
                payload["guild_id"] = str(guild_id)
                _supabase.table("server_personality").insert(payload).execute()
        except Exception as e:
            error_key = "set_server_personality"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_server_personality error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'server_personality'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/server_personality.json")
            data[str(guild_id)] = {
                "personality_note": note,
                "set_by": str(set_by),
                "updated_at": updated_at,
            }
            _write_json("data/server_personality.json", data)
    else:
        data = _read_json("data/server_personality.json")
        data[str(guild_id)] = {
            "personality_note": note,
            "set_by": str(set_by),
            "updated_at": updated_at,
        }
        _write_json("data/server_personality.json", data)


def clear_server_personality(guild_id: int):
    """Clear the personality note for a guild."""
    if _use_supabase:
        try:
            _supabase.table("server_personality").delete().eq(
                "guild_id", str(guild_id)
            ).execute()
        except Exception as e:
            error_key = "clear_server_personality"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] clear_server_personality error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'server_personality'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            # Fall back to JSON silently
            data = _read_json("data/server_personality.json")
            if str(guild_id) in data:
                del data[str(guild_id)]
            _write_json("data/server_personality.json", data)
    else:
        data = _read_json("data/server_personality.json")
        if str(guild_id) in data:
            del data[str(guild_id)]
        _write_json("data/server_personality.json", data)


# ─── User profiles (global per user_id) ────────────────────────

def get_user_profile(user_id: int) -> dict:
    """Get a user's profile data (bio, pronouns, timezone, etc.).
    Stored globally per user_id (not per-guild)."""
    if _use_supabase:
        try:
            result = _supabase.table("user_profiles").select("*").eq(
                "user_id", str(user_id)
            ).execute()
            if result.data:
                row = result.data[0]
                # FIX 2 — return flat columns, not a JSON blob
                return {
                    "bio": row.get("bio", "") or "",
                    "pronouns": row.get("pronouns", "") or "",
                    "timezone": row.get("timezone", "") or "",
                    "updated_at": row.get("updated_at", "") or "",
                }
            return {}
        except Exception as e:
            error_key = "get_user_profile"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_profile error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'user_profiles'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            data = _read_json("data/user_profiles.json")
            return data.get(str(user_id), {})
    else:
        data = _read_json("data/user_profiles.json")
        return data.get(str(user_id), {})


def set_user_profile(user_id: int, data: dict):
    """Save a user's profile data (global per user_id)."""
    if _use_supabase:
        try:
            # FIX 2 — send flat columns, not a JSON blob
            payload = {
                "bio": data.get("bio", ""),
                "pronouns": data.get("pronouns", ""),
                "timezone": data.get("timezone", ""),
                "updated_at": data.get("updated_at", ""),
            }
            existing = _supabase.table("user_profiles").select("user_id").eq(
                "user_id", str(user_id)
            ).execute()
            if existing.data:
                _supabase.table("user_profiles").update(payload).eq(
                    "user_id", str(user_id)
                ).execute()
            else:
                payload["user_id"] = str(user_id)
                _supabase.table("user_profiles").insert(payload).execute()
        except Exception as e:
            error_key = "set_user_profile"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_user_profile error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'user_profiles'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            data_store = _read_json("data/user_profiles.json")
            data_store[str(user_id)] = data
            _write_json("data/user_profiles.json", data_store)
    else:
        data_store = _read_json("data/user_profiles.json")
        data_store[str(user_id)] = data
        _write_json("data/user_profiles.json", data_store)


# ─── Birthdays (per-guild user birthdays) ──────────────────────

def set_birthday(guild_id: int, user_id: int, month: int, day: int):
    """Save or update a user's birthday (month + day only) for a guild."""
    if _use_supabase:
        try:
            existing = _supabase.table("birthdays").select("id").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            payload = {
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "month": month,
                "day": day,
            }
            if existing.data:
                _supabase.table("birthdays").update(
                    {"month": month, "day": day}
                ).eq("guild_id", str(guild_id)).eq(
                    "user_id", str(user_id)
                ).execute()
            else:
                _supabase.table("birthdays").insert(payload).execute()
        except Exception as e:
            error_key = "set_birthday"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_birthday error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'birthdays'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            data = _read_json("data/birthdays.json")
            g = str(guild_id)
            if g not in data or not isinstance(data[g], dict):
                data[g] = {"users": {}}
            data[g].setdefault("users", {})[str(user_id)] = {
                "month": month, "day": day
            }
            _write_json("data/birthdays.json", data)
    else:
        data = _read_json("data/birthdays.json")
        g = str(guild_id)
        if g not in data or not isinstance(data[g], dict):
            data[g] = {"users": {}}
        data[g].setdefault("users", {})[str(user_id)] = {
            "month": month, "day": day
        }
        _write_json("data/birthdays.json", data)


def get_upcoming_birthdays(guild_id: int, limit: int = 5) -> list:
    """Get the next `limit` upcoming birthdays for a guild.
    Returns a list of dicts: {"user_id": str, "month": int, "day": int,
    "days_until": int} sorted ascending by days_until."""
    from datetime import datetime as _dt
    now = _dt.utcnow()
    users = {}
    if _use_supabase:
        try:
            result = _supabase.table("birthdays").select("*").eq(
                "guild_id", str(guild_id)
            ).execute()
            for row in (result.data or []):
                users[row.get("user_id")] = {
                    "month": row.get("month"),
                    "day": row.get("day"),
                }
        except Exception as e:
            error_key = "get_upcoming_birthdays"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_upcoming_birthdays error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'birthdays'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
            gdata = _read_json("data/birthdays.json").get(str(guild_id), {})
            users = gdata.get("users", {}) if isinstance(gdata, dict) else {}
    else:
        gdata = _read_json("data/birthdays.json").get(str(guild_id), {})
        users = gdata.get("users", {}) if isinstance(gdata, dict) else {}

    upcoming = []
    for user_id_str, bday in users.items():
        if not isinstance(bday, dict):
            continue
        try:
            m, d = int(bday["month"]), int(bday["day"])
        except (KeyError, ValueError, TypeError):
            continue
        try:
            next_bday = _dt(now.year, m, d)
        except ValueError:
            continue
        if next_bday < now:
            try:
                next_bday = _dt(now.year + 1, m, d)
            except ValueError:
                continue
        days_until = (next_bday - now).days
        upcoming.append({
            "user_id": str(user_id_str),
            "month": m,
            "day": d,
            "days_until": days_until,
        })
    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming[:limit]


def get_birthdays_today(month: int, day: int) -> list:
    """Get every (guild_id, user_id) whose birthday matches today's
    month/day across ALL guilds. Returns a list of dicts:
    {"guild_id": str, "user_id": str}."""
    results = []
    if _use_supabase:
        try:
            result = _supabase.table("birthdays").select(
                "guild_id,user_id"
            ).eq("month", month).eq("day", day).execute()
            for row in (result.data or []):
                results.append({
                    "guild_id": row.get("guild_id"),
                    "user_id": row.get("user_id"),
                })
            return results
        except Exception as e:
            error_key = "get_birthdays_today"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_birthdays_today error: {e}")
                logger.warning(
                    "[DB] Supabase permission issue for table 'birthdays'. "
                    "Falling back to JSON."
                )
                _supabase_error_logged.add(error_key)
    # JSON fallback (and Supabase-fail path)
    data = _read_json("data/birthdays.json")
    for guild_id_str, gdata in data.items():
        if not isinstance(gdata, dict):
            continue
        users = gdata.get("users", {})
        if not isinstance(users, dict):
            continue
        for user_id_str, bday in users.items():
            if not isinstance(bday, dict):
                continue
            try:
                if int(bday.get("month", 0)) == month and int(
                    bday.get("day", 0)
                ) == day:
                    results.append({
                        "guild_id": str(guild_id_str),
                        "user_id": str(user_id_str),
                    })
            except (ValueError, TypeError):
                continue
    return results


# ─── PHASE 3D5: Tempbans ────────────────────────────────────────

def add_tempban(guild_id: int, user_id: int, unban_time: float, reason: str = ""):
    """Record a tempban that should be lifted at unban_time (epoch seconds)."""
    if _use_supabase:
        try:
            _supabase.table("tempbans").insert({
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "unban_time": unban_time,
                "reason": reason,
            }).execute()
            return
        except Exception as e:
            error_key = "add_tempban"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] add_tempban error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/tempbans.json")
    if "pending" not in data:
        data["pending"] = []
    data["pending"].append({
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "unban_time": unban_time,
        "reason": reason,
    })
    _write_json("data/tempbans.json", data)


def get_tempbans_due(before_time: float) -> list:
    """Get all tempbans where unban_time <= before_time."""
    results = []
    if _use_supabase:
        try:
            result = _supabase.table("tempbans").select("*").lt(
                "unban_time", before_time
            ).execute()
            return result.data or []
        except Exception as e:
            error_key = "get_tempbans_due"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_tempbans_due error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/tempbans.json")
    for tb in data.get("pending", []):
        try:
            if float(tb.get("unban_time", 0)) <= before_time:
                results.append(tb)
        except (ValueError, TypeError):
            continue
    return results


def remove_tempban(guild_id: int, user_id: int):
    """Remove a tempban after it has been lifted."""
    if _use_supabase:
        try:
            _supabase.table("tempbans").delete().eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            return
        except Exception as e:
            error_key = "remove_tempban"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] remove_tempban error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/tempbans.json")
    data["pending"] = [
        tb for tb in data.get("pending", [])
        if not (tb.get("guild_id") == str(guild_id)
                and tb.get("user_id") == str(user_id))
    ]
    _write_json("data/tempbans.json", data)
