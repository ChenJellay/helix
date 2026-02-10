"""LLM provider implementations.

All providers route through litellm via the LLMRouter.
Provider-specific subclasses are available for explicit construction:

- OpenAIProvider   — cloud OpenAI models
- AnthropicProvider — cloud Anthropic models
- GoogleProvider   — cloud Google Gemini models
- OllamaProvider   — local models via Ollama
- MLXProvider      — local models via mlx-lm on Apple Silicon
"""
