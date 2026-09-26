"""V0.4.40: the post-conversion verification + polish LAYER.

A post-output LLM layer that runs AFTER ``render_summary_markdown``
assembles the final per-chapter output. The generation LLM already did
a 7/10 job; this layer fills holes + fixes mistakes to make it 9/10-10/10.
The LLM is in a VERIFICATION role (not generation) — it spends its full
context + attention on fixing mistakes instead of generating from scratch
(division of labor). Runs every conversion (non-skippable — catches
LLM-variance-driven defects each run).

**Focus** (the 4 concerns that slip past the deterministic in-pipeline
postchecks):
  1. DATES — every ``(Author Year)`` citation's year matches the source.
  2. NAMES — every cited author is a real source author, correctly
     attributed (not fabricated/garbled/misattributed).
  3. CRITICAL OMISSIONS — key source claims/contributors the summary
     missed (the binding-constraint class — the V0.4.37/V0.4.38
     coverage regressions were thorough omissions).
  4. HALLUCINATIONS — fabricated claims not in the source.

**Design** — mirrors the proven D3/garble LLM-repair pattern
(``repair_d3_quotes_via_llm`` / ``repair_garbles_via_llm``):
  - **Targeted corrections, NOT a full rewrite.** The LLM returns a JSON
    array of ``{original, corrected, reason}``; the system applies each
    as a verbatim string replacement (the ``original`` must be an exact
    substring). The LLM can't rewrite the whole summary — only propose
    located fixes. This is the key safety lever (avoids the V0.02
    ``auto_repair`` full-rewrite corruption failure mode).
  - **D3-style guard.** After applying corrections, re-run the
    deterministic postchecks (garbles + stray-quotes) on the polished
    output. Reject (keep the original) if the polished output has MORE
    deterministic flags OR is >15% different in length. Strict-
    improvement.
  - **Fail-open.** If the LLM call fails / returns malformed JSON / no
    corrections apply, the original output is kept unchanged. The
    verification layer NEVER breaks the conversion.
  - **Content-agnostic (Rule 1).** The verification prompt checks
    against the runtime source for ANY book — no hardcoded names/dates/
    concepts. Works on a physics textbook, a novel, or a cooking manual.
  - **Audit trail.** Every applied correction is logged as a
    ``verification`` Issue (severity="fix") in the conversion log; the
    human 4-pillar audit can see exactly what the layer changed.

**Architectural rationale** (per the user's direction): adding more
in-pipeline deterministic MODULES is fragile — every book is different,
each module catches some defects but misses others, + the combination is
leaky. This LAYER catches the RESIDUE — whatever mistakes passed the
in-pipeline mistake-proofing — by operating on the FINAL assembled
output with a semantic LLM check the deterministic checks can't do.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from core.summarisation.postchecks.shared import Issue, logger

# Local type alias (mirrors the convention in scholar_reflection/gap_filler/etc.).
LogCallback = Callable[[str, str], None]

# ─────────────────────────────────────────────────────────────────────────────
# V0.4.40: the verification + polish prompt.
#
# Genre-agnostic (Rule 1): the prompt verifies the summary against the
# runtime source for ANY book. The 4 focus areas (Dates, Names, Omissions,
# Hallucinations) are universal concerns (any discipline's citations have
# years + authors; any summary can omit or fabricate). The prompt asks for
# TARGETED corrections (a JSON array of exact-substring replacements), NOT
# a full rewrite — the system applies each correction verbatim, so the LLM
# can't rewrite the whole summary (avoids the V0.02 auto_repair failure
# mode where a full-rewrite corrupted valid paraphrase words).
# ─────────────────────────────────────────────────────────────────────────────

_VERIFICATION_PROMPT = """You are a verification + polish pass. The SUMMARY below was generated from the SOURCE text. The summary is already a ~7/10 job; your task is to fill holes + fix mistakes to make it 9/10-10/10. Verify the summary against the source for exactly these 4 concerns:

1. DATES: every "(Author Year)" citation — the year must match the source. If a year is wrong, correct it.
2. NAMES: every cited author — the name must be a real source author AND correctly attributed. If a name is wrong/fabricated/misattributed, correct it (or remove the fabricated claim).
3. CRITICAL OMISSIONS: key source claims/contributors the summary missed. Add a concise grounded bullet (or thorough sentence) for each critical omission.
4. HALLUCINATIONS: fabricated claims (claims not in the source). Remove or correct each.

Return a JSON array of TARGETED corrections. Each correction MUST be: {"original": "<an EXACT substring of the summary to replace>", "corrected": "<the replacement text>", "reason": "<one of: date|name|omission|hallucination>"}.

Rules:
- The "original" field MUST be an EXACT substring of the SUMMARY (copied verbatim, including punctuation) so it can be located + replaced. If you can't quote an exact substring, don't propose the correction.
- Do NOT rewrite the whole summary. Only targeted, located corrections.
- For omissions, the "original" can be a short anchor substring where the new bullet/sentence should be INSERTED (the "corrected" is the anchor + the new content).
- Return [] if no corrections are needed.
- Output ONLY the JSON array, no commentary, no markdown fences.

SOURCE TEXT (for verification):
{source}

SUMMARY TO VERIFY:
"""


def _extract_corrections(raw: str) -> list[dict]:
    """Extract the JSON array of corrections from the LLM response.

    Fail-open: returns [] if no valid JSON array is found. Handles
    ```json fences + surrounding commentary.
    """
    if not raw:
        return []
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Find the first [...] block.
    m = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not m:
        # Maybe an empty array "[]".
        if re.search(r"\[\s*\]", text):
            return []
        return []
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [c for c in parsed if isinstance(c, dict)]


def _count_polish_guard_flags(text: str, source_text: str, field_label: str) -> int:
    """Count the deterministic postcheck flags (garbles + stray-quotes) on a
    text. Used by the D3-style guard to verify the polished output doesn't
    introduce new structural defects.
    """
    if not text:
        return 0
    try:
        from core.summarisation.postchecks.garble.dropped_letter import (
            detect_dropped_letter_garble,
        )
        from core.summarisation.postchecks.garble.quote_repair import (
            repair_stray_quotes_v2,
        )
        from core.summarisation.postchecks.garble.token_detectors import (
            detect_word_fragment_merge,
        )

        source_words = set(re.findall(r"\b[a-z]+\b", (source_text or "").lower()))
        _, sq = repair_stray_quotes_v2(text, field_label)
        _, frag = detect_word_fragment_merge(
            text, field_label, source_text or "", source_words=source_words
        )
        _, dropped = detect_dropped_letter_garble(
            text, field_label, source_text or "", source_words=source_words, auto_repair=False
        )
        return len(sq or []) + len(frag or []) + len(dropped or [])
    except Exception:
        logger.warning("polish-guard flag count crashed (non-fatal); returning 0")
        return 0


def verify_and_polish_summary(
    rendered_md: str,
    source_text: str,
    settings=None,
    log: LogCallback | None = None,
) -> tuple[str, list[Issue]]:
    """V0.4.40: the post-conversion verification + polish LAYER.

    Sends the rendered per-chapter summary + a clamped (≤50k-char) source
    excerpt to the LLM with the verification prompt. The LLM returns
    TARGETED corrections (a JSON array of ``{original, corrected, reason}``);
    the system applies each as a verbatim string replacement. D3-style
    guard: reject (keep the original) if the polished output has MORE
    deterministic flags OR is >15% different in length. Fail-open.

    Args:
        rendered_md: the rendered per-chapter summary markdown (the output
            of ``render_summary_markdown``).
        source_text: the chapter source text (for verification + the guard).
        settings: optional Settings; built from ``utils.settings.Settings``
            when None.
        log: optional log callback.

    Returns:
        ``(polished_md, issues)``. Each issue is a ``verification`` fix
        (a correction applied) or flag (the layer kept the original).
    """
    issues: list[Issue] = []
    if not rendered_md or not source_text:
        return rendered_md, issues

    if settings is None:
        from utils.settings import Settings as _S

        settings = _S()

    model = settings.get("summarisation.model", "") or settings.get(
        "summarisation.primary_model", ""
    )
    if not model:
        return rendered_md, issues  # no model configured → no-op (fail-open)

    try:
        # V0.4.13 pattern: use the provider abstraction (Ollama + llama.cpp).
        from core.llm.llm_provider_impl import create_provider

        arch = settings.get("summarisation.model_architecture", "single_local") or "single_local"
        if arch == "llamacpp":
            provider_name = "llamacpp"
        elif arch in ("single_api", "dual_api"):
            provider_name = settings.get("summarisation.cloud_provider", "openai_compatible")
        else:
            provider_name = "ollama"

        if provider_name not in ("ollama", "llamacpp"):
            return rendered_md, issues  # cloud providers not supported for repair

        provider = create_provider(provider_name, settings)
        if not provider:
            return rendered_md, issues

        # The verification needs the full source (to check omissions +
        # hallucinations), not just a 20k excerpt like the garble repair.
        # Clamp to 50k chars (~10k tokens) for very long chapters.
        # NOTE: use .replace (not .format) — the prompt contains literal
        # JSON-brace examples {"original": ...} that .format would try to
        # interpret as format fields (KeyError).
        source_excerpt = (source_text or "")[:50000]
        prompt = _VERIFICATION_PROMPT.replace("{source}", source_excerpt) + rendered_md
        raw = provider.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=8192,
            model=model,
        )

        if not raw or len(raw) < 10:
            return rendered_md, issues  # empty/short response → no-op

        corrections = _extract_corrections(raw)
        if not corrections:
            return rendered_md, issues  # no corrections proposed → no-op

        # Apply targeted corrections (verbatim string replacements).
        polished = rendered_md
        applied = 0
        skipped = 0
        for c in corrections:
            orig = str(c.get("original", ""))
            corr = str(c.get("corrected", ""))
            reason = str(c.get("reason", "unknown"))
            if not orig or orig == corr:
                continue
            if orig in polished:
                polished = polished.replace(orig, corr, 1)
                applied += 1
                issues.append(
                    Issue(
                        detector="verification",
                        severity="fix",
                        field="summary",
                        snippet=orig[:60],
                        detail=(f"applied {reason} correction: {orig[:50]!r} -> {corr[:50]!r}"),
                    )
                )
            else:
                # The LLM's "original" wasn't an exact substring — skip.
                skipped += 1
        if applied == 0:
            if skipped:
                issues.append(
                    Issue(
                        detector="verification",
                        severity="flag",
                        field="summary",
                        snippet=rendered_md[:60],
                        detail=(
                            f"verification proposed {skipped} correction(s) but "
                            f"none matched an exact substring — original kept."
                        ),
                    )
                )
            return rendered_md, issues

        # D3-style guard: length check (no major rewrite).
        orig_len = len(rendered_md)
        polish_len = len(polished)
        if not (0.85 * orig_len <= polish_len <= 1.15 * orig_len):
            issues.append(
                Issue(
                    detector="verification",
                    severity="flag",
                    field="summary",
                    snippet=rendered_md[:60],
                    detail=(
                        f"verification rejected: polished length {polish_len} outside "
                        f"85-115% of original {orig_len} — original kept."
                    ),
                )
            )
            return rendered_md, issues

        # D3-style guard: flag-count check (no new structural defects).
        pre_flags = _count_polish_guard_flags(rendered_md, source_text, "summary")
        post_flags = _count_polish_guard_flags(polished, source_text, "summary")
        if post_flags > pre_flags:
            issues.append(
                Issue(
                    detector="verification",
                    severity="flag",
                    field="summary",
                    snippet=rendered_md[:60],
                    detail=(
                        f"verification rejected: polished output has {post_flags} "
                        f"deterministic flags (was {pre_flags}) — correction introduced "
                        f"new structural defects; original kept."
                    ),
                )
            )
            return rendered_md, issues

        if log:
            log(
                f"    ✨ V0.4.40 verification: applied {applied} targeted correction(s) "
                f"({skipped} skipped) — polished output "
                f"({polish_len} chars, {post_flags} flags vs {pre_flags}).",
                "INFO",
            )
        return polished, issues
    except Exception as e:
        logger.warning("verification phase crashed (non-fatal): %s: %s", type(e).__name__, e)
        issues.append(
            Issue(
                detector="verification",
                severity="flag",
                field="summary",
                snippet=rendered_md[:60],
                detail=f"verification phase failed: {type(e).__name__}: {e} — original kept.",
            )
        )
        return rendered_md, issues
