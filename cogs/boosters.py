"""cogs/boosters.py — PHASE O — complete server booster system.

What happens when someone boosts:
  on_member_update (this cog) sees the authoritative boost transition
      NEW BOOST:   before.premium_since is None  AND after.premium_since is not None
      STOPPED:     before.premium_since is not None AND after.premium_since is None
  (discord.py's Member.premium_subscriber is literally
  ``premium_since is not None`` — same signal; premium_since is used here
  because it is the primitive both derive from and it survives every
  discord.py 2.x release. Role adds, nickname changes and Discord system
  messages are NEVER trusted as the signal.)

On a NEW boost (all failure-isolated — one failing piece never blocks
the others):
  1. public announcement   — enabled + channel set; text / embed /
     hybrid modes, template variables, image, footer, color, thumbnail
  2. booster role grant    — enabled + auto_role + valid non-managed
     role below aurelia's top role (hierarchy-checked, failures logged,
     never silent, never above the bot, no Administrator required)
  3. milestone check       — enabled + milestone_enabled; announces the
     HIGHEST newly-crossed threshold only once. milestone_last is the
     persisted high-water mark, so restarts and boost churn (drop below
     a threshold, climb back) can never re-post it.
  4. private log entry     — to the guild's existing log channel
     (log_settings), never a public goodbye

On an UNBOOST (no public message — we never shame anyone for stopping):
  * booster role REMOVAL is cleanup: remove_role_on_unboost + valid role
    + member currently has it. It still runs when announcements are
    disabled, so turning the module off can't leave orphaned roles.
  * private log entry only
  * the first_boost achievement (cogs/achievements.py) is PERMANENT —
    this cog never touches it. Both cogs independently observe
    on_member_update; achievements owns only "supporter", boosters owns
    announcements/roles/milestones. No overlap.

Duplicate-event protection (PART 9):
  * the premium_since transition check itself ignores unrelated member
    updates (nickname, roles, timeouts) — including the echo of aurelia
    adding the configured booster role
  * a short-lived idempotency cache (guild_id, user_id, event_type)
    with a 30s window absorbs Discord double-sending the same member
    update; nothing personal is persisted
  * milestones are persisted (booster_settings.milestone_last), so a
    reconnect/restart cannot repost them

/toggledms (PART 13): governs passive PRIVATE DMs only. The booster
announcement is a PUBLIC channel message — it is NOT gated by it, and
this cog sends no DMs at all.

Commands (ONE root group, Manage Guild):
  /boosters config <setting> [value] [channel] [role]
  /boosters show
  /boosters test   — renders the announcement with YOU as the preview
                     member. Never fakes premium_since, never awards
                     first_boost, never changes the boost count, never
                     touches roles.
  /boosters reset  — confirmation button; booster settings ONLY

DB: utils/db.py booster_settings (Supabase + JSON fallback, defaults
filled, ISO-8601 updated_at at the TIMESTAMPTZ boundary).
"""
import logging
import re
import time as _time
from typing import Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils import db as _db
from utils.db import (
    get_booster_settings_async,
    set_booster_settings_async,
    BOOSTER_DEFAULT_MESSAGE,
    BOOSTER_DEFAULT_MILESTONE_MESSAGE,
    BOOSTER_DEFAULT_MILESTONE_COUNTS,
    BOOSTER_DEFAULT_FOOTER,
)

logger = logging.getLogger('cyn.boosters')

# Veloura aesthetic (same palette family as welcome.py)
COLOR_PINK = 0xFFC0CB
COLOR_CONFIG = 0x1a1a2e
DEFAULT_BOOSTER_COLOR = "#FFC0CB"
FOOTER = "✩ ━━ aurelia ༉‧₊˚. ღ"

VALID_EMBED_MODES = ("text", "embed", "hybrid")
VALID_THUMBNAIL_MODES = ("member", "server", "none")

# PART 9 — idempotency window for duplicate member updates
EVENT_DEDUP_WINDOW = 30  # seconds

# Milestone threshold sanity bounds (config validation)
MILESTONE_MIN = 1
MILESTONE_MAX = 1000
MILESTONE_MAX_COUNT = 25


def parse_hex_color(value) -> Optional[int]:
    """Parse '#FFC0CB', '0xFFC0CB', 'FFC0CB' or short 'FCC' hex into an
    int. None when invalid. (Same contract as welcome.py's helper.)"""
    if value is None:
        return None
    s = str(value).strip().lstrip('#')
    if s.lower().startswith('0x'):
        s = s[2:]
    if len(s) == 3:
        s = ''.join(ch * 2 for ch in s)
    if len(s) != 6:
        return None
    try:
        return int(s, 16)
    except ValueError:
        return None


def parse_milestone_counts(raw) -> Optional[list]:
    """Parse a milestone threshold spec ('2, 7, 14' or a list) into a
    sorted unique list of sane ints. None when invalid."""
    items = None
    if isinstance(raw, str):
        items = [p.strip() for p in raw.replace(";", ",").split(",")]
    elif isinstance(raw, (list, tuple)):
        items = [str(p).strip() for p in raw]
    if items is None:
        return None
    out = set()
    for item in items:
        if not item:
            continue
        try:
            n = int(item)
        except ValueError:
            return None
        if not (MILESTONE_MIN <= n <= MILESTONE_MAX):
            return None
        out.add(n)
    if not out or len(out) > MILESTONE_MAX_COUNT:
        return None
    return sorted(out)


class Boosters(commands.Cog):
    """Complete server booster system — announcements, roles, milestones."""

    def __init__(self, bot):
        self.bot = bot
        # PART 9 — {(guild_id, user_id, event_type): monotonic ts}
        self._recent_events: dict[tuple, float] = {}

    # ─── Config access ────────────────────────────────────────────

    async def get_config(self, guild_id) -> dict:
        """Current booster settings (defaults filled). Public so the
        dashboard action worker can render test announcements."""
        return await get_booster_settings_async(guild_id)

    def _get_channel(self, guild, config):
        cid = config.get("channel_id")
        if not cid:
            return None
        try:
            return guild.get_channel(int(cid))
        except (TypeError, ValueError):
            return None

    # ─── PART 3 — safe variable replacement (never .format()) ──────

    def _replace_variables(self, template: str, member, guild) -> str:
        """Replace every booster template tag with .replace() only —
        unbalanced braces / user content can never crash rendering.

          {user}               member mention
          {user.name}          member username
          {user.display_name}  server display name
          {user.id}            member id
          {user.avatar}        display avatar url
          {server}             guild name
          {server.id}          guild id
          {server.icon}        guild icon url (empty string when none)
          {boostcount}         guild.premium_subscription_count
          {boostlevel}         guild.premium_tier
        """
        if not template:
            return ""
        text = str(template)
        # literal \n → real newline
        text = text.replace("\\n", "\n")
        # longest tags first so {user} can't eat {user.name}'s prefix
        text = text.replace(
            "{user.display_name}",
            str(getattr(member, "display_name", "") or ""))
        text = text.replace("{user.name}", str(getattr(member, "name", "")))
        text = text.replace("{user.id}", str(getattr(member, "id", "")))
        avatar = getattr(member, "display_avatar", None)
        text = text.replace(
            "{user.avatar}", str(avatar.url) if avatar else "")
        text = text.replace("{user}", getattr(member, "mention", ""))
        text = text.replace("{server.id}", str(getattr(guild, "id", "")))
        icon = getattr(guild, "icon", None)
        text = text.replace(
            "{server.icon}", str(icon.url) if icon else "")
        text = text.replace("{server}", str(getattr(guild, "name", "")))
        text = text.replace(
            "{boostcount}",
            str(getattr(guild, "premium_subscription_count", 0) or 0))
        text = text.replace(
            "{boostlevel}", str(getattr(guild, "premium_tier", 0) or 0))
        return text

    # ─── PART 5 — embed building + render modes ────────────────────

    def _get_color(self, config) -> int:
        parsed = parse_hex_color(config.get("color"))
        return parsed if parsed is not None else COLOR_PINK

    def _build_embed(self, text: str, member, guild, config) -> discord.Embed:
        """Booster embed: configured color, thumbnail (member avatar /
        server icon / none), optional banner image, footer template
        (default '{boostcount} boosts ♡')."""
        embed = discord.Embed(description=text[:4096], color=self._get_color(config))

        thumb_mode = str(config.get("thumbnail_mode") or "member").strip().lower()
        thumb_url = None
        avatar = getattr(member, "display_avatar", None)
        if thumb_mode == "member":
            thumb_url = avatar.url if avatar else None
        elif thumb_mode == "server":
            icon = getattr(guild, "icon", None)
            thumb_url = (icon.url if icon
                         else (avatar.url if avatar else None))
        # "none" (or anything unknown) → no thumbnail
        if thumb_url:
            embed.set_thumbnail(url=str(thumb_url))

        footer_tpl = config.get("footer")
        if footer_tpl is None:
            footer_tpl = BOOSTER_DEFAULT_FOOTER
        footer_text = self._replace_variables(str(footer_tpl), member, guild)
        footer_text = footer_text.replace("\\n", " ").strip()
        if footer_text:
            embed.set_footer(text=footer_text[:2048])

        image_url = config.get("image_url")
        if image_url:
            embed.set_image(url=str(image_url)[:500])
        return embed

    def _render_payload(self, config: dict, member, guild,
                        template: Optional[str] = None
                        ) -> Tuple[Optional[str], Optional[discord.Embed]]:
        """Render the announcement into a Discord payload WITHOUT
        sending anything. Pure function — this is what tests exercise.

        modes:
          text   → (content, None)
          embed  → (None, embed)   (default)
          hybrid → split at the FIRST '---': before = plain content,
                   after = embed description. No separator → the whole
                   template becomes the embed (never duplicated)."""
        tpl = template if template is not None else (
            config.get("message") or BOOSTER_DEFAULT_MESSAGE)
        text = self._replace_variables(tpl, member, guild)
        mode = str(config.get("embed_mode") or "embed").strip().lower()

        if mode == "text":
            return (text[:2000] or None), None
        if mode == "hybrid":
            if "---" in text:
                parts = text.split("---", 1)
                content = parts[0].strip()[:2000] or None
                embed_text = parts[1].strip()
            else:
                content = None
                embed_text = text
            return content, self._build_embed(embed_text, member, guild, config)
        return None, self._build_embed(text, member, guild, config)

    async def _send_announcement(self, channel, config, member, guild,
                                 template: Optional[str] = None) -> bool:
        """Send the rendered announcement. Returns True on success;
        every failure mode is logged, never raised."""
        try:
            content, embed = self._render_payload(
                config, member, guild, template=template)
            if content is None and embed is None:
                logger.warning(
                    "[boosters] rendered announcement was empty — skipped")
                return False
            await channel.send(content=content, embed=embed)
            return True
        except discord.Forbidden:
            logger.warning(
                f"[boosters] missing permissions to send in "
                f"#{getattr(channel, 'name', channel)}")
        except discord.HTTPException as e:
            logger.error(f"[boosters] announcement send failed: {e}")
        except Exception as e:
            logger.error(f"[boosters] announcement error: {e}")
        return False

    # ─── PART 6 — booster role management (hierarchy-safe) ─────────

    def _resolve_booster_role(self, guild, config) -> Tuple[Optional[object], Optional[str]]:
        """(role, None) when the configured role is usable, else
        (None, human-readable reason). Rejects missing roles, managed /
        integration roles (Discord's native Server Booster role),
        @everyone, roles at/above aurelia's top role, and missing
        manage-roles permission."""
        rid = config.get("booster_role_id")
        if not rid:
            return None, "no booster role configured"
        try:
            role = guild.get_role(int(rid))
        except (TypeError, ValueError):
            return None, f"invalid booster role id '{rid}'"
        if role is None:
            return None, f"booster role {rid} no longer exists"
        if getattr(role, "managed", False):
            return None, (f"booster role '{getattr(role, 'name', rid)}' is "
                          "managed by an integration — aurelia will not "
                          "touch it")
        if role.id == getattr(guild, "id", None):
            return None, "@everyone is not a valid booster role"
        me = getattr(guild, "me", None)
        if me is None:
            return None, "aurelia's member object unavailable"
        perms = getattr(me, "guild_permissions", None)
        if not getattr(perms, "manage_roles", False):
            return None, "aurelia lacks the Manage Roles permission"
        top = getattr(getattr(me, "top_role", None), "position", 0)
        if role.position >= top:
            return None, (f"booster role '{getattr(role, 'name', rid)}' is "
                          "at/above aurelia's top role — cannot manage it")
        return role, None

    async def _assign_booster_role(self, member, guild, config) -> str:
        """Grant the configured booster role. Returns a short result
        string for the log entry. Never raises."""
        role, reason = self._resolve_booster_role(guild, config)
        if role is None:
            return f"skipped ({reason})" if config.get("booster_role_id") else "off"
        try:
            await member.add_roles(
                role, reason="aurelia booster system — boost started")
            return f"granted '{role.name}'"
        except discord.Forbidden:
            logger.warning(
                f"[boosters] hierarchy/permission failure granting "
                f"'{role.name}' to {member.id} in {guild.id}")
            return f"failed (forbidden) granting '{role.name}'"
        except discord.HTTPException as e:
            logger.error(f"[boosters] role grant http error: {e}")
            return f"failed (http) granting '{role.name}'"
        except Exception as e:
            logger.error(f"[boosters] role grant error: {e}")
            return "failed (unexpected)"

    async def _remove_booster_role(self, member, guild, config) -> str:
        """Remove the configured booster role from a member who stopped
        boosting. Returns a short result string. Never raises."""
        role, reason = self._resolve_booster_role(guild, config)
        if role is None:
            if config.get("booster_role_id"):
                return f"skipped ({reason})"
            return "off"
        if role not in getattr(member, "roles", []):
            return "not held"
        try:
            await member.remove_roles(
                role, reason="aurelia booster system — boost ended")
            return f"removed '{role.name}'"
        except discord.Forbidden:
            logger.warning(
                f"[boosters] hierarchy/permission failure removing "
                f"'{role.name}' from {member.id} in {guild.id}")
            return f"failed (forbidden) removing '{role.name}'"
        except discord.HTTPException as e:
            logger.error(f"[boosters] role removal http error: {e}")
            return f"failed (http) removing '{role.name}'"
        except Exception as e:
            logger.error(f"[boosters] role removal error: {e}")
            return "failed (unexpected)"

    # ─── PART 8 — milestones (persisted, once, churn-safe) ──────────

    async def _check_milestone(self, guild, config, member) -> Optional[str]:
        """Announce the highest milestone threshold newly crossed
        upward, at most once per threshold EVER (milestone_last is the
        persisted high-water mark). Returns a result string for the log
        entry, or None when nothing was announced."""
        if not config.get("enabled"):
            return None
        if not config.get("milestone_enabled"):
            return None
        channel = self._get_channel(guild, config)
        if channel is None:
            return None
        try:
            count = int(getattr(guild, "premium_subscription_count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        last = int(config.get("milestone_last") or 0)
        thresholds = [t for t in (config.get("milestone_counts") or [])
                      if isinstance(t, int)]
        # thresholds crossed strictly ABOVE the high-water mark and
        # at/below the current count — churn back below a threshold
        # never re-lists it because `last` never decreases
        crossed = [t for t in thresholds if last < t <= count]
        if not crossed:
            return None
        target = max(crossed)  # one announcement per event: the highest
        template = config.get("milestone_message") or \
            BOOSTER_DEFAULT_MILESTONE_MESSAGE
        ok = await self._send_announcement(
            channel, config, member, guild, template=template)
        if not ok:
            # only mark on success — a failed send retries on the next
            # boost event instead of silently losing the milestone
            return "milestone send failed (will retry on next boost)"
        try:
            await set_booster_settings_async(
                guild.id, {"milestone_last": target})
        except Exception as e:
            logger.error(f"[boosters] milestone state save failed: {e}")
        return f"milestone {target} announced"

    # ─── PART 12 — private event logging (existing log channel) ─────

    async def _log_boost_event(self, guild, member, event: str,
                               count: int, role_result: str,
                               announcement_result: str):
        """Send a private boost/unboost log entry to the guild's
        EXISTING logging channel (log_settings). No new log channel is
        required or created; failures are silent (logging must never
        break the feature)."""
        try:
            log_cfg = await _db.get_guild_setting_async(guild.id, "log_settings")
            if not isinstance(log_cfg, dict) or not log_cfg.get("enabled", True):
                return
            cid = log_cfg.get("channel_id")
            if not cid:
                return
            channel = guild.get_channel(int(cid))
            if channel is None:
                return
            is_boost = (event == "boost")
            embed = discord.Embed(
                title="💜 Boost Started" if is_boost else "▫ Boost Ended",
                color=0xFFC0CB if is_boost else 0x949BA4,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="member",
                value=f"{getattr(member, 'mention', '')} "
                      f"(`{getattr(member, 'id', '?')}`)",
                inline=False,
            )
            embed.add_field(
                name="boost count", value=str(count), inline=True)
            embed.add_field(
                name="boost level",
                value=str(getattr(guild, "premium_tier", 0) or 0),
                inline=True,
            )
            embed.add_field(name="role", value=role_result, inline=False)
            if is_boost:
                embed.add_field(
                    name="announcement", value=announcement_result, inline=False)
            embed.set_footer(text="aurelia logs · booster system")
            await channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"[boosters] boost log entry failed: {e}")

    # ─── PART 9 — idempotency cache ─────────────────────────────────

    def _is_duplicate(self, guild_id, user_id, event_type: str) -> bool:
        """True when (guild, user, event) was seen inside the dedup
        window — Discord sometimes delivers the same member update
        twice; the cache absorbs it without persisting anything."""
        now = _time.monotonic()
        # prune expired entries first (bounded memory)
        for key in list(self._recent_events.keys()):
            if now - self._recent_events[key] > EVENT_DEDUP_WINDOW:
                self._recent_events.pop(key, None)
        key = (guild_id, user_id, event_type)
        if key in self._recent_events:
            return True
        self._recent_events[key] = now
        return False

    # ─── Listener: the authoritative boost transition ───────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member,
                               after: discord.Member):
        if getattr(after, "bot", False):
            return
        guild = after.guild
        if guild is None:
            return

        before_premium = getattr(before, "premium_since", None)
        after_premium = getattr(after, "premium_since", None)

        if before_premium is None and after_premium is not None:
            event = "boost"
        elif before_premium is not None and after_premium is None:
            event = "unboost"
        else:
            # unrelated member update (nickname, roles, pending flags,
            # timeout, our own role-assignment echo, booster→booster
            # date change) — NOT a boost transition
            return

        if self._is_duplicate(guild.id, after.id, event):
            logger.debug(
                f"[boosters] duplicate {event} update for {after.id} "
                f"in {guild.id} — ignored")
            return

        try:
            config = await self.get_config(guild.id)
        except Exception as e:
            logger.error(f"[boosters] settings load failed: {e}")
            return

        try:
            count = int(getattr(guild, "premium_subscription_count", 0) or 0)
        except (TypeError, ValueError):
            count = 0

        if event == "boost":
            await self._handle_new_boost(guild, after, config, count)
        else:
            await self._handle_unboost(guild, after, config, count)

    async def _handle_new_boost(self, guild, member, config, count):
        """PART 1/5/6/8/12 — announcement + role + milestone + log.
        Every step is failure-isolated."""
        # 1. public announcement (enabled + channel)
        announcement_result = "off"
        if config.get("enabled"):
            channel = self._get_channel(guild, config)
            if channel is None:
                announcement_result = (
                    "skipped (channel missing/inaccessible)" if
                    config.get("channel_id") else "skipped (no channel set)")
                if config.get("channel_id"):
                    logger.warning(
                        f"[boosters] announcement channel "
                        f"{config.get('channel_id')} not found in "
                        f"{guild.id}")
            else:
                ok = await self._send_announcement(
                    channel, config, member, guild)
                announcement_result = (
                    f"sent to #{channel.name}" if ok else "send failed")

        # 2. booster role grant (enabled + auto_role)
        if config.get("enabled") and config.get("auto_role"):
            role_result = await self._assign_booster_role(member, guild, config)
        elif config.get("auto_role") and not config.get("enabled"):
            role_result = "skipped (module disabled)"
        else:
            role_result = "off"

        # 3. milestone check (persisted, once)
        try:
            milestone_result = await self._check_milestone(guild, config, member)
        except Exception as e:
            logger.error(f"[boosters] milestone check failed: {e}")
            milestone_result = None

        # 4. private log entry
        log_announcement = announcement_result
        if milestone_result:
            log_announcement = f"{announcement_result} · {milestone_result}"
        await self._log_boost_event(
            guild, member, "boost", count, role_result, log_announcement)

    async def _handle_unboost(self, guild, member, config, count):
        """PART 7 — quiet unboost: role cleanup + private log ONLY.
        There is deliberately no public unboost message."""
        # Role removal is cleanup: it runs on remove_role_on_unboost
        # even when announcements are disabled, so disabling the module
        # can never leave orphaned booster roles on ex-boosters.
        if config.get("remove_role_on_unboost"):
            role_result = await self._remove_booster_role(member, guild, config)
        else:
            role_result = "kept (remove-on-unboost off)"
        await self._log_boost_event(
            guild, member, "unboost", count, role_result, "—")

    # ═════════════════════════ COMMANDS ═══════════════════════════

    boosters = app_commands.Group(
        name="boosters",
        description="Server booster announcements, roles & milestones",
    )

    async def _err(self, itx: discord.Interaction, msg: str):
        await itx.response.send_message(msg, ephemeral=True)

    async def _save_settings(self, guild, payload: dict):
        """Merge + persist booster settings (single write path for the
        whole cog)."""
        await set_booster_settings_async(guild.id, payload)

    def _baseline_milestones(self, config: dict, guild) -> dict:
        """When milestones start being watched (module enable or
        milestone enable), pin the high-water mark to the CURRENT boost
        count so thresholds the guild already passed historically are
        never announced retroactively."""
        try:
            count = int(getattr(guild, "premium_subscription_count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        if int(config.get("milestone_last") or 0) < count:
            return {"milestone_last": count}
        return {}

    # ─── /boosters config ───────────────────────────────────────────

    @boosters.command(name="config", description="Configure any booster setting")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        setting="Which setting to change",
        value="The new value — text, mode, hex color, URL, on/off, or milestone list",
        channel="Target channel (only for the channel setting)",
        role="Booster role (only for the booster_role setting)",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Announcement Channel", value="channel"),
        app_commands.Choice(name="Booster Message", value="message"),
        app_commands.Choice(name="Embed Mode (text/embed/hybrid)", value="embed_mode"),
        app_commands.Choice(name="Embed Color", value="color"),
        app_commands.Choice(name="Banner Image URL", value="image"),
        app_commands.Choice(name="Thumbnail (member/server/none)", value="thumbnail"),
        app_commands.Choice(name="Footer Text", value="footer"),
        app_commands.Choice(name="Booster Role", value="booster_role"),
        app_commands.Choice(name="Auto-Role On/Off", value="auto_role"),
        app_commands.Choice(name="Remove Role On Unboost", value="remove_role_on_unboost"),
        app_commands.Choice(name="Milestones On/Off", value="milestone_toggle"),
        app_commands.Choice(name="Milestone Thresholds (e.g. 2,7,14,25)", value="milestones"),
        app_commands.Choice(name="Milestone Message", value="milestone_message"),
        app_commands.Choice(name="Booster Announcements On/Off", value="toggle"),
    ])
    async def boosters_config(self, interaction: discord.Interaction,
                              setting: app_commands.Choice[str],
                              value: Optional[str] = None,
                              channel: Optional[discord.TextChannel] = None,
                              role: Optional[discord.Role] = None):
        self.bot.increment_command('boosters_config')
        if not interaction.guild:
            return await self._err(interaction, "this command only works in servers.")
        handlers = {
            "channel": self._set_channel,
            "message": self._set_message,
            "embed_mode": self._set_embed_mode,
            "color": self._set_color,
            "image": self._set_image,
            "thumbnail": self._set_thumbnail,
            "footer": self._set_footer,
            "booster_role": self._set_booster_role,
            "auto_role": self._set_auto_role,
            "remove_role_on_unboost": self._set_remove_role,
            "milestone_toggle": self._set_milestone_toggle,
            "milestones": self._set_milestones,
            "milestone_message": self._set_milestone_message,
            "toggle": self._set_toggle,
        }
        handler = handlers.get(setting.value)
        if handler is None:
            return await self._err(interaction, "❌ unknown setting.")
        await handler(interaction, value, channel, role)

    # ---- setting handlers ──────────────────────────────────────────

    async def _set_channel(self, interaction, value, channel, role):
        guild = interaction.guild
        ch = channel
        if ch is None and value:
            v = value.strip()
            cid = None
            m = re.match(r'^<#(\d+)>$', v)
            if m:
                cid = int(m.group(1))
            elif v.isdigit() and len(v) >= 15:
                cid = int(v)
            if cid is not None:
                ch = guild.get_channel(cid)
        if ch is None:
            return await self._err(
                interaction,
                "❌ mention a channel (use the `channel` option) or pass "
                "its ID / mention as `value`.",
            )
        if not isinstance(ch, discord.TextChannel):
            return await self._err(
                interaction, "❌ booster announcements need a text channel.")
        config = await self.get_config(guild.id)
        payload = {"channel_id": str(ch.id), "enabled": True}
        payload.update(self._baseline_milestones(config, guild))
        await self._save_settings(guild, payload)
        await interaction.response.send_message(
            f"✅ booster channel set to {ch.mention} — booster "
            f"announcements **enabled**."
        )

    async def _set_message(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the message as `value` — tags: `{user}` "
                "`{server}` `{boostcount}` (full list in `/boosters show`)."
            )
        guild = interaction.guild
        config = await self.get_config(guild.id)
        if value.strip().lower() == "reset":
            await self._save_settings(
                guild, {"message": BOOSTER_DEFAULT_MESSAGE})
            return await interaction.response.send_message(
                "✅ booster message reset to the default template."
            )
        await self._save_settings(
            guild, {"message": value[:4000]})
        await interaction.response.send_message(
            "✅ booster message updated."
        )

    async def _set_embed_mode(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the mode as `value`: `text`, `embed`, or `hybrid`.",
            )
        mode = value.strip().lower()
        if mode not in VALID_EMBED_MODES:
            return await self._err(
                interaction, "❌ mode must be `text`, `embed`, or `hybrid`.")
        await self._save_settings(interaction.guild, {"embed_mode": mode})
        extra = (
            " — everything before `---` is sent as plain text, everything "
            "after it becomes the embed."
            if mode == "hybrid" else ""
        )
        await interaction.response.send_message(
            f"✅ booster embed mode set to **{mode}**{extra}"
        )

    async def _set_color(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide a hex color as `value` (e.g. `#FFC0CB`) or `reset`.",
            )
        guild = interaction.guild
        if value.strip().lower() in ("reset", "default"):
            await self._save_settings(guild, {"color": DEFAULT_BOOSTER_COLOR})
            return await interaction.response.send_message(
                f"✅ booster color reset to default **{DEFAULT_BOOSTER_COLOR}**."
            )
        color_int = parse_hex_color(value)
        if color_int is None:
            return await self._err(
                interaction,
                "❌ invalid color. use hex like `#FFC0CB` or `reset`.",
            )
        normalized = "#" + value.strip().lstrip('#').upper()
        await self._save_settings(guild, {"color": normalized})
        preview = discord.Embed(
            description=f"✅ booster color set to **{normalized}**",
            color=color_int,
        )
        preview.set_footer(text=FOOTER)
        await interaction.response.send_message(embed=preview)

    async def _set_image(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide an image URL as `value`, or `reset` to remove the banner.",
            )
        guild = interaction.guild
        if value.strip().lower() in ("reset", "off", "none"):
            await self._save_settings(guild, {"image_url": None})
            return await interaction.response.send_message(
                "✅ booster banner image removed."
            )
        if not value.startswith(("http://", "https://")):
            return await self._err(
                interaction,
                "❌ image URL must start with `http://` or `https://`.",
            )
        await self._save_settings(guild, {"image_url": value[:500]})
        await interaction.response.send_message(
            "✅ booster banner image updated."
        )

    async def _set_thumbnail(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the mode as `value`: `member`, `server`, or `none`.",
            )
        mode = value.strip().lower()
        if mode not in VALID_THUMBNAIL_MODES:
            return await self._err(
                interaction,
                "❌ thumbnail must be `member`, `server`, or `none`.",
            )
        await self._save_settings(
            interaction.guild, {"thumbnail_mode": mode})
        await interaction.response.send_message(
            f"✅ booster thumbnail set to **{mode}**."
        )

    async def _set_footer(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the footer as `value` (tags supported), `reset` "
                "for the default, or `none` to remove it.",
            )
        guild = interaction.guild
        if value.strip().lower() in ("reset", "default"):
            await self._save_settings(
                guild, {"footer": BOOSTER_DEFAULT_FOOTER})
            return await interaction.response.send_message(
                f"✅ footer reset to default: **{BOOSTER_DEFAULT_FOOTER}**"
            )
        if value.strip().lower() in ("none", "off", "empty"):
            await self._save_settings(guild, {"footer": ""})
            return await interaction.response.send_message(
                "✅ footer removed."
            )
        await self._save_settings(guild, {"footer": value[:2000]})
        rendered = self._replace_variables(
            value, interaction.user, interaction.guild)
        await interaction.response.send_message(
            f"✅ footer updated — preview: **{rendered[:150]}**"
        )

    async def _set_booster_role(self, interaction, value, channel, role):
        guild = interaction.guild
        target = role
        if target is None and value:
            v = value.strip()
            if v.startswith("<@&") and v.endswith(">"):
                v = v[3:-1]
            if v.isdigit():
                target = guild.get_role(int(v))
        if target is None:
            return await self._err(
                interaction,
                "❌ mention a role (use the `role` option) or pass its "
                "ID / mention as `value`.",
            )
        # PART 6 — reject managed/integration roles (Discord's native
        # Server Booster role is managed; aurelia must never touch it),
        # @everyone, and roles at/above the bot's top role.
        if target.managed:
            return await self._err(
                interaction,
                f"❌ **{target.name}** is managed by an integration "
                "(this includes Discord's native Server Booster role) — "
                "aurelia can't assign it. pick a normal role.",
            )
        if target.is_default():
            return await self._err(
                interaction, "❌ @everyone is not a valid booster role.")
        me = guild.me
        if me and target.position >= me.top_role.position:
            return await self._err(
                interaction,
                f"❌ **{target.name}** is at/above aurelia's top role — "
                "move it below aurelia in the role list first.",
            )
        await self._save_settings(
            guild, {"booster_role_id": str(target.id)})
        await interaction.response.send_message(
            f"✅ booster role set to {target.mention}. turn automatic "
            "assignment on with `/boosters config setting:auto_role value:on`."
        )

    async def _set_auto_role(self, interaction, value, channel, role):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(
                interaction, "❌ provide `on` or `off` as `value`.")
        state = value.strip().lower()
        config = await self.get_config(interaction.guild.id)
        payload = {"auto_role": state == "on"}
        if state == "on" and not config.get("booster_role_id"):
            await self._save_settings(interaction.guild, payload)
            return await interaction.response.send_message(
                "✅ auto-role **on** — ⚠️ no booster role set yet, use "
                "`/boosters config setting:booster_role role:@booster` first."
            )
        await self._save_settings(interaction.guild, payload)
        await interaction.response.send_message(
            f"✅ automatic booster role **{state}**."
        )

    async def _set_remove_role(self, interaction, value, channel, role):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(
                interaction, "❌ provide `on` or `off` as `value`.")
        state = value.strip().lower()
        await self._save_settings(
            interaction.guild, {"remove_role_on_unboost": state == "on"})
        await interaction.response.send_message(
            f"✅ remove role on unboost **{state}**."
        )

    async def _set_milestone_toggle(self, interaction, value, channel, role):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(
                interaction, "❌ provide `on` or `off` as `value`.")
        guild = interaction.guild
        state = value.strip().lower()
        config = await self.get_config(guild.id)
        payload = {"milestone_enabled": state == "on"}
        if state == "on":
            # milestones start counting from NOW — already-passed
            # thresholds are never announced retroactively
            payload.update(self._baseline_milestones(config, guild))
        await self._save_settings(guild, payload)
        warn = ""
        if state == "on" and not config.get("channel_id"):
            warn = ("\n⚠️ no announcement channel set — use "
                    "`/boosters config setting:channel` first.")
        await interaction.response.send_message(
            f"✅ boost milestones **{state}**.{warn}"
        )

    async def _set_milestones(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the thresholds as `value`, e.g. `2, 7, 14, 25` "
                "— or `reset` for the defaults (2, 7, 14).",
            )
        guild = interaction.guild
        if value.strip().lower() == "reset":
            await self._save_settings(
                guild,
                {"milestone_counts": list(BOOSTER_DEFAULT_MILESTONE_COUNTS)})
            return await interaction.response.send_message(
                "✅ milestone thresholds reset to **2, 7, 14**."
            )
        counts = parse_milestone_counts(value)
        if counts is None:
            return await self._err(
                interaction,
                "❌ thresholds must be comma-separated whole numbers "
                f"between {MILESTONE_MIN} and {MILESTONE_MAX} (max "
                f"{MILESTONE_MAX_COUNT} of them).",
            )
        await self._save_settings(guild, {"milestone_counts": counts})
        await interaction.response.send_message(
            f"✅ milestone thresholds set to **{', '.join(map(str, counts))}**."
        )

    async def _set_milestone_message(self, interaction, value, channel, role):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the message as `value` (tags: `{server}` "
                "`{boostcount}`), or `reset` for the default.",
            )
        guild = interaction.guild
        if value.strip().lower() == "reset":
            await self._save_settings(
                guild, {"milestone_message": BOOSTER_DEFAULT_MILESTONE_MESSAGE})
            return await interaction.response.send_message(
                "✅ milestone message reset to the default template."
            )
        await self._save_settings(
            guild, {"milestone_message": value[:4000]})
        await interaction.response.send_message(
            "✅ milestone message updated."
        )

    async def _set_toggle(self, interaction, value, channel, role):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(
                interaction, "❌ provide `on` or `off` as `value`.")
        guild = interaction.guild
        state = value.strip().lower()
        config = await self.get_config(guild.id)
        payload = {"enabled": state == "on"}
        if state == "on":
            payload.update(self._baseline_milestones(config, guild))
        await self._save_settings(guild, payload)
        warn = ""
        if state == "on" and not config.get("channel_id"):
            warn = ("\n⚠️ no channel set — use "
                    "`/boosters config setting:channel` first.")
        await interaction.response.send_message(
            f"✅ booster announcements **{state}**.{warn}"
        )

    # ─── /boosters show ─────────────────────────────────────────────

    @boosters.command(name="show", description="Overview of the booster config")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def boosters_show(self, interaction: discord.Interaction):
        self.bot.increment_command('boosters_show')
        if not interaction.guild:
            return await self._err(interaction, "this command only works in servers.")
        guild = interaction.guild
        config = await self.get_config(guild.id)

        def fmt_channel(eid):
            if not eid:
                return "*not set*"
            try:
                eid_int = int(eid)
            except (ValueError, TypeError):
                return f"`{eid}` (invalid)"
            obj = guild.get_channel(eid_int)
            return obj.mention if obj else f"`{eid}` (not found)"

        def fmt_role(eid):
            if not eid:
                return "*not set*"
            try:
                obj = guild.get_role(int(eid))
            except (ValueError, TypeError):
                obj = None
            return obj.mention if obj else f"`{eid}` (not found)"

        try:
            preview = self._replace_variables(
                config.get("message") or "", interaction.user, guild)
        except Exception:
            preview = config.get("message") or ""
        if not preview:
            preview = "*(empty)*"
        preview = preview[:200] + ("..." if len(preview) > 200 else "")

        boost_count = getattr(guild, "premium_subscription_count", 0) or 0
        boost_level = getattr(guild, "premium_tier", 0) or 0

        embed = discord.Embed(
            title="✩ boosters config",
            color=self._get_color(config),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(
            text="use /boosters test to preview · ✩ ━━ aurelia ༉‧₊˚. ღ")
        embed.add_field(
            name="💜 announcements",
            inline=False,
            value=(
                f"**enabled:** `{config.get('enabled', False)}`\n"
                f"**channel:** {fmt_channel(config.get('channel_id'))}\n"
                f"**mode:** `{config.get('embed_mode', 'embed')}`\n"
                f"**color:** `{config.get('color', DEFAULT_BOOSTER_COLOR)}`\n"
                f"**image:** `{'set' if config.get('image_url') else '—'}`\n"
                f"**thumbnail:** `{config.get('thumbnail_mode', 'member')}`\n"
                f"**footer:** `{(str(config.get('footer')) if config.get('footer') is not None else BOOSTER_DEFAULT_FOOTER)[:60]}`"
            ),
        )
        embed.add_field(
            name="🎭 booster role",
            inline=False,
            value=(
                f"**role:** {fmt_role(config.get('booster_role_id'))}\n"
                f"**auto-role:** `{config.get('auto_role', False)}`\n"
                f"**remove on unboost:** "
                f"`{config.get('remove_role_on_unboost', True)}`"
            ),
        )
        embed.add_field(
            name="✨ milestones",
            inline=False,
            value=(
                f"**enabled:** `{config.get('milestone_enabled', True)}`\n"
                f"**thresholds:** `"
                f"{', '.join(str(t) for t in config.get('milestone_counts', []))}`\n"
                f"**announced up to:** `{config.get('milestone_last', 0)}`"
            ),
        )
        embed.add_field(
            name="🌌 this server",
            inline=False,
            value=f"**boosts:** `{boost_count}` · **level:** `{boost_level}`",
        )
        embed.add_field(
            name="💬 message preview",
            inline=False,
            value=f"```\n{preview}\n```",
        )
        embed.add_field(
            name="🏷️ available tags",
            inline=False,
            value=(
                "```\n"
                "{user} {user.name} {user.display_name} {user.id}\n"
                "{user.avatar} {server} {server.id} {server.icon}\n"
                "{boostcount} {boostlevel}\n"
                "```"
            ),
        )
        await interaction.response.send_message(embed=embed)

    # ─── /boosters test ─────────────────────────────────────────────

    @boosters.command(
        name="test",
        description="Preview the booster announcement (safe — nothing real changes")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def boosters_test(self, interaction: discord.Interaction):
        self.bot.increment_command('boosters_test')
        if not interaction.guild:
            return await self._err(interaction, "this command only works in servers.")
        guild = interaction.guild
        config = await self.get_config(guild.id)
        channel = self._get_channel(guild, config)
        if channel is None:
            return await self._err(
                interaction,
                "❌ booster channel not set. use "
                "`/boosters config setting:channel channel:#boosting` first.",
            )
        # PART 10 — the test renders the REAL configured announcement
        # with the caller as the preview member. It must never:
        #   * fake a premium_since mutation
        #   * award the first_boost achievement
        #   * change the actual boost count
        #   * add/remove the booster role
        #   * touch milestone state
        # _send_announcement does exactly one channel.send — nothing else.
        ok = await self._send_announcement(
            channel, config, interaction.user, guild)
        if ok:
            await interaction.response.send_message(
                f"✅ test booster announcement sent to {channel.mention} "
                "— no achievements were awarded, no roles changed and "
                "the boost count is untouched.",
                ephemeral=True,
            )
        else:
            await self._err(
                interaction,
                "❌ failed to send the test announcement (permissions? "
                "channel still exists?).",
            )

    # ─── /boosters reset ────────────────────────────────────────────

    @boosters.command(
        name="reset", description="Reset ALL booster settings to defaults")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def boosters_reset(self, interaction: discord.Interaction):
        self.bot.increment_command('boosters_reset')
        if not interaction.guild:
            return await self._err(interaction, "this command only works in servers.")
        view = BoosterResetView(interaction.user.id, self)
        await interaction.response.send_message(
            "⚠️ this wipes **every** booster setting for this server "
            "(channel, message, style, role config, milestones) and cannot "
            "be undone. actual Discord roles and earned achievements are "
            "NOT touched.\nare you sure?",
            view=view,
            ephemeral=True,
        )


class BoosterResetView(discord.ui.View):
    """Confirmation buttons for /boosters reset (mirrors welcome)."""

    def __init__(self, author_id: int, cog: "Boosters"):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            try:
                await interaction.response.send_message(
                    "this isn't your reset to confirm.", ephemeral=True
                )
            except Exception:
                pass
            return False
        return True

    @discord.ui.button(label="reset boosters", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        guild = interaction.guild
        try:
            # factory defaults (fresh default dict) + milestone baseline
            # pinned to the current count so old thresholds never replay.
            # The baseline is computed against the RESET state (last=0),
            # not the pre-reset high-water mark.
            payload = {
                "enabled": False,
                "channel_id": None,
                "message": BOOSTER_DEFAULT_MESSAGE,
                "embed_mode": "embed",
                "color": DEFAULT_BOOSTER_COLOR,
                "image_url": None,
                "thumbnail_mode": "member",
                "footer": BOOSTER_DEFAULT_FOOTER,
                "booster_role_id": None,
                "auto_role": False,
                "remove_role_on_unboost": True,
                "milestone_enabled": True,
                "milestone_message": BOOSTER_DEFAULT_MILESTONE_MESSAGE,
                "milestone_counts": list(BOOSTER_DEFAULT_MILESTONE_COUNTS),
                "milestone_last": 0,
            }
            payload.update(
                self.cog._baseline_milestones({"milestone_last": 0}, guild))
            await self.cog._save_settings(guild, payload)
            logger.info(
                f"[boosters] RESET all settings for guild {guild.id}"
            )
        except Exception as e:
            logger.error(f"[boosters] reset failed: {e}")
            await interaction.response.edit_message(
                content="couldn't reset — try again.", view=None
            )
            return
        await interaction.response.edit_message(
            content="✅ every booster setting is back to defaults. configure "
                    "again with `/boosters config setting:channel "
                    "channel:#channel`.",
            view=None,
        )

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        await interaction.response.edit_message(content="cancelled.", view=None)


async def setup(bot):
    await bot.add_cog(Boosters(bot))
