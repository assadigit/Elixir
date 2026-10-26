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
from ui_qt.components.llm_lights import build_status_lights
from ui_qt.components.modal_button_fit import install_modal_button_fit
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings import SettingsDialog
from ui_qt.theme import theme_manager
from ui_qt.views.convert_view import ConvertView
from ui_qt.views.output_scanner_view import OutputScannerView
from ui_qt.views.quarantine_view import QuarantineView
from ui_qt.views.queue_view import QueueView
from ui_qt.views.validate_dialog import ValidateDialog
from utils.geometry import (
    DEFAULT_H,
    DEFAULT_W,
    GEOMETRY_SCHEMA_VERSION,
    restored_geometry_is_visible,
    sanitize_restore_plan,
)
from utils.settings import user_data_dir
from utils.single_instance import focus_ack_indicates_visible, primary_reply

logger = logging.getLogger(__name__)


# PACKAGING (build_installer.py): resolved via user_data_dir() so the frozen
# (installed) build reads/writes %LOCALAPPDATA%\Elixir\window_geometry.json
# instead of ~/.elixir (source behavior unchanged).
_GEOMETRY_FILE = user_data_dir() / "window_geometry.json"


class ElixirWindow(QMainWindow):
    """Top-level window for the PySide6 UI."""

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"Elixir  ·  v{self._app_version()}")
        # V0.6.68: the ORIGINAL container size is back. V13.31.0 had shrunk
        # the default 20% ("was 760x540, now 608x432 — more compact"), and
        # the 2026-10-26 field report landed on exactly that: a fresh
        # install has no saved geometry, so every new user met the compact
        # default — "not in the original container size … very compact and
        # small … it has scroll". The 760x540 default (and the 1600x1000
        # restore ceiling) live in utils.geometry — the single source of
        # truth; this 560x400 minimum only keeps small screens usable.
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

        # V0.6.69: the live local-LLM status lights + their poll loop —
        # this REPLACES the removed startup "Ollama not running" warning
        # dialog (a missing local server is a state to show, never a
        # load-time error to nag with; the 2026-10-26 field report).
        self._llm_poll_timer = None
        self._llm_probe_worker = None
        self._llm_endpoints_snapshot = None
        self._topbar_static_min = None
        self._setup_llm_lights_monitoring()

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

        # V0.6.69: live local-LLM status lights — one per locally-famous
        # client (Ollama, llama.cpp, LM Studio): green = answered the last
        # probe, gray = offline, amber = still checking. Re-probed every
        # few seconds for the whole session (see
        # _setup_llm_lights_monitoring) — the polite replacement for the
        # old startup "Ollama not running" error dialog.
        self.llm_lights, _ = build_status_lights()
        if self.llm_lights is not None:
            lay.addWidget(self.llm_lights)
            lay.addSpacing(8)

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
        self._top_bar = bar  # V0.6.69: the lights' budget measures against it
        return bar

    def _refresh_top_bar_icons(self) -> None:
        p = theme_manager.palette
        # sun icon in dark mode (click → light), moon in light mode (click → dark)
        self.theme_btn.setIcon(icon("sun" if p.is_dark else "moon", p.text_primary, 16))
        # V13.31.0 (#12): info icon instead of sliders-horizontal
        self.about_btn.setIcon(icon("info", p.text_primary, 16))
        self.settings_btn.setIcon(icon("settings", p.text_primary, 16))
        # V0.6.69: the lights re-paint from the CURRENT palette
        if getattr(self, "llm_lights", None) is not None:
            self.llm_lights.refresh_theme()

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
            self,
            "Select folder containing book conversions to merge",
            "",
            QFileDialog.ShowDirsOnly,
        )
        if not folder:
            return

        # Find all book subdirectories
        base = Path(folder)
        book_dirs = [d for d in base.iterdir() if d.is_dir() and (d / "summaries").exists()]
        if not book_dirs:
            QMessageBox.information(
                self,
                "No books found",
                f"No book conversion directories found in: {folder}\n\n"
                f"Each book should have a 'summaries' subfolder.",
            )
            return

        # Let user select output location
        output_folder = QFileDialog.getExistingDirectory(
            self,
            "Select output folder for merged result",
            str(base),
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
                logger.warning("library merge raised — traceback follows", exc_info=True)
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
            QMessageBox.information(
                self, "Merge complete", f"Merged {len(book_dirs)} books.\nResult: {result}"
            )
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
        h_desc = _QL(
            "Check bullets against source text using 4 signals: verbatim match, "
            "semantic similarity, content-word overlap, and number/quote verification.\n\n"
            "Paste source text and bullets below, then click Audit."
        )
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

    # ══════════════════════════════════════════════════════════════════════
    # V0.6.69 — live local-LLM status lights (the poll loop)
    # ══════════════════════════════════════════════════════════════════════
    def _setup_llm_lights_monitoring(self) -> None:
        """Actively watch for locally-running LLM servers (Ollama,
        llama.cpp, LM Studio) and paint the verdict on the top-bar lights.

        Replaces the pre-V0.6.69 startup path — a background
        ``is_ollama_reachable`` check that popped a modal "Ollama not
        running" QMessageBox at load. The 2026-10-26 field report retired
        that design: a missing local server is an ordinary state to SHOW
        (a gray light), not an error to raise before the user has done
        anything, and the lights must notice a server STARTED mid-session
        (green on the next tick). The loop:

        * every ``LLM_LIGHTS_POLL_INTERVAL_S`` seconds: snapshot the
          endpoints on THIS (main) thread, then hand a SimpleWorker the
          frozen spec — the probe layer never touches settings off-thread
          and never raises;
        * the probes are loopback GETs with the 2 s subsecond budget (a
          dead port answers instantly) and deliberately bypass the
          routing layer's 30 s probe cache — a status light must be FRESH;
        * verdicts are applied on the main thread via the worker's queued
          ``finished`` signal; a probe that EXPLODES is log-debug only
          (the lights keep the last known state — no dialog, ever).
        """
        if getattr(self, "llm_lights", None) is None:
            return  # the widget failed to build — no lights, no polling
        try:
            from PySide6.QtCore import QTimer

            from core.system.local_llm_monitor import (
                LLM_LIGHTS_POLL_INTERVAL_S,
                probe_local_llm_clients,
                snapshot_endpoints,
            )
        except Exception:
            logger.warning("local-LLM lights monitoring unavailable", exc_info=True)
            return

        def _probe():
            # Worker thread — the frozen snapshot + pure probes only.
            return probe_local_llm_clients(self._llm_endpoints_snapshot)

        def _tick() -> None:
            prev = self._llm_probe_worker
            if prev is not None:
                try:
                    if prev.is_running():
                        return  # previous probe still in flight — skip
                except RuntimeError:
                    pass  # the finished worker was auto-deleted — replace
                self._llm_probe_worker = None
            try:
                # Main-thread read of the configured endpoints (DESIGN
                # RULE 2 in core.system.local_llm_monitor).
                self._llm_endpoints_snapshot = snapshot_endpoints(self.controller.settings)
            except Exception:
                logger.debug("llm-lights endpoint snapshot failed", exc_info=True)
                return
            worker = SimpleWorker(_probe)
            self._llm_probe_worker = worker  # Python ref (GC hazard)
            worker.finished.connect(self._on_llm_probe_finished)
            worker.failed.connect(self._on_llm_probe_failed)
            worker.start()

        timer = QTimer(self)
        timer.setInterval(LLM_LIGHTS_POLL_INTERVAL_S * 1000)
        timer.timeout.connect(_tick)
        self._llm_poll_timer = timer
        timer.start()
        _tick()  # first verdict immediately — the splash is barely closed

    @Slot(object)
    def _on_llm_probe_finished(self, statuses) -> None:
        self._llm_probe_worker = None
        lights = getattr(self, "llm_lights", None)
        if lights is not None and statuses:
            lights.apply_statuses(statuses)

    @Slot(str)
    def _on_llm_probe_failed(self, error: str) -> None:
        """Fail-soft (the W-b18 lesson, kept): keep the last painted
        verdict, log QUIETLY — a dead probe repeating every few seconds
        must never spam the log the way a warning would."""
        self._llm_probe_worker = None
        logger.debug("local-LLM liveness probe failed: %s", error)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._adapt_llm_lights()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        # V0.6.69: at first real paint the fonts/QSS are polished, so THIS
        # is the moment to (re)measure what the top bar needs without the
        # lights — the pre-show estimate can be off by the QSS font sizes.
        self._topbar_static_min = None
        self._adapt_llm_lights()

    def _adapt_llm_lights(self) -> None:
        """Hand the lights whatever width the top bar can spare; the
        widget picks the richest mode that fits (names → dots → one dot).
        Measured, not guessed: ``_topbar_static_min`` is the bar's own
        minimumSizeHint with the lights hidden."""
        lights = getattr(self, "llm_lights", None)
        if lights is None:
            return
        try:
            if self._topbar_static_min is None:
                bar = getattr(self, "_top_bar", None)
                if bar is None:
                    return
                lights.setVisible(False)
                try:
                    self._topbar_static_min = bar.minimumSizeHint().width()
                finally:
                    lights.setVisible(True)
            # 22 px cushion: the layout spacing around the lights group.
            lights.set_budget(self.width() - (self._topbar_static_min or 700) - 22)
        except Exception:
            logger.debug("llm-lights adapt failed", exc_info=True)

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
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
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
        # V0.6.67: the off-screen decision logic lives in the pure
        # utils.geometry.sanitize_restore_plan (unit-testable, Qt-free).
        # Two fixes over V18.20.4.5: (1) the visibility validation now
        # applies to MAXIMIZED restores too — the old code skipped it, so a
        # window saved as "maximized on monitor #2" maximized onto a
        # detached monitor and stayed invisible forever; (2) whenever there
        # is no validated saved position the window is CENTERED on the
        # primary screen instead of trusting Qt's default placement.
        from PySide6.QtWidgets import QApplication

        try:
            data = {}
            if _GEOMETRY_FILE.exists():
                with open(_GEOMETRY_FILE) as f:
                    data = json.load(f)
            plan = sanitize_restore_plan(data, _screens_rects(QApplication.instance()))
            if plan["rejected"] and "x" in data:  # T-b5's warning, kept alive
                logger.warning(
                    "restored window geometry (%s,%s %sx%s) is not "
                    "visible on any screen — resetting to default",
                    data.get("x"),
                    data.get("y"),
                    plan["w"],
                    plan["h"],
                )
            self.resize(plan["w"], plan["h"])
            if plan["move_to"] is not None:
                self.move(*plan["move_to"])
            elif plan["center_default"]:
                self._center_on_primary(plan["w"], plan["h"])
            if plan["maximized"]:
                self.showMaximized()
        except Exception:
            self.resize(DEFAULT_W, DEFAULT_H)
            self._center_on_primary(DEFAULT_W, DEFAULT_H)

    def _center_on_primary(self, w: int, h: int) -> None:
        """V0.6.67: deterministic default placement — centered on the
        primary screen's work area (the screen with the taskbar, i.e. the
        one the user is looking at). Best-effort."""
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None or app.primaryScreen() is None:
                return
            primary = app.primaryScreen().availableGeometry()
            self.move(
                primary.x() + max(0, (primary.width() - w) // 2),
                primary.y() + max(0, (primary.height() - h) // 2),
            )
        except Exception:
            logger.debug("default centering failed", exc_info=True)

    def _save_geometry(self) -> None:
        # V0.6.67: never persist minimized coordinates (Windows reports
        # -32000 for a minimized window — restoring them next launch puts
        # the window off-screen), and save the NORMAL geometry when
        # maximized so the restore target is the window's remembered
        # on-screen rect, not the current maximized position.
        try:
            if self.isMinimized():
                return  # keep the previous (good) file
            geo = self.normalGeometry() if self.isMaximized() else self.frameGeometry()
            data = {
                "w": self.width(),
                "h": self.height(),
                "x": geo.x(),
                "y": geo.y(),
                "maximized": self.isMaximized(),
                # V0.6.68: the schema stamp marks this save as POST-migration —
                # a deliberate hand-resize to the old compact default is a real
                # preference from now on (unstamped saves at exactly 608x432
                # were "never resized" and receive the restored 760x540 default;
                # see utils.geometry's LEGACY_COMPACT_W note).
                "v": GEOMETRY_SCHEMA_VERSION,
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
                    self,
                    "Processing in progress",
                    f"A {what} is still running. Cancel it and quit?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
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
        # V0.6.69: stop the local-LLM liveness poll loop — no probes after
        # the window is gone (an in-flight worker's queued verdict simply
        # lands on a dead receiver and is discarded by Qt).
        try:
            if getattr(self, "_llm_poll_timer", None) is not None:
                self._llm_poll_timer.stop()
        except Exception:
            pass
        # V18.20.4.12 (W-c12): release cached TTS engines (subprocesses +
        # VRAM) before process teardown. Never-raise: shutdown must not be
        # blocked by a stuck engine (engines have their own quit→wait→kill
        # teardown contract).
        try:
            from core.tts.engine_cache import clear_cache

            clear_cache()
        except Exception:
            pass
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
            queue_thread = (
                getattr(self.queue_view, "_worker_thread", None)
                if hasattr(self, "queue_view")
                else None
            )
            if queue_thread is not None and queue_thread.is_alive():
                candidates.append(queue_thread)
            conv_thread = getattr(self.controller, "current_conversion_thread", None)
            if conv_thread is not None and conv_thread.is_alive() and conv_thread not in candidates:
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
                wait_ms,
                len(retired),
            )


# ── Public entry point ──────────────────────────────────────────────────────

# V18.1 (B6): single-instance lock state. Held at module scope so the
# QLocalServer isn't garbage-collected (which would close the socket and
# silently allow a second instance to start).
_INSTANCE_KEY = "elixir_single_instance_v18"
_lock_server = None
_lock_socket = None
# V0.6.65: the primary instance's main window, set by run() before exec().
# The lock server's FOCUS handler raises THIS window when a second launch
# asks for attention — the V18.1 protocol promised that, but the server
# side was never wired: a second double-click wrote FOCUS into a pipe
# nobody read and exited silently. On a machine where the FIRST launch was
# still starting (or hung), every later click did nothing at all — one
# face of the V0.6.64 "installed … doesn't open" field report.
_primary_window = None


def _step(name: str) -> None:
    """V0.6.67: startup.log visibility from the UI layer (the launcher
    guard's step log — best-effort, never raises, no-op in tests that never
    armed the guard)."""
    try:
        from core.system.launcher_guard import startup_step

        startup_step(name)
    except Exception:
        pass


def _screens_rects(app) -> list[tuple[int, int, int, int]]:
    """The CURRENT attached screens as (x, y, w, h) available-geometry
    tuples (taskbar-free work areas). Empty when app/Qt is unavailable —
    every consumer degrades fail-safe (centered default / rescue off)."""
    try:
        if app is None:
            return []
        return [
            (
                scr.availableGeometry().x(),
                scr.availableGeometry().y(),
                scr.availableGeometry().width(),
                scr.availableGeometry().height(),
            )
            for scr in app.screens()
        ]
    except Exception:
        return []


def _window_is_onscreen(window) -> bool:
    """V0.6.67: True when the window's FRAME overlaps any attached screen
    by at least 100×100 px (a window grazing an edge is still effectively
    invisible)."""
    try:
        from PySide6.QtWidgets import QApplication

        frame = window.frameGeometry()
        return restored_geometry_is_visible(
            frame.x(),
            frame.y(),
            frame.width(),
            frame.height(),
            _screens_rects(QApplication.instance()),
            min_overlap_area=100 * 100,
        )
    except Exception:
        return False  # fail-safe: report not-visible so callers act


def _ensure_window_onscreen(window) -> bool:
    """V0.6.67 — THE POST-SHOW GUARANTEE: a window stranded off-screen
    (restored onto a detached monitor, DPI-shifted, whatever the cause) is
    moved to the center of the PRIMARY screen's work area, preserving its
    maximized state.  Returns True when a rescue move was performed.

    Field evidence (2026-10-25 diagnostics): the first launch reached
    exec() with a shown-but-invisible window and every later double-click
    deferred to it via the FOCUS protocol — "the app doesn't open" while a
    healthy invisible window ran.  Whatever put the window off-screen, this
    check runs on the FINAL, post-show position and is therefore
    cause-agnostic.  Best-effort — never raises."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or window is None:
            return False
        frame = window.frameGeometry()
        if restored_geometry_is_visible(
            frame.x(),
            frame.y(),
            frame.width(),
            frame.height(),
            _screens_rects(app),
            min_overlap_area=100 * 100,
        ):
            return False
        logger.warning(
            "main window is off-screen (frame %s, screens %s) — moving it onto the primary screen",
            frame.getRect(),
            _screens_rects(app),
        )
        was_maximized = window.isMaximized()
        if was_maximized:
            window.showNormal()  # un-maximize from the phantom screen first
        primary = app.primaryScreen().availableGeometry()
        window.move(
            primary.center().x() - window.width() // 2,
            primary.center().y() - window.height() // 2,
        )
        if was_maximized:
            window.showMaximized()  # re-maximize on the (real) primary screen
        return True
    except Exception:
        logger.debug("on-screen rescue failed", exc_info=True)
        return False


def _on_lock_connection() -> None:
    """V0.6.65: primary side of the single-instance protocol.

    Answers ``FOCUS`` by raising the main window, then replies — V0.6.67:
    HONESTLY — whether its window is actually on a visible screen AFTER a
    self-heal attempt, so a stranded-off-screen primary can no longer
    swallow every later double-click (the 2026-10-25 field report: the
    primary ACKed, raised an invisible window, and the second instance
    exited into nothing). Best-effort — never raises.
    """
    if _lock_server is None:
        return
    try:
        sock = _lock_server.nextPendingConnection()
        if sock is None:
            return
        try:
            if sock.waitForReadyRead(300):
                if b"FOCUS" in bytes(sock.readAll()) and _primary_window is not None:
                    # V0.6.67: heal FIRST — never raise an invisible window.
                    _ensure_window_onscreen(_primary_window)
                    if _primary_window.isMinimized():
                        _primary_window.showNormal()
                    _primary_window.raise_()
                    _primary_window.activateWindow()
                    sock.write(primary_reply(_window_is_onscreen(_primary_window)))
                else:
                    sock.write(b"OK")  # no window yet (still starting) — legacy reply
            else:
                sock.write(b"OK")
            sock.flush()
            sock.waitForBytesWritten(500)
        finally:
            sock.disconnectFromServer()
    except Exception:
        logger.debug("single-instance FOCUS handling failed", exc_info=True)


def _acquire_single_instance_lock(app) -> bool:
    """Try to become the sole running instance.

    Returns True if this process should continue starting the GUI; exits
    the process when a live primary instance ACKs.

    Protocol (V0.6.67 — the honest-ACK release):

    * connect to the existing server → send ``FOCUS`` → wait up to 2.5 s
      for the reply.  ``OK-VISIBLE`` (or the legacy ``OK``) → the primary
      raised a window that is ON a screen; exit quietly.
      ``OK-INVISIBLE`` → the primary answered but its window is stranded
      off-screen even after its self-heal — exiting here is exactly how
      "the app stopped opening" becomes permanent (the 2026-10-25 field
      report).  Take the name over and keep starting; our own window is
      force-checked on-screen after show().
    * NO reply → the primary is a hung/zombie process whose event loop
      cannot answer — same takeover as before (V0.6.65).
    * No server at all → the normal first launch: listen and continue.

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
            "— running multiple instances may corrupt output dirs",
            _e,
        )
        return True

    global _lock_server, _lock_socket
    _lock_socket = QLocalSocket()
    _lock_socket.connectToServer(_INSTANCE_KEY)
    if _lock_socket.waitForConnected(300):
        # A primary exists — ask it to focus, then wait for its reply.
        _lock_socket.write(b"FOCUS")
        _lock_socket.flush()
        _lock_socket.waitForBytesWritten(500)
        reply = b""
        if _lock_socket.waitForReadyRead(2500):
            reply = bytes(_lock_socket.readAll())
        if focus_ack_indicates_visible(reply):
            _step("focus handed to the running instance — exiting")
            sys.exit(0)  # the primary raised a window that is on a screen
        logger.warning(
            "single-instance primary replied %r (no visible window) — "
            "taking over the instance lock; two windows may briefly coexist",
            reply or b"(no reply)",
        )
        _step(f"primary did not present a visible window ({reply!r}) — taking over")
    # No live primary (or a zombie one) — own the name so future launches
    # detect us, and answer FOCUS for them.
    QLocalServer.removeServer(_INSTANCE_KEY)
    _lock_server = QLocalServer()
    _lock_server.newConnection.connect(_on_lock_connection)  # V0.6.65
    if not _lock_server.listen(_INSTANCE_KEY):
        # Name held by something we could not remove — never trap the user
        # out of their app; run unguarded (same degradation as the
        # QtNetwork-missing path above).
        logger.warning("single-instance lock could not listen (%s)", _lock_server.errorString())
    return True


class _StartupSplash(QWidget):
    """V0.6.65: instant liveness feedback while the app builds.

    Shown the moment the single-instance lock is acquired and closed when
    the main window appears, so a slow first launch (cold disk, antivirus
    scanning every bundled DLL as it loads) shows liveness instead of a
    silent desktop — the other face of the V0.6.64 "doesn't open at all"
    field report (the app WAS starting; it just took long enough to look
    dead, and every extra double-click made it worse via the broken
    single-instance path). V0.6.68: the plain "◆ Elixir is starting…"
    text label became the branded splash the 2026-10-26 field report
    asked for — the app icon, a constant "Elixir is loading…" label (no
    technical stage names like "Loading interface"), and an indeterminate
    progress bar. Still deliberately dependency-free (plain widgets,
    fixed palette, no theme imports — the theme is applied only moments
    later) and best-effort — constructed inside run()'s try/except so a
    splash failure can never block startup.
    """

    _TEXT = "Elixir is loading…"

    def __init__(self, app) -> None:
        from PySide6.QtWidgets import QProgressBar

        super().__init__(None)
        self._app = app
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("StartupSplash")
        self.setStyleSheet(
            "#StartupSplash { background: #23242b; "
            "border: 1px solid #3a3d47; border-radius: 14px; } "
            "QLabel { background: transparent; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 26)
        lay.setSpacing(14)

        icon_label = QLabel()
        logo = self._icon_pixmap(76)
        if logo is not None:
            icon_label.setPixmap(logo)
            lay.addWidget(icon_label, 0, Qt.AlignHCenter)

        text = QLabel(self._TEXT)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet("color: #eceef4; font-size: 15px; font-weight: 600;")
        lay.addWidget(text, 0, Qt.AlignHCenter)
        self._text = text  # handle for tests/pinning (the label itself never changes)

        bar = QProgressBar()
        bar.setRange(0, 0)  # indeterminate — animated liveness while the UI builds
        bar.setTextVisible(False)
        bar.setFixedSize(230, 4)
        bar.setStyleSheet(
            "QProgressBar { background: #3a3d47; border: none; border-radius: 2px; } "
            "QProgressBar::chunk { background: #d8aa78; border-radius: 2px; }"
        )
        lay.addWidget(bar, 0, Qt.AlignHCenter)

        self.adjustSize()
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.show()
        app.processEvents()

    def pump(self) -> None:
        """Process events now — keeps the indeterminate bar animating while
        the main window is constructed (no event loop is running yet; the
        V0.6.65 ``message()`` repaint hook survives as this text-less pump
        because the label deliberately never changes)."""
        self._app.processEvents()

    @staticmethod
    def _icon_pixmap(size: int):
        """The app icon (``assets/elixir.png``, ``.ico`` as fallback) scaled
        to ``size``, or None — an omitted icon must never block the splash.
        Best-effort by contract (called inside run()'s try/except anyway)."""
        try:
            from PySide6.QtGui import QPixmap

            from app_paths import bundled_icon_path, resource_path

            for candidate in (resource_path("assets", "elixir.png"), bundled_icon_path()):
                if candidate is None:
                    continue
                pm = QPixmap(str(candidate))
                if not pm.isNull():
                    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception:
            return None
        return None


def run() -> None:
    """Create the QApplication, apply the theme, and show the main window."""
    import sys

    global _primary_window

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    # PACKAGING: give the window/taskbar the bundled app icon (assets/elixir.ico)
    # when present. Best-effort — from source it simply picks up the committed
    # icon; nothing changes when the file is absent.
    try:
        from app_paths import bundled_icon_path

        _icon_path = bundled_icon_path()
        if _icon_path is not None:
            from PySide6.QtGui import QIcon

            app.setWindowIcon(QIcon(str(_icon_path)))
    except Exception:
        logger.debug("window icon not applied", exc_info=True)

    # V18.1 (B6): enforce single-instance — launching twice can corrupt the
    # same output dir / Ollama model state. Must come AFTER QApplication is
    # created because QLocalServer needs a QCoreApplication.
    _acquire_single_instance_lock(app)

    theme_manager.apply(app)

    # V0.6.3: fit every modal's buttons to their full label width. The
    # success modal's "📂 Open File Location" clipped its tail whenever the
    # message text was short (QMessageBox can settle below its own sizeHint
    # when the text label is narrow). Installed here — one call covers every
    # message box the process will ever show.
    install_modal_button_fit(app)

    # V0.6.65: instant "starting…" feedback (see _StartupSplash). Placed
    # AFTER the single-instance lock so a blocked second launch never
    # flashes a splash of its own.
    splash = None
    try:
        splash = _StartupSplash(app)
    except Exception:
        logger.debug("startup splash unavailable", exc_info=True)

    controller = Controller()
    if splash is not None:
        splash.pump()  # V0.6.68: repaint/keep the bar animating — the label
        # stays the branded "Elixir is loading…" (no technical stage names)
    window = ElixirWindow(controller)
    _primary_window = window  # V0.6.65: the lock server raises this on FOCUS
    window.show()
    # V0.6.67 — the post-show guarantee: whatever put the window off-screen
    # (a restored geometry aimed at a detached monitor, a DPI shift, Qt
    # default placement), exec() is only entered with a window that is
    # actually ON a screen — and it comes to the front on launch.
    _ensure_window_onscreen(window)
    window.raise_()
    window.activateWindow()
    _step(
        f"window shown — frame={window.frameGeometry().getRect()} screens={len(_screens_rects(app))}"
    )
    if splash is not None:
        splash.close()
    rc = app.exec()
    # V0.6.67: any future "the app closed itself" report now shows whether
    # the event loop exited cleanly (and with what code) vs the process
    # dying inside it — the boundary used to be invisible in startup.log.
    _step(f"event loop finished (rc={rc})")
    sys.exit(rc)
