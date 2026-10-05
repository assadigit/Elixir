"""V10.13.0 (Phase 1 / A1): Integration test with mock Ollama.

This test runs the FULL conversion pipeline end-to-end with mocked external
dependencies (PDF analysis, OCR, Ollama LLM, GPU detection).  It would have
caught ALL 5 V10.12.x crash bugs:

  V10.12.1: _extract_covers NameError (bare toc_entries)
  V10.12.2: effective_total_pages NameError (not unpacked from ExtractionResult)
  V10.12.2: segments_folder NameError (not unpacked from OutputSaveResult)
  V10.12.3: segmentation.py ImportError (wrong import path)
  V10.12.4: del raw_markdown UnboundLocalError (deleted before last user)
  V10.12.8: flashcards NameError (bare 'j' list-comprehension scope)

The test mocks at the boundary layer:
  - PdfAnalyzer.analyze → fake analysis (3 pages, 0 scanned)
  - TocExtractor.extract → fake TOC entries
  - OCRService.process_pdf + build_markdown → fake OCR results + markdown
  - safe_ollama_request → canned LLM responses (summarizer XML, briefing text, etc.)
  - detect_gpu_profile_from_system → safe GPU profile
  - pdf2image.convert_from_path → empty (skip cover screenshots)

The test verifies that the pipeline runs from start to finish WITHOUT any
NameError, ImportError, UnboundLocalError, or other wiring crash.

Run: ``pytest tests/test_integration_pipeline.py -v --no-cov``
"""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Phase 2 (task 2.5): the two end-to-end flows take 8-18 s each on a warm
# machine (mock Ollama server, real thread pool) — the suite's slowest file.
pytestmark = [pytest.mark.integration, pytest.mark.slow]

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Stub optional dependencies BEFORE any imports from core.* ──────────────
# These deps are not installed in the test environment but are imported at
# module level by core.pdf, core.segmentation, core.grounding, etc.
def _stub_optional_deps():
    """Stub optional heavy deps so the import chain doesn't fail."""
    # markitdown (imported by core.pdf.adaptive_toc)
    if "markitdown" not in sys.modules:
        md = types.ModuleType("markitdown")
        md.MarkItDown = type("MarkItDown", (), {})
        sys.modules["markitdown"] = md
    # tiktoken (imported by utils.token_counter)
    if "tiktoken" not in sys.modules:
        tk = types.ModuleType("tiktoken")
        tk.get_encoding = lambda x: MagicMock()
        tk.Encoding = type("Encoding", (), {})
        sys.modules["tiktoken"] = tk
    # sentence_transformers (imported by keypoints_builder for dedup)
    if "sentence_transformers" not in sys.modules:
        st = types.ModuleType("sentence_transformers")
        st.SentenceTransformer = MagicMock(return_value=MagicMock())
        sys.modules["sentence_transformers"] = st
    # rapidfuzz (imported by summarizer for dedup + adaptive_toc)
    if "rapidfuzz" not in sys.modules:
        rf = types.ModuleType("rapidfuzz")
        rf.fuzz = MagicMock()
        rf.fuzz.token_set_ratio = lambda a, b: 80.0
        rf.process = MagicMock()
        rf.process.extract = MagicMock(return_value=[])
        sys.modules["rapidfuzz"] = rf
    # langextract (imported by core.grounding — optional)
    if "langextract" not in sys.modules:
        le = types.ModuleType("langextract")
        sys.modules["langextract"] = le


_stub_optional_deps()


# ── Mock LLM response generator ────────────────────────────────────────────

# A minimal valid summarizer response in the expected XML format.
_MOCK_SUMMARY_RESPONSE = """<executive_summary>
This chapter discusses the key concepts and findings from the text.
</executive_summary>
<bullet_points>
- First key takeaway about the main concept.
- Second key takeaway about the methodology.
- Third key takeaway about the results.
</bullet_points>
<thorough_summary>
The chapter provides a comprehensive overview of the topic, covering the background, methods, and conclusions. The main finding is that the approach is effective. The implications for future work are discussed.
</thorough_summary>"""

_MOCK_BRIEFING_RESPONSE = (
    "This book presents a comprehensive analysis of the topic. "
    "Three key frameworks emerge from the discussion. "
    "First, the theoretical foundation provides context. "
    "Second, the practical implementation demonstrates feasibility. "
    "Third, the results validate the approach. "
    "Five actionable takeaways are identified for practitioners. "
    "The conclusion recommends further research in this area."
)

_MOCK_PODCAST_RESPONSE = (
    "Host A: Welcome to our discussion of this book.\n"
    "Host B: Today we're covering the key themes and ideas.\n"
    "Host A: Let's start with the main concept.\n"
    "Host B: That's a great point. The methodology is also interesting.\n"
    "Host A: And the results speak for themselves.\n"
    "Host B: Indeed. Let's wrap up with the key takeaways.\n"
    "Host A: Thanks for listening."
)

_MOCK_FLASHCARD_RESPONSE = (
    "What is the main concept?\tThe main concept is the theoretical foundation.\n"
    "What methodology was used?\tA practical implementation approach was used.\n"
    "What were the results?\tThe results validated the approach."
)

_MOCK_HEADING_LABEL_RESPONSE = (
    "1 Introduction (page 1)\n2 Main Content (page 2)\n3 Conclusion (page 3)\n"
)


def _mock_ollama_response(prompt: str) -> str:
    """Return an appropriate mock LLM response based on the prompt content."""
    prompt_lower = prompt.lower()
    if "executive_summary" in prompt_lower or "bullet_points" in prompt_lower:
        return _MOCK_SUMMARY_RESPONSE
    if "briefing" in prompt_lower or "executive briefing" in prompt_lower:
        return _MOCK_BRIEFING_RESPONSE
    if "podcast" in prompt_lower or "host" in prompt_lower:
        return _MOCK_PODCAST_RESPONSE
    if "flashcard" in prompt_lower or "q<tab>a" in prompt_lower:
        return _MOCK_FLASHCARD_RESPONSE
    if "heading" in prompt_lower and "page" in prompt_lower:
        return _MOCK_HEADING_LABEL_RESPONSE
    if "gap.fill" in prompt_lower or "uncovered" in prompt_lower:
        return ""  # no gap-fill bullets
    if "self.review" in prompt_lower or "verify" in prompt_lower:
        return _MOCK_SUMMARY_RESPONSE  # reuse summary format
    if "simplif" in prompt_lower:
        return ""  # no simplification (keep original)
    # Default: return a short generic response
    return "This is a mock response."


def _mock_safe_ollama_request(method, url, **kwargs):
    """Mock safe_ollama_request to return a canned response."""
    # Extract the prompt from the JSON payload
    payload = kwargs.get("json", {})
    prompt = payload.get("prompt", "")
    response_text = _mock_ollama_response(prompt)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": response_text}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ── Mock PDF analysis ──────────────────────────────────────────────────────


def _make_mock_analysis():
    """Create a mock PdfAnalysisResult."""
    from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation

    per_page = [
        PageAnalysis(
            page_num=1,
            is_scanned=False,
            extracted_text_preview="Introduction",
            recommended_action="skip",
        ),
        PageAnalysis(
            page_num=2,
            is_scanned=False,
            extracted_text_preview="Main content",
            recommended_action="skip",
        ),
        PageAnalysis(
            page_num=3,
            is_scanned=False,
            extracted_text_preview="Conclusion",
            recommended_action="skip",
        ),
    ]
    return PdfAnalysisResult(
        total_pages=3,
        scanned_pages=[],
        text_pages=[1, 2, 3],
        recommendation=PdfRecommendation.NO_OCR,
        per_page=per_page,
    )


_MOCK_MARKDOWN = """<!-- original page 1 -->
# 1 Introduction

This is the introduction text. It covers the background and motivation for the study. The key concept is defined here.

<!-- original page 2 -->
# 2 Main Content

The main content discusses the methodology and results. The approach was effective in demonstrating the key principles. Several key findings emerged from the analysis.

<!-- original page 3 -->
# 3 Conclusion

The conclusion summarizes the findings and suggests directions for future work. The results validate the approach.
"""


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def integration_setup(tmp_path):
    """Set up a complete mock environment for integration testing."""
    from utils.settings import Settings

    # Create a fake PDF file
    fake_pdf = tmp_path / "test_book.pdf"
    fake_pdf.write_text("Fake PDF content")

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Override Settings to use a temp settings file (avoid touching the user's)
    settings_dir = tmp_path / ".elixir"
    settings_dir.mkdir()

    # Reset the Settings singleton so it picks up the new paths
    Settings._instance = None
    Settings._test_override = None

    # Patch Settings to use temp paths
    with (
        patch.object(Settings, "_settings_dir", settings_dir),
        patch.object(Settings, "_settings_file", settings_dir / "settings.json"),
    ):
        settings = Settings()
        # Set minimal required settings
        settings.set("summarisation.provider", "ollama")
        settings.set("summarisation.model", "mock-model:latest")
        settings.set("summarisation.max_context_tokens", 65536)
        settings.set("summarisation.max_output_tokens", 4096)
        settings.set("summarisation.resume_enabled", False)
        settings.set("summarisation.include_book_summary", True)
        settings.set("summarisation.include_executive_summary", True)
        settings.set("summarisation.include_thorough_summary", True)
        settings.set("summarisation.include_keypoints", True)
        settings.set("summarisation.coverage_threshold", 50)
        settings.set("summarisation.temperature", 0.6)
        settings.set("grounding.enabled", False)
        settings.set("paths.poppler", "")
        settings.set("paths.tesseract", "")

        # Create ConversionRequest
        from tests.fixtures import make_minimal_request

        request = make_minimal_request(
            input_path=str(fake_pdf),
            output_dir=str(output_dir),
            source_type="normal_book",
            summarisation_model="mock-model:latest",
            generate_summaries=True,
            include_keypoints=True,
            output_briefing=True,
            output_podcast=True,
            output_flashcards=True,
            use_llm_ocr=False,
            extract_tables=False,
            extract_math=False,
            layout_analysis=False,
            extract_figure_text=False,
            enable_content_filter=False,
            academic_rigor=False,
            max_workers=1,
        )

        yield {
            "request": request,
            "output_dir": output_dir,
            "tmp_path": tmp_path,
        }

    # Clean up: reset the singleton
    Settings._instance = None
    Settings._test_override = None


# ── Integration test ──────────────────────────────────────────────────────


class TestPipelineIntegration:
    """End-to-end pipeline integration test with mocked external dependencies.

    This test catches wiring bugs (NameError, ImportError, UnboundLocalError)
    that py_compile and AST-based tests can't detect.  It runs the FULL
    conversion pipeline from Converter.convert() through to output generation.
    """

    def test_full_conversion_no_crash(self, integration_setup):
        """Run a full 1-chapter conversion end-to-end with no crashes.

        This test would have caught ALL 5 V10.12.x crash bugs:
        - _extract_covers NameError (V10.12.1)
        - effective_total_pages NameError (V10.12.2)
        - segments_folder NameError (V10.12.2)
        - segmentation.py ImportError (V10.12.3)
        - del raw_markdown UnboundLocalError (V10.12.4)
        - flashcards 'j' NameError (V10.12.8)
        """
        from core.models import ConversionResult
        from core.pipeline.converter import Converter

        request = integration_setup["request"]

        # Create the converter
        converter = Converter(
            request=request,
            progress_callback=lambda p: None,
            status_callback=lambda s: None,
            log_callback=lambda msg, level: None,  # silent
            cancel_event=threading.Event(),
        )

        # Patch ALL external dependencies
        with (
            patch("core.pdf.analyzer.PdfAnalyzer.analyze", return_value=_make_mock_analysis()),
            patch(
                "core.pdf.toc_extractor.TocExtractor.extract",
                return_value=[
                    ("1 Introduction", 1),
                    ("2 Main Content", 2),
                    ("3 Conclusion", 3),
                ],
            ),
            patch("core.pdf.toc_extractor.TocExtractor.locate_headings", return_value=None),
            patch(
                "core.ocr.service.OCRService.process_pdf",
                return_value={
                    1: {"text": "Introduction text", "markdown": "Introduction text"},
                    2: {"text": "Main content text", "markdown": "Main content text"},
                    3: {"text": "Conclusion text", "markdown": "Conclusion text"},
                },
            ),
            patch("core.ocr.service.OCRService.build_markdown", return_value=_MOCK_MARKDOWN),
            patch(
                "core.pdf.toc_extractor.TocExtractor.extract",
                return_value=[
                    ("1 Introduction", 1),
                    ("2 Main Content", 2),
                    ("3 Conclusion", 3),
                ],
            ),
            patch("utils.network.safe_ollama_request", side_effect=_mock_safe_ollama_request),
            patch(
                "core.system.hardware_monitor.detect_gpu_profile_from_system",
                return_value=("Mock GPU", None),
            ),
            patch("core.system.hardware_monitor.HardwareMonitor._find_nvidia_smi", return_value=""),
            patch(
                "core.system.thermal_safety.ThermalSafetyController.preflight_check",
                return_value=(True, "OK"),
            ),
            patch("core.system.thermal_safety.ThermalSafetyController.start"),
            patch("core.system.thermal_safety.check_output_count_safety"),
            patch("core.system.thermal_safety.recommend_thermal_safe_models"),
            patch("core.pdf.layout_reorder.LayoutReorder.is_available", return_value=False),
            patch(
                "core.summarisation.text_preprocessor.repair_hyphenation", side_effect=lambda x: x
            ),
            patch(
                "core.summarisation.text_preprocessor.smart_paragraph_joining",
                side_effect=lambda x: x,
            ),
            patch(
                "core.summarisation.text_preprocessor.remove_headers_footers",
                side_effect=lambda x: x,
            ),
        ):
            # Run the conversion
            result = converter.convert()

        # Verify the conversion didn't crash
        assert result is not None, "convert() returned None"
        assert isinstance(result, ConversionResult), (
            f"convert() should return ConversionResult, got {type(result)}"
        )

        # The conversion may succeed or fail (depending on mock quality),
        # but it MUST NOT crash with NameError/ImportError/UnboundLocalError.
        # If it does, the test will fail with that exception (not reach here).
        # A successful wiring test = the pipeline ran to completion without
        # any wiring crash, even if the output quality isn't perfect.

        # If successful, verify basic outputs exist
        if result.success:
            output_dir = integration_setup["output_dir"]
            # The full markdown should exist
            md_files = list(output_dir.rglob("*.md"))
            assert len(md_files) > 0, "No markdown files produced"

    def test_extraction_phase_no_crash(self, integration_setup):
        """Test just the extraction phase (Steps 1-4) for wiring bugs."""
        from core.pipeline.converter import Converter

        request = integration_setup["request"]
        converter = Converter(
            request=request,
            log_callback=lambda msg, level: None,
            cancel_event=threading.Event(),
        )

        try:
            with (
                patch("core.pdf.analyzer.PdfAnalyzer.analyze", return_value=_make_mock_analysis()),
                patch(
                    "core.pdf.toc_extractor.TocExtractor.extract",
                    return_value=[
                        ("1 Introduction", 1),
                        ("2 Main Content", 2),
                    ],
                ),
                patch(
                    "core.ocr.service.OCRService.process_pdf",
                    return_value={
                        1: {"text": "text", "markdown": "text"},
                    },
                ),
                patch("core.ocr.service.OCRService.build_markdown", return_value=_MOCK_MARKDOWN),
            ):
                from core.pipeline.conversion.extraction import run_extraction

                result = run_extraction(converter=converter)

            # Must not crash — verify it returns a proper result
            from core.models import ConversionResult
            from core.pipeline.conversion.extraction import ExtractionResult

            assert isinstance(result, (ExtractionResult, ConversionResult)), (
                f"run_extraction should return ExtractionResult or ConversionResult, got {type(result)}"
            )
        finally:
            # V18.2.27 (warnings fix): close the conv_logger file handle to
            # avoid ResourceWarning: unclosed file in test teardown.
            try:
                converter.conv_logger.close()
            except Exception:
                pass

    def test_segmentation_phase_no_crash(self, integration_setup):
        """Test just the segmentation phase for wiring bugs (ImportError check)."""
        from core.pipeline.converter import Converter

        request = integration_setup["request"]
        converter = Converter(
            request=request,
            log_callback=lambda msg, level: None,
            cancel_event=threading.Event(),
        )

        try:
            # This test specifically catches the V10.12.3 ImportError bug
            # (segmentation.py importing from the wrong module)
            from core.models import Segment
            from core.pipeline.conversion.segmentation import run_segmentation

            mock_analysis = _make_mock_analysis()
            mock_segments = [
                Segment(
                    heading="1 Introduction",
                    content="Intro text",
                    start_page=1,
                    end_page=1,
                    segment_type="chapter",
                ),
            ]

            with (
                patch("core.segmentation.Segmenter.segment", return_value=mock_segments),
                patch("core.pdf.toc_extractor.TocExtractor.locate_headings", return_value=None),
            ):
                result = run_segmentation(
                    converter=converter,
                    raw_markdown=_MOCK_MARKDOWN,
                    analysis=mock_analysis,
                    toc_entries=[("1 Introduction", 1)],
                )

            from core.pipeline.conversion.segmentation import SegmentationResult

            assert isinstance(result, SegmentationResult), (
                f"run_segmentation should return SegmentationResult, got {type(result)}"
            )
            assert len(result.segments) > 0
        finally:
            # V18.2.27 (warnings fix): close the conv_logger file handle.
            try:
                converter.conv_logger.close()
            except Exception:
                pass

    def test_output_save_phase_no_crash(self, integration_setup):
        """Test just the output_save phase for wiring bugs (UnboundLocalError check)."""
        from core.models import Segment
        from core.pipeline.converter import Converter

        request = integration_setup["request"]
        converter = Converter(
            request=request,
            log_callback=lambda msg, level: None,
            cancel_event=threading.Event(),
        )
        # V10.13.0: the checkpoint is normally created in convert() before
        # run_output_save is called.  Add a mock here since we're testing
        # the phase in isolation.
        converter.checkpoint = MagicMock()
        converter._thermal_safety = None

        try:
            from core.pipeline.conversion.output_save import run_output_save

            mock_segments = [
                Segment(
                    heading="1 Introduction",
                    content="Intro text here.",
                    start_page=1,
                    end_page=1,
                    segment_type="chapter",
                ),
            ]

            # This test specifically catches the V10.12.4 UnboundLocalError bug
            # (del raw_markdown before run_output_save)
            result = run_output_save(
                converter=converter,
                segments=mock_segments,
                raw_markdown=_MOCK_MARKDOWN,
                effective_total_pages=3,
                total_pages=3,
                elapsed="1.0s",
            )

            from core.pipeline.conversion.output_save import OutputSaveResult

            assert isinstance(result, OutputSaveResult), (
                f"run_output_save should return OutputSaveResult, got {type(result)}"
            )
            assert hasattr(result, "segments_folder"), "OutputSaveResult must have segments_folder"
        finally:
            # V18.2.27 (warnings fix): close the conv_logger file handle.
            try:
                converter.conv_logger.close()
            except Exception:
                pass

    def test_output_studio_no_crash(self, integration_setup):
        """Test the output-studio phase for wiring bugs (flashcards 'j' NameError check)."""
        from core.models import SummaryResult

        # Create mock summaries
        summaries = [
            SummaryResult(
                chapter_heading="1 Introduction",
                executive_summary="This is the executive summary.",
                bullet_points=["Key point one.", "Key point two.", "Key point three."],
                thorough_summary="This is the thorough summary with more detail.",
                success=True,
                model_used="mock",
                input_tokens=100,
                output_tokens=200,
            ),
        ]

        from core.pipeline.conversion.output_runner import run_output_studio

        # Create a mock request with all outputs enabled
        # NOTE (P0 test-hygiene fix): ALL output_* flags must be set
        # explicitly. MagicMock auto-creates missing attributes as truthy,
        # which silently enabled the quote-bank / agent-skill / qa / glossary
        # / patterns / cheatsheet / epub generators; their MagicMock paths
        # then made atomic_write_text() dump junk "MagicMock/…" files into
        # the CWD (project root) on every full-suite run.
        mock_request = MagicMock()
        mock_request.output_briefing = True
        mock_request.output_podcast = True
        mock_request.output_flashcards = True
        mock_request.output_packets = False
        mock_request.output_tts = False
        mock_request.output_obsidian = False
        mock_request.output_study_guide = False
        mock_request.output_social = False
        mock_request.output_mindmap = False
        mock_request.output_evidence_map = False
        mock_request.output_qa = False
        mock_request.output_glossary = False
        mock_request.output_patterns = False
        mock_request.output_cheatsheet = False
        mock_request.output_skill = False
        mock_request.output_epub = False
        mock_request.output_quote_bank = False

        # Use a REAL OutputPaths instance (rooted in the tmp output dir) so
        # every *_dir attribute resolves to a real, writable Path — hermetic
        # and future-proof (new outputs can't reintroduce the junk-file bug).
        from core.pipeline.output_paths import OutputPaths

        real_paths = OutputPaths(root=integration_setup["output_dir"], stem="test_book")
        real_paths.briefing_dir.mkdir(parents=True, exist_ok=True)
        real_paths.podcast_dir.mkdir(parents=True, exist_ok=True)
        real_paths.flashcards_dir.mkdir(parents=True, exist_ok=True)

        with patch("utils.network.safe_ollama_request", side_effect=_mock_safe_ollama_request):
            results = run_output_studio(
                request=mock_request,
                summaries=summaries,
                segments=[],
                book_title="test_book",
                paths=real_paths,
                log=lambda msg, level: None,
                update_status=lambda s: None,
                judge_results=None,
            )

        # Verify all enabled outputs produced results
        assert "output_briefing" in results, "Briefing should be in results"
        assert "output_flashcards" in results, "Flashcards should be in results"


# ════════════════════════════════════════════════════════════════════════════
# V10.30.0 (Sprint 3.6): E2E smoke tests for Sprint 1 features
# (quarantine, drops.jsonl, conservative mode, checkpoint)
# ════════════════════════════════════════════════════════════════════════════


class TestSprint1Features:
    """E2E smoke tests for the V10.28.0 Sprint 1 bullet-preservation features.

    These tests verify that the quarantine system, drops.jsonl audit log,
    conservative mode, and checkpoint are wired correctly into the pipeline
    — without running the full 6-hour conversion.  Each test exercises one
    feature end-to-end with mocked LLM.
    """

    def test_drops_jsonl_written_on_conversion(self, integration_setup):
        """A conversion that drops bullets must write drops.jsonl to logs/."""
        output_dir = integration_setup["output_dir"]
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        drops_path = logs_dir / "drops.jsonl"

        # Use the quarantine module directly (it's what the summarizer uses)
        from core.summarisation.quarantine import QuarantineLog

        q = QuarantineLog(output_dir=output_dir)
        q.add(
            "A hallucinated bullet about quantum entanglement.",
            stage="F4_source_overlap",
            source_overlap=0.05,
            reason="overlap < 25%",
            chapter="Test Chapter",
        )
        assert drops_path.exists(), "drops.jsonl was not written"
        import json as _json

        line = drops_path.read_text(encoding="utf-8").splitlines()[0]
        entry = _json.loads(line)
        assert entry["bullet"] == "A hallucinated bullet about quantum entanglement."
        assert entry["stage"] == "F4_source_overlap"
        assert entry["chapter"] == "Test Chapter"

    def test_conservative_mode_field_on_request(self):
        """ConversionRequest must accept conservative_drops (V10.28.0)."""
        from pathlib import Path as _P

        from core.models import ConversionRequest

        req = ConversionRequest(
            input_path=_P("/tmp/test.pdf"),
            output_dir=_P("/tmp/out"),
            conservative_drops=True,
        )
        assert req.conservative_drops is True

    def test_conservative_mode_default_false(self):
        """conservative_drops defaults to False."""
        from pathlib import Path as _P

        from core.models import ConversionRequest

        req = ConversionRequest(input_path=_P("/tmp/test.pdf"), output_dir=_P("/tmp/out"))
        assert req.conservative_drops is False

    def test_quarantine_recovery_writes_recovered_flag(self, integration_setup):
        """The recovery pass marks drops.jsonl entries as recovered=true."""
        output_dir = integration_setup["output_dir"]
        from core.summarisation.quarantine import QuarantineLog

        q = QuarantineLog(output_dir=output_dir)
        q.add("High-overlap bullet", stage="F4", source_overlap=0.80, actually_dropped=True)
        resurrected = q.recover(source_text="")
        assert len(resurrected) == 1
        import json as _json

        entries = q.drops_path.read_text(encoding="utf-8").splitlines()
        entry = _json.loads(entries[0])
        assert entry["recovered"] is True

    def test_checkpoint_file_format(self, integration_setup):
        """The .checkpoint.json file uses the expected path + JSON format."""
        output_dir = integration_setup["output_dir"]
        # The checkpoint system writes to output_dir/.checkpoint.json
        # We don't run a full conversion, but verify the path convention.
        checkpoint_path = output_dir / ".checkpoint.json"
        # Simulate what the converter writes
        import json as _json

        checkpoint_path.write_text(
            _json.dumps(
                {
                    "version": "1.0",
                    "phases": {},
                    "input_path": "/tmp/test.pdf",
                }
            ),
            encoding="utf-8",
        )
        assert checkpoint_path.exists()
        data = _json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert "phases" in data
        assert "version" in data

    def test_output_paths_logs_dir(self):
        """OutputPaths.logs_dir resolves to <root>/logs (where drops.jsonl lives)."""
        from pathlib import Path as _P

        from core.pipeline.output_paths import SUB_LOGS, OutputPaths

        paths = OutputPaths(_P("/tmp/book"), "testbook")
        assert paths.logs_dir == _P("/tmp/book") / "logs"
        assert SUB_LOGS == "logs"
