"""cogs/daily.py — PHASE 2 / PART 1 — daily login rewards & streaks.

/daily — one claim per user per UTC day, per guild.

Mechanics:
  * streak:  claimed yesterday (UTC) -> streak + 1
             claimed today          -> blocked with a soft cooldown message
             missed a day / new     -> streak resets to 1
  * XP:      50 base + 10 per streak day (bonus capped at +150, so the
             regular claim maxes at 200 XP) — awarded through user_levels
             (the existing leveling table), so /rank /level /leaderboard
             all see it.
  * milestones (bonus embed callout):
             7-day streak   -> +100 bonus XP
             30-day streak  -> +500 bonus XP
             100-day streak -> +2000 bonus XP

DB: utils/db.py get/save_daily_streak_async (Supabase `daily_streaks`,
JSON fallback). Run the PHASE 2 migration SQL at the top of utils/db.py.
"""
import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.daily')

# ─── Reward math (spec-fixed constants) ─────────────────────────
BASE_XP = 50
XP_PER_STREAK_DAY = 10
STREAK_BONUS_CAP = 150          # 50 + 150 = 200 max per claim
MILESTONE_BONUSES = {           # streak day -> bonus XP (on top of the claim)
    7: 100,
    30: 500,
    100: 2000,
}

MILESTONE_TEXTS = {
    7: "✦ 7 day milestone — **+100 bonus xp** ♡ keep glowing",
    30: "✦ 30 day milestone — **+500 bonus xp** ♡ a whole month of showing up",
    100: "✦ 100 day milestone — **+2000 bonus xp** ♡ legendary devotion ✦",
}


def compute_daily_reward(streak: int) -> tuple[int, int, str]:
    """Return (claim_xp, total_xp, milestone_text) for a streak day.

    claim_xp      — base + streak bonus, capped at 200
    total_xp      — claim_xp + milestone bonus (milestones are extra)
    milestone_text— the embed callout line, empty on a normal day."""
    bonus = min(XP_PER_STREAK_DAY * max(0, streak), STREAK_BONUS_CAP)
    claim_xp = min(BASE_XP + bonus, BASE_XP + STREAK_BONUS_CAP)
    milestone_bonus = 0
    milestone_text = ""
    for day, bonus_xp in MILESTONE_BONUSES.items():
        if streak == day:
            milestone_bonus = bonus_xp
            milestone_text = MILESTONE_TEXTS[day]
            break
    return claim_xp, claim_xp + milestone_bonus, milestone_text


def compute_next_streak(row: dict | None, today) -> tuple[int, int, bool]:
    """Return (new_streak, blocked_today) for the user's existing row.

    today — a datetime.date (UTC). blocked_today is True when the user
    already claimed today."""
    if not row:
        return 1, False
    last = str(row.get("last_claim_date") or "")
    if last == today.isoformat():
        return int(row.get("streak", 0) or 0), True
    try:
        last_date = datetime.strptime(last, "%Y-%m-%d").date()
    except ValueError:
        return 1, False
    if last_date == today - timedelta(days=1):
        return int(row.get("streak", 0) or 0) + 1, False
    return 1, False  # missed a day (or garbage date) -> reset


class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="daily",
        description="Claim your daily reward and grow your streak ♡",
    )
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def daily(self, interaction: discord.Interaction):
        self.bot.increment_command('daily')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )

        await interaction.response.defer()
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        today = datetime.utcnow().date()

        try:
            row = await _db.get_daily_streak_async(guild_id, user_id)
        except Exception as e:
            logger.error(f"[daily] streak read failed: {e}")
            row = None

        streak, blocked = compute_next_streak(row, today)
        if blocked:
            # Soft cooldown message (spec) — show the current streak.
            return await interaction.followup.send(
                "you already claimed your daily reward today ♡ come back "
                "tomorrow at midnight utc\n"
                f"current streak: **{streak} day(s)** 🔥",
                ephemeral=True,
            )

        highest = max(int(row.get("highest_streak", 0) or 0), streak) if row else streak
        total_claimed = (int(row.get("total_claimed", 0) or 0) + 1) if row else 1

        claim_xp, total_xp, milestone_text = compute_daily_reward(streak)

        # Award XP through the existing leveling system (user_levels).
        try:
            import asyncio
            xp_result = await asyncio.to_thread(
                _db.award_user_xp,
                interaction.guild.id, interaction.user.id, total_xp,
            )
            if xp_result.get("leveled_up"):
                milestone_text += (
                    f"\n⭐ you leveled up to **level "
                    f"{xp_result['new_level']}**!"
                )
        except Exception as e:
            # XP is best-effort — never block the claim itself.
            logger.error(f"[daily] xp award failed: {e}")

        try:
            await _db.save_daily_streak_async(
                guild_id, user_id, streak, highest,
                today.isoformat(), total_claimed,
            )
        except Exception as e:
            logger.error(f"[daily] streak save failed: {e}")

        embed = discord.Embed(
            title="꒰ა ♡ ໒꒱ daily reward",
            description=(
                f"you claimed **+{total_xp} XP** today ✦\n"
                f"current streak: **{streak} day(s)** 🔥\n"
                f"{milestone_text}".rstrip()
            ),
            color=get_seasonal_color(),
        )
        embed.set_footer(
            text=f"highest streak: {highest} days · total claimed: {total_claimed}"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Daily(bot))
