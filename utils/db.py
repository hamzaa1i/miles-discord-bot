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

CREATE TABLE IF NOT EXISTS welcome_settings (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  message TEXT,
  enabled BOOLEAN DEFAULT TRUE,
  goodbye_channel_id TEXT,
  goodbye_message TEXT,
  goodbye_enabled BOOLEAN DEFAULT TRUE,
  autorole_id TEXT,
  welcome_reward INT DEFAULT 0,
  welcomer_reward INT DEFAULT 0,
  embed_mode TEXT DEFAULT 'embed',
  dm_message TEXT,
  welcome_image TEXT,
  welcome_color TEXT DEFAULT '#FFC0CB'
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
--
-- ALTER TABLE welcome_settings ADD COLUMN IF NOT EXISTS dm_message TEXT;
-- ALTER TABLE welcome_settings ADD COLUMN IF NOT EXISTS embed_mode TEXT DEFAULT 'embed';
-- ALTER TABLE welcome_settings ADD COLUMN IF NOT EXISTS welcome_image TEXT;
-- ALTER TABLE welcome_settings ADD COLUMN IF NOT EXISTS welcome_color TEXT DEFAULT '#FFC0CB';
--
-- CREATE TABLE IF NOT EXISTS user_levels (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   xp INT DEFAULT 0,
--   level INT DEFAULT 0,
--   last_msg_time FLOAT DEFAULT 0,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.user_levels TO anon;
-- ALTER TABLE public.user_levels DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS level_rewards (
--   guild_id TEXT NOT NULL,
--   level INT NOT NULL,
--   role_id TEXT NOT NULL,
--   PRIMARY KEY (guild_id, level)
-- );
-- GRANT ALL ON public.level_rewards TO anon;
-- ALTER TABLE public.level_rewards DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS self_role_panels (
--   message_id TEXT PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   channel_id TEXT NOT NULL,
--   category TEXT NOT NULL,
--   roles JSONB
-- );
-- GRANT ALL ON public.self_role_panels TO anon;
-- ALTER TABLE public.self_role_panels DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS invite_tracking (
--   guild_id TEXT NOT NULL,
--   inviter_id TEXT NOT NULL,
--   invites INT DEFAULT 0,
--   joins INT DEFAULT 0,
--   leaves INT DEFAULT 0,
--   PRIMARY KEY (guild_id, inviter_id)
-- );
-- GRANT ALL ON public.invite_tracking TO anon;
-- ALTER TABLE public.invite_tracking DISABLE ROW LEVEL SECURITY;
--
-- FIX 4 — leveling_settings table (was missing, causing 404 spam).
-- Run this in Supabase SQL editor if you see "leveling_settings does not exist":
--
-- CREATE TABLE IF NOT EXISTS leveling_settings (
--   guild_id TEXT PRIMARY KEY,
--   enabled BOOLEAN DEFAULT TRUE,
--   channel_id TEXT,
--   rate FLOAT DEFAULT 1.0,
--   rewards JSONB DEFAULT '{}'::jsonb,
--   level_up_message TEXT DEFAULT '🎉 {user} just reached level {level}! ✦',
--   level_up_channel_mode TEXT DEFAULT 'active',
--   updated_at TEXT
-- );
-- GRANT ALL ON public.leveling_settings TO anon;
-- ALTER TABLE public.leveling_settings DISABLE ROW LEVEL SECURITY;
--
-- FIX 2 — existing leveling_settings tables only need the two new columns:
--
-- ALTER TABLE public.leveling_settings
--   ADD COLUMN IF NOT EXISTS level_up_message TEXT DEFAULT '🎉 {user} just reached level {level}! ✦';
-- ALTER TABLE public.leveling_settings
--   ADD COLUMN IF NOT EXISTS level_up_channel_mode TEXT DEFAULT 'active';
--
-- PHASE 4 — new feature tables (AI memory, AI automod, starboard,
-- giveaways, custom commands, proactive presence, onboarding).
-- Run these in the Supabase SQL editor; every function below also has a
-- JSON-file fallback so the bot works even before the tables exist:
--
-- CREATE TABLE IF NOT EXISTS user_memory (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   facts JSONB DEFAULT '[]'::jsonb,
--   updated_at TEXT,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.user_memory TO anon;
-- ALTER TABLE public.user_memory DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS ai_automod_settings (
--   guild_id TEXT PRIMARY KEY,
--   enabled BOOLEAN DEFAULT FALSE,
--   alert_channel_id TEXT,
--   timeout_minutes INT DEFAULT 10,
--   min_severity INT DEFAULT 3
-- );
-- GRANT ALL ON public.ai_automod_settings TO anon;
-- ALTER TABLE public.ai_automod_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS starboard_settings (
--   guild_id TEXT PRIMARY KEY,
--   enabled BOOLEAN DEFAULT FALSE,
--   channel_id TEXT,
--   emoji TEXT DEFAULT '⭐',
--   threshold INT DEFAULT 5
-- );
-- GRANT ALL ON public.starboard_settings TO anon;
-- ALTER TABLE public.starboard_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS starboard_posts (
--   message_id BIGINT PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   channel_id TEXT,
--   starboard_message_id BIGINT,
--   author_id TEXT
-- );
-- GRANT ALL ON public.starboard_posts TO anon;
-- ALTER TABLE public.starboard_posts DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS giveaways (
--   id TEXT PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   channel_id TEXT,
--   message_id BIGINT,
--   host_id TEXT,
--   host_name TEXT,
--   prize TEXT,
--   ends_at FLOAT,
--   winners_count INT DEFAULT 1,
--   required_role_id TEXT,
--   min_account_days INT DEFAULT 0,
--   min_level INT DEFAULT 0,
--   ended BOOLEAN DEFAULT FALSE,
--   entries JSONB DEFAULT '[]'::jsonb,
--   winner_ids JSONB DEFAULT '[]'::jsonb,
--   created_at TEXT
-- );
-- GRANT ALL ON public.giveaways TO anon;
-- ALTER TABLE public.giveaways DISABLE ROW LEVEL SECURITY;
-- (if the table already exists without host_name, run:
--  ALTER TABLE public.giveaways ADD COLUMN IF NOT EXISTS host_name TEXT;)
-- The complete, ready-to-run migration lives in scripts/supabase_migration.sql.
--
-- CREATE TABLE IF NOT EXISTS custom_commands (
--   guild_id TEXT PRIMARY KEY,
--   commands JSONB DEFAULT '[]'::jsonb
-- );
-- GRANT ALL ON public.custom_commands TO anon;
-- ALTER TABLE public.custom_commands DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS proactive_settings (
--   guild_id TEXT PRIMARY KEY,
--   enabled BOOLEAN DEFAULT FALSE,
--   channel_ids JSONB DEFAULT '[]'::jsonb
-- );
-- GRANT ALL ON public.proactive_settings TO anon;
-- ALTER TABLE public.proactive_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS onboarding_settings (
--   guild_id TEXT PRIMARY KEY,
--   enabled BOOLEAN DEFAULT FALSE,
--   welcome_text TEXT,
--   roles JSONB DEFAULT '[]'::jsonb
-- );
-- GRANT ALL ON public.onboarding_settings TO anon;
-- ALTER TABLE public.onboarding_settings DISABLE ROW LEVEL SECURITY;
--
-- PHASE 1 / PART 3 — command usage analytics (batched by utils/usage_logger.py):
--
-- CREATE TABLE IF NOT EXISTS command_usage (
--     id BIGSERIAL PRIMARY KEY,
--     guild_id TEXT NOT NULL,
--     user_id TEXT NOT NULL,
--     command_name TEXT NOT NULL,
--     timestamp TIMESTAMPTZ DEFAULT NOW()
-- );
-- GRANT ALL ON public.command_usage TO anon;
-- ALTER TABLE public.command_usage DISABLE ROW LEVEL SECURITY;
--
-- PHASE 1 / PART 5 — daily fortune history (/fortune in cogs/fun_extras.py):
--
-- CREATE TABLE IF NOT EXISTS fortune_history (
--     user_id TEXT PRIMARY KEY,
--     last_fortune_date TEXT,
--     fortune_text TEXT
-- );
-- GRANT ALL ON public.fortune_history TO anon;
-- ALTER TABLE public.fortune_history DISABLE ROW LEVEL SECURITY;
--
-- PHASE 2 (ENGAGEMENT CORE) — daily rewards, QOTD, anniversaries,
-- recurring reminders. Run in the Supabase SQL editor:
--
-- ALTER TABLE reminders ADD COLUMN IF NOT EXISTS repeat_interval TEXT DEFAULT 'none';
--
-- CREATE TABLE IF NOT EXISTS daily_streaks (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   streak INT DEFAULT 0,
--   highest_streak INT DEFAULT 0,
--   last_claim_date TEXT,
--   total_claimed INT DEFAULT 0,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.daily_streaks TO anon;
-- ALTER TABLE public.daily_streaks DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS qotd_settings (
--   guild_id TEXT PRIMARY KEY,
--   channel_id TEXT,
--   enabled BOOLEAN DEFAULT FALSE,
--   post_hour_utc INT DEFAULT 14,
--   auto_thread BOOLEAN DEFAULT TRUE,
--   last_post_date TEXT
-- );
-- GRANT ALL ON public.qotd_settings TO anon;
-- ALTER TABLE public.qotd_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS qotd_queue (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   question TEXT NOT NULL,
--   added_by TEXT,
--   used BOOLEAN DEFAULT FALSE,
--   added_at TEXT
-- );
-- GRANT ALL ON public.qotd_queue TO anon;
-- ALTER TABLE public.qotd_queue DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS anniversary_settings (
--   guild_id TEXT PRIMARY KEY,
--   channel_id TEXT,
--   enabled BOOLEAN DEFAULT FALSE,
--   last_run_date TEXT
-- );
-- GRANT ALL ON public.anniversary_settings TO anon;
-- ALTER TABLE public.anniversary_settings DISABLE ROW LEVEL SECURITY;
"""
import asyncio
import functools
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from utils.cache import cache

logger = logging.getLogger('cyn.db')

# Try to use Supabase if configured, fall back to JSON files
_supabase = None
_use_supabase = False

# FIX 3 — Track which Supabase errors have been logged so we don't spam
# the logs every 30 seconds (e.g. reminder background task polling).
# Each error is logged ONCE, then we silently fall back to JSON.
_supabase_error_logged = set()

# FIX 3 — Track which tables are MISSING from Supabase (returned 404 /
# PGRST205 / "does not exist"). Once a table is marked missing, we skip
# the Supabase query entirely and go straight to JSON — no more repeated
# 404 errors on every single message.
_supabase_table_missing = set()


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


def get_supabase():
    """PHASE 1 / PART 3 — Return the raw Supabase client, or None when
    Supabase is not configured/connected. Used by utils/usage_logger.py
    for batched command_usage inserts (and safe to call anywhere)."""
    return _supabase if _use_supabase else None


# ─── PART 2.1 — standardized graceful degradation ───────────────
#
# with_fallback wraps the async DB wrappers below. The sync functions
# already fall back to JSON internally for Supabase-side errors; this
# decorator adds the layer that was missing:
#   * a global _supabase_degraded flag (surfaced in /botinfo as
#     "Supabase - degraded" and cleared on the first success),
#   * classification of the error (outage vs schema vs unexpected),
#   * a last-resort JSON fallback for anything that still escapes
#     (e.g. the JSON write itself failing inside the sync function, or
#     the thread-pool call blowing up).

_supabase_degraded = False


def supabase_degraded() -> bool:
    """PART 8 — True while Supabase is being treated as down (shown in
    /botinfo's Storage section). Resets to False on the next success."""
    return _supabase_degraded


def with_fallback(table_name: str, fallback_fn=None):
    """Decorate an async db wrapper with standardized degradation.

    * timeout / 5xx / connection errors  → mark degraded (once), then
      call fallback_fn if provided, else return None.
    * schema errors ("column", "does not exist") → log once, return None
      (no fallback — writing to a missing table makes it worse).
    * any other error → log, call fallback_fn if provided, else None.
    * success → clear the degraded flag ("Supabase recovered").
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            global _supabase_degraded
            try:
                result = await func(*args, **kwargs)
                if _supabase_degraded:
                    logger.info("[DB] Supabase recovered")
                    _supabase_degraded = False
                return result
            except Exception as e:
                error_str = str(e).lower()
                if any(x in error_str for x in ["timeout", "503", "502", "504", "connection"]):
                    if not _supabase_degraded:
                        logger.warning(
                            f"[DB] Supabase degraded ({e}), falling back to JSON for {table_name}"
                        )
                        _supabase_degraded = True
                    if fallback_fn:
                        if asyncio.iscoroutinefunction(fallback_fn):
                            return await fallback_fn(*args, **kwargs)
                        return fallback_fn(*args, **kwargs)
                    return None
                elif "column" in error_str or "does not exist" in error_str:
                    logger.error(f"[DB] Schema error on {table_name}: {e}")
                    return None
                else:
                    logger.error(f"[DB] Unexpected error on {table_name}: {e}")
                    if fallback_fn:
                        if asyncio.iscoroutinefunction(fallback_fn):
                            return await fallback_fn(*args, **kwargs)
                        return fallback_fn(*args, **kwargs)
                    return None
        return wrapper
    return decorator


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

# FIX (schema mismatch) — Known column sets for Supabase tables that
# have a fixed schema. When set_guild_setting sends a dict to Supabase,
# it first filters the dict to only include keys that exist as columns
# in the table. This prevents "Could not find the column" errors that
# cause silent fallback to JSON + stale reads.
#
# If a table is not listed here, the full dict is sent as-is (backward
# compatible with tables that accept arbitrary columns via JSONB).
_TABLE_COLUMNS = {
    "welcome_settings": {
        "guild_id", "channel_id", "message", "enabled",
        "goodbye_channel_id", "goodbye_message", "goodbye_enabled",
        "autorole_id", "welcome_reward", "welcomer_reward",
        "embed_mode", "dm_message", "welcome_image", "welcome_color",
        "welcome_title", "welcome_thumbnail", "welcome_footer",
    },
    "log_settings": {
        "guild_id", "channel_id", "enabled",
        "message_delete", "message_edit",
        "member_join", "member_leave",
        "member_ban", "member_unban",
        "role_change", "nickname_change",
        "voice_join", "voice_leave",
    },
    "mod_settings": {
        "guild_id", "log_channel_id", "admin_role_id",
        "max_warns_before_ban",
        "warn_threshold_count", "warn_threshold_action",
        "antilink_channels", "antispam_enabled",
    },
    "prefix_settings": {
        "guild_id", "prefix",
    },
    "server_settings": {
        "guild_id", "autorole_id", "custom_status", "custom_status_type",
    },
    "confess_settings": {
        "guild_id", "channel_id", "count",
    },
    "server_rules": {
        "guild_id", "rules", "agree_role_id", "announcement_channel_id",
    },
    "birthday_settings": {
        "guild_id", "channel_id",
    },
    "leveling_settings": {
        "guild_id", "enabled", "channel_id", "rate", "rewards",
        # FIX 2 — customizable level-up messages
        "level_up_message", "level_up_channel_mode",
    },
    "bump_reminder_state": {
        "guild_id", "channel_id", "last_bump_message_id", "last_bump_at",
    },
    "self_role_panels": {
        "guild_id", "panels",
    },
    # PHASE 4 — new feature settings tables
    "ai_automod_settings": {
        "guild_id", "enabled", "alert_channel_id", "timeout_minutes",
        "min_severity",
    },
    "starboard_settings": {
        "guild_id", "enabled", "channel_id", "emoji", "threshold",
    },
    "custom_commands": {
        "guild_id", "commands",
    },
    "proactive_settings": {
        "guild_id", "enabled", "channel_ids",
    },
    "onboarding_settings": {
        "guild_id", "enabled", "welcome_text", "roles",
    },
    # PHASE 1 / PART 3 — command usage analytics (batched inserts)
    "command_usage": {"guild_id", "user_id", "command_name", "timestamp"},
    # PHASE 1 / PART 5 — daily fortune history (/fortune)
    "fortune_history": {"user_id", "last_fortune_date", "fortune_text"},
    # PHASE 2 (ENGAGEMENT CORE) — recurring reminders: the repeat_interval
    # column must survive column sanitization so /remind create can store
    # 'none' / 'daily' / 'weekly' / 'monthly'.
    "reminders": {
        "user_id", "text", "end_time", "channel_id", "fired",
        "repeat_interval",
    },
    # PHASE 2 (ENGAGEMENT CORE) — daily login streaks (/daily)
    "daily_streaks": {
        "guild_id", "user_id", "streak", "highest_streak",
        "last_claim_date", "total_claimed",
    },
    # PHASE 2 (ENGAGEMENT CORE) — question of the day (/qotd)
    "qotd_settings": {
        "guild_id", "channel_id", "enabled", "post_hour_utc",
        "auto_thread", "last_post_date",
    },
    "qotd_queue": {
        "id", "guild_id", "question", "added_by", "used", "added_at",
    },
    # PHASE 2 (ENGAGEMENT CORE) — member anniversaries (/anniversary)
    "anniversary_settings": {
        "guild_id", "channel_id", "enabled", "last_run_date",
    },
}


def _sanitize_columns(table: str, settings: dict) -> dict:
    """Filter a settings dict to only include keys that exist as columns
    in the specified Supabase table.

    If the table is not in _TABLE_COLUMNS, return the dict unchanged
    (backward compatible with tables that use JSONB or accept arbitrary
    columns).
    """
    if not isinstance(settings, dict):
        return {}
    valid_cols = _TABLE_COLUMNS.get(table)
    if valid_cols is None:
        # Unknown table — send as-is
        return settings
    return {k: v for k, v in settings.items() if k in valid_cols}


# PHASE 1 / PART 1 — per-table cache TTLs for get_guild_setting.
# Everything defaults to 60s; log_settings reads happen on nearly every
# message-delete/edit so it gets the longer 120s TTL from the spec.
_GUILD_SETTING_TTLS = {
    "log_settings": 120,
}


def get_guild_setting(guild_id: int, table: str) -> dict:
    """Get settings for a guild from a specific table/file.

    FIX 3 — If a table has previously returned a "does not exist" / 404 /
    PGRST205 error, we skip the Supabase query entirely and go straight
    to the JSON fallback. This stops the repeated `GET /rest/v1/<table>
    404 Not Found` spam that was polluting the logs on every message.

    PHASE 1 / PART 1 — results are served from the shared TTL cache
    (60s, 120s for log_settings). set_guild_setting() invalidates the
    entry on every write, so config changes show up immediately. The
    cached dict is copied on read AND on store so cogs that mutate the
    returned dict can never corrupt the cache.
    """
    key = f"gs:{table}:{guild_id}"
    cached = cache.get_sync(key)
    if cached is not None:
        return dict(cached) if isinstance(cached, dict) else cached
    result = _get_guild_setting_raw(guild_id, table)
    if isinstance(result, dict):
        cache.set_sync(
            key, dict(result), ttl=_GUILD_SETTING_TTLS.get(table, 60)
        )
    return result


def _get_guild_setting_raw(guild_id: int, table: str) -> dict:
    if not _use_supabase:
        data = _read_json(f"data/{table}.json")
        return data.get(str(guild_id), {})

    # FIX 3 — Short-circuit: if we already know this table doesn't exist
    # in Supabase, skip the query entirely.
    if table in _supabase_table_missing:
        data = _read_json(f"data/{table}.json")
        return data.get(str(guild_id), {})

    try:
        result = _supabase.table(table).select("*").eq(
            "guild_id", str(guild_id)
        ).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception as e:
        error_str = str(e)
        error_key = f"get_guild_setting_{table}"

        # FIX 3 — Table missing? Mark it permanently so we skip Supabase
        # entirely on all future reads for this table.
        if "PGRST205" in error_str or "does not exist" in error_str or "404" in error_str:
            _supabase_table_missing.add(table)
            if error_key not in _supabase_error_logged:
                logger.warning(
                    f"[DB] Table '{table}' does not exist in Supabase. "
                    f"Using JSON fallback (this message won't repeat)."
                )
                _supabase_error_logged.add(error_key)
        else:
            # Only log other errors once per table
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


def set_guild_setting(guild_id: int, table: str, settings: dict):
    """Save settings for a guild.

    FIX 3 — If the table is known-missing from Supabase, skip straight
    to JSON to avoid repeated 404 errors on writes too.

    FIX (schema mismatch) — Some tables (notably welcome_settings) have
    a fixed column set in Supabase, but the code's config dict may
    contain extra keys that don't exist as columns. When the Supabase
    insert/update fails with a "Could not find the column" error, the
    write falls back to JSON — BUT get_guild_setting reads from Supabase
    first, so it returns stale/empty data and the config appears to not
    persist.

    Fix: Before sending the payload to Supabase, sanitize the dict so
    only known columns for that table are included. This prevents the
    column-mismatch error entirely.

    PHASE 1 / PART 1 — invalidates the cached read for this guild+table
    so the next get_guild_setting sees the new value right away.
    """
    _set_guild_setting_raw(guild_id, table, settings)
    cache.invalidate_sync(f"gs:{table}:{guild_id}")


def _set_guild_setting_raw(guild_id: int, table: str, settings: dict):
    if not _use_supabase:
        data = _read_json(f"data/{table}.json")
        data[str(guild_id)] = settings
        _write_json(f"data/{table}.json", data)
        return

    # FIX 3 — Short-circuit for known-missing tables
    if table in _supabase_table_missing:
        data = _read_json(f"data/{table}.json")
        data[str(guild_id)] = settings
        _write_json(f"data/{table}.json", data)
        return

    # FIX (schema mismatch) — Sanitize the settings dict so only valid
    # columns are sent to Supabase. This prevents "Could not find the
    # column" errors that cause silent fallback to JSON + stale reads.
    sanitized = _sanitize_columns(table, settings)

    try:
        existing = _supabase.table(table).select("guild_id").eq(
            "guild_id", str(guild_id)
        ).execute()
        if existing.data:
            _supabase.table(table).update(sanitized).eq(
                "guild_id", str(guild_id)
            ).execute()
        else:
            _supabase.table(table).insert({
                "guild_id": str(guild_id), **sanitized
            }).execute()
    except Exception as e:
        error_str = str(e)
        error_key = f"set_guild_setting_{table}"

        # FIX 3 — Table missing? Mark it permanently.
        if "PGRST205" in error_str or "does not exist" in error_str or "404" in error_str:
            _supabase_table_missing.add(table)
            if error_key not in _supabase_error_logged:
                logger.warning(
                    f"[DB] Table '{table}' does not exist in Supabase. "
                    f"Using JSON fallback for writes (this message won't repeat)."
                )
                _supabase_error_logged.add(error_key)
        else:
            # Log the exact failure (not just once — this is a real error
            # the user needs to see so they can fix the schema).
            logger.error(f"[DB] set_guild_setting ({table}) error: {e}")
            if error_key not in _supabase_error_logged:
                logger.warning(
                    f"[DB] Supabase write failed for table '{table}'. "
                    "Falling back to JSON. If this persists, the table "
                    "schema may be missing columns — see the SQL comment "
                    "at the top of utils/db.py."
                )
                _supabase_error_logged.add(error_key)

        # Fall back to JSON silently
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
    """Add a warning and return the case ID.

    FIX 1.1 ("case #None") — the Supabase `warnings.case_id` column is a
    plain nullable INT (NOT an identity/serial column), so an insert
    without case_id comes back with case_id=null and the old code did
    `result.data[0].get("case_id", 0)` → None (key present, value null).
    The AI warn executor then printed "case #None".

    Fix: generate the next per-guild case number CLIENT-SIDE (max + 1,
    exactly like the JSON fallback), include it in the insert payload so
    the stored row carries a real case number, and return it."""
    if _use_supabase:
        try:
            # FIX 1.1 — next per-guild case number, computed client-side.
            case_id = None
            try:
                top = _supabase.table("warnings").select("case_id").eq(
                    "guild_id", str(guild_id)
                ).order("case_id", desc=True).limit(1).execute()
                if top.data:
                    case_id = int(top.data[0].get("case_id") or 0) + 1
                else:
                    case_id = 1
            except Exception:
                case_id = None  # fall back to whatever the DB returns
            warning["guild_id"] = str(guild_id)
            warning["user_id"] = str(user_id)
            if case_id:
                warning["case_id"] = case_id
            result = _supabase.table("warnings").insert(warning).execute()
            if result.data and result.data[0].get("case_id"):
                return int(result.data[0]["case_id"])
            return case_id or 0
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


def snooze_reminder(user_id: int, reminder_id: str, new_end_time: float) -> bool:
    """PHASE 2 (ENGAGEMENT CORE) — push a recurring reminder's next fire
    time forward instead of deleting it.

    Called by the reminder check loop in cogs/ai_chat.py when a reminder
    with repeat_interval = daily/weekly/monthly fires: end_time is moved
    to the next occurrence (the caller computes it) and the row stays
    fired=False so it fires again. Returns True when the row was updated.

    Supabase note: the loop passes the row's serial id as a string; the
    REST filter coerces it against the BIGINT column (same as
    remove_reminder)."""
    if _use_supabase:
        try:
            _supabase.table("reminders").update(
                {"end_time": float(new_end_time), "fired": False}
            ).eq("id", reminder_id).execute()
            return True
        except Exception as e:
            error_key = "snooze_reminder"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] snooze_reminder error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/reminders.json")
    u = str(user_id)
    reminders = data.get(u) if isinstance(data.get(u), list) else None
    if reminders is None:
        return False
    for r in reminders:
        if isinstance(r, dict) and str(r.get("id")) == str(reminder_id):
            r["end_time"] = float(new_end_time)
            r["fired"] = False
            _write_json("data/reminders.json", data)
            return True
    return False


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
                # P1 — single bulk delete instead of the old N+1 loop (one
                # REST call per row). Same effect, one round-trip.
                _supabase.table("conversation_memory").delete().in_(
                    "id", ids_to_delete
                ).execute()
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
    Returns {"personality_note": str, "set_by": str, "updated_at": str} or {}.

    PHASE 1 / PART 1 — cached under pers:{guild_id} for 300s (the note
    rarely changes). set/clear_server_personality invalidate on write."""
    key = f"pers:{guild_id}"
    cached = cache.get_sync(key)
    if cached is not None:
        return dict(cached) if isinstance(cached, dict) else cached
    result = _get_server_personality_raw(guild_id)
    if isinstance(result, dict):
        cache.set_sync(key, dict(result), ttl=300)
    return result


def _get_server_personality_raw(guild_id: int) -> dict:
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
    # PHASE 1 / PART 1 — the cached note is stale now
    cache.invalidate_sync(f"pers:{guild_id}")


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
    # PHASE 1 / PART 1 — drop the cached note too
    cache.invalidate_sync(f"pers:{guild_id}")


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


# ─── PHASE 4: AI user memory facts ─────────────────────────────

def get_user_facts(guild_id: int, user_id: int) -> list:
    """Return the durable facts remembered about a user in a guild.

    PHASE 1 / PART 1 — cached under facts:{guild_id}:{user_id} for 300s.
    add_user_fact / clear_user_facts invalidate on write."""
    key = f"facts:{guild_id}:{user_id}"
    cached = cache.get_sync(key)
    if cached is not None:
        return list(cached) if isinstance(cached, list) else cached
    result = _get_user_facts_raw(guild_id, user_id)
    if isinstance(result, list):
        cache.set_sync(key, list(result), ttl=300)
    return result


def _get_user_facts_raw(guild_id: int, user_id: int) -> list:
    if _use_supabase:
        try:
            result = _supabase.table("user_memory").select("facts").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            if result.data:
                facts = result.data[0].get("facts")
                return facts if isinstance(facts, list) else []
            return []
        except Exception as e:
            error_key = "get_user_facts"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_facts error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/user_memory.json")
    entry = data.get(f"{guild_id}_{user_id}", {})
    facts = entry.get("facts", [])
    return facts if isinstance(facts, list) else []


def add_user_fact(guild_id: int, user_id: int, fact: str,
                  max_facts: int = 10) -> bool:
    """Add a durable fact about a user (deduped, capped at max_facts).

    Returns True if the fact was added, False if it was a duplicate.
    When over the cap, the OLDEST fact is dropped."""
    fact = str(fact).strip()[:300]
    if not fact:
        return False
    facts = [f for f in get_user_facts(guild_id, user_id) if isinstance(f, str)]
    # dedupe: exact match or one containing the other
    for existing in facts:
        if fact.lower() == existing.lower() or fact.lower() in existing.lower() \
                or existing.lower() in fact.lower():
            return False
    facts.append(fact)
    if len(facts) > max_facts:
        facts = facts[-max_facts:]
    from datetime import datetime as _dt
    payload = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "facts": facts,
        "updated_at": _dt.utcnow().isoformat(),
    }
    if _use_supabase:
        try:
            _supabase.table("user_memory").upsert(payload).execute()
            # PHASE 1 / PART 1 — facts changed; drop the cached list
            cache.invalidate_sync(f"facts:{guild_id}:{user_id}")
            return True
        except Exception as e:
            error_key = "add_user_fact"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] add_user_fact error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/user_memory.json")
    data[f"{guild_id}_{user_id}"] = payload
    _write_json("data/user_memory.json", data)
    # PHASE 1 / PART 1 — facts changed; drop the cached list
    cache.invalidate_sync(f"facts:{guild_id}:{user_id}")
    return True


def clear_user_facts(guild_id: int, user_id: int) -> int:
    """Delete all facts for a user. Returns how many were removed."""
    facts = get_user_facts(guild_id, user_id)
    if not facts:
        return 0
    if _use_supabase:
        try:
            _supabase.table("user_memory").delete().eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            # PHASE 1 / PART 1 — facts wiped; drop the cached list
            cache.invalidate_sync(f"facts:{guild_id}:{user_id}")
            return len(facts)
        except Exception as e:
            error_key = "clear_user_facts"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] clear_user_facts error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/user_memory.json")
    data.pop(f"{guild_id}_{user_id}", None)
    _write_json("data/user_memory.json", data)
    # PHASE 1 / PART 1 — facts wiped; drop the cached list
    cache.invalidate_sync(f"facts:{guild_id}:{user_id}")
    return len(facts)


# ─── PHASE 4: starboard posts ──────────────────────────────────

def get_starboard_post(guild_id: int, message_id: int) -> dict:
    """Return the starboard record for a source message, or {}."""
    if _use_supabase:
        try:
            result = _supabase.table("starboard_posts").select("*").eq(
                "guild_id", str(guild_id)
            ).eq("message_id", int(message_id)).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            error_key = "get_starboard_post"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_starboard_post error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/starboard_posts.json")
    return data.get(str(message_id), {})


def save_starboard_post(guild_id: int, message_id: int, channel_id: int,
                        starboard_message_id: int, author_id: int):
    """Record that a message has been reposted to the starboard."""
    payload = {
        "guild_id": str(guild_id),
        "message_id": int(message_id),
        "channel_id": str(channel_id),
        "starboard_message_id": int(starboard_message_id),
        "author_id": str(author_id),
    }
    if _use_supabase:
        try:
            _supabase.table("starboard_posts").upsert(payload).execute()
            return
        except Exception as e:
            error_key = "save_starboard_post"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] save_starboard_post error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/starboard_posts.json")
    data[str(message_id)] = payload
    _write_json("data/starboard_posts.json", data)


# ─── PHASE 4: giveaways ─────────────────────────────────────────

# FIX 4 — canonical column set for the giveaways table. save_giveaway()
# upserts whatever the cog puts in the dict; if the Supabase table was
# created from an older schema (notably WITHOUT host_name), the extra key
# made the upsert fail on EVERY write — writes silently fell back to JSON
# while reads still hit Supabase first and found nothing. That split-brain
# is exactly what made /giveaway end report "no giveaway with that id"
# for giveaways that /giveaway start had just created. Only these columns
# are ever sent; host_name is retried without on schema drift.
_GIVEAWAY_COLUMNS = (
    "id", "guild_id", "channel_id", "message_id", "host_id", "host_name",
    "prize", "ends_at", "winners_count", "required_role_id",
    "min_account_days", "min_level", "ended", "entries", "winner_ids",
    "created_at",
)


def _save_giveaway_json(giveaway: dict):
    data = _read_json("data/giveaways.json")
    data[str(giveaway.get("id"))] = giveaway
    _write_json("data/giveaways.json", data)


def save_giveaway(giveaway: dict):
    """Upsert a giveaway row by its id (FIX 4 — schema-drift tolerant).

    1. Send only canonical _GIVEAWAY_COLUMNS to Supabase.
    2. If that fails (e.g. the table predates the host_name column), retry
       once WITHOUT host_name instead of losing the row.
    3. Only if both attempts fail do we fall back to the JSON file.
    Reads (get_giveaway / get_active_giveaways) heal from JSON when Supabase
    has no row, so a fallback write is still visible to every reader.
    """
    payload = {k: giveaway[k] for k in _GIVEAWAY_COLUMNS if k in giveaway}
    if _use_supabase and "giveaways" not in _supabase_table_missing:
        try:
            _supabase.table("giveaways").upsert(payload).execute()
            return
        except Exception as e:
            # Retry without optional columns — the deployed table may have
            # been created before host_name existed.
            try:
                minimal = {k: v for k, v in payload.items() if k != "host_name"}
                _supabase.table("giveaways").upsert(minimal).execute()
                logger.warning(
                    "[DB] save_giveaway: upserted without host_name "
                    "(column missing?) — run the migration SQL"
                )
                return
            except Exception as e2:
                e = e2
            error_str = str(e)
            if ("PGRST205" in error_str or "does not exist" in error_str
                    or "404" in error_str):
                _supabase_table_missing.add("giveaways")
            error_key = "save_giveaway"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] save_giveaway error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback (also the only path when the table is known-missing)
    _save_giveaway_json(giveaway)


def get_giveaway(giveaway_id: str) -> dict:
    """Return one giveaway by id, or {} (FIX 4 — JSON-healed).

    If Supabase has no row for the id, the JSON fallback is checked too —
    a write may have gone there after an upsert failure — before giving up.
    """
    if _use_supabase and "giveaways" not in _supabase_table_missing:
        try:
            result = _supabase.table("giveaways").select("*").eq(
                "id", str(giveaway_id)
            ).execute()
            if result.data:
                return result.data[0]
            # FIX 4 — not in Supabase: heal from JSON before returning {}
            data = _read_json("data/giveaways.json")
            gw = data.get(str(giveaway_id), {})
            return gw if isinstance(gw, dict) else {}
        except Exception as e:
            error_str = str(e)
            if ("PGRST205" in error_str or "does not exist" in error_str
                    or "404" in error_str):
                _supabase_table_missing.add("giveaways")
            error_key = "get_giveaway"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_giveaway error: {e}")
                _supabase_error_logged.add(error_key)
    # JSON fallback
    data = _read_json("data/giveaways.json")
    gw = data.get(str(giveaway_id), {})
    return gw if isinstance(gw, dict) else {}


def get_active_giveaways() -> list:
    """Return all not-yet-ended giveaways across every guild.

    FIX 4 — merges Supabase rows with JSON-stranded rows: a giveaway whose
    Supabase upsert failed (schema drift) lives ONLY in the JSON file and
    would otherwise never be ended by the 30s loop. JSON rows that already
    exist in Supabase (by id) are skipped so ended giveaways stay ended.
    """
    rows = []
    supabase_ids = set()
    if _use_supabase and "giveaways" not in _supabase_table_missing:
        try:
            result = _supabase.table("giveaways").select(
                "id, ended"
            ).execute()
            for row in (result.data or []):
                supabase_ids.add(str(row.get("id")))
        except Exception as e:
            error_str = str(e)
            if ("PGRST205" in error_str or "does not exist" in error_str
                    or "404" in error_str):
                _supabase_table_missing.add("giveaways")
            error_key = "get_active_giveaways"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_active_giveaways error: {e}")
                _supabase_error_logged.add(error_key)
        else:
            try:
                active = _supabase.table("giveaways").select("*").eq(
                    "ended", False
                ).execute()
                rows = active.data or []
            except Exception as e:
                error_key = "get_active_giveaways_active"
                if error_key not in _supabase_error_logged:
                    logger.error(f"[DB] get_active_giveaways error: {e}")
                    _supabase_error_logged.add(error_key)
    # JSON heal: active rows that Supabase doesn't know about at all
    data = _read_json("data/giveaways.json")
    for gid, gw in data.items():
        if (isinstance(gw, dict) and not gw.get("ended")
                and str(gid) not in supabase_ids):
            rows.append(gw)
    return rows


# ─── Async wrappers (P1 / D4 — non-blocking event loop) ────────
#
# The supabase-py client executes synchronous HTTP REST calls. Calling the
# sync functions above directly inside an async handler freezes the entire
# event loop — including Discord gateway heartbeats — for every network
# round-trip. AI-chat memory (get_conversation_history /
# save_conversation_message) runs on nearly every mention, so this was the
# highest-frequency blocker.
#
# PHASE 1 / PART 2.1 — each hot wrapper is now wrapped with
# @with_fallback(table, fallback_fn), which standardizes degradation:
# timeout/5xx/connection errors flip the global _supabase_degraded flag
# (shown in /botinfo), and a JSON fallback function answers the call if
# the sync layer somehow raised.
#
# Usage from async code:
#     from utils.db import get_conversation_history_async
#     history = await get_conversation_history_async(guild_id, user_id, ...)
#
# The sync functions remain unchanged for background tasks / sync contexts.

# ── PART 2.1 — standalone JSON fallbacks (mirror the sync functions'
# own fallback branches, so the decorator can call them directly) ──

def _json_get_guild_setting(guild_id: int, table: str) -> dict:
    data = _read_json(f"data/{table}.json")
    return data.get(str(guild_id), {})


def _json_set_guild_setting(guild_id: int, table: str, settings: dict):
    data = _read_json(f"data/{table}.json")
    data[str(guild_id)] = settings
    _write_json(f"data/{table}.json", data)


def _json_get_warnings(guild_id: int, user_id: int) -> list:
    data = _read_json("data/warnings.json")
    return data.get(str(guild_id), {}).get(str(user_id), [])


def _json_add_warning(guild_id: int, user_id: int, warning: dict) -> int:
    w = dict(warning)  # never mutate the caller's dict
    data = _read_json("data/warnings.json")
    g, u = str(guild_id), str(user_id)
    if g not in data or not isinstance(data[g], dict):
        data[g] = {}
    if u not in data[g] or not isinstance(data[g][u], list):
        data[g][u] = []
    all_cases = [
        w2.get("case_id", 0)
        for cases in data[g].values()
        for w2 in cases
        if isinstance(w2, dict)
    ]
    case_id = max(all_cases, default=0) + 1
    w["case_id"] = case_id
    data[g][u].append(w)
    _write_json("data/warnings.json", data)
    return case_id


def _json_get_conversation_history(guild_id: int, user_id: int,
                                    channel_id: int = 0,
                                    limit: int = 20) -> list:
    data = _read_json("data/conversation_memory.json")
    key = f"{guild_id}_{user_id}_{channel_id}"
    entries = data.get(key, [])
    if not isinstance(entries, list):
        return []
    return entries[-limit:]


def _json_save_conversation_message(guild_id: int, user_id: int, role: str,
                                     content: str, timestamp: str = None,
                                     channel_id: int = 0):
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat()
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


@with_fallback("guild_settings", _json_get_guild_setting)
async def get_guild_setting_async(guild_id: int, table: str) -> dict:
    """Non-blocking get_guild_setting — runs the blocking REST call in a
    thread-pool executor via asyncio.to_thread(). (Cached, PART 1 — the
    cache lives inside the sync function so thread and loop callers both
    benefit.)"""
    return await asyncio.to_thread(get_guild_setting, guild_id, table)


@with_fallback("guild_settings", _json_set_guild_setting)
async def set_guild_setting_async(guild_id: int, table: str, settings: dict):
    """Non-blocking set_guild_setting (invalidates the cache on write)."""
    return await asyncio.to_thread(set_guild_setting, guild_id, table, settings)


@with_fallback("warnings", _json_get_warnings)
async def get_warnings_async(guild_id: int, user_id: int) -> list:
    """Non-blocking get_warnings."""
    return await asyncio.to_thread(get_warnings, guild_id, user_id)


@with_fallback("warnings", _json_add_warning)
async def add_warning_async(guild_id: int, user_id: int, warning: dict) -> int:
    """Non-blocking add_warning."""
    return await asyncio.to_thread(add_warning, guild_id, user_id, warning)


@with_fallback("conversation_memory", _json_get_conversation_history)
async def get_conversation_history_async(guild_id: int, user_id: int,
                                         channel_id: int = 0,
                                         limit: int = 20) -> list:
    """Non-blocking get_conversation_history."""
    return await asyncio.to_thread(
        get_conversation_history, guild_id, user_id, channel_id, limit
    )


@with_fallback("conversation_memory", _json_save_conversation_message)
async def save_conversation_message_async(guild_id: int, user_id: int,
                                          role: str, content: str,
                                          timestamp: str = None,
                                          channel_id: int = 0):
    """Non-blocking save_conversation_message."""
    return await asyncio.to_thread(
        save_conversation_message, guild_id, user_id, role, content,
        timestamp, channel_id
    )


async def get_server_personality_async(guild_id: int) -> dict:
    """Non-blocking get_server_personality (PHASE 1 / PART 1 — cached
    under pers:{guild_id} for 300s inside the sync function). Used by the
    AI chat hot path so a cache miss no longer blocks the event loop."""
    return await asyncio.to_thread(get_server_personality, guild_id)


async def get_user_facts_async(guild_id: int, user_id: int) -> list:
    """Non-blocking get_user_facts (PHASE 4 AI memory)."""
    return await asyncio.to_thread(get_user_facts, guild_id, user_id)


async def add_user_fact_async(guild_id: int, user_id: int, fact: str,
                              max_facts: int = 10) -> bool:
    """Non-blocking add_user_fact (PHASE 4 AI memory)."""
    return await asyncio.to_thread(
        add_user_fact, guild_id, user_id, fact, max_facts
    )


async def clear_user_facts_async(guild_id: int, user_id: int) -> int:
    """Non-blocking clear_user_facts (PHASE 4 AI memory)."""
    return await asyncio.to_thread(clear_user_facts, guild_id, user_id)


async def get_active_giveaways_async() -> list:
    """Non-blocking get_active_giveaways (PHASE 4 giveaways loop)."""
    return await asyncio.to_thread(get_active_giveaways)


async def save_giveaway_async(giveaway: dict):
    """Non-blocking save_giveaway (PHASE 4 giveaways)."""
    return await asyncio.to_thread(save_giveaway, giveaway)


# ─── PHASE 1 / PART 4.5 — conversation memory retention ─────────

async def cleanup_old_conversation_memory():
    """Daily safety net: purge conversation_memory rows older than 7 days.

    save_conversation_message already trims to the most recent 20 per
    (guild, user, channel), so this is a belt-and-braces pass that keeps
    abandoned conversations and orphaned channels from accumulating
    forever. Called daily from cogs/ai_chat.py's cleanup_memory_task."""
    try:
        sb = get_supabase()
        if not sb:
            return
        # Delete messages older than 7 days as a safety net
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        await asyncio.to_thread(
            lambda: sb.table("conversation_memory")
              .delete()
              .lt("timestamp", cutoff)
              .execute()
        )
        logger.info("[CLEANUP] pruned conversation_memory older than 7 days")
    except Exception as e:
        logger.warning(f"[CLEANUP] conversation_memory cleanup failed: {e}")


# ─── PHASE 1 / PART 5 — daily fortune history (/fortune) ────────

async def get_fortune_history_async(user_id: str) -> dict | None:
    """Return the user's last fortune row, or None (PART 5 /fortune)."""
    try:
        sb = get_supabase()
        if not sb:
            return None
        result = await asyncio.to_thread(
            lambda: sb.table("fortune_history")
              .select("*")
              .eq("user_id", user_id)
              .maybe_single()
              .execute()
        )
        return result.data if result else None
    except Exception:
        return None


async def save_fortune_history_async(user_id: str, date_str: str,
                                      fortune_text: str):
    """Upsert the user's fortune for today (PART 5 /fortune)."""
    try:
        sb = get_supabase()
        if not sb:
            return
        await asyncio.to_thread(
            lambda: sb.table("fortune_history")
              .upsert({
                  "user_id": user_id,
                  "last_fortune_date": date_str,
                  "fortune_text": fortune_text,
              })
              .execute()
        )
    except Exception as e:
        logger.warning(f"[DB] save_fortune_history failed: {e}")


# ════════════════════════════════════════════════════════════════
# PHASE 2 (ENGAGEMENT CORE)
# Daily login streaks (/daily), leveling XP award, question of the
# day (/qotd), and member anniversaries (/anniversary). Every helper
# has a Supabase path and a JSON-file fallback so the features work
# before the migration SQL above has been run.
# ════════════════════════════════════════════════════════════════

# ─── PHASE 2 / PART 1 — daily login streaks (/daily) ───────────

_DAILY_STREAKS_JSON = "data/daily_streaks.json"


def _json_get_daily_streak(guild_id: str, user_id: str) -> dict | None:
    data = _read_json(_DAILY_STREAKS_JSON)
    row = data.get(f"{guild_id}_{user_id}")
    return row if isinstance(row, dict) else None


def _json_save_daily_streak(guild_id: str, user_id: str, streak: int,
                            highest: int, date_str: str, total: int):
    data = _read_json(_DAILY_STREAKS_JSON)
    data[f"{guild_id}_{user_id}"] = {
        "guild_id": guild_id,
        "user_id": user_id,
        "streak": int(streak),
        "highest_streak": int(highest),
        "last_claim_date": date_str,
        "total_claimed": int(total),
    }
    _write_json(_DAILY_STREAKS_JSON, data)


async def get_daily_streak_async(guild_id: str, user_id: str) -> dict | None:
    """PHASE 2 / PART 1 — return the user's daily-claim row for a guild:
    {"streak", "highest_streak", "last_claim_date", "total_claimed"},
    or None when they have never claimed. Supabase first, JSON fallback."""
    sb = get_supabase()
    if sb:
        try:
            result = await asyncio.to_thread(
                lambda: sb.table("daily_streaks")
                  .select("*")
                  .eq("guild_id", guild_id)
                  .eq("user_id", user_id)
                  .maybe_single()
                  .execute()
            )
            if result and result.data:
                return result.data
            # No row in Supabase — check the JSON fallback before giving
            # up (a write may have landed there after a Supabase failure).
            return _json_get_daily_streak(guild_id, user_id)
        except Exception as e:
            error_key = "get_daily_streak"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_daily_streak error: {e}")
                _supabase_error_logged.add(error_key)
            return _json_get_daily_streak(guild_id, user_id)
    return _json_get_daily_streak(guild_id, user_id)


async def save_daily_streak_async(guild_id: str, user_id: str, streak: int,
                                  highest: int, date_str: str, total: int):
    """PHASE 2 / PART 1 — upsert the user's daily-claim row for a guild."""
    payload = {
        "guild_id": guild_id,
        "user_id": user_id,
        "streak": int(streak),
        "highest_streak": int(highest),
        "last_claim_date": date_str,
        "total_claimed": int(total),
    }
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("daily_streaks").upsert(payload).execute()
            )
            return
        except Exception as e:
            error_key = "save_daily_streak"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] save_daily_streak error: {e}")
                logger.warning(
                    "[DB] Supabase write failed for 'daily_streaks'. "
                    "Falling back to JSON (run the PHASE 2 migration SQL)."
                )
                _supabase_error_logged.add(error_key)
    _json_save_daily_streak(guild_id, user_id, streak, highest,
                            date_str, total)


# ─── PHASE 2 / PART 1 — leveling XP award (user_levels) ─────────

_USER_LEVELS_JSON = "data/user_levels.json"


def level_from_total_xp(total_xp: int) -> int:
    """PHASE 2 — level for a total XP amount.

    KEEP IN SYNC with cogs/leveling.py Leveling.get_level_from_xp —
    the curve is 5·L² + 50·L + 100 XP per level."""
    level, remaining = 0, max(0, int(total_xp))
    while True:
        needed = 5 * (level ** 2) + 50 * level + 100
        if remaining < needed:
            return level
        remaining -= needed
        level += 1


def get_user_level_row(guild_id: int, user_id: int) -> dict:
    """PHASE 2 — read a user's {xp, level} row from user_levels
    (Supabase first, JSON fallback). Mirrors Leveling.get_user_level."""
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("user_levels").select("xp,level").eq(
                "guild_id", str(guild_id)
            ).eq("user_id", str(user_id)).execute()
            if r.data:
                row = r.data[0]
                return {"xp": int(row.get("xp", 0) or 0),
                        "level": int(row.get("level", 0) or 0)}
        except Exception as e:
            error_key = "get_user_level_row"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_level_row error: {e}")
                _supabase_error_logged.add(error_key)
    e = _read_json(_USER_LEVELS_JSON).get(f"{guild_id}_{user_id}", {})
    return {"xp": int(e.get("xp", 0) or 0),
            "level": int(e.get("level", 0) or 0)}


def award_user_xp(guild_id: int, user_id: int, amount: int) -> dict:
    """PHASE 2 / PART 1 — add XP to a user's user_levels row and
    recalculate the level (same curve as cogs/leveling.py).

    Returns {"xp", "old_level", "new_level", "leveled_up"}. Used by
    /daily; leveling XP from chat still flows through the Leveling cog.
    Negative amounts are clamped to 0 total."""
    if not isinstance(amount, int):
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            amount = 0
    row = get_user_level_row(guild_id, user_id)
    old_level = row["level"]
    new_xp = max(0, row["xp"] + amount)
    new_level = level_from_total_xp(new_xp)
    sb = get_supabase()
    saved = False
    if sb:
        try:
            sb.table("user_levels").upsert({
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "xp": int(new_xp),
                "level": int(new_level),
            }).execute()
            saved = True
        except Exception as e:
            error_key = "award_user_xp"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] award_user_xp error: {e}")
                _supabase_error_logged.add(error_key)
    if not saved:
        data = _read_json(_USER_LEVELS_JSON)
        data[f"{guild_id}_{user_id}"] = {"xp": int(new_xp),
                                         "level": int(new_level)}
        _write_json(_USER_LEVELS_JSON, data)
    return {"xp": new_xp, "old_level": old_level, "new_level": new_level,
            "leveled_up": new_level > old_level}


# ─── PHASE 2 / PART 2 — question of the day (/qotd) ─────────────

_QOTD_SETTINGS_TABLE = "qotd_settings"
_QOTD_QUEUE_JSON = "data/qotd_queue.json"

_QOTD_SETTINGS_DEFAULTS = {
    "channel_id": None,
    "enabled": False,
    "post_hour_utc": 14,
    "auto_thread": True,
    "last_post_date": None,
}


async def get_qotd_settings_async(guild_id: str) -> dict:
    """PHASE 2 / PART 2 — QOTD settings for a guild (cached 60s inside
    get_guild_setting; defaults filled for missing keys)."""
    raw = await get_guild_setting_async(int(guild_id), _QOTD_SETTINGS_TABLE)
    settings = dict(raw) if isinstance(raw, dict) else {}
    for key, default in _QOTD_SETTINGS_DEFAULTS.items():
        settings.setdefault(key, default)
    return settings


async def set_qotd_settings_async(guild_id: str, payload: dict):
    """PHASE 2 / PART 2 — save (merge) QOTD settings for a guild.

    Merges into the current row so a partial update (e.g. only
    last_post_date from the posting loop) can never wipe the channel or
    hour configuration."""
    current = await get_qotd_settings_async(guild_id)
    current.update(payload if isinstance(payload, dict) else {})
    # Keep only known columns — set_guild_setting sanitizes anyway, but
    # the JSON fallback row should also stay clean.
    clean = {k: v for k, v in current.items()
             if k in _TABLE_COLUMNS[_QOTD_SETTINGS_TABLE] or k == "guild_id"}
    await set_guild_setting_async(
        int(guild_id), _QOTD_SETTINGS_TABLE, clean
    )


def _json_qotd_queue(guild_id: str) -> list:
    data = _read_json(_QOTD_QUEUE_JSON)
    rows = data.get(str(guild_id), [])
    return rows if isinstance(rows, list) else []


def _json_save_qotd_queue(guild_id: str, rows: list):
    data = _read_json(_QOTD_QUEUE_JSON)
    data[str(guild_id)] = rows
    _write_json(_QOTD_QUEUE_JSON, data)


async def add_qotd_question_async(guild_id: str, question: str,
                                  added_by: str):
    """PHASE 2 / PART 2 — append a custom question to the guild's queue."""
    from datetime import datetime as _dt
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("qotd_queue").insert({
                    "guild_id": str(guild_id),
                    "question": question,
                    "added_by": str(added_by),
                    "used": False,
                    "added_at": _dt.utcnow().isoformat(),
                }).execute()
            )
            return
        except Exception as e:
            error_key = "add_qotd_question"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] add_qotd_question error: {e}")
                _supabase_error_logged.add(error_key)
    rows = _json_qotd_queue(guild_id)
    next_id = max((int(r.get("id", 0)) for r in rows
                   if isinstance(r, dict)), default=0) + 1
    rows.append({
        "id": next_id,
        "guild_id": str(guild_id),
        "question": question,
        "added_by": str(added_by),
        "used": False,
        "added_at": _dt.utcnow().isoformat(),
    })
    _json_save_qotd_queue(guild_id, rows)


async def get_next_qotd_question_async(guild_id: str) -> dict | None:
    """PHASE 2 / PART 2 — fetch AND CONSUME the next queued question.

    Returns {"question": str, "id": int|str} for the oldest unused row
    (which is marked used=True before returning, so two consumers can
    never post the same question), or None when the custom queue is
    empty — the caller then falls back to the built-in pool."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("qotd_queue").select("*").eq(
                    "guild_id", str(guild_id)
                ).eq("used", False).order("id", desc=False).limit(1).execute()
            result = await asyncio.to_thread(_fetch)
            if not (result and result.data):
                return None
            row = result.data[0]
            await asyncio.to_thread(
                lambda: sb.table("qotd_queue").update(
                    {"used": True}
                ).eq("id", row["id"]).execute()
            )
            return {"question": row.get("question", ""),
                    "id": row.get("id")}
        except Exception as e:
            error_key = "get_next_qotd_question"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_next_qotd_question error: {e}")
                _supabase_error_logged.add(error_key)
            return None
    # JSON fallback — consume in one pass
    rows = _json_qotd_queue(guild_id)
    for r in rows:
        if isinstance(r, dict) and not r.get("used"):
            r["used"] = True
            _json_save_qotd_queue(guild_id, rows)
            return {"question": r.get("question", ""), "id": r.get("id")}
    return None


async def get_qotd_queue_async(guild_id: str) -> list:
    """PHASE 2 / PART 2 — the guild's upcoming (unused) questions,
    oldest first. Used by /qotd list."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("qotd_queue").select("*").eq(
                    "guild_id", str(guild_id)
                ).eq("used", False).order("id", desc=False).limit(25).execute()
            result = await asyncio.to_thread(_fetch)
            return (result.data or []) if result else []
        except Exception as e:
            error_key = "get_qotd_queue"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_qotd_queue error: {e}")
                _supabase_error_logged.add(error_key)
    return [r for r in _json_qotd_queue(guild_id)
            if isinstance(r, dict) and not r.get("used")]


# ─── PHASE 2 / PART 3 — member anniversaries (/anniversary) ─────

_ANNIVERSARY_TABLE = "anniversary_settings"

_ANNIVERSARY_DEFAULTS = {
    "channel_id": None,
    "enabled": False,
    "last_run_date": None,
}


async def get_anniversary_settings_async(guild_id: str) -> dict:
    """PHASE 2 / PART 3 — anniversary settings for a guild (channel,
    enabled, last_run_date) with defaults filled."""
    raw = await get_guild_setting_async(int(guild_id), _ANNIVERSARY_TABLE)
    settings = dict(raw) if isinstance(raw, dict) else {}
    for key, default in _ANNIVERSARY_DEFAULTS.items():
        settings.setdefault(key, default)
    return settings


async def set_anniversary_settings_async(guild_id: str, payload: dict):
    """PHASE 2 / PART 3 — save (merge) anniversary settings for a guild.
    Merging keeps the daily loop's last_run_date update from wiping the
    channel / enabled configuration."""
    current = await get_anniversary_settings_async(guild_id)
    current.update(payload if isinstance(payload, dict) else {})
    clean = {k: v for k, v in current.items()
             if k in _TABLE_COLUMNS[_ANNIVERSARY_TABLE] or k == "guild_id"}
    await set_guild_setting_async(int(guild_id), _ANNIVERSARY_TABLE, clean)
