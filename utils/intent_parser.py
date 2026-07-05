"""
utils/intent_parser.py — Natural language → command intent parser.

FIX 8 robustness:
  1. Entire function wrapped in try/except — any failure returns chat.
  2. Strips markdown code fences (```json ... ```) before parsing.
  3. Validates intent against a known list; unknown → chat.
  4. 10-second timeout on the AI call; on timeout returns chat.
"""
import json
import os
import asyncio
import aiohttp

# Use the same AI backend as cogs/ai_chat.py
_API_URL = "https://models.inference.ai.azure.com/chat/completions"
_MODEL = "gpt-4o-mini"

INTENT_SYSTEM_PROMPT = (
    "You are a command intent parser. Given a Discord user's message, return a JSON object "
    "identifying what bot command they want to run and extract the parameters. "
    "Return ONLY valid JSON, nothing else.\n\n"
    "Format: {\"intent\": \"command_name\", \"params\": {}}\n\n"
    "If no command matches, return: {\"intent\": \"chat\", \"params\": {}}\n\n"
    "Possible intents and their params:\n"
    "- ban: {user_id, reason}\n"
    "- kick: {user_id, reason}\n"
    "- mute: {user_id, duration, reason}\n"
    "- purge: {amount}\n"
    "- warn: {user_id, reason}\n"
    "- balance: {user_id} (optional, defaults to sender)\n"
    "- pay: {target_user_id, amount}\n"
    "- daily: {}\n"
    "- work: {}\n"
    "- rank: {user_id} (optional)\n"
    "- leaderboard: {}\n"
    "- remind: {duration_seconds, reminder_text}\n"
    "- serverinfo: {}\n"
    "- avatar: {user_id} (optional)\n"
    "- poll: {question, options_list}\n"
    "- joke: {}\n"
    "- meme: {}\n"
    "- rps: {}\n"
    "- trivia: {}\n"
    "- weather: {city}\n"
    "- flip: {}\n"
    "- roll: {sides}\n"
    "- chat: {} (default fallback)"
)

KNOWN_INTENTS = {
    'ban', 'kick', 'mute', 'purge', 'warn', 'balance', 'pay', 'daily',
    'work', 'rank', 'leaderboard', 'remind', 'serverinfo', 'avatar',
    'poll', 'joke', 'meme', 'rps', 'trivia', 'weather', 'flip', 'roll',
    'chat',
}


def _extract_user_id(raw):
    """Accept <@123>, <@!123>, '123', or None and return int or None."""
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
    """Clean up params returned by the AI: cast IDs, amounts, etc."""
    if not isinstance(params, dict):
        return {}
    cleaned = {}
    for k, v in params.items():
        if k in ('user_id', 'target_user_id'):
            cleaned[k] = _extract_user_id(v)
        elif k in ('amount', 'sides', 'duration_seconds'):
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
    """Remove ```...``` fences around a JSON response from the AI."""
    response = text.strip()
    if response.startswith("```"):
        # Split on triple-backtick and take whatever's inside the first fence
        parts = response.split("```")
        if len(parts) >= 2:
            response = parts[1]
        # Strip optional language tag (json / python / etc.)
        if response.lower().startswith("json"):
            response = response[4:]
        response = response.strip()
        # Remove any trailing closing fence that may have survived
        if response.endswith("```"):
            response = response[:-3].strip()
    return response


async def parse_intent(message_content: str, ai_handler) -> dict:
    """
    Ask the AI to parse a user message into an intent + params.

    `ai_handler` is the AIChat cog instance — we reuse its github_token.
    Always returns a dict — falls back to {"intent": "chat", "params": {}}
    on any error (network, timeout, JSON parse failure, unknown intent).
    """
    fallback = {"intent": "chat", "params": {}}

    # FIX 8 (1) — wrap the entire function body in try/except
    try:
        github_token = getattr(ai_handler, 'github_token', None) or os.getenv('GITHUB_TOKEN')
        if not github_token:
            return fallback

        headers = {
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": message_content}
            ],
            "temperature": 0.0,
            "max_tokens": 200
        }

        # FIX 8 (4) — 10-second timeout on the AI call
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        return fallback
                    data = await response.json()
                    raw = data['choices'][0]['message']['content']
        except asyncio.TimeoutError:
            return fallback
        except Exception:
            return fallback

        # FIX 8 (2) — strip markdown code fences before parsing
        raw = _strip_code_fences(raw)

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return fallback

        if not isinstance(parsed, dict):
            return fallback

        intent = str(parsed.get('intent', 'chat')).lower().strip()
        params = parsed.get('params', {}) or {}

        # FIX 8 (3) — validate intent against the known list
        if intent not in KNOWN_INTENTS:
            return fallback

        return {"intent": intent, "params": normalize_params(params)}
    except Exception:
        # Catch-all — never raise out of this function
        return fallback
