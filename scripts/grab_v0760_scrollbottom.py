"""Verify the 4 VLM 'bottom card clipped' flags: scroll the host to the
bottom and grab — the flagged content must render fully there (the
designed scroll-host behaviour), proving nothing is actually clipped."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402


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


def find_scroll(widget):
    for sa in widget.findChildren(QScrollArea):
        return sa
    return None


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

    if which == "4":
        import ui_qt.views.wizard_steps.step4_outputs as m

        step = m.Step4Outputs(_StubController(), WizardState())
    elif which == "7b":
        import ui_qt.views.wizard_steps.step7b_fine_tune as m

        step = m.Step7bFineTune(_StubController(), WizardState())
    else:
        raise SystemExit(f"unknown step {which!r}")

    step.resize(w, h)
    step.show()
    app.processEvents()

    sa = find_scroll(step)
    if sa is None:
        print(f"step {which}: NO QScrollArea found — the flag would be REAL")
        return 2
    bar = sa.verticalScrollBar()
    bar.setValue(bar.maximum())
    app.processEvents()
    grab = step.grab()
    ok = grab.save(out)
    print(
        f"step {which} {theme} {w}x{h}: scroll range 0..{bar.maximum()}, "
        f"scrolled to max, bottom-view saved={ok} path={out}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
