"""Step 7b: Fine-tuning (17 settings in 4 collapsible groups) — Step7bFineTune (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step7bFineTune
(back-compat facade).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui_qt.views.wizard_steps.shared import WizardStep

# V18.20.3.12 (F821) pattern, carried with the class: the
# best-effort ``logger.debug`` sites must not NameError on
# swallowed-exception paths (house pattern per queue_view).
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Step 7b: Fine-tuning (17 settings in 4 collapsible groups)
# ════════════════════════════════════════════════════════════════════════════

class Step7bFineTune(WizardStep):
    """Fine-tuning: post-processing, DOCX, quality, summarization limits, advanced doc."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        title = QLabel("Fine-tuning")
        title.setObjectName("H2")
        lay.addWidget(title)

        subtitle = QLabel("All settings below use sensible defaults. Change them only if you need specific control.")
        subtitle.setObjectName("Caption")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setSpacing(8)
        host_lay.setContentsMargins(0, 0, 0, 0)

        # ── Post-processing (5) ─────────────────────────────────────────
        pp_box = QGroupBox("Post-processing")
        pp_lay = QVBoxLayout(pp_box)
        pp_lay.setContentsMargins(10, 10, 10, 8)
        pp_lay.setSpacing(5)
        self.clean_cb = QCheckBox("Clean markdown (remove extraction artifacts)")
        self.clean_cb.setChecked(self.state.clean_markdown)
        pp_lay.addWidget(self.clean_cb)
        self.spaces_cb = QCheckBox("Fix missing spaces (join words run together)")
        self.spaces_cb.setChecked(self.state.fix_missing_spaces)
        pp_lay.addWidget(self.spaces_cb)
        self.token_saver_cb = QCheckBox("Token saver (compress output)")
        self.token_saver_cb.setChecked(self.state.token_saver)
        pp_lay.addWidget(self.token_saver_cb)
        self.pagehead_cb = QCheckBox("Remove page-number headings")
        self.pagehead_cb.setChecked(self.state.remove_page_number_headings)
        pp_lay.addWidget(self.pagehead_cb)
        self.separators_cb = QCheckBox("Convert separators (---) to comments")
        self.separators_cb.setChecked(self.state.convert_separators_to_comments)
        pp_lay.addWidget(self.separators_cb)
        host_lay.addWidget(pp_box)

        # ── DOCX (2) ────────────────────────────────────────────────────
        docx_box = QGroupBox("DOCX options")
        docx_lay = QVBoxLayout(docx_box)
        docx_lay.setContentsMargins(10, 10, 10, 8)
        docx_lay.setSpacing(5)
        author_row = QHBoxLayout()
        author_row.setSpacing(8)
        self.author_edit = QLineEdit(self.state.docx_author)
        author_row.addWidget(QLabel("Author:"))
        author_row.addWidget(self.author_edit, 1)
        docx_lay.addLayout(author_row)
        self.toc_cb = QCheckBox("Include table of contents")
        self.toc_cb.setChecked(self.state.docx_include_toc)
        docx_lay.addWidget(self.toc_cb)
        host_lay.addWidget(docx_box)

        # ── Quality controls (4) ────────────────────────────────────────
        q_box = QGroupBox("Quality controls")
        q_lay = QVBoxLayout(q_box)
        q_lay.setContentsMargins(10, 10, 10, 8)
        q_lay.setSpacing(5)
        self.self_consist_cb = QCheckBox("Self-consistency (multi-sample voting — slower, more accurate)")
        self.self_consist_cb.setChecked(self.state.self_consistency)
        q_lay.addWidget(self.self_consist_cb)
        self.filter_cb = QCheckBox("Content filter (filter out headers/footers/non-content)")
        self.filter_cb.setChecked(self.state.enable_content_filter)
        q_lay.addWidget(self.filter_cb)
        # Heavy model
        try:
            models = self.controller.list_ollama_models()
        except Exception:
            models = []
        heavy_row = QHBoxLayout()
        heavy_row.setSpacing(8)
        heavy_row.addWidget(QLabel("Heavy model:"))
        self.heavy_combo = QComboBox()
        self.heavy_combo.addItem("  (disabled)", "")
        for m in models:
            self.heavy_combo.addItem("📝 " + m, m)
        if self.state.heavy_model:
            idx = self.heavy_combo.findData(self.state.heavy_model)
            if idx >= 0:
                self.heavy_combo.setCurrentIndex(idx)
        heavy_row.addWidget(self.heavy_combo, 1)
        q_lay.addLayout(heavy_row)
        # Coverage threshold
        cov_row = QHBoxLayout()
        cov_row.setSpacing(8)
        self.coverage_spin = QSpinBox()
        self.coverage_spin.setRange(0, 100)
        self.coverage_spin.setSuffix("%")
        self.coverage_spin.setValue(self.state.coverage_threshold)
        cov_row.addWidget(QLabel("Coverage threshold (reprompt trigger):"))
        cov_row.addWidget(self.coverage_spin)
        cov_row.addStretch()
        q_lay.addLayout(cov_row)

        # V7.7.0: Chapter-level resume — skip chapters with valid summaries
        self.resume_cb = QCheckBox(
            "Resume mode — skip chapters that already have valid summaries "
            "(process only new/changed chapters)"
        )
        self.resume_cb.setChecked(self.state.resume_enabled)
        self.resume_cb.setToolTip(
            "When enabled, chapters that were summarized in a previous run "
            "(valid summary file on disk) are skipped — the LLM only processes "
            "new chapters.  This lets you process a book in stages: a few "
            "chapters today, the rest tomorrow, without redoing work.\n\n"
            "The summary files ARE the resume token — delete a summary file "
            "to force that chapter to reprocess."
        )
        q_lay.addWidget(self.resume_cb)

        host_lay.addWidget(q_box)

        # ── Summarization limits (4) ────────────────────────────────────
        sum_box = QGroupBox("Summarization limits")
        sum_lay = QVBoxLayout(sum_box)
        sum_lay.setContentsMargins(10, 10, 10, 8)
        sum_lay.setSpacing(5)
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(8)
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(1000, 128000)
        self.ctx_spin.setSingleStep(1000)
        self.ctx_spin.setValue(self.state.max_context_tokens)
        ctx_row.addWidget(QLabel("Max context tokens:"))
        ctx_row.addWidget(self.ctx_spin)
        ctx_row.addStretch()
        sum_lay.addLayout(ctx_row)
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.out_spin = QSpinBox()
        self.out_spin.setRange(256, 32768)
        self.out_spin.setSingleStep(256)
        self.out_spin.setValue(self.state.max_output_tokens)
        out_row.addWidget(QLabel("Max output tokens:"))
        out_row.addWidget(self.out_spin)
        out_row.addStretch()
        sum_lay.addLayout(out_row)
        self.cache_cb = QCheckBox("Cache summaries to disk (faster re-runs)")
        self.cache_cb.setChecked(self.state.cache_enabled)
        sum_lay.addWidget(self.cache_cb)
        # Simplification model
        simpl_row = QHBoxLayout()
        simpl_row.setSpacing(8)
        simpl_row.addWidget(QLabel("Simplification model:"))
        self.simpl_combo = QComboBox()
        self.simpl_combo.addItem("  (use fast model)", "")
        for m in models:
            self.simpl_combo.addItem("📝 " + m, m)
        if self.state.simplification_model:
            idx = self.simpl_combo.findData(self.state.simplification_model)
            if idx >= 0:
                self.simpl_combo.setCurrentIndex(idx)
        simpl_row.addWidget(self.simpl_combo, 1)
        sum_lay.addLayout(simpl_row)
        host_lay.addWidget(sum_box)

        # ── Advanced doc handling (2) ───────────────────────────────────
        adv_box = QGroupBox("Advanced document handling")
        adv_lay = QVBoxLayout(adv_box)
        adv_lay.setContentsMargins(10, 10, 10, 8)
        adv_lay.setSpacing(5)
        self.math_cb = QCheckBox("Extract math formulas (pix2tex)")
        self.math_cb.setChecked(self.state.extract_math)
        adv_lay.addWidget(self.math_cb)
        self.layout_cb = QCheckBox("Layout analysis (detectron2 — may fail if not installed)")
        self.layout_cb.setChecked(self.state.layout_analysis)
        adv_lay.addWidget(self.layout_cb)
        host_lay.addWidget(adv_box)

        # ── V18.2.1: Performance & Embeddings ──────────────────────────
        # Controls for the embedding model (hallucination detection),
        # VRAM recovery delay (thermal management), and B4 map-reduce
        # threshold. These are settings-level (persisted to settings.json),
        # not request-level, so they survive across conversions.
        perf_box = QGroupBox("Performance & Embeddings")
        perf_lay = QVBoxLayout(perf_box)
        perf_lay.setContentsMargins(10, 10, 10, 8)
        perf_lay.setSpacing(6)

        # Embedding model — presets for the two recommended options
        perf_lay.addWidget(QLabel(
            "Embedding model (used for hallucination detection, dedup, validation):"
        ))
        emb_row = QHBoxLayout()
        emb_row.setSpacing(8)
        self.embed_combo = QComboBox()
        self.embed_combo.addItem("🦙 nomic-embed-text (274 MB — via Ollama, just `ollama pull nomic-embed-text`)", "nomic-embed-text")
        # Select the current state's model
        _emb_idx = self.embed_combo.findData(self.state.embedding_model)
        if _emb_idx >= 0:
            self.embed_combo.setCurrentIndex(_emb_idx)
        else:
            # Unknown model — add it as a custom entry
            self.embed_combo.addItem(self.state.embedding_model, self.state.embedding_model)
            self.embed_combo.setCurrentIndex(self.embed_combo.count() - 1)
        self.embed_combo.setToolTip(
            "nomic-embed-text: 274 MB, via Ollama — RECOMMENDED. Just run 'ollama pull nomic-embed-text'.\n"
            "  No sentence_transformers needed. Works with your existing Ollama setup.\n"
            "MiniLM: 80 MB, fast on CPU. Needs sentence_transformers Python package.\n"
            "BGE-small: 130 MB, MTEB 62. Needs sentence_transformers.\n"
            "BGE-base: 440 MB, MTEB 64 — needs ~0.5 GB VRAM (use with IQ2_XXS).\n"
            "Qwen3-0.6B GGUF: 639 MB, MTEB ~66, multilingual — loaded via Ollama.\n"
            "  ⚠️ Qwen3 GGUF requires: ollama create qwen3-embed -f Modelfile\n"
            "  (where Modelfile: FROM ./Qwen3-Embedding-0.6B-Q8_0.gguf)"
        )
        emb_row.addWidget(self.embed_combo, 1)
        perf_lay.addLayout(emb_row)

        # Embedding device
        dev_row = QHBoxLayout()
        dev_row.setSpacing(8)
        dev_row.addWidget(QLabel("Embedding device:"))
        self.embed_dev_combo = QComboBox()
        self.embed_dev_combo.addItem("Auto (GPU if VRAM free, else CPU)", "auto")
        self.embed_dev_combo.addItem("GPU (force CUDA)", "cuda")
        self.embed_dev_combo.addItem("CPU (force — for VRAM-constrained cards)", "cpu")
        _dev_idx = self.embed_dev_combo.findData(self.state.embedding_device)
        if _dev_idx >= 0:
            self.embed_dev_combo.setCurrentIndex(_dev_idx)
        self.embed_dev_combo.setToolTip(
            "Auto: uses GPU if >0.6 GB VRAM is free, else falls back to CPU.\n"
            "GPU: forces CUDA — faster but risks OOM if VRAM is full.\n"
            "CPU: safest — no VRAM competition with the LLM."
        )
        dev_row.addWidget(self.embed_dev_combo, 1)
        perf_lay.addLayout(dev_row)

        # Thermal / VRAM recovery delay slider
        perf_lay.addWidget(QLabel(
            "VRAM recovery delay (thermal management — 0 = disabled):"
        ))
        therm_row = QHBoxLayout()
        therm_row.setSpacing(8)
        self.thermal_slider = QSlider(Qt.Horizontal)
        self.thermal_slider.setRange(0, 180)
        self.thermal_slider.setSingleStep(10)
        self.thermal_slider.setValue(self.state.vram_recovery_delay_sec)
        self.thermal_slider.setToolTip(
            "Seconds to sleep + clear GPU cache between B4 sections.\n"
            "0 = disabled (recommended if you undervolted your GPU via MSI Afterburner).\n"
            "60-120 = useful for cards with thermal throttling issues.\n"
            "This setting is user-controllable per your request."
        )
        self.thermal_label = QLabel(f"{self.state.vram_recovery_delay_sec}s")
        self.thermal_label.setMinimumWidth(40)
        self.thermal_slider.valueChanged.connect(
            lambda v: self.thermal_label.setText(f"{v}s")
        )
        therm_row.addWidget(self.thermal_slider, 1)
        therm_row.addWidget(self.thermal_label)
        perf_lay.addLayout(therm_row)

        # B4 section cap + threshold (compact row)
        b4_row = QHBoxLayout()
        b4_row.setSpacing(8)
        b4_row.addWidget(QLabel("B4 max sections:"))
        self.b4_sections_spin = QSpinBox()
        self.b4_sections_spin.setRange(0, 20)
        self.b4_sections_spin.setToolTip(
            "Max sections processed in B4 map-reduce. 0 = unlimited (cloud-like).\n"
            "6 = default (covers most academic chapters)."
        )
        self.b4_sections_spin.setValue(self.state.b4_max_sections)
        b4_row.addWidget(self.b4_sections_spin)
        b4_row.addSpacing(12)
        b4_row.addWidget(QLabel("B4 threshold (tokens):"))
        self.b4_threshold_spin = QSpinBox()
        self.b4_threshold_spin.setRange(4000, 60000)
        self.b4_threshold_spin.setSingleStep(1000)
        self.b4_threshold_spin.setSuffix(" tok")
        self.b4_threshold_spin.setToolTip(
            "Chapters above this token count trigger B4 section map-reduce.\n"
            "12000 = default (most chapters do single-pass = 1 LLM call).\n"
            "8000 = original (more chapters use B4 = better coverage but 6× slower)."
        )
        self.b4_threshold_spin.setValue(self.state.b4_threshold_tokens)
        b4_row.addWidget(self.b4_threshold_spin)
        b4_row.addStretch()
        perf_lay.addLayout(b4_row)

        host_lay.addWidget(perf_box)

        host_lay.addStretch()
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)

    def save_to_state(self) -> None:
        self.state.clean_markdown = self.clean_cb.isChecked()
        self.state.fix_missing_spaces = self.spaces_cb.isChecked()
        self.state.token_saver = self.token_saver_cb.isChecked()
        self.state.remove_page_number_headings = self.pagehead_cb.isChecked()
        self.state.convert_separators_to_comments = self.separators_cb.isChecked()
        self.state.docx_author = self.author_edit.text().strip()
        self.state.docx_include_toc = self.toc_cb.isChecked()
        self.state.self_consistency = self.self_consist_cb.isChecked()
        self.state.heavy_model = self.heavy_combo.currentData() or ""
        self.state.coverage_threshold = self.coverage_spin.value()
        self.state.resume_enabled = self.resume_cb.isChecked()
        self.state.enable_content_filter = self.filter_cb.isChecked()
        self.state.max_context_tokens = self.ctx_spin.value()
        self.state.max_output_tokens = self.out_spin.value()
        self.state.cache_enabled = self.cache_cb.isChecked()
        self.state.simplification_model = self.simpl_combo.currentData() or ""
        self.state.extract_math = self.math_cb.isChecked()
        self.state.layout_analysis = self.layout_cb.isChecked()
        # V18.2.1: Persist performance + embedding settings to settings.json
        # These are settings-level (not request-level), so we write them
        # directly via controller.update_setting(). The pipeline reads them
        # at runtime from Settings().
        self.state.embedding_model = self.embed_combo.currentData() or "nomic-embed-text"
        self.state.embedding_device = self.embed_dev_combo.currentData() or "auto"
        self.state.vram_recovery_delay_sec = self.thermal_slider.value()
        self.state.b4_max_sections = self.b4_sections_spin.value()
        self.state.b4_threshold_tokens = self.b4_threshold_spin.value()
        try:
            self.controller.update_setting("embedding.model", self.state.embedding_model)
            self.controller.update_setting("embedding.device", self.state.embedding_device)
            self.controller.update_setting("local.vram_recovery_delay_sec", self.state.vram_recovery_delay_sec)
            self.controller.update_setting("local.b4_max_sections", self.state.b4_max_sections)
            self.controller.update_setting("summarisation.b4_threshold_tokens", self.state.b4_threshold_tokens)
        except Exception as _e:
            logger.debug("perf settings save failed: %s: %s", type(_e).__name__, _e)
