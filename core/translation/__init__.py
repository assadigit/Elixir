"""V4.7.25: Translation module — bidirectional EN ↔ FA translation.

A cross-cutting post-conversion transform that translates generated outputs
(summaries, keypoints, podcast scripts, etc.) between English and Farsi/Persian.

Architecture::

    ┌─────────┐   ┌────────────┐   ┌────────────┐   ┌─────────┐   ┌────────┐
    │ Chunker │──▶│ Translator │──▶│ Validator  │──▶│ Harakat │──▶│ Output │
    └─────────┘   └────────────┘   └────────────┘   └─────────┘   └────────┘
                         ▲               ▲
                    ┌────┴────┐     ┌────┴────┐
                    │Glossary │     │ Judge   │
                    └─────────┘     │ LLM     │
                                    └─────────┘

Key design decisions:
  * **TranslateGemma-12B via Ollama** as the primary translator (purpose-built,
    lower hallucination than general LLMs, supports Persian + harakat).
  * **Qwen3.5-9B as judge LLM** (different model family → orthogonal error
    detection).
  * **Zero hallucination tolerance**: back-translation + semantic similarity +
    judge LLM triple-validation. Flagged chunks are retried once, then kept
    + flagged in the report (never silently accepted).
  * **Harakat (اعراب‌گذاری)**: a TTS-friendly variant is produced for every
    Farsi output, reusing the confidence-first pattern from the TTS normalizer.
  * **Glossary**: proper nouns + technical terms extracted from the first
    chunk(s) and passed as context to all subsequent chunks for consistency.
"""

from __future__ import annotations

import logging

from core.translation.chunker import Chunk, TranslationChunker
from core.translation.glossary import GlossaryManager
from core.translation.harakat import HarakatGenerator
from core.translation.service import TranslationProgress, TranslationService
from core.translation.translator import Translator

# V18.20.4.6+ (P5-2b / O-c10): NLLBTranslator is GONE. The module
# core.translation.nllb_translator (deprecated since V13.31.0 #13) was
# deleted together with the lazy ``__getattr__`` shim that re-exported
# it here: the shim had zero users (nothing in the tree does
# ``from core.translation import NLLBTranslator``) and the only call site
# (the ``backend == "nllb"`` branch in TranslationService.from_settings)
# was provably unreachable — utils.settings.Settings._load() (V13.31.0)
# and core.system.bootstrap (V18.2.26 A14) both migrate legacy
# translation.backend='nllb' to 'ollama' before any read, and no UI
# offers "nllb".
from core.translation.validator import ChunkValidation, TranslationValidator, ValidationReport

logger = logging.getLogger(__name__)


__all__ = [
    "TranslationChunker",
    "Chunk",
    "GlossaryManager",
    "Translator",
    "TranslationValidator",
    "ValidationReport",
    "ChunkValidation",
    "HarakatGenerator",
    "TranslationService",
    "TranslationProgress",
]
