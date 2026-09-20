"""V18.15.3 (Phase 5 Stage 3, Batch 4.7) — primary_call characterization tests.

Byte-for-byte stability gate for ``summarize_with_model`` extracted from
``Summarizer._summarize_with_model``. Mocks ``count_tokens``,
``subprocess.run`` (nvidia-smi), and all the LLM callbacks so no real model
is invoked.

Branches covered:
1. small text (< 12000 tok) → no chunking → structured-JSON success path
2. structured returns dict → annotated with raw="", model, temperature
3. structured None + retry empty → returns None
4. structured None + retry returns raw → strip + parse + annotate
5. large text (> 12000) + thermal ok → chunked path success (returns chunked result)
6. large text + chunked returns None → WARNING + fallback to single-pass
7. large text + GPU hot (≥78°C) → _should_chunk False → single-pass
8. max_tokens from request.summarisation_max_output_tokens when max_tokens=None

Run: pytest tests/test_primary_call.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk

from core.summarisation import primary_call as pc_mod


# V18.20.2.0 (SWOT A26): summarize_with_model now routes the nvidia-smi probe
# through a ~30s module-level cache (pc_mod._gpu_temp_cache). Without this
# autouse reset, test_hot_gpu_skips_chunking's cached 80°C reading would leak
# into later tests (e.g. test_max_tokens_from_request_when_none's _no_gpu
# probe never fires — a cache HIT returns the stale 80°C → chunking disabled
# → the max_out capture never happens). Each test starts with a cold cache.
@pytest.fixture(autouse=True)
def _reset_gpu_temp_cache():
    pc_mod._gpu_temp_cache["valid"] = 0.0
    pc_mod._gpu_temp_cache["temp"] = 0.0
    pc_mod._gpu_temp_cache["ts"] = 0.0
    yield
    pc_mod._gpu_temp_cache["valid"] = 0.0


class _FakeRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _no_gpu(monkeypatch):
    """Make nvidia-smi 'fail' so _gpu_temp_c stays 0 → thermal_ok True."""
    import subprocess

    def _fake_run(*a, **kw):
        raise FileNotFoundError("no nvidia-smi in test env")

    monkeypatch.setattr(subprocess, "run", _fake_run)


def _hot_gpu(monkeypatch, temp=80):
    """Simulate a hot GPU (≥78°C)."""
    import subprocess

    class _R:
        returncode = 0
        stdout = f"{temp}\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _R())


def _set_tokens(monkeypatch, n):
    """Patch count_tokens to return a fixed token count."""
    import utils.token_counter as tc

    monkeypatch.setattr(tc, "count_tokens", lambda text: n)


class TestSummarizeWithModel:
    def test_small_text_structured_success(self, monkeypatch):
        """< 12000 tokens → no chunking → structured returns dict → annotated."""
        _set_tokens(monkeypatch, 5000)
        _no_gpu(monkeypatch)
        logs = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "model-x",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": logs.append((m, l)),
            chunked_summarize=lambda *a, **k: None,
            build_prompt=lambda *a, **k: "PROMPT",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["b1"]},
            call_llm_with_empty_retry=lambda *a, **k: None,
            strip_thinking=lambda x: x,
            parse_response=lambda x: {"bullet_points": []},
        )
        assert result == {
            "bullet_points": ["b1"],
            "raw": "",
            "model": "model-x",
            "temperature": 0.7,
        }

    def test_structured_none_retry_empty_returns_none(self, monkeypatch):
        """structured None + retry empty → returns None."""
        _set_tokens(monkeypatch, 5000)
        _no_gpu(monkeypatch)
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": None,
            chunked_summarize=lambda *a, **k: None,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert result is None

    def test_structured_none_retry_returns_raw_parses(self, monkeypatch):
        """structured None + retry returns raw → strip + parse + annotate."""
        _set_tokens(monkeypatch, 5000)
        _no_gpu(monkeypatch)
        logs = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": logs.append((m, l)),
            chunked_summarize=lambda *a, **k: None,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=lambda *a, **k: "<xml>raw</xml>",
            strip_thinking=lambda x: x.upper(),  # transforms the raw
            parse_response=lambda x: {"bullet_points": ["parsed"]},
        )
        assert result["bullet_points"] == ["parsed"]
        assert result["raw"] == "<XML>RAW</XML>"  # strip_thinking applied
        assert result["model"] == "m"
        assert result["temperature"] == 0.7
        # DEBUG log of first 500 chars
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert any("Raw response" in m for m in debugs)

    def test_large_text_chunked_success(self, monkeypatch):
        """> 12000 tokens + thermal ok → chunked path returns its result."""
        _set_tokens(monkeypatch, 15000)
        _no_gpu(monkeypatch)
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return {"bullet_points": ["chunked-bullet"], "from_chunked": True}

        logs = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": logs.append((m, l)),
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert result == {"bullet_points": ["chunked-bullet"], "from_chunked": True}
        assert chunked_calls["n"] == 1
        infos = [m for m, l in logs if l == "INFO"]
        assert any("chunked output" in m for m in infos)

    def test_large_text_chunked_none_falls_back(self, monkeypatch):
        """chunked returns None → WARNING log + fallback to single-pass."""
        _set_tokens(monkeypatch, 15000)
        _no_gpu(monkeypatch)
        logs = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": logs.append((m, l)),
            chunked_summarize=lambda *a, **k: None,  # chunked fails
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["fb"]},
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        # fell back to single-pass → structured path succeeded
        assert result["bullet_points"] == ["fb"]
        warnings = [m for m, l in logs if l == "WARNING"]
        assert len(warnings) == 1
        assert "falling back to single-pass" in warnings[0]

    def test_large_text_hot_gpu_skips_chunking(self, monkeypatch):
        """> 12000 tokens BUT GPU ≥78°C → _should_chunk False → single-pass."""
        _set_tokens(monkeypatch, 15000)
        _hot_gpu(monkeypatch, temp=80)  # ≥78
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return None

        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["single"]},
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        # chunking skipped (hot GPU) → single-pass structured path
        assert result["bullet_points"] == ["single"]
        assert chunked_calls["n"] == 0  # chunked never called

    def test_max_tokens_from_request_when_none(self, monkeypatch):
        """max_tokens=None → uses request.summarisation_max_output_tokens.

        With a low output cap (< 14000) AND large input, chunking triggers.
        We verify the chunked path gets the _max_out from the request.
        """
        _set_tokens(monkeypatch, 15000)
        _no_gpu(monkeypatch)
        captured = {}

        def chunked(heading, text, model, temp, with_cot, concepts, callouts, max_out):
            captured["max_out"] = max_out
            return {"bullet_points": []}

        pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            max_tokens=None,
            request=_FakeRequest(summarisation_max_output_tokens=8192),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert captured["max_out"] == 8192

    def test_high_output_cap_prevents_chunking(self, monkeypatch):
        """_max_out >= 14000 → chunking NOT triggered even for large input."""
        _set_tokens(monkeypatch, 15000)
        _no_gpu(monkeypatch)
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return None

        pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            max_tokens=16000,  # >= 14000 → no chunk
            request=_FakeRequest(),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["x"]},
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert chunked_calls["n"] == 0

    # ── V0.20.2 (Quality Campaign, conversion-log audit Defect L4, §7b) ──

    def test_low_bit_quant_moderate_input_chunks_v0202(self, monkeypatch):
        """V0.20.2: a LOW-BIT QUANT model with MODERATE input (>6000 tok,
        under the 12000 gate) triggers chunking. The V0.18 rig run had
        input 8566 tok (under 12000) and STILL truncated on output (CoT
        inundation + 8192 output cap). The existing 12000-tok gate missed
        this because it gates on INPUT size; the V0.20.2 condition gates
        on a MODEL property (is_low_bit_quant) + a moderate-input
        threshold. Content-agnostic — no chapter-specific branches."""
        _set_tokens(monkeypatch, 8566)  # the V0.18 rig input size
        _no_gpu(monkeypatch)
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return {"bullet_points": ["chunked-bullet"], "from_chunked": True}

        logs = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "Qwen3.8-27B-Q2_K_XL",  # a low-bit quant model (the V0.18 rig model)
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": logs.append((m, l)),
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert result == {"bullet_points": ["chunked-bullet"], "from_chunked": True}
        assert chunked_calls["n"] == 1
        infos = [m for m, l in logs if l == "INFO"]
        # The V0.20.2 message fired (not the V18.3.5 message — no double-log).
        assert any("V0.20.2: chunked output (low-bit quant" in m for m in infos), infos
        assert not any("V18.3.5: chunked output" in m for m in infos), (
            "the V18.3.5 log must NOT fire when the V0.20.2 log already fired (no double-log)"
        )

    def test_low_bit_quant_small_input_does_not_chunk_v0202(self, monkeypatch):
        """V0.20.2: a low-bit quant model with SMALL input (<=6000 tok) does
        NOT trigger the V0.20.2 chunking path — the 6000-tok threshold
        leaves a 4.6× margin below the smallest golden chapter (1262 tok).
        The golden corpus never triggers this path (byte-identical outputs
        preserved)."""
        _set_tokens(monkeypatch, 5000)  # under the 6000 V0.20.2 threshold
        _no_gpu(monkeypatch)
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return None

        pc_mod.summarize_with_model(
            "h",
            "text",
            "Qwen3.8-27B-Q2_K_XL",  # low-bit, but input too small
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["structured"]},
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert chunked_calls["n"] == 0, (
            "the V0.20.2 low-bit path must NOT fire for small input (<=6000 tok) — "
            "the golden corpus (max 1262 tok) never triggers this path"
        )

    def test_non_low_bit_model_moderate_input_does_not_chunk_v0202(self, monkeypatch):
        """V0.20.2: a NON-low-bit model with moderate input does NOT trigger
        the V0.20.2 chunking path — the condition requires BOTH low-bit
        quant AND moderate input. A full-precision model with 8566 tok
        input uses the single-pass path (it has a higher output cap and
        isn't prone to CoT inundation)."""
        _set_tokens(monkeypatch, 8566)  # moderate, but not low-bit
        _no_gpu(monkeypatch)
        chunked_calls = {"n": 0}

        def chunked(*a, **k):
            chunked_calls["n"] += 1
            return None

        pc_mod.summarize_with_model(
            "h",
            "text",
            "gemma-12b-q8",  # NOT a low-bit quant
            0.7,
            request=_FakeRequest(),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["structured"]},
            call_llm_with_empty_retry=lambda *a, **k: "",
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        assert chunked_calls["n"] == 0, (
            "the V0.20.2 low-bit path must NOT fire for a non-low-bit model "
            "(the condition requires BOTH low-bit quant AND moderate input)"
        )
