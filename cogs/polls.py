"""
cogs/polls.py — polls system.

Spec (ADD 5):
  /poll create [question] [option1] [option2] [option3(optional)] [option4(optional)] [duration(optional)]
    - Poll embed with lettered reactions: 🇦 🇧 🇨 🇩
    - Shows only the options that were provided
    - If duration given (e.g. 10m, 2h), auto-end after that time
    - On end: count reactions, show results with percentages and a bar
      graph made of ▓ and ░ characters, announce winner
  /poll end [message_id] — end a poll early and show results
  /poll results [message_id] — show current results without ending

Data stored in data/polls.json keyed by message_id.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import asyncio
import re
from datetime import datetime, timezone


POLL_EMOJIS = ["🇦", "🇧", "🇨", "🇩"]


def parse_duration(text: str) -> int:
    if not text:
        return 0
    m = re.match(r'^\s*(\d+)\s*([smhd])\s*$', text.lower())
    if not m:
        return 0
    amount = int(m.group(1))
    unit = m.group(2)
    return amount * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]


def make_bar(pct: float, length: int = 10) -> str:
    filled = int(pct / 100 * length)
    if filled > length:
        filled = length
    return "▓" * filled + "░" * (length - filled)


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/polls.json')

    # ==================== Storage helpers ====================

    def _get_poll(self, message_id: str) -> dict:
        return self.db.get(message_id, {})

    def _save_poll(self, message_id: str, data: dict):
        self.db.set(message_id, data)

    def _delete_poll(self, message_id: str):
        self.db.delete(message_id)

    # ==================== Embed builders ====================

    def _build_poll_embed(self, pdata: dict, show_results: bool = False) -> discord.Embed:
        question = pdata.get('question', '')
        options = pdata.get('options', [])
        ended = pdata.get('ended', False)

        if ended:
            title = "📊 Poll — ENDED"
        elif show_results:
            title = "📊 Poll — Live Results"
        else:
            title = "📊 Poll"

        embed = discord.Embed(title=title, description=question, color=0x1a1a2e)

        if show_results or ended:
            # Show results
            votes = pdata.get('votes', {})  # emoji -> count
            total = sum(votes.values()) if votes else 0
            results = []
            for i, opt in enumerate(options):
                emoji = POLL_EMOJIS[i] if i < len(POLL_EMOJIS) else "▪️"
                count = votes.get(emoji, 0)
                pct = (count / total * 100) if total > 0 else 0
                bar = make_bar(pct)
                results.append((count, emoji, opt, count, pct, bar))

            if results:
                # Determine winner (highest count; ties broken by first)
                winner = max(results, key=lambda x: x[0]) if results else None
                for _, emoji, opt, count, pct, bar in results:
                    embed.add_field(
                        name=f"{emoji} {opt}",
                        value=f"`{bar}` {pct:.1f}% — {count} vote(s)",
                        inline=False
                    )
                if winner and winner[0] > 0:
                    embed.set_footer(
                        text=f"Winner: {winner[2]} ({winner[1]}) · {winner[0]} vote(s)"
                    )
                else:
                    embed.set_footer(text="no votes were cast.")
            else:
                embed.add_field(name="Results", value="no options provided.", inline=False)
        else:
            # Show options only
            options_text = "\n".join(
                f"{POLL_EMOJIS[i]} {opt}" for i, opt in enumerate(options) if i < len(POLL_EMOJIS)
            )
            if options_text:
                embed.add_field(name="Options", value=options_text, inline=False)
            footer = f"by <@{pdata.get('author_id', '?')}>"
            end_time = pdata.get('end_time')
            if end_time:
                footer += f" · ends <t:{end_time}:R>"
            embed.set_footer(text=footer)

        return embed

    async def _count_votes(self, channel: discord.TextChannel, message_id: int) -> dict:
        """Fetch the message and return {emoji: count} excluding the bot's own reactions."""
        try:
            msg = await channel.fetch_message(message_id)
        except Exception:
            return {}
        votes = {}
        for reaction in msg.reactions:
            emoji_str = str(reaction.emoji)
            if emoji_str in POLL_EMOJIS:
                # Subtract the bot's own reaction
                try:
                    count = reaction.count - 1
                except Exception:
                    count = 0
                votes[emoji_str] = max(0, count)
        return votes

    async def _end_poll(self, message_id: str, force: bool = False):
        pdata = self._get_poll(message_id)
        if not pdata:
            return
        if pdata.get('ended') and not force:
            return

        channel = self.bot.get_channel(int(pdata['channel_id']))
        if not channel:
            return

        votes = await self._count_votes(channel, int(message_id))
        pdata['votes'] = votes
        pdata['ended'] = True
        self._save_poll(message_id, pdata)

        try:
            msg = await channel.fetch_message(int(message_id))
            embed = self._build_poll_embed(pdata, show_results=True)
            await msg.edit(embed=embed)
        except Exception:
            pass

        # Announce winner
        if votes:
            total = sum(votes.values())
            if total > 0:
                # Find which option had the most votes
                options = pdata.get('options', [])
                winner_emoji = max(votes, key=lambda e: votes[e])
                winner_idx = POLL_EMOJIS.index(winner_emoji) if winner_emoji in POLL_EMOJIS else 0
                if winner_idx < len(options):
                    winner_opt = options[winner_idx]
                    await channel.send(
                        f"📊 Poll ended! Winner: **{winner_opt}** ({winner_emoji}) with {votes[winner_emoji]} vote(s)."
                    )

    # ==================== Commands ====================

    poll = app_commands.Group(name="poll", description="Poll management")

    @poll.command(name="create", description="Create a poll with up to 4 options")
    async def poll_create(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        duration: str = None
    ):
        self.bot.increment_command('poll_create')
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        if len(options) < 2 or len(options) > 4:
            await interaction.response.send_message(
                "you must provide 2-4 options.", ephemeral=True
            )
            return

        seconds = 0
        if duration:
            seconds = parse_duration(duration)
            if seconds <= 0:
                await interaction.response.send_message(
                    "invalid duration. use formats like `10s`, `5m`, `2h`, `1d`.",
                    ephemeral=True
                )
                return
            if seconds > 86400 * 7:
                await interaction.response.send_message(
                    "max poll duration is 7 days.", ephemeral=True
                )
                return

        end_time = None
        if seconds > 0:
            end_time = int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()) + seconds

        pdata = {
            'message_id': None,
            'channel_id': str(interaction.channel.id),
            'guild_id': str(interaction.guild.id),
            'author_id': str(interaction.user.id),
            'question': question,
            'options': options,
            'end_time': end_time,
            'ended': False,
            'votes': {},
        }

        embed = self._build_poll_embed(pdata)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        # Add reactions
        for i in range(len(options)):
            await msg.add_reaction(POLL_EMOJIS[i])

        pdata['message_id'] = str(msg.id)
        self._save_poll(str(msg.id), pdata)

        # Schedule end if duration set
        if seconds > 0:
            self.bot.loop.create_task(self._schedule_end(str(msg.id), seconds))

    async def _schedule_end(self, message_id: str, seconds: int):
        await asyncio.sleep(seconds)
        await self._end_poll(message_id, force=False)

    @poll.command(name="end", description="End a poll early and show results")
    async def poll_end(self, interaction: discord.Interaction, message_id: str):
        self.bot.increment_command('poll_end')
        pdata = self._get_poll(message_id)
        if not pdata:
            await interaction.response.send_message(
                "no poll found with that message id.", ephemeral=True
            )
            return
        if pdata.get('ended'):
            await interaction.response.send_message(
                "that poll already ended.", ephemeral=True
            )
            return
        await self._end_poll(message_id, force=True)
        await interaction.response.send_message("✅ poll ended.")



async def setup(bot):
    await bot.add_cog(Polls(bot))
