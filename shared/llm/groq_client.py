"""
Groq client — free-tier alternative to claude_client.py, same call
signature so matcher.py doesn't care which one is active (see llm_client.py).
"""
import os

from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def call_groq(system: str, user_message: str, max_tokens: int = 1024) -> str:
    if client is None:
        raise RuntimeError("GROQ_API_KEY not set")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content