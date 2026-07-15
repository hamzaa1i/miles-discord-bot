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
    "- purge: {amount}\n"
    "- warn: {user_id, reason} — REQUIRES a @mention of the target in the message\n"
    "- delete_message: {message_id} — user wants to delete a specific message by ID, "
    "OR wants to delete the message they are replying to. Look for patterns like "
    "'delete message: 1234567890' or 'delete this message' or 'delete [id]'. "
    "If no message ID is visible, return {\"message_id\": null} and the bot will try "
    "the replied-to message.\n"
    "- slowmode: {seconds}\n"
    "- lock: {}\n"
    "- unlock: {}\n"
    "- hide: {}\n"
    "- show: {}\n"
    "- nuke: {}\n"
    "- role_add: {user_id, role}\n"
    "- role_remove: {user_id, role}\n"
    "- balance: {user_id} (optional)\n"
    "- pay: {target_user_id, amount}\n"
    "- daily: {}\n"
    "- work: {}\n"
    "- earn_fish: {}\n"
    "- earn_hunt: {}\n"
    "- earn_mine: {}\n"
    "- earn_beg: {}\n"
    "- earn_crime: {}\n"
    "- earn_rob: {user_id}\n"
    "- bank_deposit: {amount}\n"
    "- bank_withdraw: {amount}\n"
    "- eco_set: {user_id, amount}\n"
    "- eco_add: {user_id, amount}\n"
    "- eco_remove: {user_id, amount}\n"
    "- eco_reset: {user_id}\n"
    "- richest: {}\n"
    "- remind: {duration_seconds, reminder_text}\n"
    "- serverinfo: {} — ONLY for explicit requests for server statistics "
    "or data like member count, channel count, creation date. "
    "Examples that ARE serverinfo: 'server info', 'server stats', "
    "'server statistics', 'show me server info', 'what are the server details', "
    "'info about this server'. "
    "NOT serverinfo: 'how many servers are you in', 'what servers are you in', "
    "'how many servers do you have', 'how many guilds' (about the BOT, return 'chat'), "
    "'what is this server about', 'what is this server', 'tell me about this server', "
    "'what kind of server is this', 'what do u think of this server' (opinion/casual "
    "questions — return 'chat' so the AI answers from its server context knowledge, "
    "not by running a command).\n"
    "- ping: {}\n"
    "- botinfo: {}\n"
    "- uptime: {}\n"
    "- whois: {user_id} (optional)\n"
    "- avatar: {user_id} (optional)\n"
    "- poll: {question}\n"
    "- joke: {}\n"
    "- meme: {}\n"
    "- roast: {user_id} (optional)\n"
    "- flip: {}\n"
    "- roll: {sides}\n"
    "- weather: {city}\n"
    "- rep_give: {user_id, reason}\n"
    "- marry: {user_id}\n"
    "- divorce: {}\n"
    "- chat: {} (default fallback)\n\n"
    "IMPORTANT: Moderation intents (ban, kick, warn, mute) ONLY apply when there "
    "is a @mention pattern (like <@123456> or @username format) visible in the "
    "message. If a user says 'warn diva' with no @mention, return 'chat' intent, "
    "NOT 'warn' — the bot cannot reliably identify who 'diva' is without a mention."
)

KNOWN_INTENTS = {
    'ban', 'kick', 'mute', 'purge', 'warn', 'delete_message',
    'slowmode', 'lock', 'unlock',
    'hide', 'show', 'nuke', 'role_add', 'role_remove',
    'balance', 'pay', 'daily', 'work',
    'earn_fish', 'earn_hunt', 'earn_mine', 'earn_beg', 'earn_crime', 'earn_rob',
    'bank_deposit', 'bank_withdraw',
    'eco_set', 'eco_add', 'eco_remove', 'eco_reset',
    'richest',
    'remind', 'serverinfo', 'ping', 'botinfo', 'uptime', 'whois', 'avatar',
    'poll', 'joke', 'meme', 'roast',
    'flip', 'roll', 'weather',
    'rep_give', 'marry', 'divorce',
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
