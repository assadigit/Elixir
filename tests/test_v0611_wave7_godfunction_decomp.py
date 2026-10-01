"""V0.6.11 (Wave 7 / B14) — god-function decomposition characterization tests.

B14-a ``run_summarization`` (CC 136, ~1,035 LOC): the paths the split will
extract that the existing suites leave untested (the charter: characterization
tests FIRST, verbatim extraction second). Every test here runs against the
CURRENT (pre-split) code and must stay green after the split — they pin the
phase contracts, not the body layout:

* the two early exits (generate_summaries off / cancel pre-set);
* the front-matter skip (reference/bibliography/dedication families) + the
  selected-chapters DISABLE of the skip (the V0.02 false-success RCA guard);
* the very-short-chapter warning (the V10.24.0 <200-token floor);
* the two max_workers caps (thermal profile cap; the V13.28.0 VRAM
  calculator 85% cap);
* the thermal pre-flight failure exit (V13.26-era safety gate);
* the V0.4.25 run-id unification + the V0.5.20 glossary handoff attrs;
* the book-summary provenance stamp + visible footer + run-stamped copy
  (V18.20.3.7 / V0.4.25) and the end-of-run per-chapter save firing;
* the finalize contracts: cancel-mid-run leaves the checkpoint PENDING
  (V18.20.2.0 SWOT A15), success marks it done, judge_results stash +
  the Layer-8 count log;
* the V18.20.3.0 incremental checkpoint-saver wiring (ENABLED log +
  on_chapter_done handed to summarize_chapters).

B14-b ``batch_gap_fill`` (CC 107): the V18.20.3.7 RC-B.1 no-yield
escalation (previously only SOURCE-pinned by test_v182037 — the behavioral
corridor was never driven), the punctuation-insensitive duplicate guard,
and the 2×-pool bullet cap.

Content-agnostic (Rule 1): every author name / year / heading below is a
TEST FIXTURE, not runtime code.

Run: pytest tests/test_v0611_wave7_godfunction_decomp.py -v
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.pipeline.conversion.summarization as summarization_mod  # noqa: E402
from core.models import ConversionResult, SummaryResult  # noqa: E402
from core.pipeline.conversion.summarization import (  # noqa: E402
    SummarizationResult,
    run_summarization,
)
from core.system.provenance import run_stamp_suffix  # noqa: E402

# ── the fake converter surface run_summarization touches ────────────────────


class _PhaseSettings:
    """The minimal ``settings.get(path, default)`` surface the phase needs."""

    def __init__(self, data: dict | None = None) -> None:
        self._d = data or {}

    def get(self, key, default=None):
        return self._d.get(key, default)


class _FakeCheckpoint:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def mark_done(self, phase, **kw):
        self.calls.append((phase, kw))


class _FakeConverter:
    """Every converter attribute run_summarization touches (the docstring's
    own inventory), on recordable fakes."""

    def __init__(self, root: Path, request, logs: list) -> None:
        self.request = request
        self.settings = _PhaseSettings({"summarisation.incremental_chapter_save": False})
        self.output_dir = root / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.paths = SimpleNamespace(
            book_summary=self.output_dir / "summaries" / "Book.summary.md",
            summaries_dir=self.output_dir / "summaries",
        )
        self.summary_md_path = self.output_dir / "Book.summary.md"
        self.checkpoint = _FakeCheckpoint()
        self.cancel_event = threading.Event()
        self.conv_logger = SimpleNamespace(_conversion_run_id="20260930-101010-abcdef01")
        self.toc_entries = []
        self._logs = logs
        self.error_results: list[str] = []
        self._judge_results = None
        self._thermal_safety = None
        self._sanitize_filename = lambda heading: heading.replace(" ", "_")
        self._filter_segment_content = lambda seg: seg.content
        self._update_status = lambda msg: None
        self._update_progress = lambda v: None

    def _log(self, msg, level="INFO"):
        self._logs.append((level, msg))

    def _summarisation_progress(self, *a, **k):
        pass

    def _build_error_result(self, msg):
        self.error_results.append(msg)
        return ConversionResult(success=False, error_msg=msg)


class _FakeSummarizer:
    """Records the constructor args + the chapter_dicts the phase builds."""

    instances: list[_FakeSummarizer] = []

    def __init__(self, request, log_callback=None, language=None, claim_extractor=None):
        self.request = request
        self.log = log_callback
        self.language = language
        self.claim_extractor = claim_extractor
        self._run_id = "zz-generated-run-id-zz"
        self.judge_results: list = []
        self.captured_chapter_dicts = None
        self.captured_done_callback = None
        _FakeSummarizer.instances.append(self)

    def summarize_chapters(
        self,
        chapter_dicts,
        progress_callback=None,
        cancel_event=None,
        thermal_pause_callback=None,
        chapter_done_callback=None,
    ):
        self.captured_chapter_dicts = chapter_dicts
        self.captured_done_callback = chapter_done_callback
        return [
            _mk_summary(
                heading=cd["heading"],
                run_id=self._run_id,
                app_version="0.6.10",
                run_started="2026-09-30T10:10:10",
            )
            for cd in chapter_dicts
        ]

    def build_book_summary(self, summaries, book_title, stats=None):
        if stats is not None:
            stats["bullets"] = sum(len(s.bullet_points or []) for s in summaries)
        return f"BOOK SUMMARY BODY for {book_title}"


def _mk_summary(heading: str = "Chapter One", **overrides) -> SummaryResult:
    kw = dict(
        chapter_heading=heading,
        executive_summary="EXE summary text.",
        thorough_summary="THOROUGH summary body.",
        bullet_points=["Point one", "Point two"],
        success=True,
    )
    kw.update(overrides)
    return SummaryResult(**kw)


def _mk_request(root: Path, **overrides) -> SimpleNamespace:
    kw = dict(
        generate_summaries=True,
        use_llm_ocr=False,
        primary_ocr_model=None,
        enable_content_filter=False,
        selected_chapters=[],
        max_workers=2,
        model_architecture="single_local",
        summarisation_model="",
        primary_model="",
        output_dir=str(root / "output"),
        generate_docx=False,
        fast_api_url="",
        fast_api_key="",
        fast_api_model="",
        fast_model="",
    )
    kw.update(overrides)
    return SimpleNamespace(**kw)


def _mk_segments(*pairs) -> list[SimpleNamespace]:
    return [SimpleNamespace(heading=h, content=c) for h, c in pairs]


def _gpu_profile(**overrides) -> SimpleNamespace:
    kw = dict(
        name="FakeGPU",
        warning_c=80,
        caution_c=90,
        critical_c=95,
        hotspot_delta_c=10,
        max_safe_workers=4,
        emergency_mode=False,
    )
    kw.update(overrides)
    return SimpleNamespace(**kw)


@pytest.fixture(autouse=True)
def _sandbox_default(monkeypatch):
    """Deterministic externals for every test in this file: no GPU (the
    profile detection returns the empty result), the LLM provider factory
    refuses (the documented degradation path — concept technique #5 skips),
    and the fake-Summarizer class is installed."""
    monkeypatch.setattr(
        "core.system.hardware_monitor.detect_gpu_profile_from_system",
        lambda: ("", None),
    )
    monkeypatch.setattr(
        "core.llm.llm_provider.create_provider",
        _raiser("no provider in unit tests"),
    )
    monkeypatch.setattr("core.pipeline.conversion.summarization.Summarizer", _FakeSummarizer)
    _FakeSummarizer.instances.clear()
    yield


def _raiser(msg: str):
    def _boom(*a, **k):
        raise RuntimeError(msg)

    return _boom


def _drive(conv, segments, book_title="The Test Book"):
    return run_summarization(
        conv,
        segments,
        segments_folder=conv.output_dir,
        detected_lang="en",
        book_title=book_title,
        elapsed_fn=lambda: "0:42",
    )


def _infos(logs) -> list[str]:
    return [m for (_, m) in logs]


# ── B14-a: the two early exits ──────────────────────────────────────────────


class TestEarlyExits:
    def test_generate_summaries_off_returns_empty_result_without_starting(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path, generate_summaries=False), logs)
        result = _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert isinstance(result, SummarizationResult)
        assert result.summaries == []
        assert _FakeSummarizer.instances == []  # the phase never started
        assert not any("Summary phase starting" in m for m in _infos(logs))

    def test_cancelled_before_start_returns_cancelled_error(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        conv.cancel_event.set()
        result = _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert isinstance(result, ConversionResult)
        assert result.success is False
        assert result.error_msg == "Cancelled by user"


# ── B14-a: the front-matter skip + its selected-chapters disable ────────────


class TestFrontMatterSkip:
    def test_reference_families_skipped_from_summarization(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        segments = _mk_segments(
            ("References", "ref " * 300),
            ("Bibliography", "bib " * 300),
            ("Dedication", "ded " * 300),
            ("Chapter One", "word " * 300),
        )
        result = _drive(conv, segments)
        assert isinstance(result, SummarizationResult)
        assert [s.chapter_heading for s in result.summaries] == ["Chapter One"]
        inst = _FakeSummarizer.instances[0]
        assert [cd["heading"] for cd in inst.captured_chapter_dicts] == ["Chapter One"]
        msgs = _infos(logs)
        assert any("Skipping 'References'" in m and "(references)" in m for m in msgs)
        assert any("Skipped 3 reference/supplementary section(s)" in m for m in msgs)

    def test_selected_chapters_disables_the_skip(self, tmp_path):
        """The V0.02 false-success RCA contract: a deliberately selected
        Preface is ALWAYS summarized — never 'non-content'."""
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path, selected_chapters=["Preface"]), logs)
        segments = _mk_segments(("Preface", "word " * 250))
        result = _drive(conv, segments)
        assert isinstance(result, SummarizationResult)
        assert [s.chapter_heading for s in result.summaries] == ["Preface"]
        msgs = _infos(logs)
        assert any("front-matter skip disabled" in m for m in msgs)
        assert not any("Skipping 'Preface'" in m for m in msgs)
        assert any("User selected: ['Preface']" in m for m in msgs)


# ── B14-a: the very-short-chapter warning ───────────────────────────────────


class TestShortChapterWarning:
    def test_sub200_token_chapter_warns_quality_may_be_poor(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        _drive(conv, _mk_segments(("Thin Chapter", "Tiny.")))
        assert any(
            "is very short" in m and "summary quality may be poor" in m for m in _infos(logs)
        )


# ── B14-a: the two max_workers caps ─────────────────────────────────────────


class TestWorkerCaps:
    def _patch_thermal(self, monkeypatch, preflight=(True, "")):
        import core.system.thermal_safety as ts

        class _Ctrl:
            def __init__(self, log_callback=None, profile=None):
                self.profile = profile

            def preflight_check(self, nvidia_smi_path="", model_manager=None, model_name=""):
                return preflight

            def start(self):
                pass

            def wait_if_paused(self):
                pass

        monkeypatch.setattr(ts, "ThermalSafetyController", _Ctrl)
        monkeypatch.setattr(ts, "check_output_count_safety", lambda *a, **k: None)
        monkeypatch.setattr(ts, "recommend_thermal_safe_models", lambda *a, **k: None)

    def test_thermal_profile_caps_max_workers(self, tmp_path, monkeypatch):
        import core.system.hardware_monitor as hm

        monkeypatch.setattr(
            hm,
            "detect_gpu_profile_from_system",
            lambda: ("FakeGPU", _gpu_profile(max_safe_workers=2)),
        )
        monkeypatch.setattr("core.vram_calculator.get_total_vram", lambda: None)
        self._patch_thermal(monkeypatch)
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path, max_workers=4), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert conv.request.max_workers == 2
        assert any("max_workers capped 4 → 2" in m for m in _infos(logs))

    def test_vram_calculator_85pct_cap_sets_single_worker(self, tmp_path, monkeypatch):
        import core.system.hardware_monitor as hm

        monkeypatch.setattr(
            hm,
            "detect_gpu_profile_from_system",
            lambda: ("FakeGPU", _gpu_profile(max_safe_workers=8)),
        )
        monkeypatch.setattr("core.vram_calculator.get_total_vram", lambda: 24.0)
        monkeypatch.setattr(
            "core.vram_calculator.calculate_vram_budget",
            lambda **k: ((), 22.0, 24.0, None),  # peak 22 / 24 GB = 92% > 85%
        )
        self._patch_thermal(monkeypatch)
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path, max_workers=2), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert conv.request.max_workers == 1
        assert any("VRAM calculator: max_workers capped 2 → 1" in m for m in _infos(logs))
        # the started controller is STASHED on the converter (the V0.6.11
        # AST-identity pass caught a silent AttributeError on this exact
        # line — pinned so it can never regress silently again)
        assert conv._thermal_safety is not None
        assert conv._thermal_safety.profile.name == "FakeGPU"

    def test_vram_calculator_ok_keeps_workers(self, tmp_path, monkeypatch):
        import core.system.hardware_monitor as hm

        monkeypatch.setattr(
            hm,
            "detect_gpu_profile_from_system",
            lambda: ("FakeGPU", _gpu_profile(max_safe_workers=8)),
        )
        monkeypatch.setattr("core.vram_calculator.get_total_vram", lambda: 24.0)
        monkeypatch.setattr(
            "core.vram_calculator.calculate_vram_budget",
            lambda **k: ((), 12.0, 24.0, None),  # 50% — OK
        )
        self._patch_thermal(monkeypatch)
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path, max_workers=2), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert conv.request.max_workers == 2
        assert any("VRAM calculator: peak 12.0 GB" in m for m in _infos(logs))


# ── B14-a: the thermal pre-flight failure exit ─────────────────────────────


class TestThermalPreflight:
    def test_preflight_failure_aborts_with_error_result(self, tmp_path, monkeypatch):
        import core.system.hardware_monitor as hm
        import core.system.thermal_safety as ts

        monkeypatch.setattr(
            hm,
            "detect_gpu_profile_from_system",
            lambda: ("FakeGPU", _gpu_profile()),
        )
        monkeypatch.setattr("core.vram_calculator.get_total_vram", lambda: None)

        class _Ctrl:
            def __init__(self, log_callback=None, profile=None):
                pass

            def preflight_check(self, nvidia_smi_path="", model_manager=None, model_name=""):
                return (False, "GPU too hot: 96°C (critical 95°C) — aborting.")

            def start(self):
                raise AssertionError("start() must not run after a failed pre-flight")

        monkeypatch.setattr(ts, "ThermalSafetyController", _Ctrl)
        monkeypatch.setattr(ts, "check_output_count_safety", lambda *a, **k: None)
        monkeypatch.setattr(ts, "recommend_thermal_safe_models", lambda *a, **k: None)
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        result = _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert isinstance(result, ConversionResult)
        assert result.success is False
        assert "GPU too hot" in result.error_msg
        assert conv.error_results == [result.error_msg]
        assert any("Pre-flight thermal check FAILED" in m for m in _infos(logs))


# ── B14-a: run-id unification + the glossary handoff attrs ─────────────────


class TestRunIdUnification:
    def test_summarizer_run_id_unified_with_conversion_run_id(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        inst = _FakeSummarizer.instances[0]
        assert inst._run_id == "20260930-101010-abcdef01"

    def test_glossary_handoff_threads_run_id_and_output_dir(self, tmp_path):
        """The V0.5.20 rig-run-2 fix: request._run_id + request._run_output_dir
        so the deep stack persists the glossary INSIDE the run's folder."""
        logs: list = []
        req = _mk_request(tmp_path)
        conv = _FakeConverter(tmp_path, req, logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert req._run_id == "20260930-101010-abcdef01"
        assert req._run_output_dir == str(conv.output_dir)


# ── B14-a: the book-summary stamp + the end-of-run save ────────────────────


class TestBookSummaryOutput:
    def test_book_summary_stamped_footered_and_run_stamped_copy(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        result = _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert isinstance(result, SummarizationResult)
        body = conv.summary_md_path.read_text(encoding="utf-8")
        assert "BOOK SUMMARY BODY for The Test Book" in body
        assert "20260930-101010-abcdef01" in body  # the unified run id
        stamp = run_stamp_suffix("0.6.10", "20260930-101010-abcdef01")
        stamped = conv.summary_md_path.with_name(conv.summary_md_path.stem + stamp + ".summary.md")
        assert stamped.exists()
        assert stamped.read_text(encoding="utf-8") == body

    def test_per_chapter_save_fired_with_unified_ids(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        stamp = run_stamp_suffix("0.6.10", "20260930-101010-abcdef01")
        sf = conv.output_dir / "summaries" / f"001_Chapter_One{stamp}_summary.md"
        assert sf.exists()
        content = sf.read_text(encoding="utf-8")
        assert "EXE summary text." in content
        assert "<!-- COMPLETE" in content


# ── B14-a: the finalize contracts ───────────────────────────────────────────


class TestFinalizeContracts:
    def test_success_marks_summarization_checkpoint_done(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert conv.checkpoint.calls == [("summarization", {"chapters": 1})]

    def test_cancel_mid_run_leaves_checkpoint_pending(self, tmp_path):
        """V18.20.2.0 (SWOT A15): a cancelled run must NOT mark the phase
        checkpoint-done on PARTIAL state — resume re-enters the phase."""
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)

        class _CancelAndReturn(_FakeSummarizer):
            def summarize_chapters(self, *a, **k):
                conv.cancel_event.set()
                return []

        with mock.patch.object(summarization_mod, "Summarizer", _CancelAndReturn):
            result = _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert isinstance(result, SummarizationResult)
        assert conv.checkpoint.calls == []  # NOT marked done
        assert any("Cancelled — summarization checkpoint left pending" in m for m in _infos(logs))

    def test_judge_results_stashed_with_layer8_count(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)

        class _Seeded(_FakeSummarizer):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.judge_results = [
                    SimpleNamespace(grounding_layer8_available=True),
                    SimpleNamespace(grounding_layer8_available=False),
                ]

        with mock.patch.object(summarization_mod, "Summarizer", _Seeded):
            _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert len(conv._judge_results) == 2
        assert any("Layer 8 grounding ran for 1/2" in m for m in _infos(logs))

    def test_empty_judge_results_stash_no_layer8_log(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        assert conv._judge_results == []
        assert not any("Layer 8 grounding ran for" in m for m in _infos(logs))


# ── B14-a: the incremental checkpoint-saver wiring ─────────────────────────


class TestCheckpointSaverWiring:
    def test_saver_enabled_and_on_chapter_done_wired(self, tmp_path):
        logs: list = []
        conv = _FakeConverter(tmp_path, _mk_request(tmp_path), logs)
        conv.settings._d["summarisation.incremental_chapter_save"] = True
        _drive(conv, _mk_segments(("Chapter One", "word " * 300)))
        msgs = _infos(logs)
        assert any("incremental chapter checkpointing ENABLED" in m for m in msgs)
        inst = _FakeSummarizer.instances[0]
        assert callable(inst.captured_done_callback)
        # the wired callback is the real saver's on_chapter_done
        assert type(inst.captured_done_callback).__name__ == "method"
        assert inst.captured_done_callback.__self__.__class__.__name__ == "ChapterCheckpointSaver"


# ── B14-a structural pins (the V0.6.11 decomposition shape) ─────────────────


class TestB14aStructure:
    """V0.6.11 (B14-a): the run_summarization god-function decomposition —
    the phase structure + the CC ceiling. The behavioral contract is pinned
    by the classes above + the pre-existing suites (test_conversion_modules,
    test_v067/test_v068 review-loop fixes, test_v1820412_b_semantics)."""

    def test_ctx_dataclass_holds_the_phase_state(self):
        import dataclasses

        from core.pipeline.conversion import summarization as sm

        fields = {f.name for f in dataclasses.fields(sm._SummCtx)}
        expected = {
            # the 6 public parameters (same order as the signature)
            "converter",
            "segments",
            "segments_folder",
            "detected_lang",
            "book_title",
            "elapsed_fn",
            # the converter surface
            "log",
            "update_status",
            "update_progress",
            "request",
            # the derived per-phase state
            "summary_lang",
            "segments_for_summary",
            "claim_extractor",
            "gpu_name",
            "gpu_profile",
            "thermal_safety",
            "summarizer",
            "chapter_dicts",
            "loaded_summaries",
            "summaries",
        }
        assert expected <= fields

    def test_phase_helpers_exist_and_orchestrator_keeps_order(self):
        import inspect

        from core.pipeline.conversion import summarization as sm

        helpers = [
            "_rs_unload_ocr_vram",
            "_rs_apply_content_filter",
            "_rs_filter_reference_sections",
            "_rs_build_claim_extractor",
            "_rs_detect_gpu_profile",
            "_rs_start_thermal_safety",
            "_rs_init_summarizer",
            "_rs_thread_glossary_handoff",
            "_rs_make_concept_llm_fn",
            "_rs_build_chapter_dicts",
            "_rs_split_resume",
            "_rs_summarize_chapters",
            "_rs_merge_loaded_summaries",
            "_rs_write_book_summary",
            "_rs_finalize",
        ]
        for name in helpers:
            assert callable(getattr(sm, name, None)), f"missing {name}"
        src = inspect.getsource(sm.run_summarization)
        order = [src.index(f"{name}(ctx)") for name in helpers if name != "_rs_make_concept_llm_fn"]
        assert order == sorted(order), "phase call order must match the original flow"
        # the thermal pre-flight early exit still returns BEFORE the rest
        assert src.index("if _error is not None:") < src.index("_rs_init_summarizer(ctx)")
        # the concept-LLM factory is invoked from _rs_build_chapter_dicts
        bcd = inspect.getsource(sm._rs_build_chapter_dicts)
        assert "_rs_make_concept_llm_fn(ctx)" in bcd
        # the save block is still the module-level V0.6.7 helper
        assert "_save_chapter_summaries_write_once(converter, segments, ctx.summaries, log)" in src
        # the final return still carries the merged summaries
        assert "return SummarizationResult(summaries=ctx.summaries)" in src

    def test_cc_ceiling_orchestrator_thin_and_no_f_grade(self):
        """radon CC: run_summarization must be a thin coordinator (≤ 15) and
        no function in the module may regress to F (≥ 41)."""
        import ast as ast_mod
        import inspect

        from radon.visitors import ComplexityVisitor

        from core.pipeline.conversion import summarization as sm

        src = inspect.getsource(sm)
        tree = ast_mod.parse(src)
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        blocks = visitor.blocks
        assert blocks
        worst = max(b.complexity for b in blocks)
        assert worst < 41, f"no F-grade function allowed (worst={worst})"
        orch = next(b for b in blocks if b.name == "run_summarization")
        assert orch.complexity <= 15, (
            f"orchestrator must stay a thin coordinator (CC={orch.complexity})"
        )


# ── B14-b: batch_gap_fill — the previously-untested paths ───────────────────


class _GapLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((msg, level))


def _gap_deps(response_fn=None):
    """Hermetic deps in the test_gap_fill_batch.py house style."""
    log = _GapLog()
    llm_calls = []

    def check_coverage(analysis, text):
        text = text or ""
        covered = [a for a in analysis["authors"] if a in text]
        missing = [a for a in analysis["authors"] if a not in text]
        return {
            "covered": covered,
            "missing": missing,
            "total": len(analysis["authors"]),
            "coverage_pct": (len(covered) / len(analysis["authors"]))
            if analysis["authors"]
            else 0.0,
        }

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
        i = len(llm_calls)
        llm_calls.append(prompt)
        if response_fn is not None:
            return response_fn(prompt, i)
        return None

    return {
        "log": log,
        "check_coverage": check_coverage,
        "call_fast_llm": call_fast_llm,
        "strip_thinking": lambda t: t,
        "filter_thinking_bullets": lambda b, concepts=None, source_text="": list(b),
        "llm_calls": llm_calls,
    }


def _gap_run(deps, content, bullets, missing, analysis, det_authors):
    from core.summarisation.gap_fill_batch import batch_gap_fill

    return batch_gap_fill(
        "Chapter 1 — Identity",
        content,
        bullets,
        missing,
        analysis,
        det_authors,
        check_coverage=deps["check_coverage"],
        call_fast_llm=deps["call_fast_llm"],
        temperature=0.2,
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=deps["filter_thinking_bullets"],
        log=deps["log"],
    )


class TestNoYieldEscalation:
    """V18.20.3.7 (RC-B.1): an author with NO bullet for 2 CONSECUTIVE
    zero-yield rounds switches to the mention-only prompt — the escalation
    test_v182037 only source-pins; the behavioral corridor was never driven
    (empty responses never trip the veto counter, so RC-4 alone cannot
    escalate)."""

    def test_two_zero_yield_rounds_escalate_to_mention_only(self):
        deps = _gap_deps(response_fn=lambda prompt, i: "")  # always empty
        bullets: list[str] = []
        analysis = {"authors": ["Voss", "Ibarra"]}
        content = "Voss (1957) framed the model. Ibarra (1959) extended it."
        out = _gap_run(deps, content, bullets, ["Voss", "Ibarra"], analysis, ["Voss", "Ibarra"])
        assert out.total_added == 0
        # the full RC-B.1 → RC-4 chain: rounds 1-2 empty (no-yield counts hit
        # 2) → round 3 mention-only → still missing → BOTH given up → round 4
        # breaks on the empty actionable pool
        assert out.rounds == 4
        assert out.given_up == {"Voss", "Ibarra"}
        assert sorted(out.still_missing) == ["Ibarra", "Voss"]
        infos = [m for m, lvl in deps["log"].calls]
        assert any("'Voss' yielded no bullet for 2 consecutive rounds" in m for m in infos)
        assert any("'Ibarra' yielded no bullet for 2 consecutive rounds" in m for m in infos)
        assert any("No actionable authors left" in m for m in infos)
        assert any("Giving up on 'Voss'" in m for m in infos)
        assert any("Giving up on 'Ibarra'" in m for m in infos)
        # exactly 3 prompts sent; round 3's carries the mention-only block
        assert len(deps["llm_calls"]) == 3
        assert "MENTION-ONLY authors: Voss, Ibarra." in deps["llm_calls"][2]
        # rounds 1-2 did NOT carry it
        assert "MENTION-ONLY" not in deps["llm_calls"][0]
        assert "MENTION-ONLY" not in deps["llm_calls"][1]


class TestDuplicateGuard:
    def test_punctuation_and_case_insensitive_duplicate_dropped(self):
        """The dup guard normalizes BOTH sides (strip non-word chars, lower,
        first 60) — a response bullet differing only in punctuation/case from
        an existing bullet is dropped, not re-added."""
        deps = _gap_deps(
            response_fn=lambda prompt, i: (
                "- VOSS 1957 framed the two factor model of market dynamics"
            )
        )
        bullets = ["Voss (1957) framed the two-factor model of market dynamics."]
        analysis = {"authors": ["Voss"]}
        content = "Voss (1957) framed the model."
        out = _gap_run(deps, content, bullets, ["Voss"], analysis, ["Voss"])
        assert out.total_added == 0
        assert len(bullets) == 1  # the punctuation variant was NOT appended


class TestResponseBulletCap:
    def test_response_considered_at_most_two_bullets_per_author(self):
        """``_max_gap_bullets = len(_batch_authors) * 2`` — with 2 authors in
        the pool, only the FIRST 4 response lines are ever evaluated; a valid
        5th bullet beyond the cap is never appended."""
        response = "\n".join(
            [
                "- First filler bullet about testing alpha",
                "- Second filler bullet about testing beta",
                "- Third filler bullet about testing gamma",
                "- Fourth filler bullet about testing delta",
                "- Fifth filler bullet about testing epsilon",
            ]
        )
        deps = _gap_deps(response_fn=lambda prompt, i: response)
        bullets: list[str] = []
        analysis = {"authors": ["Voss", "Ibarra"]}
        content = "Voss (1957) framed the model. Ibarra (1959) extended it."
        out = _gap_run(deps, content, bullets, ["Voss", "Ibarra"], analysis, ["Voss", "Ibarra"])
        assert out.total_added == 4  # the cap: 2 authors × 2, not 5
        assert len(bullets) == 4
        assert not any("epsilon" in b for b in bullets)  # the 5th never landed


class TestB14bStructure:
    """V0.6.11 (B14-b): the batch_gap_fill god-function decomposition —
    the phase structure + the CC ceiling. The behavioral contract is pinned
    by the classes above + the pre-existing suites (test_gap_fill_batch,
    test_v182032/34/35/37/38/39, test_v05xx)."""

    def test_ctx_dataclass_holds_the_14_params_and_loop_state(self):
        import dataclasses

        from core.summarisation import gap_fill_batch as gfb

        fields = {f.name for f in dataclasses.fields(gfb._GapFillCtx)}
        expected = {
            # the 14 public parameters (same order as the signature)
            "heading",
            "content",
            "bullets",
            "missing",
            "analysis",
            "det_authors",
            "check_coverage",
            "call_fast_llm",
            "temperature",
            "strip_thinking",
            "filter_thinking_bullets",
            "log",
            "source_glossary",
            "regex_confirmed_authors",
            # the loop state (names match the original locals)
            "_sentences",
            "_gap_fill_round",
            "_still_missing",
            "_total_added",
            "_veto_counts",
            "_mention_attempted",
            "_given_up",
            "_no_yield_counts",
            "_batch_authors",
            "_mention_only",
            "_batch_context",
            "_final_check_added",
            "_final_check_rounds",
        }
        assert expected <= fields

    def test_phase_helpers_exist_and_orchestrator_keeps_order(self):
        import inspect

        from core.summarisation import gap_fill_batch as gfb

        helpers = [
            "_gff_prepare",
            "_gff_round_pool",
            "_gff_round_context",
            "_gff_round_execute",
            "_gff_post_round_accounting",
            "_gff_final_check",
            "_gff_report_still_missing",
        ]
        for name in helpers:
            assert callable(getattr(gfb, name, None)), f"missing {name}"
        src = inspect.getsource(gfb.batch_gap_fill)
        order = [src.index(f"{name}(ctx)") for name in helpers]
        assert order == sorted(order), "phase call order must match the original flow"
        # the loop + the two break plumbings stay in the orchestrator
        assert "while ctx._still_missing and ctx._gap_fill_round < 5:" in src
        assert "if not _gff_round_pool(ctx):" in src
        assert "if not _gff_round_execute(ctx):" in src
        # the no-op guard + the outcome contract are unchanged
        assert "if not missing:" in src
        assert "return GapFillOutcome(" in src

    def test_cc_ceiling_orchestrator_thin_and_no_f_grade(self):
        """radon CC: batch_gap_fill must be a thin coordinator (≤ 15) and no
        function in the module may reach F (≥ 41) — the worst verbatim units
        are the E(36) round-execute and final-check blocks (the B12 E(31)
        verbatim-loop precedent)."""
        import ast as ast_mod
        import inspect

        from radon.visitors import ComplexityVisitor

        from core.summarisation import gap_fill_batch as gfb

        src = inspect.getsource(gfb)
        tree = ast_mod.parse(src)
        visitor = ComplexityVisitor()
        visitor.visit(tree)
        blocks = visitor.blocks
        assert blocks
        worst = max(b.complexity for b in blocks)
        assert worst < 41, f"no F-grade function allowed (worst={worst})"
        orch = next(b for b in blocks if b.name == "batch_gap_fill")
        assert orch.complexity <= 15, (
            f"orchestrator must stay a thin coordinator (CC={orch.complexity})"
        )
