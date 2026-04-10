import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from utils.embeds import create_embed
from utils.database import Database

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/moderation.json')
    
    def log_action(self, guild_id: int, action: str, moderator: str, target: str, reason: str):
        """Log moderation action"""
        data = self.db.get(str(guild_id), {'actions': []})
        data['actions'].append({
            'action': action,
            'moderator': moderator,
            'target': target,
            'reason': reason,
            'timestamp': discord.utils.utcnow().isoformat()
        })
        # Keep only last 100 actions
        if len(data['actions']) > 100:
            data['actions'] = data['actions'][-100:]
        self.db.set(str(guild_id), data)
    
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a member"""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot kick someone with an equal or higher role!", ephemeral=True)
            return
        
        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
            return
        
        try:
            # DM the user
            try:
                dm_embed = create_embed(
                    title=f"🚪 Kicked from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.orange()
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            # Kick the member
            await member.kick(reason=reason)
            
            # Log action
            self.log_action(
                interaction.guild.id,
                "kick",
                str(interaction.user),
                str(member),
                reason
            )
            
            # Confirm
            embed = create_embed(
                title="👢 Member Kicked",
                description=f"**{member.mention}** has been kicked.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this member!", ephemeral=True)
    
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_messages: bool = False):
        """Ban a member"""
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot ban someone with an equal or higher role!", ephemeral=True)
            return
        
        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
            return
        
        try:
            # DM the user
            try:
                dm_embed = create_embed(
                    title=f"🔨 Banned from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.red()
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            # Ban the member
            delete_days = 1 if delete_messages else 0
            await member.ban(reason=reason, delete_message_days=delete_days)
            
            # Log action
            self.log_action(
                interaction.guild.id,
                "ban",
                str(interaction.user),
                str(member),
                reason
            )
            
            # Confirm
            embed = create_embed(
                title="🔨 Member Banned",
                description=f"**{member.mention}** has been banned.",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this member!", ephemeral=True)
    
    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        """Unban a user by ID"""
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            
            # Log action
            self.log_action(
                interaction.guild.id,
                "unban",
                str(interaction.user),
                str(user),
                "Unbanned"
            )
            
            embed = create_embed(
                title="✅ User Unbanned",
                description=f"**{user.mention}** has been unbanned.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID!", ephemeral=True)
    
    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        """Timeout a member (e.g., 10m, 1h, 1d)"""
        # Parse duration
        time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            amount = int(duration[:-1])
            seconds = amount * time_units[unit]
            
            if seconds > 2419200:  # Max 28 days
                await interaction.response.send_message("❌ Maximum timeout is 28 days!", ephemeral=True)
                return
            
        except:
            await interaction.response.send_message("❌ Invalid duration! Use format like: 10m, 1h, 2d", ephemeral=True)
            return
        
        try:
            await member.timeout(timedelta(seconds=seconds), reason=reason)
            
            # Log action
            self.log_action(
                interaction.guild.id,
                "timeout",
                str(interaction.user),
                str(member),
                f"{reason} ({duration})"
            )
            
            embed = create_embed(
                title="🔇 Member Timed Out",
                description=f"**{member.mention}** has been timed out for **{duration}**.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this member!", ephemeral=True)
    
    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        """Remove timeout"""
        try:
            await member.timeout(None)
            
            embed = create_embed(
                title="🔊 Timeout Removed",
                description=f"**{member.mention}** can now speak again.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission!", ephemeral=True)
    
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        """Warn a member"""
        # Log warning
        self.log_action(
            interaction.guild.id,
            "warn",
            str(interaction.user),
            str(member),
            reason
        )
        
        # DM the user
        try:
            dm_embed = create_embed(
                title=f"⚠️ Warning in {interaction.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow()
            )
            await member.send(embed=dm_embed)
        except:
            pass
        
        embed = create_embed(
            title="⚠️ Member Warned",
            description=f"**{member.mention}** has been warned.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="purge", description="Delete multiple messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        """Delete messages"""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        deleted = await interaction.channel.purge(limit=amount)
        
        embed = create_embed(
            title="🗑️ Messages Purged",
            description=f"Deleted **{len(deleted)}** messages.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="modlogs", description="View moderation logs")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def modlogs(self, interaction: discord.Interaction, limit: int = 10):
        """View recent mod actions"""
        data = self.db.get(str(interaction.guild.id), {'actions': []})
        
        if not data['actions']:
            await interaction.response.send_message("📋 No moderation logs yet!", ephemeral=True)
            return
        
        logs = data['actions'][-limit:]
        logs.reverse()
        
        embed = create_embed(
            title="📋 Moderation Logs",
            description=f"Last {len(logs)} actions",
            color=discord.Color.blue()
        )
        
        for log in logs:
            action_emoji = {
                'kick': '👢',
                'ban': '🔨',
                'unban': '✅',
                'timeout': '🔇',
                'warn': '⚠️'
            }.get(log['action'], '📝')
            
            embed.add_field(
                name=f"{action_emoji} {log['action'].title()}",
                value=f"**Target:** {log['target']}\n**Mod:** {log['moderator']}\n**Reason:** {log['reason']}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))