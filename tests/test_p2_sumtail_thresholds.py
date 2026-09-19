"""Phase 2 (Test-Net Deepening) — long-tail coverage for thresholds.py.

``core/summarisation/thresholds.py`` is the SINGLE SOURCE OF TRUTH for the
anti-hallucination thresholds (V13.27.0). The baseline suite imports the
constants but never exercises ``_get_threshold_scale``'s auto-calibration
map (V18.2.7) nor ``scaled_threshold`` — this file covers:

  * the per-embedder-model auto-calibration map (MiniLM/BGE/Qwen/nomic/e5/
    paraphrase/unknown)
  * the manual ``embedding.threshold_scale`` override (respected, cached)
  * the Settings-failure fail-open path (scale stays 1.0)
  * ``scaled_threshold`` clamping to [0.1, 0.99]
  * the caching semantics (a non-1.0 scale short-circuits the Settings read)

Hermetic: ``utils.settings.Settings`` is monkeypatched with a ``_FakeSettings``
stand-in (group_b discipline) — no ``~/.elixir/settings.json`` read, and the
module global ``_THRESHOLD_SCALE`` is snapshot/restored around every test.

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_thresholds.py -q --no-cov``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation import thresholds
from core.summarisation.thresholds import (
    F4_SOURCE_OVERLAP_DROP,
    F4_SOURCE_OVERLAP_RECOVER,
    PACKETS_VALIDATION_TRACE,
    SEMANTIC_FACT_CHECK_DROP,
    VERIFY_BULLETS_MARK,
    scaled_threshold,
)


class _FakeSettings:
    """Stand-in for ``utils.settings.Settings`` (hermetic)."""

    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


class _ExplodingSettings:
    """Settings stand-in whose .get always raises (fail-open path)."""

    def get(self, key, default=None):
        raise RuntimeError("settings store unavailable")


class _RaisingSettings:
    """Settings() constructor itself raises."""

    def __init__(self):
        raise RuntimeError("cannot construct Settings")


@pytest.fixture(autouse=True)
def _reset_threshold_scale():
    """Snapshot + restore the cached module global around every test."""
    saved = thresholds._THRESHOLD_SCALE
    thresholds._THRESHOLD_SCALE = 1.0
    yield
    thresholds._THRESHOLD_SCALE = saved


def _patch_settings(monkeypatch, settings_obj):
    """``settings_obj`` is either an instance (returned as-is) or a CLASS
    whose constructor raises (the raise then happens inside the caller's try)."""
    import inspect

    if inspect.isclass(settings_obj):
        monkeypatch.setattr("utils.settings.Settings", settings_obj)
    else:
        monkeypatch.setattr("utils.settings.Settings", lambda: settings_obj)


# ── 1. Auto-calibration map (V18.2.7) ───────────────────────────────────────


class TestAutoCalibrationMap:
    @pytest.mark.parametrize(
        ("model", "expected_scale"),
        [
            ("all-MiniLM-L6-v2", 1.0),  # baseline — thresholds as-is
            ("sentence-transformers/all-MiniLM-L6-v2", 1.0),
            ("BAAI/bge-small-en-v1.5", 0.85),
            ("baai/bge-base-en-v1.5", 0.85),
            ("BAAI/bge_large", 0.85),
            ("Qwen3-Embedding-0.6B", 0.80),
            ("nomic-embed-text", 0.85),
            ("intfloat/e5-small", 0.85),
            # NOTE: "paraphrase-multilingual-MiniLM-*" hits the minilm branch
            # FIRST (1.0) — the paraphrase 0.90 branch is only reachable for
            # paraphrase models WITHOUT "minilm" in the name (see the
            # suspected-bug note in this file's header).
            ("paraphrase-mpnet-base-v2", 0.90),
            ("totally-unknown-embedder", 1.0),  # unknown model — baseline
        ],
    )
    def test_auto_scale_per_embedder(self, monkeypatch, model, expected_scale):
        _patch_settings(monkeypatch, _FakeSettings({"embedding.model": model}))
        scale = thresholds._get_threshold_scale()
        assert scale == pytest.approx(expected_scale), (
            f"embedder '{model}' must auto-calibrate to {expected_scale}"
        )
        # The scale is CACHED after the first read
        assert pytest.approx(expected_scale) == thresholds._THRESHOLD_SCALE

    def test_auto_scaled_drop_threshold_value(self, monkeypatch):
        """BGE (0.85) lowers the 0.50 semantic drop threshold to 0.425."""
        _patch_settings(monkeypatch, _FakeSettings({"embedding.model": "BAAI/bge-small-en-v1.5"}))
        assert scaled_threshold(SEMANTIC_FACT_CHECK_DROP) == pytest.approx(0.425)

    def test_qwen_lowers_more_than_bge(self, monkeypatch):
        _patch_settings(monkeypatch, _FakeSettings({"embedding.model": "Qwen3-Embedding"}))
        qwen = scaled_threshold(SEMANTIC_FACT_CHECK_DROP)
        thresholds._THRESHOLD_SCALE = 1.0  # reset cache between reads
        _patch_settings(monkeypatch, _FakeSettings({"embedding.model": "BAAI/bge-small"}))
        bge = scaled_threshold(SEMANTIC_FACT_CHECK_DROP)
        assert qwen < bge, "Qwen embeddings produce lower cosines → lower scale than BGE"


# ── 2. Manual override (respected + cached) ────────────────────────────────


class TestManualOverride:
    def test_manual_scale_respected_over_auto(self, monkeypatch):
        """A manual embedding.threshold_scale != 1.0 wins over auto-calibration."""
        _patch_settings(
            monkeypatch,
            _FakeSettings(
                {"embedding.model": "BAAI/bge-small-en-v1.5", "embedding.threshold_scale": 0.70}
            ),
        )
        assert thresholds._get_threshold_scale() == pytest.approx(0.70)

    def test_cached_scale_short_circuits_settings_read(self, monkeypatch):
        """Once cached (!= 1.0), a second call returns without touching Settings."""
        _patch_settings(monkeypatch, _FakeSettings({"embedding.threshold_scale": 0.5}))
        first = thresholds._get_threshold_scale()
        assert first == pytest.approx(0.5)
        # Swap in an exploding Settings — the cached value must still be served
        _patch_settings(monkeypatch, _RaisingSettings)
        assert thresholds._get_threshold_scale() == pytest.approx(0.5)


# ── 3. Fail-open paths ─────────────────────────────────────────────────────


class TestFailOpen:
    def test_settings_get_raising_keeps_default(self, monkeypatch):
        """An exception inside the Settings read fails OPEN (scale stays 1.0)."""
        _patch_settings(monkeypatch, _ExplodingSettings())
        assert thresholds._get_threshold_scale() == 1.0

    def test_settings_constructor_raising_keeps_default(self, monkeypatch):
        _patch_settings(monkeypatch, _RaisingSettings)
        assert thresholds._get_threshold_scale() == 1.0

    def test_bad_threshold_scale_type_fails_open(self, monkeypatch):
        """A non-float threshold_scale value raises inside the try → fail-open."""
        _patch_settings(monkeypatch, _FakeSettings({"embedding.threshold_scale": "not-a-number"}))
        assert thresholds._get_threshold_scale() == 1.0


# ── 4. scaled_threshold clamping ───────────────────────────────────────────


class TestScaledThresholdClamping:
    def test_clamps_to_099_ceiling(self, monkeypatch):
        _patch_settings(monkeypatch, _FakeSettings({"embedding.threshold_scale": 3.0}))
        assert scaled_threshold(0.80) == pytest.approx(0.99)

    def test_clamps_to_01_floor(self, monkeypatch):
        _patch_settings(monkeypatch, _FakeSettings({"embedding.threshold_scale": 0.05}))
        assert scaled_threshold(0.30) == pytest.approx(0.1)

    def test_default_scale_passes_base_through(self, monkeypatch):
        _patch_settings(monkeypatch, _FakeSettings({}))
        assert scaled_threshold(0.42) == pytest.approx(0.42)


# ── 5. Documented constant values (the single-source-of-truth contract) ─────


class TestThresholdConstants:
    def test_documented_values(self):
        """The 5 documented thresholds (module docstring) must not drift."""
        assert F4_SOURCE_OVERLAP_DROP == 0.25
        assert F4_SOURCE_OVERLAP_RECOVER == 0.30
        assert VERIFY_BULLETS_MARK == 0.50
        assert SEMANTIC_FACT_CHECK_DROP == 0.50
        assert PACKETS_VALIDATION_TRACE == 0.42

    def test_recovery_strictly_above_drop(self):
        """The intentional [0.25, 0.30) dead-band: drop < recover."""
        assert F4_SOURCE_OVERLAP_RECOVER > F4_SOURCE_OVERLAP_DROP
