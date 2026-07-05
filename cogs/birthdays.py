"""
cogs/birthdays.py — birthday system.

Spec (ADD 4):
  Data stored in data/birthdays.json per guild:
    {
      "config": { "channel_id": "..." },
      "users": {
        "<user_id>": { "month": 5, "day": 17 }
      }
    }

  /birthday set [month] [day]   — save your birthday (month + day only)
  /birthday remove              — remove your birthday
  /birthday check @user         — see when someone's birthday is
  /birthday upcoming            — list next 5 upcoming birthdays
  /birthday channel #channel    — set the announcement channel (mod only)

  Background task: runs daily at midnight UTC. For every user whose
  month/day matches today, post a celebratory embed in the configured
  channel tagging the user with a 🎂 embed.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
from utils.database import Database

MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MONTHS_SHORT = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/birthdays.json')
        # Run the daily check loop
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    # ==================== Storage helpers ====================

    def get_guild_data(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'config': {'channel_id': None},
            'users': {},
        })

    def save_guild_data(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    # ==================== Daily task ====================

    @tasks.loop(hours=24)
    async def daily_check(self):
        """Run once a day. Check all guilds for users whose birthday is today
        and post a celebratory embed in each guild's configured channel."""
        now = datetime.utcnow()
        today_month = now.month
        today_day = now.day

        all_data = self.db.get_all()
        for guild_id_str, gdata in all_data.items():
            if not isinstance(gdata, dict):
                continue
            try:
                guild_id = int(guild_id_str)
            except ValueError:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            config = gdata.get('config', {})
            channel_id = config.get('channel_id')
            if not channel_id:
                continue
            channel = guild.get_channel(int(channel_id))
            if not channel:
                continue

            users = gdata.get('users', {})
            for user_id_str, bday in users.items():
                if not isinstance(bday, dict):
                    continue
                if bday.get('month') == today_month and bday.get('day') == today_day:
                    try:
                        member = guild.get_member(int(user_id_str))
                    except Exception:
                        member = None
                    if not member:
                        # FIX 9-style: wrap fetches in try/except
                        try:
                            member = await guild.fetch_member(int(user_id_str))
                        except Exception:
                            continue
                    if not member:
                        continue

                    embed = discord.Embed(
                        title="🎂 Happy Birthday!",
                        description=(
                            f"Happy birthday {member.mention}! 🎉\n"
                            f"Everyone wish **{member.display_name}** a great one."
                        ),
                        color=discord.Color.gold(),
                        timestamp=now
                    )
                    if member.avatar:
                        embed.set_thumbnail(url=member.avatar.url)
                    embed.set_footer(text=f"🎂 {MONTHS[today_month]} {today_day}")
                    try:
                        await channel.send(content=member.mention, embed=embed)
                    except Exception:
                        pass

    @daily_check.before_loop
    async def before_daily_check(self):
        """Wait until bot is ready, then sleep until the next midnight UTC."""
        await self.bot.wait_until_ready()
        now = datetime.utcnow()
        # Compute seconds to next midnight UTC
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()
        if wait_seconds > 0:
            import asyncio
            await asyncio.sleep(wait_seconds)

    # ==================== Commands ====================

    birthday = app_commands.Group(name="birthday", description="Birthday management")

    @birthday.command(name="set", description="Set your birthday (month and day only)")
    async def birthday_set(self, interaction: discord.Interaction, month: int, day: int):
        self.bot.increment_command('birthday_set')
        if month < 1 or month > 12:
            await interaction.response.send_message("month must be 1-12.", ephemeral=True)
            return
        # Basic day-of-month validation
        max_day = 31
        if month in [4, 6, 9, 11]:
            max_day = 30
        elif month == 2:
            max_day = 29  # allow leap day
        if day < 1 or day > max_day:
            await interaction.response.send_message(
                f"{MONTHS[month]} only has 1-{max_day} days.", ephemeral=True
            )
            return

        data = self.get_guild_data(interaction.guild.id)
        data.setdefault('users', {})[str(interaction.user.id)] = {
            'month': month, 'day': day
        }
        self.save_guild_data(interaction.guild.id, data)

        await interaction.response.send_message(
            f"✅ your birthday is set to **{MONTHS[month]} {day}**.",
            ephemeral=True
        )



    @birthday.command(name="upcoming", description="List the next 5 upcoming birthdays")
    async def birthday_upcoming(self, interaction: discord.Interaction):
        self.bot.increment_command('birthday_upcoming')
        data = self.get_guild_data(interaction.guild.id)
        users = data.get('users', {})
        if not users:
            await interaction.response.send_message(
                "no birthdays set in this server yet.", ephemeral=True
            )
            return

        now = datetime.utcnow()
        upcoming = []
        for user_id_str, bday in users.items():
            try:
                m, d = int(bday['month']), int(bday['day'])
            except (KeyError, ValueError, TypeError):
                continue
            # Next occurrence of this birthday
            try:
                next_bday = datetime(now.year, m, d)
            except ValueError:
                continue
            if next_bday < now:
                next_bday = datetime(now.year + 1, m, d)
            days_until = (next_bday - now).days
            upcoming.append((days_until, user_id_str, m, d))

        upcoming.sort(key=lambda x: x[0])
        if not upcoming:
            await interaction.response.send_message(
                "no valid birthdays set.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🎂 Upcoming Birthdays", color=0x1a1a2e)
        desc = ""
        for days_until, user_id_str, m, d in upcoming[:5]:
            member = interaction.guild.get_member(int(user_id_str))
            name = member.display_name if member else f"User {user_id_str}"
            if days_until == 0:
                when = "🎉 today!"
            elif days_until == 1:
                when = "tomorrow"
            else:
                when = f"in {days_until} days"
            desc += f"**{name}** — {MONTHS_SHORT[m]} {d} ({when})\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)

    @birthday.command(name="channel", description="Set the birthday announcement channel (mod only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def birthday_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('birthday_channel')
        data = self.get_guild_data(interaction.guild.id)
        data.setdefault('config', {})['channel_id'] = str(channel.id)
        self.save_guild_data(interaction.guild.id, data)
        await interaction.response.send_message(
            f"✅ birthday announcements will go to {channel.mention}."
        )


    @birthday.command(name="remove", description="Remove your birthday")
    async def birthday_remove(self, interaction: discord.Interaction):
        self.bot.increment_command('birthday_remove')
        data = self.get_guild_data(interaction.guild.id)
        users = data.get('users', {})
        if str(interaction.user.id) in users:
            del users[str(interaction.user.id)]
            data['users'] = users
            self.save_guild_data(interaction.guild.id, data)
            await interaction.response.send_message("✅ your birthday has been removed.", ephemeral=True)
        else:
            await interaction.response.send_message("you hadn't set a birthday.", ephemeral=True)

    @birthday.command(name="check", description="See someone's birthday")
    async def birthday_check(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('birthday_check')
        data = self.get_guild_data(interaction.guild.id)
        bday = data.get('users', {}).get(str(user.id))
        if not bday:
            await interaction.response.send_message(f"{user.display_name} hasn't set their birthday.", ephemeral=True)
            return
        month = bday.get('month')
        day = bday.get('day')
        await interaction.response.send_message(f"🎂 {user.mention}'s birthday is **{MONTHS[month]} {day}**")


async def setup(bot):
    await bot.add_cog(Birthdays(bot))
