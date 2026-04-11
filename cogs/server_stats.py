import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database

class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/server_stats.json')

    def format_date(self, dt: datetime) -> str:
        """Format datetime like Dyno"""
        return dt.strftime("%B %d, %Y %I:%M %p UTC")

    def time_ago(self, dt: datetime) -> str:
        """How long ago something happened"""
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        days = diff.days
        if days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes} minutes ago"
            return f"{hours} hours ago"
        elif days == 1:
            return "Yesterday"
        elif days < 30:
            return f"{days} days ago"
        elif days < 365:
            months = days // 30
            return f"{months} months ago"
        else:
            years = days // 365
            return f"{years} years ago"

    @app_commands.command(name="whois", description="Get complete info about a user")
    async def whois(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Complete user info like Dyno's whois"""
        user = user or interaction.user

        embed = discord.Embed(
            color=user.color if user.color.value else 0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        embed.set_author(
            name=f"{user} ({user.id})",
            icon_url=user.avatar.url if user.avatar else user.default_avatar.url
        )

        embed.set_thumbnail(
            url=user.avatar.url if user.avatar else user.default_avatar.url
        )

        # Status
        status_map = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }
        status = status_map.get(user.status, "⚫ Offline")

        # Badges/flags
        flags = user.public_flags
        badges = []
        if flags.staff: badges.append("Discord Staff")
        if flags.partner: badges.append("Partnered Server Owner")
        if flags.hypesquad: badges.append("HypeSquad Events")
        if flags.bug_hunter: badges.append("Bug Hunter")
        if flags.hypesquad_bravery: badges.append("HypeSquad Bravery")
        if flags.hypesquad_brilliance: badges.append("HypeSquad Brilliance")
        if flags.hypesquad_balance: badges.append("HypeSquad Balance")
        if flags.early_supporter: badges.append("Early Supporter")
        if flags.verified_bot_developer: badges.append("Verified Bot Developer")
        if flags.active_developer: badges.append("Active Developer")

        # Activity
        activity_text = "None"
        if user.activities:
            for activity in user.activities:
                if isinstance(activity, discord.Spotify):
                    activity_text = f"Listening to **{activity.title}** by {activity.artist}"
                elif isinstance(activity, discord.Game):
                    activity_text = f"Playing **{activity.name}**"
                elif isinstance(activity, discord.Streaming):
                    activity_text = f"Streaming **{activity.name}**"
                elif isinstance(activity, discord.CustomActivity):
                    activity_text = str(activity.name) if activity.name else "None"
                break

        # Joined position
        members_sorted = sorted(
            [m for m in interaction.guild.members],
            key=lambda m: m.joined_at or datetime.now(timezone.utc)
        )
        join_position = members_sorted.index(user) + 1

        # Account info
        embed.add_field(
            name="Account Created",
            value=f"{self.format_date(user.created_at)}\n({self.time_ago(user.created_at)})",
            inline=True
        )
        embed.add_field(
            name="Joined Server",
            value=f"{self.format_date(user.joined_at)}\n({self.time_ago(user.joined_at)})" if user.joined_at else "Unknown",
            inline=True
        )
        embed.add_field(
            name="Join Position",
            value=f"#{join_position}",
            inline=True
        )

        # Status & Activity
        embed.add_field(
            name="Status",
            value=status,
            inline=True
        )
        embed.add_field(
            name="Activity",
            value=activity_text,
            inline=True
        )
        embed.add_field(
            name="Bot",
            value="Yes" if user.bot else "No",
            inline=True
        )

        # Badges
        if badges:
            embed.add_field(
                name=f"Badges ({len(badges)})",
                value="\n".join(badges),
                inline=False
            )

        # Roles (excluding @everyone)
        roles = [r for r in reversed(user.roles) if r.name != "@everyone"]
        if roles:
            if len(roles) > 15:
                roles_text = " ".join([r.mention for r in roles[:15]])
                roles_text += f" and {len(roles) - 15} more"
            else:
                roles_text = " ".join([r.mention for r in roles])
        else:
            roles_text = "No roles"

        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=roles_text,
            inline=False
        )

        # Key Permissions
        key_perms = []
        perms = user.guild_permissions
        if perms.administrator: key_perms.append("Administrator")
        if perms.manage_guild: key_perms.append("Manage Server")
        if perms.manage_roles: key_perms.append("Manage Roles")
        if perms.manage_channels: key_perms.append("Manage Channels")
        if perms.manage_messages: key_perms.append("Manage Messages")
        if perms.manage_webhooks: key_perms.append("Manage Webhooks")
        if perms.manage_nicknames: key_perms.append("Manage Nicknames")
        if perms.kick_members: key_perms.append("Kick Members")
        if perms.ban_members: key_perms.append("Ban Members")
        if perms.mention_everyone: key_perms.append("Mention Everyone")
        if perms.moderate_members: key_perms.append("Timeout Members")

        if key_perms:
            embed.add_field(
                name="Key Permissions",
                value=", ".join(key_perms),
                inline=False
            )

        embed.set_footer(
            text=f"ID: {user.id}",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Detailed server information")
    async def serverinfo(self, interaction: discord.Interaction):
        """Detailed server info like Dyno"""
        guild = interaction.guild

        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        stage_channels = len(guild.stage_channels)
        forum_channels = len(guild.forums) if hasattr(guild, 'forums') else 0

        # Count members
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots

        # Verification level
        verification_map = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low — Must have verified email",
            discord.VerificationLevel.medium: "Medium — Registered for 5+ minutes",
            discord.VerificationLevel.high: "High — Member for 10+ minutes",
            discord.VerificationLevel.highest: "Highest — Must have verified phone"
        }

        # Content filter
        filter_map = {
            discord.ContentFilter.disabled: "Disabled",
            discord.ContentFilter.no_role: "Scan messages from members without a role",
            discord.ContentFilter.all_members: "Scan messages from all members"
        }

        # 2FA
        mfa = "Enabled" if guild.mfa_level else "Disabled"

        embed = discord.Embed(
            title=guild.name,
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(
            name="Owner",
            value=f"{guild.owner.mention}\n{guild.owner}",
            inline=True
        )
        embed.add_field(
            name="Created",
            value=f"{self.format_date(guild.created_at)}\n({self.time_ago(guild.created_at)})",
            inline=True
        )
        embed.add_field(
            name="Server ID",
            value=f"`{guild.id}`",
            inline=True
        )
        embed.add_field(
            name="Members",
            value=f"Total: **{total:,}**\nHumans: {humans:,}\nBots: {bots:,}",
            inline=True
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Text: {text_channels}\n"
                f"Voice: {voice_channels}\n"
                f"Categories: {categories}\n"
                f"Stage: {stage_channels}"
            ),
            inline=True
        )
        embed.add_field(
            name="Other",
            value=(
                f"Roles: {len(guild.roles)}\n"
                f"Emojis: {len(guild.emojis)}\n"
                f"Stickers: {len(guild.stickers)}\n"
                f"Boosts: {guild.premium_subscription_count}"
            ),
            inline=True
        )
        embed.add_field(
            name="Boost Status",
            value=f"Level {guild.premium_tier}\n{guild.premium_subscription_count} boosts",
            inline=True
        )
        embed.add_field(
            name="Verification Level",
            value=verification_map.get(guild.verification_level, "Unknown"),
            inline=True
        )
        embed.add_field(
            name="2FA Requirement",
            value=mfa,
            inline=True
        )
        embed.add_field(
            name="Content Filter",
            value=filter_map.get(guild.explicit_content_filter, "Unknown"),
            inline=False
        )

        # Features
        if guild.features:
            nice_features = [f.replace('_', ' ').title() for f in guild.features]
            embed.add_field(
                name=f"Server Features ({len(guild.features)})",
                value=", ".join(nice_features[:10]),
                inline=False
            )

        embed.set_footer(text=f"ID: {guild.id}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Get detailed information about a role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Detailed role info"""
        embed = discord.Embed(
            title=f"Role: {role.name}",
            color=role.color if role.color.value else 0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        # Permissions
        perms = []
        if role.permissions.administrator: perms.append("Administrator")
        if role.permissions.manage_guild: perms.append("Manage Server")
        if role.permissions.manage_roles: perms.append("Manage Roles")
        if role.permissions.manage_channels: perms.append("Manage Channels")
        if role.permissions.manage_messages: perms.append("Manage Messages")
        if role.permissions.kick_members: perms.append("Kick Members")
        if role.permissions.ban_members: perms.append("Ban Members")
        if role.permissions.mention_everyone: perms.append("Mention Everyone")
        if role.permissions.manage_webhooks: perms.append("Manage Webhooks")
        if role.permissions.moderate_members: perms.append("Timeout Members")
        if role.permissions.view_audit_log: perms.append("View Audit Log")
        if role.permissions.manage_expressions: perms.append("Manage Expressions")

        embed.add_field(name="Role ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(
            name="Created",
            value=self.format_date(role.created_at),
            inline=True
        )
        embed.add_field(name="Position", value=f"#{role.position}", inline=True)
        embed.add_field(
            name="Members",
            value=f"{len(role.members):,}",
            inline=True
        )
        embed.add_field(
            name="Mentionable",
            value="Yes" if role.mentionable else "No",
            inline=True
        )
        embed.add_field(
            name="Hoisted",
            value="Yes" if role.hoist else "No",
            inline=True
        )
        embed.add_field(
            name="Managed",
            value="Yes" if role.managed else "No",
            inline=True
        )
        embed.add_field(
            name="Mention",
            value=role.mention,
            inline=True
        )

        if perms:
            embed.add_field(
                name=f"Key Permissions ({len(perms)})",
                value=", ".join(perms),
                inline=False
            )
        else:
            embed.add_field(
                name="Key Permissions",
                value="No elevated permissions",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channelinfo", description="Get detailed channel information")
    async def channelinfo(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        """Detailed channel info"""
        channel = channel or interaction.channel

        embed = discord.Embed(
            title=f"#{channel.name}",
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Channel ID", value=f"`{channel.id}`", inline=True)
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
        embed.add_field(
            name="Created",
            value=f"{self.format_date(channel.created_at)}\n({self.time_ago(channel.created_at)})",
            inline=True
        )
        embed.add_field(name="Position", value=f"#{channel.position}", inline=True)
        embed.add_field(
            name="NSFW",
            value="Yes" if channel.is_nsfw() else "No",
            inline=True
        )

        if hasattr(channel, 'slowmode_delay') and channel.slowmode_delay:
            embed.add_field(
                name="Slowmode",
                value=f"{channel.slowmode_delay}s",
                inline=True
            )

        if channel.topic:
            embed.add_field(
                name="Topic",
                value=channel.topic[:1024],
                inline=False
            )

        # Who can access
        overwrites = channel.overwrites
        if overwrites:
            access_list = []
            for target, overwrite in list(overwrites.items())[:5]:
                if overwrite.read_messages is True:
                    access_list.append(f"✅ {target.mention}")
                elif overwrite.read_messages is False:
                    access_list.append(f"❌ {target.mention}")

            if access_list:
                embed.add_field(
                    name="Channel Access",
                    value="\n".join(access_list),
                    inline=False
                )

        embed.set_footer(text=f"ID: {channel.id}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Show full avatar of a user")
    async def avatar(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Show user avatar"""
        user = user or interaction.user

        embed = discord.Embed(
            title=f"{user.display_name}'s Avatar",
            color=0x1a1a2e
        )

        # Server avatar vs global avatar
        if user.guild_avatar:
            embed.set_image(url=user.guild_avatar.url)
            embed.set_thumbnail(
                url=user.avatar.url if user.avatar else user.default_avatar.url
            )
            embed.set_footer(text="Server Avatar shown | Global Avatar in thumbnail")
        else:
            embed.set_image(
                url=user.avatar.url if user.avatar else user.default_avatar.url
            )

        # Avatar links
        if user.avatar:
            links = (
                f"[PNG]({user.avatar.with_format('png').url}) | "
                f"[JPG]({user.avatar.with_format('jpeg').url}) | "
                f"[WEBP]({user.avatar.with_format('webp').url})"
            )
            if user.avatar.is_animated():
                links += f" | [GIF]({user.avatar.with_format('gif').url})"
            embed.add_field(name="Download Links", value=links)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Show user's banner")
    async def banner(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Show user banner"""
        user = user or interaction.user

        # Need to fetch user for banner
        fetched_user = await self.bot.fetch_user(user.id)

        if not fetched_user.banner:
            embed = discord.Embed(
                description=f"{user.mention} doesn't have a banner.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{user.display_name}'s Banner",
            color=fetched_user.accent_color or 0x1a1a2e
        )
        embed.set_image(url=fetched_user.banner.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="membercount", description="Show server member count")
    async def membercount(self, interaction: discord.Interaction):
        """Member count breakdown"""
        guild = interaction.guild

        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        online = sum(
            1 for m in guild.members
            if m.status != discord.Status.offline and not m.bot
        )

        embed = discord.Embed(
            title=f"{guild.name} — Member Count",
            color=0x1a1a2e
        )
        embed.add_field(name="Total", value=f"{total:,}", inline=True)
        embed.add_field(name="Humans", value=f"{humans:,}", inline=True)
        embed.add_field(name="Bots", value=f"{bots:,}", inline=True)
        embed.add_field(name="Online", value=f"{online:,}", inline=True)
        embed.add_field(name="Offline", value=f"{humans - online:,}", inline=True)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inrole", description="List all members with a specific role")
    async def inrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """List members in a role"""
        members = role.members

        if not members:
            embed = discord.Embed(
                description=f"No members have the {role.mention} role.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed)
            return

        # Split into chunks if too many
        member_list = ", ".join([m.mention for m in members[:50]])
        if len(members) > 50:
            member_list += f" and {len(members) - 50} more"

        embed = discord.Embed(
            title=f"Members with {role.name}",
            description=member_list,
            color=role.color if role.color.value else 0x1a1a2e
        )
        embed.set_footer(text=f"{len(members)} total members")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="permissions", description="Check a user's permissions in a channel")
    async def permissions(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        channel: discord.TextChannel = None
    ):
        """Check permissions for a user in a channel"""
        user = user or interaction.user
        channel = channel or interaction.channel

        perms = channel.permissions_for(user)

        allowed = []
        denied = []

        perm_names = {
            'read_messages': 'Read Messages',
            'send_messages': 'Send Messages',
            'manage_messages': 'Manage Messages',
            'embed_links': 'Embed Links',
            'attach_files': 'Attach Files',
            'read_message_history': 'Read Message History',
            'mention_everyone': 'Mention Everyone',
            'add_reactions': 'Add Reactions',
            'use_external_emojis': 'Use External Emojis',
            'manage_channels': 'Manage Channel',
            'manage_webhooks': 'Manage Webhooks',
            'send_tts_messages': 'Send TTS',
            'connect': 'Connect',
            'speak': 'Speak',
            'administrator': 'Administrator',
        }

        for perm, name in perm_names.items():
            if getattr(perms, perm, False):
                allowed.append(f"✅ {name}")
            else:
                denied.append(f"❌ {name}")

        embed = discord.Embed(
            title=f"Permissions for {user.display_name}",
            color=0x1a1a2e
        )
        embed.set_author(
            name=f"In #{channel.name}",
            icon_url=user.avatar.url if user.avatar else None
        )

        if allowed:
            embed.add_field(
                name="Allowed",
                value="\n".join(allowed),
                inline=True
            )
        if denied:
            embed.add_field(
                name="Denied",
                value="\n".join(denied),
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="emojis", description="List all server emojis")
    async def emojis(self, interaction: discord.Interaction):
        """List server emojis"""
        emojis = interaction.guild.emojis

        if not emojis:
            embed = discord.Embed(
                description="This server has no custom emojis.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed)
            return

        static = [e for e in emojis if not e.animated]
        animated = [e for e in emojis if e.animated]

        embed = discord.Embed(
            title=f"{interaction.guild.name} — Emojis",
            color=0x1a1a2e
        )
        embed.add_field(
            name=f"Static ({len(static)})",
            value=" ".join([str(e) for e in static[:20]]) or "None",
            inline=False
        )
        embed.add_field(
            name=f"Animated ({len(animated)})",
            value=" ".join([str(e) for e in animated[:20]]) or "None",
            inline=False
        )
        embed.set_footer(
            text=f"Total: {len(emojis)} / {interaction.guild.emoji_limit}"
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roles", description="List all server roles")
    async def roles(self, interaction: discord.Interaction):
        """List all roles"""
        roles = [
            r for r in reversed(interaction.guild.roles)
            if r.name != "@everyone"
        ]

        if not roles:
            await interaction.response.send_message(
                "No roles found.",
                ephemeral=True
            )
            return

        # Show top 30 roles
        roles_text = " ".join([r.mention for r in roles[:30]])
        if len(roles) > 30:
            roles_text += f"\n+{len(roles) - 30} more roles"

        embed = discord.Embed(
            title=f"{interaction.guild.name} — Roles",
            description=roles_text,
            color=0x1a1a2e
        )
        embed.set_footer(text=f"Total: {len(roles)} roles")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="firstmessage", description="Get link to first message in a channel")
    async def firstmessage(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        """Get first message in channel"""
        channel = channel or interaction.channel

        await interaction.response.defer()

        async for message in channel.history(limit=1, oldest_first=True):
            embed = discord.Embed(
                title="First Message",
                description=message.content or "*No text content*",
                color=0x1a1a2e,
                timestamp=message.created_at
            )
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url if message.author.avatar else None
            )
            embed.add_field(
                name="Jump to Message",
                value=f"[Click here]({message.jump_url})"
            )
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send("No messages found.")

async def setup(bot):
    await bot.add_cog(ServerStats(bot))