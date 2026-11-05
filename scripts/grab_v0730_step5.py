"""V0.7.3 phase-gate grab: full Step 5 offscreen, one variant per process.

Usage: grab_step5.py <theme> <width> <height> <out.png>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402


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
            "summarisation.provider": "ollama",
            "summarisation.model": "Ternary-Bonsai-2-27B",
            "ocr.primary_model": "qwen3-vl:8b",
        }

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value

    def get_secret(self, path, default=""):
        return default

    def set_secret(self, path, value):
        pass

    def list_ollama_models(self):
        return []


def main() -> int:
    theme, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    app = QApplication.instance() or QApplication([])

    import ui_qt.views.wizard_steps.step5_models as step5_mod
    from ui_qt.theme import theme_manager
    from ui_qt.views.wizard_steps.shared import WizardState

    theme_manager.apply(app, theme)

    # The listing worker is stubbed — no HTTP, no modal, deterministic combos.
    orig = step5_mod.SimpleWorker
    step5_mod.SimpleWorker = _FakeWorker
    try:
        step = step5_mod.Step5Models(_StubController(), WizardState())
    finally:
        step5_mod.SimpleWorker = orig

    # Populate the combos through the real main-thread slot (the seeded
    # last-used picks are already selected; the list confirms them).
    step._on_models_loaded(
        ["Ternary-Bonsai-2-27B", "gemma3:12b", "qwen3-vl:8b", "phi-4"]
    )
    # One manual-mode grab needs the spins visible/enabled state honest —
    # default grab keeps Auto ON (the shipping default).

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
