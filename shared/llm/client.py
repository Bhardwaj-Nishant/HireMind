"""
Provider selector — lets matcher.py (and later generation logic) call
`call_llm(...)` without caring whether Claude or Groq is behind it.

Switch providers with the LLM_PROVIDER env var:
    LLM_PROVIDER=claude  -> uses claude_client.py (paid, needs ANTHROPIC_API_KEY)
    LLM_PROVIDER=groq    -> uses groq_client.py (free tier, needs GROQ_API_KEY)

Defaults to groq since it's free — switch to claude once you've topped up
Anthropic credits, by setting LLM_PROVIDER=claude.
"""
import os

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()


def call_llm(system: str, user_message: str, max_tokens: int = 1024) -> str:
    if LLM_PROVIDER == "claude":
        from shared.llm.claude_client import call_claude

        return call_claude(system, user_message, max_tokens=max_tokens)

    if LLM_PROVIDER == "groq":
        from shared.llm.groq_client import call_groq

        return call_groq(system, user_message, max_tokens=max_tokens)

    raise ValueError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}' — expected 'claude' or 'groq'")