"""V10.15.0 (B1): Response parser — extracted from Summarizer.

Handles parsing of LLM responses in all formats the model emits:
  - JSON (academic-rigor mode)
  - XML tags (<executive_summary>, <bullet_points>, <thorough_summary>)
  - Plain text with bullet markers (•, -, *)
  - <point>, <bullet>, <finding><claim> tags
  - Markdown headers (## Executive Summary, ## Key Takeaways)

Also handles text stripping:
  - <think>/<thinking> tags
  - XML markup tags (generic)
  - Plain-text reasoning leaks (gap-fill/self-review artifacts)
  - Page/line references (V10.12.9)
  - Narrative from thorough summaries

This module is stateless — all functions take input + return output, no
instance state.  The Summarizer delegates to these functions.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Compiled regex patterns ────────────────────────────────────────────────

_THINK_RE = re.compile(
    r'</?(?:think|thinking|thought|analysis|reasoning|'
    r'reflection|internal_monologue|scratchpad)\s*>',
    re.IGNORECASE | re.DOTALL,
)

_THINK_BLOCK_RE = re.compile(
    r'<(?:think|thinking|thought|analysis|reasoning|reflection)\b[^>]*>.*?</(?:think|thinking|thought|analysis|reasoning|reflection)\s*>',
    re.IGNORECASE | re.DOTALL,
)

_THINKING_PROCESS_RE = re.compile(
    r'(?i)thinking\s*process\s*:.*?(?=<executive_summary>|<bullet|<thorough|\\*\\*Executive|\\*\\*Key|##|\\n\\s*[-\\*]\\s)',
    re.DOTALL,
)

_MARKUP_TAG_RE = re.compile(
    r'</?(?:'
    r'finding|claim|snippet|source_ref|evidence_quote|'
    r'verdict|reason|index'
    r'|executive_summary|bullet_points|point|reference|'
    r'summary|response|output|result|'
    r'thought|thinking|analysis|reasoning|'
    r'key_point|key_takeaway|takeaway|'
    r'chapter|section|paragraph|sentence|'
    r'quote|quotation|citation|cite|'
    r'metadata|meta|tag|label|'
    r'json|xml|html|code|pre'
    r')\s*/?>',
    re.IGNORECASE,
)

_GENERIC_MARKUP_TAG_RE = re.compile(
    r'</?[a-z_][a-z_0-9]{0,29}\s*/?>',
    re.IGNORECASE,
)

_PAGE_REF_RE = re.compile(
    r'\s*[Pp]age\s+\d+,\s*[Ll]ines?\s+\d+[-\d]*\s*',
)

_PAGE_REF_END_RE = re.compile(r'\s*[Pp]age\s+\d+\s*$')

_REASONING_PATTERNS = [
    r'(?:This is a|These are) (?:missed|missing) concept[s]? because[^.]*\.',
    r'this suggests[^.]*\.',
    r'[Tt]his (?:is also|refers to) (?:a |an )?(?:missed|missing) concept[^.]*\.',
    r'[Tt]he existing bullets (?:probably )?(?:don\'t|do not) cover[^.]*\.',
    r'I should focus on[^.]*\.',
    r'[Tt]he abstract (?:also )?mentions[^.]*\.',
    r'[Tt]he user specifically wants[^.]*\.',
    r'I\'ll check[^.]*\.',
    r'[Ss]ince I don\'t have[^.]*\.',
    r'I\'ll (?:prioritize|assume|include|add|focus)[^.]*\.',
    r'[Hh]owever, the (?:instruction|user) says[^.]*\.',
    r'[Tt]he (?:missed|missing) concepts (?:are|is)[^.]*\.',
    r'[Tt]his could be a missed concept[^.]*\.',
    r'I can still include[^.]*\.',
    r'I might (?:not )?(?:need|skip|include)[^.]*\.',
]


# ── Text stripping functions ───────────────────────────────────────────────

def strip_thinking(text: str) -> str:
    """Strip <think>/<thinking> blocks from text."""
    if not text:
        return text
    # Remove complete <think>...</think> blocks
    cleaned = _THINK_BLOCK_RE.sub('', text)
    # Remove orphaned <think> or </think> tags
    cleaned = _THINK_RE.sub('', cleaned)
    # Remove "thinking process:" prefixes
    cleaned = _THINKING_PROCESS_RE.sub('', cleaned)

    # V18.20.4.11 (P1 / T-a2): instrument the stripping — this module's
    # logger existed but was never used and every strip/fallback was
    # silent. Measured BEFORE the cosmetic final .strip() so whitespace-only
    # inputs don't false-alarm: only think-block/tag/CoT-cut removals count.
    _len_before = len(text)

    # V18.2.12: Strip plain-text CoT leakage before the first XML tag.
    # The model sometimes leaks reasoning as plain text before <executive_summary>.
    _first_tag = re.search(
        r'<(executive_summary|bullet_points|thorough_summary|key_distinctions|'
        r'theoretical_tensions|summary|chapter_summary)',
        cleaned, re.IGNORECASE
    )
    if _first_tag:
        _before = cleaned[:_first_tag.start()]
        _cot_patterns = [
            r'The user wants',
            r'Let me (go|work|carefully|identify|extract)',
            r'I need to',
            r'I must',
            r'\d+\.\s+[A-Z][a-z]+\s+\(\d{4}\)',
        ]
        _is_cot = any(re.search(p, _before, re.IGNORECASE) for p in _cot_patterns)
        if _is_cot and len(_before) > 50:
            cleaned = cleaned[_first_tag.start():]

    # V18.20.4.11 (P1 / T-a2): pathological removal → WARNING with counts.
    # >50% of a response consumed by think-blocks/CoT means the model
    # leaked reasoning past /no_think (or a cut response was mostly
    # reasoning). Two len() calls, no content logged (privacy + size).
    _len_after = len(cleaned)
    if _len_after * 2 < _len_before:
        logger.warning(
            "strip_thinking removed >50%% of text: %d -> %d chars "
            "(possible CoT/thinking leak past /no_think)",
            _len_before, _len_after,
        )

    return cleaned.strip()


def strip_markup_tags(text: str) -> str:
    """Strip XML/JSON markup tags + page/line references from text."""
    if not text:
        return text
    cleaned = _MARKUP_TAG_RE.sub('', text)
    cleaned = _GENERIC_MARKUP_TAG_RE.sub('', cleaned)
    # V10.12.9: Strip inline page/line references
    cleaned = _PAGE_REF_RE.sub(' ', cleaned)
    cleaned = _PAGE_REF_END_RE.sub('', cleaned)
    # Clean up whitespace
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    return cleaned.strip()


def strip_reasoning_leaks(text: str) -> str:
    """Strip plain-text reasoning that leaks from gap-fill + self-review."""
    if not text:
        return text
    for pattern in _REASONING_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def strip_narrative_from_thorough(text: str) -> str:
    """Strip narrative/story sentences from the thorough summary.

    For non-fiction books, the thorough summary should explain concepts
    and arguments, not retell the story. This method detects and removes
    sentences that are purely narrative.
    """
    if not text or len(text) < 100:
        return text

    # Narrative patterns — sentences describing what someone DID
    NARRATIVE_SENTENCE = re.compile(
        r'(?:^|\.\s+)([A-Z][a-z]+\s+(?:went|goes|arrives|arrived|meets|met|'
        r'tells|told|says|said|decides|decided|begins|began|walks|walked|'
        r'runs|ran|drives|drove|calls|called|visits|visited|finds|found|'
        r'moves|moved|returns|returned|leaves|left|joins|joined|leaves))',
        re.IGNORECASE,
    )

    sentences = re.split(r'(?<=[.!?])\s+', text)
    kept = []
    for sent in sentences:
        if not NARRATIVE_SENTENCE.search(sent):
            kept.append(sent)

    result = ' '.join(kept).strip()
    return result if result else text


# ── Bullet extraction helpers ─────────────────────────────────────────────

def extract_bullets_from_text(text: str) -> list[str]:
    """Extract bullets from plain text using • / - / * / numbered markers."""
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r'^[\-\*•·▸]\s+', line) or re.match(r'^\d+[\.\)]\s+', line):
            line = re.sub(r'^[\-\*•·▸]\s+', '', line)
            line = re.sub(r'^\d+[\.\)]\s+', '', line)
            if line and len(line) > 5:
                bullets.append(line)
    return bullets


def extract_bullets_from_block(block: str) -> list[str]:
    """Extract bullets from a <bullet_points> block.

    Handles <point>, <bullet>, <finding><claim> tags + bullet markers.
    """
    # Try <point> tags
    point_matches = re.findall(r'<point>\s*(.*?)\s*</point>', block, re.DOTALL | re.IGNORECASE)
    if point_matches:
        return [p.strip() for p in point_matches if p.strip() and len(p.strip()) > 5]

    # Try <bullet> tags
    bullet_matches = re.findall(r'<bullet>\s*(.*?)\s*</bullet>', block, re.DOTALL | re.IGNORECASE)
    if bullet_matches:
        return [b.strip() for b in bullet_matches if b.strip() and len(b.strip()) > 5]

    # Try <finding><claim> tags
    claim_matches = re.findall(r'<claim>\s*(.*?)\s*</claim>', block, re.DOTALL | re.IGNORECASE)
    if claim_matches:
        return [c.strip() for c in claim_matches if c.strip() and len(c.strip()) > 5]

    # Fall back to line-by-line with bullet markers
    return extract_bullets_from_text(block)


# ── Response parser ────────────────────────────────────────────────────────

def parse_response(raw: str, academic_rigor: bool = False) -> dict[str, Any]:
    """Parse an LLM response into {executive_summary, bullet_points, thorough_summary}.

    Tries JSON first (academic-rigor mode), then falls through to the
    universal XML/tag parser.
    """
    # Strip thinking + reasoning from the raw response
    cleaned = strip_thinking(raw)
    cleaned = strip_reasoning_leaks(cleaned)

    # Try JSON first (academic rigor OR if the response looks like JSON)
    # V13.34.1: Also try JSON when the response starts with { even if academic_rigor is False.
    # The model sometimes returns JSON format even in non-academic mode.
    looks_like_json = cleaned.strip().startswith('{') or '```json' in cleaned[:20].lower()
    if academic_rigor or looks_like_json:
        # V13.34.1: Strip markdown code fences before parsing
        json_text = cleaned
        json_text = re.sub(r'^```json\s*\n?', '', json_text, flags=re.IGNORECASE)
        json_text = re.sub(r'^```\s*\n?', '', json_text)
        json_text = re.sub(r'\n?```\s*$', '', json_text)
        json_text = json_text.strip()
        # Try to find the first complete JSON object
        json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', json_text, re.DOTALL)
        if not json_match:
            # Fallback: try the greedy match
            json_match = re.search(r'(\{.*\})', json_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                for key in ["executive_summary", "bullet_points", "thorough_summary"]:
                    if key not in data:
                        data[key] = []

                def _extract_claims(items):
                    result = []
                    for item in items:
                        if isinstance(item, dict):
                            claim = item.get("claim", "") or item.get("text", "") or item.get("bullet", "")
                            if claim:
                                result.append(str(claim))
                        elif isinstance(item, str):
                            if item.strip():
                                result.append(item.strip())
                    return result

                exec_items = data.get("executive_summary", [])
                bullet_items = data.get("bullet_points", [])
                thorough_items = data.get("thorough_summary", [])
                exec_summary = "\n".join(_extract_claims(exec_items)) if isinstance(exec_items, list) else str(exec_items)
                bullet_points = _extract_claims(bullet_items) if isinstance(bullet_items, list) else []
                thorough = "\n".join(_extract_claims(thorough_items)) if isinstance(thorough_items, list) else str(thorough_items)

                # V13.38.0: Extract new additive sections (key_distinctions, theoretical_tensions)
                key_distinctions = ""
                tensions = ""
                kd_items = data.get("key_distinctions", [])
                tt_items = data.get("theoretical_tensions", [])
                if isinstance(kd_items, list):
                    key_distinctions = "\n".join(_extract_claims(kd_items))
                elif isinstance(kd_items, str):
                    key_distinctions = kd_items
                if isinstance(tt_items, list):
                    tensions = "\n".join(_extract_claims(tt_items))
                elif isinstance(tt_items, str):
                    tensions = tt_items

                if exec_summary.strip() or bullet_points or thorough.strip():
                    # Strip all artifacts from extracted content
                    # V18.20.4.11 (P1 / T-a2): routine trace of the winning
                    # path — counts only, content never logged above DEBUG.
                    logger.debug(
                        "parse_response: JSON path OK (%d bullets, exec %d "
                        "chars, thorough %d chars)",
                        len(bullet_points), len(exec_summary), len(thorough),
                    )
                    exec_summary = strip_thinking(exec_summary)
                    exec_summary = strip_markup_tags(exec_summary)
                    exec_summary = strip_reasoning_leaks(exec_summary)
                    bullet_points = [strip_thinking(bp) for bp in bullet_points]
                    bullet_points = [strip_markup_tags(bp) for bp in bullet_points]
                    bullet_points = [strip_reasoning_leaks(bp) for bp in bullet_points]
                    bullet_points = [bp for bp in bullet_points if bp and len(bp) > 3]
                    thorough = strip_thinking(thorough)
                    thorough = strip_markup_tags(thorough)
                    thorough = strip_reasoning_leaks(thorough)
                    thorough = strip_narrative_from_thorough(thorough)
                    key_distinctions = strip_thinking(key_distinctions)
                    key_distinctions = strip_markup_tags(key_distinctions)
                    key_distinctions = strip_reasoning_leaks(key_distinctions)
                    tensions = strip_thinking(tensions)
                    tensions = strip_markup_tags(tensions)
                    tensions = strip_reasoning_leaks(tensions)
                    return {
                        "executive_summary": exec_summary,
                        "bullet_points": bullet_points,
                        "thorough_summary": thorough,
                        "key_distinctions": key_distinctions,
                        "theoretical_tensions": tensions,
                    }
                # V18.20.4.11 (P1 / T-a2): JSON parsed but every core field
                # empty → the universal parser gets a chance. Routine-ish
                # (the model emitted JSON-shaped nothing) → DEBUG.
                logger.debug(
                    "parse_response: JSON parsed but all core fields empty "
                    "→ universal parser (%d chars)",
                    len(cleaned),
                )
            except json.JSONDecodeError as _jde:
                # V18.20.4.11 (P1 / T-a2): was a bare silent ``pass``. The
                # JSON → universal transition is a normal salvage (the
                # universal parser handles tagged/plain content), so DEBUG
                # with the reason + size; content head only at DEBUG, capped.
                logger.debug(
                    "parse_response: JSON decode failed (%s: %s) → universal "
                    "parser (%d chars, head=%r)",
                    type(_jde).__name__, _jde.msg, len(cleaned), cleaned[:80],
                )
        else:
            # V18.20.4.11 (P1 / T-a2): looked like JSON but no JSON object
            # found at all → universal parser. DEBUG (routine salvage).
            logger.debug(
                "parse_response: no JSON object found in %d-char response → "
                "universal parser",
                len(cleaned),
            )

    # Universal parser
    # V18.20.4.11 (P1 / T-a2): the ROUTINE path for most models (tagged or
    # plain text — the structured/JSON route is disabled by default since
    # V18.15.3) — one DEBUG line naming the transition + input size.
    if not (academic_rigor or looks_like_json):
        logger.debug(
            "parse_response: non-JSON response (%d chars) → universal parser",
            len(cleaned),
        )
    return _parse_universal(cleaned)


def _parse_universal(cleaned: str) -> dict[str, Any]:
    """Universal parser — handles all model output formats."""
    exec_sum = ""
    bullets: list[str] = []
    thorough = ""
    # V18.20.4.11 (P1 / T-a2): which rung of the bullet ladder produced the
    # bullets — used for the one-line DEBUG trace at the end (routine), so
    # parser debugging no longer requires guessing the path.
    _bp_src = "none"

    # Step A: Extract executive_summary
    em = re.search(
        r'<executive_summary>\s*(.*?)(?:</executive_summary>|<bullet_points>|<thorough_summary>|<key_takeaways>|<key_points>|$)',
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if em:
        exec_sum = em.group(1).strip()

    # Step B: Extract bullet_points block
    bm = re.search(
        r'<bullet_points>\s*(.*?)(?:</bullet_points>|<thorough_summary>|<key_takeaways>|$)',
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if bm:
        bullets_block = bm.group(1).strip()
        bullets = extract_bullets_from_block(bullets_block)
        if bullets:
            _bp_src = "<bullet_points> block"

    # Step C: Try <point>/<bullet>/<finding> tags
    if not bullets:
        point_matches = re.findall(r'<point>\s*(.*?)\s*</point>', cleaned, re.DOTALL | re.IGNORECASE)
        if point_matches:
            bullets = [p.strip() for p in point_matches if p.strip() and len(p.strip()) > 5]
            if bullets:
                _bp_src = "<point> tags"

    if not bullets:
        bullet_matches = re.findall(r'<bullet>\s*(.*?)\s*</bullet>', cleaned, re.DOTALL | re.IGNORECASE)
        if bullet_matches:
            bullets = [b.strip() for b in bullet_matches if b.strip() and len(b.strip()) > 5]
            if bullets:
                _bp_src = "<bullet> tags"

    if not bullets:
        finding_matches = re.findall(
            r'<claim>\s*(.*?)\s*</claim>', cleaned, re.DOTALL | re.IGNORECASE,
        )
        if finding_matches:
            bullets = [c.strip() for c in finding_matches if c.strip() and len(c.strip()) > 5]
            if bullets:
                _bp_src = "<claim> tags"

    # Step D: Find • / - / * lines anywhere
    if not bullets:
        bullets = extract_bullets_from_text(cleaned)
        if bullets:
            _bp_src = "plain-text bullet markers"

    # Step E: Extract from exec_sum if no bullets found
    if not bullets and exec_sum:
        bullets = extract_bullets_from_text(exec_sum)
        if bullets:
            exec_sum = ""
            _bp_src = "exec_summary text"

    # Step F: Extract thorough_summary
    tm = re.search(
        r'<thorough_summary>\s*(.*?)(?:</thorough_summary>|$)',
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if tm:
        thorough = tm.group(1).strip()

    # If no thorough_summary tag, use whatever's left
    if not thorough:
        remaining = cleaned
        if em:
            remaining = remaining.replace(em.group(0), '', 1)
        if bm:
            remaining = remaining.replace(bm.group(0), '', 1)
        if tm:
            remaining = remaining.replace(tm.group(0), '', 1)
        remaining = re.sub(
            r'</?(?:summary|chapter_summary|response|output)\s*/?>',
            '', remaining, flags=re.IGNORECASE,
        )
        thorough = remaining.strip()

    # Step G: Strip all tags from extracted content
    exec_sum = strip_thinking(exec_sum)
    exec_sum = strip_markup_tags(exec_sum)
    exec_sum = strip_reasoning_leaks(exec_sum)
    bullets = [strip_thinking(bp) for bp in bullets]
    bullets = [strip_markup_tags(bp) for bp in bullets]
    bullets = [strip_reasoning_leaks(bp) for bp in bullets]
    bullets = [bp for bp in bullets if bp and len(bp) > 3]
    thorough = strip_thinking(thorough)
    thorough = strip_markup_tags(thorough)
    thorough = strip_reasoning_leaks(thorough)
    thorough = strip_narrative_from_thorough(thorough)

    # V13.38.0: Extract new additive sections
    key_distinctions = ""
    tensions = ""
    kdm = re.search(
        r'<key_distinctions>\s*(.*?)(?:</key_distinctions>|<theoretical_tensions>|$)',
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if kdm:
        key_distinctions = kdm.group(1).strip()
        # V18.20.3.1 (real-rig audit D1): the `$` fallback above fires when the
        # response was cut at the num_predict cap (done_reason=length) BEFORE
        # the closing tag — the captured section then ENDS with an incomplete
        # line (e.g. "…introjection (concrete, affectively charged."). A
        # distinction missing its contrast half is noise: drop that one
        # trailing line. Complete (closed-tag) sections are never touched.
        key_distinctions = strip_truncated_section_tail(
            key_distinctions,
            closing_tag_present='</key_distinctions>' in cleaned.lower(),
        )
    ttm = re.search(
        r'<theoretical_tensions>\s*(.*?)(?:</theoretical_tensions>|$)',
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if ttm:
        tensions = ttm.group(1).strip()
        tensions = strip_truncated_section_tail(  # V18.20.3.1 (D1) — same class
            tensions,
            closing_tag_present='</theoretical_tensions>' in cleaned.lower(),
        )
    key_distinctions = strip_thinking(key_distinctions)
    key_distinctions = strip_markup_tags(key_distinctions)
    key_distinctions = strip_reasoning_leaks(key_distinctions)
    tensions = strip_thinking(tensions)
    tensions = strip_markup_tags(tensions)
    tensions = strip_reasoning_leaks(tensions)

    # V18.20.4.11 (P1 / T-a2): make the ladder's outcome visible. Routine
    # result → one DEBUG line (winning rung + counts). Degenerate outcome
    # (non-empty input, ALL fields empty) → WARNING: the downstream salvage
    # (bullet_pipeline) also has nothing to work with, and this used to be
    # completely silent. Counts only — no content at WARNING.
    if cleaned and cleaned.strip():
        if not (exec_sum.strip() or bullets or thorough.strip()
                or key_distinctions.strip() or tensions.strip()):
            logger.warning(
                "universal parser: non-empty input (%d chars) produced ZERO "
                "content (exec/bullets/thorough/additive sections all empty)",
                len(cleaned),
            )
        else:
            logger.debug(
                "universal parser: %d bullets (via %s), exec %d chars, "
                "thorough %d chars",
                len(bullets), _bp_src, len(exec_sum), len(thorough),
            )

    return {
        "executive_summary": exec_sum,
        "bullet_points": bullets,
        "thorough_summary": thorough,
        "key_distinctions": key_distinctions,
        "theoretical_tensions": tensions,
    }


# ── V13.31.1 (P2.13 step 1): sentence-level text utilities ────────────────
# Extracted from Summarizer._truncate_to_sentences / _extract_sentences_as_bullets
# (pure functions, no instance state — moved here to shrink the summarizer
# monolith). The Summarizer keeps thin delegation shims for backward compat.


def strip_truncated_section_tail(section_text: str, closing_tag_present: bool = True) -> str:
    """V18.20.3.1 (real-rig audit D1): drop the trailing incomplete line of a
    truncated additive section.

    When an additive-section LLM response is cut at the num_predict cap
    (``done_reason=length``) mid-section, the capturing regex's end-of-string
    fallback accepts the partial section — and its LAST line is an incomplete
    sentence (unbalanced parens/quotes, dangling tail, or no terminal
    punctuation; e.g. ``"AuthorD's distinction between introjection
    (concrete, affectively charged."`` from the V18.20.3.0 the rig-test book
    run). An additive item missing its second half is noise, not content —
    drop that ONE trailing line. Earlier lines are complete (a generation cut
    happens once) and are never touched.

    Lives here (not in ``post_processing``) because ``post_processing``
    imports from this module; ``is_truncated`` is lazily imported at call
    time to avoid the import cycle.

    Args:
        section_text: the captured section body.
        closing_tag_present: True when the section's closing tag was present
            in the raw response (section is complete → returned UNCHANGED).
            False when the section was captured by the unclosed-tag
            end-of-string fallback (response truncated mid-section).

    Returns:
        The sanitized section text (trailing blank lines trimmed when a line
        was dropped; otherwise byte-identical input).
    """
    if not section_text or closing_tag_present:
        return section_text
    from core.summarisation.post_processing import is_truncated  # lazy: avoids import cycle

    lines = section_text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped:
            continue  # skip trailing blanks; the cut line is the last content
        candidate = stripped.lstrip("-*• ").strip()
        if candidate and is_truncated(candidate):
            del lines[i]
            return "\n".join(lines).rstrip()
        break  # last content line is complete → nothing to strip
    return section_text


def truncate_to_sentences(text: str, max_sentences: int = 2, max_words: int = 35) -> str:
    """Truncate text to at most ``max_sentences``, capped at ``max_words``.

    Splits on sentence-ending punctuation (. ! ?) and keeps the first
    N sentences. If a single sentence exceeds ``max_words``, truncates at
    the word boundary.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    kept = []
    word_count = 0
    for sent in sentences[:max_sentences]:
        sent_words = sent.split()
        if word_count + len(sent_words) > max_words:
            remaining = max_words - word_count
            if remaining > 5:
                kept.append(' '.join(sent_words[:remaining]) + '…')
            break
        kept.append(sent)
        word_count += len(sent_words)
    return ' '.join(kept).strip() if kept else text[:200].strip()


def extract_sentences_as_bullets(text: str, max_bullets: int = 15) -> list[str]:
    """Extract sentences from text as bullet points.

    Used as a last-resort salvage when the parser can't find bullets
    but the thorough summary has content.  Splits on sentence
    boundaries and returns the first N sentences that are long
    enough to be meaningful (>20 chars).
    """
    if not text or not text.strip():
        return []
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    bullets = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20:
            continue
        if sent.startswith('#') or sent.startswith('['):
            continue
        bullets.append(sent)
        if len(bullets) >= max_bullets:
            break
    # V18.20.4.11 (P1 / T-a2): this is the LAST rung of the parse ladder —
    # its only production caller (bullet_pipeline's salvage) reaches it
    # after every structured parser AND plain-text extraction found
    # nothing. Both outcomes are exceptional, hence WARNING with counts
    # (no content): salvaged (the ladder degraded to sentence-splitting)
    # and zero-yield (degenerate input even for the fallback).
    if bullets:
        logger.warning(
            "sentence fallback: salvaged %d bullets from %d chars "
            "(structured parsers found none)",
            len(bullets), len(text),
        )
    else:
        logger.warning(
            "sentence fallback: %d-char input yielded 0 bullets "
            "(no qualifying sentence found)",
            len(text),
        )
    return bullets
