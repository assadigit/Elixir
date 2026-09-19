"""Two-level tabbed settings dialog + section widgets.

Four head groups (vertical left rail):
  🎚 Presets · 🤖 AI · 📖 OCR · 📦 Output

Each head group has its own horizontal sub-tabs composed from small section
widgets in :mod:`ui_qt.settings.sections`.  System diagnostics live in a
separate About & System dialog under the Tools menu.
"""

from ui_qt.settings.dependencies_page import DependenciesSection
from ui_qt.settings.podcast_page import (
    PodcastDepthSection,
    PodcastFormatSection,
    PodcastPreviewSection,
    PodcastStyleSection,
)
from ui_qt.settings.presets import PRESETS
from ui_qt.settings.sections import (
    AiApiSection,
    AiLocalModelSection,
    AiOutputSelectionSection,
    AiPromptSection,
    AiQualitySection,
    OcrEngineSection,
    OcrFiguresSection,
    OcrModelSection,
    OutputDestinationSection,
    OutputGenerateSection,
    OutputKeywordsSection,
    OutputPostprocessSection,
    OutputRagSection,
    OutputSegmentationSection,
    OutputStudioSection,
)
from ui_qt.settings.settings_dialog import SettingsDialog
from ui_qt.settings.tts_page import (
    TtsEnginesSection,
    TtsNormalizationSection,
    TtsPreviewSection,
    TtsSpeedSection,
    TtsVoicesSection,
)

__all__ = [
    "SettingsDialog",
    "PRESETS",
    "AiLocalModelSection",
    "AiApiSection",
    "AiQualitySection",
    "AiOutputSelectionSection",
    "OcrEngineSection",
    "OcrModelSection",
    "OcrFiguresSection",
    "OutputDestinationSection",
    "OutputGenerateSection",
    "OutputSegmentationSection",
    "OutputKeywordsSection",
    "OutputPostprocessSection",
    "OutputRagSection",
    "OutputStudioSection",
    "TtsEnginesSection",
    "TtsVoicesSection",
    "TtsSpeedSection",
    "TtsNormalizationSection",
    "TtsPreviewSection",
    "PodcastFormatSection",
    "PodcastDepthSection",
    "PodcastStyleSection",
    "PodcastPreviewSection",
    "DependenciesSection",
]
