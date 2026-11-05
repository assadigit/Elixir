"""V0.7.5 phase-gate grab: full Step 7 / Step 7b offscreen, one variant per process.

Usage: grab_v0750_steps7.py <step> <theme> <width> <height> <out.png> [--open]

``step`` is ``7`` (Step7Advanced) or ``7b`` (Step7bFineTune). ``--open``
renders Step 7 with the advanced disclosure unfolded (the default grab is
the folded shipping state). Step 7b has no variants — the recommended
button is part of the default layout.
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


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    open_disc = "--open" in sys.argv
    which, theme, w, h, out = args[0], args[1], int(args[2]), int(args[3]), args[4]
    app = QApplication.instance() or QApplication([])

    from ui_qt.theme import theme_manager
    from ui_qt.views.wizard_steps.shared import WizardState

    theme_manager.apply(app, theme)

    # Neither step starts a worker — the build is HTTP-free by construction
    # (the V0.7.4 listing-worker trap does not apply here).
    if which == "7":
        from ui_qt.views.wizard_steps.step7_advanced import Step7Advanced

        step = Step7Advanced(_StubController(), WizardState())
        if open_disc:
            step.fold_btn.setChecked(True)
    elif which == "7b":
        from ui_qt.views.wizard_steps.step7b_fine_tune import Step7bFineTune

        step = Step7bFineTune(_StubController(), WizardState())
    else:
        raise SystemExit(f"unknown step {which!r} (use 7 or 7b)")

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
