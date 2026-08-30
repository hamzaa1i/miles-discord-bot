"""cogs/timezone.py — PHASE 2 / PART 5 — timezone utilities.

/time group (stdlib zoneinfo only — no extra dependencies):
  /time for user:<@member>     — their current local time + offset diff
  /time convert time:<t> from_tz:<tz> to_tz:<tz> — e.g. "8:00 PM",
                                  EST -> GMT, America/New_York -> Europe/London
  /time set timezone:<tz>      — set YOUR timezone (stored in user_profiles,
                                  shared with /profile_set timezone)

Timezone names accepted everywhere: common abbreviations (EST, PST, CST,
GMT, UTC, CET, JST, AEST, BST, …), UTC±H[:MM] offsets, and full IANA
names (America/New_York, Europe/Paris, Asia/Tokyo, …).
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone as _timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import discord
from discord import app_commands
from discord.ext import commands

from utils.veloura_embeds import get_seasonal_color
from utils.db import get_user_profile, set_user_profile

log = logging.getLogger('cyn.timezone')

# ─── Timezone resolution ─────────────────────────────────────────

# Common abbreviations -> fixed UTC offsets in hours. Abbreviations are
# inherently fixed-offset (EST is always UTC-5; DST variants get their
# own entries), unlike IANA zones which follow local DST rules.
TZ_ABBREVIATIONS = {
    "UTC": 0, "GMT": 0, "Z": 0,
    "EST": -5, "EDT": -4,
    "CST": -6, "CDT": -5,
    "MST": -7, "MDT": -6,
    "PST": -8, "PDT": -7,
    "AKST": -9, "AKDT": -8,
    "HST": -10,
    "BST": 1,
    "CET": 1, "CEST": 2,
    "EET": 2, "EEST": 3,
    "MSK": 3,
    "IST": 5.5,          # India Standard Time
    "KST": 9,
    "JST": 9,
    "AEST": 10, "AEDT": 11,
    "ACST": 9.5, "ACDT": 10.5,
    "NZST": 12, "NZDT": 13,
}

# UTC±H / GMT±H / UTC+H:MM style offsets
_OFFSET_RE = re.compile(
    r"^(?:utc|gmt)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE
)

_IANA_CACHE = None


def _iana_names() -> set:
    """Available IANA zone names (cached — the stdlib scans the tz db)."""
    global _IANA_CACHE
    if _IANA_CACHE is None:
        try:
            _IANA_CACHE = set(available_timezones())
        except Exception:
            _IANA_CACHE = set()
    return _IANA_CACHE


def resolve_timezone(name: str):
    """Resolve a user-supplied timezone string.

    Returns (tzinfo, display_name) or None when the name is not
    recognized. Accepts abbreviations (EST), UTC±H offsets, and IANA
    names (America/New_York)."""
    if not name or not str(name).strip():
        return None
    text = str(name).strip()

    # 1. Common abbreviation (case-insensitive)
    upper = text.upper()
    if upper in TZ_ABBREVIATIONS:
        hours = TZ_ABBREVIATIONS[upper]
        delta = timedelta(hours=hours)
        sign = "+" if hours >= 0 else "−"
        hh = int(abs(hours))
        mm = int(round((abs(hours) - hh) * 60))
        label = f"UTC{sign}{hh}" + (f":{mm:02d}" if mm else "")
        return _timezone(delta), f"{upper} ({label})"

    # 2. UTC±H[:MM] / GMT±H[:MM] offsets
    m = _OFFSET_RE.match(text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        hours = int(m.group(2))
        minutes = int(m.group(3) or 0)
        if hours > 14 or minutes > 59:
            return None
        delta = sign * timedelta(hours=hours, minutes=minutes)
        canonical = f"UTC{'+' if sign > 0 else '-'}{hours:02d}" \
                    + (f":{minutes:02d}" if minutes else "")
        return _timezone(delta), canonical

    # 3. IANA zone name
    try:
        zone = ZoneInfo(text)
        return zone, text
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        pass
    # Case heal: "america/new_york" -> "America/New_York"
    for candidate in _iana_names():
        if candidate.lower() == text.lower():
            return ZoneInfo(candidate), candidate
    return None


# ─── Time parsing / formatting helpers ────────────────────────────

_TIME_RE = re.compile(
    r"^(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?$", re.IGNORECASE
)


def parse_clock_time(text: str):
    """Parse a clock time like "8:00 PM", "8pm", "14:30", "08:00".

    Returns a datetime.time or None when invalid."""
    if not text or not str(text).strip():
        return None
    m = _TIME_RE.match(str(text).strip())
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = (m.group(3) or "").replace(".", "").lower()
    if minute > 59:
        return None
    if meridiem:  # 12-hour clock
        if not (1 <= hour <= 12):
            return None
        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        else:  # pm
            hour = 12 if hour == 12 else hour + 12
    else:  # 24-hour clock
        if hour > 23:
            return None
    return _time_from_hm(hour, minute)


def _time_from_hm(hour: int, minute: int):
    from datetime import time as _time
    return _time(hour, minute)


def format_offset_delta(delta: timedelta) -> str:
    """Human string for an offset difference: '5h 30m', '2h', '45m', '0m'."""
    total = int(round(delta.total_seconds() / 60))
    sign = "-" if total < 0 else ""
    total = abs(total)
    h, m = divmod(total, 60)
    if h and m:
        return f"{sign}{h}h {m}m"
    if h:
        return f"{sign}{h}h"
    return f"{sign}{m}m"


class TimezoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── helpers ─────────────────────────────────────────────────

    @staticmethod
    async def _profile_tz(user_id: int):
        """Resolve a user's stored profile timezone. Returns
        (tzinfo, display_name) or None when unset/unresolvable."""
        try:
            profile = await asyncio.to_thread(get_user_profile, user_id)
        except Exception as e:
            log.warning(f"[time] profile read failed for {user_id}: {e}")
            return None
        stored = (profile.get("timezone") or "").strip() if profile else ""
        if not stored:
            return None
        return resolve_timezone(stored)

    # ─── /time for ───────────────────────────────────────────────

    time_group = app_commands.Group(
        name="time", description="Timezone utilities"
    )

    @time_group.command(
        name="for", description="See someone's current local time"
    )
    @app_commands.describe(user="Whose local time to look up")
    async def time_for(self, interaction: discord.Interaction,
                       user: discord.Member):
        self.bot.increment_command('time_for')
        resolved = await self._profile_tz(user.id)
        if resolved is None:
            profile = await asyncio.to_thread(get_user_profile, user.id)
            stored = (profile.get("timezone") or "").strip() if profile else ""
            if stored:  # set, but no longer resolvable
                return await interaction.response.send_message(
                    f"@{user.display_name}'s saved timezone "
                    f"(\"{stored}\") couldn't be read — they can re-set it "
                    f"with /time set timezone:America/New_York ♡",
                    ephemeral=True,
                )
            return await interaction.response.send_message(
                f"@{user.display_name} hasn't set their timezone yet. they "
                f"can set it with /time set timezone:America/New_York ♡",
                ephemeral=True,
            )

        tz, display = resolved
        target_now = datetime.now(tz)
        local_time = target_now.strftime("%I:%M %p").lstrip("0")
        day_of_week = target_now.strftime("%A").lower()

        # Difference vs the interaction user's timezone (or UTC).
        viewer = await self._profile_tz(interaction.user.id)
        if viewer is not None:
            viewer_tz = viewer[0]
            viewer_label = "you"
        else:
            viewer_tz = _timezone.utc
            viewer_label = "utc"
        diff = (target_now.utcoffset() or timedelta(0)) - (
            datetime.now(viewer_tz).utcoffset() or timedelta(0)
        )
        diff_str = _diff_string(diff, viewer_label)

        embed = discord.Embed(
            description=(
                f"{user.display_name}'s local time is **{local_time}** "
                f"({display}) · {diff_str}"
            ),
            color=get_seasonal_color(),
        )
        embed.add_field(name="day", value=day_of_week, inline=True)
        await interaction.response.send_message(embed=embed)

    # ─── /time convert ───────────────────────────────────────────

    @time_group.command(
        name="convert", description="Convert a time between timezones"
    )
    @app_commands.describe(
        time="The time, e.g. 8:00 PM or 14:30",
        from_tz="Source timezone (EST, PST, GMT, UTC+3, America/New_York…)",
        to_tz="Target timezone (Europe/London, JST, AEST…)",
    )
    async def time_convert(self, interaction: discord.Interaction,
                           time: str, from_tz: str, to_tz: str):
        self.bot.increment_command('time_convert')

        clock = parse_clock_time(time)
        if clock is None:
            return await interaction.response.send_message(
                "couldn't read that time — try `8:00 PM`, `8pm`, or `14:30`.",
                ephemeral=True,
            )
        src = resolve_timezone(from_tz)
        if src is None:
            return await interaction.response.send_message(
                f"unknown timezone `{from_tz}` — use an abbreviation "
                f"(EST, GMT…), an offset (UTC+3), or an IANA name "
                f"(America/New_York).",
                ephemeral=True,
            )
        dst = resolve_timezone(to_tz)
        if dst is None:
            return await interaction.response.send_message(
                f"unknown timezone `{to_tz}` — use an abbreviation "
                f"(EST, GMT…), an offset (UTC+3), or an IANA name "
                f"(America/London).",
                ephemeral=True,
            )

        # Anchor the clock time to today's date in the source zone.
        src_now = datetime.now(src[0])
        moment = datetime.combine(src_now.date(), clock, tzinfo=src[0])
        converted = moment.astimezone(dst[0])

        out_str = converted.strftime("%I:%M %p").lstrip("0")
        if converted.date() > moment.date():
            out_str += " (next day)"
        elif converted.date() < moment.date():
            out_str += " (previous day)"
        in_str = moment.strftime("%I:%M %p").lstrip("0")

        embed = discord.Embed(
            title="꒰ა ✦ ໒꒱ time conversion",
            description=(
                f"**{in_str} {src[1]}** → **{out_str} {dst[1]}**"
            ),
            color=get_seasonal_color(),
        )
        embed.set_footer(text=f"source date: {moment.strftime('%a, %b %d %Y')} ♡")
        await interaction.response.send_message(embed=embed)

    # ─── /time set ───────────────────────────────────────────────

    @time_group.command(
        name="set", description="Set your timezone (for /time for)"
    )
    @app_commands.describe(
        timezone="Your timezone — EST, PST, UTC+3, America/New_York…"
    )
    async def time_set(self, interaction: discord.Interaction,
                       timezone: str):
        self.bot.increment_command('time_set')
        resolved = resolve_timezone(timezone)
        if resolved is None:
            return await interaction.response.send_message(
                "couldn't find that timezone — try `America/New_York`, "
                "`Europe/London`, `Asia/Tokyo`, `EST`, or `UTC+3`.",
                ephemeral=True,
            )
        tz, display = resolved

        # Store the canonical name (aliases keep their short form —
        # resolve_timezone understands them on every read).
        stored = timezone.strip()
        try:
            profile = await asyncio.to_thread(
                get_user_profile, interaction.user.id
            )
        except Exception:
            profile = {}
        profile = dict(profile or {})
        profile["timezone"] = stored
        profile["updated_at"] = datetime.utcnow().isoformat()
        try:
            await asyncio.to_thread(
                set_user_profile, interaction.user.id, profile
            )
        except Exception as e:
            log.error(f"[time] profile save failed: {e}")
            return await interaction.response.send_message(
                "couldn't save that — try again.", ephemeral=True
            )

        now_str = datetime.now(tz).strftime("%I:%M %p").lstrip("0")
        await interaction.response.send_message(
            f"✅ your timezone has been set to **{display}** "
            f"(current time: {now_str}) ♡"
        )


def _diff_string(diff: timedelta, viewer_label: str) -> str:
    """'3h ahead of you' / '2h 30m behind utc' / 'same time as you'."""
    minutes = int(round(diff.total_seconds() / 60))
    if minutes == 0:
        return "same time as you" if viewer_label != "utc" else "same as utc"
    if minutes > 0:
        return f"{format_offset_delta(diff)} ahead of {viewer_label}"
    return f"{format_offset_delta(-diff)} behind {viewer_label}"


async def setup(bot):
    await bot.add_cog(TimezoneCog(bot))
