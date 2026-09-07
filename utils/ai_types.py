"""
utils/ai_types.py — PHASE N shared types for the multi-provider AI core.

Everything the router, the provider adapters and the compatibility facade
(utils/ai_handler.py) exchange is defined here so no layer imports another
just for a type — that keeps the import graph acyclic:

    ai_providers/*  ──►  ai_types
    utils/ai_router ──►  ai_types + ai_providers + ai_sanitize
    utils/ai_handler ──►  ai_router (facade only)

Public calling contract (PRESERVED — see Phase N Part 1):
    call_ai(...)           -> str
    call_ai_fast(...)      -> str
    call_ai_reasoning(...) -> str
    pick_model(...)        -> str (Groq model id, compatibility shim)

The AIResult / profile machinery is internal; telemetry metadata never
leaves the router layer.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AIProfile(str, Enum):
    """Semantic routing profiles (Phase N Part 10).

    Do NOT route by raw model names from every cog — cogs speak profiles,
    the router translates profiles into concrete provider/model chains.
    """

    FAST = "fast"                          # intent parsing, one-liners
    CHAT = "chat"                          # general conversation
    REASONING = "reasoning"                # hard questions, recaps, code
    SENSITIVE_FAST = "sensitive_fast"      # automod classification, intents
    SENSITIVE_REASONING = "sensitive_reasoning"


class AIFailureCategory(str, Enum):
    """Normalized failure classification (Phase N Part 12).

    Providers raise AIRequestError with one of these; the router decides
    failover/cooldown policy from the category instead of parsing
    provider-specific error strings everywhere.
    """

    UNCONFIGURED = "unconfigured"          # missing API key — skip, not "broken"
    AUTH = "auth"                          # 401 / 403 — stop hammering
    RATE_LIMIT = "rate_limit"              # 429 — cooldown + fail over
    TIMEOUT = "timeout"                    # request deadline exceeded
    SERVER_ERROR = "server_error"          # 5xx
    MODEL_UNAVAILABLE = "model_unavailable"  # 400 / 404 / decommissioned
    INVALID_RESPONSE = "invalid_response"  # malformed / unparseable payload
    EMPTY_RESPONSE = "empty_response"      # 200 OK but no visible text
    BUDGET_EXHAUSTED = "budget_exhausted"  # OpenRouter daily soft budget
    UNKNOWN = "unknown"


class AIRequestError(Exception):
    """Raised by providers; carries a normalized failure category.

    `retry_after` is honored when a provider returns one (429), otherwise
    the router applies its own defaults.
    """

    def __init__(self, category: AIFailureCategory, message: str = "",
                 retry_after: Optional[float] = None):
        self.category = category
        self.retry_after = retry_after
        super().__init__(message or category.value)


@dataclass
class AIResult:
    """Normalized generation result (Phase N Part 5).

    `text` holds the FINAL sanitized output — every provider passes through
    the same pipeline (reasoning-tag strip, CoT preamble strip, empty
    handling, Discord 1900-char cap) before this dataclass is built, so no
    raw model output can ever reach Discord.
    """

    text: str
    provider: str = ""
    model: str = ""
    profile: str = ""
    latency_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    thinking_level: Optional[str] = None
    failed_over_from: list = field(default_factory=list)


# Thinking-level hints attached to route steps (Gemini translates these to
# ThinkingConfig; other providers may ignore them).
THINKING_LOW = "low"
THINKING_HIGH = "high"
