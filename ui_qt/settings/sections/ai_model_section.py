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
    QPushButton,
    QSlider,  # workers slider
    QWidget,
)

from controller import Controller
from core.system.timeouts import UI_PROBE_TIMEOUT_S
from ui_qt.components.icons import icon
from ui_qt.settings.widgets import labeled_line, make_form

from .helpers import _populate_models, _refresh_models_async


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

        # ── model pickers ───────────────────────────────────────────────
        # V0.6.14 (single-model order): ONE model picker. The fast-model,
        # heavy-model, fast-API, and simplification-model rows are RETIRED
        # — one model does every LLM generation task.
        self.summary_combo = QComboBox()
        f.addRow("Summarisation model", self.summary_combo)

        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)

        # ── workers ─────────────────────────────────────────────────────
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
        """W-b11: worker finished — populate the model combo (MAIN thread)."""
        _populate_models(
            self.summary_combo,
            models,
            current=self.controller.get_setting("summarisation.model", ""),
        )

    # ── save / reload ────────────────────────────────────────────────────
    def save(self) -> None:
        c = self.controller
        c.update_setting("ai.backend", self.backend_combo.currentText())
        c.update_setting("ai.custom_backend_url", self.custom_url.text().strip())
        c.update_setting("summarisation.model", self.summary_combo.currentData() or "")
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
