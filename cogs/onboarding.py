"""
cogs/onboarding.py — PHASE 4 Feature 8: DM onboarding flow (Mimu-style).

When a member joins a guild with onboarding enabled, aurelia DMs them a
soft-pink panel with up to 5 interest buttons. Clicking a button assigns
the matching role instantly — no manual role picking needed.

  /onboarding toggle <on|off>
  /onboarding addrole <role> <label> [emoji]
  /onboarding removerole <role>
  /onboarding message <text>     — the DM intro text (tags supported)
  /onboarding test               — DM me a preview right now

Persistence: buttons use custom_id "onboard:<guild_id>:<role_id>" and are
handled in on_interaction (self_roles.py pattern), so panels sent BEFORE a
restart keep working after it.

Tags in the intro text: {user} {user.name} {server} {membercount}
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.db import get_guild_setting_async, set_guild_setting_async
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.onboarding')

BUTTON_PREFIX = "onboard:"
MAX_ROLES = 5

_DEFAULT_TEXT = (
    "welcome to {server}, {user} ♡\n\n"
    "pick anything you're into below and i'll set up your roles — "
    "you can always change them later."
)


class Onboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── config helpers ──────────────────────────────────────────

    async def _get_config(self, guild_id: int) -> dict:
        cfg = await get_guild_setting_async(guild_id, "onboarding_settings")
        return {
            'enabled': bool(cfg.get('enabled')) if cfg else False,
            'welcome_text': (cfg or {}).get('welcome_text') or _DEFAULT_TEXT,
            'roles': (cfg or {}).get('roles') or [],
        }

    async def _save_config(self, guild_id: int, cfg: dict):
        await set_guild_setting_async(guild_id, "onboarding_settings", cfg)

    # ─── tag rendering (safe .replace) ───────────────────────────

    @staticmethod
    def _render(text: str, member, guild: discord.Guild) -> str:
        out = str(text)
        out = out.replace("\\n", "\n")
        out = out.replace("{user.name}", str(member.name))
        out = out.replace("{user}", member.mention)
        out = out.replace("{server}", str(guild.name))
        out = out.replace("{membercount}", str(guild.member_count))
        return out[:2000]

    # ─── panel builder ───────────────────────────────────────────

    def _build_panel(self, cfg: dict, member, guild: discord.Guild):
        text = self._render(cfg.get('welcome_text') or _DEFAULT_TEXT,
                            member, guild)
        embed = veloura_embed(f"welcome to {guild.name}", text, COLOR_PINK)
        embed.set_thumbnail(url=member.display_avatar.url)
        view = discord.ui.View(timeout=None)
        added = 0
        for entry in (cfg.get('roles') or []):
            if added >= MAX_ROLES:
                break
            role_id = entry.get('role_id')
            if not role_id:
                continue
            emoji = entry.get('emoji') or None
            label = str(entry.get('label', 'role'))[:80]
            view.add_item(discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
                custom_id=f"{BUTTON_PREFIX}{guild.id}:{role_id}",
            ))
            added += 1
        return embed, view

    # ─── listener: send panel on join ────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            cfg = await self._get_config(member.guild.id)
            if not cfg.get('enabled') or not cfg.get('roles'):
                return
            embed, view = self._build_panel(cfg, member, member.guild)
            await member.send(embed=embed, view=view)
            logger.info(
                f"[onboarding] sent panel to {member.id} "
                f"for guild {member.guild.id}"
            )
        except discord.Forbidden:
            logger.debug(f"[onboarding] {member.id} has DMs closed")
        except Exception as e:
            logger.error(f"[onboarding] join error: {type(e).__name__}: {e}")

    # ─── persistent button handler ───────────────────────────────

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
        # onboard:<guild_id>:<role_id>
        try:
            _, guild_id_str, role_id_str = custom_id.split(":")
            guild = self.bot.get_guild(int(guild_id_str))
            role_id = int(role_id_str)
        except (ValueError, TypeError):
            return
        if not guild:
            await interaction.response.send_message(
                "that server is gone — the panel expired.", ephemeral=True
            )
            return
        role = guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                "that role no longer exists.", ephemeral=True
            )
            return
        member = interaction.user
        if not isinstance(member, discord.Member) or member.guild.id != guild.id:
            await interaction.response.send_message(
                "you've left that server, so the panel no longer applies.",
                ephemeral=True,
            )
            return
        try:
            if role in member.roles:
                await interaction.response.send_message(
                    f"you already have **{role.name}** ✦", ephemeral=True
                )
                return
            await member.add_roles(role, reason="onboarding panel")
            await interaction.response.send_message(
                f"added **{role.name}** — welcome in ♡", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "i couldn't assign that role (it may be above my top role). "
                "ask a mod for help.",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"something went wrong: {e}", ephemeral=True
            )

    # ─── commands ────────────────────────────────────────────────

    onboarding = app_commands.Group(
        name="onboarding",
        description="DM onboarding with role buttons",
    )

    @onboarding.command(name="toggle", description="Enable or disable DM onboarding")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(state=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
    ])
    async def onboarding_toggle(self, interaction: discord.Interaction,
                                state: app_commands.Choice[str]):
        self.bot.increment_command('onboarding_toggle')
        cfg = await self._get_config(interaction.guild.id)
        cfg['enabled'] = (state.value == "on")
        await self._save_config(interaction.guild.id, cfg)
        warn = ""
        if cfg['enabled'] and not cfg.get('roles'):
            warn = "\n⚠️ no roles yet — use /onboarding addrole first."
        embed = veloura_embed(
            "onboarding",
            f"dm onboarding is now **{state.value}**.{warn}",
            COLOR_PINK if cfg['enabled'] else COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @onboarding.command(name="addrole", description="Add a role to the onboarding panel")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        role="Role to hand out (must be BELOW my top role)",
        label="Button label (e.g. casual gamer)",
        emoji="Optional button emoji",
    )
    async def onboarding_addrole(self, interaction: discord.Interaction,
                                 role: discord.Role, label: str,
                                 emoji: Optional[str] = None):
        self.bot.increment_command('onboarding_addrole')
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"**{role.name}** is above my top role — i can't assign it.",
                ephemeral=True,
            )
            return
        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "i can't hand out that role.", ephemeral=True,
            )
            return
        cfg = await self._get_config(interaction.guild.id)
        roles = cfg.get('roles') or []
        if any(str(r.get('role_id')) == str(role.id) for r in roles):
            await interaction.response.send_message(
                "that role is already on the panel.", ephemeral=True,
            )
            return
        if len(roles) >= MAX_ROLES:
            await interaction.response.send_message(
                f"panel is full — {MAX_ROLES} roles max.", ephemeral=True,
            )
            return
        roles.append({
            'role_id': str(role.id),
            'label': label[:80] or role.name,
            'emoji': (emoji or "").strip()[:32] or None,
        })
        cfg['roles'] = roles
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "onboarding",
            f"added **{role.name}** to the panel (`{label[:80]}`).",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @onboarding.command(name="removerole", description="Remove a role from the panel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_removerole(self, interaction: discord.Interaction,
                                    role: discord.Role):
        self.bot.increment_command('onboarding_removerole')
        cfg = await self._get_config(interaction.guild.id)
        roles = cfg.get('roles') or []
        new_roles = [r for r in roles if str(r.get('role_id')) != str(role.id)]
        if len(new_roles) == len(roles):
            await interaction.response.send_message(
                "that role isn't on the panel.", ephemeral=True,
            )
            return
        cfg['roles'] = new_roles
        await self._save_config(interaction.guild.id, cfg)
        embed = veloura_embed(
            "onboarding",
            f"removed **{role.name}** from the panel.",
            COLOR_LAVENDER,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @onboarding.command(name="message", description="Set the onboarding DM intro text")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        text="Intro text — tags: {user} {user.name} {server} {membercount}, "
             "\\n for line breaks"
    )
    async def onboarding_message(self, interaction: discord.Interaction,
                                 text: str):
        self.bot.increment_command('onboarding_message')
        cfg = await self._get_config(interaction.guild.id)
        cfg['welcome_text'] = text[:1500]
        await self._save_config(interaction.guild.id, cfg)
        preview = self._render(text, interaction.user, interaction.guild)
        embed = veloura_embed(
            "onboarding",
            f"intro text set.\n\n**preview:**\n{preview[:900]}",
            COLOR_PINK,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @onboarding.command(name="test", description="DM me a preview of the onboarding panel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def onboarding_test(self, interaction: discord.Interaction):
        self.bot.increment_command('onboarding_test')
        cfg = await self._get_config(interaction.guild.id)
        if not cfg.get('roles'):
            await interaction.response.send_message(
                "no roles on the panel yet — use /onboarding addrole first.",
                ephemeral=True,
            )
            return
        embed, view = self._build_panel(cfg, interaction.user,
                                        interaction.guild)
        try:
            await interaction.user.send(embed=embed, view=view)
            await interaction.response.send_message(
                "sent the preview to your DMs ♡", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "i couldn't DM you — your DMs are closed.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Onboarding(bot))
