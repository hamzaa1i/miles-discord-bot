"""
cogs/logging_system.py — comprehensive event logging.

Commands:
  /log setup #channel  — set the channel where all logs go
  /log disable         — disable logging for this server
  /log show            — show current log settings
  /log toggle [event]  — toggle a specific event type on or off

Event listeners:
  on_message_delete, on_message_edit, on_member_join, on_member_remove,
  on_member_ban, on_member_unban, on_member_update (role + nickname changes),
  on_voice_state_update

Data format in data/logs.json:
  {
    "guild_id": {
      "channel_id": null,
      "enabled": true,
      "events": {
        "message_delete": true, "message_edit": true,
        "member_join": true, "member_leave": true,
        "member_ban": true, "member_unban": true,
        "role_change": true, "nickname_change": true,
        "voice_join": true, "voice_leave": true
      }
    }
  }
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database


DEFAULT_EVENTS = {
    "message_delete": True,
    "message_edit": True,
    "member_join": True,
    "member_leave": True,
    "member_ban": True,
    "member_unban": True,
    "role_change": True,
    "nickname_change": True,
    "voice_join": True,
    "voice_leave": True,
}


class LoggingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/logs.json')

    def get_config(self, guild_id: int) -> dict:
        try:
            return self.db.get(str(guild_id), {
                'channel_id': None,
                'enabled': True,
                'events': dict(DEFAULT_EVENTS),
            })
        except Exception:
            return {
                'channel_id': None,
                'enabled': True,
                'events': dict(DEFAULT_EVENTS),
            }

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    async def _get_log_channel(self, guild: discord.Guild, event_key: str = None):
        config = self.get_config(guild.id)
        if not config.get('enabled', True):
            return None
        channel_id = config.get('channel_id')
        if not channel_id:
            return None
        if event_key and not config.get('events', {}).get(event_key, True):
            return None
        try:
            return guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return None

    # ==================== LISTENERS ====================

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        channel = await self._get_log_channel(message.guild, 'message_delete')
        if not channel:
            return
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(message.author),
            icon_url=message.author.avatar.url if message.author.avatar else None
        )
        embed.add_field(
            name="Author",
            value=f"{message.author.mention} ({message.author.id})",
            inline=True
        )
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024] or "*empty*", inline=False)
        embed.set_footer(text=f"cyn logs · Message ID: {message.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        channel = await self._get_log_channel(before.guild, 'message_edit')
        if not channel:
            return
        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(before.author),
            icon_url=before.author.avatar.url if before.author.avatar else None
        )
        embed.add_field(
            name="Author",
            value=f"{before.author.mention} ({before.author.id})",
            inline=True
        )
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Jump", value=f"[Click]({after.jump_url})", inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*empty*", inline=False)
        embed.set_footer(text=f"cyn logs · Message ID: {before.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = await self._get_log_channel(member.guild, 'member_join')
        if not channel:
            return
        account_age = datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)
        embed = discord.Embed(
            title="✅ Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(member),
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
        embed.add_field(name="Account Age", value=f"{account_age.days} days old", inline=True)
        embed.add_field(name="Member #", value=str(member.guild.member_count), inline=True)
        embed.set_footer(text=f"cyn logs · ID: {member.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = await self._get_log_channel(member.guild, 'member_leave')
        if not channel:
            return
        embed = discord.Embed(
            title="❌ Member Left",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(member),
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]), inline=False)
        embed.set_footer(text=f"cyn logs · ID: {member.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        channel = await self._get_log_channel(guild, 'member_ban')
        if not channel:
            return
        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else None)
        embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
        embed.set_footer(text=f"cyn logs · ID: {user.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        channel = await self._get_log_channel(guild, 'member_unban')
        if not channel:
            return
        embed = discord.Embed(
            title="🕊️ Member Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else None)
        embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
        embed.set_footer(text=f"cyn logs · ID: {user.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Nickname change
        if before.nick != after.nick:
            channel = await self._get_log_channel(before.guild, 'nickname_change')
            if channel:
                embed = discord.Embed(
                    title="📝 Nickname Changed",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(
                    name=str(after),
                    icon_url=after.avatar.url if after.avatar else None
                )
                embed.add_field(name="Before", value=before.nick or "*none*", inline=True)
                embed.add_field(name="After", value=after.nick or "*none*", inline=True)
                embed.set_footer(text=f"cyn logs · ID: {after.id}")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

        # Role change
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added or removed:
            channel = await self._get_log_channel(before.guild, 'role_change')
            if channel:
                embed = discord.Embed(
                    title="🎭 Roles Changed",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(
                    name=str(after),
                    icon_url=after.avatar.url if after.avatar else None
                )
                if added:
                    embed.add_field(name="Added", value=" ".join(r.mention for r in added), inline=False)
                if removed:
                    embed.add_field(name="Removed", value=" ".join(r.mention for r in removed), inline=False)
                embed.set_footer(text=f"cyn logs · ID: {after.id}")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if before.channel is None and after.channel is not None:
            # Joined voice
            channel = await self._get_log_channel(member.guild, 'voice_join')
            if channel:
                embed = discord.Embed(
                    title="🔊 Joined Voice",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                    description=f"{member.mention} joined {after.channel.mention}"
                )
                embed.set_author(
                    name=str(member),
                    icon_url=member.avatar.url if member.avatar else None
                )
                embed.set_footer(text=f"cyn logs · ID: {member.id}")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
        elif before.channel is not None and after.channel is None:
            # Left voice
            channel = await self._get_log_channel(member.guild, 'voice_leave')
            if channel:
                embed = discord.Embed(
                    title="🔇 Left Voice",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc),
                    description=f"{member.mention} left {before.channel.mention}"
                )
                embed.set_author(
                    name=str(member),
                    icon_url=member.avatar.url if member.avatar else None
                )
                embed.set_footer(text=f"cyn logs · ID: {member.id}")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # ==================== /log command group ====================

    log = app_commands.Group(name="log", description="Log event configuration")

    @log.command(name="setup", description="Set the channel where all logs go")
    @app_commands.describe(channel="The text channel to send logs to")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def log_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('log_setup')
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("this only works in a server.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['enabled'] = True
        self.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            title="✅ Logging Configured",
            color=0x2ecc71,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        enabled_count = sum(1 for v in config.get('events', {}).values() if v)
        embed.add_field(name="Events Enabled", value=f"{enabled_count}/{len(DEFAULT_EVENTS)}", inline=True)
        embed.set_footer(text="use /log toggle <event> to disable specific events")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @log.command(name="disable", description="Disable logging for this server")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def log_disable(self, interaction: discord.Interaction):
        self.bot.increment_command('log_disable')
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("this only works in a server.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        config['enabled'] = False
        self.save_config(interaction.guild.id, config)
        await interaction.followup.send("logging disabled for this server.", ephemeral=True)

    @log.command(name="show", description="Show current log settings")
    async def log_show(self, interaction: discord.Interaction):
        self.bot.increment_command('log_show')
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("this only works in a server.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        embed = discord.Embed(
            title="📋 Log Settings",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc)
        )

        channel_id = config.get('channel_id')
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            channel_str = channel.mention if channel else f"`{channel_id}` (not found)"
        else:
            channel_str = "not set"
        embed.add_field(name="Log Channel", value=channel_str, inline=True)
        embed.add_field(name="Enabled", value="✅" if config.get('enabled', True) else "❌", inline=True)

        events = config.get('events', {})
        events_text = ""
        for key in DEFAULT_EVENTS.keys():
            status = "✅" if events.get(key, True) else "❌"
            events_text += f"{status} {key.replace('_', ' ').title()}\n"
        embed.add_field(name="Event Toggles", value=events_text, inline=False)
        embed.set_footer(text="cyn logs")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @log.command(name="toggle", description="Toggle a specific log event on or off")
    @app_commands.describe(event="The event type to toggle")
    @app_commands.choices(event=[
        app_commands.Choice(name="Message Delete", value="message_delete"),
        app_commands.Choice(name="Message Edit", value="message_edit"),
        app_commands.Choice(name="Member Join", value="member_join"),
        app_commands.Choice(name="Member Leave", value="member_leave"),
        app_commands.Choice(name="Member Ban", value="member_ban"),
        app_commands.Choice(name="Member Unban", value="member_unban"),
        app_commands.Choice(name="Role Change", value="role_change"),
        app_commands.Choice(name="Nickname Change", value="nickname_change"),
        app_commands.Choice(name="Voice Join", value="voice_join"),
        app_commands.Choice(name="Voice Leave", value="voice_leave"),
    ])
    @app_commands.checks.has_permissions(manage_channels=True)
    async def log_toggle(self, interaction: discord.Interaction, event: app_commands.Choice[str]):
        self.bot.increment_command('log_toggle')
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("this only works in a server.", ephemeral=True)
            return

        config = self.get_config(interaction.guild.id)
        if 'events' not in config:
            config['events'] = dict(DEFAULT_EVENTS)
        current = config['events'].get(event.value, True)
        config['events'][event.value] = not current
        self.save_config(interaction.guild.id, config)
        status = "disabled ❌" if current else "enabled ✅"
        await interaction.followup.send(
            f"**{event.name}** logging is now **{status}**",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(LoggingSystem(bot))
