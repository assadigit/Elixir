"""V8.0.0 #10: Packets of Knowledge extensions.

Extends the V7.3.0 Packets of Knowledge with three new output formats:

1. **Styled PDF export** — renders the packets document as a beautifully
   styled PDF using the app's theme colors (terracotta-amber on ivory).
   Uses reportlab (already a dependency for DOCX generation).

2. **Per-packet TTS audio** — generates a short spoken audio clip for each
   packet (the TL;DR + Q&A), so the user can listen to key concepts.
   Uses the existing TTS router (NeuTTS/Kokoro for EN, Piper for FA).

3. **Lecture format** — rewrites the packets as a continuous lecture
   narrative (one host, educational tone), distinct from the 2-host
   podcast format.  Good for focused study.

Translation integration is handled by the existing translation service —
packets .md files are already in the translation file map and will be
translated when translation is enabled.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

logger = logging.getLogger(__name__)


class PacketsPDFExporter:
    """Renders a packets .md file as a styled PDF using reportlab."""

    def __init__(self, log_callback: Callable[[str, str], None] | None = None) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)

    def export(self, packets_md_path: Path, output_pdf_path: Path, book_title: str) -> Path | None:
        """Export a packets.md to a styled PDF.

        Args:
            packets_md_path: path to the {book}.Packets.md file.
            output_pdf_path: where to save the PDF.
            book_title: the book title (for the PDF title page).

        Returns the PDF path on success, None on failure.
        """
        try:
            from reportlab.lib.colors import HexColor
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
            )
        except ImportError:
            self.log("  ⚠️ Packets PDF: reportlab not installed", "WARNING")
            return None

        if not packets_md_path.exists():
            self.log(f"  ⚠️ Packets PDF: source not found: {packets_md_path}", "WARNING")
            return None

        # Theme colors (match the app's warm palette)
        accent = HexColor("#B8704A")  # terracotta
        text_primary = HexColor("#2A211B")  # warm dark brown
        text_secondary = HexColor("#6B5B4F")  # warm brown

        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_pdf_path),
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            title=f"{book_title} — Packets of Knowledge",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PacketTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=accent,
            spaceAfter=6 * mm,
        )
        h2_style = ParagraphStyle(
            "PacketH2",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=accent,
            spaceBefore=8 * mm,
            spaceAfter=3 * mm,
        )
        h3_style = ParagraphStyle(
            "PacketH3",
            parent=styles["Heading3"],
            fontSize=12,
            textColor=text_secondary,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
        )
        body_style = ParagraphStyle(
            "PacketBody",
            parent=styles["BodyText"],
            fontSize=10,
            textColor=text_primary,
            leading=14,
            spaceAfter=3 * mm,
        )
        tldr_style = ParagraphStyle(
            "PacketTLDR",
            parent=body_style,
            fontSize=10,
            textColor=accent,
            fontName="Helvetica-Oblique",
        )

        story: list = []
        # Title page
        story.append(Paragraph(f"{book_title}", title_style))
        story.append(
            Paragraph(
                "Packets of Knowledge",
                ParagraphStyle(
                    "Subtitle",
                    parent=styles["Normal"],
                    fontSize=14,
                    textColor=text_secondary,
                    alignment=TA_CENTER,
                    spaceAfter=10 * mm,
                ),
            )
        )
        story.append(PageBreak())

        # Parse the markdown + render
        content = packets_md_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 3 * mm))
                continue
            # Escape HTML entities for reportlab
            safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Convert markdown bold **text** to <b>text</b>
            safe = safe.replace("**", "<b>", 1) if "**" in safe else safe
            # Simple heading detection
            if stripped.startswith("# "):
                story.append(Paragraph(safe[2:], title_style))
            elif stripped.startswith("## "):
                story.append(Paragraph(safe[3:], h2_style))
            elif stripped.startswith("### "):
                story.append(Paragraph(safe[4:], h3_style))
            elif stripped.startswith("> "):
                story.append(Paragraph(safe[2:], tldr_style))
            elif stripped.startswith("- "):
                story.append(Paragraph(f"• {safe[2:]}", body_style))
            else:
                story.append(Paragraph(safe, body_style))

        doc.build(story)
        self.log(f"  ✅ Packets PDF: {output_pdf_path}", "SUCCESS")
        return output_pdf_path


class PacketsLectureGenerator(OutputGeneratorBase):
    """V8.0.0 #10: Rewrites packets as a continuous lecture narrative.

    Produces a single-host educational lecture (distinct from the 2-host
    podcast).  Good for focused study — one voice walking through each
    packet's key concept.
    """

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate a lecture-format document from the packets.

        Reads the existing {book}.Packets.md (generated by PacketGenerator)
        and rewrites it as a lecture narrative via LLM.
        """
        # Find the packets file
        packets_path = output_dir / f"{book_title}.Packets.md"
        if not packets_path.exists():
            self.log(f"  ℹ️ Packets lecture: no packets file at {packets_path}", "INFO")
            return None

        packets_content = packets_path.read_text(encoding="utf-8")
        if not packets_content.strip():
            self.log("  ⚠️ Packets lecture: packets file is empty", "WARNING")
            return None

        # Build the lecture prompt
        prompt = self.prompt_manager.render_template(
            "outputs/packets_lecture",
            book_title=book_title,
            packets_content=packets_content[:6000],
        )

        self.log("  🎓 Generating packets lecture format…", "INFO")
        response = self._call_llm(prompt, temperature=0.5, max_tokens=8192)
        if not response:
            self.log("  ⚠️ Packets lecture: LLM returned no response", "WARNING")
            return None

        lecture = self._strip_thinking(response)
        output_path = output_dir / f"{book_title}.Packets.Lecture.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            output_path,
            f"# Lecture: {book_title}\n\n"
            f"> Single-host educational narrative · generated from Packets of Knowledge\n\n---\n\n"
            f"{lecture}\n",
            encoding="utf-8",
        )
        self.log(f"  ✅ Packets lecture: {output_path}", "SUCCESS")
        return output_path


class PacketsAudioGenerator(OutputGeneratorBase):
    """V8.0.0 #10: Generates a short TTS audio clip per packet.

    For each packet, synthesizes the TL;DR + Q&A as a short spoken clip
    (~30-60 seconds each).  Uses the existing TTS router.
    """

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> list[Path] | None:
        """Generate per-packet audio clips from the packets file."""
        packets_path = output_dir / f"{book_title}.Packets.md"
        if not packets_path.exists():
            self.log(f"  ℹ️ Packets audio: no packets file at {packets_path}", "INFO")
            return []

        content = packets_path.read_text(encoding="utf-8")
        # Parse packets — each starts with "## Packet N:" or "### Packet N:"
        import re

        packet_blocks = re.split(r"^##+\s+Packet\s+\d+", content, flags=re.MULTILINE)
        if len(packet_blocks) <= 1:
            self.log("  ℹ️ Packets audio: no packet blocks found", "INFO")
            return []

        # Extract TL;DR + Q&A from each block
        clips: list[tuple[int, str]] = []  # (packet_num, text_to_speak)
        for i, block in enumerate(packet_blocks[1:], 1):  # skip preamble
            # Find TL;DR line
            tldr_match = re.search(r"TL;DR:\s*(.+)", block)
            qa_match = re.search(r"Q:\s*(.+)", block)
            text_parts = []
            if tldr_match:
                text_parts.append(tldr_match.group(1).strip())
            if qa_match:
                text_parts.append(qa_match.group(1).strip())
            if text_parts:
                clips.append((i, ". ".join(text_parts)))

        if not clips:
            self.log("  ℹ️ Packets audio: no TL;DR/Q&A found in packets", "INFO")
            return []

        self.log(f"  🎙️ Generating {len(clips)} packet audio clips…", "INFO")

        # Load TTS settings
        from utils.settings import Settings

        s = Settings()
        from core.tts.engine import TTSRouter

        piper_binary = Path(s.get("tts.piper_binary", ""))
        en_engine = s.get("tts.en_engine", "neutts")
        neutts_gguf = s.get("tts.neutts_gguf_path", "")
        neutts_project = s.get("tts.neutts_project_path", "")

        router = TTSRouter(
            piper_binary=piper_binary if piper_binary else None,
            piper_voices_dir=piper_binary.parent / "voices" if piper_binary else None,
            en_engine=en_engine,
            neutts_gguf_path=Path(neutts_gguf) if neutts_gguf else None,
            neutts_project_path=Path(neutts_project) if neutts_project else None,
            fa_engine=s.get("tts.fa_engine", "piper"),  # V10.37.0
            coqui_model=s.get("tts.coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2"),
            coqui_speaker=s.get("tts.coqui_speaker", "Ana"),
            coqui_voice_sample=s.get("tts.coqui_voice_sample", ""),
            log_callback=self.log,
        )

        voice = s.get("tts.host_a_voice", "dave") or "dave"
        speed = float(s.get("tts.speed", 1.0))

        audio_dir = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        output_paths: list[Path] = []
        for pkt_num, text in clips:
            clip_path = audio_dir / f"packet_{pkt_num:02d}.wav"
            self.log(f"  🎙️ Packet {pkt_num}/{len(clips)}: {text[:60]}…", "INFO")
            result = router.synthesize(text, clip_path, "en", voice, speed)
            if result:
                output_paths.append(result)

        if output_paths:
            self.log(f"  ✅ Packets audio: {len(output_paths)} clips generated", "SUCCESS")
        return output_paths
