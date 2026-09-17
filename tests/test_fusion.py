"""V13.36.0: Regression tests for the Hybrid Fusion (Local + Cloud) feature.

Tests verify:
1. Fusion settings keys exist with correct defaults
2. _call_cloud() falls back to local when fusion is disabled
3. _call_cloud() routes to cloud provider when fusion is enabled
4. _b3_cloud_judge() picks the cloud-selected sample
5. _call_cloud() graceful fallback on empty/exception

These tests use mocks — no real LLM calls are made.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


# ── Stub optional deps (same pattern as test_integration_pipeline.py) ──────
def _stub_optional_deps():
    """Stub langextract + rapidfuzz + tiktoken so imports don't crash."""
    if "langextract" not in sys.modules:
        le = types.ModuleType("langextract")
        le.data = MagicMock()
        sys.modules["langextract"] = le
    if "langextract.factory" not in sys.modules:
        factory = types.ModuleType("langextract.factory")
        factory.ModelConfig = MagicMock()
        sys.modules["langextract.factory"] = factory
    if "rapidfuzz" not in sys.modules:
        rf = types.ModuleType("rapidfuzz")
        rf.fuzz = MagicMock()
        rf.fuzz.token_set_ratio = lambda a, b: 80.0
        rf.process = MagicMock()
        rf.process.extract = MagicMock(return_value=[])
        sys.modules["rapidfuzz"] = rf
    # tiktoken — not installed in the test env, stub it
    if "tiktoken" not in sys.modules:
        tk = types.ModuleType("tiktoken")
        tk.get_encoding = MagicMock(return_value=MagicMock())
        tk.encoding_for_model = MagicMock(return_value=MagicMock())
        tk.Encoding = MagicMock  # used as a type hint at module level
        sys.modules["tiktoken"] = tk


_stub_optional_deps()


# ═══════════════════════════════════════════════════════════════════════════
# Settings tests — verify fusion keys exist with correct defaults
# ═══════════════════════════════════════════════════════════════════════════

class TestFusionSettings:
    """V13.36.0: Verify the fusion settings keys exist with correct defaults."""

    def test_fusion_defaults_exist(self):
        """All fusion_* keys should exist in the settings defaults."""
        from utils.settings import Settings
        s = Settings()
        # Read each fusion key — should return the default, not raise
        assert s.get("summarisation.fusion_enabled", None) is False
        assert s.get("summarisation.fusion_cloud_provider", None) == "openai_compat"
        assert s.get("summarisation.fusion_cloud_model", None) == "google/gemini-2.5-flash-preview:free"
        assert s.get("summarisation.fusion_cloud_max_tokens", None) == 4096
        assert s.get("summarisation.fusion_cloud_temperature", None) == 0.2
        assert s.get("summarisation.fusion_use_for_self_review", None) is True
        assert s.get("summarisation.fusion_use_for_grounding", None) is True
        assert s.get("summarisation.fusion_use_for_b3_judge", None) is True
        assert s.get("summarisation.fusion_use_for_gap_fill", None) is False

    def test_fusion_cloud_api_key_defaults_to_empty(self):
        """The fusion_cloud_api_key should default to empty (reuses summarisation.api_key)."""
        from utils.settings import Settings
        s = Settings()
        assert s.get("summarisation.fusion_cloud_api_key", None) == ""

    def test_fusion_cloud_base_url_defaults_to_empty(self):
        """The fusion_cloud_base_url should default to empty (reuses summarisation.api_base_url)."""
        from utils.settings import Settings
        s = Settings()
        assert s.get("summarisation.fusion_cloud_base_url", None) == ""


# ═══════════════════════════════════════════════════════════════════════════
# _call_cloud() routing tests — test the method logic directly
# ═══════════════════════════════════════════════════════════════════════════

class TestCallCloudRouting:
    """V13.36.0: Verify _call_cloud() routes correctly based on fusion_enabled.

    We test the method by calling it as an unbound function with a mock `self`,
    avoiding the need to construct a full Summarizer instance (which requires
    a real ConversionRequest + many settings).
    """

    def _get_call_cloud_method(self):
        """Import the Summarizer class and return the _call_cloud method."""
        try:
            from core.summarisation.summarizer import Summarizer
            return Summarizer._call_cloud
        except ImportError as e:
            pytest.skip(f"Cannot import Summarizer: {e}")

    def _make_mock_self(self, fusion_enabled=False):
        """Create a mock object with the attributes _call_cloud needs."""
        obj = MagicMock()
        obj.fusion_enabled = fusion_enabled
        obj.fusion_cloud_provider = "openai_compat"
        obj.fusion_cloud_model = "google/gemini-2.5-flash-preview:free"
        obj.fusion_cloud_api_key = "sk-test"
        obj.fusion_cloud_base_url = "https://openrouter.ai/api/v1"
        obj.fusion_cloud_max_tokens = 4096
        obj.fusion_cloud_temperature = 0.2
        obj.claude_model = "claude-3-5-sonnet"
        obj.log = MagicMock()
        # _call_cloud calls _call_via_llm_provider and _call_llm
        obj._call_via_llm_provider = MagicMock(return_value="cloud response")
        obj._call_llm = MagicMock(return_value="local response")
        return obj

    def test_call_cloud_falls_back_to_local_when_disabled(self):
        """When fusion_enabled is False, _call_cloud should call _call_llm (local)."""
        call_cloud = self._get_call_cloud_method()
        obj = self._make_mock_self(fusion_enabled=False)
        result = call_cloud(obj, "test prompt")
        # Should NOT have called _call_via_llm_provider (cloud path)
        obj._call_via_llm_provider.assert_not_called()
        # SHOULD have called _call_llm (local fallback)
        obj._call_llm.assert_called_once()
        assert result == "local response"

    def test_call_cloud_routes_to_cloud_when_enabled(self):
        """When fusion_enabled is True, _call_cloud should call _call_via_llm_provider (cloud)."""
        call_cloud = self._get_call_cloud_method()
        obj = self._make_mock_self(fusion_enabled=True)
        result = call_cloud(obj, "test prompt")
        # Should have called _call_via_llm_provider (cloud path)
        obj._call_via_llm_provider.assert_called_once()
        # Should NOT have called _call_llm (local fallback) since cloud succeeded
        obj._call_llm.assert_not_called()
        assert result == "cloud response"

    def test_call_cloud_falls_back_on_empty_cloud_response(self):
        """When cloud returns empty, _call_cloud should fall back to local."""
        call_cloud = self._get_call_cloud_method()
        obj = self._make_mock_self(fusion_enabled=True)
        obj._call_via_llm_provider = MagicMock(return_value="")  # empty response
        result = call_cloud(obj, "test prompt")
        # Should have tried cloud first
        obj._call_via_llm_provider.assert_called_once()
        # Then fallen back to local
        obj._call_llm.assert_called_once()
        assert result == "local response"

    def test_call_cloud_falls_back_on_exception(self):
        """When cloud raises an exception, _call_cloud should fall back to local."""
        call_cloud = self._get_call_cloud_method()
        obj = self._make_mock_self(fusion_enabled=True)
        obj._call_via_llm_provider = MagicMock(side_effect=Exception("Network error"))
        result = call_cloud(obj, "test prompt")
        # Should have tried cloud first
        obj._call_via_llm_provider.assert_called_once()
        # Then fallen back to local
        obj._call_llm.assert_called_once()
        assert result == "local response"


# ═══════════════════════════════════════════════════════════════════════════
# B3 cloud judge tests
# ═══════════════════════════════════════════════════════════════════════════

class TestB3CloudJudge:
    """V13.36.0: Verify _b3_cloud_judge() picks the cloud-selected sample."""

    def _get_b3_judge_method(self):
        """Import the Summarizer class and return the _b3_cloud_judge method."""
        try:
            from core.summarisation.summarizer import Summarizer
            return Summarizer._b3_cloud_judge
        except ImportError as e:
            pytest.skip(f"Cannot import Summarizer: {e}")

    def _make_mock_self(self, cloud_response="1"):
        """Create a mock object with the attributes _b3_cloud_judge needs."""
        obj = MagicMock()
        obj.fusion_cloud_temperature = 0.2
        obj.fusion_cloud_model = "google/gemini-2.5-flash-preview:free"
        obj.log = MagicMock()
        obj._call_cloud = MagicMock(return_value=cloud_response)
        obj._compute_coverage = MagicMock(return_value=0.5)
        return obj

    def test_b3_cloud_judge_picks_correct_sample(self):
        """When the cloud model picks sample #2, _b3_cloud_judge should return sample #2."""
        b3_judge = self._get_b3_judge_method()
        obj = self._make_mock_self(cloud_response="2")
        samples = [
            {"executive_summary": "Summary 1", "thorough_summary": "Thorough 1"},
            {"executive_summary": "Summary 2", "thorough_summary": "Thorough 2"},
            {"executive_summary": "Summary 3", "thorough_summary": "Thorough 3"},
        ]
        best_exec, best_thorough = b3_judge(obj, samples, "source text", "Chapter 1")
        # Cloud said "2" for both — so both should be sample index 1 (0-indexed)
        assert best_exec["executive_summary"] == "Summary 2"
        assert best_thorough["thorough_summary"] == "Thorough 2"

    def test_b3_cloud_judge_falls_back_on_invalid_response(self):
        """When cloud returns garbage, _b3_cloud_judge should fall back to coverage."""
        b3_judge = self._get_b3_judge_method()
        obj = self._make_mock_self(cloud_response="invalid garbage")
        samples = [
            {"executive_summary": "Summary 1", "thorough_summary": "Thorough 1"},
            {"executive_summary": "Summary 2", "thorough_summary": "Thorough 2"},
        ]
        best_exec, best_thorough = b3_judge(obj, samples, "source text", "Chapter 1")
        # Should fall back to coverage-based picking (mocked to return 0.5 for all)
        # so it picks the first sample (max returns the first max on ties)
        assert best_exec is not None
        assert best_thorough is not None

    def test_b3_cloud_judge_handles_none_response(self):
        """When cloud returns None, _b3_cloud_judge should fall back gracefully."""
        b3_judge = self._get_b3_judge_method()
        obj = self._make_mock_self(cloud_response=None)
        samples = [
            {"executive_summary": "Summary 1", "thorough_summary": "Thorough 1"},
            {"executive_summary": "Summary 2", "thorough_summary": "Thorough 2"},
        ]
        # Should not raise — should fall back to coverage
        best_exec, best_thorough = b3_judge(obj, samples, "source text", "Chapter 1")
        assert best_exec is not None
        assert best_thorough is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
