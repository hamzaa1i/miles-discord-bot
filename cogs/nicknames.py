"""cogs/nicknames.py — PHASE 3 / PART 5 — nickname request system.

/nick config #channel [auto_approve] [cooldown] — set the review
    channel and options (Manage Server). Default cooldown 24h.
/nick request new:<text>     — request a nickname change (2-32
    chars). With auto_approve on, it applies immediately; otherwise
    the request goes to the review channel with ✓ / ✗ buttons.
/nick pending                — mods: list pending requests with
    approve/deny buttons (Manage Server).
/nick my                     — your request history (ephemeral).

Buttons are persistent and restart-safe (custom_id "nick:approve:<id>"
/ "nick:deny:<id>" handled in on_interaction — the same pattern as
the onboarding and giveaway cogs). Denying opens a reason modal, then
DMs the requester. Permission failures (role hierarchy, missing
manage_nicknames) are reported to the reviewer and never raise.

Requests are rate-limited by the user's most recent request of ANY
status, so a denial still respects the cooldown.

DB: utils/db.py nick helpers (Supabase nick_requests + nick_settings,
JSON fallback).
"""
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.nicknames')

BUTTON_PREFIX = "nick:"

MIN_NICK_LEN = 2
MAX_NICK_LEN = 32
DEFAULT_COOLDOWN_HOURS = 24
MAX_COOLDOWN_HOURS = 168  # one week

STATUS_EMOJI = {
    "pending": "⏳",
    "approved": "✅",
    "denied": "❌",
}


def _validate_nick(text: str) -> str | None:
    """Strip + length-check a requested nickname (2-32 chars)."""
    nick = str(text or "").strip()
    if len(nick) < MIN_NICK_LEN or len(nick) > MAX_NICK_LEN:
        return None
    return nick


def _cooldown_for(last_request: dict | None, cooldown_hours: int) -> float:
    """Seconds left in the request cooldown for the guild's setting."""
    if not last_request or not last_request.get("created_at"):
        return 0.0
    try:
        then = datetime.fromisoformat(str(last_request["created_at"]))
    except (TypeError, ValueError):
        return 0.0
    elapsed = (datetime.utcnow() - then).total_seconds()
    return max(0.0, cooldown_hours * 3600 - elapsed)


def _format_hours(seconds: float) -> str:
    hours = seconds / 3600
    if hours >= 1:
        return f"{hours:.1f}h"
    return f"{max(1, int(seconds / 60))}m"


def _build_view(request_id) -> discord.ui.View:
    """The persistent ✓ / ✗ view (custom_ids handled by
    on_interaction, so it survives restarts)."""
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="Approve", style=discord.ButtonStyle.success, emoji="✓",
        custom_id=f"{BUTTON_PREFIX}approve:{request_id}",
    ))
    view.add_item(discord.ui.Button(
        label="Deny with Reason", style=discord.ButtonStyle.danger,
        emoji="✗", custom_id=f"{BUTTON_PREFIX}deny:{request_id}",
    ))
    return view


class DenyReasonModal(discord.ui.Modal, title="deny nickname request"):
    """Reason collector for denials (optional text)."""

    reason = discord.ui.TextInput(
        label="reason (shown to the requester)",
        placeholder="e.g. too close to a mod's nickname ♡",
        max_length=200,
        required=False,
    )

    def __init__(self, cog: "Nicknames", request_id):
        super().__init__()
        self.cog = cog
        self.request_id = request_id

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog._resolve(
            interaction, self.request_id, "denied",
            reason=str(self.reason or "").strip(),
        )


class Nicknames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Request embed ───────────────────────────────────────────

    def _request_embed(self, member, current: str, requested: str,
                       request_id) -> discord.Embed:
        embed = discord.Embed(
            title="꒰ა ✏️ ໒꒱ nickname request",
            description=f"{member.mention} requested nickname change",
            color=get_seasonal_color(),
        )
        embed.add_field(
            name="current nick", value=current or "*none*", inline=True
        )
        embed.add_field(
            name="requested nick", value=requested, inline=True
        )
        embed.set_footer(text=f"request #{request_id}")
        return embed

    # ─── Persistent button handling ──────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        if data.get("component_type") != 2:  # button
            return
        custom_id = data.get("custom_id", "") or ""
        if not custom_id.startswith(BUTTON_PREFIX):
            return
        # nick:approve:<id> / nick:deny:<id>
        try:
            _, action, req_id = custom_id.split(":")
        except ValueError:
            return

        # Reviewer gate: Manage Server.
        if not (interaction.guild and
                interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message(
                "❌ you need the manage server permission to review "
                "nickname requests.",
                ephemeral=True,
            )

        if action == "approve":
            await self._resolve(interaction, req_id, "approved")
        elif action == "deny":
            await interaction.response.send_modal(
                DenyReasonModal(self, req_id)
            )

    async def _resolve(self, interaction: discord.Interaction, req_id,
                       status: str, reason: str = ""):
        """Apply an approval or denial (shared by buttons + modal)."""
        try:
            row = await _db.get_nick_request_async(req_id)
        except Exception:
            row = None
        if not row or row.get("status") != "pending":
            try:
                await interaction.response.send_message(
                    "that request was already handled (or is gone).",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                pass
            return

        guild = interaction.guild
        requested = str(row.get("requested_nick") or "")
        user_id = row.get("user_id")

        member = None
        try:
            member = guild.get_member(int(user_id))
        except (TypeError, ValueError):
            member = None

        if status == "approved":
            if member is None:
                await self._respond(
                    interaction,
                    "they've left the server — request closed without "
                    "the change.",
                )
            else:
                try:
                    await member.edit(
                        nick=requested,
                        reason=f"nickname request #{req_id} approved",
                    )
                    await self._respond(
                        interaction,
                        f"✅ approved — **{member.display_name}** is now "
                        f"**{requested}**.",
                    )
                    try:
                        await member.send(
                            f"your nickname has been approved ♡ set to "
                            f"**{requested}**"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                except (discord.Forbidden, discord.HTTPException):
                    await self._respond(
                        interaction,
                        "couldn't set the nickname — check my "
                        "manage_nicknames permission and the role "
                        "hierarchy (their top role may be above mine).",
                    )
        else:
            await self._respond(
                interaction,
                f"❌ denied — they'll be DM'd the reason."
                if reason else
                "❌ denied — they'll be DM'd (no reason given).",
            )
            if member is not None:
                try:
                    await member.send(
                        f"your nickname request was denied. reason: "
                        f"{reason or 'no reason given'} ♡"
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

        try:
            await _db.update_nick_request_async(
                req_id, status, interaction.user.id, reason
            )
        except Exception as e:
            logger.warning(f"[nick] status update failed for #{req_id}: {e}")

    async def _respond(self, interaction: discord.Interaction, text: str):
        """Ephemeral reply that tolerates an already-used response."""
        try:
            await interaction.response.send_message(text, ephemeral=True)
        except discord.InteractionResponded:
            try:
                await interaction.followup.send(text, ephemeral=True)
            except Exception:
                pass
        except Exception:
            pass

    # ─── Commands ────────────────────────────────────────────────

    nick = app_commands.Group(
        name="nick",
        description="Nickname requests and review ✏️",
    )

    @nick.command(name="config", description="Configure nickname request review")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Where nickname requests are posted for review",
        auto_approve="Apply requests immediately instead of reviewing",
        cooldown="Hours between requests per user (default 24, max 168)",
    )
    async def nick_config(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          auto_approve: bool = None,
                          cooldown: app_commands.Range[int, 1,
                                                       MAX_COOLDOWN_HOURS] = None):
        self.bot.increment_command('nick_config')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        settings = await _db.get_nick_settings_async(interaction.guild.id)
        settings["channel_id"] = str(channel.id)
        if auto_approve is not None:
            settings["auto_approve"] = auto_approve
        if cooldown is not None:
            settings["cooldown_hours"] = int(cooldown)
        await _db.set_nick_settings_async(
            interaction.guild.id, settings
        )
        mode = ("auto-approve (no review)" if settings["auto_approve"]
                else f"review in {channel.mention}")
        await interaction.response.send_message(
            f"✅ nickname requests: **{mode}**, cooldown "
            f"**{settings['cooldown_hours']}h**.",
        )

    @nick.command(name="request", description="Request a nickname change")
    @app_commands.describe(new="The nickname you want (2-32 characters)")
    async def nick_request(self, interaction: discord.Interaction,
                           new: str):
        self.bot.increment_command('nick_request')
        if not interaction.guild:
            return await interaction.response.send_message(
                "nickname requests only work in servers.", ephemeral=True
            )
        requested = _validate_nick(new)
        if requested is None:
            return await interaction.response.send_message(
                f"nicknames must be {MIN_NICK_LEN}-{MAX_NICK_LEN} "
                "characters ♡",
                ephemeral=True,
            )
        member = interaction.user
        current = member.display_name or member.name

        settings = await _db.get_nick_settings_async(interaction.guild.id)

        # Cooldown: the user's most recent request of any status.
        try:
            recent = await _db.get_user_nick_requests_async(
                interaction.guild.id, member.id, limit=1
            )
        except Exception:
            recent = []
        remaining = _cooldown_for(
            recent[0] if recent else None,
            int(settings.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS),
        )
        if remaining > 0:
            return await interaction.response.send_message(
                f"you can request a nickname again in "
                f"**{_format_hours(remaining)}** ♡",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        request_id = await _db.create_nick_request_async(
            interaction.guild.id, member.id, current, requested
        )

        if settings.get("auto_approve"):
            try:
                await member.edit(
                    nick=requested,
                    reason=f"nickname request #{request_id} auto-approved",
                )
                await _db.update_nick_request_async(
                    request_id, "approved", member.id, "auto-approve"
                )
                return await interaction.followup.send(
                    f"✅ auto-approved — your nickname is now "
                    f"**{requested}** ♡",
                    ephemeral=True,
                )
            except (discord.Forbidden, discord.HTTPException):
                await _db.update_nick_request_async(
                    request_id, "denied", member.id,
                    "couldn't set nickname (permissions)"
                )
                return await interaction.followup.send(
                    "i couldn't change your nickname (permissions) — ask "
                    "a mod to set it manually ♡",
                    ephemeral=True,
                )

        channel_id = settings.get("channel_id")
        review_channel = None
        if channel_id:
            try:
                review_channel = interaction.guild.get_channel(
                    int(channel_id)
                )
            except (TypeError, ValueError):
                review_channel = None
        if review_channel is None:
            await _db.update_nick_request_async(
                request_id, "denied", member.id,
                "no review channel configured"
            )
            return await interaction.followup.send(
                "nickname review isn't set up — ask an admin to run "
                "`/nick config` first ♡",
                ephemeral=True,
            )

        try:
            await review_channel.send(
                embed=self._request_embed(
                    member, current, requested, request_id
                ),
                view=_build_view(request_id),
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(f"[nick] review post failed: {e}")
            await _db.update_nick_request_async(
                request_id, "denied", member.id,
                "couldn't post to review channel"
            )
            return await interaction.followup.send(
                f"i couldn't post your request to "
                f"{review_channel.mention} (permissions) — ask a mod ♡",
                ephemeral=True,
            )

        await interaction.followup.send(
            f"✅ request submitted — the mods will review it soon ♡",
            ephemeral=True,
        )

    @nick.command(name="pending", description="Review pending nickname requests")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def nick_pending(self, interaction: discord.Interaction):
        self.bot.increment_command('nick_pending')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        try:
            rows = await _db.get_pending_nick_requests_async(
                interaction.guild.id
            )
        except Exception:
            rows = []
        if not rows:
            return await interaction.followup.send(
                "no pending nickname requests ♡", ephemeral=True
            )

        lines = []
        for r in rows[:10]:
            try:
                who = interaction.guild.get_member(
                    int(r.get("user_id") or 0)
                )
                who_name = who.mention if who else f"`{r.get('user_id')}`"
            except (TypeError, ValueError):
                who_name = f"`{r.get('user_id')}`"
            lines.append(
                f"`#{r.get('id')}` {who_name}: "
                f"**{r.get('current_nick') or '—'}** → "
                f"**{r.get('requested_nick')}**"
            )
        embed = discord.Embed(
            title="꒰ა ✏️ ໒꒱ pending nickname requests",
            description="\n".join(lines),
            color=get_seasonal_color(),
        )
        # Fresh persistent buttons for the first 5 (10 buttons max).
        view = None
        if rows:
            view = discord.ui.View(timeout=None)
            for r in rows[:5]:
                rid = r.get("id")
                view.add_item(discord.ui.Button(
                    label=f"✓ #{rid}",
                    style=discord.ButtonStyle.success,
                    custom_id=f"{BUTTON_PREFIX}approve:{rid}",
                ))
                view.add_item(discord.ui.Button(
                    label=f"✗ #{rid}",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"{BUTTON_PREFIX}deny:{rid}",
                ))
        await interaction.followup.send(
            embed=embed, view=view, ephemeral=True
        )

    @nick.command(name="my", description="Your nickname request history")
    async def nick_my(self, interaction: discord.Interaction):
        self.bot.increment_command('nick_my')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
        try:
            rows = await _db.get_user_nick_requests_async(
                interaction.guild.id, interaction.user.id, limit=10
            )
        except Exception:
            rows = []
        if not rows:
            return await interaction.response.send_message(
                "you haven't requested a nickname here yet ♡",
                ephemeral=True,
            )
        lines = []
        for r in rows:
            emoji = STATUS_EMOJI.get(str(r.get("status")), "•")
            when = str(r.get("created_at") or "")[:10]
            reason = r.get("reason")
            line = (
                f"{emoji} **{r.get('requested_nick')}** · "
                f"{r.get('status')} · {when}"
            )
            if reason:
                line += f"\n> {str(reason)[:100]}"
            lines.append(line)
        embed = discord.Embed(
            title="꒰ა ✏️ ໒꒱ your nickname requests",
            description="\n".join(lines)[:4000],
            color=get_seasonal_color(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Nicknames(bot))
