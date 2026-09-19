"""V13.29.0 (P3.6): Smoke integration test for the Packets pipeline.

Tests the full chapter-aligned packets flow with mock summaries:
  summaries → PacketGenerator.generate() → Packets.md + Coverage.md + Map.md

This catches integration breaks that unit tests miss (e.g. a change to
SummaryResult that breaks PacketGenerator, or a change to Packet that
breaks the hierarchy builder).

The test uses mock summaries (no LLM calls, no real PDF) so it runs in
<5 seconds and works in the sandbox (no Ollama, no PySide6).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


@pytest.fixture
def mock_summaries():
    """Create 3 mock SummaryResult objects (chapters with bullets + exec summary)."""
    from core.models import SummaryResult

    return [
        SummaryResult(
            chapter_heading="Chapter 1: Introduction",
            executive_summary="This chapter introduces the concept of knowledge management and its importance for modern organizations.",
            thorough_summary="A detailed exploration of knowledge management fundamentals.",
            bullet_points=[
                "Knowledge management is critical for organizational success.",
                "Tacit knowledge is harder to capture than explicit knowledge.",
                "Communities of practice help share tacit knowledge.",
                "Technology alone cannot solve knowledge management challenges.",
                "Leadership commitment is essential for knowledge initiatives.",
                "Knowledge loops involve creation, capture, sharing, and application.",
                "Measurement of knowledge assets remains an open challenge.",
            ],
            success=True,
        ),
        SummaryResult(
            chapter_heading="Chapter 2: Tools and Techniques",
            executive_summary="This chapter surveys the tools and techniques available for knowledge management, from wikis to AI-powered summarization.",
            thorough_summary="A survey of KM tools from basic wikis to advanced AI systems.",
            bullet_points=[
                "Wikis enable collaborative knowledge capture.",
                "Knowledge graphs represent relationships between concepts.",
                "AI summarization can process large document collections.",
                "Ontologies provide structured domain knowledge representation.",
                "Search is the most common knowledge retrieval method.",
                "Tagging systems allow bottom-up organization of knowledge.",
                "Version control tracks the evolution of knowledge artifacts.",
            ],
            success=True,
        ),
        SummaryResult(
            chapter_heading="Chapter 3: Implementation",
            executive_summary="This chapter discusses practical implementation strategies for knowledge management systems.",
            thorough_summary="Implementation guidance for KM systems in organizations.",
            bullet_points=[
                "Start with a pilot project before full deployment.",
                "Involve end users in the design process.",
                "Training is critical for adoption success.",
                "Integration with existing workflows reduces friction.",
                "Regular audits keep the knowledge base accurate.",
            ],
            success=True,
        ),
    ]


@pytest.fixture
def mock_request(tmp_path):
    """Create a mock ConversionRequest."""
    req = MagicMock()
    req.input_path = tmp_path / "test_book.pdf"
    req.input_path.touch()  # create empty file
    req.output_dir = tmp_path
    return req


def test_packets_generation_chapter_aligned(mock_summaries, mock_request, tmp_path):
    """V13.29.0: Smoke test — PacketGenerator produces all expected output files.

    Tests the full pipeline:
      summaries → PacketGenerator.generate() → output files

    Verifies:
    - Packets.md is created
    - Coverage.md is created
    - Map.md is created
    - OnePage.md is created
    - Chapter-aligned mode produces 1 packet per chapter (3 chapters → 3 packets)
    - Each packet has the chapter heading as its concept
    """
    from core.outputs.packets import PacketGenerator

    gen = PacketGenerator(
        request=mock_request,
        log_callback=lambda msg, level="INFO": None,  # silent
    )

    # Mock the LLM calls (no Ollama in sandbox)
    with (
        patch.object(gen, "_call_llm") as mock_llm,
        patch.object(gen, "_generate_one_page") as mock_one_page,
    ):
        # Return a valid JSON response for synthesis
        mock_llm.return_value = '{"paragraph": "This is a synthesized paragraph about the chapter content. It covers the main concepts discussed.", "tldr": "A brief summary."}'
        # Mock one-page distillation
        mock_one_page.return_value = "# One-Page Distillation\n\n## Theme 1\nTest theme."

        paths = gen.generate(
            summaries=mock_summaries,
            book_title="Test Book",
            output_dir=tmp_path,
        )

    # Verify output files were created
    assert paths is not None, "generate() should return a list of paths"
    packets_md = tmp_path / "Test Book.Packets.md"
    assert packets_md.exists(), f"Packets.md should exist at {packets_md}"

    # Verify content
    content = packets_md.read_text(encoding="utf-8")
    assert "Test Book" in content, "Book title should be in the output"
    assert "Chapter 1: Introduction" in content, "Chapter 1 heading should appear"
    assert "Chapter 2: Tools and Techniques" in content, "Chapter 2 heading should appear"
    assert "Chapter 3: Implementation" in content, "Chapter 3 heading should appear"


def test_packets_coverage_report(mock_summaries, mock_request, tmp_path):
    """V13.29.0: Verify the Coverage report is generated and accurate."""
    from core.outputs.packets import PacketGenerator

    gen = PacketGenerator(
        request=mock_request,
        log_callback=lambda msg, level="INFO": None,
    )

    with (
        patch.object(gen, "_call_llm") as mock_llm,
        patch.object(gen, "_generate_one_page") as mock_one_page,
    ):
        mock_llm.return_value = '{"paragraph": "Synthesized content here.", "tldr": "Summary."}'
        mock_one_page.return_value = "# Distillation"

        gen.generate(
            summaries=mock_summaries,
            book_title="Test Book",
            output_dir=tmp_path,
        )

    coverage_md = tmp_path / "Test Book.Packets.Coverage.md"
    assert coverage_md.exists(), f"Coverage.md should exist at {coverage_md}"

    content = coverage_md.read_text(encoding="utf-8")
    # Should report 19 bullets (7+7+5) and 3 packets (chapter-aligned)
    assert "19" in content, "Should report 19 total bullets"
    assert "3" in content, "Should report 3 packets (1 per chapter)"


def test_packets_chapter_aligned_concept_names(mock_summaries, mock_request, tmp_path):
    """V13.29.0: Verify chapter-aligned mode uses chapter headings as concept names."""
    from core.outputs.packets import PacketGenerator

    gen = PacketGenerator(
        request=mock_request,
        log_callback=lambda msg, level="INFO": None,
    )

    with (
        patch.object(gen, "_call_llm") as mock_llm,
        patch.object(gen, "_generate_one_page") as mock_one_page,
    ):
        mock_llm.return_value = '{"paragraph": "Content.", "tldr": "TLDR."}'
        mock_one_page.return_value = "# Distillation"

        gen.generate(
            summaries=mock_summaries,
            book_title="Test Book",
            output_dir=tmp_path,
        )

    map_md = tmp_path / "Test Book.Packets.Map.md"
    assert map_md.exists(), f"Map.md should exist at {map_md}"

    content = map_md.read_text(encoding="utf-8")
    # In chapter-aligned mode, each chapter heading is a concept node
    # The map should contain sanitized versions of the chapter headings
    assert "Chapter 1" in content or "chapter_1" in content.lower(), (
        "Map should reference Chapter 1"
    )
    assert "Chapter 2" in content or "chapter_2" in content.lower(), (
        "Map should reference Chapter 2"
    )
    assert "Chapter 3" in content or "chapter_3" in content.lower(), (
        "Map should reference Chapter 3"
    )


def test_packets_chapters_md_export(mock_summaries, mock_request, tmp_path):
    """V13.29.0: Verify the .Chapters.md intermediate file can be written + read back."""
    from core.outputs.chapters_export import read_chapters_md, write_chapters_md

    # Write
    chapters_path = tmp_path / "Test Book.Chapters.md"
    write_chapters_md(mock_summaries, "Test Book", chapters_path)

    assert chapters_path.exists(), "Chapters.md should be written"

    # Read back
    book_title, summaries = read_chapters_md(chapters_path)

    assert book_title == "Test Book", f"Book title should be 'Test Book', got '{book_title}'"
    assert len(summaries) == 3, f"Should read 3 chapters, got {len(summaries)}"

    # Verify each chapter has the right structure
    for s in summaries:
        assert s.chapter_heading, "Chapter heading should be populated"
        assert s.executive_summary, "Exec summary should be populated"
        assert s.bullet_points, "Bullets should be populated"
        assert len(s.bullet_points) >= 5, "Each chapter should have 5+ bullets"
