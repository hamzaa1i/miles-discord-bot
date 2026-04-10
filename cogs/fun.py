import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.embeds import create_embed

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        """Roll dice with custom sides"""
        if sides < 2 or sides > 100:
            await interaction.response.send_message("❌ Sides must be between 2 and 100!", ephemeral=True)
            return
        
        result = random.randint(1, sides)
        
        embed = create_embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **{result}** out of {sides}!",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        """Flip a coin"""
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙" if result == "Heads" else "🔘"
        
        embed = create_embed(
            title="🪙 Coin Flip",
            description=f"{emoji} **{result}**!",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="8ball", description="Ask the magic 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        """Magic 8-ball"""
        responses = [
            "Yes, definitely!",
            "It is certain.",
            "Without a doubt.",
            "Most likely.",
            "Outlook good.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful."
        ]
        
        answer = random.choice(responses)
        
        embed = create_embed(
            title="🎱 Magic 8-Ball",
            color=discord.Color.purple()
        )
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rps", description="Play Rock Paper Scissors")
    async def rps(self, interaction: discord.Interaction, choice: str):
        """Rock Paper Scissors game"""
        choices = ["rock", "paper", "scissors"]
        choice = choice.lower()
        
        if choice not in choices:
            await interaction.response.send_message("❌ Choose rock, paper, or scissors!", ephemeral=True)
            return
        
        bot_choice = random.choice(choices)
        
        # Determine winner
        if choice == bot_choice:
            result = "It's a tie!"
            color = discord.Color.orange()
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result = "You win! 🎉"
            color = discord.Color.green()
        else:
            result = "I win! 😎"
            color = discord.Color.red()
        
        emoji_map = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        embed = create_embed(
            title="✊ Rock Paper Scissors",
            description=result,
            color=color
        )
        embed.add_field(name="You chose", value=f"{emoji_map[choice]} {choice.title()}", inline=True)
        embed.add_field(name="I chose", value=f"{emoji_map[bot_choice]} {bot_choice.title()}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="meme", description="Get a random meme")
    async def meme(self, interaction: discord.Interaction):
        """Fetch random meme from API"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://meme-api.com/gimme') as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        embed = discord.Embed(
                            title=data['title'],
                            url=data['postLink'],
                            color=discord.Color.random()
                        )
                        embed.set_image(url=data['url'])
                        embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")
                        
                        await interaction.response.send_message(embed=embed)
                    else:
                        await interaction.response.send_message("❌ Couldn't fetch meme!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Fun(bot))