"""
cogs/ai_features.py — AI-powered utility commands using Groq.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.ai_handler import call_ai


class AIFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="summarize", description="Summarize text in 3-5 bullet points")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def summarize(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('summarize')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "Summarize the text in 3-5 bullet points. Use '- ' prefix. Be concise."},
            {"role": "user", "content": text}
        ], max_tokens=500, temperature=0.3)
        embed = discord.Embed(title="📝 Summary", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="translate", description="Translate text to a target language")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def translate(self, interaction: discord.Interaction, language: str, text: str):
        self.bot.increment_command('translate')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": f"Translate the text into {language}. Return ONLY the translated text."},
            {"role": "user", "content": text}
        ], max_tokens=800, temperature=0.2)
        embed = discord.Embed(title=f"🌍 Translated to {language}", description=f"```\n{result[:1500]}\n```", color=0x1a1a2e)
        embed.add_field(name="Original", value=text[:1024], inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="explain", description="Explain a topic like you're 12")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def explain(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('explain')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "Explain the topic to a 12-year-old. Simple words, short sentences, max 2-3 paragraphs."},
            {"role": "user", "content": topic}
        ], max_tokens=500, temperature=0.5)
        embed = discord.Embed(title=f"💡 {topic} — explained", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="advice", description="Blunt, sarcastic but useful advice")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def advice(self, interaction: discord.Interaction, situation: str):
        self.bot.increment_command('advice')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "You are cyn. Give blunt, sarcastic but useful advice. Respond in 1-2 sentences only. Lowercase. No emojis."},
            {"role": "user", "content": situation}
        ], max_tokens=200, temperature=0.85)
        await interaction.followup.send(f"{result}\n*situation: {situation[:100]}*")

    @app_commands.command(name="roast_server", description="AI roasts the current server")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def roast_server(self, interaction: discord.Interaction):
        self.bot.increment_command('roast_server')
        await interaction.response.defer()
        g = interaction.guild
        channel_names = [c.name for c in g.text_channels[:15]]
        prompt = f"Server name: {g.name}\nMember count: {g.member_count}\nChannels: {', '.join(channel_names)}\n"
        result = await call_ai([
            {"role": "system", "content": "Roast a Discord server. Funny, savage, not hateful. 2-3 sentences. Lowercase. No emojis."},
            {"role": "user", "content": prompt}
        ], max_tokens=200, temperature=0.95)
        await interaction.followup.send(f"🔥 **Server roast**\n\n{result}")

    @app_commands.command(name="code", description="Generate a code snippet")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def code(self, interaction: discord.Interaction, language: str, description: str):
        self.bot.increment_command('code')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": f"Write {language} code. Return ONLY code in a fenced block. No explanation."},
            {"role": "user", "content": description}
        ], max_tokens=1000, temperature=0.2)
        embed = discord.Embed(title=f"💻 {language} code", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="debug", description="Find bugs in your code")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def debug(self, interaction: discord.Interaction, code: str):
        self.bot.increment_command('debug')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "You are a debugger. Identify bugs and suggest fixes. Be concise. Use bullet points. 1-2 sentences per bug."},
            {"role": "user", "content": code}
        ], max_tokens=600, temperature=0.3)
        embed = discord.Embed(title="🐞 Debug", description=result[:4000], color=0xff5555)
        embed.add_field(name="Your code", value="```\n" + code[:1000] + "\n```", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="story", description="AI writes a short story")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def story(self, interaction: discord.Interaction, prompt: str):
        self.bot.increment_command('story')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "Write a short story (100-150 words). No preamble."},
            {"role": "user", "content": prompt}
        ], max_tokens=300, temperature=0.9)
        embed = discord.Embed(title="📖 Story", description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"based on: {prompt[:100]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="poem", description="AI writes a short poem")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def poem(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('poem')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "Write a short poem (6-10 lines). No title. No preamble."},
            {"role": "user", "content": topic}
        ], max_tokens=200, temperature=0.95)
        embed = discord.Embed(title=f"📜 Poem about {topic}", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="define", description="Define a word with etymology and example")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def define(self, interaction: discord.Interaction, word: str):
        self.bot.increment_command('define')
        await interaction.response.defer()
        result = await call_ai([
            {"role": "system", "content": "Define the word. Give etymology in one sentence. Give one example sentence. 2-3 sentences max."},
            {"role": "user", "content": word}
        ], max_tokens=300, temperature=0.4)
        embed = discord.Embed(title=f"📚 {word}", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tldr", description="TLDR of the last 15 messages in this channel")
    @app_commands.checks.cooldown(1, 20.0, key=lambda i: i.user.id)
    async def tldr(self, interaction: discord.Interaction):
        self.bot.increment_command('tldr')
        await interaction.response.defer()
        messages = []
        try:
            async for m in interaction.channel.history(limit=30):
                if not m.author.bot and m.content:
                    messages.append(f"{m.author.display_name}: {m.content}")
                if len(messages) >= 15:
                    break
        except Exception:
            pass
        if not messages:
            await interaction.followup.send("no recent messages to summarize.")
            return
        transcript = "\n".join(reversed(messages))
        result = await call_ai([
            {"role": "system", "content": "Summarize the conversation in 2-3 sentences. Be concise."},
            {"role": "user", "content": transcript}
        ], max_tokens=150, temperature=0.3)
        embed = discord.Embed(title="📄 TLDR", description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"based on {len(messages)} recent messages")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AIFeatures(bot))
