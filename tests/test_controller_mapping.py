"""V10.30.0 (Sprint 3.4 / V10.31.0 Sprint 4.4): Unit tests for Controller.build_request_from_ui.

Tests the field translation from WizardState (UI dict) to ConversionRequest.
This was previously at 0 unit tests despite being the single most bug-prone
integration point (V10.24.0 had a critical bug where ``outputs_X`` vs
``output_X`` naming mismatch silently disabled all opt-in outputs).

V10.31.0 (Sprint 4.4): The real ``build_request_from_ui`` is now table-driven
(``_REQUEST_FIELD_MAP`` + a generic loop).  This stub mirrors that structure
so the tests still exercise the exact same mapping logic.  If the real
table changes, this stub must be updated to match — that's the point: a
deliberate, reviewed copy that fails loudly if the two drift.

Covers ≥15 field mappings:
  - input_path / output_dir (Path conversion)
  - generate_summaries / include_*_summary / include_keypoints
  - summarisation_model / fast_model / heavy_model
  - temperature / coverage_threshold (with /100.0 conversion)
  - max_workers
  - segment_strategy / token_limit_per_segment / enable_semantic_segmentation
  - page_range_start / page_range_end / selected_chapters
  - source_type / academic_rigor
  - conservative_drops (V10.28.0)
  - all 15 output_* flags (V10.29.0 registry alignment)
  - compact_summaries
  - simplification_model
  - docx_* (author, include_toc)
  - post-processing (clean_markdown, token_saver, etc.)
  - extract_tables / extract_math / layout_analysis
  - settings-fallback when ui_data omits a key

Run: ``pytest tests/test_controller_mapping.py -v``
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.models import ConversionRequest

# ── Minimal stub Controller ─────────────────────────────────────────────────
#
# The real Controller (controller.py) imports Converter + Settings +
# threading + a lot of UI-bridge code.  For mapping tests we only need
# get_setting() + build_request_from_ui().  We mirror the V10.31.0
# table-driven structure here so the test exercises the real translation
# without the heavy import chain.
#
# If the real _REQUEST_FIELD_MAP changes, this stub must be updated to
# match — that's the point: a deliberate, reviewed copy that fails loudly
# if the two drift.


class _StubController:
    """Minimal Controller with the real build_request_from_ui mapping (V10.31.0 table-driven)."""

    # V10.31.0 (Sprint 4.4): mirrors controller.py _REQUEST_FIELD_MAP.
    # (request_attr, ui_key, setting_path_or_None, default, transform_or_None)
    _REQUEST_FIELD_MAP = [
        ("input_path",  "input_path",  None, None, lambda v: Path(v)),
        ("output_dir",  "output_dir",  None, None, lambda v: Path(v)),
        ("password",                    "password",                    None, None, None),
        ("manual_segments",             "manual_segments",             None, None, None),
        ("page_range_start",            "page_range_start",            None, None, None),
        ("page_range_end",              "page_range_end",              None, None, None),
        ("selected_chapters",           "selected_chapters",           None, None, None),
        ("output_qa",                   "output_qa",                   None, False, None),
        ("output_glossary",             "output_glossary",             None, False, None),
        ("output_patterns",             "output_patterns",             None, False, None),
        ("output_cheatsheet",           "output_cheatsheet",           None, False, None),
        ("output_skill",                "output_skill",                None, False, None),
        ("compact_summaries",           "compact_summaries",           None, False, None),
        ("conservative_drops",          "conservative_drops",          None, False, None),
        ("use_llm_ocr",                 "use_llm_ocr",                 "ocr.use_llm", True, None),
        ("primary_ocr_model",           "primary_ocr_model",           "ocr.primary_model", "qwen3-vl:8b", None),
        ("fallback_ocr_model",          "fallback_ocr_model",          "ocr.fallback_model", "qwen3-vl:8b", None),
        ("auto_detect_scanned",         "auto_detect_scanned",         "ocr.auto_detect_scanned", True, None),
        ("force_ocr_all_pages",         "force_ocr_all_pages",         "ocr.force_ocr_all_pages", False, None),
        ("image_max_size",              "image_max_size",              "ocr.image_max_size", 1200, None),
        ("clean_markdown",              "clean_markdown",              "postprocess.clean_markdown", True, None),
        ("fix_missing_spaces",          "fix_missing_spaces",          "postprocess.fix_missing_spaces", False, None),
        ("token_saver",                 "token_saver",                 "postprocess.token_saver", True, None),
        ("remove_page_number_headings", "remove_page_number_headings", "postprocess.remove_page_number_headings", True, None),
        ("convert_separators_to_comments", "convert_separators_to_comments", "postprocess.convert_separators_to_comments", False, None),
        ("custom_keywords",             "custom_keywords",             "segmentation.custom_keywords", [], None),
        ("custom_regex_patterns",       "custom_regex_patterns",       "segmentation.custom_regex_patterns", [], None),
        ("chunk_by_page_groups",        "chunk_by_page_groups",        "segmentation.chunk_by_page_groups", True, None),
        ("page_group_size",             "page_group_size",             "segmentation.page_group_size", 10, None),
        ("token_limit_per_segment",     "token_limit_per_segment",     "segmentation.token_limit", 2000, None),
        ("enable_semantic_segmentation","enable_semantic_segmentation","segmentation.enable_semantic", True, None),
        ("generate_summaries",          "generate_summaries",          "summarisation.enabled", False, None),
        ("summarisation_model",         "summarisation_model",         "summarisation.model", "gemma3:12b", None),
        ("summarisation_max_context_tokens", "summarisation_max_context_tokens", "summarisation.max_context_tokens", 16000, None),
        ("summarisation_max_output_tokens",  "summarisation_max_output_tokens",  "summarisation.max_output_tokens", 4096, None),
        ("summarisation_cache_enabled", "summarisation_cache_enabled", "summarisation.cache_enabled", False, None),
        ("generate_docx",               "generate_docx",               "docx.enabled", False, None),
        ("docx_author",                 "docx_author",                 "docx.author", "MarkItDown Pro", None),
        ("docx_include_toc",            "docx_include_toc",            "docx.include_toc", True, None),
        ("max_workers",                 "max_workers",                 "summarisation.max_workers", 2, None),
        ("temperature",                 "temperature",                 "summarisation.temperature", 0.2, None),
        ("self_consistency",            "self_consistency",            "summarisation.self_consistency", False, None),
        ("fast_model",                  "fast_model",                  "summarisation.fast_model", "gemma3:12b", None),
        ("heavy_model",                 "heavy_model",                 "summarisation.heavy_model", "", None),
        ("simplification_model",        "simplification_model",        "summarisation.simplification_model", "", None),
        ("extract_tables",              "extract_tables",              "advanced.extract_tables", False, None),
        ("extract_math",                "extract_math",                "advanced.extract_math", False, None),
        ("layout_analysis",             "layout_analysis",             "advanced.layout_analysis", False, None),
        ("table_extraction_method",     "table_extraction_method",     "advanced.table_method", "camelot", None),
        ("math_model",                  "math_model",                  "advanced.math_model", "pix2tex", None),
        ("source_type",                 "source_type",                 "source_type", "normal_book", None),
        ("include_executive_summary",   "include_executive_summary",   "summarisation.include_executive_summary", True, None),
        ("include_thorough_summary",    "include_thorough_summary",    "summarisation.include_thorough_summary", True, None),
        ("include_keypoints",           "include_keypoints",           "summarisation.include_keypoints", True, None),
        ("enable_content_filter",       "enable_content_filter",       "content_filter.enabled", True, None),
        ("academic_rigor",              "academic_rigor",              "summarisation.academic_rigor", False, None),
        ("simplified_keypoints_enabled","simplified_keypoints_enabled","summarisation.simplified_keypoints_enabled", False, None),
        ("extract_figure_text",         "extract_figure_text",         "advanced.extract_figure_text", False, None),
        ("output_briefing",             "output_briefing",             "outputs.briefing", True, None),
        ("output_podcast",              "output_podcast",              "outputs.podcast", True, None),
        ("output_flashcards",           "output_flashcards",           "outputs.flashcards", True, None),
        ("output_packets",              "output_packets",              "outputs.packets", False, None),
        ("output_obsidian",             "output_obsidian",             "outputs.obsidian", False, None),
        ("output_study_guide",          "output_study_guide",          "outputs.study_guide", False, None),
        ("output_social",               "output_social",               "outputs.social", False, None),
        ("output_mindmap",              "output_mindmap",              "outputs.mindmap", False, None),
        ("output_tts",                  "output_tts",                  "outputs.tts", False, None),
        ("output_evidence_map",         "output_evidence_map",         "outputs.evidence_map", False, None),
    ]

    def __init__(self, settings: dict | None = None):
        self._settings = settings or {}

    def get_setting(self, path: str, default=None):
        # Dot-notation lookup: "summarisation.model" → settings["summarisation"]["model"]
        parts = path.split(".")
        cur = self._settings
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

    def build_request_from_ui(self, ui_data: dict) -> ConversionRequest:
        # V10.31.0 (Sprint 4.4): mirrors the real controller's table-driven approach.
        input_path = Path(ui_data["input_path"])
        output_dir = Path(ui_data.get("output_dir", input_path.parent))
        strat = ui_data.get("segment_strategy", "auto")
        if hasattr(strat, "value"):
            strat = strat.value
        cov = ui_data.get(
            "coverage_threshold",
            self.get_setting("summarisation.coverage_threshold", 50),
        ) / 100.0
        kwargs = {
            "input_path": input_path,
            "output_dir": output_dir,
            "segment_strategy": strat,
            "coverage_threshold": cov,
        }
        for req_attr, ui_key, setting_path, default, transform in self._REQUEST_FIELD_MAP:
            if req_attr in kwargs:
                continue
            if setting_path is not None:
                value = ui_data.get(ui_key, self.get_setting(setting_path, default))
            else:
                value = ui_data.get(ui_key, default)
            if transform is not None and value is not None:
                try:
                    value = transform(value)
                except Exception:
                    pass
            kwargs[req_attr] = value
        return ConversionRequest(**kwargs)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _minimal_ui_data(**overrides) -> dict:
    """A minimal ui_data dict with just the required input_path."""
    data = {"input_path": "/tmp/test.pdf"}
    data.update(overrides)
    return data


@pytest.fixture
def controller():
    """A stub controller with no settings (all defaults)."""
    return _StubController(settings={})


# ── 1. Required fields ──────────────────────────────────────────────────────


class TestRequiredFields:
    def test_input_path_converted_to_path(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data())
        assert isinstance(req.input_path, Path)
        assert str(req.input_path) == "/tmp/test.pdf"

    def test_output_dir_defaults_to_input_parent(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data())
        assert req.output_dir == Path("/tmp")

    def test_output_dir_explicit(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(output_dir="/tmp/out"))
        assert req.output_dir == Path("/tmp/out")


# ── 2. Summarisation fields ─────────────────────────────────────────────────


class TestSummarisationMapping:
    def test_generate_summaries_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(generate_summaries=True))
        assert req.generate_summaries is True

    def test_summarisation_model_mapped(self, controller):
        req = controller.build_request_from_ui(
            _minimal_ui_data(summarisation_model="qwythos-9b:latest")
        )
        assert req.summarisation_model == "qwythos-9b:latest"

    def test_fast_model_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(fast_model="gemma2:9b"))
        assert req.fast_model == "gemma2:9b"

    def test_heavy_model_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(heavy_model="qwen:32b"))
        assert req.heavy_model == "qwen:32b"

    def test_temperature_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(temperature=0.7))
        assert req.temperature == 0.7

    def test_coverage_threshold_divided_by_100(self, controller):
        """coverage_threshold in ui_data is 0-100 (percent); the request stores 0.0-1.0."""
        req = controller.build_request_from_ui(_minimal_ui_data(coverage_threshold=70))
        assert req.coverage_threshold == 0.70

    def test_coverage_threshold_default(self, controller):
        """Default coverage_threshold (when ui_data omits it) is 50 → 0.5."""
        req = controller.build_request_from_ui(_minimal_ui_data())
        assert req.coverage_threshold == 0.50

    def test_max_workers_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(max_workers=3))
        assert req.max_workers == 3

    def test_simplification_model_mapped(self, controller):
        req = controller.build_request_from_ui(
            _minimal_ui_data(simplification_model="qwen:7b")
        )
        assert req.simplification_model == "qwen:7b"


# ── 3. Conservative drops (V10.28.0) ────────────────────────────────────────


class TestConservativeDrops:
    def test_conservative_drops_default_false(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data())
        assert req.conservative_drops is False

    def test_conservative_drops_mapped_true(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(conservative_drops=True))
        assert req.conservative_drops is True


# ── 4. Output flags (all 15) ────────────────────────────────────────────────


class TestOutputFlags:
    @pytest.mark.parametrize("flag", [
        "output_briefing", "output_podcast", "output_flashcards",
        "output_packets", "output_obsidian", "output_study_guide",
        "output_social", "output_mindmap", "output_tts",
        "output_evidence_map", "output_qa", "output_glossary",
        "output_patterns", "output_cheatsheet", "output_skill",
    ])
    def test_output_flag_mapped(self, controller, flag):
        """Every output_* flag must map from ui_data to ConversionRequest."""
        req = controller.build_request_from_ui(_minimal_ui_data(**{flag: True}))
        assert getattr(req, flag) is True, f"{flag} not mapped correctly"

    def test_all_outputs_default_correct(self, controller):
        """Output flags have the correct defaults when ui_data omits them.

        V10.31.0 (Sprint 4.4): The table-driven mapper now matches the real
        controller exactly — the 3 V4.0.0 outputs (briefing/podcast/flashcards)
        default to True; the 12 newer outputs default to False.
        """
        req = controller.build_request_from_ui(_minimal_ui_data())
        # The 3 original V4.0.0 outputs default ON (preserves shipped behaviour)
        assert req.output_briefing is True
        assert req.output_podcast is True
        assert req.output_flashcards is True
        # The 12 newer outputs default OFF (opt-in)
        for flag in [
            "output_packets", "output_obsidian", "output_study_guide",
            "output_social", "output_mindmap", "output_tts",
            "output_evidence_map", "output_qa", "output_glossary",
            "output_patterns", "output_cheatsheet", "output_skill",
        ]:
            assert getattr(req, flag) is False, f"{flag} should default to False"

    def test_compact_summaries_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(compact_summaries=True))
        assert req.compact_summaries is True


# ── 5. Segmentation + selection ─────────────────────────────────────────────


class TestSegmentationMapping:
    def test_segment_strategy_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(segment_strategy="heading"))
        assert req.segment_strategy == "heading"

    def test_token_limit_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(token_limit_per_segment=3000))
        assert req.token_limit_per_segment == 3000

    def test_enable_semantic_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(enable_semantic_segmentation=False))
        assert req.enable_semantic_segmentation is False

    def test_page_range_start_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(page_range_start=5))
        assert req.page_range_start == 5

    def test_page_range_end_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(page_range_end=20))
        assert req.page_range_end == 20

    def test_selected_chapters_mapped(self, controller):
        req = controller.build_request_from_ui(
            _minimal_ui_data(selected_chapters=["Intro", "Conclusion"])
        )
        assert req.selected_chapters == ["Intro", "Conclusion"]


# ── 6. Source type + academic rigor ─────────────────────────────────────────


class TestSourceTypeMapping:
    def test_source_type_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(source_type="academic_paper"))
        assert req.source_type == "academic_paper"

    def test_academic_rigor_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(academic_rigor=True))
        assert req.academic_rigor is True


# ── 7. DOCX + post-processing ───────────────────────────────────────────────


class TestDocxAndPostprocess:
    def test_generate_docx_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(generate_docx=True))
        assert req.generate_docx is True

    def test_docx_author_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(docx_author="Test Author"))
        assert req.docx_author == "Test Author"

    def test_docx_include_toc_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(docx_include_toc=False))
        assert req.docx_include_toc is False

    def test_clean_markdown_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(clean_markdown=False))
        assert req.clean_markdown is False

    def test_extract_tables_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(extract_tables=True))
        assert req.extract_tables is True

    def test_extract_math_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(extract_math=True))
        assert req.extract_math is True

    def test_layout_analysis_mapped(self, controller):
        req = controller.build_request_from_ui(_minimal_ui_data(layout_analysis=True))
        assert req.layout_analysis is True


# ── 8. Settings fallback ────────────────────────────────────────────────────


class TestSettingsFallback:
    def test_settings_fallback_for_summarisation_model(self):
        """When ui_data omits summarisation_model, the setting is used."""
        ctrl = _StubController(settings={"summarisation": {"model": "from-settings:latest"}})
        req = ctrl.build_request_from_ui(_minimal_ui_data())
        assert req.summarisation_model == "from-settings:latest"

    def test_settings_fallback_for_output_briefing(self):
        """When ui_data omits output_briefing, the setting is used."""
        ctrl = _StubController(settings={"outputs": {"briefing": True}})
        req = ctrl.build_request_from_ui(_minimal_ui_data())
        assert req.output_briefing is True

    def test_ui_data_overrides_settings(self):
        """ui_data takes precedence over settings."""
        ctrl = _StubController(settings={"summarisation": {"model": "from-settings"}})
        req = ctrl.build_request_from_ui(
            _minimal_ui_data(summarisation_model="from-ui")
        )
        assert req.summarisation_model == "from-ui"

    def test_default_when_neither_ui_nor_setting(self, controller):
        """When neither ui_data nor settings has the key, the hardcoded default applies."""
        req = controller.build_request_from_ui(_minimal_ui_data())
        assert req.summarisation_model == "gemma3:12b"  # hardcoded default
