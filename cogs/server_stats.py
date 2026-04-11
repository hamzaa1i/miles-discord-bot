import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database

class RolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(label="View Roles", style=discord.ButtonStyle.primary, emoji="🎭")
    async def roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        roles = [r for r in reversed(self.guild.roles) if r.name != "@everyone"]
        if not roles:
            await interaction.response.send_message("No roles found.", ephemeral=True)
            return

        roles_text = " ".join([r.mention for r in roles[:40]])
        if len(roles) > 40:
            roles_text += f"\n+{len(roles) - 40} more"

        embed = discord.Embed(
            title=f"Roles — {self.guild.name}",
            description=roles_text,
            color=0x1a1a2e
        )
        embed.set_footer(text=f"Total: {len(roles)} roles")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class WhoisView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=60)
        self.member = member

    @discord.ui.button(label="Permissions", style=discord.ButtonStyle.secondary, emoji="🔑")
    async def perms_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        perms = self.member.guild_permissions
        allowed = []
        denied = []

        perm_map = {
            'administrator': 'Administrator',
            'manage_guild': 'Manage Server',
            'manage_roles': 'Manage Roles',
            'manage_channels': 'Manage Channels',
            'manage_messages': 'Manage Messages',
            'manage_webhooks': 'Manage Webhooks',
            'manage_nicknames': 'Manage Nicknames',
            'manage_expressions': 'Manage Expressions',
            'kick_members': 'Kick Members',
            'ban_members': 'Ban Members',
            'moderate_members': 'Timeout Members',
            'mention_everyone': 'Mention Everyone',
            'view_audit_log': 'View Audit Log',
            'send_messages': 'Send Messages',
            'embed_links': 'Embed Links',
            'attach_files': 'Attach Files',
            'add_reactions': 'Add Reactions',
            'use_external_emojis': 'External Emojis',
            'connect': 'Connect Voice',
            'speak': 'Speak Voice',
            'mute_members': 'Mute Members',
            'deafen_members': 'Deafen Members',
            'move_members': 'Move Members',
        }

        for perm, name in perm_map.items():
            if getattr(perms, perm, False):
                allowed.append(f"✅ {name}")
            else:
                denied.append(f"❌ {name}")

        embed = discord.Embed(
            title=f"Permissions — {self.member.display_name}",
            color=0x1a1a2e
        )

        if allowed:
            embed.add_field(
                name="Allowed",
                value="\n".join(allowed[:12]),
                inline=True
            )
        if denied:
            embed.add_field(
                name="Denied",
                value="\n".join(denied[:12]),
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Roles", style=discord.ButtonStyle.secondary, emoji="🎭")
    async def roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        roles = [r for r in reversed(self.member.roles) if r.name != "@everyone"]

        if not roles:
            await interaction.response.send_message(
                "This user has no roles.",
                ephemeral=True
            )
            return

        roles_text = " ".join([r.mention for r in roles[:30]])
        if len(roles) > 30:
            roles_text += f"\n+{len(roles) - 30} more"

        embed = discord.Embed(
            title=f"Roles — {self.member.display_name}",
            description=roles_text,
            color=self.member.color if self.member.color.value else 0x1a1a2e
        )
        embed.set_footer(text=f"Total: {len(roles)} roles")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def avatar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = self.member
        embed = discord.Embed(
            title=f"Avatar — {member.display_name}",
            color=0x1a1a2e
        )
        embed.set_image(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )

        if member.avatar:
            links = (
                f"[PNG]({member.avatar.with_format('png').url}) | "
                f"[JPG]({member.avatar.with_format('jpeg').url}) | "
                f"[WEBP]({member.avatar.with_format('webp').url})"
            )
            embed.add_field(name="Download", value=links)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/server_stats.json')

    def format_date(self, dt: datetime) -> str:
        return dt.strftime("%B %d, %Y %I:%M %p UTC")

    def time_ago(self, dt: datetime) -> str:
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
            return f"{days // 30} months ago"
        else:
            return f"{days // 365} years ago"

    @app_commands.command(name="serverinfo", description="Detailed server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots

        verification_map = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low",
            discord.VerificationLevel.medium: "Medium",
            discord.VerificationLevel.high: "High",
            discord.VerificationLevel.highest: "Highest"
        }

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
            value=guild.owner.mention,
            inline=True
        )
        embed.add_field(
            name="Created",
            value=f"{guild.created_at.strftime('%b %d, %Y')}\n({self.time_ago(guild.created_at)})",
            inline=True
        )
        embed.add_field(
            name="ID",
            value=f"`{guild.id}`",
            inline=True
        )
        embed.add_field(
            name="Members",
            value=f"**{total:,}** total\n{humans:,} humans · {bots} bots",
            inline=True
        )
        embed.add_field(
            name="Boost",
            value=f"Level {guild.premium_tier} · {guild.premium_subscription_count} boosts",
            inline=True
        )
        embed.add_field(
            name="Verification",
            value=verification_map.get(guild.verification_level, "Unknown"),
            inline=True
        )
        embed.add_field(
            name="Channels",
            value=(
                f"{len(guild.text_channels)} text · "
                f"{len(guild.voice_channels)} voice · "
                f"{len(guild.categories)} categories"
            ),
            inline=True
        )
        embed.add_field(
            name="Roles",
            value=len(guild.roles) - 1,
            inline=True
        )
        embed.add_field(
            name="Emojis",
            value=f"{len(guild.emojis)} / {guild.emoji_limit}",
            inline=True
        )

        if guild.features:
            nice = [f.replace('_', ' ').title() for f in guild.features[:5]]
            embed.add_field(
                name="Features",
                value=", ".join(nice),
                inline=False
            )

        embed.set_footer(text=f"ID: {guild.id}")

        view = RolesView(guild)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="whois", description="Complete info about a user")
    async def whois(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user

        status_map = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }

        flags = user.public_flags
        badges = []
        if flags.staff: badges.append("Discord Staff")
        if flags.partner: badges.append("Partnered Server Owner")
        if flags.hypesquad_bravery: badges.append("HypeSquad Bravery")
        if flags.hypesquad_brilliance: badges.append("HypeSquad Brilliance")
        if flags.hypesquad_balance: badges.append("HypeSquad Balance")
        if flags.early_supporter: badges.append("Early Supporter")
        if flags.bug_hunter: badges.append("Bug Hunter")
        if flags.verified_bot_developer: badges.append("Verified Bot Dev")
        if flags.active_developer: badges.append("Active Developer")

        members_sorted = sorted(
            [m for m in interaction.guild.members],
            key=lambda m: m.joined_at or datetime.now(timezone.utc)
        )
        join_pos = members_sorted.index(user) + 1

        activity_text = "None"
        if user.activities:
            for act in user.activities:
                if isinstance(act, discord.Spotify):
                    activity_text = f"Listening to {act.title}"
                elif isinstance(act, discord.Game):
                    activity_text = f"Playing {act.name}"
                elif isinstance(act, discord.CustomActivity) and act.name:
                    activity_text = str(act.name)
                break

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

        embed.add_field(
            name="Created",
            value=f"{user.created_at.strftime('%b %d, %Y')}\n({self.time_ago(user.created_at)})",
            inline=True
        )
        embed.add_field(
            name="Joined",
            value=f"{user.joined_at.strftime('%b %d, %Y') if user.joined_at else 'Unknown'}\n(#{join_pos})",
            inline=True
        )
        embed.add_field(
            name="Status",
            value=status_map.get(user.status, "Unknown"),
            inline=True
        )
        embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
        embed.add_field(name="Activity", value=activity_text, inline=True)
        embed.add_field(
            name="Top Role",
            value=user.top_role.mention if user.top_role.name != "@everyone" else "None",
            inline=True
        )

        if badges:
            embed.add_field(
                name=f"Badges ({len(badges)})",
                value="\n".join(badges),
                inline=False
            )

        roles = [r for r in user.roles if r.name != "@everyone"]
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join([r.mention for r in reversed(roles[:10])]) or "None",
            inline=False
        )

        embed.set_footer(text=f"ID: {user.id}")

        view = WhoisView(user)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="roleinfo", description="Detailed role information")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(
            title=f"Role: {role.name}",
            color=role.color if role.color.value else 0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        perms = []
        if role.permissions.administrator: perms.append("Administrator")
        if role.permissions.manage_guild: perms.append("Manage Server")
        if role.permissions.manage_roles: perms.append("Manage Roles")
        if role.permissions.manage_channels: perms.append("Manage Channels")
        if role.permissions.manage_messages: perms.append("Manage Messages")
        if role.permissions.kick_members: perms.append("Kick Members")
        if role.permissions.ban_members: perms.append("Ban Members")
        if role.permissions.moderate_members: perms.append("Timeout Members")

        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(
            name="Created",
            value=role.created_at.strftime("%b %d, %Y"),
            inline=True
        )
        embed.add_field(name="Position", value=f"#{role.position}", inline=True)
        embed.add_field(name="Members", value=f"{len(role.members):,}", inline=True)
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
            name="Key Permissions",
            value=", ".join(perms) if perms else "None",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="channelinfo", description="Channel information")
    async def channelinfo(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        channel = channel or interaction.channel

        embed = discord.Embed(
            title=f"#{channel.name}",
            color=0x1a1a2e,
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
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
            value=f"{channel.created_at.strftime('%b %d, %Y')}\n({self.time_ago(channel.created_at)})",
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

        embed.set_footer(text=f"ID: {channel.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Show user avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"{user.display_name}'s Avatar",
            color=0x1a1a2e
        )
        embed.set_image(
            url=user.avatar.url if user.avatar else user.default_avatar.url
        )

        if user.avatar:
            links = (
                f"[PNG]({user.avatar.with_format('png').url}) | "
                f"[JPG]({user.avatar.with_format('jpeg').url}) | "
                f"[WEBP]({user.avatar.with_format('webp').url})"
            )
            if user.avatar.is_animated():
                links += f" | [GIF]({user.avatar.with_format('gif').url})"
            embed.add_field(name="Download", value=links)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Show user banner")
    async def banner(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        fetched = await self.bot.fetch_user(user.id)

        if not fetched.banner:
            await interaction.response.send_message(
                f"{user.display_name} doesn't have a banner.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{user.display_name}'s Banner",
            color=fetched.accent_color or 0x1a1a2e
        )
        embed.set_image(url=fetched.banner.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="membercount", description="Member count breakdown")
    async def membercount(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)

        embed = discord.Embed(
            title=f"{guild.name} — Members",
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

    @app_commands.command(name="inrole", description="List members with a specific role")
    async def inrole(self, interaction: discord.Interaction, role: discord.Role):
        members = role.members

        if not members:
            await interaction.response.send_message(
                f"No members have {role.mention}",
                ephemeral=True
            )
            return

        member_list = " ".join([m.mention for m in members[:50]])
        if len(members) > 50:
            member_list += f" +{len(members) - 50} more"

        embed = discord.Embed(
            title=f"Members with {role.name}",
            description=member_list,
            color=role.color if role.color.value else 0x1a1a2e
        )
        embed.set_footer(text=f"{len(members)} total")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="permissions", description="Check permissions for a user")
    async def permissions(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        channel: discord.TextChannel = None
    ):
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
            'read_message_history': 'Read History',
            'mention_everyone': 'Mention Everyone',
            'add_reactions': 'Add Reactions',
            'use_external_emojis': 'External Emojis',
            'manage_channels': 'Manage Channel',
            'administrator': 'Administrator',
        }

        for perm, name in perm_names.items():
            if getattr(perms, perm, False):
                allowed.append(f"✅ {name}")
            else:
                denied.append(f"❌ {name}")

        embed = discord.Embed(
            title=f"Permissions — {user.display_name}",
            color=0x1a1a2e
        )
        embed.set_author(
            name=f"In #{channel.name}",
            icon_url=user.avatar.url if user.avatar else None
        )

        if allowed:
            embed.add_field(name="Allowed", value="\n".join(allowed), inline=True)
        if denied:
            embed.add_field(name="Denied", value="\n".join(denied), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="roles", description="List all server roles")
    async def roles(self, interaction: discord.Interaction):
        roles = [r for r in reversed(interaction.guild.roles) if r.name != "@everyone"]

        if not roles:
            await interaction.response.send_message("No roles found.", ephemeral=True)
            return

        roles_text = " ".join([r.mention for r in roles[:30]])
        if len(roles) > 30:
            roles_text += f"\n+{len(roles) - 30} more"

        embed = discord.Embed(
            title=f"{interaction.guild.name} — Roles",
            description=roles_text,
            color=0x1a1a2e
        )
        embed.set_footer(text=f"Total: {len(roles)} roles")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="emojis", description="List all server emojis")
    async def emojis(self, interaction: discord.Interaction):
        emojis = interaction.guild.emojis

        if not emojis:
            await interaction.response.send_message(
                "No custom emojis.",
                ephemeral=True
            )
            return

        static = [e for e in emojis if not e.animated]
        animated = [e for e in emojis if e.animated]

        embed = discord.Embed(
            title=f"{interaction.guild.name} — Emojis",
            color=0x1a1a2e
        )

        if static:
            embed.add_field(
                name=f"Static ({len(static)})",
                value=" ".join([str(e) for e in static[:20]]) or "None",
                inline=False
            )
        if animated:
            embed.add_field(
                name=f"Animated ({len(animated)})",
                value=" ".join([str(e) for e in animated[:20]]) or "None",
                inline=False
            )

        embed.set_footer(text=f"Total: {len(emojis)} / {interaction.guild.emoji_limit}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="firstmessage", description="Get link to first message in channel")
    async def firstmessage(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        channel = channel or interaction.channel
        await interaction.response.defer()

        async for message in channel.history(limit=1, oldest_first=True):
            embed = discord.Embed(
                title="First Message",
                description=message.content or "*No text*",
                color=0x1a1a2e,
                timestamp=message.created_at
            )
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url if message.author.avatar else None
            )
            embed.add_field(
                name="Jump",
                value=f"[Click here]({message.jump_url})"
            )
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send("No messages found.")


async def setup(bot):
    await bot.add_cog(ServerStats(bot))