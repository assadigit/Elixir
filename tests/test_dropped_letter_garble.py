"""V18.19.2.3 (Audit Fix 5): characterization tests for the dropped-letter
garbled-token detector.

The V18.19.2.0 audit found the model emitted "emergs" (should be "emerges" —
a dropped 'e' before 's'). The model noticed the typo in its own CoT
(`(Wait, use "emerges" not "emergs")`) but never corrected the output bullet.
The existing detectors missed it:
  - detect_garbled_tokens: looks for consonant clusters / impossible bigrams.
    "emergs" has vowels (e,e) and no impossible bigram.
  - detect_word_fragment_merge: looks for "word+stray space word" patterns.
    "emergs" is a single word, no space.

This new detector (``detect_dropped_letter_garble``) is SOURCE-GROUNDED:
for each word in the summary NOT in the source, check if a single-character
edit (insert/delete/substitute) makes it match a source word. If yes → flag.

Run: ``pytest tests/test_dropped_letter_garble.py -v``
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

from core.summarisation.postcheck_detectors import detect_dropped_letter_garble
from core.summarisation.postchecks import run_post_checks

# ═══════════════════════════════════════════════════════════════════════════
# 1. The exact V18.19.2.0 audit case: "emergs" → "emerges"
# ═══════════════════════════════════════════════════════════════════════════

class TestEmergsCase:
    """The exact garbled token from the V18.19.2.0 audit."""

    def test_emergs_flagged_as_dropped_letter(self):
        source = ("Self-constancy—a stable sense of unique personhood—emerges "
                  "at approximately two years, when the rapprochement subphase ends.")
        text = "The emergs of identity is a key concept in this chapter."
        _, issues = detect_dropped_letter_garble(text, "thorough", source)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) == 1
        assert "emergs" in dropped[0].detail
        assert "emerges" in dropped[0].detail

    def test_emergs_via_run_post_checks(self):
        """The full run_post_checks pipeline catches it too (wired in V18.19.2.3)."""
        source = ("Self-constancy emerges at approximately two years, when "
                  "the rapprochement subphase ends. Identity consolidation follows.")
        exec_text = "The emergs of identity is a key developmental milestone."
        pc = run_post_checks(bullets=[], executive_summary=exec_text,
                            thorough_summary="", source_text=source)
        dropped = [i for i in pc.issues if i.detector == "dropped_letter"]
        assert len(dropped) >= 1
        assert "emergs" in dropped[0].detail


# ═══════════════════════════════════════════════════════════════════════════
# 2. Other dropped-letter / substitution cases
# ═══════════════════════════════════════════════════════════════════════════

class TestOtherGarbleForms:
    @pytest.mark.parametrize("garbled,correct,source_fragment", [
        ("identiy", "identity", "identity formation is a lifelong process"),
        # ("Dukhaim" → "Durkheim" is edit-distance-3, NOT caught by this
        #  edit-distance-1 detector. That's validate_years's job. Removed.)
        ("pschoanalytic", "psychoanalytic", "the psychoanalytic literature on identity"),
        ("narcissstic", "narcissistic", "narcissistic personality structure"),
        # Single-char garbles (the "emergs" class — true non-words):
        # NOTE: "emerge"→"emerged" was removed in V18.19.2.5 — "emerge" is a real
        # English word (the base verb), and the tuning's _is_legitimate_inflection_pair
        # correctly suppresses it (emerge + "d" = emerged = past tense). Replaced
        # with "developmet"→"development" (a true garbled non-word).
        ("developmet", "development", "development is a key process"),
        ("pschology", "psychology", "psychology studies the mind"),
    ])
    def test_various_garble_forms_flagged(self, garbled, correct, source_fragment):
        text = f"The {garbled} concept appears here."
        _, issues = detect_dropped_letter_garble(text, "exec", source_fragment)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) >= 1, f"Should flag {garbled!r} (edit-distance-1 from {correct!r})"
        assert garbled in dropped[0].detail


# ═══════════════════════════════════════════════════════════════════════════
# 3. No false positives on legitimate content
# ═══════════════════════════════════════════════════════════════════════════

class TestNoFalsePositives:
    def test_source_words_not_flagged(self):
        """Words that ARE in the source must never be flagged."""
        source = "Self-constancy emerges at approximately two years when rapprochement ends."
        text = "Self-constancy emerges at approximately two years when rapprochement ends."
        _, issues = detect_dropped_letter_garble(text, "thorough", source)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) == 0

    def test_real_content_not_flagged(self):
        """Real summary sentences using source-grounded words must pass."""
        source = ("Tausk introduced the term identity in 1919. Erikson defined "
                  "ego identity as persistent sameness. Winnicott distinguished "
                  "true self from false self. Kernberg formulated a three-step "
                  "process of identity formation.")
        text = ("Tausk introduced the identity term. Erikson defined ego identity "
                "as persistent sameness. Winnicott distinguished true from false self.")
        _, issues = detect_dropped_letter_garble(text, "exec", source)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) == 0

    def test_short_words_not_flagged(self):
        """Words < 5 chars are exempt (too many false-positive neighbors)."""
        source = "The cat sat on the mat by the dog."
        text = "The ct sat on the mt by the dg."  # all garbled but < 5 chars
        _, issues = detect_dropped_letter_garble(text, "exec", source)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) == 0

    def test_structural_stopwords_not_flagged(self):
        """Function words (because, therefore, however) are exempt even if not in source."""
        source = "Identity forms in childhood."
        text = "Therefore, identity forms because childhood matters. However, this is key."
        _, issues = detect_dropped_letter_garble(text, "exec", source)
        dropped = [i for i in issues if i.detector == "dropped_letter"]
        assert len(dropped) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_text_no_crash(self):
        _, issues = detect_dropped_letter_garble("", "exec", "some source")
        assert issues == []

    def test_empty_source_no_crash(self):
        _, issues = detect_dropped_letter_garble("some text with emergs", "exec", "")
        assert issues == []

    def test_no_source_no_issues(self):
        """Without source_text, the detector returns no issues (can't validate)."""
        _, issues = detect_dropped_letter_garble("The emergs of identity", "exec", "")
        assert len(issues) == 0

    def test_unambiguous_garble_auto_repaired(self):
        """V18.20.3.4 (RC-3, audit v182033): when exactly ONE source word is
        at edit distance 1, the token is AUTO-REPAIRED (severity='fix') —
        the 'edipal'→'oedipal' class the V18.20.3.3 run shipped as a typo."""
        source = "Self-constancy emerges at approximately two years."
        text = "The emergs of identity is key."
        result, issues = detect_dropped_letter_garble(text, "exec", source)
        assert result == "The emerges of identity is key."
        assert any(
            i.severity == "fix" and "auto-repaired" in i.detail
            for i in issues
        )

    def test_ambiguous_garble_text_unchanged(self):
        """V18.20.3.4 (RC-3): with MULTIPLE edit-distance-1 candidates the
        reconstruction is ambiguous — the text stays unchanged and the
        issue stays flag-only (the human/LLM decides downstream)."""
        # "emergs" is distance-1 from BOTH "emerges" and "emerge".
        source = "It emerges and will emerge fully in time."
        text = "The emergs of identity is key."
        result, issues = detect_dropped_letter_garble(text, "exec", source)
        assert result == text
        assert any(
            i.severity == "flag" and "likely garbled" in i.detail
            for i in issues
        )


# ═══════════════════════════════════════════════════════════════════════════
# V18.19.2.5 (tune): the 16 false positives from the V18.19.2.4 audit must be
# suppressed by the new _is_legitimate_inflection_pair check.
# ═══════════════════════════════════════════════════════════════════════════

class TestV181925TuningSuppressesAuditFalsePositives:
    """The V18.19.2.4 audit found 16 false positives. V18.19.2.5 tuning must
    suppress them while keeping the true positives (emergs, identiy, etc.)."""

    # The 16 false positives from audit/results/audit_V18.19.2.4_2026-08-28.md
    # Format: (summary_word, source_word_that_triggered_the_FP)
    AUDIT_FALSE_POSITIVES = [
        ("attempts", "attempt"),       # plural
        ("author", "authors"),         # singular (source has plural)
        ("clarifies", "clarified"),    # verb conjugation (3rd-person vs past)
        ("consolidates", "consolidated"),  # verb conjugation
        ("depiction", "depictions"),   # singular
        ("describe", "described"),     # present vs past
        ("drawn", "draw"),             # past participle
        ("emerges", "emerge"),         # 3rd-person singular
        ("identifies", "identities"),  # coincidental (different stems — may stay flagged)
        ("opens", "open"),             # 3rd-person singular
        ("paths", "path"),             # plural
        ("seven", "seen"),             # coincidental (different words — may stay flagged)
        ("splits", "split"),           # 3rd-person singular
        ("surveys", "survey"),         # plural/3rd-person
        ("treat", "great"),            # coincidental (different words — may stay flagged)
        ("turns", "turn"),             # 3rd-person singular
    ]

    def test_at_least_13_of_16_audit_fps_suppressed(self):
        """V18.19.2.5 must suppress the morphological-inflection FPs (13 of 16).
        The 3 coincidental-different-word FPs (identifies/seven/treat) may remain
        flagged — they're flag-only, DEBUG-level, and acceptable residual noise."""
        suppressed = 0
        for summary_w, source_w in self.AUDIT_FALSE_POSITIVES:
            source = f"The {source_w} appears in the source text here."
            text = f"The {summary_w} appears in the summary text here."
            _, issues = detect_dropped_letter_garble(text, "exec", source)
            if not any(i.detector == "dropped_letter" for i in issues):
                suppressed += 1
        assert suppressed >= 13, (
            f"V18.19.2.5 tuning must suppress ≥13 of 16 audit FPs, got {suppressed}. "
            f"The 3 coincidental-different-word FPs (identifies/seven/treat) are acceptable."
        )

    def test_morphological_fps_all_suppressed(self):
        """All the morphological-inflection FPs (plural/verb-conjugation) must be
        suppressed. Only the 3 coincidental-different-word FPs may remain."""
        morphological_fps = [
            ("attempts", "attempt"), ("author", "authors"),
            ("clarifies", "clarified"), ("consolidates", "consolidated"),
            ("depiction", "depictions"), ("describe", "described"),
            ("drawn", "draw"), ("emerges", "emerge"),
            ("opens", "open"), ("paths", "path"),
            ("splits", "split"), ("surveys", "survey"), ("turns", "turn"),
        ]
        for summary_w, source_w in morphological_fps:
            source = f"The {source_w} appears in the source text here."
            text = f"The {summary_w} appears in the summary text here."
            _, issues = detect_dropped_letter_garble(text, "exec", source)
            dropped = [i for i in issues if i.detector == "dropped_letter"]
            assert len(dropped) == 0, (
                f"Morphological FP not suppressed: {summary_w!r} (source {source_w!r}) "
                f"— this is a legitimate English inflection, not a garbled token"
            )

    def test_true_positives_still_caught_after_tuning(self):
        """The tuning must NOT suppress true positives (actual garbled non-words)."""
        true_positives = [
            ("emergs", "emerges"),
            ("identiy", "identity"),
            ("pschoanalytic", "psychoanalytic"),
            ("narcissstic", "narcissistic"),
        ]
        for garbled, correct in true_positives:
            source = f"The {correct} concept is central and appears multiple times here."
            text = f"The {garbled} is key to understanding the topic."
            _, issues = detect_dropped_letter_garble(text, "thorough", source)
            dropped = [i for i in issues if i.detector == "dropped_letter"]
            assert len(dropped) >= 1, (
                f"True positive missed after tuning: {garbled!r} should be flagged "
                f"(it's a non-word, edit-distance-1 from {correct!r})"
            )
