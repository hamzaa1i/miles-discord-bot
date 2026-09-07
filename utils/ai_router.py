"""
utils/ai_router.py — PHASE N multi-provider AI router.

THE single failover owner (Phase N Part 4): provider adapters are pure
transport, this module owns everything about *choosing* providers:

  * semantic routing profiles (FAST / CHAT / REASONING / SENSITIVE_FAST /
    SENSITIVE_REASONING) -> ordered provider/model chains
  * failover (never retries-with-sleep — immediately continue down the
    chain so the user never waits through a long retry storm)
  * per-provider circuit breakers (429 / 5xx / 401 / 404 policies)
  * OpenRouter daily soft budget guard (45 req/day default, env-tunable)
  * persistent provider usage accounting (utils.db ai_provider_usage
    table + JSON fallback; metadata ONLY — never prompts or responses)
  * telemetry snapshots for /owner ai_status, the dashboard AI page and
    the generic public ai_status string

Chains (spec Parts 2/10; model ids from utils/ai_config):

  FAST               Gemini 3.7 Flash (low thinking) → Mistral Small 4 → Groq gpt-oss-20b
  CHAT               Gemini 3.7 Flash → Mistral Small 4 → Groq qwen3.6 → Groq qwen3.8
  REASONING          OpenRouter GLM-5.2 free → Gemini (high thinking) → Mistral → Groq gpt-oss-120b
  SENSITIVE_FAST     Mistral Small 4 → Groq gpt-oss-20b
  SENSITIVE_REASONING Mistral Small 4 → Groq gpt-oss-120b

  Gemini / OpenRouter join the sensitive chains ONLY when their explicit
  allow-flag is enabled (free-tier data-handling terms differ — privacy
  routing must be deliberate, default off).

  AI_ROUTER_ENABLED=false collapses every chain to Groq (legacy mode).
  A missing provider key shrinks its chain gracefully; when only Groq is
  configured the bot behaves exactly like the pre-Phase-N deployment.

Usage accounting privacy (Phase N Part 9): metadata only — provider,
model, profile, counts, tokens, latency. NEVER prompts, responses,
conversation text, moderation text or API keys.

PHASE N.1 hardening (this revision):
  * SANITIZATION_EMPTY — HTTP 200 with only meta/CoT output is a
    FAILURE, counted and failed over (Part 6 success accounting).
  * provider states: unconfigured / unknown / healthy / degraded /
    cooldown / auth_error / model_unavailable. "healthy" requires a
    real successful request; a configured-but-unverified provider is
    "unknown" (Part 3: configured != healthy).
  * sanitized failure telemetry: category + numeric status + latency
    only — never exception bodies.
"""
import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_providers import (
    GeminiProvider,
    MistralProvider,
    OpenRouterProvider,
    GroqProvider,
)
from utils import ai_config as cfg
from utils.ai_sanitize import sanitize_output, is_empty_content
from utils.ai_types import (
    AIProfile,
    AIFailureCategory,
    AIRequestError,
    AIResult,
)

logger = logging.getLogger('cyn.ai.router')


# ─── routing steps ──────────────────────────────────────────────────

@dataclass
class RouteStep:
    provider: str                    # "gemini" | "mistral" | "openrouter" | "groq"
    model: str                       # concrete model id from ai_config
    thinking_level: str | None = None  # "low" | "high" (Gemini hint)


class AIRoutingError(AIRequestError):
    """Every provider in the chain failed. Carries the failure summary
    so the facade can pick a graceful user-facing message."""

    def __init__(self, categories: list, message: str = "all providers failed"):
        self.categories = categories or []
        rate_limited = AIFailureCategory.RATE_LIMIT in self.categories
        super().__init__(AIFailureCategory.UNKNOWN, message)
        self.rate_limited = rate_limited


@dataclass
class ProviderHealth:
    consecutive_failures: int = 0
    cooldown_until: float = 0.0          # monotonic clock
    cooldown_reason: str = ""
    last_error_category: str | None = None
    last_error_status: int | None = None   # sanitized numeric HTTP status
    last_error_at: float | None = None   # epoch, for status display
    last_success_at: float | None = None # epoch
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0

    def state(self, configured: bool) -> str:
        """PHASE N.1 canonical health state. States:

          unconfigured     no api key — skipped, never an error
          auth_error       401/403 cooldown — key invalid/forbidden
          model_unavailable 404/decommissioned cooldown — model id gone
          cooldown         rate-limit / repeated-failure cooldown
          degraded         breaker open (consecutive failures >= threshold)
          healthy          a REAL request succeeded and nothing failed since
          unknown          configured but never verified (fresh restart,
                           or only soft failures so far)

        "healthy" REQUIRES a successful live request (configured !=
        healthy). A provider that merely has a key starts "unknown"
        until it proves itself or lands in a cooldown/degraded state.
        """
        if not configured:
            return "unconfigured"
        if self.cooldown_until > time.monotonic():
            if self.cooldown_reason.startswith("auth"):
                return "auth_error"
            if self.cooldown_reason.startswith("model"):
                return "model_unavailable"
            return "cooldown"
        if self.consecutive_failures >= cfg.BREAKER_FAILURE_THRESHOLD:
            return "degraded"
        if self.total_successes > 0 and self.consecutive_failures == 0:
            return "healthy"
        return "unknown"


# ─── the router ─────────────────────────────────────────────────────

class AIRouter:
    def __init__(self, providers: dict | None = None):
        self.providers = providers or {
            "gemini": GeminiProvider(),
            "mistral": MistralProvider(),
            "openrouter": OpenRouterProvider(),
            "groq": GroqProvider(),
        }
        self._health = {name: ProviderHealth() for name in self.providers}
        self._lock = threading.RLock()
        # in-memory usage accounting (UTC-day keyed, mirrored to db)
        self._today = self._utc_date()
        self._usage: dict = {}          # (provider, model, profile) -> stats
        self._loaded_day = None         # db rows loaded for this day
        self._keep_alive_metrics = True

    # ── chain construction ─────────────────────────────────────────

    def _steps_for(self, profile: AIProfile) -> list:
        """Effective ordered steps for a profile (before health/budget
        filtering — that happens per request)."""
        groq = "groq"
        g = cfg.GEMINI_CHAT_MODEL
        m = cfg.MISTRAL_MODEL
        glm = cfg.OPENROUTER_REASONING_MODEL

        if not cfg.ROUTER_ENABLED:
            # legacy kill-switch: Groq-only operation
            return {
                AIProfile.FAST: [RouteStep(groq, cfg.GROQ_FAST_MODEL)],
                AIProfile.CHAT: [RouteStep(groq, cfg.GROQ_CHAT_MODEL),
                                 RouteStep(groq, cfg.GROQ_CHAT_FALLBACK_MODEL)],
                AIProfile.REASONING: [RouteStep(groq, cfg.GROQ_REASONING_MODEL),
                                      RouteStep(groq, cfg.GROQ_CHAT_FALLBACK_MODEL)],
                AIProfile.SENSITIVE_FAST: [RouteStep(groq, cfg.GROQ_FAST_MODEL)],
                AIProfile.SENSITIVE_REASONING: [RouteStep(groq, cfg.GROQ_REASONING_MODEL)],
            }[profile]

        if profile == AIProfile.FAST:
            return [
                RouteStep("gemini", g, "low"),
                RouteStep("mistral", m),
                RouteStep(groq, cfg.GROQ_FAST_MODEL),
            ]
        if profile == AIProfile.CHAT:
            return [
                RouteStep("gemini", g, "low"),
                RouteStep("mistral", m),
                RouteStep(groq, cfg.GROQ_CHAT_MODEL),
                RouteStep(groq, cfg.GROQ_CHAT_FALLBACK_MODEL),
            ]
        if profile == AIProfile.REASONING:
            return [
                RouteStep("openrouter", glm, "high"),
                RouteStep("gemini", g, "high"),
                RouteStep("mistral", m),
                RouteStep(groq, cfg.GROQ_REASONING_MODEL),
            ]
        if profile == AIProfile.SENSITIVE_FAST:
            steps = []
            if cfg.ALLOW_GEMINI_SENSITIVE:
                steps.append(RouteStep("gemini", g, "low"))
            if cfg.ALLOW_OPENROUTER_SENSITIVE:
                steps.append(RouteStep("openrouter", glm, "high"))
            steps.append(RouteStep("mistral", m))
            steps.append(RouteStep(groq, cfg.GROQ_FAST_MODEL))
            return steps
        if profile == AIProfile.SENSITIVE_REASONING:
            steps = []
            if cfg.ALLOW_OPENROUTER_SENSITIVE:
                steps.append(RouteStep("openrouter", glm, "high"))
            if cfg.ALLOW_GEMINI_SENSITIVE:
                steps.append(RouteStep("gemini", g, "high"))
            steps.append(RouteStep("mistral", m))
            steps.append(RouteStep(groq, cfg.GROQ_REASONING_MODEL))
            return steps
        return [RouteStep("gemini", g, "low"), RouteStep("mistral", m),
                RouteStep(groq, cfg.GROQ_FAST_MODEL)]

    # ─── circuit breaker ────────────────────────────────────────────

    def _breaker_open(self, name: str) -> bool:
        with self._lock:
            h = self._health.get(name)
            return bool(h and h.cooldown_until > time.monotonic())

    def _record_failure(self, name: str, err: AIRequestError):
        now_mono = time.monotonic()
        with self._lock:
            h = self._health.setdefault(name, ProviderHealth())
            h.total_calls += 1
            h.total_failures += 1
            h.last_error_category = err.category.value
            h.last_error_status = err.status_code
            h.last_error_at = time.time()
            h.consecutive_failures += 1

            cat = err.category
            if cat == AIFailureCategory.RATE_LIMIT:
                wait = err.retry_after or cfg.RATE_LIMIT_COOLDOWN_SECONDS
                h.cooldown_until = now_mono + min(wait, 600.0)
                h.cooldown_reason = "rate limited"
            elif cat == AIFailureCategory.AUTH:
                h.cooldown_until = now_mono + cfg.AUTH_COOLDOWN_SECONDS
                h.cooldown_reason = "auth failed — check api key"
            elif cat == AIFailureCategory.MODEL_UNAVAILABLE:
                h.cooldown_until = now_mono + cfg.MODEL_UNAVAILABLE_COOLDOWN
                h.cooldown_reason = "model unavailable"
                h.consecutive_failures = 0  # not a health signal for the provider
            elif cat == AIFailureCategory.BAD_REQUEST:
                # request-shape error: prompt-specific or code bug — a
                # retry storm won't fix it, but it isn't the provider's
                # health either. Short cooldown, breaker unaffected.
                h.cooldown_until = now_mono + cfg.MODEL_UNAVAILABLE_COOLDOWN
                h.cooldown_reason = "bad request (request shape)"
                h.consecutive_failures = 0
            elif cat in (AIFailureCategory.SERVER_ERROR, AIFailureCategory.TIMEOUT):
                if h.consecutive_failures >= cfg.BREAKER_FAILURE_THRESHOLD:
                    h.cooldown_until = now_mono + cfg.BREAKER_COOLDOWN_SECONDS
                    h.cooldown_reason = "degraded (repeated failures)"
            elif cat in (AIFailureCategory.INVALID_RESPONSE,
                         AIFailureCategory.EMPTY_RESPONSE,
                         AIFailureCategory.SANITIZATION_EMPTY):
                # content-shaped failures: count, but need double the
                # threshold before the breaker opens
                if h.consecutive_failures >= cfg.BREAKER_FAILURE_THRESHOLD * 2:
                    h.cooldown_until = now_mono + cfg.BREAKER_COOLDOWN_SECONDS
                    h.cooldown_reason = "repeated empty/invalid responses"

    def _record_success(self, name: str):
        with self._lock:
            h = self._health.setdefault(name, ProviderHealth())
            h.total_calls += 1
            h.total_successes += 1
            h.consecutive_failures = 0
            h.cooldown_until = 0.0
            h.cooldown_reason = ""
            h.last_success_at = time.time()

    # ─── usage accounting (metadata only) ───────────────────────────

    @staticmethod
    def _utc_date() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _rollover_check(self):
        today = self._utc_date()
        if today != self._today:
            self._today = today
            self._usage = {}
            self._loaded_day = None

    def _budget_reached(self, name: str) -> bool:
        if name != "openrouter" or cfg.OPENROUTER_DAILY_BUDGET <= 0:
            return False
        used = self._provider_requests_today(name)
        return used >= cfg.OPENROUTER_DAILY_BUDGET

    def _provider_requests_today(self, name: str) -> int:
        with self._lock:
            return sum(
                s.get("requests", 0)
                for (p, _, _), s in self._usage.items() if p == name
            )

    def _bump_usage(self, provider: str, model: str, profile: str,
                    success: bool, latency_ms: float,
                    input_tokens, output_tokens):
        with self._lock:
            self._rollover_check()
            key = (provider, model, profile)
            s = self._usage.setdefault(key, {
                "requests": 0, "successes": 0, "failures": 0,
                "input_tokens": 0, "output_tokens": 0,
                "total_latency_ms": 0.0, "latency_count": 0,
            })
            s["requests"] += 1
            if success:
                s["successes"] += 1
            else:
                s["failures"] += 1
            s["total_latency_ms"] += latency_ms or 0.0
            s["latency_count"] += 1
            if isinstance(input_tokens, int):
                s["input_tokens"] += input_tokens
            if isinstance(output_tokens, int):
                s["output_tokens"] += output_tokens

    def _persist_usage(self, provider: str, model: str, profile: str,
                       success: bool, latency_ms: float,
                       input_tokens, output_tokens):
        """Thread-pool db write — fire and forget, never blocks the reply."""
        def _write():
            try:
                from utils.db import record_ai_usage
                record_ai_usage(
                    usage_date=self._today,
                    provider=provider, model=model, profile=profile,
                    requests=1,
                    successes=1 if success else 0,
                    failures=0 if success else 1,
                    input_tokens=input_tokens if isinstance(input_tokens, int) else 0,
                    output_tokens=output_tokens if isinstance(output_tokens, int) else 0,
                    total_latency_ms=int(latency_ms or 0),
                )
            except Exception as e:
                logger.debug(f"[router] usage persist failed: {e}")
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, _write)
        except RuntimeError:
            _write()

    async def load_today_from_db(self):
        """Restore today's counters after a restart (Render recycles).

        OpenRouter budget counting must survive process restarts, so the
        in-memory dict is re-seeded from the persistent accounting table.
        """
        def _load():
            try:
                from utils.db import get_ai_usage_for_date
                return get_ai_usage_for_date(self._today)
            except Exception as e:
                logger.debug(f"[router] usage load failed: {e}")
                return []
        try:
            rows = await asyncio.to_thread(_load)
        except Exception:
            rows = []
        if not rows:
            return
        with self._lock:
            self._rollover_check()
            for r in rows:
                try:
                    key = (r["provider"], r["model"], str(r.get("profile", "")))
                    s = self._usage.setdefault(key, {
                        "requests": 0, "successes": 0, "failures": 0,
                        "input_tokens": 0, "output_tokens": 0,
                        "total_latency_ms": 0.0, "latency_count": 0,
                    })
                    s["requests"] = int(r.get("requests", 0))
                    s["successes"] = int(r.get("successes", 0))
                    s["failures"] = int(r.get("failures", 0))
                    s["input_tokens"] = int(r.get("input_tokens", 0) or 0)
                    s["output_tokens"] = int(r.get("output_tokens", 0) or 0)
                    s["total_latency_ms"] = float(r.get("total_latency_ms", 0) or 0)
                    s["latency_count"] = s["successes"] or 1
                except Exception:
                    continue
            self._loaded_day = self._today

    # ─── the route ──────────────────────────────────────────────────

    async def route(
        self,
        messages: list,
        profile: AIProfile,
        max_tokens: int = 300,
        temperature: float = 0.9,
    ) -> AIResult:
        """Send `messages` through the profile's chain; return the first
        sanitized success. Raises AIRoutingError when everything failed
        or nothing was configured."""
        steps = self._steps_for(profile)
        profile_str = profile.value if isinstance(profile, AIProfile) else str(profile)
        categories: list = []
        failed_over_from: list = []
        attempted = 0

        for idx, step in enumerate(steps):
            if attempted >= cfg.MAX_ATTEMPTS_PER_REQUEST:
                logger.warning(
                    f"[router] attempt cap ({cfg.MAX_ATTEMPTS_PER_REQUEST}) "
                    f"reached for {profile_str}"
                )
                break

            provider = self.providers.get(step.provider)
            if provider is None:
                continue
            if not provider.configured:
                categories.append(AIFailureCategory.UNCONFIGURED)
                continue  # unconfigured = skip, never a crash (Part 3)

            if self._breaker_open(step.provider):
                categories.append(AIFailureCategory.SERVER_ERROR)
                continue

            if self._budget_reached(step.provider):
                categories.append(AIFailureCategory.BUDGET_EXHAUSTED)
                logger.info(
                    f"[router] openrouter daily budget reached "
                    f"({self._provider_requests_today('openrouter')}/"
                    f"{cfg.OPENROUTER_DAILY_BUDGET}) — skipping"
                )
                continue

            # timeouts: first reasoning hop gets the long budget, the
            # tail of the chain gets the chat budget
            if profile == AIProfile.REASONING and idx > 0:
                timeout = cfg.REASONING_TAIL_TIMEOUT
            else:
                timeout = cfg.profile_timeout(profile)

            attempted += 1
            start = time.monotonic()
            try:
                raw = await provider.generate(
                    messages=messages,
                    model=step.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    reasoning_level=step.thinking_level,
                    timeout_seconds=timeout,
                )
                latency_ms = raw.latency_ms or (time.monotonic() - start) * 1000.0
                raw_had_content = bool((raw.text or "").strip())
                text = sanitize_output(raw.text)

                # PHASE N.1 / PART 6 — success accounting: a provider
                # call is a SUCCESS only when transport succeeded, the
                # payload parsed, AND visible content survived
                # sanitization. HTTP 200 with only hidden reasoning /
                # meta output is a FAILURE (SANITIZATION_EMPTY), counted
                # and failed over — never silently green.
                if is_empty_content(text):
                    cat = (AIFailureCategory.SANITIZATION_EMPTY
                           if raw_had_content
                           else AIFailureCategory.EMPTY_RESPONSE)
                    raise AIRequestError(
                        cat,
                        f"{step.provider} produced no visible content "
                        f"after sanitization"
                        if raw_had_content else
                        f"{step.provider} returned no visible content",
                        status_code=200,
                    )

                # ── success ──
                self._record_success(step.provider)
                self._bump_usage(step.provider, step.model, profile_str,
                                 True, latency_ms,
                                 raw.input_tokens, raw.output_tokens)
                self._persist_usage(step.provider, step.model, profile_str,
                                    True, latency_ms,
                                    raw.input_tokens, raw.output_tokens)
                self._touch_keep_alive(latency_ms)
                logger.info(
                    f"[router] {profile_str} → {step.provider}:{step.model} "
                    f"({latency_ms:.0f}ms, {len(text)} chars"
                    + (f", failover from {failed_over_from}" if failed_over_from else "")
                    + ")"
                )
                return AIResult(
                    text=text,
                    provider=step.provider,
                    model=step.model,
                    profile=profile_str,
                    latency_ms=latency_ms,
                    input_tokens=raw.input_tokens,
                    output_tokens=raw.output_tokens,
                    finish_reason=raw.finish_reason,
                    thinking_level=step.thinking_level,
                    failed_over_from=failed_over_from,
                )
            except AIRequestError as e:
                latency_ms = (time.monotonic() - start) * 1000.0
                self._record_failure(step.provider, e)
                self._bump_usage(step.provider, step.model, profile_str,
                                 False, latency_ms, None, None)
                self._persist_usage(step.provider, step.model, profile_str,
                                    False, latency_ms, None, None)
                categories.append(e.category)
                failed_over_from.append(step.provider)
                # PHASE N.1 — sanitized failure telemetry: category +
                # numeric status only. NEVER the exception text (provider
                # bodies can echo request fragments).
                logger.warning(
                    f"[router] {step.provider}:{step.model} failure "
                    f"category={e.category.value}"
                    + (f" status={e.status_code}" if e.status_code else "")
                    + (f" retry_after={e.retry_after:.0f}s"
                       if e.retry_after else "")
                    + f" ({latency_ms:.0f}ms) — failing over"
                )
                continue

        raise AIRoutingError(
            categories=categories,
            message=f"all providers failed for {profile_str}",
        )

    # ─── keep_alive metrics (same /health feed as the Groq era) ─────

    def _touch_keep_alive(self, latency_ms: float):
        if not self._keep_alive_metrics:
            return
        try:
            import keep_alive as kl
            kl.total_ai_calls += 1
            kl.recent_response_times.append(latency_ms)
            if len(kl.recent_response_times) > 100:
                kl.recent_response_times.pop(0)
        except Exception:
            pass

    # ─── observability (Phase N Part 15) ────────────────────────────

    def status_snapshot(self) -> dict:
        """Sanitized status for owner tooling + dashboard. Contains NO
        secrets, NO prompts, NO raw error strings — categories only."""
        with self._lock:
            self._rollover_check()
            providers = {}
            for name, provider in self.providers.items():
                h = self._health.get(name, ProviderHealth())
                today = {}
                for (p, model, prof), s in self._usage.items():
                    if p != name:
                        continue
                    today.setdefault(model, {
                        "requests": 0, "successes": 0, "failures": 0,
                        "avg_latency_ms": 0.0,
                    })
                    t = today[model]
                    t["requests"] += s["requests"]
                    t["successes"] += s["successes"]
                    t["failures"] += s["failures"]
                    cnt = max(1, s.get("latency_count", 1))
                    t["avg_latency_ms"] = round(
                        (t["avg_latency_ms"] + s["total_latency_ms"] / cnt) / 2, 1
                    ) if t["avg_latency_ms"] else round(s["total_latency_ms"] / cnt, 1)

                cooldown_left = max(
                    0, int(h.cooldown_until - time.monotonic())
                ) if h.cooldown_until > time.monotonic() else 0

                providers[name] = {
                    "configured": provider.configured,
                    "state": h.state(provider.configured),
                    "models": provider.model_ids() if provider.configured else {},
                    "today": {
                        "requests": sum(t["requests"] for t in today.values()),
                        "successes": sum(t["successes"] for t in today.values()),
                        "failures": sum(t["failures"] for t in today.values()),
                    },
                    "per_model": today,
                    "last_error_category": h.last_error_category,
                    "last_error_status": h.last_error_status,
                    "last_success_at": h.last_success_at,
                    "cooldown_seconds_left": cooldown_left,
                    "cooldown_reason": h.cooldown_reason if cooldown_left else "",
                }

            chains = {}
            for prof in AIProfile:
                steps = self._steps_for(prof)
                chains[prof.value] = [
                    {"provider": s.provider, "model": s.model,
                     "thinking": s.thinking_level}
                    for s in steps
                ]

            configured = [n for n, p in providers.items() if p["configured"]]
            # PHASE N.1 — "operational" requires at least one provider
            # in the genuine "healthy" state (a real request succeeded
            # recently and nothing failed since). "unknown" providers
            # (key present, never verified) don't make the AI green, but
            # they don't mark it down either.
            healthy = [n for n in configured if providers[n]["state"] == "healthy"]
            in_cooldown = [
                n for n in configured
                if providers[n]["state"] in (
                    "cooldown", "auth_error", "model_unavailable",
                    "degraded",
                )
            ]
            if not configured:
                ai_status = "down"
            elif healthy and not in_cooldown:
                ai_status = "operational"
            elif healthy and in_cooldown:
                ai_status = "degraded"
            elif in_cooldown:
                # no healthy provider left: hard config/model errors mean
                # the AI is effectively down; soft cooldowns mean degraded
                ai_status = "down" if all(
                    providers[n]["state"] in ("auth_error", "model_unavailable")
                    for n in in_cooldown
                ) else "degraded"
            else:
                # configured but nothing verified yet (fresh restart)
                ai_status = "unknown"

            snapshot = {
                "router_enabled": cfg.ROUTER_ENABLED,
                "ai_status": ai_status,
                "providers": providers,
                "routes": chains,
                "openrouter": {
                    "daily_budget": cfg.OPENROUTER_DAILY_BUDGET,
                    "requests_today": self._provider_requests_today("openrouter"),
                },
                "privacy": {
                    "allow_gemini_sensitive": cfg.ALLOW_GEMINI_SENSITIVE,
                    "allow_openrouter_sensitive": cfg.ALLOW_OPENROUTER_SENSITIVE,
                    "sensitive_providers": ["mistral", "groq"],
                    "note": (
                        "sensitive requests (moderation, automod) route to "
                        "mistral → groq by default; gemini/openrouter are "
                        "opt-in via explicit allow flags. privacy opt-outs "
                        "are enforced before any provider is invoked."
                    ),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        return snapshot


# ─── module-level singleton ─────────────────────────────────────────

_router: AIRouter | None = None
_router_lock = threading.Lock()


def get_router() -> AIRouter:
    global _router
    with _router_lock:
        if _router is None:
            _router = AIRouter()
        return _router


def set_router(router: AIRouter | None):
    """Test/ops hook: inject a router with fake providers, or reset."""
    global _router
    with _router_lock:
        _router = router


async def init_ai_router() -> AIRouter:
    """Warm up the singleton and re-seed today's usage counters from the
    persistent accounting store (called from main.py on_ready)."""
    router = get_router()
    await router.load_today_from_db()
    return router
