"""V0.18 (Phase 5.2) — attribution / year / bold-name / subject-swap detectors.

Moved VERBATIM (byte-identical bodies) from ``postcheck_detectors.py``
during the Phase 5.2 regroup into the ``postchecks/`` package.
"""

from __future__ import annotations

import re
from datetime import date

from core.preprocessing.citations_regex import APOS as _CIT_APOS
from core.preprocessing.citations_regex import NAME_SEP as _CIT_NAME_SEP
from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    _is_subsequence,
    _snippet,
    logger,
)

MIN_YEAR = 1800

MAX_YEAR = date.today().year + 1

_SUMMARY_CITATION_RE = re.compile(
    r"([A-Z][a-zA-Z]+(?:" + _CIT_NAME_SEP + r"[A-Z][a-zA-Z]+)?"
    r"(?:" + _CIT_APOS + r"[sS]?)?)"
    r"\s*\(?(\d{4}[a-z]?)\)?"
)

_BOLD_NAME_RE = re.compile(
    r"\*\*([A-Z][a-zA-Z]+(?:" + _CIT_NAME_SEP + r"[A-Z][a-zA-Z]+)?)\*\*\s*:\s*(.{10,})"
)

_BARE_YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2}|21\d{2})\b")


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
                issues.append(
                    Issue(
                        detector="year",
                        severity="flag",
                        field=field_label,
                        snippet=snippet,
                        detail=f"implausible year {yr} (outside {MIN_YEAR}-{MAX_YEAR})",
                    )
                )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="year",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"year-range check crashed: {e!r}",
            )
        )

    # --- Check 2: author-name grounding -------------------------------------
    if source_authors:
        try:
            # Build a casefolded lookup set once.
            src_lower = {a.casefold(): a for a in source_authors if a and len(a) >= 3}
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
                    "in",
                    "by",
                    "the",
                    "a",
                    "an",
                    "as",
                    "at",
                    "to",
                    "of",
                    "and",
                    "or",
                    "for",
                    "with",
                    "from",
                    "that",
                    "this",
                    "while",
                    "when",
                    "where",
                    "later",
                    "then",
                    "early",
                }:
                    continue
                if _author_in_source(author_clean, src_lower):
                    continue
                key = author_clean.casefold()
                if key in seen_flags:
                    continue
                seen_flags.add(key)
                snippet = _snippet(text, m.start())
                issues.append(
                    Issue(
                        detector="year",
                        severity="flag",
                        field=field_label,
                        snippet=snippet,
                        detail=(
                            f"author '{author_clean}' (cited with {year}) not "
                            f"found in source's {len(source_authors)} citations "
                            f"— possible name corruption"
                        ),
                    )
                )
        except Exception as e:  # fail-open
            issues.append(
                Issue(
                    detector="year",
                    severity="flag",
                    field=field_label,
                    snippet=text[:60],
                    detail=f"author-grounding check crashed: {e!r}",
                )
            )

    return text, issues


def _author_in_source(author: str, src_lower: dict[str, str]) -> bool:
    """True if ``author`` matches any source author (casefold or fuzzy)."""
    a = author.casefold()
    if a in src_lower:
        return True
    # V18.2.19: Also try the normalized form (strip hyphens) so
    # "AuthorA" matches "chasseguetsmirgel".
    a_norm = a.replace("-", "").replace("\u2013", "").replace(" ", "")
    for src in src_lower:
        if a == src:
            return True
        src_norm = src.replace("-", "").replace("\u2013", "").replace(" ", "")
        if a_norm == src_norm:
            return True
    # Try rapidfuzz (optional dep); else fall back to startswith/levenshtein.
    try:
        from rapidfuzz import fuzz as _rf

        return any(_rf.token_set_ratio(a, src) >= 82 for src in src_lower)
    except ImportError:
        # Simple fallback: casefold startswith either direction (handles
        # "AuthorY" vs "Dukhaim" only loosely, but rapidfuzz is in deps).
        return any(a.startswith(src) or src.startswith(a) for src in src_lower)


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
        src_sentences = re.split(r"(?<=[.!?])\s+", source_text)
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
                "in",
                "by",
                "the",
                "a",
                "an",
                "as",
                "at",
                "to",
                "of",
                "and",
                "or",
                "for",
                "with",
                "from",
                "that",
                "this",
                "while",
                "when",
                "where",
                "later",
                "then",
                "early",
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
            sent_start = text.rfind(".", 0, m.start()) + 1
            sent_end = text.find(".", m.end())
            if sent_end < 0:
                sent_end = len(text)
            summary_claim = text[sent_start:sent_end].strip()

            # Find the source sentence containing this author + year.
            best_src_claim = ""
            best_sim = 0.0
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
                    _src_words_set = set(re.findall(r"\b[a-z0-9]+\b", best_src_claim.lower()))
                    _checks = [
                        e
                        for e in re.findall(
                            r"\b[A-Z][a-zA-Z]{2,}\b|\b\d{4}[a-z]?\b",
                            summary_claim,
                        )
                        if e.lower()
                        not in {
                            "the",
                            "in",
                            "by",
                            "a",
                            "an",
                            "as",
                            "at",
                            "to",
                            "of",
                            "and",
                            "or",
                            "for",
                            "with",
                            "from",
                            "that",
                            "this",
                            "these",
                            "those",
                            "while",
                            "when",
                            "where",
                            "later",
                            "then",
                            "early",
                            "his",
                            "her",
                            "their",
                            "its",
                            "he",
                            "she",
                        }
                        and e.lower() != author_clean.lower()
                    ]
                    _checks += [
                        w
                        for w in re.findall(r"\b[a-z]{5,}\b", summary_claim.lower())
                        if w
                        not in {
                            "about",
                            "their",
                            "which",
                            "there",
                            "these",
                            "those",
                            "while",
                            "through",
                            "between",
                            "during",
                            "before",
                            "after",
                            "where",
                            "would",
                            "could",
                            "should",
                            "might",
                            "because",
                            "since",
                            "although",
                            "though",
                            "other",
                            "others",
                            "being",
                            "having",
                        }
                    ]
                    if _checks:
                        _hits = sum(
                            1
                            for w in _checks
                            if w.lower() in _src_words_set
                            or w.lower().rstrip("s") in _src_words_set
                            or w.lower() + "s" in _src_words_set
                        )
                        if _hits / len(_checks) >= 0.5:
                            _suppressed_as_paraphrase = True
                if _suppressed_as_paraphrase:
                    continue
                issues.append(
                    Issue(
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
                    )
                )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="attribution",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"attribution check crashed: {e!r}",
            )
        )
    return text, issues


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

        src_sentences = _re.split(r"(?<=[.!?])\s+", source_text)

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
                issues.append(
                    Issue(
                        detector="attribution",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"bold-name author '{author}' not found in source — "
                            f"the summary attributes a claim to an author the "
                            f"source never mentions"
                        ),
                    )
                )
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
                issues.append(
                    Issue(
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
                    )
                )

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
                    r"\(" + _re.escape(author) + r"\s+\d{4}",
                    best_src_claim,
                )
                # Check if the author's name appears OUTSIDE of a parenthetical
                # citation (i.e., as the sentence subject, not just a cite).
                _non_citation_mention = bool(
                    _re.search(
                        rf"(?<!\(){author}\b(?!\s*\d{{4}})",
                        best_src_claim,
                    )
                )
                if _citation_ctx and not _non_citation_mention:
                    issues.append(
                        Issue(
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
                        )
                    )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="attribution",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"bold-name attribution check crashed: {e!r}",
            )
        )
    return text, issues


_YEAR_IN_PARENS_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\s*\((\d{3,4}[a-z]?)\)"
)


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
                        issues.append(
                            Issue(
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
                            )
                        )
                        return f"{m.group(1)} ({src_year})"  # V18.2.28: preserve space before (
                # Case 2: summary has MORE digits (e.g. "19881" vs "1981")
                elif len(summary_year) > len(src_year):
                    if _is_subsequence(src_year, summary_year):
                        issues.append(
                            Issue(
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
                            )
                        )
                        return f"{m.group(1)} ({src_year})"  # V18.2.28: preserve space before (
            return m.group(0)

        cleaned = _YEAR_IN_PARENS_RE.sub(_fix_year, cleaned)
        return cleaned, issues
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="dropped_digit_year",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"dropped-digit-year check crashed: {e!r}",
            )
        )
        return text, issues


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
    + _ATTRIB_NOUNS
    + r"\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)

# Source-side evidence: a possessive-subject construction "<Name>'s work
# <verb>" (Name ≠ claimed author) or a pronoun-subject "His/Her work
# <verb>" whose antecedent is a different name in the same region.
# V18.20.3.2: verb families via the shared _ATTRIB_VERBS alternation.
_SRC_POSSESSIVE_SUBJECT_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\u2019\-]{2,})['\u2019]s\s+" + _ATTRIB_NOUNS + r"\s+"
    r"(" + _ATTRIB_VERBS + r")\b"
)

_SRC_PRONOUN_SUBJECT_RE = re.compile(
    r"\b[Hh](?:is|er)\s+" + _ATTRIB_NOUNS + r"\s+"
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
_SRC_ACCORDING_TO_RE = re.compile(r"\baccording to\s+([A-Z][a-zA-Z'\u2019\-]{2,})\b")

# Precompiled broad attribution-verb matcher (windows / passive agents).
_ATTRIB_VERB_RE = re.compile(r"\b(?:" + _ATTRIB_VERBS + r")\b", re.IGNORECASE)

# Common non-name capitalized words that appear at sentence starts — never
# treated as the "different subject" evidence.
_NON_NAME_CAPS = {
    "The",
    "This",
    "That",
    "These",
    "Those",
    "His",
    "Her",
    "Their",
    "Its",
    "He",
    "She",
    "They",
    "It",
    "In",
    "On",
    "At",
    "By",
    "For",
    "From",
    "As",
    "With",
    "Without",
    "While",
    "When",
    "Where",
    "Although",
    "Though",
    "However",
    "Moreover",
    "Furthermore",
    "Thus",
    "Hence",
    "Therefore",
    "Indeed",
    "Notably",
    "Importantly",
    "Finally",
    "First",
    "Second",
    "Third",
    "According",
    "Both",
    "Each",
    "Such",
    "Some",
    "Most",
    "Many",
    "All",
    "No",
    "None",
    "Another",
    "Other",
    "Later",
    "Earlier",
    "Since",
    "Because",
    "Before",
    "After",
    "During",
    "Between",
    "Among",
    "If",
    "Unless",
    "Yet",
    "But",
    "And",
    "Or",
    "So",
    "What",
    "How",
    "Why",
    "Whether",
    "There",
    "Here",
    "Now",
    "Then",
    "Chapter",
    "Part",
    "Note",
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
            window = span[max(0, vm.start() - 80) : vm.start()]
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
            window = span[max(0, vm.start() - 80) : vm.start()]
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
            sent_start = (
                max(
                    text.rfind(".", 0, m.start()),
                    text.rfind("!", 0, m.start()),
                    text.rfind("?", 0, m.start()),
                )
                + 1
            )
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
                            span,
                            claimed_surname,
                            source_authors,
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
                issues.append(
                    Issue(
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
                    )
                )

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
            claim_sentence = text[m.end() : line_end].strip()
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
                            span,
                            claimed_surname,
                            source_authors,
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
                issues.append(
                    Issue(
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
                    )
                )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="attribution_swap",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"attribution-swap check crashed: {e!r}",
            )
        )
    return text, issues


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
        return claimed, stripped[m.end() :].strip()
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
                if (
                    pos_subj
                    and pos_subj.group(1) != claimed_surname
                    and pos_subj.group(1) not in _NON_NAME_CAPS
                ):
                    holder = pos_subj.group(1)
            if holder is None:
                pron_subj = _SRC_PRONOUN_SUBJECT_RE.search(span)
                if pron_subj:
                    holder = _resolve_pronoun_antecedent(
                        span,
                        claimed_surname,
                        source_authors,
                    )
            if holder is None:
                acc = _SRC_ACCORDING_TO_RE.search(span)
                if acc and acc.group(1) != claimed_surname and acc.group(1) not in _NON_NAME_CAPS:
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
            type(_veto_e).__name__,
            _veto_e,
            (bullet or "")[:80],
        )
        return None
