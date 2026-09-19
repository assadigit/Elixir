"""Property-based tests: postcheck-detector robustness (roadmap 2.2).

Targets ``core/summarisation/postcheck_detectors.py`` (Phase 2, task 2.2 of
docs/ROADMAP_V0.12.md — "Hypothesis property suites").

Invariants under test (characterization of the ACTUAL contract):

1. **Never crash on arbitrary unicode.** Every public detector accepts any
   string — mixed scripts, RTL, control characters, emoji, zero-width
   joiners, very long lines, degenerate markdown — and returns a
   ``(str, list[Issue])`` tuple without raising. The detectors sit on the
   hot path of every summarization; an exception there would kill the whole
   conversion, so "swallow and report" is the contract (the module wraps
   each body in try/except).
2. **Issue shape.** Whatever comes back is well-formed: severity is one of
   the known values, the detector tag is non-empty, and the field label is
   propagated.
3. **Fire on known-bad, silent on clean.** For the detectors with a crisp
   contractual trigger, a constructed bad sample MUST produce ≥1 issue and
   clean prose MUST produce zero issues (and, for rewrite-style detectors,
   leave the text byte-identical).

Determinism: no network, no LLM, no filesystem writes; all strategies are
pure.  Hypothesis settings are tuned per test (``deadline=None``) for the
<60 s whole-suite budget.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from core.summarisation.postcheck_detectors import (
    Issue,
    detect_cot_narrative,
    detect_extra_spaces,
    detect_garbled_tokens,
    detect_grammatical_incoherence,
    detect_missing_spaces,
    detect_prompt_leakage,
    validate_years,
)

# ── settings profiles (tuned for the <60s whole-suite budget) ───────────────
S_FAST = settings(max_examples=40, deadline=None)
_SLOW_DET = settings(max_examples=25, deadline=None)

# ═══════════════════════════════════════════════════════════════════════════
# Nasty-unicode generators
# ═══════════════════════════════════════════════════════════════════════════

_CONTROL = "".join(chr(c) for c in range(1, 32) if c not in (9, 10, 13))
_ZEROWIDTH = "\u200b\u200c\u200d\ufeff"
_EMOJI = "🔥🎉🤖🧠📈✅❌→←↔"
_RTL = "سلام دنیا این یک متن فارسی است"
_LTR = "The quick brown fox jumps over the lazy dog"
_SCRIPTS = "Ελληνικά кириллица héllo こんにちは 안녕하세요 שלום"
_MARKDOWN_DEGENERATE = "**__~~`` #### Heading - - - item [[unclosed( |table|drop"

_NASTY_CHARPOOL = _CONTROL + _ZEROWIDTH + _EMOJI + _RTL + _LTR + _SCRIPTS + _MARKDOWN_DEGENERATE

_nasty_text = st.text(
    alphabet=_NASTY_CHARPOOL,
    min_size=0,
    max_size=400,
)

_nasty_text_long = st.text(
    alphabet=_NASTY_CHARPOOL + "a" * 40,
    min_size=200,
    max_size=4000,
)

_field_labels = st.sampled_from(["exec", "thorough", "bullet1", "bullet[12]", ""])


# ═══════════════════════════════════════════════════════════════════════════
# 1. Never crash on arbitrary unicode
# ═══════════════════════════════════════════════════════════════════════════


def _assert_wellformed(result: tuple, field_label: str) -> None:
    assert isinstance(result, tuple) and len(result) == 2
    text, issues = result
    assert isinstance(text, str)
    assert isinstance(issues, list)
    for issue in issues:
        assert isinstance(issue, Issue)
        assert issue.severity in ("fix", "flag")
        assert issue.detector
        assert field_label in issue.field


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_prompt_leakage_never_crashes(text, field_label):
    _assert_wellformed(detect_prompt_leakage(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_cot_narrative_never_crashes(text, field_label):
    _assert_wellformed(detect_cot_narrative(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_garbled_tokens_never_crashes(text, field_label):
    _assert_wellformed(detect_garbled_tokens(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_grammatical_incoherence_never_crashes(text, field_label):
    _assert_wellformed(detect_grammatical_incoherence(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_validate_years_never_crashes(text, field_label):
    _assert_wellformed(validate_years(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels, source=_nasty_text)
@_SLOW_DET
def test_missing_spaces_never_crashes(text, field_label, source):
    _assert_wellformed(detect_missing_spaces(text, field_label, source_text=source), field_label)


@given(text=_nasty_text, field_label=_field_labels, source=_nasty_text)
@_SLOW_DET
def test_extra_spaces_never_crashes(text, field_label, source):
    _assert_wellformed(detect_extra_spaces(text, field_label, source_text=source), field_label)


@given(text=_nasty_text_long, field_label=_field_labels)
@_SLOW_DET
def test_detectors_never_crash_on_long_lines(text, field_label):
    # 4,000-char degenerate single-ish blob: the hot-path worst case.
    _assert_wellformed(detect_prompt_leakage(text, field_label), field_label)
    _assert_wellformed(detect_garbled_tokens(text, field_label), field_label)
    _assert_wellformed(detect_grammatical_incoherence(text, field_label), field_label)


@given(text=_nasty_text, field_label=_field_labels)
@S_FAST
def test_cleaned_text_is_always_str_and_bounded_shrink(text, field_label):
    # Rewrite detectors may only SHRINK or keep the text (they strip
    # leakage/CoT), never grow it beyond the original.
    cleaned, _ = detect_prompt_leakage(text, field_label)
    assert len(cleaned) <= len(text)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Fire on known-bad
# ═══════════════════════════════════════════════════════════════════════════


@given(
    leak=st.sampled_from(
        [
            "Here is the summary of the chapter.",
            "Now I will write the bullets.",
            "As an AI language model, I cannot.",
            "The user wants a short version.",
            "The instructions say to use five bullets.",
        ]
    ),
    before=st.text(alphabet="abcdefghijklmnopqrstuvwxyz. ", min_size=0, max_size=20),
    after=st.text(alphabet="abcdefghijklmnopqrstuvwxyz. ", min_size=0, max_size=20),
)
@S_FAST
def test_prompt_leakage_fires_on_known_leak(before, leak, after):
    # Spaces around the leak phrase keep the \b word boundaries intact
    # (a directly-concatenated "xyzHere" would NOT match — by design).
    text = f"{before} {leak} {after}"
    cleaned, issues = detect_prompt_leakage(text, "exec")
    assert issues, f"expected a prompt-leakage issue for {leak!r}"
    assert leak.lower() not in cleaned.lower()


@given(
    n_cot=st.integers(min_value=3, max_value=6),
    filler=st.text(alphabet="abcdefghijklmnopqrstuvwxyz. ", min_size=0, max_size=30),
)
@S_FAST
def test_cot_narrative_fires_on_cot_scaffolding(n_cot, filler):
    markers = [
        "Let me organize my understanding.",
        "Wait, let me re-read.",
        "Now write the answer.",
    ]
    text = filler + " " + " ".join(markers[:n_cot]) + " " + filler
    _, issues = detect_cot_narrative(text, "thorough")
    assert issues


@given(
    word=st.sampled_from(["xkqqzz", "bxxcvvv", "qwzxcvbnm"]),
    sentence=st.sampled_from(
        [
            "The argument rests on ",
            "Evidence for the claim comes from ",
            "The framework describes ",
        ]
    ),
)
@S_FAST
def test_garbled_tokens_fires_on_impossible_bigrams(sentence, word):
    _, issues = detect_garbled_tokens(f"{sentence}{word}.", "bullet1")
    assert issues


@given(
    year=st.one_of(
        st.integers(min_value=1000, max_value=1799), st.integers(min_value=2028, max_value=2199)
    )
)
@S_FAST
def test_validate_years_fires_on_implausible_years(year):
    # Only years the _BARE_YEAR_RE can SEE (1\d{3} | 20\d{2} | 21\d{2})
    # but that fall outside [1800, MAX_YEAR] are flagged — e.g. 9999 is
    # invisible to the regex and correctly ignored (characterization).
    _, issues = validate_years(f"The study was published in {year}.", "bullet2")
    assert issues


@given(
    clean=st.sampled_from(
        [
            "The author argues that identity formation occurs during adolescence.",
            "Three studies examine the crisis of identity in modern societies.",
            "The chapter concludes with a discussion of theoretical tensions.",
        ]
    )
)
@S_FAST
def test_garbled_tokens_silent_on_clean_prose(clean):
    text, issues = detect_garbled_tokens(clean, "exec")
    assert not issues
    assert text == clean


@given(
    clean=st.sampled_from(
        [
            "The author argues that identity formation occurs during adolescence.",
            "Five studies published between 1990 and 2010 examine the question.",
        ]
    )
)
@S_FAST
def test_validate_years_silent_on_clean_prose(clean):
    text, issues = validate_years(clean, "exec")
    assert not issues
    assert text == clean
