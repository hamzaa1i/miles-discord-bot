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
            ("@cyn warn/ban/kick @user", "AI moderation with confirmation"),
            ("@cyn delete message: <id>", "Delete a message by ID or reply"),
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
    "games": {
        "emoji": "🎮",
        "name": "Games",
        "desc": "Interactive games with buttons",
        "color": COLOR_GAMES,
        "commands": [
            ("/rps", "Rock Paper Scissors with buttons"),
            ("/ttt <user>", "Tic Tac Toe against a user"),
            ("/numguess", "Number guessing 1-100"),
            ("/typerace", "First to type the sentence wins"),
            ("/reaction", "Reaction time test"),
            ("/wordle", "Wordle clone (6 guesses)"),
            ("/blackjack [bet=0]", "Blackjack with optional economy bet"),
            ("/coinflip [bet=0] [choice=heads]", "Bet coins on heads/tails"),
            ("/slots", "Slot machine (10 coins to play)"),
        ],
    },
    "economy": {
        "emoji": "💰",
        "name": "Economy",
        "desc": "Earn, spend and manage coins (per-guild)",
        "color": COLOR_ECONOMY,
        "commands": [
            ("/balance [user]", "Check wallet & bank"),
            ("/daily", "Daily reward + streak + marriage bonus"),
            ("/work", "Work for coins (1h cooldown)"),
            ("/pay <user> <amount>", "Send coins to someone"),
            ("/richest", "Top 10 richest in this server"),
            ("/earn fish", "Go fishing (need Fishing Rod)"),
            ("/earn hunt", "Go hunting (need Hunting Rifle)"),
            ("/earn mine", "Go mining (need Pickaxe)"),
            ("/earn beg", "Beg for coins (15m cooldown)"),
            ("/earn crime", "Commit a crime (1h cooldown)"),
            ("/earn rob <user>", "Rob someone (1h cooldown)"),
            ("/bank deposit <amount>", "Deposit to bank"),
            ("/bank withdraw <amount>", "Withdraw from bank"),
            ("/eco_admin set", "Set balance (admin)"),
            ("/eco_admin add", "Add coins (admin)"),
            ("/eco_admin remove", "Remove coins (admin)"),
            ("/eco_admin reset", "Reset economy (admin)"),
        ],
    },
    "moderation": {
        "emoji": "🛡️",
        "name": "Moderation",
        "desc": "Server moderation tools",
        "color": COLOR_MOD,
        "commands": [
            ("/mod kick <user>", "Kick a member"),
            ("/mod ban <user>", "Ban a member"),
            ("/mod unban <id>", "Unban a user"),
            ("/mod timeout <user> <time>", "Timeout a member"),
            ("/mod unmute <user>", "Remove timeout from a user"),
            ("/mod warn <user> <reason>", "Warn a member"),
            ("/mod warn_clear <user>", "Clear all warnings for a user"),
            ("/mod purge <amount>", "Delete messages"),
            ("/mod nuke", "Clone & delete the channel"),
            ("/mod slowmode [seconds=0]", "Set channel slowmode"),
            ("/mod lock [reason]", "Lock channel for @everyone"),
            ("/mod unlock", "Unlock channel"),
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
        ],
    },
    "community": {
        "emoji": "🌍",
        "name": "Community",
        "desc": "Polls, counting, rep, marriage",
        "color": COLOR_FUN,
        "commands": [
            ("/poll create <q> <o1> <o2> [o3] [o4] [dur]", "Create a poll"),
            ("/poll end <message_id>", "End a poll early"),
            ("/counting setup #channel", "Set the counting channel"),
            ("/counting reset", "Reset count to 0 (mod)"),
            ("/counting score", "Show current count + high score"),
            ("/rep give @user [reason]", "Give +1 rep (24h cooldown)"),
            ("/rep leaderboard", "Top 10 rep in server"),
            ("/rep reset @user", "Reset rep (owner only)"),
            ("/marry @user", "Propose to someone"),
            ("/divorce", "End your marriage"),
            ("/marriage [@user]", "Check marriage status"),
            ("/proposal cancel", "Cancel your outgoing proposal"),
            ("/proposal list", "Show pending proposals"),
            ("/toggledms", "Toggle DMs from cyn"),
        ],
    },
    "settings": {
        "emoji": "⚙️",
        "name": "Settings",
        "desc": "Logging, reaction roles, auto-responder, starboard, welcome, AI mod role",
        "color": COLOR_DEFAULT,
        "commands": [
            ("/setlog #channel", "Set the logging channel"),
            ("/log toggle <event_type>", "Toggle a log event"),
            ("/log list", "View log event statuses"),
            ("/reactionrole add <id> <emoji> <role>", "Add a reaction role"),
            ("/reactionrole remove <id> <emoji>", "Remove a reaction role"),
            ("/reactionrole list", "List reaction roles"),
            ("/autorespond add <trigger> <response>", "Add an auto-responder"),
            ("/autorespond remove <trigger>", "Remove an auto-responder"),
            ("/autorespond list", "List auto-responders"),
            ("/customcmd add <name> <response>", "Add a custom command"),
            ("/customcmd remove <name>", "Remove a custom command"),
            ("/customcmd list", "List custom commands"),
            ("/starboard ignore #channel", "Ignore a channel from starboard"),
            ("/welcome channel #channel", "Set welcome channel"),
            ("/welcome message [text]", "Set welcome message"),
            ("/welcome toggle", "Enable/disable welcome messages"),
            ("/goodbye channel #channel", "Set goodbye channel"),
            ("/goodbye message [text]", "Set goodbye message"),
            ("/goodbye toggle", "Enable/disable goodbye messages"),
            ("/adminrole <role>", "Set the AI moderation role (server owner only)"),
            ("/adminrole_remove", "Remove the AI moderation role"),
        ],
    },
    "info": {
        "emoji": "ℹ️",
        "name": "Info",
        "desc": "Bot and server information commands",
        "color": COLOR_INFO,
        "commands": [
            ("/botinfo", "Bot information"),
            ("/ping", "Websocket latency"),
            ("/uptime", "Bot uptime"),
            ("/serverinfo", "Server information"),
            ("/whois [user]", "User information"),
            ("/avatar [user]", "Show user avatar"),
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
