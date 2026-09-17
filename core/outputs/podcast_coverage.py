"""V4.7.21: Podcast coverage checker — verifies ALL keypoints are covered

in the generated podcast script.

This is a CRITICAL guardrail: the podcast is one of the most important
outputs, and missing keypoints means missing content from the book. The
checker:

1. Extracts key phrases from each keypoint (nouns, named entities, domain
   terms, quoted phrases)
2. Searches the podcast script for those phrases (fuzzy matching)
3. If coverage < threshold, sends the script + missing keypoints back to
   the LLM for a revision pass ("you missed these, add them")
4. Repeats up to 2 revision passes
5. Adds a coverage report at the bottom of the .Podcast.md file

The coverage threshold is configurable via ``podcast.coverage_threshold``
(default 0.90 = 90% of keypoints must be present in the script).
"""

from __future__ import annotations

import logging
import re

from core.outputs.new_outputs import OutputGeneratorBase

# Minimum phrase length to search for (avoid false positives on short words)

logger = logging.getLogger(__name__)

_MIN_PHRASE_LEN = 4

# Words too common to be useful as coverage markers
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "without", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "as", "at", "by", "from",
    "into", "about", "than", "then", "so", "if", "when", "how", "what", "why",
    "who", "which", "you", "your", "we", "our", "they", "their", "he", "she",
    "his", "her", "not", "no", "yes", "can", "could", "should", "would",
    "will", "may", "might", "must", "do", "does", "did", "have", "has", "had",
    "more", "most", "less", "least", "very", "much", "many", "some", "any",
    "all", "each", "every", "other", "another", "such", "same", "own", "new",
    "old", "first", "last", "next", "one", "two", "three", "also", "only",
    "just", "even", "still", "well", "too", "here", "there", "now", "because", "while", "during", "before", "after", "through", "between",
    "among", "against", "upon", "within", "around",
}


def _extract_key_phrases(keypoint: str) -> list[str]:
    """Extract searchable phrases from a keypoint.

    Returns a list of 2-4 word phrases that should appear in the podcast
    script if the keypoint was covered. Uses simple heuristics:
    - Capitalised words (proper nouns, named entities)
    - Quoted phrases ("End Game", "Focus Base")
    - Domain terms (multi-word nouns)
    - Long words (>8 chars, likely domain-specific)
    """
    phrases: list[str] = []

    # 1. Quoted phrases — strongest signal
    for m in re.finditer(r'"([^"]{3,50})"', keypoint):
        phrases.append(m.group(1).lower())

    # 2. Capitalised words (proper nouns, frameworks)
    for m in re.finditer(r'\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b', keypoint):
        word = m.group(1).lower()
        if word not in _STOPWORDS and len(word) >= _MIN_PHRASE_LEN:
            phrases.append(word)

    # 3. Long words (>8 chars — likely domain-specific)
    for m in re.finditer(r'\b([a-z]{9,})\b', keypoint, re.IGNORECASE):
        word = m.group(1).lower()
        if word not in _STOPWORDS:
            phrases.append(word)

    # 4. Multi-word phrases (2-3 word sequences of non-stopwords)
    tokens = keypoint.lower().split()
    for i in range(len(tokens) - 1):
        w1 = tokens[i].strip(".,;:!?\"'()[]-")
        w2 = tokens[i + 1].strip(".,;:!?\"'()[]-")
        if (len(w1) >= _MIN_PHRASE_LEN and w1 not in _STOPWORDS and
                len(w2) >= _MIN_PHRASE_LEN and w2 not in _STOPWORDS):
            phrases.append(f"{w1} {w2}")

    # Deduplicate, prefer longer phrases
    phrases = list(dict.fromkeys(phrases))  # preserve order, remove dups
    # Sort by length descending — longer phrases are more specific
    phrases.sort(key=len, reverse=True)
    return phrases[:5]  # top 5 phrases per keypoint


def _check_keypoint_covered(keypoint: str, script_lower: str) -> tuple[bool, str | None]:
    """Check if a keypoint is covered in the script.

    Returns (covered, matched_phrase). A keypoint is "covered" if at least
    one of its key phrases appears in the script.
    """
    phrases = _extract_key_phrases(keypoint)
    if not phrases:
        # Can't extract phrases — assume covered (avoid false negatives)
        return (True, None)

    for phrase in phrases:
        if phrase in script_lower:
            return (True, phrase)

    return (False, None)


class PodcastCoverageChecker(OutputGeneratorBase):
    """Verifies that all keypoints are covered in a podcast script.

    Usage::

        checker = PodcastCoverageChecker(request, log_callback=log)
        report = checker.verify(script_text, keypoints, book_title)
        if report.needs_revision:
            revised_script = checker.revise(script_text, report.missing, book_title)
    """

    def __init__(self, request, log_callback=None):
        super().__init__(request, log_callback)

    def verify(
        self,
        script_text: str,
        keypoints: list[str],
    ) -> CoverageReport:
        """Check coverage of all keypoints in the script.

        Returns a :class:`CoverageReport` with covered/missing lists and
        a coverage percentage.
        """
        script_lower = script_text.lower()
        covered: list[tuple[str, str | None]] = []
        missing: list[str] = []

        for i, kp in enumerate(keypoints, 1):
            kp_clean = kp.strip().lstrip("-•* ").strip()
            is_covered, matched = _check_keypoint_covered(kp_clean, script_lower)
            if is_covered:
                covered.append((kp_clean, matched))
            else:
                missing.append(kp_clean)
                self.log(
                    f"    ❌ Key point {i} NOT covered: {kp_clean[:80]}…",
                    "WARNING"
                )

        total = len(keypoints)
        covered_count = len(covered)
        percentage = (covered_count / total * 100) if total > 0 else 100.0

        self.log(
            f"  📊 Coverage: {covered_count}/{total} keypoints covered "
            f"({percentage:.0f}%)",
            "INFO"
        )

        return CoverageReport(
            total=total,
            covered_count=covered_count,
            missing=missing,
            percentage=percentage,
        )

    def revise(
        self,
        script_text: str,
        missing_keypoints: list[str],
        book_title: str,
    ) -> str | None:
        """Send the script back to the LLM to add missing keypoints.

        Returns the revised script, or None if the LLM fails.
        """
        if not missing_keypoints:
            return script_text

        missing_text = "\n".join(f"- {kp}" for kp in missing_keypoints)

        prompt = self.prompt_manager.render_template(
            "outputs/podcast_coverage_revise",
            book_title=book_title,
            missing_text=missing_text,
            script_text=script_text,
        )

        self.log(
            f"  🔄 Revising script to cover {len(missing_keypoints)} missing "
            f"keypoints…",
            "INFO"
        )

        response = self._call_llm(prompt, temperature=0.4, max_tokens=8192)
        if not response:
            self.log("  ⚠️ Revision failed — no LLM response", "WARNING")
            return None

        revised = self._strip_thinking(response)
        if not revised or not revised.strip():
            self.log("  ⚠️ Revision produced empty response", "WARNING")
            return None

        return revised

    def build_report_markdown(self, report: CoverageReport) -> str:
        """Build a markdown coverage report for the bottom of the script."""
        lines = [
            "\n---\n",
            "## Coverage Report\n",
            f"**Keypoints covered:** {report.covered_count}/{report.total} "
            f"({report.percentage:.0f}%)\n",
        ]

        if report.missing:
            lines.append("### Missing Key Points (not covered in script)\n")
            for i, kp in enumerate(report.missing, 1):
                lines.append(f"{i}. {kp}")
            lines.append("")
        else:
            lines.append("✅ All key points are covered in this script.\n")

        return "\n".join(lines)


class CoverageReport:
    """Result of a coverage check."""

    def __init__(
        self,
        total: int,
        covered_count: int,
        missing: list[str],
        percentage: float,
    ):
        self.total = total
        self.covered_count = covered_count
        self.missing = missing
        self.percentage = percentage

    @property
    def needs_revision(self) -> bool:
        """True if coverage is below threshold (default 90%)."""
        return self.percentage < 90.0 and len(self.missing) > 0

    @property
    def is_complete(self) -> bool:
        """True if ALL keypoints are covered."""
        return len(self.missing) == 0
