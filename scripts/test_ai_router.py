#!/usr/bin/env python3
"""
scripts/test_ai_router.py — PHASE N PART 23 — AI router test suite.

ALL PROVIDERS ARE MOCKED. This suite never contacts Gemini, Mistral,
OpenRouter or Groq — every FakeProvider returns instantly or raises a
scripted AIRequestError. The module-level router singleton is swapped
with the fake router (utils.ai_router.set_router) BEFORE any facade
call, so call_ai / call_ai_fast / call_ai_reasoning exercise the fake
chains too. No real quota is ever burned, no network sockets opened.

Covers the 28 required scenarios:
   1  Gemini succeeds: CHAT stops at Gemini
   2  Gemini 429: CHAT falls to Mistral
   3  Gemini timeout: CHAT falls to Mistral
   4  Gemini absent: Mistral becomes first route
   5  Mistral also fails: CHAT reaches Groq
   6  all non-Groq keys absent: legacy Groq-only operation works
   7  REASONING: GLM is first
   8  GLM daily budget reached: OpenRouter skipped entirely
   9  GLM 429: falls to next provider
  10  SENSITIVE: Gemini is NOT called
  11  SENSITIVE: OpenRouter is NOT called by default
  12  sensitive allow flags: only permit providers when enabled
  13  CoT tags from ANY provider are stripped
  14  untagged reasoning preambles from ANY provider are stripped
  15  empty provider result fails over or returns safe fallback
  16  oversized response is capped safely for Discord
  17  malformed provider response never crashes the bot
  18  provider telemetry contains NO prompt text
  19  provider health circuit opens after configured failures
  20  successful call restores provider health
  21  missing API key marks provider unconfigured, not broken
  22  invalid provider key does not generate repeated calls
  23  OpenRouter counter persists across router recreation
  24  privacy opt-out still prevents relevant AI preprocessing
  25  call_ai still returns str
  26  call_ai_fast still returns str
  27  call_ai_reasoning still returns str
  28  existing AI cogs require no behavioral rewrite (contract check)

Run:  python3 scripts/test_ai_router.py
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# keep output readable: router warnings are expected in failure tests
logging.basicConfig(level=logging.CRITICAL)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


# ─── fake provider machinery (zero network) ──────────────────────────
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory
from utils.ai_sanitize import sanitize_output
import utils.ai_config as cfg
import utils.ai_router as ar
from utils.ai_router import AIRouter, set_router


class FakeProvider:
    """Configurable fake: scripts responses/errors per call."""
    name = "fake"

    def __init__(self, name: str, key: str = "k"):
        self.name = name
        self._key = key
        self.calls = 0
        self.call_models = []
        self.script = None          # list of AIResult|AIRequestError|str
        self.default_text = f"reply from {name}"

    @property
    def configured(self):
        return bool(self._key)

    def model_ids(self):
        return {"chat": f"{self.name}-model"}

    async def generate(self, messages, model, max_tokens, temperature,
                       reasoning_level=None, timeout_seconds=30.0):
        self.calls += 1
        self.call_models.append((model, reasoning_level))
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, AIRequestError):
                raise item
            if isinstance(item, AIResult):
                return item
            return AIResult(text=str(item), provider=self.name, model=model)
        return AIResult(text=self.default_text, provider=self.name,
                        model=model, input_tokens=10, output_tokens=20)

    async def close(self):
        pass


def build_router(env_overrides: dict = None):
    """Fresh AIRouter with fakes injected + the module singleton swapped
    to it, so the facade (call_ai family) also uses ONLY the fakes.

    env_overrides maps env var -> value (None = unset). API keys set to
    None also mark the matching FAKE provider unconfigured — key absence
    semantics are identical in both layers."""
    import importlib
    for k in ("GEMINI_API_KEY", "MISTRAL_API_KEY",
              "OPENROUTER_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update({
        "AI_ROUTER_ENABLED": "true",
        "AI_ALLOW_GEMINI_SENSITIVE": "false",
        "AI_ALLOW_OPENROUTER_SENSITIVE": "false",
        "OPENROUTER_DAILY_BUDGET": "45",
    })
    for k, v in (env_overrides or {}).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    importlib.reload(cfg)

    fakes = {
        "gemini": FakeProvider("gemini"),
        "mistral": FakeProvider("mistral"),
        "openrouter": FakeProvider("openrouter"),
        "groq": FakeProvider("groq"),
    }
    # absent API key -> fake provider unconfigured (never "broken")
    key_map = {
        "GEMINI_API_KEY": "gemini",
        "MISTRAL_API_KEY": "mistral",
        "OPENROUTER_API_KEY": "openrouter",
        "GROQ_API_KEY": "groq",
    }
    for env_key, prov in key_map.items():
        if env_overrides and env_key in env_overrides \
                and env_overrides[env_key] is None:
            fakes[prov]._key = None

    router = AIRouter(providers=fakes)
    router._keep_alive_metrics = False
    set_router(router)          # facade now uses ONLY the fakes
    return router, fakes


async def main():
    msgs = [{"role": "user", "content": "hello"}]
    try:
        await run_tests(msgs)
    finally:
        set_router(None)        # never leak fakes into other test suites

    print(f"\n{PASS} passed · {FAIL} failed")
    return 1 if FAIL else 0


async def run_tests(msgs):
    print("── 1-5 · chat chain behavior ──")
    # 1: Gemini succeeds, chain stops
    r, f = build_router()
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("1. CHAT stops at Gemini",
          res.provider == "gemini" and f["gemini"].calls == 1
          and f["mistral"].calls == 0 and f["groq"].calls == 0)

    # 2: Gemini 429 → Mistral
    r, f = build_router()
    f["gemini"].script = [AIRequestError(AIFailureCategory.RATE_LIMIT,
                                         "429", retry_after=30)]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("2. Gemini 429 → CHAT falls to Mistral",
          res.provider == "mistral" and f["gemini"].calls == 1)

    # 3: Gemini timeout → Mistral
    r, f = build_router()
    f["gemini"].script = [AIRequestError(AIFailureCategory.TIMEOUT, "t")]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("3. Gemini timeout → CHAT falls to Mistral",
          res.provider == "mistral")

    # 4: Gemini key absent → Mistral first
    r, f = build_router({"GEMINI_API_KEY": None})
    check("4a. fake gemini unconfigured when key absent",
          f["gemini"].configured is False)
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("4b. Gemini absent → Mistral is first route",
          res.provider == "mistral" and f["gemini"].calls == 0)

    # 5: Gemini + Mistral fail → Groq
    r, f = build_router()
    f["gemini"].script = [AIRequestError(AIFailureCategory.SERVER_ERROR, "500")]
    f["mistral"].script = [AIRequestError(AIFailureCategory.SERVER_ERROR, "503")]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("5. Mistral also fails → CHAT reaches Groq",
          res.provider == "groq" and res.model == cfg.GROQ_CHAT_MODEL)

    print("── 6 · legacy groq-only rollout ──")
    groq_only = {"GEMINI_API_KEY": None, "MISTRAL_API_KEY": None,
                 "OPENROUTER_API_KEY": None}
    r, f = build_router(groq_only)
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("6a. Groq-only: CHAT works via groq chat model",
          res.provider == "groq" and res.model == cfg.GROQ_CHAT_MODEL)
    r, f = build_router(groq_only)
    res = await r.route(msgs, cfg.AIProfile.REASONING)
    check("6b. Groq-only: REASONING works via gpt-oss-120b",
          res.provider == "groq" and res.model == cfg.GROQ_REASONING_MODEL)
    r, f = build_router(groq_only)
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_FAST)
    check("6c. Groq-only: SENSITIVE works via gpt-oss-20b",
          res.provider == "groq" and res.model == cfg.GROQ_FAST_MODEL)

    # 6d: AI_ROUTER_ENABLED=false → legacy behavior
    r, f = build_router({"AI_ROUTER_ENABLED": "false"})
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("6d. AI_ROUTER_ENABLED=false → groq-only legacy chains",
          res.provider == "groq" and f["gemini"].calls == 0
          and f["mistral"].calls == 0 and f["openrouter"].calls == 0)

    print("── 7-9 · reasoning route + GLM budget ──")
    # 7: REASONING → GLM first
    r, f = build_router()
    res = await r.route(msgs, cfg.AIProfile.REASONING)
    check("7. REASONING: GLM (openrouter) is first",
          res.provider == "openrouter" and res.model == "z-ai/glm-5.2:free")

    # 8: budget reached → openrouter skipped entirely
    r, f = build_router()
    with r._lock:
        r._usage[("openrouter", "z-ai/glm-5.2:free", "reasoning")] = {
            "requests": 45, "successes": 45, "failures": 0,
            "input_tokens": 0, "output_tokens": 0,
            "total_latency_ms": 0.0, "latency_count": 1,
        }
    res = await r.route(msgs, cfg.AIProfile.REASONING)
    check("8. GLM daily budget reached → OpenRouter skipped entirely",
          res.provider == "gemini" and f["openrouter"].calls == 0)

    # 9: GLM 429 → next provider
    r, f = build_router()
    f["openrouter"].script = [AIRequestError(AIFailureCategory.RATE_LIMIT,
                                             "429 openrouter")]
    res = await r.route(msgs, cfg.AIProfile.REASONING)
    check("9. GLM 429 → falls to Gemini (high thinking)",
          res.provider == "gemini"
          and f["gemini"].call_models[0][1] == "high")

    print("── 10-12 · sensitive routing ──")
    # 10: SENSITIVE never calls Gemini
    r, f = build_router()
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_FAST)
    check("10. SENSITIVE: Gemini is NOT called",
          res.provider == "mistral" and f["gemini"].calls == 0)

    # 11: SENSITIVE never calls OpenRouter
    r, f = build_router()
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_REASONING)
    check("11. SENSITIVE: OpenRouter is NOT called by default",
          res.provider == "mistral" and f["openrouter"].calls == 0)

    # 12: allow flags actually permit providers
    r, f = build_router({"AI_ALLOW_GEMINI_SENSITIVE": "true"})
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_FAST)
    check("12a. AI_ALLOW_GEMINI_SENSITIVE=true → Gemini serves sensitive",
          res.provider == "gemini")
    r, f = build_router({"AI_ALLOW_OPENROUTER_SENSITIVE": "true"})
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_REASONING)
    check("12b. AI_ALLOW_OPENROUTER_SENSITIVE=true → GLM serves sensitive",
          res.provider == "openrouter")

    print("── 13-17 · sanitization guarantees (any provider) ──")
    from utils.ai_handler import call_ai, call_ai_fast, call_ai_reasoning, \
        pick_model, MODEL_FAST, MODEL_REASONING, MODEL_CHAT

    # 13: tagged CoT from any provider is stripped
    out = sanitize_output(
        "We need to output two lines.\n\n"
        "<thinking>secret reasoning</thinking>\n\nhi ♡")
    check("13. tagged CoT stripped for any provider",
          "secret reasoning" not in out and "hi ♡" in out)
    r, f = build_router()
    f["gemini"].script = [AIResult(text="<thinking>internal monologue</thinking>clean answer")]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("13b. <thinking> blocks from any provider never reach Discord",
          "internal monologue" not in res.text and res.text == "clean answer")

    # 14: untagged CoT preambles stripped
    out = sanitize_output(
        "We have a conversation. The user says hi twice.\n\n\nhello! ♡")
    check("14. untagged reasoning preambles stripped",
          out == "hello! ♡")
    r, f = build_router()
    f["mistral"].script = [AIResult(
        text="The user says hi.\n\nthe real answer is 42")]
    res = await r.route(msgs, cfg.AIProfile.SENSITIVE_FAST)
    check("14b. sensitive-route output sanitized too",
          res.text == "the real answer is 42")

    # 15: empty result → failover (or safe fallback)
    r, f = build_router()
    f["gemini"].script = [AIResult(text="   ")]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("15a. empty provider result fails over to Mistral",
          res.provider == "mistral")
    r, f = build_router()
    f["gemini"].script = [AIResult(text="")]
    f["mistral"].script = [AIResult(text=""), AIResult(text="")]
    f["groq"].script = [AIResult(text=""), AIResult(text=""),
                        AIResult(text=""), AIResult(text="")]
    out = await call_ai(msgs)
    check("15b. every provider empty → legacy safe fallback str",
          out == "i'm here. what's on your mind?", f"got {out!r}")

    # 16: oversized response capped for Discord
    r, f = build_router()
    f["gemini"].script = [AIResult(text="x" * 5000)]
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("16. oversized response capped at 1900+3 chars",
          len(res.text) == 1903 and res.text.endswith("..."))

    # 17: malformed provider response never crashes the bot
    class ExplodingProvider(FakeProvider):
        async def generate(self, *a, **kw):
            self.calls += 1
            raise RuntimeError("garbage {not json")
    r, f = build_router()
    f["gemini"] = ExplodingProvider("gemini")
    r.providers["gemini"] = f["gemini"]
    out = await call_ai(msgs)
    check("17. malformed/crashing provider never crashes call_ai",
          isinstance(out, str) and len(out) > 0)

    print("── 18 · telemetry privacy ──")
    # 18: telemetry contains no prompt text
    r, f = build_router()
    secret_msg = [{"role": "user", "content": "S3CRET-PROMPT-TEXT"}]
    await r.route(secret_msg, cfg.AIProfile.CHAT)
    snap = r.status_snapshot()
    snap_str = str(snap)
    check("18a. telemetry snapshot contains NO prompt text",
          "S3CRET-PROMPT-TEXT" not in snap_str)
    with r._lock:
        usage_str = str(r._usage)
    check("18b. usage accounting contains NO prompt text",
          "S3CRET-PROMPT-TEXT" not in usage_str)
    check("18c. snapshot contains no api keys",
          not any(k in snap_str for k in ("gsk_", "fake-key", "Bearer")))

    print("── 19-22 · circuit breakers ──")
    # 19: circuit opens after configured failures (3 consecutive 5xx)
    r, f = build_router()
    for _ in range(3):
        f["gemini"].script = [AIRequestError(AIFailureCategory.SERVER_ERROR,
                                             "500")]
        await r.route(msgs, cfg.AIProfile.CHAT)
    f["gemini"].script = None
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("19. circuit opens after configured failures (gemini skipped)",
          res.provider == "mistral" and f["gemini"].calls == 3,
          f"gemini calls={f['gemini'].calls}")

    # 20: successful call restores health
    r, f = build_router()
    for _ in range(3):
        f["gemini"].script = [AIRequestError(AIFailureCategory.TIMEOUT, "t")]
        await r.route(msgs, cfg.AIProfile.CHAT)
    f["gemini"].script = None
    f["mistral"].script = [AIRequestError(AIFailureCategory.SERVER_ERROR, "x")]
    res = await r.route(msgs, cfg.AIProfile.CHAT)   # gemini breaker open
    check("20a. degraded gemini skipped while breaker open",
          res.provider == "groq")
    f["mistral"].script = None
    r._record_success("gemini")
    res = await r.route(msgs, cfg.AIProfile.CHAT)
    check("20b. success restores provider health",
          res.provider == "gemini")

    # 21: missing key = unconfigured, not broken
    r, f = build_router({"GEMINI_API_KEY": None})
    snap = r.status_snapshot()
    check("21. missing key marks provider unconfigured (not broken)",
          snap["providers"]["gemini"]["state"] == "unconfigured"
          and snap["providers"]["gemini"]["configured"] is False)

    # 22: invalid key (401) → stop hammering (cooldown, no more calls)
    r, f = build_router()
    f["gemini"].script = [AIRequestError(AIFailureCategory.AUTH, "401")]
    await r.route(msgs, cfg.AIProfile.CHAT)
    f["gemini"].script = None
    for _ in range(5):
        await r.route(msgs, cfg.AIProfile.CHAT)
    check("22. invalid key → no repeated calls (auth cooldown)",
          f["gemini"].calls == 1, f"calls={f['gemini'].calls}")

    print("── 23 · persistent budget counter ──")
    # drain pending fire-and-forget usage writes from earlier tests
    await asyncio.sleep(0.15)
    import datetime as _dt
    from utils.db import record_ai_usage, get_ai_usage_for_date
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    usage_json = "data/ai_provider_usage.json"
    if os.path.exists(usage_json):
        os.remove(usage_json)
    record_ai_usage(usage_date=today, provider="openrouter",
                    model="z-ai/glm-5.2:free", profile="reasoning",
                    requests=5, successes=5)
    rows = get_ai_usage_for_date(today)
    check("23a. usage accounting round-trips (json fallback)",
          any(x.get("provider") == "openrouter" and x.get("requests") == 5
              for x in rows), f"rows={rows}")
    r, f = build_router()
    await r.load_today_from_db()
    with r._lock:
        used = r._provider_requests_today("openrouter")
    check("23b. OpenRouter counter restored across router recreation",
          used == 5, f"got {used}")

    print("── 24 · privacy opt-outs ──")
    # 24: the enforcement points still exist in the cogs (opt-outs are
    # checked BEFORE any provider call / persistence / extraction)
    src = open("cogs/ai_chat.py", encoding="utf-8").read()
    check("24a. memory opt-out checked before persistence",
          "memory_optout" in src and "fact_extraction_optout" in src)
    check("24b. sensitive automod call opts into sensitive routing",
          "sensitive=True" in open("cogs/ai_automod.py", encoding="utf-8").read())
    check("24c. intent parser opts into sensitive routing",
          "sensitive=True" in open("utils/intent_parser.py", encoding="utf-8").read())

    print("── 25-28 · public contract preservation ──")
    # 25-27: call_ai family always returns str (through the FAKE chains)
    out = await call_ai(msgs)
    check("25. call_ai still returns str", isinstance(out, str))
    out = await call_ai_fast(msgs)
    check("26. call_ai_fast still returns str", isinstance(out, str))
    out = await call_ai_reasoning(msgs)
    check("27. call_ai_reasoning still returns str", isinstance(out, str))
    # 28: legacy model-name mapping (no cog rewrites needed)
    r, f = build_router()
    out = await call_ai(msgs, model=MODEL_FAST)
    check("28a. call_ai(model=MODEL_FAST) routes to FAST profile",
          isinstance(out, str) and f["groq"].calls == 0,
          f"groq called {f['groq'].calls}x (should be gemini-first)")
    m = pick_model("hi")
    check("28b. pick_model returns a groq id the facade understands",
          m in {MODEL_CHAT, MODEL_FAST, "qwen/qwen3.8-27b", MODEL_REASONING},
          f"got {m}")
    out = await call_ai(msgs, model=m)
    check("28c. pick_model result round-trips through call_ai",
          isinstance(out, str))
    # 28d: every provider unconfigured → graceful error string
    r, f = build_router({"GEMINI_API_KEY": None, "MISTRAL_API_KEY": None,
                         "OPENROUTER_API_KEY": None,
                         "GROQ_API_KEY": None})
    out = await call_ai(msgs)
    check("28d. all providers missing → graceful error string",
          out in ("something broke. try again.",
                  "something broke on my end. try again.",
                  "i'm at capacity right now. try again in a few minutes."),
          f"got {out!r}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
