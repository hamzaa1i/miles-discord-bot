"""
cogs/automod.py — lightweight automod / antispam system.

PHASE 2C — Simple, useful automod focused on spam detection and raid alerts.

Features:
  - Spam detection: if a non-mod user sends too many messages too quickly,
    they get a timeout. First offense = short timeout, repeat = longer.
  - Raid detection: if many members join in a short time, alert the log channel.
  - Ignores: bots, bot owner, members with mod/admin permissions.
  - Logs actions to the configured log channel (via logging_system cog).
  - /mod antispam [on|off] toggles antispam per guild (stored in mod_settings).

Uses utils/db for settings (same system as moderation cog).
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Spam tracking: {guild_id: {user_id: [timestamp, ...]}}
        self.message_tracker = defaultdict(lambda: defaultdict(list))
        # Offense tracking: {guild_id: {user_id: offense_count}}
        self.offense_counts = defaultdict(lambda: defaultdict(int))
        # Raid tracking: {guild_id: [join_timestamp, ...]}
        self.join_tracker = defaultdict(list)
        # FIX 6 — In-memory settings cache with 60s TTL to avoid hitting
        # Supabase on every single message in every guild.
        # {guild_id: (settings_dict, timestamp)}
        self._settings_cache: dict[int, tuple[dict, float]] = {}
        # Start raid check loop
        if not self.raid_check.is_running():
            self.raid_check.start()

    def cog_unload(self):
        if self.raid_check.is_running():
            self.raid_check.cancel()

    # ─── Settings helpers ──────────────────────────────────────────

    def _get_cached_settings(self, guild_id: int) -> dict:
        """Get mod_settings with a 60-second in-memory cache.
        This reduces Supabase queries from every message to once per minute per guild."""
        now = time.time()
        if guild_id in self._settings_cache:
            cached, timestamp = self._settings_cache[guild_id]
            if now - timestamp < 60:
                return cached
        from utils.db import get_guild_setting
        settings = get_guild_setting(guild_id, "mod_settings")
        self._settings_cache[guild_id] = (settings, now)
        return settings

    def get_antispam_enabled(self, guild_id: int) -> bool:
        """Check if antispam is enabled for this guild (cached)."""
        try:
            settings = self._get_cached_settings(guild_id)
            return settings.get("antispam_enabled", False)
        except Exception:
            return False

    def set_antispam_enabled(self, guild_id: int, enabled: bool):
        """Toggle antispam for this guild."""
        from utils.db import get_guild_setting, set_guild_setting
        try:
            settings = get_guild_setting(guild_id, "mod_settings")
            settings["antispam_enabled"] = enabled
            set_guild_setting(guild_id, "mod_settings", settings)
            # FIX 6 — Invalidate cache so next read picks up the new value
            if guild_id in self._settings_cache:
                del self._settings_cache[guild_id]
        except Exception as e:
            print(f"[automod] failed to save setting: {e}")

    def _is_exempt(self, member: discord.Member) -> bool:
        """Check if a member is exempt from automod."""
        if member.bot:
            return True
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if member.id == owner_id:
            return True
        if member.guild_permissions.administrator:
            return True
        if member.guild_permissions.manage_messages:
            return True
        if member.guild_permissions.moderate_members:
            return True
        return False

    async def _get_log_channel(self, guild: discord.Guild):
        """Get the configured log channel for this guild."""
        try:
            from utils.db import get_guild_setting
            config = get_guild_setting(guild.id, "log_settings")
            channel_id = config.get("channel_id")
            if channel_id:
                return guild.get_channel(int(channel_id))
        except Exception:
            pass
        return None

    async def _log_action(self, guild: discord.Guild, title: str, description: str,
                           color: int = 0xe74c3c):
        """Send an automod action to the log channel."""
        channel = await self._get_log_channel(guild)
        if not channel:
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="cyn automod")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ─── Spam detection ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detect spam: too many messages in a short window."""
        if not message.guild or message.author.bot:
            return
        if not self.get_antispam_enabled(message.guild.id):
            return
        if self._is_exempt(message.author):
            return

        guild_id = message.guild.id
        user_id = message.author.id
        now = time.time()

        # Track this message
        self.message_tracker[guild_id][user_id].append(now)

        # Clean old entries (older than 10 seconds)
        self.message_tracker[guild_id][user_id] = [
            t for t in self.message_tracker[guild_id][user_id]
            if now - t < 10
        ]

        # Spam threshold: 7 messages in 10 seconds
        recent_count = len(self.message_tracker[guild_id][user_id])
        if recent_count >= 7:
            await self._take_action(message, recent_count)

    async def _take_action(self, message: discord.Message, count: int):
        """Take action against a spammer."""
        guild = message.guild
        member = message.author
        guild_id = guild.id
        user_id = member.id

        # Increment offense count
        self.offense_counts[guild_id][user_id] += 1
        offense = self.offense_counts[guild_id][user_id]

        # First offense: 60s timeout. Repeat: 10min timeout.
        if offense == 1:
            timeout_seconds = 60
        elif offense == 2:
            timeout_seconds = 600
        else:
            timeout_seconds = 3600  # 1 hour

        # Apply timeout
        try:
            await member.timeout(
                timedelta(seconds=timeout_seconds),
                reason=f"cyn automod: spam ({count} messages in 10s, offense #{offense})"
            )
        except discord.Forbidden:
            # Can't timeout (hierarchy), just warn
            pass
        except Exception as e:
            print(f"[automod] timeout failed: {e}")

        # Delete the spam messages if possible
        try:
            await message.channel.purge(
                limit=min(count, 20),
                check=lambda m: m.author.id == user_id,
                bulk=True
            )
        except Exception:
            pass

        # Warn in channel
        try:
            await message.channel.send(
                f"{member.mention}, slow down. you're sending messages too fast.",
                delete_after=10
            )
        except Exception:
            pass

        # Log the action
        await self._log_action(
            guild,
            "🚨 Antispam Action",
            f"**User:** {member.mention} ({member.id})\n"
            f"**Action:** Timeout {timeout_seconds}s\n"
            f"**Reason:** {count} messages in 10 seconds\n"
            f"**Offense #:** {offense}"
        )

        # Reset the tracker for this user
        self.message_tracker[guild_id][user_id] = []

    # ─── Raid detection ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track joins for raid detection."""
        if member.bot:
            return
        guild_id = member.guild.id
        now = time.time()

        self.join_tracker[guild_id].append(now)
        # Clean old entries (older than 60 seconds)
        self.join_tracker[guild_id] = [
            t for t in self.join_tracker[guild_id]
            if now - t < 60
        ]

        # Raid threshold: 10 joins in 60 seconds
        if len(self.join_tracker[guild_id]) >= 10:
            # Only alert once per raid (reset tracker)
            self.join_tracker[guild_id] = []
            await self._log_action(
                member.guild,
                "🚨 Raid Alert",
                f"**{len(self.join_tracker.get(guild_id, []))}+ members** joined in the last 60 seconds.\n"
                f"Possible raid detected. Consider enabling verification or lockdown.",
                color=0xe67e22
            )

    @tasks.loop(seconds=120)
    async def raid_check(self):
        """Periodically clean old join tracker entries."""
        now = time.time()
        for guild_id in list(self.join_tracker.keys()):
            self.join_tracker[guild_id] = [
                t for t in self.join_tracker[guild_id]
                if now - t < 60
            ]
            if not self.join_tracker[guild_id]:
                del self.join_tracker[guild_id]

    @raid_check.before_loop
    async def before_raid_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
