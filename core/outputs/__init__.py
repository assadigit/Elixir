"""V4.0.0 + V4.1.0: Output generators.

V4.0.0:
- ExecutiveBriefingGenerator (B3) — one-page synthesis
- PodcastScriptGenerator  (B1) — 2-host conversational script
- FlashcardGenerator      (B2) — Anki-compatible TSV + readable MD

V4.1.0:
- ObsidianKBGenerator       — linked Obsidian vault slice (MOC + chapter notes)
- StudyGuideGenerator       — structured study guide (objectives, glossary, Q&A)
- SocialMediaPackGenerator  — X thread + LinkedIn + hooks + hashtags
- MindMapGenerator          — Mermaid mindmap + nested MD outline (deterministic)

All generators extend ``OutputGeneratorBase`` (defined in new_outputs.py),
which provides the shared LLM-call infrastructure and ``<think>`` stripping.
Each generator implements ``generate(summaries, book_title, output_dir) ->
Optional[Path]`` and is invoked from ``core/pipeline/converter.py`` only when
its corresponding ``output_*`` flag on ``ConversionRequest`` is enabled.
"""

import logging

from core.outputs.anki_export import export_anki_deck
from core.outputs.citation_graph import generate_citation_graph

# V10.35.0: New outputs
from core.outputs.epub_output import EPUBGenerator
from core.outputs.evidence_map import EvidenceMapGenerator
from core.outputs.mind_map import MindMapGenerator
from core.outputs.new_outputs import (
    ExecutiveBriefingGenerator,
    FlashcardGenerator,
    OutputGeneratorBase,
    PodcastScriptGenerator,
    QAGenerator,
)
from core.outputs.obsidian_kb import ObsidianKBGenerator
from core.outputs.packets import PacketGenerator
from core.outputs.packets_extensions import (
    PacketsAudioGenerator,
    PacketsLectureGenerator,
    PacketsPDFExporter,
)
from core.outputs.podcast_audio import PodcastAudioGenerator
from core.outputs.podcast_generator import PodcastGenerator, PodcastPromptBuilder
from core.outputs.quote_bank import QuoteBankGenerator
from core.outputs.reference_outputs import (
    AgentSkillGenerator,
    CheatsheetGenerator,
    GlossaryGenerator,
    PatternsGenerator,
)
from core.outputs.social_media import SocialMediaPackGenerator
from core.outputs.study_guide import StudyGuideGenerator

logger = logging.getLogger(__name__)

__all__ = [
    # V4.0.0
    "ExecutiveBriefingGenerator",
    "PodcastScriptGenerator",
    "FlashcardGenerator",
    "OutputGeneratorBase",
    # V4.1.0
    "ObsidianKBGenerator",
    "StudyGuideGenerator",
    "SocialMediaPackGenerator",
    "MindMapGenerator",
    # V4.2.0
    "PodcastAudioGenerator",
    # V4.6.0
    "PodcastGenerator",
    "PodcastPromptBuilder",
    # V7.3.0
    "PacketGenerator",
    # V8.0.0 #10
    "PacketsPDFExporter",
    "PacketsLectureGenerator",
    "PacketsAudioGenerator",
    # V10.1.0 — langextract integration
    "EvidenceMapGenerator",
    # V10.17.0 — Q&A study questions
    "QAGenerator",
    # V10.18.0 — citation graph + Anki export
    "generate_citation_graph",
    "export_anki_deck",
    # V10.20.0 — glossary + patterns + cheatsheet
    "GlossaryGenerator",
    "PatternsGenerator",
    "CheatsheetGenerator",
    "AgentSkillGenerator",
    # V10.35.0 — EPUB + Quote bank
    "EPUBGenerator",
    "QuoteBankGenerator",
]
