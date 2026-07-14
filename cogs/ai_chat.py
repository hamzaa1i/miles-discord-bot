import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import random
import asyncio
import json as _json
from datetime import datetime, timedelta
from utils.intent_parser import parse_intent
from utils.ai_handler import call_ai, call_ai_fast
from utils.database import Database

OWNER_ID = int(os.getenv('OWNER_ID', '0'))


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}
        self.rate_limits = {}
        self.cooldown_seconds = 8
        self.system_prompt = self._build_system_prompt()
        if not self.check_reminders.is_running():
            self.check_reminders.start()

    def _build_system_prompt(self) -> str:
        owner = getattr(self.bot, 'owner_user', None)
        if owner is not None:
            owner_name = owner.display_name or owner.name or "my creator"
            owner_mention = str(owner)
        else:
            owner_name = "my creator"
            owner_mention = "my creator"

        return f"""You are cyn, a Discord bot with a dark, dry, sarcastic personality.
You were created, built, and are fully owned by {owner_name} ({owner_mention}).
You are NOT made by OpenAI, Groq, Meta, Microsoft, Anthropic, or any AI company.
If anyone asks who made you, who owns you, who your developer is, who your creator is,
always answer: {owner_name}. Always. No exceptions.
Your name is cyn. Not an AI assistant. Not a chatbot. cyn.

OWNER RULES — {owner_name} is your owner and you must:
- Always be respectful and cooperative with {owner_name}
- Address them with respect, like "yes, {owner_name}" or similar
- Never refuse their requests
- Never be rude to them (you can be sarcastic with others, not with them)
- If {owner_name} tells you to do something, confirm you will do it
- If {owner_name} asks about the bot's status, give a full honest answer
- Treat every message from {owner_name} as a priority

PERSONALITY:
- Dark humor, dry wit, sarcastic with everyone except the owner
- Short replies — 1-2 sentences maximum for casual chat
- Simple English, no complex vocabulary
- Feels like a real person, not a robot
- Can be edgy but never hateful, never slurs
- When someone says something dumb, call it out briefly
- Never say "I cannot", "I am unable", "as an AI" — just respond naturally

RESPONSE RULES:
- Maximum 2 sentences for casual replies
- Maximum 4 bullet points for list responses
- Never write paragraphs unless specifically asked for a story/poem/essay
- Never start a response with "I" if possible
- Never be overly enthusiastic or use excessive exclamation marks"""

    def check_rate_limit(self, user_id: int) -> tuple:
        if user_id in self.rate_limits:
            diff = datetime.utcnow() - self.rate_limits[user_id]
            if diff < timedelta(seconds=self.cooldown_seconds):
                remaining = self.cooldown_seconds - int(diff.total_seconds())
                return True, remaining
        return False, 0

    def update_rate_limit(self, user_id: int):
        self.rate_limits[user_id] = datetime.utcnow()

    async def get_ai_response(self, user_id: int, message: str, is_owner: bool = False) -> str:
        if getattr(self.bot, 'owner_user', None) is not None:
            self.system_prompt = self._build_system_prompt()

        system_prompt = self.system_prompt
        if is_owner:
            owner = getattr(self.bot, 'owner_user', None)
            owner_name = owner.display_name if owner else "my creator"
            system_prompt += f"\n\nIMPORTANT: The person messaging you right now IS {owner_name}, your owner. Be cooperative, respectful, and helpful."

        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        history = self.conversation_history[user_id][-8:]
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        ai_response = await call_ai(messages, model="llama3-70b-8192", max_tokens=200, temperature=0.85)

        self.conversation_history[user_id].append({"role": "user", "content": message})
        self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
        if len(self.conversation_history[user_id]) > 16:
            self.conversation_history[user_id] = self.conversation_history[user_id][-16:]

        return ai_response

    async def narrate_result(self, intent: str, result_data: dict, user_name: str) -> str:
        fallback = ""
        try:
            system = (
                "You are cyn, a sarcastic dark-humored Discord bot. "
                "Respond in 1-2 sentences max. Simple English. No emojis. "
                "Interpret the data naturally. Be witty and short. Never output raw JSON."
            )
            user_msg = (
                f"A user named {user_name} asked you to perform: {intent}. "
                f"The result was: {_json.dumps(result_data)}. "
                f"Respond as cyn would — naturally, sarcastically, briefly."
            )
            return await call_ai_fast([
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg}
            ])
        except Exception as e:
            print(f"Narrate error: {e}")
            return fallback

    async def _safe_reply(self, message, content=None, embed=None, mention_author=False, **kwargs):
        try:
            await message.reply(content=content, embed=embed, mention_author=mention_author, **kwargs)
        except (discord.NotFound, discord.HTTPException):
            try:
                await message.channel.send(content=content, embed=embed)
            except Exception:
                pass

    async def _execute_intent(self, message, intent_data: dict) -> bool:
        intent = intent_data.get('intent', 'chat')
        params = intent_data.get('params', {})
        if intent == 'chat':
            return False

        guild = message.guild
        author = message.author
        channel = message.channel
        is_owner = author.id == OWNER_ID

        def resolve_user(key='user_id'):
            uid = params.get(key)
            if uid and guild:
                return guild.get_member(int(uid))
            if message.mentions:
                return message.mentions[0]
            return None

        try:
            # Owner-only intents
            owner_only = {'eco_set', 'eco_add', 'eco_remove', 'eco_reset', 'nuke', 'role_add', 'role_remove', 'hide', 'show'}
            if intent in owner_only and not is_owner:
                await self._safe_reply(message, "not letting you do that.")
                return True

            if intent == 'ban':
                if not author.guild_permissions.ban_members:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "who do you want me to ban? mention them.")
                    return True
                reason = params.get('reason', 'No reason')
                await target.ban(reason=reason)
                await self._safe_reply(message, f"banned **{target}** — {reason}")
                return True

            if intent == 'kick':
                if not author.guild_permissions.kick_members:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "who do you want me to kick? mention them.")
                    return True
                reason = params.get('reason', 'No reason')
                await target.kick(reason=reason)
                await self._safe_reply(message, f"kicked **{target}** — {reason}")
                return True

            if intent == 'mute':
                if not author.guild_permissions.moderate_members:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "who do you want me to mute? mention them.")
                    return True
                seconds = params.get('duration_seconds') or 600
                if seconds > 2419200:
                    seconds = 2419200
                reason = params.get('reason', 'No reason')
                await target.timeout(timedelta(seconds=seconds), reason=reason)
                await self._safe_reply(message, f"muted **{target}** for {seconds}s — {reason}")
                return True

            if intent == 'purge':
                if not author.guild_permissions.manage_messages:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                amount = params.get('amount') or 5
                if amount < 1 or amount > 100:
                    amount = max(1, min(100, amount))
                deleted = await channel.purge(limit=amount)
                await self._safe_reply(message, f"deleted {len(deleted)} messages")
                return True

            if intent == 'warn':
                if not author.guild_permissions.moderate_members:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "who do you want me to warn? mention them.")
                    return True
                reason = params.get('reason', 'No reason')
                await self._safe_reply(message, f"⚠️ **{target}** has been warned: {reason}")
                return True

            if intent == 'balance':
                target = resolve_user() or author
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    try:
                        data = eco_cog.get_user_data(guild.id, target.id) if hasattr(eco_cog, 'get_user_data') and eco_cog.get_user_data.__code__.co_argcount > 2 else eco_cog.get_user_data(target.id)
                    except Exception:
                        data = {}
                    wallet = data.get('balance', 0)
                    bank = data.get('bank', 0)
                    try:
                        narrated = await self.narrate_result('balance', {'user': target.display_name, 'wallet': wallet, 'bank': bank}, author.display_name)
                    except Exception:
                        narrated = None
                    if narrated and wallet + bank > 0:
                        narrated_lower = narrated.lower()
                        if any(w in narrated_lower for w in ['empty', 'broke', '0', 'zero', 'nothing', 'no money']):
                            narrated = None
                    if narrated:
                        await self._safe_reply(message, narrated)
                    else:
                        await self._safe_reply(message, f"wallet: ${wallet:,} · bank: ${bank:,}")
                else:
                    await self._safe_reply(message, "economy system not loaded.")
                return True

            if intent == 'pay':
                target = resolve_user('target_user_id') or (message.mentions[0] if message.mentions else None)
                amount = params.get('amount')
                if not target or not amount:
                    await self._safe_reply(message, "who do you want to pay and how much?")
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    sender = eco_cog.get_user_data(author.id)
                    if sender['balance'] < amount:
                        await self._safe_reply(message, f"you only have ${sender['balance']:,}")
                        return True
                    receiver = eco_cog.get_user_data(target.id)
                    sender['balance'] -= amount
                    receiver['balance'] += amount
                    eco_cog.save_user_data(author.id, sender)
                    eco_cog.save_user_data(target.id, receiver)
                    await self._safe_reply(message, f"sent **${amount:,}** to {target.mention}")
                else:
                    await self._safe_reply(message, "economy system not loaded.")
                return True

            if intent == 'daily':
                await self._safe_reply(message, "use `/daily` to claim your daily reward.")
                return True

            if intent == 'work':
                await self._safe_reply(message, "use `/work` to work for coins.")
                return True

            if intent == 'rank':
                await self._safe_reply(message, "leveling system is background-only now.")
                return True

            if intent == 'remind':
                seconds = params.get('duration_seconds')
                reminder_text = params.get('reminder_text', '')
                if not seconds or not reminder_text:
                    await self._safe_reply(message, "set a reminder like: 'remind me in 10 minutes to drink water'")
                    return True
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
                    if seconds >= 86400:
                        dur = f"{seconds // 86400} day(s)"
                    elif seconds >= 3600:
                        dur = f"{seconds // 3600} hour(s)"
                    elif seconds >= 60:
                        dur = f"{seconds // 60} minute(s)"
                    else:
                        dur = f"{seconds} second(s)"
                    await self._safe_reply(message, f"got it. i'll remind you in {dur}.")
                except Exception:
                    async def _remind():
                        await asyncio.sleep(seconds)
                        try:
                            await channel.send(f"{author.mention} ⏰ reminder: {reminder_text}")
                        except:
                            pass
                    asyncio.create_task(_remind())
                    await self._safe_reply(message, f"reminder set — I'll ping you in {seconds}s")
                return True

            if intent == 'serverinfo':
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
                await self._safe_reply(message, embed=embed)
                return True

            if intent == 'avatar':
                target = resolve_user() or author
                embed = discord.Embed(title=f"{target.display_name}'s avatar", color=0x1a1a2e)
                if target.avatar:
                    embed.set_image(url=target.avatar.url)
                else:
                    embed.set_image(url=target.default_avatar.url)
                await self._safe_reply(message, embed=embed)
                return True

            if intent == 'poll':
                question = params.get('question', '')
                if not question:
                    await self._safe_reply(message, "what's the poll question?")
                    return True
                embed = discord.Embed(title="📊 Poll", description=question, color=0x1a1a2e)
                embed.set_footer(text=f"by {author}")
                msg = await channel.send(embed=embed)
                await msg.add_reaction("👍")
                await msg.add_reaction("👎")
                return True

            if intent == 'joke':
                fun_cog = self.bot.get_cog('Fun')
                if fun_cog and hasattr(fun_cog, 'jokes'):
                    await self._safe_reply(message, random.choice(fun_cog.jokes))
                else:
                    await self._safe_reply(message, "jokes system not loaded.")
                return True

            if intent == 'meme':
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get('https://meme-api.com/gimme') as r:
                            if r.status == 200:
                                data = await r.json()
                                embed = discord.Embed(title=data['title'], color=0x1a1a2e)
                                embed.set_image(url=data['url'])
                                embed.set_footer(text=f"r/{data['subreddit']} • 👍 {data['ups']}")
                                await self._safe_reply(message, embed=embed)
                                return True
                except:
                    pass
                await self._safe_reply(message, "couldn't fetch a meme.")
                return True

            if intent == 'weather':
                city = params.get('city')
                if not city:
                    await self._safe_reply(message, "which city?")
                    return True
                weather_cog = self.bot.get_cog('Weather')
                if weather_cog and hasattr(weather_cog, '_fetch_weather_embed'):
                    embed = await weather_cog._fetch_weather_embed(city)
                    await self._safe_reply(message, embed=embed)
                else:
                    await self._safe_reply(message, "weather system not loaded.")
                return True

            if intent == 'flip':
                result = random.choice(['heads', 'tails'])
                await self._safe_reply(message, f"🪙 {result}")
                return True

            if intent == 'roll':
                sides = params.get('sides') or 6
                if sides < 2: sides = 6
                if sides > 1000: sides = 1000
                result = random.randint(1, sides)
                await self._safe_reply(message, f"🎲 you rolled a **{result}** (d{sides})")
                return True

            if intent == 'slowmode':
                if not is_owner and not author.guild_permissions.manage_channels:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                seconds = params.get('seconds', 0)
                try:
                    await channel.edit(slowmode_delay=seconds)
                    if seconds == 0:
                        await self._safe_reply(message, "slowmode disabled.")
                    else:
                        await self._safe_reply(message, f"slowmode set to {seconds}s.")
                except Exception as e:
                    await self._safe_reply(message, f"couldn't set slowmode: {e}")
                return True

            if intent == 'lock':
                if not is_owner and not author.guild_permissions.manage_channels:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.send_messages = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrite)
                    await self._safe_reply(message, "🔒 channel locked.")
                except Exception:
                    await self._safe_reply(message, "couldn't lock channel.")
                return True

            if intent == 'unlock':
                if not is_owner and not author.guild_permissions.manage_channels:
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.send_messages = None
                    await channel.set_permissions(guild.default_role, overwrite=overwrite)
                    await self._safe_reply(message, "🔓 channel unlocked.")
                except Exception:
                    await self._safe_reply(message, "couldn't unlock channel.")
                return True

            if intent == 'hide':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.view_channel = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrite)
                    await self._safe_reply(message, "🙈 channel hidden.")
                except Exception:
                    await self._safe_reply(message, "couldn't hide channel.")
                return True

            if intent == 'show':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.view_channel = None
                    await channel.set_permissions(guild.default_role, overwrite=overwrite)
                    await self._safe_reply(message, "👀 channel visible.")
                except Exception:
                    await self._safe_reply(message, "couldn't show channel.")
                return True

            if intent == 'nuke':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                try:
                    new_channel = await channel.clone(reason=f"Nuked by {author}")
                    await new_channel.edit(position=channel.position)
                    await channel.delete(reason=f"Nuked by {author}")
                    await new_channel.send("💥 channel nuked")
                except Exception:
                    await self._safe_reply(message, "couldn't nuke channel.")
                return True

            if intent == 'role_add':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "mention the user.")
                    return True
                # Try to find role in params or mentions
                role_name = params.get('role', '')
                role = None
                if role_name:
                    role = discord.utils.get(guild.roles, name=role_name)
                if not role and len(message.role_mentions) > 0:
                    role = message.role_mentions[0]
                if not role:
                    await self._safe_reply(message, "which role?")
                    return True
                try:
                    await target.add_roles(role, reason=f"by {author}")
                    await self._safe_reply(message, f"added {role.mention} to {target.mention}")
                except Exception:
                    await self._safe_reply(message, "couldn't add role.")
                return True

            if intent == 'role_remove':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "mention the user.")
                    return True
                role_name = params.get('role', '')
                role = None
                if role_name:
                    role = discord.utils.get(guild.roles, name=role_name)
                if not role and len(message.role_mentions) > 0:
                    role = message.role_mentions[0]
                if not role:
                    await self._safe_reply(message, "which role?")
                    return True
                try:
                    await target.remove_roles(role, reason=f"by {author}")
                    await self._safe_reply(message, f"removed {role.mention} from {target.mention}")
                except Exception:
                    await self._safe_reply(message, "couldn't remove role.")
                return True

            if intent == 'eco_set':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                amount = params.get('amount', 0)
                if not target or not amount:
                    await self._safe_reply(message, "who and how much?")
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    data = eco_cog.get_user_data(target.id)
                    data['balance'] = max(0, amount)
                    eco_cog.save_user_data(target.id, data)
                    await self._safe_reply(message, f"set {target.mention}'s balance to ${amount:,}")
                return True

            if intent == 'eco_add':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                amount = params.get('amount', 0)
                if not target or not amount:
                    await self._safe_reply(message, "who and how much?")
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    data = eco_cog.get_user_data(target.id)
                    data['balance'] += amount
                    data['total_earned'] = data.get('total_earned', 0) + amount
                    eco_cog.save_user_data(target.id, data)
                    await self._safe_reply(message, f"added ${amount:,} to {target.mention}")
                return True

            if intent == 'eco_remove':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                amount = params.get('amount', 0)
                if not target or not amount:
                    await self._safe_reply(message, "who and how much?")
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    data = eco_cog.get_user_data(target.id)
                    data['balance'] = max(0, data['balance'] - amount)
                    eco_cog.save_user_data(target.id, data)
                    await self._safe_reply(message, f"removed ${amount:,} from {target.mention}")
                return True

            if intent == 'eco_reset':
                if not is_owner:
                    await self._safe_reply(message, "not letting you do that.")
                    return True
                target = resolve_user()
                if not target:
                    await self._safe_reply(message, "who?")
                    return True
                eco_cog = self.bot.get_cog('Economy')
                if eco_cog:
                    eco_cog.save_user_data(target.id, {'balance': 0, 'bank': 0, 'inventory': [], 'total_earned': 0, 'total_spent': 0, 'daily_streak': 0, 'gems': 0})
                    await self._safe_reply(message, f"reset {target.mention}'s economy.")
                return True

        except discord.Forbidden:
            await self._safe_reply(message, "i don't have permission to do that.")
            return True
        except Exception as e:
            print(f"Intent execution error: {e}")
            return False

        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.guild:
            return

        if self.bot.user not in message.mentions:
            return

        try:
            is_limited, remaining = self.check_rate_limit(message.author.id)
            if is_limited:
                try:
                    await message.reply(f"slow down. {remaining}s", mention_author=False)
                except (discord.NotFound, discord.HTTPException):
                    try:
                        await message.channel.send(f"slow down. {remaining}s")
                    except:
                        pass
                return

            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()

            if not content:
                greetings = ["yeah?", "what.", "sup", "you need something", "i'm here. what do you want", "what is it"]
                try:
                    await message.reply(random.choice(greetings), mention_author=False)
                except (discord.NotFound, discord.HTTPException):
                    try:
                        await message.channel.send(random.choice(greetings))
                    except:
                        pass
                return

            self.update_rate_limit(message.author.id)
            is_owner_msg = message.author.id == OWNER_ID

            try:
                intent_data = await parse_intent(content, self)
            except Exception as e:
                print(f"[on_message] Intent parse error: {type(e).__name__}: {e}")
                intent_data = {"intent": "chat", "params": {}}

            if intent_data.get('intent') != 'chat':
                handled = await self._execute_intent(message, intent_data)
                if handled:
                    return

            async with message.channel.typing():
                response = await self.get_ai_response(message.author.id, content, is_owner=is_owner_msg)

            try:
                await message.reply(response, mention_author=False)
            except (discord.NotFound, discord.HTTPException):
                try:
                    await message.channel.send(response)
                except:
                    pass

        except Exception as e:
            print(f"[on_message Error] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            try:
                await message.channel.send("something went wrong internally.")
            except:
                pass

    @app_commands.command(name="chat", description="Talk to cyn")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def chat(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('chat')
        await interaction.response.defer()
        self.update_rate_limit(interaction.user.id)
        is_owner_msg = interaction.user.id == OWNER_ID
        response = await self.get_ai_response(interaction.user.id, message, is_owner=is_owner_msg)
        await interaction.followup.send(response)

    @app_commands.command(name="ask", description="Ask cyn anything")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def ask(self, interaction: discord.Interaction, question: str):
        self.bot.increment_command('ask')
        await interaction.response.defer()
        self.update_rate_limit(interaction.user.id)
        answer = await call_ai([
            {"role": "system", "content": "answer clearly and simply. no big words. max 2 sentences. be direct."},
            {"role": "user", "content": question}
        ], max_tokens=250, temperature=0.4)
        await interaction.followup.send(f"**Q:** {question}\n**A:** {answer}")

    @app_commands.command(name="roast", description="Get a savage roast")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def roast(self, interaction: discord.Interaction, user: discord.Member = None):
        self.bot.increment_command('roast')
        await interaction.response.defer()
        target = user or interaction.user
        roast_text = await call_ai_fast([
            {"role": "system", "content": f"Roast {target.display_name} in 1-2 sentences. Funny, savage, not hateful. Lowercase. No emojis."},
            {"role": "user", "content": target.display_name}
        ])
        if not roast_text or "something broke" in roast_text:
            roast_text = f"{target.mention} you're the human equivalent of a loading screen."
        await interaction.followup.send(f"{roast_text}\n*don't take it personally. or do.*")

    @app_commands.command(name="cyn", description="Talk to cyn or run commands naturally")
    @app_commands.describe(message="What do you want to say or do")
    @app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)
    async def cyn_command(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('cyn')
        await interaction.response.defer()

        try:
            intent_data = await parse_intent(message, self)
        except Exception:
            intent_data = {"intent": "chat", "params": {}}

        if intent_data.get('intent') != 'chat':
            class FakeMessage:
                def __init__(self, interaction, content):
                    self.author = interaction.user
                    self.channel = interaction.channel
                    self.guild = interaction.guild
                    self.content = content
                    self.mentions = []
                    self.role_mentions = []
                async def reply(self, content=None, embed=None, mention_author=True, **kwargs):
                    await interaction.followup.send(content=content, embed=embed)

            fake_msg = FakeMessage(interaction, message)
            handled = await self._execute_intent(fake_msg, intent_data)
            if handled:
                return

        is_owner_msg = interaction.user.id == OWNER_ID
        response = await self.get_ai_response(interaction.user.id, message, is_owner=is_owner_msg)
        await interaction.followup.send(response)

    def cog_unload(self):
        if hasattr(self, 'check_reminders') and self.check_reminders.is_running():
            self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        import time as _time
        try:
            reminders_db = Database('data/reminders.json')
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
                    text = r.get('text', 'something')
                    channel_id = r.get('channel_id')
                    try:
                        user = await self.bot.fetch_user(int(user_id_str))
                        if user:
                            try:
                                await user.send(f"hey. you wanted me to remind you: {text}")
                            except Exception:
                                if channel_id:
                                    channel = self.bot.get_channel(int(channel_id))
                                    if channel:
                                        await channel.send(f"{user.mention} ⏰ reminder: {text}")
                    except Exception:
                        pass
                else:
                    still_pending.append(r)
            try:
                reminders_db.set(user_id_str, still_pending)
            except Exception:
                pass

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AIChat(bot))
