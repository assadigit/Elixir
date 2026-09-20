"""Translation service — orchestrates the full translation pipeline.

This is the main entry point for translating files. It ties together:
  * :class:`TranslationChunker` — splits text into chunks
  * :class:`GlossaryManager` — extracts + maintains terminology
  * :class:`Translator` — translates each chunk via Ollama
  * :class:`TranslationValidator` — back-translation + judge LLM validation
  * :class:`HarakatGenerator` — adds Persian diacritics for TTS

Usage (high-level)::

    from core.translation import TranslationService, TranslationProgress

    service = TranslationService.from_settings(log_callback=my_logger)
    service.translate_book_outputs(
        book_output_dir=Path("output/MyBook"),
        book_name="MyBook",
        progress_callback=lambda p: print(f"{p.stage}: {p.message}"),
    )

File layout produced::

    output/MyBook/
    ├── MyBook.summary.md                      ← original
    ├── fa/                                    ← translation subfolder
    │   ├── MyBook.summary.fa.md               ← clean Persian
    │   ├── MyBook.summary.fa.harakat.md       ← Persian + harakat (TTS-ready)
    │   ├── chapters/
    │   │   └── summaries/
    │   │       └── 001_summary.fa.md
    │   └── MyBook.podcast.fa.harakat.md       ← ready for Podcast Maker
    └── translation_logs/
        ├── MyBook.translation.report.json
        └── MyBook.glossary.json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.translation.chunker import Chunk, TranslationChunker
from core.translation.glossary import GlossaryManager
from core.translation.harakat import HarakatGenerator
from core.translation.translator import Translator, detect_language

# V18.20.4.6+ (P5-2b / O-c10): the deprecated NLLB translator backend
# (core.translation.nllb_translator, deprecated since V13.31.0 #13) was
# retired — deleted with its lazy-import shims. Its last reachable entry
# point (the ``backend == "nllb"`` branch in TranslationService.
# from_settings) was provably dead: utils.settings.Settings._load() and
# core.system.bootstrap both migrate legacy translation.backend='nllb'
# to 'ollama' before any read, and no UI offers "nllb". Translation is
# TranslateGemma (Ollama) only.
from core.translation.validator import TranslationValidator, ValidationReport

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]
ProgressFn = Callable[["TranslationProgress"], None]


# ── Progress ─────────────────────────────────────────────────────────────


@dataclass
class TranslationProgress:
    """Progress update for UI callbacks.

    Attributes:
        stage:              "starting", "chunking", "translating",
                            "validating", "harakat", "writing", "done", "error".
        current_file:       name of the file being processed.
        current_file_index: 0-based index of the current file.
        total_files:        total number of files to translate.
        current_chunk:      0-based index of the current chunk.
        total_chunks:       total chunks in the current file.
        message:            human-readable status message.
    """

    stage: str = "starting"
    current_file: str = ""
    current_file_index: int = 0
    total_files: int = 0
    current_chunk: int = 0
    total_chunks: int = 0
    message: str = ""


# ── Output file mapping ──────────────────────────────────────────────────

# Maps translation output keys to (file_patterns, description)
# Patterns are relative to the book output directory.
_OUTPUT_FILE_MAP = {
    # V7.5.0: each entry lists BOTH the legacy flat pattern and the new
    # subfolder pattern, so translation finds files regardless of which
    # layout produced them.  Translated files are written next to the
    # source (source_path.parent / target_lang), so a subfoldered source
    # produces e.g. summaries/fa/{name}.summary.fa.md — clean.
    "full_markdown": (
        ["{name}.md", "markdown/{name}.md", "chapters/*.md", "markdown/chapters/*.md"],
        "Full book + individual chapters",
    ),
    "chapter_summaries": (
        [
            "{name}.summary.md",
            "summaries/{name}.summary.md",
            "chapters/summaries/*.md",
            "summaries/chapters/*.md",
        ],
        "Book summary + per-chapter summaries",
    ),
    "keypoints": (
        ["{name}.keypoints.md", "keypoints/{name}.keypoints.md"],
        "All keypoints",
    ),
    "simplified_keypoints": (
        [
            "{name}.simplified_keypoints.md",
            "keypoints/{name}.simplified_keypoints.md",
            "{name}.keypoints.simplified.md",
            "keypoints/{name}.keypoints.simplified.md",
        ],
        "Simplified keypoints digest",
    ),
    "briefing": (
        ["{name}.briefing.md", "briefing/{name}.briefing.md"],
        "Executive briefing",
    ),
    "podcast": (
        [
            "{name}.podcast.md",
            "{name}.Podcast.md",
            "podcast/{name}.podcast.md",
            "podcast/{name}.Podcast.md",
        ],
        "Podcast script",
    ),
    "flashcards": (
        ["{name}.flashcards.md", "flashcards/{name}.flashcards.md"],
        "Flashcards",
    ),
    "obsidian": (
        ["obsidian/*.md"],
        "Obsidian knowledge base",
    ),
    "study_guide": (
        ["{name}.study_guide.md", "study_guide/{name}.study_guide.md"],
        "Study guide",
    ),
    "social": (
        ["{name}.social.md", "social/{name}.social.md"],
        "Social media pack",
    ),
    "mindmap": (
        ["{name}.mindmap.md", "mindmap/{name}.mindmap.md"],
        "Mind map",
    ),
}


# ── Translation service ──────────────────────────────────────────────────


class TranslationService:
    """Orchestrates the full translation pipeline.

    Create via :meth:`from_settings` for a settings-configured instance,
    or directly for custom configuration.
    """

    def __init__(
        self,
        translator: Translator,
        validator: TranslationValidator | None = None,
        harakat_generator: HarakatGenerator | None = None,
        chunker: TranslationChunker | None = None,
        glossary_enabled: bool = True,
        harakat_enabled: bool = True,
        validation_enabled: bool = True,
        max_retries: int = 1,
        log_callback: LogFn | None = None,
    ) -> None:
        self.translator = translator
        self.validator = validator
        self.harakat_gen = harakat_generator
        self.chunker = chunker or TranslationChunker(max_tokens=2000)
        self.glossary_enabled = glossary_enabled
        self.harakat_enabled = harakat_enabled
        self.validation_enabled = validation_enabled
        self.max_retries = max_retries
        self.log = log_callback or (lambda msg, level="INFO": None)

    # ── Factory ───────────────────────────────────────────────────────

    @classmethod
    def from_settings(
        cls,
        log_callback: LogFn | None = None,
    ) -> TranslationService | None:
        """Create a TranslationService from saved settings.

        Returns None if translation is not configured.

        V13.31.0 (#13): NLLB backend removed from the default UI. The default
        backend is "ollama" (TranslateGemma LLM, can do harakat in the
        same model). V18.20.4.6+ (P5-2b / O-c10): the deprecated NLLB
        fallback branch was retired — legacy ``translation.backend =
        "nllb"`` settings are migrated to "ollama" by utils.settings.
        Settings._load() (V13.31.0) and core.system.bootstrap (V18.2.26
        A14) before any read, so the branch was unreachable dead code.
        """
        from utils.settings import Settings

        s = Settings()

        endpoint = s.get("translation.endpoint", "http://localhost:11434/v1")
        # V0.16 (Phase 3 / task 3.3): the path-mismatch fix. This service
        # used to read ``translation.api_key`` while ``_SECRET_PATHS``
        # listed ``translation.cloud_api_key`` — so a key migrated to the
        # OS keychain under the canonical path was INVISIBLE here (the
        # read silently defeated the keychain). Now: canonical path first,
        # legacy path as a migration fallback. Both reads go through
        # get_secret (keychain → settings → migrate), and a legacy value
        # found in the keychain is copied to the canonical entry once.
        from core.system.secrets import get_secret, set_secret

        api_key = get_secret("translation.cloud_api_key", s, "")
        if not api_key:
            legacy = get_secret("translation.api_key", s, "")
            if legacy:
                api_key = legacy
                # One-time legacy → canonical migration (best-effort:
                # failures fall back to re-reading the legacy path above,
                # which get_secret resolves from the keychain/settings).
                try:
                    set_secret("translation.cloud_api_key", legacy, s)
                    logger.warning(
                        "[security] translation API key migrated from the "
                        "legacy 'translation.api_key' path to "
                        "'translation.cloud_api_key'."
                    )
                except Exception:  # pragma: no cover — best-effort
                    pass
        temperature = float(s.get("translation.temperature", 0.1))
        no_think = bool(s.get("translation.no_think", True))

        # ── Create the translator (Ollama backend — TranslateGemma) ───
        # V18.20.4.6+ (P5-2b / O-c10): the deprecated ``backend == "nllb"``
        # branch (NLLBTranslator lazy import) was removed — provably dead
        # (see the module-head comment); Ollama is the only backend.
        model = s.get("translation.model", "translategemma:4b")
        translator = Translator(
            endpoint=endpoint,
            model=model,
            api_key=api_key,
            temperature=temperature,
            no_think=no_think,
            log_callback=log_callback,
        )
        max_tokens = int(s.get("translation.max_chunk_tokens", 2000))
        log_callback(f"  [Translation] Backend: Ollama ({model})", "INFO") if log_callback else None

        # ── Validator (judge LLM — always Ollama, regardless of translator) ─
        judge_model = s.get("translation.judge_model", "")
        if not judge_model:
            judge_model = s.get("summarisation.model", "")
        validator = None
        if s.get("translation.validation_enabled", True) and judge_model:
            validator = TranslationValidator(
                endpoint=endpoint,
                judge_model=judge_model,
                translator=translator,
                back_translation_threshold=float(
                    s.get("translation.back_translation_threshold", 0.6)
                ),
                judge_threshold=float(s.get("translation.judge_threshold", 0.7)),
                api_key=api_key,
                log_callback=log_callback,
            )

        # ── Harakat generator ──────────────────────────────────────────
        # V5.1: Harakat ALWAYS uses Ollama (the retired NLLB backend
        # couldn't do harakat, so this was never backend-dependent).
        harakat_gen = None
        if s.get("translation.harakat_enabled", True):
            harakat_model = s.get("translation.harakat_model", "translategemma:4b")
            # V8.0.0: use the summarisation model as a harakat fallback —
            # TranslateGemma produces garbage for harakat; if it fails
            # validation, retry with the summarisation model (often a
            # larger Qwen that handles harakat better).
            fallback_model = s.get("summarisation.model", "")
            harakat_gen = HarakatGenerator(
                endpoint=endpoint,
                model=harakat_model,
                api_key=api_key,
                temperature=temperature,
                no_think=no_think,
                log_callback=log_callback,
                fallback_model=fallback_model,
            )

        return cls(
            translator=translator,
            validator=validator,
            harakat_generator=harakat_gen,
            chunker=TranslationChunker(max_tokens=max_tokens),
            glossary_enabled=s.get("translation.glossary_enabled", True),
            harakat_enabled=s.get("translation.harakat_enabled", True),
            validation_enabled=s.get("translation.validation_enabled", True),
            max_retries=int(s.get("translation.max_retries", 1)),
            log_callback=log_callback,
        )

    # ── Text translation ──────────────────────────────────────────────

    def translate_text(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "fa",
    ) -> str:
        """Translate a text string. Quick single-call translation (no chunking).

        For large texts, use :meth:`translate_file` instead.
        """
        if source_lang == "auto":
            source_lang = detect_language(text)
        return self.translator.translate(text, source_lang, target_lang)

    # ── File translation ──────────────────────────────────────────────

    def translate_file(
        self,
        source_path: Path,
        target_lang: str = "fa",
        output_dir: Path | None = None,
        source_lang: str = "auto",
        progress_callback: ProgressFn | None = None,
    ) -> tuple[Path | None, ValidationReport | None]:
        """Translate a single file.

        Args:
            source_path:    path to the source .md/.txt file.
            target_lang:    "en" or "fa".
            output_dir:     directory for the translated file. If None,
                            creates a ``{target_lang}/`` subfolder next to
                            the source file.
            source_lang:    "en", "fa", or "auto".
            progress_callback: called with :class:`TranslationProgress` updates.

        Returns:
            (translated_path, validation_report) — or (None, None) on failure.
        """
        source_path = Path(source_path)
        if not source_path.exists():
            self.log(f"  [Translation] File not found: {source_path}", "ERROR")
            return None, None

        # Read source
        try:
            text = source_path.read_text(encoding="utf-8")
        except Exception as e:
            self.log(f"  [Translation] Error reading {source_path}: {e}", "ERROR")
            return None, None

        if not text.strip():
            self.log(f"  [Translation] Empty file: {source_path}", "WARNING")
            return None, None

        # Detect source language
        if source_lang == "auto":
            source_lang = detect_language(text)
        if source_lang == target_lang:
            self.log(
                f"  [Translation] Source already in {target_lang}, skipping: {source_path.name}",
                "INFO",
            )
            return None, None

        self.log(
            f"  [Translation] Translating {source_path.name}: {source_lang} → {target_lang}", "INFO"
        )

        if progress_callback:
            progress_callback(
                TranslationProgress(
                    stage="chunking",
                    current_file=source_path.name,
                    message=f"Chunking {source_path.name}...",
                )
            )

        # ── Chunk ─────────────────────────────────────────────────────
        chunks = self.chunker.chunk(text)
        if not chunks:
            return None, None

        self.log(f"  [Translation] {len(chunks)} chunks", "INFO")

        glossary_mgr, glossary_context = self._extract_glossary_context(
            chunks,
            source_lang,
            target_lang,
        )

        # ── Translate + validate each chunk ───────────────────────────
        translated_chunks: list[str] = []
        report = ValidationReport(
            file_name=source_path.name,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # V7.1.0 S4: Parallel translation for translatable chunks.
        # Split chunks into translatable and non-translatable (frontmatter/code).
        # Process translatable chunks in parallel via ThreadPoolExecutor.
        translatable_indices = []
        for i, chunk in enumerate(chunks):
            if chunk.is_frontmatter or chunk.is_code:
                # Pre-fill non-translatable chunks
                if len(translated_chunks) <= i:
                    translated_chunks.extend([""] * (i - len(translated_chunks) + 1))
                translated_chunks[i] = chunk.text
            else:
                translatable_indices.append(i)

        # Ensure translated_chunks is long enough
        while len(translated_chunks) < len(chunks):
            translated_chunks.append("")

        self._translate_chunks_parallel(
            source_path=source_path,
            chunks=chunks,
            translatable_indices=translatable_indices,
            translated_chunks=translated_chunks,
            report=report,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_context=glossary_context,
            progress_callback=progress_callback,
        )

        # ── Reassemble ────────────────────────────────────────────────
        translated_text = "\n".join(translated_chunks)

        translated_path = self._write_translation_outputs(
            source_path=source_path,
            translated_text=translated_text,
            output_dir=output_dir,
            target_lang=target_lang,
            source_lang=source_lang,
            report=report,
            glossary_mgr=glossary_mgr,
            progress_callback=progress_callback,
        )

        if progress_callback:
            progress_callback(
                TranslationProgress(
                    stage="done",
                    current_file=source_path.name,
                    message=f"Done: {report.summary()}" if report.chunk_results else "Done",
                )
            )

        return translated_path, report if self.validation_enabled else None

    # ── Glossary extraction (O-c7: extracted verbatim from translate_file) ──

    def _extract_glossary_context(
        self,
        chunks: list[Chunk],
        source_lang: str,
        target_lang: str,
    ) -> tuple[GlossaryManager | None, str]:
        """Extract the glossary from the first few translatable chunks.

        V18.20.4.6+ (P5-2b / O-c7): extracted VERBATIM from translate_file
        (pre-split service.py lines 382-401) — the body below is
        byte-identical; only this def/params/return glue is new.
        """
        # ── Glossary extraction ───────────────────────────────────────
        glossary_mgr = None
        if self.glossary_enabled:
            glossary_mgr = GlossaryManager(source_lang=source_lang, target_lang=target_lang)
            # Extract from the first few translatable chunks
            translatable_count = 0
            for c in chunks:
                if c.is_frontmatter or c.is_code:
                    continue
                glossary_mgr.extract_from_text(c.text)
                translatable_count += 1
                if translatable_count >= 5:
                    break
            if glossary_mgr.glossary.entries:
                self.log(
                    f"  [Translation] Glossary: {len(glossary_mgr.glossary.entries)} terms extracted",
                    "INFO",
                )

        glossary_context = glossary_mgr.get_context_for_prompt() if glossary_mgr else ""
        return glossary_mgr, glossary_context

    # ── Parallel chunk translation (O-c7: extracted verbatim from
    # translate_file — the V7.1.0 S4 ThreadPoolExecutor engine + the
    # V7.1.0 S4 sequential retry pass for flagged chunks) ──────────────────

    def _translate_chunks_parallel(
        self,
        source_path: Path,
        chunks: list[Chunk],
        translatable_indices: list[int],
        translated_chunks: list[str],
        report: ValidationReport,
        source_lang: str,
        target_lang: str,
        glossary_context: str,
        progress_callback: ProgressFn | None = None,
    ) -> None:
        """Translate + validate the translatable chunks (in-place).

        V18.20.4.6+ (P5-2b / O-c7): extracted VERBATIM from translate_file
        (pre-split service.py lines 429-599) — the body below is
        byte-identical, including its function-local imports
        (threading/ThreadPoolExecutor, translation cache, ChunkValidation);
        only this def/params glue is new. Mutates ``translated_chunks`` and
        ``report`` in place (same objects the caller owns).
        """
        if translatable_indices:
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # V7.1.0 S4: Use 2 workers for NLLB (small model, fits VRAM easily)
            # For Ollama (LLM), use 1 worker (VRAM constrained)
            max_workers = (
                2
                if hasattr(self.translator, "model_name")
                and "nllb" in str(getattr(self.translator, "model_name", "")).lower()
                else 1
            )
            self.log(
                f"  [Translation] Using {max_workers} parallel worker(s) for {len(translatable_indices)} chunks",
                "INFO",
            )

            lock = threading.Lock()
            completed_count = [0]

            def _translate_one(idx: int) -> tuple:
                """Translate + validate a single chunk. Returns (idx, translated, cv_result)."""
                chunk = chunks[idx]
                try:
                    # V7.2.0 S5: Check persistent cache first
                    from core.translation.cache import (
                        get_cached_translation,
                        save_cached_translation,
                    )

                    model_id = getattr(
                        self.translator, "model_name", getattr(self.translator, "model", "unknown")
                    )
                    cached = get_cached_translation(
                        text=chunk.text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        model=str(model_id),
                    )
                    if cached:
                        self.log(f"  [Translation] Chunk {idx + 1} cache hit — skipping", "DEBUG")
                        cv = None
                        if self.validator and self.validation_enabled:
                            # Reconstruct validation result from cache
                            from core.translation.validator import ChunkValidation

                            cv = ChunkValidation(
                                chunk_index=idx,
                                source_text=chunk.text,
                                translated_text=cached["translated_text"],
                                similarity_score=cached.get("similarity_score", 0.0),
                                judge_score=cached.get("judge_score", 0.0),
                                passed=cached.get("passed", True),
                            )
                        return (idx, cached["translated_text"], cv)

                    # Not cached — translate
                    translated = self.translator.translate(
                        chunk.text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        glossary_context=glossary_context,
                        prev_context=chunk.context,
                    )

                    cv = None
                    if self.validator and self.validation_enabled:
                        cv = self.validator.validate_chunk(
                            source_text=chunk.text,
                            translated_text=translated,
                            chunk_index=idx,
                            source_lang=source_lang,
                            target_lang=target_lang,
                        )

                    # V7.2.0 S5: Save to cache
                    if cv:
                        save_cached_translation(
                            text=chunk.text,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            model=str(model_id),
                            translated_text=translated,
                            similarity_score=cv.similarity_score,
                            judge_score=cv.judge_score,
                            passed=cv.passed,
                        )
                    else:
                        save_cached_translation(
                            text=chunk.text,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            model=str(model_id),
                            translated_text=translated,
                        )

                    return (idx, translated, cv)
                except Exception as e:
                    self.log(f"  [Translation] Chunk {idx + 1} failed: {e}", "WARNING")
                    return (idx, chunk.text, None)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(_translate_one, idx): idx for idx in translatable_indices
                }
                for future in as_completed(futures):
                    idx, translated, cv = future.result()
                    with lock:
                        translated_chunks[idx] = translated
                        completed_count[0] += 1
                        if progress_callback:
                            progress_callback(
                                TranslationProgress(
                                    stage="translating",
                                    current_file=source_path.name,
                                    current_chunk=completed_count[0],
                                    total_chunks=len(translatable_indices),
                                    message=f"Translated chunk {completed_count[0]}/{len(translatable_indices)}...",
                                )
                            )
                        if cv:
                            report.chunk_results.append(cv)
                            report.total_chunks += 1
                            if cv.passed:
                                report.passed_chunks += 1
                            else:
                                report.flagged_chunks += 1

            # V7.1.0 S4: Compute averages from validation results
            if report.chunk_results:
                report.avg_similarity = sum(
                    cv.similarity_score for cv in report.chunk_results
                ) / len(report.chunk_results)
                report.avg_judge_score = sum(cv.judge_score for cv in report.chunk_results) / len(
                    report.chunk_results
                )

            # V7.1.0 S4: Retry flagged chunks sequentially (after parallel pass)
            if self.max_retries > 0:
                for cv in report.chunk_results:
                    if not cv.passed and not cv.retried:
                        cv.retried = True
                        chunk = chunks[cv.chunk_index]
                        self.log(
                            f"  [Translation] Chunk {cv.chunk_index + 1} flagged ({cv.flagged_reason}), retrying...",
                            "INFO",
                        )
                        old_temp = getattr(self.translator, "temperature", 0.1)
                        self.translator.temperature = max(0.0, old_temp - 0.05)
                        translated = self.translator.translate(
                            chunk.text,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            glossary_context=glossary_context,
                            prev_context=chunk.context,
                        )
                        self.translator.temperature = old_temp

                        # Re-validate
                        new_cv = self.validator.validate_chunk(
                            source_text=chunk.text,
                            translated_text=translated,
                            chunk_index=cv.chunk_index,
                            source_lang=source_lang,
                            target_lang=target_lang,
                        )
                        new_cv.retried = True
                        if not new_cv.passed:
                            self.log(
                                f"  [Translation] Chunk {cv.chunk_index + 1} still flagged after retry: {new_cv.flagged_reason}",
                                "WARNING",
                            )
                        else:
                            self.log(
                                f"  [Translation] Chunk {cv.chunk_index + 1} passed after retry",
                                "INFO",
                            )
                        # Update the result
                        idx_in_results = report.chunk_results.index(cv)
                        report.chunk_results[idx_in_results] = new_cv
                        translated_chunks[cv.chunk_index] = translated
                        if new_cv.passed and not cv.passed:
                            report.passed_chunks += 1
                            report.flagged_chunks -= 1
                        if new_cv.retried:
                            report.retried_chunks += 1

                # Recompute averages after retries
                if report.chunk_results:
                    report.avg_similarity = sum(
                        cv.similarity_score for cv in report.chunk_results
                    ) / len(report.chunk_results)
                    report.avg_judge_score = sum(
                        cv.judge_score for cv in report.chunk_results
                    ) / len(report.chunk_results)

    # ── Output persistence (O-c7: extracted verbatim from translate_file) ───

    def _write_translation_outputs(
        self,
        source_path: Path,
        translated_text: str,
        output_dir: Path | None,
        target_lang: str,
        source_lang: str,
        report: ValidationReport,
        glossary_mgr: GlossaryManager | None,
        progress_callback: ProgressFn | None = None,
    ) -> Path:
        """Write every translation output for one translated file.

        V18.20.4.6+ (P5-2b / O-c7): extracted VERBATIM from translate_file
        (pre-split service.py lines 604-669) — the body below is
        byte-identical; only this def/params/return glue is new. Writes the
        translated file, the Farsi harakat variant, the validation report
        (JSON + MD + bilingual HTML viewer) and the glossary.
        """
        # ── Determine output path ─────────────────────────────────────
        if output_dir is None:
            output_dir = source_path.parent / target_lang
        output_dir.mkdir(parents=True, exist_ok=True)

        # File naming: original_name.{target_lang}.md
        stem = source_path.stem
        suffix = source_path.suffix
        translated_path = output_dir / f"{stem}.{target_lang}{suffix}"

        if progress_callback:
            progress_callback(
                TranslationProgress(
                    stage="writing",
                    current_file=source_path.name,
                    message=f"Writing {translated_path.name}...",
                )
            )

        translated_path.write_text(translated_text, encoding="utf-8")
        self.log(f"  [Translation] Written: {translated_path}", "INFO")

        # ── Harakat variant (Farsi only) ──────────────────────────────
        harakat_path: Path | None = None
        if target_lang == "fa" and self.harakat_enabled and self.harakat_gen:
            if progress_callback:
                progress_callback(
                    TranslationProgress(
                        stage="harakat",
                        current_file=source_path.name,
                        message=f"Generating harakat variant for {source_path.name}...",
                    )
                )

            harakat_text = self.harakat_gen.add_harakat_to_markdown(translated_text)
            harakat_path = output_dir / f"{stem}.{target_lang}.harakat{suffix}"
            harakat_path.write_text(harakat_text, encoding="utf-8")
            self.log(f"  [Translation] Harakat variant: {harakat_path}", "INFO")

        # ── Save validation report ────────────────────────────────────
        if self.validation_enabled and report.chunk_results:
            logs_dir = source_path.parent / "translation_logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            report_path = logs_dir / f"{stem}.translation.report.json"
            report.save(report_path)
            # V7.2.0 S6: Also save human-readable Markdown report
            report_md_path = logs_dir / f"{stem}.translation.report.md"
            report.save_markdown(report_md_path)
            self.log(f"  [Translation] Report: {report_path} — {report.summary()}", "INFO")

            # V7.2.0 S25: Generate bilingual HTML viewer
            try:
                bilingual_path = logs_dir / f"{stem}.bilingual.html"
                self._generate_bilingual_html(
                    source_path,
                    translated_text,
                    report,
                    bilingual_path,
                    source_lang,
                    target_lang,
                )
                self.log(f"  [Translation] Bilingual viewer: {bilingual_path}", "INFO")
            except Exception as e:
                self.log(f"  [Translation] Bilingual viewer failed: {e}", "DEBUG")

        # ── Save glossary ─────────────────────────────────────────────
        if glossary_mgr and glossary_mgr.glossary.entries:
            logs_dir = source_path.parent / "translation_logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            glossary_path = logs_dir / f"{stem}.glossary.json"
            glossary_mgr.glossary.save(glossary_path)
        return translated_path

    # ── Book-level translation ────────────────────────────────────────

    def translate_book_outputs(
        self,
        book_output_dir: Path,
        book_name: str,
        target_lang: str | None = None,
        progress_callback: ProgressFn | None = None,
    ) -> list[tuple[Path, ValidationReport | None]]:
        """Translate all selected outputs for a converted book.

        Reads ``translation.outputs.*`` settings to determine which outputs
        to translate. Writes translated files into a ``{target_lang}/``
        subfolder inside ``book_output_dir``.

        V5.3.7: Only translates files modified in the last 30 minutes (the
        current conversion session). Prevents translating stale files from
        previous conversions that are still in the output folder.

        Args:
            book_output_dir: the book's output directory (e.g., output/MyBook/).
            book_name:       the book name (without extension).
            target_lang:     override the default target language.
            progress_callback: called with progress updates.

        Returns:
            List of (translated_path, report) tuples for each translated file.
        """
        import time as _time

        from utils.settings import Settings

        s = Settings()

        if target_lang is None:
            target_lang = s.get("translation.default_target_lang", "fa")

        # Determine which outputs to translate
        outputs_config = s.get("translation.outputs", {})
        if not outputs_config:
            self.log("  [Translation] No outputs selected for translation", "WARNING")
            return []

        # V5.3.7: Only translate files modified in the last 30 minutes.
        # This prevents translating stale files from previous conversions
        # that are still sitting in the output folder.
        max_file_age_seconds = 30 * 60  # 30 minutes
        current_time = _time.time()

        # Discover files to translate
        files_to_translate: list[Path] = []
        book_output_dir = Path(book_output_dir)

        for output_key, (patterns, _desc) in _OUTPUT_FILE_MAP.items():
            if not outputs_config.get(output_key, False):
                continue
            for pattern in patterns:
                # Replace {name} with the book name
                full_pattern = pattern.replace("{name}", book_name)
                # Glob relative to book_output_dir
                matched = sorted(book_output_dir.glob(full_pattern))
                for f in matched:
                    if not f.is_file() or f in files_to_translate:
                        continue
                    # V5.3.7: Skip stale files (older than 30 minutes)
                    file_age = current_time - f.stat().st_mtime
                    if file_age > max_file_age_seconds:
                        self.log(
                            f"  [Translation] Skipping stale file (not from this conversion): "
                            f"{f.relative_to(book_output_dir)}",
                            "DEBUG",
                        )
                        continue
                    files_to_translate.append(f)
                    self.log(
                        f"  [Translation] Will translate: {f.relative_to(book_output_dir)}", "INFO"
                    )

        if not files_to_translate:
            self.log("  [Translation] No output files found to translate", "WARNING")
            return []

        self.log(
            f"  [Translation] Translating {len(files_to_translate)} file(s) to {target_lang}",
            "INFO",
        )

        results: list[tuple[Path, ValidationReport | None]] = []

        for idx, file_path in enumerate(files_to_translate):
            if progress_callback:
                progress_callback(
                    TranslationProgress(
                        stage="starting",
                        current_file=file_path.name,
                        current_file_index=idx,
                        total_files=len(files_to_translate),
                        message=f"File {idx + 1}/{len(files_to_translate)}: {file_path.name}",
                    )
                )

            translated_path, report = self.translate_file(
                source_path=file_path,
                target_lang=target_lang,
                output_dir=None,  # auto-creates {lang}/ subfolder
                progress_callback=progress_callback,
            )

            if translated_path:
                results.append((translated_path, report))

        if progress_callback:
            progress_callback(
                TranslationProgress(
                    stage="done",
                    current_file_index=len(files_to_translate),
                    total_files=len(files_to_translate),
                    message=f"All done: {len(results)} files translated to {target_lang}",
                )
            )

        return results

    # ── V7.2.0 S25: Bilingual HTML viewer ──────────────────────────────

    def _generate_bilingual_html(
        self,
        source_path: Path,
        translated_text: str,
        report: ValidationReport,
        output_path: Path,
        source_lang: str,
        target_lang: str,
    ) -> None:
        """Generate a bilingual HTML viewer with side-by-side comparison.

        Flagged chunks are highlighted in yellow. Passed chunks are white.
        """
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except OSError:
            source_text = "(unable to read source)"

        # Split both texts into paragraphs for side-by-side display
        source_paras = [p.strip() for p in re.split(r"\n\n+", source_text) if p.strip()]
        translated_paras = [p.strip() for p in re.split(r"\n\n+", translated_text) if p.strip()]

        # Build flagged chunk indices set
        flagged_indices = {cv.chunk_index for cv in report.chunk_results if not cv.passed}

        # Build HTML rows
        rows_html = []
        max_rows = max(len(source_paras), len(translated_paras))
        for i in range(max_rows):
            src = source_paras[i] if i < len(source_paras) else ""
            tgt = translated_paras[i] if i < len(translated_paras) else ""
            # Escape HTML
            src = src.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            tgt = tgt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Convert markdown bold/italic to HTML
            src = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", src)
            tgt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", tgt)
            bg = "#fff3cd" if i in flagged_indices else "#ffffff"
            rows_html.append(f"""
            <tr style="background-color: {bg};">
                <td class="src">{src}</td>
                <td class="tgt" dir="rtl">{tgt}</td>
            </tr>""")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bilingual View: {source_path.name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; font-size: 18px; }}
        .stats {{ background: #e8f4fd; padding: 10px; border-radius: 8px; margin-bottom: 15px; font-size: 13px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #333; color: white; padding: 10px; text-align: left; font-size: 13px; }}
        td {{ padding: 12px; vertical-align: top; font-size: 13px; line-height: 1.6; border-bottom: 1px solid #ddd; }}
        .src {{ width: 50%; }}
        .tgt {{ width: 50%; }}
        .flagged {{ background-color: #fff3cd !important; }}
        .legend {{ margin: 10px 0; font-size: 12px; }}
        .legend span {{ display: inline-block; padding: 3px 10px; margin-right: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>📖 Bilingual Translation Viewer: {source_path.name}</h1>
    <div class="stats">
        <strong>{report.source_lang.upper()} → {report.target_lang.upper()}</strong> |
        {report.passed_chunks}/{report.total_chunks} chunks passed |
        Avg similarity: {report.avg_similarity:.2f} |
        Avg judge: {report.avg_judge_score:.2f}
    </div>
    <div class="legend">
        <span style="background: #ffffff;">✅ Passed</span>
        <span style="background: #fff3cd;">⚠️ Flagged (review recommended)</span>
    </div>
    <table>
        <thead>
            <tr>
                <th>Source ({source_lang.upper()})</th>
                <th>Translation ({target_lang.upper()})</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
</body>
</html>"""
        output_path.write_text(html, encoding="utf-8")

    # ── Standalone text translation (for Tools menu) ──────────────────

    def translate_standalone_text(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "fa",
    ) -> str:
        """Translate arbitrary text (for the Tools → Translate menu item).

        This is a simple wrapper around :meth:`translate_text` that also
        adds harakat if the target is Farsi.
        """
        translated = self.translate_text(text, source_lang, target_lang)

        # Add harakat if Farsi and harakat is enabled
        if target_lang == "fa" and self.harakat_enabled and self.harakat_gen and translated:
            return self.harakat_gen.add_harakat_to_markdown(translated)

        return translated
