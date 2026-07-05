"""
cogs/starboard.py — starboard system.

Spec (ADD 3):
  Data per guild in data/starboard.json:
    {
      "channel_id": null,
      "threshold": 3,
      "emoji": "⭐",
      "ignored_channels": [],
      "starred_messages": {}
    }

  /starboard setup #channel [threshold=3]
  /starboard emoji [emoji]
  /starboard threshold [number]
  /starboard ignore #channel
  /starboard unignore #channel

  on_raw_reaction_add / on_raw_reaction_remove:
    - Count reactions matching the configured emoji on the message
    - If count reaches threshold and message not already on starboard:
      post to starboard channel as embed showing original content,
      author avatar, channel, jump link, attachment, star count in footer
      store message_id -> starboard_message_id in JSON
    - If count drops below threshold, delete from starboard
    - If count increases on already-starred message, edit the starboard
      embed to update the star count
    - Do not star bot messages
    - Do not star messages in ignored channels
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database


def default_config() -> dict:
    return {
        'channel_id': None,
        'threshold': 3,
        'emoji': '⭐',
        'ignored_channels': [],
        'starred_messages': {},
    }


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/starboard.json')

    def get_config(self, guild_id: int) -> dict:
        data = self.db.get(str(guild_id), default_config())
        # Ensure all expected keys exist
        merged = default_config()
        merged.update(data)
        return merged

    def save_config(self, guild_id: int, config: dict):
        self.db.set(str(guild_id), config)

    # ==================== Reaction listeners ====================

    async def _get_message(self, payload: discord.RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return None, None, None
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return None, None, None
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return None, None, None
        return guild, channel, message

    async def _count_stars(self, message: discord.Message, emoji_str: str) -> int:
        count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji_str:
                try:
                    count = reaction.count
                except Exception:
                    count = 0
                break
        return count

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        config = self.get_config(payload.guild_id)
        if not config.get('channel_id'):
            return
        emoji_str = str(payload.emoji)
        if emoji_str != config.get('emoji', '⭐'):
            return
        # Ignored channel?
        if str(payload.channel_id) in [str(c) for c in config.get('ignored_channels', [])]:
            return

        guild, channel, message = await self._get_message(payload)
        if not message:
            return
        # Don't star bot messages
        if message.author.bot:
            return

        star_count = await self._count_stars(message, config['emoji'])
        starboard_channel = guild.get_channel(int(config['channel_id']))
        if not starboard_channel:
            return

        message_id_str = str(message.id)
        starred = config.get('starred_messages', {})

        if star_count < config['threshold']:
            # Below threshold — delete from starboard if it was there
            if message_id_str in starred:
                try:
                    old_msg = await starboard_channel.fetch_message(int(starred[message_id_str]))
                    await old_msg.delete()
                except Exception:
                    pass
                del starred[message_id_str]
                config['starred_messages'] = starred
                self.save_config(payload.guild_id, config)
            return

        # At/above threshold
        if message_id_str in starred:
            # Update existing starboard message
            try:
                star_msg = await starboard_channel.fetch_message(int(starred[message_id_str]))
                await star_msg.edit(
                    content=f"{config['emoji']} **{star_count}** | {channel.mention}"
                )
            except Exception:
                pass
            return

        # Create new starboard entry
        embed = discord.Embed(
            description=message.content or "*no text*",
            color=0xffd700,
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.avatar.url if message.author.avatar else None
        )
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        embed.add_field(
            name="Source",
            value=f"[Jump to message]({message.jump_url})"
        )
        embed.set_footer(text=f"{config['emoji']} {star_count} · Message ID: {message.id}")

        try:
            star_msg = await starboard_channel.send(
                content=f"{config['emoji']} **{star_count}** | {channel.mention}",
                embed=embed
            )
            starred[message_id_str] = str(star_msg.id)
            config['starred_messages'] = starred
            self.save_config(payload.guild_id, config)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member and payload.member.bot:
            return
        await self._handle_reaction(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload)

    # ==================== Commands ====================

    starboard = app_commands.Group(name="starboard", description="Starboard management")

    @starboard.command(name="setup", description="Setup the starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        threshold: int = 3
    ):
        self.bot.increment_command('starboard_setup')
        if threshold < 1:
            threshold = 1
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['threshold'] = threshold
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ starboard set up in {channel.mention}.\n"
            f"threshold: **{threshold}** ⭐\n"
            f"emoji: {config['emoji']}"
        )

    @starboard.command(name="emoji", description="Change the star emoji")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_emoji(self, interaction: discord.Interaction, emoji: str):
        self.bot.increment_command('starboard_emoji')
        config = self.get_config(interaction.guild.id)
        config['emoji'] = emoji
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ starboard emoji set to {emoji}")

    @starboard.command(name="threshold", description="Change the required star count")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_threshold(self, interaction: discord.Interaction, number: int):
        self.bot.increment_command('starboard_threshold')
        if number < 1:
            number = 1
        config = self.get_config(interaction.guild.id)
        config['threshold'] = number
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ starboard threshold set to **{number}**")

    @starboard.command(name="ignore", description="Ignore a channel from starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_ignore(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('starboard_ignore')
        config = self.get_config(interaction.guild.id)
        ignored = config.get('ignored_channels', [])
        if str(channel.id) not in [str(c) for c in ignored]:
            ignored.append(str(channel.id))
        config['ignored_channels'] = ignored
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ {channel.mention} is now ignored by the starboard.")

    @starboard.command(name="unignore", description="Stop ignoring a channel from starboard")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_unignore(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.increment_command('starboard_unignore')
        config = self.get_config(interaction.guild.id)
        ignored = config.get('ignored_channels', [])
        ignored = [c for c in ignored if str(c) != str(channel.id)]
        config['ignored_channels'] = ignored
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ {channel.mention} is no longer ignored by the starboard.")

    # ==================== Legacy commands (kept for backward compat) ====================

    @app_commands.command(name="starboard_setup", description="Setup the starboard (legacy)")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_setup_legacy(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        threshold: int = 3,
        emoji: str = "⭐"
    ):
        self.bot.increment_command('starboard_setup_legacy')
        config = self.get_config(interaction.guild.id)
        config['channel_id'] = str(channel.id)
        config['threshold'] = max(1, threshold)
        config['emoji'] = emoji
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ starboard set up in {channel.mention}.\n"
            f"threshold: **{max(1, threshold)}** {emoji}"
        )

    @app_commands.command(name="starboard_toggle", description="Enable/disable the starboard (legacy)")
    @app_commands.checks.has_permissions(administrator=True)
    async def starboard_toggle_legacy(self, interaction: discord.Interaction, enabled: bool):
        self.bot.increment_command('starboard_toggle_legacy')
        config = self.get_config(interaction.guild.id)
        if not enabled:
            # Disable by clearing channel_id
            config['_disabled'] = True
        else:
            config['_disabled'] = False
        self.save_config(interaction.guild.id, config)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"starboard is now **{status}**")


async def setup(bot):
    await bot.add_cog(Starboard(bot))
