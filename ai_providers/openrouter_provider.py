"""
ai_providers/openrouter_provider.py — PHASE N OpenRouter (GLM) adapter.

OpenRouter exposes an OpenAI-compatible REST API and has no official
Python SDK, so this adapter uses aiohttp (already a discord.py dependency
— no new HTTP library, per Phase N Part 18).

Model: z-ai/glm-5.2:free — RESERVED for difficult requests (the REASONING
profile). Ordinary chat must never reach this provider; the router's
chain definitions enforce that.

Reasoning effort: for reasoning-profile calls the request carries
`reasoning: {"effort": AI_OPENROUTER_REASONING_EFFORT}` (default "high"),
the OpenRouter-standard way to ask reasoning models to think hard. Set
AI_OPENROUTER_REASONING_EFFORT="" to disable sending it entirely.

DAILY BUDGET GUARD (Phase N Part 8): the budget itself lives in the
ROUTER (single failover owner) and is backed by the persistent
ai_provider_usage accounting — this adapter is pure transport and never
counts or blocks on its own.
"""
import asyncio
import json
import logging
import os
import re
import time

import aiohttp

from ai_providers.base import AIProvider
from utils.ai_types import AIResult, AIRequestError, AIFailureCategory

logger = logging.getLogger('cyn.ai.openrouter')

OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"

_RETRY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def _classify_error(status: int, body: str) -> AIRequestError:
    """OpenRouter REST status -> normalized AIRequestError.

    Phase N.1: 400 (request shape) is BAD_REQUEST; 404 stays
    MODEL_UNAVAILABLE (unknown/deprecated model slug). 402 is OpenRouter's
    payment-required signal — mapped to BUDGET_EXHAUSTED so the owner
    card can show the real story instead of a generic failure.
    `body` is INTERNAL only (bounded inside AIRequestError); telemetry
    uses category + status_code.
    """
    text = f"openrouter http {status}: {body}".lower()
    retry_after = None
    if status == 429:
        m = _RETRY_RE.search(text)
        if m:
            try:
                retry_after = float(m.group(1))
            except ValueError:
                retry_after = None
        return AIRequestError(AIFailureCategory.RATE_LIMIT, text[:300],
                              retry_after, status_code=429)
    if status in (401, 403):
        return AIRequestError(AIFailureCategory.AUTH, text[:300],
                              status_code=status)
    if status == 402:
        return AIRequestError(AIFailureCategory.BUDGET_EXHAUSTED,
                              text[:300], status_code=402)
    if status == 404:
        return AIRequestError(AIFailureCategory.MODEL_UNAVAILABLE,
                              text[:300], status_code=404)
    if status == 400:
        return AIRequestError(AIFailureCategory.BAD_REQUEST, text[:300],
                              status_code=400)
    if status >= 500:
        return AIRequestError(AIFailureCategory.SERVER_ERROR, text[:300],
                              status_code=status)
    return AIRequestError(AIFailureCategory.INVALID_RESPONSE, text[:300],
                          status_code=status)


class OpenRouterProvider(AIProvider):
    name = "openrouter"
    api_key_env = "OPENROUTER_API_KEY"

    def __init__(self, api_key: str | None = None):
        super().__init__(api_key)
        self.reasoning_effort = (os.getenv("AI_OPENROUTER_REASONING_EFFORT") or "high").strip()
        self._session = None

    async def _session_or_raise(self) -> aiohttp.ClientSession:
        if not self.configured:
            raise self._unconfigured()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=90),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    # Attribution headers OpenRouter recommends for apps
                    "HTTP-Referer": "https://aurelia.bot",
                    "X-Title": "Aurelia Discord Bot",
                },
            )
        return self._session

    async def generate(
        self,
        messages: list,
        model: str,
        max_tokens: int,
        temperature: float,
        reasoning_level: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> AIResult:
        session = await self._session_or_raise()

        payload = {
            "model": model,
            "messages": [
                {
                    "role": (str(m.get("role", "user")).lower()
                             if str(m.get("role", "user")).lower()
                             in ("system", "user", "assistant", "tool")
                             else "user"),
                    "content": str(m.get("content", "") or " "),
                }
                for m in messages
            ],
            "max_tokens": int(max_tokens),
            "temperature": max(0.0, min(2.0, float(temperature))),
        }
        if reasoning_level and self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}

        start = time.monotonic()
        try:
            async with session.post(
                OPENROUTER_BASE, json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise _classify_error(resp.status, body)
                data = json.loads(body)
        except asyncio.TimeoutError:
            raise AIRequestError(AIFailureCategory.TIMEOUT,
                                 f"openrouter timeout after {timeout_seconds}s")
        except aiohttp.ClientError as e:
            raise AIRequestError(AIFailureCategory.SERVER_ERROR,
                                 f"openrouter network: {e}")
        except json.JSONDecodeError as e:
            raise AIRequestError(AIFailureCategory.INVALID_RESPONSE,
                                 f"openrouter json: {e}")

        latency_ms = (time.monotonic() - start) * 1000.0

        # ── extract text (OpenAI-compatible shape) ─────────────────
        text = ""
        try:
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content")
                if isinstance(content, list):  # some models emit part lists
                    content = "".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                text = str(content or "")
        except Exception as e:
            raise AIRequestError(AIFailureCategory.INVALID_RESPONSE,
                                 f"openrouter response parse: {e}")

        usage = data.get("usage") or {}

        return AIResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=choices[0].get("finish_reason") if choices else None,
            thinking_level=reasoning_level if reasoning_level else None,
        )

    async def close(self):
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None

    def model_ids(self) -> dict:
        from utils import ai_config as cfg
        return {"reasoning": cfg.OPENROUTER_REASONING_MODEL}
