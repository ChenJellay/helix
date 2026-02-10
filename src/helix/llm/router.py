"""LLM Router - selects and manages the active LLM provider."""

from __future__ import annotations

import logging
from typing import Any

from helix.config import settings
from helix.llm.base import BaseLLM, LLMResponse

logger = logging.getLogger(__name__)

# Singleton instances
_llm_instance: BaseLLM | None = None
_st_model: Any = None  # lazy-loaded sentence-transformers model


def _get_sentence_transformer():
    """Lazy-load the sentence-transformers embedding model (used by MLX / local providers)."""
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        model_name = settings.resolved_embedding_model
        logger.info("Loading local embedding model: %s", model_name)
        _st_model = SentenceTransformer(model_name)
    return _st_model


class LLMRouter(BaseLLM):
    """Routes LLM calls through litellm for unified multi-provider support.

    Uses litellm under the hood so any provider (OpenAI, Anthropic, Google,
    Ollama, MLX-LM, etc.) works through a single interface.
    """

    def __init__(self, model: str | None = None, **kwargs: Any):
        resolved_model = model or settings.llm_model
        super().__init__(model=resolved_model, **kwargs)
        self._configure_provider()

    def _configure_provider(self) -> None:
        """Set environment variables litellm needs based on our config."""
        import os

        provider = settings.llm_provider.lower()

        if provider == "openai" and settings.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
        elif provider == "anthropic" and settings.anthropic_api_key:
            os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
        elif provider == "google" and settings.google_api_key:
            os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
        elif provider == "ollama":
            os.environ.setdefault("OLLAMA_API_BASE", settings.ollama_base_url)
        elif provider == "mlx":
            # mlx_lm.server exposes an OpenAI-compatible API; litellm routes
            # it through its openai provider with a custom api_base.
            # A dummy key is required by litellm but ignored by the server.
            os.environ.setdefault("OPENAI_API_KEY", "mlx-local")
            os.environ.setdefault("OPENAI_API_BASE", f"{settings.mlx_base_url}/v1")

    def _resolve_model_name(self, model: str | None = None) -> str:
        """Map our model name to a litellm-compatible model string."""
        m = model or self.model
        provider = settings.llm_provider.lower()

        if provider == "mlx":
            # litellm routes to the custom OPENAI_API_BASE; the model name
            # must match what mlx_lm.server loaded, but litellm wants the
            # openai/ prefix to pick the right code-path.
            mlx_name = settings.mlx_model
            if not mlx_name.startswith("openai/"):
                return f"openai/{mlx_name}"
            return mlx_name

        # litellm uses prefix-based routing for non-OpenAI providers
        prefix_map = {
            "anthropic": "anthropic/",
            "google": "gemini/",
            "ollama": "ollama/",
        }
        prefix = prefix_map.get(provider, "")

        # Don't double-prefix
        if prefix and not m.startswith(prefix):
            return f"{prefix}{m}"
        return m

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Route a completion request through litellm.

        Constrained JSON decoding is handled per-provider:
        - **Ollama**: passes ``format="json"``
        - **MLX-LM / OpenAI-compatible**: passes
          ``response_format={"type": "json_object"}``
        """
        import litellm

        litellm.drop_params = True

        model_name = self._resolve_model_name()
        provider = settings.llm_provider.lower()
        call_kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Constrained JSON decoding — provider-specific mechanism
        json_format = kwargs.pop("format", None)
        if json_format == "json":
            if provider == "ollama":
                call_kwargs["format"] = "json"
            elif provider == "mlx":
                # mlx_lm.server supports the OpenAI response_format param
                call_kwargs["response_format"] = {"type": "json_object"}
        elif response_format:
            call_kwargs["response_format"] = response_format

        # Forward any remaining kwargs
        call_kwargs.update(kwargs)

        logger.info("LLM request: model=%s, messages=%d", model_name, len(messages))

        try:
            response = await litellm.acompletion(**call_kwargs)
        except Exception:
            logger.exception("LLM call failed for model=%s", model_name)
            raise

        content = response.choices[0].message.content or ""
        usage = dict(response.usage) if response.usage else {}

        return LLMResponse(
            content=content,
            model=model_name,
            usage=usage,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings, routing to the appropriate backend.

        - **MLX provider**: uses ``sentence-transformers`` locally because
          ``mlx_lm.server`` does not expose an embedding endpoint.
        - **Ollama**: routes through litellm with the Ollama prefix.
        - **Cloud providers**: routes through litellm normally.
        """
        provider = settings.llm_provider.lower()

        if provider == "mlx":
            return self._embed_local(texts)

        import litellm

        model_name = settings.resolved_embedding_model
        if provider == "ollama" and not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"

        logger.info("Embedding request: model=%s, texts=%d", model_name, len(texts))
        response = await litellm.aembedding(model=model_name, input=texts)
        return [item["embedding"] for item in response.data]

    @staticmethod
    def _embed_local(texts: list[str]) -> list[list[float]]:
        """Generate embeddings using a local sentence-transformers model.

        This is the fallback for providers (like MLX-LM) that don't expose
        an embedding endpoint.  Runs on CPU via PyTorch / MPS.
        """
        model = _get_sentence_transformer()
        logger.info(
            "Local embedding: model=%s, texts=%d",
            settings.resolved_embedding_model,
            len(texts),
        )
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]


class LLMRouter_OpenAI(LLMRouter):
    """Convenience subclass pre-configured for OpenAI."""

    def __init__(self, model: str = "gpt-4o", **kwargs: Any):
        super().__init__(model=model, **kwargs)


class LLMRouter_Anthropic(LLMRouter):
    """Convenience subclass pre-configured for Anthropic."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", **kwargs: Any):
        super().__init__(model=model, **kwargs)


class LLMRouter_Google(LLMRouter):
    """Convenience subclass pre-configured for Google."""

    def __init__(self, model: str = "gemini-pro", **kwargs: Any):
        super().__init__(model=model, **kwargs)


class LLMRouter_Ollama(LLMRouter):
    """Convenience subclass pre-configured for Ollama."""

    def __init__(self, model: str = "qwen2.5:7b", **kwargs: Any):
        super().__init__(model=model, **kwargs)


class LLMRouter_MLX(LLMRouter):
    """Convenience subclass pre-configured for MLX-LM (Apple Silicon)."""

    def __init__(self, model: str | None = None, **kwargs: Any):
        super().__init__(model=model or settings.mlx_model, **kwargs)


def get_llm(model: str | None = None) -> LLMRouter:
    """Get or create the singleton LLM router instance."""
    global _llm_instance
    if _llm_instance is None or model is not None:
        _llm_instance = LLMRouter(model=model)
    return _llm_instance
