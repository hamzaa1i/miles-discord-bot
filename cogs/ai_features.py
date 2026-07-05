"""
cogs/ai_features.py — additional AI-powered utility commands.
Uses the same GitHub Models backend as cogs/ai_chat.py.
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp


class AIFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"

    async def _ai_call(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 600) -> str:
        if not self.github_token:
            return "AI not connected. tell the bot owner to add GITHUB_TOKEN."
        try:
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    return f"AI returned status {response.status}."
        except Exception as e:
            print(f"AI call error: {e}")
            return "something broke on my end. try again."

    @app_commands.command(name="summarize", description="Summarize text in 3-5 bullet points")
    async def summarize(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('summarize')
        await interaction.response.defer()
        result = await self._ai_call(
            "Summarize the user's text in 3-5 bullet points. Use '- ' prefix. Be concise.",
            text,
            temperature=0.3
        )
        embed = discord.Embed(title="📝 Summary", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="translate", description="Translate text to a target language")
    async def translate(self, interaction: discord.Interaction, language: str, text: str):
        self.bot.increment_command('translate')
        await interaction.response.defer()
        result = await self._ai_call(
            f"You are a translator. Translate the user's text into {language}. Return ONLY the translated text, nothing else.",
            text,
            temperature=0.2,
            max_tokens=800
        )
        embed = discord.Embed(title=f"🌍 Translated to {language}", description=f"```\n{result[:1500]}\n```", color=0x1a1a2e)
        embed.add_field(name="Original", value=text[:1024], inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="explain", description="Explain a topic like you're 12")
    async def explain(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('explain')
        await interaction.response.defer()
        result = await self._ai_call(
            "Explain the topic to a 12-year-old. Simple words, short sentences, max 2-3 paragraphs. Use examples from everyday life.",
            topic,
            temperature=0.5
        )
        embed = discord.Embed(title=f"💡 {topic} — explained", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="code", description="Generate a code snippet")
    async def code(self, interaction: discord.Interaction, language: str, description: str):
        self.bot.increment_command('code')
        await interaction.response.defer()
        result = await self._ai_call(
            f"You are a code generator. Write {language} code for the user's request. Return ONLY code in a single fenced block, no explanation.",
            description,
            temperature=0.2,
            max_tokens=1000
        )
        embed = discord.Embed(title=f"💻 {language} code", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="debug", description="Find bugs in your code")
    async def debug(self, interaction: discord.Interaction, code: str):
        self.bot.increment_command('debug')
        await interaction.response.defer()
        result = await self._ai_call(
            "You are a debugger. Look at the user's code, identify bugs, and suggest fixes. Be specific. Use bullet points. Be concise.",
            code,
            temperature=0.3,
            max_tokens=1000
        )
        embed = discord.Embed(title="🐞 Debug report", description=result[:4000], color=0xff5555)
        embed.add_field(name="Your code", value=f"```\n{code[:1000]}\n```", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="story", description="AI writes a short story (150-200 words)")
    async def story(self, interaction: discord.Interaction, prompt: str):
        self.bot.increment_command('story')
        await interaction.response.defer()
        result = await self._ai_call(
            "Write a short story (150-200 words) based on the user's prompt. Be vivid. Use a narrative voice. No preamble.",
            prompt,
            temperature=0.9,
            max_tokens=400
        )
        embed = discord.Embed(title="📖 A short story", description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"based on: {prompt[:100]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="poem", description="AI writes a short poem (8-12 lines)")
    async def poem(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('poem')
        await interaction.response.defer()
        result = await self._ai_call(
            "Write a short poem (8-12 lines) about the user's topic. Make it evocative. No title. No preamble.",
            topic,
            temperature=0.95,
            max_tokens=300
        )
        embed = discord.Embed(title=f"📜 A poem about {topic}", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="advice", description="Blunt, sarcastic but actually useful advice")
    async def advice(self, interaction: discord.Interaction, situation: str):
        self.bot.increment_command('advice')
        await interaction.response.defer()
        result = await self._ai_call(
            "You are ao, a Discord bot. The user is describing a situation. Give blunt, sarcastic but genuinely useful advice in 3-5 sentences. Lowercase, casual tone. No emojis.",
            situation,
            temperature=0.85,
            max_tokens=300
        )
        embed = discord.Embed(description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"situation: {situation[:100]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="define", description="Define a word with etymology + example")
    async def define(self, interaction: discord.Interaction, word: str):
        self.bot.increment_command('define')
        await interaction.response.defer()
        result = await self._ai_call(
            "Define the user's word. Then give the etymology (origin) in one sentence. Then give one example sentence using the word. Be concise and accurate. If the word doesn't exist, say so.",
            word,
            temperature=0.4,
            max_tokens=400
        )
        embed = discord.Embed(title=f"📚 {word}", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tldr", description="TLDR of the last 15 messages in this channel")
    async def tldr(self, interaction: discord.Interaction):
        self.bot.increment_command('tldr')
        await interaction.response.defer()
        # Fetch last 15 messages excluding bot
        messages = []
        try:
            async for m in interaction.channel.history(limit=30, oldest_first=False):
                if not m.author.bot and m.content:
                    messages.append(f"{m.author.display_name}: {m.content}")
                if len(messages) >= 15:
                    break
        except Exception as e:
            await interaction.followup.send(f"couldn't fetch messages: {e}")
            return

        if not messages:
            await interaction.followup.send("no recent messages to summarize.")
            return

        transcript = "\n".join(reversed(messages))
        result = await self._ai_call(
            "Summarize the following Discord conversation in 2-3 sentences. Be concise. Capture the main topic and any decisions made.",
            transcript,
            temperature=0.3,
            max_tokens=200
        )
        embed = discord.Embed(title="📄 TLDR", description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"based on {len(messages)} recent messages")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roast_server", description="AI roasts the current server")
    async def roast_server(self, interaction: discord.Interaction):
        self.bot.increment_command('roast_server')
        await interaction.response.defer()
        g = interaction.guild
        channel_names = [c.name for c in g.text_channels[:15]]
        prompt = (
            f"Server name: {g.name}\n"
            f"Member count: {g.member_count}\n"
            f"Channels: {', '.join(channel_names)}\n"
        )
        result = await self._ai_call(
            "You are roasting a Discord server. Be funny, savage but not hateful. 3-4 sentences. Lowercase, casual. No slurs. No emojis.",
            prompt,
            temperature=0.95,
            max_tokens=300
        )
        embed = discord.Embed(title="🔥 Server roast", description=result[:4000], color=0xff5555)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="aipoll", description="AI generates a poll question about a topic")
    async def aipoll(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('aipoll')
        await interaction.response.defer()
        result = await self._ai_call(
            "Generate a single opinion poll question or 'would you rather' about the user's topic. Return ONLY the question, nothing else. Make it thought-provoking. Max 1 sentence.",
            topic,
            temperature=0.85,
            max_tokens=120
        )
        # Clean up
        question = result.strip().strip('"').strip('*')
        embed = discord.Embed(title="📊 AI-generated poll", description=question[:2048], color=0x1a1a2e)
        embed.set_footer(text=f"about: {topic} · by {interaction.user}")
        await interaction.followup.send(embed=embed)
        # Add reactions
        msg = await interaction.original_response()
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")


async def setup(bot):
    await bot.add_cog(AIFeatures(bot))
