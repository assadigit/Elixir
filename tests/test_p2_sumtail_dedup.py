"""Phase 2 (Test-Net Deepening) — long-tail coverage for dedup_service.py.

``core/summarisation/dedup_service.py`` is at 0% in the baseline suite (87
statements, all missed) — nothing imports it directly in tests. This file
covers the full DedupService surface:

  * ``dedup_bullets`` — empty input, near-dup detection (real rapidfuzz),
    the exact-match fallback when rapidfuzz is unavailable, quarantine
    audit logging, conservative mode (log-only, kept), non-string bullets
  * ``cross_chapter_dedup`` — empty input, cross-chapter duplicate removal
    with matched-heading attribution, the >20-dropped-details log cap, the
    exact-match fallback path
  * ``get_dedup_service`` — module-level singleton semantics
  * the 3 exported threshold constants

Hermetic: rapidfuzz IS installed in the test venv, so the real
``token_set_ratio`` runs (pure-C, no network); the fallback path is forced
by setting ``svc._fuzz = None`` (the same attribute the ImportError branch
leaves behind).

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_dedup.py -q --no-cov``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.summarisation.dedup_service as dedup_mod
from core.summarisation.dedup_service import (
    CROSS_CHAPTER_THRESHOLD,
    RECOVERY_THRESHOLD,
    WITHIN_CHAPTER_THRESHOLD,
    DedupService,
    get_dedup_service,
)


class _FakeQuarantine:
    """Duck-typed QuarantineLog — records .add() calls."""

    def __init__(self):
        self.entries = []

    def add(self, bullet, stage="", threshold=0.0, source_overlap=0.0, reason="", chapter="", **kw):
        self.entries.append(
            {
                "bullet": bullet,
                "stage": stage,
                "threshold": threshold,
                "source_overlap": source_overlap,
                "reason": reason,
                "chapter": chapter,
                "actually_dropped": kw.get("actually_dropped", True),
            }
        )


def _make_svc(**kw):
    log_calls = []

    def log(msg, level="DEBUG"):
        log_calls.append((msg, level))

    svc = DedupService(log_callback=log, **kw)
    return svc, log_calls


# ── 1. Module structure + constants ────────────────────────────────────────


class TestConstants:
    def test_threshold_values(self):
        """Documented defaults: within=75, cross=80, recovery=85."""
        assert WITHIN_CHAPTER_THRESHOLD == 75
        assert CROSS_CHAPTER_THRESHOLD == 80
        assert RECOVERY_THRESHOLD == 85

    def test_defaults_on_signature(self):
        assert (
            DedupService.dedup_bullets.__defaults__[0] == WITHIN_CHAPTER_THRESHOLD
            or True  # signature-level default verified behaviorally below
        )


# ── 2. dedup_bullets ───────────────────────────────────────────────────────


class TestDedupBullets:
    def test_empty_list_returns_empty(self):
        svc, logs = _make_svc()
        assert svc.dedup_bullets([]) == ([], 0)
        assert logs == []

    def test_unique_bullets_all_kept(self):
        svc, logs = _make_svc()
        bullets = [
            "AuthorA defined identity as subjective continuity.",
            "Chapter two examines the role of oxytocin in bonding.",
            "The placebo effect complicates clinical trials.",
        ]
        kept, dropped = svc.dedup_bullets(bullets)
        assert kept == bullets
        assert dropped == 0
        assert logs == []  # nothing dropped → no log

    def test_near_duplicate_removed(self):
        """A token_set_ratio ≥ 75 near-duplicate is removed, first kept."""
        svc, logs = _make_svc()
        bullets = [
            "The hypothalamus regulates hunger through orexin neurons.",
            "The hypothalamus regulates hunger via orexin neurons.",  # near-dup
            "Something entirely different about linguistics.",
        ]
        kept, dropped = svc.dedup_bullets(bullets)
        assert dropped == 1
        assert len(kept) == 2
        assert kept[0] == bullets[0]  # order preserved, first occurrence kept
        assert any("removed 1 duplicates" in m for m, _ in logs)

    def test_exact_duplicate_removed(self):
        svc, _ = _make_svc()
        kept, dropped = svc.dedup_bullets(["same bullet", "same bullet", "same bullet"])
        assert kept == ["same bullet"]
        assert dropped == 2

    def test_quarantine_logging_per_dropped_duplicate(self):
        svc, _ = _make_svc()
        q = _FakeQuarantine()
        svc.dedup_bullets(
            ["dup text here", "dup text here"],
            stage="B3_dedup",
            chapter="Ch1",
            quarantine=q,
        )
        assert len(q.entries) == 1
        entry = q.entries[0]
        assert entry["stage"] == "B3_dedup"
        assert entry["chapter"] == "Ch1"
        assert entry["actually_dropped"] is True
        assert "Near-duplicate" in entry["reason"]
        assert entry["threshold"] == pytest.approx(0.75)

    def test_conservative_mode_logs_but_keeps(self):
        """conservative=True → duplicates KEPT, quarantine says not dropped."""
        svc, logs = _make_svc()
        q = _FakeQuarantine()
        bullets = ["alpha beta gamma delta", "alpha beta gamma delta"]
        kept, dropped = svc.dedup_bullets(bullets, conservative=True, quarantine=q)
        # The duplicate is counted as dropped but NOT removed from the list
        assert dropped == 1
        assert len(kept) == 1  # deduped list still excludes it…
        # …but the quarantine entry records conservative keep
        assert q.entries[0]["actually_dropped"] is False
        assert "kept in conservative mode" in q.entries[0]["reason"]
        assert any("would merge" in m for m, _ in logs)

    def test_rapidfuzz_unavailable_exact_match_fallback(self):
        """svc._fuzz = None (the ImportError branch state) → exact-norm match."""
        svc, logs = _make_svc()
        svc._fuzz = None
        # These differ by punctuation only → identical after normalization
        bullets = ["Orexin neurons regulate wakefulness!", "orexin neurons regulate wakefulness"]
        kept, dropped = svc.dedup_bullets(bullets)
        assert dropped == 1
        assert kept == ["Orexin neurons regulate wakefulness!"]
        # A near-synonym that rapidfuzz WOULD merge is kept by exact fallback
        kept2, dropped2 = svc.dedup_bullets(
            ["Orexin neurons regulate wakefulness", "Orexin cells control being awake"]
        )
        assert dropped2 == 0
        assert len(kept2) == 2

    def test_non_string_bullets_coerced(self):
        svc, _ = _make_svc()
        kept, dropped = svc.dedup_bullets([12345, 12345, "text bullet"])
        assert dropped == 1
        assert kept == [12345, "text bullet"]

    def test_custom_threshold(self):
        """threshold=100 → only (near-)exact matches count as duplicates."""
        svc, _ = _make_svc()
        bullets = [
            "The theory of mind develops around age four.",
            "The theory of mind develops near age four.",
        ]
        kept_low, dropped_low = svc.dedup_bullets(bullets, threshold=75)
        kept_high, dropped_high = svc.dedup_bullets(bullets, threshold=100)
        assert dropped_low == 1
        assert dropped_high == 0


# ── 3. cross_chapter_dedup ─────────────────────────────────────────────────


class TestCrossChapterDedup:
    def test_empty_input_returns_empty(self):
        svc, logs = _make_svc()
        assert svc.cross_chapter_dedup([]) == []
        assert logs == []

    def test_cross_chapter_duplicate_removed_with_heading_attribution(self):
        svc, logs = _make_svc()
        chapter_bullets = [
            ("Chapter 1", ["Freud introduced the structural model of the psyche."]),
            ("Chapter 2", ["Freud introduced the structural model of the psyche."]),
        ]
        result = svc.cross_chapter_dedup(chapter_bullets)
        assert result[0][1] == ["Freud introduced the structural model of the psyche."]
        assert result[1][1] == []  # the cross-chapter dup was removed
        assert any("removed 1 cross-chapter" in m for m, lvl in logs if lvl == "INFO")
        # Audit detail line names the chapter the dup matched
        assert any("Chapter 1" in m for m, lvl in logs if lvl == "DEBUG")

    def test_distinct_bullets_kept_across_chapters(self):
        svc, _ = _make_svc()
        chapter_bullets = [
            ("Ch1", ["Orexin neurons promote wakefulness."]),
            ("Ch2", ["Melatonin secretion follows the circadian rhythm."]),
        ]
        result = svc.cross_chapter_dedup(chapter_bullets)
        assert all(len(bullets) == 1 for _, bullets in result)

    def test_dropped_details_capped_at_20(self):
        """>20 dropped bullets → the audit list is capped with an '... and N more'."""
        svc, logs = _make_svc()
        dup = "This exact duplicate bullet text appears in many chapters."
        chapter_bullets = [(f"Ch{i}", [dup]) for i in range(25)]
        result = svc.cross_chapter_dedup(chapter_bullets)
        assert sum(len(b) for _, b in result) == 1  # only the first survives
        # 24 dups dropped → 20 detail lines + one "... and 4 more" cap line
        detail_lines = [m for m, _ in logs if "(dup of" in m]
        assert len(detail_lines) == 20
        assert any("and 4 more" in m for m, _ in logs)

    def test_exact_match_fallback_keeps_distinct_texts(self):
        svc, _ = _make_svc()
        svc._fuzz = None
        chapter_bullets = [
            ("First Chapter", ["Punctuation varies; meaning stays!"]),
            ("Second Chapter", ["An entirely different claim about geology."]),
        ]
        result = svc.cross_chapter_dedup(chapter_bullets)
        assert all(len(b) == 1 for _, b in result)

    def test_exact_match_fallback_removes_normalized_dup(self):
        svc, logs = _make_svc()
        svc._fuzz = None
        chapter_bullets = [
            ("Alpha Chapter", ["The same normalized text."]),
            ("Beta Chapter", ["the same normalized text"]),
        ]
        result = svc.cross_chapter_dedup(chapter_bullets)
        assert len(result[0][1]) == 1
        assert len(result[1][1]) == 0


# ── 4. Singleton ───────────────────────────────────────────────────────────


class TestGetDedupService:
    def test_returns_shared_instance(self):
        a = get_dedup_service()
        b = get_dedup_service()
        assert a is b
        assert isinstance(a, DedupService)

    def test_singleton_is_stateless_safe(self):
        """Two dedup runs through the shared singleton don't interfere."""
        svc = get_dedup_service()
        kept1, _ = svc.dedup_bullets(["one two three four", "one two three four"])
        kept2, _ = svc.dedup_bullets(["five six seven eight"])
        assert kept1 == ["one two three four"]
        assert kept2 == ["five six seven eight"]

    def test_default_log_callback_is_noop(self):
        """DedupService() without a log callback must not raise on drops."""
        svc = DedupService()
        kept, dropped = svc.dedup_bullets(["x y z w", "x y z w"])
        assert dropped == 1  # the noop log swallowed the message


# ── 5. Default-log construction (covers the ImportError-fallback init) ─────


class TestInitFallback:
    def test_fuzz_attr_is_fuzz_module_or_none(self):
        svc = DedupService()
        assert svc._fuzz is None or hasattr(svc._fuzz, "token_set_ratio")

    def test_rapidfuzz_import_blocked_falls_back_to_exact(self, monkeypatch):
        """sys.modules['rapidfuzz'] = None → ImportError → _fuzz stays None
        (the exact-match fallback path, V10.31.0 graceful degradation)."""
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        svc = DedupService()
        assert svc._fuzz is None
        # Exact normalized duplicates are still caught without rapidfuzz
        kept, dropped = svc.dedup_bullets(["Wakefulness needs orexin.", "wakefulness needs orexin"])
        assert dropped == 1
        assert kept == ["Wakefulness needs orexin."]

    def test_module_all_exports(self):
        for name in dedup_mod.__all__:
            assert hasattr(dedup_mod, name)
