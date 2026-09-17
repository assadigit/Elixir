"""
DOCX report builder – Apple-inspired clean styling.
Includes text sanitisation to prevent XML corruption and improved content cleaning.
NEW: Renders structured academic rigor output (XML/JSON) into readable prose.
"""

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from core.models import ConversionRequest, SummaryResult
from utils.logging import get_main_logger

logger = get_main_logger()


class DocxBuilder:
    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)

    # ── Improved text cleaning ──────────────────────────────────────────────

    def _sanitise_text(self, text: str) -> str:
        """Remove characters that break DOCX XML and normalise PDF spacing artefacts."""
        # Strip XML-illegal control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # Collapse 3+ blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Collapse multiple inline spaces (from PDF justified text extraction)
        text = re.sub(r'(?<=\S) {2,}(?=\S)', ' ', text)
        return text

    def _clean_content_for_preview(self, text: str, max_chars: int = 500) -> str:
        """
        Clean a content snippet for display in the DOCX "Original Chapter Content" section.
        Removes page markers, fixes hyphenated line breaks, and normalises whitespace.
        """
        if not text:
            return ""

        # 1. Remove page marker comments
        text = re.sub(r'<!-- original page \d+ -->\s*\n?', '', text)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # V13.33.3: The text is ALREADY cleaned by the postprocess pipeline.
        # DO NOT re-do hyphenation repair here — it was already done correctly.
        # The old code's r'\1\2' (no space) mangled "word1-\nword2" → "word1word2".
        # Just do minimal cleanup: remove page markers (already done above) + tabs.
        text = text.replace('\t', ' ')
        text = re.sub(r' {2,}', ' ', text)

        # 4. Normalise line breaks: keep paragraphs separated by double newline,
        #    but collapse excessive newlines.
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 5. Truncate to max_chars while preserving whole words
        if len(text) > max_chars:
            # Find the last space before max_chars
            cut = text.rfind(' ', 0, max_chars)
            if cut == -1:
                cut = max_chars
            text = text[:cut] + "..."

        return text.strip()

    # ── NEW: Render structured academic rigor output ──────────────────────

    def _render_structured_summary(self, text: str) -> str:
        """
        Detect if the text contains structured academic rigor output (XML or JSON)
        and convert it to readable prose. If no structure detected, return the text as‑is.
        """
        if not text:
            return ""

        # 1. Try to parse as JSON (academic rigor mode)
        try:
            # Look for a JSON object
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                # Check if it has the expected keys
                if isinstance(data, dict):
                    parts = []
                    # Executive summary
                    if "executive_summary" in data:
                        exec_data = data["executive_summary"]
                        if isinstance(exec_data, list):
                            exec_text = ". ".join([item.get("claim", "") for item in exec_data if isinstance(item, dict)])
                        else:
                            exec_text = str(exec_data)
                        if exec_text:
                            parts.append(exec_text)
                    # Bullet points
                    if "bullet_points" in data:
                        bullets = data["bullet_points"]
                        if isinstance(bullets, list):
                            bullet_texts = []
                            for item in bullets:
                                if isinstance(item, dict):
                                    claim = item.get("claim", "")
                                    if claim:
                                        bullet_texts.append(claim)
                                elif isinstance(item, str):
                                    bullet_texts.append(item)
                            if bullet_texts:
                                parts.append("\n".join(f"• {bp}" for bp in bullet_texts))
                    # Thorough summary
                    if "thorough_summary" in data:
                        thorough_data = data["thorough_summary"]
                        if isinstance(thorough_data, list):
                            thorough_text = ". ".join([item.get("claim", "") for item in thorough_data if isinstance(item, dict)])
                        else:
                            thorough_text = str(thorough_data)
                        if thorough_text:
                            parts.append(thorough_text)
                    if parts:
                        return "\n\n".join(parts)
        except (json.JSONDecodeError, AttributeError, KeyError):
            pass

        # 2. Try to parse as XML (non‑academic rigor mode, but could have leftovers)
        # Look for tags like <executive_summary>, <bullet_points>, <thorough_summary>
        em = re.search(r'<executive_summary>(.*?)</executive_summary>', text, re.DOTALL)
        bm = re.search(r'<bullet_points>(.*?)</bullet_points>', text, re.DOTALL)
        tm = re.search(r'<thorough_summary>(.*?)</thorough_summary>', text, re.DOTALL)
        if em or bm or tm:
            parts = []
            if em:
                exec_text = em.group(1).strip()
                parts.append(exec_text)
            if bm:
                bullets_text = bm.group(1).strip()
                # Split into lines, each might be a bullet
                bullets = [line.strip() for line in bullets_text.splitlines() if line.strip()]
                if bullets:
                    parts.append("\n".join(f"• {bp}" for bp in bullets))
            if tm:
                thorough_text = tm.group(1).strip()
                parts.append(thorough_text)
            return "\n\n".join(parts)

        # 3. If no structured tags found, but we still see `<claim>` tags, try to extract them
        if '<claim>' in text or '"claim"' in text:
            # Extract everything between <claim> and </claim>
            claims = re.findall(r'<claim>(.*?)</claim>', text, re.DOTALL)
            if claims:
                return "\n\n".join(claims)
            # Or try JSON‑style "claim" keys
            try:
                claims = re.findall(r'"claim"\s*:\s*"([^"]*)"', text)
                if claims:
                    return "\n\n".join(claims)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Fallback: return the text as‑is (it will be cleaned later)
        return text

    # ── Helper methods (unchanged) ──────────────────────────────────────────

    def _set_cell_background(self, cell, color_hex: str = "F5F5F7"):
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), color_hex)
        cell._tc.get_or_add_tcPr().append(shading)

    def _add_cover_page(self, doc, title: str, source_file: Path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title)
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.name = "Helvetica"
        p.paragraph_format.space_after = Pt(48)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"Source: {source_file.name}")
        run.font.size = Pt(14)
        run.font.italic = True
        run.font.name = "Helvetica"
        p.paragraph_format.space_after = Pt(24)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"Generated by {self.request.docx_author}")
        run.font.size = Pt(12)
        run.font.name = "Helvetica"
        p.paragraph_format.space_after = Pt(24)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(datetime.now().strftime("%B %d, %Y"))
        run.font.size = Pt(12)
        run.font.name = "Helvetica"
        doc.add_page_break()

    def _clean_heading(self, heading: str) -> str:
        """
        Clean a chapter heading for display in the DOCX.
        Strips cross-reference noise that leaked in when the heading segmenter
        picks up body text: e.g. 'Chapter 3 through 9) into the open…' → 'Chapter 3'.
        """
        import re
        # Normalise whitespace (tabs, multiple spaces)
        h = re.sub(r"[\t\r\n]+", " ", heading)
        h = re.sub(r" {2,}", " ", h).strip()
        # If heading starts with "Chapter N" followed by body-text garbage
        # (lowercase continuation), truncate to just "Chapter N: Title" or "Chapter N"
        m = re.match(
            r"^((?:Chapter|Part|Appendix|Section|Unit)\s+\d+\s*(?:[:\-–—]\s*[^\(]+)?)",
            h, re.IGNORECASE,
        )
        if m:
            cleaned = m.group(1).strip().rstrip(":- –—")
            return cleaned if len(cleaned) >= 6 else h
        return h

    def _add_toc(self, doc, chapter_titles: list[str]):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Table of Contents")
        run.font.size = Pt(22)
        run.font.bold = True
        run.font.name = "Helvetica"
        p.paragraph_format.space_after = Pt(24)

        for idx, title in enumerate(chapter_titles, 1):
            clean = self._clean_heading(title)
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            # Chapter number tab-stop left, title, page placeholder right
            run_num = p.add_run(f"{idx:>2}.  ")
            run_num.font.size = Pt(11)
            run_num.font.name = "Helvetica"
            run_num.font.bold = True
            run_title = p.add_run(clean)
            run_title.font.size = Pt(11)
            run_title.font.name = "Helvetica"

        doc.add_page_break()

    def _add_heading(self, doc, text: str, level: int = 1):
        heading = doc.add_heading(text, level=level)
        for run in heading.runs:
            run.font.name = "Helvetica"
            if level == 1:
                run.font.size = Pt(20)
                run.font.bold = True
                run.font.color.rgb = RGBColor(0, 102, 204)
            elif level == 2:
                run.font.size = Pt(14)
                run.font.bold = True
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(6)

    def _add_callout_box(self, doc, title: str, bullet_points: list[str]):
        if not bullet_points:
            return
        table = doc.add_table(rows=1, cols=1)
        table.autofit = False
        table.allow_autofit = False
        table.width = Inches(6.0)
        cell = table.cell(0, 0)
        self._set_cell_background(cell, "F5F5F7")
        cell.margin_top = Inches(0.1)
        cell.margin_bottom = Inches(0.1)
        cell.margin_left = Inches(0.15)
        cell.margin_right = Inches(0.15)

        title_para = cell.paragraphs[0]
        title_run = title_para.add_run(title)
        title_run.font.size = Pt(12)
        title_run.font.bold = True
        title_run.font.name = "Helvetica"
        title_para.paragraph_format.space_after = Pt(6)

        for bp in bullet_points:
            if not bp or len(bp) < 2:
                continue
            p = cell.add_paragraph(style="List Bullet")
            run = p.add_run(bp)
            run.font.size = Pt(11)
            run.font.name = "Helvetica"
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Inches(0.25)
        doc.add_paragraph()

    def _add_full_content(self, doc, markdown_content: str):
        """
        Render markdown content into DOCX paragraphs.
        Processes paragraph-by-paragraph (split on blank lines) so that
        single-newline line-wrapping inside a paragraph is joined into one
        flowing run — eliminating the excessive line-height gap that occurred
        when every wrapped line became its own paragraph with space_after.

        NEW: If the content contains structured academic rigor tags (XML/JSON),
        render it to readable prose first.
        """
        if not markdown_content:
            doc.add_paragraph("(No content available)")
            return

        # ── Render structured content if present ──────────────────────────
        rendered = self._render_structured_summary(markdown_content)
        # If the rendered output is different (i.e., structured tags were found and converted),
        # use it; otherwise, keep the original markdown.
        if rendered != markdown_content:
            content = rendered
        else:
            content = markdown_content

        # ── Clean content ──────────────────────────────────────────────────
        # Remove page markers and HTML comments
        content = re.sub(r'<!-- original page \d+ -->', '', content)
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        content = content.replace('--- page ---', '')
        content = self._sanitise_text(content)

        # V13.33.3: DO NOT re-process hyphenation or whitespace here.
        # The postprocess pipeline ALREADY cleaned the text (hyphenation repair,
        # tab→space, paragraph joining). The old code re-did hyphenation repair
        # with r'\1\2' (joining WITHOUT a space), which MANGLED the text:
        # "humor.-\nMy" → "humor.My" (no space between sentences).
        # The text is already clean — just render it as-is.

        # ── Split into blocks ──────────────────────────────────────────────
        blocks = re.split(r'\n{2,}', content)

        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            first = lines[0]

            # Handle headings
            if first.startswith('### '):
                self._add_heading(doc, first[4:].strip(), level=3)
                lines = lines[1:]
            elif first.startswith('## '):
                self._add_heading(doc, first[3:].strip(), level=2)
                lines = lines[1:]
            elif first.startswith('# '):
                self._add_heading(doc, first[2:].strip(), level=1)
                lines = lines[1:]

            if not lines:
                continue

            # Bullet lists
            if all(l.startswith(('- ', '* ', '\u2022 ')) for l in lines):
                for l in lines:
                    p = doc.add_paragraph(style="List Bullet")
                    p.paragraph_format.left_indent = Inches(0.25)
                    p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(l[2:].strip())
                    run.font.size = Pt(11)
                    run.font.name = "Helvetica"
                continue

            # Numbered lists
            if all(re.match(r'^\d+[.)]\s', l) for l in lines):
                for l in lines:
                    p = doc.add_paragraph(style="List Number")
                    p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(re.sub(r'^\d+[.)]\s+', '', l))
                    run.font.size = Pt(11)
                    run.font.name = "Helvetica"
                continue

            # Regular paragraph: join wrapped lines into one flowing paragraph
            body = ' '.join(lines)
            p = doc.add_paragraph()
            p.paragraph_format.space_after  = Pt(6)
            p.paragraph_format.space_before = Pt(0)
            run = p.add_run(body)
            run.font.size = Pt(11)
            run.font.name = "Helvetica"

    def _add_global_takeaways(self, doc, summaries: list[SummaryResult]):
        all_bullets = []
        for summ in summaries:
            all_bullets.extend(summ.bullet_points)
        seen = set()
        unique_bullets = []
        for bp in all_bullets:
            if not bp or len(bp) < 10:
                continue
            norm = re.sub(r'[^\w\s]', '', bp.lower()).strip()
            if norm not in seen:
                seen.add(norm)
                unique_bullets.append(bp)
        if not unique_bullets:
            return
        doc.add_page_break()
        self._add_heading(doc, "Global Key Takeaways", level=1)
        self._add_callout_box(doc, "All Key Takeaways", unique_bullets)

    def _add_footer_with_page_numbers(self, doc):
        section = doc.sections[0]
        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.clear()
        run = footer_para.add_run()
        fld_char = OxmlElement('w:fldChar')
        fld_char.set(qn('w:fldCharType'), 'begin')
        run._r.append(fld_char)
        instr_text = OxmlElement('w:instrText')
        instr_text.text = "PAGE"
        run._r.append(instr_text)
        fld_char_end = OxmlElement('w:fldChar')
        fld_char_end.set(qn('w:fldCharType'), 'end')
        run._r.append(fld_char_end)
        footer_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run.font.size = Pt(9)
        run.font.name = "Helvetica"

    # ── Main build method ───────────────────────────────────────────────────

    def build_report(self, summaries, full_chapters, source_file, output_path) -> bool:
        self.log("📄 Building DOCX report…", "INFO")
        if not full_chapters:
            self.log("  No chapters to build report from.", "WARNING")
            return False

        # If no summaries, build content-only report
        has_summaries = bool(summaries)
        if has_summaries and len(summaries) != len(full_chapters):
            self.log("  Summary/chapter count mismatch — truncating.", "WARNING")
            min_len = min(len(summaries), len(full_chapters))
            summaries = summaries[:min_len]
            full_chapters = full_chapters[:min_len]

        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Helvetica'
        style.font.size = Pt(11)

        title = Path(str(source_file)).stem.replace('_', ' ').title()
        self._add_cover_page(doc, title, Path(str(source_file)))

        if self.request.docx_include_toc and has_summaries:
            self._add_toc(doc, [s.chapter_heading for s in summaries])
        elif self.request.docx_include_toc:
            self._add_toc(doc, [c.get("heading", f"Chapter {i}") for i, c in enumerate(full_chapters, 1)])

        for idx, chap in enumerate(full_chapters, 1):
            chapter_heading = (
                summaries[idx - 1].chapter_heading if has_summaries else chap.get("heading", f"Chapter {idx}")
            )
            self.log(f"  Adding chapter {idx}: {chapter_heading[:50]}…", "INFO")
            self._add_heading(doc, chapter_heading, level=1)

            if has_summaries:
                summ = summaries[idx - 1]
                p = doc.add_paragraph()
                run = p.add_run("Executive Summary")
                run.font.size = Pt(14)
                run.font.bold = True
                run.font.name = "Helvetica"
                run.font.color.rgb = RGBColor(0, 102, 204)
                p.paragraph_format.space_after = Pt(6)

                # Render structured content if present
                exec_text = self._render_structured_summary(summ.executive_summary or "")
                p = doc.add_paragraph(exec_text)
                for run in p.runs:
                    run.font.size = Pt(11)
                    run.font.name = "Helvetica"
                p.paragraph_format.space_after = Pt(12)

                if summ.bullet_points:
                    self._add_callout_box(doc, "Key Takeaways", summ.bullet_points)

                p = doc.add_paragraph()
                run = p.add_run("Thorough Summary")
                run.font.size = Pt(14)
                run.font.bold = True
                run.font.name = "Helvetica"
                run.font.color.rgb = RGBColor(0, 102, 204)
                p.paragraph_format.space_after = Pt(6)
                # Render structured content for thorough summary
                thorough_text = self._render_structured_summary(summ.thorough_summary or "")
                p = doc.add_paragraph(thorough_text)
                for run in p.runs:
                    run.font.size = Pt(11)
                    run.font.name = "Helvetica"
                p.paragraph_format.space_after = Pt(12)

                # V13.40.1: Render additive sections (Key Distinctions + Theoretical Tensions)
                # These are anti-hallucination-verified sections added in V13.38.0.
                # Only render if non-empty (the model may output "None" for chapters
                # that don't discuss distinctions/tensions).
                _kd = getattr(summ, "key_distinctions", "") or ""
                if _kd.strip():
                    p = doc.add_paragraph()
                    run = p.add_run("Key Distinctions")
                    run.font.size = Pt(14)
                    run.font.bold = True
                    run.font.name = "Helvetica"
                    run.font.color.rgb = RGBColor(0, 102, 204)
                    p.paragraph_format.space_after = Pt(6)
                    kd_text = self._render_structured_summary(_kd)
                    p = doc.add_paragraph(kd_text)
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Helvetica"
                    p.paragraph_format.space_after = Pt(12)

                _tt = getattr(summ, "theoretical_tensions", "") or ""
                if _tt.strip():
                    p = doc.add_paragraph()
                    run = p.add_run("Theoretical Tensions")
                    run.font.size = Pt(14)
                    run.font.bold = True
                    run.font.name = "Helvetica"
                    run.font.color.rgb = RGBColor(0, 102, 204)
                    p.paragraph_format.space_after = Pt(6)
                    tt_text = self._render_structured_summary(_tt)
                    p = doc.add_paragraph(tt_text)
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Helvetica"
                    p.paragraph_format.space_after = Pt(12)

                # V13.41.0: Render Scholar's Reflections (meta-cognitive gap analysis)
                _sr = getattr(summ, "scholar_reflections", "") or ""
                if _sr.strip():
                    p = doc.add_paragraph()
                    run = p.add_run("Scholar's Reflections")
                    run.font.size = Pt(14)
                    run.font.bold = True
                    run.font.name = "Helvetica"
                    run.font.color.rgb = RGBColor(0, 102, 204)
                    p.paragraph_format.space_after = Pt(6)
                    sr_text = self._render_structured_summary(_sr)
                    p = doc.add_paragraph(sr_text)
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Helvetica"
                    p.paragraph_format.space_after = Pt(12)

            # ── Full Chapter Content ──────────────────────────────────────
            p = doc.add_paragraph()
            run = p.add_run("Full Chapter Content")
            run.font.size = Pt(14)
            run.font.bold = True
            run.font.name = "Helvetica"
            run.font.color.rgb = RGBColor(0, 102, 204)
            p.paragraph_format.space_after = Pt(6)

            # Extract raw content
            raw_content = chap.get("content", "")

            # V13.33.2: Increased from 500 → 2000 chars (500 was too short)
            if raw_content:
                preview = self._clean_content_for_preview(raw_content, max_chars=2000)
                if preview:
                    p = doc.add_paragraph()
                    run = p.add_run("Original Chapter Content (first 2000 chars)")
                    run.font.size = Pt(11)
                    run.font.italic = True
                    run.font.name = "Helvetica"
                    p.paragraph_format.space_after = Pt(4)

                    p = doc.add_paragraph()
                    run = p.add_run(preview)
                    run.font.size = Pt(10)
                    run.font.name = "Helvetica"
                    run.font.color.rgb = RGBColor(80, 80, 80)
                    p.paragraph_format.space_after = Pt(12)

            # Then add the full cleaned content (with structured rendering)
            self._add_full_content(doc, raw_content)

            if idx < len(full_chapters):
                doc.add_page_break()

        if has_summaries:
            self._add_global_takeaways(doc, summaries)

        self._add_footer_with_page_numbers(doc)

        output_path = Path(str(output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        self.log(f"✅ DOCX saved to {output_path}", "SUCCESS")
        return True
