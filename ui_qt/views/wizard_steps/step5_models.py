"""Step 5: Model Selection — Step5Models (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step5Models
(back-compat facade).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.llamacpp_config import LlamaCppConfigMixin
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# V18.20.3.12 (F821) pattern, carried with the class: the
# best-effort ``logger.debug`` sites must not NameError on
# swallowed-exception paths (house pattern per queue_view).
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Step 5: Model Selection
# ════════════════════════════════════════════════════════════════════════════


class Step5Models(LlamaCppConfigMixin, WizardStep):
    """V16.0.9: Model selection — 4-mode architecture (single/dual × local/API).

    V0.04: mixes in LlamaCppConfigMixin (ui_qt/components/llamacpp_config.py)
    — the llama.cpp endpoint box, its two-stage Test-connection probe, and
    model discovery live there so this step module stays inside the O-b1
    per-step line budget.
    """

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Model selection")
        title.setObjectName("H2")
        lay.addWidget(title)

        # ── V16.0.9: 4-mode architecture selector ──────────────────────
        arch_box = QGroupBox("Model architecture")
        arch_lay = QVBoxLayout(arch_box)
        arch_lay.setContentsMargins(10, 10, 10, 8)
        arch_lay.setSpacing(6)

        arch_desc_top = QLabel(
            "Choose how models are used for this conversion. The 4 modes cover "
            "every combination of single/dual × local/API."
        )
        arch_desc_top.setWordWrap(True)
        arch_desc_top.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        arch_lay.addWidget(arch_desc_top)

        self.arch_combo = QComboBox()
        self.arch_combo.addItem("🏠  Single model — Local", "single_local")
        self.arch_combo.addItem("🏠  Dual model — Local (heavy + fast)", "dual_local")
        self.arch_combo.addItem("☁️  Single model — API", "single_api")
        self.arch_combo.addItem("☁️  Dual model — API (fast + accurate)", "dual_api")
        _saved_arch = (
            self.controller.get_setting("summarisation.model_architecture", "single_local")
            or "single_local"
        )
        # V16.0.9: backward-compat — legacy "single" → "single_local"
        if _saved_arch == "single":
            _saved_arch = "single_local"
        _arch_idx = self.arch_combo.findData(_saved_arch)
        if _arch_idx >= 0:
            self.arch_combo.setCurrentIndex(_arch_idx)
        self.arch_combo.setToolTip(
            "Select the model architecture for this conversion.\n\n"
            "• Single — Local: One local model (Ollama/LM Studio) does everything. "
            "Simplest setup, no VRAM juggling.\n"
            "• Dual — Local: Heavy + fast local models alternate in VRAM. "
            "Heavy (e.g. gemma4-12b) does deep work; fast (e.g. LFM2.5-2.6B) does "
            "concept extraction, gap-fill, merging, scholar reflection.\n"
            "• Single — API: One cloud API model (OpenRouter/OpenAI/9Router) does "
            "everything. No GPU needed.\n"
            "• Dual — API: Cheap fast cloud workhorse + expensive accurate cloud "
            "model. Best cost/quality balance for cloud users."
        )
        self.arch_combo.currentIndexChanged.connect(self._on_arch_change)
        arch_lay.addWidget(self.arch_combo)

        self.arch_desc_label = QLabel("")
        self.arch_desc_label.setObjectName("Caption")
        self.arch_desc_label.setWordWrap(True)
        self.arch_desc_label.setStyleSheet(
            "color: #555; font-size: 11px; padding: 6px 8px; "
            "background: rgba(91,155,213,0.07); border-radius: 4px;"
        )
        arch_lay.addWidget(self.arch_desc_label)
        lay.addWidget(arch_box)

        # ── Local configuration box (modes 1, 2) ───────────────────────
        self.local_box = QGroupBox("🏠 Local configuration")
        local_lay = QVBoxLayout(self.local_box)
        local_lay.setContentsMargins(10, 10, 10, 8)
        local_lay.setSpacing(6)

        self.local_desc = QLabel(
            "Local models run on your GPU via Ollama (or LM Studio). Click "
            "Refresh to detect installed models."
        )
        self.local_desc.setWordWrap(True)
        self.local_desc.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        local_lay.addWidget(self.local_desc)

        # Local backend selector (Ollama / llama.cpp / LM Studio)
        backend_row = QHBoxLayout()
        backend_row.setSpacing(8)
        backend_row.addWidget(QLabel("Local backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Ollama", "ollama")
        # V0.04: llama.cpp server (llama-server) — the rig's primary local
        # backend. Listed second because it is the CURRENT default for new
        # configurations (see utils/settings.py V0.04).
        self.backend_combo.addItem("llama.cpp server", "llamacpp")
        self.backend_combo.addItem("LM Studio", "lmstudio")
        _saved_backend = self.controller.get_setting("summarisation.provider", "llamacpp")
        if _saved_backend not in ("ollama", "llamacpp", "lmstudio"):
            _saved_backend = "llamacpp"
        _b_idx = self.backend_combo.findData(_saved_backend)
        if _b_idx >= 0:
            self.backend_combo.setCurrentIndex(_b_idx)
        self.backend_combo.currentIndexChanged.connect(self._on_arch_change)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_change)
        backend_row.addWidget(self.backend_combo, 1)
        backend_row.addStretch()
        local_lay.addLayout(backend_row)

        # LM Studio URL field (visible only when backend = lmstudio)
        self.lmstudio_widget = QWidget()
        lmstudio_lay = QVBoxLayout(self.lmstudio_widget)
        lmstudio_lay.setContentsMargins(0, 0, 0, 0)
        lmstudio_lay.setSpacing(5)
        lmstudio_row = QHBoxLayout()
        lmstudio_row.setSpacing(8)
        self.lmstudio_url_edit = QLineEdit(
            self.controller.get_setting("summarisation.lmstudio_url", "http://localhost:1234/v1")
        )
        lmstudio_row.addWidget(QLabel("LM Studio URL:"))
        lmstudio_row.addWidget(self.lmstudio_url_edit, 1)
        lmstudio_lay.addLayout(lmstudio_row)
        local_lay.addWidget(self.lmstudio_widget)

        # ── V0.04: llama.cpp server configuration (mixin-owned) ──
        # The endpoint box (URL / API key / model / Test connection) comes
        # from LlamaCppConfigMixin — see ui_qt/components/llamacpp_config.py.
        self.llamacpp_widget = self.build_llamacpp_box()
        local_lay.addWidget(self.llamacpp_widget)

        # Refresh button
        refresh_row = QHBoxLayout()
        refresh_row.setSpacing(8)
        self.refresh_btn = QPushButton("  🔄 Refresh models")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._refresh_models)
        refresh_row.addWidget(self.refresh_btn)
        refresh_row.addStretch()
        local_lay.addLayout(refresh_row)

        # Heavy / summarization model
        local_lay.addWidget(QLabel("Summarization (heavy) model:"))
        self.summ_combo = QComboBox()
        local_lay.addWidget(self.summ_combo)

        # OCR model
        self.ocr_label = QLabel("OCR model:")
        local_lay.addWidget(self.ocr_label)
        self.ocr_combo = QComboBox()
        local_lay.addWidget(self.ocr_combo)

        # Fast model (mode 2 only)
        self.fast_label = QLabel("Fast model (concept extraction / gap-fill / merge):")
        local_lay.addWidget(self.fast_label)
        self.fast_combo = QComboBox()
        local_lay.addWidget(self.fast_combo)

        lay.addWidget(self.local_box)

        # ── Heavy API configuration box (modes 3, 4) ───────────────────
        self.heavy_api_box = QGroupBox("☁️ Heavy API configuration (accurate model)")
        heavy_api_lay = QVBoxLayout(self.heavy_api_box)
        heavy_api_lay.setContentsMargins(10, 10, 10, 8)
        heavy_api_lay.setSpacing(6)

        self.heavy_api_desc = QLabel(
            "The accurate / expensive cloud model. Handles deep summarization, "
            "theme synthesis, and content judging. OpenAI-compatible (OpenRouter, "
            "OpenAI, 9Router, Groq, …)."
        )
        self.heavy_api_desc.setWordWrap(True)
        self.heavy_api_desc.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        heavy_api_lay.addWidget(self.heavy_api_desc)

        from core.llm.cloud_client import CLOUD_PRESETS

        heavy_preset_row = QHBoxLayout()
        heavy_preset_row.setSpacing(8)
        heavy_preset_row.addWidget(QLabel("Preset:"))
        self.cloud_preset_combo = QComboBox()
        for p in CLOUD_PRESETS:
            self.cloud_preset_combo.addItem(p["label"])
        heavy_preset_row.addWidget(self.cloud_preset_combo, 1)
        self.cloud_fill_btn = QPushButton("Fill")
        self.cloud_fill_btn.setObjectName("Compact")
        self.cloud_fill_btn.setCursor(Qt.PointingHandCursor)
        self.cloud_fill_btn.setToolTip("Fill base URL + model from the selected preset")
        self.cloud_fill_btn.clicked.connect(self._fill_cloud_preset)
        heavy_preset_row.addWidget(self.cloud_fill_btn)
        heavy_api_lay.addLayout(heavy_preset_row)

        cloud_url_row = QHBoxLayout()
        cloud_url_row.setSpacing(8)
        self.cloud_url_edit = QLineEdit(
            self.controller.get_setting(
                "summarisation.api_base_url", "https://openrouter.ai/api/v1"
            )
        )
        cloud_url_row.addWidget(QLabel("API base URL:"))
        cloud_url_row.addWidget(self.cloud_url_edit, 1)
        heavy_api_lay.addLayout(cloud_url_row)

        cloud_key_row = QHBoxLayout()
        cloud_key_row.setSpacing(8)
        # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
        self.cloud_key_edit = QLineEdit(self.controller.get_secret("summarisation.api_key", ""))
        self.cloud_key_edit.setEchoMode(QLineEdit.Password)
        cloud_key_row.addWidget(QLabel("API key:"))
        cloud_key_row.addWidget(self.cloud_key_edit, 1)
        heavy_api_lay.addLayout(cloud_key_row)
        # V0.16 (Phase 3 / 3.4): keychain storage indicator
        from core.system.secrets import storage_status_label

        _heavy_key_hint = QLabel(storage_status_label())
        _heavy_key_hint.setWordWrap(True)
        heavy_api_lay.addWidget(_heavy_key_hint)

        cloud_model_row = QHBoxLayout()
        cloud_model_row.setSpacing(8)
        self.cloud_model_edit = QLineEdit(
            self.controller.get_setting("summarisation.cloud_model", "")
        )
        cloud_model_row.addWidget(QLabel("Model name:"))
        cloud_model_row.addWidget(self.cloud_model_edit, 1)
        heavy_api_lay.addLayout(cloud_model_row)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.cloud_test_btn = QPushButton("🔌  Test connection")
        self.cloud_test_btn.setObjectName("Secondary")
        self.cloud_test_btn.setCursor(Qt.PointingHandCursor)
        self.cloud_test_btn.setToolTip(
            "Send a tiny request to verify the base URL, key, and model work."
        )
        self.cloud_test_btn.clicked.connect(self._test_cloud_connection)
        test_row.addWidget(self.cloud_test_btn)
        self.cloud_test_label = QLabel("")
        self.cloud_test_label.setObjectName("Caption")
        self.cloud_test_label.setWordWrap(True)
        test_row.addWidget(self.cloud_test_label, 1)
        heavy_api_lay.addLayout(test_row)

        lay.addWidget(self.heavy_api_box)

        # ── Fast API configuration box (mode 4 only) ────────────────────
        self.fast_api_box = QGroupBox("⚡ Fast API configuration (cheap workhorse)")
        fast_api_lay = QVBoxLayout(self.fast_api_box)
        fast_api_lay.setContentsMargins(10, 10, 10, 8)
        fast_api_lay.setSpacing(6)

        self.fast_api_desc = QLabel(
            "The cheap fast cloud workhorse. Handles concept extraction, "
            "gap-fill, bullet merging, and scholar reflection. Pick a low-cost "
            "model (e.g. gemini-2.5-flash, gpt-4o-mini, llama-3.1-8b)."
        )
        self.fast_api_desc.setWordWrap(True)
        self.fast_api_desc.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
        fast_api_lay.addWidget(self.fast_api_desc)

        fast_preset_row = QHBoxLayout()
        fast_preset_row.setSpacing(8)
        fast_preset_row.addWidget(QLabel("Preset:"))
        self.fast_preset_combo = QComboBox()
        for p in CLOUD_PRESETS:
            self.fast_preset_combo.addItem(p["label"])
        fast_preset_row.addWidget(self.fast_preset_combo, 1)
        self.fast_fill_btn = QPushButton("Fill")
        self.fast_fill_btn.setObjectName("Compact")
        self.fast_fill_btn.setCursor(Qt.PointingHandCursor)
        self.fast_fill_btn.setToolTip("Fill base URL + model from the selected preset")
        self.fast_fill_btn.clicked.connect(self._fill_fast_cloud_preset)
        fast_preset_row.addWidget(self.fast_fill_btn)
        fast_api_lay.addLayout(fast_preset_row)

        fast_url_row = QHBoxLayout()
        fast_url_row.setSpacing(8)
        self.fast_api_url_edit = QLineEdit(
            self.controller.get_setting("summarisation.fast_api_url", "")
        )
        self.fast_api_url_edit.setPlaceholderText("https://openrouter.ai/api/v1")
        fast_url_row.addWidget(QLabel("API base URL:"))
        fast_url_row.addWidget(self.fast_api_url_edit, 1)
        fast_api_lay.addLayout(fast_url_row)

        fast_key_row = QHBoxLayout()
        fast_key_row.setSpacing(8)
        # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
        self.fast_api_key_edit = QLineEdit(
            self.controller.get_secret("summarisation.fast_api_key", "")
        )
        self.fast_api_key_edit.setEchoMode(QLineEdit.Password)
        self.fast_api_key_edit.setPlaceholderText("sk-...")
        fast_key_row.addWidget(QLabel("API key:"))
        fast_key_row.addWidget(self.fast_api_key_edit, 1)
        fast_api_lay.addLayout(fast_key_row)

        fast_model_row = QHBoxLayout()
        fast_model_row.setSpacing(8)
        self.fast_api_model_edit = QLineEdit(
            self.controller.get_setting("summarisation.fast_api_model", "")
        )
        self.fast_api_model_edit.setPlaceholderText("google/gemini-2.5-flash-preview:free")
        fast_model_row.addWidget(QLabel("Model name:"))
        fast_model_row.addWidget(self.fast_api_model_edit, 1)
        fast_api_lay.addLayout(fast_model_row)

        fast_test_row = QHBoxLayout()
        fast_test_row.setSpacing(8)
        self.fast_test_btn = QPushButton("🔌  Test connection")
        self.fast_test_btn.setObjectName("Secondary")
        self.fast_test_btn.setCursor(Qt.PointingHandCursor)
        self.fast_test_btn.setToolTip("Send a tiny request to verify the fast API works.")
        self.fast_test_btn.clicked.connect(self._test_fast_cloud_connection)
        fast_test_row.addWidget(self.fast_test_btn)
        self.fast_test_label = QLabel("")
        self.fast_test_label.setObjectName("Caption")
        self.fast_test_label.setWordWrap(True)
        fast_test_row.addWidget(self.fast_test_label, 1)
        fast_api_lay.addLayout(fast_test_row)

        lay.addWidget(self.fast_api_box)

        # ── Parameters box (all modes) ─────────────────────────────────
        params_box = QGroupBox("Parameters")
        params_lay = QVBoxLayout(params_box)
        params_lay.setContentsMargins(10, 10, 10, 8)
        params_lay.setSpacing(6)

        # Workers + heavy temperature
        row = QHBoxLayout()
        row.setSpacing(10)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 4)
        self.workers_spin.setValue(self.state.max_workers)
        self.workers_spin.valueChanged.connect(self._check_workers_warning)
        self._workers_lock_label = None
        self._check_thermal_lock()
        row.addWidget(QLabel("Max workers:"))
        row.addWidget(self.workers_spin)
        self.workers_warn_label = QLabel("")
        self.workers_warn_label.setObjectName("Caption")
        self.workers_warn_label.setWordWrap(True)
        row.addWidget(self.workers_warn_label)

        from PySide6.QtWidgets import QDoubleSpinBox

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setValue(self.state.temperature)
        self.temp_spin.setToolTip(
            "Sampling temperature for the heavy/primary model.\n\n"
            "• Qwythos-9B: minimum 0.6 (fine-tuner spec)\n"
            "• gemma2:7b/9b: 0.4-0.9\n"
            "• qwen2.5:7b: 0.3-0.9\n"
            "• Cloud APIs: 0.2-0.7 typical\n"
            "• 0.0 — DO NOT USE — produces empty/degenerate output on most local models\n"
        )
        row.addWidget(QLabel("Heavy temp:"))
        row.addWidget(self.temp_spin)
        self.temp_warn_label = QLabel("")
        self.temp_warn_label.setObjectName("Caption")
        row.addWidget(self.temp_warn_label)
        self.temp_spin.valueChanged.connect(self._check_temp_warning)
        self._check_temp_warning(self.temp_spin.value())
        row.addStretch()
        params_lay.addLayout(row)

        # Heavy model context size
        # V0.04: range widened to 1024–262144 (was 4096–131072) so the GUI
        # never caps a model's real window — 65k-class local models
        # (llama.cpp Ternary-Bonsai: 65536) and 200k-class models now both
        # fit. GENERAL RULE: spinbox ceilings are UI conveniences, not
        # model policy; the provider layer owns the model-specific caps.
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(10)
        self.heavy_ctx_spin = QSpinBox()
        self.heavy_ctx_spin.setRange(1024, 262144)
        self.heavy_ctx_spin.setSingleStep(4096)
        self.heavy_ctx_spin.setValue(min(max(self.state.max_context_tokens, 1024), 262144))
        self.heavy_ctx_spin.setToolTip(
            "Context window size for the heavy/primary model.\n\n"
            "gemma4-12b: 32768 (32K)\n"
            "llama.cpp Ternary-Bonsai-2-27B: 65536 (65K)\n"
            "Cloud APIs: use the model's maximum (often 128K+).\n"
            "Set per your model's maximum."
        )
        ctx_row.addWidget(QLabel("Heavy model context:"))
        ctx_row.addWidget(self.heavy_ctx_spin)
        ctx_row.addStretch()
        params_lay.addLayout(ctx_row)

        # V0.04: Heavy model OUTPUT budget — previously the wizard offered
        # no way to set the output cap at the model step (only Step 7b had
        # it, starting from a stale 8192 state default). The 12k-output
        # llama.cpp model needs it front and centre: 12288.
        out_row = QHBoxLayout()
        out_row.setSpacing(10)
        self.heavy_out_spin = QSpinBox()
        self.heavy_out_spin.setRange(256, 65536)
        self.heavy_out_spin.setSingleStep(1024)
        self.heavy_out_spin.setValue(
            min(max(int(getattr(self.state, "max_output_tokens", 12288) or 12288), 256), 65536)
        )
        self.heavy_out_spin.setToolTip(
            "Maximum OUTPUT tokens per LLM call for the heavy/primary model.\n\n"
            "llama.cpp Ternary-Bonsai-2-27B: 12288 (12K — the model's output cap)\n"
            "Ollama 27B quants: 16000\n"
            "This is a ceiling per call, not a target — shorter answers are fine.\n"
            "The provider clamps requests to this automatically."
        )
        out_row.addWidget(QLabel("Heavy model output:"))
        out_row.addWidget(self.heavy_out_spin)
        out_row.addStretch()
        params_lay.addLayout(out_row)

        # Fast model temperature + context (modes 2, 4)
        fast_row = QHBoxLayout()
        fast_row.setSpacing(10)

        self.fast_temp_spin = QDoubleSpinBox()
        self.fast_temp_spin.setRange(0.0, 2.0)
        self.fast_temp_spin.setSingleStep(0.05)
        self.fast_temp_spin.setDecimals(2)
        _default_fast_temp = 0.1
        try:
            _default_fast_temp = float(
                self.controller.get_setting("summarisation.fast_model_temperature", 0.1)
            )
        except Exception:
            pass
        self.fast_temp_spin.setValue(_default_fast_temp)
        self.fast_temp_spin.setToolTip(
            "Sampling temperature for the fast model.\n\n"
            "LFM2.5-2.6B recommends 0.1.\n"
            "Qwen models recommend 0.6-0.8.\n"
            "Gemma models recommend 1.0.\n"
            "Cloud flash models: 0.2-0.4 typical."
        )
        self.fast_temp_label = QLabel("Fast temp:")
        fast_row.addWidget(self.fast_temp_label)
        fast_row.addWidget(self.fast_temp_spin)

        self.fast_ctx_spin = QSpinBox()
        self.fast_ctx_spin.setRange(1024, 262144)  # V0.04: widened with heavy ctx
        self.fast_ctx_spin.setSingleStep(4096)
        _default_fast_ctx = 131072
        try:
            _default_fast_ctx = int(
                self.controller.get_setting("summarisation.fast_model_context", 131072)
            )
        except Exception:
            pass
        self.fast_ctx_spin.setValue(_default_fast_ctx)
        self.fast_ctx_spin.setToolTip(
            "Context window size for the fast model.\n\n"
            "LFM2.5-2.6B supports up to 131072 (128K).\n"
            "Cloud flash models: use the model's maximum.\n"
            "Set to the model's maximum for best results."
        )
        self.fast_ctx_label = QLabel("Fast context:")
        fast_row.addWidget(self.fast_ctx_label)
        fast_row.addWidget(self.fast_ctx_spin)
        fast_row.addStretch()
        params_lay.addLayout(fast_row)

        lay.addWidget(params_box)
        lay.addStretch()

        # Initial model load + visibility
        # V18.20.4.5 (W-b11): initial load is now async (see
        # _refresh_models) — never blocks wizard construction on the
        # 5s-timeout Ollama HTTP call. The None ref is replaced by the
        # running SimpleWorker so the QObject can't be GC'd mid-run.
        self._models_worker = None
        self._refresh_models()
        self._on_arch_change()

    def _get_models(self) -> list[str]:
        """Get available models from the current provider (Ollama/LM Studio).

        V0.04: the llama.cpp backend does NOT come through here —
        _refresh_models dispatches it to the mixin's llamacpp_fetch_models
        (Settings-only, worker-safe) instead, so this fn keeps its original
        Ollama shape.
        """
        try:
            from utils.dependencies import DependencyChecker

            models = DependencyChecker().get_ollama_models() or []
            return models
        except Exception:
            return []

    def _refresh_models(self) -> None:
        """Refresh the local model dropdowns (heavy, OCR, fast).

        V18.20.4.5 (W-b11): the fetch is a 5s-timeout HTTP call
        (DependencyChecker().get_ollama_models, utils/dependencies.py) that
        used to run ON the UI thread — opening the wizard froze the whole
        app for up to 5s whenever Ollama was down. It now runs on a
        SimpleWorker; the combos are repopulated on the MAIN thread from
        _on_models_loaded. ``_get_models`` stays the worker fn (pure HTTP,
        no widget access).
        """
        worker = getattr(self, "_models_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself — not running
        if in_flight:
            return  # a fetch is already in flight — don't stack workers
        # V0.04: backend-aware dispatch — llama.cpp lists its models via
        # the mixin's Settings-only worker fn (GET /v1/models with the
        # configured-model fallback); the Ollama path keeps the original
        # _get_models worker. The backend is snapshotted on the MAIN
        # thread (combo reads never cross to the worker).
        self._models_backend_snapshot = (
            self.backend_combo.currentData() if hasattr(self, "backend_combo") else "ollama"
        )
        if self._models_backend_snapshot == "llamacpp":
            worker_fn = self.llamacpp_fetch_models
        else:
            worker_fn = self._get_models
        self.refresh_btn.setEnabled(False)
        self._models_worker = SimpleWorker(worker_fn)
        self._models_worker.finished.connect(self._on_models_loaded)
        self._models_worker.failed.connect(self._on_models_failed)
        self._models_worker.start()

    def _on_models_loaded(self, models) -> None:
        """W-b11: worker finished — repopulate the dropdowns (MAIN thread)."""
        self.refresh_btn.setEnabled(True)
        models = models or []
        if not models:
            QMessageBox.information(
                self,
                "No models found",
                "No Ollama models found. Make sure Ollama is running and has models pulled.\n\n"
                "To pull models:\n"
                "  ollama pull gemma4-12b:latest\n"
                "  ollama pull qwen3-vl:8b",
            )
            return

        # Remember current selections
        summ_current = self.summ_combo.currentData() or self.controller.get_setting(
            "summarisation.model", ""
        )
        ocr_current = self.ocr_combo.currentData() or self.controller.get_setting(
            "ocr.primary_model", ""
        )
        fast_current = self.fast_combo.currentData() or self.controller.get_setting(
            "summarisation.fast_model", ""
        )

        # Repopulate
        for combo, current, _label in [
            (self.summ_combo, summ_current, "Summarization"),
            (self.ocr_combo, ocr_current, "OCR"),
            (self.fast_combo, fast_current, "Fast"),
        ]:
            combo.clear()
            combo.addItem("  (use default)", "")
            for m in models:
                combo.addItem("📝 " + m, m)
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def _on_models_failed(self, _err: str) -> None:
        """W-b11: fetch failed — fail-soft (W-b18 class: never leave the
        refresh button stuck disabled). Combos keep their current items."""
        logger.debug("Model refresh failed (W-b11 fail-soft): %s", _err)
        self.refresh_btn.setEnabled(True)

    def _on_arch_change(self) -> None:
        """V16.0.9: Show/hide config boxes based on the selected architecture.

        4 modes:
          single_local — local box only (heavy does everything)
          dual_local   — local box + fast model dropdown + fast params
          single_api   — heavy API box only
          dual_api     — heavy API box + fast API box + fast params
        """
        arch = self.arch_combo.currentData() or "single_local"
        is_local = arch in ("single_local", "dual_local")
        is_api = arch in ("single_api", "dual_api")
        is_dual = arch in ("dual_local", "dual_api")

        # Local box visibility
        self.local_box.setVisible(is_local)
        # Heavy API box visibility
        self.heavy_api_box.setVisible(is_api)
        # Fast API box visibility (dual_api only)
        self.fast_api_box.setVisible(arch == "dual_api")

        # Fast model dropdown (local) — dual_local only
        self.fast_label.setVisible(arch == "dual_local")
        self.fast_combo.setVisible(arch == "dual_local")

        # Refresh button — local modes only
        self.refresh_btn.setVisible(is_local)

        # LM Studio URL — local modes + lmstudio backend
        backend = self.backend_combo.currentData() if hasattr(self, "backend_combo") else "ollama"
        self.lmstudio_widget.setVisible(is_local and backend == "lmstudio")
        # V0.04: llama.cpp config — local modes + llamacpp backend (mixin)
        self.llamacpp_set_visible(is_local, backend)

        # Fast temp + context params — dual modes only
        self.fast_temp_label.setVisible(is_dual)
        self.fast_temp_spin.setVisible(is_dual)
        self.fast_ctx_label.setVisible(is_dual)
        self.fast_ctx_spin.setVisible(is_dual)

        # Architecture description
        descs = {
            "single_local": (
                "🏠 Single — Local: One local model (via Ollama/LM Studio) handles "
                "everything — summarization, OCR, concept extraction, judging. "
                "Simplest setup, no VRAM juggling. Best for users with a single "
                "capable model (e.g. gemma4-12b)."
            ),
            "dual_local": (
                "🏠 Dual — Local: A heavy model (e.g. gemma4-12b) does deep "
                "summarization, theme synthesis, and judging; a fast model "
                "(e.g. LFM2.5-2.6B) does concept extraction, gap-fill, bullet "
                "merging, scholar reflection. The two models alternate in VRAM — "
                "the app unloads one before loading the other."
            ),
            "single_api": (
                "☁️ Single — API: One cloud model (OpenAI-compatible: OpenRouter, "
                "OpenAI, 9Router, Groq) handles everything. No GPU needed — runs "
                "entirely in the cloud. Best when you have no local GPU or want "
                "maximum speed/quality. Pay per token."
            ),
            "dual_api": (
                "☁️ Dual — API: A cheap fast workhorse (e.g. gemini-flash, "
                "gpt-4o-mini) handles simple tasks; a more expensive accurate model "
                "(e.g. gpt-4o, claude) handles deep summarization and judging. Best "
                "cost/quality balance for cloud users — the cheap model does the "
                "high-volume simple work."
            ),
        }
        self.arch_desc_label.setText(descs.get(arch, ""))

        # Highlight the active local box border
        _active_style = (
            "QGroupBox { font-weight: bold; border: 2px solid #5B9BD5; border-radius: 6px; }"
        )
        if is_local:
            self.local_box.setStyleSheet(_active_style)

    # ── V7.5.0: Cloud preset fill + connection test ──────────────────────
    def _fill_cloud_preset(self) -> None:
        """Fill heavy API base URL + model from the selected preset."""
        from core.llm.cloud_client import CLOUD_PRESETS

        idx = self.cloud_preset_combo.currentIndex()
        if 0 <= idx < len(CLOUD_PRESETS):
            p = CLOUD_PRESETS[idx]
            if p["base_url"]:
                self.cloud_url_edit.setText(p["base_url"])
            if p["model"]:
                self.cloud_model_edit.setText(p["model"])
            self.cloud_test_label.setText(p.get("hint", ""))

    def _fill_fast_cloud_preset(self) -> None:
        """V16.0.9: Fill fast API base URL + model from the selected preset."""
        from core.llm.cloud_client import CLOUD_PRESETS

        idx = self.fast_preset_combo.currentIndex()
        if 0 <= idx < len(CLOUD_PRESETS):
            p = CLOUD_PRESETS[idx]
            if p["base_url"]:
                self.fast_api_url_edit.setText(p["base_url"])
            if p["model"]:
                self.fast_api_model_edit.setText(p["model"])
            self.fast_test_label.setText(p.get("hint", ""))

    def _test_cloud_connection(self) -> None:
        """Send a tiny request to verify the heavy cloud endpoint works.

        Runs in a background thread so the UI doesn't freeze; marshals the
        result back to the UI thread via a no-arg queued slot.

        V18.20.4.9 (W-b18 remainder): the worker's ``failed`` signal is now
        connected (``_on_cloud_test_failed``) and the ref is kept on self.
        The result slot is only reached on success — a raising test used
        to leave ``cloud_test_btn`` disabled forever with the worker
        GC'd mid-run.
        """
        base = self.cloud_url_edit.text().strip()
        key = self.cloud_key_edit.text().strip()
        model = self.cloud_model_edit.text().strip()
        self.cloud_test_btn.setEnabled(False)
        self.cloud_test_label.setText("Testing…")

        def _run():
            from core.llm.cloud_client import test_cloud_connection

            ok, msg = test_cloud_connection(base, key, model)
            self._pending_cloud_result = (ok, msg)
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self, "_set_cloud_test_result", _Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                # Fallback: set directly (best-effort at thread tail)
                self._set_cloud_test_result()

        w = SimpleWorker(_run)
        self._cloud_test_worker = w  # Python ref (GC hazard, W-b11 pattern)
        w.failed.connect(self._on_cloud_test_failed)
        w.start()

    def _test_fast_cloud_connection(self) -> None:
        """V16.0.9: Send a tiny request to verify the fast cloud endpoint works.

        V18.20.4.9 (W-b18 remainder): same shape as the heavy test above —
        ``failed`` connected + ref kept, so a raising test re-enables the
        button instead of sticking it disabled.
        """
        base = self.fast_api_url_edit.text().strip()
        key = self.fast_api_key_edit.text().strip()
        model = self.fast_api_model_edit.text().strip()
        self.fast_test_btn.setEnabled(False)
        self.fast_test_label.setText("Testing…")

        def _run():
            from core.llm.cloud_client import test_cloud_connection

            ok, msg = test_cloud_connection(base, key, model)
            self._pending_fast_cloud_result = (ok, msg)
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self, "_set_fast_cloud_test_result", _Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                self._set_fast_cloud_test_result()

        w = SimpleWorker(_run)
        self._fast_cloud_test_worker = w  # Python ref (GC hazard, W-b11 pattern)
        w.failed.connect(self._on_fast_cloud_test_failed)
        w.start()

    def _on_cloud_test_failed(self, error: str) -> None:
        """W-b18 remainder: a raising test routes through the EXISTING
        result slot (same "❌ " display + re-enable; no new strings)."""
        self._pending_cloud_result = (False, error)
        self._set_cloud_test_result()

    def _on_fast_cloud_test_failed(self, error: str) -> None:
        """W-b18 remainder: a raising test routes through the EXISTING
        result slot (same "❌ " display + re-enable; no new strings)."""
        self._pending_fast_cloud_result = (False, error)
        self._set_fast_cloud_test_result()

    @Slot()
    def _set_cloud_test_result(self) -> None:
        ok, msg = getattr(self, "_pending_cloud_result", (False, ""))
        p = theme_manager.palette
        color = p.success if ok else p.error
        self.cloud_test_label.setText(("✅ " if ok else "❌ ") + msg)
        self.cloud_test_label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 10px;"
        )
        self.cloud_test_btn.setEnabled(True)

    @Slot()
    def _set_fast_cloud_test_result(self) -> None:
        ok, msg = getattr(self, "_pending_fast_cloud_result", (False, ""))
        p = theme_manager.palette
        color = p.success if ok else p.error
        self.fast_test_label.setText(("✅ " if ok else "❌ ") + msg)
        self.fast_test_label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 10px;"
        )
        self.fast_test_btn.setEnabled(True)

    def save_to_state(self) -> None:
        arch = self.arch_combo.currentData() or "single_local"
        # V16.0.9: persist the architecture + carry it per-conversion
        self.controller.update_setting("summarisation.model_architecture", arch)
        self.state.model_architecture = arch

        if arch in ("single_local", "dual_local"):
            # Local modes — provider is ollama, llamacpp or lmstudio
            backend = self.backend_combo.currentData() or "ollama"
            self.controller.update_setting("summarisation.provider", backend)
            if backend == "lmstudio":
                self.controller.update_setting(
                    "summarisation.lmstudio_url", self.lmstudio_url_edit.text().strip()
                )
            if backend == "llamacpp":
                # V0.04: persist the llama.cpp endpoint + model (mixin) and
                # make the backend's model the request's summarisation model
                # (same pattern as the API modes writing cloud_model into
                # it) so logs, provenance and the request all name the
                # served model.
                _lc_model = self.save_llamacpp_settings()
                self.controller.update_setting(
                    "summarisation.llamacpp_context_tokens", int(self.heavy_ctx_spin.value())
                )
                self.controller.update_setting(
                    "summarisation.llamacpp_max_output_tokens", int(self.heavy_out_spin.value())
                )
                if _lc_model:
                    self.state.summarisation_model = _lc_model
                    self.controller.update_setting("summarisation.model", _lc_model)
            # Heavy/summarization model
            if not (backend == "llamacpp" and self.state.summarisation_model):
                self.state.summarisation_model = self.summ_combo.currentData() or ""
                self.controller.update_setting(
                    "summarisation.model", self.state.summarisation_model
                )
            self.state.primary_ocr_model = self.ocr_combo.currentData() or ""
            self.state.fallback_ocr_model = self.ocr_combo.currentData() or ""
            self.controller.update_setting("ocr.primary_model", self.state.primary_ocr_model)
            # Fast model (dual_local only; empty for single_local)
            if arch == "dual_local":
                self.state.fast_model = self.fast_combo.currentData() or ""
                self.controller.update_setting("summarisation.fast_model", self.state.fast_model)
            else:
                self.state.fast_model = ""
            # Local modes don't use fusion
            self.controller.update_setting("summarisation.fusion_enabled", False)
        else:
            # API modes — provider is a cloud (openai_compatible)
            self.controller.update_setting("summarisation.provider", "openai_compatible")
            # Heavy cloud API config
            self.controller.update_setting(
                "summarisation.api_base_url", self.cloud_url_edit.text().strip()
            )
            # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
            self.controller.set_secret("summarisation.api_key", self.cloud_key_edit.text().strip())
            self.controller.update_setting(
                "summarisation.cloud_model", self.cloud_model_edit.text().strip()
            )
            self.state.summarisation_model = self.cloud_model_edit.text().strip()
            # OCR uses the saved local Ollama VLM (configured in Settings → OCR)
            self.state.primary_ocr_model = self.controller.get_setting("ocr.primary_model", "")
            self.state.fallback_ocr_model = self.controller.get_setting(
                "ocr.fallback_model", self.state.primary_ocr_model
            )
            # API modes don't use a local fast model
            self.state.fast_model = ""
            # Fast API config (dual_api only)
            if arch == "dual_api":
                self.controller.update_setting(
                    "summarisation.fast_api_url", self.fast_api_url_edit.text().strip()
                )
                # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
                self.controller.set_secret(
                    "summarisation.fast_api_key", self.fast_api_key_edit.text().strip()
                )
                self.controller.update_setting(
                    "summarisation.fast_api_model", self.fast_api_model_edit.text().strip()
                )
            else:
                # single_api — clear fast API fields so they don't leak
                self.controller.update_setting("summarisation.fast_api_url", "")
                self.controller.update_setting("summarisation.fast_api_model", "")
            self.controller.update_setting("summarisation.fusion_enabled", False)

        # Common parameters
        self.state.max_workers = self.workers_spin.value()
        self.state.temperature = self.temp_spin.value()
        self.state.max_context_tokens = self.heavy_ctx_spin.value()
        # V0.04: the output budget is now first-class in the wizard — the
        # heavy_out_spin (256–65536) feeds the same request field Step 7b's
        # out_spin writes, so both surfaces stay in sync via settings.
        self.state.max_output_tokens = self.heavy_out_spin.value()
        self.controller.update_setting("summarisation.max_workers", self.workers_spin.value())
        self.controller.update_setting("summarisation.temperature", self.temp_spin.value())
        self.controller.update_setting(
            "summarisation.max_context_tokens", self.heavy_ctx_spin.value()
        )
        self.controller.update_setting(
            "summarisation.max_output_tokens", self.heavy_out_spin.value()
        )
        self.controller.update_setting(
            "summarisation.fast_model_temperature", self.fast_temp_spin.value()
        )
        self.controller.update_setting(
            "summarisation.fast_model_context", self.fast_ctx_spin.value()
        )

    # V7.5.1: temperature=0 warning — many models produce degenerate output
    # at t=0.  The warning is live (updates as the user drags the spin box).
    def _check_temp_warning(self, value: float) -> None:
        p = theme_manager.palette
        # V10.1.10: warning for temperatures below 0.4 (most local models need higher)
        if value < 0.4:
            self.temp_warn_label.setText(
                "⚠️ Low temp — many local models (Qwythos, Qwen, Gemma) produce empty/degenerate "
                "output below 0.4. Cloud APIs tolerate lower temps. Check your model's spec."
            )
            self.temp_warn_label.setStyleSheet(
                f"color: {p.warning}; background: transparent; font-size: 10px;"
            )
        elif value < 0.1:
            self.temp_warn_label.setText("⚠️ t=0 can cause empty/repetitive output — use ≥ 0.1")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.warning}; background: transparent; font-size: 10px;"
            )
        elif value < 0.2:
            self.temp_warn_label.setText("low — ok for deterministic models / cloud APIs")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 10px;"
            )
        else:
            self.temp_warn_label.setText("")

    def _check_workers_warning(self, value: int) -> None:
        """V10.1.10: Warn when user selects >1 workers (GPU heat risk).

        LLM inference is a memory-bandwidth-bound workload.  Multiple
        workers multiply VRAM bandwidth load, which directly increases
        VRAM temperature.  On cards with marginal VRAM cooling (like the
        Zotac RTX 3060 Twin Edge), 2+ workers can cause visual artifacts
        (red dots/lines on the monitor) and permanent VRAM damage.
        """
        p = theme_manager.palette
        if value > 1:
            self.workers_warn_label.setText(
                f"⚠️ {value} workers = {value}× VRAM heat. "
                f"LLM inference is memory-bandwidth-bound — multiple workers "
                f"multiply VRAM thermal stress. Only use >1 on cards with "
                f"good VRAM cooling (not Zotac Twin Edge). Cloud APIs ignore this."
            )
            self.workers_warn_label.setStyleSheet(
                f"color: {p.warning}; background: transparent; font-size: 10px;"
            )
        else:
            self.workers_warn_label.setText("✓ safe")
            self.workers_warn_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 10px;"
            )

    # V10.1.5: Thermal lock — detect the GPU and lock max_workers for
    # emergency-mode cards (Zotac RTX 3060 Twin Edge etc.).  The user
    # cannot override this — it's a hardware safety constraint.
    def _check_thermal_lock(self) -> None:
        """Lock max_workers to 1 if an emergency-mode GPU is detected."""
        try:
            from core.system.hardware_monitor import detect_gpu_profile_from_system

            gpu_name, profile = detect_gpu_profile_from_system()
            if gpu_name and getattr(profile, "emergency_mode", False):
                # Lock the spinbox
                self.workers_spin.setEnabled(False)
                self.workers_spin.setValue(1)
                self.workers_spin.setToolTip(
                    f"🔒 Locked to 1 worker for VRAM protection.\n\n"
                    f"GPU: {gpu_name}\n"
                    f"Profile: {profile.name}\n\n"
                    f"This card has known VRAM thermal issues. LLM inference "
                    f"is a memory-bandwidth-bound workload — multiple workers "
                    f"would multiply VRAM heat and risk permanent damage. "
                    f"The converter will enforce this cap regardless of this "
                    f"setting, but the spinbox is disabled to make the "
                    f"constraint clear. (Cloud API modes are unaffected.)"
                )
                # Add a lock label next to the spinbox (if not already there)
                if self._workers_lock_label is None:
                    self._workers_lock_label = QLabel("🔒 1 (VRAM protection)")
                    self._workers_lock_label.setStyleSheet(
                        "color: #B0594F; font-size: 10px; font-weight: bold;"
                    )
                    self._workers_lock_label.setToolTip(
                        "Max workers locked for VRAM thermal protection."
                    )
            else:
                # No emergency card — unlock
                self.workers_spin.setEnabled(True)
                if self._workers_lock_label:
                    self._workers_lock_label.setText("")
        except Exception:
            # If detection fails, don't lock — let the user choose
            pass
