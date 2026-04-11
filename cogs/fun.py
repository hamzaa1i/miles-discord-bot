import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll a dice")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        if sides < 2 or sides > 1000:
            await interaction.response.send_message(
                "Sides must be between 2 and 1000.",
                ephemeral=True
            )
            return
        result = random.randint(1, sides)
        embed = discord.Embed(
            description=f"You rolled a **{result}** out of {sides}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            description=f"**{result}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Ask the magic 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            "It is certain.",
            "Without a doubt.",
            "Yes, definitely.",
            "Most likely.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Cannot predict now.",
            "Don't count on it.",
            "My sources say no.",
            "Very doubtful.",
            "Outlook not so good.",
            "The void says yes.",
            "The shadows are unclear.",
            "Darkness confirms it.",
            "Even the void doubts this.",
        ]
        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=random.choice(responses), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rps", description="Rock Paper Scissors")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Rock 🪨", value="rock"),
        app_commands.Choice(name="Paper 📄", value="paper"),
        app_commands.Choice(name="Scissors ✂️", value="scissors"),
    ])
    async def rps(self, interaction: discord.Interaction, choice: app_commands.Choice[str]):
        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        emoji = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if choice.value == bot_choice:
            result = "Tie."
            color = discord.Color.orange()
        elif (
            (choice.value == "rock" and bot_choice == "scissors") or
            (choice.value == "paper" and bot_choice == "rock") or
            (choice.value == "scissors" and bot_choice == "paper")
        ):
            result = "You win."
            color = discord.Color.green()
        else:
            result = "I win."
            color = discord.Color.red()

        embed = discord.Embed(description=result, color=color)
        embed.add_field(name="You", value=f"{emoji[choice.value]} {choice.value.title()}", inline=True)
        embed.add_field(name="Me", value=f"{emoji[bot_choice]} {bot_choice.title()}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="meme", description="Random meme")
    async def meme(self, interaction: discord.Interaction):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://meme-api.com/gimme') as r:
                    if r.status == 200:
                        data = await r.json()
                        embed = discord.Embed(title=data['title'], color=0x1a1a2e)
                        embed.set_image(url=data['url'])
                        embed.set_footer(text=f"r/{data['subreddit']} • 👍 {data['ups']}")
                        await interaction.response.send_message(embed=embed)
                    else:
                        await interaction.response.send_message("Couldn't fetch meme.", ephemeral=True)
        except:
            await interaction.response.send_message("Failed to fetch meme.", ephemeral=True)

    @app_commands.command(name="joke", description="Get a dark joke")
    async def joke(self, interaction: discord.Interaction):
        jokes = [
            "I told my psychiatrist I keep thinking I'm a dog. He told me to get off the couch.",
            "My grief counselor died. He was so good at his job, I don't even care.",
            "I have a lot of growing up to do. I realized that the other day inside my fort.",
            "I used to hate facial hair, but then it grew on me.",
            "My boss told me to have a good day. So I went home.",
            "I asked God for a bike, but I know God doesn't work that way. So I stole a bike and asked for forgiveness.",
            "The cemetery is a popular place. People are dying to get in.",
            "I don't trust stairs. They're always up to something.",
            "My wife told me I had to stop acting like a flamingo. I had to put my foot down.",
            "I told my doctor I broke my arm in two places. He told me to stop going to those places.",
        ]
        embed = discord.Embed(
            description=random.choice(jokes),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="fact", description="Get a random fact")
    async def fact(self, interaction: discord.Interaction):
        facts = [
            "Honey never spoils. Archaeologists found 3000-year-old honey in Egyptian tombs that was still edible.",
            "A day on Venus is longer than a year on Venus.",
            "Octopuses have three hearts, blue blood, and nine brains.",
            "The human brain uses about 20% of the body's total energy.",
            "A group of flamingos is called a flamboyance.",
            "There are more possible iterations of a game of chess than atoms in the observable universe.",
            "Sharks are older than trees. They've existed for 450 million years.",
            "The average person walks about 100,000 miles in their lifetime.",
            "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
            "A single cloud can weigh more than a million pounds.",
            "Bananas are berries, but strawberries aren't.",
            "The Eiffel Tower grows taller in summer due to thermal expansion.",
        ]
        embed = discord.Embed(
            description=f"💡 {random.choice(facts)}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ship", description="Ship two users together")
    async def ship(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member
    ):
        score = random.randint(1, 100)
        bar_filled = score // 10
        bar = "❤️" * bar_filled + "🖤" * (10 - bar_filled)

        if score < 30:
            verdict = "Not compatible at all."
        elif score < 50:
            verdict = "Maybe in another life."
        elif score < 70:
            verdict = "There's potential here."
        elif score < 90:
            verdict = "Pretty good match."
        else:
            verdict = "Perfect match. The universe wills it."

        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(
            name="Shipping",
            value=f"{user1.mention} 🖤 {user2.mention}",
            inline=False
        )
        embed.add_field(
            name=f"Compatibility: {score}%",
            value=bar,
            inline=False
        )
        embed.add_field(name="Verdict", value=verdict, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rate", description="Rate anything out of 10")
    async def rate(self, interaction: discord.Interaction, thing: str):
        score = random.randint(0, 10)
        embed = discord.Embed(
            description=f"I rate **{thing}** a **{score}/10**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reverse", description="Reverse text")
    async def reverse(self, interaction: discord.Interaction, text: str):
        embed = discord.Embed(
            description=text[::-1],
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mock", description="Mock someone's text")
    async def mock(self, interaction: discord.Interaction, text: str):
        mocked = "".join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(text)
        )
        embed = discord.Embed(description=mocked, color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="choose", description="Let the bot choose for you")
    async def choose(self, interaction: discord.Interaction, option1: str, option2: str):
        choice = random.choice([option1, option2])
        embed = discord.Embed(
            description=f"I choose **{choice}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="topic", description="Random conversation topic")
    async def topic(self, interaction: discord.Interaction):
        topics = [
            "If you could live in any fictional universe, which would it be?",
            "What's a skill you wish you had learned earlier?",
            "Would you rather know when you'll die or how you'll die?",
            "What's the darkest thought you've had that turned out to be funny?",
            "If money wasn't a factor, what would you do with your life?",
            "What's something everyone pretends to like but secretly hates?",
            "Would you erase one memory if you could?",
            "What do you think happens after death?",
            "If you could master any one skill instantly, what would it be?",
            "What's a truth most people aren't willing to admit?",
        ]
        embed = discord.Embed(
            description=random.choice(topics),
            color=0x1a1a2e
        )
        embed.set_footer(text="conversation starter")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="would", description="Would you rather")
    async def would(self, interaction: discord.Interaction, option1: str, option2: str):
        embed = discord.Embed(
            title="Would You Rather",
            color=0x1a1a2e
        )
        embed.add_field(name="Option A", value=option1, inline=True)
        embed.add_field(name="Option B", value=option2, inline=True)

        msg = await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("🅰️")
        await msg.add_reaction("🅱️")

async def setup(bot):
    await bot.add_cog(Fun(bot))