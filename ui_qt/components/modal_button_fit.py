"""V0.6.3 — guarantee every modal's buttons render at full label width.

USER REPORT (the evidenced symptom): the Summarization success modal
("Σ Summarization Complete") showed "📂 Open File Location" with the tail
of the label clipped — and "🔄 Try Another" missing its final "r" —
whenever the message text was short.

ROOT CAUSE (reproduced offscreen with the shipped QSS, light + dark):
the success modal — short message text + three QSS-padded buttons —
renders 355px wide, 19px NARROWER than its own sizeHint (374px):
"📂 Open File Location" gets 132px where its sizeHint needs 142px, and
"🔄 Try Another" gets 95px where it needs 104px. QMessageBox's internal
post-show sizing (QMessageBoxPrivate::updateSize) can settle BELOW
sizeHint when the text label is narrow; the button row then receives
less than its sizeHints and QPushButton clips its label.

THE FIX — per-button minimum widths, the approach that works WITH the
layout chain instead of fighting it: raising each button's
minimumWidth to its sizeHint().width() propagates upward (button
minimum → QDialogButtonBox minimum → the QMessageBox layout's
totalMinimumSize → dialog geometry), so the dialog can never render
narrower than its button row.

A dialog-LEVEL setMinimumWidth floor was tried first and REJECTED on
empirical evidence: layout activation during show() overwrites the
widget minimum with the layout's own totalMinimumSize, silently undoing
the programmatic floor (verified — the floor approach leaves the clip
in place; the rejection is pinned in the test suite).

APPLIED GLOBALLY: a QApplication event filter fits EVERY QMessageBox on
its first QEvent.Show — the custom-button sites (the shared success
modal, the wizard's VRAM-overbudget box, the podcast-complete box) AND
every static convenience box (QMessageBox.warning/.question/...),
current and future, with no per-call-site discipline required. Event
filters are notified BEFORE the target's own event handler, so the
raised minimums are already in place when QMessageBox's internal
resize runs.

Pure geometry — content-agnostic (Rule 1): reads only widget sizeHints;
never inspects message text or button vocabulary.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QMessageBox


def fit_message_box_buttons(box: QMessageBox) -> int:
    """Raise every button's minimum width to its sizeHint width.

    Idempotent — only ever RAISES a minimum, never lowers one — and a
    no-op on boxes with no buttons. Call it once the buttons exist; on
    show, button sizeHints are final (fonts and QSS padding resolved).

    Returns the sum of the button sizeHint widths (0 when there are no
    buttons). Callers and tests use it as an observable only, never for
    layout — the layout chain is what consumes the raised minimums.
    """
    applied = 0
    for btn in box.buttons():
        hint_w = btn.sizeHint().width()
        if btn.minimumWidth() < hint_w:
            btn.setMinimumWidth(hint_w)
        applied += hint_w
    return applied


class ModalButtonFitFilter(QObject):
    """Fits every QMessageBox's buttons on Show — the global guarantee.

    Installed once at app bootstrap (``install_modal_button_fit``); sees
    every event of every object, but the work is gated behind one
    ``QEvent.Show`` + isinstance check, so the steady-state cost is a
    single type comparison per show.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt API name)
        if event.type() == QEvent.Show and isinstance(obj, QMessageBox):
            fit_message_box_buttons(obj)
        return False  # never consume — a pure observer


_installed: ModalButtonFitFilter | None = None


def install_modal_button_fit(app: QApplication) -> ModalButtonFitFilter:
    """Install the global modal-button fit filter (idempotent).

    One call at app bootstrap (``ui_qt.app.run``, right after the theme
    is applied) covers every QMessageBox the process will ever show.
    Returns the filter instance (the same object on repeat calls).
    """
    global _installed
    if _installed is None:
        _installed = ModalButtonFitFilter()
        app.installEventFilter(_installed)
    return _installed
