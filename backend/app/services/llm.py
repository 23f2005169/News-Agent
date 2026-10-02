"""LLM client helpers."""
from __future__ import annotations

"""
backend/app/services/llm.py

Config loader (kept from the existing scaffold) + the actual chat
completion call for the explainer feature, using httpx to match the
rest of the project's HTTP client choice.
"""

import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


def get_llm_config() -> LLMConfig | None:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return LLMConfig(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        # Default changed from the free placeholder model to the real
        # production model, now that the explainer is the live feature.
        model=os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5"),
    )


def build_http_client() -> httpx.Client:
    return httpx.Client(timeout=60.0)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int = 4096,
    temperature: float = 0.4,
) -> str:
    config = get_llm_config()
    if config is None:
        raise RuntimeError("No LLM API key configured (OPENROUTER_API_KEY or ANTHROPIC_API_KEY).")

    payload = {
        "model": config.model,
        "temperature": temperature,
        "max_tokens": max_output_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    with build_http_client() as client:
        try:
            resp = client.post(
                f"{config.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {config.api_key}"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"OpenRouter HTTP {e.response.status_code}: {e.response.text}") from e

    body = resp.json()
    return body["choices"][0]["message"]["content"].strip()