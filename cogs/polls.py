import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import asyncio

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/polls.json')
    
    @app_commands.command(name="poll", description="Create a quick yes/no poll")
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        duration: int = 60
    ):
        """Create yes/no poll"""
        embed = discord.Embed(
            title="Poll",
            description=question,
            color=0x1a1a2e
        )
        embed.set_footer(text=f"Poll ends in {duration} seconds | Created by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        
        await asyncio.sleep(duration)
        
        # Fetch updated message
        msg = await interaction.channel.fetch_message(msg.id)
        
        yes_votes = 0
        no_votes = 0
        
        for reaction in msg.reactions:
            if str(reaction.emoji) == "✅":
                yes_votes = reaction.count - 1
            elif str(reaction.emoji) == "❌":
                no_votes = reaction.count - 1
        
        total = yes_votes + no_votes
        
        result_embed = discord.Embed(
            title="Poll Results",
            description=question,
            color=0x1a1a2e
        )
        
        if total > 0:
            yes_pct = (yes_votes / total) * 100
            no_pct = (no_votes / total) * 100
            
            yes_bar = "▓" * int(yes_pct / 10) + "░" * (10 - int(yes_pct / 10))
            no_bar = "▓" * int(no_pct / 10) + "░" * (10 - int(no_pct / 10))
            
            result_embed.add_field(
                name=f"✅ Yes — {yes_votes} votes",
                value=f"`{yes_bar}` {yes_pct:.1f}%",
                inline=False
            )
            result_embed.add_field(
                name=f"❌ No — {no_votes} votes",
                value=f"`{no_bar}` {no_pct:.1f}%",
                inline=False
            )
        else:
            result_embed.add_field(name="Result", value="No votes were cast.", inline=False)
        
        await msg.edit(embed=result_embed)
    
    @app_commands.command(name="multipoll", description="Create a poll with multiple options")
    async def multipoll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        duration: int = 60
    ):
        """Multi-option poll"""
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        
        embed = discord.Embed(
            title="Poll",
            description=question,
            color=0x1a1a2e
        )
        
        options_text = "\n".join([
            f"{emojis[i]} {opt}"
            for i, opt in enumerate(options)
        ])
        embed.add_field(name="Options", value=options_text, inline=False)
        embed.set_footer(text=f"Poll ends in {duration} seconds")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])
        
        await asyncio.sleep(duration)
        
        msg = await interaction.channel.fetch_message(msg.id)
        
        votes = []
        for reaction in msg.reactions:
            if str(reaction.emoji) in emojis:
                idx = emojis.index(str(reaction.emoji))
                if idx < len(options):
                    votes.append((options[idx], reaction.count - 1, str(reaction.emoji)))
        
        votes.sort(key=lambda x: x[1], reverse=True)
        total = sum(v[1] for v in votes)
        
        result_embed = discord.Embed(
            title="Poll Results",
            description=question,
            color=0x1a1a2e
        )
        
        for option, count, emoji in votes:
            pct = (count / total * 100) if total > 0 else 0
            bar = "▓" * int(pct / 10) + "░" * (10 - int(pct / 10))
            result_embed.add_field(
                name=f"{emoji} {option} — {count} votes",
                value=f"`{bar}` {pct:.1f}%",
                inline=False
            )
        
        await msg.edit(embed=result_embed)

async def setup(bot):
    await bot.add_cog(Polls(bot))