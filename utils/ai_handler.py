"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with verified-live models as of
late August 2026:

  MODEL_CHAT     = "qwen/qwen3.6-27b"        (primary casual chat)
  MODEL_FAST     = "openai/gpt-oss-20b"      (intent parsing, short chat)
  MODEL_FALLBACK = "qwen/qwen3.8-27b"        (fallback if primary fails)
  MODEL_REASONING = "openai/gpt-oss-120b"    (complex / code / debug queries)

Decommissioned / forbidden models (DO NOT USE — return 404/400):
  - llama-3.1-8b-instant
  - llama-3.3-70b-versatile
  - llama-3.1-70b-versatile
  - gemma2-9b-it
  - moonshotai/kimi-k2-instruct-0905
  - qwen/qwen3-32b (replaced by qwen3.6-27b / qwen3.8-27b)

FIX 2 — Robust empty-response handling. The bot was receiving HTTP 200 OK
but logging `response received: NONE` because:
  (a) max_tokens was too low (100) — reasoning models used all 100 tokens
      on internal reasoning headers, leaving 0 tokens for visible content.
  (b) Some models put text in `reasoning_content` instead of `content`,
      or return `tool_calls` instead of any text.

Both are fixed: max_tokens has a 300-token floor, and `_extract_content`
checks every possible field before falling back to a natural message.

FIX 2 (extended) — If a model fails with 400 / 404 (decommissioned),
we automatically retry with MODEL_FALLBACK.

FIX (empty content / "i'm here. what's on your mind?") — Groq reasoning
models (qwen3.6-27b, gpt-oss-20b/120b) emit their chain-of-thought in the
`message.reasoning` field (NOT `reasoning_content`, which is the DeepSeek
convention _extract_content originally checked). When the reasoning consumes
the whole max_tokens budget, `content` comes back as an empty string and the
extractor returned the "i'm here" fallback — which then leaked into the
conversation history and starved every downstream feature (intent parsing,
fact extraction, automod classification, proactive lines all use this path).
Fix: (a) check `reasoning` as well as `reasoning_content`; (b) if the first
call still returns no visible content, retry ONCE with a doubled max_tokens
budget so the model has room to finish reasoning and emit real text.

FIX (live P0) — Untagged chain-of-thought preambles leaked into user
messages in live testing ("We need to output two lines: first line is the
choice ..." in /pick; "We have a conversation. The user says ... The
developer says: ..." in @aurelia chat). _strip_cot_preambles() now strips
LEADING meta-reasoning paragraphs from every response and, when the
reasoning and the real answer share one block with no blank line, extracts
the final concise answer.
"""
import os
import re
import time
import asyncio
import logging
from groq import AsyncGroq

logger = logging.getLogger('cyn.ai')

_client = None

# ─── Model constants ────────────────────────────────────────────
# FIX 1 — Switched to currently-live Groq models (verified Aug 2026).
#
#   MODEL_CHAT      — primary chat model for casual conversation
#                     (qwen/qwen3.6-27b)
#   MODEL_FAST      — fast model for intent parsing / short chat
#                     (openai/gpt-oss-20b)
#   MODEL_FALLBACK  — fallback if MODEL_CHAT is rate-limited OR if a model
#                     returns 400 / 404 (decommissioned / not found)
#                     (qwen/qwen3.8-27b)
#   MODEL_REASONING — heavy reasoning model for code/debug/complex queries
#                     (openai/gpt-oss-120b)
#
# All four models return plain text in `choices[0].message.content` when
# given enough max_tokens (≥300), which fixes the empty-response bug.
MODEL_CHAT = "qwen/qwen3.6-27b"
MODEL_FAST = "openai/gpt-oss-20b"
MODEL_FALLBACK = "qwen/qwen3.8-27b"
MODEL_REASONING = "openai/gpt-oss-120b"

# Valid Groq model names (used for validation logging)
VALID_MODELS = {MODEL_CHAT, MODEL_FAST, MODEL_FALLBACK, MODEL_REASONING}

# Default primary chat model (used when caller doesn't specify)
DEFAULT_MODEL = MODEL_CHAT
# Default fast model (used by call_ai_fast)
DEFAULT_FAST_MODEL = MODEL_FAST

# Minimum token floor. Reasoning models (gpt-oss-120b, qwen3.6)
# spend tokens on internal reasoning headers before emitting visible
# content. With max_tokens=100 the model would burn all 100 tokens on
# reasoning and return an empty content string. 300 is the safe floor.
MIN_MAX_TOKENS = 300

# PHASE 1 / PART 2.2 — how many times call_ai retries (with backoff)
# after a rate limit (429) or a Groq server error (502/503/504).
MAX_RETRIES = 3

# FIX (empty content) — the canned reply returned when a completion has no
# visible text at all. call_ai() detects this marker and retries once with a
# doubled token budget before giving up on it.
_EMPTY_CONTENT_FALLBACK = "i'm here. what's on your mind?"

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


# ─── FIX 1 (live P0) — untagged CoT / meta-reasoning leak stripping ─────
#
# Live testing (Aug 2026) caught qwen3.6-27b / gpt-oss-20b leaking raw
# chain-of-thought into user-visible messages with NO XML tags at all:
#   /pick:        "We need to output two lines: first line is the choice ..."
#   @aurelia hi:  "We have a conversation. The user says 'volc: hi' twice.
#                 The developer says: note: your last two responses began ..."
# The starters below essentially never begin a legitimate casual reply, so:
#   1. LEADING paragraphs that start with one are stripped (repeatedly —
#      some models emit several reasoning paragraphs before the answer);
#   2. if the reasoning and the real answer share a single block with no
#      blank-line separator, the final concise answer (last paragraph, or
#      last line) is extracted instead.
_COT_STARTERS = (
    "we need to",
    "we have a conversation",
    "the user says",
    "the developer says",
    "let's choose",
    "let me choose",
    "let's pick",
    "let me think",
    "thinking process",
    "here is the response",
    "here's the response",
    "here's a thinking process",
    "here's my thinking process",
)

_COT_PREAMBLE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _COT_STARTERS) + r")"
    r".*?\n\n+",
    flags=re.DOTALL | re.IGNORECASE,
)

_COT_STARTER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _COT_STARTERS) + r")\b",
    flags=re.IGNORECASE,
)


def _strip_cot_preambles(content: str) -> str:
    """FIX 1 (live P0) — remove untagged reasoning preambles from output.

    Runs inside _extract_content on EVERY AI response, so every caller
    (chat, intent parsing, /pick, /vibe, automod, fact extraction, ...)
    is protected. Legitimate replies that merely MENTION these phrases
    mid-text are untouched — only LEADING paragraphs are stripped.
    """
    if not content:
        return content

    # Upstream tag removal can leave leading newlines ("</think>\n\nhi")
    # which would defeat the ^-anchored patterns below — normalize first.
    content = content.strip()

    # 1. Drop leading reasoning paragraphs (blank-line separated).
    stripped_any = False
    for _ in range(5):
        new = _COT_PREAMBLE_RE.sub("", content, count=1)
        if new == content:
            break
        content = new
        stripped_any = True

    if not _COT_STARTER_RE.match(content):
        return content.strip()

    # 2. Reasoning + answer in ONE block (no blank line): keep only the
    #    final concise answer — last non-empty paragraph, else last line.
    paragraphs = [p for p in (s.strip() for s in content.split("\n\n")) if p]
    if len(paragraphs) > 1:
        # every remaining paragraph is starter-led -> pure reasoning with
        # no real answer at all -> discard everything (the caller-side
        # empty-content fallback + doubled-token retry then kick in)
        if all(_COT_STARTER_RE.match(p) for p in paragraphs):
            return ""
        content = paragraphs[-1]
    else:
        # A single starter-led paragraph that survived the loop: if earlier
        # reasoning paragraphs were stripped above, this tail is reasoning
        # too -> discard. If nothing was stripped, it may be a legitimate
        # reply ("let me think about that ♡") -> keep, but fall back to
        # the last line when the block spans several lines.
        if stripped_any:
            return ""
        lines = [l for l in (s.strip() for s in content.splitlines()) if l]
        if len(lines) > 1:
            content = lines[-1]

    return content.strip()


def _extract_content(response) -> str:
    """FIX 2 — Robustly extract text from a Groq chat completion response.

    Reasoning models (gpt-oss-20b, gpt-oss-120b, qwen3.6) sometimes put
    the actual text inside `reasoning_content` instead of `content`, or
    wrap their internal reasoning in <think>...</think> tags. Some models
    return `tool_calls` instead of any text at all. We try every field in
    order, strip all reasoning tags, and NEVER return an empty string.

    FIX 1 — Strip <think>...</think> blocks, standalone "thinking" markers,
    and common reasoning-process preambles ("Here's a thinking process:",
    "Let me think..."). These were being sent raw to Discord and users saw
    the model's internal monologue.
    """
    try:
        if not response or not response.choices:
            return "something went wrong on my end."

        msg = response.choices[0].message

        # 1. Primary content field
        content = (getattr(msg, "content", None) or "").strip()

        # 2. Reasoning models sometimes hide text in reasoning_content
        #    (DeepSeek convention) or in `reasoning` (Groq's qwen3 / gpt-oss
        #    convention). Check BOTH — the field name differs by model family.
        if not content and hasattr(msg, 'reasoning_content') and msg.reasoning_content:
            content = (msg.reasoning_content or "").strip()
        if not content and hasattr(msg, 'reasoning') and msg.reasoning:
            content = (msg.reasoning or "").strip()

        # FIX 1 — Strip <think>...</think> blocks (including multi-line).
        # The gpt-oss-20b model outputs internal reasoning wrapped in
        # <think>...</think> tags. Without this, users see the raw
        # reasoning ("Here's a thinking process: Analyze User Input: ...").
        if content:
            content = re.sub(
                r'<think>.*?</think>',
                '',
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )
            content = re.sub(
                r'<thinking>.*?</thinking>',
                '',
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # If the model started a <think> block but never closed it,
            # strip from <think> to the end of the string.
            if '<think>' in content.lower():
                content = re.sub(
                    r'<think>.*',
                    '',
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                )
            if '<thinking>' in content.lower():
                content = re.sub(
                    r'<thinking>.*',
                    '',
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                )

            # FIX 1 (live P0) — strip untagged CoT / meta-reasoning
            # preambles ("We need to output two lines: ...", "We have a
            # conversation. The user says ...", "The developer says ...").
            # Subsumes the old "Here's a thinking process:" / "Let me
            # think" preamble strips and adds a no-blank-line fallback
            # that extracts the final concise answer.
            content = _strip_cot_preambles(content)

            content = content.strip()

        # 3. If the model tried to invoke tools instead of replying,
        #    give the user a soft fallback rather than empty text.
        if not content:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                return _EMPTY_CONTENT_FALLBACK

        # 4. Absolute last resort — never return None / empty to the caller
        if not content:
            return _EMPTY_CONTENT_FALLBACK

        # 5. Cap at 1900 chars for Discord's 2000-char message limit,
        #    leaving room for the "..." suffix.
        if len(content) > 1900:
            content = content[:1900] + "..."

        return content
    except Exception as e:
        logger.error(f"[_extract_content error] {type(e).__name__}: {e}")
        return "something went wrong on my end."


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
    temperature: float = 0.9,
    retry_count: int = 0,
) -> str:
    """Call Groq with automatic fallback AND retry-with-backoff.

    Failure chain:
      1. Try the requested `model` (defaults to MODEL_CHAT).
      2. If it returns 400 / 404 / "model not found" → retry with MODEL_FALLBACK.
      3. If MODEL_CHAT was rate-limited (429) → retry with MODEL_FALLBACK.
      4. PHASE 1 / PART 2.2 — if the whole call still failed with a rate
         limit, sleep (exponential 1s → 2s → 4s) and recurse, up to
         MAX_RETRIES (3) times. Server errors (502/503/504) retry every
         5s the same way.
      5. All retries exhausted or non-retryable → graceful error string
         (the caller-side check for _EMPTY_CONTENT_FALLBACK in
         cogs/ai_chat.py randomizes what the user sees).

    FIX 2 — `max_tokens` is floored at MIN_MAX_TOKENS (300) so reasoning
    models have enough budget to emit visible content after their internal
    reasoning headers.
    """
    start = time.time()
    clean_messages = []
    try:
        # Validate model name — fall back to MODEL_CHAT if unknown
        if model not in VALID_MODELS:
            logger.warning(f"[AI] unknown model '{model}', falling back to {DEFAULT_MODEL}")
            model = DEFAULT_MODEL

        # FIX 2 — Validate max_tokens with a 300-token floor.
        # Reasoning models (gpt-oss-120b, qwen3.6) burn tokens on internal
        # reasoning before emitting visible content. With max_tokens=100,
        # the model had 0 tokens left for the actual reply → empty string.
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            logger.warning(f"[AI] invalid max_tokens={max_tokens}, defaulting to {MIN_MAX_TOKENS}")
            max_tokens = MIN_MAX_TOKENS
        if max_tokens < MIN_MAX_TOKENS:
            logger.warning(
                f"[AI] max_tokens={max_tokens} too low for reasoning models; "
                f"raising to {MIN_MAX_TOKENS}"
            )
            max_tokens = MIN_MAX_TOKENS
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

            # FIX (empty content) — the model burned its whole token budget
            # on internal reasoning and emitted no visible text (the
            # _EMPTY_CONTENT_FALLBACK marker). Retry once with a doubled
            # budget so the reasoning AND the answer both fit.
            if result == _EMPTY_CONTENT_FALLBACK and max_tokens * 2 <= 32768:
                logger.warning(
                    f"[GROQ] {model} returned empty content at "
                    f"max_tokens={max_tokens} — retrying with {max_tokens * 2}"
                )
                try:
                    retry_result = await _call_groq(
                        model, clean_messages, max_tokens * 2, temperature
                    )
                    if retry_result and retry_result != _EMPTY_CONTENT_FALLBACK:
                        result = retry_result
                except Exception as retry_err:
                    # Retry is best-effort — keep the original fallback.
                    logger.warning(
                        f"[GROQ] empty-content retry failed: "
                        f"{type(retry_err).__name__}: {retry_err}"
                    )

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
                    max_tokens=max(max_tokens, MIN_MAX_TOKENS),
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
        error_lower = error_str.lower()

        # DIAGNOSTIC — Log ALL errors with full traceback
        logger.error(f"[GROQ CRITICAL] {type(e).__name__}: {e} time={elapsed:.2f}s")
        import traceback
        traceback.print_exc()

        # ── PART 2.2 — retry with exponential backoff on rate limits ──
        # 1s → 2s → 4s. ("rate" alone is too greedy — "generate" contains
        # it — so match the specific phrasings Groq actually returns.)
        _is_rate_limit = (
            "429" in error_lower
            or "rate limit" in error_lower
            or "rate_limit" in error_lower
            or "ratelimit" in error_lower
            or "too many requests" in error_lower
        )
        if _is_rate_limit and retry_count < MAX_RETRIES:
            wait_time = 2 ** retry_count  # 1s, 2s, 4s
            logger.warning(
                f"[AI] retry {retry_count + 1}/{MAX_RETRIES} for {model} "
                f"after 429, waiting {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            return await call_ai(
                messages, model, max_tokens, temperature, retry_count + 1
            )

        # ── PART 2.2 — retry Groq server errors (502/503/504) every 5s ──
        if (any(code in error_lower for code in ("503", "502", "504"))
                and retry_count < MAX_RETRIES):
            wait_time = 5
            logger.warning(
                f"[AI] retry {retry_count + 1}/{MAX_RETRIES} for {model} "
                f"after {error_str[:50]}, waiting {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            return await call_ai(
                messages, model, max_tokens, temperature, retry_count + 1
            )

        # Both models rate-limited AND backoff retries exhausted
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
    """Fast path: uses openai/gpt-oss-20b for intent parsing / short chat.

    FIX 2 — max_tokens is raised to MIN_MAX_TOKENS (300) inside call_ai()
    so reasoning-capable models always have enough budget to emit visible
    content. The 150 caller value is overridden to 300 for safety.
    """
    return await call_ai(
        messages,
        model=MODEL_FAST,
        max_tokens=max_tokens,
        temperature=0.85
    )


async def call_ai_reasoning(
    messages: list,
    max_tokens: int = 1000,
    temperature: float = 0.6
) -> str:
    """FIX 1.5 — heavy reasoning path: uses the BIG model
    (openai/gpt-oss-120b) for tasks that need real comprehension and
    structured output — channel recaps, deep digests, complex analysis.

    Distinct from call_ai_fast on purpose: summaries routed through the
    small chat model previously came back with the conversational
    "i'm here. what's on your mind?" fallback when the model didn't
    understand the task. The reasoning model gets a generous default
    token budget (1000) so its internal chain-of-thought can't starve
    the visible answer."""
    return await call_ai(
        messages,
        model=MODEL_REASONING,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# PHASE 3C — Smart model routing based on message content + intent
def pick_model(message_content: str, intent: str = "chat") -> str:
    """Pick the right Groq model based on complexity.

    Returns:
      MODEL_REASONING (openai/gpt-oss-120b) for complex questions / code /
      debugging queries.
      MODEL_CHAT (qwen/qwen3.6-27b) for general casual chat.
      MODEL_FAST (openai/gpt-oss-20b) for simple short chat and
      intent-based mod/utility commands.
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

    # Technical/code/debug questions → heavy reasoning model
    technical_keywords = ["code", "debug", "error", "function", "class",
                          "algorithm", "python", "javascript", "sql",
                          "explain", "how does", "what is", "why does",
                          "difference between", "compare", "analyze"]
    if any(kw in content_lower for kw in technical_keywords):
        return MODEL_REASONING

    # Very short messages → fast model
    words = message_content.split()
    if len(words) <= 5:
        return MODEL_FAST

    # Default to MODEL_CHAT for longer casual chat (richer responses)
    return MODEL_CHAT
