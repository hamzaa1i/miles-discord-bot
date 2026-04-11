import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask
from threading import Thread

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Miles')

# Keep-alive web server
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

@app.route('/health')
def health():
    return {
        "status": "online",
        "bot": str(bot.user) if bot.is_ready() else "starting...",
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "uptime": str(datetime.utcnow() - bot.start_time) if bot.is_ready() else "0"
    }

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("🌐 Keep-alive web server started on port 8080")

# Bot configuration
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.presences = True

class Miles(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=['!'],
            intents=intents,
            help_command=None,
            case_insensitive=True
            # No activity here - bot_status.py handles this
        )
        self.start_time = datetime.utcnow()

    async def setup_hook(self):
        """Load all cogs when bot starts"""
        logger.info("Loading cogs...")

        cogs = [
            'cogs.economy',
            'cogs.fun',
            'cogs.ai_chat',
            'cogs.productivity',
            'cogs.leaderboard',
            'cogs.music',
            'cogs.moderation',
            'cogs.welcome',
            'cogs.leveling',
            'cogs.games',
            'cogs.enhanced_shop',
            'cogs.server_stats',
            'cogs.bot_status',
            'cogs.custom_embeds',
            'cogs.modmail'
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Loaded: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load {cog}: {e}")

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"🤖 {self.user} is now online!")
        logger.info(f"📊 Connected to {len(self.guilds)} servers")
        logger.info(f"👥 Serving {len(self.users)} users")
        logger.info("=" * 50)

    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send(f"Missing argument: `{error.param.name}`")
            except:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(f"Slow down! Try again in {error.retry_after:.1f}s")
            except:
                pass
        else:
            logger.error(f"Error in command {ctx.command}: {error}")
            if hasattr(ctx, 'interaction') and ctx.interaction:
                if not ctx.interaction.response.is_done():
                    try:
                        await ctx.send(f"Something went wrong: {str(error)}")
                    except:
                        pass

# Create bot instance
bot = Miles()

# Help command
@bot.hybrid_command(name="help", description="Display all available commands")
async def help_command(ctx):
    """Help command"""
    embed = discord.Embed(
        title="ao — Command Center",
        description="Your server's multi-purpose companion",
        color=0x1a1a2e,
        timestamp=datetime.utcnow()
    )

    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(
        text=f"Requested by {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    # Economy
    embed.add_field(
        name="Economy",
        value=(
            "`/balance` Check your balance\n"
            "`/daily` Claim daily reward\n"
            "`/work` Work for coins\n"
            "`/shop` View the shop\n"
            "`/buy <item>` Purchase item\n"
            "`/inventory` View your items\n"
            "`/pay <user> <amount>` Send coins\n"
            "`/gamble <amount>` Gamble coins"
        ),
        inline=False
    )

    # Rankings
    embed.add_field(
        name="Rankings",
        value=(
            "`/leaderboard` Top users by coins\n"
            "`/rank` Your current rank\n"
            "`/stats` Detailed statistics"
        ),
        inline=False
    )

    # AI Features
    embed.add_field(
        name="AI Features",
        value=(
            "`@ao <message>` Natural conversation\n"
            "`/chat <message>` AI chat\n"
            "`/ask <question>` Ask questions\n"
            "`/quote` Dark quote\n"
            "`/roast <user>` Dark roast\n"
            "`/clear_chat` Clear conversation"
        ),
        inline=False
    )

    # Moderation
    embed.add_field(
        name="Moderation",
        value=(
            "`/kick <user>` Kick member\n"
            "`/ban <user>` Ban member\n"
            "`/unban <id>` Unban user\n"
            "`/timeout <user> <time>` Timeout member\n"
            "`/warn <user> <reason>` Warn member\n"
            "`/purge <amount>` Delete messages\n"
            "`/modlogs` View mod logs"
        ),
        inline=False
    )

    # Leveling
    embed.add_field(
        name="Leveling",
        value=(
            "`/level` Check your level\n"
            "`/leaderboard_levels` Level rankings"
        ),
        inline=False
    )

    # Games
    embed.add_field(
        name="Games",
        value=(
            "`/trivia` Trivia question\n"
            "`/guess <bet>` Number guessing\n"
            "`/slots <bet>` Slot machine\n"
            "`/blackjack <bet>` Blackjack\n"
            "`/roulette <bet> <choice>` Roulette"
        ),
        inline=False
    )

    # Fun
    embed.add_field(
        name="Fun",
        value=(
            "`/roll [sides]` Roll dice\n"
            "`/flip` Flip a coin\n"
            "`/8ball <question>` Magic 8-ball\n"
            "`/rps <choice>` Rock Paper Scissors\n"
            "`/meme` Random meme"
        ),
        inline=False
    )

    # Embeds
    embed.add_field(
        name="Custom Embeds",
        value=(
            "`/embed` Create a simple embed\n"
            "`/embed_advanced` Full embed builder\n"
            "`/embed_save` Save a template\n"
            "`/embed_use` Use saved template\n"
            "`/embed_list` List templates\n"
            "`/embed_delete` Delete template"
        ),
        inline=False
    )

    # ModMail & DMs
    embed.add_field(
        name="ModMail & DMs",
        value=(
            "`/modmail_setup` Setup modmail\n"
            "`/modmail_toggle` Enable/disable\n"
            "`/dm <user> <msg>` DM a user\n"
            "`/announce <msg>` Mass DM members"
        ),
        inline=False
    )

    # Welcome
    embed.add_field(
        name="Welcome",
        value=(
            "`/welcome_setup` Configure welcome\n"
            "`/welcome_test` Test welcome message\n"
            "`/goodbye_toggle` Toggle goodbye"
        ),
        inline=False
    )

    # Server Stats
    embed.add_field(
        name="Server Info",
        value=(
            "`/serverstats` Server statistics\n"
            "`/userinfo [user]` User information\n"
            "`/roleinfo <role>` Role information\n"
            "`/channelinfo` Channel info"
        ),
        inline=False
    )

    # Status
    embed.add_field(
        name="Bot Status",
        value=(
            "`/setstatus` Set custom status\n"
            "`/resetstatus` Resume rotation\n"
            "`/addstatus` Add to rotation\n"
            "`/liststatus` View all statuses"
        ),
        inline=False
    )

    # Utility
    embed.add_field(
        name="Utility",
        value=(
            "`/ping` Bot latency\n"
            "`/uptime` Bot uptime\n"
            "`/avatar [user]` Show avatar\n"
            "`/serverinfo` Server info\n"
            "`/music` Spotify status\n"
            "`/remind <time> <task>` Set reminder\n"
            "`/note <text>` Save note\n"
            "`/notes` View notes\n"
            "`/mood <emoji>` Log mood"
        ),
        inline=False
    )

    await ctx.send(embed=embed)

# Ping command
@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="Pong!",
        description=f"Latency: **{latency}ms**",
        color=0x1a1a2e
    )
    await ctx.send(embed=embed)

# Uptime command
@bot.hybrid_command(name="uptime", description="Check how long bot has been running")
async def uptime(ctx):
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    embed = discord.Embed(
        title="Uptime",
        description=f"**{days}d {hours}h {minutes}m {seconds}s**",
        color=0x1a1a2e
    )
    await ctx.send(embed=embed)

# Avatar command
@bot.hybrid_command(name="avatar", description="Show user avatar")
async def avatar(ctx, user: discord.Member = None):
    user = user or ctx.author
    embed = discord.Embed(
        title=f"{user.name}'s Avatar",
        color=0x1a1a2e
    )
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await ctx.send(embed=embed)

# Server info command
@bot.hybrid_command(name="serverinfo", description="Show server information")
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(
        title=guild.name,
        color=0x1a1a2e,
        timestamp=datetime.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)

    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN not found in environment variables!")
        exit(1)

    keep_alive()

    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")