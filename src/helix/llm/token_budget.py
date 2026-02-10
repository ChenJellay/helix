"""Token budget manager for SLM-aware context window control.

Provides utilities to:
- Estimate token counts without requiring a tokenizer dependency
- Allocate token budgets across prompt sections
- Truncate content to fit within a given budget
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from helix.config import settings

logger = logging.getLogger(__name__)

# Average chars-per-token ratio.  English text is ~4 chars/token on most
# sub-word tokenizers (BPE / SentencePiece).  We use 3.5 as a conservative
# estimate so that we slightly over-count tokens rather than under-count.
_CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in *text* using a character heuristic."""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def truncate_to_tokens(text: str, max_tokens: int, *, suffix: str = "\n...(truncated)") -> str:
    """Truncate *text* so its estimated token count is at most *max_tokens*.

    Tries to cut at the last newline boundary to avoid mid-sentence breaks.
    """
    if estimate_tokens(text) <= max_tokens:
        return text

    max_chars = int(max_tokens * _CHARS_PER_TOKEN)
    truncated = text[:max_chars]

    # Try to cut at the last newline to avoid mid-sentence breaks
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[:last_nl]

    return truncated + suffix


@dataclass
class TokenBudget:
    """Allocates a total token budget across named sections.

    Usage::

        budget = TokenBudget.for_current_model(output_tokens=2048)
        budget.reserve("system_prompt", 300)
        budget.reserve("json_schema", 400)
        remaining = budget.remaining()  # tokens left for user content
        content = budget.fit("prd", raw_prd_text)
    """

    total_input_tokens: int
    _allocated: dict[str, int] = field(default_factory=dict)

    # ── Constructors ──────────────────────────────────────────────────────

    @classmethod
    def for_current_model(cls, output_tokens: int | None = None) -> TokenBudget:
        """Create a budget sized for the active model's effective context."""
        effective = settings.effective_context_tokens
        out = output_tokens or settings.slm_max_output_tokens
        input_budget = max(512, effective - out)
        return cls(total_input_tokens=input_budget)

    # ── Budget operations ─────────────────────────────────────────────────

    def reserve(self, section: str, tokens: int) -> None:
        """Reserve *tokens* for a named section (e.g. "system_prompt")."""
        self._allocated[section] = tokens

    def remaining(self) -> int:
        """Tokens still available after all reservations."""
        return max(0, self.total_input_tokens - sum(self._allocated.values()))

    def fit(self, section: str, text: str, max_tokens: int | None = None) -> str:
        """Truncate *text* to fit in the budget and register the allocation.

        If *max_tokens* is provided it acts as an additional cap.  Otherwise
        the section gets whatever tokens remain.
        """
        available = min(max_tokens, self.remaining()) if max_tokens else self.remaining()
        fitted = truncate_to_tokens(text, available)
        actual = estimate_tokens(fitted)
        self._allocated[section] = actual
        return fitted

    def log_summary(self, agent_name: str = "") -> None:
        """Log the budget allocation for debugging."""
        total_used = sum(self._allocated.values())
        logger.info(
            "Token budget [%s]: total=%d, used=%d, remaining=%d | %s",
            agent_name or "unknown",
            self.total_input_tokens,
            total_used,
            self.remaining(),
            ", ".join(f"{k}={v}" for k, v in self._allocated.items()),
        )
