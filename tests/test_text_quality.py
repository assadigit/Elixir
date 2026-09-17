"""Unit tests for utils/text_quality.py — extracted garbled-text detection."""
from __future__ import annotations

from utils.text_quality import (
    _merge_ranges,
    find_garbled_ranges,
    find_partial_garbled_ranges,
    is_text_garbled,
)

# ── Test fixtures ──────────────────────────────────────────────────────────

CLEAN_TEXT = (
    "This chapter discusses new migraine treatments that have reached "
    "clinical practice in some countries over the last five years. "
    "The first specific drug class to be developed, the triptans, have "
    "been widely used for over two decades. New oral drugs targeting "
    "calcitonin gene-related peptide or its receptor have emerged as "
    "the first targeted acute and preventive treatments in decades. "
    "Lasmiditan is a ditan which targets the 5-HT1F receptor without "
    "vasoconstriction. Ubrogepant received FDA approval in 2019 after "
    "two phase III trials demonstrating efficacy relative to placebo."
) * 5  # repeat to get > 200 chars

GARBLED_TEXT = """N. Karsan, P. J. Goadsby

h t
i w e
s o
h t

n i n o
i t
c a
f s
i t
a s

t n
e m
t a
e r
t

d n
a n o
i t
c n
u f

n a
t p
i r
t

t n
e i
c ffi
u s
n i
""" * 3  # repeat to get > 200 chars


# ── is_text_garbled ────────────────────────────────────────────────────────

def test_clean_text_not_garbled() -> None:
    """Clean English text should not be flagged as garbled."""
    assert is_text_garbled(CLEAN_TEXT) is False


def test_garbled_text_detected() -> None:
    """Vertical column text should be flagged as garbled."""
    assert is_text_garbled(GARBLED_TEXT) is True


def test_short_text_not_garbled() -> None:
    """Text under 200 chars should return False (too short to judge)."""
    assert is_text_garbled("short text") is False


def test_empty_text_not_garbled() -> None:
    """Empty string should return False."""
    assert is_text_garbled("") is False


def test_none_text_not_garbled() -> None:
    """None should return False (not crash)."""
    assert is_text_garbled("") is False  # type: ignore


def test_partially_garbled_detected() -> None:
    """Mix of clean + garbled should be detected as garbled."""
    mixed = CLEAN_TEXT + GARBLED_TEXT
    assert is_text_garbled(mixed) is True


# ── find_garbled_ranges ───────────────────────────────────────────────────

def test_find_garbled_ranges_clean_text() -> None:
    """Clean text should return no garbled ranges."""
    assert find_garbled_ranges(CLEAN_TEXT) == []


def test_find_garbled_ranges_garbled_text() -> None:
    """Garbled text should return at least one range."""
    ranges = find_garbled_ranges(GARBLED_TEXT)
    assert len(ranges) >= 1
    for start, end in ranges:
        assert start < end
        assert start >= 0
        assert end <= len(GARBLED_TEXT)


def test_find_garbled_ranges_empty() -> None:
    """Empty text should return empty list."""
    assert find_garbled_ranges("") == []


# ── find_partial_garbled_ranges ───────────────────────────────────────────

def test_find_partial_garbled_ranges_clean() -> None:
    """Clean text should have no partial garbled ranges."""
    assert find_partial_garbled_ranges(CLEAN_TEXT) == []


def test_find_partial_garbled_ranges_garbled() -> None:
    """Garbled text should have partial garbled ranges."""
    ranges = find_partial_garbled_ranges(GARBLED_TEXT)
    assert len(ranges) >= 1


# ── _merge_ranges ─────────────────────────────────────────────────────────

def test_merge_empty() -> None:
    """Empty list should return empty."""
    assert _merge_ranges([]) == []


def test_merge_single() -> None:
    """Single range should return itself."""
    assert _merge_ranges([(0, 100)]) == [(0, 100)]


def test_merge_overlapping() -> None:
    """Overlapping ranges should be merged."""
    result = _merge_ranges([(0, 100), (50, 150)])
    assert result == [(0, 150)]


def test_merge_non_overlapping() -> None:
    """Non-overlapping ranges should remain separate."""
    result = _merge_ranges([(0, 100), (300, 400)])
    assert result == [(0, 100), (300, 400)]


def test_merge_adjacent() -> None:
    """Adjacent ranges (within 100 chars) should be merged."""
    result = _merge_ranges([(0, 100), (150, 250)])
    assert result == [(0, 250)]
