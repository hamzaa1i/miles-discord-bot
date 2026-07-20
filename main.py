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

# Owner ID from env (used everywhere)
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Global start_time — set before bot starts
start_time = datetime.utcnow()

# FIX 1 — Single Flask app. keep_alive.py no longer creates its own Flask app;
# it only stores tracking variables (bot_ref, start_time, total_ai_calls, etc.)
# that this app's /health route reads.
app = Flask(__name__)
bot = None  # set after bot is created


@app.route('/')
def home():
    return f"""<!doctype html>
<html><head><title>cyn</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 60px; background:#0f0f1a; color:#e0e0e0;">
  <h1 style="font-size: 48px; margin: 0;">cyn is online ✅</h1>
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
            # Debug: count commands in tree BEFORE sync to confirm non-zero
            all_cmds = list(self.tree.get_commands())
            total = sum(
                len(g.commands) if hasattr(g, 'commands') else 1
                for g in all_cmds
            )
            print(f"[Debug] Commands ready to sync: {len(all_cmds)} groups/commands, {total} total")
            logger.info(f"[Debug] Commands ready to sync: {len(all_cmds)} groups/commands, {total} total")

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

        # Test Groq API + print active cog count
        try:
            from utils.ai_handler import call_ai_fast
            result = await call_ai_fast([
                {"role": "user", "content": "say ok"}
            ])
            active_cogs = len(self.cogs)
            print(f"✅ Groq API working: {result[:50]}")
            print(f"✅ Active cogs loaded: {active_cogs}")
            logger.info(f"✅ Groq API working: {result[:50]}")
            logger.info(f"✅ Active cogs loaded: {active_cogs}")
        except Exception as e:
            print(f"❌ Groq API failed: {type(e).__name__}: {e}")
            logger.error(f"❌ Groq API failed: {type(e).__name__}: {e}")

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

        # Format options/args
        args_str = ""
        if options:
            args_parts = []
            for opt in options:
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
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.MissingPermissions):
        try:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        except:
            try:
                await interaction.followup.send(
                    "❌ You don't have permission to use this command.",
                    ephemeral=True
                )
            except:
                pass
    elif isinstance(error, app_commands.CommandOnCooldown):
        try:
            await interaction.response.send_message(
                f"⏱️ Slow down. Try again in {error.retry_after:.1f}s.",
                ephemeral=True
            )
        except:
            try:
                await interaction.followup.send(
                    f"⏱️ Slow down. Try again in {error.retry_after:.1f}s.",
                    ephemeral=True
                )
            except:
                pass
    elif isinstance(error, app_commands.BotMissingPermissions):
        try:
            await interaction.response.send_message(
                "❌ I don't have permission to do that here.",
                ephemeral=True
            )
        except:
            try:
                await interaction.followup.send(
                    "❌ I don't have permission to do that here.",
                    ephemeral=True
                )
            except:
                pass
    else:
        try:
            await interaction.response.send_message(
                f"❌ Something went wrong: {str(error)}",
                ephemeral=True
            )
        except:
            try:
                await interaction.followup.send(
                    f"❌ Something went wrong: {str(error)}",
                    ephemeral=True
                )
            except:
                pass
        raise error


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
async def botinfo(ctx):
    bot.increment_command('botinfo')
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    import sys
    import discord as _discord
    owner_str = str(bot.owner_user) if bot.owner_user else "volc"

    embed = discord.Embed(title="cyn", color=0x2b2d31)
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.add_field(name="Owner", value=owner_str, inline=True)
    embed.add_field(name="Servers", value=f"{len(bot.guilds):,}", inline=True)
    embed.add_field(name="Users", value=f"{sum(g.member_count for g in bot.guilds):,}", inline=True)
    embed.add_field(name="Cogs", value=f"{len(bot.cogs)}", inline=True)
    embed.add_field(name="Commands", value=f"{len(bot.tree.get_commands())}", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="discord.py", value=_discord.__version__, inline=True)
    embed.add_field(name="Python", value=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", inline=True)
    embed.add_field(name="Uptime", value=uptime_str, inline=True)
    embed.set_footer(text="cyn — built by volc")
    await ctx.send(embed=embed)


if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN not found!")
        exit(1)

    keep_alive()

    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
