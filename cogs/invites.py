"""
cogs/invites.py — Veloura invite tracking.

  /invites [@user]          — show your (or someone's) invite count
  /invite_leaderboard       — top 10 inviters in this server

Listeners:
  on_ready            — prime the invite cache for every guild
  on_invite_create    — add new invite to cache
  on_invite_delete    — remove invite from cache
  on_member_join      — diff cache vs current invites to find the inviter

Storage: data/invite_tracking.json (or Supabase via get/set_guild_setting
under the "invite_tracking" table). Format:
  { "guild_id": { "inviter_user_id": {"count": N, "valid": M} } }
"""
import logging

import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils.db import get_guild_setting, set_guild_setting, _read_json, _write_json
from utils.veloura_embeds import veloura_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.invites')

SETTINGS_TABLE = "invite_tracking"


class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # { guild_id: { code: uses } }
        self.invite_cache: dict = {}

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
    @staticmethod
    def _load_all() -> dict:
        # Try Supabase-aware guild setting storage first
        return None  # placeholder; per-guild fetch handled below

    def get_guild_data(self, guild_id: int) -> dict:
        config = get_guild_setting(guild_id, SETTINGS_TABLE)
        if isinstance(config, dict) and "inviters" in config:
            return config.get("inviters", {}) or {}
        # fall back to JSON file
        data = _read_json("data/invite_tracking.json")
        return data.get(str(guild_id), {}) or {}

    def save_guild_data(self, guild_id: int, inviters: dict):
        try:
            set_guild_setting(guild_id, SETTINGS_TABLE, {"inviters": inviters})
        except Exception as e:
            logger.error(f"[invites] save_guild_data supabase error: {e}")
        # mirror to JSON
        data = _read_json("data/invite_tracking.json")
        data[str(guild_id)] = inviters
        _write_json("data/invite_tracking.json", data)

    def increment_inviter(self, guild_id: int, inviter_id: int):
        inviters = self.get_guild_data(guild_id)
        key = str(inviter_id)
        entry = inviters.get(key, {"count": 0, "valid": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["valid"] = int(entry.get("valid", 0)) + 1
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
    @app_commands.command(name="invites", description="Show how many invites you (or someone) have")
    @app_commands.describe(user="Whose invite count to show (defaults to you)")
    async def invites(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('invites')
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
