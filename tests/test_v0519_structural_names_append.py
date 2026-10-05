"""V0.5.19 — the structural-name filter + the append-mode correction type
+ the normalized (fuzzy) correction anchor.

Three fixes, one system (all content-agnostic — Rule 1: synthetic names):

1. **The structural-name filter** (``core.summarisation.author_anchor``):
   the LLM glossary sometimes lists structural labels in its ``names``
   section (the V0.5.18 ch.9 run carried a classification-manual code as
   a "name" — the verification flag then demanded coverage for a manual).
   Shape-based filter: all-caps acronym/code shapes + generic
   section-label words. Wired at every glossary-ingestion site.

2. **The append-mode correction type** (``verification_phase``): an
   omission correction may be ``{"append", "author", "reason"}`` with NO
   anchor. Safe since the V0.5.18 et-al fix made the missing-author flag
   honest. Deterministic guards: the author must be a STILL-MISSING
   roster author, the bullet must name them, one per author, shape caps,
   total ≤15%, individually clean; insertion = the end of the takeaways
   region.

3. **The normalized anchor** (``_locate_correction_anchor``): exact
   substring first, then a case/whitespace/emphasis/quote/dash-tolerant
   match mapped back to the original span — the ch.1 run lost 5 of 6
   corrections to near-miss anchors.

Run: pytest tests/test_v0519_structural_names_append.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.author_anchor import (  # noqa: E402
    filter_structural_names,
    is_structural_name,
)
from core.summarisation.verification_phase import (  # noqa: E402
    _extract_glossary_names,
    _find_append_insertion_offset,
    _locate_correction_anchor,
    _match_missing_author,
    verify_and_polish_summary,
)

# ── 1. the structural-name filter ───────────────────────────────────────────


class TestStructuralNameShapes:
    def test_all_caps_code_shapes_filtered(self):
        """Classification-manual code shapes (all-caps + roman/digit
        suffixes) are structural labels, not authors."""
        assert is_structural_name("ABX-II")
        assert is_structural_name("ABX-III-R")
        assert is_structural_name("ABX")
        assert is_structural_name("ABX-10")
        assert is_structural_name("III")  # a bare roman numeral

    def test_section_label_words_filtered(self):
        assert is_structural_name("Conclusions")
        assert is_structural_name("Summary")
        assert is_structural_name("Glossary")
        assert is_structural_name("Introduction")

    def test_real_author_shapes_kept(self):
        assert not is_structural_name("AuthorA")
        assert not is_structural_name("AuthorB and AuthorC")
        assert not is_structural_name("AuthorD et al.")
        assert not is_structural_name("van der AuthorE")
        assert not is_structural_name("AuthorF-AuthorG")

    def test_thin_shapes_fail_open(self):
        """Too-thin shapes (single letters) are KEPT — the conservative
        direction (a false positive removes a coverage demand)."""
        assert not is_structural_name("A")
        assert not is_structural_name("A-1")
        assert not is_structural_name("")

    def test_filter_preserves_order(self):
        out = filter_structural_names(["AuthorA", "ABX-II", "AuthorB et al.", "Summary", "AuthorC"])
        assert out == ["AuthorA", "AuthorB et al.", "AuthorC"]

    def test_glossary_names_extraction_filters_structural_entries(self):
        """The verification LAYER's ground-truth extractor drops the
        garbage-glossary entries (the wiring site)."""
        gloss = {
            "names": [
                {"name": "AuthorA", "year": "1975"},
                {"name": "ABX-II", "year": ""},
                {"name": "Conclusions", "year": ""},
                {"name": "AuthorB et al.", "year": "1968"},
            ]
        }
        names = _extract_glossary_names(gloss)
        assert names == ["AuthorA", "AuthorB et al."]

    def test_gap_fill_extractor_filters_structural_entries(self):
        """The gap-fill membership extractor mirrors the filter."""
        from core.summarisation.gap_fill_batch import _v056_extract_glossary_names

        gloss = {"names": ["AuthorA", "ABX-III-R", "Overview", "AuthorC"]}
        assert _v056_extract_glossary_names(gloss) == ["AuthorA", "AuthorC"]

    def test_cross_reference_filters_glossary_side(self):
        """The cross-reference buckets drop the structural entries from
        the glossary side (they never appear as llm_only noise)."""
        from core.summarisation.glossary_parser import cross_reference_glossary

        xref = cross_reference_glossary(["AuthorA", "ABX-II", "Conclusions"], ["AuthorA"])
        assert xref["confirmed"] == ["AuthorA"]
        assert xref["llm_only"] == []
        assert xref["regex_only"] == []


# ── 2. the normalized (fuzzy) correction anchor ─────────────────────────────


class TestNormalizedAnchor:
    def test_exact_substring_wins(self):
        span = _locate_correction_anchor("abc **Bold** def", "**Bold**")
        assert span == (4, 12)

    def test_case_insensitive_match(self):
        span = _locate_correction_anchor("AuthorA (1975) described it.", "authora (1975) described")
        assert span is not None
        assert span[1] - span[0] == len("AuthorA (1975) described")

    def test_emphasis_and_quote_tolerance(self):
        """The LLM drops markdown emphasis + uses straight quotes — the
        anchor still locates (the ch.1 5-of-6-skipped family)."""
        text = "- AuthorA (1975) described the \u201cinfantile\u201d organization."
        anchor = 'AuthorA (1975) described the "infantile" organization'
        span = _locate_correction_anchor(text, anchor)
        assert span is not None
        # the span covers the anchor's original text (emphasis/quotes kept
        # inside the span — the replacement swallows them)
        assert text[span[0] : span[1]] == (
            "AuthorA (1975) described the \u201cinfantile\u201d organization"
        )

    def test_whitespace_collapse_and_dash_unification(self):
        text = "A  study from 1968\u20131975 described it."
        span = _locate_correction_anchor(text, "a study from 1968-1975 described")
        assert span is not None

    def test_short_anchor_rejected_on_normalized_path(self):
        """An EXACT short substring still matches (the V0.4.40 contract);
        a short NEAR-miss is rejected (too ambiguous under normalization)."""
        assert _locate_correction_anchor("abcdefgh", "abc") == (0, 3)  # exact wins
        # "Abc" vs "abc" — exact fails, the normalized path needs ≥8 chars
        assert _locate_correction_anchor("abc def ghi", "Abc") is None

    def test_unlocatable_anchor_is_none(self):
        assert _locate_correction_anchor("one two three", "completely absent text") is None


# ── 3. the append-mode correction type ──────────────────────────────────────


class _MockVerifyProvider:
    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls: list[dict] = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt})
        return self._raw


class _MockSettings:
    def get(self, key, default=None):
        if key == "summarisation.model":
            return "test-model"
        if key == "summarisation.model_architecture":
            return "llamacpp"
        return default


_FILLER = (
    "The broad clinical picture was described in detail with many "
    "qualifications and elaborations across the whole chapter review. "
) * 30


def _mk_rendered() -> str:
    return (
        "# Summary: Test Chapter\n\n"
        "<!-- generated-by: Elixir v0.5.19 | started=2026-09-28T00:00:00 -->\n\n"
        "## Executive Summary\n\n"
        f"This chapter covers the organization. {_FILLER}\n\n"
        "## Key Takeaways\n\n"
        "- AuthorA (1975) described the organization in detail.\n"
        "- AuthorB and AuthorC (1968) studied the concept.\n\n"
        "## Thorough Summary\n\n"
        f"{_FILLER}\n\n"
        "---\n\n"
        "*Generated by Elixir v0.5.19 · run test · 2026-09-28T00:00:00 · 2 bullets*\n\n"
        "<!-- COMPLETE run_id=test -->\n"
    )


_SOURCE = (
    "AuthorA (1975) described the organization in detail across the chapter.\n"
    "AuthorB and AuthorC (1968) studied the concept and reported findings.\n"
    "AuthorD et al. (1974) reviewed the studies of the era and summarized them.\n"
    "The AuthorD et al. (1974) review covered thirteen samples.\n"
)


def _run_layer(monkeypatch, response_json: list[dict]):
    provider = _MockVerifyProvider(json.dumps(response_json))
    monkeypatch.setattr(
        "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
    )
    return verify_and_polish_summary(_mk_rendered(), _SOURCE, settings=_MockSettings())


class TestAppendMode:
    def test_valid_append_lands_for_missing_roster_author(self, monkeypatch):
        """An append naming a genuinely-missing roster author is inserted
        at the end of the takeaways region + audited as a fix."""
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "append": (
                        "AuthorD et al. (1974) reviewed the studies of the era, "
                        "covering thirteen samples in the spectrum."
                    ),
                    "author": "AuthorD et al.",
                    "reason": "omission",
                }
            ],
        )
        assert "AuthorD et al. (1974) reviewed the studies" in out
        fixes = [i for i in issues if i.detector == "verification_append" and i.severity == "fix"]
        assert len(fixes) == 1
        assert "AuthorD" in fixes[0].detail
        # inserted INSIDE the takeaways region (before Thorough Summary)
        tk = out.index("## Key Takeaways")
        th = out.index("## Thorough Summary")
        ad = out.index("- AuthorD et al. (1974) reviewed")
        assert tk < ad < th

    def test_fabricated_author_append_skipped(self, monkeypatch):
        """An append whose author is NOT in the roster never lands."""
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "append": "AuthorX (1999) fabricated a study that does not exist anywhere at all.",
                    "author": "AuthorX",
                    "reason": "omission",
                }
            ],
        )
        assert "AuthorX" not in out
        flags = [i for i in issues if i.detector == "verification_append" and i.severity == "flag"]
        assert flags and "none passed" in flags[0].detail

    def test_already_covered_author_append_skipped(self, monkeypatch):
        """An append for an author the summary already cites is skipped
        (the dedup guard — appends are for MISSING authors only)."""
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "append": (
                        "AuthorB and AuthorC (1968) studied the concept and "
                        "reported many findings over the years of follow-up."
                    ),
                    "author": "AuthorB",
                    "reason": "omission",
                }
            ],
        )
        # no new bullet for the covered author (exactly one mention, original)
        assert out.count("AuthorB and AuthorC (1968)") == 1

    def test_append_text_must_name_the_author(self, monkeypatch):
        """An append whose TEXT does not name the matched author is
        skipped (the bullet must cover the person it claims)."""
        out, _ = _run_layer(
            monkeypatch,
            [
                {
                    "append": "An unrelated bullet about something else entirely with no name inside it.",
                    "author": "AuthorD et al.",
                    "reason": "omission",
                }
            ],
        )
        assert "unrelated bullet" not in out

    def test_append_shape_caps_enforced(self, monkeypatch):
        """Fragments (<40 chars) and essays (>400 chars) are skipped."""
        out, _ = _run_layer(
            monkeypatch,
            [
                {"append": "Too short.", "author": "AuthorD", "reason": "omission"},
                {
                    "append": "AuthorD et al. (1974) reviewed the studies "
                    + "very thoroughly " * 40,
                    "author": "AuthorD",
                    "reason": "omission",
                },
            ],
        )
        assert "Too short." not in out
        assert "very thoroughly" not in out

    def test_one_append_per_author(self, monkeypatch):
        """Two appends for the same missing author → only the first lands."""
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "append": "AuthorD et al. (1974) reviewed the studies of the era in detail here.",
                    "author": "AuthorD",
                    "reason": "omission",
                },
                {
                    "append": "AuthorD et al. (1974) also covered thirteen samples across the spectrum.",
                    "author": "AuthorD",
                    "reason": "omission",
                },
            ],
        )
        fixes = [i for i in issues if i.detector == "verification_append" and i.severity == "fix"]
        assert len(fixes) == 1

    def test_fuzzy_replacement_plus_append_compose(self, monkeypatch):
        """The two shapes compose: a near-miss replacement anchor lands
        via the normalized match AND a roster-grounded append lands."""
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "original": "AuthorA (1975) DESCRIBED the organization",  # case near-miss
                    "corrected": "AuthorA (1975) delineated the organization",
                    "reason": "name",
                },
                {
                    "append": "AuthorD et al. (1974) reviewed the studies of the era, covering thirteen samples.",
                    "author": "AuthorD",
                    "reason": "omission",
                },
            ],
        )
        assert "delineated the organization" in out
        assert "AuthorD et al. (1974) reviewed the studies" in out
        assert any(i.detector == "verification_append" and i.severity == "fix" for i in issues)
        assert any(i.detector == "verification" and i.severity == "fix" for i in issues)

    def test_no_bullet_list_means_no_append(self, monkeypatch):
        """A summary with no bullet list fails open: the append is
        skipped with a flag (nothing to append to structurally)."""
        provider = _MockVerifyProvider(
            json.dumps(
                [
                    {
                        "append": "AuthorD et al. (1974) reviewed the studies of the era comprehensively.",
                        "author": "AuthorD",
                        "reason": "omission",
                    }
                ]
            )
        )
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        no_bullets = (
            "# Summary: T\n\n## Executive Summary\n\n"
            f"{_FILLER}\n\nAuthorA (1975) described it. AuthorB and AuthorC (1968) studied it.\n\n"
            "<!-- COMPLETE run_id=t -->\n"
        )
        out, issues = verify_and_polish_summary(no_bullets, _SOURCE, settings=_MockSettings())
        assert "AuthorD et al. (1974) reviewed" not in out
        assert any(
            i.detector == "verification_append" and "no bullet list" in i.detail for i in issues
        )

    def test_length_guard_does_not_reject_appends(self, monkeypatch):
        """The D3 length guard judges the REPLACEMENTS only — appends are
        bounded by their own caps (the old guard rejected EVERY correction
        whenever additions pushed past 115%)."""
        # one missing-roster author here; a single append + the growth
        # assertion suffices (the replacement-only 115% cap must not reject
        # the append-driven growth).
        out, issues = _run_layer(
            monkeypatch,
            [
                {
                    "append": "AuthorD et al. (1974) reviewed the studies of the era, covering thirteen samples in the spectrum overall.",
                    "author": "AuthorD",
                    "reason": "omission",
                }
            ],
        )
        assert len(out) > len(_mk_rendered())  # the append grew the text
        assert not any("outside 85-115%" in i.detail for i in issues)


class TestAppendHelpers:
    def test_match_missing_author_shapes(self):
        assert _match_missing_author("AuthorD et al.", ["AuthorA", "AuthorD"]) == "AuthorD"
        assert _match_missing_author("AuthorB", ["AuthorA", "AuthorB and AuthorC"]) == (
            "AuthorB and AuthorC"
        )
        assert _match_missing_author("AuthorX", ["AuthorA"]) is None
        assert _match_missing_author("", ["AuthorA"]) is None

    def test_find_append_insertion_offset_before_thorough(self):
        md = (
            "## Key Takeaways\n\n- one\n- two\n\n## Thorough Summary\n\ntext\n\n"
            "---\n\n*Generated by Elixir v0.5.19 · run t*\n\n<!-- COMPLETE run_id=t -->\n"
        )
        off = _find_append_insertion_offset(md)
        assert off is not None
        assert md[off - len("- two\n") : off] == "- two\n"

    def test_find_append_insertion_offset_none_without_bullets(self):
        assert _find_append_insertion_offset("no bullets here\n\n<!-- COMPLETE -->") is None
