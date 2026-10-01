"""V0.4.19 — AiLocalModelSection (the local-model settings giant).

The 488-line local-backend / model-architecture / model-picker section
moved VERBATIM from ``ui_qt/settings/sections.py`` during the V0.4.19
de-monolithization — body byte-identical; only this docstring and the
re-homed imports (the async model helpers via ``.helpers``) are new.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,  # V18.20.3.12 (F821): used at :353 (fast_temp_slider) but was never imported
    QWidget,
)

from controller import Controller
from core.system.timeouts import UI_PROBE_TIMEOUT_S
from ui_qt.components.icons import icon
from ui_qt.settings.widgets import labeled_line, make_form

from .helpers import _populate_models, _populate_models_async, _refresh_models_async


class AiLocalModelSection(QGroupBox):
    """Local model backend (Ollama / llama.cpp / LM Studio / custom) + summarisation models + workers.

    The backend picker changes where the model list is fetched from:
      - Ollama    → http://localhost:11434/api/tags
      - llama.cpp → http://127.0.0.1:8080/v1/models (llama-server, V0.04)
      - LM Studio → http://localhost:1234/v1/models
      - Custom    → user-supplied URL (expects Ollama-style /api/tags)
    """

    BACKENDS = ["Ollama", "llama.cpp server", "LM Studio", "Custom"]

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
        # V0.04: an installation whose summarisation provider is llamacpp
        # (the V0.04 default / migration) shows the llama.cpp backend here
        # even when the legacy ai.backend key still says "Ollama".
        if saved_backend not in self.BACKENDS:
            if controller.get_setting("summarisation.provider", "ollama") == "llamacpp":
                saved_backend = "llama.cpp server"
            else:
                saved_backend = "Ollama"
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
        _saved_arch = (
            controller.get_setting("summarisation.model_architecture", "single_local")
            or "single_local"
        )
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
        _populate_models_async(
            self.fast_model_combo,
            controller,
            current=controller.get_setting("summarisation.fast_model", ""),
        )
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
        self.fast_refresh_btn.clicked.connect(
            lambda: _populate_models_async(
                self.fast_model_combo, controller, current=self.fast_model_combo.currentData()
            )
        )
        fast_model_row.addWidget(self.fast_refresh_btn)
        self.fast_row_widget = fast_row_widget
        f.addRow("Fast model (dual-local)", self.fast_row_widget)

        # V17.0.0: Fast model temperature
        self.fast_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.fast_temp_slider.setRange(0, 200)
        self.fast_temp_slider.setValue(
            int(controller.get_setting("summarisation.fast_model_temperature", 0.1) * 100)
        )
        self.fast_temp_slider.setToolTip(
            "Sampling temperature for the fast model.\n\n"
            "LFM2.5-2.6B recommends 0.1.\n"
            "Qwen models recommend 0.6-0.8.\n"
            "Gemma models recommend 1.0."
        )
        self.fast_temp_entry = QLineEdit(f"{self.fast_temp_slider.value() / 100:.2f}")
        self.fast_temp_entry.setMaximumWidth(56)
        self.fast_temp_entry.setAlignment(Qt.AlignCenter)
        self.fast_temp_slider.valueChanged.connect(
            lambda v: self.fast_temp_entry.setText(f"{v / 100:.2f}")
        )
        fast_temp_row = QHBoxLayout()
        fast_temp_row.setSpacing(8)
        fast_temp_row.addWidget(self.fast_temp_slider, 1)
        fast_temp_row.addWidget(self.fast_temp_entry)
        f.addRow("Fast model temperature", fast_temp_row)

        # V17.0.0: Fast model context size
        self.fast_ctx_edit = QLineEdit(
            str(controller.get_setting("summarisation.fast_model_context", 131072))
        )
        self.fast_ctx_edit.setToolTip(
            "Context window for the fast model. LFM2.5 supports up to 131072 (128K)."
        )
        f.addRow("Fast model context size", self.fast_ctx_edit)

        # V16.0.9: Fast-API fields (visible only in dual_api mode — the
        # cheap cloud workhorse).
        self.fast_api_url_edit = QLineEdit(controller.get_setting("summarisation.fast_api_url", ""))
        self.fast_api_url_edit.setPlaceholderText("https://openrouter.ai/api/v1")
        self.fast_api_url_edit.setToolTip(
            "OpenAI-compatible API URL for the fast model in Dual-API mode."
        )
        f.addRow("Fast API URL (dual-api)", self.fast_api_url_edit)

        self.fast_api_key_edit = QLineEdit(controller.get_secret("summarisation.fast_api_key", ""))
        self.fast_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.fast_api_key_edit.setPlaceholderText("sk-...")
        self.fast_api_key_edit.setToolTip("API key for the fast model endpoint in Dual-API mode.")
        f.addRow("Fast API key (dual-api)", self.fast_api_key_edit)
        # V0.16 (Phase 3 / 3.4): keychain storage indicator
        from core.system.secrets import storage_status_label

        f.addRow("", QLabel(storage_status_label()))

        self.fast_api_model_edit = QLineEdit(
            controller.get_setting("summarisation.fast_api_model", "")
        )
        self.fast_api_model_edit.setPlaceholderText("google/gemini-2.5-flash-preview:free")
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
        self.arch_desc_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px 0 2px 0;")
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
        if backend == "llama.cpp server":
            # V0.04: the llama.cpp endpoint lives in the llamacpp_* settings
            # block (shared with the wizard + provider — single source).
            _u = self.controller.get_setting(
                "summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1"
            )
            return _u[:-3] if _u.endswith("/v1") else _u
        if backend == "LM Studio":
            return "http://localhost:1234"
        return self.custom_url.text().strip() or "http://localhost:11434"

    def _fetch_models(self) -> list:
        """Fetch models from the selected backend. Falls back to Ollama.

        V18.20.4.5 (W-b11): kept for compatibility — reads the backend URL
        from the combos, so only call it on the MAIN thread. The async
        refresh snapshots the URL first and runs the widget-free
        ``_fetch_models_from(url)`` on the worker instead.

        V0.04: the llama.cpp backend dispatches to _fetch_llamacpp_models.
        """
        if self.backend_combo.currentText() == "llama.cpp server":
            return self._fetch_llamacpp_models()
        return self._fetch_models_from(self._backend_url())

    def _fetch_llamacpp_models(self) -> list:
        """V0.04: list models from the llama.cpp server (worker-safe).

        Reads the llamacpp_* settings directly (thread-safe Settings
        singleton) — NOT widgets — so it is safe as the async worker fn.
        Falls back to the configured model name when the server lists
        nothing (down / older build without /v1/models).
        """
        try:
            from core.llm.llamacpp_provider import list_llamacpp_models

            base = self.controller.get_setting(
                "summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1"
            )
            key = self.controller.get_secret("summarisation.llamacpp_api_key", "local")
            models = list_llamacpp_models(base, key, timeout=UI_PROBE_TIMEOUT_S)
            if models:
                return models
            configured = self.controller.get_setting("summarisation.llamacpp_model", "")
            return [configured] if configured else []
        except Exception:
            return []

    def _fetch_models_from(self, url: str) -> list:
        """Widget-free fetch from ``url`` (safe to run on a worker thread).

        V0.6.8 (audit B5): the self-built no-proxy session is replaced by
        the shared transports — ``list_llamacpp_models`` for the OpenAI-style
        LM Studio ``/v1/models`` probe and ``list_ollama_models`` for
        ``/api/tags`` (both proxy-proof). LM Studio 200-with-empty-data now
        falls through to the ``/api/tags`` probe (same observable [] result —
        LM Studio does not serve ``/api/tags``).
        """
        base = url.rstrip("/")
        # LM Studio uses OpenAI-style /v1/models; Ollama uses /api/tags.
        # V0.6.8 (review-loop follow-up): both shared helpers never raise
        # for the expected failure families, but a 200 response with a
        # malformed body (top-level JSON array, entry missing "name"/"id")
        # raises AttributeError/KeyError out of them — the old body's
        # never-raise contract (worker-safe, returns []) is restored with
        # a narrow local catch.
        try:
            if "localhost:1234" in url or "lmstudio" in url.lower():
                from core.llm.llamacpp_provider import list_llamacpp_models

                models = list_llamacpp_models(f"{base}/v1", "local", timeout=UI_PROBE_TIMEOUT_S)
                if models:
                    return models
            # Ollama-style
            from utils.network import list_ollama_models

            return list_ollama_models(base, timeout=UI_PROBE_TIMEOUT_S)
        except (AttributeError, KeyError, TypeError):
            return []

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — this ran a
        5s-timeout HTTP call ON the UI thread (constructor, backend
        change, reload, Refresh click) — opening Settings froze the app
        for up to 5s when the backend was down. The backend URL is
        snapshotted on the MAIN thread (combo read) and the widget-free
        ``_fetch_models_from(url)`` runs on the worker; populate happens
        on the main thread in _on_models_loaded.

        V0.04: the llama.cpp backend dispatches to _fetch_llamacpp_models
        (Settings-only reads — worker-safe) instead of the URL-based fetch.
        """
        if self.backend_combo.currentText() == "llama.cpp server":
            fetch = self._fetch_llamacpp_models  # Settings-only, worker-safe
            _refresh_models_async(self, fetch, self._on_models_loaded, self.refresh_btn)
            return
        url = self._backend_url()  # snapshot on the main thread
        fetch = self._fetch_models_from  # bound method — worker-safe body
        _refresh_models_async(self, lambda: fetch(url), self._on_models_loaded, self.refresh_btn)

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate the four combos (MAIN thread)."""
        _populate_models(
            self.summary_combo,
            models,
            current=self.controller.get_setting("summarisation.model", ""),
        )
        # V18.20.4.3 (P2 / W-b7): refresh the VISIBLE fast-model combo —
        # this used to populate the orphaned ``fast_combo``, so a global
        # model refresh never actually updated the fast-model picker.
        _populate_models(
            self.fast_model_combo,
            models,
            current=self.controller.get_setting("summarisation.fast_model", ""),
        )
        _populate_models(
            self.heavy_combo,
            models,
            current=self.controller.get_setting("summarisation.heavy_model", ""),
            allow_empty=True,
        )
        # V3.5.0: Simplification model (allow empty = use same as summarisation)
        _populate_models(
            self.simplification_combo,
            models,
            current=self.controller.get_setting("summarisation.simplification_model", ""),
            allow_empty=True,
        )

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
        # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
        c.set_secret("summarisation.fast_api_key", self.fast_api_key_edit.text().strip())
        c.update_setting("summarisation.fast_api_model", self.fast_api_model_edit.text().strip())
        c.update_setting(
            "summarisation.fast_model_temperature", self.fast_temp_slider.value() / 100
        )
        try:
            c.update_setting(
                "summarisation.fast_model_context", int(self.fast_ctx_edit.text().strip())
            )
        except (ValueError, TypeError):
            pass
        c.update_setting(
            "summarisation.simplification_model", self.simplification_combo.currentData() or ""
        )
        c.update_setting("summarisation.max_workers", self.workers_slider.value())
        # when using a local backend, set the provider so the pipeline knows
        # to use local models (not a cloud API). V0.04: the llama.cpp
        # backend maps to its own provider — the old unconditional
        # "ollama" write silently clobbered it on every Settings save.
        if self.backend_combo.currentText() == "llama.cpp server":
            c.update_setting("summarisation.provider", "llamacpp")
        else:
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
        _populate_models_async(
            self.fast_model_combo, c, current=c.get_setting("summarisation.fast_model", "")
        )
        # V16.0.9: Fast-API fields reload
        self.fast_api_url_edit.setText(c.get_setting("summarisation.fast_api_url", ""))
        self.fast_api_key_edit.setText(c.get_secret("summarisation.fast_api_key", ""))
        self.fast_api_model_edit.setText(c.get_setting("summarisation.fast_api_model", ""))
        self.fast_temp_slider.setValue(
            int(c.get_setting("summarisation.fast_model_temperature", 0.1) * 100)
        )
        self.fast_temp_entry.setText(f"{self.fast_temp_slider.value() / 100:.2f}")
        self.fast_ctx_edit.setText(str(c.get_setting("summarisation.fast_model_context", 131072)))
        self._on_arch_change()
