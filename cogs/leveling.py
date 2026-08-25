"""cogs/leveling.py — Veloura leveling system (XP, levels, role rewards)."""
import logging
import random
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
from utils import db as _db
from utils.db import get_guild_setting, set_guild_setting
from utils.veloura_embeds import veloura_embed, level_up_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.leveling')
TBL, JSON_PATH = "leveling_settings", "data/user_levels.json"
XP_MIN, XP_MAX, CD = 15, 25, 60


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}

    def get_level_from_xp(self, total_xp: int):
        level, remaining = 0, max(0, int(total_xp))
        while True:
            needed = 5 * (level ** 2) + 50 * level + 100
            if remaining < needed:
                return level, remaining, needed
            remaining -= needed
            level += 1

    def get_config(self, guild_id: int) -> dict:
        config = get_guild_setting(guild_id, TBL)
        if not isinstance(config, dict):
            config = {}
        config.setdefault("enabled", True)
        config.setdefault("channel_id", None)
        config.setdefault("rate", 1.0)
        config.setdefault("rewards", {})
        return config

    def save_config(self, guild_id: int, config: dict):
        set_guild_setting(guild_id, TBL, config)

    def get_user_level(self, guild_id: int, user_id: int) -> dict:
        sb = _db._supabase if _db.using_supabase() else None
        if sb:
            try:
                r = sb.table("user_levels").select("xp,level").eq(
                    "guild_id", str(guild_id)).eq("user_id", str(user_id)).execute()
                if r.data:
                    row = r.data[0]
                    return {"xp": int(row.get("xp", 0)), "level": int(row.get("level", 0))}
            except Exception:
                pass
        e = _db._read_json(JSON_PATH).get(f"{guild_id}_{user_id}", {})
        return {"xp": int(e.get("xp", 0)), "level": int(e.get("level", 0))}

    def set_user_level(self, guild_id: int, user_id: int, xp: int, level: int):
        sb = _db._supabase if _db.using_supabase() else None
        if sb:
            try:
                sb.table("user_levels").upsert({
                    "guild_id": str(guild_id), "user_id": str(user_id),
                    "xp": int(xp), "level": int(level),
                }).execute()
                return
            except Exception:
                pass
        data = _db._read_json(JSON_PATH)
        data[f"{guild_id}_{user_id}"] = {"xp": int(xp), "level": int(level)}
        _db._write_json(JSON_PATH, data)

    def get_leaderboard(self, guild_id: int, limit: int = 10) -> list:
        sb = _db._supabase if _db.using_supabase() else None
        if sb:
            try:
                r = sb.table("user_levels").select("user_id,xp,level").eq(
                    "guild_id", str(guild_id)).order("xp", desc=True).limit(limit).execute()
                return r.data or []
            except Exception:
                pass
        data = _db._read_json(JSON_PATH)
        rows = []
        for key, entry in data.items():
            if not key.startswith(f"{guild_id}_"):
                continue
            try:
                uid = int(key.split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            rows.append({"user_id": str(uid), "xp": int(entry.get("xp", 0)),
                         "level": int(entry.get("level", 0))})
        rows.sort(key=lambda x: x["xp"], reverse=True)
        return rows[:limit]

    def get_rank(self, guild_id: int, user_id: int):
        rows = self.get_leaderboard(guild_id, limit=10000)
        n = len(rows)
        target = str(user_id)
        return next(((i, n) for i, r in enumerate(rows, 1)
                     if r.get("user_id") == target), (n + 1, n))

    async def announce_levelup(self, guild: discord.Guild, member: discord.Member, level: int):
        config = self.get_config(guild.id)
        rewards = config.get("rewards", {}) or {}
        role_name = None
        rid = rewards.get(str(level))
        if rid:
            try:
                role = guild.get_role(int(rid))
                if role and role not in member.roles:
                    await member.add_roles(role, reason="Level reward")
                    role_name = role.name
            except (TypeError, ValueError, discord.Forbidden):
                pass
        embed = level_up_embed(member, level, role_name)
        cid = config.get("channel_id")
        ch = guild.get_channel(int(cid)) if cid else None
        if ch:
            try:
                await ch.send(content=member.mention, embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        config = self.get_config(message.guild.id)
        gid, uid = message.guild.id, message.author.id
        if not config.get("enabled", True):
            return
        key = f"{gid}_{uid}"
        last = self.xp_cooldowns.get(key)
        if last and (datetime.utcnow() - last).total_seconds() < CD:
            return
        self.xp_cooldowns[key] = datetime.utcnow()
        data = self.get_user_level(gid, uid)
        old_level = data["level"]
        rate = float(config.get("rate", 1.0) or 1.0)
        new_total = data["xp"] + int(random.randint(XP_MIN, XP_MAX) * rate)
        new_level, _, _ = self.get_level_from_xp(new_total)
        self.set_user_level(gid, uid, new_total, new_level)
        if new_level > old_level:
            await self.announce_levelup(message.guild, message.author, new_level)

    @app_commands.command(name="level", description="Show your level card (or someone else's)")
    @app_commands.describe(user="Whose level to check (defaults to you)")
    async def level(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('level')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
        target = user or interaction.user
        data = self.get_user_level(interaction.guild.id, target.id)
        level, cur, needed = self.get_level_from_xp(data["xp"])
        rank, total = self.get_rank(interaction.guild.id, target.id)
        progress = (cur / needed * 100) if needed > 0 else 0
        filled = int(progress / 100 * 20)
        bar = "▰" * filled + "▱" * (20 - filled)
        embed = veloura_embed("level card", f"**{target.display_name}**", COLOR_LAVENDER)
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        embed.add_field(name="level", value=f"**{level}**", inline=True)
        embed.add_field(name="rank", value=f"#{rank} / {total}", inline=True)
        embed.add_field(name="total xp", value=f"{data['xp']:,}", inline=True)
        embed.add_field(name=f"progress — {cur:,} / {needed:,} xp",
                        value=f"`{bar}` {progress:.1f}%", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Top 10 users in this server")
    async def leaderboard(self, interaction: discord.Interaction):
        self.bot.increment_command('leaderboard')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
        rows = self.get_leaderboard(interaction.guild.id, limit=10)
        if not rows:
            return await interaction.response.send_message(
                embed=veloura_embed("leaderboard", "no xp data yet — start chatting!", COLOR_PINK))
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for idx, row in enumerate(rows, 1):
            try:
                uid = int(row.get("user_id", 0))
            except (TypeError, ValueError):
                continue
            m = interaction.guild.get_member(uid)
            name = m.display_name if m else f"user {uid}"
            medal = medals.get(idx, f"`#{idx}`")
            lvl, xp = int(row.get('level', 0)), int(row.get('xp', 0))
            lines.append(f"{medal} **{name}** — level {lvl} · {xp:,} xp")
        await interaction.response.send_message(
            embed=veloura_embed("leaderboard", "\n".join(lines), COLOR_LAVENDER))

    @app_commands.command(name="rewards", description="Show configured level-up role rewards")
    async def rewards(self, interaction: discord.Interaction):
        self.bot.increment_command('rewards')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
        rewards = (self.get_config(interaction.guild.id).get("rewards", {}) or {})
        if not rewards:
            return await interaction.response.send_message(
                embed=veloura_embed("level rewards", "no rewards configured yet.", COLOR_PINK))
        lines = []
        for lvl_str in sorted(rewards, key=lambda x: int(x) if x.isdigit() else 0):
            try:
                role = interaction.guild.get_role(int(rewards[lvl_str]))
            except (TypeError, ValueError):
                role = None
            role_text = role.mention if role else f"`{rewards[lvl_str]}` (missing)"
            lines.append(f"**level {lvl_str}** — {role_text}")
        await interaction.response.send_message(
            embed=veloura_embed("level rewards", "\n".join(lines), COLOR_LAVENDER))

    leveling = app_commands.Group(name="leveling", description="Leveling system configuration")

    @leveling.command(name="config", description="Configure the leveling system")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        setting="What to configure",
        value="Level number (reward / reward_remove) or multiplier (rate)",
        role="Role to assign at the level (only for 'reward')",
        channel="Level-up announcement channel (only for 'channel')",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Level-up Channel", value="channel"),
        app_commands.Choice(name="Set Role Reward", value="reward"),
        app_commands.Choice(name="Remove Role Reward", value="reward_remove"),
        app_commands.Choice(name="XP Multiplier", value="rate"),
    ])
    async def leveling_config(self, interaction: discord.Interaction,
                              setting: app_commands.Choice[str], value: str = None,
                              role: discord.Role = None, channel: discord.TextChannel = None):
        self.bot.increment_command('leveling_config')
        if not interaction.guild:
            return await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
        config = self.get_config(interaction.guild.id)
        key = setting.value
        gid = interaction.guild.id

        async def err(msg):
            await interaction.response.send_message(msg, ephemeral=True)

        async def save_ok(desc):
            self.save_config(gid, config)
            await interaction.response.send_message(
                embed=veloura_embed("leveling", desc, COLOR_PINK))

        if key == "channel":
            if channel is None:
                return await err("❌ provide a `channel` for this setting.")
            config["channel_id"] = str(channel.id)
            return await save_ok(f"level-up channel set to {channel.mention}.")
        if key in ("reward", "reward_remove"):
            if value is None or (key == "reward" and role is None):
                return await err("❌ provide `value` (level number)" +
                                 (" and `role`." if key == "reward" else "."))
            try:
                level_num = int(value)
            except ValueError:
                return await err("❌ `value` must be a whole number level.")
            if level_num < 1:
                return await err("❌ level must be 1 or higher.")
            rewards = config.setdefault("rewards", {})
            if key == "reward":
                rewards[str(level_num)] = str(role.id)
                return await save_ok(f"reward set: level **{level_num}** → {role.mention}.")
            if str(level_num) not in rewards:
                return await err(f"no reward was set for level {level_num}.")
            del rewards[str(level_num)]
            return await save_ok(f"removed reward for level **{level_num}**.")
        if key == "rate":
            if value is None:
                return await err("❌ provide the multiplier as `value` (e.g. 1.5).")
            try:
                rate = float(value)
            except ValueError:
                return await err("❌ `value` must be a number (e.g. 1.5).")
            rate = max(0.1, min(10.0, rate))
            config["rate"] = rate
            return await save_ok(f"xp multiplier set to **{rate}x**.")


async def setup(bot):
    await bot.add_cog(Leveling(bot))
