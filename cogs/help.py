"""
cogs/help.py — interactive help system using a Select dropdown.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.constants import COLOR_DEFAULT, COLOR_AI, COLOR_FUN, COLOR_GAMES, COLOR_ECONOMY, COLOR_MOD, COLOR_INFO

CATEGORIES = {
    "ai": {
        "emoji": "🤖",
        "name": "AI",
        "desc": "AI chat and AI-powered features",
        "color": COLOR_AI,
        "commands": [
            ("@cyn <message>", "Chat naturally with cyn via mention"),
            ("/cyn <message>", "Slash alternative to @mention"),
            ("/chat <message>", "Slash-command AI conversation"),
            ("/summarize <text>", "Summarize text in 3-5 bullets"),
            ("/translate <language> <text>", "Translate text to a language"),
            ("/explain <topic>", "Explain a topic like you're 12"),
            ("/advice <situation>", "Blunt, sarcastic advice"),
            ("/roast_server", "AI roasts the current server"),
            ("/code <language> <description>", "Generate a code snippet"),
            ("/forget", "Clear cyn's memory of your conversation history"),
            ("@cyn warn/ban/kick @user", "AI moderation with confirmation"),
            ("@cyn delete message: <id>", "Delete a message by ID or reply"),
            ("@cyn remind me in 10m to X", "Set a reminder via AI"),
            ("@cyn cancel reminder", "Cancel a reminder via AI"),
        ],
    },
    "fun": {
        "emoji": "🎉",
        "name": "Fun",
        "desc": "Quick laughs",
        "color": COLOR_FUN,
        "commands": [
            ("/roll [sides=6]", "Roll a dice"),
            ("/flip", "Flip a coin"),
            ("/joke", "Random joke"),
            ("/meme", "Random meme"),
            ("/truth", "Random truth question"),
            ("/dare", "Random dare challenge"),
            ("/say <text>", "Bot says text (owner only)"),
        ],
    },
    "moderation": {
        "emoji": "🛡️",
        "name": "Moderation",
        "desc": "Server moderation tools + AI mod control",
        "color": COLOR_MOD,
        "commands": [
            ("/mod kick <user>", "Kick a member"),
            ("/mod ban <user>", "Ban a member"),
            ("/mod unban <id>", "Unban a user"),
            ("/mod timeout <user> <time>", "Timeout a member"),
            ("/mod unmute <user>", "Remove timeout from a user"),
            ("/mod warnings <action> <user> [reason]", "Add/list/clear warnings"),
            ("/mod purge <amount>", "Delete messages"),
            ("/mod nuke", "Clone & delete the channel"),
            ("/mod slowmode [seconds=0]", "Set channel slowmode"),
            ("/mod lock [reason]", "Lock channel for @everyone"),
            ("/mod unlock", "Unlock channel"),
            ("/adminrole <role>", "Set the AI moderation role (server owner only)"),
            ("/adminrole_remove", "Remove the AI moderation role"),
            ("/mod antispam [on/off]", "Toggle antispam automod"),
            ("/mod antilink [on/off] [channel]", "Block non-Discord links in a channel"),
            ("/mod tempban @user [duration] [reason]", "Temp ban with auto-unban"),
            ("/mod config [setting] [value]", "Configure warn thresholds"),
            ("@cyn warn/ban/kick @user", "AI-driven mod with confirmation"),
        ],
    },
    "utility": {
        "emoji": "🔧",
        "name": "Utility",
        "desc": "Handy everyday commands",
        "color": COLOR_INFO,
        "commands": [
            ("/weather <city>", "Current weather for a city"),
            ("/math <expression>", "Safely evaluate a math expression"),
            ("/snipe [index=1]", "Show nth most recent deleted message"),
            ("/afk [reason]", "Set your AFK status"),
            ("/ping", "Websocket latency"),
            ("/botinfo", "Bot information"),
            ("/uptime", "Bot uptime"),
            ("/profile [@user]", "View a user's profile"),
            ("/profile_set bio [text]", "Set your bio (max 200 chars)"),
            ("/profile_set pronouns [text]", "Set your pronouns"),
            ("/profile_set timezone [text]", "Set your timezone"),
        ],
    },
    "server": {
        "emoji": "ℹ️",
        "name": "Server",
        "desc": "Server and member information",
        "color": COLOR_INFO,
        "commands": [
            ("/serverinfo", "Server information"),
            ("/whois [user]", "User information"),
            ("/avatar [user]", "Show user avatar"),
        ],
    },
    "community": {
        "emoji": "🌍",
        "name": "Community",
        "desc": "Polls, confessions, birthdays, reminders",
        "color": COLOR_FUN,
        "commands": [
            ("/poll create <q> <o1> <o2> [o3] [o4] [dur]", "Create a poll with up to 4 options"),
            ("/poll end <message_id>", "End a poll early and show results"),
            ("/confess text [text]", "Submit an anonymous confession"),
            ("/confess setup #channel", "Set confession channel (admin)"),
            ("/birthday set [month] [day]", "Set your birthday"),
            ("/birthday upcoming", "Show upcoming birthdays"),
            ("/birthday channel #channel", "Set announcement channel (admin)"),
            ("/reminders", "List your active reminders"),
        ],
    },
    "settings": {
        "emoji": "⚙️",
        "name": "Settings",
        "desc": "Welcome, goodbye, autorole, logging, bot status, prefix, rules",
        "color": COLOR_DEFAULT,
        "commands": [
            ("/welcome config [setting] [value] [channel]", "Configure welcome & goodbye settings"),
            ("/welcome test [type]", "Test welcome/goodbye/DM messages"),
            ("/welcome show", "Show current welcome/goodbye config"),
            ("/autorole set @role", "Assign role to new members"),
            ("/autorole remove", "Disable autorole"),
            ("/autorole show", "Show configured autorole"),
            ("/log setup #channel", "Set log channel"),
            ("/log disable", "Disable logging"),
            ("/log show", "Show log settings"),
            ("/log toggle [event]", "Toggle event logging"),
            ("/status set [type] [text]", "Set custom bot status (owner)"),
            ("/status reset", "Resume auto-rotation (owner)"),
            ("/status current", "Show current status"),
            ("/status info", "How Discord displays bot status"),
            ("/rules set [text]", "Set server rules (Manage Guild)"),
            ("/rules show", "Show server rules"),
            ("/rules agree", "Agree to rules (get role)"),
            ("/rules agree_role @role", "Set the agreement role (Manage Guild)"),
            ("/bump remind", "Set a 2-hour bump reminder (admin)"),
            ("/prefix set [prefix]", "Set a custom prefix for AI chat (Manage Guild)"),
            ("/prefix remove", "Remove custom prefix (Manage Guild)"),
            ("/prefix list", "Show the current prefix"),
        ],
    },
    "owner": {
        "emoji": "👑",
        "name": "Owner",
        "desc": "Owner-only bot management (requires OWNER_ID)",
        "color": COLOR_MOD,
        "commands": [
            ("/owner status", "Bot statistics (servers, users, cogs, memory)"),
            ("/owner reload [cog]", "Reload a cog by name"),
            ("/owner sync", "Force command sync to all guilds"),
            ("/owner shutdown", "Shut down the bot gracefully"),
            ("/owner eval [code]", "Execute Python code"),
            ("/owner dm [user_id] [message]", "DM any user by ID"),
            ("/owner announce [message] [channel?] [embed?]", "Announce to a channel or all servers"),
            ("/owner createrole [name] [color] [admin]", "Create a role"),
            ("/owner giverole [role] [member]", "Give a role to a member"),
            ("/owner removerole [role] [member]", "Remove a role from a member"),
            ("/owner servers", "List all servers the bot is in"),
            ("/owner say [message] [channel]", "Send a message as the bot"),
            ("/owner leave [guild_id]", "Leave a server by ID (with confirmation)"),
            ("/owner personality [note]", "Set server personality note (owner/server owner)"),
            ("/owner personality_clear", "Clear server personality note"),
        ],
    },
}


class HelpSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = []
        for key, cat in CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat['name'], value=key, description=cat['desc'][:100], emoji=cat['emoji'],
            ))
        super().__init__(placeholder="Choose a category...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.parent_view.current_category = selected
        self.parent_view.current_page = 0
        embeds = self.parent_view.build_category_embeds(selected)
        self.parent_view.current_embeds = embeds
        self.parent_view._rebuild_view()
        try:
            await interaction.response.edit_message(embed=embeds[0], view=self.parent_view)
        except (discord.NotFound, discord.InteractionResponded):
            pass


class HelpView(discord.ui.View):
    def __init__(self, bot, author_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.current_category = None
        self.current_page = 0
        self.current_embeds = []
        self.select = HelpSelect(self)
        self.add_item(self.select)
        home_btn = discord.ui.Button(label="Home", emoji="🏠", style=discord.ButtonStyle.primary, row=1)
        home_btn.callback = self.home_callback
        self.home_btn = home_btn
        self.add_item(home_btn)
        self.prev_btn = None
        self.next_btn = None

    def build_home_embed(self):
        embed = discord.Embed(title="cyn — commands", description="pick a category from the dropdown.", color=COLOR_DEFAULT, timestamp=datetime.utcnow())
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        for key, cat in CATEGORIES.items():
            embed.add_field(name=f"{cat['emoji']} {cat['name']}", value=f"{cat['desc']}\n`{len(cat['commands'])} commands`", inline=True)
        total = sum(len(c['commands']) for c in CATEGORIES.values())
        embed.set_footer(text=f"{total} total commands")
        return embed

    def build_category_embeds(self, key):
        cat = CATEGORIES[key]
        color = cat.get('color', COLOR_DEFAULT)
        commands = cat['commands']
        pages = []
        chunk_size = 10
        chunks = [commands[i:i+chunk_size] for i in range(0, len(commands), chunk_size)]
        if not chunks:
            chunks = [[]]
        total_pages = len(chunks)
        for page_idx, chunk in enumerate(chunks):
            embed = discord.Embed(title=f"{cat['emoji']} {cat['name']}", description=cat['desc'], color=color, timestamp=datetime.utcnow())
            commands_text = ""
            for cmd, desc in chunk:
                commands_text += f"`{cmd}`\n{desc}\n\n"
            if commands_text:
                embed.add_field(name=f"Commands (page {page_idx+1}/{total_pages})", value=commands_text[:1024], inline=False)
            embed.set_footer(text=f"click 🏠 Home to return · {len(commands)} total")
            pages.append(embed)
        return pages

    def _rebuild_view(self):
        self.clear_items()
        self.select = HelpSelect(self)
        self.select.placeholder = f"Viewing: {CATEGORIES.get(self.current_category, {}).get('name', '...')}"
        self.add_item(self.select)
        self.add_item(self.home_btn)
        if len(self.current_embeds) > 1:
            prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, row=1, disabled=(self.current_page == 0))
            prev_btn.callback = self.prev_callback
            self.prev_btn = prev_btn
            self.add_item(prev_btn)
            next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, row=1, disabled=(self.current_page >= len(self.current_embeds) - 1))
            next_btn.callback = self.next_callback
            self.next_btn = next_btn
            self.add_item(next_btn)

    async def home_callback(self, interaction):
        self.current_category = None
        self.current_page = 0
        self.current_embeds = []
        self.clear_items()
        self.select = HelpSelect(self)
        self.add_item(self.select)
        self.add_item(self.home_btn)
        embed = self.build_home_embed()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass

    async def prev_callback(self, interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._rebuild_view()
            try:
                await interaction.response.edit_message(embed=self.current_embeds[self.current_page], view=self)
            except (discord.NotFound, discord.InteractionResponded):
                pass

    async def next_callback(self, interaction):
        if self.current_page < len(self.current_embeds) - 1:
            self.current_page += 1
            self._rebuild_view()
            try:
                await interaction.response.edit_message(embed=self.current_embeds[self.current_page], view=self)
            except (discord.NotFound, discord.InteractionResponded):
                pass

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            try:
                await interaction.response.send_message("this isn't your help menu.", ephemeral=True)
            except Exception:
                pass
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            try:
                item.disabled = True
            except Exception:
                pass


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all commands")
    async def help(self, interaction: discord.Interaction, command: str = None):
        self.bot.increment_command('help')
        view = HelpView(self.bot, interaction.user.id)
        embed = view.build_home_embed()
        try:
            await interaction.response.send_message(embed=embed, view=view)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
