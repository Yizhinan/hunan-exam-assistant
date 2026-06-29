"""
DeepSeek API client wrapper (OpenAI-compatible).

Provides a thin abstraction over the OpenAI SDK pointed at DeepSeek's endpoint.
"""

import json
from typing import TypeVar, Generic

from openai import OpenAI

from app.core.config import get_settings

T = TypeVar("T")
settings = get_settings()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazy-init OpenAI client pointed at DeepSeek."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client


def chat(
    system_prompt: str,
    user_message: str,
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    Simple chat completion — returns the model's text response.

    Args:
        system_prompt: System-level instruction
        user_message: User message (or combined prompt)
        model: DeepSeek model name
        temperature: Lower = more deterministic (good for grading)
        max_tokens: Max response tokens
    """
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content or ""


def chat_json(
    system_prompt: str,
    user_message: str,
    model: str = "deepseek-chat",
    temperature: float = 0.2,
) -> dict:
    """
    Chat completion that expects a JSON response.
    Uses response_format to enforce JSON output.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)
