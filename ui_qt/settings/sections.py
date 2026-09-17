"""Reusable section widgets for the settings sub-tabs.

Each section is a small QWidget with a header and a form, designed to be
composed into a sub-tab page.  Breaking the old monolithic tabs into these
sections is what enables the new 2-level settings structure (head group →
sub-tab → sections).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,  # V18.20.3.12 (F821): used at :353 (fast_temp_slider) but was never imported
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.icons import icon
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings.widgets import (
    labeled_checkbox,
    labeled_combo,
    labeled_line,
    labeled_spin,
    make_form,
)
from ui_qt.theme import theme_manager

# V18.20.3.12 follow-up (W-b11): module logger for the async model-fetch
# fail-softs — silent swallowed fetches are the W-c13 lesson.
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Helper: badge prefix for model pickers
# ════════════════════════════════════════════════════════════════════════════

_VISION_KW = ("vl", "vision", "deepseek-ocr", "llava", "bakllava", "ocr", "olmo")


def _badge(model: str) -> str:
    low = model.lower()
    return "🔍 " if any(k in low for k in _VISION_KW) else "📝 "


def _get_ollama_models(controller) -> list:
    """V17.0.0: Fetch available Ollama models."""
    try:
        from utils.dependencies import DependencyChecker
        return DependencyChecker().get_ollama_models() or []
    except Exception:
        return []


def _populate_models(combo: QComboBox, models: list[str], current: str = "",
                     allow_empty: bool = False, prefer_ocr: bool = False) -> None:
    """Fill a combo with all models (badged), selecting ``current`` or — if
    ``prefer_ocr`` — the first model whose name contains 'ocr'."""
    combo.clear()
    if allow_empty:
        combo.addItem("  (disabled)", "")
    for m in models:
        combo.addItem(_badge(m) + m, m)
    # selection priority: saved current → first 'ocr' model → first item
    target = ""
    if current:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
    if prefer_ocr:
        for m in models:
            if "ocr" in m.lower():
                idx = combo.findData(m)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    return
    if combo.count() > 0:
        combo.setCurrentIndex(0)


def _populate_models_async(combo: QComboBox, controller, current: str = "",
                           allow_empty: bool = False,
                           prefer_ocr: bool = False) -> None:
    """V18.20.4.5 (W-b11): fetch models OFF the UI thread; populate the
    combo on the main thread when done. Opening Settings no longer freezes
    the UI for up to 5s when Ollama is down."""
    worker = SimpleWorker(_get_ollama_models, controller)
    # Keep a ref on the combo so the worker isn't GC'd mid-run.
    combo._models_worker = worker
    def _apply(models):
        _populate_models(combo, models or [], current=current,
                         allow_empty=allow_empty, prefer_ocr=prefer_ocr)
    worker.finished.connect(_apply)
    worker.failed.connect(lambda _err: None)  # fail-soft: combo keeps its items
    worker.start()


def _refresh_models_async(section, fetch_fn, on_loaded,
                          refresh_btn=None) -> None:
    """V18.20.4.5 (W-b11): shared async model refresh for the settings
    sections (OcrModel / AiLocalModel / Defaults).

    ``fetch_fn`` (zero-arg, widget-free — pure HTTP) runs on a background
    SimpleWorker; ``on_loaded(models)`` populates the combos and runs on
    the MAIN thread (SimpleWorker's ``finished`` signal marshals there),
    so each section keeps its own populate semantics exactly. The worker
    is stored on ``section._models_worker`` (a Python ref — without it the
    QObject can be GC'd mid-run); ``refresh_btn`` is disabled while
    loading and re-enabled in BOTH outcome handlers (W-b18 class: a
    raising worker must never leave the button stuck disabled). Failure
    is fail-soft — the combos keep their current items.
    """
    worker = getattr(section, "_models_worker", None)
    try:
        in_flight = worker is not None and worker.is_running()
    except RuntimeError:
        in_flight = False  # worker already deleteLater'd itself — not running
    if in_flight:
        return  # a fetch is already in flight — don't stack workers
    if refresh_btn is not None:
        refresh_btn.setEnabled(False)
    w = SimpleWorker(fetch_fn)
    section._models_worker = w

    def _done(models):
        if refresh_btn is not None:
            refresh_btn.setEnabled(True)
        on_loaded(models or [])

    def _fail(err):
        logger.debug("Model refresh failed (W-b11 fail-soft): %s", err)
        if refresh_btn is not None:
            refresh_btn.setEnabled(True)

    w.finished.connect(_done)
    w.failed.connect(_fail)
    w.start()


# ════════════════════════════════════════════════════════════════════════════
# OCR sections
# ════════════════════════════════════════════════════════════════════════════

class OcrEngineSection(QGroupBox):
    """OCR engine toggles + timeout."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("OCR engine", parent)
        self.controller = controller
        f = make_form()
        self.llm_cb = labeled_checkbox(
            "Enable LLM OCR for scanned pages",
            checked=controller.get_setting("ocr.use_llm", True),
            tooltip="Use a vision LLM for scanned pages. Tesseract is the fallback.",
        )
        self.auto_cb = labeled_checkbox(
            "Auto-detect scanned pages",
            checked=controller.get_setting("ocr.auto_detect_scanned", True),
            tooltip="Only OCR pages with little extractable text.",
        )
        self.force_cb = labeled_checkbox(
            "Force OCR on every page",
            checked=controller.get_setting("ocr.force_ocr_all_pages", False),
            tooltip="Run OCR on all pages, even digital ones. Slower.",
        )
        self.paddle_cb = labeled_checkbox(
            "Enable PaddleOCR fallback",
            checked=controller.get_setting("ocr.use_paddleocr", False),
            tooltip="Try PaddleOCR before Tesseract if the vision model fails.",
        )
        f.addRow(self.llm_cb)
        f.addRow(self.auto_cb)
        f.addRow(self.force_cb)
        f.addRow(self.paddle_cb)
        self.timeout_combo = labeled_combo(
            ["30", "60", "90", "120", "180"], str(controller.get_setting("ocr.timeout", 60)),
            tooltip="Per-page OCR timeout in seconds.",
        )
        f.addRow("OCR timeout (s)", self.timeout_combo)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("ocr.use_llm", self.llm_cb.isChecked())
        c.update_setting("ocr.auto_detect_scanned", self.auto_cb.isChecked())
        c.update_setting("ocr.force_ocr_all_pages", self.force_cb.isChecked())
        c.update_setting("ocr.use_paddleocr", self.paddle_cb.isChecked())
        c.update_setting("ocr.timeout", int(self.timeout_combo.currentText()))

    def reload(self) -> None:
        c = self.controller
        self.llm_cb.setChecked(c.get_setting("ocr.use_llm", True))
        self.auto_cb.setChecked(c.get_setting("ocr.auto_detect_scanned", True))
        self.force_cb.setChecked(c.get_setting("ocr.force_ocr_all_pages", False))
        self.paddle_cb.setChecked(c.get_setting("ocr.use_paddleocr", False))
        to = str(c.get_setting("ocr.timeout", 60))
        idx = self.timeout_combo.findText(to)
        if idx >= 0:
            self.timeout_combo.setCurrentIndex(idx)


class OcrModelSection(QGroupBox):
    """Primary + fallback OCR model pickers — shows ALL Ollama models, badges
    them, and preselects the first model whose name contains 'ocr'."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("OCR models", parent)
        self.controller = controller
        f = make_form()
        self.primary_combo = QComboBox()
        self.fallback_combo = QComboBox()
        f.addRow("Primary model", self.primary_combo)
        f.addRow("Fallback model", self.fallback_combo)
        # V10.36.0: VLM fallback model for hard-to-OCR pages
        self.vlm_fallback_edit = QLineEdit(
            controller.get_setting("ocr.vlm_fallback_model", "")
        )
        self.vlm_fallback_edit.setPlaceholderText("e.g. llava:13b (leave empty to disable)")
        f.addRow("VLM fallback (local)", self.vlm_fallback_edit)
        _vlm_hint = QLabel(
            "When OlmOCR returns <50 chars on a page, this local VLM model "
            "is tried before Tesseract. Best for complex layouts / handwriting."
        )
        _vlm_hint.setObjectName("Caption")
        _vlm_hint.setWordWrap(True)
        f.addRow("", _vlm_hint)
        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)
        hint = QLabel("All installed Ollama models are listed. Models with “ocr”, "
                      "“vl”, or “vision” in the name are badged 🔍 and an OCR model "
                      "is pre-selected automatically.")
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)
        self.setLayout(f)
        # V18.20.4.5 (W-b11): worker ref for the async model fetch (a
        # Python ref keeps the SimpleWorker QObject alive mid-run).
        self._models_worker = None
        self._refresh_models()

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — the 5s-timeout
        DependencyChecker HTTP call used to run ON the UI thread here, so
        opening Settings (or clicking Refresh) froze the app for up to 5s
        when Ollama was down. Populate happens on the main thread in
        _on_models_loaded; the fetch fn is widget-free (pure HTTP)."""
        controller = self.controller  # snapshot on the main thread
        _refresh_models_async(
            self, lambda: _get_ollama_models(controller),
            self._on_models_loaded, self.refresh_btn)

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate both combos (MAIN thread)."""
        _populate_models(self.primary_combo, models,
                         current=self.controller.get_setting("ocr.primary_model", ""),
                         prefer_ocr=True)
        _populate_models(self.fallback_combo, models,
                         current=self.controller.get_setting("ocr.fallback_model", ""),
                         prefer_ocr=True)

    def save(self) -> None:
        self.controller.update_setting("ocr.primary_model", self.primary_combo.currentData() or "")
        self.controller.update_setting("ocr.fallback_model", self.fallback_combo.currentData() or "")
        # V10.36.0: VLM fallback model (local VLM for hard-to-OCR pages)
        self.controller.update_setting("ocr.vlm_fallback_model", self.vlm_fallback_edit.text().strip())

    def reload(self) -> None:
        self._refresh_models()
        self.vlm_fallback_edit.setText(self.controller.get_setting("ocr.vlm_fallback_model", ""))


class OcrFiguresSection(QGroupBox):
    """Figure-text extraction + TOC vision OCR."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Figures & TOC", parent)
        self.controller = controller
        f = make_form()
        self.figures_cb = labeled_checkbox(
            "Extract text from figures (Vision OCR)",
            checked=controller.get_setting("advanced.extract_figure_text", False),
            tooltip="Detect images and OCR visible text/labels/numbers from them.",
        )
        self.toc_vision_cb = labeled_checkbox(
            "Use vision model for TOC extraction (slower, more accurate)",
            checked=controller.get_setting("advanced.toc_vision_ocr", False),
            tooltip="Render TOC page(s) as images and pass to the vision model.",
        )
        f.addRow(self.figures_cb)
        f.addRow(self.toc_vision_cb)
        self.setLayout(f)

    def save(self) -> None:
        self.controller.update_setting("advanced.extract_figure_text", self.figures_cb.isChecked())
        self.controller.update_setting("advanced.toc_vision_ocr", self.toc_vision_cb.isChecked())

    def reload(self) -> None:
        self.figures_cb.setChecked(self.controller.get_setting("advanced.extract_figure_text", False))
        self.toc_vision_cb.setChecked(self.controller.get_setting("advanced.toc_vision_ocr", False))


# ════════════════════════════════════════════════════════════════════════════
# AI sections
# ════════════════════════════════════════════════════════════════════════════

PROVIDER_LABELS = {
    "Local (Ollama)": "ollama",
    "OpenAI-compatible": "openai_compatible",
    "Claude (Anthropic)": "claude",
}
PROVIDER_KEYS = {v: k for k, v in PROVIDER_LABELS.items()}
PROVIDER_URLS = {
    "ollama": "",
    "openai_compatible": "https://openrouter.ai/api/v1",
    "claude": "https://api.anthropic.com/v1",
}
PROVIDER_MODEL_HINTS = {
    "ollama": "(set in summarisation model above)",
    "openai_compatible": "google/gemini-2.5-flash-preview:free",
    "claude": "claude-3-5-sonnet-20241022",
}


class AiLocalModelSection(QGroupBox):
    """Local model backend (Ollama / LM Studio / custom) + summarisation models + workers.

    The backend picker changes where the model list is fetched from:
      - Ollama    → http://localhost:11434/api/tags
      - LM Studio → http://localhost:1234/v1/models
      - Custom    → user-supplied URL (expects Ollama-style /api/tags)
    """

    BACKENDS = ["Ollama", "LM Studio", "Custom"]

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Local model", parent)
        self.controller = controller
        f = make_form()

        # V13.35.0: Description label for the two-box layout
        local_desc = QLabel(
            "🏠 Local models run on your GPU via Ollama. Free, private, no API key needed. "
            "Best for RTX 3060 12GB with Gemma 4 12B."
        )
        local_desc.setWordWrap(True)
        local_desc.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0 6px 0;")
        f.addRow("", local_desc)

        # ── backend picker ──────────────────────────────────────────────
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(self.BACKENDS)
        saved_backend = controller.get_setting("ai.backend", "Ollama")
        idx = self.backend_combo.findText(saved_backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        self.backend_combo.currentTextChanged.connect(self._on_backend_change)
        f.addRow("Backend", self.backend_combo)

        # custom URL (only visible when Custom is selected)
        self.custom_url = labeled_line(
            controller.get_setting("ai.custom_backend_url", ""),
            placeholder="http://localhost:11434",
            tooltip="Ollama-style base URL for a custom local backend.",
        )
        f.addRow("Backend URL", self.custom_url)
        self._refresh_backend_url_visibility()

        # ── V16.0.9: 4-mode model architecture picker ──────────────────
        # single_local — one LOCAL model does everything (default)
        # dual_local   — local heavy + local fast model (both Ollama)
        # single_api   — one CLOUD API model does everything
        # dual_api     — fast cheap cloud API + expensive accurate cloud API
        # Legacy "single" is accepted (mapped → "single_local").
        self.arch_combo = QComboBox()
        self.arch_combo.addItem("🏠 Single — Local (default)", "single_local")
        self.arch_combo.addItem("🏠 Dual — Local (heavy + fast)", "dual_local")
        self.arch_combo.addItem("☁️ Single — API", "single_api")
        self.arch_combo.addItem("☁️ Dual — API (fast + accurate)", "dual_api")
        _saved_arch = controller.get_setting(
            "summarisation.model_architecture", "single_local"
        ) or "single_local"
        if _saved_arch == "single":
            _saved_arch = "single_local"
        _arch_idx = self.arch_combo.findData(_saved_arch)
        if _arch_idx >= 0:
            self.arch_combo.setCurrentIndex(_arch_idx)
        self.arch_combo.currentIndexChanged.connect(self._on_arch_change)
        f.addRow("Model architecture", self.arch_combo)

        # ── model pickers ───────────────────────────────────────────────
        self.summary_combo = QComboBox()
        # V18.20.4.3 (P2 / W-b7): the orphaned ``self.fast_combo`` widget is
        # REMOVED. It was created here but never added to any form row —
        # invisible, yet ``_refresh_models`` populated IT (not the visible
        # combo) and ``save()`` wrote ITS (always stale/empty) selection to
        # ``summarisation.fast_model`` before the real widget's write,
        # silently discarding one mode's selection every save. The visible
        # ``fast_model_combo`` (V16.0.9, "Fast model (dual-local)" row) is
        # the single source of truth from here on.
        self.fast_model_combo = QComboBox()
        self.heavy_combo = QComboBox()
        self.simplification_combo = QComboBox()  # V3.5.0: separate model for simplified keypoints
        f.addRow("Summarisation model", self.summary_combo)

        # V16.0.9: Fast model row with its own refresh button (visible only
        # in dual_local mode — the dedicated fast LOCAL model).
        # V18.20.4.5 (W-b11): populate OFF the UI thread — this used to be a
        # BLOCKING 5s-timeout Ollama fetch in the constructor, so opening
        # Settings froze the whole UI for up to 5s when Ollama was down.
        _populate_models_async(self.fast_model_combo, controller,
            current=controller.get_setting("summarisation.fast_model", ""))
        fast_row_widget = QWidget()
        fast_model_row = QHBoxLayout(fast_row_widget)
        fast_model_row.setContentsMargins(0, 0, 0, 0)
        fast_model_row.setSpacing(8)
        fast_model_row.addWidget(self.fast_model_combo, 1)
        self.fast_refresh_btn = QPushButton("  ↻")
        self.fast_refresh_btn.setToolTip("Refresh the model list from Ollama.")
        # V18.20.4.5 (W-b11): the ↻ click is async too — same 5s-timeout
        # fetch, must not block the UI thread (the current selection is
        # snapshotted on the main thread at click time).
        self.fast_refresh_btn.clicked.connect(lambda: _populate_models_async(
            self.fast_model_combo, controller,
            current=self.fast_model_combo.currentData()))
        fast_model_row.addWidget(self.fast_refresh_btn)
        self.fast_row_widget = fast_row_widget
        f.addRow("Fast model (dual-local)", self.fast_row_widget)

        # V17.0.0: Fast model temperature
        self.fast_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.fast_temp_slider.setRange(0, 200)
        self.fast_temp_slider.setValue(int(controller.get_setting("summarisation.fast_model_temperature", 0.1) * 100))
        self.fast_temp_slider.setToolTip(
            "Sampling temperature for the fast model.\n\n"
            "LFM2.5-2.6B recommends 0.1.\n"
            "Qwen models recommend 0.6-0.8.\n"
            "Gemma models recommend 1.0."
        )
        self.fast_temp_entry = QLineEdit(f"{self.fast_temp_slider.value() / 100:.2f}")
        self.fast_temp_entry.setMaximumWidth(56)
        self.fast_temp_entry.setAlignment(Qt.AlignCenter)
        self.fast_temp_slider.valueChanged.connect(lambda v: self.fast_temp_entry.setText(f"{v / 100:.2f}"))
        fast_temp_row = QHBoxLayout()
        fast_temp_row.setSpacing(8)
        fast_temp_row.addWidget(self.fast_temp_slider, 1)
        fast_temp_row.addWidget(self.fast_temp_entry)
        f.addRow("Fast model temperature", fast_temp_row)

        # V17.0.0: Fast model context size
        self.fast_ctx_edit = QLineEdit(str(controller.get_setting("summarisation.fast_model_context", 131072)))
        self.fast_ctx_edit.setToolTip(
            "Context window for the fast model. LFM2.5 supports up to 131072 (128K)."
        )
        f.addRow("Fast model context size", self.fast_ctx_edit)

        # V16.0.9: Fast-API fields (visible only in dual_api mode — the
        # cheap cloud workhorse).
        self.fast_api_url_edit = QLineEdit(
            controller.get_setting("summarisation.fast_api_url", "")
        )
        self.fast_api_url_edit.setPlaceholderText("https://openrouter.ai/api/v1")
        self.fast_api_url_edit.setToolTip(
            "OpenAI-compatible API URL for the fast model in Dual-API mode."
        )
        f.addRow("Fast API URL (dual-api)", self.fast_api_url_edit)

        self.fast_api_key_edit = QLineEdit(
            controller.get_setting("summarisation.fast_api_key", "")
        )
        self.fast_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.fast_api_key_edit.setPlaceholderText("sk-...")
        self.fast_api_key_edit.setToolTip(
            "API key for the fast model endpoint in Dual-API mode."
        )
        f.addRow("Fast API key (dual-api)", self.fast_api_key_edit)

        self.fast_api_model_edit = QLineEdit(
            controller.get_setting("summarisation.fast_api_model", "")
        )
        self.fast_api_model_edit.setPlaceholderText(
            "google/gemini-2.5-flash-preview:free"
        )
        self.fast_api_model_edit.setToolTip(
            "Cloud model name (e.g. gpt-4o-mini, gemini-flash) for Dual-API mode."
        )
        f.addRow("Fast API model (dual-api)", self.fast_api_model_edit)

        f.addRow("Heavy model (fallback)", self.heavy_combo)
        f.addRow("Simplification model", self.simplification_combo)

        # V16.0.9: Architecture description label — explains which tasks use
        # which model. Updates whenever the architecture combo changes.
        self.arch_desc_label = QLabel("")
        self.arch_desc_label.setObjectName("Caption")
        self.arch_desc_label.setWordWrap(True)
        self.arch_desc_label.setStyleSheet(
            "color: #666; font-size: 11px; padding: 4px 0 2px 0;"
        )
        f.addRow("", self.arch_desc_label)

        # V3.5.0: Tooltip explaining sequential model loading
        simplification_tip = (
            "Model used for simplifying keypoints into plain language. "
            "If set, the app will unload the summarisation model and load this "
            "model for the simplification phase — enables using a different "
            "model (e.g., Qwythos) that handles translation better. "
            "Leave empty to use the same model as summarisation."
        )
        self.simplification_combo.setToolTip(simplification_tip)

        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)

        # ── workers ─────────────────────────────────────────────────────
        # V18.20.3.12 (F823 fix): the method-local ``from PySide6.QtWidgets
        # import QSlider`` that used to sit here made QSlider a LOCAL name for
        # the WHOLE of __init__ — so the fast_temp_slider use at :354 (which
        # precedes this line) raised UnboundLocalError since V17.0.0. Removed
        # in favor of the module-level import added with this sweep.
        w_row = QHBoxLayout()
        w_row.setContentsMargins(0, 0, 0, 0)
        w_row.setSpacing(8)
        self.workers_slider = QSlider(Qt.Orientation.Horizontal)
        self.workers_slider.setRange(1, 4)
        self.workers_slider.setValue(int(controller.get_setting("summarisation.max_workers", 2)))
        self.workers_label = QLabel(str(self.workers_slider.value()))
        self.workers_label.setMinimumWidth(28)
        self.workers_label.setAlignment(Qt.AlignCenter)
        self.workers_slider.valueChanged.connect(lambda v: self.workers_label.setText(str(v)))
        w_row.addWidget(self.workers_slider)
        w_row.addWidget(self.workers_label)
        f.addRow("Parallel workers", w_row)

        self.setLayout(f)
        # V18.20.4.5 (W-b11): worker ref for the async model fetch (a
        # Python ref keeps the SimpleWorker QObject alive mid-run).
        self._models_worker = None
        self._refresh_models()
        # V16.0.9: Apply the initial visibility + description after construction.
        self._on_arch_change()

    # V16.0.9: React to architecture combo changes — show/hide the
    # fast-model + fast-API fields and update the description label.
    def _on_arch_change(self) -> None:
        arch = self.arch_combo.currentData() or "single_local"
        # Fast model dropdown (Ollama) is visible in dual_local only — it's
        # the dedicated fast LOCAL model. In single_local there's no separate
        # fast model; in API modes the fast model is a cloud endpoint.
        show_fast_combo = arch == "dual_local"
        # Fast-API fields are visible only in dual_api mode (the cheap cloud
        # workhorse). single_api has no fast model.
        show_fast_api = arch == "dual_api"
        # Show/hide the fast row widget (combo + refresh button).
        self.fast_row_widget.setVisible(show_fast_combo)
        # Show/hide the API URL / key / model fields.
        self.fast_api_url_edit.setVisible(show_fast_api)
        self.fast_api_key_edit.setVisible(show_fast_api)
        self.fast_api_model_edit.setVisible(show_fast_api)
        # Update the description label.
        if arch == "single_local":
            self.arch_desc_label.setText(
                "🏠 Single — Local: One local model (Ollama/LM Studio) does "
                "everything — B4 sections, synthesis, judge, concept extraction, "
                "gap-fill, scholar reflection, self-review. Simplest setup, no "
                "VRAM juggling."
            )
        elif arch == "dual_local":
            self.arch_desc_label.setText(
                "🏠 Dual — Local: Heavy model (above): B4 sections, thematic "
                "synthesis, content judge. Fast model: concept extraction, "
                "gap-fill, bullet consolidation, scholar reflection, "
                "self-review. Both via Ollama — VRAM is recovered between "
                "switches (10s before fast, 30s before heavy)."
            )
        elif arch == "single_api":
            self.arch_desc_label.setText(
                "☁️ Single — API: One cloud model (OpenRouter/OpenAI/9Router) "
                "does everything. No GPU needed. Configure the cloud endpoint "
                "in the Cloud/API section above. Pay per token."
            )
        elif arch == "dual_api":
            self.arch_desc_label.setText(
                "☁️ Dual — API: Cheap fast cloud workhorse (Fast API fields "
                "below): concept extraction, gap-fill, merge, scholar reflection. "
                "Expensive accurate cloud model (Cloud/API section above): B4 "
                "sections, synthesis, judge. Best cost/quality balance for "
                "cloud users."
            )
        else:
            self.arch_desc_label.setText("")

    # ── backend ──────────────────────────────────────────────────────────
    def _on_backend_change(self, _text: str) -> None:
        self._refresh_backend_url_visibility()
        self._refresh_models()

    def _refresh_backend_url_visibility(self) -> None:
        self.custom_url.setVisible(self.backend_combo.currentText() == "Custom")

    def _backend_url(self) -> str:
        backend = self.backend_combo.currentText()
        if backend == "Ollama":
            return "http://localhost:11434"
        if backend == "LM Studio":
            return "http://localhost:1234"
        return self.custom_url.text().strip() or "http://localhost:11434"

    def _fetch_models(self) -> list:
        """Fetch models from the selected backend. Falls back to Ollama.

        V18.20.4.5 (W-b11): kept for compatibility — reads the backend URL
        from the combos, so only call it on the MAIN thread. The async
        refresh snapshots the URL first and runs the widget-free
        ``_fetch_models_from(url)`` on the worker instead.
        """
        return self._fetch_models_from(self._backend_url())

    def _fetch_models_from(self, url: str) -> list:
        """Widget-free fetch from ``url`` (safe to run on a worker thread)."""
        try:
            import requests
            sess = requests.Session()
            sess.trust_env = False
            sess.proxies = {"http": None, "https": None}
            # LM Studio uses OpenAI-style /v1/models; Ollama uses /api/tags.
            if "localhost:1234" in url or "lmstudio" in url.lower():
                resp = sess.get(f"{url.rstrip('/')}/v1/models", timeout=5)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    return [m.get("id", "") for m in data if m.get("id")]
            # Ollama-style
            resp = sess.get(f"{url.rstrip('/')}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass  # best-effort (UI — never crash)
        return []

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — this ran a
        5s-timeout HTTP call ON the UI thread (constructor, backend
        change, reload, Refresh click) — opening Settings froze the app
        for up to 5s when the backend was down. The backend URL is
        snapshotted on the MAIN thread (combo read) and the widget-free
        ``_fetch_models_from(url)`` runs on the worker; populate happens
        on the main thread in _on_models_loaded."""
        url = self._backend_url()  # snapshot on the main thread
        fetch = self._fetch_models_from  # bound method — worker-safe body
        _refresh_models_async(self, lambda: fetch(url),
                              self._on_models_loaded, self.refresh_btn)

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate the four combos (MAIN thread)."""
        _populate_models(self.summary_combo, models,
                         current=self.controller.get_setting("summarisation.model", ""))
        # V18.20.4.3 (P2 / W-b7): refresh the VISIBLE fast-model combo —
        # this used to populate the orphaned ``fast_combo``, so a global
        # model refresh never actually updated the fast-model picker.
        _populate_models(self.fast_model_combo, models,
                         current=self.controller.get_setting("summarisation.fast_model", ""))
        _populate_models(self.heavy_combo, models,
                         current=self.controller.get_setting("summarisation.heavy_model", ""),
                         allow_empty=True)
        # V3.5.0: Simplification model (allow empty = use same as summarisation)
        _populate_models(self.simplification_combo, models,
                         current=self.controller.get_setting("summarisation.simplification_model", ""),
                         allow_empty=True)

    # ── save / reload ────────────────────────────────────────────────────
    def save(self) -> None:
        c = self.controller
        c.update_setting("ai.backend", self.backend_combo.currentText())
        c.update_setting("ai.custom_backend_url", self.custom_url.text().strip())
        c.update_setting("summarisation.model", self.summary_combo.currentData() or "")
        c.update_setting("summarisation.fast_model", self.fast_model_combo.currentData() or "")
        c.update_setting("summarisation.heavy_model", self.heavy_combo.currentData() or "")
        # V16.0.9: 4-mode model architecture settings.
        c.update_setting(
            "summarisation.model_architecture",
            self.arch_combo.currentData() or "single_local",
        )
        c.update_setting("summarisation.fast_api_url", self.fast_api_url_edit.text().strip())
        # TODO V18.1: route through core.system.secrets.store_secret() for keyring support
        c.update_setting("summarisation.fast_api_key", self.fast_api_key_edit.text().strip())
        c.update_setting("summarisation.fast_api_model", self.fast_api_model_edit.text().strip())
        c.update_setting("summarisation.fast_model_temperature", self.fast_temp_slider.value() / 100)
        try:
            c.update_setting("summarisation.fast_model_context", int(self.fast_ctx_edit.text().strip()))
        except (ValueError, TypeError):
            pass
        c.update_setting("summarisation.simplification_model", self.simplification_combo.currentData() or "")
        c.update_setting("summarisation.max_workers", self.workers_slider.value())
        # when using a local backend, set provider to ollama so the pipeline
        # knows to use local models (not a cloud API).
        c.update_setting("summarisation.provider", "ollama")

    def reload(self) -> None:
        c = self.controller
        idx = self.backend_combo.findText(c.get_setting("ai.backend", "Ollama"))
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        self.custom_url.setText(c.get_setting("ai.custom_backend_url", ""))
        self._refresh_backend_url_visibility()
        self.workers_slider.setValue(int(c.get_setting("summarisation.max_workers", 2)))
        self._refresh_models()
        # V16.0.9: Architecture combo (4 modes; legacy "single" → "single_local")
        _arch = c.get_setting("summarisation.model_architecture", "single_local") or "single_local"
        if _arch == "single":
            _arch = "single_local"
        _arch_idx = self.arch_combo.findData(_arch)
        if _arch_idx >= 0:
            self.arch_combo.setCurrentIndex(_arch_idx)
        # V18.20.4.5 (W-b11): async — reload() runs on the UI thread and
        # must not block it on the 5s-timeout Ollama fetch either.
        _populate_models_async(self.fast_model_combo, c,
            current=c.get_setting("summarisation.fast_model", ""))
        # V16.0.9: Fast-API fields reload
        self.fast_api_url_edit.setText(c.get_setting("summarisation.fast_api_url", ""))
        self.fast_api_key_edit.setText(c.get_setting("summarisation.fast_api_key", ""))
        self.fast_api_model_edit.setText(c.get_setting("summarisation.fast_api_model", ""))
        self.fast_temp_slider.setValue(int(c.get_setting("summarisation.fast_model_temperature", 0.1) * 100))
        self.fast_temp_entry.setText(f"{self.fast_temp_slider.value() / 100:.2f}")
        self.fast_ctx_edit.setText(str(c.get_setting("summarisation.fast_model_context", 131072)))
        self._on_arch_change()


# ── saved custom API providers (stored in settings) ────────────────────────

def _load_custom_providers(controller: Controller) -> list:
    """Return the list of saved custom API providers from settings."""
    return controller.get_setting("ai.custom_providers", []) or []


def _save_custom_providers(controller: Controller, providers: list) -> None:
    controller.update_setting("ai.custom_providers", providers)


class AiApiSection(QGroupBox):
    """Cloud / API provider selection with multiple saved custom providers.

    A dropdown picks the active provider type:
      - OpenAI-Compatible  (base URL + key + model)
      - Claude-Compatible  (base URL + key + model)
      - Custom (named)     (user-saved providers — name + base URL + key + model)

    When an API provider is active, the local model pickers are greyed out
    (the engine-awareness banner on the home screen also reflects this).
    """

    PROVIDER_TYPES = ["OpenAI-Compatible", "Claude-Compatible", "Custom (named)"]

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("API provider", parent)
        self.controller = controller
        f = make_form()

        # V13.35.0: Description label for the two-box layout
        api_desc = QLabel(
            "☁️ Cloud models use a remote API endpoint (OpenRouter, OpenAI, 9Router, Claude). "
            "Paid, no GPU needed. Use a preset to quick-fill popular providers."
        )
        api_desc.setWordWrap(True)
        api_desc.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0 6px 0;")
        f.addRow("", api_desc)

        # ── provider type dropdown ──────────────────────────────────────
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.PROVIDER_TYPES)
        saved_type = controller.get_setting("ai.api_type", "OpenAI-Compatible")
        idx = self.type_combo.findText(saved_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentTextChanged.connect(self._on_type_change)
        f.addRow("Provider type", self.type_combo)

        # ── saved custom providers list (only for "Custom (named)") ─────
        from PySide6.QtWidgets import QListWidget
        self.providers_list = QListWidget()
        self.providers_list.setMaximumHeight(90)
        self.providers_list.currentRowChanged.connect(self._on_provider_selected)
        f.addRow("Saved providers", self.providers_list)

        # add / delete buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.add_btn = QPushButton("  Add")
        self.add_btn.setObjectName("Compact")
        self.add_btn.clicked.connect(self._add_provider)
        self.del_btn = QPushButton("  Delete")
        self.del_btn.setObjectName("Compact")
        self.del_btn.clicked.connect(self._del_provider)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        f.addRow("", btn_row)

        # ── fields ──────────────────────────────────────────────────────
        self.name_edit = labeled_line("", placeholder="Provider name (e.g. 9Router)")
        self.base_url_edit = labeled_line(
            controller.get_setting("summarisation.api_base_url", "https://openrouter.ai/api/v1"),
            placeholder="https://api.example.com/v1",
        )
        self.api_key_edit = labeled_line(
            controller.get_setting("summarisation.api_key", ""),
            placeholder="sk-…  /  your API key", password=True,
        )
        self.model_edit = labeled_line(
            controller.get_setting("summarisation.cloud_model", "google/gemini-2.5-flash-preview:free"),
            placeholder="e.g. google/gemini-2.5-flash-preview:free",
        )
        f.addRow("Name", self.name_edit)
        f.addRow("Base URL", self.base_url_edit)
        f.addRow("API key", self.api_key_edit)
        f.addRow("Model", self.model_edit)

        self.setLayout(f)
        self._populate_providers_list()
        self._on_type_change()

    def _populate_providers_list(self) -> None:
        self.providers_list.clear()
        for p in _load_custom_providers(self.controller):
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(p.get("name", "(unnamed)"))
            item.setData(0x0100, p)  # store the provider dict
            self.providers_list.addItem(item)

    def _on_type_change(self) -> None:
        is_custom = self.type_combo.currentText() == "Custom (named)"
        self.providers_list.setVisible(is_custom)
        self.add_btn.setVisible(is_custom)
        self.del_btn.setVisible(is_custom)
        self.name_edit.setVisible(is_custom)
        # for non-custom, set sensible defaults
        if not is_custom:
            t = self.type_combo.currentText()
            if "Claude" in t:
                self.base_url_edit.setPlaceholderText("https://api.anthropic.com/v1")
                self.model_edit.setPlaceholderText("claude-3-5-sonnet-20241022")
            else:
                self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
                self.model_edit.setPlaceholderText("gpt-4o-mini")

    def _on_provider_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self.providers_list.item(row)
        if not item:
            return
        p = item.data(0x0100) or {}
        self.name_edit.setText(p.get("name", ""))
        self.base_url_edit.setText(p.get("base_url", ""))
        self.api_key_edit.setText(p.get("api_key", ""))
        self.model_edit.setText(p.get("model", ""))

    def _add_provider(self) -> None:
        providers = _load_custom_providers(self.controller)
        providers.append({
            "name": self.name_edit.text().strip() or f"Provider {len(providers) + 1}",
            "base_url": self.base_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_edit.text().strip(),
        })
        _save_custom_providers(self.controller, providers)
        self._populate_providers_list()
        self.providers_list.setCurrentRow(len(providers) - 1)

    def _del_provider(self) -> None:
        row = self.providers_list.currentRow()
        if row < 0:
            return
        providers = _load_custom_providers(self.controller)
        if 0 <= row < len(providers):
            providers.pop(row)
            _save_custom_providers(self.controller, providers)
            self._populate_providers_list()

    def save(self) -> None:
        c = self.controller
        t = self.type_combo.currentText()
        api_key = self.api_key_edit.text().strip()
        c.update_setting("ai.api_type", t)
        c.update_setting("summarisation.api_base_url", self.base_url_edit.text().strip())
        # TODO V18.1: route through core.system.secrets.store_secret() for keyring support
        c.update_setting("summarisation.api_key", api_key)
        c.update_setting("summarisation.cloud_model", self.model_edit.text().strip())
        # Only set the provider to API if the user actually configured an API key.
        # If the key is empty, the user is using Local Model (Ollama) and the
        # AiLocalModelSection.save() already set provider="ollama".  Without this
        # guard, the API section's save() overwrites the local-model provider
        # every time, causing the summarizer to call OpenRouter with no auth.
        if api_key:
            if "Claude" in t:
                c.update_setting("summarisation.provider", "claude")
                c.update_setting("summarisation.claude_base_url", self.base_url_edit.text().strip())
                # TODO V18.1: route through core.system.secrets.store_secret() for keyring support
                c.update_setting("summarisation.claude_api_key", api_key)
                c.update_setting("summarisation.claude_model", self.model_edit.text().strip())
            else:
                c.update_setting("summarisation.provider", "openai_compatible")
        # else: don't touch provider — AiLocalModelSection already set it to "ollama"
        # if currently editing a custom provider, persist its fields
        if t == "Custom (named)":
            row = self.providers_list.currentRow()
            providers = _load_custom_providers(c)
            if 0 <= row < len(providers):
                providers[row].update({
                    "name": self.name_edit.text().strip() or f"Provider {row + 1}",
                    "base_url": self.base_url_edit.text().strip(),
                    "api_key": self.api_key_edit.text().strip(),
                    "model": self.model_edit.text().strip(),
                })
                _save_custom_providers(c, providers)

    def reload(self) -> None:
        c = self.controller
        idx = self.type_combo.findText(c.get_setting("ai.api_type", "OpenAI-Compatible"))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.base_url_edit.setText(c.get_setting("summarisation.api_base_url", ""))
        self.api_key_edit.setText(c.get_setting("summarisation.api_key", ""))
        self.model_edit.setText(c.get_setting("summarisation.cloud_model", ""))
        self._populate_providers_list()
        self._on_type_change()


# Legacy aliases (kept so the dialog's _HEAD_GROUPS import doesn't break
# during the transition — the new dialog uses AiLocalModelSection/AiApiSection).
AiModelsSection = AiLocalModelSection
AiProviderSection = AiApiSection


# ════════════════════════════════════════════════════════════════════════════
# A1: Prompt Bank — user-editable prompt templates
# ════════════════════════════════════════════════════════════════════════════

class AiPromptSection(QGroupBox):
    """Prompt Bank — select and edit summarisation prompt templates."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Prompt bank", parent)
        self.controller = controller
        f = make_form()

        # ── Prompt selector ─────────────────────────────────────────────
        from core.summarisation.prompt_manager import PromptManager
        self._pm = PromptManager()
        self._prompts = self._pm.list_prompts()
        saved_prompt = controller.get_setting("summarisation.prompt", "default")
        if saved_prompt not in self._prompts:
            saved_prompt = "default"

        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(self._prompts)
        idx = self.prompt_combo.findText(saved_prompt)
        if idx >= 0:
            self.prompt_combo.setCurrentIndex(idx)
        self.prompt_combo.currentTextChanged.connect(self._on_prompt_selected)
        f.addRow("Active prompt", self.prompt_combo)

        # ── Prompt editor ───────────────────────────────────────────────
        from PySide6.QtWidgets import QHBoxLayout
        editor_label = QLabel("Edit prompt template (variables: {{heading}}, {{text}}, {{language}})")
        editor_label.setObjectName("Caption")
        f.addRow("", editor_label)

        self.editor = QTextEdit()
        self.editor.setMinimumHeight(280)
        self.editor.setFont(__import__("PySide6").QtGui.QFont("Consolas", 10))
        f.addRow(self.editor)

        # Load the current prompt into the editor
        current = self.prompt_combo.currentText()
        content = self._pm.load_prompt(current)
        if content:
            self.editor.setPlainText(content)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("  Save")
        self.save_btn.setObjectName("Compact")
        self.save_btn.clicked.connect(self._save_prompt)
        btn_row.addWidget(self.save_btn)

        self.new_btn = QPushButton("  New…")
        self.new_btn.setObjectName("Compact")
        self.new_btn.clicked.connect(self._new_prompt)
        btn_row.addWidget(self.new_btn)

        self.delete_btn = QPushButton("  Delete")
        self.delete_btn.setObjectName("Compact")
        self.delete_btn.clicked.connect(self._delete_prompt)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()
        f.addRow("", btn_row)

        # Hint
        hint = QLabel("Prompts are stored in ~/.markitdown_pro/prompts/. Changes apply on the next conversion.")
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def _on_prompt_selected(self, name: str) -> None:
        """Load the selected prompt into the editor."""
        content = self._pm.load_prompt(name)
        if content:
            self.editor.setPlainText(content)

    def _save_prompt(self) -> None:
        """Save the edited prompt to the user directory."""
        name = self.prompt_combo.currentText()
        content = self.editor.toPlainText()
        self._pm.save_prompt(name, content)
        # Update the active prompt in settings
        self.controller.update_setting("summarisation.prompt", name)

    def _new_prompt(self) -> None:
        """Create a new prompt template."""
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Prompt", "Prompt name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        # Start with the default template
        default = self._pm.load_prompt("default") or ""
        self._pm.save_prompt(name, default)
        # Add to combo and select
        if self.prompt_combo.findText(name) < 0:
            self.prompt_combo.addItem(name)
        self.prompt_combo.setCurrentText(name)
        self.editor.setPlainText(default)

    def _delete_prompt(self) -> None:
        """Delete the current prompt (only user-created ones)."""
        name = self.prompt_combo.currentText()
        if name in ("default", "academic", "technical", "creative"):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Cannot delete", f"'{name}' is a built-in preset and cannot be deleted.")
            return
        from PySide6.QtWidgets import QMessageBox
        ret = QMessageBox.question(self, "Delete prompt", f"Delete prompt '{name}'?")
        if ret == QMessageBox.Yes:
            self._pm.delete_prompt(name)
            self.prompt_combo.removeItem(self.prompt_combo.currentIndex())
            # Switch to default
            self.prompt_combo.setCurrentText("default")

    def save(self) -> None:
        """Called when the settings dialog is saved."""
        name = self.prompt_combo.currentText()
        content = self.editor.toPlainText()
        self._pm.save_prompt(name, content)
        self.controller.update_setting("summarisation.prompt", name)

    def reload(self) -> None:
        """Re-read settings."""
        saved = self.controller.get_setting("summarisation.prompt", "default")
        self._prompts = self._pm.list_prompts()
        self.prompt_combo.clear()
        self.prompt_combo.addItems(self._prompts)
        idx = self.prompt_combo.findText(saved)
        if idx >= 0:
            self.prompt_combo.setCurrentIndex(idx)
        content = self._pm.load_prompt(saved)
        if content:
            self.editor.setPlainText(content)

    def set_simple_mode(self, simple: bool) -> None:
        pass  # always visible


QUALITY_PRESETS = {
    "Fast": {"temperature": 0.3, "self_consistency": False},
    "Balanced": {"temperature": 0.2, "self_consistency": False},
    # V7.5.1: was temperature=0.0 — too low for most models (Qwen/Gemma
    # produce empty/degenerate output at t=0).  Raised to 0.1 (minimum safe).
    "Maximum": {"temperature": 0.1, "self_consistency": True},
}


class AiQualitySection(QGroupBox):
    """Quality mode + fine controls + output selection."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Quality & summaries", parent)
        self.controller = controller
        f = make_form()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Fast", "Balanced", "Maximum"])
        self.quality_combo.setCurrentText(controller.get_setting("summarisation.quality_mode", "Balanced"))
        self.quality_combo.currentTextChanged.connect(self._apply_preset)
        f.addRow("Preset", self.quality_combo)

        from PySide6.QtWidgets import QSlider
        temp_row = QHBoxLayout()
        temp_row.setContentsMargins(0, 0, 0, 0)
        temp_row.setSpacing(8)
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 70)
        self.temp_slider.setValue(int(controller.get_setting("summarisation.temperature", 0.2) * 100))
        self.temp_slider.setToolTip(
            "Sampling temperature.\n\n"
            "• 0.0 — deterministic, but many models (Qwen, Gemma, Llama) produce\n"
            "  degenerate or empty output at exactly 0. Use ≥ 0.1.\n"
            "• 0.2–0.4 — recommended for factual summaries.\n"
            "• 0.6–0.8 — more creative (podcast scripts)."
        )
        self.temp_entry = QLineEdit(f"{self.temp_slider.value() / 100:.2f}")
        self.temp_entry.setMaximumWidth(56)
        self.temp_entry.setAlignment(Qt.AlignCenter)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_entry.setText(f"{v / 100:.2f}"))
        # V7.5.1: live warning label when temperature < 0.1
        self.temp_warn_label = QLabel("")
        self.temp_warn_label.setObjectName("Caption")
        self.temp_slider.valueChanged.connect(self._check_temp_warning)
        self.temp_entry.editingFinished.connect(self._on_temp_entry)
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_entry)
        temp_row.addWidget(self.temp_warn_label)
        f.addRow("Temperature", temp_row)
        self._check_temp_warning(self.temp_slider.value())

        self.coverage_spin = labeled_spin(
            int(controller.get_setting("summarisation.coverage_threshold", 50)),
            minimum=30, maximum=90, suffix="%",
        )
        f.addRow("Coverage threshold", self.coverage_spin)
        # V15.1.0: Over-delivery — keep improving coverage past minimum threshold
        self.overdeliver_cb = labeled_checkbox(
            "📈 Over-deliver: keep gap-filling past minimum threshold toward target",
            checked=controller.get_setting("summarisation.overdeliver_enabled", True),
        )
        self.overdeliver_target_spin = labeled_spin(
            int(controller.get_setting("summarisation.overdeliver_target", 100)),
            minimum=85, maximum=100, suffix="%",
        )
        self.overdeliver_target_spin.setToolTip(
            "V15.1.1: Target coverage when over-delivery is enabled. Default 100% "
            "(the more the better). The pipeline keeps gap-filling until this target "
            "is reached (or no more concepts to fill). Must be >= coverage threshold."
        )
        f.addRow("Over-deliver target", self.overdeliver_target_spin)
        f.addRow("", self.overdeliver_cb)
        # V15.1.1: B3 voting toggle (disabled by default — damages depth)
        self.b3_voting_cb = labeled_checkbox(
            "🔄 B3 multi-sample voting (EXPERIMENTAL — disabled by default. "
            "Consensus voting dilutes conceptual depth. Enable to experiment.)",
            checked=controller.get_setting("summarisation.b3_voting_enabled", False),
        )
        f.addRow("", self.b3_voting_cb)
        self.self_consist_cb = labeled_checkbox(
            "Enable self-consistency (3× slower, more robust)",
            checked=controller.get_setting("summarisation.self_consistency", False),
        )
        self.academic_cb = labeled_checkbox(
            "🔬 Academic Rigor (temp 0, self-review, structured JSON)",
            checked=controller.get_setting("summarisation.academic_rigor", False),
        )
        # V10.1.0: Source Grounding (langextract) — Layer 8 anti-hallucination.
        self.grounding_cb = labeled_checkbox(
            "🛡️ Source Grounding (langextract — verbatim claim verification). "
            "Requires `pip install langextract`.",
            checked=controller.get_setting("grounding.enabled", False),
        )
        self.grounding_cb.setToolTip(
            "Layer 8 of the anti-hallucination defense.\n\n"
            "When enabled, Google's langextract library extracts every\n"
            "factual claim from the source text with a verbatim character\n"
            "span (char_interval).  Claims that can't be located verbatim\n"
            "are flagged as potential hallucinations — a deterministic,\n"
            "binary signal stronger than the existing semantic similarity\n"
            "checks (Layers 1-7).\n\n"
            "Falls back gracefully to Layers 1-7 if langextract is missing\n"
            "or the backend is unreachable (with a loud warning in the log)."
        )
        # Backend selector (Ollama default / Cloud optional)
        self.grounding_backend = QComboBox()
        self.grounding_backend.addItems(["ollama", "cloud"])
        self.grounding_backend.setCurrentText(
            controller.get_setting("grounding.backend", "ollama")
        )
        self.grounding_backend.setToolTip(
            "Ollama (default): local, free, no API key. Matches the\n"
            "overnight-run reliability goal. Gets verbatim grounding but\n"
            "NOT schema-constrained output.\n\n"
            "Cloud: OpenAI-compatible endpoint (9Router / OpenRouter / OpenAI).\n"
            "Gets schema-constrained output where supported. Adds latency\n"
            "and cost. Use for maximum-rigor scientific articles."
        )
        # V10.1.6: Manual GPU thermal profile override.
        # Some Zotac cards report "NVIDIA GeForce RTX 3060" (no brand name)
        # to nvidia-smi, so auto-detection fails.  This dropdown lets the
        # user force the Zotac emergency profile manually.
        self.gpu_profile_combo = QComboBox()
        self.gpu_profile_combo.addItems([
            "auto — detect from GPU name",
            "zotac_3060 — Zotac RTX 3060 Twin Edge (EMERGENCY)",
            "zotac_3060_ti — Zotac RTX 3060 Ti Twin Edge (EMERGENCY)",
            "zotac_3070 — Zotac RTX 3070 Twin Edge (EMERGENCY)",
            "generic — Standard NVIDIA (83°C/88°C)",
        ])
        _current_override = controller.get_setting("hardware.gpu_profile_override", "auto")
        _override_idx = {"auto": 0, "zotac_3060": 1, "zotac_3060_ti": 2,
                         "zotac_3070": 3, "generic": 4}.get(_current_override, 0)
        self.gpu_profile_combo.setCurrentIndex(_override_idx)
        self.gpu_profile_combo.setToolTip(
            "GPU thermal profile override.\n\n"
            "Use this if your Zotac card is detected as 'NVIDIA GeForce RTX 3060' "
            "(without the 'ZOTAC' brand name) — nvidia-smi sometimes doesn't "
            "report the board partner name on Zotac cards.\n\n"
            "Setting this to 'Zotac RTX 3060 Twin Edge (EMERGENCY)' forces:\n"
            "  • Warning at 72°C (not 83°C)\n"
            "  • Critical auto-pause at 80°C (not 88°C)\n"
            "  • max_workers locked to 1 (VRAM protection)\n"
            "  • Mandatory 20-min cool-down cycles\n"
            "  • Emergency mode warnings in the log\n\n"
            "Leave on 'auto' if your card is correctly detected."
        )
        self.simplified_cb = labeled_checkbox(
            "📝 Generate Simplified Keypoints (jargon-free digest)",
            checked=controller.get_setting("summarisation.simplified_keypoints_enabled", False),
        )
        self.filter_cb = labeled_checkbox(
            "Enable content filter (skip TOC, index, blank pages)",
            checked=controller.get_setting("content_filter.enabled", True),
        )
        f.addRow(self.self_consist_cb)
        f.addRow(self.academic_cb)
        f.addRow("🛡️ Grounding backend", self.grounding_backend)
        f.addRow("🌡️ GPU thermal profile", self.gpu_profile_combo)
        f.addRow(self.grounding_cb)
        f.addRow(self.simplified_cb)
        f.addRow(self.filter_cb)
        self.setLayout(f)

    def _apply_preset(self, mode: str) -> None:
        p = QUALITY_PRESETS.get(mode)
        if not p:
            return
        self.temp_slider.setValue(int(p["temperature"] * 100))
        self.temp_entry.setText(f"{p['temperature']:.2f}")
        self.self_consist_cb.setChecked(p["self_consistency"])
        self.controller.update_setting("summarisation.quality_mode", mode)

    def _on_temp_entry(self) -> None:
        try:
            v = float(self.temp_entry.text())
            if 0.0 <= v <= 0.7:
                self.temp_slider.setValue(int(v * 100))
                return
        except ValueError:
            pass
        self.temp_entry.setText(f"{self.temp_slider.value() / 100:.2f}")

    # V7.5.1: live temperature warning — many models produce degenerate
    # output at t=0.  Mirrors the wizard's _check_temp_warning.
    def _check_temp_warning(self, value: int) -> None:
        t = value / 100.0
        p = theme_manager.palette
        if t < 0.1:
            self.temp_warn_label.setText("⚠️ t=0 → empty/repetitive output — use ≥ 0.1")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.warning}; background: transparent; font-size: 10px;"
            )
        elif t < 0.2:
            self.temp_warn_label.setText("low — ok for deterministic models")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 10px;"
            )
        else:
            self.temp_warn_label.setText("")

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.quality_mode", self.quality_combo.currentText())
        c.update_setting("summarisation.temperature", self.temp_slider.value() / 100)
        c.update_setting("summarisation.coverage_threshold", self.coverage_spin.value())
        # V15.1.0: over-delivery settings
        c.update_setting("summarisation.overdeliver_enabled", self.overdeliver_cb.isChecked())
        _od_target = self.overdeliver_target_spin.value()
        # Ensure target >= threshold
        if _od_target < self.coverage_spin.value():
            _od_target = self.coverage_spin.value()
            self.overdeliver_target_spin.setValue(int(_od_target))
        c.update_setting("summarisation.overdeliver_target", _od_target)
        c.update_setting("summarisation.b3_voting_enabled", self.b3_voting_cb.isChecked())
        c.update_setting("summarisation.self_consistency", self.self_consist_cb.isChecked())
        c.update_setting("summarisation.academic_rigor", self.academic_cb.isChecked())
        # V10.1.0: grounding settings
        c.update_setting("grounding.enabled", self.grounding_cb.isChecked())
        c.update_setting("grounding.backend", self.grounding_backend.currentText())
        # V10.1.6: GPU thermal profile override
        _override_keys = ["auto", "zotac_3060", "zotac_3060_ti", "zotac_3070", "generic"]
        _idx = self.gpu_profile_combo.currentIndex()
        _override_val = _override_keys[_idx] if 0 <= _idx < len(_override_keys) else "auto"
        c.update_setting("hardware.gpu_profile_override", _override_val)
        c.update_setting("summarisation.simplified_keypoints_enabled", self.simplified_cb.isChecked())
        c.update_setting("content_filter.enabled", self.filter_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.quality_combo.setCurrentText(c.get_setting("summarisation.quality_mode", "Balanced"))
        self.temp_slider.setValue(int(c.get_setting("summarisation.temperature", 0.2) * 100))
        self.temp_entry.setText(f"{self.temp_slider.value() / 100:.2f}")
        self.coverage_spin.setValue(int(c.get_setting("summarisation.coverage_threshold", 50)))
        # V15.1.0: over-delivery settings
        self.overdeliver_cb.setChecked(c.get_setting("summarisation.overdeliver_enabled", True))
        self.overdeliver_target_spin.setValue(int(c.get_setting("summarisation.overdeliver_target", 100)))
        self.b3_voting_cb.setChecked(c.get_setting("summarisation.b3_voting_enabled", False))
        self.self_consist_cb.setChecked(c.get_setting("summarisation.self_consistency", False))
        self.academic_cb.setChecked(c.get_setting("summarisation.academic_rigor", False))
        # V10.1.0: grounding settings
        self.grounding_cb.setChecked(c.get_setting("grounding.enabled", False))
        self.grounding_backend.setCurrentText(c.get_setting("grounding.backend", "ollama"))
        # V10.1.6: GPU thermal profile override
        _current_override = c.get_setting("hardware.gpu_profile_override", "auto")
        _override_idx = {"auto": 0, "zotac_3060": 1, "zotac_3060_ti": 2,
                         "zotac_3070": 3, "generic": 4}.get(_current_override, 0)
        self.gpu_profile_combo.setCurrentIndex(_override_idx)
        self.simplified_cb.setChecked(c.get_setting("summarisation.simplified_keypoints_enabled", False))
        self.filter_cb.setChecked(c.get_setting("content_filter.enabled", True))


class AiOutputSelectionSection(QGroupBox):
    """What to include in summaries (executive/thorough/keypoints)."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output selection (what to include in summaries)", parent)
        self.controller = controller
        f = make_form()
        self.exec_cb = labeled_checkbox(
            "Executive summary  (150–200 words)",
            checked=controller.get_setting("summarisation.include_executive_summary", True),
        )
        self.thorough_cb = labeled_checkbox(
            "Thorough summary  (800–1200 words)",
            checked=controller.get_setting("summarisation.include_thorough_summary", True),
        )
        self.keypoints_cb = labeled_checkbox(
            "Keypoints  (bullet points)",
            checked=controller.get_setting("summarisation.include_keypoints", True),
        )
        f.addRow(self.exec_cb)
        f.addRow(self.thorough_cb)
        f.addRow(self.keypoints_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.include_executive_summary", self.exec_cb.isChecked())
        c.update_setting("summarisation.include_thorough_summary", self.thorough_cb.isChecked())
        c.update_setting("summarisation.include_keypoints", self.keypoints_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.exec_cb.setChecked(c.get_setting("summarisation.include_executive_summary", True))
        self.thorough_cb.setChecked(c.get_setting("summarisation.include_thorough_summary", True))
        self.keypoints_cb.setChecked(c.get_setting("summarisation.include_keypoints", True))


# ════════════════════════════════════════════════════════════════════════════
# Output sections
# ════════════════════════════════════════════════════════════════════════════

class OutputDestinationSection(QGroupBox):
    """Output-folder override + show-live-log + success-sound toggles."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output destination & interface", parent)
        self.controller = controller
        f = make_form()
        self.output_dir_edit = labeled_line(
            controller.get_setting("output.custom_dir", ""),
            placeholder="Leave blank to save next to the source document",
            tooltip="By default the output goes into the same folder as the input document.",
        )
        from PySide6.QtWidgets import QFileDialog
        dest_row = QHBoxLayout()
        dest_row.setContentsMargins(0, 0, 0, 0)
        dest_row.setSpacing(6)
        dest_row.addWidget(self.output_dir_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("Compact")
        browse_btn.clicked.connect(lambda: self._browse(QFileDialog))
        dest_row.addWidget(browse_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("Compact")
        clear_btn.clicked.connect(lambda: self.output_dir_edit.setText(""))
        dest_row.addWidget(clear_btn)
        f.addRow("Output folder", dest_row)
        self.show_log_cb = labeled_checkbox(
            "Show live log during conversion",
            checked=controller.get_setting("ui.show_live_log", False),
            tooltip="When off, only the brief status line above the progress bar is shown.",
        )
        f.addRow(self.show_log_cb)
        self.play_sound_cb = labeled_checkbox(
            "Play a success sound when conversion finishes",
            checked=controller.get_setting("ui.play_success_sound", True),
            tooltip="A gentle chime plays when a conversion completes successfully.",
        )
        f.addRow(self.play_sound_cb)
        self.setLayout(f)

    def _browse(self, QFileDialog) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose an output folder")
        if folder:
            self.output_dir_edit.setText(folder)

    def save(self) -> None:
        c = self.controller
        c.update_setting("output.custom_dir", self.output_dir_edit.text().strip())
        c.update_setting("ui.show_live_log", self.show_log_cb.isChecked())
        c.update_setting("ui.play_success_sound", self.play_sound_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.output_dir_edit.setText(c.get_setting("output.custom_dir", ""))
        self.show_log_cb.setChecked(c.get_setting("ui.show_live_log", False))
        self.play_sound_cb.setChecked(c.get_setting("ui.play_success_sound", True))


class OutputGenerateSection(QGroupBox):
    """Generate summaries/DOCX/author/TOC."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Generate", parent)
        self.controller = controller
        f = make_form()
        self.summaries_cb = labeled_checkbox(
            "Generate chapter summaries",
            checked=controller.get_setting("summarisation.enabled", False),
        )
        self.docx_cb = labeled_checkbox(
            "Generate DOCX report",
            checked=controller.get_setting("docx.enabled", False),
        )
        self.author_edit = labeled_line(
            controller.get_setting("docx.author", "MarkItDown Pro"),
            placeholder="Author name for the DOCX metadata",
        )
        self.toc_cb = labeled_checkbox(
            "Include table of contents in DOCX",
            checked=controller.get_setting("docx.include_toc", True),
        )
        f.addRow(self.summaries_cb)
        f.addRow(self.docx_cb)
        f.addRow("DOCX author", self.author_edit)
        f.addRow(self.toc_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.enabled", self.summaries_cb.isChecked())
        c.update_setting("docx.enabled", self.docx_cb.isChecked())
        c.update_setting("docx.author", self.author_edit.text().strip())
        c.update_setting("docx.include_toc", self.toc_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.summaries_cb.setChecked(c.get_setting("summarisation.enabled", False))
        self.docx_cb.setChecked(c.get_setting("docx.enabled", False))
        self.author_edit.setText(c.get_setting("docx.author", "MarkItDown Pro"))
        self.toc_cb.setChecked(c.get_setting("docx.include_toc", True))


class OutputSegmentationSection(QGroupBox):
    """Strategy + token limit + page-group + keywords."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Segmentation", parent)
        self.controller = controller
        f = make_form()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["auto", "heading", "semantic", "token"])
        self.strategy_combo.setCurrentText(controller.get_setting("segmentation.strategy", "auto"))
        self.strategy_combo.setToolTip(
            "auto: Chapter-Level → TOC → Heading → Semantic → Token (recommended)\n"
            "heading: Split at markdown headings (#, ##)\n"
            "semantic: Split by semantic similarity (LLM-based)\n"
            "token: Split at fixed token intervals (last resort)"
        )
        f.addRow("Strategy", self.strategy_combo)

        # V13.35.0: Strategy description (updates on selection change)
        _STRAT_DESC = {
            "auto": "Automatically selects the best strategy: Chapter-Level (if the PDF has outlines) → TOC → Heading → Semantic → Token. Recommended for most books.",
            "heading": "Splits at markdown headings (#, ##). Best for well-structured documents with a clear heading hierarchy.",
            "semantic": "Splits by semantic similarity between paragraphs using LLM-based boundary detection. Best for unstructured text without clear headings. Slower.",
            "token": "Splits at fixed token intervals. Guarantees segments fit the context window but may break mid-topic. Use as a last resort.",
        }
        self.strat_desc_label = QLabel(_STRAT_DESC.get(self.strategy_combo.currentText(), ""))
        self.strat_desc_label.setWordWrap(True)
        self.strat_desc_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        f.addRow("", self.strat_desc_label)
        self.strategy_combo.currentTextChanged.connect(
            lambda txt: self.strat_desc_label.setText(_STRAT_DESC.get(txt, ""))
        )

        self.token_spin = labeled_spin(
            int(controller.get_setting("segmentation.token_limit", 2000)),  # V13.35.0: 1200 → 2000 (matches settings.py default)
            minimum=500, maximum=32000,
            tooltip=(
                "Maximum tokens per segment.\n"
                "• Smaller values (500-1500): more LLM calls, but each segment fits comfortably in the context window.\n"
                "• Larger values (2000-8000): fewer calls, but risk of truncation on long chapters.\n"
                "• Default 2000 works for most models with 32k context.\n"
                "• For Gemma 4 12B (32k context, ~10.9 GB VRAM), 1500-2000 is optimal."
            ),
        )
        f.addRow("Token limit / segment", self.token_spin)
        self.page_group_spin = labeled_spin(
            int(controller.get_setting("segmentation.page_group_size", 10)),
            minimum=1, maximum=100,
        )
        f.addRow("Page-group size", self.page_group_spin)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("segmentation.strategy", self.strategy_combo.currentText())
        c.update_setting("segmentation.token_limit", self.token_spin.value())
        c.update_setting("segmentation.page_group_size", self.page_group_spin.value())

    def reload(self) -> None:
        c = self.controller
        self.strategy_combo.setCurrentText(c.get_setting("segmentation.strategy", "auto"))
        self.token_spin.setValue(int(c.get_setting("segmentation.token_limit", 2000)))  # V13.35.0: 1200 → 2000
        self.page_group_spin.setValue(int(c.get_setting("segmentation.page_group_size", 10)))


class OutputKeywordsSection(QGroupBox):
    """Custom chapter keywords — loaded from / saved to an editable MD file.

    V4.3.0: Replaces the old inline QTextEdit with a file-based editor.
    The keywords live in ``config/chapter_keywords.md`` (shipped with the
    app, user-editable in any text editor). The section shows the file
    path, a read-only preview, and "Edit file" / "Reload" buttons.

    On ``save()``, the MD file is parsed (one keyword per non-comment line)
    and the resulting list is written to ``segmentation.custom_keywords``
    so the segmenter can use it. On ``reload()``, the preview is refreshed
    from the file.
    """

    # The shipped default file, relative to the project root.
    _DEFAULT_KEYWORDS_FILE = "config/chapter_keywords.md"

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Custom chapter keywords", parent)
        self.controller = controller
        l = QVBoxLayout(self)

        # Resolve the keywords file path. Stored in settings so the user
        # can point to a custom file; defaults to the shipped one.
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[3]
        default_path = project_root / self._DEFAULT_KEYWORDS_FILE
        stored = controller.get_setting("segmentation.keywords_file", "")
        self._keywords_file = Path(stored) if stored else default_path

        # If the default file doesn't exist (e.g. running from a different
        # cwd), fall back to creating it from the in-app default.
        if not self._keywords_file.exists() and self._keywords_file == default_path:
            self._write_default_file(default_path)

        # File path row + edit/reload buttons
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_label = QLabel(str(self._keywords_file))
        self.path_label.setObjectName("Caption")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)

        self.edit_btn = QPushButton("Edit file")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setToolTip("Open the keywords file in your default text editor.")
        self.edit_btn.clicked.connect(self._on_edit_file)
        path_row.addWidget(self.edit_btn)

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setCursor(Qt.PointingHandCursor)
        self.reload_btn.setToolTip("Re-read the keywords file and update the preview.")
        self.reload_btn.clicked.connect(self._on_reload_file)
        path_row.addWidget(self.reload_btn)
        l.addLayout(path_row)

        # Read-only preview of the parsed keywords
        self.preview_label = QLabel()
        self.preview_label.setObjectName("Caption")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(
            "font-size: 11px; padding: 8px; background: rgba(0,0,0,0.03);"
            "border-radius: 4px;"
        )
        l.addWidget(self.preview_label)

        hint = QLabel(
            "Keywords are loaded from the MD file above. Edit the file to "
            "add/remove keywords (one per line; lines starting with # are "
            "comments). Used by the heading strategy to detect chapter "
            "boundaries in scanned PDFs."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        l.addWidget(hint)

        self._refresh_preview()

    def _parse_keywords_file(self) -> list:
        """Parse the MD file → list of keyword strings."""
        if not self._keywords_file.exists():
            return ["فصل", "بخش", "Chapter", "Part"]
        kws = []
        for line in self._keywords_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            # Skip comments, blank lines, and markdown blockquotes (> ...)
            if not line or line.startswith("#") or line.startswith(">"):
                continue
            kws.append(line)
        return kws

    def _refresh_preview(self) -> None:
        kws = self._parse_keywords_file()
        count = len(kws)
        preview = ", ".join(kws[:20])
        if count > 20:
            preview += f" … (+{count - 20} more)"
        self.preview_label.setText(
            f"{count} keywords loaded: {preview}"
        )

    def _on_edit_file(self) -> None:
        """Open the keywords file in the OS default text editor."""
        import os
        import subprocess
        import sys
        path = str(self._keywords_file)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:
            pass  # best-effort (UI — never crash)

    def _on_reload_file(self) -> None:
        self._refresh_preview()

    @staticmethod
    def _write_default_file(path) -> None:
        """Write the shipped default keywords if the file is missing."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Chapter Heading Keywords\n\n"
            "# English\nChapter\nPart\nSection\nUnit\nLesson\nModule\n"
            "Appendix\nIntroduction\nPreface\nPrologue\nEpilogue\n\n"
            "# Persian\nفصل\nبخش\nقسمت\nدرس\nمبحث\nباب\nمقدمه\nپیوست\n",
            encoding="utf-8",
        )

    def save(self) -> None:
        kws = self._parse_keywords_file()
        self.controller.update_setting("segmentation.custom_keywords", kws)
        self.controller.update_setting(
            "segmentation.keywords_file", str(self._keywords_file)
        )

    def reload(self) -> None:
        from pathlib import Path
        stored = self.controller.get_setting("segmentation.keywords_file", "")
        if stored:
            self._keywords_file = Path(stored)
        self.path_label.setText(str(self._keywords_file))
        self._refresh_preview()


class OutputPostprocessSection(QGroupBox):
    """Markdown post-processing toggles."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Markdown post-processing", parent)
        self.controller = controller
        f = make_form()
        self.clean_cb = labeled_checkbox("Clean Markdown (whitespace, headings)",
                                         checked=controller.get_setting("postprocess.clean_markdown", True))
        self.spaces_cb = labeled_checkbox("Fix missing spaces between words",
                                          checked=controller.get_setting("postprocess.fix_missing_spaces", False))
        self.pagehead_cb = labeled_checkbox("Remove page-number headings",
                                            checked=controller.get_setting("postprocess.remove_page_number_headings", True))
        self.separators_cb = labeled_checkbox("Convert separators to HTML comments",
                                              checked=controller.get_setting("postprocess.convert_separators_to_comments", False))
        self.tokensaver_cb = labeled_checkbox("Token saver (trim very long pages)",
                                              checked=controller.get_setting("postprocess.token_saver", True))
        f.addRow(self.clean_cb)
        f.addRow(self.spaces_cb)
        f.addRow(self.pagehead_cb)
        f.addRow(self.separators_cb)
        f.addRow(self.tokensaver_cb)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("postprocess.clean_markdown", self.clean_cb.isChecked())
        c.update_setting("postprocess.fix_missing_spaces", self.spaces_cb.isChecked())
        c.update_setting("postprocess.remove_page_number_headings", self.pagehead_cb.isChecked())
        c.update_setting("postprocess.convert_separators_to_comments", self.separators_cb.isChecked())
        c.update_setting("postprocess.token_saver", self.tokensaver_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.clean_cb.setChecked(c.get_setting("postprocess.clean_markdown", True))
        self.spaces_cb.setChecked(c.get_setting("postprocess.fix_missing_spaces", False))
        self.pagehead_cb.setChecked(c.get_setting("postprocess.remove_page_number_headings", True))
        self.separators_cb.setChecked(c.get_setting("postprocess.convert_separators_to_comments", False))
        self.tokensaver_cb.setChecked(c.get_setting("postprocess.token_saver", True))


class OutputRagSection(QGroupBox):
    """RAG frontmatter + target format."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("RAG output", parent)
        self.controller = controller
        f = make_form()
        self.frontmatter_cb = labeled_checkbox(
            "Include YAML frontmatter per chapter",
            checked=controller.get_setting("rag.include_frontmatter", True),
        )
        self.target_combo = labeled_combo(
            ["chromadb", "notebooklm", "plain"],
            controller.get_setting("rag.target_format", "chromadb"),
        )
        f.addRow(self.frontmatter_cb)
        f.addRow("Target format", self.target_combo)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("rag.include_frontmatter", self.frontmatter_cb.isChecked())
        c.update_setting("rag.target_format", self.target_combo.currentText())

    def reload(self) -> None:
        c = self.controller
        self.frontmatter_cb.setChecked(c.get_setting("rag.include_frontmatter", True))
        idx = self.target_combo.findText(c.get_setting("rag.target_format", "chromadb"))
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)


class OutputStudioSection(QGroupBox):
    """V4.1.0: Output Studio — toggle which extra output types to generate.

    Replaces the old ``OutputComingSoonSection`` (V4.0.0 disabled stubs).
    Each checkbox maps to a ``outputs.<name>`` setting and, through
    ``Controller.build_request_from_ui``, to the matching ``output_*`` flag
    on ``ConversionRequest``. The converter only invokes a generator when its
    flag is enabled, so unchecking an output skips its LLM call entirely.

    V10.29.0 (Sprint 2.2): The output list is now imported from
    ``core.outputs.registry`` — the single source of truth.  Previously
    this section hardcoded 9 outputs and silently missed evidence_map +
    the 5 V10.20.0/V10.21.0 outputs.
    """

    # V10.29.0: import from the registry so this list can never drift
    # from the wizard / dialog / controller again.
    from core.outputs.registry import get_settings_section_outputs as _get_outputs
    _OUTPUTS = _get_outputs()

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Output Studio", parent)
        self.controller = controller
        f = make_form()

        self._checkboxes: dict = {}
        for key, label, default in self._OUTPUTS:
            checked = controller.get_setting(key, default)
            cb = labeled_checkbox(label, checked=checked)
            self._checkboxes[key] = (cb, default)
            f.addRow(cb)

        hint = QLabel(
            "Each enabled output adds files to the output folder after the "
            "simplified keypoints. Disable any you don't need to skip its LLM "
            "call. The Mind Map is fully deterministic (no LLM, instant)."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        for key, (cb, _default) in self._checkboxes.items():
            c.update_setting(key, cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        for key, (cb, default) in self._checkboxes.items():
            cb.setChecked(c.get_setting(key, default))


# ════════════════════════════════════════════════════════════════════════════
# V11.19: Default Engines section — central place to pick the default
# model/engine/format for each standalone service dialog.
# ════════════════════════════════════════════════════════════════════════════

class DefaultsSection(QGroupBox):
    """Default engines/models/formats for the standalone service dialogs.

    Each tool's dialog (Summarize, OCR, PDF→MD, TTS, Translation) shows a
    "Default (change in Settings)" option that, when selected, reads from
    the ``quick_services.defaults`` settings block configured here.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Default engines & models", parent)
        self.controller = controller
        f = make_form()

        # ── Summarization ──────────────────────────────────────────────
        summ_lbl = QLabel("Summarization Service")
        summ_lbl.setObjectName("SectionTitle")
        f.addRow("", summ_lbl)

        self.summ_model_combo = QComboBox()
        self.summ_model_combo.setEditable(True)
        self.summ_model_combo.setMinimumWidth(300)
        self.summ_model_combo.setToolTip(
            "The default model used by the Summarization Service when "
            "'Default Model' is selected. Leave empty to use the main "
            "summarisation.model setting."
        )
        f.addRow("Default LLM model", self.summ_model_combo)

        self.summ_quality_combo = QComboBox()
        self.summ_quality_combo.addItem("Fast", "fast")
        self.summ_quality_combo.addItem("Standard", "standard")
        self.summ_quality_combo.addItem("Thorough", "thorough")
        f.addRow("Default quality", self.summ_quality_combo)

        self.summ_format_combo = QComboBox()
        self.summ_format_combo.addItem("Markdown (.md)", ".md")
        self.summ_format_combo.addItem("Word document (.docx)", ".docx")
        self.summ_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.summ_format_combo)

        self.summ_obsidian_cb = labeled_checkbox(
            "Obsidian-style markdown by default",
            checked=controller.get_setting("quick_services.defaults.summarize_obsidian", False),
            tooltip="Wrap summaries in YAML front-matter + Obsidian callouts.",
        )
        f.addRow(self.summ_obsidian_cb)

        # ── OCR ────────────────────────────────────────────────────────
        ocr_lbl = QLabel("OCR Service")
        ocr_lbl.setObjectName("SectionTitle")
        f.addRow("", ocr_lbl)

        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItem("Auto (cascade)", "auto")
        self.ocr_engine_combo.addItem("pypdf (digital PDFs)", "pypdf")
        self.ocr_engine_combo.addItem("Ollama Vision (OlmOCR/Qwen)", "ollama")
        self.ocr_engine_combo.addItem("Local VLM (llava)", "vlm")
        self.ocr_engine_combo.addItem("Tesseract", "tesseract")
        f.addRow("Default engine", self.ocr_engine_combo)

        self.ocr_model_combo = QComboBox()
        self.ocr_model_combo.setEditable(True)
        self.ocr_model_combo.setToolTip(
            "The default OCR model. Leave empty to use ocr.primary_model."
        )
        f.addRow("Default OCR model", self.ocr_model_combo)

        self.ocr_format_combo = QComboBox()
        self.ocr_format_combo.addItem("Markdown (.md)", ".md")
        self.ocr_format_combo.addItem("Plain text (.txt)", ".txt")
        self.ocr_format_combo.addItem("Word document (.docx)", ".docx")
        self.ocr_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.ocr_format_combo)

        # ── PDF → Markdown ─────────────────────────────────────────────
        pdf_lbl = QLabel("PDF → Markdown")
        pdf_lbl.setObjectName("SectionTitle")
        f.addRow("", pdf_lbl)

        self.pdf_format_combo = QComboBox()
        self.pdf_format_combo.addItem("Markdown (.md)", ".md")
        self.pdf_format_combo.addItem("Word document (.docx)", ".docx")
        self.pdf_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.pdf_format_combo)

        # ── TTS ────────────────────────────────────────────────────────
        tts_lbl = QLabel("TTS Service")
        tts_lbl.setObjectName("SectionTitle")
        f.addRow("", tts_lbl)

        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItem("Default (use tts.en_engine)", "")
        self.tts_engine_combo.addItem("Piper", "piper")
        self.tts_engine_combo.addItem("NeuTTS", "neutts")
        self.tts_engine_combo.addItem("Coqui XTTS v2", "coqui")
        f.addRow("Default engine", self.tts_engine_combo)

        # ── Translation ────────────────────────────────────────────────
        tr_lbl = QLabel("Translation Service")
        tr_lbl.setObjectName("SectionTitle")
        f.addRow("", tr_lbl)

        self.tr_backend_combo = QComboBox()
        self.tr_backend_combo.addItem("Default (use translation.backend)", "")
        # V13.31.0 (#13): NLLB backend removed from the UI. Only the
        # TranslateGemma (Ollama) backend is exposed.
        self.tr_backend_combo.addItem("Ollama (TranslateGemma)", "ollama")
        f.addRow("Default backend", self.tr_backend_combo)

        # ── Refresh button ─────────────────────────────────────────────
        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh Ollama models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)

        hint = QLabel(
            "These defaults are used by the standalone service dialogs (Tools → "
            "Summarize / OCR / PDF→Markdown / TTS / Translation). Each dialog "
            "shows a \"Default (change in Settings)\" option that, when selected, "
            "reads from this page."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)
        self._reload_widget_values()
        # V18.20.4.5 (W-b11): worker ref for the async model fetch (a
        # Python ref keeps the SimpleWorker QObject alive mid-run).
        self._models_worker = None
        self._refresh_models()

    def _reload_widget_values(self) -> None:
        """Load the saved settings into the widgets (non-model ones)."""
        c = self.controller
        # Quality
        q = c.get_setting("quick_services.defaults.summarize_quality", "standard")
        idx = self.summ_quality_combo.findData(q)
        if idx >= 0:
            self.summ_quality_combo.setCurrentIndex(idx)
        # Summarize format
        sf = c.get_setting("quick_services.defaults.summarize_format", ".md")
        idx = self.summ_format_combo.findData(sf)
        if idx >= 0:
            self.summ_format_combo.setCurrentIndex(idx)
        # OCR engine
        oe = c.get_setting("quick_services.defaults.ocr_engine", "auto")
        idx = self.ocr_engine_combo.findData(oe)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)
        # OCR format
        of = c.get_setting("quick_services.defaults.ocr_format", ".md")
        idx = self.ocr_format_combo.findData(of)
        if idx >= 0:
            self.ocr_format_combo.setCurrentIndex(idx)
        # PDF format
        pf = c.get_setting("quick_services.defaults.pdf_format", ".md")
        idx = self.pdf_format_combo.findData(pf)
        if idx >= 0:
            self.pdf_format_combo.setCurrentIndex(idx)
        # TTS engine
        te = c.get_setting("quick_services.defaults.tts_engine", "")
        idx = self.tts_engine_combo.findData(te)
        if idx >= 0:
            self.tts_engine_combo.setCurrentIndex(idx)
        # Translation backend
        tb = c.get_setting("quick_services.defaults.translation_backend", "")
        idx = self.tr_backend_combo.findData(tb)
        if idx >= 0:
            self.tr_backend_combo.setCurrentIndex(idx)

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — the 5s-timeout
        DependencyChecker HTTP call used to run ON the UI thread here, so
        opening Settings froze the app for up to 5s when Ollama was down.
        Populate happens on the main thread in _on_models_loaded; the
        fetch fn is widget-free (pure HTTP)."""
        controller = self.controller  # snapshot on the main thread
        _refresh_models_async(
            self, lambda: _get_ollama_models(controller),
            self._on_models_loaded, self.refresh_btn)

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate the model combos (MAIN thread)."""
        c = self.controller

        # Summarize model — has a "use main setting" empty option
        summ_current = c.get_setting("quick_services.defaults.summarize_model", "")
        summ_current_text = self.summ_model_combo.currentText().strip()
        self.summ_model_combo.clear()
        self.summ_model_combo.addItem("Default (use summarisation.model)", "")
        for m in models:
            self.summ_model_combo.addItem(_badge(m) + m, m)
        # Restore selection: saved setting → previously-typed text → first item
        target = summ_current or summ_current_text
        if target:
            idx = self.summ_model_combo.findData(target)
            if idx >= 0:
                self.summ_model_combo.setCurrentIndex(idx)
            else:
                self.summ_model_combo.setEditText(target)

        # OCR model — has a "use primary_model" empty option
        ocr_current = c.get_setting("quick_services.defaults.ocr_model", "")
        ocr_current_text = self.ocr_model_combo.currentText().strip()
        self.ocr_model_combo.clear()
        self.ocr_model_combo.addItem("Default (use ocr.primary_model)", "")
        for m in models:
            self.ocr_model_combo.addItem(_badge(m) + m, m)
        target = ocr_current or ocr_current_text
        if target:
            idx = self.ocr_model_combo.findData(target)
            if idx >= 0:
                self.ocr_model_combo.setCurrentIndex(idx)
            else:
                self.ocr_model_combo.setEditText(target)

    def save(self) -> None:
        c = self.controller
        c.update_setting("quick_services.defaults.summarize_model", self.summ_model_combo.currentData() or "")
        c.update_setting("quick_services.defaults.summarize_quality", self.summ_quality_combo.currentData() or "standard")
        c.update_setting("quick_services.defaults.summarize_format", self.summ_format_combo.currentData() or ".md")
        c.update_setting("quick_services.defaults.summarize_obsidian", self.summ_obsidian_cb.isChecked())
        c.update_setting("quick_services.defaults.ocr_engine", self.ocr_engine_combo.currentData() or "auto")
        c.update_setting("quick_services.defaults.ocr_model", self.ocr_model_combo.currentData() or "")
        c.update_setting("quick_services.defaults.ocr_format", self.ocr_format_combo.currentData() or ".md")
        c.update_setting("quick_services.defaults.pdf_format", self.pdf_format_combo.currentData() or ".md")
        c.update_setting("quick_services.defaults.tts_engine", self.tts_engine_combo.currentData() or "")
        c.update_setting("quick_services.defaults.translation_backend", self.tr_backend_combo.currentData() or "")

    def reload(self) -> None:
        self._reload_widget_values()
        self._refresh_models()
        self.summ_obsidian_cb.setChecked(
            self.controller.get_setting("quick_services.defaults.summarize_obsidian", False)
        )
