"""
cogs/prefix.py — custom prefix system for AI chat.

Allows server admins to set a custom prefix (e.g. "cyn.") that triggers
the AI chat handler the same way @mention does.

Commands:
  /prefix         — show the current prefix for this server
  /prefix set     — set a custom prefix (requires Manage Guild)
  /prefix remove  — remove the custom prefix (requires Manage Guild)
  /prefix list    — show all configured prefixes for this server

Data stored in Supabase via utils/db with table "prefix_settings".
"""
import discord
from discord.ext import commands
from discord import app_commands
import time
import logging

from utils.db import get_guild_setting, set_guild_setting

logger = logging.getLogger('cyn.prefix')


class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 60-second settings cache: {guild_id: (prefix_str_or_None, timestamp)}
        self._cache: dict[int, tuple[str | None, float]] = {}

    def _get_prefix(self, guild_id: int) -> str | None:
        """Get the configured prefix for this guild (with 60s cache)."""
        now = time.time()
        if guild_id in self._cache:
            cached_prefix, ts = self._cache[guild_id]
            if now - ts < 60:
                return cached_prefix
        try:
            settings = get_guild_setting(guild_id, "prefix_settings")
            prefix = settings.get("prefix") if settings else None
        except Exception:
            prefix = None
        self._cache[guild_id] = (prefix, now)
        return prefix

    def _invalidate_cache(self, guild_id: int):
        if guild_id in self._cache:
            del self._cache[guild_id]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check if message starts with the guild's custom prefix.
        If yes, strip the prefix and pass the rest to the AI chat handler."""
        if message.author.bot:
            return
        if not message.guild:
            return  # Server-only

        prefix = self._get_prefix(message.guild.id)
        if not prefix:
            return  # No prefix configured

        content = message.content
        # Case-insensitive prefix check
        if not content.lower().startswith(prefix.lower()):
            return

        # Strip the prefix and trim whitespace
        remaining = content[len(prefix):].strip()
        if not remaining:
            return  # Just the prefix with no text

        # Get the AiChat cog and call its handler
        ai_cog = self.bot.get_cog("AiChat")
        if not ai_cog:
            return

        # Check if AiChat has the handle_prefix_command method
        if hasattr(ai_cog, 'handle_prefix_command'):
            try:
                await ai_cog.handle_prefix_command(message, remaining)
            except Exception as e:
                logger.error(f"[prefix] handler error: {e}")
        else:
            # Fallback: process through the on_message handler manually
            # by injecting a fake mention
            try:
                # Temporarily add the bot mention to the message content
                # and call the on_message handler
                original_content = message.content
                message.content = f"<@{self.bot.user.id}> {remaining}"
                await ai_cog.on_message(message)
                message.content = original_content
            except Exception as e:
                logger.error(f"[prefix] fallback handler error: {e}")

    # ==================== /prefix command group ====================

    prefix_group = app_commands.Group(name="prefix", description="Custom prefix settings")

    @prefix_group.command(name="set", description="Set a custom prefix for AI chat")
    @app_commands.describe(prefix="The prefix (e.g. 'cyn.' or 'c!')")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix_set(self, interaction: discord.Interaction, prefix: str):
        self.bot.increment_command('prefix_set')
        await interaction.response.defer(ephemeral=True)

        if len(prefix) > 10:
            await interaction.followup.send("prefix too long — max 10 characters.", ephemeral=True)
            return

        try:
            set_guild_setting(interaction.guild_id, "prefix_settings", {"prefix": prefix})
            self._invalidate_cache(interaction.guild_id)
            await interaction.followup.send(
                f"✅ prefix set to `{prefix}`. use it like: `{prefix}hello`",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @prefix_group.command(name="remove", description="Remove the custom prefix")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix_remove(self, interaction: discord.Interaction):
        self.bot.increment_command('prefix_remove')
        await interaction.response.defer(ephemeral=True)

        try:
            set_guild_setting(interaction.guild_id, "prefix_settings", {"prefix": None})
            self._invalidate_cache(interaction.guild_id)
            await interaction.followup.send(
                "✅ custom prefix removed. use @mention to talk to cyn.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @prefix_group.command(name="list", description="Show the current prefix for this server")
    async def prefix_list(self, interaction: discord.Interaction):
        self.bot.increment_command('prefix_list')
        await interaction.response.defer(ephemeral=True)

        prefix = self._get_prefix(interaction.guild_id)
        if prefix:
            await interaction.followup.send(
                f"current prefix: `{prefix}`\nusage: `{prefix}hello`",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "no custom prefix set. use @mention to talk to cyn.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Prefix(bot))
