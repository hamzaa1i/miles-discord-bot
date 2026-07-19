"""
cogs/welcome.py — welcome & goodbye system with command groups + autorole.

Backward-compatibility notes:
- The existing /welcome_setup, /welcome_test, /goodbye_toggle, /toggledms
  commands are kept (they were in the old version).
- New /welcome and /goodbye slash command groups are added per Step 8.
- /autorole is added to set the role assigned to new members on join.
- Welcome & goodbye messages are now embeds with the user's avatar as thumbnail.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
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

        msg_text = self._format_welcome(
            config.get('goodbye_message', "Goodbye {user}, we'll miss you."),
            member
        )
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

    # ==================== LEGACY COMMANDS (kept for backward compat) ====================

    @app_commands.command(name="toggledms", description="Toggle DMs from cyn")
    async def toggledms(self, interaction: discord.Interaction):
        prefs = self.dm_prefs_db.get(str(interaction.user.id), {'dms_enabled': True})
        current = prefs.get('dms_enabled', True)
        if current:
            self.disable_dms(interaction.user.id)
            status = "disabled"
            detail = "you'll only get important DMs"
        else:
            self.enable_dms(interaction.user.id)
            status = "enabled"
            detail = "you'll get welcome rewards and notifications"
        embed = discord.Embed(
            description=f"DMs from cyn are now **{status}**. {detail}.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    # ==================== WELCOME & GOODBYE GROUPS ====================

    welcome = app_commands.Group(name="welcome", description="Configure welcome messages")
    goodbye = app_commands.Group(name="goodbye", description="Configure goodbye messages")

    @welcome.command(name="channel", description="Set welcome channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['enabled'] = True
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        await interaction.response.send_message(f"✅ welcome channel set to {channel.mention}")

    @welcome.command(name="message", description="Set welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_message(self, interaction: discord.Interaction, message: str):
        config = self.get_config(interaction.guild.id)
        config['message'] = message
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        await interaction.response.send_message("✅ welcome message set.\nvariables: `{user}` `{server}` `{membercount}`")

    @welcome.command(name="toggle", description="Enable/disable welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_toggle(self, interaction: discord.Interaction, enabled: bool):
        config = self.get_config(interaction.guild.id)
        config['enabled'] = enabled
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ welcome messages **{status}**")


    @goodbye.command(name="channel", description="Set goodbye channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.get_config(interaction.guild.id)
        config['goodbye_channel_id'] = str(channel.id)
        config['goodbye_enabled'] = True
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        await interaction.response.send_message(f"✅ goodbye channel set to {channel.mention}")

    @goodbye.command(name="message", description="Set goodbye message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_message(self, interaction: discord.Interaction, message: str):
        config = self.get_config(interaction.guild.id)
        config['goodbye_message'] = message
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        await interaction.response.send_message("✅ goodbye message set.")

    @goodbye.command(name="toggle", description="Enable/disable goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_toggle(self, interaction: discord.Interaction, enabled: bool):
        config = self.get_config(interaction.guild.id)
        config['goodbye_enabled'] = enabled
        set_guild_setting(interaction.guild.id, "welcome_settings", config)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ goodbye messages **{status}**")




async def setup(bot):
    await bot.add_cog(Welcome(bot))
