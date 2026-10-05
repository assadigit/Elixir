"""V0.5.16 — the gap-fill Phase 2.2 degenerate-signal guard tests.

Characterization tests for ``BulletPipeline._validate_gap_fill_bullets``
(core/summarisation/bullet_pipeline.py): on an embedder-less rig,
``semantic_fact_check`` fails CLOSED (V18.1 S1: is_grounded=False,
best_similarity=0.0, reason="embed_model_unavailable") — a DEGENERATE
signal, not a real 0.00 similarity. Before V0.5.16 the gap-fill
validation rejected EVERY bullet on that signal (the main Phase 2.2
stage already had the V18.2.30 health skip; the gap-fill call site
didn't), so an embedder-less rig lost all concept gap-fill bullets
while the deterministic F4 check passed them.

Behaviour matrix verified here:

| embedder     | bullet              | expected                        |
|--------------|---------------------|---------------------------------|
| unhealthy    | F4 overlap ≥ 25%    | KEPT (F4 gates; Phase 2.2 skip) |
| unhealthy    | F4 overlap < 25%    | REJECTED (F4 is deterministic)  |
| healthy      | sim < 0.5           | REJECTED (real signal)          |
| healthy      | reason=unavailable  | KEPT (per-bullet fail-open)     |

Content-agnostic (Rule 1): synthetic bullets, no book-derived strings.

Run: ``pytest tests/test_v0516_gapfill_embedder_guard.py -v``
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.bullet_pipeline import BulletPipeline


class _LogCollector:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def __call__(self, msg: str, level: str = "INFO") -> None:
        self.lines.append((level, msg))

    def joined(self) -> str:
        return "\n".join(m for _, m in self.lines)


def _make_summarizer():
    s = MagicMock()
    s.log = _LogCollector()
    return s


# A source + bullet pair with clearly ≥25% content-word overlap (F4 pass):
_SOURCE = (
    "The theory of identity formation describes how a persistent sense of "
    "selfsameness develops across developmental stages. Author (1970) "
    "emphasized that ego synthesis and inner solidarity form gradually."
)
_BULLET_F4_PASS = (
    "Author (1970) emphasized that ego synthesis and inner solidarity form "
    "gradually across developmental stages of identity formation."
)
# A bullet with essentially zero overlap with the source (F4 fail):
_BULLET_F4_FAIL = (
    "Zeppelin travel schedules revolutionized transatlantic postal delivery "
    "during the seventeenth century according to unnamed chroniclers."
)


def test_unhealthy_embedder_keeps_f4_passing_bullets(monkeypatch):
    """V0.5.16: the degenerate signal must not reject F4-grounded bullets."""
    fake_singletons = types.SimpleNamespace(is_embedder_healthy=lambda: False)
    monkeypatch.setitem(sys.modules, "core.llm.model_singletons", fake_singletons)

    s = _make_summarizer()
    out = BulletPipeline._validate_gap_fill_bullets([_BULLET_F4_PASS], _SOURCE, s)

    assert out == [_BULLET_F4_PASS]
    log = s.log.joined()
    assert "embedder unhealthy" in log  # the loud skip line fired
    assert "sim 0.00" not in log  # no false Phase 2.2 rejection


def test_unhealthy_embedder_still_rejects_f4_failures(monkeypatch):
    """F4 (deterministic, no embedder needed) still gates every bullet."""
    fake_singletons = types.SimpleNamespace(is_embedder_healthy=lambda: False)
    monkeypatch.setitem(sys.modules, "core.llm.model_singletons", fake_singletons)

    s = _make_summarizer()
    out = BulletPipeline._validate_gap_fill_bullets([_BULLET_F4_FAIL], _SOURCE, s)

    assert out == []
    assert "F4 overlap" in s.log.joined()


def test_healthy_embedder_rejects_low_similarity(monkeypatch):
    """A REAL low-similarity rejection (embedder present) is untouched."""
    fake_singletons = types.SimpleNamespace(is_embedder_healthy=lambda: True)
    monkeypatch.setitem(sys.modules, "core.llm.model_singletons", fake_singletons)

    import core.summarisation.bullet_pipeline as bp

    def _fake_sfc(bullet, source_text, threshold=0.5):
        return {
            "is_grounded": False,
            "best_similarity": 0.31,
            "best_source_sentence": "…",
            "reason": "low_similarity",
        }

    monkeypatch.setattr(bp, "semantic_fact_check", _fake_sfc, raising=False)
    # Patch the in-function import target (text_preprocessor module attr).
    import core.summarisation.text_preprocessor as tp

    monkeypatch.setattr(tp, "semantic_fact_check", _fake_sfc, raising=False)

    s = _make_summarizer()
    out = BulletPipeline._validate_gap_fill_bullets([_BULLET_F4_PASS], _SOURCE, s)

    assert out == []
    assert "Phase 2.2 sim 0.31" in s.log.joined()


def test_healthy_embedder_failopens_on_unavailable_reason(monkeypatch):
    """Belt+braces: reason='embed_model_unavailable' keeps the bullet
    even when the health probe passed (the load can fail mid-run)."""
    fake_singletons = types.SimpleNamespace(is_embedder_healthy=lambda: True)
    monkeypatch.setitem(sys.modules, "core.llm.model_singletons", fake_singletons)

    def _fake_sfc(bullet, source_text, threshold=0.5):
        return {
            "is_grounded": False,
            "best_similarity": 0.0,
            "best_source_sentence": "",
            "reason": "embed_model_unavailable",
        }

    import core.summarisation.text_preprocessor as tp

    monkeypatch.setattr(tp, "semantic_fact_check", _fake_sfc, raising=False)

    s = _make_summarizer()
    out = BulletPipeline._validate_gap_fill_bullets([_BULLET_F4_PASS], _SOURCE, s)

    assert out == [_BULLET_F4_PASS]
    assert "Phase 2.2 unavailable" in s.log.joined()
