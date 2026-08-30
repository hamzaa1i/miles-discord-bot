"""
cogs/recap.py — PHASE 4 Feature 3: /recap channel AI digest.

"what did i miss?" — fetches the last N hours of a channel's messages,
sends the transcript to the big reasoning model, and returns an aesthetic
digest: topics discussed, most active people, and the overall mood.

FIX 1.5 — /recap used to route through call_ai (the casual chat model
with a small token budget). When the model didn't recognize the task it
replied with Aurelia's conversational fallback ("i'm here. what's on
your mind?") instead of an actual summary. Now:
  * the digest runs on call_ai_reasoning (the BIG model, gpt-oss-120b)
    with a generous 1200-token budget
  * the prompt is an explicit summarization instruction (topics /
    participants / mood, bullet points) — nothing conversational
  * the canned greeting / error strings are treated as failures and the
    call is retried ONCE with a hard format instruction before giving up
  * fewer than 3 qualifying messages → "not enough activity to summarize"

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
from utils.ai_handler import call_ai_reasoning
from utils.veloura_embeds import veloura_embed, COLOR_PINK

logger = logging.getLogger('cyn.recap')

# FIX 1.5 — explicit, non-conversational summarization prompt. The old
# prompt still let the model slip into "chat mode"; this one demands
# bullet-point structure with topics, participants, and mood.
_SUMMARY_PROMPT = (
    "Summarize this conversation. Extract main topics, active "
    "participants, and overall mood. Format as bullet points.\n\n"
    "Structure your reply EXACTLY as markdown like this:\n"
    "topics:\n"
    "- <topic one line>\n"
    "- <topic one line>\n"
    "\n"
    "who was active:\n"
    "- <participant names>\n"
    "\n"
    "vibe: <one sentence on the overall mood of the chat>\n"
    "\n"
    "highlights:\n"
    "- <anything funny, important, or worth knowing>\n"
    "\n"
    "Write in lowercase, soft and slightly playful, but stay INFORMATIVE — "
    "this is a digest, not a performance. Rules: 2-4 topics, 1-2 "
    "highlights. Mention usernames when relevant. Never invent things "
    "that aren't in the transcript. Do NOT greet anyone, do NOT ask a "
    "question back — output ONLY the summary."
)

# FIX 1.5 — second-chance prompt when the first call came back with a
# canned conversational line instead of a summary.
_RETRY_FORMAT_INSTRUCTION = (
    "Your previous reply was a conversational greeting, not a summary. "
    "Reply with ONLY the markdown summary in the exact structure "
    "requested (topics / who was active / vibe / highlights). "
    "No greetings, no questions."
)

# FIX 1.5 — responses that mean "the model didn't summarize" — retry once.
_CANNED_RESPONSES = (
    "i'm here. what's on your mind?",
    "something broke",
    "at capacity",
)


def _is_canned(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return (not lowered) or any(sig in lowered for sig in _CANNED_RESPONSES)


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

        # FIX 1.5 — 3 qualifying messages is enough activity to summarize
        # (was 5, which made busy-but-short windows refuse).
        if len(lines) < 3:
            await interaction.followup.send(
                f"not enough activity in {target_channel.mention} in the "
                f"last {hours_val}h to summarize ༉‧₊˚"
            )
            return

        transcript = "\n".join(lines)[-12000:]  # keep the most recent 12k chars

        # ── AI digest — FIX 1.5: BIG model + retry on canned greeting ──
        user_msg = (
            f"Channel: #{target_channel.name} in the last "
            f"{hours_val} hours.\n\nTranscript:\n{transcript}"
        )
        result = None
        try:
            result = await call_ai_reasoning(
                [
                    {"role": "system", "content": _SUMMARY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=1200,
                temperature=0.6,
            )
        except Exception as e:
            logger.error(f"[recap] AI call failed: {e}")

        # FIX 1.5 — a canned greeting / error line is NOT a summary.
        # Retry once with an explicit format instruction.
        if _is_canned(result):
            logger.warning(
                f"[recap] first attempt returned canned/empty content "
                f"({(result or '')[:60]!r}) — retrying with format nudge"
            )
            try:
                result = await call_ai_reasoning(
                    [
                        {"role": "system", "content": _SUMMARY_PROMPT},
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": (result or "")},
                        {"role": "user", "content": _RETRY_FORMAT_INSTRUCTION},
                    ],
                    max_tokens=1600,
                    temperature=0.4,
                )
            except Exception as e:
                logger.error(f"[recap] retry AI call failed: {e}")

        if _is_canned(result):
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
