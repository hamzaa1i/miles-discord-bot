"""
cogs/confess.py — anonymous confession system.

/confess setup #channel — set the confession channel (admin)
/confess [text] — submit an anonymous confession

Confessions are posted as embeds in the configured channel. The bot does
NOT reveal who submitted the confession — it only stores the user_id
internally in case mods need to investigate abuse.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database
from utils.constants import COLOR_DEFAULT


class Confess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/confessions.json')

    def get_config(self, guild_id: int) -> dict:
        try:
            return self.db.get(f"config_{guild_id}", {'channel_id': None})
        except Exception:
            return {'channel_id': None}

    def save_config(self, guild_id: int, config: dict):
        self.db.set(f"config_{guild_id}", config)

    @app_commands.command(name="confess", description="Submit an anonymous confession")
    async def confess(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('confess')
        # Use ephemeral response so no one sees who submitted
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            try:
                await interaction.followup.send("confessions only work in servers.", ephemeral=True)
            except Exception:
                pass
            return

        config = self.get_config(interaction.guild.id)
        channel_id = config.get('channel_id')
        if not channel_id:
            try:
                await interaction.followup.send(
                    "confessions aren't set up. ask an admin to use `/confess setup #channel`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            try:
                await interaction.followup.send("confession channel not found.", ephemeral=True)
            except Exception:
                pass
            return

        if len(text) > 1900:
            text = text[:1900]

        embed = discord.Embed(
            title=" anonymous confession",
            description=text,
            color=COLOR_DEFAULT,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Confession #{self._next_id(interaction.guild.id)}")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.followup.send("i don't have permission to send to that channel.", ephemeral=True)
            except Exception:
                pass
            return

        # Store internally (for mod audit if needed) — never displayed
        try:
            confessions = self.db.get(f"confessions_{interaction.guild.id}", [])
            if not isinstance(confessions, list):
                confessions = []
            confessions.append({
                'user_id': str(interaction.user.id),
                'text': text,
                'timestamp': datetime.utcnow().isoformat(),
            })
            self.db.set(f"confessions_{interaction.guild.id}", confessions)
        except Exception:
            pass

        try:
            await interaction.followup.send("✅ confession submitted anonymously.", ephemeral=True)
        except Exception:
            pass

    @app_commands.command(name="confess_setup", description="Set the confession channel (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def confess_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('confess_setup')
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        self.save_config(interaction.guild.id, config)
        try:
            await interaction.response.send_message(
                f"✅ confessions will be posted to {channel.mention}.\n"
                f"users can now use `/confess <text>` to submit anonymous confessions."
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                f"✅ confessions will be posted to {channel.mention}.\n"
                f"users can now use `/confess <text>` to submit anonymous confessions."
            )

    def _next_id(self, guild_id: int) -> int:
        try:
            confessions = self.db.get(f"confessions_{guild_id}", [])
            return len(confessions) + 1 if isinstance(confessions, list) else 1
        except Exception:
            return 1


async def setup(bot):
    await bot.add_cog(Confess(bot))
