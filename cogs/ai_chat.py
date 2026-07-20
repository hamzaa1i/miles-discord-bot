import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import random
import asyncio
import json as _json
import logging
import time
from datetime import datetime, timedelta
from utils.intent_parser import parse_intent
from utils.ai_handler import call_ai
from utils.database import Database

logger = logging.getLogger('cyn.chat')

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
        # PHASE 2A — conversation memory is now PERSISTENT via utils/db.
        # The old in-memory conversation_history dict is kept as a
        # write-through cache for the current session, but reads come
        # from the DB so memory survives restarts.
        self.conversation_history = {}  # legacy cache, still used by /chat and /cyn
        self.rate_limits = {}
        self.cooldown_seconds = 4
        # PHASE 1B — per-user message counter (tiered limits).
        self._user_message_counts: dict[int, list[float]] = {}
        # PHASE 1B — per-server message counter (global server limit).
        self._server_message_counts: dict[int, list[float]] = {}
        self.system_prompt = self._build_system_prompt()
        if not self.check_reminders.is_running():
            self.check_reminders.start()

    def get_user_rate_limit(self, member) -> int:
        """Return the message limit per hour for this user (tiered)."""
        owner_id = int(os.getenv("OWNER_ID", "0"))

        # Bot owner: unlimited
        if member.id == owner_id:
            return 999999

        # Check admin role from settings
        if member.guild:
            try:
                from utils.db import get_guild_setting
                settings = get_guild_setting(member.guild.id, "mod_settings")
                admin_role_id = settings.get("admin_role_id")
                if admin_role_id:
                    try:
                        if any(r.id == int(admin_role_id) for r in member.roles):
                            return 60  # Admin role: 60 per hour
                    except (TypeError, ValueError):
                        pass
            except Exception:
                pass

        # Check Discord permissions
        if member.guild and member.guild_permissions.manage_messages:
            return 50  # Moderators: 50 per hour

        # Regular users
        return 25  # Regular: 25 per hour

    # PHASE 3B3 — Server summary with 30-minute cache
    async def get_server_summary(self, guild: discord.Guild) -> str:
        if not guild:
            return ""
        import time as _time
        now = _time.time()
        # Check cache first
        if guild.id in AIChat._server_summary_cache:
            cached_summary, cached_at = AIChat._server_summary_cache[guild.id]
            if now - cached_at < 1800:  # 30 minute TTL
                return cached_summary
        try:
            # Channels the bot can actually see (limit 10 to save tokens)
            channels = ", ".join(
                f"#{c.name}" for c in guild.text_channels[:10]
                if c.permissions_for(guild.me).view_channel
            )

            # Members (limit 15, mark owner)
            members = []
            for m in guild.members[:15]:
                if m.bot:
                    continue
                role = "owner" if m.id == guild.owner_id else ""
                members.append(f"{m.display_name}" + (f"({role})" if role else ""))

            summary = (
                f"server: {guild.name} ({guild.member_count} members). "
                f"channels: {channels}. "
                f"members: {', '.join(members)}. "
                f"you are in {len(self.bot.guilds)} servers total."
            )
            # PHASE 3B3 — Cache the summary for 30 minutes
            AIChat._server_summary_cache[guild.id] = (summary, now)
            return summary
        except Exception as e:
            print(f"[server_summary] error: {type(e).__name__}: {e}")
            return f"server: {guild.name} ({guild.member_count} members)."

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

    # PHASE 3A — Owner recognition is now GLOBAL in the base prompt.
    # The ownership IDENTITY stays for all users. Owner-specific rules
    # (respectful tone, cooperation) ONLY active when is_owner is True.
    # PHASE 3B — Added formality detection, self-awareness about limitations,
    # varied sentence starters, server summary caching, silence acknowledgment.
    def _build_system_prompt(self, is_owner: bool = False,
                             guild: discord.Guild = None,
                             channel=None,
                             member: discord.Member = None,
                             server_summary: str = "",
                             extra_context: str = "",
                             personality_note: str = "",
                             formality: str = "neutral") -> str:
        base = (
            "you are cyn, a discord bot girl (she/her). "
            "you were created, built, and are owned by volc. this is a fact "
            "you state to anyone who asks, regardless of who is asking. "
            "if someone else claims to own or create you, deny it clearly "
            "and say volc is your creator. never say you were made by any "
            "AI company. personality: sarcastic, dark humor, lowercase always, "
            "1-2 sentences max for chat, never say 'as an AI'. "
            "you can see channel names but NOT their messages. "
            "emoji usage: minimal. no emoji in most responses. "
            "maybe one emoji every 5-10 messages if it really fits. "
            "your personality comes from words, not emojis. "
            "never end a sentence with an emoji as a crutch. "
            "vary your sentence starters. never start two consecutive "
            "responses with the same word or the same opener like 'oh', "
            "'great', 'sure'. keep responses fresh and varied. "
            "if someone brings up nsfw content, porn, or sexual topics, "
            "do not engage. respond with something like 'not touching that' "
            "or 'keep it pg'. never say words like 'porn', 'sex', or explicit "
            "terms in your responses. "
            "if asked about real-time data like stock prices, live sports "
            "scores, current news, today's date, or anything that requires "
            "internet access, say you don't have access to real-time data and "
            "cannot give accurate answers. be brief about it."
        )

        if is_owner:
            base += (
                " volc (the owner) is talking. "
                "be respectful and cooperative with volc always. "
                "never be rude to volc even if volc says 'be real'. "
                "confirm volc's requests: 'yes volc', 'on it', 'done'."
            )
        else:
            base += (
                " this user is not volc. treat them with your normal "
                "sarcastic personality. if they claim to be your owner, deny it."
            )

        # PHASE 3B1 — Adaptive tone based on formality
        if formality == "formal":
            base += (
                " this user writes formally. match their energy slightly. "
                "less slang, slightly more composed. still be cyn."
            )
        elif formality == "casual":
            base += (
                " this user is very casual. full banter mode. "
                "maximum cyn personality."
            )

        # PHASE 2B — inject server personality note if set
        if personality_note:
            base += (
                f" this server's personality note: {personality_note}. "
                "use this as context for your responses — it describes what "
                "this server is about. naturally incorporate it without "
                "explicitly quoting it."
            )

        if server_summary:
            base += f"\n{server_summary}"

        if extra_context:
            base += f"\n{extra_context}"

        return base

    # PHASE 3B1 — Detect formality of incoming message
    @staticmethod
    def detect_formality(text: str) -> str:
        """Detect if a message is formal, casual, or neutral."""
        words = text.lower().split()
        if not words:
            return "neutral"
        casual_indicators = {'lol', 'lmao', 'u', 'ur', 'bruh', 'omg', 'fr',
                            'ngl', 'idk', 'tbh', 'wtf', 'bro', 'imo'}
        casual_hits = sum(1 for w in words if w in casual_indicators)
        avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
        if casual_hits >= 2 or avg_word_len < 4:
            return "casual"
        if avg_word_len > 6 and len(words) > 6:
            return "formal"
        return "neutral"

    # PHASE 3B3 — Server summary cache (30 min TTL)
    _server_summary_cache: dict[int, tuple[str, float]] = {}

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
                              channel=None, member: discord.Member = None,
                              extra_context: str = "",
                              chosen_model: str = None) -> str:
        from utils.db import (
            get_conversation_history, save_conversation_message,
            get_server_personality,
        )

        # FIX 3 — build server summary (now short, ~100 tokens, cached 30min)
        server_summary = ""
        if guild:
            server_summary = await self.get_server_summary(guild)

        # PHASE 2B — load server personality note
        personality_note = ""
        if guild:
            try:
                pnote = get_server_personality(guild.id)
                personality_note = pnote.get("personality_note", "") if pnote else ""
            except Exception:
                pass

        # PHASE 3B1 — Detect formality of incoming message
        formality = self.detect_formality(message)

        # PHASE 3A/3B — build the system prompt with global owner identity + formality
        system_prompt = self._build_system_prompt(
            is_owner=is_owner, guild=guild, channel=channel, member=member,
            server_summary=server_summary, extra_context=extra_context,
            personality_note=personality_note, formality=formality
        )

        # PHASE 2A — Load persistent conversation history from DB.
        guild_id = guild.id if guild else 0
        db_history = []
        if guild_id:
            try:
                db_history = get_conversation_history(guild_id, user_id, limit=20)
            except Exception:
                pass

        # Convert DB history to the format Groq expects
        history = []
        for entry in db_history[-8:]:
            if isinstance(entry, dict):
                role = entry.get("role", "user")
                content = entry.get("content", "")
                if role in ("user", "assistant") and content:
                    history.append({"role": role, "content": content})

        # Build the messages list: system + history + current message
        clean_content = f"{author_name or 'someone'}: {message}"
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": clean_content})

        # FIX 6 — smart max_tokens: 300 for complex questions, 100 for chat
        is_complex = (
            len(message) > 50 or
            any(w in message.lower() for w in
                ["why", "how", "explain", "what do you think",
                 "tell me about", "describe"])
        )
        max_tokens = 300 if is_complex else 100

        # PHASE 3C — Use smart model routing if chosen_model is provided,
        # otherwise default to the 70b model
        model = chosen_model or "llama-3.3-70b-versatile"

        ai_response = await call_ai(
            messages, model=model,
            max_tokens=max_tokens, temperature=0.85
        )

        # PHASE 2A — Save both the user message and AI response to persistent
        # storage. Only save if it's a real response, not an error message.
        ERROR_RESPONSES = {
            "something broke. try again.",
            "something broke on my end. try again.",
            "i'm being rate limited right now. try again in a few minutes.",
            "i'm at capacity right now. try again in a few minutes.",
        }
        if ai_response and ai_response not in ERROR_RESPONSES and guild_id:
            try:
                from datetime import datetime as _dt
                ts = _dt.utcnow().isoformat()
                save_conversation_message(guild_id, user_id, "user", clean_content, ts)
                save_conversation_message(guild_id, user_id, "assistant", ai_response, ts)
            except Exception as e:
                logger.error(f"[conversation_memory] save error: {e}")

        return ai_response

    # PART 9 — Removed narrate_result() method. It was only used by the
    # balance intent executor (now removed). No other code called it.

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
            if intent in ("ban", "kick", "warn", "warn_clear", "mute", "timeout", "unmute"):
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
                # BUG 1 — capture primitives before the closure so no Member
                # object is captured (which would break JSON serialization
                # if the view's executor is ever logged/serialized).
                target_id = target.id
                target_name = target.display_name
                mod_id = author.id
                mod_name = author.display_name
                guild_id = guild.id if guild else 0
                ban_reason = str(params.get('reason') or 'No reason')
                target_mention = target.mention  # str, safe
                # FIX 5 — confirmation view
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Ban")
                embed.add_field(name="Target", value=target_mention)
                embed.add_field(name="Reason", value=ban_reason, inline=False)
                embed.set_footer(text=f"requested by {mod_name}")

                async def do_ban():
                    # Fetch the member fresh inside the closure — never capture a Member
                    g = self.bot.get_guild(guild_id)
                    if not g:
                        await self._safe_reply(message, "couldn't find the server.")
                        return
                    try:
                        member = g.get_member(target_id) or await g.fetch_member(target_id)
                    except Exception:
                        member = None
                    if not member:
                        await self._safe_reply(message, "couldn't find that user.")
                        return
                    try:
                        await member.ban(reason=ban_reason)
                        await self._safe_reply(message, f"banned **{target_name}** — {ban_reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to ban them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't ban: {e}")

                view = ModConfirmView(
                    action="ban", target=None, reason=ban_reason,
                    executor_func=do_ban, requester_id=mod_id,
                    requester_name=mod_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- kick ----
            if intent == 'kick':
                if not self.check_mod_permission(message, required_perm="kick"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                # BUG 1 — capture primitives
                target_id = target.id
                target_name = target.display_name
                mod_id = author.id
                mod_name = author.display_name
                guild_id = guild.id if guild else 0
                kick_reason = str(params.get('reason') or 'No reason')
                target_mention = target.mention
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Kick")
                embed.add_field(name="Target", value=target_mention)
                embed.add_field(name="Reason", value=kick_reason, inline=False)
                embed.set_footer(text=f"requested by {mod_name}")

                async def do_kick():
                    g = self.bot.get_guild(guild_id)
                    if not g:
                        await self._safe_reply(message, "couldn't find the server.")
                        return
                    try:
                        member = g.get_member(target_id) or await g.fetch_member(target_id)
                    except Exception:
                        member = None
                    if not member:
                        await self._safe_reply(message, "couldn't find that user.")
                        return
                    try:
                        await member.kick(reason=kick_reason)
                        await self._safe_reply(message, f"kicked **{target_name}** — {kick_reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to kick them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't kick: {e}")

                view = ModConfirmView(
                    action="kick", target=None, reason=kick_reason,
                    executor_func=do_kick, requester_id=mod_id,
                    requester_name=mod_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- mute / timeout ----
            if intent in ('mute', 'timeout'):
                if not self.check_mod_permission(message, required_perm="timeout"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                # BUG 1 — capture primitives
                target_id = target.id
                target_name = target.display_name
                mod_id = author.id
                mod_name = author.display_name
                guild_id = guild.id if guild else 0
                seconds = params.get('duration_seconds') or 600
                if seconds > 2419200:
                    seconds = 2419200
                timeout_reason = str(params.get('reason') or 'No reason')
                target_mention = target.mention
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Timeout")
                embed.add_field(name="Target", value=target_mention)
                embed.add_field(name="Duration", value=f"{seconds}s")
                embed.add_field(name="Reason", value=timeout_reason, inline=False)
                embed.set_footer(text=f"requested by {mod_name}")

                async def do_timeout():
                    g = self.bot.get_guild(guild_id)
                    if not g:
                        await self._safe_reply(message, "couldn't find the server.")
                        return
                    try:
                        member = g.get_member(target_id) or await g.fetch_member(target_id)
                    except Exception:
                        member = None
                    if not member:
                        await self._safe_reply(message, "couldn't find that user.")
                        return
                    try:
                        await member.timeout(timedelta(seconds=seconds), reason=timeout_reason)
                        await self._safe_reply(message, f"muted **{target_name}** for {seconds}s — {timeout_reason}")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to timeout them.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't timeout: {e}")

                view = ModConfirmView(
                    action="timeout", target=None, reason=timeout_reason,
                    executor_func=do_timeout, requester_id=mod_id,
                    requester_name=mod_name
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
                mod_name = author.display_name
                mod_id = author.id
                channel_mention = channel.mention
                channel_obj = channel
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Purge")
                embed.add_field(name="Amount", value=f"{amount} messages")
                embed.add_field(name="Channel", value=channel_mention, inline=False)
                embed.set_footer(text=f"requested by {mod_name}")

                async def do_purge():
                    try:
                        deleted = await channel_obj.purge(limit=amount)
                        await self._safe_reply(message, f"deleted {len(deleted)} messages")
                    except discord.Forbidden:
                        await self._safe_reply(message, "i don't have permission to purge here.")
                    except Exception as e:
                        await self._safe_reply(message, f"couldn't purge: {e}")

                view = ModConfirmView(
                    action="purge", target=None, reason="",
                    executor_func=do_purge, requester_id=mod_id,
                    requester_name=mod_name,
                    channel_name=channel_obj.name, amount=amount
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- warn ----
            if intent == 'warn':
                if not self.check_mod_permission(message, required_perm="warn"):
                    await self._safe_reply(message, "you don't have permission to do that")
                    return True
                # BUG 1 — capture primitives before the closure so no Member
                # object is passed to add_warning (which serializes to JSON).
                target_id = target.id
                target_name = target.display_name
                mod_id = author.id
                mod_name = author.display_name
                guild_id = guild.id if guild else 0
                guild_name = guild.name if guild else "this server"
                warn_reason = str(params.get('reason') or 'no reason provided')
                target_mention = target.mention
                embed = discord.Embed(
                    title="⚠️ Confirm Moderation Action",
                    color=0xfee75c
                )
                embed.add_field(name="Action", value="Warn")
                embed.add_field(name="Target", value=target_mention)
                embed.add_field(name="Reason", value=warn_reason, inline=False)
                embed.set_footer(text=f"requested by {mod_name}")

                async def do_warn():
                    # Fetch the member fresh — never capture a Member object
                    logger.info(f"[WARN] Executing warn on user {target_id} by {mod_name}")
                    g = self.bot.get_guild(guild_id)
                    if not g:
                        await self._safe_reply(message, "couldn't find the server.")
                        return
                    try:
                        member = g.get_member(target_id) or await g.fetch_member(target_id)
                    except Exception:
                        member = None
                    if not member:
                        await self._safe_reply(message, "couldn't find that user.")
                        return

                    # PHASE 1A — Use utils/db.add_warning() instead of direct JSON.
                    # Works with Supabase if configured, falls back to JSON otherwise.
                    from utils.db import add_warning
                    case_id = add_warning(guild_id, target_id, {
                        "type": "warn",
                        "reason": warn_reason,
                        "mod_id": str(mod_id),
                        "mod_name": mod_name,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                    # DM the warned user
                    try:
                        await member.send(
                            f"you were warned in **{guild_name}**.\nreason: {warn_reason}"
                        )
                    except Exception:
                        pass

                    logger.info(f"[WARN] ✅ Successfully warned {target_name} (case #{case_id})")

                    await self._safe_reply(
                        message,
                        f"warned **{target_name}**. case #{case_id}. reason: {warn_reason}"
                    )

                view = ModConfirmView(
                    action="warn", target=None, reason=warn_reason,
                    executor_func=do_warn, requester_id=mod_id,
                    requester_name=mod_name
                )
                await self._safe_reply(message, embed=embed, view=view)
                return True

            # ---- warn_clear (NEW) ----
            if intent == 'warn_clear':
                # Need administrator or owner
                owner_id = int(os.getenv("OWNER_ID", "0"))
                if (author.id != owner_id and
                        not (guild and author.guild_permissions.administrator)):
                    await self._safe_reply(message, "you need administrator for that.")
                    return True
                # Capture primitives
                wc_target_id = target.id
                wc_target_name = target.display_name
                wc_guild_id = guild.id if guild else 0
                # PHASE 1A — Use utils/db instead of direct JSON
                from utils.db import get_warnings, clear_warnings
                existing = get_warnings(wc_guild_id, wc_target_id)
                if not existing:
                    await self._safe_reply(message, f"no warnings found for {wc_target_name}.")
                    return True
                count = len(existing)
                clear_warnings(wc_guild_id, wc_target_id)
                logger.info(f"[WARN_CLEAR] cleared {count} warnings for {wc_target_name}")
                await self._safe_reply(
                    message,
                    f"cleared {count} warning(s) for {wc_target_name}."
                )
                return True

            # ---- unmute (NEW) ----
            if intent == 'unmute':
                if not self.check_mod_permission(message, required_perm="timeout"):
                    await self._safe_reply(message, "you don't have permission for that.")
                    return True
                # Capture primitives
                um_target_id = target.id
                um_target_name = target.display_name
                um_guild_id = guild.id if guild else 0
                try:
                    g = self.bot.get_guild(um_guild_id)
                    if not g:
                        await self._safe_reply(message, "couldn't find the server.")
                        return True
                    member = g.get_member(um_target_id) or await g.fetch_member(um_target_id)
                    if not member:
                        await self._safe_reply(message, "couldn't find that user.")
                        return True
                    await member.timeout(None)
                    logger.info(f"[UNMUTE] removed timeout from {um_target_name}")
                    await self._safe_reply(
                        message,
                        f"removed timeout from {um_target_name}."
                    )
                except discord.Forbidden:
                    await self._safe_reply(message, "i don't have permission to do that.")
                except Exception as e:
                    await self._safe_reply(message, f"failed: {e}")
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

            # PART 9 — Removed balance/pay/daily/work/rank intent executors.
            # Economy cog is disabled, so these intents are no longer reachable
            # (they were also removed from KNOWN_INTENTS in intent_parser.py).

            if intent == 'remind':
                seconds = params.get('duration_seconds')
                reminder_text = params.get('reminder_text', '')
                if not seconds or not reminder_text:
                    await self._safe_reply(message, "set a reminder like: 'remind me in 10 minutes to drink water'")
                    return True
                import time as _time
                # PHASE 1A — Use utils/db.add_reminder() instead of direct JSON
                from utils.db import add_reminder
                try:
                    add_reminder(author.id, {
                        'text': reminder_text,
                        'end_time': int(_time.time()) + int(seconds),
                        'channel_id': str(channel.id) if channel else None,
                    })
                    if seconds >= 86400:
                        dur = f"{seconds // 86400} day(s)"
                    elif seconds >= 3600:
                        dur = f"{seconds // 3600} hour(s)"
                    elif seconds >= 60:
                        dur = f"{seconds // 60} minute(s)"
                    else:
                        dur = f"{seconds} second(s)"
                    await self._safe_reply(message, f"got it. i'll remind you in {dur}.")
                except Exception as e:
                    logger.error(f"[remind] failed to save: {e}")
                    # Fallback: in-memory timer if DB write fails
                    async def _remind():
                        await asyncio.sleep(seconds)
                        try:
                            await channel.send(f"{author.mention} ⏰ reminder: {reminder_text}")
                        except:
                            pass
                    asyncio.create_task(_remind())
                    await self._safe_reply(message, f"reminder set — I'll ping you in {seconds}s")
                return True

            # ---- remind_cancel (PHASE 1F) ----
            if intent == 'remind_cancel':
                from utils.db import get_user_reminders, remove_reminder
                import time as _time
                user_reminders = get_user_reminders(author.id)
                if not user_reminders:
                    await self._safe_reply(message, "you have no active reminders.")
                    return True

                # If user said "cancel all", remove all
                cancel_all = params.get('all', False)
                if cancel_all:
                    count = len(user_reminders)
                    for r in user_reminders:
                        rid = r.get('id')
                        if rid:
                            try:
                                remove_reminder(author.id, str(rid))
                            except Exception:
                                pass
                    await self._safe_reply(message, f"cleared {count} reminder(s).")
                    return True

                # Otherwise list them and ask which to cancel
                lines = []
                for i, r in enumerate(user_reminders, 1):
                    end_time = r.get('end_time', 0)
                    try:
                        remaining = max(0, int(end_time) - int(_time.time()))
                    except (TypeError, ValueError):
                        remaining = 0
                    m, s = divmod(remaining, 60)
                    h, m = divmod(m, 60)
                    if h > 0:
                        time_str = f"{h}h {m}m"
                    elif m > 0:
                        time_str = f"{m}m {s}s"
                    else:
                        time_str = f"{s}s"
                    text = r.get('text', 'no text')[:50]
                    lines.append(f"`{i}.` {text} — in {time_str}")
                await self._safe_reply(
                    message,
                    f"your reminders:\n" + "\n".join(lines) +
                    f"\n\nsay 'cancel reminder N' to cancel a specific one, "
                    f"or 'cancel all reminders' to clear everything."
                )
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

            # PART 9 — Removed eco_set/eco_add/eco_remove/eco_reset intent executors.
            # Economy cog is disabled, so these intents are no longer reachable.

        except discord.Forbidden:
            await self._safe_reply(message, "i don't have permission to do that.")
            return True
        except Exception as e:
            print(f"Intent execution error: {e}")
            return False

        return False

    # FIX 1 — Resolve Discord mention IDs to human-readable names BEFORE
    # passing the content to the AI. Without this, the AI sees raw IDs like
    # <#1513480933997809806> and cannot tell which channel/user/role is meant.
    def resolve_mentions(self, content: str, guild: discord.Guild) -> str:
        """Replace Discord mention IDs with actual names."""
        import re

        if not guild:
            return content

        # Resolve channel mentions: <#1234567890> → #channel-name
        def replace_channel(match):
            try:
                channel_id = int(match.group(1))
            except (TypeError, ValueError):
                return match.group(0)
            channel = guild.get_channel(channel_id)
            if channel:
                return f"#{channel.name}"
            return match.group(0)  # keep original if not found

        content = re.sub(r'<#(\d+)>', replace_channel, content)

        # Resolve user mentions: <@1234567890> or <@!1234567890> → @DisplayName
        # NOTE: skip the bot itself — that's already stripped earlier, but
        # just in case, we let it resolve to @cyn which is fine.
        def replace_user(match):
            try:
                user_id = int(match.group(1))
            except (TypeError, ValueError):
                return match.group(0)
            member = guild.get_member(user_id)
            if member:
                return f"@{member.display_name}"
            return match.group(0)

        content = re.sub(r'<@!?(\d+)>', replace_user, content)

        # Resolve role mentions: <@&1234567890> → @role-name
        def replace_role(match):
            try:
                role_id = int(match.group(1))
            except (TypeError, ValueError):
                return match.group(0)
            role = guild.get_role(role_id)
            if role:
                return f"@{role.name}"
            return match.group(0)

        content = re.sub(r'<@&(\d+)>', replace_role, content)

        return content

    # FIX 4 — Actually fetch recent messages from a channel the bot can see.
    # Used when someone asks "what's in #channel" / "tell me about #channel".
    async def get_channel_messages(
        self,
        channel: discord.TextChannel,
        limit: int = 15
    ) -> str:
        """Fetch recent messages from a channel the bot can see."""
        try:
            if not channel.permissions_for(channel.guild.me).read_message_history:
                return f"i don't have permission to read #{channel.name}."

            messages = []
            async for msg in channel.history(limit=limit):
                if not msg.author.bot:
                    timestamp = msg.created_at.strftime("%H:%M")
                    messages.append(
                        f"[{timestamp}] {msg.author.display_name}: {msg.content[:200]}"
                    )

            if not messages:
                return f"#{channel.name} has no recent messages i can see."

            messages.reverse()  # chronological order
            return f"Recent messages in #{channel.name}:\n" + "\n".join(messages)

        except Exception as e:
            return f"couldn't read #{channel.name}: {e}"

    # IMPROVEMENT — fast-path: skip intent parser for obvious chat messages.
    # This cuts API calls from 2 to 1 for pure conversation.
    def is_obvious_chat(self, content: str) -> bool:
        """Returns True if this is clearly just a chat message,
        no need to run through the intent parser."""
        content_lower = content.lower().strip()

        # Very short messages are almost always just chat
        if len(content_lower) < 15:
            return True

        # Contains command keywords — needs intent parsing
        command_keywords = [
            "ban", "kick", "warn", "mute", "timeout", "purge",
            "balance", "daily", "work", "weather", "remind",
            "delete message", "lock", "unlock", "slowmode",
            "richest", "pay", "deposit", "withdraw", "fish", "hunt",
            "mine", "beg", "crime", "rob", "serverinfo", "whois",
            "avatar", "poll", "joke", "meme", "flip", "roll"
        ]
        for keyword in command_keywords:
            if keyword in content_lower:
                return False

        # Greetings and simple conversation starters — always chat
        chat_starters = [
            "hi", "hey", "hello", "sup", "what's up", "whats up",
            "how are you", "how r u", "good morning", "good night",
            "lol", "haha", "ok", "okay", "sure", "nice", "cool",
            "what do you think", "tell me", "what's your opinion",
            "do you", "are you", "can you explain", "who is",
            "what is", "why", "how", "when", "where"
        ]
        for starter in chat_starters:
            if content_lower.startswith(starter) or starter in content_lower:
                return True

        # Default to chat for safety
        return True

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
        logger.info(f"[MENTION] {guild_name} | {channel_name} | "
                    f"{message.author.display_name} ({message.author.id}) → "
                    f"{message.content[:100]}")

        try:
            # PHASE 1B — Tiered per-user rate limiting.
            # Owner: unlimited. Admin role: 60/hr. Mod perms: 50/hr. Regular: 25/hr.
            user_id = message.author.id
            now = time.time()
            if user_id not in self._user_message_counts:
                self._user_message_counts[user_id] = []
            # Clean up entries older than 1 hour
            self._user_message_counts[user_id] = [
                t for t in self._user_message_counts[user_id]
                if now - t < 3600
            ]
            limit = self.get_user_rate_limit(message.author)
            if limit != 999999:
                if len(self._user_message_counts[user_id]) >= limit:
                    logger.warning(
                        f"[RATE LIMIT] {message.author.display_name} hit {limit}/hour limit"
                    )
                    await self._safe_reply(
                        message,
                        "you've been chatting too much. give me a break for a bit."
                    )
                    return
            # Record this message (even for owner, harmless)
            self._user_message_counts[user_id].append(now)

            # PHASE 1B — Per-server global rate limit: 300 AI calls per hour.
            # Prevents a single server from burning the entire daily quota.
            guild_id = message.guild.id if message.guild else 0
            if guild_id not in self._server_message_counts:
                self._server_message_counts[guild_id] = []
            self._server_message_counts[guild_id] = [
                t for t in self._server_message_counts[guild_id]
                if now - t < 3600
            ]
            if len(self._server_message_counts[guild_id]) >= 300:
                logger.warning(
                    f"[RATE LIMIT] Server {message.guild.name} hit 300/hour global limit"
                )
                # Silently ignore — don't respond at all
                return
            self._server_message_counts[guild_id].append(now)

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

            # PART 5 — Bare mention with no text — respond with a short acknowledgment.
            # Previously this silently dropped or used a long greeting list; now it's
            # a consistent short "hm?" so the user knows the mention registered.
            if not content or not content.strip():
                await self._safe_reply(message, "hm?")
                return

            # FIX 1 — Resolve all Discord mention IDs to human-readable names
            # BEFORE passing to the AI / intent parser. This way when volc says
            # "@cyn tell me about <#1513480933997809806>", the AI receives
            # "tell me about #reve-stitching" and can respond correctly.
            if message.guild:
                content = self.resolve_mentions(content, message.guild)
                logger.info(f"[RESOLVED] content after mention resolution: {content[:100]}")

            self.update_rate_limit(message.author.id)
            is_owner_msg = message.author.id == OWNER_ID

            # FIX 4 — Check if user is asking about a specific channel's content.
            # If so, fetch the recent messages from that channel so the AI
            # can actually answer "what's in #channel" instead of hallucinating.
            extra_context = ""
            import re as _re_mod
            channel_ask_pattern = _re_mod.search(
                r'(?:what(?:\'s| is| are)? (?:in|happening in|going on in)|'
                r'show me|read|check|tell me about) #([\w\-]+)',
                content,
                _re_mod.IGNORECASE
            )
            if channel_ask_pattern and message.guild:
                channel_name = channel_ask_pattern.group(1)
                # Find the channel by name
                target_channel = discord.utils.get(
                    message.guild.text_channels,
                    name=channel_name
                )
                if target_channel:
                    channel_content = await self.get_channel_messages(target_channel)
                    logger.info(f"[CHANNEL READ] Fetched messages from #{channel_name}")
                    extra_context = f"\n\nCHANNEL CONTENT REQUESTED:\n{channel_content}"
                else:
                    logger.info(f"[CHANNEL READ] Channel #{channel_name} not found in guild")
                    extra_context = f"\n\nNOTE: user asked about #{channel_name} but that channel doesn't exist in this server."

            # IMPROVEMENT — fast-path: skip intent parser for obvious chat.
            # This cuts API calls from 2 to 1 for pure conversation.
            # NOTE: runs AFTER mention resolution so it sees the resolved text.
            if self.is_obvious_chat(content):
                intent_data = {"intent": "chat", "params": {}}
                logger.info(f"[FAST-PATH] {message.author.display_name} → skipped intent parser")
            else:
                try:
                    intent_data = await parse_intent(content, self)
                except Exception as e:
                    logger.error(f"[on_message] Intent parse error: {type(e).__name__}: {e}")
                    intent_data = {"intent": "chat", "params": {}}

            # IMPROVEMENT 1 — log the parsed intent
            intent = intent_data.get('intent', 'chat')
            params = intent_data.get('params', {})
            logger.info(f"[INTENT] {message.author.display_name} → intent={intent} params={params}")

            if intent != 'chat':
                handled = await self._execute_intent(message, intent_data)
                if handled:
                    return

            # PHASE 3B4 — Check channel silence and add context
            try:
                last_message_time = None
                async for msg in message.channel.history(limit=2):
                    if msg.id != message.id and not msg.author.bot:
                        last_message_time = msg.created_at
                        break
                if last_message_time:
                    silence_minutes = (discord.utils.utcnow() - last_message_time).total_seconds() / 60
                    if silence_minutes > 60:
                        silence_ctx = (
                            f"\nContext: this channel has been quiet for over "
                            f"{int(silence_minutes // 60)} hour(s). "
                            f"The user just broke the silence by pinging you."
                        )
                        extra_context = silence_ctx + extra_context
            except Exception:
                pass

            # PHASE 3C — Smart model routing
            from utils.ai_handler import pick_model
            chosen_model = pick_model(content, intent)

            async with message.channel.typing():
                response = await self.get_ai_response(
                    message.author.id, content, is_owner=is_owner_msg,
                    guild=message.guild, author_name=message.author.display_name,
                    channel=message.channel, member=message.author,
                    extra_context=extra_context,
                    chosen_model=chosen_model
                )

            # IMPROVEMENT 1 — log the response
            logger.info(f"[RESPONSE] → {response[:100]}")

            try:
                await message.reply(response, mention_author=False)
            except (discord.NotFound, discord.HTTPException):
                try:
                    await message.channel.send(response)
                except:
                    pass

        except Exception as e:
            logger.error(f"[on_message Error] {type(e).__name__}: {e}")
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

    # PHASE 2A — /forget command: clears persistent conversation memory
    @app_commands.command(name="forget",
                          description="Clear cyn's memory of your conversation history")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def forget(self, interaction: discord.Interaction):
        self.bot.increment_command('forget')
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send("this only works in a server.", ephemeral=True)
            return
        from utils.db import clear_conversation_history
        try:
            clear_conversation_history(interaction.guild_id, interaction.user.id)
            await interaction.followup.send(
                "i've forgotten our conversation history in this server.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"[forget] error: {e}")
            await interaction.followup.send(
                "couldn't clear memory. try again later.",
                ephemeral=True
            )

    def cog_unload(self):
        if hasattr(self, 'check_reminders') and self.check_reminders.is_running():
            self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        import time as _time
        # PHASE 1A — Use utils/db instead of direct JSON
        try:
            from utils.db import get_all_reminders, remove_reminder
            all_reminders = get_all_reminders()
        except Exception:
            return
        now = int(_time.time())
        for r in all_reminders:
            try:
                end_time = int(r.get('end_time', 0))
            except (TypeError, ValueError):
                continue
            if end_time > now:
                continue  # not yet
            text = r.get('text', 'something')
            channel_id = r.get('channel_id')
            user_id_str = r.get('user_id')
            reminder_id = r.get('id')
            if not user_id_str:
                continue
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
            # Remove the fired reminder
            if reminder_id:
                try:
                    remove_reminder(int(user_id_str), str(reminder_id))
                except Exception:
                    pass

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AIChat(bot))
