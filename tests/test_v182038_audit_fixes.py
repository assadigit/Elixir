"""V18.20.3.8 — Phase 1 (honesty-layer integrity) tests + the token-cost
dialog button fix.

Every fixture traces to a real defect class found in the V18.20.3.7 SWOT
audit and/or the V18.20.3.7 real-rig run:

- W1: the two hallucination gates (F4 source-overlap, Phase 2.2 semantic
  fact-check) wrapped their whole drop stage in ``except → logger.debug`` —
  a crashed gate silently passed all bullets unfiltered
  (bullet_pipeline.py).
- W2: the recall-floor probes ended in ``except: pass`` (the module's own
  docstring admits this killed the probe in V18.20.3.4), and the 80-bullet
  cap ran AFTER the floor probe, deleting exactly the gap-fill tail the
  floor had just measured (recall_floor.py + summarizer.py).
- W4: the parenthetical-promotion veto failed OPEN silently
  (postcheck_detectors.py), and the generation-time veto passed
  ``source_authors=None`` while ship-time passed the real list
  (summarizer.py) — the two layers of the same veto disagreed.
- W9q: quarantine recovery/audit-trail failures were DEBUG-invisible
  (quarantine.py, quarantine_recovery.py); postchecks' source-author
  extraction failure degraded six detectors at DEBUG (postchecks.py).
- UI: the token-cost dialog's ancestor-level bare ``QWidget { ... }``
  stylesheets overrode the theme's ``QPushButton#Primary`` terracotta CTA
  ("Proceed has no fill color") and the fixed 640px height could clip the
  pinned button bar off-screen at Windows 125–150% DPI scaling
  (token_cost_dialog.py).

All fixes keep the standing rules: honest failure over silent failure,
never raise out of a probe, no behavior change on the happy path.
"""

from __future__ import annotations

import json
import logging
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared fixtures ────────────────────────────────────────────────────────

SRC_KHAN = (
    "Although Winnicott did not use the term identity specifically, his "
    "work provides the developmental basis for (1) authenticity; "
    '(2) "corporeality" (Khan 1983), or a deeply assimilated and '
    "personalized bodily foundation for one's self-experience; and (3) the "
    "experience of temporal continuity in the self."
)

KHAN_BULLET = (
    "Khan's work provides the developmental basis for authenticity, a "
    "deeply assimilated bodily foundation for self-experience termed "
    '"corporeality," and the experience of temporal continuity in the '
    "self."
)


class _FakeQuarantine:
    def __init__(self):
        self.entries = []

    def add(self, *a, **k):
        self.entries.append(k)


def _fake_summarizer(logs):
    return types.SimpleNamespace(
        log=lambda msg, level="INFO": logs.append((level, msg)),
        quarantine=_FakeQuarantine(),
        conservative_drops=False,
        _current_heading="Ch1",
    )


def _make_state(**kw):
    from core.summarisation.bullet_pipeline import PipelineState

    defaults = {
        "heading": "Ch1",
        "content": SRC_KHAN,
        "bullets": [KHAN_BULLET, "Winnicott described the good-enough mother."],
    }
    defaults.update(kw)
    return PipelineState(**defaults)


# ── A. W1: fail-loud hallucination gates ──────────────────────────────────


class TestF4GateFailLoud:
    def test_crash_logs_warning_and_keeps_bullets(self, monkeypatch, caplog):
        """A crashed F4 gate must keep the bullets (fail-open) but log a
        WARNING through the conversion log — never a silent debug."""
        from core.summarisation import bullet_pipeline

        logs = []
        pipeline = bullet_pipeline.BulletPipeline.__new__(bullet_pipeline.BulletPipeline)
        pipeline.s = _fake_summarizer(logs)
        state = _make_state()
        before = list(state.bullets)

        def _boom(*a, **k):
            raise RuntimeError("f4 exploded")

        monkeypatch.setattr(bullet_pipeline, "compute_source_overlap", _boom, raising=False)
        # The stage imports lazily from text_preprocessor — patch there too.
        import core.summarisation.text_preprocessor as _tp

        monkeypatch.setattr(_tp, "compute_source_overlap", _boom)

        with caplog.at_level(logging.WARNING, logger="core.summarisation.bullet_pipeline"):
            pipeline.apply_f4_source_overlap(state)  # must not raise

        assert list(state.bullets) == before  # fail-open keeps bullets
        warnings = [m for lvl, m in logs if lvl == "WARNING"]
        assert any("F4 source-overlap gate CRASHED" in m for m in warnings), logs
        assert any("F4 source-overlap gate crashed" in r.message for r in caplog.records)

    def test_happy_path_unchanged(self, caplog):
        """No crash → identical behaviour to the pre-.3.8 stage (a weak
        bullet is quarantined and dropped)."""
        from core.summarisation import bullet_pipeline

        logs = []
        pipeline = bullet_pipeline.BulletPipeline.__new__(bullet_pipeline.BulletPipeline)
        pipeline.s = _fake_summarizer(logs)
        weak = " utterly unrelated filler content with zero source words "
        state = _make_state(bullets=[weak, "Winnicott described identity."])

        pipeline.apply_f4_source_overlap(state)

        assert weak not in state.bullets
        assert len(pipeline.s.quarantine.entries) == 1


class TestPhase22GateFailLoud:
    def test_crash_logs_warning_and_keeps_bullets(self, monkeypatch, caplog):
        from core.summarisation import bullet_pipeline

        logs = []
        pipeline = bullet_pipeline.BulletPipeline.__new__(bullet_pipeline.BulletPipeline)
        pipeline.s = _fake_summarizer(logs)
        state = _make_state()
        before = list(state.bullets)

        import core.summarisation.text_preprocessor as _tp

        monkeypatch.setattr(
            _tp,
            "semantic_fact_check",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("p22 died")),
        )
        # embedder health check: patch to healthy so the stage proceeds
        import core.llm.model_singletons as _ms

        monkeypatch.setattr(_ms, "is_embedder_healthy", lambda: True)

        with caplog.at_level(logging.WARNING, logger="core.summarisation.bullet_pipeline"):
            pipeline.apply_phase22_semantic_fact_check(state)  # must not raise

        assert list(state.bullets) == before
        warnings = [m for lvl, m in logs if lvl == "WARNING"]
        assert any("Phase 2.2 semantic fact-check CRASHED" in m for m in warnings), logs

    def test_overlap_failure_marks_quarantine_reason(self, monkeypatch, caplog):
        """When the genuine-overlap recompute fails, the quarantine entry's
        reason must SAY the value is degraded (recovery eligibility)."""
        import core.summarisation.text_preprocessor as _tp
        from core.summarisation import bullet_pipeline  # noqa: E402

        logs = []
        pipeline = bullet_pipeline.BulletPipeline.__new__(bullet_pipeline.BulletPipeline)
        pipeline.s = _fake_summarizer(logs)

        real_overlap = _tp.compute_source_overlap
        monkeypatch.setattr(
            _tp,
            "semantic_fact_check",
            lambda bp, content, threshold=0.5: {
                "is_grounded": False,
                "best_similarity": 0.4,
            },
        )
        monkeypatch.setattr(
            _tp,
            "compute_source_overlap",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("overlap died")),
        )
        import core.llm.model_singletons as _ms

        monkeypatch.setattr(_ms, "is_embedder_healthy", lambda: True)

        state = _make_state(bullets=[KHAN_BULLET])
        with caplog.at_level(logging.WARNING, logger="core.summarisation.bullet_pipeline"):
            pipeline.apply_phase22_semantic_fact_check(state)

        assert pipeline.s.quarantine.entries, "bullet must be quarantined"
        reason = pipeline.s.quarantine.entries[0]["reason"]
        assert "COMPUTATION FAILED" in reason, reason
        assert any("genuine-overlap computation failed" in r.message for r in caplog.records)
        # sanity: the non-failure path does NOT carry the marker
        monkeypatch.setattr(_tp, "compute_source_overlap", real_overlap)
        pipeline.s.quarantine.entries.clear()
        state2 = _make_state(bullets=[KHAN_BULLET])
        pipeline.apply_phase22_semantic_fact_check(state2)
        assert pipeline.s.quarantine.entries, "sanity pass must quarantine too"
        assert "COMPUTATION FAILED" not in pipeline.s.quarantine.entries[0]["reason"]


# ── B. W4: veto visibility + parity ───────────────────────────────────────


class TestVetoFailOpenVisible:
    def test_crash_returns_none_and_warns(self, monkeypatch, caplog):
        # V0.18 (Phase 5.2): the detectors moved verbatim into the postchecks
        # package — patch the DEFINING module, not the re-export facade.
        from core.summarisation import postcheck_detectors as pd
        from core.summarisation.postchecks import attribution as _attr

        def _boom(bullet):
            raise RuntimeError("parser exploded")

        monkeypatch.setattr(_attr, "_parse_bullet_subject", _boom)
        with caplog.at_level(logging.WARNING, logger="core.summarisation.postcheck_detectors"):
            result = pd.detect_parenthetical_promotion(KHAN_BULLET, SRC_KHAN, ["Winnicott", "Khan"])
        assert result is None  # fail-open decision preserved
        assert any("veto CRASHED" in r.message for r in caplog.records), (
            "a crashed veto must log at WARNING"
        )

    def test_khan_bullet_still_vetoed_when_healthy(self):
        """Regression guard: the .3.5 three-form parser still catches the
        possessive Khan misattribution (the .3.4 rig defect)."""
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        result = detect_parenthetical_promotion(KHAN_BULLET, SRC_KHAN, None)
        assert result is not None
        claimed, real = result
        assert claimed == "Khan"
        assert real == "Winnicott"


class TestGenerationTimeVetoParity:
    def test_gap_fill_veto_receives_source_authors(self):
        """Wiring policy: the generation-time veto call must pass
        ``_det_authors`` (the citation-extracted author list), not None —
        parity with the ship-time check (postchecks.py passes
        source_authors).

        V18.20.3.12 (Phase 4 / W6-O5): the gap-fill loop moved VERBATIM from
        ``Summarizer._summarize_inner`` to ``gap_fill_batch.batch_gap_fill``
        (where the veto call now passes ``det_authors``) — re-pointed at the
        new module; the pinned wiring is unchanged."""
        src = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "gap_fill_batch.py"
        ).read_text(encoding="utf-8")
        # Locate the generation-time veto call inside the gap-fill section.
        gap_fill_start = src.index("Batch gap-fill round {")
        veto_call_idx = src.index("detect_parenthetical_promotion(", gap_fill_start)
        snippet = src[veto_call_idx : veto_call_idx + 2400]
        assert "det_authors," in snippet, (
            "generation-time veto must pass the citation-extracted author list"
        )
        # The old form (None as the third positional arg) must be gone.
        assert (
            "content,\n                                                        None," not in snippet
        )


class TestPostchecksAuthorExtractionVisible:
    def test_extraction_failure_warns(self, monkeypatch, caplog):
        """A source-author extraction failure degrades six detectors — it
        must WARN, not logger.debug."""
        import core.preprocessing.deterministic_analyzer as da
        from core.summarisation.postchecks import run_post_checks

        def _boom(text):
            raise RuntimeError("citation extractor died")

        monkeypatch.setattr(da, "extract_citations", _boom)
        with caplog.at_level(logging.WARNING, logger="core.summarisation.postchecks"):
            report = run_post_checks(
                ["Erikson (1956) defined ego identity."],
                "Erikson defined ego identity.",
                "Erikson defined ego identity.",
                source_text="Erikson (1956) used the term ego identity.",
            )
        assert report is not None  # did not raise
        assert any("source-author extraction failed" in r.message for r in caplog.records), (
            "must log at WARNING"
        )


# ── C. W2: recall-floor integrity ─────────────────────────────────────────


class TestRecallFloorProbeVisibility:
    ANALYSIS = (
        "## Citations\n\n1. **Erikson** (12 mentions): 1950, 1956, 1958\n"
        "2. **Winnicott** (4 mentions): 1949, 1960\n"
    )

    def test_theorist_probe_failure_visible(self, monkeypatch, caplog):
        import core.preprocessing.deterministic_analyzer as da
        from core.summarisation import recall_floor

        monkeypatch.setattr(
            da,
            "check_coverage",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cov died")),
        )
        with caplog.at_level(logging.WARNING, logger=recall_floor.__name__):
            rf = recall_floor.deterministic_recall_floor(
                self.ANALYSIS, ["Erikson bullet"], "", "source"
            )
        assert rf["theorists_probe_failed"] is True
        assert any("theorists probe FAILED" in p for p in rf["log_parts"]), rf
        assert any("theorist probe failed" in r.message for r in caplog.records)

    def test_conclusion_probe_failure_visible(self, monkeypatch, caplog):
        import core.summarisation.post_processing as pp
        from core.summarisation import recall_floor

        monkeypatch.setattr(
            pp,
            "detect_enumerated_conclusions",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("concl died")),
        )
        with caplog.at_level(logging.WARNING, logger=recall_floor.__name__):
            rf = recall_floor.deterministic_recall_floor(
                self.ANALYSIS, ["Erikson bullet"], "", "source"
            )
        assert rf["conclusion_items_probe_failed"] is True
        assert any("conclusion-items probe FAILED" in p for p in rf["log_parts"])
        assert any("conclusion-item probe failed" in r.message for r in caplog.records)

    def test_healthy_probe_still_reports_numbers(self):
        from core.summarisation.recall_floor import deterministic_recall_floor

        rf = deterministic_recall_floor(
            self.ANALYSIS,
            ["Erikson (1956) defined ego identity as persistent sameness."],
            "",
            "",
        )
        assert rf["theorists_probe_failed"] is False
        assert rf["theorists_total"] == 2
        assert "Winnicott" in rf["theorists_missing"]


class TestCoverageAwareCap:
    ANALYSIS = (
        "## Citations\n\n1. **Erikson** (12 mentions): 1956\n2. **Winnicott** (4 mentions): 1960\n"
    )

    def _bullets(self, n, extra=()):
        return [
            f"Erikson ({1956 + (i % 3)}) bullet number {i} about identity." for i in range(n)
        ] + list(extra)

    def test_noop_under_limit(self):
        from core.summarisation.recall_floor import coverage_aware_cap

        bullets = self._bullets(5)
        logs = []
        out = coverage_aware_cap(
            bullets, self.ANALYSIS, limit=80, log_fn=lambda m, level="WARNING": logs.append(m)
        )
        assert out == bullets
        assert not logs

    def test_plain_headcap_without_analysis(self):
        from core.summarisation.recall_floor import coverage_aware_cap

        bullets = self._bullets(100)
        logs = []
        out = coverage_aware_cap(
            bullets, "", limit=80, log_fn=lambda m, level="WARNING": logs.append(m)
        )
        assert out == bullets[:80]
        assert any("no deterministic analysis" in m for m in logs), logs

    def test_sole_cover_tail_bullet_is_rescued(self):
        """The W2b defect shape: a gap-fill tail bullet is the ONLY cover of
        an author; the plain head-cap would delete exactly it."""
        from core.preprocessing.deterministic_analyzer import check_coverage
        from core.summarisation.recall_floor import coverage_aware_cap

        tail = (
            "Winnicott (1960) described the good-enough mother meeting "
            "the infant's omnipotence so the true self develops."
        )
        bullets = self._bullets(85, extra=[tail])  # 85 Erikson + 1 Winnicott
        assert len(bullets) == 86
        logs = []
        out = coverage_aware_cap(
            bullets, self.ANALYSIS, limit=80, log_fn=lambda m, level="WARNING": logs.append(m)
        )
        assert len(out) == 80
        # The sole Winnicott bullet must survive…
        assert any("Winnicott" in b for b in out), (
            "the sole cover of an author must not be cut while redundant Erikson bullets survive"
        )
        # …and the floor measured on the capped set stays complete.
        cov = check_coverage(self.ANALYSIS, " ".join(out))
        assert cov["missing"] == [], cov
        assert any("cap rescue" in m for m in logs), logs

    def test_probe_failure_degrades_to_plain_headcap(self, monkeypatch, caplog):
        import core.preprocessing.deterministic_analyzer as da
        from core.summarisation import recall_floor

        monkeypatch.setattr(
            da,
            "check_coverage",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cap probe died")),
        )
        bullets = self._bullets(100)
        logs = []
        with caplog.at_level(logging.WARNING, logger=recall_floor.__name__):
            out = recall_floor.coverage_aware_cap(
                bullets,
                self.ANALYSIS,
                limit=80,
                log_fn=lambda m, level="WARNING": logs.append(m),
            )
        assert out == bullets[:80]
        assert any("coverage-aware cap probe failed" in m for m in logs)

    def test_never_raises_on_hostile_input(self):
        from core.summarisation.recall_floor import coverage_aware_cap

        assert coverage_aware_cap(None, "", limit=80) == []
        assert coverage_aware_cap([], self.ANALYSIS) == []


class TestCapBeforeFloorOrdering:
    def test_cap_runs_before_floor_probe(self):
        """Wiring policy: in _summarize_inner the coverage_aware_cap call
        must appear BEFORE the deterministic_recall_floor call — the floor
        measures the SHIPPED (post-cap) set."""
        src = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "summarizer.py"
        ).read_text(encoding="utf-8")
        tail = src[src.index("def _summarize_inner") :]
        cap_idx = tail.index("coverage_aware_cap(")
        floor_idx = tail.index("deterministic_recall_floor(")
        assert cap_idx < floor_idx, "the 80-bullet cap must run BEFORE the recall-floor probe"


# ── D. W9q: quarantine visibility ─────────────────────────────────────────


class TestQuarantineVisibility:
    def test_drops_jsonl_partial_corruption_salvages_and_warns(
        self,
        tmp_path,
        caplog,
    ):
        from core.summarisation.quarantine import QuarantineLog

        p = tmp_path / "logs" / "drops.jsonl"
        p.parent.mkdir(parents=True)
        good1 = json.dumps({"bullet": "b1", "stage": "F4_source_overlap"})
        good2 = json.dumps({"bullet": "b2", "stage": "F4_source_overlap"})
        p.write_text(good1 + "\n{corrupt line\n" + good2 + "\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="core.summarisation.quarantine"):
            entries = QuarantineLog.load_from_disk(p)
        assert len(entries) == 2  # salvage, never all-or-nothing
        assert any("unreadable" in r.message for r in caplog.records)

    def test_drops_jsonl_fully_unreadable_warns(self, tmp_path, caplog):
        from core.summarisation.quarantine import QuarantineLog

        p = tmp_path / "logs" / "drops.jsonl"
        p.parent.mkdir(parents=True)
        # Valid lines first, then unreadable bytes → the read itself raises.
        p.write_bytes(json.dumps({"bullet": "b1"}).encode("utf-8") + b"\n" + b"\xff\xfe\x00")
        with caplog.at_level(logging.WARNING, logger="core.summarisation.quarantine"):
            entries = QuarantineLog.load_from_disk(p)
        assert isinstance(entries, list)
        assert any("unreadable" in r.message for r in caplog.records)

    def test_recovery_recompute_failure_warns(self, tmp_path, monkeypatch, caplog):
        """A fresh-overlap recompute failure keeps the stale value (correct)
        but must WARN (new in .3.8)."""
        from core.summarisation.quarantine import QuarantineLog

        q = QuarantineLog(tmp_path)
        q.add(
            "Winnicott described the good-enough mother and the true self.",
            stage="F4_source_overlap",
            threshold=0.25,
            source_overlap=0.55,
            reason="test",
            chapter="Ch1",
            actually_dropped=True,
        )
        import core.summarisation.text_preprocessor as _tp

        monkeypatch.setattr(
            _tp,
            "compute_source_overlap",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("recompute died")),
        )
        with caplog.at_level(logging.WARNING, logger="core.summarisation.quarantine"):
            resurrected = q.recover(source_text=SRC_KHAN)
        # stale 0.55 > 0.30 threshold → still resurrected (fail-safe value)
        assert len(resurrected) == 1
        assert any("recompute failed" in r.message for r in caplog.records)

    def test_recovery_pass_crash_is_visible(self, caplog):
        """recover_quarantined with a crashed quarantine.recover must log a
        WARNING through BOTH the module logger and the conversion log."""
        from core.summarisation import quarantine_recovery

        logs = []

        class _CrashingQuarantine:
            def recover(self, source_text=""):
                raise RuntimeError("quarantine exploded")

        bullets = ["safe bullet"]
        with caplog.at_level(logging.WARNING, logger="core.summarisation.quarantine_recovery"):
            out = quarantine_recovery.recover_quarantined(
                bullets=bullets,
                source_text=SRC_KHAN,
                quarantine=_CrashingQuarantine(),
                log=lambda msg, level="INFO": logs.append((level, msg)),
            )
        assert out == bullets  # non-fatal: bullets unchanged
        assert any("CRASHED" in m for lvl, m in logs if lvl == "WARNING"), logs
        assert any("recovery pass crashed" in r.message for r in caplog.records)


# ── E. UI: token-cost dialog button fix ───────────────────────────────────


class TestTokenCostDialogPolicy:
    """Source-level policy test (no Qt needed): the dialog must not set any
    bare ``QWidget { ... }`` stylesheet — widget-level stylesheets take
    precedence over the application stylesheet, and a bare QWidget selector
    matches every descendant, killing the theme's QPushButton#Primary CTA
    (the "Proceed has no fill color" rig report)."""

    def test_no_bare_qwidget_selectors(self):
        src = (
            Path(__file__).resolve().parent.parent / "ui_qt" / "views" / "token_cost_dialog.py"
        ).read_text(encoding="utf-8")
        assert '"QWidget {' not in src, (
            "bare QWidget selectors in a container stylesheet override the "
            "theme's button CTA styling for all descendants"
        )
        assert "QWidget#CostDialogContent" in src
        assert "QWidget#CostDialogBtnBar" in src

    def test_screen_aware_height_cap_present(self):
        src = (
            Path(__file__).resolve().parent.parent / "ui_qt" / "views" / "token_cost_dialog.py"
        ).read_text(encoding="utf-8")
        assert "_apply_size_caps" in src
        assert "availableGeometry" in src
        assert (
            "setFixedSize" not in src.replace("setFixedSize(self._DLG_WIDTH, self._DLG_HEIGHT)", "")
            or "self.setFixedSize" not in src
        )


def _qt_available() -> bool:
    try:
        os_env = __import__("os").environ
        os_env.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTokenCostDialogBehaviour:
    """Widget-level tests (offscreen). Skipped gracefully in headless
    environments without PySide6 — the policy tests above still run."""

    @pytest.fixture(scope="class")
    def app(self):
        from PySide6.QtWidgets import QApplication

        inst = QApplication.instance() or QApplication([])
        yield inst

    def _load_dialog_class(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "token_cost_dialog_under_test",
            Path(__file__).resolve().parent.parent / "ui_qt" / "views" / "token_cost_dialog.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.TokenCostDialog

    def test_buttons_keep_theme_cta(self, app):
        from PySide6.QtWidgets import QPushButton, QWidget

        TokenCostDialog = self._load_dialog_class()
        dlg = TokenCostDialog({"total_tokens": 123456, "pdf_pages": 397})
        btns = {b.text(): b for b in dlg.findChildren(QPushButton)}
        assert "✅ Proceed" in btns and "Cancel" in btns
        assert btns["✅ Proceed"].objectName() == "Primary"
        assert btns["Cancel"].objectName() == "Secondary"
        assert btns["✅ Proceed"].isDefault()  # Enter proceeds
        # No ancestor stylesheet pollution: every container stylesheet must
        # be objectName-scoped (no bare QWidget selectors).
        for w in dlg.findChildren(QWidget):
            ss = w.styleSheet() or ""
            assert "QWidget {" not in ss and "QWidget{" not in ss, (
                f"bare QWidget selector on {w.objectName()!r}: {ss[:60]}"
            )

    def test_height_capped_between_min_and_preferred(self, app):
        TokenCostDialog = self._load_dialog_class()
        dlg = TokenCostDialog({"total_tokens": 123456, "pdf_pages": 397})
        assert dlg.width() == TokenCostDialog._DLG_WIDTH
        assert TokenCostDialog._DLG_MIN_HEIGHT <= dlg.height() <= TokenCostDialog._DLG_HEIGHT

    def test_buttons_have_matching_heights(self, app):
        from PySide6.QtWidgets import QPushButton

        TokenCostDialog = self._load_dialog_class()
        dlg = TokenCostDialog({"total_tokens": 123456, "pdf_pages": 397})
        btns = {b.text(): b for b in dlg.findChildren(QPushButton)}
        assert btns["✅ Proceed"].minimumHeight() >= 36
        assert btns["Cancel"].minimumHeight() >= 36
