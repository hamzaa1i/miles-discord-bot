import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask
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

# Keep-alive Flask app — enhanced with stats + health
app = Flask('')
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
    if bot is None:
        return {"status": "starting", "guilds": 0, "users": 0, "latency_ms": 0,
                "uptime_seconds": (datetime.utcnow() - start_time).total_seconds()}, 200
    user_count = sum(g.member_count for g in bot.guilds) if bot.is_ready() else 0
    return {
        "status": "ok" if bot.is_ready() else "starting",
        "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else 0,
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "users": user_count,
        "uptime_seconds": (datetime.utcnow() - start_time).total_seconds()
    }, 200


@app.route('/stats')
def stats():
    if bot is None:
        return {"status": "starting", "command_counts": {}}, 200
    counts = getattr(bot, 'command_counts', {})
    return {
        "status": "ok" if bot.is_ready() else "starting",
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "users": sum(g.member_count for g in bot.guilds) if bot.is_ready() else 0,
        "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else 0,
        "uptime_seconds": (datetime.utcnow() - start_time).total_seconds(),
        "command_counts": counts
    }, 200


def run_flask():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("🌐 Keep-alive server started on port 8080")


intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.presences = True


# ==================== FIX 5 — Data Directory and Files ====================
DEFAULT_DATA_FILES = [
    "economy.json", "levels.json", "welcome.json", "logs.json",
    "autorespond.json", "reaction_roles.json", "afk.json",
    "reminders.json", "notes.json", "todos.json", "warnings.json",
    "tickets.json", "suggestions.json", "giveaways.json",
    "birthdays.json", "starboard.json", "counting.json",
    "reputation.json", "marriages.json", "polls.json",
    "buttonroles.json", "customcmds.json", "snipe.json",
    # extras that cogs actually use
    "moderation.json", "leveling.json", "level_config.json",
    "server_logs.json", "dm_prefs.json", "giveaway.json",
    "automod.json", "modmail.json", "custom_embeds.json",
    "poll.json", "suggestion.json", "marriage.json",
    "reputation_db.json", "trivia.json",
    # FIX 4 — per-guild AI moderation role settings
    "settings.json",
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

        # Guild-only sync — no global sync (avoids Discord's 100-command global limit).
        # Commands are copied to each guild and synced per-guild (instant, no 1hr wait).
        if not self.synced:
            # Debug: count commands in tree before sync
            all_cmds = self.tree.get_commands()
            cmd_count = 0
            for c in all_cmds:
                if hasattr(c, 'commands'):
                    cmd_count += len(c.commands)
                else:
                    cmd_count += 1
            print(f"[Debug] Commands in tree before sync: {len(all_cmds)} ({cmd_count} total including subcommands)")

            # Do NOT call tree.clear_commands() — it wipes the global commands
            # that copy_global_to needs to copy FROM.

            success_count = 0
            fail_count = 0
            for guild in self.guilds:
                try:
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)
                    print(f"✅ Synced {len(synced)} commands to {guild.name}")
                    logger.info(f"✅ Synced {len(synced)} commands to guild: {guild.name}")
                    success_count += 1
                except Exception as e:
                    print(f"❌ Failed to sync to {guild.name}: {e}")
                    logger.error(f"❌ Failed to sync to guild {guild.name}: {e}")
                    fail_count += 1

            self.synced = True
            print(f"Sync complete: {success_count} success, {fail_count} failed")

        # Test Groq API
        try:
            from utils.ai_handler import call_ai_fast
            result = await call_ai_fast([
                {"role": "user", "content": "say ok"}
            ])
            print(f"✅ Groq API working: {result[:50]}")
            logger.info(f"✅ Groq API working: {result[:50]}")
        except Exception as e:
            print(f"❌ Groq API failed: {type(e).__name__}: {e}")
            logger.error(f"❌ Groq API failed: {type(e).__name__}: {e}")

        # Start cycling status every 5 minutes
        if not self.change_status.is_running():
            self.change_status.start()

    # POLISH 6 — Status Cycling with real live data
    @tasks.loop(minutes=5)
    async def change_status(self):
        """Cycle bot status every 5 minutes using real live guild/user counts."""
        try:
            statuses = [
                discord.Activity(type=discord.ActivityType.watching,
                                 name=f"{len(self.guilds)} servers"),
                discord.Activity(type=discord.ActivityType.listening,
                                 name="@cyn"),
                discord.Activity(type=discord.ActivityType.playing,
                                 name=f"with {sum(g.member_count for g in self.guilds)} users"),
                discord.Activity(type=discord.ActivityType.competing,
                                 name="being the best bot"),
            ]
            idx = self.change_status.current_loop % len(statuses)
            await self.change_presence(activity=statuses[idx])
        except Exception as e:
            logger.error(f"Status cycle error: {e}")

    @change_status.before_loop
    async def before_change_status(self):
        await self.wait_until_ready()

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

        print(f"[SLASH] {guild_name} | {channel_name} | {user} → /{cmd_name}{args_str}")
    except Exception as e:
        # Never let logging break the interaction
        print(f"[SLASH LOG ERROR] {type(e).__name__}: {e}")


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
