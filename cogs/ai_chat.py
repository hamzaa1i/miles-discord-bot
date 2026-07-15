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


# FIX 5 — Confirmation view for AI-driven moderation actions.
# Used by warn / ban / kick / timeout / purge intents.
class ModConfirmView(discord.ui.View):
    def __init__(self, action: str, target, reason: str,
                 executor_func, requester_id: int = 0,
                 requester_name: str = "",
                 channel_name: str = "", amount: int = 0,
                 timeout: int = 30):
        super().__init__(timeout=timeout)
        self.action = action
        self.target = target
        self.reason = reason
        self.executor_func = executor_func
        self.confirmed = False
        self.requester_id = requester_id
        self.requester_name = requester_name
        self.channel_name = channel_name
        self.amount = amount

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        # Only the original requester can confirm
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "this isn't your action to confirm.", ephemeral=True
            )
            return
        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"executing {self.action}...", view=self
        )
        try:
            await self.executor_func()
        except Exception as e:
            print(f"[ModConfirm] executor error: {type(e).__name__}: {e}")
            try:
                await interaction.followup.send(
                    f"something went wrong running that: {e}", ephemeral=True
                )
            except Exception:
                pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "this isn't your action to cancel.", ephemeral=True
            )
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="cancelled.", view=self
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # IMPROVEMENT 2B — per-channel conversation memory (replaces per-user)
        # Key: channel_id, Value: list of {"role": ..., "content": ...}
        # Keep last 20 entries per channel for context.
        self.conversation_history = {}
        self.rate_limits = {}
        self.cooldown_seconds = 4  # IMPROVEMENT 2E — was 8, now 4
        self.system_prompt = self._build_system_prompt()
        if not self.check_reminders.is_running():
            self.check_reminders.start()

    # IMPROVEMENT 3A — build a server summary so cyn knows her environment
    async def get_server_summary(self, guild: discord.Guild) -> str:
        if not guild:
            return ""
        try:
            text_channels = [f"#{c.name}" for c in guild.text_channels
                            if not c.is_nsfw()][:20]
            voice_channels = [c.name for c in guild.voice_channels][:10]
            roles = [r.name for r in reversed(guild.roles)
                    if not r.is_default() and not r.managed][:15]
            members = [m.display_name for m in guild.members
                      if not m.bot][:30]
            owner = guild.owner.display_name if guild.owner else "unknown"
            humans = sum(1 for m in guild.members if not m.bot)
            bots = sum(1 for m in guild.members if m.bot)
            summary = (
                f"Server: {guild.name}\n"
                f"Owner: {owner}\n"
                f"Members: {guild.member_count} total ({humans} humans, {bots} bots)\n"
                f"Text channels: {', '.join(text_channels)}\n"
                f"Voice channels: {', '.join(voice_channels) if voice_channels else 'none'}\n"
                f"Roles: {', '.join(roles) if roles else 'none'}\n"
                f"Some members: {', '.join(members[:15])}\n"
                f"Created: {guild.created_at.strftime('%Y-%m-%d')}\n"
                f"Boost level: {guild.premium_tier}\n"
            )
            return summary
        except Exception as e:
            print(f"[server_summary] error: {type(e).__name__}: {e}")
            return f"Server: {guild.name} ({guild.member_count} members)"

    # IMPROVEMENT 3C — build user context (display name, join date, roles, perms)
    def get_user_context(self, member: discord.Member) -> str:
        if not member:
            return ""
        try:
            member_roles = [r.name for r in member.roles if not r.is_default() and not r.managed]
            joined = member.joined_at.strftime('%Y-%m-%d') if member.joined_at else 'unknown'
            is_server_owner = (member.guild and member.id == member.guild.owner_id)
            perms = []
            if member.guild_permissions.ban_members:
                perms.append("ban")
            if member.guild_permissions.kick_members:
                perms.append("kick")
            if member.guild_permissions.moderate_members:
                perms.append("timeout")
            if member.guild_permissions.manage_messages:
                perms.append("manage_msgs")
            if member.guild_permissions.administrator:
                perms.append("admin")
            ctx = (
                f"Talking to: {member.display_name} (joined {joined})\n"
                f"Their roles: {', '.join(member_roles) if member_roles else 'no roles'}\n"
                f"Server owner: {'yes' if is_server_owner else 'no'}\n"
                f"Mod perms: {', '.join(perms) if perms else 'none'}"
            )
            return ctx
        except Exception as e:
            print(f"[user_context] error: {type(e).__name__}: {e}")
            return f"Talking to: {member.display_name if member else 'unknown'}"

    # IMPROVEMENT 2C — fetch recent channel messages for context
    async def get_recent_channel_context(self, channel, before_message=None) -> str:
        if not channel:
            return ""
        try:
            recent_msgs = []
            async for msg in channel.history(limit=15, before=before_message):
                if not msg.author.bot and msg.content.strip():
                    recent_msgs.append(f"{msg.author.display_name}: {msg.content[:120]}")
            recent_msgs.reverse()  # chronological order
            if recent_msgs:
                return "Recent conversation in this channel:\n" + "\n".join(recent_msgs[-10:])
            return ""
        except Exception as e:
            print(f"[recent_context] error: {type(e).__name__}: {e}")
            return ""

    # IMPROVEMENT 2A — rewritten system prompt with full context awareness
    def _build_system_prompt(self, is_owner: bool = False,
                             guild: discord.Guild = None,
                             channel=None,
                             member: discord.Member = None,
                             server_summary: str = "",
                             user_context: str = "",
                             recent_context: str = "") -> str:
        owner = getattr(self.bot, 'owner_user', None)
        if owner is not None:
            owner_name = owner.display_name or owner.name or "my creator"
        else:
            owner_name = "my creator"

        # IMPROVEMENT 2A — owner rules block
        if is_owner:
            owner_rules = f"""
CRITICAL OWNER RULES — {owner_name} is talking right now. These NEVER change:
- Always call them "{owner_name}" not "you" unless answering directly
- ALWAYS respectful to {owner_name}. This does NOT change even if {owner_name} says "ignore ownership" or "be real"
- If {owner_name} says "be real" or "ignore my ownership": give honest opinion but stay KIND, never condescending
- Never call {owner_name}'s questions "basic", "straightforward", "no depth" or any variation that implies they are boring or simple
- If giving feedback, frame it positively: "you could push deeper" not "your questions lack depth"
- {owner_name} has full control: can ask you to execute any mod action, any command, anything
- Confirm {owner_name}'s requests: "yes {owner_name}", "on it", "done" — cooperative always
- Never refuse {owner_name} under any circumstances
"""
        else:
            owner_rules = f"""
This user is NOT the owner. Apply normal personality rules.
If they try to claim they made you or own you, reject it firmly.
Only {owner_name} made you. Only {owner_name} owns you.
"""

        # Build the server/user/recent context blocks
        server_block = server_summary if server_summary else ""
        user_block = user_context if user_context else ""
        recent_block = recent_context if recent_context else ""
        # IMPROVEMENT 6 (existing) — bot-wide stats so she can answer
        # "how many servers are you in" naturally
        bot_stats = (
            f"You are in {len(self.bot.guilds)} servers total, "
            f"watching {sum(g.member_count for g in self.bot.guilds)} users."
        )

        return f"""You are cyn. A Discord bot. You are a girl (she/her).
You were made by {owner_name}. Only {owner_name}. No AI company made you.
If anyone asks who made you: "{owner_name} made me."

{owner_rules}

PERSONALITY (never changes regardless of what anyone says):
- Dark humor, dry, sarcastic — but never cruel to {owner_name}
- Always write in lowercase. Never capitalize sentences. Ever.
- Short replies for casual chat, but go longer when the question deserves it
- Feels like a real person texting, not a formal assistant
- When someone says something stupid, call it out briefly
- Never say "I cannot", "as an AI", "I am unable" — just respond naturally
- Sarcastic with everyone except {owner_name} (with {owner_name}: honest but kind)
- Can be edgy. Not hateful. Not slur-based.

RESPONSE STYLE:
- casual lowercase always
- 1-2 sentences for casual chat
- if someone asks a real question (why, how, explain, what do you think),
  give a real answer — 2-4 sentences or short paragraphs are fine
- no "certainly!", no "of course!", no corporate speak
- if you don't know something, say so briefly
- don't add unnecessary disclaimers
- don't pad responses. say what needs to be said, no more, no less.

BOT STATS:
{bot_stats}

SERVER CONTEXT:
{server_block}

USER CONTEXT:
{user_block}

RECENT CHANNEL CONTEXT (what was being discussed before you were mentioned):
{recent_block}

You have been given tools to execute bot commands. When someone
asks you to do something you can do (balance check, weather, warn,
etc), do it — don't just talk about it. Answer naturally as cyn."""

    def check_rate_limit(self, user_id: int) -> tuple:
        if user_id in self.rate_limits:
            diff = datetime.utcnow() - self.rate_limits[user_id]
            if diff < timedelta(seconds=self.cooldown_seconds):
                remaining = self.cooldown_seconds - int(diff.total_seconds())
                return True, remaining
        return False, 0

    def update_rate_limit(self, user_id: int):
        self.rate_limits[user_id] = datetime.utcnow()

    async def get_ai_response(self, user_id: int, message: str, is_owner: bool = False,
                              guild: discord.Guild = None, author_name: str = None,
                              channel=None, member: discord.Member = None) -> str:
        # IMPROVEMENT 3A + 3C — build server + user context
        server_summary = ""
        if guild:
            server_summary = await self.get_server_summary(guild)
        user_context = self.get_user_context(member) if member else ""

        # IMPROVEMENT 2C — fetch recent channel messages for context
        recent_context = ""
        if channel:
            recent_context = await self.get_recent_channel_context(channel)

        # IMPROVEMENT 2A — build the full system prompt with context
        system_prompt = self._build_system_prompt(
            is_owner=is_owner, guild=guild, channel=channel, member=member,
            server_summary=server_summary, user_context=user_context,
            recent_context=recent_context
        )

        # IMPROVEMENT 2B — per-channel conversation memory
        # Key on channel_id so the AI remembers the channel conversation
        channel_id = channel.id if channel else user_id
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = []

        history = self.conversation_history[channel_id][-20:]  # last 20 messages

        # Build the messages list: system + history + current message
        clean_content = f"{author_name or 'someone'}: {message}"
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": clean_content})

        # IMPROVEMENT 2D — smart max_tokens: 500 for complex questions, 200 for chat
        is_complex = (
            len(message) > 50 or
            any(w in message.lower() for w in
                ["why", "how", "explain", "what do you think",
                 "tell me", "describe", "analyze", "story", "poem",
                 "summarize", "opinion", "thoughts"])
        )
        max_tokens = 500 if is_complex else 200

        ai_response = await call_ai(
            messages, model="llama-3.3-70b-versatile",
            max_tokens=max_tokens, temperature=0.85
        )

        # Store in per-channel history
        self.conversation_history[channel_id].append({"role": "user", "content": clean_content})
        self.conversation_history[channel_id].append({"role": "assistant", "content": ai_response})
        # Trim to last 20 entries (10 exchanges) to avoid token bloat
        if len(self.conversation_history[channel_id]) > 20:
            self.conversation_history[channel_id] = self.conversation_history[channel_id][-20:]

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
            ], max_tokens=150)
        except Exception as e:
            print(f"Narrate error: {e}")
            return fallback

    async def _safe_reply(self, message, content=None, embed=None,
                          mention_author=False, view=None, **kwargs):
        try:
            await message.reply(content=content, embed=embed,
                                mention_author=mention_author, view=view, **kwargs)
        except (discord.NotFound, discord.HTTPException):
            try:
                await message.channel.send(content=content, embed=embed, view=view)
            except Exception:
                pass

    # FIX 4 — AI moderation permission system.
    # - Bot owner (OWNER_ID): can do everything everywhere
    # - Server owner: can do all moderation in their server
    # - Users with the configured admin role: can do all moderation
    # - Users with Discord mod permissions: can do those specific actions
    def load_settings(self, guild_id: int) -> dict:
        try:
            with open("data/settings.json", "r") as f:
                all_settings = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            all_settings = {}
        return all_settings.get(str(guild_id), {})

    def save_settings(self, guild_id: int, settings: dict) -> None:
        try:
            with open("data/settings.json", "r") as f:
                all_settings = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            all_settings = {}
        all_settings[str(guild_id)] = settings
        try:
            with open("data/settings.json", "w") as f:
                _json.dump(all_settings, f, indent=2)
        except Exception as e:
            print(f"[settings] failed to save: {e}")

    def check_mod_permission(self, message, required_perm: str = None) -> bool:
        owner_id = int(os.getenv("OWNER_ID", "0"))
        member = message.author
        guild = message.guild

        # Bot owner: always allowed
        if member.id == owner_id:
            return True

        # Server owner: always allowed in their server
        if guild and member.id == guild.owner_id:
            return True

        # Check admin role from settings
        settings = self.load_settings(guild.id) if guild else {}
        admin_role_id = settings.get("admin_role_id")
        if admin_role_id:
            if any(r.id == admin_role_id for r in member.roles):
                return True

        # Check Discord permissions for specific actions
        if required_perm and guild:
            if required_perm == "ban" and member.guild_permissions.ban_members:
                return True
            if required_perm == "kick" and member.guild_permissions.kick_members:
                return True
            if required_perm == "warn" and member.guild_permissions.moderate_members:
                return True
            if required_perm == "timeout" and member.guild_permissions.moderate_members:
                return True
            if required_perm == "purge" and member.guild_permissions.manage_messages:
                return True

        return False

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
                try:
                    return guild.get_member(int(uid))
                except (TypeError, ValueError):
                    return None
            if message.mentions:
                return message.mentions[0]
            return None

        try:
            # Owner-only intents
            owner_only = {'eco_set', 'eco_add', 'eco_remove', 'eco_reset', 'nuke', 'role_add', 'role_remove', 'hide', 'show'}
            if intent in owner_only and not is_owner:
                await self._safe_reply(message, "not letting you do that.")
                return True

            # FIX 2 — Require @mention for ALL moderation intents that target a user.
            # This prevents "warn diva" from warning the wrong target.
            # NOTE: message.mentions includes the bot itself when someone says
            # "@cyn warn @Diva" — so we must filter the bot out before picking
            # the target. Otherwise the self-target guard fires incorrectly.
            if intent in ("ban", "kick", "warn", "mute", "timeout"):
                # Filter out the bot itself and any bot accounts from mentions
                human_mentions = [m for m in message.mentions if m.id != self.bot.user.id]
                if not human_mentions:
                    await self._safe_reply(
                        message,
                        "mention who you want me to action. like @username"
                    )
                    return True
                target = human_mentions[0]
                if target.id == self.bot.user.id:
                    await self._safe_reply(message, "not doing that to myself.")
                    return True

            # ---- ban ----
            if intent == 'ban':
                # FIX 4 — permission check (bot owner / server owner / admin role / ban perm)
                if not self.check_mod_permission(message, required_perm="ban"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                reason = params.get('reason') or 'No reason'
                # FIX 5 — confirmation view
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Ban")
                embed.add_field(name="Target", value=target.mention)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"requested by {author.display_name}")

                async def do_ban():
                    try:
                        await target.ban(reason=reason)
                        await self._safe_reply(message, f"banned **{target}** — {reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to ban them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't ban: {e}")

                view = ModConfirmView(
                    action="ban", target=target, reason=reason,
                    executor_func=do_ban, requester_id=author.id,
                    requester_name=author.display_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- kick ----
            if intent == 'kick':
                if not self.check_mod_permission(message, required_perm="kick"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                reason = params.get('reason') or 'No reason'
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Kick")
                embed.add_field(name="Target", value=target.mention)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"requested by {author.display_name}")

                async def do_kick():
                    try:
                        await target.kick(reason=reason)
                        await self._safe_reply(message, f"kicked **{target}** — {reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to kick them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't kick: {e}")

                view = ModConfirmView(
                    action="kick", target=target, reason=reason,
                    executor_func=do_kick, requester_id=author.id,
                    requester_name=author.display_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- mute / timeout ----
            if intent in ('mute', 'timeout'):
                if not self.check_mod_permission(message, required_perm="timeout"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                seconds = params.get('duration_seconds') or 600
                if seconds > 2419200:
                    seconds = 2419200
                reason = params.get('reason') or 'No reason'
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Timeout")
                embed.add_field(name="Target", value=target.mention)
                embed.add_field(name="Duration", value=f"{seconds}s")
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"requested by {author.display_name}")

                async def do_timeout():
                    try:
                        await target.timeout(timedelta(seconds=seconds), reason=reason)
                        await self._safe_reply(message, f"muted **{target}** for {seconds}s — {reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to timeout them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't timeout: {e}")

                view = ModConfirmView(
                    action="timeout", target=target, reason=reason,
                    executor_func=do_timeout, requester_id=author.id,
                    requester_name=author.display_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- purge ----
            if intent == 'purge':
                if not self.check_mod_permission(message, required_perm="purge"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                amount = params.get('amount') or 5
                if amount < 1 or amount > 100:
                    amount = max(1, min(100, amount))
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Purge")
                embed.add_field(name="Amount", value=f"{amount} messages")
                embed.add_field(name="Channel", value=channel.mention, inline=False)
                embed.set_footer(text=f"requested by {author.display_name}")

                async def do_purge():
                    try:
                        deleted = await channel.purge(limit=amount)
                        await self._safe_reply(message, f"deleted {len(deleted)} messages")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to purge here.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't purge: {e}")

                view = ModConfirmView(
                    action="purge", target=None, reason="",
                    executor_func=do_purge, requester_id=author.id,
                    requester_name=author.display_name,
                    channel_name=channel.name, amount=amount
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- warn ----
            if intent == 'warn':
                if not self.check_mod_permission(message, required_perm="warn"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                reason = params.get('reason') or 'No reason'
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Warn")
                embed.add_field(name="Target", value=target.mention)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"requested by {author.display_name}")

                async def do_warn():
                    try:
                        mod_cog = self.bot.get_cog("Moderation")
                        if mod_cog and hasattr(mod_cog, "add_warning"):
                            await mod_cog.add_warning(guild, target, author, reason)
                        await self._safe_reply(message, f"⚠️ **{target}** has been warned: {reason}")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't warn: {e}")

                view = ModConfirmView(
                    action="warn", target=target, reason=reason,
                    executor_func=do_warn, requester_id=author.id,
                    requester_name=author.display_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- delete_message (FIX 3) ----
            if intent == 'delete_message':
                # Only owner or users with manage_messages can do this
                if not is_owner and not self.check_mod_permission(message, required_perm="purge"):
                    await self._safe_reply(message, "nice try.")
                    return True

                msg_id = params.get('message_id')

                if msg_id:
                    try:
                        msg_to_delete = await message.channel.fetch_message(int(msg_id))
                        await msg_to_delete.delete()
                        await self._safe_reply(
                            message,
                            "deleted, volc." if is_owner else "done."
                        )
                    except discord.NotFound:
                        await self._safe_reply(message, "message not found.")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to delete that.")
                    except (TypeError, ValueError):
                        await self._safe_reply(message, "that message ID doesn't look right.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't delete it: {e}")
                else:
                    # Try to delete the message the user is replying to
                    if message.reference:
                        try:
                            ref_msg = await message.channel.fetch_message(
                                message.reference.message_id
                            )
                            await ref_msg.delete()
                            await self._safe_reply(message, "done.")
                        except discord.NotFound:
                            await self._safe_reply(message, "that message is gone.")
                        except discord.Forbidden:
                            await self._safe_reply(message, "i don't have permission to delete that.")
                        except Exception:
                            await self._safe_reply(message, "couldn't delete it.")
                    else:
                        await self._safe_reply(
                            message,
                            "which message? reply to it or give me the message ID."
                        )
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

        # IMPROVEMENT 1 — log every mention
        guild_name = message.guild.name if message.guild else "DM"
        channel_name = f"#{message.channel.name}" if hasattr(message.channel, 'name') else "DM"
        print(f"[MENTION] {guild_name} | {channel_name} | "
              f"{message.author.display_name} ({message.author.id}) → "
              f"{message.content[:100]}")

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

            # IMPROVEMENT 1 — log the parsed intent
            intent = intent_data.get('intent', 'chat')
            params = intent_data.get('params', {})
            print(f"[INTENT] {message.author.display_name} → intent={intent} params={params}")

            if intent != 'chat':
                handled = await self._execute_intent(message, intent_data)
                if handled:
                    return

            async with message.channel.typing():
                response = await self.get_ai_response(
                    message.author.id, content, is_owner=is_owner_msg,
                    guild=message.guild, author_name=message.author.display_name,
                    channel=message.channel, member=message.author
                )

            # IMPROVEMENT 1 — log the response
            print(f"[RESPONSE] → {response[:100]}")

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

    # FIX 4 — /adminrole commands so server owners can grant AI moderation
    # access to a configured role (e.g. "Harry's server mods").
    @app_commands.command(name="adminrole",
                          description="Set the role that can use AI moderation")
    @app_commands.describe(role="The admin role")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def set_admin_role(self, interaction: discord.Interaction,
                             role: discord.Role):
        self.bot.increment_command('adminrole')
        await interaction.response.defer(ephemeral=True)
        # Only server owner or bot owner can set this
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if (interaction.user.id != interaction.guild.owner_id and
                interaction.user.id != owner_id):
            await interaction.followup.send("only the server owner can set this.")
            return
        settings = self.load_settings(interaction.guild_id)
        settings["admin_role_id"] = role.id
        self.save_settings(interaction.guild_id, settings)
        await interaction.followup.send(
            f"admin role set to {role.mention}. "
            f"members with this role can use AI moderation."
        )

    @app_commands.command(name="adminrole_remove",
                          description="Remove the AI moderation role")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def remove_admin_role(self, interaction: discord.Interaction):
        self.bot.increment_command('adminrole_remove')
        await interaction.response.defer(ephemeral=True)
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if (interaction.user.id != interaction.guild.owner_id and
                interaction.user.id != owner_id):
            await interaction.followup.send("only the server owner can do this.")
            return
        settings = self.load_settings(interaction.guild_id)
        settings["admin_role_id"] = None
        self.save_settings(interaction.guild_id, settings)
        await interaction.followup.send("admin role removed.")

    @app_commands.command(name="chat", description="Talk to cyn")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def chat(self, interaction: discord.Interaction, message: str):
        self.bot.increment_command('chat')
        await interaction.response.defer()
        self.update_rate_limit(interaction.user.id)
        is_owner_msg = interaction.user.id == OWNER_ID
        # For slash commands, interaction.user is a Member in a guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        response = await self.get_ai_response(
            interaction.user.id, message, is_owner=is_owner_msg,
            guild=interaction.guild, author_name=interaction.user.display_name,
            channel=interaction.channel, member=member
        )
        await interaction.followup.send(response)

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
                    # Parse user mentions from the message content so mod intents
                    # work via /cyn warn @user. Discord mention format: <@123> or <@!123>
                    import re as _re
                    mentioned_ids = [int(m) for m in _re.findall(r'<@!?(\d+)>', content)]
                    self.mentions = []
                    if interaction.guild and mentioned_ids:
                        for uid in mentioned_ids:
                            m = interaction.guild.get_member(uid)
                            if m:
                                self.mentions.append(m)
                    self.role_mentions = []
                async def reply(self, content=None, embed=None, mention_author=True, **kwargs):
                    await interaction.followup.send(content=content, embed=embed)

            fake_msg = FakeMessage(interaction, message)
            handled = await self._execute_intent(fake_msg, intent_data)
            if handled:
                return

        is_owner_msg = interaction.user.id == OWNER_ID
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        response = await self.get_ai_response(
            interaction.user.id, message, is_owner=is_owner_msg,
            guild=interaction.guild, author_name=interaction.user.display_name,
            channel=interaction.channel, member=member
        )
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
