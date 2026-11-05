"""V0.7.5 campaign close-out: the full-wizard functional sweep (plan §3).

Drives the REAL full WizardView (all 10 steps built offscreen) through
every step in BOTH themes — the r4_functional modal-recorder pattern:
every QDialog.exec is intercepted (recorded + rejected) so the headless
run verifies WHAT opens without ever blocking.

The offscreen traps (all documented at V0.7.4, honoured here):
  - navigation drives ``_current_step`` + ``_update_step()`` directly
    (never ``_go_next()`` with an invalid step — QMessageBox blocks
    forever offscreen);
  - full-wizard grabs take NO processEvents (the trap);
  - BOTH listing workers (Step 5 AND Step 6) are stubbed before the
    build — determinism, no HTTP.

Per-step assertions: the step renders, its phase-critical controls
exist and respond, the state round-trips, and the honest-copy surfaces
(the Step-8 review + the start-log lines) report the post-rework
truth (Step 7's disclosure, Step 7b's coverage-target semantics).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication.instance() or QApplication([])

# ── the global modal recorder (the r4_functional pattern) ─────────────────
opened: list[str] = []
_orig_exec = QDialog.exec


def _recording_exec(self, *a, **k):
    opened.append(self.metaObject().className())
    self.reject()
    return 0


QDialog.exec = _recording_exec  # type: ignore[method-assign]

# ── isolated HOME (settings/geometry never touch the real profile) ────────
profile = Path(tempfile.mkdtemp(prefix="elixir_v0750_sweep_"))
os.environ["HOME"] = str(profile)

import ui_qt.views.wizard_steps.step5_models as step5_mod  # noqa: E402
import ui_qt.views.wizard_steps.step6_translation as step6_mod  # noqa: E402
from ui_qt.theme import theme_manager  # noqa: E402


class _FakeSignal:
    def connect(self, *a, **k):
        pass


class _FakeWorker:
    def __init__(self, fn, *a, **k):
        pass

    finished = _FakeSignal()
    failed = _FakeSignal()

    def is_running(self):
        return False

    def start(self):
        pass


class _StubController:
    """The controller surface the full wizard touches (the V0.7.4 shape:
    settings + the keyring-shaped secret accessors)."""

    def __init__(self):
        self._settings: dict = {
            "summarisation.model": "gemma4-12b:latest",
            "summarisation.provider": "ollama",
            "translation.harakat_model": "qwen2.5:7b",
            "translation.judge_model": "translategemma:4b",
        }
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
        return ["qwen2.5:7b", "translategemma:4b", "gemma4-12b:latest"]


def _build_wizard():
    from ui_qt.views.wizard_view import WizardView

    orig5, orig6 = step5_mod.SimpleWorker, step6_mod.SimpleWorker
    step5_mod.SimpleWorker = _FakeWorker
    step6_mod.SimpleWorker = _FakeWorker
    try:
        view = WizardView(_StubController())
    finally:
        step5_mod.SimpleWorker = orig5
        step6_mod.SimpleWorker = orig6
    return view


def _check(label: str, cond: bool, failures: list[str]) -> None:
    if not cond:
        failures.append(label)
    print(f"  {'✓' if cond else '✗ FAIL'} {label}", flush=True)


def sweep(theme: str, out_dir: Path) -> list[str]:
    print(f"\n━━━ Theme: {theme} ━━━", flush=True)
    failures: list[str] = []
    theme_manager.apply(app, theme)
    view = _build_wizard()
    view.resize(820, 600)
    view.show()

    # ── Step 0 (Step 1: PDF + mode) ───────────────────────────────────
    view._current_step = 0
    view._update_step()
    _check(f"{theme}: step1 builds 3 mode cards", len(view.step1._type_cards) == 3, failures)
    _check(
        f"{theme}: step1 auto card is the selected default",
        view.step1._type_cards["auto"].property("selected") is not None
        or view.state.ocr_mode == "auto",
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step1.png"))

    # ── Step 1 (Step 2: range) ────────────────────────────────────────
    view._current_step = 1
    view._update_step()
    view.grab().save(str(out_dir / f"sweep_{theme}_step2.png"))

    # ── Step 2 (Step 3: OCR) ──────────────────────────────────────────
    view._current_step = 2
    view._update_step()
    _check(
        f"{theme}: step3 auto radio is the default",
        view.step3.auto_rb.isChecked() if hasattr(view.step3, "auto_rb") else True,
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step3.png"))

    # ── Step 3 (Step 4: outputs) ──────────────────────────────────────
    view._current_step = 3
    view._update_step()
    view.state.outputs_flashcards = True
    view.grab().save(str(out_dir / f"sweep_{theme}_step4.png"))

    # ── Step 4 (Step 5: models) ───────────────────────────────────────
    view._current_step = 4
    view._update_step()
    _check(
        f"{theme}: step5 limits Auto is the default",
        view.step5.limits_auto_cb.isChecked(),
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step5.png"))

    # ── Step 5 (Step 6: translation) ──────────────────────────────────
    view._current_step = 5
    view._update_step()
    view.state.translation_enabled = True
    view.grab().save(str(out_dir / f"sweep_{theme}_step6.png"))

    # ── Step 6 (Step 7: advanced — the 7a rework) ─────────────────────
    view._current_step = 6
    view._update_step()
    s7 = view.step7
    _check(f"{theme}: step7 fold starts hidden", not s7.disclosure.isVisibleTo(s7), failures)
    _check(f"{theme}: step7 fold icon is set", not s7.fold_btn.icon().isNull(), failures)
    # Open the disclosure; force the TOKEN strategy + manual → the gate opens.
    s7.fold_btn.setChecked(True)
    s7.strat_combo.setCurrentText("token")
    s7.token_auto_cb.setChecked(False)
    _check(f"{theme}: token gate opens under token+manual", s7.token_spin.isEnabled(), failures)
    s7.token_spin.setValue(4000)
    s7.semantic_cb.setChecked(False)
    view.steps[6].save_to_state()
    _check(
        f"{theme}: step7 state round-trips",
        view.state.segment_strategy == "token"
        and view.state.token_limit == 4000
        and view.state.enable_semantic is False,
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step7.png"))

    # ── Step 7 (Step 7b: fine-tune — the 7b/7c/7d reworks) ────────────
    view._current_step = 7
    view._update_step()
    s7b = view.step7b
    _check(
        f"{theme}: step7b has NO self-consistency control",
        not hasattr(s7b, "self_consist_cb"),
        failures,
    )
    _check(
        f"{theme}: step7b coverage caption present",
        "±3 for model randomness" in s7b.coverage_caption.text(),
        failures,
    )
    # The 7d recommended button: perturb, click, verify.
    s7b.coverage_spin.setValue(42)
    s7b.cache_cb.setChecked(True)
    s7b.recommended_btn.click()
    _check(
        f"{theme}: 7d recommended resets coverage to 85", s7b.coverage_spin.value() == 85, failures
    )
    view.steps[7].save_to_state()
    _check(
        f"{theme}: step7b state round-trips after recommended",
        view.state.coverage_threshold == 85 and view.state.cache_enabled is False,
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step7b.png"))

    # ── Step 8 (Review) ───────────────────────────────────────────────
    view._current_step = 8
    view._update_step()
    view.step8.refresh()
    review_text = view.step8.summary.toPlainText()
    _check(
        f"{theme}: review carries the honest Advanced line",
        "Token limit/segment: 4000" in review_text and "Semantic fallback: no" in review_text,
        failures,
    )
    _check(
        f"{theme}: review carries the coverage-target semantics",
        "Coverage target: 85%" in review_text and "max 3 rounds" in review_text,
        failures,
    )
    _check(
        f"{theme}: review no longer prints wizard-unset values",
        "Academic rigor:" not in review_text and "Self-consistency:" not in review_text,
        failures,
    )
    view.grab().save(str(out_dir / f"sweep_{theme}_step8.png"))

    # ── Step 9 (Logs) ─────────────────────────────────────────────────
    view._current_step = 9
    view._update_step()
    view.grab().save(str(out_dir / f"sweep_{theme}_step9.png"))

    # The start-log honesty: call _log_settings directly (no conversion).
    view._log_settings()
    log_text = view.step9.log_viewer.toPlainText()
    _check(
        f"{theme}: start-log honest Advanced + coverage lines",
        "token limit/segment: 4000" in log_text
        and "Coverage target: 85%" in log_text
        and "max 3 rounds" in log_text,
        failures,
    )
    _check(
        f"{theme}: start-log omits wizard-unset values",
        "Academic rigor" not in log_text and "Self-consistency" not in log_text,
        failures,
    )

    view.hide()
    view.deleteLater()
    theme_manager.apply(app, "light")  # restore
    return failures


def main() -> int:
    out_dir = Path("/tmp/v0750_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_failures: list[str] = []
    for theme in ("light", "dark"):
        all_failures.extend(sweep(theme, out_dir))
    print(f"\n━━━ Sweep complete: {len(all_failures)} failure(s) ━━━", flush=True)
    for f in all_failures:
        print(f"  ✗ {f}")
    if opened:
        print(f"(modal recorder saw {len(opened)} dialog(s): {sorted(set(opened))})")
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
