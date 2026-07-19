"""
cogs/counting.py — counting game.

Spec (ADD 6):
  Data per guild in data/counting.json:
    {
      "channel_id": null,
      "current_count": 0,
      "last_user_id": null,
      "high_score": 0,
      "save_count_on_fail": false
    }

  /counting setup #channel — set the counting channel
  /counting reset — reset count to 0 (mod only)
  /counting score — show current count and high score
  /counting toggle_save — toggle whether count resets to 0 on fail or saves

  on_message:
    - If message is in the counting channel
    - Try to parse the message as an integer
    - If it equals current_count + 1 AND the sender is not last_user_id:
      - Increment count, update last_user_id, save to JSON
      - If new high score, react with 🏆 and announce it
      - Otherwise react with ✅
    - If wrong number or same user counted twice:
      - React with ❌
      - Reset count to 0 (or save based on toggle)
      - Reply: "❌ {user} ruined it at {count}! Starting over."
    - Delete non-number messages in the counting channel silently
"""
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
            'current_count': 0,
            'last_user_id': None,
            'high_score': 0,
            'save_count_on_fail': False,
            'enabled': True,
        })

    def save_config(self, guild_id: int, data: dict):
        self.db.set(str(guild_id), data)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = self.get_config(message.guild.id)
        if not config.get('enabled', True):
            return
        if not config.get('channel_id'):
            return
        if str(message.channel.id) != str(config['channel_id']):
            return

        # Try to parse the message as an integer
        try:
            number = int(message.content.strip())
        except ValueError:
            # Delete non-number messages silently
            try:
                await message.delete()
            except Exception:
                pass
            return

        current_count = config.get('current_count', 0)
        last_user_id = config.get('last_user_id')
        expected = current_count + 1

        # Same user counting twice in a row = fail
        if str(message.author.id) == str(last_user_id):
            await message.add_reaction("❌")
            old_count = current_count
            if not config.get('save_count_on_fail', False):
                config['current_count'] = 0
                config['last_user_id'] = None
            else:
                # Keep the count but let the next valid number pick up from current+1
                config['last_user_id'] = None
            self.save_config(message.guild.id, config)
            embed = discord.Embed(
                description=(
                    f"❌ {message.author.mention} ruined it at **{old_count}**! "
                    f"Same user can't count twice. Starting over."
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        if number == expected:
            config['current_count'] = number
            config['last_user_id'] = str(message.author.id)

            new_high_score = False
            if number > config.get('high_score', 0):
                config['high_score'] = number
                new_high_score = True

            if new_high_score:
                await message.add_reaction("🏆")
                await message.channel.send(
                    f"🏆 new high score: **{number}**! nice."
                )
            else:
                await message.add_reaction("✅")

            # Milestone reactions
            if number % 100 == 0:
                await message.channel.send(f"**{number}** reached. nice work.")
        else:
            await message.add_reaction("❌")
            old_count = current_count
            if not config.get('save_count_on_fail', False):
                config['current_count'] = 0
                config['last_user_id'] = None
            else:
                # Save: keep the count, just clear last_user_id
                config['last_user_id'] = None
            self.save_config(message.guild.id, config)

            embed = discord.Embed(
                description=(
                    f"❌ {message.author.mention} ruined it at **{old_count}**! "
                    f"It was **{expected}**, not {number}. "
                    + ("Starting over." if not config.get('save_count_on_fail') else "Count saved.")
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        self.save_config(message.guild.id, config)

    # ==================== Commands ====================

    counting = app_commands.Group(name="counting", description="Counting game management")

    @counting.command(name="setup", description="Set the counting channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def counting_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('counting_setup')
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['enabled'] = True
        config['current_count'] = 0
        config['last_user_id'] = None
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ counting channel set to {channel.mention}. start counting from 1."
        )

    @counting.command(name="reset", description="Reset count to 0 (mod only)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def counting_reset(self, interaction: discord.Interaction):
        self.bot.increment_command('counting_reset')
        config = self.get_config(interaction.guild.id)
        config['current_count'] = 0
        config['last_user_id'] = None
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message("✅ count reset to 0.")

    @counting.command(name="score", description="Show current count and high score")
    async def counting_score(self, interaction: discord.Interaction):
        self.bot.increment_command('counting_score')
        config = self.get_config(interaction.guild.id)
        if not config.get('enabled', True):
            await interaction.response.send_message(
                "counting isn't set up. use `/counting setup #channel` first.",
                ephemeral=True
            )
            return
        embed = discord.Embed(title="🔢 Counting Score", color=0x1a1a2e)
        embed.add_field(name="Current count", value=f"**{config.get('current_count', 0)}**", inline=True)
        embed.add_field(name="High score", value=f"**{config.get('high_score', 0)}**", inline=True)
        embed.add_field(
            name="Save on fail",
            value="✅ on" if config.get('save_count_on_fail') else "❌ off",
            inline=True
        )
        await interaction.response.send_message(embed=embed)


    @app_commands.checks.has_permissions(manage_channels=True)
    async def counting_toggle_save(self, interaction: discord.Interaction):
        self.bot.increment_command('counting_toggle_save')
        config = self.get_config(interaction.guild.id)
        config['save_count_on_fail'] = not config.get('save_count_on_fail', False)
        self.save_config(interaction.guild.id, config)
        status = "✅ on (count is preserved on fail)" if config['save_count_on_fail'] else "❌ off (count resets to 0 on fail)"
        await interaction.response.send_message(f"save-on-fail is now **{status}**.")




async def setup(bot):
    await bot.add_cog(Counting(bot))
