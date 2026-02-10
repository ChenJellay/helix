"""OpenAI provider - uses LLMRouter with OpenAI defaults."""

from helix.llm.router import LLMRouter_OpenAI

# Re-export for explicit usage:  from helix.llm.providers.openai import OpenAIProvider
OpenAIProvider = LLMRouter_OpenAI
