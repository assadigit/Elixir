"""Measure step7b's scroll geometry: is any content unreachable at max scroll?

The VLM flagged the bottom card as CUT at the maximum scroll position. A
real defect would be: contentHeight > viewportHeight + scrollMax (pixels
of content below the last reachable scroll position)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402


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
    app = QApplication.instance() or QApplication([])
    from ui_qt.theme import theme_manager
    from ui_qt.views.wizard_steps.shared import WizardState
    from ui_qt.views.wizard_steps.step7b_fine_tune import Step7bFineTune

    for theme in ("dark", "light"):
        for w, h in ((740, 540), (820, 600)):
            theme_manager.apply(app, theme)
            step = Step7bFineTune(_StubController(), WizardState())
            step.resize(w, h)
            step.show()
            app.processEvents()
            sa = step.findChildren(QScrollArea)[0]
            bar = sa.verticalScrollBar()
            # The authoritative measurement: the widget's real height vs
            # viewport + scrollable range.
            wh = sa.widget().height()
            vh = sa.viewport().height()
            reachable = vh + bar.maximum()
            unreachable_px = wh - reachable
            bar.setValue(bar.maximum())
            app.processEvents()
            # Also grab the very bottom at max scroll for the crop pass.
            out = f"/home/z/my-project/grabs_v0760/measure_7b_{theme}_{w}x{h}_bottom.png"
            step.grab().save(out)
            print(
                f"7b {theme} {w}x{h}: widget={wh}px viewport={vh}px "
                f"scrollMax={bar.maximum()}px reachable={reachable}px "
                f"UNREACHABLE={unreachable_px}px  bottom_grab={out}"
            )
            step.hide()
            step.deleteLater()
    return 0


if __name__ == "__main__":
    sys.exit(main())
