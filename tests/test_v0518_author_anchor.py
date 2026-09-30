"""V0.5.18 — the boundary-safe author anchor (the ch.9 audit's Bug #1).

The V0.5.4 B1 word-boundary rule (``r"\\b" + re.escape(name) + r"\\b"``)
can NEVER match a name ending in ``"et al."`` — the terminal ``\\b`` after
the escaped period requires a following WORD character, and prose always
has ``"et al. "`` + space/paren. On the ch.9 operator-rig run, 6 of the 8
verification-flagged "missing" glossary authors were present in the
shipped text (false positives); benign as a flag, harmful the moment
append-mode corrections land (duplicate bullets for covered authors).

The fix: ``core.summarisation.author_anchor`` — strip the et-al suffix for
the presence check ("Authorone et al." anchors on "authorone") + lookaround
boundaries (``(?<!\\w)name(?!\\w)``) that work for non-word-edge names
while keeping the B1 no-substring-inside-longer-word property.

Behaviour matrix verified here:

| name                 | prose form                    | expected |
|----------------------|-------------------------------|----------|
| "Authorone et al."   | "Authorone et al. (1970) …"   | COVERED  |
| "Authorone et al."   | "Authorone's (1970) …"        | COVERED  |
| "Authorone et al."   | "Authorone and colleagues …"  | COVERED  |
| "Authorone et al."   | absent                        | MISSING  |
| "Abe"                | "Xyzabe mentioned"            | MISSING (B1 boundary) |
| "Authorxs"           | "Authorx noted"               | COVERED (plural tolerance) |

Plus: the glossary/regex cross-reference buckets anchor-normalize (an
et-al glossary name whose surname the regex caught is CONFIRMED, not
llm_only), and the verification LAYER's coverage flag no longer false-
flags present "et al." glossary names (the end-to-end regression).

Content-agnostic (Rule 1): synthetic Authorone/Authortwo fixtures.

Run: ``pytest tests/test_v0518_author_anchor.py -v``
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.author_anchor import (
    author_anchor,
    author_anchor_patterns,
    author_in_text,
    source_author_surnames,
)

# ── the anchor itself ────────────────────────────────────────────────────────


def test_anchor_strips_et_al_suffix():
    assert author_anchor("Authorone et al.") == "authorone"
    assert author_anchor("Authorone et al") == "authorone"
    assert author_anchor("Authorone") == "authorone"
    assert author_anchor("  Authorone Et Al.  ") == "authorone"
    # multi-word particle surnames keep their particles
    assert author_anchor("van der Waerden et al.") == "van der waerden"
    # fail-open: an et-al-only degenerate never yields an empty anchor
    assert author_anchor("et al.") == "et al"


def test_anchor_in_text_et_al_forms():
    # the exact prose form the B1 rule could never match (Bug #1)
    assert author_in_text("Authorone et al.", "authorone et al. (1970) described stages.")
    # possessive / colleague prose forms — same primary author
    assert author_in_text("Authorone et al.", "authorone's (1970) framework held.")
    assert author_in_text("Authorone et al.", "authorone and colleagues reported.")
    assert author_in_text("Authorone et al.", "per authorone, the stages persist.")
    # genuinely absent
    assert not author_in_text("Authorone et al.", "authortwo described a different line.")
    # end-of-string mention (no trailing char at all)
    assert author_in_text("Authorone et al.", "the framework of authorone et al.")


def test_anchor_keeps_b1_boundary_property():
    # the original B1 reason: a short surname inside a longer word is NOT a match
    assert not author_in_text("Abe", "xyzabe mentioned several theorists")
    assert author_in_text("Abe", "abe mentioned several theorists")
    # plural tolerance (the V0.5.4 crude heuristic, preserved)
    assert author_in_text("Authorxs", "authorx noted the pattern")
    # no text → no match
    assert not author_in_text("Authorone", "")


def test_anchor_patterns_compile_and_cover():
    pats = author_anchor_patterns("Authorone et al.")
    assert pats, "expected at least the anchor pattern"
    hay = "authorone et al. (1970) described stages."
    assert any(p.search(hay) for p in pats)


# ── the roster helper ────────────────────────────────────────────────────────


def test_source_author_surnames_runtime_roster():
    src = (
        "Authorone (1970) described identity formation through stages.\n"
        "Authortwo and Authorone (1971) extended the framework.\n"
        "Authorthree et al. (1975) tested it empirically."
    )
    roster = source_author_surnames(src)
    assert "Authorone" in roster
    assert "Authortwo" in roster
    assert "Authorthree" in roster
    # fail-open: no source, empty roster (a veto must never crash)
    assert source_author_surnames("") == []
    assert source_author_surnames(None) == []


# ── the cross-reference buckets (both copies anchor-normalize) ──────────────


def test_glossary_parser_cross_reference_anchor_normalized():
    from core.summarisation.glossary_parser import cross_reference_glossary

    xref = cross_reference_glossary(["Authorone et al."], ["Authorone"])
    assert xref["confirmed"] == ["Authorone et al."], (
        f"the et-al glossary name whose surname the regex caught is CONFIRMED; got {xref}"
    )
    assert xref["llm_only"] == []
    assert xref["regex_only"] == []


def test_verification_phase_cross_reference_anchor_normalized():
    from core.summarisation.verification_phase import cross_reference_glossary as xref_vp

    xref = xref_vp(["Authorone et al.", "Authortwo et al."], ["Authorone", "Authorthree"])
    # Authorone et al. ↔ Authorone: confirmed. Authortwo et al.: llm_only.
    # Authorthree: regex_only.
    assert "Authorone et al." in xref["confirmed"]
    assert "Authortwo et al." in xref["llm_only"]
    assert "Authorthree" in xref["regex_only"]


# ── the end-to-end regression: the verification coverage flag ────────────────


class _MockVerifyProvider:
    def __init__(self, raw_response):
        self._raw = raw_response

    def complete(self, *, prompt, temperature, max_tokens, model):
        return self._raw


class _MockSettings:
    def get(self, key, default=None):
        if key == "summarisation.model":
            return "mock-model"
        if key == "summarisation.model_architecture":
            return "single_local"
        return default


def test_verification_coverage_no_et_al_false_positive(monkeypatch):
    """The Bug #1 regression: a glossary name ending in 'et al.' that IS
    present in the shipped text (in et-al prose form) must NOT be flagged
    missing. Pre-V0.5.18 all such names were false-flagged."""
    from core.summarisation.verification_phase import (
        clear_glossary_cache,
        verify_and_polish_summary,
    )

    clear_glossary_cache()
    source = "Authorone et al. (1970) described the framework. Authortwo et al. (1971) extended it."
    # the summary covers Authorone et al. + Authortwo et al. in et-al prose
    # form; Authorthree (a plain glossary name) is genuinely absent.
    summary = (
        "Authorone et al. (1970) described the framework, and "
        "Authortwo et al. (1971) extended it to new populations."
    )
    glossary = {
        "names": [
            {"name": "Authorone et al.", "year": "1970", "context": "described the framework"},
            {"name": "Authortwo et al.", "year": "1971", "context": "extended the framework"},
            {"name": "Authorthree", "year": "1975", "context": "tested it empirically"},
        ],
        "path": "summaries/.glossaries/ch_test.glossary.md",
    }
    provider = _MockVerifyProvider("[]")
    monkeypatch.setattr(
        "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
    )
    _out, issues = verify_and_polish_summary(
        summary,
        source,
        settings=_MockSettings(),
        source_glossary=glossary,
        chapter_heading="Test Chapter",
    )
    cov = [i for i in issues if i.detector == "verification_coverage"]
    assert cov, "the genuinely-missing Authorthree must still be flagged"
    detail = cov[0].detail
    assert "Authorthree" in detail
    # THE FIX: the two present et-al names are no longer false-flagged
    assert "Authorone" not in detail.replace("Authorone et al.", ""), (
        f"Authorone et al. is present in the summary — must not be flagged; got: {detail!r}"
    )
    assert "Authortwo" not in detail.replace("Authortwo et al.", ""), (
        f"Authortwo et al. is present in the summary — must not be flagged; got: {detail!r}"
    )
    # exactly ONE missing author (pre-V0.5.18 this flagged all three)
    assert "1 source author(s) NOT found" in detail, detail
