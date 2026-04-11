import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from discord.ext import tasks
from utils.database import Database

class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/birthdays.json')
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        today = datetime.utcnow()
        today_str = f"{today.month}-{today.day}"

        all_data = self.db.get_all()

        for guild_id_user_id, data in all_data.items():
            if '_' not in guild_id_user_id:
                continue

            parts = guild_id_user_id.split('_', 1)
            if len(parts) != 2:
                continue

            guild_id, user_id = parts

            bday = data.get('birthday')
            if not bday:
                continue

            if bday == today_str:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue

                # Get announcement channel
                config = self.db.get(f"config_{guild_id}", {})
                channel_id = config.get('channel_id')
                if not channel_id:
                    continue

                channel = guild.get_channel(int(channel_id))
                if not channel:
                    continue

                try:
                    member = guild.get_member(int(user_id))
                    if member:
                        embed = discord.Embed(
                            description=(
                                f"today is {member.mention}'s birthday.\n"
                                f"say happy birthday."
                            ),
                            color=0x1a1a2e
                        )
                        await channel.send(embed=embed)
                except:
                    pass

    @check_birthdays.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="birthday_set", description="Set your birthday")
    async def birthday_set(
        self,
        interaction: discord.Interaction,
        month: int,
        day: int
    ):
        if month < 1 or month > 12 or day < 1 or day > 31:
            await interaction.response.send_message(
                "that's not a real date.",
                ephemeral=True
            )
            return

        key = f"{interaction.guild.id}_{interaction.user.id}"
        self.db.set(key, {'birthday': f"{month}-{day}"})

        months = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        embed = discord.Embed(
            description=f"birthday set to **{months[month]} {day}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="birthday_setup", description="Set birthday announcement channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        self.db.set(f"config_{interaction.guild.id}", {
            'channel_id': str(channel.id)
        })

        embed = discord.Embed(
            description=f"birthday announcements will go in {channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="birthday", description="Check someone's birthday")
    async def birthday(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        target = user or interaction.user
        key = f"{interaction.guild.id}_{target.id}"
        data = self.db.get(key, {})

        if not data.get('birthday'):
            await interaction.response.send_message(
                f"{target.display_name} hasn't set their birthday.",
                ephemeral=True
            )
            return

        month, day = data['birthday'].split('-')
        months = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        embed = discord.Embed(
            description=f"{target.mention}'s birthday is **{months[int(month)]} {day}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="birthdays", description="List upcoming birthdays")
    async def birthdays(self, interaction: discord.Interaction):
        all_data = self.db.get_all()
        today = datetime.utcnow()
        upcoming = []

        for key, data in all_data.items():
            if not key.startswith(str(interaction.guild.id) + "_"):
                continue
            if key.startswith("config_"):
                continue

            bday = data.get('birthday')
            if not bday:
                continue

            try:
                month, day = bday.split('-')
                month, day = int(month), int(day)

                bday_this_year = datetime(today.year, month, day)
                if bday_this_year < today:
                    bday_this_year = datetime(today.year + 1, month, day)

                days_until = (bday_this_year - today).days
                user_id = key.split('_', 1)[1]
                upcoming.append((days_until, user_id, month, day))
            except:
                continue

        upcoming.sort(key=lambda x: x[0])

        if not upcoming:
            await interaction.response.send_message(
                "no birthdays set in this server.",
                ephemeral=True
            )
            return

        months = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]

        embed = discord.Embed(title="Upcoming Birthdays", color=0x1a1a2e)
        desc = ""

        for days_until, user_id, month, day in upcoming[:10]:
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"

            if days_until == 0:
                when = "today"
            elif days_until == 1:
                when = "tomorrow"
            else:
                when = f"in {days_until} days"

            desc += f"**{name}** — {months[month]} {day} ({when})\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Birthdays(bot))