"""V8.0.0 #9 / V10.6.0: Output runner — extracted from the converter's
output-studio loop.

Contains the logic for iterating over enabled output generators, calling
each one, and collecting results.  Extracted into its own module so the
converter's ``convert()`` method is shorter and the output logic is
testable independently.

Also contains the V8.0.0 #10 packets-extensions runner (PDF, lecture,
audio) that fires after packets are generated.

V10.6.0 (Phase 8A-1): synced with the inline converter version.  The
extracted module now matches the inline loop exactly — including the
``output_evidence_map`` 10th output type, the special-case ``generate()``
signatures for evidence_map (4-arg) and flashcards (judge_results kwarg),
and the verbose TTS diagnostics block.  The converter's inline loop is
now a thin delegate to :func:`run_output_studio`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.models import SummaryResult

# The output plan: (attr, status_label, log_message, generator_class_name, subfolder_attr)
# ``subfolder_attr`` is an attribute name on OutputPaths (e.g. "briefing_dir").
# V10.6.0: added output_evidence_map (10th output — was missing from the
# original V8.0.0 extraction, causing the extracted module to be incomplete).
OUTPUT_PLAN: list[tuple[str, str, str, str, str]] = [
    (
        "output_briefing",
        "Generating Executive Briefing…",
        "📄 Generating executive briefing (1-page synthesis)…",
        "ExecutiveBriefingGenerator",
        "briefing_dir",
    ),
    (
        "output_podcast",
        "Generating Podcast Script…",
        "🎙️ Generating podcast script (configurable format/depth/style)…",
        "PodcastGenerator",
        "podcast_dir",
    ),
    (
        "output_packets",
        "Generating Packets of Knowledge…",
        "📦 Generating Packets of Knowledge (synthesized paragraphs)…",
        "PacketGenerator",
        "packets_dir",
    ),
    (
        "output_flashcards",
        "Generating Flashcards…",
        "🎴 Generating flashcards (Anki-compatible)…",
        "FlashcardGenerator",
        "flashcards_dir",
    ),
    (
        "output_obsidian",
        "Building Obsidian KB…",
        "🗂️  Building Obsidian knowledge base (linked notes)…",
        "ObsidianKBGenerator",
        "obsidian_dir",
    ),
    (
        "output_study_guide",
        "Generating Study Guide…",
        "📚 Generating study guide (objectives, glossary, Q&A)…",
        "StudyGuideGenerator",
        "study_guide_dir",
    ),
    (
        "output_social",
        "Generating Social Media Pack…",
        "📱 Generating social media pack (X thread + LinkedIn)…",
        "SocialMediaPackGenerator",
        "social_dir",
    ),
    (
        "output_mindmap",
        "Generating Mind Map…",
        "🧠 Generating mind map (Mermaid + outline)…",
        "MindMapGenerator",
        "mindmap_dir",
    ),
    (
        "output_tts",
        "Generating Podcast Audio (TTS)…",
        "🎙️ Generating podcast audio (TTS: EN→Kokoro, FA→Coqui XTTS v2)…",
        "PodcastAudioGenerator",
        "podcast_dir",
    ),
    # V10.6.0: Scientific Evidence Map (langextract grounding) — 10th output.
    (
        "output_evidence_map",
        "Generating Scientific Evidence Map…",
        "🗺️ Generating scientific evidence map (langextract grounding)…",
        "EvidenceMapGenerator",
        "evidence_dir",
    ),
    # V10.17.0 (F1): Q&A study questions — 11th output.
    (
        "output_qa",
        "Generating Study Questions…",
        "❓ Generating open-ended study questions (Q&A pairs)…",
        "QAGenerator",
        "qa_dir",
    ),
    # V10.20.0: Glossary — 12th output.
    (
        "output_glossary",
        "Generating Glossary…",
        "📖 Generating glossary (key terms + definitions)…",
        "GlossaryGenerator",
        "glossary_dir",
    ),
    # V10.20.0: Patterns/Techniques — 13th output.
    (
        "output_patterns",
        "Generating Patterns & Techniques…",
        "🔧 Generating patterns, techniques, and decision rules…",
        "PatternsGenerator",
        "patterns_dir",
    ),
    # V10.20.0: Cheatsheet — 14th output.
    (
        "output_cheatsheet",
        "Generating Cheatsheet…",
        "📋 Generating cheatsheet (decision tables + quick-reference)…",
        "CheatsheetGenerator",
        "cheatsheet_dir",
    ),
    # V10.21.0: Agent Skill export — 15th output.
    (
        "output_skill",
        "Generating Agent Skill…",
        "🤖 Generating SKILL.md for AI coding assistants…",
        "AgentSkillGenerator",
        "skill_dir",
    ),
    # V10.35.0: EPUB output — 16th output.
    (
        "output_epub",
        "Generating EPUB…",
        "📚 Generating annotated EPUB (e-reader format)…",
        "EPUBGenerator",
        "epub_dir",
    ),
    # V10.35.0: Quote bank — 17th output.
    (
        "output_quote_bank",
        "Generating Quote Bank…",
        "💬 Extracting direct quotes with page citations…",
        "QuoteBankGenerator",
        "quote_bank_dir",
    ),
]


def _log_tts_diagnostics(
    log: Callable[[str, str], None],
    paths: Any,
    book_title: str,
) -> None:
    """Emit verbose TTS configuration diagnostics (V10.6.0 extracted)."""
    log("  🎙️ TTS Audio Generation Details:", "INFO")
    log("    TTS enabled: True", "INFO")
    podcast_path = paths.podcast_script(book_title)
    log(
        f"    Podcast script exists: {podcast_path}"
        if podcast_path.exists()
        else "    Podcast script: NOT FOUND",
        "INFO",
    )
    from utils.settings import Settings

    _s = Settings()
    log(f"    EN engine: {_s.get('tts.en_engine', 'neutts')}", "INFO")
    # V0.6.64: the Piper binary + fa_host_* (Piper voice id) diagnostics are
    # gone with the Piper engine.
    log(f"    Host A voice: {_s.get('tts.host_a_voice', 'dave')}", "INFO")
    log(f"    Host B voice: {_s.get('tts.host_b_voice', 'jo')}", "INFO")
    log(f"    FA voice (Coqui speaker): {_s.get('tts.fa_voice', '') or '(Coqui default)'}", "INFO")
    log(f"    Speed: {_s.get('tts.speed', 1.0)}", "INFO")
    log(f"    Normalize: {_s.get('tts.normalize_enabled', True)}", "INFO")
    log(f"    NeuTTS GGUF: {_s.get('tts.neutts_gguf_path', '(not set)')}", "INFO")


def run_output_studio(
    request: Any,
    summaries: list[SummaryResult],
    segments: Any,
    book_title: str,
    paths: Any,
    log: Callable[[str, str], None],
    update_status: Callable[[str], None],
    judge_results: list[Any] | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
    checkpoint: Any = None,
) -> dict[str, str]:
    """Run all enabled output generators.

    Args:
        request: the ConversionRequest (has output_* flags)
        summaries: the chapter summaries
        segments: the chapter segments (needed by evidence_map generator)
        book_title: the book title
        paths: the OutputPaths instance
        log: ``fn(message, level)``
        update_status: ``fn(status_message)``
        judge_results: optional JudgeResult list from the Summarizer
            (Layer 8 grounding), consumed by the flashcards generator.
        progress_callback: V10.35.0 — optional ``fn(output_key, fraction)``
            called before/after each output so the UI can show a per-row
            progress bar (0.0 = starting, 1.0 = done).
        checkpoint: V13.25.0 (P1.1) — optional Checkpoint instance. When
            provided, output phases that are already marked ``done`` in the
            checkpoint are SKIPPED (phase-level resume). This prevents
            re-running a 30-min TTS phase if the conversion crashed after
            summarization but before podcast_audio completed.

    Returns:
        A dict of ``{output_key: "✅ done" / "❌ failed: msg"}`` for the
        output generation summary.
    """
    results: dict[str, str] = {}

    if not summaries:
        return results

    # V13.23.0: Generate the {Book}.Chapters.md intermediate file whenever
    # packets are enabled.  This file consolidates per-chapter exec summaries
    # + bullet points into a single artifact that serves as:
    # 1. A human-readable checkpoint of what the summarizer produced.
    # 2. The canonical input for the standalone Packets tool.
    # 3. A verification that detected chapters match the TOC.
    # 4. A fallback source for chapter-aligned packets (exec summary is used
    #    as supplementary context when a chapter has too few bullets).
    if getattr(request, "output_packets", False):
        try:
            from core.outputs.chapters_export import write_chapters_md

            chapters_md_path = paths.packets_dir / f"{book_title}.Chapters.md"
            write_chapters_md(summaries, book_title, chapters_md_path)
            log(f"  📄 Chapters file written: {chapters_md_path.name}", "INFO")
            results["chapters_md"] = "✅ done"
        except Exception as e:
            log(f"  ⚠️ Chapters file export failed: {e}", "WARNING")
            results["chapters_md"] = f"❌ failed: {e}"

    try:
        import core.outputs as _outputs

        enabled = [
            (attr, status, msg, getattr(_outputs, cls_name), getattr(paths, sub_attr))
            for attr, status, msg, cls_name, sub_attr in OUTPUT_PLAN
            if getattr(request, attr, False)
        ]
        if not enabled:
            log(
                "  ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).",
                "DEBUG",
            )

        # V13.25.0 (P1.1): Phase-level resume — skip outputs already done.
        # When a checkpoint is provided, any output phase marked "done" is
        # skipped. This prevents re-running a 30-min TTS phase if the
        # conversion crashed after summarization but before podcast_audio.
        if checkpoint:
            _skipped = []
            _to_run = []
            for item in enabled:
                attr = item[0]
                # Map the output_* attr to the checkpoint phase name.
                # OUTPUT_PLAN uses "output_briefing" etc.; checkpoint uses
                # "briefing", "podcast_script", etc.
                _phase_name = attr.replace("output_", "") if attr.startswith("output_") else attr
                # Special mappings for non-obvious names
                _phase_name = {
                    "output_tts": "podcast_audio",
                    "output_evidence_map": "evidence_map",
                    "output_social": "social",
                    "output_obsidian": "obsidian",
                    "output_study_guide": "study_guide",
                    "output_mindmap": "mindmap",
                    "output_packets": "packets",
                    "output_briefing": "briefing",
                    "output_podcast": "podcast_script",
                    "output_flashcards": "flashcards",
                }.get(attr, _phase_name)

                if checkpoint.is_done(_phase_name):
                    _skipped.append((item, _phase_name))
                else:
                    _to_run.append(item)

            if _skipped:
                log(
                    f"  ⏭️ Phase-level resume: skipping {len(_skipped)} already-completed output(s): "
                    + ", ".join(pn for _, pn in _skipped),
                    "INFO",
                )
                for item, _phase_name in _skipped:
                    attr = item[0]
                    results[attr] = "✅ already done (skipped — resume)"
                    if progress_callback:
                        progress_callback(attr, 1.0)
            enabled = _to_run

        for attr, status, msg, gen_cls, out_subdir in enabled:
            update_status(status)
            log(f"  {msg}", "INFO")
            # V10.35.0 (Sprint 7.1): per-output progress callback (0.0 = starting)
            if progress_callback:
                progress_callback(attr, 0.0)
            # V10.34.0 (Sprint 6.6): Retry with exponential backoff (3 attempts:
            # 1s / 2s / 4s).  Before V10.34.0 a single transient failure (Ollama
            # timeout, disk hiccup, VRAM OOM) marked the output as failed
            # permanently.  Now it retries up to 3 times before giving up.
            import time as _time

            _max_retries = 3
            _last_exc = None
            for _attempt in range(1, _max_retries + 1):
                try:
                    gen = gen_cls(request, log_callback=log)
                    # Verbose TTS diagnostics (V10.6.0 extracted).
                    if attr == "output_tts":
                        _log_tts_diagnostics(log, paths, book_title)
                    # Route to the right generate() signature:
                    # - Flashcards take an extra judge_results kwarg (evidence).
                    # - EvidenceMap takes (summaries, segments, book_title, dir).
                    if attr == "output_evidence_map":
                        gen.generate(summaries, segments, book_title, out_subdir)
                    elif attr == "output_flashcards":
                        gen.generate(
                            summaries,
                            book_title,
                            out_subdir,
                            judge_results=judge_results,
                        )
                    else:
                        gen.generate(summaries, book_title, out_subdir)
                    log(
                        f"  ✅ {gen_cls.__name__} completed successfully"
                        + (f" (attempt {_attempt}/{_max_retries})" if _attempt > 1 else ""),
                        "INFO",
                    )
                    results[attr] = "✅ done"
                    _last_exc = None
                    # V10.35.0 (Sprint 7.1): per-output progress (1.0 = done)
                    if progress_callback:
                        progress_callback(attr, 1.0)
                    break  # success — no retry
                except Exception as e:
                    _last_exc = e
                    if _attempt < _max_retries:
                        _backoff = 2 ** (_attempt - 1)  # 1s, 2s, 4s
                        log(
                            f"  ⚠️ {gen_cls.__name__} failed (attempt {_attempt}/{_max_retries}): "
                            f"{e} — retrying in {_backoff}s…",
                            "WARNING",
                        )
                        _time.sleep(_backoff)
                    else:
                        import traceback

                        log(
                            f"  ❌ {gen_cls.__name__} failed after {_max_retries} attempts: {e}",
                            "ERROR",
                        )
                        log(f"  📋 Traceback: {traceback.format_exc()[-500:]}", "DEBUG")
                        results[attr] = f"❌ failed after {_max_retries} retries: {e}"
                        # V10.35.0 (Sprint 7.1): per-output progress (1.0 = done, even on failure)
                        if progress_callback:
                            progress_callback(attr, 1.0)
            # If _last_exc is set and we didn't break, all retries failed

    except ImportError:
        log("  ℹ️ Output Studio module not available (V4.1.0)", "DEBUG")
    except Exception as e:
        log(f"  ⚠️ Output Studio generation skipped: {e}", "DEBUG")

    # V8.0.0 #10: Packets extensions — run after packets are generated.
    if getattr(request, "output_packets", False):
        packets_md = paths.packets_dir / f"{book_title}.Packets.md"
        if packets_md.exists():
            _run_packets_extensions(request, summaries, book_title, paths, log, results)

    return results


def _run_packets_extensions(
    request: Any,
    summaries: list[SummaryResult],
    book_title: str,
    paths: Any,
    log: Callable[[str, str], None],
    results: dict[str, str],
) -> None:
    """Run the V8.0.0 #10 packets extensions (PDF, lecture, audio)."""
    packets_md = paths.packets_dir / f"{book_title}.Packets.md"
    try:
        from core.outputs.packets_extensions import (
            PacketsLectureGenerator,
            PacketsPDFExporter,
        )

        # 1. Styled PDF
        pdf_exporter = PacketsPDFExporter(log_callback=log)
        pdf_exporter.export(
            packets_md,
            paths.packets_dir / f"{book_title}.Packets.pdf",
            book_title,
        )
        results["packets_pdf"] = "✅ done"
    except Exception as e:
        log(f"  ⚠️ Packets PDF export failed: {e}", "WARNING")
        results["packets_pdf"] = f"❌ failed: {e}"
    try:
        # 2. Lecture format
        lecture_gen = PacketsLectureGenerator(request, log_callback=log)
        lecture_gen.generate(summaries, book_title, paths.packets_dir)
        results["packets_lecture"] = "✅ done"
    except Exception as e:
        log(f"  ⚠️ Packets lecture failed: {e}", "WARNING")
        results["packets_lecture"] = f"❌ failed: {e}"
    # 3. Per-packet audio (only if TTS is also enabled)
    if getattr(request, "output_tts", False):
        try:
            from core.outputs.packets_extensions import PacketsAudioGenerator

            audio_gen = PacketsAudioGenerator(request, log_callback=log)
            audio_gen.generate(summaries, book_title, paths.packets_dir)
            results["packets_audio"] = "✅ done"
        except Exception as e:
            log(f"  ⚠️ Packets audio failed: {e}", "WARNING")
            results["packets_audio"] = f"❌ failed: {e}"
