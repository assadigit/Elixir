"""Phase 2 (Test-Net Deepening) — long-tail coverage for summary_validator.py.

Baseline: 280 stmts / 39 missed (86%). ``tests/test_summary_validator.py``
covers the main transforms; this file targets the missing branches:

  * ``normalize_empty_section`` — the short-hedge refusal line (<40 chars)
  * ``anti_false_precision_check`` — the empty-segment guard
  * ``semantic_dedup_bullets`` — the full embed path (fake embed model +
    numpy similarity matrix), the <2-bullets return, the numpy-ImportError
    skip, and the generic-exception skip
  * ``compute_coverage`` / ``_keyword_covered`` — empty keyword, the
    structural-stopwords ImportError fallback, the all-stopwords keyword,
    and the extract_all_concepts exception
  * ``verify_bullets`` — the rapidfuzz-ImportError early return and the
    >20-entry windows-cache eviction

Hermetic: ``get_embed_model`` / ``is_embedder_healthy`` are monkeypatched
(no localhost probe); numpy + rapidfuzz are really installed (their
ImportError branches are forced by blocking ``sys.modules`` — restored by
monkeypatch).

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_summary_validator.py -q --no-cov``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.summary_validator import (
    _keyword_covered,
    anti_false_precision_check,
    compute_coverage,
    normalize_empty_section,
    semantic_dedup_bullets,
    verify_bullets,
)


class _Log:
    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((msg, level))


# ── 1. normalize_empty_section — the short-hedge line ─────────────────────


class TestNormalizeEmptySectionShortHedge:
    def test_short_hedge_with_negation_word_emptied(self):
        """<40 chars containing a hedge word ('not ', 'no ', 'absent') → ''."""
        assert normalize_empty_section("not much to discuss") == ""
        assert normalize_empty_section("no data available") == ""
        assert normalize_empty_section("absent from this chapter") == ""

    def test_short_text_without_hedge_kept(self):
        assert normalize_empty_section("Ego development via identification.") == (
            "Ego development via identification."
        )

    def test_long_text_with_negation_word_kept(self):
        """≥40 chars → the hedge rule does not fire even with 'not '."""
        long_text = "This is not a refusal but a genuine distinction the chapter draws here."
        assert len(long_text) >= 40
        assert normalize_empty_section(long_text) == long_text.strip()


# ── 2. anti_false_precision_check — empty segment guard ───────────────────


class TestAntiFalsePrecisionEmptySegment:
    def test_empty_bullet_string_left_unchanged(self):
        result = {"bullet_points": ["", "AuthorA claims identity forms early."]}
        anti_false_precision_check("Ch", "source", result)
        assert result["bullet_points"][0] == ""

    def test_empty_summary_section_left_unchanged(self):
        result = {"executive_summary": "", "bullet_points": []}
        anti_false_precision_check("Ch", "source", result)
        assert result["executive_summary"] == ""


# ── 3. semantic_dedup_bullets — the embed path ────────────────────────────


def _fake_embed(monkeypatch, embeddings=None, raises=False):
    import core.llm.model_singletons as ms

    def _encode(texts, show_progress_bar=False, convert_to_numpy=True):
        if raises:
            raise RuntimeError("encode failed")
        import numpy as np

        return np.array(embeddings)

    model = type("FakeEmbedder", (), {"encode": staticmethod(_encode)})()
    monkeypatch.setattr(ms, "get_embed_model", lambda: model)
    monkeypatch.setattr(ms, "is_embedder_healthy", lambda: True)
    return model


class TestSemanticDedup:
    def test_fewer_than_two_real_bullets_returns_original(self):
        """One empty bullet filtered → bullet_strs < 2 → original returned."""
        out = semantic_dedup_bullets(["only one", ""], log=_Log())
        assert out == ["only one", ""]

    def test_identical_embeddings_merged(self, monkeypatch):
        """Two bullets with identical embeddings (sim 1.0 ≥ 0.92) → merged."""
        _fake_embed(monkeypatch, embeddings=[[1.0, 0.0], [1.0, 0.0]])
        log = _Log()
        out = semantic_dedup_bullets(["first bullet text", "first bullet text"], log=log)
        assert out == ["first bullet text"]
        assert any("removing bullet 2" in m for m, _ in log.calls)

    def test_orthogonal_embeddings_both_kept(self, monkeypatch):
        _fake_embed(monkeypatch, embeddings=[[1.0, 0.0], [0.0, 1.0]])
        out = semantic_dedup_bullets(["bullet one", "bullet two"])
        assert out == ["bullet one", "bullet two"]

    def test_custom_threshold(self, monkeypatch):
        """threshold=0.5 merges moderately-similar bullets (0.707 ≥ 0.5)."""
        _fake_embed(monkeypatch, embeddings=[[1.0, 0.0], [1.0, 1.0]])
        out = semantic_dedup_bullets(["bullet one", "bullet two"], threshold=0.5)
        assert out == ["bullet one"]

    def test_zero_norm_vectors_not_merged(self, monkeypatch):
        """Zero vectors → norms clamped to 1 → sim 0.0 → no merge (no NaN)."""
        _fake_embed(monkeypatch, embeddings=[[0.0, 0.0], [0.0, 0.0]])
        out = semantic_dedup_bullets(["bullet one", "bullet two"])
        assert out == ["bullet one", "bullet two"]

    def test_numpy_unavailable_skips_dedup(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "numpy", None)
        log = _Log()
        out = semantic_dedup_bullets(["a bullet", "a bullet"], log=log)
        assert out == ["a bullet", "a bullet"]
        assert any("numpy not available" in m for m, _ in log.calls)

    def test_encode_exception_skips_dedup(self, monkeypatch):
        _fake_embed(monkeypatch, raises=True)
        log = _Log()
        out = semantic_dedup_bullets(["a bullet", "a bullet"], log=log)
        assert out == ["a bullet", "a bullet"]
        assert any("error (encode failed)" in m for m, _ in log.calls)

    def test_embed_model_none_skips(self, monkeypatch):
        import core.llm.model_singletons as ms

        monkeypatch.setattr(ms, "get_embed_model", lambda: None)
        log = _Log()
        out = semantic_dedup_bullets(["a bullet", "a bullet"], log=log)
        assert out == ["a bullet", "a bullet"]
        assert any("not available" in m for m, _ in log.calls)

    def test_unhealthy_embedder_skips(self, monkeypatch):
        import core.llm.model_singletons as ms

        monkeypatch.setattr(ms, "get_embed_model", lambda: object())
        monkeypatch.setattr(ms, "is_embedder_healthy", lambda: False)
        log = _Log()
        out = semantic_dedup_bullets(["a bullet", "a bullet"], log=log)
        assert out == ["a bullet", "a bullet"]
        assert any("embedder unhealthy" in m for m, _ in log.calls)


# ── 4. compute_coverage / _keyword_covered ────────────────────────────────


class TestKeywordCoveredEdgeCases:
    def test_empty_keyword_counts_as_covered(self):
        assert _keyword_covered("", "any summary") is True

    def test_whitespace_keyword_counts_as_covered(self):
        assert _keyword_covered("   ", "any summary") is True

    def test_single_word_plural_tolerance(self):
        """'wheels' matches a summary that says 'wheel' (V0.03 plural rule)."""
        assert _keyword_covered("wheels", "the wheel turns daily") is True
        assert _keyword_covered("wheel", "the wheels turn daily") is True

    def test_hyphen_normalization(self):
        """'hamster-wheels' matches 'hamster wheels' in the summary."""
        assert _keyword_covered("hamster-wheels", "the hamster wheels spin") is True

    def test_multi_word_all_parts_required(self):
        """Multi-word keyword: every content part must be present."""
        assert _keyword_covered("identity formation", "identity through formation") is True
        assert _keyword_covered("identity formation", "identity alone here") is False

    def test_all_stopword_keyword_falls_back_to_parts(self):
        """A keyword whose ≥4-char parts are ALL structural function words →
        the content list is empty → falls back to the raw parts."""
        # "that which with" — every part is a structural function word
        assert _keyword_covered("that which with", "that which with") is True


class TestComputeCoverageEdgeCases:
    def _deps(self):
        return {}, lambda source, n: list(source.lower().split())[:n]

    def test_structural_stopwords_import_failure_uses_raw_parts(self, monkeypatch):
        """structural_stopwords import blocked → keyword matching still works
        on the raw parts (line 701-702 fallback)."""
        monkeypatch.setitem(sys.modules, "core.summarisation.structural_stopwords", None)
        cache, extract = self._deps()
        source = "identity formation shapes the developing psyche over time"
        summary = "identity and formation both appear in this summary text"
        score = compute_coverage(source, summary, cache, extract)
        assert score > 0

    def test_concept_extraction_failure_uses_keywords_only(self, monkeypatch):
        import core.summarisation.text_preprocessor as tp

        def _boom(text, max_terms=25):
            raise RuntimeError("concept extractor down")

        monkeypatch.setattr(tp, "extract_all_concepts", _boom)
        cache, extract = self._deps()
        source = "identity formation shapes the developing psyche over time"
        summary = "identity formation shapes the developing psyche over time"
        score = compute_coverage(source, summary, cache, extract)
        assert score == pytest.approx(1.0)
        # The cached tuple holds the keywords with an EMPTY concepts list
        cached = next(iter(cache.values()))
        assert cached[1] == []

    def test_cache_eviction_at_50_entries(self):
        """The coverage cache evicts the oldest entry beyond 50 sources."""
        cache, extract = self._deps()
        for i in range(52):
            compute_coverage(f"source text number {i} with words", f"summary {i}", cache, extract)
        assert len(cache) <= 50


# ── 5. verify_bullets ─────────────────────────────────────────────────────


class TestVerifyBulletsEdgeCases:
    def test_rapidfuzz_unavailable_returns_bullets_unchanged(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        bullets = ["a bullet", "another bullet"]
        out = verify_bullets(bullets, "source text " * 20, {}, log=_Log())
        assert out == bullets

    def test_windows_cache_evicts_beyond_20_sources(self):
        """The verify-windows cache keeps at most 20 source entries."""
        cache = {}
        quarantine = None
        for i in range(22):
            source = f"unique source text {i} " + "filler content here. " * 10
            verify_bullets(["a real bullet"], source, cache, quarantine, log=_Log())
        assert len(cache) <= 20

    def test_short_source_appended_whole(self):
        """A source shorter than the 80-char window: the range loop yields one
        full-source window AND the <=window_size branch appends it again."""
        cache = {}
        source = "Orexin regulates wakefulness."
        verify_bullets(["Orexin regulates wakefulness."], source, cache, log=_Log())
        windows = next(iter(cache.values()))
        # Both the range-loop window and the short-source append are the
        # whole (lowercased) source — the marker is stripped only for scoring.
        assert windows == [source.lower(), source.lower()]

    def test_verified_and_unverified_bullet_paths(self):
        """A verbatim bullet verifies; an unrelated bullet is kept but
        quarantined (conservative — V13.33.2 keeps it unmarked)."""
        cache = {}

        class _Q:
            def __init__(self):
                self.entries = []

            def add(self, **kw):
                self.entries.append(kw)

        q = _Q()
        log = _Log()
        source = "Orexin neurons in the lateral hypothalamus regulate wakefulness. " * 5
        out = verify_bullets(
            [
                "Orexin neurons in the lateral hypothalamus regulate wakefulness.",
                "Zephyr quantifiers recalibrate holographic tapestries.",
            ],
            source,
            cache,
            q,
            log=log,
        )
        assert out[0] == "Orexin neurons in the lateral hypothalamus regulate wakefulness."
        assert len(q.entries) == 1
        assert q.entries[0]["actually_dropped"] is False
        assert any("Fact-check: 1 verified, 1 unverified" in m for m, _ in log.calls)

    def test_citation_marker_stripped_for_scoring_only(self):
        """The '(p.NN)' marker is stripped only for the similarity scoring;
        the returned bullet keeps its original text (V13.33.2 — kept unmarked)."""
        cache = {}
        log = _Log()
        source = "The mirror stage was described by Jacques Lacan in 1936. " * 5
        bullet = "The mirror stage was described by Jacques Lacan in 1936. (p.31)"
        out = verify_bullets([bullet], source, cache, None, log=log)
        assert out == [bullet]  # original text preserved (citation included)
        assert any("all 1 bullets verified" in m for m, _ in log.calls)
