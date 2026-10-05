"""Core data classes, enums, and type definitions for the entire application."""

# ── Enums ─────────────────────────────────────────────────────────────────────
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

# V18.20.4.11 (P2 / W-a7 partial): single source of truth for the legacy
# default-model literals (de-duplication only — values byte-identical to
# the previous inline literals). model_taxonomy is a leaf module (imports
# only ``re``); core.llm's package init pulls model_manager → utils only,
# so there is no import cycle with this module.
from core.llm.model_taxonomy import (
    DEFAULT_FALLBACK_OCR_MODEL,
    LEGACY_DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)


class OcrEngine(StrEnum):
    """Which OCR engine was used for a page."""

    QWEN_VL = "qwen3-vl"
    TESSERACT = "tesseract"
    MARKITDOWN = "markitdown"
    NONE = "none"


class PdfRecommendation(StrEnum):
    """Recommended strategy after PDF analysis."""

    LLM_OCR = "llm_ocr"  # Use Qwen3-VL for all pages
    NO_OCR = "no_ocr"  # Use extracted text directly
    HYBRID = "hybrid"  # OCR only on scanned pages


class SegmentStrategy(StrEnum):
    """Strategy used to split document into segments."""

    AUTO = "auto"  # Automatically choose best
    HEADING = "heading"  # Markdown headings or Persian patterns
    KEYWORD = "keyword"  # User-defined keywords/regex
    SEMANTIC = "semantic"  # LLM-based boundary detection
    TOKEN = "token"  # Split by token count


# ── Analysis & OCR ────────────────────────────────────────────────────────────


@dataclass
class PageAnalysis:
    """Analysis result for a single PDF page."""

    page_num: int
    is_scanned: bool
    extracted_text_preview: str
    recommended_action: str


@dataclass
class PdfAnalysisResult:
    """Overall PDF analysis."""

    total_pages: int
    scanned_pages: list[int]
    text_pages: list[int]
    recommendation: PdfRecommendation
    per_page: list[PageAnalysis]


@dataclass
class OcrResult:
    """Result of OCR on a single page."""

    page_num: int
    text: str
    success: bool
    engine_used: OcrEngine
    error_msg: str = ""


# ── Segmentation ──────────────────────────────────────────────────────────────


@dataclass
class Segment:
    """A generic segment (chapter or page-group chunk)."""

    heading: str
    content: str
    start_page: int
    end_page: int
    segment_type: str = "chapter"  # "chapter", "chunk", or "gap"
    original_markdown: str | None = None
    # V18.3.3 (F1): aliases — headings of segments that were MERGED into this
    # one by _merge_short_segments. Preserves the lost headings so the chapter
    # matcher can still find them. E.g. if "Dedication" was merged into
    # "Title Page", the segment has heading="Title Page" + aliases=["Dedication"].
    # The matcher checks both heading AND aliases when matching user selections.
    aliases: list = None  # type: ignore  # populated by _merge_short_segments

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []

    @property
    def all_headings(self) -> list:
        """V18.3.3: the heading + all aliases — every name this segment is known by."""
        return [self.heading] + (self.aliases or [])

    @property
    def is_gap(self) -> bool:
        """V18.3.3 (F5): True if this is a gap segment (no real content, not matchable)."""
        return self.segment_type == "gap" or self.heading.startswith("Gap (")


# ── Summarisation ─────────────────────────────────────────────────────────────


@dataclass
class SummaryResult:
    """Two-level summary for a segment."""

    chapter_heading: str
    executive_summary: str
    thorough_summary: str
    bullet_points: list[str] = field(default_factory=list)
    success: bool = True
    error_msg: str = ""
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    # V13.38.0: Additive sections — anti-hallucination-verified distinctions + tensions
    key_distinctions: str = ""
    theoretical_tensions: str = ""
    # V13.41.0: Scholar reflections — meta-cognitive gap analysis
    scholar_reflections: str = ""
    # V0.03 (P0-2): Tier-3 coverage excerpts — complete-sentence, framed
    # verbatim source quotes recorded when a keyword is missing from the
    # whole summary. NEVER part of bullet_points (Key Takeaways); rendered
    # as a separate clearly-labelled section. Empty = none recorded.
    source_excerpts: list[str] = field(default_factory=list)
    # V0.03 (P1-6): quarantine appendix — rendered record of bullets the
    # quality pipeline dropped or kept-with-concerns for this chapter
    # (stage + reason + excerpt). Empty = nothing quarantined.
    quarantine_appendix: str = ""
    # V18.20.3.5: deterministic recall-floor numbers measured on the FINAL
    # set (see core/summarisation/recall_floor.py). Consumed by the quality
    # report and the end-of-conversion diagnostic so they print real
    # numbers instead of "?".
    recall_floor: dict | None = None
    # V18.20.3.7: output provenance — which conversion produced this
    # summary. Stamped by the Summarizer (one run_id per conversion) and
    # rendered into every output file by render_summary_markdown /
    # complete_sentinel (see core/system/provenance.py). Empty strings =
    # legacy/unstamped (tests, pre-.3.7 files parsed by chapter_resume).
    run_id: str = ""
    app_version: str = ""
    run_started: str = ""
    # V0.06 (rig audit F1-c — GENERAL RULE: the output selection is the
    # CONTRACT, enforced at render time too): the user's output-selection
    # flags, stamped by the Summarizer when the result is built. Renderers
    # (chapter markdown, DOCX, book summary) skip a section whose flag is
    # False EVEN IF content leaked into it — the V0.05 rig shipped a
    # "Thorough Summary" section to a user who unchecked it because every
    # gate was generation-side only and the parser's leftover fallback
    # smuggled additive-section content into the field. Defaults True =
    # legacy/unstamped results render exactly as before.
    include_executive_summary: bool = True
    include_thorough_summary: bool = True
    include_keypoints: bool = True
    # V0.5.4 (Track C1 — section breaks mirroring the source): the
    # runtime-extracted author→ALL-CAPS-section map for THIS chapter's
    # source text. Populated by the Summarizer from
    # ``deterministic_analyzer.map_authors_to_all_caps_sections``. When
    # non-empty AND bullet_points is non-empty, the markdown renderer
    # groups the key-takeaway bullets under ``## {Section Title}``
    # headings (one per source section whose authors appear in any
    # bullet). Empty = legacy flat list under ``## Key Takeaways``
    # (backward-compatible: every existing test fixture and legacy
    # SummaryResult renders byte-identical to before).
    source_section_map: list = field(default_factory=list)
    # V0.5.4 (Track B3 — Table N-N reproduction): the runtime-extracted
    # explicit ``TABLE N-N.`` tables from the chapter source. Populated
    # by the Summarizer from
    # ``deterministic_analyzer.extract_structured_tables``. The markdown
    # renderer reproduces each table's ``content_lines`` verbatim under a
    # clearly-labelled ``## Reproduced Tables (from source)`` section.
    # Empty list = no reproduced-tables section (legacy behavior).
    reproduced_tables: list = field(default_factory=list)
    # V0.5.4 (Track B4 — DSM-style criteria reproduction): the runtime-
    # extracted ``a. b. c. d.`` + ``(i) (ii) (iii)`` criteria clusters
    # from the chapter source. Populated by the Summarizer from
    # ``deterministic_analyzer.extract_structured_criteria``. The
    # markdown renderer reproduces each cluster as a nested bullet list
    # under a clearly-labelled ``## Reproduced Diagnostic Criteria (from
    # source)`` section. Empty list = no criteria section (legacy
    # behavior).
    reproduced_criteria: list = field(default_factory=list)
    # V0.5.6 (Phase 0.5 — source glossary): the runtime-extracted source
    # roster parsed from the master-summary LLM call's ``<name_glossary>``
    # block (3 subsections — names, dates, terms). Populated by the
    # Summarizer from ``glossary_parser.parse_name_glossary`` on the
    # Call 1/3 master-summary raw response. Persisted as
    # ``summaries/.glossaries/<slug>.glossary.md`` (auditable — Rule 4
    # provenance). Consumed by the verification LAYER as the coverage
    # ground truth (richer than the regex ``extract_citations`` — the
    # LLM also catches multi-word surnames + provides a 1-sentence
    # context per name). The deterministic ``cross_reference_glossary``
    # backstop keeps the LLM honest (every glossary name is checked
    # against the regex output). Empty dict = the LLM didn't emit a
    # ``<name_glossary>`` block (fail-open — never blocks the master
    # summary; the verification LAYER falls back to the regex).
    source_glossary: dict = field(default_factory=dict)


# ── Conversion Request / Result ───────────────────────────────────────────────


@dataclass
class ConversionRequest:
    """All parameters needed to run a conversion."""

    input_path: Path
    output_dir: Path
    password: str | None = None

    # PDF analysis override
    override_recommendation: PdfRecommendation | None = None

    # OCR settings
    use_llm_ocr: bool = True
    # V18.20.4.11 (P2): literals → core.llm.model_taxonomy constants
    # (values unchanged: "qwen3-vl:8b").
    primary_ocr_model: str = DEFAULT_FALLBACK_OCR_MODEL
    fallback_ocr_model: str = DEFAULT_FALLBACK_OCR_MODEL
    auto_detect_scanned: bool = True
    force_ocr_all_pages: bool = False
    image_max_size: int = 1200
    ocr_retries: int = 2

    # Post-processing
    clean_markdown: bool = True
    fix_missing_spaces: bool = False
    token_saver: bool = True
    remove_page_number_headings: bool = True
    convert_separators_to_comments: bool = False

    # Segmentation
    segment_strategy: str | SegmentStrategy = "auto"
    custom_keywords: list[str] = field(default_factory=list)
    custom_regex_patterns: list[str] = field(default_factory=list)
    page_group_size: int = 10
    chunk_by_page_groups: bool = True
    token_limit_per_segment: int = 1200
    enable_semantic_segmentation: bool = True

    # Summarisation
    generate_summaries: bool = False
    # V18.20.4.11 (P2): literal → core.llm.model_taxonomy constant
    # (value unchanged: "gemma3:12b" — the LEGACY sentinel default).
    summarisation_model: str = LEGACY_DEFAULT_MODEL
    summarisation_max_context_tokens: int = (
        131072  # V10.12.6: raised 16k → 64k (RTX 3060 12GB can handle 64k for 9B Q4)
    )
    summarisation_max_output_tokens: int = 4096  # increased default
    summarisation_cache_enabled: bool = False

    # DOCX
    generate_docx: bool = False
    docx_author: str = "Elixir"
    docx_include_toc: bool = True
    docx_font: str = "Helvetica"

    # Performance
    max_workers: int = 2  # NEW: parallel summarisation workers

    # ── Pre-flight VRAM acknowledgment (V18.20.4.10 / P0-c) ────────────────
    # Set to True ONLY by an interactive user action (the wizard's
    # "Proceed anyway" button on the VRAM-overbudget dialog). The converter
    # enforces ``local.vram_overbudget_policy`` (enforcement restored
    # V0.6.9): an overbudget plan without this acknowledgment fails fast —
    # the converter returns the policy's error message as a failed
    # ConversionResult (the VramOverbudgetError class exists for callers
    # that prefer exceptions) instead of warn-and-continue.
    vram_overbudget_acknowledged: bool = False

    # ── Manual segmentation override ──────────────────────────────────────
    manual_segments: list[tuple[int, int]] | None = None

    # ── Quality Controls ──────────────────────────────────────────────────
    temperature: float = 0.2
    self_consistency: bool = False
    # V0.6.14 (single-model order): the whole fast/heavy dual-model family
    # is REMOVED — fast_model (incl. the shadowed LEGACY_DEFAULT_MODEL
    # declaration), heavy_model, model_architecture (the 4-mode selector),
    # fast_model_temperature, fast_model_context, fast_api_url/key/model,
    # and simplification_model below. ONE model (summarisation_model,
    # reached through the provider) does every LLM generation task; OCR /
    # transcribe / translation / TTS keep their own dedicated models.
    coverage_threshold: float = 0.50  # lowered to 50%
    # V15.1.0: Over-delivery — keep improving coverage past the minimum threshold
    overdeliver_enabled: bool = True  # default ON
    overdeliver_target: float = 1.0  # V15.1.1: 100% (the more the better)
    b3_voting_enabled: bool = False  # V15.1.1: disabled (damages depth)

    # ── Page range selection ──────────────────────────────────────────────
    page_range_start: int | None = None
    page_range_end: int | None = None

    # ── Chapter selection (list of chapter titles to include) ────────────
    selected_chapters: list[str] | None = None

    # ── Advanced document handling ────────────────────────────────────────
    extract_tables: bool = False
    extract_math: bool = False
    layout_analysis: bool = False
    table_extraction_method: str = "camelot"  # or "tabula"
    math_model: str = "pix2tex"  # or "latex-ocr"

    # ── Source Type & Quick Mode ──────────────────────────────────────────
    # V3.10.0: Expanded source types for content-type presets
    # "normal_book" — non-fiction (default)
    # "academic_paper" — formal academic with citations, section numbering
    # "self_help" — motivational, action-oriented, exercises
    # "philosophy" — dense, abstract, long paragraphs, preserve nuance
    # "catalogue" — product listings, skip summarization
    source_type: str = "normal_book"
    include_executive_summary: bool = True
    include_thorough_summary: bool = True
    include_keypoints: bool = True

    # ── Content Filter toggle ─────────────────────────────────────────────
    enable_content_filter: bool = True

    # ── Academic Rigor flag ───────────────────────────────────────────────
    academic_rigor: bool = False

    # ── Simplified Keypoints Digest (Sprint 2) ────────────────────────────
    simplified_keypoints_enabled: bool = False

    # ── V10.28.0 (Sprint 1): Conservative drop mode ──────────────────────
    # When True, the summariser disables every bullet-drop site EXCEPT the
    # thinking-process / prompt-leakage filter (_filter_thinking_bullets'
    # THINKING_STARTS / BACKTICK_WORDS / INTERNAL_MARKERS / PROMPT_LEAKAGE
    # checks).  Specifically:
    #   - F4 source-overlap drop        → disabled (logged to quarantine only)
    #   - Phase 2.2 semantic fact-check → disabled (logged to quarantine only)
    #   - B3 multi-sample dedup merge   → disabled (duplicates kept)
    #   - Content Judge grounding drop  → disabled (logged to quarantine only)
    #   - Quality scorer threshold drop → disabled (all bullets kept)
    # This guarantees that in Conservative mode the output bullet count is
    # ≥ the raw LLM output count (zero drops except thinking-filter), which
    # is the Sprint 1 exit criterion.  Every drop that *would have* happened
    # is still recorded in the quarantine log so the user can audit it.
    conservative_drops: bool = False

    # ── Sprint 3 – Vision OCR for Figures ────────────────────────────────
    extract_figure_text: bool = False

    # ── V0.4.3 – Vision-Region Cropper (default ON) ───────────────────────
    # When True, the pipeline runs core/pdf/vision_region_cropper.py after
    # the existing figure_table_cropper. Layer A (vector-graphics clustering)
    # always runs; Layer B (VLM region detection) auto-enables when a vision
    # model is available (reuses V0.4.1's vision probe). Crops are saved to
    # regions/ and embedded inline in the chapter markdown at the page
    # markers. Content-agnostic — works on any PDF. See
    # docs/FEASIBILITY_vision_crop.md for the full design.
    extract_visual_regions: bool = True

    # ── V4.1.0: Output Studio — opt-in output types ─────────────────────
    # Each flag gates one optional output generator in core/outputs/.
    # Defaults are False at the model level; the settings layer
    # (build_request_from_ui) supplies sensible per-output defaults so the
    # 3 V4.0.0 outputs stay on by default and the 4 new ones are opt-in.
    output_briefing: bool = False  # B3: one-page synthesis (.Briefing.md)
    output_podcast: bool = False  # B1: 2-host conversational script (.Podcast.md)
    output_flashcards: bool = False  # B2: Anki TSV + readable MD (.Flashcards.*)
    output_packets: bool = False  # V7.3.0: Packets of Knowledge (clusters + synthesis)
    output_obsidian: bool = False  # V4.1: Obsidian KB — MD + YAML + wikilinks
    output_study_guide: bool = False  # V4.1: structured study guide (.StudyGuide.md)
    output_social: bool = False  # V4.1: social media pack (.Social.md)
    output_mindmap: bool = False  # V4.1: Mermaid mindmap + MD outline (.MindMap.md)
    output_tts: bool = False  # V4.2: podcast audio via TTS (.Podcast.wav)
    output_evidence_map: bool = False  # V10.1.0: Scientific Evidence Map (langextract)
    output_qa: bool = False  # V10.17.0: Q&A study questions
    output_glossary: bool = False  # V10.20.0: Glossary
    output_patterns: bool = False  # V10.20.0: Patterns/Techniques
    output_cheatsheet: bool = False  # V10.20.0: Cheatsheet
    output_skill: bool = False  # V10.21.0: Agent Skill (SKILL.md)
    compact_summaries: bool = False  # V10.20.0: Density mode (~1000 tokens/chapter)
    # V10.35.0 (Sprint 8/9): New outputs
    output_epub: bool = False  # V10.35.0: EPUB output (annotated)
    output_quote_bank: bool = False  # V10.35.0: Quote bank

    @property
    def layout_reorder_enabled(self) -> bool:
        return self.source_type == "academic_paper"

    def get_segment_strategy_enum(self) -> SegmentStrategy:
        if isinstance(self.segment_strategy, SegmentStrategy):
            return self.segment_strategy
        try:
            return SegmentStrategy(self.segment_strategy)
        except ValueError:
            return SegmentStrategy.AUTO


@dataclass
class ConversionResult:
    """Result of a conversion operation."""

    success: bool
    error_msg: str = ""
    full_markdown_path: Path | None = None
    chapters_folder: Path | None = None
    chunks_folder: Path | None = None
    docx_path: Path | None = None
    # V18.20.3.6: pages THIS conversion actually covered — the selected-
    # chapter / page-range page count when a selection was active, else the
    # document's total.  (Was always the whole-PDF total, so a single
    # 18-page chapter of a 397-page book reported "Pages processed: 397".)
    pages_processed: int = 0
    chapters_detected: int = 0
    chunks_created: int = 0
    summaries_generated: int = 0
    segments: list[Segment] = field(default_factory=list)
    summaries: list[SummaryResult] = field(default_factory=list)
    log_file_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


# ── Callback type aliases ──────────────────────────────────────────────────────

ProgressCallback = Callable[[float], None]
StatusCallback = Callable[[str], None]
LogCallback = Callable[[str, str], None]
