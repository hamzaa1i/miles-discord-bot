"""
ai_providers/__init__.py — PHASE N provider package.

Exports the four adapters. Importing a module here never requires its SDK
to be installed — every adapter degrades to UNCONFIGURED when its SDK or
API key is missing, so a partial deployment (Groq-only) boots exactly
like today.
"""
from ai_providers.base import AIProvider
from ai_providers.gemini_provider import GeminiProvider
from ai_providers.mistral_provider import MistralProvider
from ai_providers.openrouter_provider import OpenRouterProvider
from ai_providers.groq_provider import GroqProvider

__all__ = [
    "AIProvider",
    "GeminiProvider",
    "MistralProvider",
    "OpenRouterProvider",
    "GroqProvider",
]
