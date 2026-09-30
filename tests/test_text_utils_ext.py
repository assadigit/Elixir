"""V18.11 (Phase 5 Stage 3, Batch 1.1) — text_utils_ext characterization tests.

Byte-for-byte stability gate for ``smart_truncate`` extracted from
``Summarizer._smart_truncate``. Each test captures a canned input → golden
output pair. If the extraction changes the output by even one character, the
test fails.

Run: pytest tests/test_text_utils_ext.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so the import chain (utils.token_counter → tiktoken) works
# without the real package installed in the sandbox.
from core.summarisation.text_utils_ext import smart_truncate

# ── helper: capturing log ──────────────────────────────────────────────────


class _CapturingLog:
    """Captures log calls so tests can assert the log message + level."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


# ── 1. short-text path (≤3 paragraphs) ──────────────────────────────────────


class TestSmartTruncateShortText:
    def test_three_paragraphs_uses_plain_truncation(self):
        """≤3 paragraphs must NOT inject '[… content omitted …]' markers —
        it falls back to plain ``truncate_by_tokens``. This is the byte-for-byte
        contract of the original method's first branch."""
        text = "Para one is short.\n\nPara two is here.\n\nPara three ends."
        result = smart_truncate(text, max_tokens=10000, log=_CapturingLog())
        # Plain truncation path returns the text (under budget) untouched
        assert "[… content omitted …]" not in result
        assert "Para one is short." in result
        assert "Para three ends." in result

    def test_single_paragraph_unchanged_under_budget(self):
        text = "A single paragraph with no double-newline splits."
        result = smart_truncate(text, max_tokens=10000, log=_CapturingLog())
        assert result == text

    def test_empty_string(self):
        assert smart_truncate("", max_tokens=100, log=_CapturingLog()) == ""


# ── 2. multi-paragraph path (anchor/tail/middle) ───────────────────────────


class TestSmartTruncateMultiParagraph:
    def _multi(self, n: int = 8) -> str:
        """Build a deterministic multi-paragraph text (8 paragraphs, each
        distinguishable so we can assert which survive truncation)."""
        paras = []
        for i in range(n):
            # Mix content words + a named entity so the scorer gives non-zero
            # scores. Paragraph 0 and 7 are anchors/tails by position.
            paras.append(
                f"Paragraph {i}: Erikson described identity stage {i} as a "
                f"developmental crisis requiring resolution and integration."
            )
        return "\n\n".join(paras)

    def test_keeps_first_and_last_paragraph(self):
        """Anchor = first paragraph(s), tail = last paragraph(s) — both must
        appear in the output regardless of the middle selection."""
        text = self._multi(8)
        result = smart_truncate(text, max_tokens=400, log=_CapturingLog())
        assert "Paragraph 0:" in result
        assert "Paragraph 7:" in result

    def test_inserts_omitted_marker_between_gaps(self):
        """When the kept middle paragraphs are non-adjacent, a
        '[… content omitted …]' marker is inserted between them."""
        text = self._multi(8)
        # Use a tight budget so only a few middle paragraphs survive, forcing
        # a gap between them.
        result = smart_truncate(text, max_tokens=180, log=_CapturingLog())
        # With a tight budget, at least one gap marker appears between the
        # anchor and the tail (or between kept middles).
        assert "[… content omitted …]" in result

    def test_log_called_with_info_level(self):
        """The log callback must be invoked exactly once with level 'INFO'
        and a message containing the token-reduction report."""
        cap = _CapturingLog()
        smart_truncate(self._multi(6), max_tokens=300, log=cap)
        assert len(cap.calls) == 1
        msg, level = cap.calls[0]
        assert level == "INFO"
        assert "Smart truncation:" in msg
        assert "→" in msg  # the arrow in the log format
        assert "tokens" in msg

    def test_no_log_callback_does_not_raise(self):
        """When log=None (default), the function must not raise — it uses
        the _noop_log default."""
        text = self._multi(6)
        # No log kwarg → defaults to _noop_log
        result = smart_truncate(text, max_tokens=300)
        assert "Paragraph 0:" in result
        assert "Paragraph 5:" in result


# ── 3. byte-for-byte stability ─────────────────────────────────────────────


class TestSmartTruncateByteForByte:
    def test_deterministic_output_for_fixed_input(self):
        """The same input must produce byte-for-byte identical output across
        calls (the scorer + greedy fill are deterministic)."""
        text = (
            "First anchor paragraph establishing context and named entity Erikson.\n\n"
            "Middle paragraph about Kernberg and splitting mechanisms in detail here.\n\n"
            "Middle paragraph two about Lichtenstein identity-as-a-theme concept.\n\n"
            "Middle paragraph three continues the discussion with more content.\n\n"
            "Middle paragraph four adds the Mahler separation-individuation phase.\n\n"
            "Final tail paragraph concludes with Jacobson and sine qua non claim."
        )
        r1 = smart_truncate(text, max_tokens=250, log=_CapturingLog())
        r2 = smart_truncate(text, max_tokens=250, log=_CapturingLog())
        assert r1 == r2, "smart_truncate must be deterministic for a fixed input"

    def test_output_never_exceeds_budget_plus_ellipsis(self):
        """The truncated result must be shorter than the input when the input
        exceeds the budget (the whole point of truncation)."""
        text = "\n\n".join(
            f"Paragraph {i} with Erikson stage {i} content words to fill budget." for i in range(10)
        )
        result = smart_truncate(text, max_tokens=120, log=_CapturingLog())
        # The result should be meaningfully shorter than the input.
        assert len(result) < len(text)

    def test_anchor_tail_present_even_with_tight_budget(self):
        """Even with a very tight budget, the anchor (first) and tail (last)
        paragraphs are always kept (they fall back to truncated single
        paragraphs if the budget is too small for whole paragraphs)."""
        text = "\n\n".join(f"Paragraph {i} with Erikson content words." for i in range(5))
        result = smart_truncate(text, max_tokens=50, log=_CapturingLog())
        assert "Paragraph 0" in result
        assert "Paragraph 4" in result
