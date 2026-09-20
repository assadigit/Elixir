#!/usr/bin/env python3
"""Phase 4.2/4.3 (V0.17) — deterministic summary-quality scorecards + regression gate.

Computes a machine-parsable quality scorecard for every golden chapter under
``tests/golden/`` and enforces a regression gate against the committed
baseline (``tests/golden/eval_baseline.json``). This is the CI-runnable half
of the evaluation framework in ``docs/EVALUATION_FRAMEWORK.md`` — the four-
pillar LLM judge stays the real-rig audit; this harness provides the
DETERMINISTIC proxy that can gate every commit:

Metrics (all deterministic, no LLM in the loop):

  ROUGE-L            LCS-based F1 over Unicode word tokens (candidate vs the
                     chapter's curated ``reference_summary.md``). Self-contained
                     implementation — tokenization is ``\\w+`` on the lowercased
                     text, so Latin and non-Latin (Farsi) chapters score alike.
  faithfulness       mean char-8-gram containment of every substantive claim
                     sentence (exec + bullets + thorough + additive sections)
                     in the source chapter — "what fraction of the summary's
                     character evidence exists in the source".
  hallucination_rate fraction of substantive claims whose char-8-gram
                     containment in the source is < 0.5 (a claim with less than
                     half of its character evidence in the source is counted
                     as unsupported — the deterministic claims-without-evidence
                     proxy).
  coverage           fraction of the source's top-30 content keywords (≥4
                     chars, stopword-filtered, frequency-ranked) present in
                     the candidate — the content-judge measure.
  length_policy      per-section compliance against the REAL production
                     targets (``core.summarisation.length_policy`` — the same
                     bounds the prompts instruct), never invented bounds.
  f4_min_overlap     minimum ``compute_source_overlap`` over the shipped
                     bullets — the REAL F4 production filter value. (Latin-
                     only by production design: returns 1.0 for non-Latin
                     bullets — a documented limitation, not a pass.)

Scorecard schema (matches docs/EVALUATION_FRAMEWORK.md Part 2 so real-rig
LLM-judge audits and CI scorecards are diffable): ``summary_id``,
``overall_score``, ``factual_consistency_score``, ``coverage_score``,
``clarity_score``, ``hallucinations_detected``, ``critical_omissions_detected``,
``verdict``, ``justification`` — plus a ``metrics`` block with the raw numbers
above. Deterministic score formulas (documented, mechanical):

  factual_consistency_score = clamp(round(10 - 10 * hallucination_rate))
  coverage_score            = clamp(round(10 * coverage))
  clarity_score             = clamp(round(10 - 5 * fragment_rate - 2 * n_sections_off_target))
  verdict = FAIL if factual_consistency_score < 6 or coverage_score < 5   (framework rule)

Regression gate (``--check``) — fails on ANY of:
  * prompt-bank identity change (manifest hash) without re-baselining
  * ROUGE-L F1 drop > 0.02, faithfulness drop > 0.02
  * hallucination-rate rise > 0.02, coverage drop > 0.05, f4_min drop > 0.05
  * any length section compliant→non-compliant, or verdict PASS→FAIL
Improvements never trip the gate (one-directional).

Usage:
  python scripts/eval_summary.py                  # re-run pipeline per chapter + print scorecards
  python scripts/eval_summary.py --from-fixtures  # evaluate the frozen fixtures (fast)
  python scripts/eval_summary.py --check          # gate vs committed baseline (exit 1 on regression)
  python scripts/eval_summary.py --save-baseline  # (re)write tests/golden/eval_baseline.json
  python scripts/eval_summary.py --json out.json  # also write the full scorecard JSON

Intentional-change procedure (prompt edit / pipeline change / re-freeze):
  1. python scripts/bench_chapter.py --chapter <name> --save-golden   (re-freeze outputs)
  2. python scripts/prompt_manifest.py                               (if prompts changed)
  3. python scripts/eval_summary.py --save-baseline                  (re-baseline scorecards)
  4. Review the scorecard DIFF in the commit — quality must not regress
     without the numbers being shown (that review is the point of the gate).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GOLDEN_ROOT = PROJECT_ROOT / "tests" / "golden"
BASELINE_PATH = GOLDEN_ROOT / "eval_baseline.json"

# ── Metric primitives (pure functions — unit-tested in tests/test_p4_eval_gate.py) ──

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Sentence terminators: Latin (. ! ?), Arabic/Persian (؟ ۔).
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?؟۔])\s+")

# A claim with less than half its character evidence in the source counts as
# unsupported. 0.5 sits high enough that verbatim/trimmed source sentences
# (containment ≈ 1.0) pass easily while a fabricated sentence (containment
# ≈ 0.0-0.2) fails — the mutation test pins both directions.
_HALLUCINATION_CONTAINMENT_FLOOR = 0.5

_CHAR_NGRAM = 8

_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "as",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "from",
        "at",
        "which",
        "not",
        "but",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "their",
        "they",
        "them",
        "then",
        "there",
        "here",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "him",
        "me",
        "my",
        "mine",
        "what",
        "when",
        "where",
        "who",
        "whom",
        "whose",
        "how",
        "into",
        "over",
        "under",
        "about",
        "after",
        "before",
        "between",
        "during",
        "through",
        "above",
        "below",
        "also",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "now",
    ]
)

# Deterministic keyword-coverage window (mirrors the content judge's top-30).
_COVERAGE_TOP_N = 30


def tokens(text: str) -> list[str]:
    """Unicode word tokens, lowercased (Latin + Farsi alike)."""
    return _WORD_RE.findall(text.lower())


def _lcs_len(a: list[str], b: list[str]) -> int:
    """Length of the longest common subsequence (rolling-row DP)."""
    if not a or not b:
        return 0
    if len(b) > len(a):
        a, b = b, a  # keep the rolling row on the shorter sequence
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def rouge_l(candidate: str, reference: str) -> dict[str, float]:
    """ROUGE-L (precision / recall / F1) over Unicode word tokens."""
    c, r = tokens(candidate), tokens(reference)
    if not c or not r:
        return {"precision": 0.0, "recall": 0.0, "fmeasure": 0.0}
    lcs = _lcs_len(c, r)
    precision = lcs / len(c)
    recall = lcs / len(r)
    fmeasure = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "fmeasure": round(fmeasure, 4),
    }


def _normalize_for_containment(text: str) -> str:
    return _WS_RE.sub(" ", text.lower()).strip()


def char_ngrams(text: str, n: int = _CHAR_NGRAM) -> list[str]:
    t = _normalize_for_containment(text)
    if not t:
        return []
    return [t[i : i + n] for i in range(max(1, len(t) - n + 1))]


def sentence_containment(sentence: str, source: str, n: int = _CHAR_NGRAM) -> float:
    """Fraction of the sentence's char n-grams found in the source."""
    grams = char_ngrams(sentence, n)
    if not grams:
        return 1.0  # nothing to verify — vacuously supported
    src = _normalize_for_containment(source)
    hits = sum(1 for g in grams if g in src)
    return hits / len(grams)


def claims_from_output(output: dict[str, Any]) -> list[str]:
    """Flatten the summary output into claim sentences (the F4-layer shape).

    Bullets are individual claims; exec/thorough/additive sections are split
    into sentences. Ordering is stable (exec, bullets, thorough, key
    distinctions, theoretical tensions) so scorecards are deterministic.
    """
    parts: list[str] = []
    exec_sum = output.get("executive_summary") or ""
    if exec_sum:
        parts.append(exec_sum)
    parts.extend(output.get("bullet_points") or [])
    thorough = output.get("thorough_summary") or ""
    if thorough:
        parts.append(thorough)
    for extra in ("key_distinctions", "theoretical_tensions"):
        text = output.get(extra) or ""
        if text:
            parts.append(text)
    claims: list[str] = []
    for p in parts:
        claims.extend(s.strip() for s in _SENT_SPLIT_RE.split(p) if s.strip())
    return claims


def grounding_metrics(claims: list[str], source: str) -> dict[str, float]:
    """Faithfulness (mean containment) + hallucination rate over claims."""
    substantive = [c for c in claims if len(tokens(c)) >= 4] or claims
    if not substantive:
        return {"faithfulness": 1.0, "hallucination_rate": 0.0, "claims": 0.0}
    containments = [sentence_containment(c, source) for c in substantive]
    hallucinated = [
        c
        for c, k in zip(substantive, containments, strict=True)
        if k < _HALLUCINATION_CONTAINMENT_FLOOR
    ]
    return {
        "faithfulness": round(statistics.fmean(containments), 4),
        "hallucination_rate": round(len(hallucinated) / len(substantive), 4),
        "claims": float(len(substantive)),
    }


def source_top_keywords(source: str, top_n: int = _COVERAGE_TOP_N) -> list[str]:
    words = [w for w in tokens(source) if len(w) >= 4 and w not in _STOPWORDS]
    return [w for w, _ in Counter(words).most_common(top_n)]


def keyword_coverage(candidate: str, source: str, top_n: int = _COVERAGE_TOP_N) -> float:
    """Fraction of the source's top-N content keywords present in the candidate."""
    top = source_top_keywords(source, top_n)
    if not top:
        return 1.0
    cand_tokens = set(tokens(candidate))
    hits = sum(1 for w in top if w in cand_tokens)
    return round(hits / len(top), 4)


def length_policy_metrics(output: dict[str, Any], source: str) -> dict[str, Any]:
    """Per-section compliance vs the REAL production targets (length_policy)."""
    from core.summarisation.length_policy import (
        bullet_target,
        count_source_words,
        executive_target,
        thorough_target,
    )

    w = count_source_words(source)
    exec_words = len((output.get("executive_summary") or "").split())
    thorough_words = len((output.get("thorough_summary") or "").split())
    n_bullets = len(output.get("bullet_points") or [])

    e_lo, e_hi = executive_target(w)
    t_lo, t_hi = thorough_target(w)
    b_lo, b_hi = bullet_target(w)

    sections = {
        "exec": {
            "words": exec_words,
            "target": [e_lo, e_hi],
            "compliant": e_lo <= exec_words <= e_hi,
        },
        "thorough": {
            "words": thorough_words,
            "target": [t_lo, t_hi],
            "compliant": t_lo <= thorough_words <= t_hi,
        },
        "bullets": {
            "count": n_bullets,
            "target": [b_lo, b_hi],
            "compliant": b_lo <= n_bullets <= b_hi,
        },
    }
    return {
        "source_words": w,
        "sections": sections,
        "compliant": all(s["compliant"] for s in sections.values()),
    }


def f4_min_overlap(bullets: list[str], source: str) -> float:
    """Min compute_source_overlap over shipped bullets (the REAL F4 value).

    Production function is Latin-only (returns 1.0 when a bullet has no
    5+ char Latin content words) — for the farsi chapter this metric is
    vacuously 1.0; the char-gram faithfulness metric carries the signal.
    """
    from core.summarisation.text_preprocessor import compute_source_overlap

    if not bullets:
        return 1.0
    return round(min(compute_source_overlap(b, source) for b in bullets), 4)


# ── Scorecard assembly ──────────────────────────────────────────────────────


def _clamp_score(x: float) -> int:
    return max(0, min(10, round(x)))


def compute_scorecard(
    chapter: str,
    output: dict[str, Any],
    source: str,
    reference: str,
    prompt_manifest_hash: str,
) -> dict[str, Any]:
    """Deterministic quality scorecard (EVALUATION_FRAMEWORK schema + raw metrics)."""
    claims = claims_from_output(output)
    grounding = grounding_metrics(claims, source)

    candidate_text = " ".join(
        [output.get("executive_summary") or ""]
        + list(output.get("bullet_points") or [])
        + [output.get("thorough_summary") or ""]
        + [output.get("key_distinctions") or "", output.get("theoretical_tensions") or ""]
    ).strip()

    rl = rouge_l(candidate_text, reference)
    cov = keyword_coverage(candidate_text, source)
    lp = length_policy_metrics(output, source)
    f4_min = f4_min_overlap(output.get("bullet_points") or [], source)

    # Clarity proxy: sentence integrity + length-target adherence.
    non_empty = [c for c in claims if c] or [""]
    fragment_rate = sum(1 for c in non_empty if len(tokens(c)) < 4) / len(non_empty)
    sections_off = sum(1 for s in lp["sections"].values() if not s["compliant"])

    factual = _clamp_score(10 - 10 * grounding["hallucination_rate"])
    coverage_score = _clamp_score(10 * cov)
    clarity = _clamp_score(10 - 5 * fragment_rate - 2 * sections_off)

    top10 = source_top_keywords(source, 10)
    cand_tokens = set(tokens(candidate_text))
    omissions = sum(1 for w in top10 if w not in cand_tokens)

    overall = _clamp_score((factual + coverage_score + clarity) / 3)
    verdict = "FAIL" if (factual < 6 or coverage_score < 5) else "PASS"

    return {
        # ── EVALUATION_FRAMEWORK.md Part 2 schema ──
        "summary_id": chapter,
        "overall_score": overall,
        "factual_consistency_score": factual,
        "coverage_score": coverage_score,
        "clarity_score": clarity,
        "hallucinations_detected": int(
            round(grounding["hallucination_rate"] * grounding["claims"])
        ),
        "critical_omissions_detected": omissions,
        "verdict": verdict,
        "justification": (
            f"deterministic proxy — rouge_l_f1={rl['fmeasure']:.3f}, "
            f"hallucination_rate={grounding['hallucination_rate']:.1%}, "
            f"coverage={cov:.1%}, faithfulness={grounding['faithfulness']:.1%}"
        ),
        # ── raw metrics (gate inputs) ──
        "metrics": {
            "rouge_l": rl,
            "faithfulness": grounding["faithfulness"],
            "hallucination_rate": grounding["hallucination_rate"],
            "claims": grounding["claims"],
            "coverage": cov,
            "f4_min_overlap": f4_min,
            "fragment_rate": round(fragment_rate, 4),
            "length_policy": lp,
        },
        "prompt_manifest_hash": prompt_manifest_hash,
    }


# ── Regression gate ─────────────────────────────────────────────────────────


def compare_scorecards(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Direction-aware regressions of ``current`` vs ``baseline`` (empty = pass).

    One-directional by design: improvements never trip the gate.
    """
    problems: list[str] = []
    name = current.get("summary_id", "<unknown>")

    if baseline.get("prompt_manifest_hash") != current.get("prompt_manifest_hash"):
        problems.append(
            f"[{name}] prompt bank changed (manifest hash "
            f"{str(baseline.get('prompt_manifest_hash'))[:12]}… → "
            f"{str(current.get('prompt_manifest_hash'))[:12]}…) — re-run the "
            f"intentional-change procedure (bench --save-golden, prompt_manifest, "
            f"eval --save-baseline) and show the scorecard diff in the commit"
        )

    bm, cm = baseline.get("metrics", {}), current.get("metrics", {})

    def _delta(key: str) -> float:
        return float(cm.get(key, 0.0)) - float(bm.get(key, 0.0))

    if _delta("faithfulness") < -0.02:
        problems.append(
            f"[{name}] faithfulness regressed: {bm.get('faithfulness')} → {cm.get('faithfulness')}"
        )
    if _delta("hallucination_rate") > 0.02:
        problems.append(
            f"[{name}] hallucination_rate regressed: {bm.get('hallucination_rate')} → "
            f"{cm.get('hallucination_rate')}"
        )
    if _delta("coverage") < -0.05:
        problems.append(f"[{name}] coverage regressed: {bm.get('coverage')} → {cm.get('coverage')}")
    if _delta("f4_min_overlap") < -0.05:
        problems.append(
            f"[{name}] f4_min_overlap regressed: {bm.get('f4_min_overlap')} → {cm.get('f4_min_overlap')}"
        )

    bl_rl = float(bm.get("rouge_l", {}).get("fmeasure", 0.0))
    cr_rl = float(cm.get("rouge_l", {}).get("fmeasure", 0.0))
    if cr_rl - bl_rl < -0.02:
        problems.append(f"[{name}] ROUGE-L F1 regressed: {bl_rl} → {cr_rl}")

    bl_lp = bm.get("length_policy", {}).get("sections", {})
    cr_lp = cm.get("length_policy", {}).get("sections", {})
    for section in bl_lp:
        if bl_lp[section].get("compliant") and not cr_lp.get(section, {}).get("compliant", True):
            problems.append(f"[{name}] length_policy section '{section}' compliant → non-compliant")

    if baseline.get("verdict") == "PASS" and current.get("verdict") == "FAIL":
        problems.append(f"[{name}] verdict PASS → FAIL")
    return problems


# ── Runner ──────────────────────────────────────────────────────────────────


def golden_chapters() -> list[str]:
    """Golden chapter dirs carrying the full eval triple (source/ref/output)."""
    out = []
    for d in sorted(GOLDEN_ROOT.iterdir()):
        if not d.is_dir():
            continue
        if (
            (d / "source_chapter.md").exists()
            and (d / "reference_summary.md").exists()
            and (d / "pipeline_output.json").exists()
        ):
            out.append(d.name)
    return out


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def prompt_manifest_hash() -> str:
    """Aggregate hash of the CURRENT prompt bank (scripts/prompt_manifest.py)."""
    pm = _load_module(PROJECT_ROOT / "scripts" / "prompt_manifest.py", "prompt_manifest")
    return pm.build_manifest()["manifest_sha256"]


def eval_chapter(name: str, from_fixtures: bool, verbose: bool = False) -> dict[str, Any]:
    """Scorecard for one golden chapter — re-run the pipeline unless from_fixtures."""
    source = (GOLDEN_ROOT / name / "source_chapter.md").read_text(encoding="utf-8")
    reference = (GOLDEN_ROOT / name / "reference_summary.md").read_text(encoding="utf-8")

    if from_fixtures:
        frozen = json.loads(
            (GOLDEN_ROOT / name / "pipeline_output.json").read_text(encoding="utf-8")
        )
        output = frozen["output"]
    else:
        import types

        bench = _load_module(PROJECT_ROOT / "scripts" / "bench_chapter.py", "bench_chapter")
        args = types.SimpleNamespace(
            chapter=name,
            chapters=1,
            parallel=False,
            workers=1,
            latency_scale=0.0,
            profile=False,
            profile_out=None,
            json=None,
            save_golden=False,
            verbose=verbose,
        )
        report = bench.run_bench(args)
        if not report.get("pipeline_ok"):
            raise RuntimeError(f"[{name}] pipeline failed — eval is meaningless")
        output = report["freeze_output"]["output"]

    return compute_scorecard(name, output, source, reference, prompt_manifest_hash())


def run_eval(from_fixtures: bool, verbose: bool = False) -> dict[str, Any]:
    chapters = golden_chapters()
    if not chapters:
        raise SystemExit(f"no golden chapters found under {GOLDEN_ROOT}")
    scorecards = {name: eval_chapter(name, from_fixtures, verbose) for name in chapters}
    return {
        "schema": 1,
        "mode": "from-fixtures" if from_fixtures else "pipeline-rerun",
        "prompt_manifest_hash": prompt_manifest_hash(),
        "chapters": scorecards,
    }


# ── CLI ─────────────────────────────────────────────────────────────────────


def _print_table(report: dict[str, Any]) -> None:
    print("\n" + "=" * 96)
    print(
        f"  SUMMARY EVAL — {report['mode']}  |  prompt bank {report['prompt_manifest_hash'][:12]}…"
    )
    print("=" * 96)
    header = (
        f"  {'chapter':<18}{'rougeL':>7}{'faith':>7}{'halluc':>8}{'cover':>7}"
        f"{'f4min':>7}{'len':>5}{'fact':>5}{'cov':>4}{'clar':>5}{'verdict':>9}"
    )
    print(header)
    print("  " + "-" * 93)
    for name, sc in report["chapters"].items():
        m = sc["metrics"]
        len_ok = "ok" if m["length_policy"]["compliant"] else "OFF"
        print(
            f"  {name:<18}{m['rouge_l']['fmeasure']:>7.3f}{m['faithfulness']:>7.3f}"
            f"{m['hallucination_rate']:>8.1%}{m['coverage']:>7.1%}{m['f4_min_overlap']:>7.2f}"
            f"{len_ok:>5}{sc['factual_consistency_score']:>5}{sc['coverage_score']:>4}"
            f"{sc['clarity_score']:>5}{sc['verdict']:>9}"
        )
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--from-fixtures",
        action="store_true",
        help="evaluate frozen outputs (skip pipeline re-run)",
    )
    parser.add_argument(
        "--check", action="store_true", help="gate vs committed baseline (exit 1 on regression)"
    )
    parser.add_argument(
        "--save-baseline", action="store_true", help="(re)write tests/golden/eval_baseline.json"
    )
    parser.add_argument("--json", metavar="PATH", help="write the full scorecard JSON to PATH")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.check and args.save_baseline:
        parser.error("--check and --save-baseline are mutually exclusive")

    report = run_eval(from_fixtures=args.from_fixtures, verbose=args.verbose)

    if args.save_baseline:
        BASELINE_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"eval baseline written → {BASELINE_PATH}")

    _print_table(report)

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"scorecards written → {args.json}")

    if args.check:
        if not BASELINE_PATH.exists():
            print(f"FAIL: eval baseline missing: {BASELINE_PATH}", file=sys.stderr)
            return 1
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        problems: list[str] = []
        base_chapters = baseline.get("chapters", {})
        for name, sc in report["chapters"].items():
            if name not in base_chapters:
                problems.append(
                    f"[{name}] no baseline scorecard — run eval_summary.py --save-baseline "
                    f"and commit it with the new chapter"
                )
                continue
            problems.extend(compare_scorecards(base_chapters[name], sc))
        for name in base_chapters:
            if name not in report["chapters"]:
                problems.append(f"[{name}] chapter in baseline but golden fixture missing now")
        if problems:
            print("\nEVAL GATE: REGRESSION DETECTED", file=sys.stderr)
            for p in problems:
                print(f"  ✗ {p}", file=sys.stderr)
            return 1
        print("EVAL GATE: OK — no quality regressions vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
