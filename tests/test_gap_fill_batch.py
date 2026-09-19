"""V18.20.3.12 (Phase 4 / W6-O5) — gap_fill_batch characterization tests.

Byte-for-byte stability gate for ``batch_gap_fill`` extracted verbatim from
the ``if _missing:`` V18.14.1 batch gap-fill block of
``Summarizer._summarize_inner``. Uses hermetic stubs (capturing log, canned
fast-LLM responses, identity thinking filters, deterministic
``check_coverage``) — no LLM, no embedder, no markitdown. The REAL
``detect_parenthetical_promotion`` veto runs (it is deterministic and
hermetic); the fixtures were verified against it directly.

Run: pytest tests/test_gap_fill_batch.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like tests/test_thorough_fallback.py
# (tiktoken for the core.summarisation import chain) and
# tests/test_v18203_incremental_checkpoint.py (markitdown, defensively).
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = lambda *a, **k: None
    sys.modules["markitdown"] = _md

from core.summarisation.gap_fill_batch import (  # noqa: E402 — after the sys.modules stubs, like test_thorough_fallback.py
    GapFillOutcome,
    batch_gap_fill,
)


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _make_deps(*, responses=None, response_fn=None):
    """Build hermetic deps.

    ``responses`` is a list of canned fast-LLM responses (None-padded);
    ``response_fn(prompt, call_idx)`` overrides for dynamic responses.
    ``check_coverage`` is the deterministic stub: an author is covered iff
    its name appears in the joined bullets text (mirrors the real
    deterministic_analyzer.check_coverage contract:
    (analysis, text) -> {covered, missing, total, coverage_pct}).
    """
    log = _CapturingLog()
    llm_calls = []

    def check_coverage(analysis, text):
        text = text or ""
        covered = [a for a in analysis["authors"] if a in text]
        missing = [a for a in analysis["authors"] if a not in text]
        total = len(analysis["authors"])
        pct = (len(covered) / total) if total else 0.0
        return {"covered": covered, "missing": missing, "total": total, "coverage_pct": pct}

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
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
        "call_fast_llm": call_fast_llm,
        "strip_thinking": strip_thinking,
        "filter_thinking_bullets": filter_thinking_bullets,
        "llm_calls": llm_calls,
    }


def _run(deps, *, content, bullets, missing, analysis, det_authors, heading="Chapter 1 — Identity"):
    return batch_gap_fill(
        heading,
        content,
        bullets,
        missing,
        analysis,
        det_authors,
        check_coverage=deps["check_coverage"],
        call_fast_llm=deps["call_fast_llm"],
        temperature=0.2,
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=deps["filter_thinking_bullets"],
        log=deps["log"],
    )


def _infos(deps):
    return [m for m, lvl in deps["log"].calls if lvl == "INFO"]


def _warnings(deps):
    return [m for m, lvl in deps["log"].calls if lvl == "WARNING"]


def _debugs(deps):
    return [m for m, lvl in deps["log"].calls if lvl == "DEBUG"]


# ── 1. happy path: bullet added for the missing author ────────────────────


class TestHappyPath:
    def test_bullet_added_for_missing_author(self):
        """The LLM returns a correctly-attributed source bullet → it is
        appended to ``bullets`` (in-place mutation), coverage re-check
        clears the author, and the loop exits after round 1."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        deps = _make_deps(
            responses=["- AuthorA established the framework of identity consolidation."]
        )
        bullets = ["An existing bullet about the chapter."]
        out = _run(
            deps,
            content=src,
            bullets=bullets,
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
        )
        assert isinstance(out, GapFillOutcome)
        assert out.total_added == 1
        assert out.rounds == 1
        assert out.still_missing == []
        assert out.given_up == set()
        # bullets list MUTATED in place (the house in-place contract):
        assert len(bullets) == 2
        assert "AuthorA established the framework" in bullets[1]
        # Exactly one LLM round was needed.
        assert len(deps["llm_calls"]) == 1

    def test_round_and_complete_logs_fire(self):
        """Log parity: the round-added INFO and the final complete INFO."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        deps = _make_deps(
            responses=["- AuthorA established the framework of identity consolidation."]
        )
        _run(
            deps,
            content=src,
            bullets=["Existing bullet."],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
        )
        infos = _infos(deps)
        assert any("Batch gap-fill round 1 added 1/1 bullets" in m for m in infos)
        assert any(
            "Batch gap-fill complete — added 1 bullets across 1 round(s)" in m for m in infos
        )
        # No final WARNING (nothing still missing).
        assert not any("still missing" in w for w in _warnings(deps))

    def test_prompt_carries_heading_and_context(self):
        """The batch prompt embeds the chapter heading and the author's
        source excerpt (the '### AuthorA' context block)."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        deps = _make_deps(
            responses=["- AuthorA established the framework of identity consolidation."]
        )
        _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
            heading="Chapter 7 — The Framework",
        )
        prompt = deps["llm_calls"][0]["prompt"]
        assert "Chapter 7 — The Framework" in prompt
        assert "### AuthorA" in prompt
        assert "identity consolidation" in prompt

    def test_duplicate_bullet_not_re_added(self):
        """A bullet whose normalized 60-char prefix already exists in
        ``bullets`` is counted as dup and skipped (no crash, no add) — and
        because the existing bullet already names the author, the coverage
        re-check clears it and the loop exits after round 1."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        dup = "- AuthorA established the framework of identity consolidation."
        deps = _make_deps(responses=[dup])  # identical to what's already there
        bullets = [dup]
        out = _run(
            deps,
            content=src,
            bullets=bullets,
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
        )
        assert out.total_added == 0
        assert len(bullets) == 1  # unchanged — the dup was not re-added
        assert out.rounds == 1
        assert out.still_missing == []  # covered by the pre-existing bullet
        # The round telemetry counts the dup (DEBUG).
        debugs = [m for m, lvl in deps["log"].calls if lvl == "DEBUG"]
        assert any("dup=1" in m for m in debugs)
        # No final WARNING (nothing still missing).
        assert not any("still missing" in w for w in _warnings(deps))


# ── 2. empty LLM response path ────────────────────────────────────────────


class TestEmptyResponse:
    def test_empty_response_no_bullets_no_crash(self):
        """LLM returns None → the EMPTY-response WARNING + response=EMPTY
        telemetry fire, no bullets are added, no crash; the no-yield
        escalation then drives mention-only → give-up → loop break."""
        src = "AuthorB established the framework, drawing on AuthorA (1948)."
        deps = _make_deps(responses=[None, None, None])
        bullets = ["An existing bullet."]
        out = _run(
            deps,
            content=src,
            bullets=bullets,
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA", "AuthorB"],
        )
        assert out.total_added == 0
        assert len(bullets) == 1  # unchanged
        assert out.still_missing == ["AuthorA"]
        warnings = _warnings(deps)
        assert any("EMPTY response" in w for w in warnings)
        # Telemetry line for the empty round (DEBUG).
        debugs = [m for m, lvl in deps["log"].calls if lvl == "DEBUG"]
        assert any("response=EMPTY" in m for m in debugs)
        # 3 LLM rounds (round 4 breaks on the empty actionable pool).
        assert len(deps["llm_calls"]) == 3
        assert out.rounds == 4  # round 4 = the "no actionable authors" break

    def test_empty_response_round_telemetry_countable(self):
        """Every round is countable in the log: the empty round emits BOTH
        the WARNING (emptiness) and the DEBUG telemetry line."""
        src = "AuthorB established the framework, drawing on AuthorA (1948)."
        deps = _make_deps(responses=[None])
        _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
        )
        # Round 1 empty → WARNING + DEBUG telemetry pair:
        assert sum("EMPTY response" in w for w in _warnings(deps)) >= 1
        assert sum("response=EMPTY" in m for m, lvl in deps["log"].calls if lvl == "DEBUG") >= 1


# ── 3. veto-twice → mention-only → give-up escalation ─────────────────────


class TestVetoMentionOnlyEscalation:
    def test_veto_twice_then_mention_only_then_give_up(self):
        """The V18.20.3.4 (RC-4) escalation shape: the colon-form
        misattributed bullet is vetoed twice (source attributes the claim
        to AuthorB, not AuthorA) → round 3 switches to the MENTION-ONLY
        prompt → the mention-only attempt also fails the veto → the author
        is GIVEN UP ON with the honest WARNING → round 4 breaks on the
        empty actionable pool."""
        src = (
            "AuthorB established the unified framework of identity "
            "development, drawing on AuthorA (1948)."
        )
        bad = "- AuthorA: Established the unified framework of identity development."
        deps = _make_deps(responses=[bad, bad, bad])
        bullets = []
        out = _run(
            deps,
            content=src,
            bullets=bullets,
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA", "AuthorB"],
        )
        assert out.total_added == 0
        assert bullets == []  # every candidate was vetoed
        assert out.given_up == {"AuthorA"}
        assert out.still_missing == ["AuthorA"]
        # 3 vetoed LLM rounds; round 4 = no-actionable break.
        assert len(deps["llm_calls"]) == 3
        assert out.rounds == 4

    def test_veto_warning_names_real_subject(self):
        """Log parity: each veto WARNING names the claimed vs real subject."""
        src = (
            "AuthorB established the unified framework of identity "
            "development, drawing on AuthorA (1948)."
        )
        bad = "- AuthorA: Established the unified framework of identity development."
        deps = _make_deps(responses=[bad, bad, bad])
        _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA", "AuthorB"],
        )
        veto_warnings = [w for w in _warnings(deps) if "active-subject veto" in w]
        assert len(veto_warnings) == 3
        assert all("'AuthorB', not 'AuthorA'" in w for w in veto_warnings)

    def test_round3_prompt_is_mention_only(self):
        """Round 3's prompt carries the MENTION-ONLY block for the
        twice-vetoed author (the RC-4 escalation arm)."""
        src = (
            "AuthorB established the unified framework of identity "
            "development, drawing on AuthorA (1948)."
        )
        bad = "- AuthorA: Established the unified framework of identity development."
        deps = _make_deps(responses=[bad, bad, bad])
        _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA", "AuthorB"],
        )
        prompts = [c["prompt"] for c in deps["llm_calls"]]
        # Rounds 1-2: no mention-only block.
        assert "MENTION-ONLY authors" not in prompts[0]
        assert "MENTION-ONLY authors" not in prompts[1]
        # Round 3: the mention-only block names the author.
        assert "MENTION-ONLY authors: AuthorA" in prompts[2]

    def test_give_up_and_final_warnings_fire(self):
        """The give-up WARNING + the split final report (given-up class vs
        never-covered class) both fire."""
        src = (
            "AuthorB established the unified framework of identity "
            "development, drawing on AuthorA (1948)."
        )
        bad = "- AuthorA: Established the unified framework of identity development."
        deps = _make_deps(responses=[bad, bad, bad])
        _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA", "AuthorB"],
        )
        warnings = _warnings(deps)
        assert any("Giving up on 'AuthorA'" in w for w in warnings)
        assert any("No actionable authors left" in m for m in _infos(deps))
        final = [w for w in warnings if "still missing from bullets after gap-fill" in w]
        assert len(final) == 1
        # The split report: AuthorA is in the GIVEN-UP class, not the
        # plain "never covered" class.
        assert "given up on after a failed mention-only attempt" in final[0]
        assert "never covered (round cap/deadline)" not in final[0]


# ── 4. no-op guard: empty missing list ────────────────────────────────────


class TestNoOpGuard:
    def test_empty_missing_is_no_op(self):
        """``missing=[]`` → immediate return: no LLM call, no log line,
        bullets untouched (the original ``if _missing:`` guard shape)."""
        deps = _make_deps(responses=["- should never be called"])
        bullets = ["Existing bullet."]
        out = _run(
            deps,
            content="Some source text.",
            bullets=bullets,
            missing=[],
            analysis={"authors": []},
            det_authors=[],
        )
        assert out == GapFillOutcome(total_added=0, rounds=0, still_missing=[], given_up=set())
        assert deps["llm_calls"] == []
        assert deps["log"].calls == []
        assert bullets == ["Existing bullet."]


# ── 5. round cap: while-loop bounded at 5 rounds ──────────────────────────


class TestRoundCap:
    def test_loop_terminates_at_five_round_cap(self):
        """9 missing authors, the fast LLM ALWAYS returning bullets that
        fail grounding (every bullet is a colon-form misattribution vetoed
        by the real detector): rounds 1-2 veto the first 8 authors, round 3
        is their mention-only round (also vetoed → all 8 given up), rounds
        4-5 veto the 9th author, and the while loop TERMINATES at the
        5-round cap (no infinite loop)."""
        names = [f"Author{c}" for c in "ABCDEFGHI"]
        cites = ", ".join(f"{n} ({1900 + i})" for i, n in enumerate(names))
        src = (
            f"AuthorZ established the unified framework of identity "
            f"development, drawing on {cites}."
        )
        # One misattributed bullet per author — the same response every
        # round (all vetoed, so never appended → never dup either).
        response = "\n".join(
            f"- {n}: Established the unified framework of identity development." for n in names
        )
        deps = _make_deps(responses=[response] * 5)
        bullets = []
        out = _run(
            deps,
            content=src,
            bullets=bullets,
            missing=list(names),
            analysis={"authors": names},
            det_authors=names + ["AuthorZ"],
        )
        # The loop is bounded: exactly 5 rounds, 5 LLM calls, terminates.
        assert out.rounds == 5
        assert len(deps["llm_calls"]) == 5
        # Nothing landed (every candidate was vetoed as a misattribution).
        assert out.total_added == 0
        assert bullets == []
        # The first 8 were given up after their failed mention-only round;
        # the 9th simply never landed (round cap).
        assert out.given_up == set(names[:8])
        assert set(out.still_missing) == set(names)
        final = [w for w in _warnings(deps) if "still missing from bullets after gap-fill" in w]
        assert final and "9 theorists still missing" in final[0]

    def test_retry_marker_varies_the_prompt_between_rounds(self):
        """RC-B.2: never re-send an IDENTICAL gap-fill prompt — rounds 4
        and 5 (both batching the 9th author alone) carry different
        'attempt N' retry markers, so the prompt bytes differ."""
        names = [f"Author{c}" for c in "ABCDEFGHI"]
        cites = ", ".join(f"{n} ({1900 + i})" for i, n in enumerate(names))
        src = (
            f"AuthorZ established the unified framework of identity "
            f"development, drawing on {cites}."
        )
        response = "\n".join(
            f"- {n}: Established the unified framework of identity development." for n in names
        )
        deps = _make_deps(responses=[response] * 5)
        _run(
            deps,
            content=src,
            bullets=[],
            missing=list(names),
            analysis={"authors": names},
            det_authors=names + ["AuthorZ"],
        )
        prompts = [c["prompt"] for c in deps["llm_calls"]]
        assert prompts[3] != prompts[4]
        assert "attempt 5 for these authors" in prompts[4]
        assert "Re-phrase every bullet from scratch" in prompts[4]


# ── 6. byte-for-byte stability ────────────────────────────────────────────


class TestByteForByte:
    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same outcome + same log sequence across calls."""
        src = "AuthorA established the framework of identity consolidation in 1950."

        def _run_once():
            deps = _make_deps(
                responses=["- AuthorA established the framework of identity consolidation."]
            )
            bullets = ["Existing bullet."]
            out = _run(
                deps,
                content=src,
                bullets=bullets,
                missing=["AuthorA"],
                analysis={"authors": ["AuthorA"]},
                det_authors=["AuthorA"],
            )
            return out, bullets, deps["log"].calls

        assert _run_once() == _run_once()

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        bullets = []
        out = batch_gap_fill(
            "Chapter 1",
            src,
            bullets,
            ["AuthorA"],
            {"authors": ["AuthorA"]},
            ["AuthorA"],
            check_coverage=lambda a, t: {
                "covered": [],
                "missing": ["AuthorA"],
                "total": 1,
                "coverage_pct": 0.0,
            },
            call_fast_llm=lambda p, **k: None,
            temperature=0.2,
            strip_thinking=lambda t: t,
            filter_thinking_bullets=lambda b, **k: list(b),
        )
        assert out.total_added == 0
        assert out.still_missing == ["AuthorA"]

    def test_outcome_is_named_tuple_with_counts(self):
        """The return is a GapFillOutcome(total_added, rounds,
        still_missing, given_up) — the logging-parity contract."""
        src = "AuthorA established the framework of identity consolidation in 1950."
        deps = _make_deps(
            responses=["- AuthorA established the framework of identity consolidation."]
        )
        out = _run(
            deps,
            content=src,
            bullets=[],
            missing=["AuthorA"],
            analysis={"authors": ["AuthorA"]},
            det_authors=["AuthorA"],
        )
        assert isinstance(out.total_added, int)
        assert isinstance(out.rounds, int)
        assert isinstance(out.still_missing, list)
        assert isinstance(out.given_up, set)
