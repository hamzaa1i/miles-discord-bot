"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with moonshotai/kimi-k2-instruct-0905 for
high quality chat/reasoning and gemma2-9b-it for fast intent parsing and
simple chat. Previous models (openai/gpt-oss-120b / openai/gpt-oss-20b)
were prone to returning EMPTY content (tool_calls / reasoning_content
fields) and have been replaced.

FIX 2 — Robust empty-response handling: if the model returns tool_calls
or reasoning_content instead of plain content, we fall back gracefully
instead of sending "NONE" to Discord.
"""
import os
import time
import logging
from groq import AsyncGroq

logger = logging.getLogger('cyn.ai')

_client = None

# ─── Model constants ────────────────────────────────────────────
# FIX 1 — Switched from openai/gpt-oss-120b (empty replies) and
# openai/gpt-oss-20b (unstable for chat) to proven-stable models.
#
#   MOONSHOT_K2  — primary chat/reasoning model (kimi-k2)
#   QWEN_32B     — fallback if kimi-k2 is rate-limited or unavailable
#   GEMMA_9B     — fast model for intent parsing and simple short chat
#
# Both kimi-k2 and gemma2-9b-it return plain content in
# `choices[0].message.content`, which fixes the empty-response bug.
MOONSHOT_K2 = "moonshotai/kimi-k2-instruct-0905"
QWEN_32B = "qwen/qwen3-32b"
GEMMA_9B = "gemma2-9b-it"

# Valid Groq model names (used for validation logging)
VALID_MODELS = {MOONSHOT_K2, QWEN_32B, GEMMA_9B}

# Default primary chat model (used when caller doesn't specify)
DEFAULT_MODEL = MOONSHOT_K2
# Default fast model (used by call_ai_fast)
DEFAULT_FAST_MODEL = GEMMA_9B


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        _client = AsyncGroq(api_key=api_key)
    return _client


def _validate_messages(messages: list) -> list:
    """Sanitize the messages list before sending to Groq.

    Returns a clean copy where:
    - empty/None content is replaced with a single space
    - overly long content is truncated to 32000 chars
    - role is defaulted to 'user' if missing
    """
    clean_messages = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            logger.warning(f"[AI] msg[{i}] is not a dict, skipping")
            continue
        content = msg.get("content", "")
        if content is None:
            logger.warning(f"[AI] None content at index {i}, replacing with space")
            content = " "
        content = str(content)
        if not content.strip():
            logger.warning(f"[AI] empty content at index {i}, replacing with space")
            content = " "
        if len(content) > 32000:
            content = content[:32000]
            logger.warning(f"[AI] truncated message {i} to 32000 chars")
        role = msg.get("role", "user")
        if role not in ("system", "user", "assistant", "tool"):
            logger.warning(f"[AI] unknown role '{role}' at index {i}, defaulting to 'user'")
            role = "user"
        clean_messages.append({"role": role, "content": content})
    return clean_messages


def _extract_content(msg) -> str:
    """FIX 2 — Robustly extract text from a Groq chat completion message.

    Some reasoning models (gpt-oss, kimi-k2 in reasoning mode) put the
    actual text inside `reasoning_content` instead of `content`. Some
    models return `tool_calls` instead of any text at all. We try every
    field in order and never return an empty string.
    """
    # 1. Primary content field
    content = (getattr(msg, "content", None) or "").strip()
    if content:
        return content

    # 2. Reasoning models sometimes hide text in reasoning_content
    reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
    if reasoning:
        return reasoning

    # 3. If the model tried to invoke tools instead of replying, don't
    #    send an empty message — give the user a soft fallback.
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        return "hm, i'm not sure how to respond to that."

    # 4. Absolute last resort — never return None / empty to the caller
    return "..."


async def call_ai(
    messages: list,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 300,
    temperature: float = 0.9
) -> str:
    start = time.time()
    clean_messages = []
    try:
        # Validate model name
        if model not in VALID_MODELS:
            logger.warning(f"[AI] unknown model '{model}', falling back to {DEFAULT_MODEL}")
            model = DEFAULT_MODEL

        # Validate max_tokens
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            logger.warning(f"[AI] invalid max_tokens={max_tokens}, defaulting to 300")
            max_tokens = 300
        if max_tokens > 32768:
            logger.warning(f"[AI] max_tokens={max_tokens} too large, capping to 32768")
            max_tokens = 32768

        # Validate temperature
        if not isinstance(temperature, (int, float)):
            logger.warning(f"[AI] invalid temperature={temperature}, defaulting to 0.9")
            temperature = 0.9
        if temperature < 0.0 or temperature > 2.0:
            logger.warning(f"[AI] temperature={temperature} out of range, clamping to 0.0-2.0")
            temperature = max(0.0, min(2.0, float(temperature)))

        # Validate messages list
        if not messages:
            logger.warning("[AI] empty messages list, skipping")
            return "something broke. try again."

        clean_messages = _validate_messages(messages)
        if not clean_messages:
            logger.warning("[AI] messages list had no valid entries after cleaning")
            return "something broke. try again."

        client = get_client()
        response = await client.chat.completions.create(
            model=model,
            messages=clean_messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # FIX 2 — Use robust content extraction so we NEVER send empty text
        result = _extract_content(response.choices[0].message)

        elapsed = time.time() - start
        logger.info(f"[GROQ] model={model} tokens={max_tokens} "
                    f"time={elapsed:.2f}s messages={len(clean_messages)} "
                    f"resp_len={len(result)}")

        # PHASE 1D — Track metrics for /health endpoint
        try:
            import keep_alive as _kl
            _kl.total_ai_calls += 1
            _kl.recent_response_times.append(elapsed * 1000)
            if len(_kl.recent_response_times) > 100:
                _kl.recent_response_times.pop(0)
        except Exception:
            pass

        return result

    except Exception as e:
        elapsed = time.time() - start
        error_str = str(e)

        # DIAGNOSTIC — Log ALL errors with full traceback
        logger.error(f"[GROQ CRITICAL] {type(e).__name__}: {e} time={elapsed:.2f}s")
        import traceback
        traceback.print_exc()

        # FIX 1 — Rate limit on primary (kimi-k2) → try qwen3-32b fallback
        if "429" in error_str and model == MOONSHOT_K2:
            logger.warning(f"[GROQ] {MOONSHOT_K2} rate limited, trying {QWEN_32B} fallback")
            try:
                client = get_client()
                response = await client.chat.completions.create(
                    model=QWEN_32B,
                    messages=clean_messages if clean_messages else _validate_messages(messages),
                    max_tokens=min(max_tokens, 200),
                    temperature=temperature
                )
                result = _extract_content(response.choices[0].message)
                logger.info(f"[GROQ FALLBACK] {QWEN_32B} responded successfully (len={len(result)})")
                return result
            except Exception as e2:
                logger.error(f"[GROQ FALLBACK CRITICAL] {type(e2).__name__}: {e2}")
                traceback.print_exc()
                if "429" in str(e2):
                    import re
                    wait_match = re.search(
                        r'try again in (\d+m\d+s|\d+\.\d+s|\d+s)',
                        str(e2)
                    )
                    wait_str = wait_match.group(1) if wait_match else "a few minutes"
                    logger.error(f"[GROQ] Both chat models rate limited. Wait: {wait_str}")
                    return f"i'm at capacity right now. try again in {wait_str}."
                logger.error(f"[GROQ] {QWEN_32B} fallback failed: {e2}")

        # Extract wait time for any 429
        if "429" in error_str:
            import re
            wait_match = re.search(
                r'try again in (\d+m[\d.]+s|\d+\.\d+s|\d+s)',
                error_str
            )
            wait_str = wait_match.group(1) if wait_match else "a few minutes"
            return f"i'm at capacity right now. try again in {wait_str}."

        logger.error(f"[GROQ ERROR] model={model} max_tokens={max_tokens} temp={temperature}")
        try:
            logger.error(f"[GROQ ERROR] messages count={len(messages)}")
            for i, m in enumerate(messages):
                if isinstance(m, dict):
                    content_preview = str(m.get('content', 'NONE'))[:100]
                    logger.error(f"[GROQ ERROR] msg[{i}] role={m.get('role')} content={content_preview}")
                else:
                    logger.error(f"[GROQ ERROR] msg[{i}] NOT_A_DICT: {str(m)[:100]}")
        except Exception as log_err:
            logger.error(f"[GROQ ERROR] failed to log messages: {log_err}")

        return "something broke on my end. try again."


async def call_ai_fast(
    messages: list,
    max_tokens: int = 150
) -> str:
    """Fast path: uses gemma2-9b-it for intent parsing / simple short chat.

    gemma2-9b-it is a proven stable model for JSON output and short
    responses, and it always returns plain content (no tool_calls).
    """
    return await call_ai(
        messages,
        model=GEMMA_9B,
        max_tokens=max_tokens,
        temperature=0.85
    )


# PHASE 3C — Smart model routing based on message content + intent
def pick_model(message_content: str, intent: str = "chat") -> str:
    """Pick the right Groq model based on complexity.

    Returns MOONSHOT_K2 (kimi-k2) for complex questions / reasoning,
    GEMMA_9B for simple short chat and intent-based mod commands.
    """
    # Intent-based routing: mod/utility commands use fast model
    if intent in ("warn", "ban", "kick", "mute", "timeout", "unmute",
                  "purge", "lock", "unlock", "slowmode", "remind",
                  "weather", "flip", "roll", "joke", "fact", "remind_cancel",
                  "warn_clear", "delete_message", "nick", "serverinfo",
                  "ping", "botinfo", "uptime", "whois", "avatar"):
        return GEMMA_9B

    # Content-based routing for chat
    content_lower = message_content.lower()

    # Technical/code questions → big model
    technical_keywords = ["code", "debug", "error", "function", "class",
                          "algorithm", "python", "javascript", "sql",
                          "explain", "how does", "what is", "why does",
                          "difference between", "compare", "analyze"]
    if any(kw in content_lower for kw in technical_keywords):
        return MOONSHOT_K2

    # Very short messages → fast model
    words = message_content.split()
    if len(words) <= 5:
        return GEMMA_9B

    # Default to kimi-k2 for longer casual chat (richer responses)
    return MOONSHOT_K2
