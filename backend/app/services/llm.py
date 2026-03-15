"""LLM integration service for book analysis.

Supports multiple LLM backends via a pluggable provider pattern.
Default: Anthropic Claude API. Can be extended to support Ollama (local),
OpenAI, or any OpenAI-compatible API.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-5-20250514"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def is_available(self) -> bool:
        return self.api_key is not None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Anthropic API key not configured")

        # Lazy import to avoid dependency if not used
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

        message = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return LLMResponse(
            content=message.content[0].text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider for fully offline analysis."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        # Could do a health check, but for now just return True
        return True

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx package not installed. Run: pip install httpx")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with OpenAI, Together, Groq, etc.)."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        return self.api_key is not None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx package not installed. Run: pip install httpx")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


def get_llm_provider() -> LLMProvider:
    """Factory function to get the configured LLM provider."""
    settings = get_settings()

    provider_name = getattr(settings, "LLM_PROVIDER", "anthropic").lower()

    if provider_name == "anthropic":
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250514")
        return AnthropicProvider(api_key=api_key, model=model)

    elif provider_name == "ollama":
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        model = getattr(settings, "OLLAMA_MODEL", "llama3.2")
        return OllamaProvider(base_url=base_url, model=model)

    elif provider_name == "openai":
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = getattr(settings, "OPENAI_MODEL", "gpt-4o")
        return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
