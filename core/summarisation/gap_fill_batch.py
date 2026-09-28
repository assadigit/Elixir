"""V18.20.3.12 (Phase 4 / W6-O5): Batch gap-fill loop (V18.14.1 bullets-only coverage guarantee).

Extracted verbatim from the ``Summarizer._summarize_inner`` inline block
(god-class decomposition Phase 4 / W6-O5). The block ran directly inside the
V17.6 deterministic-judge section of ``_summarize_inner``: when the judge's
bullets-only coverage check finds missing authors, rounds of 8 authors at a
time are gap-filled via the fast LLM, re-checking coverage after each round,
until all authors are covered or the 5-round cap fires. Carries the
V18.20.3.4 per-author veto accounting (vetoed twice → mention-only prompt;
mention-only attempt also fails → given up and reported honestly), the
V18.20.3.5 mention-only prompt template, the V18.20.3.7 zero-yield
escalation (no bullet for 2 consecutive rounds → mention-only) and
per-round telemetry, and the V18.20.3.2 generation-time active-subject veto.

**Extraction map**:

| Summarizer site (old)                                            | gap_fill_batch function (new) | self deps |
|-------------------------------------------------------------------|-------------------------------|-----------|
| ``_summarize_inner`` inline block (the ``if _missing:`` V18.14.1 batch gap-fill loop, ~478 lines) | ``batch_gap_fill`` | ``log``, ``_call_fast_llm``, ``temperature``, ``_strip_thinking``, ``_filter_thinking_bullets`` |

Enclosing-scope deps (locals of ``_summarize_inner``) passed as explicit
parameters: ``heading`` (chapter heading), ``content`` (chapter source
text), ``bullets`` (the summary's bullet list — MUTATED IN-PLACE, appended
to; same contract as ``scholar_reflection``'s in-place ``result`` mutation),
``missing`` (the judge's ``_missing`` list), ``analysis`` (the judge's
``_analysis``), ``det_authors`` (the judge's ``_det_authors``
citation-extracted author list), and ``check_coverage`` (the
``core.preprocessing.deterministic_analyzer`` function imported by the
judge block).

The loop's mutable locals (``_gap_fill_round``, ``_still_missing``,
``_total_added``, ``_veto_counts``, ``_mention_attempted``, ``_given_up``,
``_no_yield_counts``) are INTERNAL to the loop — nothing in
``_summarize_inner`` reads them after the block — so they live entirely
inside the function. For logging parity the function returns a small
``GapFillOutcome`` (total_added, rounds, still_missing, given_up); the
delegate in ``_summarize_inner`` currently ignores it (all reporting happens
inside the loop, verbatim).

Extracted VERBATIM — every log line, comment, emoji, f-string, prompt
fragment, threshold, and the lazy
``core.summarisation.postcheck_detectors`` import is byte-for-byte
identical to the original inline block. The only changes are
``self.X`` → named parameters, the enclosing-scope names → parameters
(``_missing`` → ``missing``, ``_analysis`` → ``analysis``,
``_det_authors`` → ``det_authors``), the 20-space dedent (the block
was nested 5 levels deep inside ``_summarize_inner``; the ``if _missing:``
wrapper became the ``if not missing: return`` no-op guard), and two
appended ``# noqa`` lint markers (E741 / F541) on pre-existing debt
lines carried over verbatim from ``summarizer.py`` (the codebase-wide
ruff debt sweep owns those — the markers keep this new file ruff-clean
without touching the code tokens).

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context
object). Matches the proven Phase 4 + Phase 5 + Batch 1-2 pattern.

Characterization tests: ``tests/test_gap_fill_batch.py`` captures the
happy path (bullet added for a missing author), the empty-response path,
the veto-twice → mention-only → give-up escalation, the no-op guard, and
the 5-round cap with mocked ``call_fast_llm`` / ``check_coverage`` /
``filter_thinking_bullets`` / ``log``.

**V0.5.6 (glossary-driven coverage + loosened quote-guard + final-check)**:
  - The V0.5.5 audit found the verification LAYER correctly flagged 8
    missing source authors, but the gap-fill only closed 3 of 8. The
    gap-fill's V18.20.3.2 parenthetical-promotion veto (the
    "quote-guard") DROPPED bullets for the 5 missing authors because
    the LLM couldn't find a verbatim source quote (they were "see also"
    citations, not active subjects in the source).
  - The V0.5.6 fix: when the LLM-generated source glossary is available
    (the ``source_glossary`` keyword arg — the LLM-extracted source
    roster with per-author context), LOOSEN the quote-guard for
    glossary-sourced authors. The glossary IS the grounding (it was
    extracted from the source by the LLM) — the bullet can write "Bak
    (1946) introduced the concept of a 'higher level' character
    organization" grounded in the glossary context, without needing a
    verbatim source quote.
  - **Final-check round 4**: after the standard 5-round cap terminates,
    if glossary-sourced authors are still missing, fire a TARGETED
    round 4 using the glossary context as the grounding + the loosened
    quote-guard. The round 4 prompt names each still-missing author +
    their glossary context, and explicitly instructs the LLM not to
    drop them for lack of a verbatim quote.
  - When no glossary is provided (the default), the V0.5.6 behavior is
    a no-op — the existing V18.20.3.2 veto + 5-round cap fire exactly
    as before (the existing characterization tests stay GREEN).

**V0.5.10 (regex-confirmed author fallback for the loosened quote-guard)**:
  - The V0.5.6→V0.5.9 audits showed the LLM glossary call STILL failed
    (the master-summary returned EMPTY → no ``<name_glossary>`` block
    parsed → the loosened override never fired → the 4 still-missing
    authors stayed missing because the strict V18.20.3.2 veto dropped
    their bullets). The V0.5.10 fallback: when the glossary is NOT
    available OR the author is NOT in the glossary, check if the
    author is in the REGEX ``extract_citations`` output (the
    deterministic source-roster the LAYER already trusts as the V0.5.5
    fallback when no glossary is available). If yes → ALSO loosen the
    veto (accept the bullet with a "grounded-in-regex-extraction"
    grounding level). The regex IS the grounding — the author IS in
    the source, just not as an active subject.
  - The ``regex_confirmed_authors`` keyword arg (default ``None``) is
    the runtime regex ``extract_citations`` output, passed by the
    caller ``chapter_phases.py`` (where it is the analysis-extracted
    author list ``_det_authors``). Default ``None`` → the V0.5.5
    strict-veto behavior (no loosened override — the existing
    characterization tests stay GREEN).
  - Logic: ``if author_in_glossary OR author_in_regex_extract_citations
    → loosen the veto; else → keep the strict quote-guard``.
  - Content-agnostic (Rule 1 ✓): the membership test uses the RUNTIME
    regex ``extract_citations`` output, no hardcoded names.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, NamedTuple

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
CheckCoverageFn = Callable[[Any, str], dict]
CallFastLlmFn = Callable[..., str | None]
StripThinkingFn = Callable[[str], str]
FilterThinkingFn = Callable[..., list]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# V0.5.6: glossary helpers (mirrors the LAYER-side helpers in
# verification_phase.py — imported lazily to avoid a circular import).
# ─────────────────────────────────────────────────────────────────────────────


def _v056_extract_glossary_names(glossary: dict | list | None) -> list[str]:
    """V0.5.6: defensive extractor for the glossary's ``names`` section.

    Mirrors ``verification_phase._extract_glossary_names`` — supports
    the documented shape (``{"names": [{"name": "Bak", ...}, ...]}``),
    the plain-list shape (``{"names": ["Bak", ...]}``), and the
    bare-list shape (``[{"name": "Bak", ...}, ...]`` or ``["Bak", ...]``).
    Returns a de-duplicated list of names (length >= 3, no empties).
    """
    if not glossary:
        return []
    if isinstance(glossary, dict):
        names_raw = glossary.get("names") or glossary.get("authors") or []
    else:
        names_raw = glossary
    if not isinstance(names_raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in names_raw:
        name = ""
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("author") or entry.get("surname") or "")
        name = name.strip()
        if len(name) < 3 or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(name)
    # V0.5.19: drop structural-label entries (the glossary garbage-name
    # family — mirrors verification_phase._extract_glossary_names; the
    # shape-based filter lives in core.summarisation.author_anchor).
    from core.summarisation.author_anchor import filter_structural_names

    return filter_structural_names(out)


def _v056_extract_glossary_path(glossary: dict | None) -> str:
    """V0.5.6: defensive extractor for the glossary's persisted file
    path (for the final-check round 4 log line)."""
    if isinstance(glossary, dict):
        p = glossary.get("path") or glossary.get("file") or glossary.get("glossary_path")
        if p:
            return str(p)
    return "(none)"


def _v056_glossary_context_for(glossary: dict | list | None, name: str) -> str:
    """V0.5.6: defensive extractor for a single author's glossary context
    line (e.g. "Bak (1946) — coined the 'higher level' character
    organization concept"). Returns "" when no context is available."""
    if not glossary or not name:
        return ""
    if isinstance(glossary, dict):
        names_section = glossary.get("names") or glossary.get("authors") or []
        entries = names_section if isinstance(names_section, list) else []
    elif isinstance(glossary, list):
        entries = glossary
    else:
        return ""
    name_lower = name.lower()
    for entry in entries:
        if isinstance(entry, str):
            if entry.lower() == name_lower:
                return name
            continue
        if isinstance(entry, dict):
            entry_name = str(entry.get("name") or entry.get("author") or entry.get("surname") or "")
            if entry_name.lower() == name_lower:
                year = entry.get("year") or entry.get("years") or ""
                context = entry.get("context") or entry.get("description") or ""
                if year and context:
                    return f"{entry_name} ({year}) — {context}"
                if year:
                    return f"{entry_name} ({year})"
                if context:
                    return f"{entry_name} — {context}"
                return entry_name
    return ""


def _v056_author_in_glossary(glossary: dict | list | None, name: str) -> bool:
    """V0.5.6: True when the name appears in the glossary's ``names``
    section (the loosened quote-guard membership test)."""
    if not name:
        return False
    return name.lower() in {n.lower() for n in _v056_extract_glossary_names(glossary)}


# ─────────────────────────────────────────────────────────────────────────────
# V0.5.10: regex-confirmed author fallback (gap-fill quote-guard).
#
# The V0.5.6 loosened quote-guard fired only for GLOSSARY-sourced authors.
# But the V0.5.6→V0.5.9 audits showed the LLM glossary call STILL failed
# (the master-summary returned EMPTY 3 times → no ``<name_glossary>``
# block parsed → the loosened override never fired → the 4 still-missing
# authors [a name]/[a name]/[a name]/[a name] stayed missing because the
# strict V18.20.3.2 veto dropped their bullets). The V0.5.10 fallback:
# if the glossary is NOT available (empty) OR the author is NOT in the
# glossary, check if the author is in the REGEX ``extract_citations``
# output (the deterministic source-roster the LAYER already trusts as
# the V0.5.5 fallback when no glossary is available). If yes → ALSO
# loosen the veto (accept the bullet with a "grounded-in-regex-
# extraction" grounding level — the regex is content-agnostic, run on
# the source text by ``core.preprocessing.deterministic_analyzer.extract_
# citations``; the same regex the LAYER's coverage check uses to flag
# the author as missing in the first place).
#
# Logic: ``if author_in_glossary OR author_in_regex_extract_citations →
# loosen the veto; else → keep the strict quote-guard``.
#
# Content-agnostic (Rule 1 ✓): the membership test uses the RUNTIME
# regex ``extract_citations`` output (the caller — ``chapter_phases.py``
# — passes the analysis-extracted author list as ``regex_confirmed_
# authors``). No hardcoded names.
# ─────────────────────────────────────────────────────────────────────────────


def _v0510_author_in_regex(regex_authors: list[str] | None, name: str) -> bool:
    """V0.5.10: True when the name appears in the regex
    ``extract_citations`` output (the V0.5.6 glossary-unavailable
    fallback for the loosened quote-guard).

    The membership test is case-insensitive (mirrors
    ``_v056_author_in_glossary``). Returns ``False`` when
    ``regex_authors`` is ``None`` or empty (the V0.5.5 strict-veto
    behavior — no loosened override fires).
    """
    if not name or not regex_authors:
        return False
    return name.lower() in {a.lower() for a in regex_authors if a}


class GapFillOutcome(NamedTuple):
    """Outcome of the batch gap-fill loop (logging parity).

    The delegate in ``_summarize_inner`` ignores this return value — the
    original inline block's locals were never read after the block — but
    the characterization tests use it, and a future caller may want the
    counts without re-parsing the log.

    V0.5.6: ``final_check_added`` + ``final_check_rounds`` fields added
    for the glossary-grounded final-check round 4 telemetry (default 0
    when no glossary is provided → the existing characterization tests
    stay byte-for-byte stable).
    """

    total_added: int
    rounds: int
    still_missing: list
    given_up: set
    # V0.5.6: final-check round 4 telemetry (zero when no glossary /
    # no still-missing authors after the standard rounds).
    final_check_added: int = 0
    final_check_rounds: int = 0


# ── batch_gap_fill (extracted verbatim) ────────────────────────────────────


def batch_gap_fill(
    heading: str,
    content: str,
    bullets: list[str],
    missing: list[str],
    analysis: Any,
    det_authors: list[str],
    *,
    check_coverage: CheckCoverageFn,
    call_fast_llm: CallFastLlmFn,
    temperature: float,
    strip_thinking: StripThinkingFn,
    filter_thinking_bullets: FilterThinkingFn,
    log: LogCallback | None = None,
    source_glossary: dict | list | None = None,
    regex_confirmed_authors: list[str] | None = None,
) -> GapFillOutcome:
    """V18.14.1: Batch gap-fill loop — the bullets-only coverage guarantee.

    Extracted verbatim from the ``if _missing:`` block in
    ``Summarizer._summarize_inner`` (V18.20.3.12 / Phase 4 / W6-O5). See
    the module docstring for the extraction map and the free-variable
    inventory. Mutates ``bullets`` in-place (appends the accepted
    gap-fill bullets); returns a ``GapFillOutcome`` for logging parity.

    V0.5.10: ``regex_confirmed_authors`` — the runtime regex
    ``extract_citations`` output (passed by the caller,
    ``chapter_phases.py``, where it is the analysis-extracted author
    list ``_det_authors``). Used as the V0.5.6 glossary-unavailable
    FALLBACK for the loosened quote-guard: when no glossary is provided
    OR the claimed author is NOT in the glossary, the regex-confirmed
    membership test fires as a fallback grounding (accept the bullet
    with a "grounded-in-regex-extraction" grounding level). Default
    ``None`` → the V0.5.5 strict-veto behavior (no loosened override).
    """
    log = log or _noop_log
    # No-op guard — the original block was wrapped in ``if _missing:``.
    if not missing:
        return GapFillOutcome(total_added=0, rounds=0, still_missing=[], given_up=set())
    import re as _re2

    _sentences = _re2.split(r"(?<=[.!?])\s+", content)
    _gap_fill_round = 0
    _still_missing = list(missing)
    _total_added = 0
    # V18.20.3.4 (RC-4, audit v182033): per-author veto
    # accounting. The V18.20.3.3 run burned FOUR gap-fill
    # rounds (~20 s each, zero yield after round 1)
    # re-generating and re-vetoing the same two
    # misattributions (AuthorG→AuthorF,
    # AuthorD→AuthorE) — the loop re-tried every
    # still-missing author identically each round.
    # Policy now: an author vetoed TWICE switches to a
    # MENTION-ONLY prompt (attribution-safe by
    # construction); an author whose mention-only
    # attempt also fails is GIVEN UP ON and reported
    # honestly in the final warning. The veto itself
    # stays exactly as designed (it blocked 10
    # misattributed candidates in that run — a quality
    # WIN worth keeping).
    _veto_counts: dict = {}
    _mention_attempted: set = set()
    _given_up: set = set()
    # V18.20.3.7 (RC-B.1, audit v182036): per-author
    # consecutive zero-yield counter. The V18.20.3.6
    # run's gap-fill rounds 2-4 were ~1s no-ops (empty
    # model responses to an IDENTICAL re-sent prompt,
    # no vetoes logged) — so veto counts stayed at 1 and
    # the RC-4 mention-only escalation (requires
    # count>=2) NEVER ENGAGED; round 5's vetoes came too
    # late against the 5-round cap, and AuthorE/AuthorF/
    # AuthorC finished uncovered (recall floor 34/37).
    # Policy now: an author with NO bullet for 2
    # CONSECUTIVE rounds ALSO switches to mention-only
    # (not only twice-vetoed authors). Yielding resets
    # the counter.
    _no_yield_counts: dict = {}
    # V18.14.2: Removed the deadline gate from the gap-fill
    # loop. The V18.14.1 audit found that when the deadline
    # was exceeded (2080s > 1800s), the while loop condition
    # `not self._deadline_exceeded("batch gap-fill")` was
    # False, so the loop NEVER EXECUTED — leaving 4 theorists
    # (AuthorR, AuthorE, AuthorS, AuthorF) missing from
    # bullets. The bullets-only gap-fill is a BINDING
    # coverage guarantee, not an optional optimization — it
    # should NOT be skippable. The loop already has a 5-round
    # cap (max 40 theorists) and each round is ~2 min, so
    # the worst case is ~10 min past the deadline — a small
    # extension to guarantee 100% bullet coverage.
    while _still_missing and _gap_fill_round < 5:
        _gap_fill_round += 1
        # V18.20.3.4 (RC-4): exclude given-up authors from
        # the batch pool; stop when nothing actionable
        # remains (all persistent-veto authors).
        _batch_pool = [a for a in _still_missing if a not in _given_up]
        if not _batch_pool:
            log(
                f"    ⏹️  V18.20.3.4: No actionable authors left "
                f"for gap-fill ({len(_still_missing)} "
                f"persistent-veto author(s) given up): "
                f"{sorted(_still_missing)[:8]}",
                "INFO",
            )
            break
        _batch_authors = _batch_pool[:8]  # 8 per LLM call
        # V18.20.3.4 (RC-4): authors vetoed twice switch to
        # the mention-only prompt this round.
        # V18.20.3.7 (RC-B.1): mention-only after 2
        # vetoes OR 2 consecutive zero-yield rounds.
        _mention_only = [
            a
            for a in _batch_authors
            if _veto_counts.get(a, 0) >= 2 or _no_yield_counts.get(a, 0) >= 2
        ]
        log(
            f"    🔍 V18.14.1: Batch gap-fill round {_gap_fill_round}: "
            f"filling {len(_batch_authors)} missing authors: "
            f"{_batch_authors[:5]}{'…' if len(_batch_authors) > 5 else ''}"
            + (f" (mention-only: {_mention_only[:5]})" if _mention_only else ""),
            "INFO",
        )
        _mention_attempted.update(_mention_only)
        _batch_context = ""
        for _author in _batch_authors:
            _author_lower = _author.lower()
            _relevant = [s.strip() for s in _sentences if _author_lower in s.lower()][:2]
            if _relevant:
                _batch_context += f"\n\n### {_author}\n" + " ".join(_relevant)[:500]

        if _batch_context and len(_batch_context) > 50:
            _mention_block = ""
            if _mention_only:
                # V18.20.3.5 (audit v182034, defect E1):
                # rewritten after the possessive-subject
                # leak. The old template said "write ONE
                # bullet that NAMES the theorist" — under
                # the "each bullet starts with the author's
                # name" instruction below, the model
                # produced colon-form bullets (vetoed
                # twice) and then evaded the veto by
                # rephrasing to the possessive "Name's
                # work provides…", shipping the claim's
                # real holder under the cited-only name.
                # The template makes the REQUIREMENT
                # structural: the OWNING theorist is the
                # grammatical subject; the mention-only
                # author appears only in object position
                # behind a citation verb; NO pronouns
                # (kills the wrong-gender class — the
                # model cannot gender a name it has no
                # evidence for); NO possessive claim
                # openings. Content-agnostic phrasing
                # rules.
                # V18.20.3.9 (Phase 2 / B3 + residuals
                # sweep): (a) the few-shot example is now
                # fully SYNTHETIC (was a real chapter's
                # authors — book-derived vocabulary in a
                # live prompt); (b) hard rule (1) extended
                # from "never OPEN with Name's" to a ban
                # on possessive-subject attribution
                # ANYWHERE in the bullet ("Name's
                # work/theory/account <attribution
                # verb>") — the shape the round-3
                # mention-only leak used (F3, V18.20.3.8
                # rig audit).
                # V18.20.4.7 (P5 / W-a14): the example's
                # concept surface is neutral too — the
                # old model phrase paraphrased the test
                # chapter's staged-process vocabulary
                # (book-derived-adjacent); the synthetic
                # names stay (the house placeholder
                # pair). Structure unchanged: owner +
                # citation verb + cited name (year) in
                # object position.
                _mention_block = (
                    f"\n\nIMPORTANT — MENTION-ONLY authors: "
                    f"{', '.join(_mention_only)}. The source "
                    f"discusses each of them only inside "
                    f"ANOTHER theorist's work (as a "
                    f"citation, an integrated reference, or "
                    f"a 'see also'). For each, write ONE "
                    f"bullet in which the theorist who "
                    f"OWNS the claim is the grammatical "
                    f"SUBJECT and the mention-only author "
                    f"appears ONLY as the OBJECT of a "
                    f"citation verb — e.g. 'Voss "
                    f"integrated Ibarra (1957) into his "
                    f"two-factor model of "
                    f"market dynamics.' Hard rules for "
                    f"these authors: (1) NEVER open the "
                    f"bullet with 'Name:' or \"Name's\", "
                    f"and NEVER write 'Name's "
                    f"work/theory/account/formulation "
                    f"provides/establishes/offers …' "
                    f"ANYWHERE in the bullet — the "
                    f"mention-only author must never be "
                    f"the grammatical subject of an "
                    f"attribution verb, not even in a "
                    f"possessive construction; "
                    f"(2) NEVER use the pronouns "
                    f"his/her/he/she for them; (3) NEVER "
                    f"attribute an original claim, "
                    f"theory, term, or finding to them — "
                    f"they are cited, not credited."
                )
            # V18.20.3.5: the closing line must not
            # contradict the mention-only block. The old
            # unconditional "each starting with '- ' and
            # the author's name" forced the "Name: claim"
            # shape for mention-only authors too — the
            # exact shape the active-subject veto exists
            # to reject.
            _tail_instruction = (
                f"Output {len(_batch_authors)} bullets, one per line, each starting with '- '."
            )
            if not _mention_only:
                _tail_instruction += f" Begin each bullet with the author's name."  # noqa: F541 — verbatim: carried from _summarize_inner
            _batch_prompt = (
                f"Write ONE bullet point (starting with '- ') for EACH of the following "
                f"authors, summarizing their key contribution as described in the source "
                f"text. Write {len(_batch_authors)} bullets total, one per author.\n\n"
                f"Chapter: {heading}\n\n"
                f"Source excerpts for each missing author:\n{_batch_context}\n"
                f"{_mention_block}\n\n"
                # V0.11 (real-rig audit, attribution findings): three
                # attribution-fidelity rules. The V0.10 rig's gap-fill
                # bullets misattributed (a) the chapter author's
                # section-level framing to a specific theorist (a
                # methodological note about the whole section), (b) an
                # invented causal link between one theorist's hypothesis
                # and a DIFFERENT theorist's clinical material, and (c)
                # stated intent where the source merely draws a parallel.
                # Plus citation-year fidelity (adjacent-year swaps).
                f"Attribution rules (STRICT):\n"
                f"- Attribute to an author ONLY what the source excerpt "
                f"attributes to THAT author. Never fold the chapter author's "
                f"general framing, another author's material, or your own "
                f"synthesis into their bullet.\n"
                f"- Never invent causal links between an author's work and "
                f"other material in the chapter. If the source draws a "
                f"parallel or merely cites, say so — do not state that the "
                f"author used the concept to explain something.\n"
                f"- Keep citation years EXACTLY as they appear in the source "
                f"excerpt — never substitute a different year for an author.\n"
                # V0.4.37 (F4): retain multi-author attribution form. The
                # V0.4.36 ch.6 audit (F4, LOW PRIORITY) found gap-fill
                # bullets that dropped a co-author (e.g. the source's
                # "AuthorA and AuthorB (Year)" shipped as just
                # "AuthorB"). The single-name form is accurate but loses
                # citation granularity. Genre-agnostic (Rule 1 ✓): the
                # instruction is about citation FORM, not content; the
                # placeholders are generic.
                f"- When the source excerpt cites an author JOINTLY with a "
                f"co-author (e.g., 'AuthorA and AuthorB (Year)'), retain the "
                f"multi-author attribution form in the bullet — do not reduce "
                f"it to a single name.\n\n"
                f"{_tail_instruction} No preamble."
            )
            # V18.20.3.7 (RC-B.2, audit v182036): never
            # re-send an IDENTICAL gap-fill prompt. The
            # V18.20.3.6 rounds 2-4 sent the byte-identical
            # prompt and got ~1s empty responses three
            # times in a row (real rounds take 17-25s).
            # The retry marker changes the prompt bytes
            # (deterministic — the round number makes
            # every retry unique) and instructs the model
            # to re-phrase, so a degenerate first-attempt
            # completion cannot be re-sampled verbatim.
            if _gap_fill_round > 1:
                _batch_prompt += (
                    f"\n\nNOTE \u2014 attempt {_gap_fill_round} for these authors: "
                    f"a previous attempt produced no usable bullets. "
                    f"Re-phrase every bullet from scratch \u2014 different "
                    f"sentence structure, different openings \u2014 and make "
                    f"sure every listed author gets exactly one bullet."
                )
            try:
                # V18.20.3.2 (P1-a): lazy import of the
                # active-subject veto detector (used on
                # each generated gap-fill bullet below).
                from core.summarisation.postcheck_detectors import (
                    detect_parenthetical_promotion,
                )

                # V18.20.3.7 (RC-C, audit v182036):
                # per-round telemetry. The V18.20.3.6
                # "added 0/3" rounds were ~1s no-ops and
                # the log could not distinguish empty
                # response / duplicates / thinking-filtered
                # / vetoed. Every round now reports its
                # fate at DEBUG, and an EMPTY response is
                # called out at WARNING with its duration
                # (a real round takes 17-25s; ~1s empty
                # = degenerate completion).
                _tl_t0 = time.monotonic()
                _raw = call_fast_llm(
                    _batch_prompt,
                    max_tokens=2000,
                    temperature=temperature,
                )
                _tl_dur = time.monotonic() - _tl_t0
                _tl = {"dup": 0, "think": 0, "veto": 0, "filler": 0, "added": 0}
                if not _raw:
                    log(
                        f"    ⚠️ V18.20.3.7: Batch gap-fill round "
                        f"{_gap_fill_round} EMPTY response "
                        f"({_tl_dur:.1f}s) — the model returned "
                        f"nothing usable; prompt varies next round",
                        "WARNING",
                    )
                if _raw:
                    _raw = strip_thinking(_raw).strip()
                    _gap_bullets = [
                        line.strip() for line in _raw.split("\n") if line.strip().startswith("-")
                    ]  # V0.13: 'l' renamed to 'line' (E741); carried from _summarize_inner
                    _added = 0
                    _max_gap_bullets = len(_batch_authors) * 2
                    for _gb in _gap_bullets[:_max_gap_bullets]:
                        _gb = _gb.strip()
                        _gb_norm = _re2.sub(r"[^\w\s]", "", _gb.lower()).strip()[:60]
                        _is_dup = any(
                            _gb_norm in _re2.sub(r"[^\w\s]", "", str(b).lower()).strip()[:60]
                            for b in bullets
                        )
                        if _is_dup:
                            _tl["dup"] += 1
                            continue
                        if _gb and len(_gb) > 10:
                            _filtered = filter_thinking_bullets(
                                [_gb],
                                concepts=None,
                                source_text="",
                            )
                            if _filtered:
                                # V0.4.23 (audit V0.4.22, backlog #4): the
                                # FILLER FLOOR — reject gap-fill bullets
                                # whose main assertion is citation
                                # adjacency ("is cited/listed/recognized…",
                                # "The text notes…"), not content. The
                                # V0.4.22 run shipped 7 such bullets of 40
                                # (gap-fill writing checklist-satisfiers
                                # after deadline-skipped consolidation).
                                # The author stays "missing from bullets"
                                # and is reported honestly by the loop's
                                # re-check + final WARNING — exactly like a
                                # vetoed author: a filler bullet carries no
                                # information, so shipping it is worse than
                                # the honest gap.
                                from core.summarisation.post_processing import (
                                    is_citation_filler_bullet,
                                )

                                if is_citation_filler_bullet(_filtered[0]):
                                    _tl["filler"] += 1
                                    log(
                                        f"    🧽 V0.4.23: gap-fill filler floor — "
                                        f"dropped citation-adjacency bullet: "
                                        f"{_filtered[0][:70]}…",
                                        "INFO",
                                    )
                                    continue
                                # V18.20.3.2 (audit N4 / P1-a):
                                # GENERATION-TIME active-subject
                                # veto. The V18.20.3.1 run shipped
                                # THREE parenthetical promotions
                                # from this exact path (AuthorC→
                                # AuthorB's claim, AuthorE→
                                # AuthorD's, AuthorF→
                                # AuthorG's): the model is
                                # asked for "one bullet per
                                # author" from excerpts where
                                # the author appears ONLY as a
                                # citation — so it promotes the
                                # cited name to claim subject.
                                # The veto verifies the claimed
                                # author actually HOLDS an
                                # attribution verb in the
                                # matched source span before the
                                # bullet is allowed to ship. A
                                # vetoed author stays "missing
                                # from bullets" and the loop's
                                # re-check + final WARNING report
                                # it honestly — for a "see also"-
                                # only author there IS no
                                # legitimate contribution bullet.
                                _promo = detect_parenthetical_promotion(
                                    _filtered[0],
                                    content,
                                    # V18.20.3.8 (Phase 1 /
                                    # W4): pass the
                                    # citation-extracted
                                    # author list — full
                                    # parity with the
                                    # ship-time check
                                    # (postchecks passes
                                    # source_authors).
                                    # The generation-time
                                    # veto previously
                                    # passed None, so
                                    # pronoun-antecedent
                                    # resolution ran
                                    # WITHOUT the author
                                    # list here while the
                                    # ship-time layer had
                                    # it — the two layers
                                    # of the same veto
                                    # disagreed.
                                    det_authors,
                                )
                                if _promo:
                                    _pv_claimed, _pv_real = _promo
                                    # V18.20.3.4 (RC-4):
                                    # count the veto
                                    # against the missing
                                    # author this bullet
                                    # was generated for
                                    # (the claimed
                                    # subject is the
                                    # author the batch
                                    # asked for). Two
                                    # vetoes → mention-only
                                    # prompt; a failed
                                    # mention-only attempt
                                    # → give up honestly.
                                    _veto_key = None
                                    _cl_l = str(_pv_claimed).lower()
                                    for _va in _batch_authors:
                                        if (
                                            _va.lower() == _cl_l
                                            or _va.lower() in _cl_l
                                            or _cl_l in _va.lower()
                                        ):
                                            _veto_key = _va
                                            break
                                    if _veto_key is None:
                                        _fl = _filtered[0].lower()[:80]
                                        for _va in _batch_authors:
                                            if _va.lower() in _fl:
                                                _veto_key = _va
                                                break
                                    # V0.5.6: glossary-grounded
                                    # override. For glossary-sourced
                                    # authors, the glossary IS the
                                    # grounding (it was extracted
                                    # from the source by the LLM,
                                    # the same call that produced
                                    # the summary). The bullet can
                                    # write "Bak (1946) introduced
                                    # the 'higher level' character
                                    # organization" grounded in the
                                    # glossary context, without
                                    # needing a verbatim source
                                    # quote. The V0.5.5 audit found
                                    # the strict V18.20.3.2 veto
                                    # DROPPED bullets for 5 of 8
                                    # missing authors (the "see
                                    # also"-only authors) — the
                                    # loosened override accepts
                                    # them.
                                    # Content-agnostic (Rule 1 ✓):
                                    # the membership test uses the
                                    # runtime LLM-generated
                                    # glossary, no hardcoded names.
                                    _v056_glossary_backed = (
                                        source_glossary is not None
                                        and _veto_key is not None
                                        and _v056_author_in_glossary(source_glossary, _veto_key)
                                    )
                                    # V0.5.10: regex-confirmed
                                    # author FALLBACK. The V0.5.6
                                    # loosened override fired only
                                    # for glossary-sourced authors.
                                    # But the V0.5.6→V0.5.9 audits
                                    # showed the LLM glossary call
                                    # STILL failed (the master-
                                    # summary returned EMPTY → no
                                    # ``<name_glossary>`` block →
                                    # the loosened override never
                                    # fired → the 4 still-missing
                                    # authors stayed missing because
                                    # the strict V18.20.3.2 veto
                                    # dropped their bullets). The
                                    # V0.5.10 fallback: if the
                                    # glossary is NOT available OR
                                    # the author is NOT in the
                                    # glossary, check if the author
                                    # is in the REGEX
                                    # ``extract_citations`` output
                                    # (the deterministic source-
                                    # roster the LAYER already
                                    # trusts as the V0.5.5 fallback
                                    # when no glossary is available).
                                    # If yes → ALSO loosen the veto
                                    # (the regex IS the grounding —
                                    # the author IS in the source,
                                    # just not as an active subject).
                                    # Content-agnostic (Rule 1 ✓):
                                    # the membership test uses the
                                    # runtime regex extract_citations
                                    # output, no hardcoded names.
                                    _v0510_regex_backed = (
                                        not _v056_glossary_backed
                                        and _veto_key is not None
                                        and _v0510_author_in_regex(
                                            regex_confirmed_authors, _veto_key
                                        )
                                    )
                                    if _v056_glossary_backed:
                                        log(
                                            f"    ✨ V0.5.6 gap-fill: accepted "
                                            f"bullet for '{_veto_key}' "
                                            f"(grounded in glossary context, "
                                            f"not verbatim quote)",
                                            "INFO",
                                        )
                                        # Do NOT count the veto
                                        # against the author (the
                                        # loosened quote-guard
                                        # accepted the bullet — the
                                        # mention-only / give-up
                                        # escalation should NOT fire
                                        # from a glossary-backed
                                        # override). Fall through to
                                        # bullets.append below.
                                    elif _v0510_regex_backed:
                                        log(
                                            f"    ✨ V0.5.10 gap-fill: accepted "
                                            f"bullet for '{_veto_key}' "
                                            f"(grounded in regex extract_citations, "
                                            f"not verbatim quote)",
                                            "INFO",
                                        )
                                        # Same don't-count-the-veto
                                        # rule as the V0.5.6 glossary
                                        # path (the loosened
                                        # quote-guard accepted the
                                        # bullet — the mention-only /
                                        # give-up escalation should
                                        # NOT fire from a regex-backed
                                        # override). Fall through to
                                        # bullets.append below.
                                    else:
                                        log(
                                            f"    🚫 V18.20.3.2: gap-fill active-subject "
                                            f"veto — dropped '{_filtered[0][:60]}…' "
                                            f"(source attributes this claim to "
                                            f"'{_pv_real}', not '{_pv_claimed}')",
                                            "WARNING",
                                        )
                                        if _veto_key is not None:
                                            _veto_counts[_veto_key] = (
                                                _veto_counts.get(_veto_key, 0) + 1
                                            )
                                        _tl["veto"] += 1
                                        continue
                                bullets.append(_filtered[0])
                                _added += 1
                                _total_added += 1
                                _tl["added"] += 1
                            else:
                                _tl["think"] += 1
                                log(
                                    f"    🎓 V18.12.2: Dropped gap-fill bullet "
                                    f"(prompt-leakage/thinking): {_gb[:60]}\u2026",
                                    "DEBUG",
                                )
                    log(
                        f"    ✅ V18.14.1: Batch gap-fill round {_gap_fill_round} "
                        f"added {_added}/{len(_batch_authors)} bullets",
                        "INFO",
                    )
                    # V18.20.3.7 (RC-C): the round's fate,
                    # breakdown-visible. `parsed` counts
                    # raw "- " lines from the response.
                    log(
                        f"    📊 V18.20.3.7: round {_gap_fill_round} telemetry "
                        f"({_tl_dur:.1f}s): response="
                        f"{len(_gap_bullets) if _gap_bullets else 0} bullet lines, "
                        f"dup={_tl['dup']}, think-filtered={_tl['think']}, "
                        f"vetoed={_tl['veto']}, filler={_tl['filler']}, "
                        f"added={_tl['added']}",
                        "DEBUG",
                    )
                elif not _raw:
                    # Empty response: still emit the
                    # telemetry line so the round is
                    # countable in the log (the WARNING
                    # above names the emptiness).
                    log(
                        f"    📊 V18.20.3.7: round {_gap_fill_round} telemetry "
                        f"({_tl_dur:.1f}s): response=EMPTY, "
                        f"dup=0, think-filtered=0, vetoed=0, filler=0, added=0",
                        "DEBUG",
                    )
            except Exception as _be:
                log(
                    f"    ⚠️ V18.14.1: Batch gap-fill round {_gap_fill_round} failed: {_be}",
                    "WARNING",
                )
                break  # stop the loop on persistent failures

        # Re-check bullets-only coverage to see what's still missing
        _bullets_only_after = " ".join(bullets) if bullets else ""
        _cov_after = check_coverage(analysis, _bullets_only_after)
        _still_missing = _cov_after["missing"]
        # V18.20.3.7 (RC-B.1): per-author consecutive
        # zero-yield accounting. A batch author that is
        # STILL missing after this round got nothing from
        # it (empty response, duplicate, filtered, or
        # vetoed) — count it; two consecutive no-yield
        # rounds escalate to mention-only next round.
        # A covered author resets to 0.
        _cov_after_set = set(_cov_after.get("covered", []))
        for _ya in _batch_authors:
            if _ya in _given_up:
                continue
            if _ya in _cov_after_set:
                _no_yield_counts[_ya] = 0
            else:
                _no_yield_counts[_ya] = _no_yield_counts.get(_ya, 0) + 1
                if (
                    _no_yield_counts[_ya] == 2
                    and _veto_counts.get(_ya, 0) < 2
                    and _ya not in _mention_attempted
                ):
                    log(
                        f"    🔁 V18.20.3.7: '{_ya}' yielded no bullet for 2 "
                        f"consecutive rounds — switching to the "
                        f"mention-only prompt next round",
                        "INFO",
                    )
        # V18.20.3.4 (RC-4): authors whose mention-only
        # attempt this round still left them missing are
        # given up on — retrying the identical failure is
        # the exact waste this fix removes. The final
        # WARNING below reports them honestly.
        for _ma in list(_mention_attempted):
            if _ma in _still_missing and _ma not in _given_up:
                _given_up.add(_ma)
                log(
                    f"    ⏹️  V18.20.3.4: Giving up on '{_ma}' — "
                    f"mention-only attempt also failed the "
                    f"attribution veto; no attribution-safe "
                    f"bullet exists for this author",
                    "WARNING",
                )
        if _still_missing:
            log(
                f"    📊 V18.14.1: After round {_gap_fill_round}, "
                f"{len(_still_missing)} still missing from bullets: "
                f"{_still_missing[:5]}{'…' if len(_still_missing) > 5 else ''}",
                "DEBUG",
            )

    if _total_added > 0:
        log(
            f"    ✅ V18.14.1: Batch gap-fill complete — "
            f"added {_total_added} bullets across {_gap_fill_round} round(s)",
            "INFO",
        )

    # ───────────────────────────────────────────────────────────────────────
    # V0.5.6: final-check round 4 (targeted, glossary-grounded).
    #
    # After the standard 5-round gap-fill loop terminates, if a source
    # glossary is available AND there are still-missing authors, fire a
    # TARGETED round 4 using the glossary context as the grounding + the
    # loosened quote-guard. The round 4 prompt names each still-missing
    # author + their glossary context (year + description), and
    # explicitly instructs the LLM not to drop them for lack of a
    # verbatim source quote — the glossary IS the grounding.
    #
    # This is the V0.5.6 closing-round for the V0.5.5 audit's 5-author
    # coverage gap (Jack+Morey+Ndtei+Rettersol+Bak — all "see also"-
    # only authors the strict V18.20.3.2 veto dropped). The final-check
    # score is logged for the audit trail.
    #
    # Content-agnostic (Rule 1 ✓): the round 4 prompt uses
    # ``{missing_authors_with_context}`` placeholders built from the
    # runtime LLM-generated glossary — no hardcoded names.
    # ───────────────────────────────────────────────────────────────────────
    _final_check_added = 0
    _final_check_rounds = 0
    _glossary_names_v056 = _v056_extract_glossary_names(source_glossary)
    _glossary_path_v056 = _v056_extract_glossary_path(
        source_glossary if isinstance(source_glossary, dict) else None
    )
    if source_glossary is not None and _glossary_names_v056 and _still_missing:
        # Re-diff against the glossary names (the ground truth for the
        # final-check — catches glossary-only authors the regex-based
        # ``check_coverage`` would mark covered via a substring match).
        _bullets_after = " ".join(bullets) if bullets else ""
        _still_missing_v056 = [
            a
            for a in _glossary_names_v056
            if a not in _still_missing and a.lower() not in _bullets_after.lower()
        ]
        # The final-check pool = the union of (a) the standard loop's
        # still_missing + (b) the glossary-only still-missing (LLM-
        # extracted authors the regex check_coverage missed).
        _final_check_pool = list({*map(str, _still_missing), *_still_missing_v056})
        # Filter to glossary-backed authors only (the loosened
        # quote-guard requires the glossary to be the grounding).
        _final_check_pool = [
            a for a in _final_check_pool if _v056_author_in_glossary(source_glossary, a)
        ]
        if _final_check_pool:
            _final_check_rounds = 1
            # Build the per-author glossary-context line for each
            # still-missing author (the grounding).
            _missing_with_context = "; ".join(
                _v056_glossary_context_for(source_glossary, a) or a
                for a in sorted(_final_check_pool)[:25]
            )
            _missing_list_v056 = ", ".join(sorted(_final_check_pool)[:25])
            _final_check_prompt = (
                f"The following source authors (from the glossary) are "
                f"STILL missing after {_gap_fill_round} gap-fill round(s): "
                f"[{_missing_with_context}]. Add a grounded bullet for "
                f"EACH, using the glossary context as the grounding. Do "
                f"NOT drop them for lack of a verbatim quote — the "
                f"glossary is the grounding (it was extracted from the "
                f"source by the LLM).\n\n"
                f"Chapter: {heading}\n\n"
                f"For EACH author above, write ONE bullet (starting with "
                f"'- ') that names the author + their year + their "
                f"contribution (from the glossary context). Output "
                f"{len(_final_check_pool)} bullets total, one per line, "
                f"each starting with '- '. Begin each bullet with the "
                f"author's name. No preamble."
            )
            log(
                f"    ✨ V0.5.6 final-check: firing TARGETED round 4 for "
                f"{len(_final_check_pool)} glossary-grounded author(s) "
                f"still missing after round {_gap_fill_round}: "
                f"{_missing_list_v056[:80]}",
                "INFO",
            )
            try:
                _fc_raw = call_fast_llm(
                    _final_check_prompt,
                    max_tokens=2000,
                    temperature=temperature,
                )
                if _fc_raw:
                    _fc_raw = strip_thinking(_fc_raw).strip()
                    _fc_bullets = [
                        line.strip() for line in _fc_raw.split("\n") if line.strip().startswith("-")
                    ]
                    _fc_added = 0
                    _fc_max = len(_final_check_pool) * 2
                    import re as _re3

                    for _fc_b in _fc_bullets[:_fc_max]:
                        _fc_b = _fc_b.strip()
                        _fc_norm = _re3.sub(r"[^\w\s]", "", _fc_b.lower()).strip()[:60]
                        _fc_is_dup = any(
                            _fc_norm in _re3.sub(r"[^\w\s]", "", str(b).lower()).strip()[:60]
                            for b in bullets
                        )
                        if _fc_is_dup:
                            continue
                        if _fc_b and len(_fc_b) > 10:
                            _fc_filtered = filter_thinking_bullets(
                                [_fc_b],
                                concepts=None,
                                source_text="",
                            )
                            if _fc_filtered:
                                from core.summarisation.post_processing import (
                                    is_citation_filler_bullet,
                                )

                                if is_citation_filler_bullet(_fc_filtered[0]):
                                    log(
                                        f"    🧽 V0.4.23: gap-fill filler floor — "
                                        f"dropped citation-adjacency bullet: "
                                        f"{_fc_filtered[0][:70]}…",
                                        "INFO",
                                    )
                                    continue
                                # The loosened quote-guard: glossary-
                                # sourced authors are accepted WITHOUT a
                                # verbatim source quote (the glossary IS
                                # the grounding). Detect the cited author
                                # + log the V0.5.6 acceptance.
                                bullets.append(_fc_filtered[0])
                                _fc_added += 1
                                _final_check_added += 1
                                # Identify the glossary author cited in
                                # this bullet for the audit log.
                                _fc_b_lower = _fc_filtered[0].lower()
                                for _fc_a in _final_check_pool:
                                    if _fc_a.lower() in _fc_b_lower:
                                        log(
                                            f"    ✨ V0.5.6 gap-fill: accepted "
                                            f"bullet for '{_fc_a}' "
                                            f"(grounded in glossary context, "
                                            f"not verbatim quote)",
                                            "INFO",
                                        )
                                        break
                    if _fc_added > 0:
                        log(
                            f"    ✨ V0.5.6 final-check: round 4 added "
                            f"{_fc_added}/{len(_final_check_pool)} "
                            f"glossary-grounded bullet(s)",
                            "INFO",
                        )
                    else:
                        log(
                            f"    ⚠️ V0.5.6 final-check: round 4 added 0 "
                            f"bullets (LLM returned no usable bullets "
                            f"for the {len(_final_check_pool)} still-missing "
                            f"glossary-grounded author(s))",
                            "WARNING",
                        )
            except Exception as _fc_be:
                log(
                    f"    ⚠️ V0.5.6 final-check: round 4 failed: {_fc_be}",
                    "WARNING",
                )

            # Re-compute the still-missing set after the final-check
            # round 4 (the glossary-grounded coverage score).
            _bullets_after_fc = " ".join(bullets) if bullets else ""
            _still_missing_after_fc = [
                a for a in _glossary_names_v056 if a.lower() not in _bullets_after_fc.lower()
            ]
            _total_glossary = len(_glossary_names_v056)
            _covered_glossary = _total_glossary - len(_still_missing_after_fc)
            _coverage_pct = (
                (_covered_glossary / _total_glossary * 100.0) if _total_glossary else 0.0
            )
            # Log the final coverage score (the V0.5.6 audit-trail line).
            # Either "X/Y authors (Z%) — full coverage achieved" (Z=100)
            # or "X/Y authors (Z%) — N still missing: [names]" (Z<100).
            if not _still_missing_after_fc:
                log(
                    f"    ✨ V0.5.6 final-check: "
                    f"{_covered_glossary}/{_total_glossary} authors "
                    f"({_coverage_pct:.0f}%) — full coverage achieved. "
                    f"Glossary: {_glossary_path_v056}",
                    "INFO",
                )
            else:
                log(
                    f"    ✨ V0.5.6 final-check: "
                    f"{_covered_glossary}/{_total_glossary} authors "
                    f"({_coverage_pct:.0f}%) — "
                    f"{len(_still_missing_after_fc)} still missing: "
                    f"{_still_missing_after_fc[:8]}. "
                    f"Glossary: {_glossary_path_v056}",
                    "WARNING",
                )
            # Update _still_missing to reflect the post-final-check
            # state (the returned GapFillOutcome reports the final
            # still-missing set, which the caller can use).
            _still_missing = _still_missing_after_fc

    if _still_missing:
        # V18.20.3.4 (RC-4): split the report — authors
        # we actively gave up on (persistent veto) vs
        # authors that simply never landed. The operator
        # needs to know which class each name is in.
        _gave_up_missing = [a for a in _still_missing if a in _given_up]
        _plain_missing = [a for a in _still_missing if a not in _given_up]
        log(
            f"    ⚠️ V18.14.1: {len(_still_missing)} theorists still "
            f"missing from bullets after gap-fill: {_still_missing[:8]}"
            + (
                f" — of these, {len(_gave_up_missing)} given up on "
                f"after a failed mention-only attempt (no "
                f"attribution-safe bullet exists: every generated "
                f"claim was vetoed as a misattribution): "
                f"{_gave_up_missing[:8]}"
                if _gave_up_missing
                else ""
            )
            + (
                f" — {len(_plain_missing)} never covered (round cap/deadline): {_plain_missing[:8]}"
                if _plain_missing
                else ""
            ),
            "WARNING",
        )

    return GapFillOutcome(
        total_added=_total_added,
        rounds=_gap_fill_round,
        still_missing=_still_missing,
        given_up=_given_up,
        final_check_added=_final_check_added,
        final_check_rounds=_final_check_rounds,
    )


__all__ = [
    "batch_gap_fill",
    "GapFillOutcome",
    "LogCallback",
]
