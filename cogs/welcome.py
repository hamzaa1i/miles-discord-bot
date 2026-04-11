import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/welcome.json')
        self.economy_db = Database('data/economy.json')
        self.dm_prefs_db = Database('data/dm_prefs.json')

        # Track who has been welcomed recently
        self.pending_welcomes = {}
        # Track who has been notified about safe mode
        self.safe_mode_notified = set()

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'enabled': False,
            'channel_id': None,
            'message': 'Welcome {user} to {server}!',
            'goodbye_enabled': False,
            'welcome_reward': 500,
            'welcomer_reward': 1000
        })

    def wants_dms(self, user_id: int) -> bool:
        prefs = self.dm_prefs_db.get(str(user_id), {'dms_enabled': True})
        return prefs.get('dms_enabled', True)

    def disable_dms(self, user_id: int):
        self.dm_prefs_db.set(str(user_id), {'dms_enabled': False})

    def enable_dms(self, user_id: int):
        self.dm_prefs_db.set(str(user_id), {'dms_enabled': True})

    def get_economy_data(self, user_id: int) -> dict:
        return self.economy_db.get(str(user_id), {
            'balance': 0,
            'bank': 0,
            'total_earned': 0,
            'inventory': []
        })

    def save_economy_data(self, user_id: int, data: dict):
        self.economy_db.set(str(user_id), data)

    def get_total_earned(self, user_id: int) -> int:
        data = self.get_economy_data(user_id)
        return data.get('total_earned', 0)

    async def send_safe_mode_notification(
        self,
        user: discord.Member,
        guild: discord.Guild,
        total_earned: int
    ):
        """Send safe mode disabled notification when user earns 10k+"""
        if user.id in self.safe_mode_notified:
            return

        if total_earned < 10000:
            return

        if not self.wants_dms(user.id):
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
        embed.set_footer(text=f"Type /toggledms to disable future DMs from ao")

        try:
            await user.send(embed=embed)
        except:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track when someone joins - wait for others to welcome them"""
        config = self.get_config(member.guild.id)
        if not config.get('enabled'):
            return

        channel_id = config.get('channel_id')
        if not channel_id:
            return

        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        # Store pending welcome
        self.pending_welcomes[member.id] = {
            'guild_id': member.guild.id,
            'joined_at': datetime.utcnow().isoformat(),
            'welcomed_by': [],
            'channel_id': str(channel_id)
        }

        # Give reward to the new member for joining
        reward = config.get('welcome_reward', 500)
        new_user_data = self.get_economy_data(member.id)
        new_user_data['balance'] = new_user_data.get('balance', 0) + reward
        new_user_data['total_earned'] = new_user_data.get('total_earned', 0) + reward
        self.save_economy_data(member.id, new_user_data)

        # DM the new member
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
        """Detect welcome messages from users"""
        if message.author.bot or not message.guild:
            return

        # Check if message mentions someone who just joined
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

            # Check if message looks like a welcome
            welcome_words = [
                'welcome', 'wb', 'hey', 'hello', 'hi ', 'hii',
                'sup', 'glad', 'join', 'greet', 'wsg', 'wsp'
            ]
            content_lower = message.content.lower()

            is_welcome = any(word in content_lower for word in welcome_words)

            if not is_welcome:
                continue

            # Give reward to welcomer
            config = self.get_config(message.guild.id)
            welcomer_reward = config.get('welcomer_reward', 1000)

            welcomer_data = self.get_economy_data(message.author.id)
            welcomer_data['balance'] = welcomer_data.get('balance', 0) + welcomer_reward
            welcomer_data['total_earned'] = welcomer_data.get('total_earned', 0) + welcomer_reward
            total_earned = welcomer_data['total_earned']
            self.save_economy_data(message.author.id, welcomer_data)

            # Mark as welcomed
            pending['welcomed_by'].append(message.author.id)
            self.pending_welcomes[mentioned.id] = pending

            # Add reaction to their message
            try:
                await message.add_reaction("🎉")
            except:
                pass

            # DM the welcomer
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
                    dm_embed.set_footer(
                        text="Type /toggledms to disable these notifications"
                    )
                    await message.author.send(embed=dm_embed)
                except:
                    pass

            # Check safe mode threshold
            await self.send_safe_mode_notification(
                message.author,
                message.guild,
                total_earned
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send goodbye message"""
        config = self.get_config(member.guild.id)

        if not config.get('goodbye_enabled'):
            return

        channel_id = config.get('channel_id')
        if not channel_id:
            return

        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        # Clean up pending welcomes
        if member.id in self.pending_welcomes:
            del self.pending_welcomes[member.id]

        embed = discord.Embed(
            description=f"**{member.display_name}** left.",
            color=0x1a1a2e
        )
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )

        await channel.send(embed=embed)

    @app_commands.command(name="toggledms", description="Toggle DMs from ao")
    async def toggledms(self, interaction: discord.Interaction):
        """Toggle DM notifications"""
        prefs = self.dm_prefs_db.get(
            str(interaction.user.id),
            {'dms_enabled': True}
        )
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
            description=f"DMs from ao are now **{status}**. {detail}.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="welcome_setup", description="Configure welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = None,
        enabled: bool = True,
        welcome_reward: int = 500,
        welcomer_reward: int = 1000
    ):
        config = self.get_config(interaction.guild.id)
        config['enabled'] = enabled
        config['channel_id'] = str(channel.id)
        config['message'] = message or 'Welcome {user} to {server}!'
        config['welcome_reward'] = welcome_reward
        config['welcomer_reward'] = welcomer_reward
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            title="Welcome System Configured",
            color=0x1a1a2e
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Enabled", value=str(enabled), inline=True)
        embed.add_field(
            name="New Member Reward",
            value=f"${welcome_reward:,}",
            inline=True
        )
        embed.add_field(
            name="Welcomer Reward",
            value=f"${welcomer_reward:,}",
            inline=True
        )
        embed.add_field(
            name="Variables",
            value="`{user}` `{server}` `{count}`",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="welcome_test", description="Test welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)

        if not config.get('enabled'):
            await interaction.response.send_message(
                "welcome messages not enabled.",
                ephemeral=True
            )
            return

        channel_id = config.get('channel_id')
        if not channel_id:
            await interaction.response.send_message(
                "no channel configured.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "channel not found.",
                ephemeral=True
            )
            return

        # Simulate a welcome message
        welcomer_reward = config.get('welcomer_reward', 1000)

        embed = discord.Embed(
            description=(
                f"**Test:** {interaction.user.mention} would receive "
                f"**${welcomer_reward:,}** for welcoming a new member."
            ),
            color=0x1a1a2e
        )
        await channel.send(embed=embed)
        await interaction.response.send_message("test sent.", ephemeral=True)

    @app_commands.command(name="goodbye_toggle", description="Toggle goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        config = self.get_config(interaction.guild.id)
        config['goodbye_enabled'] = enabled
        self.db.set(str(interaction.guild.id), config)

        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            description=f"goodbye messages are now **{status}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))