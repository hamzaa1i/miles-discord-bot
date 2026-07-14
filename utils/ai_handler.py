"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with llama-3.3-70b-versatile for
high quality responses and llama-3.1-8b-instant for fast short responses.
"""
import os
from groq import AsyncGroq

_client: AsyncGroq | None = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        _client = AsyncGroq(api_key=api_key)
    return _client

async def call_ai(
    messages: list,
    model: str = "llama-3.3-70b-versatile",
    max_tokens: int = 300,
    temperature: float = 0.9
) -> str:
    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI Error] {type(e).__name__}: {e}")
        return "something broke on my end. try again."

async def call_ai_fast(
    messages: list,
    max_tokens: int = 150
) -> str:
    return await call_ai(
        messages,
        model="llama-3.1-8b-instant",
        max_tokens=max_tokens,
        temperature=0.85
    )
