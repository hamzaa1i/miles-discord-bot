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
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
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
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
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
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
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



    @app_commands.command(name="advice", description="Blunt, sarcastic but actually useful advice")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def advice(self, interaction: discord.Interaction, situation: str):
        self.bot.increment_command('advice')
        await interaction.response.defer()
        result = await self._ai_call(
            "You are cyn, a Discord bot. The user is describing a situation. Give blunt, sarcastic but genuinely useful advice in 3-5 sentences. Lowercase, casual tone. No emojis.",
            situation,
            temperature=0.85,
            max_tokens=300
        )
        embed = discord.Embed(description=result[:4000], color=0x1a1a2e)
        embed.set_footer(text=f"situation: {situation[:100]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roast_server", description="AI roasts the current server")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
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

async def setup(bot):
    await bot.add_cog(AIFeatures(bot))
