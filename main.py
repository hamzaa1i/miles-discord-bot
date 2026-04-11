import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask, jsonify
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

# Bot configuration
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.presences = True

class Miles(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=['!', 'm!'],
            intents=intents,
            help_command=None,
            case_insensitive=True,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="you grow 🌱 | /help"
            )
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
            'cogs.moderation',        # NEW
            'cogs.welcome',           # NEW
            'cogs.leveling',          # NEW
            'cogs.games',             # NEW
            'cogs.enhanced_shop',     # NEW
            'cogs.server_stats',      # NEW
            'cogs.bot_status',         # NEW
            'cogs.custom_embeds',     # NEW
            'cogs.modmail'            # NEW
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
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Slow down! Try again in {error.retry_after:.1f}s")
        else:
            logger.error(f"Error in command {ctx.command}: {error}")
            await ctx.send(f"❌ Something went wrong: {str(error)}")

# Create bot instance
bot = Miles()

# ------------------------------------------------------------------
# Keep-alive web server for Render (so bot stays alive 24/7)
# ------------------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "🤖 Miles is online and running!"

@app.route('/health')
def health():
    return jsonify({
        "status": "online",
        "bot": str(bot.user) if bot.is_ready() else "starting...",
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "uptime": str(datetime.utcnow() - bot.start_time) if bot.is_ready() else "unknown"
    })

def run_web():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    """Start the Flask web server in a background thread"""
    t = Thread(target=run_web, daemon=True)
    t.start()
    logger.info("🌐 Keep-alive web server started on port 8080")
# ------------------------------------------------------------------

# Custom help command with embeds
@bot.hybrid_command(name="help", description="Display all available commands")
async def help_command(ctx):
    """Professional help command"""
    embed = discord.Embed(
        title="Ao - Command Center",
        description="Your server's backbone",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    
    # Economy Commands
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
            "`@Miles <message>` Natural conversation\n"
            "`/chat <message>` AI chat\n"
            "`/ask <question>` Ask questions\n"
            "`/quote` Inspirational quote\n"
            "`/clear_chat` Clear conversation history"
        ),
        inline=False
    )
    
    # Moderation
    embed.add_field(
        name="Moderation",
        value=(
            "`/kick <user> [reason]` Kick member\n"
            "`/ban <user> [reason]` Ban member\n"
            "`/unban <user_id>` Unban user\n"
            "`/timeout <user> <duration>` Timeout member\n"
            "`/warn <user> <reason>` Warn member\n"
            "`/purge <amount>` Delete messages\n"
            "`/modlogs [limit]` View logs"
        ),
        inline=False
    )
    
    # Leveling
    embed.add_field(
        name="Leveling",
        value=(
            "`/level [user]` Check level\n"
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
    
    # Utility
    embed.add_field(
        name="Utility",
        value=(
            "`/ping` Bot latency\n"
            "`/uptime` Bot uptime\n"
            "`/serverstats` Server statistics\n"
            "`/userinfo [user]` User information\n"
            "`/welcome_setup` Configure welcome messages"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)
    """Beautiful help command with categories"""
    embed = discord.Embed(
        title="🤖 Miles - Command Center",
        description="Your personal AI companion & productivity assistant",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    
    # Economy Commands
    embed.add_field(
        name="💰 Economy",
        value=(
            "`/balance` - Check your balance\n"
            "`/daily` - Claim daily reward\n"
            "`/work` - Work for coins\n"
            "`/shop` - View the shop\n"
            "`/buy <item>` - Purchase item\n"
            "`/inventory` - View your items\n"
            "`/pay <user> <amount>` - Send coins\n"
            "`/gamble <amount>` - Take a risk!"
        ),
        inline=False
    )
    
    # Leaderboard & Ranking
    embed.add_field(
        name="🏆 Rankings",
        value=(
            "`/leaderboard` - Top users by coins\n"
            "`/rank` - Your current rank\n"
            "`/stats` - Detailed statistics"
        ),
        inline=False
    )
    
    # AI & Chat
    embed.add_field(
        name="🧠 AI Features",
        value=(
            "`/chat <message>` - Talk to AI\n"
            "`/quote` - Get inspired\n"
            "`/8ball <question>` - Ask the magic 8-ball\n"
            "`/roast <user>` - Friendly roast (AI)"
        ),
        inline=False
    )
    
    # Productivity
    embed.add_field(
        name="📝 Productivity",
        value=(
            "`/remind <time> <task>` - Set reminder\n"
            "`/note <text>` - Save a note\n"
            "`/notes` - View all notes\n"
            "`/mood <emoji>` - Track your mood\n"
            "`/todo add <task>` - Add to todo list\n"
            "`/todo list` - View todos"
        ),
        inline=False
    )
    
    # Fun Commands
    embed.add_field(
        name="🎮 Fun",
        value=(
            "`/roll [sides]` - Roll dice\n"
            "`/flip` - Flip a coin\n"
            "`/meme` - Random meme\n"
            "`/rps <choice>` - Rock Paper Scissors\n"
            "`/trivia` - Random trivia question"
        ),
        inline=False
    )
    
    # Music & Status
    embed.add_field(
        name="🎵 Music",
        value=(
            "`/music` - Your Spotify status\n"
            "`/nowplaying` - What's playing now"
        ),
        inline=False
    )
    
    # Utility
    embed.add_field(
        name="⚙️ Utility",
        value=(
            "`/ping` - Bot latency\n"
            "`/uptime` - How long I've been running\n"
            "`/avatar [user]` - Show avatar\n"
            "`/serverinfo` - Server information"
        ),
        inline=False
    )
    
    # Moderation Commands (NEW)
    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`/kick <user> [reason]` - Kick a member\n"
            "`/ban <user> [reason]` - Ban a member\n"
            "`/unban <user_id>` - Unban a user\n"
            "`/timeout <user> <time>` - Timeout member\n"
            "`/untimeout <user>` - Remove timeout\n"
            "`/warn <user> <reason>` - Warn a member\n"
            "`/purge <amount>` - Delete messages\n"
            "`/modlogs [limit]` - View mod logs"
        ),
        inline=False
    )
    
    # Welcome System (NEW)
    embed.add_field(
        name="👋 Welcome",
        value=(
            "`/welcome_setup` - Configure welcome\n"
            "`/welcome_test` - Test welcome message\n"
            "`/goodbye_toggle` - Toggle goodbye msgs"
        ),
        inline=False
    )
    
    # Leveling (NEW)
    embed.add_field(
        name="⭐ Leveling",
        value=(
            "`/level [user]` - Check level\n"
            "`/leaderboard_levels` - Level leaderboard"
        ),
        inline=False
    )
    
    # Games (NEW)
    embed.add_field(
        name="🎮 Games",
        value=(
            "`/trivia` - Trivia question\n"
            "`/guess <bet>` - Guess the number\n"
            "`/slots <bet>` - Slot machine\n"
            "`/blackjack <bet>` - Play blackjack\n"
            "`/roulette <bet> <choice>` - Roulette"
        ),
        inline=False
    )
    
    # Enhanced Shop (NEW)
    embed.add_field(
        name="🛒 Enhanced Shop",
        value=(
            "`/shop_view [category]` - View shop\n"
            "`/buy_item <item>` - Purchase item\n"
            "`/use_item <item>` - Use an item"
        ),
        inline=False
    )
    
    # Server Stats (NEW)
    embed.add_field(
        name="📊 Server Stats",
        value=(
            "`/serverstats` - Server statistics\n"
            "`/userinfo [user]` - User information\n"
            "`/roleinfo <role>` - Role information\n"
            "`/channelinfo [channel]` - Channel info"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# Basic utility commands
@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    """Check bot response time"""
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=discord.Color.green() if latency < 100 else discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="uptime", description="Check how long bot has been running")
async def uptime(ctx):
    """Show bot uptime"""
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    
    embed = discord.Embed(
        title="⏰ Bot Uptime",
        description=f"I've been running for:\n**{days}d {hours}h {minutes}m {seconds}s**",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Show user avatar")
async def avatar(ctx, user: discord.Member = None):
    """Display user's avatar"""
    user = user or ctx.author
    
    embed = discord.Embed(
        title=f"{user.name}'s Avatar",
        color=user.color
    )
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Show server information")
async def serverinfo(ctx):
    """Display server statistics"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="😃 Emojis", value=len(guild.emojis), inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    # Start the keep-alive web server (so Render/UptimeRobot can ping it)
    keep_alive()
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")