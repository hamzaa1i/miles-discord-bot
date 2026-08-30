"""
cogs/fun_extras.py — PHASE 1 / PART 5 quick-win feature commands.

Four new top-level slash commands (individual commands, NOT a group, so
autocomplete surfaces them naturally next to /roll and /joke):

  /vibe      — read the channel's recent conversation and describe its vibe
  /pick      — let aurelia choose between 2-10 comma-separated options
  /askstars  — ask the celestial oracle a question
  /fortune   — one aesthetic fortune per user per UTC day (persisted in
               the Supabase fortune_history table)

All four route through call_ai_fast (openai/gpt-oss-20b) with tight token
budgets, use get_seasonal_color() for embed accents (PART 6.4), and are
cooldown-protected so nobody can burn the Groq quota with them.
"""
import logging
import random
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

from utils.ai_handler import call_ai_fast, _EMPTY_CONTENT_FALLBACK
from utils.veloura_embeds import get_seasonal_color

logger = logging.getLogger('cyn.funextras')


class FunExtras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── PART 5.1 — /vibe ─────────────────────────────────────────

    @app_commands.command(name="vibe", description="what's the vibe in this channel? ✦")
    @app_commands.checks.cooldown(1, 300.0, key=lambda i: i.channel_id)
    async def vibe(self, interaction: discord.Interaction):
        self.bot.increment_command('vibe')
        if not interaction.guild or not interaction.channel:
            return await interaction.response.send_message(
                "this only works in a server channel.", ephemeral=True
            )
        await interaction.response.defer()

        # Fetch last 20 non-bot messages
        messages = []
        async for msg in interaction.channel.history(limit=30):
            if msg.author.bot or not msg.content:
                continue
            messages.append(f"{msg.author.display_name}: {msg.content[:200]}")
            if len(messages) >= 20:
                break

        if len(messages) < 5:
            await interaction.followup.send(
                "not enough activity to read the vibe yet ♡", ephemeral=True
            )
            return

        transcript = "\n".join(reversed(messages))
        prompt = (
            "Read this Discord conversation and describe the CURRENT VIBE "
            "in ONE short sentence (under 20 words). Use lowercase, soft "
            "aesthetic language. Include 1-2 emojis. "
            "Examples: 'chaotic dreamy energy tonight ♡', 'sleepy lo-fi study "
            "session 🌙', 'unhinged but wholesome 🌸', 'main character "
            "energy ✦'. Respond with just the vibe description, nothing else."
        )

        try:
            response = await call_ai_fast([
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript},
            ], max_tokens=60)
        except Exception as e:
            logger.error(f"[vibe] AI call failed: {e}")
            response = ""

        if not response or response == _EMPTY_CONTENT_FALLBACK:
            response = "the vibes are unreadable right now ✦ try again in a moment"

        embed = discord.Embed(
            title="꒰ა ♡ ໒꒱ channel vibe",
            description=response,
            color=get_seasonal_color(),
        )
        embed.set_footer(text=f"read {len(messages)} messages · #{interaction.channel.name}")
        await interaction.followup.send(embed=embed)

    # ─── PART 5.2 — /pick ─────────────────────────────────────────

    @app_commands.command(name="pick", description="let aurelia choose for you ♡")
    @app_commands.describe(options="comma-separated options (2-10 items)")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def pick(self, interaction: discord.Interaction, options: str):
        self.bot.increment_command('pick')
        await interaction.response.defer()

        opts = [o.strip() for o in options.split(",") if o.strip()]
        if len(opts) < 2:
            await interaction.followup.send(
                "that's not really a choice ♡ give me at least 2 options",
                ephemeral=True,
            )
            return
        if len(opts) > 10:
            await interaction.followup.send(
                "too many options ✦ keep it to 10 or fewer", ephemeral=True
            )
            return

        prompt = (
            f"Pick ONE of these options and give a short soft reason (under "
            f"15 words). Options: {', '.join(opts)}. Respond with just the "
            f"choice on line 1 and the reason on line 2. Use lowercase."
        )

        try:
            response = await call_ai_fast([
                {"role": "user", "content": prompt},
            ], max_tokens=80)
        except Exception as e:
            logger.error(f"[pick] AI call failed: {e}")
            response = ""

        if not response or response == _EMPTY_CONTENT_FALLBACK:
            # Deterministic fallback — still a valid pick.
            choice = random.choice(opts)
            reason = "the stars aligned on this one ♡"
        else:
            lines = response.strip().split("\n", 1)
            choice = lines[0].strip()
            # If the model echoed the whole list instead of one option,
            # fall back to a deterministic pick.
            if choice.lower() not in [o.lower() for o in opts]:
                matched = next(
                    (o for o in opts if o.lower() in choice.lower()), None
                )
                choice = matched or random.choice(opts)
            reason = lines[1].strip() if len(lines) > 1 else "just feels right ♡"

        embed = discord.Embed(
            title=f"꒰ა ♡ ໒꒱ {choice}",
            description=reason,
            color=get_seasonal_color(),
        )
        embed.set_footer(text=f"chose from {len(opts)} options")
        await interaction.followup.send(embed=embed)

    # ─── PART 5.3 — /askstars ─────────────────────────────────────

    @app_commands.command(name="askstars", description="ask the stars a question ✦")
    @app_commands.describe(question="what do you want to know?")
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
    async def askstars(self, interaction: discord.Interaction, question: str):
        self.bot.increment_command('askstars')
        await interaction.response.defer()

        if len(question) > 500:
            await interaction.followup.send(
                "your question is too long ✦ keep it under 500 chars",
                ephemeral=True,
            )
            return

        prompt = (
            "You are a mystical celestial oracle. Answer this question with a "
            "SHORT poetic response (under 25 words). Use lowercase, celestial "
            "imagery (stars, moon, cosmos, void, constellations). Be vague but "
            "warm. Never give definitive answers. Use metaphors."
        )

        try:
            response = await call_ai_fast([
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ], max_tokens=80)
        except Exception as e:
            logger.error(f"[askstars] AI call failed: {e}")
            response = ""

        if not response or response == _EMPTY_CONTENT_FALLBACK:
            response = "the stars are quiet tonight ✦ ask again when the sky clears"

        embed = discord.Embed(
            title="✦ the stars whisper ✦",
            description=f"*{response}*",
            color=0x9B59B6,
        )
        embed.set_footer(text=f"asked by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    # ─── PART 5.4 — /fortune ──────────────────────────────────────

    @app_commands.command(name="fortune", description="your daily fortune from aurelia 🥠")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def fortune(self, interaction: discord.Interaction):
        self.bot.increment_command('fortune')
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        today = datetime.utcnow().date().isoformat()

        # Check if user already got fortune today
        from utils.db import get_fortune_history_async, save_fortune_history_async
        try:
            existing = await get_fortune_history_async(user_id)
        except Exception:
            existing = None
        if existing and existing.get("last_fortune_date") == today:
            embed = discord.Embed(
                title="🥠 today's fortune",
                description=f"*{existing.get('fortune_text', 'fortune lost to the void ♡')}*",
                color=0xFFD700,
            )
            embed.set_footer(text="come back tomorrow for a new fortune ✦")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        prompt = (
            "Write a short aesthetic fortune cookie message (under 20 words). "
            "Lowercase, soft, hopeful. Include ONE emoji. Make it feel personal "
            "and warm. Examples: 'today, someone will notice your quiet magic ♡', "
            "'the stars are aligning in your favor ✦', 'trust the version of you "
            "you're becoming 🌙'"
        )

        try:
            response = await call_ai_fast([
                {"role": "user", "content": prompt},
            ], max_tokens=60)
        except Exception as e:
            logger.error(f"[fortune] AI call failed: {e}")
            response = ""

        if not response or response == _EMPTY_CONTENT_FALLBACK:
            response = random.choice([
                "today, someone will notice your quiet magic ♡",
                "the stars are aligning in your favor ✦",
                "trust the version of you you're becoming 🌙",
            ])

        try:
            await save_fortune_history_async(user_id, today, response)
        except Exception as e:
            logger.warning(f"[fortune] save failed (fortune still shown): {e}")

        embed = discord.Embed(
            title="🥠 your fortune",
            description=f"*{response}*",
            color=0xFFD700,
        )
        embed.set_footer(
            text=f"for {interaction.user.display_name} · valid until midnight utc"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FunExtras(bot))
