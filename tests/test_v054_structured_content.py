"""V0.5.4 — Track B3+B4+C1 (structured content reproduction + section breaks).

Pins the three new structured-content features that close the V0.5.3 audit
gaps (the AUDIT-V0.5.3-ground-truth findings — coverage 7/10 because the
summary did not reproduce the source's Table 6-1, did not reproduce the
DSM-III criteria detail, and did not preserve the source's 5 ALL-CAPS
section structure):

  C1 (P1, rendering) — section breaks mirroring the source.
    The summary builder now groups key-takeaway bullets under the source's
    ALL-CAPS section headings (``## DESCRIPTIVE STUDIES``, ``## PSYCHOANALYTIC
    VIEWS``, …). The mapping is fully runtime-derived — the deterministic
    analyzer extracts the source's ALL-CAPS sections + the author-per-section
    list, the renderer assigns each bullet to its section by word-boundary
    author match. NO hardcoded section names. The test fixture's source text
    uses DESCRIPTIVE STUDIES + PSYCHOANALYTIC VIEWS with Magnan/Kraepelin
    cited under DESCRIPTIVE and Freud/Blum under PSYCHOANALYTIC — the
    rendered summary must carry BOTH section headings.

  B3 (P2, structured tables) — Table N-N reproduction.
    The deterministic analyzer detects the generic ``TABLE N-N.`` marker and
    extracts the following markdown-table rows verbatim. The renderer
    reproduces them under a clearly-labelled ``## Reproduced Tables (from
    source)`` section — no LLM paraphrasing. The test fixture's source text
    has ``TABLE 6-1.`` + a 3-row markdown table; the summary's detailed
    section must contain the reproduced table.

  B4 (P3, structured criteria) — DSM-style criteria reproduction.
    The deterministic analyzer detects the generic ``a. b. c. d.`` +
    ``(i) (ii) (iii)`` pattern and extracts each cluster. The renderer
    reproduces them as a nested bullet list under a clearly-labelled
    ``## Reproduced Diagnostic Criteria (from source)`` section. The test
    fixture's source text has a 2-letter criteria block (a. with (i)/(ii);
    b. with (i)) and the rendered summary must reproduce them as a nested
    bullet list.

GENERAL rules pinned (the book is only the test that exposed them — the
fixes are content-agnostic and would help any book/chapter with explicit
table markers, structured criteria, or ALL-CAPS section headings):

  - the structured-content extractors live in the deterministic analyzer
    (regex-only, 100% reliable, no LLM in the loop);
  - the rendering lives in render_summary_markdown (single source of
    truth — used by both the incremental checkpoint saver and the end-of-
    loop writer);
  - the wiring lives on the Summarizer (the analyzer is invoked once per
    chapter, the payload is stamped onto the SummaryResult, the renderer
    consumes it);
  - empty payloads (legacy / test fixtures that don't opt in) render
    byte-identical to before — strict improvement, never a regression;
  - Rule 1 (content-agnostic): the production code uses GENERIC patterns
    only (``TABLE \\d+-\\d+\\.`` / ``a. b. c. d.`` + ``(i) (ii)`` / ALL-CAPS
    detection). The book-derived names (DESCRIPTIVE STUDIES, Table 6-1,
    DSM-III, Magnan, Freud, etc.) appear in THIS TEST FILE ONLY as test
    fixtures — never in the production code.
"""

from __future__ import annotations

from core.models import SummaryResult
from core.pipeline.chapter_checkpoint import render_summary_markdown
from core.preprocessing.deterministic_analyzer import (
    extract_structured_criteria,
    extract_structured_tables,
    map_authors_to_all_caps_sections,
)

# ─── shared test fixtures ────────────────────────────────────────────────────


def _mk_summary(**kw) -> SummaryResult:
    """Build a SummaryResult with sensible defaults; tests override fields."""
    base = dict(
        chapter_heading="Test Chapter",
        executive_summary="Exec text.",
        thorough_summary="Thorough text.",
        bullet_points=["A bullet.", "Another bullet."],
    )
    base.update(kw)
    return SummaryResult(**base)


_C1_SOURCE_TEXT = """\
INTRODUCTION

A short intro paragraph.

DESCRIPTIVE STUDIES

Magnan (1880) described the du délire chronique evolution. Kraepelin (1905)
framed the paranoid constitution. Bleuler (1908) named the paranoid
condition.

PSYCHOANALYTIC VIEWS

Freud (1910) traced paranoia to repressed homosexuality. Blum (1946)
elaborated the projective mechanism. Klein (1957) connected it to the
paranoid-schizoid position.

COMMENT

A short closing paragraph.
"""


_B3_SOURCE_TEXT = """\
AN ATTEMPT AT SYNTHESIS

A short synthesis paragraph.

TABLE 6-1. Clinical Features of a Hypothetical Disorder.

| Area | Overt | Covert |
|---|---|---|
| Self-concept | arrogant, grandiose | timid, gullible |
| Interpersonal | mistrustful | devoted, dependent |

A closing paragraph after the table.
"""


_B4_SOURCE_TEXT = """\
DSM-III AND DSM-III-R

DSM-III listed the following diagnostic criteria (1980, p. 309):

a. Pervasive, unwarranted suspiciousness as indicated by at least three of the following:

(i) expectation of trickery or harm
(ii) hypervigilance, manifested by continual scanning of the environment
(iii) guardedness or secretiveness

b. Hypersensitivity as indicated by at least two of the following:

(i) tendency to be easily slighted and quick to take offense
(ii) exaggeration of difficulties, e.g., making mountains out of molehills

While seemingly adequate, these criteria left much to be desired.
"""


# ─── C1 — section breaks mirroring the source ────────────────────────────────


class TestC1SectionBreaksMirrorSource:
    """C1 (Track C1): the summary's bullets are grouped under the source's
    ALL-CAPS section headings — the renderer inserts ``## {Section Title}``
    before each group. Pure rendering change: the bullets are already
    generated; the source-section_map is the deterministic analyzer's output
    on the chapter source."""

    def test_section_breaks_mirror_source(self):
        """A summary whose source has DESCRIPTIVE STUDIES + PSYCHOANALYTIC
        VIEWS sections, with bullets citing Magnan/Kraepelin (DESCRIPTIVE)
        and Freud/Blum (PSYCHOANALYTIC), renders BOTH section headings and
        the bullets grouped under each."""
        section_map = map_authors_to_all_caps_sections(_C1_SOURCE_TEXT)
        # sanity-check the deterministic map before the rendering assertion
        # — if the analyzer missed a section the renderer can't render it.
        section_titles = [s["section_title"] for s in section_map]
        assert "DESCRIPTIVE STUDIES" in section_titles
        assert "PSYCHOANALYTIC VIEWS" in section_titles
        # the authors must be associated with their correct sections so the
        # renderer's bullet→section assignment has signal to work with.
        descriptive = next(s for s in section_map if s["section_title"] == "DESCRIPTIVE STUDIES")
        assert "Magnan" in descriptive["authors"]
        assert "Kraepelin" in descriptive["authors"]
        psychoanalytic = next(
            s for s in section_map if s["section_title"] == "PSYCHOANALYTIC VIEWS"
        )
        assert "Freud" in psychoanalytic["authors"]
        assert "Blum" in psychoanalytic["authors"]

        # build the SummaryResult with bullets citing the section's authors
        # — the same way the Summarizer would after the LLM produces them.
        summ = _mk_summary(
            bullet_points=[
                "Magnan (1880) traced the chronic delusion evolution.",
                "Kraepelin (1905) framed the paranoid constitution.",
                "Freud (1910) traced paranoia to repressed homosexuality.",
                "Blum (1946) elaborated the projective mechanism.",
            ],
            source_section_map=section_map,
        )
        md = render_summary_markdown(summ)
        # BOTH source-section headings must appear in the rendered summary,
        # each preceding the bullets that cite the section's authors.
        assert "## DESCRIPTIVE STUDIES" in md
        assert "## PSYCHOANALYTIC VIEWS" in md
        # the bullets citing DESCRIPTIVE authors are grouped UNDER the
        # DESCRIPTIVE heading, NOT under PSYCHOANALYTIC — assert ordering.
        descriptive_pos = md.index("## DESCRIPTIVE STUDIES")
        psychoanalytic_pos = md.index("## PSYCHOANALYTIC VIEWS")
        # Magnan + Kraepelin bullets appear after DESCRIPTIVE and before
        # PSYCHOANALYTIC (the source's section order).
        magnan_pos = md.index("Magnan")
        kraepelin_pos = md.index("Kraepelin")
        freud_pos = md.index("Freud")
        blum_pos = md.index("Blum")
        assert descriptive_pos < magnan_pos < psychoanalytic_pos
        assert descriptive_pos < kraepelin_pos < psychoanalytic_pos
        assert psychoanalytic_pos < freud_pos
        assert psychoanalytic_pos < blum_pos

    def test_legacy_summary_without_section_map_still_flat(self):
        """Strict-improvement contract: a SummaryResult WITHOUT a
        source_section_map (every legacy fixture + every test that doesn't
        opt in) renders the bullets as a flat list under the canonical
        ``## Key Takeaways`` heading — byte-identical to the pre-V0.5.4
        output."""
        summ = _mk_summary(
            bullet_points=["Bullet one.", "Bullet two."],
            # source_section_map intentionally NOT set (defaults to [])
        )
        md = render_summary_markdown(summ)
        assert "## Key Takeaways" in md
        assert "- Bullet one." in md
        assert "- Bullet two." in md

    def test_section_map_with_no_author_matches_falls_back_to_flat(self):
        """When the section_map is present but the bullets cite NO author
        from any section, the renderer falls back to the legacy flat list
        (strict-improvement: never regresses, never emits an empty section)."""
        section_map = map_authors_to_all_caps_sections(_C1_SOURCE_TEXT)
        # bullets that cite NEITHER Magnan/Kraepelin NOR Freud/Blum
        summ = _mk_summary(
            bullet_points=[
                "A general observation about the literature.",  # no author
                "Another general takeaway.",  # no author
            ],
            source_section_map=section_map,
        )
        md = render_summary_markdown(summ)
        # legacy flat list under Key Takeaways (the ungrouped fallback).
        assert "## Key Takeaways" in md
        # the section headings DO NOT appear (no bullets assigned to them
        # → no empty headings, per the V0.05 rig F9a rule).
        assert "## DESCRIPTIVE STUDIES" not in md
        assert "## PSYCHOANALYTIC VIEWS" not in md


# ─── B3 — Table N-N reproduction ─────────────────────────────────────────────


class TestB3TableReproduced:
    """B3 (Track B3): when the source has an explicit ``TABLE N-N.`` marker
    followed by a markdown table, the deterministic analyzer extracts it and
    the renderer reproduces it verbatim under a clearly-labelled section."""

    def test_table_reproduced(self):
        """A source with ``TABLE 6-1.`` + a markdown table → the summary's
        detailed section contains the reproduced table (verbatim rows)."""
        tables = extract_structured_tables(_B3_SOURCE_TEXT)
        # sanity-check the deterministic extractor before the rendering
        # assertion — if the extractor missed the table, the renderer can't
        # reproduce it.
        assert len(tables) == 1
        t = tables[0]
        assert t["marker"] == "TABLE 6-1."
        assert "Clinical Features" in t["title"]
        # the markdown-table rows are reproduced verbatim (header + sep + 2
        # data rows = 4 lines minimum).
        assert len(t["content_lines"]) >= 4
        assert any("Self-concept" in line for line in t["content_lines"])
        assert any("Interpersonal" in line for line in t["content_lines"])

        summ = _mk_summary(
            bullet_points=["A takeaway about the clinical features."],
            reproduced_tables=tables,
        )
        md = render_summary_markdown(summ)
        # the reproduced-tables section heading is clearly labelled so a
        # reader can distinguish reproduced-source tables from summarizer-
        # authored additive-section tables.
        assert "## Reproduced Tables (from source)" in md
        # the marker + title render as a bolded label.
        assert "**TABLE 6-1.**" in md
        # the markdown-table rows reproduce verbatim (no paraphrasing).
        assert "| Area | Overt | Covert |" in md
        assert "|---|---|---|" in md
        assert "| Self-concept | arrogant, grandiose | timid, gullible |" in md
        assert "| Interpersonal | mistrustful | devoted, dependent |" in md

    def test_source_without_table_marker_yields_no_tables_section(self):
        """Conservative scope: a source without ``TABLE N-N.`` produces NO
        reproduced-tables section (legacy behavior — the renderer emits no
        empty section heading)."""
        # _C1_SOURCE_TEXT has no TABLE N-N. marker.
        tables = extract_structured_tables(_C1_SOURCE_TEXT)
        assert tables == []
        summ = _mk_summary(
            bullet_points=["A takeaway."],
            reproduced_tables=tables,  # empty list
        )
        md = render_summary_markdown(summ)
        assert "## Reproduced Tables (from source)" not in md

    def test_implicit_table_not_reproduced(self):
        """Conservative scope: a markdown table WITHOUT the ``TABLE N-N.``
        marker is NOT reproduced (the conservative-marker contract keeps the
        reproduction honest — implicit tables would inject noise)."""
        src = """\
A paragraph.

| col1 | col2 |
|---|---|
| a | b |

Another paragraph.
"""
        tables = extract_structured_tables(src)
        # the marker regex requires the explicit "TABLE N-N." prefix;
        # a bare markdown table does NOT trigger the extractor.
        assert tables == []


# ─── B4 — DSM-style criteria reproduction ─────────────────────────────────────


class TestB4CriteriaReproduced:
    """B4 (Track B4): when the source has the DSM-style ``a. b. c. d.`` +
    ``(i) (ii) (iii)`` pattern, the deterministic analyzer extracts it and
    the renderer reproduces it as a nested bullet list under a clearly-
    labelled section."""

    def test_criteria_reproduced(self):
        """A source with ``a. ... (i) ... (ii) ... (iii) ... b. ... (i) ...``
        → the summary has a nested bullet list reproducing the criteria."""
        criteria = extract_structured_criteria(_B4_SOURCE_TEXT)
        # sanity-check the deterministic extractor before the rendering
        # assertion.
        assert len(criteria) == 1
        cluster = criteria[0]
        items = cluster["items"]
        # the cluster must contain both lettered criteria (a and b) and
        # each must carry its Roman sub-items.
        letters = [it["letter"] for it in items]
        assert "a" in letters
        assert "b" in letters
        item_a = next(it for it in items if it["letter"] == "a")
        assert "Pervasive, unwarranted suspiciousness" in item_a["text"]
        a_subs = [m for m, _ in item_a["sub_items"]]
        assert "i" in a_subs
        assert "ii" in a_subs
        assert "iii" in a_subs
        item_b = next(it for it in items if it["letter"] == "b")
        assert "Hypersensitivity" in item_b["text"]
        b_subs = [m for m, _ in item_b["sub_items"]]
        assert "i" in b_subs
        assert "ii" in b_subs

        summ = _mk_summary(
            bullet_points=["A takeaway about the diagnostic criteria."],
            reproduced_criteria=criteria,
        )
        md = render_summary_markdown(summ)
        # the reproduced-criteria section heading is clearly labelled.
        assert "## Reproduced Diagnostic Criteria (from source)" in md
        # each lettered criterion renders as a top-level bullet with the
        # letter bolded.
        assert "- **a.** Pervasive, unwarranted suspiciousness" in md
        assert "- **b.** Hypersensitivity" in md
        # each Roman sub-item renders as an INDENTED bullet (two leading
        # spaces before the dash) under its lettered parent.
        assert "  - (i) expectation of trickery or harm" in md
        assert "  - (ii) hypervigilance" in md
        assert "  - (iii) guardedness or secretiveness" in md
        assert "  - (i) tendency to be easily slighted" in md
        # the lettered parent appears BEFORE its Roman sub-items (nested
        # bullet structure — the indentation contract).
        a_letter_pos = md.index("- **a.**")
        i_sub_pos = md.index("  - (i) expectation")
        assert a_letter_pos < i_sub_pos

    def test_source_without_criteria_pattern_yields_no_criteria_section(self):
        """Conservative scope: a source without the ``a. ... (i) ...`` pattern
        produces NO reproduced-criteria section (legacy behavior)."""
        # _C1_SOURCE_TEXT has no lettered+Roman pattern.
        criteria = extract_structured_criteria(_C1_SOURCE_TEXT)
        assert criteria == []
        summ = _mk_summary(
            bullet_points=["A takeaway."],
            reproduced_criteria=criteria,  # empty list
        )
        md = render_summary_markdown(summ)
        assert "## Reproduced Diagnostic Criteria (from source)" not in md

    def test_bare_numbered_list_not_reproduced(self):
        """Conservative scope: a numbered list (``1. 2. 3.``) WITHOUT the
        lettered+Roman pattern is NOT reproduced (the conservative shape
        contract — only DSM-style ``a. b. c. d.`` + ``(i) (ii)`` is
        reproduced)."""
        src = """\
A paragraph.

1. First item
2. Second item
3. Third item

Another paragraph.
"""
        criteria = extract_structured_criteria(src)
        # the criteria extractor requires the lettered-parent + Roman-sub
        # shape; a bare numbered list does NOT match.
        assert criteria == []


# ─── combined C1+B3+B4 — end-to-end summary carries all three ────────────────


class TestCombinedAllThree:
    """End-to-end: a SummaryResult carrying ALL three payloads (section_map
    + reproduced_tables + reproduced_criteria) renders a summary with ALL
    three sections + grouped bullets."""

    def test_summary_carries_sections_tables_and_criteria(self):
        section_map = map_authors_to_all_caps_sections(_C1_SOURCE_TEXT)
        tables = extract_structured_tables(_B3_SOURCE_TEXT)
        criteria = extract_structured_criteria(_B4_SOURCE_TEXT)
        # sanity check
        assert section_map and tables and criteria

        summ = _mk_summary(
            bullet_points=[
                "Magnan (1880) traced the chronic delusion evolution.",
                "Freud (1910) traced paranoia to repressed homosexuality.",
            ],
            source_section_map=section_map,
            reproduced_tables=tables,
            reproduced_criteria=criteria,
        )
        md = render_summary_markdown(summ)
        # ALL three new sections render (no one is shadowed by another).
        assert "## DESCRIPTIVE STUDIES" in md
        assert "## PSYCHOANALYTIC VIEWS" in md
        assert "## Reproduced Tables (from source)" in md
        assert "## Reproduced Diagnostic Criteria (from source)" in md
        # the legacy contract is preserved: exec + thorough still render.
        assert "## Executive Summary" in md
        assert "## Thorough Summary" in md
        # the COMPLETE sentinel still closes the file (provenance preserved).
        assert md.rstrip().endswith("<!-- COMPLETE -->")
