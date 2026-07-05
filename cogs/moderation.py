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
        data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        if 'actions' not in data:
            data['actions'] = []
        if 'warnings' not in data:
            data['warnings'] = {}
        data['actions'].append({
            'action': action, 'moderator': moderator,
            'target': target, 'reason': reason,
            'timestamp': discord.utils.utcnow().isoformat()
        })
        if len(data['actions']) > 100:
            data['actions'] = data['actions'][-100:]
        self.db.set(str(guild_id), data)

    def add_warning(self, guild_id, user_id, reason, moderator):
        data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        if 'warnings' not in data:
            data['warnings'] = {}
        uid = str(user_id)
        if uid not in data['warnings']:
            data['warnings'][uid] = []
        data['warnings'][uid].append({
            'reason': reason,
            'moderator': moderator,
            'timestamp': discord.utils.utcnow().isoformat()
        })
        self.db.set(str(guild_id), data)

    def clear_warnings(self, guild_id, user_id):
        data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        if 'warnings' not in data:
            data['warnings'] = {}
        data['warnings'].pop(str(user_id), None)
        self.db.set(str(guild_id), data)

    def get_warnings(self, guild_id, user_id):
        data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        return data.get('warnings', {}).get(str(user_id), [])

    mod = app_commands.Group(name="mod", description="Moderation commands")

    # ==================== EXISTING COMMANDS (kept) ====================

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
            except:
                pass
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
            except:
                pass
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
        self.add_warning(interaction.guild.id, member.id, reason, str(interaction.user))
        try:
            dm = discord.Embed(description=f"you were warned in **{interaction.guild.name}**\nreason: {reason}", color=0x1a1a2e)
            await member.send(embed=dm)
        except:
            pass
        warns = self.get_warnings(interaction.guild.id, member.id)
        embed = discord.Embed(description=f"warned **{member}**\nreason: {reason}\ntotal warnings: **{len(warns)}**", color=0x1a1a2e)
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

    # ==================== NEW COMMANDS (Step 12) ====================

    @mod.command(name="nuke", description="Clone and delete the channel (purge everything)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke(self, interaction: discord.Interaction):
        self.bot.increment_command('mod_nuke')
        # Confirmation view
        view = NukeConfirmView(interaction.user)
        embed = discord.Embed(
            title="💥 Nuke this channel?",
            description="This will clone the channel and delete the original. All messages will be lost.\nClick **Confirm** within 30 seconds to proceed.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
        await view.wait()

        if not view.confirmed:
            try:
                await interaction.followup.send("nuke cancelled.", ephemeral=True)
            except:
                pass
            return

        channel = interaction.channel
        try:
            # Clone
            new_channel = await channel.clone(reason=f"Channel nuked by {interaction.user}")
            await new_channel.edit(position=channel.position)
            await channel.delete(reason=f"Channel nuked by {interaction.user}")
            await new_channel.send("💥 channel nuked")
        except discord.Forbidden:
            try:
                await interaction.followup.send("i don't have permission to do that.", ephemeral=True)
            except:
                pass
        except Exception as e:
            try:
                await interaction.followup.send(f"nuke failed: {e}", ephemeral=True)
            except:
                pass

    @mod.command(name="role", description="Add or remove a role from a user")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def mod_role(
        self,
        interaction: discord.Interaction,
        action: str,
        member: discord.Member,
        role: discord.Role
    ):
        self.bot.increment_command('mod_role')
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("i can't manage that role — it's above my top role.", ephemeral=True)
            return
        action = action.lower()
        if action == 'add':
            try:
                await member.add_roles(role, reason=f"by {interaction.user}")
                await interaction.response.send_message(f"✅ added {role.mention} to {member.mention}")
            except discord.Forbidden:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
        elif action == 'remove':
            try:
                await member.remove_roles(role, reason=f"by {interaction.user}")
                await interaction.response.send_message(f"✅ removed {role.mention} from {member.mention}")
            except discord.Forbidden:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
        else:
            await interaction.response.send_message("action must be `add` or `remove`.", ephemeral=True)

    @mod.command(name="nickname", description="Change a member's nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def mod_nickname(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str = None
    ):
        self.bot.increment_command('mod_nickname')
        if member.top_role >= interaction.user.top_role and member != interaction.user:
            await interaction.response.send_message("can't change nickname of someone with equal or higher role.", ephemeral=True)
            return
        try:
            await member.edit(nick=nickname or None, reason=f"by {interaction.user}")
            if nickname:
                await interaction.response.send_message(f"✅ {member.mention}'s nickname set to **{nickname}**")
            else:
                await interaction.response.send_message(f"✅ {member.mention}'s nickname reset.")
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission to change that nickname.", ephemeral=True)

    @mod.command(name="softban", description="Ban then unban to delete user's messages without keeping them banned")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Softban"):
        self.bot.increment_command('mod_softban')
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("can't softban someone with equal or higher role.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason, delete_message_days=1)
            await interaction.guild.unban(member, reason="Softban auto-unban")
            self.log_action(interaction.guild.id, "softban", str(interaction.user), str(member), reason)
            embed = discord.Embed(description=f"softbanned **{member}** — messages deleted, not banned anymore.\nreason: {reason}", color=0x1a1a2e)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="warn_list", description="Show all warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_list(self, interaction: discord.Interaction, member: discord.Member):
        self.bot.increment_command('mod_warn_list')
        warns = self.get_warnings(interaction.guild.id, member.id)
        if not warns:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"⚠️ Warnings — {member.display_name}",
            color=0xffa500,
            description=f"{len(warns)} warning(s) total"
        )
        for i, w in enumerate(warns[-10:], 1):
            embed.add_field(
                name=f"#{i} — {w.get('reason', 'no reason')}",
                value=f"by {w.get('moderator', 'unknown')} · {w.get('timestamp', 'unknown')[:19]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @mod.command(name="warn_clear", description="Clear all warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_clear(self, interaction: discord.Interaction, member: discord.Member):
        self.bot.increment_command('mod_warn_clear')
        self.clear_warnings(interaction.guild.id, member.id)
        await interaction.response.send_message(f"✅ cleared all warnings for {member.mention}")

    @mod.command(name="slowmode", description="Set channel slowmode (0 disables)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        self.bot.increment_command('mod_slowmode')
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("slowmode must be 0-21600 seconds.", ephemeral=True)
            return
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await interaction.response.send_message("✅ slowmode disabled.")
            else:
                await interaction.response.send_message(f"✅ slowmode set to **{seconds}s**")
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="lock", description="Lock a channel (deny Send Messages for @everyone)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason"):
        self.bot.increment_command('mod_lock')
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Lock by {interaction.user}: {reason}")
            await interaction.response.send_message(f"🔒 channel locked. reason: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)

    @mod.command(name="unlock", description="Unlock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        self.bot.increment_command('mod_unlock')
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = None  # reset to neutral
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Unlock by {interaction.user}")
            await interaction.response.send_message("🔓 channel unlocked.")
        except discord.Forbidden:
            await interaction.response.send_message("i don't have permission.", ephemeral=True)


class NukeConfirmView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=30)
        self.author = author
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("not your nuke.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="nuking...", view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="cancelled.", view=self)
        self.stop()


async def setup(bot):
    await bot.add_cog(Moderation(bot))
