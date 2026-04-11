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

# ==================== INTERACTIVE HELP WITH BUTTONS ====================

class HelpView(discord.ui.View):
    def __init__(self, bot, author_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.current_page = "main"

        self.categories = {
            "economy": {
                "name": "💰 Economy",
                "desc": "Earn, spend, and manage coins",
                "commands": [
                    ("/balance [user]", "Check wallet & bank"),
                    ("/daily", "Daily reward + streak bonus"),
                    ("/work", "Work for coins (1h cooldown)"),
                    ("/fish", "Go fishing 🎣 (needs rod)"),
                    ("/hunt", "Go hunting 🔫 (needs rifle)"),
                    ("/mine", "Mine for gems ⛏️ (needs pickaxe)"),
                    ("/beg", "Beg for coins"),
                    ("/crime", "Attempt a crime"),
                    ("/rob <user>", "Rob someone"),
                    ("/deposit <amount>", "Deposit to bank"),
                    ("/withdraw <amount>", "Withdraw from bank"),
                    ("/pay <user> <amount>", "Send coins"),
                    ("/shop", "Browse the shop"),
                    ("/buy <item>", "Buy an item"),
                    ("/inventory", "View your items"),
                    ("/profile", "Economy profile"),
                    ("/streak", "Daily streak info"),
                    ("/richest", "Top 10 richest"),
                    ("/setmoney", "Set balance (Admin)"),
                    ("/addmoney", "Add coins (Admin)"),
                    ("/removemoney", "Remove coins (Admin)"),
                ]
            },
            "fun": {
                "name": "🎮 Fun",
                "desc": "Entertainment commands",
                "commands": [
                    ("/roll [sides]", "Roll a dice"),
                    ("/flip", "Flip a coin"),
                    ("/8ball <question>", "Magic 8-ball"),
                    ("/rps <choice>", "Rock Paper Scissors"),
                    ("/meme", "Random meme"),
                    ("/joke", "Dark joke"),
                    ("/fact", "Random fact"),
                    ("/ship <u1> <u2>", "Ship two users"),
                    ("/rate <thing>", "Rate anything"),
                    ("/reverse <text>", "Reverse text"),
                    ("/mock <text>", "Mock text"),
                    ("/choose <a> <b>", "Bot chooses"),
                    ("/topic", "Conversation starter"),
                    ("/would <a> <b>", "Would you rather"),
                    ("/truth [user]", "Truth question"),
                    ("/dare [user]", "Dare challenge"),
                    ("/tod [user]", "Random truth or dare"),
                    ("/trivia", "Trivia question"),
                    ("/trivia_stats", "Your trivia stats"),
                ]
            },
            "ai": {
                "name": "🧠 AI",
                "desc": "AI-powered features",
                "commands": [
                    ("@ao <message>", "Chat naturally"),
                    ("/chat <message>", "AI chat"),
                    ("/ask <question>", "Ask anything"),
                    ("/quote", "Dark quote"),
                    ("/roast [user]", "Friendly roast"),
                    ("/clear_chat", "Clear conversation"),
                ]
            },
            "social": {
                "name": "💕 Social",
                "desc": "Social and community features",
                "commands": [
                    ("/marry <user>", "Propose to someone"),
                    ("/divorce", "End your marriage"),
                    ("/spouse [user]", "View marriage status"),
                    ("/rep <user>", "Give reputation"),
                    ("/repcheck [user]", "Check reputation"),
                    ("/replb", "Rep leaderboard"),
                    ("/birthday_set", "Set your birthday"),
                    ("/birthday [user]", "Check birthday"),
                    ("/birthdays", "Upcoming birthdays"),
                    ("/afk [reason]", "Set AFK status"),
                ]
            },
            "leveling": {
                "name": "⭐ Leveling",
                "desc": "MEE6-style XP system",
                "commands": [
                    ("/level [user]", "Check level & XP"),
                    ("/leaderboard_levels", "XP leaderboard"),
                    ("/level_setup", "Set level-up channel (Admin)"),
                    ("/level_role", "Set level rewards (Admin)"),
                    ("/level_ignore", "Ignore channel (Admin)"),
                    ("/level_config", "View leveling config"),
                    ("/give_xp", "Give XP (Admin)"),
                    ("/remove_xp", "Remove XP (Admin)"),
                    ("/reset_xp", "Reset XP (Admin)"),
                ]
            },
            "moderation": {
                "name": "🛡️ Moderation",
                "desc": "Server moderation tools",
                "commands": [
                    ("/kick <user>", "Kick member"),
                    ("/ban <user>", "Ban member"),
                    ("/unban <id>", "Unban user"),
                    ("/timeout <user>", "Timeout member"),
                    ("/untimeout <user>", "Remove timeout"),
                    ("/warn <user>", "Warn member"),
                    ("/modlogs", "Moderation logs"),
                    ("/purge <amount>", "Delete messages"),
                    ("/lock [channel]", "Lock channel"),
                    ("/unlock [channel]", "Unlock channel"),
                    ("/slowmode <sec>", "Set slowmode"),
                    ("/antispam", "Configure anti-spam"),
                    ("/filter_add <word>", "Add word filter"),
                    ("/filter_remove <word>", "Remove filter"),
                    ("/filter_list", "View filters"),
                ]
            },
            "server": {
                "name": "📊 Server",
                "desc": "Server info and management",
                "commands": [
                    ("/whois [user]", "Complete user info"),
                    ("/serverinfo", "Server information"),
                    ("/roleinfo <role>", "Role details"),
                    ("/channelinfo", "Channel details"),
                    ("/avatar [user]", "View avatar"),
                    ("/banner [user]", "View banner"),
                    ("/membercount", "Member breakdown"),
                    ("/inrole <role>", "Members with role"),
                    ("/permissions", "Check permissions"),
                    ("/emojis", "List emojis"),
                    ("/roles", "List all roles"),
                    ("/logs_setup", "Setup logging (Admin)"),
                    ("/autorole_add", "Auto role (Admin)"),
                    ("/reactionrole_add", "Reaction role (Admin)"),
                    ("/welcome_setup", "Welcome config (Admin)"),
                ]
            },
            "events": {
                "name": "🎉 Events",
                "desc": "Community events and activities",
                "commands": [
                    ("/poll <question>", "Create poll"),
                    ("/multipoll", "Multi-option poll"),
                    ("/giveaway", "Start giveaway"),
                    ("/suggest <idea>", "Submit suggestion"),
                    ("/suggest_approve", "Approve suggestion (Mod)"),
                    ("/suggest_deny", "Deny suggestion (Mod)"),
                    ("/ticket_setup", "Setup tickets (Admin)"),
                    ("/counting_setup", "Setup counting (Admin)"),
                    ("/count", "Check current count"),
                    ("/starboard_setup", "Setup starboard (Admin)"),
                    ("/birthday_setup", "Birthday channel (Admin)"),
                    ("/dm <user>", "DM a user (Admin)"),
                    ("/announce", "Mass DM (Admin)"),
                ]
            },
            "utility": {
                "name": "⚙️ Utility",
                "desc": "Useful tools",
                "commands": [
                    ("/ping", "Bot latency"),
                    ("/uptime", "Bot uptime"),
                    ("/embed", "Create embed (Mod)"),
                    ("/embed_advanced", "Advanced embed (Mod)"),
                    ("/setstatus", "Set status (Admin)"),
                    ("/resetstatus", "Reset status (Admin)"),
                    ("/modmail_setup", "Setup modmail (Admin)"),
                    ("/music [user]", "Spotify status"),
                    ("/remind <time>", "Set reminder"),
                    ("/note <text>", "Save note"),
                    ("/notes", "View notes"),
                    ("/mood <emoji>", "Log mood"),
                    ("/toggledms", "Toggle DMs from bot"),
                ]
            }
        }

    def build_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="ao — Command Center",
            description="pick a category to see commands",
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        for key, cat in self.categories.items():
            count = len(cat['commands'])
            embed.add_field(
                name=cat['name'],
                value=f"{cat['desc']}\n`{count} commands`",
                inline=True
            )

        total = sum(len(c['commands']) for c in self.categories.values())
        embed.set_footer(text=f"ao • {total} total commands • buttons expire in 2 minutes")
        return embed

    def build_category_embed(self, key: str) -> discord.Embed:
        cat = self.categories[key]
        embed = discord.Embed(
            title=cat['name'],
            description=cat['desc'],
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        commands_text = ""
        for cmd, desc in cat['commands']:
            commands_text += f"`{cmd}`\n{desc}\n\n"

        # Split into fields if too long
        if len(commands_text) <= 4096:
            embed.description = f"{cat['desc']}\n\n{commands_text}"
        else:
            embed.description = cat['desc']
            chunk = ""
            field_count = 0
            for cmd, desc in cat['commands']:
                line = f"`{cmd}`\n{desc}\n\n"
                if len(chunk) + len(line) > 1024:
                    embed.add_field(
                        name="Commands" if field_count == 0 else "\u200b",
                        value=chunk,
                        inline=False
                    )
                    chunk = line
                    field_count += 1
                else:
                    chunk += line
            if chunk:
                embed.add_field(
                    name="Commands" if field_count == 0 else "\u200b",
                    value=chunk,
                    inline=False
                )

        embed.set_footer(text="ao • click Back to return to categories")
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
        """Update button states based on current page"""
        self.clear_items()

        if page == "main":
            # Add category buttons
            categories_row1 = ["economy", "fun", "ai", "social", "leveling"]
            categories_row2 = ["moderation", "server", "events", "utility"]

            for i, key in enumerate(categories_row1):
                cat = self.categories[key]
                btn = discord.ui.Button(
                    label=cat['name'].split(' ')[1],
                    emoji=cat['name'].split(' ')[0],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"cat_{key}",
                    row=0
                )
                btn.callback = self.make_category_callback(key)
                self.add_item(btn)

            for i, key in enumerate(categories_row2):
                cat = self.categories[key]
                btn = discord.ui.Button(
                    label=cat['name'].split(' ')[1],
                    emoji=cat['name'].split(' ')[0],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"cat_{key}",
                    row=1
                )
                btn.callback = self.make_category_callback(key)
                self.add_item(btn)
        else:
            # Add back button
            back_btn = discord.ui.Button(
                label="Back",
                emoji="◀️",
                style=discord.ButtonStyle.primary,
                custom_id="back",
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
    """Interactive help with buttons"""
    view = HelpView(bot, ctx.author.id)
    view.update_buttons("main")
    embed = view.build_main_embed()
    await ctx.send(embed=embed, view=view)

# ==================== PREFIX COMMANDS (non-slash support) ====================

@bot.command(name="balance", aliases=["bal", "wallet", "money"])
async def prefix_balance(ctx, user: discord.Member = None):
    """!balance or !bal"""
    user = user or ctx.author
    from utils.database import Database
    db = Database('data/economy.json')
    data = db.get(str(user.id), {'balance': 0, 'bank': 0})

    embed = discord.Embed(color=0x1a1a2e)
    embed.set_author(
        name=f"{user.display_name}'s Balance",
        icon_url=user.avatar.url if user.avatar else None
    )
    embed.add_field(name="Wallet", value=f"${data.get('balance', 0):,}", inline=True)
    embed.add_field(name="Bank", value=f"${data.get('bank', 0):,}", inline=True)
    embed.add_field(
        name="Net Worth",
        value=f"${data.get('balance', 0) + data.get('bank', 0):,}",
        inline=True
    )
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def prefix_ping(ctx):
    """!ping"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        description=f"Latency: **{latency}ms**",
        color=0x1a1a2e
    )
    await ctx.send(embed=embed)

@bot.command(name="help", aliases=["h", "commands"])
async def prefix_help(ctx):
    """!help"""
    view = HelpView(bot, ctx.author.id)
    view.update_buttons("main")
    embed = view.build_main_embed()
    await ctx.send(embed=embed, view=view)

@bot.command(name="level", aliases=["lvl", "rank", "xp"])
async def prefix_level(ctx, user: discord.Member = None):
    """!level or !lvl"""
    user = user or ctx.author
    from utils.database import Database
    db = Database('data/leveling.json')
    data = db.get(f"{ctx.guild.id}_{user.id}", {'xp': 0, 'level': 0, 'total_xp': 0})

    # Simple XP formula
    def xp_for_level(lvl):
        return 5 * (lvl ** 2) + 50 * lvl + 100

    total_xp = data.get('total_xp', 0)
    level = 0
    xp_remaining = total_xp

    while True:
        needed = xp_for_level(level)
        if xp_remaining < needed:
            break
        xp_remaining -= needed
        level += 1

    needed = xp_for_level(level)
    progress = (xp_remaining / needed * 100) if needed > 0 else 0
    bar_filled = int((progress / 100) * 15)
    bar = "▰" * bar_filled + "▱" * (15 - bar_filled)

    embed = discord.Embed(color=0x1a1a2e)
    embed.set_author(
        name=user.display_name,
        icon_url=user.avatar.url if user.avatar else None
    )
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="Total XP", value=f"{total_xp:,}", inline=True)
    embed.add_field(
        name="Progress",
        value=f"`{bar}` {xp_remaining}/{needed}",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name="whois", aliases=["userinfo", "ui"])
async def prefix_whois(ctx, user: discord.Member = None):
    """!whois or !userinfo"""
    user = user or ctx.author
    embed = discord.Embed(
        color=user.color if user.color.value else 0x1a1a2e
    )
    embed.set_author(
        name=f"{user} ({user.id})",
        icon_url=user.avatar.url if user.avatar else user.default_avatar.url
    )
    embed.set_thumbnail(
        url=user.avatar.url if user.avatar else user.default_avatar.url
    )
    embed.add_field(
        name="Created",
        value=user.created_at.strftime("%b %d, %Y"),
        inline=True
    )
    embed.add_field(
        name="Joined",
        value=user.joined_at.strftime("%b %d, %Y") if user.joined_at else "Unknown",
        inline=True
    )
    roles = [r for r in user.roles if r.name != "@everyone"]
    embed.add_field(
        name=f"Roles ({len(roles)})",
        value=" ".join([r.mention for r in reversed(roles[:10])]) or "None",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", aliases=["si", "server"])
async def prefix_serverinfo(ctx):
    """!serverinfo or !si"""
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=0x1a1a2e)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=f"{guild.member_count:,}", inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="purge", aliases=["clear", "delete"])
@commands.has_permissions(manage_messages=True)
async def prefix_purge(ctx, amount: int = 5):
    """!purge 10"""
    if amount < 1 or amount > 100:
        await ctx.send("amount must be 1-100.", delete_after=3)
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"deleted {len(deleted) - 1} messages.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except:
        pass

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def prefix_kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """!kick @user reason"""
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            description=f"kicked **{member}**. reason: {reason}",
            color=0x1a1a2e
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("i can't kick that user.")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def prefix_ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """!ban @user reason"""
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            description=f"banned **{member}**. reason: {reason}",
            color=0x1a1a2e
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("i can't ban that user.")

@bot.command(name="avatar", aliases=["av", "pfp"])
async def prefix_avatar(ctx, user: discord.Member = None):
    """!avatar or !pfp"""
    user = user or ctx.author
    embed = discord.Embed(title=f"{user.display_name}'s Avatar", color=0x1a1a2e)
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="uptime")
async def prefix_uptime(ctx):
    """!uptime"""
    delta = datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    embed = discord.Embed(
        description=f"running for **{days}d {hours}h {minutes}m {seconds}s**",
        color=0x1a1a2e
    )
    await ctx.send(embed=embed)

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