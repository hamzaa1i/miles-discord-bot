import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.database import Database

class RolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        self.guild = guild

    @discord.ui.button(
        label="View Roles",
        style=discord.ButtonStyle.primary,
        emoji="🎭"
    )
    async def roles_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        roles = [
            r for r in reversed(self.guild.roles)
            if r.name != "@everyone"
        ]
        if not roles:
            await interaction.response.send_message(
                "no roles found.",
                ephemeral=True
            )
            return

        roles_text = " ".join([r.mention for r in roles[:40]])
        if len(roles) > 40:
            roles_text += f"\n+{len(roles) - 40} more"

        embed = discord.Embed(
            title=f"{self.guild.name} — Roles",
            description=roles_text,
            color=0x1a1a2e
        )
        embed.set_footer(text=f"{len(roles)} roles total")
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

    @app_commands.command(name="serverinfo", description="Server information")
    async def serverinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild

        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(name=guild.name)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(
            name="Owner",
            value=guild.owner.mention,
            inline=True
        )
        embed.add_field(
            name="Created",
            value=guild.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        embed.add_field(
            name="Members",
            value=guild.member_count,
            inline=True
        )
        embed.add_field(
            name="Channels",
            value=len(guild.channels),
            inline=True
        )
        embed.add_field(
            name="Roles",
            value=len(guild.roles) - 1,
            inline=True
        )
        embed.add_field(
            name="Emojis",
            value=len(guild.emojis),
            inline=True
        )

        view = RolesView(guild)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="whois", description="Complete info about a user")
    async def whois(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
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



    @app_commands.command(name="avatar", description="Show user avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
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

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="membercount", description="Member count breakdown")
    async def membercount(self, interaction: discord.Interaction):
        await interaction.response.defer()
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




async def setup(bot):
    await bot.add_cog(ServerStats(bot))