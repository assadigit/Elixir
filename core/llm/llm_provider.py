"""V19.1.0.0 (Phase 2e): llm_provider — thin re-export layer.

All functions/classes/constants extracted to ``_impl.py``. This module
re-exports everything for backward compatibility.

V18.20.1.0 (D3): also re-exports ``_runtime_state`` so tests that patch via the
re-export module name (``llm_provider._runtime_state.keep_alive_cache = Y``)
mutate the shared state object — fixing the order-dependent test failures.

V18.20.1.1 (hotfix): the 3 provider classes are now lazy-loaded in
llm_provider_impl via __getattr__. ``import *`` doesn't pick them up, so they
need explicit imports here. At this point llm_provider_impl is fully loaded,
so the lazy __getattr__ triggers the provider module import safely (no
circular deadlock).
"""
from __future__ import annotations

from core.llm.llm_provider_impl import *  # noqa: F401, F403

# Explicit re-exports for underscore-prefixed names
# V18.20.1.1 (hotfix): explicit re-exports for the 3 provider classes.
# These are lazy in llm_provider_impl (via __getattr__ to break a circular
# import), so ``import *`` doesn't pick them up. Importing them here triggers
# the lazy load — safe because llm_provider_impl is fully loaded by the time
# this module loads.
from core.llm.llm_provider_impl import (  # noqa: F401
    ClaudeProvider,
    LlamaCppProvider,
    OllamaProvider,
    OpenAICompatProvider,
    _get_keep_alive,
    _keep_alive_cache,
    create_provider,
)

# V18.20.1.0 (D3): re-export the shared runtime state object.
from core.summarisation._runtime_state import state as _runtime_state  # noqa: F401
