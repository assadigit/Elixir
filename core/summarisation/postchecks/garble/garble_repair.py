"""V0.4.39 (Option A): LLM semantic repair for flagged garbles.

Extends the V0.4.11/V0.4.13 ``repair_d3_quotes_via_llm`` pattern to
``fragment_merge`` + ``dropped_letter`` garbles. When the postcheck flags
a garbled token (a non-word that is edit-distance-1 from a real source
word, or a word+stray fragment of a dropped sentence boundary), this
sends the text + a clamped source excerpt to the LLM with a "fix ONLY
the garbled tokens, preserve all other text" prompt. Fail-open; D3-style
guard (keep the original if the repair doesn't reduce the garble flag
count). Content-agnostic (Rule 1 — the prompt is about token repair,
not content; works on any chapter).
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.shared import Issue

# ─────────────────────────────────────────────────────────────────────────────
# V0.4.39 (Option A): LLM semantic repair for garbled tokens.
#
# The V0.4.37/V0.4.38 ch.6 audits found garbles that shipped DETECTED+flagged
# but unrepaired (the fragment_merge + dropped_letter detectors are flag-only;
# the dropped_letter auto_repair is default OFF since V0.03 P0-1 because it
# corrupted valid paraphrase words in V0.02). Rather than re-enable the risky
# deterministic auto_repair (V0.02's failure mode), this mirrors the proven
# V0.4.11/V0.4.13 D3 stray-quote LLM-repair pattern: send the flagged text +
# source context to the LLM with a "fix ONLY the garbled tokens" prompt. The
# LLM considers context (no blind edit-distance-1 rewrite), and the D3-style
# guard (keep the original if the repair doesn't reduce the flag count) keeps
# it strict-improvement.
#
# Content-agnostic (Rule 1): the prompt is about TOKEN repair (replace each
# non-word with the most likely real English word intended), not content; the
# source excerpt is generic context. Works on any book/chapter, not tuned to
# any specific garble. Flag-only detectors stay as the honest record; this
# repair is defense-in-depth on top.
# ─────────────────────────────────────────────────────────────────────────────

_GARBLE_REPAIR_PROMPT = """The following text contains garbled/mangled tokens — words that are NOT real English words, likely the result of a dropped sentence boundary or a fused token (e.g. a word with a stray trailing character, or two words fused). Your task: fix ONLY the garbled tokens by replacing each with the most likely real English word intended, using the provided source text as context. Do NOT change any other text, do NOT add or remove sentences, do NOT change punctuation other than fixing the garbled tokens, do NOT reorder content. Output ONLY the corrected text, no commentary.

SOURCE TEXT (for context — the garbled tokens are likely edit-distance-1 from a word in this source):
{source}

TEXT TO FIX:
"""


def _count_garble_flags(
    text: str,
    field_label: str,
    source_text: str,
    source_words: set | None,
) -> int:
    """Count fragment_merge + dropped_letter flags in the text.

    Re-runs both garble detectors (flag-only — ``auto_repair=False`` for
    dropped_letter) and returns the total flag count. Used by the D3-style
    guard to verify the LLM repair reduced the flag count.
    """
    if not text or not source_text:
        return 0
    if source_words is None:
        source_words = set(re.findall(r"\b[a-z]+\b", source_text.lower()))
    if not source_words:
        return 0
    try:
        from core.summarisation.postchecks.garble.dropped_letter import (
            detect_dropped_letter_garble,
        )
        from core.summarisation.postchecks.garble.token_detectors import (
            detect_word_fragment_merge,
        )

        _, frag = detect_word_fragment_merge(
            text, field_label, source_text, source_words=source_words
        )
        _, dropped = detect_dropped_letter_garble(
            text, field_label, source_text, source_words=source_words, auto_repair=False
        )
        return len(frag or []) + len(dropped or [])
    except Exception:
        from core.summarisation.postchecks.shared import logger

        logger.warning("garble-flag count crashed (non-fatal); returning 0")
        return 0


def repair_garbles_via_llm(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
    settings=None,
) -> tuple[str, list[Issue]]:
    """V0.4.39 (Option A): send flagged garble text to the LLM for semantic repair.

    Mirrors ``repair_d3_quotes_via_llm`` (V0.4.11/V0.4.13). When
    ``fragment_merge`` / ``dropped_letter`` flags are present, sends the
    text + a clamped (≤20k-char) source excerpt to the LLM with a "fix
    ONLY the garbled tokens" prompt. Fail-open; D3-style guard (keep the
    original if the repair returns empty/short text OR doesn't reduce the
    garble flag count). Content-agnostic (Rule 1).

    Args:
        text: the summary field text.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the chapter source text (for context + flag-counting).
        source_words: optional precomputed source word-set.
        settings: optional Settings; built from ``utils.settings.Settings``
            when None.

    Returns:
        ``(repaired_text, issues)``. Each issue is a
        ``garble_llm_repair`` fix (repair applied) or flag (repair kept
        the original).
    """
    issues: list[Issue] = []
    if not text:
        return text, issues

    # Check if there are any garble flags to repair.
    pre_flags = _count_garble_flags(text, field_label, source_text, source_words)
    if not pre_flags:
        return text, issues  # no garbles — nothing to repair

    if settings is None:
        from utils.settings import Settings as _S

        settings = _S()

    model = settings.get("summarisation.model", "") or settings.get(
        "summarisation.primary_model", ""
    )
    if not model:
        return text, issues  # no model configured

    try:
        # V0.4.13 pattern: use the provider abstraction (works with Ollama
        # AND llama.cpp).
        from core.llm.llm_provider_impl import create_provider

        arch = settings.get("summarisation.model_architecture", "single_local") or "single_local"
        if arch == "llamacpp":
            provider_name = "llamacpp"
        elif arch in ("single_api", "dual_api"):
            provider_name = settings.get("summarisation.cloud_provider", "openai_compatible")
        else:
            provider_name = "ollama"

        if provider_name not in ("ollama", "llamacpp"):
            return text, issues  # cloud providers not supported for repair

        provider = create_provider(provider_name, settings)
        if not provider:
            return text, issues

        # Clamp the source excerpt (~20k chars) for context.
        source_excerpt = (source_text or "")[:20000]
        prompt = _GARBLE_REPAIR_PROMPT.format(source=source_excerpt) + text
        repaired = provider.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=8192,
            model=model,
        )

        if not repaired or len(repaired) < len(text) * 0.8:
            issues.append(
                Issue(
                    detector="garble_llm_repair",
                    severity="flag",
                    field=field_label,
                    snippet=text[:60],
                    detail="semantic LLM repair returned empty/short text — original kept.",
                )
            )
            return text, issues

        # D3-style guard: verify the repaired text has fewer garble flags.
        post_flags = _count_garble_flags(repaired, field_label, source_text, source_words)
        if post_flags < pre_flags:
            issues.append(
                Issue(
                    detector="garble_llm_repair",
                    severity="fix",
                    field=field_label,
                    snippet=text[:60],
                    detail=(
                        f"semantic LLM repair: fixed {pre_flags - post_flags} garbled "
                        f"token(s) via LLM (was {pre_flags} garble flag(s), now {post_flags})."
                    ),
                )
            )
            return repaired, issues
        else:
            issues.append(
                Issue(
                    detector="garble_llm_repair",
                    severity="flag",
                    field=field_label,
                    snippet=text[:60],
                    detail=(
                        f"semantic LLM repair attempted but {post_flags} garble flag(s) "
                        f"remain — original text kept."
                    ),
                )
            )
    except Exception as e:
        from core.summarisation.postchecks.shared import logger

        logger.warning("garble LLM repair crashed (non-fatal): %s: %s", type(e).__name__, e)
        issues.append(
            Issue(
                detector="garble_llm_repair",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"semantic LLM repair failed: {type(e).__name__}: {e} — original kept.",
            )
        )
    return text, issues
