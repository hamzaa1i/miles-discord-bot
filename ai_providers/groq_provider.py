"""
ai_providers/groq_provider.py — PHASE N Groq adapter (emergency tier).

Wraps the existing `groq` SDK behind the standard provider interface.
Groq remains the always-on emergency floor: when every other provider is
unconfigured, rate-limited or down, the chains collapse to Groq and
aurelia behaves exactly like the pre-Phase-N deployment.

The robust field-juggling from the legacy _extract_content (content /
reasoning / reasoning_content / tool_calls) lives here for Groq's
response shape — the router still runs the shared sanitization pipeline
on whatever comes out.

No internal fallback, no retries: the ROUTER owns failover. The old
in-handler MODEL_CHAT -> MODEL_FALLBACK dance is now expressed as two
consecutive Groq steps in the router's chains.
"""
import asyncio
import logging
import re
import time

from ai_providers.base import AIProvider
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory

logger = logging.getLogger('cyn.ai.groq')

_AsyncGroq = None
_SDK_IMPORT_ERROR = None
try:
    from groq import AsyncGroq as _AsyncGroq  # type: ignore
except Exception as _e:  # pragma: no cover
    _AsyncGroq = None
    _SDK_IMPORT_ERROR = _e

_RETRY_RE = re.compile(r"try again in (\d+m[\d.]+s|\d+\.\d+s|\d+s)", re.IGNORECASE)


def _classify_error(exc: Exception) -> AIRequestError:
    """Map a groq SDK exception to a normalized AIRequestError.

    Phase N.1: 400 (request shape, e.g. a bad parameter) is BAD_REQUEST,
    NOT MODEL_UNAVAILABLE — only 404 / model_not_found / decommissioned
    signals are MODEL_UNAVAILABLE, so breaker policy and the owner
    status card stop mislabeling request-shape errors as "model gone".
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    status_code = None
    m = re.search(r"\b(4\d\d|5\d\d)\b", text)
    if m:
        status_code = int(m.group(1))
    retry_after = None
    if "429" in text or "rate limit" in text or "rate_limit" in text \
            or "ratelimit" in text or "too many requests" in text:
        m = _RETRY_RE.search(text)
        if m:
            unit = m.group(1)
            try:
                if unit.endswith("m"):
                    retry_after = float(unit[:-1]) * 60
                else:
                    retry_after = float(unit.rstrip("s"))
            except ValueError:
                retry_after = None
        return AIRequestError(AIFailureCategory.RATE_LIMIT, text[:300],
                              retry_after, status_code=429)
    if "401" in text or "403" in text or "invalid api key" in text or "unauthorized" in text:
        return AIRequestError(AIFailureCategory.AUTH, text[:300],
                              status_code=status_code or 401)
    if "404" in text or "model_not_found" in text or "model not found" in text \
            or "does not exist" in text or "decommissioned" in text \
            or "not_available" in text:
        return AIRequestError(AIFailureCategory.MODEL_UNAVAILABLE, text[:300],
                              status_code=status_code or 404)
    if "400" in text or "bad request" in text or "invalid_request" in text:
        return AIRequestError(AIFailureCategory.BAD_REQUEST, text[:300],
                              status_code=400)
    if "timeout" in text or "timed out" in text:
        return AIRequestError(AIFailureCategory.TIMEOUT, text[:300])
    if "503" in text or "502" in text or "504" in text or "500" in text or "service unavailable" in text:
        return AIRequestError(AIFailureCategory.SERVER_ERROR, text[:300],
                              status_code=status_code)
    return AIRequestError(AIFailureCategory.UNKNOWN, text[:300],
                          status_code=status_code)


class GroqProvider(AIProvider):
    name = "groq"
    api_key_env = "GROQ_API_KEY"

    def _client_or_raise(self):
        if _AsyncGroq is None:
            raise AIRequestError(
                AIFailureCategory.UNCONFIGURED,
                f"groq SDK unavailable ({_SDK_IMPORT_ERROR})",
            )
        if not self.configured:
            raise self._unconfigured()
        if self._client is None:
            self._client = _AsyncGroq(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list,
        model: str,
        max_tokens: int,
        temperature: float,
        reasoning_level: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> AIResult:
        client = self._client_or_raise()

        payload = []
        for m in messages:
            role = str(m.get("role", "user")).lower()
            if role not in ("system", "user", "assistant", "tool"):
                role = "user"
            payload.append({"role": role, "content": str(m.get("content", "") or " ")})

        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=payload,
                    max_tokens=int(max_tokens),
                    temperature=max(0.0, min(2.0, float(temperature))),
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise AIRequestError(AIFailureCategory.TIMEOUT,
                                 f"groq timeout after {timeout_seconds}s")
        except Exception as e:
            raise _classify_error(e)

        latency_ms = (time.monotonic() - start) * 1000.0

        # ── robust extraction (legacy FIX 2 field order) ───────────
        text = ""
        try:
            if response and response.choices:
                msg = response.choices[0].message
                content = (getattr(msg, "content", None) or "").strip()
                if not content:
                    rc = getattr(msg, "reasoning_content", None)
                    if rc:
                        content = rc.strip()
                if not content:
                    r = getattr(msg, "reasoning", None)
                    if r:
                        content = r.strip()
                text = content
        except Exception as e:
            raise AIRequestError(AIFailureCategory.INVALID_RESPONSE,
                                 f"groq response parse: {e}")

        usage = getattr(response, "usage", None) if response is not None else None

        def _u(field):
            v = getattr(usage, field, None)
            return int(v) if isinstance(v, int) else None

        finish = None
        try:
            if response and response.choices:
                finish = response.choices[0].finish_reason
        except Exception:
            finish = None

        return AIResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            input_tokens=_u("prompt_tokens"),
            output_tokens=_u("completion_tokens"),
            finish_reason=str(finish) if finish is not None else None,
        )

    def model_ids(self) -> dict:
        from utils.ai_config import (
            GROQ_CHAT_MODEL, GROQ_CHAT_FALLBACK_MODEL,
            GROQ_FAST_MODEL, GROQ_REASONING_MODEL,
        )
        return {
            "chat": GROQ_CHAT_MODEL,
            "chat_fallback": GROQ_CHAT_FALLBACK_MODEL,
            "fast": GROQ_FAST_MODEL,
            "reasoning": GROQ_REASONING_MODEL,
        }
