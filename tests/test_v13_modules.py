"""V13.30.0 (P3.2): Tests for new V13.x modules — chapters_export, thresholds, vram_calculator.

Raises test coverage for the modules added in V13.23.0–V13.29.0.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── chapters_export tests ──────────────────────────────────────────────────

class TestChaptersExport:
    """Tests for core/outputs/chapters_export.py (V13.23.0)."""

    def test_write_and_read_roundtrip(self, tmp_path):
        """Write a .Chapters.md file and read it back — should match."""
        from core.models import SummaryResult
        from core.outputs.chapters_export import read_chapters_md, write_chapters_md

        summaries = [
            SummaryResult(
                chapter_heading="Chapter 1: Test",
                executive_summary="This is the exec summary for chapter 1.",
                thorough_summary="Detailed thorough summary.",
                bullet_points=["Bullet 1", "Bullet 2", "Bullet 3"],
                success=True,
            ),
            SummaryResult(
                chapter_heading="Chapter 2: Another",
                executive_summary="Exec summary for chapter 2.",
                thorough_summary="Another thorough summary.",
                bullet_points=["Point A", "Point B"],
                success=True,
            ),
        ]

        out_path = tmp_path / "Test Book.Chapters.md"
        write_chapters_md(summaries, "Test Book", out_path)

        assert out_path.exists()
        book_title, read_summaries = read_chapters_md(out_path)

        assert book_title == "Test Book"
        assert len(read_summaries) == 2
        assert read_summaries[0].chapter_heading == "Chapter 1: Test"
        assert read_summaries[1].chapter_heading == "Chapter 2: Another"
        assert "Bullet 1" in read_summaries[0].bullet_points
        assert "Point A" in read_summaries[1].bullet_points

    def test_write_includes_toc(self, tmp_path):
        """The written file should include a Table of Contents."""
        from core.models import SummaryResult
        from core.outputs.chapters_export import write_chapters_md

        summaries = [
            SummaryResult(
                chapter_heading="Intro",
                executive_summary="Intro summary.",
                thorough_summary="",
                bullet_points=["Bullet 1"],
                success=True,
            ),
        ]
        out_path = tmp_path / "Book.Chapters.md"
        write_chapters_md(summaries, "My Book", out_path)

        content = out_path.read_text(encoding="utf-8")
        assert "## Table of Contents" in content
        assert "1. Intro" in content
        assert "# My Book" in content

    def test_read_empty_file_raises(self, tmp_path):
        """Reading an empty file should raise ValueError."""
        from core.outputs.chapters_export import read_chapters_md

        empty_path = tmp_path / "empty.md"
        empty_path.write_text("")
        with pytest.raises(ValueError):
            read_chapters_md(empty_path)


# ── thresholds tests ──────────────────────────────────────────────────────

class TestThresholds:
    """Tests for core/summarisation/thresholds.py (V13.27.0)."""

    def test_thresholds_exist(self):
        """All 5 grounding thresholds should be defined."""
        from core.summarisation.thresholds import (
            F4_SOURCE_OVERLAP_DROP,
            F4_SOURCE_OVERLAP_RECOVER,
            PACKETS_VALIDATION_TRACE,
            SEMANTIC_FACT_CHECK_DROP,
            VERIFY_BULLETS_MARK,
        )
        assert F4_SOURCE_OVERLAP_DROP == 0.25
        assert F4_SOURCE_OVERLAP_RECOVER == 0.30
        assert VERIFY_BULLETS_MARK == 0.50
        assert SEMANTIC_FACT_CHECK_DROP == 0.50
        assert PACKETS_VALIDATION_TRACE == 0.42

    def test_recovery_higher_than_drop(self):
        """Recovery threshold should be higher than drop (borderline bullets stay dropped)."""
        from core.summarisation.thresholds import F4_SOURCE_OVERLAP_DROP, F4_SOURCE_OVERLAP_RECOVER
        assert F4_SOURCE_OVERLAP_RECOVER > F4_SOURCE_OVERLAP_DROP

    def test_packets_trace_lower_than_semantic(self):
        """Packets validation threshold should be lower than semantic fact-check
        (synthesis produces cross-bullet framing sentences)."""
        from core.summarisation.thresholds import PACKETS_VALIDATION_TRACE, SEMANTIC_FACT_CHECK_DROP
        assert PACKETS_VALIDATION_TRACE < SEMANTIC_FACT_CHECK_DROP


# ── VRAM calculator tests ─────────────────────────────────────────────────

class TestVRamCalculator:
    """Tests for core/vram_calculator.py (V13.26.0 rewrite)."""

    def test_parse_param_count(self):
        """Parameter count parsing from model names."""
        from core.vram_calculator import _parse_param_count
        assert _parse_param_count("gemma-4-12b-it") == 12.0
        assert _parse_param_count("qwen3.5-9b") == 9.0
        assert _parse_param_count("llama-7b") == 7.0
        assert _parse_param_count("nllb-200-distilled-600m") == 0.6
        assert _parse_param_count("model-without-params") is None

    def test_parse_quantization(self):
        """Quantization tag parsing from model names."""
        from core.vram_calculator import _parse_quantization
        assert _parse_quantization("model-Q5_K_XL")[0] == "q5_k_xl"
        assert _parse_quantization("model-Q4_K_M")[0] == "q4_k_m"
        assert _parse_quantization("model-Q8_0")[0] == "q8_0"
        assert _parse_quantization("model-F16")[0] == "f16"
        assert _parse_quantization("model-no-quant")[0] == "unknown"

    def test_estimate_gemma_4_12b_q5_xl_32k(self):
        """Gemma 4 12B Q5_K_XL at 32k context should estimate ~10.9 GB."""
        from core.vram_calculator import _estimate_model_vram
        vram = _estimate_model_vram("gemma-4-12b-it-Q5_K_XL", "Summarization", 32768)
        # Should be ~10.9 GB (weights 8.64 + KV 1.8 + overhead 0.5)
        assert 10.0 < vram < 11.5, f"Expected ~10.9 GB, got {vram}"

    def test_estimate_lower_context_uses_less_vram(self):
        """Same model at 8k context should use less VRAM than at 32k."""
        from core.vram_calculator import _estimate_model_vram
        vram_32k = _estimate_model_vram("gemma-4-12b-Q5_K_XL", "Sum", 32768)
        vram_8k = _estimate_model_vram("gemma-4-12b-Q5_K_XL", "Sum", 8192)
        assert vram_8k < vram_32k, "8k context should use less VRAM than 32k"

    def test_calculate_vram_budget_returns_tuple(self):
        """calculate_vram_budget should return (estimates, peak, total, recommendation)."""
        from core.vram_calculator import calculate_vram_budget
        estimates, peak, total, rec = calculate_vram_budget(
            summarization_model="gemma-4-12b-Q5_K_XL",
            max_workers=1,
            context_tokens=32768,
        )
        assert isinstance(estimates, list)
        assert isinstance(peak, float)
        assert peak > 0
        assert isinstance(rec, str)
        assert len(rec) > 0
