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


class GapFillOutcome(NamedTuple):
    """Outcome of the batch gap-fill loop (logging parity).

    The delegate in ``_summarize_inner`` ignores this return value — the
    original inline block's locals were never read after the block — but
    the characterization tests use it, and a future caller may want the
    counts without re-parsing the log.
    """

    total_added: int
    rounds: int
    still_missing: list
    given_up: set


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
) -> GapFillOutcome:
    """V18.14.1: Batch gap-fill loop — the bullets-only coverage guarantee.

    Extracted verbatim from the ``if _missing:`` block in
    ``Summarizer._summarize_inner`` (V18.20.3.12 / Phase 4 / W6-O5). See
    the module docstring for the extraction map and the free-variable
    inventory. Mutates ``bullets`` in-place (appends the accepted
    gap-fill bullets); returns a ``GapFillOutcome`` for logging parity.
    """
    log = log or _noop_log
    # No-op guard — the original block was wrapped in ``if _missing:``.
    if not missing:
        return GapFillOutcome(total_added=0, rounds=0, still_missing=[], given_up=set())
    import re as _re2
    _sentences = _re2.split(r'(?<=[.!?])\s+', content)
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
        _batch_pool = [
            a for a in _still_missing if a not in _given_up
        ]
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
            a for a in _batch_authors
            if _veto_counts.get(a, 0) >= 2
            or _no_yield_counts.get(a, 0) >= 2
        ]
        log(
            f"    🔍 V18.14.1: Batch gap-fill round {_gap_fill_round}: "
            f"filling {len(_batch_authors)} missing authors: "
            f"{_batch_authors[:5]}{'…' if len(_batch_authors) > 5 else ''}"
            + (
                f" (mention-only: {_mention_only[:5]})"
                if _mention_only else ""
            ),
            "INFO"
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
                _tail_instruction += (
                    f" Begin each bullet with the author's name."  # noqa: F541 — verbatim: carried from _summarize_inner
                )
            _batch_prompt = (
                f"Write ONE bullet point (starting with '- ') for EACH of the following "
                f"authors, summarizing their key contribution as described in the source "
                f"text. Write {len(_batch_authors)} bullets total, one per author.\n\n"
                f"Chapter: {heading}\n\n"
                f"Source excerpts for each missing author:\n{_batch_context}\n"
                f"{_mention_block}\n\n"
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
                    _batch_prompt, max_tokens=2000,
                    temperature=temperature,
                )
                _tl_dur = time.monotonic() - _tl_t0
                _tl = {"dup": 0, "think": 0, "veto": 0, "added": 0}
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
                    _gap_bullets = [l.strip() for l in _raw.split("\n") if l.strip().startswith("-")]  # noqa: E741 — verbatim: carried from _summarize_inner
                    _added = 0
                    _max_gap_bullets = len(_batch_authors) * 2
                    for _gb in _gap_bullets[:_max_gap_bullets]:
                        _gb = _gb.strip()
                        _gb_norm = _re2.sub(r'[^\w\s]', '', _gb.lower()).strip()[:60]
                        _is_dup = any(
                            _gb_norm in _re2.sub(r'[^\w\s]', '', str(b).lower()).strip()[:60]
                            for b in bullets
                        )
                        if _is_dup:
                            _tl["dup"] += 1
                            continue
                        if _gb and len(_gb) > 10:
                            _filtered = filter_thinking_bullets(
                                [_gb], concepts=None, source_text="",
                            )
                            if _filtered:
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
                                    _filtered[0], content,
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
                                    log(
                                        f"    🚫 V18.20.3.2: gap-fill active-subject "
                                        f"veto — dropped '{_filtered[0][:60]}…' "
                                        f"(source attributes this claim to "
                                        f"'{_pv_real}', not '{_pv_claimed}')",
                                        "WARNING",
                                    )
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
                        "INFO"
                    )
                    # V18.20.3.7 (RC-C): the round's fate,
                    # breakdown-visible. `parsed` counts
                    # raw "- " lines from the response.
                    log(
                        f"    📊 V18.20.3.7: round {_gap_fill_round} telemetry "
                        f"({_tl_dur:.1f}s): response="
                        f"{len(_gap_bullets) if _gap_bullets else 0} bullet lines, "
                        f"dup={_tl['dup']}, think-filtered={_tl['think']}, "
                        f"vetoed={_tl['veto']}, added={_tl['added']}",
                        "DEBUG"
                    )
                elif not _raw:
                    # Empty response: still emit the
                    # telemetry line so the round is
                    # countable in the log (the WARNING
                    # above names the emptiness).
                    log(
                        f"    📊 V18.20.3.7: round {_gap_fill_round} telemetry "
                        f"({_tl_dur:.1f}s): response=EMPTY, "
                        f"dup=0, think-filtered=0, vetoed=0, added=0",
                        "DEBUG"
                    )
            except Exception as _be:
                log(f"    ⚠️ V18.14.1: Batch gap-fill round {_gap_fill_round} failed: {_be}", "WARNING")
                break  # stop the loop on persistent failures

        # Re-check bullets-only coverage to see what's still missing
        _bullets_only_after = ' '.join(bullets) if bullets else ''
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
                _no_yield_counts[_ya] = (
                    _no_yield_counts.get(_ya, 0) + 1
                )
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
                "DEBUG"
            )

    if _total_added > 0:
        log(
            f"    ✅ V18.14.1: Batch gap-fill complete — "
            f"added {_total_added} bullets across {_gap_fill_round} round(s)",
            "INFO"
        )
    if _still_missing:
        # V18.20.3.4 (RC-4): split the report — authors
        # we actively gave up on (persistent veto) vs
        # authors that simply never landed. The operator
        # needs to know which class each name is in.
        _gave_up_missing = [
            a for a in _still_missing if a in _given_up
        ]
        _plain_missing = [
            a for a in _still_missing if a not in _given_up
        ]
        log(
            f"    ⚠️ V18.14.1: {len(_still_missing)} theorists still "
            f"missing from bullets after gap-fill: {_still_missing[:8]}"
            + (
                f" — of these, {len(_gave_up_missing)} given up on "
                f"after a failed mention-only attempt (no "
                f"attribution-safe bullet exists: every generated "
                f"claim was vetoed as a misattribution): "
                f"{_gave_up_missing[:8]}"
                if _gave_up_missing else ""
            )
            + (
                f" — {len(_plain_missing)} never covered "
                f"(round cap/deadline): {_plain_missing[:8]}"
                if _plain_missing else ""
            ),
            "WARNING"
        )

    return GapFillOutcome(
        total_added=_total_added,
        rounds=_gap_fill_round,
        still_missing=_still_missing,
        given_up=_given_up,
    )


__all__ = [
    "batch_gap_fill",
    "GapFillOutcome",
    "LogCallback",
]
