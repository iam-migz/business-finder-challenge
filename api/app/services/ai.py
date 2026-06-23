from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, OpenAIError

DEFAULT_OPENAI_BASE_URL = "https://martial-miracle-critical-history.trycloudflare.com/v1"
DEFAULT_OPENAI_MODEL = "smart"
DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant for a business opportunity finder. "
    "Use the supplied listing and market context, be concise, and avoid inventing facts."
)


class AIConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AISettings:
    base_url: str
    model: str
    has_api_key: bool


@dataclass(frozen=True)
class AIResponse:
    content: str
    model: str | None
    usage: dict[str, Any] | None


def get_ai_settings() -> AISettings:
    return AISettings(
        base_url=_normalized_base_url(
            os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)
        ),
        model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        has_api_key=bool(os.getenv("OPENAI_API_KEY")),
    )


class AIService:
    def __init__(self) -> None:
        self.settings = get_ai_settings()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AIConfigurationError("OPENAI_API_KEY is not configured")

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.settings.base_url,
        )

    def complete(
        self,
        prompt: str,
        context: dict[str, Any] | list[Any] | str | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.2,
        max_tokens: int = 500,
    ) -> AIResponse:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if context is not None:
            messages.append(
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nTask:\n{prompt}",
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return AIResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None,
        )

    def contact(self) -> AIResponse:
        return self.complete(
            prompt="Reply with one short sentence confirming the AI service is reachable.",
            max_tokens=80,
        )


def ai_status() -> dict[str, Any]:
    settings = get_ai_settings()
    return {
        "configured": settings.has_api_key,
        "base_url": settings.base_url,
        "model": settings.model,
        "api_key_present": settings.has_api_key,
    }


def create_ai_service() -> AIService:
    return AIService()


def _normalized_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    if not base_url.endswith("/v1"):
        return f"{base_url}/v1"
    return base_url


def ai_error_response(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AIConfigurationError):
        return {"ok": False, "type": "configuration", "error": str(exc)}
    if isinstance(exc, OpenAIError):
        return {"ok": False, "type": "provider", "error": str(exc)}
    return {"ok": False, "type": "unexpected", "error": str(exc)}
