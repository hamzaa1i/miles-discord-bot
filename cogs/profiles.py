"""
cogs/profiles.py — user profiles.

  /profile [@user]               — view a profile embed (standalone command)
  /profile_set bio [text]         — set bio (max 200 chars)
  /profile_set pronouns [text]    — set pronouns
  /profile_set timezone [text]    — set timezone

FIX 4 — /profile is now a standalone top-level command, not a group.
/profile_set is a separate group for setting fields.
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from utils.db import get_user_profile, set_user_profile

logger = logging.getLogger('cyn.profiles')

MAX_BIO_LENGTH = 200
MAX_PRONOUNS_LENGTH = 40
MAX_TIMEZONE_LENGTH = 60


class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Profile helpers ──────────────────────────────────────────

    def get_profile(self, user_id: int) -> dict:
        data = get_user_profile(user_id)
        if not isinstance(data, dict):
            data = {}
        data.setdefault("bio", "")
        data.setdefault("pronouns", "")
        data.setdefault("timezone", "")
        return data

    def save_profile(self, user_id: int, data: dict) -> None:
        try:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_user_profile(user_id, data)
        except Exception as e:
            logger.error(f"failed to save profile for {user_id}: {e}")

    # ─── /profile — standalone command (FIX 4) ────────────────────

    @app_commands.command(name="profile", description="View a user's profile")
    @app_commands.describe(user="User to view (leave empty for your own)")
    async def profile_view(self, interaction: discord.Interaction,
                          user: discord.Member = None):
        self.bot.increment_command('profile')
        target = user or interaction.user
        data = self.get_profile(target.id)

        embed = discord.Embed(
            title=f"{target.display_name}'s profile",
            color=0x1a1a2e,
            timestamp=datetime.now(timezone.utc),
        )
        avatar_url = (
            target.avatar.url if target.avatar
            else target.default_avatar.url
        )
        embed.set_thumbnail(url=avatar_url)

        bio = (data.get("bio") or "").strip()
        embed.add_field(
            name="Bio",
            value=bio[:1024] if bio else "_(no bio set)_",
            inline=False,
        )
        pronouns = (data.get("pronouns") or "").strip()
        embed.add_field(
            name="Pronouns",
            value=pronouns if pronouns else "_(not set)_",
            inline=True,
        )
        tz = (data.get("timezone") or "").strip()
        embed.add_field(
            name="Timezone",
            value=tz if tz else "_(not set)_",
            inline=True,
        )
        embed.set_footer(text=f"User ID: {target.id}")
        await interaction.response.send_message(embed=embed)

    # ─── /profile_set group (FIX 4 — separate from /profile) ──────

    profile_set = app_commands.Group(
        name="profile_set", description="Set your profile fields"
    )

    @profile_set.command(name="bio", description="Set your bio (max 200 chars)")
    @app_commands.describe(text="Your bio text (max 200 chars)")
    async def profile_set_bio(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('profile_set_bio')
        if len(text) > MAX_BIO_LENGTH:
            await interaction.response.send_message(
                f"bio is too long — max {MAX_BIO_LENGTH} chars "
                f"(you sent {len(text)}).",
                ephemeral=True,
            )
            return
        data = self.get_profile(interaction.user.id)
        data["bio"] = text.strip()
        self.save_profile(interaction.user.id, data)
        logger.info(f"profile bio set for user {interaction.user.id}")
        await interaction.response.send_message(
            "✅ your bio has been updated.", ephemeral=True
        )

    @profile_set.command(name="pronouns", description="Set your pronouns")
    @app_commands.describe(text="Your pronouns (e.g. they/them, she/her)")
    async def profile_set_pronouns(self, interaction: discord.Interaction,
                                   text: str):
        self.bot.increment_command('profile_set_pronouns')
        if len(text) > MAX_PRONOUNS_LENGTH:
            await interaction.response.send_message(
                f"pronouns too long — max {MAX_PRONOUNS_LENGTH} chars.",
                ephemeral=True,
            )
            return
        data = self.get_profile(interaction.user.id)
        data["pronouns"] = text.strip()
        self.save_profile(interaction.user.id, data)
        logger.info(f"profile pronouns set for user {interaction.user.id}")
        await interaction.response.send_message(
            "✅ your pronouns have been updated.", ephemeral=True
        )

    @profile_set.command(name="timezone", description="Set your timezone")
    @app_commands.describe(text="Your timezone (e.g. UTC-5 / EST, Europe/London)")
    async def profile_set_timezone(self, interaction: discord.Interaction,
                                   text: str):
        self.bot.increment_command('profile_set_timezone')
        if len(text) > MAX_TIMEZONE_LENGTH:
            await interaction.response.send_message(
                f"timezone too long — max {MAX_TIMEZONE_LENGTH} chars.",
                ephemeral=True,
            )
            return
        data = self.get_profile(interaction.user.id)
        data["timezone"] = text.strip()
        self.save_profile(interaction.user.id, data)
        logger.info(f"profile timezone set for user {interaction.user.id}")
        await interaction.response.send_message(
            "✅ your timezone has been updated.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Profiles(bot))
