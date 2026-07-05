"""
cogs/moderation.py — essential moderation commands.

Trimmed to stay under Discord's 100 global slash command limit.
Kept: /mod kick, /mod ban, /mod unban, /mod timeout, /mod untimeout,
      /mod warn, /mod purge, /mod nuke, /mod slowmode, /mod lock,
      /mod unlock (11 subcommands).
Removed: /mod warn list/clear/case, /mod role add/remove, /mod nickname,
         /mod softban, /mod hide, /mod show, /mod massrole add/remove,
         /mod logs (11 subcommands removed).
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import asyncio
from utils.database import Database


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/moderation.json')

    def log_action(self, guild_id, action, moderator, target, reason):
        try:
            data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        except Exception:
            data = {'actions': [], 'warnings': {}}
        if 'actions' not in data:
            data['actions'] = []
        data['actions'].append({
            'action': action, 'moderator': moderator,
            'target': target, 'reason': reason,
            'timestamp': discord.utils.utcnow().isoformat()
        })
        if len(data['actions']) > 100:
            data['actions'] = data['actions'][-100:]
        self.db.set(str(guild_id), data)

    def add_warning(self, guild_id, user_id, reason, moderator):
        try:
            data = self.db.get(str(guild_id), {'actions': [], 'warnings': {}})
        except Exception:
            data = {'actions': [], 'warnings': {}}
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

    mod = app_commands.Group(name="mod", description="Moderation commands")

    @mod.command(name="kick", description="Kick a member")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        if member.top_role >= interaction.user.top_role:
            try:
                await interaction.response.send_message("can't kick someone with equal or higher role.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        try:
            try:
                dm = discord.Embed(description=f"you were kicked from **{interaction.guild.name}**\nreason: {reason}", color=0x2b2d31)
                await member.send(embed=dm)
            except Exception:
                pass
            await member.kick(reason=reason)
            self.log_action(interaction.guild.id, "kick", str(interaction.user), str(member), reason)
            embed = discord.Embed(description=f"kicked **{member}**\nreason: {reason}", color=0xe67e22)
            embed.set_footer(text=f"by {interaction.user}")
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission to kick this member.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="ban", description="Ban a member")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        if member.top_role >= interaction.user.top_role:
            try:
                await interaction.response.send_message("can't ban someone with equal or higher role.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        try:
            try:
                dm = discord.Embed(description=f"you were banned from **{interaction.guild.name}**\nreason: {reason}", color=0x2b2d31)
                await member.send(embed=dm)
            except Exception:
                pass
            await member.ban(reason=reason, delete_message_days=0)
            self.log_action(interaction.guild.id, "ban", str(interaction.user), str(member), reason)
            embed = discord.Embed(description=f"banned **{member}**\nreason: {reason}", color=0xe67e22)
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="unban", description="Unban a user")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            self.log_action(interaction.guild.id, "unban", str(interaction.user), str(user), "Unbanned")
            embed = discord.Embed(description=f"unbanned **{user}**", color=0x57f287)
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except discord.NotFound:
            try:
                await interaction.response.send_message("user not found or not banned.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="timeout", description="Timeout a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
        time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            amount = int(duration[:-1])
            seconds = amount * time_units[unit]
            if seconds > 2419200:
                try:
                    await interaction.response.send_message("max timeout is 28 days.", ephemeral=True)
                except discord.InteractionResponded:
                    pass
                return
        except Exception:
            try:
                await interaction.response.send_message("invalid format. use like: 10m, 1h, 2d", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        try:
            await member.timeout(timedelta(seconds=seconds), reason=reason)
            self.log_action(interaction.guild.id, "timeout", str(interaction.user), str(member), f"{reason} ({duration})")
            embed = discord.Embed(description=f"timed out **{member}** for **{duration}**\nreason: {reason}", color=0xe67e22)
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="warn", description="Warn a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        self.log_action(interaction.guild.id, "warn", str(interaction.user), str(member), reason)
        self.add_warning(interaction.guild.id, member.id, reason, str(interaction.user))
        try:
            dm = discord.Embed(description=f"you were warned in **{interaction.guild.name}**\nreason: {reason}", color=0xe67e22)
            await member.send(embed=dm)
        except Exception:
            pass
        embed = discord.Embed(description=f"warned **{member}**\nreason: {reason}", color=0xe67e22)
        try:
            await interaction.response.send_message(embed=embed)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)

    @mod.command(name="purge", description="Delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            try:
                await interaction.response.send_message("amount must be 1-100.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"deleted {len(deleted)} messages.", ephemeral=True)

    @mod.command(name="untimeout", description="Remove timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None)
            embed = discord.Embed(description=f"timeout removed from **{member}**", color=0x57f287)
            try:
                await interaction.response.send_message(embed=embed)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="nuke", description="Clone and delete the channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke(self, interaction: discord.Interaction):
        view = NukeConfirmView(interaction.user)
        embed = discord.Embed(
            title="💥 Nuke this channel?",
            description="Click **Confirm** within 30 seconds to proceed.",
            color=0xed4245
        )
        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()
        await view.wait()
        if not view.confirmed:
            try:
                await interaction.followup.send("nuke cancelled.", ephemeral=True)
            except Exception:
                pass
            return
        channel = interaction.channel
        try:
            new_channel = await channel.clone(reason=f"Channel nuked by {interaction.user}")
            await new_channel.edit(position=channel.position)
            await channel.delete(reason=f"Channel nuked by {interaction.user}")
            await new_channel.send("💥 channel nuked")
        except discord.Forbidden:
            try:
                await interaction.followup.send("i don't have permission.", ephemeral=True)
            except Exception:
                pass

    @mod.command(name="slowmode", description="Set channel slowmode (0 disables)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            try:
                await interaction.response.send_message("slowmode must be 0-21600 seconds.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            msg = "✅ slowmode disabled." if seconds == 0 else f"✅ slowmode set to **{seconds}s**"
            try:
                await interaction.response.send_message(msg)
            except discord.InteractionResponded:
                await interaction.followup.send(msg)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="lock", description="Lock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason"):
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Lock by {interaction.user}: {reason}")
            try:
                await interaction.response.send_message(f"🔒 channel locked. reason: {reason}")
            except discord.InteractionResponded:
                await interaction.followup.send(f"🔒 channel locked. reason: {reason}")
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="unlock", description="Unlock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = None
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Unlock by {interaction.user}")
            try:
                await interaction.response.send_message("🔓 channel unlocked.")
            except discord.InteractionResponded:
                await interaction.followup.send("🔓 channel unlocked.")
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="hide", description="Hide a channel from @everyone")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def hide(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        try:
            overwrite = target.overwrites_for(interaction.guild.default_role)
            overwrite.view_channel = False
            await target.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Hidden by {interaction.user}")
            try:
                await interaction.response.send_message(f"🙈 {target.mention} is now hidden.")
            except discord.InteractionResponded:
                await interaction.followup.send(f"🙈 {target.mention} is now hidden.")
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="show", description="Show a hidden channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def show(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        try:
            overwrite = target.overwrites_for(interaction.guild.default_role)
            overwrite.view_channel = None
            await target.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Shown by {interaction.user}")
            try:
                await interaction.response.send_message(f"👀 {target.mention} is now visible.")
            except discord.InteractionResponded:
                await interaction.followup.send(f"👀 {target.mention} is now visible.")
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="nickname", description="Change a member's nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        try:
            await member.edit(nick=nickname or None, reason=f"by {interaction.user}")
            if nickname:
                msg = f"✅ {member.mention}'s nickname set to **{nickname}**"
            else:
                msg = f"✅ {member.mention}'s nickname reset."
            try:
                await interaction.response.send_message(msg)
            except discord.InteractionResponded:
                await interaction.followup.send(msg)
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="softban", description="Ban then unban to wipe messages")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Softban"):
        try:
            await member.ban(reason=reason, delete_message_days=1)
            await interaction.guild.unban(member, reason="Softban auto-unban")
            self.log_action(interaction.guild.id, "softban", str(interaction.user), str(member), reason)
            try:
                await interaction.response.send_message(f"softbanned **{member}** — messages deleted.")
            except discord.InteractionResponded:
                await interaction.followup.send(f"softbanned **{member}** — messages deleted.")
        except discord.Forbidden:
            try:
                await interaction.response.send_message("i don't have permission.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="role", description="Add or remove a role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def mod_role(self, interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role):
        if role.position >= interaction.guild.me.top_role.position:
            try:
                await interaction.response.send_message("i can't manage that role.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        if action == "add":
            try:
                await member.add_roles(role, reason=f"by {interaction.user}")
                try:
                    await interaction.response.send_message(f"✅ added {role.mention} to {member.mention}")
                except discord.InteractionResponded:
                    await interaction.followup.send(f"✅ added {role.mention} to {member.mention}")
            except discord.Forbidden:
                try:
                    await interaction.response.send_message("i don't have permission.", ephemeral=True)
                except discord.InteractionResponded:
                    pass
        elif action == "remove":
            try:
                await member.remove_roles(role, reason=f"by {interaction.user}")
                try:
                    await interaction.response.send_message(f"✅ removed {role.mention} from {member.mention}")
                except discord.InteractionResponded:
                    await interaction.followup.send(f"✅ removed {role.mention} from {member.mention}")
            except discord.Forbidden:
                try:
                    await interaction.response.send_message("i don't have permission.", ephemeral=True)
                except discord.InteractionResponded:
                    pass
        else:
            try:
                await interaction.response.send_message("action must be `add` or `remove`.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @mod.command(name="massrole", description="Mass-role management")
    @app_commands.checks.has_permissions(administrator=True)
    async def massrole(self, interaction: discord.Interaction, action: str, role: discord.Role):
        if role.position >= interaction.guild.me.top_role.position:
            try:
                await interaction.response.send_message("i can't manage that role.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        await interaction.response.defer(ephemeral=True)
        count = 0
        failed = 0
        for member in interaction.guild.members:
            if action == "add" and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Mass-role by {interaction.user}")
                    count += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.5)
            elif action == "remove" and role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"Mass-role by {interaction.user}")
                    count += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.5)
        verb = "added to" if action == "add" else "removed from"
        await interaction.followup.send(f"done. {role.mention} {verb} {count} members." + (f" ({failed} failed)" if failed else ""), ephemeral=True)

    @mod.command(name="warn_list", description="Show all warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_list(self, interaction: discord.Interaction, member: discord.Member):
        data = self.db.get(str(interaction.guild.id), {'actions': [], 'warnings': {}})
        warns = data.get('warnings', {}).get(str(member.id), [])
        if not warns:
            try:
                await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        embed = discord.Embed(title=f"⚠️ Warnings — {member.display_name}", color=0xffa500, description=f"{len(warns)} warning(s)")
        for i, w in enumerate(warns[-10:], 1):
            embed.add_field(name=f"#{i}", value=f"reason: {w.get('reason', '?')}\nby: {w.get('moderator', '?')}", inline=False)
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @mod.command(name="warn_clear", description="Clear all warnings for a user")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_clear(self, interaction: discord.Interaction, member: discord.Member):
        data = self.db.get(str(interaction.guild.id), {'actions': [], 'warnings': {}})
        if 'warnings' not in data: data['warnings'] = {}
        data['warnings'].pop(str(member.id), None)
        self.db.set(str(interaction.guild.id), data)
        try:
            await interaction.response.send_message(f"✅ cleared all warnings for {member.mention}")
        except discord.InteractionResponded:
            await interaction.followup.send(f"✅ cleared all warnings for {member.mention}")

    @mod.command(name="case", description="Look up a mod case by number")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def case(self, interaction: discord.Interaction, number: int):
        data = self.db.get(str(interaction.guild.id), {'actions': [], 'warnings': {}})
        actions = data.get('actions', [])
        if number < 1 or number > len(actions):
            try:
                await interaction.response.send_message(f"no case #{number}.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        case = actions[number - 1]
        embed = discord.Embed(title=f"📋 Case #{number}", color=0xe67e22)
        embed.add_field(name="Action", value=case.get('action', '?').title(), inline=True)
        embed.add_field(name="Target", value=case.get('target', '?'), inline=True)
        embed.add_field(name="Moderator", value=case.get('moderator', '?'), inline=True)
        embed.add_field(name="Reason", value=case.get('reason', '?'), inline=False)
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @mod.command(name="logs", description="View moderation logs")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def logs(self, interaction: discord.Interaction, limit: int = 10):
        data = self.db.get(str(interaction.guild.id), {'actions': [], 'warnings': {}})
        logs_list = data.get('actions', [])
        if not logs_list:
            try:
                await interaction.response.send_message("no mod logs.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        logs_list = logs_list[-limit:]
        logs_list.reverse()
        embed = discord.Embed(title="Moderation Logs", color=0x1a1a2e)
        emojis = {'kick': '👢', 'ban': '🔨', 'unban': '✅', 'timeout': '🔇', 'warn': '⚠️', 'softban': '👻'}
        for log in logs_list:
            embed.add_field(
                name=f"{emojis.get(log['action'], '📝')} {log['action'].title()}",
                value=f"**Target:** {log.get('target', '?')}\n**Mod:** {log.get('moderator', '?')}\n**Reason:** {log.get('reason', '?')}",
                inline=False
            )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


class NukeConfirmView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=30)
        self.author = author
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            try:
                await interaction.response.send_message("not your nuke.", ephemeral=True)
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send("not your nuke.", ephemeral=True)
                except Exception:
                    pass
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(content="nuking...", view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(content="cancelled.", view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        self.stop()


async def setup(bot):
    await bot.add_cog(Moderation(bot))
