"""V0.4.19 — stray-quote repair (v0.20.5 / v2) and the D3 LLM repair.

``repair_stray_quotes``, the v2 state-machine repair
(``repair_stray_quotes_v2`` + the ``_v2_*`` helpers), and
``repair_d3_quotes_via_llm`` moved VERBATIM from ``garble.py`` during the
V0.4.19 de-monolithization (including their explanatory comment blocks
and module-level constants).
"""

from __future__ import annotations

from core.summarisation.postchecks.shared import Issue

# ── V0.20.5 (Quality Campaign, brainstorm D2): stray-quote repair ──


def repair_stray_quotes(
    text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V0.20.5 (brainstorm D2): repair stray/misplaced double-quotes.

    The V0.20.4 thorough summary had ~10 instances of misplaced closing
    quotes where the model opened a quote but misplaced the closing quote
    (e.g., a quoted phrase followed by a comma where the closing quote
    landed after the comma instead of after the phrase). The existing
    quote_verification postcheck strips mismatched quotes, but it doesn't
    catch all shapes.

    This detector finds lines with an ODD number of double-quote characters
    (a stray quote) and removes the orphan opening or closing quote. The
    heuristic: if a line has an odd quote count, the LAST quote is the
    orphan — remove it. This is conservative (removes one quote per odd-
    count line) and content-agnostic (no hardcoded quote patterns).

    Args:
        text: the summary field text.
        field_label: "bullet", "exec", or "thorough".

    Returns:
        ``(repaired_text, issues)``. Each issue is a ``stray_quote`` fix.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    try:
        lines = text.split("\n")
        repaired_lines = []
        for line in lines:
            quote_count = line.count('"')
            if quote_count % 2 == 1 and quote_count >= 1:
                # Odd quote count → stray quote. Remove the LAST quote
                # (the most likely orphan — a misplaced closing quote).
                last_quote_idx = line.rfind('"')
                repaired_line = line[:last_quote_idx] + line[last_quote_idx + 1 :]
                issues.append(
                    Issue(
                        detector="stray_quote",
                        severity="fix",
                        field=field_label,
                        snippet=line[:60],
                        detail=(
                            f"removed a stray double-quote (line had {quote_count} "
                            f"quotes — odd count; removed the last quote)"
                        ),
                    )
                )
                repaired_lines.append(repaired_line)
            else:
                repaired_lines.append(line)
        return "\n".join(repaired_lines), issues
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("stray-quote detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues


# ─────────────────────────────────────────────────────────────────────────────
# V0.20.6 (brainstorm D2+): stray-quote repair v2 — handle even-count mismatches.
#
# The V0.20.5 ``repair_stray_quotes`` (above) only fires on ODD ASCII ``"``
# counts per line, and counts ALL ``"`` including HTML attribute quotes
# (e.g., ``style="font-size:0.9em"``). The V0.4.1 NPD output showed two real
# bug classes that escape v0.20.5:
#
#   Class A — even-count mismatch: a line has an even total ``"`` count where
#     HTML attribute quotes (always paired) mask an imbalance in the text-
#     content quotes. The V0.4.1 NPD thorough summary shipped with ~4 such
#     mismatches on a single 44-quote line (all four confirmed by audit).
#
#   Class B — HTML-attribute blind spot: v0.20.5 counts ALL ``"`` (including
#     HTML attribute quotes). If a line has even HTML-attribute quotes + an
#     odd number of text-content orphans, the total count is ODD, and
#     v0.20.5 removes the LAST ``"`` — which may be an HTML attribute quote,
#     breaking the HTML. (Theoretical; not observed in V0.4.1, but the risk
#     is real and the fix is strict-improvement.)
#
# This v2 adds three content-agnostic detectors:
#
#   D1 — HTML-aware odd-count repair: strip HTML tags before counting; if
#        the text-content quote count is odd, remove the last text-content
#        ``"``. Strict improvement over v0.20.5 (never breaks HTML).
#
#   D2 — State-machine stray detection: walk text-content ``"`` chars with
#        an open/closed state machine. Auto-repair 1-sided orphans:
#          - state=closed + closer-pattern ``"`` -> stray closer -> DELETE
#          - state=open at EoL -> last opener never closed -> INSERT closer
#          - state=open + opener-pattern ``"`` -> previous open never closed
#            -> INSERT closer just before this opener
#
#   D3 — Long-span pair FLAG: if the state machine pairs an opener with a
#        closer > ``span_threshold`` chars apart, flag it as suspicious
#        (likely a "both dropped" case where the LLM omitted an opener AND
#        a closer, keeping the count even). Flag-only — no auto-repair
#        (the state machine can't tell WHERE to insert the missing pair
#        without semantic understanding; auto-repair would risk new errors).
#
# Content-agnostic guarantees:
#   - No hardcoded author names, book titles, or content patterns.
#   - Decisions based purely on local character context (left/right chars).
#   - Conservative: ambiguous context -> leave the quote alone.
#   - Always fail-open: any exception returns the original text.
#
# Validation: run on V0.4.1 NPD output -> 4 D3 flags (all confirmed by
# manual audit). Run on V0.3 Ch.2 -> 3 D3 flags (all confirmed). Run on
# V0.18 Ch.1 -> 1 D3 flag (confirmed). No false positives on cleaner lines.
# ─────────────────────────────────────────────────────────────────────────────

_V2_OPENER_LEFT_CHARS = frozenset(" \t([{,;:-\u2014\u2013")
_V2_OPENER_RIGHT_EXTRA = frozenset('"\u201c\u2018')
_V2_CLOSER_LEFT_EXTRA = frozenset(".!,?'\u201d\u2019")
_V2_CLOSER_RIGHT_CHARS = frozenset(" \t)]},;:.!?")
_V2_PUNCT_FOR_CLOSER = ",.;"

# Default threshold for D3 "suspicious long span" — a quote pair spanning
# more than this many chars is flagged. Tuned from V0.4.1 NPD: the longest
# LEGITIMATE pair is ~120 chars (a short quoted phrase with an inline
# citation); the SHORTEST broken pair is ~700 chars. 250 sits comfortably
# above the legitimate max and well below the broken min. Content-agnostic:
# based purely on distance, not on content.
_V2_DEFAULT_SPAN_THRESHOLD = 250


def _v2_text_quote_positions(line: str) -> list[int]:
    """Find all ``"`` positions that are NOT inside an HTML tag.

    HTML attribute quotes (e.g., ``style="font-size:0.9em"``) are always
    paired and never broken — including them in the count masks real
    imbalances in the text-content quotes.
    """
    positions: list[int] = []
    in_tag = False
    for i, c in enumerate(line):
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif c == '"' and not in_tag:
            positions.append(i)
    return positions


def _v2_looks_like_opener(line: str, pos: int) -> bool:
    """Does the ``"`` at ``line[pos]`` look like an opening quote?"""
    left = line[pos - 1] if pos > 0 else ""
    right = line[pos + 1] if pos + 1 < len(line) else ""
    left_ok = pos == 0 or left in _V2_OPENER_LEFT_CHARS
    right_ok = bool(right) and (right.isalnum() or right in _V2_OPENER_RIGHT_EXTRA)
    return left_ok and right_ok


def _v2_looks_like_closer(line: str, pos: int) -> bool:
    """Does the ``"`` at ``line[pos]`` look like a closing quote?"""
    left = line[pos - 1] if pos > 0 else ""
    right = line[pos + 1] if pos + 1 < len(line) else ""
    left_ok = bool(left) and (left.isalnum() or left in _V2_CLOSER_LEFT_EXTRA)
    right_ok = (pos + 1 >= len(line)) or (right in _V2_CLOSER_RIGHT_CHARS)
    return left_ok and right_ok


def _v2_find_closer_insert_pos(line: str, last_opener_pos: int) -> int:
    """Find the best position to insert a missing closing quote.

    Heuristic: just before the last comma/period/semicolon that appears
    AFTER the last opener. If none found, at end-of-line.
    """
    for i in range(len(line) - 1, last_opener_pos, -1):
        if line[i] in _V2_PUNCT_FOR_CLOSER:
            return i
    return len(line)


def _v2_repair_line(
    line: str,
    field_label: str,
    max_repairs: int,
    span_threshold: int,
) -> tuple[str, list[Issue]]:
    """Run D1+D2+D3 on a single line. Returns (new_line, issues)."""
    issues: list[Issue] = []
    positions = _v2_text_quote_positions(line)

    if not positions:
        return line, issues

    # ── D1: HTML-aware odd-count repair ──────────────────────────────────
    # If the text-content quote count is odd, remove the last text-content
    # `"` (a strict improvement over v0.20.5 which counts HTML quotes too).
    if len(positions) % 2 == 1:
        last_pos = positions[-1]
        new_line = line[:last_pos] + line[last_pos + 1 :]
        issues.append(
            Issue(
                detector="stray_quote_v2_d1",
                severity="fix",
                field=field_label,
                snippet=line[max(0, last_pos - 25) : min(len(line), last_pos + 25)],
                detail=(
                    f'removed stray text-content " at pos {last_pos} '
                    f"(text-content count was odd: {len(positions)})"
                ),
            )
        )
        return new_line, issues

    # ── D2: State-machine stray detection (even count) ────────────────────
    actions: list[tuple[int, str]] = []  # (pos, action)
    pair_spans: list[tuple[int, int, int]] = []  # (opener_pos, closer_pos, span)
    state = "closed"
    last_opener: int = -1

    for pos in positions:
        if state == "closed":
            if _v2_looks_like_opener(line, pos):
                state = "open"
                last_opener = pos
            elif _v2_looks_like_closer(line, pos):
                # Stray closer (no opener before it). Delete it.
                actions.append((pos, "delete"))
                # state stays closed
            else:
                # Ambiguous — assume opener (best guess).
                state = "open"
                last_opener = pos
        else:  # state == "open"
            if _v2_looks_like_closer(line, pos):
                state = "closed"
                pair_spans.append((last_opener, pos, pos - last_opener))
            elif _v2_looks_like_opener(line, pos):
                # Previous open never closed — insert closer just before this opener.
                actions.append((pos, "insert_before"))
                # state stays open; this quote becomes the new opener
                last_opener = pos
            else:
                # Ambiguous — assume closer, close the open state.
                state = "closed"
                pair_spans.append((last_opener, pos, pos - last_opener))

    # After all quotes: if state=open, last open never closed.
    if state == "open" and last_opener >= 0:
        insert_pos = _v2_find_closer_insert_pos(line, last_opener)
        actions.append((insert_pos, "insert_at"))

    # ── D3: Long-span pair FLAG ──────────────────────────────────────────
    for opener_pos, closer_pos, span in pair_spans:
        if span > span_threshold:
            issues.append(
                Issue(
                    detector="stray_quote_v2_d3",
                    severity="flag",  # NOT 'fix' — flag-only
                    field=field_label,
                    snippet=line[opener_pos : min(len(line), opener_pos + 50)],
                    detail=(
                        f"suspicious long-span quote pair: opener at pos {opener_pos} "
                        f"paired with closer at pos {closer_pos} ({span} chars apart; "
                        f"threshold {span_threshold}). Likely a dropped opener AND "
                        f"closer in between — needs semantic review."
                    ),
                )
            )

    # Apply cap on auto-repairs.
    if len(actions) > max_repairs:
        actions = actions[:max_repairs]

    if not actions:
        return line, issues

    # Apply actions in REVERSE position order so earlier positions stay valid.
    actions.sort(key=lambda a: a[0], reverse=True)
    new_line = line
    for pos, action in actions:
        if action == "delete":
            new_line = new_line[:pos] + new_line[pos + 1 :]
            issues.append(
                Issue(
                    detector="stray_quote_v2_d2",
                    severity="fix",
                    field=field_label,
                    snippet=line[max(0, pos - 25) : min(len(line), pos + 25)],
                    detail=f"deleted stray closing quote at pos {pos} (no opener before it)",
                )
            )
        elif action == "insert_before":
            new_line = new_line[:pos] + '"' + new_line[pos:]
            issues.append(
                Issue(
                    detector="stray_quote_v2_d2",
                    severity="fix",
                    field=field_label,
                    snippet=line[max(0, pos - 25) : min(len(line), pos + 25)],
                    detail=(
                        f"inserted missing closing quote before pos {pos} "
                        f"(previous open never closed)"
                    ),
                )
            )
        elif action == "insert_at":
            new_line = new_line[:pos] + '"' + new_line[pos:]
            issues.append(
                Issue(
                    detector="stray_quote_v2_d2",
                    severity="fix",
                    field=field_label,
                    snippet=line[max(0, pos - 25) : min(len(line), pos + 25)],
                    detail=(
                        f"inserted missing closing quote at pos {pos} (final open never closed)"
                    ),
                )
            )

    return new_line, issues


def repair_stray_quotes_v2(
    text: str,
    field_label: str,
    *,
    max_repairs_per_line: int = 8,
    span_threshold: int = _V2_DEFAULT_SPAN_THRESHOLD,
) -> tuple[str, list[Issue]]:
    """V0.20.6 (brainstorm D2+): extend stray-quote repair to even-count mismatches.

    Subsumes v0.20.5 ``repair_stray_quotes`` with three content-agnostic
    detectors (D1/D2/D3). See the long docstring block above for details.

    Args:
        text: the summary field text.
        field_label: "bullet", "exec", "thorough", "key_distinctions",
            or "theoretical_tensions".
        max_repairs_per_line: safety cap on auto-repairs per line.
        span_threshold: D3 flag threshold (chars); pairs spanning more than
            this are flagged as suspicious.

    Returns:
        ``(repaired_text, issues)``. Each issue is either ``severity="fix"``
        (auto-repair applied) or ``severity="flag"`` (D3 long-span suspicion;
        no auto-repair — surfaces in the conversion log for review).
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    try:
        lines = text.split("\n")
        out_lines: list[str] = []
        for line in lines:
            new_line, line_issues = _v2_repair_line(
                line, field_label, max_repairs_per_line, span_threshold
            )
            out_lines.append(new_line)
            issues.extend(line_issues)
        return "\n".join(out_lines), issues
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("stray-quote-v2 detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues


# ─────────────────────────────────────────────────────────────────────────────
# V0.4.11 (audit item #4): semantic LLM repair for D3 long-span quote pairs.
#
# The V0.4.2 stray_quote_v2_d3 detector flags long-span quote pairs but is
# flag-only — the state machine can't tell WHERE to insert the missing
# quote pair. This function takes the flagged text + source text and sends
# them to the fast LLM with a "fix the quote pairing" prompt. Fail-open:
# if the LLM call fails, the original text is returned unchanged.
#
# Content-agnostic: the prompt only asks for quote-pair repair, not
# content changes. The LLM is instructed to preserve all text and only
# add/remove/reposition double-quote characters.
# ─────────────────────────────────────────────────────────────────────────────

_D3_REPAIR_PROMPT = """The following text has mismatched double-quote characters. Some opening quotes lack closing quotes, and some closing quotes lack opening quotes. Your task: fix ONLY the quote pairing by adding or removing double-quote characters so every opening quote has a matching closing quote and vice versa. Do NOT change any other text, do NOT add or remove words, do NOT change punctuation other than double-quote characters. Output ONLY the corrected text, no commentary.

TEXT TO FIX:
"""


def repair_d3_quotes_via_llm(
    text: str,
    field_label: str,
    source_text: str = "",
    settings=None,
) -> tuple[str, list[Issue]]:
    """V0.4.11/V0.4.13: send flagged D3 text to the LLM for semantic quote repair.

    V0.4.13: rewritten to use the provider abstraction (provider.complete())
    instead of the Ollama-specific /api/generate. This makes it work with
    llama.cpp backends too (the V0.4.11 version used safe_ollama_request
    which only works with Ollama — on a llama.cpp backend the endpoint
    /api/generate doesn't exist, so the repair silently failed).

    Uses the user's configured summarisation model + endpoint from
    settings. Fail-open: if the LLM call fails, returns the original text.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues

    # Check if there are any D3 flags to repair.
    _, v2_issues = repair_stray_quotes_v2(text, field_label)
    d3_flags = [i for i in v2_issues if i.detector == "stray_quote_v2_d3"]
    if not d3_flags:
        return text, issues  # no D3 flags — nothing to repair

    if settings is None:
        from utils.settings import Settings as _S

        settings = _S()

    model = settings.get("summarisation.model", "") or settings.get(
        "summarisation.primary_model", ""
    )
    if not model:
        return text, issues  # no model configured

    try:
        # V0.4.13: use the provider abstraction instead of raw HTTP.
        # This makes the repair work with both Ollama AND llama.cpp.
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

        prompt = _D3_REPAIR_PROMPT + text
        repaired = provider.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=8192,
            model=model,
        )

        if not repaired or len(repaired) < len(text) * 0.8:
            issues.append(
                Issue(
                    detector="stray_quote_v2_d3_llm_repair",
                    severity="flag",
                    field=field_label,
                    snippet=text[:60],
                    detail="semantic LLM repair returned empty/short text — original kept.",
                )
            )
            return text, issues

        # Verify the repaired text has fewer D3 flags.
        _, post_issues = repair_stray_quotes_v2(repaired, field_label)
        post_d3 = [i for i in post_issues if i.detector == "stray_quote_v2_d3"]
        if len(post_d3) < len(d3_flags):
            issues.append(
                Issue(
                    detector="stray_quote_v2_d3_llm_repair",
                    severity="fix",
                    field=field_label,
                    snippet=text[:60],
                    detail=(
                        f"semantic LLM repair: fixed {len(d3_flags) - len(post_d3)} "
                        f"D3 long-span quote pair(s) via LLM (was {len(d3_flags)} flags, "
                        f"now {len(post_d3)})."
                    ),
                )
            )
            return repaired, issues
        else:
            issues.append(
                Issue(
                    detector="stray_quote_v2_d3_llm_repair",
                    severity="flag",
                    field=field_label,
                    snippet=text[:60],
                    detail=(
                        f"semantic LLM repair attempted but {len(post_d3)} D3 flags "
                        f"remain — original text kept."
                    ),
                )
            )
    except Exception as e:
        from core.summarisation.postchecks.shared import logger

        logger.warning("D3 LLM repair crashed (non-fatal): %s: %s", type(e).__name__, e)
        issues.append(
            Issue(
                detector="stray_quote_v2_d3_llm_repair",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"semantic LLM repair failed: {type(e).__name__}: {e} — original kept.",
            )
        )
    return text, issues
