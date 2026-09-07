"""cogs/achievements.py — PHASE 3 / PART 3 — achievements.

/achievements show [@user] [public] — everything a user has unlocked,
    grouped by rarity (legendary first), with a progress bar.
    Ephemeral by default.
/achievements list — ALL possible achievements; locked ones show as
    "???" so there's still something to chase. Ephemeral.

Passive tracking:
  * on_message: first_message, 100_messages, 1000_messages,
    night_owl (00:00–04:59 UTC), early_bird (05:00–08:59 UTC)
  * on_member_update: first_boost (was not a booster → now is)
  * on_raw_reaction_add: loved (a message's total reactions ≥ 50)
  * Hooks called from other cogs (loose coupling via get_cog):
      cogs/daily.py     → check_streak (streak_7 / streak_30 / streak_100)
      cogs/leveling.py  → check_level  (level_10 / level_25 / level_50)
      cogs/confess.py   → unlock_confession
  * "helper" is defined in the catalog but has no wired trigger yet
    (its detection heuristic isn't part of this phase — it simply
    stays locked).

Message counts: in-memory counters, lazily loaded from the
message_counts store on a user's first message after boot, flushed
every 5 minutes (and immediately at the 1/100/1000 milestones), so
the hot path costs zero REST calls.

When an achievement unlocks, the user gets a rarity-colored DM;
closed DMs are silently ignored.

DB: utils/db.py unlock_achievement_async / get_user_achievements_async /
get_message_count_async / set_message_count_async (Supabase
user_achievements + message_counts, JSON fallback).
"""
import asyncio
import logging
import time as _time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.achievements')

# ─── Catalog (spec-fixed) ────────────────────────────────────────
ACHIEVEMENTS = {
    "first_message": {
        "name": "first steps",
        "description": "sent your first message ♡",
        "emoji": "🌱",
        "rarity": "common",
    },
    "100_messages": {
        "name": "chatty",
        "description": "sent 100 messages",
        "emoji": "💬",
        "rarity": "common",
    },
    "1000_messages": {
        "name": "wordsmith",
        "description": "sent 1000 messages",
        "emoji": "📜",
        "rarity": "rare",
    },
    "level_10": {
        "name": "rising star",
        "description": "reached level 10",
        "emoji": "⭐",
        "rarity": "common",
    },
    "level_25": {
        "name": "veteran",
        "description": "reached level 25",
        "emoji": "🌟",
        "rarity": "rare",
    },
    "level_50": {
        "name": "legendary",
        "description": "reached level 50",
        "emoji": "✨",
        "rarity": "epic",
    },
    "night_owl": {
        "name": "night owl",
        "description": "active between 12am-4am UTC",
        "emoji": "🌙",
        "rarity": "uncommon",
    },
    "early_bird": {
        "name": "early bird",
        "description": "active between 5am-8am UTC",
        "emoji": "☀️",
        "rarity": "uncommon",
    },
    "streak_7": {
        "name": "week warrior",
        "description": "7-day daily streak",
        "emoji": "🔥",
        "rarity": "uncommon",
    },
    "streak_30": {
        "name": "month monk",
        "description": "30-day daily streak",
        "emoji": "💎",
        "rarity": "epic",
    },
    "streak_100": {
        "name": "century soul",
        "description": "100-day daily streak",
        "emoji": "👑",
        "rarity": "legendary",
    },
    "first_boost": {
        "name": "supporter",
        "description": "boosted the server",
        "emoji": "💜",
        "rarity": "rare",
    },
    "helper": {
        "name": "kind soul",
        "description": "helped 10 different users in chat",
        "emoji": "🌷",
        "rarity": "rare",
    },
    "loved": {
        "name": "adored",
        "description": "received 50 reactions on one message",
        "emoji": "💖",
        "rarity": "epic",
    },
    "confession": {
        "name": "secret keeper",
        "description": "made your first confession",
        "emoji": "🤫",
        "rarity": "uncommon",
    },
}

RARITY_COLORS = {
    "common": 0xB0BEC5,      # gray
    "uncommon": 0x66BB6A,    # green
    "rare": 0x42A5F5,        # blue
    "epic": 0xAB47BC,        # purple
    "legendary": 0xFFD700,   # gold
}

RARITY_ORDER = ("legendary", "epic", "rare", "uncommon", "common")

# Reaction total that grants "loved".
LOVED_THRESHOLD = 50

# Streak → achievement key (cogs/daily.py hook).
STREAK_ACHIEVEMENTS = {
    7: "streak_7",
    30: "streak_30",
    100: "streak_100",
}

# Level → achievement key (cogs/leveling.py hook).
LEVEL_ACHIEVEMENTS = {
    10: "level_10",
    25: "level_25",
    50: "level_50",
}


def _date_str(unlocked_at) -> str:
    try:
        return datetime.fromisoformat(str(unlocked_at)).strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return "unknown date"


class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {(guild_id, user_id): message count} — lazily loaded
        self._counts: dict[tuple, int] = {}
        # Keys whose stored count lags the in-memory one.
        self._dirty: set[tuple] = set()
        # In-flight per-user loads (dedupes concurrent on_message races).
        self._load_tasks: dict[tuple, asyncio.Task] = {}
        # {message_id: [total_reactions, last_ts]} for the "loved" check
        self._reaction_counts: dict[int, list] = {}
        # message_ids that already resolved (awarded or confirmed not yet)
        self._loved_done: set[int] = set()
        if not self.maintenance_loop.is_running():
            self.maintenance_loop.start()

    def cog_unload(self):
        if self.maintenance_loop.is_running():
            self.maintenance_loop.cancel()

    # ─── Message counting (lazy load + periodic flush) ────────────

    async def _load_count(self, gid: int, uid: int):
        try:
            stored = await _db.get_message_count_async(gid, uid)
        except Exception:
            stored = 0
        self._counts[(gid, uid)] = int(stored or 0)

    async def _ensure_count(self, gid: int, uid: int):
        key = (gid, uid)
        if key in self._counts:
            return
        task = self._load_tasks.get(key)
        if task is None:
            self._load_tasks[key] = task = asyncio.create_task(
                self._load_count(gid, uid)
            )
        try:
            await asyncio.shield(task)
        except Exception:
            self._counts.setdefault(key, 0)
        finally:
            self._load_tasks.pop(key, None)

    # ─── Maintenance loop (flush counts, prune reaction cache) ────

    @tasks.loop(minutes=5)
    async def maintenance_loop(self):
        # Flush only the counters that have drifted since the last
        # write — milestones (1/100/1000) persist immediately, this
        # covers the in-between growth.
        try:
            now = _time.time()
            for key in list(self._dirty):
                count = self._counts.get(key)
                if count is None:
                    self._dirty.discard(key)
                    continue
                try:
                    await _db.set_message_count_async(key[0], key[1], count)
                    self._dirty.discard(key)
                except Exception:
                    break  # retry next cycle
            # Prune reaction counters older than 7 days and keep the
            # done-set bounded.
            for mid in list(self._reaction_counts.keys()):
                entry = self._reaction_counts.get(mid)
                if not entry or now - entry[1] > 7 * 86400:
                    self._reaction_counts.pop(mid, None)
            if len(self._loved_done) > 5000:
                self._loved_done = set(list(self._loved_done)[-2500:])
        except Exception as e:
            logger.warning(f"[achievements] maintenance error: {e}")

    @maintenance_loop.before_loop
    async def before_maintenance_loop(self):
        await self.bot.wait_until_ready()

    # ─── Core unlock + notify ─────────────────────────────────────

    async def _try_unlock(self, guild: discord.Guild, member,
                          achievement_key: str) -> bool:
        """Unlock an achievement and DM the user. Returns True when
        newly unlocked. Never raises."""
        try:
            if guild is None or member is None:
                return False
            newly = await _db.unlock_achievement_async(
                str(guild.id), str(member.id), achievement_key
            )
            if not newly:
                return False
            meta = ACHIEVEMENTS.get(achievement_key)
            if not meta:
                return False
            logger.info(
                f"[achievements] {member.id} unlocked "
                f"'{achievement_key}' in guild {guild.id}"
            )
            embed = discord.Embed(
                title=f"{meta['emoji']} achievement unlocked!",
                description=(
                    f"**{meta['name']}** ({meta['rarity']})\n"
                    f"{meta['description']}"
                ),
                color=RARITY_COLORS.get(meta["rarity"], 0xB0BEC5),
            )
            embed.set_footer(text="see all of them with /achievements show")
            try:
                await member.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass  # DMs closed — the unlock still counts
            return True
        except Exception as e:
            logger.warning(
                f"[achievements] unlock '{achievement_key}' failed: {e}"
            )
            return False

    # ─── Passive listeners ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if getattr(message, "webhook_id", None):
            return
        if message.type not in (discord.MessageType.default,
                                discord.MessageType.reply):
            return
        member = message.author
        gid, uid = message.guild.id, member.id
        try:
            await self._ensure_count(gid, uid)
        except Exception:
            return

        key = (gid, uid)
        self._counts[key] = self._counts.get(key, 0) + 1
        count = self._counts[key]

        # Persist exactly at the milestones; the 5-min loop covers drift.
        if count in (1, 100, 1000):
            self._dirty.discard(key)
            try:
                await _db.set_message_count_async(gid, uid, count)
            except Exception:
                self._dirty.add(key)
        else:
            self._dirty.add(key)

        checks = []
        if count == 1:
            checks.append("first_message")
        if count == 100:
            checks.append("100_messages")
        if count == 1000:
            checks.append("1000_messages")
        hour = datetime.utcnow().hour
        if 0 <= hour <= 4:
            checks.append("night_owl")
        elif 5 <= hour <= 8:
            checks.append("early_bird")
        for achievement_key in checks:
            await self._try_unlock(message.guild, member, achievement_key)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member,
                               after: discord.Member):
        # first_boost: was not a booster, now is.
        if before.premium_subscriber or not after.premium_subscriber:
            return
        await self._try_unlock(after.guild, after, "first_boost")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,
                                  payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        if payload.user_id == self.bot.user.id:
            return  # bot's own reactions still count in the fetched total
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        mid = payload.message_id
        if mid in self._loved_done:
            return

        entry = self._reaction_counts.get(mid)
        if entry is None:
            # First time seeing this message — seed with the true total
            # (one fetch; the reaction we're processing is already
            # included in the REST counts).
            info = await self._fetch_message_reaction_info(payload)
            if info is None:
                return  # fetch failed; retry on the next reaction
            total, author = info
            self._reaction_counts[mid] = [total, _time.time()]
            if total >= LOVED_THRESHOLD:
                self._loved_done.add(mid)
                if author is not None and not author.bot:
                    await self._try_unlock(guild, author, "loved")
            return

        entry[0] += 1
        entry[1] = _time.time()
        if entry[0] >= LOVED_THRESHOLD:
            # Re-verify against the real message (resync after restarts).
            info = await self._fetch_message_reaction_info(payload)
            if info is None:
                return
            total, author = info
            self._reaction_counts[mid] = [total, _time.time()]
            if total >= LOVED_THRESHOLD:
                self._loved_done.add(mid)
                if author is not None and not author.bot:
                    await self._try_unlock(guild, author, "loved")

    async def _fetch_message_reaction_info(self,
                                           payload: discord.RawReactionActionEvent):
        """(total reactions, author Member | None) for the payload's
        message, or None when the fetch failed."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return None
        channel = guild.get_channel_or_thread(payload.channel_id)
        if channel is None:
            return None
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        total = sum(int(r.count) for r in message.reactions)
        author = message.author
        if not isinstance(author, discord.Member):
            author = guild.get_member(author.id)
        return total, author

    # ─── Public hooks for other cogs ──────────────────────────────

    async def check_streak(self, guild: discord.Guild, member, streak: int):
        """cogs/daily.py — call after a /daily claim."""
        key = STREAK_ACHIEVEMENTS.get(int(streak))
        if key:
            await self._try_unlock(guild, member, key)

    async def check_level(self, guild: discord.Guild, member, level: int):
        """cogs/leveling.py (and /daily's level-up path) — call when a
        member's level changes."""
        key = LEVEL_ACHIEVEMENTS.get(int(level))
        if key:
            await self._try_unlock(guild, member, key)

    async def unlock_confession(self, guild: discord.Guild, member):
        """cogs/confess.py — call after a confession is posted."""
        await self._try_unlock(guild, member, "confession")

    # ─── Commands ─────────────────────────────────────────────────

    achievements = app_commands.Group(
        name="achievements",
        description="Your unlocked badges and everything still to earn ✦",
    )

    @achievements.command(name="show", description="Show someone's unlocked achievements")
    @app_commands.describe(
        user="Whose achievements to show (defaults to you)",
        public="Show the card publicly instead of just to you",
    )
    async def achievements_show(self, interaction: discord.Interaction,
                                user: discord.Member = None,
                                public: bool = False):
        self.bot.increment_command('achievements_show')
        if not interaction.guild:
            return await interaction.response.send_message(
                "achievements live in servers ♡", ephemeral=True
            )
        target = user or interaction.user
        await interaction.response.defer(ephemeral=not public)
        try:
            rows = await _db.get_user_achievements_async(
                str(interaction.guild.id), str(target.id)
            )
        except Exception as e:
            logger.error(f"[achievements] show failed: {e}")
            rows = []

        unlocked = {}
        for r in rows:
            k = r.get("achievement_key")
            if k in ACHIEVEMENTS:
                unlocked[k] = r.get("unlocked_at")

        total = len(ACHIEVEMENTS)
        got = len(unlocked)
        percent = round(got / total * 100) if total else 0
        filled = round(percent / 100 * 20)
        bar = "▰" * filled + "▱" * (20 - filled)

        embed = discord.Embed(
            title=f"꒰ა ✦ ໒꒱ {target.display_name}'s achievements",
            description=(
                f"{got}/{total} achievements ({percent}%)\n"
                f"`{bar}`"
            ),
            color=get_seasonal_color(),
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        else:
            embed.set_thumbnail(url=target.default_avatar.url)

        grouped_lines = {r: [] for r in RARITY_ORDER}
        for rarity in RARITY_ORDER:
            for akey, meta in ACHIEVEMENTS.items():
                if meta["rarity"] != rarity:
                    continue
                if akey in unlocked:
                    grouped_lines[rarity].append(
                        f"{meta['emoji']} **{meta['name']}** — "
                        f"{meta['description']} · "
                        f"*{_date_str(unlocked.get(akey))}*"
                    )
        for rarity in RARITY_ORDER:
            lines = grouped_lines[rarity]
            if lines:
                embed.add_field(
                    name=f"{rarity} ({len(lines)})",
                    value="\n".join(lines)[:1024],
                    inline=False,
                )
        if got == 0:
            embed.add_field(
                name="start here",
                value="send your first message to unlock 🌱 *first steps*",
                inline=False,
            )
        await interaction.followup.send(
            embed=embed, ephemeral=not public
        )

    @achievements.command(name="list", description="Every possible achievement")
    async def achievements_list(self, interaction: discord.Interaction):
        self.bot.increment_command('achievements_list')
        if not interaction.guild:
            return await interaction.response.send_message(
                "achievements live in servers ♡", ephemeral=True
            )
        try:
            rows = await _db.get_user_achievements_async(
                str(interaction.guild.id), str(interaction.user.id)
            )
        except Exception:
            rows = []
        unlocked_keys = {
            r.get("achievement_key") for r in rows
            if r.get("achievement_key") in ACHIEVEMENTS
        }

        lines = []
        for rarity in RARITY_ORDER:
            group = [k for k, m in ACHIEVEMENTS.items()
                     if m["rarity"] == rarity]
            if not group:
                continue
            lines.append(f"**__{rarity}__**")
            for akey in group:
                meta = ACHIEVEMENTS[akey]
                if akey in unlocked_keys:
                    lines.append(
                        f"{meta['emoji']} **{meta['name']}** — "
                        f"{meta['description']} ✅"
                    )
                else:
                    lines.append(f"{meta['emoji']} **???** — ??? 🔒")
            lines.append("")
        embed = discord.Embed(
            title="꒰ა ✦ ໒꒱ all achievements",
            description="\n".join(lines)[:4096],
            color=0xB0BEC5,  # gray — locked things stay mysterious
        )
        embed.set_footer(
            text=f"{len(unlocked_keys)}/{len(ACHIEVEMENTS)} unlocked · "
                 "🔒 = ???"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Achievements(bot))
