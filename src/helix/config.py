"""Helix application configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


# ── SLM Profile Defaults ─────────────────────────────────────────────────────
# These define conservative token budgets that keep prompts within the
# "effective attention zone" of 7B-class models where output quality is highest.

SLM_PROFILES: dict[str, dict] = {
    "qwen-7b": {
        "effective_context_tokens": 6144,   # quality degrades above this on 7B
        "max_output_tokens": 2048,          # shorter, focused responses
        "prompt_reserve_tokens": 4096,      # input budget = effective - output
        "chunk_token_limit": 256,           # smaller RAG chunks for precision
        "retrieval_top_k": 3,               # fewer but more relevant chunks
        "embedding_model": "all-MiniLM-L6-v2",  # local sentence-transformers model
        "json_retries": 2,                  # extra parse attempts for JSON
        "use_constrained_json": True,       # request JSON-only output from server
        "simplify_prompts": True,           # use SLM-optimised prompt templates
    },
    "llama-3-8b": {
        "effective_context_tokens": 6144,
        "max_output_tokens": 2048,
        "prompt_reserve_tokens": 4096,
        "chunk_token_limit": 256,
        "retrieval_top_k": 3,
        "embedding_model": "all-MiniLM-L6-v2",
        "json_retries": 2,
        "use_constrained_json": True,
        "simplify_prompts": True,
    },
    "default": {
        "effective_context_tokens": 128000,
        "max_output_tokens": 4096,
        "prompt_reserve_tokens": 120000,
        "chunk_token_limit": 512,
        "retrieval_top_k": 5,
        "embedding_model": "",              # use setting from env
        "json_retries": 0,
        "use_constrained_json": False,
        "simplify_prompts": False,
    },
}


class Settings(BaseSettings):
    """Global application settings loaded from environment / .env file."""

    # General
    helix_env: str = "development"
    helix_debug: bool = True
    helix_api_key: str = "changeme-generate-a-real-key"
    helix_mode: str = "local"  # "local" (default) or "cloud"

    # Local workspace — root directory for all watched repositories.
    # All repo paths in the DB are stored relative to this directory.
    helix_workspace: str = "~/projects"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "helix"
    postgres_password: str = "helix_dev_password"
    postgres_db: str = "helix"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8200

    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "helix_neo4j_dev"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: str = "openai"  # openai | anthropic | google | ollama | mlx
    llm_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    mlx_base_url: str = "http://localhost:8080"  # mlx_lm.server default
    mlx_model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"
    embedding_model: str = "text-embedding-3-small"

    # SLM tuning — override via env or leave blank for auto-detection
    slm_profile: str = ""  # e.g. "qwen-7b", "llama-3-8b", or "" for auto

    # GitHub (cloud mode only)
    github_token: str = ""
    github_webhook_secret: str = "changeme-webhook-secret"

    # ── Derived SLM helpers ───────────────────────────────────────────────

    @property
    def active_slm_profile(self) -> dict:
        """Return the active SLM profile dict, auto-detecting from model name."""
        if self.slm_profile:
            return SLM_PROFILES.get(self.slm_profile, SLM_PROFILES["default"])
        # Auto-detect from model name (check both llm_model and mlx_model)
        candidates = [self.llm_model.lower()]
        if self.llm_provider.lower() == "mlx":
            candidates.append(self.mlx_model.lower())
        for model_lower in candidates:
            if "qwen" in model_lower and ("7b" in model_lower or "7B" in model_lower):
                return SLM_PROFILES["qwen-7b"]
            if ("llama" in model_lower or "llama3" in model_lower) and "8b" in model_lower:
                return SLM_PROFILES["llama-3-8b"]
        return SLM_PROFILES["default"]

    @property
    def is_slm(self) -> bool:
        """Whether the current model is classified as a small language model."""
        return self.active_slm_profile.get("simplify_prompts", False)

    @property
    def effective_context_tokens(self) -> int:
        return self.active_slm_profile["effective_context_tokens"]

    @property
    def slm_max_output_tokens(self) -> int:
        return self.active_slm_profile["max_output_tokens"]

    @property
    def prompt_reserve_tokens(self) -> int:
        return self.active_slm_profile["prompt_reserve_tokens"]

    @property
    def resolved_embedding_model(self) -> str:
        """Return the embedding model, preferring the SLM profile override."""
        profile_embed = self.active_slm_profile.get("embedding_model", "")
        return profile_embed if profile_embed else self.embedding_model

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
