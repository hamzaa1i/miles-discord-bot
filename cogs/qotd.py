"""cogs/qotd.py — PHASE 2 / PART 2 — question of the day.

An automated daily conversation starter: once per UTC day, after the
configured post hour, aurelia posts a soft question to the QOTD channel
(and opens a public thread for answers when auto_thread is on).

Questions come from the server's own queue (/qotd add, consumed
oldest-first) and fall back to a built-in pool of 40 aesthetic
conversation starters when the queue runs dry.

Commands (all Manage-Guild by default — the whole group):
  /qotd config channel [#channel] [hour_utc] [auto_thread] — configure
  /qotd toggle [enabled]      — on/off (flips when omitted)
  /qotd add question [text]   — queue a custom question
  /qotd list                  — upcoming queue (ephemeral)
  /qotd post                  — force-post the next question now
  /qotd show                  — current settings

DB: utils/db.py qotd helpers (Supabase qotd_settings + qotd_queue,
JSON fallback). Run the PHASE 2 migration SQL at the top of utils/db.py.
"""
import logging
import random
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.qotd')

# ─── Built-in fallback pool (40 soft, aesthetic starters) ────────
FALLBACK_QUESTIONS = (
    "what's a song that feels like a warm hug? 🎧",
    "if you could freeze any moment in time, which one? ⏳",
    "what's your comfort late-night snack? 🌙",
    "what's something small that made you smile recently? 🌸",
    "what's a smell that takes you back to a happy memory? 🕯️",
    "if your day had a soundtrack, what's playing right now? 🎵",
    "what's the nicest thing someone did for you this week? 💛",
    "sunrise person or sunset person — and why? 🌅",
    "what's one thing you're looking forward to? ✨",
    "what's your comfort movie or show you rewatch endlessly? 📺",
    "if you could have tea with anyone, living or not, who? 🍵",
    "what's a small win you had today? 🌟",
    "what's your favorite season and the feeling it gives you? 🍂",
    "share a lyric that lives in your head rent-free 🎶",
    "what's the last thing that made you laugh out loud? 😌",
    "if you could teleport anywhere for a day, where would you go? 🗺️",
    "what's something you learned this week, big or small? 📖",
    "what's your go-to comfort drink? ☕",
    "describe your ideal rainy day 🌧️",
    "what's a hobby you'd pick up if time weren't a factor? 🎨",
    "what's the best advice you've ever received? 💭",
    "what's a food combination you love that others find weird? 🍕",
    "if you had a free day tomorrow with zero obligations, what would you do? ☁️",
    "what's something you're secretly really good at? ✦",
    "which fictional world would you live in for a week? 📚",
    "what's your favorite little ritual? 🕊️",
    "what's a compliment you received that stuck with you? 💗",
    "beach, forest, or city — what recharges you? 🌊",
    "what's the last photo you took that made you happy? 📸",
    "if your pet (or dream pet) had a voice, what would they say? 🐾",
    "what's one goal you're quietly working toward? 🌱",
    "what was your favorite cartoon growing up? 🧸",
    "what's the most beautiful place you've ever been? 🏔️",
    "what's a small luxury that makes your day better? 🫧",
    "if today was a chapter title, what would it be called? 📕",
    "what's something you've changed your mind about recently? 🌗",
    "what's your favorite way to waste time? 🎮",
    "share one thing on your bucket list 🪣",
    "what's a flavor that reminds you of childhood? 🍦",
    "if you could thank one person from your past, who would it be? 💌",
)

QOTD_TITLE = "꒰ა 💭 ໒꒱ question of the day"
QOTD_FOOTER = "reply in the thread below · question of the day ♡"


class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not self.posting_loop.is_running():
            self.posting_loop.start()

    def cog_unload(self):
        if self.posting_loop.is_running():
            self.posting_loop.cancel()

    # ─── Shared posting engine ───────────────────────────────────

    async def _post_qotd(self, guild: discord.Guild, channel,
                         settings: dict, now: datetime) -> bool:
        """Post the next question to `channel` and stamp last_post_date.

        Returns True when the embed actually went out. Used by both the
        15-minute background loop and /qotd post."""
        question = None
        try:
            queued = await _db.get_next_qotd_question_async(str(guild.id))
            if queued and (queued.get("question") or "").strip():
                question = queued["question"].strip()
        except Exception as e:
            logger.warning(f"[qotd] queue fetch failed for {guild.id}: {e}")

        if not question:
            question = random.choice(FALLBACK_QUESTIONS)

        embed = discord.Embed(
            title=QOTD_TITLE,
            description=f"### {question}",
            color=get_seasonal_color(),
            timestamp=now,
        )
        embed.set_footer(text=QOTD_FOOTER)

        try:
            message = await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(
                f"[qotd] no permission to post in channel {channel.id} "
                f"(guild {guild.id})"
            )
            return False
        except discord.HTTPException as e:
            logger.error(f"[qotd] post failed in {channel.id}: {e}")
            return False

        # Auto-thread — best-effort; a failed thread never fails the post.
        if settings.get("auto_thread", True):
            try:
                await channel.create_thread(
                    message=message,
                    name=f"qotd — {datetime.utcnow().strftime('%b %d')}",
                    auto_archive_duration=1440,
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.warning(f"[qotd] thread creation failed: {e}")

        try:
            await _db.set_qotd_settings_async(str(guild.id), {
                "last_post_date": now.date().isoformat(),
            })
        except Exception as e:
            logger.error(f"[qotd] last_post_date save failed: {e}")

        logger.info(f"[qotd] posted to #{channel.name} in {guild.name}")
        return True

    # ─── Background loop ─────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def posting_loop(self):
        now = datetime.utcnow()
        today = now.date().isoformat()
        for guild in self.bot.guilds:
            try:
                settings = await _db.get_qotd_settings_async(str(guild.id))
                if not settings.get("enabled"):
                    continue
                # One post per UTC day.
                if str(settings.get("last_post_date") or "") == today:
                    continue
                # Not yet the configured hour.
                try:
                    post_hour = int(settings.get("post_hour_utc") or 14)
                except (TypeError, ValueError):
                    post_hour = 14
                if now.hour < post_hour:
                    continue
                channel_id = settings.get("channel_id")
                if not channel_id:
                    continue
                try:
                    channel = guild.get_channel(int(channel_id))
                except (TypeError, ValueError):
                    channel = None
                if channel is None:
                    continue
                await self._post_qotd(guild, channel, settings, now)
            except Exception as e:
                logger.warning(f"[qotd] loop error for guild {guild.id}: {e}")

    @posting_loop.before_loop
    async def before_posting_loop(self):
        await self.bot.wait_until_ready()

    # ─── Commands (whole group: Manage Server by default) ────────

    qotd = app_commands.Group(
        name="qotd",
        description="Question of the day configuration",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @qotd.command(name="config", description="Configure the QOTD channel, post hour, and threads")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Channel where the daily question is posted",
        hour_utc="Post hour in UTC (0-23, default 14)",
        auto_thread="Open a public thread for answers on each question",
    )
    async def qotd_config(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          hour_utc: int = None,
                          auto_thread: bool = None):
        self.bot.increment_command('qotd_config')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        if hour_utc is not None and not (0 <= hour_utc <= 23):
            return await interaction.response.send_message(
                "hour_utc must be between 0 and 23.", ephemeral=True
            )

        settings = await _db.get_qotd_settings_async(str(interaction.guild.id))
        settings["channel_id"] = str(channel.id)
        settings["enabled"] = True  # auto-enable on config
        if hour_utc is not None:
            settings["post_hour_utc"] = hour_utc
        if auto_thread is not None:
            settings["auto_thread"] = auto_thread
        await _db.set_qotd_settings_async(str(interaction.guild.id), settings)

        hour = settings.get("post_hour_utc", 14)
        threads = "on" if settings.get("auto_thread", True) else "off"
        await interaction.response.send_message(
            f"✅ question of the day configured — posting to {channel.mention} "
            f"daily at **{hour:02d}:00 utc**, auto-thread **{threads}**, "
            f"and **enabled**."
        )

    @qotd.command(name="toggle", description="Enable or disable the question of the day")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(enabled="On or off (flips the current state when omitted)")
    async def qotd_toggle(self, interaction: discord.Interaction,
                         enabled: bool = None):
        self.bot.increment_command('qotd_toggle')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        settings = await _db.get_qotd_settings_async(str(interaction.guild.id))
        if enabled is None:
            enabled = not settings.get("enabled", False)
        settings["enabled"] = enabled
        await _db.set_qotd_settings_async(str(interaction.guild.id), settings)
        warn = ""
        if enabled and not settings.get("channel_id"):
            warn = "\n⚠️ no channel set — use `/qotd config channel:#channel` first."
        await interaction.response.send_message(
            f"✅ question of the day is now **"
            f"{'enabled' if enabled else 'disabled'}**.{warn}"
        )

    @qotd.command(name="add", description="Add a custom question to the QOTD queue")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(question="The question to queue (oldest-first)")
    async def qotd_add(self, interaction: discord.Interaction, question: str):
        self.bot.increment_command('qotd_add')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        question = question.strip()[:500]
        if not question:
            return await interaction.response.send_message(
                "the question can't be empty.", ephemeral=True
            )
        try:
            await _db.add_qotd_question_async(
                str(interaction.guild.id), question, str(interaction.user.id)
            )
        except Exception as e:
            logger.error(f"[qotd] add failed: {e}")
            return await interaction.response.send_message(
                "couldn't save that question — try again.", ephemeral=True
            )
        await interaction.response.send_message(
            f"✅ queued: *{question}*\nit'll be posted when its turn comes ♡"
        )

    @qotd.command(name="list", description="Show the upcoming queued questions")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_list(self, interaction: discord.Interaction):
        self.bot.increment_command('qotd_list')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        try:
            rows = await _db.get_qotd_queue_async(str(interaction.guild.id))
        except Exception as e:
            logger.error(f"[qotd] list failed: {e}")
            rows = []
        if not rows:
            return await interaction.response.send_message(
                "the custom queue is empty — aurelia is drawing from her "
                "built-in pool of questions. add some with `/qotd add` ♡",
                ephemeral=True,
            )
        lines = []
        for i, r in enumerate(rows[:15], 1):
            q = str(r.get("question", ""))[:90]
            lines.append(f"`{i}.` {q}")
        extra = f"\n…and {len(rows) - 15} more" if len(rows) > 15 else ""
        await interaction.response.send_message(
            "**upcoming questions:**\n" + "\n".join(lines) + extra,
            ephemeral=True,
        )

    @qotd.command(name="post", description="Post the next question right now (admin)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_post(self, interaction: discord.Interaction):
        self.bot.increment_command('qotd_post')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        settings = await _db.get_qotd_settings_async(str(interaction.guild.id))
        channel_id = settings.get("channel_id")
        if not channel_id:
            return await interaction.response.send_message(
                "no QOTD channel set — use `/qotd config channel:#channel` first.",
                ephemeral=True,
            )
        try:
            channel = interaction.guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            channel = None
        if channel is None:
            return await interaction.response.send_message(
                "the configured QOTD channel no longer exists — reconfigure "
                "with `/qotd config`.", ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        ok = await self._post_qotd(
            interaction.guild, channel, settings, datetime.utcnow()
        )
        if ok:
            await interaction.followup.send(f"✅ posted to {channel.mention}.")
        else:
            await interaction.followup.send(
                "couldn't post — check my permissions in that channel.",
            )

    @qotd.command(name="show", description="Show the current QOTD settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_show(self, interaction: discord.Interaction):
        self.bot.increment_command('qotd_show')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        settings = await _db.get_qotd_settings_async(str(interaction.guild.id))
        channel = None
        if settings.get("channel_id"):
            try:
                channel = interaction.guild.get_channel(int(settings["channel_id"]))
            except (TypeError, ValueError):
                channel = None
        try:
            queue_count = len(
                await _db.get_qotd_queue_async(str(interaction.guild.id))
            )
        except Exception:
            queue_count = 0

        embed = discord.Embed(
            title="꒰ა 💭 ໒꒱ qotd settings",
            color=get_seasonal_color(),
        )
        embed.add_field(
            name="status",
            value=(
                f"**enabled:** `{settings.get('enabled', False)}`\n"
                f"**channel:** {channel.mention if channel else '*not set*'}\n"
                f"**post hour:** `{settings.get('post_hour_utc', 14):02d}:00 utc`\n"
                f"**auto-thread:** `{settings.get('auto_thread', True)}`\n"
                f"**last posted:** `{settings.get('last_post_date') or 'never'}`\n"
                f"**queued questions:** `{queue_count}`"
            ),
            inline=False,
        )
        embed.set_footer(text="built-in fallback pool: 40 questions ♡")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(QOTD(bot))
