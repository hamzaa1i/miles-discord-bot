"""
cogs/setup_wizard.py — PHASE M PART 3 — interactive first-time setup.

Two entry points:

  1. `/setup` (manage_guild) — a guided, ephemeral, in-server wizard:
     feature multi-select -> per-feature channel pickers -> summary with
     test buttons -> done, with a link to the web dashboard for the
     advanced config.

  2. on_guild_join — the cog's own listener (main.py already syncs
     commands on join; this listener ONLY sends the owner a soft welcome
     DM with quick-start / dashboard / support links). Never raises —
     a failed DM must never break the join.

Design notes (documented deviations):
  * The interactive flow runs as an EPHEMERAL message in the server, not
    a DM: discord's channel-select / role-select components only work
    with guild context, and ephemeral keeps the conversation as private
    as a DM while still letting the pickers see the server's channels.
  * Settings are written read-modify-write (get -> merge -> set) so the
    wizard never wipes keys it doesn't know about (custom messages,
    thresholds, colors, ...).
  * "Test" buttons on the summary reuse the exact same code paths the
    dashboard's live actions use (Welcome cog `_send_welcome_message`,
    QOTD cog `_post_qotd`) so a passing test means the feature works.
  * Nothing here changes existing cog behavior — it only writes the
    settings tables those cogs already read.
"""
import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    get_guild_setting_async,
    set_guild_setting_async,
)
from utils.veloura_embeds import veloura_embed

logger = logging.getLogger('cyn.setup_wizard')

SUPPORT_SERVER_URL = (os.getenv("SUPPORT_SERVER_URL") or "").strip()
DASHBOARD_URL = (os.getenv("DASHBOARD_URL") or "").strip()

WIZARD_TIMEOUT = 600  # seconds


# ─── feature definitions ───────────────────────────────────────────
class FeatureDef:
    def __init__(self, key, label, emoji, blurb, kind, table=None,
                 writes=None, info=None):
        self.key = key          # internal id
        self.label = label      # shown in the multi-select
        self.emoji = emoji
        self.blurb = blurb      # one-line description in the select
        self.kind = kind        # 'channel' | 'info' | 'qotd'
        self.table = table      # settings table to merge into
        self.writes = writes    # extra keys merged when a channel is set
        self.info = info        # informational copy for 'info' steps


FEATURES = [
    FeatureDef(
        "welcome", "welcome messages", "♡",
        "greet every soul that drifts in (embed cards + optional DM)",
        "channel", table="welcome_settings",
        writes={"enabled": True},
    ),
    FeatureDef(
        "leveling", "leveling", "✦",
        "xp, levels, role rewards and a leaderboard",
        "channel", table="leveling_settings",
        writes={"enabled": True},
    ),
    FeatureDef(
        "logging", "moderation + logging", "🛡",
        "warnings work out of the box; this sets the server event log",
        "channel", table="log_settings",
        writes={"enabled": True},
    ),
    FeatureDef(
        "ai", "ai chat", "🌙",
        "@aurelia to talk — optionally let her drift into a channel",
        "channel", table="proactive_settings",
        writes={"enabled": True},
        info="ai chat works with no setup — just @aurelia or /aurelia ♡ "
             "pick a channel if you'd also like her to chime in on her own.",
    ),
    FeatureDef(
        "qotd", "qotd", "❓",
        "one question a day, with an answer thread",
        "qotd", table="qotd_settings",
    ),
    FeatureDef(
        "anniversary", "anniversaries", "🎂",
        "celebrate the stayers on their join-day milestones",
        "channel", table="anniversary_settings",
        writes={"enabled": True},
    ),
    FeatureDef(
        "confessions", "confessions", "🌙",
        "anonymous whispers posted to a channel of your choice",
        "channel", table="confess_settings",
        writes={"count": 0},
    ),
    FeatureDef(
        "daily", "daily rewards", "🎁",
        "/daily streaks + bonus xp — zero configuration needed",
        "info", info="daily rewards need no configuration — members just "
                     "run /daily and grow their streak. xp lands in the "
                     "leveling system you configured a moment ago ♡",
    ),
]

FEATURES_BY_KEY = {f.key: f for f in FEATURES}

QOTD_HOURS = [0, 6, 8, 12, 14, 18, 20, 22]


# ─── helpers ───────────────────────────────────────────────────────
async def merge_setting(guild_id, table: str, updates: dict) -> bool:
    """Read-modify-write one settings table. Never wipes unknown keys."""
    try:
        cfg = await get_guild_setting_async(int(guild_id), table) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg.update(updates)
        await set_guild_setting_async(int(guild_id), table, cfg)
        return True
    except Exception as e:
        logger.error(f"[setup] merge_setting({table}) failed: {e}")
        return False


def _links_line() -> str:
    parts = []
    if DASHBOARD_URL:
        parts.append(f"[dashboard]({DASHBOARD_URL})")
    if SUPPORT_SERVER_URL:
        parts.append(f"[support server]({SUPPORT_SERVER_URL})")
    return (" · " + " · ".join(parts)) if parts else ""


# ─── the wizard view ───────────────────────────────────────────────
class SetupWizardView(discord.ui.View):
    """One persistent, re-rendering view — the whole guided flow.

    States (self.step):
      'select'  → feature multi-select + begin button
      'intro'   → informational copy + continue (features with kind=info)
      'channel' → channel picker + skip (features with kind=channel)
      'qotd'    → channel picker + hour select + skip
      'summary' → what was configured + test buttons + finish
    """

    def __init__(self, bot, guild: discord.Guild, user_id: int):
        super().__init__(timeout=WIZARD_TIMEOUT)
        self.bot = bot
        self.guild = guild
        self.user_id = user_id
        self.step = "select"
        self.queue: list = []      # ordered list of FeatureDef to walk
        self.index = 0
        self.chosen: dict = {}     # feature key -> {'channel': id, ...}
        self.configured: list = [] # (FeatureDef, channel_id, extra) done
        self._render()

    # ─── rendering ─────────────────────────────────────────────────
    def _render(self):
        self.clear_items()

        if self.step == "select":
            sel = discord.ui.Select(
                placeholder="pick everything you'd like to enable ♡",
                min_values=1, max_values=len(FEATURES),
                options=[
                    discord.SelectOption(
                        label=f.label, value=f.key, description=f.blurb[:100],
                        emoji=f.emoji,
                    ) for f in FEATURES
                ],
            )

            async def _select_cb(interaction, s=sel):
                await self._on_feature_select(interaction, s)

            sel.callback = _select_cb
            self.add_item(sel)
            go = discord.ui.Button(
                label="let's go ✦", style=discord.ButtonStyle.primary,
                emoji="✧", disabled=not self.chosen.get("_selected"),
            )
            go.callback = self._on_begin
            self.add_item(go)

        elif self.step == "channel":
            feat = self.queue[self.index]
            ch_sel = discord.ui.ChannelSelect(
                placeholder=f"where should {feat.label} live?",
                channel_types=[discord.ChannelType.text],
                min_values=1, max_values=1,
            )

            async def _ch_cb(interaction, s=ch_sel):
                await self._on_channel(interaction, s)

            ch_sel.callback = _ch_cb
            self.add_item(ch_sel)
            skip = discord.ui.Button(
                label="skip for now", style=discord.ButtonStyle.secondary,
            )
            skip.callback = self._on_skip
            self.add_item(skip)

        elif self.step == "qotd":
            ch_sel = discord.ui.ChannelSelect(
                placeholder="which channel gets the daily question?",
                channel_types=[discord.ChannelType.text],
                min_values=1, max_values=1,
            )

            async def _ch_cb(interaction, s=ch_sel):
                await self._on_channel(interaction, s)

            ch_sel.callback = _ch_cb
            self.add_item(ch_sel)
            hour_sel = discord.ui.Select(
                placeholder="post hour (utc) — default 14:00",
                min_values=1, max_values=1,
                options=[
                    discord.SelectOption(
                        label=f"{h:02d}:00 utc", value=str(h),
                        description=("afternoon" if 12 <= h < 18 else
                                     "morning" if 6 <= h < 12 else "evening"
                                     if h >= 18 else "night owl"),
                    ) for h in QOTD_HOURS
                ],
            )

            async def _hour_cb(interaction, s=hour_sel):
                await self._on_hour(interaction, s)

            hour_sel.callback = _hour_cb
            self.add_item(hour_sel)
            skip = discord.ui.Button(
                label="skip for now", style=discord.ButtonStyle.secondary,
            )
            skip.callback = self._on_skip
            self.add_item(skip)

        elif self.step == "intro":
            cont = discord.ui.Button(
                label="continue ✦", style=discord.ButtonStyle.primary,
            )
            cont.callback = self._on_continue
            self.add_item(cont)

        elif self.step == "summary":
            if self._feature_done("welcome"):
                t = discord.ui.Button(
                    label="test welcome", style=discord.ButtonStyle.success,
                    emoji="♡", row=0,
                )
                t.callback = self._on_test_welcome
                self.add_item(t)
            if self._feature_done("qotd"):
                t = discord.ui.Button(
                    label="post today's qotd", style=discord.ButtonStyle.success,
                    emoji="❓", row=0,
                )
                t.callback = self._on_test_qotd
                self.add_item(t)
            finish = discord.ui.Button(
                label="finish ♡", style=discord.ButtonStyle.primary,
                emoji="✦", row=1,
            )
            finish.callback = self._on_finish
            self.add_item(finish)
            redo = discord.ui.Button(
                label="start over", style=discord.ButtonStyle.secondary,
                row=1,
            )
            redo.callback = self._on_restart
            self.add_item(redo)

    def _feature_done(self, key: str) -> bool:
        return any(f.key == key for f, _cid, _ex in self.configured)

    def _current_feature(self):
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def _advance(self):
        self.index += 1
        if self.index >= len(self.queue):
            self.step = "summary"
        else:
            feat = self.queue[self.index]
            self.step = "intro" if feat.kind == "info" else feat.kind

    # ─── embeds ────────────────────────────────────────────────────
    def _embed(self) -> discord.Embed:
        if self.step == "select":
            e = veloura_embed(
                "aurelia setup ✦",
                "pick the features you want switched on — i'll ask for "
                "channels one at a time, then save everything at the end.\n"
                f"*you can change all of this later with slash commands or "
                f"the dashboard{_links_line()}.*",
            )
            return e

        feat = self._current_feature()
        if self.step == "intro" and feat is not None:
            return veloura_embed(f"{feat.emoji} {feat.label}", feat.info)
        if self.step == "channel" and feat is not None:
            return veloura_embed(
                f"{feat.emoji} {feat.label}",
                f"{feat.blurb}.\n\npick the channel it should use — "
                "or skip and configure it later.",
            )
        if self.step == "qotd":
            return veloura_embed(
                "❓ qotd",
                "one question a day, posted to a channel of your choice "
                "with a public thread for answers ♡",
            )

        # summary
        e = veloura_embed("setup complete ♡", "here's what i configured:")
        if self.configured:
            for feat, cid, extra in self.configured:
                ch = self.guild.get_channel(cid) if cid else None
                where = ch.mention if ch else "*(no channel — skipped)*"
                e.add_field(
                    name=f"{feat.emoji} {feat.label}", value=where, inline=True,
                )
        else:
            e.description = ("nothing saved — you skipped every step. no "
                             "worries, everything stays configurable later ✧")
        e.add_field(
            name="next steps",
            value="test your setup with the buttons below, then explore:\n"
                  f"- `/help` — the full command menu\n"
                  + (f"- [dashboard]({DASHBOARD_URL}) — configure everything visually\n"
                     if DASHBOARD_URL else "")
                  + (f"- [support server]({SUPPORT_SERVER_URL}) — questions & feedback"
                     if SUPPORT_SERVER_URL else ""),
            inline=False,
        )
        return e

    # ─── callbacks ─────────────────────────────────────────────────
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            try:
                await interaction.response.send_message(
                    "this setup session belongs to someone else ♡",
                    ephemeral=True,
                )
            except Exception:
                pass
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction):
        self._render()
        try:
            await interaction.response.edit_message(
                embed=self._embed(), view=self,
            )
        except (discord.NotFound, discord.InteractionResponded):
            pass

    async def _on_feature_select(self, interaction: discord.Interaction,
                                  sel: discord.ui.Select):
        keys = list(sel.values or [])
        self.queue = [FEATURES_BY_KEY[k] for k in keys if k in FEATURES_BY_KEY]
        self.chosen["_selected"] = True
        await self._refresh(interaction)

    async def _on_begin(self, interaction: discord.Interaction):
        if not self.queue:
            try:
                await interaction.response.send_message(
                    "pick at least one feature first ♡", ephemeral=True,
                )
            except Exception:
                pass
            return
        self.index = 0
        feat = self.queue[0]
        self.step = "intro" if feat.kind == "info" else feat.kind
        await self._refresh(interaction)

    async def _on_channel(self, interaction: discord.Interaction,
                          sel: discord.ui.ChannelSelect):
        feat = self._current_feature()
        if feat is None or not sel.values:
            await self._refresh(interaction)
            return
        channel = self.guild.get_channel(sel.values[0].id) or sel.values[0]

        updates = {"channel_id": str(channel.id)}
        if feat.writes:
            updates.update(feat.writes)

        if feat.kind == "qotd":
            hour = self.chosen.get("qotd_hour", 14)
            updates.update({
                "enabled": True,
                "post_hour_utc": int(hour),
                "auto_thread": True,
            })

        ok = await merge_setting(self.guild.id, feat.table, updates)
        if ok:
            extra = {"post_hour_utc": updates.get("post_hour_utc")} \
                if feat.kind == "qotd" else None
            self.configured.append((feat, channel.id, extra))
        self._advance()
        await self._refresh(interaction)

    async def _on_hour(self, interaction: discord.Interaction,
                       sel: discord.ui.Select):
        try:
            self.chosen["qotd_hour"] = int(sel.values[0])
        except (ValueError, IndexError):
            pass
        try:
            await interaction.response.defer()
        except Exception:
            pass

    async def _on_skip(self, interaction: discord.Interaction):
        self._advance()
        await self._refresh(interaction)

    async def _on_continue(self, interaction: discord.Interaction):
        self._advance()
        await self._refresh(interaction)

    async def _on_restart(self, interaction: discord.Interaction):
        self.step = "select"
        self.queue = []
        self.index = 0
        self.chosen = {}
        self.configured = []
        await self._refresh(interaction)

    async def _on_finish(self, interaction: discord.Interaction):
        for child in self.children:
            try:
                child.disabled = True
            except Exception:
                pass
        e = self._embed()
        e.description = (e.description or "") + \
            "\n\n*thanks for having me — welcome to the soft side ✧*"
        try:
            await interaction.response.edit_message(embed=e, view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        self.stop()
    async def _on_test_welcome(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        cog = self.bot.get_cog("Welcome")
        if cog is None:
            await interaction.followup.send(
                "the welcome cog isn't loaded — try again in a moment ♡",
                ephemeral=True,
            )
            return
        config = cog.get_config(self.guild.id)
        cid = config.get("channel_id")
        channel = self.guild.get_channel(int(cid)) if cid else None
        if channel is None:
            await interaction.followup.send(
                "welcome channel not found — was it deleted?", ephemeral=True,
            )
            return
        try:
            ok = await cog._send_welcome_message(
                channel, config, interaction.user, self.guild,
            )
        except Exception as e:
            logger.error(f"[setup] welcome test failed: {e}")
            ok = False
        if ok:
            await interaction.followup.send(
                f"test welcome sent to {channel.mention} ♡", ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"i couldn't post to {channel.mention} — check my "
                "permissions there (view + send + embed links).",
                ephemeral=True,
            )

    async def _on_test_qotd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        cog = self.bot.get_cog("QOTD")
        if cog is None:
            await interaction.followup.send(
                "the qotd cog isn't loaded — try again in a moment ♡",
                ephemeral=True,
            )
            return
        from utils.db import get_qotd_settings_async
        settings = await get_qotd_settings_async(str(self.guild.id))
        channel_id = settings.get("channel_id")
        channel = self.guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            await interaction.followup.send(
                "qotd channel not found — was it deleted?", ephemeral=True,
            )
            return
        try:
            ok = await cog._post_qotd(
                self.guild, channel, settings, datetime.utcnow(),
            )
        except Exception as e:
            logger.error(f"[setup] qotd test failed: {e}")
            ok = False
        if ok:
            await interaction.followup.send(
                f"today's question is live in {channel.mention} ✦",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "the question pool is empty — add some with /qotd add ♡",
                ephemeral=True,
            )


# ─── cog ───────────────────────────────────────────────────────────
class SetupWizard(commands.Cog):
    """PHASE M PART 3 — interactive first-time server setup."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup", description="Run Aurelia's interactive first-time setup",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction):
        self.bot.increment_command('setup')
        if interaction.guild is None:
            await interaction.response.send_message(
                "setup only works inside a server ♡", ephemeral=True,
            )
            return
        view = SetupWizardView(self.bot, interaction.guild, interaction.user.id)
        await interaction.response.send_message(
            embed=view._embed(), view=view, ephemeral=True,
        )

    # ─── auto-DM the owner when aurelia joins a new server ─────────
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = guild.owner
        if owner is None:
            try:
                owner = await guild.fetch_member(guild.owner_id)
            except Exception:
                owner = None
        if owner is None:
            return

        e = veloura_embed(
            f"welcome to aurelia ✦ {guild.name}",
            "thanks for inviting me — i'm soft-spoken, slightly playful, "
            "and i remember the people who talk to me.\n\n"
            "**quick start**\n"
            "- `/setup` — an interactive wizard that configures the "
            "essentials in under a minute\n"
            "- `/help` — the full command menu (ai, moderation, "
            "community, roles, utility)\n"
            "- `@aurelia hello` — just talk to me ♡",
        )
        links = []
        if DASHBOARD_URL:
            e.add_field(
                name="dashboard",
                value=f"[configure everything visually]({DASHBOARD_URL}) — "
                      "welcome cards, leveling, qotd, moderation and more.",
                inline=False,
            )
            links.append(f"[getting started guide]({DASHBOARD_URL}/docs/getting-started)")
        if SUPPORT_SERVER_URL:
            e.add_field(
                name="support",
                value=f"[join the support server]({SUPPORT_SERVER_URL}) — "
                      "questions, feedback and updates.",
                inline=False,
            )
            links.append(f"[support server]({SUPPORT_SERVER_URL})")
        if links:
            e.set_footer(text=" · ".join(l.replace("[", "").replace("]", "")
                                         .replace("(", "").replace(")", "")
                                         for l in links))
        if self.bot.user and self.bot.user.avatar:
            e.set_thumbnail(url=self.bot.user.avatar.url)

        try:
            await owner.send(embed=e)
        except (discord.Forbidden, discord.HTTPException):
            # DMs closed — never raise, the /setup command still exists
            logger.info(
                f"[setup] could not DM owner of {guild.name} (DMs closed) — "
                "they can still run /setup",
            )

    async def on_app_command_error(self, interaction, error):  # pragma: no cover
        # local handler: mirror the bot's permission error wording
        if isinstance(error, app_commands.MissingPermissions):
            try:
                await interaction.response.send_message(
                    "you need the **manage server** permission to run "
                    "/setup ♡", ephemeral=True,
                )
            except Exception:
                pass
            return
        raise error


async def setup(bot):
    await bot.add_cog(SetupWizard(bot))
