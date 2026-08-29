"""
cogs/recap.py — PHASE 4 Feature 3: /recap channel AI digest.

"what did i miss?" — fetches the last N hours of a channel's messages,
sends the transcript to the big model, and returns an aesthetic digest:
topics discussed, most active people, and the overall mood.

Named /recap (not /summarize) because ai_features.py already ships a
/summarize command that summarizes pasted TEXT — this one summarizes a
CHANNEL's history, so it gets its own name.

Usage:
  /recap                 — recap of the current channel (last 2h)
  /recap #general 6      — last 6 hours of #general

Guards:
  - 60s per-user cooldown (protects the Groq quota)
  - the caller must be able to read the target channel (Discord-level
    permission check via permissions_for)
  - bots and commands are excluded from the transcript
"""
import logging
from datetime import timedelta
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.ai_handler import call_ai
from utils.veloura_embeds import veloura_embed, COLOR_PINK

logger = logging.getLogger('cyn.recap')

_SUMMARY_PROMPT = (
    "You summarize Discord channel transcripts for people who were away. "
    "Write in lowercase, soft and slightly playful, but stay INFORMATIVE — "
    "this is a digest, not a performance.\n\n"
    "Structure your reply EXACTLY as markdown like this:\n"
    "topics:\n"
    "- <topic one line>\n"
    "- <topic one line>\n"
    "\n"
    "vibe: <one sentence on the overall mood of the chat>\n"
    "\n"
    "highlights:\n"
    "- <anything funny, important, or worth knowing>\n"
    "\n"
    "Rules: 2-4 topics, 1-2 highlights. Mention usernames when relevant. "
    "Never invent things that aren't in the transcript. If the transcript "
    "is too thin to summarize, say so in one short line instead."
)


class Recap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {user_id: epoch} — 60s cooldown
        self._cooldowns = {}

    @app_commands.command(
        name="recap",
        description="Get an AI recap of what happened in a channel",
    )
    @app_commands.describe(
        channel="Channel to recap (defaults to this one)",
        hours="How many hours back to look (1-24, default 2)",
    )
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.guild_id, i.user.id))
    async def recap(self, interaction: discord.Interaction,
                    channel: Optional[discord.TextChannel] = None,
                    hours: Optional[app_commands.Range[int, 1, 24]] = None):
        self.bot.increment_command('recap')
        target_channel = channel or interaction.channel
        hours_val = hours or 2

        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message(
                "i can only recap text channels.", ephemeral=True
            )
            return

        # permission gate: caller must be able to read the target channel
        perms = target_channel.permissions_for(interaction.user)
        if not perms.read_messages or not perms.read_message_history:
            await interaction.response.send_message(
                "you can't read that channel, so i won't recap it for you.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()  # AI call takes a few seconds

        # ── collect transcript ──
        cutoff = discord.utils.utcnow() - timedelta(hours=hours_val)
        lines = []
        try:
            async for msg in target_channel.history(
                    limit=300, after=cutoff, oldest_first=True):
                if msg.author.bot:
                    continue
                content = msg.content.strip()
                if not content or content.startswith(('!', '/', '-')):
                    continue
                lines.append(f"{msg.author.display_name}: {content[:220]}")
        except discord.Forbidden:
            await interaction.followup.send(
                "i don't have permission to read that channel's history.",
                ephemeral=True,
            )
            return

        if len(lines) < 5:
            await interaction.followup.send(
                f"not enough conversation in {target_channel.mention} in the "
                f"last {hours_val}h to recap ༉‧₊˚"
            )
            return

        transcript = "\n".join(lines)[-12000:]  # keep the most recent 12k chars

        # ── AI digest ──
        try:
            result = await call_ai(
                [
                    {"role": "system", "content": _SUMMARY_PROMPT},
                    {"role": "user",
                     "content": f"Channel: #{target_channel.name} in the last "
                                f"{hours_val} hours.\n\nTranscript:\n{transcript}"},
                ],
                max_tokens=800,
                temperature=0.6,
            )
        except Exception as e:
            logger.error(f"[recap] AI call failed: {e}")
            await interaction.followup.send(
                "the recap broke on my end. try again in a minute.", ephemeral=True
            )
            return

        if not result or "something broke" in result or "at capacity" in result:
            await interaction.followup.send(
                "the recap broke on my end. try again in a minute.", ephemeral=True
            )
            return

        embed = veloura_embed(
            f"digest • #{target_channel.name} • last {hours_val}h",
            result[:4000],
            COLOR_PINK,
        )
        embed.set_footer(text=f"{len(lines)} messages read • requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @recap.error
    async def recap_error(self, interaction: discord.Interaction,
                          error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"slow down — try again in {int(error.retry_after)}s.",
                ephemeral=True,
            )
        else:
            logger.error(f"[recap] command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "something went wrong.", ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(Recap(bot))
