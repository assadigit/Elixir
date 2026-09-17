"""V18.2.24 (Phase 3.2) — Prompt budget accounting + smart context compaction.

The problem
-----------
The existing ``_smart_truncate`` in ``summarizer.py`` cuts text ONCE when it
exceeds the model's context limit. But a chapter's pipeline makes 5-10 LLM
calls, each of which adds tokens (exec summary, thorough summary, bullets).
There's no tracking of the *cumulative* token budget across the pipeline —
each call independently truncates, losing different content each time.

The fix (Phase 3.2)
-------------------
A ``PromptBudget`` that:
1. Tracks the configured token limit (``summarisation.max_context_tokens``).
2. Estimates token counts via the existing ``count_tokens`` (char-based // 4).
3. Provides ``compact(text, keep_head=0.25, keep_tail=0.25)`` — drops the
   MIDDLE of a long text (keeps head + tail), preserving the chapter's
   opening (context) and conclusion (often the most important part).
   This is better than a single cut which loses the ending.
4. Provides ``fits(text, reserved=0) -> bool`` — check if text fits with
   reserved space for the model's response.
5. Provides ``allocate(prompt_tokens, response_tokens)`` — record usage so
   the next call knows how much budget remains.

Design: stateless utility, no persistence
------------------------------------------
This is a pure utility class — no disk cache, no global state. The
summarizer creates one per chapter, feeds it the chapter content, and
calls ``compact`` before each LLM call if needed.

Book-agnostic (Key Decision #3): the compaction is purely structural
(head/tail preservation), no content awareness.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Rough token estimate: 4 chars ≈ 1 token (matches the sync provider's
# ``_adaptive_context`` heuristic). Good enough for budgeting; exact counts
# would require tiktoken (already a dependency, but slow to call per-text).
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text`` (char-based, ~4 chars/token).

    This matches the heuristic used by ``OllamaProvider._adaptive_context``.
    It's a rough estimate — actual counts vary by tokenizer — but
    sufficient for budgeting (we leave a 4096-token safety margin).
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass
class PromptBudget:
    """Tracks token usage across a multi-call LLM pipeline.

    Usage::

        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000)
        if not budget.fits(chapter_content, reserved=16000):
            chapter_content = budget.compact(chapter_content)
        # ... call LLM ...
        budget.allocate(prompt_tokens=estimate_tokens(chapter_content),
                        response_tokens=estimate_tokens(llm_response))

    Attributes:
        max_context_tokens: the model's context window (e.g. 32768).
        max_output_tokens: the reserved space for the model's response.
        safety_margin: extra tokens reserved for system prompt + overhead.
            Default 4096 (matches the sync provider's margin).
        used_tokens: cumulative tokens consumed so far (prompt + response).
    """

    max_context_tokens: int = 32768
    max_output_tokens: int = 16000
    safety_margin: int = 4096
    used_tokens: int = 0
    _compactions: int = 0
    _tokens_saved: int = 0  # tokens removed by compaction (for diagnostics)

    @property
    def available(self) -> int:
        """Tokens available for the next prompt (after response + margin)."""
        return max(0, self.max_context_tokens - self.max_output_tokens - self.safety_margin - self.used_tokens)

    def fits(self, text: str, reserved: int = 0) -> bool:
        """Check if ``text`` fits in the available budget.

        Args:
            text: the text to check.
            reserved: additional tokens to reserve (e.g. for a system prompt
                or injected context). Default 0.

        Returns:
            True if the text fits within the available budget.
        """
        needed = estimate_tokens(text) + reserved
        return needed <= self.available

    def compact(
        self,
        text: str,
        *,
        keep_head: float = 0.25,
        keep_tail: float = 0.25,
        target_tokens: int | None = None,
    ) -> str:
        """Compact ``text`` to fit the budget by dropping the middle.

        Preserves the head (chapter opening — sets context) and tail
        (chapter conclusion — often the most important part). Drops the
        middle (which is usually elaboration/examples).

        Args:
            text: the text to compact.
            keep_head: fraction of the text to keep from the start (0.0-1.0).
                Default 0.25 (first quarter).
            keep_tail: fraction to keep from the end (0.0-1.0).
                Default 0.25 (last quarter). Head + tail = 50% kept, 50%
                (middle) dropped.
            target_tokens: optional explicit target. If None, compacts to
                fit ``self.available``.

        Returns:
            The compacted text. If the text already fits, returns it
            unchanged. If head + tail still exceeds the target, truncates
            the tail further (last resort).
        """
        if not text:
            return text
        text_tokens = estimate_tokens(text)
        target = target_tokens or self.available
        if text_tokens <= target:
            return text  # already fits

        # Calculate head/tail sizes in characters
        text_chars = len(text)
        head_chars = int(text_chars * keep_head)
        tail_chars = int(text_chars * keep_tail)

        # If head + tail still exceeds target, reduce tail (last resort)
        head_tokens = estimate_tokens(text[:head_chars])
        tail_tokens = estimate_tokens(text[-tail_chars:])
        # Aggressively reduce tail until head + tail fits
        while head_tokens + tail_tokens > target and tail_chars > 100:
            tail_chars = int(tail_chars * 0.5)  # halve each iteration
            tail_tokens = estimate_tokens(text[-tail_chars:])
        # If tail is exhausted, reduce head too
        while head_tokens + tail_tokens > target and head_chars > 100:
            head_chars = int(head_chars * 0.8)
            head_tokens = estimate_tokens(text[:head_chars])

        head = text[:head_chars]
        tail = text[-tail_chars:] if tail_chars > 0 else ""
        # Ellipsis marker so the model knows content was removed
        marker = "\n…[content compacted — middle section omitted]…\n"
        compacted = head + marker + tail

        original_tokens = text_tokens
        new_tokens = estimate_tokens(compacted)
        saved = original_tokens - new_tokens
        self._compactions += 1
        self._tokens_saved += saved
        logger.debug(
            "PromptBudget.compact: %d → %d tokens (saved %d, kept head=%d + tail=%d)",
            original_tokens, new_tokens, saved, head_tokens, tail_tokens,
        )
        return compacted

    def allocate(self, prompt_tokens: int, response_tokens: int) -> None:
        """Record token usage for a completed LLM call.

        Args:
            prompt_tokens: tokens in the prompt sent to the model.
            response_tokens: tokens in the model's response.

        Updates ``used_tokens`` so subsequent ``fits`` / ``compact`` calls
        account for the cumulative usage.
        """
        self.used_tokens += prompt_tokens + response_tokens

    def reset(self) -> None:
        """Reset the budget for a new chapter (clears used_tokens + diagnostics)."""
        self.used_tokens = 0
        self._compactions = 0
        self._tokens_saved = 0

    @property
    def compaction_count(self) -> int:
        """Number of times ``compact`` actually removed content."""
        return self._compactions

    @property
    def tokens_saved(self) -> int:
        """Total tokens removed by compaction (diagnostic)."""
        return self._tokens_saved

    def summary(self) -> str:
        """Human-readable budget summary for logging."""
        return (
            f"PromptBudget(used={self.used_tokens}/{self.max_context_tokens}, "
            f"available={self.available}, compactions={self._compactions}, "
            f"tokens_saved={self._tokens_saved})"
        )
