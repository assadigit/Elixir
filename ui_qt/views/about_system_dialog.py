"""About & System dialog — diagnostics surface reachable from the header
info button / the sidebar's About item.

Shows: app version, OS/Python, all library dependencies (✅/❌), Ollama
connection + every installed model with 🔍/📝 badges, and Tesseract/Poppler
paths with auto-detect + Browse.  This replaces the old "System" settings
tab — it's read-mostly diagnostics, not a setting, so it lives here rather
than cluttering the settings dialog.

M2 additions (UI/UX redesign, decisions Q2 + Q3):
  • the "Experimental tools…" section — the four destinations that left
    primary navigation when the fixed-sidebar dashboard shipped (Queue,
    Output Scanner, Bullet Audit, Hallucination Audit) stay fully
    functional and reachable from here via the window's navigation
    facade (they remain reachable through their existing routes too:
    drop-a-PDF → Queue, Packets output → Hallucination Audit).
    Hidden ≠ removed.
  • the FULL local-LLM lights (Ollama / llama.cpp / LM Studio, per-client
    dots + names + tooltips) — the header keeps ONE aggregate dot and the
    details live here. The window's poll loop feeds both sinks; opening
    the dialog shows the latest verdict immediately (the window hands
    over its last snapshot).
"""

from __future__ import annotations

import os
import platform
import shutil

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.icons import icon
from ui_qt.components.llm_lights import build_status_lights
from ui_qt.settings.widgets import make_form
from ui_qt.theme import theme_manager


def _detect_tesseract() -> str:
    found = shutil.which("tesseract")
    if found:
        return found
    if os.name == "nt":
        for cand in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.isfile(cand):
                return cand
    for cand in ("/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"):
        if os.path.isfile(cand):
            return cand
    return ""


def _detect_poppler() -> str:
    if shutil.which("pdftoppm"):
        return ""
    if os.name == "nt":
        for cand in (
            r"C:\poppler\Library\bin",
            r"C:\poppler-24.08.0\Library\bin",
            r"C:\poppler-23.11.0\Library\bin",
        ):
            if os.path.isdir(cand):
                return cand
    return ""


class _DepScanThread(QThread):
    done = Signal(dict)

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller

    def run(self) -> None:  # type: ignore[override]
        try:
            from utils.dependencies import DependencyChecker

            deps = DependencyChecker().check_all()
        except Exception:
            deps = {}
        self.done.emit(deps)


# M2 (decision Q2): the four destinations that left primary navigation.
# Labels are the EXACT former tab labels; blurbs are the existing
# user-facing descriptions (nothing invented). Clicking a row closes the
# dialog and switches the window's stack via the navigation facade.
_EXPERIMENTAL_TOOLS: tuple[tuple[str, str, str, str], ...] = (
    ("queue", "list-checks", "Queue", "Batch processing of multiple PDFs"),
    ("output_scanner", "scan", "Output Scanner", "Audit a book's output folder"),
    ("quarantine", "alert-triangle", "Bullet Audit", "Dropped-bullet audit & restore"),
    ("hallucination_audit", "shield", "Hallucination Audit", "Check bullets against source text"),
)


class AboutSystemDialog(QDialog):
    """Modal About + System diagnostics dialog."""

    # M2 (decision Q2): emitted with a page key when the user opens one of
    # the hidden experimental destinations — the window connects this to
    # its switch_to_page facade (the dialog never touches the stack).
    open_page = Signal(str)

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("About & System")
        self.resize(620, 540)  # V7.4.0: was 720x620 — compact
        self._scan_thread: _DepScanThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── About header ────────────────────────────────────────────────
        about = QGroupBox("About")
        al = QVBoxLayout(about)
        al.setSpacing(4)
        ver = self._app_version()
        al.addWidget(QLabel(f"<b>Elixir</b>  ·  v{ver}"))
        al.addWidget(QLabel("Local AI-powered PDF → Markdown + DOCX converter."))
        al.addWidget(QLabel("All processing happens on your machine — no API costs."))
        al.addWidget(QLabel("GUI: PySide6 (Qt 6)."))
        root.addWidget(about)

        # ── Local LLM servers (M2, decision Q3 — the full lights) ──
        llm_gb = QGroupBox("Local LLM servers")
        ll = QVBoxLayout(llm_gb)
        ll.setSpacing(4)
        self.llm_lights, _lights_err = build_status_lights()
        if self.llm_lights is not None:
            # The dialog has room — always the richest mode (dot + name per
            # client, verdict + endpoint in the tooltips). The header keeps
            # its single aggregate dot (decision Q3).
            self.llm_lights.set_budget(1000)
            ll.addWidget(self.llm_lights)
            cap = QLabel(
                "Live status of locally-running LLM clients — the header dot "
                "summarises these; re-checked every few seconds."
            )
        else:
            cap = QLabel("Status lights unavailable in this build.")
        cap.setObjectName("Caption")
        cap.setWordWrap(True)
        ll.addWidget(cap)
        root.addWidget(llm_gb)

        # ── Experimental tools (M2, decision Q2 — the fallback) ──
        exp_gb = QGroupBox("Experimental tools")
        el = QVBoxLayout(exp_gb)
        el.setSpacing(6)
        exp_note = QLabel(
            "Working views that left the main navigation — Queue also opens "
            "whenever you drop a PDF anywhere in the window."
        )
        exp_note.setObjectName("Caption")
        exp_note.setWordWrap(True)
        el.addWidget(exp_note)
        p = theme_manager.palette
        for page_key, glyph, label, blurb in _EXPERIMENTAL_TOOLS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            glyph_lbl = QLabel()
            glyph_lbl.setPixmap(icon(glyph, p.icon, 16).pixmap(16, 16))
            row.addWidget(glyph_lbl)
            row.addWidget(QLabel(f"<b>{label}</b> — {blurb}"), 1)
            open_btn = QPushButton("Open")
            open_btn.setObjectName("Compact")
            open_btn.clicked.connect(
                lambda checked=False, k=page_key: self._open_experimental(k)
            )
            row.addWidget(open_btn)
            el.addLayout(row)
        root.addWidget(exp_gb)

        # ── System paths ────────────────────────────────────────────────
        paths_gb = QGroupBox("System paths")
        pf = make_form()
        self.tesseract_edit = QLineEdit(
            controller.get_setting("paths.tesseract", "") or _detect_tesseract()
        )
        self.tesseract_edit.setPlaceholderText("Auto-detected · click Browse to override")
        tr = QHBoxLayout()
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(6)
        tr.addWidget(self.tesseract_edit, 1)
        tb = QPushButton("Browse…")
        tb.setObjectName("Compact")
        tb.clicked.connect(self._browse_tess)
        tr.addWidget(tb)
        td = QPushButton("Auto-detect")
        td.setObjectName("Compact")
        td.clicked.connect(lambda: self.tesseract_edit.setText(_detect_tesseract()))
        tr.addWidget(td)
        pf.addRow("Tesseract", tr)

        self.poppler_edit = QLineEdit(
            controller.get_setting("paths.poppler", "") or _detect_poppler()
        )
        self.poppler_edit.setPlaceholderText("Leave blank to use system PATH")
        pr = QHBoxLayout()
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(6)
        pr.addWidget(self.poppler_edit, 1)
        pb = QPushButton("Browse…")
        pb.setObjectName("Compact")
        pb.clicked.connect(self._browse_pop)
        pr.addWidget(pb)
        pd = QPushButton("Auto-detect")
        pd.setObjectName("Compact")
        pd.clicked.connect(lambda: self.poppler_edit.setText(_detect_poppler()))
        pr.addWidget(pd)
        pf.addRow("Poppler", pr)
        paths_gb.setLayout(pf)
        root.addWidget(paths_gb)

        # ── Dependencies + models ───────────────────────────────────────
        dep_gb = QGroupBox("Dependencies & models")
        dl = QVBoxLayout(dep_gb)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        head.addStretch()
        self.refresh_btn = QPushButton("  Refresh")
        self.refresh_btn.setObjectName("Compact")
        self.refresh_btn.setIcon(icon("refresh", theme_manager.palette.icon, 14))
        self.refresh_btn.clicked.connect(self._scan)
        head.addWidget(self.refresh_btn)
        dl.addLayout(head)
        self.info = QTextBrowser()
        self.info.setOpenExternalLinks(False)
        self.info.setMinimumHeight(220)
        self.info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        dl.addWidget(self.info)
        root.addWidget(dep_gb, 1)

        # save paths on close
        self._scan()

    # ── M2: the experimental-tools fallback (decision Q2) ──────────────
    def _open_experimental(self, page_key: str) -> None:
        """Close this dialog, then hand the page key to the window's
        navigation facade (the switch must not land behind a modal)."""
        self.accept()
        self.open_page.emit(page_key)

    # ── M2: the full-lights sink (decision Q3) ─────────────────────────
    def apply_llm_statuses(self, statuses) -> None:
        """Render the latest poll verdict on the full lights (the window's
        poll loop calls this while the dialog is open; the header's
        aggregate dot is fed in parallel)."""
        if self.llm_lights is not None and statuses:
            self.llm_lights.apply_statuses(statuses)

    @staticmethod
    def _app_version() -> str:
        try:
            from app_paths import resource_path  # V0.6.63: bundle-aware

            vf = resource_path("VERSION")
            if vf.exists():
                return vf.read_text().strip() or "1.0.0"
        except Exception:
            pass  # best-effort (UI — never crash)
        return "1.0.0"

    def _browse_tess(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate tesseract", "", "tesseract (tesseract tesseract.exe);;All files (*)"
        )
        if path:
            self.tesseract_edit.setText(path)

    def _browse_pop(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Locate Poppler 'bin' folder")
        if path:
            self.poppler_edit.setText(path)

    def _scan(self) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            return
        self.info.setPlainText("Scanning…")
        self._scan_thread = _DepScanThread(self.controller)
        self._scan_thread.done.connect(self._render)
        self._scan_thread.start()

    def _render(self, deps: dict) -> None:
        ver = self._app_version()
        lines: list[str] = []
        lines.append("APPLICATION")
        lines.append(f"  Elixir  v{ver}")
        lines.append(f"  OS: {platform.system()} {platform.release()}")
        lines.append(f"  Python: {platform.python_version()}")
        lines.append("")
        lines.append("CORE DEPENDENCIES")
        lines.append(f"  {'✅' if deps.get('markitdown') else '❌'} MarkItDown")
        lines.append(f"  {'✅' if deps.get('pdf2image') else '❌'} pdf2image")
        lines.append(f"  {'✅' if deps.get('python_docx') else '❌'} python-docx")
        lines.append(f"  {'✅' if deps.get('wordninja') else '❌'} wordninja")
        lines.append("")
        lines.append("OLLAMA")
        lines.append(f"  {'✅' if deps.get('ollama') else '❌'} installed")
        lines.append(
            f"  {'✅' if deps.get('ollama_running') else '❌'} server running (localhost:11434)"
        )
        models = deps.get("models", []) or []
        if models:
            # V0.6.7 (review-loop B4): the vision/text split routes through
            # the model_taxonomy SSOT (was a local copy of the keyword list).
            from core.llm.model_taxonomy import is_vision_model

            vision = [m for m in models if is_vision_model(m)]
            text = [m for m in models if not is_vision_model(m)]
            if vision:
                lines.append("  🔍 Vision / OCR models:")
                for m in vision:
                    lines.append(f"      • {m}")
            if text:
                lines.append("  📝 Text models:")
                for m in text:
                    lines.append(f"      • {m}")
        lines.append("")
        lines.append("SYSTEM TOOLS")
        lines.append(f"  {'✅' if deps.get('tesseract') else '❌'} Tesseract OCR")
        self.info.setPlainText("\n".join(lines))

    def accept(self) -> None:  # type: ignore[override]
        # persist system paths
        self.controller.update_setting("paths.tesseract", self.tesseract_edit.text().strip())
        self.controller.update_setting("paths.poppler", self.poppler_edit.text().strip())
        try:
            self.controller.settings.save()
        except Exception:
            pass  # best-effort (UI — never crash)
        super().accept()
