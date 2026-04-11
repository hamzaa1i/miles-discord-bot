import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from utils.database import Database

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/reputation.json')

    def get_user(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'rep': 0,
            'last_given': None,
            'given_to': [],
            'received_from': []
        })

    def save_user(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    @app_commands.command(name="rep", description="Give someone reputation points")
    async def rep(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "you can't rep yourself.",
                ephemeral=True
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "bots don't need reputation.",
                ephemeral=True
            )
            return

        giver_data = self.get_user(interaction.user.id)

        if giver_data['last_given']:
            last = datetime.fromisoformat(giver_data['last_given'])
            diff = datetime.utcnow() - last
            if diff < timedelta(hours=24):
                remaining = timedelta(hours=24) - diff
                h = remaining.seconds // 3600
                m = (remaining.seconds % 3600) // 60
                await interaction.response.send_message(
                    f"already gave rep today. try again in {h}h {m}m.",
                    ephemeral=True
                )
                return

        receiver_data = self.get_user(user.id)
        receiver_data['rep'] += 1

        if str(interaction.user.id) not in receiver_data['received_from']:
            receiver_data['received_from'].append(str(interaction.user.id))

        giver_data['last_given'] = datetime.utcnow().isoformat()
        if str(user.id) not in giver_data['given_to']:
            giver_data['given_to'].append(str(user.id))

        self.save_user(interaction.user.id, giver_data)
        self.save_user(user.id, receiver_data)

        embed = discord.Embed(
            description=f"+1 rep to {user.mention}. they now have **{receiver_data['rep']} rep**",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="repcheck", description="Check reputation of a user")
    async def repcheck(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        target = user or interaction.user
        data = self.get_user(target.id)

        embed = discord.Embed(color=0x1a1a2e)
        embed.set_author(
            name=target.display_name,
            icon_url=target.avatar.url if target.avatar else None
        )
        embed.add_field(
            name="reputation",
            value=f"**{data['rep']}** points",
            inline=True
        )
        embed.add_field(
            name="received from",
            value=f"{len(data['received_from'])} users",
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="replb", description="Reputation leaderboard")
    async def replb(self, interaction: discord.Interaction):
        all_data = self.db.get_all()

        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('rep', 0),
            reverse=True
        )[:10]

        if not sorted_users:
            await interaction.response.send_message(
                "no rep data yet.",
                ephemeral=True
            )
            return

        embed = discord.Embed(title="Rep Leaderboard", color=0x1a1a2e)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        desc = ""

        for idx, (uid, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.name
            except:
                name = f"User {uid}"
            medal = medals.get(idx, f"`#{idx}`")
            desc += f"{medal} **{name}** — {data.get('rep', 0)} rep\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Reputation(bot))