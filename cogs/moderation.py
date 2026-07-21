"""cogs/moderation.py — essential moderation commands.

Kept: /mod kick, ban, unban, timeout, warn, warn_clear, unmute, purge, nuke,
      slowmode, lock, unlock, antispam (13 subcommands).
Added: /mod antilink, /mod tempban, /mod config (3 subcommands).
Also: improved mod log embeds, antilink listener, tempban background task,
      warning thresholds w/ auto-action, AI mod logging, 60s settings cache.
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import timedelta
import os
import re
import time
import logging
from utils.database import Database
from utils.db import (get_guild_setting, set_guild_setting, get_warnings,
                      add_tempban, get_tempbans_due, remove_tempban)

logger = logging.getLogger(__name__)

# Matches http(s):// links that are NOT pointing at Discord's own domains.
ANTILINK_PATTERN = re.compile(
    r'https?://(?!(?:discord\.gg|discord\.com|discordapp\.com))[^\s]+',
    re.IGNORECASE,
)

THRESHOLD_ACTION_LABELS = {
    "timeout_1h": "Timeout 1h", "timeout_24h": "Timeout 24h",
    "kick": "Kick", "ban": "Ban",
}


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/moderation.json')
        # 60s TTL cache for mod_settings reads: {guild_id: (settings, ts)}
        self._settings_cache: dict[int, tuple[dict, float]] = {}
        if not self.tempban_loop.is_running():
            self.tempban_loop.start()

    def cog_unload(self):
        if self.tempban_loop.is_running():
            self.tempban_loop.cancel()

    def _get_settings(self, guild_id):
        """Get mod_settings with 60s cache."""
        import time
        now = time.time()
        if guild_id in self._settings_cache:
            cached, ts = self._settings_cache[guild_id]
            if now - ts < 60:
                return cached
        settings = get_guild_setting(guild_id, "mod_settings")
        self._settings_cache[guild_id] = (settings, now)
        return settings

    def _invalidate_settings(self, guild_id):
        """Drop cached mod_settings after a write so the next read is fresh."""
        self._settings_cache.pop(guild_id, None)

    def _get_log_channel(self, guild):
        """Resolve the configured mod log channel for a guild, or None."""
        try:
            settings = self._get_settings(guild.id)
        except Exception:
            return None
        log_channel_id = settings.get("log_channel_id") if isinstance(settings, dict) else None
        if not log_channel_id:
            return None
        try:
            return guild.get_channel(int(log_channel_id))
        except (ValueError, TypeError):
            return None

    async def _send_mod_log(self, guild, action_label, target, moderator,
                            reason, color=0xe67e22):
        """Send an enriched embed (thumbnail + Account Age + Previous Offenses)
        to the configured mod log channel. No-ops if no log channel is set."""
        channel = self._get_log_channel(guild)
        if channel is None:
            return
        embed = discord.Embed(title=f"🛡️ {action_label}", color=color,
                              timestamp=discord.utils.utcnow())
        try:
            embed.set_thumbnail(url=target.display_avatar.url)
        except Exception:
            pass
        embed.add_field(name="User", value=f"{target.mention}\n`{target.id}`", inline=True)
        embed.add_field(name="Moderator", value=str(moderator), inline=True)
        embed.add_field(name="Reason", value=(reason or "No reason")[:1024] or "No reason", inline=False)
        try:
            account_age = (discord.utils.utcnow() - target.created_at).days
        except Exception:
            account_age = 0
        try:
            prev = len(get_warnings(guild.id, target.id))
        except Exception:
            prev = 0
        embed.add_field(name="Account Age", value=f"{account_age} days", inline=True)
        embed.add_field(name="Previous Offenses", value=str(prev), inline=True)
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"[moderation] failed to send mod log: {e}")

    async def log_ai_action(self, guild, action, target_name, target_id,
                            requester_name, original_message):
        """Send an AI mod action embed to the configured mod log channel."""
        channel = self._get_log_channel(guild)
        if channel is None:
            return
        embed = discord.Embed(title=f"🤖 AI Mod Action — {action}", color=0x9b59b6,
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Target", value=f"{target_name}\n`{target_id}`", inline=True)
        embed.add_field(name="Requested By", value=str(requester_name), inline=True)
        snippet = (original_message or "")[:1024]
        embed.add_field(name="Original Message", value=snippet or "—", inline=False)
        embed.set_footer(text="Auto-actioned by AI moderation")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"[moderation] failed to send AI mod log: {e}")

    async def _maybe_apply_threshold(self, interaction, member, reason):
        """After a warn, auto-apply the configured action if the warning count
        reached the configured threshold."""
        try:
            settings = self._get_settings(interaction.guild.id)
        except Exception:
            return
        if not isinstance(settings, dict):
            return
        threshold = settings.get("warn_threshold_count")
        action = settings.get("warn_threshold_action")
        if not threshold or not action or action not in THRESHOLD_ACTION_LABELS:
            return
        try:
            threshold = int(threshold)
        except (ValueError, TypeError):
            return
        try:
            count = len(get_warnings(interaction.guild.id, member.id))
        except Exception:
            return
        if count < threshold:
            return
        auto_reason = f"Auto-action: reached {count} warnings"
        msg = None
        try:
            if action == "timeout_1h":
                await member.timeout(timedelta(hours=1), reason=auto_reason)
                msg = f"⏱️ auto-timed out **{member}** for 1h (reached {count} warnings)."
            elif action == "timeout_24h":
                await member.timeout(timedelta(hours=24), reason=auto_reason)
                msg = f"⏱️ auto-timed out **{member}** for 24h (reached {count} warnings)."
            elif action == "kick":
                await member.kick(reason=auto_reason)
                msg = f"👢 auto-kicked **{member}** (reached {count} warnings)."
            elif action == "ban":
                await member.ban(reason=auto_reason, delete_message_days=0)
                msg = f"🔨 auto-banned **{member}** (reached {count} warnings)."
        except discord.Forbidden:
            msg = f"⚠️ threshold reached ({count} warnings) but I lack permissions to {THRESHOLD_ACTION_LABELS[action]}."
        except Exception as e:
            logger.warning(f"[moderation] threshold auto-action failed: {e}")
            return
        if msg:
            try:
                await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass

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
            await self._send_mod_log(interaction.guild, "Kick", member, interaction.user, reason, color=0xe67e22)
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
            await self._send_mod_log(interaction.guild, "Ban", member, interaction.user, reason, color=0xed4245)
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
            await self._send_mod_log(interaction.guild, "Unban", user, interaction.user, "Manual unban", color=0x57f287)
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

    # PHASE 2B — Consolidated /mod warnings command
    @mod.command(name="warnings", description="Add, list, or clear warnings for a user")
    @app_commands.describe(
        action="What to do",
        user="The target user",
        reason="Reason for the warning (only for add action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add Warning", value="add"),
        app_commands.Choice(name="List Warnings", value="list"),
        app_commands.Choice(name="Clear Warnings", value="clear"),
    ])
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mod_warnings(self, interaction: discord.Interaction,
                           action: app_commands.Choice[str],
                           user: discord.Member,
                           reason: str = "No reason"):
        self.bot.increment_command('mod_warnings')
        await interaction.response.defer(ephemeral=True)

        if action.value == "add":
            self.log_action(interaction.guild.id, "warn", str(interaction.user), str(user), reason)
            self.add_warning(interaction.guild.id, user.id, reason, str(interaction.user))
            try:
                dm = discord.Embed(description=f"you were warned in **{interaction.guild.name}**\nreason: {reason}", color=0xe67e22)
                await user.send(embed=dm)
            except Exception:
                pass
            embed = discord.Embed(description=f"warned **{user}**\nreason: {reason}", color=0xe67e22)
            await interaction.followup.send(embed=embed)
            await self._send_mod_log(interaction.guild, "Warn", user, interaction.user, reason, color=0xe67e22)
            await self._maybe_apply_threshold(interaction, user, reason)

        elif action.value == "list":
            from utils.db import get_warnings
            warnings = get_warnings(interaction.guild.id, user.id)
            if not warnings:
                await interaction.followup.send(f"no warnings for {user.display_name}.", ephemeral=True)
                return
            embed = discord.Embed(
                title=f"⚠️ Warnings for {user.display_name}",
                color=0xe67e22,
                timestamp=discord.utils.utcnow()
            )
            for i, w in enumerate(warnings[:15], 1):
                w_reason = w.get('reason', 'N/A') if isinstance(w, dict) else str(w)
                w_mod = w.get('moderator', 'Unknown') if isinstance(w, dict) else 'Unknown'
                embed.add_field(
                    name=f"#{i}",
                    value=f"reason: {w_reason}\nby: {w_mod}",
                    inline=False
                )
            embed.set_footer(text=f"Total: {len(warnings)} warning(s)")
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action.value == "clear":
            from utils.db import get_warnings, clear_warnings
            existing = get_warnings(interaction.guild_id, user.id)
            if not existing:
                await interaction.followup.send(f"no warnings found for {user.display_name}.", ephemeral=True)
                return
            count = len(existing)
            clear_warnings(interaction.guild_id, user.id)
            await interaction.followup.send(f"cleared {count} warning(s) for {user.display_name}.", ephemeral=True)

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

    @mod.command(name="unmute", description="Remove timeout from a user (unmute)")
    @app_commands.describe(user="The user to unmute")
    async def mod_unmute(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.followup.send("you need moderate members permission.")
            return
        try:
            await user.timeout(None)
            await interaction.followup.send(f"removed timeout from {user.display_name}.")
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission to do that.")
        except Exception as e:
            await interaction.followup.send(f"failed: {e}")

    @mod.command(name="antispam", description="Toggle antispam automod on or off")
    @app_commands.describe(enabled="on or off")
    @app_commands.choices(enabled=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ])
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mod_antispam(self, interaction: discord.Interaction, enabled: app_commands.Choice[str]):
        self.bot.increment_command('mod_antispam')
        await interaction.response.defer(ephemeral=True)
        try:
            settings = get_guild_setting(interaction.guild_id, "mod_settings")
            settings["antispam_enabled"] = (enabled.value == "on")
            set_guild_setting(interaction.guild_id, "mod_settings", settings)
            self._invalidate_settings(interaction.guild_id)
            status = "enabled" if enabled.value == "on" else "disabled"
            await interaction.followup.send(f"✅ antispam is now **{status}** for this server.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @mod.command(name="antilink", description="Toggle antilink (block non-Discord links) for a channel")
    @app_commands.describe(enabled="on or off", channel="Optional channel to toggle (defaults to current channel)")
    @app_commands.choices(enabled=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ])
    @app_commands.checks.has_permissions(manage_messages=True)
    async def mod_antilink(self, interaction: discord.Interaction, enabled: app_commands.Choice[str],
                           channel: discord.TextChannel | None = None):
        self.bot.increment_command('mod_antilink')
        await interaction.response.defer(ephemeral=True)
        target_channel = channel or interaction.channel
        try:
            settings = get_guild_setting(interaction.guild_id, "mod_settings")
            if not isinstance(settings, dict):
                settings = {}
            antilink_channels = [str(c) for c in (settings.get("antilink_channels") or [])]
            cid = str(target_channel.id)
            if enabled.value == "on":
                if cid not in antilink_channels:
                    antilink_channels.append(cid)
                msg = f"✅ antilink **enabled** in {target_channel.mention}. Non-Discord links will be deleted."
            else:
                if cid in antilink_channels:
                    antilink_channels.remove(cid)
                msg = f"✅ antilink **disabled** in {target_channel.mention}. Links are allowed again."
            settings["antilink_channels"] = antilink_channels
            set_guild_setting(interaction.guild_id, "mod_settings", settings)
            self._invalidate_settings(interaction.guild_id)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @mod.command(name="tempban", description="Temporarily ban a member (auto-unbans after duration)")
    @app_commands.describe(member="The member to tempban", duration="How long the ban lasts", reason="Reason for the tempban")
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 hour", value="1h"), app_commands.Choice(name="6 hours", value="6h"),
        app_commands.Choice(name="12 hours", value="12h"), app_commands.Choice(name="1 day", value="1d"),
        app_commands.Choice(name="3 days", value="3d"), app_commands.Choice(name="7 days", value="7d"),
    ])
    @app_commands.checks.has_permissions(ban_members=True)
    async def mod_tempban(self, interaction: discord.Interaction, member: discord.Member,
                          duration: app_commands.Choice[str], reason: str = "No reason"):
        self.bot.increment_command('mod_tempban')
        await interaction.response.defer(ephemeral=True)
        if member.top_role >= interaction.user.top_role:
            await interaction.followup.send("can't tempban someone with equal or higher role.", ephemeral=True)
            return
        time_units = {'h': 3600, 'd': 86400}
        unit = duration.value[-1].lower()
        try:
            amount = int(duration.value[:-1])
            seconds = amount * time_units[unit]
        except (ValueError, KeyError):
            await interaction.followup.send("invalid duration.", ephemeral=True)
            return
        unban_time = time.time() + seconds
        try:
            dm = discord.Embed(description=f"you were temporarily banned from **{interaction.guild.name}** for **{duration.value}**\nreason: {reason}", color=0xed4245)
            await member.send(embed=dm)
        except Exception:
            pass
        try:
            await member.ban(reason=f"Tempban ({duration.value}): {reason}", delete_message_days=0)
        except discord.Forbidden:
            await interaction.followup.send("i don't have permission to ban this member.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"failed to ban: `{e}`", ephemeral=True)
            return
        try:
            add_tempban(interaction.guild.id, member.id, unban_time,
                        reason=f"{reason} (tempban {duration.value} by {interaction.user})")
        except Exception as e:
            logger.warning(f"[moderation] add_tempban failed: {e}")
        self.log_action(interaction.guild.id, "tempban", str(interaction.user), str(member), f"{reason} ({duration.value})")
        embed = discord.Embed(description=f"⏳ tempbanned **{member}** for **{duration.value}**\nreason: {reason}", color=0xed4245)
        embed.set_footer(text=f"by {interaction.user}")
        await interaction.followup.send(embed=embed)
        await self._send_mod_log(interaction.guild, f"Tempban ({duration.value})", member, interaction.user, reason, color=0xed4245)

    @mod.command(name="config", description="Configure moderation settings (warn thresholds)")
    @app_commands.describe(setting="Which setting to configure", value="New value (number for count; timeout_1h/timeout_24h/kick/ban for action)")
    @app_commands.choices(setting=[
        app_commands.Choice(name="Warn Threshold Count", value="warn_threshold_count"),
        app_commands.Choice(name="Warn Threshold Action", value="warn_threshold_action"),
    ])
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mod_config(self, interaction: discord.Interaction, setting: app_commands.Choice[str], value: str):
        self.bot.increment_command('mod_config')
        await interaction.response.defer(ephemeral=True)
        try:
            settings = get_guild_setting(interaction.guild_id, "mod_settings")
            if not isinstance(settings, dict):
                settings = {}
        except Exception as e:
            await interaction.followup.send(f"failed to read settings: `{e}`", ephemeral=True)
            return
        if setting.value == "warn_threshold_count":
            try:
                count = int(value)
            except ValueError:
                await interaction.followup.send("value must be a whole number (e.g. `3`).", ephemeral=True)
                return
            if count < 1 or count > 100:
                await interaction.followup.send("warn threshold count must be between 1 and 100.", ephemeral=True)
                return
            settings["warn_threshold_count"] = count
            msg = f"✅ warn threshold count set to **{count}**.\ncurrent action: `{settings.get('warn_threshold_action', 'not set')}`"
        elif setting.value == "warn_threshold_action":
            valid = {"timeout_1h", "timeout_24h", "kick", "ban"}
            v = value.strip().lower()
            if v not in valid:
                await interaction.followup.send("value must be one of: `timeout_1h`, `timeout_24h`, `kick`, `ban`.", ephemeral=True)
                return
            settings["warn_threshold_action"] = v
            msg = (f"✅ warn threshold action set to **{THRESHOLD_ACTION_LABELS[v]}** (`{v}`).\n"
                   f"current count: `{settings.get('warn_threshold_count', 'not set')}`")
        else:
            await interaction.followup.send("unknown setting.", ephemeral=True)
            return
        try:
            set_guild_setting(interaction.guild_id, "mod_settings", settings)
            self._invalidate_settings(interaction.guild_id)
        except Exception as e:
            await interaction.followup.send(f"failed to save: `{e}`", ephemeral=True)
            return
        await interaction.followup.send(msg, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Delete non-Discord links in channels flagged via /mod antilink."""
        if not message.guild or message.author.bot:
            return
        try:
            settings = self._get_settings(message.guild.id)
        except Exception:
            return
        antilink_channels = (settings or {}).get("antilink_channels") if isinstance(settings, dict) else None
        if not antilink_channels:
            return
        if str(message.channel.id) not in {str(c) for c in antilink_channels}:
            return
        # Exempt staff with Manage Messages and the bot owner.
        try:
            if message.author.guild_permissions.manage_messages:
                return
        except Exception:
            pass
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if owner_id and message.author.id == owner_id:
            return
        content = message.content or ""
        if not ANTILINK_PATTERN.search(content):
            return
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass
        except Exception as e:
            logger.debug(f"[moderation] antilink delete failed: {e}")
        try:
            await message.channel.send(
                f"🚫 {message.author.mention}, non-Discord links are not allowed here.",
                delete_after=5)
        except Exception:
            pass

    @tasks.loop(minutes=5)
    async def tempban_loop(self):
        """Lift tempbans whose unban_time has passed."""
        try:
            for entry in get_tempbans_due(time.time()):
                try:
                    guild_id = int(entry.get("guild_id"))
                    user_id = int(entry.get("user_id"))
                except (ValueError, TypeError):
                    continue
                guild = self.bot.get_guild(guild_id)
                if guild is not None:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await guild.unban(user, reason="Tempban expired")
                        try:
                            await self._send_mod_log(guild, "Tempban Expired (Auto-Unban)", user,
                                                     self.bot.user, "Automatic unban — duration elapsed.", color=0x57f287)
                        except Exception:
                            pass
                    except discord.NotFound:
                        pass
                    except discord.Forbidden:
                        logger.warning(f"[moderation] lacking unban permission in {guild_id}")
                    except Exception as e:
                        logger.warning(f"[moderation] tempban unban failed: {e}")
                # Always remove the entry so we don't retry forever on NotFound/Forbidden/gone guild.
                try:
                    remove_tempban(guild_id, user_id)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[moderation] tempban_loop error: {e}")

    @tempban_loop.before_loop
    async def before_tempban_loop(self):
        await self.bot.wait_until_ready()


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
