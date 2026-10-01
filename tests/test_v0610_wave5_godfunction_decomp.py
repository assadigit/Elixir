"""V0.6.10 (Wave 5) — god-function decomposition characterization tests.

Covers the paths the B12/B13 refactor touches that the existing suites left
untested (the charter: characterization tests FIRST, verbatim extraction
second):

* ``scholar_reflection`` (B12 — CC 118 → phase helpers behind a context
  dataclass):
  - the V0.4.23 FILLER FLOOR on the SCHOLAR path (the batch-path floor is
    covered by tests/test_v00423_filler_floor.py; the scholar twin wasn't);
  - the V0.06 bullet-budget TRIM path (at-cap skip is covered by
    tests/test_v006_rig_audit_fixes.py; the partial-room trim wasn't);
  - the V18.20.3.4 thinking-filter CRASH path (fail-open, bullets kept);
  - the reflections-without-gap-fill log path.

* ``verify_and_polish_summary`` (B13 — the 12 copy-pasted exits → one exit
  helper):
  - the D1 contract at the NO-MODEL exit: en-dash normalization lands even
    when the LLM is never called (the empty-input exit is covered by the
    V0.5.4 suite; the no-model exit's deterministic-fix behavior wasn't
    asserted directly);
  - the cloud-provider exit (provider_name not in ollama/llamacpp →
    original kept, no LLM call).

Content-agnostic (Rule 1): every author name / year below is a TEST FIXTURE,
not runtime code.

Run: pytest tests/test_v0610_wave5_godfunction_decomp.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.scholar_reflection import (
    scholar_reflection,
    scholar_reflection_gapfill_only,
)
from core.summarisation.verification_phase import verify_and_polish_summary

# ── B12 structural pins (the V0.6.10 decomposition shape) ───────────────────


class TestB12Structure:
    """V0.6.10 (B12): the scholar_reflection god-function decomposition —
    the phase structure + the CC ceiling. The behavioral contract is pinned
    by the classes above + the pre-existing suites (test_scholar_reflection,
    test_v182042_p1_scholar_probe_gate, test_v1820412_b_semantics,
    test_v182032/34/36, test_v006_rig_audit_fixes)."""

    def test_ctx_dataclass_holds_the_13_params(self):
        import dataclasses

        from core.summarisation import scholar_reflection as sr

        fields = {f.name for f in dataclasses.fields(sr._ScholarCtx)}
        expected = {
            "heading",
            "text",
            "result",
            "max_context_tokens",
            "language",
            "temperature",
            "prompt_manager",
            "recover_vram",
            "call_llm",  # V0.6.14 (single-model order): was call_fast_llm
            "strip_thinking",
            "filter_thinking_bullets",
            "log",
            "bullet_cap",
        }
        assert expected <= fields

    def test_phase_helpers_exist_and_orchestrator_keeps_order(self):
        import inspect

        from core.summarisation import scholar_reflection as sr

        helpers = [
            "_sr_prepare",
            "_sr_probe_gate",
            "_sr_build_prompt",
            "_sr_prompt_overflow_skip",
            "_sr_call_llm",
            "_sr_parse_response",
            "_sr_ground_gap_bullets",
            "_sr_merge_gap_bullets",
        ]
        for name in helpers:
            assert callable(getattr(sr, name, None)), f"missing {name}"
        src = inspect.getsource(sr.scholar_reflection)
        order = [
            src.index("_sr_prepare(ctx)"),
            src.index("_sr_probe_gate(ctx)"),
            src.index("_sr_build_prompt(ctx)"),
            src.index("_sr_prompt_overflow_skip(ctx)"),
            src.index("_sr_call_llm(ctx)"),
            src.index("_sr_parse_response(ctx)"),
            src.index("_sr_ground_gap_bullets(ctx)"),
            src.index("_sr_merge_gap_bullets(ctx, _grounded)"),
        ]
        assert order == sorted(order), "phase call order must match the original flow"
        # the two skip-gates return BEFORE the try (the original semantics)
        try_pos = src.index("try:")
        assert order[1] < try_pos and order[3] < try_pos
        # the fail-open except is the LAST statement of the orchestrator
        assert "Scholar reflection failed" in src.split("except Exception as e:")[-1]

    def test_cc_ceiling_no_f_grade_function_remains(self):
        """radon CC: the module's worst function is E(31) (was F/118 for
        scholar_reflection alone); no function may regress to F (>=41)."""
        import ast
        import inspect

        from radon.visitors import ComplexityVisitor

        from core.summarisation import scholar_reflection as sr

        src = inspect.getsource(sr)
        tree = ast.parse(src)
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        blocks = visitor.blocks
        assert blocks
        worst = max(b.complexity for b in blocks)
        assert worst < 41, f"no F-grade function allowed (worst={worst})"
        orch = next(b for b in blocks if b.name == "scholar_reflection")
        assert orch.complexity <= 15, (
            f"orchestrator must stay a thin coordinator (CC={orch.complexity})"
        )


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))

    def infos(self):
        return [m for m, l in self.calls if l == "INFO"]

    def warnings(self):
        return [m for m, l in self.calls if l == "WARNING"]


class _FakePromptManager:
    def render_template(self, name, **kw):
        return (
            f"PROMPT name={name} heading={kw.get('heading')} "
            f"theorists={kw.get('theorists_hint', '')[:50]}..."
        )


def _make_deps(*, llm_responses=None, llm_raises=None):
    """Mock deps for scholar_reflection (multi-response aware for retries)."""
    llm_responses = list(llm_responses or [""])
    llm_calls = []
    rvram_calls = []

    # V0.6.14 (single-model order): the dep was renamed call_fast_llm →
    # call_llm (the ONE model's empty-retry path); mock renamed to match.
    def call_llm(prompt, temperature=None, max_tokens=None, **kw):
        llm_calls.append({"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens})
        if llm_raises is not None:
            raise llm_raises
        if llm_responses:
            return llm_responses.pop(0)
        return ""

    def recover_vram(context="", delay_sec=0.0, **kw):
        rvram_calls.append({"context": context, "delay_sec": delay_sec})

    def strip_thinking(text):
        return text

    return {
        "prompt_manager": _FakePromptManager(),
        "recover_vram": recover_vram,
        "call_llm": call_llm,
        "strip_thinking": strip_thinking,
        "_llm_calls": llm_calls,
        "_rvram_calls": rvram_calls,
    }


def _run_scholar(deps, result, *, text="src", bullet_cap=None, filter_fn=None):
    log = _CapturingLog()
    scholar_reflection(
        "Ch",
        text,
        result,
        max_context_tokens=32768,
        language="en",
        temperature=0.7,
        prompt_manager=deps["prompt_manager"],
        recover_vram=deps["recover_vram"],
        call_llm=deps["call_llm"],
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=filter_fn,
        log=log,
        bullet_cap=bullet_cap,
    )
    return log


# ── B12 characterization: the untested scholar paths ────────────────────────


class TestScholarFillerFloor:
    def test_citation_adjacency_gap_fill_dropped_by_filler_floor(self):
        """V0.4.23 on the SCHOLAR path: a quote-grounded gap-fill bullet whose
        main assertion is citation adjacency ("is cited among the authors")
        passes the quote-guard but is dropped by the filler floor before the
        merge — it carries zero content."""
        src = (
            "Marcia (1966) described ego identity development as evolving through "
            "specific decision points about occupational and ideological choices, "
            "a framework later extended by longitudinal research on adolescence."
        )
        llm = (
            "<scholar_reflections>- Missing coverage of Marcia\n"
            "</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Marcia is cited among the authors as relevant to "ego identity '
            'development through specific decision points"\n'
            "</gap_fill_bullets>"
        )
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}
        log = _run_scholar(deps, result, text=src)
        # Quote-grounded (would have merged pre-V0.4.23) BUT filler → dropped.
        assert result["bullet_points"] == ["b1"]
        assert any("Filler floor dropped" in i for i in log.infos())

    def test_content_gap_fill_survives_the_filler_floor(self):
        """A real-content gap-fill bullet (same quote grounding, real
        predicate) is NOT dropped by the filler floor."""
        src = (
            "Marcia (1966) described ego identity development as evolving through "
            "specific decision points about occupational and ideological choices."
        )
        llm = (
            "<scholar_reflections>- Missing coverage of Marcia\n"
            "</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Marcia (1966) framed "ego identity development" as evolving '
            "through decision points on occupational and ideological choices\n"
            "</gap_fill_bullets>"
        )
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}
        log = _run_scholar(deps, result, text=src)
        assert len(result["bullet_points"]) == 2
        assert not any("Filler floor dropped" in i for i in log.infos())


class TestScholarBulletBudgetTrim:
    def test_partial_room_trims_to_budget(self):
        """V0.06 F4-b on the SCHOLAR path: cap - existing = 1 → of 2 grounded
        gap-fill bullets only the FIRST merges; the trim is logged honestly."""
        src = (
            "Marcia (1966) described ego identity development through decision "
            "points. Erikson described identity as a persistent sameness within "
            "oneself and sharing of essential character with others."
        )
        llm = (
            "<scholar_reflections>- Missing coverage\n</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Marcia framed "ego identity development" through decision points\n'
            '- Erikson described identity as "persistent sameness within oneself '
            'and sharing of essential character with others"\n'
            "</gap_fill_bullets>"
        )
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}
        log = _run_scholar(deps, result, text=src, bullet_cap=2)
        # room = cap(2) - existing(1) = 1 → only the first gap bullet merges.
        assert result["bullet_points"] == [
            "b1",
            '- Marcia framed "ego identity development" through decision points',
        ]
        assert any("bullet budget allows 1 more" in i for i in log.infos())


class TestScholarFilterCrash:
    def test_filter_crash_keeps_bullets_unfiltered(self):
        """V18.20.3.4 fail-open: a crashing filter_thinking_bullets callback
        must NOT drop the grounded gap-fill bullets (WARNING logged, bullets
        kept unfiltered)."""
        src = (
            "Marcia (1966) described ego identity development through decision "
            "points about occupational and ideological choices."
        )
        llm = (
            "<scholar_reflections>- Missing coverage\n</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Marcia framed "ego identity development" through decision points '
            "about occupational and ideological choices\n"
            "</gap_fill_bullets>"
        )
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}

        def crashing_filter(bullets, concepts=None, source_text=None):
            raise RuntimeError("filter exploded")

        log = _run_scholar(deps, result, text=src, filter_fn=crashing_filter)
        assert len(result["bullet_points"]) == 2
        assert any("filter crashed" in w for w in log.warnings())


class TestScholarReflectionsOnlyLog:
    def test_reflections_without_gap_fill_logs_could_not_fill(self):
        """A response with a closed non-empty <scholar_reflections> section
        and NO gap-fill bullets → 'identified gaps but could not fill them'."""
        llm = "<scholar_reflections>\n- One gap identified in coverage\n</scholar_reflections>"
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}
        log = _run_scholar(deps, result)
        assert "One gap identified" in result["scholar_reflections"]
        assert result["bullet_points"] == ["b1"]
        assert any("could not fill them" in i for i in log.infos())


class TestScholarGapfillOnlyPreserved:
    def test_gapfill_only_suppresses_but_fills(self):
        """The gapfill-only variant still merges grounded bullets while
        suppressing the reflections text (the delegate contract)."""
        src = (
            "Marcia (1966) described ego identity development through decision "
            "points about occupational and ideological choices."
        )
        llm = (
            "<scholar_reflections>- Missing coverage\n</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Marcia framed "ego identity development" through decision points '
            "about occupational and ideological choices\n"
            "</gap_fill_bullets>"
        )
        deps = _make_deps(llm_responses=[llm])
        result = {"executive_summary": "e", "bullet_points": ["b1"], "thorough_summary": "t"}
        log = _CapturingLog()
        scholar_reflection_gapfill_only(
            "Ch",
            src,
            result,
            max_context_tokens=32768,
            language="en",
            temperature=0.7,
            prompt_manager=deps["prompt_manager"],
            recover_vram=deps["recover_vram"],
            call_llm=deps["call_llm"],  # V0.6.14: was call_fast_llm
            strip_thinking=deps["strip_thinking"],
            log=log,
        )
        assert result["scholar_reflections"] == ""
        assert len(result["bullet_points"]) == 2


# ── B13 structural pins (the V0.6.10 exit funnel) ───────────────────────────


class TestB13ExitFunnelStructure:
    """V0.6.10 (B13): verify_and_polish_summary's 12 copy-pasted exits
    collapse to the single ``_exit`` helper — the D1 deterministic-fix layer
    is structurally guaranteed at every exit (no future exit site can forget
    it). Behavioral D1 coverage: TestVerifyExitFunnel above + the V0.5.4/V0.5.6
    suites (tests/test_v054_verification_layer.py,
    tests/test_v056_verification_glossary.py)."""

    def test_exit_helper_exists_and_is_the_only_deterministic_fix_caller(self):
        import inspect

        import core.summarisation.verification_phase as vp

        assert callable(getattr(vp, "_exit", None))
        exit_src = inspect.getsource(vp._exit)
        # the helper is the old return expression verbatim (one call site)
        assert exit_src.count("_apply_deterministic_fixes(text, issues)") == 1

    def test_verify_body_has_no_direct_deterministic_fix_calls(self):
        import inspect

        import core.summarisation.verification_phase as vp

        body = inspect.getsource(vp.verify_and_polish_summary)
        assert "_apply_deterministic_fixes(" not in body, (
            "every exit must funnel through _exit (the D1 guarantee)"
        )
        # the 12 exits: 11 rendered_md keeps + 1 polished success
        assert body.count("return _exit(rendered_md, issues)") == 11
        assert body.count("return _exit(polished, issues)") == 1


# ── B13 characterization: the exit-funnel contracts ─────────────────────────


class _NoModelSettings:
    """Settings stub: no model configured → the no-LLM exit path."""

    def get(self, key, default=None):
        if key == "summarisation.model":
            return ""
        if key == "summarisation.primary_model":
            return ""
        return default


class TestVerifyExitFunnel:
    def test_no_model_exit_still_applies_deterministic_fixes(self):
        """D1 at the no-model exit: the returned text is en-dash normalized
        even though the LLM was never called (the 12 exits must all funnel
        through the deterministic-fix layer)."""
        rendered = "The author's active years were 1887–1902 in Vienna.\n\n- bullet\n"
        out, issues = verify_and_polish_summary(
            rendered,
            "source text 1887-1902",
            settings=_NoModelSettings(),
        )
        assert "1887-1902" in out
        assert "1887–1902" not in out
        # The normalization is RECORDED as a severity="fix" issue.
        assert any(i.severity == "fix" and "en-dash" in i.detail for i in issues)

    def test_cloud_provider_exit_keeps_original(self):
        """The cloud-provider exit (provider_name not in ollama/llamacpp):
        original kept, no LLM call, deterministic fixes still applied."""
        rendered = "Active years 1887–1902.\n\n- bullet\n"

        class _CloudSettings(_NoModelSettings):
            def get(self, key, default=None):
                if key == "summarisation.model":
                    return "gpt-x"
                if key == "summarisation.model_architecture":
                    return "single_api"
                if key == "summarisation.cloud_provider":
                    return "openai_compatible"
                return default

        out, issues = verify_and_polish_summary(
            rendered, "src 1887-1902", settings=_CloudSettings()
        )
        assert "1887-1902" in out
        assert "1887–1902" not in out

    def test_empty_raw_exit_keeps_original(self):
        """The empty-LLM-response exit: original kept + deterministic fixes
        (the provider returns '' → no corrections path)."""

        class _Provider:
            def complete(self, *, prompt, temperature, max_tokens, model):
                return ""

        import core.summarisation.verification_phase as vp

        _orig = vp.create_provider if hasattr(vp, "create_provider") else None
        # Patch the lazily-imported factory where the module resolves it.
        import core.llm.llm_provider_impl as impl

        orig_create = impl.create_provider
        impl.create_provider = lambda name, settings: _Provider()
        try:

            class _S(_NoModelSettings):
                def get(self, key, default=None):
                    if key == "summarisation.model":
                        return "mock-model"
                    return default

            out, issues = verify_and_polish_summary(
                "Years 1887–1902.\n\n- bullet\n", "src 1887-1902", settings=_S()
            )
        finally:
            impl.create_provider = orig_create
        assert "1887-1902" in out
        assert "1887–1902" not in out
