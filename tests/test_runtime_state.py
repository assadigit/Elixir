"""V18.20.1.0 (Debt D3): characterization tests for the centralized runtime state.

The V18.19.2.4 SWOT (W1) diagnosed the root cause of the 5 order-dependent test
failures: the re-export pattern imports the VALUE of module-level singletons at
import time, so patches against the re-export module don't propagate to the impl
module. V18.20.1.0 (D3) fixes this by centralizing the 5 singletons into a
shared ``_runtime_state.state`` object.

These tests verify the fix: patches via the re-export module name propagate to
the impl module (and vice versa) because both reference the SAME state object.
"""

from __future__ import annotations

import sys
import types

import pytest

if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = lambda *a, **k: None
    _tk.encoding_for_model = lambda *a, **k: None
    _tk.Encoding = type("Encoding", (), {})
    sys.modules["tiktoken"] = _tk


# ═══════════════════════════════════════════════════════════════════════════
# 1. The shared state object is the SAME across re-export + impl modules
# ═══════════════════════════════════════════════════════════════════════════


class TestSharedStateObject:
    """The re-export module and impl module must reference the SAME state object."""

    def test_content_judge_shares_state(self):
        import core.summarisation.content_judge as cj_reexport
        import core.summarisation.content_judge_impl as cj_impl

        assert cj_reexport._runtime_state is cj_impl._runtime_state, (
            "content_judge re-export and content_judge_impl must share the SAME "
            "_runtime_state object (D3 fix)"
        )

    def test_text_preprocessor_shares_state(self):
        import core.summarisation.text_preprocessor as tp_reexport
        import core.summarisation.text_preprocessor_impl as tp_impl

        assert tp_reexport._runtime_state is tp_impl._runtime_state, (
            "text_preprocessor re-export and impl must share _runtime_state"
        )

    def test_llm_provider_shares_state(self):
        import core.llm.llm_provider as lp_reexport
        import core.llm.llm_provider_impl as lp_impl

        assert lp_reexport._runtime_state is lp_impl._runtime_state, (
            "llm_provider re-export and impl must share _runtime_state"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Patches via the re-export module propagate to the impl module (THE FIX)
# ═══════════════════════════════════════════════════════════════════════════


class TestPatchPropagation:
    """The D3 root-cause fix: patches via the re-export module propagate."""

    def test_content_judge_warned_embedding_disabled_propagates(self):
        import core.summarisation.content_judge as cj_reexport
        import core.summarisation.content_judge_impl as cj_impl

        cj_reexport._runtime_state.warned_embedding_disabled = True
        assert cj_impl._runtime_state.warned_embedding_disabled is True
        cj_reexport._runtime_state.reset()

    def test_content_judge_warned_semantic_fallback_propagates(self):
        import core.summarisation.content_judge as cj_reexport
        import core.summarisation.content_judge_impl as cj_impl

        cj_reexport._runtime_state.warned_semantic_fallback = True
        assert cj_impl._runtime_state.warned_semantic_fallback is True
        cj_reexport._runtime_state.reset()

    def test_text_preprocessor_spacy_nlp_propagates(self):
        import core.summarisation.text_preprocessor as tp_reexport
        import core.summarisation.text_preprocessor_impl as tp_impl

        _sentinel = object()
        tp_reexport._runtime_state.spacy_nlp = _sentinel
        assert tp_impl._runtime_state.spacy_nlp is _sentinel
        tp_reexport._runtime_state.reset()

    def test_text_preprocessor_warned_no_embed_model_propagates(self):
        import core.summarisation.text_preprocessor as tp_reexport
        import core.summarisation.text_preprocessor_impl as tp_impl

        tp_reexport._runtime_state.warned_no_embed_model = True
        assert tp_impl._runtime_state.warned_no_embed_model is True
        tp_reexport._runtime_state.reset()

    def test_llm_provider_keep_alive_cache_propagates(self):
        import core.llm.llm_provider as lp_reexport
        import core.llm.llm_provider_impl as lp_impl

        lp_reexport._runtime_state.keep_alive_cache = "45m"
        assert lp_impl._runtime_state.keep_alive_cache == "45m"
        lp_reexport._runtime_state.reset()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Patches via the impl module propagate to the re-export module (symmetric)
# ═══════════════════════════════════════════════════════════════════════════


class TestPatchPropagationReverse:
    """Symmetric: patches via the impl module propagate to the re-export."""

    def test_impl_to_reexport_propagation(self):
        import core.summarisation.content_judge as cj_reexport
        import core.summarisation.content_judge_impl as cj_impl

        cj_impl._runtime_state.warned_embedding_disabled = True
        assert cj_reexport._runtime_state.warned_embedding_disabled is True
        cj_impl._runtime_state.reset()


# ═══════════════════════════════════════════════════════════════════════════
# 4. The reset() method clears all 5 singletons
# ═══════════════════════════════════════════════════════════════════════════


class TestStateReset:
    """The reset() method restores all 5 singletons to defaults."""

    def test_reset_clears_all_singletons(self):
        from core.summarisation._runtime_state import state

        # Pollute all 5
        state.warned_embedding_disabled = True
        state.warned_semantic_fallback = True
        state.st_model = object()
        state.warned_no_embed_model = True
        state.spacy_nlp = object()
        state.spacy_lang = "en"
        state.keep_alive_cache = "45m"
        # Reset
        state.reset()
        # Verify all defaults
        assert state.warned_embedding_disabled is False
        assert state.warned_semantic_fallback is False
        assert state.st_model is None
        assert state.warned_no_embed_model is False
        assert state.spacy_nlp is None
        assert state.spacy_lang is None
        assert state.keep_alive_cache is None


# ═══════════════════════════════════════════════════════════════════════════
# 5. Autouse fixture: reset state before each test (prevents cross-test pollution)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    """Reset the shared runtime state before each test.

    This is the V18.20.1.0 (D3) fix for the order-dependent test failures:
    without this, a Summarizer construction in one test would pollute the
    singleton state for downstream tests. The fixture mirrors the pattern in
    test_embedder_optional.py (which manually reset 2 of these 5).
    """
    from core.summarisation._runtime_state import state

    state.reset()
    yield
    state.reset()
