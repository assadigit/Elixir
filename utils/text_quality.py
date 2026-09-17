"""Text quality detection utilities — shared across pipeline stages.

Extracted from Converter._is_text_garbled() in V10.2.6 to break the
circular import between core.pipeline.converter and core.summarisation.summarizer.

This module has NO dependencies on any core/ module — it's pure Python.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["is_text_garbled", "find_garbled_ranges", "find_partial_garbled_ranges"]


def is_text_garbled(text: str) -> bool:
    """Detect if text was extracted with vertical column reading.

    Scans 5 sections across the full text (at 0%, 20%, 40%, 60%, 80%
    positions).  If ANY section has 2+ bad metrics, the whole text is
    flagged as garbled.

    Bad metrics:
        - Average word length < 2.5 chars
        - >50% of words are 1-2 characters
        - >30% of lines are single characters
        - Space-to-character ratio < 8%
    """
    if not text or len(text) < 200:
        return False

    text_len = len(text)
    sample_size = min(3000, text_len // 5)
    if sample_size < 500:
        sample_size = text_len

    for i in range(5):
        start = (text_len * i) // 5
        end = min(start + sample_size, text_len)
        if end - start < 200:
            continue
        if _is_section_garbled(text[start:end]):
            return True

    return False


def _is_section_garbled(sample: str) -> bool:
    """Check if a single text section is garbled (2+ bad metrics)."""
    words = sample.split()
    if not words:
        return True  # empty section = garbled

    avg_word_len = sum(len(w) for w in words) / len(words)
    short_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
    lines = sample.splitlines()
    line_ratio = sum(
        1 for l in lines if l.strip() and len(l.strip()) <= 2
    ) / max(1, len(lines))
    space_ratio = sample.count(' ') / max(1, len(sample))

    signals = sum([
        avg_word_len < 2.5,
        short_ratio > 0.5,
        line_ratio > 0.3,
        space_ratio < 0.08,
    ])
    return signals >= 2


def find_garbled_ranges(text: str) -> list[tuple[int, int]]:
    """Find character ranges in the text that are garbled.

    Returns a list of (start, end) tuples for garbled sections.
    Scans the text in 2000-char windows with 500-char overlap.
    """
    if not text or len(text) < 200:
        return []

    ranges: list[tuple[int, int]] = []
    window = 2000
    overlap = 500
    step = window - overlap
    text_len = len(text)
    i = 0
    while i < text_len:
        sample = text[i:i + window]
        if len(sample) < 200:
            break
        if _is_section_garbled(sample):
            ranges.append((i, min(i + window, text_len)))
        i += step

    return _merge_ranges(ranges)


def find_partial_garbled_ranges(text: str) -> list[tuple[int, int]]:
    """Find sections with partial garbling (avg word length < 3.5).

    Used for academic papers where the main detector doesn't fire
    but some sections have suspiciously short words.
    """
    if not text or len(text) < 200:
        return []

    ranges: list[tuple[int, int]] = []
    window = 1000
    overlap = 300
    step = window - overlap
    text_len = len(text)
    i = 0
    while i < text_len:
        sample = text[i:i + window]
        if len(sample) < 200:
            break
        words = sample.split()
        if words:
            avg = sum(len(w) for w in words) / len(words)
            if avg < 3.5:
                ranges.append((i, min(i + window, text_len)))
        i += step

    return _merge_ranges(ranges)


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent ranges."""
    if not ranges:
        return []
    ranges.sort()
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        if start <= merged[-1][1] + 100:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
