import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from utils.embeds import create_embed

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.openrouter.ai/api/v1/chat/completions"
        # Free AI models we can use
        self.models = [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.2-11b-vision-instruct:free"
        ]
    
    async def get_ai_response(self, prompt, system_message="You are Miles, a helpful and friendly Discord bot assistant. Keep responses concise and casual."):
        """Get AI response from free API"""
        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "model": random.choice(self.models),
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        return "Sorry, I'm having trouble thinking right now. Try again later!"
        except Exception as e:
            return f"Oops! Something went wrong: {str(e)}"
    
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
        await interaction.response.defer()
        
        prompt = "Generate one short, original motivational quote. Just the quote, no explanation."
        response = await self.get_ai_response(prompt)
        
        embed = create_embed(
            title="✨ Quote of the Moment",
            description=f"*{response}*",
            color=discord.Color.purple()
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="roast", description="Get a friendly AI roast")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        """Roast a user (friendly)"""
        await interaction.response.defer()
        
        target = user or interaction.user
        prompt = f"Give a short, funny, friendly roast for someone named {target.name}. Keep it light and playful, not mean."
        
        response = await self.get_ai_response(prompt)
        
        embed = create_embed(
            title=f"🔥 Roasting {target.name}",
            description=response,
            color=discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))