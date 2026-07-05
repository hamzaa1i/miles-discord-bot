"""utils/checks.py — permission decorators for slash commands.

Usage:
    from utils.checks import is_owner, is_mod, is_admin

    @app_commands.command(...)
    @is_owner()
    async def my_command(interaction):
        ...

Each decorator sends an ephemeral error message if the user lacks the
required permission, then returns False to abort the command.
"""
import os
import discord
from discord import app_commands


def is_owner():
    """Only the bot owner (set via OWNER_ID env var) can use this command."""
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if interaction.user.id != owner_id:
            try:
                await interaction.response.send_message(
                    "❌ only my owner can use this.", ephemeral=True
                )
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "❌ only my owner can use this.", ephemeral=True
                    )
                except Exception:
                    pass
            except Exception:
                pass
            return False
        return True
    return app_commands.check(predicate)


def is_mod():
    """User must have Manage Messages permission in the guild."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            try:
                await interaction.response.send_message(
                    "❌ this command only works in a server.", ephemeral=True
                )
            except Exception:
                pass
            return False
        if not interaction.user.guild_permissions.manage_messages:
            try:
                await interaction.response.send_message(
                    "❌ you need Manage Messages permission.", ephemeral=True
                )
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "❌ you need Manage Messages permission.", ephemeral=True
                    )
                except Exception:
                    pass
            except Exception:
                pass
            return False
        return True
    return app_commands.check(predicate)


def is_admin():
    """User must have Administrator permission in the guild."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            try:
                await interaction.response.send_message(
                    "❌ this command only works in a server.", ephemeral=True
                )
            except Exception:
                pass
            return False
        if not interaction.user.guild_permissions.administrator:
            try:
                await interaction.response.send_message(
                    "❌ you need Administrator permission.", ephemeral=True
                )
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "❌ you need Administrator permission.", ephemeral=True
                    )
                except Exception:
                    pass
            except Exception:
                pass
            return False
        return True
    return app_commands.check(predicate)
