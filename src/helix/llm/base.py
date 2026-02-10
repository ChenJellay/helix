"""Base LLM interface for the pluggable provider abstraction."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""

    content: str
    model: str
    usage: dict[str, Any] = {}
    raw: dict[str, Any] | None = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers.

    All providers (OpenAI, Anthropic, Google, Ollama) implement this interface,
    allowing the rest of Helix to be provider-agnostic.
    """

    def __init__(self, model: str, **kwargs: Any):
        self.model = model
        self.kwargs = kwargs

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of {"role": ..., "content": ...} message dicts.
            temperature: Sampling temperature (0 = deterministic).
            max_tokens: Maximum tokens in the response.
            response_format: Optional JSON schema for structured output.
            **kwargs: Provider-specific overrides.

        Returns:
            LLMResponse with the generated content.
        """
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of texts.

        Args:
            texts: Strings to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        ...
