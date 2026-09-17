"""V18.4 (Phase 2) — Embedder optional-mode tests.

Exit-gate tests for the two new settings knobs:

  - ``embedding.enabled``  (default ``True``) — gates the semantic path.
  - ``embedding.fallback`` (default ``"jaccard"``, optional ``"skip"``) —
    decides what happens when ``enabled=False``.

Behaviour matrix verified here:

  | enabled | fallback   | Phase 2.2 behaviour                              |
  |---------|------------|--------------------------------------------------|
  | True    | (ignored)  | embedder attempted; auto-Jaccard on failure      |
  | False   | "jaccard"  | embedder NOT attempted; Jaccard similarity used  |
  | False   | "skip"     | EmbeddingDisabled raised; judge() skips Phase 2.2 |

These tests load ``content_judge.py`` directly via ``importlib`` (same
pattern as ``test_content_judge.py``) to bypass ``core.summarisation.__init__``
which imports ``Summarizer`` → ``tiktoken`` (heavy / not always installed).

The ``_embedding_settings()`` helper is patched at the module level so the
tests are hermetic — no real ``Settings()`` / ``settings.json`` needed.

Run: ``pytest tests/test_embedder_optional.py -v``
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load content_judge.py directly to bypass core.summarisation.__init__
# (which imports Summarizer → tiktoken). content_judge only needs
# core.models.SummaryResult, which is a pure dataclass.
import core.models  # noqa: F401  (ensures core.models is importable)

_spec = importlib.util.spec_from_file_location(
    "core.summarisation.content_judge_v18_4_test",
    _project_root / "core" / "summarisation" / "content_judge_impl.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

_semantic_similarity = _mod._semantic_similarity
_jaccard = _mod._jaccard
_embedding_settings = _mod._embedding_settings
ContentJudge = _mod.ContentJudge
JudgeResult = _mod.JudgeResult
EmbeddingDisabled = _mod.EmbeddingDisabled
EmbedderUnavailable = _mod.EmbedderUnavailable

from core.models import SummaryResult


@pytest.fixture(autouse=True)
def _reset_warning_flags():
    """Reset the module-level one-time-warning flags before each test.

    ``_warned_semantic_fallback`` and ``_warned_embedding_disabled`` are
    module globals that fire once per process. Without resetting, the first
    test to trip a warning would mask the behaviour for subsequent tests.
    """
    _mod._warned_semantic_fallback = False
    _mod._warned_embedding_disabled = False
    yield


# ── 1. _embedding_settings() helper ────────────────────────────────────────


class TestEmbeddingSettingsHelper:
    """The helper reads the knobs safely and normalises bad values."""

    def test_returns_defaults_when_settings_unavailable(self, monkeypatch):
        """When Settings() raises, the helper falls back to (True, 'jaccard')."""
        def _boom():
            raise RuntimeError("no settings in test sandbox")
        # Patch the Settings import inside the helper by making the module's
        # _embedding_settings call a broken Settings. Easiest: patch the
        # function to simulate the except-branch by raising at import time.
        # Instead, directly verify the default-return path via the helper's
        # documented behaviour: it catches Exception and returns (True, "jaccard").
        import utils.settings as settings_mod
        orig_get = settings_mod.Settings.get if hasattr(settings_mod, "Settings") else None
        # Force Settings().get to raise
        class _BrokenSettings:
            def get(self, path, default=None):
                raise RuntimeError("boom")
            def _defaults(self):
                return {}
        monkeypatch.setattr(settings_mod, "Settings", lambda: _BrokenSettings())
        enabled, fallback = _embedding_settings()
        assert enabled is True
        assert fallback == "jaccard"

    def test_normalises_unknown_fallback_to_jaccard(self, monkeypatch):
        """An unknown fallback value degrades to 'jaccard' (safer than 'skip')."""
        import utils.settings as settings_mod
        class _FakeSettings:
            _data = {"embedding": {"enabled": False, "fallback": "banana"}}
            def get(self, path, default=None):
                parts = path.split(".")
                cur = self._data
                for p in parts:
                    if isinstance(cur, dict) and p in cur:
                        cur = cur[p]
                    else:
                        return default
                return cur
            def _defaults(self):
                return self._data
        monkeypatch.setattr(settings_mod, "Settings", lambda: _FakeSettings())
        enabled, fallback = _embedding_settings()
        assert enabled is False
        assert fallback == "jaccard"  # normalised from "banana"


# ── 2. _semantic_similarity — skip path (enabled=False, fallback="skip") ──


class TestSemanticSimilaritySkipPath:
    """When enabled=False + fallback="skip", _semantic_similarity raises
    EmbeddingDisabled — the explicit, non-silent signal to skip Phase 2.2."""

    def test_raises_embedding_disabled_when_skip_mode(self, monkeypatch):
        """enabled=False, fallback="skip" → EmbeddingDisabled raised."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "skip"))
        with pytest.raises(EmbeddingDisabled) as exc_info:
            _semantic_similarity("a claim", "a candidate")
        assert "embedding.enabled=False" in str(exc_info.value)
        assert "skip" in str(exc_info.value)

    def test_skip_does_not_attempt_embedder(self, monkeypatch):
        """The embedder is never loaded/called in skip mode (no network, no torch)."""
        # If the embedder WERE attempted, it would import sentence_transformers
        # (not installed in sandbox) and hit the generic-Exception fallback.
        # We assert the EmbeddingDisabled fires BEFORE that code path.
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "skip"))
        embedder_called = []
        # Patch get_embed_model to detect any embedder access (should NOT happen).
        import core.llm.model_singletons as ms
        monkeypatch.setattr(ms, "get_embed_model",
                            lambda *a, **k: embedder_called.append(1) or None)
        with pytest.raises(EmbeddingDisabled):
            _semantic_similarity("claim", "candidate")
        assert embedder_called == [], "embedder must not be called in skip mode"


# ── 3. _semantic_similarity — jaccard path (enabled=False, fallback="jaccard") ─


class TestSemanticSimilarityJaccardPath:
    """When enabled=False + fallback="jaccard", _semantic_similarity returns
    a Jaccard word-overlap float WITHOUT attempting the embedder."""

    def test_returns_jaccard_float_not_raises(self, monkeypatch):
        """enabled=False, fallback="jaccard" → returns a float similarity."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "jaccard"))
        sim = _semantic_similarity("the cat sat on mat", "the cat sat")
        assert isinstance(sim, float)
        # Jaccard: words1={the,cat,sat,on,mat}, words2={the,cat,sat}
        # intersection=3, union=5 → 0.6
        assert sim == pytest.approx(0.6, abs=1e-6)

    def test_jaccard_path_does_not_attempt_embedder(self, monkeypatch):
        """No embedder call in the explicit-jaccard path either."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "jaccard"))
        embedder_called = []
        import core.llm.model_singletons as ms
        monkeypatch.setattr(ms, "get_embed_model",
                            lambda *a, **k: embedder_called.append(1) or None)
        sim = _semantic_similarity("some claim", "some candidate")
        assert isinstance(sim, float)
        assert embedder_called == [], "embedder must not be called when enabled=False"

    def test_jaccard_returns_zero_for_empty_strings(self, monkeypatch):
        """Edge case: empty input → 0.0 (not a division-by-zero)."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "jaccard"))
        assert _semantic_similarity("", "candidate") == 0.0
        assert _semantic_similarity("claim", "") == 0.0

    def test_jaccard_identical_strings_return_one(self, monkeypatch):
        """Identical non-empty strings → Jaccard = 1.0."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "jaccard"))
        sim = _semantic_similarity("identical text here", "identical text here")
        assert sim == pytest.approx(1.0, abs=1e-6)


# ── 4. _semantic_similarity — default path (enabled=True) ──────────────────


class TestSemanticSimilarityDefaultPath:
    """Regression guard: the default (enabled=True) path is UNCHANGED by V18.4.

    It still attempts the embedder (which fails in the sandbox because
    sentence_transformers is not installed) and falls back to Jaccard via
    the generic-Exception handler — the pre-V18.4 behaviour. Crucially, it
    does NOT raise EmbeddingDisabled and does NOT take the explicit-disable
    early return.
    """

    def test_default_does_not_raise_embedding_disabled(self, monkeypatch):
        """enabled=True → never raises EmbeddingDisabled."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (True, "jaccard"))
        # In the sandbox, sentence_transformers is not installed → the try
        # block raises ImportError → caught by `except Exception` → Jaccard.
        sim = _semantic_similarity("the cat sat", "the cat sat")
        assert isinstance(sim, float)
        # Should be the Jaccard fallback value, not an EmbeddingDisabled.
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_default_does_not_set_disable_warning_flag(self, monkeypatch):
        """The _warned_embedding_disabled flag stays False on the default path.

        That flag only fires in the enabled=False+jaccard branch. If the
        default path tripped it, the opt-out warning would leak into normal runs.
        """
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (True, "jaccard"))
        _mod._warned_embedding_disabled = False
        _semantic_similarity("claim text", "candidate text")
        assert _mod._warned_embedding_disabled is False, (
            "default path must not set the disable-warning flag"
        )

    def test_default_unchanged_behaviour_returns_float(self, monkeypatch):
        """The default path returns a float (via embedder-or-fallback), matching
        the pre-V18.4 signature."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (True, "jaccard"))
        result = _semantic_similarity("foo bar baz", "foo bar qux")
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ── 5. ContentJudge.judge() — end-to-end skip ──────────────────────────────


class TestJudgeSkipMode:
    """When enabled=False + fallback="skip", judge() short-circuits Phase 2.2:
    sets coverage_skipped=True, auto-passes coverage, logs a WARNING."""

    @pytest.fixture
    def judge(self):
        return ContentJudge(log_callback=lambda msg, level="INFO": None)

    def _make_source_with_claims(self) -> str:
        """Source text with extractable claims (numbers + causal language)."""
        return (
            "The study found that 42% of participants improved significantly. "
            "Therefore the treatment causes recovery in most cases. "
            "Researchers demonstrated that the mechanism activates within 24 hours. "
        ) * 10  # repeat so _chunk_text produces enough claims

    def test_judge_sets_coverage_skipped_in_skip_mode(self, judge, monkeypatch):
        """judge() with enabled=False+skip → coverage_skipped=True, auto-pass."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "skip"))
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="The study shows improvement.",
            bullet_points=["42% of participants improved.", "The treatment causes recovery."],
            thorough_summary="The mechanism activates within 24 hours.",
        )
        result = judge.judge(summary, self._make_source_with_claims())
        assert result.coverage_skipped is True
        # Coverage auto-passed (can't measure → 1.0)
        assert result.coverage_pct == 1.0
        assert result.covered_claims == result.total_source_claims
        # No uncovered claims → no gap-fill triggered
        assert result.uncovered_claims == []

    def test_judge_does_not_skip_in_jaccard_mode(self, judge, monkeypatch):
        """judge() with enabled=False+jaccard → coverage_skipped=False (runs Jaccard)."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "jaccard"))
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="The study shows 42% improvement.",
            bullet_points=["42% of participants improved."],
            thorough_summary="The treatment causes recovery.",
        )
        result = judge.judge(summary, self._make_source_with_claims())
        assert result.coverage_skipped is False
        # Coverage was actually computed (Jaccard), not auto-passed
        assert 0.0 <= result.coverage_pct <= 1.0

    def test_judge_does_not_skip_in_default_mode(self, judge, monkeypatch):
        """judge() with enabled=True → coverage_skipped=False (default path)."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (True, "jaccard"))
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="The study shows 42% improvement.",
            bullet_points=["42% of participants improved."],
            thorough_summary="The treatment causes recovery.",
        )
        result = judge.judge(summary, self._make_source_with_claims())
        assert result.coverage_skipped is False

    def test_coverage_skipped_appears_in_format_report(self, judge, monkeypatch):
        """format_report() shows 'coverage=SKIPPED(embedding off)' when skipped."""
        monkeypatch.setattr(_mod, "_embedding_settings", lambda: (False, "skip"))
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="Some summary.",
            bullet_points=["A bullet."],
            thorough_summary="A thorough.",
        )
        result = judge.judge(summary, self._make_source_with_claims())
        report = result.format_report()
        assert "SKIPPED(embedding off)" in report
