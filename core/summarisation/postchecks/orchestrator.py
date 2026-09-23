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
    # V0.4.19 (de-monolithization): SELF_TALK_PATTERNS / classify_scar /
    # is_citation_only_fragment moved with the bullets phase to
    # field_phases.py — kept as facade re-exports (is_truncated is still
    # used by the KD/TT section below).
    SELF_TALK_PATTERNS,  # noqa: F401 (V18.20.3.2 audit N1 / P0-2)
    classify_scar,  # noqa: F401
    is_citation_only_fragment,  # noqa: F401 (V18.20.3.2 audit N5 / P1-c)
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

# V0.4.19 (de-monolithization): the per-field phases (the bullets / exec /
# thorough sections of run_post_checks) moved VERBATIM to field_phases.py;
# this import wires them back in at the same positions in the flow.
# _PADDING_PATTERNS + _is_padding_bullet moved with the bullets phase and
# are re-exported here for the historical facade surface.
from core.summarisation.postchecks.field_phases import (
    _PADDING_PATTERNS,  # noqa: F401 — facade re-export (moved with the bullets phase)
    PhaseCtx,
    _is_padding_bullet,  # noqa: F401 — facade re-export (moved with the bullets phase)
    postcheck_bullets,
    postcheck_exec,
    postcheck_thorough,
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
    detect_multi_author_conflation,  # V0.4.11 (audit #8) — multi-author concept conflation
    detect_sentence_fusion,  # V0.4.3 (audit D4) — sentence-boundary fusion
    detect_word_fragment_merge,
    repair_stray_quotes,  # V0.20.5 (brainstorm D2)
    repair_stray_quotes_v2,  # V0.20.6 (brainstorm D2+) — even-count mismatches
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
    enum_guarantee_texts: list[str] | None = None,
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
        enum_guarantee_texts: V0.4.24 (audit backlog #3) — the exact texts
            of the enumeration-guarantee bullets (stashed on the parsed
            result by ``_ensure_enumeration_bullets``). These bullets are
            exempt from the ship-time truncation drop (their items are
            verbatim source text); the exemption is logged as a flag Issue.

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

    # V0.4.19 (de-monolithization): the three per-field sections below moved
    # VERBATIM to field_phases.py (postcheck_bullets / postcheck_exec /
    # postcheck_thorough) — same detector order, same issue order. The ctx
    # threads the SWOT A24 precompute (built once, above) into the phases so
    # no detector call rebuilds the source-derived values.
    ctx = PhaseCtx(
        source_text=source_text,
        source_lower=_src_lower,
        source_lower_full=_src_lower_full,
        source_words=_src_words,
        source_authors=source_authors,
        auto_repair_garble=auto_repair_garble,
    )
    # ── Bullets ──────────────────────────────────────────────────────────
    # V0.4.24 (audit backlog #3): guarantee texts threaded through so the
    # truncation drop can exempt them (flag, never silently drop).
    report.bullets = postcheck_bullets(
        bullets, ctx, report, enum_guarantee_texts=enum_guarantee_texts
    )
    # ── Executive summary ────────────────────────────────────────────────
    report.executive_summary = postcheck_exec(executive_summary, ctx, report)
    # ── Thorough summary ─────────────────────────────────────────────────
    report.thorough_summary = postcheck_thorough(thorough_summary, ctx, report)

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

        # V0.4.16: inject page refs into KD/TT if the model didn't include them.
        from core.summarisation.postchecks.garble import inject_page_refs

        report.key_distinctions, kd_page_issues = inject_page_refs(
            report.key_distinctions, "key_distinctions", source_text or ""
        )
        report.theoretical_tensions, tt_page_issues = inject_page_refs(
            report.theoretical_tensions, "theoretical_tensions", source_text or ""
        )
        report.issues.extend(kd_page_issues or [])
        report.issues.extend(tt_page_issues or [])

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
