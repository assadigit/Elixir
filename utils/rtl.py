"""V0.6.5 — RTL (right-to-left) script detection for the output formatters.

The Summarizer / Translation / Styler service tools can now emit
right-to-left documents (Persian, Arabic, Hebrew, …). Deciding the
direction is a pure text property, so it lives in ``utils`` (a leaf
module — stdlib only, importable from ``core.outputs``,
``core.summarisation`` and the dialogs without cycles).

Design notes (content-agnostic by construction — Rule 1):
  - The detector counts LETTERS only (Unicode categories starting with
    "L"). Digits, punctuation, whitespace and markdown syntax never vote,
    so ``"- **Steam Cloud** — 5 GB"`` is judged by its letters alone.
  - A text is RTL-dominant when at least 35% of its letters are from RTL
    scripts. A Persian article with English product names stays RTL; an
    English article quoting one Persian sentence stays LTR.
  - No language NAME is detected — only script blocks — so the rule
    generalizes to any RTL script the ranges cover.
"""

from __future__ import annotations

import unicodedata

# Unicode block ranges whose letters are written right-to-left.
# (Arabic incl. Supplement + presentation forms, Hebrew incl. presentation
# forms, Syriac, Thaana, NKo, Samaritan, Mandaic, Arabic Ext-A/B.)
_RTL_RANGES: tuple[tuple[int, int], ...] = (
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0700, 0x074F),  # Syriac
    (0x0750, 0x077F),  # Arabic Supplement
    (0x0780, 0x07BF),  # Thaana
    (0x07C0, 0x07FF),  # NKo
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB1D, 0xFDFF),  # Hebrew presentation forms (incl. ligatures)
    (0xFE70, 0xFEFF),  # Arabic presentation forms
    (0x10800, 0x108FF),  # Cypriot syllabary / Phoenician region (RTL)
)


def _is_rtl_char(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _RTL_RANGES)


def rtl_ratio(text: str) -> float:
    """Fraction of RTL letters among all letters in ``text``.

    Returns 0.0 for empty / letter-free text (never a crash).
    """
    rtl = 0
    total = 0
    for ch in text:
        if unicodedata.category(ch).startswith("L"):
            total += 1
            if _is_rtl_char(ch):
                rtl += 1
    return (rtl / total) if total else 0.0


def is_rtl_dominant(text: str, threshold: float = 0.35) -> bool:
    """True when RTL letters make up ≥ ``threshold`` of all letters.

    ``threshold=0.35``: a genuinely RTL document (Persian article with
    English tech terms mixed in) clears it easily; an LTR document with a
    quoted RTL sentence does not.
    """
    return rtl_ratio(text) >= threshold
