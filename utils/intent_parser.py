"""
utils/intent_parser.py — Natural language → command intent parser.
Uses Groq API (mixtral-8x7b for speed).
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
    "- ban: {user_id, reason}\n"
    "- kick: {user_id, reason}\n"
    "- mute: {user_id, duration_seconds, reason}\n"
    "- unmute: {user_id}\n"
    "- purge: {amount}\n"
    "- warn: {user_id, reason}\n"
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
    "- inventory: {}\n"
    "- richest: {}\n"
    "- rank: {user_id} (optional)\n"
    "- remind: {duration_seconds, reminder_text}\n"
    "- serverinfo: {}\n"
    "- ping: {}\n"
    "- botinfo: {}\n"
    "- uptime: {}\n"
    "- whois: {user_id} (optional)\n"
    "- avatar: {user_id} (optional)\n"
    "- poll: {question}\n"
    "- joke: {}\n"
    "- meme: {}\n"
    "- fact: {}\n"
    "- quote: {}\n"
    "- roast: {user_id} (optional)\n"
    "- compliment: {user_id} (optional)\n"
    "- rate: {thing}\n"
    "- ship: {user_id1, user_id2}\n"
    "- battle: {user_id}\n"
    "- vibe: {}\n"
    "- flip: {}\n"
    "- roll: {sides}\n"
    "- truth: {}\n"
    "- dare: {}\n"
    "- weather: {city}\n"
    "- suggest: {text}\n"
    "- birthday_check: {user_id}\n"
    "- rep_give: {user_id, reason}\n"
    "- rep_check: {user_id}\n"
    "- marry: {user_id}\n"
    "- divorce: {}\n"
    "- chat: {} (default fallback)"
)

KNOWN_INTENTS = {
    'ban', 'kick', 'mute', 'unmute', 'purge', 'warn', 'slowmode', 'lock', 'unlock',
    'hide', 'show', 'nuke', 'role_add', 'role_remove',
    'balance', 'pay', 'daily', 'work',
    'earn_fish', 'earn_hunt', 'earn_mine', 'earn_beg', 'earn_crime', 'earn_rob',
    'bank_deposit', 'bank_withdraw',
    'eco_set', 'eco_add', 'eco_remove', 'eco_reset',
    'inventory', 'richest',
    'rank', 'remind', 'serverinfo', 'ping', 'botinfo', 'uptime', 'whois', 'avatar',
    'poll', 'joke', 'meme', 'fact', 'quote', 'roast', 'compliment', 'rate', 'ship',
    'battle', 'vibe', 'flip', 'roll', 'truth', 'dare', 'weather',
    'suggest', 'birthday_check', 'rep_give', 'rep_check', 'marry', 'divorce',
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
        elif k in ('amount', 'sides', 'duration_seconds', 'seconds'):
            try:
                cleaned[k] = int(v)
            except (TypeError, ValueError):
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
        ], max_tokens=200)

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
