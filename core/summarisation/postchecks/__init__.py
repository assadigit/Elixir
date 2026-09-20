"""V0.18 (Phase 5.2) — the postchecks package.

``postchecks.py`` (orchestrator + facade) and ``postcheck_detectors.py``
(the 4,762-LOC detector monolith) were regrouped into this package by
detector family. The public API surface is UNCHANGED:

  - ``from core.summarisation.postchecks import <detector>`` — works (below)
  - ``from core.summarisation.postchecks import run_post_checks`` — works
    (lazily forwarded to ``orchestrator``, keeping the historical import
    surface while avoiding an import cycle: ``orchestrator`` imports
    ``post_processing``, which imports the ``postcheck_detectors`` facade,
    which imports this package's leaf family modules).

Detector families: ``shared`` / ``leakage`` / ``garble`` / ``attribution`` /
``coherence``. The legacy ``core.summarisation.postcheck_detectors`` module
remains as a compatibility facade over the same objects.
"""

from __future__ import annotations

from core.summarisation.postchecks.attribution import (  # noqa: F401
    _ATTRIB_NOUNS,
    _ATTRIB_VERB_RE,
    _ATTRIB_VERBS,
    _ATTRIBUTIVE_POSSESSIVE_RE,
    _BARE_YEAR_RE,
    _BOLD_NAME_RE,
    _BULLET_ACTIVE_PREFIX_RE,
    _BULLET_COLON_SUBJECT_RE,
    _BULLET_NAME_PREFIX_RE,
    _BULLET_POSSESSIVE_PREFIX_RE,
    _NON_NAME_CAPS,
    _SRC_ACCORDING_TO_RE,
    _SRC_ACTIVE_SUBJECT_RE,
    _SRC_POSSESSIVE_SUBJECT_RE,
    _SRC_PRONOUN_SUBJECT_RE,
    _SUMMARY_CITATION_RE,
    _YEAR_IN_PARENS_RE,
    MAX_YEAR,
    MIN_YEAR,
    _all_occurrences_parenthetical,
    _author_in_source,
    _content_overlap,
    _name_holds_any_attrib_verb,
    _name_holds_verb,
    _parse_bullet_subject,
    _resolve_pronoun_antecedent,
    _verb_stems,
    detect_attribution_subject_swap,
    detect_dropped_digit_years,
    detect_parenthetical_promotion,
    validate_years,
    verify_attribution,
    verify_bold_name_attribution,
)
from core.summarisation.postchecks.coherence import (  # noqa: F401
    _AUTHOR_RE,
    _HEDGE_RE,
    _HEDGE_WORDS,
    _INTERPRETIVE_FIRST_PERSON_RE,
    _INTERPRETIVE_LEAP_RE,
    _MISSING_CLAIM_RE,
    _PRONOUN_MAP,
    _PRONOUN_RE,
    detect_citation_coverage_gap,
    detect_exec_bullet_inconsistency,
    detect_hedge_loss,
    detect_inconsistency,
    detect_interpretive_leaps,
    detect_pronoun_mismatch,
)
from core.summarisation.postchecks.garble import (  # noqa: F401
    _CAMELCASE_MERGE_RE,
    _COMMON_ENGLISH_WORDS,
    _COMMON_SUFFIXES,
    _ENGLISH_LEXICON,
    _FRAGMENT_MERGE_RE,
    _IMPOSSIBLE_BIGRAM_RE,
    _IMPOSSIBLE_BIGRAMS,
    _LEGIT_SUFFIXES,
    _LONG_CONSONANT_CLUSTER_RE,
    _MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE,
    _MERGED_SENTENCE_RE,
    _MIN_GARBLED_WORD_LEN,
    _MISSING_SPACE_CAP_RE,
    _MISSING_SPACE_LOWER_RE,
    _STRUCTURAL_STOPWORDS,
    _VERB_ENDINGS,
    _VERB_STOPWORDS,
    _VOWEL,
    _VOWEL_LESS_LONG_RE,
    _common_word_stem_in_stoplist,
    _edit_distance_one_neighbors,
    _is_legitimate_inflection,
    _is_legitimate_inflection_pair,
    _load_english_lexicon,
    _paragraph_corroborated,
    detect_dropped_letter_garble,
    detect_extra_spaces,
    detect_garbled_tokens,
    detect_grammatical_incoherence,
    detect_missing_spaces,
    detect_word_fragment_merge,
)
from core.summarisation.postchecks.leakage import (  # noqa: F401
    _COT_NARRATIVE_MARKERS,
    _COT_NARRATIVE_RE,
    _PROMPT_LEAKAGE_PATTERNS,
    _PROMPT_LEAKAGE_RE,
    detect_cot_narrative,
    detect_prompt_leakage,
)
from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    PostCheckReport,
    _is_subsequence,
    _snippet,
)


def __getattr__(name: str):
    # PEP 562 — lazy forward to the orchestrator (run_post_checks etc.).
    # Lazy loading is what breaks the import cycle described in the module
    # docstring: this __init__ only eagerly imports the leaf family modules.
    # NOTE: importlib.import_module (NOT ``from . import orchestrator``) —
    # the from-form looks the name up on this package, which would re-enter
    # this very __getattr__ and recurse forever.
    import importlib

    _m = importlib.import_module("core.summarisation.postchecks.orchestrator")
    try:
        return getattr(_m, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__() -> list[str]:
    return sorted(set(globals()) | {"run_post_checks", "orchestrator"})


__all__ = [
    "Issue",
    "MAX_YEAR",
    "MIN_YEAR",
    "PostCheckReport",
    "_ATTRIBUTIVE_POSSESSIVE_RE",
    "_ATTRIB_NOUNS",
    "_ATTRIB_VERBS",
    "_ATTRIB_VERB_RE",
    "_AUTHOR_RE",
    "_BARE_YEAR_RE",
    "_BOLD_NAME_RE",
    "_BULLET_ACTIVE_PREFIX_RE",
    "_BULLET_COLON_SUBJECT_RE",
    "_BULLET_NAME_PREFIX_RE",
    "_BULLET_POSSESSIVE_PREFIX_RE",
    "_CAMELCASE_MERGE_RE",
    "_COMMON_ENGLISH_WORDS",
    "_COMMON_SUFFIXES",
    "_COT_NARRATIVE_MARKERS",
    "_COT_NARRATIVE_RE",
    "_ENGLISH_LEXICON",
    "_FRAGMENT_MERGE_RE",
    "_HEDGE_RE",
    "_HEDGE_WORDS",
    "_IMPOSSIBLE_BIGRAMS",
    "_IMPOSSIBLE_BIGRAM_RE",
    "_INTERPRETIVE_FIRST_PERSON_RE",
    "_INTERPRETIVE_LEAP_RE",
    "_LEGIT_SUFFIXES",
    "_LONG_CONSONANT_CLUSTER_RE",
    "_MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE",
    "_MERGED_SENTENCE_RE",
    "_MIN_GARBLED_WORD_LEN",
    "_MISSING_CLAIM_RE",
    "_MISSING_SPACE_CAP_RE",
    "_MISSING_SPACE_LOWER_RE",
    "_NON_NAME_CAPS",
    "_PROMPT_LEAKAGE_PATTERNS",
    "_PROMPT_LEAKAGE_RE",
    "_PRONOUN_MAP",
    "_PRONOUN_RE",
    "_SRC_ACCORDING_TO_RE",
    "_SRC_ACTIVE_SUBJECT_RE",
    "_SRC_POSSESSIVE_SUBJECT_RE",
    "_SRC_PRONOUN_SUBJECT_RE",
    "_STRUCTURAL_STOPWORDS",
    "_SUMMARY_CITATION_RE",
    "_VERB_ENDINGS",
    "_VERB_STOPWORDS",
    "_VOWEL",
    "_VOWEL_LESS_LONG_RE",
    "_YEAR_IN_PARENS_RE",
    "_all_occurrences_parenthetical",
    "_author_in_source",
    "_common_word_stem_in_stoplist",
    "_content_overlap",
    "_edit_distance_one_neighbors",
    "_is_legitimate_inflection",
    "_is_legitimate_inflection_pair",
    "_is_subsequence",
    "_load_english_lexicon",
    "_name_holds_any_attrib_verb",
    "_name_holds_verb",
    "_paragraph_corroborated",
    "_parse_bullet_subject",
    "_resolve_pronoun_antecedent",
    "_snippet",
    "_verb_stems",
    "detect_attribution_subject_swap",
    "detect_citation_coverage_gap",
    "detect_cot_narrative",
    "detect_dropped_digit_years",
    "detect_dropped_letter_garble",
    "detect_exec_bullet_inconsistency",
    "detect_extra_spaces",
    "detect_garbled_tokens",
    "detect_grammatical_incoherence",
    "detect_hedge_loss",
    "detect_inconsistency",
    "detect_interpretive_leaps",
    "detect_missing_spaces",
    "detect_parenthetical_promotion",
    "detect_prompt_leakage",
    "detect_pronoun_mismatch",
    "detect_word_fragment_merge",
    "validate_years",
    "verify_attribution",
    "verify_bold_name_attribution",
    "run_post_checks",
]
