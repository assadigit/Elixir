"""V0.7.6 audit grab: Steps 1 / 2 / 4 offscreen, one variant per process.

Usage: grab_v0760_audit.py <step> <theme> <width> <height> <out.png>

``step`` is ``1`` (Step1Pdf, the 3 mode cards, no file picked), ``2``
(Step2Range) or ``4`` (Step4Outputs). Follows the grab_v0750_steps7.py
pattern: stub controller, one processEvents (a single step shown alone
tolerates exactly one), no workers (none of these three steps starts
one in this state).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402


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


def main() -> int:
    which, theme, w, h, out = (
        sys.argv[1],
        sys.argv[2],
        int(sys.argv[3]),
        int(sys.argv[4]),
        sys.argv[5],
    )
    app = QApplication.instance() or QApplication([])

    from ui_qt.theme import theme_manager
    from ui_qt.views.wizard_steps.shared import WizardState

    theme_manager.apply(app, theme)

    if which == "1":
        from ui_qt.views.wizard_steps.step1_pdf import Step1Pdf

        step = Step1Pdf(_StubController(), WizardState())
    elif which == "2":
        from ui_qt.views.wizard_steps.step2_range import Step2Range

        step = Step2Range(_StubController(), WizardState())
    elif which == "4":
        from ui_qt.views.wizard_steps.step4_outputs import Step4Outputs

        step = Step4Outputs(_StubController(), WizardState())
    else:
        raise SystemExit(f"unknown step {which!r} (use 1, 2 or 4)")

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
