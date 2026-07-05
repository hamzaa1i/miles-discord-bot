import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
from datetime import datetime


class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/afk.json')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Never process bot messages
        if message.author.bot:
            return

        # FIX 9 (1) — only remove AFK on genuine chat messages,
        # not on slash commands or prefix commands.
        content_stripped = message.content.strip()
        is_command = (
            content_stripped.startswith('/')
            or content_stripped.startswith('!')
        )

        # If the author is currently AFK and this is a real chat message,
        # remove the AFK status and let them know.
        try:
            afk_data = self.db.get(str(message.author.id), {})
        except Exception:
            afk_data = {}

        if afk_data.get('afk') and not is_command:
            try:
                self.db.delete(str(message.author.id))
            except Exception:
                pass
            embed = discord.Embed(
                description=f"Welcome back {message.author.display_name}! Removed your AFK.",
                color=0x1a1a2e
            )
            try:
                await message.reply(embed=embed, mention_author=False)
            except Exception:
                pass

        # FIX 9 (2) — when checking mentioned users for AFK status,
        # skip if the message author IS the AFK user (don't notify
        # someone they pinged themselves while AFK)
        for user in message.mentions:
            if user.bot:
                continue
            if user.id == message.author.id:
                # Don't notify the author about their own AFK status
                continue

            try:
                user_afk = self.db.get(str(user.id), {})
            except Exception:
                # FIX 9 (3) — wrap member/data fetches in try/except so a
                # corrupt or missing entry never crashes the listener
                continue

            if not user_afk.get('afk'):
                continue

            try:
                since = datetime.fromisoformat(user_afk['since'])
                duration = datetime.utcnow() - since
                minutes = int(duration.total_seconds() / 60)
            except Exception:
                minutes = 0

            embed = discord.Embed(
                description=(
                    f"{user.mention} is AFK: *{user_afk.get('reason', 'AFK')}* "
                    f"— {minutes}m ago"
                ),
                color=0x1a1a2e
            )
            try:
                await message.reply(embed=embed, mention_author=False)
            except Exception:
                pass

    @app_commands.command(name="afk", description="Set your AFK status")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        """Set AFK"""
        self.bot.increment_command('afk')
        self.db.set(str(interaction.user.id), {
            'afk': True,
            'reason': reason,
            'since': datetime.utcnow().isoformat()
        })

        embed = discord.Embed(
            description=f"AFK set: *{reason}*",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(AFK(bot))
