"""V18.20.3.0: Incremental per-chapter checkpoint saving (crash-safe).

User requirement (verbatim): "Currently it user add a full book for
summarization, the app refuses to give outputs until the all books is
finished, but this method is not very efficient or reliable. we need to
plan a saving mechanism into app, for example after every chapter, save
the docx and outputs of that chapter (create a new folder as well), so if
by any means, like electricity problems/ sudden shutdowns etc, app got
stopped/cancelled, we have a backup and save until that point of
application. For example book is 10 chapter, 9 chapter is done, the app
crashes at the 10th chapter, we must have 9 chapters ready and untouched
by this crash, because they're already done and saved."

The gap this closes
-------------------
Before V18.20.3.0 the pipeline held ALL chapter summaries in memory and
only wrote them to disk AFTER the last chapter finished (the
"Incremental saving" loop in ``conversion/summarization.py`` — which was
atomic per file but ran once, post-loop). The full-book DOCX was built
even later (converter Step 10). A power cut / crash / user-cancel at
chapter 10 of 11 therefore lost chapters 1-10: nothing was on disk for
the chapter-resume system (V7.7.0) to find, and no DOCX existed at all.

What happens now
----------------
The moment each chapter's summary is produced,
:class:`ChapterCheckpointSaver` (wired as the ``chapter_done_callback`` of
``Summarizer.summarize_chapters``) writes — ATOMICALLY and WRITE-ONCE
(never rewrites a completed chapter):

    {output_dir}/
    ├── summaries/{NNN}_{heading}_summary.md      ← canonical summary file
    │                                                 (``<!-- COMPLETE -->``
    │                                                 marker → the V7.7.0
    │                                                 chapter-resume system
    │                                                 picks it up on re-run)
    └── checkpoints/
        ├── chapter_manifest.json                  ← crash-recovery state
        │                                             (chapters done, paths,
        │                                             timestamps, bullet counts)
        └── chapters/
            └── {NNN}_{heading}/
                ├── {NNN}_{heading}_summary.md     ← self-contained copy
                └── {NNN}_{heading}_summary.docx   ← per-chapter DOCX report

On restart after a crash, ``detect_processed_chapters()`` (V7.7.0) finds
the surviving summary files and the LLM processes ONLY the missing
chapters; whole-book outputs are then rebuilt from the merged set. The
user also has every completed chapter's DOCX available immediately —
readable mid-run, not just after the whole book finishes.

Design rules
------------
- **Best-effort, never fatal**: every write is wrapped; a checkpoint
  failure logs a WARNING and the conversion continues (checkpointing must
  never crash the pipeline).
- **Atomic**: ``utils.atomic_io.atomic_write_text`` / ``atomic_write_json``
  for .md/.json; DOCX is saved to a ``.tmp`` sibling then ``os.replace``d
  (python-docx's ``save()`` is not atomic by itself).
- **Write-once**: if the target summary file already exists WITH the
  COMPLETE marker it is never rewritten — completed chapters stay
  byte-identical across re-runs ("ready and untouched").
- **Positioning**: files are numbered by the chapter's FINAL position in
  the merged (loaded + new) summary list, computed upfront from the
  segment order — so checkpoint files match the end-of-run numbering and
  resume numbering stays stable. Fallback: the callback's 1-based index.
- **Failed chapters are not saved** (mirrors the end-of-loop rule: failed
  summaries never produce COMPLETE files, so they are reprocessed on
  resume).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import SummaryResult
from utils.error_trace import log_swallow

logger = logging.getLogger(__name__)

# V18.2.7/V18.2.8 (shared with conversion/summarization.py): academic years
# in parentheses render italic + smaller in the summary markdown.
# V18.20.3.2 (audit N8 / P2-b): the old pattern `\((\d{4})\)` only matched
# parentheticals containing EXACTLY one bare year — "(1956)" was styled but
# "(1961, 1963)" and "(1950a, 1956, 1958, 1959)" were not, so the shipped
# markdown mixed styled and plain years inside the SAME bullet list. The new
# pattern styles EVERY 4-digit year inside ANY parenthetical group (single,
# multi-year, and year+letter citations), making the rendering consistent.
_YEAR_IN_PARENS_RE = re.compile(r"\(([^()]*)\)")
# V18.20.3.2: (?<!\d)/(?!\d) instead of \b — "1950a" has no word boundary
# between "0" and "a" (both word chars), so \b\d{4}\b MISSED year+letter
# citations while styling their bare-year siblings ("(1950a, 1956)" styled
# only 1956). The digit-lookarounds allow letter suffixes but reject longer
# digit runs.
_BARE_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")

_MANIFEST_VERSION = "18.20.3.0"

# V0.4.36 (F3): pattern for detecting section transitions in the thorough —
# a sentence starting with "Author (Year)" or "Author (*Year*) signals a
# new topic. Content-agnostic (the pattern is a generic citation format).
_SECTION_TRANSITION_RE = re.compile(
    r"(?<=[.!?]\s)(?=[A-Z][a-z]+ (?:\(\*?1[89]\d{2}\*?\)|\(\d{4}\)))"
)


def _render_bullets_grouped_by_section(
    bullets: list[str],
    section_map: list[dict],
) -> str:
    """V0.5.4 (Track C1): group key-takeaway bullets under the source's
    ALL-CAPS section headings.

    Each bullet is assigned to the FIRST source section whose author set
    contains a name that appears (case-insensitive, word-boundary substring)
    in the bullet text. The mapping is fully runtime-derived (no hardcoded
    names): the section titles come from the deterministic
    ``extract_all_caps_sections`` pass on the chapter source, and the
    author-per-section list comes from the deterministic
    ``map_authors_to_all_caps_sections`` pass. Both are populated by the
    Summarizer and stamped onto the SummaryResult's ``source_section_map``
    field.

    Bullets that do NOT mention any author from any source section are listed
    at the end under the legacy ``## Key Takeaways`` heading (so the contract
    a chapter without a section_map delivers — a flat list — is preserved).

    The section order matches the source's ALL-CAPS section order (NOT the
    bullets' order) so the rendered summary MIRRORS the source's structure —
    the explicit goal of Track C1.

    Content-agnostic (Rule 1): zero hardcoded section names, zero hardcoded
    author names — every name and every section title is runtime-derived.
    """
    if not section_map or not bullets:
        return "\n".join(f"- {b}" for b in bullets)

    # Build author→section-title index (first section wins on duplicates).
    author_to_section: dict[str, str] = {}
    for sec in section_map:
        title = sec.get("section_title", "")
        if not title:
            continue
        for author in sec.get("authors", []) or []:
            if author and author not in author_to_section:
                author_to_section[author] = title

    # If NO section has any authors, the map is non-informative — fall back
    # to the legacy flat list (strict improvement: never regresses).
    if not author_to_section:
        return "\n".join(f"- {b}" for b in bullets)

    # Assign each bullet to its section (first-author-match wins; bullets
    # with no matching author go to the ungrouped bucket, in source order).
    section_bullets: dict[str, list[str]] = {s.get("section_title", ""): [] for s in section_map}
    ungrouped: list[str] = []
    # Pre-build case-insensitive regex patterns (one per author) — re.search
    # is case-sensitive by default, and the bullet text is lowercased while
    # the author names retain their original (capitalized) case in the map.
    author_patterns = [
        (author, re.compile(r"\b" + re.escape(author.lower()) + r"\b"))
        for author in author_to_section
    ]
    for bullet in bullets:
        bullet_lower = bullet.lower()
        assigned: str | None = None
        for author, pat in author_patterns:
            # word-boundary substring match (case-insensitive) — the
            # \b anchors prevent short-surname false positives (a 4-letter
            # name must not match a substring of a longer word) and also
            # keep a name from matching its derived adjective form (the
            # "-ian" suffix case).
            if pat.search(bullet_lower):
                assigned = author_to_section[author]
                break
        if assigned is None:
            ungrouped.append(bullet)
        else:
            section_bullets.setdefault(assigned, []).append(bullet)

    # Render: one ## {section title} group per section WITH bullets (sections
    # without assigned bullets are omitted — strict-improvement, no empty
    # headings, per the V0.05 rig F9a rule).
    out_parts: list[str] = []
    for sec in section_map:
        title = sec.get("section_title", "")
        if not title:
            continue
        sec_bs = section_bullets.get(title, [])
        if not sec_bs:
            continue
        out_parts.append(f"## {title}\n\n")
        for b in sec_bs:
            out_parts.append(f"- {b}\n")
        out_parts.append("\n")
    if ungrouped:
        # legacy fallback: bullets not assigned to any source section are
        # rendered under the canonical "## Key Takeaways" heading so a
        # reader still sees them and so the existing section parser still
        # finds the section.
        out_parts.append("## Key Takeaways\n\n")
        for b in ungrouped:
            out_parts.append(f"- {b}\n")
    rendered = "".join(out_parts).rstrip() + "\n"
    return rendered


def _render_reproduced_tables(tables: list[dict]) -> str:
    """V0.5.4 (Track B3): render the runtime-extracted ``TABLE N-N.``
    tables verbatim as markdown under a clearly-labelled section.

    Conservative scope (per the V054-TRACK-B3 brief): the table content is
    reproduced AS-IS from the deterministic extractor's ``content_lines``
    (the markdown-table rows that follow the ``TABLE N-N.`` marker in the
    source). No paraphrasing, no LLM rewriting — the goal is faithful
    reproduction.

    The section heading is labelled "Reproduced Tables (from source)" so a
    reader / downstream consumer can distinguish reproduced-source tables
    from summarizer-authored additive-section tables. Each table is
    preceded by its marker (e.g., ``TABLE 6-1.``) and title (if any) as a
    bolded label.

    Content-agnostic (Rule 1): the marker + content are runtime-derived
    from the chapter source; the renderer does not look for any specific
    table number.
    """
    if not tables:
        return ""
    parts = ["\n## Reproduced Tables (from source)\n\n"]
    parts.append(
        "The following tables are reproduced verbatim from the chapter "
        "source. They were detected by the deterministic ``TABLE N-N.`` "
        "marker (no LLM rewriting — the table content is the source's own "
        "markdown-table rows).\n\n"
    )
    for t in tables:
        marker = t.get("marker", "") or ""
        title = t.get("title", "") or ""
        content_lines = t.get("content_lines", []) or []
        if marker:
            parts.append(f"**{marker}**")
            if title:
                parts.append(f" {title}")
            parts.append("\n\n")
        elif title:
            parts.append(f"**{title}**\n\n")
        if content_lines:
            parts.append("\n".join(content_lines).rstrip() + "\n\n")
    return "".join(parts)


def _render_reproduced_criteria(criteria_clusters: list[dict]) -> str:
    """V0.5.4 (Track B4): render the runtime-extracted ``a. b. c. d.`` +
    ``(i) (ii) (iii)`` diagnostic-criteria clusters as nested bullet lists.

    Conservative scope (per the V054-TRACK-B4 brief): the criteria are
    reproduced AS-IS from the deterministic extractor — no paraphrasing, no
    condensing. Each lettered criterion becomes a top-level bullet
    (``- **a.** text``), and each Roman sub-item becomes an indented bullet
    (``  - (i) sub-text``).

    The section heading is labelled "Reproduced Diagnostic Criteria (from
    source)" so a reader can distinguish reproduced-source criteria from
    summarizer-authored additive-section content.

    Content-agnostic (Rule 1): the criteria text comes from the chapter
    source (runtime-detected); the renderer does not look for any specific
    criteria wording.
    """
    if not criteria_clusters:
        return ""
    parts = ["\n## Reproduced Diagnostic Criteria (from source)\n\n"]
    parts.append(
        "The following diagnostic criteria are reproduced verbatim from the "
        "chapter source. They were detected by the deterministic "
        "``a. b. c. d.`` + ``(i) (ii) (iii)`` pattern (no LLM condensing — "
        "the criteria are the source's own structured list).\n\n"
    )
    for cluster in criteria_clusters:
        items = cluster.get("items", []) or []
        if not items:
            continue
        for it in items:
            letter = it.get("letter", "")
            text = it.get("text", "")
            parts.append(f"- **{letter}.** {text}\n")
            for marker, sub_text in it.get("sub_items", []) or []:
                parts.append(f"  - ({marker}) {sub_text}\n")
        parts.append("\n")
    return "".join(parts).rstrip() + "\n\n"


def _style_years_in_parens(match: re.Match) -> str:
    """Style every 4-digit year inside one parenthetical group.

    V0.4.26 (audit backlog #5): emit markdown italic emphasis (``*YYYY*``)
    instead of raw HTML ``<em style="font-size:0.9em">YYYY</em>``. The HTML
    leaked raw into the markdown output (the V0.4.25 ch.1 audit's HTML-
    leakage finding) — the DOCX builder does not consume ``format_years``
    (it has its own run-styling path), so the ``<em>`` was pure markdown-side
    leakage with no consumer. ``*YYYY*`` is the correct markdown emphasis
    and renders italic in any compliant markdown viewer (incl. the DOCX
    builder's markdown-to-runs converter if it parses ``*``).
    """
    inner = match.group(1)
    if not _BARE_YEAR_RE.search(inner):
        return match.group(0)  # no years — leave untouched
    return "(" + _BARE_YEAR_RE.sub(r"*\1*", inner) + ")"


def _break_thorough_into_paragraphs(thorough: str) -> str:
    """V0.4.36 (F3): break the thorough into MULTIPLE paragraphs at
    section transitions.

    The thorough ships as a single ~4000-word paragraph (6 consecutive
    audits flagged this). The fix: a deterministic post-processing pass
    that splits the thorough at sentence boundaries where a new
    Author (Year) citation signals a section transition. Content-agnostic
    (the split pattern is a generic English discourse marker: a sentence
    starting with an Author (Year) citation signals a new section).
    Rule 1 compliant (no book-specific names or content).
    """
    if not thorough or len(thorough) < 500:
        return thorough  # short thorough — no need to split
    # Split at sentence boundaries where the next sentence starts with
    # "AuthorName (Year)" or "AuthorName (*Year*) — the citation pattern.
    parts = _SECTION_TRANSITION_RE.split(thorough)
    if len(parts) <= 1:
        return thorough  # no transitions found — return as-is
    return "\n\n".join(parts)


def format_years(text: str) -> str:
    """Wrap 4-digit years in parentheses with markdown italic emphasis.

    Extracted verbatim from the (formerly inline) end-of-loop writer in
    ``conversion/summarization.py`` so the incremental checkpoint writer
    and the final writer produce byte-identical files.

    V18.20.3.2 (P2-b): every parenthesized year is styled — single years
    ("(1956)"), multi-year citations ("(1961, 1963)"), and year+letter
    citations ("(1950a, 1956)") — closing the styled/plain inconsistency
    the V18.20.3.1 audit flagged in the shipped Key Takeaways.

    V0.4.26 (audit backlog #5): the styling is now markdown italic
    (``*YYYY*``) instead of raw HTML ``<em>`` (see
    ``_style_years_in_parens`` for the rationale + the audit finding).
    """
    if not text:
        return text
    return _YEAR_IN_PARENS_RE.sub(_style_years_in_parens, text)


def _final_stray_quote_sweep(text: str, field_label: str) -> str:
    """V0.4.37 (F6): defense-in-depth final stray-quote sweep at the
    render boundary (thorough only).

    The postcheck's ``repair_stray_quotes_v2`` (postchecks/garble/
    quote_repair.py) runs on the thorough while it is still a single
    very long line; its state-machine D2 can mis-pair ambiguous quotes
    on a long line and leave an orphan undetected (no ``stray_quote``
    fix is logged). The V0.4.36 (F3) paragraph-breaking that runs
    HERE shortens the thorough into ~16 paragraph-lines, making
    per-line quote-pairing far more reliable. Re-running the sweep
    AFTER paragraph-breaking + format_years therefore catches orphans
    the pre-paragraph-break single-line pass missed (the V0.4.36 ch.6
    audit F6 evidence: a stray ``"`` before a trailing participle
    survived into the rendered thorough despite the postcheck logging
    no stray-quote fix on it).

    Strictly content-agnostic (Rule 1 ✓): the detector counts
    double-quotes per line and removes the orphan on odd-count lines
    — no hardcoded patterns, names, or content. Strict-improvement:
    it only removes orphan quotes, never adds or repositions them; on
    already-clean text it is a no-op (the postcheck's primary fixes
    still own the structured conversion-log report; this render-time
    sweep is defense-in-depth and logs its catches at WARNING).
    """
    if not text or '"' not in text:
        return text
    try:
        from core.summarisation.postchecks.garble.quote_repair import (
            repair_stray_quotes_v2,
        )

        cleaned, issues = repair_stray_quotes_v2(text, field_label)
        if issues:
            logger.warning(
                "V0.4.37 F6 render-sweep: %d stray-quote fix(es) on '%s' "
                "after paragraph-breaking/format_years (orphans the "
                "postcheck's single-line pass missed).",
                len(issues),
                field_label,
            )
        return cleaned
    except Exception as e:  # pragma: no cover — render must never break
        logger.warning(
            "render stray-quote sweep crashed (non-fatal): %s: %s",
            type(e).__name__,
            e,
        )
        return text


def _normalize_self_compounds(text: str, field_label: str) -> str:
    """V0.4.38 (F5): insert missing hyphens in 'self' + word fusions.

    The V0.4.37 summary shipped 'selfinflation' (bullet line 76) and
    'selfrighteousness' (bullet line 63) — the model fused 'self' + a
    noun/adjective without the hyphen. This pass finds words starting
    with 'self' (>= 4 trailing lowercase chars, no hyphen) where the
    FULL word is NOT a real English word but the trailing part IS →
    inserts the hyphen ('selfinflation' → 'self-inflation';
    'selfrighteousness' → 'self-righteousness'). Real words like
    'selfless'/'selfish' are in the lexicon → left alone.
    Content-agnostic (Rule 1): the lexicon is the vendored generic
    English wordlist; the 'self-' prefix is generic English morphology.
    Strict-improvement (only adds hyphens; no-op on already-hyphenated
    or correct text). Logs catches at WARNING (defense-in-depth, like
    the F6 render-sweep).
    """
    if not text or "self" not in text.lower():
        return text
    try:
        import re as _re

        from core.summarisation.postchecks.garble.lexicon import (
            _load_english_lexicon,
        )

        _lex = _load_english_lexicon()
        if not _lex:
            return text
        _pattern = _re.compile(r"\bself[a-z]{4,}\b")
        fixes: list[str] = []

        def _fix(m: _re.Match[str]) -> str:
            w = m.group(0)
            tail = w[4:]  # after "self"
            # only hyphenate if the fused word is NOT real AND the tail IS
            if w in _lex or tail not in _lex:
                return w
            fixes.append(w)
            return "self-" + tail

        cleaned = _pattern.sub(_fix, text)
        if fixes:
            logger.warning(
                "V0.4.38 F5 render-sweep: %d self-compound hyphen fix(es) on '%s' (%s).",
                len(fixes),
                field_label,
                fixes[:5],
            )
        return cleaned
    except Exception as e:  # pragma: no cover — render must never break
        logger.warning(
            "self-compound hyphen normalization crashed (non-fatal): %s: %s",
            type(e).__name__,
            e,
        )
        return text


def render_summary_markdown(summ: SummaryResult) -> str:
    """Render a SummaryResult to the canonical chapter-summary markdown.

    Byte-identical to the end-of-loop writer in
    ``conversion/summarization.py`` (heading, Executive Summary, Key
    Takeaways with year-formatted bullets, Thorough Summary, optional
    additive sections, ``<!-- COMPLETE -->`` sentinel) — so a file written
    mid-run by the checkpoint saver is indistinguishable from one written
    at the end, and the V7.7.0 chapter-resume parser accepts both.

    V18.20.3.7: when the SummaryResult carries provenance
    (``run_id``/``app_version``/``run_started`` — set by the Summarizer,
    one id per conversion), the file becomes SELF-IDENTIFYING: a
    ``<!-- generated-by: ... -->`` comment sits under the title and the
    COMPLETE sentinel is stamped with the run id. Unstamped (legacy)
    summaries render exactly as before — byte-for-byte.
    """
    formatted_bullets = [
        _normalize_self_compounds(format_years(str(bp)), f"bullet[{i}]")
        for i, bp in enumerate(summ.bullet_points)
    ]
    # V0.5.4 (Track C1 — section breaks mirroring the source): when the
    # SummaryResult carries a runtime-derived ``source_section_map`` (the
    # author→ALL-CAPS-section map the Summarizer stamps onto the result),
    # the bullets are grouped under the source's ALL-CAPS section
    # headings INSTEAD of the legacy flat ``## Key Takeaways`` list. Empty
    # section_map (the default for every legacy result + every test fixture
    # that does not opt in) → legacy flat list → byte-identical to before.
    _section_map = getattr(summ, "source_section_map", None) or []
    if _section_map and formatted_bullets:
        bullets_md = _render_bullets_grouped_by_section(formatted_bullets, _section_map)
    else:
        bullets_md = "\n".join(f"- {_fbp}" for _fbp in formatted_bullets)

    exec_formatted = _normalize_self_compounds(format_years(summ.executive_summary or ""), "exec")
    # V0.4.36 (F3): break the thorough into MULTIPLE paragraphs at section
    # transitions. The V0.4.26 backlog item 3 — flagged for 6 consecutive
    # audits. The thorough ships as a single ~4000-word paragraph, burying
    # hallucinations in dense prose. The fix: a deterministic post-processing
    # pass that splits the thorough at sentence boundaries where a new
    # author/topic is introduced (the "Stanton (1978)..." → new paragraph
    # pattern). Content-agnostic (the split pattern is a generic English
    # discourse marker: a sentence starting with an Author (Year) citation
    # signals a new section transition).
    thorough_formatted = _normalize_self_compounds(
        _final_stray_quote_sweep(
            format_years(_break_thorough_into_paragraphs(summ.thorough_summary or "")),
            "thorough",
        ),
        "thorough",
    )

    kd_md = ""
    if getattr(summ, "key_distinctions", None) and str(summ.key_distinctions).strip():
        kd_md = f"\n## Key Distinctions\n\n{summ.key_distinctions}\n\n"
    tt_md = ""
    if getattr(summ, "theoretical_tensions", None) and str(summ.theoretical_tensions).strip():
        tt_md = f"\n## Theoretical Tensions\n\n{summ.theoretical_tensions}\n\n"
    sr_md = ""
    if getattr(summ, "scholar_reflections", None) and str(summ.scholar_reflections).strip():
        sr_md = f"\n## Scholar's Reflections\n\n{summ.scholar_reflections}\n\n"
    # V0.03 (P0-2): Tier-3 source excerpts — a SEPARATE, clearly-labelled
    # section. These are framed verbatim quotes recorded for coverage on
    # keywords the summary text itself did not cover; they are never mixed
    # into Key Takeaways (the V0.02 rig shipped a mid-quote fragment of
    # the source's *anti-pattern answer* as the book's final takeaway).
    se_md = ""
    _se = getattr(summ, "source_excerpts", None) or []
    if len(_se):
        _se_lines = "\n".join(f"- {str(e)}" for e in _se if str(e).strip())
        se_md = (
            "\n## Source Excerpts (auto-inserted)\n\n"
            "The following verbatim source sentences were auto-recorded for "
            "concepts the summary text did not cover. They are quotes from "
            "the book — including possible examples of what NOT to do — and "
            "are not the summarizer's advice.\n\n"
            f"{_se_lines}\n\n"
        )
    # V0.03 (P1-6) → V0.06 (rig audit F2 — REMOVED FROM THE DELIVERABLE):
    # the quarantine record (what the quality pipeline dropped) is pipeline
    # bookkeeping — it renders into logs/drops.jsonl (QuarantineLog) and the
    # conversion log, NEVER into the chapter summary. The V0.05 rig shipped
    # a "## Quarantine Log (quality-pipeline drops)" section inside every
    # affected chapter file; the user's ruling: "keep it for your logs".
    # The render is deleted; the appendix field is never populated (V0.06).

    # V18.20.3.7: provenance comment (self-identification) — only when the
    # summary is stamped with a real run-id STRING; legacy/unstamped output
    # (and duck-typed mocks without string fields) renders unchanged.
    prov_md = ""
    footer_md = ""
    _rid_raw = getattr(summ, "run_id", "")
    _run_id = _rid_raw if isinstance(_rid_raw, str) and _rid_raw else ""
    if _run_id:
        from core.system.provenance import provenance_comment, visible_footer

        _app_ver = getattr(summ, "app_version", "") or "unknown"
        _started = getattr(summ, "run_started", "") or "unknown"
        prov_md = (
            provenance_comment(
                _app_ver,
                _run_id,
                _started,
                len(formatted_bullets),
            )
            + "\n\n"
        )
        # V18.20.4.3 (P2 / G-3, the F8 follow-up): human-VISIBLE footer —
        # the HTML comment above is invisible in rendered markdown, which
        # is exactly how a stale artifact from an old app-version folder
        # got mistaken for fresh output. Rendered only for stamped
        # summaries; legacy output stays byte-identical.
        footer_md = visible_footer(
            _app_ver,
            _run_id,
            _started,
            len(formatted_bullets),
        )

    from core.system.provenance import complete_sentinel

    # (Type guard rationale above — a MagicMock run_id must render as a
    # legacy bare sentinel, never as garbage text.)
    # V0.05 (rig audit F9a — GENERAL RULE: no empty headings): every section
    # heading renders ONLY when the section has content. The renderer
    # previously emitted "## Executive Summary" / "## Key Takeaways" /
    # "## Thorough Summary" unconditionally — a user who unchecked a section
    # in the wizard still got its (empty or fabricated) heading in the file,
    # and a section the pipeline could not populate shipped as a blank
    # heading. When ALL core sections are present the bytes are identical to
    # the legacy writer (the chunk shapes below are the legacy fragments).
    #
    # V0.06 (rig audit F1-c — GENERAL RULE: the output selection is the
    # CONTRACT, enforced AT RENDER TIME): content-presence alone was proven
    # insufficient — the V0.05 rig shipped a "## Thorough Summary" section
    # to a user who unchecked the output, because the parser's leftover
    # fallback smuggled unrequested additive-section content into the field
    # and the renderer was flag-blind. The SummaryResult now carries the
    # user's output-selection flags (stamped at construction, F1-b); a
    # section renders only when BOTH its flag is on AND it has content.
    # Unstamped (legacy) results default to True = byte-identical legacy
    # behaviour.
    _inc_exec_r = getattr(summ, "include_executive_summary", True)
    _inc_kp_r = getattr(summ, "include_keypoints", True)
    _inc_th_r = getattr(summ, "include_thorough_summary", True)
    _core_chunks = []
    if _inc_exec_r and (exec_formatted or "").strip():
        _core_chunks.append(f"## Executive Summary\n\n{exec_formatted}\n\n")
    if _inc_kp_r and (bullets_md or "").strip():
        # V0.5.4 (Track C1): when the bullets were grouped under the
        # source's ALL-CAPS section headings by ``_render_bullets_grouped_by_
        # section``, the rendered string already opens with a ``## {Section}``
        # heading — wrapping it under the legacy ``## Key Takeaways``
        # heading would produce a doubly-nested heading tree (an ugly
        # "## Key Takeaways" followed by sibling ``## {Section}`` children).
        # The grouped bullets are emitted as a peer of Executive Summary
        # and Thorough Summary (no Key Takeaways wrapper); the legacy
        # flat-list case keeps the ``## Key Takeaways`` wrapper for byte-
        # identical backward compatibility.
        if _section_map and formatted_bullets and bullets_md.startswith("## "):
            _core_chunks.append(f"{bullets_md}\n")
        else:
            _core_chunks.append(f"## Key Takeaways\n\n{bullets_md}\n\n")
    if _inc_th_r and (thorough_formatted or "").strip():
        _core_chunks.append(f"## Thorough Summary\n\n{thorough_formatted}\n")
    # V0.5.4 (Track B3+B4): render the runtime-extracted reproduced tables
    # and reproduced diagnostic criteria as clearly-labelled appendices,
    # AFTER the additive sections (key_distinctions / theoretical_tensions /
    # scholar_reflections / source_excerpts) and BEFORE the provenance
    # footer. Each is rendered only when the Summarizer stamped a non-empty
    # list onto the SummaryResult — legacy/empty results render byte-
    # identical to before.
    _repro_tables = getattr(summ, "reproduced_tables", None) or []
    rt_md = _render_reproduced_tables(_repro_tables) if _repro_tables else ""
    _repro_criteria = getattr(summ, "reproduced_criteria", None) or []
    rc_md = _render_reproduced_criteria(_repro_criteria) if _repro_criteria else ""
    return (
        f"# Summary: {summ.chapter_heading}\n\n"
        f"{prov_md}"
        f"{''.join(_core_chunks)}"
        f"{kd_md}{tt_md}{sr_md}{se_md}"
        f"{rt_md}{rc_md}"
        f"{footer_md}"
        f"{complete_sentinel(_run_id)}\n"
    )


class ChapterCheckpointSaver:
    """Incremental per-chapter checkpoint writer (V18.20.3.0).

    Constructed once per conversion (in ``conversion/summarization.py``)
    and invoked as the ``chapter_done_callback`` of
    ``Summarizer.summarize_chapters`` immediately after EACH chapter's
    summary is produced — sequentially or in parallel.
    """

    def __init__(
        self,
        converter: Any,
        heading_positions: dict[str, int] | None = None,
        chapters_total: int = 0,
        build_docx: bool = True,
        book_title: str = "",
    ) -> None:
        self._converter = converter
        self._log = getattr(converter, "_log", None) or (lambda msg, level="INFO": None)
        self._positions: dict[str, int] = heading_positions or {}
        self._chapters_total = chapters_total
        self._book_title = book_title
        self._request = getattr(converter, "request", None)
        self._output_dir: Path = Path(converter.output_dir)
        self._summaries_dir: Path = Path(converter.paths.summaries_dir)
        self._chapters_root: Path = self._output_dir / "checkpoints" / "chapters"
        self._manifest_path: Path = self._output_dir / "checkpoints" / "chapter_manifest.json"
        self._sanitize = getattr(converter, "_sanitize_filename", None) or (
            lambda h: re.sub(r"[^\w\s\-]", "", re.sub(r"\s+", "_", (h or "").strip()))[:80]
        )
        self._build_docx = build_docx
        # Counters (for logging + tests)
        self.saved_count = 0
        self.skipped_existing = 0
        self.docx_count = 0
        self._logged_intro = False

    # ── public API (the callback) ────────────────────────────────────────

    def on_chapter_done(
        self,
        idx: int,
        summary: SummaryResult,
        chapter: dict[str, Any] | None = None,
    ) -> None:
        """Checkpoint one completed chapter. NEVER raises.

        Args:
            idx: 1-based index of the chapter within the chapters being
                summarized this run (fallback when no heading map).
            summary: the chapter's SummaryResult.
            chapter: the chapter dict (``heading``/``content``) — used for
                the per-chapter DOCX's full-content section.
        """
        try:
            self._on_chapter_done_impl(idx, summary, chapter)
        except Exception as e:  # best-effort — never crash the pipeline
            try:
                self._log(
                    f"  ⚠️ V18.20.3.0 chapter checkpoint failed for chapter "
                    f"{idx}: {e!r} — conversion continues (chapter outputs "
                    f"will still be written at the end of the phase).",
                    "WARNING",
                )
            except Exception:
                pass

    # ── internals ─────────────────────────────────────────────────────────

    def _on_chapter_done_impl(
        self,
        idx: int,
        summary: SummaryResult,
        chapter: dict[str, Any] | None,
    ) -> None:
        if not self._logged_intro:
            self._logged_intro = True
            self._log(
                f"  🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — "
                f"each chapter is saved (md + docx) the moment it completes; "
                f"crash-safe via {self._output_dir / 'checkpoints'}",
                "INFO",
            )

        # Mirror the end-of-loop rule: never checkpoint FAILED/empty summaries
        # (they must not produce COMPLETE files, or resume would skip them).
        if not getattr(summary, "success", True) or (
            not summary.executive_summary
            and not summary.bullet_points
            and not summary.thorough_summary
        ):
            self._log(
                f"  ⏭️ Checkpoint skip: chapter {idx} "
                f"('{(summary.chapter_heading or '?')[:40]}') failed/empty — "
                f"it will be reprocessed on resume.",
                "DEBUG",
            )
            return

        heading = (chapter or {}).get("heading") or summary.chapter_heading or f"Chapter {idx}"
        pos = self._positions.get(heading, idx)
        safe = self._sanitize(summary.chapter_heading or heading) or "chapter"
        # V0.4.25: run-stamped filename — unique per conversion so the
        # operator's file-transfer layer (caches attachments by filename)
        # can never deliver a stale run's bytes, and re-runs into the same
        # output dir coexist instead of colliding with old files. The stamp
        # comes from the summary's OWN provenance (adopted/resumed chapters
        # keep their ORIGINAL run's stamp — the filename always tells the
        # truth about which run produced the content). Unstamped (legacy)
        # results keep the exact legacy filename for write-once compat.
        _stamp = ""
        try:
            from core.system.provenance import run_stamp_suffix

            _stamp = run_stamp_suffix(
                getattr(summary, "app_version", ""), getattr(summary, "run_id", "")
            )
        except Exception:  # pragma: no cover — stamping must never break the save
            _stamp = ""
        sf_name = f"{pos:03d}_{safe}{_stamp}_summary.md"

        # V0.5.2 (FIX-P0-2): the V0.4.40 verification + polish LAYER now
        # runs BEFORE the checkpoint save (was dead code in the end-of-loop
        # writer at conversion/summarization.py:1065-1102 because the
        # file-existence short-circuit at summarization.py:1038-1060
        # fires `continue` BEFORE the try-block where the LAYER lived —
        # the V18.20.3.0 checkpoint writes the file mid-run, so the
        # end-of-loop always sees a COMPLETE-sentinel file and skips).
        # Re-wiring into the SAME path that writes the checkpoint means
        # the LAYER runs on every chapter (including checkpointed ones)
        # and the checkpoint writes the VERIFIED summary.md + DOCX (not
        # the pre-verification draft). Source = the chapter's own
        # ``content`` (the chapter dict carries the source directly —
        # simpler than the end-of-loop ``_source_for_summary`` heading-
        # match + largest-segment fallback, which is preserved for the
        # non-checkpointed path (``incremental_chapter_save=False``)).
        # Fail-open: a crash logs a WARNING and the draft ships (the
        # layer must never break the write). Content-agnostic (Rule 1).
        _rendered = render_summary_markdown(summary)
        _v_source = (chapter or {}).get("content") or ""
        if _v_source:
            try:
                from core.summarisation.verification_phase import (
                    verify_and_polish_summary,
                )

                # V0.5.6: pass the SummaryResult's ``source_glossary``
                # field through to the verification LAYER (the LLM-
                # generated ``<name_glossary>`` block from the master-
                # summary call — the LAYER uses it as the coverage
                # ground truth + the loosened quote-guard membership
                # test). Fail-open via ``getattr`` when the field
                # isn't populated yet (the V056-PROMPT-PARSER subagent
                # adds the field; until then the LAYER falls back to
                # the V0.5.5 regex behavior).
                _v_glossary = getattr(summary, "source_glossary", None)
                _rendered, _v_issues = verify_and_polish_summary(
                    _rendered,
                    _v_source,
                    self._converter.settings,
                    self._log,
                    source_glossary=_v_glossary,
                    chapter_heading=summary.chapter_heading or heading,
                )
                # V0.5.1 (BUG fix): LOG the verification issues to the
                # conversion log (was silently dropped — the audit
                # couldn't see the date-check + LLM verification output).
                for _vi in _v_issues or []:
                    self._log(
                        f"    ✨ V0.5.1 verification: "
                        f"[{_vi.detector}/{_vi.severity}] "
                        f"{_vi.detail[:120]}",
                        "DEBUG" if _vi.severity == "fix" else "WARNING",
                    )
            except Exception as _ve:  # pragma: no cover — layer must never break write
                self._log(
                    f"    ⚠️  V0.4.40 verification crashed (non-fatal): {type(_ve).__name__}: {_ve}",
                    "WARNING",
                )

        # 1) canonical summary file (resume-compatible) — write-once.
        #    Writes the VERIFIED markdown (post-V0.5.2 FIX-P0-2 re-wire).
        sf = self._summaries_dir / sf_name
        wrote_canonical = self._atomic_write_once(sf, _rendered)
        if not wrote_canonical:
            self.skipped_existing += 1

        # 2) dedicated checkpoint folder: md copy + per-chapter DOCX.
        #    The md copy is the VERIFIED markdown (matches the canonical
        #    file byte-for-byte — both come from the same ``_rendered``).
        chapter_folder = self._chapters_root / f"{pos:03d}_{safe}"
        chapter_folder.mkdir(parents=True, exist_ok=True)
        cp_md = chapter_folder / sf_name
        self._atomic_write_once(cp_md, _rendered, quiet=True)

        docx_path: Path | None = None
        if self._build_docx:
            # V0.6.6 (review-loop L2-3): the per-chapter DOCX now carries
            # the SAME run stamp as its sibling .md — an un-stamped name
            # was shared across runs, so a resumed duplicate-heading
            # chapter OVERWROTE the completed chapter's DOCX at the same
            # pos+heading path (fresh-eyes probe: RUN1 marker gone after
            # RUN2), violating the "completed chapters are never touched"
            # guarantee. Stamped names coexist per run instead.
            docx_path = self._build_chapter_docx(
                summary,
                chapter or {"heading": heading, "content": ""},
                chapter_folder / f"{pos:03d}_{safe}{_stamp}_summary.docx",
            )
            if docx_path is not None:
                self.docx_count += 1

        # 3) manifest + checkpoint phase progress
        self.saved_count += 1
        self._update_manifest(pos, heading, sf, chapter_folder, docx_path, summary)
        self._mark_checkpoint_progress()

        _docx_note = " + DOCX" if docx_path is not None else ""
        self._log(
            f"  🛟 Checkpoint saved: chapter {pos}"
            f"{f'/{self._chapters_total}' if self._chapters_total else ''} "
            f"'{heading[:40]}' → summaries/{sf_name}{_docx_note}",
            "DEBUG",
        )

    def _atomic_write_once(self, path: Path, content: str, quiet: bool = False) -> bool:
        """Atomic write with write-once semantics.

        Returns True if this call wrote the file, False if a COMPLETE file
        already existed (untouched guarantee). A file that exists WITHOUT
        the marker is rewritten (belt-and-suspenders for pre-atomic-era
        partial writes).
        """
        from utils.atomic_io import atomic_write_text

        if path.exists():
            try:
                _existing = path.read_text(encoding="utf-8")
                # V18.20.3.7: accepts BOTH the legacy bare sentinel and the
                # run-id-stamped form; when the existing file was produced
                # by a DIFFERENT run, the skip is logged with both run ids
                # (the V18.20.3.6 audit spent two sessions proving which
                # run wrote a file — now the log says it outright). Resume
                # semantics UNCHANGED: cross-run adoption is the documented
                # chapter-resume feature, so the run id is audit info, not
                # a write-once discriminator.
                from core.system.provenance import (
                    adoption_note,
                    has_complete_sentinel,
                )

                if has_complete_sentinel(_existing):
                    if not quiet:
                        _note = adoption_note(_existing, content)
                        self._log(
                            f"  🛟 Checkpoint intact — not rewriting {path.name} "
                            f"(completed chapters are never touched)."
                            + (f" 🪪 {_note}." if _note else ""),
                            "DEBUG",
                        )
                    return False
            except OSError as _e:
                # V0.4.27 (Phase-5 P1 / W3-E1, audit backlog, site 2 of 3):
                # a transient read error (AV/indexer lock on a COMPLETED
                # chapter) can't check the sentinel → falls through to
                # rewrite → can clobber the 'completed chapters are never
                # touched' guarantee. Control-flow UNCHANGED per Phase-5
                # P1 (rewrite-on-true-corruption semantics kept — a
                # genuinely corrupt file must still be rewritten); the
                # WARNING surfaces the transient-error case for diagnosis.
                log_swallow(
                    "checkpoint_read_existing",
                    _e,
                    level=logging.WARNING,
                    detail=f"path={path}",
                )
                # unreadable → rewrite (control-flow unchanged)
        atomic_write_text(path, content)
        return True

    def _build_chapter_docx(
        self, summary: SummaryResult, chapter: dict[str, Any], out_path: Path
    ) -> Path | None:
        """Build the per-chapter DOCX report atomically (tmp + os.replace).

        V18.20.3.1 (real-rig audit D4): the builder's own "✅ DOCX saved to …"
        log line reported the TEMP path (``…_summary.docx.tmp``) because it
        received ``tmp_path`` — the user-facing log then showed a file that
        doesn't exist after the rename. The log callback now rewrites the
        tmp path to the final path, so the log stays truthful.
        """
        try:
            from core.docx.builder import DocxBuilder

            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

            def _truthful_log(msg: str, level: str = "INFO") -> None:
                # Rewrite the tmp path → final path in builder log lines.
                try:
                    if str(tmp_path) in str(msg):
                        msg = str(msg).replace(str(tmp_path), str(out_path))
                except Exception:
                    pass
                self._log(msg, level)

            builder = DocxBuilder(self._request, log_callback=_truthful_log)
            ok = builder.build_report(
                [summary],
                [
                    {
                        "heading": chapter.get("heading", summary.chapter_heading),
                        "content": chapter.get("content", ""),
                    }
                ],
                getattr(self._request, "input_path", self._output_dir),
                tmp_path,
            )
            if not ok:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None
            os.replace(tmp_path, out_path)
            return out_path
        except Exception as e:
            self._log(
                f"  ⚠️ Per-chapter DOCX checkpoint failed for "
                f"'{summary.chapter_heading[:40]}': {e!r} — md checkpoint "
                f"still saved.",
                "WARNING",
            )
            return None

    def _update_manifest(
        self,
        pos: int,
        heading: str,
        canonical_md: Path,
        chapter_folder: Path,
        docx_path: Path | None,
        summary: SummaryResult,
    ) -> None:
        """Merge this chapter's record into checkpoints/chapter_manifest.json."""
        from utils.atomic_io import atomic_write_json

        manifest = self._load_manifest()
        chapters: dict[str, Any] = manifest.setdefault("chapters", {})
        # V0.6.6 (review-loop L2-3): keyed by the canonical FILENAME, not
        # str(pos) — pos is not unique once duplicate headings fall back
        # to per-run indexes (a fallback idx can equal another chapter's
        # mapped position; the fresh-eyes probe ended with one manifest
        # record clobbering another). The canonical md filename is unique
        # per chapter+run (pos + heading + run stamp) — and it still
        # merges idempotently: a re-saved chapter rewrites its own record.
        chapters[canonical_md.name] = {
            "pos": pos,
            "heading": heading,
            "done_at": datetime.now().isoformat(timespec="seconds"),
            "summary_md": str(canonical_md),
            "chapter_folder": str(chapter_folder),
            "docx": str(docx_path) if docx_path else None,
            "bullets": len(summary.bullet_points or []),
            "exec_chars": len(summary.executive_summary or ""),
            "success": bool(getattr(summary, "success", True)),
        }
        manifest["version"] = _MANIFEST_VERSION
        manifest["book"] = self._book_title or (self._output_dir.name)
        manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            atomic_write_json(self._manifest_path, manifest, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(
                f"  ⚠️ Chapter manifest update failed: {e!r} — chapter files "
                f"remain saved; only the manifest summary is stale.",
                "WARNING",
            )

    def _load_manifest(self) -> dict[str, Any]:
        """Load the manifest, tolerating absence/corruption (crash safety)."""
        try:
            if self._manifest_path.exists():
                import json

                data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _mark_checkpoint_progress(self) -> None:
        """Record chapters-done progress on the phase-level checkpoint.

        V18.20.3.0: uses ``Checkpoint.mark_progress`` — status stays
        "pending" (NEVER "done") until the whole summarization phase
        completes, preserving the A15 invariant: a partial/crashed run must
        re-enter the summarization phase on resume; the chapter-resume
        sentinels decide which chapters to skip.
        """
        try:
            cp = getattr(self._converter, "checkpoint", None)
            if cp is None:
                return
            done = self.saved_count + self.skipped_existing
            cp.mark_progress(
                "summarization",
                chapters_done=done,
                **({"chapters_total": self._chapters_total} if self._chapters_total else {}),
            )
        except Exception as e:
            self._log(f"  ⚠️ Checkpoint progress update failed: {e!r}", "DEBUG")
