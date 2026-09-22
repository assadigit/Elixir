"""V0.4.19 — the multi-author concept conflation detector.

``detect_multi_author_conflation`` moved VERBATIM from ``garble.py``
during the V0.4.19 de-monolithization.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.shared import Issue

# ─────────────────────────────────────────────────────────────────────────────
# V0.4.11 (audit item #8): multi-author concept conflation detector.
#
# The V0.4.1 Jones/Waelder "God complex" conflation: the summary credited
# BOTH Jones and Waelder with the "God complex" concept, but the source
# attributes it only to Jones. The existing attribution veto catches
# single-author misattribution but not "2+ authors credited with a single
# named concept that the source attributes to only 1 of them."
#
# Content-agnostic: the detector finds quoted phrases attributed to 2+
# authors in the same sentence, then checks if the source attributes that
# phrase to only 1 of them. If so, it flags the conflation.
# ─────────────────────────────────────────────────────────────────────────────


def detect_multi_author_conflation(
    text: str,
    field_label: str,
    source_text: str = "",
    source_authors: set | None = None,
) -> tuple[str, list[Issue]]:
    """V0.4.11 (audit item #8): detect when 2+ authors are credited with
    a single named concept that the source attributes to only 1 of them.

    Pattern: a sentence in the summary contains a quoted phrase (e.g.,
    "God complex") AND mentions 2+ author names from source_authors.
    The source is checked: does the quoted phrase appear near ONLY ONE
    of those authors? If so, the other author(s) are conflated.

    Flag-only (no auto-repair — the correct reconstruction is ambiguous).

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the source chapter text.
        source_authors: set of author surnames from the runtime analysis.

    Returns:
        ``(text, issues)``. Text is UNCHANGED.
    """
    issues: list[Issue] = []
    if not text or not source_text or not source_authors:
        return text, issues
    try:
        # Find sentences with a quoted phrase + 2+ author names.
        # A "quoted phrase" is text between " or " or " (smart quotes).
        _quote_re = re.compile(r'["\u201c]([^"\u201c\u201d]{3,60})["\u201d]')
        for sent_match in re.finditer(r"[^.!?]*[.!?]", text):
            sent = sent_match.group(0)
            sent_lower = sent.lower()
            # Find all author names mentioned in this sentence.
            mentioned = set()
            for author in source_authors:
                if len(author) < 3:
                    continue
                if author.lower() in sent_lower:
                    mentioned.add(author)
            if len(mentioned) < 2:
                continue  # need 2+ authors for a conflation
            # Find quoted phrases in this sentence.
            quotes = _quote_re.findall(sent)
            if not quotes:
                continue
            # For each quoted phrase, check which author(s) the source
            # attributes it to.
            for phrase in quotes:
                phrase_lower = phrase.lower()
                # Find the phrase in the source text.
                src_idx = source_text.lower().find(phrase_lower)
                if src_idx < 0:
                    continue  # phrase not in source — skip
                # Check which mentioned authors appear within 200 chars
                # of the phrase in the source.
                src_context = source_text[max(0, src_idx - 200) : src_idx + 200].lower()
                source_attributed = set()
                for author in mentioned:
                    if author.lower() in src_context:
                        source_attributed.add(author)
                # If the source attributes the phrase to FEWER authors
                # than the summary mentions, it's a conflation.
                conflated = mentioned - source_attributed
                if conflated:
                    snippet_start = max(0, sent_match.start() - 25)
                    snippet_end = min(len(text), sent_match.end() + 25)
                    issues.append(
                        Issue(
                            detector="multi_author_conflation",
                            severity="flag",
                            field=field_label,
                            snippet=text[snippet_start:snippet_end],
                            detail=(
                                f"possible multi-author conflation: the phrase "
                                f'"{phrase}" is attributed to {sorted(mentioned)} '
                                f"in the summary, but the source attributes it only "
                                f"to {sorted(source_attributed) or '[none found nearby]'}. "
                                f"Conflated author(s): {sorted(conflated)}."
                            ),
                        )
                    )
    except Exception as e:  # pragma: no cover
        from core.summarisation.postchecks.shared import logger

        logger.warning(
            "multi-author conflation detector crashed (non-fatal): %s: %s", type(e).__name__, e
        )
    return text, issues
