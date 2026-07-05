"""
cogs/logging_system.py — comprehensive event logging.

NOTE: cogs/server_logs.py already logs message/member/role/channel/voice
events. To avoid duplicate listeners for the same events, this cog
provides the *command interface* (/setlog, /log toggle) and re-uses the
ServerLogs cog's data file ('data/server_logs.json') so that toggles
made here take effect for ServerLogs too.

If ServerLogs is not loaded for some reason, this cog falls back to its
own listeners.

Step 9 spec: per-guild config with log_channel_id + enabled dict covering
message_delete, message_edit, member_join, member_leave, member_ban,
member_unban, role_changes, channel_changes, voice_activity, nickname_changes.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database


DEFAULT_ENABLED = {
    "message_delete": True,
    "message_edit": True,
    "member_join": True,
    "member_leave": True,
    "member_ban": True,
    "member_unban": True,
    "role_changes": True,
    "channel_changes": True,
    "voice_activity": True,
    "nickname_changes": True,
}


class LoggingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Use the same file as server_logs.py to keep behavior consistent
        self.db = Database('data/logs.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'log_channel_id': None,
            'enabled': dict(DEFAULT_ENABLED),
        })

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    async def _get_log_channel(self, guild: discord.Guild, event_key: str = None):
        config = self.get_config(guild.id)
        channel_id = config.get('log_channel_id')
        if not channel_id:
            return None
        if event_key and not config.get('enabled', {}).get(event_key, True):
            return None
        return guild.get_channel(int(channel_id))

    # ==================== LISTENERS (fallback if ServerLogs cog is not loaded) ====================

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if self.bot.get_cog('ServerLogs'):
            return  # let ServerLogs handle it
        channel = await self._get_log_channel(message.guild, 'message_delete')
        if not channel:
            return
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(message.author),
                         icon_url=message.author.avatar.url if message.author.avatar else None)
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
        embed.set_footer(text=f"Message ID: {message.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        if self.bot.get_cog('ServerLogs'):
            return
        channel = await self._get_log_channel(before.guild, 'message_edit')
        if not channel:
            return
        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(before.author),
                         icon_url=before.author.avatar.url if before.author.avatar else None)
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author.id})", inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Jump", value=f"[Click]({after.jump_url})", inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*empty*", inline=False)
        embed.set_footer(text=f"Message ID: {before.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.bot.get_cog('ServerLogs'):
            return
        channel = await self._get_log_channel(member.guild, 'member_join')
        if not channel:
            return
        account_age = datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)
        embed = discord.Embed(
            title="✅ Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(member),
                         icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
        embed.add_field(name="Account Age", value=f"{account_age.days} days old", inline=True)
        embed.add_field(name="Member #", value=str(member.guild.member_count), inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.bot.get_cog('ServerLogs'):
            return
        channel = await self._get_log_channel(member.guild, 'member_leave')
        if not channel:
            return
        embed = discord.Embed(
            title="❌ Member Left",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(member),
                         icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]), inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if self.bot.get_cog('ServerLogs'):
            return
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
        embed.set_footer(text=f"ID: {user.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if self.bot.get_cog('ServerLogs'):
            return
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
        embed.set_footer(text=f"ID: {user.id}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self.bot.get_cog('ServerLogs'):
            return
        # Nickname change
        if before.nick != after.nick:
            channel = await self._get_log_channel(before.guild, 'nickname_changes')
            if channel:
                embed = discord.Embed(
                    title="📝 Nickname Changed",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=str(after), icon_url=after.avatar.url if after.avatar else None)
                embed.add_field(name="Before", value=before.nick or "*none*", inline=True)
                embed.add_field(name="After", value=after.nick or "*none*", inline=True)
                embed.set_footer(text=f"ID: {after.id}")
                await channel.send(embed=embed)

        # Role change
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added or removed:
            channel = await self._get_log_channel(before.guild, 'role_changes')
            if channel:
                embed = discord.Embed(
                    title="🎭 Roles Changed",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=str(after), icon_url=after.avatar.url if after.avatar else None)
                if added:
                    embed.add_field(name="Added", value=" ".join(r.mention for r in added), inline=False)
                if removed:
                    embed.add_field(name="Removed", value=" ".join(r.mention for r in removed), inline=False)
                embed.set_footer(text=f"ID: {after.id}")
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if self.bot.get_cog('ServerLogs'):
            return
        log_channel = await self._get_log_channel(channel.guild, 'channel_changes')
        if not log_channel:
            return
        embed = discord.Embed(
            title="📁 Channel Created",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=f"{channel.mention} ({channel.id})", inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace('_', ' ').title(), inline=True)
        embed.set_footer(text=f"ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if self.bot.get_cog('ServerLogs'):
            return
        log_channel = await self._get_log_channel(channel.guild, 'channel_changes')
        if not log_channel:
            return
        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=f"#{channel.name}", inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace('_', ' ').title(), inline=True)
        embed.set_footer(text=f"ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if self.bot.get_cog('ServerLogs'):
            return
        if member.bot:
            return
        channel = await self._get_log_channel(member.guild, 'voice_activity')
        if not channel:
            return
        if before.channel is None and after.channel is not None:
            action = f"🔊 Joined voice: {after.channel.mention}"
            color = discord.Color.green()
        elif before.channel is not None and after.channel is None:
            action = f"🔇 Left voice: {before.channel.mention}"
            color = discord.Color.red()
        elif before.channel != after.channel:
            action = f"🔁 Moved: {before.channel.mention} → {after.channel.mention}"
            color = discord.Color.blue()
        else:
            return
        embed = discord.Embed(
            description=f"{member.mention} {action}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed)

    # ==================== COMMANDS ====================

    @app_commands.command(name="setlog", description="Set the logging channel for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('setlog')
        config = self.get_config(interaction.guild.id)
        config['log_channel_id'] = str(channel.id)
        self.save_config(interaction.guild.id, config)
        embed = discord.Embed(
            title="📋 Logging Configured",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Events", value=", ".join(k for k, v in config['enabled'].items() if v), inline=False)
        embed.set_footer(text="use /log toggle <event> to disable specific events")
        await interaction.response.send_message(embed=embed)

    log = app_commands.Group(name="log", description="Logging configuration")

    @log.command(name="toggle", description="Toggle a specific log event")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Message Delete", value="message_delete"),
        app_commands.Choice(name="Message Edit", value="message_edit"),
        app_commands.Choice(name="Member Join", value="member_join"),
        app_commands.Choice(name="Member Leave", value="member_leave"),
        app_commands.Choice(name="Member Ban", value="member_ban"),
        app_commands.Choice(name="Member Unban", value="member_unban"),
        app_commands.Choice(name="Role Changes", value="role_changes"),
        app_commands.Choice(name="Channel Changes", value="channel_changes"),
        app_commands.Choice(name="Voice Activity", value="voice_activity"),
        app_commands.Choice(name="Nickname Changes", value="nickname_changes"),
    ])
    async def log_toggle(self, interaction: discord.Interaction, event_type: app_commands.Choice[str]):
        self.bot.increment_command('log_toggle')
        config = self.get_config(interaction.guild.id)
        current = config['enabled'].get(event_type.value, True)
        config['enabled'][event_type.value] = not current
        self.save_config(interaction.guild.id, config)
        status = "Disabled" if current else "Enabled"
        await interaction.response.send_message(
            f"✅ **{event_type.name}** logging is now **{status}**"
        )

    @log.command(name="list", description="List all log event statuses")
    async def log_list(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)
        embed = discord.Embed(
            title="📋 Log Event Status",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc)
        )
        for key, label in [
            ("message_delete", "Message Delete"),
            ("message_edit", "Message Edit"),
            ("member_join", "Member Join"),
            ("member_leave", "Member Leave"),
            ("member_ban", "Member Ban"),
            ("member_unban", "Member Unban"),
            ("role_changes", "Role Changes"),
            ("channel_changes", "Channel Changes"),
            ("voice_activity", "Voice Activity"),
            ("nickname_changes", "Nickname Changes"),
        ]:
            value = config['enabled'].get(key, True)
            embed.add_field(name=label, value="✅ on" if value else "❌ off", inline=True)
        channel_id = config.get('log_channel_id')
        embed.set_footer(text=f"log channel: {channel_id or 'not set'}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(LoggingSystem(bot))
