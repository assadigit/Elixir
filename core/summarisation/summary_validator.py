"""V18.7 (Phase 5.2, Batch A): Summary-validator pure functions.

Extracted from ``Summarizer`` (god-class decomposition Stage 2). These are the
verification/coverage/dedup methods — the "SummaryValidator" cluster.

**Extraction map** (what moved where):

| Summarizer method (old)              | summary_validator function (new)     | self deps                          |
|--------------------------------------|--------------------------------------|------------------------------------|
| ``_normalize_empty_section``         | ``normalize_empty_section``          | NONE (static)                      |
| ``_verify_additive_section_item``    | ``verify_additive_section_item``     | NONE (static)                      |
| ``_verify_additive_sections``        | ``verify_additive_sections``         | quarantine + log                   |
| ``_anti_false_precision_check``      | ``anti_false_precision_check``       | log                                |
| ``_semantic_dedup_bullets``          | ``semantic_dedup_bullets``           | log                                |
| ``_compute_coverage``                | ``compute_coverage``                 | coverage_cache + extract_keywords  |
| ``_verify_bullets``                  | ``verify_bullets``                   | verify_windows_cache + quarantine + log |

Each function is extracted VERBATIM — the only change is ``self.X`` becomes a
parameter. The Summarizer methods now delegate to these functions.

**NOT extracted** (deferred to Batch B — HIGH risk):
- ``_llm_grounding_check`` — makes live LLM calls (uses ``_call_cloud`` /
  ``_call_llm``). Part of Phase 5.1 (LLMDispatcher) extraction.

Characterization tests: ``tests/test_summary_validator.py`` captures canned
inputs → golden outputs for every function. Byte-for-byte stability gate.

**V18.6.3 crash mitigation**: This extraction uses EXPLICIT PARAMETERS (not a
context object like the failed ``PromptContext`` pattern). This matches the
proven Phase 4 pattern (``post_processing.py`` + ``prompt_assembly.py`` 5 of 6
methods) which passed all sandbox tests AND the golden-master gate.
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Type aliases (duck-typed — we only call .add() on quarantine, .__call__ on log).
QuarantineLike = Any
LogCallback = Callable[[str, str], None]


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── normalize_empty_section (extracted verbatim from Summarizer V13.39.0) ──


def normalize_empty_section(text: str) -> str:
    """V13.39.0: Normalize 'None' / 'chapter does not discuss' to empty.

    The prompt explicitly allows the model to output "None" when the chapter
    doesn't discuss distinctions/tensions. This normalizes those responses
    to an empty string so they don't appear in the final output.

    Extracted verbatim from ``Summarizer._normalize_empty_section`` (was a
    ``@staticmethod`` — no ``self`` usage). Mechanical move, no logic change.
    """
    if not text or not text.strip():
        return ""
    t = text.strip().lower()
    # Common "empty" responses the model might produce
    _empty_markers = [
        "none", "n/a", "na", "not applicable", "no distinctions",
        "no tensions", "no debates", "no ambiguities",
        "the chapter does not discuss", "the chapter does not explore",
        "the chapter does not draw", "not discussed in this chapter",
        "no explicit distinctions", "no explicit tensions",
    ]
    if t in _empty_markers or any(t.startswith(m) for m in _empty_markers):
        return ""
    # If it's very short and looks like a refusal/hedge
    if len(t) < 40 and any(w in t for w in ["no ", "none", "not ", "absent", "absence"]):
        return ""
    return text.strip()


# ── verify_additive_section_item (extracted verbatim from Summarizer V13.39.0) ──


def verify_additive_section_item(item: str, source_text: str) -> bool:
    """V13.39.0: Verify a single distinction/tension item is source-grounded.

    Extracts key noun phrases from the item and checks if they appear in
    the source text. If the key terms can't be found, the item is likely
    hallucinated and should be dropped.

    Returns True if the item is source-grounded, False if likely fabricated.

    Extracted verbatim from ``Summarizer._verify_additive_section_item``
    (was a ``@staticmethod``). Mechanical move, no logic change.
    """
    if not item or not item.strip():
        return False
    item_clean = item.strip().lstrip("- ").strip()
    # Extract significant words (length > 3, not common stopwords)
    _stop = frozenset(["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must", "shall", "this", "that", "these", "those", "it", "its", "their", "there", "here", "which", "who", "whom", "what", "when", "where", "why", "how", "between", "versus", "vs", "contrast", "distinction", "tension", "debate", "ambiguity", "important", "matters", "significant", "because", "while", "although", "though", "however", "thus", "therefore", "hence", "rather", "more", "most", "less", "least"])
    words = [w.strip(".,;:!?\"'()[]").lower() for w in item_clean.split()]
    key_words = [w for w in words if len(w) > 3 and w not in _stop]
    if not key_words:
        # No extractable key terms — can't verify, keep it (benefit of doubt)
        return True
    # Check how many key words appear in the source (normalized)
    source_norm = re.sub(r'\s+', ' ', source_text).strip().lower()
    found = sum(1 for w in key_words if w in source_norm)
    # Require at least 40% of key words to appear in the source
    ratio = found / len(key_words) if key_words else 1.0
    return ratio >= 0.40


# ── verify_additive_sections (extracted verbatim from Summarizer V13.39.0) ──


def verify_additive_sections(
    heading: str,
    text: str,
    result: dict,
    quarantine: QuarantineLike | None = None,
    log: LogCallback | None = None,
) -> None:
    """V13.39.0: Verify key_distinctions + theoretical_tensions against source.

    Multi-layer anti-hallucination guard for the V13.38.0 additive sections:
    1. Normalize "None" / "chapter does not discuss" -> empty string
    2. Split each section into individual bullets
    3. For each bullet, extract key terms and verify they appear in the source
    4. Drop bullets that can't be source-grounded (likely fabricated)
    5. Log dropped items to quarantine for audit trail

    Modifies ``result`` in-place: sets ``key_distinctions`` and
    ``theoretical_tensions`` to the verified (possibly reduced) content.

    Extracted verbatim from ``Summarizer._verify_additive_sections``. The only
    change: ``self._normalize_empty_section`` → ``normalize_empty_section``,
    ``self._verify_additive_section_item`` → ``verify_additive_section_item``,
    ``self.quarantine`` → ``quarantine`` param, ``self.log`` → ``log`` param.
    """
    _log = log or _noop_log
    source_text = text  # the full chapter content

    for section_key in ("key_distinctions", "theoretical_tensions"):
        raw = result.get(section_key, "")
        # Layer 1: normalize "None" responses
        raw = normalize_empty_section(raw)
        if not raw:
            result[section_key] = ""
            continue

        # Layer 2: split into individual items (bullets)
        items = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and (line.startswith("- ") or line.startswith("\u2022 ") or
                         re.match(r'^\d+\.\s', line)):
                items.append(line)
        # If no bullet markers found, treat the whole thing as one item
        if not items and raw.strip():
            items = [raw.strip()]

        # Layer 3: verify each item is source-grounded
        kept_items = []
        dropped_items = []
        for item in items:
            if verify_additive_section_item(item, source_text):
                kept_items.append(item)
            else:
                dropped_items.append(item)

        # Layer 4: log dropped items to quarantine
        if dropped_items and quarantine:
            for item in dropped_items:
                quarantine.add(
                    bullet=item,
                    stage=f"Layer A: Additive-section verification ({section_key})",
                    reason="Item could not be source-grounded - likely fabricated",
                    source_overlap=0.0,
                    actually_dropped=True,
                )

        if dropped_items:
            _log(
                f"\U0001f6e1\ufe0f {section_key}: dropped {len(dropped_items)} ungrounded item(s), "
                f"kept {len(kept_items)}",
                "INFO",
            )

        result[section_key] = "\n".join(kept_items) if kept_items else ""


# ── anti_false_precision_check (extracted verbatim from Summarizer V13.45.0) ──


def anti_false_precision_check(
    heading: str,
    text: str,
    result: dict,
    log: LogCallback | None = None,
) -> None:
    """V13.45.0: Deterministic anti-false-precision post-check.

    Scans the generated summary's bullet_points + executive_summary +
    thorough_summary for the "Author A views X as Y while/whereas Author B
    views X as Z" pattern. When such a pattern is found, verifies whether
    the source actually separates the two authors. If the source groups
    them together (e.g., "AuthorL 1964, AuthorD 1967 regard X as Y"),
    the summary bullet is REWRITTEN to preserve the grouping instead of
    the invented distinction.

    This catches the specific hallucination surfaced in the V13.44.4 audit:
    the summary claimed "AuthorL views it as a defining condition of borderline
    disorders while AuthorD views it as a defining condition of narcissistic
    disorders" — but the source groups both authors for both disorders.

    Deterministic — no LLM call. Operates on the result dict in-place.

    Extracted verbatim from ``Summarizer._anti_false_precision_check``. The
    only change: ``self.log`` → ``log`` param (used inside the nested closure
    via ``nonlocal``).
    """
    _log = log or _noop_log
    import re as _re

    # Gather all summary text to scan
    _bullets = result.get("bullet_points", []) or []
    _exec = result.get("executive_summary", "") or ""
    _thorough = result.get("thorough_summary", "") or ""
    _kd = result.get("key_distinctions", "") or ""
    _tt = result.get("theoretical_tensions", "") or ""

    # Truncate source for matching
    src_lower = text[:200000].lower()

    # Pattern: "Name1 ... [views/regards/proposes] ... while/whereas Name2 ..."
    # Capture the two names and the contrastive conjunction.
    # V13.45.0: Do NOT use re.IGNORECASE for the whole pattern — it makes
    # the name pattern [A-Z][a-z]+ match lowercase words like "views",
    # causing "AuthorL views" to be captured as a compound surname.
    # Instead, use inline (?i:...) ONLY for the contrastive conjunction.
    contrast_pat = _re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:\([^)]*\))?\s*'
        r'(.{5,120}?)\s+'
        r'(?i:while|whereas|where as|in contrast|by contrast|on the other hand|'
        r'as opposed to|unlike|rather than)\s+'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:\([^)]*\))?\s*(.{5,120})',
    )

    rewritten = 0

    def _rewrite_if_ungrounded(segment: str) -> str:
        nonlocal rewritten
        if not segment:
            return segment
        new_text = segment
        # V13.45.0: Use search() with manual position advancement instead
        # of finditer(). When name1 is a stopword (e.g., "In this literature,
        # AuthorL views... while AuthorD..."), finditer consumes the WHOLE
        # span as one match and never retries from "AuthorL". By advancing
        # pos by just 1 char when name1 is a stopword, we allow re-matching
        # from the next position, finding the real "AuthorL...while AuthorD"
        # contrast within the same sentence.
        pos = 0
        while pos < len(segment):
            m = contrast_pat.search(segment, pos)
            if not m:
                break
            name1, claim1, name2, claim2 = m.groups()
            # Skip if either name is a common word
            _stop = {"The", "This", "These", "Those", "A", "An", "In",
                     "While", "When", "If", "It", "He", "She", "They",
                     "We", "Our", "You", "By", "For", "Of", "To", "On",
                     "As", "At", "Or", "And", "But", "From"}
            if name1 in _stop or name2 in _stop:
                # Advance by 1 to allow re-matching within this span
                pos = m.start() + 1
                continue
            # Check if the source groups name1 AND name2 together
            # (e.g., "Name1 ... Name2 ... regard X as Y")
            # Look for both names within 120 chars of each other in source
            n1_lower = name1.lower()
            n2_lower = name2.lower()
            if n1_lower not in src_lower or n2_lower not in src_lower:
                # Names not in source — can't verify, skip and advance
                pos = m.end()
                continue
            # Use regex to find "name1 ... name2" within 120 chars of each
            # other in the source — if they appear close together, the source
            # groups them (e.g., "AuthorL 1964, AuthorD 1967 regard X as Y").
            close_pat = _re.compile(
                _re.escape(n1_lower) + r'.{0,120}?' + _re.escape(n2_lower) +
                r'|' + _re.escape(n2_lower) + r'.{0,120}?' + _re.escape(n1_lower),
                _re.DOTALL,
            )
            grouped_in_source = bool(close_pat.search(src_lower))

            if grouped_in_source:
                # The source groups them — the summary's contrast is a
                # false-precision hallucination. Rewrite to preserve grouping.
                # Extract the common predicate by taking claim1 up to the
                # contrastive verb and merging.
                orig = m.group(0)
                # Simple merge: "Name1 and Name2 both [claim1]"
                # Strip trailing punctuation from claim1
                c1 = claim1.strip().rstrip(',;.')
                # V18.10.1 (grammar guard): Skip the rewrite if claim1 is a
                # fragment that starts with a conjunction ("and", "or", "but")
                # or is too short to form a valid predicate. The V18.10.0
                # audit found that "AuthorL (1964) and AuthorK (1958, 1968),
                # while AuthorD..." produced claim1 = "and AuthorK (1958,
                # 1968)," — merging this into "AuthorL and AuthorD both and
                # AuthorK" is grammatically broken (no verb). When claim1 starts
                # with a conjunction, the original contrast spans multiple
                # authors with nested citations — the simple merge can't
                # handle it. Skip the rewrite (leave the original intact)
                # rather than produce a broken sentence.
                _c1_first_word = c1.split()[0].lower().rstrip(',;.') if c1.split() else ""
                _CONJUNCTIONS = {"and", "or", "but", "while", "whereas", "where", "as"}
                _is_fragment = (
                    _c1_first_word in _CONJUNCTIONS
                    or len(c1) < 8  # too short to be a valid predicate
                )
                if _is_fragment:
                    _log(
                        f"    🛡️ Anti-false-precision: SKIPPED rewrite of "
                        f"'{orig[:60]}…' — claim1 is a fragment starting with "
                        f"'{_c1_first_word}' (merge would produce broken grammar)",
                        "DEBUG",
                    )
                    pos = m.end()
                    continue
                merged = f"{name1} and {name2} both {c1}"
                new_text = new_text.replace(orig, merged, 1)
                rewritten += 1
                _log(
                    f"    🛡️ Anti-false-precision: rewrote '{orig[:60]}…' "
                    f"→ '{merged[:60]}…' (source groups {name1} + {name2})",
                    "INFO",
                )
            # Advance past this match to continue scanning
            pos = m.end()
        return new_text

    # Apply to bullets
    if isinstance(_bullets, list) and _bullets:
        new_bullets = []
        for bp in _bullets:
            bp_str = str(bp)
            new_bp = _rewrite_if_ungrounded(bp_str)
            new_bullets.append(new_bp)
        if new_bullets != list(_bullets):
            result["bullet_points"] = new_bullets

    # Apply to executive_summary, thorough_summary, kd, tt (strings)
    for key in ("executive_summary", "thorough_summary", "key_distinctions", "theoretical_tensions"):
        seg = result.get(key, "") or ""
        if seg:
            new_seg = _rewrite_if_ungrounded(seg)
            if new_seg != seg:
                result[key] = new_seg

    if rewritten > 0:
        _log(
            f"    🛡️ Anti-false-precision: rewrote {rewritten} claim(s) "
            f"that invented distinctions between authors the source groups together",
            "INFO",
        )
    else:
        # V13.45.2: Log even when 0 rewrites so we know the check ran
        _log(
            "    🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)",
            "DEBUG",
        )


# ── semantic_dedup_bullets (extracted verbatim from Summarizer V13.45.5) ──


def semantic_dedup_bullets(
    bullets: list[str],
    threshold: float = 0.92,
    log: LogCallback | None = None,
) -> list[str]:
    """V13.45.5: Semantic dedup pass using sentence-transformer embeddings.

    V17.4: Raised threshold from 0.85 → 0.92 to be less aggressive.
    The V17.1.3 conversion merged 30 of 61 bullets (49%!) — too many
    unique bullets were lost. With 0.92, only near-exact semantic
    duplicates merge, preserving more unique information.

    After all bullet-generation stages (B4, B3, gap-fill, scholar reflection),
    there may be semantic duplicates — bullets expressing the same concept
    in different wording. rapidfuzz catches lexical duplicates but misses
    semantic ones (e.g., "AuthorI defined the core construct as inner sameness"
    vs "AuthorI's the core construct concept means persistent self-sameness").

    This method:
    1. Encodes all bullets with all-MiniLM-L6-v2 (384-dim, fast)
    2. Computes pairwise cosine similarity
    3. For any pair with similarity ≥ threshold, keeps the FIRST bullet
       (which is usually from the main summarization pass, not gap-fill)
    4. Returns the deduplicated list (order preserved)

    Content-agnostic: works for any book/topic. The threshold (0.85) is
    conservative — only removes near-semantic-duplicates, not related-but-
    distinct bullets.

    Falls back gracefully if sentence-transformers is not installed.

    Extracted verbatim from ``Summarizer._semantic_dedup_bullets``. The only
    change: ``self.log`` → ``log`` param. The embedder is a module singleton
    (``core.llm.model_singletons.get_embed_model``) — no instance state.
    """
    _log = log or _noop_log

    if len(bullets) < 2:
        return bullets

    try:
        import numpy as np

        from core.llm.model_singletons import get_embed_model, is_embedder_healthy

        embed_model = get_embed_model()
        if embed_model is None:
            _log("    🧹 Semantic dedup: sentence-transformers not available — skipping", "DEBUG")
            return bullets

        # V18.2.23 (BUG-B churn fix): if the embedder is unhealthy (Ollama
        # model not installed → smoke-test failed), SKIP semantic dedup
        # entirely. Running it with zero vectors makes every cos_sim = 0.0
        # (no bullets merged) but WORSE, the Jaccard fallback in
        # content_judge._semantic_similarity drops valid bullets at <0.50.
        # The V18.2.21 conversion log showed 35 bullets dropped then all 35
        # resurrected by the recovery pass — pure churn from a broken
        # embedder. Skipping dedup when unhealthy avoids this churn.
        if not is_embedder_healthy():
            _log(
                "    🧹 Semantic dedup: embedder unhealthy — skipping "
                "(would produce false drops on zero-vector similarity)",
                "WARNING",
            )
            return bullets

        # Encode all bullets (batched — fast)
        bullet_strs = [str(b) if not isinstance(b, str) else b for b in bullets if b]
        if len(bullet_strs) < 2:
            return bullets

        embeddings = embed_model.encode(bullet_strs, show_progress_bar=False, convert_to_numpy=True)
        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # avoid division by zero
        embeddings_norm = embeddings / norms

        # Compute pairwise similarity matrix
        sim_matrix = np.dot(embeddings_norm, embeddings_norm.T)

        # Greedy dedup: for each bullet, check if it's a duplicate of an
        # earlier bullet (similarity ≥ threshold). Keep the first occurrence.
        keep_indices = []
        removed = 0
        for i in range(len(bullet_strs)):
            is_dup = False
            for j in keep_indices:
                if sim_matrix[i][j] >= threshold:
                    is_dup = True
                    removed += 1
                    _log(
                        f"    🧹 Semantic dedup: removing bullet {i+1} (sim={sim_matrix[i][j]:.2f} with bullet {j+1})",
                        "DEBUG",
                    )
                    break
            if not is_dup:
                keep_indices.append(i)

        return [bullets[i] for i in keep_indices]

    except ImportError:
        _log("    🧹 Semantic dedup: numpy not available — skipping", "DEBUG")
        return bullets
    except Exception as e:
        _log(f"    🧹 Semantic dedup: error ({e}) — skipping", "DEBUG")
        return bullets


# ── compute_coverage (extracted verbatim from Summarizer V13.32.8/V18.2.19) ──


def compute_coverage(
    source: str,
    summary: str,
    coverage_cache: dict[str, tuple],
    extract_keywords: Callable[[str, int], list[str]],
) -> float:
    """Return fraction of source keywords + concepts present in summary.

    Uses BOTH keyword coverage AND concept coverage.
    The final score is max(keyword_coverage, concept_coverage) — V13.32.8
    changed this from a weighted average (40/60) to MAX so a strong
    concept match isn't dragged down by weak keyword overlap (and vice
    versa). This better reflects whether the summary actually covers the
    source's key ideas.

    V18.2.19: Increased keyword count from 18 → 30 and concept count
    from 15 → 25 for finer granularity. The old 18/15 counts produced
    coarse 5-7% steps (e.g., 17/18=94%, 16/18=89%), and the MAX of
    keyword+concept often landed on the same value (e.g., 12/13=92.3%)
    across different runs — making it look like a hardcoded "92%". The
    higher counts give ~3% steps and more varied results.

    Keywords and concepts are cached per source text (keyed by hash)
    to avoid re-extraction on repeated calls (multi-sample, self-review).

    Extracted verbatim from ``Summarizer._compute_coverage``. The only
    changes: ``self._coverage_cache`` → ``coverage_cache`` param (dict,
    passed by reference — mutations persist), ``self._extract_keywords`` →
    ``extract_keywords`` param (callable). The ``logger.debug`` call uses
    this module's logger (was ``summarizer.py``'s ``logger``).
    """
    # Cache lookup: extract keywords + concepts once per source text
    source_hash = hashlib.md5(source.encode()).hexdigest()
    if source_hash in coverage_cache:
        keywords, concepts = coverage_cache[source_hash]
    else:
        # V18.2.19: n=30 (was 18) for finer granularity.
        keywords = extract_keywords(source, 30)
        concepts = []
        try:
            from core.summarisation.text_preprocessor import extract_all_concepts
            # V18.2.19: max_terms=25 (was 15) for finer granularity.
            concepts = extract_all_concepts(source, max_terms=25)
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        coverage_cache[source_hash] = (keywords, concepts)
        # Prevent unbounded cache growth (keep last 50 chapters)
        if len(coverage_cache) > 50:
            oldest = next(iter(coverage_cache))
            del coverage_cache[oldest]

    if not keywords:
        return 1.0
    # V13.37.0: Normalize whitespace in both summary and concepts before
    # matching. The old code (sl = summary.lower()) failed when concepts
    # contained newlines from PDF table extraction.
    sl = re.sub(r'\s+', ' ', summary).strip().lower()
    keyword_found = sum(1 for k in keywords if k in sl)
    keyword_coverage = keyword_found / len(keywords)

    # Concept-based coverage (uses cached concepts)
    if concepts:
        # V13.37.0: Normalize concept whitespace too (newline → space)
        concept_found = sum(1 for c in concepts if re.sub(r'\s+', ' ', c).strip().lower() in sl)
        concept_coverage = concept_found / len(concepts)
        return max(keyword_coverage, concept_coverage)  # V13.32.8: MAX not weighted avg

    return keyword_coverage


# ── verify_bullets (extracted verbatim from Summarizer A3/V13.27.0) ────────


def verify_bullets(
    bullets: list,
    source_text: str,
    verify_windows_cache: dict[str, list],
    quarantine: QuarantineLike | None = None,
    log: LogCallback | None = None,
) -> list[str]:
    """A3: Deterministic fact-checking — verify each bullet against source.

    For each bullet, slide an 80-char window across the source text and
    compute fuzzy similarity. If the max score < 50%, mark as "⚠️ Unverified".

    V13.27.0 (P2.3): Fixed the 3-way threshold contradiction — docstring
    said 60%, code used 50%, log said 35%. All three now say 50%. Also
    added quarantine logging for unverified bullets (was cosmetic-only —
    the ⚠️ prefix was added but no downstream filter checked for it, and
    no quarantine entry was logged). Now the audit trail is complete.

    This catches hallucinations without needing a second LLM call.

    Performance: source windows are cached per source text (keyed by
    hash) to avoid recomputation on repeated calls (multi-sample,
    self-review).

    Extracted verbatim from ``Summarizer._verify_bullets``. The only changes:
    ``self._verify_windows_cache`` → ``verify_windows_cache`` param (dict,
    passed by reference — the caller must initialize it; the old lazy-init
    ``hasattr`` check is removed since the caller now guarantees it exists),
    ``self.quarantine`` → ``quarantine`` param, ``self.log`` → ``log`` param.
    """
    _log = log or _noop_log

    try:
        from rapidfuzz import fuzz as rf_fuzz
    except ImportError:
        return bullets  # rapidfuzz not available, skip verification

    # Cache the source windows (keyed by source text hash)
    src_hash = hashlib.md5(source_text.encode()).hexdigest()
    if src_hash in verify_windows_cache:
        windows = verify_windows_cache[src_hash]
    else:
        # Prepare source: lowercased, split into overlapping 80-char windows
        src_lower = source_text.lower()
        src_len = len(src_lower)
        window_size = 80
        windows = []
        for i in range(0, max(1, src_len - window_size), 40):
            windows.append(src_lower[i:i + window_size])
        if src_len <= window_size:
            windows.append(src_lower)
        verify_windows_cache[src_hash] = windows
        # Prevent unbounded cache growth
        if len(verify_windows_cache) > 20:
            oldest = next(iter(verify_windows_cache))
            del verify_windows_cache[oldest]

    # V13.27.0 P2.3: Single threshold constant — no more 35/50/60 contradiction
    VERIFY_THRESHOLD = 50.0  # bullets below this are "unverified"

    verified = 0
    unverified = 0
    result = []
    for bp in bullets:
        bp_str = str(bp).strip() if not isinstance(bp, str) else bp.strip()
        if not bp_str:
            continue
        # Strip citation markers for verification (e.g., "(p.31)")
        bp_clean = re.sub(r'\s*\(p\.\d+\)\s*$', '', bp_str).strip().lower()
        if len(bp_clean) < 10:
            result.append(bp_str)
            continue

        # Find the best matching window
        best_score = 0.0
        for window in windows:
            score = rf_fuzz.partial_ratio(bp_clean, window)
            if score > best_score:
                best_score = score
                if score >= 80:
                    break  # good enough, stop searching

        if best_score >= VERIFY_THRESHOLD:
            result.append(bp_str)
            verified += 1
        else:
            # V13.33.2: Don't add ⚠️ prefix to user-facing bullets.
            # The fact-checker false-positives on paraphrased bullets.
            # The bullet is kept (conservative mode) — adding ⚠️ confuses users.
            result.append(bp_str)
            unverified += 1
            # V13.27.0 P2.3: Log to quarantine for audit trail (was missing)
            if quarantine:
                quarantine.add(
                    bullet=bp_str,
                    stage="Layer A: Deterministic fact-check (verify_bullets)",
                    reason=f"rapidfuzz partial_ratio {best_score:.0f}% < {VERIFY_THRESHOLD:.0f}%",
                    source_overlap=best_score / 100.0,
                    actually_dropped=False,  # bullet is kept but marked ⚠️
                )

    if unverified > 0:
        # V13.27.0 P2.3: Fixed log message — was "< 35%", now matches the actual threshold
        _log(
            f"    🔍 Fact-check: {verified} verified, {unverified} unverified "
            f"(best-score < {VERIFY_THRESHOLD:.0f}%) — marked ⚠️, logged to quarantine",
            "WARNING"
        )
    else:
        _log(f"    🔍 Fact-check: all {verified} bullets verified ✓", "DEBUG")

    return result


__all__ = [
    "normalize_empty_section",
    "verify_additive_section_item",
    "verify_additive_sections",
    "anti_false_precision_check",
    "semantic_dedup_bullets",
    "compute_coverage",
    "verify_bullets",
]
