"""cogs/anniversary.py — PHASE 2 / PART 3 — member anniversary celebrations.

A passive daily loop that celebrates how long members have been part of
the server. Milestones: 1 month (30d), 6 months (182d), 1 year (365d),
2 years (730d), and every full year from 3 years up (1095d, 1460d, …).

Commands (admin — the whole group is Manage Server by default):
  /anniversary config channel [#channel] enabled [bool]
  /anniversary show

DB: utils/db.py anniversary helpers (Supabase `anniversary_settings`,
JSON fallback). last_run_date is stamped after each scan so a restart
can never double-celebrate the same day.
"""
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.anniversary')

# Fixed milestone durations (days since joined) -> human text.
MILESTONES = {
    30: "1 month",
    182: "6 months",
    365: "1 year",
    730: "2 years",
}
THREE_YEARS_DAYS = 1095  # 3 * 365 — every full year from here on counts


def milestone_for(days: int) -> str | None:
    """Return the milestone text for an exact day count, else None."""
    if days in MILESTONES:
        return MILESTONES[days]
    if days >= THREE_YEARS_DAYS and days % 365 == 0:
        return f"{days // 365} years"
    return None


class Anniversary(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not self.daily_check.is_running():
            self.daily_check.start()

    def cog_unload(self):
        if self.daily_check.is_running():
            self.daily_check.cancel()

    # ─── Daily background loop ───────────────────────────────────

    @tasks.loop(hours=24)
    async def daily_check(self):
        now = discord.utils.utcnow()
        today = now.date().isoformat()
        for guild in self.bot.guilds:
            try:
                settings = await _db.get_anniversary_settings_async(
                    str(guild.id)
                )
                if not settings.get("enabled"):
                    continue
                # Already celebrated (or scanned) today — restarts can't
                # double-post.
                if str(settings.get("last_run_date") or "") == today:
                    continue
                channel_id = settings.get("channel_id")
                if not channel_id:
                    continue
                try:
                    channel = guild.get_channel(int(channel_id))
                except (TypeError, ValueError):
                    channel = None
                if channel is None:
                    continue
                await self._celebrate(guild, channel, now)
                # Stamp the run even when nobody hit a milestone —
                # otherwise we'd rescan and re-post all day.
                await _db.set_anniversary_settings_async(str(guild.id), {
                    "last_run_date": today,
                })
            except Exception as e:
                logger.warning(
                    f"[anniversary] loop error for guild {guild.id}: {e}"
                )

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()

    async def _celebrate(self, guild: discord.Guild, channel, now):
        """Send a celebration card for every member hitting a milestone."""
        celebrated = 0
        for member in list(guild.members):
            if member.bot or member.joined_at is None:
                continue
            days = (now - member.joined_at).days
            text = milestone_for(days)
            if text is None:
                continue
            embed = discord.Embed(
                title="꒰ა 🍰 ໒꒱ happy server anniversary!",
                description=(
                    f"{member.mention} has been a part of "
                    f"**{guild.name}** for **{text}** today! "
                    f"thank you for being here ♡"
                ),
                color=get_seasonal_color(),
                timestamp=now,
            )
            avatar = member.avatar.url if member.avatar \
                else member.default_avatar.url
            embed.set_thumbnail(url=avatar)
            embed.set_footer(
                text=f"joined on "
                     f"{member.joined_at.strftime('%b %d, %Y')} ✦"
            )
            try:
                await channel.send(content=member.mention, embed=embed)
                celebrated += 1
            except discord.Forbidden:
                logger.warning(
                    f"[anniversary] no permission to post in "
                    f"channel {channel.id}"
                )
                return  # permissions won't heal mid-run
            except discord.HTTPException as e:
                logger.error(f"[anniversary] send failed: {e}")
        if celebrated:
            logger.info(
                f"[anniversary] celebrated {celebrated} member(s) in "
                f"{guild.name}"
            )

    # ─── Commands ────────────────────────────────────────────────

    anniversary = app_commands.Group(
        name="anniversary",
        description="Member join-anniversary celebrations",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @anniversary.command(
        name="config",
        description="Set the channel where join anniversaries are celebrated",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Channel for anniversary messages",
        enabled="Turn celebrations on or off",
    )
    async def anniversary_config(self, interaction: discord.Interaction,
                                 channel: discord.TextChannel,
                                 enabled: bool):
        self.bot.increment_command('anniversary_config')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        await _db.set_anniversary_settings_async(str(interaction.guild.id), {
            "channel_id": str(channel.id),
            "enabled": enabled,
        })
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ anniversary celebrations **{state}** — posting to "
            f"{channel.mention}."
        )

    @anniversary.command(name="show", description="Show anniversary settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def anniversary_show(self, interaction: discord.Interaction):
        self.bot.increment_command('anniversary_show')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        settings = await _db.get_anniversary_settings_async(
            str(interaction.guild.id)
        )
        channel = None
        if settings.get("channel_id"):
            try:
                channel = interaction.guild.get_channel(
                    int(settings["channel_id"])
                )
            except (TypeError, ValueError):
                channel = None
        embed = discord.Embed(
            title="꒰ა 🍰 ໒꒱ anniversary settings",
            color=get_seasonal_color(),
        )
        embed.add_field(
            name="status",
            value=(
                f"**enabled:** `{settings.get('enabled', False)}`\n"
                f"**channel:** {channel.mention if channel else '*not set*'}\n"
                f"**last scan:** `{settings.get('last_run_date') or 'never'}`"
            ),
            inline=False,
        )
        embed.set_footer(
            text="milestones: 1 month · 6 months · 1 year · 2 years · 3+ years ♡"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Anniversary(bot))
