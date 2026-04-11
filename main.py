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

# ==================== INTERACTIVE HELP WITH BUTTONS ====================

class HelpView(discord.ui.View):
    def __init__(self, bot, author_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.current_page = "main"

        self.categories = {
            "economy": {
                "emoji": "💰",
                "name": "Economy",
                "desc": "Earn, spend and manage your coins",
                "commands": [
                    ("/balance", "Check wallet & bank"),
                    ("/daily", "Daily reward + streak bonus"),
                    ("/work", "Work for coins (1h cooldown)"),
                    ("/pay <user> <amount>", "Send coins to someone"),
                    ("/shop", "Browse the item shop"),
                    ("/buy <item>", "Purchase an item"),
                    ("/inventory", "View your items"),
                    ("/profile", "Your full economy profile"),
                    ("/richest", "Top 10 richest users"),
                    ("/earn fish", "Go fishing 🎣"),
                    ("/earn hunt", "Go hunting 🔫"),
                    ("/earn mine", "Mine for gems ⛏️"),
                    ("/earn beg", "Beg for coins"),
                    ("/earn crime", "Attempt a crime"),
                    ("/earn rob <user>", "Rob someone"),
                    ("/bank deposit <amount>", "Deposit coins to bank"),
                    ("/bank withdraw <amount>", "Withdraw from bank"),
                    ("/eco_admin set", "Set balance (Admin)"),
                    ("/eco_admin add", "Add coins (Admin)"),
                    ("/eco_admin remove", "Remove coins (Admin)"),
                    ("/eco_admin reset", "Reset user economy (Admin)"),
                ]
            },
            "fun": {
                "emoji": "🎮",
                "name": "Fun",
                "desc": "Entertainment and games",
                "commands": [
                    ("/roll [sides]", "Roll a dice"),
                    ("/flip", "Flip a coin"),
                    ("/8ball <question>", "Ask the magic 8-ball"),
                    ("/rps <choice>", "Rock Paper Scissors"),
                    ("/meme", "Random meme"),
                    ("/joke", "Random dark joke"),
                    ("/fact", "Random interesting fact"),
                    ("/ship <u1> <u2>", "Ship compatibility"),
                    ("/rate <thing>", "Rate anything out of 10"),
                    ("/reverse <text>", "Reverse text"),
                    ("/mock <text>", "Mock text"),
                    ("/choose <a> <b>", "Bot chooses for you"),
                    ("/topic", "Random conversation topic"),
                    ("/would <a> <b>", "Would you rather"),
                    ("/truth [user]", "Truth question"),
                    ("/dare [user]", "Dare challenge"),
                    ("/tod [user]", "Random truth or dare"),
                    ("/trivia", "Trivia question"),
                    ("/trivia_stats", "Your trivia statistics"),
                ]
            },
            "ai": {
                "emoji": "🧠",
                "name": "AI",
                "desc": "AI-powered features",
                "commands": [
                    ("@ao <message>", "Chat naturally with ao"),
                    ("/chat <message>", "AI conversation"),
                    ("/ask <question>", "Ask ao anything"),
                    ("/quote", "Dark quote of the moment"),
                    ("/roast [user]", "Friendly dark roast"),
                    ("/clear_chat", "Reset conversation memory"),
                ]
            },
            "social": {
                "emoji": "💕",
                "name": "Social",
                "desc": "Social and community features",
                "commands": [
                    ("/marry <user>", "Propose to someone"),
                    ("/divorce", "End your marriage"),
                    ("/spouse [user]", "View marriage status"),
                    ("/rep <user>", "Give reputation (+rep)"),
                    ("/repcheck [user]", "Check reputation"),
                    ("/replb", "Reputation leaderboard"),
                    ("/birthday_set <month> <day>", "Set your birthday"),
                    ("/birthday [user]", "Check someone's birthday"),
                    ("/birthdays", "Upcoming birthdays list"),
                    ("/afk [reason]", "Set your AFK status"),
                    ("/toggledms", "Toggle DMs from ao"),
                ]
            },
            "leveling": {
                "emoji": "⭐",
                "name": "Leveling",
                "desc": "MEE6-style XP and leveling system",
                "commands": [
                    ("/level [user]", "Check level and XP progress"),
                    ("/leaderboard_levels", "XP leaderboard"),
                    ("/xp setup <channel>", "Set level-up channel (Admin)"),
                    ("/xp role <level> <role>", "Set level reward role (Admin)"),
                    ("/xp ignore <channel>", "Ignore channel from XP (Admin)"),
                    ("/xp give <user> <amount>", "Give XP to user (Admin)"),
                    ("/xp remove <user> <amount>", "Remove XP (Admin)"),
                    ("/xp reset <user>", "Reset user XP (Admin)"),
                    ("/xp config", "View leveling configuration"),
                ]
            },
            "moderation": {
                "emoji": "🛡️",
                "name": "Moderation",
                "desc": "Server moderation tools",
                "commands": [
                    ("/mod kick <user>", "Kick a member"),
                    ("/mod ban <user>", "Ban a member"),
                    ("/mod unban <id>", "Unban a user"),
                    ("/mod timeout <user> <time>", "Timeout a member"),
                    ("/mod untimeout <user>", "Remove timeout"),
                    ("/mod warn <user> <reason>", "Warn a member"),
                    ("/mod purge <amount>", "Delete messages"),
                    ("/mod logs", "View moderation logs"),
                    ("/lock [channel]", "Lock a channel"),
                    ("/unlock [channel]", "Unlock a channel"),
                    ("/slowmode <seconds>", "Set channel slowmode"),
                    ("/antispam", "Configure anti-spam (Admin)"),
                    ("/filter_add <word>", "Add word to filter (Admin)"),
                    ("/filter_remove <word>", "Remove filtered word"),
                    ("/filter_list", "View filtered words"),
                    ("/filter_clear", "Clear all filters (Admin)"),
                    ("/filter_action", "Set filter action (Admin)"),
                ]
            },
            "server": {
                "emoji": "📊",
                "name": "Server",
                "desc": "Server info and management",
                "commands": [
                    ("/whois [user]", "Complete user information"),
                    ("/serverinfo", "Detailed server info + roles button"),
                    ("/roleinfo <role>", "Role details and permissions"),
                    ("/channelinfo [channel]", "Channel information"),
                    ("/avatar [user]", "View avatar with download links"),
                    ("/banner [user]", "View user banner"),
                    ("/membercount", "Member count breakdown"),
                    ("/inrole <role>", "List members with a role"),
                    ("/permissions [user]", "Check channel permissions"),
                    ("/emojis", "List all server emojis"),
                    ("/roles", "List all server roles"),
                    ("/firstmessage", "First message in channel"),
                    ("/logs_setup <channel>", "Setup server logging (Admin)"),
                    ("/logs_toggle <event>", "Toggle log events (Admin)"),
                    ("/logs_ignore <channel>", "Ignore channel from logs"),
                    ("/autorole_add <role>", "Add auto role on join (Admin)"),
                    ("/autorole_remove <role>", "Remove auto role (Admin)"),
                    ("/autorole_list", "View auto roles"),
                    ("/welcome_setup", "Configure welcome messages (Admin)"),
                    ("/welcome_test", "Test welcome message"),
                    ("/goodbye_toggle", "Toggle goodbye messages"),
                    ("/reactionrole_add", "Add reaction role (Admin)"),
                    ("/reactionrole_remove", "Remove reaction role (Admin)"),
                    ("/reactionrole_list", "View reaction roles"),
                    ("/reactionrole_clear", "Clear reaction roles (Admin)"),
                ]
            },
            "automod": {
                "emoji": "🔧",
                "name": "AutoMod",
                "desc": "Automatic moderation system",
                "commands": [
                    ("/antispam", "Configure anti-spam"),
                    ("/filter_add <word>", "Add word to filter"),
                    ("/filter_remove <word>", "Remove filtered word"),
                    ("/filter_list", "View filtered words"),
                    ("/filter_clear", "Clear all filters"),
                    ("/filter_action <action>", "Set filter action"),
                    ("/automod_setup <channel>", "Set automod log channel"),
                    ("/automod_status", "View automod config"),
                    ("/slowmode <seconds>", "Set channel slowmode"),
                    ("/lock [channel]", "Lock a channel"),
                    ("/unlock [channel]", "Unlock a channel"),
                ]
            },
            "events": {
                "emoji": "🎉",
                "name": "Events",
                "desc": "Community events and activities",
                "commands": [
                    ("/poll <question>", "Create yes/no poll"),
                    ("/multipoll <question>", "Create multi-option poll"),
                    ("/giveaway <prize> <duration>", "Start a giveaway"),
                    ("/suggest <idea>", "Submit a suggestion"),
                    ("/suggestion_approve <id>", "Approve suggestion (Mod)"),
                    ("/suggestion_deny <id>", "Deny suggestion (Mod)"),
                    ("/suggestions_setup <channel>", "Setup suggestions (Admin)"),
                    ("/ticket_setup", "Setup ticket system (Admin)"),
                    ("/ticket_close", "Close current ticket"),
                    ("/counting_setup <channel>", "Setup counting game (Admin)"),
                    ("/count", "Check current count"),
                    ("/starboard_setup", "Setup starboard (Admin)"),
                    ("/starboard_toggle", "Toggle starboard (Admin)"),
                    ("/birthday_setup <channel>", "Set birthday channel (Admin)"),
                ]
            },
            "utility": {
                "emoji": "⚙️",
                "name": "Utility",
                "desc": "General utility and tools",
                "commands": [
                    ("/ping", "Check bot latency"),
                    ("/uptime", "Bot uptime"),
                    ("/embed create", "Create a custom embed (Mod)"),
                    ("/embed advanced", "Advanced embed builder (Mod)"),
                    ("/embed save <name>", "Save embed template (Mod)"),
                    ("/embed use <name>", "Use saved template (Mod)"),
                    ("/embed list", "List saved templates"),
                    ("/embed delete <name>", "Delete template (Mod)"),
                    ("/setstatus", "Set bot status (Admin)"),
                    ("/resetstatus", "Reset status rotation (Admin)"),
                    ("/addstatus", "Add to status rotation (Admin)"),
                    ("/liststatus", "View all statuses"),
                    ("/modmail_setup", "Setup modmail (Admin)"),
                    ("/modmail_toggle", "Enable/disable modmail (Admin)"),
                    ("/dm <user> <msg>", "DM a user (Admin)"),
                    ("/announce <msg>", "Mass DM members (Admin)"),
                    ("/music [user]", "View Spotify status"),
                    ("/remind <time> <task>", "Set a reminder"),
                    ("/note <text>", "Save a quick note"),
                    ("/notes", "View all your notes"),
                    ("/mood <emoji>", "Log today's mood"),
                ]
            }
        }

    def build_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="ao — commands",
            description="pick a category below to see its commands.",
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        for key, cat in self.categories.items():
            count = len(cat['commands'])
            embed.add_field(
                name=f"{cat['emoji']} {cat['name']}",
                value=f"{cat['desc']}\n`{count} commands`",
                inline=True
            )

        total = sum(len(c['commands']) for c in self.categories.values())
        embed.set_footer(
            text=f"{total} total commands — buttons expire in 2 minutes",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        return embed

    def build_category_embed(self, key: str) -> discord.Embed:
        cat = self.categories[key]

        embed = discord.Embed(
            title=f"{cat['emoji']} {cat['name']}",
            description=cat['desc'],
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        commands_text = ""
        for cmd, desc in cat['commands']:
            commands_text += f"`{cmd}`\n{desc}\n\n"

        if len(commands_text) <= 4000:
            embed.description = f"{cat['desc']}\n\n{commands_text}"
        else:
            embed.description = cat['desc']
            chunk = ""
            first = True
            for cmd, desc in cat['commands']:
                line = f"`{cmd}`\n{desc}\n\n"
                if len(chunk) + len(line) > 1024:
                    embed.add_field(
                        name="Commands" if first else "\u200b",
                        value=chunk,
                        inline=False
                    )
                    chunk = line
                    first = False
                else:
                    chunk += line
            if chunk:
                embed.add_field(
                    name="Commands" if first else "\u200b",
                    value=chunk,
                    inline=False
                )

        embed.set_footer(
            text="click Back to return to categories",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "this isn't your help menu.",
                ephemeral=True
            )
            return False
        return True

    def update_buttons(self, page: str):
        self.clear_items()

        if page == "main":
            keys = list(self.categories.keys())
            row0 = keys[:5]
            row1 = keys[5:]

            for i, key in enumerate(row0):
                cat = self.categories[key]
                btn = discord.ui.Button(
                    label=cat['name'],
                    emoji=cat['emoji'],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"cat_{key}",
                    row=0
                )
                btn.callback = self.make_category_callback(key)
                self.add_item(btn)

            for i, key in enumerate(row1):
                cat = self.categories[key]
                btn = discord.ui.Button(
                    label=cat['name'],
                    emoji=cat['emoji'],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"cat_{key}",
                    row=1
                )
                btn.callback = self.make_category_callback(key)
                self.add_item(btn)
        else:
            back_btn = discord.ui.Button(
                label="Back",
                emoji="◀️",
                style=discord.ButtonStyle.primary,
                custom_id="back_btn",
                row=0
            )
            back_btn.callback = self.back_callback
            self.add_item(back_btn)

    def make_category_callback(self, key: str):
        async def callback(interaction: discord.Interaction):
            self.current_page = key
            self.update_buttons(key)
            embed = self.build_category_embed(key)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons("main")
        embed = self.build_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

@bot.hybrid_command(name="help", description="Show all commands")
async def help_command(ctx):
    view = HelpView(bot, ctx.author.id)
    view.update_buttons("main")
    embed = view.build_main_embed()
    await ctx.send(embed=embed, view=view)

# ==================== UTILITY SLASH COMMANDS ====================

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