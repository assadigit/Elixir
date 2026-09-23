"""V0.18 (Phase 5.2) — interpretive-leap / hedge / pronoun / inconsistency detectors.

Moved VERBATIM (byte-identical bodies) from ``postcheck_detectors.py``
during the Phase 5.2 regroup into the ``postchecks/`` package.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    _snippet,
)

_INTERPRETIVE_FIRST_PERSON_RE = re.compile(
    r"\b(?:"
    r"we\s+can\s+see\s+that|we\s+can\s+conclude\s+that|"
    r"we\s+see\s+that|we\s+note\s+that|we\s+observe\s+that|"
    r"we\s+can\s+infer\s+that|we\s+can\s+deduce\s+that|"
    r"it\s+is\s+clear\s+that|it\s+is\s+evident\s+that|"
    r"it\s+is\s+obvious\s+that|it\s+should\s+be\s+noted\s+that|"
    r"it\s+is\s+worth\s+noting\s+that|it\s+is\s+important\s+to\s+note\s+that"
    r")\s*,?\s*",
    re.IGNORECASE,
)

_INTERPRETIVE_LEAP_RE = re.compile(
    r"\b(?:"
    r"this\s+implies|this\s+suggests|this\s+means|"
    r"this\s+indicates|this\s+demonstrates|this\s+shows|"
    r"this\s+reveals|this\s+illustrates|this\s+proves"
    r")\b",
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
            issues.append(
                Issue(
                    detector="interpretation",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=f"stripped first-person interpretation: '{m.group(0).strip()}'",
                )
            )
        cleaned = _INTERPRETIVE_FIRST_PERSON_RE.sub("", cleaned)
        # Clean up the double-space / capitalization left behind.
        cleaned = re.sub(r"\s+([,.;])", r"\1", cleaned)
        cleaned = re.sub(r"  +", " ", cleaned)

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
            issues.append(
                Issue(
                    detector="interpretation",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=(
                        f"interpretive leap '{phrase}' not found in source — "
                        f"summarizer may be adding interpretation"
                    ),
                )
            )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="interpretation",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"interpretive-leap check crashed: {e!r}",
            )
        )
        return text, issues
    return cleaned, issues


_HEDGE_WORDS = (
    "may",
    "might",
    "could",
    "appears to",
    "seems to",
    "suggests",
    "likely",
    "possibly",
    "perhaps",
    "uncertain",
    "unclear",
    "remains",
    "arguably",
    "presumably",
    "potentially",
    "seemingly",
    "allegedly",
    "purportedly",
    "hinges on",
    "depends on",
    "not yet",
    "not fully",
    "not entirely",
    "subject to",
    "tentatively",
    "hypothetically",
    "theoretically",
)

_HEDGE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _HEDGE_WORDS) + r")\b",
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
            issues.append(
                Issue(
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
                )
            )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="hedge",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"hedge-loss check crashed: {e!r}",
            )
        )
    return text, issues


_PRONOUN_MAP = {
    "he": "she",
    "she": "he",
    "his": "her",
    "her": "his",
    "him": "her",
    "himself": "herself",
}

_PRONOUN_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\b"
    r"(?:.{0,200}?)\b(he|she|his|her)\b",
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
                "chapter",
                "figure",
                "table",
                "page",
                "section",
            }:
                continue
            author_lower = author.lower()
            if author_lower not in src_lower:
                continue  # author not in source at all
            # V18.20.3.1 (D2): author must be a source-cited author when the
            # citation-extracted list is available.
            if _gate_on and (
                author_lower not in _author_set and author.split()[-1].lower() not in _author_last
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
            _between = text[m.end(1) : m.start(2)]
            # Clause-scoped: a sentence boundary (. ! ? ;) resets the
            # antecedent — "AuthorO (1958) proposed a continuum. He
            # stressed ..." binds He→AuthorO (a TRUE positive the V18.2.19
            # tests pin). Only a noun phrase in the SAME final clause as the
            # pronoun (the .3.6 bullet[25] shape: "... if a good-enough
            # mother fails ..., she produces ...") suppresses the flag.
            _final_clause = re.split(r"[.!?;]\s*", _between)[-1] if _between else ""
            _bt_tokens = [_w.strip(",;:.!?\u2014\u201c\u201d'\"()") for _w in _final_clause.split()]
            _bt_tokens = [_w for _w in _bt_tokens if _w]
            _DETERMINERS = {
                "a",
                "an",
                "the",
                "this",
                "that",
                "these",
                "those",
                "his",
                "her",
                "their",
                "its",
                "each",
                "every",
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
                rf"\b{re.escape(author)}\b.{{0,200}}?\b(he|she|his|her)\b",
                source_text,
                re.IGNORECASE | re.DOTALL,
            ):
                src_pronoun = src_m.group(1).lower()
                break
            if src_pronoun and src_pronoun != pronoun:
                # Check if they're actually different gender (he vs she, his vs her)
                # vs just different forms (he vs his — same gender).
                _sum_gender = "m" if pronoun in ("he", "his", "him", "himself") else "f"
                _src_gender = "m" if src_pronoun in ("he", "his", "him", "himself") else "f"
                if _sum_gender != _src_gender:
                    # V18.20.3.1 (D2): flag-only — the V18.2.28 auto-fix
                    # re.sub block was dead code (all call sites discard the
                    # returned text) and its Issue detail falsely claimed
                    # "Auto-fixed". Removed; the message is now honest. No
                    # auto-rewrite is also the SAFE choice: the source's
                    # nearest pronoun can belong to a different author.
                    issues.append(
                        Issue(
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
                        )
                    )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="pronoun",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"pronoun check crashed: {e!r}",
            )
        )
    return text, issues


_MISSING_CLAIM_RE = re.compile(
    r"\b(?:"
    r"not\s+mention(?:ed|s)?|not\s+discuss(?:ed|es)?|not\s+address(?:ed|es)?|"
    r"not\s+cover(?:ed|s)?|not\s+explor(?:ed|es)?|not\s+examin(?:ed|es)?|"
    r"not\s+includ(?:ed|es)?|not\s+present(?:ed|s)?|"
    r"absent|omitted|missing|excluded|overlooked|ignored"
    r")\b",
    re.IGNORECASE,
)

# V0.4.23 (audit V0.4.22, backlog #5): the source's OWN omission markers —
# a sentence carrying one of these AND the concept's words asserts the
# omission IN THE SOURCE (the 'noteworthy omission' (Cited 1989) of
# psychotic-like episodes…"). A summary faithfully reporting that claim
# is not making a false "missing" claim.
_SRC_OMISSION_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"omissions?|omitted|omits?|omitting|"
    r"absent|absence|lacks?|lacking|"
    r"excluded|excludes|overlooked|overlooks|ignored|ignores|"
    r"fails?\s+to\s+(?:mention|discuss|address|consider|include|note|cover)|"
    r"not\s+(?:mentioned|discussed|addressed|covered|included|presented)|"
    r"no\s+(?:mention|discussion|reference|treatment|account|consideration)"
    r")\b",
    re.IGNORECASE,
)


def _source_asserts_omission(source_text: str, concept_words: list) -> bool:
    """V0.4.23: True when the SOURCE ITSELF asserts the omission of the
    concept (an omission-marker sentence containing ≥50% of the concept's
    content words).

    The V0.4.22 post-check flagged "omitted psychotic-like episodes" as a
    false "missing" claim because the concept words DO appear in the
    source — but they appear inside the source's own "noteworthy omission"
    statement (Cited 1989, p. 239), which the summary faithfully
    reports. Statements-about-omissions are not summary errors.
    """
    if not source_text or not concept_words:
        return False
    try:
        for sent in re.split(r"(?<=[.!?])\s+|\n", source_text[:200000]):
            if not sent or not _SRC_OMISSION_CONTEXT_RE.search(sent):
                continue
            s_low = sent.lower()
            hits = sum(1 for w in concept_words if str(w).lower() in s_low)
            if hits / len(concept_words) >= 0.50:
                return True
        return False
    except Exception:
        return False


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
            after = text[m.end() : m.end() + 80]
            # Cut at the first sentence boundary.
            cut = re.search(r"[.!?;,\n]|$", after)
            concept = after[: cut.start()].strip() if cut else after.strip()
            # Clean: remove leading articles/prepositions + trailing spaces.
            concept = re.sub(
                r"^(?:the\s+|a\s+|an\s+|of\s+|to\s+|in\s+)", "", concept, flags=re.IGNORECASE
            ).strip()
            if len(concept) < 3:
                continue  # nothing to check

            # Search the source for the concept's key words.
            # Extract content words (≥4 chars, alphabetic) from the concept.
            concept_words = [
                w
                for w in re.findall(r"[a-zA-Z]{4,}", concept)
                if w.lower()
                not in {
                    "that",
                    "this",
                    "with",
                    "from",
                    "have",
                    "been",
                    "were",
                    "they",
                    "their",
                    "which",
                    "would",
                    "could",
                    "should",
                    "about",
                    "into",
                    "than",
                    "then",
                    "them",
                }
            ]
            if not concept_words:
                continue

            # Check if ≥50% of the concept's content words appear in source.
            found = sum(1 for w in concept_words if w.lower() in src_lower)
            ratio = found / len(concept_words) if concept_words else 0
            if ratio >= 0.50:
                # V0.4.23 (audit V0.4.22, backlog #5): STATEMENTS-ABOUT-
                # OMISSIONS EXCEPTION — when the source ITSELF asserts the
                # omission of these concept words ("the 'noteworthy
                # omission' … of psychotic-like episodes"), the summary is
                # faithfully REPORTING the source's omission claim, not
                # making a false "missing" claim. Both V0.4.22 flags of
                # this shape were false positives.
                if _source_asserts_omission(source_text, concept_words):
                    continue
                issues.append(
                    Issue(
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
                    )
                )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="consistency",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"consistency check crashed: {e!r}",
            )
        )
    return text, issues


_AUTHOR_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:[-\u2013][A-Z][a-zA-Z]+)?)\s*\((\d{4}[a-z]?)\)",
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
        parts = re.split(r"[-\u2013]", author)
        found = author in bullet_text or any(p in bullet_text for p in parts if len(p) >= 4)
        if not found:
            issues.append(
                Issue(
                    detector="consistency",
                    severity="flag",
                    field=field_label,
                    snippet=executive_summary[:60],
                    detail=(
                        f"exec mentions author '{author}' but no bullet point "
                        f"covers this author — possible hallucination in exec or "
                        f"omission in bullets"
                    ),
                )
            )

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
        parts = re.split(r"[-\u2013]", author_lower)
        found = author_lower in summary_lower or any(
            p in summary_lower for p in parts if len(p) >= 4
        )
        if not found:
            missing.append(author_original)

    coverage = 1.0 - (len(missing) / len(source_authors))
    if coverage < coverage_floor:
        issues.append(
            Issue(
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
            )
        )

    return issues
