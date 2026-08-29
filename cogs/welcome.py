"""cogs/welcome.py — welcome & goodbye system (Mimu-style).

Commands:
- /welcome config [setting] [value?] [channel?] — view/change any setting
- /welcome test [type]   — preview welcome/goodbye/DM
- /welcome show          — show current config + available tags
- /toggledms             — toggle DMs from aurelia

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

FIX 2 — All template rendering uses _replace_variables() (safe .replace()),
  never .format(), so user templates with unbalanced braces don't crash.

FIX 3 — Mimu-style advanced welcome:
  - Advanced tags: {user} {user.name} {user.id} {user.avatar}
    {server} {server.id} {membercount} {server.icon}
  - Hybrid send mode: split message at "---" separator, send first part
    as normal text + second part as embed
  - Embed modes: "embed" (default), "text", "hybrid"
  - welcome_image config: set a banner image URL for the embed
  - Member count in footer, user avatar as thumbnail
  - Literal \\n converted to real newlines
"""
import logging
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

    def _build_welcome_embed(self, text: str, member, guild, image_url=None,
                             color=COLOR_PINK) -> discord.Embed:
        """FIX 3 — Build a Veloura-aesthetic embed for welcome/goodbye."""
        embed = discord.Embed(description=text[:4096], color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{guild.member_count} members ♡")
        if image_url:
            embed.set_image(url=image_url)
        return embed

    async def _send_welcome_message(self, channel, config, member, guild,
                                     is_goodbye=False):
        """FIX 3 — Send welcome/goodbye message using the configured embed mode.

        Supports three modes:
          "embed"  — entire message as embed description (default)
          "text"   — plain text, no embed
          "hybrid" — split at "---", first part as text + second as embed
        """
        if is_goodbye:
            template = config.get('goodbye_message', "Goodbye {user}, we'll miss you.")
            color = COLOR_GOODBYE
        else:
            template = config.get('message', 'Welcome {user} to {server}!')
            color = COLOR_PINK

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
        image_url = config.get('welcome_image')

        try:
            if embed_mode == "text":
                await channel.send(content=text[:2000])
            elif embed_mode in ("hybrid", "both"):
                if "---" in text:
                    parts = text.split("---", 1)
                    normal_text = parts[0].strip()
                    embed_text = parts[1].strip()
                else:
                    normal_text = None
                    embed_text = text
                embed = self._build_welcome_embed(embed_text, member, guild,
                                                   image_url=image_url, color=color)
                await channel.send(content=normal_text[:2000] if normal_text else None,
                                   embed=embed)
            else:  # default "embed"
                embed = self._build_welcome_embed(text, member, guild,
                                                   image_url=image_url, color=color)
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

    # ==================== WELCOME GROUP (consolidated) ====================
    welcome = app_commands.Group(name="welcome", description="Configure welcome & goodbye messages")

    async def _err(self, itx: discord.Interaction, msg: str):
        await itx.response.send_message(msg, ephemeral=True)

    # ---- /welcome config ----
    @welcome.command(name="config", description="View or change a welcome/goodbye setting")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        setting="Which setting to view or change",
        value="Toggles: on/off • embed_mode: embed/text/hybrid • image URL for welcome_image",
        channel="Required only for welcome_channel / goodbye_channel",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Welcome Channel", value="welcome_channel"),
        app_commands.Choice(name="Welcome Message", value="welcome_message"),
        app_commands.Choice(name="Welcome DM", value="welcome_dm"),
        app_commands.Choice(name="Welcome Toggle", value="welcome_toggle"),
        app_commands.Choice(name="Goodbye Channel", value="goodbye_channel"),
        app_commands.Choice(name="Goodbye Message", value="goodbye_message"),
        app_commands.Choice(name="Goodbye Toggle", value="goodbye_toggle"),
        app_commands.Choice(name="Embed Mode", value="embed_mode"),
        app_commands.Choice(name="Welcome Image", value="welcome_image"),
    ])
    async def welcome_config(self, interaction: discord.Interaction, setting: app_commands.Choice[str], value: Optional[str] = None, channel: Optional[discord.TextChannel] = None):
        config = self.get_config(interaction.guild.id)
        gid = interaction.guild.id
        key, name = setting.value, setting.name
        bool_words = {"on": True, "true": True, "yes": True, "off": False, "false": False, "no": False}

        # FIX 1 — Explicit mapping from user-facing setting names to Supabase column names.
        SETTING_TO_COLUMN = {
            "welcome_channel": "channel_id",
            "welcome_message": "message",
            "welcome_toggle": "enabled",
            "goodbye_channel": "goodbye_channel_id",
            "goodbye_message": "goodbye_message",
            "goodbye_toggle": "goodbye_enabled",
            "welcome_dm": "dm_message",
            "embed_mode": "embed_mode",
            "welcome_image": "welcome_image",
        }
        column_name = SETTING_TO_COLUMN.get(key, key)

        async def _save_and_verify(cfg, col_name, col_value):
            set_guild_setting(gid, "welcome_settings", cfg)
            logger.info(
                f"[welcome] SAVED to welcome_settings for guild {gid}: "
                f"column '{col_name}'='{col_value}' "
                f"(full config keys: {list(cfg.keys())})"
            )
            readback = get_guild_setting(gid, "welcome_settings")
            logger.info(
                f"[welcome] READBACK from welcome_settings for guild {gid}: "
                f"enabled={readback.get('enabled') if readback else 'NONE'}, "
                f"channel_id={readback.get('channel_id') if readback else 'NONE'}, "
                f"message={str(readback.get('message', ''))[:60] if readback else 'NONE'}, "
                f"goodbye_enabled={readback.get('goodbye_enabled') if readback else 'NONE'}, "
                f"goodbye_channel_id={readback.get('goodbye_channel_id') if readback else 'NONE'}, "
                f"dm_message={str(readback.get('dm_message', ''))[:60] if readback else 'NONE'}, "
                f"embed_mode={readback.get('embed_mode') if readback else 'NONE'}, "
                f"welcome_image={str(readback.get('welcome_image', ''))[:60] if readback else 'NONE'}"
            )

        # Channel-based settings
        if key in ("welcome_channel", "goodbye_channel"):
            if channel is None:
                return await self._err(interaction, f"❌ Provide a `channel` for **{name}**.")
            if key == "welcome_channel":
                config['channel_id'] = str(channel.id)
                config['enabled'] = True  # auto-enable welcome
            else:
                config['goodbye_channel_id'] = str(channel.id)
                config['goodbye_enabled'] = True  # auto-enable goodbye
            await _save_and_verify(config, column_name, str(channel.id))
            return await interaction.response.send_message(f"✅ {name} set to {channel.mention}")

        # Toggle-based settings
        if key in ("welcome_toggle", "goodbye_toggle"):
            if value is None:
                return await self._err(interaction, f"❌ Provide `value` (on/off) for **{name}**.")
            parsed = value.strip().lower()
            if parsed not in bool_words:
                return await self._err(interaction, f"❌ Invalid `{value}`. Use on/off, true/false, yes/no.")
            enabled = bool_words[parsed]
            config['enabled' if key == "welcome_toggle" else 'goodbye_enabled'] = enabled
            await _save_and_verify(config, column_name, enabled)
            return await interaction.response.send_message(f"✅ {name} **{'enabled' if enabled else 'disabled'}**")

        # Embed mode (now supports hybrid)
        if key == "embed_mode":
            if value is None:
                return await self._err(interaction, "❌ Provide `value` (`embed`, `text`, or `hybrid`).")
            parsed = value.strip().lower()
            if parsed not in ("embed", "text", "hybrid", "both"):
                return await self._err(interaction, f"❌ Invalid `{value}`. Use `embed`, `text`, or `hybrid`.")
            if parsed == "both":
                parsed = "hybrid"
            config['embed_mode'] = parsed
            await _save_and_verify(config, column_name, parsed)
            return await interaction.response.send_message(f"✅ Embed mode set to **{parsed}**")

        # Welcome image URL
        if key == "welcome_image":
            if value is None:
                return await self._err(interaction, "❌ Provide `value` (image URL) or `off` to disable.")
            if value.strip().lower() == "off":
                config['welcome_image'] = None
                await _save_and_verify(config, column_name, "(disabled)")
                return await interaction.response.send_message("✅ Welcome image disabled.")
            # Basic URL validation
            if not value.startswith("http://") and not value.startswith("https://"):
                return await self._err(interaction, "❌ Image URL must start with `http://` or `https://`.")
            config['welcome_image'] = value[:500]
            await _save_and_verify(config, column_name, value[:80])
            return await interaction.response.send_message(f"✅ Welcome image set.\nURL: {value[:200]}")

        # Text-based settings (welcome_message / goodbye_message / welcome_dm)
        text_cfg = {
            "welcome_message": ("message", "`{user}` `{server}` `{membercount}` `{user.name}` `{user.id}` `{user.avatar}` `{server.id}` `{server.icon}`"),
            "goodbye_message": ("goodbye_message", "`{user}` `{server}` `{membercount}` `{duration}`"),
            "welcome_dm": ("dm_message", "`{user}` `{server}`"),
        }
        if key in text_cfg:
            if value is None:
                return await self._err(interaction, f"ℹ️ Provide `value` for **{name}**.")
            cfg_key, vars_str = text_cfg[key]
            is_dm = key == "welcome_dm"
            if is_dm and value.lower() == "off":
                config[cfg_key] = ""
                await _save_and_verify(config, cfg_key, "(disabled)")
                return await interaction.response.send_message("✅ Welcome DM disabled.")
            # FIX 3C — Convert literal \n to real newlines before saving
            saved_value = value[:1000] if is_dm else value
            config[cfg_key] = saved_value
            await _save_and_verify(config, cfg_key, saved_value[:80])
            if is_dm:
                preview = self._replace_variables(value, interaction.user, interaction.guild)
                return await interaction.response.send_message(f"✅ Welcome DM set. Variables: {vars_str}\nPreview: {preview[:500]}")
            return await interaction.response.send_message(f"✅ {name} set.\nVariables: {vars_str}")

    # ---- /welcome test ----
    # S2 — manage_guild required: previews post to the real welcome channel,
    # so this is a moderator action, not a curiosity command.
    @welcome.command(name="test", description="Preview welcome, goodbye, or DM message")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(type="Which message type to test")
    @app_commands.choices(type=[
        app_commands.Choice(name="Welcome", value="welcome"),
        app_commands.Choice(name="Goodbye", value="goodbye"),
        app_commands.Choice(name="DM", value="dm"),
    ])
    async def welcome_test(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        config = self.get_config(interaction.guild.id)
        member = interaction.user

        if type.value in ("welcome", "goodbye"):
            if type.value == "welcome":
                cid = config.get('channel_id')
            else:
                cid = config.get('goodbye_channel_id') or config.get('channel_id')
            channel = interaction.guild.get_channel(int(cid)) if cid else None
            if not channel:
                return await self._err(interaction, f"❌ {type.name} channel not set. Use `/welcome config` first.")
            is_goodbye = (type.value == "goodbye")
            success = await self._send_welcome_message(
                channel, config, member, interaction.guild, is_goodbye=is_goodbye
            )
            if success:
                await interaction.response.send_message(f"✅ Test {type.value} sent to {channel.mention}")
            else:
                await self._err(interaction, f"❌ Failed to send test {type.value}.")
            return

        if type.value == "dm":
            dm_msg = config.get('dm_message', '')
            if not dm_msg or dm_msg.lower() == 'off':
                return await self._err(interaction, "❌ Welcome DM not configured. Use `/welcome config setting: Welcome DM` first.")
            try:
                dm_text = self._replace_variables(dm_msg, member, interaction.guild)
                await member.send(dm_text[:2000])
                await interaction.response.send_message("✅ Test DM sent to your inbox.", ephemeral=True)
            except discord.Forbidden:
                await self._err(interaction, "❌ Couldn't DM you — your DMs are closed.")
            except Exception as e:
                await self._err(interaction, f"❌ Failed: {e}")

    # ---- /welcome show ----
    # S2 — manage_guild required: config preview can reveal DM templates
    # and reward settings meant for staff.
    @welcome.command(name="show", description="Show the current welcome & goodbye configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_show(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)
        logger.info(
            f"[welcome] SHOW reading welcome_settings for guild {interaction.guild.id}: "
            f"enabled={config.get('enabled')}, "
            f"channel_id={config.get('channel_id')}, "
            f"goodbye_enabled={config.get('goodbye_enabled')}, "
            f"goodbye_channel_id={config.get('goodbye_channel_id')}, "
            f"embed_mode={config.get('embed_mode')}, "
            f"welcome_image={'set' if config.get('welcome_image') else 'none'}"
        )
        g = interaction.guild

        def fmt(kind, eid):
            if not eid: return "*not set*"
            try: eid_int = int(eid)
            except (ValueError, TypeError): return f"`{eid}` (invalid)"
            obj = g.get_channel(eid_int) if kind == "channel" else g.get_role(eid_int)
            return obj.mention if obj else f"`{eid}` (not found)"

        def fmt_msg(msg, fallback):
            text = msg or fallback
            if len(text) > 200: text = text[:197] + "..."
            return f"```\n{text}\n```"

        default_goodbye = "Goodbye {user}, we'll miss you."
        default_welcome = 'Welcome {user} to {server}! You are member #{membercount}.'
        dm_msg = config.get('dm_message', '')
        dm_enabled = bool(dm_msg) and dm_msg.lower() != 'off'
        image_url = config.get('welcome_image')
        embed = discord.Embed(title="📋 Welcome & Goodbye Configuration", color=COLOR_CONFIG, timestamp=datetime.utcnow())
        embed.set_footer(text=f"Guild: {g.name}")
        embed.add_field(name="🎉 Welcome", inline=False, value=f"**Enabled:** `{config.get('enabled', False)}`\n**Channel:** {fmt('channel', config.get('channel_id'))}\n**Message:** {fmt_msg(config.get('message'), default_welcome)}")
        embed.add_field(name="👋 Goodbye", inline=False, value=f"**Enabled:** `{config.get('goodbye_enabled', False)}`\n**Channel:** {fmt('channel', config.get('goodbye_channel_id'))}\n**Message:** {fmt_msg(config.get('goodbye_message'), default_goodbye)}")
        embed.add_field(name="✉️ Welcome DM", inline=False, value=f"**Enabled:** `{dm_enabled}`\n**Message:** {fmt_msg(dm_msg, '(disabled)') if dm_msg else '*(disabled)*'}")
        embed.add_field(name="⚙️ Other", inline=False, value=f"**Embed Mode:** `{config.get('embed_mode', 'embed')}`\n**Welcome Image:** `{image_url[:80] + '...' if image_url and len(image_url) > 80 else image_url or 'not set'}`\n**Welcome Reward:** `${config.get('welcome_reward', 500):,}`\n**Welcomer Reward:** `${config.get('welcomer_reward', 1000):,}`\n**Autorole:** {fmt('role', config.get('autorole_id'))}")
        embed.add_field(name="📝 Available Tags", inline=False, value=(
            "```\n"
            "Tags: {user} {user.name} {user.id} {user.avatar}\n"
            "{server} {server.id} {membercount} {server.icon}\n"
            "{duration} (goodbye only)\n\n"
            "Embed modes: text, embed, hybrid\n"
            "Use --- to separate normal text from embed content (hybrid mode)\n"
            "Use \\n for line breaks\n"
            "```"
        ))
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
