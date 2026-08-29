-- ============================================================================
-- Aurelia (miles-discord-bot) — COMPLETE Supabase migration
-- ============================================================================
-- Generated to match the ACTUAL table and column names used by the code
-- (utils/db.py _TABLE_COLUMNS + the CRUD calls in the cogs).
--
-- HOW TO USE: paste this ENTIRE file into the Supabase SQL editor and run.
-- Every statement is idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS),
-- so it is safe to run on a fresh project AND on an existing one — it only
-- creates what is missing and only adds columns that are absent.
--
-- Naming notes (vs. earlier drafts — the CODE is the source of truth):
--   * AI memory table is `user_memory` with a `facts` JSONB array
--     (one row per guild+user), NOT a per-row `user_facts` table.
--   * Giveaways are keyed by the short lowercase id shown in the embed
--     footer (`id TEXT`, e.g. 'd93fc8ac'), with `ends_at` FLOAT, `entries`
--     JSONB, `winner_ids` JSONB, `winners_count` INT and `host_name` TEXT.
--   * Custom commands are one row per guild: `commands` JSONB array.
--   * Proactive channels column is `channel_ids` (JSONB array of strings).
--   * Onboarding intro text column is `welcome_text`; roles is `roles` JSONB.
--   * Starboard uses TWO tables: starboard_settings + starboard_posts
--     (the posts table is what makes reposts once-only).
--   * leveling_settings.rate is a FLOAT multiplier (default 1.0), not an int.
-- ============================================================================


-- ============================================================================
-- 1. AI LONG-TERM MEMORY  (cogs/ai_chat.py, cogs/ai_memory.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_memory (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  facts JSONB DEFAULT '[]'::jsonb,
  updated_at TEXT,
  PRIMARY KEY (guild_id, user_id)
);
GRANT ALL ON public.user_memory TO anon;
ALTER TABLE public.user_memory DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 2. AI AUTOMOD ESCALATION LADDER  (cogs/ai_automod.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ai_automod_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  alert_channel_id TEXT,
  timeout_minutes INT DEFAULT 10,
  min_severity INT DEFAULT 3
);
GRANT ALL ON public.ai_automod_settings TO anon;
ALTER TABLE public.ai_automod_settings DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 3. STARBOARD  (cogs/starboard.py) — settings + once-only posts
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.starboard_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  channel_id TEXT,
  emoji TEXT DEFAULT '⭐',
  threshold INT DEFAULT 5
);
GRANT ALL ON public.starboard_settings TO anon;
ALTER TABLE public.starboard_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.starboard_posts (
  message_id BIGINT PRIMARY KEY,
  guild_id TEXT NOT NULL,
  channel_id TEXT,
  starboard_message_id BIGINT,
  author_id TEXT
);
GRANT ALL ON public.starboard_posts TO anon;
ALTER TABLE public.starboard_posts DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 4. GIVEAWAYS  (cogs/giveaways.py) — keyed by the short footer id
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.giveaways (
  id TEXT PRIMARY KEY,                -- short lowercase hex, e.g. 'd93fc8ac'
  guild_id TEXT NOT NULL,
  channel_id TEXT,
  message_id BIGINT,
  host_id TEXT,
  host_name TEXT,
  prize TEXT,
  ends_at FLOAT,
  winners_count INT DEFAULT 1,
  required_role_id TEXT,
  min_account_days INT DEFAULT 0,
  min_level INT DEFAULT 0,
  ended BOOLEAN DEFAULT FALSE,
  entries JSONB DEFAULT '[]'::jsonb,
  winner_ids JSONB DEFAULT '[]'::jsonb,
  created_at TEXT
);
GRANT ALL ON public.giveaways TO anon;
ALTER TABLE public.giveaways DISABLE ROW LEVEL SECURITY;

-- Repair for tables created before host_name existed (this missing column
-- made every giveaway upsert fail, which is why /giveaway end could not
-- find giveaways that /giveaway start had just created).
ALTER TABLE public.giveaways
  ADD COLUMN IF NOT EXISTS host_name TEXT;


-- ============================================================================
-- 5. CUSTOM COMMANDS  (cogs/custom_commands.py) — one row per guild
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.custom_commands (
  guild_id TEXT PRIMARY KEY,
  commands JSONB DEFAULT '[]'::jsonb
);
GRANT ALL ON public.custom_commands TO anon;
ALTER TABLE public.custom_commands DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 6. PROACTIVE PRESENCE  (cogs/proactive.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.proactive_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  channel_ids JSONB DEFAULT '[]'::jsonb
);
GRANT ALL ON public.proactive_settings TO anon;
ALTER TABLE public.proactive_settings DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 7. DM ONBOARDING  (cogs/onboarding.py)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.onboarding_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  welcome_text TEXT,
  roles JSONB DEFAULT '[]'::jsonb
);
GRANT ALL ON public.onboarding_settings TO anon;
ALTER TABLE public.onboarding_settings DISABLE ROW LEVEL SECURITY;


-- ============================================================================
-- 8. RECAP  (cogs/recap.py) — cooldowns only, no table needed.
--    (60s per-user cooldown is enforced in memory; nothing to create.)
-- ============================================================================


-- ============================================================================
-- 9. EARLIER SCHEMA FIXES (idempotent repairs for existing tables)
-- ============================================================================

-- Confessions counter
ALTER TABLE public.confess_settings
  ADD COLUMN IF NOT EXISTS count BIGINT NOT NULL DEFAULT 0;

-- Mod settings extras
ALTER TABLE public.mod_settings
  ADD COLUMN IF NOT EXISTS antispam_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.mod_settings
  ADD COLUMN IF NOT EXISTS warn_threshold_count INT DEFAULT 5;
ALTER TABLE public.mod_settings
  ADD COLUMN IF NOT EXISTS warn_threshold_action TEXT DEFAULT 'timeout_1h';
ALTER TABLE public.mod_settings
  ADD COLUMN IF NOT EXISTS antilink_channels TEXT[] DEFAULT '{}';

-- Welcome system (Mimu-style extras)
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS dm_message TEXT;
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS embed_mode TEXT DEFAULT 'embed';
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS welcome_image TEXT;
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS welcome_color TEXT DEFAULT '#FFC0CB';

-- Leveling settings
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS channel_id TEXT;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS rate FLOAT DEFAULT 1.0;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS rewards JSONB DEFAULT '{}'::jsonb;

-- Self-role panels (panels blob added after the original per-message schema)
ALTER TABLE public.self_role_panels
  ADD COLUMN IF NOT EXISTS panels JSONB DEFAULT '{}';

-- Per-channel conversation memory
ALTER TABLE public.conversation_memory
  ADD COLUMN IF NOT EXISTS channel_id TEXT DEFAULT '0';


-- ============================================================================
-- 10. FULL TABLE DEFINITIONS (for fresh databases / anything still missing)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.welcome_settings (
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
GRANT ALL ON public.welcome_settings TO anon;
ALTER TABLE public.welcome_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.mod_settings (
  guild_id TEXT PRIMARY KEY,
  log_channel_id TEXT,
  admin_role_id TEXT,
  max_warns_before_ban INT DEFAULT 5,
  warn_threshold_count INT DEFAULT 5,
  warn_threshold_action TEXT DEFAULT 'timeout_1h',
  antilink_channels TEXT[] DEFAULT '{}',
  antispam_enabled BOOLEAN DEFAULT FALSE
);
GRANT ALL ON public.mod_settings TO anon;
ALTER TABLE public.mod_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.log_settings (
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
GRANT ALL ON public.log_settings TO anon;
ALTER TABLE public.log_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.server_settings (
  guild_id TEXT PRIMARY KEY,
  autorole_id TEXT,
  custom_status TEXT,
  custom_status_type TEXT
);
GRANT ALL ON public.server_settings TO anon;
ALTER TABLE public.server_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.prefix_settings (
  guild_id TEXT PRIMARY KEY,
  prefix TEXT
);
GRANT ALL ON public.prefix_settings TO anon;
ALTER TABLE public.prefix_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.confess_settings (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  count BIGINT DEFAULT 0
);
GRANT ALL ON public.confess_settings TO anon;
ALTER TABLE public.confess_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.server_rules (
  guild_id TEXT PRIMARY KEY,
  rules TEXT,
  agree_role_id TEXT,
  announcement_channel_id TEXT
);
GRANT ALL ON public.server_rules TO anon;
ALTER TABLE public.server_rules DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.birthday_settings (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT
);
GRANT ALL ON public.birthday_settings TO anon;
ALTER TABLE public.birthday_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.bump_reminder_state (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  last_bump_message_id TEXT,
  last_bump_at TIMESTAMPTZ
);
GRANT ALL ON public.bump_reminder_state TO anon;
ALTER TABLE public.bump_reminder_state DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.leveling_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT TRUE,
  channel_id TEXT,
  rate FLOAT DEFAULT 1.0,
  rewards JSONB DEFAULT '{}'::jsonb,
  updated_at TEXT
);
GRANT ALL ON public.leveling_settings TO anon;
ALTER TABLE public.leveling_settings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.self_role_panels (
  guild_id TEXT PRIMARY KEY,
  panels JSONB DEFAULT '{}'
);
GRANT ALL ON public.self_role_panels TO anon;
ALTER TABLE public.self_role_panels DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.warnings (
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
GRANT ALL ON public.warnings TO anon;
GRANT ALL ON SEQUENCE public.warnings_id_seq TO anon;
ALTER TABLE public.warnings DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.reminders (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  text TEXT,
  end_time FLOAT,
  channel_id TEXT,
  fired BOOLEAN DEFAULT FALSE
);
GRANT ALL ON public.reminders TO anon;
GRANT ALL ON SEQUENCE public.reminders_id_seq TO anon;
ALTER TABLE public.reminders DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.conversation_memory (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  channel_id TEXT DEFAULT '0'
);
GRANT ALL ON public.conversation_memory TO anon;
GRANT ALL ON SEQUENCE public.conversation_memory_id_seq TO anon;
ALTER TABLE public.conversation_memory DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.server_personality (
  guild_id TEXT PRIMARY KEY,
  personality_note TEXT,
  set_by TEXT,
  updated_at TEXT
);
GRANT ALL ON public.server_personality TO anon;
ALTER TABLE public.server_personality DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.user_profiles (
  user_id TEXT PRIMARY KEY,
  bio TEXT,
  pronouns TEXT,
  timezone TEXT,
  updated_at TEXT
);
GRANT ALL ON public.user_profiles TO anon;
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.birthdays (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  month INT NOT NULL,
  day INT NOT NULL,
  PRIMARY KEY (guild_id, user_id)
);
GRANT ALL ON public.birthdays TO anon;
ALTER TABLE public.birthdays DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.tempbans (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  unban_time FLOAT NOT NULL,
  reason TEXT
);
GRANT ALL ON public.tempbans TO anon;
GRANT ALL ON SEQUENCE public.tempbans_id_seq TO anon;
ALTER TABLE public.tempbans DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.user_levels (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  xp INT DEFAULT 0,
  level INT DEFAULT 0,
  last_msg_time FLOAT DEFAULT 0,
  PRIMARY KEY (guild_id, user_id)
);
GRANT ALL ON public.user_levels TO anon;
ALTER TABLE public.user_levels DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.level_rewards (
  guild_id TEXT NOT NULL,
  level INT NOT NULL,
  role_id TEXT NOT NULL,
  PRIMARY KEY (guild_id, level)
);
GRANT ALL ON public.level_rewards TO anon;
ALTER TABLE public.level_rewards DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.invite_tracking (
  guild_id TEXT NOT NULL,
  inviter_id TEXT NOT NULL,
  invites INT DEFAULT 0,
  joins INT DEFAULT 0,
  leaves INT DEFAULT 0,
  PRIMARY KEY (guild_id, inviter_id)
);
GRANT ALL ON public.invite_tracking TO anon;
ALTER TABLE public.invite_tracking DISABLE ROW LEVEL SECURITY;
