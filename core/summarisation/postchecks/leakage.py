"""V0.18 (Phase 5.2) — prompt-leakage / chain-of-thought narrative detectors.

Moved VERBATIM (byte-identical bodies) from ``postcheck_detectors.py``
during the Phase 5.2 regroup into the ``postchecks/`` package.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    _snippet,
)

_PROMPT_LEAKAGE_PATTERNS: tuple[str, ...] = (
    # Direct echoes of the prompt template
    r"provided\s+in\s+the\s+(?:input|source|text|chapter|passage)\b",
    r"as\s+(?:mentioned|noted|stated|described|discussed)\s+in\s+the\s+(?:source|input|text|passage|chapter)\b",
    r"based\s+on\s+the\s+source\s+(?:text|material|content)\b",
    r"according\s+to\s+the\s+(?:source|input|text|passage)\b",
    # First-person process leaks
    r"\bI\s+(?:need\s+to|must|should|will|am\s+going\s+to|can|cannot|don't\s+have)\b",
    r"\bI'll\b",
    # V18.15.7.0 (Fix 1): extended the "Let me" alternation with the verbs the
    # V18.15.6.0 golden-master actually produced ("Let me organize my
    # understanding", "Let me count carefully", "Let me draft each section
    # now", "Wait, let me re-read", "Let me be very careful", "Let me list
    # them"). Pre-V18.15.7.0 these bypassed detection — the thorough_summary
    # was 100% chain-of-thought narrative.
    r"\bLet\s+me\s+(?:go|work|carefully|identify|extract|now|think|consider|check|analyze|summarize|organize|count|draft|re-?read|be\s+very\s+careful|list|write|note|see|ensure|make\s+sure|count\s+carefully)\b",
    r"\bWait,?\s+let\s+me\b",
    # V18.15.7.0 (Fix 1): the model's structural-reasoning phrases that leak
    # into thorough_summary as bullet-preparation narrative.
    r"\bNamed contributors in order\b",
    r"\bwrite the five sections\b",
    r"\bBullet points\s*\(\s*\d+-\d+\s*\)\s*:",
    r"\bExecutive Summary\s*\(\s*\d+-\d+\s*words?\s*\)\s*:",
    r"\bI need \d+-\d+ distinct key takeaways\b",
    r"\bLet me count\b",
    r"\bLet me draft\b",
    r"\bLet me list them\b",
    r"\bLet me be very careful\b",
    # V18.15.7.0 (Fix 1): prompt-instruction echoes (the V18.15.6.0 run shipped
    # these as standalone bullets in the Key Takeaways).
    r"^Keep sentences under \d+ words\b",
    r"^Preserve (?:technical|all)\s+(?:terms|citations)\b",
    r"^Use active voice\b",
    r"^Sentences under \d+ words\b",
    r"\bCover all named contributors\b",
    r"\bInclude the full progression\b",
    r"\bEnd with the conclusion'?s enumerated list\b",
    r"\bThis is a tension\b",
    r"\bThis is the (?:reading|reading level) requirement\b",
    r"\bmaking sure to:\s*$",
    r"\bwhile also maintaining academic precision\b",
    r"\bgo through the source material\b",
    # V18.20.3.9 (Phase 2 / A3 — residuals sweep): was the book-keyed literal
    # "what appears to be a domain text" (harvested from a run on a
    # analysis book). Generalized to the structural class: the model
    # speculating about the SOURCE's genre is CoT self-commentary regardless
    # of the domain — "a historical text", "a technical manual"… all match.
    r"\bwhat (?:appears|seems) to be (?:a|an) [a-z\-]+ (?:text|book|work|chapter|document|study|manual)\b",
    r"\bextract all key concepts, arguments, frameworks\b",
    r"\bLet me organize my understanding\b",
    r"\bwait,? let me re-?read\b",
    r"\bnow write\b",
    r"\bNow\s+I\s+(?:will|shall|can|need)\b",
    # Self-reference / refusals
    r"\bas\s+an\s+AI\b",
    r"\bas\s+a\s+language\s+model\b",
    r"\bI'm\s+(?:not\s+)?(?:able|sure)\s+to\b",
    # Template scaffolding that survives parsing
    r"\bhere\s+is\s+the\s+(?:summary|bullet|list|chapter)\b",
    r"\bhere\s+are\s+the\s+(?:bullets|key\s+points|takeaways)\b",
    r"\bthe\s+user\s+(?:wants|asked|requested|specifically)\b",
    r"\bthe\s+instructions?\s+(?:say|state|ask|require)\b",
)

_PROMPT_LEAKAGE_RE = [re.compile(p, re.IGNORECASE) for p in _PROMPT_LEAKAGE_PATTERNS]


def detect_prompt_leakage(text: str, field_label: str) -> tuple[str, list[Issue]]:
    """Strip prompt-leakage phrases from ``text``.

    Removes the model's CoT/process phrases that leak past
    :func:`response_parser.strip_reasoning_leaks`. Also removes a stray
    leading ``"("`` when the leakage phrase it opened (``"( provided in the
    input"``) is gone — the V18.2.12 garbled token was literally
    ``"( provided in the input"`` with an unmatched paren.

    Each removed phrase is recorded as an Issue with severity ``"fix"``.

    Args:
        text: the summary text to clean.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(cleaned_text, issues)``.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    cleaned = text
    try:
        for pat in _PROMPT_LEAKAGE_RE:
            for m in list(pat.finditer(cleaned)):
                snippet = _snippet(cleaned, m.start())
                issues.append(
                    Issue(
                        detector="prompt",
                        severity="fix",
                        field=field_label,
                        snippet=snippet,
                        detail=f"stripped prompt-leakage: '{m.group(0)[:40]}'",
                    )
                )
            cleaned = pat.sub("", cleaned)
        # Collapse the double-spaces the substitutions leave behind.
        cleaned = re.sub(r"  +", " ", cleaned)
        # Remove a stray leading "(" that now opens nothing — the classic
        # V18.2.12 artifact was "( provided in the input" and after removing
        # the phrase, "(" lingers at the start of a bullet/sentence.
        cleaned = re.sub(r"(?m)^\s*\(\s+", "", cleaned)
        cleaned = re.sub(r"\s+\)\s*([.;,])", r"\1", cleaned)  # dangling ")"
        # Strip a leading ", " left behind when a leakage phrase opened a
        # clause (e.g., "( provided in the input, the author notes..." ->
        # after stripping the leakage + leading "(" we get ", the author notes";
        # clean up the orphaned comma so the bullet starts cleanly).
        cleaned = re.sub(r"(?m)^\s*,\s+", "", cleaned)
        # Collapse newlines that the removals may have orphaned.
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned).strip()
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="prompt",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"prompt-leakage check crashed: {e!r}",
            )
        )
        return text, issues
    return cleaned, issues


_COT_NARRATIVE_MARKERS: tuple[str, ...] = (
    r"\bLet me (?:organize|count|draft|list|write|be very careful)\b",
    r"\bNamed contributors in order\b",
    r"\bwrite the five sections\b",
    r"\bBullet points\s*\(\s*\d+-\d+\s*\)\s*:",
    r"\bExecutive Summary\s*\(\s*\d+-\d+\s*words?\s*\)\s*:",
    r"\bI need \d+-\d+ distinct key takeaways\b",
    r"\bWait,? let me re-?read\b",
    r"\bLet me organize my understanding\b",
    r"\bwhat (?:appears|seems) to be (?:a|an) [a-z\-]+ (?:text|book|work|chapter|document|study|manual)\b",  # V18.20.3.9: book-keyed literal generalized (see the leak-pattern twin above)
    r"\bgo through the source material\b",
    r"\bextract all key concepts, arguments, frameworks\b",
    r"\bmaking sure to:\s*$",
    r"\bwhile also maintaining academic precision\b",
    r"\bThis is a tension\b",
    r"\bnow write\b",
    r"\bLet me count carefully\b",
    r"\bLet me draft each section\b",
    r"\bLet me list them\b",
    # V18.16.0.1 (Fix 1): exec-from-thorough CoT markers. The V18.16.0.0
    # regression: the exec-from-thorough call produced CoT that started with
    # "me to write a 150-250 word executive summary... synthesize the key
    # points... Draft: This chapter...". These are the model echoing the
    # PROMPT INSTRUCTIONS back as its output, NOT a summary.
    r"\bme to write\b",
    r"\bsynthesize the key\b",
    r"\bKey elements to capture\b",
    r"\bthis in flowing prose\b",
    r"\bcarefully\.\s*Draft\b",
    r"^\s*Draft:\s",
    r"\bsynthesize.*thorough summary\b",
)

_COT_NARRATIVE_RE = [re.compile(p, re.IGNORECASE) for p in _COT_NARRATIVE_MARKERS]


def detect_cot_narrative(text: str, field_label: str) -> tuple[str, list[Issue]]:
    """V18.15.7.0 (Fix 1): Detect if the thorough_summary is the model's
    chain-of-thought narrative (NOT a summary).

    The V18.15.6.0 golden-master produced a thorough_summary that was 100% CoT
    ("Let me organize my understanding...", "Named contributors in order:",
    "Let me count carefully.", "Let me draft each section now."). The
    ``detect_prompt_leakage`` detector strips individual phrases but leaves
    the surrounding CoT scaffolding, producing a fragmented mess.

    This detector counts structural CoT markers. If >= 3 are present, the
    text is overwhelmingly CoT narrative → truncate to empty + flag. The
    caller (``summarizer._summarize_inner`` line ~3077) then falls back to
    ``exec_sum`` for the thorough_summary field.

    Threshold rationale: a legitimate summary might accidentally contain 1
    CoT-like phrase (e.g., "Let me elaborate on..."). 3+ markers is a strong
    signal the entire field is CoT.

    Args:
        text: the thorough_summary text to check.
        field_label: typically "thorough".

    Returns:
        ``(cleaned_text, issues)``. If CoT is detected, ``cleaned_text`` is
        empty (caller falls back); otherwise it's the original text unchanged.
    """
    issues: list[Issue] = []
    if not text or len(text) < 50:
        return text, issues
    try:
        marker_count = sum(1 for pat in _COT_NARRATIVE_RE if pat.search(text))
        if marker_count >= 3:
            issues.append(
                Issue(
                    detector="cot_narrative",
                    severity="flag",
                    field=field_label,
                    snippet=text[:80],
                    detail=(
                        f"thorough_summary is chain-of-thought narrative "
                        f"({marker_count} CoT markers detected — truncating to "
                        f"empty; caller falls back to exec_sum). The V18.15.6.0 "
                        f"golden-master regression was caused by this: the "
                        f"thorough_summary was 100% model reasoning, not a summary."
                    ),
                )
            )
            return "", issues
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="cot_narrative",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"CoT-narrative check crashed: {e!r}",
            )
        )
    return text, issues
