"""V18.11 (Phase 5 Stage 3, Batch 2.4) — self_review characterization tests.

Byte-for-byte stability gate for ``self_review_batched`` extracted from
``Summarizer._self_review_batched``. Uses mocked ``call_llm`` /
``prompt_manager`` / ``recover_vram`` to capture the batched review flow.

Run: pytest tests/test_self_review.py -v
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.self_review import self_review_batched


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


class _FakePromptManager:
    def render_template(self, name, **kw):
        # Return a deterministic prompt string capturing the kwargs
        return f"REVIEW name={name} heading={kw.get('heading')} batch={kw.get('batch_index')}/{kw.get('batch_count')} bullets={kw.get('numbered_bullets', '')[:40]}..."


def _make_deps(
    *,
    llm_responses=None,
    llm_raises=None,
    strip_result=None,
):
    if llm_responses is None:
        llm_responses = []
    responses = list(llm_responses)
    idx = {"i": 0}
    llm_calls = []
    rvram_calls = []

    def call_llm(prompt, model=None, temperature=None, **kw):
        i = idx["i"]
        idx["i"] += 1
        llm_calls.append({"prompt": prompt, "model": model, "temperature": temperature})
        if llm_raises is not None and i < len(llm_raises) and llm_raises[i]:
            raise llm_raises[i]
        if i < len(responses):
            return responses[i]
        return None

    def recover_vram(context="", delay_sec=0.0, **kw):
        rvram_calls.append({"context": context, "delay_sec": delay_sec})

    def strip_thinking(text):
        return strip_result if strip_result is not None else text

    return {
        "prompt_manager": _FakePromptManager(),
        "recover_vram": recover_vram,
        "call_llm": call_llm,
        "strip_thinking": strip_thinking,
        "_llm_calls": llm_calls,
        "_rvram_calls": rvram_calls,
    }


def _common_kwargs(deps):
    return dict(
        heavy_model="heavy-model",
        primary_model="primary-model",
        max_context_tokens=32768,
        temperature=0.7,
        prompt_manager=deps["prompt_manager"],
        recover_vram=deps["recover_vram"],
        call_llm=deps["call_llm"],
        strip_thinking=deps["strip_thinking"],
        log=_CapturingLog(),
    )


# ── 1. no model ────────────────────────────────────────────────────────────


class TestNoModel:
    def test_no_model_returns_none(self):
        """When both heavy_model and primary_model are None/empty, returns
        None immediately and logs 'skipped'."""
        deps = _make_deps(llm_responses=["SHOULD_NOT_BE_CALLED"])
        kw = _common_kwargs(deps)
        kw["heavy_model"] = None
        kw["primary_model"] = ""
        cap = kw["log"]
        out = self_review_batched(
            "Ch", "text", ["b1", "b2"], "thorough", **{k: v for k, v in kw.items()}
        )
        assert out is None
        # No LLM call
        assert len(deps["_llm_calls"]) == 0
        # An INFO log about skipping
        infos = [m for m, l in cap.calls if l == "INFO"]
        assert any("skipped" in i.lower() for i in infos)

    def test_uses_heavy_model_when_available(self):
        """When heavy_model is set, it's used as the review model (preferred
        over primary)."""
        deps = _make_deps(llm_responses=['[{"verdict": "supported"}]'])
        kw = _common_kwargs(deps)
        kw["heavy_model"] = "heavy-27b"
        kw["primary_model"] = "primary-12b"
        self_review_batched("Ch", "text", ["b1"], "t", **{k: v for k, v in kw.items()})
        assert deps["_llm_calls"][0]["model"] == "heavy-27b"

    def test_falls_back_to_primary_model(self):
        """When heavy_model is None, primary_model is used."""
        deps = _make_deps(llm_responses=['[{"verdict": "supported"}]'])
        kw = _common_kwargs(deps)
        kw["heavy_model"] = None
        kw["primary_model"] = "primary-12b"
        self_review_batched("Ch", "text", ["b1"], "t", **{k: v for k, v in kw.items()})
        assert deps["_llm_calls"][0]["model"] == "primary-12b"


# ── 2. batching ────────────────────────────────────────────────────────────


class TestBatching:
    def test_single_batch_under_10_bullets(self):
        """≤10 bullets → 1 batch → 1 LLM call → returns the verdicts as JSON."""
        verdicts = (
            '[{"claim": "one", "verdict": "supported"}, {"claim": "two", "verdict": "unsupported"}]'
        )
        deps = _make_deps(llm_responses=[verdicts])
        out = self_review_batched(
            "Ch", "src text", ["b1", "b2"], "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert out is not None
        parsed = _json.loads(out)
        assert len(parsed) == 2
        assert len(deps["_llm_calls"]) == 1

    def test_multiple_batches_over_10_bullets(self):
        """25 bullets → 3 batches (10, 10, 5) → 3 LLM calls → merged verdicts."""
        bullets = [f"bullet {i} claim here." for i in range(25)]
        verdicts_per_batch = [
            _json.dumps([{"claim": f"b{i}", "verdict": "supported"} for i in range(10)]),
            _json.dumps([{"claim": f"b{i}", "verdict": "unsupported"} for i in range(10, 20)]),
            _json.dumps(
                [{"claim": f"b{i}", "verdict": "partially_supported"} for i in range(20, 25)]
            ),
        ]
        deps = _make_deps(llm_responses=verdicts_per_batch)
        out = self_review_batched(
            "Ch", "src", bullets, "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        parsed = _json.loads(out)
        assert len(parsed) == 25
        assert len(deps["_llm_calls"]) == 3

    def test_vram_recovery_between_batches(self):
        """recover_vram is called before each batch EXCEPT the first.
        3 batches → 2 recover_vram calls (before batch 2 and 3)."""
        bullets = [f"b{i}" for i in range(25)]
        deps = _make_deps(llm_responses=['[{"verdict":"supported"}]'] * 3)
        self_review_batched(
            "Ch", "src", bullets, "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert len(deps["_rvram_calls"]) == 2
        assert [c["context"] for c in deps["_rvram_calls"]] == [
            "self-review-batch-2",
            "self-review-batch-3",
        ]
        assert all(c["delay_sec"] == 30.0 for c in deps["_rvram_calls"])  # V15.1.0: 30s


# ── 3. per-batch failure handling ─────────────────────────────────────────


class TestBatchFailures:
    def test_empty_batch_response_skipped(self):
        """If a batch returns empty (None), it's skipped (WARNING) but other
        batches still run."""
        bullets = [f"b{i}" for i in range(15)]  # 2 batches
        deps = _make_deps(llm_responses=[None, '[{"verdict":"supported"}]'])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out = self_review_batched("Ch", "src", bullets, "t", **{k: v for k, v in kw.items()})
        # 1 verdict from the surviving batch
        assert out is not None
        assert len(_json.loads(out)) == 1
        # A WARNING about batch 1 empty
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("Batch 1 returned empty" in w for w in warnings)

    def test_no_json_in_response_skipped(self):
        """If a batch response has no JSON array, it's skipped (WARNING)."""
        bullets = [f"b{i}" for i in range(5)]  # 1 batch
        deps = _make_deps(llm_responses=["This is plain text with no JSON array."])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out = self_review_batched("Ch", "src", bullets, "t", **{k: v for k, v in kw.items()})
        assert out is None  # no verdicts collected
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("no JSON found" in w for w in warnings)

    def test_batch_exception_skipped(self):
        """If a batch's LLM call raises, it's caught and skipped (WARNING)."""
        bullets = [f"b{i}" for i in range(15)]  # 2 batches
        deps = _make_deps(
            llm_responses=[None, '[{"verdict":"supported"}]'],
            llm_raises=[RuntimeError("ollama crashed"), None],
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out = self_review_batched("Ch", "src", bullets, "t", **{k: v for k, v in kw.items()})
        # batch 1 crashed, batch 2 returned 1 verdict
        assert out is not None
        assert len(_json.loads(out)) == 1
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("Batch 1 failed" in w for w in warnings)

    def test_all_batches_fail_returns_none(self):
        """If every batch fails, returns None (no verdicts)."""
        bullets = [f"b{i}" for i in range(25)]  # 3 batches
        deps = _make_deps(llm_responses=[None, None, None])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out = self_review_batched("Ch", "src", bullets, "t", **{k: v for k, v in kw.items()})
        assert out is None
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("produced no verdicts" in w for w in warnings)


# ── 4. byte-for-byte stability ────────────────────────────────────────────


class TestByteForByte:
    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same JSON output across calls."""
        bullets = [f"b{i}" for i in range(5)]
        verdicts = '[{"verdict":"supported"}]'

        def _run():
            deps = _make_deps(llm_responses=[verdicts])
            return self_review_batched(
                "Ch", "src", bullets, "t", **{k: v for k, v in _common_kwargs(deps).items()}
            )

        assert _run() == _run()

    def test_returns_optional_str(self):
        """Returns Optional[str] — None or a JSON array string."""
        deps = _make_deps(llm_responses=['[{"verdict":"supported"}]'])
        out = self_review_batched(
            "Ch", "src", ["b1"], "t", **{k: v for k, v in _common_kwargs(deps).items()}
        )
        assert isinstance(out, str)
        _json.loads(out)  # valid JSON
        deps2 = _make_deps(llm_responses=[None])
        out2 = self_review_batched(
            "Ch", "src", ["b1"], "t", **{k: v for k, v in _common_kwargs(deps2).items()}
        )
        assert out2 is None

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        deps = _make_deps(llm_responses=['[{"verdict":"supported"}]'])
        kw = _common_kwargs(deps)
        kw.pop("log")
        out = self_review_batched("Ch", "src", ["b1"], "t", **{k: v for k, v in kw.items()})
        assert out is not None
