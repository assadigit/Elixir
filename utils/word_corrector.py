# utils/word_corrector.py
#
# V18.15.3.2: ALL hand-curated word lists DELETED. No _FALLBACK_WORDS, no
# wordfreq import, no external word frequency database. The reversed-text
# detection feature is now a NO-OP (returns text unchanged) because it
# required a word frequency database to detect reversed words. Source-grounded
# validation in postchecks.py replaces all word-list-based validation.
#
# This module is kept for import-compatibility (core/postprocess/cleaner.py
# imports correct_reversed_paragraph). The function is a no-op.

import logging

logger = logging.getLogger(__name__)


def correct_reversed_paragraph(paragraph: str) -> str:
    """V18.15.3.2: NO-OP. Reversed-text detection required a word frequency
    database (wordfreq or _FALLBACK_WORDS), which is a hand-curated/external
    word list — not allowed. The function is kept for import-compatibility
    (cleaner.py imports it) but returns text unchanged.

    If reversed-text detection is needed in the future, it should use
    source-grounded validation (check if the reversed text appears in the
    source) rather than an external word list.
    """
    return paragraph
