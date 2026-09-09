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
-- PART 2 (welcome rework) — title / thumbnail source / footer template
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS welcome_title TEXT;
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS welcome_thumbnail TEXT DEFAULT 'avatar';
ALTER TABLE public.welcome_settings
  ADD COLUMN IF NOT EXISTS welcome_footer TEXT DEFAULT '{membercount} members ♡';

-- Leveling settings
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS channel_id TEXT;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS rate FLOAT DEFAULT 1.0;
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS rewards JSONB DEFAULT '{}'::jsonb;
-- FIX 2 — customizable level-up messages (template + channel mode:
-- active | configured | dm | none)
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS level_up_message TEXT DEFAULT '🎉 {user} just reached level {level}! ✦';
ALTER TABLE public.leveling_settings
  ADD COLUMN IF NOT EXISTS level_up_channel_mode TEXT DEFAULT 'active';

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
  welcome_color TEXT DEFAULT '#FFC0CB',
  welcome_title TEXT,
  welcome_thumbnail TEXT DEFAULT 'avatar',
  welcome_footer TEXT DEFAULT '{membercount} members ♡'
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
  level_up_message TEXT DEFAULT '🎉 {user} just reached level {level}! ✦',
  level_up_channel_mode TEXT DEFAULT 'active',
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

-- ─── DASHBOARD (web dashboard) ──────────────────────────────────────
-- Audit log for every dashboard mutation + owner blacklist storage.
CREATE TABLE IF NOT EXISTS public.dashboard_audit (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  guild_id TEXT NOT NULL,
  action TEXT NOT NULL,
  details JSONB,
  ip_address TEXT,
  user_agent TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_guild
  ON public.dashboard_audit(guild_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user
  ON public.dashboard_audit(user_id, timestamp DESC);
GRANT ALL ON public.dashboard_audit TO anon;
ALTER TABLE public.dashboard_audit DISABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.owner_blacklist (
  user_id TEXT PRIMARY KEY,
  added_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
GRANT ALL ON public.owner_blacklist TO anon;
ALTER TABLE public.owner_blacklist DISABLE ROW LEVEL SECURITY;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;

-- ─── PHASE N — AI PROVIDER USAGE ACCOUNTING ─────────────────────────
-- Persistent provider telemetry for the multi-provider AI router
-- (utils/ai_router.py). One row per (usage_date, provider, model,
-- profile); the OpenRouter daily-budget guard counts requests from
-- this table so the counter survives Render restarts.
--
-- METADATA ONLY: provider/model/profile names, request counts, token
-- counts and latency. This table NEVER stores prompts, AI responses,
-- conversation text, moderation text or API keys.
CREATE TABLE IF NOT EXISTS public.ai_provider_usage (
  id BIGSERIAL PRIMARY KEY,
  usage_date DATE NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  profile TEXT NOT NULL,
  requests INTEGER DEFAULT 0,
  successes INTEGER DEFAULT 0,
  failures INTEGER DEFAULT 0,
  input_tokens BIGINT DEFAULT 0,
  output_tokens BIGINT DEFAULT 0,
  total_latency_ms BIGINT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT ai_provider_usage_unique
    UNIQUE (usage_date, provider, model, profile)
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_date
  ON public.ai_provider_usage(usage_date DESC);
GRANT ALL ON public.ai_provider_usage TO anon;
ALTER TABLE public.ai_provider_usage DISABLE ROW LEVEL SECURITY;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;

-- ─── PHASE O — SERVER BOOSTER SYSTEM (/boosters) ────────────────────
-- Per-guild booster configuration for cogs/boosters.py:
--   announcement (channel/message/embed_mode/color/image_url/
--   thumbnail_mode/footer), booster role management (booster_role_id/
--   auto_role/remove_role_on_unboost), milestones (milestone_enabled/
--   milestone_message/milestone_counts + milestone_last high-water
--   mark so a threshold is announced once, EVER — restarts and boost
--   churn can never repost it).
-- updated_at is written by the code as an ISO-8601 UTC string
-- (TIMESTAMPTZ-safe boundary — the Phase N.1 22007 lesson).
-- milestone_counts is a JSONB array of ints (default [2, 7, 14] =
-- Discord boost-level boundaries; admins can add 5/10/20/25/50/100…).
CREATE TABLE IF NOT EXISTS public.booster_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  channel_id TEXT,
  message TEXT,
  embed_mode TEXT DEFAULT 'embed',
  color TEXT DEFAULT '#FFC0CB',
  image_url TEXT,
  thumbnail_mode TEXT DEFAULT 'member',
  footer TEXT,
  booster_role_id TEXT,
  auto_role BOOLEAN DEFAULT FALSE,
  remove_role_on_unboost BOOLEAN DEFAULT TRUE,
  milestone_enabled BOOLEAN DEFAULT TRUE,
  milestone_message TEXT,
  milestone_counts JSONB DEFAULT '[2,7,14]'::jsonb,
  milestone_last INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
GRANT ALL ON public.booster_settings TO anon;
ALTER TABLE public.booster_settings DISABLE ROW LEVEL SECURITY;
