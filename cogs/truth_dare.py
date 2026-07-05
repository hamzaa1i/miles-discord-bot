import discord
from discord.ext import commands
from discord import app_commands
import random


class TruthDare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # 40+ truths
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
            "what's a secret you've never told anyone?",
            "who's the last person you stalked on social media?",
            "what's the cringiest message you've ever sent?",
            "what's something you'd never admit to your parents?",
            "have you ever pretended to be sick to get out of something?",
            "what's the worst advice you've ever given someone?",
            "what's the most embarrassing nickname you've had?",
            "what's a weird dream you've had recently?",
            "have you ever cried during a movie? which one?",
            "what's a song you're embarrassed to admit you like?",
            "what's the biggest misconception people have about you?",
            "have you ever accidentally sent a text to the wrong person?",
            "what's the longest you've gone without sleep?",
            "what's a skill you wish you had but don't?",
            "have you ever been caught doing something you shouldn't?",
            "what's the most impulsive thing you've ever done?",
            "what's a food everyone loves that you can't stand?",
            "what's the worst date you've ever been on?",
            "have you ever lied on a resume or application?",
            "what's the strangest thing you've ever eaten?",
            "what's the most trouble you've ever gotten into at school/work?",
            "have you ever faked being happy when you weren't?",
            "what's a conspiracy theory you kinda believe?",
            "what's the longest you've kept a secret?",
            "what's something you'd do if you knew no one would judge you?",
            "have you ever re-gifted a present?",
            "what's the most awkward situation you've been in recently?",
            "what's a phobia you have that you don't talk about?",
            "what's the most money you've ever lost at once?",
        ]

        # 40+ dares
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
            "send the most embarrassing emoji combo you can think of",
            "type the next 5 messages without using the letter 'e'",
            "make up a 4-line rap about the person above you",
            "share a screenshot of your home screen",
            "send a pick-up line to the next person who speaks",
            "talk in a fancy accent for the next 5 messages",
            "send the 7th message in your DMs with no context",
            "do 10 jumping jacks and tell us when you're done",
            "post a selfie doing a funny face",
            "say one nice thing about the bot",
            "change your nickname to your middle name (or a fake one) for 30 minutes",
            "send the first message that comes up when you open your notes app",
            "type the alphabet backwards in your next message",
            "send a voice message of you doing an evil laugh",
            "compliment the next 3 people who send a message",
            "tell us your most-used emoji of all time",
            "send the most recent photo in your camera roll (SFW only)",
            "write a 1-star review of this server",
            "ping the owner and confess your undying love (jk)",
            "share the last thing you copy-pasted",
            "make up a fake conspiracy theory about the server owner",
            "send a 'good morning' message to the bot",
            "type your next message entirely in pig latin",
            "give yourself a temporary avatar of a meme for 10 minutes",
            "tell us your most embarrassing username you've ever had",
            "send a screenshot of your most-used apps",
            "write a love poem about an inanimate object near you",
            "send the last gif you used in any chat",
            "do your best impression of a robot for the next 3 messages",
            "share a song you love that you think no one here knows",
        ]

    @app_commands.command(name="truth", description="Get a truth question")
    async def truth(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('truth')
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
        self.bot.increment_command('dare')
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
        self.bot.increment_command('tod')
        target = user or interaction.user
        if random.choice([True, False]):
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
