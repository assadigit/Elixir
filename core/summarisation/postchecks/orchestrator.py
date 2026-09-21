"""V18.2.13: Deterministic post-checks — final sweep for the four classes of
garbled-token artifacts that low-bit quantization (IQ2_XXS, 2.1 bits/param)
introduces into generated summaries.

V18.18.0.0 (Phase 2c): Detector functions + constants extracted to
``postcheck_detectors.py``. This module retains the orchestrator
(run_post_checks) and helpers (_snippet, _is_subsequence), and re-exports
the public detector API from postcheck_detectors for backward
compatibility. V0.08 (P2 hygiene): the wildcard re-export was replaced by
an explicit import — transitive stdlib leakage (``logging``/``re``/
``dataclass``/``date``/``field``) is no longer re-exported.

All existing imports ``from core.summarisation.postchecks import X`` continue
to work unchanged.
"""

# V0.18 (Phase 5.2): this orchestrator moved VERBATIM from
# core/summarisation/postchecks.py into the postchecks package as
# orchestrator.py; the package __init__ re-exports the public API and
# lazily forwards to this module (import-cycle-safe).

from __future__ import annotations

import logging
import re

from core.summarisation.post_processing import (  # V18.20.3.4 (RC-1)
    SELF_TALK_PATTERNS,  # V18.20.3.2 (audit N1 / P0-2)
    classify_scar,
    is_citation_only_fragment,  # V18.20.3.2 (audit N5 / P1-c)
    is_truncated,
)
from core.summarisation.postchecks.attribution import (  # noqa: F401
    _BARE_YEAR_RE,
    _BOLD_NAME_RE,
    _SUMMARY_CITATION_RE,
    MAX_YEAR,
    MIN_YEAR,
    _author_in_source,
    detect_attribution_subject_swap,
    detect_dropped_digit_years,
    detect_parenthetical_promotion,
    validate_years,
    verify_attribution,
    verify_bold_name_attribution,
)
from core.summarisation.postchecks.coherence import (  # noqa: F401
    _HEDGE_RE,
    _HEDGE_WORDS,
    _INTERPRETIVE_FIRST_PERSON_RE,
    _INTERPRETIVE_LEAP_RE,
    detect_citation_coverage_gap,
    detect_exec_bullet_inconsistency,
    detect_hedge_loss,
    detect_inconsistency,
    detect_interpretive_leaps,
    detect_pronoun_mismatch,
)
from core.summarisation.postchecks.garble import (  # noqa: F401
    _CAMELCASE_MERGE_RE,
    _FRAGMENT_MERGE_RE,
    _IMPOSSIBLE_BIGRAM_RE,
    _IMPOSSIBLE_BIGRAMS,
    _LEGIT_SUFFIXES,
    _LONG_CONSONANT_CLUSTER_RE,
    _MERGED_SENTENCE_RE,
    _MISSING_SPACE_CAP_RE,
    _MISSING_SPACE_LOWER_RE,
    _VERB_ENDINGS,
    _VERB_STOPWORDS,
    _VOWEL,
    _VOWEL_LESS_LONG_RE,
    _is_legitimate_inflection,
    detect_and_repair_author_garbles,  # V0.20.5 (brainstorm D1)
    detect_dropped_letter_garble,
    detect_extra_spaces,
    detect_garbled_tokens,
    detect_grammatical_incoherence,
    detect_missing_spaces,
    detect_word_fragment_merge,
    repair_stray_quotes,  # V0.20.5 (brainstorm D2)
)
from core.summarisation.postchecks.leakage import (  # noqa: F401
    _COT_NARRATIVE_MARKERS,
    _COT_NARRATIVE_RE,
    _PROMPT_LEAKAGE_PATTERNS,
    _PROMPT_LEAKAGE_RE,
    detect_cot_narrative,
    detect_prompt_leakage,
)

# V18.18.0.0 (Phase 2c): Re-export the public detector API.
# V0.08 (P2): explicit imports (was ``import *``) — intentional re-exports,
# ruff F401 suppressed; consumed by the orchestrator below and by importers
# of this backward-compat facade.
# Explicit imports for underscore-prefixed names (not exported by *)
# V18.20.3.12: noqa: F401 added — these are intentional re-exports consumed by
# tests (test_citations_regex, test_postcheck_fragment_merge_fix, test_v18219);
# the safe ruff auto-fix removed them once as "unused" which broke those imports.
# V0.18 (Phase 5.2): detectors now live in the sibling family modules
from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    PostCheckReport,
    _is_subsequence,
    _snippet,
)

logger = logging.getLogger(
    "core.summarisation.postchecks"
)  # V0.18 (Phase 5.2): literal historical channel name


# V18.18.0.0: Issue + PostCheckReport moved to postcheck_detectors.py


# ═══════════════════════════════════════════════════════════════════════════
# Detector 1 — Year + author-name validation
# ═══════════════════════════════════════════════════════════════════════════


def run_post_checks(
    bullets: list[str],
    executive_summary: str,
    thorough_summary: str,
    source_text: str | None = None,
    key_distinctions: str = "",
    theoretical_tensions: str = "",
    auto_repair_garble: bool = False,
) -> PostCheckReport:
    """Run all deterministic post-checks on the final summary.

    Order matters: we run **auto-fixing** detectors first (prompt-leakage,
    missing-space, interpretive-leaps) so that the **flagging** detectors
    (garbled-tokens, year/name validation, attribution, hedge, consistency)
    scan the already-cleaned text. This prevents a leakage phrase from
    being recorded as a garbled-token false positive.

    For each of bullets / exec / thorough, the detectors run in this order:

        1. :func:`detect_prompt_leakage`     (fixes)
        2. :func:`detect_missing_spaces`     (fixes)
        3. :func:`detect_prompt_leakage`     (fixes, re-run)
        4. :func:`detect_interpretive_leaps` (fixes first-person, flags leaps)
        5. :func:`detect_garbled_tokens`     (flags only)
        6. :func:`validate_years`            (flags only, source-aware)
        7. :func:`verify_attribution`        (flags only, source-aware) [V18.2.17]
        8. :func:`detect_hedge_loss`         (flags only, source-aware) [V18.2.17]
        9. :func:`detect_inconsistency`      (flags only, source-aware) [V18.2.17]

    Args:
        bullets: the final bullet list (post-consolidation, post-gap-fill).
        executive_summary: the final exec summary.
        thorough_summary: the final thorough summary.
        source_text: optional chapter source. When provided, its author list
            is extracted via :func:`deterministic_analyzer.extract_citations`
            and used to validate the summary's ``(Author Year)`` citations.
        auto_repair_garble: V0.03 (P0-1) — default False. The dropped-letter
            auto-repair is DISABLED until re-validated on a real rig (the
            V0.02 rig run: 12 of 13 auto-repairs corrupted valid paraphrase
            words). When True, repairs additionally require the English-
            lexicon guard, paragraph corroboration, and strict single-
            candidate uniqueness (see detect_dropped_letter_garble).

    Returns:
        :class:`PostCheckReport` with cleaned outputs + issues.
    """
    report = PostCheckReport()

    # V18.20.2.0 (SWOT A24): precompute the shared source-derived values ONCE
    # per run — previously every detector rebuilt `source_text.lower()` (and
    # the source word-set) per bullet, ~300 full-source scans per 60-bullet
    # chapter. The values are passed down to the detectors via their new
    # optional ``source_lower`` / ``source_words`` params (lazy-computed when
    # omitted, so existing direct callers/tests keep working).
    _src_lower_full: str = source_text.lower() if source_text else ""
    _src_lower: str = _src_lower_full[:200000] if source_text else ""
    _src_words: set = set(re.findall(r"\b[a-z]+\b", _src_lower_full)) if source_text else set()

    # Lazy: extract source authors only once, if we have source text.
    source_authors: list[str] | None = None
    if source_text:
        try:
            from core.preprocessing.deterministic_analyzer import extract_citations

            cites = extract_citations(source_text)
            # De-dup, preserve order, surnames only (first capitalized token).
            seen: set = set()
            authors: list[str] = []
            for c in cites:
                a = c.get("author", "").strip()
                if not a or len(a) < 3:
                    continue
                # Take the surname (last token) for matching — handles
                # "First Middle Last" → "Last".
                surname = a.split()[-1] if " " in a else a
                key = surname.casefold()
                if key in seen:
                    continue
                seen.add(key)
                authors.append(surname)
            source_authors = authors
        except Exception as e:
            # V18.20.3.8 (Phase 1 / W9): this failure silently degrades the
            # year-validation, attribution-verify, bold-name, subject-swap,
            # pronoun and parenthetical-promotion detectors at once — it
            # must be visible, not DEBUG-buried (honest failure over silent
            # failure).
            logger.warning(
                "postcheck: source-author extraction failed — year/attribution/"
                "pronoun detectors degrade to source-text-only mode: %s: %s",
                type(e).__name__,
                e,
            )
            source_authors = None  # degrade to range-only year check

    # ── Bullets ──────────────────────────────────────────────────────────
    cleaned_bullets: list[str] = []
    for i, bp in enumerate(bullets or []):
        bp_str = str(bp) if bp else ""
        label = f"bullet[{i}]"
        bp_str, leak1 = detect_prompt_leakage(bp_str, label)
        bp_str, space1 = detect_missing_spaces(
            bp_str,
            label,
            source_text or "",
            source_lower=_src_lower_full,
            source_words=_src_words,
        )
        # Re-run prompt-leakage once more — missing-space split can expose
        # a leakage phrase that was hidden inside a merged token.
        bp_str, leak2 = detect_prompt_leakage(bp_str, label)
        # V18.2.17 Fix 5: interpretive-leap strip/flag (source-aware).
        bp_str, interp = detect_interpretive_leaps(
            bp_str, label, source_text, source_lower=_src_lower
        )
        # V18.2.19 Improvement 1: extra-space detector (auto-fixes split words).
        bp_str, extra_space = detect_extra_spaces(
            bp_str,
            label,
            source_text or "",
            source_lower=_src_lower_full,
            source_words=_src_words,
        )
        _, garbled_issues = detect_garbled_tokens(
            bp_str, label, source_text or "", source_words=_src_words
        )
        # V18.2.18 Improvement 2: grammatical coherence (catches broken bullets).
        _, grammar_issues = detect_grammatical_incoherence(bp_str, label)
        # V18.2.19 Improvement 2: word-fragment merge (flag-only).
        _, fragment_issues = detect_word_fragment_merge(
            bp_str, label, source_text or "", source_words=_src_words
        )
        # V18.20.2.0 (SWOT A19): dropped-letter garble detector on BULLETS.
        # The V18.19.2.3 detector ran on exec (:221) and thorough (:277) only —
        # the exact "emergs"→"emerges" single-word garble class it was built
        # for shipped unflagged in Key Takeaways bullets (the field where the
        # V18.19.2.0 audit found the defect).
        # V18.20.3.4 (RC-3): the return text is now CAPTURED — the detector
        # auto-repairs unambiguous single-candidate garbles (the "emergs"→
        # "emerges" class, audit F7, which shipped as a typo in BOTH the
        # bullet and the thorough of the V18.20.3.3 run). Ambiguous garbles
        # remain flag-only.
        bp_str, dropped_issues = detect_dropped_letter_garble(
            bp_str,
            label,
            source_text or "",
            source_words=_src_words,
            auto_repair=auto_repair_garble,
        )
        # V0.20.5 (brainstorm D1): cross-check author surnames against the
        # source author list — auto-repair edit-distance-1 garbles (e.g., a
        # dropped letter in a cited author's surname). Content-agnostic: the
        # source author list comes from the runtime analysis.
        bp_str, name_garble_issues = detect_and_repair_author_garbles(bp_str, label, source_authors)
        # V0.20.5 (brainstorm D2): repair stray/misplaced double-quotes.
        bp_str, stray_quote_issues = repair_stray_quotes(bp_str, label)
        _, year_issues = validate_years(bp_str, label, source_authors)
        # V18.2.17 Fix 7: attribution verification (source-aware).
        _, attrib_issues = (
            verify_attribution(
                bp_str, source_text or "", label, source_authors, source_lower=_src_lower
            )
            if source_text
            else (None, [])
        )
        # V18.2.18 Improvement 1: bold-name attribution check (catches
        # **Author**: claim format that verify_attribution misses).
        _, bold_attrib = (
            verify_bold_name_attribution(
                bp_str, source_text or "", label, source_authors, source_lower=_src_lower
            )
            if source_text
            else (None, [])
        )
        # V18.20.3.0 (Audit FLAG-01): subject-swap attribution check — catches
        # "X's work provides …" bullets where the source attributes the same
        # claim to a different subject and X is only a parenthetical citation
        # (the cited-vs-holder class — invisible to overlap + embedding judges).
        _, swap_attrib = (
            detect_attribution_subject_swap(
                bp_str, source_text or "", label, source_authors, source_lower=_src_lower
            )
            if source_text
            else (None, [])
        )
        # V18.2.17 Fix 8: consistency check (source-aware).
        _, consist_issues = (
            detect_inconsistency(bp_str, source_text or "", label, source_lower=_src_lower)
            if source_text
            else (None, [])
        )
        # V18.2.19 Improvement 3: pronoun mismatch check (source-aware).
        # V18.20.3.1 (D2): source_authors gate passed — non-cited "authors"
        # (ordinary nouns like 'views'/'fails') no longer produce flags.
        _, pronoun_issues = (
            detect_pronoun_mismatch(
                bp_str,
                source_text or "",
                label,
                source_lower=_src_lower,
                source_authors=source_authors,
            )
            if source_text
            else (None, [])
        )
        # V18.2.28 (regression fix): dropped-digit year check (source-aware).
        # Catches "Author (181)" when the source says "Author (1981)".
        bp_str, year_digit_issues = (
            detect_dropped_digit_years(bp_str, source_text or "", label)
            if source_text
            else (bp_str, [])
        )
        # V18.15.5.0 (DEBT-07 / Known Issue #3): re-run is_truncated on the
        # FINAL bullet (post-consolidation). Pre-V18.15.5.0, is_truncated ran
        # only PRE-consolidation (via classify_bullets at post_processing.py:398,
        # called from summarizer.py:2982/2989). After _consolidate_bullets
        # (summarizer.py:3413) and the V17.6 deterministic-judge gap-fill (which
        # can ADD new bullets), truncated bullets could ship to the user
        # undetected — this was the direct cause of the V18.15.4.0 truncated
        # bullet.
        # V18.20.3.4 (RC-3, audit v182033): the flag-only policy was wrong for
        # this class. The V18.20.3.3 run flagged `[truncated/flag] bullet[38]`
        # (audit F1: the self-referential gap-fill bullet truncated mid-quote)
        # and shipped it anyway — a truncated bullet cannot be verified
        # against the source (its claim is cut), and its generation-time
        # classification already drops this class in normal mode. Now the
        # ship-time check DROPS it (severity=fix records the drop in the
        # quality report). The cosmetic period-append is removed — you cannot
        # punctuate your way out of a cut sentence.
        trunc_issues: list = []
        if bp_str.strip() and is_truncated(bp_str):
            trunc_issues = [
                Issue(
                    detector="truncated",
                    severity="fix",
                    field=label,
                    snippet=bp_str[:60],
                    detail=(
                        "dropped truncated bullet (unmatched quote/paren, no "
                        "terminal punctuation, or dangling function-word tail) — "
                        "an unverifiable cut claim"
                    ),
                )
            ]
        # Collect ALL issues so the report fully accounts for every fix/flag.
        report.issues.extend(leak1)
        report.issues.extend(space1)
        report.issues.extend(leak2)
        report.issues.extend(interp)
        report.issues.extend(extra_space)
        report.issues.extend(garbled_issues)
        report.issues.extend(grammar_issues or [])
        report.issues.extend(fragment_issues or [])
        report.issues.extend(dropped_issues or [])  # V18.20.2.0 (SWOT A19)
        report.issues.extend(name_garble_issues or [])  # V0.20.5 (brainstorm D1)
        report.issues.extend(stray_quote_issues or [])  # V0.20.5 (brainstorm D2)
        report.issues.extend(year_issues)
        report.issues.extend(attrib_issues or [])
        report.issues.extend(bold_attrib or [])
        report.issues.extend(swap_attrib or [])  # V18.20.3.0 (Audit FLAG-01)
        report.issues.extend(consist_issues or [])
        report.issues.extend(pronoun_issues or [])
        report.issues.extend(year_digit_issues or [])
        report.issues.extend(trunc_issues)
        # V18.20.3.2 (audit N1 / P0-2): ship-time self-talk drop. Generation-
        # time filtering (classify_bullets) is the primary gate, but bullets
        # can acquire self-talk later (consolidation merges, gap-fill
        # additions after the filter). A bullet containing model self-talk
        # is NEVER summary content — drop it outright (severity=fix records
        # the drop in the quality report).
        if bp_str.strip() and SELF_TALK_PATTERNS.search(bp_str):
            report.issues.append(
                Issue(
                    detector="self_talk",
                    severity="fix",
                    field=label,
                    snippet=bp_str[:60],
                    detail=(
                        "dropped model self-talk bullet (include this! / let me "
                        "add / be more specific / the source says / looking at "
                        "the text) — CoT planning note, not summary content"
                    ),
                )
            )
            continue
        # V18.20.3.2 (audit N5 / P1-c): ship-time citation-only drop.
        if bp_str.strip() and is_citation_only_fragment(bp_str):
            report.issues.append(
                Issue(
                    detector="citation_only",
                    severity="fix",
                    field=label,
                    snippet=bp_str[:60],
                    detail=(
                        "dropped citation-only fragment (no predicate, <8 "
                        "content words after citation strip) — carries no claim"
                    ),
                )
            )
            continue
        # V18.20.3.2 (audit N4 / P1-a): PRE-SHIP parenthetical-promotion
        # veto. Upgrades the D3 subject-swap class from flag-only to a real
        # drop: a bullet confirmed as a parenthetical promotion (claimed
        # author never holds an attribution verb in the matching source
        # span; a different name does; ≥30% content overlap) is a factual
        # misattribution — the judges cannot see it (high lexical overlap
        # by construction), so it must not ship.
        if source_text and bp_str.strip():
            _promo = detect_parenthetical_promotion(
                bp_str,
                source_text,
                source_authors,
            )
            if _promo:
                _claimed, _real = _promo
                report.issues.append(
                    Issue(
                        detector="parenthetical_promotion",
                        severity="fix",
                        field=label,
                        snippet=bp_str[:60],
                        detail=(
                            f"dropped misattributed bullet: '{_claimed}' is "
                            f"credited with a claim the source attributes to "
                            f"'{_real}' ('{_claimed}' appears there only as a "
                            f"citation/list item). Verified via the generation-"
                            f"time active-subject veto."
                        ),
                    )
                )
                continue
        # V18.20.3.4 (RC-3, audit v182033): ENFORCED truncation drop. The
        # flag was recorded above; a bullet whose claim is cut mid-sentence
        # cannot be verified against the source, so it must not ship. This
        # is the ship-time mirror of the generation-time conservative-gated
        # drop (classify_bullets "thinking_filter.truncated").
        if trunc_issues:
            continue
        # V18.20.3.4 (RC-1 layer 1, audit v182033): ship-time STRUCTURAL
        # QUARANTINE — the final-assembly regex stage from
        # audit/results/v182033_pipeline_root_causes.md. Generation-time
        # filtering (classify_bullets, now with the scar patterns) is the
        # primary gate, but bullets can acquire scars later (consolidation
        # merges, gap-fill paths that bypassed the filter, conclusion-bullet
        # injection). The five scar classes: checklist stubs ("Two
        # directions - covered"), summary self-assessment ("a topic the
        # summary omits entirely"), truncation markers ("(text cuts off)"),
        # bare terminal ellipsis, and verbless label stubs ("Author five
        # categories"). None of these is ever summary content; all 8
        # defective bullets in the V18.20.3.3 Key Takeaways fall in these
        # classes (F1-F6; F7 is repaired by the dropped-letter auto-fix;
        # F8 by the non-skippable dedup).
        if bp_str.strip():
            _scar = classify_scar(bp_str)
            if _scar is not None:
                _scar_detail = {
                    "checklist_stub": (
                        "dropped gap-fill checklist stub ('X - covered') — the "
                        "model ticking off its own coverage list"
                    ),
                    "summary_self_assessment": (
                        "dropped summary self-assessment ('a topic the summary "
                        "omits…') — incoherent inside the summary it describes"
                    ),
                    "truncation_marker": (
                        "dropped bullet with an explicit truncation marker "
                        "('(text cuts off)') — the model's annotation of a cut"
                    ),
                    "bare_ellipsis": (
                        "dropped bullet ending in a bare ellipsis — mid-"
                        "generation cut, unverifiable claim"
                    ),
                    "label_stub": (
                        "dropped verbless label stub (no predicate, or ends "
                        "with a bare colon introducing absent sub-content) — "
                        "names a topic but carries no claim"
                    ),
                }.get(_scar, f"dropped process-scar bullet ({_scar})")
                report.issues.append(
                    Issue(
                        detector=f"scar_{_scar}",
                        severity="fix",
                        field=label,
                        snippet=bp_str[:60],
                        detail=_scar_detail,
                    )
                )
                continue
        # Drop the bullet if it became empty after leakage stripping
        # (the entire bullet was a CoT leak with no content).
        if bp_str.strip():
            cleaned_bullets.append(bp_str)
        else:
            report.add(
                Issue(
                    detector="prompt",
                    severity="fix",
                    field=label,
                    snippet="(empty after leakage strip)",
                    detail="dropped empty bullet",
                )
            )
    report.bullets = cleaned_bullets

    # ── Executive summary ────────────────────────────────────────────────
    exec_str = executive_summary or ""
    # V18.16.0.1 (Fix 2): Run detect_cot_narrative on exec summary too.
    # The V18.16.0.0 regression: the exec-from-thorough call produced CoT
    # ("me to write a 150-250 word executive summary... Draft:...") which
    # passed through run_post_checks undetected because detect_cot_narrative
    # only ran on thorough_summary. This is the SAME class of gap that
    # V18.15.7.0 Fix 1 addressed for thorough — now applied to exec too.
    exec_str, exec_cot = detect_cot_narrative(exec_str, "exec")
    exec_str, exec_leak1 = detect_prompt_leakage(exec_str, "exec")
    exec_str, exec_space = detect_missing_spaces(
        exec_str,
        "exec",
        source_text or "",
        source_lower=_src_lower_full,
        source_words=_src_words,
    )
    exec_str, exec_leak2 = detect_prompt_leakage(exec_str, "exec")
    # V18.2.17 Fix 5: interpretive-leap strip/flag.
    exec_str, exec_interp = detect_interpretive_leaps(
        exec_str, "exec", source_text, source_lower=_src_lower
    )
    # V18.2.19 Improvement 1: extra-space detector.
    exec_str, exec_extra = detect_extra_spaces(
        exec_str,
        "exec",
        source_text or "",
        source_lower=_src_lower_full,
        source_words=_src_words,
    )
    _, exec_garbled = detect_garbled_tokens(
        exec_str, "exec", source_text or "", source_words=_src_words
    )
    # V18.2.18 Improvement 2: grammatical coherence.
    _, exec_grammar = detect_grammatical_incoherence(exec_str, "exec")
    # V18.2.19 Improvement 2: word-fragment merge.
    _, exec_fragment = detect_word_fragment_merge(
        exec_str, "exec", source_text or "", source_words=_src_words
    )
    exec_str, exec_dropped = detect_dropped_letter_garble(
        exec_str, "exec", source_text or "", source_words=_src_words, auto_repair=auto_repair_garble
    )  # V18.20.3.4 (RC-3): capture auto-repairs; V0.03: guarded + default-off
    exec_str, exec_name_garble = detect_and_repair_author_garbles(
        exec_str, "exec", source_authors
    )  # V0.20.5 (brainstorm D1)
    exec_str, exec_stray_quotes = repair_stray_quotes(exec_str, "exec")  # V0.20.5 (brainstorm D2)
    _, exec_year = validate_years(exec_str, "exec", source_authors)
    # V18.2.17 Fix 7: attribution verification.
    _, exec_attrib = (
        verify_attribution(
            exec_str, source_text or "", "exec", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.2.18 Improvement 1: bold-name attribution check.
    _, exec_bold = (
        verify_bold_name_attribution(
            exec_str, source_text or "", "exec", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.20.3.0 (Audit FLAG-01): subject-swap attribution check.
    _, exec_swap = (
        detect_attribution_subject_swap(
            exec_str, source_text or "", "exec", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.2.17 Fix 6: hedge-loss check.
    _, exec_hedge = (
        detect_hedge_loss(exec_str, source_text or "", "exec") if source_text else (None, [])
    )
    # V18.2.17 Fix 8: consistency check.
    _, exec_consist = (
        detect_inconsistency(exec_str, source_text or "", "exec", source_lower=_src_lower)
        if source_text
        else (None, [])
    )
    # V18.2.19 Improvement 3: pronoun mismatch.
    _, exec_pronoun = (
        detect_pronoun_mismatch(
            exec_str,
            source_text or "",
            "exec",
            source_lower=_src_lower,
            source_authors=source_authors,
        )
        if source_text
        else (None, [])
    )
    # V18.2.28 (regression fix): dropped-digit year check for exec summary.
    exec_str, exec_year_digit = (
        detect_dropped_digit_years(exec_str, source_text or "", "exec")
        if source_text
        else (exec_str, [])
    )
    report.issues.extend(exec_cot)  # V18.16.0.1 (Fix 2): CoT-narrative detector for exec
    report.issues.extend(exec_leak1)
    report.issues.extend(exec_space)
    report.issues.extend(exec_leak2)
    report.issues.extend(exec_interp)
    report.issues.extend(exec_extra)
    report.issues.extend(exec_garbled)
    report.issues.extend(exec_grammar or [])
    report.issues.extend(exec_fragment or [])
    report.issues.extend(exec_dropped or [])
    report.issues.extend(exec_name_garble or [])  # V0.20.5 (brainstorm D1)
    report.issues.extend(exec_stray_quotes or [])  # V0.20.5 (brainstorm D2)
    report.issues.extend(exec_year)
    report.issues.extend(exec_attrib or [])
    report.issues.extend(exec_bold or [])
    report.issues.extend(exec_swap or [])  # V18.20.3.0 (Audit FLAG-01)
    report.issues.extend(exec_hedge or [])
    report.issues.extend(exec_consist or [])
    report.issues.extend(exec_pronoun or [])
    report.issues.extend(exec_year_digit or [])
    report.executive_summary = exec_str

    # ── Thorough summary ─────────────────────────────────────────────────
    tho_str = thorough_summary or ""
    # V18.15.7.0 (Fix 1): CoT-narrative detector — runs BEFORE
    # detect_prompt_leakage. If the thorough_summary is the model's
    # chain-of-thought narrative (>= 3 CoT markers), truncate to empty.
    # The V18.15.6.0 golden-master produced a 4346-word thorough_summary
    # that was 100% CoT ("Let me organize my understanding...", "Named
    # contributors in order:", "Let me count carefully.", etc.).
    # detect_prompt_leakage strips individual phrases but leaves the CoT
    # scaffolding — this detector catches the SUSTAINED pattern.
    tho_str, tho_cot = detect_cot_narrative(tho_str, "thorough")
    tho_str, tho_leak1 = detect_prompt_leakage(tho_str, "thorough")
    tho_str, tho_space = detect_missing_spaces(
        tho_str,
        "thorough",
        source_text or "",
        source_lower=_src_lower_full,
        source_words=_src_words,
    )
    tho_str, tho_leak2 = detect_prompt_leakage(tho_str, "thorough")
    # V18.2.17 Fix 5: interpretive-leap strip/flag.
    tho_str, tho_interp = detect_interpretive_leaps(
        tho_str, "thorough", source_text, source_lower=_src_lower
    )
    # V18.2.19 Improvement 1: extra-space detector.
    tho_str, tho_extra = detect_extra_spaces(
        tho_str,
        "thorough",
        source_text or "",
        source_lower=_src_lower_full,
        source_words=_src_words,
    )
    _, tho_garbled = detect_garbled_tokens(
        tho_str, "thorough", source_text or "", source_words=_src_words
    )
    # V18.2.18 Improvement 2: grammatical coherence.
    _, tho_grammar = detect_grammatical_incoherence(tho_str, "thorough")
    # V18.2.19 Improvement 2: word-fragment merge.
    _, tho_fragment = detect_word_fragment_merge(
        tho_str, "thorough", source_text or "", source_words=_src_words
    )
    tho_str, tho_dropped = detect_dropped_letter_garble(
        tho_str,
        "thorough",
        source_text or "",
        source_words=_src_words,
        auto_repair=auto_repair_garble,
    )  # V18.20.3.4 (RC-3): capture auto-repairs; V0.03: guarded + default-off
    tho_str, tho_name_garble = detect_and_repair_author_garbles(
        tho_str, "thorough", source_authors
    )  # V0.20.5 (brainstorm D1)
    tho_str, tho_stray_quotes = repair_stray_quotes(tho_str, "thorough")  # V0.20.5 (brainstorm D2)
    _, tho_year = validate_years(tho_str, "thorough", source_authors)
    # V18.2.17 Fix 7: attribution verification.
    _, tho_attrib = (
        verify_attribution(
            tho_str, source_text or "", "thorough", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.2.18 Improvement 1: bold-name attribution check.
    _, tho_bold = (
        verify_bold_name_attribution(
            tho_str, source_text or "", "thorough", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.20.3.0 (Audit FLAG-01): subject-swap attribution check.
    _, tho_swap = (
        detect_attribution_subject_swap(
            tho_str, source_text or "", "thorough", source_authors, source_lower=_src_lower
        )
        if source_text
        else (None, [])
    )
    # V18.2.17 Fix 6: hedge-loss check.
    _, tho_hedge = (
        detect_hedge_loss(tho_str, source_text or "", "thorough") if source_text else (None, [])
    )
    # V18.2.17 Fix 8: consistency check.
    _, tho_consist = (
        detect_inconsistency(tho_str, source_text or "", "thorough", source_lower=_src_lower)
        if source_text
        else (None, [])
    )
    # V18.2.19 Improvement 3: pronoun mismatch.
    _, tho_pronoun = (
        detect_pronoun_mismatch(
            tho_str,
            source_text or "",
            "thorough",
            source_lower=_src_lower,
            source_authors=source_authors,
        )
        if source_text
        else (None, [])
    )
    # V18.2.28 (regression fix): dropped-digit year check for thorough summary.
    tho_str, tho_year_digit = (
        detect_dropped_digit_years(tho_str, source_text or "", "thorough")
        if source_text
        else (tho_str, [])
    )
    report.issues.extend(tho_cot)  # V18.15.7.0 (Fix 1): CoT-narrative detector
    report.issues.extend(tho_leak1)
    report.issues.extend(tho_space)
    report.issues.extend(tho_leak2)
    report.issues.extend(tho_interp)
    report.issues.extend(tho_extra)
    report.issues.extend(tho_garbled)
    report.issues.extend(tho_grammar or [])
    report.issues.extend(tho_fragment or [])
    report.issues.extend(tho_dropped or [])
    report.issues.extend(tho_name_garble or [])  # V0.20.5 (brainstorm D1)
    report.issues.extend(tho_stray_quotes or [])  # V0.20.5 (brainstorm D2)
    report.issues.extend(tho_year)
    report.issues.extend(tho_attrib or [])
    report.issues.extend(tho_bold or [])
    report.issues.extend(tho_swap or [])  # V18.20.3.0 (Audit FLAG-01)
    report.issues.extend(tho_hedge or [])
    report.issues.extend(tho_consist or [])
    report.issues.extend(tho_pronoun or [])
    report.issues.extend(tho_year_digit or [])
    report.thorough_summary = tho_str

    # ── Key Distinctions + Theoretical Tensions (V18.15.3.4) ──────────
    # These additive sections are generated by the same LLM call as the
    # bullets/exec/thorough, so they can have the SAME truncation + split-
    # word defects. The V18.15.3.2 audit found 2 truncated items in
    # Theoretical Tensions that is_truncated() would have caught. Now we
    # run the same detect_extra_spaces + detect_missing_spaces chain on
    # these sections. We also run is_truncated() on each line and drop
    # truncated lines (conservative-gated: logged but kept if conservative).
    for _section_name, _section_text in [
        ("key_distinctions", key_distinctions),
        ("theoretical_tensions", theoretical_tensions),
    ]:
        if not _section_text:
            continue
        _sec = _section_text
        # Run the same auto-fixing detectors as exec/thorough
        _sec, _sec_leak = detect_prompt_leakage(_sec, _section_name)
        _sec, _sec_space = detect_missing_spaces(
            _sec,
            _section_name,
            source_text or "",
            source_lower=_src_lower_full,
            source_words=_src_words,
        )
        _sec, _sec_leak2 = detect_prompt_leakage(_sec, _section_name)
        _sec, _sec_extra = detect_extra_spaces(
            _sec,
            _section_name,
            source_text or "",
            source_lower=_src_lower_full,
            source_words=_src_words,
        )
        report.issues.extend(_sec_leak)
        report.issues.extend(_sec_space)
        report.issues.extend(_sec_leak2)
        report.issues.extend(_sec_extra)
        # V18.15.3.4: Truncation check on each line of the section.
        # These sections are often bullet-like (one item per line).
        # V18.20.3.1 (real-rig audit D1): DROP truncated lines (was: keep +
        # cosmetic period-append). The V18.20.3.0 rig-test
        # shipped a bullet with an unmatched parenthetical mid-citation
        # affectively charged." — a distinction missing its entire contrast
        # half is noise, not content (unlike a bullet, where "more bullets >
        # lower coverage" argues for keeping). The drop is recorded as a
        # severity="fix" issue so the quality report accounts for it.
        # V18.15.5.0: is_truncated now imported at module top (also used in
        # the bullet loop above — see DEBT-07 / Known Issue #3 fix).
        _lines = _sec.split("\n")
        _clean_lines = []
        for _line in _lines:
            _line_stripped = _line.strip().lstrip("-•* ").strip()
            if _line_stripped and is_truncated(_line_stripped):
                report.issues.append(
                    Issue(
                        detector="truncated",
                        severity="fix",
                        field=_section_name,
                        snippet=_line_stripped[:60],
                        detail=(
                            f"dropped truncated line in {_section_name} (unmatched "
                            f"quote/paren, dangling tail, or no terminal punctuation — "
                            f"an additive item missing its contrast half is noise)"
                        ),
                    )
                )
                continue  # drop the truncated line entirely
            _clean_lines.append(_line)
        _sec = "\n".join(_clean_lines)
        setattr(report, _section_name, _sec)

    # ── V0.05 (rig audit F8 — P3): verbatim-quote verification ───────────
    # Model-typed quotes are verified as NORMALIZED substrings of the source
    # (case/whitespace/punctuation-insensitive). A span that fails ships as
    # a paraphrase (quotes stripped) instead of a misquote — the V0.04 rig
    # quoted "it should never happen…" where the source reads "this should
    # never happen…". Verbatim excerpts from _find_source_sentence are
    # already exact; this targets model-typed quotation marks.
    def _quote_norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

    _src_quote_norm = _quote_norm(source_text or "")
    if _src_quote_norm:
        _QUOTE_SPAN_RE = re.compile(r'[“"]([^“”"\n]{20,})[”"]')

        def _verify_quotes(text: str, field: str) -> str:
            if not text or '"' not in text and "“" not in text:
                return text
            out = text
            for _m in list(_QUOTE_SPAN_RE.finditer(text)):
                _span = _m.group(1)
                if len(_span.split()) < 4:
                    continue  # short quotes: single-word/phrase quotes are paraphrase-safe
                if _quote_norm(_span) not in _src_quote_norm:
                    # failing span: strip the quotation marks, keep the words
                    out = out.replace(_m.group(0), _span, 1)
                    report.issues.append(
                        Issue(
                            detector="quote_verification",
                            severity="fix",
                            field=field,
                            snippet=_span[:60],
                            detail=(
                                "quoted span is not verbatim in the source — shipped "
                                "as a paraphrase (quotation marks stripped) instead "
                                "of a misquote"
                            ),
                        )
                    )
            return out

        report.bullets = [_verify_quotes(b, f"bullet[{i}]") for i, b in enumerate(report.bullets)]
        report.executive_summary = _verify_quotes(report.executive_summary, "exec")
        report.thorough_summary = _verify_quotes(report.thorough_summary, "thorough")
        report.key_distinctions = _verify_quotes(report.key_distinctions, "key_distinctions")
        report.theoretical_tensions = _verify_quotes(
            report.theoretical_tensions, "theoretical_tensions"
        )

        # ── V0.06 (rig audit F6): trailing-quote dedupe + byline strip ────
        # GENERAL RULE: a bullet states its claim ONCE. Two rig leak shapes:
        #   (a) DUPLICATED QUOTE — the claim embeds a quote inline and the
        #       generation template APPENDS the same quote again at the end:
        #       'Borwankar explicitly states that such decisions "very rarely
        #       result in happy outcomes," a direct causal claim … "Such
        #       decisions very rarely result in happy outcomes."'
        #       → the trailing span is stripped when its normalized text is
        #       already contained in the rest of the bullet.
        #   (b) BYLINE ECHO — a trailing quoted "By <Author>" used as
        #       evidence ('The chapter is authored by Neal Ford, who argues
        #       … "By Neal Ford"'). A byline is attribution metadata, never
        #       a content quote — the span is stripped regardless of
        #       containment.
        _BYLINE_SPAN_RE = re.compile(r"^\s*By\s+[A-Z][\w\'’-]*(?:\s+[A-Z][\w\'’-]*){0,3}\.?\s*$")
        _TRAILING_QUOTE_SPAN_RE = re.compile(r'["\u201c]([^"\u201d\n]{4,400})["\u201d]\s*[.!]?\s*$')

        def _strip_trailing_quote_dup(text: str, field: str) -> str:
            if not text or not text.strip():
                return text
            m = _TRAILING_QUOTE_SPAN_RE.search(text.rstrip())
            if not m:
                return text
            span = m.group(1).strip()
            rest = text.rstrip()[: m.start()].rstrip().rstrip(",;:—–-").rstrip()
            if not span or not rest:
                return text
            if _BYLINE_SPAN_RE.match(span):
                report.issues.append(
                    Issue(
                        detector="quote_dedupe",
                        severity="fix",
                        field=field,
                        snippet=span[:60],
                        detail=(
                            "stripped trailing byline quote (\u201cBy <Author>\u201d) — "
                            "attribution metadata quoted as evidence, not content"
                        ),
                    )
                )
                return rest
            if _quote_norm(span) and _quote_norm(span) in _quote_norm(rest):
                report.issues.append(
                    Issue(
                        detector="quote_dedupe",
                        severity="fix",
                        field=field,
                        snippet=span[:60],
                        detail=(
                            "stripped trailing duplicate quote — the same span "
                            "is already quoted/embedded in the bullet"
                        ),
                    )
                )
                return rest
            return text

        report.bullets = [
            _strip_trailing_quote_dup(b, f"bullet[{i}]") for i, b in enumerate(report.bullets)
        ]

    # ── V0.05 (rig audit F6 — P2): ship-time near-duplicate removal ──────
    # Normalized token-set containment >= 0.8 → keep the FIRST, drop the
    # rest. The V0.04 rig shipped 36 bullets for a ~430-word chapter with
    # >=3 near-duplicate pairs ("moments of emotional tension → mutually
    # agreed-upon goals" appearing twice, etc.) — gap-fill dedup was
    # exact-prefix-only and the semantic-dedup phase is skippable. Content
    # words only (len > 2), so function words never drive a match.
    def _content_tokens(s: str) -> frozenset:
        # light plural normalization (developer/developers, conversation/
        # conversations) — mirrors summary_validator's plural tolerance so
        # inflection alone never defeats the near-dup detector.
        _out = set()
        for w in re.findall(r"[a-z0-9]+", s.lower()):
            if len(w) <= 2:
                continue
            if len(w) > 3 and w.endswith("s"):
                _out.add(w[:-1])
            _out.add(w)
        return frozenset(_out)

    _seen_token_sets: list[tuple[frozenset, int]] = []
    _deduped_bullets: list[str] = []
    for _i, _b in enumerate(report.bullets):
        _toks = _content_tokens(_b)
        _dup_of = None
        if len(_toks) >= 4:  # very short bullets: token sets too small to judge
            for _prev, _pi in _seen_token_sets:
                _inter = len(_toks & _prev)
                if _inter and _inter / min(len(_toks), len(_prev)) >= 0.8:
                    _dup_of = _pi
                    break
        if _dup_of is not None:
            report.issues.append(
                Issue(
                    detector="near_duplicate",
                    severity="fix",
                    field=f"bullet[{_i}]",
                    snippet=_b[:60],
                    detail=(
                        f"near-duplicate of bullet[{_dup_of}] (token-set "
                        f"containment >= 0.8) — kept the first, dropped this one"
                    ),
                )
            )
            continue
        _seen_token_sets.append((_toks, _i))
        _deduped_bullets.append(_b)
    if len(_deduped_bullets) != len(report.bullets):
        report.bullets = _deduped_bullets

    # Recompute counts from the issues list (some detectors add issues
    # directly via .add(), others via extend()).
    report.fixed_count = sum(1 for i in report.issues if i.severity == "fix")
    report.flagged_count = sum(1 for i in report.issues if i.severity == "flag")

    return report


# ── Helpers ───────────────────────────────────────────────────────────────


# V18.18.0.2: _snippet moved to postcheck_detectors.py (re-exported via import *)
# ═══════════════════════════════════════════════════════════════════════════
# V18.2.25 (Phase 4.3) — Hallucination hardening: consistency cross-checks
# ═══════════════════════════════════════════════════════════════════════════

# Two new deterministic, book-agnostic checks:
# 1. detect_exec_bullet_inconsistency — exec-summary claims must be a subset
#    of bullet-claims (if the exec says X but no bullet mentions X, that's
#    either a hallucination in the exec or an omission in the bullets).
# 2. detect_citation_coverage_gap — if the source names N authors and the
#    summary names <N*0.8, flag for review (extends the existing bold-name-
#    attribution check with a quantitative coverage gate).

# Pattern for extracting named authors: Capitalized word optionally followed
# by a year in parentheses. This is the same pattern used by the existing
# attribution checks.

# V18.18.0.2: _is_subsequence moved to postcheck_detectors.py (re-exported via import *)
