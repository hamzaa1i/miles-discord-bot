"""
utils/ai_config.py — PHASE N configuration layer.

THE single source of truth for every provider name, model id, routing
flag and budget (Phase N Part 3: "Centralize all model/provider names in
ONE configuration layer. Support environment overrides.").

Nothing else in the codebase hardcodes a model id — cogs speak semantic
profiles, the router reads chain definitions that reference the constants
below, and every constant is env-overridable so the owner can swap a
model without touching code.

Model IDs verified against the providers' current official APIs
(Sept 2026):
  gemini-3.7-flash          Google Gemini Developer API
  mistral-small-2603        Mistral API (Mistral Small 4)
  z-ai/glm-5.2:free         OpenRouter (free GLM endpoint)
  qwen/qwen3.6-27b          Groq (live-verified in production)
  qwen/qwen3.8-27b          Groq (live-verified)
  openai/gpt-oss-20b        Groq (live-verified)
  openai/gpt-oss-120b       Groq (live-verified)

API keys are SERVER-SIDE ONLY (Render). None of these variables may ever
be mirrored as NEXT_PUBLIC_* into the browser bundle.
"""
import os

from utils.ai_types import AIProfile


def _env(key: str, default: str) -> str:
    return (os.getenv(key) or default).strip() or default


def _env_bool(key: str, default: bool) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


# ─── API keys (server-side only) ────────────────────────────────────
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
MISTRAL_API_KEY = (os.getenv("MISTRAL_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

# ─── Model ids (env-overridable) ───────────────────────────────────
GEMINI_CHAT_MODEL = _env("AI_MODEL_GEMINI_CHAT", "gemini-3.7-flash")
MISTRAL_MODEL = _env("AI_MODEL_MISTRAL", "mistral-small-2603")
OPENROUTER_REASONING_MODEL = _env("AI_MODEL_OPENROUTER_REASONING", "z-ai/glm-5.2:free")
GROQ_CHAT_MODEL = _env("AI_MODEL_GROQ_CHAT", "qwen/qwen3.6-27b")
GROQ_CHAT_FALLBACK_MODEL = _env("AI_MODEL_GROQ_CHAT_FALLBACK", "qwen/qwen3.8-27b")
GROQ_FAST_MODEL = _env("AI_MODEL_GROQ_FAST", "openai/gpt-oss-20b")
GROQ_REASONING_MODEL = _env("AI_MODEL_GROQ_REASONING", "openai/gpt-oss-120b")

# ─── Routing flags ─────────────────────────────────────────────────
# AI_ROUTER_ENABLED=false -> everything goes straight to Groq (legacy
# behavior, the safe-rollout kill switch).
ROUTER_ENABLED = _env_bool("AI_ROUTER_ENABLED", True)

# Privacy: Gemini free-tier / OpenRouter free models have different data
# handling terms than paid tiers. Sensitive requests skip BOTH providers
# unless explicitly allowed (Phase N Parts 2/6/8 — default false).
ALLOW_GEMINI_SENSITIVE = _env_bool("AI_ALLOW_GEMINI_SENSITIVE", False)
ALLOW_OPENROUTER_SENSITIVE = _env_bool("AI_ALLOW_OPENROUTER_SENSITIVE", False)

# ─── OpenRouter daily soft budget (requests per UTC day) ───────────
# 45 deliberately leaves a buffer below the provider's basic free
# allowance; configurable for when the owner has a higher tier.
OPENROUTER_DAILY_BUDGET = max(0, int(
    _env("OPENROUTER_DAILY_BUDGET", "45") or 45))

# OpenRouter reasoning effort for REASONING-profile calls ("high" default;
# set empty string to not send the param at all).
OPENROUTER_REASONING_EFFORT = _env("AI_OPENROUTER_REASONING_EFFORT", "high")

# ─── Timeout policy (seconds, per provider attempt) ────────────────
TIMEOUTS = {
    AIProfile.FAST: 12.0,
    AIProfile.CHAT: 25.0,
    AIProfile.REASONING: 50.0,          # first (complex) provider
    AIProfile.REASONING.value: 50.0,
    AIProfile.SENSITIVE_FAST: 12.0,
    AIProfile.SENSITIVE_REASONING: 45.0,
}
# Fallback providers after the first reasoning hop get the shorter chat
# timeout so the whole chain stays under ~2 minutes worst-case.
REASONING_TAIL_TIMEOUT = 25.0


def profile_timeout(profile: AIProfile) -> float:
    return float(TIMEOUTS.get(profile, TIMEOUTS.get(profile.value, 25.0)))


# ─── Circuit-breaker tuning ────────────────────────────────────────
BREAKER_FAILURE_THRESHOLD = 3        # consecutive 5xx/timeouts -> degrade
BREAKER_COOLDOWN_SECONDS = 90.0      # degraded cooldown (60-120s band)
RATE_LIMIT_COOLDOWN_SECONDS = 60.0   # default 429 cooldown
AUTH_COOLDOWN_SECONDS = 3600.0       # 401/403 — stop hammering for 1h
MODEL_UNAVAILABLE_COOLDOWN = 900.0   # 400/404 — 15 min

# Hard cap on provider attempts per user request (Part 12: one message
# must never trigger a 15-request storm).
MAX_ATTEMPTS_PER_REQUEST = 4
