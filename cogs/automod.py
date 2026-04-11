import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from utils.database import Database

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/automod.json')
        # Track messages per user for spam detection
        # {guild_id: {user_id: [timestamp, ...]}}
        self.message_tracker = defaultdict(lambda: defaultdict(list))

    def get_config(self, guild_id: int) -> dict:
        return self.db.get(str(guild_id), {
            'antispam': {
                'enabled': False,
                'threshold': 5,      # Messages
                'interval': 5,       # In seconds
                'action': 'timeout', # timeout, kick, ban, delete
                'timeout_duration': 300  # 5 minutes
            },
            'wordfilter': {
                'enabled': False,
                'words': [],
                'action': 'delete',  # delete, warn, timeout
                'log_violations': True
            },
            'antispam_ignored_channels': [],
            'antispam_ignored_roles': [],
            'log_channel': None
        })

    async def log_action(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        color: discord.Color
    ):
        """Log automod action"""
        config = self.get_config(guild.id)
        channel_id = config.get('log_channel')
        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))
        if not channel:
            return

        embed = discord.Embed(
            title=f"AutoMod — {title}",
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check messages for spam and banned words"""
        if not message.guild:
            return
        if message.author.bot:
            return

        config = self.get_config(message.guild.id)

        # Check if user has ignored role
        ignored_roles = config.get('antispam_ignored_roles', [])
        user_role_ids = [str(r.id) for r in message.author.roles]
        if any(r in user_role_ids for r in ignored_roles):
            return

        # ===== ANTI SPAM =====
        antispam = config.get('antispam', {})
        if antispam.get('enabled', False):
            ignored_channels = config.get('antispam_ignored_channels', [])
            if str(message.channel.id) not in ignored_channels:
                await self._check_spam(message, antispam)

        # ===== WORD FILTER =====
        wordfilter = config.get('wordfilter', {})
        if wordfilter.get('enabled', False):
            await self._check_words(message, wordfilter)

    async def _check_spam(self, message: discord.Message, antispam: dict):
        """Check if user is spamming"""
        guild_id = message.guild.id
        user_id = message.author.id
        now = datetime.now(timezone.utc)

        # Add current message timestamp
        self.message_tracker[guild_id][user_id].append(now)

        # Clean old timestamps
        interval = antispam.get('interval', 5)
        cutoff = now - timedelta(seconds=interval)
        self.message_tracker[guild_id][user_id] = [
            t for t in self.message_tracker[guild_id][user_id]
            if t > cutoff
        ]

        # Check threshold
        threshold = antispam.get('threshold', 5)
        if len(self.message_tracker[guild_id][user_id]) >= threshold:
            # Reset tracker
            self.message_tracker[guild_id][user_id] = []

            action = antispam.get('action', 'timeout')
            member = message.author

            try:
                if action == 'delete':
                    # Delete recent messages
                    def is_from_user(m):
                        return m.author.id == member.id

                    await message.channel.purge(limit=threshold, check=is_from_user)

                elif action == 'timeout':
                    duration = antispam.get('timeout_duration', 300)
                    await member.timeout(
                        timedelta(seconds=duration),
                        reason="AutoMod: Spam detected"
                    )
                    try:
                        dm_embed = discord.Embed(
                            description=f"You were timed out in **{message.guild.name}** for spamming.",
                            color=discord.Color.red()
                        )
                        await member.send(embed=dm_embed)
                    except:
                        pass

                elif action == 'kick':
                    await member.kick(reason="AutoMod: Spam detected")

                elif action == 'ban':
                    await member.ban(reason="AutoMod: Spam detected")

                await self.log_action(
                    message.guild,
                    "Spam Detected",
                    f"**User:** {member.mention} ({member.id})\n"
                    f"**Action:** {action.title()}\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Messages:** {threshold} in {interval}s",
                    discord.Color.red()
                )

            except discord.Forbidden:
                pass

    async def _check_words(self, message: discord.Message, wordfilter: dict):
        """Check message for banned words"""
        words = wordfilter.get('words', [])
        if not words:
            return

        content_lower = message.content.lower()
        found_word = None

        for word in words:
            if word.lower() in content_lower:
                found_word = word
                break

        if not found_word:
            return

        action = wordfilter.get('action', 'delete')
        member = message.author

        try:
            if action in ['delete', 'warn', 'timeout']:
                await message.delete()

            if action == 'warn':
                warn_embed = discord.Embed(
                    description=f"{member.mention} Your message contained a banned word.",
                    color=discord.Color.orange()
                )
                warn_msg = await message.channel.send(embed=warn_embed)
                # Auto delete warning after 5 seconds
                await discord.utils.sleep_until(
                    discord.utils.utcnow() + discord.utils.timedelta(seconds=5)
                )
                try:
                    await warn_msg.delete()
                except:
                    pass

            elif action == 'timeout':
                await member.timeout(
                    timedelta(minutes=5),
                    reason=f"AutoMod: Banned word used"
                )

            if wordfilter.get('log_violations', True):
                await self.log_action(
                    message.guild,
                    "Word Filter",
                    f"**User:** {member.mention} ({member.id})\n"
                    f"**Action:** {action.title()}\n"
                    f"**Channel:** {message.channel.mention}\n"
                    f"**Word:** ||{found_word}||",
                    discord.Color.orange()
                )

        except discord.Forbidden:
            pass

    # ==================== ANTI SPAM COMMANDS ====================

    @app_commands.command(
        name="antispam",
        description="Configure anti-spam settings"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        enabled="Enable or disable anti-spam",
        threshold="Number of messages before action",
        interval="Time window in seconds",
        action="Action to take on spammers"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Delete Messages", value="delete"),
        app_commands.Choice(name="Timeout", value="timeout"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
    ])
    async def antispam(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        threshold: int = 5,
        interval: int = 5,
        action: app_commands.Choice[str] = None
    ):
        """Setup anti-spam"""
        config = self.get_config(interaction.guild.id)
        config['antispam']['enabled'] = enabled
        config['antispam']['threshold'] = max(2, min(threshold, 20))
        config['antispam']['interval'] = max(2, min(interval, 30))
        if action:
            config['antispam']['action'] = action.value
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            title="Anti-Spam Configured",
            color=0x1a1a2e
        )
        embed.add_field(
            name="Status",
            value="Enabled" if enabled else "Disabled",
            inline=True
        )
        embed.add_field(
            name="Threshold",
            value=f"{config['antispam']['threshold']} messages",
            inline=True
        )
        embed.add_field(
            name="Interval",
            value=f"{config['antispam']['interval']} seconds",
            inline=True
        )
        embed.add_field(
            name="Action",
            value=config['antispam']['action'].title(),
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    # ==================== WORD FILTER COMMANDS ====================

    @app_commands.command(
        name="filter_add",
        description="Add a word to the filter"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def filter_add(self, interaction: discord.Interaction, word: str):
        """Add word to filter"""
        config = self.get_config(interaction.guild.id)
        words = config['wordfilter']['words']

        if word.lower() in [w.lower() for w in words]:
            await interaction.response.send_message(
                "That word is already in the filter.",
                ephemeral=True
            )
            return

        words.append(word.lower())
        config['wordfilter']['words'] = words
        config['wordfilter']['enabled'] = True
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"Added `||{word}||` to the word filter.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="filter_remove",
        description="Remove a word from the filter"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def filter_remove(self, interaction: discord.Interaction, word: str):
        """Remove word from filter"""
        config = self.get_config(interaction.guild.id)
        words = config['wordfilter']['words']

        word_lower = word.lower()
        if word_lower not in [w.lower() for w in words]:
            await interaction.response.send_message(
                "That word isn't in the filter.",
                ephemeral=True
            )
            return

        config['wordfilter']['words'] = [
            w for w in words if w.lower() != word_lower
        ]
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"Removed `{word}` from the word filter.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="filter_list",
        description="View all filtered words"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def filter_list(self, interaction: discord.Interaction):
        """List filtered words"""
        config = self.get_config(interaction.guild.id)
        words = config['wordfilter']['words']

        if not words:
            embed = discord.Embed(
                description="No words in the filter.",
                color=0x1a1a2e
            )
        else:
            words_text = "\n".join([f"• ||{w}||" for w in words])
            embed = discord.Embed(
                title=f"Word Filter ({len(words)} words)",
                description=words_text,
                color=0x1a1a2e
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="filter_clear",
        description="Clear all filtered words"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def filter_clear(self, interaction: discord.Interaction):
        """Clear word filter"""
        config = self.get_config(interaction.guild.id)
        config['wordfilter']['words'] = []
        config['wordfilter']['enabled'] = False
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description="Word filter cleared and disabled.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="filter_action",
        description="Set what happens when a filtered word is detected"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(action=[
        app_commands.Choice(name="Delete Message", value="delete"),
        app_commands.Choice(name="Delete + Warn", value="warn"),
        app_commands.Choice(name="Delete + Timeout", value="timeout"),
    ])
    async def filter_action(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str]
    ):
        """Set filter action"""
        config = self.get_config(interaction.guild.id)
        config['wordfilter']['action'] = action.value
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"Word filter action set to: **{action.name}**",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    # ==================== SLOWMODE COMMAND ====================

    @app_commands.command(
        name="slowmode",
        description="Set channel slowmode"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0 to disable)",
        channel="Channel to apply slowmode to"
    )
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.TextChannel = None
    ):
        """Set slowmode"""
        target = channel or interaction.channel

        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message(
                "Slowmode must be between 0 and 21600 seconds (6 hours).",
                ephemeral=True
            )
            return

        await target.edit(slowmode_delay=seconds)

        if seconds == 0:
            description = f"Slowmode disabled in {target.mention}"
        elif seconds < 60:
            description = f"Slowmode set to **{seconds} seconds** in {target.mention}"
        elif seconds < 3600:
            minutes = seconds // 60
            description = f"Slowmode set to **{minutes} minutes** in {target.mention}"
        else:
            hours = seconds // 3600
            description = f"Slowmode set to **{hours} hours** in {target.mention}"

        embed = discord.Embed(description=description, color=0x1a1a2e)
        await interaction.response.send_message(embed=embed)

    # ==================== LOCK/UNLOCK COMMANDS ====================

    @app_commands.command(
        name="lock",
        description="Lock a channel so members cannot send messages"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        reason: str = "No reason provided"
    ):
        """Lock a channel"""
        target = channel or interaction.channel
        everyone = interaction.guild.default_role

        await target.set_permissions(
            everyone,
            send_messages=False,
            reason=reason
        )

        embed = discord.Embed(
            title="Channel Locked",
            description=f"{target.mention} has been locked.\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="unlock",
        description="Unlock a channel"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        """Unlock a channel"""
        target = channel or interaction.channel
        everyone = interaction.guild.default_role

        await target.set_permissions(
            everyone,
            send_messages=None  # Reset to default
        )

        embed = discord.Embed(
            title="Channel Unlocked",
            description=f"{target.mention} has been unlocked.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="automod_setup",
        description="Set the automod log channel"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel
    ):
        """Set automod log channel"""
        config = self.get_config(interaction.guild.id)
        config['log_channel'] = str(log_channel.id)
        self.db.set(str(interaction.guild.id), config)

        embed = discord.Embed(
            description=f"AutoMod violations will be logged in {log_channel.mention}",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="automod_status",
        description="View current AutoMod configuration"
    )
    async def automod_status(self, interaction: discord.Interaction):
        """View automod config"""
        config = self.get_config(interaction.guild.id)
        antispam = config['antispam']
        wordfilter = config['wordfilter']

        embed = discord.Embed(
            title="AutoMod Configuration",
            color=0x1a1a2e
        )

        embed.add_field(
            name="Anti-Spam",
            value=(
                f"Status: {'Enabled' if antispam['enabled'] else 'Disabled'}\n"
                f"Threshold: {antispam['threshold']} msgs / {antispam['interval']}s\n"
                f"Action: {antispam['action'].title()}"
            ),
            inline=True
        )

        embed.add_field(
            name="Word Filter",
            value=(
                f"Status: {'Enabled' if wordfilter['enabled'] else 'Disabled'}\n"
                f"Words: {len(wordfilter['words'])}\n"
                f"Action: {wordfilter['action'].title()}"
            ),
            inline=True
        )

        log_channel_id = config.get('log_channel')
        if log_channel_id:
            ch = interaction.guild.get_channel(int(log_channel_id))
            embed.add_field(
                name="Log Channel",
                value=ch.mention if ch else "Deleted",
                inline=True
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoMod(bot))