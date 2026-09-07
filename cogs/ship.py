"""cogs/ship.py — PHASE 3 / PART 1 — ship compatibility matcher.

/ship match @user1 [@user2] — generate a deterministic daily
compatibility score + poetic AI reason for a pair of members, and
save the result to ship_history.

/ship history [@user]       — a member's top recent ships (ephemeral).

Score math (deterministic so re-shipping the same pair on the same
UTC day returns the same number, but the date seed rotates it daily):
  * base 40–95% from a sha256 of the ordered pair + today's date
  * +5 bonus when the two users share at least one fact keyword
  * capped at 100

Privacy: if either member has ship privacy on (/privacy set ship off)
the command refuses with "one of them has ship privacy on ♡".

Discord constraint (same as /confess): a slash command cannot be BOTH
a bare command with arguments and a group, so the pair shiper lives at
/ship match and the log at /ship history.

DB: utils/db.py save_ship_async / get_ship_history_async
(Supabase ship_history, JSON fallback).
"""
import hashlib
import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.ai_handler import call_ai_fast, _EMPTY_CONTENT_FALLBACK
from utils.veloura_embeds import get_seasonal_color
from utils.db import (
    get_user_facts_async, save_ship_async, get_ship_history_async,
    get_user_privacy_async,
)

logger = logging.getLogger('cyn.ship')

# Words too generic to count as a "shared fact keyword".
_STOPWORDS = {
    "the", "and", "with", "that", "this", "from", "they", "them",
    "their", "there", "likes", "like", "loves", "love", "plays",
    "play", "very", "really", "sometimes", "always", "never", "about",
    "into", "over", "under", "been", "being", "have", "has", "will",
    "would", "could", "when", "what", "who", "know", "people",
}

# Poetic fallback lines when the AI reason call fails, keyed by band.
_FALLBACK_REASONS = {
    "high": (
        "two soft hearts orbiting the same warm star — of course they "
        "resonate ♡"
    ),
    "mid": (
        "a quiet gravity pulls them together — gentle, patient, "
        "undeniable ✦"
    ),
    "low": (
        "parallel daydreams — a little distance, but the same sky 🌙"
    ),
}


def compute_ship_score(user1_id: int, user2_id: int, day_seed: str,
                       shared_keyword: bool = False) -> int:
    """Deterministic per-pair-per-day compatibility score.

    sha256(min_id:max_id:date) -> stable 40..95 base; +5 when the pair
    shares a fact keyword; capped at 100."""
    a, b = min(int(user1_id), int(user2_id)), max(int(user1_id), int(user2_id))
    digest = hashlib.sha256(f"ship:{a}:{b}:{day_seed}".encode()).hexdigest()
    score = 40 + int(digest[:8], 16) % 56  # 40..95
    if shared_keyword:
        score += 5
    return min(score, 100)


def _fact_keywords(facts) -> set:
    """Content words (4+ chars, no stopwords) from a user's facts."""
    words = set()
    for f in facts or []:
        if not isinstance(f, str):
            continue
        for w in re.findall(r"[a-z0-9]{4,}", f.lower()):
            if w not in _STOPWORDS:
                words.add(w)
    return words


def build_ship_name(name1: str, name2: str) -> str:
    """Blend two display names into a ship name.

    Short names (<6 chars): drop name1's last char and keep name2
    whole — "volc" + "diva" -> "voldiva". Longer names take their
    front/back halves. Always lowercase + alphanumeric only."""
    a = re.sub(r"[^a-z0-9]", "", str(name1).lower()) or "some"
    b = re.sub(r"[^a-z0-9]", "", str(name2).lower()) or "one"
    if len(a) < 6:
        part_a = a[:-1] or a
    else:
        part_a = a[:(len(a) + 1) // 2]
    if len(b) < 6:
        part_b = b
    else:
        part_b = b[(len(b) + 1) // 2:]
    return (part_a + part_b)[:32] or "ship"


def _score_bar(score: int) -> str:
    """10-slot emoji bar for a compatibility score."""
    filled = max(0, min(10, round(score / 10)))
    return "❤️" * filled + "🤍" * (10 - filled)


def _first_word(name: str) -> str:
    return str(name or "").split()[0] if str(name or "").split() else "someone"


class Ship(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ship = app_commands.Group(
        name="ship", description="Ship two members and check compatibility ♡"
    )

    @ship.command(name="match", description="Ship two members (defaults to you + them)")
    @app_commands.describe(
        user1="The first member to ship",
        user2="The second member (defaults to you)",
    )
    @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
    async def ship_match(self, interaction: discord.Interaction,
                         user1: discord.Member, user2: discord.Member = None):
        self.bot.increment_command('ship_match')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        user2 = user2 or interaction.user
        if user1.id == user2.id:
            return await interaction.response.send_message(
                "you can't ship someone with themselves... as cute as that "
                "would be ♡ pick two different people.",
                ephemeral=True,
            )

        await interaction.response.defer()

        # Privacy: either side may have ship privacy on.
        for u in (user1, user2):
            try:
                priv = await get_user_privacy_async(u.id)
            except Exception:
                priv = None
            if priv and priv.get("ship_optout"):
                return await interaction.followup.send(
                    "one of them has ship privacy on ♡", ephemeral=True
                )

        guild_id = str(interaction.guild.id)

        # Known facts for both (best-effort; empty lists are fine).
        facts1, facts2 = [], []
        try:
            facts1 = await get_user_facts_async(guild_id, user1.id) or []
        except Exception:
            facts1 = []
        try:
            facts2 = await get_user_facts_async(guild_id, user2.id) or []
        except Exception:
            facts2 = []

        kw1, kw2 = _fact_keywords(facts1), _fact_keywords(facts2)
        shared = bool(kw1 & kw2)

        day_seed = datetime.utcnow().date().isoformat()
        score = compute_ship_score(user1.id, user2.id, day_seed, shared)

        # AI reason (playful, soft, poetic, under 30 words).
        reason = ""
        try:
            name1 = _first_word(user1.display_name)
            name2 = _first_word(user2.display_name)
            prompt = (
                "You write one compatibility reason for a Discord ship. "
                "Playful, soft, poetic, under 30 words, lowercase. Base it "
                "on the two users' known facts when given. Never explain "
                "your reasoning. Output only the reason."
            )
            user_msg = (
                f"{name1}'s known facts: "
                f"{'; '.join(str(f) for f in facts1[:6]) or 'unknown'}\n"
                f"{name2}'s known facts: "
                f"{'; '.join(str(f) for f in facts2[:6]) or 'unknown'}\n"
                f"compatibility score: {score}%"
            )
            response = await call_ai_fast([
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg},
            ], max_tokens=80)
            if response and response != _EMPTY_CONTENT_FALLBACK:
                # single line, capped
                reason = " ".join(response.split())[:300]
        except Exception as e:
            logger.warning(f"[ship] AI reason failed: {e}")
            reason = ""

        if not reason:
            band = "high" if score >= 75 else ("mid" if score >= 50 else "low")
            reason = _FALLBACK_REASONS[band]

        ship_name = build_ship_name(
            _first_word(user1.display_name), _first_word(user2.display_name)
        )

        embed = discord.Embed(
            title=f"꒰ა 💕 ໒꒱ {ship_name}",
            color=get_seasonal_color(),
        )
        embed.add_field(
            name="compatibility",
            value=f"**{score}%** {_score_bar(score)}",
            inline=False,
        )
        embed.add_field(name="the vibe", value=reason, inline=False)
        if user1.avatar:
            embed.set_thumbnail(url=user1.avatar.url)
        else:
            embed.set_thumbnail(url=user1.default_avatar.url)
        embed.set_footer(
            text=f"requested by {interaction.user.display_name} · "
                 f"{user1.display_name} × {user2.display_name}"
        )

        # Persist for /ship history (best-effort).
        try:
            await save_ship_async(
                guild_id, user1.id, user2.id, score, reason
            )
        except Exception as e:
            logger.warning(f"[ship] history save failed: {e}")

        await interaction.followup.send(embed=embed)

    @ship.command(name="history", description="Your (or someone's) top recent ships")
    @app_commands.describe(user="Whose ship history to show (defaults to you)")
    async def ship_history(self, interaction: discord.Interaction,
                           user: discord.Member = None):
        self.bot.increment_command('ship_history')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        target = user or interaction.user
        await interaction.response.defer(ephemeral=True)

        try:
            rows = await get_ship_history_async(
                str(interaction.guild.id), target.id, limit=25
            )
        except Exception as e:
            logger.error(f"[ship] history read failed: {e}")
            rows = []

        if not rows:
            return await interaction.followup.send(
                f"no ships yet for **{target.display_name}** — start one "
                "with `/ship match` ♡",
                ephemeral=True,
            )

        # Top 5 of their recent ships, sorted by score descending.
        rows.sort(key=lambda r: int(r.get("score", 0) or 0), reverse=True)
        lines = []
        for r in rows[:5]:
            try:
                other_id = (
                    r.get("user2_id")
                    if str(r.get("user1_id")) == str(target.id)
                    else r.get("user1_id")
                )
                other = interaction.guild.get_member(int(other_id))
                other_name = other.display_name if other else f"user {other_id}"
            except (TypeError, ValueError):
                other_name = "someone"
            score = int(r.get("score", 0) or 0)
            lines.append(
                f"**{score}%** {_score_bar(score)[:5]} × **{other_name}**"
            )
        embed = discord.Embed(
            title=f"꒰ა 💕 ໒꒱ {target.display_name}'s ships",
            description="\n".join(lines),
            color=get_seasonal_color(),
        )
        embed.set_footer(text="top 5 of their 25 most recent ships")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Ship(bot))
