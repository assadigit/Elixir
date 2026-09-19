"""V13.39.0: Anti-hallucination tests for additive sections.

Tests verify:
1. _normalize_empty_section normalizes "None" / "chapter does not discuss" to empty
2. _verify_additive_section_item returns True for source-grounded items
3. _verify_additive_section_item returns False for fabricated items
4. _verify_additive_sections drops fabricated items and keeps real ones
5. Full pipeline: fabricated distinctions are dropped, real ones survive
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub tiktoken (not installed in test env)
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from core.summarisation.summarizer import Summarizer

# ═══════════════════════════════════════════════════════════════════════════
# _normalize_empty_section tests
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeEmptySection:
    """V13.39.0: Verify 'None' / 'chapter does not discuss' is normalized to empty."""

    def test_none_becomes_empty(self):
        assert Summarizer._normalize_empty_section("None") == ""
        assert Summarizer._normalize_empty_section("none") == ""
        assert Summarizer._normalize_empty_section("N/A") == ""
        assert Summarizer._normalize_empty_section("Not applicable") == ""

    def test_chapter_does_not_discuss_becomes_empty(self):
        assert (
            Summarizer._normalize_empty_section("The chapter does not discuss any distinctions.")
            == ""
        )
        assert (
            Summarizer._normalize_empty_section("No explicit distinctions found in this chapter.")
            == ""
        )

    def test_real_content_is_preserved(self):
        real = "- Ego identity vs. existential identity: the former is inner sameness."
        assert Summarizer._normalize_empty_section(real) == real

    def test_empty_string_stays_empty(self):
        assert Summarizer._normalize_empty_section("") == ""
        assert Summarizer._normalize_empty_section("   ") == ""


# ═══════════════════════════════════════════════════════════════════════════
# _verify_additive_section_item tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyAdditiveSectionItem:
    """V13.39.0: Verify individual items are source-grounded."""

    def test_real_distinction_passes_verification(self):
        """A distinction using terms from the source should pass."""
        source = """
        Erikson defined ego identity as the inner sameness and continuity
        of the self. Existential identity, by contrast, refers to the
        social continuity and shared character with others.
        """
        item = "- Ego identity vs. existential identity: inner sameness vs. social continuity."
        result = Summarizer._verify_additive_section_item(item, source)
        assert result is True

    def test_fabricated_distinction_fails_verification(self):
        """A distinction using terms NOT in the source should fail."""
        source = """
        This chapter discusses basic arithmetic operations including
        addition, subtraction, multiplication, and division.
        """
        item = "- Quantum entanglement vs. classical correlation: non-locality vs. local hidden variables."
        result = Summarizer._verify_additive_section_item(item, source)
        assert result is False

    def test_fabricated_tension_fails_verification(self):
        """A fabricated tension using terms not in the source should fail."""
        source = """
        The water cycle involves evaporation, condensation, and precipitation.
        Water moves through the atmosphere and returns to the surface as rain.
        """
        item = "- The debate between string theory and loop quantum gravity remains unresolved."
        result = Summarizer._verify_additive_section_item(item, source)
        assert result is False

    def test_empty_item_fails(self):
        """Empty items should fail verification."""
        assert Summarizer._verify_additive_section_item("", "source") is False
        assert Summarizer._verify_additive_section_item("   ", "source") is False


# ═══════════════════════════════════════════════════════════════════════════
# _verify_additive_sections tests (full method)
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyAdditiveSections:
    """V13.39.0: Verify the full method drops fabricated items, keeps real ones."""

    class _FakeSummarizer:
        """A fake summarizer that uses the REAL static methods (no mocking)."""

        log = MagicMock()
        quarantine = None

        # Bind the real static methods
        _normalize_empty_section = staticmethod(Summarizer._normalize_empty_section)
        _verify_additive_section_item = staticmethod(Summarizer._verify_additive_section_item)

        def _verify_additive_sections(self, heading, text, result):
            """Call the real method (uses the bound static methods above)."""
            Summarizer._verify_additive_sections(self, heading, text, result)

    def _make_summarizer(self):
        return self._FakeSummarizer()

    def test_fabricated_distinctions_are_dropped(self):
        """When all distinctions are fabricated, they should all be dropped."""
        source = """
        This chapter discusses basic arithmetic. Addition combines numbers.
        Subtraction finds the difference. Multiplication is repeated addition.
        Division splits a number into equal parts.
        """
        result = {
            "key_distinctions": (
                "- Quantum entanglement vs. classical correlation: non-locality.\n"
                "- String theory vs. loop quantum gravity: background dependence.\n"
            ),
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._verify_additive_sections("Chapter 1", source, result)
        # All fabricated items should be dropped
        assert result["key_distinctions"] == ""

    def test_real_distinctions_are_kept(self):
        """When distinctions use source terms, they should be kept."""
        source = """
        Erikson defined ego identity as inner sameness and continuity.
        Existential identity refers to social continuity with others.
        The distinction matters because it separates personal experience
        from group membership.
        """
        result = {
            "key_distinctions": "- Ego identity vs. existential identity: inner sameness vs. social continuity.",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._verify_additive_sections("Chapter 1", source, result)
        # Real distinction should be kept
        assert "ego identity" in result["key_distinctions"].lower()
        assert "existential identity" in result["key_distinctions"].lower()

    def test_none_response_is_normalized_to_empty(self):
        """When the model outputs 'None', it should become empty."""
        source = "Some source text about a topic."
        result = {
            "key_distinctions": "None",
            "theoretical_tensions": "The chapter does not discuss any tensions.",
        }
        obj = self._make_summarizer()
        obj._verify_additive_sections("Chapter 1", source, result)
        assert result["key_distinctions"] == ""
        assert result["theoretical_tensions"] == ""

    def test_mixed_real_and_fabricated_only_keeps_real(self):
        """When some items are real and some fabricated, only real survive."""
        source = """
        Erikson defined ego identity as inner sameness.
        Existential identity refers to social continuity.
        """
        result = {
            "key_distinctions": (
                "- Ego identity vs. existential identity: inner sameness vs. social continuity.\n"
                "- Quantum entanglement vs. classical correlation: non-locality.\n"
            ),
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._verify_additive_sections("Chapter 1", source, result)
        # Real distinction kept, fabricated dropped
        assert "ego identity" in result["key_distinctions"].lower()
        assert "quantum entanglement" not in result["key_distinctions"].lower()

    def test_empty_sections_stay_empty(self):
        """Empty sections should remain empty without errors."""
        source = "Some source text."
        result = {
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._verify_additive_sections("Chapter 1", source, result)
        assert result["key_distinctions"] == ""
        assert result["theoretical_tensions"] == ""

    def test_quarantine_logged_for_dropped_items(self):
        """Dropped items should be logged to quarantine for audit trail."""
        source = "Basic arithmetic: addition, subtraction, multiplication, division."
        result = {
            "key_distinctions": "- Quantum entanglement vs. classical correlation: non-locality.",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        mock_quarantine = MagicMock()
        obj.quarantine = mock_quarantine
        obj._verify_additive_sections("Chapter 1", source, result)
        # Quarantine.add should have been called for the dropped item
        assert mock_quarantine.add.called
        call_args = mock_quarantine.add.call_args
        assert (
            "quantum entanglement" in str(call_args).lower()
            or "fabricated" in str(call_args).lower()
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
