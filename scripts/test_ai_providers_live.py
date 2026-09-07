#!/usr/bin/env python3
"""
scripts/test_ai_providers_live.py — PHASE N.1 / PART 13.

Owner-run LIVE diagnostic for the multi-provider AI core. Sends ONE tiny
request to every CONFIGURED provider (Gemini / Mistral / OpenRouter /
Groq) and prints a sanitized one-line verdict per provider:

    gemini      gemini-3.7-flash            ok          812ms   4 chars
    mistral     mistral-small-2603          fail        auth        401
    openrouter  z-ai/glm-5.2:free           ok          1903ms   5 chars

SAFETY RULES (non-negotiable):
  * Refuses to run unless AURELIA_ALLOW_LIVE_AI_TESTS=true — this script
    is NEVER wired into startup, CI, or the test suites; a test run must
    never consume live AI quota by accident.
  * Prints ONLY: provider, model id, ok/fail, failure category, numeric
    HTTP status, latency, and the LENGTH of the sanitized visible output.
    NEVER API keys, NEVER auth headers, NEVER prompts, NEVER raw error
    bodies, NEVER response content.
  * The prompt is a fixed 3-word probe ("say ok") with a 32-token cap —
    the smallest possible live footprint.
  * Exit code 0 when every configured provider answered, 1 otherwise
    (2 = not enabled).

Usage (Render shell or local):
    AURELIA_ALLOW_LIVE_AI_TESTS=true python scripts/test_ai_providers_live.py
"""
import asyncio
import os
import sys

# gate FIRST — before any provider import touches env keys
if (os.getenv("AURELIA_ALLOW_LIVE_AI_TESTS", "").strip().lower()
        not in ("1", "true", "yes", "on")):
    print("refusing to run: set AURELIA_ALLOW_LIVE_AI_TESTS=true "
          "(live tests consume real provider quota; never run at startup)")
    sys.exit(2)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from ai_providers import (  # noqa: E402
    GeminiProvider,
    MistralProvider,
    OpenRouterProvider,
    GroqProvider,
)
from utils.ai_sanitize import sanitize_output, is_empty_content  # noqa: E402
from utils.ai_types import AIRequestError  # noqa: E402

PROBE_MESSAGES = [{"role": "user", "content": "say ok"}]
PROBE_MAX_TOKENS = 32


async def probe(provider, model: str):
    """One tiny request. Returns the sanitized verdict line fields."""
    try:
        result = await provider.generate(
            messages=PROBE_MESSAGES,
            model=model,
            max_tokens=PROBE_MAX_TOKENS,
            temperature=0.0,
            reasoning_level=None,
            timeout_seconds=20.0,
        )
    except AIRequestError as e:
        return {
            "ok": False, "category": e.category.value,
            "status": e.status_code, "latency_ms": 0, "visible_len": 0,
        }
    except Exception as e:
        # non-normalized failure (SDK import, network, …): type name only
        return {
            "ok": False, "category": f"unhandled:{type(e).__name__}",
            "status": None, "latency_ms": 0, "visible_len": 0,
        }

    visible = sanitize_output(result.text or "")
    return {
        "ok": not is_empty_content(visible),
        "category": None,
        "status": None,
        "latency_ms": result.latency_ms or 0.0,
        "visible_len": len(visible),
    }


async def main() -> int:
    from utils import ai_config as cfg

    providers = [
        ("gemini", GeminiProvider(), cfg.GEMINI_CHAT_MODEL),
        ("mistral", MistralProvider(), cfg.MISTRAL_MODEL),
        ("openrouter", OpenRouterProvider(), cfg.OPENROUTER_REASONING_MODEL),
        ("groq", GroqProvider(), cfg.GROQ_FAST_MODEL),
    ]

    print(f"live ai probe · {len(providers)} providers · "
          f"prompt: fixed 3-word · max_tokens: {PROBE_MAX_TOKENS}")
    print("(output is sanitized: no keys, no headers, no prompts, "
          "no response content)\n")

    failures = 0
    for name, provider, model in providers:
        if not provider.configured:
            print(f"{name:<11} {model:<28} skip (no api key)")
            continue
        verdict = await probe(provider, model)
        if verdict["ok"]:
            print(f"{name:<11} {model:<28} ok          "
                  f"{verdict['latency_ms']:.0f}ms   "
                  f"{verdict['visible_len']} chars")
        else:
            failures += 1
            status = (f" http={verdict['status']}"
                      if verdict.get("status") else "")
            print(f"{name:<11} {model:<28} fail        "
                  f"{verdict['category']}{status}")

    print()
    if failures:
        print(f"verdict: {failures} provider(s) failing — check "
              f"/owner ai_status categories, then provider credentials "
              f"or model availability")
        return 1
    print("verdict: every configured provider answered with visible content")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
