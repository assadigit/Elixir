"""V0.5.6 (verification LAYER glossary integration) tests.

Covers the 3 V0.5.6 sub-tasks implemented across
``core/summarisation/verification_phase.py`` +
``core/summarisation/gap_fill_batch.py``:
  1. The coverage check uses the LLM-generated source glossary as the
     ground truth (PREFERS the glossary's ``names`` section over the
     ``extract_citations`` regex set — closes the V0.5.5 5-author gap
     where the regex missed "see also"-only authors).
  2. The quote-guard is LOOSENED for glossary-sourced authors (the
     V18.20.3.2 parenthetical-promotion veto no longer drops bullets
     for authors in the glossary — the glossary IS the grounding).
  3. The final-check round 4 (targeted, glossary-grounded) fires AFTER
     the standard 5-round gap-fill loop terminates — for each still-
     missing glossary-sourced author, a targeted LLM call uses the
     glossary context as the grounding + the loosened quote-guard +
     logs the final coverage score.

Content-agnostic (Rule 1): the author names + years in these tests are
TEST FIXTURES (Alpha / Beta / Gamma / Delta / Epsilon) — they do NOT
appear in runtime code. The production coverage check uses the runtime
LLM-generated ``source_glossary`` (the ``<name_glossary>`` block from
the master-summary call), no hardcoded names.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub the optional heavy deps exactly like tests/test_v054_verification_layer.py
# (markitdown) and tests/test_gap_fill_batch.py (tiktoken + markitdown) —
# both modules are imported eagerly by the core.summarisation chain.
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")

    class _E:
        pass

    _tk.Encoding = _E
    _tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = _tk

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ─────────────────────────────────────────────────────────────────────────────
# Shared test scaffolding (mirrors tests/test_v054_verification_layer.py +
# tests/test_gap_fill_batch.py)
# ─────────────────────────────────────────────────────────────────────────────


class _MockVerifyProvider:
    """A mock LLM provider that returns a caller-supplied raw response."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls: list[dict] = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt, "temperature": temperature})
        return self._raw


class _MockSettings:
    """Minimal Settings stub returning a configured model + ollama arch."""

    def __init__(self, *, model="mock-model", arch="single_local"):
        self._model = model
        self._arch = arch

    def get(self, key, default=None):
        if key == "summarisation.model":
            return self._model
        if key == "summarisation.model_architecture":
            return self._arch
        return default


class _CapturingLog:
    """Captures (msg, level) pairs — mirrors tests/test_gap_fill_batch.py."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _make_gap_fill_deps(*, responses=None, response_fn=None):
    """Build hermetic deps for batch_gap_fill (mirrors tests/test_gap_fill_batch.py)."""
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
        call_fast_llm=deps["call_fast_llm"],
        temperature=0.2,
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=deps["filter_thinking_bullets"],
        log=deps["log"],
        source_glossary=source_glossary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: coverage check uses the glossary as the ground truth
# ─────────────────────────────────────────────────────────────────────────────


class TestCoverageUsesGlossaryAsGroundTruth:
    """V0.5.6: when a source glossary is available, the LAYER's coverage
    check PREFERS the glossary's ``names`` section over the
    ``extract_citations`` regex set. The glossary is the richer LLM-
    extracted source roster (catches authors the regex misses — the
    V0.5.5 audit's 5-author gap: the regex flagged 8 missing, the gap-
    fill closed 3, the quote-guard dropped 5).
    """

    def test_coverage_check_uses_glossary_as_ground_truth(self, monkeypatch):
        """A glossary with names [Alpha, Beta, Gamma] + a summary that
        covers only Alpha → flags Beta + Gamma as missing (using the
        glossary, not the regex). The regex extracts only Alpha (the
        summary's covered author) — without the glossary, the LAYER
        would have flagged 0 missing authors (false "fully covered").
        """
        from core.summarisation.verification_phase import (
            clear_glossary_cache,
            verify_and_polish_summary,
        )

        # Isolate the test from any prior stashed glossary.
        clear_glossary_cache()

        # Source: only mentions Alpha (the regex will extract only Alpha).
        # The glossary, however, has [Alpha, Beta, Gamma] — the LLM
        # extracted Beta + Gamma from the source's "see also" citations
        # (which the regex misses).
        source = "Alpha (1971) described the framework."
        summary = "Alpha (1971) described the framework."
        glossary = {
            "names": [
                {"name": "Alpha", "year": "1971", "context": "described the framework"},
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
                {"name": "Gamma", "year": "1985", "context": "provided the integration"},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }

        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
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

        # The coverage flag should fire (Beta + Gamma missing).
        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert cov, (
            "V0.5.6: the coverage check should flag Beta + Gamma as "
            "missing (the glossary is the ground truth, not the regex)."
        )
        detail = cov[0].detail
        # V0.5.6 log: glossary-grounded coverage flag.
        assert "glossary-grounded" in detail, (
            f"V0.5.6: the detail should say 'glossary-grounded'; got: {detail!r}"
        )
        # The missing list should name BOTH Beta + Gamma.
        assert "Beta" in detail, f"V0.5.6: Beta should be flagged; got: {detail!r}"
        assert "Gamma" in detail, f"V0.5.6: Gamma should be flagged; got: {detail!r}"
        # The cross-reference buckets should be logged.
        assert "Cross-ref:" in detail, (
            f"V0.5.6: the detail should log the cross-ref buckets; got: {detail!r}"
        )
        assert "confirmed=1" in detail, (
            "V0.5.6: Alpha is in BOTH the glossary + the regex → confirmed=1"
        )
        assert "llm_only=2" in detail, (
            "V0.5.6: Beta + Gamma are in the glossary but NOT the regex → llm_only=2"
        )
        # The glossary path should be logged for the audit.
        assert "summaries/.glossaries/ch_test.glossary.md" in detail, (
            "V0.5.6: the detail should include the glossary's persisted path"
        )

    def test_coverage_check_falls_back_to_extract_citations_without_glossary(self, monkeypatch):
        """When NO glossary is provided, the coverage check uses the
        ``extract_citations`` regex (the V0.5.5 behavior — fail-open).
        The flag detail says 'coverage-targeting:' (NOT 'glossary-
        grounded') + does NOT log the cross-reference buckets.
        """
        from core.summarisation.verification_phase import (
            clear_glossary_cache,
            verify_and_polish_summary,
        )

        # Isolate the test from any prior stashed glossary.
        clear_glossary_cache()

        # Source: 3 authors via the regex pattern.
        source = "Alpha (1971) described X. Beta (1980) extended it. Gamma (1985) synthesized."
        summary = "Alpha (1971) described X."  # Beta + Gamma missing

        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        _out, issues = verify_and_polish_summary(
            summary,
            source,
            settings=_MockSettings(),
            # No source_glossary + no chapter_heading → fallback to regex.
        )

        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert cov, "V0.5.5 fallback: Beta + Gamma should be flagged via the regex"
        detail = cov[0].detail
        # V0.5.5 fallback: the detail says 'coverage-targeting:' (NOT
        # 'glossary-grounded') + does NOT log cross-ref buckets.
        assert "coverage-targeting:" in detail
        assert "glossary-grounded" not in detail, (
            "V0.5.5 fallback: the detail should NOT say 'glossary-grounded'"
        )
        assert "Cross-ref:" not in detail, (
            "V0.5.5 fallback: the detail should NOT log cross-ref buckets"
        )
        assert "Beta" in detail
        assert "Gamma" in detail


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: loosened quote-guard for glossary authors
# ─────────────────────────────────────────────────────────────────────────────


class TestLoosenedQuoteGuard:
    """V0.5.6: the V18.20.3.2 parenthetical-promotion veto (the
    "quote-guard") is LOOSENED for glossary-sourced authors. The glossary
    IS the grounding (extracted from the source by the LLM) — the bullet
    can write "Bak (1946) introduced..." grounded in the glossary context,
    without needing a verbatim source quote. For non-glossary authors,
    the strict V0.5.4 veto still fires (prevents fabrication).
    """

    def test_quote_guard_loosened_for_glossary_authors(self):
        """A gap-fill bullet for a glossary author that fires the
        parenthetical-promotion veto (the source attributes the claim
        to a DIFFERENT author) → ACCEPTED anyway (the glossary IS the
        grounding — V0.5.21 update: provided the bullet's content is
        covered by the glossary context, the see-also bound; a bullet
        exceeding the context is bound-rejected, see
        tests/test_v0521_backlog.py). The V0.5.6 INFO log line fires.
        """
        from core.summarisation.gap_fill_batch import GapFillOutcome

        # Source: Zeta established the framework, drawing on Epsilon
        # (1948). The bullet claims Epsilon established it → the veto
        # fires (correctly, per V18.20.3.2). Epsilon is in the glossary
        # AND the glossary context grounds the bullet's content → the
        # loosened quote-guard accepts the bullet (V0.5.21: the context
        # carries the SAME content, so the see-also bound passes).
        src = (
            "Zeta established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bad = "- Epsilon: Established the unified framework of identity development."
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
        deps = _make_gap_fill_deps(responses=[bad])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Zeta"],
            source_glossary=glossary,
        )
        # The loosened quote-guard ACCEPTED the bullet (was: dropped).
        assert isinstance(out, GapFillOutcome)
        assert len(bullets) == 1, (
            "V0.5.6: the loosened quote-guard should ACCEPT the "
            "bullet for the glossary author Epsilon (was: dropped "
            "by the V18.20.3.2 veto)."
        )
        assert "Epsilon" in bullets[0]
        # The V0.5.6 INFO log should fire.
        all_logs = [m for m, _ in deps["log"].calls]
        v056_accept_logs = [
            m for m in all_logs if "✨ V0.5.6 gap-fill: accepted bullet for 'Epsilon'" in m
        ]
        assert v056_accept_logs, (
            "V0.5.6: the INFO log line '✨ V0.5.6 gap-fill: accepted "
            "bullet for ...' should fire when the loosened quote-guard "
            "accepts a glossary-backed bullet"
        )

    def test_quote_guard_strict_for_non_glossary_authors(self):
        """A gap-fill bullet for a NON-glossary author that fires the
        parenthetical-promotion veto → DROPPED (the V0.5.5 behavior —
        prevents fabrication). No V0.5.6 INFO log line fires.
        """
        from core.summarisation.gap_fill_batch import GapFillOutcome

        # Same source as the glossary-backed test, but NO glossary
        # provided → the loosened override never fires → the strict
        # V18.20.3.2 veto drops the bullet (the V0.5.5 behavior).
        src = (
            "Zeta established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bad = "- Epsilon: Established the unified framework of identity development."
        deps = _make_gap_fill_deps(responses=[bad, bad, bad])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Zeta"],
            # No source_glossary → strict V0.5.4 veto (the V0.5.5 behavior).
            source_glossary=None,
        )
        assert isinstance(out, GapFillOutcome)
        # The strict veto DROPPED the bullet (the V0.5.5 behavior).
        assert bullets == [], (
            "V0.5.5: the strict V18.20.3.2 veto should DROP the bullet "
            "for the non-glossary author Epsilon (no loosened override)"
        )
        # The V0.5.6 INFO log should NOT fire (no glossary → no
        # loosened override).
        all_logs = [m for m, _ in deps["log"].calls]
        v056_accept_logs = [m for m in all_logs if "✨ V0.5.6 gap-fill: accepted" in m]
        assert not v056_accept_logs, (
            "V0.5.5: the V0.5.6 loosened-override log line should NOT "
            "fire when no glossary is provided"
        )
        # The V18.20.3.2 veto WARNING should fire (the strict path).
        v_veto_logs = [m for m in all_logs if "V18.20.3.2: gap-fill active-subject veto" in m]
        assert v_veto_logs, "V0.5.5: the V18.20.3.2 veto WARNING should fire on the strict path"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: final-check round 4 (targeted, glossary-grounded)
# ─────────────────────────────────────────────────────────────────────────────


class TestFinalCheckRound4:
    """V0.5.6: after the standard 5-round gap-fill loop terminates,
    if a source glossary is available AND there are still-missing
    authors, fire a TARGETED round 4 using the glossary context as the
    grounding + the loosened quote-guard. The round 4 prompt names each
    still-missing author + their glossary context, and explicitly
    instructs the LLM not to drop them for lack of a verbatim quote.
    The final coverage score is logged for the audit trail.
    """

    def test_final_check_round_4_targets_still_missing(self):
        """After the standard 5-round gap-fill loop terminates (3 empty
        responses → 2 authors given up via the V18.20.3.4 escalation),
        2 authors still missing → round 4 fires + targets them by name
        + glossary context. The round 4 prompt names BOTH missing
        authors + their glossary context lines.
        """
        # Source: 3 authors (Alpha covered by the existing bullet; Beta
        # + Gamma missing). The standard loop returns 3 empty responses
        # (rounds 1-3 — round 3 is the mention-only attempt that fails
        # → give up). The final-check round 4 fires for [Beta, Gamma]
        # + the canned Beta + Gamma bullets are accepted.
        src = "Alpha established the framework. Beta extended it. Gamma synthesized it."
        glossary = {
            "names": [
                {"name": "Alpha", "year": "1971", "context": "described the framework"},
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
                {"name": "Gamma", "year": "1985", "context": "provided the integration"},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        # 3 empty responses for the standard loop's 3 rounds, then 1
        # response with Beta + Gamma bullets for the final-check round 4.
        deps = _make_gap_fill_deps(
            responses=[
                None,  # round 1 standard: empty
                None,  # round 2 standard: empty (no-yield=2 → mention-only)
                None,  # round 3 standard: mention-only attempt fails → give up
                "- Beta (1980) extended the synthesis.\n- Gamma (1985) provided the integration.",
                # ↑ round 4 final-check: 2 glossary-grounded bullets
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
        # The final-check round 4 fired (4 LLM calls: 3 standard rounds
        # + 1 final-check round 4).
        assert len(deps["llm_calls"]) == 4, (
            f"V0.5.6: round 4 should fire after the standard loop's 3 "
            f"empty rounds (give-up) — 4 LLM calls expected; got "
            f"{len(deps['llm_calls'])}"
        )
        # The round 4 prompt should name BOTH Beta + Gamma + their
        # glossary context (the FINAL-CHECK prompt, not the standard
        # loop's prompt — it's the 4th LLM call).
        round4_prompt = deps["llm_calls"][3]["prompt"]
        assert "Beta" in round4_prompt, (
            "V0.5.6: the round 4 prompt should name Beta (the still-missing author)"
        )
        assert "Gamma" in round4_prompt, (
            "V0.5.6: the round 4 prompt should name Gamma (the still-missing author)"
        )
        assert "extended the synthesis" in round4_prompt, (
            "V0.5.6: the round 4 prompt should include Beta's glossary context "
            "'extended the synthesis'"
        )
        assert "provided the integration" in round4_prompt, (
            "V0.5.6: the round 4 prompt should include Gamma's glossary context "
            "'provided the integration'"
        )
        # NB: the prompt says "Do NOT drop them" (uppercase NOT). Lowercasing
        # the prompt makes it "do not drop them" — the assertion's substring
        # uses the lowercased form so it matches.
        assert "do not drop them for lack of a verbatim quote" in round4_prompt.lower(), (
            "V0.5.6: the round 4 prompt should instruct the LLM not to "
            "drop the authors for lack of a verbatim quote"
        )
        assert "glossary is the grounding" in round4_prompt.lower(), (
            "V0.5.6: the round 4 prompt should state that the glossary IS the grounding"
        )
        # The final-check should have added 2 bullets.
        assert out.final_check_added == 2, (
            f"V0.5.6: final-check round 4 should add 2 bullets; got {out.final_check_added}"
        )
        assert out.final_check_rounds == 1, "V0.5.6: final-check rounds should be 1"
        # The bullets list should now contain all 3 authors (Alpha + Beta + Gamma).
        assert len(bullets) == 3
        assert any("Beta" in b for b in bullets)
        assert any("Gamma" in b for b in bullets)

    def test_final_check_logs_coverage_score(self):
        """The final-check logs the coverage score: either 'X/Y
        authors (Z%) — full coverage achieved' (Z=100) or 'X/Y authors
        (Z%) — N still missing: [names]' (Z<100). Both shapes are
        regression-guarded."""
        # Sub-test A: full coverage achieved (round 4 closes the gap).
        # 3 authors in the glossary, 1 covered (Alpha), 2 missing
        # (Beta + Gamma). Standard loop runs 3 empty rounds → give up.
        # Final-check round 4 fires + adds Beta + Gamma → full coverage.
        src = "Alpha described X. Beta extended it. Gamma synthesized it."
        glossary_full = {
            "names": [
                {"name": "Alpha", "year": "1971", "context": "described the framework"},
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
                {"name": "Gamma", "year": "1985", "context": "provided the integration"},
            ],
            "path": "summaries/.glossaries/full.glossary.md",
        }
        deps_full = _make_gap_fill_deps(
            responses=[
                None,  # round 1 standard: empty
                None,  # round 2 standard: empty (mention-only next round)
                None,  # round 3 standard: mention-only attempt fails → give up
                "- Beta (1980) extended the synthesis.\n- Gamma (1985) provided the integration.",
                # ↑ round 4 final-check: closes the gap
            ]
        )
        bullets_full = ["- Alpha (1971) described the framework."]
        _run_gap_fill(
            deps_full,
            content=src,
            bullets=bullets_full,
            missing=["Beta", "Gamma"],
            analysis={"authors": ["Beta", "Gamma"]},
            det_authors=["Beta", "Gamma"],
            source_glossary=glossary_full,
        )
        all_logs_full = [m for m, _ in deps_full["log"].calls]
        # The "full coverage achieved" log line fires when round 4
        # closes the gap.
        full_cov_logs = [
            m for m in all_logs_full if "V0.5.6 final-check:" in m and "full coverage achieved" in m
        ]
        assert full_cov_logs, (
            "V0.5.6: the final-check should log 'full coverage achieved' "
            "when round 4 closes the gap"
        )
        # The log line should report 3/3 (100%).
        assert "3/3 authors (100%)" in full_cov_logs[0], (
            f"V0.5.6: the final-check log should report 3/3 (100%); got: {full_cov_logs[0]!r}"
        )
        assert "summaries/.glossaries/full.glossary.md" in full_cov_logs[0], (
            "V0.5.6: the final-check log should include the glossary path"
        )

        # Sub-test B: partial coverage (round 4 doesn't fully close
        # the gap — the LLM returned nothing usable).
        # 4 authors in the glossary, 1 covered (Alpha), 3 missing
        # (Beta + Gamma + Delta). Standard loop runs 3 empty rounds
        # (round 3 mention-only fails → give up). Final-check round 4
        # fires for [Beta, Gamma, Delta] but returns empty → 1/4 (25%).
        src_b = (
            "Alpha described X. Beta extended it. Gamma synthesized it. Delta added the critique."
        )
        glossary_partial = {
            "names": [
                {"name": "Alpha", "year": "1971", "context": "described the framework"},
                {"name": "Beta", "year": "1980", "context": "extended the synthesis"},
                {"name": "Gamma", "year": "1985", "context": "provided the integration"},
                {"name": "Delta", "year": "1990", "context": "added the critique"},
            ],
            "path": "summaries/.glossaries/partial.glossary.md",
        }
        deps_partial = _make_gap_fill_deps(
            responses=[
                None,  # round 1 standard: empty
                None,  # round 2 standard: empty (mention-only next round)
                None,  # round 3 standard: mention-only attempt fails → give up
                None,  # round 4 final-check: empty (the LLM returned nothing)
            ]
        )
        bullets_partial = ["- Alpha (1971) described the framework."]
        _run_gap_fill(
            deps_partial,
            content=src_b,
            bullets=bullets_partial,
            missing=["Beta", "Gamma", "Delta"],
            analysis={"authors": ["Beta", "Gamma", "Delta"]},
            det_authors=["Beta", "Gamma", "Delta"],
            source_glossary=glossary_partial,
        )
        all_logs_partial = [m for m, _ in deps_partial["log"].calls]
        # The coverage-score log line fires when round 4 doesn't close
        # the gap. Match on the percentage marker 'authors (' +
        # 'still missing:' (the firing log line says 'still missing
        # after round N' WITHOUT the colon — the coverage-score line
        # says 'N still missing:' WITH the colon).
        partial_cov_logs = [
            m
            for m in all_logs_partial
            if "V0.5.6 final-check:" in m and "authors (" in m and "still missing:" in m
        ]
        assert partial_cov_logs, (
            "V0.5.6: the final-check should log the coverage-score line "
            "('X/Y authors (Z%) — N still missing: ...') when round 4 "
            "doesn't close the gap"
        )
        # The log line should report 1/4 (25%) — only Alpha covered.
        assert "1/4 authors (25%)" in partial_cov_logs[0], (
            f"V0.5.6: the final-check log should report 1/4 (25%); got: {partial_cov_logs[0]!r}"
        )
        assert "summaries/.glossaries/partial.glossary.md" in partial_cov_logs[0], (
            "V0.5.6: the final-check log should include the glossary path"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
