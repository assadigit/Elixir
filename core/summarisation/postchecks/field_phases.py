"""V0.4.19 — per-field post-check phases (bullets/exec/thorough), extracted
VERBATIM from orchestrator.run_post_checks. Issue order preserved exactly.

V0.4.19 (de-monolithization): run_post_checks keeps the V18.20.2.0 (SWOT A24)
precompute block and threads the shared source-derived values into these
phases via :class:`PhaseCtx` (built once per run). The three detector chains
below are byte-identical to the sections they replaced — same detector order,
same fix/flag policy, same ``report.issues`` ordering — so behavior is
unchanged. The padding-bullet helper moved here with the bullets phase (its
only consumer); orchestrator.py re-exports it for the historical facade.

The KD/TT section, verbatim-quote verification and the ship-time
content-token dedupe + padding filter stayed in run_post_checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.summarisation.post_processing import (
    SELF_TALK_PATTERNS,
    classify_scar,
    is_citation_only_fragment,
    is_truncated,
)
from core.summarisation.postchecks.attribution import (
    detect_attribution_subject_swap,
    detect_dropped_digit_years,
    detect_parenthetical_promotion,
    validate_years,
    verify_attribution,
    verify_bold_name_attribution,
)
from core.summarisation.postchecks.coherence import (
    detect_hedge_loss,
    detect_inconsistency,
    detect_interpretive_leaps,
    detect_pronoun_mismatch,
)
from core.summarisation.postchecks.garble import (
    detect_and_repair_author_garbles,
    detect_dropped_letter_garble,
    detect_extra_spaces,
    detect_garbled_tokens,
    detect_grammatical_incoherence,
    detect_missing_spaces,
    detect_multi_author_conflation,
    detect_sentence_fusion,
    detect_word_fragment_merge,
    repair_stray_quotes,
    repair_stray_quotes_v2,
)
from core.summarisation.postchecks.leakage import (
    detect_cot_narrative,
    detect_prompt_leakage,
)
from core.summarisation.postchecks.shared import Issue, PostCheckReport

# V0.4.19 (de-monolithization): moved VERBATIM from orchestrator.py — the
# bullets phase is its only consumer.
# V0.4.3 (audit D5): padding-bullet suppression patterns.
# These are gap-fill artifacts that convey no substantive claim, only
# co-citation. Content-agnostic — the patterns match the SHAPE of the
# bullet, not specific author names.
_PADDING_PATTERNS = [
    # "no specific contribution... is explicitly attributed to X"
    "no specific contribution",
    # "X's contribution is not clearly discernible from the provided source"
    "not clearly discernible",
    "not clearly discernable",
    # "X is cited in the source text alongside other ... references"
    "is cited in the source text alongside",
    "is cited alongside other authors as having",
    "cited alongside other",
]


def _is_padding_bullet(bullet: str) -> bool:
    """V0.4.3 (audit D5): return True if the bullet is a gap-fill padding
    artifact (no substantive claim, only co-citation).

    Content-agnostic: matches the SHAPE of the bullet, not specific
    author names. The patterns cover the 3 forms observed in the V0.4.2
    NPD output (Waals, Ayyedura-jo, Walsh bullets).
    """
    if not bullet:
        return False
    b_lower = bullet.lower()
    return any(p in b_lower for p in _PADDING_PATTERNS)


@dataclass(frozen=True)
class PhaseCtx:
    """V0.4.19 — the shared source-derived values run_post_checks precomputes
    ONCE per run (V18.20.2.0 / SWOT A24) and threads into the per-field
    phases, so no detector call rebuilds them.

    Attribute names keep the historical semantic names (the orchestrator
    locals they carry): ``source_text`` (param), ``source_lower`` (was
    ``_src_lower``, the 200k-char-capped lowercased source),
    ``source_lower_full`` (was ``_src_lower_full``), ``source_words`` (was
    ``_src_words``), ``source_authors``, ``auto_repair_garble`` (param).
    """

    source_text: str | None
    source_lower: str
    source_lower_full: str
    source_words: set
    source_authors: list[str] | None
    auto_repair_garble: bool


def postcheck_bullets(
    bullets: list[str],
    ctx: PhaseCtx,
    report: PostCheckReport,
    enum_guarantee_texts: list[str] | None = None,
) -> list[str]:
    """V0.4.19 — the former "── Bullets ──" section of run_post_checks,
    moved VERBATIM (see the module docstring). Runs the per-bullet detector
    chain, appends every fix/flag Issue to ``report.issues`` in the exact
    historical order and returns the cleaned bullet list (the caller
    assigns ``report.bullets``).

    V0.4.24 (audit backlog #3 — the Stern escape): ``enum_guarantee_texts``
    carries the exact texts of the enumeration-guarantee bullets (stashed
    by ``SummarizerAdditiveMixin._ensure_enumeration_bullets``). Those
    bullets are EXEMPT from the truncation drop — their items are verbatim
    source text, verifiable against the source, so the "unverifiable cut
    claim" rationale does not apply. The exemption is logged as a
    severity="flag" Issue (never a silent pass); every other drop path is
    unchanged.
    """
    # V0.4.19: re-bind the shared precomputed values from the ctx (the
    # SWOT A24 precompute stays in run_post_checks); the original local
    # names are kept so the moved body below is byte-identical.
    source_text = ctx.source_text
    _src_lower = ctx.source_lower
    _src_lower_full = ctx.source_lower_full
    _src_words = ctx.source_words
    source_authors = ctx.source_authors
    auto_repair_garble = ctx.auto_repair_garble
    # ── Bullets ──────────────────────────────────────────────────────────
    cleaned_bullets: list[str] = []
    # V0.4.24 (audit backlog #3): the exact texts of the enumeration-
    # guarantee bullets (stashed by _ensure_enumeration_bullets). Matched
    # against the ORIGINAL bullet text (before any detector repairs it) so
    # a space/quote repair never breaks the exemption match.
    _guarantee_set = {str(t).strip() for t in (enum_guarantee_texts or []) if t}
    # V0.4.39 (Option A): lazy Settings for the per-bullet garble LLM-repair
    # (constructed only if a garble is flagged on a bullet — bounded no-op
    # otherwise). Mirrors the thorough wiring.
    _garble_settings = None
    for i, bp in enumerate(bullets or []):
        bp_str = str(bp) if bp else ""
        _enum_guarantee = bp_str.strip() in _guarantee_set
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
        # V0.4.3 (audit D4): sentence-fusion garble — catches
        # "praiseity"-class fusions that word_fragment_merge misses.
        # V0.5.4 (Track C2): detect_sentence_fusion now returns
        # (possibly-rewritten) text + issues. V0.5.10 (Track C4):
        # CAPTURE the returned text (was `_, fusion_issues = ...` —
        # the V0.4.3 flag-only discard) so the V0.5.4 rewrite (the
        # "ego-syntonically personalities" → "ego-syntonic
        # personalities" grammatical garble) actually propagates to
        # the shipped bullet AND to subsequent detectors (the dropped-
        # letter detector + the LLM repair + the author-garble + the
        # stray-quote repair) so they see the corrected text, not the
        # garbled original. Issue list is still collected the same way.
        bp_str, fusion_issues = detect_sentence_fusion(
            bp_str, label, source_text or "", source_words=_src_words
        )
        fragment_issues = (fragment_issues or []) + (fusion_issues or [])
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
        # V0.4.39 (Option A): LLM semantic repair for flagged garbles
        # (per-bullet). Mirrors the thorough wiring. Fires only when a
        # garble is flagged on THIS bullet (bounded — no-op on clean
        # bullets). Content-agnostic (Rule 1 — the prompt is about token
        # repair; works on any chapter). Fail-open; D3-style guard.
        _bp_garble_flags = (fragment_issues or []) + (dropped_issues or [])
        if _bp_garble_flags:
            if _garble_settings is None:
                from utils.settings import Settings as _BSettings

                _garble_settings = _BSettings()
            _bg_model = _garble_settings.get("summarisation.model", "") or _garble_settings.get(
                "summarisation.primary_model", ""
            )
            if _bg_model:
                from core.summarisation.postchecks.garble import repair_garbles_via_llm

                bp_str, _bp_garble_repair = repair_garbles_via_llm(
                    bp_str, label, source_text or "", _src_words, _garble_settings
                )
                report.issues.extend(_bp_garble_repair or [])
        # V0.20.5 (brainstorm D1): cross-check author surnames against the
        # source author list — auto-repair edit-distance-1 garbles (e.g., a
        # dropped letter in a cited author's surname). Content-agnostic: the
        # source author list comes from the runtime analysis.
        bp_str, name_garble_issues = detect_and_repair_author_garbles(bp_str, label, source_authors)
        # V0.20.5 (brainstorm D2): repair stray/misplaced double-quotes.
        bp_str, stray_quote_issues = repair_stray_quotes(bp_str, label)
        # V0.20.6 (brainstorm D2+): extend to even-count mismatches (HTML-
        # attribute-aware state machine + long-span pair flag). Content-
        # agnostic; runs after v0.20.5 to catch the bug class v0.20.5 misses.
        bp_str, stray_quote_v2_issues = repair_stray_quotes_v2(bp_str, label)
        stray_quote_issues = (stray_quote_issues or []) + (stray_quote_v2_issues or [])
        # V0.4.23: source_text threaded for the raw-source verbatim exemption
        # (text-quoted-name class — see validate_years docstring).
        _, year_issues = validate_years(bp_str, label, source_authors, source_text or "")
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
            if _enum_guarantee:
                # V0.4.24 (audit backlog #3 — the Stern escape): the
                # guarantee bullet LOOKS truncated (a source item cut at a
                # paragraph break, an odd quote inside a verbatim item) —
                # but its items are verbatim source text, verifiable
                # against the source. EXEMPT from the drop; flag visibly.
                # The V4.23 run dropped exactly this class (a guarantee
                # bullet whose mid-word-sliced label and cut final item
                # tripped every truncation heuristic at once) and silently
                # lost 4 enumerated items.
                trunc_issues = [
                    Issue(
                        detector="truncated",
                        severity="flag",
                        field=label,
                        snippet=bp_str[:60],
                        detail=(
                            "enumeration-guarantee bullet LOOKS truncated — "
                            "EXEMPT from the truncation drop (V0.4.24): its "
                            "items are verbatim source text, verifiable "
                            "against the source; no postcheck may silently "
                            "drop a guaranteed bullet"
                        ),
                    )
                ]
            else:
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
        # V0.4.24: enumeration-guarantee bullets are exempt (severity=flag
        # above) — verbatim source items are verifiable by construction.
        if trunc_issues and trunc_issues[0].severity == "fix":
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
        # V0.4.3 (audit D5): drop "padding bullets" — gap-fill artifacts
        # that convey no substantive claim, only co-citation. The V0.4.2
        # NPD output shipped 4 of these (Waals, Tyson, Byrne, Walsh,
        # Ayyedura-jo). They satisfy the "theorist floor" coverage
        # counter but add noise for the reader. Content-agnostic patterns:
        #   - "no specific contribution... is explicitly attributed to X"
        #   - "not clearly discernible from the provided source"
        #   - "is cited in the source text alongside other ... references"
        if _is_padding_bullet(bp_str):
            report.issues.append(
                Issue(
                    detector="padding_bullet",
                    severity="fix",
                    field=label,
                    snippet=bp_str[:60],
                    detail=(
                        "dropped padding bullet (gap-fill artifact with no "
                        "substantive claim, only co-citation)"
                    ),
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
    return cleaned_bullets


def postcheck_exec(executive_summary: str, ctx: PhaseCtx, report: PostCheckReport) -> str:
    """V0.4.19 — the former "── Executive summary ──" section of
    run_post_checks, moved VERBATIM (see the module docstring). Extends
    ``report.issues`` exactly as before and returns the cleaned exec
    string (the caller assigns ``report.executive_summary``).
    """
    # V0.4.19: re-bind the shared precomputed values from the ctx (the
    # SWOT A24 precompute stays in run_post_checks); the original local
    # names are kept so the moved body below is byte-identical.
    source_text = ctx.source_text
    _src_lower = ctx.source_lower
    _src_lower_full = ctx.source_lower_full
    _src_words = ctx.source_words
    source_authors = ctx.source_authors
    auto_repair_garble = ctx.auto_repair_garble
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
    # V0.4.3 (audit D4): sentence-fusion garble.
    # V0.5.10 (Track C4): CAPTURE the returned text (was
    # `_, exec_fusion = ...` — the V0.4.3 flag-only discard) so the
    # V0.5.4 (Track C2) rewrite (the "ego-syntonically personalities"
    # → "ego-syntonic personalities" grammatical garble) actually
    # propagates to the shipped exec AND to subsequent detectors (the
    # dropped-letter detector + the LLM repair + the author-garble +
    # the stray-quote repair) so they see the corrected text, not the
    # garbled original. Issue list is still collected the same way.
    exec_str, exec_fusion = detect_sentence_fusion(
        exec_str, "exec", source_text or "", source_words=_src_words
    )
    exec_fragment = (exec_fragment or []) + (exec_fusion or [])
    exec_str, exec_dropped = detect_dropped_letter_garble(
        exec_str, "exec", source_text or "", source_words=_src_words, auto_repair=auto_repair_garble
    )  # V18.20.3.4 (RC-3): capture auto-repairs; V0.03: guarded + default-off
    # V0.4.39 (Option A): LLM semantic repair for flagged garbles (exec).
    # Mirrors the thorough wiring. Fires only when a garble is flagged on
    # the exec (bounded — no-op on clean exec). Content-agnostic (Rule 1).
    _exec_garble_flags = (exec_fragment or []) + (exec_dropped or [])
    if _exec_garble_flags:
        from utils.settings import Settings as _ESettings

        _egs = _ESettings()
        _eg_model = _egs.get("summarisation.model", "") or _egs.get(
            "summarisation.primary_model", ""
        )
        if _eg_model:
            from core.summarisation.postchecks.garble import repair_garbles_via_llm

            exec_str, _exec_garble_repair = repair_garbles_via_llm(
                exec_str, "exec", source_text or "", _src_words, _egs
            )
            report.issues.extend(_exec_garble_repair or [])
    exec_str, exec_name_garble = detect_and_repair_author_garbles(
        exec_str, "exec", source_authors
    )  # V0.20.5 (brainstorm D1)
    exec_str, exec_stray_quotes = repair_stray_quotes(exec_str, "exec")  # V0.20.5 (brainstorm D2)
    # V0.20.6 (brainstorm D2+): even-count mismatches + long-span flag.
    exec_str, exec_stray_quotes_v2 = repair_stray_quotes_v2(exec_str, "exec")
    exec_stray_quotes = (exec_stray_quotes or []) + (exec_stray_quotes_v2 or [])
    # V0.4.23: raw-source verbatim exemption (see validate_years docstring).
    _, exec_year = validate_years(exec_str, "exec", source_authors, source_text or "")
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
    return exec_str


def postcheck_thorough(thorough_summary: str, ctx: PhaseCtx, report: PostCheckReport) -> str:
    """V0.4.19 — the former "── Thorough summary ──" section of
    run_post_checks, moved VERBATIM (see the module docstring). Extends
    ``report.issues`` exactly as before and returns the cleaned thorough
    string (the caller assigns ``report.thorough_summary``).
    """
    # V0.4.19: re-bind the shared precomputed values from the ctx (the
    # SWOT A24 precompute stays in run_post_checks); the original local
    # names are kept so the moved body below is byte-identical.
    source_text = ctx.source_text
    _src_lower = ctx.source_lower
    _src_lower_full = ctx.source_lower_full
    _src_words = ctx.source_words
    source_authors = ctx.source_authors
    auto_repair_garble = ctx.auto_repair_garble
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
    # V0.4.3 (audit D4): sentence-fusion garble — the V0.4.2 NPD thorough
    # shipped two fusions (praiseity, self-developmentstic); this catches
    # them. Flag-only.
    # V0.5.10 (Track C4): CAPTURE the returned text (was `_, tho_fusion
    # = ...` — the V0.4.3 flag-only discard) so the V0.5.4 (Track C2)
    # rewrite (the "ego-syntonically personalities" → "ego-syntonic
    # personalities" grammatical garble) actually propagates to the
    # shipped thorough AND to subsequent detectors (the dropped-letter
    # detector + the author-garble + the stray-quote repair + the D3
    # LLM repair) so they see the corrected text, not the garbled
    # original. Issue list is still collected the same way.
    tho_str, tho_fusion = detect_sentence_fusion(
        tho_str, "thorough", source_text or "", source_words=_src_words
    )
    tho_fragment = (tho_fragment or []) + (tho_fusion or [])
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
    # V0.20.6 (brainstorm D2+): even-count mismatches + long-span flag.
    # The thorough is the highest-risk field for this bug class (long
    # paragraphs with many inline citations + quoted phrases; HTML
    # attribute quotes from <em>YEAR</em> inflate the count and mask
    # imbalances). The V0.4.1 NPD thorough shipped with 4 such mismatches.
    tho_str, tho_stray_quotes_v2 = repair_stray_quotes_v2(tho_str, "thorough")
    tho_stray_quotes = (tho_stray_quotes or []) + (tho_stray_quotes_v2 or [])
    # V0.4.11/V0.4.13 (audit item #4): semantic LLM repair for D3 long-span
    # quote pairs. If D3 flags are present, send the thorough to the LLM with
    # a "fix the quote pairing" prompt. Fail-open: if LLM fails, text is
    # unchanged. V0.4.13: now uses the provider abstraction (works with both
    # Ollama AND llama.cpp backends — the V0.4.11 version used the Ollama-
    # specific /api/generate which silently failed on llama.cpp).
    _d3_flags = [i for i in (tho_stray_quotes_v2 or []) if i.detector == "stray_quote_v2_d3"]
    if _d3_flags:
        from utils.settings import Settings as _Settings

        _s = _Settings()
        _model = _s.get("summarisation.model", "") or _s.get("summarisation.primary_model", "")
        if _model:
            from core.summarisation.postchecks.garble import repair_d3_quotes_via_llm

            tho_str, d3_issues = repair_d3_quotes_via_llm(
                tho_str, "thorough", source_text or "", _s
            )
            tho_stray_quotes = (tho_stray_quotes or []) + (d3_issues or [])
    # V0.4.39 (Option A): LLM semantic repair for flagged garbles
    # (fragment_merge + dropped_letter). Mirrors the V0.4.11/V0.4.13 D3
    # stray-quote LLM-repair pattern above. General — catches any garble
    # on any chapter; content-agnostic (Rule 1 — the prompt is about token
    # repair, not content). Fail-open; D3-style guard (keep the original
    # if the repair doesn't reduce the garble flag count). Fires only when
    # the postcheck flagged a garble, so it's bounded (no-op on clean text).
    _garble_flags = (tho_fragment or []) + (tho_dropped or [])
    if _garble_flags:
        from utils.settings import Settings as _GSettings

        _gs = _GSettings()
        _g_model = _gs.get("summarisation.model", "") or _gs.get("summarisation.primary_model", "")
        if _g_model:
            from core.summarisation.postchecks.garble import repair_garbles_via_llm

            tho_str, _garble_repair_issues = repair_garbles_via_llm(
                tho_str, "thorough", source_text or "", _src_words, _gs
            )
            # The pre-repair garble flags (tho_fragment + tho_dropped) stay
            # as the honest "what was found" record; the repair issues
            # (fix/flag) document the LLM repair on top. Mirror the D3 path.
            report.issues.extend(_garble_repair_issues or [])
    # V0.4.23: raw-source verbatim exemption (see validate_years docstring).
    _, tho_year = validate_years(tho_str, "thorough", source_authors, source_text or "")
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
    # V0.4.11 (audit #8): multi-author concept conflation check.
    _, tho_conflation = (
        detect_multi_author_conflation(tho_str, "thorough", source_text or "", source_authors)
        if source_text and source_authors
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
    return tho_str
