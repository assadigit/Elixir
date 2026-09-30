"""V18.15.3 (Phase 5 Stage 3, Batch 4.4) — fast_llm characterization tests.

Byte-for-byte stability gate for ``call_fast_llm`` extracted from
``Summarizer._call_fast_llm``. Mocked callbacks so no real LLM is invoked.

Branches covered (all 4 architecture modes + fallbacks):
1. single_local → call_llm_with_empty_retry
2. single_api   → call_llm_with_empty_retry
3. legacy "single" alias → treated as single_local
4. dual_local, no fast_model → heavy fallback
5. dual_local, fast_model == "gemma3:12b" → heavy fallback (short-circuit)
6. dual_local, valid fast_model → switch_to_fast_model + call_fast_ollama
7. dual_local, call_fast_ollama raises → WARNING + switch_to_heavy + heavy fallback
8. dual_api, missing api_url/model → heavy fallback
9. dual_api, valid config → call_openai_compat
10. dual_api, call_openai_compat raises → heavy fallback
11. unknown arch → None
12. fast_model_temperature pulled from request

Run: pytest tests/test_fast_llm.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.fast_llm import call_fast_llm


class _FakeRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _callbacks():
    """Build a tracking callback bundle."""
    state = {
        "heavy_calls": 0,
        "fast_calls": 0,
        "switch_fast": 0,
        "switch_heavy": 0,
        "openai_calls": 0,
        "logs": [],
    }

    def heavy(prompt, **kw):
        state["heavy_calls"] += 1
        return "HEAVY"

    def fast_ollama(prompt, **kw):
        state["fast_calls"] += 1
        return "FAST"

    def openai_compat(prompt, **kw):
        state["openai_calls"] += 1
        return "OPENAI"

    def switch_fast():
        state["switch_fast"] += 1

    def switch_heavy():
        state["switch_heavy"] += 1

    def log(msg, level="INFO"):
        state["logs"].append((msg, level))

    return state, heavy, fast_ollama, openai_compat, switch_fast, switch_heavy, log


class TestCallFastLlm:
    def test_single_local_uses_heavy(self):
        req = _FakeRequest(model_architecture="single_local")
        st, heavy, *_ = _callbacks()
        result = call_fast_llm(
            "p", request=req, call_llm_with_empty_retry=heavy, log=lambda m, l="INFO": None
        )
        assert result == "HEAVY"
        assert st["heavy_calls"] == 1

    def test_single_api_uses_heavy(self):
        req = _FakeRequest(model_architecture="single_api")
        st, heavy, *_ = _callbacks()
        result = call_fast_llm(
            "p", request=req, call_llm_with_empty_retry=heavy, log=lambda m, l="INFO": None
        )
        assert result == "HEAVY"
        assert st["heavy_calls"] == 1

    def test_legacy_single_alias_treated_as_single_local(self):
        """Legacy 'single' → normalized to 'single_local' → heavy path."""
        req = _FakeRequest(model_architecture="single")
        st, heavy, *_ = _callbacks()
        result = call_fast_llm(
            "p", request=req, call_llm_with_empty_retry=heavy, log=lambda m, l="INFO": None
        )
        assert result == "HEAVY"
        assert st["heavy_calls"] == 1

    def test_dual_local_no_fast_model_falls_back(self):
        req = _FakeRequest(model_architecture="dual_local", fast_model="")
        st, heavy, fast_oll, _, switch_f, _, _ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            switch_to_fast_model=switch_f,
            call_fast_ollama=fast_oll,
            log=lambda m, l="INFO": None,
        )
        assert result == "HEAVY"
        assert st["fast_calls"] == 0
        assert st["switch_fast"] == 0  # never switched

    def test_dual_local_gemma3_short_circuit(self):
        """fast_model == 'gemma3:12b' → heavy fallback (short-circuit)."""
        req = _FakeRequest(model_architecture="dual_local", fast_model="gemma3:12b")
        st, heavy, fast_oll, _, switch_f, _, _ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            switch_to_fast_model=switch_f,
            call_fast_ollama=fast_oll,
            log=lambda m, l="INFO": None,
        )
        assert result == "HEAVY"
        assert st["fast_calls"] == 0
        assert st["switch_fast"] == 0

    def test_dual_local_valid_fast_model(self):
        req = _FakeRequest(
            model_architecture="dual_local", fast_model="lfm2:2.6b", fast_model_temperature=0.3
        )
        st, heavy, fast_oll, _, switch_f, _, _ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            switch_to_fast_model=switch_f,
            call_fast_ollama=fast_oll,
            log=lambda m, l="INFO": None,
        )
        assert result == "FAST"
        assert st["fast_calls"] == 1
        assert st["switch_fast"] == 1
        assert st["heavy_calls"] == 0

    def test_dual_local_fast_ollama_raises_fallback_with_warning(self):
        def fast_oll_raise(prompt, **kw):
            raise RuntimeError("ollama down")

        req = _FakeRequest(model_architecture="dual_local", fast_model="lfm2:2.6b")
        st, heavy, _, _, switch_f, switch_h, log = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            switch_to_fast_model=switch_f,
            call_fast_ollama=fast_oll_raise,
            switch_to_heavy_model=switch_h,
            log=log,
        )
        assert result == "HEAVY"  # fell back to heavy
        assert st["switch_heavy"] == 1
        warnings = [m for m, l in st["logs"] if l == "WARNING"]
        assert len(warnings) == 1
        assert "falling back to heavy" in warnings[0]

    def test_dual_api_missing_config_falls_back(self):
        req = _FakeRequest(model_architecture="dual_api", fast_api_url="", fast_api_model="")
        st, heavy, _, openai, *_ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            call_openai_compat=openai,
            log=lambda m, l="INFO": None,
        )
        assert result == "HEAVY"
        assert st["openai_calls"] == 0

    def test_dual_api_valid_config_uses_openai_compat(self):
        req = _FakeRequest(
            model_architecture="dual_api",
            fast_api_url="http://x",
            fast_api_key="k",
            fast_api_model="gpt-4o-mini",
            fast_model_temperature=0.3,
        )
        st, heavy, _, openai, *_ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            call_openai_compat=openai,
            log=lambda m, l="INFO": None,
        )
        assert result == "OPENAI"
        assert st["openai_calls"] == 1
        assert st["heavy_calls"] == 0

    def test_dual_api_openai_raises_falls_back(self):
        def openai_raise(prompt, **kw):
            raise RuntimeError("api 500")

        req = _FakeRequest(
            model_architecture="dual_api", fast_api_url="http://x", fast_api_model="m"
        )
        st, heavy, _, _, *_ = _callbacks()
        result = call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            call_openai_compat=openai_raise,
            log=lambda m, l="INFO": None,
        )
        assert result == "HEAVY"
        assert st["heavy_calls"] == 1

    def test_unknown_arch_returns_none(self):
        req = _FakeRequest(model_architecture="bogus")
        st, heavy, *_ = _callbacks()
        result = call_fast_llm(
            "p", request=req, call_llm_with_empty_retry=heavy, log=lambda m, l="INFO": None
        )
        assert result is None
        assert st["heavy_calls"] == 0

    def test_fast_model_temperature_default_when_missing(self):
        """request without fast_model_temperature → default 0.1 (no crash)."""
        req = _FakeRequest(model_architecture="dual_local", fast_model="lfm2:2.6b")
        # no fast_model_temperature attr → getattr default 0.1
        st, heavy, fast_oll, _, switch_f, _, _ = _callbacks()
        captured = {}

        def fast_ollama_capture(prompt, **kw):
            captured.update(kw)
            return "FAST"

        call_fast_llm(
            "p",
            request=req,
            call_llm_with_empty_retry=heavy,
            switch_to_fast_model=switch_f,
            call_fast_ollama=fast_ollama_capture,
            log=lambda m, l="INFO": None,
        )
        assert captured.get("temp") == 0.1
