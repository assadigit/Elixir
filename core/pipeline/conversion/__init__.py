"""V8.0.0 #9 / V10.6.0: Conversion phase modules.

This package contains logic extracted from the monolithic ``converter.py``
into focused phase modules.  The converter remains the orchestrator (it
owns the pipeline flow + state), but the individual phase logic lives here
for testability and readability.

Current modules (V10.7.0 — all now WIRED into the converter as delegates):
- ``settings_logger`` — the verbose conversion-settings dump (V7.5.1).
  Wired in V10.6.0 Phase 8A-2 via ``converter._log_conversion_settings``.
- ``output_runner`` — the Output Studio generation loop (V8.0.0).
  Wired in V10.6.0 Phase 8A-3 via ``converter.convert()`` (replaces the
  150-line inline output-studio block).
- ``postprocess`` — the markdown post-processing pipeline (V10.7.0).
  Wired in V10.7.0 Phase 8B-2 via ``converter.convert()`` (replaces the
  348-line inline post-processing block: hyphenation, paragraph joining,
  header/footer removal, figure/table extraction, targeted OCR repair,
  content-type auto-detection, layout reorder, advanced document handling,
  vision OCR for figures).

Current modules (V10.8.0 — all WIRED into the converter as delegates):
- ``extraction`` — PDF analysis + OCR + markdown building (V10.8.0).
  Wired in V10.8.0 Phase 8C via ``converter.convert()`` (replaces the
  238-line inline Steps 1–4 block: analyse PDF, extract TOC, extract text,
  build raw markdown).  Returns ExtractionResult or ConversionResult
  (early exit on 0-page/cancel).

- ``segmentation`` — chapter/chunk segmentation (V10.9.0).
  Wired in V10.9.0 Phase 8D via ``converter.convert()`` (replaces the
  103-line inline Step 5 block: extract page markers, pre-locate TOC
  headings, run Segmenter, filter by selected chapters).  Returns
  SegmentationResult or ConversionResult (early exit on cancel).

- ``output_save`` — clean + detect language + save files (V10.10.0).
  Wired in V10.10.0 Phase 8E via ``converter.convert()`` (replaces the
  136-line inline Steps 6–8 block: MarkdownCleaner, language detection,
  book-title detection + folder rename, full-markdown assembly, per-
  segment file saving, checkpoint marking, S19 pre-warm).  Returns
  OutputSaveResult (book_title, detected_lang, source_name).  Mutates
  converter state for folder rename.

- ``summarization`` — LLM summarization orchestration (V10.11.0).
  Wired in V10.11.0 Phase 8F via ``converter.convert()`` (replaces the
  476-line inline Step 9 block: OCR model unload, content filter, skip
  reference sections, ClaimExtractor, GPU thermal profile, ThermalSafety,
  Summarizer, chapter resume, incremental save, judge_results).  Returns
  SummarizationResult or ConversionResult (early exit on cancel/thermal).

All 6 major pipeline phases are now extracted.  The converter's convert()
method is a readable orchestration sequence: extraction (delegated) →
postprocess (delegated) → segment (delegated) → output_save (delegated)
→ summarise (delegated) → outputs (delegated) → validate.  converter.py
dropped from 2939 (V10.5.0) to ~1463 lines (~50% smaller).

Current modules (V0.4.26 — Phase 3 de-monolithization of converter_impl.py,
per the Task 3-plan extraction series):
- ``visual_features`` — cover screenshots, OCR repair, vision-region
  cropper, footnotes (V0.4.19; ConverterVisualMixin, VERBATIM moves).
- ``reporting`` — quality_report.json generation + the end-of-run
  diagnostic summary (V0.4.26 Phase 3 commit 1: ConverterReportingMixin
  + ``run_diagnostic_summary``, VERBATIM moves from converter_impl.py;
  wired via the mixin base + the convert() delegate call).
"""
