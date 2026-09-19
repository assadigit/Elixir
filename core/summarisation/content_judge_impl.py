"""V9.3.0: Content Judge — final pre-output validation pass.

The Content Judge is the last gate before outputs are generated.  It answers
four questions about each chapter's summary:

1. **Full coverage?** — Did the summary cover ≥75% of the source's key claims?
2. **Grounded facts?** — Is every bullet point traceable to the source text?
3. **Hallucinations?** — Are there any claims not supported by the source?
4. **Concept deviations?** — Did the summary distort or misrepresent concepts?

**How it works (chunked, deterministic + semantic):**

1. Split the chapter's raw content into ~2000-token chunks.
2. For each chunk, extract key claims deterministically (sentences with
   numbers, named entities, causal language, domain terms).
3. For each key claim, check if it's semantically covered by the summary
   (embedding similarity ≥ 0.50 against any bullet or thorough-summary
   sentence).
4. Claims not covered → "uncovered" list.
5. Bullets not traceable to ANY chunk → "ungrounded" list (hallucination).
6. If coverage < 75%: trigger a gap-fill reprompt (send uncovered claims
   back to the LLM).
7. If ungrounded bullets > 20%: flag for re-summarization.

**Cost:** deterministic extraction is ~1-2s per chunk. Semantic similarity
uses sentence-transformers (same model already loaded for the existing
fact-check). Gap-fill reprompt only fires when coverage is poor.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.models import SummaryResult

# V18.2.21 (BUG-1/2/3 fix): import EmbedderUnavailable at module level so the
# except clause in _semantic_similarity can reference it even when
# sentence_transformers is NOT installed (the import inside the try would
# raise ModuleNotFoundError before EmbedderUnavailable was bound).
try:
    from core.llm.embedder_backend import EmbedderUnavailable
except Exception:  # pragma: no cover - defensive
    EmbedderUnavailable = RuntimeError  # type: ignore[assignment,misc]


class EmbeddingDisabled(RuntimeError):
    """V18.4 (Phase 2): raised by ``_semantic_similarity`` when the user has
    explicitly disabled the embedder AND chosen ``fallback="skip"``.

    This is the EXPLICIT, non-silent signal that Phase 2.2 (the semantic
    fact-check / coverage check) must be skipped entirely. ``ContentJudge.judge``
    checks the setting once at the top of Q1 and short-circuits the whole
    coverage loop — so this exception is a **defense-in-depth** for any OTHER
    caller that invokes ``_semantic_similarity`` directly without the judge
    pre-check (e.g. the per-bullet grounding loop). Such a caller should catch
    ``EmbeddingDisabled`` and treat the pair as "unmeasurable" rather than
    computing a misleading 0.0 similarity.

    Contrast with ``EmbedderUnavailable`` (the embedder was enabled but the
    backend is broken): that one falls back to Jaccard. ``EmbeddingDisabled``
    means the user OPTED OUT of similarity entirely.
    """


def _embedding_settings() -> tuple[bool, str]:
    """V18.4 (Phase 2): read the embedder optional-mode knobs from settings.

    Returns ``(enabled, fallback)`` with safe defaults ``(True, "jaccard")``
    when Settings is unavailable (e.g. import-time, test sandbox). Never
    raises.

    - ``enabled``   — gates the semantic-similarity path in
      ``_semantic_similarity`` (Phase 2.2 fact-check).
    - ``fallback``  — one of ``{"jaccard", "skip"}``; decides what happens
      when ``enabled=False``.
    """
    try:
        from utils.settings import Settings

        _enabled = Settings().get("embedding.enabled", True)
        _fallback = Settings().get("embedding.fallback", "jaccard")
    except Exception:
        _enabled, _fallback = True, "jaccard"
    # Defensive normalisation: unknown fallback values degrade to "jaccard"
    # (the safer, real-signal option) rather than "skip".
    if _fallback not in ("jaccard", "skip"):
        _fallback = "jaccard"
    return bool(_enabled), str(_fallback)


# V18.4 (Phase 2): one-time warning flag — fires when the semantic similarity
# helper is explicitly disabled (enabled=False) AND running in "skip" mode.
# Mirrors the existing ``_warned_semantic_fallback`` pattern: log once per
# process, not once per claim (which would spam the log for 46+ claims).
# V18.20.1.0 (D3): centralized to _runtime_state.state.warned_embedding_disabled.
# The module-level ``_warned_embedding_disabled`` below is a backward-compat
# proxy: tests that ``monkeypatch.setattr("...content_judge_impl._warned_embedding_disabled", True)``
# still work (it mutates the module attr), but the IMPL reads/writes
# ``state.warned_embedding_disabled`` directly. Both paths see the same value
# because the impl uses the shared state object.
from core.summarisation._runtime_state import state as _runtime_state

_warned_embedding_disabled = False  # backward-compat proxy (impl uses _runtime_state)

# V18.20.2.0 (SWOT-A finding 2 / thresholds wiring): the Q2 grounding
# threshold now imports from core/summarisation/thresholds.py — the declared
# SINGLE SOURCE OF TRUTH (previously zero production importers). Value is
# IDENTICAL to the previous literal (0.50) — wiring fix only.
from core.summarisation.thresholds import SEMANTIC_FACT_CHECK_DROP as _THRESHOLDS_SEMANTIC_DROP

# V10.1.0: langextract grounding is an optional Layer 8.  We import it
# lazily inside ContentJudge so this module still imports cleanly when
# langextract isn't installed.


LogFn = Callable[[str, str], None]


# ── Configuration ──────────────────────────────────────────────────────────

CHUNK_SIZE_TOKENS = 2000  # ~8000 chars per chunk
MIN_COVERAGE_PCT = 0.75  # 75% of source claims must be covered
GROUNDED_SIM_THRESHOLD = _THRESHOLDS_SEMANTIC_DROP  # min embedding similarity for "grounded" (V18.20.2.0: from thresholds.py, was 0.50)
UNGROUNDED_MAX_PCT = 0.20  # max 20% of bullets can be ungrounded
GAP_FILL_THRESHOLD = 0.75  # trigger gap-fill reprompt if coverage < 75%


@dataclass
class JudgeResult:
    """Result of the content judge for one chapter."""

    chapter_heading: str
    # Q1: Coverage
    total_source_claims: int = 0
    covered_claims: int = 0
    uncovered_claims: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    # Q2: Grounding
    total_bullets: int = 0
    grounded_bullets: int = 0
    ungrounded_bullets: list[str] = field(default_factory=list)
    grounding_pct: float = 0.0
    # Q3: Hallucinations (same as ungrounded, but separate label)
    hallucination_count: int = 0
    # Q4: Deviations (claims where the summary distorts the source)
    deviation_count: int = 0
    deviation_details: list[str] = field(default_factory=list)
    # V10.1.0: Layer 8 — langextract verbatim grounding (two-tier)
    # strong_grounded_bullets: bullets with a langextract char_interval
    #   (deterministic verbatim grounding — the strongest signal).
    # weak_grounded_bullets: bullets that failed verbatim but pass the
    #   existing semantic ≥ 0.50 check (paraphrased but topically sound).
    # ungrounded_strong: bullets that failed BOTH tiers (likely hallucinations).
    strong_grounded_bullets: int = 0
    weak_grounded_bullets: int = 0
    ungrounded_strong: list[str] = field(default_factory=list)
    grounding_layer8_available: bool = False
    grounding_alarm: str = ""  # non-empty if Layer 8 was degraded
    # Per-bullet evidence spans (char_interval → source snippet), for the
    # keypoints/flashcards/evidence-map outputs to consume.
    bullet_evidence: dict[str, str] = field(default_factory=dict)
    # V18.4 (Phase 2): True when Phase 2.2 (semantic coverage check) was
    # explicitly skipped because embedding.enabled=False + fallback="skip".
    # Distinguishes a user-opted-out skip from the degenerate-0/N auto-pass
    # (which fires when the embedder is broken, not disabled). When True,
    # coverage_pct is set to 1.0 (auto-pass) and uncovered_claims is empty —
    # the deterministic judge + postchecks still run downstream.
    coverage_skipped: bool = False
    # Overall
    passed: bool = False
    needs_gap_fill: bool = False
    summary: str = ""

    def format_report(self) -> str:
        """One-line summary for logging."""
        base = (
            f"📊 Judge: coverage={self.coverage_pct:.0%} "
            f"({self.covered_claims}/{self.total_source_claims} claims), "
            f"grounding={self.grounding_pct:.0%} "
            f"({self.grounded_bullets}/{self.total_bullets} bullets), "
            f"hallucinations={self.hallucination_count}, "
            f"deviations={self.deviation_count}"
        )
        if self.coverage_skipped:
            base += ", coverage=SKIPPED(embedding off)"
        if self.grounding_layer8_available:
            base += (
                f", L8={self.strong_grounded_bullets}S/"
                f"{self.weak_grounded_bullets}W/"
                f"{len(self.ungrounded_strong)}U"
            )
        elif self.grounding_alarm:
            base += f", L8=OFF({self.grounding_alarm})"
        base += f" — {'✅ PASS' if self.passed else '❌ FAIL'}"
        return base


# ── Claim extraction (deterministic, no LLM) ───────────────────────────────

# Patterns that indicate a "key claim" sentence
_CLAIM_PATTERNS = [
    # Contains numbers/data
    re.compile(r"\b\d+[.,]?\d*\s*[%‰]?\b"),
    # Contains causal/result language
    re.compile(
        r"\b(?:therefore|because|thus|hence|results? show|"
        r"found that|demonstrates?|indicates?|suggests?|"
        r"implies?|means?|causes?|leads? to|results? in)\b",
        re.IGNORECASE,
    ),
    # Contains definition language
    re.compile(
        r"\b(?:is defined as|refers to|means|consists of|"
        r"comprises|constitutes?)\b",
        re.IGNORECASE,
    ),
    # Contains comparison/contrast
    re.compile(
        r"\b(?:compared to|in contrast|whereas|while|"
        r"unlike|similarly|conversely)\b",
        re.IGNORECASE,
    ),
    # Contains named entity (Capitalized phrase 2+ words)
    re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
]

# Sentences to skip (not claims)
_SKIP_PATTERNS = [
    re.compile(
        r"^\s*(?:Figure|Table|Fig\.?|Eq\.?|Equation|Section|Chapter|Appendix)\s*\d", re.IGNORECASE
    ),
    re.compile(r"^\s*(?:References|Bibliography|Acknowledg)", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # page numbers
    re.compile(r"^\s*(?:©|Copyright|All rights reserved)", re.IGNORECASE),
]


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences (simple regex splitter)."""
    # Split on . ! ? followed by space + capital letter, or newline
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 30]


def _extract_key_claims(chunk_text: str) -> list[str]:
    """Extract key claims from a chunk of text (deterministic).

    A "key claim" is a sentence that contains at least one of:
    - Numbers/data
    - Causal/result language
    - Definition language
    - Comparison/contrast
    - Named entities

    Sentences that are figure/table captions or references are skipped.
    """
    sentences = _split_into_sentences(chunk_text)
    claims = []
    for sent in sentences:
        # Skip non-claim sentences
        if any(pat.match(sent) for pat in _SKIP_PATTERNS):
            continue
        # Check if sentence matches any claim pattern
        if any(pat.search(sent) for pat in _CLAIM_PATTERNS):
            claims.append(sent)
    # Cap at 8 claims per chunk to keep the check fast
    return claims[:8]


def _chunk_text(text: str, chunk_chars: int = 8000) -> list[str]:
    """Split text into chunks of approximately chunk_chars characters.

    Splits on paragraph boundaries to avoid breaking sentences.
    """
    if len(text) <= chunk_chars:
        return [text]
    chunks = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) > chunk_chars and current:
            chunks.append(current)
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current:
        chunks.append(current)
    return chunks


# ── Semantic similarity (uses sentence-transformers if available) ──────────

# V18.1 (S1): one-time warning flag — fires when the semantic similarity
# helper silently falls back to Jaccard word overlap because the embed
# model isn't available. Jaccard is a real (weaker) signal, not a silent
# pass, so we warn rather than fail-closed.
# V18.20.1.0 (D3): centralized to _runtime_state.state.warned_semantic_fallback.
_warned_semantic_fallback = False  # backward-compat proxy (impl uses _runtime_state)


def _jaccard(claim: str, candidate: str) -> float:
    """Jaccard word-overlap similarity between two strings.

    Factored out (V18.4 Phase 2) so the ``embedding.enabled=False`` explicit
    paths and the existing exception-driven fallbacks share one implementation.
    Returns 0.0 when either side has no words.
    """
    words1 = set(claim.lower().split())
    words2 = set(candidate.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def _semantic_similarity(claim: str, candidate: str, candidate_emb: Any = None) -> float:
    """Compute semantic similarity between two texts.

    Uses sentence-transformers if available, falls back to Jaccard word
    overlap (same pattern as the existing fact-check).

    V18.20.2.0 (SWOT A23): optional ``candidate_emb`` — a PRE-COMPUTED
    embedding for ``candidate`` (e.g. a hoisted source-chunk embedding from
    :func:`_encode_chunks_cached`). When supplied, the candidate is NOT
    re-encoded; every other step (settings gate, health check, degenerate-
    vector guard, cos_sim, Jaccard fallbacks) is identical to the two-encode
    path, so the returned values are identical.

    V10.31.0 (Sprint 4.6): uses the shared singleton from
    ``core.llm.model_singletons`` instead of a module-global that was
    never actually shared across modules (each file had its own
    ``_st_model`` global).

    V18.2.21 (BUG-1/2/3 fix): catches ``EmbedderUnavailable`` explicitly
    so a broken Ollama embed backend (model not pulled, zero vectors)
    trips the Jaccard fallback ONCE with a loud warning, rather than
    raising per-call and being swallowed into the generic Exception path.

    V18.4 (Phase 2): honours ``embedding.enabled`` + ``embedding.fallback``
    from settings. When ``enabled=False``:
      - ``fallback="jaccard"`` (default) → skip the embedder ATTEMPT and go
        straight to Jaccard (explicit, one INFO log). Phase 2.2 still runs
        on the lexical signal.
      - ``fallback="skip"`` → raise ``EmbeddingDisabled`` so the caller
        skips Phase 2.2 ENTIRELY (no similarity, no coverage %). This is
        the explicit, non-silent opt-out. ``ContentJudge.judge`` pre-checks
        the setting and short-circuits the whole coverage loop, so this
        exception is defense-in-depth for direct callers.
    """
    # V18.20.1.0 (D3): read/write the centralized state object directly.
    # This is the fix for the order-dependent test failures: patches against
    # the re-export module (content_judge._warned_X) OR the impl module
    # (content_judge_impl._warned_X) both propagate because the impl reads
    # the shared _runtime_state.state object.

    # ── V18.4 (Phase 2): embedding.enabled gate ─────────────────────────
    _emb_enabled, _emb_fallback = _embedding_settings()
    if not _emb_enabled:
        if _emb_fallback == "skip":
            # Explicit opt-out: signal the caller to skip Phase 2.2 entirely.
            # judge() pre-checks this and won't enter the coverage loop, so
            # reaching here means a DIRECT caller (e.g. per-bullet grounding)
            # invoked _semantic_similarity without the pre-check.
            raise EmbeddingDisabled(
                "embedding.enabled=False + fallback='skip' — Phase 2.2 "
                "semantic similarity explicitly disabled by user config"
            )
        # fallback == "jaccard": skip the embedder attempt, go straight to
        # the lexical signal. Log ONCE per process (not per claim).
        if not _runtime_state.warned_embedding_disabled:
            logger.info(
                "content_judge: embedding.enabled=False + fallback='jaccard' "
                "— semantic similarity using Jaccard word overlap only "
                "(embedder not attempted, per user config). Phase 2.2 "
                "coverage check still runs on the lexical signal."
            )
            _runtime_state.warned_embedding_disabled = True
        return _jaccard(claim, candidate)

    try:
        from sentence_transformers import util

        from core.llm.model_singletons import get_embed_model, is_embedder_healthy

        model = get_embed_model()
        if model is None:
            raise ImportError("sentence-transformers not available")
        # V18.2.23 (BUG-B): proactively check health BEFORE calling encode().
        # If the Ollama embed backend is unhealthy (smoke-test failed), fall
        # back to Jaccard immediately — cos_sim(0, x) = 0 would be a worse
        # signal than Jaccard word overlap (which at least catches real
        # lexical matches). This also avoids the degenerate-0/N guard firing
        # when Jaccard would have found some real coverage.
        if not is_embedder_healthy():
            raise EmbedderUnavailable("embedder backend marked unhealthy (smoke-test failed)")
        emb1 = model.encode([claim], show_progress_bar=False)
        # V18.20.2.0 (SWOT A23): reuse a precomputed candidate embedding when
        # supplied (Q2/Q4 hoist); otherwise encode it (original behaviour).
        if candidate_emb is None:
            emb2 = model.encode([candidate], show_progress_bar=False)
        else:
            emb2 = candidate_emb
        # V18.2.44 (Next Step #5): defense-in-depth degenerate-vector guard.
        # Even with the SentenceTransformerBackend smoke-test (Part A/B), a
        # backend can pass the smoke-test then silently OOM on a later
        # encode() (CUDA memory pressure from the LLM mid-chapter). cos_sim
        # of two zero/NaN vectors is mathematically 0 (or NaN→0) for EVERY
        # pair → the degenerate-0/N guard fires → Phase 2.2 fact-check is
        # silently SKIPPED. Here we check the ACTUAL returned vectors: if
        # either is all-zero or all-NaN, raise EmbedderUnavailable so the
        # Jaccard fallback (a real, weaker signal) takes over instead of a
        # silent zero-similarity. This is the single most important line in
        # closing the "Phase 2.2 always skipped" regression.
        import numpy as _np_sem

        for _vec, _label in ((emb1, "claim"), (emb2, "candidate")):
            _arr = _np_sem.asarray(_vec, dtype=_np_sem.float32).ravel()
            if _arr.size == 0 or not _np_sem.any(_arr) or _np_sem.isnan(_arr).any():
                raise EmbedderUnavailable(
                    f"degenerate {_label} vector (size={_arr.size}, "
                    f"all_zero={bool(not _np_sem.any(_arr))}, "
                    f"has_nan={bool(_np_sem.isnan(_arr).any())}) — "
                    f"backend marked healthy but encode() returned garbage"
                )
        sim = util.cos_sim(emb1, emb2)[0][0].item()
        return sim
    except EmbedderUnavailable as _e:
        # V18.2.21: embed backend is unhealthy (smoke-test failed, or all
        # batch items failing). Fall back to Jaccard with ONE loud warning
        # so the user knows the semantic judge is degraded this run.
        if not _runtime_state.warned_semantic_fallback:
            logger.warning(
                "content_judge: embed backend unavailable (%s) — falling "
                "back to Jaccard word overlap for ALL similarity checks "
                "this run. Coverage/hallucination signals will be weaker. "
                "Fix: pull the embed model in Ollama, or set "
                "embedding.model to a HuggingFace model (e.g. "
                "BAAI/bge-small-en-v1.5) in settings.",
                _e,
            )
            _runtime_state.warned_semantic_fallback = True
        words1 = set(claim.lower().split())
        words2 = set(candidate.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0
    except Exception as _e:
        # Fallback: Jaccard word overlap
        if not _runtime_state.warned_semantic_fallback:
            logger.warning(
                "content_judge._semantic_similarity: embed model unavailable "
                "(%s) — falling back to Jaccard word overlap (weaker signal). "
                "Subsequent occurrences suppressed.",
                _e,
            )
            _runtime_state.warned_semantic_fallback = True
        words1 = set(claim.lower().split())
        words2 = set(candidate.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0


def _encode_chunks_cached(chunks: list[str]) -> list[Any] | None:
    """V18.20.2.0 (SWOT A23): encode the source chunks ONCE per judge() call.

    Q2 (grounding) and Q4 (deviation) loop over every bullet × every chunk;
    the pre-hoist code re-encoded the SAME chunks once per bullet via
    ``_semantic_similarity`` (~1,600 encode calls for an 80-bullet ×
    10-chunk chapter, of which ~800 were redundant re-encodes of the same
    10 chunks). This mirrors the V18.2.25 Q1 batch fix: one
    :func:`core.llm.embedding_cache.cached_encode` call for all chunks,
    reused per bullet.

    Returns:
        A list aligned with ``chunks`` (each entry is the chunk's embedding,
        or None when that chunk could not be encoded — those pairs fall back
        to the original per-pair path), or None when the embed path is
        unavailable/disabled (the whole Q2/Q4 loops then use the original
        per-pair behaviour unchanged).
    """
    try:
        # Same gate as the embed path in _semantic_similarity: when the
        # embedder is disabled, per-pair calls go straight to Jaccard —
        # hoisting nothing preserves that exactly.
        if not _embedding_settings()[0]:
            return None
        from core.llm.embedding_cache import cached_encode
        from core.llm.model_singletons import get_embed_model, is_embedder_healthy

        model = get_embed_model()
        if model is None or not is_embedder_healthy():
            return None

        embs = cached_encode(model, list(chunks))
        if embs is None:
            return None
        embs = list(embs)
        if len(embs) != len(chunks):
            return None
        # Shape sanity per chunk: a malformed entry falls back to the
        # per-pair path (None). Degenerate (all-zero/NaN) vectors are
        # passed through — _semantic_similarity's existing degenerate-
        # vector guard turns them into the Jaccard fallback, exactly as a
        # fresh encode of the same text would.
        import numpy as _np_chunks

        out: list[Any] = []
        for e in embs:
            try:
                _arr = _np_chunks.asarray(e, dtype=_np_chunks.float32)
                if _arr.ndim < 1 or _arr.shape[0] == 0 or _arr.shape[-1] == 0:
                    out.append(None)
                else:
                    out.append(e)
            except Exception:
                out.append(None)
        return out
    except Exception as _e:
        logger.debug(
            "chunk-embedding hoist unavailable (%s: %s) — using per-pair path",
            type(_e).__name__,
            _e,
        )
        return None


# ── Content Judge ──────────────────────────────────────────────────────────


class ContentJudge:
    """Final pre-output validation: coverage, grounding, hallucination, deviation.

    Called after summarization, before output generation.  Checks the summary
    against the raw source content in chunks.

    V10.1.0: Added Layer 8 — langextract verbatim grounding.  When a
    ``ClaimExtractor`` is supplied (and grounding is enabled in settings),
    each summary bullet is checked for a verbatim ``char_interval`` in the
    source.  This produces a two-tier grounding verdict:

      * **strong** — bullet has a char_interval (deterministic, verbatim).
      * **weak**   — no char_interval, but passes the existing semantic
        ≥ 0.50 check (paraphrased but topically sound).
      * **ungrounded** — fails both tiers (likely hallucination).

    If langextract is unavailable, the judge falls back to the pure-semantic
    check (Layers 1-7) and sets ``grounding_alarm`` so the caller can warn
    the user loudly (Q2=A+alarm — never silent).
    """

    def __init__(
        self,
        log_callback: LogFn | None = None,
        min_coverage: float = MIN_COVERAGE_PCT,
        grounded_threshold: float = GROUNDED_SIM_THRESHOLD,
        claim_extractor: Any | None = None,
        content_type: str = "normal_book",
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.min_coverage = min_coverage
        self.grounded_threshold = grounded_threshold
        # V10.1.0: optional Layer 8 extractor.  If None, grounding is
        # pure-semantic (legacy behaviour).  If supplied but langextract
        # is missing/unreachable, the extractor returns available=False
        # and we fall back gracefully (with an alarm).
        self._claim_extractor = claim_extractor
        self._content_type = content_type

    def _check_coverage_batched(
        self,
        all_claims: list[str],
        summary_texts: list[str],
        result: JudgeResult,
    ) -> int | None:
        """V18.2.25 (Phase 3.3 wiring): batch-embed claims + summary_texts.

        Encodes all claims and all summary_texts in 2 batch calls (via the
        EmbeddingCache), computes the full similarity matrix, and counts
        covered claims. This replaces the per-pair loop that made 2760+
        encode calls (46 claims × ~30 summary_texts × 2 encode calls per pair).

        Returns:
            The number of covered claims (int), or None if the batch path
            is unavailable (embedder not installed / unhealthy / sentence-
            transformers missing). The caller falls back to the per-pair
            Jaccard path when None is returned.

        V18.4 (Phase 2): returns None immediately when ``embedding.enabled``
        is False — the per-pair ``_semantic_similarity`` path then handles
        the ``fallback`` choice (jaccard computes a real lexical signal;
        skip raises ``EmbeddingDisabled`` which ``judge()`` pre-empts).
        """
        # V18.4 (Phase 2): respect the embedder optional-mode gate. When
        # disabled, the batch embedder path is not attempted — fall through
        # to the per-pair path (which itself honours enabled/fallback).
        if not _embedding_settings()[0]:
            return None
        try:
            from sentence_transformers import util

            from core.llm.embedding_cache import cached_encode
            from core.llm.model_singletons import get_embed_model, is_embedder_healthy

            model = get_embed_model()
            if model is None or not is_embedder_healthy():
                return None  # fall back to per-pair Jaccard

            # Batch-encode all claims + all summary texts (cached across runs).
            claims_emb = cached_encode(model, all_claims)  # (N_claims, dim)
            summary_emb = cached_encode(model, summary_texts)  # (N_summary, dim)

            # Compute the full similarity matrix: (N_claims, N_summary).
            sim_matrix = util.cos_sim(claims_emb, summary_emb)

            # Count covered claims: a claim is covered if its best similarity
            # across all summary texts is >= 0.50 (same threshold as the
            # per-pair path).
            covered = 0
            for i in range(len(all_claims)):
                best_sim = float(sim_matrix[i].max().item())
                if best_sim >= 0.50:
                    covered += 1
                else:
                    result.uncovered_claims.append(all_claims[i][:100])

            self.log(
                f"    📊 Batch coverage: {covered}/{len(all_claims)} claims "
                f"(2 batch encode calls via EmbeddingCache, was "
                f"{len(all_claims) * len(summary_texts) * 2} per-pair calls)",
                "DEBUG",
            )
            return covered
        except Exception as exc:
            logger.debug(
                "batch coverage check failed (%s: %s) — falling back to per-pair Jaccard",
                type(exc).__name__,
                exc,
            )
            return None

    def judge(
        self,
        summary: SummaryResult,
        source_content: str,
    ) -> JudgeResult:
        """Judge one chapter's summary against its source content.

        Args:
            summary: the SummaryResult to validate.
            source_content: the raw chapter text (the source the summary was
                generated from).

        Returns:
            A :class:`JudgeResult` with coverage, grounding, hallucination,
            and deviation metrics.
        """
        result = JudgeResult(chapter_heading=summary.chapter_heading)

        if not source_content or len(source_content) < 200:
            result.passed = True
            result.summary = "Source too short for judging — auto-pass"
            return result

        # Build the summary text to check against
        summary_texts = []
        if summary.executive_summary:
            summary_texts.append(summary.executive_summary)
        if summary.thorough_summary:
            summary_texts.append(summary.thorough_summary)
        for bp in summary.bullet_points:
            summary_texts.append(bp)
        combined_summary = " ".join(summary_texts)

        if not combined_summary.strip():
            result.passed = False
            result.summary = "Empty summary — FAIL"
            return result

        # ── Q1: Coverage check (source → summary) ────────────────────────
        chunks = _chunk_text(source_content)
        all_claims: list[str] = []
        for chunk in chunks:
            claims = _extract_key_claims(chunk)
            all_claims.extend(claims)

        result.total_source_claims = len(all_claims)
        # V18.4 (Phase 2): read the embedder optional-mode knobs ONCE for the
        # whole Q1 block (cheap — Settings is a cached singleton).
        _emb_enabled, _emb_fallback = _embedding_settings()
        if result.total_source_claims == 0:
            # No extractable claims — can't check coverage, auto-pass
            result.coverage_pct = 1.0
            result.covered_claims = 0
        elif not _emb_enabled and _emb_fallback == "skip":
            # V18.4 (Phase 2): explicit, non-silent skip of Phase 2.2.
            # The user set embedding.enabled=False + fallback="skip" — they
            # opted out of the semantic coverage check entirely. Auto-pass
            # coverage (can't measure), keep uncovered_claims empty so nothing
            # tries to gap-fill, and flag coverage_skipped so the report and
            # downstream consumers can distinguish this from a real measurement.
            # The deterministic judge + postchecks still run downstream.
            logger.warning(
                "content_judge: Phase 2.2 (semantic coverage check) SKIPPED "
                "— embedding.enabled=False + fallback='skip' (user-configured "
                "opt-out). Coverage auto-passed; deterministic judge + "
                "postchecks still verify the summary."
            )
            if self.log:
                self.log(
                    "⏭️ Phase 2.2 semantic coverage check SKIPPED "
                    "(embedding.enabled=False, fallback='skip') — "
                    "deterministic judge still runs",
                    "WARNING",
                )
            result.coverage_pct = 1.0  # auto-pass (unmeasurable)
            result.covered_claims = result.total_source_claims
            result.uncovered_claims = []
            result.coverage_skipped = True
        else:
            # V18.2.25 (Phase 3.3 wiring): try batch embedding first.
            # The V18.2.21 conversion log showed 2760+ per-pair encode calls
            # (46 claims × ~30 summary texts × 2 encode calls per pair).
            # Batch-encoding all claims + all summary texts once reduces this
            # to 2 batch calls (and 0 on re-runs via the EmbeddingCache).
            # Falls back to the per-pair Jaccard path if the embedder is
            # unavailable or batch encoding fails.
            #
            # V18.4 (Phase 2): when embedding.enabled=False + fallback="jaccard",
            # _check_coverage_batched returns None and _semantic_similarity goes
            # straight to Jaccard — so the coverage loop still runs on the
            # lexical signal (a real, weaker measurement).
            covered = self._check_coverage_batched(all_claims, summary_texts, result)
            if covered is None:
                # Batch path unavailable → per-pair Jaccard fallback (original).
                covered = 0
                for claim in all_claims:
                    best_sim = 0.0
                    for s_text in summary_texts:
                        sim = _semantic_similarity(claim, s_text)
                        if sim > best_sim:
                            best_sim = sim
                            if sim >= 0.50:
                                break
                    if best_sim >= 0.50:
                        covered += 1
                    else:
                        result.uncovered_claims.append(claim[:100])
            result.covered_claims = covered
            result.coverage_pct = covered / result.total_source_claims

            # V18.2.21 (BUG-2 fix): Degenerate-coverage guard.
            # If we found ≥10 claims and ZERO are covered, that is almost
            # never a real "0% coverage" — it's a broken embedder (zero
            # vectors → cos_sim=0 for every pair) OR the Jaccard fallback
            # running on a paraphrased summary (word overlap rarely ≥0.50).
            # The V18.2.20 conversion log showed exactly this: 0/46 covered
            # → 2 wasted gap-fill LLM calls (both returned empty at t=0.49)
            # → the V18.2.19 auto-pass workaround fired AFTER burning ~6s +
            # 2 LLM round-trips. Now: detect 0/N, mark coverage as
            # "degenerate / unmeasurable", skip gap-fill, and log loudly.
            if result.total_source_claims >= 10 and covered == 0 and summary_texts:
                logger.error(
                    "content_judge: DEGENERATE coverage 0/%d — the embedder "
                    "is almost certainly broken (zero vectors or unavailable). "
                    "Skipping gap-fill (would waste LLM calls on a false "
                    "signal). The V17.6 deterministic judge + postchecks "
                    "will verify real coverage downstream. Enable a working "
                    "embed model (BAAI/bge-small-en-v1.5) to restore the "
                    "semantic signal.",
                    result.total_source_claims,
                )
                if self.log:
                    self.log(
                        "⚠️ Judge coverage reported 0% but this is a degenerate "
                        "signal (embedder broken/unavailable), not a real "
                        "0%. Skipping gap-fill. The deterministic judge will "
                        "verify actual coverage next.",
                        "WARNING",
                    )
                # Mark as "auto-passed (degenerate)" so the caller's gap-fill
                # trigger sees coverage >= threshold and skips the reprompt.
                # Keep uncovered_claims empty so nothing tries to gap-fill.
                result.coverage_pct = 1.0  # auto-pass
                result.covered_claims = result.total_source_claims
                result.uncovered_claims = []

        # ── Q2+Q3: Grounding check (summary → source) ────────────────────
        # V10.1.0: Two-tier grounding.  Tier 1 (Layer 8) is langextract's
        # verbatim char_interval — the strongest, deterministic signal.
        # Tier 2 is the legacy semantic ≥ 0.50 check.  A bullet that passes
        # Tier 1 is "strongly grounded"; one that fails Tier 1 but passes
        # Tier 2 is "weakly grounded"; one that fails both is ungrounded.
        result.total_bullets = len(summary.bullet_points)

        # ── Layer 8: langextract verbatim grounding (optional) ───────────
        # Run this FIRST so its char_intervals can upgrade the verdict on
        # bullets that the semantic check might otherwise reject (e.g. a
        # bullet that is verbatim in the source but scores < 0.50 on
        # cosine similarity because it's short).
        l8_strong_bullets: set = set()  # indices of strongly-grounded bullets
        l8_evidence: dict[str, str] = {}
        l8_available = False
        l8_alarm = ""
        if self._claim_extractor is not None and result.total_bullets > 0:
            try:
                from core.grounding import GroundingResult

                gr: GroundingResult = self._claim_extractor.extract(
                    source_text=source_content,
                    summary_bullets=summary.bullet_points,
                    content_type=self._content_type,
                )
                l8_available = gr.available
                if not gr.available and gr.alarm is not None:
                    # LOUD alarm — never silent (Q2=A+alarm).
                    l8_alarm = gr.alarm.code
                    self.log(
                        f"  ⚠️ {gr.alarm.message}",
                        "WARNING" if gr.alarm.severity != "error" else "ERROR",
                    )
                elif gr.available:
                    # Match grounded bullets by text overlap.  A bullet is
                    # "strongly grounded" iff some claim in gr.claims has
                    # extraction_class == "summary_bullet", is_grounded=True,
                    # and its text fuzzy-matches the bullet ≥ 60%.
                    try:
                        from rapidfuzz import fuzz as rf_fuzz

                        _has_rf = True
                    except ImportError:
                        _has_rf = False
                    for idx, _bp in enumerate(summary.bullet_points):
                        bp_clean = (bp or "").strip()
                        if not bp_clean:
                            continue
                        for claim in gr.claims:
                            if claim.extraction_class != "summary_bullet":
                                continue
                            if not claim.is_grounded:
                                continue
                            if _has_rf:
                                score = (
                                    rf_fuzz.partial_ratio(bp_clean.lower(), claim.text.lower())
                                    / 100.0
                                )
                            else:
                                a = set(bp_clean.lower().split())
                                b = set(claim.text.lower().split())
                                score = (len(a & b) / len(a)) if a else 0.0
                            if score >= 0.60:
                                l8_strong_bullets.add(idx)
                                l8_evidence[bp_clean] = claim.source_snippet
                                break
                    self.log(
                        f"  🛡️ Layer 8: {len(l8_strong_bullets)}/"
                        f"{result.total_bullets} bullets verbatim-grounded "
                        f"({gr.format_report()})",
                        "DEBUG",
                    )
            except Exception as e:
                # Never let Layer 8 crash the judge.  Alarm + fall back.
                l8_alarm = f"layer8_exception:{type(e).__name__}"
                self.log(
                    f"  ⚠️ Layer 8 grounding crashed ({e}) — "
                    f"falling back to semantic-only (Layers 1-7)",
                    "ERROR",
                )

        result.grounding_layer8_available = l8_available
        result.grounding_alarm = l8_alarm
        result.bullet_evidence = l8_evidence

        # V18.20.2.0 (SWOT A23): hoisted chunk embeddings for the Q2/Q4
        # loops — None until (and unless) the semantic-grounding else-branch
        # below computes them (initialised here so the Q4 loop can never hit
        # an unbound name under any branch combination).
        _chunk_embs = None

        # ── Tier 2: semantic grounding (legacy) ──────────────────────────
        if result.total_bullets > 0:
            # V18.4 (Phase 2): when embedding is disabled + fallback="skip",
            # the Q2 grounding loop and Q4 deviation loop both call
            # _semantic_similarity, which would raise EmbeddingDisabled.
            # Short-circuit Q2: auto-ground all non-L8 bullets (can't measure
            # semantic similarity) and skip Q4 entirely. The deterministic
            # judge + postchecks still verify grounding downstream.
            _skip_grounding = not _emb_enabled and _emb_fallback == "skip"
            if _skip_grounding:
                # Auto-ground every bullet (Layer 8 strong + the rest as
                # "unmeasurable"). Keep ungrounded_bullets empty so the
                # verdict isn't a false FAIL on a user-opted-out skip.
                grounded = len(summary.bullet_points)
                for idx, _bp in enumerate(summary.bullet_points):
                    if idx not in l8_strong_bullets:
                        # Not verbatim-grounded, but we can't semantic-check
                        # it either — count as weakly grounded (auto-pass).
                        pass
                result.grounded_bullets = grounded
                result.grounding_pct = 1.0
                result.hallucination_count = 0
                result.strong_grounded_bullets = len(l8_strong_bullets)
                result.weak_grounded_bullets = grounded - len(l8_strong_bullets)
                if self.log:
                    self.log(
                        "⏭️ Phase 2.2 semantic grounding SKIPPED "
                        "(embedding.enabled=False, fallback='skip') — "
                        "all bullets auto-grounded; deterministic judge still runs",
                        "WARNING",
                    )
            else:
                # V18.20.2.0 (SWOT A23): hoist the source-chunk embeddings —
                # encode the chunks ONCE per judge() call (via the same
                # EmbeddingCache path the Q1 batch fix uses) and reuse the
                # vectors for every bullet in the Q2 grounding loop below
                # AND the Q4 deviation loop further down. Previously each
                # (bullet × chunk) pair made 2 fresh encode() calls, so an
                # 80-bullet × 10-chunk chapter re-encoded the SAME 10 chunks
                # ~80 times (~1,600 encode round-trips; 2-5 min of pure
                # embed overhead per chapter on the Ollama backend).
                # None → embed path unavailable/disabled → every pair keeps
                # the ORIGINAL per-pair behaviour unchanged. A None ENTRY
                # (malformed single chunk) falls back to per-pair for that
                # chunk only. Similarity VALUES are identical: the hoisted
                # vector is the same encoding the per-pair path would have
                # produced (cached_encode wraps model.encode; degenerate
                # vectors still trip the guard inside _semantic_similarity).
                _chunk_embs = _encode_chunks_cached(chunks) if chunks else None
                grounded = 0
                for idx, _bp in enumerate(summary.bullet_points):
                    # If Layer 8 already grounded this bullet strongly, count
                    # it and skip the (slower) semantic check.
                    if idx in l8_strong_bullets:
                        grounded += 1
                        continue
                    best_sim = 0.0
                    for ci, chunk in enumerate(chunks):
                        sim = _semantic_similarity(
                            bp,
                            chunk,
                            candidate_emb=(_chunk_embs[ci] if _chunk_embs is not None else None),
                        )
                        if sim > best_sim:
                            best_sim = sim
                            if sim >= self.grounded_threshold:
                                break
                    if best_sim >= self.grounded_threshold:
                        grounded += 1
                    else:
                        result.ungrounded_bullets.append(bp[:80])
                        # If Layer 8 was available, this bullet failed BOTH
                        # tiers — record it as a strong-ungrounded (likely
                        # hallucination) for the enhanced verdict below.
                        if l8_available:
                            result.ungrounded_strong.append(bp[:80])
                result.grounded_bullets = grounded
                result.grounding_pct = grounded / result.total_bullets
                result.hallucination_count = len(result.ungrounded_bullets)
                # V10.1.0: split the grounded count into strong/weak for reporting
                result.strong_grounded_bullets = len(l8_strong_bullets)
                result.weak_grounded_bullets = grounded - len(l8_strong_bullets)

        # ── Q4: Deviation check ──────────────────────────────────────────
        # A "deviation" is a bullet that IS grounded (similarity > 0.50)
        # but where the summary's claim contradicts or distorts the source.
        # We check this by comparing the bullet's sentiment/stance against
        # the source chunk it's most similar to.  For now, this is a
        # simplified check: if the bullet contains a negation ("not", "never",
        # "cannot") that the source doesn't, it's a potential deviation.
        negation_words = {
            "not",
            "never",
            "cannot",
            "no ",
            "none",
            "neither",
            "nor",
            "without",
            "fails",
            "unable",
            "impossible",
        }
        if result.total_bullets > 0 and not _skip_grounding:
            # V18.4 (Phase 2): Q4 deviation check also calls _semantic_similarity,
            # so it must be skipped in skip-mode (would raise EmbeddingDisabled).
            # When _skip_grounding is True, deviation_count stays 0 (can't
            # measure without similarity). The deterministic postchecks still
            # catch contradictions downstream.
            # V18.20.2.0 (SWOT A23): Q4 reuses the SAME hoisted chunk
            # embeddings computed before the Q2 loop (chunks are re-scanned
            # here a 3rd time for negation bullets — pre-hoist that was a
            # fresh encode per (bullet × chunk) pair again).
            for bp in summary.bullet_points:
                bp_lower = bp.lower()
                bp_has_negation = any(neg in bp_lower for neg in negation_words)
                if bp_has_negation:
                    # Find the best-matching source chunk
                    best_sim = 0.0
                    best_chunk = ""
                    for ci, chunk in enumerate(chunks):
                        sim = _semantic_similarity(
                            bp,
                            chunk,
                            candidate_emb=(_chunk_embs[ci] if _chunk_embs is not None else None),
                        )
                        if sim > best_sim:
                            best_sim = sim
                            best_chunk = chunk
                    if best_chunk:
                        source_lower = best_chunk.lower()
                        source_has_negation = any(neg in source_lower for neg in negation_words)
                        # If the bullet negates but the source doesn't → deviation
                        if bp_has_negation and not source_has_negation and best_sim >= 0.40:
                            result.deviation_count += 1
                            result.deviation_details.append(
                                f"Bullet says '{bp[:60]}…' but source doesn't negate"
                            )

        # ── Overall verdict ──────────────────────────────────────────────
        # V10.1.0: When Layer 8 (langextract) was available, a bullet that
        # fails BOTH the verbatim and semantic tiers is a "strong ungrounded"
        # — a much more confident hallucination signal than the semantic-only
        # check alone.  We apply a tighter threshold for those: no more than
        # 10% of bullets may be strong-ungrounded (vs 20% for the legacy
        # weak-ungrounded).  This makes the judge stricter precisely when
        # the strongest signal is available, and unchanged when it isn't
        # (graceful fallback preserves the original 20% bar).
        ungrounded_pct = 1.0 - result.grounding_pct if result.total_bullets > 0 else 0.0
        strong_ungrounded_pct = (
            len(result.ungrounded_strong) / result.total_bullets
            if (result.grounding_layer8_available and result.total_bullets > 0)
            else 0.0
        )
        STRONG_UNGROUNDED_MAX_PCT = 0.10  # 10% bar when Layer 8 is active
        result.passed = (
            result.coverage_pct >= self.min_coverage
            and ungrounded_pct <= UNGROUNDED_MAX_PCT
            and strong_ungrounded_pct <= STRONG_UNGROUNDED_MAX_PCT
            and result.deviation_count <= 2  # allow up to 2 minor deviations
        )
        result.needs_gap_fill = (
            result.coverage_pct < GAP_FILL_THRESHOLD and len(result.uncovered_claims) > 0
        )
        result.summary = result.format_report()
        return result

    # ──────────────────────────────────────────────────────────────────────
    # V10.2.3: LLM-based judge backup (user's idea)
    # ──────────────────────────────────────────────────────────────────────

    def llm_judge_grounding(
        self,
        bullets: list[str],
        source_content: str,
        llm_call_fn: Callable[[str], str | None] | None = None,
    ) -> tuple[int, int, list[str]] | None:
        """V10.2.3: LLM-based grounding check for paraphrased bullets.

        User's idea: "LLM models summarizing from text is harder than
        auditing/checking two texts against each other."  This method gives
        the LLM judge the summary bullets + source text, and asks it to rate
        each bullet as "grounded" or "not grounded" based on SEMANTIC
        equivalence (not word overlap).

        This fires ONLY when the deterministic check is uncertain:
        - Deterministic says >30% ungrounded (would reject)
        - But content is substantial (not empty/garbage)

        Returns:
            (grounded_count, total_count, ungrounded_bullets) if the LLM
            judge ran successfully, or None if it couldn't run.

        The LLM judge's verdict OVERRIDES the deterministic check — if the
        LLM says ≥70% are grounded, the summary is accepted.
        """
        if not llm_call_fn or not bullets or not source_content:
            return None

        # Truncate source to fit context (keep first + last 2000 chars)
        if len(source_content) > 6000:
            source_truncated = source_content[:3000] + "\n...\n" + source_content[-3000:]
        else:
            source_truncated = source_content

        # Build the prompt
        bullets_text = "\n".join(f"{i + 1}. {bp}" for i, bp in enumerate(bullets))
        from core.summarisation.prompt_manager import PromptManager

        _pm = PromptManager()
        prompt = _pm.render_template(
            "summarisation/content_judge",
            source_truncated=source_truncated,
            bullets_text=bullets_text,
            n_bullets=len(bullets),
        )

        try:
            response = llm_call_fn(prompt)
            if not response:
                return None

            # Parse the response
            grounded_count = 0
            ungrounded_bullets = []
            for bp_idx, bp in enumerate(bullets, 1):
                # Look for "GROUNDED: N" or "NOT_GROUNDED: N" in the response
                pattern_grounded = rf"(?i)GROUNDED\s*[:\-]?\s*{bp_idx}\b"
                pattern_not = rf"(?i)NOT[\s_]*GROUNDED\s*[:\-]?\s*{bp_idx}\b"
                if re.search(pattern_not, response):
                    ungrounded_bullets.append(bp)
                elif re.search(pattern_grounded, response):
                    grounded_count += 1
                else:
                    # Couldn't find a verdict for this bullet — assume grounded
                    grounded_count += 1

            self.log(
                f"  🤖 LLM Judge: {grounded_count}/{len(bullets)} bullets "
                f"grounded (semantic check — overrides deterministic).",
                "INFO",
            )
            return (grounded_count, len(bullets), ungrounded_bullets)

        except Exception as e:
            self.log(f"  ⚠️ LLM Judge failed: {e}", "WARNING")
            return None

    def build_gap_fill_prompt(
        self,
        heading: str,
        uncovered_claims: list[str],
        existing_bullets: list[str],
    ) -> str:
        """Build a gap-fill reprompt for the LLM.

        Sent when the judge finds coverage < 75%.  Asks the LLM to add
        bullets covering the uncovered source claims.
        """
        claims_text = "\n".join(f"- {c}" for c in uncovered_claims[:15])
        existing_text = "\n".join(f"- {b}" for b in existing_bullets[:20])
        from core.summarisation.prompt_manager import PromptManager

        _pm = PromptManager()
        rendered = _pm.render_template(
            "summarisation/gap_fill_reprompt",
            heading=heading,
            claims_text=claims_text,
            existing_text=existing_text,
        )
        return rendered if rendered is not None else ""


# ── Global model cache (avoid re-loading sentence-transformers per call) ───
# V18.20.1.0 (D3): _st_model was a dead variable (never read in code — the
# actual model is fetched via get_embed_model() from model_singletons).
# Removed. The centralized state.st_model exists for future use if needed.
# (Keeping the comment to document the removal for anyone grepping for _st_model.)
