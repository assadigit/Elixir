"""V19.1.0.0 (Phase 2e): content_judge — thin re-export layer.

All functions/classes/constants extracted to ``_impl.py``. This module
re-exports the public API for backward compatibility. V0.08 (P2 hygiene):
the wildcard re-export was replaced by an explicit import — transitive
names (``typing``/``dataclasses``/``SummaryResult``/``EmbedderUnavailable``)
leaked from the impl module are no longer re-exported.

V18.20.1.0 (D3): also re-exports ``_runtime_state`` so tests that patch via the
re-export module name (``content_judge._runtime_state.warned_X = Y``) mutate the
shared state object — fixing the 5 order-dependent test failures at the root.
"""

from __future__ import annotations

# V18.20.1.0 (D3): re-export the shared runtime state object so tests can patch
# via the re-export module name AND have the change propagate to the impl module.
# ``content_judge._runtime_state.warned_X = Y`` mutates the SAME object that
# ``content_judge_impl._runtime_state.warned_X`` reads — no more silent no-ops.
from core.summarisation._runtime_state import state as _runtime_state  # noqa: F401

# V0.08 (P2): explicit re-export of the impl module's public API
# (was: ``from content_judge_impl import *``). Intentional re-exports —
# ruff F401 suppressed per the docstring contract above.
# Explicit re-exports for underscore-prefixed names
# V18.20.3.12: noqa: F401 added — intentional re-exports consumed by tests
# (test_content_judge accesses _extract_key_claims etc. via this module);
# the safe ruff auto-fix removed them once as "unused" which broke those accesses.
from core.summarisation.content_judge_impl import (  # noqa: F401
    _CLAIM_PATTERNS,
    _SKIP_PATTERNS,
    CHUNK_SIZE_TOKENS,
    GAP_FILL_THRESHOLD,
    GROUNDED_SIM_THRESHOLD,
    MIN_COVERAGE_PCT,
    UNGROUNDED_MAX_PCT,
    ContentJudge,
    EmbeddingDisabled,
    JudgeResult,
    _chunk_text,
    _embedding_settings,
    _extract_key_claims,
    _jaccard,
    _semantic_similarity,
    _split_into_sentences,
    _warned_embedding_disabled,
    _warned_semantic_fallback,
)
