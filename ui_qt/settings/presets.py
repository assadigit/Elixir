"""Preset definitions for the Presets head group.

Each preset is a named bundle of settings applied when the user selects a
document type. The four "main" presets mirror the type cards on the home
screen; "Full OCR" and "Mixed" are preset-only (no home-screen card).

V0.7.0 (wizard rework ②, D3): the OCR flags moved to the 3-mode
vocabulary — presets carry ``ocr.mode`` (digital/scanned/auto) exactly
like the wizard's Step-1 mode cards, and the dead flags are purged
(the auto-detect flag was log-only; the content-filter preset values
were never read — the filter hardcodes 80/0.40). ``apply_preset_settings``
is the ONE applier both surfaces route through (the audit's split-brain
applier note, §W2 — the wizard previously applied a subset, the
Settings dialog all of it).
"""

from __future__ import annotations

from collections.abc import Callable
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
            "ocr.mode": "auto",
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
            "ocr.mode": "auto",
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
            "ocr.mode": "auto",
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
            "ocr.mode": "scanned",
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
            "ocr.mode": "scanned",
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
            "ocr.mode": "auto",
            "advanced.extract_figure_text": False,
            "segmentation.strategy": "auto",
        },
    },
    # V11.31: "Quick Markdown" (minimal) preset removed per user request.
}


def apply_preset_settings(update_setting: Callable[[str, Any], None], key: str) -> dict[str, Any]:
    """Apply a preset's canonical settings bundle via ``update_setting``.

    V0.7.0 (rework ②, the split-brain fix): the ONE applier — the Settings
    dialog's Presets page routes through here, and the bundle's vocabulary
    (``ocr.mode`` etc.) is the same one the wizard's Step-1 mode cards
    write, so the two surfaces can no longer drift apart. Unknown keys
    fall back to the normal_book bundle (mirrors the pre-V0.7.0 behaviour
    of ``PRESETS.get(key, PRESETS["normal_book"])``).

    Returns the applied bundle (callers may re-read it for UI refresh).
    """
    preset = PRESETS.get(key, PRESETS["normal_book"])
    bundle = preset["settings"]
    for setting_key, value in bundle.items():
        update_setting(setting_key, value)
    # source_type is carried inside the bundle — apply it explicitly too so
    # the standalone key always lands (pre-V0.7.0 behaviour, kept verbatim).
    update_setting("source_type", bundle.get("source_type", "normal_book"))
    return bundle


# V10.35.0 (Sprint 7.5): Token budget slider presets
TOKEN_BUDGET_PRESETS = [
    {
        "position": 0,
        "label": "Quick",
        "time_estimate": "~5 min",
        "cost_estimate": "$0",
        "settings": {
            "summarisation.enabled": True,
            "summarisation.include_keypoints": True,
            "docx.enabled": False,
            "outputs.briefing": False,
            "outputs.flashcards": False,
            "outputs.mindmap": True,
        },
    },
    {
        "position": 25,
        "label": "Standard",
        "time_estimate": "~15 min",
        "cost_estimate": "$0",
        "settings": {
            "summarisation.enabled": True,
            "summarisation.include_keypoints": True,
            "docx.enabled": False,
            "outputs.briefing": True,
            "outputs.flashcards": True,
            "outputs.mindmap": True,
        },
    },
    {
        "position": 50,
        "label": "Enhanced",
        "time_estimate": "~25 min",
        "cost_estimate": "$0.50",
        "settings": {
            "summarisation.enabled": True,
            "summarisation.include_keypoints": True,
            "summarisation.simplified_keypoints_enabled": True,
            "docx.enabled": True,
            "outputs.briefing": True,
            "outputs.podcast": True,
            "outputs.flashcards": True,
            "outputs.obsidian": True,
            "outputs.study_guide": True,
            "outputs.mindmap": True,
        },
    },
    {
        "position": 75,
        "label": "Comprehensive",
        "time_estimate": "~35 min",
        "cost_estimate": "$1.50",
        "settings": {
            "summarisation.enabled": True,
            "summarisation.include_keypoints": True,
            "summarisation.simplified_keypoints_enabled": True,
            "docx.enabled": True,
            "outputs.briefing": True,
            "outputs.podcast": True,
            "outputs.flashcards": True,
            "outputs.packets": True,
            "outputs.obsidian": True,
            "outputs.study_guide": True,
            "outputs.social": True,
            "outputs.mindmap": True,
            "outputs.qa": True,
            "outputs.glossary": True,
        },
    },
    {
        "position": 100,
        "label": "Thorough",
        "time_estimate": "~45 min",
        "cost_estimate": "$2.50",
        "settings": {
            "summarisation.enabled": True,
            "summarisation.include_keypoints": True,
            "summarisation.simplified_keypoints_enabled": True,
            "docx.enabled": True,
            "outputs.briefing": True,
            "outputs.podcast": True,
            "outputs.flashcards": True,
            "outputs.packets": True,
            "outputs.obsidian": True,
            "outputs.study_guide": True,
            "outputs.social": True,
            "outputs.mindmap": True,
            "outputs.qa": True,
            "outputs.glossary": True,
            "outputs.patterns": True,
            "outputs.cheatsheet": True,
            "outputs.epub": True,
            "outputs.quote_bank": True,
        },
    },
]
