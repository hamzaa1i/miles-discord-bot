"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with llama-3.3-70b-versatile for
high quality responses and llama-3.1-8b-instant for fast short responses.
"""
import os
import time
import logging
from groq import AsyncGroq

logger = logging.getLogger('cyn.ai')

_client = None

# Valid Groq model names (used for validation logging)
VALID_MODELS = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}

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


async def call_ai(
    messages: list,
    model: str = "llama-3.3-70b-versatile",
    max_tokens: int = 300,
    temperature: float = 0.9
) -> str:
    start = time.time()
    try:
        # Validate model name
        if model not in VALID_MODELS:
            logger.warning(f"[AI] unknown model '{model}', falling back to llama-3.3-70b-versatile")
            model = "llama-3.3-70b-versatile"

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
        result = response.choices[0].message.content.strip()
        elapsed = time.time() - start
        logger.info(f"[GROQ] model={model} tokens={max_tokens} "
                    f"time={elapsed:.2f}s messages={len(clean_messages)}")
        return result

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[GROQ ERROR] {type(e).__name__}: {e} time={elapsed:.2f}s")
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
    return await call_ai(
        messages,
        model="llama-3.1-8b-instant",
        max_tokens=max_tokens,
        temperature=0.85
    )
