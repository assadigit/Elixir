"""V0.6.10 (B15) — the timeout policy leaf tests.

Pins the AUDIT_SWOT W4 mechanical win: ``core/system/timeouts.py`` is the
single home for the wall-clock budget constants (the tts/ named-constant
precedent, generalized). The 11-value policy table exists; the 10
highest-churn sites (the LLM layer) are migrated; the remaining ~49 sites
are FLAGGED with file:line evidence in the module for the next waves.

Behavior byte-identical: every swap is import + constant, same value — the
pins below assert BOTH the constant values and the migrated call sites.

Run: pytest tests/test_v0610_b15_timeout_leaf.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.system.timeouts import (
    API_BATCH_TIMEOUT_S,
    CLI_POLL_TIMEOUT_S,
    CLI_SWEEP_TIMEOUT_S,
    FAST_LLM_TIMEOUT_S,
    HTTP_FETCH_TIMEOUT_S,
    KEYPOINTS_WHOLE_CALL_TIMEOUT_S,
    LLM_REQUEST_TIMEOUT_S,
    LONG_RUN_TIMEOUT_S,
    SLOW_LLM_TIMEOUT_S,
    SUBSECOND_PROBE_TIMEOUT_S,
    UI_PROBE_TIMEOUT_S,
)


class TestPolicyTable:
    """The 11 magic values (AUDIT_SWOT W4, measured) each have ONE named
    constant with the ORIGINAL value — the policy leaf is documentation
    the compiler can check."""

    def test_the_11_values(self):
        assert SUBSECOND_PROBE_TIMEOUT_S == 2
        assert UI_PROBE_TIMEOUT_S == 5
        assert CLI_POLL_TIMEOUT_S == 10
        assert CLI_SWEEP_TIMEOUT_S == 20
        assert API_BATCH_TIMEOUT_S == 30
        assert HTTP_FETCH_TIMEOUT_S == 60
        assert FAST_LLM_TIMEOUT_S == 120
        assert SLOW_LLM_TIMEOUT_S == 180
        assert LLM_REQUEST_TIMEOUT_S == 300
        assert KEYPOINTS_WHOLE_CALL_TIMEOUT_S == 420
        assert LONG_RUN_TIMEOUT_S == 600

    def test_import_is_side_effect_free(self):
        import importlib

        import core.system.timeouts as t

        importlib.reload(t)  # pure-constants module: reload must be a no-op


def _src(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


class TestMigratedSites:
    """The 10 highest-churn sites (the LLM layer the V0.6.8/V0.6.9 sessions
    touched most) now use the named constants — source pins, one per site."""

    def test_llm_provider_impl_five_sites(self):
        src = _src("core/llm/llm_provider_impl.py")
        # 3x constructor generation timeouts (Ollama, OpenRouter, FreeLLMAPI)
        assert src.count("timeout=LLM_REQUEST_TIMEOUT_S") == 3
        # the Claude constructor's slow-request timeout
        assert src.count("timeout=SLOW_LLM_TIMEOUT_S") == 1
        # the /v1/models detection probe
        assert "list_llamacpp_models(_lc_base, _lc_key, timeout=UI_PROBE_TIMEOUT_S)" in src

    def test_ollama_provider_ps_probe(self):
        src = _src("core/llm/ollama_provider.py")
        assert (
            'safe_ollama_request("GET", f"{self.base_url}/api/ps", timeout=UI_PROBE_TIMEOUT_S)'
            in src
        )

    def test_llamacpp_provider_models_probe(self):
        src = _src("core/llm/llamacpp_provider.py")
        assert "timeout=UI_PROBE_TIMEOUT_S," in src

    def test_primary_call_probe(self):
        src = _src("core/summarisation/primary_call.py")
        assert "timeout=UI_PROBE_TIMEOUT_S," in src

    def test_script_generator_tags_probe(self):
        src = _src("core/podcast/script_generator.py")
        assert "timeout=UI_PROBE_TIMEOUT_S" in src

    def test_dependency_checker_probe(self):
        src = _src("core/system/dependency_checker.py")
        assert "timeout=UI_PROBE_TIMEOUT_S," in src

    def test_no_magic_values_remain_in_migrated_constructors(self):
        """The provider-construction block must carry no bare timeout
        literals anymore (the three 300s + the 180 + the 5)."""
        src = _src("core/llm/llm_provider_impl.py")
        assert "timeout=300" not in src
        assert "timeout=180" not in src
        assert "timeout=5" not in src


class TestFlaggedRemainder:
    """The flagged remainder is DOCUMENTED in the leaf (the charter:
    migrate the highest-churn 10 first, flag the rest) — the module source
    itself carries the evidence snapshot for the next waves."""

    def test_flagged_sections_present(self):
        src = _src("core/system/timeouts.py")
        assert "FLAGGED remainder" in src
        # V0.6.11 (wave 8) pin evolution: a family's flag section is REMOVED
        # from the list when its wave lands (a MIGRATED note replaces it) —
        # the UI-probe family is gone; the not-yet-migrated families stay.
        assert "MIGRATED in V0.6.11 wave 8" in src
        for marker in (
            "CLI_POLL_TIMEOUT_S (10)",
            "FAST_LLM_TIMEOUT_S (120)",
            "SLOW_LLM_TIMEOUT_S (180) remaining",
            "LLM_REQUEST_TIMEOUT_S (300) remaining",
            "LONG_RUN_TIMEOUT_S (600)",
        ):
            assert marker in src, f"missing flag section: {marker}"

    def test_flagged_sites_still_inline_not_yet_migrated(self):
        """Honesty pin: the flagged sites are still inline literals (the
        migration is 10 sites, not a silent mass-replace) — spot-check one
        per family."""
        assert "timeout=600, retries=1" in _src("core/llm/model_manager.py")
        assert "self.timeout = 600" in _src("core/summarisation/summarizer_init.py")
        assert "_provider.timeout = 300" in _src("core/pipeline/conversion/summarization.py")
