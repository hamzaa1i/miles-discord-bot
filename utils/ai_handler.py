"""
utils/ai_handler.py — Single source of truth for all AI calls.

Uses Groq API (console.groq.com) with llama3-70b for complex tasks
and mixtral-8x7b for fast one-liners.
"""
import os
from groq import AsyncGroq

_client = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return _client

async def call_ai(
    messages: list,
    model: str = "llama3-70b-8192",
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
        print(f"[AI Error] {e}")
        return "something broke on my end. try again."

async def call_ai_fast(messages: list, max_tokens: int = 150) -> str:
    return await call_ai(
        messages,
        model="mixtral-8x7b-32768",
        max_tokens=max_tokens,
        temperature=0.85
    )
