"""V0.6.2 — the two user-reported bugs, defect-driven.

USER REPORT (verbatim, abridged):

  1. "I tried a book (which lasted for around 2 hour and 40 minutes),
     after a while the elapsed time was buggy and was showing something
     like this -21:34:45 (a wrong and misleading number with a negative)."

  2. "I tried a book, which had 1-2 page chapters. and the exec summary
     + bullet point + thorough summary risen above the original source
     word count!, also caused lots of repetitive bullets - which were
     rephrased the same concepts in few bullets with minor
     hallucinations. So we need to make sure it doesn't happen for BOOKS
     that have THIN CONTENT, or THIN CHAPTERS."

BUG 1 — the negative elapsed timer (ui_qt/views/wizard_view.py).
  Root cause (reproduced live on this rig with a fake clock): the Step-9
  elapsed label is driven by ``QTime.currentTime()`` + ``secsTo``.
  ``QTime`` is a TIME-OF-DAY type with no day tracking: a conversion that
  crosses midnight makes ``secsTo`` return a negative value in
  [-86400, 0), which the floor-division formatter renders as a misleading
  ``-HH:MM:SS`` (empirically: start 23:34:45 → now 02:00:00 renders
  "-22:25:15"; the user's "-21:34:45" is the same family). A >24h run
  wraps modulo 24h and silently resets. THE FIX: a monotonic clock
  (``time.monotonic()``) — negative-impossible, wrap-impossible.

BUG 2 — thin-chapter over-generation (core/summarisation/length_policy.py
  + coverage_guarantee.py + bullet_pipeline.py).
  Root causes (all in the thin regime, W < 800 — the 97-Things/small-source
  boundary the policy already uses):

  * ``thorough_target``: the ``THOROUGH_SMALL_SOURCE`` (120) floor is
    taken inside the max WITHOUT being capped by the 45% fraction — for
    W=150 the hi target is 120 words = 80% of the source; for W=100 it is
    100 words = 100% of the source. The module's own docstring promises
    "at most ~45% of the source"; the code breaks that promise for thin
    chapters and instructs the model to restate (then pad —
    hallucination-by-instruction).
  * ``executive_target``: same defect — the ``EXEC_SMALL_SOURCE`` (60)
    floor pushes a 100-word chapter's exec target to 60 words = 60% of
    the source.
  * ``bullet_cap`` returns 0 ("no cap") for EVERY chapter (the V0.4.23
    directive). The cap only ever bounds the ADDITIVE machinery (Tier-2
    gap-fill, scholar gap-fill, quarantine resurrection) — never primary
    bullets — so restoring it for the thin regime bounds the exact
    machinery that padded the user's thin book, while normal chapters
    keep the no-cap directive.
  * The bullet prompt phrase for thin chapters is "at least N — there is
    NO MAXIMUM" — an explicit invitation to rephrase the same concepts
    into more bullets when the chapter has fewer distinct ideas than N.
  * No COMBINED budget: the three section targets structurally sum to
    ~115% of a thin chapter's words (exec 20% + thorough 45% + bullets
    ~50%); nothing states or measures the combined ratio (the user's
    headline number).
  * Tier-2 gap-fill insertions are checked for EXACT duplicates only
    (``bp_str not in result['bullet_points']``) — a rephrased near-dup
    of an existing bullet is appended unconditionally (the user's
    "repetitive bullets which rephrased the same concepts").

THE FIXES (content-agnostic, thin-scoped — the V18 richness contract for
normal chapters is untouched):
  * the small-source floors may never push a target past its source
    fraction (the fraction is the TRUE cap);
  * the lo floors stop forcing point-targets on tiny sources;
  * ``bullet_cap`` is two-regime: the source-scaled ADDITIVE budget for
    thin chapters (the V0.06 rig-audit F4-b semantics), 0 for normal;
  * the thin bullet phrase is a bounded range + a one-distinct-idea
    rule; the thin budget block states the COMBINED budget;
  * ``expansion_audit`` measures the combined ratio (thin-scoped) and F1
    passes the bullet words in + logs them;
  * Tier-2 insertions pass the within-chapter near-duplicate guard
    (DedupService, token_set_ratio ≥ 75) before appending.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent


# ── Qt availability gate (the elapsed-timer tests construct a QLabel) ──────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


# ═══════════════════════════════════════════════════════════════════════════
# BUG 1 — the elapsed timer (view-level drives, dual-seam fakes)
# ═══════════════════════════════════════════════════════════════════════════
#
# The drive patches BOTH clock seams at once:
#   * ``PySide6.QtCore.QTime`` — the PRE-FIX implementation reads it via
#     function-local imports;
#   * ``ui_qt.views.wizard_view.time`` — the POST-FIX implementation reads
#     the module-level ``time`` import.
# Both fakes tell the SAME wall-clock story (the QTime one faithfully —
# secsTo is negative across midnight, no day tracking), so the drive works
# identically before and after the fix: pre-fix it produces the bug,
# post-fix the honest elapsed time.


class _FakeQTimer:
    """Signal-less QTimer stand-in (safe to parent on a bare widget)."""

    def __init__(self, parent=None):  # noqa: ARG002 (parent unused)
        self._parent = parent

    def start(self, ms: int) -> None:  # noqa: ARG002
        pass

    def stop(self) -> None:
        pass

    def deleteLater(self) -> None:
        pass

    timeout = SimpleNamespace(connect=lambda fn: None)


class _FakeQTime:
    """Faithful ``QTime`` stand-in: time-of-day ONLY, no day tracking.

    ``secsTo`` reproduces the C++ semantics verified live on this rig
    (QTime(23,34,45).secsTo(QTime(2,0,0)) == -77685 — NEGATIVE across
    midnight, no wrap; a >24h span collapses to the same-day residue).
    """

    _clock = {"secs": 0}

    def __init__(self, secs_of_day: int):
        self._s = int(secs_of_day) % 86400

    @staticmethod
    def currentTime() -> _FakeQTime:
        return _FakeQTime(_FakeQTime._clock["secs"])

    def secsTo(self, other: _FakeQTime) -> int:
        return other._s - self._s


def _drive_elapsed(
    monkeypatch,
    start_secs_of_day: int,
    elapsed_seconds: int,
):
    """Start the wizard's elapsed timer, advance both fake clocks by
    ``elapsed_seconds``, tick once, and return the view."""
    _app()
    from PySide6.QtWidgets import QLabel

    import ui_qt.views.wizard_view as wv

    _FakeQTime._clock["secs"] = int(start_secs_of_day)
    _mono = {"t": 1000.0}

    monkeypatch.setattr("PySide6.QtCore.QTime", _FakeQTime)
    monkeypatch.setattr("PySide6.QtCore.QTimer", _FakeQTimer)
    monkeypatch.setattr(wv, "time", SimpleNamespace(monotonic=lambda: _mono["t"]))

    view = wv.WizardView.__new__(wv.WizardView)  # no __init__ (controller deps)
    view.step9 = SimpleNamespace(elapsed_label=QLabel())
    view._start_elapsed_timer()

    # advance: the QTime clock wraps modulo 24h like the real one; the
    # monotonic clock does not.
    _FakeQTime._clock["secs"] = (int(start_secs_of_day) + elapsed_seconds) % 86400
    _mono["t"] = 1000.0 + elapsed_seconds
    view._update_elapsed()
    return view


@pytest.mark.skipif(not _qt_available(), reason="PySide6 unavailable")
class TestElapsedTimer:
    def test_midnight_crossing_shows_positive_elapsed(self, monkeypatch):
        """THE USER'S CASE: a conversion started at 23:34:45, viewed at
        02:00:00 (2h25m15s real elapsed). Pre-fix the label renders a
        misleading negative (the QTime secsTo floor-division distortion —
        "-22:25:15" on this exact clock; the user's "-21:34:45" is the
        same family). Post-fix: "⏱️ Elapsed: 02:25:15"."""
        view = _drive_elapsed(monkeypatch, 23 * 3600 + 34 * 60 + 45, 2 * 3600 + 25 * 60 + 15)
        text = view.step9.elapsed_label.text()
        assert text == "⏱️ Elapsed: 02:25:15", f"got {text!r}"

    def test_label_is_never_negative_across_midnight_sweep(self, monkeypatch):
        """For EVERY start time near midnight and every elapsed span up to
        10 hours, the label must never start with '-' (the sign is the
        defect — any negative rendering is a wrong, misleading number)."""
        for start in (22 * 3600, 23 * 3600, 23 * 3600 + 59 * 60 + 59):
            for span in (1, 60, 3600, 5 * 3600, 10 * 3600):
                view = _drive_elapsed(monkeypatch, start, span)
                text = view.step9.elapsed_label.text()
                assert not text.startswith("-"), f"start={start}s span={span}s rendered {text!r}"

    def test_over_24h_run_keeps_counting(self, monkeypatch):
        """A >24h conversion (marathon runs happen — the user's was 2h40m
        on a thin book with many chapters) must not wrap modulo 24h:
        25h elapsed renders "25:00:00", not "01:00:00"."""
        view = _drive_elapsed(monkeypatch, 0, 25 * 3600)
        text = view.step9.elapsed_label.text()
        assert text == "⏱️ Elapsed: 25:00:00", f"got {text!r}"

    def test_clock_skew_never_renders_negative(self, monkeypatch):
        """A monotonic clock can only move forward, but the formatter must
        also be robust to a skew/backwards reading (clamp to zero, never
        render a negative duration)."""
        _app()
        from PySide6.QtWidgets import QLabel

        import ui_qt.views.wizard_view as wv

        monkeypatch.setattr("PySide6.QtCore.QTime", _FakeQTime)
        monkeypatch.setattr("PySide6.QtCore.QTimer", _FakeQTimer)
        _t = {"t": 5000.0}
        monkeypatch.setattr(wv, "time", SimpleNamespace(monotonic=lambda: _t["t"]))

        view = wv.WizardView.__new__(wv.WizardView)
        view.step9 = SimpleNamespace(elapsed_label=QLabel())
        view._start_elapsed_timer()
        _t["t"] = 4000.0  # skew: clock reads backwards
        view._update_elapsed()
        text = view.step9.elapsed_label.text()
        assert text == "⏱️ Elapsed: 00:00:00", f"got {text!r}"

    def test_timer_restarts_on_new_conversion(self, monkeypatch):
        """A second conversion in the same wizard session restarts the
        clock (a stale start from the previous run must not leak)."""
        _app()
        from PySide6.QtWidgets import QLabel

        import ui_qt.views.wizard_view as wv

        monkeypatch.setattr("PySide6.QtCore.QTime", _FakeQTime)
        monkeypatch.setattr("PySide6.QtCore.QTimer", _FakeQTimer)
        _t = {"t": 1000.0}
        monkeypatch.setattr(wv, "time", SimpleNamespace(monotonic=lambda: _t["t"]))

        view = wv.WizardView.__new__(wv.WizardView)
        view.step9 = SimpleNamespace(elapsed_label=QLabel())
        view._start_elapsed_timer()
        _t["t"] += 3600.0
        view._update_elapsed()
        assert view.step9.elapsed_label.text() == "⏱️ Elapsed: 01:00:00"

        # second conversion: restart
        view._start_elapsed_timer()
        _t["t"] += 90.0
        view._update_elapsed()
        assert view.step9.elapsed_label.text() == "⏱️ Elapsed: 00:01:30", (
            view.step9.elapsed_label.text()
        )


# ═══════════════════════════════════════════════════════════════════════════
# BUG 2, L1 — the thin-source length policy (pure functions)
# ═══════════════════════════════════════════════════════════════════════════


class TestThinThoroughFloorCappedByFraction:
    """The 120-word small-source floor may never push a thin chapter's
    thorough target past the 45% fraction (the module's own "at most ~45%
    of the source" contract)."""

    def test_very_thin_sources_get_fraction_targets(self):
        from core.summarisation.length_policy import thorough_target

        cases = {
            100: (27, 45),  # was (80, 100) — 100% of the source!
            150: (41, 68),  # was (80, 120) — 80% of the source
            200: (80, 90),  # was (80, 120) — 60% of the source
            250: (80, 112),  # was (80, 120)
        }
        for w, (lo_exp, hi_exp) in cases.items():
            lo, hi = thorough_target(w)
            assert (lo, hi) == (lo_exp, hi_exp), (
                f"W={w}: expected ({lo_exp}, {hi_exp}), got ({lo}, {hi})"
            )

    def test_thin_targets_never_exceed_the_fraction(self):
        from core.summarisation.length_policy import (
            THOROUGH_SOURCE_FRACTION,
            thorough_target,
        )

        for w in range(20, 800, 13):
            _lo, hi = thorough_target(w)
            assert hi <= round(THOROUGH_SOURCE_FRACTION * w), (
                f"W={w}: thorough hi {hi} exceeds the 45% fraction"
            )
            assert hi <= w, f"W={w}: never above the source"

    def test_no_point_targets_on_tiny_sources(self):
        """The 80-word lo floor must not collapse a sub-80 hi into a
        point target ("68-68 word" forces a minimum the source cannot
        honestly support)."""
        from core.summarisation.length_policy import thorough_target

        for w in (60, 100, 150):
            lo, hi = thorough_target(w)
            assert lo < hi, f"W={w}: point target ({lo}, {hi}) forces padding"

    def test_medium_small_sources_unchanged(self):
        """W >= 267 (where 0.45W >= 120): the floor is already inert —
        byte-identical targets (the V0.05/V0.07 rig contracts)."""
        from core.summarisation.length_policy import thorough_target

        cases = {300: (81, 135), 340: (92, 153), 441: (119, 198)}
        for w, (lo_exp, hi_exp) in cases.items():
            assert thorough_target(w) == (lo_exp, hi_exp), w

    def test_normal_regime_unchanged(self):
        from core.summarisation.length_policy import thorough_target

        cases = {
            800: (480, 800),
            1000: (480, 800),
            1780: (481, 801),
            3000: (810, 1350),
            10000: (2700, 4500),
        }
        for w, expected in cases.items():
            assert thorough_target(w) == expected, w


class TestThinExecFloorCappedByFraction:
    """The 60-word exec floor may never push a thin chapter's exec target
    past the 20% fraction (was: 60 words = 60% of a 100-word chapter)."""

    def test_very_thin_sources_get_fraction_targets(self):
        from core.summarisation.length_policy import executive_target

        cases = {
            100: (12, 20),  # was (40, 60) — 60% of the source
            150: (18, 30),  # was (40, 60) — 40% of the source
            250: (40, 50),  # was (40, 60) — 24% of the source
        }
        for w, (lo_exp, hi_exp) in cases.items():
            assert executive_target(w) == (lo_exp, hi_exp), (
                f"W={w}: expected ({lo_exp}, {hi_exp}), got {executive_target(w)}"
            )

    def test_medium_sources_unchanged(self):
        from core.summarisation.length_policy import executive_target

        assert executive_target(300) == (40, 60)
        assert executive_target(340) == (41, 68)
        assert executive_target(3000) == (150, 250)

    def test_no_point_targets_on_tiny_sources(self):
        from core.summarisation.length_policy import executive_target

        for w in (50, 100, 150):
            lo, hi = executive_target(w)
            assert lo < hi, f"W={w}: point target ({lo}, {hi}) forces padding"


class TestBulletCapTwoRegimes:
    """``bullet_cap`` is the ADDITIVE budget (Tier-2/scholar gap-fill +
    quarantine resurrection — never primary bullets). Thin chapters get
    the source-scaled budget back (the V0.06 rig-audit F4-b semantics);
    normal chapters keep the V0.4.23 no-cap directive (0)."""

    def test_thin_sources_get_the_scaled_budget(self):
        from core.summarisation.length_policy import bullet_cap, bullet_target

        # the V0.06 rig chapter sizes — the historical 14/14/18/18/16
        for w, expected in ((344, 14), (358, 14), (439, 18), (445, 18), (412, 16)):
            assert bullet_cap(w) == expected, f"W={w}: expected {expected}"
            assert bullet_cap(w) == bullet_target(w)[1], w

        for w in (50, 150, 250, 340, 441, 600, 799):
            assert bullet_cap(w) == bullet_target(w)[1] > 0, w

    def test_normal_sources_stay_uncapped(self):
        from core.summarisation.length_policy import bullet_cap

        for w in (800, 1000, 3000, 12000, 100000):
            assert bullet_cap(w) == 0, f"W={w}: the no-cap directive must hold"


class TestThinBulletPhraseBounded:
    def test_thin_phrase_is_a_bounded_range(self):
        from core.summarisation.length_policy import bullet_range_phrase

        phrase = bullet_range_phrase(340)
        assert phrase == "9-14", phrase  # bounded, not "at least 9"

    def test_normal_phrase_is_the_floor(self):
        from core.summarisation.length_policy import bullet_range_phrase

        assert bullet_range_phrase(1000) == "at least 27"
        assert bullet_range_phrase(20000) == "at least 27"  # lo of the 27-40 window


class TestThinBudgetBlock:
    def test_thin_block_states_combined_budget_and_distinct_idea_rule(self):
        from core.summarisation.length_policy import length_budget_block

        block = length_budget_block(340, True, True, True)
        assert "approximately 340 words" in block
        assert "COMBINED BUDGET" in block, "the combined budget line is missing"
        # the bullet line is bounded for thin sources
        assert "9-14 bullets" in block, block
        assert "NO MAXIMUM" not in block, "thin chapters must not be told NO MAXIMUM"
        # the anti-repetition contract (the user's repetitive bullets)
        assert "DISTINCT" in block and "rephras" in block.lower(), block

    def test_normal_block_keeps_no_maximum(self):
        from core.summarisation.length_policy import length_budget_block

        block = length_budget_block(1000, True, True, True)
        assert "NO MAXIMUM" in block
        assert "at least 27 bullets" in block
        assert "COMBINED BUDGET" not in block
        assert "COMPRESSION CONTRACT" in block


class TestExpansionAuditCombined:
    def test_combined_overgeneration_is_flagged_for_thin_sources(self):
        """THE USER'S HEADLINE NUMBER: exec 60 + bullets 120 + thorough 140
        = 320 words against a 300-word chapter = 1.1x the source."""
        from core.summarisation.length_policy import expansion_audit

        findings = expansion_audit(300, 60, 140, bullet_words=120)
        assert any("combined" in f and "1.1x" in f for f in findings), findings

    def test_combined_within_budget_is_silent(self):
        from core.summarisation.length_policy import expansion_audit

        assert expansion_audit(300, 50, 100, bullet_words=60) == []
        assert expansion_audit(340, 68, 153, bullet_words=80) == []

    def test_combined_check_is_thin_scoped(self):
        """Normal chapters keep the V18 richness contract (combined may
        legitimately exceed the source there) — no combined finding."""
        from core.summarisation.length_policy import expansion_audit

        findings = expansion_audit(1000, 200, 450, bullet_words=500)
        assert not any("combined" in f for f in findings), findings

    def test_per_section_findings_survive(self):
        from core.summarisation.length_policy import expansion_audit

        findings = expansion_audit(408, 180, 911)
        assert any("2.2x" in f for f in findings), findings
        assert expansion_audit(408, 60, 160) == []

    def test_three_arg_call_still_works(self):
        from core.summarisation.length_policy import expansion_audit

        assert expansion_audit(408, 60, 160) == expansion_audit(408, 60, 160, bullet_words=0)


# ═══════════════════════════════════════════════════════════════════════════
# BUG 2, L2 — Tier-2 gap-fill near-duplicate insertion guard
# ═══════════════════════════════════════════════════════════════════════════


def _run_tier2(monkeypatch, existing, new_bullets, *, bullet_cap=0):
    """Drive apply_3tier_coverage with a gap-fill that returns
    ``new_bullets``; return (result, logs)."""
    from core.summarisation.coverage_guarantee import apply_3tier_coverage

    result = {
        "executive_summary": "E",
        "bullet_points": list(existing),
        "thorough_summary": "T",
    }
    logs: list[str] = []

    apply_3tier_coverage(
        "H",
        "src text",
        "content text",
        result,
        0.4,
        coverage_threshold=0.85,
        extract_keywords=lambda c, n=18: ["kw1"],
        log=lambda m, l="INFO": logs.append(m),
        targeted_gap_fill=lambda h, t, missing: list(new_bullets),
        filter_thinking_bullets=lambda b: list(b),
        max_bullets_per_chapter=99999,
        compute_coverage=lambda c, s: 0.4,
        force_insert_missing=lambda t, sm, r: None,
        bullet_cap=bullet_cap,
    )
    return result, logs


class TestTier2NearDupInsertionGuard:
    def test_rephrased_insertion_is_skipped(self):
        """A gap-fill bullet that REPHRASES an existing bullet (the user's
        'repetitive bullets - which were rephrased the same concepts') must
        NOT be appended."""
        existing = ["The orexin system regulates wakefulness and appetite."]
        rephrase = "The orexin system regulates the state of wakefulness."
        result, logs = _run_tier2(None, existing, [rephrase])
        assert result["bullet_points"] == existing, result["bullet_points"]
        assert any("near-duplicate" in m.lower() for m in logs), logs

    def test_distinct_insertion_still_appends(self):
        existing = ["The orexin system regulates wakefulness."]
        distinct = "Brown fat thermogenesis protects neonatal mice from cold."
        result, _logs = _run_tier2(None, existing, [distinct])
        assert distinct in result["bullet_points"]

    def test_exact_duplicate_still_skipped(self):
        existing = ["A bullet about topic one."]
        result, _logs = _run_tier2(None, existing, ["A bullet about topic one."])
        assert result["bullet_points"].count("A bullet about topic one.") == 1

    def test_guard_fail_open_without_rapidfuzz(self, monkeypatch):
        """Without rapidfuzz the guard degrades to the exact-match check
        (fail-open: distinct content still appends)."""
        from core.summarisation.dedup_service import DedupService

        svc = DedupService()
        svc._fuzz = None  # simulate rapidfuzz-unavailable (exact-match fallback)
        # the guard's lazy import resolves get_dedup_service from the
        # dedup_service module at call time — patch it there
        monkeypatch.setattr("core.summarisation.dedup_service.get_dedup_service", lambda: svc)
        existing = ["The orexin system regulates wakefulness."]
        distinct = "Brown fat thermogenesis protects neonatal mice from cold."
        result, _logs = _run_tier2(monkeypatch, existing, [distinct])
        assert distinct in result["bullet_points"]

    def test_thin_budget_bounds_insertion_room(self):
        """The thin-scoped bullet_cap bounds Tier-2 additions: 12 existing
        bullets on a 340-word chapter (cap 14) leaves room for 2 — the
        gap-fill list is trimmed; at 14 there is no room at all."""
        from core.summarisation.coverage_guarantee import apply_3tier_coverage

        result = {
            "executive_summary": "E",
            "bullet_points": [f"existing bullet number {i}" for i in range(14)],
            "thorough_summary": "T",
        }
        logs: list[str] = []
        missing_seen: list[list[str]] = []

        def gap_fill(heading, text, missing):
            missing_seen.append(list(missing))
            return [f"new bullet about {m}" for m in missing]

        apply_3tier_coverage(
            "H",
            "src",
            "content",
            result,
            0.4,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw1", "kw2", "kw3"],
            log=lambda m, l="INFO": logs.append(m),
            targeted_gap_fill=gap_fill,
            filter_thinking_bullets=lambda b: list(b),
            max_bullets_per_chapter=99999,
            compute_coverage=lambda c, s: 0.4,
            force_insert_missing=lambda t, sm, r: None,
            bullet_cap=14,  # the thin 340-word budget
        )
        assert result["bullet_points"] == [f"existing bullet number {i}" for i in range(14)]
        assert any("Tier-2 gap-fill SKIPPED" in m for m in logs), logs


# ═══════════════════════════════════════════════════════════════════════════
# BUG 2, L3 — F1 ships the combined honest measurement
# ═══════════════════════════════════════════════════════════════════════════


class TestF1CombinedMeasurement:
    def _run_f1(self, source_words, exec_sum, thorough, bullets):
        from core.summarisation.bullet_pipeline import BulletPipeline

        logs: list[tuple[str, str]] = []
        stub = SimpleNamespace(log=lambda m, l="DEBUG": logs.append((m, l)))
        state = SimpleNamespace(
            content=" ".join(f"word{i}" for i in range(source_words)),
            exec_sum=exec_sum,
            thorough=thorough,
            bullets=list(bullets),
        )
        BulletPipeline(stub).apply_f1_length_validation(state)
        return logs

    def test_f1_logs_bullet_words_and_combined_finding(self):
        """A 300-word chapter shipping 60w exec + 120w bullets + 140w
        thorough (= 320w, 1.1x the source) gets the combined WARNING +
        the 📏 line reports the bullet words."""
        bullets = [" ".join(f"b{i}w{j}" for j in range(12)) for i in range(10)]
        logs = self._run_f1(300, " ".join(["x"] * 60), " ".join(["y"] * 140), bullets)
        all_msgs = [m for m, _l in logs]
        assert any("bullets=" in m for m in all_msgs), all_msgs
        assert any("over-generation" in m for m in all_msgs), all_msgs

    def test_f1_combined_silent_when_within_budget(self):
        bullets = [" ".join(f"b{i}w{j}" for j in range(10)) for i in range(6)]
        logs = self._run_f1(300, " ".join(["x"] * 40), " ".join(["y"] * 90), bullets)
        msgs = [m for m, _l in logs]
        assert not any("over-generation" in m for m in msgs), msgs


# ═══════════════════════════════════════════════════════════════════════════
# BUG 2, integration — the additive machinery reads the thin budget
# ═══════════════════════════════════════════════════════════════════════════


class TestThinBudgetWiring:
    def test_coverage_wrapper_passes_the_thin_cap(self):
        """``SummarizerCoverageMixin._apply_3tier_coverage`` threads
        ``length_policy.bullet_cap(count_source_words(text))`` — with the
        two-regime cap, a thin text yields the scaled budget (> 0).
        Source pin + the real policy value."""
        src = (_project_root / "core" / "summarisation" / "summarizer_coverage.py").read_text(
            encoding="utf-8"
        )
        assert "bullet_cap=_lp_bullet_cap(" in src, (
            "the coverage wrapper must keep threading the additive budget"
        )
        from core.summarisation.length_policy import bullet_cap

        assert bullet_cap(340) == 14

    def test_scholar_and_recovery_helpers_delegate_the_cap(self):
        """The scholar gap-fill + quarantine-recovery call sites pass
        ``_lp_bullet_cap_fn(text)`` — with the thin regime they now carry
        a real budget."""
        from core.summarisation.summarizer import _lp_bullet_cap_fn

        thin_text = " ".join(f"w{i}" for i in range(340))
        fat_text = " ".join(f"w{i}" for i in range(2000))
        assert _lp_bullet_cap_fn(thin_text) == 14
        assert _lp_bullet_cap_fn(fat_text) == 0

    def test_thorough_expansion_threshold_scales_for_thin(self):
        """chapter_phases' dedicated-expansion threshold reads
        ``thorough_target`` lo — for a 150-word chapter it is now 41 (was
        80 = 53% of the source): the expansion call no longer forces a
        half-source thorough on a thin chapter."""
        src = (_project_root / "core" / "summarisation" / "chapter_phases.py").read_text(
            encoding="utf-8"
        )
        assert "_th_lo_lp" in src, "the expansion threshold must keep reading the scaled lo"
        from core.summarisation.length_policy import count_source_words, thorough_target

        text = " ".join(f"w{i}" for i in range(150))
        lo, _hi = thorough_target(count_source_words(text))
        assert lo == 41, (lo, _hi)
