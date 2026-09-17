"""V18.18.0.0 (Phase 2c): Post-check detector functions.

Extracted from ``postchecks.py`` (was 2586 LOC). This module contains all the
detector functions + their module-level constants. The ``postchecks.py`` module
retains: Issue, PostCheckReport, run_post_checks, _snippet, _is_subsequence,
and re-exports everything from here for backward compatibility.

All existing imports ``from core.summarisation.postchecks import X`` continue
to work — postchecks.py re-exports everything.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from core.preprocessing.citations_regex import APOS as _CIT_APOS
from core.preprocessing.citations_regex import NAME_SEP as _CIT_NAME_SEP

logger = logging.getLogger(__name__)


MIN_YEAR = 1800

MAX_YEAR = date.today().year + 1

# ── Prompt-leakage phrases ────────────────────────────────────────────────
# Case-insensitive. Each is a raw regex; matched with re.IGNORECASE.
# These are the model's own CoT/process phrases that leak past the
# response_parser's per-field strip_reasoning_leaks() — that function
# runs on individual fields during parsing; this is the FINAL sweep
# across the assembled summary and catches what slipped through.


@dataclass
class Issue:
    """A single post-check finding."""
    detector: str
    severity: str
    field: str
    snippet: str
    detail: str


@dataclass
class PostCheckReport:
    """Result of running all post-checks."""
    bullets: list[str] = field(default_factory=list)
    executive_summary: str = ""
    thorough_summary: str = ""
    key_distinctions: str = ""
    theoretical_tensions: str = ""
    issues: list[Issue] = field(default_factory=list)
    fixed_count: int = 0
    flagged_count: int = 0

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)
        if issue.severity == "fix":
            self.fixed_count += 1
        else:
            self.flagged_count += 1

    @property
    def total_findings(self) -> int:
        return len(self.issues)



def _snippet(text: str, pos: int, width: int = 60) -> str:
    """Return a ~``width``-char context window around ``pos``."""
    if not text:
        return ""
    start = max(0, pos - width // 2)
    end = min(len(text), pos + width // 2)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return re.sub(r'\s+', ' ', snippet).strip()

_PROMPT_LEAKAGE_PATTERNS: tuple[str, ...] = (
    # Direct echoes of the prompt template
    r'provided\s+in\s+the\s+(?:input|source|text|chapter|passage)\b',
    r'as\s+(?:mentioned|noted|stated|described|discussed)\s+in\s+the\s+(?:source|input|text|passage|chapter)\b',
    r'based\s+on\s+the\s+source\s+(?:text|material|content)\b',
    r'according\s+to\s+the\s+(?:source|input|text|passage)\b',
    # First-person process leaks
    r"\bI\s+(?:need\s+to|must|should|will|am\s+going\s+to|can|cannot|don't\s+have)\b",
    r"\bI'll\b",
    # V18.15.7.0 (Fix 1): extended the "Let me" alternation with the verbs the
    # V18.15.6.0 golden-master actually produced ("Let me organize my
    # understanding", "Let me count carefully", "Let me draft each section
    # now", "Wait, let me re-read", "Let me be very careful", "Let me list
    # them"). Pre-V18.15.7.0 these bypassed detection — the thorough_summary
    # was 100% chain-of-thought narrative.
    r"\bLet\s+me\s+(?:go|work|carefully|identify|extract|now|think|consider|check|analyze|summarize|organize|count|draft|re-?read|be\s+very\s+careful|list|write|note|see|ensure|make\s+sure|count\s+carefully)\b",
    r"\bWait,?\s+let\s+me\b",
    # V18.15.7.0 (Fix 1): the model's structural-reasoning phrases that leak
    # into thorough_summary as bullet-preparation narrative.
    r"\bNamed contributors in order\b",
    r"\bwrite the five sections\b",
    r"\bBullet points\s*\(\s*\d+-\d+\s*\)\s*:",
    r"\bExecutive Summary\s*\(\s*\d+-\d+\s*words?\s*\)\s*:",
    r"\bI need \d+-\d+ distinct key takeaways\b",
    r"\bLet me count\b",
    r"\bLet me draft\b",
    r"\bLet me list them\b",
    r"\bLet me be very careful\b",
    # V18.15.7.0 (Fix 1): prompt-instruction echoes (the V18.15.6.0 run shipped
    # these as standalone bullets in the Key Takeaways).
    r"^Keep sentences under \d+ words\b",
    r"^Preserve (?:technical|all)\s+(?:terms|citations)\b",
    r"^Use active voice\b",
    r"^Sentences under \d+ words\b",
    r"\bCover all named contributors\b",
    r"\bInclude the full progression\b",
    r"\bEnd with the conclusion'?s enumerated list\b",
    r"\bThis is a tension\b",
    r"\bThis is the (?:reading|reading level) requirement\b",
    r"\bmaking sure to:\s*$",
    r"\bwhile also maintaining academic precision\b",
    r"\bgo through the source material\b",
    # V18.20.3.9 (Phase 2 / A3 — residuals sweep): was the book-keyed literal
    # "what appears to be a domain text" (harvested from a run on a
    # analysis book). Generalized to the structural class: the model
    # speculating about the SOURCE's genre is CoT self-commentary regardless
    # of the domain — "a historical text", "a technical manual"… all match.
    r"\bwhat (?:appears|seems) to be (?:a|an) [a-z\-]+ (?:text|book|work|chapter|document|study|manual)\b",
    r"\bextract all key concepts, arguments, frameworks\b",
    r"\bLet me organize my understanding\b",
    r"\bwait,? let me re-?read\b",
    r"\bnow write\b",
    r'\bNow\s+I\s+(?:will|shall|can|need)\b',
    # Self-reference / refusals
    r'\bas\s+an\s+AI\b',
    r'\bas\s+a\s+language\s+model\b',
    r"\bI'm\s+(?:not\s+)?(?:able|sure)\s+to\b",
    # Template scaffolding that survives parsing
    r'\bhere\s+is\s+the\s+(?:summary|bullet|list|chapter)\b',
    r'\bhere\s+are\s+the\s+(?:bullets|key\s+points|takeaways)\b',
    r'\bthe\s+user\s+(?:wants|asked|requested|specifically)\b',
    r'\bthe\s+instructions?\s+(?:say|state|ask|require)\b',
)

# Compiled once at import.

_PROMPT_LEAKAGE_RE = [re.compile(p, re.IGNORECASE) for p in _PROMPT_LEAKAGE_PATTERNS]

# ── Garbled-token detection ───────────────────────────────────────────────
# A word is "garbled" if it hits any of these. We use word-boundary regex on
# tokens of length >= 4 (too many false positives below 4).

# Consonant cluster of 6+ (English maxes out around 5: "lengths", "twelfths",
# "angstrom", "borschts"). 6+ almost always indicates a merge artifact.
# NOTE: 'y' is EXCLUDED from the consonant class — in words like "rhythm",
# "nymph", "myth", "syzygy" it acts as a vowel. Including it would
# false-flag those common academic words. (The vowel-less detector below
# already treats 'y' as a vowel for the same reason.)

_LONG_CONSONANT_CLUSTER_RE = re.compile(
    r'\b\w*[bcdfghjklmnpqrstvwxz]{6,}\w*\b', re.IGNORECASE
)

# Impossible English bigrams inside a word (case-sensitive lowercased).
# "xz", "qq", "zc", "kx" never appear in real English words.

_IMPOSSIBLE_BIGRAMS = ('xz', 'zx', 'qq', 'zz', 'kx', 'xk', 'jx', 'xj',
                       'qx', 'xq', 'vc', 'cv', 'kz', 'zk', 'jz', 'zj')

_IMPOSSIBLE_BIGRAM_RE = re.compile(
    r'\b\w*(?:' + '|'.join(_IMPOSSIBLE_BIGRAMS) + r')\w*\b', re.IGNORECASE
)

# Long vowel-less words. English words with no vowel (a/e/i/o/u) longer than
# 4 chars are extremely rare (the only common ones are "crwth", "cwm",
# "nth", "tsktsk", "phpht" — none appear in academic prose). We also treat
# "y" as a vowel here to avoid flagging "rhythm", "nymph", "myth", "syzygy".

_VOWEL = 'aeiouy'

_VOWEL_LESS_LONG_RE = re.compile(
    r'\b[^aeiouy\W\d]{5,}\b', re.IGNORECASE  # V18.2.19: exclude digits (1980b etc.)
)

# V18.15.3.2: _GARBLED_ALLOWLIST DELETED. Hand-curated word lists are not
# allowed — they're bandaids that break on the next book. detect_garbled_tokens
# now uses source-grounding: if a vowel-less word appears in the source text,
# it's legitimate (don't flag). See detect_garbled_tokens() for the source-aware
# validation that replaced this list.

# ── Missing-space detection ───────────────────────────────────────────────
# "the"+Capitalized, "of"+Capitalized, "and"+Capitalized etc. The detector
# splits these. We match the JOINED form: a stopword immediately followed by
# a Capitalized or lowercase word, forming one token.
# Examples: "theAuthor" → "the AuthorZ", "thesonic" → "the sonic",
#           "ofAuthor" → "of AuthorL", "doingsIdentity" → "doings Identity".
#
# V18.15.3.2: _SPACE_STOPWORDS and _LOWER_SPLIT_SAFE DELETED. Hand-curated
# word lists are not allowed. Pattern detection now uses structural length
# filters, and validation is source-grounded (see detect_missing_spaces).

# Pattern 1: any 1-3 char lowercase word + Capitalized word (e.g., "theFreud")
# The Capital letter after a short lowercase word is a near-certain merge signal.

_MISSING_SPACE_CAP_RE = re.compile(
    r'\b([a-z]{1,3})([A-Z][a-zA-Z]{2,})\b'
)

# Pattern 2: any 1-3 char lowercase word + 4+ char lowercase suffix (e.g., "thesonic")
# 4-char min on the suffix to avoid catching "thee", "them", "then", "thea".
# V18.15.3.2: source-grounded validation decides whether to split (see below).

_MISSING_SPACE_LOWER_RE = re.compile(
    r'\b([a-z]{1,3})([a-z]{4,})\b',
    re.IGNORECASE
)

# Pattern 3: lowercase word + Capitalized word mid-token (camelCase merge,
# e.g., "doingsIdentity"). The lowercase part must be >= 3 chars and the
# Capitalized part >= 3 chars.

_CAMELCASE_MERGE_RE = re.compile(
    r'\b([a-z]{3,})([A-Z][a-zA-Z]{2,})\b'
)

# ── Year / citation validation ────────────────────────────────────────────
# Matches "Author (YYYY)" and "Author YYYY" (inline). We use this to find
# citations in the SUMMARY so we can validate the author against the source.
# V18.15.5.1 (DEBT-08): use shared Unicode-aware apostrophe + dash classes
# from core.preprocessing.citations_regex. Pre-V18.15.5.1, this used ASCII-only
# `'` and `[-\u2013]`, silently SKIPPING curly-possessive citations
# (e.g. "Federn's (1952)" with U+2019 copied verbatim from PDF source).

_SUMMARY_CITATION_RE = re.compile(
    r'([A-Z][a-zA-Z]+(?:' + _CIT_NAME_SEP + r'[A-Z][a-zA-Z]+)?'
    r"(?:" + _CIT_APOS + r"[sS]?)?)"
    r'\s*\(?(\d{4}[a-z]?)\)?'
)
# V18.2.18 Improvement 1: Bold-name bullet pattern — "**AuthorName**: text".
# Gap-fill bullets use this format (e.g. "**AuthorC**: Provided the developmental
# basis for..."). The existing _SUMMARY_CITATION_RE only matches Author+Year,
# so it misses these bold-name bullets entirely. This pattern captures the
# bolded author name (no year required) so we can verify the author exists in
# the source AND check the claim's attribution.
# V18.15.5.1 (DEBT-08): use shared NAME_SEP (adds U+2014 em-dash + U+2010/U+2011
# typographic hyphens for compound surnames).

_BOLD_NAME_RE = re.compile(
    r'\*\*([A-Z][a-zA-Z]+(?:' + _CIT_NAME_SEP + r'[A-Z][a-zA-Z]+)?)\*\*\s*:\s*(.{10,})'
)
# Bare 4-digit number that looks like a year (not part of a citation).

_BARE_YEAR_RE = re.compile(r'\b(1\d{3}|20\d{2}|21\d{2})\b')


def validate_years(
    text: str,
    field_label: str,
    source_authors: list[str] | None = None,
) -> tuple[str, list[Issue]]:
    """Validate 4-digit years and ``(Author Year)`` citations.

    Two checks:

    1. **Plausible range.** Every 4-digit number that looks like a year is
       checked against ``[MIN_YEAR, MAX_YEAR]``. Years outside the range are
       flagged (severity ``"flag"`` — we don't know the right year, so we
       don't rewrite; the bullet is kept and logged for human review).

    2. **Author-name grounding** (only when ``source_authors`` is provided).
       Every ``(Author YYYY)`` citation found in ``text`` is checked: if the
       Author does not fuzzy-match any author in the source's citation list,
       it is flagged. This is the detector that catches "Dukhaim 1951" — the
       source has "AuthorY", the summary has "Dukhaim", and the names don't
       match. The corrupted name is kept as-is (we can't reliably reconstruct
       it deterministically) but the issue is recorded.

       The fuzzy match uses casefold equality first, then a simple normalized
       Levenshtein-ish check (rapidfuzz if available, else a startswith
       fallback). Authors shorter than 3 chars are skipped (too noisy).

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]" — for issue reporting.
        source_authors: optional list of author surnames extracted from the
            source via ``deterministic_analyzer.extract_citations``. When
            ``None``, only the year-range check runs.

    Returns:
        ``(text, issues)``. The text is returned UNCHANGED — year/name
        validation only flags; it never rewrites (the corrections are
        ambiguous without an LLM).
    """
    issues: list[Issue] = []
    if not text:
        return text, issues

    # --- Check 1: plausible year range --------------------------------------
    try:
        for m in _BARE_YEAR_RE.finditer(text):
            yr = int(m.group(1))
            if yr < MIN_YEAR or yr > MAX_YEAR:
                snippet = _snippet(text, m.start())
                issues.append(Issue(
                    detector="year",
                    severity="flag",
                    field=field_label,
                    snippet=snippet,
                    detail=f"implausible year {yr} (outside {MIN_YEAR}-{MAX_YEAR})",
                ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="year", severity="flag", field=field_label,
            snippet=text[:60], detail=f"year-range check crashed: {e!r}",
        ))

    # --- Check 2: author-name grounding -------------------------------------
    if source_authors:
        try:
            # Build a casefolded lookup set once.
            src_lower = {a.casefold(): a for a in source_authors
                         if a and len(a) >= 3}
            seen_flags = set()  # avoid duplicate flags for the same name
            for m in _SUMMARY_CITATION_RE.finditer(text):
                author = m.group(1).strip()
                year = m.group(2)
                # Skip possessive 's / trailing punctuation
                author_clean = re.sub(r"['\u2019]s$", "", author)
                author_clean = author_clean.strip(".,;:")
                if len(author_clean) < 3:
                    continue
                # Skip obvious non-names (the regex can catch "In (1950)" etc.)
                if author_clean.split()[0].lower() in {
                    "in", "by", "the", "a", "an", "as", "at", "to", "of",
                    "and", "or", "for", "with", "from", "that", "this",
                    "while", "when", "where", "later", "then", "early",
                }:
                    continue
                if _author_in_source(author_clean, src_lower):
                    continue
                key = author_clean.casefold()
                if key in seen_flags:
                    continue
                seen_flags.add(key)
                snippet = _snippet(text, m.start())
                issues.append(Issue(
                    detector="year",
                    severity="flag",
                    field=field_label,
                    snippet=snippet,
                    detail=(f"author '{author_clean}' (cited with {year}) not "
                            f"found in source's {len(source_authors)} citations "
                            f"— possible name corruption"),
                ))
        except Exception as e:  # fail-open
            issues.append(Issue(
                detector="year", severity="flag", field=field_label,
                snippet=text[:60], detail=f"author-grounding check crashed: {e!r}",
            ))

    return text, issues



def _author_in_source(author: str, src_lower: dict[str, str]) -> bool:
    """True if ``author`` matches any source author (casefold or fuzzy)."""
    a = author.casefold()
    if a in src_lower:
        return True
    # V18.2.19: Also try the normalized form (strip hyphens) so
    # "AuthorA" matches "chasseguetsmirgel".
    a_norm = a.replace('-', '').replace('\u2013', '').replace(' ', '')
    for src in src_lower:
        if a == src:
            return True
        src_norm = src.replace('-', '').replace('\u2013', '').replace(' ', '')
        if a_norm == src_norm:
            return True
    # Try rapidfuzz (optional dep); else fall back to startswith/levenshtein.
    try:
        from rapidfuzz import fuzz as _rf
        return any(
            _rf.token_set_ratio(a, src) >= 82
            for src in src_lower
        )
    except ImportError:
        # Simple fallback: casefold startswith either direction (handles
        # "AuthorY" vs "Dukhaim" only loosely, but rapidfuzz is in deps).
        return any(
            a.startswith(src) or src.startswith(a)
            for src in src_lower
        )


# ═══════════════════════════════════════════════════════════════════════════
# Detector 2 — Prompt-leakage stripping
# ═══════════════════════════════════════════════════════════════════════════


def detect_prompt_leakage(text: str, field_label: str) -> tuple[str, list[Issue]]:
    """Strip prompt-leakage phrases from ``text``.

    Removes the model's CoT/process phrases that leak past
    :func:`response_parser.strip_reasoning_leaks`. Also removes a stray
    leading ``"("`` when the leakage phrase it opened (``"( provided in the
    input"``) is gone — the V18.2.12 garbled token was literally
    ``"( provided in the input"`` with an unmatched paren.

    Each removed phrase is recorded as an Issue with severity ``"fix"``.

    Args:
        text: the summary text to clean.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(cleaned_text, issues)``.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    cleaned = text
    try:
        for pat in _PROMPT_LEAKAGE_RE:
            for m in list(pat.finditer(cleaned)):
                snippet = _snippet(cleaned, m.start())
                issues.append(Issue(
                    detector="prompt",
                    severity="fix",
                    field=field_label,
                    snippet=snippet,
                    detail=f"stripped prompt-leakage: '{m.group(0)[:40]}'",
                ))
            cleaned = pat.sub('', cleaned)
        # Collapse the double-spaces the substitutions leave behind.
        cleaned = re.sub(r'  +', ' ', cleaned)
        # Remove a stray leading "(" that now opens nothing — the classic
        # V18.2.12 artifact was "( provided in the input" and after removing
        # the phrase, "(" lingers at the start of a bullet/sentence.
        cleaned = re.sub(r'(?m)^\s*\(\s+', '', cleaned)
        cleaned = re.sub(r'\s+\)\s*([.;,])', r'\1', cleaned)  # dangling ")"
        # Strip a leading ", " left behind when a leakage phrase opened a
        # clause (e.g., "( provided in the input, the author notes..." ->
        # after stripping the leakage + leading "(" we get ", the author notes";
        # clean up the orphaned comma so the bullet starts cleanly).
        cleaned = re.sub(r'(?m)^\s*,\s+', '', cleaned)
        # Collapse newlines that the removals may have orphaned.
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned).strip()
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="prompt", severity="flag", field=field_label,
            snippet=text[:60], detail=f"prompt-leakage check crashed: {e!r}",
        ))
        return text, issues
    return cleaned, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.15.7.0 (Fix 1): CoT-narrative detector for thorough_summary
# ═══════════════════════════════════════════════════════════════════════════

# Signals that the thorough_summary field is the model's chain-of-thought
# narrative, NOT a summary. The V18.15.6.0 golden-master produced a 4346-word
# thorough_summary that was 100% CoT ("Let me organize my understanding...",
# "Named contributors in order:", "write the five sections carefully...",
# "Let me count carefully.", "Let me draft each section now.", etc.).
# detect_prompt_leakage strips individual phrases but leaves the surrounding
# CoT scaffolding. This detector catches the SUSTAINED pattern: if the
# thorough_summary contains >= 3 of these structural CoT markers, it's CoT
# narrative, not a summary → truncate to empty (the caller falls back to
# exec_sum per summarizer.py:3077).

_COT_NARRATIVE_MARKERS: tuple[str, ...] = (
    r'\bLet me (?:organize|count|draft|list|write|be very careful)\b',
    r'\bNamed contributors in order\b',
    r'\bwrite the five sections\b',
    r'\bBullet points\s*\(\s*\d+-\d+\s*\)\s*:',
    r'\bExecutive Summary\s*\(\s*\d+-\d+\s*words?\s*\)\s*:',
    r'\bI need \d+-\d+ distinct key takeaways\b',
    r'\bWait,? let me re-?read\b',
    r'\bLet me organize my understanding\b',
    r'\bwhat (?:appears|seems) to be (?:a|an) [a-z\-]+ (?:text|book|work|chapter|document|study|manual)\b',  # V18.20.3.9: book-keyed literal generalized (see the leak-pattern twin above)
    r'\bgo through the source material\b',
    r'\bextract all key concepts, arguments, frameworks\b',
    r'\bmaking sure to:\s*$',
    r'\bwhile also maintaining academic precision\b',
    r'\bThis is a tension\b',
    r'\bnow write\b',
    r'\bLet me count carefully\b',
    r'\bLet me draft each section\b',
    r'\bLet me list them\b',
    # V18.16.0.1 (Fix 1): exec-from-thorough CoT markers. The V18.16.0.0
    # regression: the exec-from-thorough call produced CoT that started with
    # "me to write a 150-250 word executive summary... synthesize the key
    # points... Draft: This chapter...". These are the model echoing the
    # PROMPT INSTRUCTIONS back as its output, NOT a summary.
    r'\bme to write\b',
    r'\bsynthesize the key\b',
    r'\bKey elements to capture\b',
    r'\bthis in flowing prose\b',
    r'\bcarefully\.\s*Draft\b',
    r'^\s*Draft:\s',
    r'\bsynthesize.*thorough summary\b',
)

_COT_NARRATIVE_RE = [re.compile(p, re.IGNORECASE) for p in _COT_NARRATIVE_MARKERS]



def detect_cot_narrative(text: str, field_label: str) -> tuple[str, list[Issue]]:
    """V18.15.7.0 (Fix 1): Detect if the thorough_summary is the model's
    chain-of-thought narrative (NOT a summary).

    The V18.15.6.0 golden-master produced a thorough_summary that was 100% CoT
    ("Let me organize my understanding...", "Named contributors in order:",
    "Let me count carefully.", "Let me draft each section now."). The
    ``detect_prompt_leakage`` detector strips individual phrases but leaves
    the surrounding CoT scaffolding, producing a fragmented mess.

    This detector counts structural CoT markers. If >= 3 are present, the
    text is overwhelmingly CoT narrative → truncate to empty + flag. The
    caller (``summarizer._summarize_inner`` line ~3077) then falls back to
    ``exec_sum`` for the thorough_summary field.

    Threshold rationale: a legitimate summary might accidentally contain 1
    CoT-like phrase (e.g., "Let me elaborate on..."). 3+ markers is a strong
    signal the entire field is CoT.

    Args:
        text: the thorough_summary text to check.
        field_label: typically "thorough".

    Returns:
        ``(cleaned_text, issues)``. If CoT is detected, ``cleaned_text`` is
        empty (caller falls back); otherwise it's the original text unchanged.
    """
    issues: list[Issue] = []
    if not text or len(text) < 50:
        return text, issues
    try:
        marker_count = sum(1 for pat in _COT_NARRATIVE_RE if pat.search(text))
        if marker_count >= 3:
            issues.append(Issue(
                detector="cot_narrative",
                severity="flag",
                field=field_label,
                snippet=text[:80],
                detail=(
                    f"thorough_summary is chain-of-thought narrative "
                    f"({marker_count} CoT markers detected — truncating to "
                    f"empty; caller falls back to exec_sum). The V18.15.6.0 "
                    f"golden-master regression was caused by this: the "
                    f"thorough_summary was 100% model reasoning, not a summary."
                ),
            ))
            return "", issues
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="cot_narrative", severity="flag", field=field_label,
            snippet=text[:60], detail=f"CoT-narrative check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# Detector 3 — Garbled-token detection (flag only)
# ═══════════════════════════════════════════════════════════════════════════


def detect_garbled_tokens(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """Flag unusual character sequences that signal garbled tokens.

    Three signals:

    1. **Long consonant clusters** (6+ consonants in a row inside a word).
       English tops out around 5 ("lengths", "twelfths"); 6+ almost always
       indicates a token-merge artifact.
    2. **Impossible English bigrams** (``xz``, ``qq``, ``kx``, …). These
       never appear inside a real English word.
    3. **Long vowel-less words** (5+ chars, no a/e/i/o/u/y). Real English
       vowel-less words are extremely rare and none appear in academic prose.

    This detector FLAGS only — it does not rewrite. (A garbled token like
    "thesonic" is handled by :func:`detect_missing_spaces`; "Dukhaim" by
    :func:`validate_years`. Pure nonsense tokens have no safe deterministic
    correction, so we flag for review rather than guess.)

    The allowlist :data:`_GARBLED_ALLOWLIST` exempts common cluster-heavy
    words ("through", "strength", "rhythms", etc.) to avoid false positives.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is returned UNCHANGED.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    try:
        # V18.20.2.0 (SWOT A24): the source word-set was previously rebuilt
        # (a full-source regex scan) inside _flag for EVERY flagged match;
        # accept a precomputed set from run_post_checks and fall back to the
        # lazy per-call build for direct callers.
        if source_words is None:
            source_words = set(re.findall(r'\b[a-z]+\b', source_text.lower())) if source_text else set()
        flagged_words: set = set()

        def _flag(match: re.Match, signal: str) -> None:
            word = match.group(0)
            # Strip surrounding punctuation for allowlist lookup.
            bare = word.strip('.,;:!?"\'()[]{}')
            # V18.15.3.2: source-grounded — if the word is in the source, it's legitimate
            if source_words and bare.casefold() in source_words:
                return
            key = (bare.casefold(), signal)
            if key in flagged_words:
                return
            flagged_words.add(key)
            snippet = _snippet(text, match.start())
            issues.append(Issue(
                detector="garbled",
                severity="flag",
                field=field_label,
                snippet=snippet,
                detail=f"{signal}: '{bare}'",
            ))

        for m in _LONG_CONSONANT_CLUSTER_RE.finditer(text):
            _flag(m, "long consonant cluster (6+)")
        for m in _IMPOSSIBLE_BIGRAM_RE.finditer(text):
            _flag(m, "impossible English bigram")
        for m in _VOWEL_LESS_LONG_RE.finditer(text):
            _flag(m, "long vowel-less word (5+)")
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="garbled", severity="flag", field=field_label,
            snippet=text[:60], detail=f"garbled-token check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# Detector 4 — Missing-space detection (auto-fix)
# ═══════════════════════════════════════════════════════════════════════════


def detect_missing_spaces(
    text: str,
    field_label: str,
    source_text: str = "",
    source_lower: str | None = None,
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """Fix missing spaces where a stopword merged with the following word.

    Catches the V18.2.12 artifacts ``"thesonic"`` (→ ``"the sonic"``) and
    ``"thefive-stage"`` (→ ``"the five-stage"``).

    Three patterns:

    1. **stopword + Capitalized** (``theAuthor`` → ``the AuthorZ``). The Capital
       is a strong signal that two tokens were joined. Always fixed.
    2. **stopword + lowercase (4+ chars)** (``thesonic`` → ``the sonic``).
       The 4-char minimum avoids catching ``thee``/``them``/``then``/``thea``.
       Fixed only if the *split* form is more plausible: we check that the
       stopword + suffix isn't itself a known word (via a small stoplist of
       real merged words like ``theory``, ``theme``, ``there``, ``these``).
    3. **camelCase merge** (``doingsIdentity`` → ``doings Identity``). Lowercase
       run of 3+ chars followed by a Capitalized run of 3+ chars. Fixed.

    Args:
        text: the summary text to clean.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(cleaned_text, issues)``.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    cleaned = text
    try:
        # Pattern 1: stopword + Capitalized → split (always safe).
        def _split_cap(m: re.Match) -> str:
            issues.append(Issue(
                detector="space",
                severity="fix",
                field=field_label,
                snippet=_snippet(cleaned, m.start()),
                detail=f"split '{m.group(0)}' → '{m.group(1)} {m.group(2)}'",
            ))
            return f"{m.group(1)} {m.group(2)}"
        cleaned = _MISSING_SPACE_CAP_RE.sub(_split_cap, cleaned)

        # Pattern 3: camelCase merge → split (always safe).
        def _split_camel(m: re.Match) -> str:
            # Don't split if the lowercase part is a known stopword that
            # Pattern 1 already handled (avoid double-splitting "theFreud").
            # V18.15.3.2: skip if Pattern 1 already handled (short word + Capital)
            if len(m.group(1)) <= 3:
                return m.group(0)
            issues.append(Issue(
                detector="space",
                severity="fix",
                field=field_label,
                snippet=_snippet(cleaned, m.start()),
                detail=f"split camelCase '{m.group(0)}' → '{m.group(1)} {m.group(2)}'",
            ))
            return f"{m.group(1)} {m.group(2)}"
        cleaned = _CAMELCASE_MERGE_RE.sub(_split_camel, cleaned)

        # Pattern 2: "the" + lowercase (4+) → split, but NOT if the merged
        # form is a real English word. Pattern 2 is restricted to "the" only
        # (see _LOWER_SPLIT_SAFE), so this allowlist only needs "the"-prefixed
        # real words whose suffix is 4+ chars: "theater", "theatre", "theirs",
        # "thence", "theorem", "theology", "theorist", "theoretical", etc.
        # Short suffixes (<=3 chars: "theory"="the"+"ory" where "ory" is 3)
        # never reach this code because of the {4,} minimum in the regex.
                # V18.15.3.2: _real_merged DELETED. Source-grounded validation replaces it.
        # V18.20.2.0 (SWOT A24): accept precomputed source_lower/source_words
        # from run_post_checks (was rebuilt per bullet); lazy-build when omitted.
        if source_lower is None:
            source_lower = source_text.lower() if source_text else ""
        if source_words is None:
            source_words = set(re.findall(r'\b[a-z]+\b', source_lower)) if source_text else set()

        def _split_lower(m: re.Match) -> str:
            merged = m.group(0)
            merged_lower = merged.casefold()
            split_form = f"{m.group(1)} {m.group(2)}"
            if not source_text:
                return merged  # no source -> can't validate -> don't split (safe)
            # If merged word is in source -> real word -> don't split
            if merged_lower in source_words:
                return merged
            # If split form appears in source -> confirmed merge -> split
            if split_form.lower() in source_lower:
                issues.append(Issue(
                    detector="space",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=f"split '{merged}' -> '{split_form}' (source-validated)",
                ))
                return split_form
            # Neither form in source -> conservative: don't split
            return merged
        cleaned = _MISSING_SPACE_LOWER_RE.sub(_split_lower, cleaned)

        # Final whitespace cleanup.
        cleaned = re.sub(r'  +', ' ', cleaned).strip()
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="space", severity="flag", field=field_label,
            snippet=text[:60], detail=f"missing-space check crashed: {e!r}",
        ))
        return text, issues
    return cleaned, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.17 Fix 5 — Anti-interpretation filter (deterministic + book-agnostic)
# ═══════════════════════════════════════════════════════════════════════════

# First-person interpretive phrases — the summarizer's OWN voice adding
# interpretation. These are ALWAYS auto-stripped (they never belong in a
# faithful summary). Book-agnostic: "we can see that" is bad in any
# discipline.

_INTERPRETIVE_FIRST_PERSON_RE = re.compile(
    r'\b(?:'
    r'we\s+can\s+see\s+that|we\s+can\s+conclude\s+that|'
    r'we\s+see\s+that|we\s+note\s+that|we\s+observe\s+that|'
    r'we\s+can\s+infer\s+that|we\s+can\s+deduce\s+that|'
    r'it\s+is\s+clear\s+that|it\s+is\s+evident\s+that|'
    r'it\s+is\s+obvious\s+that|it\s+should\s+be\s+noted\s+that|'
    r'it\s+is\s+worth\s+noting\s+that|it\s+is\s+important\s+to\s+note\s+that'
    r')\s*,?\s*',
    re.IGNORECASE,
)

# Interpretive-leap phrases — signal the summarizer is drawing a
# conclusion the source may not make. These are FLAGGED, not auto-stripped,
# because the source itself sometimes uses them legitimately. The flag
# leaves a trace for review.

_INTERPRETIVE_LEAP_RE = re.compile(
    r'\b(?:'
    r'this\s+implies|this\s+suggests|this\s+means|'
    r'this\s+indicates|this\s+demonstrates|this\s+shows|'
    r'this\s+reveals|this\s+illustrates|this\s+proves'
    r')\b',
    re.IGNORECASE,
)



def detect_interpretive_leaps(
    text: str,
    field_label: str,
    source_text: str | None = None,
    source_lower: str | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.17 Fix 5: Strip/flag interpretive leaps the summarizer adds.

    Two tiers:

    1. **First-person interpretive phrases** (auto-stripped): "we can see
       that", "it is clear that", "it should be noted that", etc. These
       are ALWAYS the summarizer's voice — a faithful summary reports
       what the source says, not what the summarizer concludes. Stripped
       + recorded as a fix.

    2. **Interpretive-leap phrases** (flagged): "this implies", "this
       suggests", "this means", "this indicates", "this demonstrates",
       etc. These COULD be the source's own language (legitimate) OR the
       summarizer adding interpretation. When ``source_text`` is provided,
       we check if the phrase appears in the source near the same context;
       if it does, we skip (the source used it). If not, we FLAG — the
       summarizer likely added the interpretation.

    Book-agnostic: "we can see that" is bad in biology, history, philosophy,
    economics — any discipline. No domain-specific terms.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: optional source. When provided, interpretive-leap
            phrases are only flagged if they DON'T appear in the source
            (the source's own use is legitimate).

    Returns:
        ``(cleaned_text, issues)``.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    cleaned = text
    try:
        # Tier 1: Auto-strip first-person interpretive phrases.
        for m in list(_INTERPRETIVE_FIRST_PERSON_RE.finditer(cleaned)):
            issues.append(Issue(
                detector="interpretation",
                severity="fix",
                field=field_label,
                snippet=_snippet(cleaned, m.start()),
                detail=f"stripped first-person interpretation: '{m.group(0).strip()}'",
            ))
        cleaned = _INTERPRETIVE_FIRST_PERSON_RE.sub('', cleaned)
        # Clean up the double-space / capitalization left behind.
        cleaned = re.sub(r'\s+([,.;])', r'\1', cleaned)
        cleaned = re.sub(r'  +', ' ', cleaned)

        # Tier 2: Flag interpretive-leap phrases (source-aware).
        # V18.20.2.0 (SWOT A24): accept the precomputed 200k-char lowercased
        # source from run_post_checks (was rebuilt per bullet); lazy-build
        # when omitted. Callers must pass the SLICED variant
        # (source_text.lower()[:200000]) to preserve behaviour.
        if source_lower is None:
            source_lower = source_text.lower()[:200000] if source_text else ""
        src_lower = source_lower
        for m in list(_INTERPRETIVE_LEAP_RE.finditer(cleaned)):
            phrase = m.group(0).lower()
            # If the source itself uses this exact phrase within 200 chars
            # of the surrounding context, it's likely the source's own
            # language — skip (legitimate).
            if src_lower and phrase in src_lower:
                # Check if the source uses it near a similar context.
                # Simple check: is the phrase present in the source at all?
                # (A full context-match would need embeddings; this is a
                # conservative proxy that avoids false-flagging the source's
                # own language.)
                continue
            issues.append(Issue(
                detector="interpretation",
                severity="flag",
                field=field_label,
                snippet=_snippet(cleaned, m.start()),
                detail=(
                    f"interpretive leap '{phrase}' not found in source — "
                    f"summarizer may be adding interpretation"
                ),
            ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="interpretation", severity="flag", field=field_label,
            snippet=text[:60], detail=f"interpretive-leap check crashed: {e!r}",
        ))
        return text, issues
    return cleaned, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.17 Fix 6 — Hedge preservation (deterministic + book-agnostic)
# ═══════════════════════════════════════════════════════════════════════════

# Universal hedge words — present in academic writing across ALL disciplines
# (biology, history, philosophy, economics, psychology, etc.). These signal
# uncertainty/qualification in the source. Book-agnostic by design.

_HEDGE_WORDS = (
    'may', 'might', 'could', 'appears to', 'seems to', 'suggests',
    'likely', 'possibly', 'perhaps', 'uncertain', 'unclear',
    'remains', 'arguably', 'presumably', 'potentially', 'seemingly',
    'allegedly', 'purportedly', 'hinges on', 'depends on',
    'not yet', 'not fully', 'not entirely', 'subject to',
    'tentatively', 'hypothetically', 'theoretically',
)

_HEDGE_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(w) for w in _HEDGE_WORDS) + r')\b',
    re.IGNORECASE,
)



def detect_hedge_loss(
    text: str,
    source_text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V18.2.17 Fix 6: Detect when the summary drops the source's hedging.

    Compares the hedge density (hedge words per 1000 chars) of the summary
    vs the source. If the source has significant hedges but the summary has
    far fewer, the summary may be presenting hedged claims as certain.

    This is a SUMMARY-LEVEL check (one issue per field), not per-bullet —
    matching individual hedged claims across source/summary requires
    embeddings and is too noisy deterministically. The density comparison
    is a reliable, book-agnostic signal.

    Threshold: if source has ≥3 hedges per 1000 chars AND summary has <1
    per 1000 chars → FLAG (the summary is dropping hedges).

    Book-agnostic: "may", "appears to", "suggests" are universal academic
    hedges. No domain-specific terms.

    Args:
        text: the summary text.
        source_text: the chapter source text.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only — rewriting
        requires understanding which hedge to add, which is ambiguous).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        src_hedges = len(_HEDGE_RE.findall(source_text))
        sum_hedges = len(_HEDGE_RE.findall(text))
        # Normalize per 1000 chars.
        src_density = src_hedges / max(len(source_text), 1) * 1000
        sum_density = sum_hedges / max(len(text), 1) * 1000

        if src_density >= 3.0 and sum_density < 1.0:
            issues.append(Issue(
                detector="hedge",
                severity="flag",
                field=field_label,
                snippet=f"source {src_density:.1f}/1k vs summary {sum_density:.1f}/1k",
                detail=(
                    f"hedge loss: source has {src_hedges} hedges "
                    f"({src_density:.1f}/1k chars) but summary has only "
                    f"{sum_hedges} ({sum_density:.1f}/1k) — hedged claims "
                    f"may be presented as certain"
                ),
            ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="hedge", severity="flag", field=field_label,
            snippet=text[:60], detail=f"hedge-loss check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.17 Fix 7 — Attribution verification (deterministic + book-agnostic)
# ═══════════════════════════════════════════════════════════════════════════


def verify_attribution(
    text: str,
    source_text: str,
    field_label: str,
    source_authors: list[str] | None = None,
    source_lower: str | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.17 Fix 7: Verify each (Author Year) citation's claim matches source.

    For each ``(Author Year)`` citation in the summary:
    1. Extract the surrounding sentence as the "summary claim".
    2. Find the same ``(Author Year)`` in the source.
    3. Extract the source's sentence as the "source claim".
    4. Compute text similarity (rapidfuzz token_set_ratio, or difflib fallback).
    5. If similarity < 50% → FLAG (the summary's claim about this author may
       not match what the source says about them).

    Book-agnostic: uses citation-pattern matching + generic text similarity.
    No domain-specific terms, no hardcoded author lists. Works on any
    discipline where authors are cited with years.

    Args:
        text: the summary text.
        source_text: the chapter source text.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_authors: optional pre-extracted author list (from
            :func:`validate_years`). When None, only the claim-matching
            runs (no name-grounding — that's validate_years' job).

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only — rewriting
        the claim requires understanding what the source actually said).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        # Find all (Author Year) citations in the summary.
        summary_citations = list(_SUMMARY_CITATION_RE.finditer(text))
        if not summary_citations:
            return text, issues

        # Build source sentence index for fast lookup.
        src_sentences = re.split(r'(?<=[.!?])\s+', source_text)
        # V18.20.2.0 (SWOT A24): accept the precomputed 200k-char lowercased
        # source (was rebuilt per bullet); lazy-build when omitted.
        src_lower = source_lower if source_lower is not None else source_text.lower()[:200000]

        # Try rapidfuzz for similarity; fall back to difflib.
        try:
            from rapidfuzz import fuzz as _rf
            _has_rf = True
        except ImportError:
            from difflib import SequenceMatcher
            _has_rf = False

        def _similarity(a: str, b: str) -> float:
            if _has_rf:
                return _rf.token_set_ratio(a, b) / 100.0
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()

        seen = set()  # avoid duplicate flags for the same author
        for m in summary_citations:
            author = m.group(1).strip()
            year = m.group(2)
            author_clean = re.sub(r"['\u2019]s$", "", author).strip(".,;:")
            if len(author_clean) < 3:
                continue
            # Skip non-name stopwords (same list as validate_years).
            if author_clean.split()[0].lower() in {
                "in", "by", "the", "a", "an", "as", "at", "to", "of",
                "and", "or", "for", "with", "from", "that", "this",
                "while", "when", "where", "later", "then", "early",
            }:
                continue
            key = author_clean.casefold()
            if key in seen:
                continue
            seen.add(key)

            # Find this author in the source.
            author_lower = author_clean.lower()
            if author_lower not in src_lower:
                continue  # validate_years already flags name mismatches

            # Extract the summary's sentence containing this citation.
            sent_start = text.rfind('.', 0, m.start()) + 1
            sent_end = text.find('.', m.end())
            if sent_end < 0:
                sent_end = len(text)
            summary_claim = text[sent_start:sent_end].strip()

            # Find the source sentence containing this author + year.
            best_src_claim = ""
            best_sim = 0.0
            year_lower = year.lower()
            for sent in src_sentences:
                if author_lower in sent.lower():
                    # Prefer sentences that also mention the year.
                    sim = _similarity(summary_claim, sent)
                    if sim > best_sim:
                        best_sim = sim
                        best_src_claim = sent

            if best_src_claim and best_sim < 0.50:
                # V18.20.3.4 (RC-5c, audit v182033): borderline-band
                # verification. The V18.20.3.3 run produced attribution
                # flags at 43-49% similarity on CORRECT paraphrases — a
                # tight paraphrase legitimately scores below 50% on
                # token-set overlap while its content still tracks the
                # source sentence. For the 40-50% band, verify the claim's
                # SALIENT VOCABULARY against the best source sentence
                # before flagging: named entities (theorist, year, proper
                # nouns) AND long content words (>= 5 chars, non-function).
                # When at least half of them appear in the source sentence,
                # the claim is a paraphrase, not a misattribution — suppress.
                # Below 40% the claim is far enough from the source that
                # this check would not rescue it anyway — flag as before.
                # NOTE: the cited author + year alone never carry the
                # rescue — a fabricated claim about the same author also
                # "aligns" on those. The check only helps when the claim
                # has OTHER vocabulary, and most of it tracks the source.
                _suppressed_as_paraphrase = False
                if 0.40 <= best_sim < 0.50:
                    _src_words_set = set(
                        re.findall(r'\b[a-z0-9]+\b', best_src_claim.lower())
                    )
                    _checks = [
                        e for e in re.findall(
                            r'\b[A-Z][a-zA-Z]{2,}\b|\b\d{4}[a-z]?\b',
                            summary_claim,
                        )
                        if e.lower() not in {
                            "the", "in", "by", "a", "an", "as", "at", "to",
                            "of", "and", "or", "for", "with", "from", "that",
                            "this", "these", "those", "while", "when", "where",
                            "later", "then", "early", "his", "her", "their",
                            "its", "he", "she",
                        } and e.lower() != author_clean.lower()
                    ]
                    _checks += [
                        w for w in re.findall(r'\b[a-z]{5,}\b', summary_claim.lower())
                        if w not in {
                            "about", "their", "which", "there", "these",
                            "those", "while", "through", "between", "during",
                            "before", "after", "where", "would", "could",
                            "should", "might", "because", "since", "although",
                            "though", "other", "others", "being", "having",
                        }
                    ]
                    if _checks:
                        _hits = sum(
                            1 for w in _checks
                            if w.lower() in _src_words_set
                            or w.lower().rstrip('s') in _src_words_set
                            or w.lower() + 's' in _src_words_set
                        )
                        if _hits / len(_checks) >= 0.5:
                            _suppressed_as_paraphrase = True
                if _suppressed_as_paraphrase:
                    continue
                issues.append(Issue(
                    detector="attribution",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"attribution mismatch: summary's claim about "
                        f"'{author_clean} ({year})' has {best_sim:.0%} "
                        f"similarity to the source's claim about this author "
                        f"(threshold 50% — the claim may be misrepresented"
                    ),
                ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="attribution", severity="flag", field=field_label,
            snippet=text[:60], detail=f"attribution check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.18 Improvement 1 — Bold-name attribution verification
# ═══════════════════════════════════════════════════════════════════════════


def verify_bold_name_attribution(
    text: str,
    source_text: str,
    field_label: str,
    source_authors: list[str] | None = None,
    source_lower: str | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.18 Improvement 1: Verify ``**AuthorName**: claim`` bullets.

    Gap-fill bullets use the ``**Author**: claim`` format (e.g.
    ``**AuthorC**: Provided the foundational mechanism for...``). The existing
    :func:`verify_attribution` only matches ``(Author Year)`` citations,
    so it misses these entirely. This detector:

    1. Finds all ``**Author**: text`` patterns.
    2. Checks if the Author exists in the source's citation list (when
       ``source_authors`` is provided). If NOT → FLAG (unknown author).
    3. Checks if the Author's name appears anywhere in the source text.
       If NOT → FLAG (author not mentioned in source at all).
    4. If the author IS in the source, checks the claim's similarity to
       source sentences mentioning that author. If <50% → FLAG (claim may
       be misrepresented — this is what caught the AuthorC error in V18.2.15).

    Book-agnostic: uses bold-name pattern matching + generic text similarity.
    No domain-specific terms.

    Args:
        text: the summary text.
        source_text: the chapter source text.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_authors: optional pre-extracted author list.

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        bold_matches = list(_BOLD_NAME_RE.finditer(text))
        if not bold_matches:
            return text, issues

        # V18.20.2.0 (SWOT A24): accept the precomputed 200k-char lowercased
        # source (was rebuilt per bullet); lazy-build when omitted.
        src_lower = source_lower if source_lower is not None else source_text.lower()[:200000]
        # Try rapidfuzz for similarity; fall back to difflib.
        try:
            from rapidfuzz import fuzz as _rf
            _has_rf = True
        except ImportError:
            from difflib import SequenceMatcher
            _has_rf = False

        def _similarity(a: str, b: str) -> float:
            if _has_rf:
                return _rf.token_set_ratio(a, b) / 100.0
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()

        import re as _re
        src_sentences = _re.split(r'(?<=[.!?])\s+', source_text)

        seen = set()
        for m in bold_matches:
            author = m.group(1).strip()
            claim = m.group(2).strip()
            if len(author) < 3:
                continue
            key = author.casefold()
            if key in seen:
                continue
            seen.add(key)

            author_lower = author.lower()
            if author_lower not in src_lower:
                # Author not mentioned in source at all → FLAG.
                issues.append(Issue(
                    detector="attribution",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"bold-name author '{author}' not found in source — "
                        f"the summary attributes a claim to an author the "
                        f"source never mentions"
                    ),
                ))
                continue

            # Author IS in source — check if the claim matches.
            # Find source sentences mentioning this author.
            best_sim = 0.0
            best_src_claim = ""
            for sent in src_sentences:
                if author_lower in sent.lower():
                    sim = _similarity(claim, sent)
                    if sim > best_sim:
                        best_sim = sim
                        best_src_claim = sent

            if best_src_claim and best_sim < 0.50:
                issues.append(Issue(
                    detector="attribution",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"bold-name attribution mismatch: '**{author}**: "
                        f"{claim[:40]}…' has {best_sim:.0%} similarity to "
                        f"the source's claim about this author (threshold 50% "
                        f"— the claim may be misrepresented"
                    ),
                ))

            # V18.2.18 Improvement 1 (enhanced): Check if the author is the
            # SUBJECT of the source's claim, not just mentioned. The AuthorC
            # error in V18.2.15: source says "AuthorB... His work provides
            # the foundational mechanism for the constructs; the term (AuthorC
            # 1983)..." — AuthorC is only cited for the TERM, not the work.
            # The summary's "**AuthorC**: Provided the foundational mechanism..."
            # misattributes AuthorB's work to AuthorC.
            # Detection: if the author appears ONLY in "(Author Year)" citation
            # context in the best-matching source sentence, AND the sentence
            # (or its preceding context) names a DIFFERENT author as the
            # subject, flag it.
            if best_src_claim:
                _citation_ctx = _re.search(
                    r'\(' + _re.escape(author) + r'\s+\d{4}',
                    best_src_claim,
                )
                # Check if the author's name appears OUTSIDE of a parenthetical
                # citation (i.e., as the sentence subject, not just a cite).
                _non_citation_mention = bool(_re.search(
                    rf'(?<!\(){author}\b(?!\s*\d{{4}})',
                    best_src_claim,
                ))
                if _citation_ctx and not _non_citation_mention:
                    issues.append(Issue(
                        detector="attribution",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"bold-name subject mismatch: '**{author}**: "
                            f"{claim[:40]}…' — the source mentions "
                            f"'{author}' only as a citation (e.g. "
                            f"'({author} YEAR)'), not as the subject of the "
                            f"claim. The work may be attributed to a different "
                            f"author in the source."
                        ),
                    ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="attribution", severity="flag", field=field_label,
            snippet=text[:60], detail=f"bold-name attribution check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.18 Improvement 2 — Grammatical coherence check (broken-bullet detector)
# ═══════════════════════════════════════════════════════════════════════════

# V18.2.15 had a broken Key Distinctions bullet: "Identity and AuthorD both
# crisis of adolescence versus a diagnostic construct: AuthorI described the usual
# identity crisis of adolescenceThe distinction matters because..."
# This is a generation/formatting failure — not a token-level garble (no
# consonant clusters, no impossible bigrams) but a grammatical one (no main
# verb, two sentences merged without separator).
#
# Detection heuristics (book-agnostic):
# 1. Missing main verb: the bullet's first ~40 words contain no finite verb.
# 2. Merged sentences: a period immediately followed by a Capital letter
#    with no space (e.g. "adolescenceThe").
# 3. Disjoint noun phrases: "Noun1 and Noun2 both Noun3" pattern (no verb
#    between subject and object).

# Pattern 2: period+Capital with no space (merged sentences)

_MERGED_SENTENCE_RE = re.compile(r'\.([A-Z][a-z]+)')

# Common finite-verb endings (3rd person singular + base forms).
# Used to detect "no main verb" — if none of these appear in the first
# 40 words, the bullet likely has no finite verb.

_VERB_ENDINGS = (
    'es', 'ed', 'ing', 'ies', 'ied', 'ays', 'ows', 'aps', 'ops', 'ups',
    'ans', 'ens', 'ins', 'ars', 'ers', 'irs', 'ors', 'urs',
    'ate', 'ite', 'ose', 'ise', 'ize',
    'ect', 'act', 'ict', 'upt', 'apt', 'opt',
    'ain', 'oin', 'urn', 'awn',
    # V18.2.19: Irregular verb endings (past tense + participles).
    'ade',  # made, bade, waded
    'oke',  # broke, spoke, woke
    'elt',  # felt, dealt, knelt
    'ew',   # knew, threw, grew, blew
    'at',   # sat, pat, chat
    'it',   # hit, split, quit
    'ut',   # shut, cut, put
    'et',   # set, let, get, met
    'ound', # found, bound, wound
    'old',  # sold, told, held
    'ung',  # hung, sung, rung
    'unk',  # sunk, drunk, shrunk
)
# Stopwords that look like verbs but aren't (auxiliaries + articles).

_VERB_STOPWORDS = frozenset({
    'the', 'and', 'but', 'for', 'with', 'from', 'this', 'that', 'these',
    'those', 'which', 'what', 'when', 'where', 'while', 'during', 'before',
    'after', 'between', 'among', 'through', 'without', 'within', 'against',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'shall', 'must',
})



def detect_grammatical_incoherence(
    text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V18.2.18 Improvement 2: Flag grammatically broken bullets.

    Catches the V18.2.15 broken Key Distinctions bullet pattern:
    "Identity and AuthorD both crisis of adolescence versus identity
    diffusion: AuthorI described..."

    Three signals (any one triggers a FLAG):
    1. **Merged sentences**: a period immediately followed by a Capital
       letter with no space (``.The`` → ``. The``).
    2. **No main verb**: the first 40 words contain no finite verb.
    3. **Disjoint subject-object**: "Noun1 and Noun2 both Noun3" with no
       verb between (e.g. "Identity and AuthorD both crisis").

    Book-agnostic: these are universal grammatical signals, not
    domain-specific. Works on any language that uses Latin script.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only).
    """
    issues: list[Issue] = []
    if not text or len(text.strip()) < 20:
        return text, issues
    try:
        # Signal 1: Merged sentences (.Capital with no space)
        for m in list(_MERGED_SENTENCE_RE.finditer(text)):
            issues.append(Issue(
                detector="grammar",
                severity="flag",
                field=field_label,
                snippet=_snippet(text, m.start()),
                detail=(
                    f"merged sentences: '.{m.group(1)}' — a period is "
                    f"immediately followed by a Capital letter with no space. "
                    f"Likely a formatting/extraction failure."
                ),
            ))

        # Signal 2 + 3: Check each bullet/line for missing verb
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 15]
        for line in lines:
            words = re.findall(r'[A-Za-z]+', line)
            if len(words) < 5:
                continue
            first_40 = words[:40]
            # Check for any finite verb (word >3 chars ending in a verb suffix,
            # not a stopword).
            has_verb = any(
                len(w) > 3 and w.lower() not in _VERB_STOPWORDS and
                any(w.lower().endswith(e) for e in _VERB_ENDINGS)
                for w in first_40
            )
            if not has_verb:
                # Double-check: is there an auxiliary (is/are/was/were)?
                has_aux = any(w.lower() in _VERB_STOPWORDS for w in first_40
                              if w.lower() in ('is', 'are', 'was', 'were',
                                               'have', 'has', 'had'))
                if not has_aux:
                    issues.append(Issue(
                        detector="grammar",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(line, 0),
                        detail=(
                            f"no main verb detected in first 40 words of "
                            f"'{line[:40]}…' — the bullet may be grammatically "
                            f"broken (generation/formatting failure)"
                        ),
                    ))

            # Signal 3: "Noun1 and Noun2 both Noun3" with no verb
            # Pattern: two proper nouns joined by "and", then "both", then
            # a lowercase noun (not a verb).
            _disjoint = re.search(
                r'([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+both\s+([a-z]+)',
                line,
            )
            if _disjoint:
                third = _disjoint.group(3).lower()
                # Is the third word a verb? If not, it's a disjoint pattern.
                _is_verb = any(third.endswith(e) for e in _VERB_ENDINGS) and \
                           len(third) > 3
                if not _is_verb:
                    issues.append(Issue(
                        detector="grammar",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(line, 0),
                        detail=(
                            f"disjoint subject-object: '{_disjoint.group(0)}' "
                            f"— '{_disjoint.group(1)} and {_disjoint.group(2)} "
                            f"both {_disjoint.group(3)}' has no verb between "
                            f"the subject and object. Likely a broken bullet."
                        ),
                    ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="grammar", severity="flag", field=field_label,
            snippet=text[:60], detail=f"grammar check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.19 Improvement 1 — Extra-space detector (split words)
# ═══════════════════════════════════════════════════════════════════════════

# Catches "the oreticians" → "theoreticians" (word split by a spurious space).
# This is the OPPOSITE failure mode from detect_missing_spaces: a single word
# is split into two tokens by an extra space inserted by low-bit quantization.
#
# Detection (book-agnostic): a stopword + a fragment that together form a
# known English word when joined. Uses a common-word set (~5000 words built
# from the most frequent English terms). No domain-specific vocabulary.

def detect_extra_spaces(
    text: str,
    field_label: str,
    source_text: str = "",
    source_lower: str | None = None,
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V18.15.3.2: Detect words split by a spurious space — SOURCE-GROUNDED.

    NO external word lists. The source text is the only dictionary.

    Detection: any short word (1-3 chars) + space + fragment (3+ chars).
    The length filter is structural (not a curated stopword list).

    Validation (Phase 1 — direct): is the joined word a standalone word in
    the source? And is the fragment NOT in the source? If both → join.
    (If the fragment IS in the source, it's a real word, not a split fragment.)

    Validation (Phase 2 — adjacent-word guided): if Phase 1 fails, get
    adjacent words from the summary, find them in the source, search nearby
    for the joined word (allowing hyphens). If found → join.

    If neither phase validates → don't join (safe — no false positives).
    If source_text is empty/None → can't validate → return unchanged.
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues

    # V18.20.2.0 (SWOT A24): accept precomputed source_lower/source_words
    # from run_post_checks (was rebuilt per bullet); lazy-build when omitted.
    source_lower = source_lower if source_lower is not None else source_text.lower()
    # Build a set of standalone words in the source (for O(1) lookup)
    source_words = source_words if source_words is not None else set(re.findall(r'\b[a-z]+\b', source_lower))

    cleaned = text
    try:
        # Pattern: any short word (1-3 chars) + space + fragment (3+ chars)
        _SPLIT_RE = re.compile(r'\b([a-zA-Z]{1,3})\s+([a-z]{3,})\b')

        def _join_if_valid(m: re.Match) -> str:
            word1 = m.group(1).lower()
            fragment = m.group(2).lower()
            joined = word1 + fragment

            # V18.20.3.2 (audit N8 / P2-b): GLOBAL split-form veto. If the
            # split form ("ego ideal") appears ANYWHERE in the source as
            # standalone words, the two-word form is legitimate in this
            # source — never join. The V18.20.3.1 run joined 'ego ideal' →
            # 'egoideal' via Phase 2: a hyphenated 'ego-ideal' occurrence sat
            # inside the ±300-char window while the 8 spaced occurrences
            # elsewhere in the source went unseen (the old split-form guard
            # was window-local). The source is the dictionary — if it uses
            # the split form at all, we keep it.
            if re.search(
                r'\b' + re.escape(word1) + r'\s+' + re.escape(fragment) + r'\b',
                source_lower,
            ):
                return m.group(0)

            # Phase 1: Direct source lookup
            # Join only if: joined IS in source AND fragment is NOT in source.
            # This catches "the reby" → "thereby" (source has "thereby",
            # "reby" is not a standalone source word).
            if joined in source_words and fragment not in source_words:
                issues.append(Issue(
                    detector="extra_space",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=f"joined split word: '{m.group(0)}' \u2192 '{joined}' (source-validated)",
                ))
                return joined

            # Phase 2: Adjacent-word guided lookup
            # V18.15.3.2 bugfix: Phase 2 must search for the JOINED form
            # (or hyphenated variant), NOT the split form. The old regex
            # allowed an optional space between parts, which matched
            # "the core construct" in the source and falsely joined it to
            # "egoidentity". Now we search for the exact joined token or
            # the hyphenated variant only.
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            context = text[start:end].lower()
            context_words = [w for w in re.findall(r'\b[a-z]{4,}\b', context)
                            if w != fragment and w != word1]

            for adj_word in context_words[:4]:
                adj_pos = source_lower.find(adj_word)
                if adj_pos >= 0:
                    window_start = max(0, adj_pos - 300)
                    window_end = min(len(source_lower), adj_pos + 300)
                    window = source_lower[window_start:window_end]
                    # Search for the JOINED form as a standalone token,
                    # or the hyphenated variant (e.g., a compound term).
                    # Do NOT match the split form ("the core construct").
                    hyphenated = word1 + '-' + fragment
                    if (re.search(r'\b' + re.escape(joined) + r'\b', window) or
                        re.search(r'\b' + re.escape(hyphenated) + r'\b', window)):
                        # Extra safety: don't join if the split form (word1 + ' ' + fragment)
                        # also appears in the window as standalone words — that means
                        # the split form is legitimate in this source.
                        split_pattern = r'\b' + re.escape(word1) + r'\s+' + re.escape(fragment) + r'\b'
                        if re.search(split_pattern, window):
                            continue  # split form is in source → don't join
                        issues.append(Issue(
                            detector="extra_space",
                            severity="fix",
                            field=field_label,
                            snippet=_snippet(cleaned, m.start()),
                            detail=f"joined split word: '{m.group(0)}' \u2192 '{joined}' (source-validated via adjacent '{adj_word}')",
                        ))
                        return joined

            # Not found in source → don't join (safe)
            return m.group(0)

        cleaned = _SPLIT_RE.sub(_join_if_valid, cleaned)
    except Exception as e:
        issues.append(Issue(
            detector="extra_space", severity="flag", field=field_label,
            snippet=text[:60], detail=f"extra-space check crashed: {e!r}",
        ))
        return text, issues
    return cleaned, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.19 Improvement 2 — Word-fragment merge detector
# ═══════════════════════════════════════════════════════════════════════════

# Catches "adolescenceo fill" → "adolescence. To fill" (merged sentence boundary).
# A word + stray chars + space + another word, where the stray chars (1-2
# lowercase letters) are the remnant of a dropped ". T" or ". t".

# Pattern: (dictionary word)(1-2 lowercase chars)(space)(common word)
# The 1-2 stray chars are the "o" from "To" after the ". T" was dropped.

_FRAGMENT_MERGE_RE = re.compile(
    r'\b([a-z]{4,})([a-z]{1,2})\s+([a-z]{2,})\b',
    re.IGNORECASE,
)

# V18.9 (Option B fix): Legitimate English inflection suffixes.
# When the "stray chars" are one of these, the word+stray is a valid
# inflection (plural, past tense, adjective, etc.) — NOT a fragment merge.
# This eliminates the 5th-occurrence false-positive class where "differences",
# "conditions", "contributions", "representations", etc. were flagged.

_LEGIT_SUFFIXES = frozenset({
    's',    # plural: difference→differences, condition→conditions
    'es',   # plural: box→boxes, church→churches
    'ed',   # past tense: contribute→contributed, view→viewed
    'er',   # comparative/agent: view→viewer, think→thinker
    'ly',   # adverb: quick→quickly, clear→clearly
    'al',   # adjective: environment→environmental, condition→conditional
    'ing',  # participle: run→running, think→thinking
    'est',  # superlative: big→biggest, fast→fastest
    'd',    # past tense: use→used, move→moved
    'ers',  # plural agent: view→viewers, think→thinkers
    'ies',  # plural: city→cities, theory→theories
    'ied',  # past tense: city→citied (rare but valid)
    'ier',  # comparative: happy→happier
    'iest', # superlative: happy→happiest
    'ing',  # present participle (duplicate for safety)
    'ic',   # adjective: history→historic
    'ity',  # noun: active→activity
    'ment', # noun: develop→development
    'ness', # noun: dark→darkness
    'tion', # noun: act→action
    'able', # adjective: use→usable
    'ible', # adjective: access→accessible
    'ous',  # adjective: danger→dangerous
    'ive',  # adjective: act→active
    'ful',  # adjective: use→useful
    'less', # adjective: use→useless
})



def _is_legitimate_inflection(word: str, stray: str) -> bool:
    """V18.9: Check if word+stray is a legitimate English inflection of word.

    Returns True if ``stray`` is a standard English suffix (plural, past
    tense, adjective, etc.) — meaning ``word+stray`` is a valid word form,
    NOT a fragment-merge artifact.

    This eliminates the false-positive class where "differences" (word=
    "difference", stray="s") was flagged as a fragment merge. "differences"
    is the standard plural of "difference" — not a dropped sentence boundary.
    """
    return stray.lower() in _LEGIT_SUFFIXES



def detect_word_fragment_merge(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.19: Detect merged sentence-boundary fragments.

    Catches "adolescenceo fill" → "adolescence. To fill" where a period+T
    was dropped and "to" became "o". The result is a word + stray char(s)
    + space + another word.

    Detection (book-agnostic): finds ``(word)(1-2 stray chars) (word)``
    where the first part (word+stray) is NOT a known word, but the word
    alone IS known. This indicates the stray chars are a fragment of a
    dropped sentence boundary.

    Flag-only (doesn't auto-fix — the correct reconstruction is ambiguous:
    "adolescenceo" could be "adolescence. To" or "adolescence. O" etc.)

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED.
    """
    issues: list[Issue] = []

    # V18.20.2.0 (SWOT A24): accept the precomputed source word-set from
    # run_post_checks (was rebuilt per bullet); lazy-build when omitted.
    if source_words is None:
        source_words = set(re.findall(r'\b[a-z]+\b', source_text.lower())) if source_text else set()
    if not text:
        return text, issues
    try:
        for m in list(_FRAGMENT_MERGE_RE.finditer(text)):
            # V18.2.19: Check BOTH the left side (group1+group2) AND the
            # right side (group3) for word+stray patterns. The fragment
            # merge can appear on either side of the space.
            # Left: "emphasized" → group1="emphasize", group2="d" → "emphasized" IS a word (OK)
            # Right: "adolescenceo" → need to split group3 too.
            # Check the left side first:
            word = m.group(1).lower()
            stray = m.group(2).lower()
            full = (word + stray).lower()
            # V18.9 (Option B fix): Skip if stray is a legitimate English suffix
            # (plural 's', past tense 'ed', adjective 'al', etc.). This eliminates
            # the 5th-occurrence false-positive class where "differences", "conditions",
            # "contributions", etc. were flagged. These are valid inflections, NOT
            # dropped sentence boundaries.
            if word in source_words and full not in source_words and len(stray) <= 2:
                if _is_legitimate_inflection(word, stray):
                    continue  # valid plural/past-tense/adjective — not a fragment merge
                issues.append(Issue(
                    detector="fragment_merge",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"word-fragment merge: '{m.group(1)}{m.group(2)} {m.group(3)}' "
                        f"— '{word}' is a known word but '{full}' is not. "
                        f"The '{stray}' may be a remnant of a dropped "
                        f"sentence boundary (e.g. '. To')."
                    ),
                ))
                continue
            # Check the right side (group3): is it a known word + stray chars?
            # E.g. "adolescenceo" → "adolescence" + "o"
            right = m.group(3).lower()
            # Try stripping 1-2 chars from the end and see if the base is known.
            for strip_len in (1, 2):
                if len(right) > strip_len + 3:
                    base = right[:-strip_len]
                    stray_right = right[-strip_len:]
                    if base in source_words and right not in source_words:
                        # V18.9 (Option B fix): Skip if the stripped suffix is a
                        # legitimate English inflection (plural, past tense, etc.)
                        if _is_legitimate_inflection(base, stray_right):
                            continue  # valid inflection — not a fragment merge
                        issues.append(Issue(
                            detector="fragment_merge",
                            severity="flag",
                            field=field_label,
                            snippet=_snippet(text, m.start(3)),
                            detail=(
                                f"word-fragment merge: '{m.group(3)}' "
                                f"— '{base}' is a known word but '{right}' is not. "
                                f"The trailing '{stray_right}' may be a remnant "
                                f"of a dropped sentence boundary (e.g. '. To')."
                            ),
                        ))
                        break
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="fragment_merge", severity="flag", field=field_label,
            snippet=text[:60], detail=f"fragment-merge check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.19.2.3 (Audit Fix 5): Dropped-letter / single-char garbled-token detector
# ═══════════════════════════════════════════════════════════════════════════
# The V18.19.2.0 audit found the model emitted "emergs" (should be "emerges" —
# a dropped 'e' before 's'). This is a single-word garbled token that the
# existing detectors miss:
#   - detect_garbled_tokens: looks for consonant clusters / impossible bigrams /
#     vowel-less words. "emergs" has vowels (e,e) and no impossible bigram.
#   - detect_word_fragment_merge: looks for "word+stray space word" patterns.
#     "emergs" is a single word, no space.
#
# This detector is SOURCE-GROUNDED (no hand-curated word list — the project
# explicitly banned those in V18.15.3.2). Logic: for each word in the summary
# that is NOT in the source text, check if a single-character edit (insert /
# delete / substitute) makes it appear in the source. If yes → flag as a
# likely garbled token. This catches "emergs"→"emerges", "Dukhaim"→"AuthorY",
# "identiy"→"identity", etc.
#
# Constraint: minimum word length 5 (shorter words have too many edit-distance-1
# neighbors → false positives). Cap iterations to avoid pathological source sets.

_MIN_GARBLED_WORD_LEN = 5
_MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE = 20000  # cap; larger sources skip the check


def _edit_distance_one_neighbors(word: str) -> set:
    """Return the set of all words within edit distance 1 of ``word``.

    Includes insertions, deletions, and substitutions of a single character.
    Used to check if a summary word is a garbled form of a source word.
    """
    neighbors = set()
    # Deletions (remove 1 char): "emergs" → "emerg", "emegs", "emers", ...
    for i in range(len(word)):
        neighbors.add(word[:i] + word[i + 1:])
    # Insertions (add 1 char): "emergs" → "aemergs", "bemergs", ...
    # Limited to common letters to bound the set size.
    for i in range(len(word) + 1):
        for c in "abcdefghijklmnopqrstuvwxyz":
            neighbors.add(word[:i] + c + word[i:])
    # Substitutions (replace 1 char): "emergs" → "amergs", "bmergs", ...
    for i in range(len(word)):
        for c in "abcdefghijklmnopqrstuvwxyz":
            if c != word[i]:
                neighbors.add(word[:i] + c + word[i + 1:])
    return neighbors


def _is_legitimate_inflection_pair(summary_word: str, source_word: str) -> bool:
    """V18.19.2.5 (tune): Is ``summary_word`` a legitimate English form of ``source_word``?

    The V18.19.2.4 audit found 16 false positives from detect_dropped_letter_garble:
    the detector flagged words like "author" (matching source "authors"), "clarifies"
    (matching "clarified"), "surveys" (matching "survey"), "paths" (matching "path") —
    all legitimate English inflections, NOT garbled tokens.

    The original "emergs"→"emerges" true positive is a NON-word ("emergs" is not
    real English). The false positives are all REAL English words that happen to be
    edit-distance-1 from a different source word via standard morphology.

    This helper checks if the edit-distance-1 relationship is a legitimate English
    morphological transformation (the summary word is an inflection/derivation of
    the source word, or vice versa). Returns True if it is → the flag should be
    suppressed (it's a false positive).

    Checks (any True → legitimate):
      1. The summary word ends with a standard suffix that, when stripped, yields
         the source word (e.g. "authors" - "s" = "author"). Covers plurals,
         verb conjugations, adverbs, adjectives.
      2. The source word ends with a standard suffix that, when stripped, yields
         the summary word (e.g. "clarified" - "d" = "clarifie" ≈ "clarifies" via
         further 'e'→'es' morph). Covers the reverse direction.
      3. The two words differ only by a trailing 's'/'es' (plural/3rd-person).
      4. The two words differ only by a trailing 'd'/'ed' (past tense).

    This is source-grounded morphology (grammatical structure, not a content
    dictionary — same exemption as _STRUCTURAL_STOPWORDS under the V18.15.3.2
    "no hand-curated word lists" constraint, which targets CONTENT dictionaries).
    """
    sw = summary_word.lower()
    src = source_word.lower()
    if sw == src:
        return True  # identical (shouldn't happen — caller already checked)
    # 1. summary word = source word + suffix (e.g. "authors" = "author" + "s")
    for suffix in _LEGIT_SUFFIXES:
        if sw == src + suffix:
            return True
    # 2. source word = summary word + suffix (e.g. "clarified" = "clarifie" + "d"
    #    — but "clarifie" isn't "clarifies"; this catches "drawn" vs "draw" where
    #    "drawn" = "draw" + "n"... actually "n" isn't a suffix. Let me handle
    #    the specific past-participle/past-tense cases below.)
    for suffix in _LEGIT_SUFFIXES:
        if src == sw + suffix:
            return True
    # 3. Trailing-s difference (plural / 3rd person singular):
    #    author↔authors, path↔paths, open↔opens, turn↔turns, split↔splits,
    #    survey↔surveys, attempt↔attempts
    if (len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == 's'):
        return True
    if (len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == 's'):
        return True
    # 4. Trailing-d/ed difference (past tense):
    #    describe↔described, clarify↔clarified, consolidate↔consolidated,
    #    emerge↔emerged (note: "emergs"≠"emerged" — emergs is a non-word, caught below)
    #    BUT "emergs" → "emerges" is NOT past tense (no d/ed) → still flagged. ✓
    if (len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == 'd'):
        return True
    if (len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == 'd'):
        return True
    if (len(sw) == len(src) + 2 and sw.startswith(src) and sw[-2:] == 'ed'):
        return True
    if (len(src) == len(sw) + 2 and src.startswith(sw) and src[-2:] == 'ed'):
        return True
    # 5. Past participle -n (draw↔drawn, show↔shown). Rare but legitimate.
    if (len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == 'n'):
        return True
    if (len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == 'n'):
        return True
    # 6. V18.19.2.5: -y / -ies / -ied verb-conjugation + noun-plural transformations.
    #    clarifY↔clarifieS, clarifY↔clarifieD, identitY↔identitIES.
    def _y_to_ies(w: str) -> str:
        if w.endswith('y') and len(w) >= 3:
            return w[:-1] + 'ies'
        return w
    def _y_to_ied(w: str) -> str:
        if w.endswith('y') and len(w) >= 3:
            return w[:-1] + 'ied'
        return w
    def _ies_to_y(w: str) -> str:
        if w.endswith('ies') and len(w) >= 4:
            return w[:-3] + 'y'
        return w
    def _ied_to_y(w: str) -> str:
        if w.endswith('ied') and len(w) >= 4:
            return w[:-3] + 'y'
        return w
    for transform in (_y_to_ies, _y_to_ied, _ies_to_y, _ied_to_y):
        if transform(sw) == src or transform(src) == sw:
            return True
    # 8. V18.20.3.5 (audit v182034, user rule: no chapter-derived word
    # lists): Greek/Latin -is <-> -es plural pair. "basis"->"bases",
    # "analysis"->"analyses", "crisis"->"crises", "thesis"->"theses",
    # "diagnosis"->"diagnoses" — the singular ends in "is", the plural in
    # "es", and the stems are IDENTICAL. This is a general morphological
    # rule of English (a closed grammatical system), not a content word
    # list: it covers EVERY -is noun in any chapter, which is what
#    replaces the V18.20.3.4 hand-added entries (learned from ONE
    # "bases" were learned from ONE book's false positives — exactly the
    # chapter-specific tuning the user banned).
    if (
        sw.endswith('is') and src.endswith('es')
        and sw[:-2] == src[:-2] and len(sw) - 2 >= 3
    ):
        return True
    if (
        src.endswith('is') and sw.endswith('es')
        and src[:-2] == sw[:-2] and len(src) - 2 >= 3
    ):
        return True
    # 10. V18.20.3.5: -is discipline vs -ts agent-plural tail swap:
# "analysis" <-> "analysts" (equal length, identical prefix, ONLY the
    # (equal length, identical prefix, ONLY the last two characters differ
    # as is<->ts). The Greek-derived agent-noun pattern. This is the pair
# the V18.20.3.4 hand-added stoplist entry was hand-blocking —
    # without a rule here the unique-candidate auto-repair would CORRUPT
# "the analysis of society" into "the analysts of
    # society". Structural: prefix identity + tail is<->ts, no word list;
    # requires length >= 8 so it covers analysis/analysts while keeping
    # shorter coincidental pairs flagged.
    if (
        len(sw) == len(src) and len(sw) >= 8
        and sw[:-2] == src[:-2]
        and {sw[-2:], src[-2:]} == {'is', 'ts'}
    ):
        return True
    # 9. V18.20.3.5: final-character inflection swap. Two words of EQUAL
    # length that share everything except the LAST character, where both
    # final characters are standard inflection endings (s/d/t/n —
    # 3rd-person, past, participle; 'e' deliberately EXCLUDED: the s<->e
    # swap is the bogus 3rd-person class "emergs"<->"emerge", the
    # detector's original true positive, and no real inflection pair
    # needs it): "meant" <-> "means" (irregular mean paradigm),
    # "notes" <-> "noted", "states" <-> "stated". Garbles of the dropped-letter class are
#    edits at ARBITRARY positions (a garbled name differs at one position
    # 4 of 6), so restricting this blessing to the FINAL position keeps
    # the true-positive garble class flagged while covering the irregular
    # verb pairs that forced the old hand-list entries.
    _FINAL_INFLECTION_CHARS = frozenset('sdtn')
    if (
        len(sw) == len(src) and len(sw) >= 5
        and sw[:-1] == src[:-1]
        and sw[-1] in _FINAL_INFLECTION_CHARS
        and src[-1] in _FINAL_INFLECTION_CHARS
        and sw[-1] != src[-1]
    ):
        return True
    # 7. V18.19.2.5: shared-stem inflections — TIGHTENED. Two words that share
    #    a common stem (>=4 chars) AND differ ONLY by swapping one standard
    #    inflectional suffix for ANOTHER standard inflectional suffix (both
    #    suffixes in the set, equal length) are legitimate conjugation pairs.
    #    Examples:
    #      clarifIES ↔ clarifIED (stem "clarif", swap "ies"↔"ied" — both 3 chars)
    #      consolidatES ↔ consolidatED (stem "consolidat", swap "es"↔"ed" — both 2)
    #    But NOT:
    #      emergS ↔ emergES (stem "emerg", "s"↔"es" — but "emergs" is a non-word;
    #        the "s" here is a dropped letter, not a plural suffix. The signal:
    #        "emergs" stripped of "s" = "emerg" (4 chars), "emerges" stripped of
    #        "es" = "emerg" (4 chars) — stems match. BUT "s" and "es" differ in
    #        length by 1, and the shorter word "emergs" is not a real inflection
    #        of "emerg" (the 3rd-person is "emerges", not "emergs"). So we require
    #        the suffixes to be EQUAL length — a true conjugation swap, not a
    #        dropped-letter case.)
    _INFLECTION_SUFFIXES_BY_LEN = {
        3: ('ies', 'ied', 'ing', 'est', 'ers', 'ment', 'tion', 'ness', 'able',
            'ible', 'ous', 'ive', 'ful', 'less'),
        2: ('es', 'ed', 'er', 'al', 'ly', 'ic', 'ity'),
        1: ('s', 'd'),
    }
    for suf_len in (3, 2, 1):
        suffixes = _INFLECTION_SUFFIXES_BY_LEN[suf_len]
        if sw.endswith(suffixes) and src.endswith(suffixes):
            sw_stem = sw[:-suf_len] if len(sw) > suf_len else sw
            src_stem = src[:-suf_len] if len(src) > suf_len else src
            if (sw_stem == src_stem and len(sw_stem) >= 4
                    and len(sw) == len(src)  # equal length → true suffix swap
                    and sw[-suf_len:] != src[-suf_len:]):  # different suffixes
                return True
    return False


def detect_dropped_letter_garble(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V18.19.2.3 (Audit Fix 5): Detect single-character garbled tokens.
    V18.19.2.5 (tune): Suppress false positives on legitimate English inflections.

    Catches words like "emergs" (should be "emerges"), "identiy" (should be
    "identity"), "Dukhaim" (should be "AuthorY") — words that are NOT in the
    source but become a source word after a single-character edit (insert /
    delete / substitute).

    V18.19.2.5 tuning (per the V18.19.2.4 audit): the V18.19.2.3 detector produced
    16 false positives — flagging legitimate English words ("author", "clarifies",
    "surveys", "paths", "seven") that happen to be edit-distance-1 from a different
    source word. The fix: suppress the flag if the edit-distance-1 relationship is
    a legitimate English morphological transformation (the summary word is an
    inflection/derivation of the source word via a standard suffix). This keeps
    the true positive ("emergs"→"emerges" — "emergs" is a non-word) while dropping
    the 16 false positives (all real English words).

    Source-grounded: no hand-curated content word list (per the V18.15.3.2
    constraint). The morphological suffix set is grammatical structure, not a
    content dictionary — same exemption as _STRUCTURAL_STOPWORDS.

    A word is flagged only if:
      1. It's >= 5 chars (shorter words have too many false-positive neighbors).
      2. It's NOT in the source text (already-legitimate source words are exempt).
      3. A single-character edit makes it match a source word.
      4. The edit-distance-1 relationship is NOT a legitimate English inflection
         (V18.19.2.5: _is_legitimate_inflection_pair check).
      5. It's not in the _STRUCTURAL_STOPWORDS exempt set.

    V18.20.3.4 (RC-3, audit v182033): UNAMBIGUOUS repairs are now AUTO-FIXED.
    When exactly ONE source word is at edit distance 1 (the "emergs"→
    "emerges" class — the V18.20.3.3 run flagged it twice and shipped the
    typo both times), the token is replaced in the returned text and the
    issue is severity="fix". Multiple candidates remain flag-only (the
    reconstruction is ambiguous: "emergs" could be "emerges" or "emerge";
    the human/LLM decides downstream).

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the source chapter text (the only allowed dictionary).

    Returns:
        ``(text, issues)``. Text carries the unambiguous auto-repairs
        (V18.20.3.4 RC-3); ambiguous garbles leave it unchanged.
    """
    issues: list[Issue] = []
    # V18.20.3.4 (RC-3): queued (garble, repair) pairs — applied after
    # the scan loop. Initialized OUTSIDE the try so a crash anywhere in
    # the scan still leaves the post-loop application valid.
    _repairs: list = []
    if not text or not source_text:
        return text, issues
    try:
        # V18.20.2.0 (SWOT A24): accept the precomputed source word-set from
        # run_post_checks (was rebuilt per bullet/exec/thorough call);
        # lazy-build when omitted.
        if source_words is None:
            source_words = set(re.findall(r'\b[a-z]+\b', source_text.lower()))
        if len(source_words) > _MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE:
            # Skip for very large sources (perf guard — rare; the 9120-token
            # trust-ground produces ~2500 unique words, well under the cap).
            return text, issues
        # Pre-build a set of source words >= _MIN_GARBLED_WORD_LEN - 1 (so a
        # deletion could land in range). This bounds the neighbor-checking.
        candidate_sources = {w for w in source_words if len(w) >= _MIN_GARBLED_WORD_LEN - 1}
        if not candidate_sources:
            return text, issues
        seen: set = set()
        for m in re.finditer(r'\b[a-zA-Z]{%d,}\b' % _MIN_GARBLED_WORD_LEN, text):
            word = m.group(0).lower()
            if word in seen:
                continue
            seen.add(word)
            # Skip if the word IS in the source (legitimate).
            if word in source_words:
                continue
            if word in _STRUCTURAL_STOPWORDS:
                continue
            # V18.20.3.2 (audit N7 / P2-a): common-English-word stoplist. The
            # V18.20.3.1 run false-flagged 8 ordinary words ('moving', 'seven',
            # 'stages', 'clarify', 'fusing', 'raising', 'identifies') that are
            # real English merely absent from that source. A common word is
            # never a garble candidate regardless of its edit-distance-1
            # neighbors (latent-corruption guard: a future auto-fix would
            # otherwise turn 'moving through' into 'loving').
            if _common_word_stem_in_stoplist(word):
                continue
            # Check if any edit-distance-1 neighbor is a source word.
            neighbors = _edit_distance_one_neighbors(word)
            matching_source = candidate_sources & neighbors
            if not matching_source:
                continue
            # V18.19.2.5 (tune): suppress false positives on legitimate English
            # inflections. If the edit-distance-1 relationship is a standard
            # morphological transformation (plural, verb conjugation, etc.),
            # the summary word is a real English word — NOT garbled. Only flag
            # if NONE of the matching source words are legitimate inflection
            # partners (i.e. the summary word is a true non-word like "emergs").
            non_inflection_matches = {
                src_w for src_w in matching_source
                if not _is_legitimate_inflection_pair(word, src_w)
            }
            if not non_inflection_matches:
                # All edit-distance-1 matches are legitimate inflections →
                # the summary word is a real English word. Suppress the flag.
                # (e.g. "author" matches "authors" via plural — suppress.)
                continue
            # V18.20.3.4 (RC-3, audit v182033): UNAMBIGUOUS dropped-letter
            # tokens are now AUTO-REPAIRED instead of flag-only. The
            # V18.20.3.3 run flagged `[dropped_letter/flag]` twice for
            # garbled token (bullet + thorough; audit F7) and shipped the
            # typo both times — the reconstruction was never in
            # doubt: it is the ONLY source token at edit distance 1. Rule:
            # exactly one non-inflection candidate → replace (severity=fix);
            # multiple candidates → keep flag-only (the reconstruction is
            # ambiguous; the human/LLM decides downstream). Case is
            # preserved: a capitalized garble gets a capitalized repair.
            if len(non_inflection_matches) == 1:
                _repair = next(iter(non_inflection_matches))
                _orig_tok = m.group(0)
                if _orig_tok[:1].isupper():
                    _repair_tok = _repair.capitalize()
                else:
                    _repair_tok = _repair
                # V18.20.3.5 (audit v182034, user rule: no chapter-derived
                # word lists): POSITION-0 INFLECTED-FORM GUARD on the
                # auto-repair. The residual false-repair class after the
                # rule-8/rule-9 morphology coverage: a real English word
                # that is edit-distance-1 from a DIFFERENT source word via
                # a LEADING-character edit — "elated" vs "related",
                # "review" vs "preview", "version" vs "aversion". These
                # pairs share no morphology, so only lexical knowledge
                # separates them; without a lexicon, the structural
                # proxy is: a token that DECOMPOSES as stem + standard
                # inflection suffix ("elat"+"ed", "review" has none) looks
                # like a real inflected English form and is NOT
                # auto-repaired (flag-only, human decides). Non-decomposing
                # tokens (the audit's true positive) still
                # auto-repair. Purely structural, no word list.
                _pos0_edit = (word == _repair[1:] or _repair == word[1:])
                _looks_inflected = any(
                    word.endswith(_suf) and len(word) - len(_suf) >= 3
                    for _suf in _COMMON_SUFFIXES
                )
                if _pos0_edit and _looks_inflected:
                    issues.append(Issue(
                        detector="dropped_letter",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"possible garble: '{_orig_tok}' is edit-distance-1 "
                            f"(leading-character edit) from source word "
                            f"'{_repair}' — but '{_orig_tok}' decomposes as a "
                            f"stem + standard English suffix, so it may be a "
                            f"real word unrelated to '{_repair}' (the "
                            f"'elated'/'related' class). NOT auto-repaired; "
                            f"verify manually."
                        ),
                    ))
                    continue
                issues.append(Issue(
                    detector="dropped_letter",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"auto-repaired garbled token: '{_orig_tok}' → "
                        f"'{_repair_tok}' (the unique source word at edit "
                        f"distance 1 — V18.20.3.4 RC-3, the 'emergs'→"
                        f"'emerges' class)"
                    ),
                ))
                # Queue the repair (word-boundary-scoped so a substring
                # token can never be partially rewritten). Applied AFTER
                # the scan loop so the finditer match positions stay valid
                # for subsequent issues' snippets.
                _repairs.append((_orig_tok, _repair_tok))
                seen.add(_repair)
                continue
            _suggestion = sorted(non_inflection_matches)[0]
            issues.append(Issue(
                detector="dropped_letter",
                severity="flag",
                field=field_label,
                snippet=_snippet(text, m.start()),
                detail=(
                    f"likely garbled token: '{m.group(0)}' is not in the source "
                    f"and is not a legitimate inflection of any source word, "
                    f"but is edit-distance-1 from '{_suggestion}' "
                    f"(single-char insert/delete/substitute). "
                    f"V18.19.2.5: caught 'emergs'→'emerges' (non-word) class."
                ),
            ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="dropped_letter", severity="flag", field=field_label,
            snippet=text[:60], detail=f"dropped-letter check crashed: {e!r}",
        ))
    # V18.20.3.4 (RC-3): apply the queued unambiguous repairs now that the
    # scan is done (match positions are no longer needed). Word-boundary
    # scoping keeps a substring token from being partially rewritten.
    for _orig_tok, _repair_tok in _repairs:
        try:
            text = re.sub(
                r'(?<!\w)' + re.escape(_orig_tok) + r'(?!\w)',
                _repair_tok.replace('\\', '\\\\'),
                text,
            )
        except re.error:
            pass  # defensive — a repair regex failure must not lose the flag
    return text, issues


# Tiny structural-stopword set (function words only — NOT a content dictionary).
# Exempt from the "no hand-curated word lists" constraint (V18.15.3.2) because
# these are grammatical glue, not content claims. Keeps the detector from
# flagging "because"/"therefore"/"however" on chapters that don't happen to
# contain them verbatim.
_STRUCTURAL_STOPWORDS = frozenset({
    "because", "therefore", "however", "moreover", "furthermore", "nevertheless",
    "thus", "hence", "although", "though", "whereas", "while", "unless",
    "between", "through", "during", "before", "after", "since", "until",
    "against", "without", "within", "among", "across", "behind", "beyond",
    "already", "always", "never", "often", "sometimes", "usually",
    # V18.20.3.4 (RC-3 hardening, found while verifying the auto-repair):
    # high-frequency function/frequency words that are edit-distance-1 from
    # a DIFFERENT common word ("thorough"≈"through", "from"≈"form",
    # "their"≈"there"). The V18.20.3.4 auto-repair makes the stoplist
    # safety-critical (a missed common word could be "repaired" into its
    # neighbor), so the preposition/determiner/adverb core of English is
    # exempted here — grammatical glue, not content claims.
    "from", "than", "then", "there", "their", "about", "into", "upon",
    "over", "under", "again", "almost", "perhaps", "quite", "rather",
    "still", "just", "even", "also", "both", "either", "neither",
    "instead", "indeed", "somewhat", "thorough",
})

# V18.20.3.2 (audit N7 / P2-a): common-English-word stoplist for the
# dropped-letter detector. The V18.20.3.1 run false-flagged 8 ORDINARY words
# ('identifies', 'fusing', 'raising', 'clarify' ×2, 'moving', 'seven',
# 'stages') — legitimate English absent from that particular source but
# edit-distance-1 from a DIFFERENT source word ('seven'→'seen',
# 'stages'→'states', 'clarify'→'clarity', 'moving'→'loving', …). The
# V18.19.2.5 inflection check only suppresses morphological pairs
# (author→authors), not unrelated real words. This stoplist covers the
# high-frequency English lexicon (base forms; inflections are checked via
# suffix-stripping below). Same exemption class as _STRUCTURAL_STOPWORDS:
# grammatical/lexical structure, not content claims — and it only ever
# SUPPRESSES flags (latent-corruption risk: any future auto-fix built on
# this detector would otherwise turn "moving through" into "loving").
_COMMON_ENGLISH_WORDS = frozenset({
    # high-frequency verbs (base forms; inflections stripped before lookup)
    "make", "take", "give", "get", "put", "keep", "find", "hold", "come",
    "go", "see", "look", "know", "think", "say", "tell", "use", "show",
    "move", "live", "work", "call", "try", "ask", "need", "feel", "become",
    "leave", "mean", "meet", "run", "help", "talk", "turn", "start",
    "bring", "lose", "pay", "sit", "stand", "hear", "play", "grow",
    "raise", "rise", "fall", "fell", "pass", "cross", "cut", "read",
    "write", "speak", "spoke", "learn", "teach", "taught", "buy", "sell",
    "send", "build", "break", "broke", "share", "carry", "catch", "caught",
    "choose", "chose", "deal", "draw", "drew", "drive", "drove", "eat",
    "feed", "fill", "fly", "flew", "follow",
    "forget", "hang", "happen", "hit", "hope", "join", "jump",
    "kill", "land", "laugh", "lead", "led", "let", "lie", "lay", "light",
    "love", "marry", "match", "miss", "mix", "open", "close",
    "order", "own", "pick", "plan", "point", "press", "prove", "pull",
    "push", "reach", "realize", "remain", "remember", "repeat", "reply",
    "report", "require", "rest", "return", "ride", "ring", "save", "seem", "serve", "set", "settle", "shake", "shine",
    "shoot", "shout", "sing", "sang", "sleep", "smell", "smile", "spend",
    "spread", "stay", "step", "stick", "stop", "study", "support",
    "survive", "swim", "swing", "taste", "tear", "thank", "throw", "threw", "touch", "train", "travel", "treat",
    "trust", "understand", "understood", "visit", "wait", "wake", "walk",
    "want", "warm", "wash", "watch", "wear", "wore", "win", "won", "wish",
    "wonder", "worry",
    # common verbs that appeared as real FPs in the V18.20.3.1 audit
    "clarify", "fuse", "identify", "argue", "assert", "note", "observe",
    "recognize", "suggest", "emphasize", "highlight", "distinguish",
    "examine", "explore", "trace", "define", "view", "consider",
    # numbers (edit-distance-1 traps: seven→seen, nine→none)
    "seven", "eight", "nine", "three", "four", "five", "six", "ten",
    "eleven", "twelve", "forty", "fifty", "sixty", "seventy", "eighty",
    "ninety", "hundred", "thousand", "million", "none", "one", "two",
    # high-frequency nouns/adjectives/adverbs
    "stage", "state", "case", "place", "part", "fact", "force",
    "form", "kind", "type", "sort", "field", "group", "level", "sense", "side", "thing", "time", "value", "world", "area",
    "body", "book", "child", "city", "class", "color", "day", "door",
    "east", "end", "even", "example", "eye", "face", "family",
    "father", "feet", "figure", "girl", "hand", "head", "hour", "idea",
    "inch", "interest", "job", "king", "lady", "language", "law",
    "letter", "line", "list", "man", "matter", "may", "method", "mind",
    "minute", "moment", "money", "month", "mother", "mouth", "music",
    "name", "nation", "nature", "night", "north", "number",
    "object", "office", "page", "paper", "person", "picture", "piece",
    "plant", "power", "price", "problem", "question",
    "race", "rate", "reason", "record", "research", "result", "right",
    "river", "road", "rock", "room", "rule", "school", "science", "season",
    "second", "sentence", "series", "service", "shape", "ship", "short",
    "sound", "south", "space", "special", "story", "street", "student",
    "subject", "table", "teacher", "test", "theory", "thought",
    "title", "today", "topic", "town", "trade", "true", "unit", "voice",
    "war", "water", "way", "week", "west", "wheel", "woman", "word",
    "young",
    # V18.20.3.4 (RC-5a, audit v182033) → V18.20.3.5 POLICY CHANGE (user
    # rule: "never add a word list of this chapter — solve problems
    # fundamentally"): the .3.4 entries added after auditing ONE book's
    # false positives ("analysis", "elated", "argues", "asserts",
    # "noted", "means") are REMOVED. Their FP classes are now covered by
    # the general morphological rules added to
    # _is_legitimate_inflection_pair (rule 8: Greek -is/-es plurals covers
    # -is plurals, basis/bases, analysis/analyses in ANY
    # chapter; rule 9: final-char inflection swap covers meant/means); the
    # bare-inflection entries are redundant with the suffix-stripping
    # lookup below (argues→argue, asserts→assert, noted→note, means→mean
    # are all in the base list). Kept entries are top-3000 general English
    # (analysis, analyst, base, basis, mean, meant) that belong in ANY
    # English lexicon, independent of any book. POLICY: this set accepts
    # ONLY general-English core vocabulary and grammatical structure —
    # never words learned from a specific chapter's audit.
    "analysis", "analyst", "base", "basis", "meant",
})

# Common English inflection suffixes — stripped before the stoplist lookup
# ("moving" → "move" ✓, "stages" → "stage" ✓, "identifies" → "identify" ✓).
# V18.20.3.2 fix: -ing strips also try stem+"e" (English drops the 'e'
# before -ing: move→moving, fuse→fusing) — the naive strip gave "mov"/"fus"
# and the FP suppression missed exactly the two audit words.
_COMMON_SUFFIXES = (
    "ies", "ied", "ing", "est", "ers", "es", "ed", "er", "ly", "s", "d",
)


def _common_word_stem_in_stoplist(word: str) -> bool:
    """V18.20.3.2 (P2-a): True when ``word`` (lowercase) is a common English
    word — either directly in ``_COMMON_ENGLISH_WORDS`` or its base form
    (after stripping one common inflection suffix) is."""
    if word in _COMMON_ENGLISH_WORDS:
        return True
    for suf in _COMMON_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            stem = word[: -len(suf)]
            if suf == "ies" or suf == "ied":
                stem = word[: -len(suf)] + "y"
            if stem in _COMMON_ENGLISH_WORDS:
                return True
            # -ing / -ed restore the dropped 'e' (move→moving, fuse→fusing,
            # raise→raised).
            if suf == "ing" or suf == "ed":
                if (stem + "e") in _COMMON_ENGLISH_WORDS:
                    return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.19 Improvement 3 — Pronoun mismatch detector
# ═══════════════════════════════════════════════════════════════════════════

# Catches "AuthorO... He stressed" when the source uses "she" for AuthorO.
# A gender-pronoun attribution error — the model assigned the wrong pronoun
# to a named author.


_PRONOUN_MAP = {
    'he': 'she', 'she': 'he',
    'his': 'her', 'her': 'his',
    'him': 'her', 'himself': 'herself',
}

_PRONOUN_RE = re.compile(
    r'\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\b'
    r'(?:.{0,200}?)\b(he|she|his|her)\b',
    re.IGNORECASE | re.DOTALL,
)



def detect_pronoun_mismatch(
    text: str,
    source_text: str,
    field_label: str,
    source_lower: str | None = None,
    source_authors: list[str] | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.19: Detect gender-pronoun mismatches for named authors.

    Finds ``[AuthorName] ... [he/she/his/her]`` in the summary, then checks
    what pronoun the source uses for that author. If they differ → FLAG.

    Book-agnostic: pronoun consistency is universal (any discipline uses
    he/she for named individuals). No domain-specific terms.

    V18.20.3.1 (real-rig audit D2): two honesty fixes.

    1. **Author gating.** The V18.20.3.0 the rig-test book run showed the
       author-extraction regex (any capitalized word before a pronoun)
       captured ordinary nouns — 'views', 'fails', 'technical',
       'differentiation' — producing 5 bogus flags. When ``source_authors``
       (the citation-extracted surname list) is available and non-empty,
       only candidate authors actually cited in the source are checked.

    2. **No auto-rewrite.** The V18.2.28 "auto-fix" re.sub block was DEAD
       CODE — all three call sites discard the returned text (``_, issues =
       ...``) — while the Issue detail claimed ``Auto-fixed to '…'``, so the
       conversion log LIED about fixes that never landed. Removing the
       block makes the function match its docstring (flag-only, text
       UNCHANGED). This is also the SAFE choice: the source's nearest
       pronoun can belong to a DIFFERENT author (the run's 'she→his'
       "fix" for AuthorA — a woman — would have corrupted a
       correct bullet had it been applied).

    Args:
        text: the summary text.
        source_text: the chapter source text.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_lower: precomputed lowercased source (optional).
        source_authors: citation-extracted author surnames (optional gate).

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only — the correct
        pronoun requires knowing the author's gender).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        # V18.20.3.1 (D2): author gate — only source-cited authors are
        # eligible for the pronoun check (kills the 'views'/'fails' class).
        _author_set = {a.lower() for a in (source_authors or []) if a}
        _author_last = {a.split()[-1].lower() for a in (source_authors or []) if a}
        _gate_on = bool(_author_set)
        # V18.20.2.0 (SWOT A24): accept the precomputed 200k-char lowercased
        # source (was rebuilt per bullet); lazy-build when omitted.
        src_lower = source_lower if source_lower is not None else source_text.lower()[:200000]
        seen = set()
        for m in list(_PRONOUN_RE.finditer(text)):
            author = m.group(1).strip()
            pronoun = m.group(2).lower()
            if len(author) < 3:
                continue
            # Skip non-name stopwords (same list as validate_years).
            if author.split()[0].lower() in {
                "in", "by", "the", "a", "an", "as", "at", "to", "of",
                "and", "or", "for", "with", "from", "that", "this",
                "while", "when", "where", "later", "then", "early",
                "chapter", "figure", "table", "page", "section",
            }:
                continue
            author_lower = author.lower()
            if author_lower not in src_lower:
                continue  # author not in source at all
            # V18.20.3.1 (D2): author must be a source-cited author when the
            # citation-extracted list is available.
            if _gate_on and (
                author_lower not in _author_set
                and author.split()[-1].lower() not in _author_last
            ):
                continue
            key = (author_lower, pronoun)
            if key in seen:
                continue
            seen.add(key)
            # V18.20.3.7 (audit v182036, recurring pronoun-flag class):
            # antecedent-adjacency gate. The V18.20.3.6 run flagged
            # bullet[25] ("AuthorB described that if a [mother] ... she
            # ...") — there the 'she' almost certainly refers to the
            # intervening NOUN ("a mother"), not to AuthorB: a
            # determiner+noun phrase immediately before the pronoun is a
            # nearer antecedent candidate than the author name up to 200
            # chars away. When such a noun phrase sits within the 2 words
            # preceding the pronoun, the pronoun is NOT structurally bound
            # to the author — skip the flag (advisory noise reduction; it
            # cannot create wrong output). Direct-binding cases ("AuthorH: Her
            # works ...", "Name — he argued ...") have no intervening
            # determiner+noun and still flag. Closed-class English
            # determiners only — content-agnostic by construction.
            _between = text[m.end(1):m.start(2)]
            # Clause-scoped: a sentence boundary (. ! ? ;) resets the
            # antecedent — "AuthorO (1958) proposed a continuum. He
            # stressed ..." binds He→AuthorO (a TRUE positive the V18.2.19
            # tests pin). Only a noun phrase in the SAME final clause as the
            # pronoun (the .3.6 bullet[25] shape: "... if a good-enough
            # mother fails ..., she produces ...") suppresses the flag.
            _final_clause = re.split(r"[.!?;]\s*", _between)[-1] if _between else ""
            _bt_tokens = [
                _w.strip(",;:.!?\u2014\u201c\u201d'\"()") for _w in _final_clause.split()
            ]
            _bt_tokens = [_w for _w in _bt_tokens if _w]
            _DETERMINERS = {
                "a", "an", "the", "this", "that", "these", "those",
                "his", "her", "their", "its", "each", "every",
            }
            _has_np_antecedent = False
            _tail = _bt_tokens[-3:] if _bt_tokens else []
            for _di in range(len(_tail) - 1):
                if _tail[_di].lower() in _DETERMINERS and _tail[_di + 1][:1].isalpha():
                    _has_np_antecedent = True
                    break
            if _has_np_antecedent:
                continue
            # Find what pronoun the source uses for this author.
            # V18.2.19: Use DOTALL + .{0,200}? (not [^.!]) so we can match
            # across sentence boundaries — the pronoun may be in the NEXT
            # sentence after the author name.
            src_pronoun = None
            for src_m in re.finditer(
                rf'\b{re.escape(author)}\b.{{0,200}}?\b(he|she|his|her)\b',
                source_text, re.IGNORECASE | re.DOTALL,
            ):
                src_pronoun = src_m.group(1).lower()
                break
            if src_pronoun and src_pronoun != pronoun:
                # Check if they're actually different gender (he vs she, his vs her)
                # vs just different forms (he vs his — same gender).
                _sum_gender = 'm' if pronoun in ('he', 'his', 'him', 'himself') else 'f'
                _src_gender = 'm' if src_pronoun in ('he', 'his', 'him', 'himself') else 'f'
                if _sum_gender != _src_gender:
                    # V18.20.3.1 (D2): flag-only — the V18.2.28 auto-fix
                    # re.sub block was dead code (all call sites discard the
                    # returned text) and its Issue detail falsely claimed
                    # "Auto-fixed". Removed; the message is now honest. No
                    # auto-rewrite is also the SAFE choice: the source's
                    # nearest pronoun can belong to a different author.
                    issues.append(Issue(
                        detector="pronoun",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"pronoun mismatch: summary uses '{pronoun}' for "
                            f"'{author}' but source uses '{src_pronoun}' near "
                            f"that name. Flagged for review (no auto-rewrite — "
                            f"the source's nearby pronoun may belong to a "
                            f"different author)."
                        ),
                    ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="pronoun", severity="flag", field=field_label,
            snippet=text[:60], detail=f"pronoun check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.17 Fix 8 — Internal consistency validator (deterministic + book-agnostic)
# ═══════════════════════════════════════════════════════════════════════════

# Phrases where the summary claims something is "missing"/"not discussed".
# These are red flags when the concept actually DOES appear in the source.

_MISSING_CLAIM_RE = re.compile(
    r'\b(?:'
    r'not\s+mention(?:ed|s)?|not\s+discuss(?:ed|es)?|not\s+address(?:ed|es)?|'
    r'not\s+cover(?:ed|s)?|not\s+explor(?:ed|es)?|not\s+examin(?:ed|es)?|'
    r'not\s+includ(?:ed|es)?|not\s+present(?:ed|s)?|'
    r'absent|omitted|missing|excluded|overlooked|ignored'
    r')\b',
    re.IGNORECASE,
)



def detect_inconsistency(
    text: str,
    source_text: str,
    field_label: str,
    source_lower: str | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.17 Fix 8: Detect "not mentioned" claims that contradict the source.

    Scans the summary for phrases like "not mentioned", "not discussed",
    "absent", "omitted", then extracts the concept that follows and checks
    if that concept actually appears in the source. If it does, the summary
    is making a false "missing" claim → FLAG.

    Book-agnostic: "not mentioned" + concept-search works on any content.
    No domain-specific terms.

    Example:
        Summary: "The chapter does not discuss the role of feedback loops."
        Source: actually contains "feedback loops" → FLAG (false "missing" claim)

    Args:
        text: the summary text.
        source_text: the chapter source text.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        # V18.20.2.0 (SWOT A24): accept the precomputed 200k-char lowercased
        # source (was rebuilt per bullet); lazy-build when omitted.
        src_lower = source_lower if source_lower is not None else source_text.lower()[:200000]
        for m in list(_MISSING_CLAIM_RE.finditer(text)):
            # Extract the concept that follows the "not mentioned" phrase.
            # Take up to 80 chars after the phrase, ending at punctuation.
            after = text[m.end():m.end() + 80]
            # Cut at the first sentence boundary.
            cut = re.search(r'[.!?;,\n]|$', after)
            concept = after[:cut.start()].strip() if cut else after.strip()
            # Clean: remove leading articles/prepositions + trailing spaces.
            concept = re.sub(r'^(?:the\s+|a\s+|an\s+|of\s+|to\s+|in\s+)', '', concept, flags=re.IGNORECASE).strip()
            if len(concept) < 3:
                continue  # nothing to check

            # Search the source for the concept's key words.
            # Extract content words (≥4 chars, alphabetic) from the concept.
            concept_words = [w for w in re.findall(r'[a-zA-Z]{4,}', concept)
                             if w.lower() not in {
                                 'that', 'this', 'with', 'from', 'have',
                                 'been', 'were', 'they', 'their', 'which',
                                 'would', 'could', 'should', 'about',
                                 'into', 'than', 'then', 'them',
                             }]
            if not concept_words:
                continue

            # Check if ≥50% of the concept's content words appear in source.
            found = sum(1 for w in concept_words if w.lower() in src_lower)
            ratio = found / len(concept_words) if concept_words else 0
            if ratio >= 0.50:
                issues.append(Issue(
                    detector="consistency",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"false 'missing' claim: '{m.group(0)}' followed by "
                        f"'{concept[:40]}' — but {found}/{len(concept_words)} "
                        f"of the concept's words DO appear in the source "
                        f"(summary may falsely claim it's missing)"
                    ),
                ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="consistency", severity="flag", field=field_label,
            snippet=text[:60], detail=f"consistency check crashed: {e!r}",
        ))
    return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# Coordinator
# ═══════════════════════════════════════════════════════════════════════════


_AUTHOR_RE = re.compile(
    r'\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\s*\((\d{4}[a-z]?)\)',
)



def detect_exec_bullet_inconsistency(
    executive_summary: str,
    bullet_points: list[str],
    field_label: str = "exec",
) -> list[Issue]:
    """V18.2.25 (Phase 4.3): Check that exec-summary claims are covered by bullets.

    The executive summary is a compressed overview; the bullet_points are the
    detailed claims. If the exec mentions a named author or a specific claim
    that NO bullet mentions, that's either:
    - A hallucination in the exec (invented author/claim), OR
    - An omission in the bullets (the exec knows something the bullets don't).

    Either way, it's an inconsistency that warrants a FLAG.

    Book-agnostic: uses the same author-detection pattern as the existing
    checks. No domain-specific terms.

    Args:
        executive_summary: the executive summary text.
        bullet_points: the list of bullet point strings.
        field_label: "exec" (the field being checked).

    Returns:
        List of Issue objects (one per uncovered author/claim). Severity is
        always "flag" (not auto-fixable — the correct resolution is ambiguous).
    """
    issues: list[Issue] = []
    if not executive_summary or not bullet_points:
        return issues

    # Extract authors mentioned in the exec summary.
    exec_authors = set()
    for m in _AUTHOR_RE.finditer(executive_summary):
        author = m.group(1).strip()
        if len(author) >= 3:
            exec_authors.add(author.lower())

    if not exec_authors:
        return issues  # no authors in exec → nothing to check

    # Build a combined bullet text for author lookup.
    bullet_text = " ".join(bullet_points).lower()

    # Check each exec author against the bullets.
    for author in exec_authors:
        # Match the author name (or surname) in the bullet text.
        # "AuthorA" → check "chasseguet" OR "smirgel" in bullets.
        parts = re.split(r'[-\u2013]', author)
        found = author in bullet_text or any(p in bullet_text for p in parts if len(p) >= 4)
        if not found:
            issues.append(Issue(
                detector="consistency",
                severity="flag",
                field=field_label,
                snippet=executive_summary[:60],
                detail=(
                    f"exec mentions author '{author}' but no bullet point "
                    f"covers this author — possible hallucination in exec or "
                    f"omission in bullets"
                ),
            ))

    return issues



def detect_citation_coverage_gap(
    source_text: str,
    summary_text: str,
    field_label: str = "summary",
    coverage_floor: float = 0.8,
) -> list[Issue]:
    """V18.2.25 (Phase 4.3): Check that the summary covers ≥80% of source authors.

    If the source names N authors and the summary names fewer than N*0.8,
    that's a significant coverage gap — the summary is omitting a substantial
    fraction of the chapter's named contributors.

    This extends the existing bold-name-attribution check with a quantitative
    coverage gate. The existing check verifies attribution accuracy (correct
    author + year); this check verifies coverage (are all major authors
    mentioned at all?).

    Book-agnostic: uses the same author-detection pattern. The 0.8 floor is
    configurable (``coverage_floor`` parameter).

    Args:
        source_text: the chapter source text.
        summary_text: the summary text to check (exec + bullets + thorough).
        field_label: "summary" (the field being checked).
        coverage_floor: the minimum fraction of source authors that must
            appear in the summary (default 0.8 = 80%).

    Returns:
        List of Issue objects. If coverage < floor, a single FLAG issue lists
        the missing authors. If coverage >= floor, returns [].
    """
    issues: list[Issue] = []
    if not source_text or not summary_text:
        return issues

    # Extract authors from the source.
    source_authors: dict[str, str] = {}  # lower → original case
    for m in _AUTHOR_RE.finditer(source_text):
        author = m.group(1).strip()
        if len(author) >= 3:
            source_authors[author.lower()] = author

    if len(source_authors) < 5:
        return issues  # too few authors to enforce a coverage floor

    # Check each source author against the summary.
    summary_lower = summary_text.lower()
    missing: list[str] = []
    for author_lower, author_original in source_authors.items():
        parts = re.split(r'[-\u2013]', author_lower)
        found = author_lower in summary_lower or any(
            p in summary_lower for p in parts if len(p) >= 4
        )
        if not found:
            missing.append(author_original)

    coverage = 1.0 - (len(missing) / len(source_authors))
    if coverage < coverage_floor:
        issues.append(Issue(
            detector="citation_coverage",
            severity="flag",
            field=field_label,
            snippet=f"{len(source_authors)} authors in source, {len(missing)} missing",
            detail=(
                f"citation coverage gap: {len(missing)}/{len(source_authors)} "
                f"source authors not mentioned in summary "
                f"(coverage={coverage:.0%}, floor={coverage_floor:.0%}). "
                f"Missing: {', '.join(missing[:10])}"
                f"{'…' if len(missing) > 10 else ''}"
            ),
        ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.2.28 (regression fix) — Dropped-digit year detector
# ═══════════════════════════════════════════════════════════════════════════

# Catches "AuthorX (181)" — the model dropped a digit from "1981".
# Low-bit quants (IQ2_XXS) sometimes drop a character from numeric tokens.
# This detector cross-references the summary's year against the source's
# author-year citations. If the summary has "Author (18X)" but the source
# has "Author (19XY)" where 18X is a prefix of 19XY, it's a dropped digit.


_YEAR_IN_PARENS_RE = re.compile(
    r'\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\s*\((\d{3,4}[a-z]?)\)'
)




def _is_subsequence(short: str, long: str) -> bool:
    """Check if ``short`` is a subsequence of ``long`` (not necessarily contiguous)."""
    it = iter(long)
    return all(c in it for c in short)

def detect_dropped_digit_years(
    text: str,
    source_text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V18.2.28: Detect dropped-digit year typos by cross-referencing the source.

    Catches "AuthorX (181)" when the source says "AuthorX (1981)" — the model
    dropped a digit. Low-bit quants (IQ2_XXS) sometimes drop characters from
    numeric tokens.

    Detection: for each ``Author (year)`` in the summary, find the same author
    in the source. If the source's year has MORE digits and the summary's year
    is a prefix (or vice versa), it's a dropped-digit typo.

    Auto-fix: replaces the summary's year with the source's year (deterministic
    — the source is the ground truth).

    Book-agnostic: works on any citation format ``Name (YYYY)``.

    Args:
        text: the summary text to scan.
        source_text: the chapter source text (ground truth for years).
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(cleaned_text, issues)``. Auto-fixes dropped digits.
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues

    try:
        # Build a map of author → years from the source.
        source_years: dict[str, list[str]] = {}
        for m in _YEAR_IN_PARENS_RE.finditer(source_text):
            author = m.group(1).strip()
            year = m.group(2).strip()
            if len(author) >= 3:
                source_years.setdefault(author.lower(), []).append(year)

        if not source_years:
            return text, issues  # no author-year citations in source

        # Scan the summary for author-year citations.
        cleaned = text

        def _fix_year(m: re.Match) -> str:
            author = m.group(1).strip()
            summary_year = m.group(2).strip()
            src_years = source_years.get(author.lower(), [])
            if not src_years:
                return m.group(0)  # author not in source — can't verify

            # Check if summary_year is a dropped-digit version of any source year.
            for src_year in src_years:
                # Case 1: summary has fewer digits (e.g. "181" vs "1981")
                if len(summary_year) < len(src_year):
                    # V18.2.28: the model can drop a digit from ANY position
                    # (start, middle, or end). "181" from "1981" dropped the
                    # middle "9". Check if summary_year is a SUBSEQUENCE of
                    # src_year (same digits in same order, one missing).
                    if _is_subsequence(summary_year, src_year):
                        issues.append(Issue(
                            detector="dropped_digit_year",
                            severity="fix",
                            field=field_label,
                            snippet=_snippet(cleaned, m.start()),
                            detail=(
                                f"dropped-digit year: '{author} ({summary_year})' "
                                f"→ '{author} ({src_year})' (source has "
                                f"{len(src_year)} digits, summary has "
                                f"{len(summary_year)} — the model dropped a digit)"
                            ),
                        ))
                        return f"{m.group(1)} ({src_year})"  # V18.2.28: preserve space before (
                # Case 2: summary has MORE digits (e.g. "19881" vs "1981")
                elif len(summary_year) > len(src_year):
                    if _is_subsequence(src_year, summary_year):
                        issues.append(Issue(
                            detector="dropped_digit_year",
                            severity="fix",
                            field=field_label,
                            snippet=_snippet(cleaned, m.start()),
                            detail=(
                                f"extra-digit year: '{author} ({summary_year})' "
                                f"→ '{author} ({src_year})' (source has "
                                f"{len(src_year)} digits, summary has "
                                f"{len(summary_year)} — the model added a digit)"
                            ),
                        ))
                        return f"{m.group(1)} ({src_year})"  # V18.2.28: preserve space before (
            return m.group(0)

        cleaned = _YEAR_IN_PARENS_RE.sub(_fix_year, cleaned)
        return cleaned, issues
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="dropped_digit_year", severity="flag", field=field_label,
            snippet=text[:60], detail=f"dropped-digit-year check crashed: {e!r}",
        ))
        return text, issues


# ═══════════════════════════════════════════════════════════════════════════
# V18.20.3.0 (Audit FLAG-01) — Attribution subject-swap detector
# ═══════════════════════════════════════════════════════════════════════════
#
# The V18.20.2.0 real-rig audit found ONE hallucination in an otherwise
# clean 30-bullet output:
#
#   Summary bullet: "AuthorC's work provides the foundational mechanism for
#   authenticity, 'the term' as a deeply assimilated and personalized
#   bodily foundation for self-experience, and the experience of temporal
#   continuity in the self."
#
#   Source: "AuthorB did not use the term identity but his views are of
#   great significance. His work provides the foundational mechanism for
#   (1) authenticity; (2) 'the term' (AuthorC 1983), or a deeply
#   assimilated and personalized bodily foundation for one's self-
#   experience; and (3) the experience of temporal continuity in the self."
#
# AuthorC (1983) is cited ONLY as the coiner of "the term"; the
# foundational mechanism is the real holder's. The bullet swapped the sentence's
# subject for its parenthetical citation. This error class passes every
# existing guard BY CONSTRUCTION: F4 source-overlap is high (the bullet is
# a near-lexical rewrite of the source sentence), the embedding judge sees
# the same high similarity, and verify_attribution never fires because the
# bullet carries no "(Author Year)" citation of its own.
#
# Detector: when a summary text asserts "<Name>'s work <ATTRIBUTION-VERB> …"
# but the best-matching source region (a) mentions that Name ONLY inside a
# parenthetical citation, (b) attributes the SAME verb to a DIFFERENT
# subject (a named possessive "AuthorB's work provides" or a pronoun
# "His work provides" with a different name as antecedent), and (c) shares
# ≥ 30% content-word overlap with that source region (the claims are about
# the same content) → FLAG for review (severity "flag" — never auto-fixed:
# subject resolution is heuristic).
#
# Book-agnostic: name/citation patterns + verb families, no domain terms
# and no hardcoded author lists.

# Summary-side pattern: "AuthorC's work provides …" / "AuthorB's account
# offers …" / "AuthorK's formulation establishes …" (possessive + scholarly
# noun + attribution verb).
#
# V18.20.3.2 (audit N4): the attribution-verb families are consolidated into
# ONE shared alternation (_ATTRIB_VERBS) used by every regex in this section.
# The V18.20.3.1 list missed the verbs the real gap-fill bullets actually
# used — 'Contributed' (AuthorE evaded the colon detector), 'Identified'
# (AuthorF), 'Made significant contributions' (AuthorM & AuthorN),
# 'Co-authored' (AuthorR), 'Developed' (AuthorQ), 'Suggested' (AuthorU),
# 'Highlighted' (AuthorS), 'Helped clarify' (AuthorO). The expanded list
# covers the verb families observed in V18.20.3.1's gap-fill output plus the
# common scholarly-attribution verbs.
_ATTRIB_VERBS = (
    "provides?|provided|offers?|offered|gives?|gave|forms?|formed|"
    "constitutes?|constituted|establishes?|established|lays?|laid|"
    "suppl(?:y|ies|ied)|creates?|created|builds?|built|grounds?|grounded|"
    "formulates?|formulated|proposes?|proposed|describes?|described|"
    "introduces?|introduced|"
    # V18.20.3.2 additions (verbs observed in real gap-fill bullets):
    "contributes?|contributed|identifies?|identified|makes?|made|"
    "co-?authors?|co-?authored|develops?|developed|suggests?|suggested|"
    "highlights?|highlighted|helps?|helped|clarifies?|clarified|"
    "recognizes?|recognized|distinguishes?|distinguished|notes?|noted|"
    "emphasizes?|emphasized|advances?|advanced|argues?|argued|"
    "asserts?|asserted|maintains?|maintained|observes?|observed|"
    "defines?|defined|coined|stresses?|stressed|examines?|examined|"
    "explores?|explored|traces?|traced|views?|viewed|considers?|"
    "considered|sees?|saw|"
    # V18.20.3.5 (audit v182034, AuthorC leak): general academic attribution
    # verbs missing from the list. Widening the verb set widens BOTH the
    # holder detection AND the escape hatch ("the claimed author genuinely
    # holds a verb in the span → no veto") — for survey-style sources,
    # where every theorist eventually holds one of these verbs in a
    # sentence that mentions them, the net effect is FEWER false vetoes on
    # legitimate bullets. Standard academic-English register, no content
    # words. (combined/integrated/synthesized deliberately EXCLUDED: their
    # subject-position use in passives like "Her works were combined by X"
    # would false-veto correct object-position mention-only bullets.)
    "used|uses?|termed|terms?|called|calls?|named|names?|referred|"
    "refers?|regarded|regards?|outlined|outlines?|reviewed|reviews?|"
    "surveyed|surveys?|discussed|discusses?|addressed|addresses?|"
    "extended|extends?|enriched|enriches?|elaborated|elaborates?|"
    "revived|revives?|resurrected|resurrects?|wrote|writes?|writing|"
    "talked|talks?|pointed|points?|mentioned|mentions?|applied|applies?"
)
# V18.20.3.9 (Phase 2 / B3): the scholarly-noun alternation used by every
# possessive-subject regex below, factored into ONE shared constant and
# BROADENED (was: work|writings|theory|model|framework|approach|account|views|
# analysis|formulation|schema|concept|contributions). Added the possessive
# shapes the V18.20.3.8 rig audit's F3 concern used: "Name's perspective
# provides…", "Name's research establishes…", "Name's ideas emphasize…".
# Widening the noun set widens BOTH subject extraction AND the escape hatch
# (the claimed author genuinely holds the verb → no veto) — confirmation
# still requires the full source-side swap evidence, so precision is
# unchanged. Standard scholarly-English register, no content words.
_ATTRIB_NOUNS = (
    r"(?:work|writings?|theor(?:y|ies)|model|framework|approach|account|views?|"
    r"analysis|formulation|schema|concept(?:ualization)?|contributions?|"
    r"perspectives?|insights?|emphasis|arguments?|claims?|positions?|"
    r"influence|stud(?:y|ies)|research|papers?|essays?|ideas?)"
)
_ATTRIBUTIVE_POSSESSIVE_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\u2019\-]{2,}(?:\s+[A-Z][a-zA-Z'\u2019\-]{2,})?)['\u2019]s\s+"
    + _ATTRIB_NOUNS + r"\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)

# Source-side evidence: a possessive-subject construction "<Name>'s work
# <verb>" (Name ≠ claimed author) or a pronoun-subject "His/Her work
# <verb>" whose antecedent is a different name in the same region.
# V18.20.3.2: verb families via the shared _ATTRIB_VERBS alternation.
_SRC_POSSESSIVE_SUBJECT_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\u2019\-]{2,})['\u2019]s\s+"
    + _ATTRIB_NOUNS + r"\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)
_SRC_PRONOUN_SUBJECT_RE = re.compile(
    r"\b[Hh](?:is|er)\s+"
    + _ATTRIB_NOUNS + r"\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)
# V18.20.3.2 (audit N4 / AuthorF case): "according to <Name>" — the claim's
# owner when the source phrase has no attribution VERB at all ("a second
# force, which, according to AuthorG, is the longing to abandon…").
# The V18.20.3.1 run shipped "AuthorF: Identified a force juxtaposed to the
# driving pressure of the '<concept>'…" (V18.20.4.7 / W-a14: neutral
# placeholder — the original quote used the test chapter's own concept
# name, book-derived vocabulary in a comment) because no verb-based holder
# could be resolved in that span — AuthorG owns the claim only via the
# "according to" phrase.
_SRC_ACCORDING_TO_RE = re.compile(
    r"\baccording to\s+([A-Z][a-zA-Z'\u2019\-]{2,})\b"
)
# Precompiled broad attribution-verb matcher (windows / passive agents).
_ATTRIB_VERB_RE = re.compile(r"\b(?:" + _ATTRIB_VERBS + r")\b", re.IGNORECASE)

# Common non-name capitalized words that appear at sentence starts — never
# treated as the "different subject" evidence.
_NON_NAME_CAPS = {
    "The", "This", "That", "These", "Those", "His", "Her", "Their", "Its",
    "He", "She", "They", "It", "In", "On", "At", "By", "For", "From", "As",
    "With", "Without", "While", "When", "Where", "Although", "Though",
    "However", "Moreover", "Furthermore", "Thus", "Hence", "Therefore",
    "Indeed", "Notably", "Importantly", "Finally", "First", "Second",
    "Third", "According", "Both", "Each", "Such", "Some", "Most", "Many",
    "All", "No", "None", "Another", "Other", "Later", "Earlier", "Since",
    "Because", "Before", "After", "During", "Between", "Among", "If",
    "Unless", "Yet", "But", "And", "Or", "So", "What", "How", "Why",
    "Whether", "There", "Here", "Now", "Then", "Chapter", "Part", "Note",
}

# V18.20.3.1 (real-rig audit D3): the gap-fill path produces BOLD-COLON
# attribution bullets — "AuthorC: Provided the foundational mechanism…" /
# "AuthorE: Formulated a staged process…" — which the V18.20.3.0
# possessive-only detector cannot see. The V18.20.3.0 the rig-test book
# run shipped BOTH of those misattributions undetected (the source credits
# AuthorB and AuthorD respectively; AuthorC/AuthorE appear only as cited
# names inside those claims). Two new patterns close the gap:
#
# Bullet side: "<Name>: <attribution-verb> …" (optionally bolded, optionally
# bulleted, Name may be "A and B").
# V18.20.3.2: verb alternation shared with the source-side regexes via
# _ATTRIB_VERBS (the V18.20.3.1 list missed 'Contributed'/'Identified'/…).
_BULLET_COLON_SUBJECT_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*•]\s*)?(?:\*\*)?\s*"
    r"([A-Z][a-zA-Z'\u2019\-]{2,}(?:\s+(?:and|&)\s+[A-Z][a-zA-Z'\u2019\-]{2,})?)"
    r"(?:\*\*)?\s*:\s*"
    r"((?i:" + _ATTRIB_VERBS + r"))\b"
)

# Source side: an ACTIVE subject construction "<Name> <verb>" (optionally
# with a parenthetical citation between: "AuthorD formulated…" /
# "AuthorO (1958a,b) described…"). Used to find who REALLY holds the
# verb in the candidate span — and to veto when that holder IS the claimed
# author (the bullet is then correctly attributed).
# V18.20.3.2: verb alternation shared via _ATTRIB_VERBS.
_SRC_ACTIVE_SUBJECT_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\u2019\-]{2,})\s*(?:\([^)\d]*\d{4}[^)]*\))?\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)


def _name_holds_verb(name: str, span: str, verb_stems: set) -> bool:
    """V18.20.3.1 (D3): True when ``name`` is the grammatical holder of a
    verb from ``verb_stems`` in ``span`` — active ("AuthorE (1948)
    formulated…"), possessive ("AuthorE's work provides…"), or passive agent
    ("… was formulated … by AuthorE"). Used by the colon-form check: if the
    claimed author genuinely holds the verb in the same span, the bullet is
    correctly attributed and must NOT be flagged (the AuthorE case's claimed
    name appears in the span's "works of AuthorE (1948), …" list — as an
    OBJECT, not a subject)."""
    try:
        for sm in _SRC_ACTIVE_SUBJECT_RE.finditer(span):
            if sm.group(1) == name and (_verb_stems(sm.group(2).lower()) & verb_stems):
                return True
        for sm in _SRC_POSSESSIVE_SUBJECT_RE.finditer(span):
            if sm.group(1) == name and (_verb_stems(sm.group(2).lower()) & verb_stems):
                return True
        for vm in re.finditer(rf"\bby\s+{re.escape(name)}\b", span, re.IGNORECASE):
            window = span[max(0, vm.start() - 80):vm.start()]
            for w in _ATTRIB_VERB_RE.finditer(window):
                if _verb_stems(w.group(0).lower()) & verb_stems:
                    return True
    except re.error:
        pass
    return False


def _name_holds_any_attrib_verb(name: str, span: str) -> bool:
    """V18.20.3.2 (audit N4 / P1-a): True when ``name`` is the grammatical
    holder of ANY attribution verb in ``span`` — active ("AuthorK
    formulated…"), possessive ("AuthorK's work provides…"), or passive agent
    ("… was formulated … by AuthorK").

    Unlike :func:`_name_holds_verb` this takes no verb-stems set — it matches
    the full _ATTRIB_VERBS family. Used by the generation-time
    parenthetical-promotion veto: if the claimed author genuinely holds ANY
    attribution verb in the matched span, the bullet is correctly attributed
    and must NOT be vetoed.
    """
    try:
        for sm in _SRC_ACTIVE_SUBJECT_RE.finditer(span):
            if sm.group(1) == name:
                return True
        for sm in _SRC_POSSESSIVE_SUBJECT_RE.finditer(span):
            if sm.group(1) == name:
                return True
        for vm in re.finditer(rf"\bby\s+{re.escape(name)}\b", span, re.IGNORECASE):
            window = span[max(0, vm.start() - 80):vm.start()]
            if _ATTRIB_VERB_RE.search(window):
                return True
    except re.error:
        pass
    return False


def _verb_stems(verb: str) -> set:
    """Morphological stems for verb-family matching: {'provide'} from
    'provides' / 'provide'; {'establish'} from 'establishes' (strip 's'
    then 'es').

    V18.20.3.1 (real-rig audit D3): past-tense stems added so a bullet's
    "Provided" matches a source's "provides" (the gap-fill colon bullets
    use the past tense — "AuthorC: Provided the foundational mechanism…" — while
    the source says "His work provides…"). Input is case-normalised
    (bullet-side captures keep the sentence-start capital). Irregulars
    (gave/laid/built) intentionally do NOT cross-match; same-form matches
    still work."""
    verb = verb.lower()
    stems = {verb}
    if verb.endswith("ies") and len(verb) > 4:
        stems.add(verb[:-3] + "y")  # supplies → supply
    if verb.endswith("es") and len(verb) > 4:
        stems.add(verb[:-2])
    if verb.endswith("s") and len(verb) > 3:
        stems.add(verb[:-1])
    if verb.endswith("ied") and len(verb) > 4:
        stems.add(verb[:-3] + "y")  # supplied → supply
    if verb.endswith("ed") and len(verb) > 4:
        stems.add(verb[:-2])  # provided → provid
        stems.add(verb[:-1])  # provided → provide
    elif verb.endswith("d") and len(verb) > 3:
        stems.add(verb[:-1])
    return stems


def _all_occurrences_parenthetical(name: str, span: str) -> bool:
    """True if every word-boundary occurrence of ``name`` in ``span`` sits
    inside a parenthesised group (i.e. the name is only ever a citation,
    never a discussed subject)."""
    start = 0
    found = False
    lowered = span
    while True:
        pos = lowered.find(name, start)
        if pos < 0:
            break
        found = True
        # word-boundary check on both sides
        before_ok = pos == 0 or not (lowered[pos - 1].isalnum())
        after = pos + len(name)
        after_ok = after >= len(lowered) or not (lowered[after].isalnum())
        if before_ok and after_ok:
            depth = lowered[:pos].count("(") - lowered[:pos].count(")")
            if depth <= 0:
                return False  # occurs outside any parenthesis
        start = pos + 1
    return found


def _content_overlap(bullet: str, span: str, exclude: set) -> float:
    """Fraction of the bullet's content words (len > 3, minus excluded
    names/verbs) that appear in the source span."""
    words = [
        w.strip("'\u2018\u2019\u201c\u201d.,;:!?()\"").lower()
        for w in re.findall(r"\b\w{4,}\b", bullet)
    ]
    words = [w for w in words if w and w not in exclude]
    if not words:
        return 0.0
    span_lower = span.lower()
    hits = sum(1 for w in words if w in span_lower)
    return hits / len(words)


def _resolve_pronoun_antecedent(
    span: str,
    claimed_surname: str,
    source_authors: list[str] | None,
) -> str | None:
    """Resolve a 'His/Her work <verb>' subject: the different name the
    pronoun points to.

    Strategy: prefer a KNOWN source author (citation-extracted — high
    precision), then fall back to the first plausible capitalized name
    token outside parentheses. The fallback matters because citation
    extraction only finds authors who are formally cited — the true
    subject (e.g. an author the chapter discusses at length without a
    parenthetical year) is often absent from the citation list.
    """
    fallback: str | None = None
    for tok in re.finditer(r"\b([A-Z][a-zA-Z'\u2019\-]{2,})\b", span):
        cand = tok.group(1)
        if cand in _NON_NAME_CAPS or cand == claimed_surname:
            continue
        if _all_occurrences_parenthetical(cand, span):
            continue
        if source_authors:
            if cand in source_authors or any(
                a.startswith(cand) or cand.startswith(a) for a in source_authors
            ):
                return cand  # known author — high confidence
        if fallback is None:
            fallback = cand
    return fallback


def detect_attribution_subject_swap(
    text: str,
    source_text: str,
    field_label: str,
    source_authors: list[str] | None = None,
    source_lower: str | None = None,
) -> tuple[str, list[Issue]]:
    """V18.20.3.0 (Audit FLAG-01): flag subject-swap misattributions.

    Catches the class where a summary bullet asserts ``<Name>'s work
    provides …`` while the matching source sentence attributes the SAME
    claim to a DIFFERENT subject, with ``<Name>`` appearing only as a
    parenthetical citation there. High-lexical-overlap by construction —
    invisible to source-overlap and embedding judges.

    Returns ``(text, issues)`` — text is UNCHANGED (flag-only; subject
    resolution is heuristic and rewriting could corrupt a correct bullet).
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues
    try:
        matches = list(_ATTRIBUTIVE_POSSESSIVE_RE.finditer(text))
        colon_matches = list(_BULLET_COLON_SUBJECT_RE.finditer(text))

        # Split source into sentences ONCE; build 2-sentence spans (the
        # pronoun antecedent usually lives in the preceding sentence).
        src_sentences = re.split(r"(?<=[.!?])\s+", source_text)

        # ── Path 1 (V18.20.3.0): possessive form "X's work provides …" ────
        for m in matches:
            claimed = m.group(1).strip()
            claimed_surname = claimed.split()[-1]
            verb = m.group(2).lower()
            verb_stems = _verb_stems(verb)

            # The claim text around the match (sentence granularity).
            sent_start = max(text.rfind(".", 0, m.start()), text.rfind("!", 0, m.start()), text.rfind("?", 0, m.start())) + 1
            sent_end = text.find(".", m.end())
            if sent_end < 0:
                sent_end = len(text)
            claim_sentence = text[sent_start:sent_end].strip()

            # Find source spans mentioning the claimed surname. Scan ALL
            # of them: a confirmed swap in one span must still be vetoed if
            # ANY other span genuinely names the claimed author as an
            # attributive subject (escape hatch — first-match break would
            # miss the veto and false-flag).
            confirmed_span = None
            has_genuine_subject_elsewhere = False
            for i, sent in enumerate(src_sentences):
                if claimed_surname not in sent:
                    continue
                span = sent
                if i > 0:
                    span = src_sentences[i - 1] + " " + sent
                # Escape-hatch: the claimed author appears OUTSIDE parens
                # with an attributive construction somewhere → genuine
                # subject; never flag.
                if not _all_occurrences_parenthetical(claimed_surname, span):
                    _genuine = _SRC_POSSESSIVE_SUBJECT_RE.search(span)
                    if _genuine and _genuine.group(1) == claimed_surname:
                        has_genuine_subject_elsewhere = True
                    continue  # name is discussed outside parens — not our class

                if confirmed_span is not None:
                    continue  # already confirmed; keep scanning for the veto

                # (b) a DIFFERENT subject with the SAME verb in this span?
                diff_name = None
                pos_subj = _SRC_POSSESSIVE_SUBJECT_RE.search(span)
                if pos_subj and pos_subj.group(1) != claimed_surname:
                    if _verb_stems(pos_subj.group(2).lower()) & verb_stems:
                        diff_name = pos_subj.group(1)
                if diff_name is None:
                    pron_subj = _SRC_PRONOUN_SUBJECT_RE.search(span)
                    if pron_subj and _verb_stems(pron_subj.group(1).lower()) & verb_stems:
                        # Resolve the pronoun antecedent: prefer a KNOWN
                        # source author (citation-extracted — high precision);
                        # fall back to the first plausible capitalized name
                        # token outside parens (citation extraction misses
                        # authors who are only discussed, never cited).
                        diff_name = _resolve_pronoun_antecedent(
                            span, claimed_surname, source_authors,
                        )
                if diff_name is None:
                    continue

                # (c) the bullet and the span are about the same content.
                _excl = {claimed_surname.lower(), verb} | verb_stems
                if _content_overlap(claim_sentence, span, _excl) < 0.30:
                    continue

                confirmed_span = (span, diff_name)

            if confirmed_span and not has_genuine_subject_elsewhere:
                span, real = confirmed_span
                issues.append(Issue(
                    detector="attribution_swap",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"subject-swap misattribution: summary attributes a "
                        f"'{verb}' claim to '{claimed}', but the matching "
                        f"source passage attributes it to '{real}' "
                        f"('{claimed}' appears there only as a parenthetical "
                        f"citation). Verify: is the WORK really {claimed}'s, "
                        f"or is {claimed} only cited for a term?"
                    ),
                ))

        # ── Path 2 (V18.20.3.1, audit D3): colon form "Name: <verb> …" ────
        # The gap-fill path emits bold-colon attribution stubs. Unlike the
        # possessive class, the claimed name may appear NON-parenthetically
        # in the source span (inside a "works of AuthorE (1948), AuthorI…"
        # integration list — an OBJECT, not the subject). Confirmation
        # therefore requires: (a) a DIFFERENT name holds the same verb in
        # the span (active / possessive / pronoun-resolved), (b) the claimed
        # name does NOT itself hold the verb in that span, (c) ≥30% content
        # overlap, and (d) no span anywhere names the claimed author as the
        # verb's genuine holder (veto).
        for m in colon_matches:
            claimed = m.group(1).strip()
            claimed_surname = claimed.split()[-1]
            verb = m.group(2).lower()
            verb_stems = _verb_stems(verb)

            # Claim text: the rest of the bullet line after the verb.
            line_end = text.find("\n", m.start())
            if line_end < 0:
                line_end = len(text)
            claim_sentence = text[m.end():line_end].strip()
            if len(claim_sentence) < 20:
                continue  # too thin to confirm content overlap

            confirmed_span = None
            has_genuine_subject_elsewhere = False
            for i, sent in enumerate(src_sentences):
                if claimed_surname not in sent:
                    continue
                span = sent
                if i > 0:
                    span = src_sentences[i - 1] + " " + sent

                # (a) who holds the verb in this span?
                holder = None
                for sm in _SRC_ACTIVE_SUBJECT_RE.finditer(span):
                    if _verb_stems(sm.group(2).lower()) & verb_stems:
                        cand = sm.group(1)
                        if cand in _NON_NAME_CAPS:
                            continue
                        holder = cand
                        break
                if holder is None:
                    pos_subj = _SRC_POSSESSIVE_SUBJECT_RE.search(span)
                    if pos_subj and (_verb_stems(pos_subj.group(2).lower()) & verb_stems):
                        holder = pos_subj.group(1)
                if holder is None:
                    pron_subj = _SRC_PRONOUN_SUBJECT_RE.search(span)
                    if pron_subj and _verb_stems(pron_subj.group(1).lower()) & verb_stems:
                        holder = _resolve_pronoun_antecedent(
                            span, claimed_surname, source_authors,
                        )
                if holder is None:
                    continue
                if holder == claimed_surname:
                    # The claimed author genuinely holds the verb here —
                    # the bullet is correctly attributed (veto evidence).
                    has_genuine_subject_elsewhere = True
                    continue

                # (b) the claimed name must NOT itself hold the verb in
                # this span (as subject or passive agent).
                if _name_holds_verb(claimed_surname, span, verb_stems):
                    continue

                # (c) same content?
                _excl = {claimed_surname.lower(), verb} | verb_stems
                if _content_overlap(claim_sentence, span, _excl) < 0.30:
                    continue

                confirmed_span = (span, holder)

            if confirmed_span and not has_genuine_subject_elsewhere:
                span, real = confirmed_span
                issues.append(Issue(
                    detector="attribution_swap",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"subject-swap misattribution (colon form): summary "
                        f"attributes a '{verb}' claim to '{claimed}', but the "
                        f"matching source passage attributes it to '{real}' "
                        f"('{claimed}' appears there only inside a citation/"
                        f"list, not as the claim's subject). Verify: is the "
                        f"claim really {claimed}'s, or is {claimed} only "
                        f"cited within it?"
                    ),
                ))
    except Exception as e:  # fail-open
        issues.append(Issue(
            detector="attribution_swap", severity="flag", field=field_label,
            snippet=text[:60], detail=f"attribution-swap check crashed: {e!r}",
        ))
    return text, issues


# ── V18.20.3.2 (audit N4 / P1-a): generation-time parenthetical-promotion veto ──
#
# The V18.20.3.1 real-rig run shipped THREE misattributions of the same class
# (AuthorC credited with AuthorB's claim, AuthorE credited with AuthorD's
# staged process, AuthorF credited with AuthorG's force) — all
# generated by the V18.14.1 batch gap-fill, which asks the model for "one
# bullet per author" from source excerpts where the author appears ONLY as a
# parenthetical citation ("(AuthorC 1983)"), an integration-list object ("works
# of AuthorE (1948), …") or a "see also" aside. The model promotes the cited
# name to claim subject. This detector is the GENERATION-TIME veto: it runs
# on each gap-fill bullet BEFORE it is appended, and on final bullets as a
# pre-ship drop in run_post_checks.
#
# It is deliberately RELAXED vs detect_attribution_subject_swap (the flag-only
# detector): the bullet-side accepts ANY "Name: claim" prefix (not just
# attribution-verb starts — "AuthorE: Contributed to the formulation…" evaded
# the V18.20.3.1 colon regex because 'Contributed' wasn't in the verb list),
# and the holder-side accepts ANY attribution verb plus "according to <Name>"
# (the AuthorF span has no attribution verb at all). The false-positive cost
# is asymmetric and cheap: dropping one gap-fill bullet loses a little
# coverage (logged loudly), while shipping a misattribution is a factual
# error the judges cannot see (high lexical overlap by construction).

_BULLET_NAME_PREFIX_RE = re.compile(
    r"^\s*(?:[-*\u2022]\s*)?(?:\*\*)?\s*"
    r"([A-Z][a-zA-Z'\u2019\-]{2,}(?:\s+(?:and|&)\s+[A-Z][a-zA-Z'\u2019\-]{2,})?)"
    r"(?:\*\*)?\s*:\s*(.+)$",
    re.DOTALL,
)

# V18.20.3.5 (audit v182034, the AuthorC leak): the veto entry was COLON-ONLY
# ("Name: claim"). The V18.20.3.4 mention-only prompt made the model
# rephrase its twice-vetoed colon bullet into the POSSESSIVE form —
# "AuthorC's work provides the foundational mechanism…" — which is invisible to
# the entry regex, so the veto never ran and the misattribution shipped
# (audit E1). The entry now accepts the three subject-claim shapes a
# bullet can open with (content-agnostic grammar, no word lists):
#   1. colon:      "Name: <claim>"
#   2. possessive: "Name's <noun-phrase> <attribution-verb> …"
#                 (reuse of _ATTRIBUTIVE_POSSESSIVE_RE — the same shape the
#                  flag-only swap detector sees)
#   3. bare active: "Name <attribution-verb> …" (optionally "Name (Year)
#                  <verb>")
# Passive / object-position forms ("AuthorE's 1948 work was integrated by
# AuthorD…") deliberately do NOT match — the labeled name there is the
# OBJECT of the citation verb, not the claim owner, and vetoing those
# would destroy correct mention-only bullets.
_BULLET_POSSESSIVE_PREFIX_RE = re.compile(
    r"^\s*(?:[-*\u2022]\s*)?(?:\*\*)?\s*"
    r"([A-Z][a-zA-Z'\u2019\-]{2,}(?:\s+(?:and|&)\s+[A-Z][a-zA-Z'\u2019\-]{2,})?)"
    r"(?:\*\*)?['\u2019]s\b\s*(.+)$",
    re.DOTALL,
)
_BULLET_ACTIVE_PREFIX_RE = re.compile(
    r"^\s*(?:[-*\u2022]\s*)?(?:\*\*)?\s*"
    r"([A-Z][a-zA-Z'\u2019\-]{2,}(?:\s+(?:and|&)\s+[A-Z][a-zA-Z'\u2019\-]{2,})?)"
    r"(?:\*\*)?\s*(?:\([^)\d]*\d{4}[^)]*\))?\s*"
    r"((?i:" + _ATTRIB_VERBS + r"))\b",
)


def _parse_bullet_subject(bullet: str) -> tuple[str, str] | None:
    """V18.20.3.5: parse a gap-fill bullet's claimed subject + claim text.

    Returns ``(claimed_name, claim_text)`` for the three subject-claim
    shapes (colon / possessive / bare-active), else ``None``. The
    possessive form requires an attributive-possessive construction
    ("Name's work provides…") within the bullet's opening — matched via
    :data:`_ATTRIBUTIVE_POSSESSIVE_RE` — so plain possessive mentions
    ("AuthorI's six phases…") without an attribution verb do not enter
    the veto.
    """
    stripped = bullet.strip()
    # Form 1: colon
    m = _BULLET_NAME_PREFIX_RE.match(stripped)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Form 2: possessive + attributive construction
    m = _BULLET_POSSESSIVE_PREFIX_RE.match(stripped)
    if m:
        claimed = m.group(1).strip()
        rest = m.group(2)
        if _ATTRIBUTIVE_POSSESSIVE_RE.search(stripped):
            return claimed, rest.strip()
    # Form 3: bare active subject + attribution verb
    m = _BULLET_ACTIVE_PREFIX_RE.match(stripped)
    if m:
        claimed = m.group(1).strip()
        return claimed, stripped[m.end():].strip()
    return None


def detect_parenthetical_promotion(
    bullet: str,
    source_text: str,
    source_authors: list[str] | None = None,
) -> tuple[str, str] | None:
    """V18.20.3.2 (audit N4 / P1-a): detect a parenthetical-promotion
    misattribution in a gap-fill bullet.

    A bullet of the form ``<Name>: <claim>`` is a promotion when the source
    sentence(s) mentioning ``<Name>`` attribute the SAME content to a
    DIFFERENT active subject, and ``<Name>`` never holds any attribution
    verb there. Verified regression vectors (V18.20.3.1 the rig-test book):

    - ``AuthorC: Provided the foundational mechanism for the constructs…`` — source:
      "his work provides…" (AuthorB's; AuthorC 1983 only coined "the term")
    - ``AuthorE: Contributed to the formulation of a staged process…`` —
      source: "AuthorD formulated a staged process… by integrating the
      works of AuthorE (1948)…" (agent swapped)
    - ``AuthorF: Identified a force juxtaposed to the driving pressure of
      the '<concept>'…`` — source: "…according to AuthorG, is the
      longing to abandon… (see also AuthorF 1960 in this connection)"

    Args:
        bullet: the gap-fill bullet (``"Name: claim"`` or with leading dash).
        source_text: the full chapter source text.
        source_authors: optional citation-extracted author list (improves
            pronoun-antecedent resolution).

    Returns:
        ``(claimed_name, real_name)`` when the bullet is CONFIRMED as a
        parenthetical promotion, else ``None`` (keep the bullet). Fail-open
        on any internal error.
    """
    if not bullet or not source_text:
        return None
    try:
        # V18.20.3.5: three-form subject parser (colon / possessive /
        # bare-active). The old colon-only regex is why the possessive
        # "AuthorC's work provides…" mention-only bullet sailed through the
        # generation-time veto AND the ship-time drop in run_post_checks
        # (audit v182034, defect E1).
        parsed = _parse_bullet_subject(bullet)
        if not parsed:
            return None
        claimed, claim_text = parsed
        if len(claim_text) < 20:
            return None  # too thin to confirm content overlap
        claimed_surname = claimed.split()[-1]

        src_sentences = re.split(r"(?<=[.!?])\s+", source_text)
        confirmed: tuple[str, str] | None = None
        has_genuine_subject = False
        for i, sent in enumerate(src_sentences):
            if claimed_surname not in sent:
                continue
            span = sent
            if i > 0:
                span = src_sentences[i - 1] + " " + sent

            # (a) Escape hatch: the claimed author genuinely holds ANY
            # attribution verb in this span → correctly attributed, no veto.
            if _name_holds_any_attrib_verb(claimed_surname, span):
                has_genuine_subject = True
                continue

            if confirmed is not None:
                continue  # already confirmed; keep scanning for the veto

            # (b) Who REALLY holds an attribution verb / "according to" here?
            holder: str | None = None
            for sm in _SRC_ACTIVE_SUBJECT_RE.finditer(span):
                cand = sm.group(1)
                if cand in _NON_NAME_CAPS or cand == claimed_surname:
                    continue
                holder = cand
                break
            if holder is None:
                pos_subj = _SRC_POSSESSIVE_SUBJECT_RE.search(span)
                if (pos_subj and pos_subj.group(1) != claimed_surname
                        and pos_subj.group(1) not in _NON_NAME_CAPS):
                    holder = pos_subj.group(1)
            if holder is None:
                pron_subj = _SRC_PRONOUN_SUBJECT_RE.search(span)
                if pron_subj:
                    holder = _resolve_pronoun_antecedent(
                        span, claimed_surname, source_authors,
                    )
            if holder is None:
                acc = _SRC_ACCORDING_TO_RE.search(span)
                if (acc and acc.group(1) != claimed_surname
                        and acc.group(1) not in _NON_NAME_CAPS):
                    holder = acc.group(1)
            if not holder or holder == claimed_surname:
                continue

            # (c) Same content? (≥30% content-word overlap, claim minus the
            # claimed name.)
            _excl = {claimed_surname.lower()}
            if _content_overlap(claim_text, span, _excl) < 0.30:
                continue

            confirmed = (claimed_surname, holder)

        if confirmed and not has_genuine_subject:
            return confirmed
        return None
    except Exception as _veto_e:
        # V18.20.3.8 (Phase 1 / W4): fail-open remains the DECISION (never
        # auto-drop on an internal error — that would be destructive), but
        # a crashed veto must be VISIBLE. A silent fail-open here lets a
        # misattributed bullet ship with no trace, and an audit cannot
        # distinguish "checked, clean" from "check never ran" — the same
        # silent-death class the V18.20.3.4 recall-floor probe made famous.
        logger.warning(
            "parenthetical-promotion veto CRASHED — fail-open (bullet kept, "
            "verify manually): %s: %s | bullet: %r",
            type(_veto_e).__name__, _veto_e, (bullet or "")[:80],
        )
        return None

