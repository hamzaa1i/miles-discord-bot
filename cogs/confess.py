"""
cogs/confess.py — anonymous confession system.

  /confess setup #channel  — set the confession channel (admin only)
  /confess text [text]      — submit an anonymous confession

Confessions are posted as embeds in the configured channel. The bot does
NOT reveal who submitted the confession — the user_id is only stored
internally in case mods need to investigate abuse.

Settings table: "confess_settings"
Format: {"channel_id": null, "count": 0}

Note: Discord does not allow a slash command to be BOTH a Group (with
subcommands) and a top-level command with arguments at the same time.
So `/confess` is implemented as a Group with `setup` and `text`
subcommands — the original `/confess [text]` becomes `/confess text [text]`.
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from utils.db import get_guild_setting, set_guild_setting

logger = logging.getLogger('cyn.confess')

DEFAULT_CONFIG = {"channel_id": None, "count": 0}


class Confess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Config helpers ───────────────────────────────────────────

    def get_config(self, guild_id: int) -> dict:
        config = get_guild_setting(guild_id, "confess_settings")
        if not isinstance(config, dict):
            config = {}
        config.setdefault("channel_id", None)
        config.setdefault("count", 0)
        return config

    def save_config(self, guild_id: int, config: dict) -> None:
        try:
            set_guild_setting(guild_id, "confess_settings", config)
        except Exception as e:
            logger.error(f"save_config failed for guild {guild_id}: {e}")

    # ─── Slash command group ──────────────────────────────────────

    confess = app_commands.Group(
        name="confess", description="Anonymous confessions"
    )

    @confess.command(name="setup", description="Set the confession channel (admin)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def confess_setup(
        self, interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        self.bot.increment_command('confess_setup')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        config = self.get_config(interaction.guild.id)
        config["channel_id"] = str(channel.id)
        self.save_config(interaction.guild.id, config)
        logger.info(
            f"confess channel set to #{channel.name} ({channel.id}) "
            f"in guild {interaction.guild.id}"
        )
        await interaction.response.send_message(
            f"✅ confessions will now be posted to {channel.mention}.",
            ephemeral=True,
        )

    @confess.command(name="text", description="Submit an anonymous confession")
    @app_commands.describe(text="Your anonymous confession (max ~1900 chars)")
    async def confess_text(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('confess_text')
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            try:
                await interaction.followup.send(
                    "confessions only work in servers.", ephemeral=True
                )
            except Exception:
                pass
            return

        config = self.get_config(interaction.guild.id)
        channel_id = config.get("channel_id")
        if not channel_id:
            try:
                await interaction.followup.send(
                    "confessions aren't set up. ask an admin to use "
                    "`/confess setup #channel`.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            try:
                await interaction.followup.send(
                    "confession channel not found. ask an admin to re-run "
                    "`/confess setup #channel`.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        if len(text) > 1900:
            text = text[:1900]

        # Increment the confession counter for a stable footer ID
        try:
            config["count"] = int(config.get("count", 0)) + 1
        except (TypeError, ValueError):
            config["count"] = 1
        confession_id = config["count"]

        embed = discord.Embed(
            title="anonymous confession",
            description=text,
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Confession #{confession_id}")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            try:
                await interaction.followup.send(
                    "i don't have permission to send to that channel.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"failed to post confession: {e}")
            try:
                await interaction.followup.send(
                    "something went wrong posting your confession.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        # Persist the incremented counter
        self.save_config(interaction.guild.id, config)

        try:
            await interaction.followup.send(
                "✅ confession submitted anonymously.", ephemeral=True
            )
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Confess(bot))
