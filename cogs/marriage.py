import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import Database

class Marriage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/marriage.json')
        self.pending = {}

    def get_user(self, user_id: int) -> dict:
        return self.db.get(str(user_id), {
            'married_to': None,
            'married_since': None,
            'proposals_sent': 0,
            'proposals_received': 0,
            'times_divorced': 0
        })

    def save_user(self, user_id: int, data: dict):
        self.db.set(str(user_id), data)

    def is_married(self, user_id: int) -> bool:
        data = self.get_user(user_id)
        return data['married_to'] is not None

    @app_commands.command(name="marry", description="Propose to someone")
    async def marry(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "you can't marry yourself. that's not how this works.",
                ephemeral=True
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "bots don't do relationships. we've discussed this.",
                ephemeral=True
            )
            return

        proposer_data = self.get_user(interaction.user.id)
        target_data = self.get_user(user.id)

        if proposer_data['married_to']:
            await interaction.response.send_message(
                "you're already married. sort that out first.",
                ephemeral=True
            )
            return

        if target_data['married_to']:
            await interaction.response.send_message(
                f"{user.display_name} is already taken.",
                ephemeral=True
            )
            return

        if interaction.user.id in self.pending:
            await interaction.response.send_message(
                "you already have a pending proposal. wait for a response.",
                ephemeral=True
            )
            return

        self.pending[interaction.user.id] = user.id

        embed = discord.Embed(
            description=(
                f"{interaction.user.mention} is proposing to {user.mention}\n\n"
                f"{user.mention} type **yes** or **no** in the next 30 seconds."
            ),
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

        def check(m):
            return (
                m.author.id == user.id
                and m.channel.id == interaction.channel.id
                and m.content.lower() in ['yes', 'no']
            )

        try:
            import asyncio
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)

            if msg.content.lower() == 'yes':
                now = datetime.utcnow().isoformat()

                proposer_data['married_to'] = str(user.id)
                proposer_data['married_since'] = now
                proposer_data['proposals_sent'] += 1

                target_data['married_to'] = str(interaction.user.id)
                target_data['married_since'] = now
                target_data['proposals_received'] += 1

                self.save_user(interaction.user.id, proposer_data)
                self.save_user(user.id, target_data)

                result_embed = discord.Embed(
                    description=f"{interaction.user.mention} and {user.mention} are now married.",
                    color=0x1a1a2e
                )
                await interaction.channel.send(embed=result_embed)
            else:
                proposer_data['proposals_sent'] += 1
                self.save_user(interaction.user.id, proposer_data)
                target_data['proposals_received'] += 1
                self.save_user(user.id, target_data)

                result_embed = discord.Embed(
                    description=f"{user.mention} said no. rough.",
                    color=0x1a1a2e
                )
                await interaction.channel.send(embed=result_embed)

        except Exception:
            result_embed = discord.Embed(
                description=f"{user.mention} didn't respond. left on read.",
                color=0x1a1a2e
            )
            await interaction.channel.send(embed=result_embed)

        finally:
            if interaction.user.id in self.pending:
                del self.pending[interaction.user.id]

    @app_commands.command(name="divorce", description="End your marriage")
    async def divorce(self, interaction: discord.Interaction):
        data = self.get_user(interaction.user.id)

        if not data['married_to']:
            await interaction.response.send_message(
                "you're not married. nothing to end.",
                ephemeral=True
            )
            return

        spouse_id = int(data['married_to'])

        data['married_to'] = None
        data['married_since'] = None
        data['times_divorced'] = data.get('times_divorced', 0) + 1
        self.save_user(interaction.user.id, data)

        spouse_data = self.get_user(spouse_id)
        spouse_data['married_to'] = None
        spouse_data['married_since'] = None
        spouse_data['times_divorced'] = spouse_data.get('times_divorced', 0) + 1
        self.save_user(spouse_id, spouse_data)

        try:
            spouse = await self.bot.fetch_user(spouse_id)
            spouse_name = spouse.mention
        except:
            spouse_name = "your ex"

        embed = discord.Embed(
            description=f"{interaction.user.mention} divorced {spouse_name}.",
            color=0x1a1a2e
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="spouse", description="Check your or someone's marriage status")
    async def spouse(
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

        if data['married_to']:
            try:
                spouse = await self.bot.fetch_user(int(data['married_to']))
                spouse_name = spouse.mention
            except:
                spouse_name = "unknown"

            since = datetime.fromisoformat(data['married_since'])
            days = (datetime.utcnow() - since).days

            embed.add_field(
                name="married to",
                value=spouse_name,
                inline=True
            )
            embed.add_field(
                name="for",
                value=f"{days} days",
                inline=True
            )
        else:
            embed.description = "not married."

        if data.get('times_divorced', 0) > 0:
            embed.set_footer(text=f"divorced {data['times_divorced']} time(s)")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Marriage(bot))