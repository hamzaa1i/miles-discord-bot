"""
cogs/ai_features.py — AI-powered utility commands using Groq.

FIX 3 — Every AI slash command now:
  1. Calls interaction.response.defer() as the very first line
  2. Wraps the AI call in asyncio.wait_for(..., timeout=30.0)
  3. Always calls interaction.followup.send() so the interaction is
     never left hanging ("Aurelia is thinking..." forever)
"""
import asyncio
import logging

import discord
from discord.ext import commands
from discord import app_commands
from utils.ai_handler import call_ai

logger = logging.getLogger('cyn.ai_features')

# FIX 3 — Hard ceiling on how long any AI slash command may run.
AI_TIMEOUT_SECONDS = 30.0


class AIFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="summarize", description="Summarize text in 3-5 bullet points")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def summarize(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('summarize')
        await interaction.response.defer()
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": "Summarize the text in 3-5 bullet points. Use '- ' prefix. Be concise."},
                        {"role": "user", "content": text},
                    ],
                    max_tokens=500,
                    temperature=0.3,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[summarize] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        embed = discord.Embed(title="📝 Summary", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="translate", description="Translate text to a target language")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def translate(self, interaction: discord.Interaction, language: str, text: str):
        self.bot.increment_command('translate')
        await interaction.response.defer()
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": f"Translate the text into {language}. Return ONLY the translated text."},
                        {"role": "user", "content": text},
                    ],
                    max_tokens=800,
                    temperature=0.2,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[translate] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        embed = discord.Embed(
            title=f"🌍 Translated to {language}",
            description=f"```\n{result[:1500]}\n```",
            color=0x1a1a2e,
        )
        embed.add_field(name="Original", value=text[:1024], inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="explain", description="Explain a topic like you're 12")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def explain(self, interaction: discord.Interaction, topic: str):
        self.bot.increment_command('explain')
        await interaction.response.defer()
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": "Explain the topic to a 12-year-old. Simple words, short sentences, max 2-3 paragraphs."},
                        {"role": "user", "content": topic},
                    ],
                    max_tokens=500,
                    temperature=0.5,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[explain] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        embed = discord.Embed(title=f"💡 {topic} — explained", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="advice", description="Blunt, sarcastic but useful advice")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def advice(self, interaction: discord.Interaction, situation: str):
        self.bot.increment_command('advice')
        await interaction.response.defer()
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": "You are aurelia. Give blunt, sarcastic but useful advice. Respond in 1-2 sentences only. Lowercase. No emojis."},
                        {"role": "user", "content": situation},
                    ],
                    max_tokens=200,
                    temperature=0.85,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[advice] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        await interaction.followup.send(f"{result}\n*situation: {situation[:100]}*")

    @app_commands.command(name="roast_server", description="AI roasts the current server")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def roast_server(self, interaction: discord.Interaction):
        self.bot.increment_command('roast_server')
        await interaction.response.defer()
        g = interaction.guild
        channel_names = [c.name for c in g.text_channels[:15]]
        prompt = f"Server name: {g.name}\nMember count: {g.member_count}\nChannels: {', '.join(channel_names)}\n"
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": "Roast a Discord server. Funny, savage, not hateful. 2-3 sentences. Lowercase. No emojis."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=200,
                    temperature=0.95,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[roast_server] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        await interaction.followup.send(f"🔥 **Server roast**\n\n{result}")

    @app_commands.command(name="code", description="Generate a code snippet")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def code(self, interaction: discord.Interaction, language: str, description: str):
        self.bot.increment_command('code')
        await interaction.response.defer()
        try:
            result = await asyncio.wait_for(
                call_ai(
                    [
                        {"role": "system", "content": f"Write {language} code. Return ONLY code in a fenced block. No explanation."},
                        {"role": "user", "content": description},
                    ],
                    max_tokens=1000,
                    temperature=0.2,
                ),
                timeout=AI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("took too long. try again.")
            return
        except Exception as e:
            logger.error(f"[code] {type(e).__name__}: {e}")
            await interaction.followup.send("something went wrong.")
            return
        embed = discord.Embed(title=f"💻 {language} code", description=result[:4000], color=0x1a1a2e)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AIFeatures(bot))
