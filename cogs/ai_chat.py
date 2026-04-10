import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from utils.embeds import create_embed

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def get_ai_response(self, prompt):
        """Get AI response from free API"""
        # Using a simple free API that doesn't require authentication
        url = "https://api.popcat.xyz/chatbot"
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "msg": prompt,
                    "owner": "Miles",
                    "botname": "Miles"
                }
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('response', "I'm having trouble thinking right now!")
                    else:
                        return "Sorry, I'm having trouble thinking right now. Try again later!"
        except Exception as e:
            return "Oops! My brain is buffering. Try again in a moment!"
    
    @app_commands.command(name="chat", description="Talk to Miles AI")
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with AI"""
        await interaction.response.defer()
        
        response = await self.get_ai_response(message)
        
        embed = create_embed(
            title="🤖 Miles AI",
            description=response,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Asked by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="quote", description="Get an inspiring quote")
    async def quote(self, interaction: discord.Interaction):
        """Generate motivational quote"""
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Believe you can and you're halfway there. - Theodore Roosevelt",
            "Success is not final, failure is not fatal. - Winston Churchill",
            "The future belongs to those who believe in their dreams. - Eleanor Roosevelt",
            "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
            "The secret of getting ahead is getting started. - Mark Twain",
            "It always seems impossible until it's done. - Nelson Mandela",
            "You are never too old to set another goal. - C.S. Lewis",
            "Be yourself; everyone else is already taken. - Oscar Wilde",
            "Dream big and dare to fail. - Norman Vaughan"
        ]
        
        quote = random.choice(quotes)
        
        embed = create_embed(
            title="✨ Quote of the Moment",
            description=f"*{quote}*",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="roast", description="Get a friendly roast")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        """Roast a user (friendly)"""
        target = user or interaction.user
        
        roasts = [
            f"{target.mention} You're like a software update. Whenever I see you, I think 'Not now.'",
            f"{target.mention} I'd agree with you, but then we'd both be wrong!",
            f"{target.mention} You're proof that evolution can go in reverse.",
            f"{target.mention} I'm jealous of people who haven't met you yet.",
            f"{target.mention} You're not stupid; you just have bad luck thinking.",
            f"{target.mention} If I wanted to hear from you, I'd read your error logs.",
            f"{target.mention} You're like a cloud. When you disappear, it's a beautiful day.",
            f"{target.mention} I'd explain it to you, but I left my crayons at home."
        ]
        
        roast = random.choice(roasts)
        
        embed = create_embed(
            title=f"🔥 Roasting {target.name}",
            description=roast,
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))