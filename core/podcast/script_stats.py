"""V0.6.20 (W-f1): pure-Python podcast script statistics + analytics.

Why this exists
---------------
Before V0.6.20, the wizard and the CLI could tell the operator the
script's line count and coverage percentage, but NOT the things that
actually matter for planning a generation run:

  - How long will the audio be? (Word count × words-per-minute ≈ duration.)
  - How is the talking time split between Host A and Host B? (A 50/50
    split is the conversational ideal; a 90/10 split means Host B is
    barely in it.)
  - What's the reading level? (A podcast pitched at grade 14 is
    graduate-textbook territory; grade 8 is accessible to a broad
    audience.)
  - How many words per line on average? (A 200-word line is a long
    monologue; a 5-word line is a backchannel "Yeah, exactly.")
  - What's the segment distribution? (intro / content / conclusion —
    a script with no conclusion feels cut off.)

The wizard's Loading view shows a live log during generation but the
operator has no preview of these stats BEFORE they click "Generate
Podcast." The CLI's `info` subcommand prints line count + mode +
coverage but not the richer analytics.

This module provides both. The wizard can call ``compute_stats(script)``
in the Script view (after the script is generated/edited) and show the
result in a small stats panel; the CLI gets a new ``stats`` subcommand
that prints the same data to stdout. Pure-Python, no Qt/torch deps.

The statistics are computed from the script's text content using only
stdlib (``re``, ``statistics``, ``unicodedata``) — no NLTK / spaCy /
textstat dependency (those aren't in every rig's venv). The reading-
level estimate uses the Flesch Reading Ease formula (adapted), which
needs only syllable count + word count + sentence count. Syllable
counting is heuristic (regex-based) — accurate to ~±1 syllable per
word, which is good enough for a grade-level estimate.

Public API:
  - ``ScriptStats`` — the dataclass holding all computed stats.
  - ``compute_stats(script)`` — compute + return a ScriptStats.
  - ``format_stats_for_display(stats, log)`` — multi-line formatter.
  - ``estimate_duration_seconds(word_count, wpm=150)`` — standalone
    duration estimator (used by compute_stats; exposed for the CLI).
  - ``count_syllables(word)`` — standalone syllable counter (used by
    the reading-level estimate; exposed for testing).
  - ``flesch_reading_ease(text)`` — standalone Flesch score (0-100;
    higher = easier).
  - ``flesch_kincaid_grade(text)`` — standalone grade-level estimate
    (e.g., 8.2 = grade 8).
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from core.podcast.script_generator import ScriptResult

# The default speaking rate for podcast hosts. 150 WPM is the widely-
# cited average for English conversational speech (audiobooks are ~150-
# 160; auctioneers hit 250; a slow thoughtful podcast host is ~130).
# Tunable; the wizard's future UI might let the operator override.
DEFAULT_WPM = 150

# Fallback WPM for Farsi text — Farsi speech is typically a bit slower
# than English due to the agglutinative morphology. This is a rough
# estimate; the operator can override via the wpm parameter.
FARSI_DEFAULT_WPM = 130


@dataclass
class HostStats:
    """Per-host statistics (Host A / Host B)."""

    host: str  # "A" or "B"
    line_count: int = 0
    word_count: int = 0
    char_count: int = 0
    avg_words_per_line: float = 0.0
    estimated_duration_seconds: float = 0.0
    estimated_duration_human: str = ""  # "1:23" format

    @property
    def pct_of_total_words(self) -> float:
        """Computed by the caller (needs both hosts' word counts).
        Stored as a plain attribute after compute_stats populates it."""
        return getattr(self, "_pct_words", 0.0)


@dataclass
class SegmentStats:
    """Per-segment-type statistics (intro / content / conclusion)."""

    segment_type: str
    line_count: int = 0
    word_count: int = 0


@dataclass
class ScriptStats:
    """The full statistics for a podcast script.

    All duration estimates assume DEFAULT_WPM (150) unless the script
    is Farsi (FARSI_DEFAULT_WPM = 130). The caller can override via
    ``compute_stats(script, wpm=...)``.
    """

    # Top-level counts.
    total_lines: int = 0
    total_words: int = 0
    total_chars: int = 0
    total_syllables: int = 0
    total_sentences: int = 0
    unique_words: int = 0  # vocabulary size

    # Per-host breakdown.
    host_a: HostStats = field(default_factory=lambda: HostStats(host="A"))
    host_b: HostStats = field(default_factory=lambda: HostStats(host="B"))

    # Per-segment-type breakdown.
    segments: list[SegmentStats] = field(default_factory=list)

    # Distribution metrics.
    avg_words_per_line: float = 0.0
    median_words_per_line: float = 0.0
    max_words_in_line: int = 0
    min_words_in_line: int = 0
    line_word_counts: list[int] = field(default_factory=list)

    # Duration estimate.
    estimated_duration_seconds: float = 0.0
    estimated_duration_human: str = ""  # "3:12" format
    wpm_used: int = DEFAULT_WPM

    # Reading level.
    flesch_reading_ease: float = 0.0  # 0-100, higher = easier
    flesch_kincaid_grade: float = 0.0  # e.g., 8.2 = grade 8
    reading_level_label: str = ""  # "Standard" / "Easy" / "Difficult"

    # Mode + title (echoed from the script for the formatter).
    title: str = ""
    is_conversational: bool = True

    @property
    def host_split_ratio(self) -> str:
        """The A:B word split as a string like '52:48' (always sums to 100).
        Returns '100:0' if only one host has lines."""
        total = self.host_a.word_count + self.host_b.word_count
        if total == 0:
            return "0:0"
        a_pct = round(self.host_a.word_count / total * 100)
        b_pct = 100 - a_pct
        return f"{a_pct}:{b_pct}"


# ── The heuristic syllable counter ─────────────────────────────────────────


# Vowel groups for English syllable counting. The heuristic: count
# vowel groups (a sequence of one+ vowels counts as one syllable),
# then apply a few correction rules. Accurate to ~±1 syllable per word.
_VOWELS = "aeiouyAEIOUY"


def count_syllables(word: str) -> int:
    """Count syllables in an English word using a vowel-group heuristic.

    The algorithm (a well-known approximation, e.g. the one in the
    textstat library):

      1. Lowercase + strip non-alpha.
      2. If the word is empty, return 0.
      3. Check for the "-le" ending (e.g., "apple", "table") — this
         adds 1 syllable BUT the silent-e strip would remove the 'e'
         before the -le check could fire, so we check -le on the
         ORIGINAL word first.
      4. If the word ends in a silent 'e' (and has >1 syllable after
         step 3), drop it.
      5. Count vowel groups (a sequence of one+ vowels counts as one).
      6. If the result is 0 (a word with no vowels, e.g., "TV"), return 1.
      7. Add 1 for the -le ending if the preceding char is a consonant
         (e.g., "apple" = 2, "table" = 2; "ale" = 1 — the 'l' follows a
         vowel so no extra syllable).

    Accuracy: ~±1 syllable per word, which is good enough for a grade-
    level estimate over a 500-word script.

    For non-English (Farsi / CJK) words, the heuristic is unreliable —
    the caller should pass the whole text to ``flesch_reading_ease``
    which handles the multi-language case by falling back to a neutral
    1-syllable-per-word estimate when the vowel heuristic returns 0.
    """
    word = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not word:
        return 0
    # Check the -le ending on the ORIGINAL word (before silent-e strip).
    # "apple" ends in "le" and word[-3]='p' (consonant) → +1 syllable.
    # "ale" ends in "le" but word[-3]='a' (vowel) → no extra (the 'le'
    # is part of the existing vowel group).
    le_bonus = 0
    if word.endswith("le") and len(word) > 2 and word[-3] not in _VOWELS:
        le_bonus = 1
    # Silent 'e' at the end: "like" has 1 syllable, not 2.
    if word.endswith("e") and len(word) > 2:
        word = word[:-1]
    # Count vowel groups.
    count = 0
    prev_was_vowel = False
    for ch in word:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    count += le_bonus
    # Every word has at least 1 syllable.
    return max(1, count)


# ── The Flesch reading-ease formulas ───────────────────────────────────────


# Sentence-ending punctuation. We split on these, then filter empties.
_SENTENCE_END = re.compile(r"[.!?]+")


def _split_sentences(text: str) -> list[str]:
    """Split a text into sentences. Strips empty sentences (e.g., from
    '...' or trailing periods)."""
    parts = _SENTENCE_END.split(text)
    return [p.strip() for p in parts if p.strip()]


def _count_words(text: str) -> int:
    """Count words in a text. A word is a maximal run of non-whitespace."""
    return len(text.split())


def flesch_reading_ease(text: str) -> float:
    """Compute the Flesch Reading Ease score for a text.

    Formula: 206.835 - 1.015 × (words / sentences) - 84.6 × (syllables / words)

    Returns a float in [0, 100] (clamped). Higher = easier to read:
      90-100: 5th grade (very easy)
      60-70:  8th-9th grade (standard)
      30-50:  college graduate
      0-30:   college graduate (very difficult)

    For non-English text (no detectable syllables), falls back to a
    neutral estimate (60.0 = standard) so the score doesn't break.
    """
    words = _count_words(text)
    if words == 0:
        return 0.0
    sentences = len(_split_sentences(text))
    if sentences == 0:
        sentences = 1  # treat the whole text as one sentence
    syllables = sum(count_syllables(w) for w in text.split())
    # If the syllable heuristic returned 0 for every word (non-English),
    # fall back to 1 syllable per word so the formula doesn't divide by 0.
    if syllables == 0:
        syllables = words
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    return max(0.0, min(100.0, score))


def flesch_kincaid_grade(text: str) -> float:
    """Compute the Flesch-Kincaid grade level for a text.

    Formula: 0.39 × (words / sentences) + 11.8 × (syllables / words) - 15.59

    Returns a float (e.g., 8.2 = grade 8 reading level). Clamped to >= 0.
    """
    words = _count_words(text)
    if words == 0:
        return 0.0
    sentences = len(_split_sentences(text))
    if sentences == 0:
        sentences = 1
    syllables = sum(count_syllables(w) for w in text.split())
    if syllables == 0:
        syllables = words
    grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
    return max(0.0, grade)


def _reading_level_label(flesch_score: float) -> str:
    """Map a Flesch Reading Ease score to a human-readable label."""
    if flesch_score >= 90:
        return "Very Easy (5th grade)"
    if flesch_score >= 70:
        return "Easy (6th-7th grade)"
    if flesch_score >= 60:
        return "Standard (8th-9th grade)"
    if flesch_score >= 50:
        return "Fairly Difficult (10th-12th grade)"
    if flesch_score >= 30:
        return "Difficult (college level)"
    return "Very Difficult (college graduate)"


# ── Duration formatting ────────────────────────────────────────────────────


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as 'M:SS' (e.g., 192 -> '3:12').
    For durations >= 1 hour, uses 'H:MM:SS'."""
    if seconds < 0:
        return "0:00"
    total_seconds = int(round(seconds))
    if total_seconds >= 3600:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}:{secs:02d}"


def estimate_duration_seconds(word_count: int, wpm: int = DEFAULT_WPM) -> float:
    """Estimate audio duration in seconds from a word count.

    Args:
        word_count: the number of words in the script.
        wpm: words per minute (default 150 for English; 130 for Farsi).

    Returns:
        Estimated seconds (word_count / wpm × 60). Returns 0 if
        word_count is 0 or wpm is 0.
    """
    if word_count <= 0 or wpm <= 0:
        return 0.0
    return word_count / wpm * 60.0


# ── The main compute function ──────────────────────────────────────────────


def _is_farsi_text(text: str) -> bool:
    """Detect if a text is predominantly Farsi (Persian) / Arabic.

    Uses the Unicode block check: Farsi/Arabic chars are in the
    U+0600–U+06FF (Arabic), U+FB50–U+FDFF (Arabic Presentation Forms-A),
    and U+FE70–U+FEFF (Arabic Presentation Forms-B) ranges. If >10% of
    the non-whitespace chars are in these ranges, treat as Farsi.
    """
    if not text:
        return False
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return False
    farsi_count = sum(
        1
        for c in non_ws
        if (0x0600 <= ord(c) <= 0x06FF)
        or (0xFB50 <= ord(c) <= 0xFDFF)
        or (0xFE70 <= ord(c) <= 0xFEFF)
    )
    return farsi_count / len(non_ws) > 0.10


def compute_stats(
    script: ScriptResult,
    wpm: int | None = None,
) -> ScriptStats:
    """Compute the full statistics for a podcast script.

    Args:
        script: the ScriptResult to analyze.
        wpm: optional override for words-per-minute (default: 150 for
            English, 130 for Farsi — auto-detected from the text).

    Returns:
        A ScriptStats with all fields populated.
    """
    lines = script.lines
    stats = ScriptStats(
        title=script.title,
        is_conversational=any(ln.host == "B" for ln in lines),
    )
    stats.total_lines = len(lines)
    if stats.total_lines == 0:
        return stats

    # Detect Farsi to pick the right WPM.
    all_text = " ".join(ln.text for ln in lines)
    is_farsi = _is_farsi_text(all_text)
    if wpm is None:
        stats.wpm_used = FARSI_DEFAULT_WPM if is_farsi else DEFAULT_WPM
    else:
        stats.wpm_used = wpm

    # Per-line + per-host + per-segment accumulation.
    host_a_words = 0
    host_b_words = 0
    segment_map: dict[str, SegmentStats] = {}
    line_word_counts: list[int] = []
    all_words: list[str] = []

    for line in lines:
        words = line.text.split()
        wc = len(words)
        chars = len(line.text)
        line_word_counts.append(wc)
        all_words.extend(words)

        stats.total_words += wc
        stats.total_chars += chars

        # Per-host accumulation.
        if line.host == "A":
            stats.host_a.line_count += 1
            stats.host_a.word_count += wc
            stats.host_a.char_count += chars
            host_a_words += wc
        elif line.host == "B":
            stats.host_b.line_count += 1
            stats.host_b.word_count += wc
            stats.host_b.char_count += chars
            host_b_words += wc

        # Per-segment accumulation.
        seg = segment_map.setdefault(line.segment_type, SegmentStats(line.segment_type))
        seg.line_count += 1
        seg.word_count += wc

    stats.segments = list(segment_map.values())

    # Distribution metrics.
    if line_word_counts:
        stats.avg_words_per_line = statistics.mean(line_word_counts)
        stats.median_words_per_line = statistics.median(line_word_counts)
        stats.max_words_in_line = max(line_word_counts)
        stats.min_words_in_line = min(line_word_counts)
    stats.line_word_counts = line_word_counts

    # Vocabulary size (unique words, case-insensitive).
    stats.unique_words = len({w.lower() for w in all_words})

    # Syllables + sentences (for reading level).
    stats.total_syllables = sum(count_syllables(w) for w in all_words)
    stats.total_sentences = len(_split_sentences(all_text))

    # Duration estimates.
    stats.estimated_duration_seconds = estimate_duration_seconds(stats.total_words, stats.wpm_used)
    stats.estimated_duration_human = _format_duration(stats.estimated_duration_seconds)
    stats.host_a.estimated_duration_seconds = estimate_duration_seconds(
        stats.host_a.word_count, stats.wpm_used
    )
    stats.host_a.estimated_duration_human = _format_duration(
        stats.host_a.estimated_duration_seconds
    )
    stats.host_b.estimated_duration_seconds = estimate_duration_seconds(
        stats.host_b.word_count, stats.wpm_used
    )
    stats.host_b.estimated_duration_human = _format_duration(
        stats.host_b.estimated_duration_seconds
    )

    # Avg words per line per host.
    if stats.host_a.line_count > 0:
        stats.host_a.avg_words_per_line = stats.host_a.word_count / stats.host_a.line_count
    if stats.host_b.line_count > 0:
        stats.host_b.avg_words_per_line = stats.host_b.word_count / stats.host_b.line_count

    # Reading level.
    stats.flesch_reading_ease = flesch_reading_ease(all_text)
    stats.flesch_kincaid_grade = flesch_kincaid_grade(all_text)
    stats.reading_level_label = _reading_level_label(stats.flesch_reading_ease)

    return stats


def format_stats_for_display(
    stats: ScriptStats,
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format a ScriptStats as a multi-line string for the wizard's stats
    panel or the CLI's stdout. Optionally logs each section.

    The format:

        📊 Script Statistics
        ════════════════════════════════════════════════════════════
        Title:          My Podcast
        Mode:           conversational
        Lines:          24
        Words:          1,247  (unique: 412)
        Characters:      7,234
        Syllables:      1,856  (sentences: 38)

        ⏱️  Duration estimate (150 WPM):
            Total:        8:19
            Host A:       4:12  (52%)
            Host B:       4:07  (48%)
            Split:        52:48

        👥 Per-host breakdown:
            Host A:  12 lines,  647 words, avg 54.0 words/line
            Host B:  12 lines,  600 words, avg 50.0 words/line

        📑 Segment distribution:
            intro:        1 line,   42 words
            content:     22 lines, 1,150 words
            conclusion:   1 line,   55 words

        📏 Line-length distribution:
            Avg: 52.0 words  |  Median: 50.0  |  Min: 12  |  Max: 89

        📖 Reading level:
            Flesch Reading Ease: 62.3/100  (Standard, 8th-9th grade)
            Flesch-Kincaid Grade: 8.2

    If the script is empty, returns "⚠️ Empty script — no stats to show.".
    """
    if stats.total_lines == 0:
        msg = "⚠️ Empty script — no stats to show."
        if log:
            log(msg, "WARNING")
        return msg

    parts: list[str] = []
    parts.append("📊 Script Statistics")
    parts.append("═" * 60)
    parts.append(f"Title:          {stats.title or '(none)'}")
    parts.append(f"Mode:           {'conversational' if stats.is_conversational else 'lecture'}")
    parts.append(f"Lines:          {stats.total_lines}")
    parts.append(f"Words:          {stats.total_words:,}  (unique: {stats.unique_words})")
    parts.append(f"Characters:     {stats.total_chars:,}")
    if stats.total_syllables:
        parts.append(
            f"Syllables:      {stats.total_syllables:,}  (sentences: {stats.total_sentences})"
        )
    parts.append("")
    parts.append(f"⏱️  Duration estimate ({stats.wpm_used} WPM):")
    parts.append(f"    Total:        {stats.estimated_duration_human}")
    if stats.is_conversational:
        total_words = stats.host_a.word_count + stats.host_b.word_count
        if total_words > 0:
            a_pct = round(stats.host_a.word_count / total_words * 100)
            b_pct = 100 - a_pct
            parts.append(f"    Host A:       {stats.host_a.estimated_duration_human}  ({a_pct}%)")
            parts.append(f"    Host B:       {stats.host_b.estimated_duration_human}  ({b_pct}%)")
            parts.append(f"    Split:        {stats.host_split_ratio}")
    parts.append("")
    parts.append("👥 Per-host breakdown:")
    parts.append(
        f"    Host A:  {stats.host_a.line_count} lines,  "
        f"{stats.host_a.word_count} words, "
        f"avg {stats.host_a.avg_words_per_line:.1f} words/line"
    )
    if stats.is_conversational:
        parts.append(
            f"    Host B:  {stats.host_b.line_count} lines,  "
            f"{stats.host_b.word_count} words, "
            f"avg {stats.host_b.avg_words_per_line:.1f} words/line"
        )
    parts.append("")
    parts.append("📑 Segment distribution:")
    for seg in stats.segments:
        parts.append(
            f"    {seg.segment_type:12s}: {seg.line_count:3d} lines, {seg.word_count:5d} words"
        )
    parts.append("")
    parts.append("📏 Line-length distribution:")
    parts.append(
        f"    Avg: {stats.avg_words_per_line:.1f} words  |  "
        f"Median: {stats.median_words_per_line:.1f}  |  "
        f"Min: {stats.min_words_in_line}  |  Max: {stats.max_words_in_line}"
    )
    parts.append("")
    parts.append("📖 Reading level:")
    parts.append(
        f"    Flesch Reading Ease: {stats.flesch_reading_ease:.1f}/100  "
        f"({stats.reading_level_label})"
    )
    parts.append(f"    Flesch-Kincaid Grade: {stats.flesch_kincaid_grade:.1f}")

    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out
