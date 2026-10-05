"""V0.04: the llama.cpp server configuration mixin (wizard Step 5).

Why a mixin in components/ (not inside ``wizard_steps/step5_models.py``):
the O-b1 wizard split enforces ``wizard_steps/`` = exactly one module per
step (tests/test_v182046 pins the file set) and a per-step line budget
(< 1000 lines). The llama.cpp backend surface — endpoint box, two-stage
Test-connection probe, model discovery, save — is ~200 lines of backend-
specific UI that would push Step5Models past its budget. It lives here as
``LlamaCppConfigMixin`` and Step5Models simply inherits it.

All endpoint state reads/writes the ``summarisation.llamacpp_*`` settings
block (single source of truth — the provider factory reads the same keys),
so the wizard, the Settings dialog and the provider can never disagree.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.system.timeouts import CLI_POLL_TIMEOUT_S
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.theme import theme_manager

LLAMACPP_DEFAULT_URL = "http://127.0.0.1:8080/v1"
LLAMACPP_DEFAULT_MODEL = "Ternary-Bonsai-2-27B-Instruct-Vision"


def build_llamacpp_endpoint_options(
    primary_url: str, primary_key: str, endpoints: list | None
) -> list[dict]:
    """Build the endpoint-dropdown options (Primary + the configured list).

    V0.4.31 (B1 per-conversion dropdown): the dropdown lists the Primary
    endpoint (the current ``llamacpp_base_url``/``llamacpp_api_key``) + each
    entry from the ``llamacpp_endpoints`` setting (a list of
    ``{base_url, api_key, label}``). Picking one populates the URL/key
    fields so ``save_llamacpp_settings`` writes the selected endpoint;
    ``create_provider`` then detects the served model (V0.4.30).

    Pure (no Qt, no settings I/O) — testable without a QApplication.
    """
    opts: list[dict] = [{"label": "Primary", "base_url": primary_url, "api_key": primary_key}]
    for ep in endpoints or []:
        _url = (ep.get("base_url") or "").strip() if isinstance(ep, dict) else ""
        if not _url:
            continue  # skip empty/malformed endpoints
        opts.append(
            {
                "label": ep.get("label") or _url,
                "base_url": _url,
                "api_key": ep.get("api_key") or "local",
            }
        )
    return opts


class LlamaCppConfigMixin:
    """Builds + owns the llama.cpp endpoint box; Step5Models mixes it in."""

    # ── construction (called from Step5Models._build) ────────────────────

    def build_llamacpp_box(self) -> QWidget:
        """The llama.cpp server config box (URL / API key / model / test)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        # V0.4.20: 5 → 8 — the three label+field rows were visually fused
        # (user-reported "cramped"); match the wizard's other row spacing.
        lay.setSpacing(8)

        # V0.4.31 (B1 per-conversion dropdown): quick-select among the
        # configured llama.cpp endpoints (Primary + llamacpp_endpoints).
        # Picking one populates the URL/key fields below; create_provider
        # then detects the served model (V0.4.30).
        ep_row = QHBoxLayout()
        ep_row.setSpacing(8)
        ep_row.addWidget(QLabel("Endpoint:"))
        self.llamacpp_endpoint_combo = QComboBox()
        self.llamacpp_endpoint_combo.setMinimumWidth(260)
        _primary_url = self.controller.get_setting(
            "summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_URL
        )
        _primary_key = self.controller.get_secret("summarisation.llamacpp_api_key", "local")
        _endpoints = self.controller.get_setting("summarisation.llamacpp_endpoints", [])
        self._llamacpp_endpoint_opts = build_llamacpp_endpoint_options(
            _primary_url, _primary_key, _endpoints
        )
        _active_idx = 0
        for _i, _opt in enumerate(self._llamacpp_endpoint_opts):
            self.llamacpp_endpoint_combo.addItem(f"{_opt['label']}  ({_opt['base_url']})", _i)
            if _opt["base_url"] == _primary_url:
                _active_idx = _i
        self.llamacpp_endpoint_combo.setCurrentIndex(_active_idx)
        self.llamacpp_endpoint_combo.currentIndexChanged.connect(
            self._on_llamacpp_endpoint_selected
        )
        ep_row.addWidget(self.llamacpp_endpoint_combo, 1)
        lay.addLayout(ep_row)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.llamacpp_url_edit = QLineEdit(
            self.controller.get_setting("summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_URL)
        )
        self.llamacpp_url_edit.setPlaceholderText(LLAMACPP_DEFAULT_URL)
        # V0.4.20: never let the URL field get crushed below a usable width
        # in narrow windows — the endpoint must stay readable.
        self.llamacpp_url_edit.setMinimumWidth(260)
        url_row.addWidget(QLabel("llama.cpp URL:"))
        url_row.addWidget(self.llamacpp_url_edit, 1)
        lay.addLayout(url_row)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self.llamacpp_key_edit = QLineEdit(
            # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
            self.controller.get_secret("summarisation.llamacpp_api_key", "local")
        )
        self.llamacpp_key_edit.setEchoMode(QLineEdit.Password)
        self.llamacpp_key_edit.setPlaceholderText(
            "local (ignored unless llama-server uses --api-key)"
        )
        key_row.addWidget(QLabel("API key:"))
        key_row.addWidget(self.llamacpp_key_edit, 1)
        lay.addLayout(key_row)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.llamacpp_model_edit = QLineEdit(
            self.controller.get_setting("summarisation.llamacpp_model", LLAMACPP_DEFAULT_MODEL)
        )
        self.llamacpp_model_edit.setPlaceholderText(LLAMACPP_DEFAULT_MODEL)
        self.llamacpp_model_edit.setMinimumWidth(260)  # V0.4.20: keep the model name readable
        model_row.addWidget(QLabel("Model name:"))
        model_row.addWidget(self.llamacpp_model_edit, 1)
        lay.addLayout(model_row)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.llamacpp_test_btn = QPushButton("🔌  Test connection")
        self.llamacpp_test_btn.setObjectName("Secondary")
        self.llamacpp_test_btn.setCursor(Qt.PointingHandCursor)
        self.llamacpp_test_btn.setToolTip(
            "Probe the llama.cpp server: (1) GET /v1/models — is llama-server "
            "alive at this URL? (2) a 1-token chat completion — is the model "
            "loaded and generating?"
        )
        self.llamacpp_test_btn.clicked.connect(self._test_llamacpp_connection)
        test_row.addWidget(self.llamacpp_test_btn)
        self.llamacpp_test_label = QLabel("")
        self.llamacpp_test_label.setObjectName("Caption")
        self.llamacpp_test_label.setWordWrap(True)
        test_row.addWidget(self.llamacpp_test_label, 1)
        lay.addLayout(test_row)

        hint = QLabel(
            "Start the server with a 65k window, e.g.:\n"
            "  llama-server -m Ternary-Bonsai-2-27B-Instruct-Vision.gguf -c 65536 --port 8080"
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 10px; padding: 2px 0;")
        lay.addWidget(hint)
        return w

    # ── visibility (called from Step5Models._on_arch_change) ─────────────

    def _on_llamacpp_endpoint_selected(self, idx: int) -> None:
        """Populate the URL/key fields from the selected endpoint (B1)."""
        opts = getattr(self, "_llamacpp_endpoint_opts", None)
        if not opts or idx < 0 or idx >= len(opts):
            return
        _opt = opts[idx]
        self.llamacpp_url_edit.setText(_opt["base_url"])
        self.llamacpp_key_edit.setText(_opt["api_key"])

    def llamacpp_set_visible(self, is_local: bool, backend: str) -> None:
        self.llamacpp_widget.setVisible(is_local and backend == "llamacpp")

    # ── model discovery (the SimpleWorker fn — Settings only, no widgets) ─

    def llamacpp_fetch_models(self) -> list[str]:
        """Worker fn: list the server's loaded models via GET /v1/models.

        Reads the llamacpp_* settings directly (thread-safe Settings
        singleton) — deliberately NOT the wizard's line edits, so this is
        safe to run on the worker thread. Falls back to the configured
        model name when the server lists nothing (down / older build).
        """
        try:
            from core.llm.llamacpp_provider import list_llamacpp_models

            base = self.controller.get_setting(
                "summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_URL
            )
            key = self.controller.get_secret("summarisation.llamacpp_api_key", "local")
            models = list_llamacpp_models(base, key, timeout=CLI_POLL_TIMEOUT_S)
            if models:
                return models
            configured = self.controller.get_setting("summarisation.llamacpp_model", "")
            return [configured] if configured else []
        except Exception:
            return []

    # ── save (called from Step5Models.save_to_state) ─────────────────────

    def save_llamacpp_settings(self) -> str:
        """Persist the endpoint + model; returns the model name (may be '')."""
        url = self.llamacpp_url_edit.text().strip() or LLAMACPP_DEFAULT_URL
        key = self.llamacpp_key_edit.text().strip() or "local"
        model = self.llamacpp_model_edit.text().strip()
        self.controller.update_setting("summarisation.llamacpp_base_url", url)
        # V0.16 (Phase 3 / 3.2): keyring-backed write (was plaintext).
        self.controller.set_secret("summarisation.llamacpp_api_key", key)
        if model:
            self.controller.update_setting("summarisation.llamacpp_model", model)
        return model

    # ── backend switch — per-backend token-budget defaults ───────────────

    def _on_backend_change(self) -> None:
        """V0.04: when the local backend changes, align the ctx/output
        spinboxes with the backend's model defaults.

        GENERAL RULE: switching backends switches model CAPABILITIES — the
        token budget fields must follow, or the wizard quietly carries the
        previous backend's numbers into calls the new model can't honour
        (a 16000-output request against a 12288-cap model; a 32k ctx
        against a 65k-window server).

        Only the "untouched" values are aligned: if the user has already
        customised a field for this visit, their number survives.
        """
        try:
            backend = self.backend_combo.currentData() or "ollama"
            if backend == "llamacpp":
                _lc_ctx = int(
                    self.controller.get_setting("summarisation.llamacpp_context_tokens", 65536)
                    or 65536
                )
                _lc_out = int(
                    self.controller.get_setting("summarisation.llamacpp_max_output_tokens", 12288)
                    or 12288
                )
                if self.heavy_ctx_spin.value() == 32768:
                    self.heavy_ctx_spin.setValue(min(max(_lc_ctx, 1024), 262144))
                if self.heavy_out_spin.value() in (8192, 16000):
                    self.heavy_out_spin.setValue(min(max(_lc_out, 256), 65536))
                # Re-list models from the llama.cpp server.
                self._refresh_models()
            else:
                # Switching back to Ollama/LM Studio: restore the persisted
                # summarisation token settings when the spins still show
                # the llama.cpp defaults.
                _ctx = int(
                    self.controller.get_setting("summarisation.max_context_tokens", 32768) or 32768
                )
                _out = int(
                    self.controller.get_setting("summarisation.max_output_tokens", 16000) or 16000
                )
                if self.heavy_ctx_spin.value() == 65536 and _ctx != 65536:
                    self.heavy_ctx_spin.setValue(min(max(_ctx, 1024), 262144))
                if self.heavy_out_spin.value() == 12288 and _out != 12288:
                    self.heavy_out_spin.setValue(min(max(_out, 256), 65536))
                self._refresh_models()
        except Exception:
            pass  # UI sugar — never raise from a combo signal

    # ── the two-stage connection probe (W-b11/W-b18 worker pattern) ──────

    def _test_llamacpp_connection(self) -> None:
        """Probe the server on a background thread; marshal the result back
        via a queued slot (same shape as _test_cloud_connection — the
        worker's ``failed`` signal is connected and the ref kept on self so
        a raising probe re-enables the button instead of sticking it)."""
        base = self.llamacpp_url_edit.text().strip() or LLAMACPP_DEFAULT_URL
        key = self.llamacpp_key_edit.text().strip() or "local"
        model = self.llamacpp_model_edit.text().strip()
        self.llamacpp_test_btn.setEnabled(False)
        self.llamacpp_test_label.setText("Testing…")

        def _run():
            from core.llm.llamacpp_provider import test_llamacpp_connection

            ok, msg = test_llamacpp_connection(base, key, model)
            self._pending_llamacpp_result = (ok, msg)
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self,
                    "_set_llamacpp_test_result",
                    _Qt.ConnectionType.QueuedConnection,
                )
            except Exception:
                self._set_llamacpp_test_result()

        w = SimpleWorker(_run)
        self._llamacpp_test_worker = w  # Python ref (GC hazard, W-b11 pattern)
        w.failed.connect(self._on_llamacpp_test_failed)
        w.start()

    def _on_llamacpp_test_failed(self, error: str) -> None:
        """W-b18 pattern: a raising probe routes through the result slot."""
        self._pending_llamacpp_result = (False, error)
        self._set_llamacpp_test_result()

    @Slot()
    def _set_llamacpp_test_result(self) -> None:
        ok, msg = getattr(self, "_pending_llamacpp_result", (False, ""))
        p = theme_manager.palette
        color = p.success if ok else p.error
        self.llamacpp_test_label.setText(("✅ " if ok else "❌ ") + msg)
        self.llamacpp_test_label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 10px;"
        )
        self.llamacpp_test_btn.setEnabled(True)
