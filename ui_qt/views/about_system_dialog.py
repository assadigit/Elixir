"""About & System dialog — diagnostics surface reachable from the Tools menu.

Shows: app version, OS/Python, all library dependencies (✅/❌), Ollama
connection + every installed model with 🔍/📝 badges, and Tesseract/Poppler
paths with auto-detect + Browse.  This replaces the old "System" settings
tab — it's read-mostly diagnostics, not a setting, so it lives here rather
than cluttering the settings dialog.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

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
from ui_qt.settings.widgets import make_form


def _detect_tesseract() -> str:
    found = shutil.which("tesseract")
    if found:
        return found
    if os.name == "nt":
        for cand in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                     r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
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
        for cand in (r"C:\poppler\Library\bin", r"C:\poppler-24.08.0\Library\bin",
                     r"C:\poppler-23.11.0\Library\bin"):
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


class AboutSystemDialog(QDialog):
    """Modal About + System diagnostics dialog."""

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

        # ── System paths ────────────────────────────────────────────────
        paths_gb = QGroupBox("System paths")
        pf = make_form()
        self.tesseract_edit = QLineEdit(
            controller.get_setting("paths.tesseract", "") or _detect_tesseract()
        )
        self.tesseract_edit.setPlaceholderText("Auto-detected · click Browse to override")
        tr = QHBoxLayout(); tr.setContentsMargins(0, 0, 0, 0); tr.setSpacing(6)
        tr.addWidget(self.tesseract_edit, 1)
        tb = QPushButton("Browse…"); tb.setObjectName("Compact")
        tb.clicked.connect(self._browse_tess); tr.addWidget(tb)
        td = QPushButton("Auto-detect"); td.setObjectName("Compact")
        td.clicked.connect(lambda: self.tesseract_edit.setText(_detect_tesseract())); tr.addWidget(td)
        pf.addRow("Tesseract", tr)

        self.poppler_edit = QLineEdit(
            controller.get_setting("paths.poppler", "") or _detect_poppler()
        )
        self.poppler_edit.setPlaceholderText("Leave blank to use system PATH")
        pr = QHBoxLayout(); pr.setContentsMargins(0, 0, 0, 0); pr.setSpacing(6)
        pr.addWidget(self.poppler_edit, 1)
        pb = QPushButton("Browse…"); pb.setObjectName("Compact")
        pb.clicked.connect(self._browse_pop); pr.addWidget(pb)
        pd = QPushButton("Auto-detect"); pd.setObjectName("Compact")
        pd.clicked.connect(lambda: self.poppler_edit.setText(_detect_poppler())); pr.addWidget(pd)
        pf.addRow("Poppler", pr)
        paths_gb.setLayout(pf)
        root.addWidget(paths_gb)

        # ── Dependencies + models ───────────────────────────────────────
        dep_gb = QGroupBox("Dependencies & models")
        dl = QVBoxLayout(dep_gb)
        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0); head.setSpacing(8)
        head.addStretch()
        self.refresh_btn = QPushButton("  Refresh")
        self.refresh_btn.setObjectName("Compact")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 14))
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

    @staticmethod
    def _app_version() -> str:
        try:
            vf = Path(__file__).resolve().parent.parent.parent / "VERSION"
            if vf.exists():
                return vf.read_text().strip() or "1.0.0"
        except Exception:
            pass  # best-effort (UI — never crash)
        return "1.0.0"

    def _browse_tess(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate tesseract", "",
                                              "tesseract (tesseract tesseract.exe);;All files (*)")
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
        lines.append(f"  {'✅' if deps.get('ollama_running') else '❌'} server running (localhost:11434)")
        models = deps.get("models", []) or []
        if models:
            vision_kw = ("vl", "vision", "deepseek-ocr", "llava", "bakllava", "ocr", "olmo")
            vision = [m for m in models if any(k in m.lower() for k in vision_kw)]
            text = [m for m in models if not any(k in m.lower() for k in vision_kw)]
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
