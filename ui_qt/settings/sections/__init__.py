"""Reusable section widgets for the settings sub-tabs.

Each section is a small QWidget with a header and a form, designed to be
composed into a sub-tab page.  Breaking the old monolithic tabs into these
sections is what enables the new 2-level settings structure (head group →
sub-tab → sections).

V0.4.19 (de-monolithization): the former 2,303-line ``sections.py`` module
became this package — every section class, helper, and constant moved
VERBATIM (byte-identical bodies) into per-family modules, and this facade
preserves the historical ``ui_qt.settings.sections`` import surface exactly
(``from ui_qt.settings.sections import <X>`` keeps working for every
previously importable name — classes, helpers, and constants):

  - ``helpers``           — model-picker helpers: ``_VISION_KW``, ``_badge``,
                            ``_get_ollama_models``, ``_populate_models``,
                            ``_populate_models_async`` /
                            ``_refresh_models_async`` (the W-b11 async
                            model-fetch machinery)
  - ``providers``         — ``PROVIDER_LABELS`` / ``PROVIDER_KEYS`` /
                            ``PROVIDER_URLS`` / ``PROVIDER_MODEL_HINTS``
  - ``ocr_sections``      — ``OcrEngineSection``, ``OcrModelSection``,
                            ``OcrFiguresSection``
  - ``ai_model_section``  — ``AiLocalModelSection`` (local backend /
                            architecture / model pickers)
  - ``ai_api_section``    — ``AiApiSection`` + the legacy
                            ``AiModelsSection`` / ``AiProviderSection``
                            aliases
  - ``ai_prompt_quality`` — ``AiPromptSection``, ``QUALITY_PRESETS``,
                            ``AiQualitySection``
  - ``output_sections``   — ``AiOutputSelectionSection`` + the seven
                            ``Output*`` sections (destination, generate,
                            segmentation, keywords, postprocess, RAG,
                            studio)
  - ``defaults_section``  — ``DefaultsSection`` (default engines/models
                            for the standalone service dialogs)
"""

from __future__ import annotations

from ui_qt.settings.sections.ai_api_section import (  # noqa: F401
    AiApiSection,
    AiModelsSection,
    AiProviderSection,
)
from ui_qt.settings.sections.ai_model_section import AiLocalModelSection  # noqa: F401
from ui_qt.settings.sections.ai_prompt_quality import (  # noqa: F401
    QUALITY_PRESETS,
    AiPromptSection,
    AiQualitySection,
)
from ui_qt.settings.sections.defaults_section import DefaultsSection  # noqa: F401
from ui_qt.settings.sections.helpers import (  # noqa: F401
    _VISION_KW,
    _badge,
    _get_ollama_models,
    _populate_models,
    _populate_models_async,
    _refresh_models_async,
    logger,
)
from ui_qt.settings.sections.ocr_sections import (  # noqa: F401
    OcrEngineSection,
    OcrFiguresSection,
    OcrModelSection,
)
from ui_qt.settings.sections.output_sections import (  # noqa: F401
    AiOutputSelectionSection,
    OutputDestinationSection,
    OutputGenerateSection,
    OutputKeywordsSection,
    OutputPostprocessSection,
    OutputRagSection,
    OutputSegmentationSection,
    OutputStudioSection,
)
from ui_qt.settings.sections.providers import (  # noqa: F401
    PROVIDER_KEYS,
    PROVIDER_LABELS,
    PROVIDER_MODEL_HINTS,
    PROVIDER_URLS,
)
