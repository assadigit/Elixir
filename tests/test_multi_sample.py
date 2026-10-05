"""V18.11 (Phase 5 Stage 3, Batch 2.2) — multi_sample characterization tests.

Byte-for-byte stability gate for ``multi_sample_summarize`` extracted from
``Summarizer._multi_sample_summarize``. Uses mocked ``summarize_with_model`` /
``compute_coverage`` / ``b3_cloud_judge`` to capture the B3 voting flow.

Run: pytest tests/test_multi_sample.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.multi_sample import multi_sample_summarize


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _sample(exec_sum: str, bullets: list, thorough: str) -> dict:
    return {
        "executive_summary": exec_sum,
        "bullet_points": bullets,
        "thorough_summary": thorough,
    }


def _make_deps(
    *,
    sample_results=None,
    sample_raises=None,
    coverage_map=None,
    b3_judge_result=None,
):
    """Build mock deps. sample_results is a list of dicts (one per sample).
    sample_raises is a list of bools (True = that sample raises)."""
    if sample_results is None:
        sample_results = []
    if sample_raises is None:
        sample_raises = [False] * len(sample_results)
    if coverage_map is None:
        coverage_map = {}
    swm_calls = []
    rvram_calls = []
    cov_calls = []
    judge_calls = []

    def summarize_with_model(
        heading, text, model, temp, with_cot=True, concepts=None, callouts=None, **kw
    ):
        swm_calls.append({"heading": heading, "model": model, "temp": temp})
        idx = len(swm_calls) - 1
        if idx < len(sample_raises) and sample_raises[idx]:
            raise RuntimeError(f"sample {idx + 1} crashed")
        if idx < len(sample_results):
            return sample_results[idx]
        return None

    def recover_vram(context="", delay_sec=0.0, **kw):
        rvram_calls.append({"context": context, "delay_sec": delay_sec})

    def compute_coverage(source, summary):
        cov_calls.append({"source": source, "summary": summary})
        # Deterministic coverage: look up the summary in coverage_map, else 0.5
        return coverage_map.get(summary, 0.5)

    def b3_cloud_judge(samples, source, heading):
        judge_calls.append({"n_samples": len(samples), "heading": heading})
        if b3_judge_result is not None:
            return b3_judge_result
        return (samples[0]["executive_summary"], samples[0]["thorough_summary"])

    return {
        "recover_vram": recover_vram,
        "summarize_with_model": summarize_with_model,
        "b3_cloud_judge": b3_cloud_judge,
        "compute_coverage": compute_coverage,
        "_swm_calls": swm_calls,
        "_rvram_calls": rvram_calls,
        "_cov_calls": cov_calls,
        "_judge_calls": judge_calls,
    }


def _common_kwargs(deps):
    return dict(
        primary_model="test-model",
        temperature=0.7,
        recover_vram=deps["recover_vram"],
        summarize_with_model=deps["summarize_with_model"],
        b3_cloud_judge=deps["b3_cloud_judge"],
        compute_coverage=deps["compute_coverage"],
        conservative_drops=False,
        quarantine=None,
        current_heading="Chapter 1",
        fusion_enabled=False,
        fusion_use_for_b3_judge=False,
        log=_CapturingLog(),
    )


# ── 1. no samples ─────────────────────────────────────────────────────────


class TestMultiSampleNoSamples:
    def test_all_samples_fail_returns_none(self):
        """If every sample raises (or returns None), returns None."""
        deps = _make_deps(
            sample_results=[None, None, None],
            sample_raises=[True, True, True],
        )
        out = multi_sample_summarize(
            "Ch", "text", n_samples=3, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out is None

    def test_all_samples_return_none(self):
        """If every sample returns None (no crash, just empty), returns None."""
        deps = _make_deps(sample_results=[None, None, None])
        out = multi_sample_summarize(
            "Ch", "text", n_samples=3, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out is None


# ── 2. single sample ──────────────────────────────────────────────────────


class TestMultiSampleSingle:
    def test_single_sample_returned_as_is(self):
        """If only 1 sample succeeds, it's returned directly (no voting)."""
        one = _sample("Exec one.", ["Bullet one.", "Bullet two."], "Thorough one.")
        deps = _make_deps(
            sample_results=[one, None, None],
            sample_raises=[False, True, True],
        )
        out = multi_sample_summarize(
            "Ch", "text", n_samples=3, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        # Single sample → returned as-is (the dict, not wrapped)
        assert out is one
        assert out["executive_summary"] == "Exec one."


# ── 3. N-sample voting ────────────────────────────────────────────────────


class TestMultiSampleVoting:
    def test_voted_bullets_keep_all_unique(self):
        """Threshold=1: keep any bullet from any sample (unique by normalized
        text). Bullets appearing in multiple samples are deduped to 1."""
        s1 = _sample("Exec 1.", ["Bullet alpha here.", "Bullet beta here."], "Thorough 1.")
        s2 = _sample("Exec 2.", ["Bullet alpha here.", "Bullet gamma here."], "Thorough 2.")
        s3 = _sample("Exec 3.", ["Bullet beta here.", "Bullet delta here."], "Thorough 3.")
        deps = _make_deps(
            sample_results=[s1, s2, s3],
            coverage_map={
                "Exec 1.": 0.8,
                "Exec 2.": 0.5,
                "Exec 3.": 0.6,
                "Thorough 1.": 0.5,
                "Thorough 2.": 0.9,
                "Thorough 3.": 0.4,
            },
        )
        out = multi_sample_summarize(
            "Ch", "text", n_samples=3, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        # Voted bullets: alpha (s1+s2), beta (s1+s3), gamma (s2), delta (s3) → 4 unique
        assert len(out["bullet_points"]) == 4
        # Best exec by coverage = "Exec 1." (0.8)
        assert out["executive_summary"] == "Exec 1."
        # Best thorough by coverage = "Thorough 2." (0.9)
        assert out["thorough_summary"] == "Thorough 2."
        assert out["model"] == "multi_sample_voted"
        assert out["temperature"] == "voted"

    def test_per_sample_vram_recovery_between_samples(self):
        """recover_vram is called before each sample EXCEPT the first
        (i > 0). With n_samples=3, expect 2 recover_vram calls."""
        s = _sample("E.", ["B."], "T.")
        deps = _make_deps(sample_results=[s, s, s])
        multi_sample_summarize(
            "Ch", "text", n_samples=3, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert len(deps["_rvram_calls"]) == 2  # before sample 2 and 3
        # The contexts are B3-sample-2 and B3-sample-3
        contexts = [c["context"] for c in deps["_rvram_calls"]]
        assert contexts == ["B3-sample-2", "B3-sample-3"]

    def test_one_sample_crash_doesnt_kill_others(self):
        """If sample 2 raises, samples 1 and 3 still run; the result is built
        from the 2 surviving samples (voting + coverage pick)."""
        s1 = _sample("Exec 1.", ["Bullet one."], "Thorough 1.")
        s3 = _sample("Exec 3.", ["Bullet three."], "Thorough 3.")
        deps = _make_deps(
            sample_results=[s1, None, s3],
            sample_raises=[False, True, False],
            coverage_map={"Exec 1.": 0.7, "Exec 3.": 0.5, "Thorough 1.": 0.4, "Thorough 3.": 0.8},
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out = multi_sample_summarize("Ch", "text", n_samples=3, **{k: v for k, v in kw.items()})
        # 2 surviving samples → voted bullets from both
        assert len(out["bullet_points"]) == 2
        # A WARNING-level log call about the crashed sample 2 (check the raw
        # calls list — level == WARNING and message mentions 'crashed').
        assert any(l == "WARNING" and "crashed" in m for m, l in cap.calls), (
            f"expected a WARNING about the crash; got calls={cap.calls!r}"
        )


# ── 4. fusion judge path ──────────────────────────────────────────────────


class TestMultiSampleFusionJudge:
    def test_fusion_judge_used_when_enabled(self):
        """When fusion_enabled AND fusion_use_for_b3_judge AND >1 sample,
        b3_cloud_judge is called (coverage pick is NOT). The real
        _b3_cloud_judge returns (best_exec_sample, best_thorough_sample) —
        sample DICTS, not strings (the caller does .get() on them)."""
        s1 = _sample("Exec 1.", ["B1."], "Thorough 1.")
        s2 = _sample("Exec 2.", ["B2."], "Thorough 2.")
        # The judge returns sample dicts; we craft dicts whose .get() yields
        # the judged exec/thorough (the real _b3_cloud_judge returns samples[i]).
        judged_exec = {"executive_summary": "JUDGED EXEC", "thorough_summary": "irrelevant"}
        judged_thorough = {"executive_summary": "irrelevant", "thorough_summary": "JUDGED THOROUGH"}
        deps = _make_deps(
            sample_results=[s1, s2],
            b3_judge_result=(judged_exec, judged_thorough),
        )
        kw = _common_kwargs(deps)
        kw["fusion_enabled"] = True
        kw["fusion_use_for_b3_judge"] = True
        out = multi_sample_summarize("Ch", "text", n_samples=2, **{k: v for k, v in kw.items()})
        # The judge was called
        assert len(deps["_judge_calls"]) == 1
        # The judge's picks are used (not the coverage max)
        assert out["executive_summary"] == "JUDGED EXEC"
        assert out["thorough_summary"] == "JUDGED THOROUGH"
        # coverage was NOT called for the exec/thorough pick
        assert len(deps["_cov_calls"]) == 0

    def test_fusion_disabled_uses_coverage_pick(self):
        """When fusion_enabled=False, coverage pick is used (b3_cloud_judge
        is NOT called)."""
        s1 = _sample("Exec 1.", ["B1."], "Thorough 1.")
        s2 = _sample("Exec 2.", ["B2."], "Thorough 2.")
        deps = _make_deps(
            sample_results=[s1, s2],
            coverage_map={"Exec 1.": 0.9, "Exec 2.": 0.3, "Thorough 1.": 0.2, "Thorough 2.": 0.8},
        )
        kw = _common_kwargs(deps)
        kw["fusion_enabled"] = False
        out = multi_sample_summarize("Ch", "text", n_samples=2, **{k: v for k, v in kw.items()})
        # Judge NOT called
        assert len(deps["_judge_calls"]) == 0
        # Coverage picked the max
        assert out["executive_summary"] == "Exec 1."
        assert out["thorough_summary"] == "Thorough 2."

    def test_fusion_enabled_but_single_sample_skips_judge(self):
        """fusion_enabled + single surviving sample → no judge (len(samples)<=1
        short-circuits before the fusion branch)."""
        s1 = _sample("Exec 1.", ["B1."], "Thorough 1.")
        deps = _make_deps(sample_results=[s1, None, None], sample_raises=[False, True, True])
        kw = _common_kwargs(deps)
        kw["fusion_enabled"] = True
        kw["fusion_use_for_b3_judge"] = True
        out = multi_sample_summarize("Ch", "text", n_samples=3, **{k: v for k, v in kw.items()})
        # Single sample → returned as-is (no judge, no voting)
        assert out is s1
        assert len(deps["_judge_calls"]) == 0


# ── 5. byte-for-byte stability ────────────────────────────────────────────


class TestMultiSampleByteForByte:
    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same output dict across calls."""
        s1 = _sample("Exec 1.", ["Bullet alpha."], "Thorough 1.")
        s2 = _sample("Exec 2.", ["Bullet beta."], "Thorough 2.")

        def _run():
            deps = _make_deps(
                sample_results=[s1, s2],
                coverage_map={
                    "Exec 1.": 0.8,
                    "Exec 2.": 0.5,
                    "Thorough 1.": 0.5,
                    "Thorough 2.": 0.9,
                },
            )
            return multi_sample_summarize(
                "Ch", "text", n_samples=2, **{k: v for k, v in _common_kwargs(deps).items()}
            )

        r1 = _run()
        r2 = _run()
        assert r1 == r2

    def test_returns_optional_dict(self):
        """Returns Optional[Dict] — None when no samples, dict otherwise."""
        deps = _make_deps(sample_results=[None, None])
        out = multi_sample_summarize(
            "Ch", "text", n_samples=2, **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out is None
        s = _sample("E.", ["B."], "T.")
        deps2 = _make_deps(sample_results=[s, s])
        out2 = multi_sample_summarize(
            "Ch", "text", n_samples=2, **{k: v for k, v in _common_kwargs(deps2).items()}
        )
        assert isinstance(out2, dict)
