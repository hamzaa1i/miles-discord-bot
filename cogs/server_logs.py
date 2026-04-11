import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database

class ServerLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/server_logs.json')

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'enabled': False,
            'log_channel': None,
            'ignored_channels': [],
            'events': {
                'message_delete': True,
                'message_edit': True,
                'member_join': True,
                'member_leave': True,
                'member_ban': True,
                'member_unban': True,
                'member_kick': True,
                'role_create': True,
                'role_delete': True,
                'role_update': True,
                'channel_create': True,
                'channel_delete': True,
                'channel_update': True,
                'member_update': True,
                'voice_update': True,
                'invite_create': True,
                'invite_delete': True,
            }
        })

    async def get_log_channel(self, guild: discord.Guild):
        """Get the log channel for a guild"""
        config = self.get_config(guild.id)
        if not config.get('enabled'):
            return None
        channel_id = config.get('log_channel')
        if not channel_id:
            return None
        return guild.get_channel(int(channel_id))

    def is_event_enabled(self, guild_id: int, event: str) -> bool:
        """Check if specific event logging is enabled"""
        config = self.get_config(guild_id)
        return config.get('events', {}).get(event, True)

    def is_channel_ignored(self, guild_id: int, channel_id: int) -> bool:
        """Check if channel is ignored"""
        config = self.get_config(guild_id)
        return str(channel_id) in config.get('ignored_channels', [])

    # ==================== MESSAGE EVENTS ====================

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not self.is_event_enabled(message.guild.id, 'message_delete'):
            return
        if self.is_channel_ignored(message.guild.id, message.channel.id):
            return

        channel = await self.get_log_channel(message.guild)
        if not channel:
            return

        embed = discord.Embed(
            title="Message Deleted",
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
        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=True
        )
        if message.content:
            embed.add_field(
                name="Content",
                value=message.content[:1024],
                inline=False
            )
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join([a.filename for a in message.attachments]),
                inline=False
            )
        embed.set_footer(text=f"Message ID: {message.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        if not self.is_event_enabled(before.guild.id, 'message_edit'):
            return
        if self.is_channel_ignored(before.guild.id, before.channel.id):
            return

        channel = await self.get_log_channel(before.guild)
        if not channel:
            return

        embed = discord.Embed(
            title="Message Edited",
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
        embed.add_field(
            name="Channel",
            value=before.channel.mention,
            inline=True
        )
        embed.add_field(
            name="Jump to Message",
            value=f"[Click here]({after.jump_url})",
            inline=True
        )
        embed.add_field(
            name="Before",
            value=before.content[:1024] if before.content else "*Empty*",
            inline=False
        )
        embed.add_field(
            name="After",
            value=after.content[:1024] if after.content else "*Empty*",
            inline=False
        )
        embed.set_footer(text=f"Message ID: {before.id}")

        await channel.send(embed=embed)

    # ==================== MEMBER EVENTS ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.is_event_enabled(member.guild.id, 'member_join'):
            return

        channel = await self.get_log_channel(member.guild)
        if not channel:
            return

        account_age = datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)
        is_new = account_age.days < 7

        embed = discord.Embed(
            title="Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(member),
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.add_field(
            name="User",
            value=f"{member.mention} ({member.id})",
            inline=True
        )
        embed.add_field(
            name="Account Created",
            value=f"{member.created_at.strftime('%B %d, %Y')}\n({account_age.days} days ago)",
            inline=True
        )
        embed.add_field(
            name="Member Count",
            value=f"#{member.guild.member_count}",
            inline=True
        )

        if is_new:
            embed.add_field(
                name="⚠️ New Account",
                value=f"Account is only **{account_age.days} days old**",
                inline=False
            )

        embed.set_footer(text=f"ID: {member.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not self.is_event_enabled(member.guild.id, 'member_leave'):
            return

        channel = await self.get_log_channel(member.guild)
        if not channel:
            return

        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        time_in_server = None
        if member.joined_at:
            diff = datetime.now(timezone.utc) - member.joined_at.replace(tzinfo=timezone.utc)
            time_in_server = f"{diff.days} days"

        embed = discord.Embed(
            title="Member Left",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(member),
            icon_url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        embed.add_field(
            name="User",
            value=f"{member.mention} ({member.id})",
            inline=True
        )
        if time_in_server:
            embed.add_field(
                name="Time in Server",
                value=time_in_server,
                inline=True
            )
        if roles:
            embed.add_field(
                name=f"Roles ({len(roles)})",
                value=" ".join(roles[:10]) if roles else "None",
                inline=False
            )
        embed.set_footer(text=f"ID: {member.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if not self.is_event_enabled(guild.id, 'member_ban'):
            return

        channel = await self.get_log_channel(guild)
        if not channel:
            return

        # Try to get reason from audit log
        reason = "No reason provided"
        moderator = "Unknown"
        try:
            async for entry in guild.audit_logs(
                limit=1,
                action=discord.AuditLogAction.ban
            ):
                if entry.target.id == user.id:
                    reason = entry.reason or "No reason provided"
                    moderator = str(entry.user)
                    break
        except:
            pass

        embed = discord.Embed(
            title="Member Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(user),
            icon_url=user.avatar.url if user.avatar else None
        )
        embed.add_field(
            name="User",
            value=f"{user.mention} ({user.id})",
            inline=True
        )
        embed.add_field(name="Moderator", value=moderator, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"ID: {user.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        if not self.is_event_enabled(guild.id, 'member_unban'):
            return

        channel = await self.get_log_channel(guild)
        if not channel:
            return

        embed = discord.Embed(
            title="Member Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(user),
            icon_url=user.avatar.url if user.avatar else None
        )
        embed.add_field(
            name="User",
            value=f"{user.mention} ({user.id})",
            inline=True
        )
        embed.set_footer(text=f"ID: {user.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not self.is_event_enabled(before.guild.id, 'member_update'):
            return

        channel = await self.get_log_channel(before.guild)
        if not channel:
            return

        changes = []

        # Nickname change
        if before.nick != after.nick:
            changes.append(("Nickname", before.nick or "*None*", after.nick or "*None*"))

        # Role change
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        if not changes and not added_roles and not removed_roles:
            return

        embed = discord.Embed(
            title="Member Updated",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=str(after),
            icon_url=after.avatar.url if after.avatar else None
        )
        embed.add_field(
            name="User",
            value=f"{after.mention} ({after.id})",
            inline=False
        )

        for name, old, new in changes:
            embed.add_field(name=f"{name} Before", value=old, inline=True)
            embed.add_field(name=f"{name} After", value=new, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        if added_roles:
            embed.add_field(
                name="Roles Added",
                value=" ".join([r.mention for r in added_roles]),
                inline=False
            )
        if removed_roles:
            embed.add_field(
                name="Roles Removed",
                value=" ".join([r.mention for r in removed_roles]),
                inline=False
            )

        embed.set_footer(text=f"ID: {after.id}")
        await channel.send(embed=embed)

    # ==================== ROLE EVENTS ====================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if not self.is_event_enabled(role.guild.id, 'role_create'):
            return

        channel = await self.get_log_channel(role.guild)
        if not channel:
            return

        embed = discord.Embed(
            title="Role Created",
            color=role.color if role.color.value else discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Role", value=f"{role.mention} ({role.id})", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(
            name="Hoisted",
            value="Yes" if role.hoist else "No",
            inline=True
        )
        embed.set_footer(text=f"Role ID: {role.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        if not self.is_event_enabled(role.guild.id, 'role_delete'):
            return

        channel = await self.get_log_channel(role.guild)
        if not channel:
            return

        embed = discord.Embed(
            title="Role Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Role Name", value=role.name, inline=True)
        embed.add_field(
            name="Members Had",
            value=str(len(role.members)),
            inline=True
        )
        embed.set_footer(text=f"Role ID: {role.id}")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if not self.is_event_enabled(before.guild.id, 'role_update'):
            return

        channel = await self.get_log_channel(before.guild)
        if not channel:
            return

        changes = []
        if before.name != after.name:
            changes.append(("Name", before.name, after.name))
        if before.color != after.color:
            changes.append(("Color", str(before.color), str(after.color)))
        if before.hoist != after.hoist:
            changes.append(("Hoisted", str(before.hoist), str(after.hoist)))
        if before.mentionable != after.mentionable:
            changes.append((
                "Mentionable",
                str(before.mentionable),
                str(after.mentionable)
            ))

        if not changes:
            return

        embed = discord.Embed(
            title="Role Updated",
            color=after.color if after.color.value else discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Role",
            value=f"{after.mention} ({after.id})",
            inline=False
        )
        for name, old, new in changes:
            embed.add_field(name=f"{name} Before", value=old, inline=True)
            embed.add_field(name=f"{name} After", value=new, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.set_footer(text=f"Role ID: {after.id}")
        await channel.send(embed=embed)

    # ==================== CHANNEL EVENTS ====================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if not self.is_event_enabled(channel.guild.id, 'channel_create'):
            return

        log_channel = await self.get_log_channel(channel.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Channel Created",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="Channel",
            value=f"{channel.mention} ({channel.id})",
            inline=True
        )
        embed.add_field(
            name="Type",
            value=str(channel.type).replace('_', ' ').title(),
            inline=True
        )
        embed.add_field(
            name="Category",
            value=channel.category.name if channel.category else "None",
            inline=True
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if not self.is_event_enabled(channel.guild.id, 'channel_delete'):
            return

        log_channel = await self.get_log_channel(channel.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Channel Deleted",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Channel Name", value=f"#{channel.name}", inline=True)
        embed.add_field(
            name="Type",
            value=str(channel.type).replace('_', ' ').title(),
            inline=True
        )
        embed.add_field(
            name="Category",
            value=channel.category.name if channel.category else "None",
            inline=True
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")

        await log_channel.send(embed=embed)

    # ==================== VOICE EVENTS ====================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        if not self.is_event_enabled(member.guild.id, 'voice_update'):
            return
        if member.bot:
            return

        channel = await self.get_log_channel(member.guild)
        if not channel:
            return

        # Joined voice
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="Joined Voice Channel",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(
                name=str(member),
                icon_url=member.avatar.url if member.avatar else None
            )
            embed.add_field(
                name="User",
                value=f"{member.mention} ({member.id})",
                inline=True
            )
            embed.add_field(
                name="Channel",
                value=after.channel.mention,
                inline=True
            )

        # Left voice
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="Left Voice Channel",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(
                name=str(member),
                icon_url=member.avatar.url if member.avatar else None
            )
            embed.add_field(
                name="User",
                value=f"{member.mention} ({member.id})",
                inline=True
            )
            embed.add_field(
                name="Channel",
                value=before.channel.mention,
                inline=True
            )

        # Moved voice
        elif before.channel != after.channel:
            embed = discord.Embed(
                title="Moved Voice Channel",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(
                name=str(member),
                icon_url=member.avatar.url if member.avatar else None
            )
            embed.add_field(
                name="User",
                value=f"{member.mention} ({member.id})",
                inline=True
            )
            embed.add_field(
                name="From",
                value=before.channel.mention,
                inline=True
            )
            embed.add_field(
                name="To",
                value=after.channel.mention,
                inline=True
            )
        else:
            return

        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed)

    # ==================== SETUP COMMANDS ====================

    @app_commands.command(name="logs_setup", description="Setup server logging")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        enabled: bool = True
    ):
        """Setup server logs"""
        config = self.get_config(interaction.guild.id)
        config['enabled'] = enabled
        config['log_channel'] = str(channel.id)
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            title="Server Logs Configured",
            color=0x1a1a2e
        )
        embed.add_field(name="Log Channel", value=channel.mention, inline=True)
        embed.add_field(
            name="Status",
            value="Enabled" if enabled else "Disabled",
            inline=True
        )
        embed.set_footer(
            text="All server events will now be logged. Use /logs_toggle to disable specific events."
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="logs_toggle", description="Toggle specific log events")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(event="The event type to toggle")
    @app_commands.choices(event=[
        app_commands.Choice(name="Message Delete", value="message_delete"),
        app_commands.Choice(name="Message Edit", value="message_edit"),
        app_commands.Choice(name="Member Join", value="member_join"),
        app_commands.Choice(name="Member Leave", value="member_leave"),
        app_commands.Choice(name="Member Ban", value="member_ban"),
        app_commands.Choice(name="Member Unban", value="member_unban"),
        app_commands.Choice(name="Role Changes", value="role_create"),
        app_commands.Choice(name="Channel Changes", value="channel_create"),
        app_commands.Choice(name="Member Updates", value="member_update"),
        app_commands.Choice(name="Voice Updates", value="voice_update"),
    ])
    async def logs_toggle(
        self,
        interaction: discord.Interaction,
        event: app_commands.Choice[str]
    ):
        """Toggle a specific log event"""
        config = self.get_config(interaction.guild.id)
        current = config['events'].get(event.value, True)
        config['events'][event.value] = not current
        self.db.set(str(interaction.guild.id), config)

        status = "Disabled" if current else "Enabled"
        embed = discord.Embed(
            description=f"**{event.name}** logging is now **{status}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="logs_ignore", description="Ignore a channel from logging")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_ignore(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Toggle channel ignore"""
        config = self.get_config(interaction.guild.id)
        ignored = config.get('ignored_channels', [])

        if str(channel.id) in ignored:
            ignored.remove(str(channel.id))
            action = "removed from"
        else:
            ignored.append(str(channel.id))
            action = "added to"

        config['ignored_channels'] = ignored
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"{channel.mention} {action} ignored channels list.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerLogs(bot))