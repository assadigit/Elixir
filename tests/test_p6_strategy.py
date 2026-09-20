"""V0.10 (P6) — adaptive strategy engine tests (core/summarisation/strategy.py).

WHY THIS FILE EXISTS
────────────────────
P6 replaces the four inconsistent "does it fit?" answers (map-reduce 40000 /
B4 12000 / chunked 12000+14000 / _prepare_text ctx-out-700) with ONE pure
``decide_strategy`` function.  These tests pin the two halves of its
contract:

  1. LEGACY PARITY — at window <= 32768 the decisions are EXACTLY the
     current hardcoded thresholds, so every pre-220k model keeps
     byte-identical dispatch behavior (the hard constraint from the
     approved architecture).
  2. ADAPTIVE — above 32768 a chapter that fits the window goes
     single-pass (the 220k rig's 40k-token chapters stop being shredded
     into 4k map-reduce chunks), and only genuinely oversized sources
     map-reduce with window-scaled chunks.

Wiring pins (the 4 dispatch sites consult decide_strategy) live in
``TestWiringPins`` at the bottom; they were appended in P6-b.

Run: pytest tests/test_p6_strategy.py -v
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import tempfile
from pathlib import Path

import pytest

from core.summarisation.strategy import (
    LEGACY_B4_THRESHOLD,
    LEGACY_CHUNKED_INPUT_THRESHOLD,
    LEGACY_CHUNKED_OUTPUT_THRESHOLD,
    LEGACY_MAP_OVERLAP,
    LEGACY_MAP_REDUCE_THRESHOLD,
    StrategyDecision,
    decide_strategy,
)

_project_root = Path(__file__).resolve().parent.parent

# The default live values used across the parity table (the wizard-era
# 32k window and the user's Task-8 max-output rule — 8192 for Ollama).
_DEFAULT_WINDOW = 32768
_DEFAULT_OUTPUT = 8192


# ════════════════════════════════════════════════════════════════════════════
# 1. LEGACY PARITY — window <= 32768 reproduces the CURRENT thresholds EXACTLY
# ════════════════════════════════════════════════════════════════════════════


class TestLegacyParity:
    """At legacy windows the decision is the pre-P6 dispatch cascade:

    map_reduce iff src > 40000; b4 iff src > 12000; chunked_output iff
    src > 12000 AND output < 14000; else single_pass.
    """

    # src_tokens -> expected legacy strategy (output=8192, default thresholds).
    PARITY_TABLE = {
        1000: "single_pass",  # small chapter — plain primary call
        11999: "single_pass",  # just under the b4 threshold
        12001: "b4_sections",  # just over the b4 threshold (B4, NOT chunked)
        39999: "b4_sections",  # long chapter, still under map-reduce
        40001: "map_reduce",  # just over MAP_REDUCE_THRESHOLD
        60000: "map_reduce",  # very large chapter
    }

    @pytest.mark.parametrize("window", [16384, 32768])
    @pytest.mark.parametrize(
        ("src_tokens", "expected"),
        sorted(PARITY_TABLE.items()),
        ids=lambda v: f"src={v}",
    )
    def test_parity_table(self, window, src_tokens, expected):
        """Both legacy windows produce the SAME decision for the same src —
        the pre-P6 thresholds never looked at the window, and parity keeps
        it that way (byte-identical behavior for every <= 32k model)."""
        decision = decide_strategy(src_tokens, window, _DEFAULT_OUTPUT)
        assert decision.strategy == expected
        assert decision.map_chunk_tokens == 4000  # MAP_CHUNK_TOKENS parity
        assert decision.overlap == 0.10  # MAP_CHUNK_OVERLAP parity

    def test_parity_table_boundaries_are_strict(self):
        """The legacy comparisons are strict (>, <) — pin the exact edges."""
        # b4: > 12000 (not >=)
        assert decide_strategy(12000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT).strategy == "single_pass"
        assert decide_strategy(12001, _DEFAULT_WINDOW, _DEFAULT_OUTPUT).strategy == "b4_sections"
        # map_reduce: > 40000 (not >=)
        assert decide_strategy(40000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT).strategy == "b4_sections"
        assert decide_strategy(40001, _DEFAULT_WINDOW, _DEFAULT_OUTPUT).strategy == "map_reduce"
        # chunked output gate: input > 12000 AND output < 14000 (both strict)
        # (surfaced only when b4 is raised, else B4 wins the cascade first)
        assert (
            decide_strategy(12000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, b4_threshold=999999).strategy
            == "single_pass"
        )
        assert (
            decide_strategy(12001, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, b4_threshold=999999).strategy
            == "chunked_output"
        )
        assert (
            decide_strategy(13000, _DEFAULT_WINDOW, 14000, b4_threshold=999999).strategy
            == "single_pass"
        )

    def test_chunked_output_decision_only_below_14000_output(self):
        """The chunked gate needs output < 14000 — at/above it, single-pass."""
        for out in (14000, 16000, 32000):
            decision = decide_strategy(13000, _DEFAULT_WINDOW, out, b4_threshold=999999)
            assert decision.strategy == "single_pass", f"output {out} must not chunk"
        for out in (2048, 4096, 8192, 13999):
            decision = decide_strategy(13000, _DEFAULT_WINDOW, out, b4_threshold=999999)
            assert decision.strategy == "chunked_output", f"output {out} must chunk"

    def test_explicit_thresholds_flow_through_at_legacy_windows(self):
        """The settings-driven b4_threshold and the Summarizer's
        MAP_REDUCE_THRESHOLD keep flowing through UNCHANGED at legacy
        windows (decide_strategy never reads Settings itself)."""
        # b4 lowered to the V13.40.3 value 8000 (the documented user lever):
        assert (
            decide_strategy(11999, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, b4_threshold=8000).strategy
            == "b4_sections"
        )
        # b4 raised above map-reduce: the map-reduce threshold still wins:
        assert (
            decide_strategy(45000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, b4_threshold=50000).strategy
            == "map_reduce"
        )
        # map_reduce raised to 50000: a 45k chapter is B4, not map-reduce:
        assert (
            decide_strategy(
                45000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, map_reduce_threshold=50000
            ).strategy
            == "b4_sections"
        )
        assert (
            decide_strategy(
                60000, _DEFAULT_WINDOW, _DEFAULT_OUTPUT, map_reduce_threshold=50000
            ).strategy
            == "map_reduce"
        )

    def test_legacy_constants_match_the_live_codebase(self):
        """The local constants are the LIVE hardcoded values (drift-catch):
        the MAP_* attrs (V0.18 Phase 5.1 step 5: _init_map_reduce_and_prompts
        moved VERBATIM to summarizer_init.py) and settings.py's b4 default."""
        summarizer_src = (
            _project_root / "core" / "summarisation" / "summarizer_init.py"
        ).read_text(encoding="utf-8")
        assert f"self.MAP_CHUNK_TOKENS = {4000}" in summarizer_src
        assert f"self.MAP_CHUNK_OVERLAP = {LEGACY_MAP_OVERLAP}" in summarizer_src
        assert f"self.MAP_REDUCE_THRESHOLD = {LEGACY_MAP_REDUCE_THRESHOLD}" in summarizer_src
        settings_src = (_project_root / "utils" / "settings.py").read_text(encoding="utf-8")
        # V0.13: whitespace-flexible — ruff-format normalized the column padding
        import re as _re_b4

        assert _re_b4.search(rf'"b4_threshold_tokens":\s*{LEGACY_B4_THRESHOLD},', settings_src)
        primary_src = (_project_root / "core" / "summarisation" / "primary_call.py").read_text(
            encoding="utf-8"
        )
        assert f"> {LEGACY_CHUNKED_INPUT_THRESHOLD}" in primary_src
        assert f"< {LEGACY_CHUNKED_OUTPUT_THRESHOLD}" in primary_src


# ════════════════════════════════════════════════════════════════════════════
# 2. ADAPTIVE — window > 32768 (the 220k rig)
# ════════════════════════════════════════════════════════════════════════════


class TestAdaptive:
    """Above the legacy window the fit math is budget-driven."""

    WINDOW = 220000  # the Ternary-Bonsai-2 27B rig (P5 registry capability)
    OUTPUT = 8192
    # usable = 220000 - 8192 - 700 - 512
    USABLE = 210596

    def test_100k_chapter_goes_single_pass(self):
        """The headline 220k win: a 100k-token chapter that legacy would
        map-reduce (25+ LLM calls of 4k chunks) fits ONE call."""
        decision = decide_strategy(100000, self.WINDOW, self.OUTPUT)
        assert decision.strategy == "single_pass"
        assert "usable 210,596" in decision.reason
        assert f"window {self.WINDOW:,}" in decision.reason

    def test_oversized_chapter_map_reduces_with_scaled_chunk(self):
        """250k tokens > usable 210,596 → map_reduce with 27,500-token
        chunks (220000 // 8), NOT the legacy 4k."""
        decision = decide_strategy(250000, self.WINDOW, self.OUTPUT)
        assert decision.strategy == "map_reduce"
        assert decision.map_chunk_tokens == 27500
        assert decision.overlap == 0.10

    def test_usable_boundary_is_inclusive(self):
        """src == usable fits (<=); src == usable + 1 does not."""
        assert decide_strategy(self.USABLE, self.WINDOW, self.OUTPUT).strategy == "single_pass"
        assert decide_strategy(self.USABLE + 1, self.WINDOW, self.OUTPUT).strategy == "map_reduce"

    @pytest.mark.parametrize(
        "src_tokens",
        [1000, 12001, 13000, 39999, 40001, 60000, 100000, 210596, 210597, 250000, 1000000],
    )
    def test_b4_and_chunked_never_fire_at_large_windows(self, src_tokens):
        """b4_sections / chunked_output are DISABLED above 32768 — even for
        the src sizes that trigger them at legacy windows, and even with
        aggressive explicit thresholds."""
        decision = decide_strategy(src_tokens, self.WINDOW, self.OUTPUT)
        assert decision.strategy in ("single_pass", "map_reduce")
        aggressive = decide_strategy(
            src_tokens, self.WINDOW, self.OUTPUT, b4_threshold=1, map_reduce_threshold=1
        )
        assert aggressive.strategy == decision.strategy
        assert aggressive.strategy in ("single_pass", "map_reduce")

    def test_chunk_scaling_clamped_to_bounds(self):
        """chunk = clamp(window // 8, 4000, 32000)."""
        # 220000 // 8 = 27500 (in range)
        assert decide_strategy(250000, 220000, 8192).map_chunk_tokens == 27500
        # 1M window // 8 = 125000 → clamped to 32000
        assert decide_strategy(990000, 1000000, 8192).map_chunk_tokens == 32000
        # barely-adaptive window 32769 // 8 = 4096 (above the 4000 floor)
        assert decide_strategy(99000, 32769, 8192).map_chunk_tokens == 4096

    def test_output_reserve_scales_usable(self):
        """A bigger output target shrinks the usable budget one-for-one."""
        d1 = decide_strategy(55000, 65536, 8192)  # usable 56,132
        d2 = decide_strategy(55000, 65536, 4096)  # usable 60,228
        assert "usable 56,132" in d1.reason
        assert "usable 60,228" in d2.reason
        assert d1.strategy == "single_pass" and d2.strategy == "single_pass"
        # 60000 fits only with the smaller reserve:
        assert decide_strategy(60000, 65536, 8192).strategy == "map_reduce"
        assert decide_strategy(60000, 65536, 4096).strategy == "single_pass"


# ════════════════════════════════════════════════════════════════════════════
# 3. BOUNDARY — the 32768/32769 switch
# ════════════════════════════════════════════════════════════════════════════


class TestBoundary:
    """window=32769 is the first adaptive window."""

    OUTPUT = 8192
    USABLE_32769 = 32769 - 8192 - 700 - 512  # 23365

    def test_32768_is_still_legacy(self):
        d = decide_strategy(13000, 32768, self.OUTPUT)
        assert d.strategy == "b4_sections"  # legacy: 13000 > 12000 → B4
        assert d.map_chunk_tokens == 4000

    def test_32769_is_adaptive_single_pass_for_fitting_chapters(self):
        """Just above the legacy window, adaptive math applies: a 13k
        chapter that would B4 at 32768 now fits in ONE call."""
        d = decide_strategy(13000, 32769, self.OUTPUT)
        assert d.strategy == "single_pass"
        assert f"usable {self.USABLE_32769:,}" in d.reason

    def test_32769_boundary_arithmetic(self):
        assert decide_strategy(self.USABLE_32769, 32769, self.OUTPUT).strategy == "single_pass"
        assert decide_strategy(self.USABLE_32769 + 1, 32769, self.OUTPUT).strategy == "map_reduce"
        assert decide_strategy(self.USABLE_32769 + 1, 32769, self.OUTPUT).map_chunk_tokens == 4096


# ════════════════════════════════════════════════════════════════════════════
# 4. PURITY — decide_strategy must stay a PURE function
# ════════════════════════════════════════════════════════════════════════════


class TestPurity:
    """The strategy picker is a PURE function of (src_tokens, window,
    output_target): no I/O, no Settings, no LLM, no registry probes."""

    def test_frozen_dataclass(self):
        d = decide_strategy(1000, 32768, 8192)
        assert isinstance(d, StrategyDecision)
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.strategy = "map_reduce"  # type: ignore[misc]

    def test_function_source_has_no_io_or_settings_reads(self):
        """Checked on the function BODY with the docstring stripped (the
        docstring legitimately *explains* that Settings is never read)."""
        tree = ast.parse(inspect.getsource(decide_strategy))
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        body = list(func.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]  # drop the docstring
        code = "\n".join(ast.unparse(stmt) for stmt in body)
        for banned in (
            "Settings",
            ".get(",
            "open(",
            "self",
            "request",
            "get_registry",
            "subprocess",
            "import ",
        ):
            assert banned not in code, f"decide_strategy body must not contain {banned!r}"

    def test_module_import_rules(self):
        """strategy.py imports ONLY stdlib + core.llm.context_budget (the
        P6 spec constraint) — verified on the AST, not a substring."""
        tree = ast.parse(
            (_project_root / "core" / "summarisation" / "strategy.py").read_text(encoding="utf-8")
        )
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert imported <= {"__future__", "dataclasses", "typing", "core.llm.context_budget"}, (
            f"strategy.py imports {imported - {'__future__', 'dataclasses', 'typing', 'core.llm.context_budget'}}"
        )

    def test_window_zero_raises(self):
        with pytest.raises(ValueError):
            decide_strategy(1000, 0, 8192)


# ════════════════════════════════════════════════════════════════════════════
# 5. WIRING PINS (P6-b) — the 4 dispatch sites consult decide_strategy
# ════════════════════════════════════════════════════════════════════════════


class TestWiringPins:
    """Source-pin style (house precedent: test_vram_recovery.py,
    test_deadline_watchdog.py) — the dispatch sites route through
    decide_strategy, the MAP_CHUNK geometry flows from the decision, and
    _prepare_text keeps its legacy math."""

    def test_map_reduce_dispatch_routes_through_decide_strategy(self):
        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        assert "decide_strategy" in src, "map-reduce dispatch must consult decide_strategy"
        assert '_p6_decision.strategy == "map_reduce"' in src
        # MAP_CHUNK flows from the decision (== 4000 at legacy windows):
        assert "map_chunk_tokens=_p6_decision.map_chunk_tokens" in src
        assert "map_chunk_overlap=_p6_decision.overlap" in src
        # …and the literal 40000 comparison is GONE (replaced by the decision):
        assert "src_tokens > self.MAP_REDUCE_THRESHOLD" not in src

    def test_b4_dispatch_routes_through_decide_strategy(self):
        from core.summarisation.summarizer import Summarizer

        # V0.18 (Phase 5.1, steps 2-4): the B4 dispatch gate moved VERBATIM
        # to the single-pass phase method.
        src = inspect.getsource(Summarizer._phase_single_pass_primary)
        # Legacy leg kept (byte-parity with the pre-P6 gate) AND the
        # decision leg (disables B4 above the legacy window):
        assert "tok_in > _b4_threshold" in src
        assert '_b4_decision.strategy == "b4_sections"' in src

    def test_decision_uses_live_window_output_and_settings_b4(self):
        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        assert 'getattr(self.request, "summarisation_max_context_tokens", 32768)' in src
        assert 'getattr(self.request, "summarisation_max_output_tokens", 8192)' in src
        # the settings-driven b4 threshold still flows through:
        assert "summarisation.b4_threshold_tokens" in src

    def test_one_info_log_per_chapter(self):
        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        assert "strategy={_p6_decision.strategy}" in src
        assert "src={src_tokens:,} tok / window={_p6_window:,} / output={_p6_output:,}" in src
        assert "{_p6_decision.reason}" in src

    def test_primary_call_chunked_gate_has_window_guard(self):
        import core.summarisation.primary_call as pc_mod

        src = inspect.getsource(pc_mod.summarize_with_model)
        # the legacy gates stay byte-identical…
        assert "_input_tokens_actual > 12000" in src
        assert "_max_out < 14000" in src
        # …and the V0.10 (P6) window guard is ANDed in:
        assert "_window_tokens <= LEGACY_WINDOW" in src
        assert 'getattr(request, "summarisation_max_context_tokens", LEGACY_WINDOW)' in src

    def test_prepare_text_math_unchanged(self):
        """P6 spec B.4: _prepare_text keeps its ctx-out-700 floor-8000 math
        — it stays the final truncation safety net, NOT rewired."""
        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._prepare_text)
        # V0.13: the long expression is format-wrapped across 3 lines — pin the
        # three operands in order instead of one contiguous string.
        assert "self.request.summarisation_max_context_tokens" in src
        assert "self.request.summarisation_max_output_tokens" in src
        assert "- 700" in src
        assert "if max_tok < 8000:" in src

    def test_map_reduce_summarize_accepts_decision_geometry(self):
        """_map_reduce_summarize takes the decision's chunk geometry; the
        instance constants remain the fallback (legacy parity)."""
        import types

        import core.summarisation.summarizer as sz_mod
        from core.summarisation.summarizer import Summarizer

        captured: dict = {}

        def _fake_mr(heading, content, **kw):
            captured.clear()
            captured.update(kw)
            return ("raw-response", 4242)

        # summarizer binds the name at module import — patch it there.
        original = sz_mod.mr_map_reduce_summarize
        sz_mod.mr_map_reduce_summarize = _fake_mr
        try:
            s = object.__new__(Summarizer)
            s.primary_model = "m"
            s.temperature = 0.2
            s.cache_dir = Path(tempfile.mkdtemp())
            s.MAP_CHUNK_TOKENS = 4000
            s.MAP_CHUNK_OVERLAP = 0.10
            s.MAP_MINI_WORDS = 300
            s.local_chapter_deadline = 0
            s.request = types.SimpleNamespace(
                input_path=Path("book.pdf"),
                summarisation_cache_enabled=False,
            )
            s._build_prompt = lambda *a, **k: "PROMPT"
            s._call_llm = lambda *a, **k: "RAW"
            s.log = lambda *a, **k: None

            # No kwargs → instance-constant fallback (the pre-P6 behavior):
            raw, n = s._map_reduce_summarize("H", "C")
            assert (raw, n) == ("raw-response", 4242)
            assert captured["map_chunk_tokens"] == 4000
            assert captured["map_chunk_overlap"] == 0.10
            assert captured["map_mini_words"] == 300

            # Decision-driven geometry (the 220k rig: 27,500-token chunks):
            raw, n = s._map_reduce_summarize(
                "H", "C", map_chunk_tokens=27500, map_chunk_overlap=0.10
            )
            assert captured["map_chunk_tokens"] == 27500
            assert captured["map_chunk_overlap"] == 0.10
        finally:
            sz_mod.mr_map_reduce_summarize = original


class _FakeRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class TestChunkedGateBehavior:
    """Behavioral pin for the primary_call window guard (V18.3.5 gates +
    the V0.10 P6 leg). Mirrors the tests/test_primary_call.py harness."""

    @staticmethod
    def _run(monkeypatch, window, n_tokens=13000, max_out=8192):
        import subprocess

        import core.summarisation.primary_call as pc_mod
        import utils.token_counter as tc

        pc_mod._gpu_temp_cache.update({"valid": 0.0, "temp": 0.0, "ts": 0.0})
        monkeypatch.setattr(tc, "count_tokens", lambda text: n_tokens)

        def _fake_run(*a, **kw):
            raise FileNotFoundError("no nvidia-smi in test env")

        monkeypatch.setattr(subprocess, "run", _fake_run)

        chunked_calls: list[int] = []

        def _chunked(*a, **kw):
            chunked_calls.append(1)
            return {"bullet_points": ["chunked"], "from_chunked": True}

        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            max_tokens=max_out,
            request=_FakeRequest(summarisation_max_context_tokens=window),
            log=lambda m, l="INFO": None,
            chunked_summarize=_chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["single-pass"]},
            call_llm_with_empty_retry=lambda *a, **k: None,
            strip_thinking=lambda x: x,
            parse_response=lambda x: {"bullet_points": []},
        )
        return result, len(chunked_calls)

    def test_legacy_window_still_chunks(self, monkeypatch):
        """window=32768: input 13000 > 12000, output 8192 < 14000, thermal
        ok → chunked path fires (V18.3.5 behavior byte-identical)."""
        result, n_chunked = self._run(monkeypatch, 32768)
        assert n_chunked == 1
        assert result == {"bullet_points": ["chunked"], "from_chunked": True}

    def test_220k_window_never_chunks(self, monkeypatch):
        """window=220000 (the 220k rig): the SAME input/output that chunks
        at 32k goes single-pass — the chunked-output path is disabled
        above LEGACY_WINDOW."""
        result, n_chunked = self._run(monkeypatch, 220000)
        assert n_chunked == 0
        assert result["bullet_points"] == ["single-pass"]

    def test_request_without_window_defaults_to_legacy(self, monkeypatch):
        """No context value on the request → default 32768 → legacy gate."""
        import subprocess

        import core.summarisation.primary_call as pc_mod
        import utils.token_counter as tc

        pc_mod._gpu_temp_cache.update({"valid": 0.0, "temp": 0.0, "ts": 0.0})
        monkeypatch.setattr(tc, "count_tokens", lambda text: 13000)
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError)
        )
        chunked_calls: list[int] = []
        result = pc_mod.summarize_with_model(
            "h",
            "text",
            "m",
            0.7,
            max_tokens=8192,
            request=_FakeRequest(),  # no summarisation_max_context_tokens
            log=lambda m, l="INFO": None,
            chunked_summarize=lambda *a, **k: chunked_calls.append(1) or {"from_chunked": True},
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["single-pass"]},
            call_llm_with_empty_retry=lambda *a, **k: None,
            strip_thinking=lambda x: x,
            parse_response=lambda x: {"bullet_points": []},
        )
        assert len(chunked_calls) == 1  # legacy default window → chunked fires
        assert result == {"from_chunked": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
