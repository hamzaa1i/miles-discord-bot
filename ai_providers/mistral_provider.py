"""
ai_providers/mistral_provider.py — PHASE N Mistral adapter.

Uses Mistral's official Python SDK (`mistralai`). Supports both the v1
line (`from mistralai import Mistral`) and the v2 line
(`from mistralai.client import Mistral`) — both expose
`client.chat.complete_async(model=..., messages=..., ...)`.

Mistral's roles (Phase N Part 7):
  * system    -> system (supported natively)
  * user      -> user
  * assistant -> assistant
Plain TypedDict-style dicts ({"role": ..., "content": ...}) are accepted
by both SDK lines, so the normalized message list passes straight through.

Error handling: timeouts, 429, 5xx, malformed response, empty response,
auth/config failure — all normalized into AIRequestError categories. No
retries, no fallbacks (the router owns failover).

Role in routing: FIRST fallback after Gemini for normal chat, PRIMARY
provider for sensitive requests (EU hosting, no training on API data),
and a reasoning fallback where appropriate.
"""
import asyncio
import logging
import re
import time

from ai_providers.base import AIProvider
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory

logger = logging.getLogger('cyn.ai.mistral')

_Mistral = None
_SDK_IMPORT_ERROR = None
try:  # v2 line first (current PyPI), then v1 line — both work identically
    from mistralai.client import Mistral as _Mistral  # type: ignore
except Exception:
    try:
        from mistralai import Mistral as _Mistral  # type: ignore
    except Exception as _e:  # pragma: no cover
        _Mistral = None
        _SDK_IMPORT_ERROR = _e

_RETRY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def _classify_error(exc: Exception) -> AIRequestError:
    """Map a mistralai SDK exception to a normalized AIRequestError.

    Phase N.1: the mistralai 2.x SDK raises
    `mistralai.client.errors.sdkerror.SDKError` with a numeric
    `status_code` attribute (verified against mistralai 2.9.4:
    str(exc) == "API error occurred: Status 401. Body: {...}").
    The numeric status is authoritative — string sniffing is only the
    fallback for exceptions raised client-side (timeouts, connection
    resets). 400 (request shape) is BAD_REQUEST, not MODEL_UNAVAILABLE;
    only 404 / unknown-model / decommissioned signals are
    MODEL_UNAVAILABLE so the status card stops mislabeling request-shape
    errors as "model gone".
    """
    status_code = getattr(exc, "status_code", None)
    if not isinstance(status_code, int):
        status_code = None
    text = f"{type(exc).__name__}: {exc}".lower()
    if status_code is None:
        m = re.search(r"status (\d{3})", text)
        if m:
            status_code = int(m.group(1))

    if status_code == 429 or "rate limit" in text or "429" in text:
        retry_after = None
        m = _RETRY_RE.search(text)
        if m:
            try:
                retry_after = float(m.group(1))
            except ValueError:
                retry_after = None
        return AIRequestError(AIFailureCategory.RATE_LIMIT, text[:300],
                              retry_after, status_code=429)
    if status_code in (401, 403) or "unauthorized" in text \
            or "forbidden" in text or "invalid api key" in text:
        return AIRequestError(AIFailureCategory.AUTH, text[:300],
                              status_code=status_code or 401)
    if status_code == 404 or "not found" in text or "unknown model" in text \
            or "model_not_found" in text or "decommissioned" in text \
            or ("model" in text and "not" in text):
        return AIRequestError(AIFailureCategory.MODEL_UNAVAILABLE, text[:300],
                              status_code=status_code or 404)
    if status_code == 400 or "bad request" in text:
        return AIRequestError(AIFailureCategory.BAD_REQUEST, text[:300],
                              status_code=400)
    if "timeout" in text or "timed out" in text:
        return AIRequestError(AIFailureCategory.TIMEOUT, text[:300])
    if status_code is not None and status_code >= 500 \
            or "service unavailable" in text or "5xx" in text:
        return AIRequestError(AIFailureCategory.SERVER_ERROR, text[:300],
                              status_code=status_code)
    return AIRequestError(AIFailureCategory.UNKNOWN, text[:300],
                          status_code=status_code)


class MistralProvider(AIProvider):
    name = "mistral"
    api_key_env = "MISTRAL_API_KEY"

    def _client_or_raise(self):
        if _Mistral is None:
            raise AIRequestError(
                AIFailureCategory.UNCONFIGURED,
                f"mistralai SDK unavailable ({_SDK_IMPORT_ERROR})",
            )
        if not self.configured:
            raise self._unconfigured()
        if self._client is None:
            self._client = _Mistral(api_key=self._api_key)
        return self._client

    @staticmethod
    def _map_messages(messages: list) -> list:
        """Normalized OpenAI-style dicts pass through; only 'tool' roles
        need coercion (not used by aurelia today)."""
        out = []
        for msg in messages:
            role = str(msg.get("role", "user")).lower()
            if role not in ("system", "user", "assistant"):
                role = "user"
            out.append({"role": role, "content": str(msg.get("content", "") or " ")})
        return out

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
        payload = self._map_messages(messages)

        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.complete_async(
                    model=model,
                    messages=payload,
                    temperature=max(0.0, min(2.0, float(temperature))),
                    max_tokens=int(max_tokens),
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise AIRequestError(AIFailureCategory.TIMEOUT,
                                 f"mistral timeout after {timeout_seconds}s")
        except Exception as e:
            raise _classify_error(e)

        latency_ms = (time.monotonic() - start) * 1000.0

        # ── extract text ───────────────────────────────────────────
        text = ""
        try:
            choices = getattr(response, "choices", None) or []
            if choices:
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    text = content
        except Exception as e:
            raise AIRequestError(AIFailureCategory.INVALID_RESPONSE,
                                 f"mistral response parse: {e}")

        usage = getattr(response, "usage", None)

        def _u(field):
            v = getattr(usage, field, None)
            return int(v) if isinstance(v, int) else None

        finish = None
        try:
            choices = getattr(response, "choices", None) or []
            if choices:
                finish = getattr(choices[0], "finish_reason", None)
                finish = str(finish).split(".")[-1].lower() if finish is not None else None
        except Exception:
            finish = None

        return AIResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            input_tokens=_u("prompt_tokens"),
            output_tokens=_u("completion_tokens"),
            finish_reason=finish,
        )

    def model_ids(self) -> dict:
        from utils import ai_config as cfg
        return {"chat": cfg.MISTRAL_MODEL}
