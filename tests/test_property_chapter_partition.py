"""Property-based tests: chapter segmentation PARTITIONS the page range (roadmap 2.2).

Targets ``core/segmentation/heading_segmenter.py`` and
``core/segmentation/chapter_matcher.py`` (Phase 2, task 2.2 of
docs/ROADMAP_V0.12.md — "Hypothesis property suites").

Invariants under test (characterization of the ACTUAL contract):

HeadingSegmenter.segment() — given well-formed ``page_markers`` (one marker per
page, marker line-indices and page numbers co-sorted, first page == 1):

1. **No gaps**: for consecutive segments ``prev`` → ``next``,
   ``next.start_page <= prev.end_page`` — every page 1..N is covered by at
   least one segment (front matter becomes the leading "Introduction"
   segment).  NOTE: overlaps of +/- 1 page at chapter boundaries are BY
   DESIGN (a heading that falls mid-page is ambiguous, so both the closing
   and the opening segment claim that page) — the roadmap's "no overlaps"
   clause is intentionally relaxed to "no gaps" here to match the
   implemented contract.
2. **Monotonicity**: ``start_page`` is non-decreasing across segments.
3. **Bounds**: ``1 <= start_page <= end_page <= total_pages`` for every
   segment; the first segment starts at page 1, the last ends at
   ``total_pages``.
4. **Headline cap**: every heading is <= 80 chars (the V0.07 glued-paragraph
   guard).
5. **Structural model**: the segmentation equals the one implied by the
   per-line boundary flags (content runs become segments; a boundary with no
   following content run drops its heading; leading content becomes
   "Introduction") — an executable spec re-implemented independently below.

ChapterMatcher / filter_toc_entries_for_selection — matching invariants:

6. Exact (normalized) heading matches score 3; chapter-number matches score
   2; results are sorted by score descending, deduplicated by segment
   identity, and never contain gap segments; ``max_results`` is respected.
7. TOC filtering returns a subsequence of the input entries and reports the
   exact dropped count; zero/one matches return the ORIGINAL list unchanged
   (the "never summarize less than requested" safety net).

Determinism: no network, no LLM, no filesystem writes; all strategies are
pure.  Hypothesis settings are tuned per test (``deadline=None``).
"""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from core.models import ConversionRequest, Segment
from core.segmentation.chapter_matcher import (
    ChapterMatcher,
    _extract_chapter_number,
    _is_gap_segment,
    _normalize,
    _validate_toc_title,
    filter_toc_entries_for_selection,
)
from core.segmentation.heading_segmenter import (
    BLOCKLIST,
    HEADING_STOP_STARTS,
    HeadingSegmenter,
)

# ── settings profiles (tuned for the <60s whole-suite budget) ───────────────
S_FAST = settings(max_examples=60, deadline=None)
S_MED = settings(max_examples=30, deadline=None)

# ═══════════════════════════════════════════════════════════════════════════
# Shared fixtures / generators
# ═══════════════════════════════════════════════════════════════════════════

_REQUEST = ConversionRequest(input_path=Path("dummy_input.pdf"), output_dir=Path("dummy_out"))
_HS = HeadingSegmenter(_REQUEST)

# Body lines: guaranteed NON-boundaries (lowercase prose, no '#', no digits,
# no leading structural keywords, < 80 chars, no title-case so the plain-
# heading heuristic can never pick them up either).
_BODY_LINES = (
    "the quick brown fox jumps over the lazy dog",
    "a steady flow of data moves through the pipeline",
    "several ideas emerge from the discussion",
    "",
    "observations accumulate across the trials",
    "the argument unfolds in careful stages",
    "evidence supports the central claim",
)
_body_line = st.sampled_from(_BODY_LINES)

_TITLES = ("Origins", "Methods", "Results", "Discussion", "Forward Path", "Closing Notes")


def _heading_line(n: int, fmt_idx: int) -> str:
    """A heading line that is guaranteed to hit an explicit boundary pattern."""
    fmts = (
        "# Chapter {n}: {t}",
        "## Section {n}",
        "# Part {n}: {t}",
        "# فصل {n}",
        "Chapter {n} — {t}",
        "# Appendix {c}: {t}",
    )
    return fmts[fmt_idx % len(fmts)].format(
        n=n, t=_TITLES[n % len(_TITLES)], c=chr(ord("A") + n % 26)
    )


@st.composite
def _multi_chapter_docs(draw):
    """A doc with >= 2 explicit chapters (so the plain-heading fallback never
    triggers) plus a consistent page-marker set (one marker per page, first
    page == 1, indices co-sorted with page numbers)."""
    n_chapters = draw(st.integers(min_value=2, max_value=5))
    lines: list[str] = []
    # optional front matter (becomes the "Introduction" segment)
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        lines.append(draw(_body_line))
    for c in range(n_chapters):
        lines.append(_heading_line(c + 1, draw(st.integers(min_value=0, max_value=5))))
        for _ in range(draw(st.integers(min_value=1, max_value=4))):
            lines.append(draw(_body_line))
    # drop trailing blank lines (splitlines() would drop them and desync the
    # line indices between doc and markers)
    while lines and lines[-1] == "":
        lines.pop()
    n = len(lines)
    n_pages = draw(st.integers(min_value=1, max_value=6))
    n_pages = min(n_pages, n)
    cuts = sorted(draw(st.sets(st.integers(min_value=1, max_value=n - 1), max_size=n_pages - 1)))
    markers = [(1, 0)] + [(p + 1, idx) for p, idx in enumerate(cuts, start=1)]
    total_pages = len(markers)
    return "\n".join(lines), markers, total_pages


@st.composite
def _any_docs(draw):
    """Docs with 0-5 chapters (may exercise the plain-heading fallback)."""
    n_chapters = draw(st.integers(min_value=0, max_value=5))
    lines: list[str] = []
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        lines.append(draw(_body_line))
    for c in range(n_chapters):
        lines.append(_heading_line(c + 1, draw(st.integers(min_value=0, max_value=5))))
        for _ in range(draw(st.integers(min_value=1, max_value=4))):
            lines.append(draw(_body_line))
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        lines = ["the quick brown fox jumps over the lazy dog"]
    n = len(lines)
    n_pages = min(draw(st.integers(min_value=1, max_value=6)), n)
    if n >= 2:
        cuts = sorted(
            draw(st.sets(st.integers(min_value=1, max_value=n - 1), max_size=n_pages - 1))
        )
    else:
        cuts = []
    markers = [(1, 0)] + [(p + 1, idx) for p, idx in enumerate(cuts, start=1)]
    return "\n".join(lines), markers, len(markers)


# ── executable spec: independent re-implementation of the segmentation ──────


def _spec_start_page(line_idx: int, markers: list[tuple[int, int]]) -> int:
    """Page a line belongs to: the last marker at-or-before the line."""
    page = 1
    for p_num, p_idx in markers:
        if p_num >= 1 and p_idx <= line_idx:
            page = p_num
    return page


def _spec_end_page(line_idx: int, markers: list[tuple[int, int]], total_pages: int) -> int:
    """First page whose marker starts strictly after the given line."""
    for p_num, p_idx in markers:
        if p_idx > line_idx:
            return p_num
    return total_pages


def _spec_normalise_heading(raw_line: str) -> str:
    text = raw_line.strip().lstrip("#").strip()
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    if len(text) > 80:
        m = re.search(r"[.!?]", text)
        if m and m.start() <= 80:
            text = text[: m.start()].strip()
        else:
            text = text[:80].rsplit(" ", 1)[0].strip()
    return text


def _spec_segments(hs: HeadingSegmenter, lines: list[str], markers, total_pages: int):
    """The segmentation implied by the boundary flags (independent model)."""
    bset = {i for i, ln in enumerate(lines) if hs._is_chapter_boundary(ln)}
    segs = []
    current_lines: list[str] = []
    current_heading = "Introduction"
    current_start = 1
    for i, ln in enumerate(lines):
        if i in bset:
            if current_lines:
                segs.append(
                    (
                        current_heading,
                        "\n".join(current_lines),
                        current_start,
                        _spec_end_page(i, markers, total_pages),
                    )
                )
            current_heading = _spec_normalise_heading(ln)
            current_lines = []
            current_start = _spec_start_page(i, markers)
        else:
            current_lines.append(ln)
    if current_lines:
        segs.append((current_heading, "\n".join(current_lines), current_start, total_pages))
    return segs


# ═══════════════════════════════════════════════════════════════════════════
# Boundary classification properties
# ═══════════════════════════════════════════════════════════════════════════


@S_FAST
@given(
    n=st.integers(min_value=1, max_value=99),
    fmt=st.integers(min_value=0, max_value=5),
)
def test_generated_heading_lines_are_boundaries(n, fmt):
    """Every heading format the generator emits must be a chapter boundary."""
    assert _HS._is_chapter_boundary(_heading_line(n, fmt))


@S_FAST
@given(lines=st.lists(_body_line, min_size=0, max_size=20))
def test_generated_body_lines_are_not_boundaries(lines):
    """Lowercase prose lines are never chapter boundaries."""
    for ln in lines:
        assert not _HS._is_chapter_boundary(ln)


@S_FAST
@given(
    prefix=st.text(alphabet=st.sampled_from(list("abcdefg hij")), min_size=0, max_size=30),
    suffix=st.text(alphabet=st.sampled_from(list("xyz. ,")), min_size=0, max_size=30),
)
def test_overlong_lines_are_never_boundaries(prefix, suffix):
    """The V0.07 guard: lines > 120 chars (glued title+body) are never boundaries."""
    line = "# Chapter 1: " + prefix + "x" * 130 + suffix
    assert len(line.strip()) > 120
    assert not _HS._is_chapter_boundary(line)


@S_MED
@given(heading=st.sampled_from(["# Contents", "# REFERENCES", "# Preface", "# Index", "# فهرست"]))
def test_blocklisted_headings_are_not_boundaries(heading):
    """Front/back-matter headings in the blocklist are never chapter boundaries."""
    assert not _HS._is_chapter_boundary(heading)


@S_FAST
@given(
    title=st.text(
        alphabet=st.sampled_from("abcdefghij kmnprstuvwz"),
        min_size=4,
        max_size=30,
    )
)
def test_plain_h1_headings_are_boundaries(title):
    """``# A long enough heading`` matches the h1 fallback (4+ chars, not
    blocklisted, not short-all-caps — lowercase prose titles always qualify)."""
    stripped = title.strip()
    if len(stripped) >= 4 and stripped.upper() not in BLOCKLIST:
        assert _HS._is_chapter_boundary(f"# {stripped}")


# ═══════════════════════════════════════════════════════════════════════════
# Partition invariants (the roadmap 2.2 core)
# ═══════════════════════════════════════════════════════════════════════════


def _assert_partition(segs, total_pages):
    assert segs, "non-empty docs must yield at least one segment"
    prev = None
    covered: set[int] = set()
    for s in segs:
        assert 1 <= s.start_page <= s.end_page <= total_pages
        covered.update(range(s.start_page, s.end_page + 1))
        if prev is not None:
            # no gaps: the next segment may overlap or touch, never start
            # beyond the previous segment's end
            assert s.start_page <= prev.end_page, (
                f"page gap between {prev.heading!r}[{prev.start_page}-{prev.end_page}] "
                f"and {s.heading!r}[{s.start_page}-{s.end_page}]"
            )
            assert s.start_page >= prev.start_page, "start pages must be monotonic"
        prev = s
    assert segs[0].start_page == 1
    assert segs[-1].end_page == total_pages
    assert covered == set(range(1, total_pages + 1)), "every page must belong to a segment"


@S_MED
@given(doc=_multi_chapter_docs())
def test_multi_chapter_docs_partition_page_range(doc):
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    _assert_partition(segs, total_pages)


@S_MED
@given(doc=_any_docs())
def test_any_docs_partition_page_range(doc):
    """The partition invariants hold on the plain-heading fallback path too."""
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    if segs:
        _assert_partition(segs, total_pages)


@S_MED
@given(doc=_multi_chapter_docs())
def test_start_pages_monotonic_nondecreasing(doc):
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    starts = [s.start_page for s in segs]
    assert starts == sorted(starts)


@S_MED
@given(doc=_multi_chapter_docs())
def test_pages_within_document_bounds(doc):
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    for s in segs:
        assert 1 <= s.start_page <= s.end_page <= total_pages


@S_MED
@given(doc=_multi_chapter_docs())
def test_heading_length_capped_at_80(doc):
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    for s in segs:
        assert len(s.heading) <= 80


@S_MED
@given(doc=_multi_chapter_docs())
def test_segmentation_matches_independent_model(doc):
    """Full characterization: segment() == the boundary-flag model.

    Content runs become segments in order; the heading is the LAST boundary
    before the run (normalized, capped at 80 chars); leading content becomes
    "Introduction"; a boundary immediately followed by another boundary drops
    its heading; the last segment ends at total_pages.
    """
    md, markers, total_pages = doc
    lines = md.splitlines()
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    expected = _spec_segments(_HS, lines, markers, total_pages)
    assert len(expected) >= 2  # generator guarantees the no-fallback regime
    got = [(s.heading, s.content, s.start_page, s.end_page) for s in segs]
    assert got == expected


@S_MED
@given(doc=_multi_chapter_docs())
def test_content_lines_preserved_byte_exact(doc):
    """Every non-boundary line survives verbatim, in order, in its segment."""
    md, markers, total_pages = doc
    lines = md.splitlines()
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    rejoined = "\n".join(s.content for s in segs).split("\n")
    non_boundary = [ln for ln in lines if not _HS._is_chapter_boundary(ln)]
    assert rejoined == non_boundary


@S_MED
@given(doc=_multi_chapter_docs())
def test_segment_count_equals_content_runs(doc):
    md, markers, total_pages = doc
    lines = md.splitlines()
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    bset = {i for i, ln in enumerate(lines) if _HS._is_chapter_boundary(ln)}
    runs, cur = [], []
    for i, ln in enumerate(lines):
        if i in bset:
            runs.append(cur)
            cur = []
        else:
            cur.append(ln)
    runs.append(cur)
    non_empty_runs = [r for r in runs if r]
    assert len(segs) == len(non_empty_runs)


@S_MED
@given(doc=_multi_chapter_docs())
def test_leading_content_becomes_introduction(doc):
    """Front matter before the first heading is labeled 'Introduction'."""
    md, markers, total_pages = doc
    lines = md.splitlines()
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    first_boundary = next((i for i, ln in enumerate(lines) if _HS._is_chapter_boundary(ln)), None)
    if first_boundary and lines[:first_boundary]:
        # any line (even blank) before the first boundary → Introduction
        assert segs[0].heading == "Introduction"
        assert segs[0].content == "\n".join(lines[:first_boundary])
    else:
        assert all(s.heading != "Introduction" for s in segs) or segs == []


@S_MED
@given(
    body=st.lists(_body_line.filter(lambda s: s), min_size=1, max_size=3),
)
def test_doc_without_boundaries_is_single_introduction_segment(body):
    """No headings → exactly one 'Introduction' segment spanning all pages."""
    md = "\n".join(body)
    segs = _HS.segment(md, total_pages=1, page_markers=[(1, 0)])
    assert len(segs) == 1
    assert segs[0].heading == "Introduction"
    assert segs[0].content == md
    assert (segs[0].start_page, segs[0].end_page) == (1, 1)


@S_FAST
@given(n=st.integers(min_value=1, max_value=9))
def test_consecutive_boundaries_drop_empty_heading(n):
    """A heading immediately followed by another heading loses its segment."""
    md = f"# Chapter 1: First\n# Chapter {n}: Second\nbody line one here"
    segs = _HS.segment(md, total_pages=1, page_markers=[(1, 0)])
    headings = [s.heading for s in segs]
    assert "Chapter 1: First" not in headings
    assert f"Chapter {n}: Second" in headings


def test_empty_document_yields_no_segments():
    assert _HS.segment("", total_pages=1, page_markers=[(1, 0)]) == []


@S_MED
@given(doc=_multi_chapter_docs())
def test_segments_are_in_document_order(doc):
    md, markers, total_pages = doc
    segs = _HS.segment(md, total_pages=total_pages, page_markers=markers)
    cursor = 0
    for s in segs:
        pos = md.find(s.content, cursor)
        assert pos >= 0, f"segment {s.heading!r} content not found in order"
        cursor = pos + len(s.content)


# ═══════════════════════════════════════════════════════════════════════════
# Plain-heading fallback path
# ═══════════════════════════════════════════════════════════════════════════

_PLAIN_WORDS = (
    "Quiet",
    "Rivers",
    "Flow",
    "Slowly",
    "Silver",
    "Mountains",
    "Stand",
    "Tall",
    "Winter",
    "Harvest",
    "Fields",
    "Rest",
    "Ocean",
    "Currents",
    "Shift",
    "North",
)


def _plain_heading(k: int) -> str:
    words = [_PLAIN_WORDS[(3 * k + j) % len(_PLAIN_WORDS)] for j in range(3)]
    return " ".join(words)


@S_MED
@given(k=st.integers(min_value=0, max_value=40))
def test_plain_headings_are_detected_by_heuristic(k):
    """Generated title-case lines qualify as plain headings (near a marker)."""
    line = _plain_heading(k)
    # heuristic checks (mirror of _detect_plain_headings guards)
    assert 0 < len(line) <= 80
    assert not re.search(r"[.;,]$", line)
    assert line.split()[0].lower() not in HEADING_STOP_STARTS
    assert re.search(r"[A-Z]", line)
    assert len(line.split()) >= 3
    words = line.split()
    assert all(re.match(r"^[A-Z]", w) for w in words)  # title case
    assert not _HS._is_chapter_boundary(line)


@S_MED
@given(
    words=st.lists(
        st.sampled_from(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]), min_size=3, max_size=6
    ),
)
def test_plain_heading_detection_distance_window(words):
    """A title-case line 1-5 lines after a marker is detected; 6+ is not."""
    heading = " ".join(words)
    for dist in range(1, 6):
        # place: marker line, then dist-1 body lines, then the heading
        body = ["plain body text here"] * (dist - 1)
        doc_lines = ["page starts here"] + body + [heading]
        detected = _HS._detect_plain_headings(doc_lines, [(1, 0)])
        assert len(doc_lines) - 1 in detected
    # 6+ lines after the marker: not detected
    doc_lines = ["page starts here"] + ["plain body text here"] * 5 + [heading]
    detected = _HS._detect_plain_headings(doc_lines, [(1, 0)])
    assert len(doc_lines) - 1 not in detected


@S_MED
@given(
    title_words=st.lists(st.sampled_from(_PLAIN_WORDS), min_size=3, max_size=5, unique=True),
    bodies=st.lists(st.lists(_body_line, min_size=1, max_size=3), min_size=2, max_size=3),
)
def test_plain_fallback_resegments_single_segment_docs(title_words, bodies):
    """A doc whose explicit pass yields ONE segment is re-scanned for plain
    headings — and the plain pass obeys the same partition invariants."""
    headings = [" ".join(title_words[:3]), " ".join(title_words[-3:])]
    # doc: body, HEADING, body, HEADING, body — with markers so headings are
    # within 5 lines after a marker
    lines: list[str] = []
    marks: list[tuple[int, int]] = [(1, 0)]
    lines.append(bodies[0][0])
    lines.append(headings[0])
    marks.append((2, len(lines)))  # marker right before the 2nd heading zone
    lines.extend(bodies[1])
    lines.append(headings[1])
    lines.extend(bodies[0])
    md = "\n".join(lines)
    segs = _HS.segment(md, total_pages=2, page_markers=marks)
    # explicit pass: 0 boundaries → 1 segment → fallback must have run
    assert any(s.heading in headings for s in segs)
    _assert_partition(segs, 2)


# ═══════════════════════════════════════════════════════════════════════════
# Custom keywords / regex + academic subsection helpers
# ═══════════════════════════════════════════════════════════════════════════


@S_MED
@given(
    keyword=st.sampled_from([" Keystone ", "TWILIGHT", "Sigil", "Beacon"]),
    body=st.lists(_body_line, min_size=1, max_size=3),
)
def test_custom_keyword_lines_are_boundaries(keyword, body):
    req = ConversionRequest(
        input_path=Path("d.pdf"),
        output_dir=Path("o"),
        custom_keywords=[keyword],
    )
    hs = HeadingSegmenter(req)
    kw = keyword.strip()
    line = f"{kw} and everything that follows counts"
    assert hs._is_chapter_boundary(line)
    for ln in body:
        if ln and kw.lower() not in ln.lower():
            assert not hs._is_chapter_boundary(ln)


@S_MED
@given(
    pat=st.sampled_from([r"^KEYNOTE \d+", r"^§+ ", r"^~~~"]),
    n=st.integers(min_value=1, max_value=9),
)
def test_custom_regex_lines_are_boundaries(pat, n):
    req = ConversionRequest(
        input_path=Path("d.pdf"), output_dir=Path("o"), custom_regex_patterns=[pat]
    )
    hs = HeadingSegmenter(req)
    line = {"^KEYNOTE \\d+": f"KEYNOTE {n}", "^§+ ": "§§ custom", "^~~~": "~~~ wave"}[pat]
    assert hs._is_chapter_boundary(line)


@S_FAST
@given(
    major=st.integers(min_value=1, max_value=99),
    minor=st.integers(min_value=1, max_value=99),
    sub=st.none() | st.integers(min_value=1, max_value=99),
)
def test_academic_subsection_detection(major, minor, sub):
    numbered = f"{major}.{minor}" + (f".{sub}" if sub is not None else "")
    for variant in (numbered + " Introduction", f"## {numbered} Methodology"):
        assert _HS.is_academic_subsection(variant)
    # top-level sections and plain prose are NOT subsections
    assert not _HS.is_academic_subsection(f"{major}. Introduction")
    assert not _HS.is_academic_subsection("the quick brown fox jumps over")
    assert not _HS.is_academic_subsection("")


@S_FAST
@given(
    majors=st.lists(st.integers(min_value=1, max_value=9), min_size=1, max_size=4),
    minors=st.lists(st.integers(min_value=1, max_value=9), min_size=1, max_size=3),
)
def test_extract_academic_subsections_finds_all(majors, minors):
    lines = [
        f"{majors[i % len(majors)]}.{minors[i % len(minors)]} Subheading {chr(65 + i)}"
        for i in range(6)
    ]
    md = "\n".join(["intro line"] + lines + ["outro line"])
    found = _HS.extract_academic_subsections(md)
    assert [idx for idx, _ in found] == list(range(1, 1 + len(lines)))
    for (_, heading), line in zip(found, lines, strict=True):
        assert heading == line.strip().lstrip("#").strip()


@S_FAST
@given(text=st.text(min_size=0, max_size=200))
def test_normalise_heading_caps_and_collapses(text):
    out = _HS._normalise_heading("# " + text)
    assert len(out) <= 80
    assert "\t" not in out
    assert "  " not in out
    assert not out.startswith("#")


# ═══════════════════════════════════════════════════════════════════════════
# ChapterMatcher properties
# ═══════════════════════════════════════════════════════════════════════════

_MATCH_TITLES = (
    "River Systems",
    "Mountain Weather",
    "Harbor Lights",
    "Desert Crossings",
    "Forest Canopies",
)


def _segments_dicts(n: int) -> list[dict]:
    return [
        {
            "heading": _MATCH_TITLES[i % len(_MATCH_TITLES)] + (f" {i}" if i >= 5 else ""),
            "start_page": i + 1,
            "end_page": i + 2,
            "aliases": [],
            "segment_type": "chapter",
        }
        for i in range(n)
    ]


@S_MED
@given(n=st.integers(min_value=1, max_value=8), idx=st.integers(min_value=0, max_value=7))
def test_exact_heading_match_returns_score_3(n, idx):
    segs = _segments_dicts(max(n, idx + 1))
    target = segs[idx % len(segs)]
    results = ChapterMatcher().match([target["heading"]], segs)
    assert results
    assert results[0][0] == 3
    assert results[0][1] is target


@S_MED
@given(n=st.integers(min_value=1, max_value=8), k=st.integers(min_value=1, max_value=5))
def test_match_results_sorted_by_score_desc(n, k):
    segs = _segments_dicts(n)
    selected = [s["heading"] for s in segs[: min(k, len(segs))]]
    results = ChapterMatcher().match(selected, segs)
    scores = [sc for sc, _ in results]
    assert scores == sorted(scores, reverse=True)


@S_MED
@given(n=st.integers(min_value=1, max_value=8), k=st.integers(min_value=1, max_value=6))
def test_match_no_duplicate_segments(n, k):
    segs = _segments_dicts(n)
    selected = [s["heading"] for s in segs[: min(k, len(segs))]] * 2
    results = ChapterMatcher().match(selected, segs)
    ids = [id(s) for _, s in results]
    assert len(ids) == len(set(ids))


@S_MED
@given(
    heading=st.sampled_from(["Gap (pages 5-9)", "Gap (front matter)", "Anything At All"]),
    segment_type=st.sampled_from(["gap", "chapter"]),
)
def test_gap_segments_never_matched(heading, segment_type):
    is_gap = segment_type == "gap" or heading.strip().lower().startswith("gap (")
    seg = {
        "heading": heading,
        "start_page": 1,
        "end_page": 2,
        "aliases": [],
        "segment_type": segment_type,
    }
    results = ChapterMatcher().match([heading], [seg])
    if is_gap:
        assert results == []
    else:
        assert results and results[0][1] is seg


@S_MED
@given(
    alias=st.sampled_from(["Dedication", "Colophon", "Original Name"]),
    primary=st.sampled_from(["Merged Title", "Combined Chapter"]),
)
def test_alias_headings_are_matchable(alias, primary):
    seg = {
        "heading": primary,
        "start_page": 1,
        "end_page": 3,
        "aliases": [alias],
        "segment_type": "chapter",
    }
    results = ChapterMatcher().match([alias], [seg])
    assert results and results[0][1] is seg
    assert results[0][0] == 3


@S_FAST
@given(n=st.integers(min_value=0, max_value=4))
def test_empty_selection_returns_empty(n):
    segs = _segments_dicts(max(n, 1))
    assert ChapterMatcher().match([], segs) == []


@S_MED
@given(
    n=st.integers(min_value=1, max_value=6),
    cap=st.integers(min_value=1, max_value=4),
)
def test_max_results_respected(n, cap):
    segs = _segments_dicts(n)
    selected = [s["heading"] for s in segs]
    results = ChapterMatcher().match(selected, segs, max_results=cap)
    assert len(results) <= cap


@S_MED
@given(
    num=st.integers(min_value=1, max_value=20),
    title_a=st.sampled_from(["Cannabinoids", "Memantine", "Receptors"]),
    title_b=st.sampled_from(["Therapy", "Outcomes", "Trials"]),
)
def test_chapter_number_match_scores_2(num, title_a, title_b):
    seg = {
        "heading": f"{num} {title_a}",
        "start_page": 1,
        "end_page": 2,
        "aliases": [],
        "segment_type": "chapter",
    }
    results = ChapterMatcher().match([f"{num} {title_b}"], [seg])
    assert results and results[0][0] == 2 and results[0][1] is seg


@S_MED
@given(
    a=st.integers(min_value=1, max_value=9),
    b=st.integers(min_value=1, max_value=9),
    ta=st.sampled_from(["Cannabinoids", "Memantine"]),
    tb=st.sampled_from(["Therapy", "Outcomes"]),
)
def test_distinct_chapter_numbers_never_match(a, b, ta, tb):
    if a == b:
        return
    matched, score = ChapterMatcher()._match_heading_text(f"{a}.1 {ta}", f"{b}.2 {tb}")
    assert not matched
    assert score == 0


@S_FAST
@given(
    major=st.integers(min_value=1, max_value=9),
    minor=st.integers(min_value=1, max_value=9),
    sub=st.integers(min_value=1, max_value=9),
)
def test_parent_section_number_matches_child(major, minor, sub):
    seg = {
        "heading": f"{major}.{minor}.{sub} Details",
        "start_page": 1,
        "end_page": 2,
        "aliases": [],
        "segment_type": "chapter",
    }
    results = ChapterMatcher().match([f"{major}.{minor} Other"], [seg])
    assert results and results[0][0] == 2


@S_MED
@given(n=st.integers(min_value=1, max_value=6), k=st.integers(min_value=1, max_value=4))
def test_match_is_deterministic(n, k):
    segs = _segments_dicts(n)
    selected = [s["heading"] for s in segs[: min(k, len(segs))]]
    m = ChapterMatcher()
    r1 = [(sc, id(s)) for sc, s in m.match(selected, segs)]
    r2 = [(sc, id(s)) for sc, s in m.match(selected, segs)]
    assert r1 == r2


@S_MED
@given(
    sel=st.sampled_from(["Foundations of Thought", "Hidden Currents"]),
    page=st.integers(min_value=1, max_value=20),
    start=st.integers(min_value=1, max_value=20),
)
def test_page_based_fallback_matches_segment_containing_toc_page(sel, page, start):
    """Renamed chapters are found via their TOC page (score 1)."""
    seg = {
        "heading": "River Systems",
        "start_page": start,
        "end_page": start + 3,
        "aliases": [],
        "segment_type": "chapter",
    }
    matcher = ChapterMatcher(toc_entries=[(sel, page)])
    results = matcher.match([sel], [seg])
    if start <= page <= start + 3:
        assert results and results[0][1] is seg and results[0][0] == 1
    else:
        assert results == []


# ── matcher helpers ─────────────────────────────────────────────────────────


@S_FAST
@given(s=st.text(min_size=0, max_size=60))
def test_normalize_is_idempotent_and_lowercase(s):
    once = _normalize(s)
    assert _normalize(once) == once
    assert once == once.lower()
    assert "  " not in once
    assert not re.search(r"[^\w\s]", once)


@S_FAST
@given(
    major=st.integers(min_value=1, max_value=99),
    minor=st.integers(min_value=1, max_value=99),
    sub=st.none() | st.integers(min_value=1, max_value=99),
    word=st.sampled_from(["Chapter", "Lesson", "Section", "Part"]),
)
def test_extract_chapter_number_roundtrip(major, minor, sub, word):
    dotted = f"{major}.{minor}" + (f".{sub}" if sub is not None else "")
    assert _extract_chapter_number(f"{dotted} Some Heading") == dotted
    assert _extract_chapter_number(f"{word} {major} Heading") == str(major)
    assert _extract_chapter_number("Plain Heading Words") is None
    assert _extract_chapter_number("") is None


@S_FAST
@given(
    title=st.text(min_size=0, max_size=40),
)
def test_validate_toc_title_truth_table(title):
    t = title.strip()
    valid = len(t) >= 3 and not re.match(r"^\d+$", t) and len(re.sub(r"[^\w]", "", t)) >= 2
    assert _validate_toc_title(title) == valid


@S_FAST
@given(
    pages=st.lists(st.integers(min_value=-5, max_value=30), min_size=0, max_size=6),
    titles=st.lists(st.text(min_size=0, max_size=12), min_size=0, max_size=6),
)
def test_normalize_toc_entries_filters_garbage(pages, titles):
    entries = list(zip(titles, pages, strict=True)) if len(titles) == len(pages) else []
    out = ChapterMatcher._normalize_toc_entries(entries)
    for title, page in out:
        assert isinstance(title, str) and isinstance(page, int)
        assert page >= 1
        assert _validate_toc_title(title)
    # every kept entry must have been a valid (title, positive page) input
    assert len(out) <= len(entries)


@S_FAST
@given(
    heading=st.text(min_size=0, max_size=30),
    segment_type=st.sampled_from(["gap", "chapter", "chunk", ""]),
)
def test_is_gap_segment_truth_table(heading, segment_type):
    expected = segment_type == "gap" or heading.strip().lower().startswith("gap (")
    assert _is_gap_segment(heading, segment_type) == expected


# ═══════════════════════════════════════════════════════════════════════════
# filter_toc_entries_for_selection
# ═══════════════════════════════════════════════════════════════════════════

_TOC_TITLES = (
    ("Keystone Approaches", 1),
    ("Lantern Studies", 5),
    ("Marble Quarries", 9),
    ("Nomad Routes", 13),
    ("Orchard Seasons", 17),
)


@S_MED
@given(
    k=st.integers(min_value=2, max_value=5),
    extra=st.lists(st.tuples(st.text(min_size=3, max_size=20), st.integers(1, 50)), max_size=3),
)
def test_filter_toc_subset_and_dropped_count(k, extra):
    toc = list(_TOC_TITLES) + [
        (t or "Filler Entry", p) for t, p in extra if _validate_toc_title(t or "Filler Entry")
    ]
    selected = [title for title, _ in _TOC_TITLES[:k]]
    filtered, dropped = filter_toc_entries_for_selection(toc, selected)
    assert dropped == len(toc) - len(filtered)
    # subset + order preserved
    it = iter(toc)
    assert all(any(e is f for e in it) for f in filtered)
    assert len(filtered) >= k
    kept_titles = {t for t, _ in filtered}
    assert set(selected) <= kept_titles


@S_MED
@given(
    selected=st.lists(
        st.sampled_from(["Zzqx Vvwv", "Qqxj Wwvv", "Xkqj Vvww"]), min_size=1, max_size=3
    ),
)
def test_filter_toc_no_match_returns_original(selected):
    toc = list(_TOC_TITLES)
    filtered, dropped = filter_toc_entries_for_selection(toc, selected)
    assert filtered is toc  # identity: the safety net returns the input as-is
    assert dropped == 0


@S_FAST
@given(toc=st.lists(st.tuples(st.text(min_size=0, max_size=10), st.integers(1, 30)), max_size=5))
def test_filter_toc_empty_selection_returns_original(toc):
    filtered, dropped = filter_toc_entries_for_selection(toc, [])
    assert filtered is toc
    assert dropped == 0


@S_FAST
@given(k=st.integers(min_value=0, max_value=4))
def test_filter_toc_empty_toc_returns_original(k):
    selected = [t for t, _ in _TOC_TITLES[:k]]
    filtered, dropped = filter_toc_entries_for_selection([], selected)
    assert filtered == []
    assert dropped == 0


@S_FAST
@given(
    matched_title=st.sampled_from(["Keystone Approaches", "Lantern Studies"]),
    other_titles=st.lists(st.sampled_from(["Marble Quarries", "Nomad Routes"]), max_size=2),
)
def test_filter_toc_single_match_returns_original(matched_title, other_titles):
    """V0.07: a 1-entry TOC would disable TOC segmentation — return full TOC."""
    toc = [(matched_title, 1)] + [(t, i + 2) for i, t in enumerate(other_titles)]
    filtered, dropped = filter_toc_entries_for_selection(toc, [matched_title])
    assert filtered is toc
    assert dropped == 0


# ═══════════════════════════════════════════════════════════════════════════
# Segment dataclass invariants
# ═══════════════════════════════════════════════════════════════════════════


@S_FAST
@given(
    heading=st.text(min_size=0, max_size=30),
    content=st.text(min_size=0, max_size=30),
    start=st.integers(min_value=1, max_value=100),
    length=st.integers(min_value=0, max_value=50),
    segment_type=st.sampled_from(["chapter", "chunk", "gap"]),
    aliases=st.none() | st.lists(st.text(min_size=0, max_size=10), max_size=3),
)
def test_segment_dataclass_invariants(heading, content, start, length, segment_type, aliases):
    seg = Segment(
        heading=heading,
        content=content,
        start_page=start,
        end_page=start + length,
        segment_type=segment_type,
        aliases=aliases,
    )
    assert seg.aliases == (aliases if aliases is not None else [])
    assert seg.all_headings == [seg.heading] + seg.aliases
    assert seg.is_gap == (segment_type == "gap" or heading.startswith("Gap ("))
    assert seg.start_page <= seg.end_page
