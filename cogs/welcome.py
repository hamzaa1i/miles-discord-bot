"""cogs/welcome.py — welcome & goodbye system (Mimu-style).

Commands (FIX 3 — consolidated):
- /welcome config <setting> <value> [channel]  — ALL 13 config options in
  one command: channel, message, embed_mode, color, image, title,
  thumbnail, footer, dm, toggle, goodbye_channel, goodbye_message,
  goodbye_toggle
- /welcome test [type]   — preview welcome/goodbye/DM
- /welcome show          — rich overview of the current config
- /welcome tags          — every available tag + formatting tips
- /welcome reset         — factory reset (with confirmation button)
- /toggledms             — toggle DMs from aurelia

(The old /welcome set …, /welcome toggle, and /welcome goodbye …
subcommands — 17 subcommands total — were folded into /welcome config,
leaving 5 subcommands.)

FIX 1 — Config keys map to Supabase columns:
  welcome_channel  → channel_id
  welcome_message  → message
  welcome_toggle   → enabled
  goodbye_channel  → goodbye_channel_id
  goodbye_message  → goodbye_message
  goodbye_toggle   → goodbye_enabled
  welcome_dm       → dm_message
  embed_mode       → embed_mode
  welcome_image    → welcome_image
  welcome_color    → welcome_color (hex string, default #FFC0CB)

FIX 2 — All template rendering uses _replace_variables() (safe .replace()),
  never .format(), so user templates with unbalanced braces don't crash.

FIX 3 — Mimu-style advanced welcome:
  - Advanced tags: {user} {user.name} {user.id} {user.avatar}
    {server} {server.id} {membercount} {server.icon}
  - Hybrid send mode: split message at "---" separator, send first part
    as normal text + second part as embed
  - Embed modes: "embed" (default), "text", "hybrid"
  - welcome_image config: set a banner image URL for the embed
  - welcome_color config: custom embed color (hex like #FFC0CB);
    applied to the welcome embed in ALL embed modes (incl. hybrid),
    goodbye keeps its own soft pink
  - Member count in footer, user avatar as thumbnail
  - Literal \\n converted to real newlines
  - /welcome show carries the full Mimu-style tag reference + formatting tips
"""
import logging
import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional
from utils.database import Database
from utils.db import get_guild_setting, set_guild_setting

logger = logging.getLogger('cyn.welcome')

# Veloura aesthetic colors
COLOR_PINK = 0xFFC0CB
COLOR_GOODBYE = 0xFFB6C1
COLOR_CONFIG = 0x1a1a2e
FOOTER = "✩ ━━ aurelia ༉‧₊˚. ღ"

# Default welcome embed color (soft pink) — Mimu-style customizable via
# /welcome set color #RRGGBB
DEFAULT_WELCOME_COLOR = "#FFC0CB"

# PART 2 — default footer template. Supports every welcome tag
# ({membercount}, {server}, {user.name}, ...). Set to an empty string to
# remove the footer entirely.
DEFAULT_WELCOME_FOOTER = "{membercount} members ♡"


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/welcome.json')
        self.economy_db = Database('data/economy.json')
        self.dm_prefs_db = Database('data/dm_prefs.json')
        self.pending_welcomes = {}
        self.safe_mode_notified = set()

    def get_config(self, guild_id: int) -> dict:
        config = get_guild_setting(guild_id, "welcome_settings")
        if not config:
            return {
                'enabled': False,
                'channel_id': None,
                'message': 'Welcome {user} to {server}! You are member #{membercount}.',
                'goodbye_enabled': False,
                'goodbye_channel_id': None,
                'goodbye_message': "Goodbye {user}, we'll miss you.",
                'autorole_id': None,
                'welcome_reward': 500,
                'welcomer_reward': 1000,
                'embed_mode': 'embed',
                'dm_message': '',
                'welcome_image': None,
                'welcome_color': DEFAULT_WELCOME_COLOR,
                # PART 2 — new style settings (title / thumbnail / footer)
                'welcome_title': '',
                'welcome_thumbnail': 'avatar',
                'welcome_footer': DEFAULT_WELCOME_FOOTER,
            }
        config.setdefault('enabled', False)
        config.setdefault('channel_id', None)
        config.setdefault('message', 'Welcome {user} to {server}! You are member #{membercount}.')
        config.setdefault('goodbye_enabled', False)
        config.setdefault('goodbye_channel_id', None)
        config.setdefault('goodbye_message', "Goodbye {user}, we'll miss you.")
        config.setdefault('autorole_id', None)
        config.setdefault('welcome_reward', 500)
        config.setdefault('welcomer_reward', 1000)
        config.setdefault('embed_mode', 'embed')
        config.setdefault('dm_message', '')
        config.setdefault('welcome_image', None)
        config.setdefault('welcome_color', DEFAULT_WELCOME_COLOR)
        # PART 2 — new style settings
        config.setdefault('welcome_title', '')
        config.setdefault('welcome_thumbnail', 'avatar')
        config.setdefault('welcome_footer', DEFAULT_WELCOME_FOOTER)
        return config

    def wants_dms(self, user_id: int) -> bool:
        prefs = self.dm_prefs_db.get(str(user_id), {'dms_enabled': True})
        return prefs.get('dms_enabled', True)

    def disable_dms(self, user_id: int):
        self.dm_prefs_db.set(str(user_id), {'dms_enabled': False})

    def enable_dms(self, user_id: int):
        self.dm_prefs_db.set(str(user_id), {'dms_enabled': True})

    def get_economy_data(self, user_id: int) -> dict:
        return self.economy_db.get(str(user_id), {
            'balance': 0, 'bank': 0, 'total_earned': 0, 'inventory': []
        })

    def save_economy_data(self, user_id: int, data: dict):
        self.economy_db.set(str(user_id), data)

    def get_total_earned(self, user_id: int) -> int:
        return self.get_economy_data(user_id).get('total_earned', 0)

    # ─── FIX 2+3: Safe variable replacement (never .format()) ────

    def _replace_variables(self, template: str, member, guild) -> str:
        """Replace all {variable} tags in a user-provided template string.

        FIX 2 — Uses .replace() instead of .format() so unbalanced braces
        (e.g. '[membercount}' or '50% off}') don't crash with ValueError.

        FIX 3 — Supports Mimu-style advanced tags:
          {user}        → member mention (@user)
          {user.name}   → member username
          {user.id}     → member ID
          {user.avatar} → member avatar URL
          {server}      → server name
          {server.id}   → server ID
          {membercount} → total member count
          {server.icon} → server icon URL (empty if no icon)
        """
        if not template:
            return ""
        text = str(template)
        # FIX 3C — Convert literal "\n" (backslash-n as text) to newlines
        text = text.replace("\\n", "\n")
        # Advanced tags — order matters: replace {user.name} before {user}
        # so {user} doesn't eat the {user.name} prefix.
        text = text.replace("{user.name}", str(member.name))
        text = text.replace("{user.id}", str(member.id))
        text = text.replace("{user.avatar}", str(member.display_avatar.url))
        text = text.replace("{user}", member.mention)
        text = text.replace("{server.id}", str(guild.id))
        if guild.icon:
            text = text.replace("{server.icon}", str(guild.icon.url))
        else:
            text = text.replace("{server.icon}", "")
        text = text.replace("{server}", str(guild.name))
        text = text.replace("{membercount}", str(guild.member_count))
        return text

    # ─── FIX 3 (Mimu-style welcome_color) ────────────────────────

    @staticmethod
    def _parse_hex_color(value) -> Optional[int]:
        """Parse '#FFC0CB', '0xFFC0CB', 'FFC0CB', or short 'FCC' hex into an int.
        Returns None if the value isn't a valid color."""
        if value is None:
            return None
        s = str(value).strip().lstrip('#')
        if s.lower().startswith('0x'):
            s = s[2:]
        if len(s) == 3:  # expand short hex like 'FCC' → 'FFCCDD'-style
            s = ''.join(ch * 2 for ch in s)
        if len(s) != 6:
            return None
        try:
            return int(s, 16)
        except ValueError:
            return None

    def _get_welcome_color(self, config) -> int:
        """Resolve the configured welcome embed color to an int.
        Falls back to soft pink (0xFFC0CB) when unset or invalid."""
        parsed = self._parse_hex_color(config.get('welcome_color'))
        return parsed if parsed is not None else COLOR_PINK

    def _build_welcome_embed(self, text: str, member, guild, config=None,
                             is_goodbye: bool = False) -> discord.Embed:
        """PART 2 — build the veloura welcome/goodbye embed.

        Embed structure (fixes the old awkward vertical spacing):
          * title      — only when welcome_title is set (rendered with tags)
          * description — the rendered message text
          * thumbnail  — welcome_thumbnail mode: avatar (default) | server |
                         none | url:<URL>  (small image, no vertical space)
          * image      — the welcome_image banner, ONLY when configured
          * footer     — welcome_footer template (default
                         "{membercount} members ♡"), rendered with tags;
                         an empty string removes the footer entirely
        Goodbye keeps its own soft pink color and always uses the member
        avatar as thumbnail."""
        config = config or {}
        color = COLOR_GOODBYE if is_goodbye else self._get_welcome_color(config)
        embed = discord.Embed(description=text[:4096], color=color)

        # title — welcome only; goodbye has no title slot by default
        title = str(config.get('welcome_title') or '').strip()
        if title and not is_goodbye:
            rendered_title = self._replace_variables(title, member, guild)
            if rendered_title.strip():
                embed.title = rendered_title[:256]

        # thumbnail source
        thumb_mode = str(config.get('welcome_thumbnail') or 'avatar').strip().lower()
        thumb_url = None
        if is_goodbye or thumb_mode == 'avatar':
            thumb_url = member.display_avatar.url
        elif thumb_mode == 'server':
            thumb_url = (guild.icon.url if guild.icon
                         else member.display_avatar.url)
        elif thumb_mode == 'none':
            thumb_url = None
        elif thumb_mode.startswith('url:'):
            thumb_url = thumb_mode[4:].strip() or None
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        # footer — customizable template, rendered with all tags
        footer_tpl = config.get('welcome_footer')
        if footer_tpl is None:
            footer_tpl = DEFAULT_WELCOME_FOOTER
        footer_text = self._replace_variables(str(footer_tpl), member, guild)
        footer_text = footer_text.replace("\\n", " ").strip()
        if footer_text:
            embed.set_footer(text=footer_text[:2048])

        # banner image — only when one is configured
        image_url = config.get('welcome_image')
        if image_url:
            embed.set_image(url=image_url)
        return embed

    async def _send_welcome_message(self, channel, config, member, guild,
                                     is_goodbye=False):
        """FIX 3 — Send welcome/goodbye message using the configured embed mode.

        PART 2 — modes:
          "embed"  — entire message as embed description (default)
          "text"   — plain text, no embed
          "hybrid" — split at "---": BEFORE the separator is sent as plain
                     text (outside the embed), AFTER it becomes the embed
                     description. If the template has NO "---", hybrid is
                     treated as pure embed mode — the message is never
                     duplicated.

        The welcome embed uses the guild's configured color in every mode;
        goodbye keeps its own soft pink. See _build_welcome_embed for the
        title / thumbnail / footer / image styling.
        """
        if is_goodbye:
            template = config.get('goodbye_message', "Goodbye {user}, we'll miss you.")
        else:
            template = config.get('message', 'Welcome {user} to {server}!')

        text = self._replace_variables(template, member, guild)

        # For goodbye, also replace {duration}
        if is_goodbye:
            joined = member.joined_at
            if joined:
                delta = discord.utils.utcnow() - joined
                days = delta.days
                if days == 0:
                    hours = delta.seconds // 3600
                    duration_str = f"{hours} hour{'s' if hours != 1 else ''}" if hours > 0 else "just now"
                elif days == 1:
                    duration_str = "1 day"
                else:
                    duration_str = f"{days} days"
            else:
                duration_str = "some time"
            text = text.replace("{duration}", duration_str)

        embed_mode = config.get('embed_mode', 'embed')

        try:
            if embed_mode == "text":
                await channel.send(content=text[:2000])
            elif embed_mode in ("hybrid", "both"):
                # PART 2 — hybrid split: before "---" = plain content,
                # after "---" = embed description. No "---" → pure embed
                # (never duplicate the message in both content and embed).
                if "---" in text:
                    parts = text.split("---", 1)
                    normal_text = parts[0].strip()
                    embed_text = parts[1].strip()
                else:
                    normal_text = None
                    embed_text = text
                embed = self._build_welcome_embed(
                    embed_text, member, guild, config=config,
                    is_goodbye=is_goodbye,
                )
                await channel.send(content=normal_text[:2000] if normal_text else None,
                                   embed=embed)
            else:  # default "embed"
                embed = self._build_welcome_embed(
                    text, member, guild, config=config,
                    is_goodbye=is_goodbye,
                )
                await channel.send(embed=embed)
            return True
        except discord.Forbidden:
            logger.warning(f"[welcome] no permission to send in #{channel.name}")
        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning("[welcome] rate limited sending message")
            else:
                logger.error(f"[welcome] send failed: {e}")
        except Exception as e:
            logger.error(f"[welcome] send error: {e}")
        return False

    async def send_safe_mode_notification(self, user, guild, total_earned):
        if user.id in self.safe_mode_notified or total_earned < 10000 or not self.wants_dms(user.id):
            return
        self.safe_mode_notified.add(user.id)
        embed = discord.Embed(
            description=(
                f"Congrats on earning more than ⭐10,000 coins in **{guild.name}**!\n\n"
                f"Due to this, your economy safe mode is now **disabled**. "
                f"This means people can now `/rob` you.\n"
                f"Don't worry, you can `/rob` people back!\n\n"
                f"*You will not receive another DM about safe mode and it cannot be re-enabled.*"
            ),
            color=COLOR_CONFIG
        )
        embed.set_footer(text="Type /toggledms to disable future DMs from aurelia")
        try:
            await user.send(embed=embed)
        except:
            pass

    # ==================== LISTENERS ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        logger.info(
            f"[welcome] on_member_join fired for {member.display_name} "
            f"({member.id}) in guild {member.guild.id}"
        )
        logger.info(
            f"[welcome] settings: enabled={config.get('enabled')}, "
            f"channel_id={config.get('channel_id')}, "
            f"embed_mode={config.get('embed_mode')}, "
            f"welcome_image={'set' if config.get('welcome_image') else 'none'}"
        )

        # Autorole assignment
        autorole_id = config.get('autorole_id')
        if autorole_id:
            try:
                role = member.guild.get_role(int(autorole_id))
                if role:
                    await member.add_roles(role, reason="Autorole")
                    logger.info(f"[welcome] autorole {role.name} assigned to {member.display_name}")
            except Exception as e:
                logger.warning(f"[welcome] autorole failed: {e}")

        # Welcome message
        if config.get('enabled'):
            channel_id = config.get('channel_id')
            if channel_id:
                try:
                    channel = member.guild.get_channel(int(channel_id))
                except (TypeError, ValueError) as e:
                    logger.warning(f"[welcome] invalid channel_id '{channel_id}': {e}")
                    channel = None
                if channel:
                    success = await self._send_welcome_message(
                        channel, config, member, member.guild, is_goodbye=False
                    )
                    if success:
                        logger.info(f"[welcome] welcome message sent to #{channel.name}")
                else:
                    logger.warning(f"[welcome] channel_id {channel_id} not found in guild")
            else:
                logger.debug("[welcome] no channel_id configured")
        else:
            logger.debug("[welcome] welcome not enabled for this guild")

        # FIX 3 — Send custom DM message if configured (uses _replace_variables)
        dm_msg = config.get('dm_message', '')
        if dm_msg and dm_msg.lower() != 'off':
            try:
                dm_text = self._replace_variables(dm_msg, member, member.guild)
                await member.send(dm_text[:2000])
            except discord.Forbidden:
                pass
            except Exception:
                pass

        # Pending welcome (for welcomer rewards)
        self.pending_welcomes[member.id] = {
            'guild_id': member.guild.id,
            'joined_at': datetime.utcnow().isoformat(),
            'welcomed_by': [],
            'channel_id': config.get('channel_id')
        }

        # Welcome reward for new member
        reward = config.get('welcome_reward', 500)
        if reward:
            new_data = self.get_economy_data(member.id)
            new_data['balance'] = new_data.get('balance', 0) + reward
            new_data['total_earned'] = new_data.get('total_earned', 0) + reward
            self.save_economy_data(member.id, new_data)

        # DM new member
        if self.wants_dms(member.id):
            try:
                join_embed = discord.Embed(
                    description=(
                        f"hey, welcome to **{member.guild.name}**!\n\n"
                        f"you got **${reward:,}** just for joining.\n"
                        f"use `/daily`, `/work`, `/fish`, and more to earn coins.\n\n"
                        f"*type `/toggledms` if you don't want DMs from me.*"
                    ),
                    color=COLOR_CONFIG
                )
                await member.send(embed=join_embed)
            except:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        for mentioned in message.mentions:
            if mentioned.id not in self.pending_welcomes:
                continue
            pending = self.pending_welcomes[mentioned.id]
            if str(message.guild.id) != str(pending['guild_id']):
                continue
            if message.author.id == mentioned.id:
                continue
            if message.author.id in pending['welcomed_by']:
                continue
            welcome_words = ['welcome', 'wb', 'hey', 'hello', 'hi ', 'hii', 'sup', 'glad', 'join', 'greet', 'wsg', 'wsp']
            content_lower = message.content.lower()
            if not any(word in content_lower for word in welcome_words):
                continue
            config = self.get_config(message.guild.id)
            welcomer_reward = config.get('welcomer_reward', 1000)
            welcomer_data = self.get_economy_data(message.author.id)
            welcomer_data['balance'] = welcomer_data.get('balance', 0) + welcomer_reward
            welcomer_data['total_earned'] = welcomer_data.get('total_earned', 0) + welcomer_reward
            total_earned = welcomer_data['total_earned']
            self.save_economy_data(message.author.id, welcomer_data)
            pending['welcomed_by'].append(message.author.id)
            self.pending_welcomes[mentioned.id] = pending
            try:
                await message.add_reaction("🎉")
            except:
                pass
            if self.wants_dms(message.author.id):
                try:
                    dm_embed = discord.Embed(
                        description=(
                            f"Congrats **{message.author.display_name}** (@{message.author.name})!\n\n"
                            f"You earned **{welcomer_reward:,} coins** for welcoming in "
                            f"**{mentioned.display_name}** in **{message.guild.name}**! 🎉"
                        ),
                        color=COLOR_CONFIG
                    )
                    dm_embed.set_footer(text="Type /toggledms to disable these notifications")
                    await message.author.send(embed=dm_embed)
                except:
                    pass
            await self.send_safe_mode_notification(message.author, message.guild, total_earned)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        logger.info(
            f"[welcome] on_member_remove fired for {member.display_name} "
            f"({member.id}) in guild {member.guild.id}"
        )
        logger.info(
            f"[welcome] goodbye settings: goodbye_enabled={config.get('goodbye_enabled')}, "
            f"goodbye_channel_id={config.get('goodbye_channel_id')}"
        )
        if not config.get('goodbye_enabled'):
            logger.debug("[welcome] goodbye not enabled, skipping")
            return
        channel_id = config.get('goodbye_channel_id') or config.get('channel_id')
        if not channel_id:
            logger.warning("[welcome] no goodbye channel_id configured")
            return
        try:
            channel = member.guild.get_channel(int(channel_id))
        except (TypeError, ValueError) as e:
            logger.warning(f"[welcome] invalid goodbye channel_id '{channel_id}': {e}")
            return
        if not channel:
            logger.warning(f"[welcome] goodbye channel_id {channel_id} not found in guild")
            return
        if member.id in self.pending_welcomes:
            del self.pending_welcomes[member.id]
        success = await self._send_welcome_message(
            channel, config, member, member.guild, is_goodbye=True
        )
        if success:
            logger.info(f"[welcome] goodbye message sent to #{channel.name}")

    # ==================== STANDALONE COMMAND ====================
    @app_commands.command(name="toggledms", description="Toggle DMs from aurelia")
    async def toggledms(self, interaction: discord.Interaction):
        prefs = self.dm_prefs_db.get(str(interaction.user.id), {'dms_enabled': True})
        if prefs.get('dms_enabled', True):
            self.disable_dms(interaction.user.id); status, detail = "disabled", "you'll only get important DMs"
        else:
            self.enable_dms(interaction.user.id); status, detail = "enabled", "you'll get welcome rewards and notifications"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"DMs from aurelia are now **{status}**. {detail}.", color=COLOR_CONFIG), ephemeral=True)

    # ==================== WELCOME GROUP (FIX 3 consolidation) ====================
    # The PART 2 rework split configuration across 17 subcommands
    # (/welcome set channel|message|embed|color|image|title|thumbnail|footer|dm,
    # /welcome toggle, /welcome goodbye channel|message|toggle, plus
    # test/show/tags/reset). That inflated the command count and cluttered
    # autocomplete. FIX 3 folds the 13 config subcommands into ONE command:
    #
    #   /welcome config <setting> <value> [channel]  — 13 settings via choice
    #   /welcome test    — preview welcome/goodbye/DM
    #   /welcome show    — rich overview card
    #   /welcome tags    — variable reference
    #   /welcome reset   — factory reset (confirmation button)
    welcome = app_commands.Group(name="welcome", description="Configure welcome & goodbye messages")

    async def _err(self, itx: discord.Interaction, msg: str):
        await itx.response.send_message(msg, ephemeral=True)

    def _save_config(self, gid: int, config: dict, col_name: str, col_value):
        set_guild_setting(gid, "welcome_settings", config)
        logger.info(
            f"[welcome] SAVED welcome_settings for guild {gid}: "
            f"'{col_name}'='{str(col_value)[:80]}'"
        )

    def _resolve_channel_arg(self, guild, value, channel):
        """FIX 3 — resolve the target channel for the config command: the
        dedicated `channel` option wins; otherwise parse a <#id> mention or
        a raw numeric ID out of `value`. Returns a channel or None."""
        if channel is not None:
            return channel
        if value:
            v = value.strip()
            cid = None
            m = re.match(r'^<#(\d+)>$', v)
            if m:
                cid = int(m.group(1))
            elif v.isdigit() and len(v) >= 15:
                cid = int(v)
            if cid is not None and guild is not None:
                return guild.get_channel(cid)
        return None

    # ---- /welcome config — single-command configuration ──────────

    @welcome.command(name="config", description="Configure any welcome or goodbye setting")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        setting="Which setting to change",
        value="The new value — text, mode, hex color, URL, or on/off",
        channel="Target channel (only for the channel settings)",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Welcome Channel", value="channel"),
        app_commands.Choice(name="Welcome Message", value="message"),
        app_commands.Choice(name="Embed Mode (text/embed/hybrid)", value="embed_mode"),
        app_commands.Choice(name="Embed Color", value="color"),
        app_commands.Choice(name="Banner Image", value="image"),
        app_commands.Choice(name="Embed Title", value="title"),
        app_commands.Choice(name="Thumbnail (avatar/server/none/url)", value="thumbnail"),
        app_commands.Choice(name="Footer Text", value="footer"),
        app_commands.Choice(name="Welcome DM", value="dm"),
        app_commands.Choice(name="Welcome On/Off", value="toggle"),
        app_commands.Choice(name="Goodbye Channel", value="goodbye_channel"),
        app_commands.Choice(name="Goodbye Message", value="goodbye_message"),
        app_commands.Choice(name="Goodbye On/Off", value="goodbye_toggle"),
    ])
    async def welcome_config(self, interaction: discord.Interaction,
                             setting: app_commands.Choice[str],
                             value: Optional[str] = None,
                             channel: Optional[discord.TextChannel] = None):
        self.bot.increment_command('welcome_config')
        if not interaction.guild:
            return await self._err(interaction, "this command only works in servers.")
        # FIX 3 — dict dispatch: each setting's logic lives in its own
        # handler method (carried over from the old subcommands).
        handlers = {
            "channel": self._set_channel,
            "message": self._set_message,
            "embed_mode": self._set_embed_mode,
            "color": self._set_color,
            "image": self._set_image,
            "title": self._set_title,
            "thumbnail": self._set_thumbnail,
            "footer": self._set_footer,
            "dm": self._set_dm,
            "toggle": self._set_toggle,
            "goodbye_channel": self._set_goodbye_channel,
            "goodbye_message": self._set_goodbye_message,
            "goodbye_toggle": self._set_goodbye_toggle,
        }
        handler = handlers.get(setting.value)
        if handler is None:
            return await self._err(interaction, "❌ unknown setting.")
        await handler(interaction, value, channel)

    # ---- setting handlers (ported from the old /welcome set … subcommands) ----

    async def _set_channel(self, interaction, value, channel):
        gid = interaction.guild.id
        ch = self._resolve_channel_arg(interaction.guild, value, channel)
        if ch is None:
            return await self._err(
                interaction,
                "❌ mention a channel (use the `channel` option) or pass its "
                "ID / mention as `value`."
            )
        config = self.get_config(gid)
        config['channel_id'] = str(ch.id)
        config['enabled'] = True  # auto-enable welcome
        self._save_config(gid, config, 'channel_id', ch.id)
        await interaction.response.send_message(
            f"✅ welcome channel set to {ch.mention} — welcome messages **enabled**."
        )

    async def _set_message(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the message as `value` — tags: `{user}` `{server}` "
                "`{membercount}` (full list in `/welcome tags`)."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        config['message'] = value
        self._save_config(gid, config, 'message', value[:80])
        await interaction.response.send_message("✅ welcome message updated.")

    async def _set_embed_mode(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the mode as `value`: `text`, `embed`, or `hybrid`."
            )
        mode = value.strip().lower()
        if mode not in ("text", "embed", "hybrid"):
            return await self._err(
                interaction, "❌ mode must be `text`, `embed`, or `hybrid`."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        config['embed_mode'] = mode
        self._save_config(gid, config, 'embed_mode', mode)
        extra = (
            " — everything before `---` is sent as plain text, everything "
            "after it becomes the embed."
            if mode == "hybrid" else ""
        )
        await interaction.response.send_message(f"✅ embed mode set to **{mode}**{extra}")

    async def _set_color(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide a hex color as `value` (e.g. `#FFC0CB`) or `reset`."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        if value.strip().lower() in ("reset", "default", "off"):
            config['welcome_color'] = DEFAULT_WELCOME_COLOR
            self._save_config(gid, config, 'welcome_color', DEFAULT_WELCOME_COLOR)
            return await interaction.response.send_message(
                f"✅ welcome color reset to default **{DEFAULT_WELCOME_COLOR}**."
            )
        color_int = self._parse_hex_color(value)
        if color_int is None:
            return await self._err(
                interaction,
                "❌ invalid color. use hex like `#FFC0CB`, `#5865F2`, or `reset`."
            )
        normalized = "#" + value.strip().lstrip('#').upper()
        config['welcome_color'] = normalized
        self._save_config(gid, config, 'welcome_color', normalized)
        preview = discord.Embed(
            description=f"✅ welcome color set to **{normalized}**",
            color=color_int,
        )
        preview.set_footer(text=FOOTER)
        await interaction.response.send_message(embed=preview)

    async def _set_image(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide an image URL as `value`, or `reset` to remove the banner."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        if value.strip().lower() in ("reset", "off", "none"):
            config['welcome_image'] = None
            self._save_config(gid, config, 'welcome_image', '(removed)')
            return await interaction.response.send_message("✅ welcome image removed.")
        if not value.startswith(("http://", "https://")):
            return await self._err(
                interaction, "❌ image URL must start with `http://` or `https://`."
            )
        config['welcome_image'] = value[:500]
        self._save_config(gid, config, 'welcome_image', value[:80])
        await interaction.response.send_message("✅ welcome image updated.")

    async def _set_title(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the title as `value` (tags supported), or `reset` to remove it."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        if value.strip().lower() in ("reset", "off", "none"):
            config['welcome_title'] = ''
            self._save_config(gid, config, 'welcome_title', '(removed)')
            return await interaction.response.send_message("✅ welcome title removed.")
        config['welcome_title'] = value[:256]
        self._save_config(gid, config, 'welcome_title', value[:80])
        await interaction.response.send_message(
            f"✅ welcome title set to **{value[:100]}**."
        )

    async def _set_thumbnail(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the mode as `value`: `avatar`, `server`, `none`, "
                "or an image URL."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        v = value.strip()
        if v.lower() in ("reset", "avatar", "default"):
            config['welcome_thumbnail'] = 'avatar'
            self._save_config(gid, config, 'welcome_thumbnail', 'avatar')
            return await interaction.response.send_message(
                "✅ welcome thumbnail set to **avatar**."
            )
        if v.lower() == "server":
            config['welcome_thumbnail'] = 'server'
            self._save_config(gid, config, 'welcome_thumbnail', 'server')
            return await interaction.response.send_message(
                "✅ welcome thumbnail set to the **server icon**."
            )
        if v.lower() in ("none", "off"):
            config['welcome_thumbnail'] = 'none'
            self._save_config(gid, config, 'welcome_thumbnail', 'none')
            return await interaction.response.send_message("✅ welcome thumbnail removed.")
        if v.startswith(("http://", "https://")):
            config['welcome_thumbnail'] = f"url:{v[:500]}"
            self._save_config(gid, config, 'welcome_thumbnail', v[:80])
            return await interaction.response.send_message(
                "✅ welcome thumbnail set to your URL."
            )
        return await self._err(
            interaction,
            "❌ thumbnail must be `avatar`, `server`, `none`, or an image URL."
        )

    async def _set_footer(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the footer as `value` (tags supported), `reset` for "
                "the default, or `none` to remove it."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        if value.strip().lower() in ("reset", "default"):
            config['welcome_footer'] = DEFAULT_WELCOME_FOOTER
            self._save_config(gid, config, 'welcome_footer', DEFAULT_WELCOME_FOOTER)
            return await interaction.response.send_message(
                f"✅ footer reset to default: **{DEFAULT_WELCOME_FOOTER}**"
            )
        if value.strip().lower() in ("none", "off", "empty"):
            config['welcome_footer'] = ""
            self._save_config(gid, config, 'welcome_footer', '(removed)')
            return await interaction.response.send_message("✅ footer removed.")
        config['welcome_footer'] = value[:2000]
        self._save_config(gid, config, 'welcome_footer', value[:80])
        rendered = self._replace_variables(value, interaction.user, interaction.guild)
        await interaction.response.send_message(
            f"✅ footer updated — preview: **{rendered[:150]}**"
        )

    async def _set_dm(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the DM text as `value` (tags supported), or `disable`."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        if value.strip().lower() in ("disable", "off", "none"):
            config['dm_message'] = ''
            self._save_config(gid, config, 'dm_message', '(disabled)')
            return await interaction.response.send_message("✅ welcome DM disabled.")
        config['dm_message'] = value[:1000]
        self._save_config(gid, config, 'dm_message', value[:80])
        preview = self._replace_variables(value, interaction.user, interaction.guild)
        await interaction.response.send_message(
            f"✅ welcome DM updated.\npreview: {preview[:500]}"
        )

    async def _set_toggle(self, interaction, value, channel):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(interaction, "❌ provide `on` or `off` as `value`.")
        gid = interaction.guild.id
        config = self.get_config(gid)
        state = value.strip().lower()
        config['enabled'] = (state == "on")
        self._save_config(gid, config, 'enabled', state)
        warn = ""
        if config['enabled'] and not config.get('channel_id'):
            warn = "\n⚠️ no channel set — use `/welcome config setting:channel` first."
        await interaction.response.send_message(f"✅ welcome messages **{state}**.{warn}")

    async def _set_goodbye_channel(self, interaction, value, channel):
        gid = interaction.guild.id
        ch = self._resolve_channel_arg(interaction.guild, value, channel)
        if ch is None:
            return await self._err(
                interaction,
                "❌ mention a channel (use the `channel` option) or pass its "
                "ID / mention as `value`."
            )
        config = self.get_config(gid)
        config['goodbye_channel_id'] = str(ch.id)
        config['goodbye_enabled'] = True  # auto-enable goodbye
        self._save_config(gid, config, 'goodbye_channel_id', ch.id)
        await interaction.response.send_message(
            f"✅ goodbye channel set to {ch.mention} — goodbye messages **enabled**."
        )

    async def _set_goodbye_message(self, interaction, value, channel):
        if not value or not value.strip():
            return await self._err(
                interaction,
                "❌ provide the message as `value` — tags: `{user}` `{server}` "
                "`{membercount}` `{duration}`."
            )
        gid = interaction.guild.id
        config = self.get_config(gid)
        config['goodbye_message'] = value
        self._save_config(gid, config, 'goodbye_message', value[:80])
        await interaction.response.send_message("✅ goodbye message updated.")

    async def _set_goodbye_toggle(self, interaction, value, channel):
        if not value or value.strip().lower() not in ("on", "off"):
            return await self._err(interaction, "❌ provide `on` or `off` as `value`.")
        gid = interaction.guild.id
        config = self.get_config(gid)
        state = value.strip().lower()
        config['goodbye_enabled'] = (state == "on")
        self._save_config(gid, config, 'goodbye_enabled', state)
        warn = ""
        if config['goodbye_enabled'] and not config.get('goodbye_channel_id'):
            warn = "\n⚠️ no channel set — use `/welcome config setting:goodbye_channel` first."
        await interaction.response.send_message(f"✅ goodbye messages **{state}**.{warn}")

    # ---- /welcome test ────────────────────────────────────────────
    # S2 — manage_guild required: previews post to the real welcome channel,
    # so this is a moderator action, not a curiosity command.
    @welcome.command(name="test", description="Preview the welcome, goodbye, or DM message")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(type="Which message type to test (defaults to welcome)")
    @app_commands.choices(type=[
        app_commands.Choice(name="Welcome", value="welcome"),
        app_commands.Choice(name="Goodbye", value="goodbye"),
        app_commands.Choice(name="DM", value="dm"),
    ])
    async def welcome_test(self, interaction: discord.Interaction,
                           type: Optional[app_commands.Choice[str]] = None):
        self.bot.increment_command('welcome_test')
        config = self.get_config(interaction.guild.id)
        member = interaction.user
        # type is optional — defaults to a welcome preview
        type_value = (type.value if type else "welcome")

        if type_value in ("welcome", "goodbye"):
            if type_value == "welcome":
                cid = config.get('channel_id')
            else:
                cid = config.get('goodbye_channel_id') or config.get('channel_id')
            channel = interaction.guild.get_channel(int(cid)) if cid else None
            if not channel:
                return await self._err(
                    interaction,
                    f"❌ {type_value} channel not set. use "
                    f"`/welcome config setting:channel` (or `setting:goodbye_channel`) first."
                )
            is_goodbye = (type_value == "goodbye")
            success = await self._send_welcome_message(
                channel, config, member, interaction.guild, is_goodbye=is_goodbye
            )
            if success:
                await interaction.response.send_message(
                    f"✅ test {type_value} sent to {channel.mention}"
                )
            else:
                await self._err(interaction, f"❌ failed to send test {type_value}.")
            return

        if type_value == "dm":
            dm_msg = config.get('dm_message', '')
            if not dm_msg or dm_msg.lower() == 'off':
                return await self._err(
                    interaction,
                    "❌ welcome DM not configured. use `/welcome config setting:dm` first."
                )
            try:
                dm_text = self._replace_variables(dm_msg, member, interaction.guild)
                await member.send(dm_text[:2000])
                await interaction.response.send_message(
                    "✅ test DM sent to your inbox.", ephemeral=True
                )
            except discord.Forbidden:
                await self._err(interaction, "❌ couldn't DM you — your DMs are closed.")
            except Exception as e:
                await self._err(interaction, f"❌ failed: {e}")

    # ---- /welcome show — rich preview card ────────────────────────
    @welcome.command(name="show", description="Overview of the current welcome config")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_show(self, interaction: discord.Interaction):
        self.bot.increment_command('welcome_show')
        config = self.get_config(interaction.guild.id)
        g = interaction.guild

        def fmt_channel(eid):
            if not eid:
                return "*not set*"
            try:
                eid_int = int(eid)
            except (ValueError, TypeError):
                return f"`{eid}` (invalid)"
            obj = g.get_channel(eid_int)
            return obj.mention if obj else f"`{eid}` (not found)"

        dm_msg = config.get('dm_message', '')
        dm_enabled = bool(dm_msg) and dm_msg.lower() != 'off'
        # rendered message preview (first 200 chars)
        try:
            preview = self._replace_variables(
                config.get('message') or '', interaction.user, g
            )
        except Exception:
            preview = config.get('message') or ''
        if not preview:
            preview = "*(empty)*"
        preview = preview[:200] + ("..." if len(preview) > 200 else "")

        color_value = self._get_welcome_color(config)
        embed = discord.Embed(
            title="✩ welcome config",
            color=color_value,  # the embed color IS the color swatch
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="use /welcome test to preview · ✩ ━━ aurelia ༉‧₊˚. ღ")
        embed.add_field(
            name="🎉 welcome",
            inline=False,
            value=(
                f"**enabled:** `{config.get('enabled', False)}`\n"
                f"**channel:** {fmt_channel(config.get('channel_id'))}\n"
                f"**mode:** `{config.get('embed_mode', 'embed')}`"
            ),
        )
        embed.add_field(
            name="👋 goodbye",
            inline=False,
            value=(
                f"**enabled:** `{config.get('goodbye_enabled', False)}`\n"
                f"**channel:** {fmt_channel(config.get('goodbye_channel_id'))}"
            ),
        )
        embed.add_field(
            name="✉️ dm",
            inline=False,
            value=f"**enabled:** `{dm_enabled}`",
        )
        embed.add_field(
            name="🎨 style",
            inline=False,
            value=(
                f"**color:** `{config.get('welcome_color', DEFAULT_WELCOME_COLOR)}`\n"
                f"**title:** `{(config.get('welcome_title') or '—')[:60]}`\n"
                f"**thumbnail:** `{config.get('welcome_thumbnail', 'avatar')}`\n"
                f"**image:** `{(config.get('welcome_image') or '—')[:60]}`\n"
                f"**footer:** `{(str(config.get('welcome_footer')) if config.get('welcome_footer') is not None else DEFAULT_WELCOME_FOOTER)[:60]}`"
            ),
        )
        embed.add_field(
            name="💬 message preview",
            inline=False,
            value=f"```\n{preview}\n```",
        )
        await interaction.response.send_message(embed=embed)

    # ---- /welcome tags ────────────────────────────────────────────
    @welcome.command(name="tags", description="Every tag you can use in welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_tags(self, interaction: discord.Interaction):
        self.bot.increment_command('welcome_tags')
        embed = discord.Embed(
            title="📝 welcome tag reference",
            color=COLOR_CONFIG,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Available tags", inline=False, value=(
            "```\n"
            "{user} — mention the new member\n"
            "{user.name} — member's username\n"
            "{user.id} — member's Discord ID\n"
            "{user.avatar} — member's avatar URL\n"
            "{server} — server name\n"
            "{server.id} — server ID\n"
            "{membercount} — total member count\n"
            "{server.icon} — server icon URL\n"
            "{duration} — how long they stayed (goodbye only)\n"
            "```"
        ))
        embed.add_field(name="Formatting tips", inline=False, value=(
            "```\n"
            "• Use \\n for line breaks in your message\n"
            "• Use --- to separate plain text from embed (hybrid mode)\n"
            "• <#channelid> renders as a clickable channel link in embeds\n"
            "• [text](https://discord.com/channels/GUILD/CHANNEL) for named links\n"
            "• /welcome config embed_mode hybrid — Mimu-style text + embed\n"
            "• /welcome config image <url> — banner at the bottom of the embed\n"
            "• /welcome config color #FFC0CB — custom embed color\n"
            "• /welcome config footer none — remove the footer entirely\n"
            "```"
        ))
        embed.set_footer(text="✩ ━━ aurelia ༉‧₊˚. ღ")
        await interaction.response.send_message(embed=embed)

    # ---- /welcome reset — with confirmation button ────────────────
    @welcome.command(name="reset", description="Reset ALL welcome settings to defaults")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_reset(self, interaction: discord.Interaction):
        self.bot.increment_command('welcome_reset')
        view = WelcomeResetView(interaction.user.id, self)
        await interaction.response.send_message(
            "⚠️ this wipes **every** welcome & goodbye setting for this server "
            "(channel, messages, style — everything) and cannot be undone.\n"
            "are you sure?",
            view=view,
            ephemeral=True,
        )


class WelcomeResetView(discord.ui.View):
    """PART 2 — confirmation buttons for /welcome reset."""

    def __init__(self, author_id: int, cog: "Welcome"):
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

    @discord.ui.button(label="reset everything", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        try:
            # factory defaults: get_config(guild 0) is never configured, so
            # it returns the pure default dict — write it over the guild row.
            defaults = self.cog.get_config(0)
            set_guild_setting(interaction.guild.id, "welcome_settings", defaults)
            logger.info(
                f"[welcome] RESET all settings for guild {interaction.guild.id}"
            )
        except Exception as e:
            logger.error(f"[welcome] reset failed: {e}")
            await interaction.response.edit_message(
                content="couldn't reset — try again.", view=None
            )
            return
        await interaction.response.edit_message(
            content="✅ every welcome setting is back to defaults. configure "
                    "again with `/welcome config setting:channel <#channel>`.",
            view=None,
        )

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        await interaction.response.edit_message(content="cancelled.", view=None)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
