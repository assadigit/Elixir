"""V18.15.3 (Phase 5 Stage 3, Batch 4.2) — b3_judge characterization tests.

Byte-for-byte stability gate for ``b3_cloud_judge`` extracted from
``Summarizer._b3_cloud_judge``. Mocked ``prompt_manager`` / ``call_cloud`` /
``compute_coverage`` so no real LLM is invoked.

Branches covered:
1. success — cloud picks exec#2 + thorough#3 from digit responses
2. empty cloud response — defaults to index 0 for both
3. out-of-range index in response — defaults to index 0
4. exception path — falls back to coverage-based picking + WARNING log
5. prompt_manager.render_template called with correct args (heading, n, block)

Run: pytest tests/test_b3_judge.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.b3_judge import b3_cloud_judge


class _FakePromptManager:
    def __init__(self):
        self.calls = []

    def render_template(self, name, **kw):
        self.calls.append((name, kw))
        return f"PROMPT[{name}]"


def _make_samples(n=3):
    return [
        {"executive_summary": f"exec {i}", "thorough_summary": f"thorough {i}"} for i in range(n)
    ]


class TestB3CloudJudge:
    def test_success_picks_chosen_indices(self):
        """Cloud returns '2' for exec and '3' for thorough → picks #2 and #3."""
        pm = _FakePromptManager()
        responses = iter(["2", "3"])  # exec then thorough

        def call_cloud(prompt, **kw):
            return next(responses)

        logs = []
        samples = _make_samples(3)
        best_exec, best_thorough = b3_cloud_judge(
            samples,
            "source text",
            "Heading",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.3,
            log=lambda m, l="INFO": logs.append((m, l)),
            compute_coverage=lambda s, c: 0.5,
        )
        assert best_exec is samples[1]  # index 2-1 = 1
        assert best_thorough is samples[2]  # index 3-1 = 2
        # one DEBUG log naming both picks
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert len(debugs) == 1
        assert "exec#2" in debugs[0] and "thorough#3" in debugs[0]

    def test_empty_response_defaults_to_index_zero(self):
        """Empty cloud response → best index stays 0 for both."""
        pm = _FakePromptManager()

        def call_cloud(prompt, **kw):
            return ""

        samples = _make_samples(3)
        best_exec, best_thorough = b3_cloud_judge(
            samples,
            "src",
            "H",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.3,
            log=lambda m, l="INFO": None,
        )
        assert best_exec is samples[0]
        assert best_thorough is samples[0]

    def test_out_of_range_index_defaults_to_zero(self):
        """Cloud returns '9' (> len(samples)) → index stays 0."""
        pm = _FakePromptManager()

        def call_cloud(prompt, **kw):
            return "9"

        samples = _make_samples(3)
        best_exec, best_thorough = b3_cloud_judge(
            samples,
            "src",
            "H",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.3,
            log=lambda m, l="INFO": None,
        )
        assert best_exec is samples[0]
        assert best_thorough is samples[0]

    def test_exception_falls_back_to_coverage(self):
        """call_cloud raises → exception path picks max-coverage sample."""
        pm = _FakePromptManager()

        def call_cloud(prompt, **kw):
            raise RuntimeError("cloud down")

        # coverage returns higher for sample index 2 (exec) and 0 (thorough)
        cov_map = {
            "exec 0": 0.1,
            "exec 1": 0.2,
            "exec 2": 0.9,
            "thorough 0": 0.8,
            "thorough 1": 0.2,
            "thorough 2": 0.1,
        }

        def compute_coverage(src, cand):
            return cov_map.get(cand, 0.0)

        logs = []
        samples = _make_samples(3)
        best_exec, best_thorough = b3_cloud_judge(
            samples,
            "src",
            "H",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.3,
            log=lambda m, l="INFO": logs.append((m, l)),
            compute_coverage=compute_coverage,
        )
        assert best_exec is samples[2]  # exec 2 has 0.9
        assert best_thorough is samples[0]  # thorough 0 has 0.8
        warnings = [m for m, l in logs if l == "WARNING"]
        assert len(warnings) == 1
        assert "falling back to coverage" in warnings[0]

    def test_render_template_called_with_correct_args(self):
        """prompt_manager.render_template receives heading, n_candidates, candidates_block."""
        pm = _FakePromptManager()

        def call_cloud(prompt, **kw):
            return "1"

        samples = _make_samples(3)
        b3_cloud_judge(
            samples,
            "src",
            "MyHeading",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.5,
            log=lambda m, l="INFO": None,
        )
        assert len(pm.calls) == 2
        exec_name, exec_kw = pm.calls[0]
        thorough_name, thorough_kw = pm.calls[1]
        assert exec_name == "summarisation/b3_judge_exec"
        assert thorough_name == "summarisation/b3_judge_thorough"
        assert exec_kw["heading"] == "MyHeading"
        assert exec_kw["n_candidates"] == 3
        assert "--- Summary 1 ---" in exec_kw["candidates_block"]
        assert "exec 0" in exec_kw["candidates_block"]
        # thorough block truncates at 1500 chars
        assert thorough_kw["n_candidates"] == 3

    def test_candidate_truncation_exec_1000_thorough_1500(self):
        """exec candidates truncated to 1000 chars, thorough to 1500."""
        pm = _FakePromptManager()

        def call_cloud(prompt, **kw):
            return "1"

        long_exec = "E" * 2000
        long_thorough = "T" * 3000
        samples = [{"executive_summary": long_exec, "thorough_summary": long_thorough}]
        b3_cloud_judge(
            samples,
            "src",
            "H",
            prompt_manager=pm,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.3,
            log=lambda m, l="INFO": None,
        )
        exec_block = pm.calls[0][1]["candidates_block"]
        thorough_block = pm.calls[1][1]["candidates_block"]
        # exec body capped at 1000 chars (+ the "--- Summary 1 ---\n" prefix + "\n\n")
        assert "E" * 1000 in exec_block
        assert "E" * 1001 not in exec_block
        # thorough body capped at 1500 chars
        assert "T" * 1500 in thorough_block
        assert "T" * 1501 not in thorough_block
