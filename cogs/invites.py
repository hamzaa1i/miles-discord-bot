"""
cogs/invites.py — Veloura invite tracking.

  /invites show [@user]     — show your (or someone's) invite count
  /invites set @user [count] — set invite count (owner/admin only)
  /invite_leaderboard        — top 10 inviters in this server

Listeners:
  on_ready            — prime the invite cache for every guild
  on_invite_create    — add new invite to cache
  on_invite_delete    — remove invite from cache
  on_member_join      — diff cache vs current invites to find the inviter

Storage: data/invite_tracking.json (primary) + Supabase mirror (best-effort).
Format: { "guild_id": { "inviter_user_id": {"count": N, "valid": M} } }
"""
import logging
import os

import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import db as _db
from utils.db import get_guild_setting, set_guild_setting, _read_json, _write_json
from utils.veloura_embeds import veloura_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.invites')

SETTINGS_TABLE = "invite_tracking"
INVITES_JSON_PATH = "data/invite_tracking.json"


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # { guild_id: { code: uses } }
        self.invite_cache: dict = {}
        # FIX 4A — load persisted invite data on startup so counts
        # survive restarts. The JSON file is the source of truth.
        self._load_persisted_invites()

    def _load_persisted_invites(self):
        """FIX 4A — Load invite data from JSON on cog init.
        Logs how many guilds/users were loaded for verification."""
        try:
            data = _read_json(INVITES_JSON_PATH)
            total_guilds = len(data)
            total_users = sum(len(v) for v in data.values() if isinstance(v, dict))
            logger.info(
                f"[invites] loaded persisted data: {total_guilds} guilds, "
                f"{total_users} inviter records"
            )
        except Exception as e:
            logger.warning(f"[invites] failed to load persisted data: {e}")

    # ─── Cog lifecycle ──────────────────────────────────────────
    async def cog_load(self):
        # Start a background task that primes the cache once the bot is ready.
        self._prime_loop.start()

    def cog_unload(self):
        self._prime_loop.cancel()

    @tasks.loop(count=1)
    async def _prime_loop(self):
        await self.bot.wait_until_ready()
        await self.prime_cache()

    @_prime_loop.before_loop
    async def _before_prime(self):
        await self.bot.wait_until_ready()

    async def prime_cache(self):
        """Fetch invites for every guild and store current uses."""
        for guild in self.bot.guilds:
            await self._refresh_guild_cache(guild)

    async def _refresh_guild_cache(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            logger.warning(f"[invites] no manage_guild permission in {guild.name}")
            self.invite_cache.pop(guild.id, None)
            return
        except discord.HTTPException as e:
            logger.error(f"[invites] failed to fetch invites for {guild.name}: {e}")
            return
        mapping = {}
        for inv in invites:
            try:
                mapping[inv.code] = inv.uses or 0
            except Exception:
                continue
        self.invite_cache[guild.id] = mapping

    # ─── Storage helpers ────────────────────────────────────────
    # FIX 3 — The invite_tracking Supabase table has columns:
    #   guild_id, inviter_id, invites, joins, leaves
    # (composite PK: guild_id + inviter_id)
    # JSON file is the primary store; Supabase is a best-effort mirror.

    def get_guild_data(self, guild_id: int) -> dict:
        # Primary: JSON file (always works)
        data = _read_json(INVITES_JSON_PATH)
        return data.get(str(guild_id), {}) or {}

    def save_guild_data(self, guild_id: int, inviters: dict):
        # Primary: JSON file
        data = _read_json(INVITES_JSON_PATH)
        data[str(guild_id)] = inviters
        _write_json(INVITES_JSON_PATH, data)
        # Best-effort Supabase mirror using the correct column names.
        try:
            sb = _db._supabase if _db.using_supabase() else None
            if sb:
                for uid_str, entry in inviters.items():
                    try:
                        sb.table(SETTINGS_TABLE).upsert({
                            "guild_id": str(guild_id),
                            "inviter_id": str(uid_str),
                            "invites": int(entry.get("count", 0)),
                            "joins": int(entry.get("valid", 0)),
                            "leaves": 0,
                        }).execute()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"[invites] supabase mirror failed: {e}")

    def increment_inviter(self, guild_id: int, inviter_id: int):
        inviters = self.get_guild_data(guild_id)
        key = str(inviter_id)
        entry = inviters.get(key, {"count": 0, "valid": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["valid"] = int(entry.get("valid", 0)) + 1
        inviters[key] = entry
        self.save_guild_data(guild_id, inviters)

    def set_inviter_count(self, guild_id: int, inviter_id: int, count: int):
        """FIX 4B — Set invite count for a specific user (manual override)."""
        inviters = self.get_guild_data(guild_id)
        key = str(inviter_id)
        entry = inviters.get(key, {"count": 0, "valid": 0})
        entry["count"] = int(count)
        entry["valid"] = int(count)
        inviters[key] = entry
        self.save_guild_data(guild_id, inviters)

    def get_inviter_count(self, guild_id: int, user_id: int) -> int:
        inviters = self.get_guild_data(guild_id)
        entry = inviters.get(str(user_id), {})
        return int(entry.get("count", 0))

    def get_leaderboard(self, guild_id: int, limit: int = 10) -> list:
        inviters = self.get_guild_data(guild_id)
        rows = []
        for uid_str, entry in inviters.items():
            try:
                rows.append({
                    "user_id": uid_str,
                    "count": int(entry.get("count", 0)),
                    "valid": int(entry.get("valid", 0)),
                })
            except (TypeError, ValueError):
                continue
        rows.sort(key=lambda x: x["count"], reverse=True)
        return rows[:limit]

    # ─── Listeners ──────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if not invite.guild:
            return
        guild_id = invite.guild.id
        if guild_id not in self.invite_cache:
            await self._refresh_guild_cache(invite.guild)
            return
        try:
            self.invite_cache[guild_id][invite.code] = invite.uses or 0
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if not invite.guild:
            return
        guild_id = invite.guild.id
        if guild_id in self.invite_cache:
            self.invite_cache[guild_id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        try:
            current = await guild.invites()
        except discord.Forbidden:
            logger.warning(f"[invites] can't track joins in {guild.name} — no permission")
            return
        except discord.HTTPException as e:
            logger.error(f"[invites] fetch invites on join failed: {e}")
            return
        cached = self.invite_cache.get(guild.id, {})
        inviter_id = None
        for inv in current:
            try:
                prev_uses = cached.get(inv.code, 0)
                uses_now = inv.uses or 0
                if uses_now > prev_uses and inv.inviter is not None:
                    inviter_id = inv.inviter.id
                    cached[inv.code] = uses_now
                    break
            except Exception:
                continue
        # Rebuild cache from current snapshot
        new_cache = {}
        for inv in current:
            try:
                new_cache[inv.code] = inv.uses or 0
            except Exception:
                continue
        self.invite_cache[guild.id] = new_cache
        if inviter_id:
            self.increment_inviter(guild.id, inviter_id)
            logger.info(f"[invites] {member} joined {guild.name} via inviter {inviter_id}")

    # ─── Slash commands ─────────────────────────────────────────
    # FIX 4B — /invites is now a group with "show" and "set" subcommands.
    invites = app_commands.Group(name="invites", description="Invite tracking commands")

    @invites.command(name="show", description="Show how many invites you (or someone) have")
    @app_commands.describe(user="Whose invite count to show (defaults to you)")
    async def invites_show(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('invites_show')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        target = user or interaction.user
        count = self.get_inviter_count(interaction.guild.id, target.id)
        embed = veloura_embed(
            "invites",
            f"**{target.display_name}** has invited **{count}** "
            f"member{'s' if count != 1 else ''} to "
            f"**{interaction.guild.name}**. ✩",
            COLOR_LAVENDER,
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        await interaction.response.send_message(embed=embed)

    @invites.command(name="set", description="Set invite count for a user (owner/admin only)")
    @app_commands.describe(user="The user whose invite count to set", count="The new invite count")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def invites_set(self, interaction: discord.Interaction, user: discord.Member, count: int):
        self.bot.increment_command('invites_set')
        # Also allow bot owner
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if interaction.user.id != owner_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "only the server owner or bot owner can set invite counts.",
                ephemeral=True,
            )
            return
        if count < 0:
            await interaction.response.send_message(
                "count must be 0 or higher.", ephemeral=True
            )
            return
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        self.set_inviter_count(interaction.guild.id, user.id, count)
        logger.info(
            f"[invites] set {user.display_name}'s invite count to {count} "
            f"in guild {interaction.guild.id} by {interaction.user.display_name}"
        )
        embed = veloura_embed(
            "invites set",
            f"**{user.display_name}**'s invite count set to **{count}**. ✩",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite_leaderboard", description="Top 10 inviters in this server")
    async def invite_leaderboard(self, interaction: discord.Interaction):
        self.bot.increment_command('invite_leaderboard')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        rows = self.get_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            await interaction.response.send_message(
                embed=veloura_embed(
                    "invite leaderboard",
                    "no invite data yet — invite some friends! ♡",
                    COLOR_PINK,
                )
            )
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for idx, row in enumerate(rows, 1):
            try:
                uid = int(row["user_id"])
            except (TypeError, ValueError):
                continue
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"user {uid}"
            count = int(row.get("count", 0))
            medal = medals.get(idx, f"`#{idx}`")
            lines.append(f"{medal} **{name}** — {count} invite{'s' if count != 1 else ''}")
        embed = veloura_embed(
            "invite leaderboard",
            "\n".join(lines),
            COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Invites(bot))
