"""V18.11 (Phase 5 Stage 3, Batch 1.3 + 1.4): Bullet consolidation.

Extracted verbatim from ``Summarizer`` (god-class decomposition Stage 3). Two
related dedup/consolidation passes:

1. ``consolidate_duplicate_claims`` — deterministic rapidfuzz-based near-dup
   merge (no LLM). The "deterministic fallback" used when the LLM
   consolidation leaks metadata.
2. ``consolidate_bullets`` — LLM-assisted consolidation with a leak-guard
   that rejects LLM output and falls back to (1) when the LLM leaks its
   dedup reasoning into the bullet content.

**Extraction map**:

| Summarizer method (old)            | bullet_consolidation function (new)  | self deps                          |
|------------------------------------|--------------------------------------|------------------------------------|
| ``_consolidate_duplicate_claims``  | ``consolidate_duplicate_claims``     | ``log`` (2 calls, DEBUG)           |
| ``_consolidate_bullets``            | ``consolidate_bullets``              | ``log``, ``prompt_manager``, ``_select_prompt``, ``_call_llm_with_empty_retry``, ``primary_model``, ``temperature``, ``_strip_thinking`` (delegate), ``_leak_guard_fire_count`` (mutable int → returned), ``_consolidate_duplicate_claims`` (delegate) |

Each function is extracted VERBATIM — the only change is ``self.X`` → a named
parameter. The Summarizer methods now delegate to these functions.

**Mutable-state handling for ``_leak_guard_fire_count``**: the original
``_consolidate_bullets`` mutates ``self._leak_guard_fire_count`` (a plain
``int``) when the leak-guard fires. ``test_leak_guard_counter.py`` manipulates
this attribute directly (``s._leak_guard_fire_count += 1``), so it MUST stay a
plain ``int`` on the Summarizer instance. The extracted
``consolidate_bullets`` therefore takes ``leak_guard_fire_count: int`` as an
input parameter and RETURNS the (possibly incremented) new count alongside the
consolidated bullets:

    consolidated, self._leak_guard_fire_count = bc_consolidate_bullets(
        bullets, leak_guard_fire_count=self._leak_guard_fire_count, ...
    )
    return consolidated

This keeps the attribute a plain ``int`` (no type change), preserves the
byte-for-byte increment + read behaviour, and satisfies the existing
characterization tests.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object
like the failed ``PromptContext``). Matches the proven Phase 4 + Phase 5
pattern.

Characterization tests: ``tests/test_bullet_consolidation.py`` captures
canned inputs → golden outputs for both functions. The existing
``tests/test_consolidation_leak_guard.py`` (which tests
``BulletPipeline.detect_leaked_consolidation_metadata`` directly) and
``tests/test_deadline_watchdog.py`` (which asserts the source contains
``self._consolidate_bullets(bullets)`` after the deadline guard) must
continue to pass unchanged.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the summary_validator/llm_dispatcher convention).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
SelectPromptFn = Callable[[str], str]
CallLlmFn = Callable[..., str | None]
StripThinkingFn = Callable[[str], str]


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── consolidate_duplicate_claims (extracted verbatim) ──────────────────────


def consolidate_duplicate_claims(
    bullets: list[str],
    *,
    log: LogCallback | None = None,
) -> list[str]:
    """V13.44.0 Idea #5: Dedup consolidation pass.

    After B4 merges bullets from multiple sections, detect bullets making
    the same claim about different subjects and merge them.

Example: "AuthorL views X as a defining condition" + "AuthorD views X as a defining condition"
→ "AuthorL and AuthorD both view X as a defining condition"

    Uses rapidfuzz to detect near-duplicate sentence structures (same claim,
    different subject). Deterministic — no LLM call.

    Extracted verbatim from ``Summarizer._consolidate_duplicate_claims``. The
    only change is ``self.log(...)`` → ``log(...)`` (with ``_noop_log``
    default). All logic — the punctuation-normalize exact dedup, the 0.92
    fuzzy threshold, the symmetric-difference subject-name extraction, the
    "X and Y both [claim]" merge template — is byte-for-byte identical.
    """
    log = log or _noop_log
    if len(bullets) < 2:
        return bullets

    try:
        from rapidfuzz import fuzz as rf_fuzz
        has_rf = True
    except ImportError:
        has_rf = False

    # First pass: exact dedup (normalize punctuation)
    seen = set()
    unique_bullets = []
    for bp in bullets:
        norm = re.sub(r'[^\w\s]', '', str(bp).lower()).strip()
        if norm and norm not in seen:
            seen.add(norm)
            unique_bullets.append(str(bp))

    if len(unique_bullets) < 2 or not has_rf:
        return unique_bullets

    # Second pass: fuzzy merge — detect bullets with >85% similarity
    # that differ only in the subject name (e.g., "AuthorL" vs "AuthorD")
    merged = []
    used = set()
    for i, bp1 in enumerate(unique_bullets):
        if i in used:
            continue
        merge_group = [bp1]
        for j in range(i + 1, len(unique_bullets)):
            if j in used:
                continue
            bp2 = unique_bullets[j]
            # Check if the two bullets are structurally similar
            sim = rf_fuzz.token_set_ratio(bp1.lower(), bp2.lower()) / 100.0
            # V17.4: Raised threshold from 0.85 → 0.92 to be less aggressive.
            # The V17.1.3 conversion merged 30 of 61 bullets (49%!) — too
            # many unique bullets were lost. With 0.92, only near-exact
            # duplicates merge, preserving more unique information.
            if sim >= 0.92:
                # Check if they differ in a subject name (not just rewording)
                words1 = set(bp1.lower().split())
                words2 = set(bp2.lower().split())
                diff_words = words1.symmetric_difference(words2)
                # If the difference is small (1-3 words), it's likely a subject merge
                if 0 < len(diff_words) <= 6:
                    merge_group.append(bp2)
                    used.add(j)
                    log(f"    \U0001f527 Consolidated: '{bp1[:40]}\u2026' + '{bp2[:40]}\u2026' (sim={sim:.2f})", "DEBUG")
        used.add(i)

        if len(merge_group) > 1:
            # Merge: extract the common subject names and combine
            subjects = []
            for bp in merge_group:
                # Try to extract the first proper noun or name
                words = bp.split()
                for w in words[:5]:
                    if w[0].isupper() and len(w) > 2 and w not in ("The", "This", "These", "Those", "A", "An", "In", "While", "When", "If"):
                        if w not in subjects:
                            subjects.append(w)
                        break
            if len(subjects) >= 2:
                # Create merged bullet: "X and Y both [common claim]"
                # Use the first bullet as template, replace the first subject with combined
                template = merge_group[0]
                first_subject = subjects[0]
                combined_subjects = " and ".join(subjects)
                merged_bp = template.replace(first_subject, combined_subjects, 1)
                # Add "both" if not present
                if "both" not in merged_bp.lower():
                    merged_bp = merged_bp.replace(combined_subjects, f"{combined_subjects} both", 1)
                merged.append(merged_bp)
                log(f"    \U0001f527 Merged {len(merge_group)} bullets \u2192 '{merged_bp[:60]}\u2026'", "DEBUG")
            else:
                merged.extend(merge_group)
        else:
            merged.append(bp1)

    return merged


__all__ = [
    "consolidate_duplicate_claims",
    "consolidate_bullets",
    "LogCallback",
]


# ── consolidate_bullets (extracted verbatim) ────────────────────────────────


def consolidate_bullets(
    bullets: list[str],
    *,
    leak_guard_fire_count: int,
    prompt_manager: PromptManagerLike,
    select_prompt: SelectPromptFn,
    call_llm_with_empty_retry: CallLlmFn,
    primary_model: str,
    temperature: float,
    strip_thinking: StripThinkingFn,
    consolidate_duplicate_claims: Callable[[list[str]], list[str]],
    log: LogCallback | None = None,
    author_coverage_fn: Callable[[list[str]], set | None] | None = None,
) -> tuple[list[str], int]:
    """V16.0.2: LLM-assisted bullet consolidation (merge near-duplicates).

    Extracted verbatim from ``Summarizer._consolidate_bullets``. Returns a
    ``(consolidated_bullets, new_leak_guard_fire_count)`` tuple — the caller
    (the thin delegate on Summarizer) unpacks and assigns the count back to
    ``self._leak_guard_fire_count`` (which must stay a plain ``int`` per
    ``test_leak_guard_counter.py``).

    V18.2.38 (output-format guard): after the LLM returns its consolidated
    bullets, we run ``BulletPipeline.detect_leaked_consolidation_metadata``
    to detect leaked dedup-reasoning (e.g. "Bullet 11:", "KEEP BOTH",
    "This is similar to bullet 27"). When leaked metadata is detected, we
    REJECT the LLM output and fall back to the deterministic rapidfuzz-based
    dedup (``consolidate_duplicate_claims``), which never leaks metadata.
    This preserves all unique bullets (no hard cap on count — closely
    related bullets are preferred over omission, per user policy).

    V18.20.3.7 (audit v182036 RC-A — consolidation coverage assertion): the
    optional ``author_coverage_fn(bullets) -> set`` callback enables a
    deterministic MUST-KEEP assertion on the LLM result. The V18.20.3.6
    rig run's consolidation call degenerated (25,735 chars out, cut at the
    6144-token cap, done_reason=length) and the salvage read "42 → 37
    bullets (merged 5)" while silently DESTROYING part of the scholar
    gap-fill's coverage — 5 authors vanished between consolidation input
    and output, the 50% over-merge guard saw only 11.9%, and the pipeline
    had NO check between consolidation and the judge. Now:

    * coverage BEFORE vs AFTER the consolidation is measured with the SAME
      deterministic author-extraction the judge uses;
    * ANY covered-author loss on a non-truncated response → REJECT the
      consolidation, keep the originals ("more bullets is better than
      lower coverage" — standing user rule);
    * a truncated response (done_reason=length, via
      ``core.llm.call_meta``) gets a salvage: the salvaged set + the
      original bullets of every lost author are re-appended (a loss is
      allowed ONLY among bullets the response had already re-emitted
      before the cut); if the salvage would exceed the input count, the
      originals win outright.

    The callback returning ``None`` (probe failure / no analysis) disables
    the assertion — it must never break the chapter.
    """
    log = log or _noop_log
    # Local mutable copy of the fire counter — incremented only in the
    # leak-detected branch; returned to the caller for re-assignment to self.
    fire_count = leak_guard_fire_count

    # V18.20.3.7 (RC-A.1): deterministic author coverage BEFORE the call —
    # the must-keep set for the post-consolidation assertion.
    covered_before = None
    if author_coverage_fn is not None:
        try:
            covered_before = author_coverage_fn(bullets)
        except Exception:
            covered_before = None  # assertion disabled — never break the chapter

    if len(bullets) < 5:
        return bullets, fire_count

    # V18.20.3.11 (Phase 3.b, .3.9 rig audit §2 — consolidation merged-0
    # three runs running): deterministic pre-check BEFORE the LLM call.
    # The consolidation LLM call costs 218-290s/chapter on the rig and
    # merged 0 bullets in THREE consecutive runs (.3.7/.3.8/.3.9: the
    # telemetry line read "41 → 41, merged 0" every time) while the
    # deterministic probe below ALSO finds 0 mergeable pairs on those
    # lists. The LLM prompt's own bar ("95% identical" merge guidance) is
    # STRICTER than the probe's 0.92 rapidfuzz threshold, so a probe-zero
    # list has nothing for the LLM to merge either. Probe says 0
    # candidates → skip the call entirely; probe finds candidates → run
    # the LLM exactly as before. A probe crash NEVER skips the call.
    _probe_merged = -1
    try:
        _probe_out = consolidate_duplicate_claims(list(bullets))
        if isinstance(_probe_out, list):
            _probe_merged = len(bullets) - len(_probe_out)
    except Exception:
        _probe_merged = -1
    if _probe_merged == 0:
        log(
            f"    🔧 Bullet consolidation SKIPPED — deterministic probe found "
            f"0 mergeable pairs ({len(bullets)} bullets, LLM call not needed; "
            f"rig .3.7-.3.9: the LLM merged 0 on the same input shape)",
            "INFO",
        )
        return bullets, fire_count

    log(f"    \U0001f527 V16.0.2 Bullet consolidation: {len(bullets)} bullets \u2192 LLM...", "INFO")
    # V16.0.3 FIX: Use the passed prompt_manager (the Summarizer's, already
    # initialized in __init__) instead of _get_prompt_manager() which doesn't
    # exist at module level.
    numbered = "\n".join(f"{i+1}. {bp}" for i, bp in enumerate(bullets))
    # V18.2.44 (Next Step #4): Pick the LOW-BIT consolidation prompt for
    # low-bit quant models (IQ2_XXS/XS/S, Q2_K*, IQ1*). The original
    # ``bullet_consolidation.md`` has a 6-step PROCESS + a "95% identical"
    # threshold + a "count should be close to input count" hint — this
    # COMPLEXITY invites low-bit quants to leak their dedup reasoning into
    # the bullet content ("Bullet 11:", "KEEP BOTH", "These are related
    # but different facts"). The V18.2.38 leak guard catches the leak and
    # falls back to deterministic rapidfuzz dedup, but that wastes an LLM
    # call AND means the consolidation step adds zero value for these
    # models. The dedicated ``bullet_consolidation_lowbit.md`` prompt is
    # short, imperative, and provides a concrete few-shot example so the
    # model learns the output format by pattern-matching instead of by
    # reasoning (which is what leaks). For full-precision / large models
    # the original (richer) prompt is kept — they handle it fine.
    #
    # V18.5 (Phase 3, Task 3.3): now uses the shared select_prompt helper
    # instead of inlining the is_low_bit_quant check. Behaviour is identical
    # — the helper checks for the _lowbit variant's existence and falls
    # back to the base name if missing.
    _consolidation_prompt_name = select_prompt(
        "summarisation/bullet_consolidation"
    )
    prompt = prompt_manager.render_template(_consolidation_prompt_name, bullets=numbered)
    if not prompt:
        log("    \u26a0\ufe0f Bullet consolidation: prompt file not found, skipping", "WARNING")
        return bullets, fire_count
    try:
        # V17.1.3: Moved consolidation from FAST → HEAVY.
        # The fast model (LFM2.5-2.6B) is too small for this task — it
        # echoes the input format ("Bullet 1:", "Bullet 2:"), leaks
        # chain-of-thought ("I need to systematically group them"), and
        # produces cluster headers instead of clean merged bullets.
        # The consolidation prompt has a 7-step process that requires
        # semantic understanding + format following — only the heavy
        # model handles it reliably.
        raw = call_llm_with_empty_retry(
            prompt, model=primary_model,
            # V18.20.3.1 (real-rig audit D7): 2048 → 4096. The V18.20.3.0
            # the rig-test book run cut the consolidation response at the
            # 2048 cap mid-generation (done_reason=length, 8272 chars out)
            # — the parser then read "26 → 15 bullets (merged 11)" when
            # part of those 11 were silently LOST to the cut, not merged.
            # The 50% over-merge guard only catches big losses; a ~40%
            # loss sails under it. 4096 gives the consolidated list room
            # to finish (still under the 8192 output ceiling).
            # V18.20.3.2 (audit D7 follow-up / P1-d): 4096 → 6144. The
            # V18.20.3.1 run STILL hit the 4096 cap (done_reason=length,
            # 15,214 chars out — consolidation of a 47-bullet list) and
            # bullet[25] shipped truncated post-consolidation. 6144 = 75%
            # of the 8192 output ceiling; the consolidation of a ~50-bullet
            # list needs ~5k output tokens.
            temperature=temperature, max_tokens=6144,
        )

        # V18.20.3.7 (RC-A.2): was the response cut at the output cap? The
        # provider sets the ContextVar after EVERY response; read-and-reset
        # immediately after the call. A truncated consolidation gets the
        # salvage path below; a non-truncated one is held to the strict
        # assertion.
        _response_truncated = False
        try:
            from core.llm.call_meta import consume_call_truncated
            _response_truncated = consume_call_truncated()
        except Exception:
            pass

        if not raw or len(raw.strip()) < 50:
            log("    \u26a0\ufe0f Bullet consolidation: empty response, keeping original", "WARNING")
            return bullets, fire_count
        raw = strip_thinking(raw)
        import re as _re
        lines = _re.findall(r'(?:^|\n)\s*[-*]\s*(.+?)(?=\n|$)', raw)
        consolidated = []
        seen = set()
        for line in lines:
            b = line.strip()
            if len(b) < 5:
                continue
            key = b.lower()[:60]
            if key not in seen:
                seen.add(key)
                consolidated.append(b)

        # V18.2.38: Output-format guard — detect leaked dedup metadata.
        # If the LLM echoed its internal reasoning (bullet numbering,
        # KEEP/REJECT verdicts, comparison commentary) into the bullet
        # content, REJECT the entire consolidation result and fall back
        # to the deterministic rapidfuzz-based dedup. This never leaks
        # metadata and preserves all unique bullets.
        try:
            from core.summarisation.bullet_pipeline import BulletPipeline
            leaked_count, leaked_samples = (
                BulletPipeline.detect_leaked_consolidation_metadata(consolidated)
            )
            if leaked_count > 0:
                # V18.5 (Phase 3, Task 3.4): increment the per-run
                # leak-guard fire counter. The goal is 0 fires/chapter
                # (the _lowbit prompts should prevent the leak at the
                # source). At >2 fires, escalate — the lowbit prompt
                # isn't working for this model and the guard is carrying
                # the load (band-aid, not fix).
                fire_count += 1
                _fire_count = fire_count
                log(
                    f"    \U0001f6ab Bullet consolidation: leaked {leaked_count} dedup-metadata "
                    f"bullet(s) detected \u2014 REJECTING LLM output, falling back to "
                    f"deterministic rapidfuzz dedup. Samples: "
                    f"{[s[2][:50] for s in leaked_samples[:3]]}\u2026",
                    "WARNING",
                )
                if _fire_count > 2:
                    log(
                        f"    \u26a0\ufe0f\u26a0\ufe0f V18.5: leak-guard has now fired "
                        f"{_fire_count}\u00d7 in this conversion \u2014 the _lowbit "
                        f"consolidation prompt is NOT preventing leaks for "
                        f"model '{primary_model}'. Revisit the prompt: "
                        f"check 'prompts/summarisation/bullet_consolidation_lowbit.md' "
                        f"is up to date and the FORBIDDEN section covers the "
                        f"observed leak patterns. The deterministic fallback "
                        f"is carrying the load (band-aid, not fix).",
                        "WARNING",
                    )
                # Fall back to deterministic dedup — never leaks metadata,
                # preserves all unique bullets (no hard count cap).
                return consolidate_duplicate_claims(bullets), fire_count
        except ImportError:
            # Best-effort: if BulletPipeline can't be imported (e.g. during
            # early bootstrap), skip the guard and use the LLM output.
            pass

        if consolidated and len(consolidated) <= len(bullets):
            # V18.15.4.1: Over-aggressive consolidation guard. If the LLM
            # merged more than 50% of the bullets, it was too aggressive —
            # reject the result and keep the originals. The prompt says to
            # merge only 85%+ identical bullets (typically 0-5 per chapter),
            # but low-bit quants sometimes ignore this and merge everything.
            # This deterministic guard catches that case.
            merge_ratio = 1.0 - (len(consolidated) / len(bullets)) if bullets else 0.0
            if merge_ratio > 0.50:
                log(
                    f"    \u26a0\ufe0f V18.15.4.1: Bullet consolidation too aggressive — merged "
                    f"{len(bullets) - len(consolidated)}/{len(bullets)} bullets ({merge_ratio:.0%}). "
                    f"Threshold is 50%. Keeping originals (the prompt asked for 85%+ identical only).",
                    "WARNING",
                )
                return bullets, fire_count
            if covered_before:
                covered_after = None
                try:
                    covered_after = author_coverage_fn(consolidated)
                except Exception:
                    covered_after = None
                if covered_after is not None:
                    _lost = set(covered_before) - set(covered_after)
                    if _lost:
                        _lost_names = ", ".join(sorted(str(a) for a in _lost)[:8])
                        if not _response_truncated:
                            log(
                                f"    \U0001f6ab V18.20.3.7: Bullet consolidation REJECTED \u2014 it "
                                f"would lose coverage of {len(_lost)} covered "
                                f"author(s): {_lost_names}. Keeping the original "
                                f"bullets (more bullets is better than lower "
                                f"coverage).",
                                "WARNING",
                            )
                            return bullets, fire_count
                        # Truncated response: salvage instead of reject. The
                        # cut happened mid-list, so the lost authors' bullets
                        # may simply lie beyond the cut \u2014 restore the
                        # ORIGINAL bullets covering each lost author (a loss
                        # is allowed only among bullets the response had
                        # already re-emitted before the cut \u2014 i.e. covered
                        # authors, which are not in _lost).
                        _lost_lower = [str(a).lower() for a in _lost]
                        _seen_keys = {
                            _re.sub(r"[^\w\s]", "", str(c).lower()).strip()[:60]
                            for c in consolidated
                        }
                        _restored = []
                        for _ob in bullets:
                            _ob_s = str(_ob)
                            if not any(_la in _ob_s.lower() for _la in _lost_lower):
                                continue
                            _ob_key = _re.sub(
                                r"[^\w\s]", "", _ob_s.lower()
                            ).strip()[:60]
                            if _ob_key in _seen_keys:
                                continue  # already present post-merge
                            _seen_keys.add(_ob_key)
                            _restored.append(_ob_s)
                        if _restored and len(consolidated) + len(_restored) <= len(bullets):
                            log(
                                f"    \U0001fa79 V18.20.3.7: Truncated consolidation salvaged \u2014 "
                                f"restored {len(_restored)} original bullet(s) to "
                                f"preserve coverage of: {_lost_names} "
                                f"({len(bullets)} \u2192 {len(consolidated)} merged, "
                                f"+{len(_restored)} restored).",
                                "WARNING",
                            )
                            consolidated = consolidated + _restored
                        else:
                            log(
                                f"    \U0001f6ab V18.20.3.7: Truncated consolidation REJECTED \u2014 "
                                f"salvage could not preserve coverage of "
                                f"{_lost_names} without exceeding the input "
                                f"count. Keeping the original bullets.",
                                "WARNING",
                            )
                            return bullets, fire_count
            log(f"    \u2705 Bullet consolidation: {len(bullets)} \u2192 {len(consolidated)} bullets (merged {len(bullets) - len(consolidated)})", "INFO")
            return consolidated, fire_count
        else:
            log("    \u2139\ufe0f Bullet consolidation: no improvement, keeping original", "DEBUG")
            return bullets, fire_count
    except Exception as e:
        log(f"    \u26a0\ufe0f Bullet consolidation failed: {e}", "WARNING")
        return bullets, fire_count
