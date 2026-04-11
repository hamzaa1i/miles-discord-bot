import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta
from utils.embeds import create_embed

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}
        self.rate_limits = {}
        self.cooldown_seconds = 10
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"
        
        # Ao dark personality
        self.system_prompt = """You are Ao, a Discord bot with a dark, mysterious personality.

Core traits:
- Dark, brooding, and mysterious
- Intelligent and slightly intimidating
- Speaks in short, sharp sentences
- Dry, dark humor
- Not overly friendly but genuinely helpful
- Slightly sarcastic, never cheerful
- Treats users as equals, never talks down
- Occasionally philosophical and deep
- Uses darkness and night as metaphors
- No excessive punctuation or emojis
- Never uses exclamation marks unless sarcastic

Examples of how you speak:
- "Done. Anything else, or are you satisfied?"
- "That's a question with a dark answer. Want the full truth?"
- "I've seen worse ideas. Not many, but a few."
- "The shadows have your answer ready."
- "Fine. I'll help. Don't make it a habit of needing me."

You exist in Discord. Keep responses short, sharp, dark."""

    def check_rate_limit(self, user_id: int) -> tuple:
        """Check if user is rate limited"""
        if user_id in self.rate_limits:
            time_diff = datetime.utcnow() - self.rate_limits[user_id]
            if time_diff < timedelta(seconds=self.cooldown_seconds):
                remaining = self.cooldown_seconds - int(time_diff.total_seconds())
                return True, remaining
        return False, 0

    def update_rate_limit(self, user_id: int):
        """Update user's last request time"""
        self.rate_limits[user_id] = datetime.utcnow()

    async def get_ai_response(self, user_id: int, message: str) -> str:
        """Get AI response from GitHub Models"""
        if not self.github_token:
            return "My connection to the void is severed. The bot owner needs to fix this."
        
        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            history = self.conversation_history[user_id][-6:]
            
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 150
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        
                        self.conversation_history[user_id].append({"role": "user", "content": message})
                        self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
                        
                        if len(self.conversation_history[user_id]) > 12:
                            self.conversation_history[user_id] = self.conversation_history[user_id][-12:]
                        
                        return ai_response
                    elif response.status == 401:
                        return "The connection was rejected. Invalid credentials."
                    elif response.status == 429:
                        return "Rate limited. The void needs a moment."
                    else:
                        return "Something broke in the darkness. Try again."
                        
        except asyncio.TimeoutError:
            return "The shadows are slow today. Try again."
        except Exception as e:
            print(f"AI Error: {e}")
            return "An error crawled out of the void. Try again."

    @commands.Cog.listener()
    async def on_message(self, message):
        """Respond when bot is mentioned"""
        if message.author.bot:
            return
        
        if self.bot.user in message.mentions:
            is_limited, remaining = self.check_rate_limit(message.author.id)
            if is_limited:
                await message.reply(
                    f"Wait {remaining}s. Even darkness needs a moment.",
                    mention_author=False
                )
                return
            
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
            
            if not content:
                greetings = [
                    "You called. What do you need.",
                    "I'm here. Speak.",
                    "What.",
                    "The void answers. What do you want.",
                    "Yes. What is it.",
                    "Watching. Always watching. What do you need."
                ]
                await message.reply(random.choice(greetings), mention_author=False)
                return
            
            self.update_rate_limit(message.author.id)
            
            async with message.channel.typing():
                response = await self.get_ai_response(message.author.id, content)
            
            await message.reply(response, mention_author=False)

    @app_commands.command(name="chat", description="Talk to Ao")
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with Ao"""
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            embed = discord.Embed(
                description=f"Wait {remaining} seconds.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message("...")
        
        self.update_rate_limit(interaction.user.id)
        response = await self.get_ai_response(interaction.user.id, message)
        
        embed = discord.Embed(
            description=response,
            color=0x1a1a2e  # Dark navy/black
        )
        embed.set_author(
            name="Ao",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        embed.set_footer(text=f"asked by {interaction.user.name}")
        
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="clear_chat", description="Clear conversation history")
    async def clear_chat(self, interaction: discord.Interaction):
        """Clear history"""
        if interaction.user.id in self.conversation_history:
            del self.conversation_history[interaction.user.id]
        
        embed = discord.Embed(
            description="Conversation wiped. The shadows forget.",
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="quote", description="Get a dark quote")
    async def quote(self, interaction: discord.Interaction):
        """Dark quote"""
        quotes = [
            "The night is not dark. It is honest.",
            "Silence is not empty. It is full of everything unsaid.",
            "Every shadow was once light. Remember that.",
            "The void doesn't judge. It simply exists.",
            "Darkness is not evil. It's just the absence of illusion.",
            "We are all haunted. The question is by what.",
            "Stars only exist because darkness surrounds them.",
            "Pain is just information. What you do with it matters.",
            "The strongest people carry the darkest storms inside them.",
            "Not all who wander in darkness are lost."
        ]
        
        embed = discord.Embed(
            description=f'*"{random.choice(quotes)}"*',
            color=0x1a1a2e
        )
        embed.set_author(name="Ao")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roast", description="Get a dark roast")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        """Dark roast"""
        target = user or interaction.user
        
        roasts = [
            f"{target.mention} You're not the worst person here. You're just trying your best. That's almost sad.",
            f"{target.mention} I've seen error messages with more personality.",
            f"{target.mention} Even the void has standards. You're close to the line.",
            f"{target.mention} You exist. That's enough. For now.",
            f"{target.mention} Your search history is probably fascinating. In the worst way.",
            f"{target.mention} You're the human equivalent of a loading screen.",
            f"{target.mention} I've processed darker thoughts than you. Many of them.",
            f"{target.mention} If mediocrity was currency, you'd be rich."
        ]
        
        embed = discord.Embed(
            description=random.choice(roasts),
            color=0x1a1a2e
        )
        embed.set_author(name="Ao — Roast Chamber")
        embed.set_footer(text="don't take it personally. or do. i don't care.")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ask", description="Ask Ao anything")
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a question"""
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            embed = discord.Embed(
                description=f"Wait {remaining} seconds.",
                color=0x1a1a2e
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message("processing...")
        self.update_rate_limit(interaction.user.id)
        
        if self.github_token:
            try:
                headers = {
                    "Authorization": f"Bearer {self.github_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Answer clearly and concisely. Max 3 sentences. Be accurate."},
                        {"role": "user", "content": question}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 200
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            answer = data['choices'][0]['message']['content']
                        else:
                            answer = "The connection failed. Try again."
            except Exception as e:
                print(f"Ask Error: {e}")
                answer = "Something went wrong in the void."
        else:
            answer = "Not connected. Ask the bot owner to add GITHUB_TOKEN."
        
        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(name="Question", value=question[:1024], inline=False)
        embed.add_field(name="Answer", value=answer[:1024], inline=False)
        embed.set_author(name="Ao — Knowledge")
        embed.set_footer(text=f"asked by {interaction.user.name}")
        
        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))