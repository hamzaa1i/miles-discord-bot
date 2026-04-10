import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.embeds import create_embed

class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="serverstats", description="View detailed server statistics")
    async def serverstats(self, interaction: discord.Interaction):
        """Detailed server stats"""
        guild = interaction.guild
        
        # Count members by status
        online = sum(1 for m in guild.members if m.status == discord.Status.online)
        idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
        dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
        offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
        
        # Count bots
        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        
        # Channel counts
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Other stats
        roles = len(guild.roles)
        emojis = len(guild.emojis)
        
        embed = create_embed(
            title=f"📊 {guild.name} Statistics",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # General info
        embed.add_field(
            name="👑 Owner",
            value=guild.owner.mention,
            inline=True
        )
        embed.add_field(
            name="📅 Created",
            value=guild.created_at.strftime("%b %d, %Y"),
            inline=True
        )
        embed.add_field(
            name="🆔 Server ID",
            value=f"`{guild.id}`",
            inline=True
        )
        
        # Members
        embed.add_field(
            name="👥 Members",
            value=f"Total: **{guild.member_count}**\n"
                  f"Humans: {humans}\n"
                  f"Bots: {bots}",
            inline=True
        )
        
        # Member status
        embed.add_field(
            name="📡 Status",
            value=f"🟢 {online}\n"
                  f"🟡 {idle}\n"
                  f"🔴 {dnd}\n"
                  f"⚫ {offline}",
            inline=True
        )
        
        # Channels
        embed.add_field(
            name="💬 Channels",
            value=f"Text: {text_channels}\n"
                  f"Voice: {voice_channels}\n"
                  f"Categories: {categories}",
            inline=True
        )
        
        # Other
        embed.add_field(
            name="🎭 Roles",
            value=roles,
            inline=True
        )
        embed.add_field(
            name="😃 Emojis",
            value=emojis,
            inline=True
        )
        embed.add_field(
            name="🚀 Boost Level",
            value=f"Level {guild.premium_tier}\n{guild.premium_subscription_count} boosts",
            inline=True
        )
        
        # Verification
        verification_level = str(guild.verification_level).replace('_', ' ').title()
        embed.add_field(
            name="🔒 Verification",
            value=verification_level,
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="Get information about a user")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        """User information"""
        user = user or interaction.user
        
        embed = create_embed(
            title=f"👤 {user.name}",
            color=user.color
        )
        
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        # Basic info
        embed.add_field(
            name="🆔 ID",
            value=f"`{user.id}`",
            inline=True
        )
        embed.add_field(
            name="📛 Nickname",
            value=user.display_name,
            inline=True
        )
        embed.add_field(
            name="🤖 Bot",
            value="Yes" if user.bot else "No",
            inline=True
        )
        
        # Dates
        embed.add_field(
            name="📅 Account Created",
            value=user.created_at.strftime("%b %d, %Y"),
            inline=True
        )
        embed.add_field(
            name="📥 Joined Server",
            value=user.joined_at.strftime("%b %d, %Y") if user.joined_at else "Unknown",
            inline=True
        )
        
        # Status
        status_emoji = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }
        embed.add_field(
            name="📡 Status",
            value=status_emoji.get(user.status, "Unknown"),
            inline=True
        )
        
        # Roles
        roles = [role.mention for role in user.roles[1:]]  # Skip @everyone
        if roles:
            roles_text = ", ".join(roles[:10])
            if len(user.roles) > 11:
                roles_text += f" +{len(user.roles) - 11} more"
        else:
            roles_text = "No roles"
        
        embed.add_field(
            name=f"🎭 Roles ({len(user.roles) - 1})",
            value=roles_text,
            inline=False
        )
        
        # Permissions
        perms = []
        if user.guild_permissions.administrator:
            perms.append("Administrator")
        if user.guild_permissions.manage_guild:
            perms.append("Manage Server")
        if user.guild_permissions.manage_roles:
            perms.append("Manage Roles")
        if user.guild_permissions.manage_channels:
            perms.append("Manage Channels")
        if user.guild_permissions.kick_members:
            perms.append("Kick Members")
        if user.guild_permissions.ban_members:
            perms.append("Ban Members")
        
        if perms:
            embed.add_field(
                name="🔑 Key Permissions",
                value=", ".join(perms),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="roleinfo", description="Get information about a role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Role information"""
        embed = create_embed(
            title=f"🎭 {role.name}",
            color=role.color
        )
        
        embed.add_field(name="🆔 ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="🎨 Color", value=str(role.color), inline=True)
        embed.add_field(name="👥 Members", value=len(role.members), inline=True)
        embed.add_field(name="📍 Position", value=role.position, inline=True)
        embed.add_field(name="📌 Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="🔔 Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="📅 Created", value=role.created_at.strftime("%b %d, %Y"), inline=True)
        
        # Permissions count
        perms = [perm for perm, value in role.permissions if value]
        embed.add_field(name="🔑 Permissions", value=len(perms), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="channelinfo", description="Get information about a channel")
    async def channelinfo(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Channel information"""
        channel = channel or interaction.channel
        
        embed = create_embed(
            title=f"💬 #{channel.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="🆔 ID", value=f"`{channel.id}`", inline=True)
        embed.add_field(name="📁 Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="📍 Position", value=channel.position, inline=True)
        embed.add_field(name="📅 Created", value=channel.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="🔞 NSFW", value="Yes" if channel.is_nsfw() else "No", inline=True)
        embed.add_field(name="📌 Topic", value=channel.topic or "No topic set", inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerStats(bot))