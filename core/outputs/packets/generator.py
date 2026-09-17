"""Packets of Knowledge — the PacketGenerator engine.

V18.20.4.6+ (P5-2b / O-c4): extracted VERBATIM from the former
core/outputs/packets.py monolith (lines 109-1707 of the pre-split file) —
only this module docstring + import block differ. The shared data classes
(Packet / PacketCollection) and the LogFn alias live in
core.outputs.packets.models; import this module's names via the
core.outputs.packets facade.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from core.models import SummaryResult

from core.outputs.packets.models import LogFn, Packet, PacketCollection

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# Packet Generator
# ════════════════════════════════════════════════════════════════════════════

class PacketGenerator:
    """Generates Packets of Knowledge from chapter summaries."""

    CLUSTER_SIZE_MIN = 5
    CLUSTER_SIZE_MAX = 8

    # V13.23.0: Chapter-aligned mode thresholds.
    # MIN_BULLETS_PER_PACKET — below this, supplement with exec summary.
    # MAX_BULLETS_PER_PACKET — above this, split into multiple packets.
    # TARGET_BULLETS_PER_PACKET — sweet spot for splitting dense chapters.
    MIN_BULLETS_PER_PACKET = 5
    MAX_BULLETS_PER_PACKET = 10
    TARGET_BULLETS_PER_PACKET = 7

    def __init__(
        self,
        request: Any,
        log_callback: LogFn | None = None,
    ) -> None:
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)

    def _get_mode(self) -> str:
        """V13.23.0: Get the packets mode from settings.

        Returns "chapter" (default, new architecture) or "cross_chapter"
        (legacy, cross-chapter semantic clustering — may produce mismatched
        packets, use at own risk).
        """
        try:
            from utils.settings import Settings
            s = Settings()
            mode = s.get("packets.mode", "chapter")
            if mode not in ("chapter", "cross_chapter"):
                mode = "chapter"
            return mode
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return "chapter"

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> list[Path] | None:
        """Main entry point — generate all packet outputs.

        V13.23.0: Branches on ``packets.mode`` setting:
        - "chapter" (default): chapter-aligned mode — 1+ packets per chapter,
          split if too many bullets, supplement with exec summary if too few.
        - "cross_chapter": legacy cross-chapter semantic clustering (may
          produce mismatched packets — use at own risk).
        """
        t_start = time.time()
        mode = self._get_mode()
        self.log(f"📦 Generating Packets of Knowledge (mode: {mode})...", "INFO")

        if mode == "cross_chapter":
            self.log(
                "  ⚠️ Cross-chapter mode uses semantic clustering that may produce "
                "mismatched packets. Chapter-aligned mode is recommended for best results.",
                "WARNING"
            )

        # 1. Collect all keypoints
        all_bullets = self._collect_bullets(summaries)
        if len(all_bullets) < 10:
            self.log(f"  ℹ️ Not enough keypoints for packets ({len(all_bullets)} < 10)", "INFO")
            return None

        self.log(f"  📊 Collected {len(all_bullets)} keypoints from {len(summaries)} chapters", "INFO")

        # V13.19.0 Fix 2: Pre-clustering deduplication (rapidfuzz, 85% threshold).
        # Done BEFORE clustering so duplicate bullets don't pollute the clusters.
        original_bullet_count = len(all_bullets)
        all_bullets = self._deduplicate_bullets(all_bullets)
        dedup_bullet_count = len(all_bullets)

        # 2. Cluster into packets — branch on mode
        if mode == "chapter":
            packets = self._cluster_by_chapter(summaries)
        else:
            packets = self._cluster_bullets(all_bullets, summaries)
        self.log(f"  📦 Created {len(packets)} packets from {len(all_bullets)} keypoints", "INFO")

        # 3. Generate content for each packet
        for i, packet in enumerate(packets):
            self._generate_packet_content(packet, i, len(packets))
            # V13.19.0 Fix 3: If validation failed, replace paragraph with
            # the source bullets as a formatted list.  We do NOT drop the
            # packet — 100% of source bullets must remain visible.
            if not packet.validation_passed:
                self._apply_bullet_fallback(packet, i)
            if (i + 1) % 10 == 0:
                self.log(f"  📦 Generated {i+1}/{len(packets)} packets", "INFO")

        # V13.19.0 Fix 3: do NOT drop failed packets.  Re-index packets so
        # the surviving indices stay contiguous (no gaps for the user).
        # Previously: `valid_packets = [p for p in packets if p.validation_passed]`
        # which silently lost 45% of packets (9/20) and 44% of source bullets.
        synthesized = sum(1 for p in packets if p.validation_passed)
        fallback = len(packets) - synthesized
        if fallback > 0:
            self.log(
                f"  ⚠️ {fallback} packet(s) failed validation — using bullet-list fallback "
                f"(no packets dropped, no bullets lost)",
                "WARNING"
            )
        self.log(
            f"  📊 Coverage: {synthesized} synthesized, {fallback} bullet-list fallback "
            f"(out of {len(packets)} packets)",
            "INFO"
        )
        # Re-index so packet numbers are contiguous 1..N
        for i, p in enumerate(packets):
            p.index = i

        # 4. Build hierarchy (themes → concepts → packets)
        self._build_hierarchy(packets)
        self.log(f"  🌳 Hierarchy: {len(set(p.theme for p in packets))} themes, "
                 f"{len(set(p.concept for p in packets))} concepts", "INFO")

        # 5. Generate cross-references
        self._generate_cross_refs(packets)
        self.log("  🔗 Cross-references generated", "INFO")

        # 6. Generate one-page distillation
        one_page = self._generate_one_page(packets, book_title)

        # 7. Build collection
        collection = PacketCollection(
            book_title=book_title,
            packets=packets,
            themes=sorted(set(p.theme for p in packets if p.theme)),
            concepts=sorted(set(p.concept for p in packets if p.concept)),
            total_bullets=len(all_bullets),
            total_packets=len(packets),
            generation_time_s=time.time() - t_start,
        )

        # 8. Write output files
        output_paths: list[Path] = []
        output_dir.mkdir(parents=True, exist_ok=True)

        # Full packets document
        full_path = output_dir / f"{book_title}.Packets.md"
        self._write_full_document(collection, full_path)
        output_paths.append(full_path)
        self.log(f"  ✅ Packets: {full_path.name}", "SUCCESS")

        # One-page distillation
        one_page_path = output_dir / f"{book_title}.Packets.OnePage.md"
        one_page_path.write_text(one_page, encoding="utf-8")
        output_paths.append(one_page_path)
        self.log(f"  ✅ One-page distillation: {one_page_path.name}", "SUCCESS")

        # Knowledge map (Mermaid)
        map_path = output_dir / f"{book_title}.Packets.Map.md"
        self._write_knowledge_map(collection, map_path)
        output_paths.append(map_path)
        self.log(f"  ✅ Knowledge map: {map_path.name}", "SUCCESS")

        # V13.19.0 Fix 4: Coverage report — bullet → packet mapping
        coverage_path = output_dir / f"{book_title}.Packets.Coverage.md"
        self._write_coverage_report(
            collection=collection,
            original_bullets=all_bullets,
            original_count=original_bullet_count,
            dedup_count=dedup_bullet_count,
            path=coverage_path,
        )
        output_paths.append(coverage_path)
        self.log(f"  ✅ Coverage report: {coverage_path.name}", "SUCCESS")

        elapsed = time.time() - t_start
        self.log(f"  📦 Packets complete: {len(packets)} packets in {elapsed:.1f}s", "SUCCESS")

        return output_paths

    # ── Step 1: Collect bullets ────────────────────────────────────────

    def _collect_bullets(self, summaries: list[SummaryResult]) -> list[tuple[str, str]]:
        """Collect all keypoints as (bullet_text, chapter_heading) tuples."""
        bullets = []
        for s in summaries:
            if not s.success or not s.bullet_points:
                continue
            for bp in s.bullet_points:
                clean = bp.strip().lstrip("-•* ").strip()
                if clean and len(clean) > 10:
                    bullets.append((clean, s.chapter_heading or "Unknown"))
        return bullets

    # ── Step 1b: Deduplicate bullets (V13.19.0 Fix 2) ─────────────────

    def _deduplicate_bullets(
        self,
        bullets: list[tuple[str, str]],
        threshold: int = 70,
    ) -> list[tuple[str, str]]:
        """Merge near-duplicate bullets before clustering.

        V13.21.0: Lowered threshold from 85 to 70 AND added content-word
        overlap check (Jaccard). The old 85% token_set_ratio was too strict
        — it missed semantic duplicates like "Take detailed notes using a
        contact sheet" vs "Use detailed notes called a client contact sheet"
        (token_set_ratio ~60%, but content-word overlap is 80%).

        Now uses TWO signals:
        1. rapidfuzz token_set_ratio >= 70% (was 85%)
        2. Content-word Jaccard overlap >= 50%
        If EITHER signal fires, the bullet is considered a duplicate.
        """
        if len(bullets) < 2:
            return list(bullets)

        # Stop words for content-word comparison
        _STOP = frozenset(
            ["the", "a", "an", "and", "or", "to", "in", "for", "with", "on", "at", "by", "from", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these", "those", "they", "them", "their", "he", "she", "we", "you", "i", "me", "my", "your", "his", "her", "our", "not", "no", "do", "does", "did", "will", "would", "can", "could", "should", "may", "might", "must", "shall", "of", "as", "if", "than", "then", "so", "such", "very", "more", "most", "some", "any", "all", "each", "every", "which", "what", "who", "whom", "whose", "where", "when", "why", "how", "into", "out", "up", "down", "over", "under", "again", "further", "once", "here", "there", "about", "above", "below", "off", "through", "during", "before", "after", "between", "among"])

        def _content_words(text: str) -> set:
            """Extract significant content words (lowercase, 3+ chars, not stop words)."""
            return {w.lower() for w in re.findall(r'[a-zA-Z]{3,}', text)
                    if w.lower() not in _STOP}

        try:
            from rapidfuzz import fuzz as _rf_fuzz  # type: ignore

            def _ratio(a: str, b: str) -> float:
                return float(_rf_fuzz.token_set_ratio(a, b))
        except ImportError:
            from difflib import SequenceMatcher

            def _ratio(a: str, b: str) -> float:
                return SequenceMatcher(None, a, b).ratio() * 100.0

        deduped: list[tuple[str, str]] = []
        deduped_words: list = []  # cache content words for speed
        duplicates_removed = 0
        for bullet, chapter in bullets:
            is_dup = False
            bullet_words = _content_words(bullet)
            for i, (kept_bullet, _) in enumerate(deduped):
                # Signal 1: rapidfuzz token_set_ratio >= 70%
                try:
                    if _ratio(bullet, kept_bullet) >= threshold:
                        is_dup = True
                        break
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
                    pass
                # Signal 2: content-word Jaccard overlap >= 50%
                kept_words = deduped_words[i]
                if bullet_words and kept_words:
                    overlap = len(bullet_words & kept_words)
                    union = len(bullet_words | kept_words)
                    if union > 0 and overlap / union >= 0.50:
                        is_dup = True
                        break
            if is_dup:
                duplicates_removed += 1
                # V13.26.0 (P1.6): Track dropped bullets for audit
                if not hasattr(self, '_dedup_dropped_details'):
                    self._dedup_dropped_details = []
                self._dedup_dropped_details.append(f"  🗑️ '{bullet[:60]}...' (dup)")
            else:
                deduped.append((bullet, chapter))
                deduped_words.append(bullet_words)

        if duplicates_removed > 0:
            self.log(
                f"  📊 Deduplicated: {len(bullets)} → {len(deduped)} bullets "
                f"({duplicates_removed} duplicates removed)",
                "INFO",
            )
            # V13.26.0 (P1.6): Log each dropped bullet for audit trail
            details = getattr(self, '_dedup_dropped_details', [])
            for detail in details[:15]:
                self.log(detail, "DEBUG")
            if len(details) > 15:
                self.log(f"  ... and {len(details) - 15} more", "DEBUG")
        return deduped

    # ── Step 2 (chapter mode): Cluster by chapter ─────────────────────

    def _cluster_by_chapter(
        self,
        summaries: list[SummaryResult],
    ) -> list[Packet]:
        """V13.23.0: Chapter-aligned clustering — uses the author's own chapter
        boundaries instead of lossy cross-chapter semantic clustering.

        For each chapter:
        - If bullets >= MAX_BULLETS_PER_PACKET (10): split into 2+ packets
          of ~TARGET_BULLETS_PER_PACKET (7) each.
        - If bullets >= MIN_BULLETS_PER_PACKET (5): 1 packet (ideal).
        - If bullets < MIN_BULLETS_PER_PACKET (5): supplement with exec
          summary sentences as ``supplementary_context`` so the LLM has
          context to synthesize without hallucinating.

        Each packet's ``source_chapters`` contains exactly one chapter heading
        (the author's own section title), which becomes the concept node in
        the hierarchy — giving a naturally balanced, meaningful knowledge map.

        Returns:
            List of Packet objects, each tied to exactly one chapter.
        """
        packets: list[Packet] = []
        chapters_with_bullets = 0
        chapters_supplemented = 0
        chapters_split = 0

        for s in summaries:
            heading = (s.chapter_heading or f"Chapter {len(packets) + 1}").strip()
            bullets = list(s.bullet_points)

            if not bullets:
                # Skip chapters with no bullets at all — nothing to synthesize
                self.log(f"  Ⓜ️ Chapter '{heading[:40]}': no bullets — skipped", "DEBUG")
                continue

            chapters_with_bullets += 1
            n = len(bullets)

            if n > self.MAX_BULLETS_PER_PACKET:
                # ── Split dense chapters into 2+ packets ────────────────
                chunks = self._split_bullets_into_chunks(bullets, self.TARGET_BULLETS_PER_PACKET)
                chapters_split += 1
                self.log(
                    f"  📂 Chapter '{heading[:40]}': {n} bullets → {len(chunks)} packets",
                    "INFO"
                )
                for chunk in chunks:
                    packet = Packet(
                        index=len(packets),
                        source_bullets=chunk,
                        source_chapters=[heading],
                    )
                    packets.append(packet)

            elif n < self.MIN_BULLETS_PER_PACKET:
                # ── Supplement thin chapters with exec summary ──────────
                supp = self._extract_exec_summary_sentences(s.executive_summary)
                packet = Packet(
                    index=len(packets),
                    source_bullets=bullets,
                    source_chapters=[heading],
                    supplementary_context=supp,
                )
                chapters_supplemented += 1
                self.log(
                    f"  📝 Chapter '{heading[:40]}': {n} bullets (< {self.MIN_BULLETS_PER_PACKET}) "
                    f"+ {len(supp)} exec-summary sentences as supplementary context",
                    "INFO"
                )
                packets.append(packet)

            else:
                # ── Ideal: 1 packet per chapter ────────────────────────
                packet = Packet(
                    index=len(packets),
                    source_bullets=bullets,
                    source_chapters=[heading],
                )
                packets.append(packet)

        self.log(
            f"  📊 Chapter-aligned: {chapters_with_bullets} chapters with bullets, "
            f"{chapters_split} split, {chapters_supplemented} supplemented with exec summary, "
            f"{len(packets)} packets total",
            "INFO"
        )

        if not packets:
            # Fallback: no chapters had bullets — shouldn't happen (checked
            # earlier) but guard against empty output.
            self.log("  ⚠️ No packets created from chapters — falling back to sequential", "WARNING")
            return self._sequential_cluster(
                [(b, "Unknown") for s in summaries for b in s.bullet_points]
            )

        return packets

    @staticmethod
    def _split_bullets_into_chunks(
        bullets: list[str],
        target_size: int,
    ) -> list[list[str]]:
        """Split a list of bullets into chunks of ~target_size each.

        Distributes remainder evenly across chunks (not all in the last).
        E.g. 22 bullets with target 7 → [8, 7, 7] (not [7, 7, 8]).
        """
        if not bullets:
            return []
        n = len(bullets)
        if n <= target_size:
            return [list(bullets)]

        # Calculate number of chunks and distribute remainder
        n_chunks = (n + target_size - 1) // target_size
        base_size = n // n_chunks
        remainder = n % n_chunks

        chunks: list[list[str]] = []
        idx = 0
        for i in range(n_chunks):
            size = base_size + (1 if i < remainder else 0)
            chunks.append(bullets[idx:idx + size])
            idx += size
        return chunks

    @staticmethod
    def _extract_exec_summary_sentences(exec_summary: str) -> list[str]:
        """Split an executive summary into sentences for supplementary context.

        V13.23.0: When a chapter has fewer than MIN_BULLETS_PER_PACKET bullets,
        the exec summary is used as supplementary context so the LLM doesn't
        hallucinate to fill the gap.  These sentences are NOT primary bullets —
        they're context.  Tracked separately in ``packet.supplementary_context``.

        Returns up to 5 sentences (enough to provide context without flooding
        the prompt).  Filters out very short sentences (< 30 chars).
        """
        if not exec_summary or not exec_summary.strip():
            return []

        # Split on sentence boundaries (. ! ?) followed by whitespace + capital
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', exec_summary.strip())
        sentences = [
            s.strip()
            for s in raw_sentences
            if len(s.strip()) >= 30
        ]
        return sentences[:5]  # cap at 5 to avoid flooding the prompt

    # ── Step 2 (cross-chapter mode): Cluster bullets ──────────────────

    def _cluster_bullets(
        self,
        bullets: list[tuple[str, str]],
        summaries: list[SummaryResult],
    ) -> list[Packet]:
        """Cluster bullets into packets using sentence-transformer embeddings."""
        try:
            from sentence_transformers import SentenceTransformer  # noqa (kept for util)
            from core.llm.model_singletons import get_embed_model
            import numpy as np
            from sklearn.cluster import AgglomerativeClustering
        except ImportError:
            self.log("  ⚠️ sentence-transformers/sklearn not available — using sequential grouping", "WARNING")
            return self._sequential_cluster(bullets)

        try:
            model = get_embed_model()  # V10.31.0 singleton
            texts = [b[0] for b in bullets]
            embeddings = model.encode(texts, show_progress_bar=False)

            n_bullets = len(bullets)

            # V13.21.0: Target 5 bullets per packet with even distribution.
            TARGET_SIZE = 5
            SOFT_MIN = 3
            SOFT_MAX = 8

            n_clusters = max(1, n_bullets // TARGET_SIZE)
            n_clusters = min(n_clusters, max(1, n_bullets // SOFT_MIN))
            self.log(f"  📊 Target: {n_clusters} packets × ~{TARGET_SIZE} bullets each", "INFO")

            # Agglomerative clustering — groups semantically similar bullets
            clustering = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric="cosine",
                linkage="average",
            )
            labels = clustering.fit_predict(embeddings)

            # V13.21.0: Build initial clusters, then rebalance for even distribution.
            clusters: dict = {}
            for i, label in enumerate(labels):
                clusters.setdefault(int(label), []).append(i)

            # Phase 1: Split oversized clusters (>SOFT_MAX) into chunks of TARGET_SIZE
            split_clusters: list = []
            for indices in clusters.values():
                if len(indices) > SOFT_MAX:
                    centroid = np.mean(embeddings[indices], axis=0)
                    sims = [float(np.dot(embeddings[i], centroid) /
                                   (np.linalg.norm(embeddings[i]) * np.linalg.norm(centroid) + 1e-8))
                            for i in indices]
                    sorted_indices = [i for _, i in sorted(zip(sims, indices), reverse=True)]
                    for j in range(0, len(sorted_indices), TARGET_SIZE):
                        chunk = sorted_indices[j:j + TARGET_SIZE]
                        if chunk:
                            split_clusters.append(chunk)
                else:
                    split_clusters.append(indices)

            # Phase 2: Merge undersized clusters (<SOFT_MIN) with nearest neighbor
            cluster_centroids = []
            for indices in split_clusters:
                if indices:
                    cluster_centroids.append(np.mean(embeddings[indices], axis=0))
                else:
                    cluster_centroids.append(np.zeros(embeddings.shape[1]))

            merged: list = []
            used: set = set()
            for i, indices in enumerate(split_clusters):
                if i in used:
                    continue
                if len(indices) < SOFT_MIN and len(merged) > 0:
                    best_j = -1
                    best_sim = -1.0
                    for j, merged_indices in enumerate(merged):
                        if not merged_indices:
                            continue
                        merged_centroid = np.mean(embeddings[merged_indices], axis=0)
                        sim = float(np.dot(cluster_centroids[i], merged_centroid) /
                                    (np.linalg.norm(cluster_centroids[i]) * np.linalg.norm(merged_centroid) + 1e-8))
                        if sim > best_sim:
                            best_sim = sim
                            best_j = j
                    if best_j >= 0:
                        merged[best_j].extend(indices)
                        used.add(i)
                        continue
                merged.append(list(indices))
                used.add(i)

            # Phase 3: Final split — any clusters >SOFT_MAX from merging get split again
            final_clusters: list = []
            for indices in merged:
                if len(indices) > SOFT_MAX:
                    for j in range(0, len(indices), TARGET_SIZE):
                        chunk = indices[j:j + TARGET_SIZE]
                        if chunk:
                            final_clusters.append(chunk)
                else:
                    final_clusters.append(indices)

            # Build packets from final clusters
            packets = []
            for cluster_indices in final_clusters:
                if not cluster_indices:
                    continue
                packet = Packet(
                    index=len(packets),
                    source_bullets=[bullets[i][0] for i in cluster_indices],
                    source_chapters=[bullets[i][1] for i in cluster_indices],
                )
                packets.append(packet)

            # V13.21.0: Handle any orphan bullets (not assigned to any cluster)
            assigned = set()
            for p in packets:
                for b in p.source_bullets:
                    for i, (orig_b, _) in enumerate(bullets):
                        if orig_b == b:
                            assigned.add(i)

            orphans = [i for i in range(len(bullets)) if i not in assigned]
            if orphans and packets:
                # Distribute orphans across packets (round-robin, not all to last)
                for j, i in enumerate(orphans):
                    target_packet = packets[j % len(packets)]
                    target_packet.source_bullets.append(bullets[i][0])
                    target_packet.source_chapters.append(bullets[i][1])

            # V13.21.0: Log distribution stats
            sizes = [len(p.source_bullets) for p in packets]
            if sizes:
                self.log(
                    f"  📊 Packet distribution: {len(packets)} packets, "
                    f"min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)/len(sizes):.1f}",
                    "INFO")

            return packets if packets else self._sequential_cluster(bullets)

        except Exception as e:
            self.log(f"  ⚠️ Clustering failed ({e}) — using sequential grouping", "WARNING")
            return self._sequential_cluster(bullets)

    def _sequential_cluster(self, bullets: list[tuple[str, str]]) -> list[Packet]:
        """Fallback: group bullets sequentially into packets of 5-8."""
        packets = []
        target_size = (self.CLUSTER_SIZE_MIN + self.CLUSTER_SIZE_MAX) // 2
        for i in range(0, len(bullets), target_size):
            chunk = bullets[i:i + target_size]
            packet = Packet(
                index=len(packets),
                source_bullets=[b[0] for b in chunk],
                source_chapters=[b[1] for b in chunk],
            )
            packets.append(packet)
        return packets

    # ── Step 3: Generate packet content ───────────────────────────────

    def _generate_packet_content(self, packet: Packet, idx: int, total: int) -> None:
        """Generate paragraph + TL;DR (combined call), importance, validation.

        V13.19.0 changes:
        - Synthesis + TL;DR are produced in ONE LLM call (JSON output) —
          was 2 separate calls.
        - Q&A generation has been REMOVED entirely (per user request).
          ``packet.question`` is preserved for backward-compat but kept
          empty.
        - Importance is still a separate LLM call (1 call) — total 2 LLM
          calls per packet (was 4: synthesis + tldr + qa + importance).
        """
        bullets_text = "\n".join(f"- {b}" for b in packet.source_bullets)

        # V13.23.0: If this packet has supplementary context (exec summary
        # sentences for thin chapters), include it in the prompt so the LLM
        # has background to synthesize without hallucinating.  The bullets
        # remain the primary ground truth; the supplementary context fills
        # gaps when there aren't enough bullets.
        supp_context_block = ""
        if packet.supplementary_context:
            supp_text = "\n".join(f"- {s}" for s in packet.supplementary_context)
            supp_context_block = f"""

SUPPLEMENTARY CONTEXT (from the chapter's executive summary — use as background
to understand the bullets; do NOT treat these as primary bullets to synthesize):
{supp_text}
"""

        # Combined synthesis + TL;DR prompt — returns JSON.
        # V16.0.4: prompt moved to prompts/outputs/packets_synthesize.md.
        # The supplementary-context rule is injected conditionally — if the
        # packet has supplementary context, an extra rule line is included;
        # otherwise the rule line is empty (and the .md template trims it).
        supplementary_rule = (
            "- Use the SUPPLEMENTARY CONTEXT below as background to understand the bullets. You may draw framing from it, but every content sentence must still trace to a primary bullet.\n"
            if packet.supplementary_context else ""
        )
        from core.summarisation.prompt_manager import PromptManager
        _pm = PromptManager()
        combined_prompt = _pm.render_template(
            "outputs/packets_synthesize",
            bullets_text=bullets_text,
            supp_context_block=supp_context_block,
            supplementary_rule=supplementary_rule,
        )

        # Importance prompt
        importance_prompt = _pm.render_template(
            "outputs/packets_importance",
            bullets_text=bullets_text,
        )

        # Call LLM for combined synthesis + TL;DR (1 call) and importance (1 call).
        try:
            from utils.settings import Settings
            s = Settings()
            model = s.get("summarisation.model", "qwythos-9b-claude-mythos-5-1m-q4_k_m-empero-v3:latest")
            provider = s.get("summarisation.provider", "ollama")
            temperature = 0.1

            # V13.19.0 Fix 7: combined synthesis + TL;DR in ONE LLM call.
            combined_raw = self._call_llm(combined_prompt, model, provider, temperature)
            paragraph, tldr = self._parse_combined_response(combined_raw)

            # V13.21.0: Fix rendering bug — if the LLM didn't return a real
            # synthesis (paragraph is empty, too short, or just the bullets),
            # mark as validation failure so the bullet-list fallback kicks in
            # with the proper "⚠️ Synthesis failed" banner. Previously, the
            # fallback set paragraph=bullets_text, which then PASSED validation
            # (because bullets ARE in source), showing "✅ Validated" with no
            # actual synthesis — a misleading false positive.
            _synthesis_failed = False
            if not paragraph or len(paragraph) < 50 or paragraph.strip() == bullets_text.strip():
                _synthesis_failed = True
                paragraph = ""

            packet.paragraph = paragraph.strip() if paragraph else ""
            packet.tldr = (tldr or "").strip()

            # V13.19.0 Fix 1: Q&A removed entirely — keep field empty for
            # backward-compat with the QAPair/question consumers.
            packet.question = ""

            # Score importance
            importance = self._call_llm(importance_prompt, model, provider, 0.0)
            imp_clean = (importance or "").strip().lower()
            if "critical" in imp_clean:
                packet.importance = "critical"
            elif "important" in imp_clean:
                packet.importance = "important"
            else:
                packet.importance = "contextual"

            # Generate title from TL;DR or first few words
            if packet.tldr:
                packet.title = packet.tldr[:60] + ("..." if len(packet.tldr) > 60 else "")
            else:
                packet.title = f"Packet {idx + 1}"

            # V13.21.0: If synthesis failed (empty paragraph), skip validation
            # and go straight to bullet-list fallback. Don't run validation on
            # an empty paragraph — it would give a false "✅ Validated" stamp.
            if _synthesis_failed:
                packet.validation_passed = False
                packet.validation_details = "Synthesis empty or too short — using bullet-list fallback"
            else:
                # Validate (claim tracing)
                packet.validation_passed, packet.validation_details = self._validate_packet(packet)

            # Detect contradictions
            packet.has_tension, packet.tension_description = self._detect_tension(packet)

        except Exception as e:
            self.log(f"  ⚠️ Packet {idx+1} generation failed: {e}", "WARNING")
            packet.paragraph = bullets_text
            packet.title = f"Packet {idx + 1}"
            packet.tldr = ""
            packet.question = ""
            packet.validation_passed = False
            packet.validation_details = f"Generation error: {e}"

    def _parse_combined_response(self, raw: str | None) -> tuple[str, str]:
        """Parse the combined synthesis+TL;DR JSON response from the LLM.

        Accepts either:
        - A clean JSON object ``{"paragraph": "...", "tldr": "..."}``
        - A JSON object wrapped in ```json fences
        - A freeform response containing a paragraph and a TL;DR line

        Returns ``(paragraph, tldr)``.  On any parse failure returns
        ``(raw_text_or_empty, "")`` so the caller can decide whether to
        fall back to bullet-list mode.
        """
        if not raw:
            return "", ""

        # Strip <think> blocks first (some local models wrap responses)
        text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        # Strip markdown code fences if present
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if fence_match:
            text = fence_match.group(1)
        else:
            # Try to find a bare {...} block
            brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if brace_match:
                text = brace_match.group(0)

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                paragraph = str(obj.get("paragraph", "")).strip()
                tldr = str(obj.get("tldr", "")).strip()
                # Drop any nested quotes/escapes that survived json.loads
                if paragraph.startswith('"') and paragraph.endswith('"'):
                    paragraph = paragraph[1:-1]
                if tldr.startswith('"') and tldr.endswith('"'):
                    tldr = tldr[1:-1]
                return paragraph, tldr
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: try regex extraction of "paragraph" / "tldr" fields
        para_match = re.search(r'"paragraph"\s*:\s*"((?:[^"\\]|\\.)*)"', text, flags=re.DOTALL)
        tldr_match = re.search(r'"tldr"\s*:\s*"((?:[^"\\]|\\.)*)"', text, flags=re.DOTALL)
        if para_match or tldr_match:
            paragraph = para_match.group(1).encode().decode("unicode_escape") if para_match else ""
            tldr = tldr_match.group(1).encode().decode("unicode_escape") if tldr_match else ""
            return paragraph, tldr

        # Last-resort fallback: treat the whole response as the paragraph
        # (caller will run validation; if it fails, bullet-list fallback kicks in)
        return raw.strip(), ""

    def _apply_bullet_fallback(self, packet: Packet, idx: int) -> None:
        """V13.19.0 Fix 3: replace a failed packet's synthesis with bullet list.

        Called when ``packet.validation_passed == False``.  Replaces the
        paragraph with the source bullets formatted as a markdown list,
        prefixed with a clear ``⚠️ Synthesis failed validation`` banner so
        the user knows why this packet looks different.  The packet is
        NOT dropped — every source bullet remains visible.
        """
        bullets_md = "\n".join(f"- {b}" for b in packet.source_bullets)
        packet.paragraph = (
            "⚠️ Synthesis failed validation — showing source bullets instead.\n\n"
            f"{bullets_md}"
        )
        # Keep the existing title; clear the TL;DR so we don't show a
        # potentially-hallucinated one-liner next to the bullet list.
        if not packet.title:
            packet.title = f"Packet {idx + 1}"
        packet.tldr = ""
        packet.question = ""
        self.log(
            f"  ⚠️ Packet {idx+1}: synthesis failed validation — using bullet-list fallback",
            "WARNING",
        )

    def _parse_ollama_stream(self, resp) -> str:
        """Parse Ollama /api/generate NDJSON stream -> accumulated response text.

        V13.35.0: Restored streaming (was stream:False — a regression that
        made the (10,300) tuple timeout apply to total generation time
        instead of inter-chunk gaps). Each line is a JSON object with a
        ``response`` token and a ``done`` flag.
        """
        content = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                token = chunk.get("response", "")
                if token:
                    content += token
                if chunk.get("done", False):
                    break
            except (json.JSONDecodeError, ValueError):
                continue
        return content.strip()

    def _parse_openai_stream(self, resp) -> str:
        """Parse OpenAI-compatible SSE stream -> accumulated content text.

        Handles the ``data: {...}\\n\\n`` SSE format used by OpenAI, OpenRouter,
        and Ollama's /v1/chat/completions endpoint. Terminates on ``[DONE]``.
        """
        content = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            content += token
                except (json.JSONDecodeError, ValueError, IndexError):
                    continue
        return content.strip()

    def _call_llm(self, prompt: str, model: str, provider: str, temperature: float) -> str | None:
        """Call the LLM (Ollama or cloud) and return the response.

        V13.31.0: PERMANENT timeout fix. Uses (10, 300) tuple timeout + 1 retry.
        Uses native Ollama /api/generate for better long-generation handling.
        This fix has been lost 3 times by subagent rewrites — it is now
        written directly by the parent agent, not delegated.

        V13.35.0: Restored stream=True (lost regression). The tuple timeout
        (10s connect, 300s read) now applies to GAPS BETWEEN CHUNKS, not
        total generation time. This prevents false timeouts on long but
        healthy generations (Gemma 4 12B can take 4+ min for 8k tokens).
        """
        import requests

        from utils.settings import Settings
        s = Settings()

        timeout = (10, 300)  # 10s connect, 300s read
        max_retries = 2

        for attempt in range(max_retries):
            try:
                if provider == "cloud":
                    api_url = s.get("summarisation.api_base_url", "https://openrouter.ai/api/v1")
                    api_key = s.get("summarisation.api_key", "")
                    cloud_model = s.get("summarisation.cloud_model", model)
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    payload = {
                        "model": cloud_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "stream": True,
                    }
                    resp = requests.post(f"{api_url}/chat/completions", json=payload,
                                         headers=headers, timeout=timeout, stream=True)
                    resp.raise_for_status()
                    content = self._parse_openai_stream(resp)
                else:
                    # Ollama — use native /api/generate for better timeout handling
                    api_url = s.get("summarisation.endpoint", "http://localhost:11434/v1")
                    if "/v1" in api_url and "11434" in api_url:
                        native_url = api_url.replace("/v1", "") + "/api/generate"
                        payload = {
                            "model": model,
                            "prompt": prompt,
                            "stream": True,
                            "options": {"temperature": temperature},
                        }
                        resp = requests.post(native_url, json=payload, timeout=timeout, stream=True)
                        resp.raise_for_status()
                        content = self._parse_ollama_stream(resp)
                    else:
                        payload = {
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": temperature,
                            "stream": True,
                        }
                        resp = requests.post(f"{api_url}/chat/completions", json=payload,
                                             timeout=timeout, stream=True)
                        resp.raise_for_status()
                        content = self._parse_openai_stream(resp)

                # Strip <think> blocks
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                if content:
                    return content
                # V13.35.0: empty stream — fall through to retry (don't return "")
                self.log(f"    ⚠️ Empty stream response (attempt {attempt+1}/{max_retries})", "WARNING")

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    self.log(f"    ⏱️ LLM timeout (attempt {attempt+1}/{max_retries}), retrying...", "WARNING")
                    continue
                self.log(f"    ❌ LLM timed out after {max_retries} attempts", "WARNING")
                return None
            except Exception as e:
                self.log(f"    ❌ LLM call failed: {e}", "WARNING")
                return None

        return None

    # ── Step 3f: Validation ────────────────────────────────────────────

    # V13.22.0: Validation thresholds — tuned from real Gemma 4 12B output.
    # The old settings (0.50 similarity, 0 untraced allowed) caused a 78%
    # false-positive fallback rate: Gemma consistently writes 1 legitimate
    # "closing framing" sentence per paragraph (sim 0.22–0.46 to any single
    # bullet, because it synthesizes across ALL bullets). That sentence is
    # NOT hallucination — it's the synthesis we asked for.
    _VAL_SIM_THRESHOLD = 0.42   # was 0.50 — a traced sentence needs ≥ this to a bullet
    _VAL_MAX_UNTRACED = 1       # was 0 — allow 1 closing/framing sentence
    _VAL_MIN_TRACED_RATIO = 0.60  # at least 60% of sentences must trace

    def _validate_packet(self, packet: Packet) -> tuple[bool, str]:
        """Validate that the paragraph doesn't hallucinate beyond source bullets.

        V13.22.0: Relaxed from zero-tolerance to a 3-signal holistic check.
        A packet PASSES if ALL of:
          1. At least ``_VAL_MIN_TRACED_RATIO`` (60%) of sentences trace to a
             bullet at similarity ≥ ``_VAL_SIM_THRESHOLD`` (0.42).
          2. At most ``_VAL_MAX_UNTRACED`` (1) sentence is untraced — allows
             one legitimate closing/framing synthesis sentence.
          3. No untraced sentence has similarity below 0.20 (that would
             indicate real hallucination — invented content with no anchor).

        This fixes the 78% false-positive fallback rate observed with Gemma 4
        12B, where every paragraph had N good traced sentences + 1 closing
        summary sentence at ~0.30–0.45 sim — legitimate synthesis, not
        hallucination.
        """
        try:
            from sentence_transformers import SentenceTransformer  # noqa (kept for util)
            from core.llm.model_singletons import get_embed_model
            import numpy as np

            model = get_embed_model()  # V10.31.0 singleton

            # Split paragraph into sentences
            sentences = re.split(r"(?<=[.!?])\s+", packet.paragraph)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            if not sentences:
                return True, "No sentences to validate"

            # Encode sentences and source bullets
            sent_emb = model.encode(sentences, show_progress_bar=False)

            # V13.23.0: Validation traces against bullets + supplementary
            # context (exec summary sentences for thin chapters).  When
            # supplementary context is present, a sentence is "traced" if it
            # matches EITHER a bullet OR a supplementary sentence.
            validation_sources = list(packet.source_bullets)
            if packet.supplementary_context:
                validation_sources.extend(packet.supplementary_context)

            bullet_emb = model.encode(validation_sources, show_progress_bar=False)

            # Check each sentence's max similarity to any bullet (or supp context)
            traced = 0
            untraced = []
            hallucinated = []  # untraced AND very low sim — real hallucination
            for i, sent in enumerate(sentences):
                sims = np.dot(bullet_emb, sent_emb[i]) / (
                    np.linalg.norm(bullet_emb, axis=1) * np.linalg.norm(sent_emb[i]) + 1e-8
                )
                max_sim = float(np.max(sims))
                if max_sim >= self._VAL_SIM_THRESHOLD:
                    traced += 1
                else:
                    untraced.append((sent[:40], max_sim))
                    if max_sim < 0.20:
                        hallucinated.append((sent[:40], max_sim))

            n = len(sentences)
            traced_ratio = traced / n
            # V13.22.0 3-signal holistic pass:
            #   - enough sentences trace (≥60%)
            #   - at most 1 untraced (allows 1 closing framing sentence)
            #   - no sentence is a true hallucination (sim < 0.20)
            passed = (
                traced_ratio >= self._VAL_MIN_TRACED_RATIO
                and len(untraced) <= self._VAL_MAX_UNTRACED
                and len(hallucinated) == 0
            )
            details = f"{traced}/{n} sentences traced ({traced_ratio:.0%})"
            if untraced:
                details += " — untraced: " + ", ".join(
                    f"'{s}...' (sim: {m:.2f})" for s, m in untraced[:3]
                )
            if hallucinated:
                details += f" — ⚠ {len(hallucinated)} possible hallucination(s)"

            return passed, details
        except Exception as e:
            # V9.0.0 P1-6: on exception, return False (conservative — don't
            # pass validation just because the validator crashed).
            return False, f"Validation error ({e})"

    # ── Step 3g: Contradiction detection ──────────────────────────────

    def _detect_tension(self, packet: Packet) -> tuple[bool, str]:
        """Detect if source bullets contain contradictory information.

        V13.22.1: Lowered threshold from 0.30 → 0.15. The old 0.30 threshold
        flagged any two topically-different bullets as "tension" — e.g.,
        "Spot someone who wants to leave..." vs "Be professional and clear..."
        (sim 0.28) was flagged, but those aren't contradictory, just different
        topics. True contradictions (a claim vs its opposite) score well below
        0.15 because they share almost no semantic content. 0.15 catches real
        contradictions without the false-positive noise.
        """
        if len(packet.source_bullets) < 2:
            return False, ""

        try:
            from sentence_transformers import SentenceTransformer  # noqa (kept for util)
            from core.llm.model_singletons import get_embed_model
            import numpy as np

            model = get_embed_model()  # V10.31.0 singleton
            emb = model.encode(packet.source_bullets, show_progress_bar=False)

            # Check for low similarity pairs (potential contradictions)
            sims = np.dot(emb, emb.T) / (
                np.outer(np.linalg.norm(emb, axis=1), np.linalg.norm(emb, axis=1)) + 1e-8
            )

            # V13.22.1: Find pairs with similarity < 0.15 (potentially contradictory)
            # was 0.30 — too aggressive, flagged dissimilar-but-not-contradictory pairs
            tension_pairs = []
            for i in range(len(packet.source_bullets)):
                for j in range(i + 1, len(packet.source_bullets)):
                    if sims[i][j] < 0.15:
                        tension_pairs.append((
                            packet.source_bullets[i][:60],
                            packet.source_bullets[j][:60],
                            float(sims[i][j]),
                        ))

            if tension_pairs:
                desc = "; ".join(
                    f"'{a}...' vs '{b}...' (sim: {s:.2f})"
                    for a, b, s in tension_pairs[:2]
                )
                return True, desc

            return False, ""
        except Exception as _e:
            return False, ""

    # ── Step 4: Build hierarchy ────────────────────────────────────────

    def _build_hierarchy(self, packets: list[Packet]) -> None:
        """Group packets into concepts and themes.

        V13.23.0: In chapter-aligned mode, each packet has exactly one
        source_chapter (the author's own heading).  We use that directly as
        the concept name — no clustering needed.  This gives a naturally
        balanced, meaningful hierarchy where each chapter is its own concept
        node (fixes the V13.22.0 "lopsided map" problem where 14/18 packets
        landed under one concept).

        In cross-chapter mode, packets may have multiple source_chapters, so
        we fall back to semantic clustering of TL;DRs.
        """
        if not packets:
            return

        # V13.23.0: Chapter-aligned mode detection — if all packets have
        # exactly 1 source chapter, use the chapter heading as the concept.
        all_single_chapter = all(
            len(p.source_chapters) == 1 and p.source_chapters[0]
            for p in packets
        )
        if all_single_chapter:
            for packet in packets:
                chapter = packet.source_chapters[0]
                packet.concept = chapter
                packet.theme = "Main Theme"
            return

        # Cross-chapter mode: fall back to semantic clustering of TL;DRs
        try:
            from sentence_transformers import SentenceTransformer  # noqa (kept for util)
            from core.llm.model_singletons import get_embed_model
            import numpy as np
            from sklearn.cluster import AgglomerativeClustering

            model = get_embed_model()  # V10.31.0 singleton

            # Use TL;DRs (or titles) for clustering
            texts = [p.tldr or p.title or f"Packet {p.index}" for p in packets]
            emb = model.encode(texts, show_progress_bar=False)

            # Level 2: Concepts (group packets into ~5-10 concepts)
            n_concepts = min(len(packets) // 5, 10) if len(packets) > 10 else 1
            if n_concepts > 1:
                clustering = AgglomerativeClustering(n_clusters=n_concepts, metric="cosine", linkage="average")
                concept_labels = clustering.fit_predict(emb)

                # V9.0.0 P2-6: name each concept semantically using the
                # TL;DRs of its member packets (was "Concept 1/2/3…").
                concept_names: dict = {}
                for c in range(n_concepts):
                    member_tldrs = [packets[i].tldr for i in range(len(packets))
                                    if concept_labels[i] == c and packets[i].tldr]
                    if member_tldrs:
                        # Use the first 3 words of the first TL;DR as the label
                        words = member_tldrs[0].split()[:4]
                        concept_names[c] = " ".join(words)
                    else:
                        concept_names[c] = f"Concept {c + 1}"

                for i, packet in enumerate(packets):
                    packet.concept = concept_names.get(concept_labels[i], f"Concept {concept_labels[i] + 1}")

                # Level 1: Themes (group concepts into ~3-5 themes)
                concept_emb = []
                for c in range(n_concepts):
                    mask = concept_labels == c
                    concept_emb.append(np.mean(emb[mask], axis=0))
                concept_emb = np.array(concept_emb)

                n_themes = min(n_concepts // 2, 5) if n_concepts > 2 else 1
                if n_themes > 1:
                    theme_clustering = AgglomerativeClustering(n_clusters=n_themes, metric="cosine", linkage="average")
                    theme_labels = theme_clustering.fit_predict(concept_emb)

                    # V9.0.0 P2-6: name themes semantically too
                    theme_names: dict = {}
                    for t in range(n_themes):
                        # Find the first concept in this theme and use its name
                        for c in range(n_concepts):
                            if theme_labels[c] == t:
                                theme_names[t] = concept_names.get(c, f"Theme {t + 1}")
                                break

                    for i, packet in enumerate(packets):
                        concept_idx = concept_labels[i]
                        packet.theme = theme_names.get(
                            theme_labels[concept_idx], f"Theme {theme_labels[concept_idx] + 1}"
                        )
                else:
                    for packet in packets:
                        packet.theme = "Main Theme"
            else:
                for packet in packets:
                    packet.concept = "Core Concepts"
                    packet.theme = "Main Theme"

        except Exception as e:
            self.log(f"  ⚠️ Hierarchy building failed ({e}) — using flat structure", "DEBUG")
            for packet in packets:
                packet.concept = "Core Concepts"
                packet.theme = "Main Theme"

    # ── Step 5: Cross-references ──────────────────────────────────────

    def _generate_cross_refs(self, packets: list[Packet]) -> None:
        """Find related packets and add cross-references."""
        if len(packets) < 2:
            return

        try:
            from sentence_transformers import SentenceTransformer  # noqa (kept for util)
            from core.llm.model_singletons import get_embed_model
            import numpy as np

            model = get_embed_model()  # V10.31.0 singleton
            texts = [p.tldr or p.title for p in packets]
            emb = model.encode(texts, show_progress_bar=False)

            # Compute pairwise similarities
            sims = np.dot(emb, emb.T) / (
                np.outer(np.linalg.norm(emb, axis=1), np.linalg.norm(emb, axis=1)) + 1e-8
            )

            # For each packet, find top 3 most similar (excluding itself)
            for i, packet in enumerate(packets):
                sim_scores = [(j, float(sims[i][j])) for j in range(len(packets)) if j != i]
                sim_scores.sort(key=lambda x: x[1], reverse=True)
                packet.cross_refs = [j for j, s in sim_scores[:3] if s > 0.5]

        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)  # Cross-references are nice-to-have

    # ── Step 6: One-page distillation ──────────────────────────────────

    def _generate_one_page(self, packets: list[Packet], book_title: str) -> str:
        """Generate a one-page distillation from all packets.

        V13.21.0: Fixed the broken fallback. Previously, when packets had
        no TL;DR (bullet-list fallback), the one-page showed empty bullets.
        Now uses packet titles + first source bullet as context when TL;DR
        is missing. Also sends richer context to the LLM (titles + TL;DRs
        + key bullets) so the theme synthesis works even with partial data.
        """
        # V13.21.0: Build rich context — use TL;DR if available, otherwise
        # use the packet title + first 2 source bullets.
        packet_summaries = []
        for p in packets:
            if p.tldr:
                packet_summaries.append(f"- [{p.title}] {p.tldr}")
            elif p.source_bullets:
                # Use first 2 source bullets as context
                first_two = "; ".join(p.source_bullets[:2])
                packet_summaries.append(f"- [{p.title}] {first_two[:150]}")
            else:
                packet_summaries.append(f"- [{p.title}]")

        all_summaries_text = "\n".join(packet_summaries)
        n_packets = len(packets)

        from core.summarisation.prompt_manager import PromptManager
        _pm = PromptManager()
        prompt = _pm.render_template(
            "outputs/packets_distillation",
            book_title=book_title,
            n_packets=n_packets,
            all_summaries_text=all_summaries_text,
        )

        try:
            from utils.settings import Settings
            s = Settings()
            model = s.get("summarisation.model", "")
            provider = s.get("summarisation.provider", "ollama")
            response = self._call_llm(prompt, model, provider, 0.2)

            if response and len(response) > 150 and "##" in response:
                header = f"# 📖 One-Page Distillation: {book_title}"
                footer = (
                    f"\n\n---\n*Synthesized from {n_packets} packets*"
                )
                return f"{header}\n\n{response}{footer}"
        except Exception as _e:
            logger.debug("one-page synthesis failed: %s: %s", type(_e).__name__, _e)

        # V13.21.0: Improved fallback — shows packet titles + key bullets
        # instead of empty TL;DR lines. Still useful even without LLM synthesis.
        lines = [f"# 📖 One-Page Distillation: {book_title}", ""]
        lines.append(f"**{n_packets} knowledge packets** from this source.")
        lines.append("")
        lines.append("## Packet Overview")
        lines.append("")
        for p in packets:
            icon = {"critical": "🔴", "important": "🟡", "contextual": "🟢"}.get(p.importance, "🟢")
            if p.tldr:
                lines.append(f"{icon} **{p.title}** — {p.tldr}")
            elif p.source_bullets:
                first = p.source_bullets[0][:100]
                lines.append(f"{icon} **{p.title}** — {first}...")
            else:
                lines.append(f"{icon} **{p.title}**")
        lines.append("")
        lines.append("---")
        lines.append("*Theme synthesis unavailable — showing packet overview. "
                     "Re-run with a faster model for full distillation.*")
        return "\n".join(lines)

    # ── Step 8: Write output files ────────────────────────────────────

    def _write_full_document(self, collection: PacketCollection, path: Path) -> None:
        """Write the full Packets of Knowledge document."""
        lines = []
        lines.append(f"# 📦 Packets of Knowledge: {collection.book_title}")
        lines.append("")
        lines.append(f"**{collection.total_packets} packets** synthesized from "
                     f"**{collection.total_bullets} keypoints** across "
                     f"**{len(collection.themes)} themes** and "
                     f"**{len(collection.concepts)} concepts**.")
        lines.append(f"Generated in {collection.generation_time_s:.1f}s")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Group by theme → concept → packets
        themes = sorted(set(p.theme for p in collection.packets if p.theme))
        for theme in themes:
            theme_packets = [p for p in collection.packets if p.theme == theme]
            lines.append(f"# 🌳 {theme}")
            lines.append("")

            concepts = sorted(set(p.concept for p in theme_packets if p.concept))
            for concept in concepts:
                concept_packets = [p for p in theme_packets if p.concept == concept]
                lines.append(f"## 📋 {concept}")
                lines.append("")

                for packet in concept_packets:
                    lines.append(self._format_packet(packet))
                    lines.append("---")
                    lines.append("")

        # Reader's Journey at the end
        lines.append("# 🗺️ Reader's Journey")
        lines.append("")
        lines.append("A suggested reading path through the packets:")
        lines.append("")

        # Sort by importance (critical first)
        importance_order = {"critical": 0, "important": 1, "contextual": 2}
        sorted_packets = sorted(collection.packets, key=lambda p: importance_order.get(p.importance, 3))

        for i, packet in enumerate(sorted_packets[:20]):
            next_packet = sorted_packets[i + 1] if i + 1 < len(sorted_packets) else None
            lines.append(f"**{i+1}.** [{packet.title}]")
            if next_packet:
                lines.append(f"   → Next: [{next_packet.title}]")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")

    def _format_packet(self, packet: Packet) -> str:
        """Format a single packet as markdown.

        V13.19.0 Fix 1: Q&A section removed entirely (was ``**Q: ...**``).
        """
        lines = []
        importance_icon = {"critical": "🔴", "important": "🟡", "contextual": "🟢"}
        icon = importance_icon.get(packet.importance, "🟢")

        lines.append(f"### 📦 Packet {packet.index + 1}: {packet.title}")
        lines.append(f"**{icon} {packet.importance.title()}**")
        lines.append("")

        if packet.tldr:
            lines.append(f"**TL;DR:** {packet.tldr}")
            lines.append("")

        # V13.19.0 Fix 1: Q&A section removed (was: ``**Q: {packet.question}**``)

        lines.append(packet.paragraph)
        lines.append("")

        if packet.has_tension:
            lines.append(f"**⚠️ TENSION POINT:** {packet.tension_description}")
            lines.append("")

        # Source bullets (collapsible)
        lines.append("<details>")
        lines.append(f"<summary>Source bullets ({len(packet.source_bullets)})</summary>")
        lines.append("")
        for b in packet.source_bullets:
            lines.append(f"- {b}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # Validation
        if packet.validation_passed:
            lines.append(f"*✅ Validated: {packet.validation_details}*")
        else:
            lines.append(f"*⚠️ Validation: {packet.validation_details}*")
        lines.append("")

        # Cross-references (Obsidian wikilinks)
        if packet.cross_refs:
            refs = ", ".join(f"[[Packet {r+1}]]" for r in packet.cross_refs)
            lines.append(f"**🔗 Connects to:** {refs}")
            lines.append("")

        return "\n".join(lines)

    # ── Step 9: Knowledge map (Mermaid) ───────────────────────────────

    @staticmethod
    def _sanitize_mermaid_id(raw: str, prefix: str = "n") -> str:
        """V13.19.0 Fix 6: sanitize a string into a valid Mermaid node ID.

        Mermaid node IDs must be alphanumeric + underscore and cannot
        start with a digit.  Commas, punctuation, and spaces break the
        parser.  This function:
        - lowercases
        - replaces every non-alphanumeric char with ``_``
        - collapses runs of ``_`` into a single ``_``
        - truncates to 30 chars (Mermaid prefers short IDs)
        - prepends ``prefix`` if the result starts with a digit
        - falls back to ``prefix`` alone if the result is empty
        """
        if not raw:
            return prefix
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
        if not cleaned:
            return prefix
        cleaned = cleaned[:30]
        if cleaned[0].isdigit():
            cleaned = f"{prefix}_{cleaned}"
        return cleaned

    def _write_knowledge_map(self, collection: PacketCollection, path: Path) -> None:
        """Write a Mermaid knowledge map showing packet relationships.

        V13.19.0 Fix 6: node IDs are sanitized (alphanumeric + underscore,
        ≤30 chars) so commas / punctuation no longer break Mermaid syntax.
        Also uses concept-level nodes (Theme → Concept → Packets) with
        meaningful edge labels.
        """
        lines = ["# Knowledge Map", ""]
        lines.append("```mermaid")
        lines.append("graph TD")

        # V13.19.0 Fix 6: build a single theme_name → sanitized ID map
        # upfront and reuse it everywhere.  This guarantees that two
        # packets sharing the same theme name link to the same node,
        # AND that two different theme names that sanitize to the same
        # ID don't silently collide.
        theme_name_to_id: dict[str, str] = {}
        used_theme_ids: set = set()
        for theme in collection.themes:
            tid = self._sanitize_mermaid_id(theme, prefix="t")
            base = tid
            n = 2
            while tid in used_theme_ids:
                tid = f"{base}_{n}"
                n += 1
            used_theme_ids.add(tid)
            theme_name_to_id[theme] = tid
            label = theme.replace('"', "'")
            lines.append(f'    {tid}["{label}"]')

        # ── Concept nodes + Theme→Concept edges ──
        # V13.19.0 Fix 6: track concept NAME → sanitized ID so packets
        # sharing the same concept name reuse the same node (was emitting
        # duplicate core_concepts_2/_3/_4 nodes for the same concept).
        concept_name_to_id: dict[str, str] = {}
        theme_concept_edges: set = set()  # avoid duplicate edges
        for packet in collection.packets:
            if not packet.concept:
                continue
            if packet.concept in concept_name_to_id:
                cid = concept_name_to_id[packet.concept]
            else:
                cid = self._sanitize_mermaid_id(packet.concept, prefix="c")
                # Ensure uniqueness across DIFFERENT concept names that
                # sanitize to the same ID (e.g. "AI/ML" and "AI-ML").
                base = cid
                n = 2
                while cid in concept_name_to_id.values():
                    cid = f"{base}_{n}"
                    n += 1
                concept_name_to_id[packet.concept] = cid
                label = packet.concept.replace('"', "'")
                lines.append(f'    {cid}["{label}"]')

            if packet.theme and packet.theme in theme_name_to_id:
                tid = theme_name_to_id[packet.theme]
                edge_key = (tid, cid)
                if edge_key not in theme_concept_edges:
                    theme_concept_edges.add(edge_key)
                    lines.append(f'    {tid} -->|contains| {cid}')

        # ── Packet nodes + Concept→Packet edges ──
        concept_packet_edges: set = set()
        for packet in collection.packets:
            pid = f"P{packet.index}"
            title = (packet.title or f"Packet {packet.index + 1}").replace('"', "'")
            # Truncate label to keep map readable
            short_title = title[:40] + ("…" if len(title) > 40 else "")
            lines.append(f'    {pid}["P{packet.index + 1}: {short_title}"]')

            if packet.concept and packet.concept in concept_name_to_id:
                cid = concept_name_to_id[packet.concept]
                edge_key = (cid, pid)
                if edge_key not in concept_packet_edges:
                    concept_packet_edges.add(edge_key)
                    lines.append(f'    {cid} -->|packet| {pid}')

        # ── Cross-reference edges (dotted) ──
        for packet in collection.packets:
            for ref in packet.cross_refs:
                if 0 <= ref < len(collection.packets):
                    lines.append(f"    P{packet.index} -.-> P{ref}")

        lines.append("```")
        path.write_text("\n".join(lines), encoding="utf-8")

    # ── Step 10: Coverage report (V13.19.0 Fix 4) ────────────────────

    def _write_coverage_report(
        self,
        collection: PacketCollection,
        original_bullets: list[tuple[str, str]],
        original_count: int,
        dedup_count: int,
        path: Path,
    ) -> None:
        """Write a coverage report mapping every input bullet → packet + status.

        V13.19.0 Fix 4: previously the user had no way to see which input
        bullets were lost (45% of packets were silently dropped).  This
        report lists every input bullet (post-dedup) alongside the packet
        number it ended up in and whether that packet was synthesized or
        fell back to bullet-list mode.
        """
        bullets_in_packets = sum(len(p.source_bullets) for p in collection.packets)
        synthesized = sum(1 for p in collection.packets if p.validation_passed)
        fallback = len(collection.packets) - synthesized
        coverage_pct = (
            100.0 * bullets_in_packets / max(1, dedup_count)
        )

        # Build a lookup: bullet_text → (packet_index, status)
        # If the same bullet text appears in multiple packets (shouldn't
        # happen post-dedup but be defensive), pick the first.
        bullet_to_packet: dict[str, tuple[int, str]] = {}
        for p in collection.packets:
            for b in p.source_bullets:
                if b not in bullet_to_packet:
                    status = "✅ Synthesized" if p.validation_passed else "⚠️ Bullet-list fallback"
                    bullet_to_packet[b] = (p.index + 1, status)

        lines: list[str] = []
        lines.append(f"# Coverage Report — {collection.book_title}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Input bullets (raw): {original_count}")
        if original_count != dedup_count:
            removed = original_count - dedup_count
            lines.append(f"- Removed as duplicates: {removed}")
        lines.append(f"- Input bullets (post-dedup): {dedup_count}")
        lines.append(
            f"- Bullets in packets: {bullets_in_packets} "
            f"({coverage_pct:.1f}% of post-dedup)"
        )
        lines.append(f"- Packets generated: {len(collection.packets)}")
        lines.append(f"- Packets with synthesis: {synthesized}")
        lines.append(f"- Packets with bullet-list fallback: {fallback}")
        lines.append("")
        lines.append("## Bullet → Packet Mapping")
        lines.append("")
        lines.append("| # | Bullet (first 60 chars) | Packet # | Status |")
        lines.append("|---|------------------------|----------|--------|")

        for i, (bullet, _chapter) in enumerate(original_bullets, start=1):
            short = bullet[:60].replace("|", "\\|")
            if bullet in bullet_to_packet:
                pkt_num, status = bullet_to_packet[bullet]
                pkt_str = str(pkt_num)
            else:
                # Bullet was dropped (shouldn't happen post-V13.19.0 —
                # every bullet should land in some packet via orphans
                # handling).  Surface it explicitly so the user can see.
                pkt_str = "—"
                status = "❌ Not in any packet"
            lines.append(f"| {i} | {short} | {pkt_str} | {status} |")

        # Orphan bullets (in packets but not in original list — shouldn't happen)
        orphan_lines: list[str] = []
        for p in collection.packets:
            for b in p.source_bullets:
                if b not in {orig_b for orig_b, _ in original_bullets}:
                    orphan_lines.append(
                        f"- Packet {p.index + 1}: {b[:60]}…"
                    )
        if orphan_lines:
            lines.append("")
            lines.append("## ⚠️ Orphan bullets (in packets but not in input)")
            lines.extend(orphan_lines[:20])

        path.write_text("\n".join(lines), encoding="utf-8")
