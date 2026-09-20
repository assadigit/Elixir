#!/usr/bin/env python3
"""Phase 1.2 (V0.14) — per-stage timing harness for the chapter pipeline.

Runs the golden chapter through the REAL ``Summarizer`` (real ``__init__``,
real ``_summarize_inner`` 16-stage pipeline) with a **mock LLM** whose
latency is bucketed into three classes, then reports per-stage wall-clock
timings. This is the "before" measurement every later "after" (Phase 5
de-monolithization, Phase 6 performance) is compared against — see
``docs/ROADMAP_V0.12.md`` Phase 1 and ``docs/baseline/timings_V0.13.md``.

Why a mock LLM: the pipeline's wall-clock on the real rig is ~95% LLM
inference time, which dwarfs the Python-side stage costs and varies with
GPU load. A latency-bucketed mock makes the *structure* of the pipeline
measurable deterministically: how many calls each chapter fires, in what
latency class, and how the stages overlap (or serialize) in parallel mode.

Latency classes (simulated, before ``--latency-scale``):
  HEAVY  20 s — primary/chunked summarization calls (max_tokens >= 8192,
                 or no max_tokens + a long prompt carrying the chapter)
  MEDIUM  8 s — secondary calls (self-review, gap-fill, judges, ~2-8k tokens)
  LIGHT   3 s — auxiliary calls (consolidation, preflight, small checks)

The response for every call is a deterministic canned XML built from the
golden chapter's own sentences (grounded by construction → the filter /
judge stages keep the bullets and the full pipeline shape is exercised).
No network, no GPU, no model files — safe to run anywhere.

Usage:
  python scripts/bench_chapter.py                          # sequential, fast (scale 0.05)
  python scripts/bench_chapter.py --parallel --workers 2   # parallel chapter mode
  python scripts/bench_chapter.py --profile                # + cProfile hotspots
  python scripts/bench_chapter.py --latency-scale 1.0      # realistic full latency
  python scripts/bench_chapter.py --chapters 4             # replicate the chapter N×
  python scripts/bench_chapter.py --chapter academic       # any tests/golden/<name>/ fixture
  python scripts/bench_chapter.py --json out.json          # machine-readable timings
  python scripts/bench_chapter.py --save-golden            # freeze outputs (Phase 1.4)

Golden chapters (V0.17 / Phase 4.1): academic, nonfiction (V0.14) plus
academic_tables, scanned_ocr, multicolumn, farsi (V0.17 — the Phase-4
edge-case expansion: tables/citations, OCR artifacts, naive two-column
extraction interleave, non-Latin script). The farsi chapter runs the
Summarizer with language="fa" (see GOLDEN_LANGUAGES).

Exit code 0 = pipeline completed for every chapter; 1 = configuration or
pipeline failure (details on stderr); 2 = pipeline ran but a chapter failed.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import re
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Latency model ───────────────────────────────────────────────────────────

LATENCY_CLASSES: dict[str, float] = {"light": 3.0, "medium": 8.0, "heavy": 20.0}

# Phase 4.1 (V0.17): per-chapter Summarizer language override. English is
# the default; the farsi golden chapter exercises the language="fa" path
# (Persian output instructions, non-Latin postcheck behavior).
GOLDEN_LANGUAGES: dict[str, str] = {"farsi": "fa"}


def chapter_language(name: str) -> str:
    """Summarizer language for a golden chapter ("en" unless overridden)."""
    return GOLDEN_LANGUAGES.get(name, "en")


# Prompt-size heuristic: primary/chunked prompts embed the chapter text and
# are an order of magnitude longer than aux prompts (bullet lists, judges).
_LONG_PROMPT_CHARS = 6000


def classify_call(prompt: str, max_tokens: int | None) -> str:
    """Map an LLM call to its latency class (see module docstring)."""
    mt = max_tokens or 0
    if mt >= 8192:
        return "heavy"
    if max_tokens is None and len(prompt) > _LONG_PROMPT_CHARS:
        return "heavy"  # primary call: full chapter in the prompt, default budget
    if mt >= 2048 or len(prompt) > _LONG_PROMPT_CHARS:
        return "medium"
    return "light"


# ── Deterministic canned responses ──────────────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    sents = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    return sents or [text.strip()]


def _trim_words(text: str, limit: int) -> str:
    words = text.split()
    return " ".join(words[:limit])


def build_primary_response(source: str) -> str:
    """A grounded XML summary built ONLY from the source's own sentences.

    Every bullet/exec/thorough line is a verbatim source sentence, so the
    F4 source-overlap, thinking-filter and content-judge stages all PASS and
    the full pipeline shape (filters → judge → ship) is exercised. Bullets
    are sampled EVENLY ACROSS THE WHOLE CHAPTER: the content judge
    hard-rejects below 30% keyword coverage, and keyword coverage is
    measured against the source's top-30 n-grams — a summary drawn only
    from the chapter's opening would under-cover the rest. Determinism is
    what matters for the freeze (Phase 1.4): the SAME source always yields
    the SAME response.
    """
    sents = _sentences(re.sub(r"^#+ .*$", "", source, flags=re.MULTILINE))
    body = [s for s in sents if len(s.split()) >= 4] or sents or ["The chapter content."]
    exec_sents = body[:3]

    n_bullets = min(10, len(body))
    step = max(1, len(body) // n_bullets) if n_bullets else 1
    bullet_sents = [body[i] for i in range(0, len(body), step)][:n_bullets] or body[:1]
    thorough_sents = body[:40]  # F1 length cap is 1500 words; fixtures are ≪

    bullets = "\n".join(f"- {_trim_words(s, 40)}" for s in bullet_sents)
    return (
        f"<executive_summary>{' '.join(_trim_words(s, 60) for s in exec_sents)}"
        f"</executive_summary>\n"
        f"<bullet_points>\n{bullets}\n</bullet_points>\n"
        f"<thorough_summary>{' '.join(_trim_words(s, 80) for s in thorough_sents)}"
        f"</thorough_summary>\n"
        f"<key_distinctions>{_trim_words(body[0], 30)} versus {_trim_words(body[1], 30)}"
        f"</key_distinctions>\n"
        f"<theoretical_tensions>{_trim_words(body[2], 30)} compared with "
        f"{_trim_words(body[3], 30)}</theoretical_tensions>"
    )


def build_aux_response(prompt: str, source_response: str) -> str:
    """Canned response for secondary/aux LLM calls (deterministic per shape).

    Most aux phases (self-review, grounding, consolidation, gap-fill,
    scholar reflection) parse free text or short lists and degrade
    gracefully when the shape does not match — their LLM latency (the thing
    being measured) is identical either way.
    """
    p = prompt.lower()
    if "bullet" in p and ("consolidat" in p or "merge" in p or "dedup" in p):
        # Consolidation: echo a compact merged list (keeps the pipeline on
        # its "consolidation produced output" branch).
        return "- merged point retaining all grounded details"
    if "json" in p:
        return '{"verdict": "pass", "grounded": true, "gaps": []}'
    if "review" in p or "reflection" in p or "gap" in p:
        return (
            "The summary is grounded in the source and covers the key claims. "
            "No missing concepts were identified. No additions are required."
        )
    # Default: a grounded short paragraph (never empty — the empty-retry
    # path would fire a second call and skew the call counts).
    return _trim_words(_sentences(source_response)[0], 25) or "The chapter is covered."


# ── Hermetic Settings stand-in (offline, deterministic) ─────────────────────


class BenchSettings:
    """Deterministic offline Settings for the bench (via Settings._test_override).

    Mirrors the ``_FakeSettings`` pattern from tests/test_group_b_characterization.py
    but drives the REAL ``Settings()`` DI hook (``_test_override``), so every
    ``Settings()`` call anywhere in the pipeline — including in-function
    ``from utils.settings import Settings`` imports — resolves to this
    instance. No ~/.elixir/settings.json is ever read: the baseline is
    reproducible on any machine.
    """

    _VALUES: dict[str, Any] = {
        "summarisation.provider": "ollama",
        "summarisation.b4_threshold_tokens": 12000,
        "summarisation.cross_chapter_context": True,
        "local.http_timeout_sec": 600,
        "local.chapter_deadline_sec": 600,
        "local.vram_recovery_delay_sec": 0,  # no GPU sleeps in the bench
        "embedding.enabled": False,  # Jaccard fallback — deterministic, no model
        "model_temperatures": {},
    }

    # Phase 6 (V0.19): per-run overrides (the parallel-stages levers for the
    # --parallel-stages acceptance measurement). Empty by default — the
    # default bench run is bit-for-bit the pre-V0.19 configuration.
    _EXTRA: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._EXTRA:
            return self._EXTRA[key]
        return self._VALUES.get(key, default)

    def get_ollama_url(self) -> str:
        return "http://localhost:11434"


# ── Latency-bucketed mock LLM ───────────────────────────────────────────────


@dataclass
class LlmCallRecord:
    cls: str
    latency: float
    prompt_chars: int
    max_tokens: int | None
    wall: float  # actual slept time (s)


@dataclass
class MockLlmStats:
    calls: list[LlmCallRecord] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {"light": 0, "medium": 0, "heavy": 0}
        for c in self.calls:
            out[c.cls] += 1
        return out

    def simulated_total(self) -> float:
        return sum(c.latency for c in self.calls)

    def wall_total(self) -> float:
        return sum(c.wall for c in self.calls)


def install_hermetic_singletons() -> list[tuple[Any, str, Any]]:
    """Force the embedder/spacy singletons to their absent-machine path.

    ``get_embed_model`` (Ollama ``/api/embed`` probe) and ``get_spacy_nlp``
    (``spacy.load`` attempt) RE-PROBE on every call after a failure — the
    failure is not cached — so a single bench chapter fires ~8 network /
    import probes whose wall time is environment-dependent (connection
    refused vs. a live server vs. a model download). The bench measures the
    PIPELINE, not the machine's port 11434: patch both to the documented
    None-fallback (Jaccard overlap / no-NER — the same code path as a rig
    without those models) and restore afterwards.
    """
    import core.llm.model_singletons as ms

    undo = []
    for name in ("get_embed_model", "get_spacy_nlp"):
        orig = getattr(ms, name, None)
        if orig is not None:
            setattr(ms, name, lambda *a, **k: None)
            undo.append((ms, name, orig))
    return undo


def install_mock_llm(
    summarizer: Any,
    source_response: str,
    scale: float,
    stats: MockLlmStats,
    log: Callable[[str, str], None],
    source_response_source: str = "",
) -> None:
    """Replace ``summarizer._call_llm`` with the latency-bucketed mock.

    Every LLM call in the pipeline funnels through ``_call_llm`` (verified:
    ``_call_llm_with_empty_retry`` and ``_call_llm_structured`` both wrap
    it; the structured/JSON path is disabled in production — V18.20.2.0
    A16 — so XML is the real path).
    """

    # Phase 6 b3 mode: the FIRST primary-shaped call returns a deliberately
    # NARROW summary (first 2 body sentences only) so the coverage check
    # fails and the pipeline enters B3 multi-sample voting; the B3 samples
    # (also primary-shaped) get the full grounded response. Deterministic:
    # a counter over primary-class calls.
    narrow_first = getattr(install_mock_llm, "_b3_mode", False)
    primary_seen = {"n": 0}

    def _narrow_response(source: str) -> str:
        sents = _sentences(re.sub(r"^#+ .*$", "", source, flags=re.MULTILINE))
        body = [s for s in sents if len(s.split()) >= 4] or sents[:1]
        two = " ".join(_trim_words(s, 60) for s in body[:2])
        one = _trim_words(body[0], 40)
        return (
            f"<executive_summary>{two}</executive_summary>\n"
            f"<bullet_points>\n- {one}\n</bullet_points>\n"
            f"<thorough_summary>{two}</thorough_summary>\n"
            f"<key_distinctions>{one} versus {one}</key_distinctions>\n"
            f"<theoretical_tensions>{one} compared with {one}</theoretical_tensions>"
        )

    def _mock_call_llm(prompt, model=None, temperature=None, max_tokens=None):
        cls = classify_call(prompt, max_tokens)
        latency = LATENCY_CLASSES[cls] * scale
        t0 = time.perf_counter()
        if latency > 0:
            time.sleep(latency)
        wall = time.perf_counter() - t0
        stats.calls.append(
            LlmCallRecord(
                cls=cls,
                latency=latency,
                prompt_chars=len(prompt),
                max_tokens=max_tokens,
                wall=wall,
            )
        )
        log(f"[mock-llm] {cls} call: {latency:.2f}s simulated, {len(prompt)} chars", "DEBUG")
        if len(prompt) > _LONG_PROMPT_CHARS or max_tokens is None:
            # Primary/chunked shape → the grounded chapter summary.
            if narrow_first:
                primary_seen["n"] += 1
                if primary_seen["n"] == 1:
                    return _narrow_response(source_response_source)
            return source_response
        return build_aux_response(prompt, source_response)

    summarizer._call_llm = _mock_call_llm


# ── Per-stage timing ────────────────────────────────────────────────────────


@dataclass
class StageTiming:
    name: str
    calls: int = 0
    total: float = 0.0

    def add(self, dur: float) -> None:
        self.calls += 1
        self.total += dur


class StageTimer:
    """Wraps named methods with perf_counter timing (instance or class level).

    ``wrap_instance`` patches bound methods on one object (the Summarizer).
    ``wrap_class`` patches methods on the BulletPipeline CLASS — the pipeline
    object is constructed inside ``_summarize_inner``, so class-level is the
    only interception point. Both restore the original on ``restore()``.
    """

    def __init__(self) -> None:
        self.stages: dict[str, StageTiming] = {}
        self._instance_undo: list[tuple[Any, str, Any]] = []
        self._class_undo: list[tuple[type, str, Any]] = []

    def wrap_instance(self, obj: Any, names: list[str]) -> None:
        for name in names:
            orig = getattr(obj, name, None)
            if orig is None:
                continue
            self._wrap_one(obj, name, orig)

    def _wrap_one(self, obj: Any, name: str, orig: Any) -> None:
        stage = self.stages.setdefault(name, StageTiming(name))

        def timed(*args, __orig=orig, __stage=stage, **kwargs):
            t0 = time.perf_counter()
            try:
                return __orig(*args, **kwargs)
            finally:
                __stage.add(time.perf_counter() - t0)

        setattr(obj, name, timed)
        self._instance_undo.append((obj, name, orig))

    def wrap_class(self, cls: type, names: list[str]) -> None:
        for name in names:
            orig = getattr(cls, name, None)
            if orig is None:
                continue
            stage = self.stages.setdefault(f"pipeline.{name}", StageTiming(f"pipeline.{name}"))

            def timed(*args, __orig=orig, __stage=stage, **kwargs):
                t0 = time.perf_counter()
                try:
                    return __orig(*args, **kwargs)
                finally:
                    __stage.add(time.perf_counter() - t0)

            setattr(cls, name, timed)
            self._class_undo.append((cls, name, orig))

    def restore(self) -> None:
        for obj, name, orig in self._instance_undo:
            setattr(obj, name, orig)
        for cls, name, orig in self._class_undo:
            setattr(cls, name, orig)
        self._instance_undo.clear()
        self._class_undo.clear()


# Summarizer stages (method names verified against _summarize_inner, V0.13).
SUMMARIZER_STAGES = [
    "_prepare_text",
    "_summarize_with_model",
    "_parse_response",
    "_filter_thinking_bullets",
    "_normalize_bullets",
    "_consolidate_bullets",
    "_semantic_dedup_bullets",
    "_compute_coverage",
    "_verify_bullets",
    "_recover_quarantined",
    "_scholar_reflection",
    "_map_reduce_summarize",
    "_section_map_reduce",
    "_multi_sample_summarize",
    "_ensure_additive_sections",
    "_ensure_exec_from_thorough",
    "_anti_false_precision_check",
    "_call_dedicated_thorough_with_fallback",
]

# BulletPipeline stages (delegated from _summarize_inner since V10.32).
PIPELINE_STAGES = [
    "run_self_consistency_and_review",
    "apply_academic_factual_verification",
    "salvage_empty_output",
    "apply_f1_length_validation",
    "apply_f4_source_overlap",
    "apply_phase22_semantic_fact_check",
    "apply_f3_reading_level",
    "run_informational_checks",
    "run_content_judge",
    "run_gap_fill",
]


# ── Bench run ───────────────────────────────────────────────────────────────


def build_mapreduce_chapter(base_source: str, target_tokens: int = 60000) -> tuple[str, str]:
    """Phase 6 bench mode: a deterministic OVERSIZED chapter (>40k tokens)
    that routes through the map-reduce path (the strategy decision sends
    src_tokens > MAP_REDUCE_THRESHOLD = 40000 to chunked map+reduce at the
    legacy 32k window). Built by cycling the golden source's sentences with
    numbered stanza prefixes — deterministic, content varies per stanza so
    paragraph chunking produces ~12 real chunks."""
    sents = _sentences(re.sub(r"^#+ .*$", "", base_source, flags=re.MULTILINE))
    body = [s for s in sents if len(s.split()) >= 4] or sents or ["The content."]
    out: list[str] = []
    stanza = 0
    approx_chars = target_tokens * 4
    while sum(len(p) for p in out) < approx_chars:
        stanza += 1
        para = " ".join(body[(stanza + i) % len(body)] for i in range(min(6, len(body))))
        out.append(f"Section {stanza}. {para}")
    text = "# Synthetic Map-Reduce Benchmark Chapter\n\n" + "\n\n".join(out)
    return "Synthetic Map-Reduce Benchmark Chapter", text


def load_golden_chapter(name: str) -> tuple[str, str]:
    path = PROJECT_ROOT / "tests" / "golden" / name / "source_chapter.md"
    if not path.exists():
        raise FileNotFoundError(f"golden chapter not found: {path}")
    text = path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0].lstrip("# ").strip() or f"Golden {name}"
    return first_line, text


def build_summarizer(
    output_dir: Path,
    parallel: bool,
    workers: int,
    log: Callable[[str, str], None],
    language: str = "en",
) -> Any:
    """Construct a REAL Summarizer under hermetic settings (no network/GPU)."""
    from core.models import ConversionRequest
    from core.summarisation.summarizer import Summarizer

    req = ConversionRequest(input_path=PROJECT_ROOT / "VERSION", output_dir=output_dir)
    req.generate_summaries = True
    req.max_workers = workers if parallel else 1
    # Phase 6 bench modes: the b3 mode drives the multi-sample path.
    if getattr(build_summarizer, "_b3_mode", False):
        try:
            req.b3_voting_enabled = True
        except Exception:
            pass
    # Phase 6 mapreduce mode: pin the LEGACY 32k window so the strategy
    # decision routes the >40k-token synthetic chapter to map-reduce (the
    # request default window is 131072 — a 46k chapter FITS single-pass
    # there, which is the modern behavior, not the path being measured).
    # The synthetic model name is NOT in the model registry, so the V0.09
    # (P5) registry raise (32768 → 65536 for known models) does not apply —
    # the legacy cascade (src > 40000 → map_reduce, 4000-token chunks) is
    # the measured path.
    if getattr(build_summarizer, "_mapreduce_mode", False):
        req.summarisation_max_context_tokens = 32768
        req.summarisation_model = "bench-synthetic-mr:12b"
    s = Summarizer(request=req, log_callback=log, language=language, claim_extractor=None)
    # Force the execution mode regardless of any model-profile defaults.
    s.max_workers = workers if parallel else 1
    return s


def run_bench(args: argparse.Namespace) -> dict[str, Any]:
    from core.summarisation.bullet_pipeline import BulletPipeline
    from utils.settings import Settings

    if args.bench_mode == "mapreduce":
        _base_heading, base_source = load_golden_chapter(args.chapter)
        heading, source = build_mapreduce_chapter(base_source)
    else:
        heading, source = load_golden_chapter(args.chapter)
    source_response = build_primary_response(source)

    # Phase 6 (V0.19): the acceptance configuration — turn the
    # parallel-stages levers ON (the roadmap's "after soak" configuration,
    # measured deterministically). Default OFF = the shipped default.
    if args.parallel_stages:
        BenchSettings._EXTRA = {
            "summarisation.parallel_stages": True,
            "summarisation.parallel_stages_max_workers": args.parallel_workers,
        }
    else:
        BenchSettings._EXTRA = {}
    build_summarizer._b3_mode = args.bench_mode == "b3"
    install_mock_llm._b3_mode = args.bench_mode == "b3"
    build_summarizer._mapreduce_mode = args.bench_mode == "mapreduce"

    log_lines: list[tuple[str, str]] = []

    def log(msg: str, level: str = "INFO") -> None:
        log_lines.append((level, msg))
        if args.verbose:
            print(f"  [{level}] {msg}")

    chapters = [
        {"heading": heading if i == 0 else f"{heading} (copy {i + 1})", "content": source}
        for i in range(args.chapters)
    ]

    stats = MockLlmStats()
    timer = StageTimer()
    previous_override = Settings._test_override
    Settings._test_override = BenchSettings()  # type: ignore[assignment]
    undo_singletons = install_hermetic_singletons()

    results: list[Any] = []
    prof: cProfile.Profile | None = cProfile.Profile() if args.profile else None
    t_total0 = time.perf_counter()

    try:
        with tempfile.TemporaryDirectory(prefix="elixir-bench-") as tmp:
            out_dir = Path(tmp)
            s = build_summarizer(
                out_dir, args.parallel, args.workers, log, language=chapter_language(args.chapter)
            )
            install_mock_llm(
                s,
                source_response,
                args.latency_scale,
                stats,
                log,
                source_response_source=source,
            )

            timer.wrap_instance(s, SUMMARIZER_STAGES)
            timer.wrap_class(BulletPipeline, PIPELINE_STAGES)

            if prof is not None:
                prof.enable()
            try:
                results = s.summarize_chapters(chapters)
            finally:
                if prof is not None:
                    prof.disable()
                timer.restore()
    finally:
        Settings._test_override = previous_override
        for obj, name, orig in undo_singletons:
            setattr(obj, name, orig)
        BenchSettings._EXTRA = {}
        build_summarizer._b3_mode = False
        install_mock_llm._b3_mode = False
        build_summarizer._mapreduce_mode = False

    wall = time.perf_counter() - t_total0

    ok = bool(results) and all(getattr(r, "success", False) for r in results)
    counts = stats.counts()

    report: dict[str, Any] = {
        "mode": "parallel" if args.parallel else "sequential",
        "workers": args.workers if args.parallel else 1,
        "chapter": args.chapter,
        "bench_mode": args.bench_mode,
        "parallel_stages": bool(args.parallel_stages),
        "chapters": len(chapters),
        "latency_scale": args.latency_scale,
        "pipeline_ok": ok,
        "wall_clock_sec": round(wall, 3),
        "llm_calls": counts,
        "llm_calls_total": len(stats.calls),
        "llm_simulated_sec": round(stats.simulated_total(), 3),
        "llm_sleep_sec": round(stats.wall_total(), 3),
        "stages": {
            name: {"calls": st.calls, "total_sec": round(st.total, 4)}
            for name, st in sorted(timer.stages.items(), key=lambda kv: kv[1].total, reverse=True)
        },
        "results": [
            {
                "heading": r.chapter_heading,
                "success": r.success,
                "error_msg": getattr(r, "error_msg", ""),
                "bullets": len(r.bullet_points),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
            }
            for r in results
        ],
    }

    if len(results) == 1:
        # Always expose the freezable dict for single-chapter runs (the
        # freeze test reads it; --save-golden additionally writes it).
        report["freeze_output"] = build_frozen(results[0], heading, source, args.chapter)

    if args.save_golden:
        report["golden"] = save_golden(args, results, heading, source)

    print_report(report)
    if prof is not None:
        print_profile(prof, args.profile_out)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nJSON timings written to {args.json}")
    return report


def build_frozen(r: Any, heading: str, source: str, chapter_name: str) -> dict[str, Any]:
    """Phase 1.4: build the deterministic freeze dict for one chapter result.

    Only content fields are frozen — provenance (run_id/timestamps) is
    intentionally excluded. ``save_golden`` writes this to disk; the freeze
    test (tests/test_golden_freeze.py) compares it against the committed
    fixture. Single source of truth for the field list.
    """
    return {
        "engine": "scripts/bench_chapter.py --save-golden (mock LLM, deterministic)",
        "chapter": chapter_name,
        "input": {
            "heading": heading,
            "content_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        },
        "output": {
            "success": r.success,
            "executive_summary": r.executive_summary,
            "bullet_points": list(r.bullet_points),
            "thorough_summary": r.thorough_summary,
            "key_distinctions": r.key_distinctions,
            "theoretical_tensions": r.theoretical_tensions,
            "scholar_reflections": r.scholar_reflections,
            "source_excerpts": list(r.source_excerpts),
            "quarantine_appendix": r.quarantine_appendix,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        },
    }


def save_golden(
    args: argparse.Namespace, results: list[Any], heading: str, source: str
) -> dict[str, Any]:
    """Phase 1.4: write the frozen pipeline output (deterministic content only).

    Regenerate with ``--save-golden``; the freeze test
    (tests/test_golden_freeze.py) asserts byte-identical equality on CI.
    """
    if len(results) != 1:
        raise SystemExit("--save-golden requires exactly one chapter (--chapters 1)")
    frozen = build_frozen(results[0], heading, source, args.chapter)
    out_dir = PROJECT_ROOT / "tests" / "golden" / args.chapter
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "pipeline_output.json"
    out_path.write_text(json.dumps(frozen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Golden pipeline output frozen → {out_path}")
    return {"path": str(out_path.relative_to(PROJECT_ROOT))}


def print_report(report: dict[str, Any]) -> None:
    mode = report["mode"]
    n = report["chapters"]
    print("\n" + "=" * 72)
    _extra = ""
    if report.get("bench_mode", "golden") != "golden":
        _extra += f", bench={report['bench_mode']}"
    if report.get("parallel_stages"):
        _extra += ", PARALLEL-STAGES ON"
    print(f"  BENCH CHAPTER — {mode} mode, {n} chapter(s), scale {report['latency_scale']}{_extra}")
    print("=" * 72)
    status = "OK" if report["pipeline_ok"] else "FAILED"
    print(f"  pipeline: {status}   wall-clock: {report['wall_clock_sec']:.2f}s")
    c = report["llm_calls"]
    print(
        f"  LLM calls: {report['llm_calls_total']} "
        f"(heavy {c['heavy']} × {LATENCY_CLASSES['heavy']}s, "
        f"medium {c['medium']} × {LATENCY_CLASSES['medium']}s, "
        f"light {c['light']} × {LATENCY_CLASSES['light']}s)"
    )
    sim = report["llm_simulated_sec"]
    wall = report["wall_clock_sec"]
    ratio = (sim / wall) if wall > 0 else 0.0
    if ratio > 1.05:
        overlap = f"{ratio * 100:.0f}% of wall — OVERLAP (parallelism working)"
    elif report["mode"] == "parallel":
        overlap = f"{ratio * 100:.0f}% of wall — serialized (no overlap gained)"
    else:
        overlap = (
            f"{ratio * 100:.0f}% of wall — sequential + fixed overhead "
            f"(init, prompt build, filters)"
        )
    print(f"  simulated LLM time: {sim:.2f}s total = {overlap}")
    per_ch = report["llm_calls_total"] / n if n else 0
    print(f"  calls per chapter (mean): {per_ch:.1f}")

    print("\n  Per-stage wall-clock (all chapters, incl. nested LLM sleep):")
    print(f"  {'stage':<44} {'calls':>6} {'total s':>9}")
    print("  " + "-" * 62)
    for name, st in report["stages"].items():
        print(f"  {name:<44} {st['calls']:>6} {st['total_sec']:>9.3f}")

    print("\n  Chapter results:")
    for r in report["results"]:
        mark = "✓" if r["success"] else "✗"
        print(
            f"   {mark} {r['heading'][:44]:<46} bullets={r['bullets']:<3} "
            f"in={r['input_tokens']} tok out={r['output_tokens']} tok"
        )
        if r.get("error_msg"):
            print(f"      error: {r['error_msg'][:100]}")


def print_profile(prof: cProfile.Profile, out_path: str | None) -> None:
    print("\n" + "=" * 72)
    print("  cProfile — top 25 by cumulative time")
    print("=" * 72)
    stream = io.StringIO()
    ps = pstats.Stats(prof, stream=stream)
    ps.sort_stats("cumulative").print_stats(25)
    print(stream.getvalue())
    if out_path:
        prof.dump_stats(out_path)
        print(f"  Full profile dumped → {out_path} (inspect: snakeviz / pstats)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 1.2 per-stage timing harness (mock LLM, deterministic)"
    )
    parser.add_argument(
        "--chapter",
        default="nonfiction",
        help="golden fixture name under tests/golden/ (default: nonfiction)",
    )
    parser.add_argument(
        "--chapters", type=int, default=1, help="replicate the chapter N times (default 1)"
    )
    parser.add_argument(
        "--parallel", action="store_true", help="parallel chapter mode (ThreadPoolExecutor)"
    )
    parser.add_argument("--workers", type=int, default=2, help="max_workers in parallel mode")
    parser.add_argument(
        "--latency-scale",
        type=float,
        default=0.05,
        help="multiply the 3/8/20s classes (default 0.05 = fast structurally-accurate run)",
    )
    parser.add_argument("--profile", action="store_true", help="wrap the run in cProfile")
    parser.add_argument("--profile-out", default=None, help="dump .prof file (implies --profile)")
    parser.add_argument("--json", default=None, help="write the report as JSON to this path")
    parser.add_argument(
        "--save-golden",
        action="store_true",
        help="freeze pipeline output to tests/golden/<chapter>/pipeline_output.json",
    )
    parser.add_argument("--verbose", action="store_true", help="stream pipeline log to stdout")
    parser.add_argument(
        "--parallel-stages",
        action="store_true",
        help="turn the Phase-6 intra-chapter overlap levers ON "
        "(summarisation.parallel_stages — the acceptance configuration)",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=4,
        help="summarisation.parallel_stages_max_workers when --parallel-stages (default 4)",
    )
    parser.add_argument(
        "--bench-mode",
        choices=["golden", "b3", "mapreduce"],
        default="golden",
        help="golden: the frozen single-pass chapter (default). b3: first primary "
        "deliberately narrow → B3 multi-sample voting path. mapreduce: synthetic "
        ">40k-token chapter → chunked map-reduce path.",
    )
    args = parser.parse_args(argv)

    if args.profile_out and not args.profile:
        args.profile = True
    if args.save_golden and args.chapters != 1:
        parser.error("--save-golden requires --chapters 1 (deterministic single-chapter freeze)")
    if args.parallel and args.chapters < 2:
        print("note: --parallel with 1 chapter runs sequentially (nothing to overlap)")

    try:
        report = run_bench(args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary: report and exit 1
        print(f"bench failed: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
    return 0 if report.get("pipeline_ok") else 2


if __name__ == "__main__":
    sys.exit(main())
