"""cogs/birthdays.py — birthday system.

  /birthday set [month] [day]   — save your birthday
  /birthday upcoming            — list the next 5 birthdays
  /birthday channel #channel   — set the announcement channel (Manage Guild)

DB helpers used: set_birthday, get_upcoming_birthdays, get_birthdays_today.
Channel config stored via get/set_guild_setting under the
"birthday_settings" table. Format: {"channel_id": null}.
A 24-hour background task posts celebratory embeds in each guild's
configured channel for users whose birthday matches today.
"""
import logging
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone

from utils.db import (
    get_guild_setting, set_guild_setting,
    set_birthday, get_upcoming_birthdays, get_birthdays_today,
)

logger = logging.getLogger('cyn.birthdays')

MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS_SHORT = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
SETTINGS_TABLE = "birthday_settings"


class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    def get_channel_id(self, guild_id: int):
        config = get_guild_setting(guild_id, SETTINGS_TABLE)
        if not isinstance(config, dict):
            return None
        return config.get("channel_id")

    def set_channel_id(self, guild_id: int, channel_id) -> None:
        try:
            set_guild_setting(guild_id, SETTINGS_TABLE, {"channel_id": str(channel_id)})
        except Exception as e:
            logger.error(f"failed to save birthday channel: {e}")

    # ─── Daily background task ────────────────────────────────────

    @tasks.loop(hours=24)
    async def daily_check(self):
        now = datetime.now(timezone.utc)
        try:
            today_list = get_birthdays_today(now.month, now.day)
        except Exception as e:
            logger.error(f"get_birthdays_today failed: {e}")
            return
        if not today_list:
            return
        logger.info(f"birthday daily_check: {len(today_list)} match(es)")
        for entry in today_list:
            guild_id_str = entry.get("guild_id")
            user_id_str = entry.get("user_id")
            if not guild_id_str or not user_id_str:
                continue
            try:
                guild_id = int(guild_id_str)
            except (TypeError, ValueError):
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            channel_id = self.get_channel_id(guild_id)
            if not channel_id:
                continue
            try:
                channel = guild.get_channel(int(channel_id))
            except (TypeError, ValueError):
                continue
            if not channel:
                continue
            try:
                member = guild.get_member(int(user_id_str))
            except (TypeError, ValueError):
                member = None
            if not member:
                try:
                    member = await guild.fetch_member(int(user_id_str))
                except Exception:
                    continue
            embed = discord.Embed(
                title="🎂 Happy Birthday!",
                description=(
                    f"Happy birthday {member.mention}! 🎉\n"
                    f"everyone wish **{member.display_name}** a great one."
                ),
                color=discord.Color.gold(), timestamp=now,
            )
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            embed.set_footer(text=f"🎂 {MONTHS[now.month]} {now.day}")
            try:
                await channel.send(content=member.mention, embed=embed)
            except discord.Forbidden:
                logger.warning(f"missing permissions to post birthday in channel {channel.id}")
            except Exception as e:
                logger.error(f"failed to post birthday message: {e}")

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()

    # ─── Slash commands ──────────────────────────────────────────

    birthday = app_commands.Group(name="birthday", description="Birthday system")

    @birthday.command(name="set", description="Set your birthday (month + day)")
    @app_commands.describe(month="Birth month (1-12)", day="Birth day (1-31 depending on month)")
    async def birthday_set(self, interaction: discord.Interaction, month: int, day: int):
        self.bot.increment_command('birthday_set')
        if not interaction.guild:
            await interaction.response.send_message("this command only works in servers.", ephemeral=True)
            return
        if month < 1 or month > 12:
            await interaction.response.send_message("month must be 1-12.", ephemeral=True)
            return
        max_day = 30 if month in (4, 6, 9, 11) else 29 if month == 2 else 31
        if day < 1 or day > max_day:
            await interaction.response.send_message(f"{MONTHS[month]} only has 1-{max_day} days.", ephemeral=True)
            return
        try:
            set_birthday(interaction.guild.id, interaction.user.id, month, day)
        except Exception as e:
            logger.error(f"set_birthday failed: {e}")
            await interaction.response.send_message("couldn't save your birthday — try again later.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ your birthday is set to **{MONTHS[month]} {day}**.", ephemeral=True)

    @birthday.command(name="upcoming", description="Show the next 5 birthdays")
    async def birthday_upcoming(self, interaction: discord.Interaction):
        self.bot.increment_command('birthday_upcoming')
        if not interaction.guild:
            await interaction.response.send_message("this command only works in servers.", ephemeral=True)
            return
        try:
            upcoming = get_upcoming_birthdays(interaction.guild.id, limit=5)
        except Exception as e:
            logger.error(f"get_upcoming_birthdays failed: {e}")
            upcoming = []
        if not upcoming:
            await interaction.response.send_message("no birthdays set in this server yet.", ephemeral=True)
            return
        embed = discord.Embed(title="🎂 Upcoming Birthdays", color=0x1a1a2e, timestamp=datetime.now(timezone.utc))
        lines = []
        for entry in upcoming:
            user_id_str, m, d = entry.get("user_id"), entry.get("month"), entry.get("day")
            days_until = entry.get("days_until", 0)
            if not user_id_str or m is None or d is None:
                continue
            try:
                member = interaction.guild.get_member(int(user_id_str))
            except (TypeError, ValueError):
                member = None
            name = member.display_name if member else f"User {user_id_str}"
            when = "🎉 today!" if days_until == 0 else "tomorrow" if days_until == 1 else f"in {days_until} days"
            lines.append(f"**{name}** — {MONTHS_SHORT[m]} {d} ({when})")
        embed.description = "\n".join(lines) if lines else "_none_"
        await interaction.response.send_message(embed=embed)

    @birthday.command(name="channel", description="Set the birthday announcement channel (Manage Guild)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def birthday_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('birthday_channel')
        if not interaction.guild:
            await interaction.response.send_message("this command only works in servers.", ephemeral=True)
            return
        self.set_channel_id(interaction.guild.id, channel.id)
        logger.info(f"birthday channel set to #{channel.name} ({channel.id}) in guild {interaction.guild.id}")
        await interaction.response.send_message(f"✅ birthday announcements will go to {channel.mention}.")


async def setup(bot):
    await bot.add_cog(Birthdays(bot))
