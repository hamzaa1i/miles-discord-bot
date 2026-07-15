"""
cogs/moderation.py — essential moderation commands.

Trimmed to stay under Discord's 100 global slash command limit.
Kept: /mod kick, /mod ban, /mod unban, /mod timeout, /mod untimeout,
      /mod warn, /mod warn_clear, /mod unmute, /mod purge, /mod nuke,
      /mod slowmode, /mod lock, /mod unlock (13 subcommands).
Removed: /mod warn list/case, /mod role add/remove, /mod nickname,
         /mod softban, /mod hide, /mod show, /mod massrole add/remove,
         /mod logs (11 subcommands removed).
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import asyncio
import os
import json
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
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role:
            await interaction.followup.send("can't kick someone with equal or higher role.", ephemeral=True)
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
            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission to kick this member.", ephemeral=True)

    @mod.command(name="ban", description="Ban a member")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role:
            await interaction.followup.send("can't ban someone with equal or higher role.", ephemeral=True)
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
            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    @mod.command(name="unban", description="Unban a user")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            self.log_action(interaction.guild.id, "unban", str(interaction.user), str(user), "Unbanned")
            embed = discord.Embed(description=f"unbanned **{user}**", color=0x57f287)
            await interaction.followup.send(embed=embed)
        except discord.NotFound:
            await interaction.followup.send("user not found or not banned.", ephemeral=True)

    @mod.command(name="timeout", description="Timeout a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
        await interaction.response.defer(ephemeral=True)
        time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = duration[-1].lower()
            amount = int(duration[:-1])
            seconds = amount * time_units[unit]
            if seconds > 2419200:
                await interaction.followup.send("max timeout is 28 days.", ephemeral=True)
                return
        except Exception:
            await interaction.followup.send("invalid format. use like: 10m, 1h, 2d", ephemeral=True)
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
        await interaction.response.defer(ephemeral=True)
        self.log_action(interaction.guild.id, "warn", str(interaction.user), str(member), reason)
        self.add_warning(interaction.guild.id, member.id, reason, str(interaction.user))
        try:
            dm = discord.Embed(description=f"you were warned in **{interaction.guild.name}**\nreason: {reason}", color=0xe67e22)
            await member.send(embed=dm)
        except Exception:
            pass
        embed = discord.Embed(description=f"warned **{member}**\nreason: {reason}", color=0xe67e22)
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
        await interaction.response.defer(ephemeral=True)
        if seconds < 0 or seconds > 21600:
            await interaction.followup.send("slowmode must be 0-21600 seconds.", ephemeral=True)
            return
        try:
            await interaction.channel.edit(slowmode_delay=seconds)
            msg = "slowmode disabled." if seconds == 0 else f"slowmode set to {seconds}s."
            await interaction.followup.send(msg)
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    @mod.command(name="lock", description="Lock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason"):
        await interaction.response.defer(ephemeral=True)
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Lock by {interaction.user}: {reason}")
            await interaction.followup.send(f"🔒 channel locked. reason: {reason}")
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    @mod.command(name="unlock", description="Unlock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = None
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Unlock by {interaction.user}")
            await interaction.followup.send("🔓 channel unlocked.")
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission.", ephemeral=True)

    # NEW COMMAND 1 — /mod warn_clear
    @mod.command(name="warn_clear",
                 description="Clear all warnings for a user")
    @app_commands.describe(user="The user to clear warnings for")
    async def mod_warn_clear(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        # Permission check
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if (interaction.user.id != owner_id and
                not interaction.user.guild_permissions.administrator):
            await interaction.followup.send("no permission.")
            return

        try:
            with open("data/warnings.json", "r") as f:
                warn_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            warn_data = {}

        guild_key = str(interaction.guild_id)
        user_key = str(user.id)

        if guild_key not in warn_data or user_key not in warn_data[guild_key]:
            await interaction.followup.send(f"no warnings found for {user.display_name}.")
            return

        count = len(warn_data[guild_key][user_key])
        warn_data[guild_key][user_key] = []

        with open("data/warnings.json", "w") as f:
            json.dump(warn_data, f, indent=2)

        await interaction.followup.send(
            f"cleared {count} warning(s) for {user.display_name}."
        )

    # NEW COMMAND 2 — /mod unmute
    @mod.command(name="unmute",
                 description="Remove timeout from a user (unmute)")
    @app_commands.describe(user="The user to unmute")
    async def mod_unmute(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.moderate_members:
            await interaction.followup.send("you need moderate members permission.")
            return

        try:
            await user.timeout(None)  # None removes the timeout
            await interaction.followup.send(f"removed timeout from {user.display_name}.")
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission to do that.")
        except Exception as e:
            await interaction.followup.send(f"failed: {e}")




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
