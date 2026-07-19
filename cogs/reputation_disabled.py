"""
cogs/reputation.py — reputation system.

Spec (ADD 7):
  Data stored in data/reputation.json per user:
    { "rep": 0, "last_given": "iso", "received_from": [], "given_to": [] }

  /rep give @user [reason(optional)] — give someone +1 rep
    - 24 hour cooldown per GIVER (not per recipient)
    - Cannot give yourself rep
    - Cannot give bots rep
    - Shows confirmation with their new total
  /rep check @user — see someone's reputation score
  /rep leaderboard — top 10 reputation in the server
  /rep reset @user — owner only, reset a user's rep to 0
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import os
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))


class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/reputation.json')

    def get_user(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'rep': 0,
            'last_given': None,
            'received_from': [],
            'given_to': []
        })

    def save_user(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    rep = app_commands.Group(name="rep", description="Reputation system")

    @rep.command(name="give", description="Give someone +1 reputation")
    async def rep_give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = None
    ):
        self.bot.increment_command('rep_give')
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "you can't rep yourself.", ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "bots don't need reputation.", ephemeral=True
            )
            return

        giver_data = self.get_user(interaction.user.id)

        # 24h cooldown per giver
        if giver_data.get('last_given'):
            try:
                last = datetime.fromisoformat(giver_data['last_given'])
            except Exception:
                last = None
            if last:
                diff = datetime.utcnow() - last
                if diff < timedelta(hours=24):
                    remaining = timedelta(hours=24) - diff
                    h = remaining.seconds // 3600
                    m = (remaining.seconds % 3600) // 60
                    await interaction.response.send_message(
                        f"⏱️ you already gave rep in the last 24h. try again in {h}h {m}m.",
                        ephemeral=True
                    )
                    return

        receiver_data = self.get_user(user.id)
        receiver_data['rep'] = receiver_data.get('rep', 0) + 1
        if str(interaction.user.id) not in receiver_data.get('received_from', []):
            receiver_data.setdefault('received_from', []).append(str(interaction.user.id))

        giver_data['last_given'] = datetime.utcnow().isoformat()
        if str(user.id) not in giver_data.get('given_to', []):
            giver_data.setdefault('given_to', []).append(str(user.id))

        self.save_user(interaction.user.id, giver_data)
        self.save_user(user.id, receiver_data)

        embed = discord.Embed(
            description=(
                f"✅ +1 rep to {user.mention}.\n"
                f"they now have **{receiver_data['rep']} rep**."
                + (f"\nreason: *{reason}*" if reason else "")
            ),
            color=0x1a1a2e
        )
        embed.set_footer(text=f"by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


    @rep.command(name="leaderboard", description="Top 10 reputation in the server")
    async def rep_leaderboard(self, interaction: discord.Interaction):
        self.bot.increment_command('rep_leaderboard')
        await interaction.response.defer()
        all_data = self.db.get_all()
        # Filter to members of this guild
        guild_member_ids = {str(m.id) for m in interaction.guild.members}
        filtered = [
            (uid, data.get('rep', 0))
            for uid, data in all_data.items()
            if uid in guild_member_ids and isinstance(data, dict)
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)
        top = filtered[:10]
        if not top:
            await interaction.followup.send("no rep data yet.")
            return
        embed = discord.Embed(title="🏆 Reputation Leaderboard", color=0x1a1a2e)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        desc = ""
        for idx, (uid, rep) in enumerate(top, 1):
            try:
                user_obj = await self.bot.fetch_user(int(uid))
                name = user_obj.name
            except Exception:
                # FIX 9-style: wrap fetches in try/except
                name = f"User {uid}"
            medal = medals.get(idx, f"`#{idx}`")
            desc += f"{medal} **{name}** — {rep} rep\n"
        embed.description = desc
        await interaction.followup.send(embed=embed)

    @rep.command(name="reset", description="Reset a user's reputation to 0 (owner only)")
    async def rep_reset(self, interaction: discord.Interaction, user: discord.Member):
        self.bot.increment_command('rep_reset')
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ only the bot owner can reset reputation.", ephemeral=True
            )
            return
        data = self.get_user(user.id)
        data['rep'] = 0
        data['received_from'] = []
        self.save_user(user.id, data)
        await interaction.response.send_message(
            f"✅ reset {user.mention}'s reputation to 0."
        )




async def setup(bot):
    await bot.add_cog(Reputation(bot))
