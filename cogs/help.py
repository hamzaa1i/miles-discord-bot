"""
cogs/help.py — interactive button-based help system.

Replaces the old HelpView that used to live in main.py.
/help opens an embed with category buttons; each button opens a new
embed listing the commands in that category.
/help [command] shows detailed help for a specific command.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime


CATEGORIES = {
    "ai": {
        "emoji": "🤖",
        "name": "AI",
        "desc": "AI chat and AI-powered features",
        "commands": [
            ("@ao <message>", "Chat naturally with ao via mention"),
            ("/chat <message>", "Slash-command AI conversation"),
            ("/ask <question>", "Ask ao anything"),
            ("/clear_chat", "Reset your conversation memory"),
            ("/quote", "Get a dark quote"),
            ("/roast [user]", "AI-generated savage roast"),
            ("/summarize <text>", "Summarize text in 3-5 bullets"),
            ("/translate <language> <text>", "Translate text to a language"),
            ("/explain <topic>", "Explain a topic like you're 12"),
            ("/code <language> <description>", "Generate a code snippet"),
            ("/debug <code>", "Find bugs in your code"),
            ("/story <prompt>", "AI writes a 150-200 word story"),
            ("/poem <topic>", "AI writes an 8-12 line poem"),
            ("/advice <situation>", "Blunt, sarcastic advice"),
            ("/define <word>", "Define a word + etymology + example"),
            ("/tldr", "TLDR of last 15 channel messages"),
            ("/roast_server", "AI roasts the current server"),
            ("/aipoll <topic>", "AI generates a poll question about a topic"),
        ],
    },
    "fun": {
        "emoji": "🎉",
        "name": "Fun",
        "desc": "Entertainment and quick laughs",
        "commands": [
            ("/joke", "Random joke (50+)"),
            ("/meme", "Random meme from r/all"),
            ("/compliment [user]", "AI-generated funny compliment"),
            ("/pickup", "Random pickup line (40+)"),
            ("/wouldyourather", "Random WYR question (40+)"),
            ("/fact", "Random fact (60+)"),
            ("/quote", "Dark quote (50+)"),
            ("/roll [sides=6]", "Roll a dice"),
            ("/flip", "Flip a coin"),
            ("/8ball <question>", "Magic 8-ball (20 responses)"),
            ("/rate <thing>", "AI rates the thing /10"),
            ("/ship <u1> <u2>", "Ship two users"),
            ("/hack <user>", "Fake 'hacking' animation"),
            ("/howsmart [user]", "How smart is the user?"),
            ("/roastme", "Roast yourself"),
            ("/mock <text>", "aLtErNaTiNg case"),
            ("/clap <text>", "adds 👏 between every word"),
            ("/reverse <text>", "Reverse the text"),
            ("/say <text>", "Bot sends text (Manage Messages)"),
            ("/ascii <text>", "ASCII art from text"),
            ("/truth", "Truth question (40+)"),
            ("/dare", "Dare challenge (40+)"),
            ("/emojify <text>", "Letters to regional indicator emojis"),
            ("/choose <a> <b>", "Bot chooses for you"),
            ("/topic", "Conversation starter"),
            ("/would <a> <b>", "Custom WYR with reactions"),
        ],
    },
    "games": {
        "emoji": "🎮",
        "name": "Games",
        "desc": "Interactive games with buttons",
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
        "commands": [
            ("/balance [user]", "Check wallet & bank"),
            ("/daily", "Daily reward + streak bonus"),
            ("/work", "Work for coins (1h cooldown)"),
            ("/pay <user> <amount>", "Send coins to someone"),
            ("/shop", "Browse the item shop"),
            ("/buy <item>", "Purchase an item"),
            ("/inventory [user]", "View your items"),
            ("/profile [user]", "Your full economy profile"),
            ("/richest", "Top 10 richest users"),
            ("/earn fish", "Go fishing"),
            ("/earn hunt", "Go hunting"),
            ("/earn mine", "Mine for gems"),
            ("/earn beg", "Beg for coins"),
            ("/earn crime", "Attempt a crime"),
            ("/earn rob <user>", "Rob someone"),
            ("/bank deposit <amount>", "Deposit coins to bank"),
            ("/bank withdraw <amount>", "Withdraw from bank"),
            ("/eco_admin set", "Set balance (Admin)"),
        ],
    },
    "leveling": {
        "emoji": "⭐",
        "name": "Leveling",
        "desc": "XP and leveling system",
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
        ],
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
            ("/mod warn list <user>", "Show all warnings for a user"),
            ("/mod warn clear <user>", "Clear all warnings for a user"),
            ("/mod purge <amount>", "Delete messages"),
            ("/mod nuke", "Clone & delete the channel"),
            ("/mod role add <user> <role>", "Add a role to a user"),
            ("/mod role remove <user> <role>", "Remove a role from a user"),
            ("/mod nickname <user> [nick]", "Change nickname"),
            ("/mod softban <user> [reason]", "Ban then unban to wipe messages"),
            ("/mod slowmode [seconds=0]", "Set channel slowmode"),
            ("/mod lock [reason]", "Lock channel for @everyone"),
            ("/mod unlock", "Unlock channel"),
            ("/mod logs", "View moderation logs"),
            ("/antispam", "Configure anti-spam (Admin)"),
            ("/filter_add <word>", "Add filtered word"),
            ("/filter_remove <word>", "Remove filtered word"),
            ("/filter_list", "List filtered words"),
        ],
    },
    "utility": {
        "emoji": "🔧",
        "name": "Utility",
        "desc": "Handy everyday commands",
        "commands": [
            ("/weather <city>", "Current weather for a city"),
            ("/math <expression>", "Safely evaluate a math expression"),
            ("/password [length=16]", "Generate a secure password"),
            ("/encode <type> <text>", "Encode to base64/binary/hex"),
            ("/decode <type> <text>", "Decode from base64/binary/hex"),
            ("/timestamp <datetime>", "Get Discord timestamp formats"),
            ("/snipe", "Last deleted message in this channel"),
            ("/editsnipe", "Last edited message in this channel"),
            ("/afk [reason]", "Set your AFK status"),
            ("/firstmessage", "First message in channel"),
            ("/botinfo", "Bot information"),
            ("/uptime", "Bot uptime"),
            ("/ping", "Websocket latency"),
            ("/remind <time> <task>", "Set a reminder"),
            ("/note <text>", "Save a quick note"),
            ("/notes", "View your notes"),
        ],
    },
    "music": {
        "emoji": "🎵",
        "name": "Music",
        "desc": "Music playback (if available)",
        "commands": [
            ("/play <query>", "Play a song"),
            ("/pause", "Pause playback"),
            ("/resume", "Resume playback"),
            ("/skip", "Skip the current song"),
            ("/stop", "Stop and clear queue"),
            ("/queue", "View the queue"),
            ("/nowplaying", "Currently playing song"),
            ("/volume <0-100>", "Set volume"),
        ],
    },
    "settings": {
        "emoji": "⚙️",
        "name": "Settings",
        "desc": "Welcome, logging, reaction roles, auto-responder",
        "commands": [
            ("/welcome channel #channel", "Set welcome channel"),
            ("/welcome message [text]", "Set welcome message"),
            ("/welcome toggle <enabled>", "Enable/disable welcomes"),
            ("/welcome test", "Trigger a test welcome"),
            ("/goodbye channel #channel", "Set goodbye channel"),
            ("/goodbye message [text]", "Set goodbye message"),
            ("/goodbye toggle <enabled>", "Enable/disable goodbyes"),
            ("/autorole [role]", "Set the role auto-assigned on join"),
            ("/setlog #channel", "Set the logging channel"),
            ("/log toggle <event_type>", "Toggle a log event"),
            ("/log list", "View log event statuses"),
            ("/reactionrole add <id> <emoji> <role>", "Add a reaction role"),
            ("/reactionrole remove <id> <emoji>", "Remove a reaction role"),
            ("/reactionrole list", "List reaction roles"),
            ("/buttonrole create <channel> <title> <desc>", "Create button-role prompt"),
            ("/buttonrole addbutton <id> <role> <label>", "Add a button"),
            ("/autorespond add <trigger> <response>", "Add an auto-responder"),
            ("/autorespond remove <trigger>", "Remove an auto-responder"),
            ("/autorespond list", "List auto-responders"),
            ("/customcmd add <name> <response>", "Add a custom command"),
            ("/customcmd remove <name>", "Remove a custom command"),
            ("/customcmd list", "List custom commands"),
            ("/starboard setup <channel> [threshold]", "Setup starboard"),
            ("/starboard emoji <emoji>", "Change star emoji"),
            ("/starboard threshold <n>", "Change star threshold"),
            ("/starboard ignore #channel", "Ignore a channel"),
            ("/starboard unignore #channel", "Stop ignoring a channel"),
        ],
    },
    "community": {
        "emoji": "📋",
        "name": "Community",
        "desc": "Giveaways, suggestions, polls, birthdays, counting, rep, marriage",
        "commands": [
            ("/giveaway start <dur> <winners> <prize> [#chan]", "Start a giveaway (dur: 10s/5m/2h/1d)"),
            ("/giveaway end <message_id>", "Force-end a giveaway"),
            ("/giveaway reroll <message_id>", "Pick a new winner"),
            ("/giveaway list", "List active giveaways"),
            ("/suggest setup #channel", "Set suggestions channel"),
            ("/suggest submit <text>", "Submit a suggestion"),
            ("/suggest approve <id> [reason]", "Approve (mod)"),
            ("/suggest deny <id> [reason]", "Deny (mod)"),
            ("/suggest list", "List pending suggestions"),
            ("/poll create <q> <o1> <o2> [o3] [o4] [dur]", "Create a poll"),
            ("/poll end <message_id>", "End a poll early"),
            ("/poll results <message_id>", "Show poll results"),
            ("/birthday set <month> <day>", "Set your birthday"),
            ("/birthday remove", "Remove your birthday"),
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
            ("/marry_status", "Check your own marriage status"),
            ("/ticket_setup", "Setup ticket system (Admin)"),
            ("/ticket_close", "Close current ticket"),
            ("/toggledms", "Toggle DMs from ao"),
        ],
    },
    "other": {
        "emoji": "📦",
        "name": "Other",
        "desc": "Legacy + misc commands",
        "commands": [
            ("/suggestions_setup #channel", "Legacy: setup suggestions"),
            ("/suggestion_approve <id>", "Legacy: approve suggestion"),
            ("/suggestion_deny <id>", "Legacy: deny suggestion"),
            ("/starboard_setup", "Legacy: setup starboard"),
            ("/starboard_toggle <enabled>", "Legacy: toggle starboard"),
            ("/birthday_set <m> <d>", "Legacy: set birthday"),
            ("/birthday_setup #channel", "Legacy: set birthday channel"),
            ("/birthday [@user]", "Legacy: check birthday"),
            ("/birthdays", "Legacy: list birthdays"),
            ("/counting_setup #channel", "Legacy: setup counting"),
            ("/count", "Legacy: current count"),
            ("/repcheck [@user]", "Legacy: check reputation"),
            ("/replb", "Legacy: rep leaderboard"),
            ("/spouse [@user]", "Legacy: marriage status"),
            ("/multipoll <q> <o1> <o2> [o3] [o4]", "Legacy: multi-option poll"),
            ("/music", "Music feature availability"),
        ],
    },
}


class HelpView(discord.ui.View):
    def __init__(self, bot, author_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.current_page = "main"

    def build_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="ao — commands",
            description="pick a category below to see its commands.",
            color=0x1a1a2e,
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
            text=f"{total} total commands — buttons expire in 2 minutes",
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )
        return embed

    def build_category_embed(self, key: str) -> discord.Embed:
        cat = CATEGORIES[key]
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
                    embed.add_field(name="Commands" if first else "\u200b", value=chunk, inline=False)
                    chunk = line
                    first = False
                else:
                    chunk += line
            if chunk:
                embed.add_field(name="Commands" if first else "\u200b", value=chunk, inline=False)

        embed.set_footer(
            text="click Back to return to categories",
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("this isn't your help menu.", ephemeral=True)
            return False
        return True

    def update_buttons(self, page: str):
        self.clear_items()
        if page == "main":
            keys = list(CATEGORIES.keys())
            row0 = keys[:5]
            row1 = keys[5:]
            for key in row0:
                cat = CATEGORIES[key]
                btn = discord.ui.Button(
                    label=cat['name'],
                    emoji=cat['emoji'],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"cat_{key}",
                    row=0
                )
                btn.callback = self.make_category_callback(key)
                self.add_item(btn)
            for key in row1:
                cat = CATEGORIES[key]
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
                # Check subcommands (groups)
                if hasattr(c, 'commands'):
                    for sub in c.commands:
                        full = f"{c.name} {sub.name}"
                        if full == command.lower() or sub.name == command.lower():
                            cmd_obj = sub
                            cmd_obj._full_name = full
                            break

            if not cmd_obj:
                await interaction.response.send_message(f"no command named `{command}` found.", ephemeral=True)
                return

            name = getattr(cmd_obj, '_full_name', cmd_obj.name)
            desc = cmd_obj.description or "no description"
            embed = discord.Embed(
                title=f"📖 /{name}",
                description=desc,
                color=0x1a1a2e,
                timestamp=datetime.utcnow()
            )
            # Parameters
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

            # Check permissions
            checks = getattr(cmd_obj, 'checks', [])
            perm_text = "none required"
            for check in checks:
                check_name = getattr(check, '__name__', '')
                if 'has_permissions' in check_name or 'permission' in check_name.lower():
                    perm_text = "requires specific permissions (see command)"
                    break
            embed.add_field(name="Permissions", value=perm_text, inline=False)
            embed.add_field(name="Example", value=f"`/{name}`", inline=False)
            embed.set_footer(text="ao help system")
            await interaction.response.send_message(embed=embed)
            return

        view = HelpView(self.bot, interaction.user.id)
        view.update_buttons("main")
        embed = view.build_main_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
