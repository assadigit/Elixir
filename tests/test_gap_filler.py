"""V18.12 (Phase 5 Stage 3, Batch 2.7) — gap_filler characterization tests.

Byte-for-byte stability gate for ``gap_fill_concepts`` extracted from
``Summarizer._gap_fill_concepts``. Uses mocked ``call_fast_llm`` /
``prompt_manager`` / ``recover_vram`` / ``switch_to_fast_model`` /
``set_last_coverage`` and stubs the local imports
(``analysis_exists``, ``find_analysis_for_heading``, ``check_coverage``,
``extract_authors_from_analysis``).

Run: pytest tests/test_gap_filler.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.gap_filler import gap_fill_concepts


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


class _FakePromptManager:
    def render_template(self, name, **kw):
        return f"PROMPT name={name} concept={kw.get('concept', '')[:30]} ctx={kw.get('context', '')[:40]}..."


def _stub_analysis_exists(exists: bool):
    """Install a fake core.preprocessing.deterministic_analyzer with analysis_exists.

    V18.20.3.5 (test-infra): the stub REPLACES the real module in
    sys.modules and every test in this file relied on it leaking for the
    duration of the test — but it was never RESTORED, so any test file
    collected after this one that imports check_coverage /
    extract_authors_from_analysis got the stub (empty results) instead of
    the real functions. The snapshot/restore autouse fixture below now
    puts the real module back after each test.
    """
    mod = types.ModuleType("core.preprocessing.deterministic_analyzer")
    mod.analysis_exists = lambda output_dir, log_fn=None: exists
    # Also stub the find/check/extract functions used in the V17.3 judge
    mod.find_analysis_for_heading = lambda output_dir, heading, log_fn=None: (None, None)
    mod.check_coverage = lambda analysis, summary: {
        "covered": 0,
        "missing": [],
        "total": 0,
        "coverage_pct": 0.0,
    }
    mod.extract_authors_from_analysis = lambda analysis: []
    sys.modules["core.preprocessing.deterministic_analyzer"] = mod
    return mod


@pytest.fixture(autouse=True)
def _restore_deterministic_analyzer():
    """V18.20.3.5: snapshot sys.modules['core.preprocessing.
    deterministic_analyzer'] before each test and restore it after —
    the stub above used to leak across file boundaries."""
    key = "core.preprocessing.deterministic_analyzer"
    saved = sys.modules.get(key)
    yield
    if saved is None:
        sys.modules.pop(key, None)
    else:
        sys.modules[key] = saved


def _make_deps(
    *,
    llm_responses=None,
    llm_raises=None,
):
    """Build mock deps for gap_fill_concepts."""
    if llm_responses is None:
        llm_responses = []
    responses = list(llm_responses)
    idx = {"i": 0}
    llm_calls = []
    rvram_calls = []
    switch_calls = []
    setlc_calls = []

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
        i = idx["i"]
        idx["i"] += 1
        llm_calls.append({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})
        if llm_raises is not None and i < len(llm_raises) and llm_raises[i]:
            raise llm_raises[i]
        if i < len(responses):
            return responses[i]
        return None

    def recover_vram(context="", delay_sec=0.0, **kw):
        rvram_calls.append({"context": context, "delay_sec": delay_sec})

    def strip_thinking(text):
        return text  # identity

    def switch_to_fast_model():
        switch_calls.append(True)

    def set_last_coverage(pct):
        setlc_calls.append(pct)

    return {
        "prompt_manager": _FakePromptManager(),
        "recover_vram": recover_vram,
        "call_fast_llm": call_fast_llm,
        "strip_thinking": strip_thinking,
        "switch_to_fast_model": switch_to_fast_model,
        "set_last_coverage": set_last_coverage,
        "_llm_calls": llm_calls,
        "_rvram_calls": rvram_calls,
        "_switch_calls": switch_calls,
        "_setlc_calls": setlc_calls,
    }


def _common_kwargs(deps):
    return dict(
        output_dir="/tmp/test_output",
        temperature=0.7,
        effective_target=0.85,
        overdeliver_enabled=True,
        overdeliver_target=1.0,
        coverage_threshold=0.70,
        prompt_manager=deps["prompt_manager"],
        recover_vram=deps["recover_vram"],
        call_fast_llm=deps["call_fast_llm"],
        strip_thinking=deps["strip_thinking"],
        switch_to_fast_model=deps["switch_to_fast_model"],
        set_last_coverage=deps["set_last_coverage"],
        log=_CapturingLog(),
    )


# ── 1. early-return paths ──────────────────────────────────────────────────


class TestEarlyReturns:
    def test_no_concepts_returns_unchanged(self):
        """concepts=[] → returns bullets unchanged (no LLM call)."""
        _stub_analysis_exists(False)
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        out = gap_fill_concepts(
            "Ch", "content", ["b1"], [], "e", "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out == ["b1"]
        assert len(deps["_llm_calls"]) == 0

    def test_no_bullets_returns_unchanged(self):
        """bullets=[] → returns [] unchanged (no LLM call)."""
        _stub_analysis_exists(False)
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        out = gap_fill_concepts(
            "Ch", "content", [], ["c1"], "e", "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out == []
        assert len(deps["_llm_calls"]) == 0

    def test_analysis_exists_skips_sequential_gap_fill(self):
        """When deterministic analysis exists, the V17.4 early-return skips
        the old sequential gap-fill (no LLM call)."""
        _stub_analysis_exists(True)
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        cap = _common_kwargs(deps)
        cap["log"] = _CapturingLog()
        out = gap_fill_concepts(
            "Ch", "content", ["b1"], ["c1"], "e", "t", **{k: v for k, v in cap.items()}
        )
        assert out == ["b1"]  # unchanged
        assert len(deps["_llm_calls"]) == 0
        infos = [m for m, l in cap["log"].calls if l == "INFO"]
        assert any("Deterministic analysis found" in i for i in infos)

    def test_all_concepts_covered_skips_gap_fill(self):
        """When all concepts are already covered, returns bullets unchanged
        (no LLM call, no VRAM recovery)."""
        _stub_analysis_exists(False)
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        # The concept "identity" appears in the exec_summary → covered
        out = gap_fill_concepts(
            "Ch",
            "content",
            ["b1"],
            ["identity"],
            "identity is defined",
            "t",
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out == ["b1"]
        assert len(deps["_llm_calls"]) == 0
        assert len(deps["_rvram_calls"]) == 0

    def test_coverage_above_effective_target_skips_gap_fill(self):
        """When current coverage >= effective_target (but not 100%, so the
        'all covered' branch is skipped), gap-fill is skipped via the
        coverage-threshold branch."""
        _stub_analysis_exists(False)
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        cap = _common_kwargs(deps)
        cap["log"] = _CapturingLog()
        # 2 concepts: 1 covered (in exec), 1 not covered → 50% coverage.
        # But effective_target=0.85 → 50% < 85% → gap-fill would NOT skip.
        # To test the skip path, set effective_target LOW so coverage >= target.
        cap["effective_target"] = 0.40  # 50% >= 40% → skip
        out = gap_fill_concepts(
            "Ch",
            "content with identity word",
            ["b1"],
            ["identity", "missing_concept_xyz"],
            "identity is defined here",
            "t",
            **{k: v for k, v in cap.items()},
        )
        assert out == ["b1"]
        assert len(deps["_llm_calls"]) == 0
        infos = [m for m, l in cap["log"].calls if l == "INFO"]
        assert any("Gap-fill skipped" in i for i in infos)


# ── 2. concept gap-fill ────────────────────────────────────────────────────


class TestConceptGapFill:
    def test_uncovered_concept_gap_filled(self):
        """An uncovered concept with a source sentence is gap-filled: the LLM
        returns a bullet, which is appended to bullets."""
        _stub_analysis_exists(False)
        # concept "ego" does NOT appear in exec/bullets/thorough → uncovered
        # content has a sentence with "ego" → relevant source sentence found
        content = (
            "The ego is first and foremost a bodily ego. The ego develops through identifications."
        )
        llm_resp = "The ego is a bodily structure that develops through identifications."
        deps = _make_deps(llm_responses=[llm_resp])
        cap = _common_kwargs(deps)
        cap["log"] = _CapturingLog()
        out = gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["ego"],
            "exec summary",
            "thorough summary",
            **{k: v for k, v in cap.items()},
        )
        # The gap-fill bullet was added
        assert len(out) == 2
        assert "bodily" in out[1].lower() or "ego" in out[1].lower()
        # set_last_coverage was called with the post-gap-fill coverage %
        assert len(deps["_setlc_calls"]) == 1
        # "ego" still not in the summary text (the bullet doesn't contain "ego" literally),
        # so coverage might still be 0/1 = 0.0 OR 1/1 = 1.0 depending on whether the bullet
        # text contains the concept. The bullet "The ego is a bodily structure..." DOES contain "ego".
        # So post-coverage = 1/1 = 1.0.
        assert deps["_setlc_calls"][0] == 1.0
        # An INFO log about gap-fill success
        infos = [m for m, l in cap["log"].calls if l == "INFO"]
        assert any("Gap-fill: added 1 bullets" in i for i in infos)

    def test_gap_fill_llm_exception_skipped(self):
        """If the LLM call raises, the concept is skipped (WARNING) but the
        method continues and returns the original bullets."""
        _stub_analysis_exists(False)
        content = "The ego is a bodily ego."
        deps = _make_deps(llm_responses=[None], llm_raises=[RuntimeError("crashed")])
        cap = _common_kwargs(deps)
        cap["log"] = _CapturingLog()
        out = gap_fill_concepts(
            "Ch", content, ["b1"], ["ego"], "exec", "thorough", **{k: v for k, v in cap.items()}
        )
        assert out == ["b1"]  # unchanged (the crash skipped the concept)
        warnings = [m for m, l in cap["log"].calls if l == "WARNING"]
        assert any("Gap-fill call 1 crashed" in w for w in warnings)

    def test_no_relevant_source_sentence_skips_concept(self):
        """If no source sentence contains the uncovered concept, the concept
        is skipped (no LLM call for it)."""
        _stub_analysis_exists(False)
        # content has NO sentence containing "uncovered_concept_xyz"
        content = "Some unrelated source text about other topics entirely."
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        out = gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["uncovered_concept_xyz"],
            "exec",
            "thorough",
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        # No LLM call (concept had no relevant source sentence)
        assert len(deps["_llm_calls"]) == 0
        # bullets unchanged
        assert out == ["b1"]

    def test_vram_recovery_between_concepts(self):
        """recover_vram is called before the first concept (pre-gap-fill, 30s)
        and before each subsequent concept (gap-fill-N, 30s)."""
        _stub_analysis_exists(False)
        content = "Concept alpha is defined here. Concept beta is described here. Concept gamma is mentioned here."
        # 3 uncovered concepts → 3 LLM calls → recover_vram before #1 (pre-gap-fill) + before #2 + #3
        deps = _make_deps(llm_responses=["bullet a", "bullet b", "bullet c"])
        gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["alpha", "beta", "gamma"],
            "exec",
            "thorough",
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        # pre-gap-fill (30s) + gap-fill-2 (30s) + gap-fill-3 (30s) = 3 recover_vram calls
        assert len(deps["_rvram_calls"]) == 3
        contexts = [c["context"] for c in deps["_rvram_calls"]]
        assert contexts == ["pre-gap-fill", "gap-fill-2", "gap-fill-3"]
        assert all(c["delay_sec"] == 30.0 for c in deps["_rvram_calls"])

    def test_switch_to_fast_model_called_on_first_concept(self):
        """switch_to_fast_model is called exactly once, on the first gap-fill call."""
        _stub_analysis_exists(False)
        content = "Concept alpha here. Concept beta here."
        deps = _make_deps(llm_responses=["bullet a", "bullet b"])
        gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["alpha", "beta"],
            "exec",
            "thorough",
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert len(deps["_switch_calls"]) == 1  # only on _gi == 0


# ── 3. byte-for-byte stability ──────────────────────────────────────────────


class TestByteForByte:
    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same output bullets across calls."""
        _stub_analysis_exists(False)
        content = "The ego is a bodily ego."

        def _run():
            deps = _make_deps(llm_responses=["The ego is a bodily structure."])
            return gap_fill_concepts(
                "Ch",
                content,
                ["b1"],
                ["ego"],
                "exec",
                "thorough",
                **{k: v for k, v in _common_kwargs(deps).items()},
            )

        assert _run() == _run()

    def test_returns_list_of_strings(self):
        """Returns a list of str (the bullets)."""
        _stub_analysis_exists(False)
        content = "The ego is a bodily ego."
        deps = _make_deps(llm_responses=["The ego is a bodily structure."])
        out = gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["ego"],
            "exec",
            "thorough",
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert isinstance(out, list)
        assert all(isinstance(x, str) for x in out)

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        _stub_analysis_exists(False)
        content = "The ego is a bodily ego."
        deps = _make_deps(llm_responses=["The ego is a bodily structure."])
        kw = _common_kwargs(deps)
        kw.pop("log")
        out = gap_fill_concepts(
            "Ch", content, ["b1"], ["ego"], "exec", "thorough", **{k: v for k, v in kw.items()}
        )
        assert isinstance(out, list)
