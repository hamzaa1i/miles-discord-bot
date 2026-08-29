"""
cogs/starboard.py — PHASE 4 Feature 4: starboard.

Members star a message with the configured emoji (default ⭐); once the
count reaches the threshold, aurelia reposts it to the starboard channel
in a soft-pink embed — once and only once (deduped via starboard_posts).

Uses on_raw_reaction_add so it still fires for messages outside the
message cache (old messages / after bot restarts).

Commands (manage_guild):
  /starboard channel <#channel>   — set the starboard channel (enables it)
  /starboard threshold <n>        — stars needed to feature (1-50)
  /starboard emoji <emoji>        — the counting emoji (default ⭐)
  /starboard toggle <on|off>
  /starboard status

Supersedes the old cogs/starboard_disabled.py (deleted) — that version
used on_reaction_add (cache-limited) and had no persistence for which
messages were already starred.
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from utils.db import (
    get_guild_setting_async, set_guild_setting_async,
    get_starboard_post, save_starboard_post,
)
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.starboard')


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── config ──────────────────────────────────────────────────

    async def _get_config(self, guild_id: int) -> dict:
        cfg = await get_guild_setting_async(guild_id, "starboard_settings")
        return {
            'enabled': bool(cfg.get('enabled')) if cfg else False,
            'channel_id': (cfg or {}).get('channel_id'),
            'emoji': (cfg or {}).get('emoji') or '⭐',
            'threshold': int((cfg or {}).get('threshold') or 5),
        }

    async def _save_config(self, guild_id: int, cfg: dict):
        await set_guild_setting_async(guild_id, "starboard_settings", cfg)

    @staticmethod
    def _reaction_matches(payload_emoji: discord.PartialEmoji, cfg_emoji: str) -> bool:
        """Compare a raw payload emoji against the configured emoji.

        The configured emoji may be unicode (⭐) or custom (<:name:id>)."""
        if payload_emoji.is_unicode_emoji():
            return str(payload_emoji) == cfg_emoji
        # custom emoji: match on the full <:name:id> form or just the name
        return cfg_emoji in (f"<:{payload_emoji.name}:{payload_emoji.id}>",
                             payload_emoji.name)

    # ─── listener ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            if payload.guild_id is None or payload.user_id == self.bot.user.id:
                return
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            cfg = await self._get_config(guild.id)
            if not cfg.get('enabled') or not cfg.get('channel_id'):
                return
            if not self._reaction_matches(payload.emoji, cfg.get('emoji', '⭐')):
                return

            channel = guild.get_channel_or_thread(payload.channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return
            star_channel = guild.get_channel(int(cfg['channel_id']))
            if not star_channel or star_channel.id == channel.id:
                return

            # already featured?
            if get_starboard_post(guild.id, payload.message_id):
                return

            try:
                message = await channel.fetch_message(payload.message_id)
            except (discord.NotFound, discord.Forbidden):
                return
            if message.author.bot:  # don't starboard bots
                return

            # count the matching reactions on the message
            count = 0
            for reaction in message.reactions:
                if self._reaction_matches(reaction.emoji, cfg.get('emoji', '⭐')):
                    # exclude bots from the count
                    try:
                        users = [u async for u in reaction.users()]
                        count += sum(1 for u in users if not u.bot)
                    except discord.HTTPException:
                        count += reaction.count
                    break
            if count < int(cfg.get('threshold', 5)):
                return

            # ── repost to starboard ──
            jump = f"https://discord.com/channels/{guild.id}/{channel.id}/{message.id}"
            embed = veloura_embed(
                f"{cfg.get('emoji', '⭐')} {count} | featured message",
                message.content[:1024] or "*(no text — attachment)*",
                COLOR_PINK,
            )
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.display_avatar.url,
            )
            if message.attachments:
                first = message.attachments[0]
                if first.content_type and first.content_type.startswith("image/"):
                    embed.set_image(url=first.url)
            embed.add_field(
                name="jump",
                value=f"[original message]({jump})",
                inline=False,
            )
            embed.set_footer(text=f"in #{channel.name}")

            sent = await star_channel.send(embed=embed)
            save_starboard_post(
                guild.id, message.id, channel.id, sent.id, message.author.id
            )
            logger.info(
                f"[starboard] featured message {message.id} from "
                f"{message.author.id} in guild {guild.id} ({count} stars)"
            )
        except Exception as e:
            logger.error(f"[starboard] reaction error: {type(e).__name__}: {e}")

    # ─── commands ────────────────────────────────────────────────

    starboard = app_commands.Group(
        name="starboard",
        description="Starboard configuration",
    )

    @starboard.command(name="channel", description="Set the starboard channel (this enables it)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def starboard_channel(self, interaction: discord.Interaction,
                                 channel: discord.TextChannel):
        self.bot.increment_command('starboard_channel')
        cfg = await self._get_config(interaction.guild.id)
        cfg['channel_id'] = str(channel.id)
        cfg['enabled'] = True
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "starboard",
            f"starboard channel set to {channel.mention} — starboard is now **on**.",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @starboard.command(name="threshold", description="Stars needed to feature a message")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(stars="1 to 50 (default 5)")
    async def starboard_threshold(self, interaction: discord.Interaction,
                                   stars: app_commands.Range[int, 1, 50]):
        self.bot.increment_command('starboard_threshold')
        cfg = await self._get_config(interaction.guild.id)
        cfg['threshold'] = stars
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "starboard",
            f"a message now needs **{stars}** star(s) to be featured.",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @starboard.command(name="emoji", description="Set the counting emoji")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(emoji="Emoji to count (unicode like ⭐ or custom)")
    async def starboard_emoji(self, interaction: discord.Interaction,
                              emoji: str):
        self.bot.increment_command('starboard_emoji')
        cfg = await self._get_config(interaction.guild.id)
        cfg['emoji'] = emoji.strip()[:64] or '⭐'
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "starboard",
            f"counting emoji is now {cfg['emoji']}.",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @starboard.command(name="toggle", description="Enable or disable the starboard")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(state=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def starboard_toggle(self, interaction: discord.Interaction,
                               state: app_commands.Choice[str]):
        self.bot.increment_command('starboard_toggle')
        cfg = await self._get_config(interaction.guild.id)
        cfg['enabled'] = (state.value == "on")
        await self._save_config(interaction.guild.id, cfg)
        warn = ""
        if cfg['enabled'] and not cfg.get('channel_id'):
            warn = "\n⚠️ no channel set — use /starboard channel first."
        embed = veloura_embed(
            "starboard",
            f"starboard is now **{state.value}**.{warn}",
            COLOR_PINK if cfg['enabled'] else COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @starboard.command(name="status", description="Show the starboard configuration")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def starboard_status(self, interaction: discord.Interaction):
        self.bot.increment_command('starboard_status')
        cfg = await self._get_config(interaction.guild.id)
        ch = interaction.guild.get_channel(int(cfg['channel_id'])) if cfg.get('channel_id') else None
        embed = veloura_embed(
            "starboard",
            (
                f"**enabled:** `{cfg['enabled']}`\n"
                f"**channel:** {ch.mention if ch else 'not set'}\n"
                f"**emoji:** {cfg['emoji']}\n"
                f"**threshold:** {cfg['threshold']} star(s)"
            ),
            COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Starboard(bot))
