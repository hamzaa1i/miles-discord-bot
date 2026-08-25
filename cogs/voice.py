"""
cogs/voice.py — Veloura voice channel management.

  /voice [action] [value]
      action choices:
        lock        — block new people from joining (deny @everyone connect)
        unlock      — restore connect for @everyone
        hide        — hide the channel from everyone (deny view_channel)
        unhide      — restore view_channel for @everyone
        limit       — set the user limit (parse int from `value`)
        rename      — rename the channel (use `value` as the new name)

Requires:
  - caller is connected to a voice channel
  - caller has manage_channels permission
  - bot has manage_channels permission
"""
import logging

import discord
from discord.ext import commands
from discord import app_commands

from utils.veloura_embeds import veloura_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.voice')


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Helpers ────────────────────────────────────────────────
    @staticmethod
    def _user_vc(member: discord.Member):
        """Return the VoiceChannel the member is connected to, or None."""
        if not member.voice:
            return None
        return getattr(member.voice, "channel", None)

    @staticmethod
    async def _send(itx: discord.Interaction, msg: str, ephemeral: bool = True):
        try:
            await itx.response.send_message(msg, ephemeral=ephemeral)
        except discord.InteractionResponded:
            await itx.followup.send(msg, ephemeral=ephemeral)

    async def _send_embed(self, itx: discord.Interaction, title: str, desc: str,
                          color: int = COLOR_LAVENDER, ephemeral: bool = False):
        embed = veloura_embed(title, desc, color)
        try:
            await itx.response.send_message(embed=embed, ephemeral=ephemeral)
        except discord.InteractionResponded:
            await itx.followup.send(embed=embed, ephemeral=ephemeral)

    # ─── Slash command ──────────────────────────────────────────
    @app_commands.command(name="voice", description="Manage your current voice channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        action="What to do with your current voice channel",
        value="New name (for rename) or member limit (for limit)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Lock", value="lock"),
        app_commands.Choice(name="Unlock", value="unlock"),
        app_commands.Choice(name="Hide", value="hide"),
        app_commands.Choice(name="Unhide", value="unhide"),
        app_commands.Choice(name="Set User Limit", value="limit"),
        app_commands.Choice(name="Rename", value="rename"),
    ])
    async def voice(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        value: str = None,
    ):
        self.bot.increment_command('voice')
        if not interaction.guild:
            await self._send(
                interaction, "this command only works in servers.", ephemeral=True
            )
            return
        if not interaction.guild.me.guild_permissions.manage_channels:
            await self._send(
                interaction,
                "❌ i need manage_channels permission to do that.",
                ephemeral=True,
            )
            return
        channel = self._user_vc(interaction.user)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            await self._send(
                interaction, "❌ you need to be in a voice channel first.", ephemeral=True
            )
            return

        key = action.value

        if key == "lock":
            try:
                await channel.set_permissions(
                    interaction.guild.default_role,
                    connect=False,
                    reason=f"voice lock by {interaction.user}",
                )
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel's permissions.", ephemeral=True)
                return
            await self._send_embed(
                interaction,
                "voice",
                f"🔒 {channel.mention} is now **locked** — no new members can join.",
                COLOR_PINK,
            )
            return

        if key == "unlock":
            try:
                await channel.set_permissions(
                    interaction.guild.default_role,
                    connect=True,
                    reason=f"voice unlock by {interaction.user}",
                )
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel's permissions.", ephemeral=True)
                return
            await self._send_embed(
                interaction,
                "voice",
                f"🔓 {channel.mention} is now **unlocked** — members can join again.",
                COLOR_LAVENDER,
            )
            return

        if key == "hide":
            try:
                await channel.set_permissions(
                    interaction.guild.default_role,
                    view_channel=False,
                    reason=f"voice hide by {interaction.user}",
                )
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel's permissions.", ephemeral=True)
                return
            await self._send_embed(
                interaction,
                "voice",
                f"🙈 {channel.mention} is now **hidden** from the channel list.",
                COLOR_PINK,
            )
            return

        if key == "unhide":
            try:
                # Restore default view permission by clearing the override
                try:
                    await channel.set_permissions(
                        interaction.guild.default_role,
                        view_channel=None,
                        reason=f"voice unhide by {interaction.user}",
                    )
                except discord.Forbidden:
                    # fall back to overwrite clear
                    await channel.set_permissions(
                        interaction.guild.default_role,
                        overwrite=None,
                        reason=f"voice unhide by {interaction.user}",
                    )
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel's permissions.", ephemeral=True)
                return
            await self._send_embed(
                interaction,
                "voice",
                f"👁️ {channel.mention} is now **visible** again.",
                COLOR_LAVENDER,
            )
            return

        if key == "limit":
            if value is None:
                await self._send(interaction, "❌ provide the new limit as `value` (0 = unlimited).", ephemeral=True)
                return
            try:
                limit = int(value)
            except ValueError:
                await self._send(interaction, "❌ `value` must be a whole number (0-99).", ephemeral=True)
                return
            if limit < 0 or limit > 99:
                await self._send(interaction, "❌ limit must be between 0 and 99 (0 = unlimited).", ephemeral=True)
                return
            try:
                await channel.edit(user_limit=limit, reason=f"voice limit by {interaction.user}")
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel.", ephemeral=True)
                return
            label = "unlimited" if limit == 0 else str(limit)
            await self._send_embed(
                interaction,
                "voice",
                f"🔢 user limit for {channel.mention} set to **{label}**.",
                COLOR_LAVENDER,
            )
            return

        if key == "rename":
            if value is None or not value.strip():
                await self._send(interaction, "❌ provide the new name as `value`.", ephemeral=True)
                return
            new_name = value.strip()[:100]
            try:
                await channel.edit(name=new_name, reason=f"voice rename by {interaction.user}")
            except discord.Forbidden:
                await self._send(interaction, "❌ i can't edit that channel.", ephemeral=True)
                return
            await self._send_embed(
                interaction,
                "voice",
                f"✏️ {channel.mention} renamed to **{new_name}**.",
                COLOR_LAVENDER,
            )
            return


async def setup(bot):
    await bot.add_cog(Voice(bot))
