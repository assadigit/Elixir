"""Step 6: Translation Settings — Step6Translation.

V0.7.4 (wizard rework ⑥) — the Step-6 rebuild:

**6a (D15)** — skipability is VISIBLE (audit §W10): the master
"Translate outputs" switch carries the "optional — runs after
conversion" caption.  "What to translate" becomes a radio —
"The outputs I selected in step 4" (the DEFAULT; at Start the wizard
derives ``translation.outputs`` through
``core.outputs.registry.selected_translation_outputs`` — the backend
needs no change, translation is a settings-driven post-conversion
phase) vs "Let me choose" (the manual checkbox list, the pre-rework
surface).

**6a (D14 reuse)** — the harakat/judge combos open on the last-used
picks (the V0.7.3 ``_seed_model_combo`` pattern) and list the server's
models OFF the UI thread (SimpleWorker, the W-b11 pattern — the old
build called ``controller.list_ollama_models()`` synchronously, so a
hung server froze the wizard open for the full 5s timeout).  The
listing's empty case is a muted hint label, never a modal.

**6b (D16)** — the harakat picker's copy tells the truth: the
``.harakat.md`` file is a MANUAL-REVIEW copy; the TTS / Podcast-Maker
wiring is backlog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import icon
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings.translation_page import _TRANSLATABLE_OUTPUTS
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 6: Translation Settings
# ════════════════════════════════════════════════════════════════════════════


class Step6Translation(WizardStep):
    """Translation settings: two selection modes, live model pickers."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    STEP_HEADER = (6, "Translation", "Optionally translate the outputs — skip this step freely.")

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ── The master switch + the visible skip affordance (6a) ────────
        # V0.7.4 (rework ⑥, §W10): the audit's finding — the ONLY
        # skip affordance was the unchecked checkbox; no "optional" copy.
        # The caption now says it in plain words, right under the switch.
        self.enable_cb = QCheckBox("Translate outputs")
        self.enable_cb.setChecked(self.state.translation_enabled)
        self.enable_cb.stateChanged.connect(self._on_enable_changed)
        self.enable_cb.setToolTip(
            "Off by default — the conversion finishes normally and no\n"
            "translation runs. Everything below only matters when this is on."
        )
        lay.addWidget(self.enable_cb)
        self.optional_caption = QLabel("Optional — runs after conversion.")
        self.optional_caption.setStyleSheet(
            f"color: {theme_manager.palette.text_secondary}; font-size: 11px;"
            " padding: 2px 0; background: transparent;"
        )
        lay.addWidget(self.optional_caption)

        # Settings host: the frameless scroll area (the Step4/Step5/Step7b
        # pattern) — mode B's checkbox list exceeds the 740×540 viewport.
        self.settings_widget = QScrollArea()
        self.settings_widget.setWidgetResizable(True)
        self.settings_widget.setFrameShape(QFrame.NoFrame)
        settings_host = QWidget()
        settings_lay = QVBoxLayout(settings_host)
        settings_lay.setContentsMargins(0, 8, 0, 0)
        settings_lay.setSpacing(8)

        # ── Target language (the main-flow choice) ──────────────────────
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        lang_row.addWidget(QLabel("Target language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Farsi / Persian (fa)", "fa")
        self.lang_combo.addItem("English (en)", "en")
        idx = self.lang_combo.findData(self.state.translation_target_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.setToolTip("The language the selected outputs are translated into.")
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        settings_lay.addLayout(lang_row)

        # ── What to translate: the two modes (D15) ─────────────────────
        mode_box = QGroupBox("What to translate")
        mode_lay = QVBoxLayout(mode_box)
        mode_lay.setContentsMargins(10, 10, 10, 8)
        mode_lay.setSpacing(6)

        self.mode_a_rb = QRadioButton("The outputs I selected in step 4")
        self.mode_a_rb.setToolTip(
            "At Start, the translation list is derived from your Step 4\n"
            "output selection — nothing to re-tick here."
        )
        mode_lay.addWidget(self.mode_a_rb)
        self.mode_b_rb = QRadioButton("Let me choose")
        self.mode_b_rb.setToolTip("Pick the exact files to translate from the list below.")
        mode_lay.addWidget(self.mode_b_rb)

        # The manual list (mode B only — the pre-rework checkbox surface).
        self.manual_widget = QWidget()
        manual_lay = QVBoxLayout(self.manual_widget)
        manual_lay.setContentsMargins(20, 0, 0, 0)
        manual_lay.setSpacing(2)
        self._tr_cbs: dict[str, QCheckBox] = {}
        for key, label, subtitle in _TRANSLATABLE_OUTPUTS:
            cb = QCheckBox(f"{label}  —  {subtitle}")
            cb.setChecked(self.state.translation_outputs.get(key, False))
            manual_lay.addWidget(cb)
            self._tr_cbs[key] = cb
        mode_lay.addWidget(self.manual_widget)

        # Open on the remembered mode (D15: mode A is the default).
        if self.state.translation_selection_mode == "manual":
            self.mode_b_rb.setChecked(True)
        else:
            self.mode_a_rb.setChecked(True)
        self.mode_a_rb.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()
        settings_lay.addWidget(mode_box)

        # ── Quality (advanced): backend + the two model pickers ───────
        quality_box = QGroupBox("Quality (advanced)")
        quality_lay = QVBoxLayout(quality_box)
        quality_lay.setContentsMargins(10, 10, 10, 8)
        quality_lay.setSpacing(6)

        backend_row = QHBoxLayout()
        backend_row.setSpacing(8)
        backend_row.addWidget(QLabel("Translator backend:"))
        self.backend_combo = QComboBox()
        # V13.31.0 (#13): NLLB removed from the UI. Only TranslateGemma
        # (Ollama) is exposed.
        self.backend_combo.addItem("Ollama LLM (TranslateGemma)", "ollama")
        backend_current = self.state.translation_backend or self.controller.get_setting(
            "translation.backend", "ollama"
        )
        # V13.31.0 (#13): legacy "nllb" backends fall back to "ollama" in UI
        if backend_current == "nllb":
            backend_current = "ollama"
        idx = self.backend_combo.findData(backend_current)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        self.backend_combo.setToolTip(
            "The engine that translates. Ollama running a TranslateGemma\n"
            "model — the only supported backend."
        )
        backend_row.addWidget(self.backend_combo)
        backend_row.addStretch()
        quality_lay.addLayout(backend_row)

        # Refresh (the Step-5 grammar): re-list the server's models.
        refresh_row = QHBoxLayout()
        refresh_row.setSpacing(8)
        self.refresh_btn = QPushButton("Refresh models")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.setIcon(icon("refresh", color=theme_manager.palette.text_primary, size=16))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setToolTip(
            "List the models installed on the Ollama server\n"
            "(the llm.ollama_url setting says which server)."
        )
        self.refresh_btn.clicked.connect(self._refresh_models)
        refresh_row.addWidget(self.refresh_btn)
        refresh_row.addStretch()
        quality_lay.addLayout(refresh_row)

        # Harakat model — opens on the last-used pick, lists live.
        quality_lay.addWidget(QLabel("Harakat model (adds Persian diacritics — always Ollama):"))
        self.harakat_combo = QComboBox()
        self._seed_combo(
            self.harakat_combo, "translation_harakat_model", "translation.harakat_model"
        )
        self.harakat_combo.setToolTip(
            "The Ollama model that adds vowel diacritics to the Farsi\n"
            "translation.\n\nThe .harakat.md file it produces is a MANUAL-REVIEW\n"
            "copy — it is not yet wired into the Podcast Maker / TTS\n"
            "(that wiring is on the backlog)."
        )
        quality_lay.addWidget(self.harakat_combo)

        # Judge model
        quality_lay.addWidget(QLabel("Judge model (validation — empty = use summarization model):"))
        self.judge_combo = QComboBox()
        self.judge_combo.addItem("  (use summarization model)", "")
        self._seed_combo(self.judge_combo, "translation_judge_model", "translation.judge_model")
        self.judge_combo.setToolTip(
            "The Ollama model that scores each translated chunk for\n"
            "faithfulness. Empty uses the summarization model."
        )
        quality_lay.addWidget(self.judge_combo)

        # The muted, NON-MODAL listing hint — the empty case never blocks
        # (a QMessageBox here would trap every offscreen test that builds
        # this step; Step 5's modal is the cautionary tale).
        self.models_hint = QLabel("")
        self.models_hint.setWordWrap(True)
        self.models_hint.setStyleSheet(
            f"color: {theme_manager.palette.text_secondary}; font-size: 11px;"
            " padding: 2px 0; background: transparent;"
        )
        quality_lay.addWidget(self.models_hint)

        settings_lay.addWidget(quality_box)
        settings_lay.addStretch()
        self.settings_widget.setWidget(settings_host)
        lay.addWidget(self.settings_widget, 1)

        # ── The live listing (W-b11: never on the UI thread) ───────────
        # V0.7.4: the old build called controller.list_ollama_models()
        # SYNCHRONOUSLY — a hung server froze the wizard open for the
        # full 5s timeout. The listing now rides a SimpleWorker (the
        # Step-5 pattern); the combos already hold the seeded picks, so
        # the step is fully usable before the list lands.
        self._models_worker = None
        self._refresh_models()

        self._on_enable_changed()

    # ── Mode + enable wiring ────────────────────────────────────────────

    def _on_enable_changed(self) -> None:
        self.settings_widget.setEnabled(self.enable_cb.isChecked())

    def _on_mode_changed(self) -> None:
        """Mode A hides the manual list (the derivation follows Step 4 at
        Start); mode B reveals it (the pre-rework surface)."""
        self.manual_widget.setVisible(self.mode_b_rb.isChecked())

    # ── Model listing (the V0.7.3 Step-5 pattern, modal-free) ──────────

    def _seed_combo(self, combo: QComboBox, state_field: str, settings_key: str) -> None:
        """V0.7.4 (rework ⑥, D14 reuse): open the combo on the last-used
        pick — the state field (loaded from settings at wizard open, B5)
        first, the setting as fallback — before any listing has run.  The
        wizard shows what the user last chose, not an empty box."""
        saved = (
            str(getattr(self.state, state_field, "") or "").strip()
            or str(self.controller.get_setting(settings_key, "") or "").strip()
        )
        if saved and combo.findData(saved) < 0:
            combo.addItem(saved, saved)
            combo.setCurrentIndex(combo.findData(saved))

    def _fetch_models(self) -> list[str]:
        """The worker fn (pure HTTP through the controller's B1 method —
        no widget access; a stub controller without the method, or a down
        server, degrades to an empty list)."""
        try:
            return list(self.controller.list_ollama_models() or [])
        except Exception:
            return []

    def _refresh_models(self) -> None:
        """List the Ollama models on a worker (never blocks the UI thread)."""
        worker = getattr(self, "_models_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return
        self.refresh_btn.setEnabled(False)
        self._models_worker = SimpleWorker(self._fetch_models)
        self._models_worker.finished.connect(self._on_models_loaded)
        self._models_worker.failed.connect(self._on_models_failed)
        self._models_worker.start()

    def _on_models_loaded(self, models) -> None:
        """Worker finished — repopulate both pickers on the MAIN thread.

        V0.7.3 (rework ⑤, D14) pattern: the picks survive the refresh —
        a pick the server no longer lists is re-added and stays selected
        (a temporarily-down or reloaded server must not forget the
        user's choice).  Deliberately NON-MODAL on the empty case: the
        muted hint label carries it.
        """
        self.refresh_btn.setEnabled(True)
        models = list(models or [])
        for combo, state_field, settings_key in (
            (self.harakat_combo, "translation_harakat_model", "translation.harakat_model"),
            (self.judge_combo, "translation_judge_model", "translation.judge_model"),
        ):
            current = (
                str(combo.currentData() or "")
                or str(getattr(self.state, state_field, "") or "")
                or str(self.controller.get_setting(settings_key, "") or "")
            ).strip()
            has_placeholder = combo is self.judge_combo
            combo.clear()
            if has_placeholder:
                combo.addItem("  (use summarization model)", "")
            for m in models:
                combo.addItem(m, m)
            if current and combo.findData(current) < 0:
                # The last-used pick is not on the server right now — keep
                # it selectable anyway, right under the placeholder.
                combo.insertItem(1 if has_placeholder else 0, current, current)
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        if models:
            self.models_hint.setText(f"{len(models)} model(s) listed from Ollama.")
        else:
            self.models_hint.setText(
                "No models listed — make sure the Ollama server is running, then Refresh."
            )

    def _on_models_failed(self, _err=None) -> None:
        self.refresh_btn.setEnabled(True)
        self.models_hint.setText(
            "Could not reach the Ollama server — the saved picks stay selected; Refresh to retry."
        )

    # ── Save ────────────────────────────────────────────────────────────

    def save_to_state(self) -> None:
        self.state.translation_enabled = self.enable_cb.isChecked()
        self.state.translation_backend = self.backend_combo.currentData()
        self.state.translation_target_lang = self.lang_combo.currentData()
        self.state.translation_harakat_model = self.harakat_combo.currentData() or ""
        self.state.translation_judge_model = self.judge_combo.currentData() or ""
        # V0.7.4 (rework ⑥, D15): the selection mode rides the state; the
        # Start save turns it into the derivation (mode A) or the manual
        # list (mode B).
        self.state.translation_selection_mode = (
            "manual" if self.mode_b_rb.isChecked() else "selected"
        )
        for key, cb in self._tr_cbs.items():
            self.state.translation_outputs[key] = cb.isChecked()
