"""V18.15.3 (Phase 5 Stage 3, Batch 4.5) — coverage_guarantee characterization tests.

Byte-for-byte stability gate for ``apply_3tier_coverage`` extracted from
``Summarizer._apply_3tier_coverage``. Mocked callbacks so no real LLM is
invoked.

Branches covered:
1. coverage >= threshold → short-circuit return (no gap-fill)
2. no missing keywords → return coverage (no gap-fill)
3. Tier 2 gap-fill appends filtered bullets + sets model tag "+gapfill"
4. max_bullets cap applied after gap-fill
5. Tier 3 force_insert called when coverage2 < threshold
6. coverage breakdown log + GUARANTEED log when final >= threshold
7. filtered-empty bullet dropped (DEBUG drop log)
8. combined string includes key_distinctions + theoretical_tensions

Run: pytest tests/test_coverage_guarantee.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E: pass
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules['tiktoken'] = tk

from core.summarisation.coverage_guarantee import apply_3tier_coverage


def _base_result(bullets=None, exec_summary="exec", thorough="thorough",
                 kd="", tt=""):
    return {
        "bullet_points": list(bullets or []),
        "executive_summary": exec_summary,
        "thorough_summary": thorough,
        "key_distinctions": kd,
        "theoretical_tensions": tt,
        "model": "primary",
    }


class TestApply3TierCoverage:

    def test_threshold_satisfied_short_circuits(self):
        """coverage >= threshold → return coverage immediately, no gap-fill."""
        logs = []
        gapfill_calls = {"n": 0}
        def gapfill(*a):
            gapfill_calls["n"] += 1
            return []
        result = _base_result()
        ret = apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.90,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw1"],
            log=lambda m, l="INFO": logs.append((m, l)),
            targeted_gap_fill=gapfill,
            filter_thinking_bullets=lambda b: b,
            max_bullets_per_chapter=30,
            compute_coverage=lambda s, c: 0.0,
            force_insert_missing=lambda t, m, r: None,
        )
        assert ret == 0.90
        assert gapfill_calls["n"] == 0
        assert logs == []  # short-circuit before any log

    def test_round_float_edge_case_short_circuits(self):
        """round(coverage, 2) >= threshold → short-circuit (V13.34.2)."""
        # 0.849999 rounded to 0.85 == threshold 0.85 → short-circuit
        result = _base_result()
        ret = apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.849999,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw1"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=lambda *a: [],
            filter_thinking_bullets=lambda b: b,
            compute_coverage=lambda s, c: 0.0,
            force_insert_missing=lambda t, m, r: None,
        )
        assert ret == 0.849999

    def test_no_missing_keywords_returns_coverage(self):
        """All keywords present in combined → return coverage (no gap-fill)."""
        gapfill_calls = {"n": 0}
        def gapfill(*a):
            gapfill_calls["n"] += 1
            return []
        result = _base_result(bullets=["identity"], exec_summary="phase")
        # keywords 'identity' and 'phase' both in combined → none missing
        ret = apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.50,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["identity", "phase"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=gapfill,
            filter_thinking_bullets=lambda b: b,
            compute_coverage=lambda s, c: 0.0,
            force_insert_missing=lambda t, m, r: None,
        )
        assert ret == 0.50
        assert gapfill_calls["n"] == 0

    def test_tier2_gapfill_appends_and_sets_model_tag(self):
        """Tier 2: gap-fill returns bullets → filtered + appended + '+gapfill' tag."""
        result = _base_result(bullets=["existing"])
        def gapfill(heading, text, missing):
            return ["new bullet 1", "new bullet 2"]
        # filter passes everything through
        def filt(bullets):
            return list(bullets)
        ret = apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["missing_kw"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=gapfill,
            filter_thinking_bullets=filt,
            max_bullets_per_chapter=30,
            compute_coverage=lambda s, c: 0.95,  # final >= threshold
            force_insert_missing=lambda t, m, r: None,
        )
        assert "new bullet 1" in result["bullet_points"]
        assert "new bullet 2" in result["bullet_points"]
        assert result["model"] == "primary+gapfill"
        assert ret == 0.95

    def test_max_bullets_cap_applied(self):
        """max_bullets_per_chapter caps the bullet list after gap-fill."""
        result = _base_result(bullets=["b0"])
        def gapfill(*a):
            return [f"new{i}" for i in range(10)]
        def filt(b):
            return list(b)
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=gapfill,
            filter_thinking_bullets=filt,
            max_bullets_per_chapter=3,  # cap at 3
            compute_coverage=lambda s, c: 0.95,
            force_insert_missing=lambda t, m, r: None,
        )
        assert len(result["bullet_points"]) == 3

    def test_tier3_force_insert_called_when_coverage2_low(self):
        """coverage2 < threshold → force_insert_missing invoked."""
        force_calls = {"n": 0, "args": None}
        def force(text, missing, result):
            force_calls["n"] += 1
            force_calls["args"] = (text, list(missing), result)
        result = _base_result(bullets=["b"])
        # coverage2 returns 0.50 (< 0.85 threshold) → force_insert called
        # coverage3 returns 0.90 (>= threshold)
        cov_returns = iter([0.50, 0.90])
        def cov(s, c):
            return next(cov_returns)
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["missing_kw"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=lambda *a: [],
            filter_thinking_bullets=lambda b: b,
            compute_coverage=cov,
            force_insert_missing=force,
        )
        assert force_calls["n"] == 1
        assert "missing_kw" in force_calls["args"][1]

    def test_tier3_skipped_when_coverage2_meets_threshold(self):
        """coverage2 >= threshold → force_insert NOT called."""
        force_calls = {"n": 0}
        def force(*a):
            force_calls["n"] += 1
        result = _base_result(bullets=["b"])
        cov_returns = iter([0.90, 0.90])
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw"],
            log=lambda m, l="INFO": None,
            targeted_gap_fill=lambda *a: [],
            filter_thinking_bullets=lambda b: b,
            compute_coverage=lambda s, c: next(cov_returns),
            force_insert_missing=force,
        )
        assert force_calls["n"] == 0

    def test_coverage_breakdown_log_and_guaranteed_log(self):
        """final >= threshold → both breakdown INFO log + GUARANTEED log."""
        logs = []
        result = _base_result(bullets=["b"])
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw"],
            log=lambda m, l="INFO": logs.append((m, l)),
            targeted_gap_fill=lambda *a: [],
            filter_thinking_bullets=lambda b: b,
            compute_coverage=lambda s, c: 0.95,
            force_insert_missing=lambda t, m, r: None,
        )
        infos = [m for m, l in logs if l == "INFO"]
        assert any("Coverage breakdown" in m for m in infos)
        assert any("GUARANTEED" in m for m in infos)

    def test_filtered_empty_bullet_dropped_with_debug_log(self):
        """filter returns [] → bullet dropped, DEBUG drop log emitted."""
        logs = []
        result = _base_result(bullets=["existing"])
        def gapfill(*a):
            return ["leaky bullet"]
        def filt(b):
            return []  # filter drops everything
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: ["kw"],
            log=lambda m, l="INFO": logs.append((m, l)),
            targeted_gap_fill=gapfill,
            filter_thinking_bullets=filt,
            compute_coverage=lambda s, c: 0.95,
            force_insert_missing=lambda t, m, r: None,
        )
        assert "leaky bullet" not in result["bullet_points"]
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert any("Dropped Tier 2 gap-fill bullet" in m for m in debugs)

    def test_combined_includes_kd_and_tt(self):
        """key_distinctions + theoretical_tensions included in coverage check."""
        kd_seen = {"v": False}
        def extract(c, n=18):
            # return a keyword that's ONLY in kd/tt, not in exec/thorough/bullets
            return ["special_kw"]
        result = _base_result(bullets=["b"], exec_summary="exec",
                              thorough="thorough", kd="special_kw", tt="tensions")
        # 'special_kw' is in kd → not missing → no gap-fill
        gapfill_calls = {"n": 0}
        apply_3tier_coverage(
            "h", "text", "content", result, coverage=0.40,
            coverage_threshold=0.85,
            extract_keywords=extract,
            log=lambda m, l="INFO": None,
            targeted_gap_fill=lambda *a: (gapfill_calls.__setitem__("n", gapfill_calls["n"]+1), [])[1],
            filter_thinking_bullets=lambda b: b,
            compute_coverage=lambda s, c: 0.95,
            force_insert_missing=lambda t, m, r: None,
        )
        assert gapfill_calls["n"] == 0  # special_kw found in kd → not missing
