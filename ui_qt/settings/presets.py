"""Preset definitions for the Presets head group.

Each preset is a named bundle of settings applied when the user selects a
document type.  The four "main" presets mirror the type cards on the home
screen; "Full OCR" and "Mixed" are preset-only (no home-screen card).
"""

from __future__ import annotations

from typing import Any

# (key, label, icon, subtitle, settings-applied-on-select, sub-tabs)
PRESETS: dict[str, dict[str, Any]] = {
    "normal_book": {
        "label": "Book",
        "icon": "book",
        "subtitle": "Standard text — novels, biographies, business books.",
        "settings": {
            "source_type": "normal_book",
            "ocr.timeout": 60,
            "is_academic": False,
            "ocr.force_ocr_all_pages": False,
            "ocr.auto_detect_scanned": True,
            "content_filter.min_content_chars": 80,
            "content_filter.min_word_count": 3,
            "advanced.extract_tables": False,
            "advanced.extract_figure_text": False,
            "summarisation.self_consistency": False,
            "segmentation.strategy": "auto",
        },
    },
    "academic_paper": {
        "label": "Research Paper",
        "icon": "file-text",
        "subtitle": "Two-column papers, journals, conference proceedings.",
        "settings": {
            "source_type": "academic_paper",
            "ocr.timeout": 90,
            "is_academic": True,
            "ocr.force_ocr_all_pages": False,
            "ocr.auto_detect_scanned": True,
            "content_filter.min_content_chars": 40,
            "content_filter.min_word_count": 2,
            "advanced.extract_tables": True,
            "advanced.extract_figure_text": False,
            "summarisation.self_consistency": False,
            "segmentation.strategy": "auto",
        },
    },
    "visual_catalogue": {
        "label": "Journal",
        "icon": "newspaper",
        "subtitle": "Visual-heavy — magazines, catalogues, InDesign layouts, multi-column.",
        "settings": {
            "source_type": "visual_catalogue",
            "ocr.timeout": 120,
            "is_academic": False,
            "ocr.force_ocr_all_pages": False,
            "ocr.auto_detect_scanned": True,
            "content_filter.min_content_chars": 80,
            "content_filter.min_word_count": 3,
            "advanced.extract_tables": False,
            "advanced.extract_figure_text": False,
            "segmentation.strategy": "auto",
        },
    },
    "infographics_slides": {
        "label": "Infographics & Slides",
        "icon": "image",
        "subtitle": "Image-only PDFs — LinkedIn carousels, posters, slide decks. Full OCR.",
        "settings": {
            "source_type": "visual_catalogue",
            "ocr.timeout": 120,
            "is_academic": False,
            "ocr.force_ocr_all_pages": True,
            "ocr.auto_detect_scanned": False,
            "content_filter.min_content_chars": 30,
            "content_filter.min_word_count": 1,
            "advanced.extract_figure_text": True,
            "segmentation.strategy": "token",
            "segmentation.token_limit": 1200,
            "summarisation.self_consistency": False,
        },
    },
    "full_ocr": {
        "label": "Full OCR",
        "icon": "scan",
        "subtitle": "Every page OCR'd, even if a text layer exists. For unreliable digital text.",
        "settings": {
            "source_type": "normal_book",
            "ocr.timeout": 120,
            "is_academic": False,
            "ocr.force_ocr_all_pages": True,
            "ocr.auto_detect_scanned": False,
            "content_filter.min_content_chars": 50,
            "content_filter.min_word_count": 2,
            "advanced.extract_figure_text": False,
            "segmentation.strategy": "auto",
        },
    },
    "mixed": {
        "label": "Mixed Document",
        "icon": "layers",
        "subtitle": "Hybrid — some digital pages, some scanned. Auto-detect handles each page.",
        "settings": {
            "source_type": "normal_book",
            "ocr.timeout": 90,
            "is_academic": False,
            "ocr.force_ocr_all_pages": False,
            "ocr.auto_detect_scanned": True,
            "content_filter.min_content_chars": 60,
            "content_filter.min_word_count": 2,
            "advanced.extract_figure_text": False,
            "segmentation.strategy": "auto",
        },
    },
    # V11.31: "Quick Markdown" (minimal) preset removed per user request.
}

# V10.35.0 (Sprint 7.5): Token budget slider presets
TOKEN_BUDGET_PRESETS = [
    {"position": 0, "label": "Quick", "time_estimate": "~5 min", "cost_estimate": "$0",
     "settings": {"summarisation.enabled": True, "summarisation.include_keypoints": True,
                  "docx.enabled": False, "outputs.briefing": False, "outputs.flashcards": False,
                  "outputs.mindmap": True}},
    {"position": 25, "label": "Standard", "time_estimate": "~15 min", "cost_estimate": "$0",
     "settings": {"summarisation.enabled": True, "summarisation.include_keypoints": True,
                  "docx.enabled": False, "outputs.briefing": True, "outputs.flashcards": True,
                  "outputs.mindmap": True}},
    {"position": 50, "label": "Enhanced", "time_estimate": "~25 min", "cost_estimate": "$0.50",
     "settings": {"summarisation.enabled": True, "summarisation.include_keypoints": True,
                  "summarisation.simplified_keypoints_enabled": True, "docx.enabled": True,
                  "outputs.briefing": True, "outputs.podcast": True, "outputs.flashcards": True,
                  "outputs.obsidian": True, "outputs.study_guide": True, "outputs.mindmap": True}},
    {"position": 75, "label": "Comprehensive", "time_estimate": "~35 min", "cost_estimate": "$1.50",
     "settings": {"summarisation.enabled": True, "summarisation.include_keypoints": True,
                  "summarisation.simplified_keypoints_enabled": True, "docx.enabled": True,
                  "outputs.briefing": True, "outputs.podcast": True, "outputs.flashcards": True,
                  "outputs.packets": True, "outputs.obsidian": True, "outputs.study_guide": True,
                  "outputs.social": True, "outputs.mindmap": True, "outputs.qa": True,
                  "outputs.glossary": True}},
    {"position": 100, "label": "Thorough", "time_estimate": "~45 min", "cost_estimate": "$2.50",
     "settings": {"summarisation.enabled": True, "summarisation.include_keypoints": True,
                  "summarisation.simplified_keypoints_enabled": True, "docx.enabled": True,
                  "outputs.briefing": True, "outputs.podcast": True, "outputs.flashcards": True,
                  "outputs.packets": True, "outputs.obsidian": True, "outputs.study_guide": True,
                  "outputs.social": True, "outputs.mindmap": True, "outputs.qa": True,
                  "outputs.glossary": True, "outputs.patterns": True, "outputs.cheatsheet": True,
                  "outputs.epub": True, "outputs.quote_bank": True}},
]
