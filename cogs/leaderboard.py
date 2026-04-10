import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
from utils.embeds import create_embed

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/economy.json')
    
    @app_commands.command(name="leaderboard", description="View top users by coins")
    async def leaderboard(self, interaction: discord.Interaction):
        """Display leaderboard"""
        all_data = self.db.get_all()
        
        # Sort by total wealth (balance + bank)
        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0),
            reverse=True
        )[:10]  # Top 10
        
        if not sorted_users:
            embed = create_embed(
                title="📊 Leaderboard",
                description="No users found yet!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = create_embed(
            title="🏆 Top 10 Richest Users",
            description="",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.name
            except:
                username = f"User {user_id}"
            
            total_wealth = data.get('balance', 0) + data.get('bank', 0)
            medal = medals[idx-1] if idx <= 3 else f"`#{idx}`"
            
            embed.add_field(
                name=f"{medal} {username}",
                value=f"💰 ${total_wealth:,}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rank", description="Check your rank")
    async def rank(self, interaction: discord.Interaction):
        """Show user's rank"""
        all_data = self.db.get_all()
        
        # Sort by total wealth
        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get('balance', 0) + x[1].get('bank', 0),
            reverse=True
        )
        
        # Find user's rank
        user_rank = None
        for idx, (user_id, data) in enumerate(sorted_users, 1):
            if int(user_id) == interaction.user.id:
                user_rank = idx
                user_data = data
                break
        
        if not user_rank:
            embed = create_embed(
                title="📊 Your Rank",
                description="You haven't earned any coins yet!",
                color=discord.Color.orange()
            )
        else:
            total_wealth = user_data.get('balance', 0) + user_data.get('bank', 0)
            
            embed = create_embed(
                title=f"📊 {interaction.user.name}'s Rank",
                color=discord.Color.blue()
            )
            embed.add_field(name="🏅 Rank", value=f"#{user_rank}", inline=True)
            embed.add_field(name="💰 Net Worth", value=f"${total_wealth:,}", inline=True)
            embed.add_field(name="👥 Total Users", value=len(sorted_users), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="stats", description="View detailed statistics")
    async def stats(self, interaction: discord.Interaction):
        """Show detailed user statistics"""
        data = self.db.get(str(interaction.user.id), {})
        
        if not data:
            embed = create_embed(
                title="📊 No Statistics",
                description="You haven't used any economy commands yet!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = create_embed(
            title=f"📊 {interaction.user.name}'s Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💰 Wealth",
            value=(
                f"Wallet: ${data.get('balance', 0):,}\n"
                f"Bank: ${data.get('bank', 0):,}\n"
                f"Net Worth: ${data.get('balance', 0) + data.get('bank', 0):,}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 Earnings",
            value=f"${data.get('total_earned', 0):,}",
            inline=True
        )
        
        embed.add_field(
            name="📉 Spending",
            value=f"${data.get('total_spent', 0):,}",
            inline=True
        )
        
        embed.add_field(
            name="🎒 Items Owned",
            value=len(data.get('inventory', [])),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))