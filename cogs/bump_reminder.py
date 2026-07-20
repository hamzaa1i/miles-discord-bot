"""
cogs/bump_reminder.py — Disboard bump reminder system.

  on_message listener:
    - detect messages from Disboard bot (ID 302050872383242240)
      containing "bump done" or "successfully bumped"
    - asyncio.sleep(7200) → send "@here time to bump again! use `/bump`"

  /bump remind:
    admin slash command that manually schedules a 2-hour bump reminder
    in the current channel.

Background reminders run as fire-and-forget asyncio tasks so the bot
remains responsive. We track active reminders per-channel so we can
cancel a duplicate if a new bump comes in mid-wait.
"""
import asyncio
import logging
import discord
from discord.ext import commands
from discord import app_commands

from utils.db import get_guild_setting, set_guild_setting

logger = logging.getLogger('cyn.bump_reminder')

DISBOARD_ID = 302050872383242240
REMINDER_DELAY_SECONDS = 7200  # 2 hours
BUMP_TRIGGERS = ("bump done", "successfully bumped")

# DB table for storing which channels have a pending reminder so the
# bot can survive a restart mid-wait (best-effort; in-flight asyncio
# tasks are not resumed, but the flag prevents duplicate scheduling).
TABLE = "bump_reminder_state"


class BumpReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # channel_id -> asyncio.Task
        self._tasks: dict[int, asyncio.Task] = {}

    def cog_unload(self):
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    # ─── Helpers ──────────────────────────────────────────────────

    def _get_state(self, guild_id: int) -> dict:
        state = get_guild_setting(guild_id, TABLE)
        return state if isinstance(state, dict) else {}

    def _save_state(self, guild_id: int, state: dict) -> None:
        try:
            set_guild_setting(guild_id, TABLE, state)
        except Exception as e:
            logger.error(f"failed to save bump state: {e}")

    @staticmethod
    def _is_disboard_bump(message: discord.Message) -> bool:
        if message.author.id != DISBOARD_ID:
            return False
        content = (message.content or "").lower()
        # Some Disboard responses are embeds without text content
        if any(t in content for t in BUMP_TRIGGERS):
            return True
        # Fall back to scanning embeds (Disboard usually embeds the result)
        for embed in message.embeds:
            combined = " ".join(filter(None, [
                embed.title, embed.description,
                embed.footer.text if embed.footer else None,
            ])).lower()
            if any(t in combined for t in BUMP_TRIGGERS):
                return True
        return False

    # ─── Reminder worker ─────────────────────────────────────────

    async def _schedule_reminder(self, channel: discord.TextChannel):
        """Sleep 2h then ping @here to bump again."""
        # Cancel any pending reminder for this channel so we don't double-ping
        existing = self._tasks.get(channel.id)
        if existing and not existing.done():
            existing.cancel()

        async def _runner():
            try:
                await asyncio.sleep(REMINDER_DELAY_SECONDS)
                await channel.send(
                    "@here time to bump again! use `/bump`"
                )
                logger.info(
                    f"bump reminder fired in #{channel.name} ({channel.id})"
                )
            except asyncio.CancelledError:
                # Newer bump replaced us — clean exit
                pass
            except discord.Forbidden:
                logger.warning(
                    f"missing permissions to send bump reminder in "
                    f"channel {channel.id}"
                )
            except Exception as e:
                logger.error(f"bump reminder failed: {e}")
            finally:
                self._tasks.pop(channel.id, None)

        self._tasks[channel.id] = asyncio.create_task(_runner())

    # ─── Listener ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Skip DMs and our own messages
        if not message.guild or message.author.bot:
            return
        if not self._is_disboard_bump(message):
            return
        # Disboard just bumped — schedule the 2h reminder in this channel
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return

        # Persist "last bumped" timestamp so a future restart could reschedule
        try:
            state = self._get_state(message.guild.id)
            state["channel_id"] = str(channel.id)
            state["last_bump_message_id"] = str(message.id)
            from datetime import datetime, timezone
            state["last_bump_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state(message.guild.id, state)
        except Exception as e:
            logger.error(f"failed to persist bump state: {e}")

        logger.info(
            f"disboard bump detected in guild {message.guild.id} "
            f"channel {channel.id} — scheduling 2h reminder"
        )
        await self._schedule_reminder(channel)

    # ─── Slash command ───────────────────────────────────────────

    bump = app_commands.Group(name="bump", description="Bump reminder tools")

    @bump.command(
        name="remind",
        description="Manually schedule a 2-hour bump reminder in this channel (admin)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bump_remind(self, interaction: discord.Interaction):
        self.bot.increment_command('bump_remind')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "this command must be run in a text channel.",
                ephemeral=True,
            )
            return

        await self._schedule_reminder(channel)
        logger.info(
            f"manual bump reminder scheduled by {interaction.user.id} "
            f"in guild {interaction.guild.id} channel {channel.id}"
        )
        await interaction.response.send_message(
            f"✅ i'll remind this channel to bump again in 2 hours "
            f"({REMINDER_DELAY_SECONDS // 60} minutes).",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(BumpReminder(bot))
