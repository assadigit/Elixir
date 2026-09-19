"""V10.21.0: Nested config dataclasses for ConversionRequest (B2).

Groups the 115 fields of ConversionRequest into logical config objects:
  - OCRConfig: OCR settings (model, retries, force, image size)
  - PostprocessConfig: markdown cleaning, token saver, page number removal
  - SegmentationConfig: strategy, keywords, page groups, token limits
  - SummarizationConfig: model, context/output tokens, temperature, coverage
  - OutputConfig: all output_* flags + docx + compact_summaries
  - QualityConfig: academic rigor, content filter, self-consistency
  - AdvancedConfig: tables, math, layout, figure extraction
  - SelectionConfig: page range, chapter selection, manual segments
  - DocxConfig: author, toc, font

These are view objects built from the flat ConversionRequest fields.
The flat fields remain the source of truth (backward compat — every existing
`request.some_field` access still works).  New code can use the grouped
access pattern for clarity::

    # Old (still works):
    model = request.primary_ocr_model
    # New (grouped):
    model = request.ocr.primary_model

V10.29.0 (Sprint 2.6) correction: the previous docstring said these were
"READ-ONLY view objects", which was misleading — the nested config
dataclasses ARE mutable (they're regular ``@dataclass`` objects without
``frozen=True``), but mutations to them do NOT write back to the underlying
``ConversionRequest``.  So they are effectively read-only *with respect to
the request*, even though the dataclass itself isn't frozen.  This is the
adapter pattern — the nested configs are computed views, not separate
storage.  A true split (moving storage into nested objects) would break all
500+ call sites; this approach gives the structural benefit without the
risk.
"""

from __future__ import annotations

from typing import Any

# V10.22.0 (B2): Writable config adapter — each config object delegates
# __getattr__ + __setattr__ to the ConversionRequest's flat fields.
# This makes the nested configs bidirectional: reads go through to the flat
# fields, writes go through to the flat fields.  No data duplication.
#
# Usage:
#   request.ocr.primary_model           # reads request.primary_ocr_model
#   request.ocr.primary_model = "new"   # writes request.primary_ocr_model
#
# The mapping between nested config attributes and flat ConversionRequest
# fields is defined in _FIELD_MAP below.

# Field mapping: {config_attr: (request_field, config_name)}
_FIELD_MAP = {
    # OCRConfig
    "use_llm_ocr": ("use_llm_ocr", "ocr"),
    "primary_model": ("primary_ocr_model", "ocr"),
    "fallback_model": ("fallback_ocr_model", "ocr"),
    "auto_detect_scanned": ("auto_detect_scanned", "ocr"),
    "force_ocr_all_pages": ("force_ocr_all_pages", "ocr"),
    "image_max_size": ("image_max_size", "ocr"),
    "retries": ("ocr_retries", "ocr"),
    # PostprocessConfig
    "clean_markdown": ("clean_markdown", "postprocess"),
    "fix_missing_spaces": ("fix_missing_spaces", "postprocess"),
    "token_saver": ("token_saver", "postprocess"),
    "remove_page_number_headings": ("remove_page_number_headings", "postprocess"),
    "convert_separators_to_comments": ("convert_separators_to_comments", "postprocess"),
    # SegmentationConfig
    "strategy": ("segment_strategy", "segmentation"),
    "custom_keywords": ("custom_keywords", "segmentation"),
    "custom_regex_patterns": ("custom_regex_patterns", "segmentation"),
    "page_group_size": ("page_group_size", "segmentation"),
    "chunk_by_page_groups": ("chunk_by_page_groups", "segmentation"),
    "token_limit_per_segment": ("token_limit_per_segment", "segmentation"),
    "enable_semantic": ("enable_semantic_segmentation", "segmentation"),
    # SummarizationConfig
    "enabled": ("generate_summaries", "summarization"),
    "model": ("summarisation_model", "summarization"),
    "max_context_tokens": ("summarisation_max_context_tokens", "summarization"),
    "max_output_tokens": ("summarisation_max_output_tokens", "summarization"),
    "cache_enabled": ("summarisation_cache_enabled", "summarization"),
    "temperature": ("temperature", "summarization"),
    "self_consistency": ("self_consistency", "summarization"),
    "fast_model": ("fast_model", "summarization"),
    "heavy_model": ("heavy_model", "summarization"),
    "coverage_threshold": ("coverage_threshold", "summarization"),
    "simplification_model": ("simplification_model", "summarization"),
    "max_workers": ("max_workers", "summarization"),
    # OutputConfig — all output_* fields map directly
    "generate_summaries": ("generate_summaries", "outputs"),
    "include_executive_summary": ("include_executive_summary", "outputs"),
    "include_thorough_summary": ("include_thorough_summary", "outputs"),
    "include_keypoints": ("include_keypoints", "outputs"),
    "generate_docx": ("generate_docx", "outputs"),
    "output_briefing": ("output_briefing", "outputs"),
    "output_podcast": ("output_podcast", "outputs"),
    "output_flashcards": ("output_flashcards", "outputs"),
    "output_packets": ("output_packets", "outputs"),
    "output_obsidian": ("output_obsidian", "outputs"),
    "output_study_guide": ("output_study_guide", "outputs"),
    "output_social": ("output_social", "outputs"),
    "output_mindmap": ("output_mindmap", "outputs"),
    "output_tts": ("output_tts", "outputs"),
    "output_evidence_map": ("output_evidence_map", "outputs"),
    "output_qa": ("output_qa", "outputs"),
    "output_glossary": ("output_glossary", "outputs"),
    "output_patterns": ("output_patterns", "outputs"),
    "output_cheatsheet": ("output_cheatsheet", "outputs"),
    "compact_summaries": ("compact_summaries", "outputs"),
    "simplified_keypoints_enabled": ("simplified_keypoints_enabled", "outputs"),
    # QualityConfig
    "academic_rigor": ("academic_rigor", "quality"),
    "enable_content_filter": ("enable_content_filter", "quality"),
    "source_type": ("source_type", "quality"),
    # AdvancedConfig
    "extract_tables": ("extract_tables", "advanced"),
    "extract_math": ("extract_math", "advanced"),
    "layout_analysis": ("layout_analysis", "advanced"),
    "table_extraction_method": ("table_extraction_method", "advanced"),
    "math_model": ("math_model", "advanced"),
    "extract_figure_text": ("extract_figure_text", "advanced"),
    # SelectionConfig
    "page_range_start": ("page_range_start", "selection"),
    "page_range_end": ("page_range_end", "selection"),
    "selected_chapters": ("selected_chapters", "selection"),
    "manual_segments": ("manual_segments", "selection"),
    # DocxConfig
    "author": ("docx_author", "docx"),
    "include_toc": ("docx_include_toc", "docx"),
    "font": ("docx_font", "docx"),
}

# Reverse map: {config_name: {request_field: config_attr}}
_CONFIG_FIELD_MAP = {}
for _attr, (_req_field, _config_name) in _FIELD_MAP.items():
    if _config_name not in _CONFIG_FIELD_MAP:
        _CONFIG_FIELD_MAP[_config_name] = {}
    _CONFIG_FIELD_MAP[_config_name][_req_field] = _attr


class _WritableConfig:
    """Bidirectional adapter — reads/writes delegate to the ConversionRequest.

    This is NOT a dataclass — it's a lightweight proxy that maps
    nested-style attribute names to flat ConversionRequest field names.
    """

    def __init__(self, request: Any, config_name: str) -> None:
        object.__setattr__(self, "_request", request)
        object.__setattr__(self, "_config_name", config_name)
        object.__setattr__(self, "_field_map", _CONFIG_FIELD_MAP.get(config_name, {}))

    def __getattr__(self, name: str) -> Any:
        field_map = object.__getattribute__(self, "_field_map")
        # field_map is {request_field: config_attr}
        # We need to find the request_field where config_attr == name
        for req_f, config_a in field_map.items():
            if config_a == name:
                request = object.__getattribute__(self, "_request")
                return getattr(request, req_f)
        # V10.31.0 (Sprint 4.7): use .format() instead of nested-quote f-string
        # (the old f"'{...self, "_config_name"...}'" used Python 3.12+ nested
        # double-quotes inside an f-string, which breaks on 3.11 and earlier).
        cfg_name = object.__getattribute__(self, "_config_name")
        raise AttributeError(f"'{cfg_name}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        field_map = object.__getattribute__(self, "_field_map")
        for req_f, config_a in field_map.items():
            if config_a == name:
                request = object.__getattribute__(self, "_request")
                setattr(request, req_f, value)
                return
        raise AttributeError(f"Cannot set '{name}' on '{self._config_name}'")

    def __repr__(self) -> str:
        field_map = object.__getattribute__(self, "_field_map")
        request = object.__getattribute__(self, "_request")
        attrs = {config_a: getattr(request, req_f) for req_f, config_a in field_map.items()}
        return f"{self._config_name}({attrs})"


# Config classes are now thin wrappers around _WritableConfig
class OCRConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "ocr")


class PostprocessConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "postprocess")


class SegmentationConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "segmentation")


class SummarizationConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "summarization")


class OutputConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "outputs")


class QualityConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "quality")


class AdvancedConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "advanced")


class SelectionConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "selection")


class DocxConfig(_WritableConfig):
    def __init__(self, request):
        super().__init__(request, "docx")


def build_config_views(request: Any) -> dict[str, Any]:
    """Build all config view objects from a ConversionRequest.

    V10.22.0 (B2): Config views are now WRITABLE — changes to nested
    config attributes propagate back to the flat ConversionRequest fields.
    This enables true bidirectional access::

        request.ocr.primary_model = "new-model"  # writes request.primary_ocr_model
        print(request.primary_ocr_model)          # reads "new-model"
    """
    return {
        "ocr": OCRConfig(request),
        "postprocess": PostprocessConfig(request),
        "segmentation": SegmentationConfig(request),
        "summarization": SummarizationConfig(request),
        "outputs": OutputConfig(request),
        "quality": QualityConfig(request),
        "advanced": AdvancedConfig(request),
        "selection": SelectionConfig(request),
        "docx": DocxConfig(request),
    }
