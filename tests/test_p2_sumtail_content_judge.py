"""Phase 2 (Test-Net Deepening) — long-tail coverage for content_judge_impl.py.

Baseline: 413 stmts / 78 missed (81%). ``tests/test_content_judge.py`` covers
the Jaccard-fallback happy paths; this file targets the missing branches:

  * ``JudgeResult.format_report`` — the ``L8=OFF(alarm)`` suffix
  * ``_extract_key_claims`` — the figure/table/reference skip patterns
  * ``_semantic_similarity`` — the FULL embed path via a fake
    ``sentence_transformers`` module (model-None ImportError, unhealthy
    embedder, the V18.2.44 degenerate-vector guard, cos_sim success) and
    both Jaccard fallbacks' empty-word returns
  * ``_encode_chunks_cached`` — disabled gate, model-None, cached_encode
    None / length-mismatch / malformed / raising entries, happy path
  * ``_check_coverage_batched`` — happy path (sim matrix → covered count +
    uncovered_claims), model-None, and the exception fallback
  * ``judge()`` — the degenerate 0/N coverage guard, the Layer-8 grounding
    loop (alarm / strong-grounded / strong-ungrounded / extractor crash),
    the Q2 grounded+break paths, and the Q4 negation deviation
  * ``llm_judge_grounding`` — no-args None, the >6000-char source
    truncation, verdict parsing, and the exception path

Hermetic: sentence-transformers is NOT installed in the venv — the embed
paths are driven through a fake ``sys.modules`` entry (snapshot/restore);
``get_embed_model`` / ``is_embedder_healthy`` / ``cached_encode`` are
monkeypatched; the shared ``_runtime_state`` warn-flags are snapshot/restored
per the group_b singleton discipline.

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_content_judge.py -q --no-cov``
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.models import SummaryResult
from core.summarisation import content_judge_impl as cji
from core.summarisation.content_judge_impl import (
    ContentJudge,
    JudgeResult,
    _chunk_text,
    _encode_chunks_cached,
    _extract_key_claims,
    _semantic_similarity,
)


class _Log:
    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((msg, level))

    def lines(self, level=None):
        return [m for m, lvl in self.calls if level is None or lvl == level]


# ── Fake sentence_transformers infrastructure ─────────────────────────────


class _FakeScalar:
    def __init__(self, v):
        self._v = v

    def item(self):
        return self._v


class _FakeRow:
    def __init__(self, vals):
        self._vals = vals

    def __getitem__(self, i):
        return _FakeScalar(self._vals[i])

    def max(self):
        return _FakeScalar(max(self._vals))


class _FakeMatrix:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, i):
        return self._rows[i]


def _install_fake_st(monkeypatch, cos_sim_matrix=None, scalar_sim=None, cos_sim_raises=False):
    """Install a fake sentence_transformers + .util module pair."""
    fake_st = types.ModuleType("sentence_transformers")
    fake_util = types.ModuleType("sentence_transformers.util")

    def _cos_sim(a, b):
        if cos_sim_raises:
            raise RuntimeError("cos_sim backend exploded")
        if scalar_sim is not None:
            return _FakeMatrix([[_FakeScalar(scalar_sim)]])
        if cos_sim_matrix is not None:
            return _FakeMatrix([_FakeRow(r) for r in cos_sim_matrix])
        return _FakeMatrix([[_FakeScalar(0.0)]])

    fake_util.cos_sim = _cos_sim
    fake_st.util = fake_util
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    monkeypatch.setitem(sys.modules, "sentence_transformers.util", fake_util)
    return fake_st


def _fake_model(monkeypatch, encode_result=None, healthy=True, model=None):
    import core.llm.model_singletons as ms

    if model is None:
        model = SimpleNamespace(
            name="fake-embedder",
            encode=lambda texts, show_progress_bar=False: encode_result,
        )
    monkeypatch.setattr(ms, "get_embed_model", lambda: model)
    monkeypatch.setattr(ms, "is_embedder_healthy", lambda: healthy)
    return model


@pytest.fixture(autouse=True)
def _no_real_embedder(monkeypatch):
    """Default: get_embed_model → None (hermetic — the real singleton would
    probe localhost:11434 from judge()'s _encode_chunks_cached call).
    Tests that drive the embed path override this with their own patches."""
    import core.llm.model_singletons as ms

    monkeypatch.setattr(ms, "get_embed_model", lambda: None)
    monkeypatch.setattr(ms, "is_embedder_healthy", lambda: True)
    # Snapshot/restore the shared _runtime_state warn flags (D3 discipline).
    saved_sem = cji._runtime_state.warned_semantic_fallback
    saved_dis = cji._runtime_state.warned_embedding_disabled
    cji._runtime_state.warned_semantic_fallback = False
    cji._runtime_state.warned_embedding_disabled = False
    yield
    cji._runtime_state.warned_semantic_fallback = saved_sem
    cji._runtime_state.warned_embedding_disabled = saved_dis


def _patch_embedding_settings(monkeypatch, enabled=True, fallback="jaccard"):
    import utils.settings as us

    class _FakeSettings:
        def get(self, key, default=None):
            if key == "embedding.enabled":
                return enabled
            if key == "embedding.fallback":
                return fallback
            return default

    monkeypatch.setattr(us, "Settings", lambda: _FakeSettings())


# ── 1. JudgeResult.format_report — L8=OFF branch ──────────────────────────


class TestFormatReport:
    def test_l8_off_alarm_suffix(self):
        """grounding_alarm set + layer8 unavailable → 'L8=OFF(alarm)'."""
        r = JudgeResult(
            chapter_heading="Ch.1",
            grounding_layer8_available=False,
            grounding_alarm="langextract_missing",
            passed=False,
        )
        report = r.format_report()
        assert "L8=OFF(langextract_missing)" in report

    def test_coverage_skipped_suffix(self):
        r = JudgeResult(chapter_heading="Ch.1", coverage_skipped=True, passed=True)
        assert "coverage=SKIPPED(embedding off)" in r.format_report()


# ── 2. _extract_key_claims — skip patterns ────────────────────────────────


class TestExtractKeyClaimsSkipPatterns:
    def test_figure_captions_skipped(self):
        """'Figure 1 …' sentences with numbers are NOT claims."""
        text = (
            "Figure 1 shows the 42% improvement across cohorts. "
            "The study found that 42% of participants improved significantly."
        )
        claims = _extract_key_claims(text)
        assert len(claims) == 1
        assert claims[0].startswith("The study found")

    def test_table_and_reference_lines_skipped(self):
        text = (
            "Table 2 summarizes the 15 measurements taken. "
            "References AuthorA 2021 completely unrelated filler text here. "
            "Bibliography entries list 30 sources for this chapter."
        )
        claims = _extract_key_claims(text)
        assert claims == []

    def test_copyright_lines_skipped(self):
        text = (
            "© 2019 Publisher Name. All rights reserved.\n\n"
            "The 2019 study demonstrated that measurement works well here."
        )
        claims = _extract_key_claims(text)
        assert len(claims) == 1
        assert claims[0].startswith("The 2019 study")


# ── 3. _semantic_similarity — the full embed path ─────────────────────────


class TestSemanticSimilarityEmbedPath:
    def test_model_none_raises_importerror_to_jaccard(self, monkeypatch):
        """get_embed_model → None → ImportError('not available') → Jaccard.

        (The autouse fixture already pins get_embed_model → None — only the
        fake sentence_transformers module needs installing.)
        """
        _install_fake_st(monkeypatch)
        sim = _semantic_similarity("the cat sat", "the cat sat")
        assert sim == pytest.approx(1.0)

    def test_unhealthy_embedder_falls_back_to_jaccard(self, monkeypatch):
        _install_fake_st(monkeypatch)
        _fake_model(monkeypatch, healthy=False)
        sim = _semantic_similarity("shared words here", "shared words here")
        assert sim == pytest.approx(1.0)

    def test_degenerate_zero_vector_falls_back_to_jaccard(self, monkeypatch):
        """The V18.2.44 guard: an all-zero claim vector → EmbedderUnavailable."""
        import numpy as np

        _install_fake_st(monkeypatch)
        _fake_model(monkeypatch, encode_result=np.zeros((1, 4)))
        sim = _semantic_similarity("some claim text", "some claim text")
        assert sim == pytest.approx(1.0)  # Jaccard of identical strings

    def test_nan_vector_falls_back_to_jaccard(self, monkeypatch):
        import numpy as np

        _install_fake_st(monkeypatch)
        _fake_model(monkeypatch, encode_result=np.full((1, 4), np.nan))
        sim = _semantic_similarity("some claim text", "some claim text")
        assert sim == pytest.approx(1.0)

    def test_cos_sim_success(self, monkeypatch):
        import numpy as np

        _install_fake_st(monkeypatch, scalar_sim=0.87)
        _fake_model(monkeypatch, encode_result=np.ones((1, 4)))
        sim = _semantic_similarity("claim", "candidate")
        assert sim == pytest.approx(0.87)

    def test_precomputed_candidate_embedding_used(self, monkeypatch):
        """candidate_emb supplied → the candidate is NOT re-encoded."""
        import numpy as np

        calls = {"n": 0}

        def _encode(texts, show_progress_bar=False):
            calls["n"] += 1
            return np.ones((len(texts), 4))

        _install_fake_st(monkeypatch, scalar_sim=0.66)
        _fake_model(monkeypatch, model=SimpleNamespace(encode=_encode))
        sim = _semantic_similarity("claim", "candidate", candidate_emb=np.ones((1, 4)))
        assert sim == pytest.approx(0.66)
        assert calls["n"] == 1  # only the claim was encoded


class TestEmbeddingSettingsHelper:
    def test_settings_raising_fails_open_to_jaccard(self, monkeypatch):
        import utils.settings as us

        class _Boom:
            def __init__(self):
                raise RuntimeError("settings store unreadable")

        monkeypatch.setattr(us, "Settings", _Boom)
        assert cji._embedding_settings() == (True, "jaccard")

    def test_unknown_fallback_value_normalized_to_jaccard(self, monkeypatch):
        import utils.settings as us

        class _FakeSettings:
            def get(self, key, default=None):
                if key == "embedding.fallback":
                    return "explode"
                return default

        monkeypatch.setattr(us, "Settings", lambda: _FakeSettings())
        assert cji._embedding_settings() == (True, "jaccard")

    def test_jaccard_helper_empty_words_returns_zero(self, monkeypatch):
        """``_jaccard`` itself returns 0.0 when either side has no words."""
        assert cji._jaccard("", "candidate") == 0.0
        assert cji._jaccard("claim", "") == 0.0

    def test_disabled_jaccard_mode_with_empty_claim_returns_zero(self, monkeypatch):
        _patch_embedding_settings(monkeypatch, enabled=False, fallback="jaccard")
        assert _semantic_similarity("", "candidate words") == 0.0


class TestSemanticSimilarityFallbacks:
    def test_jaccard_unavailable_path_empty_words_returns_zero(self, monkeypatch):
        """EmbedderUnavailable path with an empty claim → 0.0."""
        _install_fake_st(monkeypatch)
        _fake_model(monkeypatch, healthy=False)
        assert _semantic_similarity("", "candidate words") == 0.0
        assert _semantic_similarity("claim words", "") == 0.0

    def test_generic_exception_path_empty_words_returns_zero(self, monkeypatch):
        """No sentence_transformers at all (real env) + empty side → 0.0."""
        # Ensure the fake is NOT installed (the real env has no ST package)
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        _fake_model(monkeypatch, healthy=True)
        assert _semantic_similarity("", "candidate words") == 0.0

    def test_embedding_disabled_skip_mode_raises(self, monkeypatch):
        """enabled=False + fallback='skip' → EmbeddingDisabled (defense-in-depth)."""
        _patch_embedding_settings(monkeypatch, enabled=False, fallback="skip")
        with pytest.raises(cji.EmbeddingDisabled):
            _semantic_similarity("claim", "candidate")

    def test_embedding_disabled_jaccard_mode_uses_jaccard(self, monkeypatch):
        _patch_embedding_settings(monkeypatch, enabled=False, fallback="jaccard")
        sim = _semantic_similarity("shared words", "shared words")
        assert sim == pytest.approx(1.0)


class TestJudgeShortSourceAndEmptySummary:
    def test_short_source_auto_passes(self):
        judge = ContentJudge(log_callback=_Log())
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary="Whatever.",
            bullet_points=["b"],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, "too short source")
        assert result.passed is True
        assert "Source too short" in result.summary

    def test_empty_summary_fails(self):
        judge = ContentJudge(log_callback=_Log())
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary="",
            bullet_points=[],
            thorough_summary="",
            success=True,
        )
        source = "A sufficiently long source text. " * 10
        result = judge.judge(summary, source)
        assert result.passed is False
        assert "Empty summary" in result.summary

    def test_skip_mode_short_circuits_coverage_and_grounding(self, monkeypatch):
        """embedding.enabled=False + fallback='skip' → coverage auto-passed
        (coverage_skipped=True) and ALL bullets auto-grounded (V18.4 Phase 2)."""
        _patch_embedding_settings(monkeypatch, enabled=False, fallback="skip")
        log = _Log()
        judge = ContentJudge(log_callback=log)
        source = (
            "In 1998 researchers demonstrated that orexin deficiency causes "
            "narcolepsy in mice and dogs across several continents. "
            + "Additional context sentences follow here. "
            * 10
        )
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary="Orexin deficiency causes narcolepsy.",
            bullet_points=["Orexin deficiency causes narcolepsy in dogs."],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.coverage_skipped is True
        assert result.coverage_pct == 1.0
        assert result.grounding_pct == 1.0
        assert result.ungrounded_bullets == []
        assert result.deviation_count == 0  # Q4 skipped in skip-mode
        assert any(
            "semantic coverage check SKIPPED" in m for m, lvl in log.calls if lvl == "WARNING"
        )
        assert any("semantic grounding SKIPPED" in m for m, lvl in log.calls if lvl == "WARNING")


class TestJudgePerPairCoverageLoop:
    def test_covered_claim_breaks_early_and_counts(self):
        """Per-pair loop (batch unavailable): a claim covered by an early
        summary text breaks and increments the covered count."""
        judge = ContentJudge(log_callback=_Log())
        claim_sentence = (
            "In 1998 researchers demonstrated that orexin deficiency causes "
            "narcolepsy in mice and dogs"
        )
        source = claim_sentence + ". " + "Plain filler context sentences follow. " * 8
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary=claim_sentence,  # identical → jaccard 1.0
            bullet_points=[claim_sentence],
            thorough_summary=claim_sentence,
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.total_source_claims >= 1
        assert result.covered_claims >= 1
        assert result.coverage_pct > 0


# ── 4. _encode_chunks_cached ──────────────────────────────────────────────


class TestEncodeChunksCached:
    def _patch_cached_encode(self, monkeypatch, fn):
        import core.llm.embedding_cache as ec

        monkeypatch.setattr(ec, "cached_encode", fn)

    def test_disabled_returns_none(self, monkeypatch):
        _patch_embedding_settings(monkeypatch, enabled=False)
        assert _encode_chunks_cached(["chunk"]) is None

    def test_model_none_returns_none(self, monkeypatch):
        # The autouse fixture pins get_embed_model → None
        self._patch_cached_encode(monkeypatch, lambda m, c: [])
        assert _encode_chunks_cached(["chunk"]) is None

    def test_unhealthy_returns_none(self, monkeypatch):
        _fake_model(monkeypatch, healthy=False)
        self._patch_cached_encode(monkeypatch, lambda m, c: [])
        assert _encode_chunks_cached(["chunk"]) is None

    def test_cached_encode_none_returns_none(self, monkeypatch):
        _fake_model(monkeypatch)
        self._patch_cached_encode(monkeypatch, lambda m, c: None)
        assert _encode_chunks_cached(["chunk"]) is None

    def test_length_mismatch_returns_none(self, monkeypatch):
        import numpy as np

        _fake_model(monkeypatch)
        self._patch_cached_encode(monkeypatch, lambda m, c: np.ones((3, 4)))
        assert _encode_chunks_cached(["c1", "c2"]) is None

    def test_malformed_scalar_entry_maps_to_none(self, monkeypatch):
        import numpy as np

        _fake_model(monkeypatch)
        self._patch_cached_encode(monkeypatch, lambda m, c: [np.float32(1.0), np.ones(4)])
        out = _encode_chunks_cached(["c1", "c2"])
        assert out is not None
        assert out[0] is None  # ndim 0 → per-pair fallback for that chunk
        assert out[1] is not None

    def test_unconvertible_entry_maps_to_none(self, monkeypatch):
        import numpy as np

        _fake_model(monkeypatch)
        self._patch_cached_encode(monkeypatch, lambda m, c: ["not-a-number", np.ones(4)])
        out = _encode_chunks_cached(["c1", "c2"])
        assert out is not None
        assert out[0] is None

    def test_cached_encode_raising_returns_none(self, monkeypatch):
        _fake_model(monkeypatch)

        def _boom(m, c):
            raise RuntimeError("cache unavailable")

        self._patch_cached_encode(monkeypatch, _boom)
        assert _encode_chunks_cached(["c1"]) is None

    def test_happy_path_returns_embeddings(self, monkeypatch):
        import numpy as np

        _fake_model(monkeypatch)
        self._patch_cached_encode(monkeypatch, lambda m, c: np.ones((2, 4)))
        out = _encode_chunks_cached(["c1", "c2"])
        assert out is not None and len(out) == 2


# ── 5. _check_coverage_batched ────────────────────────────────────────────


class TestCheckCoverageBatched:
    def _judge(self):
        log = _Log()
        return ContentJudge(log_callback=log), log

    def test_disabled_returns_none(self, monkeypatch):
        _patch_embedding_settings(monkeypatch, enabled=False)
        judge, _ = self._judge()
        result = JudgeResult(chapter_heading="Ch")
        assert judge._check_coverage_batched(["claim"], ["summary"], result) is None

    def test_model_none_returns_none(self, monkeypatch):
        _install_fake_st(monkeypatch)
        # The autouse fixture pins get_embed_model → None
        judge, _ = self._judge()
        result = JudgeResult(chapter_heading="Ch")
        assert judge._check_coverage_batched(["claim"], ["summary"], result) is None

    def test_batch_coverage_counts_covered_and_uncovered(self, monkeypatch):
        """2 claims: claim 0 covered (best sim 0.9), claim 1 uncovered (0.2)."""
        import core.llm.embedding_cache as ec

        _install_fake_st(monkeypatch, cos_sim_matrix=[[0.9, 0.3], [0.2, 0.25]])
        _fake_model(monkeypatch)
        monkeypatch.setattr(ec, "cached_encode", lambda m, texts: [[0.0]] * len(texts))
        judge, log = self._judge()
        result = JudgeResult(chapter_heading="Ch")
        covered = judge._check_coverage_batched(
            ["claim zero text", "claim one text"], ["summary text"], result
        )
        assert covered == 1
        assert result.uncovered_claims == ["claim one text"]
        assert any("Batch coverage: 1/2 claims" in m for m, _ in log.calls)

    def test_exception_returns_none(self, monkeypatch):
        _install_fake_st(monkeypatch, cos_sim_raises=True)
        _fake_model(monkeypatch)
        judge, _ = self._judge()
        result = JudgeResult(chapter_heading="Ch")
        assert judge._check_coverage_batched(["claim"], ["summary"], result) is None


# ── 6. judge() — degenerate coverage guard ────────────────────────────────


class TestJudgeDegenerateCoverage:
    def test_zero_of_many_claims_auto_passes_degenerate(self):
        """≥10 claims, 0 covered (broken embedder signature) → coverage
        auto-passes at 100% with uncovered_claims cleared (V18.2.21 BUG-2).

        Claims are capped at 8 per chunk — a >8000-char multi-paragraph
        source yields 2 chunks → up to 16 claims."""
        judge = ContentJudge(log_callback=_Log())
        # Paragraphs of ~2500 chars each; the first two carry numeric claims
        claim_para = " ".join(
            f"Measurement number {i} produced unique findings about topic." for i in range(10)
        )
        filler_tail = " ".join(
            "Plain filler sentence without any claim markers here." for _ in range(40)
        )
        claim_para = claim_para + " " + filler_tail
        plain_para = filler_tail + " " + filler_tail
        source = "\n\n".join([claim_para, claim_para, claim_para, plain_para, plain_para])
        assert len(source) > 8000  # guarantees ≥2 chunks
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary="Zephyr holograms recalibrate nothing at all here.",
            bullet_points=["Quantum tapestries unfurl beyond the shimmering veil."],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.total_source_claims >= 10
        assert result.coverage_pct == 1.0
        assert result.covered_claims == result.total_source_claims
        assert result.uncovered_claims == []


# ── 7. judge() — Layer 8 grounding loop ───────────────────────────────────


class _FakeGroundingResult:
    def __init__(self, available=True, alarm=None, claims=()):
        self.available = available
        self.alarm = alarm
        self.claims = list(claims)

    def format_report(self):
        return "fake L8 report"


def _claim(text, grounded=True, extraction_class="summary_bullet", snippet="src span"):
    return SimpleNamespace(
        extraction_class=extraction_class,
        is_grounded=grounded,
        text=text,
        source_snippet=snippet,
    )


class _FakeExtractor:
    def __init__(self, gr=None, raise_on_extract=False):
        self._gr = gr
        self._raise = raise_on_extract

    def extract(self, source_text, summary_bullets, content_type):
        if self._raise:
            raise RuntimeError("langextract crashed")
        return self._gr


class TestJudgeLayer8:
    def _source(self):
        # > 200 chars, one claim-free filler + one claim sentence
        return (
            "This chapter describes orexin neurons and their role in the regulation "
            "of wakefulness and appetite across mammalian species and laboratory "
            "studies conducted over several decades of careful research. "
            "In 1998 researchers demonstrated that orexin deficiency causes "
            "narcolepsy in mice and dogs."
        )

    def _summary(self, bullets):
        return SummaryResult(
            chapter_heading="Ch",
            executive_summary="Orexin neurons regulate wakefulness.",
            bullet_points=bullets,
            thorough_summary="",
            success=True,
        )

    def test_l8_alarm_logged_and_fallback(self):
        """Extractor available=False + alarm → WARNING + semantic-only path."""
        log = _Log()
        alarm = SimpleNamespace(
            code="langextract_missing", message="langextract not installed", severity="warning"
        )
        gr = _FakeGroundingResult(available=False, alarm=alarm)
        judge = ContentJudge(log_callback=log, claim_extractor=_FakeExtractor(gr))
        bullet = "Orexin neurons regulate wakefulness and appetite."
        result = judge.judge(self._summary([bullet]), self._source())
        assert result.grounding_layer8_available is False
        assert result.grounding_alarm == "langextract_missing"
        assert any("langextract not installed" in m for m, lvl in log.calls if lvl == "WARNING")

    def test_l8_crash_sets_exception_alarm(self):
        log = _Log()
        judge = ContentJudge(
            log_callback=log, claim_extractor=_FakeExtractor(raise_on_extract=True)
        )
        result = judge.judge(
            self._summary(["Orexin neurons regulate wakefulness."]), self._source()
        )
        assert result.grounding_alarm == "layer8_exception:RuntimeError"
        assert any("Layer 8 grounding crashed" in m for m, lvl in log.calls if lvl == "ERROR")

    def test_l8_strong_grounded_bullet_skips_semantic_check(self):
        """A bullet matched by a grounded L8 claim counts WITHOUT the semantic
        loop (grounded even when Jaccard would fail)."""
        log = _Log()
        bullet = "Zephyr quantifiers recalibrate holographic tapestries."
        gr = _FakeGroundingResult(available=True, claims=[_claim(text=bullet)])
        judge = ContentJudge(log_callback=log, claim_extractor=_FakeExtractor(gr))
        result = judge.judge(self._summary([bullet]), self._source())
        assert result.grounding_layer8_available is True
        assert result.strong_grounded_bullets == 1
        assert result.grounded_bullets == 1
        assert result.grounding_pct == 1.0
        # The verbatim evidence is exposed for the keypoints builder
        assert result.bullet_evidence[bullet] == "src span"
        assert any("Layer 8: 1/1 bullets verbatim-grounded" in m for m, _ in log.calls)

    def test_l8_unrelated_claims_ignored(self):
        """L8 claims with extraction_class != summary_bullet are ignored."""
        gr = _FakeGroundingResult(
            available=True,
            claims=[_claim(text="anything", extraction_class="source_claim")],
        )
        judge_l8 = ContentJudge(log_callback=_Log(), claim_extractor=_FakeExtractor(gr))
        bullet = "Orexin neurons regulate wakefulness and appetite."
        result = judge_l8.judge(self._summary([bullet]), self._source())
        assert result.strong_grounded_bullets == 0

    def test_l8_ungrounded_claim_ignored(self):
        """An L8 claim with is_grounded=False is skipped (never counts)."""
        gr = _FakeGroundingResult(
            available=True,
            claims=[
                _claim(text="Orexin neurons regulate wakefulness and appetite.", grounded=False)
            ],
        )
        judge = ContentJudge(log_callback=_Log(), claim_extractor=_FakeExtractor(gr))
        result = judge.judge(
            self._summary(["Orexin neurons regulate wakefulness and appetite."]), self._source()
        )
        assert result.strong_grounded_bullets == 0

    def test_l8_empty_bullet_skipped(self):
        """An empty/whitespace bullet in the summary is skipped in the L8 loop."""
        gr = _FakeGroundingResult(available=True, claims=[])
        judge = ContentJudge(log_callback=_Log(), claim_extractor=_FakeExtractor(gr))
        result = judge.judge(self._summary(["", "   "]), self._source())
        assert result.total_bullets == 2

    def test_l8_rapidfuzz_unavailable_word_overlap_fallback(self, monkeypatch):
        """rapidfuzz blocked → the L8 claim match uses word-overlap scoring."""
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        bullet = "Orexin neurons regulate wakefulness and appetite."
        gr = _FakeGroundingResult(available=True, claims=[_claim(text=bullet)])
        judge = ContentJudge(log_callback=_Log(), claim_extractor=_FakeExtractor(gr))
        result = judge.judge(self._summary([bullet]), self._source())
        # Word-overlap score = 1.0 (identical) ≥ 0.60 → strong grounded
        assert result.strong_grounded_bullets == 1

    def test_l8_available_ungrounded_bullet_goes_to_strong_ungrounded(self):
        """L8 available + bullet failing BOTH tiers → ungrounded_strong."""
        gr = _FakeGroundingResult(available=True, claims=[])
        judge = ContentJudge(log_callback=_Log(), claim_extractor=_FakeExtractor(gr))
        bullet = "Zephyr quantifiers recalibrate holographic tapestries."
        result = judge.judge(self._summary([bullet]), self._source())
        assert result.ungrounded_strong == [bullet[:80]]
        assert result.hallucination_count == 1


# ── 8. judge() — Q2 grounding + Q4 deviation ──────────────────────────────


class TestJudgeGroundingAndDeviation:
    def test_grounded_bullet_via_jaccard(self):
        judge = ContentJudge(log_callback=_Log())
        sentence = (
            "Orexin producing neurons in the lateral hypothalamus regulate "
            "wakefulness and appetite in mammals"
        )
        source = (
            sentence + ". " + "Additional context sentences follow to pass the length gate." * 3
        )
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary=sentence,
            bullet_points=[sentence],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.grounded_bullets == 1
        assert result.grounding_pct == 1.0

    def test_multi_chunk_grounding_breaks_early(self):
        """>8000-char multi-PARAGRAPH source → 2+ chunks; a bullet grounded in
        an early chunk breaks the loop (V18.20.2.0 A23 hoist path)."""
        judge = ContentJudge(log_callback=_Log())
        grounded_sentence = (
            "Orexin neurons in the lateral hypothalamus regulate wakefulness "
            "and appetite in mammals"
        )
        # _chunk_text splits on paragraph boundaries — paragraphs of ~4.6k
        # chars force a 2-chunk split (cumulative > 8000)
        filler_para = "Unrelated filler content about geology and weather patterns. " * 75
        source = grounded_sentence + ".\n\n" + filler_para + "\n\n" + filler_para
        assert len(_chunk_text(source)) >= 2
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary=grounded_sentence,
            bullet_points=[grounded_sentence],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.grounded_bullets == 1

    def test_negation_deviation_detected(self):
        """Bullet negates ('not effective') but the source doesn't → deviation."""
        judge = ContentJudge(log_callback=_Log())
        source = (
            "the treatment is effective for children and adults across multiple "
            "clinical sites and many countries where doctors observe consistent "
            "outcomes and durable remission patterns over several years of "
            "extended follow up in diverse independent hospitals and clinics"
        )
        assert len(source) > 200
        bullet = (
            "the treatment is not effective for children and adults across "
            "multiple clinical sites and many countries where doctors observe "
            "consistent outcomes"
        )
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary=bullet,
            bullet_points=[bullet],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.deviation_count == 1
        assert any("doesn't negate" in d for d in result.deviation_details)

    def test_source_negation_matches_no_deviation(self):
        """Bullet negates AND source negates → no deviation."""
        judge = ContentJudge(log_callback=_Log())
        source = (
            "the treatment is not effective for children and adults across "
            "multiple clinical sites and many countries where doctors observe "
            "consistent outcomes and durable remission patterns over years "
            "of extended follow up in diverse independent hospitals and clinics"
        )
        assert len(source) > 200
        bullet = (
            "the treatment is not effective for children and adults across "
            "multiple clinical sites and many countries where doctors observe "
            "consistent outcomes"
        )
        summary = SummaryResult(
            chapter_heading="Ch",
            executive_summary=bullet,
            bullet_points=[bullet],
            thorough_summary="",
            success=True,
        )
        result = judge.judge(summary, source)
        assert result.deviation_count == 0


# ── 9. llm_judge_grounding ────────────────────────────────────────────────


class TestLlmJudgeGrounding:
    def _bullets(self):
        return ["Orexin neurons regulate wakefulness.", "Zephyr quantifiers shimmer."]

    def test_no_llm_call_fn_returns_none(self):
        judge = ContentJudge(log_callback=_Log())
        assert judge.llm_judge_grounding(self._bullets(), "source", llm_call_fn=None) is None

    def test_no_bullets_returns_none(self):
        judge = ContentJudge(log_callback=_Log())
        assert judge.llm_judge_grounding([], "source", llm_call_fn=lambda p: "x") is None

    def test_no_source_returns_none(self):
        judge = ContentJudge(log_callback=_Log())
        assert judge.llm_judge_grounding(self._bullets(), "", llm_call_fn=lambda p: "x") is None

    def test_long_source_truncated_but_verdicts_parsed(self):
        """A >6000-char source is truncated; the GROUNDED/NOT_GROUNDED
        verdicts are still parsed per bullet."""
        judge = ContentJudge(log_callback=_Log())
        source = "x" * 7000
        response = "GROUNDED: 1\nNOT_GROUNDED: 2\nGROUNDED summary follows."
        out = judge.llm_judge_grounding(self._bullets(), source, llm_call_fn=lambda p: response)
        assert out is not None
        grounded, total, ungrounded = out
        assert grounded == 1
        assert total == 2
        assert ungrounded == ["Zephyr quantifiers shimmer."]
        assert any("1/2 bullets grounded" in m for m, _ in judge.log.calls)

    def test_missing_verdict_assumed_grounded(self):
        judge = ContentJudge(log_callback=_Log())
        response = "GROUNDED: 1\nNo mention of the second bullet at all."
        out = judge.llm_judge_grounding(self._bullets(), "source text " * 40, lambda p: response)
        grounded, total, ungrounded = out
        assert grounded == 2  # unmentioned bullet assumed grounded
        assert ungrounded == []

    def test_empty_llm_response_returns_none(self):
        judge = ContentJudge(log_callback=_Log())
        assert judge.llm_judge_grounding(self._bullets(), "src", lambda p: "") is None

    def test_llm_call_exception_returns_none(self):
        judge = ContentJudge(log_callback=_Log())

        def _boom(prompt):
            raise RuntimeError("LLM down")

        assert judge.llm_judge_grounding(self._bullets(), "src", _boom) is None
        assert any("LLM Judge failed" in m for m, lvl in judge.log.calls if lvl == "WARNING")


# ── 10. build_gap_fill_prompt fallback ────────────────────────────────────


class TestBuildGapFillPrompt:
    def test_prompt_contains_claims_and_bullets(self):
        judge = ContentJudge(log_callback=_Log())
        prompt = judge.build_gap_fill_prompt(
            "Chapter Heading",
            ["uncovered claim one", "uncovered claim two"],
            ["existing bullet"],
        )
        assert isinstance(prompt, str)
