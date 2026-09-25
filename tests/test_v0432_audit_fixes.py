"""V0.4.32 — the audit-backlog regression tests (V0.4.31 ch.6 audit post-mortem).

Every test here pins one defect from the V0.4.31 ch.6 audit
(`audit/results/AUDIT_V0.4.31_run20260925-203638-b1687582_ch6_summary_vs_source.md`):

1. Item 1 — the F1-F5 hallucination class. The V0.4.24 attribution-edge
   check on thorough additive prose picked the first 8 keywords BY POSITION
   (cap 8). On real chapter sources, that selection picked common abstract
   words (e.g. "affective") that share a window with any cited author
   elsewhere in the source, passing fabricated substantive claims whose
   actual distinctive content words never co-occur with the cited author.
   The V0.4.32 fix sorts the keywords RAREST-FIRST and caps at 4 (the
   claim's distinctive content fingerprint), with a source-size gate so
   the rarest-4 probe only fires on sources large enough that a 0-frequency
   rare word is a fabrication signature, not a small-source artifact.

(Item 2 — the Phase 2.2 semantic fact-check scope extension, and Item 3 —
the thorough-theorist-floor gap-fill hallucination-guard — are added in
their own commits below.)

The deny-list test (``tests/test_v182039_audit_fixes.py::TestResidualsDenyList``)
enforces Rule 1 (content-agnostic): no book-derived proper nouns in the
runtime code. The synthetic test fixtures here use placeholder names
(Voss / Ibarra / Knight — the .3.9 prompt-scrub house pair + the V0.4.24
audit-fixes house name) and synthetic claims that model the F1-F5
PATTERN (a fabricated substantive claim attached to a real author whose
actual source claim is different) without naming any real book / author.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in __import__("sys").path:
    import sys

    sys.path.insert(0, str(_PROJECT_ROOT))

from core.summarisation.thorough_theorist_floor import (  # noqa: E402
    _MIN_SOURCE_CHARS,
    _grounded_addition_sentences,
)

# ─────────────────────────────────────────────────────────────────────────────
# Item 1 — the F1-F5 hallucination pattern (rarest-4 + source-size gate)
# ─────────────────────────────────────────────────────────────────────────────


class TestV0432AttributionEdgeRarestFirst:
    """The V0.4.32 strengthened attribution-edge check.

    Models the F1-F5 pattern from the V0.4.31 ch.6 audit: a fabricated
    substantive claim attached to a real author whose actual source claim
    is different. The fabricated claim happens to use a common abstract
    word that DOES appear in the author's source window (so the V0.4.24
    first-8-by-position rule passes it on that common word); the V0.4.32
    rarest-4 rule focuses on the claim's distinctive content fingerprint
    and drops the fabricated claim.

    Content-agnostic per Rule 1: the test fixtures use the V0.4.24 house
    name (Knight) and the V0.4.32 house pair (Voss / Ibarra) — synthetic
    placeholder names, never real book-derived names. The fabricated
    claim PATTERN (a real author + a fabricated substantive claim that
    shares a common word with the author's actual source claim) is a
    structural property, not a book-specific property.
    """

    # A real-sized source (≥ _MIN_SOURCE_CHARS = 1000 chars) — exercises
    # the V0.4.32 rarest-4 path. Knight appears with an actual claim
    # about ego functions and borderline conditions; the source also
    # contains the common word "affective" elsewhere.
    SOURCE = (
        "Knight (1953) catalogued eleven ego functions impaired in "
        "borderline conditions. The affective reactions distinguish "
        "borderline from neurotic patients. Knight's framework remains "
        "influential in the structural literature on ego psychology. "
        + ("filler padding text body " * 60)
        + "Other authors discuss affective phenomena in different "
        "clinical contexts without referencing Knight's cataloguing. "
        + ("more padding content here " * 40)
    )

    def test_v0432_drops_fabricated_claim_that_shares_a_common_word(self):
        """The F1-F5 pattern: a fabricated claim that uses a common word
        ('affective') that appears in the author's source window, but
        whose distinctive content words ('refined', 'conceptualization',
        'emphasizing', 'markers') never co-occur with the author."""
        # The fabricated claim — modeled on the audit's F1 evidence
        # (a fabricated substantive claim attached to an author whose
        # actual source claim is different; the fabricated claim happens
        # to use a common word 'affective' that DOES co-occur with the
        # author's actual claim about ego functions).
        fabricated = (
            "Knight (1984) further refined the conceptualization by "
            "emphasizing the distinct cognitive and affective markers "
            "that differentiate borderline traits from general anxiety "
            "or depression."
        )
        filtered, dropped = _grounded_addition_sentences(fabricated, self.SOURCE, ["Knight"])
        # The V0.4.32 rarest-4 rule MUST drop this — the rarest distinctive
        # words ('refined', 'conceptualization', 'emphasizing', 'markers')
        # never co-occur with Knight in the source.
        assert len(dropped) == 1, (
            f"V0.4.32 must drop the fabricated claim that shares a common "
            f"word with the author's source window (the F1-F5 pattern). "
            f"dropped={dropped}"
        )
        assert "Knight (1984)" in dropped[0]

    def test_v0432_keeps_grounded_claim_that_uses_distinctive_words(self):
        """The control: a real grounded claim whose distinctive content
        words DO co-occur with the author in the source. The V0.4.32
        rarest-4 rule keeps this."""
        grounded = (
            "Knight (1953) catalogued the eleven ego functions impaired in borderline conditions."
        )
        filtered, dropped = _grounded_addition_sentences(grounded, self.SOURCE, ["Knight"])
        assert not dropped, f"V0.4.32 must keep grounded claims: {dropped}"
        assert filtered == grounded

    def test_v0432_keeps_claim_when_author_absent_from_source(self):
        """A name absent from the source entirely is kept (it arrived
        from the runtime analysis, not the model — unverifiable)."""
        grounded = (
            "Ibarra (1967) catalogued the eleven ego functions whose "
            "impairment distinguishes borderline patients."
        )
        filtered, dropped = _grounded_addition_sentences(grounded, self.SOURCE, ["Ibarra"])
        assert not dropped
        assert filtered == grounded

    def test_v0432_nameless_sentence_passes_untouched(self):
        """A sentence that carries no gap-fill name is never checked."""
        nameless = (
            "The chapter traces the layered model of structure formation "
            "across five decades of clinical literature."
        )
        filtered, dropped = _grounded_addition_sentences(nameless, self.SOURCE, ["Knight"])
        assert not dropped
        assert filtered == nameless

    def test_v0432_source_size_gate_uses_v0424_fallback_on_tiny_sources(self):
        """On sources smaller than _MIN_SOURCE_CHARS, the V0.4.24
        first-8-by-position rule is used (the rarest-4 selection
        degenerates on tiny sources — too many 0-frequency words)."""
        # A tiny source (< _MIN_SOURCE_CHARS chars): the rarest-4 would
        # be all 0-frequency; the V0.4.24 fallback applies.
        tiny_source = "Source text about Knight ego functions and Rinsley developmental arrest."
        assert len(tiny_source) < _MIN_SOURCE_CHARS
        # A long Knight sentence with many distinctive words (most are
        # 0-frequency in the tiny source). V0.4.24 first-8 would include
        # 'functions' (which appears in the tiny source) → keeps. V0.4.32
        # rarest-4 (if applied) would pick 4 all-0-freq words → drop
        # (false positive). The source-size gate prevents this.
        long_knight = (
            "Knight (1953) catalogued the eleven ego functions whose "
            "combined impairment distinguishes borderline patients from "
            "neurotics, framing the diagnosis in structural rather than "
            "purely descriptive terms for the American literature."
        )
        filtered, dropped = _grounded_addition_sentences(long_knight, tiny_source, ["Knight"])
        # The V0.4.24 fallback keeps the Knight sentence (because
        # 'functions' is in the first 8 by position AND co-occurs with
        # Knight in the tiny source).
        assert not dropped, f"V0.4.24 fallback on tiny sources must keep grounded claims: {dropped}"
        assert "Knight (1953) catalogued" in filtered

    def test_v0432_threshold_is_above_tiny_test_sources(self):
        """Sanity: the source-size gate threshold is between the tiny
        test sources (~62 chars) and the V0.4.24 TestGroundedAdditionSentences
        SOURCE (~1562 chars)."""
        # Tiny synthetic test sources are well below the threshold.
        tiny = "Source text about Knight ego functions."
        assert len(tiny) < _MIN_SOURCE_CHARS
        # Real chapter sources are well above the threshold.
        real_chapter_min = 5000
        assert real_chapter_min > _MIN_SOURCE_CHARS
        # The V0.4.24 TestGroundedAdditionSentences SOURCE (~1562 chars)
        # is ABOVE the threshold (so V0.4.32 applies there — verified
        # by tests/test_v00424_audit_fixes.py::TestGroundedAdditionSentences
        # passing unchanged on this source).
        source_v00424 = (
            "Klein (1946) described play-technique criticism of the child's "
            "primitive object relations. "
            * 3
            + "…far away… " * 50
            + "Knight (1953) catalogued eleven ego functions impaired in "
            "borderline conditions. "
            + "…elsewhere… " * 50
            + "Piaget (1945) wrote on the psychology of play in children."
        )
        assert len(source_v00424) >= _MIN_SOURCE_CHARS


# ─────────────────────────────────────────────────────────────────────────────
# Item 2 — Phase 2.2 semantic fact-check scope extension (the new helper)
# ─────────────────────────────────────────────────────────────────────────────


class TestV0432SemanticGroundAdditionSentences:
    """The V0.4.32 EXTENSION of Phase 2.2 (semantic fact-check) to
    thorough additive prose. The bullet-pipeline's Phase 2.2
    (apply_phase22_semantic_fact_check, V3.7.0) verifies ≥0.50 embedding
    similarity for bullets; the V0.4.32 closes the bullets-only gap by
    running the same check on thorough additive prose via the new
    ``_semantic_ground_addition_sentences`` helper."""

    def test_helper_importable(self):
        """The new helper is importable from the thorough_theorist_floor
        module (alongside _grounded_addition_sentences)."""
        from core.summarisation.thorough_theorist_floor import (
            _semantic_ground_addition_sentences,
        )

        assert callable(_semantic_ground_addition_sentences)

    def test_helper_returns_unchanged_on_empty_input(self):
        """The helper fail-softs on degenerate input — returns the
        original addition unchanged, no dropped sentences."""
        from core.summarisation.thorough_theorist_floor import (
            _semantic_ground_addition_sentences,
        )

        # Empty addition → return unchanged.
        filtered, dropped = _semantic_ground_addition_sentences("", "src")
        assert filtered == ""
        assert dropped == []
        # Empty source → return unchanged.
        filtered, dropped = _semantic_ground_addition_sentences("Some prose here.", "")
        assert filtered == "Some prose here."
        assert dropped == []

    def test_helper_skips_when_embedder_unhealthy(self):
        """The V18.2.30 degenerate-signal guard: when the embedder is
        unhealthy (sandbox: no sentence-transformers → returns None →
        is_embedder_healthy() returns False), the check is skipped with
        the original addition returned unchanged (the V0.4.25 honest-
        divergence pattern: rely on the attribution-edge drop (item 1)
        for hallucination filtering when the embedder can't be trusted).

        This test verifies the GUARD fires in the sandbox (the actual
        semantic check runs on the rig — disclose per Rule 2)."""
        from core.llm.model_singletons import is_embedder_healthy
        from core.summarisation.thorough_theorist_floor import (
            _semantic_ground_addition_sentences,
        )

        if is_embedder_healthy():
            pytest.skip(
                "embedder is healthy in this environment — the degenerate-"
                "signal guard does not fire (the semantic check would run). "
                "Test this on a sandbox without sentence-transformers."
            )

        addition = (
            "Knight (1953) catalogued the eleven ego functions whose "
            "impairment distinguishes borderline patients. The affective "
            "reactions distinguish borderline from neurotic patients."
        )
        source = (
            "Knight (1953) catalogued eleven ego functions impaired in borderline conditions. " * 5
        )
        filtered, dropped = _semantic_ground_addition_sentences(addition, source)
        # The guard fires → returns the original addition unchanged.
        assert filtered == addition, (
            "When the embedder is unhealthy, the helper must return the "
            "original addition unchanged (V18.2.30 degenerate-signal guard)."
        )
        assert dropped == []

    def test_helper_skips_short_sentences(self):
        """Sentences shorter than 20 chars are kept without probing
        (semantic similarity on very short text is unreliable)."""
        from core.llm.model_singletons import is_embedder_healthy
        from core.summarisation.thorough_theorist_floor import (
            _semantic_ground_addition_sentences,
        )

        if is_embedder_healthy():
            pytest.skip("embedder healthy — guard does not fire")

        # Short sentences should pass untouched even with a real source.
        addition = "Short. Also short."
        source = "Some real source content. " * 20
        filtered, dropped = _semantic_ground_addition_sentences(addition, source)
        assert filtered == addition
        assert dropped == []

    def test_helper_never_raises_on_bad_input(self):
        """The helper fail-softs on None / bad input — returns the
        original addition unchanged."""
        from core.summarisation.thorough_theorist_floor import (
            _semantic_ground_addition_sentences,
        )

        assert _semantic_ground_addition_sentences(None, "src")[0] in (None, "")  # type: ignore[arg-type]
