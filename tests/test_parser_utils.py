"""Tests for the parser utilities (strip_markup_tags, strip_reasoning_leaks).

These are the functions that clean LLM output — they caused the most bugs
in the V10.x debug sessions (XML tags leaking into DOCX, reasoning leaking
into summaries, etc.).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Markup tag stripping ──────────────────────────────────────────────────
# Re-implement the regex here (can't import summarizer due to deps)

_MARKUP_TAG_RE = re.compile(
    r'</?(?:'
    r'finding|claim|snippet|source_ref|evidence_quote|verdict|reason|index'
    r'|executive_summary|bullet_points|point|reference|summary|response|output|result'
    r'|thought|thinking|analysis|reasoning|key_point|key_takeaway|takeaway'
    r'|chapter|section|paragraph|sentence|quote|quotation|citation|cite'
    r'|metadata|meta|tag|label|json|xml|html|code|pre'
    r'|source|source_reference|text_snippet|supporting_text|bullet'
    r')\s*/?>',
    re.IGNORECASE,
)
_GENERIC_MARKUP_TAG_RE = re.compile(r'</?[a-z_][a-z_0-9]{0,29}\s*/?>', re.IGNORECASE)


def strip_markup_tags(text: str) -> str:
    """Strip XML/JSON markup tags from text."""
    if not text:
        return text
    cleaned = _MARKUP_TAG_RE.sub('', text)
    cleaned = _GENERIC_MARKUP_TAG_RE.sub('', cleaned)
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    return cleaned.strip()


# ── Reasoning leak stripping ──────────────────────────────────────────────

_REASONING_PATTERNS = [
    r'(?:This is a|These are) (?:missed|missing) concept[s]? because[^.]*\.',
    r'this suggests[^.]*\.',
    r'[Tt]his (?:is also|refers to) (?:a |an )?(?:missed|missing) concept[^.]*\.',
    r'[Tt]he existing bullets (?:probably )?(?:don\'t|do not) cover[^.]*\.',
    r'I should focus on[^.]*\.',
    r'[Tt]he abstract (?:also )?mentions[^.]*\.',
    r'[Tt]he user specifically wants[^.]*\.',
    r'I\'ll check[^.]*\.',
    r'[Ss]ince I don\'t have[^.]*\.',
    r'I\'ll (?:prioritize|assume|include|add|focus)[^.]*\.',
    r'[Hh]owever, the (?:instruction|user) says[^.]*\.',
    r'[Tt]he (?:missed|missing) concepts (?:are|is)[^.]*\.',
    r'[Tt]his could be a missed concept[^.]*\.',
    r'I can still include[^.]*\.',
    r'I might (?:not )?(?:need|skip|include)[^.]*\.',
]


def strip_reasoning_leaks(text: str) -> str:
    """Strip plain-text reasoning that leaks from gap-fill + self-review."""
    if not text:
        return text
    for pattern in _REASONING_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


# ── Tests ─────────────────────────────────────────────────────────────────

def test_strip_markup_tags_removes_known_tags() -> None:
    """All known XML tags should be stripped."""
    text = "<executive_summary>Test content</executive_summary>"
    assert strip_markup_tags(text) == "Test content"


def test_strip_markup_tags_removes_nested_tags() -> None:
    """Nested tags should be stripped."""
    text = "<finding><claim>Test claim</claim><snippet>Quote</snippet></finding>"
    result = strip_markup_tags(text)
    assert "<" not in result
    assert "Test claim" in result
    assert "Quote" in result


def test_strip_markup_tags_removes_point_tags() -> None:
    """<point> tags should be stripped."""
    text = "<point>This is a bullet</point>"
    assert strip_markup_tags(text) == "This is a bullet"


def test_strip_markup_tags_preserves_content() -> None:
    """Content between tags should be preserved."""
    text = "<executive_summary>Migraine is a neurological disorder.</executive_summary>"
    result = strip_markup_tags(text)
    assert "Migraine is a neurological disorder" in result
    assert "<" not in result


def test_strip_markup_tags_empty() -> None:
    """Empty string should return empty."""
    assert strip_markup_tags("") == ""


def test_strip_markup_tags_no_tags() -> None:
    """Text without tags should be unchanged."""
    text = "This is plain text with no tags."
    assert strip_markup_tags(text) == text


def test_strip_markup_tags_generic_fallback() -> None:
    """Unknown tags should be caught by the generic fallback."""
    text = "<unknown_tag>Content</unknown_tag>"
    result = strip_markup_tags(text)
    assert "<" not in result
    assert "Content" in result


# ── Reasoning leak tests ──────────────────────────────────────────────────

def test_strip_reasoning_missed_concept() -> None:
    """'This is a missed concept because...' should be stripped."""
    text = "Real bullet. This is a missed concept because the existing bullets don't cover it."
    result = strip_reasoning_leaks(text)
    assert "missed concept" not in result
    assert "Real bullet" in result


def test_strip_reasoning_this_suggests() -> None:
    """'this suggests...' should be stripped."""
    text = "Real bullet. this suggests a phase III trial involving memantine."
    result = strip_reasoning_leaks(text)
    assert "this suggests" not in result
    assert "Real bullet" in result


def test_strip_reasoning_multiple_patterns() -> None:
    """Multiple reasoning patterns in one text should all be stripped."""
    text = (
        "Bullet one. This is a missed concept because reasons. "
        "Bullet two. I should focus on the missing parts. "
        "Bullet three."
    )
    result = strip_reasoning_leaks(text)
    assert "missed concept" not in result
    assert "I should focus" not in result
    assert "Bullet one" in result
    assert "Bullet two" in result
    assert "Bullet three" in result


def test_strip_reasoning_preserves_real_content() -> None:
    """Real summary content should not be stripped."""
    text = "Triptans carry vascular risk and cannot be used in elderly patients."
    result = strip_reasoning_leaks(text)
    assert result == text


def test_strip_reasoning_empty() -> None:
    """Empty string should return empty."""
    assert strip_reasoning_leaks("") == ""
