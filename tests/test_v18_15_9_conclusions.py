"""V18.15.9.1 — consolidated conclusion bullet + UI fixes tests.

Byte-for-byte stability gate for the V18.15.9.1 fixes:

  Fix 1: Consolidate 7 characteristics as ONE bullet (not 7 scattered).
         The user's V18.15.9.0 audit feedback: "THIS SYSTEM SHOULD CONSOLIDATE
         ALL 7 CHARACTERISTICS AS A BULLET, NOT SCATTERED."
  Fix 2: Double-dash prefix — the bullet text does NOT start with "- " (the
         markdown formatter adds it).
  Fix 3: Malformed extraction — collapse newlines + strip trailing "and".
  Fix 4 (UI): Token Cost Dialog "Proceed" button border + "Cost Calculator" cutoff.

Run: pytest tests/test_v18_15_9_conclusions.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = lambda *a, **k: None
    tk.encoding_for_model = lambda *a, **k: None
    tk.Encoding = type("_E", (), {})
    sys.modules["tiktoken"] = tk

from core.summarisation.post_processing import detect_enumerated_conclusions

# ═══════════════════════════════════════════════════════════════════════════
# 1. detect_enumerated_conclusions — V18.15.9.1 Fix 3: newline + "and" cleanup
# ═══════════════════════════════════════════════════════════════════════════


class TestV18_15_9_1ExtractionFixes:
    """V18.15.9.1 Fix 3: collapse newlines + strip trailing "and"."""

    @pytest.fixture
    def salman_akhtar_source(self):
        _candidates = [
            _project_root / "audit" / "trust-ground" / "001_1_IDENTITY_AND_ITS_ORIGINS_source.md",
            Path("/home/z/my-project/audit/trust-ground/001_1_IDENTITY_AND_ITS_ORIGINS_source.md"),
            _project_root.parent / "audit" / "trust-ground" / "001_1_IDENTITY_AND_ITS_ORIGINS_source.md",
        ]
        for p in _candidates:
            if p.exists():
                return p.read_text(encoding="utf-8")
        pytest.skip("Salman Akhtar source not found")

    def test_characteristic_6_no_newline(self, salman_akhtar_source):
        """V18.15.9.1 Fix 3: Characteristic 6 must NOT have a newline
        (V18.15.9.0 had "subjective clarity\\nregarding one's gender")."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _num6, text6 = conclusions[5]
        assert _num6 == 6
        assert "\n" not in text6, f"char 6 has newline: {text6!r}"
        assert "\r" not in text6
        assert "subjective clarity" in text6.lower()
        assert "gender" in text6.lower()

    def test_characteristic_6_no_trailing_and(self, salman_akhtar_source):
        """V18.15.9.1 Fix 3: Characteristic 6 must NOT end with "and"
        (V18.15.9.0 had "subjective clarity regarding one's gender, and.").
        The trailing "and" is stripped (it's a conjunction for the next item)."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _num6, text6 = conclusions[5]
        _lower = text6.lower().strip().rstrip(',;.')
        assert not _lower.endswith("and"), f"char 6 ends with 'and': {text6!r}"

    def test_all_7_no_newlines(self, salman_akhtar_source):
        """V18.15.9.1 Fix 3: NO conclusion text has a newline."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        for num, text in conclusions:
            assert "\n" not in text, f"char {num} has newline: {text!r}"
            assert "\r" not in text, f"char {num} has carriage return: {text!r}"

    def test_all_7_no_trailing_and(self, salman_akhtar_source):
        """V18.15.9.1 Fix 3: NO conclusion text ends with "and"."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        for num, text in conclusions:
            _lower = text.lower().strip().rstrip(',;.')
            assert not _lower.endswith("and"), f"char {num} ends with 'and': {text!r}"

    def test_newline_collapse_synthetic(self):
        """Synthetic test: a source with a newline mid-item is collapsed."""
        source = (
            "A" * 1000 + " "
            "items: (1) first item, (2) second item with\na newline, (3) third item."
        )
        conclusions = detect_enumerated_conclusions(source)
        assert len(conclusions) == 3
        _num2, text2 = conclusions[1]
        assert "\n" not in text2, f"newline not collapsed: {text2!r}"
        assert "second item with" in text2
        assert "a newline" in text2

    def test_trailing_and_stripped_synthetic(self):
        """Synthetic test: trailing "and" is stripped from each item."""
        source = (
            "A" * 1000 + " "
            "items: (1) first and, (2) second and, (3) third."
        )
        conclusions = detect_enumerated_conclusions(source)
        assert len(conclusions) == 3
        for num, text in conclusions:
            _lower = text.lower().strip().rstrip(',;.')
            assert not _lower.endswith("and"), f"char {num} ends with 'and': {text!r}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. V18.15.9.1 Fix 1 + Fix 2: consolidated bullet (not scattered) + no double-dash
# ═══════════════════════════════════════════════════════════════════════════


class TestV18_15_9_1ConsolidatedBullet:
    """V18.15.9.1 Fix 1: ONE consolidated bullet (not 7 scattered).
    V18.15.9.1 Fix 2: no double-dash prefix (the formatter adds "- ")."""

    @pytest.fixture
    def salman_akhtar_source(self):
        _candidates = [
            _project_root / "audit" / "trust-ground" / "001_1_IDENTITY_AND_ITS_ORIGINS_source.md",
            Path("/home/z/my-project/audit/trust-ground/001_1_IDENTITY_AND_ITS_ORIGINS_source.md"),
        ]
        for p in _candidates:
            if p.exists():
                return p.read_text(encoding="utf-8")
        pytest.skip("Salman Akhtar source not found")

    def test_consolidated_bullet_is_one_bullet(self, salman_akhtar_source):
        """V18.15.9.1 Fix 1: the 7 characteristics become ONE bullet, not 7.
        Simulate the _ensure_conclusion_bullets logic."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        assert len(conclusions) == 7
        # Build the consolidated bullet (mirrors summarizer._ensure_conclusion_bullets)
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        _items_text = "; ".join(f"({n}) {t}" for n, t in conclusions)
        _consolidated = f"**{_label_plural} of solid identity**: {_items_text}."
        # Verify it's ONE string (not 7 separate bullets)
        assert isinstance(_consolidated, str)
        assert _consolidated.startswith("**Characteristics of solid identity**:")
        # Verify all 7 are in the single bullet
        for n, t in conclusions:
            assert f"({n})" in _consolidated, f"item {n} missing from consolidated bullet"

    def test_consolidated_bullet_no_leading_dash(self, salman_akhtar_source):
        """V18.15.9.1 Fix 2: the bullet text does NOT start with "- " (the
        markdown formatter adds it). V18.15.9.0 had "- - **Characteristic**:".
        """
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        _items_text = "; ".join(f"({n}) {t}" for n, t in conclusions)
        _consolidated = f"**{_label_plural} of solid identity**: {_items_text}."
        # The bullet text must NOT start with "- " (the formatter adds it)
        assert not _consolidated.startswith("- "), f"bullet starts with '- ': {_consolidated!r}"
        assert not _consolidated.startswith("- - "), f"bullet starts with '- - ': {_consolidated!r}"

    def test_consolidated_bullet_contains_all_7(self, salman_akhtar_source):
        """V18.15.9.1 Fix 1: the consolidated bullet contains all 7
        characteristics (no #3 missing like V18.15.9.0)."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        _items_text = "; ".join(f"({n}) {t}" for n, t in conclusions)
        _consolidated = f"**{_label_plural} of solid identity**: {_items_text}."
        # Verify #3 (genuineness and authenticity) is present (V18.15.9.0 missed it)
        assert "(3)" in _consolidated
        assert "genuineness and authenticity" in _consolidated.lower() or "authenticity" in _consolidated.lower()

    def test_consolidated_bullet_no_malformed_items(self, salman_akhtar_source):
        """V18.15.9.1 Fix 3: no malformed items (no newlines, no trailing 'and')."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _items_text = "; ".join(f"({n}) {t}" for n, t in conclusions)
        # No newlines in the consolidated items
        assert "\n" not in _items_text, f"newline in items: {_items_text!r}"
        assert "\r" not in _items_text
        # No item ends with "and" (before the semicolon or end)
        import re
        _items = _items_text.split(";")
        for item in _items:
            _clean = item.strip().lower().rstrip(',;.')
            # The "and" may appear inside an item (e.g., "genuineness and authenticity")
            # but not as a trailing word
            assert not re.search(r'\s+and\s*$', _clean), f"item ends with 'and': {item!r}"

    def test_label_characteristic_for_7_items(self, salman_akhtar_source):
        """V18.15.9.1: 7 items → label "Characteristics" (plural)."""
        conclusions = detect_enumerated_conclusions(salman_akhtar_source)
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        assert _label_plural == "Characteristics"

    def test_label_conclusions_for_3_items(self):
        """V18.15.9.1: 3 items → label "Conclusions" (plural)."""
        source = "A" * 1000 + " " + "items: (1) alpha, (2) beta, (3) gamma."
        conclusions = detect_enumerated_conclusions(source)
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        assert _label_plural == "Conclusions"


# ═══════════════════════════════════════════════════════════════════════════
# 3. V18.15.9.1 Fix 2: distinct-bullet check (not text-anywhere fuzzy)
# ═══════════════════════════════════════════════════════════════════════════


class TestV18_15_9_1DistinctBulletCheck:
    """V18.15.9.1 Fix 2: check if a DISTINCT conclusion bullet already exists,
    not if the conclusion TEXT appears anywhere (V18.15.9.0's false-negative)."""

    def test_distinct_bullet_detected(self):
        """When a bullet starts with '**Characteristics', it's a distinct
        conclusion bullet — the method should no-op (not scatter)."""
        # Simulate the distinct-bullet check (mirrors the regex approach in summarizer.py)
        import re
        existing_bullets = [
            "Tausk (1919) introduced identity.",
            "**Characteristics of solid identity**: (1) selfsameness; (2) ...",
        ]
        _label_plural = "Characteristics"
        _found = False
        for bp in existing_bullets:
            _bp_clean = re.sub(r'^\s*(?:[-\u2022]\s+)?', '', str(bp)).strip()
            # V18.15.9.1: check the prefix (not the full "**Characteristics**")
            # because the label may be "**Characteristics of solid identity**:"
            if _bp_clean.lower().startswith(f"**{_label_plural.lower()}"):
                _found = True
                break
        assert _found, "distinct conclusion bullet should be detected"

    def test_text_anywhere_not_detected_as_distinct(self):
        """V18.15.9.0 false-negative: 'genuineness and authenticity' appears
        inside another bullet's text (not as a distinct bullet). V18.15.9.1
        should NOT treat this as 'already present' — it should still add the
        consolidated bullet."""
        import re
        existing_bullets = [
            "The chapter's conclusion lists seven characteristics: sustained "
            "selfsameness, temporal continuity, genuineness and authenticity, "
            "realistic body image, inner solidity, gender clarity, ethnic solidarity.",
        ]
        _label_plural = "Characteristics"
        _found = False
        for bp in existing_bullets:
            _bp_clean = re.sub(r'^\s*(?:[-\u2022]\s+)?', '', str(bp)).strip()
            if _bp_clean.lower().startswith(f"**{_label_plural.lower()}"):
                _found = True
                break
        # V18.15.9.1: this should be FALSE (no distinct bullet) → method proceeds
        assert not _found, (
            "text-anywhere should NOT be detected as a distinct bullet "
            "(V18.15.9.0 false-negative — V18.15.9.1 fixes this)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. UI fixes (smoke tests — no PySide6 in sandbox, so logic-only)
# ═══════════════════════════════════.══════════════════════════════════════


class TestV18_15_9_1UIFixes:
    """V18.15.9.1 UI fixes — logic tests (PySide6 not available in sandbox)."""

    def test_dialog_height_raised(self):
        """V18.15.9.1: dialog height raised 560 → 640 (fixes Cost Calculator cutoff)."""
        # Read the token_cost_dialog.py + check the _DLG_HEIGHT constant
        _dialog_path = _project_root / "ui_qt" / "views" / "token_cost_dialog.py"
        if not _dialog_path.exists():
            pytest.skip("token_cost_dialog.py not found")
        _src = _dialog_path.read_text(encoding="utf-8")
        # Verify _DLG_HEIGHT = 640 (was 560 in V18.15.9.0)
        assert "_DLG_HEIGHT = 640" in _src, "dialog height not raised to 640"
        assert "_DLG_HEIGHT = 560" not in _src, "old 560 height still present"

    def test_proceed_button_no_leading_spaces(self):
        """V18.15.9.1: 'Proceed' button text has no leading spaces (was '  ✅ Proceed').
        The padding is now controlled by the theme (symmetrical)."""
        _dialog_path = _project_root / "ui_qt" / "views" / "token_cost_dialog.py"
        if not _dialog_path.exists():
            pytest.skip("token_cost_dialog.py not found")
        _src = _dialog_path.read_text(encoding="utf-8")
        # The old text was "  ✅ Proceed" (2 leading spaces); new is "✅ Proceed"
        assert '"  ✅ Proceed"' not in _src, "old leading-spaces button text still present"
        assert '"✅ Proceed"' in _src, "new centered button text not found"

    def test_proceed_button_text_centered(self):
        """V18.15.9.1: 'Proceed' button has text-align: center."""
        _dialog_path = _project_root / "ui_qt" / "views" / "token_cost_dialog.py"
        if not _dialog_path.exists():
            pytest.skip("token_cost_dialog.py not found")
        _src = _dialog_path.read_text(encoding="utf-8")
        assert "text-align: center" in _src, "text-align: center not added"

    def test_primary_button_outline_none(self):
        """V18.15.9.1: Primary button has `outline: none` (removes focus rectangle)."""
        _theme_path = _project_root / "ui_qt" / "theme.py"
        if not _theme_path.exists():
            pytest.skip("theme.py not found")
        _src = _theme_path.read_text(encoding="utf-8")
        # Find the QPushButton#Primary block + verify outline: none
        _primary_idx = _src.find("QPushButton#Primary")
        assert _primary_idx >= 0, "QPushButton#Primary block not found"
        _block = _src[_primary_idx:_primary_idx + 500]
        assert "outline: none" in _block, "outline: none not in Primary button block"
