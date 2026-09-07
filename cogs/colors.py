"""cogs/colors.py — PHASE 3 / PART 4 — custom color roles.

/color set hex       — set your personal color role (#RRGGBB or
                       RRGGBB). 24h cooldown per user. Creates the
                       role "🎨 <display name>" (positioned just above
                       @everyone) or edits your existing one.
/color remove        — delete your color role (and the server role).
/color show [@user]  — show someone's current color.
/color cleanup       — (owner or Manage Roles) sweep empty 🎨 roles
                       and stale database rows; the daily background
                       loop does the same automatically.

The role name stays in sync with the member's display name so the
role list keeps looking tidy.

DB: utils/db.py user_color_roles helpers (Supabase, JSON fallback).
"""
import logging
import os
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import db as _db

logger = logging.getLogger('cyn.colors')

COLOR_ROLE_PREFIX = "🎨 "
COLOR_COOLDOWN_HOURS = 24
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_hex_color(text: str) -> int | None:
    """Validate #RRGGBB / RRGGBB and return the int, or None."""
    m = _HEX_RE.match(str(text or "").strip())
    if not m:
        return None
    return int(m.group(1), 16)


def hex_str(color: int) -> str:
    return f"#{color:06X}"


def _cooldown_remaining(last_changed) -> float:
    """Seconds left in the 24h cooldown; 0 when it has passed."""
    if not last_changed:
        return 0.0
    try:
        last = datetime.fromisoformat(str(last_changed))
    except (TypeError, ValueError):
        return 0.0
    elapsed = (datetime.utcnow() - last).total_seconds()
    limit = COLOR_COOLDOWN_HOURS * 3600
    return max(0.0, limit - elapsed)


def _format_hours(seconds: float) -> str:
    hours = seconds / 3600
    if hours >= 1:
        return f"{hours:.1f}h"
    return f"{max(1, int(seconds / 60))}m"


def _is_owner_or_manage_roles():
    """PHASE 3 / PART 4 — /color cleanup gate: the bot owner OR any
    member with Manage Roles (an OR, not a stack of two checks)."""
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = int(os.getenv("OWNER_ID", "0") or 0)
        if owner_id and interaction.user.id == owner_id:
            return True
        if interaction.guild and interaction.user.guild_permissions.manage_roles:
            return True
        try:
            await interaction.response.send_message(
                "❌ only my owner or members with manage roles can do that.",
                ephemeral=True,
            )
        except discord.InteractionResponded:
            pass
        except Exception:
            pass
        return False
    return app_commands.check(predicate)


class Colors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not self.cleanup_loop.is_running():
            self.cleanup_loop.start()

    def cog_unload(self):
        if self.cleanup_loop.is_running():
            self.cleanup_loop.cancel()

    # ─── Role plumbing ───────────────────────────────────────────

    async def _find_color_role(self, guild: discord.Guild,
                               member: discord.Member):
        """The member's tracked color role, as a discord.Role or None.
        Falls back to any 🎨-prefixed role the member already holds
        (e.g. rows lost to a data wipe)."""
        row = None
        try:
            row = await _db.get_user_color_role_async(guild.id, member.id)
        except Exception:
            row = None
        if row and row.get("role_id"):
            try:
                role = guild.get_role(int(row["role_id"]))
                if role is not None:
                    return role, row
            except (TypeError, ValueError):
                pass
        # Fallback: first 🎨 role the member actually holds.
        for role in member.roles:
            if role.name.startswith(COLOR_ROLE_PREFIX):
                return role, row
        return None, row

    async def _cleanup_guild(self, guild: discord.Guild) -> dict:
        """Remove empty 🎨 roles and stale DB rows. Returns counts."""
        removed_roles = 0
        removed_rows = 0
        me = guild.me
        can_manage = (
            me is not None
            and me.guild_permissions.manage_roles
        )
        if can_manage:
            for role in list(guild.roles):
                if not role.name.startswith(COLOR_ROLE_PREFIX):
                    continue
                try:
                    if len(role.members) == 0:
                        await role.delete(reason="color role cleanup")
                        removed_roles += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass
        # Stale DB rows: role no longer exists in the guild.
        try:
            rows = await _db.get_guild_color_roles_async(guild.id)
        except Exception:
            rows = []
        existing_ids = {str(r.id) for r in guild.roles}
        for row in rows:
            role_id = str(row.get("role_id") or "")
            if role_id and role_id not in existing_ids:
                try:
                    await _db.delete_user_color_role_async(
                        guild.id, row.get("user_id")
                    )
                    removed_rows += 1
                except Exception:
                    pass
        return {"roles": removed_roles, "rows": removed_rows}

    @tasks.loop(hours=24)
    async def cleanup_loop(self):
        for guild in self.bot.guilds:
            try:
                await self._cleanup_guild(guild)
            except Exception as e:
                logger.warning(
                    f"[colors] cleanup failed in {guild.id}: {e}"
                )

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self):
        await self.bot.wait_until_ready()

    # ─── Commands ────────────────────────────────────────────────

    color = app_commands.Group(
        name="color", description="Your personal color role ♡"
    )

    @color.command(name="set", description="Set your personal color role (#RRGGBB)")
    @app_commands.describe(hex="A hex color like #FFC0CB or FFC0CB")
    async def color_set(self, interaction: discord.Interaction, hex: str):
        self.bot.increment_command('color_set')
        if not interaction.guild:
            return await interaction.response.send_message(
                "color roles only work in servers.", ephemeral=True
            )
        hex_value = parse_hex_color(hex)
        if hex_value is None:
            return await interaction.response.send_message(
                "that doesn't look like a hex color — try `#FFC0CB` or "
                "`FFC0CB` ♡",
                ephemeral=True,
            )
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "i need the **manage roles** permission for this ♡",
                ephemeral=True,
            )

        await interaction.response.defer()

        member = interaction.user
        role, row = await self._find_color_role(
            interaction.guild, member
        )

        # 24h cooldown from the last change.
        if row and row.get("last_changed"):
            remaining = _cooldown_remaining(row.get("last_changed"))
            if remaining > 0:
                return await interaction.followup.send(
                    f"you can change your color again in "
                    f"**{_format_hours(remaining)}** — colors need time "
                    "to set ♡",
                    ephemeral=True,
                )

        try:
            if role is not None:
                # Edit the existing role (name stays in sync too).
                await role.edit(
                    color=discord.Color(hex_value),
                    name=f"{COLOR_ROLE_PREFIX}{member.display_name}"[:100],
                    reason="custom color role update",
                )
                if role not in member.roles:
                    await member.add_roles(
                        role, reason="custom color role"
                    )
            else:
                role = await interaction.guild.create_role(
                    name=f"{COLOR_ROLE_PREFIX}{member.display_name}"[:100],
                    color=discord.Color(hex_value),
                    reason="custom color role",
                )
                # Just above @everyone — visible, low priority.
                try:
                    await role.edit(position=1)
                except (discord.Forbidden, discord.HTTPException):
                    pass
                await member.add_roles(role, reason="custom color role")
        except discord.Forbidden:
            return await interaction.followup.send(
                "i couldn't manage that role — it may be above my top "
                "role ♡",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            logger.error(f"[colors] role write failed: {e}")
            return await interaction.followup.send(
                "something broke while setting the color — try again ♡",
                ephemeral=True,
            )

        try:
            await _db.set_user_color_role_async(
                interaction.guild.id, member.id, role.id, hex_str(hex_value)
            )
        except Exception as e:
            logger.warning(f"[colors] row save failed: {e}")

        embed = discord.Embed(
            title="꒰ა 🎨 ໒꒱ your color",
            description=(
                f"set to **{hex_str(hex_value)}** ✦\n"
                f"role: {role.mention}"
            ),
            color=hex_value,  # the preview IS the color
        )
        embed.set_footer(
            text=f"changes again in {COLOR_COOLDOWN_HOURS}h"
        )
        await interaction.followup.send(embed=embed)

    @color.command(name="remove", description="Remove your color role")
    async def color_remove(self, interaction: discord.Interaction):
        self.bot.increment_command('color_remove')
        if not interaction.guild:
            return await interaction.response.send_message(
                "color roles only work in servers.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        role, _row = await self._find_color_role(
            interaction.guild, member
        )
        if role is None:
            return await interaction.followup.send(
                "you don't have a color role set — make one with "
                "`/color set` ♡",
                ephemeral=True,
            )
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="color role removed")
            await role.delete(reason="color role removed")
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(f"[colors] remove failed: {e}")
            return await interaction.followup.send(
                "i couldn't remove that role (permissions) — ask a mod "
                "to delete it manually ♡",
                ephemeral=True,
            )
        try:
            await _db.delete_user_color_role_async(
                interaction.guild.id, member.id
            )
        except Exception:
            pass
        await interaction.followup.send(
            f"✅ your color role has been removed ♡", ephemeral=True
        )

    @color.command(name="show", description="Show someone's color role")
    @app_commands.describe(user="Whose color to show (defaults to you)")
    async def color_show(self, interaction: discord.Interaction,
                         user: discord.Member = None):
        self.bot.increment_command('color_show')
        if not interaction.guild:
            return await interaction.response.send_message(
                "color roles only work in servers.", ephemeral=True
            )
        target = user or interaction.user
        role, row = await self._find_color_role(
            interaction.guild, target
        )
        if role is None:
            return await interaction.response.send_message(
                f"**{target.display_name}** doesn't have a color role yet ♡",
                ephemeral=True,
            )
        hex_value = role.color.value if role.color.value else 0xE6E6FA
        embed = discord.Embed(
            title=f"꒰ა 🎨 ໒꒱ {target.display_name}'s color",
            description=f"**{hex_str(hex_value)}** · {role.mention}",
            color=hex_value,
        )
        await interaction.response.send_message(embed=embed)

    @color.command(name="cleanup", description="Sweep empty color roles (owner/mods)")
    @_is_owner_or_manage_roles()
    async def color_cleanup(self, interaction: discord.Interaction):
        self.bot.increment_command('color_cleanup')
        if not interaction.guild:
            return await interaction.response.send_message(
                "color roles only work in servers.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        try:
            counts = await self._cleanup_guild(interaction.guild)
        except Exception as e:
            logger.error(f"[colors] cleanup command failed: {e}")
            return await interaction.followup.send(
                "cleanup failed — check my permissions ♡", ephemeral=True
            )
        await interaction.followup.send(
            f"✅ cleaned **{counts['roles']}** empty color role(s) and "
            f"**{counts['rows']}** stale entr"
            f"{'y' if counts['rows'] == 1 else 'ies'} ♡",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Colors(bot))
