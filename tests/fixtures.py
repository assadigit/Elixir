"""Test fixtures for ConversionRequest — avoids setting 40+ fields per test."""
from __future__ import annotations

from pathlib import Path


def make_minimal_request(
    input_path: str = "/tmp/test.pdf",
    output_dir: str = "/tmp/output",
    source_type: str = "academic_paper",
    summarisation_model: str = "test-model:latest",
    max_workers: int = 1,
    temperature: float = 0.6,
    **overrides,
):
    """Create a ConversionRequest with sensible defaults for testing.

    Any field can be overridden via kwargs. Only the fields relevant to
    the test need to be set — the rest get safe defaults.
    """
    from core.models import ConversionRequest

    defaults = dict(
        input_path=Path(input_path),
        output_dir=Path(output_dir),
        password=None,
        override_recommendation=None,
        use_llm_ocr=True,
        primary_ocr_model="test-ocr:latest",
        fallback_ocr_model="test-ocr:latest",
        auto_detect_scanned=True,
        force_ocr_all_pages=False,
        image_max_size=1200,
        ocr_retries=2,
        clean_markdown=True,
        fix_missing_spaces=False,
        token_saver=True,
        remove_page_number_headings=True,
        convert_separators_to_comments=False,
        segment_strategy="auto",
        custom_keywords=[],
        custom_regex_patterns=[],
        page_group_size=10,
        chunk_by_page_groups=True,
        token_limit_per_segment=1200,
        enable_semantic_segmentation=True,
        generate_summaries=True,
        summarisation_model=summarisation_model,
        summarisation_max_context_tokens=16000,
        summarisation_max_output_tokens=4096,
        summarisation_cache_enabled=False,
        generate_docx=False,
        docx_author="Test",
        docx_include_toc=True,
        docx_font="Helvetica",
        max_workers=max_workers,
        manual_segments=None,
        temperature=temperature,
        self_consistency=False,
        fast_model="",
        heavy_model="",
        coverage_threshold=0.50,
        simplification_model="",
        page_range_start=None,
        page_range_end=None,
        selected_chapters=None,
        extract_tables=False,
        extract_math=False,
        layout_analysis=False,
        table_extraction_method="camelot",
        math_model="pix2tex",
        source_type=source_type,
        include_executive_summary=True,
        include_thorough_summary=True,
        include_keypoints=True,
        enable_content_filter=True,
        academic_rigor=False,
        simplified_keypoints_enabled=False,
        extract_figure_text=False,
        output_briefing=False,
        output_podcast=False,
        output_flashcards=False,
        output_packets=False,
        output_obsidian=False,
        output_study_guide=False,
        output_social=False,
        output_mindmap=False,
        output_tts=False,
        output_evidence_map=False,
        output_qa=False,
        output_glossary=False,
        output_patterns=False,
        output_cheatsheet=False,
        output_skill=False,
        compact_summaries=False,
        # V10.28.0 (Sprint 1): conservative drop mode — default off.
        conservative_drops=False,
    )
    defaults.update(overrides)
    return ConversionRequest(**defaults)
