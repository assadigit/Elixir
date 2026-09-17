"""Keypoints Builder – extracts and formats key takeaways from chapter summaries.

Creates two output files:
  - [BookName].Keypoints.md        – bullet-point list of all key takeaways.
  - [BookName].Keypoints.docx      – styled DOCX version.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Inches, Pt

from core.models import SummaryResult


class KeypointsBuilder:
    def __init__(
        self,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.log = log_callback or (lambda msg, level="INFO": None)
        # V18.20.3.10 (W11): the FINAL (deduped) keypoint count of the last
        # build() — exposed so callers can report the number that actually
        # shipped in the keypoints file instead of the raw bullet count
        # (the library previously recorded the raw count: 41 vs the file's
        # 36, the .3.7 SWOT's W11). None until build() runs.
        self.final_keypoint_count: int | None = None

    def build(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
        segments: list | None = None,
        concepts: list[str] | None = None,
        judge_results: list[Any] | None = None,
    ) -> tuple[Path | None, Path | None]:
        """
        Build keypoints files from chapter summaries.

        V3.4.1: Added segments + concepts params for J1 (ordering), K1 (confidence),
        K2 (source excerpts), and H2 (page traceability).

        V10.1.0: Added judge_results param.  When the Content Judge ran with
        Layer 8 (langextract) grounding, each JudgeResult carries a
        ``bullet_evidence`` dict mapping bullet-text → verbatim source
        snippet.  Keypoints that have a Layer 8 evidence span get a 🛡️
        "verified" badge and the snippet is shown as the source citation
        (replacing the heuristic excerpt).  This turns keypoints from
        "trust me" into "verify me" — directly addressing the "life or
        money at stake" requirement for scientific articles.

        Args:
            summaries: List of SummaryResult objects.
            book_title: Title of the book (used for file naming).
            output_dir: Output directory.
            segments: Optional list of Segment objects (for source text + page markers).
            concepts: Optional list of extracted concepts (for confidence scoring).
            judge_results: Optional list of JudgeResult objects (one per summary,
                in the same order).  When supplied, bullet_evidence is used to
                enhance the DOCX with verified-source citations.

        Returns:
            (md_path, docx_path) – paths to the generated files, or None if no keypoints.
        """
        # Collect all bullet points from summaries
        all_bullets = []
        for summ in summaries:
            if summ.success and summ.bullet_points:
                all_bullets.extend(summ.bullet_points)

        # V18.20.3.10 (W11): record the count that will actually ship —
        # set here to the raw count, updated after the dedup pass below,
        # so the library/diagnostic can never disagree with the file.
        self.final_keypoint_count = len(all_bullets)

        if not all_bullets:
            self.log("  ℹ️ No keypoints found to build.", "INFO")
            return None, None

        # Remove duplicates (preserve order) — cross-chapter dedup:
        # V3.3.0 C3: Added embedding-based dedup using sentence-transformers
        # if available. Falls back to rapidfuzz 75% if not installed.
        # Embedding dedup catches semantic duplicates that string matching
        # misses: "Use signature greetings to create rapport" vs "A signature
        # greeting technique builds immediate rapport" (rapidfuzz ~60%, but
        # cosine similarity >0.85).
        #
        # V10.32.0 (Sprint 4 s2): The rapidfuzz fallback path now delegates
        # to DedupService.dedup_bullets().  The embedding path stays inline
        # (it's a different algorithm — cosine similarity vs token_set_ratio).
        try:
            from rapidfuzz import fuzz
            _has_rf = True
        except ImportError:
            _has_rf = False

        # V3.3.0 C3: Try to load sentence-transformers for embedding dedup.
        # V10.31.0 (Sprint 4.6): use the shared singleton instead of reloading
        # the model on every call (was 20 reloads for a 20-chapter book).
        _has_embeddings = False
        _embed_model = None
        try:
            from core.llm.model_singletons import get_embed_model
            _embed_model = get_embed_model()
            if _embed_model is not None:
                _has_embeddings = True
                # V18.20.3.4 (audit v182033 non-defect note): name the ACTUAL
                # backend in the log. The old message hardcoded
                # "sentence-transformers loaded" even when the singleton had
                # resolved an Ollama embedder (nomic-embed-text via
                # OllamaEmbedBackend) — the V18.20.3.3 rig log said ST while
                # the summarisation embedder ran Ollama, which read as an
                # inconsistency with the pre-flight ST skip. The singleton
                # picks the backend from settings.embedding.model; when the
                # backend can't initialize (ST absent AND the Ollama model
                # not pulled), get_embed_model returns None and this stage
                # falls back to the rapidfuzz dedup below — graceful by
                # design, no sentence-transformers dependency required.
                _embed_backend = type(_embed_model).__name__
                self.log(
                    f"  🧠 Embedding dedup: embedder ready (shared singleton, "
                    f"backend={_embed_backend})",
                    "DEBUG",
                )
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)  # not installed — fall back to rapidfuzz

        seen_norms: list = []
        seen_embeddings: list = []  # for C3 embedding dedup
        unique_bullets = []
        dedup_dropped = 0
        dropped_details: list = []  # V13.26.0: for audit logging
        for bp in all_bullets:
            if not bp or len(bp.strip()) < 2:
                continue
            # Normalize: lowercase, collapse whitespace, keep digits and %, $, /
            norm = re.sub(r'\s+', ' ', bp.lower().strip())
            norm = re.sub(r'[^\w\s%$/\-]', '', norm)  # keep word chars, spaces, %, $, /, -

            # Exact dedup
            if norm in seen_norms:
                dedup_dropped += 1
                dropped_details.append(f"  🗑️ '{bp[:60]}...' (exact match)")
                continue

            # V3.3.0 C3: Embedding-based dedup (if available)
            # V18.2.25 (Phase 3.3 wiring): use cached_encode so the same
            # bullet text isn't re-encoded across runs. This was the crash
            # site in V18.2.21 (encode() raised EmbedderUnavailable → fatal).
            # V18.2.23 fixed encode() to return zeros (fail-safe), and now
            # we also cache to avoid redundant encode calls entirely.
            if _has_embeddings and _embed_model:
                import numpy as np

                from core.llm.embedding_cache import cached_encode
                bp_embedding = cached_encode(_embed_model, [bp])[0]
                is_dup = False
                for existing_emb in seen_embeddings:
                    # Cosine similarity
                    sim = np.dot(bp_embedding, existing_emb) / (
                        np.linalg.norm(bp_embedding) * np.linalg.norm(existing_emb) + 1e-8
                    )
                    if sim > 0.85:  # semantic duplicate threshold
                        is_dup = True
                        break
                if is_dup:
                    dedup_dropped += 1
                    dropped_details.append(f"  🗑️ '{bp[:60]}...' (embedding sim > 0.85)")
                    continue
                seen_embeddings.append(bp_embedding)
            elif _has_rf:
                # V10.32.0 (Sprint 4 s2): Delegate the rapidfuzz check to
                # DedupService so the threshold + algorithm are unified.
                # V3.9.2: Cross-chapter dedup uses a FIXED 75% threshold.
                from core.summarisation.dedup_service import WITHIN_CHAPTER_THRESHOLD
                is_dup = False
                for existing in seen_norms:
                    if fuzz.token_set_ratio(norm, existing) >= WITHIN_CHAPTER_THRESHOLD:
                        is_dup = True
                        break
                if is_dup:
                    dedup_dropped += 1
                    dropped_details.append(f"  🗑️ '{bp[:60]}...' (rapidfuzz >= 75%)")
                    continue

            seen_norms.append(norm)
            unique_bullets.append(bp)

        if dedup_dropped > 0:
            # V13.26.0 (P1.6): Log at INFO (was DEBUG) + list dropped bullets
            self.log(
                f"  🧹 Keypoints dedup: removed {dedup_dropped} duplicate(s) "
                f"({len(all_bullets)} → {len(unique_bullets)} keypoints)",
                "INFO",
            )
            for detail in dropped_details[:15]:
                self.log(detail, "DEBUG")
            if len(dropped_details) > 15:
                self.log(f"  ... and {len(dropped_details) - 15} more", "DEBUG")

        if not unique_bullets:
            self.log("  ℹ️ No unique keypoints after filtering.", "INFO")
            return None, None

        # V18.20.3.10 (W11): the deduped count is the number that ships in
        # the keypoints file — final value for callers (library/diagnostic).
        self.final_keypoint_count = len(unique_bullets)

        # V3.4.1 J1: Order bullets by topic clustering for structured readability
        try:
            from core.summarisation.text_preprocessor import order_bullets_by_topic
            ordered_bullets = order_bullets_by_topic(unique_bullets)
            self.log("  📑 J1: Bullets reordered by topic clustering", "DEBUG")
        except Exception as _e:
            ordered_bullets = unique_bullets

        # V3.4.1 K1+K2+H2: Compute confidence scores, source excerpts, and page citations
        source_text = ""
        page_markers = None
        all_concepts = concepts or []
        if segments:
            source_text = " ".join(s.content for s in segments)
            # Try to get page markers from segments
            try:
                page_markers = [(s.start_page, s.start_page) for s in segments if hasattr(s, 'start_page')]
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Compute per-bullet metadata
        # V10.1.0: Build a global evidence lookup from judge_results.
        # Each JudgeResult.bullet_evidence maps bullet-text → verbatim source
        # snippet (from langextract char_interval).  When a bullet has a
        # Layer 8 evidence span, we use it INSTEAD of the heuristic excerpt
        # and mark the bullet as "verified" so the DOCX renderer can show
        # a 🛡️ badge.
        evidence_lookup = {}  # bullet_text_normalized → (snippet, verified_bool)
        l8_active = False
        if judge_results:
            for jr in judge_results:
                if jr is None:
                    continue
                if getattr(jr, "grounding_layer8_available", False):
                    l8_active = True
                be = getattr(jr, "bullet_evidence", {}) or {}
                for bp_text, snippet in be.items():
                    if snippet:
                        # Normalize the key the same way bullets are compared
                        norm = re.sub(r'\s+', ' ', bp_text.lower().strip())
                        evidence_lookup[norm] = (snippet, True)

        bullet_metadata = []
        try:
            from core.summarisation.text_preprocessor import (
                classify_bullet,
                compute_bullet_confidence,
                find_source_excerpt,
                find_source_page,
            )
            verified_count = 0
            for bp in ordered_bullets:
                confidence = compute_bullet_confidence(bp, source_text, all_concepts) if source_text else 50
                excerpt = find_source_excerpt(bp, source_text) if source_text else None
                page = find_source_page(bp, source_text, page_markers) if page_markers else None
                # V3.6.0: Classify bullet as core/supporting/additional
                classification = classify_bullet(bp, all_concepts, source_text)
                # V10.1.0: Layer 8 evidence lookup
                bp_norm = re.sub(r'\s+', ' ', bp.lower().strip())
                l8_evidence = evidence_lookup.get(bp_norm)
                verified = False
                if l8_evidence:
                    # Verbatim span wins over heuristic excerpt
                    excerpt = l8_evidence[0]
                    verified = True
                    verified_count += 1
                    # Layer 8 verification is the strongest confidence signal
                    # — bump confidence toward 100 (floor at 85 so a verified
                    # bullet never shows as "low confidence").
                    confidence = max(confidence, 85)
                bullet_metadata.append({
                    "text": bp,
                    "confidence": confidence,
                    "excerpt": excerpt,
                    "page": page,
                    "classification": classification,
                    "verified": verified,  # V10.1.0
                })
            core_count = sum(1 for b in bullet_metadata if b["classification"] == "core")
            supp_count = sum(1 for b in bullet_metadata if b["classification"] == "supporting")
            addl_count = sum(1 for b in bullet_metadata if b["classification"] == "additional")
            self.log(
                f"  🎯 K1+Classification: {len(bullet_metadata)} bullets — "
                f"{core_count} core, {supp_count} supporting, {addl_count} additional"
                + (f" | 🛡️ {verified_count} Layer-8 verified" if l8_active else ""),
                "INFO",
            )
        except Exception:
            # Fallback: no metadata
            bullet_metadata = [{"text": bp, "confidence": 50, "excerpt": None, "page": None,
                               "classification": "additional", "verified": False}
                              for bp in ordered_bullets]

        # Generate Markdown
        md_path = output_dir / f"{book_title}.Keypoints.md"
        md_content = self._build_markdown(book_title, [b["text"] for b in bullet_metadata])
        # V9.3.1 fix: ensure the output directory exists (lazy-folder system
        # may not have created it yet if keypoints is the first output to write here).
        md_path.parent.mkdir(parents=True, exist_ok=True)
        from utils.atomic_io import atomic_write_text
        try:
            atomic_write_text(md_path, md_content)
        except OSError as _owe:
            # V10.4.0 (Phase 6A-4): Surface disk-full with a clear message.
            # Re-raise — the converter's per-output handler catches this and
            # marks keypoints as failed (graceful degradation); the user sees
            # an actionable message in the output-results summary instead of
            # a raw ``[Errno 28]`` traceback.
            if _owe.errno == 28 or "No space left" in str(_owe):
                raise OSError(
                    f"Disk is full — cannot write keypoints MD "
                    f"({md_path.name}). Free space on {md_path.anchor}. "
                    f"Original error: {_owe}"
                ) from _owe
            raise
        self.log(f"  📌 Keypoints MD → {md_path}", "INFO")

        # Generate DOCX (with K1 confidence indicators + K2 source excerpts)
        docx_path = output_dir / f"{book_title}.Keypoints.docx"
        self._build_docx_enhanced(book_title, bullet_metadata, docx_path)
        self.log(f"  📌 Keypoints DOCX → {docx_path}", "INFO")

        return md_path, docx_path

    def _build_markdown(self, book_title: str, bullets: list[str]) -> str:
        """Build Markdown content."""
        lines = [
            f"# Keypoints: {book_title}",
            "",
            f"**Total keypoints:** {len(bullets)}",
            "",
            "---",
            "",
        ]
        for i, bp in enumerate(bullets, 1):
            lines.append(f"{i}. {bp}")
            lines.append("")  # blank line after each keypoint
            lines.append("")  # extra blank line for readability spacing
            lines.append("")  # V3.4.2: third blank line for more line height
        return "\n".join(lines)

    def _build_docx(self, book_title: str, bullets: list[str], docx_path: Path) -> None:
        """Build DOCX document."""
        doc = Document()

        # Title
        title = doc.add_heading(f"Keypoints: {book_title}", level=0)
        title.alignment = 1  # center

        # Metadata
        p = doc.add_paragraph(f"Total keypoints: {len(bullets)}")
        p.paragraph_format.space_after = Pt(12)

        # Bullets
        for bp in bullets:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(bp)
            run.font.size = Pt(11)
            run.font.name = "Helvetica"
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_after = Pt(20)  # V3.4.2: increased from 14 → 20 for more line height

        doc.save(str(docx_path))

    def _build_docx_enhanced(self, book_title: str, bullet_metadata: list[dict], docx_path: Path) -> None:
        """V3.4.1 K1+K2+H2 + V3.4.2 K3: Build DOCX with confidence indicators,
        source excerpts, page citations, and progressive disclosure structure."""
        from docx.shared import RGBColor

        doc = Document()

        # V3.4.2 K3: Progressive disclosure — use heading levels for collapsible structure
        # Title (Level 0 — always visible)
        title = doc.add_heading(f"Keypoints: {book_title}", level=0)
        title.alignment = 1  # center

        # Metadata
        p = doc.add_paragraph(f"Total keypoints: {len(bullet_metadata)}")
        p.paragraph_format.space_after = Pt(12)

        # Legend (Level 2 heading — collapsible in Word)
        legend_heading = doc.add_heading("Legend", level=2)
        legend = doc.add_paragraph()
        # V10.1.0: added 🛡️ verified line when Layer 8 grounding is active
        verified_total = sum(1 for m in bullet_metadata if m.get("verified"))
        legend_text = (
            "Confidence: 🟢 High (80-100)  🟡 Medium (50-79)  🔴 Low (<50)\n"
            "Classification: ★ Core Concept  ◆ Supporting Detail  ○ Additional Insight"
        )
        if verified_total > 0:
            legend_text += (
                "\n🛡️ Verified = verbatim source span confirmed by "
                "langextract (Layer 8 grounding)"
            )
        legend_run = legend.add_run(legend_text)
        legend_run.font.size = Pt(9)
        legend_run.font.italic = True
        legend_run.font.color.rgb = RGBColor(150, 150, 150)
        legend.paragraph_format.space_after = Pt(16)

        # V3.6.0: Group bullets by classification — Core first, then Supporting, then Additional
        core_bullets = [m for m in bullet_metadata if m.get("classification") == "core"]
        supporting_bullets = [m for m in bullet_metadata if m.get("classification") == "supporting"]
        additional_bullets = [m for m in bullet_metadata if m.get("classification") == "additional"]

        # Core Concepts (Level 1 heading)
        if core_bullets:
            doc.add_heading(f"★ Core Concepts ({len(core_bullets)})", level=1)
            for meta in core_bullets:
                self._add_bullet_to_docx(doc, meta)

        # Supporting Details (Level 1 heading)
        if supporting_bullets:
            doc.add_heading(f"◆ Supporting Details ({len(supporting_bullets)})", level=1)
            for meta in supporting_bullets:
                self._add_bullet_to_docx(doc, meta)

        # Additional Insights (Level 1 heading)
        if additional_bullets:
            doc.add_heading(f"○ Additional Insights ({len(additional_bullets)})", level=1)
            for meta in additional_bullets:
                self._add_bullet_to_docx(doc, meta)

        doc.save(str(docx_path))

    def _add_bullet_to_docx(self, doc, meta: dict) -> None:
        """V3.6.0: Add a single bullet with confidence + source excerpt to DOCX."""
        from docx.shared import RGBColor

        bp = meta["text"]
        confidence = meta.get("confidence", 50)
        excerpt = meta.get("excerpt")
        page = meta.get("page")

        # Confidence indicator
        if confidence >= 80:
            indicator = "🟢"
            conf_color = RGBColor(0x4A, 0x7C, 0x4A)  # green
        elif confidence >= 50:
            indicator = "🟡"
            conf_color = RGBColor(0xC4, 0xA0, 0x50)  # gold
        else:
            indicator = "🔴"
            conf_color = RGBColor(0xB0, 0x59, 0x4F)  # red

        # Bullet text with confidence indicator
        p = doc.add_paragraph(style="List Bullet")
        # Confidence indicator
        ind_run = p.add_run(f"{indicator} ")
        ind_run.font.size = Pt(11)
        # V10.1.0: 🛡️ verified badge (Layer 8 verbatim grounding)
        if meta.get("verified"):
            shield_run = p.add_run("🛡️ ")
            shield_run.font.size = Pt(11)
        # Bullet text
        run = p.add_run(bp)
        run.font.size = Pt(11)
        run.font.name = "Helvetica"
        # Confidence score in parentheses
        conf_run = p.add_run(f"  [{confidence}/100]")
        conf_run.font.size = Pt(8)
        conf_run.font.color.rgb = conf_color
        conf_run.font.italic = True

        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(10)

        # K2: Source excerpt as sub-bullet
        if excerpt:
            sub_p = doc.add_paragraph()
            sub_p.paragraph_format.left_indent = Inches(0.75)
            sub_p.paragraph_format.space_after = Pt(2)
            # V10.1.0: verified bullets use 🛡️ label, others use 📖
            if meta.get("verified"):
                cite_label = "🛡️ Verified source: "
                cite_color = RGBColor(0x2A, 0x6E, 0x2A)  # darker green
            elif page:
                # V10.24.0: Removed page citation — find_source_page was returning
                # wrong page numbers (all p.173).  The source excerpt is still
                # included for grounding, but the page number is unreliable.
                cite_label = "📖 Source: "
                cite_color = RGBColor(120, 120, 120)
            else:
                cite_label = "📖 Source: "
                cite_color = RGBColor(120, 120, 120)
            cite_run = sub_p.add_run(cite_label)
            cite_run.font.size = Pt(8)
            cite_run.font.italic = True
            cite_run.font.color.rgb = cite_color
            excerpt_run = sub_p.add_run(f'"{excerpt}"')
            excerpt_run.font.size = Pt(9)
            excerpt_run.font.italic = True
            excerpt_run.font.color.rgb = RGBColor(100, 100, 100)

        # Extra spacing after each bullet
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
