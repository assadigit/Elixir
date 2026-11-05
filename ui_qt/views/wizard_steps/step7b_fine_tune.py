"""Step 7b: Fine-tuning — post-processing, DOCX, quality, advanced doc — Step7bFineTune (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step7bFineTune
(back-compat facade).

V0.7.3 (wizard rework ⑤, D12): the duplicate "Summarization limits"
group is DELETED — Step 5 is the single owner of the model context /
output limits (its save-order overwrite here silently beat Step 5's
values at Start; audit §W12). The summary-cache checkbox relocated
into Quality controls.

V0.7.5 (wizard rework ⑦, 7b / D10): the self-consistency checkbox is
REMOVED from this step — it silently no-op'd unless the provider was
Ollama (bullet_pipeline.py:992) and the "vote" is a union-merge, not a
majority vote (~3-4× cost; audit §W12). The backend stays; the
Settings → AI-quality page carries the only UI control with truthful
copy; a WARNING log line fires when it is requested on an unsupported
provider. 7c (same release) reworks the coverage line below.
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
    QPushButton,
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
# Step 7b: Fine-tuning — post-processing, DOCX, quality, advanced doc
# (V0.7.3, D12: the Summarization limits group moved to Step 5)
# ════════════════════════════════════════════════════════════════════════════


class Step7bFineTune(WizardStep):
    """Fine-tuning: post-processing, DOCX, quality, advanced doc."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    # V0.7.3 (D12): "limits" dropped from the caption — Step 5 owns them.
    STEP_HEADER = (8, "Fine-tuning", "Quality, caching, and post-processing knobs.")

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        subtitle = QLabel(
            "All settings below use sensible defaults. Change them only if you need specific control."
        )
        subtitle.setObjectName("Caption")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        # ── V0.7.5 (wizard rework ⑦, 7d / W12): the recommended-defaults
        # banner-button (the Step-1 detector-banner precedent): one click
        # applies the post-rework audited defaults to THIS step's controls.
        # The honest trio it stands for: the coverage loop is on by design
        # (85, regenerate to measured ±3, max 3 rounds — 7c); self-
        # consistency stays OFF by default (Settings → AI quality; the
        # wizard never writes it — 7b); model limits live on Step 5
        # (Auto by default — V0.7.3's single-owner rule). The wizard never
        # writes settings-owned keys from here (the B5-class overwrite).
        rec_row = QHBoxLayout()
        rec_row.setSpacing(8)
        self.recommended_btn = QPushButton("Use recommended settings")
        self.recommended_btn.setObjectName("Compact")
        self.recommended_btn.clicked.connect(self._apply_recommended)
        self.recommended_btn.setToolTip(
            "Applies the audited defaults to this step's controls:\n"
            "• Coverage target 85 (the loop is always on: regenerate to\n"
            "  measured ±3, max 3 rounds)\n"
            "• Resume on · cache off · content filter on\n"
            "• Post-processing: clean markdown + page-heading removal on;\n"
            "  the rest off. DOCX TOC on, author Elixir.\n"
            "• Embedding/perf at their audited defaults.\n\n"
            "Self-consistency stays OFF by default (Settings → AI quality;\n"
            "Ollama-only) — the wizard never writes it. Model limits live\n"
            "on Step 5 (Auto by default)."
        )
        rec_row.addWidget(self.recommended_btn)
        self.recommended_caption = QLabel(
            "Coverage 85 · resume on · cache off — the audited defaults for this step."
        )
        self.recommended_caption.setObjectName("Caption")
        self.recommended_caption.setWordWrap(True)
        rec_row.addWidget(self.recommended_caption, 1)
        lay.addLayout(rec_row)

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

        # ── Quality controls (4) ────────────────────────────────────────────
        # V0.7.5 (wizard rework ⑦, 7b / D10): the self-consistency checkbox
        # is REMOVED from the wizard — it silently no-ops unless the
        # provider is Ollama (bullet_pipeline.py:992) and the merge is a
        # union, not a majority vote (~3-4× cost). The backend stays; the
        # Settings → AI-quality page is the only UI writer (default off);
        # a log line now fires when it is requested on an unsupported
        # provider (no more silent no-op).
        q_box = QGroupBox("Quality controls")
        q_lay = QVBoxLayout(q_box)
        q_lay.setContentsMargins(10, 10, 10, 8)
        q_lay.setSpacing(5)
        self.filter_cb = QCheckBox("Content filter (filter out headers/footers/non-content)")
        self.filter_cb.setChecked(self.state.enable_content_filter)
        q_lay.addWidget(self.filter_cb)
        # V0.6.14 (single-model order): the heavy-model picker is retired.
        # Coverage threshold
        # V0.7.5 (wizard rework ⑦, 7c / D11): the label stops overstating
        # ("reprompt trigger" — the audit §W12 finding) and now tells the
        # truth about the close-the-loop: the summaries are regenerated
        # until MEASURED coverage reaches this level, ±3 for model
        # randomness, max 3 rounds (core/summarisation/coverage_loop.py).
        cov_row = QHBoxLayout()
        cov_row.setSpacing(8)
        self.coverage_spin = QSpinBox()
        self.coverage_spin.setRange(0, 100)
        self.coverage_spin.setSuffix("%")
        self.coverage_spin.setValue(self.state.coverage_threshold)
        self.coverage_spin.setToolTip(
            "The summaries are regenerated (targeted gap-fill, up to 3 rounds)\n"
            "until MEASURED coverage reaches this level — ±3 points for model\n"
            "randomness. Chapters that end below target report what was\n"
            "reached and what is still missing (the honest terminal report)."
        )
        cov_row.addWidget(QLabel("Coverage target:"))
        cov_row.addWidget(self.coverage_spin)
        cov_row.addStretch()
        q_lay.addLayout(cov_row)
        self.coverage_caption = QLabel(
            "Regenerates until measured coverage reaches this level — "
            "±3 for model randomness, max 3 rounds."
        )
        self.coverage_caption.setObjectName("Caption")
        self.coverage_caption.setWordWrap(True)
        q_lay.addWidget(self.coverage_caption)

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

        # V0.7.3 (wizard rework ⑤, D12): the cache checkbox moved here from
        # the deleted "Summarization limits" group — Step 5 owns the context
        # /output limits now (single owner; the old group's save-order
        # overwrite, audit §W12, is gone). Summary caching is a re-run
        # behavior, so it lives beside Resume mode.
        self.cache_cb = QCheckBox("Cache summaries to disk (faster re-runs)")
        self.cache_cb.setChecked(self.state.cache_enabled)
        self.cache_cb.setToolTip(
            "Store each chapter's summaries on disk. Re-runs skip chapters "
            "whose cached summaries are still fresh — combined with Resume "
            "mode, a re-run only pays for the chapters that changed."
        )
        q_lay.addWidget(self.cache_cb)

        host_lay.addWidget(q_box)

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
        perf_lay.addWidget(
            QLabel("Embedding model (used for hallucination detection, dedup, validation):")
        )
        emb_row = QHBoxLayout()
        emb_row.setSpacing(8)
        self.embed_combo = QComboBox()
        self.embed_combo.addItem(
            # V0.7.2 (wizard rework ④, D9): the 🦙 emoji prefix is gone —
            # plain combo text (combo items carry no icons).
            "nomic-embed-text (274 MB — via Ollama, just `ollama pull nomic-embed-text`)",
            "nomic-embed-text",
        )
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
        perf_lay.addWidget(QLabel("VRAM recovery delay (thermal management — 0 = disabled):"))
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
        self.thermal_slider.valueChanged.connect(lambda v: self.thermal_label.setText(f"{v}s"))
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

    # ── V0.7.5 (rework ⑦, 7d): the audited-defaults applier ──────────────

    _RECOMMENDED = {
        # The audited post-rework defaults (the WizardState dataclass
        # defaults + the unified coverage 85). Pinned by
        # tests/test_v0750_steps7_7b.py::TestFineTuneRecommended.
        "clean": True,
        "spaces": False,
        "saver": True,
        "pagehead": True,
        "separators": False,
        "docx_author": "Elixir",
        "docx_toc": True,
        "coverage": 85,
        "resume": True,
        "cache": False,
        "filter": True,
        "math": False,
        "layout": False,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_device": "auto",
        "vram_recovery": 0,
        "b4_sections": 6,
        "b4_threshold": 12000,
    }

    def _apply_recommended(self) -> None:
        """Apply the audited defaults to this step's controls (7d).

        The honest trio the button stands for: the coverage loop is on by
        design (85, ±3, max 3 rounds); self-consistency stays OFF by
        default (Settings → AI quality — the wizard never writes it);
        model limits live on Step 5 (Auto by default). This method only
        touches THIS step's controls — no settings-owned keys, no
        cross-step writes (the B5-class overwrite is the cautionary tale).
        """
        r = self._RECOMMENDED
        self.clean_cb.setChecked(r["clean"])
        self.spaces_cb.setChecked(r["spaces"])
        self.token_saver_cb.setChecked(r["saver"])
        self.pagehead_cb.setChecked(r["pagehead"])
        self.separators_cb.setChecked(r["separators"])
        self.author_edit.setText(r["docx_author"])
        self.toc_cb.setChecked(r["docx_toc"])
        self.coverage_spin.setValue(r["coverage"])
        self.resume_cb.setChecked(r["resume"])
        self.cache_cb.setChecked(r["cache"])
        self.filter_cb.setChecked(r["filter"])
        self.math_cb.setChecked(r["math"])
        self.layout_cb.setChecked(r["layout"])
        # Embedding: select the audited model (add it as a custom entry if
        # the combo doesn't list it — the D14 add-missing pattern).
        _idx = self.embed_combo.findData(r["embedding_model"])
        if _idx < 0:
            self.embed_combo.addItem(r["embedding_model"], r["embedding_model"])
            _idx = self.embed_combo.findData(r["embedding_model"])
        if _idx >= 0:
            self.embed_combo.setCurrentIndex(_idx)
        _dev_idx = self.embed_dev_combo.findData(r["embedding_device"])
        if _dev_idx >= 0:
            self.embed_dev_combo.setCurrentIndex(_dev_idx)
        self.thermal_slider.setValue(r["vram_recovery"])
        self.b4_sections_spin.setValue(r["b4_sections"])
        self.b4_threshold_spin.setValue(r["b4_threshold"])

    def save_to_state(self) -> None:
        self.state.clean_markdown = self.clean_cb.isChecked()
        self.state.fix_missing_spaces = self.spaces_cb.isChecked()
        self.state.token_saver = self.token_saver_cb.isChecked()
        self.state.remove_page_number_headings = self.pagehead_cb.isChecked()
        self.state.convert_separators_to_comments = self.separators_cb.isChecked()
        self.state.docx_author = self.author_edit.text().strip()
        self.state.docx_include_toc = self.toc_cb.isChecked()
        # V0.7.5 (rework ⑦, 7b / D10): self_consistency is NO LONGER written
        # here — the checkbox is gone from the wizard. The backend stays;
        # the Settings page is the only UI writer; the request builder
        # resolves it from settings when the wizard path doesn't carry it.
        self.state.coverage_threshold = self.coverage_spin.value()
        self.state.resume_enabled = self.resume_cb.isChecked()
        self.state.enable_content_filter = self.filter_cb.isChecked()
        # V0.7.3 (wizard rework ⑤, D12): max_context_tokens / max_output
        # tokens are NO LONGER written here — Step 5 is the single owner
        # (this used to overwrite Step 5's values by save order at Start;
        # audit §W12). Only the cache flag (relocated into Quality
        # controls) still rounds through this step.
        self.state.cache_enabled = self.cache_cb.isChecked()
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
            self.controller.update_setting(
                "local.vram_recovery_delay_sec", self.state.vram_recovery_delay_sec
            )
            self.controller.update_setting("local.b4_max_sections", self.state.b4_max_sections)
            self.controller.update_setting(
                "summarisation.b4_threshold_tokens", self.state.b4_threshold_tokens
            )
        except Exception as _e:
            logger.debug("perf settings save failed: %s: %s", type(_e).__name__, _e)
