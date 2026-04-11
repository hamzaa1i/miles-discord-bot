import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from utils.database import Database

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/moderation.json')

    def log_action(self, guild_id, action, moderator, target, reason):
        data = self.db.get(str(guild_id), {'actions': []})
        data['actions'].append({
            'action': action, 'moderator': moderator,
            'target': target, 'reason': reason,
            'timestamp': discord.utils.utcnow().isoformat()
        })
        if len(data['actions']) > 100:
            data['actions'] = data['actions'][-100:]
        self.db.set(str(guild_id), data)

    mod = app_commands.Group(name="mod", description="Moderation commands")

    @mod.command(name="kick", description="Kick a member")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("can't kick someone with equal or higher role.", ephemeral=True)
            return
        try:
            try:
                dm = discord.Embed(description=f"you were kicked from **{interaction.guild.name}**\nreason: {reason}", color=0x1a1a2e)
                await member.send(embed=dm)
            except: pass
            await member.kick(reason=reason)
            self.log_action(interaction.guild.id, "kick", str(interaction.user), str(member), reason)
            embed = discord.Embed(description=f"kicked **{member}**\nreason: {reason}", color=0x1a1a2e)
            embed.set_footer(text=f"by {interaction.user}")
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission to kick this member.", ephemeral=True)

    @mod.command(name="ban", description="Ban a member")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason", delete_messages: bool = False):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("can't ban someone with equal or higher role.", ephemeral=True)
            return
        try:
            try:
                dm = discord.Embed(description=f"you were banned from **{interaction.guild.name}**\nreason: {reason}", color=0x1a1a2e)
                await member.send(embed=dm)
            except: pass
            await member.ban(reason=reason, delete_message_days=1 if delete_messages else 0)
            self.log_action(interaction.guild.id, "ban", str(interaction.user), str(member), reason)
            embed = discord.Embed(description=f"banned **{member}**\nreason: {reason}", color=0x1a1a2e)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="unban", description="Unban a user")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            self.log_action(interaction.guild.id, "unban", str(interaction.user), str(user), "Unbanned")
            embed = discord.Embed(description=f"unbanned **{user}**", color=0x1a1a2e)
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("user not found or not banned.", ephemeral=True)

    @mod.command(name="timeout", description="Timeout a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
        time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            amount = int(duration[:-1])
            seconds = amount * time_units[unit]
            if seconds > 2419200:
                await interaction.response.send_message("max timeout is 28 days.", ephemeral=True)
                return
        except:
            await interaction.response.send_message("invalid format. use like: 10m, 1h, 2d", ephemeral=True)
            return
        try:
            await member.timeout(timedelta(seconds=seconds), reason=reason)
            self.log_action(interaction.guild.id, "timeout", str(interaction.user), str(member), f"{reason} ({duration})")
            embed = discord.Embed(description=f"timed out **{member}** for **{duration}**\nreason: {reason}", color=0x1a1a2e)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="untimeout", description="Remove timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None)
            embed = discord.Embed(description=f"timeout removed from **{member}**", color=0x1a1a2e)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="warn", description="Warn a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        self.log_action(interaction.guild.id, "warn", str(interaction.user), str(member), reason)
        try:
            dm = discord.Embed(description=f"you were warned in **{interaction.guild.name}**\nreason: {reason}", color=0x1a1a2e)
            await member.send(embed=dm)
        except: pass
        embed = discord.Embed(description=f"warned **{member}**\nreason: {reason}", color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    @mod.command(name="purge", description="Delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            await interaction.response.send_message("amount must be 1-100.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"deleted {len(deleted)} messages.", ephemeral=True)

    @mod.command(name="logs", description="View moderation logs")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def modlogs(self, interaction: discord.Interaction, limit: int = 10):
        data = self.db.get(str(interaction.guild.id), {'actions': []})
        if not data['actions']:
            await interaction.response.send_message("no mod logs.", ephemeral=True)
            return
        logs = data['actions'][-limit:]
        logs.reverse()
        embed = discord.Embed(title="Moderation Logs", color=0x1a1a2e)
        emojis = {'kick': '👢', 'ban': '🔨', 'unban': '✅', 'timeout': '🔇', 'warn': '⚠️'}
        for log in logs:
            embed.add_field(
                name=f"{emojis.get(log['action'], '📝')} {log['action'].title()}",
                value=f"**Target:** {log['target']}\n**Mod:** {log['moderator']}\n**Reason:** {log['reason']}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))