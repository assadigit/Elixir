"""V0.5.17 — the near-duplicate author-coverage veto tests.

Characterization tests for the ship-time near-duplicate removal in
``core/summarisation/postchecks/orchestrator.py`` (``run_post_checks``).

Before V0.5.17 the near-dup check ("keep the first, drop the rest" on
token-set containment ≥ 0.8) had NO author awareness: it could drop a
gap-fill bullet that uniquely named a regex-confirmed source author
(the V0.5.16 ch.1 repeatability run lost Eissler this way — the gap-fill
added "Eissler and Blos shared Erikson's emphasis on adolescence…", the
near-dup check dropped it as a twin of the kept Blos/Erikson bullet).

Behaviour matrix verified here:

| scenario                        | expected                        |
|---------------------------------|---------------------------------|
| near-dup, no unique author      | DROPPED (the V0.05 F6 behavior) |
| near-dup, unique source author  | KEPT + a `flag` Issue (veto)    |
| near-dup, author elsewhere      | DROPPED (covered by kept text)  |
| no source_text                  | DROPPED (legacy fail-closed)    |

Content-agnostic (Rule 1): synthetic authors + bullets.

Run: ``pytest tests/test_v0517_neardup_author_veto.py -v``
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.postchecks import run_post_checks

# A synthetic source: Authorone (1970) + Authortwo (1971) are cited.
_SOURCE = (
    "Authorone (1970) described how identity formation proceeds through "
    "developmental stages toward a persistent sense of selfsameness.\n"
    "Authortwo (1971) emphasized the consolidation of inner solidarity "
    "during adolescence alongside Authorone's framework."
)

_KEPT_BULLET = (
    "Authortwo (1971) and developmental theorists shared the emphasis on "
    "adolescence as the critical period for identity formation."
)
# A 0.8-token twin of _KEPT_BULLET that uniquely names Authorone.
_DUP_UNIQUE_AUTHOR = (
    "Authorone (1970) and Authortwo (1971) shared the emphasis on "
    "adolescence as the critical period for identity formation."
)
# A 0.8-token twin with no uniquely-named author.
_DUP_NO_UNIQUE = (
    "Authortwo (1971) and other theorists shared the emphasis on "
    "adolescence as the critical period for identity formation."
)


def _issues_for(rep, detector: str):
    return [i for i in rep.issues if i.detector == detector]


def test_near_dup_without_unique_author_dropped():
    rep = run_post_checks(
        [_KEPT_BULLET, _DUP_NO_UNIQUE],
        "",
        "",
        source_text=_SOURCE,
    )
    assert rep.bullets == [_KEPT_BULLET]
    drops = [i for i in _issues_for(rep, "near_duplicate") if i.severity == "fix"]
    assert drops, "expected a near_duplicate fix (drop) issue"
    assert "dropped" in drops[0].detail


def test_near_dup_with_unique_source_author_kept():
    """The V0.5.17 veto: the dup bullet uniquely names Authorone (a
    regex-confirmed source author absent from the kept text) → KEPT."""
    rep = run_post_checks(
        [_KEPT_BULLET, _DUP_UNIQUE_AUTHOR],
        "",
        "",
        source_text=_SOURCE,
    )
    assert len(rep.bullets) == 2, f"both bullets must survive: {rep.bullets}"
    vetoes = [i for i in _issues_for(rep, "near_duplicate") if i.severity == "flag"]
    assert vetoes, "expected a near_duplicate flag (V0.5.17 keep-veto) issue"
    assert "Authorone" in vetoes[0].detail
    assert "V0.5.17" in vetoes[0].detail


def test_near_dup_unique_author_covered_elsewhere_dropped():
    """When the author is already covered by the exec/thorough text, the
    dup bullet is still dropped (the veto only rescues LOST coverage)."""
    rep = run_post_checks(
        [_KEPT_BULLET, _DUP_UNIQUE_AUTHOR],
        "Authorone (1970) described identity formation through stages.",
        "",
        source_text=_SOURCE,
    )
    assert rep.bullets == [_KEPT_BULLET]
    assert not [i for i in _issues_for(rep, "near_duplicate") if i.severity == "flag"]


def test_no_source_text_legacy_drop():
    rep = run_post_checks([_KEPT_BULLET, _DUP_NO_UNIQUE], "", "", source_text=None)
    assert rep.bullets == [_KEPT_BULLET]


# A misattributed twin: the source attributes the claim to Authorthree;
# Authorfour appears only as a citation-parenthetical inside Authorthree's
# claim (the parenthetical-promotion pattern). The twin bullet swaps the
# subject name — the V0.5.17 veto must NOT rescue it (preserving a
# misattribution to save an author mention is negative value).
_PROMOTION_SOURCE = (
    "Authorthree did not use the term explicitly, but his work provides "
    "the foundational basis for structural integration and continuity of "
    "the self (Authorfour 1983), according to the developmental account."
)
_PROMOTION_KEPT = (
    "Authorthree provided the foundational basis for structural "
    "integration and the continuity of the self."
)
_PROMOTION_TWIN = (
    "Authorfour's work provides the foundational basis for structural "
    "integration and the continuity of the self."
)


def test_misattributed_twin_not_rescued():
    """V0.5.17 refinement: a CONFIRMED parenthetical promotion stays
    dropped even though it uniquely names a source author."""
    rep = run_post_checks(
        [_PROMOTION_KEPT, _PROMOTION_TWIN],
        "",
        "",
        source_text=_PROMOTION_SOURCE,
    )
    assert rep.bullets == [_PROMOTION_KEPT]
    assert not [i for i in _issues_for(rep, "near_duplicate") if i.severity == "flag"]
