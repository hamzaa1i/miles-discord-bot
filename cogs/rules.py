"""
cogs/rules.py — server rules system.

  /rules set [text]          — set the server rules (Manage Guild)
  /rules show                — show rules as a numbered embed
  /rules agree               — show an "I Agree" button that grants a role
  /rules agree_role @role    — set the role to grant on agreement (Manage Guild)

Settings table: "server_rules"
Format: {"rules": "", "agree_role_id": null}

When a user clicks "I Agree", the configured role is added and an
ephemeral "you're in." confirmation is sent.
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from utils.db import get_guild_setting, set_guild_setting

logger = logging.getLogger('cyn.rules')

DEFAULT_CONFIG = {"rules": "", "agree_role_id": None}
AGREE_BUTTON_CUSTOM_ID = "cyn:rules:agree"


class Rules(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self, guild_id: int) -> dict:
        config = get_guild_setting(guild_id, "server_rules")
        if not isinstance(config, dict):
            config = {}
        config.setdefault("rules", "")
        config.setdefault("agree_role_id", None)
        return config

    def save_config(self, guild_id: int, config: dict) -> None:
        try:
            set_guild_setting(guild_id, "server_rules", config)
        except Exception as e:
            logger.error(f"failed to save rules config: {e}")

    @staticmethod
    def _build_embed(rules_text: str) -> discord.Embed:
        lines = [ln.strip() for ln in (rules_text or "").split("\n") if ln.strip()]
        desc = "\n".join(
            f"**{i + 1}.** {ln}" for i, ln in enumerate(lines)
        ) if lines else "_no rules set yet._"
        embed = discord.Embed(
            title="📜 Server Rules", description=desc[:4000],
            color=0x1a1a2e, timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Click 'I Agree' below to accept the rules.")
        return embed

    rules = app_commands.Group(name="rules", description="Server rules")

    @rules.command(name="set", description="Set the server rules (Manage Guild)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(text="Full server rules text. Newlines = list items.")
    async def rules_set(self, interaction: discord.Interaction, text: str):
        self.bot.increment_command('rules_set')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
            return
        config = self.get_config(interaction.guild.id)
        config["rules"] = text[:4000]
        self.save_config(interaction.guild.id, config)
        logger.info(
            f"rules updated in guild {interaction.guild.id} "
            f"by {interaction.user.id}")
        await interaction.response.send_message(
            "✅ server rules updated. use `/rules show` to display them.",
            ephemeral=True)

    @rules.command(name="show", description="Show the server rules")
    async def rules_show(self, interaction: discord.Interaction):
        self.bot.increment_command('rules_show')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
            return
        config = self.get_config(interaction.guild.id)
        await interaction.response.send_message(
            embed=self._build_embed(config.get("rules", "")))

    @rules.command(name="agree", description="Show a rules panel with an I Agree button")
    async def rules_agree(self, interaction: discord.Interaction):
        self.bot.increment_command('rules_agree')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
            return
        config = self.get_config(interaction.guild.id)
        await interaction.response.send_message(
            embed=self._build_embed(config.get("rules", "")),
            view=RulesAgreeView())

    @rules.command(name="agree_role", description="Set the role granted on agreement (Manage Guild)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(role="The role to grant on agreement")
    async def rules_agree_role(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.increment_command('rules_agree_role')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True)
            return
        config = self.get_config(interaction.guild.id)
        config["agree_role_id"] = str(role.id)
        self.save_config(interaction.guild.id, config)
        logger.info(f"agree role set to {role.name} ({role.id}) in guild {interaction.guild.id}")
        await interaction.response.send_message(
            f"✅ members who click **I Agree** will receive the {role.mention} role.",
            ephemeral=True)


class RulesAgreeView(discord.ui.View):
    """Persistent view — works across bot restarts."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I Agree", style=discord.ButtonStyle.success,
        custom_id=AGREE_BUTTON_CUSTOM_ID, emoji="✅",
    )
    async def agree_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("this only works in servers.", ephemeral=True)
            return
        config = get_guild_setting(guild.id, "server_rules")
        if not isinstance(config, dict):
            config = {}
        agree_role_id = config.get("agree_role_id")
        if not agree_role_id:
            await interaction.response.send_message(
                "no agree role configured. ask an admin to use `/rules agree_role @role`.",
                ephemeral=True)
            return
        member = guild.get_member(interaction.user.id)
        if not member:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except Exception:
                member = None
        if not member:
            await interaction.response.send_message("couldn't find you in this server.", ephemeral=True)
            return
        role = guild.get_role(int(agree_role_id))
        if not role:
            await interaction.response.send_message(
                "the configured agree role no longer exists. "
                "ask an admin to re-run `/rules agree_role @role`.",
                ephemeral=True)
            return
        if role in member.roles:
            await interaction.response.send_message("you've already agreed — welcome back.", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason="Agreed to server rules")
        except discord.Forbidden:
            await interaction.response.send_message(
                "i don't have permission to give you that role. "
                "ask an admin to fix my role hierarchy.",
                ephemeral=True)
            return
        except Exception as e:
            logger.error(f"failed to add agree role: {e}")
            await interaction.response.send_message("something went wrong adding your role.", ephemeral=True)
            return
        await interaction.response.send_message("✅ you're in.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Rules(bot))
    bot.add_view(RulesAgreeView())
