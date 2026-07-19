"""
utils/intent_parser.py — Natural language → command intent parser.
Uses Groq API (llama-3.1-8b-instant for speed).
"""
import json
import os
from utils.ai_handler import call_ai_fast

INTENT_SYSTEM_PROMPT = (
    "You are a command intent parser. Given a Discord user's message, return a JSON object "
    "identifying what bot command they want to run and extract the parameters. "
    "Return ONLY valid JSON, nothing else.\n\n"
    "Format: {\"intent\": \"command_name\", \"params\": {}}\n\n"
    "If no command matches, return: {\"intent\": \"chat\", \"params\": {}}\n\n"
    "Possible intents and their params:\n"
    "- ban: {user_id, reason} — REQUIRES a @mention of the target in the message\n"
    "- kick: {user_id, reason} — REQUIRES a @mention of the target in the message\n"
    "- mute: {user_id, duration_seconds, reason} — REQUIRES a @mention of the target in the message\n"
    "- timeout: same as mute (alias)\n"
    "- unmute: {user_id} — remove timeout from a user. REQUIRES a @mention.\n"
    "- purge: {amount}\n"
    "- warn: {user_id, reason} — REQUIRES a @mention of the target in the message\n"
    "- warn_clear: {user_id} — clear all warnings for a user. REQUIRES a @mention.\n"
    "- delete_message: {message_id} — delete a specific message by ID, or the "
    "message they are replying to. Look for 'delete message: 1234567890' or "
    "'delete this message'. If no ID visible, return {\"message_id\": null}.\n"
    "- slowmode: {seconds}\n"
    "- lock: {}\n"
    "- unlock: {}\n"
    "- hide: {}\n"
    "- show: {}\n"
    "- nuke: {}\n"
    "- nick: {user_id, nickname} — change a user's nickname. REQUIRES a @mention.\n"
    "- role_add: {user_id, role}\n"
    "- role_remove: {user_id, role}\n"
    "- remind: {duration_seconds, reminder_text}\n"
    "- serverinfo: {} — ONLY for explicit requests for server statistics "
    "or data like member count, channel count, creation date. "
    "Examples that ARE serverinfo: 'server info', 'server stats', "
    "'server statistics', 'show me server info', 'what are the server details'. "
    "NOT serverinfo: 'how many servers are you in' (about the BOT, return 'chat'), "
    "'what is this server about', 'tell me about this server' (opinion/casual, "
    "return 'chat' so the AI answers from context).\n"
    "- ping: {}\n"
    "- botinfo: {}\n"
    "- uptime: {}\n"
    "- whois: {user_id} (optional)\n"
    "- avatar: {user_id} (optional)\n"
    "- joke: {}\n"
    "- meme: {}\n"
    "- flip: {}\n"
    "- roll: {sides}\n"
    "- fact: {} — user wants a random fun fact\n"
    "- truth: {} — user wants a truth question\n"
    "- dare: {} — user wants a dare challenge\n"
    "- weather: {city}\n"
    "- chat: {} (default fallback)\n\n"
    "IMPORTANT: Moderation intents (ban, kick, warn, mute) ONLY apply when there "
    "is a @mention pattern (like <@123456> or @username format) visible in the "
    "message. If a user says 'warn diva' with no @mention, return 'chat' intent, "
    "NOT 'warn' — the bot cannot reliably identify who 'diva' is without a mention.\n\n"
    "NOTE: 'poll' intent has been removed. If a user talks about polls, voting, "
    "or poll results, return 'chat' — the AI handles it conversationally."
)

KNOWN_INTENTS = {
    'ban', 'kick', 'mute', 'timeout', 'unmute', 'purge',
    'warn', 'warn_clear', 'delete_message',
    'slowmode', 'lock', 'unlock',
    'hide', 'show', 'nuke', 'nick', 'role_add', 'role_remove',
    'remind', 'serverinfo', 'ping', 'botinfo', 'uptime', 'whois', 'avatar',
    'joke', 'meme', 'flip', 'roll', 'fact', 'truth', 'dare', 'weather',
    'chat',
}


def _extract_user_id(raw):
    if raw is None:
        return None
    if not isinstance(raw, (str, int)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    for prefix in ('<@!', '<@', '<#', '<@&'):
        if s.startswith(prefix):
            s = s[len(prefix):]
    s = s.rstrip('>').strip()
    try:
        return int(s)
    except ValueError:
        return None


def normalize_params(params: dict) -> dict:
    if not isinstance(params, dict):
        return {}
    cleaned = {}
    for k, v in params.items():
        if k in ('user_id', 'target_user_id', 'user_id1', 'user_id2'):
            cleaned[k] = _extract_user_id(v)
        elif k in ('amount', 'sides', 'duration_seconds', 'seconds', 'message_id'):
            if v is None:
                cleaned[k] = None
            else:
                try:
                    cleaned[k] = int(v)
                except (TypeError, ValueError):
                    # message_id may be a string with extra chars — try to extract digits
                    if k == 'message_id' and isinstance(v, str):
                        import re as _re
                        m = _re.search(r'\d{10,}', v)
                        cleaned[k] = int(m.group(0)) if m else None
                    else:
                        cleaned[k] = None
        elif isinstance(v, list):
            cleaned[k] = [str(x) for x in v]
        else:
            cleaned[k] = str(v) if v is not None else None
    return cleaned


def _strip_code_fences(text: str) -> str:
    response = text.strip()
    if response.startswith("```"):
        parts = response.split("```")
        if len(parts) >= 2:
            response = parts[1]
        if response.lower().startswith("json"):
            response = response[4:]
        response = response.strip()
        if response.endswith("```"):
            response = response[:-3].strip()
    return response


async def parse_intent(message_content: str, ai_handler) -> dict:
    fallback = {"intent": "chat", "params": {}}
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            return fallback

        raw = await call_ai_fast([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": message_content}
        ], max_tokens=100)

        if not raw or "something broke" in raw:
            return fallback

        raw = _strip_code_fences(raw)

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return fallback

        if not isinstance(parsed, dict):
            return fallback

        intent = str(parsed.get('intent', 'chat')).lower().strip()
        params = parsed.get('params', {}) or {}

        if intent not in KNOWN_INTENTS:
            return fallback

        return {"intent": intent, "params": normalize_params(params)}
    except Exception:
        return fallback
