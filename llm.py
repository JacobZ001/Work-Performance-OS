"""LLM provider adapters (OpenAI + Gemini)."""

from __future__ import annotations

import os
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return model text completion."""


class OpenAIClient:
    def __init__(self, model: str, api_key: str) -> None:
        from openai import OpenAI

        self._model = model
        self._client = OpenAI(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned empty content.")
        return content.strip()


class GeminiClient:
    def __init__(self, model: str, api_key: str) -> None:
        from google import genai

        self._model = model
        self._client = genai.Client(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config={
                "system_instruction": system,
                "temperature": 0.2,
            },
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned empty content.")
        return text


def _require_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    joined = " / ".join(names)
    raise ValueError(
        f"Missing API key ({joined}). "
        f"Add it to the project-root .env file (see .env.example)."
    )


def create_llm(ai_config: dict | None) -> LLMClient:
    """Build an LLM client from the `ai:` section of config.yaml."""
    cfg = ai_config or {}
    provider = (cfg.get("provider") or "openai").strip().lower()
    model = (cfg.get("model") or "").strip()

    if provider in ("openai", "gpt"):
        api_key = _require_env("OPENAI_API_KEY")
        return OpenAIClient(model=model or "gpt-4o-mini", api_key=api_key)

    if provider in ("gemini", "google"):
        api_key = _require_env("GEMINI_API_KEY", "GOOGLE_API_KEY")
        return GeminiClient(model=model or "gemini-2.0-flash", api_key=api_key)

    raise ValueError(
        f"Unsupported ai.provider: {provider!r}. Use 'openai' or 'gemini'."
    )
