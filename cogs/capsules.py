"""cogs/capsules.py — PHASE 3 / PART 2 — time capsules.

/capsule create message unlock [public] — seal a message that
    aurelia delivers later (1 hour .. 5 years). Private capsules
    (default) DM the author when they unlock; public capsules post
    back into the channel where they were sealed.
/capsule list — your pending capsules (ephemeral, soonest first).
/capsule delete id — delete one of your pending capsules
    (confirmation button required).
/capsule opened — your last 10 unlocked capsules (ephemeral).

Duration grammar (capsule-specific — "m" means MONTH here, unlike
/remind where it means minutes): "3d", "1w", "1m", "6m", "1y",
"30min", "1h", and stacked forms like "1y6m". Min 1 hour, max 5
years.

Background loop @tasks.loop(minutes=5): finds every capsule whose
unlock time has passed, delivers it (channel post or DM), and marks
it unlocked. Failed deliveries (DMs closed, channel deleted) are
logged and the capsule is still marked unlocked — a terminal state,
so nothing refires every 5 minutes.

DB: utils/db.py capsule helpers (Supabase time_capsules, JSON
fallback).
"""
import logging
import re
import time as _time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.capsules')

# ─── Duration parsing (m = MONTH, mo = month, min = minute) ──────
_CAPSULE_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(minutes?|mins?|min|seconds?|secs?|s|hours?|hrs?|h|"
    r"days?|d|weeks?|w|months?|mo|m|years?|y)",
    re.IGNORECASE,
)
_CAPSULE_UNITS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
    "mo": 2592000, "m": 2592000, "month": 2592000, "months": 2592000,
    "y": 31536000, "year": 31536000, "years": 31536000,
}

MIN_CAPSULE_SECONDS = 3600            # 1 hour
MAX_CAPSULE_SECONDS = 5 * 31536000    # 5 years
MAX_CAPSULE_CHARS = 2000

CAPSULE_TITLE = "🕰️ time capsule unlocked ♡"


def parse_capsule_duration(spec: str) -> int | None:
    """Parse a capsule duration into seconds, or None when invalid.

    Grammar: s / min / h / d / w / m (month!) / mo / y, full words,
    stacked segments ("1y6m"), floats ("1.5w"). Range-checked
    1 hour .. 5 years. A bare number is rejected (ambiguous)."""
    if not spec or not str(spec).strip():
        return None
    text = str(spec).strip().lower()
    matches = _CAPSULE_DURATION_RE.findall(text)
    if not matches:
        return None
    # Reject trailing junk ("2d later") and bare numbers alike.
    stripped = re.sub(r"\s+", "", text)
    rebuilt = "".join(f"{n}{u}" for n, u in matches)
    if stripped != rebuilt:
        return None
    total = 0.0
    for num, unit in matches:
        total += float(num) * _CAPSULE_UNITS[unit.lower()]
    seconds = int(round(total))
    if seconds < MIN_CAPSULE_SECONDS or seconds > MAX_CAPSULE_SECONDS:
        return None
    return seconds


def _format_duration(seconds: int) -> str:
    """Compact human duration for confirmations ("6 months")."""
    seconds = max(1, int(seconds))
    y, rem = divmod(seconds, 31536000)
    mo, rem = divmod(rem, 2592000)
    d, rem = divmod(rem, 86400)
    h, m = divmod(rem, 3600)
    parts = []
    if y:
        parts.append(f"{y} year" + ("s" if y != 1 else ""))
    if mo:
        parts.append(f"{mo} month" + ("s" if mo != 1 else ""))
    if d:
        parts.append(f"{d} day" + ("s" if d != 1 else ""))
    if h:
        parts.append(f"{h}h")
    if m and not parts:
        parts.append(f"{m}m")
    return " ".join(parts) or "a moment"


def _unlock_date_str(unlock_time: float) -> str:
    dt = datetime.utcfromtimestamp(float(unlock_time))
    return dt.strftime("%b %d, %Y · %H:%M utc")


def _created_date_str(created_at) -> str:
    try:
        dt = datetime.fromisoformat(str(created_at))
        return dt.strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return "some time ago"


class CapsuleDeleteView(discord.ui.View):
    """Confirmation buttons for /capsule delete."""

    def __init__(self, cog: "Capsules", capsule_id, user_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.capsule_id = capsule_id
        self.user_id = user_id

    @discord.ui.button(label="delete it", style=discord.ButtonStyle.danger,
                       emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "that isn't your capsule to delete.", ephemeral=True
            )
        try:
            ok = await _db.delete_capsule_async(
                self.capsule_id, str(self.user_id)
            )
        except Exception:
            ok = False
        for item in self.children:
            item.disabled = True
        if ok:
            await interaction.response.edit_message(
                content="🕰️ capsule deleted — it'll stay sealed forever ♡",
                view=self,
            )
        else:
            await interaction.response.edit_message(
                content="couldn't find that pending capsule — it may "
                        "already be unlocked.",
                view=self,
            )

    @discord.ui.button(label="keep it", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "that isn't your capsule to delete.", ephemeral=True
            )
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="kept — your capsule stays sealed ♡", view=self
        )


class Capsules(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not self.delivery_loop.is_running():
            self.delivery_loop.start()

    def cog_unload(self):
        if self.delivery_loop.is_running():
            self.delivery_loop.cancel()

    # ─── Delivery loop ───────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def delivery_loop(self):
        try:
            due = await _db.get_due_capsules_async()
        except Exception as e:
            logger.warning(f"[capsule] due fetch failed: {e}")
            return
        for row in due:
            try:
                await self._deliver(row)
            except Exception as e:
                logger.warning(
                    f"[capsule] delivery error for capsule "
                    f"{row.get('id')}: {e}"
                )
            # Terminal either way (see module docstring).
            try:
                await _db.mark_capsule_unlocked_async(row.get("id"))
            except Exception as e:
                logger.warning(f"[capsule] mark-unlocked failed: {e}")

    @delivery_loop.before_loop
    async def before_delivery_loop(self):
        await self.bot.wait_until_ready()

    async def _deliver(self, row: dict):
        """Send one unlocked capsule (channel post or DM)."""
        user_id = row.get("user_id")
        message_text = str(row.get("message") or "")
        created = _created_date_str(row.get("created_at"))

        embed = discord.Embed(
            title=CAPSULE_TITLE,
            description=message_text[:4096] or "*sealed with nothing? ♡*",
            color=get_seasonal_color(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"sealed {created} · unlocked today ✦")

        if row.get("is_public"):
            guild = self.bot.get_guild(int(row.get("guild_id") or 0))
            channel = None
            if guild:
                try:
                    channel = guild.get_channel(
                        int(row.get("channel_id") or 0)
                    )
                except (TypeError, ValueError):
                    channel = None
            if channel is None:
                logger.warning(
                    f"[capsule] public capsule {row.get('id')}: channel "
                    f"gone — falling back to a DM"
                )
            else:
                mention = f"<@{user_id}>"
                await channel.send(
                    content=f"a time capsule from {mention} has opened 🕰️",
                    embed=embed,
                )
                return

        # Private capsule (or public fallback): DM the author.
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (TypeError, ValueError, discord.NotFound,
                discord.HTTPException):
            logger.warning(
                f"[capsule] couldn't resolve user {user_id} — skipping"
            )
            return
        try:
            await user.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            # DMs closed — log and skip (the loop still marks unlocked).
            logger.warning(
                f"[capsule] DM to {user_id} failed ({type(e).__name__}) — "
                f"capsule {row.get('id')} marked unlocked without delivery"
            )

    # ─── Commands ────────────────────────────────────────────────

    capsule = app_commands.Group(
        name="capsule", description="Seal messages for the future 🕰️"
    )

    @capsule.command(name="create", description="Seal a message that unlocks later")
    @app_commands.describe(
        message="The message to seal (max 2000 chars)",
        unlock="When it unlocks — 3d, 1w, 6m, 1y … (m = months here)",
        public="Post it to this channel when it unlocks (default: DM you)",
    )
    async def capsule_create(self, interaction: discord.Interaction,
                             message: str, unlock: str,
                             public: bool = False):
        self.bot.increment_command('capsule_create')
        if not interaction.guild:
            return await interaction.response.send_message(
                "capsules need a server to live in ♡", ephemeral=True
            )
        message = message.strip()
        if not message:
            return await interaction.response.send_message(
                "an empty capsule? seal something inside it first ♡",
                ephemeral=True,
            )
        if len(message) > MAX_CAPSULE_CHARS:
            return await interaction.response.send_message(
                f"too long — capsules hold up to {MAX_CAPSULE_CHARS} "
                f"characters (you sent {len(message)}).",
                ephemeral=True,
            )
        seconds = parse_capsule_duration(unlock)
        if seconds is None:
            return await interaction.response.send_message(
                "i couldn't read that duration. try forms like `1h`, `3d`, "
                "`1w`, `1m` (month!), `6m`, `1y`, `1y6m` — min 1 hour, "
                "max 5 years.",
                ephemeral=True,
            )

        unlock_time = _time.time() + seconds
        try:
            capsule_id = await _db.create_capsule_async(
                str(interaction.guild.id),
                str(interaction.channel.id) if interaction.channel else None,
                str(interaction.user.id),
                message, unlock_time, public,
            )
        except Exception as e:
            logger.error(f"[capsule] create failed: {e}")
            return await interaction.response.send_message(
                "something broke while sealing it — try again ♡",
                ephemeral=True,
            )

        kind = "posted back **here**" if public else "**DM'd to you**"
        embed = discord.Embed(
            title="꒰ა 🕰️ ໒꒱ time capsule sealed",
            description=(
                f"🕰️ your capsule will unlock in "
                f"**{_format_duration(seconds)}**\n"
                f"on **{_unlock_date_str(unlock_time)}** ✦\n"
                f"when it opens, it'll be {kind}."
            ),
            color=get_seasonal_color(),
        )
        embed.set_footer(
            text=f"capsule #{capsule_id} · {len(message)} chars sealed"
        )
        await interaction.response.send_message(embed=embed)

    @capsule.command(name="list", description="Your pending capsules (soonest first)")
    async def capsule_list(self, interaction: discord.Interaction):
        self.bot.increment_command('capsule_list')
        await interaction.response.defer(ephemeral=True)
        try:
            rows = await _db.get_user_capsules_async(
                str(interaction.user.id), unlocked=False, limit=20
            )
        except Exception as e:
            logger.error(f"[capsule] list failed: {e}")
            rows = []
        if not rows:
            return await interaction.followup.send(
                "you have no capsules waiting — seal one with "
                "`/capsule create` ♡",
                ephemeral=True,
            )
        lines = []
        now = _time.time()
        for r in rows:
            try:
                remaining = max(0, float(r.get("unlock_time", 0)) - now)
            except (TypeError, ValueError):
                remaining = 0
            preview = str(r.get("message") or "")[:40].replace("\n", " ")
            kind = "🌍 public" if r.get("is_public") else "🔒 private"
            lines.append(
                f"`#{r.get('id')}` · {kind} · unlocks in "
                f"**{_format_duration(remaining)}**\n> {preview}"
            )
        embed = discord.Embed(
            title="꒰ა 🕰️ ໒꒱ your pending capsules",
            description="\n".join(lines)[:4000],
            color=get_seasonal_color(),
        )
        embed.set_footer(
            text=f"{len(rows)} sealed · /capsule delete to remove one"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @capsule.command(name="delete", description="Delete one of your pending capsules")
    @app_commands.describe(id="The capsule id from /capsule list")
    async def capsule_delete(self, interaction: discord.Interaction, id: int):
        self.bot.increment_command('capsule_delete')
        view = CapsuleDeleteView(self, id, interaction.user.id)
        await interaction.response.send_message(
            f"delete capsule `#{id}`? this can't be undone — the message "
            "stays sealed forever ♡",
            view=view,
            ephemeral=True,
        )

    @capsule.command(name="opened", description="Your last 10 unlocked capsules")
    async def capsule_opened(self, interaction: discord.Interaction):
        self.bot.increment_command('capsule_opened')
        await interaction.response.defer(ephemeral=True)
        try:
            rows = await _db.get_user_capsules_async(
                str(interaction.user.id), unlocked=True, limit=10
            )
        except Exception as e:
            logger.error(f"[capsule] opened failed: {e}")
            rows = []
        if not rows:
            return await interaction.followup.send(
                "no capsules have opened for you yet ♡", ephemeral=True
            )
        rows = list(reversed(rows))  # most recently unlocked first
        lines = []
        for r in rows:
            preview = str(r.get("message") or "")[:40].replace("\n", " ")
            try:
                unlocked = _unlock_date_str(float(r.get("unlock_time") or 0))
            except (TypeError, ValueError):
                unlocked = "unknown date"
            lines.append(f"> {preview}\n*unlocked {unlocked}*")
        embed = discord.Embed(
            title="꒰ა 🕰️ ໒꒱ opened capsules",
            description="\n".join(lines)[:4000],
            color=get_seasonal_color(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Capsules(bot))
