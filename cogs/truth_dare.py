import discord
from discord.ext import commands
from discord import app_commands
import random

class TruthDare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.truths = [
            "what's the most embarrassing thing you've done online?",
            "what's a lie you've told that you got away with?",
            "what's something you pretend to like but actually hate?",
            "who was your first crush in this server?",
            "what's the most childish thing you still do?",
            "what's something you've done that you thought no one saw?",
            "what's the weirdest thing you've searched online?",
            "what's a habit you have that you're embarrassed about?",
            "have you ever talked badly about someone in this server?",
            "what's your biggest insecurity?",
            "what's the dumbest thing you've spent money on?",
            "what's something you're secretly afraid of?",
            "have you ever cheated in a game? which one?",
            "what's the last thing you lied about?",
            "what's the longest you've gone without showering?",
        ]

        self.dares = [
            "change your nickname to 'absolute clown' for 10 minutes",
            "send a 'i miss you' text to the 5th person in your contacts",
            "post your phone's battery percentage right now",
            "speak in third person for the next 5 messages",
            "type with your elbows for your next message",
            "say something nice to the person above you in the member list",
            "share the last song you listened to",
            "do your best impression of this server's owner (text format)",
            "write a haiku about the server right now",
            "use only emojis for your next 3 messages",
            "change your avatar for the next hour (if you're willing)",
            "ping someone random and say 'you know what you did'",
            "describe yourself in 3 words",
            "send the last meme you saved",
            "rate everyone currently online in this channel out of 10",
        ]

    @app_commands.command(name="truth", description="Get a truth question")
    async def truth(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user

        question = random.choice(self.truths)

        embed = discord.Embed(
            title="Truth",
            description=f"{target.mention} {question}",
            color=0x1a1a2e
        )
        embed.set_footer(text="answer honestly. or don't. your call.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dare", description="Get a dare")
    async def dare(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user

        challenge = random.choice(self.dares)

        embed = discord.Embed(
            title="Dare",
            description=f"{target.mention} {challenge}",
            color=0x1a1a2e
        )
        embed.set_footer(text="do it or admit you're scared.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tod", description="Random truth or dare")
    async def tod(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        is_truth = random.choice([True, False])

        if is_truth:
            content = random.choice(self.truths)
            title = "Truth"
            footer = "answer honestly."
        else:
            content = random.choice(self.dares)
            title = "Dare"
            footer = "do it."

        embed = discord.Embed(
            title=title,
            description=f"{target.mention} {content}",
            color=0x1a1a2e
        )
        embed.set_footer(text=footer)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(TruthDare(bot))