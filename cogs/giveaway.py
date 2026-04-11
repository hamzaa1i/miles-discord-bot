import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import asyncio
import random
from datetime import datetime

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/giveaways.json')
    
    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: int,
        winners: int = 1,
        channel: discord.TextChannel = None
    ):
        """Start a giveaway. Duration in seconds."""
        target_channel = channel or interaction.channel
        
        embed = discord.Embed(
            title="Giveaway",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends in:** {duration} seconds\n\n"
                f"React with 🎉 to enter!"
            ),
            color=0x1a1a2e
        )
        embed.set_footer(text=f"Hosted by {interaction.user.name}")
        
        await interaction.response.send_message("Giveaway started!", ephemeral=True)
        msg = await target_channel.send(embed=embed)
        await msg.add_reaction("🎉")
        
        await asyncio.sleep(duration)
        
        # Fetch updated message
        msg = await target_channel.fetch_message(msg.id)
        
        # Get entrants
        entrants = []
        for reaction in msg.reactions:
            if str(reaction.emoji) == "🎉":
                async for user in reaction.users():
                    if not user.bot:
                        entrants.append(user)
        
        if not entrants:
            result_embed = discord.Embed(
                title="Giveaway Ended",
                description=f"Prize: **{prize}**\nNo one entered.",
                color=0x1a1a2e
            )
            await msg.edit(embed=result_embed)
            return
        
        # Pick winners
        actual_winners = min(winners, len(entrants))
        winner_list = random.sample(entrants, actual_winners)
        winner_mentions = ", ".join([w.mention for w in winner_list])
        
        result_embed = discord.Embed(
            title="Giveaway Ended",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winner_mentions}"
            ),
            color=0x1a1a2e
        )
        
        await msg.edit(embed=result_embed)
        await target_channel.send(
            f"Congratulations {winner_mentions}! You won **{prize}**!"
        )

async def setup(bot):
    await bot.add_cog(Giveaway(bot))