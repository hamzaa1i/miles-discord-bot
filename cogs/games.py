import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from utils.embeds import create_embed
from utils.database import Database

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
        self.trivia_questions = [
            {"question": "What is the capital of France?", "answer": "paris", "options": ["London", "Paris", "Berlin", "Madrid"]},
            {"question": "What is 2 + 2?", "answer": "4", "options": ["3", "4", "5", "6"]},
            {"question": "Which planet is known as the Red Planet?", "answer": "mars", "options": ["Venus", "Mars", "Jupiter", "Saturn"]},
            {"question": "Who painted the Mona Lisa?", "answer": "leonardo da vinci", "options": ["Michelangelo", "Leonardo da Vinci", "Picasso", "Van Gogh"]},
            {"question": "What is the largest ocean on Earth?", "answer": "pacific", "options": ["Atlantic", "Indian", "Arctic", "Pacific"]},
            {"question": "How many continents are there?", "answer": "7", "options": ["5", "6", "7", "8"]},
            {"question": "What is the speed of light?", "answer": "299792458", "options": ["299,792,458 m/s", "150,000,000 m/s", "300,000,000 m/s", "250,000,000 m/s"]},
            {"question": "Who wrote 'Romeo and Juliet'?", "answer": "shakespeare", "options": ["Dickens", "Shakespeare", "Hemingway", "Twain"]},
            {"question": "What year did World War II end?", "answer": "1945", "options": ["1943", "1944", "1945", "1946"]},
            {"question": "What is the smallest prime number?", "answer": "2", "options": ["1", "2", "3", "5"]},
        ]
    
    def get_user_balance(self, user_id: int) -> int:
        """Get user's balance"""
        data = self.db.get(str(user_id), {})
        return data.get('balance', 0)
    
    def update_balance(self, user_id: int, amount: int):
        """Update user's balance"""
        data = self.db.get(str(user_id), {'balance': 0})
        data['balance'] += amount
        self.db.set(str(user_id), data)
    
    @app_commands.command(name="trivia", description="Answer a trivia question for coins!")
    async def trivia(self, interaction: discord.Interaction):
        """Trivia game"""
        question_data = random.choice(self.trivia_questions)
        options = question_data['options']
        random.shuffle(options)
        
        # Create embed with options
        embed = create_embed(
            title="🧠 Trivia Time!",
            description=question_data['question'],
            color=discord.Color.blue()
        )
        
        options_text = "\n".join([f"**{chr(65+i)}.** {opt}" for i, opt in enumerate(options)])
        embed.add_field(name="Options", value=options_text, inline=False)
        embed.add_field(name="Reward", value="💰 200 coins for correct answer!", inline=False)
        embed.set_footer(text="You have 15 seconds to answer!")
        
        await interaction.response.send_message(embed=embed)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=15.0)
            user_answer = msg.content.strip().lower()
            
            # Check if answer is correct
            correct = False
            if user_answer in ['a', 'b', 'c', 'd']:
                idx = ord(user_answer) - 97
                if 0 <= idx < len(options):
                    if options[idx].lower() == question_data['answer'].lower():
                        correct = True
            elif user_answer == question_data['answer'].lower():
                correct = True
            
            if correct:
                self.update_balance(interaction.user.id, 200)
                result_embed = create_embed(
                    title="✅ Correct!",
                    description=f"You won **200 coins**! 🎉",
                    color=discord.Color.green()
                )
            else:
                result_embed = create_embed(
                    title="❌ Wrong!",
                    description=f"The correct answer was: **{question_data['answer']}**",
                    color=discord.Color.red()
                )
            
            await interaction.channel.send(embed=result_embed)
            
        except asyncio.TimeoutError:
            timeout_embed = create_embed(
                title="⏰ Time's Up!",
                description=f"The correct answer was: **{question_data['answer']}**",
                color=discord.Color.orange()
            )
            await interaction.channel.send(embed=timeout_embed)
    
    @app_commands.command(name="guess", description="Guess the number game (1-100)")
    async def guess(self, interaction: discord.Interaction, bet: int):
        """Number guessing game"""
        if bet < 50:
            await interaction.response.send_message("❌ Minimum bet is 50 coins!", ephemeral=True)
            return
        
        balance = self.get_user_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(f"❌ You only have {balance} coins!", ephemeral=True)
            return
        
        number = random.randint(1, 100)
        attempts = 5
        
        embed = create_embed(
            title="🎲 Guess the Number!",
            description=f"I'm thinking of a number between **1-100**\nYou have **{attempts} attempts**\nBet: **{bet} coins**",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()
        
        for attempt in range(attempts):
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=20.0)
                guess = int(msg.content)
                
                if guess == number:
                    winnings = bet * 3
                    self.update_balance(interaction.user.id, winnings - bet)
                    
                    win_embed = create_embed(
                        title="🎉 You Won!",
                        description=f"The number was **{number}**!\nYou won **{winnings} coins**!",
                        color=discord.Color.green()
                    )
                    await interaction.channel.send(embed=win_embed)
                    return
                elif guess < number:
                    hint = "📈 Higher!"
                else:
                    hint = "📉 Lower!"
                
                remaining = attempts - attempt - 1
                if remaining > 0:
                    hint_embed = create_embed(
                        title=hint,
                        description=f"Attempts remaining: **{remaining}**",
                        color=discord.Color.orange()
                    )
                    await interaction.channel.send(embed=hint_embed)
                
            except asyncio.TimeoutError:
                break
        
        # Lost
        self.update_balance(interaction.user.id, -bet)
        
        lose_embed = create_embed(
            title="😔 You Lost!",
            description=f"The number was **{number}**\nYou lost **{bet} coins**",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=lose_embed)
    
    @app_commands.command(name="slots", description="Play the slot machine!")
    async def slots(self, interaction: discord.Interaction, bet: int):
        """Slot machine game"""
        if bet < 100:
            await interaction.response.send_message("❌ Minimum bet is 100 coins!", ephemeral=True)
            return
        
        balance = self.get_user_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(f"❌ You only have {balance} coins!", ephemeral=True)
            return
        
        symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
        weights = [30, 25, 20, 15, 7, 3]  # Probability weights
        
        # Spin the slots
        result = random.choices(symbols, weights=weights, k=3)
        
        # Calculate winnings
        if result[0] == result[1] == result[2]:
            if result[0] == "💎":
                multiplier = 10
            elif result[0] == "7️⃣":
                multiplier = 20
            else:
                multiplier = 5
            winnings = bet * multiplier
            win = True
        elif result[0] == result[1] or result[1] == result[2]:
            multiplier = 2
            winnings = bet * multiplier
            win = True
        else:
            winnings = 0
            win = False
        
        # Update balance
        if win:
            self.update_balance(interaction.user.id, winnings - bet)
        else:
            self.update_balance(interaction.user.id, -bet)
        
        # Display result
        slots_display = f"🎰 | {result[0]} | {result[1]} | {result[2]} | 🎰"
        
        if win:
            embed = create_embed(
                title="🎉 WINNER!",
                description=slots_display,
                color=discord.Color.green()
            )
            embed.add_field(name="Winnings", value=f"+{winnings} coins")
        else:
            embed = create_embed(
                title="💸 You Lost!",
                description=slots_display,
                color=discord.Color.red()
            )
            embed.add_field(name="Lost", value=f"-{bet} coins")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="blackjack", description="Play blackjack!")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        """Blackjack game"""
        if bet < 50:
            await interaction.response.send_message("❌ Minimum bet is 50 coins!", ephemeral=True)
            return
        
        balance = self.get_user_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(f"❌ You only have {balance} coins!", ephemeral=True)
            return
        
        # Simple blackjack
        cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        
        def card_value(card):
            if card in ['J', 'Q', 'K']:
                return 10
            elif card == 'A':
                return 11
            else:
                return int(card)
        
        def calculate_hand(hand):
            total = sum(card_value(card) for card in hand)
            aces = hand.count('A')
            while total > 21 and aces:
                total -= 10
                aces -= 1
            return total
        
        # Deal initial cards
        player_hand = [random.choice(cards), random.choice(cards)]
        dealer_hand = [random.choice(cards), random.choice(cards)]
        
        player_total = calculate_hand(player_hand)
        dealer_total = calculate_hand(dealer_hand)
        
        # Show initial hands
        embed = create_embed(
            title="🃏 Blackjack",
            description=f"**Your hand:** {' '.join(player_hand)} (Total: {player_total})\n**Dealer:** {dealer_hand[0]} ❓",
            color=discord.Color.blue()
        )
        embed.set_footer(text="React with ✅ to hit, ❌ to stand")
        
        msg = await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
        
        # Player's turn
        while player_total < 21:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=15.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Hit
                    player_hand.append(random.choice(cards))
                    player_total = calculate_hand(player_hand)
                    
                    embed = create_embed(
                        title="🃏 Blackjack",
                        description=f"**Your hand:** {' '.join(player_hand)} (Total: {player_total})\n**Dealer:** {dealer_hand[0]} ❓",
                        color=discord.Color.blue()
                    )
                    await msg.edit(embed=embed)
                    
                    if player_total > 21:
                        break
                else:
                    # Stand
                    break
                    
            except asyncio.TimeoutError:
                break
        
        # Dealer's turn
        while dealer_total < 17:
            dealer_hand.append(random.choice(cards))
            dealer_total = calculate_hand(dealer_hand)
        
        # Determine winner
        if player_total > 21:
            result = "💸 Bust! You lost!"
            winnings = -bet
            color = discord.Color.red()
        elif dealer_total > 21 or player_total > dealer_total:
            result = "🎉 You won!"
            winnings = bet
            color = discord.Color.green()
        elif player_total < dealer_total:
            result = "😔 Dealer wins!"
            winnings = -bet
            color = discord.Color.red()
        else:
            result = "🤝 Push! (Tie)"
            winnings = 0
            color = discord.Color.orange()
        
        self.update_balance(interaction.user.id, winnings)
        
        # Final embed
        final_embed = create_embed(
            title="🃏 Blackjack - Final",
            description=f"**Your hand:** {' '.join(player_hand)} (Total: {player_total})\n**Dealer:** {' '.join(dealer_hand)} (Total: {dealer_total})\n\n{result}",
            color=color
        )
        if winnings != 0:
            final_embed.add_field(name="Result", value=f"{'+'if winnings > 0 else ''}{winnings} coins")
        
        await msg.edit(embed=final_embed)
    
    @app_commands.command(name="roulette", description="Bet on roulette!")
    async def roulette(self, interaction: discord.Interaction, bet: int, choice: str):
        """Roulette game - choice: red, black, green, or number (0-36)"""
        if bet < 50:
            await interaction.response.send_message("❌ Minimum bet is 50 coins!", ephemeral=True)
            return
        
        balance = self.get_user_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(f"❌ You only have {balance} coins!", ephemeral=True)
            return
        
        # Spin the wheel
        number = random.randint(0, 36)
        
        # Determine color
        if number == 0:
            color_result = "green"
        elif number in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]:
            color_result = "red"
        else:
            color_result = "black"
        
        choice = choice.lower()
        win = False
        
        # Check win
        if choice == str(number):
            winnings = bet * 35
            win = True
        elif choice == color_result:
            if color_result == "green":
                winnings = bet * 14
            else:
                winnings = bet * 2
            win = True
        
        if win:
            self.update_balance(interaction.user.id, winnings - bet)
            embed = create_embed(
                title="🎰 Roulette - Winner!",
                description=f"The ball landed on **{number} ({color_result})** 🎉",
                color=discord.Color.green()
            )
            embed.add_field(name="Your bet", value=choice)
            embed.add_field(name="Winnings", value=f"+{winnings} coins")
        else:
            self.update_balance(interaction.user.id, -bet)
            embed = create_embed(
                title="🎰 Roulette - Lost",
                description=f"The ball landed on **{number} ({color_result})**",
                color=discord.Color.red()
            )
            embed.add_field(name="Your bet", value=choice)
            embed.add_field(name="Lost", value=f"-{bet} coins")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Games(bot))