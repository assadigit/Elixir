"""V0.14 (Phase 1.4) — Golden pipeline FREEZE tests.

Locks two things that pure unit tests can't see:

1. **Prompt-bank identity** — every template under ``prompts/`` must match
   ``tests/golden/prompt_manifest.json`` (path + sha256). Prompts ARE
   behavior; an accidental edit/reformat/merge mistake now fails CI even
   when no functional test notices.

2. **End-to-end pipeline output** — running the golden chapters through the
   REAL Summarizer (real ``_summarize_inner``, all 16 stages) with the
   deterministic mock LLM from ``scripts/bench_chapter.py`` must reproduce
   ``tests/golden/<name>/pipeline_output.json`` EXACTLY (exec summary,
   bullets, thorough, additive sections, quarantine appendix, token counts).
   This is the pre-net for Phase 5 (de-monolithization): any refactor that
   changes behavior by a single character fails here BEFORE it reaches the
   real rig's golden-master audit.

Determinism contract (verified during V0.14 freeze): identical output across
runs and across ``PYTHONHASHSEED`` values — no set-iteration-order leakage,
no timestamps in the frozen fields (provenance run_id/timestamps are
deliberately excluded from the fixture).

Regeneration procedure (when a change is INTENTIONAL):
    python scripts/bench_chapter.py --save-golden                    # nonfiction
    python scripts/bench_chapter.py --chapter academic --save-golden # academic
    python scripts/prompt_manifest.py                               # if prompts changed

Run: ``pytest tests/test_golden_freeze.py -v``
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Load the bench harness (scripts/ is not a package) ──────────────────────

_spec = importlib.util.spec_from_file_location(
    "bench_chapter", _project_root / "scripts" / "bench_chapter.py"
)
bench = importlib.util.module_from_spec(_spec)
sys.modules["bench_chapter"] = bench
_spec.loader.exec_module(bench)

GOLDEN_DIRS = ["academic", "nonfiction"]
FREEZE_LATENCY_SCALE = 0.0  # zero sleep: the freeze measures CONTENT, not time


@pytest.fixture(autouse=True)
def _reset_runtime_singletons():
    """Snapshot/restore the module singletons a real Summarizer run touches.

    Mirrors the autouse fixture in test_group_b_characterization.py — a real
    Summarizer construction + run flips one-time-warning flags in
    content_judge_impl / text_preprocessor_impl and may set
    llm_provider_impl._keep_alive_cache. Without the reset these leak into
    downstream tests (order-dependent failures — see the V18.19.1.4 note).
    """
    import core.llm.llm_provider_impl as lpi
    import core.summarisation.content_judge_impl as cji
    import core.summarisation.text_preprocessor_impl as tpi

    snapshot = {
        "cji.warned_embedding_disabled": getattr(cji, "_warned_embedding_disabled", None),
        "cji.warned_semantic_fallback": getattr(cji, "_warned_semantic_fallback", None),
        "cji.st_model": getattr(cji, "_st_model", None),
        "tpi.warned_no_embed_model": getattr(tpi, "_warned_no_embed_model", None),
        "tpi.spacy_nlp": getattr(tpi, "_SPACY_NLP", None),
        "lpi.keep_alive_cache": getattr(lpi, "_keep_alive_cache", None),
    }
    yield
    cji._warned_embedding_disabled = snapshot["cji.warned_embedding_disabled"]
    cji._warned_semantic_fallback = snapshot["cji.warned_semantic_fallback"]
    cji._st_model = snapshot["cji.st_model"]
    tpi._warned_no_embed_model = snapshot["tpi.warned_no_embed_model"]
    if hasattr(tpi, "_SPACY_NLP"):
        tpi._SPACY_NLP = snapshot["tpi.spacy_nlp"]
    lpi._keep_alive_cache = snapshot["lpi.keep_alive_cache"]


def _run_freeze(chapter_name: str) -> dict:
    """Run the deterministic pipeline over one golden chapter, in-process."""
    args = types.SimpleNamespace(
        chapter=chapter_name,
        chapters=1,
        parallel=False,
        workers=1,
        latency_scale=FREEZE_LATENCY_SCALE,
        profile=False,
        profile_out=None,
        json=None,
        save_golden=False,
        verbose=False,
    )
    # save_golden=False: the freeze test must NOT rewrite the fixture it is
    # comparing against — it captures the frozen dict instead.
    report = bench.run_bench(args)
    assert report["pipeline_ok"], (
        f"[{chapter_name}] pipeline failed — freeze comparison is meaningless"
    )
    return report


# ── 1) Prompt manifest ──────────────────────────────────────────────────────


def test_prompt_manifest_matches_prompt_bank():
    """Every prompts/ file must match its committed sha256 (drift = failure)."""
    manifest_mod_spec = importlib.util.spec_from_file_location(
        "prompt_manifest", _project_root / "scripts" / "prompt_manifest.py"
    )
    pm = importlib.util.module_from_spec(manifest_mod_spec)
    sys.modules["prompt_manifest"] = pm
    manifest_mod_spec.loader.exec_module(pm)

    current = pm.build_manifest()
    manifest_path = _project_root / "tests" / "golden" / "prompt_manifest.json"
    assert manifest_path.exists(), "tests/golden/prompt_manifest.json is missing"
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Identity comparison: files + aggregate hash. The informational
    # generated_for_version field is excluded (a VERSION bump must never
    # trip the prompt gate — prompts didn't change).
    assert pm.manifest_identity(current) == pm.manifest_identity(committed), (
        "Prompt bank drifted from the frozen manifest. If the change is "
        "intentional: python scripts/prompt_manifest.py && re-freeze golden "
        "outputs (see this file's docstring)."
    )


def test_prompt_manifest_wellformed():
    """Sanity: manifest covers ≥50 files (the V0.14 bank) with valid hashes."""
    manifest = json.loads(
        (_project_root / "tests" / "golden" / "prompt_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == 1
    assert manifest["file_count"] >= 50
    assert len(manifest["files"]) == manifest["file_count"]
    for entry in manifest["files"]:
        assert len(entry["sha256"]) == 64
        assert entry["bytes"] > 0
    # The primary-call prompt bank (top-level variants selected by
    # Summarizer.active_prompt) and the summarisation/ aux prompts the
    # pipeline's secondary phases render must all be under the manifest.
    paths = {e["path"] for e in manifest["files"]}
    assert "default.md" in paths  # primary prompt (active_prompt default)
    assert "summarisation/self_review.md" in paths


# ── 2) Frozen pipeline outputs ──────────────────────────────────────────────


@pytest.mark.parametrize("chapter_name", GOLDEN_DIRS)
def test_pipeline_output_frozen(chapter_name: str):
    """Byte-identical pipeline output vs the committed fixture (Phase 5 pre-net)."""
    fixture_path = _project_root / "tests" / "golden" / chapter_name / "pipeline_output.json"
    assert fixture_path.exists(), (
        f"missing freeze fixture {fixture_path} — regenerate with "
        f"scripts/bench_chapter.py --chapter {chapter_name} --save-golden"
    )
    committed = json.loads(fixture_path.read_text(encoding="utf-8"))

    report = _run_freeze(chapter_name)
    produced = report["freeze_output"]["output"]

    # Input identity: the fixture pins the source chapter by hash.
    heading, source = bench.load_golden_chapter(chapter_name)
    import hashlib

    src_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert committed["input"]["content_sha256"] == src_sha, (
        f"[{chapter_name}] source chapter changed — the fixture must be "
        f"re-frozen deliberately, not silently"
    )

    # Output identity: every content field must match exactly.
    assert produced == committed["output"], (
        f"[{chapter_name}] pipeline output drifted from the frozen fixture.\n"
        f"Produced: {json.dumps(produced, indent=2)[:2000]}\n"
        f"Expected: {json.dumps(committed['output'], indent=2)[:2000]}"
    )


@pytest.mark.parametrize("chapter_name", GOLDEN_DIRS)
def test_frozen_fixture_has_content(chapter_name: str):
    """The frozen fixtures must be real summaries, not empty hulls."""
    fixture = json.loads(
        (_project_root / "tests" / "golden" / chapter_name / "pipeline_output.json").read_text(
            encoding="utf-8"
        )
    )
    out = fixture["output"]
    assert out["success"] is True
    assert len(out["executive_summary"].split()) >= 10
    assert len(out["bullet_points"]) >= 5
    assert len(out["thorough_summary"].split()) >= 30
