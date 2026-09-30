"""V0.5.18 — the semantic-dedup author-coverage veto (the ch.9 audit's Bug #2).

The V0.5.17 near-duplicate removal has the author-coverage veto (it
rescued two uniquely-named-author bullets on the ch.9 operator run), but
the post-gap-fill SEMANTIC dedup (V18.20.3.2, embeddings, keep-first) did
NOT — on that run it silently dropped two round-4-accepted bullets that
uniquely named source authors (95→87), the same pattern as the V0.5.16
ch.1 loss, one removal layer over.

Behaviour matrix verified here (``summary_validator.semantic_dedup_bullets``
with the new ``source_authors`` / ``context_text`` / ``source_text`` params):

| scenario                                  | expected                    |
|-------------------------------------------|------------------------------|
| sim-twin, no unique author                | DROPPED (legacy behavior)   |
| sim-twin, unique source author            | KEPT (the veto) + INFO log  |
| sim-twin, author covered by context_text  | DROPPED (no coverage lost)  |
| sim-twin, author covered by a LATER bullet| DROPPED (deferred veto sees |
|                                           |  the COMPLETE kept set)     |
| misattributed twin (parenthetical         | DROPPED (the V0.5.17        |
| promotion CONFIRMED)                      |  refinement)                |
| no source_authors supplied                | DROPPED (veto inert)        |

The embedder is faked (deterministic vectors: a crafted twin pair shares
one vector → cos sim 1.0 ≥ threshold; every other string gets a unique
hash-based unit vector) — sentence-transformers is not a test dep.

Content-agnostic (Rule 1): synthetic Authorone/Authortwo fixtures.

Run: ``pytest tests/test_v0518_semantic_dedup_veto.py -v``
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.author_anchor import source_author_surnames
from core.summarisation.summary_validator import semantic_dedup_bullets

# ── the fake embedder ────────────────────────────────────────────────────────


class _FakeEmbedder:
    """Deterministic embedder: every string in the same ``twin_group``
    list shares one vector (cos sim 1.0 ≥ threshold); all other strings
    get unique hash-based unit vectors (mutually near-orthogonal)."""

    def __init__(self, twin_groups: list[list[str]] | None = None):
        self._groups = [list(g) for g in (twin_groups or [])]

    def encode(self, strs, show_progress_bar=False, convert_to_numpy=True):
        import numpy as np

        def _hash_vec(s: str):
            h = hashlib.sha1(s.encode()).digest()
            return [((b - 128) / 128.0) for b in h[:16]]

        # group vectors: one hash vector per GROUP, shared by members
        group_vecs = [_hash_vec(f"__group_{i}__") for i in range(len(self._groups))]

        def _vec_for(s: str):
            for gi, grp in enumerate(self._groups):
                if s in grp:
                    return group_vecs[gi]
            return _hash_vec(s)

        rows = [_vec_for(s) for s in strs]
        arr = np.array(rows, dtype=float)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _install_fake_embedder(monkeypatch, twin_groups=None):
    import core.llm.model_singletons as singletons

    fake = _FakeEmbedder(twin_groups)
    monkeypatch.setattr(singletons, "get_embed_model", lambda: fake)
    monkeypatch.setattr(singletons, "is_embedder_healthy", lambda: True)
    return fake


# ── fixtures ─────────────────────────────────────────────────────────────────

_SOURCE = (
    "Authorone (1970) described how identity formation proceeds through "
    "developmental stages toward a persistent sense of selfsameness.\n"
    "Authortwo (1971) emphasized the consolidation of inner solidarity "
    "during adolescence alongside Authorone's framework."
)

_KEPT = (
    "Authortwo (1971) and developmental theorists shared the emphasis on "
    "adolescence as the critical period for identity formation."
)
# a semantic twin of _KEPT that uniquely names Authorone
_TWIN_UNIQUE = (
    "Authorone (1970) and Authortwo (1971) shared the emphasis on "
    "adolescence as the critical period for identity formation."
)
# a semantic twin with no uniquely-named author
_TWIN_PLAIN = (
    "Authortwo (1971) and other theorists shared the emphasis on "
    "adolescence as the critical period for identity formation."
)
# a non-twin bullet that covers Authorone (for the later-bullet scenario)
_STANDALONE_AUTHORONE = (
    "Authorone (1970) charted developmental stages toward selfsameness with a longitudinal design."
)


def _dedup(monkeypatch, bullets, twin_groups=None, **kwargs):
    log = _CapturingLog()
    _install_fake_embedder(monkeypatch, twin_groups)
    out = semantic_dedup_bullets(bullets, threshold=0.85, log=log, **kwargs)
    return out, log


# ── the matrix ───────────────────────────────────────────────────────────────


def test_plain_twin_still_dropped(monkeypatch):
    """No uniquely-named author → the legacy keep-first drop (veto inert)."""
    out, log = _dedup(
        monkeypatch,
        [_KEPT, _TWIN_PLAIN],
        twin_groups=[[_KEPT, _TWIN_PLAIN]],
        source_authors=source_author_surnames(_SOURCE),
        context_text="",
        source_text=_SOURCE,
    )
    assert out == [_KEPT]
    assert not any("veto" in m.lower() for m, _ in log.calls)


def test_unique_author_twin_kept(monkeypatch):
    """THE V0.5.18 VETO: the twin uniquely names Authorone (a roster author
    absent from the kept text) → KEPT, with the INFO audit line."""
    out, log = _dedup(
        monkeypatch,
        [_KEPT, _TWIN_UNIQUE],
        twin_groups=[[_KEPT, _TWIN_UNIQUE]],
        source_authors=source_author_surnames(_SOURCE),
        context_text="",
        source_text=_SOURCE,
    )
    assert out == [_KEPT, _TWIN_UNIQUE]
    veto_logs = [m for m, lvl in log.calls if "V0.5.18 semantic-dedup veto" in m and lvl == "INFO"]
    assert veto_logs and "Authorone" in veto_logs[0]


def test_author_covered_by_context_text_dropped(monkeypatch):
    """The exec/thorough already names Authorone → the twin loses no
    coverage → still dropped (the veto only rescues LOST coverage)."""
    out, _ = _dedup(
        monkeypatch,
        [_KEPT, _TWIN_UNIQUE],
        twin_groups=[[_KEPT, _TWIN_UNIQUE]],
        source_authors=source_author_surnames(_SOURCE),
        context_text="Authorone (1970) described identity formation through stages.",
        source_text=_SOURCE,
    )
    assert out == [_KEPT]


def test_author_covered_by_later_kept_bullet_dropped(monkeypatch):
    """Deferred-veto semantics: the kept set is evaluated COMPLETE (a
    non-twin bullet LATER in the list covers the author → the twin's
    author is not unique → dropped)."""
    out, _ = _dedup(
        monkeypatch,
        [_KEPT, _TWIN_UNIQUE, _STANDALONE_AUTHORONE],
        twin_groups=[[_KEPT, _TWIN_UNIQUE]],
        source_authors=source_author_surnames(_SOURCE),
        context_text="",
        source_text=_SOURCE,
    )
    assert out == [_KEPT, _STANDALONE_AUTHORONE]
    assert _TWIN_UNIQUE not in out


def test_order_preserved_on_rescue(monkeypatch):
    """A rescued twin re-enters at its ORIGINAL position (order preserved)."""
    out, _ = _dedup(
        monkeypatch,
        [
            _KEPT,
            _TWIN_UNIQUE,
            _STANDALONE_AUTHORONE.replace("Authorone (1970) charted", "Authorx (1970) charted"),
        ],
        twin_groups=[[_KEPT, _TWIN_UNIQUE]],
        source_authors=source_author_surnames(_SOURCE),
        context_text="",
        source_text=_SOURCE,
    )
    # the third bullet names no roster author uniquely… it names Authorx
    # (not a source author) — kept because it is NOT a twin of anything.
    assert out[0] == _KEPT
    assert out[1] == _TWIN_UNIQUE


# The V0.5.17 refinement, applied to this layer: a CONFIRMED parenthetical
# promotion is NOT rescuable (the misattributed twin has negative value).
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


def test_misattributed_twin_not_rescued(monkeypatch):
    out, log = _dedup(
        monkeypatch,
        [_PROMOTION_KEPT, _PROMOTION_TWIN],
        twin_groups=[[_PROMOTION_KEPT, _PROMOTION_TWIN]],
        source_authors=source_author_surnames(_PROMOTION_SOURCE),
        context_text="",
        source_text=_PROMOTION_SOURCE,
    )
    assert out == [_PROMOTION_KEPT]
    assert not any("V0.5.18 semantic-dedup veto: KEPT" in m for m, _ in log.calls)


def test_no_source_authors_veto_inert(monkeypatch):
    """Legacy call shape (no roster): plain keep-first dedup."""
    out, _ = _dedup(monkeypatch, [_KEPT, _TWIN_UNIQUE], twin_groups=[[_KEPT, _TWIN_UNIQUE]])
    assert out == [_KEPT]


def test_embedder_unavailable_returns_unchanged(monkeypatch):
    """Pre-existing fail-open: no embedder → no dedup at all (the V18.2.23
    churn fix), veto params notwithstanding."""
    import core.llm.model_singletons as singletons

    monkeypatch.setattr(singletons, "get_embed_model", lambda: None)
    monkeypatch.setattr(singletons, "is_embedder_healthy", lambda: False)
    out, _ = _dedup(
        monkeypatch,
        [_KEPT, _TWIN_UNIQUE],
        source_authors=source_author_surnames(_SOURCE),
        context_text="",
        source_text=_SOURCE,
    )
    assert out == [_KEPT, _TWIN_UNIQUE]
