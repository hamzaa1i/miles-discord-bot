"""
cogs/giveaways.py — PHASE 4 Feature 5: giveaways with entry requirements.

Mimu-style giveaway flow:
  /giveaway start prize:"nitro" duration:"2d" winners:3
      channel:#giveaways required_role:@booster
      min_account_days:7 min_level:5

  → posts an embed with a persistent "enter" button
    (custom_id gw:<id>, restart-safe via on_interaction — same pattern
    as self_roles.py)
  → entrants are validated against the requirements when they click
    AND again when winners are drawn (people leave/lose roles)
  → a 30s background loop ends due giveaways and announces winners

Requirements:
  required_role   — member must hold the role to enter
  min_account_days— Discord account age in days
  min_level       — leveling-cog level (skipped if leveling cog absent)

Commands (start/end/reroll require manage_guild; list is open):
  /giveaway start|end|reroll|list

Supersedes the old cogs/giveaways_disabled.py (deleted) — that version
had no entry requirements, no persistence across restarts, and no
re-verification at draw time.
"""
import logging
import random
import uuid
import asyncio
import re
import time as _time
import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
from utils.db import (
    get_giveaway, save_giveaway_async, get_active_giveaways_async,
)
from utils.veloura_embeds import veloura_embed, COLOR_LAVENDER, COLOR_PINK

logger = logging.getLogger('cyn.giveaways')

BUTTON_PREFIX = "gw:"

_DURATION_UNITS = {
    's': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800,
}


def parse_duration_str(raw: str) -> Optional[int]:
    """Parse '10m', '2h', '1d', '3d12h' etc. into seconds. None if invalid."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    if '-' in s:
        return None
    total, matched = 0, False
    for num, unit in re.findall(r'(\d+)\s*(s|m|h|d|w)(?![a-z])', s):
        total += int(num) * _DURATION_UNITS[unit]
        matched = True
    if not matched or total <= 0:
        try:
            total = int(s)
            matched = total > 0
        except ValueError:
            return None
    return total if matched else None


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # in-memory entry guards: {giveaway_id: set(user_id)} for this boot
        self._click_guard = set()
        if not self.check_giveaways.is_running():
            self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    # ─── requirement checks ──────────────────────────────────────

    async def _check_requirements(self, member: discord.Member,
                                  gw: dict) -> tuple:
        """Return (ok, reason). reason is None when ok."""
        # required role
        required_role_id = gw.get('required_role_id')
        if required_role_id:
            try:
                role = member.guild.get_role(int(required_role_id))
            except (TypeError, ValueError):
                role = None
            if role and role not in member.roles:
                return False, f"you need the **{role.name}** role to enter"
        # account age
        min_days = int(gw.get('min_account_days') or 0)
        if min_days > 0:
            if member.created_at is None:
                return False, "couldn't verify your account age"
            age_days = (discord.utils.utcnow() - member.created_at).days
            if age_days < min_days:
                return False, f"your account must be at least **{min_days}d** old"
        # level requirement (via leveling cog if loaded)
        min_level = int(gw.get('min_level') or 0)
        if min_level > 0:
            leveling = self.bot.get_cog("Leveling")
            if leveling:
                try:
                    data = leveling.get_user_level(member.guild.id, member.id)
                    if int(data.get('level', 0)) < min_level:
                        return False, f"you need **level {min_level}** to enter"
                except Exception:
                    pass  # leveling read failed — fail-open rather than block
        return True, None

    # ─── persistent button handler (restart-safe) ────────────────

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
        gw_id = custom_id[len(BUTTON_PREFIX):]
        gw = await asyncio.to_thread(get_giveaway, gw_id)
        if not gw:
            try:
                await interaction.response.send_message(
                    "this giveaway no longer exists.", ephemeral=True
                )
            except discord.HTTPException:
                pass
            return
        if gw.get('ended'):
            try:
                await interaction.response.send_message(
                    "this giveaway has already ended.", ephemeral=True
                )
            except discord.HTTPException:
                pass
            return
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        # throttle double-clicks within this boot
        guard_key = (gw_id, interaction.user.id)
        if guard_key in self._click_guard:
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.HTTPException:
                pass
            return
        self._click_guard.add(guard_key)

        entries = [str(e) for e in (gw.get('entries') or []) if str(e) != str(interaction.user.id)]
        # re-check requirements live
        ok, reason = await self._check_requirements(interaction.user, gw)
        if not ok:
            try:
                await interaction.response.send_message(
                    f"can't enter — {reason}.", ephemeral=True
                )
            except discord.HTTPException:
                pass
            return
        entries.append(str(interaction.user.id))
        gw['entries'] = entries
        await save_giveaway_async(gw)
        try:
            await interaction.response.send_message(
                f"you're in ✦ ({len(entries)} entrants)",
                ephemeral=True,
            )
        except discord.HTTPException:
            pass

    # ─── embed builders ──────────────────────────────────────────

    def _requirements_text(self, gw: dict, guild: discord.Guild) -> str:
        parts = []
        if gw.get('required_role_id'):
            try:
                role = guild.get_role(int(gw['required_role_id']))
                parts.append(f"role: {role.mention if role else '*(deleted role)*'}")
            except (TypeError, ValueError):
                pass
        if int(gw.get('min_account_days') or 0) > 0:
            parts.append(f"account age ≥ {gw['min_account_days']}d")
        if int(gw.get('min_level') or 0) > 0:
            parts.append(f"level ≥ {gw['min_level']}")
        return " • ".join(parts) if parts else "none — everyone can enter"

    def _build_embed(self, gw: dict, guild: discord.Guild,
                     ended: bool = False) -> discord.Embed:
        ends_at = float(gw.get('ends_at') or 0)
        if ended:
            status = "ended"
            winners = gw.get('winner_ids') or []
            if winners:
                mentions = " ".join(f"<@{w}>" for w in winners[:10])
                outcome = f"winner{'s' if len(winners) != 1 else ''}: {mentions}"
            else:
                outcome = "no valid entrants won"
            desc = (
                f"**prize:** {gw.get('prize', 'something nice')}\n"
                f"{outcome}"
            )
            embed = veloura_embed("giveaway", desc, COLOR_LAVENDER)
        else:
            desc = (
                f"**prize:** {gw.get('prize', 'something nice')}\n"
                f"**ends:** <t:{int(ends_at)}:R>\n"
                f"**entrants:** {len(gw.get('entries') or [])}\n"
                f"**requirements:** {self._requirements_text(gw, guild)}\n\n"
                f"click the button to enter ✦"
            )
            embed = veloura_embed("giveaway", desc, COLOR_PINK)
        try:
            host = f"<@{gw.get('host_id')}>"
        except Exception:
            host = "someone"
        embed.set_footer(text=f"hosted by {gw.get('host_name', host)} • id: {gw.get('id')}")
        return embed

    @staticmethod
    def _enter_button(gw_id: str) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label="enter ✦",
            style=discord.ButtonStyle.primary,
            custom_id=f"{BUTTON_PREFIX}{gw_id}",
        ))
        return view

    # ─── ending logic ────────────────────────────────────────────

    async def _end_giveaway(self, gw: dict, force: bool = False):
        """Mark ended, pick winners (re-checking requirements), announce."""
        guild = self.bot.get_guild(int(gw.get('guild_id') or 0))
        if not guild:
            gw['ended'] = True
            await save_giveaway_async(gw)
            return
        channel = None
        try:
            channel = guild.get_channel(int(gw.get('channel_id') or 0))
        except (TypeError, ValueError):
            channel = None

        entries = [str(e) for e in (gw.get('entries') or [])]
        winners = []
        if entries:
            # re-validate every entrant, then sample
            valid = []
            for uid in set(entries):
                member = guild.get_member(int(uid))
                if not member:
                    try:
                        member = await guild.fetch_member(int(uid))
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        member = None
                if not member:
                    continue
                ok, _ = await self._check_requirements(member, gw)
                if ok:
                    valid.append(uid)
            count = int(gw.get('winners_count') or 1)
            if valid:
                winners = random.sample(valid, min(count, len(valid)))

        gw['ended'] = True
        gw['winner_ids'] = winners
        await save_giveaway_async(gw)

        if channel:
            try:
                embed = self._build_embed(gw, guild, ended=True)
                # edit the original giveaway message if we can
                message_id = gw.get('message_id')
                if message_id:
                    try:
                        msg = await channel.fetch_message(int(message_id))
                        await msg.edit(embed=embed, view=None)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                await channel.send(embed=embed)
            except discord.HTTPException as e:
                logger.error(f"[giveaways] announce failed: {e}")
        logger.info(
            f"[giveaways] ended {gw.get('id')} in {guild.id}: "
            f"{len(entries)} entrants, {len(winners)} winners"
        )

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        try:
            active = await get_active_giveaways_async()
            now = _time.time()
            for gw in active:
                try:
                    if float(gw.get('ends_at') or 0) <= now:
                        await self._end_giveaway(gw)
                except Exception as e:
                    logger.error(
                        f"[giveaways] end loop error for {gw.get('id')}: "
                        f"{type(e).__name__}: {e}"
                    )
        except Exception as e:
            logger.error(f"[giveaways] loop error: {type(e).__name__}: {e}")

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ─── commands ────────────────────────────────────────────────

    giveaway = app_commands.Group(
        name="giveaway",
        description="Giveaways with entry requirements",
    )

    @giveaway.command(name="start", description="Start a giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        prize="What they're winning",
        duration="How long it runs: 30m, 2h, 1d, 3d12h ...",
        winners="Number of winners (1-20)",
        channel="Channel to host it in (defaults to here)",
        required_role="Entrants must hold this role",
        min_account_days="Minimum Discord account age in days",
        min_level="Minimum leveling-cog level",
    )
    async def giveaway_start(
        self, interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: app_commands.Range[int, 1, 20] = 1,
        channel: Optional[discord.TextChannel] = None,
        required_role: Optional[discord.Role] = None,
        min_account_days: Optional[app_commands.Range[int, 0, 3650]] = None,
        min_level: Optional[app_commands.Range[int, 0, 500]] = None,
    ):
        self.bot.increment_command('giveaway_start')
        seconds = parse_duration_str(duration)
        if not seconds or seconds < 60:
            await interaction.response.send_message(
                "invalid duration — use something like `30m`, `2h`, `1d` "
                "(minimum 1 minute).",
                ephemeral=True,
            )
            return
        if seconds > 30 * 86400:
            seconds = 30 * 86400

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message(
                "i can only host giveaways in text channels.", ephemeral=True
            )
            return
        perms = target_channel.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.response.send_message(
                f"i can't post embeds in {target_channel.mention}.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        gw_id = uuid.uuid4().hex[:8]
        gw = {
            'id': gw_id,
            'guild_id': str(interaction.guild.id),
            'channel_id': str(target_channel.id),
            'message_id': None,
            'host_id': str(interaction.user.id),
            'host_name': interaction.user.display_name,
            'prize': prize[:200],
            'ends_at': _time.time() + seconds,
            'winners_count': int(winners),
            'required_role_id': str(required_role.id) if required_role else None,
            'min_account_days': int(min_account_days or 0),
            'min_level': int(min_level or 0),
            'ended': False,
            'entries': [],
            'winner_ids': [],
            'created_at': _time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime()),
        }
        embed = self._build_embed(gw, interaction.guild)
        msg = await target_channel.send(
            embed=embed, view=self._enter_button(gw_id)
        )
        gw['message_id'] = str(msg.id)
        await save_giveaway_async(gw)
        await interaction.followup.send(
            f"giveaway **{prize[:80]}** started in {target_channel.mention} — "
            f"id `{gw_id}` ✦"
        )

    @giveaway.command(name="end", description="End a giveaway early")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(giveaway_id="The giveaway id shown in its footer")
    async def giveaway_end(self, interaction: discord.Interaction,
                           giveaway_id: str):
        self.bot.increment_command('giveaway_end')
        gw = await asyncio.to_thread(get_giveaway, giveaway_id.strip().lower())
        if not gw or gw.get('guild_id') != str(interaction.guild.id):
            await interaction.response.send_message(
                "no giveaway with that id in this server.", ephemeral=True
            )
            return
        if gw.get('ended'):
            await interaction.response.send_message(
                "that giveaway already ended.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await self._end_giveaway(gw, force=True)
        await interaction.followup.send("ended — winners announced ✦")

    @giveaway.command(name="reroll", description="Pick a new winner for an ended giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(giveaway_id="The giveaway id shown in its footer")
    async def giveaway_reroll(self, interaction: discord.Interaction,
                              giveaway_id: str):
        self.bot.increment_command('giveaway_reroll')
        gw = await asyncio.to_thread(get_giveaway, giveaway_id.strip().lower())
        if not gw or gw.get('guild_id') != str(interaction.guild.id):
            await interaction.response.send_message(
                "no giveaway with that id in this server.", ephemeral=True
            )
            return
        if not gw.get('ended'):
            await interaction.response.send_message(
                "end the giveaway first — can't reroll a running one.",
                ephemeral=True,
            )
            return
        entries = [str(e) for e in (gw.get('entries') or [])]
        if not entries:
            await interaction.response.send_message(
                "that giveaway had no entrants.", ephemeral=True
            )
            return
        await interaction.response.defer()
        guild = interaction.guild
        valid = []
        for uid in set(entries):
            member = guild.get_member(int(uid))
            if not member:
                try:
                    member = await guild.fetch_member(int(uid))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    member = None
            if member:
                ok, _ = await self._check_requirements(member, gw)
                if ok:
                    valid.append(uid)
        if not valid:
            await interaction.followup.send("no valid entrants to reroll.")
            return
        previous = set(str(w) for w in (gw.get('winner_ids') or []))
        pool = [u for u in valid if u not in previous] or valid
        new_winner = random.choice(pool)
        gw['winner_ids'] = [new_winner]
        await save_giveaway_async(gw)
        await interaction.followup.send(
            f"rerolled — new winner: <@{new_winner}> ✦"
        )

    @giveaway.command(name="list", description="List running giveaways in this server")
    async def giveaway_list(self, interaction: discord.Interaction):
        self.bot.increment_command('giveaway_list')
        await interaction.response.defer(ephemeral=True)
        active = await get_active_giveaways_async()
        mine = [
            gw for gw in active
            if gw.get('guild_id') == str(interaction.guild.id)
        ]
        if not mine:
            await interaction.followup.send("no running giveaways here.")
            return
        lines = []
        for gw in mine[:10]:
            ends_at = int(float(gw.get('ends_at') or 0))
            lines.append(
                f"`{gw.get('id')}` — **{str(gw.get('prize'))[:40]}** • "
                f"ends <t:{ends_at}:R> • {len(gw.get('entries') or [])} entrants"
            )
        embed = veloura_embed(
            "running giveaways",
            "\n".join(lines),
            COLOR_LAVENDER,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
