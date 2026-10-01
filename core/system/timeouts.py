"""V0.6.10 (B15): the timeout POLICY leaf — the single home for wall-clock
budget constants (the tts/ named-constant precedent, generalized).

THE PROBLEM (AUDIT_SWOT_V0.6.7 W4, MEASURED): ~60 runtime timeout sites
scattered across core/, utils/ and ui_qt/ carrying 11 distinct magic values
(2/5/10/20/30/60/120/180/300/420/600 seconds) with no central home — the
audit's "Where are timeouts defined? Nowhere centrally — the honest gap"
(F&A question). Changing a policy (e.g. the probe budget on a slow rig)
means greping 60 sites; a value's MEANING is invisible at the call site.

THE LEAF (this module): every value gets ONE named constant + a comment
stating its family and its measured site count. Per the V0.6.10 charter
(O4 mechanical wins), the HIGHEST-CHURN 10 sites are migrated in this
commit (the LLM layer — the files the V0.6.8/V0.6.9 sessions touched
most); every remaining site is FLAGGED below with file:line evidence so
the next waves migrate them mechanically (import + swap, no behavior
change, one commit per family).

Style precedent: core/tts/vibevoice_engine.py
(``VIBEVOICE_LOAD_TIMEOUT_S = 300  # was the inline ``300`` in _ensure_model``).

Content-agnostic (Rule 1): the constants encode INFRASTRUCTURE budgets
(HTTP probes, subprocess walls, generation caps), never book/chapter
properties.
"""

from __future__ import annotations

# ── the 11-value policy table (measured V0.6.10; counts = inline sites) ─────

# 2 s — reachability probes + thread joins (5 sites: dependency_checker's
# is_ollama_reachable, utils/dependencies CLI version probes ×2,
# hardware_monitor's thread join, ocr dialog's quick checks).
SUBSECOND_PROBE_TIMEOUT_S = 2

# 5 s — the model-list / health-probe family. These run on UI THREADS in
# several dialogs (the V0.6.8 review-loop finding: the shared transports'
# 10 s default had silently doubled worst-case UI-thread blocks on
# blackholed endpoints) — keep this budget SMALL (measured: 15 sites —
# the 6 migrated in V0.6.10 + the 9 below, ALL migrated in V0.6.11
# wave 8 together with the markdown-styler tight sibling).
UI_PROBE_TIMEOUT_S = 5

# 3 s — the markdown-styler's tight probe budget (the V0.6.8 review-loop
# restored latency budget; its own leaf value per the V0.6.10 note —
# migrated in V0.6.11 wave 8).
UI_PROBE_TIGHT_TIMEOUT_S = 3

# 10 s — CLI/subprocess polling (nvidia-smi, ollama CLI, thermal safety,
# llamacpp model listing; 10 sites, all flagged).
CLI_POLL_TIMEOUT_S = 10

# 20 s — the hardware_monitor full CLI sweep (1 site, flagged).
CLI_SWEEP_TIMEOUT_S = 20

# 30 s — the openai-compat batch/async request family (4 sites, flagged).
API_BATCH_TIMEOUT_S = 30

# 60 s — session POSTs + model downloads + OCR subprocess (4 sites,
# flagged; the tts/ normalizer already names its own 60 s family inline).
HTTP_FETCH_TIMEOUT_S = 60

# 120 s — the fast-model call family (dispatcher fallback, coverage
# futures, pipeline fast-model timeouts, OCR/TOC vision calls; 9 sites,
# flagged).
FAST_LLM_TIMEOUT_S = 120

# 180 s — the slow-request family: the Claude provider constructor (the
# one migrated site below), the dispatcher's openai-compat POST, the
# semantic segmenter, the TOC extractor, the vision heading labeler /
# figure extractor, neutts' JSON-line read (7 sites).
SLOW_LLM_TIMEOUT_S = 180

# 300 s — the default LOCAL generation request timeout: the Ollama +
# OpenAI-compat provider constructors, the pipeline's concept-extraction
# timeouts, the podcast script generator, the new-outputs LLM calls (10
# sites — 4 migrated below, 6 flagged).
LLM_REQUEST_TIMEOUT_S = 300

# 420 s — the simplified-keypoints whole-call budget (1 site, flagged).
KEYPOINTS_WHOLE_CALL_TIMEOUT_S = 420

# 600 s — the long-run family: model pull, transcription, the summarizer's
# primary timeout (3 sites, flagged).
LONG_RUN_TIMEOUT_S = 600


# ── the 10 highest-churn sites migrated in V0.6.10 (this commit) ────────────
#
# The LLM layer — the files the V0.6.8/V0.6.9 sessions churned most
# (B4 provider attrs, B5 shared transports, the review-loop timeout-budget
# restorations). Each swap is import + constant, value byte-identical:
#
#   core/llm/llm_provider_impl.py  :241  OllamaProvider(timeout=300)
#   core/llm/llm_provider_impl.py  :267  list_llamacpp_models(timeout=5)
#   core/llm/llm_provider_impl.py  :313  OpenAICompatProvider(timeout=300)
#   core/llm/llm_provider_impl.py  :327  OpenAICompatProvider(timeout=300)
#   core/llm/llm_provider_impl.py  :341  ClaudeProvider(timeout=180)
#   core/llm/ollama_provider.py    :404  GET /api/ps probe (timeout=5)
#   core/llm/llamacpp_provider.py  :455  models probe (timeout=5)
#   core/summarisation/primary_call.py:96  provider probe (timeout=5)
#   core/podcast/script_generator.py:1327  GET /api/tags probe (timeout=5)
#   core/system/dependency_checker.py:388  ollama reachability (timeout=5)


# ── the FLAGGED remainder (the remaining waves) ─────────────────────────────
#
# NOT migrated yet, per the charter ("migrate the highest-churn 10 first,
# flag the rest"). Each future wave: import the constant, swap the literal,
# run the file's tests, one commit. Evidence snapshot (V0.6.10 line numbers;
# V0.6.11 note: line numbers drift as waves land — grep the value):
#
# MIGRATED in V0.6.11 wave 8 — the UI-probe family (10 sites): the
#   normalizer _tags_url probe, the dependencies /api/tags probes ×3, the
#   translation/transcribe/podcast model pickers, the ai_model_section
#   listings ×3, and the markdown-styler tight probe (its own leaf value
#   UI_PROBE_TIGHT_TIMEOUT_S above, per the V0.6.10 note).
#
#
#
#
#
# SLOW_LLM_TIMEOUT_S (180) remaining:
#   core/summarisation/llm_dispatcher.py:567  openai-compat POST
#   core/segmentation/semantic_segmenter.py:49  segmenter budget
#   core/pdf/toc_extractor.py:213  TOC LLM call
#   core/pdf/llm_heading_labeler.py:107  heading labeler
#   core/pdf/vision_figure_extractor.py:57  figure extractor
#   core/tts/neutts_engine.py:851  JSON-line read
#   ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py:1085
#
# LLM_REQUEST_TIMEOUT_S (300) remaining:
#   core/pipeline/conversion/summarization.py:831,875,919,942  provider timeouts
#   core/podcast/script_generator.py:1310  script generation
#   core/outputs/new_outputs.py:135,165  new-output LLM calls
#   ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py:1356
#
# KEYPOINTS_WHOLE_CALL_TIMEOUT_S (420):
#   core/summarisation/simplified_keypoints.py:123
#
# LONG_RUN_TIMEOUT_S (600):
#   core/llm/model_manager.py:191  model pull
#   core/summarisation/summarizer_init.py:161  primary timeout
#   core/transcribe/transcribe_service.py:69  transcription
#
# CLI_SWEEP_TIMEOUT_S (20):
#   core/system/hardware_monitor.py:1021  full CLI sweep

__all__ = [
    "SUBSECOND_PROBE_TIMEOUT_S",
    "UI_PROBE_TIMEOUT_S",
    "UI_PROBE_TIGHT_TIMEOUT_S",
    "CLI_POLL_TIMEOUT_S",
    "CLI_SWEEP_TIMEOUT_S",
    "API_BATCH_TIMEOUT_S",
    "HTTP_FETCH_TIMEOUT_S",
    "FAST_LLM_TIMEOUT_S",
    "SLOW_LLM_TIMEOUT_S",
    "LLM_REQUEST_TIMEOUT_S",
    "KEYPOINTS_WHOLE_CALL_TIMEOUT_S",
    "LONG_RUN_TIMEOUT_S",
]
