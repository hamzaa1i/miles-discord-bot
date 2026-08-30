"""
utils/intent_parser.py — Natural language → command intent parser.
Uses Groq API (openai/gpt-oss-20b for speed and stable JSON output).
"""
import json
import os
import re
from utils.ai_handler import call_ai_fast

INTENT_SYSTEM_PROMPT = (
    "You are a command intent parser. Given a Discord user's message, return a JSON object "
    "identifying what bot command they want to run and extract the parameters. "
    "Return ONLY valid JSON, nothing else.\n\n"
    "Format: {\"intent\": \"command_name\", \"params\": {}}\n\n"
    "If no command matches, return: {\"intent\": \"chat\", \"params\": {}}\n\n"
    "Possible intents and their params:\n\n"
    "=== MODERATION INTENTS (highest priority) ===\n"
    "- mute: {user_id, duration_seconds, reason} — user wants to mute/timeout someone "
    "in the server.\n"
    "  Examples: 'mute @user', 'mute @user for 1m', 'timeout @user 5m', 'mute them', "
    "'put @user on timeout for 10 minutes'\n"
    "  REQUIRES an @mention of the target user.\n"
    "  Params: user_id (from the @mention), duration_seconds (if provided, converted "
    "to seconds: '1m'→60, '5m'→300, '10 minutes'→600, '2h'→7200, '1d'→86400), "
    "reason (if provided)\n"
    "- timeout: same as mute — user wants to timeout someone. Treat 'mute' and "
    "'timeout' as synonyms.\n"
    "- unmute: {user_id} — user wants to unmute/untimeout someone.\n"
    "  Examples: 'unmute @user', 'remove timeout from @user', 'untimeout @user'\n"
    "  REQUIRES an @mention.\n"
    "- ban: {user_id, reason} — user wants to ban someone.\n"
    "  Examples: 'ban @user', 'ban @user for spamming', 'ban them'\n"
    "  REQUIRES an @mention.\n"
    "- kick: {user_id, reason} — user wants to kick someone.\n"
    "  Examples: 'kick @user', 'kick @user for being toxic'\n"
    "  REQUIRES an @mention.\n"
    "- warn: {user_id, reason} — user wants to warn someone.\n"
    "  Examples: 'warn @user', 'warn @user for spam', 'give @user a warning'\n"
    "  REQUIRES an @mention.\n"
    "- warn_clear: {user_id} — clear all warnings for a user. REQUIRES an @mention.\n"
    "- warn_list: {user_id} — list warnings for a user. REQUIRES an @mention.\n"
    "- purge: {amount} — user wants to delete messages.\n"
    "  Examples: 'purge 10', 'delete 50 messages', 'clear chat'\n"
    "- lock: {} — user wants to lock a channel.\n"
    "  Examples: 'lock', 'lock this channel', 'lock the channel'\n"
    "- unlock: {} — user wants to unlock a channel.\n"
    "  Examples: 'unlock', 'unlock this channel'\n\n"
    "=== OTHER INTENTS ===\n"
    "- delete_message: {message_id} — delete a specific message by ID, or the "
    "message they are replying to. Look for 'delete message: 1234567890' or "
    "'delete this message'. If no ID visible, return {\"message_id\": null}.\n"
    "- slowmode: {seconds}\n"
    "- hide: {}\n"
    "- show: {}\n"
    "- nuke: {}\n"
    "- nick: {user_id, nickname} — change a user's nickname. REQUIRES an @mention.\n"
    "- role_add: {user_id, role}\n"
    "- role_remove: {user_id, role}\n"
    "- remind: {duration_seconds, reminder_text}\n"
    "- remind_cancel: {} — user wants to cancel a reminder. If they say "
    "'cancel all reminders', set params to {\"all\": true}. Otherwise leave "
    "params empty and the bot will list their reminders for them to choose.\n"
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
    "IMPORTANT: If a message contains a moderation keyword (mute, timeout, ban, kick, "
    "warn, purge, lock, unlock, unmute) AND an @mention, it is ALWAYS a moderation "
    "intent, never chat. Only classify as 'chat' if no moderation keyword is present "
    "or if the user is asking a question ABOUT moderation (like 'can you mute someone?' "
    "or 'what does mute do?'). If a moderation keyword appears with NO @mention of a "
    "target (e.g. 'warn diva'), return 'chat' — the bot cannot reliably identify who "
    "'diva' is without a mention.\n\n"
    "NOTE: 'poll' intent has been removed. If a user talks about polls, voting, "
    "or poll results, return 'chat' — the AI handles it conversationally."
)

KNOWN_INTENTS = {
    'ban', 'kick', 'mute', 'timeout', 'unmute', 'purge',
    'warn', 'warn_clear', 'warn_list', 'delete_message',
    'slowmode', 'lock', 'unlock',
    'hide', 'show', 'nuke', 'nick', 'role_add', 'role_remove',
    'remind', 'remind_cancel', 'serverinfo', 'ping', 'botinfo', 'uptime', 'whois', 'avatar',
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


_DURATION_UNITS = {
    's': 1, 'sec': 1, 'secs': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'mins': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hrs': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
}


def _parse_duration_to_seconds(raw):
    """FIX (mute duration) — models sometimes return duration as a string like
    '1m', '5 min', '2h', '1d', '90s', or '10 minutes' instead of raw seconds.
    Convert any of those into seconds. Plain ints pass through unchanged.
    Returns None if nothing parseable is found."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip().lower()
    if not s:
        return None
    import re as _re
    total = 0
    matched = False
    for num, unit in _re.findall(
            r'(\d+)\s*(s|secs?|seconds?|m|mins?|minutes?|h|hrs?|hours?|d|days?)(?![a-z])',
            s):
        total += int(num) * _DURATION_UNITS[unit]
        matched = True
    if matched and total > 0:
        return total
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
        elif k in ('duration', 'duration_seconds'):
            # FIX (mute duration) — normalize the key to 'duration_seconds' so
            # the executor always reads one canonical key, and convert
            # '1m'/'10 minutes' style strings into seconds.
            cleaned['duration_seconds'] = _parse_duration_to_seconds(v)
        elif k in ('amount', 'sides', 'seconds', 'message_id'):
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


# ─── FIX 2 — deterministic (regex) moderation intent detection ──
#
# Runs BEFORE the AI intent parser so moderation commands with an
# @mention never depend on the model classifying them correctly.
# Order matters: unmute must be checked before mute/timeout, and
# lockdown before lock (the \b word boundaries already prevent most
# substring collisions, but the ordering keeps it bulletproof).
MOD_PATTERNS = [
    (r'\bunmute\b|\buntimeout\b|\bremove timeout\b', 'unmute'),
    (r'\b(?:mute|timeout)\b', 'timeout'),
    (r'\bban\b', 'ban'),
    (r'\bkick\b', 'kick'),
    (r'\bwarn(?:ing)?\b', 'warn'),
    (r'\bpurge\b|\bclear\s+\d+\s+messages?\b|\bdelete\s+\d+\s+messages?\b', 'purge'),
    (r'\blockdown\b', 'lockdown'),
    (r'\block\b', 'lock'),
    (r'\bunlock\b', 'unlock'),
    (r'\bslowmode\b', 'slowmode'),
    (r'\bnuke\b', 'nuke'),
]


def deterministic_mod_intent(content: str, mention_count: int = 0) -> dict | None:
    """
    Detect moderation intent via regex before the AI parser.
    Returns {"intent": ..., "params": {...}} or None.

    Deliberately conservative:
    - questions ABOUT moderation ("can you mute someone?", "what does
      mute do?") never trigger — they fall through to the AI parser;
    - 'unmute' wins over 'mute', 'lockdown' over 'lock' (pattern order);
    - word boundaries keep tense/compound words safe ("muted",
      "banned", "unlocked" do not match).
    """
    content_lower = content.lower().strip()
    if not content_lower:
        return None

    # Question phrases that should NOT trigger mod intent
    question_phrases = [
        'can you', 'how do', 'what is', 'what does',
        'what are', 'how does', 'why does', 'tell me about',
        'what do you', 'do you know'
    ]

    # If it's a question ABOUT moderation, don't trigger
    for qp in question_phrases:
        if content_lower.startswith(qp) or f'{qp} ' in content_lower:
            return None

    for pattern, intent in MOD_PATTERNS:
        match = re.search(pattern, content_lower)
        if match:
            params = {}

            # Extract target user from mentions if provided
            if mention_count > 0:
                params['user_id'] = None  # executor uses message.mentions

            # Extract duration
            dur_match = re.search(
                r'(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)',
                content_lower
            )
            if dur_match:
                amount = float(dur_match.group(1))
                unit = dur_match.group(2).lower()
                if unit.startswith('m'):
                    params['duration_seconds'] = int(amount * 60)
                elif unit.startswith('h'):
                    params['duration_seconds'] = int(amount * 3600)
                elif unit.startswith('d'):
                    params['duration_seconds'] = int(amount * 86400)

            # Extract amount for purge
            if intent == 'purge':
                amt_match = re.search(r'(\d+)', content_lower)
                if amt_match:
                    params['amount'] = int(amt_match.group(1))

            # Extract slowmode seconds
            if intent == 'slowmode':
                sm_match = re.search(r'(\d+)', content_lower)
                if sm_match:
                    params['seconds'] = int(sm_match.group(1))

            # Extract reason (everything after "for " or "reason: ")
            reason_match = re.search(
                r'(?:for|reason[:\s])\s+(.+?)(?:\s+for\s+\d|\s+\d+\s*(?:m|h|d|min|hour|day)|$)',
                content_lower
            )
            if reason_match and reason_match.group(1):
                # Don't capture duration as reason
                reason = reason_match.group(1).strip()
                if not re.match(r'^\d+\s*(m|h|d|min|hour|day)', reason):
                    params['reason'] = reason

            return {"intent": intent, "params": params}

    return None


# ─── FIX 1 — deterministic utility intent detection ──
#
# Root cause of "@aurelia snipe" answering "sniper's a solid pick": the
# AI-chat fast-path (is_obvious_chat in cogs/ai_chat.py) ran BEFORE any
# intent parsing and short-circuited every short message without a
# moderation keyword straight to the chat model. Utility commands were
# never matched.
#
# parse_fast_intent() is the deterministic counterpart of parse_intent():
# regex ONLY, zero Groq calls, zero latency. It runs FIRST in the mention
# handler, so utility commands (and moderation commands, which keep their
# dedicated question-guarded detector) never depend on the model.
UTILITY_PATTERNS = [
    # (regex, intent) — first match wins. Word boundaries keep tense and
    # compound words safe ("sniper", "rolled", "trolled" don't match).
    (r'\bsnipe\b', 'snipe'),
    (r'\bflip\b', 'flip'),
    (r'\broll\b', 'roll'),
    (r'\bjoke\b', 'joke'),
    (r'\bmeme\b', 'meme'),
    # weather: bare command ("weather") OR a city phrase
    # ("weather in tokyo") — conversational mentions like "tell me about
    # the weather phenomenon known as rain" must NOT trigger
    (r'^\s*(?:weather|forecast)\b\s*$|\b(?:weather|forecast)\s+(?:in|at|for|of)\s+\S', 'weather'),
    (r'\bavatar\b|\bpfp\b', 'avatar'),
    (r'\bwhois\b|\buserinfo\b', 'whois'),
    (r'\bserver\s?info\b|\bserver\s?stats\b', 'serverinfo'),
    (r'\bremind\b', 'remind'),
]


def parse_fast_intent(content: str, message=None) -> dict | None:
    """Deterministic regex-only parser. Returns intent dict or None.

    Contains ONLY the regex matching logic — never calls Groq. Covers the
    moderation intents (via deterministic_mod_intent, which keeps its
    question guards) plus the utility intents the AI-chat fast-path used
    to swallow. Returns {"intent": ..., "params": {...}} or None when no
    pattern matches.
    """
    if not content or not content.strip():
        return None

    mention_count = 0
    if message is not None:
        try:
            mention_count = len(message.mentions or [])
        except Exception:
            mention_count = 0

    # moderation intents keep their dedicated (question-guarded) detector
    mod = deterministic_mod_intent(content, mention_count)
    if mod:
        return mod

    content_lower = content.lower().strip()

    for pattern, intent in UTILITY_PATTERNS:
        if not re.search(pattern, content_lower):
            continue

        params = {}
        if intent == 'snipe':
            m = re.search(r'\bsnipe\s+(\d+)', content_lower)
            if m and int(m.group(1)) >= 1:
                params['index'] = int(m.group(1))

        elif intent == 'roll':
            m = re.search(r'\broll\s+(?:a\s+)?(?:d\s*)?(\d+)', content_lower)
            if m and int(m.group(1)) >= 2:
                params['sides'] = min(int(m.group(1)), 1000)

        elif intent == 'weather':
            m = re.search(
                r'\b(?:weather|forecast)\s+(?:in|at|for|of)\s+(.+)',
                content_lower)
            if m:
                city = m.group(1).strip().strip('?.!')
                if city:
                    params['city'] = city[:80]

        elif intent == 'remind':
            # "remind me in 10 minutes to drink water"
            dur = re.search(
                r'\b(?:in|after)\s+(\d+(?:\.\d+)?)\s*'
                r'(s|secs?|seconds?|m|mins?|minutes?|h|hrs?|hours?|d|days?)'
                r'(?![a-z])',
                content_lower)
            if dur:
                mult = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[dur.group(2)[0]]
                params['duration_seconds'] = int(float(dur.group(1)) * mult)
            txt = re.search(r'\bto\s+(.+)', content_lower)
            if txt:
                reminder_text = txt.group(1).strip().strip('?.!')
                if reminder_text:
                    params['reminder_text'] = reminder_text[:500]

        return {"intent": intent, "params": params}

    return None


async def parse_intent(message_content: str, ai_handler) -> dict:
    fallback = {"intent": "chat", "params": {}}
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            import logging as _log
            _log.getLogger('cyn.intent').error("[INTENT_PARSER] GROQ_API_KEY not set")
            return fallback

        import logging as _log
        # FIX 6 — demote per-message intent parser logs from INFO to DEBUG
        # so they don't spam Render logs on every @mention / prefix command.
        _log.getLogger('cyn.intent').debug(f"[INTENT_PARSER] calling call_ai_fast for: {message_content[:80]}")

        raw = await call_ai_fast([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": message_content}
        ], max_tokens=100)

        _log.getLogger('cyn.intent').debug(f"[INTENT_PARSER] raw response: {raw[:100] if raw else 'NONE'}")

        if not raw or "something broke" in raw:
            _log.getLogger('cyn.intent').warning(f"[INTENT_PARSER] got error response: {raw[:100] if raw else 'NONE'}")
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
