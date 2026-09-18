"""V18.20.4.11 (P1) — find_analysis_for_heading uses its heading parameter.

Fixes the wrong-chapter analysis injection (sweep 2-a flag / roadmap #1):
V17.5's ``find_analysis_for_heading`` IGNORED ``heading`` and returned the
FIRST readable ``*_analysis.md`` tree-wide. Since the V18.20.4.10 P0 fix
made multi-segment books the norm, EVERY chapter received segment-001's
analysis (wrong-chapter authors/keywords in prompts, coverage probes,
gap-fill, recall floor, thorough-theorist floor).

Covered here:

  - **slug helper pin** — ``core.common.heading_utils.segment_filename_slug``
    is byte-identical to the former inline output_save transformation
    (reference regexes re-implemented in this file, house pattern from
    tests/test_parser_utils.py) on tricky inputs: tabs/newlines, double
    spaces, unicode dashes, the 60-char cap, empty-after-strip.
  - **output_save integration pin** — output_save.py now CALLS the shared
    helper and no longer carries the duplicated inline regexes; the two
    former computation sites are gone.
  - **multi-file exact slug match** — segment+analysis pairs named the way
    output_save names them (``{idx:03d}_{slug}.md`` + ``_analysis.md``
    twin) for three headings incl. special chars and a >60-char heading:
    each heading finds ITS analysis.
  - **fuzzy fallback** — case/whitespace-drifted heading still finds its
    file (difflib ratio ≥ 0.75) with an INFO match log.
  - **single-file legacy** — one analysis file is returned for ANY heading
    (V17.5 single-segment contract), no WARNING.
  - **fail-closed** — multiple files, unmatchable heading → ("", "") + a
    LOUD WARNING via log_fn (previously: the first file = wrong-chapter
    content was injected).
  - **duplicate headings** — two files share a slug → first returned
    (deterministic) + AMBIGUOUS WARNING.

Run: pytest tests/test_v1820411_p1_analysis_heading.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.common.heading_utils import segment_filename_slug
from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

_OS = _project_root / "core" / "pipeline" / "conversion" / "output_save.py"
_DA = _project_root / "core" / "preprocessing" / "deterministic_analyzer.py"


def _legacy_output_save_slug(heading: str) -> str:
    """The FORMER inline transformation from output_save.py:198-200 (V18.20.4.9),
    re-implemented verbatim as the reference for the equivalence pin."""
    _h = re.sub(r"[\t\r\n]+", " ", heading)
    _h = re.sub(r" {2,}", " ", _h).strip()
    return re.sub(r"[^\w\s\-]", "", _h).strip()[:60]


def _write_segment_pair(folder: Path, idx: int, heading: str, marker: str) -> Path:
    """Write a segment + analysis pair EXACTLY the way output_save does
    (slug via the shared helper, ``{idx:03d}_{slug}.md`` naming, analysis
    twin ``{idx:03d}_{slug}_analysis.md`` in the same folder)."""
    safe = segment_filename_slug(heading) or f"segment_{idx:03d}"
    seg_file = folder / f"{idx:03d}_{safe}.md"
    seg_file.write_text(f"# {heading}\n\nbody", encoding="utf-8")
    analysis_file = folder / f"{idx:03d}_{safe}_analysis.md"
    analysis_file.write_text(
        f"## Citations\n\n1. **{marker}** (1 mentions): 1900\n", encoding="utf-8"
    )
    return analysis_file


class _Log:
    """log_fn collector: list of (message, level)."""

    def __init__(self):
        self.records: list[tuple[str, str]] = []

    def __call__(self, msg: str, level: str = "DEBUG") -> None:
        self.records.append((msg, level))

    def warnings(self) -> list[str]:
        return [m for m, lvl in self.records if lvl == "WARNING"]

    def infos(self) -> list[str]:
        return [m for m, lvl in self.records if lvl == "INFO"]


@pytest.fixture(autouse=True)
def _clear_analysis_scan_cache():
    """Hermeticity: the O-a6 scan cache is module-level and keyed by resolved
    dir — clear it around every test (house pattern, test_v182048)."""
    import core.preprocessing.deterministic_analyzer as da

    da._ANALYSIS_SCAN_CACHE.clear()
    yield
    da._ANALYSIS_SCAN_CACHE.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Slug helper pin — byte-identical to the former output_save transformation
# ═══════════════════════════════════════════════════════════════════════════

class TestSegmentFilenameSlug:
    @pytest.mark.parametrize(
        "heading",
        [
            "Chapter One: Beginnings",
            'Chapter 5: "Quotes" & Symbols/Slash',
            "Tab\tinside\tand\ncollapsed newlines",
            "Double  spaces   collapsed",
            "Em — dash and – en dash",
            "???",                                     # empty after strip
            "",                                       # empty heading
            "A" * 200,                                # >60-char cap
            "Unicode ünïcödé heading ✓ works",
            "Mixed 123 numbers & (parens) [brackets]",
            " word boundaries kept ",
            "under_scores are \\w and stay",
        ],
    )
    def test_matches_legacy_output_save_transformation(self, heading):
        assert segment_filename_slug(heading) == _legacy_output_save_slug(heading)

    def test_sixty_char_cap(self):
        h = "A" * 100
        assert len(segment_filename_slug(h)) == 60
        assert segment_filename_slug(h) == "A" * 60

    def test_empty_after_strip(self):
        assert segment_filename_slug("?!.,;:") == ""
        assert segment_filename_slug(None) == ""   # defensive: None heading

    def test_special_chars_removed_after_space_collapse(self):
        # order matters: spaces collapse BEFORE special-char removal, so
        # " & " leaves a DOUBLE space behind (pinned — must stay in lockstep
        # with the filenames output_save writes).
        assert segment_filename_slug("A & B") == "A  B"

    def test_unicode_dash_removed(self):
        # the class keeps only ASCII '-' (escaped in the regex), not —/–
        assert segment_filename_slug("A — B") == "A  B"
        assert segment_filename_slug("A - B") == "A - B"


# ═══════════════════════════════════════════════════════════════════════════
# output_save integration pin — the helper replaced the duplicated inline
# regexes without changing naming (source-level, house _strip_comments pin)
# ═══════════════════════════════════════════════════════════════════════════

class TestOutputSaveIntegrationPin:
    def _strip_comments(self, text: str) -> str:
        out = []
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
        return "\n".join(out)

    def test_output_save_uses_shared_helper(self):
        src = self._strip_comments(_OS.read_text(encoding="utf-8"))
        # the shared helper is imported and used at BOTH former sites
        assert "from core.common.heading_utils import segment_filename_slug" in src
        assert src.count("safe = segment_filename_slug(seg.heading) or f\"segment_{idx:03d}\"") == 2
        # the former duplicated inline computation is gone
        assert 're.sub(r"[^\\w\\s\\-]", "", _h)' not in src
        assert "_h = re.sub(r\"[\\t\\r\\n]+\", \" \", seg.heading)" not in src

    def test_deterministic_analyzer_uses_shared_helper(self):
        src = self._strip_comments(_DA.read_text(encoding="utf-8"))
        assert "from core.common.heading_utils import segment_filename_slug" in src
        assert "segment_filename_slug(heading" in src

    def test_naming_unchanged_on_varied_headings(self):
        """The helper's output equals the old inline output on 10 varied
        headings — importing it into output_save cannot have changed naming
        (the two computations are byte-identical by construction)."""
        varied = [
            "Chapter 1",
            "Chapter One: Beginnings",
            'Chapter 5: "Quotes" & Symbols/Slash',
            "Part II — The Middle Years",
            "Appendix A: Data Tables (2023)",
            "97 Things Every Programmer Should Know About Psychology",
            "فصل اول",                       # non-Latin script (\w keeps it)
            "Conclusion",
            "Tab\tand\nnewline heading",
            "!!! ???",
        ]
        for h in varied:
            assert segment_filename_slug(h) == _legacy_output_save_slug(h)


# ═══════════════════════════════════════════════════════════════════════════
# Multi-file exact slug match — each heading finds ITS analysis
# ═══════════════════════════════════════════════════════════════════════════

_HEADINGS_AND_MARKERS = [
    ("Chapter One: Beginnings", "AlphaAuthor"),
    ('Chapter 5: "Quotes" & Symbols/Slash', "BetaAuthor"),
    ("This Heading Is Deliberately Much Longer Than Sixty Characters To Force Truncation", "GammaAuthor"),
]


class TestMultiFileExactSlugMatch:
    @pytest.fixture()
    def multi_tree(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        for i, (h, marker) in enumerate(_HEADINGS_AND_MARKERS, 1):
            _write_segment_pair(seg, i, h, marker)
        return tmp_path

    @pytest.mark.parametrize("heading,marker", _HEADINGS_AND_MARKERS)
    def test_each_heading_finds_its_own_analysis(self, multi_tree, heading, marker):
        log = _Log()
        seg_path, analysis = find_analysis_for_heading(multi_tree, heading, log_fn=log)
        assert analysis, f"heading {heading!r} found no analysis"
        assert marker in analysis, (
            f"heading {heading!r} got the WRONG analysis (expected {marker})"
        )
        # the segment path is the slug-named twin, and the match is logged
        assert seg_path.endswith(".md") and "segments" in seg_path
        assert any("exact slug" in m for m in log.infos()), log.infos()

    def test_wrong_analysis_no_longer_injected(self, multi_tree):
        """The V17.5 bug: every heading got segment-001's analysis. Now the
        FIRST heading's marker must NOT appear in chapter 3's analysis."""
        h3, _marker3 = _HEADINGS_AND_MARKERS[2]
        _, analysis3 = find_analysis_for_heading(multi_tree, h3)
        assert "AlphaAuthor" not in analysis3
        assert "GammaAuthor" in analysis3

    def test_truncated_long_heading_still_matches(self, multi_tree):
        """A >60-char heading is truncated in the filename on BOTH sides
        (write + lookup) — must still resolve to its own analysis."""
        long_h = _HEADINGS_AND_MARKERS[2][0]
        slug = segment_filename_slug(long_h)
        assert len(slug) == 60
        _, analysis = find_analysis_for_heading(multi_tree, long_h)
        assert "GammaAuthor" in analysis


# ═══════════════════════════════════════════════════════════════════════════
# Fuzzy fallback — case/whitespace drift
# ═══════════════════════════════════════════════════════════════════════════

class TestFuzzyFallback:
    def test_case_drifted_heading_matches_via_fuzzy(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Chapter One: Beginnings", "AlphaAuthor")
        _write_segment_pair(seg, 2, "Different Chapter Entirely", "BetaAuthor")
        log = _Log()
        # different case + collapsed/extra whitespace → no exact slug hit,
        # but the fuzzy rung (ratio ≥ 0.75) must find chapter one's file.
        _, analysis = find_analysis_for_heading(
            tmp_path, "chapter one:  beginnings", log_fn=log
        )
        assert "AlphaAuthor" in analysis
        assert any("fuzzy" in m for m in log.infos()), log.infos()


# ═══════════════════════════════════════════════════════════════════════════
# Single-file legacy behavior (V17.5 contract — pinned by test_v182048 too)
# ═══════════════════════════════════════════════════════════════════════════

class TestSingleFileLegacy:
    def test_single_file_returned_for_any_heading_without_warning(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Chapter One", "AlphaAuthor")
        for heading in ("Chapter One", "anything else entirely", ""):
            log = _Log()
            seg_path, analysis = find_analysis_for_heading(tmp_path, heading, log_fn=log)
            assert "AlphaAuthor" in analysis, heading
            assert seg_path.endswith("001_Chapter One.md")
            assert not log.warnings(), log.warnings()

    def test_empty_dir_returns_empty_pair(self, tmp_path):
        log = _Log()
        assert find_analysis_for_heading(tmp_path, "Chapter One", log_fn=log) == ("", "")
        assert not log.warnings()


# ═══════════════════════════════════════════════════════════════════════════
# Fail-closed — unmatchable heading among multiple files
# ═══════════════════════════════════════════════════════════════════════════

class TestFailClosed:
    def test_unmatchable_heading_returns_empty_and_warns(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Alpha Chapter", "AlphaAuthor")
        _write_segment_pair(seg, 2, "Beta Chapter", "BetaAuthor")
        _write_segment_pair(seg, 3, "Gamma Chapter", "GammaAuthor")
        log = _Log()
        seg_path, analysis = find_analysis_for_heading(
            tmp_path, "ZZZ Unrelated Quantum Topic", log_fn=log
        )
        # fail-closed: NOTHING injected (previously segment-001's analysis)
        assert (seg_path, analysis) == ("", "")
        warnings = log.warnings()
        assert any("injecting NOTHING" in w for w in warnings), warnings
        assert any("ZZZ Unrelated Quantum Topic" in w for w in warnings)
        assert any("3 candidates found" in w for w in warnings)

    def test_empty_slug_heading_fails_closed_when_multiple_files(self, tmp_path):
        """A heading that collapses to "" can't exact-match anything; with
        multiple files the fuzzy rung can't rescue it either → fail-closed."""
        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Alpha Chapter", "AlphaAuthor")
        _write_segment_pair(seg, 2, "Beta Chapter", "BetaAuthor")
        log = _Log()
        seg_path, analysis = find_analysis_for_heading(tmp_path, "???", log_fn=log)
        assert (seg_path, analysis) == ("", "")
        assert any("injecting NOTHING" in w for w in log.warnings())


# ═══════════════════════════════════════════════════════════════════════════
# Duplicate chapter headings — ambiguous slug, first wins + WARNING
# ═══════════════════════════════════════════════════════════════════════════

class TestDuplicateHeadings:
    def test_duplicate_slug_returns_first_with_warning(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Conclusion", "FirstAuthor")
        _write_segment_pair(seg, 2, "Conclusion", "SecondAuthor")
        log = _Log()
        seg_path, analysis = find_analysis_for_heading(
            tmp_path, "Conclusion", log_fn=log
        )
        # deterministic: the FIRST file wins (no worse than the old
        # first-match), and the ambiguity is LOUD.
        assert "FirstAuthor" in analysis
        assert "SecondAuthor" not in analysis
        assert seg_path.endswith("001_Conclusion.md"), seg_path
        warnings = log.warnings()
        assert any("AMBIGUOUS" in w for w in warnings), warnings
        assert any("Conclusion" in w for w in warnings)
        # ambiguous matches still surface WHICH file was used (INFO)
        assert any("slug-ambiguous" in m or "AMBIGUOUS" in m for m in log.infos() + log.warnings())


# ═══════════════════════════════════════════════════════════════════════════
# Scan-cache contract (O-a6) is untouched by the heading-aware selection
# ═══════════════════════════════════════════════════════════════════════════

class TestCacheStillDrivesLookup:
    def test_source_pins_cache_still_used(self):
        src = _DA.read_text(encoding="utf-8")
        assert "_ANALYSIS_SCAN_CACHE" in src
        assert "def _list_analysis_files(output_dir: Path) -> list:" in src
        assert "analysis_files = _list_analysis_files(output_dir)" in src

    def test_repeated_calls_hit_cache_and_agree(self, tmp_path):
        import core.preprocessing.deterministic_analyzer as da

        seg = tmp_path / "segments"
        seg.mkdir()
        _write_segment_pair(seg, 1, "Alpha Chapter", "AlphaAuthor")
        _write_segment_pair(seg, 2, "Beta Chapter", "BetaAuthor")

        r1 = find_analysis_for_heading(tmp_path, "Beta Chapter")
        real_rglob = Path.rglob
        calls = {"n": 0}

        def counting_rglob(self, pattern):
            calls["n"] += 1
            return real_rglob(self, pattern)

        orig = Path.rglob
        Path.rglob = counting_rglob
        try:
            r2 = find_analysis_for_heading(tmp_path, "Beta Chapter")
        finally:
            Path.rglob = orig
        assert r1 == r2
        assert calls["n"] == 0, "repeat calls must not re-walk the tree (O-a6)"
