"""Property-based tests: ``utils/text_utils.py`` contracts (roadmap 2.2).

Targets ``utils/text_utils.py`` (Phase 2, task 2.2 of
docs/ROADMAP_V0.12.md — "Hypothesis property suites").

Invariants under test (characterization of the ACTUAL contract):

1. ``detect_persian_text`` — the decision is EXACTLY the ratio contract:
   ``count(Persian chars) / len(text) > threshold``; empty → False;
   pure-ASCII → False; pure-Persian → True at the default threshold.
2. ``remove_page_number_headings`` — only ``# Page N`` / ``# N`` heading
   lines are removed; all other lines survive byte-identical; idempotent.
3. ``convert_separators_to_comments`` — every ``--- page ---`` becomes
   ``<!-- page break -->``; idempotent (no separator survives one pass).
4. ``insert_page_number_comments`` — output = marker + ``\\n`` + original
   text; the marker carries the page number verbatim; stripping the first
   line recovers the input exactly.
5. ``optimize_for_tokens`` — ``token_saver=False`` → identity; idempotent;
   after one pass no line has trailing blanks, no run of 3+ newlines
   survives, and ``*``/``+``/``•`` list markers are normalised to ``-``.
6. ``fix_missing_spaces`` — never fires when disabled (either flag) or on
   Persian text (identity contract — wordninja is English-only).

Determinism: no network, no LLM, no filesystem writes; pure functions.
Hypothesis settings tuned per test (``deadline=None``).
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from utils.text_utils import (
    PERSIAN_UNICODE_RANGE,
    convert_separators_to_comments,
    detect_persian_text,
    fix_missing_spaces,
    insert_page_number_comments,
    optimize_for_tokens,
    remove_page_number_headings,
)

# ── settings profiles (tuned for the <60s whole-suite budget) ───────────────
S_FAST = settings(max_examples=100, deadline=None)

# ═══════════════════════════════════════════════════════════════════════════
# Generators
# ═══════════════════════════════════════════════════════════════════════════

_ascii_text = st.text(alphabet="abcXYZ .,\n", min_size=0, max_size=300)
_persian_char = st.sampled_from("ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")
_persian_text = st.lists(_persian_char, min_size=1, max_size=50).map("".join)
_any_text = st.text(min_size=0, max_size=300)
_page_num = st.integers(min_value=0, max_value=100_000)

_body_line = st.sampled_from(
    [
        "A normal paragraph line.",
        "## A Real Heading",
        "- a list item",
        "text with numbers 123",
        "",
    ]
)


def _ratio(text: str) -> float:
    """Executable spec of the Persian-ratio decision input."""
    if not text:
        return 0.0
    return len(PERSIAN_UNICODE_RANGE.findall(text)) / len(text)


# ═══════════════════════════════════════════════════════════════════════════
# 1. detect_persian_text — the ratio contract
# ═══════════════════════════════════════════════════════════════════════════


@given(text=_any_text, threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@S_FAST
def test_detect_persian_matches_ratio_contract(text, threshold):
    assert detect_persian_text(text, threshold) == (_ratio(text) > threshold)


@given(text=_ascii_text)
@S_FAST
def test_detect_persian_false_on_pure_ascii(text):
    assert detect_persian_text(text) is False


@given(text=_persian_text)
@S_FAST
def test_detect_persian_true_on_pure_persian(text):
    assert detect_persian_text(text) is True


@given(text=st.one_of(st.just(""), st.just("   ")))
@S_FAST
def test_detect_persian_false_on_empty(text):
    assert detect_persian_text(text) is False


# ═══════════════════════════════════════════════════════════════════════════
# 2. remove_page_number_headings
# ═══════════════════════════════════════════════════════════════════════════


@given(page=_page_num, level=st.sampled_from(["#", "##", "###", "####"]))
@S_FAST
def test_page_number_headings_removed(page, level):
    text = f"{level} Page {page}\nbody stays\n"
    out = remove_page_number_headings(text)
    assert "body stays" in out
    assert f"Page {page}" not in out


@given(page=_page_num, level=st.sampled_from(["#", "##"]))
@S_FAST
def test_bare_number_headings_removed(page, level):
    text = f"{level} {page}\nbody stays\n"
    out = remove_page_number_headings(text)
    assert "body stays" in out
    assert not re.search(rf"^{level} {page}$", out, flags=re.MULTILINE)


@given(lines=st.lists(_body_line, min_size=0, max_size=20))
@S_FAST
def test_remove_page_headings_keeps_other_lines_and_is_idempotent(lines):
    text = "\n".join(lines)
    once = remove_page_number_headings(text)
    twice = remove_page_number_headings(once)
    assert twice == once
    for line in lines:
        if line and not re.match(r"^#+\s+(Page\s+)?\d+\s*$", line):
            assert line in once


# ═══════════════════════════════════════════════════════════════════════════
# 3. convert_separators_to_comments
# ═══════════════════════════════════════════════════════════════════════════


@given(before=_any_text, after=_any_text, count=st.integers(min_value=1, max_value=5))
@S_FAST
def test_separators_converted(before, after, count):
    text = before + ("--- page ---" * count) + after
    out = convert_separators_to_comments(text)
    assert "--- page ---" not in out
    assert out.count("<!-- page break -->") == count


@given(text=_any_text)
@S_FAST
def test_separator_conversion_idempotent_and_preserves_separator_free_text(text):
    out = convert_separators_to_comments(text)
    assert convert_separators_to_comments(out) == out
    if "--- page ---" not in text:
        assert out == text


# ═══════════════════════════════════════════════════════════════════════════
# 4. insert_page_number_comments
# ═══════════════════════════════════════════════════════════════════════════


@given(text=_any_text, page=_page_num)
@S_FAST
def test_page_comment_prefix_and_roundtrip(text, page):
    out = insert_page_number_comments(text, page)
    assert out.startswith(f"<!-- original page {page} -->\n")
    stripped = out.split("\n", 1)[1] if "\n" in out else ""
    assert stripped == text


@given(page=_page_num)
@S_FAST
def test_page_comment_marker_format(page):
    out = insert_page_number_comments("x", page)
    assert re.match(rf"^<!-- original page {page} -->\n", out)


# ═══════════════════════════════════════════════════════════════════════════
# 5. optimize_for_tokens
# ═══════════════════════════════════════════════════════════════════════════


@given(text=_any_text)
@S_FAST
def test_optimize_identity_when_disabled(text):
    assert optimize_for_tokens(text, token_saver=False) == text


@given(text=_any_text)
@S_FAST
def test_optimize_idempotent(text):
    once = optimize_for_tokens(text, token_saver=True)
    assert optimize_for_tokens(once, token_saver=True) == once


@given(text=_any_text)
@S_FAST
def test_optimize_leaves_no_trailing_blanks_or_deep_blank_runs(text):
    out = optimize_for_tokens(text, token_saver=True)
    for line in out.split("\n"):
        assert line == line.rstrip(" \t")
    assert "\n\n\n" not in out


@given(
    marker=st.sampled_from(["*", "+", "•"]),
    indent=st.sampled_from(["", "  ", "\t"]),
    item=st.sampled_from(["first point", "second point"]),
)
@S_FAST
def test_optimize_normalises_list_markers(marker, indent, item):
    out = optimize_for_tokens(f"{indent}{marker} {item}\n", token_saver=True)
    assert out.split("\n")[0].strip() == f"- {item}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. fix_missing_spaces — the never-fire contracts
# ═══════════════════════════════════════════════════════════════════════════


@given(text=_any_text)
@S_FAST
def test_fix_missing_spaces_identity_when_disabled(text):
    assert fix_missing_spaces(text, fix_spaces=False, wordninja_available=True) == text
    assert fix_missing_spaces(text, fix_spaces=True, wordninja_available=False) == text


@given(text=_persian_text)
@S_FAST
def test_fix_missing_spaces_identity_on_persian(text):
    # wordninja is English-only: Persian text must pass through untouched.
    assert fix_missing_spaces(text, fix_spaces=True, wordninja_available=True) == text
