"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with three stable models as of
late August 2026:

  MODEL_CHAT     = "llama-3.3-70b-versatile"   (primary chat / reasoning)
  MODEL_FAST     = "llama-3.1-8b-instant"      (intent parsing, short chat)
  MODEL_FALLBACK = "qwen/qwen3-32b"            (fallback if primary fails)

Decommissioned / forbidden models (DO NOT USE):
  - gemma2-9b-it          (decommissioned by Groq → 400 error)
  - openai/gpt-oss-20b    (returns empty content via tool_calls)
  - openai/gpt-oss-120b   (returns empty content via tool_calls)
  - moonshotai/kimi-k2-instruct-0905 (was unreliable in practice)

FIX 2 — Robust empty-response handling: if the model returns tool_calls
or reasoning_content instead of plain content, we fall back gracefully
instead of sending "NONE" to Discord.

FIX 2 (extended) — If a model fails with a 400 or 404 error (e.g.
decommissioned model), we automatically retry with MODEL_FALLBACK.
"""
import os
import re
import time
import logging
from groq import AsyncGroq

logger = logging.getLogger('cyn.ai')

_client = None

# ─── Model constants ────────────────────────────────────────────
# FIX 1 — Switched to currently-live Groq models.
#
#   MODEL_CHAT     — primary chat/reasoning model (llama-3.3-70b-versatile)
#   MODEL_FAST     — fast model for intent parsing / simple short chat
#                    (llama-3.1-8b-instant; proven stable for JSON output)
#   MODEL_FALLBACK — fallback if MODEL_CHAT is rate-limited OR if a model
#                    returns 400 / 404 (decommissioned / not found)
#
# All three models return plain text in `choices[0].message.content`,
# which fixes the empty-response bug seen with gpt-oss-* models.
MODEL_CHAT = "llama-3.3-70b-versatile"
MODEL_FAST = "llama-3.1-8b-instant"
MODEL_FALLBACK = "qwen/qwen3-32b"

# Valid Groq model names (used for validation logging)
VALID_MODELS = {MODEL_CHAT, MODEL_FAST, MODEL_FALLBACK}

# Default primary chat model (used when caller doesn't specify)
DEFAULT_MODEL = MODEL_CHAT
# Default fast model (used by call_ai_fast)
DEFAULT_FAST_MODEL = MODEL_FAST

# Error signatures that indicate "model unavailable / decommissioned"
# — these should trigger an automatic retry with MODEL_FALLBACK.
_MODEL_UNAVAILABLE_SIGNATURES = (
    "400", "404", "model_not_found", "model not found",
    "does not exist", "decommissioned", "not_available",
)


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


def _extract_content(response) -> str:
    """FIX 2 — Robustly extract text from a Groq chat completion response.

    Some reasoning models (gpt-oss, kimi-k2 in reasoning mode) put the
    actual text inside `reasoning_content` instead of `content`. Some
    models return `tool_calls` instead of any text at all. We try every
    field in order and NEVER return an empty string.
    """
    try:
        msg = response.choices[0].message
        # 1. Primary content field
        content = (getattr(msg, "content", None) or "").strip()
        if content:
            return content

        # 2. Reasoning models sometimes hide text in reasoning_content
        reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
        if reasoning:
            return reasoning

        # 3. If the model tried to invoke tools instead of replying,
        #    give the user a soft fallback rather than empty text.
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            return "hmm, let me think about that differently."

        # 4. Absolute last resort — never return None / empty to the caller
        return "..."
    except Exception as e:
        logger.error(f"[_extract_content] {type(e).__name__}: {e}")
        return "..."


def _is_model_unavailable_error(error_str: str) -> bool:
    """FIX 2 — Return True if the error suggests the model itself is
    unavailable (400 Bad Request, 404 Not Found, decommissioned, etc.).
    In that case we should retry with MODEL_FALLBACK instead of giving up.
    """
    err_lower = (error_str or "").lower()
    return any(sig in err_lower for sig in _MODEL_UNAVAILABLE_SIGNATURES)


async def _call_groq(model: str, messages: list, max_tokens: int,
                     temperature: float) -> str:
    """Single Groq API call with content extraction. Raises on error."""
    client = get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return _extract_content(response)


async def call_ai(
    messages: list,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 300,
    temperature: float = 0.9
) -> str:
    """Call Groq with automatic fallback.

    Failure chain:
      1. Try the requested `model` (defaults to MODEL_CHAT).
      2. If it returns 400 / 404 / "model not found" → retry with MODEL_FALLBACK.
      3. If MODEL_CHAT was rate-limited (429) → retry with MODEL_FALLBACK.
      4. If MODEL_FALLBACK is also rate-limited → return a "try again later" msg.
      5. Anything else → return "something broke on my end. try again."
    """
    start = time.time()
    clean_messages = []
    try:
        # Validate model name — fall back to MODEL_CHAT if unknown
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

        # ── Attempt 1 — requested model ───────────────────────────
        try:
            result = await _call_groq(model, clean_messages, max_tokens, temperature)
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
            error_str = str(e)
            # If the model itself is unavailable (400/404), retry with fallback.
            # If it's a 429 rate limit on MODEL_CHAT, also retry with fallback.
            should_retry = (
                _is_model_unavailable_error(error_str)
                or ("429" in error_str and model == MODEL_CHAT)
            )
            if not should_retry:
                # Re-raise so the outer except can handle it
                raise

            # ── Attempt 2 — MODEL_FALLBACK ────────────────────────
            logger.warning(
                f"[GROQ] {model} failed ({type(e).__name__}); "
                f"retrying with {MODEL_FALLBACK}"
            )
            try:
                result = await _call_groq(
                    MODEL_FALLBACK, clean_messages,
                    max_tokens=min(max_tokens, 400),
                    temperature=temperature,
                )
                elapsed = time.time() - start
                logger.info(f"[GROQ FALLBACK] {MODEL_FALLBACK} responded "
                            f"(len={len(result)} time={elapsed:.2f}s)")
                # Track metrics
                try:
                    import keep_alive as _kl
                    _kl.total_ai_calls += 1
                    _kl.recent_response_times.append(elapsed * 1000)
                    if len(_kl.recent_response_times) > 100:
                        _kl.recent_response_times.pop(0)
                except Exception:
                    pass
                return result
            except Exception as e2:
                # If fallback also fails, fall through to the 429 handler
                # below or the generic error handler.
                e = e2
                error_str = str(e2)
                raise

    except Exception as e:
        elapsed = time.time() - start
        error_str = str(e)

        # DIAGNOSTIC — Log ALL errors with full traceback
        logger.error(f"[GROQ CRITICAL] {type(e).__name__}: {e} time={elapsed:.2f}s")
        import traceback
        traceback.print_exc()

        # Both models rate-limited
        if "429" in error_str:
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
    """Fast path: uses llama-3.1-8b-instant for intent parsing / short chat.

    llama-3.1-8b-instant is a proven stable model for JSON output and
    short responses, and it always returns plain content (no tool_calls).
    """
    return await call_ai(
        messages,
        model=MODEL_FAST,
        max_tokens=max_tokens,
        temperature=0.85
    )


# PHASE 3C — Smart model routing based on message content + intent
def pick_model(message_content: str, intent: str = "chat") -> str:
    """Pick the right Groq model based on complexity.

    Returns MODEL_CHAT (llama-3.3-70b-versatile) for complex questions /
    reasoning, MODEL_FAST (llama-3.1-8b-instant) for simple short chat
    and intent-based mod/utility commands.
    """
    # Intent-based routing: mod/utility commands use fast model
    if intent in ("warn", "ban", "kick", "mute", "timeout", "unmute",
                  "purge", "lock", "unlock", "slowmode", "remind",
                  "weather", "flip", "roll", "joke", "fact", "remind_cancel",
                  "warn_clear", "delete_message", "nick", "serverinfo",
                  "ping", "botinfo", "uptime", "whois", "avatar"):
        return MODEL_FAST

    # Content-based routing for chat
    content_lower = message_content.lower()

    # Technical/code questions → big model
    technical_keywords = ["code", "debug", "error", "function", "class",
                          "algorithm", "python", "javascript", "sql",
                          "explain", "how does", "what is", "why does",
                          "difference between", "compare", "analyze"]
    if any(kw in content_lower for kw in technical_keywords):
        return MODEL_CHAT

    # Very short messages → fast model
    words = message_content.split()
    if len(words) <= 5:
        return MODEL_FAST

    # Default to llama-3.3-70b for longer casual chat (richer responses)
    return MODEL_CHAT
