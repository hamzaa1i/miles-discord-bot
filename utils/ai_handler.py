"""
utils/ai_handler.py — PHASE N compatibility facade over the AI router.

HISTORY: this module used to BE the AI implementation — a Groq-only
client with inline retry loops. Phase N moved the engine to a
multi-provider architecture:

    utils/ai_config.py      one configuration layer (models, flags, budgets)
    utils/ai_types.py       profiles, failure categories, AIResult
    utils/ai_sanitize.py    the ONE output-sanitization pipeline
    ai_providers/*          provider transport adapters (no logic)
    utils/ai_router.py      the ONE failover owner (chains, breakers,
                            budgets, telemetry)

PUBLIC CALLING CONTRACT — PRESERVED (Phase N Part 1). Existing cogs were
NOT rewritten; these symbols keep their exact signatures and semantics:

    call_ai(messages, model=DEFAULT_MODEL, max_tokens, temperature,
            retry_count)        -> str
    call_ai_fast(messages, max_tokens=150, sensitive=False) -> str
    call_ai_reasoning(messages, max_tokens=1000, temperature=0.6) -> str
    pick_model(message_content, intent="chat") -> str (Groq id shim)
    MODEL_CHAT / MODEL_FAST / MODEL_FALLBACK / MODEL_REASONING
    VALID_MODELS / DEFAULT_MODEL / DEFAULT_FAST_MODEL / MIN_MAX_TOKENS
    _EMPTY_CONTENT_FALLBACK / _validate_messages / get_client

Legacy `model` arguments map onto semantic routing profiles:
    MODEL_FAST     -> FAST profile          (Gemini low → Mistral → Groq)
    MODEL_CHAT     -> CHAT profile          (Gemini → Mistral → Groq → Groq)
    MODEL_FALLBACK -> CHAT profile
    MODEL_REASONING-> REASONING profile     (GLM → Gemini high → Mistral → Groq)

The deterministic intent parser stays FIRST in the cogs (zero LLM calls
for known intents). Sensitive callers (ai_automod, intent parser) pass
sensitive=True -> SENSITIVE_FAST (Mistral → Groq; Gemini/OpenRouter only
with explicit allow flags).

All outputs pass through the SAME final sanitization pipeline
(utils/ai_sanitize): CoT stripping, untagged reasoning stripping,
empty-response handling, Discord length cap, unsafe-None guard. Every
provider result the router returns is already sanitized; the facade
adds the legacy graceful error strings.
"""
import logging
import os

# ── re-export the shared sanitization pipeline (backwards compat) ────
from utils.ai_sanitize import (  # noqa: F401
    sanitize_output,
    strip_cot_preambles,
    strip_reasoning_tags,
    is_empty_content,
    is_meta_reasoning_text,
    EMPTY_CONTENT_MARK,
    DISCORD_CHAR_CAP,
)
from utils.ai_types import AIProfile, AIFailureCategory  # noqa: F401
from utils.ai_router import AIRouter, get_router, AIRoutingError

logger = logging.getLogger('cyn.ai')

# ─── Legacy model constants (compatibility shims) ───────────────────
# These names still describe the Groq emergency-tier models; the router
# translates them into profiles. Values come from the single config
# layer so env overrides apply everywhere consistently.
from utils.ai_config import (  # noqa: F401
    GEMINI_CHAT_MODEL,
    MISTRAL_MODEL,
    OPENROUTER_REASONING_MODEL,
    GROQ_CHAT_MODEL as MODEL_CHAT,
    GROQ_FAST_MODEL as MODEL_FAST,
    GROQ_CHAT_FALLBACK_MODEL as MODEL_FALLBACK,
    GROQ_REASONING_MODEL as MODEL_REASONING,
)

VALID_MODELS = {MODEL_CHAT, MODEL_FAST, MODEL_FALLBACK, MODEL_REASONING}
DEFAULT_MODEL = MODEL_CHAT
DEFAULT_FAST_MODEL = MODEL_FAST

# Minimum token floor. Reasoning models spend tokens on internal
# reasoning before emitting visible content (the old max_tokens=100
# empty-response bug), so 300 remains the floor for every provider.
MIN_MAX_TOKENS = 300

# Canned graceful fallbacks — exact strings the cogs already match on
# (cogs/ai_chat.py ERROR_RESPONSES) so downstream error detection keeps
# working unchanged.
_EMPTY_CONTENT_FALLBACK = "i'm here. what's on your mind?"
_GENERIC_ERROR = "something broke on my end. try again."
_RATE_LIMIT_ERROR = "i'm at capacity right now. try again in a few minutes."

# legacy model name -> routing profile
_MODEL_TO_PROFILE = {
    MODEL_FAST: AIProfile.FAST,
    MODEL_CHAT: AIProfile.CHAT,
    MODEL_FALLBACK: AIProfile.CHAT,
    MODEL_REASONING: AIProfile.REASONING,
}


def get_client():
    """Legacy helper: the raw Groq AsyncGroq client (kept for the few
    places that still poke Groq directly). Raises when GROQ_API_KEY is
    unset — same as before."""
    from groq import AsyncGroq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    return AsyncGroq(api_key=api_key)


def _validate_messages(messages: list) -> list:
    """Sanitize the messages list before sending to any provider.

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
            content = " "
        content = str(content)
        if not content.strip():
            content = " "
        if len(content) > 32000:
            content = content[:32000]
            logger.warning(f"[AI] truncated message {i} to 32000 chars")
        role = msg.get("role", "user")
        if role not in ("system", "user", "assistant", "tool"):
            logger.warning(
                f"[AI] unknown role '{role}' at index {i}, defaulting to 'user'")
            role = "user"
        clean_messages.append({"role": role, "content": content})
    return clean_messages


def _clamp_params(max_tokens, temperature):
    """Legacy validation: 300-token floor, 0-2 temperature clamp."""
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        max_tokens = MIN_MAX_TOKENS
    if max_tokens < MIN_MAX_TOKENS:
        max_tokens = MIN_MAX_TOKENS
    if max_tokens > 32768:
        max_tokens = 32768
    if not isinstance(temperature, (int, float)):
        temperature = 0.9
    temperature = max(0.0, min(2.0, float(temperature)))
    return max_tokens, temperature


async def call_ai_profile(
    messages: list,
    profile: AIProfile,
    max_tokens: int = 300,
    temperature: float = 0.9,
) -> str:
    """NEW explicit-profile entry point (Phase N). Routes through the
    multi-provider chain and returns the sanitized text, or one of the
    legacy graceful error strings when every provider failed.

    PHASE N.1 / PART 5 — FINAL OUTPUT SAFETY GUARD: the router already
    sanitized every provider result (and failed over on meta-only
    output), but the facade re-checks the text at the boundary before
    ANY cog receives it. If the text still trips the meta-reasoning
    detector (defense in depth against a sanitizer regression), it is
    NOT sent to Discord — the caller gets the legacy graceful fallback
    line instead and the event is logged with a category.
    """
    if not messages:
        logger.warning("[AI] empty messages list, skipping")
        return "something broke. try again."
    clean_messages = _validate_messages(messages)
    if not clean_messages:
        logger.warning("[AI] messages list had no valid entries after cleaning")
        return "something broke. try again."

    max_tokens, temperature = _clamp_params(max_tokens, temperature)

    router: AIRouter = get_router()
    try:
        result = await router.route(
            messages=clean_messages,
            profile=profile,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not result.text:
            return _EMPTY_CONTENT_FALLBACK

        # ── PHASE N.1 PART 5: the final guard ──
        guarded = _final_output_guard(result.text, profile)
        if guarded is not None:
            return guarded

        return result.text
    except AIRoutingError as e:
        if e.rate_limited:
            return _RATE_LIMIT_ERROR
        # every provider answered but with no visible content — the
        # legacy empty-content marker (ai_chat randomizes it into a
        # graceful line; its ERROR_RESPONSES set matches this exactly).
        # PHASE N.1: SANITIZATION_EMPTY (HTTP 200, only meta/CoT output)
        # joins the same graceful branch — a provider whose entire
        # response was hidden reasoning counts as no usable content.
        if e.categories and all(
            c in (AIFailureCategory.EMPTY_RESPONSE,
                  AIFailureCategory.SANITIZATION_EMPTY)
            for c in e.categories
        ):
            return _EMPTY_CONTENT_FALLBACK
        logger.error(f"[AI] routing failed: {[c.value for c in e.categories]}")
        return _GENERIC_ERROR
    except Exception as e:
        logger.error(f"[AI] unexpected router error: {type(e).__name__}: {e}")
        return _GENERIC_ERROR


def _final_output_guard(text: str, profile) -> str | None:
    """PHASE N.1 / PART 5 — the LAST check before text reaches a cog.

    Re-runs the sanitizer (idempotent) and the conservative
    meta-reasoning detector. Returns the replacement fallback string
    when the text must NOT be shown, or None when the text is clean and
    the caller should return it as-is. Only ultra-high-confidence
    markers trip the meta detector (see utils/ai_sanitize) — normal
    casual replies pass untouched.
    """
    try:
        resanitized = sanitize_output(text)
        if is_empty_content(resanitized):
            logger.warning(
                "[AI] final guard: router text empty after re-sanitize "
                f"(profile={getattr(profile, 'value', profile)}) — fallback"
            )
            return _EMPTY_CONTENT_FALLBACK
        if is_meta_reasoning_text(resanitized):
            logger.warning(
                "[AI] final guard: meta-reasoning detected at facade "
                f"boundary (profile={getattr(profile, 'value', profile)}) "
                f"({len(resanitized)} chars) — replaced with fallback"
            )
            return _EMPTY_CONTENT_FALLBACK
        return None
    except Exception as e:
        logger.error(f"[AI] final guard error: {type(e).__name__}: {e}")
        return _EMPTY_CONTENT_FALLBACK


async def call_ai(
    messages: list,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 300,
    temperature: float = 0.9,
    retry_count: int = 0,
) -> str:
    """Call the AI with automatic multi-provider failover.

    The legacy `model` argument is translated into a routing profile
    (see _MODEL_TO_PROFILE); unknown names fall back to the CHAT
    profile, exactly like the old unknown-model fallback to
    DEFAULT_MODEL. `retry_count` is accepted for signature
    compatibility — the router's failover + circuit breakers supersede
    the old sleep-and-retry loops (immediate failover, never makes the
    user wait through backoff).

    Returns str ALWAYS — graceful canned lines on total failure.
    """
    profile = _MODEL_TO_PROFILE.get(model)
    if profile is None:
        logger.warning(
            f"[AI] unknown model '{model}', routing via CHAT profile")
        profile = AIProfile.CHAT
    return await call_ai_profile(
        messages, profile, max_tokens=max_tokens, temperature=temperature
    )


async def call_ai_fast(
    messages: list,
    max_tokens: int = 150,
    sensitive: bool = False,
) -> str:
    """Fast path: intent parsing, one-liners, short chat.

    sensitive=True (used by AI automod classification and the NL intent
    parser) routes through SENSITIVE_FAST — Mistral first, Groq as the
    floor — so moderation content never touches Gemini free-tier or
    OpenRouter unless the owner explicitly allowed it. Deterministic
    intents still never reach ANY provider (the deterministic parser in
    utils/intent_parser.py runs first).
    """
    return await call_ai_profile(
        messages,
        AIProfile.SENSITIVE_FAST if sensitive else AIProfile.FAST,
        max_tokens=max(max_tokens, MIN_MAX_TOKENS),
        temperature=0.85,
    )


async def call_ai_reasoning(
    messages: list,
    max_tokens: int = 1000,
    temperature: float = 0.6,
) -> str:
    """Heavy reasoning path: channel recaps, deep digests, complex
    analysis, code/architecture questions.

    REASONING profile: OpenRouter GLM-5.2 free (budget-guarded) →
    Gemini with high thinking → Mistral → Groq gpt-oss-120b. Trivial
    chat never reaches this route (see pick_profile's conservative
    complexity scoring).
    """
    return await call_ai_profile(
        messages,
        AIProfile.REASONING,
        max_tokens=max(max_tokens, MIN_MAX_TOKENS),
        temperature=temperature,
    )


# ─── PHASE N — profile picker (successor of pick_model) ─────────────
#
# Conservative complexity scoring (Part 14): SHORT ORDINARY QUESTIONS
# STAY ON CHAT. The reasoning route needs real signals — a complex
# coding/debug request, large input, multiple constraints, explicit
# analysis/comparison phrasing, recap-shaped requests.

# Intent families that never need more than the FAST profile.
_FAST_INTENTS = (
    "warn", "ban", "kick", "mute", "timeout", "unmute", "purge", "lock",
    "unlock", "slowmode", "remind", "weather", "flip", "roll", "joke",
    "fact", "remind_cancel", "warn_clear", "delete_message", "nick",
    "serverinfo", "ping", "botinfo", "uptime", "whois", "avatar",
)

# STRONG reasoning signals — any one is enough.
_REASONING_STRONG = (
    "architecture", "refactor", "debug this", "why does this code",
    "step by step", "deep dive", "root cause", "trade-offs",
    "tradeoffs", "pros and cons", "compare and contrast",
)

# WEAK signals — need TWO or more together (or one + long input).
_REASONING_WEAK = (
    "code", "debug", "error", "traceback", "stack trace", "algorithm",
    "python", "javascript", "typescript", "sql", "regex", "function",
    "class", "api design", "database schema", "compare", "analyze",
    "optimization", "performance", "concurrency", "race condition",
    "explain how", "how does", "why does",
)

# recap-shaped phrasing (large conversation history summarization)
_RECAP_SIGNALS = (
    "recap", "summarize the conversation", "what did i miss",
    "catch me up", "digest of",
)


def pick_profile(message_content: str, intent: str = "chat") -> AIProfile:
    """Pick the routing profile for a message (Phase N Part 14).

    FAST        — known mod/utility intents, very short messages
    REASONING   — only with real complexity signals (conservative!)
    CHAT        — everything else (the default, deliberately)
    """
    content = message_content or ""
    content_lower = content.lower()

    if intent in _FAST_INTENTS:
        return AIProfile.FAST

    words = content_lower.split()
    if len(words) <= 5 and not any(k in content_lower for k in _REASONING_WEAK):
        return AIProfile.FAST

    strong = any(k in content_lower for k in _REASONING_STRONG)
    weak_hits = sum(1 for k in _REASONING_WEAK if k in content_lower)
    recap = any(k in content_lower for k in _RECAP_SIGNALS)
    long_input = len(content) > 600

    if strong or recap:
        return AIProfile.REASONING
    if weak_hits >= 2:
        return AIProfile.REASONING
    if weak_hits >= 1 and long_input:
        return AIProfile.REASONING
    return AIProfile.CHAT


# PHASE 3C — legacy model picker (kept for compatibility).
#
# Still returns Groq model ids (some call sites and tests pass the
# result into call_ai(model=...), which now maps them onto profiles —
# the contract is preserved end to end). New code should call
# pick_profile() instead.
def pick_model(message_content: str, intent: str = "chat") -> str:
    """Pick the right Groq model based on complexity.

    Returns:
      MODEL_REASONING (openai/gpt-oss-120b) for complex questions / code /
      debugging queries.
      MODEL_CHAT (qwen/qwen3.6-27b) for general casual chat.
      MODEL_FAST (openai/gpt-oss-20b) for simple short chat and
      intent-based mod/utility commands.
    """
    if intent in _FAST_INTENTS:
        return MODEL_FAST

    content_lower = message_content.lower()
    technical_keywords = [
        "code", "debug", "error", "function", "class",
        "algorithm", "python", "javascript", "sql",
        "explain", "how does", "what is", "why does",
        "difference between", "compare", "analyze",
    ]
    if any(kw in content_lower for kw in technical_keywords):
        return MODEL_REASONING

    words = message_content.split()
    if len(words) <= 5:
        return MODEL_FAST

    return MODEL_CHAT


def router_status() -> dict:
    """Expose the router's sanitized status snapshot (owner tooling /
    dashboard endpoint / public generic ai_status)."""
    return get_router().status_snapshot()
