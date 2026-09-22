"""V0.4.19 — AiApiSection + the legacy section aliases.

``AiApiSection`` (cloud / API provider selection with multiple saved
custom providers) and the legacy ``AiModelsSection`` / ``AiProviderSection``
aliases moved VERBATIM from ``ui_qt/settings/sections.py`` during the
V0.4.19 de-monolithization — bodies byte-identical; only this docstring
and the re-homed imports are new.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QWidget

from controller import Controller
from ui_qt.settings.widgets import labeled_line, make_form
from utils.provider_catalog import (  # V0.16 (Phase 3 / 3.2): Qt-free home
    load_custom_providers as _load_custom_providers,
)
from utils.provider_catalog import (
    save_custom_providers as _save_custom_providers,
)

from .ai_model_section import AiLocalModelSection

# ── saved custom API providers ─────────────────────────────────────────────
# V0.16 (Phase 3 / 3.2): the catalog load/save helpers moved to
# ui_qt/settings/provider_catalog.py (imported at the top) — a Qt-free
# module so the credential logic is testable in CI without PySide6 GUI libs.


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
            controller.get_secret("summarisation.api_key", ""),
            placeholder="sk-…  /  your API key",
            password=True,
        )
        self.model_edit = labeled_line(
            controller.get_setting(
                "summarisation.cloud_model", "google/gemini-2.5-flash-preview:free"
            ),
            placeholder="e.g. google/gemini-2.5-flash-preview:free",
        )
        f.addRow("Name", self.name_edit)
        f.addRow("Base URL", self.base_url_edit)
        f.addRow("API key", self.api_key_edit)
        # V0.16 (Phase 3 / 3.4): keychain storage indicator
        from core.system.secrets import storage_status_label

        f.addRow("", QLabel(storage_status_label()))
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
        providers.append(
            {
                "name": self.name_edit.text().strip() or f"Provider {len(providers) + 1}",
                "base_url": self.base_url_edit.text().strip(),
                "api_key": self.api_key_edit.text().strip(),
                "model": self.model_edit.text().strip(),
            }
        )
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
        # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
        c.set_secret("summarisation.api_key", api_key)
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
                # V0.16 (Phase 3 / 3.2): keyring-backed write (completes the V18.1 TODO)
                c.set_secret("summarisation.claude_api_key", api_key)
                c.update_setting("summarisation.claude_model", self.model_edit.text().strip())
            else:
                c.update_setting("summarisation.provider", "openai_compatible")
        # else: don't touch provider — AiLocalModelSection already set it to "ollama"
        # if currently editing a custom provider, persist its fields
        if t == "Custom (named)":
            row = self.providers_list.currentRow()
            providers = _load_custom_providers(c)
            if 0 <= row < len(providers):
                providers[row].update(
                    {
                        "name": self.name_edit.text().strip() or f"Provider {row + 1}",
                        "base_url": self.base_url_edit.text().strip(),
                        "api_key": self.api_key_edit.text().strip(),
                        "model": self.model_edit.text().strip(),
                    }
                )
                _save_custom_providers(c, providers)

    def reload(self) -> None:
        c = self.controller
        idx = self.type_combo.findText(c.get_setting("ai.api_type", "OpenAI-Compatible"))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.base_url_edit.setText(c.get_setting("summarisation.api_base_url", ""))
        self.api_key_edit.setText(c.get_secret("summarisation.api_key", ""))
        self.model_edit.setText(c.get_setting("summarisation.cloud_model", ""))
        self._populate_providers_list()
        self._on_type_change()


# Legacy aliases (kept so the dialog's _HEAD_GROUPS import doesn't break
# during the transition — the new dialog uses AiLocalModelSection/AiApiSection).
AiModelsSection = AiLocalModelSection
AiProviderSection = AiApiSection
