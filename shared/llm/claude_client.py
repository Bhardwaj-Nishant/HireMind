"""
Shared Claude client for intelligence-service.

Used by matcher.py now, and later by generation logic (resume/cover
letter/email drafting) that will live in this same service.
"""
import os

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


def call_claude(system: str, user_message: str, max_tokens: int = 1024) -> str:
    """Single-turn call, returns the text of the first content block.
    Raises if Claude returns no text block (e.g. only a refusal stop)."""
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError("No text content in Claude response")