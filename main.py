import discord
from discord.ext import commands
import os
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
logger = logging.getLogger('ao')

# Keep-alive
app = Flask('')

@app.route('/')
def home():
    return "ao is online."

@app.route('/health')
def health():
    return {
        "status": "online",
        "bot": str(bot.user) if bot.is_ready() else "starting",
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "uptime": str(datetime.utcnow() - bot.start_time) if bot.is_ready() else "0"
    }

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

class AoBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=['!'],
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.start_time = datetime.utcnow()

    async def setup_hook(self):
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
            'cogs.server_stats',
            'cogs.bot_status',
            'cogs.custom_embeds',
            'cogs.modmail',
            'cogs.autorole',
            'cogs.polls',
            'cogs.afk',
            'cogs.giveaway',
            'cogs.server_logs',
            'cogs.reaction_roles',
            'cogs.automod',
            'cogs.owner'
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Loaded: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load {cog}: {e}")

        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"❌ Failed to sync: {e}")

    async def on_ready(self):
        logger.info(f"🤖 {self.user} is online!")
        logger.info(f"📊 {len(self.guilds)} servers | {len(self.users)} users")
        logger.info("=" * 50)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send(f"Missing argument: `{error.param.name}`")
            except:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(
                    f"Slow down. Try again in {error.retry_after:.1f}s",
                    ephemeral=True
                )
            except:
                pass
        else:
            logger.error(f"Error in {ctx.command}: {error}")

bot = AoBot()

# ==================== HELP COMMAND ====================

@bot.hybrid_command(name="help", description="Show all commands")
@discord.app_commands.describe(category="Filter by category")
@discord.app_commands.choices(category=[
    discord.app_commands.Choice(name="💰 Economy", value="economy"),
    discord.app_commands.Choice(name="🎮 Fun", value="fun"),
    discord.app_commands.Choice(name="🧠 AI", value="ai"),
    discord.app_commands.Choice(name="⭐ Leveling", value="leveling"),
    discord.app_commands.Choice(name="🛡️ Moderation", value="moderation"),
    discord.app_commands.Choice(name="📊 Server", value="server"),
    discord.app_commands.Choice(name="🔧 AutoMod", value="automod"),
    discord.app_commands.Choice(name="📝 Productivity", value="productivity"),
    discord.app_commands.Choice(name="🎉 Events", value="events"),
    discord.app_commands.Choice(name="⚙️ Utility", value="utility"),
])
async def help_command(ctx, category: str = None):
    """Dynamic help command with categories"""

    all_categories = {
        "economy": {
            "name": "💰 Economy",
            "desc": "Earn, spend and manage your coins",
            "commands": [
                ("/balance [user]", "Check wallet & bank balance"),
                ("/daily", "Claim daily reward + streak bonus"),
                ("/work", "Work to earn coins (1h cooldown)"),
                ("/deposit <amount|all>", "Deposit to bank"),
                ("/withdraw <amount|all>", "Withdraw from bank"),
                ("/pay <user> <amount>", "Send coins to someone"),
                ("/shop", "Browse the item shop"),
                ("/buy <item>", "Purchase an item"),
                ("/inventory", "View your items"),
                ("/use <item>", "Use an item"),
                ("/rob <user>", "Attempt to rob someone"),
                ("/baltop", "Richest users leaderboard"),
                ("/setmoney <user> <amount>", "Set user balance (Admin)"),
                ("/addmoney <user> <amount>", "Add coins to user (Admin)"),
                ("/removemoney <user> <amount>", "Remove coins from user (Admin)"),
                ("/reseteconomy <user>", "Reset user economy (Admin)"),
                ("/fish", "Go fishing for coins"),
                ("/hunt", "Go hunting for coins"),
                ("/mine", "Mine for coins and gems"),
                ("/beg", "Beg for coins"),
                ("/crime", "Attempt a crime for coins"),
                ("/profile [user]", "View economy profile"),
                ("/streak", "Check your daily streak"),
                ("/richest", "Top 10 richest users"),
            ]
        },
        "fun": {
            "name": "🎮 Fun",
            "desc": "Fun commands to entertain your server",
            "commands": [
                ("/roll [sides]", "Roll a dice"),
                ("/flip", "Flip a coin"),
                ("/8ball <question>", "Ask the magic 8-ball"),
                ("/rps <choice>", "Rock Paper Scissors"),
                ("/meme", "Random meme"),
                ("/joke", "Random dark joke"),
                ("/fact", "Random interesting fact"),
                ("/ship <user1> <user2>", "Ship two users"),
                ("/rate <thing>", "Rate anything out of 10"),
                ("/reverse <text>", "Reverse text"),
                ("/mock <text>", "Mock someone's text"),
                ("/choose <option1> <option2>", "Bot chooses for you"),
                ("/topic", "Random conversation topic"),
                ("/would <option1> <option2>", "Would you rather"),
            ]
        },
        "ai": {
            "name": "🧠 AI Features",
            "desc": "AI-powered commands",
            "commands": [
                ("@ao <message>", "Chat naturally with ao"),
                ("/chat <message>", "AI conversation"),
                ("/ask <question>", "Ask ao anything"),
                ("/quote", "Dark quote of the moment"),
                ("/roast <user>", "Dark friendly roast"),
                ("/clear_chat", "Reset conversation memory"),
            ]
        },
        "leveling": {
            "name": "⭐ Leveling",
            "desc": "MEE6-style XP and leveling system",
            "commands": [
                ("/level [user]", "Check level and XP progress"),
                ("/leaderboard_levels", "XP leaderboard"),
                ("/level_setup <channel>", "Set level-up channel (Admin)"),
                ("/level_role <level> <role>", "Set level reward role (Admin)"),
                ("/level_ignore <channel>", "Ignore channel from XP (Admin)"),
                ("/level_config", "View leveling config"),
                ("/give_xp <user> <amount>", "Give XP to user (Admin)"),
                ("/remove_xp <user> <amount>", "Remove XP from user (Admin)"),
                ("/reset_xp <user>", "Reset user XP (Admin)"),
            ]
        },
        "moderation": {
            "name": "🛡️ Moderation",
            "desc": "Server moderation tools",
            "commands": [
                ("/kick <user> [reason]", "Kick a member"),
                ("/ban <user> [reason]", "Ban a member"),
                ("/unban <id>", "Unban a user"),
                ("/timeout <user> <time>", "Timeout a member"),
                ("/untimeout <user>", "Remove timeout"),
                ("/warn <user> <reason>", "Warn a member"),
                ("/modlogs [limit]", "View moderation logs"),
                ("/purge <amount>", "Delete messages"),
                ("/lock [channel]", "Lock a channel"),
                ("/unlock [channel]", "Unlock a channel"),
                ("/slowmode <seconds>", "Set channel slowmode"),
                ("/nick <user> <name>", "Change nickname"),
                ("/role_add <user> <role>", "Add role to user"),
                ("/role_remove <user> <role>", "Remove role from user"),
            ]
        },
        "server": {
            "name": "📊 Server Info",
            "desc": "Server and user information",
            "commands": [
                ("/whois [user]", "Complete user info"),
                ("/serverinfo", "Detailed server info"),
                ("/roleinfo <role>", "Role information"),
                ("/channelinfo [channel]", "Channel information"),
                ("/avatar [user]", "View avatar"),
                ("/banner [user]", "View banner"),
                ("/membercount", "Member count breakdown"),
                ("/inrole <role>", "Members with a role"),
                ("/permissions [user]", "Check permissions"),
                ("/emojis", "List server emojis"),
                ("/roles", "List all roles"),
                ("/firstmessage", "First message in channel"),
                ("/logs_setup <channel>", "Setup server logs (Admin)"),
                ("/logs_toggle <event>", "Toggle log events (Admin)"),
                ("/reactionrole_add", "Add reaction role (Admin)"),
                ("/reactionrole_remove", "Remove reaction role (Admin)"),
                ("/reactionrole_list", "List reaction roles"),
                ("/autorole_add <role>", "Add auto role (Admin)"),
                ("/autorole_list", "View auto roles"),
                ("/welcome_setup", "Configure welcome (Admin)"),
                ("/welcome_test", "Test welcome message"),
            ]
        },
        "automod": {
            "name": "🔧 AutoMod",
            "desc": "Automatic moderation system",
            "commands": [
                ("/antispam", "Configure anti-spam (Admin)"),
                ("/filter_add <word>", "Add word to filter (Admin)"),
                ("/filter_remove <word>", "Remove filtered word (Admin)"),
                ("/filter_list", "View filtered words (Mod)"),
                ("/filter_clear", "Clear all filtered words (Admin)"),
                ("/filter_action <action>", "Set filter action (Admin)"),
                ("/automod_setup <channel>", "Set automod log channel"),
                ("/automod_status", "View automod config"),
            ]
        },
        "productivity": {
            "name": "📝 Productivity",
            "desc": "Personal productivity tools",
            "commands": [
                ("/remind <time> <task>", "Set a reminder"),
                ("/note <text>", "Save a quick note"),
                ("/notes", "View all your notes"),
                ("/note_delete <number>", "Delete a note"),
                ("/mood <emoji>", "Log today's mood"),
                ("/afk [reason]", "Set AFK status"),
                ("/music [user]", "View Spotify status"),
            ]
        },
        "events": {
            "name": "🎉 Events",
            "desc": "Server events and activities",
            "commands": [
                ("/poll <question> [duration]", "Create yes/no poll"),
                ("/multipoll <question>", "Multi-option poll"),
                ("/giveaway <prize> <duration>", "Start a giveaway"),
                ("/modmail_setup <channel>", "Setup modmail (Admin)"),
                ("/modmail_toggle", "Enable/disable modmail (Admin)"),
                ("/dm <user> <message>", "DM a user (Admin)"),
                ("/announce <message>", "Mass DM announcement (Admin)"),
                ("/embed <title> <desc>", "Create embed (Mod)"),
                ("/embed_advanced", "Advanced embed builder (Mod)"),
                ("/embed_save <name>", "Save embed template (Mod)"),
                ("/embed_use <name>", "Use saved template (Mod)"),
            ]
        },
        "utility": {
            "name": "⚙️ Utility",
            "desc": "General utility commands",
            "commands": [
                ("/ping", "Check bot latency"),
                ("/uptime", "Bot uptime"),
                ("/serverinfo", "Server information"),
                ("/avatar [user]", "Show avatar"),
                ("/setstatus", "Set bot status (Admin)"),
                ("/resetstatus", "Reset status rotation (Admin)"),
                ("/addstatus", "Add to status rotation (Admin)"),
                ("/liststatus", "View all statuses"),
            ]
        }
    }

    if category and category in all_categories:
        # Show specific category
        cat = all_categories[category]

        embed = discord.Embed(
            title=cat["name"],
            description=cat["desc"],
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        commands_text = ""
        for cmd, desc in cat["commands"]:
            commands_text += f"`{cmd}`\n{desc}\n\n"

        # Split if too long
        if len(commands_text) > 4096:
            chunks = []
            current = ""
            for cmd, desc in cat["commands"]:
                line = f"`{cmd}`\n{desc}\n\n"
                if len(current) + len(line) > 1024:
                    chunks.append(current)
                    current = line
                else:
                    current += line
            if current:
                chunks.append(current)

            embed.description = cat["desc"]
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"Commands {'' if i == 0 else f'(cont.)'}",
                    value=chunk,
                    inline=False
                )
        else:
            embed.description = cat["desc"] + "\n\n" + commands_text

        embed.set_footer(
            text=f"ao • Use /help to see all categories",
            icon_url=bot.user.avatar.url if bot.user.avatar else None
        )

        await ctx.send(embed=embed)

    else:
        # Show category overview
        embed = discord.Embed(
            title="ao — Command Center",
            description=(
                "Your server's multi-purpose dark companion.\n"
                "Use `/help <category>` to see commands in that category.\n\n"
            ),
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(
            url=bot.user.avatar.url if bot.user.avatar else None
        )

        for key, cat in all_categories.items():
            cmd_count = len(cat["commands"])
            embed.add_field(
                name=cat["name"],
                value=f"{cat['desc']}\n`{cmd_count} commands`",
                inline=True
            )

        total_commands = sum(len(c["commands"]) for c in all_categories.values())

        embed.set_footer(
            text=f"ao • {total_commands} total commands • /help <category> for details",
            icon_url=bot.user.avatar.url if bot.user.avatar else None
        )

        await ctx.send(embed=embed)

# ==================== UTILITY COMMANDS ====================

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    color = (
        discord.Color.green() if latency < 100
        else discord.Color.orange() if latency < 200
        else discord.Color.red()
    )
    embed = discord.Embed(
        description=f"Latency: **{latency}ms**",
        color=color
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="uptime", description="Check bot uptime")
async def uptime(ctx):
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    embed = discord.Embed(
        description=f"Running for **{days}d {hours}h {minutes}m {seconds}s**",
        color=0x1a1a2e
    )
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