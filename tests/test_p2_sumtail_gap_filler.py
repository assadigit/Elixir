"""Phase 2 (Test-Net Deepening) — long-tail coverage for gap_filler.py.

``tests/test_gap_filler.py`` covers the main paths (early returns, concept
gap-fill, VRAM recovery, fast-model switch). This file targets the 39
UNCOVERED lines:

  * the ``analysis_exists`` exception path (V17.5 WARNING, line 126-127)
  * the empty-concept skip in the coverage matrix (line 143)
  * the "bullets"/"thorough" location entries in the coverage-matrix log
    (lines 159, 161)
  * the post-gap-fill coverage exception → ``log_swallow`` (lines 290-292)
  * the FULL V17.3 deterministic-judge block (lines 312-373): authors found,
    coverage reported, missing-author targeted gap-fill, the "ALL COVERED"
    branch, and the per-author crash swallow
  * the "no analysis for judge" DEBUG branch (376-380)
  * the V17.5 judge-failure WARNING (381-382)

Hermetic: same stubbing discipline as ``test_gap_filler.py`` — the
``core.preprocessing.deterministic_analyzer`` module is replaced in
sys.modules with a fake and snapshot/RESTORED after every test (the
V18.20.3.5 leak fix).

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_gap_filler.py -q --no-cov``
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

_DA_KEY = "core.preprocessing.deterministic_analyzer"


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))

    def infos(self):
        return [m for m, lvl in self.calls if lvl == "INFO"]

    def warnings(self):
        return [m for m, lvl in self.calls if lvl == "WARNING"]

    def debugs(self):
        return [m for m, lvl in self.calls if lvl == "DEBUG"]


class _FakePromptManager:
    def render_template(self, name, **kw):
        return f"PROMPT name={name} concept={kw.get('concept', '')[:30]}"


@pytest.fixture(autouse=True)
def _restore_deterministic_analyzer():
    """Snapshot/restore sys.modules[DA] — the stub must never leak (V18.20.3.5)."""
    saved = sys.modules.get(_DA_KEY)
    yield
    if saved is None:
        sys.modules.pop(_DA_KEY, None)
    else:
        sys.modules[_DA_KEY] = saved


def _stub_da(
    *,
    exists=False,
    exists_raises=False,
    analysis=None,
    find_raises=False,
    authors=None,
    coverage=None,
):
    """Install a fake core.preprocessing.deterministic_analyzer."""
    mod = types.ModuleType(_DA_KEY)

    def _analysis_exists(output_dir, log_fn=None):
        if exists_raises:
            raise RuntimeError("analysis store unreadable")
        return exists

    def _find_analysis_for_heading(output_dir, heading, log_fn=None):
        if find_raises:
            raise RuntimeError("analysis index corrupted")
        return (None, analysis)

    mod.analysis_exists = _analysis_exists
    mod.find_analysis_for_heading = _find_analysis_for_heading
    mod.extract_authors_from_analysis = lambda a: authors if authors is not None else []
    mod.check_coverage = lambda a, summary: (
        coverage
        or {
            "covered": 0,
            "missing": [],
            "total": 0,
            "coverage_pct": 0.0,
        }
    )
    sys.modules[_DA_KEY] = mod
    return mod


def _make_deps(llm_responses=None):
    responses = list(llm_responses or [])
    idx = {"i": 0}
    llm_calls = []
    setlc_calls = []
    switch_calls = []

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
        i = idx["i"]
        idx["i"] += 1
        llm_calls.append(prompt)
        return responses[i] if i < len(responses) else None

    return {
        "prompt_manager": _FakePromptManager(),
        "recover_vram": lambda context="", delay_sec=0.0, **kw: None,
        "call_fast_llm": call_fast_llm,
        "strip_thinking": lambda t: t,
        "switch_to_fast_model": lambda: switch_calls.append(True),
        "set_last_coverage": lambda pct: setlc_calls.append(pct),
        "_llm_calls": llm_calls,
        "_setlc_calls": setlc_calls,
        "_switch_calls": switch_calls,
    }


def _kwargs(deps, log=None, **overrides):
    kw = dict(
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
        log=log if log is not None else _CapturingLog(),
    )
    kw.update(overrides)
    return kw


# ── 1. analysis_exists exception path ──────────────────────────────────────


class TestAnalysisExistsFailure:
    def test_analysis_exists_crash_logs_warning_and_continues(self):
        """A crashing analysis_exists check logs the V17.5 WARNING and falls
        through to the sequential gap-fill (does NOT early-return)."""
        _stub_da(exists_raises=True)
        deps = _make_deps(llm_responses=["The ego is a bodily structure that develops."])
        log = _CapturingLog()
        content = "The ego is a bodily ego that develops through identification."
        out = gap_fill_concepts(
            "Ch", content, ["b1"], ["ego"], "exec", "thorough", **_kwargs(deps, log)
        )
        # Sequential gap-fill RAN (LLM called despite the analysis_exists crash)
        assert len(deps["_llm_calls"]) == 1
        assert len(out) == 2
        assert any("analysis_exists check failed" in w for w in log.warnings())


# ── 2. Coverage-matrix branches ────────────────────────────────────────────


class TestCoverageMatrix:
    def test_empty_concept_skipped(self):
        """An empty/whitespace concept is skipped in the matrix (not gap-filled,
        not counted in covered/uncovered)."""
        _stub_da(exists=False)
        deps = _make_deps()
        log = _CapturingLog()
        out = gap_fill_concepts(
            "Ch",
            "Some source content about topics.",
            ["b1"],
            ["", "   "],  # both concepts normalize to empty
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        # No uncovered concepts → "all covered" early return (0 of 0 concept
        # coverage → _current_coverage computed as len(covered)/len(concepts)
        # = 0/2 = 0.0 < effective_target... BUT uncovered is empty so the
        # 'not uncovered' branch fires first (line 170).
        assert out == ["b1"]
        assert len(deps["_llm_calls"]) == 0
        # uncovered is empty (both concepts skipped) → the "all covered"
        # early-return fires; len(concepts) counts the skipped ones too
        assert any("All 2 concepts covered" in d for d in log.debugs())

    def test_matrix_locations_reported_per_section(self):
        """The matrix logs where each concept is covered: exec/bullets/thorough."""
        _stub_da(exists=False)
        deps = _make_deps()
        log = _CapturingLog()
        # "identity" is in exec + thorough; "mirror" is in bullets; "shadow"
        # is uncovered (drives the gap-fill skip via no source sentence)
        gap_fill_concepts(
            "Ch",
            "Text that mentions nothing relevant here.",
            ["bullet mentions mirror stage"],
            ["identity", "mirror", "shadow"],
            "identity is defined in the executive summary",
            "the thorough section covers identity again",
            **_kwargs(deps, log),
        )
        matrix = "\n".join(log.debugs())
        assert "identity → exec/thorough" in matrix
        assert "mirror → bullets" in matrix
        assert "shadow → MISSING" in matrix


# ── 3. Post-gap-fill coverage exception ────────────────────────────────────


class TestPostCoverageFailure:
    def test_set_last_coverage_crash_swallowed(self):
        """A crashing set_last_coverage (or coverage computation) is swallowed
        via log_swallow — the function still returns the bullets."""
        _stub_da(exists=False)
        deps = _make_deps()
        deps["set_last_coverage"] = lambda pct: (_ for _ in ()).throw(
            RuntimeError("coverage store closed")
        )
        log = _CapturingLog()
        content = "The ego is a bodily ego."
        out = gap_fill_concepts(
            "Ch",
            content,
            ["b1"],
            ["nonexistent_concept_xyz"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        # Returns normally despite the swallowed exception
        assert out == ["b1"]


# ── 4. V17.3 deterministic judge — the full block ──────────────────────────


class TestDeterministicJudge:
    def _analysis(self):
        return {"authors": ["AuthorX", "AuthorY"]}

    def test_no_analysis_found_skips_judge(self):
        """find_analysis_for_heading → (None, None) → DEBUG 'No analysis found'."""
        _stub_da(exists=False, analysis=None)
        deps = _make_deps()
        log = _CapturingLog()
        gap_fill_concepts(
            "Ch",
            "Source content here.",
            ["b1"],
            ["c1"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        assert any("No analysis found for judge" in d for d in log.debugs())

    def test_judge_crash_logs_v175_warning(self):
        """find_analysis_for_heading raising → V17.5 WARNING, bullets returned."""
        _stub_da(exists=False, find_raises=True)
        deps = _make_deps()
        log = _CapturingLog()
        out = gap_fill_concepts(
            "Ch",
            "Source content here.",
            ["b1"],
            ["c1"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        assert out == ["b1"]
        assert any("Deterministic judge failed" in w for w in log.warnings())

    def test_all_authors_covered(self):
        """Judge finds authors, coverage 100% → 'ALL COVERED' log, no LLM calls."""
        _stub_da(
            exists=False,
            analysis=self._analysis(),
            authors=["AuthorX"],
            coverage={"covered": 1, "missing": [], "total": 1, "coverage_pct": 1.0},
        )
        deps = _make_deps()
        log = _CapturingLog()
        content = "AuthorX wrote extensively about the mirror stage in 1936."
        # Concept "uncovered_xyz" has no source sentence → no sequential calls
        gap_fill_concepts(
            "Ch",
            content,
            ["AuthorX covered the mirror stage."],
            ["uncovered_xyz"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        assert any("ALL COVERED" in i for i in log.infos())
        assert deps["_llm_calls"] == []

    def test_missing_authors_gap_filled(self):
        """Judge finds missing authors → targeted gap-fill appends '- bullet'."""
        _stub_da(
            exists=False,
            analysis=self._analysis(),
            authors=["AuthorX", "AuthorY"],
            coverage={
                "covered": 1,
                "missing": ["AuthorY"],
                "total": 2,
                "coverage_pct": 0.5,
            },
        )
        deps = _make_deps(llm_responses=["AuthorY described the mirror stage in infants."])
        log = _CapturingLog()
        content = (
            "AuthorX wrote about the ego. AuthorY described the mirror stage "
            "in infants during 1949."
        )
        out = gap_fill_concepts(
            "Ch",
            content,
            ["AuthorX wrote about the ego."],
            ["uncovered_zz"],  # no source sentence → no sequential gap-fill call
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        # The sequential concept had no relevant sentence → 0 calls there;
        # the judge's missing-author gap-fill made exactly 1 LLM call
        assert len(deps["_llm_calls"]) == 1
        assert len(out) == 2
        assert out[1].startswith("- ")  # V17.3 appends with the bullet marker
        assert "AuthorY" in out[1]
        assert any("Added gap-fill for 'AuthorY'" in i for i in log.infos())

    def test_missing_author_llm_crash_swallowed(self):
        """A crashing LLM call inside the per-author loop is swallowed (B4)."""
        _stub_da(
            exists=False,
            analysis=self._analysis(),
            authors=["AuthorY"],
            coverage={"covered": 0, "missing": ["AuthorY"], "total": 1, "coverage_pct": 0.0},
        )

        def _crash(prompt, max_tokens=None, temperature=None, **kw):
            raise RuntimeError("fast model exploded")

        deps = _make_deps()
        deps["call_fast_llm"] = _crash
        log = _CapturingLog()
        content = "AuthorY described the mirror stage in infants during 1949."
        out = gap_fill_concepts(
            "Ch",
            content,
            ["existing bullet"],
            ["uncovered_zz"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        # The crash is swallowed — original bullets returned unchanged
        assert out == ["existing bullet"]

    def test_missing_author_no_source_sentence_skipped(self):
        """A missing author with no source sentence is skipped (no LLM call)."""
        _stub_da(
            exists=False,
            analysis=self._analysis(),
            authors=["AuthorZ"],
            coverage={"covered": 0, "missing": ["AuthorZ"], "total": 1, "coverage_pct": 0.0},
        )
        deps = _make_deps()
        log = _CapturingLog()
        content = "This content never mentions the missing author at all."
        out = gap_fill_concepts(
            "Ch",
            content,
            ["existing bullet"],
            ["uncovered_zz"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        assert deps["_llm_calls"] == []
        assert out == ["existing bullet"]

    def test_gap_bullet_length_bounds_respected(self):
        """Judge gap-bullets outside (10, 300) chars are dropped."""
        _stub_da(
            exists=False,
            analysis=self._analysis(),
            authors=["AuthorY"],
            coverage={"covered": 0, "missing": ["AuthorY"], "total": 1, "coverage_pct": 0.0},
        )
        # Response longer than 300 chars → rejected by the length bound
        long_response = "AuthorY " + "very " * 100 + "much."
        deps = _make_deps(llm_responses=[long_response])
        log = _CapturingLog()
        content = "AuthorY described the mirror stage in infants during 1949."
        out = gap_fill_concepts(
            "Ch",
            content,
            ["existing bullet"],
            ["uncovered_zz"],
            "exec",
            "thorough",
            **_kwargs(deps, log),
        )
        assert out == ["existing bullet"]
