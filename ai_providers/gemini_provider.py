"""
ai_providers/gemini_provider.py — PHASE N Google Gemini adapter.

Uses the CURRENT official Python SDK (`google-genai` — the successor of
the deprecated `google-generativeai` package), async surface
(`client.aio.models.generate_content`).

Message mapping (Phase N Part 6):
  * system messages  -> GenerateContentConfig.system_instruction
  * assistant role   -> Gemini "model" role
  * user role        -> user role (normal)
  * conversation order preserved

Thinking controls:
  * reasoning_level "low"  -> ThinkingConfig(thinking_level=LOW)  (routine chat)
  * reasoning_level "high" -> ThinkingConfig(thinking_level=HIGH) (hard fallback)

PHASE N.1 / PART 2 — AUTOMATIC FUNCTION CALLING IS EXPLICITLY DISABLED:
`GenerateContentConfig(automatic_function_calling=
AutomaticFunctionCallingConfig(disable=True))` on EVERY ordinary text
generation. Root cause of the production log noise ("AFC is enabled with
max remote calls: 10" + "Direct use of automatic function calling (AFC)
in AsyncModels.generate_content is not recommended"): google-genai
defaults AFC to ENABLED on the async models path even when no tools are
attached, which routes the call through the AFC loop instead of the
plain `_generate_content` request. With `disable=True` the SDK's
`should_disable_afc()` predicate short-circuits to the plain request —
no AFC loop, no warnings. Verified against google-genai 2.22.0
(`_extra_utils.should_disable_afc` + `models.AsyncModels.generate_content`).

NO external grounding: the Google search / web tools are never enabled —
aurelia must not unexpectedly search the internet just because Gemini
supports it. No `tools` are ever attached to ordinary generation.

SENSITIVE routing: this adapter is never called for sensitive requests
unless AI_ALLOW_GEMINI_SENSITIVE=true — the ROUTER enforces that; the
adapter itself is transport-only.
"""
import asyncio
import logging
import re
import time

from ai_providers.base import AIProvider
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory

logger = logging.getLogger('cyn.ai.gemini')

_SDK_IMPORT_ERROR = None
try:  # graceful: missing SDK = unconfigured, never a crash
    from google import genai as _genai
    from google.genai import types as _gtypes
except Exception as _e:  # pragma: no cover
    _genai = None
    _gtypes = None
    _SDK_IMPORT_ERROR = _e


_ROLE_MAP = {"system": None, "user": "user", "assistant": "model", "tool": "user"}


def _classify_error(exc: Exception) -> AIRequestError:
    """Map a google-genai exception to a normalized AIRequestError.

    Phase N.1: uses the numeric HTTP status from the SDK's own exception
    classes (`google.genai.errors.ClientError/ServerError.code`) when
    present — string sniffing is only the fallback. 400 (request shape)
    is BAD_REQUEST, NOT MODEL_UNAVAILABLE; only real 404/not-found/
    decommissioned/unsupported-model signals are MODEL_UNAVAILABLE, so
    cooldowns and the owner status card stop lying about "model gone".
    `message` stays INTERNAL (bounded, never logged verbatim in
    production); telemetry uses category + status_code only.
    """
    status_code = None
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        status_code = code
    text = f"{type(exc).__name__}: {exc}".lower()
    if status_code is None:
        m = re.search(r"\b(4\d\d|5\d\d)\b", text)
        if m:
            status_code = int(m.group(1))

    if status_code == 429 or "resource_exhausted" in text or "rate" in text:
        # google-genai surfaces RetryInfo ("429s" retry delay) inside the
        # message; extract a plain seconds number when present.
        retry_after = None
        m = re.search(r"(\d+(?:\.\d+)?)s", text)
        if m:
            try:
                retry_after = float(m.group(1))
            except ValueError:
                retry_after = None
        return AIRequestError(AIFailureCategory.RATE_LIMIT, text[:300],
                              retry_after, status_code=429)
    if status_code in (401, 403) or "unauthenticated" in text \
            or "permission" in text:
        return AIRequestError(AIFailureCategory.AUTH, text[:300],
                              status_code=status_code or 401)
    if status_code == 404 or "not found" in text or "not_found" in text \
            or "decommissioned" in text or "model_not_found" in text \
            or ("model" in text and "unsupported" in text):
        return AIRequestError(AIFailureCategory.MODEL_UNAVAILABLE, text[:300],
                              status_code=status_code or 404)
    if status_code == 400 or "invalid_argument" in text \
            or "bad request" in text:
        return AIRequestError(AIFailureCategory.BAD_REQUEST, text[:300],
                              status_code=400)
    if "timeout" in text or "deadline" in text:
        return AIRequestError(AIFailureCategory.TIMEOUT, text[:300])
    if status_code is not None and status_code >= 500 \
            or "unavailable" in text or "overloaded" in text \
            or "internal" in text:
        return AIRequestError(AIFailureCategory.SERVER_ERROR, text[:300],
                              status_code=status_code)
    return AIRequestError(AIFailureCategory.UNKNOWN, text[:300],
                          status_code=status_code)


class GeminiProvider(AIProvider):
    name = "gemini"
    api_key_env = "GEMINI_API_KEY"

    def _client_or_raise(self):
        if _genai is None:
            raise AIRequestError(
                AIFailureCategory.UNCONFIGURED,
                f"google-genai SDK unavailable ({_SDK_IMPORT_ERROR})",
            )
        if not self.configured:
            raise self._unconfigured()
        if self._client is None:
            # Default transport is REST (httpx) — no gRPC deps required.
            self._client = _genai.Client(api_key=self._api_key)
        return self._client

    def _map_messages(self, messages: list):
        """OpenAI-style messages -> (contents, system_instruction)."""
        system_parts = []
        contents = []
        for msg in messages:
            role = str(msg.get("role", "user")).lower()
            content = str(msg.get("content", "") or " ")
            if role == "system":
                system_parts.append(content)
                continue
            gemini_role = _ROLE_MAP.get(role, "user")
            if gemini_role is None:  # defensive
                system_parts.append(content)
                continue
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
        if not contents:
            # everything was system — still need one user turn
            contents.append({"role": "user", "parts": [{"text": " "}]})
        return contents, ("\n\n".join(system_parts) if system_parts else None)

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
        contents, system_instruction = self._map_messages(messages)

        thinking_cfg = None
        if reasoning_level in ("high", "low") and _gtypes is not None:
            try:
                level = _gtypes.ThinkingLevel.HIGH if reasoning_level == "high" \
                    else _gtypes.ThinkingLevel.LOW
                thinking_cfg = _gtypes.ThinkingConfig(thinking_level=level)
            except Exception:
                thinking_cfg = None

        # PHASE N.1 / PART 2 — explicitly disable automatic function
        # calling on EVERY ordinary text generation. google-genai defaults
        # AFC to enabled on the async models path even with no tools,
        # which both logs the noisy AFC warnings and routes the call
        # through the AFC loop. `disable=True` makes the SDK take the plain
        # request path (see module docstring). `tools` is never set — no
        # grounding, no function calling, nothing implicit.
        afc_disable_cfg = None
        if _gtypes is not None:
            try:
                afc_disable_cfg = _gtypes.AutomaticFunctionCallingConfig(
                    disable=True,
                )
            except Exception:
                afc_disable_cfg = None

        config_kwargs = {
            "temperature": max(0.0, min(2.0, float(temperature))),
            "max_output_tokens": int(max_tokens),
        }
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        if thinking_cfg is not None:
            config_kwargs["thinking_config"] = thinking_cfg
        if afc_disable_cfg is not None:
            config_kwargs["automatic_function_calling"] = afc_disable_cfg
        config = _gtypes.GenerateContentConfig(**config_kwargs)

        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise AIRequestError(AIFailureCategory.TIMEOUT,
                                 f"gemini timeout after {timeout_seconds}s")
        except Exception as e:
            raise _classify_error(e)

        latency_ms = (time.monotonic() - start) * 1000.0

        # ── extract text ───────────────────────────────────────────
        text = ""
        try:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                parts = getattr(candidates[0], "content", None)
                parts = getattr(parts, "parts", None) or []
                chunks = []
                for p in parts:
                    t = getattr(p, "text", None)
                    if isinstance(t, str):
                        chunks.append(t)
                text = "".join(chunks)
        except Exception as e:
            raise AIRequestError(AIFailureCategory.INVALID_RESPONSE,
                                 f"gemini response parse: {e}")

        usage = getattr(response, "usage_metadata", None)

        def _u(field):
            v = getattr(usage, field, None)
            return int(v) if isinstance(v, int) else None

        finish = None
        try:
            if candidates:
                finish = getattr(candidates[0], "finish_reason", None)
                finish = str(finish).split(".")[-1].lower() if finish is not None else None
        except Exception:
            finish = None

        return AIResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            input_tokens=_u("prompt_token_count"),
            output_tokens=_u("candidates_token_count"),
            finish_reason=finish,
            thinking_level=reasoning_level,
        )

    def model_ids(self) -> dict:
        from utils import ai_config as cfg
        return {"chat": cfg.GEMINI_CHAT_MODEL}
