"""
cogs/help.py — interactive help system using a Select dropdown.

BUG FIX: The previous button-based implementation crashed with
`ValueError: item would not fit at row 1 (6 > 5 width)` because it tried
to put 6+ category buttons in a single row (Discord allows max 5 buttons
per row and 5 rows per message).

New implementation uses a `discord.ui.Select` dropdown (max 25 options,
no row limit) for category selection, plus a "← Home" button to return
to the main list. Categories with more than 10 commands are split into
multiple embed pages with ◀ ▶ pagination buttons.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.constants import COLOR_DEFAULT, COLOR_AI, COLOR_FUN, COLOR_GAMES, COLOR_ECONOMY, COLOR_MOD, COLOR_INFO
from utils.paginator import Paginator


# ==================== Category definitions ====================
# Each command is a (command_signature, one_line_description) tuple.
# These lists were verified against every cog file in the repo.

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
            ("/ask <question>", "Ask cyn anything"),
            ("/roast [user]", "AI-generated savage roast"),
            ("/summarize <text>", "Summarize text in 3-5 bullets"),
            ("/translate <language> <text>", "Translate text to a language"),
            ("/explain <topic>", "Explain a topic like you're 12"),
            ("/advice <situation>", "Blunt, sarcastic advice"),
            ("/roast_server", "AI roasts the current server"),
        ],
    },
    "fun": {
        "emoji": "🎉",
        "name": "Fun",
        "desc": "Quick laughs and games",
        "color": COLOR_FUN,
        "commands": [
            ("/roll [sides=6]", "Roll a dice"),
            ("/flip", "Flip a coin"),
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
        "desc": "Earn, spend and manage coins",
        "color": COLOR_ECONOMY,
        "commands": [
            ("/balance [user]", "Check wallet & bank"),
            ("/daily", "Daily reward + streak bonus"),
            ("/work", "Work for coins (1h cooldown)"),
            ("/pay <user> <amount>", "Send coins to someone"),
            ("/shop", "Browse the item shop"),
            ("/buy <item>", "Purchase an item"),
            ("/inventory [user]", "View your items"),
            ("/profile [user]", "Your full economy profile (image)"),
            ("/richest", "Top 10 richest users (image)"),
        ],
    },
    "leveling": {
        "emoji": "⭐",
        "name": "Leveling",
        "desc": "XP and leveling system",
        "color": COLOR_ECONOMY,
        "commands": [
            ("/level [user]", "Check level and XP progress (image card)"),
            ("/leaderboard_levels", "XP leaderboard (image card)"),
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
            ("/mod untimeout <user>", "Remove timeout"),
            ("/mod warn <user> <reason>", "Warn a member"),
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
            ("/password [length=16]", "Generate a secure password"),
            ("/snipe [index=1]", "Show nth most recent deleted message"),
            ("/urban <word>", "Urban Dictionary definition"),
            ("/afk [reason]", "Set your AFK status"),
            ("/announce <channel> <title> <msg>", "Send announcement embed (mod)"),
        ],
    },
    "community": {
        "emoji": "🌍",
        "name": "Community",
        "desc": "Giveaways, suggestions, polls, birthdays, counting, rep, marriage, confessions",
        "color": COLOR_FUN,
        "commands": [
            ("/giveaway start <dur> <winners> <prize> [#chan]", "Start a giveaway"),
            ("/giveaway end <message_id>", "Force-end a giveaway"),
            ("/giveaway reroll <message_id>", "Pick a new winner"),
            ("/giveaway list", "List active giveaways"),
            ("/suggest setup #channel", "Set suggestions channel"),
            ("/suggest submit <text>", "Submit a suggestion"),
            ("/suggest approve <id> [reason]", "Approve (mod)"),
            ("/suggest deny <id> [reason]", "Deny (mod)"),
            ("/poll create <q> <o1> <o2> [o3] [o4] [dur]", "Create a poll"),
            ("/poll end <message_id>", "End a poll early"),
            ("/poll results <message_id>", "Show poll results"),
            ("/birthday set <month> <day>", "Set your birthday"),
            ("/birthday check @user", "Check someone's birthday"),
            ("/birthday upcoming", "Next 5 birthdays"),
            ("/birthday channel #channel", "Set announcement channel (mod)"),
            ("/counting setup #channel", "Set the counting channel"),
            ("/counting reset", "Reset count to 0 (mod)"),
            ("/counting score", "Show current count + high score"),
            ("/counting toggle_save", "Toggle count-save on fail"),
            ("/rep give @user [reason]", "Give +1 rep (24h cooldown)"),
            ("/rep check [@user]", "Check reputation"),
            ("/rep leaderboard", "Top 10 rep in server"),
            ("/rep reset @user", "Reset rep (owner only)"),
            ("/marry @user", "Propose to someone"),
            ("/divorce", "End your marriage"),
            ("/marriage [@user]", "Check marriage status"),
            ("/confess <text>", "Submit an anonymous confession"),
            ("/confess_setup #channel", "Set confession channel (admin)"),
            ("/toggledms", "Toggle DMs from cyn"),
        ],
    },
    "settings": {
        "emoji": "⚙️",
        "name": "Settings",
        "desc": "Logging, reaction roles, auto-responder, starboard",
        "color": COLOR_DEFAULT,
        "commands": [
            ("/autorole [role]", "Set the role auto-assigned on join"),
            ("/setlog #channel", "Set the logging channel"),
            ("/reactionrole add <id> <emoji> <role>", "Add a reaction role"),
            ("/reactionrole remove <id> <emoji>", "Remove a reaction role"),
            ("/reactionrole list", "List reaction roles"),
            ("/autorespond add <trigger> <response>", "Add an auto-responder"),
            ("/autorespond remove <trigger>", "Remove an auto-responder"),
            ("/autorespond list", "List auto-responders"),
            ("/customcmd add <name> <response>", "Add a custom command"),
            ("/customcmd remove <name>", "Remove a custom command"),
            ("/customcmd list", "List custom commands"),
            ("/starboard setup <channel> [threshold]", "Setup starboard"),
            ("/starboard ignore #channel", "Ignore a channel"),
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
            ("/membercount", "Member count breakdown"),
        ],
    },
}


# ==================== Help View with Select dropdown ====================

class HelpSelect(discord.ui.Select):
    """Dropdown for picking a help category."""

    def __init__(self, parent_view: "HelpView"):
        self.parent_view = parent_view
        options = []
        for key, cat in CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat['name'],
                value=key,
                description=cat['desc'][:100],
                emoji=cat['emoji'],
            ))
        super().__init__(
            placeholder="Choose a category to view its commands...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            selected = self.values[0]
        except (IndexError, AttributeError):
            return
        self.parent_view.current_category = selected
        self.parent_view.current_page = 0
        embeds = self.parent_view.build_category_embeds(selected)
        self.parent_view.current_embeds = embeds
        # Rebuild view: keep select + home button + pagination buttons if needed
        self.parent_view._rebuild_view()
        try:
            await interaction.response.edit_message(
                embed=embeds[0], view=self.parent_view
            )
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except Exception:
            pass


class HelpView(discord.ui.View):
    """Main help view: Select dropdown + Home button + pagination."""

    def __init__(self, bot, author_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.current_category = None  # None = on home page
        self.current_page = 0
        self.current_embeds = []  # list of embeds for the current category

        # Add the select dropdown
        self.select = HelpSelect(self)
        self.add_item(self.select)

        # Add Home button
        home_btn = discord.ui.Button(
            label="Home", emoji="🏠", style=discord.ButtonStyle.primary, row=1
        )
        home_btn.callback = self.home_callback
        self.home_btn = home_btn
        self.add_item(home_btn)

        # Pagination buttons (only added when needed)
        self.prev_btn = None
        self.next_btn = None

    def build_home_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="cyn — commands",
            description="pick a category from the dropdown below to see its commands.",
            color=COLOR_DEFAULT,
            timestamp=datetime.utcnow()
        )
        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        for key, cat in CATEGORIES.items():
            count = len(cat['commands'])
            embed.add_field(
                name=f"{cat['emoji']} {cat['name']}",
                value=f"{cat['desc']}\n`{count} commands`",
                inline=True
            )
        total = sum(len(c['commands']) for c in CATEGORIES.values())
        embed.set_footer(
            text=f"{total} total commands — dropdown expires in 3 minutes",
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )
        return embed

    def build_category_embeds(self, key: str) -> list:
        """Build a list of embeds for a category. If >10 commands, split
        into multiple pages of ~10 each."""
        cat = CATEGORIES[key]
        color = cat.get('color', COLOR_DEFAULT)
        commands = cat['commands']
        pages = []

        # Split into chunks of 10
        chunk_size = 10
        chunks = [commands[i:i + chunk_size] for i in range(0, len(commands), chunk_size)]
        if not chunks:
            chunks = [[]]

        total_pages = len(chunks)
        for page_idx, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=f"{cat['emoji']} {cat['name']}",
                description=cat['desc'],
                color=color,
                timestamp=datetime.utcnow()
            )
            commands_text = ""
            for cmd, desc in chunk:
                commands_text += f"`{cmd}`\n{desc}\n\n"
            if commands_text:
                # Use a single field to avoid field count limits
                embed.add_field(
                    name=f"Commands (page {page_idx + 1}/{total_pages})",
                    value=commands_text[:1024],
                    inline=False
                )
            embed.set_footer(
                text=f"click 🏠 Home to return · {len(commands)} total commands in {cat['name']}",
                icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
            )
            pages.append(embed)
        return pages

    def _rebuild_view(self):
        """Rebuild the view: keep select + home, add pagination if >1 page."""
        self.clear_items()
        # Re-add select (row 0)
        self.select = HelpSelect(self)
        # Reset placeholder since user just selected
        self.select.placeholder = f"Viewing: {CATEGORIES.get(self.current_category, {}).get('name', '...')}"
        self.add_item(self.select)
        # Re-add home button (row 1)
        self.add_item(self.home_btn)

        # Add pagination buttons if multiple pages
        if len(self.current_embeds) > 1:
            prev_btn = discord.ui.Button(
                label="◀", style=discord.ButtonStyle.secondary, row=1,
                disabled=(self.current_page == 0)
            )
            prev_btn.callback = self.prev_callback
            self.prev_btn = prev_btn
            self.add_item(prev_btn)

            next_btn = discord.ui.Button(
                label="▶", style=discord.ButtonStyle.secondary, row=1,
                disabled=(self.current_page >= len(self.current_embeds) - 1)
            )
            next_btn.callback = self.next_callback
            self.next_btn = next_btn
            self.add_item(next_btn)

    async def home_callback(self, interaction: discord.Interaction):
        self.current_category = None
        self.current_page = 0
        self.current_embeds = []
        # Rebuild view: just select + home
        self.clear_items()
        self.select = HelpSelect(self)
        self.add_item(self.select)
        self.add_item(self.home_btn)
        embed = self.build_home_embed()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except Exception:
            pass

    async def prev_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._rebuild_view()
            try:
                await interaction.response.edit_message(
                    embed=self.current_embeds[self.current_page], view=self
                )
            except (discord.NotFound, discord.InteractionResponded):
                pass
            except Exception:
                pass
        else:
            try:
                await interaction.response.defer()
            except Exception:
                pass

    async def next_callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.current_embeds) - 1:
            self.current_page += 1
            self._rebuild_view()
            try:
                await interaction.response.edit_message(
                    embed=self.current_embeds[self.current_page], view=self
                )
            except (discord.NotFound, discord.InteractionResponded):
                pass
            except Exception:
                pass
        else:
            try:
                await interaction.response.defer()
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            try:
                await interaction.response.send_message(
                    "this isn't your help menu.", ephemeral=True
                )
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

    @app_commands.command(name="help", description="Show all commands or get help for a specific command")
    async def help(self, interaction: discord.Interaction, command: str = None):
        self.bot.increment_command('help')
        if command:
            # Look up specific command across all cogs
            cmd_obj = None
            for c in self.bot.tree.get_commands():
                if c.name == command.lower():
                    cmd_obj = c
                    break
                if hasattr(c, 'commands'):
                    for sub in c.commands:
                        full = f"{c.name} {sub.name}"
                        if full == command.lower() or sub.name == command.lower():
                            cmd_obj = sub
                            cmd_obj._full_name = full
                            break

            if not cmd_obj:
                try:
                    await interaction.response.send_message(
                        f"no command named `{command}` found.", ephemeral=True
                    )
                except Exception:
                    pass
                return

            name = getattr(cmd_obj, '_full_name', cmd_obj.name)
            desc = cmd_obj.description or "no description"
            embed = discord.Embed(
                title=f"📖 /{name}",
                description=desc,
                color=COLOR_INFO,
                timestamp=datetime.utcnow()
            )
            params = []
            if hasattr(cmd_obj, 'parameters'):
                for p in cmd_obj.parameters:
                    req = "required" if p.required else "optional"
                    params.append(f"`{p.name}` ({req}) — {p.description or 'no description'}")
            if hasattr(cmd_obj, '_params'):
                for p in cmd_obj._params.values():
                    req = "required" if p.required else "optional"
                    params.append(f"`{p.name}` ({req}) — {p.description or 'no description'}")
            if params:
                embed.add_field(name="Parameters", value="\n".join(params), inline=False)

            checks = getattr(cmd_obj, 'checks', [])
            perm_text = "none required"
            for check in checks:
                check_name = getattr(check, '__qualname__', '') or getattr(check, '__name__', '')
                if 'permission' in check_name.lower() or 'is_owner' in check_name or 'is_mod' in check_name or 'is_admin' in check_name:
                    perm_text = "requires specific permissions (see command)"
                    break
            embed.add_field(name="Permissions", value=perm_text, inline=False)
            embed.add_field(name="Example", value=f"`/{name}`", inline=False)
            embed.set_footer(text="cyn help system")
            try:
                await interaction.response.send_message(embed=embed)
            except Exception:
                pass
            return

        view = HelpView(self.bot, interaction.user.id)
        embed = view.build_home_embed()
        try:
            await interaction.response.send_message(embed=embed, view=view)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
