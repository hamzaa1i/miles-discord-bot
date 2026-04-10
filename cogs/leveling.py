import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.embeds import create_embed
from utils.database import Database

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database('data/leveling.json')
        self.cooldowns = {}
    
    def get_user_data(self, guild_id: int, user_id: int):
        """Get user level data"""
        data = self.db.get(f"{guild_id}_{user_id}", {
            'xp': 0,
            'level': 1,
            'messages': 0
        })
        return data
    
    def save_user_data(self, guild_id: int, user_id: int, data):
        """Save user level data"""
        self.db.set(f"{guild_id}_{user_id}", data)
    
    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a level"""
        return 5 * (level ** 2) + 50 * level + 100
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Award XP for messages"""
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        # Cooldown check (1 XP per minute max)
        key = f"{message.guild.id}_{message.author.id}"
        if key in self.cooldowns:
            return
        
        self.cooldowns[key] = True
        
        # Award XP
        data = self.get_user_data(message.guild.id, message.author.id)
        xp_gain = random.randint(15, 25)
        data['xp'] += xp_gain
        data['messages'] += 1
        
        # Check for level up
        xp_needed = self.calculate_xp_for_level(data['level'])
        
        if data['xp'] >= xp_needed:
            data['level'] += 1
            data['xp'] = 0
            
            # Level up message
            embed = create_embed(
                title="🎉 Level Up!",
                description=f"{message.author.mention} reached **Level {data['level']}**!",
                color=discord.Color.gold()
            )
            
            try:
                await message.channel.send(embed=embed)
            except:
                pass
        
        self.save_user_data(message.guild.id, message.author.id, data)
        
        # Remove cooldown after 60 seconds
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=60))
        if key in self.cooldowns:
            del self.cooldowns[key]
    
    @app_commands.command(name="level", description="Check your or someone's level")
    async def level(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check level"""
        user = user or interaction.user
        data = self.get_user_data(interaction.guild.id, user.id)
        
        xp_needed = self.calculate_xp_for_level(data['level'])
        progress = (data['xp'] / xp_needed) * 100
        
        embed = create_embed(
            title=f"📊 {user.name}'s Level",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        
        embed.add_field(name="Level", value=f"⭐ {data['level']}", inline=True)
        embed.add_field(name="XP", value=f"{data['xp']} / {xp_needed}", inline=True)
        embed.add_field(name="Messages", value=data['messages'], inline=True)
        
        # Progress bar
        bar_length = 10
        filled = int((progress / 100) * bar_length)
        bar = "▓" * filled + "░" * (bar_length - filled)
        embed.add_field(name="Progress", value=f"`{bar}` {progress:.1f}%", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard_levels", description="View level leaderboard")
    async def leaderboard_levels(self, interaction: discord.Interaction):
        """Level leaderboard"""
        all_data = self.db.get_all()
        
        # Filter for this guild
        guild_data = {}
        for key, value in all_data.items():
            if key.startswith(f"{interaction.guild.id}_"):
                user_id = int(key.split('_')[1])
                guild_data[user_id] = value
        
        # Sort by level, then XP
        sorted_users = sorted(
            guild_data.items(),
            key=lambda x: (x[1].get('level', 1), x[1].get('xp', 0)),
            reverse=True
        )[:10]
        
        if not sorted_users:
            await interaction.response.send_message("📊 No level data yet!", ephemeral=True)
            return
        
        embed = create_embed(
            title="🏆 Level Leaderboard",
            description=f"Top users in {interaction.guild.name}",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(user_id)
                medal = medals[idx-1] if idx <= 3 else f"`#{idx}`"
                
                embed.add_field(
                    name=f"{medal} {user.name}",
                    value=f"Level {data['level']} • {data['xp']} XP • {data['messages']} msgs",
                    inline=False
                )
            except:
                pass
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))