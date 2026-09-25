"""V18.20.4.7 (P5 phase 2 / O-a2): the thorough-theorist floor — a
Summarizer mixin.

The V18.20.3.13 (Phase 5 / W7+O3) thorough gap-fill machinery — exactly one
runtime method, ``_thorough_theorist_floor`` — moved out of the ~5.2k-line
``summarizer.py`` monolith into this module, re-homed via the mixin
pattern (``Summarizer`` inherits ``SummarizerThoroughFloorMixin``). The
call site (``thorough = self._thorough_theorist_floor(...)``) stays in
``_summarize_inner`` — that orchestrator is explicitly NOT moved (out of
the approved P5 scope).

VERBATIM CONTRACT: the method body was byte-identical to the V18.20.4.6
zip's ``summarizer.py`` through V0.4.23. V0.4.24 (audit backlog #2+#4+#6,
the V4.23 run post-mortem) deliberately changed it: the single 47-name
gap-fill call became ≤3 chunked calls (≤12 names each) with anti-roster
prompt constraints, the unclosed ``<thorough_addition>`` fallback now runs
the V18.20.3.2 KD/TT truncation guard, and the shipped addition is
filtered by the module-level attribution-edge co-occurrence check
(``_grounded_addition_sentences``).
"""

from __future__ import annotations

import re
from collections import Counter

from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()

# V0.4.24 (audit backlog #6): co-occurrence window — a name's claim is
# "near" the name when its key phrase appears within this many characters
# of any occurrence of the name in the source.
_NAME_WINDOW = 600

# V0.4.32 (audit backlog item 1): the source-size gate. The V0.4.32
# rarest-4 keyword selection is meaningful only on sources large enough
# that a 0-frequency rare word is a fabrication signature (the word
# appears nowhere in a real-sized source → the claim is fabricated). On
# tiny synthetic test sources (≤1000 chars), the rarest-4 degenerates
# to all 0-frequency words (the source is too small to contain them);
# the V0.4.24 first-8-by-position rule is used instead. Real chapter
# sources are always ≥10× this threshold.
_MIN_SOURCE_CHARS = 1000


def _grounded_addition_sentences(
    addition: str, source: str, names: list[str]
) -> tuple[str, list[str]]:
    """V0.4.24 (audit backlog #6) → V0.4.32 (audit backlog item 1):
    attribution-edge check on gap-fill prose.

    The V0.4.23 thorough gap-fill shipped a sentence welding a theorist to
    a criticism he never appears near in the source ("N's theories were
    referenced regarding <M's criticism>" — N occurs nowhere near that key
    phrase; the audited instance: a developmental theorist welded to a
    play-technique criticism that belongs to a different author). This
    filter drops a sentence when NONE of the names it carries co-occur
    (±600 chars) with ANY of the sentence's distinctive content words —
    the welding signature.

    V0.4.32 (V0.4.31 ch.6 audit backlog item 1 — the F1-F5 hallucination
    class): the V0.4.24 first-N-by-position keyword selection (cap 8) was
    too coarse — it picked common abstract words ("further", "distinct",
    "affective", "individual") that share a window with any cited author
    elsewhere in the source, passing fabricated substantive claims whose
    actual content words never co-occur with the cited author. The rig
    audit's F1 (a fabricated "differentiate from anxiety/depression" claim
    attached to an author whose actual source claim is "phobic vs paranoid
    characters") slipped because ONE of the first-8 keywords ("affective")
    happens to appear in that author's ±600-char source window. The V0.4.32
    fix sorts the candidate keywords by RAREST source frequency first and
    takes the rarest 4 — the claim's distinctive content fingerprint — so
    the common-word false-positive is removed and the fabricated claim is
    dropped. (Content-agnostic per Rule 1: the rule is a structural
    property of source-word-frequency, not a book-specific property. The
    F1-F5 evidence is book-specific; the fix is generic — it improves
    detection on any book where an LLM fabricates a substantive claim
    attached to a real author whose actual source claim is different.)

    Honest deviation disclosed (Rule 2): the audit's narrative said the
    V0.4.24 attribution-edge drop "does NOT cover thorough additive
    prose." That characterisation is inaccurate — the check IS applied
    to the thorough-theorist-floor chunked gap-fill output (call site at
    line 397 of this module; conversion-log lines 879-881 confirm the
    check RAN on the V0.4.31 rig run, dropping 2 wrong-year thorough
    additive sentences). The F1-F5 hallucinations slipped not because
    the check was missing on the thorough path, but because the check's
    keyword extraction was too coarse: the V0.4.24 first-N-by-position
    selection picked common abstract words that share a window with any
    cited author elsewhere in the source. The V0.4.32 fix targets THIS
    root cause (rarest-first sort + cap 4 + a source-size gate so the
    rarest-4 probe is only invoked when the source is large enough that
    a 0-frequency rare word is a fabrication signature, not a small-source
    artifact).

    High-precision by construction:
      * only sentences that carry one of the chunk's missing names are
        checked — prose without a gap-fill name passes untouched;
      * keywords are ≥6 chars, de-duplicated, sorted rarest-first, capped
        at 4 (the V0.4.24 cap was 8 by position — too coarse), and exclude
        words so frequent in the source (>40 occurrences) that they
        cannot anchor a co-occurrence;
      * a name absent from the source entirely is kept (it arrived from
        the deterministic analysis, not the model);
      * a sentence with no anchorable keywords after filtering is kept
        (cannot probe — unverifiable);
      * a sentence is dropped only when EVERY name in it fails the
        co-occurrence probe on the rarest-4 fingerprint.

    Source-size gate (V0.4.32): on sources smaller than
    ``_MIN_SOURCE_CHARS`` (~1000 chars / ~200 words — well below the
    smallest real chapter, well above the synthetic test sources), the
    rarest-4 selection degenerates (almost every distinctive word is
    0-frequency because the source is too small to contain it). On
    such tiny sources the V0.4.24 first-8-by-position rule is used
    instead (lenient; matches the V0.4.24 test fixtures). On real
    chapter sources the V0.4.32 rarest-4 rule is used (discriminating;
    catches the F1-F5 fabricated-claim class).

    Returns ``(filtered_addition, dropped_sentences)`` — paragraph
    structure preserved; a paragraph whose every sentence was dropped
    vanishes. Never raises.
    """
    try:
        if not addition or not source or not names:
            return addition, []
        src_lower = source.lower()
        freq = Counter(re.findall(r"[a-z]{6,}", src_lower))
        generic = {w for w, c in freq.items() if c > 40}
        # V0.4.32 (audit backlog item 1): source-size gate. The rarest-
        # 4 selection is meaningful only on sources large enough that
        # a 0-frequency rare word is a fabrication signature. On tiny
        # test sources (≤1000 chars) the rarest-4 degenerates to all
        # 0-frequency words (the source simply doesn't contain them);
        # the V0.4.24 first-8-by-position rule is used instead. Real
        # chapter sources (≥10× the threshold) always use V0.4.32.
        use_v0432_rarest4 = len(source) >= _MIN_SOURCE_CHARS
        out_paras: list[str] = []
        dropped: list[str] = []
        for para in re.split(r"\n{2,}", addition):
            para = para.strip()
            if not para:
                continue
            kept_s: list[str] = []
            for sent in (s.strip() for s in re.split(r"(?<=[.!?])\s+", para)):
                if not sent:
                    continue
                sent_names = [n for n in names if re.search(rf"\b{re.escape(n)}\b", sent)]
                if not sent_names:
                    kept_s.append(sent)
                    continue
                kws = [
                    w
                    for w in re.findall(r"[a-z]{6,}", sent.lower())
                    if w not in generic and not any(w in n.lower() for n in sent_names)
                ]
                kws = list(dict.fromkeys(kws))
                if use_v0432_rarest4:
                    # V0.4.32 (audit backlog item 1): sort RAREST-first
                    # (lowest source frequency) and cap at 4 — the V0.4.24
                    # first-N-by-position cap (8) picked common abstract
                    # words that share a window with any cited author
                    # elsewhere in the source, passing the F1-F5 fabricated-
                    # claim class. The rarest-4 are the claim's distinctive
                    # content fingerprint; a fabricated substantive claim
                    # whose actual content words never co-occur with the
                    # cited author's source window is dropped even when a
                    # common word like "affective" or "individual" happens
                    # to share that window.
                    kws.sort(key=lambda w: freq.get(w, 0))
                    kws = kws[:4]
                else:
                    # V0.4.24 fallback: first 8 by position (lenient on
                    # tiny test sources where rarest-first degenerates).
                    kws = kws[:8]
                # No anchorable keywords → cannot probe; keep (the V0.4.24
                # unverifiable-keep behaviour, made explicit here).
                if not kws:
                    kept_s.append(sent)
                    continue
                grounded = False
                for n in sent_names:
                    n_low = n.lower()
                    if n_low not in src_lower:
                        grounded = True  # unverifiable — keep (came from the analysis)
                        break
                    windows = " \u0000 ".join(
                        src_lower[max(0, m.start() - _NAME_WINDOW) : m.end() + _NAME_WINDOW]
                        for m in re.finditer(re.escape(n_low), src_lower)
                    )
                    if any(re.search(rf"\b{re.escape(kw)}\b", windows) for kw in kws):
                        grounded = True
                        break
                if grounded:
                    kept_s.append(sent)
                else:
                    dropped.append(sent)
            if kept_s:
                out_paras.append(" ".join(kept_s))
        return ("\n\n".join(out_paras), dropped)
    except Exception:
        return addition, []


# V0.4.32 (audit backlog item 2): the Phase 2.2 semantic fact-check scope
# extension — the SAME semantic_fact_check helper the bullet pipeline
# (apply_phase22_semantic_fact_check, V3.7.0) runs on bullets, applied
# to thorough additive prose. The V0.4.31 ch.6 rig audit's F1-F5
# hallucinations would fail a ≥0.50 embedding similarity check (they're
# fabricated claims, low similarity to the source's actual claims about
# the cited authors). Content-agnostic per Rule 1: the check uses the
# embedder + the source text, no hardcoded names.
# V18.2.30 degenerate-signal guard (the V0.4.25 honest-divergence
# pattern): when the embedder is unhealthy, the check is skipped with
# an explicit log line — a broken embedder produces zero/NaN vectors
# which always score <0.50 similarity, dropping ALL prose as
# "hallucinated" (churn). In that case, rely on the attribution-edge
# drop (item 1, _grounded_addition_sentences above) for hallucination
# filtering.
# V0.4.32 threshold source: thresholds.py _SEMANTIC_FACT_CHECK_DROP
# (V18.20.2.0 SWOT-A2 — the same threshold the bullet pipeline uses;
# the helper imports it lazily so the module doesn't pull in
# thresholds.py at import time).
def _semantic_ground_addition_sentences(
    addition: str,
    source: str,
    threshold: float | None = None,
) -> tuple[str, list[str]]:
    """V0.4.32 (audit backlog item 2): semantic fact-check on
    thorough additive prose.

    The V3.7.0 Phase 2.2 semantic fact-check on bullets
    (``apply_phase22_semantic_fact_check`` in ``bullet_pipeline.py``)
    verifies each bullet's embedding similarity to the source ≥0.50
    (the V18.20.2.0 ``_SEMANTIC_FACT_CHECK_DROP`` threshold). The
    V0.4.31 ch.6 rig audit found 5 fabricated claims (F1-F5) in
    thorough additive paragraph 5 that would have been caught by this
    check (fabricated claims have low embedding similarity to the
    source's actual claims about the cited authors). The V0.4.32
    closes the bullets-only gap by running the SAME check on thorough
    additive prose via this helper.

    Fail-soft (house pattern): if the embedder is unhealthy (the V18.2.30
    degenerate-signal guard — the V0.4.25 honest-divergence pattern),
    the check is skipped and the original addition is returned unchanged
    with no dropped sentences. A broken embedder produces zero/NaN
    vectors which always score <0.50 similarity, dropping ALL prose as
    "hallucinated" (churn); in that case, the attribution-edge drop
    (item 1) is the active hallucination filter. The sandbox has no
    sentence-transformers installed → the guard fires here; the actual
    semantic check runs on the rig (which has nomic-embed-text via
    Ollama).

    Args:
        addition: the thorough additive prose to filter (one or more
            paragraphs, separated by blank lines).
        source: the chapter source text to ground against.
        threshold: the similarity threshold below which a sentence is
            dropped. Defaults to ``_SEMANTIC_FACT_CHECK_DROP`` from
            ``thresholds.py`` (0.50 — the same threshold the bullet
            pipeline uses).

    Returns:
        ``(filtered_addition, dropped_sentences)`` — paragraph
        structure preserved; a paragraph whose every sentence was
        dropped vanishes. Never raises.
    """
    try:
        if not addition or not source:
            return addition, []
        # V18.2.30: degenerate-signal guard. A broken embedder produces
        # zero/NaN vectors which always score <0.50 similarity (dropping
        # ALL prose as "hallucinated" — churn). Skip the check entirely
        # and rely on the attribution-edge drop (item 1) for hallucination
        # filtering in that case. The sandbox has no sentence-transformers
        # → is_embedder_healthy() returns False → the guard fires here.
        from core.llm.model_singletons import is_embedder_healthy

        if not is_embedder_healthy():
            return addition, []
        if threshold is None:
            from core.summarisation.thresholds import (
                SEMANTIC_FACT_CHECK_DROP as _P22_THRESHOLD,
            )

            threshold = float(_P22_THRESHOLD)
        from core.summarisation.text_preprocessor import semantic_fact_check

        out_paras: list[str] = []
        dropped: list[str] = []
        for para in re.split(r"\n{2,}", addition):
            para = para.strip()
            if not para:
                continue
            kept_s: list[str] = []
            for sent in (s.strip() for s in re.split(r"(?<=[.!?])\s+", para)):
                if not sent:
                    continue
                # V0.4.32: very short sentences (<20 chars) are kept
                # without probing — embedding similarity on very short
                # text is unreliable (the bullet pipeline's
                # apply_phase22_semantic_fact_check applies the same
                # heuristic implicitly by operating on bullets ≥10 chars).
                if len(sent) < 20:
                    kept_s.append(sent)
                    continue
                result = semantic_fact_check(sent, source, threshold=threshold)
                if result.get("is_grounded"):
                    kept_s.append(sent)
                else:
                    dropped.append(sent)
            if kept_s:
                out_paras.append(" ".join(kept_s))
        return ("\n\n".join(out_paras), dropped)
    except Exception:
        return addition, []


class SummarizerThoroughFloorMixin:
    """Thorough-theorist floor for :class:`Summarizer` (see the module
    docstring). The method body is byte-identical to summarizer.py's."""

    def _thorough_theorist_floor(
        self,
        heading: str,
        content: str,
        thorough: str,
        analysis: str,
        scaled_target_hi: int | None = None,
    ) -> str:
        """V18.20.3.13 (Phase 5 / W7+O3): thorough-theorist floor + targeted gap-fill.

        Why this exists (the .3.7 SWOT W7 gap, approved as O3 for this
        phase): the recall floor (V18.20.3.4) guarantees theorist coverage
        in the BULLETS, and the V18.14 thorough-only judge line is purely
        informational — when the thorough missed theorists, nothing
        repaired it and nothing enforced a floor. This method (a) measures
        the floor on the FINAL thorough text with the same
        ``check_coverage(analysis, text)`` machinery the thorough-only
        judge uses, (b) logs it in the recall-floor house style (INFO when
        met / WARNING when not), and (c) when authors are missing, the
        deadline allows it, and the thorough is non-trivial, fires targeted
        LLM calls (``_call_llm_with_empty_retry``) asking for 1-2 flowing
        paragraphs that weave in ONLY the missing contributors,
        source-grounded, appended to the thorough. After the append it
        re-runs the coverage check and logs the honest before/after line.

        V0.4.24 (audit backlog #2+#4, the V4.23 run post-mortem): the
        single call is now CHUNKED — ≤12 names per call, at most 3 calls.
        The V4.23 run asked one 1024-token call to weave 47 names; the
        model's only way to comply was a 40-name roster paragraph (the
        name-dump defect) and the response was cut mid-sentence — shipping
        a visible unclosed ``<thorough_addition>`` tag (the fallback path
        had none of the truncation guards the KD/TT additive path got in
        V18.20.3.2). Each chunked call now gets the anti-roster prompt
        constraints, the unclosed-tag-safe regex, and the
        ``strip_truncated_section_tail`` guard; the shipped addition is
        additionally filtered by the attribution-edge co-occurrence check
        (``_grounded_addition_sentences`` — the welded-attribution class).

        Book-agnostic (.3.9 standing rule): the missing-author list comes
        from the RUNTIME deterministic analysis passed in as ``analysis``
        (the same ``find_analysis_for_heading`` result the recall floor
        uses) — no author/theorist/person name is hardcoded here, and the
        names only ever flow from analysis → prompt at runtime.

        Fail-soft (house pattern): any crash logs a WARNING and the
        original thorough is returned unchanged — the chapter is never
        broken by the floor itself.

        Args:
            heading: chapter heading (prompt context).
            content: chapter source text (prompt grounding, clamped).
            thorough: the FINAL thorough summary text.
            analysis: the deterministic analysis text for this chapter
                (``_analysis_rf`` from the caller — "" disables the floor,
                same as the recall floor's no-analysis behaviour).

        Returns:
            The thorough text — with the gap-fill paragraphs appended when
            the targeted calls succeeded, otherwise the original.
        """
        try:
            if not analysis or not (thorough or "").strip():
                # Nothing measurable — the recall-floor house style logs
                # nothing when there is no analysis (theorist list) to
                # measure against.
                return thorough
            from core.preprocessing.deterministic_analyzer import check_coverage

            _cov = check_coverage(analysis, thorough)
            _total = _cov.get("total") or 0
            if not _total:
                return thorough
            _covered = len(_cov.get("covered", []) or [])
            _missing = list(_cov.get("missing", []) or [])
            # V18.20.3.13 floor line — recall-floor house style (INFO when
            # met / WARNING when not; missing names listed like the V18.14
            # judge lists them so the operator can act without re-running).
            self.log(
                f"    🎯 V18.20.3.13 Thorough theorist floor: {_covered}/{_total} authors in thorough"
                + (
                    f" — MISSING from thorough: {_missing[:5]}"
                    if _missing
                    else " — ALL IN THOROUGH ✅"
                ),
                "INFO" if not _missing else "WARNING",
            )
            if not _missing:
                return thorough
            # ── Repair decision (O3: one targeted call) ──────────────────
            # V0.20 (Quality Campaign, audit V0.18 on the standing test
            # chapter, Defect C): this gap-fill is NON-SKIPPABLE on deadline.
            # The V0.18 rig run took 1551s > 1200s deadline and skipped this
            # phase (conversion-log "skipping optional phase: thorough
            # theorist floor gap-fill") — the thorough shipped with 13/37
            # theorists (35%), missing 5 named contributors. This is the
            # ONLY phase that repairs thorough-theorist coverage: the recall
            # floor (V18.20.3.4) guarantees theorist coverage in the
            # BULLETS, but nothing else enforces a floor on the THOROUGH.
            # Skipping it on a deadline overrun trades a timing constraint
            # for a coverage deficit — the opposite of the V0.20 campaign
            # goal ("QUALITY, not timing"). The V18.20.3.4 precedent
            # (post-gap-fill dedup made non-skippable because "it is the
            # ONLY pass that runs after the gap-fill rounds, so skipping it
            # ships every duplicate the gap-fill introduced") applies
            # directly: skipping this ships every theorist the thorough
            # missed. The single targeted call (~60-130s) is bounded by
            # _call_llm_with_empty_retry's own timeout + the fail-soft
            # try/except below — the worst case is one extra bounded call,
            # not an unbounded hang.
            if self._deadline_exceeded("thorough theorist floor gap-fill"):
                self.log(
                    f"    ⏱️⚠️ V0.20: Deadline exceeded but the thorough "
                    f"theorist floor gap-fill is NON-SKIPPABLE (the thorough "
                    f"is missing {len(_missing)} of {_total} theorists — coverage "
                    f"deficit is the V0.20 campaign target; timing is not). "
                    f"Running the targeted calls anyway.",
                    "WARNING",
                )
            _tf_words = len((thorough or "").split())
            # V0.05 (rig audit F9b): BUDGET GATE — the 150-300-word append is
            # skipped when the thorough already meets its SOURCE-SCALED target
            # (``scaled_target_hi`` from length_policy.thorough_target). The
            # V0.04 rig's short chapters were padded past their sources by
            # exactly this append; a summary section never grows beyond its
            # scaled ceiling to chase a name that the bullets already carry.
            if scaled_target_hi is not None and _tf_words >= int(scaled_target_hi):
                self.log(
                    f"    ⏭️  V0.05: Thorough gap-fill skipped — thorough "
                    f"({_tf_words} words) already meets its source-scaled "
                    f"target ({scaled_target_hi} words); the missing "
                    f"contributor(s) are covered by the bullets/recall floor",
                    "INFO",
                )
                return thorough
            if _tf_words < 50:
                # A stub thorough (empty/exec-copy/degenerate) cannot be
                # safely extended with "continuation" prose — report and
                # leave the floor verdict as the honest record.
                self.log(
                    f"    ⏭️  V18.20.3.13: Thorough gap-fill skipped — thorough "
                    f"too short ({_tf_words} words) to extend; floor stays "
                    f"{_covered}/{_total}",
                    "INFO",
                )
                return thorough
            # ── V0.4.24 (audit backlog #4): CHUNKED targeted gap-fill ─────
            # Source clamp mirrors the dedicated-thorough prompt
            # (prompt_assembly: ~40k chars); the thorough TAIL (~4k chars,
            # the exec-from-thorough prompt's thorough cap) gives the model
            # the prose style to match without re-sending the whole field.
            _NAMES_PER_CALL = 12
            _MAX_FLOOR_CALLS = 3
            _chunks = [
                _missing[i : i + _NAMES_PER_CALL] for i in range(0, len(_missing), _NAMES_PER_CALL)
            ][:_MAX_FLOOR_CALLS]
            _source = (content or "")[:40000]
            _tail = (thorough or "")[-4000:]
            _lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
            _additions: list[str] = []
            _chunk_calls = 0
            for _chunk in _chunks:
                _names = ", ".join(_chunk)
                # V18.20.3.13: inline f-string prompt (the same ROLE/CONTEXT/
                # TASK/CONSTRAINTS/INPUT shape the prompt_assembly helpers
                # use) — no new prompt FILE; every name in it arrives at
                # runtime from the deterministic analysis.
                # V0.4.24 (audit backlog #4): the anti-roster constraints —
                # the V4.23 single 47-name call produced a paragraph whose
                # opening sentence WAS the name list (citation adjacency in
                # prose form).
                _prompt = f"""### ROLE ###
You are a senior academic summarizer. Your task is to write a short prose addition to an existing thorough summary. {_lang}

### CONTEXT ###
Chapter: "{heading}"

The final paragraphs of the existing thorough summary (for style matching only):
<thorough_tail>
{_tail}
</thorough_tail>

### TASK ###
The thorough summary above does not yet mention every named contributor from the chapter. Write ONE to TWO flowing paragraphs (roughly 150-300 words) that weave in ONLY the {len(_chunk)} contributors listed below, each with their SPECIFIC contribution as described in the chapter source:

{_names}

### CONSTRAINTS ###
- Flowing academic prose that matches the style of the thorough summary above — no bullet points, no headings, no lists
- ONLY the listed contributors — do not repeat contributors the thorough summary already covers
- Ground every attribution in the chapter source below; do NOT invent facts, dates, works, or attributions
- NEVER open a paragraph with a roster of names, and never write a sentence that names several contributors without stating each one's specific contribution — a name list in prose form is citation adjacency, not content
- The paragraphs will be APPENDED to the thorough summary — write them as a natural continuation with no preamble
- Do NOT include thinking/reasoning — only the final prose
- Wrap the output exactly like this:

<thorough_addition>
your one-to-two paragraphs here
</thorough_addition>

### INPUT ###
Chapter content:
{_source}"""
                _raw = self._call_llm_with_empty_retry(
                    _prompt,
                    model=self.primary_model,
                    temperature=self.temperature,
                    # V0.4.24 (audit backlog #2): 1024 → 1536. With ≤12
                    # names per chunk the honest ask (~300 words ≈ 400
                    # tokens) fits comfortably; 1536 is 3.8× the ask and
                    # the truncation guard below makes even a cut ship
                    # cleanly. The V4.23 47-name call blew the 1024 cap
                    # mid-sentence and shipped an unclosed tag.
                    max_tokens=1536,
                )
                _chunk_calls += 1
                if not _raw or not _raw.strip():
                    self.log(
                        f"    ⚠️ V18.20.3.13: Thorough gap-fill call returned "
                        f"empty for a {len(_chunk)}-name chunk — chunk skipped",
                        "WARNING",
                    )
                    continue
                _raw = self._strip_thinking(_raw)
                # V18.16.0.1-class CoT guard (same as _ensure_exec_from_thorough):
                # a thinking-mode response must never be appended as prose.
                from core.summarisation.postchecks import detect_cot_narrative

                _raw_cleaned, _cot_issues = detect_cot_narrative(_raw, "thorough")
                if _cot_issues:
                    self.log(
                        f"    ⚠️ V18.20.3.13: Thorough gap-fill output looks like "
                        f"CoT ({_cot_issues[0].detail[:60]}) — chunk discarded",
                        "WARNING",
                    )
                    continue
                # V0.4.24 (audit backlog #2 — the truncation guard): the
                # unclosed-tag-safe regex (the V4.23 regex required BOTH
                # tags, so a max_tokens cut that ate </thorough_addition>
                # fell back to shipping the RAW response — visible opening
                # tag and mid-sentence tail). The opening tag is always
                # consumed; the cut tail is dropped by the SAME
                # strip_truncated_section_tail the KD/TT additive path uses
                # (V18.20.3.2).
                _closed = "</thorough_addition>" in _raw_cleaned
                _m = re.search(
                    r"<thorough_addition>(.*?)(?:</thorough_addition>|$)",
                    _raw_cleaned,
                    re.DOTALL,
                )
                _addition = _m.group(1).strip() if _m else _raw_cleaned.strip()
                if not _closed:
                    from core.summarisation.response_parser import (
                        strip_truncated_section_tail,
                    )

                    _sanitized = strip_truncated_section_tail(_addition, closing_tag_present=False)
                    if _sanitized != _addition:
                        self.log(
                            "    ✂️ V0.4.24: thorough_addition was cut at the "
                            "output cap — dropped the incomplete trailing line "
                            "(the V18.20.3.2 KD/TT guard, now applied to this "
                            "path too)",
                            "WARNING",
                        )
                        _addition = _sanitized
                if len(_addition.split()) < 20:
                    self.log(
                        f"    ⚠️ V18.20.3.13: Thorough gap-fill addition too short "
                        f"({len(_addition.split())} words) — chunk discarded",
                        "WARNING",
                    )
                    continue
                # V0.4.24 (audit backlog #6): attribution-edge filter — a
                # sentence welding a chunk name to key phrases that never
                # co-occur with that name in the source is dropped (the
                # welded-attribution class).
                _addition, _dropped_sents = _grounded_addition_sentences(
                    _addition, content or "", _chunk
                )
                for _ds in _dropped_sents:
                    self.log(
                        f"    🧹 V0.4.24: gap-fill sentence dropped "
                        f'(attribution-edge): "{_ds[:70]}…" — its name(s) never '
                        f"co-occur with the claim's key phrases in the source",
                        "WARNING",
                    )
                if len(_addition.split()) < 20:
                    self.log(
                        "    ⚠️ V0.4.24: Thorough gap-fill chunk fully dropped by "
                        "the attribution-edge filter",
                        "WARNING",
                    )
                    continue
                # V0.4.33 (audit item 1): wire the semantic fact-check
                # (V0.4.32 item 2's helper — was dead code, never called)
                # into the production pipeline. Runs AFTER the attribution-
                # edge check; if the embedder is unhealthy (sandbox), the
                # degenerate-signal guard fires + the original is returned
                # unchanged. On the rig, catches fabricated claims with
                # low embedding similarity to the source.
                _addition, _sem_dropped = _semantic_ground_addition_sentences(
                    _addition, content or ""
                )
                for _ds in _sem_dropped:
                    self.log(
                        f"    🧹 V0.4.33: thorough gap-fill sentence dropped "
                        f'(semantic fact-check): "{_ds[:70]}…" — embedding '
                        f"similarity < 0.50 to the source",
                        "WARNING",
                    )
                if len(_addition.split()) < 20:
                    self.log(
                        "    ⚠️ V0.4.33: Thorough gap-fill chunk fully dropped "
                        "by the semantic fact-check filter",
                        "WARNING",
                    )
                    continue
                _additions.append(_addition)
            if not _additions:
                self.log(
                    f"    ⚠️ V18.20.3.13: Thorough gap-fill produced no usable "
                    f"addition ({_chunk_calls} call(s)) — thorough unchanged, "
                    f"floor stays {_covered}/{_total}",
                    "WARNING",
                )
                return thorough
            thorough = (thorough or "").rstrip() + "\n\n" + "\n\n".join(_additions)
            # Re-run the SAME coverage check on the appended thorough so the
            # after-line is a measurement, not a promise.
            _cov_after = check_coverage(analysis, thorough)
            _skipped_names = max(0, len(_missing) - _MAX_FLOOR_CALLS * _NAMES_PER_CALL)
            self.log(
                f"    ✅ V18.20.3.13 Thorough gap-fill: floor {_covered}/{_total} → "
                f"{len(_cov_after.get('covered', []) or [])}/{_cov_after.get('total') or 0} "
                f"({_chunk_calls} chunked call(s), ≤{_NAMES_PER_CALL} names each"
                + (
                    f"; {_skipped_names} name(s) beyond the 3-call bound remain "
                    f"thorough-uncovered — carried by the bullets/recall floor"
                    if _skipped_names
                    else ""
                )
                + ")",
                "INFO",
            )
            return thorough
        except Exception as _tf_e:
            # Fail-soft (house pattern): the floor must never break the
            # chapter — log visibly and ship the thorough unchanged.
            self.log(
                f"    ⚠️ V18.20.3.13: Thorough theorist floor failed (non-fatal): "
                f"{type(_tf_e).__name__}: {_tf_e}",
                "WARNING",
            )
            logger.debug(
                "thorough theorist floor failed: %s: %s",
                type(_tf_e).__name__,
                _tf_e,
            )
            return thorough
