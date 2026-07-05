"""
cogs/games.py — interactive games using discord.ui.

Includes: /rps, /ttt, /numguess, /typerace, /reaction, /wordle,
/blackjack, /coinflip, /slots.

Economy integration: blackjack/coinflip/slots read & write the user's
balance via the Economy cog (data/economy.json).
"""
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
import os
import aiohttp

from utils.database import Database


# ==================== shared economy helper ====================
def _get_economy(bot, user_id):
    eco = bot.get_cog('Economy')
    if not eco:
        return None, None, None
    data = eco.get_user_data(user_id)
    return eco, data, data.get('balance', 0)


def _save_economy(bot, user_id, data):
    eco = bot.get_cog('Economy')
    if eco:
        eco.save_user_data(user_id, data)


# ==================== RPS ====================
class RPSView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player
        self.result_msg = ""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("this isn't your game.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.primary, row=0)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.primary, row=0)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.primary, row=0)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "scissors")

    async def resolve(self, interaction: discord.Interaction, choice: str):
        bot_choice = random.choice(["rock", "paper", "scissors"])
        emoji = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        if choice == bot_choice:
            result = "Tie."
            color = discord.Color.orange()
        elif (
            (choice == "rock" and bot_choice == "scissors") or
            (choice == "paper" and bot_choice == "rock") or
            (choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win."
            color = discord.Color.green()
        else:
            result = "I win."
            color = discord.Color.red()

        embed = discord.Embed(description=result, color=color)
        embed.add_field(name="You", value=f"{emoji[choice]} {choice.title()}", inline=True)
        embed.add_field(name="cyn", value=f"{emoji[bot_choice]} {bot_choice.title()}", inline=True)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ==================== Tic Tac Toe ====================
class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=60)
        self.players = [player1, player2]
        self.current = 0
        self.board = [["" for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                btn = discord.ui.Button(label="\u200b", style=discord.ButtonStyle.secondary, row=i)
                btn.callback = self.make_callback(i, j)
                self.add_item(btn)

    def make_callback(self, i, j):
        async def callback(interaction: discord.Interaction):
            await self.handle_click(interaction, i, j)
        return callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.players[self.current].id:
            await interaction.response.send_message(
                f"wait your turn. it's {self.players[self.current].mention}'s move.",
                ephemeral=True
            )
            return False
        return True

    async def handle_click(self, interaction: discord.Interaction, i: int, j: int):
        if self.board[i][j] != "":
            await interaction.response.send_message("square already taken.", ephemeral=True)
            return
        symbol = "X" if self.current == 0 else "O"
        self.board[i][j] = symbol
        # Update button
        idx = i * 3 + j
        btn = self.children[idx]
        btn.label = symbol
        btn.disabled = True
        btn.style = discord.ButtonStyle.success if symbol == "X" else discord.ButtonStyle.danger

        # Check win
        if self.check_win(symbol):
            for child in self.children:
                child.disabled = True
            embed = discord.Embed(
                description=f"🏆 {self.players[self.current].mention} wins!",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        # Check draw
        if all(self.board[r][c] != "" for r in range(3) for c in range(3)):
            for child in self.children:
                child.disabled = True
            embed = discord.Embed(description="It's a draw.", color=discord.Color.orange())
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            return

        # Switch
        self.current = 1 - self.current
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        # Reset the timeout window each move
        self.message_created_at = time.time()

    def check_win(self, sym: str) -> bool:
        for i in range(3):
            if all(self.board[i][j] == sym for j in range(3)):
                return True
            if all(self.board[j][i] == sym for j in range(3)):
                return True
        if all(self.board[i][i] == sym for i in range(3)):
            return True
        if all(self.board[i][2 - i] == sym for i in range(3)):
            return True
        return False

    def _build_embed(self):
        embed = discord.Embed(
            title="Tic Tac Toe",
            description=f"Turn: **{self.players[self.current].display_name}** ({'X' if self.current == 0 else 'O'})",
            color=0x1a1a2e
        )
        return embed

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, 'message'):
            try:
                await self.message.edit(view=self)
            except:
                pass


# ==================== Blackjack ====================
def card_value(card):
    rank = card.split()[0]
    if rank in ('K', 'Q', 'J'):
        return 10
    if rank == 'A':
        return 11
    return int(rank)


def card_str(rank, suit):
    return f"{rank} {suit}"


def hand_value(cards):
    total = sum(card_value(c) for c in cards)
    aces = sum(1 for c in cards if c.startswith('A '))
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def draw_card():
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    suits = ['♠️', '♥️', '♦️', '♣️']
    return card_str(random.choice(ranks), random.choice(suits))


class BlackjackView(discord.ui.View):
    def __init__(self, user: discord.Member, bet: int, bot):
        super().__init__(timeout=120)
        self.user = user
        self.bet = bet
        self.bot = bot
        self.player = [draw_card(), draw_card()]
        self.dealer = [draw_card(), draw_card()]
        self.finished = False

        # If player has 21 immediately, finish
        if hand_value(self.player) == 21:
            self.finished = True

    def build_embed(self) -> discord.Embed:
        pv = hand_value(self.player)
        dv = hand_value(self.dealer)
        if self.finished:
            dealer_str = " · ".join(self.dealer) + f"  ({dv})"
            color = discord.Color.green() if pv > 21 or (dv > 21 and pv <= 21) or (pv <= 21 and pv > dv and dv <= 21) else (
                discord.Color.red() if pv > 21 or pv < dv <= 21 else discord.Color.orange()
            )
            # Determine outcome more simply
            if pv > 21:
                outcome = "bust. you lose."
                color = discord.Color.red()
            elif dv > 21:
                outcome = "dealer busts. you win!"
                color = discord.Color.green()
            elif pv > dv:
                outcome = "you win!"
                color = discord.Color.green()
            elif pv < dv:
                outcome = "dealer wins."
                color = discord.Color.red()
            else:
                outcome = "push. tie."
                color = discord.Color.orange()
            embed = discord.Embed(title="🃏 Blackjack", color=color)
            embed.add_field(name="Your hand", value=" · ".join(self.player) + f"  ({pv})", inline=False)
            embed.add_field(name="Dealer", value=dealer_str, inline=False)
            embed.add_field(name="Result", value=outcome, inline=False)
            return embed
        else:
            dealer_hidden = f"{self.dealer[0]} · ❓"
            embed = discord.Embed(title="🃏 Blackjack", color=0x1a1a2e)
            embed.add_field(name="Your hand", value=" · ".join(self.player) + f"  ({pv})", inline=False)
            embed.add_field(name="Dealer", value=dealer_hidden, inline=False)
            embed.set_footer(text=f"bet: {self.bet} coins" if self.bet > 0 else "playing for fun")
            return embed

    async def resolve(self, interaction: discord.Interaction):
        # Dealer draws to 17
        while hand_value(self.dealer) < 17:
            self.dealer.append(draw_card())
        self.finished = True

        # Process payout
        pv = hand_value(self.player)
        dv = hand_value(self.dealer)
        if self.bet > 0:
            eco, data, _ = _get_economy(self.bot, self.user.id)
            if eco:
                if pv > 21:
                    data['balance'] = data.get('balance', 0) - self.bet
                elif dv > 21 or pv > dv:
                    data['balance'] = data.get('balance', 0) + self.bet
                elif pv < dv:
                    data['balance'] = data.get('balance', 0) - self.bet
                # tie: no change
                _save_economy(self.bot, self.user.id, data)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, row=0)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("not your game.", ephemeral=True)
            return
        self.player.append(draw_card())
        if hand_value(self.player) >= 21:
            await self.resolve(interaction)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, row=0)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("not your game.", ephemeral=True)
            return
        await self.resolve(interaction)


# ==================== Games Cog ====================
class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory state for games (per-channel)
        self.active_numguess = {}  # channel_id -> { 'target': n, 'attempts': int, 'user_id': id }
        self.active_typerace = {}  # channel_id -> { 'sentence': str, 'start': ts }
        self.active_wordle = {}    # user_id -> { 'word': str, 'guesses': [], 'over': bool }

        # 100+ common 5-letter words for wordle
        self.wordle_words = [
            "apple", "bread", "crane", "drive", "eagle", "flame", "grape", "house",
            "ivory", "juice", "knife", "lemon", "mango", "noble", "ocean", "piano",
            "queen", "river", "stone", "table", "ultra", "vivid", "water", "xenon",
            "yacht", "zebra", "abide", "blame", "clash", "drain", "elite", "flock",
            "gloom", "haste", "ionic", "joker", "kneel", "latch", "mirth", "nurse",
            "oasis", "plaid", "quirk", "rusty", "sworn", "tense", "unite", "vault",
            "witty", "xerox", "yield", "zonal", "brave", "crisp", "doubt", "empty",
            "frail", "gravy", "horde", "input", "jealous"[0:5], "knack", "lunar",
            "marsh", "nerve", "onion", "pride", "quote", "ridge", "slash", "trace",
            "union", "vowel", "whirl", "xylem", "young", "zesty", "blush", "choir",
            "dwarf", "enemy", "fjord", "giant", "honey", "ideal", "jewel", "karma",
            "light", "moist", "novel", "olive", "peace", "quart", "reuse", "shade",
            "trust", "udder", "vague", "wheat", "xylic", "yodel", "zilch", "bingo",
            "chunk", "delay", "extra", "fresh", "giddy", "happy", "infer", "jolly",
        ]
        # Sanitize list (remove non-5-letter entries)
        self.wordle_words = [w for w in self.wordle_words if isinstance(w, str) and len(w) == 5 and w.isalpha()]

    @app_commands.command(name="rps", description="Rock Paper Scissors with buttons")
    async def rps(self, interaction: discord.Interaction):
        self.bot.increment_command('rps')
        view = RPSView(interaction.user)
        embed = discord.Embed(
            title="🪨 📄 ✂️ Rock Paper Scissors",
            description=f"{interaction.user.mention}, pick your move.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="ttt", description="Tic Tac Toe against another user")
    async def ttt(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('ttt')
        # FIX 13 — only block if the target IS the bot itself (user.bot is True AND user.id == bot's id)
        # Other users with .bot=True are webhook/bot accounts — we block those too
        if user.id == interaction.client.user.id:
            try:
                await interaction.response.send_message("can't play against me. pick a human.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("can't play against me. pick a human.", ephemeral=True)
            return
        if user.id == interaction.user.id:
            try:
                await interaction.response.send_message("can't play against yourself.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("can't play against yourself.", ephemeral=True)
            return
        view = TicTacToeView(interaction.user, user)
        embed = view._build_embed()
        try:
            await interaction.response.send_message(embed=embed, view=view)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="numguess", description="Number guessing game (1-100)")
    async def numguess(self, interaction: discord.Interaction):
        self.bot.increment_command('numguess')
        target = random.randint(1, 100)
        channel_id = interaction.channel.id
        self.active_numguess[channel_id] = {
            'target': target,
            'attempts': 0,
            'user_id': interaction.user.id,
            'over': False
        }
        embed = discord.Embed(
            title="🔢 Number Guess",
            description=(
                f"{interaction.user.mention}, I'm thinking of a number between 1 and 100.\n"
                "Type your guesses in this channel. Type `quit` to give up.\n"
                "30 seconds per guess."
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

        def check(m):
            if m.channel.id != channel_id:
                return False
            if m.author.id != interaction.user.id:
                return False
            if m.author.bot:
                return False
            content = m.content.strip().lower()
            return content == 'quit' or content.isdigit()

        while not self.active_numguess[channel_id]['over']:
            try:
                msg = await self.bot.wait_for('message', timeout=30.0, check=check)
            except asyncio.TimeoutError:
                try:
                    await interaction.channel.send(f"{interaction.user.mention} you took too long. game over. the number was **{target}**.")
                except:
                    pass
                self.active_numguess.pop(channel_id, None)
                return

            content = msg.content.strip().lower()
            if content == 'quit':
                await interaction.channel.send(f"quitting. the number was **{target}**.")
                self.active_numguess.pop(channel_id, None)
                return

            guess = int(content)
            self.active_numguess[channel_id]['attempts'] += 1
            attempts = self.active_numguess[channel_id]['attempts']

            if guess == target:
                await interaction.channel.send(
                    f"🎉 {interaction.user.mention} got it in **{attempts}** attempts! the number was **{target}**."
                )
                self.active_numguess.pop(channel_id, None)
                return
            elif guess < target:
                await interaction.channel.send(f"📈 higher. (attempt {attempts})")
            else:
                await interaction.channel.send(f"📉 lower. (attempt {attempts})")

    @app_commands.command(name="typerace", description="Typing race — first to type the sentence wins")
    async def typerace(self, interaction: discord.Interaction):
        self.bot.increment_command('typerace')
        fun_cog = self.bot.get_cog('Fun')
        sentences = getattr(fun_cog, 'typerace_sentences', None) if fun_cog else None
        if not sentences:
            sentences = [
                "the quick brown fox jumps over the lazy dog.",
                "to be or not to be that is the question.",
                "a journey of a thousand miles begins with a single step.",
            ]
        sentence = random.choice(sentences)
        channel_id = interaction.channel.id
        start = time.time()
        self.active_typerace[channel_id] = {'sentence': sentence, 'start': start}

        embed = discord.Embed(
            title="⌨️ Typerace",
            description=(
                f"Type this sentence exactly:\n\n```\n{sentence}\n```\n\n"
                "First person to type it correctly wins."
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

        def check(m):
            if m.channel.id != channel_id:
                return False
            if m.author.bot:
                return False
            return m.content.strip() == sentence

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await interaction.channel.send("no one typed it in time. race over.")
            self.active_typerace.pop(channel_id, None)
            return

        elapsed = time.time() - start
        await interaction.channel.send(
            f"🏆 {msg.author.mention} won in **{elapsed:.2f}s**!"
        )
        self.active_typerace.pop(channel_id, None)

    @app_commands.command(name="reaction", description="Reaction time test")
    async def reaction(self, interaction: discord.Interaction):
        self.bot.increment_command('reaction')
        delay = random.uniform(2.0, 5.0)
        embed = discord.Embed(
            description="get ready...",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        await asyncio.sleep(delay)
        start = time.time()
        await msg.edit(content=None, embed=discord.Embed(description="GO! 🟢", color=discord.Color.green()))

        def check(r, u):
            return r.message.id == msg.id and str(r.emoji) == "✅" and not u.bot

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=10.0, check=check)
        except asyncio.TimeoutError:
            await interaction.channel.send("no one reacted. game over.")
            return

        elapsed_ms = int((time.time() - start) * 1000)
        await interaction.channel.send(f"⚡ {user.mention} reacted in **{elapsed_ms}ms**!")

    @app_commands.command(name="wordle", description="Wordle clone — guess the 5-letter word in 6 tries")
    async def wordle(self, interaction: discord.Interaction):
        self.bot.increment_command('wordle')
        word = random.choice(self.wordle_words).lower()
        self.active_wordle[interaction.user.id] = {
            'word': word,
            'guesses': [],
            'over': False
        }

        embed = discord.Embed(
            title="🟩 Wordle",
            description=(
                f"{interaction.user.mention}, I picked a 5-letter word.\n"
                "Type your guesses in this channel. You have 6 tries.\n"
                "Type `quit` to give up.\n"
                "🟩 = correct position · 🟨 = wrong position · ⬛ = not in word"
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

        def check(m):
            if m.channel.id != interaction.channel.id:
                return False
            if m.author.id != interaction.user.id:
                return False
            if m.author.bot:
                return False
            c = m.content.strip().lower()
            return c == 'quit' or (len(c) == 5 and c.isalpha())

        state = self.active_wordle[interaction.user.id]
        while not state['over'] and len(state['guesses']) < 6:
            try:
                msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await interaction.channel.send("timed out. game over.")
                self.active_wordle.pop(interaction.user.id, None)
                return

            guess = msg.content.strip().lower()
            if guess == 'quit':
                await interaction.channel.send(f"quitting. the word was **{state['word']}**.")
                self.active_wordle.pop(interaction.user.id, None)
                return

            state['guesses'].append(guess)

            # Build grid
            grid = ""
            for g in state['guesses']:
                row = ""
                for i, ch in enumerate(g):
                    if ch == state['word'][i]:
                        row += "🟩"
                    elif ch in state['word']:
                        row += "🟨"
                    else:
                        row += "⬛"
                grid += f"{g.upper()}  →  {row}\n"

            if guess == state['word']:
                embed = discord.Embed(
                    title="🟩 Wordle",
                    description=f"🎉 {interaction.user.mention} got it in **{len(state['guesses'])}/6**!\n\n```\n{grid}\n```",
                    color=discord.Color.green()
                )
                await interaction.channel.send(embed=embed)
                self.active_wordle.pop(interaction.user.id, None)
                return

            remaining = 6 - len(state['guesses'])
            embed = discord.Embed(
                title="🟩 Wordle",
                description=f"{remaining} guesses left.\n\n```\n{grid}\n```",
                color=0x1a1a2e
            )
            await interaction.channel.send(embed=embed)

        # Out of guesses
        grid = ""
        for g in state['guesses']:
            row = ""
            for i, ch in enumerate(g):
                if ch == state['word'][i]:
                    row += "🟩"
                elif ch in state['word']:
                    row += "🟨"
                else:
                    row += "⬛"
            grid += f"{g.upper()}  →  {row}\n"
        embed = discord.Embed(
            title="🟩 Wordle",
            description=f"out of guesses. the word was **{state['word']}**.\n\n```\n{grid}\n```",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed)
        self.active_wordle.pop(interaction.user.id, None)

    @app_commands.command(name="blackjack", description="Play blackjack (optional bet)")
    async def blackjack(self, interaction: discord.Interaction, bet: int = 0):
        self.bot.increment_command('blackjack')
        if bet < 0:
            await interaction.response.send_message("bet must be 0 or positive.", ephemeral=True)
            return
        if bet > 0:
            eco, data, balance = _get_economy(self.bot, interaction.user.id)
            if not eco:
                await interaction.response.send_message("economy system not loaded.", ephemeral=True)
                return
            if balance < bet:
                await interaction.response.send_message(f"you only have {balance} coins.", ephemeral=True)
                return
        view = BlackjackView(interaction.user, bet, self.bot)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

        # If player got 21 immediately (blackjack)
        if view.finished:
            # Dealer reveals
            while hand_value(view.dealer) < 17:
                view.dealer.append(draw_card())
            if bet > 0:
                pv = hand_value(view.player)
                dv = hand_value(view.dealer)
                eco, data, _ = _get_economy(self.bot, interaction.user.id)
                if eco:
                    if pv == 21 and dv != 21:
                        data['balance'] = data.get('balance', 0) + int(bet * 1.5)
                    elif pv == 21 and dv == 21:
                        pass  # push
                    _save_economy(self.bot, interaction.user.id, data)
            for child in view.children:
                child.disabled = True
            try:
                await view.message.edit(embed=view.build_embed(), view=view)
            except:
                pass

    @app_commands.command(name="coinflip", description="Bet coins on heads or tails")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    async def coinflip(self, interaction: discord.Interaction, bet: int = 0, choice: app_commands.Choice[str] = None):
        self.bot.increment_command('coinflip')
        pick = choice.value if choice else random.choice(['heads', 'tails'])
        result = random.choice(['heads', 'tails'])

        if bet > 0:
            eco, data, balance = _get_economy(self.bot, interaction.user.id)
            if not eco:
                await interaction.response.send_message("economy system not loaded.", ephemeral=True)
                return
            if balance < bet:
                await interaction.response.send_message(f"you only have {balance} coins.", ephemeral=True)
                return
            won = (pick == result)
            if won:
                data['balance'] = data.get('balance', 0) + bet
            else:
                data['balance'] = data.get('balance', 0) - bet
            _save_economy(self.bot, interaction.user.id, data)

            color = discord.Color.green() if won else discord.Color.red()
            outcome = "you won!" if won else "you lost."
            embed = discord.Embed(title="🪙 Coinflip", color=color)
            embed.add_field(name="Your pick", value=pick.title(), inline=True)
            embed.add_field(name="Result", value=result.title(), inline=True)
            embed.add_field(name="Outcome", value=f"{outcome} ({'+' if won else '-'}{bet} coins)", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="🪙 Coinflip", color=0x1a1a2e)
            embed.add_field(name="Your pick", value=pick.title(), inline=True)
            embed.add_field(name="Result", value=result.title(), inline=True)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slots", description="Spin the slot machine (10 coins)")
    async def slots(self, interaction: discord.Interaction):
        self.bot.increment_command('slots')
        cost = 10
        eco, data, balance = _get_economy(self.bot, interaction.user.id)
        if eco and balance < cost:
            await interaction.response.send_message(f"need {cost} coins to play. you have {balance}.", ephemeral=True)
            return
        if eco:
            data['balance'] = data.get('balance', 0) - cost
            _save_economy(self.bot, interaction.user.id, data)

        symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
        # Spinning animation
        await interaction.response.send_message(embed=discord.Embed(
            title="🎰 Slots",
            description="`[ 🔄 | 🔄 | 🔄 ]`\nspinning...",
            color=0x1a1a2e
        ))
        msg = await interaction.original_response()
        for _ in range(3):
            await asyncio.sleep(0.6)
            preview = [random.choice(symbols) for _ in range(3)]
            await msg.edit(embed=discord.Embed(
                title="🎰 Slots",
                description=f"`[ {preview[0]} | {preview[1]} | {preview[2]} ]`\nspinning...",
                color=0x1a1a2e
            ))

        # Final result
        final = [random.choice(symbols) for _ in range(3)]
        if final[0] == final[1] == final[2]:
            payout = 100
            outcome = f"🎉 jackpot! +{payout} coins"
            color = discord.Color.gold()
        elif final[0] == final[1] or final[1] == final[2] or final[0] == final[2]:
            payout = 10  # break even (cost was 10)
            outcome = f"matched 2. +{payout} coins (break even)"
            color = discord.Color.green()
        else:
            payout = 0
            outcome = "no match. -10 coins"
            color = discord.Color.red()

        if eco and payout > 0:
            data['balance'] = data.get('balance', 0) + payout
            _save_economy(self.bot, interaction.user.id, data)

        embed = discord.Embed(
            title="🎰 Slots",
            description=f"`[ {final[0]} | {final[1]} | {final[2]} ]`\n\n{outcome}",
            color=color
        )
        await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Games(bot))
