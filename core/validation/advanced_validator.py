"""AdvancedValidator – Hybrid Guardrail for Summary Quality.

Adds:
1. Semantic Embedding (Cosine Similarity) – catches paraphrasing.
2. Named Entity Recognition (NER) – ensures factual entities are preserved.
3. Contextual Overlap Distribution – prevents keyword stuffing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re

import numpy as np


class AdvancedValidator:
    _embedder = None
    _nlp = None

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._load_models()

    def _load_models(self):
        """Lazy load models to save memory if not used."""
        # 1. Embedder (Semantic Similarity) — V10.31.0 (Sprint 4.6): shared singleton
        if AdvancedValidator._embedder is None:
            try:
                from core.llm.model_singletons import get_embed_model
                AdvancedValidator._embedder = get_embed_model()
                if AdvancedValidator._embedder is not None:
                    self.log("   ✅ Embedding model loaded (shared singleton).", "DEBUG")
                else:
                    self.log("   ⚠️ sentence-transformers not installed. Semantic guardrail disabled.", "WARNING")
            except Exception as e:
                self.log(f"   ⚠️ Embedding model load failed: {e}", "WARNING")

        # 2. SpaCy NER (Entity Recognition) — V10.31.0 (Sprint 4.6): shared singleton
        if AdvancedValidator._nlp is None:
            try:
                from core.llm.model_singletons import get_spacy_nlp
                AdvancedValidator._nlp = get_spacy_nlp(
                    "en_core_web_sm", disable=["parser", "tagger", "attribute_ruler"]
                )
                if AdvancedValidator._nlp is not None:
                    self.log("   ✅ SpaCy NER model loaded (shared singleton).", "DEBUG")
                else:
                    self.log("   ⚠️ SpaCy not installed. NER guardrail disabled.", "WARNING")
            except Exception as e:
                self.log(f"   ⚠️ SpaCy load failed: {e}", "WARNING")

    # ──────────────────────────────────────────────────────────────
    # 1. Semantic Embedding Guardrail
    # ──────────────────────────────────────────────────────────────
    def compute_semantic_similarity(self, source: str, summary: str) -> float:
        """
        Compute cosine similarity between source and summary embeddings.

        V18.2.2 (audit O1): Fixed the chunking bug. Previously truncated
        source/summary to 8000 chars (≈2000 tokens) and encoded as ONE vector
        — but the embedder's token limit is 512, so only the first ~2000 chars
        were actually used. The rest was silently ignored.

        Now: splits source and summary into 512-token chunks, encodes each
        chunk, and mean-pools the chunk embeddings into a single document
        vector. This captures the full text instead of just the first ~25%.

        Returns 0.0 if model unavailable, else score between 0 and 1.
        """
        if AdvancedValidator._embedder is None:
            return 0.0

        try:
            # V18.2.2: chunk-based encoding (was: single-vector on truncated text)
            # Split into ~512-token chunks (roughly 2000 chars at 4 chars/token).
            # Mean-pool the chunk vectors to get a single document embedding.
            source_vec = self._encode_document(source)
            summary_vec = self._encode_document(summary)
            if source_vec is None or summary_vec is None:
                return 0.0
            # Cosine similarity
            norm_s = np.linalg.norm(source_vec)
            norm_t = np.linalg.norm(summary_vec)
            if norm_s == 0 or norm_t == 0:
                return 0.0
            similarity = float(np.dot(source_vec, summary_vec) / (norm_s * norm_t))
            return similarity
        except Exception as e:
            self.log(f"   ⚠️ Semantic similarity failed: {e}", "WARNING")
            return 0.0

    def _encode_document(self, text: str, chunk_chars: int = 2000) -> np.ndarray | None:
        """V18.2.2: Encode a long text by chunking + mean-pooling.

        Splits ``text`` into chunks of ``chunk_chars`` characters (≈512 tokens
        at 4 chars/token — the embedder's context limit), encodes each chunk,
        and mean-pools the vectors into a single document embedding.

        This fixes the bug where encoding 8000 chars as one vector silently
        ignored everything past the first ~2000 chars.
        """
        if not text:
            return None
        # If text is short enough for one chunk, encode directly
        if len(text) <= chunk_chars:
            vec = AdvancedValidator._embedder.encode([text])
            return np.asarray(vec[0] if hasattr(vec, '__getitem__') and len(vec.shape) > 1 else vec,
                             dtype=np.float32)

        # Split into chunks at paragraph boundaries (prefer not to split mid-sentence)
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= chunk_chars:
                chunks.append(remaining)
                break
            # Find a paragraph or sentence break near the chunk boundary
            cut = remaining.rfind("\n\n", 0, chunk_chars)
            if cut < chunk_chars // 2:
                cut = remaining.rfind(". ", 0, chunk_chars)
            if cut < chunk_chars // 2:
                cut = remaining.rfind(" ", 0, chunk_chars)
            if cut < chunk_chars // 2:
                cut = chunk_chars  # hard cut — no good boundary found
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()

        if not chunks:
            return None
        try:
            vecs = AdvancedValidator._embedder.encode(chunks)
            vecs = np.asarray(vecs, dtype=np.float32)
            # Mean-pool the chunk vectors
            return np.mean(vecs, axis=0)
        except Exception as e:
            self.log(f"   ⚠️ Document chunked encoding failed: {e}", "WARNING")
            # Fallback: encode just the first chunk
            try:
                vec = AdvancedValidator._embedder.encode([chunks[0]])
                return np.asarray(vec[0] if len(np.asarray(vec).shape) > 1 else vec,
                                 dtype=np.float32)
            except Exception:
                return None

    # ──────────────────────────────────────────────────────────────
    # 2. Named Entity Guardrail (Factual Rigor) – FIXED to return count
    # ──────────────────────────────────────────────────────────────
    def compute_entity_preservation(self, source: str, summary: str) -> dict[str, float]:
        """
        Extracts named entities (PERSON, ORG, DATE, GPE, etc.) from source and summary.
        Returns recall (how many source entities are in summary), hallucination penalty,
        and source_entity_count for auto-pass logic.
        """
        result = {"recall": 0.0, "hallucination_penalty": 1.0, "source_entity_count": 0}

        if AdvancedValidator._nlp is None:
            return result

        try:
            # Truncate to avoid memory issues with very long text
            source_trunc = source[:50000]
            summary_trunc = summary[:50000]

            doc_source = AdvancedValidator._nlp(source_trunc)
            doc_summary = AdvancedValidator._nlp(summary_trunc)

            # Extract entities (normalize text and lower case)
            source_entities = set()
            for ent in doc_source.ents:
                # Skip numbers less than 10 (noise)
                if ent.label_ in ["DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL"]:
                    if len(ent.text) < 3 and ent.text.isdigit() and int(ent.text) < 10:
                        continue
                source_entities.add((ent.label_, ent.text.lower().strip()))

            summary_entities = set()
            for ent in doc_summary.ents:
                summary_entities.add((ent.label_, ent.text.lower().strip()))

            source_count = len(source_entities)
            result["source_entity_count"] = source_count

            if source_count == 0:
                # No entities in source, recall is 1.0 by default (auto-pass)
                result["recall"] = 1.0
                result["hallucination_penalty"] = 1.0
                return result

            # Recall: How many source entities are captured?
            hits = source_entities.intersection(summary_entities)
            recall = len(hits) / source_count
            result["recall"] = recall

            # Penalty: If summary has entities completely absent from source (hallucination)
            summary_only = summary_entities - source_entities
            if summary_entities:
                hallucination_ratio = len(summary_only) / len(summary_entities)
            else:
                hallucination_ratio = 0.0

            # Hallucination penalty: If 50% of summary's entities are new, heavily penalize faithfulness.
            penalty = 1.0 - (hallucination_ratio * 0.5)  # Cap: drops to 0.5 if all entities are fake.
            result["hallucination_penalty"] = max(0.5, penalty)

            return result
        except Exception as e:
            self.log(f"   ⚠️ NER failed: {e}", "WARNING")
            return {"recall": 0.0, "hallucination_penalty": 1.0, "source_entity_count": 0}

    # ──────────────────────────────────────────────────────────────
    # 3. Contextual Overlap (Anti-Keyword-Stuffing)
    # ──────────────────────────────────────────────────────────────
    def compute_distribution_score(self, source: str, summary: str, lexical_keywords: list[str]) -> float:
        """
        Checks if the matched lexical keywords are spread across the summary sentences.
        Rewards even distribution, penalizes clustering in 1 sentence.
        """
        if not lexical_keywords or len(lexical_keywords) < 3:
            return 1.0  # Too few keywords to judge, assume pass.

        # Split summary into sentences
        sentences = re.split(r'(?<=[.!?])\s+', summary)
        if len(sentences) < 2:
            return 0.8  # Short summary, cannot distribute well, give moderate pass.

        # For each keyword, find which sentence it appears in (normalized)
        keyword_positions = []
        for kw in lexical_keywords:
            kw_lower = kw.lower()
            found = False
            for idx, sent in enumerate(sentences):
                if kw_lower in sent.lower():
                    keyword_positions.append(idx)
                    found = True
                    break
            if not found:
                # Keyword not found in summary (coverage will catch this)
                pass

        if not keyword_positions:
            return 0.0

        # Calculate variance of positions. High variance = well distributed.
        positions = np.array(keyword_positions)
        if len(positions) < 2:
            return 0.5

        variance = np.var(positions)
        # Normalize variance to a 0-1 score. Max variance is (len(sentences)/2)^2
        max_variance = (len(sentences) / 2) ** 2 if len(sentences) > 2 else 1.0
        if max_variance == 0:
            return 0.5

        raw_score = min(1.0, variance / max_variance)
        # Boost slightly to not be overly harsh
        return 0.6 + (raw_score * 0.4)
