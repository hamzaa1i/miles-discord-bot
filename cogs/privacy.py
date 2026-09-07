"""cogs/privacy.py — PHASE 3 / PART 6 — privacy controls.

/privacy show             — your five opt-out preferences (ephemeral).
/privacy set feature enabled — toggle one feature (or all at once).
/privacy delete           — delete EVERYTHING stored about you across
    all tables. Requires a confirmation button AND typing "DELETE"
    into the modal. Discord-side color roles are deleted too; the
    final reply lists the record counts removed.
/privacy export           — everything aurelia knows about you, as a
    JSON file attachment (ephemeral).

Opt-out semantics: "on" = the feature is ALLOWED; "off" = opted out.
The five features: memory (conversation history), vibe (/vibe
transcripts), recap (/recap digests), ship (/ship), fact_extraction
(aurelia remembering facts about you).

Integration points (checks added BEFORE processing):
  * cogs/ai_chat.py  — memory_optout skips history saves;
                       fact_extraction_optout skips fact extraction
  * cogs/fun_extras.py /vibe — vibe_optout members are skipped in
    the transcript
  * cogs/recap.py    — recap_optout members are skipped
  * cogs/ship.py     — ship_optout members refuse to be shipped

DB: utils/db.py privacy helpers (Supabase user_privacy, JSON
fallback, 120s read cache).
"""
import io
import json
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.veloura_embeds import get_seasonal_color
from utils import db as _db

logger = logging.getLogger('cyn.privacy')

# Feature -> human label + what "on" means.
FEATURE_LABELS = {
    "memory": ("memory", "aurelia remembers your conversations"),
    "vibe": ("vibe check", "your messages can be read for /vibe"),
    "recap": ("recap", "your messages appear in /recap digests"),
    "ship": ("ship", "you can be shipped with /ship"),
    "fact_extraction": ("fact extraction",
                        "aurelia can remember facts about you"),
}


class PrivacyDeleteModal(discord.ui.Modal, title="final confirmation"):
    """Typed confirmation — the user must type DELETE."""

    confirm = discord.ui.TextInput(
        label='type "DELETE" to confirm',
        placeholder="DELETE",
        min_length=4,
        max_length=10,
        required=True,
    )

    def __init__(self, cog: "Privacy"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if str(self.confirm or "").strip().upper() != "DELETE":
            return await interaction.response.send_message(
                "cancelled — nothing was deleted. (you needed to type "
                "DELETE exactly.) ♡",
                ephemeral=True,
            )
        user = interaction.user
        # Discord-side color roles first (the DB rows vanish next).
        roles_removed = await self.cog._delete_color_roles(user)
        try:
            counts = await _db.delete_all_user_data_async(str(user.id))
        except Exception as e:
            logger.error(f"[privacy] purge failed for {user.id}: {e}")
            return await interaction.response.send_message(
                "something broke mid-deletion — try again in a minute ♡",
                ephemeral=True,
            )
        counts["discord color roles"] = roles_removed
        total = sum(v for v in counts.values() if isinstance(v, int))
        lines = "\n".join(
            f"• {label}: {n}" for label, n in counts.items()
        )
        embed = discord.Embed(
            title="꒰ა 🕊️ ໒꒱ your data is gone",
            description=(
                f"**{total}** records deleted across every table:\n"
                f"{lines}\n\nit's like we just met ♡"
            ),
            color=get_seasonal_color(),
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )


class PrivacyDeleteView(discord.ui.View):
    """Step 1 of deletion: the scary button that opens the modal."""

    def __init__(self, cog: "Privacy"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(
        label="delete everything", style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def start(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        await interaction.response.send_modal(
            PrivacyDeleteModal(self.cog)
        )


class Privacy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Shared helpers ──────────────────────────────────────────

    async def _delete_color_roles(self, user) -> int:
        """Delete the user's Discord color roles in every guild
        (run before the DB purge wipes the rows that map to them)."""
        removed = 0
        for guild in self.bot.guilds:
            member = guild.get_member(user.id)
            if member is None:
                continue
            try:
                row = await _db.get_user_color_role_async(
                    guild.id, user.id
                )
            except Exception:
                row = None
            if not row or not row.get("role_id"):
                continue
            try:
                role = guild.get_role(int(row["role_id"]))
                if role is not None:
                    await role.delete(reason="privacy data purge")
                    removed += 1
            except (TypeError, ValueError, discord.Forbidden,
                    discord.HTTPException):
                pass
        return removed

    def _privacy_embed(self, privacy: dict) -> discord.Embed:
        lines = []
        for feature, (label, on_desc) in FEATURE_LABELS.items():
            opted_out = bool(privacy.get(f"{feature}_optout"))
            if opted_out:
                lines.append(f"**{label}** — off *(opted out)*")
            else:
                lines.append(f"**{label}** — on ({on_desc})")
        embed = discord.Embed(
            title="꒰ა 🕊️ ໒꒱ your privacy",
            description="\n".join(lines),
            color=get_seasonal_color(),
        )
        embed.set_footer(
            text="change these with /privacy set · /privacy delete wipes all"
        )
        return embed

    # ─── Commands ────────────────────────────────────────────────

    privacy = app_commands.Group(
        name="privacy", description="Control what aurelia remembers about you"
    )

    @privacy.command(name="show", description="See your privacy settings")
    async def privacy_show(self, interaction: discord.Interaction):
        self.bot.increment_command('privacy_show')
        try:
            privacy = await _db.get_user_privacy_async(
                interaction.user.id
            )
        except Exception:
            privacy = {}
        await interaction.response.send_message(
            embed=self._privacy_embed(privacy), ephemeral=True
        )

    @privacy.command(name="set", description="Turn a feature on or off")
    @app_commands.describe(
        feature="Which feature to change (or all)",
        enabled="True = feature allowed · False = opted out",
    )
    @app_commands.choices(feature=[
        app_commands.Choice(name="memory", value="memory"),
        app_commands.Choice(name="vibe check", value="vibe"),
        app_commands.Choice(name="recap", value="recap"),
        app_commands.Choice(name="ship", value="ship"),
        app_commands.Choice(name="fact extraction", value="fact_extraction"),
        app_commands.Choice(name="all", value="all"),
    ])
    async def privacy_set(self, interaction: discord.Interaction,
                          feature: app_commands.Choice[str],
                          enabled: bool):
        self.bot.increment_command('privacy_set')
        feature_key = feature.value
        if feature_key not in FEATURE_LABELS and feature_key != "all":
            return await interaction.response.send_message(
                "unknown feature ♡", ephemeral=True
            )
        try:
            await _db.set_user_privacy_async(
                interaction.user.id, feature_key, enabled
            )
        except Exception as e:
            logger.error(f"[privacy] set failed: {e}")
            return await interaction.response.send_message(
                "couldn't save that — try again ♡", ephemeral=True
            )

        if feature_key == "all":
            state = "on" if enabled else "off (opted out)"
            desc = f"all five features are now **{state}**."
        else:
            label, on_desc = FEATURE_LABELS[feature_key]
            if enabled:
                desc = f"**{label}** is back on — {on_desc}."
            else:
                desc = f"**{label}** is off — i'll skip your data for it ♡"
        await interaction.response.send_message(
            f"✅ {desc}", ephemeral=True
        )

    @privacy.command(name="delete", description="Delete ALL your data everywhere")
    async def privacy_delete(self, interaction: discord.Interaction):
        self.bot.increment_command('privacy_delete')
        embed = discord.Embed(
            title="꒰ა 🗑️ ໒꒱ delete everything?",
            description=(
                "this permanently erases **everything** i've stored about "
                "you, across every server:\n"
                "facts · conversation memory · profile · levels & xp · "
                "warnings · daily streaks · fortunes · time capsules · "
                "achievements · color roles · nickname requests · "
                "ships · privacy settings\n\n"
                "there is no undo. you'll confirm twice ♡"
            ),
            color=0xFF6B6B,
        )
        await interaction.response.send_message(
            embed=embed,
            view=PrivacyDeleteView(self),
            ephemeral=True,
        )

    @privacy.command(name="export", description="Download all your data (JSON)")
    async def privacy_export(self, interaction: discord.Interaction):
        self.bot.increment_command('privacy_export')
        await interaction.response.defer(ephemeral=True)
        try:
            data = await _db.export_user_data_async(
                str(interaction.user.id)
            )
        except Exception as e:
            logger.error(f"[privacy] export failed: {e}")
            return await interaction.followup.send(
                "the export broke on my end — try again in a minute ♡",
                ephemeral=True,
            )
        blob = json.dumps(data, indent=2, ensure_ascii=False,
                          default=str)
        buffer = io.BytesIO(blob.encode("utf-8"))
        file = discord.File(
            buffer,
            filename=f"aurelia-data-{interaction.user.id}.json",
        )
        await interaction.followup.send(
            "🕊️ everything i know about you, as of right now ♡",
            file=file,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Privacy(bot))
