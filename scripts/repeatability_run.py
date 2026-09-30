#!/usr/bin/env python3
"""V0.5.16 (repeatability session) — the headless end-to-end chapter run.

Runs the REAL Summarizer 16-stage pipeline (master summary + glossary
architecture + gap-fill + postchecks + verification LAYER) on a chapter
source file through a REAL LLM — without the Qt UI, the PDF extraction,
or a local GGUF model.

WHY THIS SCRIPT EXISTS
──────────────────────
The V0.5.15 result (70/74 = 95% author coverage, 0 hallucinations, ch.6
of the test book) was produced on the owner's rig (llama.cpp +
Ternary-Bonsai-2-27B). The repeatability session's goal is to verify the
result is REPEATABLE on a DIFFERENT chapter — which requires running the
pipeline end-to-end with a real LLM from any machine.

This harness mirrors the conversion-level summarisation phase
(core/pipeline/conversion/summarization.py) piece by piece:

  1. hermetic Settings stand-in (the BenchSettings pattern from
     scripts/bench_chapter.py) — rig-parity values (provider=llamacpp,
     t=0.7, ctx=128000, max_out=32768, coverage floor 85% +
     over-delivery) with the llamacpp endpoint pointed at a
     llama-server-compatible backend (any OpenAI-compat server that
     serves GET /v1/models + POST /v1/chat/completions);
  2. the REAL ConversionRequest + Summarizer construction;
  3. the conversion-level chapter-dict pre-step (concepts via
     extract_concepts_rich + callouts) — the same inputs
     summarize_chapters receives on the rig;
  4. summarize_chapters() — the full 16-stage pipeline, every LLM call
     through the REAL LlamaCppProvider streaming path;
  5. the conversion-level save path: render_summary_markdown +
     verify_and_polish_summary (V0.5.6 checkpoint-path shape — the
     glossary + chapter_heading are passed) + provenance stamp + the
     run-stamped filename — the same artifacts a rig conversion
     produces, auditable by the same tooling.

Content-agnostic (Rule 1): the chapter path, book label, and endpoint
are CLI args; no book/author/chapter strings are hardcoded.

Usage:
  python scripts/repeatability_run.py \
      --chapter "docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md" \
      --out runs/ch1 \
      --llamacpp-url http://127.0.0.1:3031/v1 \
      --llamacpp-model glm-4-plus

Outputs (in --out):
  summaries/001_<heading>_v<ver>_<run_id>_summary.md   the chapter summary
  <label>_v<ver>_<run_id>.conversion.log.md            the full pipeline log
  result.json                                          machine-readable fields
  run_settings.json                                    the exact settings used
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Hermetic Settings stand-in (rig parity) ─────────────────────────────────


class RepeatabilitySettings:
    """Deterministic offline Settings for the repeatability run.

    Mirrors the rig's conversion-settings block (audit/results/
    bench_v0501_ch6_paranoid/*.conversion.log.md: Provider llamacpp,
    t=0.70, max context 128000, max output 32768, coverage 85% +
    over-delivery) with the llamacpp endpoint + model pointed at the
    CLI-provided backend. Drives the REAL ``Settings()`` DI hook
    (``_test_override``) so every in-function ``Settings()`` call in the
    pipeline resolves to this instance (the bench_chapter.py pattern).

    Divergences from the rig (documented for the audit, Rule 2):
      - ``summarisation.model_architecture`` = "llamacpp" (the rig ran
        "single_local"). REASON: the verification LAYER's provider
        routing (core/summarisation/verification_phase.py:711) only
        routes to llama.cpp when arch == "llamacpp"; under the rig's
        "single_local" it built an OllamaProvider against localhost:11434
        — which had no llamacpp-served model, so the LAYER's LLM call
        failed open. "llamacpp" is a real, coded branch and makes the
        V0.5.6 glossary-grounded verification LAYER actually fire
        through the SAME model as the primary path (single-model parity).
      - ``local.chapter_deadline_sec`` = 0 (rig: 600). REASON: cloud
        LLM latency per heavy call (~30-120s) is higher than the rig's
        local GPU; a 600s per-chapter deadline would abort enrichment
        mid-pipeline on nearly every chapter. Disabled = the BenchSettings
        value (no GPU to protect).
    """

    _VALUES: dict[str, object] = {
        "summarisation.provider": "llamacpp",
        "summarisation.llamacpp_base_url": "http://127.0.0.1:3031/v1",
        "summarisation.llamacpp_model": "glm-4-plus",
        "summarisation.llamacpp_api_key": "local",
        "summarisation.llamacpp_context_tokens": 128000,
        "summarisation.llamacpp_max_output_tokens": 32768,
        "summarisation.model": "glm-4-plus",
        "summarisation.temperature": 0.7,
        # see class docstring — routes the verification LAYER to llama.cpp
        "summarisation.model_architecture": "llamacpp",
        "summarisation.cache_enabled": False,
        "summarisation.parallel_stages": False,
        "embedding.enabled": False,  # Jaccard fallback — no embedder model
        "local.http_timeout_sec": 600,
        "local.chapter_deadline_sec": 0,
        "local.vram_recovery_delay_sec": 0,
        "local.b4_max_sections": 3,
        "local.vram_overbudget_policy": "proceed",  # V0.5.14: non-blocking
        "model_temperatures": {},
    }

    def __init__(self, llamacpp_url: str, llamacpp_model: str) -> None:
        self._VALUES = dict(self._VALUES)
        self._VALUES["summarisation.llamacpp_base_url"] = llamacpp_url.rstrip("/")
        self._VALUES["summarisation.llamacpp_model"] = llamacpp_model
        self._VALUES["summarisation.model"] = llamacpp_model

    def get(self, key: str, default: object = None) -> object:
        return self._VALUES.get(key, default)

    def get_ollama_url(self) -> str:
        return "http://localhost:11434"


def install_hermetic_singletons() -> list[tuple[object, str, object]]:
    """Force embedder/spacy singletons to their absent-machine path.

    The bench_chapter.py pattern: ``get_embed_model`` / ``get_spacy_nlp``
    re-probe on every call after a failure (network / import), which adds
    environment-dependent wall time. Patch both to the documented
    None-fallback (Jaccard overlap / no-NER) and restore afterwards.
    """
    import core.llm.model_singletons as ms

    undo: list[tuple[object, str, object]] = []
    for name in ("get_embed_model", "get_spacy_nlp"):
        orig = getattr(ms, name, None)
        if orig is not None:
            setattr(ms, name, lambda *a, **k: None)
            undo.append((ms, name, orig))
    return undo


# ── Chapter loading ──────────────────────────────────────────────────────────


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_chapter(path: Path, max_chars: int = 0) -> tuple[str, str, str]:
    """Load a ground-truth chapter md → (heading, content, frontmatter_json).

    Strips the YAML frontmatter (the ground-truth files carry extraction
    metadata, not chapter content). Heading = the first ``# `` line.
    """
    raw = path.read_text(encoding="utf-8")
    fm = {}
    m = _FRONTMATTER_RE.match(raw)
    if m:
        try:
            import yaml

            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            fm = {}
        raw = raw[m.end() :]
    heading = ""
    for line in raw.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            break
    if not heading:
        heading = path.stem
    if max_chars > 0:
        raw = raw[:max_chars]
    return heading, raw.strip(), json.dumps(fm, ensure_ascii=False)


# ── The run ──────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="headless end-to-end chapter run")
    parser.add_argument("--chapter", required=True, help="path to the chapter source md")
    parser.add_argument("--out", required=True, help="output directory for the run artifacts")
    parser.add_argument("--label", default="", help="book label for the conversion-log filename")
    parser.add_argument("--llamacpp-url", default="http://127.0.0.1:3031/v1")
    parser.add_argument("--llamacpp-model", default="glm-4-plus")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=0,
        help="clamp the source to N chars (smoke tests only; 0 = full chapter)",
    )
    args = parser.parse_args(argv)

    from utils.settings import Settings

    chapter_path = Path(args.chapter).resolve()
    if not chapter_path.exists():
        print(f"chapter not found: {chapter_path}", file=sys.stderr)
        return 1
    out_dir = Path(args.out).resolve()
    summary_folder = out_dir / "summaries"
    summary_folder.mkdir(parents=True, exist_ok=True)

    heading, source, frontmatter = load_chapter(chapter_path, args.max_chars)
    label = args.label or chapter_path.stem

    # ── log capture (rig conversion-log format) ──────────────────────────
    from core.system.provenance import get_app_version, make_run_id, run_started_iso

    run_id = make_run_id()
    app_version = get_app_version()
    started = run_started_iso()
    t0 = time.time()
    log_lines: list[tuple[str, str, str]] = []  # (timestamp, level, msg)

    def log(msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log_lines.append((ts, level, msg))
        print(f"[{ts}] [{level}] {msg}", flush=True)

    log("🚀 Repeatability run — headless end-to-end chapter pipeline", "SUCCESS")
    log(f"  Chapter file: {chapter_path.name}")
    log(f"  Heading: {heading!r}")
    log(f"  Source: {len(source.split())} words / {len(source)} chars")
    log(f"  Frontmatter: {frontmatter[:120]}")
    log(f"  Endpoint: {args.llamacpp_url} (model {args.llamacpp_model})")
    log(f"  Run id: {run_id} (app {app_version})")

    # ── hermetic settings ────────────────────────────────────────────────
    settings = RepeatabilitySettings(args.llamacpp_url, args.llamacpp_model)
    previous_override = Settings._test_override
    Settings._test_override = settings  # type: ignore[assignment]
    undo_singletons = install_hermetic_singletons()

    try:
        return _run_pipeline(
            args,
            log,
            log_lines,
            heading,
            source,
            out_dir,
            summary_folder,
            label,
            run_id,
            app_version,
            started,
            t0,
            settings,
        )
    finally:
        Settings._test_override = previous_override
        for obj, name, orig in undo_singletons:
            setattr(obj, name, orig)


def _run_pipeline(
    args: argparse.Namespace,
    log,
    log_lines: list[tuple[str, str, str]],
    heading: str,
    source: str,
    out_dir: Path,
    summary_folder: Path,
    label: str,
    run_id: str,
    app_version: str,
    started: str,
    t0: float,
    settings: RepeatabilitySettings,
) -> int:
    from core.models import ConversionRequest
    from core.summarisation.summarizer import Summarizer

    # ── ConversionRequest (rig parity) ───────────────────────────────────
    req = ConversionRequest(input_path=Path(args.chapter).resolve(), output_dir=out_dir)
    req.generate_summaries = True
    req.summarisation_model = args.llamacpp_model
    req.summarisation_max_context_tokens = 128000  # rig: 128000
    req.summarisation_max_output_tokens = 32768  # rig: 32768
    req.temperature = 0.7  # rig: 0.70
    req.coverage_threshold = 0.85  # rig: 85%
    req.overdeliver_enabled = True  # rig: ENABLED (85→100%)
    req.self_consistency = False  # rig: False
    req.b3_voting_enabled = False  # default (damages depth)
    req.academic_rigor = False  # rig: False
    req.model_architecture = "single_local"  # rig mode; fast tasks → primary
    req.max_workers = 1  # rig: sequential
    req.source_type = "normal_book"

    log("━━━ Conversion Settings (repeatability harness) ━━━", "INFO")
    for key in (
        "provider=llamacpp",
        "model=" + args.llamacpp_model,
        "t=0.70",
        "max_context=128000",
        "max_output=32768",
        "coverage_floor=0.85",
        "overdeliver=True",
        "workers=1",
        "lang=en",
        "Layer8=disabled (local backend)",
    ):
        log(f"  {key}", "INFO")

    # ── Summarizer + run-id unification (conversion parity) ─────────────
    summarizer = Summarizer(request=req, log_callback=log, language="en", claim_extractor=None)
    summarizer._run_id = run_id
    summarizer._app_version = app_version
    log(f"  Summarizer built (primary_model={summarizer.primary_model!r})", "INFO")

    # ── conversion-level pre-step: segments + deterministic analysis ─────
    # (core/pipeline/conversion/output_save.py:355-380 — the rig writes each
    # segment file then runs analyze_segment_file on it, producing the
    # {segment_stem}_analysis.md twin. The Summarizer's V18.14 author judge +
    # the batch gap-fill (incl. the V0.5.6 final-check round 4) require that
    # artifact — the first V0.5.16 ch.1 run without it skipped the author
    # targeting entirely: "[V17.5] No analysis found for judge".)
    from core.preprocessing.deterministic_analyzer import analyze_segment_file

    try:
        from core.pipeline.conversion.output_save import segment_filename_slug
    except Exception:
        from core.preprocessing.deterministic_analyzer import segment_filename_slug  # type: ignore
    segments_folder = out_dir / "segments"
    segments_folder.mkdir(parents=True, exist_ok=True)
    safe = segment_filename_slug(heading) or "segment_001"
    seg_file = segments_folder / f"001_{safe}.md"
    seg_file.write_text(source, encoding="utf-8")
    try:
        analyze_segment_file(seg_file)
        log(
            f"  📊 V17.2 Deterministic analysis: 1/1 segments analyzed → {seg_file.stem}_analysis.md",
            "INFO",
        )
    except Exception as _e:
        log(f"  ⚠️ Deterministic analysis failed for {seg_file.name}: {_e}", "WARNING")

    # ── conversion-level pre-step: concepts + callouts ───────────────────
    # (core/pipeline/conversion/summarization.py:457-733 — the chapter dicts
    # the Summarizer receives on the rig carry concepts + callouts; the
    # LLM-assisted technique #5 runs through the SAME llamacpp provider.)
    from core.summarisation.text_preprocessor import DeterministicPreprocessor

    pp = DeterministicPreprocessor()
    concepts: list[str] = []
    llm_assisted = False
    try:
        from core.summarisation.text_preprocessor import extract_concepts_rich

        _llm_call_fn = None
        try:
            from core.llm.llm_provider import create_provider
            from utils.settings import Settings as _S

            _prov = create_provider(
                provider="llamacpp", settings=_S(), log_callback=log, supervisor=None
            )
            _summ_model = args.llamacpp_model

            def _llm_call_fn(prompt, __prov=_prov, __model=_summ_model):
                try:
                    _result = __prov.complete(
                        prompt=prompt, temperature=1.0, max_tokens=800, model=__model
                    )
                    if _result and len(_result.strip()) >= 20:
                        return _result
                    _result2 = __prov.complete(
                        prompt=prompt + "\n\nPlease output the response now.",
                        temperature=1.0,
                        max_tokens=800,
                        model=__model,
                    )
                    return _result2 if _result2 and len(_result2.strip()) >= 20 else None
                except Exception:
                    return None

            llm_assisted = True
        except Exception as _e:
            log(f"  ℹ️ concept-extraction provider unavailable ({_e}) — deterministic only", "DEBUG")

        concepts = extract_concepts_rich(source, max_terms=50, llm_call_fn=_llm_call_fn, log_fn=log)
    except Exception as _e:
        log(f"  ⚠️ extract_concepts_rich failed ({_e}) — falling back", "DEBUG")
        try:
            from core.summarisation.text_preprocessor import extract_all_concepts

            concepts = extract_all_concepts(source)
        except Exception:
            concepts = pp.extract_concepts(source)
    callouts = pp.extract_callouts(source)
    log(
        f"  🎯 {len(concepts)} concepts extracted (llm_assisted={llm_assisted}), "
        f"{len(callouts)} callouts",
        "INFO",
    )

    chapter_dicts = [
        {
            "heading": heading,
            "content": source,
            "concepts": concepts,
            "callouts": callouts,
            "start_page": None,
            "end_page": None,
        }
    ]

    # ── the full pipeline ────────────────────────────────────────────────
    log("🚀 summarize_chapters() — the full 16-stage pipeline…", "SUCCESS")
    t_summ0 = time.time()
    results = []
    try:
        results = summarizer.summarize_chapters(chapter_dicts)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        log(f"❌ summarize_chapters crashed: {exc}", "ERROR")
        traceback.print_exc()
    log(f"🏁 summarize_chapters done in {time.time() - t_summ0:.1f}s", "SUCCESS")

    if not results:
        log("❌ no results — run failed", "ERROR")
        _write_artifacts(
            log,
            log_lines,
            out_dir,
            summary_folder,
            label,
            run_id,
            app_version,
            started,
            t0,
            None,
            source,
            heading,
            settings,
            args,
        )
        return 2

    summ = results[0]
    log(
        f"  Result: success={summ.success} bullets={len(summ.bullet_points)} "
        f"exec={len(summ.executive_summary or '')}ch thorough={len(summ.thorough_summary or '')}ch "
        f"in_tok={summ.input_tokens} out_tok={summ.output_tokens} "
        f"glossary_names={len((summ.source_glossary or {}).get('names', []))}",
        "INFO",
    )

    # ── conversion-level save path (checkpoint-path shape) ───────────────
    from core.pipeline.chapter_checkpoint import render_summary_markdown
    from core.summarisation.verification_phase import verify_and_polish_summary

    log("🛡️ V0.4.40 verification + polish LAYER (V0.5.6 glossary wiring)…", "INFO")
    _rendered = render_summary_markdown(summ)
    _rendered, _v_issues = verify_and_polish_summary(
        _rendered,
        source,
        settings,
        log,
        source_glossary=getattr(summ, "source_glossary", None) or None,
        chapter_heading=summ.chapter_heading or heading,
    )
    for _vi in _v_issues or []:
        log(
            f"    ✨ V0.5.1 verification: [{_vi.detector}/{_vi.severity}] {_vi.detail[:120]}",
            "DEBUG" if _vi.severity == "fix" else "WARNING",
        )
    log(f"  Verification LAYER: {len(_v_issues or [])} issues (fixes + flags)", "INFO")

    # provenance stamp (conversion parity)
    try:
        from core.system.provenance import provenance_comment, visible_footer

        _prov_note = provenance_comment(app_version, run_id, started, len(summ.bullet_points))
        if not _rendered.startswith("<!--"):
            _rendered = f"{_prov_note}\n\n{_rendered}"
        _rendered = f"{_rendered.rstrip()}\n{visible_footer(app_version, run_id, started, len(summ.bullet_points))}"
    except Exception as _e:
        log(f"  ⚠️ provenance stamp skipped ({_e})", "WARNING")

    # run-stamped filename (conversion parity: {NNN}_{heading}_v{ver}_{run_id}_summary.md)
    from core.pipeline.converter import Converter
    from core.system.provenance import run_stamp_suffix

    safe_heading = Converter._sanitize_filename(summ.chapter_heading)
    _stamp = run_stamp_suffix(getattr(summ, "app_version", ""), getattr(summ, "run_id", ""))
    sf_name = f"001_{safe_heading}{_stamp}_summary.md"
    sf = summary_folder / sf_name
    sf.write_text(_rendered, encoding="utf-8")
    log(f"💾 Saved chapter summary: summaries/{sf_name}", "INFO")

    _write_artifacts(
        log,
        log_lines,
        out_dir,
        summary_folder,
        label,
        run_id,
        app_version,
        started,
        t0,
        summ,
        source,
        heading,
        settings,
        args,
    )
    return 0 if summ.success else 2


def _write_artifacts(
    log,
    log_lines,
    out_dir,
    summary_folder,
    label,
    run_id,
    app_version,
    started,
    t0,
    summ,
    source,
    heading,
    settings,
    args,
) -> None:
    # conversion log (rig format)
    label_safe = re.sub(r'[:?*<>|"\\/]', "", label).strip() or "chapter"
    log_path = out_dir / f"{label_safe}_v{app_version}_{run_id}.conversion.log.md"
    lines = [
        f"# Conversion Log: {label} (repeatability harness)",
        "",
        f"Started at: {started}",
        "",
        f"<!-- generated-by: Elixir v{app_version} | run_id={run_id} | harness=scripts/repeatability_run.py -->",
        "",
        "---",
        "",
    ]
    lines += [f"[{ts}] [{level}] {msg}" for ts, level, msg in log_lines]
    lines += ["", f"Finished at: {datetime.now().isoformat()}", ""]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nconversion log → {log_path}")

    # result.json (machine-readable audit input)
    result: dict = {
        "run_id": run_id,
        "app_version": app_version,
        "started": started,
        "chapter_file": str(Path(args.chapter).resolve()),
        "heading": heading,
        "source_words": len(source.split()),
        "llamacpp_url": args.llamacpp_url,
        "llamacpp_model": args.llamacpp_model,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    if summ is not None:
        result["summary"] = {
            "success": summ.success,
            "model_used": summ.model_used,
            "executive_summary": summ.executive_summary,
            "bullet_points": list(summ.bullet_points),
            "thorough_summary": summ.thorough_summary,
            "key_distinctions": summ.key_distinctions,
            "theoretical_tensions": summ.theoretical_tensions,
            "scholar_reflections": summ.scholar_reflections,
            "source_excerpts": list(summ.source_excerpts),
            "quarantine_appendix": summ.quarantine_appendix,
            "input_tokens": summ.input_tokens,
            "output_tokens": summ.output_tokens,
            "source_glossary": summ.source_glossary,
            "source_section_map": summ.source_section_map,
            "reproduced_tables": summ.reproduced_tables,
            "reproduced_criteria": summ.reproduced_criteria,
        }
    (out_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # the exact settings (audit provenance, Rule 4)
    (out_dir / "run_settings.json").write_text(
        json.dumps(
            {
                "settings": settings._VALUES,
                "request": {
                    "temperature": 0.7,
                    "coverage_threshold": 0.85,
                    "overdeliver_enabled": True,
                    "summarisation_max_context_tokens": 128000,
                    "summarisation_max_output_tokens": 32768,
                    "model_architecture": "single_local",
                    "max_workers": 1,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"result.json + run_settings.json → {out_dir}")


if __name__ == "__main__":
    sys.exit(main())
