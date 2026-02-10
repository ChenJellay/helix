"""MLX-LM local provider (Apple Silicon) - uses LLMRouter with MLX defaults.

Expects ``mlx_lm.server`` running locally, which exposes an
OpenAI-compatible API.  Start it with::

    python -m mlx_lm.server \\
        --model mlx-community/Qwen2.5-7B-Instruct-4bit \\
        --port 8080
"""

from helix.llm.router import LLMRouter_MLX

MLXProvider = LLMRouter_MLX
