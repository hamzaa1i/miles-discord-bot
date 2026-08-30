"""
cogs/prefix.py — custom prefix system with two-tier command routing.

TIER 1: Known structured commands (welcome, goodbye, mod, utility)
        are handled directly without going through the AI.
TIER 2: Everything else falls through to the AI intent parser.

Slash commands:
  /prefix set [prefix]   — set a custom prefix (Manage Guild)
  /prefix remove         — remove custom prefix (Manage Guild)
  /prefix list           — show current prefix

Data stored in Supabase via utils/db with table "prefix_settings".
"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import time
import logging

from utils.db import get_guild_setting_async, set_guild_setting_async

logger = logging.getLogger('cyn.prefix')


class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache: dict[int, tuple[str | None, float]] = {}

    async def _get_prefix(self, guild_id: int) -> str | None:
        """P1 — async: the Supabase REST read runs in a thread so the
        per-message event loop never blocks."""
        now = time.time()
        if guild_id in self._cache:
            cached_prefix, ts = self._cache[guild_id]
            if now - ts < 60:
                return cached_prefix
        try:
            settings = await get_guild_setting_async(guild_id, "prefix_settings")
            prefix = settings.get("prefix") if settings else None
        except Exception:
            prefix = None
        self._cache[guild_id] = (prefix, now)
        return prefix

    def _invalidate_cache(self, guild_id: int):
        if guild_id in self._cache:
            del self._cache[guild_id]

    # ==================== on_message: prefix routing ====================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        prefix = await self._get_prefix(message.guild.id)
        if not prefix:
            return

        content = message.content
        if not content.lower().startswith(prefix.lower()):
            return

        command_text = content[len(prefix):].strip()
        if not command_text:
            return

        parts = command_text.split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        args_str = " ".join(args)

        await self._route_command(message, cmd, args, args_str, command_text)

    async def _route_command(self, message, cmd, args, args_str, full_text):
        # Welcome commands (consolidated)
        if cmd == "welcome":
            await self._handle_welcome(message, args, args_str)
            return

        # Goodbye commands (now part of welcome config, but keep backward compat)
        if cmd == "goodbye":
            await self._handle_goodbye(message, args, args_str)
            return

        # Mod commands (consolidated warnings + direct execution)
        if cmd in ("warn", "kick", "ban", "purge", "lock", "unlock", "slowmode", "warnings"):
            await self._handle_mod(message, cmd, args, args_str)
            return

        # Simple utility commands
        if cmd in ("help", "ping", "uptime", "botinfo", "flip", "roll",
                   "joke", "fact", "meme", "truth", "dare", "weather"):
            await self._handle_simple(message, cmd, args, args_str)
            return

        # Prefix management via text
        if cmd == "prefix":
            await self._handle_prefix_cmd(message, args, args_str)
            return

        # Fall through to AI
        ai_cog = self.bot.get_cog("AIChat")
        if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
            try:
                await ai_cog.handle_prefix_command(message, full_text)
            except Exception as e:
                logger.error(f"[prefix] AI handler error: {e}")

    # ─── Welcome ──────────────────────────────────────────────────

    # FIX 3 — settings the prefix "welcome config" command can write.
    # Mirrors the /welcome config slash choices (channels and toggles get
    # dedicated handling below; everything else is a plain string write).
    WELCOME_CONFIG_KEYS = {
        "channel": "channel_id",
        "message": "message",
        "embed_mode": "embed_mode",
        "color": "welcome_color",
        "image": "welcome_image",
        "title": "welcome_title",
        "thumbnail": "welcome_thumbnail",
        "footer": "welcome_footer",
        "dm": "dm_message",
        "goodbye_channel": "goodbye_channel_id",
        "goodbye_message": "goodbye_message",
    }

    async def _handle_welcome(self, message, args, args_str):
        sub = args[0].lower() if args else ""

        # FIX 3 — /welcome config consolidation: the prefix equivalent is
        # "welcome config <setting> <value...>", mirroring the slash choices.
        if sub == "config":
            await self._handle_welcome_config(message, args[1:])
            return

        if sub == "show":
            await self._handle_welcome_show(message)
            return

        if sub == "test":
            await self._handle_welcome_test(message, args[1:])
            return

        # Back-compat shortcuts from the old prefix interface
        if sub == "message":
            # FIX 2 — Capture everything after "welcome message " including newlines
            prefix = await self._get_prefix(message.guild.id)
            match = re.match(
                rf'^{re.escape(prefix)}welcome\s+message\s+',
                message.content,
                re.IGNORECASE
            )
            if match:
                text = message.content[match.end():]
            else:
                text = ""

            if not text:
                await message.reply("provide a message. use {user} for username, {server} for server name.")
                return

            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            settings["message"] = text
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            await message.reply("welcome message set. variables: {user}, {server}, {membercount}")
            return

        if sub == "channel":
            if not message.channel_mentions:
                await message.reply("mention a channel: welcome channel #channel")
                return
            channel = message.channel_mentions[0]
            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            settings["channel_id"] = str(channel.id)
            settings["enabled"] = True
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            await message.reply(f"welcome channel set to {channel.mention}.")
            return

        await message.reply(
            "usage: welcome config <setting> <value> | welcome test "
            "[welcome|goodbye|dm] | welcome show\n(use /welcome for full config options)"
        )

    async def _handle_welcome_config(self, message, args):
        """FIX 3 — prefix mirror of /welcome config: 13 settings via
        "welcome config <setting> <value>". The slash command does the rich
        validation (hex colors, URL checks, autocomplete); this route keeps
        writes simple so the advertised help text is truthful."""
        if not message.author.guild_permissions.manage_guild:
            owner_id = int(os.getenv("OWNER_ID", "0"))
            if message.author.id != owner_id:
                await message.reply("no permission.")
                return

        if not args:
            await message.reply(
                "usage: welcome config <setting> <value>\n"
                "settings: channel, message, embed_mode, color, image, title, "
                "thumbnail, footer, dm, toggle, goodbye_channel, "
                "goodbye_message, goodbye_toggle\n"
                "(use /welcome config for autocomplete + validation)"
            )
            return

        setting = args[0].lower()

        # value = everything after the setting word, so multi-word message
        # templates survive intact (same trick as "welcome message <text>")
        prefix = await self._get_prefix(message.guild.id) or ""
        match = re.match(
            rf'^{re.escape(prefix)}welcome\s+config\s+\S+\s+',
            message.content,
            re.IGNORECASE
        )
        value = message.content[match.end():].strip() if match else " ".join(args[1:])

        # toggles
        if setting in ("toggle", "goodbye_toggle"):
            state = (value or "").strip().lower()
            if state not in ("on", "off"):
                await message.reply(f"usage: welcome config {setting} on|off")
                return
            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            if setting == "toggle":
                settings["enabled"] = (state == "on")
            else:
                settings["goodbye_enabled"] = (state == "on")
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            label = "welcome" if setting == "toggle" else "goodbye"
            await message.reply(f"{label} messages {state}.")
            return

        # channel settings — a #channel mention in the message wins
        if setting in ("channel", "goodbye_channel"):
            channel = message.channel_mentions[0] if message.channel_mentions else None
            if not channel:
                await message.reply(f"mention a channel: welcome config {setting} #channel")
                return
            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            if setting == "channel":
                settings["channel_id"] = str(channel.id)
                settings["enabled"] = True
            else:
                settings["goodbye_channel_id"] = str(channel.id)
                settings["goodbye_enabled"] = True
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            await message.reply(f"{setting} set to {channel.mention}.")
            return

        key = self.WELCOME_CONFIG_KEYS.get(setting)
        if key is None:
            await message.reply(
                f"unknown setting `{setting}`. (use /welcome config for the full list)"
            )
            return
        if not value:
            await message.reply(f"usage: welcome config {setting} <value>")
            return

        settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
        # 'reset'-style values normalize to the cleared state for the
        # style settings, matching the slash command's behavior
        if (value.strip().lower() in ("none", "reset", "disable", "off")
                and key in ("welcome_image", "welcome_title",
                            "welcome_footer", "dm_message")):
            settings[key] = None if key == "welcome_image" else ""
        else:
            settings[key] = value[:2000]
        await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
        await message.reply(f"{setting} updated.")

    async def _handle_welcome_show(self, message):
        """FIX 3 — prefix mirror of /welcome show: a compact text overview
        (the slash command shows the rich embed card)."""
        welcome_cog = self.bot.get_cog("Welcome")
        if not welcome_cog:
            await message.reply("welcome system not loaded.")
            return
        config = welcome_cog.get_config(message.guild.id)
        guild = message.guild

        def fmt_channel(eid):
            if not eid:
                return "not set"
            try:
                obj = guild.get_channel(int(eid))
                return obj.mention if obj else f"`{eid}` (not found)"
            except (ValueError, TypeError):
                return f"`{eid}` (invalid)"

        dm_msg = config.get('dm_message', '')
        lines = [
            f"**welcome:** {'on' if config.get('enabled') else 'off'} · {fmt_channel(config.get('channel_id'))}",
            f"**goodbye:** {'on' if config.get('goodbye_enabled') else 'off'} · {fmt_channel(config.get('goodbye_channel_id'))}",
            f"**mode:** {config.get('embed_mode', 'embed')} · **color:** {config.get('welcome_color', '#FFC0CB')}",
            f"**dm:** {'on' if dm_msg else 'off'}",
            f"**message:** {(config.get('message') or '')[:150]}",
        ]
        await message.reply(
            "**welcome config**\n" + "\n".join(lines) +
            "\n(use /welcome show for the rich preview card)"
        )

    async def _handle_welcome_test(self, message, args):
        """FIX 3 — optional type argument, same as /welcome test:
        welcome (default), goodbye, or dm. Renders through the Welcome cog
        so the preview matches what members actually see."""
        test_type = (args[0].lower() if args else "welcome")
        if test_type not in ("welcome", "goodbye", "dm"):
            await message.reply("usage: welcome test [welcome|goodbye|dm]")
            return
        if not message.author.guild_permissions.manage_guild:
            owner_id = int(os.getenv("OWNER_ID", "0"))
            if message.author.id != owner_id:
                await message.reply("no permission.")
                return
        welcome_cog = self.bot.get_cog("Welcome")
        if not welcome_cog:
            await message.reply("welcome system not loaded.")
            return
        config = welcome_cog.get_config(message.guild.id)

        if test_type == "dm":
            dm_msg = config.get('dm_message', '')
            if not dm_msg or dm_msg.lower() == 'off':
                await message.reply("welcome DM not configured. use welcome config dm <text> first.")
                return
            try:
                dm_text = welcome_cog._replace_variables(dm_msg, message.author, message.guild)
                await message.author.send(dm_text[:2000])
                await message.reply("test DM sent to your inbox.")
            except discord.Forbidden:
                await message.reply("couldn't DM you — your DMs are closed.")
            return

        if test_type == "welcome":
            cid = config.get('channel_id')
        else:
            cid = config.get('goodbye_channel_id') or config.get('channel_id')
        channel = message.guild.get_channel(int(cid)) if cid else None
        if not channel:
            setting = 'channel' if test_type == 'welcome' else 'goodbye_channel'
            await message.reply(
                f"no {test_type} channel set. use welcome config {setting} #channel first."
            )
            return
        success = await welcome_cog._send_welcome_message(
            channel, config, message.author, message.guild,
            is_goodbye=(test_type == "goodbye")
        )
        if success:
            await message.reply(f"test {test_type} sent to {channel.mention}.")
        else:
            await message.reply(f"failed to send test {test_type}.")

    # ─── Goodbye ──────────────────────────────────────────────────

    async def _handle_goodbye(self, message, args, args_str):
        sub = args[0].lower() if args else ""

        if sub == "message":
            prefix = await self._get_prefix(message.guild.id)
            match = re.match(
                rf'^{re.escape(prefix)}goodbye\s+message\s+',
                message.content,
                re.IGNORECASE
            )
            if match:
                text = message.content[match.end():]
            else:
                text = ""

            if not text:
                await message.reply("provide a message.")
                return

            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            settings["goodbye_message"] = text
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            await message.reply("goodbye message set.")
            return

        if sub == "channel":
            if not message.channel_mentions:
                await message.reply("mention a channel: goodbye channel #channel")
                return
            channel = message.channel_mentions[0]
            settings = await get_guild_setting_async(message.guild.id, "welcome_settings")
            settings["goodbye_channel_id"] = str(channel.id)
            settings["goodbye_enabled"] = True
            await set_guild_setting_async(message.guild.id, "welcome_settings", settings)
            await message.reply(f"goodbye channel set to {channel.mention}.")
            return

        await message.reply("usage: goodbye channel #channel | goodbye message [text]")

    # ─── Mod commands ─────────────────────────────────────────────

    async def _handle_mod(self, message, cmd, args, args_str):
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if not message.author.guild_permissions.manage_messages and message.author.id != owner_id:
            await message.reply("no permission.")
            return

        # PHASE 2B — Handle consolidated warnings command
        if cmd == "warnings":
            sub = args[0].lower() if args else ""
            if sub == "add" and message.mentions:
                target = message.mentions[0]
                reason = args_str.replace(f"<@{target.id}>", "").replace(f"<@!{target.id}>", "").replace("add", "").strip()
                reason = reason or "no reason provided"
                ai_cog = self.bot.get_cog("AIChat")
                if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
                    await ai_cog.handle_prefix_command(message, f"warn {target.mention} {reason}")
                return
            if sub == "list" and message.mentions:
                target = message.mentions[0]
                ai_cog = self.bot.get_cog("AIChat")
                if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
                    await ai_cog.handle_prefix_command(message, f"show warnings for {target.mention}")
                return
            if sub == "clear" and message.mentions:
                target = message.mentions[0]
                ai_cog = self.bot.get_cog("AIChat")
                if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
                    await ai_cog.handle_prefix_command(message, f"clear warnings for {target.mention}")
                return
            await message.reply("usage: warnings add @user [reason] | warnings list @user | warnings clear @user")
            return

        if cmd == "warn" and message.mentions:
            target = message.mentions[0]
            reason = args_str.replace(f"<@{target.id}>", "").replace(f"<@!{target.id}>", "").strip()
            reason = reason or "no reason provided"
            ai_cog = self.bot.get_cog("AIChat")
            if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
                await ai_cog.handle_prefix_command(message, f"warn {target.mention} {reason}")
            return

        if cmd == "purge" and args:
            try:
                amount = int(args[0])
                deleted = await message.channel.purge(limit=amount + 1)
                await message.channel.send(f"deleted {len(deleted) - 1} messages.", delete_after=3)
            except ValueError:
                await message.reply("usage: purge [amount]")
            return

        if cmd == "lock":
            try:
                overwrite = message.channel.overwrites_for(message.guild.default_role)
                overwrite.send_messages = False
                await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
                await message.reply("channel locked.")
            except discord.Forbidden:
                await message.reply("i don't have permission.")
            return

        if cmd == "unlock":
            try:
                overwrite = message.channel.overwrites_for(message.guild.default_role)
                overwrite.send_messages = None
                await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
                await message.reply("channel unlocked.")
            except discord.Forbidden:
                await message.reply("i don't have permission.")
            return

        if cmd == "slowmode" and args:
            try:
                seconds = int(args[0])
                await message.channel.edit(slowmode_delay=seconds)
                await message.reply(f"slowmode set to {seconds}s." if seconds > 0 else "slowmode disabled.")
            except ValueError:
                await message.reply("usage: slowmode [seconds]")
            return

        # ban/kick → pass to AI for confirmation flow
        ai_cog = self.bot.get_cog("AIChat")
        if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
            await ai_cog.handle_prefix_command(message, f"{cmd} {args_str}")

    # ─── Simple commands ──────────────────────────────────────────

    async def _handle_simple(self, message, cmd, args, args_str):
        if cmd == "help":
            prefix = await self._get_prefix(message.guild.id) or "@aurelia"
            help_text = (
                f"**aurelia commands** (prefix: `{prefix}`)\n"
                f"also available as slash commands (`/help` for full menu)\n\n"
                f"**AI Chat**\n"
                f"`{prefix}` + any question → talk to aurelia\n\n"
                f"**Welcome**\n"
                f"`{prefix}welcome config <setting> <value>`\n"
                f"`{prefix}welcome test [welcome|goodbye|dm]`\n"
                f"`{prefix}welcome show`\n"
                f"(use /welcome for full config options)\n\n"
                f"**Moderation**\n"
                f"`{prefix}warnings add @user [reason]`\n"
                f"`{prefix}warnings list @user`\n"
                f"`{prefix}warnings clear @user`\n"
                f"`{prefix}purge [amount]`\n"
                f"`{prefix}lock` / `{prefix}unlock`\n"
                f"`{prefix}slowmode [seconds]`\n\n"
                f"**Utility**\n"
                f"`{prefix}ping` — latency\n"
                f"`{prefix}uptime` — bot uptime\n"
                f"`{prefix}botinfo` — bot info\n"
                f"`{prefix}weather [city]` — weather\n"
                f"`{prefix}prefix set/remove/list` — manage prefix\n\n"
                f"**Fun**\n"
                f"`{prefix}joke` `{prefix}fact` `{prefix}meme`\n"
                f"`{prefix}flip` `{prefix}roll` `{prefix}truth` `{prefix}dare`\n"
            )
            await message.reply(help_text)
            return

        if cmd == "ping":
            latency = round(self.bot.latency * 1000)
            await message.reply(f"pong. {latency}ms")
            return

        if cmd == "uptime":
            import keep_alive
            from datetime import datetime
            if keep_alive.start_time:
                delta = datetime.utcnow() - keep_alive.start_time
                d = delta.days
                h = (delta.seconds % 86400) // 3600
                m = (delta.seconds % 3600) // 60
                await message.reply(f"uptime: {d}d {h}h {m}m")
            else:
                await message.reply("uptime unavailable.")
            return

        if cmd == "botinfo":
            await message.reply(
                f"aurelia — veloura's AI companion\n"
                f"servers: {len(self.bot.guilds)}\n"
                f"users: {sum(g.member_count for g in self.bot.guilds)}\n"
                f"latency: {round(self.bot.latency * 1000)}ms"
            )
            return

        # flip, roll, joke, fact, meme, truth, dare, weather → pass to AI
        ai_cog = self.bot.get_cog("AIChat")
        if ai_cog and hasattr(ai_cog, 'handle_prefix_command'):
            if cmd == "weather" and args:
                await ai_cog.handle_prefix_command(message, f"weather in {args_str}")
            else:
                await ai_cog.handle_prefix_command(message, cmd)

    # ─── Prefix management via text ───────────────────────────────

    async def _handle_prefix_cmd(self, message, args, args_str):
        if not message.author.guild_permissions.manage_guild:
            owner_id = int(os.getenv("OWNER_ID", "0"))
            if message.author.id != owner_id:
                # Still allow viewing
                prefix = await self._get_prefix(message.guild.id)
                if prefix:
                    await message.reply(f"current prefix: `{prefix}`")
                else:
                    await message.reply("no custom prefix set. use @mention.")
                return

        sub = args[0].lower() if args else ""

        if sub == "set" and len(args) > 1:
            new_prefix = args[1]
            if len(new_prefix) > 10:
                await message.reply("prefix too long — max 10 characters.")
                return
            # P1 — async write keeps the blocking REST call off the event loop
            await set_guild_setting_async(message.guild.id, "prefix_settings", {"prefix": new_prefix})
            self._invalidate_cache(message.guild.id)
            await message.reply(f"prefix set to `{new_prefix}`. use it like: `{new_prefix}hello`")
            return

        if sub == "remove":
            await set_guild_setting_async(message.guild.id, "prefix_settings", {"prefix": None})
            self._invalidate_cache(message.guild.id)
            await message.reply("custom prefix removed. use @mention to talk to aurelia.")
            return

        # Show current
        prefix = await self._get_prefix(message.guild.id)
        if prefix:
            await message.reply(f"current prefix: `{prefix}`\nusage: `{prefix}hello`")
        else:
            await message.reply("no custom prefix set. use @mention to talk to aurelia.")

    # ==================== /prefix slash command group ====================

    prefix_group = app_commands.Group(name="prefix", description="Custom prefix settings")

    @prefix_group.command(name="set", description="Set a custom prefix for AI chat")
    @app_commands.describe(prefix="The prefix (e.g. 'aurelia.' or 'a!')")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix_set(self, interaction: discord.Interaction, prefix: str):
        self.bot.increment_command('prefix_set')
        await interaction.response.defer(ephemeral=True)
        if len(prefix) > 10:
            await interaction.followup.send("prefix too long — max 10 characters.", ephemeral=True)
            return
        try:
            await set_guild_setting_async(interaction.guild_id, "prefix_settings", {"prefix": prefix})
            self._invalidate_cache(interaction.guild_id)
            await interaction.followup.send(
                f"✅ prefix set to `{prefix}`. use it like: `{prefix}hello`",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @prefix_group.command(name="remove", description="Remove the custom prefix")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def prefix_remove(self, interaction: discord.Interaction):
        self.bot.increment_command('prefix_remove')
        await interaction.response.defer(ephemeral=True)
        try:
            await set_guild_setting_async(interaction.guild_id, "prefix_settings", {"prefix": None})
            self._invalidate_cache(interaction.guild_id)
            await interaction.followup.send(
                "✅ custom prefix removed. use @mention to talk to aurelia.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"failed: `{e}`", ephemeral=True)

    @prefix_group.command(name="list", description="Show the current prefix for this server")
    async def prefix_list(self, interaction: discord.Interaction):
        self.bot.increment_command('prefix_list')
        await interaction.response.defer(ephemeral=True)
        prefix = await self._get_prefix(interaction.guild_id)
        if prefix:
            await interaction.followup.send(
                f"current prefix: `{prefix}`\nusage: `{prefix}hello`",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "no custom prefix set. use @mention to talk to aurelia.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Prefix(bot))
