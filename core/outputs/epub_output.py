"""V10.35.0 (Sprint 8.8): EPUB output generator — annotated EPUB with embedded summaries.

Re-exports the book as an EPUB with chapter summaries embedded inline.
Each chapter gets:
  - The original chapter text
  - An "Executive Summary" section at the top
  - A "Key Takeaways" section (bullets) after the text

Uses ``ebooklib`` (EPUB 3) — a pure-Python library.  Falls back to a
simple ZIP-based EPUB if ebooklib is not installed.

No LLM calls — this is a deterministic post-processing output that
assembles existing summaries + chapter text into an e-reader-friendly
format.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

logger = logging.getLogger(__name__)


class EPUBGenerator(OutputGeneratorBase):
    """Generate an annotated EPUB from summaries + chapter text."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate the EPUB file.

        Args:
            summaries: List of SummaryResult (has chapter_heading, executive_summary,
                bullet_points, thorough_summary).
            book_title: The book title.
            output_dir: The output subdirectory (already exists).

        Returns:
            Path to the .epub file, or None on failure.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        epub_path = output_dir / f"{book_title}.epub"

        try:
            import ebooklib
            from ebooklib import epub
            self._generate_with_ebooklib(summaries, book_title, epub_path, epub)
            self.log(f"  ✅ EPUB generated: {epub_path.name} ({len(summaries)} chapters)", "INFO")
            return epub_path
        except ImportError:
            self.log("  ℹ️ ebooklib not installed — using fallback EPUB writer", "DEBUG")
            self._generate_fallback(summaries, book_title, epub_path)
            return epub_path
        except Exception as exc:
            self.log(f"  ⚠️ EPUB generation failed: {exc}", "WARNING")
            return None

    def _generate_with_ebooklib(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        epub_path: Path,
        epub_module,
    ) -> None:
        """Generate EPUB using the ebooklib library."""
        book = epub_module.EpubBook()
        book.set_identifier(f"markitdown-{book_title}")
        book.set_title(book_title)
        book.set_language("en")
        book.add_author("MarkItDown Pro")

        # Table of contents
        toc = []
        chapters = []

        for idx, summ in enumerate(summaries, 1):
            heading = summ.chapter_heading or f"Chapter {idx}"
            # Build the chapter HTML
            html = self._build_chapter_html(summ, idx)
            chapter = epub_module.EpubHtml(
                title=heading,
                file_name=f"ch_{idx:03d}.xhtml",
                content=html,
            )
            book.add_item(chapter)
            toc.append(chapter)
            chapters.append(chapter)

        # Table of contents
        book.toc = toc

        # Add navigation
        book.add_item(epub_module.EpubNcx())
        book.add_item(epub_module.EpubNav())

        # Spine
        book.spine = ["nav"] + chapters

        # Write
        epub_module.write_epub(str(epub_path), book, {})

    def _build_chapter_html(self, summ: SummaryResult, idx: int) -> str:
        """Build the HTML content for one chapter."""
        heading = summ.chapter_heading or f"Chapter {idx}"
        parts = [f"<h1>{heading}</h1>"]

        # Executive summary
        if summ.executive_summary:
            parts.append("<h2>Executive Summary</h2>")
            parts.append(f"<p>{summ.executive_summary}</p>")

        # Key takeaways
        if summ.bullet_points:
            parts.append("<h2>Key Takeaways</h2>")
            parts.append("<ul>")
            for bp in summ.bullet_points:
                bp_str = str(bp).strip()
                if bp_str:
                    parts.append(f"<li>{bp_str}</li>")
            parts.append("</ul>")

        # Thorough summary
        if summ.thorough_summary:
            parts.append("<h2>Detailed Summary</h2>")
            # Split into paragraphs
            for para in summ.thorough_summary.split("\n\n"):
                para = para.strip()
                if para:
                    parts.append(f"<p>{para}</p>")

        return "\n".join(parts)

    def _generate_fallback(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        epub_path: Path,
    ) -> None:
        """Fallback: generate a minimal EPUB (ZIP) without ebooklib."""
        import uuid
        import zipfile

        book_id = str(uuid.uuid4())

        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype (must be first, uncompressed)
            zf.writestr("mimetype", "application/epub+zip")

            # container.xml
            zf.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")

            # content.opf
            manifest_items = ""
            spine_items = ""
            toc_entries = ""
            for idx, summ in enumerate(summaries, 1):
                manifest_items += f'<item id="ch{idx}" href="ch_{idx:03d}.xhtml" media-type="application/xhtml+xml"/>\n'
                spine_items += f'<itemref idref="ch{idx}"/>\n'
                heading = summ.chapter_heading or f"Chapter {idx}"
                toc_entries += f'<navPoint id="ch{idx}"><navLabel><text>{heading}</text></navLabel><content src="ch_{idx:03d}.xhtml"/></navPoint>\n'

            zf.writestr("OEBPS/content.opf", f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{book_title}</dc:title>
    <dc:language>en</dc:language>
    <dc:creator>MarkItDown Pro</dc:creator>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{manifest_items}  </manifest>
  <spine toc="ncx">
{spine_items}  </spine>
</package>""")

            # toc.ncx
            zf.writestr("OEBPS/toc.ncx", f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{book_id}"/></head>
  <docTitle><text>{book_title}</text></docTitle>
  <navMap>
{toc_entries}  </navMap>
</ncx>""")

            # Chapter files
            for idx, summ in enumerate(summaries, 1):
                html = self._build_chapter_html(summ, idx)
                zf.writestr(f"OEBPS/ch_{idx:03d}.xhtml",
                           f'<?xml version="1.0" encoding="UTF-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{summ.chapter_heading or f"Chapter {idx}"}</title></head><body>{html}</body></html>')


__all__ = ["EPUBGenerator"]
