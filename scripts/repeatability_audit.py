#!/usr/bin/env python3
"""V0.5.16 (repeatability session) — the coverage audit for a repeatability run.

Computes the AUTHOR-COVERAGE scorecard for one repeatability_run.py run,
using the same deterministic methodology as the V0.5.x rig audits:

  1. roster: ``extract_citations`` (the runtime deterministic regex,
     core/preprocessing/deterministic_analyzer.py — the same function the
     verification LAYER + gap-fill use) over the chapter SOURCE;
  2. coverage: word-boundary regex search of each author name in the
     summary text (the V0.5.4 B1 rule — verification_phase.py:790),
     across ALL summary fields (bullets + exec + thorough + distinctions
     + tensions + excerpts);
  3. glossary cross-reference: the run's persisted source glossary
     (LLM-extracted roster) vs the regex roster (confirmed / llm_only /
     regex_only buckets — cross_reference_glossary);
  4. grounding spot-check: each bullet's named authors vs the source
     (authors in the summary but NOT in the source roster = candidate
     hallucinations to manually verify).

Content-agnostic (Rule 1): all names come from the runtime regex + the
run's own glossary; nothing is hardcoded.

Usage:
  python scripts/repeatability_audit.py --run runs/ch1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.preprocessing.deterministic_analyzer import extract_citations
from core.summarisation.author_anchor import author_anchor_patterns, author_in_text


def author_set(text: str) -> dict[str, list[str]]:
    """The source roster: author → years (len>=3 names only, the
    verification-phase rule)."""
    cits = extract_citations(text)
    roster: dict[str, list[str]] = {}
    for c in cits:
        a = (c.get("author") or "").strip()
        if len(a) < 3:
            continue
        yrs = c.get("years") or ""
        roster.setdefault(a, [])
        for y in re.split(r"[,\s]+", yrs):
            y = y.strip()
            if y and y not in roster[a]:
                roster[a].append(y)
    return roster


def covered(authors: dict[str, list[str]], summary_text: str) -> tuple[list[str], list[str]]:
    """Boundary-safe anchor coverage check (the V0.5.4 B1 rule, V0.5.18
    anchor form — ``\b`` after a name ending in "et al." never matched)."""
    hay = summary_text.lower()
    have, missing = [], []
    for a in authors:
        if author_in_text(a, hay):
            have.append(a)
        else:
            missing.append(a)
    return have, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="author-coverage audit for a repeatability run")
    parser.add_argument("--run", required=True, help="the repeatability run directory")
    args = parser.parse_args(argv)

    run_dir = Path(args.run).resolve()
    result_path = run_dir / "result.json"
    if not result_path.exists():
        print(f"no result.json in {run_dir}", file=sys.stderr)
        return 1
    result = json.loads(result_path.read_text(encoding="utf-8"))

    chapter_file = Path(result["chapter_file"])
    source = chapter_file.read_text(encoding="utf-8")
    # strip frontmatter for the citation scan (same as the summarizer sees)
    fm = re.match(r"\A---\s*\n.*?\n---\s*\n", source, re.DOTALL)
    if fm:
        source = source[fm.end() :]

    s = result.get("summary") or {}
    fields = {
        "executive_summary": s.get("executive_summary") or "",
        "bullet_points": "\n".join(s.get("bullet_points") or []),
        "thorough_summary": s.get("thorough_summary") or "",
        "key_distinctions": s.get("key_distinctions") or "",
        "theoretical_tensions": s.get("theoretical_tensions") or "",
        "source_excerpts": "\n".join(s.get("source_excerpts") or []),
        "scholar_reflections": s.get("scholar_reflections") or "",
    }
    # re-read the SHIPPED file if present (post verification-LAYER polish)
    shipped = ""
    for sf in sorted((run_dir / "summaries").glob("*_summary.md")):
        shipped = sf.read_text(encoding="utf-8")
    combined = shipped or "\n\n".join(fields.values())

    roster = author_set(source)
    have, missing = covered(roster, combined)
    n_total, n_have = len(roster), len(have)
    pct = (100.0 * n_have / n_total) if n_total else 0.0

    # summary-side names NOT in the source roster (hallucination candidates)
    summ_roster = author_set(combined)
    hallucination_candidates = [a for a in summ_roster if not author_in_text(a, source.lower())]

    # glossary cross-reference
    gloss = s.get("source_glossary") or {}
    gloss_names = [n.get("name", "") for n in (gloss.get("names") or []) if n.get("name")]
    # V0.5.19: drop structural-label entries (the glossary garbage-name
    # family — mirrors the pipeline-side filter so the scorecard roster
    # and the pipeline's ground truth agree).
    from core.summarisation.author_anchor import filter_structural_names

    gloss_names = filter_structural_names(gloss_names)
    from core.summarisation.glossary_parser import cross_reference_glossary

    xref = cross_reference_glossary(gloss_names, list(roster.keys()))

    print("=" * 72)
    print(f"  REPEATABILITY AUDIT — {result['heading']}")
    print(
        f"  run {result['run_id']} (v{result['app_version']}, {result['elapsed_sec']}s, "
        f"model={result['llamacpp_model']})"
    )
    print("=" * 72)
    print(f"  source authors (regex roster): {n_total}")
    print(f"  COVERED in shipped summary:    {n_have}  ({pct:.1f}%)")
    print(f"  MISSING:                       {n_total - n_have}")
    if missing:
        print("\n  Missing authors (source-mention counts):")
        src_low = source.lower()
        for a in sorted(missing):
            # boundary-safe count (the anchor form — see covered())
            cnt = sum(len(p.findall(src_low)) for p in author_anchor_patterns(a))
            yrs = ",".join(roster[a][:4])
            print(f"    - {a} ({yrs}) — {cnt} source mention(s)")
    print(
        f"\n  Glossary: {len(gloss_names)} LLM names; "
        f"xref confirmed={len(xref['confirmed'])} llm_only={len(xref['llm_only'])} "
        f"regex_only={len(xref['regex_only'])}"
    )
    if xref["llm_only"]:
        print(f"    llm_only (glossary caught, regex missed): {', '.join(xref['llm_only'][:15])}")
    if xref["regex_only"]:
        print(
            f"    regex_only (regex caught, glossary missed): {', '.join(xref['regex_only'][:15])}"
        )
    print(f"\n  Bullets: {len(s.get('bullet_points') or [])}")
    print(
        f"  Hallucination candidates (names in summary absent from source): "
        f"{len(hallucination_candidates)}"
    )
    for a in hallucination_candidates[:15]:
        print(f"    - {a}")
    print("=" * 72)

    # machine-readable companion
    audit = {
        "run_id": result["run_id"],
        "heading": result["heading"],
        "roster_size": n_total,
        "covered": n_have,
        "coverage_pct": round(pct, 1),
        "missing_authors": missing,
        "glossary_names": len(gloss_names),
        "xref": dict(xref),
        "hallucination_candidates": hallucination_candidates,
        "bullets": len(s.get("bullet_points") or []),
        "benchmark_ch6_v0515": {"covered": 70, "roster": 74, "pct": 94.6},
    }
    out = run_dir / "coverage_audit.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"coverage_audit.json → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
