"""V7.7.0: Chapter-level resume system.

The user's concept: "I processed chapters 1-3 yesterday. Today I want to do
chapters 4-10 (or the full book). The system should skip the already-
processed chapters to save time and resources."

This is different from the V7.0.0 checkpoint system (which resumes a
*crashed* conversion at the phase level).  This is **chapter-level skip**:
detect which chapters already have valid summaries on disk, load them, and
only run the LLM summarizer on the new/changed chapters.

**How "done" is detected:**
A chapter is considered done if its summary file exists at
``summaries/chapters/{idx:03d}_{heading}_summary.md`` (or the legacy
``markdown/chapters/summaries/`` path) AND the file contains a non-empty
executive summary + at least one bullet point.

**Matching:**
Chapters are matched by **heading text** (sanitized), not by index —
because indices can shift if the user changes the page range or chapter
selection between runs.  Heading text is stable for the same PDF + TOC.

**What gets skipped:**
Only the per-chapter LLM summarization is skipped.  Whole-book outputs
(briefing, book summary, podcast full-book, packets) are always regenerated
because they synthesize across ALL chapters — adding new chapters changes
the result.

**The summary files ARE the resume token.**  No separate state file to
maintain or get out of sync.  If a summary file is deleted, that chapter
is reprocessed.  If it's corrupted/incomplete, it's reprocessed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult

logger = logging.getLogger(__name__)


def _sanitize_heading(heading: str) -> str:
    """Sanitize a chapter heading for filename matching.

    Mirrors the converter's ``_sanitize_filename`` logic so we can match
    summary files to chapter headings.
    """
    safe = re.sub(r"[^\w\s\-]", "", heading)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:80]


def _find_summary_files(output_dir: Path) -> list[Path]:
    """Find all existing chapter summary files in the output dir.

    Checks both the V7.5.0+ layout (``summaries/chapters/``) and the
    legacy layout (``markdown/chapters/summaries/``) for backward compat.

    V0.4.25: returns the files NEWEST-FIRST (mtime descending). With
    run-stamped filenames, files from MULTIPLE runs of the same book
    coexist in one folder; ``detect_processed_chapters`` keys by heading,
    so iterating newest-first and keeping the first hit per heading makes
    the NEWEST run's content win deterministically (glob order is
    arbitrary — without this, a re-run could adopt an arbitrary older
    file when a newer one exists).
    """
    candidates = []
    # V7.5.0+ layout: summaries/chapters/*_summary.md
    new_dir = output_dir / "summaries" / "chapters"
    if new_dir.exists():
        candidates.extend(new_dir.glob("*_summary.md"))
    # Legacy layout: markdown/chapters/summaries/*_summary.md
    legacy_dir = output_dir / "markdown" / "chapters" / "summaries"
    if legacy_dir.exists():
        candidates.extend(legacy_dir.glob("*_summary.md"))
    # Also check the flat summaries/ dir (some older runs)
    flat_dir = output_dir / "summaries"
    if flat_dir.exists():
        candidates.extend(flat_dir.glob("*_summary.md"))
    try:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:  # pragma: no cover — a deleted-mid-scan file must not crash resume
        pass
    return candidates


def parse_summary_file(path: Path) -> SummaryResult | None:
    """Parse a saved summary .md file back into a SummaryResult.

    Returns None if the file is corrupted or incomplete (missing sections).

    The file format (from converter.py):
    ::
        # Summary: {heading}

        ## Executive Summary
        {executive_summary}

        ## Key Takeaways
        - {bullet 1}
        - {bullet 2}

        ## Thorough Summary
        {thorough_summary}
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not content.strip():
        return None

    # V9.0.0 P2-1: require the COMPLETE sentinel — if a file was partially
    # written (crash mid-write before the atomic rename), it won't have
    # this marker and will be treated as "not done" → re-summarized.
    # V18.20.3.7: accepts both the legacy bare sentinel and the run-id-
    # stamped form, and parses the file's provenance (which app version /
    # run wrote it) onto the loaded SummaryResult — so resume can report
    # WHERE a reused summary came from.
    from core.system.provenance import has_complete_sentinel, parse_provenance

    if not has_complete_sentinel(content):
        return None
    _prov = parse_provenance(content)

    # Extract heading
    heading_match = re.match(r"^#\s+Summary:\s*(.+)$", content, re.MULTILINE)
    if not heading_match:
        return None
    heading = heading_match.group(1).strip()

    # Extract executive summary
    exec_match = re.search(
        r"##\s+Executive Summary\s*\n(.*?)(?=\n##\s+|\Z)",
        content,
        re.DOTALL,
    )
    executive_summary = exec_match.group(1).strip() if exec_match else ""
    # V0.05 (F9a): no single section is individually REQUIRED anymore — the
    # user's output-selection flags are enforced end-to-end, so a legitimately
    # unchecked section (exec, keypoints, or thorough) is simply ABSENT from
    # the file. The completeness criterion moves to the combined check below:
    # at least ONE of the three core sections must have content.

    # Extract bullet points
    bullets_match = re.search(
        r"##\s+Key Takeaways\s*\n(.*?)(?=\n##\s+|\Z)",
        content,
        re.DOTALL,
    )
    bullet_points: list[str] = []
    if bullets_match:
        for line in bullets_match.group(1).strip().splitlines():
            line = line.strip()
            if line.startswith("- "):
                bp = line[2:].strip()
                if bp:
                    bullet_points.append(bp)
    # Extract thorough summary
    thorough_match = re.search(
        r"##\s+Thorough Summary\s*\n(.*?)(?=\n##\s+|\Z)",
        content,
        re.DOTALL,
    )
    thorough_summary = thorough_match.group(1).strip() if thorough_match else ""

    # V0.05 (F9a) combined completeness check: at least ONE core section
    # (executive / takeaways / thorough) must carry content. A file with
    # NONE of them is corrupt or truncated — treat as not done so the
    # chapter is reprocessed. (Previously bullets alone were mandatory,
    # which forced an endless re-summarize loop for a keypoints-disabled
    # run even though its exec/thorough sections were complete.)
    if not executive_summary and not bullet_points and not thorough_summary:
        return None

    return SummaryResult(
        chapter_heading=heading,
        executive_summary=executive_summary,
        thorough_summary=thorough_summary,
        bullet_points=bullet_points,
        success=True,
        # V18.20.3.7: provenance of the on-disk file (empty strings for
        # legacy files without a stamp).
        run_id=_prov.get("run_id", ""),
        app_version=_prov.get("app_version", ""),
        run_started=_prov.get("started", ""),
    )


def detect_processed_chapters(output_dir: Path) -> dict[str, SummaryResult]:
    """Scan the output dir for existing chapter summaries.

    Returns a dict ``{sanitized_heading: SummaryResult}`` for all chapters
    that have valid (complete) summary files on disk.  Incomplete/corrupted
    files are skipped (those chapters will be reprocessed).

    V0.4.25: when run-stamped files from multiple runs coexist, the NEWEST
    file per heading wins (``_find_summary_files`` returns newest-first;
    the first valid hit per heading is kept and later — older — hits are
    ignored). For the single-file-per-chapter case this is byte-identical
    to the previous behavior.
    """
    processed: dict[str, SummaryResult] = {}
    for sf in _find_summary_files(output_dir):
        result = parse_summary_file(sf)
        if result and result.success:
            key = _sanitize_heading(result.chapter_heading).lower()
            if key not in processed:  # newest-first → first hit = newest run
                processed[key] = result
    return processed


def split_chapters_for_resume(
    chapter_dicts: list[dict],
    processed: dict[str, SummaryResult],
    log_callback=None,
) -> tuple[list[dict], list[SummaryResult]]:
    """Split chapters into (todo, skip_loaded).

    Args:
        chapter_dicts: the full list of chapter dicts ``{heading, content, ...}``
            that the converter is about to summarize.
        processed: the dict from :func:`detect_processed_chapters`.
        log_callback: optional ``fn(msg, level)``.

    Returns:
        ``(todo_chapters, loaded_summaries)`` where:
          - ``todo_chapters`` is the subset of ``chapter_dicts`` that need
            LLM summarization (no valid summary on disk).
          - ``loaded_summaries`` is the list of SummaryResults loaded from
            disk for the skipped chapters (to be merged with new summaries).
    """
    log = log_callback or (lambda msg, level: None)
    todo: list[dict] = []
    loaded: list[SummaryResult] = []
    used_keys: set = set()  # V9.0.0 P1-2: track which processed entries we've consumed

    for cd in chapter_dicts:
        heading = cd.get("heading", "")
        key = _sanitize_heading(heading).lower()
        # V9.0.0 P1-2: fix duplicate-heading silent duplication.  Previously
        # two chapters with the same heading would both match the same
        # processed entry, causing the same SummaryResult to be appended
        # twice.  Now each processed entry can only be consumed once.
        if key in processed and key not in used_keys:
            loaded.append(processed[key])
            used_keys.add(key)
            # V18.20.3.7: name the producing run when the reused file is
            # stamped — the operator sees which app version's output is
            # being adopted (the V18.20.3.6 stale-file confusion killer:
            # a .3.4 file in a .3.6 folder is now visible at resume time).
            _src = processed[key]
            _prov_tag = ""
            if getattr(_src, "run_id", ""):
                _prov_tag = (
                    f" (file from run {_src.run_id}"
                    + (f", app v{_src.app_version}" if getattr(_src, "app_version", "") else "")
                    + ")"
                )
            log(
                f"  ⏭️  Resume: '{heading[:50]}' already processed — skipping LLM{_prov_tag}", "INFO"
            )
            # V0.4.25: version-mismatch escalation. Adopting an OLDER app
            # version's summaries is still allowed (the V7.7.0 chapter-skip
            # feature — incremental processing), but when the operator
            # re-runs the SAME book to get the NEW version's output, this
            # silent adoption is exactly how a "genuinely new" run ships
            # old content. Escalate to WARNING with the actionable fix so
            # it can never pass unnoticed in the conversion log again.
            try:
                from core.system.provenance import get_app_version

                _adopted_ver = getattr(_src, "app_version", "")
                _cur_ver = get_app_version()
                if _adopted_ver and _adopted_ver != _cur_ver:
                    log(
                        f"  ⚠️  Resume adopted a chapter summary from app v{_adopted_ver} "
                        f"but this conversion runs v{_cur_ver} — its content is the OLD "
                        f"version's output. To re-summarize with v{_cur_ver}: delete "
                        f"summaries/chapters/ (or convert into a fresh output folder).",
                        "WARNING",
                    )
            except Exception:  # pragma: no cover — visibility must never break resume
                pass
        else:
            todo.append(cd)

    if loaded:
        log(f"  📂 Chapter resume: {len(loaded)} already done, {len(todo)} to process", "INFO")
    return todo, loaded


def merge_summaries(
    todo_summaries: list[SummaryResult],
    loaded_summaries: list[SummaryResult],
    chapter_order: list[str],
) -> list[SummaryResult]:
    """Merge newly-generated summaries with loaded ones, in chapter order.

    Args:
        todo_summaries: summaries just generated by the LLM (for the
            todo chapters).
        loaded_summaries: summaries loaded from disk (for the skip chapters).
        chapter_order: list of sanitized headings in the original chapter
            order, so the merged list preserves the book's reading order.

    Returns:
        A single list of SummaryResults in the original chapter order.

    V0.6.6 (review-loop L2-2): occurrence-aware merge. The old heading-
    keyed dict dropped a LOADED chapter's summary whenever duplicate
    headings + resume coincided (two "Notes" chapters: the loaded one
    was lost and the new one duplicated into both positions — silent
    data loss in the final book outputs, which build on the merged
    list). Now each heading consumes its summaries in order (todo
    first — the "don't overwrite new with loaded" rule is preserved:
    the FIRST occurrence of a heading still gets the new summary), and
    no summary object is ever emitted twice.
    """
    from collections import defaultdict, deque

    # Per-heading queues: todo entries first, loaded behind them — for a
    # UNIQUE heading the queue holds at most one entry and behavior is
    # byte-identical to the old dict (new wins, loaded dropped on ties).
    by_heading: dict[str, deque] = defaultdict(deque)
    for s in todo_summaries:
        by_heading[_sanitize_heading(s.chapter_heading).lower()].append(s)
    for s in loaded_summaries:
        by_heading[_sanitize_heading(s.chapter_heading).lower()].append(s)

    # Reassemble in original order, one summary per occurrence.
    merged: list[SummaryResult] = []
    for heading in chapter_order:
        q = by_heading.get(_sanitize_heading(heading).lower())
        if q:
            merged.append(q.popleft())
    return merged
