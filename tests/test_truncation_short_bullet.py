"""V18.19.3.1 (audit fix): characterization tests for the is_truncated detector's
short-bullet unmatched-paren check.

The V18.19.3.0 audit (audit/results/audit_V18.19.3.0_2026-08-28.md) found a
truncated bullet in the delivered summary:
    - Kernberg (198

The primary call's 26th bullet hit the 8192-token ceiling mid-citation, cutting
"1980b" to "198" and leaving an UNMATCHED open paren. The V18.15.3.1 is_truncated
detector should have caught this — but its `len(stripped) < 40` exemption (line
328) skipped all short bullets, assuming they were intentional label-style
fragments. "Kernberg (198" is 14 chars, so the unmatched-paren check never ran.

V18.19.3.1 fix: check unmatched quotes/parens REGARDLESS of length. A label like
"Freud (1926a)" has matched parens; a truncated "Kernberg (198" does not. The
"no terminal punctuation" check stays gated on >= 40 chars (short labels
legitimately lack terminal punctuation).

Run: ``pytest tests/test_truncation_short_bullet.py -v``
"""
from __future__ import annotations

import sys
import types

import pytest

if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = lambda *a, **k: None
    _tk.encoding_for_model = lambda *a, **k: None
    _tk.Encoding = type("Encoding", (), {})
    sys.modules["tiktoken"] = _tk

from core.summarisation.post_processing import is_truncated

# ═══════════════════════════════════════════════════════════════════════════
# 1. The exact V18.19.3.0 audit defect: "Kernberg (198"
# ═══════════════════════════════════════════════════════════════════════════

class TestKernberg198Case:
    """The exact truncated bullet from the V18.19.3.0 audit."""

    def test_kernberg_198_flagged_as_truncated(self):
        """'- Kernberg (198' — 14 chars, unmatched open paren — MUST be flagged."""
        # The bullet as it appeared in the summary (after the "- " prefix strip)
        bullet = "Kernberg (198"
        assert is_truncated(bullet) is True, (
            "V18.19.3.0 audit defect: 'Kernberg (198' has an unmatched open paren "
            "(max_tokens cut '1980b' to '198'). Must be flagged as truncated."
        )

    def test_kernberg_198_with_bullet_prefix(self):
        """The bullet as it appears in the markdown (with '- ' prefix)."""
        bullet = "- Kernberg (198"
        assert is_truncated(bullet) is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. Other short-bullet truncation forms (unmatched parens/quotes)
# ═══════════════════════════════════════════════════════════════════════════

class TestShortBulletUnmatchedDelimiters:
    """Short bullets with unmatched parens/quotes must be flagged (any length)."""

    @pytest.mark.parametrize("bullet", [
        "Erikson (195",           # 13 chars, unmatched paren
        "Freud (1926",             # 11 chars, unmatched paren
        "Mahler (1958a,b, 1968",   # 22 chars, unmatched paren
        "Jacobson (1964",          # 15 chars, unmatched paren
        '"incomplete quote',      # 17 chars, unmatched quote
        '"another unclosed',      # 17 chars, unmatched quote
    ])
    def test_short_unmatched_paren_or_quote_flagged(self, bullet):
        assert is_truncated(bullet) is True, (
            f"Short bullet with unmatched delimiter must be flagged: {bullet!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Regression guard: legitimate short labels must NOT be flagged
# ═══════════════════════════════════════════════════════════════════════════

class TestLegitimateShortLabelsNotFlagged:
    """Short bullets with MATCHED parens/quotes are intentional labels, not
    truncated. They must NOT be flagged."""

    @pytest.mark.parametrize("bullet", [
        "Freud (1926a)",           # 13 chars, matched parens — citation label
        "Erikson (1950)",          # 14 chars, matched parens — citation label
        "See above.",              # 10 chars, ends in '.' — complete
        "Tausk (1919)",            # 12 chars, matched parens
        "Mahler et al. (1975)",    # 19 chars, matched parens
        "Kernberg (1967, 1976, 1980b)",  # 28 chars, matched parens — complete
        '"complete quote"',        # 16 chars, matched quotes
    ])
    def test_legitimate_short_label_not_flagged(self, bullet):
        assert is_truncated(bullet) is False, (
            f"Legitimate short label must NOT be flagged: {bullet!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Long-bullet truncation still works (regression guard)
# ═══════════════════════════════════════════════════════════════════════════

class TestLongBulletTruncationStillWorks:
    """The existing long-bullet truncation checks must still work."""

    def test_long_no_terminal_punctuation(self):
        bullet = "This is a very long bullet that has no terminal punctuation at all yeah"
        assert is_truncated(bullet) is True

    def test_long_with_terminal_punctuation_not_flagged(self):
        bullet = "This is a long bullet that ends with a period. So it is complete."
        assert is_truncated(bullet) is False

    def test_long_unmatched_quote(self):
        bullet = ('"He said the identity concept was important '
                  'but the quote never closes in this very long bullet')
        assert is_truncated(bullet) is True

    def test_long_unmatched_paren(self):
        bullet = ("The author (Kernberg described this in his 1967 work "
                  "on borderline pathology but never closed the paren")
        assert is_truncated(bullet) is True


# ═══════════════════════════════════════════════════════════════════════════
# 5. Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_string(self):
        assert is_truncated("") is False

    def test_whitespace_only(self):
        assert is_truncated("   ") is False

    def test_single_open_paren(self):
        """A single '(' is clearly truncated (unmatched)."""
        assert is_truncated("(") is True

    def test_single_close_paren(self):
        """A single ')' is unmatched (no open) — also truncated."""
        assert is_truncated(")") is True

    def test_matched_empty_parens(self):
        """'()' is matched — not truncated (though meaningless)."""
        assert is_truncated("()") is False
