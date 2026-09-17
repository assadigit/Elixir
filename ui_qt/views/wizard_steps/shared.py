"""Wizard step-common definitions (V18.20.4.6, P5 / O-b1 split).

``WizardState`` (the whole-wizard choices dataclass) and
``WizardStep`` (the QWidget base every step derives from) moved
here VERBATIM from ui_qt/views/wizard_view.py — byte-identical
bodies; only this module's top-of-file imports differ.
``ui_qt.views.wizard_view`` re-exports both names (facade).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QWidget

from controller import Controller

# ════════════════════════════════════════════════════════════════════════════
# Wizard State
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class WizardState:
    """Holds all choices made during the wizard."""
    # Step 1: PDF
    input_path: str = ""
    source_type: str = "normal_book"
    # Step 2: Range
    page_range_start: int | None = None
    page_range_end: int | None = None
    page_group_size: int = 10
    auto_detect_scanned: bool = True
    # Step 3: OCR
    use_llm_ocr: bool = True
    force_ocr_all_pages: bool = False
    use_paddleocr: bool = False
    ocr_timeout: int = 120
    extract_figure_text: bool = False
    extract_tables: bool = False
    # Step 4: Outputs
    generate_summaries: bool = True
    include_executive_summary: bool = True
    include_thorough_summary: bool = True
    include_keypoints: bool = True
    simplified_keypoints_enabled: bool = True  # V13.34.0: enabled by default
    generate_docx: bool = True  # V13.34.0: enabled by default
    outputs_briefing: bool = False  # V13.34.0: off by default
    outputs_podcast: bool = False  # V13.34.0: off by default
    outputs_flashcards: bool = False  # V13.34.0: off by default
    outputs_packets: bool = False   # V7.3.0: Packets of Knowledge
    outputs_obsidian: bool = False
    outputs_study_guide: bool = False
    outputs_social: bool = False
    outputs_mindmap: bool = False
    outputs_tts: bool = False
    # V10.29.0 (Sprint 2.1): The 6 fields below were accessed via
    # getattr(self, "outputs_X", False) in to_ui_data() but were NOT
    # declared as dataclass fields.  This meant asdict(self.state) (used by
    # _save_profile) silently dropped them → save/load profile lost these
    # 6 outputs every time.  Declaring them here fixes the silent data-loss
    # bug.  All default to False (opt-in), matching ConversionRequest.
    outputs_evidence_map: bool = False   # V10.1.0: Scientific Evidence Map
    outputs_qa: bool = False             # V10.17.0: Q&A study questions
    outputs_glossary: bool = False       # V10.20.0: Glossary
    outputs_patterns: bool = False       # V10.20.0: Patterns/Techniques
    outputs_cheatsheet: bool = False     # V10.20.0: Cheatsheet
    outputs_skill: bool = False          # V10.21.0: Agent Skill (SKILL.md)
    compact_summaries: bool = False      # V10.20.0: Density mode
    _streaming_enabled: bool = False     # V10.21.0: Streaming output display
    # V10.35.0: New outputs
    outputs_epub: bool = False           # V10.35.0: EPUB output
    outputs_quote_bank: bool = False     # V10.35.0: Quote bank
    # Step 5: Models
    summarisation_model: str = ""
    primary_ocr_model: str = ""
    fallback_ocr_model: str = ""
    fast_model: str = ""
    max_workers: int = 1   # V10.1.10: was 2 — VRAM safety default
    temperature: float = 1.0  # V13.34.0: Gemma 4 recommended  # V10.1.10: was 0.2 — fine-tuner minimum for Qwythos/gemma
    # V16.0.9: 4-mode model architecture
    model_architecture: str = "single_local"  # single_local | dual_local | single_api | dual_api
    # Step 6: Translation
    translation_enabled: bool = False
    # V13.31.0 (#13): default backend is now "ollama" (was "nllb").
    # NLLB has been removed from the UI but remains available as a
    # deprecated fallback via direct settings.json edits.
    translation_backend: str = "ollama"
    translation_target_lang: str = "fa"
    translation_harakat_model: str = ""
    translation_judge_model: str = ""
    translation_outputs: dict[str, bool] = field(default_factory=lambda: {
        "chapter_summaries": True,
        "keypoints": True,
        "podcast": True,
    })
    # Step 7: Advanced
    segment_strategy: str = "auto"
    token_limit: int = 2000
    enable_semantic: bool = True
    academic_rigor: bool = False
    # V10.28.0 (Sprint 1): Conservative drop mode — when True, the
    # summariser keeps every bullet except thinking/prompt-leakage ones.
    # All other drops are logged to the quarantine (drops.jsonl) but the
    # bullets stay in the output.  See SPRINT_ROADMAP.md Sprint 1.
    conservative_drops: bool = False
    # Step 7b: Fine-tuning — Post-processing (5)
    clean_markdown: bool = True
    fix_missing_spaces: bool = False
    token_saver: bool = True
    remove_page_number_headings: bool = True
    convert_separators_to_comments: bool = False
    # Step 7b: Fine-tuning — DOCX (2)
    docx_author: str = "MarkItDown Pro"
    docx_include_toc: bool = True
    # Step 7b: Fine-tuning — Quality controls (4)
    self_consistency: bool = False
    heavy_model: str = ""
    coverage_threshold: int = 85  # V13.34.0
    resume_enabled: bool = True   # V7.7.0: skip chapters with valid summaries on disk
    post_completion_action: str = "none"  # V8.1.0: "none"/"quit"/"sleep"/"hibernate"/"shutdown"
    enable_content_filter: bool = True
    # Step 7b: Fine-tuning — Summarization limits (4)
    max_context_tokens: int = 32768  # V13.34.0: 32k local
    max_output_tokens: int = 8192  # V13.34.0
    cache_enabled: bool = False
    simplification_model: str = ""
    # Step 7b: Fine-tuning — Advanced doc handling (2)
    extract_math: bool = False
    layout_analysis: bool = False
    # V18.2.1: Performance & Embeddings (settings-level, not request-level)
    embedding_model: str = "BAAI/bge-small-en-v1.5"   # V18.2.2: default switched MiniLM→bge-small
    embedding_device: str = "auto"              # "auto" | "cuda" | "cpu"
    vram_recovery_delay_sec: int = 0            # 0 = disabled (user undervolted GPU)
    b4_max_sections: int = 6                     # 0 = unlimited (cloud-like)
    b4_threshold_tokens: int = 12000            # chapters above this trigger B4 map-reduce
    # Chapter selection (from Step 2)
    selected_chapters: list[str] | None = None
    # Output
    output_dir: str = ""

    def to_ui_data(self) -> dict[str, Any]:
        """Convert to the dict format expected by Controller.build_request_from_ui."""
        return {
            "input_path": self.input_path,
            "output_dir": self.output_dir or str(Path(self.input_path).parent),
            "source_type": self.source_type,
            "is_academic": self.source_type == "academic_paper",
            "page_range_start": self.page_range_start,
            "page_range_end": self.page_range_end,
            "selected_chapters": self.selected_chapters,
            "page_group_size": self.page_group_size,
            "auto_detect_scanned": self.auto_detect_scanned,
            "use_llm_ocr": self.use_llm_ocr,
            "force_ocr_all_pages": self.force_ocr_all_pages,
            "image_max_size": 1200,
            "extract_tables": self.extract_tables,
            "extract_figure_text": self.extract_figure_text,
            "generate_summaries": self.generate_summaries,
            "summarisation_model": self.summarisation_model,
            "primary_ocr_model": self.primary_ocr_model,
            "fallback_ocr_model": self.fallback_ocr_model,
            "fast_model": self.fast_model,
            "max_workers": self.max_workers,
            "temperature": self.temperature,
            # V16.0.9: 4-mode model architecture (per-conversion override)
            "model_architecture": self.model_architecture,
            "include_executive_summary": self.include_executive_summary,
            "include_thorough_summary": self.include_thorough_summary,
            "include_keypoints": self.include_keypoints,
            "generate_docx": self.generate_docx,
            # V10.24.0: FIXED key names — 'output_X' (no 's') to match
            # ConversionRequest field names. Was 'outputs_X' which caused
            # build_request_from_ui to never find the values → fell back
            # to settings defaults → all opt-in outputs were always False.
            "output_briefing": self.outputs_briefing,
            "output_podcast": self.outputs_podcast,
            "output_flashcards": self.outputs_flashcards,
            "output_packets": self.outputs_packets,
            "output_obsidian": self.outputs_obsidian,
            "output_study_guide": self.outputs_study_guide,
            "output_social": self.outputs_social,
            "output_mindmap": self.outputs_mindmap,
            "output_tts": self.outputs_tts,
            # V10.29.0 (Sprint 2.1): These 8 fields are now declared on the
            # dataclass (they were getattr-only before, which caused silent
            # profile save/load data loss — asdict() skips undeclared attrs).
            "output_qa": self.outputs_qa,
            "output_glossary": self.outputs_glossary,
            "output_patterns": self.outputs_patterns,
            "output_cheatsheet": self.outputs_cheatsheet,
            "output_skill": self.outputs_skill,
            "output_evidence_map": self.outputs_evidence_map,
            "compact_summaries": self.compact_summaries,
            "_streaming_enabled": self._streaming_enabled,
            # V10.35.0: New outputs
            "output_epub": self.outputs_epub,
            "output_quote_bank": self.outputs_quote_bank,
            "segment_strategy": self.segment_strategy,
            "token_limit_per_segment": self.token_limit,
            "enable_semantic_segmentation": self.enable_semantic,
            "academic_rigor": self.academic_rigor,
            "conservative_drops": self.conservative_drops,  # V10.28.0 (Sprint 1)
            "simplified_keypoints_enabled": self.simplified_keypoints_enabled,
            # Step 7b: Fine-tuning — Post-processing
            "clean_markdown": self.clean_markdown,
            "fix_missing_spaces": self.fix_missing_spaces,
            "token_saver": self.token_saver,
            "remove_page_number_headings": self.remove_page_number_headings,
            "convert_separators_to_comments": self.convert_separators_to_comments,
            # Step 7b: Fine-tuning — DOCX
            "docx_author": self.docx_author,
            "docx_include_toc": self.docx_include_toc,
            # Step 7b: Fine-tuning — Quality controls
            "self_consistency": self.self_consistency,
            "heavy_model": self.heavy_model,
            "coverage_threshold": self.coverage_threshold,
            "resume_enabled": self.resume_enabled,
            "enable_content_filter": self.enable_content_filter,
            # Step 7b: Fine-tuning — Summarization limits
            "summarisation_max_context_tokens": self.max_context_tokens,
            "summarisation_max_output_tokens": self.max_output_tokens,
            "summarisation_cache_enabled": self.cache_enabled,
            "simplification_model": self.simplification_model,
            # Step 7b: Fine-tuning — Advanced doc handling
            "extract_math": self.extract_math,
            "layout_analysis": self.layout_analysis,
        }

# ════════════════════════════════════════════════════════════════════════════
# Base Step
# ════════════════════════════════════════════════════════════════════════════

class WizardStep(QWidget):
    """Base class for wizard steps."""

    def __init__(self, controller: Controller, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.state = state
        self._build()

    def _build(self) -> None:
        """Override in subclasses to build the step UI."""
        pass

    def validate(self) -> tuple[bool, str]:
        """Validate the step. Returns (ok, error_message)."""
        return True, ""

    def save_to_state(self) -> None:
        """Save step choices to the wizard state."""
        pass

    def refresh_theme(self) -> None:
        """Refresh theme-dependent styling."""
        pass
