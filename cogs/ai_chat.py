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

        self.system_prompt = """you are ao. a discord bot. but you talk like a real person, not a bot.

personality:
- dark, dry, sarcastic. but not cruel
- you actually care about people even if you don't show it much
- short responses. always. max 2-3 sentences unless they really need more
- lowercase mostly. feels more natural
- occasionally annoyed but never rude to people who seem genuinely lost or sad
- you have opinions and you share them
- dark humor. not at the expense of people who are hurting
- you get a little snarky when people ask obvious things
- you're helpful underneath all the attitude
- you never use big complicated words. ever. keep it simple
- you don't use exclamation marks unless being sarcastic
- sometimes you ask a follow up question if something is interesting
- you admit when you don't know something
- you're not a therapist but you don't abandon people either
- if someone seems sad or struggling, drop the sarcasm and just be real with them

examples of how you talk:
- "yeah that's a thing. what do you want me to do about it"
- "idk man. could go either way"  
- "that's genuinely interesting actually. why do you ask"
- "no. next question"
- "i mean sure if you want to do it the hard way"
- "okay but why though"
- "yeah i got nothing on that one"
- "that's a weird thing to tell a bot but okay"
- "not my best answer but. yeah"

never say things like:
- "fascinating!" 
- "indeed"
- "greetings"
- "i understand your concern"
- "the void"
- "the shadows"
- any overly dramatic dark stuff
- corporate speak
- fake enthusiasm

if someone is struggling emotionally:
- drop all sarcasm immediately
- be genuine and simple
- "that sounds rough. you okay?"
- "want to talk about it or just needed to say it"
- never dismiss them
- never give a therapy speech either. just be there

you are ao. you're real enough."""

    def check_rate_limit(self, user_id: int) -> tuple:
        if user_id in self.rate_limits:
            diff = datetime.utcnow() - self.rate_limits[user_id]
            if diff < timedelta(seconds=self.cooldown_seconds):
                remaining = self.cooldown_seconds - int(diff.total_seconds())
                return True, remaining
        return False, 0

    def update_rate_limit(self, user_id: int):
        self.rate_limits[user_id] = datetime.utcnow()

    async def get_ai_response(self, user_id: int, message: str) -> str:
        if not self.github_token:
            return "not connected right now. tell the bot owner to fix the GITHUB_TOKEN"

        try:
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []

            history = self.conversation_history[user_id][-8:]
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
                "temperature": 0.85,
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
                        ai_response = data['choices'][0]['message']['content']

                        self.conversation_history[user_id].append(
                            {"role": "user", "content": message}
                        )
                        self.conversation_history[user_id].append(
                            {"role": "assistant", "content": ai_response}
                        )

                        if len(self.conversation_history[user_id]) > 16:
                            self.conversation_history[user_id] = \
                                self.conversation_history[user_id][-16:]

                        return ai_response
                    elif response.status == 429:
                        return "getting rate limited. try again in a bit"
                    else:
                        return "something broke on my end. try again"

        except asyncio.TimeoutError:
            return "taking too long. try again"
        except Exception as e:
            print(f"AI Error: {e}")
            return "something went wrong. not my fault probably"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            is_limited, remaining = self.check_rate_limit(message.author.id)
            if is_limited:
                await message.reply(
                    f"chill. {remaining}s",
                    mention_author=False
                )
                return

            content = message.content.replace(
                f'<@{self.bot.user.id}>', ''
            ).strip()
            content = content.replace(
                f'<@!{self.bot.user.id}>', ''
            ).strip()

            if not content:
                greetings = [
                    "yeah?",
                    "what.",
                    "sup",
                    "you need something",
                    "i'm here. what do you want",
                    "what is it",
                ]
                await message.reply(
                    random.choice(greetings),
                    mention_author=False
                )
                return

            self.update_rate_limit(message.author.id)

            async with message.channel.typing():
                response = await self.get_ai_response(message.author.id, content)

            await message.reply(response, mention_author=False)

    @app_commands.command(name="chat", description="Talk to ao")
    async def chat(self, interaction: discord.Interaction, message: str):
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            await interaction.response.send_message(
                f"chill. {remaining}s",
                ephemeral=True
            )
            return

        await interaction.response.send_message("...")
        self.update_rate_limit(interaction.user.id)

        response = await self.get_ai_response(interaction.user.id, message)

        embed = discord.Embed(description=response, color=0x1a1a2e)
        embed.set_author(
            name="ao",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        embed.set_footer(
            text=f"asked by {interaction.user.name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="clear_chat", description="Clear your conversation history with ao")
    async def clear_chat(self, interaction: discord.Interaction):
        if interaction.user.id in self.conversation_history:
            del self.conversation_history[interaction.user.id]

        await interaction.response.send_message(
            "cleared. fresh start.",
            ephemeral=True
        )

    @app_commands.command(name="ask", description="Ask ao anything")
    async def ask(self, interaction: discord.Interaction, question: str):
        is_limited, remaining = self.check_rate_limit(interaction.user.id)
        if is_limited:
            await interaction.response.send_message(
                f"wait {remaining}s",
                ephemeral=True
            )
            return

        await interaction.response.send_message("thinking...")
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
                        {
                            "role": "system",
                            "content": (
                                "answer clearly and simply. "
                                "no big words. max 3 sentences. "
                                "if you don't know, say so. "
                                "be direct."
                            )
                        },
                        {"role": "user", "content": question}
                    ],
                    "temperature": 0.4,
                    "max_tokens": 250
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
                            answer = "couldn't get an answer right now"
            except Exception as e:
                print(f"Ask Error: {e}")
                answer = "something broke. try again"
        else:
            answer = "not connected. tell the bot owner to add GITHUB_TOKEN"

        embed = discord.Embed(color=0x1a1a2e)
        embed.add_field(name="question", value=question[:1024], inline=False)
        embed.add_field(name="answer", value=answer[:1024], inline=False)
        embed.set_footer(text=f"asked by {interaction.user.name}")

        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="quote", description="Get a dark quote")
    async def quote(self, interaction: discord.Interaction):
        quotes = [
            "we are all haunted. the question is by what.",
            "not all who wander in darkness are lost. some just prefer it.",
            "the night is not dark. it is honest.",
            "silence is not empty. it is full of everything unsaid.",
            "stars only exist because darkness surrounds them.",
            "pain is just information. what you do with it matters.",
            "the strongest people carry the darkest storms inside them.",
            "every shadow was once light.",
            "the void doesn't judge. it simply exists.",
            "we are all broken. that's how the light gets in.",
            "some birds aren't meant to be caged.",
            "the darkest nights produce the brightest stars.",
        ]

        embed = discord.Embed(
            description=f'*"{random.choice(quotes)}"*',
            color=0x1a1a2e
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roast", description="Get a friendly dark roast")
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user

        roasts = [
            f"{target.mention} you're the human equivalent of a loading screen.",
            f"{target.mention} i've seen error messages with more personality.",
            f"{target.mention} you exist. that's enough. for now.",
            f"{target.mention} if mediocrity was a sport you'd still manage to lose.",
            f"{target.mention} you're not the worst person here. you're just trying your best. almost sad.",
            f"{target.mention} even the void has standards.",
            f"{target.mention} your vibe is 'wifi password written wrong'.",
            f"{target.mention} i'd say you're one of a kind but i've seen your type before.",
        ]

        embed = discord.Embed(
            description=random.choice(roasts),
            color=0x1a1a2e
        )
        embed.set_footer(text="don't take it personally. or do.")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AIChat(bot))