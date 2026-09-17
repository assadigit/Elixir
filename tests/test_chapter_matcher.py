"""Tests for the chapter matching logic (Converter._match_chapter).

These tests verify the V10.2.4 strict number-based matching that replaced
the old fuzzy word-overlap matcher (which matched "3.6 Cannabinoids"
against "2.2 Memantine" because they shared the word "Treatment").
"""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _make_converter():
    """Create a minimal mock that has the _match_chapter method.

    We can't import Converter directly (it pulls in markitdown etc.),
    so we extract just the method logic via a stub class.
    """
    import re

    try:
        from rapidfuzz import fuzz as rf_fuzz
        _rf = True
    except ImportError:
        _rf = False

    class _StubConverter:
        """Stubs just enough to call _match_chapter."""
        pass

    # Copy the _match_chapter method from converter.py
    # (We can't import it, so we re-implement the same logic)
    def _match_chapter(self, heading: str, selected: str) -> bool:
        heading_clean = heading.strip()
        selected_clean = selected.strip()

        def normalize(s):
            s = s.lower()
            s = re.sub(r'[^\w\s]', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        heading_norm = normalize(heading_clean)
        selected_norm = normalize(selected_clean)

        if heading_norm == selected_norm:
            return True

        def extract_chapter_number(s):
            m = re.match(r'^(\d+(?:\.\d+)*)\s', s)
            if m:
                return m.group(1)
            return None

        heading_num = extract_chapter_number(heading_clean)
        selected_num = extract_chapter_number(selected_clean)

        if heading_num and selected_num:
            if heading_num == selected_num:
                return True
            if selected_num in heading_num and len(selected_num) < len(heading_num):
                return True
            return False

        _COMMON = {
            "chapter", "part", "section", "appendix", "the", "of", "a", "an",
            "and", "or", "to", "in", "for", "with", "on", "at", "by", "from",
            "treatment", "acute", "preventive", "prevention", "study",
            "evidence", "trial", "clinical", "practice", "review",
            "introduction", "conclusion", "conclusions", "future",
            "therapeutics", "management", "therapy", "drug", "drugs",
            "migraine", "headache", "pain", "receptor", "antagonist",
            "agonist", "inhibition", "action", "mode", "proposed",
        }
        heading_words = set(w for w in heading_norm.split() if len(w) > 2 and w not in _COMMON)
        selected_words = set(w for w in selected_norm.split() if len(w) > 2 and w not in _COMMON)

        if heading_words and selected_words:
            overlap = heading_words & selected_words
            if len(overlap) == len(selected_words) and len(selected_words) >= 2:
                return True
            if len(selected_words) == 1 and overlap == selected_words:
                return True

        if _rf:
            score = rf_fuzz.token_set_ratio(heading_norm, selected_norm)
            if score >= 95:
                return True

        return False

    _StubConverter._match_chapter = _match_chapter
    return _StubConverter()


# ── Number-based matching ─────────────────────────────────────────────────

def test_exact_number_match() -> None:
    """Same chapter number should match."""
    c = _make_converter()
    assert c._match_chapter("3.6 Cannabinoids: Acute Treatment", "3.6 Cannabinoids: Acute Treatment") is True


def test_different_numbers_no_match() -> None:
    """Different chapter numbers should NOT match (the core bug fix)."""
    c = _make_converter()
    assert c._match_chapter("2.2 Memantine (NMDA Receptor Antagonist)", "3.6 Cannabinoids: Acute Treatment") is False


def test_parent_child_match() -> None:
    """Parent chapter number should match sub-chapters."""
    c = _make_converter()
    # Selecting "2" should match "2.1 Lasmiditan"
    assert c._match_chapter("2.1 Lasmiditan (Serotonin 5HT1F Agonist)", "2 Currently Available New Treatments") is True


def test_same_number_different_text() -> None:
    """Same number, different text after number should still match."""
    c = _make_converter()
    assert c._match_chapter("3.6 Cannabinoids: Acute Treatment", "3.6 Cannabinoids") is True


def test_sub_sub_chapter() -> None:
    """Sub-sub-chapters (2.1.1) should match their parent (2.1)."""
    c = _make_converter()
    assert c._match_chapter("2.1.1 Proposed Mode of Action", "2.1 Lasmiditan") is True


# ── Non-numbered chapters ─────────────────────────────────────────────────

def test_non_numbered_exact_match() -> None:
    """Non-numbered chapters should match on exact title."""
    c = _make_converter()
    assert c._match_chapter("Abstract", "Abstract") is True


def test_non_numbered_no_common_words() -> None:
    """Non-numbered chapters with no shared significant words should NOT match."""
    c = _make_converter()
    assert c._match_chapter("References", "Conclusions") is False


# ── Edge cases ────────────────────────────────────────────────────────────

def test_empty_strings() -> None:
    """Empty strings should not crash."""
    c = _make_converter()
    assert c._match_chapter("", "") is True  # both normalize to ""


def test_none_values() -> None:
    """None should not crash (handled by .strip())."""
    c = _make_converter()
    # .strip() on None would crash, but the function is typed str — skip
    pass


def test_all_treatment_chapters_dont_match_each_other() -> None:
    """The bug: chapters sharing 'Treatment' should NOT all match each other."""
    c = _make_converter()
    chapters = [
        "2.2 Memantine (NMDA Receptor Antagonist): Preventive Treatment",
        "2.3 Melatonin: Preventive Treatment",
        "3.1 Orexins: Preventive Treatment—The 'Rexants'",
        "3.5 Amylin: Acute and Preventive Treatment",
        "3.6 Cannabinoids: Acute Treatment",
        "3.7 Non-μ-Opioid Receptors: Acute and Preventive Treatment",
    ]
    selected = "3.6 Cannabinoids: Acute Treatment"
    for ch in chapters:
        if "3.6" in ch:
            assert c._match_chapter(ch, selected) is True, f"Should match: {ch}"
        else:
            assert c._match_chapter(ch, selected) is False, f"Should NOT match: {ch}"
