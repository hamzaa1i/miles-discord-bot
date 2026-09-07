import sys
# BUG 5 — line buffering so print() shows up immediately in Render logs
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask, jsonify
from threading import Thread
from utils.cache import cache
from utils.usage_logger import usage_logger

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('cyn')

# PHASE M (PART 6) — support server link (optional). When set it is
# appended to generic error messages (and cogs/help.py reads the same
# env) so users always have a human to turn to. Empty string = feature
# silently off, nothing changes for existing users.
SUPPORT_SERVER_URL = (os.getenv("SUPPORT_SERVER_URL") or "").strip()
SUPPORT_HINT = (
    f"\nneed help? support server: {SUPPORT_SERVER_URL}"
    if SUPPORT_SERVER_URL else ""
)

# PHASE 1 / PART 7 — Sentry error tracking (optional).
# Enabled only when SENTRY_DSN is set in the environment (add it to the
# Render env vars if you want crash + error reporting; the free tier is
# 5,000 errors/month). SENTRY_ENV (default "production") and
# SENTRY_RELEASE (default "unknown") are optional tags.
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_logging = LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )

        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.1,
            environment=os.getenv("SENTRY_ENV", "production"),
            integrations=[sentry_logging],
            release=os.getenv("SENTRY_RELEASE", "unknown"),
        )
        logger.info("✅ Sentry error tracking initialized")
    except Exception as e:
        logger.warning(f"⚠️ Sentry init failed: {e}")
else:
    logger.info("ℹ️ Sentry disabled (SENTRY_DSN not set)")

# Owner ID from env (used everywhere)
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Global start_time — set before bot starts
start_time = datetime.utcnow()

# FIX 1 — Single Flask app. keep_alive.py no longer creates its own Flask app;
# it only stores tracking variables (bot_ref, start_time, total_ai_calls, etc.)
# that this app's /health route reads.
app = Flask(__name__)
bot = None  # set after bot is created

# DASHBOARD (PART 1) — register the /api/dashboard/* blueprint (auth,
# CORS, rate limit, CSRF and audit live in utils/dashboard_api.py).
try:
    from utils.dashboard_api import init_dashboard_api
    init_dashboard_api(app)
except Exception as e:
    logger.error(f"❌ Dashboard API registration failed: {e}")
    import traceback
    traceback.print_exc()

# PHASE M (PART 4/5) — public marketing endpoints (NO auth, aggregated +
# anonymized only, 60s cache, per-IP rate limit): /api/public/stats,
# /api/changelog, /changelog.rss. Also starts the 10-minute stats history
# sampler that builds the /stats growth chart. Additive — no bot behavior
# change.
try:
    from utils.public_api import init_public_api
    init_public_api(app)
except Exception as e:
    logger.error(f"❌ Public API registration failed: {e}")
    import traceback
    traceback.print_exc()


@app.route('/')
def home():
    return f"""<!doctype html>
<html><head><title>Aurelia</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 60px; background:#0f0f1a; color:#e0e0e0;">
  <h1 style="font-size: 48px; margin: 0;">Aurelia is online ✦</h1>
  <p style="color:#888;">uptime since {start_time.isoformat()}</p>
  <p style="color:#666;">{datetime.utcnow().isoformat()} UTC</p>
</body></html>"""


@app.route('/health')
def health():
    """FIX 1 — Enhanced /health endpoint with full bot metrics."""
    import keep_alive as kl

    uptime_seconds = 0
    if kl.start_time:
        delta = datetime.utcnow() - kl.start_time
        uptime_seconds = int(delta.total_seconds())

    def fmt_uptime(s):
        d = s // 86400
        h = (s % 86400) // 3600
        m = (s % 3600) // 60
        return f"{d}d {h}h {m}m"

    b = kl.bot_ref

    # Read AI call metrics from keep_alive tracking vars
    ai_calls = getattr(kl, 'total_ai_calls', 0)
    response_times = getattr(kl, 'recent_response_times', [])
    avg_response = (
        sum(response_times) / len(response_times)
        if response_times else 0.0
    )

    # Read Supabase status
    using_supabase = False
    try:
        from utils.db import using_supabase as _us
        using_supabase = _us()
    except Exception:
        pass

    if b is None or not getattr(b, 'is_ready', lambda: False)():
        return jsonify({
            "status": "starting",
            "uptime_seconds": uptime_seconds,
            "uptime_human": fmt_uptime(uptime_seconds),
            "guilds": 0,
            "users": 0,
            "latency_ms": 0,
            "ai_calls_total": ai_calls,
            "avg_response_ms": round(avg_response, 1),
            "active_cogs": 0,
            "using_supabase": using_supabase
        }), 200

    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime_seconds,
        "uptime_human": fmt_uptime(uptime_seconds),
        "guilds": len(b.guilds),
        "users": sum(g.member_count for g in b.guilds),
        "latency_ms": round(b.latency * 1000, 1),
        "ai_calls_total": ai_calls,
        "avg_response_ms": round(avg_response, 1),
        "active_cogs": len(b.cogs),
        "using_supabase": using_supabase
    }), 200


@app.route('/stats')
def stats():
    import keep_alive as kl
    b = kl.bot_ref
    if b is None:
        return jsonify({"status": "starting", "command_counts": {}}), 200
    counts = getattr(b, 'command_counts', {})
    ready = getattr(b, 'is_ready', lambda: False)()
    response_times = getattr(kl, 'recent_response_times', [])
    avg_response = (
        sum(response_times) / len(response_times)
        if response_times else 0.0
    )
    return jsonify({
        "status": "ok" if ready else "starting",
        "guilds": len(b.guilds) if ready else 0,
        "users": sum(g.member_count for g in b.guilds) if ready else 0,
        "latency_ms": round(b.latency * 1000, 2) if ready else 0,
        "uptime_seconds": int((datetime.utcnow() - start_time).total_seconds()),
        "command_counts": counts,
        "ai_calls_total": getattr(kl, 'total_ai_calls', 0),
        "avg_response_ms": round(avg_response, 1)
    }), 200


def run_flask():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    # CRITICAL BUG 2 — Verify all routes are registered on THIS app before starting
    with app.test_client() as client:
        resp = client.get('/health')
        print(f"[Debug] /health route test: {resp.status_code}")
        logger.info(f"[Debug] /health route test: {resp.status_code}")
        if resp.status_code != 200:
            print(f"[Debug] /health route FAILED — routes on app: {[r.rule for r in app.url_map.iter_rules()]}")
            logger.error(f"[Debug] /health route FAILED — routes on app: {[r.rule for r in app.url_map.iter_rules()]}")
    t = Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("🌐 Keep-alive server started on port 8080")


intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.presences = True


# ==================== Data Directory and Files ====================
# Trimmed to only the files needed by active cogs.
# CHANGE 7 — added bot_status.json and autorole.json for re-enabled cogs.
DEFAULT_DATA_FILES = [
    "welcome.json", "logs.json", "afk.json",
    "reminders.json", "notes.json", "todos.json", "warnings.json",
    "snipe.json",
    "moderation.json",
    # per-guild AI moderation role settings
    "settings.json",
    # CHANGE 7 — re-enabled cogs
    "bot_status.json",  # BotStatus cog (custom status persistence)
    "autorole.json",    # AutoRole cog (per-guild autorole config)
    # PHASE 2A — persistent conversation memory (JSON fallback for Supabase)
    "conversation_memory.json",
    # PHASE 2B — per-server personality notes (JSON fallback for Supabase)
    "server_personality.json",
    # PHASE 3 — new cog data files (JSON fallback for Supabase)
    "confess_settings.json",
    "server_rules.json",
    "user_profiles.json",
    "birthdays.json",
    "tempbans.json",
    # CHANGE 2 — prefix settings (JSON fallback for Supabase)
    "prefix_settings.json",
    # Veloura — new cog data files
    "user_levels.json",
    "level_rewards.json",
    "self_role_panels.json",
    "invite_tracking.json",
    # PHASE 4 — new features (AI memory, AI automod, starboard,
    # giveaways, custom commands, proactive, onboarding). JSON
    # fallbacks for Supabase.
    "user_memory.json",
    "ai_automod_settings.json",
    "starboard_settings.json",
    "starboard_posts.json",
    "giveaways.json",
    "custom_commands.json",
    "proactive_settings.json",
    "onboarding_settings.json",
]


def ensure_data_files():
    """Create the /data directory and every default JSON file if missing.
    Runs on import and again in on_ready so it works on cold Render boots."""
    os.makedirs("data", exist_ok=True)
    for fname in DEFAULT_DATA_FILES:
        path = os.path.join("data", fname)
        if not os.path.exists(path):
            try:
                with open(path, "w") as f:
                    json.dump({}, f)
            except Exception as e:
                logger.warning(f"could not create {path}: {e}")


# Run once at import time so files exist before any cog loads
ensure_data_files()


class CynBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=['!'],
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.start_time = start_time
        self.owner_user = None
        # In-memory command usage counter for /stats endpoint
        self.command_counts = {}
        # FIX 2 — sync flag so we only sync on first ready, not on every reconnect
        self.synced = False

    def increment_command(self, name: str):
        """Increment a counter for a command invocation."""
        self.command_counts[name] = self.command_counts.get(name, 0) + 1

    async def setup_hook(self):
        logger.info("Loading cogs...")

        # FIX 3 — Cog Loading Visibility: explicit loader with traceback on failure.
        # Scans /cogs for every .py file, skipping __init__.py and *_disabled.py.
        cogs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cogs')
        if not os.path.isdir(cogs_dir):
            logger.error("cogs/ directory not found")
            return

        for filename in sorted(os.listdir(cogs_dir)):
            if filename.endswith(".py") and not filename.endswith("_disabled.py") and filename != "__init__.py":
                cog_name = filename[:-3]
                try:
                    await self.load_extension(f"cogs.{cog_name}")
                    print(f"✅ Loaded: {filename}")
                    logger.info(f"✅ Loaded: cogs.{cog_name}")
                except Exception as e:
                    import traceback
                    print(f"❌ Failed to load {filename}: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    logger.error(f"❌ Failed to load cogs.{cog_name}: {e}", exc_info=True)

        # PHASE 1 / PART 1 — cache hygiene: prune expired entries every
        # 5 minutes so the TTL store never holds stale rows.
        if not cache_cleanup_task.is_running():
            cache_cleanup_task.start()

        # PHASE 1 / PART 3 — start the batched command-usage flush loop
        # (drains the usage_logger buffer to Supabase every 30 seconds).
        asyncio.create_task(usage_logger.start_periodic_flush())
        logger.info("✅ Cache cleanup task + usage logger started")

        # DASHBOARD (PART 1) — bot-side consumer of dashboard actions.
        # Flask worker threads put live actions (qotd_post_now,
        # welcome_test, giveaway_end, reload_cog, ...) on a thread-safe
        # queue; this coroutine on the bot's event loop polls it every
        # 5 seconds and executes with full bot access.
        try:
            from utils.dashboard_actions import start_dashboard_action_worker
            await start_dashboard_action_worker(self)
        except Exception as e:
            logger.error(f"❌ Dashboard action worker failed to start: {e}")

    async def on_ready(self):
        logger.info(f"🤖 {self.user} is online!")
        logger.info(f"📊 {len(self.guilds)} servers | {len(self.users)} users")
        logger.info("=" * 50)

        # PHASE 1A — Initialize the database (Supabase or JSON fallback)
        try:
            from utils.db import init_db, using_supabase
            init_db()
            if using_supabase():
                logger.info("✅ Database: Supabase connected")
                print("✅ Database: Supabase connected")
            else:
                logger.info("✅ Database: JSON files (Supabase not configured)")
                print("✅ Database: JSON files (Supabase not configured)")
        except Exception as e:
            logger.error(f"❌ Database init failed: {e}")
            print(f"❌ Database init failed: {e}")

        # PHASE 1D — Inject bot ref into keep_alive for /health endpoint
        try:
            import keep_alive as _kl
            _kl.bot_ref = self
            _kl.start_time = datetime.utcnow()
        except Exception:
            pass

        # FIX 5 — make absolutely sure data files exist on every ready
        ensure_data_files()

        # PHASE N — warm up the multi-provider AI router: build provider
        # chains from the env keys, restore today's usage counters from
        # the persistent ai_provider_usage accounting (restart-safe GLM
        # budget) and log a one-line provider summary. Missing optional
        # keys are normal (Groq-only deployments) — never an error.
        try:
            from utils.ai_router import init_ai_router, get_router
            await init_ai_router()
            snap = get_router().status_snapshot()
            providers_line = ", ".join(
                f"{name}:{'on' if p.get('configured') else 'off'}"
                for name, p in snap.get("providers", {}).items()
            )
            print(f"✅ AI router ready ({providers_line}) · status: "
                  f"{snap.get('ai_status')}")
            logger.info(f"✅ AI router ready ({providers_line}) · "
                        f"status: {snap.get('ai_status')}")
        except Exception as e:
            print(f"⚠️ AI router init skipped: {type(e).__name__}: {e}")
            logger.warning(f"AI router init skipped: {e}")

        # PHASE 2 (B1) — One-time legacy warnings migration.
        # If data/moderation.json still exists AND contains actual warnings,
        # import them into the unified utils.db store, then rename the file
        # so this never runs again. (ensure_data_files()/log_action() may
        # recreate an empty moderation.json afterwards — that must NOT
        # re-trigger this.) Migration runs in a thread (blocking Supabase
        # REST calls) and never blocks startup on failure.
        try:
            legacy_path = os.path.join("data", "moderation.json")
            if os.path.exists(legacy_path):
                from scripts.migrate_legacy_warnings import (
                    migrate_legacy_warnings, legacy_warnings_exist,
                )
                if legacy_warnings_exist():
                    result = await asyncio.to_thread(migrate_legacy_warnings)
                    logger.info(
                        f"[MIGRATE] legacy warnings: {result['imported']} imported, "
                        f"{result['skipped']} duplicates skipped"
                    )
                    os.rename(legacy_path, os.path.join("data", "moderation_migrated.json"))
                    logger.info("[MIGRATE] data/moderation.json → data/moderation_migrated.json")
        except Exception as e:
            logger.error(f"[MIGRATE] legacy warnings migration failed: {e}")

        # Fetch owner user object
        if OWNER_ID:
            try:
                self.owner_user = await self.fetch_user(OWNER_ID)
                logger.info(f"👑 Owner: {self.owner_user} ({self.owner_user.id})")
            except Exception as e:
                logger.error(f"❌ Failed to fetch owner: {e}")
                self.owner_user = None
        else:
            logger.warning("⚠️ OWNER_ID not set in env")

        # CRITICAL BUG 1 FIX — Do NOT clear the in-memory tree before syncing.
        # The previous code called clear_commands(guild=None) + sync() which
        # wiped the tree AFTER cogs loaded their commands, then copy_global_to
        # copied nothing → 0 commands synced to every guild.
        #
        # Correct order: cogs load commands into tree during setup_hook (already
        # done by this point). We just copy to each guild and sync per-guild.
        # Do NOT call clear_commands or bare sync() — those wipe the tree.
        if not getattr(self, 'synced', False):
            # PHASE N.1 / PART 12 — canonical command counting (the ONE
            # helper, same numbers everywhere: startup log, /botinfo,
            # public stats, docs surfaces, tests).
            from utils.command_counts import count_commands_runtime, format_command_summary
            counts = count_commands_runtime(self)
            print(f"[Debug] Commands ready to sync: {format_command_summary(counts)}")
            logger.info(
                f"[Debug] Commands ready to sync: "
                f"{format_command_summary(counts)}"
            )

            success = 0
            failed = 0
            for guild in self.guilds:
                try:
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)
                    print(f"✅ Synced {len(synced)} commands to {guild.name}")
                    logger.info(f"✅ Synced {len(synced)} commands to guild: {guild.name}")
                    success += 1
                except Exception as e:
                    print(f"❌ Failed to sync to {guild.name}: {e}")
                    logger.error(f"❌ Failed to sync to {guild.name}: {e}")
                    failed += 1

            self.synced = True
            print(f"Sync complete: {success} success, {failed} failed")
            logger.info(f"Sync complete: {success} success, {failed} failed")

        # Test the AI route + print active cog count + command count.
        # PHASE N — the old Groq-only probe now goes through the router
        # (call_ai_fast -> FAST chain), so it verifies whichever provider
        # chain the environment actually configured and fails over like
        # production traffic. A graceful canned string means every
        # provider failed — logged, never fatal.
        try:
            from utils.ai_handler import call_ai_fast, router_status
            result = await call_ai_fast([
                {"role": "user", "content": "say ok"}
            ])
            from utils.command_counts import (
                count_commands_runtime, format_command_summary,
            )
            counts = count_commands_runtime(self)
            snap = router_status()
            provider_states = ", ".join(
                f"{n}={p.get('state')}"
                for n, p in snap.get("providers", {}).items()
            )
            print(f"✅ AI route working: {result[:50]}")
            print(f"✅ AI providers: {provider_states}")
            print(f"✅ Active cogs loaded: {counts['cogs']}")
            print(f"✅ Commands in tree: {counts['top_level']} groups/commands, "
                  f"{counts['total_invokable']} total invokable")
            logger.info(f"✅ AI route working: {result[:50]}")
            logger.info(f"✅ AI providers: {provider_states}")
            logger.info(f"✅ Active cogs loaded: {counts['cogs']}")
            logger.info(
                f"[STARTUP] Commands in tree: {counts['top_level']} "
                f"groups/commands, {counts['total_invokable']} total invokable"
            )
        except Exception as e:
            print(f"❌ AI route test failed: {type(e).__name__}: {e}")
            logger.error(f"❌ AI route test failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        # NOTE: Status rotation is now owned by cogs/bot_status.py (BotStatus cog).
        # The old change_status task that lived here was removed to avoid duplicate
        # rotation and to let the cog manage custom vs auto status.

    # FIX 6 (part 1) — regular prefix-command error handler
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            try:
                await ctx.send("❌ You don't have permission to do that.")
            except:
                pass
            return
        if isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send(f"❌ Missing argument: `{error.param.name}`")
            except:
                pass
            return
        if isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(f"⏱️ Slow down. Try again in {error.retry_after:.1f}s.")
            except:
                pass
            return
        if isinstance(error, commands.BadArgument):
            try:
                await ctx.send(f"❌ Bad argument: {error}")
            except:
                pass
            return
        logger.error(f"Error in {ctx.command}: {error}", exc_info=error)


bot = CynBot()


# PHASE 1 / PART 1 — prune expired cache entries every 5 minutes.
# cleanup() only touches entries whose TTL already elapsed, so this is
# a cheap pass; it exists so keys for guilds/users that went quiet get
# reclaimed instead of waiting for a random future read.
@tasks.loop(minutes=5)
async def cache_cleanup_task():
    pruned = await cache.cleanup()
    if pruned > 0:
        logger.debug(f"[CACHE] pruned {pruned} expired entries")


@cache_cleanup_task.before_loop
async def before_cache_cleanup():
    await bot.wait_until_ready()


# Sync commands to new guilds when the bot joins them
@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to new guild: {guild.name}")
        logger.info(f"✅ Synced {len(synced)} commands to new guild: {guild.name}")
    except Exception as e:
        print(f"❌ Failed to sync to {guild.name}: {e}")
        logger.error(f"❌ Failed to sync to new guild {guild.name}: {e}")


# IMPROVEMENT 1 — Log every slash command invocation to console for Render logs.
# Fires for every application command interaction (slash commands, button clicks
# on message components, select menus, etc.) before the command runs.
@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Only log application command invocations (not button/select interactions)
    if interaction.type != discord.InteractionType.application_command:
        return
    try:
        guild_name = interaction.guild.name if interaction.guild else "DM"
        if hasattr(interaction.channel, 'name'):
            channel_name = f"#{interaction.channel.name}"
        else:
            channel_name = "DM"
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        cmd_name = interaction.data.get('name', 'unknown') if interaction.data else 'unknown'
        options = interaction.data.get('options', []) if interaction.data else []

        # S4 — Privacy: /confess submissions must stay anonymous. Never log
        # the invoking user's ID or any option values (the confession text)
        # for confess commands — render them as [redacted].
        is_private_cmd = cmd_name.lower() in ("confess",)
        if is_private_cmd:
            user = f"{interaction.user.display_name} ([redacted])"

        # Format options/args
        args_str = ""
        if options:
            args_parts = []
            for opt in options:
                if is_private_cmd:
                    args_parts.append(f"{opt['name']}=[redacted]")
                    continue
                if 'options' in opt:
                    # subcommand group: /parent child arg=val
                    for sub in opt['options']:
                        args_parts.append(f"{sub['name']}={sub.get('value', '')}")
                else:
                    args_parts.append(f"{opt['name']}={opt.get('value', '')}")
            if args_parts:
                args_str = " | " + ", ".join(args_parts)

        logger.info(f"[SLASH] {guild_name} | {channel_name} | {user} → /{cmd_name}{args_str}")
    except Exception as e:
        # Never let logging break the interaction
        logger.error(f"[SLASH LOG ERROR] {type(e).__name__}: {e}")


# FIX 6 (part 2) — global slash-command error handler
#
# PHASE N.1 / PART 7 — DOUBLE-RESPONSE FIX. discord.py 2.7.1 invokes
# BOTH the command-local error handler AND this global tree error
# handler for the same AppCommandError (verified in
# discord/app_commands/tree.py `_call`:
#     await command._invoke_error_handlers(interaction, e)
#     await self.on_error(interaction, e)
# ). The /recap cooldown produced TWO ephemeral replies in production:
# "slow down — try again in 48s." (cogs/recap.py local handler) AND
# "⏱️ Slow down. Try again in 48.9s." (this handler's bare-except →
# followup.send fallback firing after the local handler already
# responded).
#
# Ownership rule: a command with its own @command.error handler OWNS
# the user-facing response for its errors. This global handler only
# speaks when NOBODY has responded yet — `interaction.response.is_done()`
# is checked FIRST in every branch, and the followup fallback is only
# used when the response was NOT already consumed by a local handler.
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    # PHASE N.1 — a local error handler already answered: say nothing
    # (one owner per handled error). Log only.
    if interaction.response.is_done():
        logger.debug(
            f"[app-cmd error] already handled locally: "
            f"{type(error).__name__} for /{getattr(interaction.command, 'name', '?')}"
        )
        return

    async def _reply_once(content: str):
        """Send exactly ONE response: response first, followup fallback
        only if the initial response raced a completion elsewhere."""
        try:
            await interaction.response.send_message(content, ephemeral=True)
        except discord.InteractionResponded:
            # someone responded between the is_done() check and now —
            # do NOT duplicate; drop the message entirely.
            return
        except Exception:
            try:
                await interaction.followup.send(content, ephemeral=True)
            except Exception:
                pass

    if isinstance(error, app_commands.MissingPermissions):
        await _reply_once("❌ You don't have permission to use this command.")
    elif isinstance(error, app_commands.CommandOnCooldown):
        await _reply_once(
            f"⏱️ Slow down. Try again in {error.retry_after:.1f}s."
        )
    elif isinstance(error, app_commands.BotMissingPermissions):
        await _reply_once("❌ I don't have permission to do that here.")
    else:
        await _reply_once(
            f"❌ Something went wrong: {str(error)}{SUPPORT_HINT}"
        )
        raise error


# PHASE 1 / PART 3 — batched command-usage analytics.
# Every completed application command is queued in-memory and flushed
# to the Supabase `command_usage` table in batches of 10 (or every 30s
# by the periodic flush started in setup_hook). Fire-and-forget: usage
# logging can never break or delay a command. Also feeds the in-memory
# per-command counters used by the /stats endpoint.
@bot.event
async def on_app_command_completion(
    interaction: discord.Interaction,
    command: app_commands.Command,
):
    try:
        bot.increment_command(command.qualified_name)
        asyncio.create_task(usage_logger.log(
            guild_id=str(interaction.guild_id) if interaction.guild_id else "dm",
            user_id=str(interaction.user.id),
            command_name=command.qualified_name,
        ))
    except Exception:
        pass  # never let logging break a command


# ==================== CORE SLASH COMMANDS (kept in main for compatibility) ====================

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    bot.increment_command('ping')
    latency = round(bot.latency * 1000)
    color = (
        discord.Color.green() if latency < 100
        else discord.Color.orange() if latency < 200
        else discord.Color.red()
    )
    embed = discord.Embed(
        title="🏓 Pong",
        description=f"Websocket latency: **{latency}ms**",
        color=color
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="uptime", description="Check bot uptime")
async def uptime(ctx):
    bot.increment_command('uptime')
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    embed = discord.Embed(
        description=f"Running for **{days}d {hours}h {minutes}m {seconds}s**",
        color=0x2b2d31
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="botinfo", description="Show bot information")
# FIX 3 (live) — /botinfo was public. It exposes infrastructure details
# (cache stats, storage backend, latency), which only server staff need.
# Verified against discord.py 2.7.1: app_commands.checks gate the slash
# path, commands.checks gate the prefix path — BOTH are needed so regular
# members can't run it either way.
@commands.has_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def botinfo(ctx):
    bot.increment_command('botinfo')
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    uptime_str = f"{days}d {hours}h {minutes}m"

    import sys
    import discord as _discord

    # PHASE 1 / PART 8 — cache stats + storage health.
    cache_stats = cache.stats()
    try:
        from utils.db import using_supabase, supabase_degraded
        if supabase_degraded():
            storage_str = "Supabase (degraded)"
        elif using_supabase():
            storage_str = "Supabase"
        else:
            storage_str = "JSON files"
    except Exception:
        storage_str = "JSON files"

    # PHASE N.1 / PART 12 — canonical command counts (same helper as
    # the startup log, public stats and the docs surfaces).
    try:
        from utils.command_counts import (
            count_commands_runtime, format_command_summary,
        )
        counts_str = format_command_summary(count_commands_runtime(bot))
    except Exception:
        counts_str = "command counts unavailable"

    # FIX 3 (live) — sleek, minimalist system-status card. The old embed
    # had 12 noisy emoji fields; the new one is three clean rows.
    embed = discord.Embed(title="✦ aurelia — system status", color=0x2b2d31)
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.add_field(
        name="Overview",
        value=(
            f"Servers: {len(bot.guilds):,} · "
            f"Members: {sum(g.member_count for g in bot.guilds):,} · "
            f"Latency: {round(bot.latency * 1000)}ms · "
            f"Uptime: {uptime_str}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Cache & Storage",
        value=(
            f"Cache: {cache_stats['size']} entries "
            f"({cache_stats['hit_rate']}% hit rate) · "
            f"Database: {storage_str}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Engine",
        value=(
            f"Python {sys.version_info.major}.{sys.version_info.minor} · "
            f"discord.py {_discord.__version__} · "
            f"multi-provider AI (Gemini · Mistral · GLM · Groq failover)"
        ),
        inline=False,
    )
    embed.add_field(name="Commands", value=counts_str, inline=False)
    embed.set_footer(text="aurelia — built by volc")
    await ctx.send(embed=embed)


# FIX 5 — start_with_retry: exponential backoff if Discord rate-limits us
# (HTTP 429 / Cloudflare 1015). Without this, the bot would retry too fast
# and get banned longer, eventually getting IP-banned by Cloudflare.
async def start_with_retry(bot_instance, token: str, max_retries: int = 5):
    """Start the bot with exponential backoff on rate-limit errors.

    On 429 / 1015 errors we wait `delay` seconds (starting at 30s, doubling
    each retry, capped at 600s = 10 min) before retrying. Other exceptions
    are re-raised immediately so we don't silently swallow real bugs.
    """
    delay = 30  # start with 30 seconds
    for attempt in range(max_retries):
        try:
            await bot_instance.start(token)
            # bot.start only returns when the bot shuts down cleanly
            return
        except discord.HTTPException as e:
            error_str = str(e)
            if e.status == 429 or "1015" in error_str:
                logger.warning(
                    f"Rate limited by Discord (attempt {attempt + 1}/{max_retries}). "
                    f"Waiting {delay}s before retry."
                )
                print(f"⚠️ Rate limited. Waiting {delay}s before retry "
                      f"({attempt + 1}/{max_retries}).")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 600)  # cap at 10 minutes
            else:
                raise
        except Exception as e:
            error_str = str(e)
            # Cloudflare 1015 errors sometimes come through as generic
            # ConnectionErrors rather than HTTPException — catch those too.
            if "1015" in error_str or "429" in error_str:
                logger.warning(
                    f"Connection rate-limited (attempt {attempt + 1}/{max_retries}). "
                    f"Waiting {delay}s before retry."
                )
                print(f"⚠️ Connection rate-limited. Waiting {delay}s "
                      f"({attempt + 1}/{max_retries}).")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 600)
            else:
                raise
    logger.error(f"❌ Bot failed to start after {max_retries} retries.")
    print(f"❌ Bot failed to start after {max_retries} retries.")


if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN not found!")
        exit(1)

    keep_alive()

    try:
        asyncio.run(start_with_retry(bot, token))
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        import traceback
        traceback.print_exc()
