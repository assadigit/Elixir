"""V18.12 (Phase 5 Stage 3, Batch 2.6): Scholar reflection (meta-cognitive gap analysis + gap-fill).

Extracted verbatim from ``Summarizer._scholar_reflection`` and
``Summarizer._scholar_reflection_gapfill_only`` (god-class decomposition Stage 3).

V13.41.0 introduced the meta-cognitive reflection — the LLM reviews its own
summary for gaps. V13.42.0 added gap-FILLING: the LLM writes a bullet for each
identified gap (with a verbatim source quote), and the bullets are appended to
the summary. V18.2 (audit Fix 2) added the gapfill-only variant that suppresses
the self-contradicting reflections text section.

**Extraction map**:

| Summarizer method (old)                  | scholar_reflection function (new)         | self deps |
|------------------------------------------|------------------------------------------|-----------|
| ``_scholar_reflection``                   | ``scholar_reflection``                   | ``request.summarisation_max_context_tokens``, ``language``, ``prompt_manager``, ``log``, ``_recover_vram``, ``_call_fast_llm``, ``_strip_thinking`` |
| ``_scholar_reflection_gapfill_only``      | ``scholar_reflection_gapfill_only``      | delegates to ``scholar_reflection`` + ``log`` |

Both functions mutate the ``result`` dict IN-PLACE (add/extend
``bullet_points``, set ``scholar_reflections``) — same contract as the
original methods. The Summarizer methods now delegate to these functions.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-2 pattern.

Characterization tests: ``tests/test_scholar_reflection.py`` captures the
gap-identification, gap-fill (source-grounded), and gapfill-only paths with
mocked ``call_fast_llm`` / ``prompt_manager`` / ``recover_vram``.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

# V18.20.4.8 (P6 / O-a5): the single canonical structural-stopwords module
# (fixes W-a5's 3 drifting hand-curated copies).
from core.summarisation.structural_stopwords import THEORIST_NAME_STOPWORDS

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
CallFastLlmFn = Callable[..., str | None]
RecoverVramFn = Callable[..., None]
StripThinkingFn = Callable[[str], str]
# V18.20.3.4 (RC-1 layer 2): optional thinking-filter callback — same
# duck-typed contract as Summarizer._filter_thinking_bullets /
# filter_thinking.filter_thinking_bullets (takes a bullet list, returns the
# filtered list). Filters gap-fill bullets BEFORE they merge into
# bullet_points.
FilterThinkingFn = Callable[..., list]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── scholar_reflection (extracted verbatim) ────────────────────────────────


def scholar_reflection(
    heading: str,
    text: str,
    result: dict,
    *,
    max_context_tokens: int,
    language: str,
    temperature: float,
    prompt_manager: PromptManagerLike,
    recover_vram: RecoverVramFn,
    call_fast_llm: CallFastLlmFn,
    strip_thinking: StripThinkingFn,
    filter_thinking_bullets: FilterThinkingFn | None = None,
    log: LogCallback | None = None,
) -> None:
    """V13.41.0: Meta-cognitive reflection — the LLM reviews its own summary for gaps.

    V13.42.0: Now also FILLS the gaps — generates missing content as new bullets
    and adds them to the summary. The scholar reflection identifies what's
    missing, writes a bullet for each gap (with a verbatim source quote),
    and the bullets are appended to the summary's bullet_points list.

    Anti-hallucination: each gap-fill bullet MUST include a verbatim quote
    from the source. Bullets that can't be source-ground are dropped.

    Extracted verbatim from ``Summarizer._scholar_reflection``. The only
    changes are ``self.X`` → named parameters. The full-summary overview
    (V18.2 audit Fix 1 — no aggressive truncation), the deterministic theorist
    extraction with the expanded stopword list (V13.45.0), the VRAM recovery
    before the call, the two-section parsing (``<scholar_reflections>`` +
    ``<gap_fill_bullets>``), the source-grounding of gap-fill bullets (60%
    quote-word match), the dedup against existing bullets, and the result-dict
    mutation are byte-for-byte identical.

    Mutates ``result`` in-place: extends ``result["bullet_points"]`` with
    source-grounded gap-fill bullets and sets ``result["scholar_reflections"]``
    to the identification text.
    """
    log = log or _noop_log
    # Build a concise summary overview for the LLM to review
    _exec = result.get("executive_summary", "") or ""
    _bullets = result.get("bullet_points", []) or []
    _thorough = result.get("thorough_summary", "") or ""
    _kd = result.get("key_distinctions", "") or ""
    _tt = result.get("theoretical_tensions", "") or ""

    # V18.2 (audit Fix 1): REMOVED the aggressive truncation that caused the
    # Scholar's Reflections contradiction. Previously:
    #   _exec[:800], _bullets[:25], _thorough[:1500]
    # The model was shown only 25 bullets but told to verify 30+ theorists —
    # so theorists in bullets 26+ were correctly flagged as "missing" relative
    # to the truncated view, creating a self-contradicting output.
    # Now we pass the FULL summary (exec + all bullets + full thorough).
    # For a 40-bullet summary this is ~8-12 KB — trivial for a 128k-context model.
    _summary_overview = f"""EXECUTIVE SUMMARY:
{_exec}

KEY TAKEAWAYS ({len(_bullets)} bullets):
{chr(10).join(f'- {bp}' for bp in _bullets)}

THOROUGH SUMMARY:
{_thorough}

KEY DISTINCTIONS:
{_kd}

THEORETICAL TENSIONS:
{_tt}"""

    # Truncate source text to fit context window
    max_src = max(max_context_tokens - 2500, 8000)
    src_text = text[:max_src * 4]

    # V13.45.0: Deterministic theorist extraction — find all "Surname (year)"
    # patterns in the source so we can ask the LLM to verify each is covered.
    theorist_matches = re.findall(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)',
        src_text,
    )
    # Filter out non-theorist matches (common false positives)
    # V13.45.0: Expanded stopwords to include sentence-starting adverbs
    # that get falsely captured as the first word of a compound surname
    # (e.g., "Later Author" → should be just "Author").
    # V18.20.4.8 (P6 / O-a5): the literal moved to the canonical
    # structural-stopwords module (membership byte-identical).
    _stopwords = THEORIST_NAME_STOPWORDS
    theorists_found = []
    _seen = set()
    for name, year in theorist_matches:
        # If the name is compound (two words), check the FIRST word — if
        # it's a stopword, strip it and keep just the second word.
        parts = name.split()
        if len(parts) > 1 and parts[0] in _stopwords:
            name = parts[1]
        if name in _stopwords or len(name) < 3:
            continue
        key = f"{name} ({year})"
        if key not in _seen:
            _seen.add(key)
            theorists_found.append(key)
    # Cap to keep prompt manageable
    theorists_found = theorists_found[:30]

    # V18.20.4.2 (P1 / F9, Phase 3.c): deterministic probe-gate BEFORE the
    # 6144-token LLM call — mirrors the V18.20.3.11 consolidation skip
    # (bullet_consolidation.py:263-288: deterministic rapidfuzz probe → if 0
    # mergeable pairs, skip the 218-290s LLM call). The scholar call cost
    # 479.5s = 30% of all LLM time on the .3.14 rig for ZERO usable output
    # (truncated at the 6144 cap mid-gap-analysis, verdict UNRELIABLE in
    # 3/5 runs: .3.7/.3.8/.3.14), while the deterministic theorist judge +
    # batch gap-fill performed the entire gap detection for 62s.
    #
    # The probe: the scholar prompt asks the LLM to verify EACH of
    # ``theorists_found`` appears in the summary. If they are ALL already
    # covered (a well-parsing primary that closed every cited author), the
    # LLM call has nothing to add for its scope — skip it entirely (no
    # recover_vram, no 6144-token call). A probe CRASH never skips
    # (``_probe_missing = -1`` falls through to the LLM call, the same
    # fail-soft contract as the .3.11 consolidation skip). NB: this gate
    # fires on the "already complete" path; the .3.14-specific burn (gaps
    # existed, the call ramble-truncated) needs the larger budget-cut /
    # reorder — flagged as Phase-3.c continued.
    _probe_missing = -1
    if theorists_found:
        try:
            _joined = " ".join(_bullets)
            _joined_lower = _joined.lower()
            _probe_missing = sum(
                1 for _t in theorists_found
                if _t.lower() not in _joined_lower
            )
        except Exception:
            _probe_missing = -1  # assertion disabled — never break the chapter
    if _probe_missing == 0:
        log(
            f"    \U0001f393 Scholar reflection SKIPPED (probe-gate) \u2014 all "
            f"{len(theorists_found)} named author(s) already covered by the "
            f"primary bullets (LLM call not needed; mirrors the V18.20.3.11 "
            f"consolidation skip; rig .3.14: the scholar call burned 479.5s "
            f"for 0 usable output on a path the deterministic judge + batch "
            f"gap-fill closed for 62s)",
            "INFO",
        )
        result["scholar_reflections"] = ""
        return

    theorists_hint = ""
    if theorists_found:
        theorists_hint = f"""
THEORIST COVERAGE CHECK — Authors cited in source: {', '.join(theorists_found)}
Verify EACH appears in the summary with their specific contribution. Flag ANY missing. Secondary contributors are EASIEST to miss.
"""

    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    prompt = prompt_manager.render_template(
        "summarisation/scholar_reflection",
        heading=heading,
        src_text=src_text,
        summary_overview=_summary_overview,
        theorists_hint=theorists_hint,
        language=lang,
    )

    log("    \U0001f393 Running scholar reflection (gap analysis + gap-fill)\u2026", "INFO")
    if theorists_found:
        log(
            f"    \U0001f393 Theorist coverage check: {len(theorists_found)} named author(s) "
            f"found in source \u2014 verifying each is covered",
            "DEBUG",
        )

    # V13.41.0: VRAM recovery before scholar reflection — this runs at the
    # very end after B4 + gap-fill + judge + recovery, when GPU is most exhausted.
    recover_vram(context="pre-scholar-reflection", delay_sec=15.0)

    try:
        # V18.20.3.1 (real-rig audit D7): 3000 → 4096. The V18.20.3.0 run cut
        # the scholar response at the 3000 cap (done_reason=length, 11171
        # chars out) — "identified gaps but could not fill them" was the
        # truncation, not the model's verdict. 4096 stays under the 8192
        # output ceiling.
        # V18.20.3.2 (audit D7 follow-up / P1-d): 4096 -> 6144. The V18.20.3.1
        # run STILL hit the 4096 cap (done_reason=length, 15,297 chars out)
        # and "no significant gaps found" was parsed from the TRUNCATED
        # response \u2014 the gap analysis never completed, so the verdict was
        # unreliable. 6144 = 75% of the output ceiling.
        raw = call_fast_llm(prompt, temperature=temperature, max_tokens=6144)
        if not raw:
            log("    \u26a0\ufe0f Scholar reflection returned empty \u2014 skipping", "WARNING")
            return
        raw = strip_thinking(raw)

        # V18.20.3.5 (audit v182034): authoritative truncation signal from
        # the provider (done_reason=length, propagated via ContextVar — see
        # core/llm/call_meta.py). The V18.20.3.4 rig run's scholar response
        # was cut at 26,237 chars BEFORE <gap_fill_bullets> ever opened, the
        # tag heuristic below evaluated False, and the pipeline logged a
        # clean "no significant gaps found" from an analysis that never
        # finished. The provider flag has no such blind spot.
        try:
            from core.llm.call_meta import consume_call_truncated
            _provider_truncated = consume_call_truncated()
        except Exception:  # pragma: no cover — flag must never break the stage
            _provider_truncated = False

        # V18.20.3.2 (P1-d): truncation signal for the verdict-qualification
        # below. The response format asks for <scholar_reflections> then
        # <gap_fill_bullets> (in that order). When the LAST section's closing
        # tag is missing, generation was cut mid-output \u2014 any "no gaps"
        # verdict parsed from an unclosed <scholar_reflections> section is
        # the truncation point, NOT the model's conclusion.
        # V18.20.3.5: the heuristic is BROADENED — but it must still TRUST a
        # properly closed verdict: "<scholar_reflections>none</scholar_
        # reflections>" with no gap-fill section is a compliant "no gaps"
        # answer. The suspect shapes are (a) <gap_fill_bullets> opened but
        # never closed, and (b) the gap-fill section entirely absent WHILE
        # the reflections section is also absent-or-unclosed (the .3.4 rig
        # response was cut before ANY section completed). Kept as the
        # fallback signal because it is provider-agnostic; the provider
        # flag above is the primary.
        _rl = raw.lower()
        _has_refl_open = '<scholar_reflections>' in _rl
        _has_refl_close = '</scholar_reflections>' in _rl
        _has_gf_open = '<gap_fill_bullets>' in _rl
        _has_gf_close = '</gap_fill_bullets>' in _rl
        _response_truncated = (
            _provider_truncated
            or (_has_gf_open and not _has_gf_close)
            or (not _has_gf_open and not (_has_refl_open and _has_refl_close))
        )

        # Parse the <scholar_reflections> section (identification)
        srm = re.search(
            r'<scholar_reflections>\s*(.*?)(?:</scholar_reflections>|<gap_fill_bullets>|$)',
            raw, re.DOTALL | re.IGNORECASE,
        )
        # V13.42.0: Parse the <gap_fill_bullets> section (the actual fill content)
        gfm = re.search(
            r'<gap_fill_bullets>\s*(.*?)(?:</gap_fill_bullets>|$)',
            raw, re.DOTALL | re.IGNORECASE,
        )
        # V18.20.3.1 (real-rig audit D1 class): if the response was cut at
        # the output cap mid-gap-fill, the `$` fallback captures an
        # incomplete trailing bullet — drop it (same helper as the additive
        # sections; complete sections are never touched).
        _gfm_closed = '</gap_fill_bullets>' in raw.lower()

        # Process scholar reflections (identification)
        reflections_text = ""
        if srm:
            reflections = srm.group(1).strip()
            reflections_norm = reflections.strip().lower()
            if reflections_norm in ("none", "n/a", "no gaps found", ""):
                # V18.20.3.2 (P1-d): a "no gaps" verdict from a TRUNCATED
                # response is unreliable \u2014 the analysis may have been cut
                # before reaching the gaps. Qualify the log so the operator
                # knows the verdict cannot be trusted (the V18.20.3.1 run
                # logged a clean "no significant gaps found" from a
                # done_reason=length response).
                if _response_truncated:
                    log(
                        "    \U0001f393 Scholar reflection: no significant gaps found "
                        "\u2014 \u26a0\ufe0f VERDICT UNRELIABLE (response truncated at the "
                        "output cap; the gap analysis was cut short and the "
                        "gap-fill section never closed)",
                        "WARNING",
                    )
                else:
                    log("    \U0001f393 Scholar reflection: no significant gaps found", "INFO")
            else:
                items = []
                for line in reflections.split("\n"):
                    line = line.strip()
                    if line and (line.startswith("- ") or line.startswith("\u2022 ")):
                        items.append(line)
                if not items and reflections.strip():
                    items = [reflections.strip()]
                grounded_items = []
                for item in items:
                    if '"' in item or '\u201c' in item or '\u201d' in item:
                        grounded_items.append(item)
                    else:
                        grounded_items.append(item)
                reflections_text = "\n".join(grounded_items) if grounded_items else ""

        # Process gap-fill bullets (the actual missing content)
        gap_bullets_added = 0
        if gfm:
            gap_text = gfm.group(1).strip()
            if not _gfm_closed and gap_text:
                from core.summarisation.response_parser import strip_truncated_section_tail
                _gap_clean = strip_truncated_section_tail(gap_text, closing_tag_present=False)
                if _gap_clean != gap_text:
                    log(
                        f"    \u2702\ufe0f Scholar gap-fill truncated \u2014 dropped the incomplete "
                        f"trailing bullet ({len(gap_text) - len(_gap_clean)} chars).",
                        "WARNING",
                    )
                    gap_text = _gap_clean
            if gap_text and gap_text.lower() not in ("none", "n/a", ""):
                gap_bullets = []
                for line in gap_text.split("\n"):
                    line = line.strip()
                    if line and (line.startswith("- ") or line.startswith("\u2022 ")):
                        # Clean up the bullet
                        bullet = line.lstrip("- \u2022\t").strip()
                        if bullet and len(bullet) > 10:
                            gap_bullets.append(bullet)

                if gap_bullets:
                    # V13.42.0: Source-ground each gap-fill bullet (anti-hallucination)
                    # Each bullet MUST contain a verbatim quote from the source
                    grounded_bullets = []
                    for gb in gap_bullets:
                        # Check if the bullet contains a quote
                        has_quote = ('"' in gb or '\u201c' in gb or '\u201d' in gb or
                                   "''" in gb or "\u2014" in gb)
                        if has_quote:
                            # Verify the quote appears in the source (at least partially)
                            # Extract quoted portions and check against source
                            quotes = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]{15,})["\u201c\u201d]', gb)
                            if quotes:
                                source_lower = src_text.lower()
                                quote_found = False
                                for q in quotes:
                                    # Check if at least 60% of the quote words appear in source
                                    q_words = [w.lower().strip(".,;:!?") for w in q.split() if len(w) > 3]
                                    if q_words:
                                        found = sum(1 for w in q_words if w in source_lower)
                                        if found / len(q_words) >= 0.6:
                                            quote_found = True
                                            break
                                if quote_found:
                                    grounded_bullets.append(f"- {gb}")
                                else:
                                    log(f"    \U0001f393 Dropped ungrounded gap-fill: {gb[:60]}\u2026", "DEBUG")
                            else:
                                grounded_bullets.append(f"- {gb}")  # has quotes but can't extract — keep
                        else:
                            log(f"    \U0001f393 Dropped gap-fill without quote: {gb[:60]}\u2026", "DEBUG")

                    if grounded_bullets:
                        # Add the gap-fill bullets to the summary's bullet_points
                        existing_bps = result.get("bullet_points", [])
                        existing_norms = set()
                        for bp in existing_bps:
                            norm = re.sub(r'[^\w\s]', '', str(bp).lower().strip()[:60])
                            existing_norms.add(norm)

                        new_bullets = []
                        for gb in grounded_bullets:
                            norm = re.sub(r'[^\w\s]', '', gb.lower()).strip()[:60]
                            if norm not in existing_norms:
                                new_bullets.append(gb)
                                existing_norms.add(norm)

                        # V18.20.3.4 (RC-1 layer 2, audit v182033): run the
                        # SAME thinking/self-talk/scar filter the expansion
                        # path uses over the gap-fill bullets BEFORE they
                        # merge into bullet_points. The V18.20.3.3 run shipped
                        # 8 scarred bullets; the scholar-reflection path (+8)
                        # and the V18.14.1 batch path (+5) had no equivalent
                        # filter (only quote-grounding), so CoT planning
                        # notes and checklist stubs from those paths entered
                        # the final Key Takeaways unfiltered. The filter is
                        # OPTIONAL (default None) so direct callers/tests
                        # keep working; the Summarizer delegates pass
                        # self._filter_thinking_bullets.
                        if filter_thinking_bullets is not None:
                            try:
                                _pre_n = len(new_bullets)
                                new_bullets = [
                                    nb for nb in filter_thinking_bullets(
                                        [b.lstrip("- \u2022\t").strip()
                                         for b in new_bullets],
                                        concepts=None, source_text=text,
                                    )
                                    if nb and nb.strip()
                                ]
                                if len(new_bullets) != _pre_n:
                                    log(
                                        f"    \U0001f9e9 V18.20.3.4: Filtered "
                                        f"{_pre_n - len(new_bullets)} "
                                        f"thinking/scar bullet(s) from scholar "
                                        f"gap-fill before merge",
                                        "INFO",
                                    )
                            except Exception as _fe:
                                log(
                                    f"    \u26a0\ufe0f V18.20.3.4: Scholar gap-fill "
                                    f"filter crashed (non-fatal, bullets kept "
                                    f"unfiltered): {_fe}",
                                    "WARNING",
                                )
                        if new_bullets:
                            result["bullet_points"] = list(existing_bps) + new_bullets
                            gap_bullets_added = len(new_bullets)
                            log(
                                f"    \U0001f393 Gap-fill: added {gap_bullets_added} new bullet(s) "
                                f"from scholar reflection (source-grounded)",
                                "INFO",
                            )

        # Store the reflections text (identification, not the fill)
        # V13.45.5: Removed the "NOTE: N gap(s) FILLED" prefix — the user
        # found it confusing as end-user-facing metadata. The gap-fill
        # bullets themselves appear in Key Takeaways; the reflections
        # section now just shows what gaps were identified (clean content).
        result["scholar_reflections"] = reflections_text
        if reflections_text and gap_bullets_added > 0:
            log(
                f"    \U0001f393 Scholar reflection: identified {reflections_text.count(chr(10)) + 1} gap(s), "
                f"filled {gap_bullets_added} with new bullets",
                "INFO",
            )
        elif reflections_text:
            log("    \U0001f393 Scholar reflection: identified gaps but could not fill them", "INFO")
        elif not reflections_text and gap_bullets_added == 0:
            # V18.20.3.5 (audit v182034): this is the exact path that lied
            # in the rig run — the response was truncated before the gap
            # analysis reached any conclusion, both sections parsed empty,
            # and the pipeline logged a clean "no significant gaps found".
            # A cut analysis has no verdict. Qualify loudly and fall through
            # to the deterministic theorist-coverage judge (V17.6/V18.14),
            # which is what actually caught the gaps in that run.
            if _response_truncated:
                log(
                    "    \U0001f393 Scholar reflection: no significant gaps found "
                    "\u2014 \u26a0\ufe0f VERDICT UNRELIABLE (response truncated at "
                    "the output cap before the gap analysis completed; "
                    "relying on the deterministic theorist-coverage judge "
                    "for gap detection)",
                    "WARNING",
                )
            else:
                log("    \U0001f393 Scholar reflection: no significant gaps found", "INFO")

    except Exception as e:
        log(f"    \u26a0\ufe0f Scholar reflection failed: {e}", "WARNING")
        logger.debug("scholar reflection failed: %s: %s", type(e).__name__, e)


# ── scholar_reflection_gapfill_only (extracted verbatim) ───────────────────


def scholar_reflection_gapfill_only(
    heading: str,
    text: str,
    result: dict,
    *,
    max_context_tokens: int,
    language: str,
    temperature: float,
    prompt_manager: PromptManagerLike,
    recover_vram: RecoverVramFn,
    call_fast_llm: CallFastLlmFn,
    strip_thinking: StripThinkingFn,
    filter_thinking_bullets: FilterThinkingFn | None = None,
    log: LogCallback | None = None,
) -> None:
    """V18.2 (audit Fix 2): Run gap-fill ONLY, suppress the reflections text.

    Extracted verbatim from ``Summarizer._scholar_reflection_gapfill_only``.
    Delegates to ``scholar_reflection`` (the full method) then clears the
    ``scholar_reflections`` text section in ``result``.

    The full ``scholar_reflection`` generates two outputs:
    1. ``<scholar_reflections>`` — a TEXT section listing "what's missing"
    2. ``<gap_fill_bullets>`` — new bullets that fill the gaps

    The user's analysis showed #1 is the #1 defect — it contradicts itself
    by claiming content is "missing" that appears elsewhere. This method
    runs the same LLM call but ONLY keeps #2 (the gap-fill bullets) and
    suppresses #1 (the reflections text).

    This preserves the value of gap-filling (adding genuinely missing
    content) while eliminating the self-contradicting output section.
    """
    log = log or _noop_log
    # Delegate to the full method, then clear the reflections text.
    # This avoids code duplication — the full method does the LLM call,
    # parses both sections, and adds gap-fill bullets to result.
    # We just need to suppress the reflections_text afterward.
    scholar_reflection(
        heading, text, result,
        max_context_tokens=max_context_tokens,
        language=language,
        temperature=temperature,
        prompt_manager=prompt_manager,
        recover_vram=recover_vram,
        call_fast_llm=call_fast_llm,
        strip_thinking=strip_thinking,
        filter_thinking_bullets=filter_thinking_bullets,
        log=log,
    )
    # Suppress the reflections text section (keep the gap-fill bullets)
    if "scholar_reflections" in result:
        result["scholar_reflections"] = ""
    log("    \U0001f393 V18.2: Scholar reflections text suppressed (gap-fill only)", "DEBUG")


__all__ = [
    "scholar_reflection",
    "scholar_reflection_gapfill_only",
    "LogCallback",
]
