"""V0.4.19 — the garble detector family package (de-monolithization).

``garble.py`` (3,084 lines — the largest module in the repo) was split into
focused submodules during the V0.4.19 de-monolithization. Every function and
constant moved VERBATIM (byte-identical bodies); this facade preserves the
historical ``core.summarisation.postchecks.garble`` import surface exactly
— ``from core.summarisation.postchecks.garble import <name>`` keeps working
for every previously importable name (constants, helpers, and detectors).

History: the detectors were first regrouped into the ``postchecks/`` package
from ``postcheck_detectors.py`` in V0.18 (Phase 5.2); this V0.4.19 split takes
the flat ``garble.py`` one level further:

  - ``lexicon``          — shared regex/lexicon constants + morphology helpers
                           (incl. the lazy ``_ENGLISH_LEXICON`` singleton)
  - ``token_detectors``  — garbled-token / missing-space / grammar /
                           extra-space / fragment-merge detectors
  - ``dropped_letter``   — the dropped-letter garble detector (flag + guarded
                           auto-repair)
  - ``author_garbles``   — author-surname garble cross-check + repair
  - ``quote_repair``     — stray-quote repair v0.20.5/v2 + D3 LLM repair
  - ``fusion``           — sentence-boundary fusion detector
  - ``conflation``       — multi-author concept conflation detector
  - ``page_refs``        — KD/TT page-reference injector
"""

from __future__ import annotations

from core.summarisation.postchecks.garble.author_garbles import (  # noqa: F401
    _AUTHOR_YEAR_RE,
    detect_and_repair_author_garbles,
)
from core.summarisation.postchecks.garble.conflation import (  # noqa: F401
    detect_multi_author_conflation,
)
from core.summarisation.postchecks.garble.dropped_letter import (  # noqa: F401
    detect_dropped_letter_garble,
)
from core.summarisation.postchecks.garble.fusion import (  # noqa: F401
    _FUSION_LEGIT_COMPOUNDS,
    _FUSION_LEGIT_SUFFIXES,
    _FUSION_MAX_SUFFIX,
    _FUSION_MIN_PREFIX,
    _FUSION_MIN_SUFFIX,
    _FUSION_MIN_WORD_LEN,
    _is_legit_fusion_suffix,
    detect_sentence_fusion,
)

# V0.4.39 (Option A): LLM semantic repair for garbles (mirrors the D3 pattern).
from core.summarisation.postchecks.garble.garble_repair import (  # noqa: F401
    repair_garbles_via_llm,
)
from core.summarisation.postchecks.garble.lexicon import (  # noqa: F401
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
)
from core.summarisation.postchecks.garble.page_refs import (  # noqa: F401
    inject_page_refs,
)
from core.summarisation.postchecks.garble.quote_repair import (  # noqa: F401
    _D3_REPAIR_PROMPT,
    _V2_CLOSER_LEFT_EXTRA,
    _V2_CLOSER_RIGHT_CHARS,
    _V2_DEFAULT_SPAN_THRESHOLD,
    _V2_OPENER_LEFT_CHARS,
    _V2_OPENER_RIGHT_EXTRA,
    _V2_PUNCT_FOR_CLOSER,
    _v2_find_closer_insert_pos,
    _v2_looks_like_closer,
    _v2_looks_like_opener,
    _v2_repair_line,
    _v2_text_quote_positions,
    repair_d3_quotes_via_llm,
    repair_stray_quotes,
    repair_stray_quotes_v2,
)
from core.summarisation.postchecks.garble.token_detectors import (  # noqa: F401
    detect_extra_spaces,
    detect_garbled_tokens,
    detect_grammatical_incoherence,
    detect_missing_spaces,
    detect_word_fragment_merge,
)
from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    _snippet,
)
