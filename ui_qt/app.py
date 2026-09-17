"""Main application window — slim top bar + single focused conversion screen.

  ┌──────────────────────────────────────────────────────────────┐
  │  ◆ Elixir ·  PDF → Markdown + Summaries     [🧰][⚙]  │  top bar
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │            ( ConvertView — the two flows + CTA )             │  scrollable
  │                                                              │
  └──────────────────────────────────────────────────────────────┘

The gear button opens the VLC-style :class:`SettingsDialog`.  The toolbox
button opens the Tools menu (Validate summaries…).  Closing the window while
a conversion is running asks for confirmation first.  Window size + position
persist between launches.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.icons import icon, load_brand_logo
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings import SettingsDialog
from ui_qt.theme import theme_manager
from ui_qt.views.convert_view import ConvertView
from ui_qt.views.output_scanner_view import OutputScannerView
from ui_qt.views.quarantine_view import QuarantineView
from ui_qt.views.queue_view import QueueView
from ui_qt.views.validate_dialog import ValidateDialog
from utils.geometry import restored_geometry_is_visible

logger = logging.getLogger(__name__)


_GEOMETRY_FILE = Path.home() / ".elixir" / "window_geometry.json"


class ElixirWindow(QMainWindow):
    """Top-level window for the PySide6 UI."""

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"Elixir  ·  v{self._app_version()}")
        # V13.31.0 (#3): 20% smaller default — was 760x540, now 608x432.
        # More compact per user request.
        self.setMinimumSize(560, 400)
        self._restore_geometry()

        self._settings_dialog: SettingsDialog | None = None
        self._validate_dialog: ValidateDialog | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_content(), 1)

        # enable window-wide drag-and-drop
        self.setAcceptDrops(True)

        # non-blocking Ollama reachability check
        self._warn_ollama()

    # ══════════════════════════════════════════════════════════════════════
    # Top bar
    # ══════════════════════════════════════════════════════════════════════
    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(48)  # V13.31.0: was 38 — more breathing room per user request
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 14, 0)  # V13.31.0: wider margins
        lay.setSpacing(10)  # V13.31.0: more spacing between elements

        # brand mark + title — V4.7.25: PNG logo with SVG fallback
        p = theme_manager.palette
        brand = QLabel()
        logo_pm = load_brand_logo(height=22)
        if logo_pm is not None:
            brand.setPixmap(logo_pm)
        else:
            brand.setPixmap(icon("book", p.accent, 18).pixmap(18, 18))
        lay.addWidget(brand)

        title = QLabel("Elixir")
        title.setObjectName("H3")  # V7.4.0: H2→H3 for compact top bar
        lay.addWidget(title)

        subtitle = QLabel("·  PDF → Markdown + Summaries")
        subtitle.setObjectName("Caption")
        lay.addWidget(subtitle)

        lay.addStretch()

        # V5.3.2: Process Wizard CTA — prominent button in top bar
        self.wizard_btn = QPushButton("✨  Process Wizard")
        self.wizard_btn.setObjectName("Primary")
        self.wizard_btn.setCursor(Qt.PointingHandCursor)
        self.wizard_btn.setToolTip("Open the guided step-by-step conversion wizard")
        self.wizard_btn.clicked.connect(self._open_wizard)
        lay.addWidget(self.wizard_btn)

        # V13.31.0 (#10): Merge Books moved to header as a compact link
        # (was a prominent Secondary button — too cluttered with 3 buttons)
        self.merge_btn = QPushButton("📚  Merge")
        self.merge_btn.setObjectName("Compact")
        self.merge_btn.setCursor(Qt.PointingHandCursor)
        self.merge_btn.setToolTip("Merge summaries + keypoints from multiple book conversions")
        self.merge_btn.clicked.connect(self._open_merge_dialog)
        lay.addWidget(self.merge_btn)

        # V13.31.0 (#9): Quick Convert removed per user request

        # theme toggle (sun/moon)
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("IconBtn")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("Toggle dark / light theme")
        self.theme_btn.clicked.connect(self._toggle_theme)
        lay.addWidget(self.theme_btn)

        # V13.31.0 (#12): Changed from "tools" (sliders icon) to "info" icon
        # The sliders-horizontal icon looked like volume controls. Now uses
        # an info icon — opens the About & System dialog.
        self.about_btn = QPushButton()
        self.about_btn.setObjectName("IconBtn")
        self.about_btn.setCursor(Qt.PointingHandCursor)
        self.about_btn.setToolTip("About & System Info")
        self.about_btn.clicked.connect(self._open_about_system)
        lay.addWidget(self.about_btn)

        # settings gear
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("IconBtn")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(self.settings_btn)

        self._refresh_top_bar_icons()
        return bar

    def _refresh_top_bar_icons(self) -> None:
        p = theme_manager.palette
        # sun icon in dark mode (click → light), moon in light mode (click → dark)
        self.theme_btn.setIcon(icon("sun" if p.is_dark else "moon", p.text_primary, 16))
        # V13.31.0 (#12): info icon instead of sliders-horizontal
        self.about_btn.setIcon(icon("info", p.text_primary, 16))
        self.settings_btn.setIcon(icon("settings", p.text_primary, 16))

    def _auto_detect_system_theme(self) -> str:
        """V10.18.0 (E6): Detect the system's dark/light theme preference."""
        try:
            from PySide6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if app:
                scheme = app.styleHints().colorScheme()
                if scheme.name == "Dark":
                    return "dark"
                elif scheme.name == "Light":
                    return "light"
        except Exception:
            logger.debug("theme detect failed", exc_info=True)
        return "dark"  # default

    def _toggle_theme(self) -> None:
        theme_manager.toggle()
        self._refresh_top_bar_icons()
        self.convert_view.refresh_theme()
        if hasattr(self, "queue_view"):
            self.queue_view.refresh_theme()
        if hasattr(self, "output_scanner_view"):
            self.output_scanner_view.refresh_theme()
        if hasattr(self, "quarantine_view"):
            self.quarantine_view.refresh_theme()
        # V18.20.4.6 (W-b20): the dead branch that used to sit here was
        # removed — it refreshed a hallucination-audit view attribute
        # that is never assigned anywhere (the hallucination audit opens
        # from convert_view, not the main window).

    def _open_wizard(self) -> None:
        """V5.3.2: Open the Process Wizard as a modal dialog."""
        from ui_qt.views.wizard_view import WizardView
        dlg = WizardView(self.controller, self)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()

    def _open_merge_dialog(self) -> None:
        """V10.21.0: Open the multi-PDF merge dialog.

        V18.20.4.9 (W-b12): the merge itself used to run synchronously in
        this click slot (the UI froze for the whole merge). It now runs on
        a SimpleWorker (P4 W-b11 pattern: worker ref on self, re-entrancy
        guard, merge button disabled while running and re-enabled in BOTH
        outcome handlers); on failure the traceback is logged at WARNING
        BEFORE the user box (W-b17 crash-visibility — was str(e)-only).
        """
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        # Let user select multiple book output directories
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder containing book conversions to merge", "",
            QFileDialog.ShowDirsOnly,
        )
        if not folder:
            return

        # Find all book subdirectories
        base = Path(folder)
        book_dirs = [d for d in base.iterdir() if d.is_dir() and (d / "summaries").exists()]
        if not book_dirs:
            QMessageBox.information(self, "No books found",
                f"No book conversion directories found in: {folder}\n\n"
                f"Each book should have a 'summaries' subfolder.")
            return

        # Let user select output location
        output_folder = QFileDialog.getExistingDirectory(
            self, "Select output folder for merged result", str(base),
            QFileDialog.ShowDirsOnly,
        )
        if not output_folder:
            return

        # Run the merge (W-b12: off the UI thread)
        worker = getattr(self, "_merge_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return  # a merge is already in flight — don't stack workers

        self.merge_btn.setEnabled(False)
        # The finished handler quotes the book count in its box.
        self._merge_book_dirs = book_dirs

        def _work():
            from core.pipeline.multi_pdf_merge import merge_books
            try:
                return merge_books(book_dirs, Path(output_folder), log_callback=None)
            except Exception:
                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE
                # the "Merge error" box (was str(e)-only — zero
                # diagnostics for support).
                logger.warning("library merge raised — traceback follows",
                               exc_info=True)
                raise

        w = SimpleWorker(_work)
        self._merge_worker = w  # Python ref — the QObject can't be GC'd mid-run
        w.finished.connect(self._on_merge_finished)
        w.failed.connect(self._on_merge_failed)
        w.start()

    def _on_merge_finished(self, result) -> None:
        """W-b12: main-thread handler — re-enable + the identical boxes."""
        self.merge_btn.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        book_dirs = self._merge_book_dirs
        if result:
            QMessageBox.information(self, "Merge complete",
                f"Merged {len(book_dirs)} books.\nResult: {result}")
        else:
            QMessageBox.warning(self, "Merge failed", "No summaries found to merge.")

    def _on_merge_failed(self, error: str) -> None:
        """W-b12/W-b18: a raising merge must never leave the button stuck
        disabled — re-enable + the existing error box (same title/text
        shape; the diagnostics went to the log via the W-b17 wrapper)."""
        self.merge_btn.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Merge error", error)

    # V13.31.0 (#9): Quick Convert removed per user request
    # The full Process Wizard covers all use cases.

    # ══════════════════════════════════════════════════════════════════════
    # Content
    # ══════════════════════════════════════════════════════════════════════
    def _build_content(self) -> QWidget:
        # V13.31.0: Tab bar redesigned:
        # - Removed Podcast Maker tab (now opens as modal from tool dashboard)
        # - Added Hallucination Audit tab (was only accessible from tool cards)
        # - Removed tools menu (moved to About button in header)
        from PySide6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("MainTabs")
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        p = theme_manager.palette

        # Tab 1: Convert (primary page — tool dashboard)
        convert_scroll = QScrollArea()
        convert_scroll.setWidgetResizable(True)
        convert_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        convert_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        convert_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.convert_view = ConvertView(self.controller)
        convert_scroll.setWidget(self.convert_view)
        self.tab_widget.addTab(convert_scroll, icon("rocket", p.text_secondary, 16), "Convert")

        # Tab 2: Queue (batch processing)
        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        queue_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.queue_view = QueueView(self.controller)
        queue_scroll.setWidget(self.queue_view)
        self.tab_widget.addTab(queue_scroll, icon("list-checks", p.text_secondary, 16), "Queue")

        # V13.31.0 (#6): Podcast Maker tab REMOVED — now opens as modal dialog
        # from the tool dashboard, consistent with all other tools.

        # Tab 3: Output Scanner (audit a book's output folder)
        scanner_scroll = QScrollArea()
        scanner_scroll.setWidgetResizable(True)
        scanner_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scanner_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scanner_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_scanner_view = OutputScannerView(self.controller)
        scanner_scroll.setWidget(self.output_scanner_view)
        self.tab_widget.addTab(scanner_scroll, icon("scan", p.text_secondary, 16), "Output Scanner")

        # Tab 4: Bullet Audit (quarantine — dropped-bullet audit & restore)
        quarantine_scroll = QScrollArea()
        quarantine_scroll.setWidgetResizable(True)
        quarantine_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        quarantine_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        quarantine_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.quarantine_view = QuarantineView(self.controller)
        quarantine_scroll.setWidget(self.quarantine_view)
        self.tab_widget.addTab(
            quarantine_scroll, icon("alert-triangle", p.text_secondary, 16), "Bullet Audit"
        )

        # Tab 5: Hallucination Audit (V13.31.0 #1 — new tab per user request)
        # A lightweight wrapper around the HallucinationAuditDialog content,
        # embedded as a tab instead of a modal.
        hallucination_scroll = QScrollArea()
        hallucination_scroll.setWidgetResizable(True)
        hallucination_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        hallucination_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hallucination_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Create a simple widget with the hallucination audit UI
        from PySide6.QtWidgets import QLabel as _QL
        from PySide6.QtWidgets import QPushButton as _QPB
        from PySide6.QtWidgets import QVBoxLayout as _VL
        hallucination_widget = QWidget()
        h_lay = _VL(hallucination_widget)
        h_lay.setContentsMargins(20, 16, 20, 16)
        h_lay.setSpacing(10)
        h_title = _QL("🛡️ Hallucination Audit")
        h_title.setObjectName("H2")
        h_lay.addWidget(h_title)
        h_desc = _QL("Check bullets against source text using 4 signals: verbatim match, "
                     "semantic similarity, content-word overlap, and number/quote verification.\n\n"
                     "Paste source text and bullets below, then click Audit.")
        h_desc.setObjectName("Caption")
        h_desc.setWordWrap(True)
        h_lay.addWidget(h_desc)
        h_btn = _QPB("🛡️ Open Hallucination Audit Dialog")
        h_btn.setObjectName("Primary")
        h_btn.clicked.connect(lambda: self._open_hallucination_audit())
        h_lay.addWidget(h_btn)
        h_lay.addStretch()
        hallucination_scroll.setWidget(hallucination_widget)
        self.tab_widget.addTab(
            hallucination_scroll, icon("shield", p.text_secondary, 16), "Hallucination Audit"
        )

        # Refresh views when their tab is switched to
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        return self.tab_widget

    def _on_tab_changed(self, idx: int):
        """V4.3.0: Refresh the Queue view's count badge when its tab opens.
        V7.4.0: RAG refresh removed (tab deleted).
        V10.28.0: Quarantine auto-reloads its drops.jsonl when opened.
        V13.31.0: Podcast Maker tab removed."""
        widget = self.tab_widget.widget(idx)
        if widget is None:
            return
        # Convert / Queue / Output Scanner are wrapped in QScrollArea — unwrap.
        inner = widget.widget() if isinstance(widget, QScrollArea) else widget
        if inner is getattr(self, "queue_view", None):
            self.queue_view.refresh()
        if inner is getattr(self, "quarantine_view", None):
            # Auto-detect the latest book's drops.jsonl if nothing is loaded,
            # then refresh the table.
            try:
                self.quarantine_view._reload()
            except Exception:
                logger.debug("quarantine reload failed", exc_info=True)
            if not getattr(self.quarantine_view, "_drops_path", None):
                try:
                    self.quarantine_view._auto_detect()
                except Exception:
                    logger.debug("quarantine auto-detect failed", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════════
    def _open_hallucination_audit(self) -> None:
        """V13.31.0 (#1): Open the Hallucination Audit dialog."""
        from ui_qt.views.service_dialogs.base_dialog import HallucinationAuditDialog
        dlg = HallucinationAuditDialog(self.controller, self)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()

    def _open_about_system(self) -> None:
        from ui_qt.views.about_system_dialog import AboutSystemDialog
        dlg = AboutSystemDialog(self.controller, self)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()

    def _open_validate(self) -> None:
        dlg = ValidateDialog(self.controller, self)
        self._validate_dialog = dlg
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        # (The post-exec line below touches self, not dlg — safe to delete the dialog.)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        self._validate_dialog = None

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.controller, self)
        self._settings_dialog = dlg
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        # (The post-exec lines below touch self, not dlg — safe to delete the dialog.)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        # after the dialog closes, refresh UI prefs the user may have changed
        # (output-folder override, live-log visibility, engine indicator).
        self.convert_view.apply_ui_preferences()
        self._settings_dialog = None

    def _warn_ollama(self) -> None:
        """Non-blocking Ollama reachability check.

        V18.20.4.9 (W-b18 remainder): the worker's ``failed`` signal is now
        connected (fail-soft log) and the ref is kept on self — an
        unconnected ``failed`` meant a raising check died invisibly with
        the QObject GC'd mid-run.
        """

        def _check():
            try:
                from utils.network import is_ollama_reachable
                if not is_ollama_reachable():
                    from PySide6.QtCore import QMetaObject
                    from PySide6.QtCore import Qt as _Qt
                    QMetaObject.invokeMethod(
                        self, "_show_ollama_warning", _Qt.ConnectionType.QueuedConnection
                    )
            except Exception:
                logger.debug("UI op failed", exc_info=True)

        w = SimpleWorker(_check)
        self._ollama_check_worker = w  # Python ref (GC hazard)
        w.failed.connect(self._on_ollama_check_failed)
        w.start()

    def _on_ollama_check_failed(self, error: str) -> None:
        """W-b18 remainder: fail-soft — the startup check itself raised.
        No button lives on this path, so this is log-only."""
        logger.warning("Ollama reachability check failed: %s", error)

    @Slot()
    def _show_ollama_warning(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self, "Ollama not running",
            "Ollama does not appear to be running on localhost:11434.\n\n"
            "LLM OCR and summarisation will not work until Ollama is started.\n"
            "Start Ollama, then try your conversion.",
        )

    # ══════════════════════════════════════════════════════════════════════
    # Drag-and-drop — dropped PDFs go to the Queue view (any tab)
    # ══════════════════════════════════════════════════════════════════════
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    # V18.20.4.1 (P0 / W-b1): PDF only — the Queue view is the
                    # sole drop consumer and it is PDF-focused, matching the
                    # overlay's "Drop a PDF here" promise. (The old set
                    # .pdf/.md/.txt/.docx advertised drops that no live view
                    # could accept.)
                    if Path(url.toLocalFile()).suffix.lower() == ".pdf":
                        event.acceptProposedAction()
                        self._show_drop_overlay(True)
                        return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._show_drop_overlay(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self._show_drop_overlay(False)
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if not paths:
            event.ignore()
            return
        # V18.20.4.1 (P0 / W-b1): the Queue view is the ONLY live drop
        # consumer — route drops from ANY tab to it. The old non-Queue path
        # forwarded to ``convert_view.handle_dropped_file``, which crashed
        # with ``AttributeError: 'NoneType' object has no attribute
        # 'set_path'``: the Convert page's file picker was removed in
        # V11.0.0 (``input_picker = None``), the same V11.0.0-latent class
        # as the V18.20.3.14 ``_on_complete`` crash, and this path was
        # reachable on EVERY drop outside the Queue tab while the drop
        # overlay advertised the feature. The queue accepts PDFs (adds them
        # as queued books); anything else falls through to ignore().
        if self.queue_view.handle_dropped_files(paths):
            event.acceptProposedAction()
            return
        event.ignore()

    def _show_drop_overlay(self, show: bool) -> None:
        """Show/hide a translucent drop-zone overlay with 'Drop a PDF here' text."""
        if not hasattr(self, "_drop_overlay"):
            from PySide6.QtWidgets import QLabel
            p = theme_manager.palette
            self._drop_overlay = QLabel("📄  Drop a PDF here", self)
            self._drop_overlay.setAlignment(Qt.AlignCenter)
            self._drop_overlay.setStyleSheet(
                f"QLabel {{ background-color: rgba(200, 128, 90, 0.12);"
                f" color: {p.accent}; border: 3px dashed {p.accent};"
                f" border-radius: 16px; font-size: 16px; font-weight: 600; }}"
            )
            self._drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        if show:
            self._drop_overlay.setGeometry(self.rect())
            self._drop_overlay.raise_()
            self._drop_overlay.show()
        else:
            self._drop_overlay.hide()

    # ══════════════════════════════════════════════════════════════════════
    # Version (read from VERSION file alongside main.py)
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def _app_version() -> str:
        from pathlib import Path
        try:
            vf = Path(__file__).resolve().parent.parent / "VERSION"
            if vf.exists():
                return vf.read_text().strip() or "1.0.0"
        except Exception:
            logger.debug("version read failed", exc_info=True)
        return "1.0.0"

    # ══════════════════════════════════════════════════════════════════════
    # Geometry persistence
    # ══════════════════════════════════════════════════════════════════════
    def _restore_geometry(self) -> None:
        try:
            if _GEOMETRY_FILE.exists():
                with open(_GEOMETRY_FILE) as f:
                    data = json.load(f)
                # V13.31.0 (#3): 20% smaller default — was 760x540, now 608x432
                w = min(data.get("w", 608), 900)
                h = min(data.get("h", 432), 620)
                self.resize(w, h)
                if data.get("x") is not None and data.get("y") is not None:
                    self.move(data["x"], data["y"])
                    # V18.20.4.5 (T-b5): a monitor change since the last
                    # run can leave the restored position fully off-screen
                    # — the app looks "dead on launch". Validate the
                    # restored window against every screen; on failure fall
                    # back to the default size centered on the primary
                    # screen. (A maximized restore is always visible —
                    # showMaximized below — so the check is skipped.)
                    if not data.get("maximized"):
                        from PySide6.QtWidgets import QApplication
                        screens = [
                            (scr.availableGeometry().x(), scr.availableGeometry().y(),
                             scr.availableGeometry().width(), scr.availableGeometry().height())
                            for scr in QApplication.screens()
                        ]
                        if not restored_geometry_is_visible(
                                data["x"], data["y"], w, h, screens):
                            logger.warning(
                                "restored window geometry (%s,%s %sx%s) is not "
                                "visible on any screen — resetting to default",
                                data["x"], data["y"], w, h)
                            primary = QApplication.primaryScreen().availableGeometry()
                            self.resize(608, 432)
                            self.move(
                                primary.x() + max(0, (primary.width() - 608) // 2),
                                primary.y() + max(0, (primary.height() - 432) // 2),
                            )
                if data.get("maximized"):
                    self.showMaximized()
            else:
                self.resize(608, 432)
        except Exception:
            self.resize(608, 432)

    def _save_geometry(self) -> None:
        try:
            data = {
                "w": self.width(),
                "h": self.height(),
                "x": self.x(),
                "y": self.y(),
                "maximized": self.isMaximized(),
            }
            with open(_GEOMETRY_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            logger.debug("geometry save failed", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # Close handling — confirm if a conversion is running
    # ══════════════════════════════════════════════════════════════════════
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        # ask before killing a running conversion or queue
        try:
            is_conv = self.controller.is_converting()
            is_queue = hasattr(self, "queue_view") and self.queue_view.is_running()
            if is_conv or is_queue:
                from PySide6.QtWidgets import QMessageBox
                what = "queue" if is_queue else "conversion"
                ret = QMessageBox.question(
                    self, "Processing in progress",
                    f"A {what} is still running. Cancel it and quit?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    event.ignore()
                    return
                if is_queue:
                    self.queue_view.stop()
                else:
                    self.controller.cancel_conversion()
        except Exception:
            logger.debug("close-event cancel failed", exc_info=True)
        # V18.20.4.9 (T-b6): the conversion/queue workers are daemon
        # threads that WRITE output files — quitting without a join used
        # to kill one mid-write (atomic writes mitigate most, but the
        # W-c4 reset path can still be triggered). Stop was requested
        # above; now stop-and-wait + park, the T-b2 retire pattern.
        self._retire_conversion_workers()
        # persist settings + window geometry
        try:
            self.controller.settings.save()
        except Exception:
            logger.debug("settings save on close failed", exc_info=True)
        self._save_geometry()
        super().closeEvent(event)

    def _retire_conversion_workers(self, wait_ms: int = 2000) -> None:
        """V18.20.4.9 (T-b6): stop-and-wait for the daemon writer threads.

        The queue worker (``queue_view._worker_thread``, daemon=True) and
        the controller's conversion thread
        (``controller.current_conversion_thread``, daemon=True — the SAME
        object while a queue runs) are the two background writers a
        cancel-and-quit used to kill mid-write. The cancel was already
        requested by the confirmation branch above; here we join each
        (best-effort, ``wait_ms``) and park any still-winding-down thread
        on ``self._retired_workers`` so its last reference is never
        dropped while it is alive (the T-b2 retire pattern).
        """
        candidates: list[threading.Thread] = []
        try:
            queue_thread = getattr(self.queue_view, "_worker_thread", None) \
                if hasattr(self, "queue_view") else None
            if queue_thread is not None and queue_thread.is_alive():
                candidates.append(queue_thread)
            conv_thread = getattr(self.controller, "current_conversion_thread", None)
            if (conv_thread is not None and conv_thread.is_alive()
                    and conv_thread not in candidates):
                candidates.append(conv_thread)
        except Exception:
            logger.debug("worker retire scan failed", exc_info=True)
            return
        if not candidates:
            return
        retired: list[threading.Thread] = []
        for t in candidates:
            try:
                t.join(wait_ms)
            except Exception:
                pass  # best-effort — never hang the close on a stuck writer
            if t.is_alive():
                retired.append(t)
        # Park still-running threads (T-b2 retire list). They are daemons,
        # so if the process exits anyway they die like before — but with
        # the join, the common case is a clean finish of the in-flight
        # write instead of a mid-write kill.
        self._retired_workers = retired
        if retired:
            logger.warning(
                "conversion worker(s) still writing after the %sms retire "
                "wait — parked %d thread(s) on close (T-b6)",
                wait_ms, len(retired))


# ── Public entry point ──────────────────────────────────────────────────────

# V18.1 (B6): single-instance lock state. Held at module scope so the
# QLocalServer isn't garbage-collected (which would close the socket and
# silently allow a second instance to start).
_INSTANCE_KEY = "elixir_single_instance_v18"
_lock_server = None
_lock_socket = None


def _acquire_single_instance_lock(app) -> bool:
    """Try to become the sole running instance.

    Returns True if this process should continue starting the GUI. Returns
    False (and ``sys.exit(0)``s) if another instance is already running —
    in that case we send a ``FOCUS`` message so the existing window can
    bring itself to the front.

    Implemented with a Qt ``QLocalServer``/``QLocalSocket`` pair so we
    don't add a platform-specific dep (named pipes / fcntl / win32 mutex).
    If PySide6.QtNetwork isn't installed, the lock is skipped with a
    WARNING — better to start the app unguarded than to crash on import.
    """
    import sys
    try:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
    except Exception as _e:  # pragma: no cover — env-specific
        logging.getLogger(__name__).warning(
            "single-instance lock disabled (PySide6.QtNetwork unavailable: %s) "
            "— running multiple instances may corrupt output dirs", _e,
        )
        return True

    global _lock_server, _lock_socket
    _lock_socket = QLocalSocket()
    _lock_socket.connectToServer(_INSTANCE_KEY)
    if _lock_socket.waitForConnected(200):
        # Another instance is running — ask it to focus, then exit.
        _lock_socket.write(b"FOCUS")
        _lock_socket.flush()
        _lock_socket.waitForBytesWritten(500)
        sys.exit(0)
    # No existing instance — start the server so future launches detect us.
    QLocalServer.removeServer(_INSTANCE_KEY)
    _lock_server = QLocalServer()
    _lock_server.listen(_INSTANCE_KEY)
    return True


def run() -> None:
    """Create the QApplication, apply the theme, and show the main window."""
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    # V18.1 (B6): enforce single-instance — launching twice can corrupt the
    # same output dir / Ollama model state. Must come AFTER QApplication is
    # created because QLocalServer needs a QCoreApplication.
    _acquire_single_instance_lock(app)

    theme_manager.apply(app)

    controller = Controller()
    window = ElixirWindow(controller)
    window.show()
    sys.exit(app.exec())
