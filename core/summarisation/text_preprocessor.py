"""V19.0.0 (Phase 2d): Text preprocessor — thin re-export layer.

V19.0.0 (Phase 2d): All 50 functions + constants + classes extracted to
``text_preprocessor_impl.py``. This module re-exports everything for
backward compatibility — all existing imports
``from core.summarisation.text_preprocessor import X`` continue to work
unchanged.

The module-level mutable state (``_SPACY_NLP``, ``_warned_no_embed_model``)
is also re-exported — patches on ``text_preprocessor._SPACY_NLP`` etc.
will work because they point to the same object.
"""
from __future__ import annotations

# Re-export everything from the implementation module
from core.summarisation.text_preprocessor_impl import *  # noqa: F401, F403

# Explicit re-exports for underscore-prefixed names (not exported by *)
# V18.20.3.12: noqa: F401 added — intentional re-exports (docstring contract:
# "all existing imports ... continue to work unchanged"); the safe ruff
# auto-fix removed them once as "unused" which broke that contract.
# Also re-export _is_valid_concept, _tokenize, _load_spacy_model,
# _bullet_similarity, _get_embed_model, _extract_proper_noun_theorists,
# _normalize_heading, _extract_section_headings, _extract_conclusion_lists,
# _extract_position_weighted_concepts, _llm_assisted_concept_extraction,
# _filter_concepts_by_source (all underscore-prefixed functions)
from core.summarisation.text_preprocessor_impl import (  # noqa: F401  # noqa: F401
    _ACADEMIC_TERM_PATTERNS,
    _AUTHOR_YEAR_PATTERN,
    _CALLOUT_PATTERN,
    _CALLOUT_PREFIX_PATTERN,
    _COMMON_500,
    _COMMON_WORDS,
    _CONCEPT_NOUN_PATTERN,
    _CONCEPT_STOPWORDS,
    _CORE_INDICATORS,
    _DEFINITION_VERB_PATTERN,
    _DISCOURSE_MARKERS,
    _DOMAIN_TERMS,
    _HEADING_PATTERN,
    _HYPHEN_PATTERN,
    _KEYWORD_STOPWORDS,
    _LOCATION_PATTERN,
    _MAX_JOINED_WORD_LEN,
    _NER_EXCLUDE,
    _NUMBER_PATTERN,
    _ORG_PATTERN,
    _PAGE_MARKER,
    _PERSON_PATTERN,
    _QUOTE_PATTERN,
    _QUOTED_TERM_PATTERN,
    _SENTENCE_END,
    _SENTENCE_SPLIT,
    _SPACY_LANG,
    _SPACY_NLP,
    _SUPPORTING_INDICATORS,
    _bullet_similarity,
    _extract_conclusion_lists,
    _extract_position_weighted_concepts,
    _extract_proper_noun_theorists,
    _extract_section_headings,
    _filter_concepts_by_source,
    _get_embed_model,
    _is_valid_concept,
    _llm_assisted_concept_extraction,
    _load_spacy_model,
    _normalize_heading,
    _tokenize,
    _warned_no_embed_model,
)

# Try to re-export bracket citation patterns (may not exist)
try:
    from core.summarisation.text_preprocessor_impl import (
        _BRACKET_CITATION_PATTERN,
        _NUMERICAL_CITATION_PATTERN,
    )
except ImportError:
    pass

# V18.20.1.0 (D3): re-export the shared runtime state object so tests can patch
# via the re-export module name AND have the change propagate to the impl module.
# ``text_preprocessor._runtime_state.spacy_nlp = Y`` mutates the SAME object that
# ``text_preprocessor_impl._runtime_state.spacy_nlp`` reads — no more silent no-ops.
from core.summarisation._runtime_state import state as _runtime_state  # noqa: F401
