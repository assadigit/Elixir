"""V0.5.21 backlog tests (the three code-fixable items).

The V0.5.20 release closed the dedicated-tools campaign's pipeline-side
backlog; the remaining V0.5.21 backlog (filed by the V0.5.17 audit line
44 + the V0.5.19.1 audit line 88 + NEW_SESSION_PROMPT.md §"Secondary
agenda") has three code-fixable items:

ITEM 1 — thin roster-gap-fill prompt tightening: the thin one-liners
  ("Name made significant contributions to …" / "Name: Contributed to
  literature on …") are all CAUGHT by the V0.5.19/V0.5.20 quality flags,
  but the MODEL still writes them — the roster gap-fill prompts never
  demanded the author's SPECIFIC contribution. Fix: a quality rule in
  the main batch prompt + the final-check round-4 prompt.

ITEM 2 — glossary pair-form dedup at ingestion: the rig glossary listed
  BOTH "A and B" AND "B and A" (the commuted pair-form artifact — the
  individuals are covered; the pair is listed twice). Fix: keep-first
  dedup of commuted two-name pair-forms in ``_parse_name_bullets`` (all
  3 parse tiers pass through it).

ITEM 3 — the see-also bound: the loosened quote-guard (V0.5.6
  glossary-backed override + the final-check round 4) accepted a
  see-also-only citation bullet with slight content inflation — the
  bullet credited the see-also author with the HOLDER's claim words
  that sit in the same source sentence. The backlog: "verify whether
  the glossary context should bound it" — it should: a loosened
  acceptance now requires the bullet's content tokens (light-verb-
  stripped, author/year-removed) to be ≥ 55% covered by the GLOSSARY
  CONTEXT for the author (the house containment floor —
  summarizer_coverage's per-bullet 0.55 precedent). Source sentences
  are deliberately NOT part of the grounding: the holder's claim words
  sit in the same sentence — that is exactly the inflation vector. A
  bound-rejected bullet is treated like a vetoed one (the author stays
  honestly missing; the mention-only escalation / give-up machinery
  applies). The V0.5.10 regex fallback is NOT bounded (no glossary
  context exists for the author on that path by construction — the
  regex confirms presence, not content).

Content-agnostic (Rule 1): all author names in these tests are
SYNTHETIC FIXTURES (Sigma / Rho / Epsilon / Kappa / AuthorOne /
AuthorTwo / Beta / Gamma — the house placeholder set); the bound
measure uses the RUNTIME glossary context + generic English light
verbs, no book-derived vocabulary. The banned-phrase list in the
prompt rules is the generic citation-registry verb set the V0.5.19
detector already pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v0510_quoteguard_markitdown.py
# (markitdown) and tests/test_gap_fill_batch.py (tiktoken + markitdown) —
# both modules are imported eagerly by the core.summarisation chain.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ─────────────────────────────────────────────────────────────────────────────
# Shared scaffolding (mirrors tests/test_v0510_quoteguard_markitdown.py).
# ─────────────────────────────────────────────────────────────────────────────


class _CapturingLog:
    """Captures (msg, level) pairs."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _make_gap_fill_deps(*, responses=None, response_fn=None):
    """Build hermetic deps for batch_gap_fill."""
    log = _CapturingLog()
    llm_calls = []

    def check_coverage(analysis, text):
        text = text or ""
        covered = [a for a in analysis["authors"] if a in text]
        missing = [a for a in analysis["authors"] if a not in text]
        total = len(analysis["authors"])
        pct = (len(covered) / total) if total else 0.0
        return {"covered": covered, "missing": missing, "total": total, "coverage_pct": pct}

    def call_llm(prompt, max_tokens=None, temperature=None, **kw):
        i = len(llm_calls)
        llm_calls.append({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})
        if response_fn is not None:
            return response_fn(prompt, i)
        if responses is not None and i < len(responses):
            return responses[i]
        return None

    def strip_thinking(text):
        return text

    def filter_thinking_bullets(bullets, concepts=None, source_text=""):
        return list(bullets)

    return {
        "log": log,
        "check_coverage": check_coverage,
        "call_llm": call_llm,
        "strip_thinking": strip_thinking,
        "filter_thinking_bullets": filter_thinking_bullets,
        "llm_calls": llm_calls,
    }


def _run_gap_fill(
    deps,
    *,
    content,
    bullets,
    missing,
    analysis,
    det_authors,
    heading="Chapter 1 — Test",
    source_glossary=None,
    regex_confirmed_authors=None,
):
    from core.summarisation.gap_fill_batch import batch_gap_fill

    return batch_gap_fill(
        heading,
        content,
        bullets,
        missing,
        analysis,
        det_authors,
        check_coverage=deps["check_coverage"],
        call_llm=deps["call_llm"],
        temperature=0.2,
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=deps["filter_thinking_bullets"],
        log=deps["log"],
        source_glossary=source_glossary,
        regex_confirmed_authors=regex_confirmed_authors,
    )


# The see-also-bound synthetic source: the holder (Rho) holds the claim
# via "according to Rho"; the missing author (Sigma) appears ONLY inside
# the see-also parenthetical (the V0.5.17 audit's verified veto vector —
# detect_parenthetical_promotion docstring, the AuthorF/AuthorG shape).
_SEE_ALSO_SRC = (
    "The drive toward isolation, according to Rho, is the longing to "
    "abandon the human quality of identity (see also Sigma 1960 in this "
    "connection)."
)
# The inflated bullet (the Searles shape): credits Sigma with the
# holder's claim words — "longing", "human", "quality" go beyond the
# glossary context's "cited in connection with identity abandonment".
_INFLATED_BULLET = "- Sigma (1960) discussed the longing to abandon the human quality of identity."
_SEE_ALSO_GLOSSARY = {
    "names": [
        {
            "name": "Sigma",
            "year": "1960",
            "context": "cited in connection with identity abandonment",
        },
    ],
    "path": "summaries/.glossaries/ch_test.glossary.md",
}


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 3 (first — the bound helper is the new contract): the see-also bound
# ═══════════════════════════════════════════════════════════════════════════


class TestSeeAlsoBoundHelper:
    """V0.5.21: the pure bound measure — content-token coverage of a
    loosened-quote-guard bullet by the GLOSSARY CONTEXT for the author."""

    def _bound(self, bullet, author, texts):
        from core.summarisation.gap_fill_batch import _v0521_see_also_bound

        return _v0521_see_also_bound(bullet, author, texts)

    def test_full_coverage_returns_one(self):
        cov = self._bound(
            "- Epsilon: Established the unified framework of identity development.",
            "Epsilon",
            ["Epsilon (1948) — established the unified framework of identity development"],
        )
        assert cov == 1.0, f"full coverage expected 1.0, got {cov}"

    def test_light_verbs_do_not_count_against_coverage(self):
        # "attributed"/"introduced"/"discussed" are attribution verbs —
        # the house _LIGHT_VERB_RE strips them before tokenizing, so a
        # bullet's verb choice never defeats the bound.
        cov = self._bound(
            "Klein (1946) attributed the paranoid-schizoid position to infants.",
            "Klein",
            ["Klein (1946) — the paranoid-schizoid position of infants"],
        )
        assert cov >= 0.55, f"verb-only difference should pass; got {cov}"

    def test_inflated_see_also_shape_below_floor(self):
        cov = self._bound(
            _INFLATED_BULLET, "Sigma", ["cited in connection with identity abandonment"]
        )
        assert cov < 0.55, (
            f"the see-also inflation shape ({_INFLATED_BULLET[:50]}…) must "
            f"score below the 0.55 floor; got {cov}"
        )

    def test_prefix_tolerance_abandon_abandonment(self):
        # "abandon" (bullet) ~ "abandonment" (glossary context) — the
        # derivational-prefix tolerance (min 5 chars, either direction).
        cov = self._bound(
            "Sigma (1960) — the abandon of identity.",
            "Sigma",
            ["cited in connection with identity abandonment"],
        )
        # tokens: {the, abandon, identity} — the ✗, abandon ✓ (prefix),
        # identity ✓ → 2/3 = 0.67 ≥ 0.55
        assert cov >= 0.55, f"prefix tolerance expected; got {cov}"

    def test_plural_normalization_relations_relation(self):
        cov = self._bound(
            "Beta (1980) — object relations.",
            "Beta",
            ["Beta (1980) — the object relation in development"],
        )
        assert cov == 1.0, f"plural tolerance expected 1.0; got {cov}"

    def test_author_and_year_tokens_excluded(self):
        # A bullet that is ONLY the author name + year has no content to
        # bound → 1.0 (never the bound's business).
        cov = self._bound("- Sigma (1960).", "Sigma", ["whatever context"])
        assert cov == 1.0

    def test_empty_bullet_returns_one(self):
        assert self._bound("", "Sigma", ["ctx"]) == 1.0

    def test_no_grounding_texts_returns_zero(self):
        # Nothing grounds the bullet → fail-closed (0.0 → rejection).
        cov = self._bound("- Sigma (1960) described the framework.", "Sigma", [])
        assert cov == 0.0

    def test_name_only_grounding_cannot_bound_content(self):
        # A glossary entry with NO context (the bare-name shape) grounds
        # nothing → any content bullet scores 0 → rejected.
        cov = self._bound(
            "- Sigma (1960) described the framework of identity.",
            "Sigma",
            ["Sigma"],
        )
        assert cov == 0.0


class TestGlossaryOverrideBound:
    """V0.5.21 item 3: the V0.5.6 glossary-backed loosened override is now
    BOUNDED by the glossary context. An inflated bullet (the see-also
    shape) is rejected like a vetoed one; a glossary-grounded bullet
    (the V0.5.6 Bak shape) is still accepted."""

    def test_inflated_see_also_bullet_rejected(self):
        deps = _make_gap_fill_deps(responses=[_INFLATED_BULLET, None, None, None, None])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=_SEE_ALSO_SRC,
            bullets=bullets,
            missing=["Sigma"],
            analysis={"authors": ["Sigma"]},
            det_authors=["Sigma", "Rho"],
            source_glossary=_SEE_ALSO_GLOSSARY,
        )
        assert bullets == [], (
            "V0.5.21: the inflated see-also bullet must NOT be merged — "
            "the glossary context does not ground 'longing/human/quality'"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        bound_logs = [m for m in all_logs if "V0.5.21 see-also bound" in m]
        assert bound_logs, "V0.5.21: the bound-rejection WARNING must fire"
        accept_logs = [m for m in all_logs if "✨ V0.5.6 gap-fill: accepted" in m]
        assert not accept_logs, "V0.5.21: no V0.5.6 acceptance log on a bound rejection"
        # The author finishes honestly missing (the final WARNING names it).
        assert "Sigma" in out.still_missing or any(
            "still missing" in m and "Sigma" in m for m in all_logs
        ), "V0.5.21: the bound-rejected author must be reported honestly missing"

    def test_bound_rejection_feeds_the_veto_escalation(self):
        # A bound rejection counts like a veto: TWO bound rejections →
        # the mention-only prompt fires for the author on the next round.
        deps = _make_gap_fill_deps(
            responses=[
                _INFLATED_BULLET,  # round 1: bound-rejected (veto count 1)
                _INFLATED_BULLET,  # round 2: bound-rejected (veto count 2)
                "- Rho integrated Sigma (1960) into the account of identity.",  # r3 mention-only
                None,
                None,
            ]
        )
        bullets: list[str] = []
        _run_gap_fill(
            deps,
            content=_SEE_ALSO_SRC,
            bullets=bullets,
            missing=["Sigma"],
            analysis={"authors": ["Sigma"]},
            det_authors=["Sigma", "Rho"],
            source_glossary=_SEE_ALSO_GLOSSARY,
        )
        round3_prompt = deps["llm_calls"][2]["prompt"]
        assert "MENTION-ONLY authors: Sigma" in round3_prompt, (
            "V0.5.21: two bound rejections must escalate Sigma to the "
            "mention-only prompt (the veto-count path)"
        )

    def test_glossary_grounded_bullet_still_accepted(self):
        # The V0.5.6 Bak shape: the bullet's content IS the glossary
        # context → the bound passes → the acceptance log fires.
        src = (
            "Kappa established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bullet = "- Epsilon: Established the unified framework of identity development."
        glossary = {
            "names": [
                {
                    "name": "Epsilon",
                    "year": "1948",
                    "context": "established the unified framework of identity development",
                },
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        deps = _make_gap_fill_deps(responses=[bullet])
        bullets: list[str] = []
        _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Kappa"],
            source_glossary=glossary,
        )
        assert len(bullets) == 1 and "Epsilon" in bullets[0], (
            "V0.5.21: a glossary-grounded bullet (content ⊆ glossary "
            "context) must still be accepted by the loosened quote-guard"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        assert any("✨ V0.5.6 gap-fill: accepted" in m for m in all_logs)
        assert not any("V0.5.21 see-also bound" in m for m in all_logs)

    def test_regex_fallback_path_not_bounded(self):
        # The V0.5.10 regex fallback has NO glossary context for the
        # author by construction (the author is not in the glossary —
        # that is why the regex path fired) → the bound does NOT apply
        # (the regex confirms PRESENCE, not content — scoping documented
        # in the V0.5.21 CHANGELOG).
        src = (
            "Kappa established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bullet = "- Epsilon: Established the unified framework of identity development."
        deps = _make_gap_fill_deps(responses=[bullet])
        bullets: list[str] = []
        _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Kappa"],
            source_glossary=None,
            regex_confirmed_authors=["Epsilon", "Kappa"],
        )
        assert len(bullets) == 1, (
            "V0.5.21: the V0.5.10 regex path keeps its acceptance "
            "behavior (no glossary context to bound by)"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        assert not any("V0.5.21 see-also bound" in m for m in all_logs)


class TestRound4Bound:
    """V0.5.21 item 3: the final-check round 4 acceptance is bounded by
    the glossary context (the Searles bullet's actual origin — the
    V0.5.6 round 4 fired "Klein + Searles accepted glossary-grounded")."""

    def test_round4_inflated_bullet_rejected(self):
        # 3 empty standard rounds → give-up → round 4 fires for Sigma →
        # the response carries the inflated bullet → the bound rejects it.
        deps = _make_gap_fill_deps(
            responses=[
                None,  # round 1 standard: empty
                None,  # round 2 standard: empty (mention-only next round)
                None,  # round 3 standard: mention-only attempt fails → give up
                _INFLATED_BULLET,  # round 4 final-check: the inflated bullet
            ]
        )
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=_SEE_ALSO_SRC,
            bullets=bullets,
            missing=["Sigma"],
            analysis={"authors": ["Sigma"]},
            det_authors=["Sigma", "Rho"],
            source_glossary=_SEE_ALSO_GLOSSARY,
        )
        assert bullets == [], "V0.5.21: round 4 must not merge the inflated bullet"
        assert out.final_check_added == 0, (
            f"V0.5.21: final_check_added must be 0 (bound rejection); got {out.final_check_added}"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        assert any("V0.5.21 see-also bound" in m for m in all_logs), (
            "V0.5.21: the round-4 bound rejection must log the WARNING"
        )
        # The final-check coverage line reports Sigma still missing.
        assert any("still missing" in m and "Sigma" in m for m in all_logs), (
            "V0.5.21: the final-check must report the bound-rejected author honestly"
        )

    def test_round4_glossary_context_bullet_accepted(self):
        # The round-4 fixture shape (the existing V0.5.6 contract): the
        # bullet mirrors the glossary context → accepted, bound silent.
        src = "Alpha established the framework. Beta extended it. Gamma synthesized it."
        glossary = {
            "names": [
                {"name": "Alpha", "year": "1971", "context": "described the framework"},
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
                {"name": "Gamma", "year": "1985", "context": "provided the integration"},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        deps = _make_gap_fill_deps(
            responses=[
                None,
                None,
                None,
                "- Beta (1980) extended the synthesis.\n- Gamma (1985) provided the integration.",
            ]
        )
        bullets = ["- Alpha (1971) described the framework."]
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Beta", "Gamma"],
            analysis={"authors": ["Beta", "Gamma"]},
            det_authors=["Beta", "Gamma"],
            source_glossary=glossary,
        )
        assert out.final_check_added == 2, (
            f"V0.5.21: glossary-context-grounded round-4 bullets must be "
            f"accepted; got {out.final_check_added}"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        assert not any("V0.5.21 see-also bound" in m for m in all_logs)

    def test_round4_name_only_glossary_entry_rejects_content_bullet(self):
        # A glossary entry with NO context grounds nothing — the round-4
        # contribution bullet cannot be bounded by it → rejected (fail-
        # closed: the author stays honestly missing rather than shipping
        # an ungroundable bullet).
        glossary = {
            "names": [
                {"name": "Beta", "year": "1980", "context": ""},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        deps = _make_gap_fill_deps(
            responses=[
                None,
                None,
                None,
                "- Beta (1980) extended the synthesis.",
            ]
        )
        bullets = ["- Alpha (1971) described the framework."]
        out = _run_gap_fill(
            deps,
            content=(
                "Alpha established the framework of identity development. "
                "Beta extended the framework toward the broader synthesis "
                "of perspectives on identity."
            ),
            bullets=bullets,
            missing=["Beta"],
            analysis={"authors": ["Beta"]},
            det_authors=["Beta", "Alpha"],
            source_glossary=glossary,
        )
        assert out.final_check_added == 0, (
            "V0.5.21: a contextless glossary entry cannot ground a round-4 contribution bullet"
        )
        all_logs = [m for m, _ in deps["log"].calls]
        assert any("V0.5.21 see-also bound" in m for m in all_logs)


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 1 — the thin roster-gap-fill prompt tightening
# ═══════════════════════════════════════════════════════════════════════════


class TestPromptTightening:
    """V0.5.21 item 1: the roster gap-fill prompts (the main batch prompt
    + the final-check round-4 prompt) now DEMAND the author's SPECIFIC
    contribution and ban the generic registry phrases (the thin
    one-liner family the V0.5.19/V0.5.20 flags catch at ship time — the
    model should not write them in the first place)."""

    def test_batch_prompt_demands_specific_contribution(self):
        deps = _make_gap_fill_deps(
            responses=["- Rho: Established the framework of identity development."]
        )
        bullets: list[str] = []
        _run_gap_fill(
            deps,
            content="Rho established the framework of identity development.",
            bullets=bullets,
            missing=["Rho"],
            analysis={"authors": ["Rho"]},
            det_authors=["Rho"],
        )
        assert deps["llm_calls"], "the gap-fill LLM call must have fired"
        p = deps["llm_calls"][0]["prompt"]
        assert "SPECIFIC contribution" in p, (
            "V0.5.21: the batch prompt must demand the SPECIFIC contribution"
        )
        # The banned generic registry phrases are named in the prompt
        # (generic citation-registry verbs — the V0.5.19 detector's set).
        assert "made significant contributions to" in p, (
            "V0.5.21: the batch prompt must ban the generic registry phrase"
        )
        assert "contributed to the literature" in p or "authored literature on" in p

    def test_round4_prompt_demands_specific_contribution(self):
        glossary = {
            "names": [
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        deps = _make_gap_fill_deps(
            responses=[
                None,
                None,
                None,
                "- Beta (1980) extended the synthesis.",
            ]
        )
        bullets = ["- Alpha (1971) described the framework."]
        _run_gap_fill(
            deps,
            content=(
                "Alpha established the framework of identity development. "
                "Beta extended the framework toward the broader synthesis "
                "of perspectives on identity."
            ),
            bullets=bullets,
            missing=["Beta"],
            analysis={"authors": ["Beta"]},
            det_authors=["Beta", "Alpha"],
            source_glossary=glossary,
        )
        assert len(deps["llm_calls"]) >= 4, (
            f"the round-4 final-check LLM call must have fired (got {len(deps['llm_calls'])} calls)"
        )
        round4_prompt = deps["llm_calls"][3]["prompt"]
        assert "SPECIFIC contribution" in round4_prompt, (
            "V0.5.21: the round-4 prompt must demand the SPECIFIC contribution"
        )


# ═══════════════════════════════════════════════════════════════════════════
# ITEM 2 — the glossary pair-form dedup at ingestion
# ═══════════════════════════════════════════════════════════════════════════


_PAIR_MARKDOWN_RESPONSE = """## Source Glossary — Names
- **AuthorOne and AuthorTwo** (1980) — jointly described the framework
- **AuthorTwo and AuthorOne** (1981) — duplicate commuted pair form
- **SoloAuthor** (1975) — individual entry
## Source Glossary — Dates
- **1980-1990** — the framework's development decade
## Source Glossary — Terms
- **X framework** — a theoretical model for understanding Y
"""

_PAIR_XML_RESPONSE = """<name_glossary>
## Names
- **AuthorOne and AuthorTwo** (1980) — jointly described the framework
- **AuthorTwo and AuthorOne** (1981) — duplicate commuted pair form
- **SoloAuthor** (1975) — individual entry
## Dates
## Terms
</name_glossary>
"""

_PAIR_LENIENT_RESPONSE = """- **AuthorOne and AuthorTwo** (1980) — jointly described the framework
- **AuthorTwo and AuthorOne** (1981) — duplicate commuted pair form
- **SoloAuthor** (1975) — individual entry
"""


class TestPairFormDedup:
    """V0.5.21 item 2: commuted two-name pair-forms are deduplicated at
    glossary INGESTION (keep-first) — every parse tier passes through
    ``_parse_name_bullets``."""

    @pytest.mark.parametrize(
        ("raw", "label"),
        [
            (_PAIR_MARKDOWN_RESPONSE, "markdown-header tier"),
            (_PAIR_XML_RESPONSE, "xml tier"),
            (_PAIR_LENIENT_RESPONSE, "lenient bare-bullets tier"),
        ],
    )
    def test_commutated_pair_deduped_all_tiers(self, raw, label):
        from core.summarisation.glossary_parser import parse_name_glossary

        g = parse_name_glossary(raw)
        pair_entries = [n for n in g["names"] if " and " in n["name"]]
        assert len(pair_entries) == 1, (
            f"V0.5.21 ({label}): the commuted pair-form must be deduplicated "
            f"to the FIRST occurrence; got {[n['name'] for n in g['names']]}"
        )
        assert pair_entries[0]["name"] == "AuthorOne and AuthorTwo", (
            f"V0.5.21 ({label}): keep-FIRST semantics"
        )
        assert pair_entries[0]["year"] == "1980", "keep-first keeps the first year"
        # The individual entry is untouched.
        assert any(n["name"] == "SoloAuthor" for n in g["names"])

    def test_non_commutated_entries_untouched(self):
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha** (1970) — the framework
- **Beta** (1971) — the extension
- **Alpha and Beta** (1980) — the joint work
- **Gamma and Delta** (1982) — another pair
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert [n["name"] for n in g["names"]] == [
            "Alpha",
            "Beta",
            "Alpha and Beta",
            "Gamma and Delta",
        ], "V0.5.21: non-commuted entries (individuals + distinct pairs) are untouched"

    def test_ampersand_pair_form_deduped(self):
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha & Beta** (1980) — the joint work
- **Beta and Alpha** (1981) — the commuted duplicate
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert len(g["names"]) == 1
        assert g["names"][0]["name"] == "Alpha & Beta"

    def test_pair_form_with_different_years_deduped(self):
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha and Beta** (1980) — the joint work
- **Beta and Alpha** (1990) — the commuted duplicate with another year
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert len(g["names"]) == 1
        assert g["names"][0]["year"] == "1980"

    def test_same_name_pair_not_deduped_as_pair(self):
        # "Alpha and Alpha" is not a commuted pair (identical halves) —
        # the pair-form key ignores it (weird input, no crash, kept).
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha and Alpha** (1980) — degenerate form
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert len(g["names"]) == 1

    def test_three_name_form_untouched(self):
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha, Beta and Gamma** (1980) — the three-name form
- **Gamma, Beta and Alpha** (1981) — a different ordering (NOT a 2-name commuted pair)
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert len(g["names"]) == 2, (
            "V0.5.21: the dedup is scoped to TWO-name commuted pair-forms "
            "(the evidenced artifact shape) — three-name forms are untouched"
        )

    def test_exact_single_name_duplicates_kept_at_parse(self):
        # Characterization (pre-existing): single-name exact duplicates
        # are NOT deduped at parse (the downstream extractors dedupe) —
        # the V0.5.21 dedup is scoped to commuted pair-forms only.
        from core.summarisation.glossary_parser import parse_name_glossary

        raw = """## Source Glossary — Names
- **Alpha** (1980) — first
- **Alpha** (1981) — second
## Source Glossary — Dates
## Source Glossary — Terms
"""
        g = parse_name_glossary(raw)
        assert len(g["names"]) == 2

    def test_pair_form_helper_key(self):
        from core.summarisation.glossary_parser import _pair_form_key

        assert _pair_form_key("Alpha and Beta") == ("alpha", "beta")
        assert _pair_form_key("Beta and Alpha") == ("alpha", "beta")  # commuted → same key
        assert _pair_form_key("Alpha & Beta") == ("alpha", "beta")
        assert _pair_form_key("Alpha") is None
        assert _pair_form_key("Alpha, Beta and Gamma") is None
        assert _pair_form_key("Alpha and Alpha") is None
        assert _pair_form_key("") is None


class TestPairFormDedupIntegration:
    """The dedup flows through the full ingestion pipeline: parse →
    persist → cross-reference (one pair entry everywhere)."""

    def test_extract_persist_cross_reference_with_commutated_pair(self, tmp_path):
        from core.summarisation.glossary_parser import (
            extract_persist_and_cross_reference_glossary,
        )

        log = _CapturingLog()
        g = extract_persist_and_cross_reference_glossary(
            _PAIR_MARKDOWN_RESPONSE,
            heading="Chapter 1 — Test",
            output_dir=tmp_path,
            run_id="test-run",
            app_version="V0.5.21",
            regex_authors=["AuthorOne", "AuthorTwo", "SoloAuthor"],
            log=log,
        )
        pair_entries = [n for n in g["names"] if " and " in n["name"]]
        assert len(pair_entries) == 1, "the deduped dict carries the pair ONCE"
        # The persisted .md carries the pair ONCE.
        persisted = list((tmp_path / "summaries" / ".glossaries").glob("*.glossary.md"))
        assert persisted, "the glossary file must be persisted"
        content = persisted[0].read_text(encoding="utf-8")
        assert content.count("**AuthorOne and AuthorTwo**") == 1
        assert "AuthorTwo and AuthorOne" not in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
