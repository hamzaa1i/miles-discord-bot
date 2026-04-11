import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/counting.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'channel_id': None,
            'count': 0,
            'last_user': None,
            'high_score': 0,
            'enabled': False
        })

    def save_config(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = self.get_config(message.guild.id)

        if not config['enabled']:
            return

        if not config['channel_id']:
            return

        if str(message.channel.id) != str(config['channel_id']):
            return

        # Check if message is a number
        try:
            number = int(message.content.strip())
        except ValueError:
            await message.delete()
            return

        expected = config['count'] + 1

        # Same user counting twice
        if str(message.author.id) == str(config['last_user']):
            await message.add_reaction("❌")
            config['count'] = 0
            config['last_user'] = None
            self.save_config(message.guild.id, config)

            embed = discord.Embed(
                description=(
                    f"{message.author.mention} you can't count twice in a row. "
                    f"back to 0."
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        if number == expected:
            config['count'] = number
            config['last_user'] = str(message.author.id)

            if number > config['high_score']:
                config['high_score'] = number

            await message.add_reaction("✅")

            # Milestone reactions
            if number % 100 == 0:
                await message.channel.send(
                    f"**{number}** reached. nice work."
                )
        else:
            await message.add_reaction("❌")
            old_count = config['count']
            config['count'] = 0
            config['last_user'] = None
            self.save_config(message.guild.id, config)

            embed = discord.Embed(
                description=(
                    f"{message.author.mention} ruined it at **{old_count}**. "
                    f"it was **{expected}**, not {number}. starting over."
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        self.save_config(message.guild.id, config)

    @app_commands.command(name="counting_setup", description="Setup the counting channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def counting_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['enabled'] = True
        config['count'] = 0
        config['last_user'] = None
        self.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            description=(
                f"counting channel set to {channel.mention}.\n"
                f"start counting from 1."
            ),
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="count", description="Check current count")
    async def count(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)

        if not config['enabled']:
            await interaction.response.send_message(
                "counting isn't set up. use /counting_setup",
                ephemeral=True
            )
            return

        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(
            name="current count",
            value=f"**{config['count']}**",
            inline=True
        )
        embed.add_field(
            name="high score",
            value=f"**{config['high_score']}**",
            inline=True
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Counting(bot))