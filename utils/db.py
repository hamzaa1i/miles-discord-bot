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
--
-- PHASE 3 (SOCIAL & IDENTITY SYSTEMS) — ship, time capsules,
-- achievements, message counts, custom color roles, nickname
-- requests, and privacy controls. Run in the Supabase SQL editor;
-- as with every other phase, each helper below also has a JSON-file
-- fallback so the features work even before these tables exist:
--
-- CREATE TABLE IF NOT EXISTS ship_history (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   user1_id TEXT NOT NULL,
--   user2_id TEXT NOT NULL,
--   score INT,
--   reason TEXT,
--   created_at TEXT
-- );
-- GRANT ALL ON public.ship_history TO anon;
-- ALTER TABLE public.ship_history DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS time_capsules (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   channel_id TEXT,
--   user_id TEXT NOT NULL,
--   message TEXT,
--   unlock_time TIMESTAMPTZ NOT NULL,
--   is_public BOOLEAN DEFAULT FALSE,
--   unlocked BOOLEAN DEFAULT FALSE,
--   created_at TEXT
-- );
-- PHASE N.1: unlock_time is TIMESTAMPTZ (this matches the LIVE production
-- table — the schema comment previously said FLOAT, which is what caused
-- the 22007 epoch-float insert failures). The Python boundary converts
-- epoch floats <-> ISO-8601 UTC strings automatically (see
-- _capsule_iso / _normalize_capsule_row); the JSON fallback keeps floats.
-- GRANT ALL ON public.time_capsules TO anon;
-- ALTER TABLE public.time_capsules DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS user_achievements (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   achievement_key TEXT NOT NULL,
--   unlocked_at TEXT
-- );
-- GRANT ALL ON public.user_achievements TO anon;
-- ALTER TABLE public.user_achievements DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS message_counts (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   message_count INT DEFAULT 0,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.message_counts TO anon;
-- ALTER TABLE public.message_counts DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS user_color_roles (
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   role_id TEXT,
--   hex_color TEXT,
--   last_changed TEXT,
--   PRIMARY KEY (guild_id, user_id)
-- );
-- GRANT ALL ON public.user_color_roles TO anon;
-- ALTER TABLE public.user_color_roles DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS nick_requests (
--   id BIGSERIAL PRIMARY KEY,
--   guild_id TEXT NOT NULL,
--   user_id TEXT NOT NULL,
--   current_nick TEXT,
--   requested_nick TEXT,
--   status TEXT DEFAULT 'pending',
--   reviewer_id TEXT,
--   reason TEXT,
--   created_at TEXT,
--   resolved_at TEXT
-- );
-- GRANT ALL ON public.nick_requests TO anon;
-- ALTER TABLE public.nick_requests DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS nick_settings (
--   guild_id TEXT PRIMARY KEY,
--   channel_id TEXT,
--   auto_approve BOOLEAN DEFAULT FALSE,
--   cooldown_hours INT DEFAULT 24
-- );
-- GRANT ALL ON public.nick_settings TO anon;
-- ALTER TABLE public.nick_settings DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS user_privacy (
--   user_id TEXT PRIMARY KEY,
--   memory_optout BOOLEAN DEFAULT FALSE,
--   vibe_optout BOOLEAN DEFAULT FALSE,
--   recap_optout BOOLEAN DEFAULT FALSE,
--   ship_optout BOOLEAN DEFAULT FALSE,
--   fact_extraction_optout BOOLEAN DEFAULT FALSE,
--   updated_at TEXT
-- );
-- GRANT ALL ON public.user_privacy TO anon;
-- ALTER TABLE public.user_privacy DISABLE ROW LEVEL SECURITY;
--
-- DASHBOARD (web dashboard, utils/dashboard_api.py) — audit log for every
-- dashboard mutation. Owner blacklist storage (owner-only endpoints).
--
-- CREATE TABLE IF NOT EXISTS public.dashboard_audit (
--   id BIGSERIAL PRIMARY KEY,
--   user_id TEXT NOT NULL,
--   guild_id TEXT NOT NULL,
--   action TEXT NOT NULL,
--   details JSONB,
--   ip_address TEXT,
--   user_agent TEXT,
--   timestamp TIMESTAMPTZ DEFAULT NOW()
-- );
-- CREATE INDEX IF NOT EXISTS idx_audit_guild
--   ON public.dashboard_audit(guild_id, timestamp DESC);
-- CREATE INDEX IF NOT EXISTS idx_audit_user
--   ON public.dashboard_audit(user_id, timestamp DESC);
-- GRANT ALL ON public.dashboard_audit TO anon;
-- ALTER TABLE public.dashboard_audit DISABLE ROW LEVEL SECURITY;
--
-- CREATE TABLE IF NOT EXISTS public.owner_blacklist (
--   user_id TEXT PRIMARY KEY,
--   added_by TEXT,
--   created_at TIMESTAMPTZ DEFAULT NOW()
-- );
-- GRANT ALL ON public.owner_blacklist TO anon;
-- ALTER TABLE public.owner_blacklist DISABLE ROW LEVEL SECURITY;
--
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;
"""
import asyncio
import functools
import os
import json
import logging
from datetime import datetime, timedelta, timezone
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


# ─── PHASE N.1 / PART 8 — passive DM preference (/toggledms) ──────
#
# ONE shared gate for every UNSOLICITED (passive) DM aurelia sends:
# achievement unlocks, level-up DMs, welcome/join rewards, welcomer
# coin rewards, onboarding panels, economy safe-mode notices.
# Explicitly user-requested DM flows are NOT gated (modmail, /welcome
# test type:dm, user-created reminders, private time-capsule delivery,
# /privacy export, /owner dm).
#
# Storage: the same data/dm_prefs.json the /toggledms command has
# always used (welcome cog), so EXISTING stored preferences keep
# working — no migration, no Supabase table, no SQL. Default is
# allow=True (Part 9: no silent flips of stored preferences; users
# opt OUT with /toggledms and that is universally respected).

_DM_PREFS_JSON = "data/dm_prefs.json"


def user_allows_passive_dms(user_id) -> bool:
    """True when unsolicited aurelia DMs are allowed for this user.

    Default True (opt-out model, unchanged from the original /toggledms
    behavior). Reads data/dm_prefs.json; never raises — a broken/missing
    file means "allow" (same failure mode as before, and a missing file
    must never break a level-up or achievement unlock).
    """
    try:
        data = _read_json(_DM_PREFS_JSON)
        prefs = data.get(str(user_id))
        if isinstance(prefs, dict):
            return bool(prefs.get("dms_enabled", True))
        # legacy/malformed row — default allow
        return True
    except Exception:
        return True


def set_user_allows_passive_dms(user_id, allow: bool) -> None:
    """Store a user's passive-DM preference (the /toggledms writer)."""
    data = _read_json(_DM_PREFS_JSON)
    if not isinstance(data, dict):
        data = {}
    data[str(user_id)] = {"dms_enabled": bool(allow)}
    _write_json(_DM_PREFS_JSON, data)


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
    # PHASE 3 (SOCIAL & IDENTITY SYSTEMS) — /ship match history
    "ship_history": {
        "id", "guild_id", "user1_id", "user2_id", "score", "reason",
        "created_at",
    },
    # PHASE 3 — /capsule time capsules
    "time_capsules": {
        "id", "guild_id", "channel_id", "user_id", "message",
        "unlock_time", "is_public", "unlocked", "created_at",
    },
    # PHASE 3 — /achievements unlocked badges
    "user_achievements": {
        "id", "guild_id", "user_id", "achievement_key", "unlocked_at",
    },
    # PHASE 3 — message counts for the 100/1000-message achievements
    "message_counts": {
        "guild_id", "user_id", "message_count",
    },
    # PHASE 3 — /color custom color roles
    "user_color_roles": {
        "guild_id", "user_id", "role_id", "hex_color", "last_changed",
    },
    # PHASE 3 — /nick nickname request queue
    "nick_requests": {
        "id", "guild_id", "user_id", "current_nick", "requested_nick",
        "status", "reviewer_id", "reason", "created_at", "resolved_at",
    },
    # PHASE 3 — /nick review configuration
    "nick_settings": {
        "guild_id", "channel_id", "auto_approve", "cooldown_hours",
    },
    # PHASE 3 — /privacy per-user opt-outs
    "user_privacy": {
        "user_id", "memory_optout", "vibe_optout", "recap_optout",
        "ship_optout", "fact_extraction_optout", "updated_at",
    },
    # PHASE N — multi-provider AI usage accounting (metadata ONLY:
    # provider/model/profile names, counts, tokens, latency — never
    # prompts, responses, conversation or moderation text, never keys)
    "ai_provider_usage": {
        "usage_date", "provider", "model", "profile",
        "requests", "successes", "failures",
        "input_tokens", "output_tokens", "total_latency_ms", "updated_at",
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


# ════════════════════════════════════════════════════════════════
# PHASE 3 (SOCIAL & IDENTITY SYSTEMS)
# Ship history (/ship), time capsules (/capsule), achievements
# (/achievements), message counts, custom color roles (/color),
# nickname requests (/nick), and privacy controls (/privacy).
# Every helper has a Supabase path and a JSON-file fallback so the
# features work before the PHASE 3 migration SQL above has been run.
# ════════════════════════════════════════════════════════════════

# ─── PHASE 3 / PART 1 — ship history (/ship) ─────────────────────

_SHIP_HISTORY_JSON = "data/ship_history.json"


def _json_ship_rows(guild_id: str) -> list:
    data = _read_json(_SHIP_HISTORY_JSON)
    rows = data.get(str(guild_id), [])
    return rows if isinstance(rows, list) else []


async def save_ship_async(guild_id: str, user1_id: str, user2_id: str,
                          score: int, reason: str):
    """PHASE 3 / PART 1 — record a ship result for a guild."""
    from datetime import datetime as _dt
    payload = {
        "guild_id": str(guild_id),
        "user1_id": str(user1_id),
        "user2_id": str(user2_id),
        "score": int(score),
        "reason": str(reason or "")[:500],
        "created_at": _dt.utcnow().isoformat(),
    }
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("ship_history").insert(payload).execute()
            )
            return
        except Exception as e:
            error_key = "save_ship"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] save_ship error: {e}")
                _supabase_error_logged.add(error_key)
    data = _read_json(_SHIP_HISTORY_JSON)
    rows = data.get(str(guild_id), [])
    if not isinstance(rows, list):
        rows = []
    payload["id"] = max(
        (int(r.get("id", 0)) for r in rows if isinstance(r, dict)),
        default=0,
    ) + 1
    rows.append(payload)
    data[str(guild_id)] = rows
    _write_json(_SHIP_HISTORY_JSON, data)


async def get_ship_history_async(guild_id: str, user_id: str,
                                 limit: int = 5) -> list:
    """PHASE 3 / PART 1 — the user's most recent ships (involving them
    on either side), newest first."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("ship_history").select("*").eq(
                    "guild_id", str(guild_id)
                ).or_(
                    f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
                ).order("id", desc=True).limit(limit).execute()
            result = await asyncio.to_thread(_fetch)
            return (result.data or []) if result else []
        except Exception as e:
            error_key = "get_ship_history"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_ship_history error: {e}")
                _supabase_error_logged.add(error_key)
    rows = _json_ship_rows(guild_id)
    uid = str(user_id)
    mine = [
        r for r in rows
        if isinstance(r, dict) and uid in (str(r.get("user1_id")),
                                           str(r.get("user2_id")))
    ]
    mine.reverse()  # newest first (rows are appended oldest-first)
    return mine[:limit]


# ─── PHASE 3 / PART 2 — time capsules (/capsule) ──────────────────

_TIME_CAPSULES_JSON = "data/time_capsules.json"


def _json_capsules() -> dict:
    data = _read_json(_TIME_CAPSULES_JSON)
    return data if isinstance(data, dict) else {}


# ─── PHASE N.1 / PART 10 — Supabase TIMESTAMPTZ boundary ──────────
#
# ROOT CAUSE of the production Postgres 22007 ("invalid input syntax
# for type timestamp with time zone: 1788796983.7098389"): the live
# Supabase time_capsules table stores unlock_time as TIMESTAMPTZ
# (that is how the table was actually created in the Supabase editor),
# while create_capsule_async inserted raw Unix epoch FLOATS and
# get_due_capsules_async compared against a float — every Supabase
# capsule operation failed with 22007 and silently fell back to JSON.
#
# FIX: standardize on ISO-8601 UTC strings AT THE SUPABASE BOUNDARY.
# Epoch floats are converted on the way in (write) and on the way out
# (read) via _normalize_capsule_row, so every consumer (the cog, the
# delivery loop) keeps working with plain floats. The JSON fallback
# format is unchanged (floats), so existing local rows keep working
# with zero migration. Render-side note: no SQL migration is required —
# Postgres accepts ISO-8601 for TIMESTAMPTZ directly.

def _capsule_iso(unlock_time) -> str:
    """Epoch float -> ISO-8601 UTC string (the Supabase write format)."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz
    return _dt.fromtimestamp(float(unlock_time), tz=_tz.utc).isoformat()


def _capsule_epoch(value) -> float:
    """ISO-8601 string | numeric | None -> epoch float (never raises)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        from datetime import datetime as _dt
        text = str(value).strip()
        # Supabase may return "2026-09-08T12:34:56.789+00:00" (parseable
        # directly) or a date-only value; fromisoformat handles both on
        # 3.11+. A trailing 'Z' needs swapping to +00:00 pre-3.11 — do it
        # defensively anyway.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = _dt.fromisoformat(text)
        if dt.tzinfo is None:
            from datetime import timezone as _tz
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _normalize_capsule_row(row) -> dict:
    """One capsule row with unlock_time as an epoch float, whatever the
    storage layer returned (ISO string from Supabase, float from JSON)."""
    if not isinstance(row, dict):
        return row
    out = dict(row)
    out["unlock_time"] = _capsule_epoch(row.get("unlock_time"))
    return out


async def create_capsule_async(guild_id: str, channel_id, user_id: str,
                               message: str, unlock_time: float,
                               is_public: bool):
    """PHASE 3 / PART 2 — store a capsule; returns its id (int on
    Supabase, int client-side on the JSON fallback).

    PHASE N.1: `unlock_time` is written to Supabase as an ISO-8601 UTC
    string (TIMESTAMPTZ-compatible — fixes the 22007 insert failures);
    the JSON fallback keeps the legacy epoch-float format.
    """
    from datetime import datetime as _dt
    payload = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id) if channel_id else None,
        "user_id": str(user_id),
        "message": str(message)[:2000],
        "unlock_time": float(unlock_time),
        "is_public": bool(is_public),
        "unlocked": False,
        "created_at": _dt.utcnow().isoformat(),
    }
    sb = get_supabase()
    if sb:
        try:
            def _insert():
                return sb.table("time_capsules").insert({
                    **payload,
                    "unlock_time": _capsule_iso(unlock_time),
                }).execute()
            result = await asyncio.to_thread(_insert)
            if result and result.data:
                return result.data[0].get("id")
            return None
        except Exception as e:
            error_key = "create_capsule"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] create_capsule error: {e}")
                _supabase_error_logged.add(error_key)
    data = _json_capsules()
    next_id = max(
        (int(k) for k in data.keys() if str(k).isdigit()), default=0
    ) + 1
    payload["id"] = next_id
    data[str(next_id)] = payload
    _write_json(_TIME_CAPSULES_JSON, data)
    return next_id


async def get_user_capsules_async(user_id: str, unlocked: bool = False,
                                  limit: int = 20) -> list:
    """PHASE 3 / PART 2 — a user's capsules, sorted by unlock time
    ascending (earliest first). Rows are normalized: unlock_time is an
    epoch float whether the row came from Supabase (ISO string) or the
    JSON fallback (float)."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("time_capsules").select("*").eq(
                    "user_id", str(user_id)
                ).eq("unlocked", bool(unlocked)).order(
                    "unlock_time", desc=False
                ).limit(limit).execute()
            result = await asyncio.to_thread(_fetch)
            if result and result.data:
                return [_normalize_capsule_row(r) for r in result.data]
            return []
        except Exception as e:
            error_key = "get_user_capsules"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_capsules error: {e}")
                _supabase_error_logged.add(error_key)
    uid = str(user_id)
    rows = [
        r for r in _json_capsules().values()
        if isinstance(r, dict) and str(r.get("user_id")) == uid
        and bool(r.get("unlocked")) == bool(unlocked)
    ]
    rows.sort(key=lambda r: float(r.get("unlock_time", 0) or 0))
    return rows[:limit]


async def get_due_capsules_async() -> list:
    """PHASE 3 / PART 2 — every capsule with unlocked=False and
    unlock_time <= now, across all guilds (the 5-minute loop's work
    list).

    PHASE N.1: the Supabase comparison uses an ISO-8601 UTC string
    (`.lte("unlock_time", iso_now)`) — the old float comparison was the
    22007 that broke the due query. JSON fallback unchanged (floats).
    """
    from datetime import datetime as _dt
    from datetime import timezone as _tz
    now_iso = _dt.now(_tz.utc).isoformat()
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("time_capsules").select("*").eq(
                    "unlocked", False
                ).lte("unlock_time", now_iso).order(
                    "unlock_time", desc=False
                ).limit(100).execute()
            result = await asyncio.to_thread(_fetch)
            if result and result.data:
                return [_normalize_capsule_row(r) for r in result.data]
            return []
        except Exception as e:
            error_key = "get_due_capsules"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_due_capsules error: {e}")
                _supabase_error_logged.add(error_key)
    import time as _time
    now = float(_time.time())
    rows = [
        r for r in _json_capsules().values()
        if isinstance(r, dict) and not r.get("unlocked")
        and float(r.get("unlock_time", 0) or 0) <= now
    ]
    rows.sort(key=lambda r: float(r.get("unlock_time", 0) or 0))
    return rows


async def mark_capsule_unlocked_async(capsule_id):
    """PHASE 3 / PART 2 — flip a capsule to unlocked=True (terminal
    state, so a failed DM/channel send never retries forever)."""
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("time_capsules").update(
                    {"unlocked": True}
                ).eq("id", capsule_id).execute()
            )
            return True
        except Exception as e:
            error_key = "mark_capsule_unlocked"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] mark_capsule_unlocked error: {e}")
                _supabase_error_logged.add(error_key)
    data = _json_capsules()
    row = data.get(str(capsule_id))
    if isinstance(row, dict):
        row["unlocked"] = True
        _write_json(_TIME_CAPSULES_JSON, data)
        return True
    return False


async def delete_capsule_async(capsule_id, user_id: str) -> bool:
    """PHASE 3 / PART 2 — remove a PENDING capsule; only its creator
    can delete. Returns True when a row was removed."""
    sb = get_supabase()
    if sb:
        try:
            def _run():
                existing = sb.table("time_capsules").select("id").eq(
                    "id", capsule_id
                ).eq("user_id", str(user_id)).eq("unlocked", False).execute()
                if not existing.data:
                    return False
                sb.table("time_capsules").delete().eq(
                    "id", capsule_id
                ).execute()
                return True
            return await asyncio.to_thread(_run)
        except Exception as e:
            error_key = "delete_capsule"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] delete_capsule error: {e}")
                _supabase_error_logged.add(error_key)
            return False
    data = _json_capsules()
    row = data.get(str(capsule_id))
    if (isinstance(row, dict) and str(row.get("user_id")) == str(user_id)
            and not row.get("unlocked")):
        del data[str(capsule_id)]
        _write_json(_TIME_CAPSULES_JSON, data)
        return True
    return False


# ─── PHASE 3 / PART 3 — achievements + message counts ─────────────

_USER_ACHIEVEMENTS_JSON = "data/user_achievements.json"
_MESSAGE_COUNTS_JSON = "data/message_counts.json"


def _json_achievement_rows(guild_id: str, user_id: str) -> list:
    data = _read_json(_USER_ACHIEVEMENTS_JSON)
    rows = data.get(f"{guild_id}_{user_id}", [])
    return rows if isinstance(rows, list) else []


async def unlock_achievement_async(guild_id: str, user_id: str,
                                   achievement_key: str) -> bool:
    """PHASE 3 / PART 3 — unlock an achievement.

    Returns True when this call NEWLY unlocked it (first time), False
    when the user already had it. Look-before-insert makes it
    idempotent even if two listeners race."""
    from datetime import datetime as _dt
    sb = get_supabase()
    if sb:
        try:
            def _run():
                existing = sb.table("user_achievements").select("id").eq(
                    "guild_id", str(guild_id)
                ).eq("user_id", str(user_id)).eq(
                    "achievement_key", achievement_key
                ).execute()
                if existing.data:
                    return False
                sb.table("user_achievements").insert({
                    "guild_id": str(guild_id),
                    "user_id": str(user_id),
                    "achievement_key": achievement_key,
                    "unlocked_at": _dt.utcnow().isoformat(),
                }).execute()
                return True
            return await asyncio.to_thread(_run)
        except Exception as e:
            error_key = "unlock_achievement"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] unlock_achievement error: {e}")
                _supabase_error_logged.add(error_key)
            return False
    data = _read_json(_USER_ACHIEVEMENTS_JSON)
    key = f"{guild_id}_{user_id}"
    rows = data.get(key, [])
    if not isinstance(rows, list):
        rows = []
    if any(isinstance(r, dict) and r.get("achievement_key") == achievement_key
           for r in rows):
        return False
    rows.append({
        "achievement_key": achievement_key,
        "unlocked_at": _dt.utcnow().isoformat(),
    })
    data[key] = rows
    _write_json(_USER_ACHIEVEMENTS_JSON, data)
    return True


async def get_user_achievements_async(guild_id: str, user_id: str) -> list:
    """PHASE 3 / PART 3 — all achievements a user has unlocked in a
    guild: [{"achievement_key", "unlocked_at"}]."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("user_achievements").select(
                    "achievement_key,unlocked_at"
                ).eq("guild_id", str(guild_id)).eq(
                    "user_id", str(user_id)
                ).order("id", desc=False).execute()
            result = await asyncio.to_thread(_fetch)
            return (result.data or []) if result else []
        except Exception as e:
            error_key = "get_user_achievements"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_achievements error: {e}")
                _supabase_error_logged.add(error_key)
    return _json_achievement_rows(guild_id, user_id)


async def get_message_count_async(guild_id, user_id) -> int:
    """PHASE 3 / PART 3 — a user's stored message count for a guild."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("message_counts").select(
                    "message_count"
                ).eq("guild_id", str(guild_id)).eq(
                    "user_id", str(user_id)
                ).maybe_single().execute()
            result = await asyncio.to_thread(_fetch)
            if result and result.data:
                return int(result.data.get("message_count", 0) or 0)
            return 0
        except Exception as e:
            error_key = "get_message_count"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_message_count error: {e}")
                _supabase_error_logged.add(error_key)
    data = _read_json(_MESSAGE_COUNTS_JSON)
    try:
        return int(data.get(f"{guild_id}_{user_id}", 0) or 0)
    except (TypeError, ValueError):
        return 0


async def set_message_count_async(guild_id, user_id, count: int):
    """PHASE 3 / PART 3 — persist a user's message count for a guild."""
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("message_counts").upsert({
                    "guild_id": str(guild_id),
                    "user_id": str(user_id),
                    "message_count": int(max(0, count)),
                }).execute()
            )
            return
        except Exception as e:
            error_key = "set_message_count"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_message_count error: {e}")
                _supabase_error_logged.add(error_key)
    data = _read_json(_MESSAGE_COUNTS_JSON)
    data[f"{guild_id}_{user_id}"] = int(max(0, count))
    _write_json(_MESSAGE_COUNTS_JSON, data)


# ─── PHASE 3 / PART 4 — custom color roles (/color) ──────────────

_USER_COLOR_ROLES_JSON = "data/user_color_roles.json"


def _json_color_role(guild_id: str, user_id: str) -> dict | None:
    data = _read_json(_USER_COLOR_ROLES_JSON)
    row = data.get(f"{guild_id}_{user_id}")
    return row if isinstance(row, dict) else None


def _json_all_color_roles(guild_id: str) -> list:
    data = _read_json(_USER_COLOR_ROLES_JSON)
    prefix = f"{guild_id}_"
    return [
        dict(r, user_id=k[len(prefix):])
        for k, r in data.items()
        if isinstance(k, str) and k.startswith(prefix)
        and isinstance(r, dict)
    ]


async def get_user_color_role_async(guild_id, user_id) -> dict | None:
    """PHASE 3 / PART 4 — the user's color-role row for a guild:
    {"role_id", "hex_color", "last_changed"}, or None."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("user_color_roles").select(
                    "role_id,hex_color,last_changed"
                ).eq("guild_id", str(guild_id)).eq(
                    "user_id", str(user_id)
                ).maybe_single().execute()
            result = await asyncio.to_thread(_fetch)
            if result and result.data:
                return result.data
            return _json_color_role(str(guild_id), str(user_id))
        except Exception as e:
            error_key = "get_user_color_role"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_color_role error: {e}")
                _supabase_error_logged.add(error_key)
            return _json_color_role(str(guild_id), str(user_id))
    return _json_color_role(str(guild_id), str(user_id))


async def set_user_color_role_async(guild_id, user_id, role_id, hex_color: str):
    """PHASE 3 / PART 4 — upsert the user's color-role row (stamps
    last_changed with the current time for the 24h cooldown)."""
    from datetime import datetime as _dt
    payload = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "role_id": str(role_id),
        "hex_color": str(hex_color),
        "last_changed": _dt.utcnow().isoformat(),
    }
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("user_color_roles").upsert(payload).execute()
            )
            return
        except Exception as e:
            error_key = "set_user_color_role"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_user_color_role error: {e}")
                _supabase_error_logged.add(error_key)
    data = _read_json(_USER_COLOR_ROLES_JSON)
    data[f"{guild_id}_{user_id}"] = {
        "role_id": payload["role_id"],
        "hex_color": payload["hex_color"],
        "last_changed": payload["last_changed"],
    }
    _write_json(_USER_COLOR_ROLES_JSON, data)


async def delete_user_color_role_async(guild_id, user_id) -> bool:
    """PHASE 3 / PART 4 — remove the user's color-role row."""
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("user_color_roles").delete().eq(
                    "guild_id", str(guild_id)
                ).eq("user_id", str(user_id)).execute()
            )
            return True
        except Exception as e:
            error_key = "delete_user_color_role"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] delete_user_color_role error: {e}")
                _supabase_error_logged.add(error_key)
    data = _read_json(_USER_COLOR_ROLES_JSON)
    key = f"{guild_id}_{user_id}"
    if key in data:
        del data[key]
        _write_json(_USER_COLOR_ROLES_JSON, data)
        return True
    return False


async def get_guild_color_roles_async(guild_id) -> list:
    """PHASE 3 / PART 4 — every color-role row for a guild (for
    /color cleanup stale-entry sweeps)."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("user_color_roles").select(
                    "user_id,role_id,hex_color,last_changed"
                ).eq("guild_id", str(guild_id)).execute()
            result = await asyncio.to_thread(_fetch)
            if result and result.data:
                return result.data
        except Exception as e:
            error_key = "get_guild_color_roles"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_guild_color_roles error: {e}")
                _supabase_error_logged.add(error_key)
    return _json_all_color_roles(str(guild_id))


# ─── PHASE 3 / PART 5 — nickname requests (/nick) ────────────────

_NICK_REQUESTS_JSON = "data/nick_requests.json"
_NICK_SETTINGS_TABLE = "nick_settings"

_NICK_SETTINGS_DEFAULTS = {
    "channel_id": None,
    "auto_approve": False,
    "cooldown_hours": 24,
}


async def get_nick_settings_async(guild_id) -> dict:
    """PHASE 3 / PART 5 — nick review settings with defaults filled."""
    raw = await get_guild_setting_async(int(guild_id), _NICK_SETTINGS_TABLE)
    settings = dict(raw) if isinstance(raw, dict) else {}
    for key, default in _NICK_SETTINGS_DEFAULTS.items():
        settings.setdefault(key, default)
    return settings


async def set_nick_settings_async(guild_id, payload: dict):
    """PHASE 3 / PART 5 — save (merge) nick review settings."""
    current = await get_nick_settings_async(guild_id)
    current.update(payload if isinstance(payload, dict) else {})
    clean = {k: v for k, v in current.items()
             if k in _TABLE_COLUMNS[_NICK_SETTINGS_TABLE] or k == "guild_id"}
    await set_guild_setting_async(int(guild_id), _NICK_SETTINGS_TABLE, clean)


def _json_nick_rows(guild_id) -> list:
    data = _read_json(_NICK_REQUESTS_JSON)
    rows = data.get(str(guild_id), [])
    return rows if isinstance(rows, list) else []


def _json_save_nick_rows(guild_id, rows: list):
    data = _read_json(_NICK_REQUESTS_JSON)
    data[str(guild_id)] = rows
    _write_json(_NICK_REQUESTS_JSON, data)


async def create_nick_request_async(guild_id, user_id, current: str,
                                    requested: str):
    """PHASE 3 / PART 5 — store a pending nickname request; returns id."""
    from datetime import datetime as _dt
    payload = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "current_nick": str(current or "")[:64],
        "requested_nick": str(requested)[:32],
        "status": "pending",
        "reviewer_id": None,
        "reason": None,
        "created_at": _dt.utcnow().isoformat(),
        "resolved_at": None,
    }
    sb = get_supabase()
    if sb:
        try:
            def _insert():
                return sb.table("nick_requests").insert(payload).execute()
            result = await asyncio.to_thread(_insert)
            if result and result.data:
                return result.data[0].get("id")
            return None
        except Exception as e:
            error_key = "create_nick_request"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] create_nick_request error: {e}")
                _supabase_error_logged.add(error_key)
    rows = _json_nick_rows(guild_id)
    next_id = max(
        (int(r.get("id", 0)) for r in rows if isinstance(r, dict)),
        default=0,
    ) + 1
    payload["id"] = next_id
    rows.append(payload)
    _json_save_nick_rows(guild_id, rows)
    return next_id


async def get_pending_nick_requests_async(guild_id) -> list:
    """PHASE 3 / PART 5 — this guild's pending requests, oldest first."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("nick_requests").select("*").eq(
                    "guild_id", str(guild_id)
                ).eq("status", "pending").order(
                    "id", desc=False
                ).limit(25).execute()
            result = await asyncio.to_thread(_fetch)
            return (result.data or []) if result else []
        except Exception as e:
            error_key = "get_pending_nick_requests"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_pending_nick_requests error: {e}")
                _supabase_error_logged.add(error_key)
    return [r for r in _json_nick_rows(guild_id)
            if isinstance(r, dict) and r.get("status") == "pending"]


async def get_nick_request_async(request_id) -> dict | None:
    """PHASE 3 / PART 5 — one request by id (button handlers)."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("nick_requests").select("*").eq(
                    "id", request_id
                ).maybe_single().execute()
            result = await asyncio.to_thread(_fetch)
            return result.data if (result and result.data) else None
        except Exception as e:
            error_key = "get_nick_request"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_nick_request error: {e}")
                _supabase_error_logged.add(error_key)
            return None
    for guild_rows in _read_json(_NICK_REQUESTS_JSON).values():
        if not isinstance(guild_rows, list):
            continue
        for r in guild_rows:
            if (isinstance(r, dict)
                    and str(r.get("id")) == str(request_id)):
                return r
    return None


async def update_nick_request_async(request_id, status: str,
                                    reviewer_id, reason: str = ""):
    """PHASE 3 / PART 5 — mark a request approved/denied and stamp who
    reviewed it, when, and why."""
    from datetime import datetime as _dt
    payload = {
        "status": str(status),
        "reviewer_id": str(reviewer_id) if reviewer_id else None,
        "reason": (str(reason)[:200] if reason else None),
        "resolved_at": _dt.utcnow().isoformat(),
    }
    sb = get_supabase()
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("nick_requests").update(
                    payload
                ).eq("id", request_id).execute()
            )
            return True
        except Exception as e:
            error_key = "update_nick_request"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] update_nick_request error: {e}")
                _supabase_error_logged.add(error_key)
            return False
    data = _read_json(_NICK_REQUESTS_JSON)
    found = False
    for guild_rows in data.values():
        if not isinstance(guild_rows, list):
            continue
        for r in guild_rows:
            if (isinstance(r, dict)
                    and str(r.get("id")) == str(request_id)):
                r.update(payload)
                found = True
    if found:
        _write_json(_NICK_REQUESTS_JSON, data)
    return found


async def get_user_nick_requests_async(guild_id, user_id,
                                       limit: int = 10) -> list:
    """PHASE 3 / PART 5 — a user's requests in a guild, newest first
    (also drives the request cooldown check)."""
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("nick_requests").select("*").eq(
                    "guild_id", str(guild_id)
                ).eq("user_id", str(user_id)).order(
                    "id", desc=True
                ).limit(limit).execute()
            result = await asyncio.to_thread(_fetch)
            return (result.data or []) if result else []
        except Exception as e:
            error_key = "get_user_nick_requests"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_nick_requests error: {e}")
                _supabase_error_logged.add(error_key)
    uid = str(user_id)
    rows = [
        r for r in _json_nick_rows(guild_id)
        if isinstance(r, dict) and str(r.get("user_id")) == uid
    ]
    rows.reverse()  # newest first
    return rows[:limit]


# ─── PHASE 3 / PART 6 — privacy controls (/privacy) ──────────────

_USER_PRIVACY_JSON = "data/user_privacy.json"

_PRIVACY_FEATURES = (
    "memory", "vibe", "recap", "ship", "fact_extraction",
)

_PRIVACY_DEFAULTS = {
    "memory_optout": False,
    "vibe_optout": False,
    "recap_optout": False,
    "ship_optout": False,
    "fact_extraction_optout": False,
}


async def get_user_privacy_async(user_id) -> dict:
    """PHASE 3 / PART 6 — the user's privacy row with all five opt-out
    booleans filled (defaults: everything allowed).

    Results are cached for 120s (shared TTLCache) so hot paths like
    /vibe and /recap can check every message author without a REST
    round-trip each; set_user_privacy_async invalidates on write."""
    key = f"priv:{user_id}"
    cached = cache.get_sync(key)
    if cached is not None and isinstance(cached, dict):
        return dict(cached)
    row = None
    sb = get_supabase()
    if sb:
        try:
            def _fetch():
                return sb.table("user_privacy").select(
                    "memory_optout,vibe_optout,recap_optout,"
                    "ship_optout,fact_extraction_optout,updated_at"
                ).eq("user_id", str(user_id)).maybe_single().execute()
            result = await asyncio.to_thread(_fetch)
            row = result.data if (result and result.data) else None
        except Exception as e:
            error_key = "get_user_privacy"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] get_user_privacy error: {e}")
                _supabase_error_logged.add(error_key)
            row = None
    if not row:
        data = _read_json(_USER_PRIVACY_JSON)
        row = data.get(str(user_id))
        if not isinstance(row, dict):
            row = {}
    settings = dict(_PRIVACY_DEFAULTS)
    for col in _PRIVACY_DEFAULTS:
        settings[col] = bool(row.get(col, False))
    settings["updated_at"] = row.get("updated_at") or ""
    cache.set_sync(key, dict(settings), ttl=120)
    return settings


async def set_user_privacy_async(user_id, feature: str, enabled: bool):
    """PHASE 3 / PART 6 — set one feature's opt-out (or all five when
    feature='all').

    `enabled=True` means the feature is ALLOWED (opt-out False);
    `enabled=False` opts the user out. Returns the saved row."""
    from datetime import datetime as _dt
    current = await get_user_privacy_async(user_id)
    features = _PRIVACY_FEATURES if feature == "all" else (feature,)
    for f in features:
        col = f"{f}_optout"
        if col in _PRIVACY_DEFAULTS:
            current[col] = not bool(enabled)
    current["updated_at"] = _dt.utcnow().isoformat()
    payload = {
        "user_id": str(user_id),
        "memory_optout": bool(current["memory_optout"]),
        "vibe_optout": bool(current["vibe_optout"]),
        "recap_optout": bool(current["recap_optout"]),
        "ship_optout": bool(current["ship_optout"]),
        "fact_extraction_optout": bool(current["fact_extraction_optout"]),
        "updated_at": current["updated_at"],
    }
    sb = get_supabase()
    saved = False
    if sb:
        try:
            await asyncio.to_thread(
                lambda: sb.table("user_privacy").upsert(payload).execute()
            )
            saved = True
        except Exception as e:
            error_key = "set_user_privacy"
            if error_key not in _supabase_error_logged:
                logger.error(f"[DB] set_user_privacy error: {e}")
                _supabase_error_logged.add(error_key)
    if not saved:
        data = _read_json(_USER_PRIVACY_JSON)
        data[str(user_id)] = payload
        _write_json(_USER_PRIVACY_JSON, data)
    cache.invalidate_sync(f"priv:{user_id}")
    return current


def _privacy_purge_json(user_id: str) -> dict:
    """JSON-fallback side of delete_all_user_data_async. Returns the
    same counts shape as the Supabase path."""
    uid = str(user_id)
    counts = {}

    def _purge_keyed(path: str, out_key: str, idx: int = 1) -> int:
        data = _read_json(path)
        removed = 0
        for k in list(data.keys()):
            parts = str(k).split("_")
            if len(parts) > idx and parts[idx] == uid:
                del data[k]
                removed += 1
        if removed:
            _write_json(path, data)
        counts[out_key] = removed
        return removed

    _purge_keyed("data/user_memory.json", "facts")
    _purge_keyed("data/conversation_memory.json", "conversation_memory")
    _purge_keyed("data/user_levels.json", "levels")
    _purge_keyed("data/daily_streaks.json", "daily_streaks")
    _purge_keyed("data/user_achievements.json", "achievements")
    _purge_keyed("data/user_color_roles.json", "color_roles")
    _purge_keyed("data/message_counts.json", "message_counts")

    # profile
    data = _read_json("data/user_profiles.json")
    if uid in data:
        del data[uid]
        _write_json("data/user_profiles.json", data)
        counts["profile"] = 1
    else:
        counts["profile"] = 0

    # privacy row
    data = _read_json(_USER_PRIVACY_JSON)
    if uid in data:
        del data[uid]
        _write_json(_USER_PRIVACY_JSON, data)
        counts["privacy"] = 1
    else:
        counts["privacy"] = 0

    # warnings (nested guild -> user)
    data = _read_json("data/warnings.json")
    removed = 0
    for g in list(data.keys()):
        users = data.get(g)
        if isinstance(users, dict) and uid in users:
            removed += len(users[uid]) if isinstance(users[uid], list) else 1
            del users[uid]
    if removed:
        _write_json("data/warnings.json", data)
    counts["warnings"] = removed

    # time capsules (keyed by capsule id)
    data = _read_json(_TIME_CAPSULES_JSON)
    before = len(data)
    data = {k: v for k, v in data.items()
            if not (isinstance(v, dict) and str(v.get("user_id")) == uid)}
    if len(data) != before:
        _write_json(_TIME_CAPSULES_JSON, data)
    counts["capsules"] = before - len(data)

    # nick requests (per-guild lists)
    data = _read_json(_NICK_REQUESTS_JSON)
    removed = 0
    for g in list(data.keys()):
        rows = data.get(g)
        if not isinstance(rows, list):
            continue
        keep = [r for r in rows
                if not (isinstance(r, dict)
                        and str(r.get("user_id")) == uid)]
        removed += len(rows) - len(keep)
        data[g] = keep
    if removed:
        _write_json(_NICK_REQUESTS_JSON, data)
    counts["nick_requests"] = removed

    # ship history (per-guild lists, either side)
    data = _read_json(_SHIP_HISTORY_JSON)
    removed = 0
    for g in list(data.keys()):
        rows = data.get(g)
        if not isinstance(rows, list):
            continue
        keep = [r for r in rows
                if not (isinstance(r, dict)
                        and uid in (str(r.get("user1_id")),
                                    str(r.get("user2_id"))))]
        removed += len(rows) - len(keep)
        data[g] = keep
    if removed:
        _write_json(_SHIP_HISTORY_JSON, data)
    counts["ships"] = removed

    return counts


def _sb_purge(table: str, where: list) -> int:
    """Count-then-delete rows matching all eq filters. 0 when nothing
    matched, -1 when Supabase is unavailable (caller falls back)."""
    sb = get_supabase()
    if not sb:
        return -1
    q = sb.table(table).select("*")
    for col, val in where:
        q = q.eq(col, val)
    rows = q.execute().data or []
    if not rows:
        return 0
    qd = sb.table(table).delete()
    for col, val in where:
        qd = qd.eq(col, val)
    qd.execute()
    return len(rows)


async def delete_all_user_data_async(user_id) -> dict:
    """PHASE 3 / PART 6 — GDPR-style purge of every row the user owns
    across all tables, across all guilds. Returns a {label: count} dict.

    Supabase first; any failure (or no Supabase) runs the JSON purge
    so the user always gets a real deletion. Discord-side artifacts
    (color roles) are deleted by the /privacy cog BEFORE this call."""
    uid = str(user_id)
    counts = {}

    async def _purge(label: str, table: str, where: list):
        try:
            n = await asyncio.to_thread(_sb_purge, table, where)
        except Exception as e:
            logger.error(f"[DB] purge {table} failed: {e}")
            n = -1
        if n >= 0:
            counts[label] = n

    await _purge("facts", "user_memory", [("user_id", uid)])
    await _purge("conversation_memory", "conversation_memory",
                 [("user_id", uid)])
    await _purge("profile", "user_profiles", [("user_id", uid)])
    await _purge("levels", "user_levels", [("user_id", uid)])
    await _purge("warnings", "warnings", [("user_id", uid)])
    await _purge("daily_streaks", "daily_streaks", [("user_id", uid)])
    await _purge("capsules", "time_capsules", [("user_id", uid)])
    await _purge("achievements", "user_achievements", [("user_id", uid)])
    await _purge("color_roles", "user_color_roles", [("user_id", uid)])
    await _purge("nick_requests", "nick_requests", [("user_id", uid)])
    await _purge("privacy", "user_privacy", [("user_id", uid)])

    # fortune_history (no JSON fallback for this table in db.py)
    sb = get_supabase()
    if sb:
        try:
            n = await asyncio.to_thread(
                _sb_purge, "fortune_history", [("user_id", uid)]
            )
            if n >= 0:
                counts["fortunes"] = n
        except Exception:
            pass

    # ship_history needs an OR filter (either side of the ship)
    if sb:
        try:
            def _purge_ship():
                rows = sb.table("ship_history").select("id").or_(
                    f"user1_id.eq.{uid},user2_id.eq.{uid}"
                ).execute().data or []
                if not rows:
                    return 0
                ids = [r["id"] for r in rows]
                sb.table("ship_history").delete().in_("id", ids).execute()
                return len(ids)
            counts["ships"] = await asyncio.to_thread(_purge_ship)
        except Exception as e:
            logger.error(f"[DB] purge ship_history failed: {e}")

    # message counts (achievement bookkeeping — purge for a clean slate)
    await _purge("message_counts", "message_counts", [("user_id", uid)])

    if not sb:
        # No Supabase at all — the JSON purge is the real deletion.
        return _privacy_purge_json(uid)

    # Supabase path succeeded for the listed tables; still run the JSON
    # purge so any fallback-stranded rows (from earlier outages) are
    # wiped too — merged into the counts.
    json_counts = await asyncio.to_thread(_privacy_purge_json, uid)
    for k, v in json_counts.items():
        counts[k] = counts.get(k, 0) + v
    return counts


async def export_user_data_async(user_id) -> dict:
    """PHASE 3 / PART 6 — compile everything stored about a user into
    one JSON-serializable dict (for /privacy export)."""
    from datetime import datetime as _dt
    uid = str(user_id)
    export = {
        "generated_at": _dt.utcnow().isoformat(),
        "user_id": uid,
    }
    sb = get_supabase()

    def _sb_select(table: str, where: list) -> list:
        if not sb:
            return []
        q = sb.table(table).select("*")
        for col, val in where:
            q = q.eq(col, val)
        return (q.execute().data or [])

    async def _rows(label: str, table: str, where: list, json_fn):
        try:
            rows = await asyncio.to_thread(_sb_select, table, where)
        except Exception:
            rows = []
        if not rows:
            rows = await asyncio.to_thread(json_fn) if json_fn else []
        export[label] = rows

    def _json_facts():
        data = _read_json("data/user_memory.json")
        return [
            {"guild_id": k.rsplit("_", 1)[0], "facts": v.get("facts", [])}
            for k, v in data.items()
            if isinstance(v, dict) and k.rsplit("_", 1)[-1] == uid
        ]

    def _json_conv():
        data = _read_json("data/conversation_memory.json")
        out = []
        for k, entries in data.items():
            parts = str(k).split("_")
            if len(parts) >= 3 and parts[1] == uid and isinstance(entries, list):
                out.append({
                    "guild_id": parts[0], "channel_id": parts[2],
                    "messages": entries,
                })
        return out

    def _json_levels():
        data = _read_json("data/user_levels.json")
        return [
            {"guild_id": k.rsplit("_", 1)[0], **{c: v.get(c, 0)
                                                 for c in ("xp", "level")}}
            for k, v in data.items()
            if isinstance(v, dict) and k.rsplit("_", 1)[-1] == uid
        ]

    def _json_streaks():
        data = _read_json("data/daily_streaks.json")
        return [
            {"guild_id": k.rsplit("_", 1)[0], **v}
            for k, v in data.items()
            if isinstance(v, dict) and k.rsplit("_", 1)[-1] == uid
        ]

    def _json_capsules_export():
        # (deliberately NOT named _json_capsules — that would shadow
        # the module-level helper and recurse forever)
        return [
            v for v in _json_capsules().values()
            if isinstance(v, dict) and str(v.get("user_id")) == uid
        ]

    def _json_achievements():
        # flat rows (same shape as the Supabase path): one dict per
        # unlocked achievement, with its guild attached
        data = _read_json(_USER_ACHIEVEMENTS_JSON)
        out = []
        for gk, rows in data.items():
            if not isinstance(rows, list):
                continue
            if gk.rsplit("_", 1)[-1] != uid:
                continue
            for r in rows:
                if isinstance(r, dict):
                    out.append({"guild_id": gk.rsplit("_", 1)[0], **r})
        return out

    def _json_warnings():
        data = _read_json("data/warnings.json")
        out = []
        for g, users in data.items():
            if isinstance(users, dict) and uid in users:
                out.append({"guild_id": g, "warnings": users[uid]})
        return out

    await _rows("facts", "user_memory", [("user_id", uid)], _json_facts)
    await _rows("conversation_history", "conversation_memory",
                [("user_id", uid)], _json_conv)
    await _rows("levels", "user_levels", [("user_id", uid)], _json_levels)
    await _rows("daily_streaks", "daily_streaks", [("user_id", uid)],
                _json_streaks)
    await _rows("time_capsules", "time_capsules", [("user_id", uid)],
                _json_capsules_export)
    await _rows("achievements", "user_achievements", [("user_id", uid)],
                _json_achievements)
    await _rows("warnings", "warnings", [("user_id", uid)], _json_warnings)

    # profile + privacy (single rows)
    try:
        export["profile"] = await asyncio.to_thread(get_user_profile, uid)
    except Exception:
        export["profile"] = {}
    try:
        export["privacy"] = await get_user_privacy_async(uid)
    except Exception:
        export["privacy"] = dict(_PRIVACY_DEFAULTS)

    return export


# ─── PHASE N: AI provider usage accounting ──────────────────────────
#
# Persistent, restart-safe provider telemetry for utils/ai_router.py
# (spec Part 9). One row per (usage_date, provider, model, profile).
#
# PRIVACY GUARANTEE: this table stores METADATA ONLY — provider name,
# model id, profile, request counts, token counts, latency. It NEVER
# stores prompts, responses, conversation text, moderation text or API
# keys. Writes are fire-and-forget from the router (thread executor);
# failures fall back to JSON and never break AI replies.
#
# Supabase schema (run scripts/supabase_migration.sql):
#   ai_provider_usage(
#     id BIGSERIAL PRIMARY KEY,
#     usage_date DATE NOT NULL,
#     provider TEXT NOT NULL,
#     model TEXT NOT NULL,
#     profile TEXT NOT NULL,
#     requests INT DEFAULT 0, successes INT DEFAULT 0, failures INT DEFAULT 0,
#     input_tokens BIGINT DEFAULT 0, output_tokens BIGINT DEFAULT 0,
#     total_latency_ms BIGINT DEFAULT 0,
#     updated_at TIMESTAMPTZ DEFAULT NOW(),
#     UNIQUE (usage_date, provider, model, profile))
#
# JSON fallback: data/ai_provider_usage.json
#   { "2026-09-07": [ {provider, model, profile, requests, ...}, ... ] }
#   days older than 7 are pruned on write.

_AI_USAGE_JSON = "data/ai_provider_usage.json"
_AI_USAGE_KEEP_DAYS = 7

_USAGE_INT_FIELDS = (
    "requests", "successes", "failures",
    "input_tokens", "output_tokens", "total_latency_ms",
)


def _json_usage_day(day: str) -> list:
    data = _read_json(_AI_USAGE_JSON)
    rows = data.get(day, [])
    return rows if isinstance(rows, list) else []


def record_ai_usage(usage_date: str, provider: str, model: str,
                    profile: str, requests: int = 0, successes: int = 0,
                    failures: int = 0, input_tokens: int = 0,
                    output_tokens: int = 0, total_latency_ms: int = 0) -> bool:
    """Increment (or insert) one usage row. Supabase when available,
    JSON fallback otherwise. Never raises."""
    try:
        if using_supabase():
            sb = get_supabase()
            if sb is not None:
                rows = sb.table("ai_provider_usage").select("id,requests,successes,failures,input_tokens,output_tokens,total_latency_ms") \
                    .eq("usage_date", usage_date).eq("provider", provider) \
                    .eq("model", model).eq("profile", profile).execute().data or []
                if rows:
                    row = rows[0]
                    sb.table("ai_provider_usage").update({
                        "requests": int(row.get("requests", 0)) + int(requests),
                        "successes": int(row.get("successes", 0)) + int(successes),
                        "failures": int(row.get("failures", 0)) + int(failures),
                        "input_tokens": int(row.get("input_tokens", 0) or 0) + int(input_tokens),
                        "output_tokens": int(row.get("output_tokens", 0) or 0) + int(output_tokens),
                        "total_latency_ms": int(row.get("total_latency_ms", 0) or 0) + int(total_latency_ms),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", row["id"]).execute()
                else:
                    sb.table("ai_provider_usage").insert({
                        "usage_date": usage_date,
                        "provider": provider,
                        "model": model,
                        "profile": profile,
                        "requests": int(requests),
                        "successes": int(successes),
                        "failures": int(failures),
                        "input_tokens": int(input_tokens),
                        "output_tokens": int(output_tokens),
                        "total_latency_ms": int(total_latency_ms),
                    }).execute()
                return True
    except Exception as e:
        logger.debug(f"[DB] ai_provider_usage supabase write failed: {e}")

    # JSON fallback (also the primary path without Supabase)
    try:
        from datetime import date as _date, timedelta as _td
        try:
            day = _date.fromisoformat(str(usage_date))
        except (ValueError, TypeError):
            day = _date.today()
        data = _read_json(_AI_USAGE_JSON)
        rows = data.get(str(day), [])
        if not isinstance(rows, list):
            rows = []
        found = None
        for r in rows:
            if (isinstance(r, dict) and r.get("provider") == provider
                    and r.get("model") == model
                    and r.get("profile") == profile):
                found = r
                break
        if found is None:
            found = {"provider": provider, "model": model, "profile": profile,
                     "requests": 0, "successes": 0, "failures": 0,
                     "input_tokens": 0, "output_tokens": 0,
                     "total_latency_ms": 0}
            rows.append(found)
        found["requests"] = int(found.get("requests", 0)) + int(requests)
        found["successes"] = int(found.get("successes", 0)) + int(successes)
        found["failures"] = int(found.get("failures", 0)) + int(failures)
        found["input_tokens"] = int(found.get("input_tokens", 0)) + int(input_tokens)
        found["output_tokens"] = int(found.get("output_tokens", 0)) + int(output_tokens)
        found["total_latency_ms"] = int(found.get("total_latency_ms", 0)) + int(total_latency_ms)
        data[str(day)] = rows
        # prune old days
        cutoff = (_date.today() - _td(days=_AI_USAGE_KEEP_DAYS)).isoformat()
        data = {k: v for k, v in data.items() if str(k) >= cutoff}
        _write_json(_AI_USAGE_JSON, data)
        return True
    except Exception as e:
        logger.debug(f"[DB] ai_provider_usage json write failed: {e}")
        return False


def get_ai_usage_for_date(usage_date: str) -> list:
    """Read every usage row for one date (UTC iso 'YYYY-MM-DD').
    Supabase first, JSON fallback. Returns [] on any failure — never
    raises (the router treats telemetry as best-effort)."""
    rows: list = []
    try:
        if using_supabase():
            sb = get_supabase()
            if sb is not None:
                rows = sb.table("ai_provider_usage").select("*") \
                    .eq("usage_date", usage_date).execute().data or []
    except Exception as e:
        logger.debug(f"[DB] ai_provider_usage supabase read failed: {e}")
        rows = []
    if rows:
        return rows
    try:
        return _json_usage_day(str(usage_date))
    except Exception:
        return []


async def record_ai_usage_async(**kwargs) -> bool:
    """Thread-pool wrapper for the event loop (router hot path)."""
    return await asyncio.to_thread(record_ai_usage, **kwargs)


async def get_ai_usage_for_date_async(usage_date: str) -> list:
    return await asyncio.to_thread(get_ai_usage_for_date, usage_date)
