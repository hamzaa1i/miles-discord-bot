"""
cogs/autorole.py — automatic role assignment on member join.

Commands:
  /autorole set @role    — assign this role to all new members
  /autorole remove       — disable autorole
  /autorole show         — show the currently configured autorole

Listener:
  on_member_join — gives the configured role to new members

Data stored in data/autorole.json per guild:
  {"guild_id": {"role_id": null}}
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import json as _json
from utils.database import Database


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/autorole.json')

    def get_config(self, guild_id: int) -> dict:
        try:
            return self.db.get(str(guild_id), {'role_id': None})
        except Exception:
            return {'role_id': None}

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Give the configured autorole to new members."""
        try:
            config = self.get_config(member.guild.id)
        except Exception:
            return
        role_id = config.get('role_id')
        if not role_id:
            return
        try:
            role = member.guild.get_role(int(role_id))
            if role:
                await member.add_roles(role, reason="Auto Role")
        except Exception:
            pass

    # ==================== /autorole command group ====================
    autorole = app_commands.Group(name="autorole", description="Automatic role assignment")

    @autorole.command(name="set", description="Assign a role to all new members when they join")
    @app_commands.describe(role="The role to give new members")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_set(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.increment_command('autorole_set')
        await interaction.response.defer(ephemeral=True)

        # Permission checks: Manage Roles OR bot owner
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if (interaction.user.id != owner_id and
                not interaction.user.guild_permissions.manage_roles):
            await interaction.followup.send("you need Manage Roles permission.", ephemeral=True)
            return

        # Bot hierarchy check
        if role >= interaction.guild.me.top_role:
            await interaction.followup.send(
                "that role is above my top role. move my role higher.",
                ephemeral=True
            )
            return

        # Manageable check
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.followup.send("i don't have Manage Roles permission.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        config['role_id'] = str(role.id)
        self.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            title="✅ Autorole Set",
            color=0x2ecc71,
            description=f"new members will now receive {role.mention}"
        )
        embed.set_footer(text=f"set by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @autorole.command(name="remove", description="Disable autorole for this server")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_remove(self, interaction: discord.Interaction):
        self.bot.increment_command('autorole_remove')
        await interaction.response.defer(ephemeral=True)

        owner_id = int(os.getenv("OWNER_ID", "0"))
        if (interaction.user.id != owner_id and
                not interaction.user.guild_permissions.manage_roles):
            await interaction.followup.send("you need Manage Roles permission.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        if not config.get('role_id'):
            await interaction.followup.send("autorole is not set up.", ephemeral=True)
            return

        config['role_id'] = None
        self.save_config(interaction.guild.id, config)
        await interaction.followup.send("autorole disabled.", ephemeral=True)

    @autorole.command(name="show", description="Show the currently configured autorole")
    async def autorole_show(self, interaction: discord.Interaction):
        self.bot.increment_command('autorole_show')
        await interaction.response.defer(ephemeral=True)
        config = self.get_config(interaction.guild.id)
        role_id = config.get('role_id')
        if not role_id:
            await interaction.followup.send("no autorole configured.", ephemeral=True)
            return
        try:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await interaction.followup.send(
                    f"autorole is set to {role.mention}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "the configured autorole no longer exists. use /autorole remove.",
                    ephemeral=True
                )
        except Exception:
            await interaction.followup.send("autorole config is corrupted.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
