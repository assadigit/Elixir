"""V0.5.19 — the prose-form author-year consistency check (3b), the
thin roster-gap-fill bullet flag, and the scholar-reflection loosened
quote-guard.

The V0.5.18 ch.9 re-run's thin roster-gap-fill bullet said an author was
"Cited in a work from 1980" — the real year is 1988, but the year sat in
PROSE (no parentheses), so the citation-shaped checks 1/3 could not see
it. Three fixes (content-agnostic — Rule 1: synthetic names):

1. **Check 3b** (``attribution.validate_years``): a sentence naming a
   KNOWN roster author + a scholarly-work prose-year attachment
   ("a work/paper/study/... from/in/of NNNN") must carry the year in a
   named author's roster years (or be citation-shaped-adjacent in the
   source) — else flagged.
2. **The thin-bullet flag**: "Name: Cited in/Authored/Contributed to …"
   one-liner shapes are flagged as quality signals for the audit.
3. **The loosened quote-guard** (``scholar_reflection``): a quote-less
   gap-fill bullet that NAMES a runtime-roster source author is KEPT
   (the V0.5.10 regex-roster fallback gap_fill_batch already has).

Run: pytest tests/test_v0519_prose_year_thin_bullet.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk

from core.summarisation.postchecks.attribution import validate_years  # noqa: E402
from core.summarisation.scholar_reflection import scholar_reflection  # noqa: E402

# ── 1. check 3b: the prose-form year consistency ────────────────────────────


class TestProseFormYearConsistency:
    def _run(self, text: str, source: str, source_authors: list[str]):
        _out, issues = validate_years(text, "summary", source_authors, source)
        return issues

    def test_prose_year_slip_flagged(self):
        """The evidenced shape: a roster author + 'a work from YEAR'
        where the year is not in their roster years → flagged."""
        source = "AuthorA et al. (1988) reviewed the attribution rules comprehensively."
        issues = self._run(
            "- AuthorA: Cited in a work from 1980 regarding attribution rules.",
            source,
            ["AuthorA"],
        )
        prose_flags = [i for i in issues if "prose-form year" in i.detail]
        assert len(prose_flags) == 1
        assert "1980" in prose_flags[0].detail

    def test_correct_prose_year_passes(self):
        source = "AuthorA et al. (1988) reviewed the attribution rules comprehensively."
        issues = self._run(
            "- AuthorA: Cited in a work from 1988 regarding attribution rules.",
            source,
            ["AuthorA"],
        )
        assert not [i for i in issues if "prose-form year" in i.detail]

    def test_co_cited_author_year_passes(self):
        """When the sentence names multiple roster authors and the year
        belongs to one of THEM, the check stays silent (conservative)."""
        source = (
            "AuthorB (1980) critiqued the rules. AuthorA et al. (1988) reviewed them."
        )
        issues = self._run(
            "- AuthorA and AuthorB: a study from 1980 changed the field.",
            source,
            ["AuthorA", "AuthorB"],
        )
        assert not [i for i in issues if "prose-form year" in i.detail]

    def test_citation_shaped_adjacency_exemption(self):
        """A year the source genuinely pairs with the author (in a shape
        the roster build missed) is exempt — same exemption as check 3."""
        source = "AuthorA's lengthy 1979 report on the topic appeared that year."
        issues = self._run(
            "- AuthorA: a work from 1979 appeared that year.",
            source,
            ["AuthorA"],
        )
        assert not [i for i in issues if "prose-form year" in i.detail]

    def test_count_not_year_ignored(self):
        """'a study of 1200 patients' — the 4-digit COUNT below the year
        floor never reads as a year."""
        source = "AuthorA et al. (1988) reviewed the literature."
        issues = self._run(
            "- AuthorA ran a study of 1200 patients across the clinics.",
            source,
            ["AuthorA"],
        )
        assert not [i for i in issues if "prose-form year" in i.detail]

    def test_no_known_author_in_sentence_ignored(self):
        """A prose-year with no roster author named in the sentence is
        not our case (no attribution to check)."""
        source = "AuthorA et al. (1988) reviewed the literature."
        issues = self._run(
            "- An anonymous work from 1910 shaped the field's direction.",
            source,
            ["AuthorA"],
        )
        assert not [i for i in issues if "prose-form year" in i.detail]


# ── 2. the thin roster-gap-fill bullet flag ─────────────────────────────────


class TestThinGapFillBulletFlag:
    def _thin_flags(self, text: str):
        _out, issues = validate_years(text, "summary", [], "")
        return [i for i in issues if "thin roster-gap-fill" in i.detail]

    def test_cited_in_shape_flagged(self):
        flags = self._thin_flags("- WidigerLike: Cited in a work from 1980 regarding rules.")
        assert len(flags) == 1

    def test_authored_shape_flagged(self):
        flags = self._thin_flags("- WolfLike: Authored literature on two related conditions.")
        assert len(flags) == 1

    def test_contributed_shape_flagged(self):
        flags = self._thin_flags("- ChickLike: Contributed to literature on early phenomena.")
        assert len(flags) == 1

    def test_real_claim_bullet_not_flagged(self):
        assert not self._thin_flags(
            "- AuthorA (1975) delineated the organization and its three levels of severity."
        )
        assert not self._thin_flags("- AuthorA: Demonstrated that the mechanism operates in stages.")

    def test_deduped_per_line(self):
        text = "- AuthorA: Cited in a work from 1980 regarding rules."
        assert len(self._thin_flags(text)) == 1
        assert len(self._thin_flags(text + "\n" + text)) == 1


# ── 3. the scholar-reflection loosened quote-guard ──────────────────────────


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


class _FakePromptManager:
    def render_template(self, name, **kw):
        return f"PROMPT name={name}"


def _run_scholar(src: str, llm: str):
    result = {"executive_summary": "e", "bullet_points": ["existing bullet"], "thorough_summary": "t"}
    log = _CapturingLog()
    scholar_reflection(
        "Ch",
        src,
        result,
        max_context_tokens=32768,
        language="en",
        temperature=0.7,
        prompt_manager=_FakePromptManager(),
        recover_vram=lambda *a, **k: None,
        call_fast_llm=lambda prompt, **kw: llm,
        strip_thinking=lambda t: t,
        log=log,
    )
    return result, log


class TestScholarReflectionLoosenedQuoteGuard:
    def test_roster_grounded_quoteless_bullet_kept(self):
        """V0.5.19: a quote-less gap-fill bullet that NAMES a
        runtime-roster source author is KEPT (the regex-roster
        grounding — the V0.5.10 gap_fill_batch pattern)."""
        src = "AuthorF (1971) described the mechanism of the condition in the source text."
        llm = (
            "<gap_fill_bullets>\n"
            "- AuthorF (1971) described the mechanism of the condition in detail\n"
            "</gap_fill_bullets>"
        )
        result, log = _run_scholar(src, llm)
        assert len(result["bullet_points"]) == 2
        assert any("AuthorF (1971) described the mechanism" in b for b in result["bullet_points"])
        debugs = [m for m, l in log.calls if l == "DEBUG"]
        assert any("Accepted roster-grounded gap-fill" in d for d in debugs)

    def test_quoteless_bullet_without_roster_author_still_dropped(self):
        """The strict V13.42.0 guard stays for bullets naming NO roster
        author (the anti-hallucination default)."""
        src = "AuthorF (1971) described the mechanism of the condition in the source text."
        llm = (
            "<gap_fill_bullets>\n"
            "- AuthorX (1999) fabricated a study with no quote markers at all\n"
            "</gap_fill_bullets>"
        )
        result, log = _run_scholar(src, llm)
        assert len(result["bullet_points"]) == 1  # unchanged
        debugs = [m for m, l in log.calls if l == "DEBUG"]
        assert any("Dropped gap-fill without quote" in d for d in debugs)

    def test_quoted_bullet_path_unchanged(self):
        """The quoted-bullet grounding path is unchanged (a verbatim
        quote still grounds a bullet for any author)."""
        src = "AuthorF (1971) described the persistent sameness of the condition in the source."
        llm = (
            "<gap_fill_bullets>\n"
            '- AuthorF described the "persistent sameness of the condition"\n'
            "</gap_fill_bullets>"
        )
        result, _ = _run_scholar(src, llm)
        assert len(result["bullet_points"]) == 2
