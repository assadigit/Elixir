"""V8.0.0 #9 / V10.6.0: Settings logger — extracted from
converter._log_conversion_settings.

This is the verbose settings dump that appears at the top of every
conversion log.  Extracted into its own module so it's testable and
editable without touching the converter.

V10.6.0 (Phase 8A-2): synced with the inline converter version.  The
extracted module now matches the inline ``_log_conversion_settings``
exactly — including the VRAM budget, page range, segmentation, post-
processing, DOCX, output paths, and resume-status sections that were
missing from the original V8.0.0 extraction.  The converter's inline
method is now a thin delegate to :func:`log_conversion_settings`.

The function takes a "context" dict (everything it needs to know about the
conversion) + a log callback, and emits the settings block.
"""

from __future__ import annotations

import logging
import platform
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def log_conversion_settings(
    ctx: dict[str, Any],
    log: Callable[[str, str], None],
) -> None:
    """Emit the verbose conversion-settings block to the log.

    Args:
        ctx: a dict with keys:
            - ``request`` — the ConversionRequest
            - ``settings`` — the Settings singleton
            - ``paths`` — the OutputPaths instance
            - ``output_dir`` — the book's output directory Path
            - ``app_version`` — the app version string (from VERSION file)
        log: ``fn(message, level)``
    """
    r = ctx["request"]
    settings = ctx["settings"]
    paths = ctx["paths"]
    app_version = ctx.get("app_version", "unknown")

    log("━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━", "INFO")
    log(f"  Input file: {r.input_path.name}", "INFO")
    log(f"  Input path (full): {r.input_path}", "INFO")
    log(f"  Output dir: {ctx['output_dir']}", "INFO")
    log(f"  Source type: {r.source_type}", "INFO")
    log(f"  App version: {app_version}", "INFO")

    # ── Environment diagnostics ───────────────────────────────────────
    log(f"  Python: {platform.python_version()} on {platform.platform()}", "INFO")
    try:
        import torch

        cuda = torch.cuda.is_available()
        log(f"  PyTorch: {torch.__version__}, CUDA available: {cuda}", "INFO")
        if cuda:
            props = torch.cuda.get_device_properties(0)
            log(
                f"  GPU: {props.name}, {props.total_memory / (1024**3):.1f} GB total VRAM",
                "INFO",
            )
    except ImportError:
        log("  PyTorch: NOT installed (no VRAM detection)", "WARNING")
    # Ollama reachability
    try:
        from utils.network import is_ollama_reachable

        log(f"  Ollama reachable (localhost:11434): {is_ollama_reachable()}", "INFO")
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # ── Provider + cloud config (critical for cloud runs) ─────────────
    provider = settings.get("summarisation.provider", "ollama")
    log(f"  Provider: {provider}", "INFO")
    if provider == "cloud":
        base = settings.get("summarisation.api_base_url", "")
        key = settings.get("summarisation.api_key", "")
        masked = (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("(set)" if key else "(empty)")
        log(f"  Cloud base URL: {base}", "INFO")
        log(f"  Cloud API key: {masked}", "INFO")
        log(f"  Cloud model: {settings.get('summarisation.cloud_model', '')}", "INFO")
        log(f"  Cloud max tokens: {settings.get('summarisation.cloud_max_tokens', 16000)}", "INFO")

    # ── VRAM budget (pre-flight snapshot) ─────────────────────────────
    try:
        from core.vram_calculator import calculate_vram_budget, format_vram_report

        estimates, peak, total, rec = calculate_vram_budget(
            ocr_model=r.primary_ocr_model if r.use_llm_ocr else "",
            summarization_model=r.summarisation_model,
            fast_model=r.fast_model,
            heavy_model=r.heavy_model or "",
            translation_backend=settings.get("translation.backend", "")
            if settings.get("translation.enabled")
            else "",
            translation_model=settings.get("translation.model", ""),
            harakat_model=settings.get("translation.harakat_model", ""),
            judge_model=settings.get("translation.judge_model", ""),
            tts_enabled=r.output_tts,
            max_workers=r.max_workers,
        )
        for line in format_vram_report(estimates, peak, total, rec).split("\n"):
            log(line, "INFO")
    except Exception as e:
        log(f"  VRAM budget calc failed: {e}", "DEBUG")

    # ── OCR ───────────────────────────────────────────────────────────
    log(f"  LLM OCR: {r.use_llm_ocr}, Force OCR all: {r.force_ocr_all_pages}", "INFO")
    log(f"  Auto-detect scanned: {r.auto_detect_scanned}", "INFO")
    log(f"  Primary OCR model: {r.primary_ocr_model}", "INFO")
    # V18.2.22 (BUG-5): Warn when LLM OCR is enabled but no OCR model is set.
    # The V18.2.20 conversion log showed "Primary OCR model: " (empty string)
    # with no warning. OCR will silently fall back to the default or fail. This
    # was a config gap in the user's settings.json — the warning makes it
    # visible instead of silent.
    if r.use_llm_ocr and not r.primary_ocr_model:
        log(
            "  ⚠️ LLM OCR is enabled but primary_ocr_model is EMPTY — OCR will "
            "fall back to the default or fail. Set ocr.primary_model in "
            "settings.json (e.g. 'OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest').",
            "WARNING",
        )
    log(f"  OCR retries: {r.ocr_retries}, Image max size: {r.image_max_size}", "INFO")

    # ── Page range + chapters ─────────────────────────────────────────
    if r.page_range_start:
        log(f"  Page range: {r.page_range_start}-{r.page_range_end}", "INFO")
    else:
        log("  Page range: all", "INFO")
    if r.selected_chapters:
        log(f"  Selected chapters: {len(r.selected_chapters)} chapter(s)", "INFO")
        for ch in r.selected_chapters[:10]:
            log(f"    → {ch}", "DEBUG")
        if len(r.selected_chapters) > 10:
            log(f"    … and {len(r.selected_chapters) - 10} more", "DEBUG")

    # ── Segmentation ──────────────────────────────────────────────────
    log(f"  Segmentation: {r.segment_strategy}, Token limit: {r.token_limit_per_segment}", "INFO")
    log(f"  Semantic: {r.enable_semantic_segmentation}, Page group: {r.page_group_size}", "INFO")

    # ── Summarization ─────────────────────────────────────────────────
    log(f"  Generate summaries: {r.generate_summaries}", "INFO")
    log(f"  Model: {r.summarisation_model}", "INFO")
    log(f"  Fast model: {r.fast_model}, Heavy model: {r.heavy_model or '(disabled)'}", "INFO")
    log(f"  Workers (requested): {r.max_workers}, Temperature: {r.temperature}", "INFO")
    # temperature=0 warning (models need min ~0.6)
    if r.temperature < 0.1:
        log(
            f"  ⚠️ Temperature {r.temperature} is very low — many models (especially "
            f"Qwen/Gemma) produce degenerate output or empty responses at t=0. "
            f"Consider 0.2-0.4 if summaries come back empty or repetitive.",
            "WARNING",
        )
    log(
        f"  Self-consistency: {r.self_consistency}, Coverage threshold: {r.coverage_threshold * 100:.0f}%",
        "INFO",
    )
    # V15.1.0: Over-delivery
    _od = getattr(r, "overdeliver_enabled", True)
    _od_t = getattr(r, "overdeliver_target", 0.92)
    if _od and _od_t > r.coverage_threshold:
        log(
            f"  📈 Over-delivery: ENABLED (floor {r.coverage_threshold * 100:.0f}% → target {_od_t * 100:.0f}%)",
            "INFO",
        )
    else:
        log("  Over-delivery: disabled", "DEBUG")
    # V15.1.1: B3 voting status
    _b3 = getattr(r, "b3_voting_enabled", False)
    if _b3:
        log("  🔄 B3 voting: ENABLED (experimental — may dilute depth)", "INFO")
    else:
        log("  B3 voting: disabled (default since V15.1.1)", "DEBUG")
    log(f"  Academic rigor: {r.academic_rigor}", "INFO")
    log(f"  Max context tokens: {r.summarisation_max_context_tokens}", "INFO")
    log(f"  Max output tokens: {r.summarisation_max_output_tokens}", "INFO")

    # ── V18.20.3.2 (audit N9 / P2-c): LLM runtime knobs that were previously
    # invisible in the settings banner. The V18.20.3.1 real-rig audit could
    # not verify two HARD constraints from the log alone: keep_alive (models
    # cold-reloading between chapters vs staying resident) and
    # presence_penalty (1.5 required for Qwen3 Instruct — 0.0 activates
    # thinking mode). keep_alive comes from settings; presence_penalty is
    # read from the model's Modelfile via `ollama show` (the value the
    # Modelfile actually carries — the app deliberately does NOT override
    # it in the API payload).
    try:
        _keep_alive = settings.get("llm.keep_alive", "30m")
        log(f"  Keep-alive: {_keep_alive}", "INFO")
    except Exception as _ka_e:
        logger.debug("keep_alive banner log failed: %s", _ka_e)
    try:
        from core.llm.modelfile_integrity import _run_ollama_show, parse_modelfile

        _mf_text = _run_ollama_show(r.summarisation_model)
        if _mf_text:
            _mf_params = parse_modelfile(_mf_text)
            _pp = _mf_params.get("presence_penalty", "")
            if _pp:
                log(f"  Presence penalty (Modelfile): {_pp}", "INFO")
            else:
                log(
                    "  Presence penalty: (not set in Modelfile — Qwen3 Instruct "
                    "requires 1.5; set it with a custom Modelfile)",
                    "WARNING",
                )
        else:
            log(
                "  Presence penalty: (Modelfile unreadable — run "
                f"`ollama show {r.summarisation_model}` to verify 1.5)",
                "DEBUG",
            )
    except Exception as _pp_e:
        logger.debug("presence_penalty banner log failed: %s", _pp_e)

    # ── Outputs ───────────────────────────────────────────────────────
    outs = []
    if r.include_executive_summary:
        outs.append("exec_summary")
    if r.include_thorough_summary:
        outs.append("thorough_summary")
    if r.include_keypoints:
        outs.append("keypoints")
    if r.simplified_keypoints_enabled:
        outs.append("simplified_keypoints")
    if r.generate_docx:
        outs.append("docx")
    if r.output_briefing:
        outs.append("briefing")
    if r.output_podcast:
        outs.append("podcast_script")
    if r.output_tts:
        outs.append("podcast_audio")
    if r.output_flashcards:
        outs.append("flashcards")
    if getattr(r, "output_packets", False):
        outs.append("packets")
    if r.output_obsidian:
        outs.append("obsidian")
    if r.output_study_guide:
        outs.append("study_guide")
    if r.output_social:
        outs.append("social")
    if r.output_mindmap:
        outs.append("mindmap")
    log(f"  Outputs: {', '.join(outs) if outs else '(none)'}", "INFO")

    # ── Translation ───────────────────────────────────────────────────
    if settings.get("translation.enabled", False):
        # V13.31.0 (#13): default backend is now "ollama" (was "nllb")
        t_backend = settings.get("translation.backend", "ollama")
        log(f"  Translation: enabled, backend={t_backend}", "INFO")
        log(f"    Target lang: {settings.get('translation.default_target_lang', 'fa')}", "INFO")
        if t_backend == "nllb":
            # DEPRECATED (V13.31.0): NLLB branch kept for legacy settings.json
            log(
                f"    NLLB model: {settings.get('translation.nllb_model', '')} [DEPRECATED]", "INFO"
            )
            log(
                "    Warning: NLLB backend is deprecated — switch to 'ollama' (TranslateGemma).",
                "WARNING",
            )
        else:
            log(f"    Ollama model: {settings.get('translation.model', '')}", "INFO")
        log(f"    Harakat model: {settings.get('translation.harakat_model', '')}", "INFO")
        log(
            f"    Judge model: {settings.get('translation.judge_model', '') or '(uses summariser)'}",
            "INFO",
        )
        log(
            f"    Validation: {settings.get('translation.validation_enabled', True)}, max_retries: {settings.get('translation.max_retries', 1)}",
            "INFO",
        )
        tr_outs = settings.get("translation.outputs", {})
        log(f"    Translate outputs: {tr_outs}", "INFO")
    else:
        log("  Translation: disabled", "INFO")

    # ── Post-processing ───────────────────────────────────────────────
    log(f"  Clean markdown: {r.clean_markdown}, Token saver: {r.token_saver}", "INFO")
    log(f"  Content filter: {r.enable_content_filter}", "INFO")
    log(
        f"  Extract tables: {r.extract_tables}, Math: {r.extract_math}, Figures: {r.extract_figure_text}",
        "INFO",
    )
    log(f"  Layout analysis: {r.layout_analysis}", "INFO")

    # ── DOCX ──────────────────────────────────────────────────────────
    if r.generate_docx:
        log(f"  DOCX author: {r.docx_author}, TOC: {r.docx_include_toc}", "INFO")

    # ── Output paths (subfolder layout for debugging) ─────────────────
    log("  Output paths (V7.5 subfolders):", "INFO")
    log(f"    markdown: {paths.full_markdown}", "DEBUG")
    log(f"    summaries: {paths.book_summary}", "DEBUG")
    log(f"    keypoints: {paths.keypoints_md}", "DEBUG")
    log(f"    packets: {paths.packets_dir}", "DEBUG")
    log(f"    podcast: {paths.podcast_dir}", "DEBUG")
    log(f"    logs: {paths.quality_report}", "DEBUG")

    # ── Resume status ─────────────────────────────────────────────────
    resume_enabled = settings.get("summarisation.resume_enabled", True)
    log(
        f"  Resume mode: {'enabled — will skip done chapters' if resume_enabled else 'disabled — reprocess all'}",
        "INFO",
    )
    if resume_enabled:
        try:
            from pathlib import Path as _Path

            from core.pipeline.chapter_resume import detect_processed_chapters

            processed = detect_processed_chapters(_Path(ctx["output_dir"]))
            if processed:
                log(
                    f"  📂 Found {len(processed)} already-processed chapter(s) on disk — will skip these",
                    "INFO",
                )
            else:
                log(
                    "  📂 No previously-processed chapters found — all chapters will be summarized",
                    "INFO",
                )
        except Exception as e:
            log(f"  ⚠️ Resume detection failed: {e}", "DEBUG")

    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")
