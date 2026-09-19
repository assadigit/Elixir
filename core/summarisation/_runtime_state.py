"""V18.20.1.0 (Debt D3): Centralized runtime state for the 5 module-level singletons.

The V18.19.2.4 audit (SWOT W1) diagnosed the root cause of the 5 order-dependent
test failures: the re-export pattern (e.g. ``content_judge.py`` does
``from content_judge_impl import _warned_X``) imports the VALUE at import time.
Code in the impl module reads ``_warned_X`` as a module-global lookup against
``content_judge_impl._warned_X``. Consequence:
``monkeypatch.setattr("core.summarisation.content_judge._warned_X", True)``
rebinds the attribute on the RE-EXPORT module only — the impl module still sees
``False``. Tests that patch via the re-export name silently no-op; tests that
pollute the impl-module global (by constructing a Summarizer) leak into downstream
tests.

This module fixes the root cause: all 5 singletons live as attributes of a SINGLE
``_State`` instance. Both the re-export modules AND the impl modules import the
SAME ``state`` object. A patch against either
``core.summarisation._runtime_state.state.warned_X`` OR (via the re-export
shim) ``content_judge._state.warned_X`` mutates the shared object — all readers
see the new value. No more silent no-op patches; no more cross-test pollution.

The 5 singletons:
  - content_judge_impl: _warned_embedding_disabled, _warned_semantic_fallback, _st_model
  - text_preprocessor_impl: _warned_no_embed_model, _SPACY_NLP
  - llm_provider_impl: _keep_alive_cache

Backward compatibility: the impl modules keep their module-level names (e.g.
``content_judge_impl._warned_embedding_disabled``) as PROPERTY PROXIES that
read/write ``state.warned_embedding_disabled``. Existing code that does
``global _warned_X; _warned_X = True`` continues to work — the ``global``
statement now rebinds the proxy descriptor... actually no. The cleaner approach:
replace the ``global X; X = Y`` pattern with ``state.X = Y`` in the impl modules.
The module-level ``_warned_X = False`` lines become
``_warned_X = state.warned_X  # proxy for backward compat`` — but those are
value-copies at import, which reintroduces the bug. So the impl modules MUST
read/write ``state.X`` directly. This module provides the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _State:
    """Centralized mutable runtime state shared across all impl modules.

    All attributes default to the pre-V18.20.1.0 values (False / None) so
    behavior is identical unless a caller mutates them. Tests reset via
    ``reset()`` in an autouse fixture (see tests/test_runtime_state.py).
    """

    # content_judge_impl singletons
    warned_embedding_disabled: bool = False
    warned_semantic_fallback: bool = False
    st_model: Any = None  # the sentence_transformers model (lazy-loaded)

    # text_preprocessor_impl singletons
    warned_no_embed_model: bool = False
    spacy_nlp: Any = None  # the spaCy NLP pipeline (lazy-loaded)
    spacy_lang: str | None = None  # which language is currently loaded

    # llm_provider_impl singleton
    keep_alive_cache: str | None = None  # the Ollama keep_alive setting

    def reset(self) -> None:
        """Reset all singletons to their defaults (pre-construction state).

        Called by the autouse test fixture in tests/test_runtime_state.py
        to prevent cross-test pollution. Mirrors the pattern in
        test_embedder_optional.py (which manually reset 2 of these 5).
        """
        self.warned_embedding_disabled = False
        self.warned_semantic_fallback = False
        self.st_model = None
        self.warned_no_embed_model = False
        self.spacy_nlp = None
        self.spacy_lang = None
        self.keep_alive_cache = None


# The single shared instance. All impl + re-export modules import THIS object.
state = _State()
