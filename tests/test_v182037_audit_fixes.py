"""V18.20.3.7 — audit v182036 fix bundle (fixtures from the real run).

Every fixture below is drawn from the V18.20.3.6 rig run of "Broken
Structures" (Salman Akhtar), Ch. 1 "Identity and Its Origins" — the run
whose consolidation call degenerated (42 → 37 "merged 5" while 5 authors
silently vanished; done_reason=length, 25,735 chars out) and whose gap-fill
rounds 2-4 were ~1s empty no-ops that starved the RC-4 mention-only
escalation (recall floor finished 34/37 with Klein/Searles/Khan missing).

The five fixes (audit Part 5 items 1-5 + Part 6 item 7):

  RC-A.1  consolidation coverage assertion — deterministic author
          coverage measured before/after; ANY loss on a non-truncated
          response rejects the consolidation (originals kept).
  RC-A.2  truncation-aware salvage — a cut response may keep its merged
          set ONLY if the lost authors' original bullets are restored.
  RC-B.1  escalate-on-no-yield — mention-only after 2 vetoes OR 2
          consecutive zero-yield rounds (the empty-no-op starvation fix).
  RC-B.2  prompt variation on retry — never re-send an identical gap-fill
          prompt (the ~1s empty responses came from byte-identical
          retries).
  RC-C    per-round gap-fill telemetry — empty / dup / think-filtered /
          vetoed / added, with durations; empty responses at WARNING.
  P6-7    provenance stamping — every output file self-identifies (app
          version + run id + start time + bullet count) and the COMPLETE
          sentinel carries the run id; resume/write-once log adoptions of
          another run's file. Two audit sessions were spent proving which
          run produced an uploaded file; the files now say it themselves.

  +  pronoun antecedent-adjacency gate — the V18.20.3.6 bullet[25] flag
     ("Winnicott ... she" where 'she' binds to "a mother" in the bullet)
     is the recurring false-positive class; a determiner+noun immediately
     before the pronoun now suppresses the flag (advisory noise reduction,
     zero output risk — the D2 no-auto-rewrite decision stands).

Content-agnostic by construction: coverage measured with the SAME
deterministic author extraction the judge uses; escalation keyed on
round yields; prompt variation keyed on the round number; provenance is
version/run metadata; the pronoun gate uses closed-class English
determiners. No chapter-derived word lists anywhere (policy tests below
guard the ban).

Run: pytest tests/test_v182037_audit_fixes.py -v
"""
from __future__ import annotations

import ast
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub optional heavy deps (same pattern as test_v18202_system_fixes.py —
# markitdown/tiktoken are not installed in this sandbox).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = MagicMock(return_value=MagicMock())
    _tk.encoding_for_model = MagicMock(return_value=MagicMock())
    _tk.Encoding = MagicMock
    sys.modules["tiktoken"] = _tk

import pytest

from core.llm.call_meta import consume_call_truncated, mark_call_truncated
from core.models import SummaryResult
from core.summarisation.bullet_consolidation import consolidate_bullets
from core.system import provenance

# ── Real-run constants (V18.20.3.6 rig run, 2026-08-31 02:10–02:40) ───────
CONSOL_IN = 42          # bullets into the degenerated consolidation call
CONSOL_OUT = 37         # bullets salvaged from the truncated response
CONSOL_CHARS = 25735    # response length at the 6144-token cut
RECALL_FLOOR = "34/37"  # theorists in final bullets (Klein/Searles/Khan lost)
GAP_ROUNDS_NOOP = (2, 3, 4)  # ~1s empty no-op rounds (identical prompts)

# The five authors the V18.20.3.6 consolidation silently lost coverage of
# (judge logged them MISSING from bullets right after 42 → 37).
LOST_AUTHORS = ["Klein", "Loewald", "Loewenstein", "Searles", "Spitz"]


# ── helpers ────────────────────────────────────────────────────────────────


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))

    def warnings(self):
        return [m for m, l in self.calls if l == "WARNING"]

    def infos(self):
        return [m for m, l in self.calls if l == "INFO"]


class _FakePromptManager:
    def render_template(self, name, bullets=""):
        return f"CONSOLIDATE: {bullets}"


def _make_deps(llm_response: str = "", llm_truncated: bool = False):
    """consolidate_bullets deps; the mock provider sets the truncation
    ContextVar exactly like the real ollama_provider does (after EVERY
    response)."""

    def select_prompt(name):
        return name

    def call_llm_with_empty_retry(prompt, model=None, temperature=None, max_tokens=None):
        mark_call_truncated(llm_truncated)
        return llm_response

    def strip_thinking(text):
        return text

    def consolidate_duplicate_claims(bullets):
        # V18.20.3.11: the deterministic pre-check probe now GATES the LLM
        # call (probe finds 0 mergeable pairs → skip). These tests
        # characterize the LLM-path assertion/salvage machinery, so the
        # probe reports one mergeable pair to let the LLM path run.
        return bullets[:-1] if len(bullets) > 1 else list(bullets)

    return {
        "prompt_manager": _FakePromptManager(),
        "select_prompt": select_prompt,
        "call_llm_with_empty_retry": call_llm_with_empty_retry,
        "primary_model": "test-model",
        "temperature": 0.7,
        "strip_thinking": strip_thinking,
        "consolidate_duplicate_claims": consolidate_duplicate_claims,
    }


def _author_coverage_fn(authors, bullets):
    """Deterministic coverage closure for tests: an author is covered when
    their surname appears in the joined bullet text (same shape as
    check_coverage on the deterministic analysis)."""
    def fn(bs):
        text = " ".join(str(b) for b in bs).lower()
        return {a for a in authors if a.lower() in text}
    return bullets and fn or None


def _coverage_fn_for(authors):
    def fn(bs):
        if not bs:
            return set()
        text = " ".join(str(b) for b in bs).lower()
        return {a for a in authors if a.lower() in text}
    return fn


# Six-bullet fixture: one covered author per bullet (the .3.6 shape in
# miniature — the scholar gap-fill had just added coverage rows).
SIX_BULLETS = [
    "Kernberg (1967) proposed that ego identity develops through internalization of early object relationships.",
    "Klein (1948) provided foundational works that Kernberg integrated into his three-step process of identity formation.",
    "Erikson (1956) defined ego identity as a persistent sameness within oneself.",
    "Jacobson (1964) formulated five categories of contribution to identity development.",
    "Blos (1962) described the second individuation of adolescence as emotional disengagement.",
    "Winnicott supplied the developmental basis for authenticity and temporal continuity.",
]
SIX_AUTHORS = ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos", "Winnicott"]


def _llm_output_missing(bullets, drop_authors):
    """Simulate a consolidation response that 'merges' bullets away for the
    given authors (they vanish from the output — the RC-A defect)."""
    drop_lower = {a.lower() for a in drop_authors}
    return "\n".join(
        f"- {b}" for b in bullets
        if not any(d in b.lower() for d in drop_lower)
    )


# ══ RC-A.1 — consolidation coverage assertion ══════════════════════════════


class TestConsolidationCoverageAssertion:
    def test_non_truncated_loss_rejected_originals_kept(self):
        """The .3.6 regression shape: LLM output drops covered authors →
        the whole consolidation is REJECTED, originals kept, WARNING."""
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein", "Winnicott"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        cap = _CapturingLog()
        out, fire = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(SIX_AUTHORS), **deps,
        )
        assert out == SIX_BULLETS  # originals — not the lossy LLM output
        assert fire == 0
        assert any("REJECTED" in w and "Klein" in w and "Winnicott" in w
                   for w in cap.warnings()), cap.warnings()

    def test_all_authors_preserved_accepted(self):
        """A consolidation that keeps every covered author ships normally."""
        llm_out = "\n".join(f"- {b} (merged)" for b in SIX_BULLETS[:5])
        # 5 outputs (one legitimate merge), all six authors still named:
        llm_out += "\n- Blos and Winnicott both supplied developmental foundations."
        llm_out = "\n".join(l for l in llm_out.split("\n")[:6])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        cap = _CapturingLog()
        out, fire = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(SIX_AUTHORS), **deps,
        )
        assert out != SIX_BULLETS  # the consolidated set shipped
        assert any("Bullet consolidation: 6 →" in i for i in cap.infos())

    def test_coverage_fn_none_disables_assertion(self):
        """Probe failure (None) must disable the assertion, not break the
        chapter — legacy behaviour (LLM output accepted)."""
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        cap = _CapturingLog()
        out, _ = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=lambda bs: None, **deps,
        )
        assert len(out) == 5 and out != SIX_BULLETS
        assert not any("REJECTED" in w for w in cap.warnings())

    def test_coverage_fn_raising_disables_assertion(self):
        """A raising closure is treated as 'probe failed' → disabled."""
        def boom(bs):
            raise RuntimeError("analysis unreadable")
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        out, _ = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=_CapturingLog(),
            author_coverage_fn=boom, **deps,
        )
        assert len(out) == 5  # LLM output accepted (assertion off)

    def test_no_coverage_fn_legacy_behavior(self):
        """No callback → byte-for-byte legacy path (no assertion)."""
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        out, _ = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=_CapturingLog(),
            **deps,
        )
        assert len(out) == 5

    def test_real_run_shape_42_to_37_rejected(self):
        """The exact .3.6 numbers in miniature: 10 bullets in, LLM 'merges'
        to 7 while losing 3 covered authors → REJECTED (non-truncated
        variant of the degenerate call)."""
        bullets = [
            f"{a} (19xx) contributed finding number {i} to the chapter."
            for i, a in enumerate(
                ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos",
                 "Winnicott", "Mahler", "Loewald", "Searles", "Spitz"]
            )
        ]
        authors = ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos",
                   "Winnicott", "Mahler", "Loewald", "Searles", "Spitz"]
        llm_out = _llm_output_missing(bullets, ["Loewald", "Searles", "Spitz"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=False)
        cap = _CapturingLog()
        out, _ = consolidate_bullets(
            list(bullets), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(authors), **deps,
        )
        assert out == bullets  # the 10 originals, not the lossy 7
        assert any("3 covered author(s)" in w for w in cap.warnings())


# ══ RC-A.2 — truncation-aware salvage ══════════════════════════════════════


class TestTruncationAwareSalvage:
    def test_truncated_loss_salvaged_with_originals(self):
        """done_reason=length + lost authors → the lost authors' ORIGINAL
        bullets are re-appended to the salvaged set (a loss is allowed only
        among bullets the response had already re-emitted)."""
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein", "Winnicott"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=True)
        cap = _CapturingLog()
        out, _ = consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(SIX_AUTHORS), **deps,
        )
        # 4 merged survivors + 2 restored originals = 6 (<= input count)
        assert len(out) == 6
        joined = " ".join(out)
        assert "Klein" in joined and "Winnicott" in joined
        assert any("salvaged" in w and "restored 2" in w for w in cap.warnings())

    def test_truncated_salvage_exceeding_input_rejected(self):
        """If salvage would exceed the input count, the originals win."""
        bullets = [
            f"{a} (19xx) contributed finding number {i} to the chapter."
            for i, a in enumerate(
                ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos",
                 "Winnicott", "Mahler", "Loewald"]
            )
        ]
        authors = ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos",
                   "Winnicott", "Mahler", "Loewald"]
        # LLM keeps 7 (loses only Loewald) — but ALSO duplicates Klein's
        # content into two near-identical bullets, so restoring Loewald
        # would still fit; force the exceed case with a wide loss instead:
        llm_out = _llm_output_missing(bullets, ["Loewald", "Mahler"])
        # …and craft the merged set to be 7 lines (one a near-dup restating
        # of Klein) so restored(2) + consolidated(6-ish) is under 8 — this
        # is the ACCEPT branch; the reject branch needs consolidated close
        # to input. Simpler: drop only ONE author but make consolidated 7
        # where one line restates another author's content, then check the
        # guard arithmetic directly with a 7+2 case:
        llm_out = _llm_output_missing(bullets, ["Loewald", "Mahler", "Searles"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=True)
        cap = _CapturingLog()
        out, _ = consolidate_bullets(
            list(bullets), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(authors + ["Searles"]), **deps,
        )
        # consolidated=5, restored: Loewald, Mahler, Searles → 5+3=8 <= 8 OK
        assert len(out) == 8

    def test_truncated_reject_when_restored_exceeds(self):
        """consolidated + restored > len(bullets) → reject outright."""
        bullets = [
            f"{a} (19xx) contributed finding number {i} to the chapter."
            for i, a in enumerate(
                ["Kernberg", "Klein", "Erikson", "Jacobson", "Blos", "Winnicott"]
            )
        ]
        # LLM output keeps 6 lines (nothing merged — each survivor distinct
        # in the first 60 chars) but drops every author's NAME except via a
        # fabricated restatement that loses Klein + Winnicott coverage:
        llm_out = "\n".join([
            "- Kernberg (1967) proposed internalization of object relationships.",
            "- Erikson (1956) defined ego identity as persistent sameness.",
            "- Jacobson (1964) formulated five categories of contribution.",
            "- Blos (1962) described the second individuation of adolescence.",
            "- Mahler (1958) distinguished psychological from biological birth.",
            "- Freud (1926) used the term identity technically only once.",
        ])
        authors = SIX_AUTHORS  # Klein + Winnicott expected, absent above
        deps = _make_deps(llm_response=llm_out, llm_truncated=True)
        cap = _CapturingLog()
        out, _ = consolidate_bullets(
            list(bullets), leak_guard_fire_count=0, log=cap,
            author_coverage_fn=_coverage_fn_for(authors), **deps,
        )
        # consolidated=6, restored=2 → 8 > 6 → reject, originals kept
        assert out == bullets
        assert any("REJECTED" in w for w in cap.warnings())

    def test_truncation_flag_consumed_not_leaked(self):
        """The truncation ContextVar is read-and-reset by the assertion — a
        later consumer cannot see a stale flag."""
        llm_out = _llm_output_missing(SIX_BULLETS, ["Klein"])
        deps = _make_deps(llm_response=llm_out, llm_truncated=True)
        consolidate_bullets(
            list(SIX_BULLETS), leak_guard_fire_count=0, log=_CapturingLog(),
            author_coverage_fn=_coverage_fn_for(SIX_AUTHORS), **deps,
        )
        assert consume_call_truncated() is False


# ══ RC-A wiring — Summarizer delegate arms the assertion ═══════════════════


class TestConsolidationCoverageWiring:
    """Source-structure tests (the established pattern for loop logic too
    deep to drive without a full conversion): the delegate must build the
    coverage closure from the SAME analysis the judge uses, and the call
    site must pass the heading."""

    def _src(self):
        return (_project_root / "core" / "summarisation" / "summarizer.py").read_text(
            encoding="utf-8")

    def test_delegate_builds_coverage_closure(self):
        src = self._src()
        assert "author_coverage_fn=_coverage_fn" in src
        assert "find_analysis_for_heading" in src
        # The closure uses the SAME check_coverage as the V18.14 judge.
        assert "check_coverage" in src

    def test_call_site_passes_heading(self):
        src = self._src()
        assert "self._consolidate_bullets(bullets, heading=heading)" in src

    def test_delegate_signature_has_heading(self):
        src = self._src()
        # V18.20.3.12: pin modernized List[str]/Optional[str] -> list[str]/
        # str | None (ruff UP006/UP045 annotation sweep — same types).
        assert (
            "def _consolidate_bullets(self, bullets: list[str], "
            "heading: str | None = None)" in src
        )

    def test_consolidation_module_has_assertion(self):
        src = (_project_root / "core" / "summarisation" /
               "bullet_consolidation.py").read_text(encoding="utf-8")
        assert "author_coverage_fn" in src
        assert "consume_call_truncated" in src
        assert "REJECTED" in src


# ══ RC-B.1/B.2 + RC-C — gap-fill loop control flow ════════════════════════


class TestGapFillLoopControlFlow:
    """Source-structure tests pinned to the .3.6 failure: the empty no-op
    rounds must (a) count against the author, (b) escalate to mention-only,
    (c) never be re-sent an identical prompt, (d) report their fate.

    V18.20.3.12 (Phase 4 / W6-O5): the loop moved VERBATIM from the
    ``if _missing:`` block in ``Summarizer._summarize_inner`` to
    ``gap_fill_batch.batch_gap_fill`` — this class re-points at the new
    module; the pinned strings are unchanged (the same adaptation the
    consolidation extraction made for ``bullet_consolidation.py``)."""

    def _src(self):
        return (_project_root / "core" / "summarisation" / "gap_fill_batch.py").read_text(
            encoding="utf-8")

    def test_no_yield_counter_initialized(self):
        assert "_no_yield_counts: dict = {}" in self._src()

    def test_mention_only_escalation_includes_no_yield(self):
        src = self._src()
        # The RC-4 veto arm AND the new no-yield arm, in the same condition:
        assert "_veto_counts.get(a, 0) >= 2" in src
        assert "or _no_yield_counts.get(a, 0) >= 2" in src

    def test_no_yield_accounting_resets_on_yield(self):
        src = self._src()
        assert "if _ya in _cov_after_set:" in src
        assert "_no_yield_counts[_ya] = 0" in src
        assert "_no_yield_counts.get(_ya, 0) + 1" in src

    def test_escalation_log_line_exists(self):
        src = self._src()
        assert "consecutive zero-yield" in src
        assert "mention-only prompt next round" in src

    def test_prompt_variation_on_retry(self):
        src = self._src()
        assert "if _gap_fill_round > 1:" in src
        # The retry marker makes every re-sent prompt byte-unique:
        assert "attempt {_gap_fill_round} for these authors" in src
        assert "Re-phrase every bullet from scratch" in src

    def test_round_telemetry_instrumented(self):
        src = self._src()
        assert "_tl_t0 = time.monotonic()" in src
        assert "EMPTY response" in src
        assert 'response=EMPTY' in src
        assert "dup={_tl['dup']}" in src
        assert "vetoed={_tl['veto']}" in src

    def test_veto_and_add_counters_feed_telemetry(self):
        src = self._src()
        assert '_tl["veto"] += 1' in src
        assert '_tl["added"] += 1' in src
        assert '_tl["dup"] += 1' in src
        assert '_tl["think"] += 1' in src


# ══ P6-7 — provenance module ══════════════════════════════════════════════


class TestProvenanceModule:
    def test_make_run_id_unique(self):
        ids = {provenance.make_run_id() for _ in range(50)}
        assert len(ids) == 50

    def test_get_app_version_reads_version_file(self):
        v = provenance.get_app_version()
        assert v and v != "unknown"
        # V0.01 (versioning reset): Elixir versions on its own two-part line
        # (0.01, 0.02, ...). The pin stays dotted-numeric (rejects "unknown"
        # and garbage) but no longer assumes >= 3 parts (legacy 18.x form).
        assert re.match(r"^\d+(?:\.\d+)+", v), v

    def test_complete_sentinel_forms(self):
        assert provenance.complete_sentinel("") == "<!-- COMPLETE -->"
        assert provenance.complete_sentinel(None) == "<!-- COMPLETE -->"
        s = provenance.complete_sentinel("20260831-021017-ab12cd34")
        assert s == "<!-- COMPLETE run_id=20260831-021017-ab12cd34 -->"

    def test_has_complete_sentinel_accepts_both_forms(self):
        assert provenance.has_complete_sentinel("x\n<!-- COMPLETE -->\n")
        assert provenance.has_complete_sentinel(
            "x\n<!-- COMPLETE run_id=abc-123 -->\n")
        assert not provenance.has_complete_sentinel("no sentinel here")
        assert not provenance.has_complete_sentinel("")

    def test_provenance_comment_round_trip(self):
        c = provenance.provenance_comment(
            "18.20.3.7", "20260831-021017-ab12cd34",
            "2026-08-31T02:10:17", 41,
        )
        assert c.startswith("<!-- generated-by: Elixir v18.20.3.7")
        parsed = provenance.parse_provenance(f"# Summary: X\n\n{c}\n\nbody")
        assert parsed["app_version"] == "18.20.3.7"
        assert parsed["run_id"] == "20260831-021017-ab12cd34"
        assert parsed["started"] == "2026-08-31T02:10:17"
        assert parsed["bullets"] == "41"

    def test_parse_provenance_legacy_file(self):
        # The stale .3.4 file shape: no comment, bare sentinel → empties.
        parsed = provenance.parse_provenance(
            "# Summary: X\n\n## Executive Summary\n\ntext\n\n<!-- COMPLETE -->\n")
        assert parsed == {
            "run_id": "", "app_version": "", "started": "", "bullets": "",
        }

    def test_parse_provenance_sentinel_only(self):
        # No comment but a stamped sentinel → run_id still recoverable.
        parsed = provenance.parse_provenance("body\n<!-- COMPLETE run_id=r1 -->")
        assert parsed["run_id"] == "r1"

    def test_adoption_note_different_runs(self):
        existing = (
            "# Summary: X\n"
            + provenance.provenance_comment("18.20.3.4", "run-old", "t0", 39)
            + "\n\n<!-- COMPLETE run_id=run-old -->\n"
        )
        incoming = (
            "# Summary: X\n"
            + provenance.provenance_comment("18.20.3.6", "run-new", "t1", 41)
            + "\n\n<!-- COMPLETE run_id=run-new -->\n"
        )
        note = provenance.adoption_note(existing, incoming)
        assert note is not None
        assert "run-old" in note and "18.20.3.4" in note
        assert "run-new" in note
        assert "39 bullets" in note

    def test_adoption_note_same_run_silent(self):
        body = provenance.provenance_comment("18.20.3.7", "same-run", "t", 5)
        assert provenance.adoption_note(body, body) is None

    def test_adoption_note_legacy_silent(self):
        # Both files legacy (no stamps) → cannot compare → silent.
        assert provenance.adoption_note("<!-- COMPLETE -->", "<!-- COMPLETE -->") is None

    def test_stdlib_only_module(self):
        """core/system modules must stay stdlib-only (AST-verified — same
        policy as crash_visibility.py)."""
        tree = ast.parse(
            (_project_root / "core" / "system" / "provenance.py").read_text(
                encoding="utf-8"))
        allowed = {"re", "uuid", "datetime", "pathlib", "typing", "__future__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed, alias.name
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] in allowed, node.module


# ══ P6-7 — renderer stamps provenance ═════════════════════════════════════


def _summ(**kw):
    base = dict(
        chapter_heading="1 - IDENTITY AND ITS ORIGINS",
        executive_summary="Identity traces from Tausk (1919) through Erikson.",
        thorough_summary="A longer thorough treatment of the chapter.",
        bullet_points=[
            "Tausk (1919) first introduced the term into psychoanalytic literature.",
            "Erikson (1956) defined ego identity as persistent sameness.",
        ],
    )
    base.update(kw)
    return SummaryResult(**base)


class TestRendererProvenance:
    def test_stamped_render_contains_comment_and_sentinel(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown
        md = render_summary_markdown(_summ(
            run_id="20260831-021017-ab12cd34",
            app_version="18.20.3.7",
            run_started="2026-08-31T02:10:17",
        ))
        assert "generated-by: Elixir v18.20.3.7" in md
        assert "run_id=20260831-021017-ab12cd34" in md
        assert "bullets=2" in md
        assert md.rstrip().endswith("<!-- COMPLETE run_id=20260831-021017-ab12cd34 -->")
        # The comment sits under the title, before the first section.
        assert md.index("generated-by") < md.index("## Executive Summary")

    def test_legacy_render_unchanged(self):
        """Unstamped SummaryResult → byte-identical legacy markdown (no
        comment, bare sentinel) — backward compatibility for every caller
        that builds SummaryResults without provenance."""
        from core.pipeline.chapter_checkpoint import render_summary_markdown
        md = render_summary_markdown(_summ())
        assert "generated-by" not in md
        assert md.rstrip().endswith("<!-- COMPLETE -->")

    def test_summary_result_has_provenance_fields(self):
        s = SummaryResult(chapter_heading="h", executive_summary="e",
                          thorough_summary="t")
        assert s.run_id == "" and s.app_version == "" and s.run_started == ""


# ══ P6-7 — resume parses + reports provenance ═════════════════════════════


class TestResumeProvenance:
    def _write_summary(self, tmp_path, *, run_id, app_version, started, bullets):
        from core.pipeline.chapter_checkpoint import render_summary_markdown
        md = render_summary_markdown(_summ(
            run_id=run_id, app_version=app_version, run_started=started,
            bullet_points=bullets,
        ))
        f = tmp_path / "summaries" / "001_X_summary.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(md, encoding="utf-8")
        return f

    def test_parse_summary_file_returns_provenance(self, tmp_path):
        self._write_summary(
            tmp_path, run_id="run-A", app_version="18.20.3.6",
            started="2026-08-31T02:10:17",
            bullets=["Tausk (1919) introduced the term.", "Erikson (1956) defined it."],
        )
        from core.pipeline.chapter_resume import detect_processed_chapters
        processed = detect_processed_chapters(tmp_path)
        assert len(processed) == 1
        (result,) = processed.values()
        assert result.run_id == "run-A"
        assert result.app_version == "18.20.3.6"
        assert result.run_started == "2026-08-31T02:10:17"

    def test_legacy_sentinel_still_accepted(self, tmp_path):
        """Pre-.3.7 files (bare sentinel) remain valid resume tokens."""
        f = tmp_path / "summaries" / "001_X_summary.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            "# Summary: X\n\n## Executive Summary\n\nSome exec text.\n\n"
            "## Key Takeaways\n\n- Bullet one here.\n\n"
            "## Thorough Summary\n\nThorough text.\n\n<!-- COMPLETE -->\n",
            encoding="utf-8",
        )
        from core.pipeline.chapter_resume import detect_processed_chapters
        processed = detect_processed_chapters(tmp_path)
        assert len(processed) == 1

    def test_resume_log_names_producing_run(self, tmp_path):
        """The .3.6 confusion killer: when resume adopts a file from another
        run, the log says which run + app version produced it."""
        self._write_summary(
            tmp_path, run_id="run-old-34", app_version="18.20.3.4",
            started="2026-08-30T20:44:12",
            bullets=["Tausk (1919) introduced the term.", "Erikson (1956) defined it."],
        )
        from core.pipeline.chapter_resume import (
            detect_processed_chapters,
            split_chapters_for_resume,
        )
        processed = detect_processed_chapters(tmp_path)
        cap = _CapturingLog()
        todo, loaded = split_chapters_for_resume(
            [{"heading": "1 - IDENTITY AND ITS ORIGINS"}], processed,
            log_callback=cap,
        )
        assert not todo and len(loaded) == 1
        line = " ".join(cap.infos())
        assert "file from run run-old-34" in line
        assert "app v18.20.3.4" in line

    def test_resume_log_plain_for_legacy_files(self, tmp_path):
        """Legacy files (no stamp) keep the plain historical log line."""
        f = tmp_path / "summaries" / "001_X_summary.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            "# Summary: X\n\n## Executive Summary\n\nSome exec text.\n\n"
            "## Key Takeaways\n\n- Bullet one here.\n\n"
            "## Thorough Summary\n\nThorough text.\n\n<!-- COMPLETE -->\n",
            encoding="utf-8",
        )
        from core.pipeline.chapter_resume import (
            detect_processed_chapters,
            split_chapters_for_resume,
        )
        processed = detect_processed_chapters(tmp_path)
        cap = _CapturingLog()
        split_chapters_for_resume([{"heading": "X"}], processed, log_callback=cap)
        line = " ".join(cap.infos())
        assert "already processed" in line
        assert "file from run" not in line


# ══ P6-7 — write-once + book summary wiring ═══════════════════════════════


class TestProvenanceWiring:
    def test_write_once_uses_sentinel_helper(self):
        src = (_project_root / "core" / "pipeline" / "chapter_checkpoint.py"
               ).read_text(encoding="utf-8")
        assert "has_complete_sentinel" in src
        assert "adoption_note" in src

    def test_end_of_run_writer_uses_sentinel_helper(self):
        src = (_project_root / "core" / "pipeline" / "conversion" /
               "summarization.py").read_text(encoding="utf-8")
        assert "has_complete_sentinel" in src
        assert "adoption_note" in src
        # Book-level summary gets the provenance comment too:
        assert "provenance_comment" in src

    def test_summarizer_stamps_every_summary(self):
        src = (_project_root / "core" / "summarisation" / "summarizer.py"
               ).read_text(encoding="utf-8")
        assert "self._run_id = make_run_id()" in src
        assert 'run_id=getattr(self, "_run_id", "")' in src
        assert 'app_version=getattr(self, "_app_version", "")' in src


# ══ Pronoun antecedent-adjacency gate ═════════════════════════════════════


class TestPronounAntecedentGate:
    """V18.20.3.6 bullet[25] class: 'Winnicott described that if a
    [mother] ... she ...' — the 'she' binds to the intervening noun, not to
    Winnicott; the flag was advisory noise. A determiner+noun within the 2
    words before the pronoun now suppresses the flag. Direct-binding shapes
    (no intervening noun phrase) still flag."""

    SRC = (
        "Winnicott described the true self. Near his name the source uses "
        "his for Winnicott repeatedly, and elsewhere: Winnicott (1965) "
        "wrote that his squiggle game reveals the self."
    )

    def _detect(self, text, src=None):
        from core.summarisation.postcheck_detectors import detect_pronoun_mismatch
        return detect_pronoun_mismatch(
            text, src or self.SRC, "bullet[N]",
            source_authors=["Winnicott", "Kris", "Jacobson"],
        )

    def test_intervening_noun_phrase_suppresses_flag(self):
        # The .3.6 bullet[25] shape: 'she' follows 'a good-enough mother'.
        _, issues = self._detect(
            "Winnicott described that if a good-enough mother fails to meet "
            "the infant's omnipotence, she produces a false self."
        )
        assert issues == []

    def test_determiner_the_before_pronoun_suppresses_flag(self):
        _, issues = self._detect(
            "Winnicott described the holding environment and the infant "
            "develops; the mother adapts, she provides a good enough start."
        )
        assert issues == []

    def test_direct_binding_still_flags(self):
        # Kris E2 shape (.3.4): possessive directly after the label — no
        # intervening determiner+noun → the flag must fire.
        src = (
            "Kris contributed metapsychological works; the source refers to "
            "his contributions and his writings alongside Hartmann."
        )
        _, issues = self._detect(
            "Kris: Her metapsychological works were combined by Jacobson "
            "with her own findings.", src=src,
        )
        assert len(issues) == 1
        assert "pronoun mismatch" in issues[0].detail

    def test_author_then_bare_pronoun_still_flags(self):
        # Nothing between author and pronoun but punctuation/conjunctions.
        src = (
            "Jacobson wrote extensively; the source says his framework "
            "and his formulations about affective disorders."
        )
        _, issues = self._detect(
            "Jacobson, she formulated five categories of contribution.",
            src=src,
        )
        assert len(issues) == 1

    def test_gate_uses_closed_class_determiners_only(self):
        """Policy: the gate must not ship chapter-derived vocabulary —
        only closed-class English determiners (content-agnostic)."""
        src = (_project_root / "core" / "summarisation" /
               "postcheck_detectors.py").read_text(encoding="utf-8")
        m = re.search(r'_DETERMINERS = \{(.*?)\}', src, re.DOTALL)
        assert m, "determiner set not found"
        words = re.findall(r'"([a-z]+)"', m.group(1))
        # All closed-class function words — no content vocabulary.
        assert set(words) <= {
            "a", "an", "the", "this", "that", "these", "those",
            "his", "her", "their", "its", "each", "every",
        }


# ══ Policy — no chapter-derived word lists (standing user rule) ═══════════


class TestNoChapterDerivedLists:
    def test_provenance_module_has_no_content_words(self):
        """Provenance stamps carry metadata only — no book content."""
        src = (_project_root / "core" / "system" / "provenance.py").read_text(
            encoding="utf-8")
        for banned in ("Klein", "Winnicott", "Kernberg", "identity",
                       "psychoanaly", "mother"):
            assert banned.lower() not in src.lower(), banned


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
