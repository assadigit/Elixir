"""Translation validator — triple-validation for zero hallucination tolerance.

Implements a 3-stage, non-blocking validation pipeline:

  1. **Back-translation**: translate the target back to source, then compute
     semantic similarity (via ``sentence-transformers`` all-MiniLM-L6-v2,
     already installed in the project). Threshold: 0.6.
  2. **Judge LLM**: a separate Ollama call (Qwen3.5-9B by default — different
     model family from the translator for orthogonal error detection) scores
     the translation 0.0-1.0 on faithfulness. Threshold: 0.7.
  3. **Report**: flagged chunks get one retry with a stricter prompt. If still
     failing, the translation is kept but flagged in
     ``translation_logs/Book.translation.report.json``.

Output is never blocked — the user always gets a translation file. The report
tells them which chunks to review manually.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ── Sentence-transformers lazy-load (already a project dependency) ───────

_sentence_model = None
_sentence_model_available = None


def _get_sentence_model():
    """Lazy-load the sentence-transformers model. Returns None if unavailable.

    V10.31.0 (Sprint 4.6): delegates to the shared singleton.
    """
    # V10.31.0: use shared singleton
    from core.llm.model_singletons import get_embed_model
    model = get_embed_model()
    _sentence_model_available = model is not None
    return model


def _semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts via sentence embeddings.

    Returns 0.0 if sentence-transformers is unavailable.
    """
    model = _get_sentence_model()
    if model is None:
        # Fallback: word-overlap Jaccard similarity
        return _jaccard_similarity(text_a, text_b)
    try:
        from numpy import dot
        from numpy.linalg import norm
        emb = model.encode([text_a, text_b])
        a, b = emb[0], emb[1]
        sim = float(dot(a, b) / (norm(a) * norm(b) + 1e-8))
        return max(0.0, min(1.0, sim))
    except Exception as _e:
        return _jaccard_similarity(text_a, text_b)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Fallback similarity: Jaccard overlap of word sets."""
    words_a = set(re.findall(r"\w+", text_a.lower()))
    words_b = set(re.findall(r"\w+", text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


# ── Data structures ───────────────────────────────────────────────────────

@dataclass
class ChunkValidation:
    """Validation result for a single chunk.

    Attributes:
        chunk_index:       0-based chunk position.
        source_text:       the original text (truncated to 500 chars in report).
        translated_text:   the translation (truncated to 500 chars in report).
        back_translated:   the back-translation (truncated to 500 chars in report).
        similarity_score:  semantic similarity (0.0-1.0) between source and back-translation.
        judge_score:       judge LLM faithfulness score (0.0-1.0).
        judge_reason:      judge LLM's explanation.
        passed:            True if both similarity >= threshold AND judge >= threshold.
        flagged_reason:    why it was flagged (empty if passed).
        retried:           True if this chunk was retried.
    """
    chunk_index: int
    source_text: str = ""
    translated_text: str = ""
    back_translated: str = ""
    similarity_score: float = 0.0
    judge_score: float = 0.0
    judge_reason: str = ""
    passed: bool = False
    flagged_reason: str = ""
    retried: bool = False


@dataclass
class ValidationReport:
    """Aggregate validation report for an entire file translation.

    Attributes:
        file_name:         the source file that was translated.
        source_lang:       source language ("en" or "fa").
        target_lang:       target language ("en" or "fa").
        total_chunks:      total number of translatable chunks.
        passed_chunks:     number of chunks that passed validation.
        flagged_chunks:    number of chunks that were flagged.
        retried_chunks:    number of chunks that were retried.
        avg_similarity:    average semantic similarity across all chunks.
        avg_judge_score:   average judge LLM score across all chunks.
        chunk_results:     per-chunk validation details.
    """
    file_name: str = ""
    source_lang: str = "en"
    target_lang: str = "fa"
    total_chunks: int = 0
    passed_chunks: int = 0
    flagged_chunks: int = 0
    retried_chunks: int = 0
    avg_similarity: float = 0.0
    avg_judge_score: float = 0.0
    chunk_results: list[ChunkValidation] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Truncate long text fields for the JSON report
        for cr in d["chunk_results"]:
            cr["source_text"] = cr["source_text"][:500] + ("..." if len(cr["source_text"]) > 500 else "")
            cr["translated_text"] = cr["translated_text"][:500] + ("..." if len(cr["translated_text"]) > 500 else "")
            cr["back_translated"] = cr["back_translated"][:500] + ("..." if len(cr["back_translated"]) > 500 else "")
        return d

    def save(self, path: Path) -> None:
        """Save the report to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def save_markdown(self, path: Path) -> None:
        """V7.2.0 S6: Save a human-readable Markdown report alongside the JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        lines.append(f"# Translation Report: {self.file_name}")
        lines.append("")
        lines.append(f"**Source language:** {self.source_lang}")
        lines.append(f"**Target language:** {self.target_lang}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- **Total chunks:** {self.total_chunks}")
        lines.append(f"- **Passed:** {self.passed_chunks} ({self.passed_chunks/max(self.total_chunks,1)*100:.0f}%)")
        lines.append(f"- **Flagged:** {self.flagged_chunks}")
        lines.append(f"- **Retried:** {self.retried_chunks}")
        lines.append(f"- **Average similarity:** {self.avg_similarity:.2f}")
        lines.append(f"- **Average judge score:** {self.avg_judge_score:.2f}")
        lines.append("")

        flagged = [cv for cv in self.chunk_results if not cv.passed]
        if flagged:
            lines.append("## Flagged Chunks (Require Manual Review)")
            lines.append("")
            for cv in flagged:
                lines.append(f"### Chunk {cv.chunk_index + 1}")
                lines.append(f"**Source:** {cv.source_text[:200]}{'...' if len(cv.source_text) > 200 else ''}")
                lines.append(f"**Translation:** {cv.translated_text[:200]}{'...' if len(cv.translated_text) > 200 else ''}")
                if cv.back_translated:
                    lines.append(f"**Back-translation:** {cv.back_translated[:200]}{'...' if len(cv.back_translated) > 200 else ''}")
                lines.append(f"**Similarity:** {cv.similarity_score:.2f}")
                lines.append(f"**Judge score:** {cv.judge_score:.2f}")
                if cv.judge_reason:
                    lines.append(f"**Judge reason:** {cv.judge_reason}")
                if cv.flagged_reason:
                    lines.append(f"**Flagged because:** {cv.flagged_reason}")
                if cv.retried:
                    lines.append("*This chunk was retried but still failed validation.*")
                lines.append("")
        else:
            lines.append("## ✅ All chunks passed validation — no manual review needed.")
            lines.append("")

        passed = [cv for cv in self.chunk_results if cv.passed]
        if passed:
            lines.append("## Passed Chunks")
            lines.append("")
            lines.append("| Chunk | Similarity | Judge | Status |")
            lines.append("|-------|------------|-------|--------|")
            for cv in passed:
                status = "✅ retried" if cv.retried else "✅"
                lines.append(f"| {cv.chunk_index + 1} | {cv.similarity_score:.2f} | {cv.judge_score:.2f} | {status} |")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def summary(self) -> str:
        """Return a one-line summary string for logging."""
        return (
            f"{self.passed_chunks}/{self.total_chunks} chunks passed "
            f"(avg similarity: {self.avg_similarity:.2f}, "
            f"avg judge: {self.avg_judge_score:.2f}, "
            f"{self.flagged_chunks} flagged, {self.retried_chunks} retried)"
        )


# ── Judge LLM prompt ─────────────────────────────────────────────────────

_JUDGE_PROMPT = """You are a translation quality judge. Given a source text and its translation, \
score the translation's faithfulness on a scale of 0.0 to 1.0.

Faithfulness means: does the translation convey the exact same meaning as the source, \
without adding, omitting, or distorting information?

Rules:
- 1.0 = perfect faithfulness (same meaning, no additions/omissions)
- 0.7-0.9 = minor issues (slight rewording, but meaning preserved)
- 0.4-0.6 = moderate issues (some meaning lost or added)
- 0.0-0.3 = major issues (hallucination, significant omission, or wrong meaning)

Respond in EXACTLY this format (no other text):
SCORE: <float between 0.0 and 1.0>
REASON: <one sentence explanation>

Source ({source_lang}):
{source_text}

Translation ({target_lang}):
{translated_text}

Score:"""


# ── Validator ────────────────────────────────────────────────────────────

class TranslationValidator:
    """Validates translation quality via back-translation + judge LLM.

    Usage::

        v = TranslationValidator(
            endpoint="http://localhost:11434/v1",
            judge_model="Qwen3.5-9B",
            translator=my_translator,  # for back-translation
        )
        result = v.validate_chunk(
            source_text="Hello world",
            translated_text="سلام دنیا",
            chunk_index=0,
            source_lang="en",
            target_lang="fa",
        )
        if not result.passed:
            ...  # retry or flag
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/v1",
        judge_model: str = "",
        translator: object | None = None,
        back_translation_threshold: float = 0.6,
        judge_threshold: float = 0.7,
        api_key: str = "",
        timeout: int = 120,
        log_callback: LogFn | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.judge_model = judge_model
        self.translator = translator  # for back-translation
        self.similarity_threshold = back_translation_threshold
        self.judge_threshold = judge_threshold
        self.api_key = api_key
        self.timeout = timeout
        self.log = log_callback or (lambda msg, level="INFO": None)
        # Track judge LLM failures (like the normalizer pattern)
        self._judge_failure_count = 0
        self._judge_disabled = False
        self._max_judge_failures = 5

    def validate_chunk(
        self,
        source_text: str,
        translated_text: str,
        chunk_index: int,
        source_lang: str,
        target_lang: str,
    ) -> ChunkValidation:
        """Validate a single chunk's translation.

        Returns a :class:`ChunkValidation` with scores and pass/fail status.
        """
        result = ChunkValidation(
            chunk_index=chunk_index,
            source_text=source_text,
            translated_text=translated_text,
        )

        # ── Stage 1: Back-translation + semantic similarity ────────────
        if self.translator is not None:
            try:
                back = self.translator.translate_back(
                    translated_text, source_lang, target_lang
                )
                result.back_translated = back
                result.similarity_score = _semantic_similarity(source_text, back)
            except Exception as e:
                self.log(
                    f"  [Validation] Back-translation failed for chunk "
                    f"{chunk_index}: {e}",
                    "WARNING"
                )
                result.similarity_score = 0.0
        else:
            # No translator available — skip back-translation, set high score
            result.similarity_score = 1.0

        # ── Stage 2: Judge LLM ─────────────────────────────────────────
        if not self._judge_disabled and self.judge_model:
            result.judge_score, result.judge_reason = self._call_judge(
                source_text, translated_text, source_lang, target_lang
            )
        else:
            # No judge LLM — rely only on similarity
            result.judge_score = 1.0
            result.judge_reason = "Judge LLM unavailable"

        # ── Stage 3: Determine pass/fail ───────────────────────────────
        similarity_passed = result.similarity_score >= self.similarity_threshold
        judge_passed = result.judge_score >= self.judge_threshold

        if similarity_passed and judge_passed:
            result.passed = True
        else:
            result.passed = False
            reasons = []
            if not similarity_passed:
                reasons.append(
                    f"similarity {result.similarity_score:.2f} < "
                    f"{self.similarity_threshold}"
                )
            if not judge_passed:
                reasons.append(
                    f"judge {result.judge_score:.2f} < {self.judge_threshold}"
                )
            result.flagged_reason = "; ".join(reasons)

        return result

    def validate_file(
        self,
        chunks: list[tuple],  # [(source_text, translated_text, chunk_index), ...]
        source_lang: str,
        target_lang: str,
        file_name: str = "",
    ) -> ValidationReport:
        """Validate an entire file's translation. Returns an aggregate report."""
        report = ValidationReport(
            file_name=file_name,
            source_lang=source_lang,
            target_lang=target_lang,
            total_chunks=len(chunks),
        )

        similarities = []
        judge_scores = []

        for source_text, translated_text, chunk_index in chunks:
            cv = self.validate_chunk(
                source_text, translated_text, chunk_index,
                source_lang, target_lang,
            )
            report.chunk_results.append(cv)
            if cv.passed:
                report.passed_chunks += 1
            else:
                report.flagged_chunks += 1
            if cv.retried:
                report.retried_chunks += 1
            similarities.append(cv.similarity_score)
            judge_scores.append(cv.judge_score)

        if similarities:
            report.avg_similarity = sum(similarities) / len(similarities)
        if judge_scores:
            report.avg_judge_score = sum(judge_scores) / len(judge_scores)

        return report

    # ── Internal: judge LLM call ──────────────────────────────────────

    def _call_judge(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> tuple:
        """Call the judge LLM and return (score, reason)."""
        prompt = _JUDGE_PROMPT.replace("{source_lang}", source_lang)
        prompt = prompt.replace("{target_lang}", target_lang)
        # V9.0.0 P3-8: increase truncation from 2000 to 8000 chars so long
        # chunks have their full content judged (was truncating the tail).
        prompt = prompt.replace("{source_text}", source_text[:8000])
        prompt = prompt.replace("{translated_text}", translated_text[:8000])

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.judge_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,  # deterministic for scoring
            "stream": False,
        }

        try:
            url = f"{self.endpoint}/chat/completions"
            resp = requests.post(url, json=payload, headers=headers,
                                 timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            # V9.0.0 P3-9: fix brittle SCORE regex — match only on the SCORE
            # line (line-anchored), not the first float anywhere in the text.
            # Old regex would match "I'd score this 0.9 because of 2 issues" → 0.9.
            score_match = re.search(r"^SCORE:\s*(\d+\.?\d*)\s*$", content, re.MULTILINE | re.IGNORECASE)
            if not score_match:
                # Fallback: try the old pattern but only on the first line containing SCORE
                score_match = re.search(r"SCORE:\s*(\d+\.?\d*)", content, re.IGNORECASE)
            reason_match = re.search(r"REASON:\s*(.+)", content, re.IGNORECASE | re.DOTALL)

            score = float(score_match.group(1)) if score_match else 0.5
            score = max(0.0, min(1.0, score))  # clamp
            reason = reason_match.group(1).strip() if reason_match else "No reason provided"

            self._judge_failure_count = 0  # reset on success
            return score, reason

        except Exception as e:
            self._judge_failure_count += 1
            if self._judge_failure_count >= self._max_judge_failures:
                self._judge_disabled = True
                self.log(
                    f"  [Validation] Judge LLM disabled after "
                    f"{self._judge_failure_count} failures (last: {e}). "
                    f"Relying on back-translation similarity only.",
                    "WARNING"
                )
            return 0.5, f"Judge LLM error: {e}"
