"""
cogs/self_roles.py — Veloura button-based self-role panels.

  /selfroles setup [category] [role1] [role2] [role3] [role4]
      — post a Veloura-styled embed with up to 4 role buttons

category choices: notifications, pronouns, age, dms, location

Button click → toggle role (add if absent, remove if present) →
ephemeral confirmation. Buttons keep working across bot restarts
because clicks are handled by the on_interaction listener.

Panel config stored in data/self_role_panels.json (or Supabase via
get/set_guild_setting under the "self_role_panels" table).
"""
import logging
import json

import discord
from discord.ext import commands
from discord import app_commands

from utils.db import get_guild_setting, set_guild_setting, _read_json, _write_json
from utils.veloura_embeds import veloura_embed, COLOR_PINK, COLOR_LAVENDER

logger = logging.getLogger('cyn.self_roles')

SETTINGS_TABLE = "self_role_panels"
BUTTON_PREFIX = "veloura_sr:"

CATEGORY_LABELS = {
    "notifications": "🔔 notifications",
    "pronouns": "💗 pronouns",
    "age": "🎂 age",
    "dms": "✉️ dms",
    "location": "🌍 location",
}

CATEGORY_EMOJIS = {
    "notifications": "🔔",
    "pronouns": "💗",
    "age": "🎂",
    "dms": "✉️",
    "location": "🌍",
}


class SelfRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── Panel storage ──────────────────────────────────────────
    def get_panels(self, guild_id: int) -> list:
        config = get_guild_setting(guild_id, SETTINGS_TABLE)
        if isinstance(config, dict):
            panels = config.get("panels", [])
            if isinstance(panels, list):
                return panels
        # fall back to JSON file directly
        data = _read_json("data/self_role_panels.json")
        panels = data.get(str(guild_id), [])
        return panels if isinstance(panels, list) else []

    def save_panels(self, guild_id: int, panels: list):
        # Try Supabase-aware guild setting first
        try:
            set_guild_setting(guild_id, SETTINGS_TABLE, {"panels": panels})
        except Exception as e:
            logger.error(f"[self_roles] save_panels supabase error: {e}")
        # Also mirror to JSON file for resilience
        data = _read_json("data/self_role_panels.json")
        data[str(guild_id)] = panels
        _write_json("data/self_role_panels.json", data)

    # ─── View builder ───────────────────────────────────────────
    @staticmethod
    def build_view(roles: list) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for entry in roles[:4]:
            role_id = entry.get("role_id")
            label = entry.get("label", "role")[:80]
            if not role_id:
                continue
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"{BUTTON_PREFIX}{role_id}",
            )
            view.add_item(btn)
        return view

    # ─── Button handler (persistent, restart-safe) ─────────────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        if data.get("component_type") != 2:  # button
            return
        custom_id = data.get("custom_id", "") or ""
        if not custom_id.startswith(BUTTON_PREFIX):
            return
        if not interaction.guild:
            return
        try:
            role_id = int(custom_id[len(BUTTON_PREFIX):])
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "❌ couldn't parse role id.", ephemeral=True
            )
            return
        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "❌ that role no longer exists.", ephemeral=True
            )
            return
        member = interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                await interaction.response.send_message(
                    "❌ couldn't find you in this server.", ephemeral=True
                )
                return
        # Toggle
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="self-role toggle")
                action, emoji = "removed", "➖"
            else:
                await member.add_roles(role, reason="self-role toggle")
                action, emoji = "added", "➕"
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ i don't have permission to manage that role "
                "(it may be above my top role).",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ failed to update roles: {e}", ephemeral=True
            )
            return
        embed = veloura_embed(
            "self roles",
            f"{emoji} **{role.name}** {action} for {member.mention}.",
            COLOR_LAVENDER,
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Slash command ─────────────────────────────────────────
    selfroles = app_commands.Group(name="selfroles", description="Self-role panels")

    @selfroles.command(name="setup", description="Post a self-role button panel")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        category="What kind of roles this panel is for",
        role1="First role to offer (required)",
        role2="Second role (optional)",
        role3="Third role (optional)",
        role4="Fourth role (optional)",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Notifications", value="notifications"),
        app_commands.Choice(name="Pronouns", value="pronouns"),
        app_commands.Choice(name="Age", value="age"),
        app_commands.Choice(name="DMs", value="dms"),
        app_commands.Choice(name="Location", value="location"),
    ])
    async def selfroles_setup(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        role1: discord.Role,
        role2: discord.Role = None,
        role3: discord.Role = None,
        role4: discord.Role = None,
    ):
        self.bot.increment_command('selfroles_setup')
        if not interaction.guild:
            await interaction.response.send_message(
                "this command only works in servers.", ephemeral=True
            )
            return
        roles_in = [r for r in (role1, role2, role3, role4) if r is not None]
        if not roles_in:
            await interaction.response.send_message(
                "❌ provide at least one role.", ephemeral=True
            )
            return
        # Bot hierarchy check
        me = interaction.guild.me
        for r in roles_in:
            if r >= me.top_role:
                await interaction.response.send_message(
                    f"❌ {r.mention} is above my top role — i can't manage it.",
                    ephemeral=True,
                )
                return
        role_entries = [{"role_id": str(r.id), "label": r.name} for r in roles_in]
        emoji = CATEGORY_EMOJIS.get(category.value, "✩")
        cat_label = CATEGORY_LABELS.get(category.value, category.value)
        lines = []
        for entry in role_entries:
            try:
                role_obj = interaction.guild.get_role(int(entry["role_id"]))
                mention = role_obj.mention if role_obj else entry["label"]
            except (TypeError, ValueError):
                mention = entry["label"]
            lines.append(f"{emoji} {mention}")
        embed = veloura_embed(
            cat_label,
            f"pick a role below to toggle it on or off.\n\n" + "\n".join(lines),
            COLOR_PINK,
        )
        view = self.build_view(role_entries)
        try:
            await interaction.channel.send(embed=embed, view=view)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ i can't send messages in this channel.", ephemeral=True
            )
            return
        # Record the panel
        panels = self.get_panels(interaction.guild.id)
        panels.append({
            "category": category.value,
            "channel_id": str(interaction.channel.id),
            "roles": role_entries,
        })
        self.save_panels(interaction.guild.id, panels)
        try:
            await interaction.response.send_message(
                f"✅ {cat_label} panel posted.", ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                f"✅ {cat_label} panel posted.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(SelfRoles(bot))
