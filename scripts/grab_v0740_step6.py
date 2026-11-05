"""V0.7.4 phase-gate grab: full Step 6 offscreen, one variant per process.

Usage: grab_v0740_step6.py <theme> <width> <height> <out.png> [--mode-b]

The default grab is mode A (the shipping default — "The outputs I
selected in step 4", the manual list hidden).  ``--mode-b`` renders the
manual-list variant.
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
        self._settings = {
            "translation.backend": "ollama",
            "translation.harakat_model": "qwen2.5:7b",
            "translation.judge_model": "translategemma:4b",
        }

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value

    def list_ollama_models(self):
        return []


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode_b = "--mode-b" in sys.argv
    theme, w, h, out = args[0], int(args[1]), int(args[2]), args[3]
    app = QApplication.instance() or QApplication([])

    import ui_qt.views.wizard_steps.step6_translation as step6_mod
    from ui_qt.theme import theme_manager
    from ui_qt.views.wizard_steps.shared import WizardState

    theme_manager.apply(app, theme)

    # The listing worker is stubbed — no HTTP, no modal, deterministic combos.
    orig = step6_mod.SimpleWorker
    step6_mod.SimpleWorker = _FakeWorker
    try:
        step = step6_mod.Step6Translation(_StubController(), WizardState())
    finally:
        step6_mod.SimpleWorker = orig

    # Populate the combos through the real main-thread slot (the seeded
    # last-used picks are already selected; the list confirms them).
    step._on_models_loaded(["qwen2.5:7b", "translategemma:4b", "gemma3:12b"])

    # The master box ON (the interesting state — the skip-off default is
    # just a greyed-out variant of the same layout).
    step.enable_cb.setChecked(True)
    if mode_b:
        step.mode_b_rb.setChecked(True)

    step.resize(w, h)
    step.show()
    app.processEvents()
    grab = step.grab()
    assert not grab.isNull()
    ok = grab.save(out)
    step.hide()
    step.deleteLater()
    print(f"saved={ok} path={out} bytes={Path(out).stat().st_size if ok else 0}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
