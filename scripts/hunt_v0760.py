"""V0.7.6 audit hunt: the untried combinations (Part 3).

Offscreen, modal-free, the v0750_full_sweep pattern (no _go_next, no
processEvents in the full-wizard flow, SimpleWorker stubbed in BOTH
step5_models and step6_translation before the build).

Hunts:
  H1  Scanned mode + Token strategy + a manual token limit — the state
      round-trip AND the built request (via the REAL _REQUEST_FIELD_MAP).
  H2  LM Studio listing uses its OWN URL (worker-fn capture, no HTTP).
  H3  Translation mode B end-to-end (manual list → Start → settings).
  H4  Coverage targets 0 / 50 / 100 — the ±3 tolerance + max-3-rounds
      math at the extremes; target 0 must NEVER loop.
  H5  The fold toggle rapid-clicked (20 toggles) — icon + state stay
      consistent, no crash.
  H6  A fully-defaulted run (no human input on any step) Step 1 →
      start-log: no crash, no wizard-unset values, defaults intact.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402


class _FakeSignal:
    def connect(self, *a, **k):
        pass


class _FakeWorker:
    captured = None

    def __init__(self, fn, *a, **k):
        type(self).captured = fn

    finished = _FakeSignal()
    failed = _FakeSignal()

    def is_running(self):
        return False

    def start(self):
        pass


class _StubController:
    def __init__(self):
        self._settings: dict = {}
        self.secrets: dict = {}

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value

    def get_secret(self, path, default=None):
        return self.secrets.get(path, default)

    def set_secret(self, path, value):
        self.secrets[path] = value

    def list_ollama_models(self):
        return []


FAILS: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  {'✓' if cond else '✗ FAIL'} {label}", flush=True)
    if not cond:
        FAILS.append(label)


def main() -> int:
    _app = QApplication.instance() or QApplication([])  # noqa: F841 — keep the Qt app alive

    import ui_qt.views.wizard_steps.step5_models as step5_mod
    import ui_qt.views.wizard_steps.step6_translation as step6_mod

    # The offscreen trap: stub SimpleWorker in BOTH step modules.
    orig5, orig6 = step5_mod.SimpleWorker, step6_mod.SimpleWorker
    step5_mod.SimpleWorker = _FakeWorker
    step6_mod.SimpleWorker = _FakeWorker

    from ui_qt.views.wizard_view import WizardView

    try:
        ctrl = _StubController()
        view = WizardView(ctrl)
        s = view.state

        # ── H1: Scanned + Token strategy + manual limit ────────────────
        print("H1: Scanned mode + Token strategy + manual token limit")
        view._current_step = 0
        view._update_step()
        view.step1._type_cards["scanned"].set_selected(True)
        view.step1._on_type_selected("scanned") if hasattr(
            view.step1, "_on_type_selected"
        ) else None
        view.steps[0].save_to_state()
        check("H1: scanned mode lands in state", s.ocr_mode == "scanned")
        view._current_step = 6
        view._update_step()
        s7 = view.step7
        s7.fold_btn.setChecked(True)
        s7.strat_combo.setCurrentText("token")
        s7.token_auto_cb.setChecked(False)
        s7.token_spin.setValue(3500)
        view.steps[6].save_to_state()
        check(
            "H1: token+manual round-trips", s.segment_strategy == "token" and s.token_limit == 3500
        )
        from controller import Controller

        ui_data = s.to_ui_data()
        # Build the request the way the wizard does — the REAL map + builder.
        _c = Controller()
        built = _c.build_request_from_ui(ui_data)
        check(
            "H1: the REAL request carries ocr_mode=scanned + token 3500",
            built is not None
            and getattr(built, "ocr_mode", None) == "scanned"
            and getattr(built, "token_limit_per_segment", None) == 3500,
        )
        check(
            "H1: ui_data carries ocr_mode=scanned + token 3500",
            ui_data.get("ocr_mode") == "scanned" and ui_data.get("token_limit_per_segment") == 3500,
        )

        # ── H2: LM Studio listing uses its OWN URL ─────────────────────
        print("H2: LM Studio backend lists from its own URL")
        view._current_step = 4
        view._update_step()
        s5 = view.step5
        idx = s5.backend_combo.findData("lmstudio")
        check("H2: lmstudio is selectable", idx >= 0)
        s5.backend_combo.setCurrentIndex(idx)
        s5.lmstudio_url_edit.setText("http://localhost:1234/v1")
        _FakeWorker.captured = None
        s5._refresh_models()
        cap = _FakeWorker.captured
        check("H2: a worker fn was dispatched", cap is not None)
        # partial(list_lmstudio_models, url) — verify the URL is baked in
        import functools

        is_partial = isinstance(cap, functools.partial)
        url_ok = is_partial and "localhost:1234" in str(cap.args)
        fn_ok = is_partial and cap.func.__name__ == "list_lmstudio_models"
        check("H2: the worker fn is list_lmstudio_models(lm-studio-url)", bool(url_ok and fn_ok))

        # ── H3: translation mode B end-to-end ─────────────────────────
        print("H3: Translation mode B (manual) end-to-end")
        view._current_step = 5
        view._update_step()
        s6 = view.step6
        s6.enable_cb.setChecked(True)
        s6.mode_b_rb.setChecked(True)
        # manual list: pick exactly flashcards + study_guide via the checkboxes
        picked = set()
        for key, cb in getattr(s6, "_tr_cbs", {}).items():
            want = key in ("flashcards", "study_guide")
            cb.setChecked(want)
            if want:
                picked.add(key)
        view.steps[5].save_to_state()
        check(
            "H3: mode B picks land in state",
            s.translation_selection_mode == "manual"
            and s.translation_outputs.get("flashcards") is True
            and s.translation_outputs.get("study_guide") is True
            and s.translation_outputs.get("chapter_summaries") is False,
        )
        # Start: the wizard saves translation settings via _save_translation_settings
        view._save_translation_settings()
        check(
            "H3: Start writes the manual selection to settings (per-key)",
            ctrl._settings.get("translation.outputs.flashcards") is True
            and ctrl._settings.get("translation.outputs.study_guide") is True
            and ctrl._settings.get("translation.outputs.chapter_summaries") is False
            and ctrl._settings.get("translation.selection_mode") == "manual"
            and ctrl._settings.get("translation.enabled") is True,
        )

        # ── H4: coverage extremes 0 / 50 / 100 ─────────────────────────
        print("H4: coverage targets 0 / 50 / 100 (the REAL loop, stubbed fns)")
        from core.summarisation.coverage_loop import (
            COVERAGE_TOLERANCE,
            MAX_COVERAGE_ROUNDS,
            run_coverage_close_loop,
        )

        def _run_loop(coverage, target, fill=None, keywords=("kw-a", "kw-b"), bump=0.10):
            logs = []

            def gap_fill(heading, text, missing):
                logs.append(f"fill:{len(missing)}")
                return list(fill or [])

            def compute(content, combined):
                # each fill round bumps coverage by `bump` (0.0 = fill never helps)
                nonlocal coverage
                if fill is not None:
                    coverage = min(1.0, coverage + bump)
                return coverage

            bullets, cov, rounds = run_coverage_close_loop(
                "h",
                "t",
                "c",
                ["b1"],
                "e",
                "th",
                coverage,
                coverage_threshold=target,
                extract_keywords=lambda content, n=18: list(keywords),
                targeted_gap_fill=gap_fill,
                filter_thinking_bullets=lambda bs: [b for b in bs if "THINK" not in b],
                compute_coverage=compute,
                is_near_duplicate=lambda b, bs: b in bs,
                log=lambda m, level="INFO": logs.append(m),
            )
            return bullets, cov, rounds, logs

        # target 0: ANY coverage is in-band — never loops
        _, cov, rounds, logs = _run_loop(0.0, 0.0)
        check("H4: target 0 @ 0% never loops (rounds=0)", rounds == 0 and cov == 0.0)
        _, cov, rounds, logs = _run_loop(0.55, 0.0)
        check("H4: target 0 @ 55% never loops (rounds=0)", rounds == 0)
        # target 50: 46% is below 47 (target-3) → one fill round to 56% → met
        _, cov, rounds, logs = _run_loop(0.46, 0.50, fill=["new-bullet"])
        check("H4: target 50 @ 46% loops once then meets (56%)", rounds == 1 and cov == 0.56)
        # target 50: 47% is exactly in-band → no loop
        _, cov, rounds, logs = _run_loop(0.47, 0.50)
        check("H4: target 50 @ 47% in-band (no loop)", rounds == 0)
        # target 100: 96% below 97, a FRESH bullet each round (no near-dup)
        # that never improves coverage → exhausts at 3, honest report
        fresh_n = [0]

        def _never_helps(heading, text, missing):
            fresh_n[0] += 1
            return [f"fresh-bullet-{fresh_n[0]}"]

        logs_nh = []
        _, cov, rounds = run_coverage_close_loop(
            "h",
            "t",
            "c",
            ["b1"],
            "e",
            "th",
            0.96,
            coverage_threshold=1.0,
            extract_keywords=lambda content, n=18: ["kw-a", "kw-b"],
            targeted_gap_fill=_never_helps,
            filter_thinking_bullets=lambda bs: list(bs),
            compute_coverage=lambda content, combined: 0.96,
            is_near_duplicate=lambda b, bs: b in bs,
            log=lambda m, level="INFO": logs_nh.append(m),
        )
        exhausted = any("after 3 attempts" in m and "remaining gaps" in m for m in logs_nh)
        check("H4: target 100 @ 96% exhausts at 3 rounds + names gaps", rounds == 3 and exhausted)
        # target 100: 97% in-band
        _, cov, rounds, logs = _run_loop(0.97, 1.0)
        check("H4: target 100 @ 97% in-band (no loop)", rounds == 0)
        # stalled form 1: no fillable candidates
        _, cov, rounds, logs = _run_loop(0.80, 1.0, keywords=())
        stalled1 = any("no fillable gaps" in m for m in logs)
        check("H4: no-candidates stall reported honestly", stalled1 and rounds == 1)
        # stalled form 2: gap-fill produces nothing usable
        _, cov, rounds, logs = _run_loop(0.80, 1.0, fill=[])
        stalled2 = any("produced nothing usable" in m for m in logs)
        check("H4: no-output stall reported honestly", stalled2 and rounds == 1)
        # Tier-2 guards: thinking-tainted + near-dup fills are dropped
        _, cov, rounds, logs = _run_loop(0.40, 0.50, fill=["THINK leak", "b1", "real-new"])
        dropped_think = any("prompt-leakage/thinking" in m for m in logs)
        dropped_dup = any("near-duplicate" in m for m in logs)
        check("H4: Tier-2 guards drop thinking + near-dup fills", dropped_think and dropped_dup)
        check(
            "H4: tolerance + rounds constants (0.03 / 3)",
            COVERAGE_TOLERANCE == 0.03 and MAX_COVERAGE_ROUNDS == 3,
        )

        # ── H5: fold toggle rapid-clicked ──────────────────────────────
        print("H5: fold toggle rapid-clicked (21×, ends OPEN)")
        view._current_step = 6
        view._update_step()
        s7 = view.step7
        crash = False
        final_visible = final_icon_ok = None
        try:
            for i in range(21):  # odd count → ends CHECKED (open)
                s7.fold_btn.setChecked(i % 2 == 0)
            final_visible = s7.disclosure.isVisibleTo(s7)
            final_icon_ok = not s7.fold_btn.icon().isNull()
        except Exception as exc:  # noqa: BLE001
            crash = True
            print("   crash:", exc)
        check(
            "H5: 21 rapid toggles, no crash, ends open with icon set",
            not crash and bool(final_visible) and bool(final_icon_ok),
        )

        # ── H6: fully-defaulted run Step 1 → start-log ─────────────────
        print("H6: fully-defaulted run (no human input) → start-log")
        fresh = WizardView(_StubController())
        fs = fresh.state
        fresh.step1.pdf_edit.setText("/tmp/does-not-matter.pdf")  # validation only
        for i in range(len(fresh.steps) - 2):  # steps 0..7 (skip review+logs)
            fresh._current_step = i
            fresh._update_step()
            fresh.steps[i].save_to_state()
        fresh._save_translation_settings()
        fresh._log_settings()
        log_text = fresh.step9.log_viewer.toPlainText()
        check("H6: no crash through all steps + start-log", len(log_text) > 0)
        check(
            "H6: defaults intact (85/32768/16000/2000/auto)",
            fs.coverage_threshold == 85
            and fs.max_context_tokens == 32768
            and fs.max_output_tokens == 16000
            and fs.token_limit == 2000
            and fs.ocr_mode == "auto",
        )
        check(
            "H6: log omits wizard-unset values",
            "Academic rigor" not in log_text and "Self-consistency" not in log_text,
        )
        check(
            "H6: log carries the honest coverage line",
            "Coverage target: 85%" in log_text and "max 3 rounds" in log_text,
        )
        fresh.hide()
        fresh.deleteLater()

        view.hide()
        view.deleteLater()
    finally:
        step5_mod.SimpleWorker = orig5
        step6_mod.SimpleWorker = orig6

    print(f"\n━━━ Hunt complete: {len(FAILS)} failure(s) ━━━")
    for f in FAILS:
        print("  ✗", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
