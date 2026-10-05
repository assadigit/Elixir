"""V0.5.10 (Track C4) — fix the 3 ``field_phases.py`` callers that
discarded the Pattern C rewrite (the V0.5.3 "ego-syntonically" garble
shipped uncorrected from V0.5.4 through V0.5.9).

Context: the V0.5.4 (Track C2) upgrade of ``detect_sentence_fusion`` in
``core/summarisation/postchecks/garble/fusion.py`` is correct at the
FUNCTION level — it returns ``(possibly-rewritten) text + issues`` for
the adverb-as-adjective grammatical garble (e.g., the V0.5.3 ground-
truth audit's bullet 15 garble ``ego-syntonically personalities`` →
``ego-syntonic personalities``). BUT the 3 production callers in
``core/summarisation/postchecks/field_phases.py`` (the bullets phase at
L192, the exec phase at L602, the thorough phase at L770) were written
for the V0.4.3 flag-only contract and DISCARDED the returned text with
``_, fusion_issues = detect_sentence_fusion(...)``. As a result, the
function-level rewrite took effect in the returned text + the issue
detail, but the caller-level discard meant the rewrite's effect on the
ACTUAL summary text NEVER reached the shipped bullet / exec / thorough —
the V0.5.3 "ego-syntonically personalities" garble shipped uncorrected
from V0.5.4 through V0.5.9 (the rewrite shipped as a flagged-but-not-
applied issue-detail note ONLY).

V0.5.10 (Track C4): the 3 callers now CAPTURE the returned text
(``bp_str, fusion_issues = ...`` / ``exec_str, exec_fusion = ...`` /
``tho_str, tho_fusion = ...``). The rewritten text propagates to:

  (a) the shipped bullet / exec / thorough (the field text returned by
      ``postcheck_bullets`` / ``postcheck_exec`` / ``postcheck_thorough``)
  (b) all subsequent detectors (the dropped-letter detector, the LLM
      semantic repair, the author-garble, the stray-quote repair) so
      they see the corrected text, not the garbled original

Content-agnostic (Rule 1): the callers use the runtime text variable;
"ego-syntonically" appears in TESTS only (never in the production code
— verified by the test ``test_all_detect_sentence_fusion_callers_use_
returned_text``).
"""

from __future__ import annotations

import re
from pathlib import Path

from core.summarisation.postchecks.field_phases import (
    PhaseCtx,
    postcheck_bullets,
    postcheck_exec,
    postcheck_thorough,
)
from core.summarisation.postchecks.shared import PostCheckReport

# Source text used by the rewrite tests: contains ``egosyntonic`` (so
# Pattern A fires on the adverb form ``ego-syntonically`` — the
# unhyphenated adjective IS in the source-word set) and
# ``syntonically`` (so the ``ally`` suffix is in the source-word suffix
# set). Mirrors the V0.5.4 (Track C2) test setup at
# ``tests/test_v052_audit_fixes.py:333``.
_REWRITE_SRC = "The patient showed egosyntonic traits. The behaviour was syntonically appropriate."

# The V0.5.3 ground-truth audit's bullet 15 garble.
_GARBLE = "ego-syntonically personalities"
_REWRITE = "ego-syntonic personalities"


def _make_ctx(src: str) -> PhaseCtx:
    """Build a minimal PhaseCtx with the source-derived values
    precomputed (matches what orchestrator.run_post_checks does once
    per run — see orchestrator.py's ``_src_lower``/``_src_words``).
    """
    src_lower = src.lower()
    src_words = {w for w in re.split(r"\W+", src_lower) if w}
    return PhaseCtx(
        source_text=src,
        source_lower=src_lower,
        source_lower_full=src_lower,
        source_words=src_words,
        source_authors=[],
        auto_repair_garble=False,
    )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.10 (Track C4) — the 3 field_phases.py callers capture the rewrite
# ═══════════════════════════════════════════════════════════════════════════


class TestV0510FieldPhasesRewritePropagation:
    """V0.5.10 (Track C4): the 3 ``field_phases.py`` callers (the
    bullets phase, the exec phase, the thorough phase) now capture the
    returned (possibly-rewritten) text from ``detect_sentence_fusion``,
    so the V0.5.4 (Track C2) rewrite reaches the shipped bullet / exec
    / thorough AND flows into subsequent detectors (the dropped-letter
    detector, the LLM semantic repair, the author-garble, the stray-
    quote repair). Before V0.5.10, the 3 callers discarded the returned
    text (``_, fusion_issues = ...`` — the V0.4.3 flag-only contract),
    so the rewrite's effect on the actual summary text NEVER reached
    the shipped output (the V0.5.3 "ego-syntonically personalities"
    garble shipped uncorrected from V0.5.4 through V0.5.9).
    """

    # ── e2e: the rewrite reaches the shipped text (was discarded pre-V0.5.10) ──

    def test_field_phases_uses_rewritten_text(self):
        """e2e: a bullet / exec / thorough with the V0.5.3 garble
        ``ego-syntonically personalities`` is rewritten to
        ``ego-syntonic personalities`` in the SHIPPED text (the
        pre-V0.5.10 discard shipped the garble uncorrected).

        This test exercises ALL 3 caller sites in a single assertion
        block — the bullets phase (``postcheck_bullets``), the exec
        phase (``postcheck_exec``), and the thorough phase
        (``postcheck_thorough``). Before V0.5.10, the rewrite shipped
        as an issue-detail note ONLY — the actual bullet / exec /
        thorough text retained the original garble.
        """
        ctx = _make_ctx(_REWRITE_SRC)

        # --- bullets phase (the field the V0.5.3 audit's bullet 15
        # shipped in) ---
        bullet_text = f"The patient displays {_GARBLE} in the clinical evaluation."
        report = PostCheckReport()
        out_bullets = postcheck_bullets([bullet_text], ctx, report)
        assert len(out_bullets) == 1, (
            "V0.5.10: the garble bullet must NOT be dropped — it has a "
            f"predicate + terminal punctuation; got: {out_bullets!r}"
        )
        assert _REWRITE in out_bullets[0], (
            "V0.5.10: the bullets-phase caller must capture the rewritten "
            "text so 'ego-syntonic personalities' ships in the bullet "
            f"(was discarded in V0.4.3–V0.5.9); got: {out_bullets[0]!r}"
        )
        assert _GARBLE not in out_bullets[0], (
            "V0.5.10: the original garble 'ego-syntonically personalities' "
            f"must NOT ship in the bullets-phase output; got: {out_bullets[0]!r}"
        )
        # The rewrite also reached the issue-detail note (the V0.5.4
        # function-level behavior is preserved end-to-end).
        fusion = [i for i in report.issues if i.detector == "sentence_fusion"]
        assert any(
            "Auto-rewrite" in (i.detail or "") and "ego-syntonic" in (i.detail or "")
            for i in fusion
        ), (
            "V0.5.10: the issue detail must note the auto-rewrite "
            "(V0.5.4 contract preserved); got: "
            f"{[i.detail for i in fusion]}"
        )

        # --- exec phase ---
        exec_text = f"The executive summary notes {_GARBLE} observed in evaluation."
        report = PostCheckReport()
        out_exec = postcheck_exec(exec_text, ctx, report)
        assert _REWRITE in out_exec, (
            "V0.5.10: the exec-phase caller must capture the rewritten "
            f"text so 'ego-syntonic personalities' ships in the exec; got: {out_exec!r}"
        )
        assert _GARBLE not in out_exec, (
            "V0.5.10: the original garble 'ego-syntonically personalities' "
            f"must NOT ship in the exec-phase output; got: {out_exec!r}"
        )

        # --- thorough phase ---
        thorough_text = f"The thorough analysis notes {_GARBLE} observed in the evaluation."
        report = PostCheckReport()
        out_tho = postcheck_thorough(thorough_text, ctx, report)
        assert _REWRITE in out_tho, (
            "V0.5.10: the thorough-phase caller must capture the rewritten "
            "text so 'ego-syntonic personalities' ships in the thorough; "
            f"got: {out_tho!r}"
        )
        assert _GARBLE not in out_tho, (
            "V0.5.10: the original garble 'ego-syntonically personalities' "
            f"must NOT ship in the thorough-phase output; got: {out_tho!r}"
        )

    # ── e2e: real fusions still flag (the rewrite doesn't over-suppress) ──

    def test_field_phases_real_fusion_still_flagged(self):
        """e2e: a real dropped-prefix fusion (``persecutionensate``)
        is STILL flagged by the sentence-fusion detector AND is NOT
        rewritten — the V0.5.4 (Track C2) rewrite is conservative (only
        the adverb-as-adjective ``-ically → -ic`` pattern rewrites;
        dropped-prefix fusions need LLM repair, not a deterministic
        rewrite). This guards against the V0.5.10 (Track C4) caller
        propagation inadvertently over-suppressing real garbles.
        """
        # Source has "persecution" + "compensate" so the dropped-prefix
        # fusion "persecutionensate" (mid-overlap) is a Pattern C garble.
        src = "persecution is wrong. compensate for the losses incurred."
        ctx = _make_ctx(src)
        bullet_text = "A persecutionensate problem was noted in the evaluation."
        report = PostCheckReport()
        out_bullets = postcheck_bullets([bullet_text], ctx, report)
        # The bullet ships (it has a predicate + terminal punctuation —
        # the fusion is flag-only, not a fix that drops the bullet).
        assert len(out_bullets) == 1, (
            "V0.5.10: the fusion bullet must NOT be dropped (the sentence-"
            f"fusion detector is flag-only); got: {out_bullets!r}"
        )
        # The fusion is still flagged (Pattern C: persecution + ensate).
        fusion = [i for i in report.issues if i.detector == "sentence_fusion"]
        assert fusion, (
            "V0.5.10: 'persecutionensate' (a real dropped-prefix fusion) "
            "MUST still be flagged — the V0.5.10 caller propagation must "
            "not over-suppress real garbles"
        )
        # The text is NOT rewritten (the -ically rule doesn't apply to
        # non-"-ically" words — only adverb→adjective rewrites fire).
        assert "persecutionensate" in out_bullets[0], (
            "V0.5.10: 'persecutionensate' must NOT be rewritten (the -ically "
            "rule doesn't apply — only adverb→adjective rewrites fire); "
            f"got: {out_bullets[0]!r}"
        )
        # No auto-rewrite note in the issue detail (the rule didn't fire).
        assert all("Auto-rewrite" not in (i.detail or "") for i in fusion), (
            "V0.5.10: the 'persecutionensate' issue must NOT include an "
            "auto-rewrite note (the V0.5.4 rule didn't fire — the word "
            f"doesn't end in -ically); got: {[i.detail for i in fusion]}"
        )

    # ── static: NO production caller discards the returned text ──

    def test_all_detect_sentence_fusion_callers_use_returned_text(self):
        """Static: grep-verify that NO PRODUCTION caller of
        ``detect_sentence_fusion`` discards the returned text with the
        ``_, `` pattern. This pins the V0.5.10 (Track C4) contract:
        every production caller captures the returned (possibly-
        rewritten) text so the V0.5.4 (Track C2) rewrite propagates to
        the shipped summary.

        Scoped to production code (``core/summarisation/``) — TEST
        files legitimately discard the text when testing issue
        flagging only (e.g., ``tests/test_v0438_audit_fixes.py:64``'s
        ``_, issues = detect_sentence_fusion(...)`` tests that the
        detector flags issues, NOT that the rewrite propagates).
        """
        repo_root = Path(__file__).resolve().parent.parent
        core_dir = repo_root / "core" / "summarisation"
        # Walk all .py files under core/summarisation/ and grep for
        # discard-the-text call sites of detect_sentence_fusion.
        discard_sites: list[str] = []
        call_sites: list[str] = []
        # The discard pattern: line starts (after optional whitespace)
        # with the discard placeholder ``_`` + ``,`` + a target variable
        # name + ``=`` + ``detect_sentence_fusion(``. Matches both
        # ``_, fusion_issues = detect_sentence_fusion(`` and the
        # tighter ``_,exec_fusion = detect_sentence_fusion(`` forms.
        discard_re = re.compile(r"^\s*_,\s*\w+\s*=\s*detect_sentence_fusion\(")
        for py_file in sorted(core_dir.rglob("*.py")):
            text = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if "detect_sentence_fusion(" not in line:
                    continue
                rel = py_file.relative_to(repo_root)
                if "= detect_sentence_fusion(" in line:
                    call_sites.append(f"{rel}:{line_no}")
                if discard_re.match(line):
                    discard_sites.append(f"{rel}:{line_no}: {line.strip()}")
        assert call_sites, (
            "V0.5.10: the test expected to find at least one production "
            "call site of detect_sentence_fusion under "
            "core/summarisation/ — if zero, the test scope is stale "
            "(the function moved or was renamed)"
        )
        assert not discard_sites, (
            "V0.5.10 (Track C4): NO production caller of "
            "detect_sentence_fusion may discard the returned text — "
            "the V0.5.4 (Track C2) rewrite MUST propagate to the "
            "shipped summary. Found discard sites:\n  " + "\n  ".join(discard_sites)
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
