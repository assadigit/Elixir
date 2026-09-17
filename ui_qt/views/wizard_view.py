"""V5.3.0: Process Wizard — step-by-step guided conversion.

A user-friendly alternative to the Convert tab. Guides the user through
9 steps with smart defaults, validation, and a live-logs final page.

Steps:
  1. PDF selection + document type
  2. Page range + OCR settings
  3. OCR engine settings
  4. Output selection (19 types: 4 core + 15 Output Studio)
  5. Model selection (summarization, OCR, translation)
  6. Translation settings (backend, harakat, outputs)
  7. Advanced (segmentation, filter, academic rigor)
  8. Review + start conversion
  9. Live logs + progress

The existing Convert tab remains for power users — the wizard is a
simpler, more guided option that uses the same backend.

V18.20.4.6 (P5 / O-b1): the per-step decomposition. The step classes
moved VERBATIM into ui_qt/views/wizard_steps/ (one module per step +
shared.py for WizardState / the WizardStep base); this module keeps
the WizardView orchestrator (navigation, _start_conversion with the
W-b10 owner-tagged bridge install, closeEvent, the hardware-monitor
wiring, timers) and re-exports every step name below — everything
that was importable from ui_qt.views.wizard_view before the split
still is (back-compat facade; the only external importers,
app.py and convert_view.py, import WizardView). Step 9 — the
completion "Open summaries folder" button — now lives in
wizard_steps/step9_logs.py; its click is wired to
WizardView._open_summaries_folder (see _wire_controller).
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.models import ConversionResult
from ui_qt.controller_bridge import QtControllerBridge
from ui_qt.theme import theme_manager

# V18.20.4.6 (O-b1): the wizard's step classes now live in
# ui_qt/views/wizard_steps/ (one module per step, bodies verbatim).
# WizardView instantiates them all (see _build_ui / _rebuild_steps),
# and these imports double as the back-compat facade: every name
# below was importable from ui_qt.views.wizard_view before the split
# and still is (see __all__).
from ui_qt.views.wizard_steps.shared import WizardState, WizardStep
from ui_qt.views.wizard_steps.step1_pdf import Step1Pdf
from ui_qt.views.wizard_steps.step2_range import Step2Range
from ui_qt.views.wizard_steps.step3_ocr import Step3Ocr
from ui_qt.views.wizard_steps.step4_outputs import Step4Outputs
from ui_qt.views.wizard_steps.step5_models import Step5Models
from ui_qt.views.wizard_steps.step6_translation import Step6Translation
from ui_qt.views.wizard_steps.step7_advanced import Step7Advanced
from ui_qt.views.wizard_steps.step7b_fine_tune import Step7bFineTune
from ui_qt.views.wizard_steps.step8_review import Step8Review
from ui_qt.views.wizard_steps.step9_logs import Step9Logs

__all__ = [
    "WizardState",
    "WizardStep",
    "Step1Pdf",
    "Step2Range",
    "Step3Ocr",
    "Step4Outputs",
    "Step5Models",
    "Step6Translation",
    "Step7Advanced",
    "Step7bFineTune",
    "Step8Review",
    "Step9Logs",
    "WizardView",
]

# V18.20.3.12 (F821): module logger — the best-effort
# ``logger.debug`` sites referenced an undefined name (NameError on
# every swallowed-exception path); house pattern per
# ui_qt/views/queue_view.py.
logger = logging.getLogger(__name__)

# V18.20.4.9 (W-b14): compiled ONCE at import — ``_on_log`` runs on every
# log line (thousands per conversion); the old per-call ``import re`` +
# recompiles were pure overhead on the hot path. Patterns are verbatim
# from the old inline ``re.search`` calls (behavior identical).
_PROGRESS_RE = re.compile(r'Progress: (\d+)/(\d+) done.*?(\d+) bullets')
_CHAPTER_RE = re.compile(r'Chapter (\d+)/(\d+)')

# ════════════════════════════════════════════════════════════════════════════
# Wizard View (main container)
# ════════════════════════════════════════════════════════════════════════════

_STEP_LABELS = ["PDF", "Range", "OCR", "Outputs", "Models", "Translation", "Advanced", "Fine-tune", "Review", "Logs"]


class WizardView(QDialog):
    """The Process Wizard — a guided, step-by-step conversion dialog.

    Opens as a modal dialog from a CTA button on the primary page.
    The user walks through 10 steps, reviews all settings, then starts
    the conversion. The dialog stays open during conversion to show
    live logs, then the user can close it or start another.
    """

    conversion_started = Signal()
    conversion_complete = Signal(object)  # ConversionResult
    # V18.20.4.1 (P0 / W-b2): hardware-monitor auto-pause, marshalled to the
    # main thread. The monitor invokes auto_pause_callback on its own
    # polling thread; emitting this signal from that thread queues the
    # ``_on_auto_pause`` slot onto the Qt main thread (the same guarantee
    # the controller bridge gives the conversion callbacks).
    auto_pause_requested = Signal()

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.state = WizardState()
        # V10.1.10: load saved settings into the wizard state so the wizard
        # shows the user's actual configured values (max_workers, temperature,
        # models, etc.) instead of the hardcoded WizardState defaults.
        self._load_settings_into_state()
        self._current_step = 0
        self.bridge = QtControllerBridge()
        self._quick_mode = False  # V10.16.0 (E1): quick-mode flag

        # Dialog setup — modal, large, resizable
        self.setWindowTitle("Process Wizard — Step by Step Conversion")
        self.setModal(True)
        self.setMinimumSize(740, 540)  # V7.4.0: was 900x680 — compact
        self.resize(820, 600)            # V7.4.0: was 960x720

        self._build_ui()
        self._wire_controller()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Progress indicator ─────────────────────────────────────────
        self.progress_widget = QWidget()
        self.progress_widget.setFixedHeight(42)  # V7.4.0: was 48
        pw_lay = QHBoxLayout(self.progress_widget)
        pw_lay.setContentsMargins(20, 8, 20, 8)
        pw_lay.setSpacing(0)

        self._step_dots: list[QLabel] = []
        self._step_labels: list[QLabel] = []
        for i, label in enumerate(_STEP_LABELS):
            dot_col = QVBoxLayout()
            dot_col.setSpacing(2)
            dot_col.setAlignment(Qt.AlignCenter)
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet("font-size: 14px; background: transparent;")
            self._step_dots.append(dot)
            dot_col.addWidget(dot)
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: palette(text-muted); background: transparent;")
            self._step_labels.append(lbl)
            dot_col.addWidget(lbl)
            pw_lay.addLayout(dot_col)
            if i < len(_STEP_LABELS) - 1:
                line = QLabel("━")
                line.setAlignment(Qt.AlignCenter)
                line.setStyleSheet("font-size: 10px; color: palette(border); background: transparent;")
                pw_lay.addWidget(line)

        root.addWidget(self.progress_widget)

        # ── Step stack ─────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.step1 = Step1Pdf(self.controller, self.state)
        self.step2 = Step2Range(self.controller, self.state)
        self.step3 = Step3Ocr(self.controller, self.state)
        self.step4 = Step4Outputs(self.controller, self.state)
        self.step5 = Step5Models(self.controller, self.state)
        self.step6 = Step6Translation(self.controller, self.state)
        self.step7 = Step7Advanced(self.controller, self.state)
        self.step7b = Step7bFineTune(self.controller, self.state)
        self.step8 = Step8Review(self.controller, self.state)
        self.step9 = Step9Logs(self.controller, self.state)
        self.steps = [self.step1, self.step2, self.step3, self.step4,
                      self.step5, self.step6, self.step7, self.step7b,
                      self.step8, self.step9]
        for s in self.steps:
            self.stack.addWidget(s)
        root.addWidget(self.stack, 1)

        # ── Navigation buttons ─────────────────────────────────────────
        nav = QWidget()
        nav.setFixedHeight(46)  # V7.4.0: was 52
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(20, 8, 20, 8)
        nav_lay.setSpacing(10)

        self.cancel_wizard_btn = QPushButton("Cancel")
        self.cancel_wizard_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_wizard_btn.clicked.connect(self._cancel_wizard)
        nav_lay.addWidget(self.cancel_wizard_btn)
        nav_lay.addStretch()

        self.back_btn = QPushButton("< Back")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._go_back)
        nav_lay.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next >")
        self.next_btn.setObjectName("Primary")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.clicked.connect(self._go_next)
        nav_lay.addWidget(self.next_btn)

        root.addWidget(nav)

        self._update_step()

    def _wire_controller(self) -> None:
        """Connect controller callbacks to the logs step."""
        self.step8.start_requested.connect(self._start_conversion)
        self.step8.edit_step_requested.connect(self._jump_to_step)
        self.step9.cancel_btn.clicked.connect(self._cancel_conversion)
        self.step9.again_btn.clicked.connect(self._reset_wizard)
        self.step9.open_folder_btn.clicked.connect(self._open_output_folder)
        self.step9.open_summaries_btn.clicked.connect(self._open_summaries_folder)
        # V18.20.4.1 (P0 / W-b2): hardware-monitor auto-pause runs on the
        # MAIN thread (see the class-level signal).
        self.auto_pause_requested.connect(self._on_auto_pause)

    @Slot()
    def _on_auto_pause(self) -> None:
        """V9.0.0 E3 auto-pause — executed on the Qt main thread.

        V18.20.4.1 (P0 / W-b2): this used to run on the HardwareMonitor's
        polling thread and called ``self._on_log`` directly — a QTextBrowser
        write from a non-main thread (undefined behavior in Qt; the wizard's
        own comment at ``_start_conversion`` forbids exactly this class).
        Routed through ``auto_pause_requested`` the emission is queued and
        this slot runs on the main thread.
        """
        self._on_log("  ⏸️ Auto-pause triggered by hardware monitor.", "ERROR")
        self.controller.cancel_conversion()

    def _load_settings_into_state(self) -> None:
        """V10.1.10: Load saved settings into the wizard state.

        The wizard state has hardcoded defaults (max_workers=1, temp=0.6)
        but the user may have saved different values in settings.json.
        This loads the saved values so the wizard shows what's actually
        configured, not the defaults.
        """
        try:
            s = self.controller
            # Load key settings from the Settings singleton
            _mw = s.get_setting("summarisation.max_workers", 1)
            _temp = s.get_setting("summarisation.temperature", 0.6)
            _model = s.get_setting("summarisation.model", "")
            _fast = s.get_setting("summarisation.fast_model", "")
            _ocr = s.get_setting("ocr.primary_model", "")
            _source = s.get_setting("source_type", "normal_book")
            _cov = s.get_setting("summarisation.coverage_threshold", 50)
            _arch = s.get_setting("summarisation.model_architecture", "single_local") or "single_local"
            # Apply to state
            self.state.max_workers = int(_mw)
            self.state.temperature = float(_temp)
            # V16.0.9: backward-compat — legacy "single" → "single_local"
            self.state.model_architecture = "single_local" if _arch == "single" else _arch
            if _model:
                self.state.summarisation_model = _model
            if _fast:
                self.state.fast_model = _fast
            if _ocr:
                self.state.primary_ocr_model = _ocr
                self.state.fallback_ocr_model = _ocr
            if _source:
                self.state.source_type = _source
            # V18.2.1: Load performance + embedding settings into wizard state
            self.state.embedding_model = s.get_setting("embedding.model", "all-MiniLM-L6-v2")
            self.state.embedding_device = s.get_setting("embedding.device", "auto")
            self.state.vram_recovery_delay_sec = int(s.get_setting("local.vram_recovery_delay_sec", 0))
            self.state.b4_max_sections = int(s.get_setting("local.b4_max_sections", 6))
            self.state.b4_threshold_tokens = int(s.get_setting("summarisation.b4_threshold_tokens", 12000))
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)  # if settings can't be loaded, use WizardState defaults

    # ── Navigation ────────────────────────────────────────────────────

    def _update_step(self) -> None:
        self.stack.setCurrentIndex(self._current_step)
        # Update dots — V7.6.0 R3: current step is visually distinct via
        # larger dot + accent-colored background pill + bold label.
        p = theme_manager.palette
        for i, (dot, lbl) in enumerate(zip(self._step_dots, self._step_labels)):
            if i < self._current_step:
                # Completed step — muted green, normal size
                color = p.success
                dot.setStyleSheet(
                    f"font-size: 14px; color: {color}; background: transparent;"
                    f" font-weight: normal; border: none;"
                )
                lbl.setStyleSheet(
                    f"font-size: 10px; color: {p.text_muted}; background: transparent;"
                    f" font-weight: normal;"
                )
            elif i == self._current_step:
                # Current step — bigger dot, accent color, soft background pill
                dot.setStyleSheet(
                    f"font-size: 20px; color: {p.accent};"
                    f" background: {p.accent_soft};"
                    f" font-weight: bold;"
                    f" border: 2px solid {p.accent};"
                    f" border-radius: 12px;"
                    f" padding: 2px 6px;"
                )
                lbl.setStyleSheet(
                    f"font-size: 11px; color: {p.accent}; background: transparent;"
                    f" font-weight: bold;"
                )
            else:
                # Future step — muted, normal
                color = p.text_muted
                dot.setStyleSheet(
                    f"font-size: 14px; color: {color}; background: transparent;"
                    f" font-weight: normal; border: none;"
                )
                lbl.setStyleSheet(
                    f"font-size: 10px; color: {color}; background: transparent;"
                    f" font-weight: normal;"
                )
        # Update buttons
        self.back_btn.setEnabled(self._current_step > 0 and self._current_step < 9)
        if self._current_step == 9:
            # Logs step — hide nav buttons
            self.next_btn.setVisible(False)
            self.back_btn.setVisible(False)
            self.cancel_wizard_btn.setVisible(False)
        elif self._current_step == 8:
            # Review step — show Start button
            self.next_btn.setText("  🚀  Start")
            self.next_btn.setVisible(True)
            self.back_btn.setVisible(True)
            self.cancel_wizard_btn.setVisible(True)
            self.step8.refresh()
        else:
            self.next_btn.setText("Next >")
            self.next_btn.setVisible(True)
            self.back_btn.setVisible(True)
            self.cancel_wizard_btn.setVisible(True)

    def _go_next(self) -> None:
        # Save + validate current step
        self.steps[self._current_step].save_to_state()
        ok, err = self.steps[self._current_step].validate()
        if not ok:
            QMessageBox.warning(self, "Cannot proceed", err)
            return
        if self._current_step == 8:
            # Review → start conversion
            self._start_conversion()
            return
        if self._current_step < 9:
            self._current_step += 1
            self._update_step()

    def _go_back(self) -> None:
        if self._current_step > 0 and self._current_step < 9:
            self._current_step -= 1
            self._update_step()

    def _jump_to_step(self, step_idx: int) -> None:
        """Jump to a specific step (used by Review's Edit buttons)."""
        if 0 <= step_idx < 9:
            self._current_step = step_idx
            self._update_step()

    def _cancel_wizard(self) -> None:
        ret = QMessageBox.question(
            self, "Cancel wizard",
            "Cancel the wizard? Your choices will be lost.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.reject()  # Close the modal dialog

    def _reset_wizard(self) -> None:
        self.state = WizardState()
        self._current_step = 0
        # Rebuild step 1 (it holds references to old state)
        self._rebuild_steps()
        self.step9.reset()
        self._update_step()

    def _rebuild_steps(self) -> None:
        """Rebuild all steps with fresh state (used after reset)."""
        # Remove old steps
        for s in self.steps:
            self.stack.removeWidget(s)
            s.deleteLater()
        # Create new steps
        self.step1 = Step1Pdf(self.controller, self.state)
        self.step2 = Step2Range(self.controller, self.state)
        self.step3 = Step3Ocr(self.controller, self.state)
        self.step4 = Step4Outputs(self.controller, self.state)
        self.step5 = Step5Models(self.controller, self.state)
        self.step6 = Step6Translation(self.controller, self.state)
        self.step7 = Step7Advanced(self.controller, self.state)
        self.step7b = Step7bFineTune(self.controller, self.state)
        self.step8 = Step8Review(self.controller, self.state)
        self.step9 = Step9Logs(self.controller, self.state)
        self.steps = [self.step1, self.step2, self.step3, self.step4,
                      self.step5, self.step6, self.step7, self.step7b,
                      self.step8, self.step9]
        for s in self.steps:
            self.stack.addWidget(s)
        # Re-wire
        self.step8.start_requested.connect(self._start_conversion)
        self.step8.edit_step_requested.connect(self._jump_to_step)
        self.step9.cancel_btn.clicked.connect(self._cancel_conversion)
        self.step9.again_btn.clicked.connect(self._reset_wizard)
        self.step9.open_folder_btn.clicked.connect(self._open_output_folder)
        self.step9.open_summaries_btn.clicked.connect(self._open_summaries_folder)

    def _apply_quick_defaults(self) -> None:
        """V10.16.0 (E1): Apply smart defaults for quick-mode wizard.

        Quick mode shows only 3 essential steps:
          1. PDF selection (Step 1)
          2. Output selection (Step 4)
          3. Review + Start (Step 8)

        All other steps use smart defaults:
          - Range: all pages
          - OCR: auto-detect
          - Models: use saved settings
          - Translation: disabled
          - Advanced: defaults
          - Fine-tune: defaults
        """
        self.setWindowTitle("⚡ Quick Convert — 3-Step Setup")
        # Smart defaults — everything the user didn't explicitly set
        self.state.page_range_start = None
        self.state.page_range_end = None
        self.state.use_llm_ocr = True
        self.state.auto_detect_scanned = True
        self.state.force_ocr_all_pages = False
        self.state.enable_content_filter = True
        self.state.generate_summaries = True
        self.state.include_executive_summary = True
        self.state.include_thorough_summary = True
        self.state.include_keypoints = True
        self.state.translation_enabled = False
        # Quick mode: jump directly to Step 1 (PDF selection)
        self._current_step = 0
        self._update_step()

    # ── Conversion ────────────────────────────────────────────────────

    def _start_conversion(self) -> None:
        """Save all steps and start the conversion."""
        # Save all steps to state (steps 0-8, excluding logs at 9)
        for s in self.steps[:9]:
            s.save_to_state()
        # Validate step 1
        ok, err = self.step1.validate()
        if not ok:
            QMessageBox.warning(self, "Cannot start", err)
            self._current_step = 0
            self._update_step()
            return

        # Save translation settings to controller
        self._save_translation_settings()

        # V7.7.0: persist resume_enabled to settings (converter reads it from there)
        self.controller.update_setting(
            "summarisation.resume_enabled", self.state.resume_enabled
        )

        # V8.1.0: capture post-completion action from Step8's combo + persist
        self.state.post_completion_action = self.step8.post_action_combo.currentData()
        self.controller.update_setting(
            "ui.post_completion_action", self.state.post_completion_action
        )

        # Build request
        try:
            ui_data = self.state.to_ui_data()
            request = self.controller.build_request_from_ui(ui_data)
        except Exception as e:
            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
            # user box (was str(e)-only — zero diagnostics).
            logger.warning("failed to build conversion request",
                           exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to build conversion request: {e}")
            return

        # V10.19.0: Token cost estimation modal — show BEFORE starting.
        # Estimates total token usage (input + output) and asks the user
        # to confirm.  Especially important for cloud API users who pay
        # per token.
        try:
            from PySide6.QtWidgets import QDialog

            from core.pipeline.token_estimator import estimate_conversion_tokens
            from ui_qt.views.token_cost_dialog import TokenCostDialog

            estimate = estimate_conversion_tokens(
                pdf_path=request.input_path,
                request=request,
                password=request.password,
                log_callback=lambda msg, level: None,  # silent
            )
            if estimate and estimate.get("total_tokens", 0) > 0:
                dlg = TokenCostDialog(estimate, self)
                if dlg.exec() != QDialog.Accepted:
                    return  # user cancelled — don't start the conversion
        except ImportError:
            pass  # token estimator not available — proceed without estimate
        except Exception as e:
            # Don't block conversion if the estimator fails
            import logging
            logging.getLogger(__name__).debug(f"Token estimator skipped: {e}")

        # Jump to logs step (index 9)
        self._current_step = 9
        self.step9.reset()
        self._update_step()

        # Wire controller callbacks through the QtControllerBridge.
        # CRITICAL: The controller runs in a background thread. Qt widgets
        # can only be accessed from the main thread. The bridge uses Qt
        # signals (which are thread-safe) to marshal calls to the main thread.
        # Setting callbacks directly (controller.on_log = self._on_log) would
        # crash because the background thread would access Qt widgets directly.
        # V18.20.4.5 (W-b10): tag this set as the wizard's so closeEvent knows
        # whether it may hand the callbacks back to ConvertView (it must NOT
        # while the queue worker owns them for a whole queue run).
        self.controller.set_callbacks(
            on_progress=self.bridge.emit_progress,
            on_status=self.bridge.emit_status,
            on_log=self.bridge.emit_log,
            on_complete=self.bridge.emit_complete,
            owner="wizard",
        )
        # Connect bridge signals to the logs step UI
        self.bridge.connect_progress(self._on_progress)
        self.bridge.connect_status(self._on_status)
        self.bridge.connect_log(self._on_log)
        self.bridge.connect_complete(self._on_complete)

        # Start
        self.conversion_started.emit()
        self.step9.log_viewer.append("🚀 Starting conversion...", "INFO")
        # V5.3.7: Log ALL settings so we can diagnose what was sent
        self._log_settings()
        # V7.1.0 S3 + V18.20.4.10 (P0-c): VRAM budget check before starting.
        # Returns False when the user chose Abort (or the policy says abort) —
        # the conversion must NOT start, and no monitor/timer may be left running.
        if not self._check_vram_budget(request):
            self.step9.log_viewer.append(
                "⏹️ Conversion NOT started: VRAM overbudget (aborted).", "WARNING"
            )
            return
        # V8.1.0: Start hardware monitor
        self._start_hardware_monitor()
        # V10.25.0: Start elapsed timer
        self._start_elapsed_timer()
        self.controller.start_conversion(request)

    def _check_vram_budget(self, request=None) -> bool:
        """V7.1.0 S3: Calculate and log VRAM budget before conversion.

        V18.20.4.10 (P0-c): returns ``True`` when the conversion may start.
        When the plan is overbudget, the configured policy decides
        (``local.vram_overbudget_policy``):

        - ``"proceed"``  → log + continue (old behaviour, explicit choice).
        - ``"abort"``    → log + ``False`` (do not start).
        - ``"ask"`` (default) → a modal with **Abort as the default button**.
          "Proceed anyway" stamps ``request.vram_overbudget_acknowledged``
          (the converter re-checks and honors it); Abort returns ``False``.
          The V18.20.4.9 dialog was a plain warning whose OK button was the
          default — an accidental Enter started a 20.2 GB model on a 12 GB
          card and the run stalled for hours (the 97-Things incident).
        """
        try:
            from core.vram_calculator import calculate_vram_budget, format_vram_report
            s = self.state
            estimates, peak, total, recommendation = calculate_vram_budget(
                ocr_model=s.primary_ocr_model,
                summarization_model=s.summarisation_model,
                fast_model=s.fast_model,
                heavy_model=s.heavy_model,
                translation_backend=s.translation_backend if s.translation_enabled else "",
                translation_model=s.summarisation_model,  # Ollama translator
                harakat_model=s.translation_harakat_model if s.translation_enabled else "",
                judge_model=s.translation_judge_model if s.translation_enabled else "",
                tts_enabled=s.outputs_tts,
                tts_engine="neutts",
                max_workers=s.max_workers,
            )
            report = format_vram_report(estimates, peak, total, recommendation)
            for line in report.split("\n"):
                if "❌" in line or "⚠️" in line:
                    self.step9.log_viewer.append(line, "WARNING")
                else:
                    self.step9.log_viewer.append(line, "INFO")

            # V7.1.0 S3: If overbudget, let the policy decide (P0-c).
            if total and peak > total:
                from utils.settings import Settings as _VramSettings
                policy = str(
                    _VramSettings().get("local.vram_overbudget_policy", "ask")
                ).strip().lower()
                if policy == "proceed":
                    self.step9.log_viewer.append(
                        "⚠️ VRAM overbudget — policy=proceed: continuing at "
                        "explicit user choice (expect heavy CPU offload).",
                        "WARNING",
                    )
                    return True
                if policy == "abort":
                    self.step9.log_viewer.append(
                        "🛑 VRAM overbudget — policy=abort: conversion NOT started.",
                        "ERROR",
                    )
                    return False
                # policy == "ask" (default)
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("VRAM Overbudget — start anyway?")
                box.setText(
                    f"⚠️ VRAM Overbudget!\n\n"
                    f"Peak VRAM estimate: {peak:.1f} GB\n"
                    f"Available VRAM: {total:.1f} GB\n\n"
                    f"The model does NOT fit on the GPU. It will run heavily "
                    f"CPU-offloaded (~5-15 min per LLM call on a 27B quant) — "
                    f"a long-chapter book can take many hours.\n\n"
                    f"Recommendations:\n"
                    f"  • Use a smaller summarization model\n"
                    f"  • Reduce max_workers to 1\n"
                    f"  • Disable translation or TTS"
                )
                proceed_btn = box.addButton(
                    "Proceed anyway (at my own risk)",
                    QMessageBox.ButtonRole.AcceptRole,
                )
                abort_btn = box.addButton("Abort", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(abort_btn)  # V18.20.4.10: Abort is the DEFAULT
                box.exec()
                if box.clickedButton() is proceed_btn:
                    if request is not None:
                        # Stamp the interactive acknowledgment — the converter
                        # re-checks the budget and honors this (P0-c).
                        request.vram_overbudget_acknowledged = True
                    self.step9.log_viewer.append(
                        "⚠️ VRAM overbudget — user chose Proceed anyway.", "WARNING"
                    )
                    return True
                self.step9.log_viewer.append(
                    "🛑 VRAM overbudget — user chose Abort: conversion NOT started.",
                    "ERROR",
                )
                return False
            return True
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)  # VRAM check should never block conversion
            return True  # check itself failed — never block (V7.1.0 semantics)

    # ── V8.1.0: Hardware monitor ─────────────────────────────────────────

    def _start_elapsed_timer(self) -> None:
        """V10.25.0: Start a live elapsed timer shown in Step9Logs."""
        from PySide6.QtCore import QTime
        from PySide6.QtCore import QTimer as _QTimer
        self._elapsed_start = QTime.currentTime()
        self._elapsed_timer = _QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._elapsed_timer.start(1000)  # update every 1 second

    def _update_elapsed(self) -> None:
        """Update the elapsed time label."""
        from PySide6.QtCore import QTime
        if not hasattr(self, "_elapsed_start") or not hasattr(self.step9, "elapsed_label"):
            return
        elapsed = self._elapsed_start.secsTo(QTime.currentTime())
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self.step9.elapsed_label.setText(f"⏱️ Elapsed: {h:02d}:{m:02d}:{s:02d}")

    def _stop_elapsed_timer(self) -> None:
        """Stop the elapsed timer."""
        if hasattr(self, "_elapsed_timer"):
            self._elapsed_timer.stop()
            self._elapsed_timer.deleteLater()
            del self._elapsed_timer

    def _start_hardware_monitor(self) -> None:
        """Start the GPU/CPU/RAM monitor + a UI timer to update the label."""
        from core.system.hardware_monitor import HardwareMonitor
        # V9.0.0 E3: auto-pause callback — triggers cancel_conversion when
        # GPU temp reaches critical (88°C), preventing hardware damage.
        # V18.20.4.1 (P0 / W-b2): BOTH monitor callbacks run on the monitor's
        # polling thread — they must NOT touch Qt widgets directly (the
        # exact class the comment at ``_start_conversion`` forbids: "Setting
        # callbacks directly would crash because the background thread
        # would access Qt widgets directly"). The log callback now goes
        # through the bridge's log signal (emission from any thread queues
        # the connected slot onto the main thread — the bridge is the
        # wizard's own, and ``bridge.log → self._on_log`` is connected in
        # ``_start_conversion`` BEFORE the monitor starts); auto-pause goes
        # through the ``auto_pause_requested`` signal → ``_on_auto_pause``
        # slot, also queued to the main thread.
        def _auto_pause():
            self.auto_pause_requested.emit()
        self._hw_monitor = HardwareMonitor(
            log_callback=lambda msg, level: self.bridge.emit_log(msg, level),
            interval_sec=5.0,
            auto_pause_callback=_auto_pause,
        )
        self._hw_monitor.start()
        # QTimer to poll the snapshot + update the label (every 5s)
        from PySide6.QtCore import QTimer
        self._hw_timer = QTimer(self)
        self._hw_timer.timeout.connect(self._update_hw_label)
        self._hw_timer.start(5000)
        # Also log periodic snapshots (every 60s) for the conversion log
        self._hw_log_counter = 0

    def _stop_hardware_monitor(self) -> None:
        """Stop the hardware monitor + timer."""
        if hasattr(self, "_hw_timer"):
            self._hw_timer.stop()
            del self._hw_timer
        if hasattr(self, "_hw_monitor"):
            self._hw_monitor.stop()
            # Log a final snapshot
            snap = self._hw_monitor.get_snapshot()
            if not snap.is_empty():
                self.step9.log_viewer.append(
                    f"📊 Final hardware stats: {snap.format_compact()}", "INFO"
                )
            del self._hw_monitor

    def _update_hw_label(self) -> None:
        """Update the hardware status label with the latest snapshot."""
        if not hasattr(self, "_hw_monitor"):
            return
        snap = self._hw_monitor.get_snapshot()
        if snap.is_empty():
            return
        p = theme_manager.palette
        # Color the label red if GPU temp is critical
        temp_color = p.text_muted
        if snap.gpu_temp_c is not None:
            if snap.gpu_temp_c >= 88:
                temp_color = p.error
            elif snap.gpu_temp_c >= 83:
                temp_color = p.warning
        self.step9.hw_label.setText(f"📊 {snap.format_compact()}")
        self.step9.hw_label.setStyleSheet(
            f"font-size: 10px; color: {temp_color};"
            f" background: {p.bg_input};"
            f" padding: 3px 8px; border-radius: 4px;"
        )
        # Log a periodic snapshot every ~60s (12 polls at 5s interval)
        self._hw_log_counter += 1
        if self._hw_log_counter >= 12:
            self._hw_log_counter = 0
            self.step9.log_viewer.append(
                f"  📊 HW: {snap.format_compact()}", "DEBUG"
            )

    def _log_settings(self) -> None:
        """Dump all wizard settings to the log for diagnostics."""
        s = self.state
        log = self.step9.log_viewer
        log.append("━━━ Conversion Settings ━━━", "INFO")
        log.append(f"  PDF: {Path(s.input_path).name if s.input_path else '(none)'}", "INFO")
        log.append(f"  Document type: {s.source_type}", "INFO")
        if s.page_range_start is None:
            log.append("  Pages: all", "INFO")
        else:
            log.append(f"  Pages: {s.page_range_start}-{s.page_range_end}", "INFO")
        if s.selected_chapters:
            log.append(f"  Selected chapters: {len(s.selected_chapters)} chapter(s)", "INFO")
        log.append(f"  Auto-detect scanned: {s.auto_detect_scanned}", "INFO")
        log.append(f"  LLM OCR: {s.use_llm_ocr}, Force OCR: {s.force_ocr_all_pages}", "INFO")
        log.append(f"  PaddleOCR: {s.use_paddleocr}, Timeout: {s.ocr_timeout}s", "INFO")
        log.append(f"  Extract figures: {s.extract_figure_text}, Tables: {s.extract_tables}", "INFO")
        # Outputs
        outs = []
        if s.generate_summaries and s.include_executive_summary: outs.append("exec_summary")
        if s.generate_summaries and s.include_thorough_summary: outs.append("thorough_summary")
        if s.include_keypoints: outs.append("keypoints")
        if s.simplified_keypoints_enabled: outs.append("simplified_keypoints")
        if s.generate_docx: outs.append("docx")
        if s.outputs_briefing: outs.append("briefing")
        if s.outputs_podcast: outs.append("podcast_script")
        if s.outputs_tts: outs.append("podcast_audio")
        if s.outputs_flashcards: outs.append("flashcards")
        if s.outputs_packets: outs.append("packets")
        if s.outputs_obsidian: outs.append("obsidian")
        if s.outputs_study_guide: outs.append("study_guide")
        if s.outputs_social: outs.append("social")
        if s.outputs_mindmap: outs.append("mindmap")
        log.append(f"  Outputs: {', '.join(outs) if outs else '(none)'}", "INFO")
        # Models
        log.append(f"  Summarization model: {s.summarisation_model or '(default)'}", "INFO")
        log.append(f"  OCR model: {s.primary_ocr_model or '(default)'}", "INFO")
        log.append(f"  Fast model: {s.fast_model or '(default)'}", "INFO")
        log.append(f"  Workers: {s.max_workers}, Temperature: {s.temperature}", "INFO")
        # Translation
        log.append(f"  Translation enabled: {s.translation_enabled}", "INFO")
        if s.translation_enabled:
            log.append(f"    Backend: {s.translation_backend}", "INFO")
            log.append(f"    Target: {s.translation_target_lang}", "INFO")
            log.append(f"    Harakat model: {s.translation_harakat_model or '(default)'}", "INFO")
            log.append(f"    Judge model: {s.translation_judge_model or '(use summarization)'}", "INFO")
            tr_outs = [k for k, v in s.translation_outputs.items() if v]
            log.append(f"    Translate outputs: {', '.join(tr_outs) if tr_outs else '(none)'}", "INFO")
        # Advanced
        log.append(f"  Segmentation: {s.segment_strategy} (tokens: {s.token_limit})", "INFO")
        log.append(f"  Semantic: {s.enable_semantic}, Academic rigor: {s.academic_rigor}, "
                    f"Conservative drops: {s.conservative_drops}", "INFO")
        # Fine-tuning
        log.append(f"  Clean markdown: {s.clean_markdown}, Token saver: {s.token_saver}", "INFO")
        log.append(f"  Self-consistency: {s.self_consistency}, Coverage: {s.coverage_threshold}%", "INFO")
        log.append(f"  Content filter: {s.enable_content_filter}", "INFO")
        log.append(f"  Max context: {s.max_context_tokens}, Max output: {s.max_output_tokens}", "INFO")
        log.append(f"  Cache: {s.cache_enabled}", "INFO")
        log.append(f"  Heavy model: {s.heavy_model or '(disabled)'}", "INFO")
        log.append(f"  Simplification model: {s.simplification_model or '(use fast)'}", "INFO")
        log.append(f"  Extract math: {s.extract_math}, Layout analysis: {s.layout_analysis}", "INFO")
        log.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")

    def _save_translation_settings(self) -> None:
        """Save translation settings to the controller so the post-conversion
        auto-translation picks them up."""
        c = self.controller
        c.update_setting("translation.enabled", self.state.translation_enabled)
        c.update_setting("translation.backend", self.state.translation_backend)
        c.update_setting("translation.default_target_lang", self.state.translation_target_lang)
        c.update_setting("translation.harakat_model", self.state.translation_harakat_model)
        c.update_setting("translation.judge_model", self.state.translation_judge_model)
        for key, val in self.state.translation_outputs.items():
            c.update_setting(f"translation.outputs.{key}", val)

    # ── Controller callbacks ──────────────────────────────────────────

    def _on_progress(self, value: float) -> None:
        self.step9.progress.setValue(int(value * 100))
        # V7.1.0 S15: Update time estimate
        self._update_time_estimate()

    def _on_status(self, msg: str) -> None:
        # V6.0.0 Fix 2: Prefix status with phase info so user knows it's not done
        self.step9.status_label.setText(msg)
        # V7.1.0 S15: Track phase start time for time estimates
        # (W-b14: ``time`` is a module-level import — was per-call.)
        if not hasattr(self, "_phase_start_time"):
            self._phase_start_time = time.time()
        self._current_status = msg

    def _update_time_estimate(self) -> None:
        """V7.1.0 S15: Calculate and display estimated time remaining."""
        # (W-b14: ``time`` is a module-level import — was per-call.)
        if not hasattr(self, "_conversion_start_time"):
            self._conversion_start_time = time.time()
        if not hasattr(self, "_phase_start_time"):
            self._phase_start_time = self._conversion_start_time

        elapsed = time.time() - self._conversion_start_time
        progress_pct = self.step9.progress.value()

        if progress_pct > 5 and elapsed > 10:
            # Estimate: (elapsed / progress) * (100 - progress) = remaining
            remaining = (elapsed / progress_pct) * (100 - progress_pct)
            elapsed_str = self._format_duration(elapsed)
            remaining_str = self._format_duration(remaining)
            status = self.step9.status_label.text()
            # Append time estimate to status (only if not already there)
            if "Est." not in status:
                self.step9.status_label.setText(
                    f"{status}  |  Elapsed: {elapsed_str} | Est. remaining: ~{remaining_str}"
                )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as '1h 23m' or '4m 30s'."""
        if seconds < 60:
            return f"{int(seconds)}s"
        minutes = int(seconds / 60)
        if minutes < 60:
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        hours = int(minutes / 60)
        mins = minutes % 60
        return f"{hours}h {mins}m"

    def _on_log(self, msg: str, level: str = "INFO") -> None:
        self.step9.log_viewer.append(msg, level)

        # V10.21.0: Update quality dashboard from log messages
        # (W-b14: module-level compiled regex — was ``import re`` + two
        # recompiles per log line. The JSON-first structured source lands
        # at completion via _update_quality_dashboard_from_report, W-b15;
        # this log-string parse stays as the LIVE-progress fallback.)
        if hasattr(self.step9, "quality_label"):
            m = _PROGRESS_RE.search(msg)
            if m:
                done, total, bullets = int(m.group(1)), int(m.group(2)), int(m.group(3))
                self.step9.quality_label.setText(
                    f"Quality: {done}/{total} chapters done | {bullets} bullets total"
                )

        # V10.21.0: Update chapter status indicator
        if hasattr(self.step9, "chapter_status_label"):
            if "Chapter" in msg and "complete" in msg:
                m = _CHAPTER_RE.search(msg)
                if m:
                    done, total = int(m.group(1)), int(m.group(2))
                    self.step9.chapter_status_label.setText(
                        f"Chapters: {done}/{total} " + "✅" * min(done, 8) + "🔄"
                    )
            elif "attempt" in msg and "🤖" in msg:
                self.step9.chapter_status_label.setText("Chapters: Processing…")

        # V10.21.0: Update output preview pane
        if hasattr(self.step9, "preview_label"):
            if any(x in msg for x in ["Generating", "saved to", "completed"]):
                self.step9.preview_label.setText(f"Preview: {msg[:120]}")

    # ── V8.1.0: Post-completion action ───────────────────────────────────

    def _execute_post_completion_action(self, action: str) -> None:
        """Execute the post-completion action (shutdown/sleep/hibernate/quit).

        For shutdown/sleep/hibernate: shows a 60-second countdown dialog
        that the user can cancel.  For quit: closes the wizard immediately.
        """
        if action == "quit":
            self.step9.log_viewer.append("  👋 Quitting app as requested…", "INFO")
            # Close the wizard + the main window
            self.accept()  # close the wizard dialog
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
            return

        # shutdown / sleep / hibernate — show countdown
        action_labels = {
            "shutdown": "Shut down",
            "sleep": "Sleep",
            "hibernate": "Hibernate",
        }
        label = action_labels.get(action, action.capitalize())
        # V9.0.0 E2: configurable countdown (setting ui.shutdown_countdown_sec)
        countdown_sec = int(self.controller.get_setting("ui.shutdown_countdown_sec", 60))
        self.step9.log_viewer.append(
            f"  ⏳ {label} in {countdown_sec} seconds (click Cancel in the dialog to abort)…",
            "WARNING"
        )

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

        countdown_dlg = QDialog(self)
        countdown_dlg.setWindowTitle(f"{label} countdown")
        countdown_dlg.setModal(True)
        countdown_dlg.setMinimumWidth(360)
        cdl = QVBoxLayout(countdown_dlg)
        msg_label = QLabel(
            f"<b>{label}</b> in <b>{countdown_sec}</b> seconds…\n\n"
            f"The conversion is complete. The computer will {label.lower()} "
            f"automatically.\n\nClick <b>Cancel</b> to abort."
        )
        msg_label.setWordWrap(True)
        cdl.addWidget(msg_label)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Danger")
        cancel_btn.setMinimumWidth(80)
        btn_row.addWidget(cancel_btn)
        cdl.addLayout(btn_row)

        countdown_dlg._cancelled = False

        def _cancel():
            countdown_dlg._cancelled = True
            countdown_dlg.accept()

        cancel_btn.clicked.connect(_cancel)

        # Countdown timer — V9.0.0 E2: configurable duration
        remaining = [countdown_sec]
        def _tick():
            remaining[0] -= 1
            if remaining[0] <= 0:
                timer.stop()
                countdown_dlg.accept()
            else:
                msg_label.setText(
                    f"<b>{label}</b> in <b>{remaining[0]}</b> seconds…\n\n"
                    f"The conversion is complete. The computer will {label.lower()} "
                    f"automatically.\n\nClick <b>Cancel</b> to abort."
                )

        timer = QTimer(countdown_dlg)
        timer.timeout.connect(_tick)
        timer.start(1000)

        countdown_dlg.exec()

        if countdown_dlg._cancelled:
            self.step9.log_viewer.append(f"  ✅ {label} cancelled by user.", "INFO")
            return

        # Execute the action
        try:
            from core.system.hardware_monitor import execute_post_completion_action
            execute_post_completion_action(action, delay_seconds=0, log_callback=self._on_log)
            self.step9.log_viewer.append(f"  🔌 {label} command executed.", "INFO")
        except Exception as e:
            self.step9.log_viewer.append(f"  ⚠️ {label} failed: {e}", "ERROR")

    def _on_complete(self, result: ConversionResult) -> None:
        # Stop hardware monitor + elapsed timer IMMEDIATELY
        self._stop_hardware_monitor()
        self._stop_elapsed_timer()

        # V10.24.0: Show the modal directly (not via singleShot).
        # The singleShot(0) approach was causing the modal to not appear
        # in some cases — the event loop was busy with pending log
        # messages and the modal was delayed indefinitely.
        # Direct call ensures the user sees the completion immediately.
        try:
            self._show_completion_modal(result)
        except Exception:
            # Fallback: if the modal fails, at least show a basic message
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Conversion Complete",
                f"Conversion finished. Success: {result.success}")

    def _update_quality_dashboard_from_report(self) -> None:
        """V18.20.4.9 (W-b15): refresh the step9 quality dashboard from the
        run's ``logs/quality_report.json`` (written at end-of-run by the
        converter — the structured metrics source).

        Reads ``totals`` (successful_summaries / chapters_summarized /
        total_bullets) and renders the SAME format string the _on_log
        fallback produces. Missing file / unparsable / non-numeric →
        silent no-op: the _on_log log-string parse remains the live
        in-run source and its last values stay on screen (fail-soft).
        """
        if not hasattr(self.step9, "quality_label"):
            return
        try:
            import json

            base = (Path(self.state.output_dir)
                    if self.state.output_dir
                    else (Path(self.state.input_path).parent
                          if self.state.input_path else None))
            if base is None:
                return
            report_path = base / "logs" / "quality_report.json"
            if not report_path.exists():
                return
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            totals = report.get("totals") or {}
            done = totals.get("successful_summaries")
            total = totals.get("chapters_summarized")
            bullets = totals.get("total_bullets")
            if not (isinstance(done, int) and isinstance(total, int)
                    and isinstance(bullets, int)):
                return  # non-numeric/missing — keep the fallback values
            self.step9.quality_label.setText(
                f"Quality: {done}/{total} chapters done | {bullets} bullets total"
            )
        except Exception:
            logger.debug("quality report read failed", exc_info=True)

    def _show_completion_modal(self, result: ConversionResult) -> None:
        """Show the completion/failure modal (called via singleShot on main thread)."""
        if result.success:
            self.step9.progress.setValue(100)
            # V18.20.4.9 (W-b15): land the FINAL measured numbers from
            # logs/quality_report.json (the same file the P0 W-a2 coverage
            # fix reads) — JSON-first, with the _on_log log-string parse as
            # the live in-run fallback. Success-gated so a failed run never
            # paints a STALE report's numbers; displayed format identical.
            self._update_quality_dashboard_from_report()
            self.step9.status_label.setText("✅ All phases complete!")
            self.step9.log_viewer.append("", "INFO")
            self.step9.log_viewer.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "SUCCESS")
            self.step9.log_viewer.append("✅ CONVERSION FULLY COMPLETE!", "SUCCESS")
            self.step9.log_viewer.append(f"  Pages processed: {result.pages_processed}", "INFO")
            self.step9.log_viewer.append(f"  Chapters detected: {result.chapters_detected}", "INFO")
            self.step9.log_viewer.append(f"  Summaries generated: {result.summaries_generated}", "INFO")
            if result.warnings:
                self.step9.log_viewer.append(f"  Warnings: {len(result.warnings)}", "WARNING")
                for w in result.warnings[:5]:
                    self.step9.log_viewer.append(f"    ⚠️ {w}", "WARNING")
            self.step9.log_viewer.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "SUCCESS")
            self.step9.cancel_btn.setVisible(False)
            self.step9.open_folder_btn.setVisible(True)
            self.step9.open_summaries_btn.setVisible(True)
            self.step9.again_btn.setVisible(True)
            QMessageBox.information(
                self, "Conversion Complete",
                f"✅ Conversion fully complete!\n\n"
                f"Pages processed: {result.pages_processed}\n"
                f"Chapters: {result.chapters_detected}\n"
                f"Summaries: {result.summaries_generated}\n\n"
                f"Output saved to:\n{result.full_markdown_path.parent if result.full_markdown_path else '(unknown)'}\n\n"
                f"Click 'Open output folder' to see the results."
            )
            # Auto-open output folder on completion (if enabled)
            if self.controller.get_setting("ui.auto_open_output_folder", False):
                try:
                    import subprocess
                    import sys
                    folder = str(result.full_markdown_path.parent) if result.full_markdown_path else ""
                    if folder:
                        if sys.platform == "win32":
                            subprocess.Popen(["explorer", folder])
                        elif sys.platform == "darwin":
                            subprocess.Popen(["open", folder])
                        else:
                            subprocess.Popen(["xdg-open", folder])
                except (OSError, FileNotFoundError):
                    pass

            # Post-completion action (shutdown/sleep/quit)
            action = self.state.post_completion_action
            if action and action != "none":
                self._execute_post_completion_action(action)
        else:
            self.step9.status_label.setText("❌ Conversion failed")
            self.step9.log_viewer.append(f"❌ Conversion failed: {result.error_msg}", "ERROR")
            self.step9.cancel_btn.setVisible(False)
            self.step9.again_btn.setVisible(True)
            QMessageBox.critical(
                self, "Conversion Failed",
                f"❌ Conversion failed:\n\n{result.error_msg}\n\n"
                f"Check the log for details."
            )
        self.conversion_complete.emit(result)

    def closeEvent(self, event) -> None:
        """Clean up controller callbacks when the wizard dialog closes."""
        # V18.20.4.1 (P0 / W-b4): closing the wizard mid-conversion used to
        # ORPHAN the hardware monitor (a thread polling nvidia-smi every 5s)
        # and the elapsed timer (a 1s QTimer) for the rest of the app
        # session — ``_on_complete`` was the ONLY stop path, and this
        # handler disconnects the very bridge signals that deliver it (the
        # exact V18.20.3.14 close-mid-conversion scenario). Both stoppers
        # are hasattr-guarded and no-ops when nothing is running, so a
        # normal close-after-completion is unaffected.
        try:
            self._stop_hardware_monitor()
        except Exception:
            pass  # best-effort — never crash on close
        try:
            self._stop_elapsed_timer()
        except Exception:
            pass  # best-effort — never crash on close
        # V5.4.1: Safe disconnect — wrap each in try/except to avoid
        # "Failed to disconnect (None)" runtime warnings when signals
        # were never connected (e.g., user closed before starting conversion)
        for sig in [self.bridge.progress, self.bridge.status,
                       self.bridge.log, self.bridge.complete]:
            try:
                sig.disconnect()
            except Exception:
                pass  # best-effort — never crash on close
        # V18.20.4.5 (W-b10): restore ConvertView's callbacks ONLY if
        # nothing else owns them now. The queue worker installs its own
        # callbacks for the whole queue run (queue_view
        # _install_queue_callbacks); an unconditional restore here used to
        # STEAL them mid-queue — the queue's on_complete result capture
        # silently stopped firing and per-book modals popped from a hidden
        # tab. Never steal from the queue.
        try:
            main_window = self.parent()
            if main_window and hasattr(main_window, "convert_view"):
                owner = getattr(self.controller, "callback_owner", None)
                if owner == "queue":
                    log_target = getattr(
                        getattr(self, "step9", None), "log_viewer", None)
                    if log_target is not None:
                        log_target.append(
                            "ℹ️ Queue owns the controller callbacks — wizard "
                            "close leaves them in place (W-b10).", "INFO")
                else:
                    main_window.convert_view._register_callbacks()
        except Exception:
            pass  # best-effort
        super().closeEvent(event)

    def _cancel_conversion(self) -> None:
        ret = QMessageBox.question(
            self, "Cancel conversion",
            "Cancel the running conversion?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.controller.cancel_conversion()
            self.step9.log_viewer.append("⚠️ Cancellation requested...", "WARNING")

    def _open_output_folder(self) -> None:
        import subprocess
        import sys
        out_dir = self.state.output_dir or str(Path(self.state.input_path).parent)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", out_dir])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])

    def _open_summaries_folder(self) -> None:
        """V18.20.3.9 (Phase 2 / B1): open <output>/summaries directly —

        The canonical, provenance-stamped chapter summaries live there;
        opening the folder at completion kills the wrong-file-upload class
        (the user previously grabbed a stale file from an older version's
        folder 4 times in a row).
        """
        import subprocess
        import sys
        base = Path(self.state.output_dir) if self.state.output_dir else Path(self.state.input_path).parent
        target = base / "summaries"
        if not target.exists():
            target = base  # graceful fallback — never error from a button
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])

    # ── Public ────────────────────────────────────────────────────────

    def refresh_theme(self) -> None:
        """Refresh theme-dependent styling."""
        self._update_step()
