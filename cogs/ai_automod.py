"""
cogs/ai_automod.py — PHASE 4 Feature 2: AI-powered automod escalation ladder.

Turns aurelia from a REACTIVE mod (only acts when asked) into a PROACTIVE
guardian: messages that trip a cheap local heuristic get classified by the
fast Groq model, then escalated through a ladder:

  severity 3          → delete + soft public warning
  severity 4          → delete + formal warning (utils.db warnings store)
  severity 5          → delete + timeout (configurable, default 10m) + mod alert
  repeat offenders    → 3+ violations within 1h auto-escalate one rung

Cost control — the Groq call only fires when a LOCAL heuristic gate trips:
  - excessive caps (≥70% caps, len ≥ 12)
  - long repeated-character runs (spam)
  - very long walls of text (≥ 600 chars)
  - a small seed list of obviously-hostile words
Otherwise the message passes without any API call.

Exemptions: bots, DMs, members with moderate_members, the bot owner, and
messages from other moderators' actions (commands).

Commands (all manage_guild):
  /aiautomod toggle <on|off>
  /aiautomod channel #alerts     — where mod alerts are posted
  /aiautomod timeout <duration>  — escalation timeout length (30m, 1h, 2h,
                                   1d, or a bare number = minutes; 1m–1d)
  /aiautomod status              — current config
"""
import logging
import os
import re
import time
import json as _json
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.ai_handler import call_ai_fast
from utils.db import (
    add_warning_async, get_guild_setting_async, set_guild_setting_async,
)
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.ai_automod')

OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# FIX 3 — timeout duration parsing. The parameter used to be
# app_commands.Range[int, 1, 120], which made Discord itself reject any
# duration string like "30m" / "1h" before the handler even ran. Now the
# option is a free-form string parsed with the SAME pattern the intent
# parser uses (compound number+unit regex), with a bare number meaning
# minutes.
_TIMEOUT_UNITS = {
    's': 1, 'sec': 1, 'secs': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'mins': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hrs': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
}


def parse_timeout_minutes(raw: str) -> Optional[int]:
    """Parse '30m', '5m', '1h', '2h', '1d', '90s', or '10' (minutes)
    into minutes. Returns None if unparseable.

    Uses the same compound number+unit pattern as the intent parser, so
    values like '1h30m' also work. A bare number is MINUTES (not seconds).
    Result is clamped to 1..1440 (1 minute to 1 day)."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s or '-' in s:
        return None
    total_seconds, matched = 0, False
    for num, unit in re.findall(
            r'(\d+)\s*(s|secs?|seconds?|m|mins?|minutes?|h|hrs?|hours?|d|days?)(?![a-z])',
            s):
        total_seconds += int(num) * _TIMEOUT_UNITS[unit]
        matched = True
    if not matched:
        # bare number → minutes
        try:
            return max(1, min(1440, int(s)))
        except ValueError:
            return None
    if total_seconds <= 0:
        return None
    minutes = -(-total_seconds // 60)  # ceil division → whole minutes
    return max(1, min(1440, minutes))


# Local heuristic seed words — deliberately tiny; the model handles nuance.
_HEURISTIC_WORDS = (
    "kill yourself", "kys", "faggot", "n1gger", "nigger", "retard",
    "tranny", "chink", "spic", "wetback", "towelhead",
)

_CLASSIFY_PROMPT = (
    "You are a Discord server moderation classifier. Given a user's message, "
    "rate how severe the toxicity / rule-breaking is.\n\n"
    "Return ONLY valid JSON: {\"severity\": <1-5>, \"reason\": \"<short>\"}\n"
    "1 = harmless (normal chat, jokes, friendly banter)\n"
    "2 = mildly rude but tolerable\n"
    "3 = toxic: insults, harassment, targeted rudeness — worth deleting\n"
    "4 = hateful: slurs, hate speech, threats of harm — delete + warn\n"
    "5 = extreme: threats, doxxing, incitement, spam raids — delete + timeout\n\n"
    "Be careful NOT to flag: reclaimed language, quoting someone to report "
    "them, song lyrics, friendly trash talk, or questions about moderation."
)


class AIAutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {user_id: [epoch floats]}} — violations in the last hour
        self._violations = {}

    # ─── config helpers ──────────────────────────────────────────

    def _default_config(self) -> dict:
        return {
            'enabled': False,
            'alert_channel_id': None,
            'timeout_minutes': 10,
            'min_severity': 3,
        }

    async def _get_config(self, guild_id: int) -> dict:
        cfg = await get_guild_setting_async(guild_id, "ai_automod_settings")
        if not cfg:
            return self._default_config()
        merged = self._default_config()
        merged.update({k: v for k, v in cfg.items() if v is not None})
        return merged

    async def _save_config(self, guild_id: int, cfg: dict):
        await set_guild_setting_async(guild_id, "ai_automod_settings", cfg)

    # ─── heuristic gate (cheap, no API) ──────────────────────────

    @staticmethod
    def _heuristic_trips(content: str) -> bool:
        if not content:
            return False
        lowered = content.lower()
        # seed words
        for word in _HEURISTIC_WORDS:
            if word in lowered:
                return True
        # excessive caps
        letters = [c for c in content if c.isalpha()]
        if len(letters) >= 12:
            caps = sum(1 for c in letters if c.isupper())
            if caps / len(letters) >= 0.70:
                return True
        # long repeated char runs (e.g. "AAAAAAA", "!!!!!!!!")
        if re.search(r'(.)\1{11,}', content):
            return True
        # walls of text
        if len(content) >= 600:
            return True
        return False

    # ─── violation tracking (1h sliding window) ──────────────────

    def _record_violation(self, guild_id: int, user_id: int) -> int:
        now = time.time()
        guild_map = self._violations.setdefault(guild_id, {})
        window = [t for t in guild_map.get(user_id, []) if now - t <= 3600]
        window.append(now)
        guild_map[user_id] = window
        return len(window)

    # ─── listener ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot or not message.guild:
                return
            author = message.author
            if not isinstance(author, discord.Member):
                return
            # exempt mods / admins / owner — they moderate themselves
            if author.guild_permissions.moderate_members:
                return
            if author.id == OWNER_ID:
                return
            # ignore commands (slash invoke replies carry a nonce; prefix !)
            if message.content.startswith(('!', '/', '-')):
                return

            # PART 5.2 — never interfere with other systems' messages:
            # (a) @Aurelia mention → the AI chat pipeline owns it
            if self.bot.user and self.bot.user in message.mentions:
                return
            # (b) guild custom prefix → the prefix cog owns it
            prefix_cog = self.bot.get_cog("Prefix")
            if prefix_cog and hasattr(prefix_cog, "_get_prefix"):
                try:
                    pfx = await prefix_cog._get_prefix(message.guild.id)
                    if pfx and message.content.lower().startswith(
                            str(pfx).lower()):
                        return
                except Exception:
                    pass

            cfg = await self._get_config(message.guild.id)
            if not cfg.get('enabled'):
                return
            if not self._heuristic_trips(message.content):
                return

            # (c) custom commands → the custom-commands cog owns it. Only
            # checked when the heuristic already tripped (rare), so the
            # table lookup is effectively free.
            custom_cog = self.bot.get_cog("CustomCommands")
            if custom_cog:
                try:
                    content = message.content.strip().lower()
                    table = custom_cog._cache.get(message.guild.id)
                    if table:
                        if content in table or any(
                                ' ' in t and content.startswith(t + ' ')
                                for t in table):
                            return
                except Exception:
                    pass

            # ── classify via fast model ──
            raw = await call_ai_fast(
                [
                    {"role": "system", "content": _CLASSIFY_PROMPT},
                    {"role": "user", "content": message.content[:1000]},
                ],
                max_tokens=300,
            )
            severity, reason = self._parse_classification(raw)
            if severity is None:
                return  # unparseable → do nothing (fail-open)

            min_severity = int(cfg.get('min_severity') or 3)
            if severity < min_severity:
                return

            # ── escalation ladder ──
            violations = self._record_violation(message.guild.id, author.id)
            escalated = violations >= 3

            effective = min(5, severity + (1 if escalated else 0))
            await self._enforce(message, author, cfg, effective, reason,
                                escalated)
        except Exception as e:
            logger.error(f"[ai_automod] on_message error: {type(e).__name__}: {e}")

    @staticmethod
    def _parse_classification(raw: str):
        """Parse {'severity': n, 'reason': str} out of a model response."""
        if not raw or "something broke" in raw:
            return None, None
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            return None, None
        try:
            parsed = _json.loads(raw[start:end + 1])
            severity = int(parsed.get("severity", 0))
            if not 1 <= severity <= 5:
                return None, None
            reason = str(parsed.get("reason", "toxic content"))[:150]
            return severity, reason
        except (ValueError, TypeError, KeyError):
            return None, None

    # ─── enforcement ─────────────────────────────────────────────

    async def _enforce(self, message, member, cfg: dict, severity: int,
                       reason: str, escalated: bool):
        guild = message.guild
        mod_alert_channel = None
        alert_cid = cfg.get('alert_channel_id')
        if alert_cid:
            try:
                mod_alert_channel = guild.get_channel(int(alert_cid))
            except (TypeError, ValueError):
                mod_alert_channel = None

        # delete the offending message
        deleted = False
        try:
            await message.delete()
            deleted = True
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        try:
            if severity >= 5:
                # timeout + alert
                # FIX 3 — cap raised from 120m to 1440m (1 day) so durations
                # like '1d' survive a restart without silently shrinking.
                minutes = int(cfg.get('timeout_minutes') or 10)
                minutes = max(1, min(1440, minutes))
                try:
                    from datetime import timedelta as _td
                    await member.timeout(_td(minutes=minutes), reason=f"aurelia ai-automod: {reason}")
                    if message.channel:
                        await message.channel.send(
                            f"{member.mention} has been timed out for {minutes}m — "
                            f"ai-automod: {reason}."
                        )
                except discord.Forbidden:
                    if message.channel:
                        await message.channel.send(
                            f"{member.mention} — flagged ({reason}). "
                            f"mods, i can't timeout them."
                        )
                # record a formal warning too
                await add_warning_async(
                    guild.id, member.id,
                    {
                        'reason': f"[ai-automod sev{severity}] {reason}",
                        'moderator': str(self.bot.user),
                        'mod_id': str(self.bot.user.id),
                        'mod_name': 'aurelia',
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    },
                )
            elif severity == 4:
                # formal warning (persistent)
                await add_warning_async(
                    guild.id, member.id,
                    {
                        'reason': f"[ai-automod sev4] {reason}",
                        'moderator': str(self.bot.user),
                        'mod_id': str(self.bot.user.id),
                        'mod_name': 'aurelia',
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    },
                )
                if message.channel:
                    await message.channel.send(
                        f"{member.mention} — warning logged: {reason}. "
                        f"keep it kind ✦"
                    )
            else:
                # severity 3 — soft public nudge, no persistent record
                if message.channel:
                    await message.channel.send(
                        f"{member.mention} — let's keep it chill in here "
                        f"({reason})."
                    )

            # mod alert for sev >= 4 or escalated repeats
            if mod_alert_channel and (severity >= 4 or escalated):
                embed = veloura_embed(
                    "ai-automod",
                    (
                        f"**user:** {member.mention} (`{member.id}`)\n"
                        f"**severity:** {severity}/5{' • **repeat offender**' if escalated else ''}\n"
                        f"**reason:** {reason}\n"
                        f"**message:** {'deleted' if deleted else 'could not delete'}\n"
                        f"**action:** "
                        + ("timeout + warning" if severity >= 5
                           else "warning" if severity == 4 else "nudge")
                    ),
                    0xFEE75C,
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                try:
                    await mod_alert_channel.send(embed=embed)
                except discord.HTTPException:
                    pass
            logger.info(
                f"[ai_automod] {guild.id}/{member.id} sev={severity} "
                f"escalated={escalated} reason={reason}"
            )
        except Exception as e:
            logger.error(f"[ai_automod] enforce error: {type(e).__name__}: {e}")

    # ─── commands ────────────────────────────────────────────────

    aiautomod = app_commands.Group(
        name="aiautomod",
        description="AI-powered automod configuration",
    )

    @aiautomod.command(name="toggle", description="Enable or disable AI automod")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(state="on or off")
    @app_commands.choices(state=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def aiautomod_toggle(self, interaction: discord.Interaction,
                               state: app_commands.Choice[str]):
        self.bot.increment_command('aiautomod_toggle')
        cfg = await self._get_config(interaction.guild.id)
        cfg['enabled'] = (state.value == "on")
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "ai-automod",
            f"ai automod is now **{state.value}**."
            + ("\n⚠️ no alert channel set — use /aiautomod channel" if cfg['enabled'] and not cfg.get('alert_channel_id') else ""),
            COLOR_PINK if cfg['enabled'] else COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @aiautomod.command(name="channel", description="Set the mod-alert channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def aiautomod_channel(self, interaction: discord.Interaction,
                                channel: discord.TextChannel):
        self.bot.increment_command('aiautomod_channel')
        cfg = await self._get_config(interaction.guild.id)
        cfg['alert_channel_id'] = str(channel.id)
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "ai-automod",
            f"mod alerts will go to {channel.mention}.",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @aiautomod.command(name="timeout", description="Set the escalation timeout length")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        duration="How long a severity-5 timeout lasts: 30m, 1h, 2h, 1d, "
                 "or a plain number = minutes (10)"
    )
    async def aiautomod_timeout(self, interaction: discord.Interaction,
                                duration: str):
        self.bot.increment_command('aiautomod_timeout')
        minutes = parse_timeout_minutes(duration)
        if minutes is None:
            await interaction.response.send_message(
                "that duration doesn't look right — try `30m`, `1h`, `2h`, "
                "`1d`, or a plain number of minutes like `10`.",
                ephemeral=True,
            )
            return
        cfg = await self._get_config(interaction.guild.id)
        cfg['timeout_minutes'] = minutes
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "ai-automod",
            f"severity-5 escalation timeout set to **{minutes}m**.",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @aiautomod.command(name="status", description="Show the AI automod configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def aiautomod_status(self, interaction: discord.Interaction):
        self.bot.increment_command('aiautomod_status')
        cfg = await self._get_config(interaction.guild.id)
        alert = "not set"
        if cfg.get('alert_channel_id'):
            ch = interaction.guild.get_channel(int(cfg['alert_channel_id']))
            alert = ch.mention if ch else "`deleted channel`"
        embed = veloura_embed(
            "ai-automod",
            (
                f"**enabled:** `{cfg['enabled']}`\n"
                f"**alert channel:** {alert}\n"
                f"**timeout:** `{cfg['timeout_minutes']}m`\n"
                f"**min severity to act:** `{cfg['min_severity']}`\n\n"
                f"ladder: sev3 → nudge • sev4 → warning • sev5 → timeout\n"
                f"3 violations in 1h auto-escalates one rung."
            ),
            COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AIAutoMod(bot))
