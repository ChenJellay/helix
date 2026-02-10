"""Base agent class providing shared capabilities for all Helix agents."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from helix.config import settings
from helix.llm import LLMRouter, get_llm
from helix.llm.token_budget import TokenBudget, estimate_tokens

logger = logging.getLogger(__name__)

# Jinja2 template environments — standard and SLM-optimised
PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"
SLM_PROMPTS_DIR = PROMPTS_DIR / "slm"

_jinja_env = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    autoescape=False,
)
_slm_jinja_env = Environment(
    loader=FileSystemLoader([str(SLM_PROMPTS_DIR), str(PROMPTS_DIR)]),
    autoescape=False,
)


class BaseAgent:
    """Base class for all Helix AI agents.

    Provides:
    - LLM access via the pluggable router
    - Jinja2 prompt template rendering (with SLM-optimised variants)
    - Token budget management for SLM context windows
    - Structured JSON output parsing with retries
    - Audit logging
    """

    agent_name: str = "base"
    prompt_template: str = ""  # e.g. "risk_analysis.j2"

    def __init__(self, llm: LLMRouter | None = None):
        self.llm = llm or get_llm()

    # ── Prompt rendering ──────────────────────────────────────────────────

    def render_prompt(self, **kwargs: Any) -> str:
        """Render a Jinja2 prompt template with the given variables.

        When running on an SLM and a matching template exists under
        ``prompts/slm/``, the SLM-optimised version is used automatically.
        """
        env = _slm_jinja_env if settings.is_slm else _jinja_env
        template = env.get_template(self.prompt_template)
        return template.render(**kwargs)

    def create_budget(self, output_tokens: int | None = None) -> TokenBudget:
        """Create a token budget sized for the current model."""
        return TokenBudget.for_current_model(output_tokens=output_tokens)

    # ── LLM calls ─────────────────────────────────────────────────────────

    async def call_llm(
        self,
        user_content: str,
        system_content: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Send a message to the LLM and return the content string.

        *max_tokens* defaults to the SLM profile's ``max_output_tokens``
        so that responses stay focused and within budget.
        """
        if max_tokens is None:
            max_tokens = settings.slm_max_output_tokens

        messages: list[dict[str, str]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})

        # Pass constrained JSON format for SLMs (Ollama, MLX, etc.)
        # The router translates this to the provider-specific mechanism.
        extra_kwargs: dict[str, Any] = {}
        if settings.is_slm and settings.active_slm_profile.get("use_constrained_json"):
            extra_kwargs["format"] = "json"

        response = await self.llm.complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **extra_kwargs,
        )

        logger.info(
            "Agent %s LLM call: model=%s, tokens_in≈%d, usage=%s",
            self.agent_name,
            response.model,
            estimate_tokens(user_content + (system_content or "")),
            response.usage,
        )
        return response.content

    async def call_llm_structured(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Call the LLM and parse the response as JSON.

        On SLMs, retries up to ``json_retries`` times with an increasingly
        explicit repair prompt if the initial response fails to parse.
        """
        retries = settings.active_slm_profile.get("json_retries", 0)

        raw = await self.call_llm(prompt, temperature=temperature, max_tokens=max_tokens)
        result = self.parse_json(raw)
        if "error" not in result:
            return result

        # Retry loop — only on SLMs where JSON parsing is less reliable
        for attempt in range(1, retries + 1):
            logger.warning(
                "Agent %s: JSON parse failed (attempt %d/%d), retrying with repair prompt",
                self.agent_name,
                attempt,
                retries,
            )
            repair_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond ONLY with a valid JSON object. "
                "No markdown, no explanation, just the JSON.\n\n"
                f"Original request (summarised):\n{prompt[:1500]}"
            )
            raw = await self.call_llm(
                repair_prompt, temperature=0.0, max_tokens=max_tokens
            )
            result = self.parse_json(raw)
            if "error" not in result:
                return result

        return result

    # ── JSON parsing ──────────────────────────────────────────────────────

    @staticmethod
    def parse_json(text: str) -> dict[str, Any]:
        """Parse a JSON response, stripping markdown code fences if present.

        Applies multiple extraction strategies:
        1. Strip markdown fences and parse directly
        2. Find the first ``{…}`` block in the text and parse that
        """
        # Strategy 1: strip fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = cleaned.strip().rstrip("`")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract first JSON object via brace matching
        start = text.find("{")
        if start != -1:
            depth, end = 0, start
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse JSON from LLM response: %s...", text[:200])
        return {"error": "Failed to parse response", "raw": text[:500]}
