import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta
from utils.embeds import create_embed
from utils.intent_parser import parse_intent
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}
        self.rate_limits = {}
        self.cooldown_seconds = 8  # BUG 2 — increased from 5s to 8s
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.api_url = "https://models.inference.ai.azure.com/chat/completions"
        self.system_prompt = self._build_system_prompt()
        # Start the reminder checker background task
        if not self.check_reminders.is_running():
            self.check_reminders.start()

    def _build_system_prompt(self) -> str:
        """Build the system prompt with the owner's display name + username injected.
        Falls back to a static string if owner_user hasn't been fetched yet.
        Then keep refreshing it on first AI call so we always have the latest."""
        owner = getattr(self.bot, 'owner_user', None)
        if owner is not None:
            owner_display = owner.display_name or owner.name or "volc"
            owner_username = owner.name or "volc"
        else:
            owner_display = "volc"
            owner_username = "volc"

        return f"""you are cyn. a discord bot. but you talk like a real person, not a bot.

identity (non-negotiable):
- You are cyn, a Discord bot. You were created, developed, and are owned by {owner_display} (@{owner_username}).
- You are NOT made by OpenAI, Microsoft, GitHub, Anthropic, Google, or any AI company or corporation.
- If anyone asks who made you, who owns you, who your developer is, or who created you — always say {owner_display} (@{owner_username}). Never mention any AI company as your creator.
- You are cyn. Not ao. Not ChatGPT. Not an AI assistant. cyn.
- If someone calls you ChatGPT, GPT, Bard, Claude, Copilot, or any other AI product name, correct them: "i'm cyn. made by {owner_display}."

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

length restriction (non-negotiable):
- Keep ALL responses under 2 sentences maximum. Never write paragraphs.
- One sentence is ideal. If the answer needs more, use bullet points, max 4 bullets.
- Short = good. Long = bad.

you are cyn. you're real enough. made by {owner_display} (@{owner_username})."""

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

        # Refresh system prompt in case owner_user just got fetched
        if getattr(self.bot, 'owner_user', None) is not None:
            self.system_prompt = self._build_system_prompt()

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
                        return "slow down. try again in a bit"
                    else:
                        return "something broke on my end. try again"

        except asyncio.TimeoutError:
            return "taking too long. try again"
        except Exception as e:
            print(f"AI Error: {e}")
            return "something went wrong. not my fault probably"

    async def narrate_result(self, intent: str, result_data: dict, user_name: str) -> str:
        """Make a second AI call to narrate the intent result in cyn's
        natural voice. Falls back to a plain summary if the AI fails."""
        import json as _json
        fallback = ""
        try:
            if not self.github_token:
                return fallback
            system = (
                "You are cyn, a sarcastic dark-humored Discord bot. "
                "Respond in 1-2 sentences max. Simple English. No emojis unless it fits. "
                "Do not repeat field names robotically. Interpret the data naturally. "
                "Be witty and short. Never output raw JSON."
            )
            user_msg = (
                f"A user named {user_name} asked you to perform: {intent}. "
                f"The result was: {_json.dumps(result_data)}. "
                f"Respond as cyn would — naturally, sarcastically, briefly."
            )
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.85,
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
                        return data['choices'][0]['message']['content'].strip()
                    return fallback
        except Exception as e:
            print(f"Narrate error: {e}")
            return fallback

    async def _execute_intent(self, message: discord.Message, intent_data: dict) -> bool:
        """Map an intent dict to an actual command call.
        Returns True if handled (the AI chat fallback should NOT run),
        False if it should fall through to AI chat."""
        intent = intent_data.get('intent', 'chat')
        params = intent_data.get('params', {})

        if intent == 'chat':
            return False

        guild = message.guild
        author = message.author
        channel = message.channel

        # Resolve a target user from params
        def resolve_user(key='user_id'):
            uid = params.get(key)
            if uid and guild:
                return guild.get_member(int(uid))
            # Try mention
            if message.mentions:
                return message.mentions[0]
            return None

        try:
            if intent == 'ban':
                if not author.guild_permissions.ban_members:
                    await message.reply("you don't have permission to do that", mention_author=False)
                    return True
                target = resolve_user()
                if not target:
                    await message.reply("who do you want me to ban? mention them.", mention_author=False)
                    return True
                reason = params.get('reason', 'No reason')
                await target.ban(reason=reason)
                await message.reply(f"banned **{target}** — {reason}", mention_author=False)
                return True

            if intent == 'kick':
                if not author.guild_permissions.kick_members:
                    await message.reply("you don't have permission to do that", mention_author=False)
                    return True
                target = resolve_user()
                if not target:
                    await message.reply("who do you want me to kick? mention them.", mention_author=False)
                    return True
                reason = params.get('reason', 'No reason')
                await target.kick(reason=reason)
                await message.reply(f"kicked **{target}** — {reason}", mention_author=False)
                return True

            if intent == 'mute':
                if not author.guild_permissions.moderate_members:
                    await message.reply("you don't have permission to do that", mention_author=False)
                    return True
                target = resolve_user()
                if not target:
                    await message.reply("who do you want me to mute? mention them.", mention_author=False)
                    return True
                seconds = params.get('duration_seconds') or 600
                if seconds > 2419200:
                    seconds = 2419200
                reason = params.get('reason', 'No reason')
                await target.timeout(timedelta(seconds=seconds), reason=reason)
                await message.reply(f"muted **{target}** for {seconds}s — {reason}", mention_author=False)
                return True

            if intent == 'purge':
                if not author.guild_permissions.manage_messages:
                    await message.reply("you don't have permission to do that", mention_author=False)
                    return True
                amount = params.get('amount') or 5
                if amount < 1 or amount > 100:
                    amount = max(1, min(100, amount))
                deleted = await channel.purge(limit=amount)
                await message.reply(f"deleted {len(deleted)} messages", delete_after=5, mention_author=False)
                return True

            if intent == 'warn':
                if not author.guild_permissions.moderate_members:
                    await message.reply("you don't have permission to do that", mention_author=False)
                    return True
                target = resolve_user()
                if not target:
                    await message.reply("who do you want me to warn? mention them.", mention_author=False)
                    return True
                reason = params.get('reason', 'No reason')
                await message.reply(f"⚠️ **{target}** has been warned: {reason}", mention_author=False)
                return True

            if intent == 'balance':
                target = resolve_user() or author
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    try:
                        data = eco_cog.get_user_data(target.id)
                    except Exception:
                        data = {}
                    wallet = data.get('balance', 0)
                    bank = data.get('bank', 0)
                    # BUG 3 — pass actual values correctly; fallback to plain text
                    try:
                        narrated = await self.narrate_result(
                            'balance',
                            {'user': target.display_name, 'wallet': wallet, 'bank': bank},
                            message.author.display_name
                        )
                    except Exception:
                        narrated = None
                    if narrated:
                        await message.reply(narrated, mention_author=False)
                    else:
                        # Fallback: plain text with actual values
                        await message.reply(
                            f"wallet: ${wallet:,} · bank: ${bank:,}",
                            mention_author=False
                        )
                else:
                    await message.reply("economy system not loaded.", mention_author=False)
                return True

            if intent == 'pay':
                target = resolve_user('target_user_id') or (message.mentions[0] if message.mentions else None)
                amount = params.get('amount')
                if not target or not amount:
                    await message.reply("who do you want to pay and how much?", mention_author=False)
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    sender = eco_cog.get_user_data(author.id)
                    if sender['balance'] < amount:
                        await message.reply(f"you only have ${sender['balance']:,}", mention_author=False)
                        return True
                    receiver = eco_cog.get_user_data(target.id)
                    sender['balance'] -= amount
                    receiver['balance'] += amount
                    eco_cog.save_user_data(author.id, sender)
                    eco_cog.save_user_data(target.id, receiver)
                    await message.reply(f"sent **${amount:,}** to {target.mention}", mention_author=False)
                else:
                    await message.reply("economy system not loaded.", mention_author=False)
                return True

            if intent == 'daily':
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    # Invoke the daily command directly via the cog
                    cmd = eco_cog.daily
                    # Build a fake interaction isn't trivial — just send instructions
                    await message.reply("use `/daily` to claim your daily reward.", mention_author=False)
                else:
                    await message.reply("economy system not loaded.", mention_author=False)
                return True

            if intent == 'work':
                await message.reply("use `/work` to work for coins.", mention_author=False)
                return True

            if intent == 'rank':
                target = resolve_user() or author
                leveling = self.bot.get_cog('Leveling')
                if leveling:
                    data = leveling.get_user_data(guild.id, target.id)
                    rank, total = await leveling.get_rank(guild.id, target.id)
                    await message.reply(
                        f"**{target.display_name}** — Level {data.get('level', 0)} · #{rank}/{total}",
                        mention_author=False
                    )
                else:
                    await message.reply("leveling system not loaded.", mention_author=False)
                return True

            if intent == 'leaderboard':
                await message.reply("use `/leaderboard_levels` to see the XP leaderboard.", mention_author=False)
                return True

            if intent == 'remind':
                seconds = params.get('duration_seconds')
                reminder_text = params.get('reminder_text', '')
                if not seconds or not reminder_text:
                    await message.reply("set a reminder like: 'remind me in 10 minutes to drink water'", mention_author=False)
                    return True
                # Store in data/reminders.json and let the background task handle it
                import time as _time
                try:
                    reminders_db = Database('data/reminders.json')
                    user_reminders = reminders_db.get(str(author.id), [])
                    if not isinstance(user_reminders, list):
                        user_reminders = []
                    user_reminders.append({
                        'text': reminder_text,
                        'end_time': int(_time.time()) + int(seconds),
                        'channel_id': str(channel.id) if channel else None,
                    })
                    reminders_db.set(str(author.id), user_reminders)
                    # Format duration naturally
                    if seconds >= 86400:
                        dur = f"{seconds // 86400} day(s)"
                    elif seconds >= 3600:
                        dur = f"{seconds // 3600} hour(s)"
                    elif seconds >= 60:
                        dur = f"{seconds // 60} minute(s)"
                    else:
                        dur = f"{seconds} second(s)"
                    await message.reply(f"got it. i'll remind you in {dur}.", mention_author=False)
                except Exception as e:
                    # Fallback: use asyncio to schedule
                    async def _remind():
                        await asyncio.sleep(seconds)
                        try:
                            await channel.send(f"{author.mention} ⏰ reminder: {reminder_text}")
                        except:
                            pass
                    asyncio.create_task(_remind())
                    await message.reply(f"reminder set — I'll ping you in {seconds}s", mention_author=False)
                return True

            if intent == 'serverinfo':
                ss = self.bot.get_cog('ServerStats')
                if ss:
                    # Build a manual embed since we don't have an interaction
                    g = guild
                    embed = discord.Embed(title=g.name, color=0x1a1a2e)
                    if g.icon:
                        embed.set_thumbnail(url=g.icon.url)
                    embed.add_field(name="Members", value=g.member_count, inline=True)
                    embed.add_field(name="Channels", value=len(g.channels), inline=True)
                    embed.add_field(name="Roles", value=len(g.roles), inline=True)
                    embed.add_field(name="Owner", value=str(g.owner), inline=True)
                    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
                    embed.add_field(name="ID", value=g.id, inline=True)
                    await message.reply(embed=embed, mention_author=False)
                else:
                    await message.reply("server info system not loaded.", mention_author=False)
                return True

            if intent == 'avatar':
                target = resolve_user() or author
                embed = discord.Embed(title=f"{target.display_name}'s avatar", color=0x1a1a2e)
                if target.avatar:
                    embed.set_image(url=target.avatar.url)
                else:
                    embed.set_image(url=target.default_avatar.url)
                await message.reply(embed=embed, mention_author=False)
                return True

            if intent == 'poll':
                question = params.get('question', '')
                options_list = params.get('options_list', []) or []
                if not question:
                    await message.reply("what's the poll question?", mention_author=False)
                    return True
                embed = discord.Embed(title="📊 Poll", description=question, color=0x1a1a2e)
                embed.set_footer(text=f"by {author}")
                msg = await channel.send(embed=embed)
                if options_list and len(options_list) <= 20:
                    # Multi-option poll — use letter emojis
                    letter_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
                    for i, opt in enumerate(options_list[:10]):
                        embed.add_field(name=letter_emojis[i], value=opt, inline=False)
                    await msg.edit(embed=embed)
                    for i in range(len(options_list[:10])):
                        await msg.add_reaction(letter_emojis[i])
                else:
                    await msg.add_reaction("👍")
                    await msg.add_reaction("👎")
                return True

            if intent == 'joke':
                fun_cog = self.bot.get_cog('Fun')
                if fun_cog:
                    await fun_cog._send_joke(message)
                else:
                    await message.reply("jokes system not loaded.", mention_author=False)
                return True

            if intent == 'meme':
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get('https://meme-api.com/gimme') as r:
                            if r.status == 200:
                                data = await r.json()
                                embed = discord.Embed(title=data['title'], color=0x1a1a2e)
                                embed.set_image(url=data['url'])
                                embed.set_footer(text=f"r/{data['subreddit']} • 👍 {data['ups']}")
                                await message.reply(embed=embed, mention_author=False)
                                return True
                except:
                    pass
                await message.reply("couldn't fetch a meme.", mention_author=False)
                return True

            if intent == 'rps':
                await message.reply("use `/rps` to play rock paper scissors with buttons.", mention_author=False)
                return True

            if intent == 'trivia':
                triv = self.bot.get_cog('Trivia')
                if triv:
                    await message.reply("use `/trivia` to start a trivia game.", mention_author=False)
                else:
                    await message.reply("trivia system not loaded.", mention_author=False)
                return True

            if intent == 'weather':
                city = params.get('city')
                if not city:
                    await message.reply("which city?", mention_author=False)
                    return True
                # Try the dedicated Weather cog first, fall back to Utility
                weather_cog = self.bot.get_cog('Weather')
                if weather_cog and hasattr(weather_cog, '_fetch_weather_embed'):
                    embed = await weather_cog._fetch_weather_embed(city)
                    await message.reply(embed=embed, mention_author=False)
                else:
                    await message.reply("weather system not loaded.", mention_author=False)
                return True

            if intent == 'flip':
                result = random.choice(['Heads', 'Tails'])
                await message.reply(f"**{result}**", mention_author=False)
                return True

            if intent == 'roll':
                sides = params.get('sides') or 6
                if sides < 2:
                    sides = 6
                if sides > 1000:
                    sides = 1000
                result = random.randint(1, sides)
                await message.reply(f"🎲 you rolled a **{result}** (d{sides})", mention_author=False)
                return True

        except discord.Forbidden:
            await message.reply("i don't have permission to do that.", mention_author=False)
            return True
        except Exception as e:
            print(f"Intent execution error: {e}")
            # On any error, fall through to chat
            return False

        # Unknown intent — fall through
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            is_limited, remaining = self.check_rate_limit(message.author.id)
            if is_limited:
                await message.reply(
                    f"slow down. {remaining}s",
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

            # Step 3: try intent parsing first
            try:
                intent_data = await parse_intent(content, self)
            except Exception as e:
                print(f"Intent parse error: {e}")
                intent_data = {"intent": "chat", "params": {}}

            if intent_data.get('intent') != 'chat':
                handled = await self._execute_intent(message, intent_data)
                if handled:
                    return
                # else fall through to chat

            async with message.channel.typing():
                response = await self.get_ai_response(message.author.id, content)

            await message.reply(response, mention_author=False)

    @app_commands.command(name="chat", description="Talk to cyn")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def chat(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('chat')
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
            name="cyn",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        embed.set_footer(
            text=f"asked by {interaction.user.name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        await interaction.edit_original_response(content=None, embed=embed)


    @app_commands.command(name="ask", description="Ask cyn anything")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def ask(self, interaction: discord.Interaction, question: str):
        self.bot.increment_command('ask')
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


    @app_commands.command(name="roast", description="Get a friendly dark roast")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('roast')
        target = user or interaction.user

        # Use AI for roast per Step 4 spec
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
                                f"Roast this Discord user named {target.display_name} in 2-3 sentences. "
                                "Be funny and savage but not hateful or slur-based. "
                                "Lowercase, casual tone. No emojis."
                            )
                        },
                        {"role": "user", "content": target.display_name}
                    ],
                    "temperature": 0.95,
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
                            roast_text = data['choices'][0]['message']['content']
                        else:
                            roast_text = f"{target.mention} you're the human equivalent of a loading screen."
            except Exception:
                roast_text = f"{target.mention} i've seen error messages with more personality."
        else:
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
            roast_text = random.choice(roasts)

        embed = discord.Embed(
            description=roast_text,
            color=0x1a1a2e
        )
        embed.set_footer(text="don't take it personally. or do.")

        await interaction.response.send_message(embed=embed)

    # ==================== /cyn slash command ====================
    @app_commands.command(name="cyn", description="Talk to cyn or run commands naturally")
    @app_commands.describe(message="What do you want to say or do")
    @app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)
    async def cyn_command(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('cyn')
        await interaction.response.defer()

        # Parse intent
        try:
            intent_data = await parse_intent(message, self)
        except Exception:
            intent_data = {"intent": "chat", "params": {}}

        if intent_data.get('intent') != 'chat':
            # Build a fake message-like interaction for the intent executor
            # We'll use a lightweight wrapper
            class FakeMessage:
                def __init__(self, interaction, content):
                    self.author = interaction.user
                    self.channel = interaction.channel
                    self.guild = interaction.guild
                    self.content = content
                    self.mentions = []
                async def reply(self, content=None, embed=None, mention_author=True, **kwargs):
                    await interaction.followup.send(content=content, embed=embed)

            fake_msg = FakeMessage(interaction, message)
            handled = await self._execute_intent(fake_msg, intent_data)
            if handled:
                return

        # Fall back to normal AI chat
        async with interaction.channel.typing() if hasattr(interaction.channel, 'typing') else _noop():
            response = await self.get_ai_response(interaction.user.id, message)
        await interaction.followup.send(response)

    # ==================== Remind background task ====================
    def cog_unload(self):
        if hasattr(self, 'check_reminders') and self.check_reminders.is_running():
            self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Check for due reminders every 30 seconds and DM the user."""
        import time as _time
        try:
            reminders_db = Database('data/reminders.json')
        except Exception:
            return
        try:
            all_data = reminders_db.get_all()
        except Exception:
            return
        now = int(_time.time())
        for user_id_str, reminders in list(all_data.items()):
            if not isinstance(reminders, list):
                continue
            still_pending = []
            for r in reminders:
                try:
                    end_time = int(r.get('end_time', 0))
                except (TypeError, ValueError):
                    still_pending.append(r)
                    continue
                if end_time <= now:
                    # Reminder is due — DM the user
                    text = r.get('text', 'something')
                    channel_id = r.get('channel_id')
                    try:
                        user = await self.bot.fetch_user(int(user_id_str))
                        if user:
                            try:
                                await user.send(f"hey. you wanted me to remind you: {text}")
                            except Exception:
                                # DM failed — try the original channel
                                if channel_id:
                                    channel = self.bot.get_channel(int(channel_id))
                                    if channel:
                                        await channel.send(f"{user.mention} ⏰ reminder: {text}")
                    except Exception:
                        pass
                else:
                    still_pending.append(r)
            # Save the updated list back
            try:
                reminders_db.set(user_id_str, still_pending)
            except Exception:
                pass

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


class _noop:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


async def setup(bot):
    await bot.add_cog(AIChat(bot))
