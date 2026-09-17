"""V18.2.26 (A1 wiring) — Tests for parallel stage runner."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.obs.parallel_stages import (
    _safe_get,
    parallel_judge_and_grounding,
    parallel_stages,
)


class TestParallelJudgeAndGrounding:
    def test_both_succeed(self):
        judge_result = parallel_judge_and_grounding(
            judge_fn=lambda: "judge_ok",
            grounding_fn=lambda: ["ungrounded_bullet"],
        )
        assert judge_result[0] == "judge_ok"
        assert judge_result[1] == ["ungrounded_bullet"]

    def test_runs_concurrently(self):
        """Wall-clock should be ~max(t1, t2), not t1 + t2."""
        def slow_judge():
            time.sleep(0.1)
            return "judge"

        def slow_grounding():
            time.sleep(0.1)
            return "grounding"

        start = time.time()
        result = parallel_judge_and_grounding(slow_judge, slow_grounding)
        elapsed = time.time() - start
        assert result == ("judge", "grounding")
        # If sequential: 0.2s. Parallel should be ~0.1s.
        assert elapsed < 0.18, f"took {elapsed:.3f}s — not parallel"

    def test_judge_raises_propagates(self):
        def bad_judge():
            raise RuntimeError("judge failed")
        def good_grounding():
            return "grounding"

        with pytest.raises(RuntimeError, match="judge failed"):
            parallel_judge_and_grounding(bad_judge, good_grounding)

    def test_grounding_fails_graceful(self):
        """Grounding failure → None, judge result still returned."""
        result = parallel_judge_and_grounding(
            judge_fn=lambda: "judge_ok",
            grounding_fn=lambda: (_ for _ in ()).throw(RuntimeError("grounding failed")),
        )
        assert result[0] == "judge_ok"
        assert result[1] is None  # graceful degradation

    def test_log_callback_invoked(self):
        logs = []
        parallel_judge_and_grounding(
            judge_fn=lambda: "j",
            grounding_fn=lambda: "g",
            log_callback=lambda msg, level="INFO": logs.append((msg, level)),
        )
        assert len(logs) >= 2  # start + complete
        assert any("parallel" in m.lower() for m, _ in logs)


class TestParallelStages:
    def test_all_succeed(self):
        results = parallel_stages(
            lambda: "a",
            lambda: "b",
            lambda: "c",
        )
        assert results == ["a", "b", "c"]

    def test_preserves_order(self):
        results = parallel_stages(
            lambda: 3,
            lambda: 1,
            lambda: 2,
        )
        assert results == [3, 1, 2]

    def test_runs_concurrently(self):
        start = time.time()
        results = parallel_stages(
            lambda: time.sleep(0.05) or "a",
            lambda: time.sleep(0.05) or "b",
            lambda: time.sleep(0.05) or "c",
        )
        elapsed = time.time() - start
        assert results == ["a", "b", "c"]
        # Sequential: 0.15s. Parallel: ~0.05s.
        assert elapsed < 0.12

    def test_one_fails_returns_none(self):
        results = parallel_stages(
            lambda: "a",
            lambda: (_ for _ in ()).throw(ValueError("b failed")),
            lambda: "c",
        )
        assert results == ["a", None, "c"]

    def test_empty_input(self):
        assert parallel_stages() == []

    def test_single_function(self):
        assert parallel_stages(lambda: "only") == ["only"]

    def test_max_workers_caps_concurrency(self):
        in_flight = {"max": 0, "current": 0}
        def track():
            in_flight["current"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["current"])
            time.sleep(0.02)
            in_flight["current"] -= 1
            return "ok"

        parallel_stages(track, track, track, track, track, max_workers=2)
        assert in_flight["max"] <= 2

    def test_log_callback(self):
        logs = []
        parallel_stages(
            lambda: "a",
            lambda: "b",
            log_callback=lambda msg, level="INFO": logs.append(msg),
        )
        assert any("parallel" in m.lower() for m in logs)


class TestSafeGet:
    def test_returns_result(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(lambda: 42)
            assert _safe_get(fut) == 42

    def test_returns_none_on_failure(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(lambda: (_ for _ in ()).throw(ValueError("fail")))
            assert _safe_get(fut) is None

    def test_returns_none_on_timeout(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(lambda: time.sleep(1) or "late")
            assert _safe_get(fut, timeout=0.01) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
