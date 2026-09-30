"""V13.40.0: Tests for VRAM recovery + additive-section followup.

Tests verify:
1. _recover_vram exists and doesn't crash (no CUDA in test env)
2. _ensure_additive_sections populates empty sections via followup call
3. _ensure_additive_sections skips when sections already populated
4. _ensure_additive_sections handles followup failure gracefully
5. B4 threshold raised from 8000 → 12000 (chapters under 12k use single-pass)
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub tiktoken
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from core.summarisation.summarizer import Summarizer

# ═══════════════════════════════════════════════════════════════════════════
# _recover_vram tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRecoverVRAM:
    """V13.40.0: Verify VRAM recovery doesn't crash and logs correctly."""

    def _make_mock_summarizer(self):
        obj = MagicMock()
        obj.log = MagicMock()
        obj.is_local = False  # V13.44.3: _recover_vram is a no-op for cloud
        obj.local_vram_recovery_delay = 0  # V13.44.3: disable delay in tests
        return obj

    def test_recover_vram_doesnt_crash_without_cuda(self):
        """_recover_vram should not crash when CUDA is unavailable."""
        obj = self._make_mock_summarizer()
        obj.is_local = True  # override for this test
        obj.local_vram_recovery_delay = 0  # use delay_sec param instead
        # Should complete without raising
        Summarizer._recover_vram(obj, context="test", delay_sec=0.01)

    def test_recover_vram_logs_recovery(self, monkeypatch):
        """V0.6.6 (review-loop B10): was ``assert True`` — a can't-fail test
        nominally guarding the V13.44.3 log path. Now pins the delegation:
        ``_recover_vram`` forwards is_local / delays / context / log_fn to
        ``core.summarisation.vram.recover_vram`` (whose real log behavior
        is separately tested in test_vram_phases.py)."""
        import core.summarisation.vram as vram_mod

        calls = []

        def _fake_recover(*, is_local, delay_sec, configured_delay, context, log_fn):
            calls.append((is_local, delay_sec, configured_delay, context, log_fn))

        monkeypatch.setattr(vram_mod, "recover_vram", _fake_recover)
        obj = self._make_mock_summarizer()
        obj.is_local = True  # V13.44.3: only runs for local
        obj.local_vram_recovery_delay = 0  # use delay_sec param instead
        Summarizer._recover_vram(obj, context="pre-gap-fill", delay_sec=0.01)
        assert calls == [(True, 0.01, 0, "pre-gap-fill", obj.log)]


# ═══════════════════════════════════════════════════════════════════════════
# _ensure_additive_sections tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsureAdditiveSections:
    """V13.40.0: Verify additive-section followup populates empty sections."""

    def _make_mock_summarizer(self, followup_response=""):
        obj = MagicMock()
        obj.log = MagicMock()
        obj.language = "en"
        obj.temperature = 1.0
        obj.request = MagicMock()
        obj.request.summarisation_max_context_tokens = 32768
        obj._call_llm_with_empty_retry = MagicMock(return_value=followup_response)
        obj._strip_thinking = MagicMock(side_effect=lambda x: x)
        return obj

    def test_skips_when_both_sections_populated(self):
        """When both sections already have content, no followup call needed."""
        obj = self._make_mock_summarizer(followup_response="should not be called")
        result = {
            "key_distinctions": "- Real distinction here.",
            "theoretical_tensions": "- Real tension here.",
        }
        Summarizer._ensure_additive_sections(obj, "Chapter 1", "source text", result)
        # Followup should NOT have been called
        obj._call_llm_with_empty_retry.assert_not_called()

    def test_populates_empty_sections_from_followup(self):
        """When sections are empty, followup call should populate them."""
        followup = """<key_distinctions>
- Ego identity vs. existential identity: inner sameness vs. social continuity.
</key_distinctions>
<theoretical_tensions>
- Debate over infantile vs. adolescent origins of identity.
</theoretical_tensions>"""
        obj = self._make_mock_summarizer(followup_response=followup)
        result = {
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        Summarizer._ensure_additive_sections(obj, "Chapter 1", "source text", result)
        # Followup should have been called
        obj._call_llm_with_empty_retry.assert_called_once()
        # Sections should be populated
        assert "ego identity" in result["key_distinctions"].lower()
        assert "infantile" in result["theoretical_tensions"].lower()

    def test_handles_empty_followup_response(self):
        """When followup returns empty, sections stay empty (no crash)."""
        obj = self._make_mock_summarizer(followup_response="")
        result = {
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        Summarizer._ensure_additive_sections(obj, "Chapter 1", "source text", result)
        # Should not crash, sections stay empty
        assert result["key_distinctions"] == ""
        assert result["theoretical_tensions"] == ""

    def test_handles_followup_exception(self):
        """When followup raises an exception, no crash."""
        obj = self._make_mock_summarizer(followup_response="valid")
        obj._call_llm_with_empty_retry = MagicMock(side_effect=Exception("Network error"))
        result = {
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        # Should not crash
        Summarizer._ensure_additive_sections(obj, "Chapter 1", "source text", result)

    def test_partial_population_preserves_existing(self):
        """When one section is populated and the other isn't, only the empty one is filled."""
        followup = """<key_distinctions>
- New distinction from followup.
</key_distinctions>
<theoretical_tensions>
- New tension from followup.
</theoretical_tensions>"""
        obj = self._make_mock_summarizer(followup_response=followup)
        result = {
            "key_distinctions": "- Existing distinction (should be preserved).",
            "theoretical_tensions": "",  # empty — should be filled
        }
        Summarizer._ensure_additive_sections(obj, "Chapter 1", "source text", result)
        # Existing distinction should be preserved (not overwritten)
        assert "Existing distinction" in result["key_distinctions"]
        # Empty tension should be filled
        assert "New tension" in result["theoretical_tensions"]


# ═══════════════════════════════════════════════════════════════════════════
# B4 threshold test
# ═══════════════════════════════════════════════════════════════════════════


class TestB4Threshold:
    """V18.2: Verify B4 threshold is configurable (default 12000)."""

    def test_b4_threshold_is_configurable(self):
        """V18.2 (audit): B4 threshold is now configurable via settings.

        Was hardcoded 8000 (V13.40.3), which triggered B4 for a 9127-token
        chapter = 6 LLM calls = 1 hour on a 27B/12GB card. Raised to 12000
        so most chapters do single-pass = 1 call = ~10 min. Users can
        lower to 8000 if coverage drops on long chapters.
        """
        import inspect

        source = inspect.getsource(Summarizer._summarize_inner)
        # V18.2: threshold is now read from settings, not hardcoded
        assert "b4_threshold_tokens" in source
        # V0.18 (Phase 5.1, steps 2-4): the B4 gate moved VERBATIM to the
        # single-pass phase method.
        source = inspect.getsource(Summarizer._phase_single_pass_primary)
        assert "tok_in > _b4_threshold" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
