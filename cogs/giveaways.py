"""
cogs/giveaways.py — giveaway system.

Spec (ADD 1):
  /giveaway start [duration] [winners] [prize] [channel(optional)]
    - duration format: 10s, 5m, 2h, 1d
    - Creates an embed with a 🎉 button to enter
    - Shows: prize, host, time remaining, entry count
    - On end: picks random winner(s) from entrants, announces in same channel
    - Edits original message to show "ENDED" with winners listed
    - Persists across restarts: stores end_time as unix timestamp; on cog
      load checks for unfinished giveaways and resumes their timers
  /giveaway end [message_id] — force end early
  /giveaway reroll [message_id] — pick new winner from same entrants
  /giveaway list — show all active giveaways in this server

Data stored in data/giveaways.json keyed by message_id.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import asyncio
import random
import re
from datetime import datetime, timezone


def parse_duration(text: str) -> int:
    """Parse '10s', '5m', '2h', '1d' into seconds. Returns 0 on failure."""
    if not text:
        return 0
    m = re.match(r'^\s*(\d+)\s*([smhd])\s*$', text.lower())
    if not m:
        return 0
    amount = int(m.group(1))
    unit = m.group(2)
    return amount * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]


def format_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    return " ".join(parts)


class GiveawayEnterView(discord.ui.View):
    """Persistent-ish button view for entering a giveaway. Each instance is
    tied to one giveaway message; the parent cog handles the click."""

    def __init__(self, cog: "Giveaways", message_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(label="Enter", emoji="🎉", style=discord.ButtonStyle.primary, custom_id="giveaway_enter")
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.data:
            return
        # custom_id is just "giveaway_enter" — use the message id from the view
        await self.cog.handle_enter(interaction, self.message_id)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/giveaways.json')
        # In-memory entrant tracking: message_id -> set of user_ids
        self.entrants: dict = {}
        # Load active giveaways from disk and resume timers
        self._load_active()

    # ==================== Storage helpers ====================

    def _all_giveaways(self) -> dict:
        return self.db.get_all()

    def _get_giveaway(self, message_id: str) -> dict:
        return self.db.get(message_id, {})

    def _save_giveaway(self, message_id: str, data: dict):
        self.db.set(message_id, data)

    def _delete_giveaway(self, message_id: str):
        self.db.delete(message_id)

    def _load_active(self):
        """On cog load, find all not-yet-ended giveaways and resume timers."""
        all_data = self._all_giveaways()
        for message_id, gdata in all_data.items():
            if not isinstance(gdata, dict):
                continue
            if gdata.get('ended'):
                continue
            end_time = gdata.get('end_time')
            if not end_time:
                continue
            # Restore entrants in memory
            self.entrants[message_id] = set(gdata.get('entrants', []))
            # Schedule the ender
            self.bot.loop.create_task(self._resume_giveaway(message_id, end_time))

    async def _resume_giveaway(self, message_id: str, end_time: int):
        """Wait until end_time (or 1s if already past) then end the giveaway."""
        now = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
        wait = max(1, end_time - now)
        await asyncio.sleep(wait)
        await self._end_giveaway(message_id, force=False)

    # ==================== Entrant handling ====================

    async def handle_enter(self, interaction: discord.Interaction, message_id: int):
        mid = str(message_id)
        gdata = self._get_giveaway(mid)
        if not gdata or gdata.get('ended'):
            await interaction.response.send_message(
                "this giveaway has ended.", ephemeral=True
            )
            return

        if mid not in self.entrants:
            self.entrants[mid] = set(gdata.get('entrants', []))

        if interaction.user.id in self.entrants[mid]:
            await interaction.response.send_message(
                "you're already entered.", ephemeral=True
            )
            return

        self.entrants[mid].add(interaction.user.id)
        # Persist entrants back to disk
        gdata['entrants'] = list(self.entrants[mid])
        self._save_giveaway(mid, gdata)

        await interaction.response.send_message(
            f"✅ entered the giveaway for **{gdata.get('prize', 'a prize')}**! "
            f"({len(self.entrants[mid])} entrants)",
            ephemeral=True
        )

        # Edit the giveaway embed to reflect the new entry count
        try:
            channel = self.bot.get_channel(int(gdata['channel_id']))
            if channel:
                msg = await channel.fetch_message(int(mid))
                embed = self._build_embed(gdata, len(self.entrants[mid]))
                await msg.edit(embed=embed)
        except Exception:
            pass

    # ==================== Embed builder ====================

    def _build_embed(self, gdata: dict, entrant_count: int = None) -> discord.Embed:
        if entrant_count is None:
            entrant_count = len(gdata.get('entrants', []))

        end_time = gdata.get('end_time', 0)
        now = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
        remaining = max(0, end_time - now)

        if gdata.get('ended'):
            winners = gdata.get('winners', [])
            if winners:
                winners_str = ", ".join(f"<@{w}>" for w in winners)
                title = "🎉 GIVEAWAY ENDED"
                desc = (
                    f"**Prize:** {gdata.get('prize', 'a prize')}\n"
                    f"**Winners:** {winners_str}\n"
                    f"**Hosted by:** <@{gdata.get('host_id')}>"
                )
                color = discord.Color.gold()
            else:
                title = "🎉 GIVEAWAY ENDED"
                desc = (
                    f"**Prize:** {gdata.get('prize', 'a prize')}\n"
                    f"**Winners:** none (no entrants)\n"
                    f"**Hosted by:** <@{gdata.get('host_id')}>"
                )
                color = discord.Color.red()
        else:
            title = "🎉 GIVEAWAY"
            desc = (
                f"**Prize:** {gdata.get('prize', 'a prize')}\n"
                f"**Winners:** {gdata.get('winner_count', 1)}\n"
                f"**Time remaining:** {format_remaining(remaining)}\n"
                f"**Entries:** {entrant_count}\n"
                f"**Hosted by:** <@{gdata.get('host_id')}>\n\n"
                f"Click the 🎉 button below to enter!"
            )
            color = 0x1a1a2e

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text=f"Ends at <t:{end_time}:F> • Message ID: {gdata.get('message_id', '?')}")
        return embed

    # ==================== End logic ====================

    async def _end_giveaway(self, message_id: str, force: bool = False):
        gdata = self._get_giveaway(message_id)
        if not gdata:
            return
        if gdata.get('ended') and not force:
            return

        entrant_ids = list(self.entrants.get(message_id, set(gdata.get('entrants', []))))
        winner_count = gdata.get('winner_count', 1)
        winners = []
        if entrant_ids:
            actual_winners = min(winner_count, len(entrant_ids))
            winners = random.sample(entrant_ids, actual_winners)

        gdata['ended'] = True
        gdata['ended_at'] = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())
        gdata['winners'] = winners
        gdata['entrants'] = entrant_ids
        self._save_giveaway(message_id, gdata)

        # Edit original message
        try:
            channel = self.bot.get_channel(int(gdata['channel_id']))
            if channel:
                msg = await channel.fetch_message(int(message_id))
                embed = self._build_embed(gdata)
                # Disable the button by editing view to a new one with all disabled
                view = GiveawayEnterView(self, int(message_id))
                for child in view.children:
                    child.disabled = True
                await msg.edit(embed=embed, view=view)

                if winners:
                    winners_str = ", ".join(f"<@{w}>" for w in winners)
                    await channel.send(
                        f"🎉 Congratulations {winners_str}! You won **{gdata.get('prize', 'a prize')}**!"
                    )
                else:
                    await channel.send(
                        f"😢 The giveaway for **{gdata.get('prize', 'a prize')}** ended with no entrants."
                    )
        except Exception as e:
            print(f"Giveaway end edit error: {e}")

    # ==================== Commands ====================

    giveaway = app_commands.Group(name="giveaway", description="Giveaway management")

    @giveaway.command(name="start", description="Start a new giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_start(
        self,
        interaction: discord.Interaction,
        duration: str,
        winners: int,
        prize: str,
        channel: discord.TextChannel = None
    ):
        self.bot.increment_command('giveaway_start')
        seconds = parse_duration(duration)
        if seconds <= 0:
            await interaction.response.send_message(
                "invalid duration. use formats like `10s`, `5m`, `2h`, `1d`.",
                ephemeral=True
            )
            return
        if seconds > 86400 * 30:
            await interaction.response.send_message(
                "max giveaway duration is 30 days.", ephemeral=True
            )
            return
        if winners < 1 or winners > 20:
            await interaction.response.send_message(
                "winners must be 1-20.", ephemeral=True
            )
            return

        target_channel = channel or interaction.channel
        end_time = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) + seconds

        gdata = {
            'message_id': None,  # filled in after send
            'channel_id': str(target_channel.id),
            'guild_id': str(interaction.guild.id),
            'host_id': str(interaction.user.id),
            'prize': prize,
            'winner_count': winners,
            'end_time': end_time,
            'ended': False,
            'winners': [],
            'entrants': [],
        }

        embed = self._build_embed(gdata, 0)
        view = GiveawayEnterView(self, 0)  # placeholder id, replaced after send

        await interaction.response.send_message("giveaway starting...", ephemeral=True)
        msg = await target_channel.send(embed=embed, view=view)
        # Re-attach the view with the real message id
        view = GiveawayEnterView(self, msg.id)
        await msg.edit(view=view)

        gdata['message_id'] = str(msg.id)
        self._save_giveaway(str(msg.id), gdata)
        self.entrants[str(msg.id)] = set()

        # Schedule the ender
        self.bot.loop.create_task(self._resume_giveaway(str(msg.id), end_time))

        await interaction.followup.send(
            f"✅ giveaway started in {target_channel.mention}!", ephemeral=True
        )

    @giveaway.command(name="end", description="Force-end a giveaway early")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str):
        self.bot.increment_command('giveaway_end')
        gdata = self._get_giveaway(message_id)
        if not gdata:
            await interaction.response.send_message("no giveaway found with that message id.", ephemeral=True)
            return
        if gdata.get('ended'):
            await interaction.response.send_message("that giveaway already ended.", ephemeral=True)
            return
        await self._end_giveaway(message_id, force=True)
        await interaction.response.send_message("✅ giveaway ended.")

    @giveaway.command(name="reroll", description="Pick a new winner from the same entrants")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, interaction: discord.Interaction, message_id: str):
        self.bot.increment_command('giveaway_reroll')
        gdata = self._get_giveaway(message_id)
        if not gdata:
            await interaction.response.send_message("no giveaway found with that message id.", ephemeral=True)
            return
        entrants = gdata.get('entrants', [])
        if not entrants:
            await interaction.response.send_message("no entrants to reroll from.", ephemeral=True)
            return
        new_winner = random.choice(entrants)
        gdata.setdefault('winners', [])
        gdata['winners'].append(new_winner)
        self._save_giveaway(message_id, gdata)
        await interaction.response.send_message(
            f"🎉 New winner: <@{new_winner}>!"
        )



    @giveaway.command(name="list", description="List active giveaways in this server")
    async def giveaway_list(self, interaction: discord.Interaction):
        self.bot.increment_command('giveaway_list')
        all_data = self._all_giveaways()
        active = []
        for mid, gdata in all_data.items():
            if not isinstance(gdata, dict) or gdata.get('ended'):
                continue
            if str(gdata.get('guild_id')) != str(interaction.guild.id):
                continue
            active.append(gdata)
        if not active:
            try:
                await interaction.response.send_message("no active giveaways.", ephemeral=True)
            except discord.InteractionResponded:
                pass
            return
        embed = discord.Embed(title="🎉 Active Giveaways", color=0x2b2d31)
        import time as _time
        now = int(_time.time())
        for gdata in active[:10]:
            remaining = max(0, gdata.get('end_time', 0) - now)
            embed.add_field(
                name=gdata.get('prize', 'a prize'),
                value=f"Host: <@{gdata.get('host_id', '?')}>\nEntries: {len(gdata.get('entrants', []))}\nEnds in: {remaining}s",
                inline=False
            )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
