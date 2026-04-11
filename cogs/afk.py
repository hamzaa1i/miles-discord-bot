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
        if message.author.bot:
            return
        
        # Check if message author is AFK
        afk_data = self.db.get(str(message.author.id), {})
        if afk_data.get('afk'):
            # Remove AFK
            self.db.delete(str(message.author.id))
            embed = discord.Embed(
                description=f"Welcome back. AFK removed.",
                color=0x1a1a2e
            )
            try:
                await message.reply(embed=embed, mention_author=False)
            except:
                pass
        
        # Check if mentioned users are AFK
        for user in message.mentions:
            if user.bot:
                continue
            user_afk = self.db.get(str(user.id), {})
            if user_afk.get('afk'):
                since = datetime.fromisoformat(user_afk['since'])
                duration = datetime.utcnow() - since
                minutes = int(duration.total_seconds() / 60)
                
                embed = discord.Embed(
                    description=f"{user.mention} is AFK: *{user_afk['reason']}* — {minutes}m ago",
                    color=0x1a1a2e
                )
                try:
                    await message.reply(embed=embed, mention_author=False)
                except:
                    pass
    
    @app_commands.command(name="afk", description="Set your AFK status")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK"):
        """Set AFK"""
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