"""
ai_providers/base.py — PHASE N standard provider interface.

Provider adapters translate ONE provider's API and nothing else
(Phase N Part 4):
  * no fallback chains — the ROUTER is the single failover owner
  * no prompt construction — cogs build messages, providers transport them
  * no sanitization — utils/ai_sanitize owns the output pipeline; the
    router runs it on every result

Messages arrive in Aurelia's normalized OpenAI-style shape:
    [{"role": "system"|"user"|"assistant", "content": str}, ...]
Each adapter maps that to its provider's native format.
"""
import abc
import functools
import os

from utils.ai_types import AIResult, AIRequestError, AIFailureCategory


class AIProvider(abc.ABC):
    """Base class for all AI provider adapters."""

    #: lowercase provider key ("gemini", "mistral", "openrouter", "groq")
    name: str = "base"

    #: env var holding this provider's API key (server-side ONLY — never
    #: mirrored into the Next.js client bundle)
    api_key_env: str = ""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else self._default_key()
        self._client = None  # lazy SDK client cache

    def _default_key(self) -> str | None:
        return (os.getenv(self.api_key_env) or "").strip() or None

    # ── configuration state ────────────────────────────────────────
    @property
    def configured(self) -> bool:
        """A missing API key means the provider is UNCONFIGURED — the
        router simply skips it (never an error, never a broken badge)."""
        return bool(self._api_key)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    # ── shared helpers ─────────────────────────────────────────────
    def _unconfigured(self) -> AIRequestError:
        return AIRequestError(
            AIFailureCategory.UNCONFIGURED,
            "provider api key not set",
        )

    def require_configured(fn):
        """Decorator: raise UNCONFIGURED before touching the SDK."""

        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            if not self.configured:
                raise self._unconfigured()
            return await fn(self, *args, **kwargs)

        return wrapper

    # ── the one method every adapter implements ────────────────────
    @abc.abstractmethod
    async def generate(
        self,
        messages: list,
        model: str,
        max_tokens: int,
        temperature: float,
        reasoning_level: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> AIResult:
        """Send `messages` to `model` and return a normalized AIResult.

        Raises AIRequestError (with a category) on any failure — the
        adapter NEVER retries and NEVER falls back on its own.
        """
        raise NotImplementedError

    def model_ids(self) -> dict:
        """Active model ids this provider may be asked for (for status
        display). Subclasses override."""
        return {}

    async def close(self):
        """Release SDK resources if any (client caches etc.)."""
        self._client = None
