import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from utils.database import Database

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/leveling.json')
        self.config_db = Database('data/level_config.json')
        # XP cooldown per user per guild (key = guild_id_user_id)
        self.xp_cooldowns = {}
        # XP per message (MEE6 gives 15-25 XP per message)
        self.xp_min = 15
        self.xp_max = 25
        # Cooldown between XP gains in seconds (MEE6 uses 60s)
        self.cooldown = 60

    def get_user_data(self, guild_id: int, user_id: int) -> dict:
        """Get user level data"""
        return self.db.get(f"{guild_id}_{user_id}", {
            'xp': 0,
            'level': 0,
            'total_xp': 0,
            'last_message': None
        })

    def save_user_data(self, guild_id: int, user_id: int, data: dict):
        """Save user level data"""
        self.db.set(f"{guild_id}_{user_id}", data)

    def xp_for_level(self, level: int) -> int:
        """
        MEE6 exact XP formula:
        XP needed = 5 * (level^2) + 50 * level + 100
        """
        return 5 * (level ** 2) + 50 * level + 100

    def total_xp_for_level(self, level: int) -> int:
        """Total XP needed from level 0 to reach this level"""
        total = 0
        for lvl in range(level):
            total += self.xp_for_level(lvl)
        return total

    def get_level_from_xp(self, total_xp: int) -> tuple:
        """
        Get current level and XP progress from total XP.
        Returns (level, current_xp, xp_needed)
        """
        level = 0
        xp_remaining = total_xp

        while True:
            xp_needed = self.xp_for_level(level)
            if xp_remaining < xp_needed:
                return level, xp_remaining, xp_needed
            xp_remaining -= xp_needed
            level += 1

    def is_on_cooldown(self, guild_id: int, user_id: int) -> bool:
        """Check if user is on XP cooldown"""
        key = f"{guild_id}_{user_id}"
        if key not in self.xp_cooldowns:
            return False
        elapsed = (datetime.utcnow() - self.xp_cooldowns[key]).total_seconds()
        return elapsed < self.cooldown

    def set_cooldown(self, guild_id: int, user_id: int):
        """Set XP cooldown for user"""
        key = f"{guild_id}_{user_id}"
        self.xp_cooldowns[key] = datetime.utcnow()

    async def get_rank_in_guild(self, guild_id: int, user_id: int) -> tuple:
        """Get user rank in guild. Returns (rank, total_users)"""
        all_data = self.db.get_all()
        guild_users = []

        for key, data in all_data.items():
            if key.startswith(f"{guild_id}_"):
                uid = int(key.split('_')[1])
                guild_users.append((uid, data.get('total_xp', 0)))

        guild_users.sort(key=lambda x: x[1], reverse=True)

        rank = 1
        for uid, _ in guild_users:
            if uid == user_id:
                return rank, len(guild_users)
            rank += 1

        return len(guild_users) + 1, len(guild_users)

    async def announce_levelup(
        self,
        guild: discord.Guild,
        user: discord.Member,
        new_level: int
    ):
        """Send level up announcement"""
        config = self.config_db.get(str(guild.id), {})
        channel_id = config.get('levelup_channel')

        # Find channel to send in
        if channel_id:
            channel = guild.get_channel(int(channel_id))
        else:
            channel = None

        if not channel:
            return

        embed = discord.Embed(
            description=f"{user.mention} reached **Level {new_level}**",
            color=0x1a1a2e
        )
        embed.set_author(
            name=user.display_name,
            icon_url=user.avatar.url if user.avatar else None
        )

        await channel.send(embed=embed)

        # Check for level roles
        level_roles = config.get('level_roles', {})
        role_id = level_roles.get(str(new_level))

        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await user.add_roles(role, reason=f"Reached level {new_level}")
                except:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Award XP for messages - MEE6 style"""
        # Ignore bots
        if message.author.bot:
            return

        # Only in guilds
        if not message.guild:
            return

        # Check if leveling is enabled in this guild
        config = self.config_db.get(str(message.guild.id), {})
        if not config.get('enabled', True):
            return

        # Check ignored channels
        ignored_channels = config.get('ignored_channels', [])
        if str(message.channel.id) in ignored_channels:
            return

        # Check XP cooldown
        if self.is_on_cooldown(message.guild.id, message.author.id):
            return

        # Set cooldown
        self.set_cooldown(message.guild.id, message.author.id)

        # Get user data
        data = self.get_user_data(message.guild.id, message.author.id)

        # Give random XP (MEE6 style)
        import random
        xp_gained = random.randint(self.xp_min, self.xp_max)

        old_level = data['level']
        data['total_xp'] += xp_gained

        # Recalculate level from total XP
        new_level, current_xp, xp_needed = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp

        # Save data
        self.save_user_data(message.guild.id, message.author.id, data)

        # Level up!
        if new_level > old_level:
            await self.announce_levelup(message.guild, message.author, new_level)

    @app_commands.command(name="level", description="Check your or someone's level")
    async def level(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Check level - MEE6 style rank card"""
        user = user or interaction.user
        data = self.get_user_data(interaction.guild.id, user.id)

        level, current_xp, xp_needed = self.get_level_from_xp(data.get('total_xp', 0))
        rank, total_users = await self.get_rank_in_guild(
            interaction.guild.id,
            user.id
        )

        # Progress percentage
        progress = (current_xp / xp_needed * 100) if xp_needed > 0 else 0

        # Progress bar (20 chars wide like MEE6)
        bar_filled = int((progress / 100) * 20)
        bar_empty = 20 - bar_filled
        progress_bar = "▰" * bar_filled + "▱" * bar_empty

        embed = discord.Embed(
            color=0x1a1a2e
        )

        embed.set_author(
            name=user.display_name,
            icon_url=user.avatar.url if user.avatar else None
        )

        embed.add_field(
            name="Rank",
            value=f"#{rank} / {total_users}",
            inline=True
        )
        embed.add_field(
            name="Level",
            value=str(level),
            inline=True
        )
        embed.add_field(
            name="Total XP",
            value=f"{data.get('total_xp', 0):,}",
            inline=True
        )
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{progress_bar}` {current_xp:,} / {xp_needed:,} XP",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard_levels", description="View XP leaderboard")
    async def leaderboard_levels(self, interaction: discord.Interaction):
        """Level leaderboard - MEE6 style"""
        await interaction.response.defer()

        all_data = self.db.get_all()

        # Filter for this guild and sort by total XP
        guild_users = []
        for key, data in all_data.items():
            if key.startswith(f"{interaction.guild.id}_"):
                uid = int(key.split('_')[1])
                guild_users.append((uid, data))

        guild_users.sort(
            key=lambda x: x[1].get('total_xp', 0),
            reverse=True
        )

        top_users = guild_users[:10]

        if not top_users:
            embed = discord.Embed(
                description="No level data yet. Start chatting!",
                color=0x1a1a2e
            )
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"XP Leaderboard — {interaction.guild.name}",
            color=0x1a1a2e
        )

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        description = ""
        for idx, (uid, data) in enumerate(top_users, 1):
            try:
                member = interaction.guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
            except:
                name = f"User {uid}"

            level, current_xp, xp_needed = self.get_level_from_xp(
                data.get('total_xp', 0)
            )
            medal = medals.get(idx, f"`#{idx}`")
            total_xp = data.get('total_xp', 0)

            description += (
                f"{medal} **{name}**\n"
                f"Level {level} • {total_xp:,} XP\n\n"
            )

        embed.description = description
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="level_setup",
        description="Configure the leveling system"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def level_setup(
        self,
        interaction: discord.Interaction,
        levelup_channel: discord.TextChannel,
        enabled: bool = True
    ):
        """Setup leveling"""
        config = self.config_db.get(str(interaction.guild.id), {})
        config['enabled'] = enabled
        config['levelup_channel'] = str(levelup_channel.id)
        self.config_db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            title="Leveling Configured",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Level Up Channel",
            value=levelup_channel.mention,
            inline=True
        )
        embed.add_field(
            name="Status",
            value="Enabled" if enabled else "Disabled",
            inline=True
        )
        embed.set_footer(
            text="Users earn 15-25 XP per message (60s cooldown)"
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="level_role",
        description="Set a role reward for reaching a level"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def level_role(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role
    ):
        """Set level role reward"""
        config = self.config_db.get(str(interaction.guild.id), {})

        if 'level_roles' not in config:
            config['level_roles'] = {}

        config['level_roles'][str(level)] = str(role.id)
        self.config_db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"Users will receive {role.mention} when they reach **Level {level}**",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="level_ignore",
        description="Ignore a channel from giving XP"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def level_ignore(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Ignore channel from XP"""
        config = self.config_db.get(str(interaction.guild.id), {})

        if 'ignored_channels' not in config:
            config['ignored_channels'] = []

        if str(channel.id) in config['ignored_channels']:
            config['ignored_channels'].remove(str(channel.id))
            action = "removed from"
        else:
            config['ignored_channels'].append(str(channel.id))
            action = "added to"

        self.config_db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"{channel.mention} {action} XP ignore list.",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="give_xp",
        description="Give XP to a user (Admin only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def give_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        """Manually give XP"""
        data = self.get_user_data(interaction.guild.id, user.id)
        old_level = data['level']

        data['total_xp'] += amount
        new_level, current_xp, xp_needed = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp

        self.save_user_data(interaction.guild.id, user.id, data)

        # Announce level up if needed
        if new_level > old_level:
            await self.announce_levelup(interaction.guild, user, new_level)

        embed = discord.Embed(
            description=f"Gave **{amount:,} XP** to {user.mention}. They are now Level {new_level}.",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="remove_xp",
        description="Remove XP from a user (Admin only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        """Manually remove XP"""
        data = self.get_user_data(interaction.guild.id, user.id)

        data['total_xp'] = max(0, data['total_xp'] - amount)
        new_level, current_xp, xp_needed = self.get_level_from_xp(data['total_xp'])
        data['level'] = new_level
        data['xp'] = current_xp

        self.save_user_data(interaction.guild.id, user.id, data)

        embed = discord.Embed(
            description=f"Removed **{amount:,} XP** from {user.mention}. They are now Level {new_level}.",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="reset_xp",
        description="Reset a user's XP (Admin only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_xp(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Reset user XP"""
        self.save_user_data(interaction.guild.id, user.id, {
            'xp': 0,
            'level': 0,
            'total_xp': 0,
            'last_message': None
        })

        embed = discord.Embed(
            description=f"{user.mention}'s XP has been reset.",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="level_config",
        description="View current leveling configuration"
    )
    async def level_config(self, interaction: discord.Interaction):
        """View level config"""
        config = self.config_db.get(str(interaction.guild.id), {})

        embed = discord.Embed(
            title="Leveling Configuration",
            color=0x1a1a2e
        )

        # Status
        embed.add_field(
            name="Status",
            value="Enabled" if config.get('enabled', True) else "Disabled",
            inline=True
        )

        # XP Rate
        embed.add_field(
            name="XP Per Message",
            value=f"{self.xp_min}-{self.xp_max} XP",
            inline=True
        )

        # Cooldown
        embed.add_field(
            name="Cooldown",
            value=f"{self.cooldown}s between XP gains",
            inline=True
        )

        # Level up channel
        channel_id = config.get('levelup_channel')
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            embed.add_field(
                name="Level Up Channel",
                value=channel.mention if channel else "Deleted",
                inline=True
            )
        else:
            embed.add_field(
                name="Level Up Channel",
                value="Not set",
                inline=True
            )

        # Level roles
        level_roles = config.get('level_roles', {})
        if level_roles:
            roles_text = ""
            for level, role_id in sorted(
                level_roles.items(),
                key=lambda x: int(x[0])
            ):
                role = interaction.guild.get_role(int(role_id))
                role_name = role.mention if role else "Deleted Role"
                roles_text += f"Level {level}: {role_name}\n"
            embed.add_field(
                name="Level Roles",
                value=roles_text,
                inline=False
            )

        # Ignored channels
        ignored = config.get('ignored_channels', [])
        if ignored:
            channels_text = ""
            for ch_id in ignored:
                ch = interaction.guild.get_channel(int(ch_id))
                if ch:
                    channels_text += f"{ch.mention}\n"
            embed.add_field(
                name="XP Ignored Channels",
                value=channels_text or "None",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))