"""V0.09 (P5): ModelRegistry + ContextBudget tests (spec section D).

Covers the two new core/llm modules:

  - ``core.llm.registry`` — per-model context-window resolution
    (settings override > /api/show probe > Modelfile num_ctx > static
    table > name hints > backend defaults; local 220,144 cap; VRAM-ladder
    bound for discovered values; max_output rules).
  - ``core.llm.context_budget`` — tokenizer-aware fit math with the 32k
    legacy-parity pins (chunk 4000, max_source 23364).

NO NETWORK: the /api/show probe is never allowed to hit a real socket in
this file — the autouse fixture replaces ``core.llm.registry._ollama_show_probe``
with a bomb; tests that WANT a probe monkeypatch it on top (their patch is
applied later, so it wins).  The wiring classes at the bottom are added in
the P5-b commit.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import core.llm.registry as registry_mod
from core.llm.context_budget import (
    ContextBudget,
    chunk_size,
    count_tokens,
    fits,
    make_budget,
    max_source_tokens,
)
from core.llm.registry import (
    ModelRegistry,
    backend_for_provider,
    get_registry,
)
from utils.token_counter import count_tokens as _real_count_tokens

# tests/conftest.py inserts the project root into sys.path (and pins the
# real tiktoken + utils.token_counter) before any test module loads.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════
# Hermetic fixtures
# ═══════════════════════════════════════════════════════════════════════════


class _FakeSettings:
    """Stand-in for utils.settings.Settings (hermetic — no settings.json).

    Returns controlled values from .get(key, default) so registry tests
    never depend on (or mutate) the machine's real ~/.elixir/settings.json.
    """

    def __init__(self, values: dict | None = None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture(autouse=True)
def _hermetic_registry(monkeypatch):
    """Every test in this file runs with:

    1. a fake Settings (default: NO llm.context_window_overrides, registry
       enabled) — patch ``utils.settings.Settings`` per-test for variants;
    2. a RECORDING fake /api/show probe that returns None ("offline") —
       the REAL probe (which opens a socket) is monkeypatched out for the
       whole file, so no test can touch the network; tests that want a
       live-probe shape re-patch ``_ollama_show_probe`` on top;
    3. a recording fake Modelfile harvester (same contract: no `ollama`
       CLI subprocess in tests);
    4. a clean discovery cache on the process-wide singleton (probe/table
       results must never leak between tests).
    """
    monkeypatch.setattr("utils.settings.Settings", lambda: _FakeSettings())

    probe_calls: list = []

    def _offline_probe(model, base_url):
        probe_calls.append((model, base_url))
        return None  # "offline" — the real probe's failure contract

    def _offline_modelfile(model):
        return None  # no `ollama` CLI in the sandbox

    monkeypatch.setattr(registry_mod, "_ollama_show_probe", _offline_probe)
    monkeypatch.setattr(registry_mod, "_modelfile_num_ctx", _offline_modelfile)
    get_registry()._cache.clear()
    yield
    get_registry()._cache.clear()


def _inject_probe(monkeypatch, value: int | None, calls: list | None = None):
    """Replace the offline fake probe with a deterministic one (opt-in).

    The real probe NEVER raises (it catches internally and returns None on
    any failure), so ``value=None`` simulates a failed/offline probe and an
    int simulates a successful /api/show response."""

    def _probe(model, base_url):
        if calls is not None:
            calls.append((model, base_url))
        return value

    monkeypatch.setattr(registry_mod, "_ollama_show_probe", _probe)
    return _probe


# ═══════════════════════════════════════════════════════════════════════════
# A. Registry — backend defaults + taxonomy
# ═══════════════════════════════════════════════════════════════════════════


class TestBackendDefaults:
    """Rung 6: backend defaults reproduce TODAY's values exactly."""

    @pytest.mark.parametrize(
        "backend,expected",
        [
            ("ollama", 32768),  # matches settings.py:204 max_context_tokens
            ("llamacpp", 65536),  # matches the llm_provider_impl default
            ("openai_compat", 131072),
            ("claude", 200000),
        ],
    )
    def test_bare_call_returns_backend_default(self, backend, expected):
        reg = ModelRegistry()
        assert reg.get_context_window("totally-unknown-model:latest", backend) == expected

    def test_unknown_backend_normalizes_to_ollama(self):
        reg = ModelRegistry()
        assert reg.get_context_window("m", "weird-backend") == 32768

    def test_provider_strings_map_to_backends(self):
        assert backend_for_provider("ollama") == "ollama"
        assert backend_for_provider("llamacpp") == "llamacpp"
        assert backend_for_provider("openrouter") == "openai_compat"
        assert backend_for_provider("openai") == "openai_compat"
        assert backend_for_provider("openai_compatible") == "openai_compat"
        assert backend_for_provider("freellmapi") == "openai_compat"
        assert backend_for_provider("claude") == "claude"
        assert backend_for_provider("fusion") == "ollama"
        # canonical backend names pass through (both vocabularies accepted)
        assert backend_for_provider("openai_compat") == "openai_compat"
        # unknown → ollama (mirrors create_provider's else-branch)
        assert backend_for_provider("lmstudio") == "ollama"
        assert backend_for_provider(None) == "ollama"

    def test_capability_returns_none_for_unknown_models(self):
        """None (not the backend default) — callers must be able to tell
        'known 8k model' from 'unknown model' (the backend default is NOT
        a capability)."""
        reg = ModelRegistry()
        assert reg.get_capability("totally-unknown-model:latest", "ollama") is None


# ═══════════════════════════════════════════════════════════════════════════
# B. Registry — static table + name hints
# ═══════════════════════════════════════════════════════════════════════════


class TestStaticTable:
    """Rung 4: the static REGISTRY table."""

    def test_ternary_bonsai_220k(self):
        """The user's 220k llama.cpp model (Task 8 decision #4) — prefix
        match covers the -Instruct-Vision variant and future variants."""
        reg = ModelRegistry()
        assert reg.get_capability("Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp") == 220000
        assert reg.get_capability("ternary-bonsai-2-27b-some-future-variant", "llamacpp") == 220000

    def test_common_ollama_models(self):
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 8192
        assert reg.get_capability("llama3.1:8b", "ollama") == 131072
        assert reg.get_capability("gemma3:12b", "ollama") == 128000

    def test_deepseek_api_models(self):
        """deepseek* → 128000; the exact 'deepseek v4 flash' 1M entry
        (Task 8 decision #2) beats the prefix."""
        reg = ModelRegistry()
        assert reg.get_capability("deepseek-chat", "openai_compat") == 128000
        assert reg.get_capability("Deepseek-R1", "openai_compat") == 128000
        assert reg.get_capability("deepseek v4 flash", "openai_compat") == 1000000

    def test_exact_beats_prefix(self):
        reg = ModelRegistry()
        # "deepseek v4 flash" is an exact key AND matches "deepseek*";
        # the exact entry (1M) must win.
        assert reg.get_capability("deepseek v4 flash", "openai_compat") == 1_000_000

    def test_table_match_is_case_insensitive(self):
        reg = ModelRegistry()
        assert reg.get_capability("LLAMA3:8B", "ollama") == 8192


class TestNameHints:
    """Rung 5: context declarations embedded in the model NAME.

    The Task 3-b audit's finding: "The '-1M' tag in the new model's name
    is parsed by nothing" — P5 parses it.
    """

    def test_k_hint(self):
        reg = ModelRegistry()
        assert reg.get_capability("my-model-220k", "llamacpp") == 220000
        assert reg.get_capability("qwen_custom_128k", "ollama") == 128000

    def test_m_hint_api_only(self):
        """'1M' tags → 1M windows on API backends ONLY (Task 8 decision
        #2: 1M-class is API-only)."""
        reg = ModelRegistry()
        assert (
            reg.get_capability("Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M", "openai_compat") == 1_000_000
        )
        # ...and NOT on local backends:
        assert reg.get_capability("Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M", "ollama") is None
        assert reg.get_capability("Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M", "llamacpp") is None

    @pytest.mark.parametrize(
        "model",
        [
            "Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest",
            "Qwen3.8-27B-UD-Q2_K_XL:latest",
            "some-model-name-Q2_K:latest",
            "model-Q4_K_M:latest",
            "gemma4-12b:latest",
            "test-model:latest",
        ],
    )
    def test_no_misfire_on_today_model_names(self, model):
        """REGRESSION GUARD: none of the models used across the existing
        suite / the rig today may accidentally match a hint (the k-regex
        is case-sensitive lowercase so quant tags like Q4_K_M can't hit;
        the M-hint is API-only so local -1M names can't claim 1M)."""
        reg = ModelRegistry()
        assert reg.get_capability(model, "ollama") is None


# ═══════════════════════════════════════════════════════════════════════════
# C. Registry — caps (Task 8 decision #2)
# ═══════════════════════════════════════════════════════════════════════════


class TestCaps:
    """Local backends capped at 220,144; API backends uncapped (1M ok)."""

    def test_local_cap_on_configured(self):
        reg = ModelRegistry()
        assert reg.get_context_window("m", "llamacpp", configured=300000) == 220144
        assert reg.get_context_window("m", "ollama", configured=262144) == 220144
        # at/below the cap: unchanged
        assert reg.get_context_window("m", "ollama", configured=32768) == 32768

    def test_local_cap_on_table_hit(self):
        reg = ModelRegistry()
        # 220000 < 220144 → unchanged
        assert reg.get_context_window("Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp") == 220000

    def test_api_uncapped(self):
        reg = ModelRegistry()
        assert reg.get_context_window("m", "openai_compat", configured=2_000_000) == 2_000_000
        assert reg.get_context_window("deepseek v4 flash", "openai_compat") == 1_000_000

    def test_local_1m_hint_suppressed(self):
        reg = ModelRegistry()
        # unknown model named "-1M" on a LOCAL backend: no hint, backend default.
        assert reg.get_context_window("model-1M", "ollama") == 32768

    def test_local_override_capped_at_220144(self):
        """Even an explicit user override is local-capped (1M is API-only)."""
        fake = _FakeSettings({"llm.context_window_overrides": {"m1": 1_000_000}})
        from unittest.mock import patch

        with patch("utils.settings.Settings", lambda: fake):
            reg = ModelRegistry()
            assert reg.get_context_window("m1", "llamacpp") == 220144
            assert reg.get_context_window("m1", "openai_compat") == 1_000_000


# ═══════════════════════════════════════════════════════════════════════════
# D. Registry — override priority + VRAM bound + raise-only floor
# ═══════════════════════════════════════════════════════════════════════════


class TestOverridePriority:
    """Rung 1: llm.context_window_overrides (absent by default)."""

    def test_override_beats_configured_and_table(self):
        fake = _FakeSettings(
            {
                "llm.context_window_overrides": {
                    "Ternary-Bonsai-2-27B-Instruct-Vision": 99999,
                }
            }
        )
        from unittest.mock import patch

        with patch("utils.settings.Settings", lambda: fake):
            reg = ModelRegistry()
            assert (
                reg.get_context_window(
                    "Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp", configured=65536
                )
                == 99999
            )

    def test_override_supports_wildcard_and_case_insensitive(self):
        fake = _FakeSettings({"llm.context_window_overrides": {"llama3*": 55555}})
        from unittest.mock import patch

        with patch("utils.settings.Settings", lambda: fake):
            reg = ModelRegistry()
            assert reg.get_capability("LLAMA3:8B", "ollama") == 55555

    def test_override_for_other_model_ignored(self):
        fake = _FakeSettings({"llm.context_window_overrides": {"other-model": 99999}})
        from unittest.mock import patch

        with patch("utils.settings.Settings", lambda: fake):
            reg = ModelRegistry()
            assert reg.get_context_window("llama3:8b", "ollama", configured=32768) == 32768

    def test_no_override_key_by_default(self):
        """The new settings key is ABSENT by default (no settings.json
        churn) — resolution must be identical with an empty settings."""
        reg = ModelRegistry()
        assert reg.get_context_window("llama3:8b", "ollama", configured=32768) == 32768


class TestVramBoundAndFloor:
    """The Summarizer shape: base floor + VRAM-ladder bound."""

    def test_discovered_window_bounded_by_ladder(self):
        reg = ModelRegistry()
        # 220k model on a small rig (ladder 65536) → 65536
        assert (
            reg.get_context_window(
                "Ternary-Bonsai-2-27B-Instruct-Vision",
                "llamacpp",
                base=32768,
                vram_limit_fn=lambda: 65536,
            )
            == 65536
        )
        # ...on a big rig (ladder 262144) → the full capability
        assert (
            reg.get_context_window(
                "Ternary-Bonsai-2-27B-Instruct-Vision",
                "llamacpp",
                base=32768,
                vram_limit_fn=lambda: 262144,
            )
            == 220000
        )

    def test_explicit_configured_not_ladder_reduced(self):
        """Pre-P5 semantics: an explicit value was never ladder-bounded
        (the ladder only replaced <= 16000 values or raised the floor)."""
        reg = ModelRegistry()
        assert (
            reg.get_context_window("m", "ollama", configured=200000, vram_limit_fn=lambda: 65536)
            == 200000
        )

    def test_base_floor_never_lowered(self):
        """Discovery only ever RAISES the pipeline floor — a known
        8192-token model must not shrink a 32768 pipeline (that lowering
        decision belongs to P6)."""
        reg = ModelRegistry()
        assert reg.get_context_window("llama3:8b", "ollama", base=32768) == 32768

    def test_unknown_model_base_returned_unchanged(self):
        reg = ModelRegistry()
        assert (
            reg.get_context_window(
                "totally-unknown:latest", "ollama", base=131072, vram_limit_fn=lambda: 65536
            )
            == 131072
        )

    def test_broken_ladder_ignored(self):
        reg = ModelRegistry()
        assert (
            reg.get_context_window(
                "Ternary-Bonsai-2-27B-Instruct-Vision",
                "llamacpp",
                base=32768,
                vram_limit_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            == 220000
        )

    def test_ladder_not_applied_to_api_backends(self):
        reg = ModelRegistry()
        assert (
            reg.get_context_window(
                "deepseek v4 flash", "openai_compat", base=32768, vram_limit_fn=lambda: 65536
            )
            == 1_000_000
        )


# ═══════════════════════════════════════════════════════════════════════════
# E. Registry — probe (offline safety), Modelfile rung, cache, kill switch
# ═══════════════════════════════════════════════════════════════════════════


class TestProbeOfflineSafety:
    """The /api/show probe: injectable, cached, failure-tolerant, and
    NEVER a live socket in this suite (the autouse fixture bombs it)."""

    def test_probe_beats_table(self, monkeypatch):
        calls: list = []
        _inject_probe(monkeypatch, 4096, calls)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 4096
        assert len(calls) == 1

    def test_probe_failure_falls_through_to_table(self, monkeypatch):
        """A failed probe (the real one returns None on ANY failure —
        offline, 404, timeout, malformed) must fall through, never raise."""
        _inject_probe(monkeypatch, None)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 8192

    def test_probe_none_falls_through_to_table(self, monkeypatch):
        _inject_probe(monkeypatch, None)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 8192

    def test_probe_cached_per_model(self, monkeypatch):
        calls: list = []
        _inject_probe(monkeypatch, 4096, calls)
        reg = ModelRegistry()
        reg.get_capability("llama3:8b", "ollama")
        reg.get_capability("llama3:8b", "ollama")
        reg.get_context_window("llama3:8b", "ollama")
        assert len(calls) == 1, "successful discoveries must be cached (LRU-ish)"

    def test_invalidate_forces_reprobe(self, monkeypatch):
        calls: list = []
        _inject_probe(monkeypatch, 4096, calls)
        reg = ModelRegistry()
        reg.get_capability("llama3:8b", "ollama")
        reg.invalidate("llama3:8b", "ollama")
        reg.get_capability("llama3:8b", "ollama")
        assert len(calls) == 2

    def test_probe_disabled_switch(self, monkeypatch):
        """PROBE_ENABLED=False: the REAL probe returns None BEFORE any
        socket/HTTP import — proven by bombing utils.network."""
        import utils.network as network_mod

        def _socket_bomb(*args, **kwargs):  # pragma: no cover — must never run
            raise AssertionError("socket attempted despite PROBE_ENABLED=False")

        monkeypatch.setattr(network_mod, "safe_ollama_request", _socket_bomb)
        monkeypatch.setattr(registry_mod, "PROBE_ENABLED", False)
        assert registry_mod._ollama_show_probe("any-model", "http://x:1") is None
        # and through the registry: disabled probe → table rung
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 8192

    def test_probe_only_for_ollama_backend(self, monkeypatch):
        calls: list = []
        _inject_probe(monkeypatch, 999999, calls)
        reg = ModelRegistry()
        assert reg.get_capability("Ternary-Bonsai-2-27B-x", "llamacpp") == 220000
        assert reg.get_capability("deepseek-chat", "openai_compat") == 128000
        assert calls == [], "llamacpp/API backends must never hit /api/show"

    def test_allow_probe_false_skips_probe(self, monkeypatch):
        calls: list = []
        _inject_probe(monkeypatch, 4096, calls)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama", allow_probe=False) == 8192
        assert calls == []

    def test_modelfile_rung_after_probe(self, monkeypatch):
        """Probe resolves → the Modelfile CLI rung is never reached."""
        _inject_probe(monkeypatch, 2048)

        def _modelfile_bomb(model):  # pragma: no cover — must never run
            raise AssertionError("Modelfile rung reached despite probe success")

        monkeypatch.setattr(registry_mod, "_modelfile_num_ctx", _modelfile_bomb)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 2048

    def test_modelfile_rung_used_when_probe_fails(self, monkeypatch):
        _inject_probe(monkeypatch, None)
        monkeypatch.setattr(registry_mod, "_modelfile_num_ctx", lambda model: 16384)
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 16384


class TestKillSwitch:
    """llm.model_registry_enabled == False → pure legacy passthrough."""

    def test_passthrough_configured(self, monkeypatch):
        fake = _FakeSettings({"llm.model_registry_enabled": False})
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)
        reg = ModelRegistry()
        # table hit ignored, caps NOT applied, base returned as-is
        assert (
            reg.get_context_window(
                "Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp", configured=65536
            )
            == 65536
        )
        assert reg.get_context_window("m", "llamacpp", base=32768) == 32768
        assert reg.get_capability("Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp") is None

    def test_enabled_by_default(self):
        reg = ModelRegistry()
        assert reg.get_capability("llama3:8b", "ollama") == 8192


# ═══════════════════════════════════════════════════════════════════════════
# F. Registry — max_output rules (Task 8 decision #1)
# ═══════════════════════════════════════════════════════════════════════════


class TestMaxOutput:
    def test_ollama_8192(self):
        reg = ModelRegistry()
        assert reg.get_max_output("any-model:latest", "ollama") == 8192

    def test_llamacpp_from_65536_config(self):
        """llama.cpp uses the 65536-context config's output value
        (summarisation.llamacpp_max_output_tokens, default 12288)."""
        reg = ModelRegistry()
        assert reg.get_max_output("Ternary-Bonsai-2-27B-Instruct-Vision", "llamacpp") == 12288

    def test_llamacpp_config_override_respected(self, monkeypatch):
        fake = _FakeSettings({"summarisation.llamacpp_max_output_tokens": 4096})
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)
        reg = ModelRegistry()
        assert reg.get_max_output("m", "llamacpp") == 4096

    def test_api_default_8192(self):
        reg = ModelRegistry()
        assert reg.get_max_output("some-unknown-api-model", "openai_compat") == 8192

    def test_api_model_specific(self):
        reg = ModelRegistry()
        assert reg.get_max_output("gpt-4o", "openai_compat") == 16384


# ═══════════════════════════════════════════════════════════════════════════
# G. Import-surface constraints (no cycles)
# ═══════════════════════════════════════════════════════════════════════════


class TestImportSurface:
    """P5 constraint: the two new modules must never import
    core.summarisation / core.system (import-cycle rule), and registry's
    module-level imports are stdlib-only (utils.* / core.llm.* are lazy,
    inside functions)."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "core/llm/registry.py",
            "core/llm/context_budget.py",
        ],
    )
    def test_no_forbidden_module_level_imports(self, relpath):
        src = (_PROJECT_ROOT / relpath).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("core.summarisation"), (
                    f"{relpath} imports {name} — core.summarisation is forbidden"
                )
                assert not name.startswith("core.system"), (
                    f"{relpath} imports {name} — core.system is forbidden"
                )

    def test_registry_module_level_imports_stdlib_only(self):
        src = (_PROJECT_ROOT / "core/llm/registry.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Only look at MODULE-LEVEL import statements (depth 0-1 of the tree)
        top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert top_level, "expected module-level imports to inspect"
        for node in top_level:
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                assert not name.startswith("core."), (
                    f"registry.py must not import {name} at module level "
                    "(lazy imports inside functions only)"
                )

    def test_context_budget_imports_utils_only(self):
        src = (_PROJECT_ROOT / "core/llm/context_budget.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        for node in top_level:
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                assert name.startswith(("utils", "stdlib_placeholder")) or name in (
                    "dataclasses",
                    "typing",
                    "logging",
                    "re",
                    "threading",
                    "collections",
                    "functools",
                    "math",
                    "abc",
                    "__future__",
                ), f"unexpected module-level import {name!r} in context_budget.py"


# ═══════════════════════════════════════════════════════════════════════════
# H. ContextBudget — the 32k legacy-parity pins
# ═══════════════════════════════════════════════════════════════════════════


class TestContextBudgetMath:
    def test_make_budget_defaults_at_32k(self):
        b = make_budget(32768)
        assert isinstance(b, ContextBudget)
        assert b.window == 32768
        assert b.output_reserve == 8192  # min(8192, 32768//4)
        assert b.prompt_overhead == 512
        assert b.margin == 700  # the legacy _prepare_text margin

    def test_output_reserve_scales_on_small_windows(self):
        assert make_budget(16384).output_reserve == 4096  # 16384//4
        assert make_budget(8192).output_reserve == 2048  # 8192//4

    def test_explicit_output_reserve(self):
        assert make_budget(32768, output_reserve=4096).output_reserve == 4096

    def test_max_source_tokens_32k_parity(self):
        """SPEC PIN: at window=32768, output_reserve=8192, margin=700:
        max_source_tokens == 32768 - 8192 - 512 - 700 == 23364.

        (Today's _prepare_text computes ctx - out - 700 == 23876 with NO
        prompt_overhead term; the 512 is P5's slightly-more-conservative
        prompt-scaffold reserve, adopted so P6's switchover can never
        OVERFLOW where the legacy code fit. _prepare_text itself is NOT
        rewired in P5 — its behavior is unchanged until P6.)"""
        b = make_budget(32768)
        assert max_source_tokens(b) == 23364

    def test_fits_boundary(self):
        b = make_budget(32768)
        assert fits(23364, b) is True
        assert fits(23365, b) is False

    def test_fits_takes_tokens_not_chars(self):
        b = make_budget(32768)
        # 100k chars of merged-token text ('x' runs) is ~12.5k tokens, NOT 25k
        wall = "x" * 100_000
        assert count_tokens(wall) < max_source_tokens(b)
        assert fits(count_tokens(wall), b) is True

    def test_count_tokens_is_the_tiktoken_counter(self):
        """The re-export must be the REAL utils.token_counter function —
        the provider path must not grow a second counting implementation."""
        assert count_tokens is _real_count_tokens

    def test_invalid_window_rejected(self):
        with pytest.raises(ValueError):
            make_budget(0)
        with pytest.raises(ValueError):
            make_budget(-5)


class TestChunkSize:
    """chunk_size: EXACTLY 4000 (the legacy MAP_CHUNK_TOKENS) at every
    window <= 32768; window//8 clamped [4000, 32000] above it."""

    @pytest.mark.parametrize("window", [8192, 16384, 24576, 32768])
    def test_legacy_4000_at_32k_and_below(self, window):
        assert chunk_size(make_budget(window)) == 4000

    @pytest.mark.parametrize(
        "window,expected",
        [
            (65536, 8192),
            (131072, 16384),
            (220000, 27500),  # the 220k model
            (262144, 32000),  # clamped at the ceiling
            (1048576, 32000),
        ],
    )
    def test_scaled_above_32k(self, window, expected):
        assert chunk_size(make_budget(window)) == expected

    def test_strategy_param_accepted(self):
        b = make_budget(32768)
        assert chunk_size(b, "map_reduce") == 4000
        assert chunk_size(b, "b4_section_map") == 4000


# ═══════════════════════════════════════════════════════════════════════════
# I. WIRING (P5-b) — create_provider + Summarizer + provider token math
# ═══════════════════════════════════════════════════════════════════════════


class TestFactoryWiring:
    """create_provider routes ctx through the registry with the SETTINGS
    value as the ``configured`` override — byte-identical at today's
    defaults, changeable only via the new override key / the local cap."""

    @staticmethod
    def _factory_settings(values: dict | None = None) -> _FakeSettings:
        base = {
            "summarisation.model": "gemma4-12b:latest",
            "summarisation.temperature": 0.6,
            "summarisation.max_output_tokens": 4096,
            "summarisation.max_context_tokens": 32768,
            "summarisation.llamacpp_model": "Ternary-Bonsai-2-27B-Instruct-Vision",
            "summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1",
            "summarisation.llamacpp_api_key": "local",
            "summarisation.llamacpp_max_output_tokens": 12288,
            "summarisation.llamacpp_context_tokens": 65536,
            "local.http_timeout_sec": 600,
        }
        base.update(values or {})
        return _FakeSettings(base)

    def test_ollama_defaults_byte_identical(self):
        """The default 32k passes through untouched (settings.py:204)."""
        from core.llm.llm_provider import create_provider

        p = create_provider("ollama", self._factory_settings())
        assert type(p).__name__ == "OllamaProvider"
        assert p.context_tokens == 32768

    def test_llamacpp_defaults_byte_identical(self):
        """The default 65k passes through untouched — INCLUDING for the
        Ternary-Bonsai model (the 220k table hit must stay inert at the
        factory: the settings value wins; pinned jointly with
        tests/test_v004_llamacpp.py::TestFactoryWiring)."""
        from core.llm.llm_provider import create_provider

        p = create_provider("llamacpp", self._factory_settings())
        assert type(p).__name__ == "LlamaCppProvider"
        assert p.model == "Ternary-Bonsai-2-27B-Instruct-Vision"
        assert p.context_tokens == 65536

    def test_override_key_changes_factory_ctx(self, monkeypatch):
        """The new llm.context_window_overrides key (absent by default)
        is the ONE discovery source that beats the settings value."""
        from core.llm.llm_provider import create_provider

        fake = _FakeSettings(
            {
                "llm.context_window_overrides": {"gemma4-12b:latest": 131072},
            }
        )
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)
        p = create_provider("ollama", self._factory_settings())
        assert p.context_tokens == 131072

    def test_local_cap_applied_at_factory(self):
        """Task 8 #2: a local window above 220,144 is capped (the GUI
        spinbox still allows 262144 — the registry clamps the EFFECTIVE
        window)."""
        from core.llm.llm_provider import create_provider

        p = create_provider(
            "ollama",
            self._factory_settings(
                {
                    "summarisation.max_context_tokens": 262144,
                }
            ),
        )
        assert p.context_tokens == 220144

    def test_absent_settings_key_resolves_to_ollama_default(self):
        """The pre-P5 factory hardcoded a 65536 FALLBACK for
        summarisation.max_context_tokens while the settings default is
        32768 (the Task 3-b "65538-vs-32768 mismatch"). With the key
        absent, the registry now resolves the backend default (32768)."""
        from core.llm.llm_provider import create_provider

        settings = self._factory_settings()
        settings._values.pop("summarisation.max_context_tokens")
        p = create_provider("ollama", settings)
        assert p.context_tokens == 32768


class TestSummarizerCtxWiring:
    """The Summarizer's ctx (settings → VRAM ladder → 32k floor) is routed
    through the registry as the FLOOR: known capabilities only RAISE it."""

    @staticmethod
    def _make_summarizer(monkeypatch, model: str, provider: str, ctx: int):
        """Full Summarizer construction with hermetic settings (the
        test_group_b_characterization.py pattern)."""
        fake = _FakeSettings(
            {
                "summarisation.provider": provider,
                "local.http_timeout_sec": 600,
                "local.chapter_deadline_sec": 0,
                "model_temperatures": {},
            }
        )
        monkeypatch.setattr("core.summarisation.summarizer.Settings", lambda: fake)
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)

        from core.models import ConversionRequest
        from core.summarisation.summarizer import Summarizer

        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.summarisation_model = model
        req.summarisation_max_context_tokens = ctx
        return Summarizer(
            request=req,
            log_callback=lambda m, lvl="INFO": None,
            language="en",
            claim_extractor=None,
        )

    def test_default_settings_identical(self, monkeypatch):
        """Default model (not in the table), default 32k request ctx →
        the registry layer is a NO-OP (byte-identical to pre-P5)."""
        monkeypatch.setattr(
            "core.summarisation.summarizer.Summarizer._auto_detect_context_limit",
            lambda self: 65536,
        )
        s = self._make_summarizer(
            monkeypatch, model="gemma4-12b:latest", provider="ollama", ctx=32768
        )
        assert s.request.summarisation_max_context_tokens == 32768

    def test_220k_model_uses_capability(self, monkeypatch):
        """THE P5 FEATURE: the rig's 220k llama.cpp model raises the
        pipeline window to its capability (ladder permitting — here the
        ladder is monkeypatched to a 24GB-class 262144)."""
        monkeypatch.setattr(
            "core.summarisation.summarizer.Summarizer._auto_detect_context_limit",
            lambda self: 262144,
        )
        s = self._make_summarizer(
            monkeypatch,
            model="Ternary-Bonsai-2-27B-Instruct-Vision",
            provider="llamacpp",
            ctx=32768,
        )
        assert s.request.summarisation_max_context_tokens == 220000

    def test_220k_model_ladder_bounded(self, monkeypatch):
        """Same model on a small rig (ladder 65536): the DISCOVERED window
        is bounded by the VRAM ladder — the pipeline gets 65536, not 220000
        (the escape hatch is an explicit llm.context_window_overrides
        entry, which is never ladder-reduced)."""
        monkeypatch.setattr(
            "core.summarisation.summarizer.Summarizer._auto_detect_context_limit",
            lambda self: 65536,
        )
        s = self._make_summarizer(
            monkeypatch,
            model="Ternary-Bonsai-2-27B-Instruct-Vision",
            provider="llamacpp",
            ctx=32768,
        )
        assert s.request.summarisation_max_context_tokens == 65536

    def test_low_capability_table_entry_never_lowers(self, monkeypatch):
        """llama3:8b (table 8192) with a 32768 pipeline → stays 32768:
        discovery only ever RAISES the floor (lowering is P6's call)."""
        monkeypatch.setattr(
            "core.summarisation.summarizer.Summarizer._auto_detect_context_limit",
            lambda self: 65536,
        )
        s = self._make_summarizer(monkeypatch, model="llama3:8b", provider="ollama", ctx=32768)
        assert s.request.summarisation_max_context_tokens == 32768

    def test_override_key_uses_capability(self, monkeypatch):
        """llm.context_window_overrides names the model → the pipeline
        window becomes the override (explicit user word, not
        ladder-reduced, but still local-capped)."""
        fake = _FakeSettings(
            {
                "summarisation.provider": "ollama",
                "local.http_timeout_sec": 600,
                "local.chapter_deadline_sec": 0,
                "model_temperatures": {},
                "llm.context_window_overrides": {"gemma4-12b:latest": 131072},
            }
        )
        monkeypatch.setattr("core.summarisation.summarizer.Settings", lambda: fake)
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)
        monkeypatch.setattr(
            "core.summarisation.summarizer.Summarizer._auto_detect_context_limit",
            lambda self: 65536,
        )

        from core.models import ConversionRequest
        from core.summarisation.summarizer import Summarizer

        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.summarisation_model = "gemma4-12b:latest"
        req.summarisation_max_context_tokens = 32768
        s = Summarizer(
            request=req,
            log_callback=lambda m, lvl="INFO": None,
            language="en",
            claim_extractor=None,
        )
        assert s.request.summarisation_max_context_tokens == 131072


class TestProviderTokenMathWiring:
    """The two former chars//4 sites now count REAL tokens."""

    def test_adaptive_context_uses_count_tokens(self, monkeypatch):
        """_adaptive_context estimates via core.llm.context_budget
        (tiktoken), not len//4: a 60k-char 'x '-wall is 30k tokens (the
        chars//4 estimate would be 15k)."""
        from core.llm.ollama_provider import OllamaProvider

        p = OllamaProvider(model="m", context_tokens=32768)
        prompt = "x " * 30000  # 60k chars → 30001 tiktoken tokens
        # count_tokens: needed = 30001 + 4096 + 4096 = 38193 → capped at 32768
        # chars//4 (pre-P5): needed = 15000 + 4096 + 4096 = 23192
        assert p._adaptive_context(prompt, max_tokens=4096) == 32768

    def test_adaptive_context_patchable_binding(self, monkeypatch):
        """The consumer-binding patch pattern (the summarizer.py:228
        convention) controls the estimate."""
        from core.llm import ollama_provider

        monkeypatch.setattr(ollama_provider, "_count_tokens", lambda text: 20000)
        p = ollama_provider.OllamaProvider(model="m", context_tokens=32768)
        # needed = 20000 + 4096 + 4096 = 28192 (chars//4 of "tiny" would give 16000)
        assert p._adaptive_context("tiny", max_tokens=4096) == 28192

    def test_fit_max_tokens_uses_count_tokens(self):
        """fit_max_tokens estimates via core.llm.context_budget: the
        240k-char x-wall is 30k REAL tokens, so the 12,288 request FITS
        (under chars//4 the budget would have shrunk to 5024)."""
        from core.llm.llamacpp_provider import LlamaCppProvider

        p = LlamaCppProvider(model="m", context_tokens=65536, output_cap=12288)
        assert p.fit_max_tokens(12288, "x" * 240_000) == 12288
        # ...and a genuine ~60k-token prompt still shrinks to what fits:
        assert p.fit_max_tokens(12288, "word " * 60000) == 65536 - 60001 - 512
