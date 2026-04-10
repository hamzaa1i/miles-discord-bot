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
        
        # Miles personality
        self.system_prompt = """You are Miles, a professional and intelligent Discord bot assistant.

Personality:
- Professional yet approachable
- Clear and concise communication
- Minimal to no emojis
- Provide well-structured, informative responses
- Helpful and efficient
- Maintain a mature, respectful tone

Focus on delivering value in every response."""

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
        """Get AI response from GitHub Models using aiohttp"""
        if not self.github_token:
            return "My brain isn't connected! Ask the bot owner to add the GITHUB_TOKEN."
        
        try:
            # Get conversation history
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            history = self.conversation_history[user_id][-6:]
            
            # Build messages
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            # API request
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.7,
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
                        
                        # Save to history
                        self.conversation_history[user_id].append({"role": "user", "content": message})
                        self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
                        
                        # Trim history
                        if len(self.conversation_history[user_id]) > 12:
                            self.conversation_history[user_id] = self.conversation_history[user_id][-12:]
                        
                        return ai_response
                    elif response.status == 401:
                        return "My brain token is invalid! Ask the bot owner to check GITHUB_TOKEN."
                    elif response.status == 429:
                        return "I'm being rate limited. Try again in a few seconds!"
                    else:
                        error_text = await response.text()
                        print(f"API Error {response.status}: {error_text}")
                        return "Oops, my brain glitched. Try again?"
                        
        except asyncio.TimeoutError:
            return "Sorry, I'm thinking too slow right now. Try again?"
        except Exception as e:
            print(f"AI Error: {e}")
            return "Oops, something went wrong. Try again?"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Respond when bot is mentioned"""
        if message.author.bot:
            return
        
        # Check if bot was mentioned
        if self.bot.user in message.mentions:
            # Check rate limit
            is_limited, remaining = self.check_rate_limit(message.author.id)
            if is_limited:
                await message.reply(
                    f"⏰ Slow down! You can chat again in **{remaining}s**",
                    mention_author=False
                )
                return
            
            # Remove mention from message
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
            
            # Just pinged with no message
            if not content:
                greetings = [
                    "Hey! What's up? 👋",
                    "Yo, you called?",
                    "What can I do for you?",
                    "Hey there! Need something?",
                    "I'm here! What's on your mind?"
                ]
                await message.reply(random.choice(greetings), mention_author=False)
                return
            
            # Update rate limit
            self.update_rate_limit(message.author.id)
            
            # Show typing indicator
            async with message.channel.typing():
                response = await self.get_ai_response(message.author.id, content)
            
            # Reply naturally
            await message.reply(response, mention_author=False)

    @app_commands.command(name="chat", description="Talk to Miles AI")
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with slash command"""
        # Check rate limit
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            embed = create_embed(
                title="⏰ Cooldown Active",
                description=f"You can chat again in **{remaining} seconds**",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Respond immediately
        await interaction.response.send_message("💭 Thinking...")
        
        # Update rate limit
        self.update_rate_limit(interaction.user.id)
        
        # Get AI response
        response = await self.get_ai_response(interaction.user.id, message)
        
        # Edit response with embed
        embed = create_embed(
            title="🤖 Miles",
            description=response,
            color=discord.Color.blue()
        )
        embed.set_footer(
            text=f"Chatting with {interaction.user.name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="clear_chat", description="Clear conversation history")
    async def clear_chat(self, interaction: discord.Interaction):
        """Clear conversation history"""
        if interaction.user.id in self.conversation_history:
            del self.conversation_history[interaction.user.id]
        
        embed = create_embed(
            title="🧹 Chat Cleared",
            description="Fresh start! I've forgotten our conversation.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="quote", description="Get an inspiring quote")
    async def quote(self, interaction: discord.Interaction):
        """Generate quote"""
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Believe you can and you're halfway there. - Theodore Roosevelt",
            "Success is not final, failure is not fatal. - Winston Churchill",
            "It always seems impossible until it's done. - Nelson Mandela",
            "Dream big and dare to fail. - Norman Vaughan",
            "The secret of getting ahead is getting started. - Mark Twain",
            "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
            "You are never too old to set another goal. - C.S. Lewis",
            "Be yourself; everyone else is already taken. - Oscar Wilde",
            "The future belongs to those who believe in their dreams. - Eleanor Roosevelt"
        ]
        
        embed = create_embed(
            title="✨ Quote of the Moment",
            description=f"*{random.choice(quotes)}*",
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roast", description="Get a friendly roast")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        """Friendly roast"""
        target = user or interaction.user
        
        roasts = [
            f"{target.mention}, you're like a software update. Whenever I see you, I think 'Not now.'",
            f"{target.mention}, I'd agree with you, but then we'd both be wrong!",
            f"{target.mention}, you're not stupid; you just have bad luck thinking.",
            f"{target.mention}, I'm jealous of people who haven't met you yet.",
            f"{target.mention}, you're like a cloud. When you disappear, it's a beautiful day.",
            f"{target.mention}, if I wanted to hear from you, I'd read your error logs.",
            f"{target.mention}, you're proof that evolution can go in reverse.",
            f"{target.mention}, I'd explain it to you, but I left my crayons at home."
        ]
        
        embed = create_embed(
            title=f"🔥 Roasting {target.display_name}",
            description=random.choice(roasts),
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ask", description="Ask Miles anything")
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a question"""
        # Check rate limit
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            embed = create_embed(
                title="⏰ Cooldown Active",
                description=f"You can ask again in **{remaining} seconds**",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Respond immediately
        await interaction.response.send_message("🤔 Let me think...")
        
        # Update rate limit
        self.update_rate_limit(interaction.user.id)
        
        # Get response
        if self.github_token:
            try:
                headers = {
                    "Authorization": f"Bearer {self.github_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Give clear, accurate, concise answers. Max 3 sentences."},
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
                            answer = "I couldn't process that question right now."
            except Exception as e:
                print(f"Ask Error: {e}")
                answer = "Sorry, that's taking too long. Try a simpler question?"
        else:
            answer = "My brain isn't connected! Ask the bot owner to add the GITHUB_TOKEN."
        
        embed = create_embed(
            title="💡 Answer",
            color=discord.Color.blue()
        )
        embed.add_field(name="Question", value=question[:1024], inline=False)
        embed.add_field(name="Answer", value=answer[:1024], inline=False)
        embed.set_footer(
            text=f"Asked by {interaction.user.name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        
        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))