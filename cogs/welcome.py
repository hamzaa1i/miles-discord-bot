"""cogs/welcome.py — welcome & goodbye system.

Commands:
- /welcome config [setting] [value?] [channel?] — view/change any setting
- /welcome test [type]   — preview welcome/goodbye/DM
- /welcome show          — show current config
- /toggledms             — toggle DMs from cyn
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional
from utils.database import Database
from utils.db import get_guild_setting, set_guild_setting


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/welcome.json')
        self.economy_db = Database('data/economy.json')
        self.dm_prefs_db = Database('data/dm_prefs.json')

        self.pending_welcomes = {}
        self.safe_mode_notified = set()

    def get_config(self, guild_id: int) -> dict:
        # PHASE 1A — use utils.db (Supabase-aware)
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
                'welcomer_reward': 1000
            }
        # Ensure all keys present
        config.setdefault('enabled', False)
        config.setdefault('channel_id', None)
        config.setdefault('message', 'Welcome {user} to {server}! You are member #{membercount}.')
        config.setdefault('goodbye_enabled', False)
        config.setdefault('goodbye_channel_id', None)
        config.setdefault('goodbye_message', "Goodbye {user}, we'll miss you.")
        config.setdefault('autorole_id', None)
        config.setdefault('welcome_reward', 500)
        config.setdefault('welcomer_reward', 1000)
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

    def _format_welcome(self, template: str, member: discord.Member) -> str:
        return template.format(
            user=member.mention,
            user_id=member.id,
            server=member.guild.name,
            membercount=member.guild.member_count,
        )

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
            color=0x1a1a2e
        )
        embed.set_footer(text="Type /toggledms to disable future DMs from cyn")
        try:
            await user.send(embed=embed)
        except:
            pass

    # ==================== LISTENERS ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = self.get_config(member.guild.id)

        # Autorole assignment
        autorole_id = config.get('autorole_id')
        if autorole_id:
            role = member.guild.get_role(int(autorole_id))
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except:
                    pass

        # Welcome message
        if config.get('enabled'):
            channel_id = config.get('channel_id')
            if channel_id:
                channel = member.guild.get_channel(int(channel_id))
                if channel:
                    msg_text = self._format_welcome(
                        config.get('message', 'Welcome {user} to {server}!'),
                        member
                    )
                    embed = discord.Embed(
                        title=f"Welcome to {member.guild.name}!",
                        description=msg_text,
                        color=0x1a1a2e,
                        timestamp=datetime.utcnow()
                    )
                    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                    embed.set_footer(text=f"User ID: {member.id}")
                    try:
                        await channel.send(embed=embed)
                    except:
                        pass

        # PHASE 4E1 — Send custom DM message if configured
        dm_msg = config.get('dm_message', '')
        if dm_msg and dm_msg.lower() != 'off':
            try:
                dm_text = dm_msg.replace("{user}", member.display_name).replace("{server}", member.guild.name)
                await member.send(dm_text)
            except discord.Forbidden:
                pass  # DMs disabled, silently ignore
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
                    color=0x1a1a2e
                )
                await member.send(embed=join_embed)
            except:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Welcomer reward logic (kept from original)
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
                        color=0x1a1a2e
                    )
                    dm_embed.set_footer(text="Type /toggledms to disable these notifications")
                    await message.author.send(embed=dm_embed)
                except:
                    pass

            await self.send_safe_mode_notification(message.author, message.guild, total_earned)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        if not config.get('goodbye_enabled'):
            return
        channel_id = config.get('goodbye_channel_id') or config.get('channel_id')
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        if member.id in self.pending_welcomes:
            del self.pending_welcomes[member.id]

        # PHASE 4E2 — Calculate how long the member was in the server
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

        # Format goodbye message with {duration} variable
        goodbye_template = config.get('goodbye_message', "Goodbye {user}, we'll miss you.")
        msg_text = self._format_welcome(goodbye_template, member)
        msg_text = msg_text.replace("{duration}", duration_str)
        embed = discord.Embed(
            title=f"Goodbye {member.display_name}",
            description=msg_text,
            color=0xff5555,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")
        try:
            await channel.send(embed=embed)
        except:
            pass

    # ==================== STANDALONE COMMAND ====================
    @app_commands.command(name="toggledms", description="Toggle DMs from cyn")
    async def toggledms(self, interaction: discord.Interaction):
        prefs = self.dm_prefs_db.get(str(interaction.user.id), {'dms_enabled': True})
        if prefs.get('dms_enabled', True):
            self.disable_dms(interaction.user.id); status, detail = "disabled", "you'll only get important DMs"
        else:
            self.enable_dms(interaction.user.id); status, detail = "enabled", "you'll get welcome rewards and notifications"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"DMs from cyn are now **{status}**. {detail}.", color=0x1a1a2e), ephemeral=True)

    # ==================== WELCOME GROUP (consolidated) ====================
    welcome = app_commands.Group(name="welcome", description="Configure welcome & goodbye messages")

    async def _err(self, itx: discord.Interaction, msg: str):
        await itx.response.send_message(msg, ephemeral=True)

    # ---- /welcome config ----
    @welcome.command(name="config", description="View or change a welcome/goodbye setting")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        setting="Which setting to view or change",
        value="Toggles: on/off/true/false/yes/no • embed_mode: embed/text",
        channel="Required only for welcome_channel / goodbye_channel",
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Welcome Channel", value="welcome_channel"), app_commands.Choice(name="Welcome Message", value="welcome_message"),
        app_commands.Choice(name="Welcome DM", value="welcome_dm"), app_commands.Choice(name="Welcome Toggle", value="welcome_toggle"),
        app_commands.Choice(name="Goodbye Channel", value="goodbye_channel"), app_commands.Choice(name="Goodbye Message", value="goodbye_message"),
        app_commands.Choice(name="Goodbye Toggle", value="goodbye_toggle"), app_commands.Choice(name="Embed Mode", value="embed_mode"),
    ])
    async def welcome_config(self, interaction: discord.Interaction, setting: app_commands.Choice[str], value: Optional[str] = None, channel: Optional[discord.TextChannel] = None):
        config = self.get_config(interaction.guild.id)
        gid = interaction.guild.id
        key, name = setting.value, setting.name
        bool_words = {"on": True, "true": True, "yes": True, "off": False, "false": False, "no": False}

        # Channel-based settings
        if key in ("welcome_channel", "goodbye_channel"):
            if channel is None:
                return await self._err(interaction, f"❌ Provide a `channel` for **{name}**.")
            if key == "welcome_channel":
                config['channel_id'] = str(channel.id); config['enabled'] = True
            else:
                config['goodbye_channel_id'] = str(channel.id); config['goodbye_enabled'] = True
            set_guild_setting(gid, "welcome_settings", config)
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
            set_guild_setting(gid, "welcome_settings", config)
            return await interaction.response.send_message(f"✅ {name} **{'enabled' if enabled else 'disabled'}**")

        # Embed mode
        if key == "embed_mode":
            if value is None:
                return await self._err(interaction, "❌ Provide `value` (`embed` or `text`).")
            parsed = value.strip().lower()
            if parsed not in ("embed", "text"):
                return await self._err(interaction, f"❌ Invalid `{value}`. Use `embed` or `text`.")
            config['embed_mode'] = parsed
            set_guild_setting(gid, "welcome_settings", config)
            return await interaction.response.send_message(f"✅ Embed mode set to **{parsed}**")

        # Text-based settings (welcome_message / goodbye_message / welcome_dm)
        text_cfg = {"welcome_message": ("message", "`{user}` `{server}` `{membercount}`"), "goodbye_message": ("goodbye_message", "`{user}` `{server}` `{membercount}` `{duration}`"), "welcome_dm": ("dm_message", "`{user}` `{server}`")}
        if key in text_cfg:
            if value is None: return await self._err(interaction, f"ℹ️ Provide `value` for **{name}**.")
            cfg_key, vars_str = text_cfg[key]
            is_dm = key == "welcome_dm"
            if is_dm and value.lower() == "off":
                config[cfg_key] = ""; set_guild_setting(gid, "welcome_settings", config)
                return await interaction.response.send_message("✅ Welcome DM disabled.")
            config[cfg_key] = value[:1000] if is_dm else value
            set_guild_setting(gid, "welcome_settings", config)
            if is_dm:
                preview = value.replace("{user}", interaction.user.display_name).replace("{server}", interaction.guild.name)
                return await interaction.response.send_message(f"✅ Welcome DM set. Variables: {vars_str}\nPreview: {preview}")
            return await interaction.response.send_message(f"✅ {name} set.\nVariables: {vars_str}")

    # ---- /welcome test ----
    @welcome.command(name="test", description="Preview welcome, goodbye, or DM message")
    @app_commands.describe(type="Which message type to test")
    @app_commands.choices(type=[
        app_commands.Choice(name="Welcome", value="welcome"), app_commands.Choice(name="Goodbye", value="goodbye"), app_commands.Choice(name="DM", value="dm"),
    ])
    async def welcome_test(self, interaction: discord.Interaction, type: app_commands.Choice[str]):
        config = self.get_config(interaction.guild.id)
        member = interaction.user
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

        if type.value in ("welcome", "goodbye"):
            if type.value == "welcome":
                cid = config.get('channel_id')
                msg_text = self._format_welcome(config.get('message', 'Welcome {user} to {server}!'), member)
                title, color = f"Welcome to {interaction.guild.name}!", 0x1a1a2e
            else:
                cid = config.get('goodbye_channel_id') or config.get('channel_id')
                msg_text = self._format_welcome(config.get('goodbye_message', "Goodbye {user}, we'll miss you."), member).replace("{duration}", "just now")
                title, color = f"Goodbye {member.display_name}", 0xff5555
            channel = interaction.guild.get_channel(int(cid)) if cid else None
            if not channel: return await self._err(interaction, f"❌ {type.name} channel not set. Use `/welcome config` first.")
            embed = discord.Embed(title=title, description=msg_text, color=color, timestamp=datetime.utcnow())
            embed.set_thumbnail(url=avatar_url); embed.set_footer(text=f"User ID: {member.id} • (test)")
            try:
                await channel.send(embed=embed)
                await interaction.response.send_message(f"✅ Test {type.value} sent to {channel.mention}")
            except Exception as e:
                await self._err(interaction, f"❌ Failed: {e}")
            return

        if type.value == "dm":
            dm_msg = config.get('dm_message', '')
            if not dm_msg or dm_msg.lower() == 'off':
                return await self._err(interaction, "❌ Welcome DM not configured. Use `/welcome config setting: Welcome DM` first.")
            try:
                await member.send(dm_msg.replace("{user}", member.display_name).replace("{server}", interaction.guild.name))
                await interaction.response.send_message("✅ Test DM sent to your inbox.", ephemeral=True)
            except discord.Forbidden:
                await self._err(interaction, "❌ Couldn't DM you — your DMs are closed.")
            except Exception as e:
                await self._err(interaction, f"❌ Failed: {e}")

    # ---- /welcome show ----
    @welcome.command(name="show", description="Show the current welcome & goodbye configuration")
    async def welcome_show(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)
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
        embed = discord.Embed(title="📋 Welcome & Goodbye Configuration", color=0x1a1a2e, timestamp=datetime.utcnow())
        embed.set_footer(text=f"Guild: {g.name}")
        embed.add_field(name="🎉 Welcome", inline=False, value=f"**Enabled:** `{config.get('enabled', False)}`\n**Channel:** {fmt('channel', config.get('channel_id'))}\n**Message:** {fmt_msg(config.get('message'), default_welcome)}")
        embed.add_field(name="👋 Goodbye", inline=False, value=f"**Enabled:** `{config.get('goodbye_enabled', False)}`\n**Channel:** {fmt('channel', config.get('goodbye_channel_id'))}\n**Message:** {fmt_msg(config.get('goodbye_message'), default_goodbye)}")
        embed.add_field(name="✉️ Welcome DM", inline=False, value=f"**Enabled:** `{dm_enabled}`\n**Message:** {fmt_msg(dm_msg, '(disabled)') if dm_msg else '*(disabled)*'}")
        embed.add_field(name="⚙️ Other", inline=False, value=f"**Embed Mode:** `{config.get('embed_mode', 'embed')}`\n**Welcome Reward:** `${config.get('welcome_reward', 500):,}`\n**Welcomer Reward:** `${config.get('welcomer_reward', 1000):,}`\n**Autorole:** {fmt('role', config.get('autorole_id'))}")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
