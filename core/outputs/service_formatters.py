"""V11.18.0: Shared output formatters for the standalone service dialogs.

Converts a markdown / plain-text summary string into the user's chosen
output format: ``.md``, ``.docx``, or ``.pdf``. Also produces an
**Obsidian-flavoured** variant of the markdown when the user opts in
(callouts, front-matter, proper heading levels, tag block) so the result
drops cleanly into an Obsidian vault.

Used by:
  - ``SummarizationServiceDialog`` (multi-file summarization)
  - ``QuickConvertDialog`` (PDF → Markdown, now also .docx/.pdf)
  - ``OcrServiceDialog`` (OCR output, now also .docx/.pdf)
  - ``TranslationServiceDialog`` / ``TtsServiceDialog`` (text outputs)

Design notes:
  - All dependencies (python-docx, reportlab, weasyprint, markdown) are
    already listed in ``requirements.txt`` and verified at import time.
    If a library is missing, the formatter degrades gracefully: it writes
    the ``.md`` file and logs a WARNING with the install command.
  - The Obsidian formatter is pure-Python (no external deps) so it always
    works — Obsidian callouts are just ``> [!note]`` blockquotes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text
from utils.rtl import is_rtl_dominant

logger = logging.getLogger(__name__)

OutputFormat = Literal[".md", ".docx", ".pdf"]


# ── RTL support (V0.6.5) ───────────────────────────────────────────────
#
# The user report: "the pdf conversion (summarization) of a Farsi text
# works, but it still LTRs the content — not easily readable; it's fine
# in md and docx." Root cause: none of the three writers had ANY
# direction handling. The fix is one detector (utils.rtl — letters-only
# script ratio, content-agnostic) threaded through every format:
#
#   .md   → an Obsidian ``dir: rtl`` front-matter property (merged into
#           existing front-matter, never duplicated)
#   .docx → ``w:bidi`` paragraph property + right alignment on EVERY
#           paragraph (Word then renders bullets on the right and
#           reorders runs correctly)
#   .pdf  → WeasyPrint: ``direction: rtl`` CSS + the bundled Vazirmatn
#           font via @font-face (Pango does proper bidi + shaping);
#           ReportLab fallback: arabic_reshaper + python-bidi per
#           fragment + right-aligned styles + the registered Vazirmatn
#           TTF (graceful LTR degrade + WARNING when the libs are absent)
#
# The Vazirmatn TTFs ship in ``assets/fonts/`` (SIL OFL 1.1 — the
# standard Persian typeface) because the default PDF fonts (Helvetica /
# Segoe UI) have no Arabic glyphs on most hosts — that was the earlier
# black-squares report.

# Repo root (core/outputs/service_formatters.py → two parents up).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FONT_DIR = _REPO_ROOT / "assets" / "fonts"


def _vazirmatn_font_url(weight: str = "Regular") -> str | None:
    """File:// URL of the bundled Vazirmatn TTF, or None when absent."""
    p = _FONT_DIR / f"Vazirmatn-{weight}.ttf"
    return p.as_uri() if p.exists() else None


def _register_vazirmatn_reportlab() -> str | None:
    """Register the bundled Vazirmatn TTFs with ReportLab.

    Returns the regular family name ("Vazirmatn") on success, else None
    (caller keeps the default font — right-aligned but unshaped text is
    still more readable than an exception).
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return None
    regular = _FONT_DIR / "Vazirmatn-Regular.ttf"
    if not regular.exists():
        return None
    try:
        pdfmetrics.registerFont(TTFont("Vazirmatn", str(regular)))
        bold = _FONT_DIR / "Vazirmatn-Bold.ttf"
        if bold.exists():
            pdfmetrics.registerFont(TTFont("Vazirmatn-Bold", str(bold)))
        return "Vazirmatn"
    except Exception as e:
        logger.warning("Vazirmatn TTF registration failed (%s); using default font", e)
        return None


def _shape_rtl_fragment(text: str) -> str:
    """Reshape + bidi-reorder one plain-text fragment for ReportLab.

    ReportLab does NO bidi/shaping itself: Arabic text drawn as-is comes
    out letter-isolated and left-to-right (the user's unreadable-PDF
    report). ``arabic_reshaper`` maps to presentation forms, then
    ``get_display`` produces the visual order ReportLab must draw.

    Degrades to the input text (with a WARNING) when the libs are absent
    — requirements.txt carries both, so a normal install has them.
    """
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError:
        logger.warning(
            "arabic-reshaper / python-bidi not installed — RTL PDF text "
            "will render unshaped. Run: pip install arabic-reshaper python-bidi"
        )
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception as e:
        logger.warning("RTL shaping failed (%s); drawing raw fragment", e)
        return text


def _plain_md(text: str) -> str:
    """Strip markdown markers to plain text (the RTL ReportLab path).

    Markup tags (<b>, <i>) interleave badly with bidi-reordered text, so
    the RTL path draws plain fragments only (same trade-off the docx
    writer already makes for bullets).
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text


def _ensure_md_dir_rtl(text: str) -> str:
    """Give a markdown document the Obsidian ``dir: rtl`` property.

    Merged into existing front-matter (after the opening ``---`` line)
    or prepended as a new block. Never duplicates the property.
    """
    if re.search(r"(?m)^dir:\s*rtl\s*$", text[:2000]):
        return text
    if text.startswith("---"):
        # Insert after the opening --- line of the existing front-matter.
        nl = text.find("\n")
        if nl != -1:
            return text[: nl + 1] + "dir: rtl\n" + text[nl + 1 :]
    return f"---\ndir: rtl\n---\n\n{text}"


# ── Obsidian formatter ────────────────────────────────────────────────


def to_obsidian_markdown(
    text: str,
    *,
    title: str | None = None,
    source_filename: str | None = None,
    tags: list[str] | None = None,
    quality: str | None = None,
    model: str | None = None,
    rtl: bool | None = None,
) -> str:
    """Convert plain markdown into Obsidian-flavoured markdown.

    Adds:
      - YAML front-matter (``---`` block) with title, source, tags, quality,
        model, and a generated ISO timestamp.
      - Converts ``## Section`` headings into Obsidian callouts where
        appropriate (``## Executive Summary`` → ``> [!summary] Executive Summary``).
      - Bullet lists are kept as-is (Obsidian renders them natively).
      - A trailing ``#summary`` tag + backlinks section so the note shows up
        in Obsidian's graph view.
    """
    # Strip any existing front-matter so we don't double-wrap.
    body = re.sub(r"^---\n.*?\n---\n?", "", text, flags=re.DOTALL).strip()

    # V0.6.5: resolve the direction once (None = auto-detect on the body).
    if rtl is None:
        rtl = is_rtl_dominant(body)

    # Build front-matter
    import datetime

    fm_lines = ["---"]
    # V0.6.5: the Obsidian text-direction property — an RTL note opens
    # right-aligned in the editor AND the reading view.
    if rtl:
        fm_lines.append("dir: rtl")
    if title:
        fm_lines.append(f'title: "{title.replace('"', '\\"')}"')
    if source_filename:
        fm_lines.append(f'source: "[[{source_filename}]]"')
    if quality:
        fm_lines.append(f"quality: {quality}")
    if model:
        fm_lines.append(f'model: "{model}"')
    fm_lines.append(f"created: {datetime.datetime.now().isoformat(timespec='seconds')}")
    if tags:
        fm_lines.append("tags:")
        for t in tags:
            fm_lines.append(f"  - {t.lstrip('#')}")
    else:
        fm_lines.append("tags:")
        fm_lines.append("  - summary")
    fm_lines.append("---")
    front_matter = "\n".join(fm_lines)

    # Convert section headings into Obsidian callouts.
    # Mapping: heading text → callout type. Unknown headings stay as ## headings.
    callout_map = {
        "executive summary": "summary",
        "key takeaways": "info",
        "key points": "info",
        "detailed summary": "abstract",
        "analysis": "example",
        "conclusion": "success",
        "warnings": "warning",
        "questions": "question",
        "quotes": "quote",
        # V0.6.4: the depth-prompt sections (normalize_depth_headings turns
        # the bare "Overview:" labels into ## headings, which land here).
        "overview": "summary",
        "important details": "info",
        "key facts and figures": "info",
        "conclusions and takeaways": "success",
    }
    out_lines: list[str] = []
    in_callout = False
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            level, heading_text = len(m.group(1)), m.group(2).strip()
            key = heading_text.lower().rstrip(":.")
            callout_type = callout_map.get(key)
            if callout_type and level <= 3:
                # Start a callout block
                if in_callout:
                    out_lines.append("")  # close previous callout with blank line
                out_lines.append(f"> [!{callout_type}] {heading_text}")
                in_callout = True
                continue
            else:
                if in_callout:
                    out_lines.append("")
                    in_callout = False
                out_lines.append(line)
                continue
        if in_callout:
            # Inside a callout — prefix continuation lines with "> "
            if line.strip() == "":
                out_lines.append(">")  # keep blank lines inside callout
            else:
                out_lines.append(f"> {line}")
        else:
            out_lines.append(line)
    if in_callout:
        out_lines.append("")

    body_formatted = "\n".join(out_lines)

    # Footer with backlinks hint
    footer_parts = ["", "---", ""]
    if source_filename:
        footer_parts.append(f"**Source:** [[{source_filename}]]")
    if quality:
        footer_parts.append(f"**Summary type:** `{quality}`")
    if model:
        footer_parts.append(f"**Model:** `{model}`")
    footer_parts.append("")
    footer = "\n".join(footer_parts)

    return f"{front_matter}\n\n{body_formatted}\n{footer}"


# ── DOCX formatter ────────────────────────────────────────────────────


def write_docx(text: str, out_path: Path, *, title: str | None = None, rtl: bool = False) -> bool:
    """Write a markdown-ish string to a .docx file.

    Returns True on success, False if python-docx is unavailable.
    Basic markdown rendering: headings (# → Title, ## → Heading 1, …),
    bullet lines (``- `` / ``* ``) → List Bullet, numbered (``1. ``) →
    List Number, everything else → Normal.

    V0.6.5: ``rtl=True`` (the auto-detected default from
    :func:`write_output` for RTL-dominant text) sets the ``w:bidi``
    paragraph property + right alignment on EVERY paragraph — Word
    then reorders runs, renders bullets on the right and keeps mixed
    LTR fragments (product names, numbers) readable.
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
    except ImportError:
        logger.warning(
            "python-docx not installed — cannot write .docx. Run: pip install python-docx"
        )
        return False

    doc = Document()

    # V0.6.4 (user report): BLACK headings by default. python-docx's default
    # template styles Heading 1-4 with the Word blue theme; the old code
    # only explicitly darkened the level-0 title, so every section heading
    # rendered blue. Every heading run now carries the explicit near-black
    # RGB (0x1A1A1A — the same value the title already used).
    _BLACK = RGBColor(0x1A, 0x1A, 0x1A)

    # V0.6.5: the RTL paragraph decorator — right alignment + ``w:bidi``.
    # Applied to EVERY paragraph the writer creates (headings, bullets,
    # numbered, quotes, normal) so the document reads naturally in Word.
    _rtl = bool(rtl)

    def _rtlify(p):
        if not _rtl or p is None:
            return p
        try:
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn

            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pPr = p._p.get_or_add_pPr()
            if pPr.find(qn("w:bidi")) is None:
                pPr.append(OxmlElement("w:bidi"))
        except Exception as e:  # noqa: BLE001 — best-effort, never fatal
            logger.warning("docx RTL paragraph flag failed (%s); paragraph stays LTR", e)
        return p

    def _add_black_heading(text: str, level: int):
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.color.rgb = _BLACK
            # V0.6.5: mark the run itself RTL so Word renders the run's
            # characters with RTL semantics (mixed-direction titles).
            if _rtl:
                try:
                    run.font.rtl = True
                except Exception as _e:  # noqa: BLE001 — best-effort
                    logger.debug("run.rtl set failed: %s", _e)
        return _rtlify(h)

    # Optional title
    if title:
        _add_black_heading(title, level=0)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Skip YAML front-matter
        if line.strip() == "---":
            continue
        # Headings
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            level = min(len(m.group(1)), 4)  # Word only has Heading 1–4; #/## map to Title/Heading1
            _add_black_heading(m.group(2).strip(), level=level if level >= 1 else 1)
            continue
        # Bullet list
        if re.match(r"^\s*[-*+]\s+", line):
            item = re.sub(r"^\s*[-*+]\s+", "", line)
            # Strip markdown bold/italic markers for docx (best-effort)
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
            item = re.sub(r"\*(.+?)\*", r"\1", item)
            _rtlify(doc.add_paragraph(item, style="List Bullet"))
            continue
        # Numbered list
        if re.match(r"^\s*\d+\.\s+", line):
            item = re.sub(r"^\s*\d+\.\s+", "", line)
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
            item = re.sub(r"\*(.+?)\*", r"\1", item)
            _rtlify(doc.add_paragraph(item, style="List Number"))
            continue
        # Blockquote → indent + italic
        if line.startswith(">"):
            text_clean = line.lstrip(">").strip()
            if text_clean:
                p = doc.add_paragraph(text_clean)
                # V0.6.5: the quote indent follows the reading direction.
                p.paragraph_format.right_indent = Pt(24) if _rtl else None
                p.paragraph_format.left_indent = None if _rtl else Pt(24)
                for run in p.runs:
                    run.italic = True
                _rtlify(p)
            continue
        # Horizontal rule
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            _rtlify(doc.add_paragraph("─" * 40))
            continue
        # Blank line
        if not line.strip():
            continue
        # Normal paragraph — strip bold/italic markers
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)
        clean = re.sub(r"`(.+?)`", r"\1", clean)
        _rtlify(doc.add_paragraph(clean))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return True


# ── PDF formatter ─────────────────────────────────────────────────────


# V0.6.4 (user report): the pdf CSS is a BLACK-THEME module constant (was
# a green theme inlined in write_pdf: #166534/#15803d/#16a34a headings,
# #86efac blockquote border, #f0fdf4 tinted backgrounds). Module-level so
# tests can pin the declared default. Neutral grays for the structural
# accents; near-black #1a1a1a for all text.
_PDF_CSS = """
        @page { size: A4; margin: 2cm; }
        body { font-family: 'Segoe UI', 'Helvetica', sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }
        h1 { color: #1a1a1a; font-size: 20pt; border-bottom: 2px solid #1a1a1a; padding-bottom: 4px; }
        h2 { color: #1a1a1a; font-size: 15pt; margin-top: 1.2em; }
        h3 { color: #333333; font-size: 12pt; }
        blockquote { border-left: 3px solid #9ca3af; margin-left: 0; padding: 4px 12px; color: #374151; background: #f9fafb; }
        code { background: #f3f4f6; padding: 1px 4px; border-radius: 3px; font-family: 'Consolas', monospace; font-size: 9.5pt; }
        pre { background: #f3f4f6; padding: 8px; border-radius: 4px; overflow-x: auto; }
        pre code { background: none; padding: 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #d1d5db; padding: 4px 8px; text-align: left; }
        th { background: #f3f4f6; }
        ul, ol { padding-left: 20px; }
        li { margin: 2px 0; }
        hr { border: none; border-top: 1px solid #d1d5db; margin: 1em 0; }
        """


# V0.6.5: the RTL overrides appended to _PDF_CSS when the document is
# RTL-dominant. WeasyPrint/Pango does REAL bidi + Arabic shaping, so the
# fix is purely declarative: direction + right alignment + the bundled
# Vazirmatn @font-face (the default Helvetica/Segoe stack has no Arabic
# glyphs — the black-squares report). Lists/quotes flip sides to match.
# The @font-face src URLs are injected at build time (module import time
# would pin a path that moves in frozen builds; write_pdf resolves it).
_PDF_RTL_CSS_TEMPLATE = """
        body {{ direction: rtl; text-align: right; }}
        th, td {{ text-align: right; }}
        ul, ol {{ padding-right: 20px; padding-left: 0; }}
        blockquote {{ border-left: none; border-right: 3px solid #9ca3af; margin-right: 0; margin-left: 0; padding-left: 12px; padding-right: 12px; }}
        """


def _rtl_css_with_fonts() -> str:
    """V0.6.5: _PDF_RTL_CSS + the Vazirmatn @font-face rules (when the
    bundled TTFs exist — they ship with the app, so normally yes)."""
    css = _PDF_RTL_CSS_TEMPLATE
    regular = _vazirmatn_font_url("Regular")
    if regular:
        css += (
            f"\n        @font-face {{ font-family: 'Vazirmatn'; "
            f"src: url('{regular}'); font-weight: normal; }}"
        )
        bold = _vazirmatn_font_url("Bold")
        if bold:
            css += (
                f"\n        @font-face {{ font-family: 'Vazirmatn'; "
                f"src: url('{bold}'); font-weight: bold; }}"
            )
        css += "\n        body { font-family: 'Vazirmatn', 'Segoe UI', 'Helvetica', sans-serif; }"
    return css


def write_pdf(text: str, out_path: Path, *, title: str | None = None, rtl: bool = False) -> bool:
    """Write a markdown-ish string to a PDF file.

    Tries WeasyPrint first (best markdown rendering via HTML), falls back
    to ReportLab (pure-Python, always available) if WeasyPrint's system
    deps (cairo/pango) aren't installed.

    V0.6.5: ``rtl=True`` (auto-detected by :func:`write_output`) —
    WeasyPrint gets ``direction: rtl`` + right alignment + Vazirmatn
    (Pango shapes Arabic correctly); ReportLab gets per-fragment
    reshaping (arabic_reshaper + python-bidi), right-aligned styles and
    the registered Vazirmatn TTF.

    Returns True on success, False if both backends fail.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Attempt 1: WeasyPrint (renders HTML → PDF with proper styling)
    try:
        import markdown as _md  # type: ignore

        html_body = _md.markdown(text, extensions=["extra", "tables", "fenced_code"])
        # V0.6.4: the black-theme CSS (module constant — see _PDF_CSS).
        css = _PDF_CSS
        # V0.6.5: RTL overrides + the Vazirmatn @font-face.
        if rtl:
            css += _rtl_css_with_fonts()
        full_html = (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>"
        )
        if title:
            full_html += f"<h1>{title}</h1>"
        full_html += html_body
        full_html += "</body></html>"

        from weasyprint import HTML

        HTML(string=full_html).write_pdf(str(out_path))
        return True
    except ImportError:
        pass  # weasyprint or markdown not available → fall back to reportlab
    except Exception as e:
        logger.debug(f"WeasyPrint failed ({e}); falling back to ReportLab")

    # Attempt 2: ReportLab (pure Python, always works, simpler rendering)
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable,
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )

        # V0.6.5 (RTL): right-aligned styles + the registered Vazirmatn
        # family + per-fragment reshaping. ReportLab draws whatever byte
        # order it is given — arabic_reshaper + python-bidi produce the
        # visual order (see _shape_rtl_fragment). A mixed-direction
        # custom title stays LTR naturally (shaping a Latin string is a
        # no-op). When Vazirmatn registration fails the default Helvetica
        # is kept (still right-aligned; the Arabic glyphs then depend on
        # the viewer's substitution).
        _rtl = bool(rtl)
        _align = TA_RIGHT if _rtl else TA_LEFT
        _rl_font = _register_vazirmatn_reportlab() if _rtl else None
        _rl_font_bold = None
        if _rl_font and (_FONT_DIR / "Vazirmatn-Bold.ttf").exists():
            _rl_font_bold = "Vazirmatn-Bold"

        def _frag(txt: str) -> str:
            """One reportlab text fragment: plain markdown → shaped."""
            if _rtl:
                return _shape_rtl_fragment(_plain_md(txt))
            return _strip_md(txt)

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        # V0.6.4 (user report): BLACK text colors (was the green theme
        # #166534/#15803d/#16a34a). Near-black for the title + H1, the
        # neutral #333 for H2 — matching the WeasyPrint CSS hierarchy.
        title_style = ParagraphStyle(
            "Title2",
            parent=styles["Title"],
            textColor=HexColor("#1a1a1a"),
            fontSize=20,
            spaceAfter=12,
            fontName=_rl_font_bold or (_rl_font or "Helvetica"),
            alignment=_align,
        )
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            textColor=HexColor("#1a1a1a"),
            fontSize=15,
            spaceBefore=12,
            spaceAfter=6,
            fontName=_rl_font_bold or (_rl_font or "Helvetica"),
            alignment=_align,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            textColor=HexColor("#333333"),
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
            fontName=_rl_font_bold or (_rl_font or "Helvetica"),
            alignment=_align,
        )
        body_style = ParagraphStyle(
            "Body2",
            parent=styles["BodyText"],
            fontSize=11,
            leading=16,
            alignment=_align,
            fontName=_rl_font or "Helvetica",
        )
        quote_style = ParagraphStyle(
            "Quote",
            parent=body_style,
            textColor=HexColor("#374151"),
            # V0.6.5: the quote indent follows the reading direction.
            rightIndent=18 if _rtl else 0,
            leftIndent=0 if _rtl else 18,
        )

        story: list = []
        if title:
            story.append(Paragraph(_frag(title), title_style))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=HexColor("#1a1a1a"),
                    spaceBefore=2,
                    spaceAfter=10,
                )
            )

        current_list: list[ListItem] | None = None

        def flush_list():
            nonlocal current_list
            if current_list:
                story.append(ListFlowable(current_list, bulletType="bullet", start="•"))
                story.append(Spacer(1, 4))
                current_list = None

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if line.strip() == "---":
                continue
            m = re.match(r"^(#{1,6})\s+(.+)$", line)
            if m:
                flush_list()
                level = len(m.group(1))
                txt = _frag(m.group(2).strip())
                if level == 1:
                    story.append(Paragraph(txt, title_style))
                elif level == 2:
                    story.append(Paragraph(txt, h1_style))
                else:
                    story.append(Paragraph(txt, h2_style))
                continue
            if re.match(r"^\s*[-*+]\s+", line):
                item = _frag(re.sub(r"^\s*[-*+]\s+", "", line))
                if current_list is None:
                    current_list = []
                # V0.6.5: RTL bullets hang on the right edge (0, not None —
                # ReportLab's bullet-position arithmetic chokes on None).
                if _rtl:
                    current_list.append(
                        ListItem(Paragraph(item, body_style), rightIndent=18, leftIndent=0)
                    )
                else:
                    current_list.append(ListItem(Paragraph(item, body_style), leftIndent=18))
                continue
            if re.match(r"^\s*\d+\.\s+", line):
                flush_list()
                item = _frag(re.sub(r"^\s*\d+\.\s+", "", line))
                story.append(
                    ListFlowable([ListItem(Paragraph(item, body_style))], bulletType="1", start="1")
                )
                continue
            if line.startswith(">"):
                flush_list()
                txt = _frag(line.lstrip(">").strip())
                if txt:
                    story.append(Paragraph(txt, quote_style))
                continue
            if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
                flush_list()
                story.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.5,
                        color=HexColor("#d1d5db"),
                        spaceBefore=6,
                        spaceAfter=6,
                    )
                )
                continue
            if not line.strip():
                flush_list()
                story.append(Spacer(1, 6))
                continue
            flush_list()
            story.append(Paragraph(_frag(line), body_style))

        flush_list()
        doc.build(story)
        return True
    except Exception as e:
        logger.error(f"PDF write failed (ReportLab): {e}")
        return False


def _strip_md(text: str) -> str:
    """Strip common markdown markers for ReportLab (which doesn't render md)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)  # bold → reportlab bold
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)  # italic → reportlab italic
    text = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)  # links → text only
    return text


# ── Unified entry point ───────────────────────────────────────────────


def write_output(
    text: str,
    out_path: Path,
    *,
    fmt: OutputFormat | str = ".md",
    title: str | None = None,
    obsidian: bool = False,
    source_filename: str | None = None,
    tags: list[str] | None = None,
    quality: str | None = None,
    model: str | None = None,
    rtl: bool | None = None,
) -> tuple[bool, str]:
    """Write ``text`` to ``out_path`` in the chosen format.

    Returns ``(success, message)``. If ``obsidian=True`` and ``fmt == '.md'``,
    the markdown is first run through :func:`to_obsidian_markdown`.

    For non-markdown formats, the Obsidian flag is ignored (Obsidian
    callouts are markdown-only syntax).

    V0.6.5: ``rtl=None`` (the default) AUTO-DETECTS the direction from
    the text letters (utils.rtl — ≥35% RTL letters ⇒ RTL document) and
    threads it into every writer: md → ``dir: rtl`` front-matter,
    docx → ``w:bidi`` + right alignment, pdf → direction CSS / shaping.
    An explicit ``True``/``False`` overrides the detection.
    """
    # V0.6.5: resolve once, thread everywhere.
    if rtl is None:
        rtl = is_rtl_dominant(text)
    rtl = bool(rtl)

    fmt = str(fmt).lower()
    if not fmt.startswith("."):
        fmt = "." + fmt

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == ".md":
        if obsidian:
            text = to_obsidian_markdown(
                text,
                title=title or source_filename,
                source_filename=source_filename,
                tags=tags,
                quality=quality,
                model=model,
                rtl=rtl,
            )
        elif rtl:
            # V0.6.5: plain .md gets the Obsidian ``dir: rtl`` property too
            # (markdown viewers ignore it; Obsidian honors it).
            text = _ensure_md_dir_rtl(text)
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        atomic_write_text(out_path, text, encoding="utf-8")
        return True, f"Wrote {out_path.name} ({len(text):,} chars)"

    if fmt == ".docx":
        ok = write_docx(text, out_path, title=title, rtl=rtl)
        if ok:
            return True, f"Wrote {out_path.name}"
        # Fallback: write .md next to the requested .docx
        fallback = out_path.with_suffix(".md")
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        # V0.6.5: keep the RTL property on the markdown fallback as well.
        if rtl:
            text = _ensure_md_dir_rtl(text)
        atomic_write_text(fallback, text, encoding="utf-8")
        return False, f"python-docx unavailable — wrote {fallback.name} instead"

    if fmt == ".pdf":
        ok = write_pdf(text, out_path, title=title, rtl=rtl)
        if ok:
            return True, f"Wrote {out_path.name}"
        fallback = out_path.with_suffix(".md")
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        # V0.6.5: keep the RTL property on the markdown fallback as well.
        if rtl:
            text = _ensure_md_dir_rtl(text)
        atomic_write_text(fallback, text, encoding="utf-8")
        return False, f"PDF backend unavailable — wrote {fallback.name} instead"

    # Unknown format → default to .md
    # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
    atomic_write_text(out_path, text, encoding="utf-8")
    return True, f"Wrote {out_path.name} (unknown fmt, used .md)"
