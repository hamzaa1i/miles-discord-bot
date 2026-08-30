"""cogs/leveling.py — Veloura leveling system (XP, levels, role rewards)."""
import logging
import random
import time as _time
from datetime import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils import db as _db
from utils.db import get_guild_setting, set_guild_setting
from utils.veloura_embeds import veloura_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.leveling')
TBL, JSON_PATH = "leveling_settings", "data/user_levels.json"
XP_MIN, XP_MAX, CD = 15, 25, 60
# FIX 5 — Cache TTL for leveling settings (seconds). Reduces Supabase
# queries from every-message to once-per-minute-per-guild.
CONFIG_CACHE_TTL = 60

# FIX 2 — default level-up message template + valid channel modes.
# Template variables (safe .replace, never .format, so unbalanced braces
# in user templates can't crash):
#   {user}  {user.name}  {level}  {next_level}  {xp}  {server}  {membercount}
DEFAULT_LEVEL_UP_MESSAGE = "🎉 {user} just reached level {level}! ✦"
LEVEL_UP_CHANNEL_MODES = ("active", "configured", "dm", "none")


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}
        # FIX 5 — {guild_id: (config_dict, timestamp)}; refreshed at most
        # once per CONFIG_CACHE_TTL seconds per guild.
        self._config_cache: dict[int, tuple[dict, float]] = {}
        # PHASE 1 / PART 4.3 — xp_cooldowns only ever GREW: every user who
        # ever chatted in any guild left a "{gid}_{uid}" key forever. This
        # sweep drops entries older than the 60s cooldown window (they're
        # meaningless by then) and forgets config-cache entries for guilds
        # the bot left.
        if not self.cooldown_cleanup.is_running():
            self.cooldown_cleanup.start()

    def cog_unload(self):
        if self.cooldown_cleanup.is_running():
            self.cooldown_cleanup.cancel()

    @tasks.loop(minutes=10)
    async def cooldown_cleanup(self):
        now = datetime.utcnow()
        stale = [
            k for k, ts in self.xp_cooldowns.items()
            if (now - ts).total_seconds() > CD
        ]
        for k in stale:
            del self.xp_cooldowns[k]
        tnow = _time.time()
        for gid in list(self._config_cache.keys()):
            cached = self._config_cache.get(gid)
            if cached is None or tnow - cached[1] > 3600:
                self._config_cache.pop(gid, None)

    @cooldown_cleanup.before_loop
    async def before_cooldown_cleanup(self):
        await self.bot.wait_until_ready()

    def get_level_from_xp(self, total_xp: int):
        level, remaining = 0, max(0, int(total_xp))
        while True:
            needed = 5 * (level ** 2) + 50 * level + 100
            if remaining < needed:
                return level, remaining, needed
            remaining -= needed
            level += 1

    def get_config(self, guild_id: int) -> dict:
        """FIX 5 — Return leveling config with a 60s in-memory cache.

        Previously this hit Supabase on every single message, which
        caused the repeated `GET /rest/v1/leveling_settings 404` log
        spam and wasted quota. The cache is invalidated on save_config().
        """
        now = _time.time()
        cached = self._config_cache.get(guild_id)
        if cached is not None:
            config, ts = cached
            if now - ts < CONFIG_CACHE_TTL:
                # Ensure default keys are present on cached reads too
                config.setdefault("enabled", True)
                config.setdefault("channel_id", None)
                config.setdefault("rate", 1.0)
                config.setdefault("rewards", {})
                # FIX 2 — level-up message defaults
                config.setdefault("level_up_message", DEFAULT_LEVEL_UP_MESSAGE)
                config.setdefault("level_up_channel_mode", "active")
                return config
        config = get_guild_setting(guild_id, TBL)
        if not isinstance(config, dict):
            config = {}
        config.setdefault("enabled", True)
        config.setdefault("channel_id", None)
        config.setdefault("rate", 1.0)
        config.setdefault("rewards", {})
        # FIX 2 — level-up message defaults
        config.setdefault("level_up_message", DEFAULT_LEVEL_UP_MESSAGE)
        config.setdefault("level_up_channel_mode", "active")
        self._config_cache[guild_id] = (config, now)
        return config

    def save_config(self, guild_id: int, config: dict):
        set_guild_setting(guild_id, TBL, config)
        # FIX 5 — Invalidate cache so the next read picks up the new value
        self._config_cache.pop(guild_id, None)

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

    def render_level_up_message(self, template: str, member, guild,
                                 level: int, total_xp: int) -> str:
        """FIX 2 — render the level-up template with all variables.

        Uses chained .replace() (never .format()) so a user template with
        unbalanced braces can't raise. {xp} is thousands-separated."""
        text = str(template or DEFAULT_LEVEL_UP_MESSAGE)
        # {user.name} must be replaced before {user} (prefix collision)
        text = text.replace("{user.name}", member.display_name)
        text = text.replace("{user}", member.mention)
        text = text.replace("{level}", str(level))
        text = text.replace("{next_level}", str(level + 1))
        try:
            text = text.replace("{xp}", f"{int(total_xp):,}")
        except (TypeError, ValueError):
            text = text.replace("{xp}", str(total_xp))
        text = text.replace("{server}", guild.name if guild else "the server")
        text = text.replace("{membercount}", str(guild.member_count or 0) if guild else "0")
        return text[:2000]

    async def announce_levelup(self, guild: discord.Guild, member: discord.Member,
                               level: int, message: discord.Message = None,
                               total_xp: int = 0):
        """FIX 2 — customizable level-up announcements.

        Rewritten from the old hardcoded announce-channel embed:
          * message text  — level_up_message template (rendered with
                            {user} {user.name} {level} {next_level} {xp}
                            {server} {membercount})
          * where it goes — level_up_channel_mode:
              "active"     → the channel where the member leveled up (default)
              "configured" → the channel set via /leveling config channel
              "dm"         → a DM to the member (silently skipped if closed)
              "none"       → no announcement at all
        Role rewards are still handed out regardless of the mode."""
        config = self.get_config(guild.id)

        # ---- role rewards (unchanged behavior) ----
        rewards = config.get("rewards", {}) or {}
        rid = rewards.get(str(level))
        if rid:
            try:
                role = guild.get_role(int(rid))
                if role and role not in member.roles:
                    await member.add_roles(role, reason="Level reward")
            except (TypeError, ValueError, discord.Forbidden):
                pass

        mode = str(config.get("level_up_channel_mode") or "active").lower()
        if mode not in LEVEL_UP_CHANNEL_MODES:
            mode = "active"
        template = config.get("level_up_message") or DEFAULT_LEVEL_UP_MESSAGE
        text = self.render_level_up_message(template, member, guild, level, total_xp)

        try:
            if mode == "none":
                return  # announcements disabled
            if mode == "dm":
                await member.send(text)
                return
            if mode == "configured":
                cid = config.get("channel_id")
                ch = guild.get_channel(int(cid)) if cid else None
                if ch:
                    await ch.send(text)
                elif message is not None:
                    # configured channel vanished — fall back to active
                    await message.channel.send(text)
                return
            # default: "active" — the channel that triggered the level-up
            if message is not None:
                await message.channel.send(text)
            else:
                cid = config.get("channel_id")
                ch = guild.get_channel(int(cid)) if cid else None
                if ch:
                    await ch.send(text)
        except discord.Forbidden:
            pass  # missing perms / DMs closed — skip silently
        except discord.HTTPException:
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
            await self.announce_levelup(
                message.guild, message.author, new_level,
                message=message, total_xp=new_total
            )

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
        value="Level number (reward / reward_remove), multiplier (rate), "
              "level-up message text (level_message), channel mode "
              "(level_channel: active/configured/dm/none), or on/off (toggle)",
        role="Role to assign at the level (only for 'reward')",
        channel="Level-up announcement channel (only for 'channel')",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Level-up Channel", value="channel"),
        app_commands.Choice(name="Set Role Reward", value="reward"),
        app_commands.Choice(name="Remove Role Reward", value="reward_remove"),
        app_commands.Choice(name="XP Multiplier", value="rate"),
        app_commands.Choice(name="Level-up Message", value="level_message"),
        app_commands.Choice(name="Level-up Channel Mode", value="level_channel"),
        app_commands.Choice(name="Enable / Disable", value="toggle"),
        app_commands.Choice(name="Show Settings", value="show"),
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

        # ── FIX 2 — customizable level-up messages ──────────────────
        if key == "level_message":
            if value is None or not value.strip():
                return await err(
                    "❌ provide the template as `value`. variables: `{user}` "
                    "`{user.name}` `{level}` `{next_level}` `{xp}` `{server}` "
                    "`{membercount}` — or `reset` for the default."
                )
            if value.strip().lower() in ("reset", "default"):
                config["level_up_message"] = DEFAULT_LEVEL_UP_MESSAGE
                return await save_ok(
                    f"level-up message reset to default:\n> {DEFAULT_LEVEL_UP_MESSAGE}"
                )
            config["level_up_message"] = value[:500]
            preview = self.render_level_up_message(
                value, interaction.user, interaction.guild, 5, 1234)
            return await save_ok(
                f"level-up message set. preview:\n> {preview[:300]}"
            )

        if key == "level_channel":
            if value is None or not value.strip():
                return await err(
                    "❌ provide the mode as `value`: `active` (where they "
                    "leveled up, default), `configured` (the announce "
                    "channel), `dm`, or `none` (disable)."
                )
            mode = value.strip().lower()
            if mode not in LEVEL_UP_CHANNEL_MODES:
                return await err(
                    "❌ mode must be `active`, `configured`, `dm`, or `none`."
                )
            config["level_up_channel_mode"] = mode
            desc = {
                "active": "posted in the channel where the member leveled up",
                "configured": "posted in the configured level-up channel",
                "dm": "sent as a DM to the member",
                "none": "level-up announcements disabled",
            }[mode]
            warn = ("\n⚠️ no level-up channel set — also run "
                    "`/leveling config setting:channel`."
                    if mode == "configured" and not config.get("channel_id") else "")
            return await save_ok(f"level-up messages: {desc}.{warn}")

        if key == "toggle":
            if value is None or not value.strip():
                return await err("❌ provide `on` or `off` as `value`.")
            state = value.strip().lower()
            if state in ("on", "enable", "enabled", "true", "yes"):
                config["enabled"] = True
                return await save_ok("leveling **enabled**.")
            if state in ("off", "disable", "disabled", "false", "no"):
                config["enabled"] = False
                return await save_ok("leveling **disabled**.")
            return await err("❌ `value` must be `on` or `off`.")

        # FIX 2.4 — config overview (was nothing: /leveling config had no
        # way to see current settings at all)
        if key == "show":
            mode = str(config.get("level_up_channel_mode") or "active")
            template = config.get("level_up_message") or DEFAULT_LEVEL_UP_MESSAGE
            cid = config.get("channel_id")
            ch = interaction.guild.get_channel(int(cid)) if cid else None
            rewards = config.get("rewards", {}) or {}
            embed = veloura_embed("leveling config", "current settings", COLOR_LAVENDER)
            embed.add_field(
                name="status",
                value=(
                    f"**enabled:** `{config.get('enabled', True)}`\n"
                    f"**xp multiplier:** `{config.get('rate', 1.0)}x`\n"
                    f"**level-up channel:** {ch.mention if ch else '*not set*'}"
                ),
                inline=False,
            )
            embed.add_field(
                name="level-up message",
                value=f"```\n{template[:400]}\n```",
                inline=False,
            )
            embed.add_field(
                name="level-up channel mode",
                value=f"`{mode}` — " + {
                    "active": "posted where the member leveled up",
                    "configured": "posted in the configured level-up channel",
                    "dm": "DM'd to the member",
                    "none": "announcements disabled",
                }.get(mode, "posted where the member leveled up"),
                inline=False,
            )
            if rewards:
                lines = []
                for lvl_str in sorted(rewards, key=lambda x: int(x) if x.isdigit() else 0):
                    r = interaction.guild.get_role(int(rewards[lvl_str])) \
                        if str(rewards[lvl_str]).isdigit() else None
                    lines.append(f"level {lvl_str} → {r.mention if r else f'`{rewards[lvl_str]}`'}")
                embed.add_field(name="role rewards", value="\n".join(lines)[:1024], inline=False)
            embed.set_footer(
                text="variables: {user} {user.name} {level} {next_level} {xp} {server} {membercount}"
            )
            await interaction.response.send_message(embed=embed)
            return


async def setup(bot):
    await bot.add_cog(Leveling(bot))
