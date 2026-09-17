"""V18.20.2.0 (SWOT A9-A12, A14, A15, A28, A30) — system/pipeline fixes.

Characterization tests for the IMPL-C batch (pipeline/system/controller):

  A9  — hardware_monitor: the sustained-load cool-down recommendation must
        actually emit (est_hotspot NameError killed it silently).
  A10 — hardware_monitor: pynvml.NVMLError from nvmlInit() reaches the
        intended handler (was an unreachable duplicate ``except ImportError``).
  A11 — hardware_monitor: _auto_pause_triggered re-arms after the GPU cools,
        so a SECOND overheat re-pauses.
  A12 — thermal_safety: CooldownScheduler always terminates a cool-down
        (unconditional end-conditions + per-event hard duration cap) and
        wait_if_paused honors an optional cancel_event.
  A14 — controller: a cancel clicked in the thread-start window survives
        (no redundant cancel_event.clear() in the worker).
  A15 — converter_impl/summarization: a cancel observed during the chapter
        loop skips every downstream phase (DOCX, keypoints, simplified
        keypoints, output studio, citation graph, quality report, footnotes,
        library), leaves skipped phases out of the checkpoint, and reports
        through the existing cancelled plumbing (success=False +
        "Cancelled by user").
  A28 — settings: no duplicate ``fast_model`` keys; effective default ("")
        unchanged.
  A30 — atomic writes at the five converter-flow sites; identical bytes,
        no .tmp leftovers.

Run: ``pytest tests/test_v18202_system_fixes.py -v -o addopts=""``
"""
from __future__ import annotations

import ast
import json
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like tests/test_conversion_modules.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager controller→pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = MagicMock(return_value=MagicMock())
    _tk.encoding_for_model = MagicMock(return_value=MagicMock())
    _tk.Encoding = MagicMock
    sys.modules["tiktoken"] = _tk


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_monitor(logs, pause_calls=None):
    """HardwareMonitor with a capturing log sink + optional pause spy."""
    from core.system.hardware_monitor import HardwareMonitor
    mon = HardwareMonitor(
        log_callback=lambda msg, level="INFO": logs.append((msg, level)),
        auto_pause_callback=(
            (lambda: pause_calls.append("pause")) if pause_calls is not None else None
        ),
    )
    return mon


def _zotac_profile():
    """The EMERGENCY Zotac profile (the target rig's card)."""
    from core.system.hardware_monitor import _PROFILE_ZOTAC_3060_TWIN_EDGE
    return _PROFILE_ZOTAC_3060_TWIN_EDGE


def _no_pynvml():
    """Context that guarantees 'import pynvml' fails (ImportError path)."""
    saved = sys.modules.pop("pynvml", None)
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["pynvml"] = saved


# ═══════════════════════════════════════════════════════════════════════════
# A9 — sustained-load recommendation must emit (est_hotspot NameError)
# ═══════════════════════════════════════════════════════════════════════════

class TestA9SustainedLoadWarning:
    """V18.20.2.0 (SWOT A9): _check_thresholds survives sustained load."""

    def _drive(self, logs, vram_temp=None):
        from core.system.hardware_monitor import HardwareSnapshot
        mon = _make_monitor(logs)
        mon._profile = _zotac_profile()  # sustained_pause_interval_min=20
        now = time.time()
        snap = HardwareSnapshot(
            timestamp=now,
            gpu_temp_c=60,                 # below warning → no tier spam
            gpu_vram_temp_c=vram_temp,
            gpu_utilization_pct=95,        # sustained load >80%
        )
        # 21 min of sustained load, no cool-down taken yet
        mon._sustained_load_start = now - 21 * 60
        mon._last_cooldown_time = None
        mon._check_thresholds(snap)  # pre-fix: NameError: est_hotspot

    def test_no_exception_and_warning_emitted(self):
        logs = []
        self._drive(logs)  # must not raise
        sustained = [m for m, lvl in logs if "Sustained load" in m]
        assert sustained, "the 20-min cool-down recommendation must be logged"
        assert any("Recommend a 5-min cool-down" in m for m in sustained)

    def test_hotspot_value_is_estimated_from_core_plus_delta(self):
        """Without a VRAM sensor the hotspot shows core + profile delta (60+18)."""
        logs = []
        self._drive(logs, vram_temp=None)
        sustained = [m for m, lvl in logs if "Sustained load" in m]
        assert sustained and "~78°C hotspot" in sustained[0], (
            "estimated hotspot = 60°C core + 18°C Zotac delta"
        )

    def test_hotspot_value_uses_real_vram_temp_when_available(self):
        """With temperature.memory available the real VRAM temp is shown."""
        logs = []
        self._drive(logs, vram_temp=90)
        sustained = [m for m, lvl in logs if "Sustained load" in m]
        assert sustained and "~90°C hotspot" in sustained[0], (
            "real VRAM temp (90°C) must be displayed, not a NameError"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A10 — duplicate except ImportError (dead NVMLError handler)
# ═══════════════════════════════════════════════════════════════════════════

class TestA10NVMLErrorHandling:
    """V18.20.2.0 (SWOT A10): nvmlInit failures reach the intended handler."""

    def _fake_pynvml(self, exc):
        class _NVMLError(Exception):
            pass

        mod = types.ModuleType("pynvml")
        mod.NVMLError = _NVMLError

        def _init():
            raise exc

        mod.nvmlInit = _init
        mod.nvmlDeviceGetHandleByIndex = lambda idx: MagicMock()
        return mod, _NVMLError

    def test_nvml_error_from_init_is_swallowed(self):
        """NVMLError (no NVIDIA driver) → falls back to nvidia-smi, no raise."""
        mod, err_cls = self._fake_pynvml(exc=None)
        def _raise():
            raise err_cls("Driver Not Loaded")
        mod.nvmlInit = _raise
        logs = []
        mon = _make_monitor(logs)
        with patch.dict(sys.modules, {"pynvml": mod}):
            available = mon._init_nvml()
        assert available is False
        assert mon._nvml_available is False
        # initialized latch: subsequent calls short-circuit to False
        assert mon._init_nvml() is False

    def test_other_error_from_init_is_swallowed_not_raised(self):
        """A non-NVMLError failure must also never crash the monitor."""
        mod, _ = self._fake_pynvml(exc=None)
        def _raise():
            raise RuntimeError("weird pynvml build")
        mod.nvmlInit = _raise
        mon = _make_monitor([])
        with patch.dict(sys.modules, {"pynvml": mod}):
            assert mon._init_nvml() is False

    def test_import_error_still_falls_back(self):
        """pynvml not installed → ImportError path unchanged (returns False)."""
        mon = _make_monitor([])
        saved = sys.modules.pop("pynvml", None)
        try:
            with patch.dict(sys.modules, {"pynvml": None}):
                # patch.dict with None value makes 'import pynvml' fail
                # with ImportError in CPython 3.3+? No — it raises ImportError
                # only when the loader can't find it; a None entry also fails.
                try:
                    assert mon._init_nvml() is False
                except ImportError:
                    pytest.fail("ImportError must be caught by _init_nvml")
        finally:
            if saved is not None:
                sys.modules["pynvml"] = saved
            else:
                sys.modules.pop("pynvml", None)

    def test_no_duplicate_except_import_error(self):
        """Source guard: _init_nvml has exactly one ``except ImportError``."""
        import re
        src = (_project_root / "core" / "system" / "hardware_monitor.py").read_text(
            encoding="utf-8"
        )
        start = src.index("def _init_nvml")
        end = src.index("def _query_gpu_nvml")
        body = src[start:end]
        clauses = re.findall(r"^\s*except ImportError", body, re.M)
        assert len(clauses) == 1, (
            "the duplicate (unreachable) ``except ImportError:`` clause "
            "must not come back — the second clause is the NVMLError handler"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A11 — _auto_pause_triggered must re-arm after cooldown
# ═══════════════════════════════════════════════════════════════════════════

class TestA11AutoPauseRelatch:
    """V18.20.2.0 (SWOT A11): a second overheat re-pauses."""

    def test_pause_cooldown_repause(self):
        from core.system.hardware_monitor import HardwareSnapshot
        pause_calls = []
        mon = _make_monitor([], pause_calls)
        mon._profile = _zotac_profile()  # critical 80°C

        now = time.time()
        hot = HardwareSnapshot(
            timestamp=now, gpu_temp_c=85, gpu_utilization_pct=50,
            gpu_vram_temp_c=None,
        )
        cool = HardwareSnapshot(
            timestamp=now, gpu_temp_c=60, gpu_utilization_pct=10,
            gpu_vram_temp_c=None,
        )

        # 1. First overheat → auto-pause fires
        mon._check_thresholds(hot)
        assert len(pause_calls) == 1
        assert mon._auto_pause_triggered is True

        # (still hot → anti-spam, no duplicate pause)
        mon._check_thresholds(hot)
        assert len(pause_calls) == 1

        # 2. Temp normalizes → latch resets (pre-fix: stayed True forever)
        mon._check_thresholds(cool)
        assert mon._auto_pause_triggered is False, (
            "the auto-pause latch must re-arm when the GPU cools below the "
            "warning threshold"
        )

        # 3. SECOND overheat → pauses again
        mon._check_thresholds(hot)
        assert len(pause_calls) == 2, (
            "a second overheat later in the same run must re-trigger the "
            "auto-pause"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A12 — CooldownScheduler cannot hang; wait_if_paused honors cancel_event
# ═══════════════════════════════════════════════════════════════════════════

class TestA12CooldownScheduler:
    """V18.20.2.0 (SWOT A12): cool-downs always terminate."""

    def _scheduler(self, logs):
        from core.system.thermal_safety import CooldownScheduler
        return CooldownScheduler(log_callback=lambda m, l="INFO": logs.append((m, l)))

    def test_first_cooldown_ends_at_hard_cap_under_sustained_load(self):
        """util>80% + temp>68°C + FIRST cool-down → still ends at the cap."""
        from core.system.thermal_safety import (
            COOLDOWN_DURATION_MIN,
            COOLDOWN_INTERVAL_MIN,
        )
        logs = []
        sched = self._scheduler(logs)
        t0 = 1_000_000.0

        # 20+ min of sustained load at >80% util with a hot temp
        sched.update(95, 75, t0)
        sched.update(95, 75, t0 + (COOLDOWN_INTERVAL_MIN + 1) * 60)
        assert sched.is_paused is True, "cool-down must trigger after 20 min load"

        # util STAYS >80% and temp STAYS >68°C — pre-fix this never ended
        start = t0 + (COOLDOWN_INTERVAL_MIN + 1) * 60
        sched.update(95, 75, start + 60)  # +1 min: still paused
        assert sched.is_paused is True
        sched.update(95, 75, start + 2 * 60)  # +2 min: still paused
        assert sched.is_paused is True
        # hard cap (COOLDOWN_DURATION_MIN from the cool-down's START)
        sched.update(95, 75, start + COOLDOWN_DURATION_MIN * 60 + 1)
        assert sched.is_paused is False, (
            "the first cool-down must end at its hard duration cap even when "
            "GPU util stays >80% and the temp never drops to the resume level"
        )
        assert any("Cool-down complete" in m for m, _ in logs)

    def test_cooldown_ends_early_when_temp_recovers(self):
        """Temp-based resume still works (ends before the hard cap)."""
        logs = []
        sched = self._scheduler(logs)
        t0 = 2_000_000.0
        sched.update(95, 75, t0)
        sched.update(95, 75, t0 + 21 * 60)
        assert sched.is_paused is True
        # util drops but stays >80%? No — temp-based end must work regardless
        # of util now; even under sustained load a cool GPU ends the pause.
        sched.update(95, 60, t0 + 21 * 60 + 30)
        assert sched.is_paused is False

    def test_cooldown_ends_at_hard_cap_even_with_none_util(self):
        """Even when the utilization sensor reports None, the end-condition
        check runs (truly unconditional — the old code returned early)."""
        from core.system.thermal_safety import COOLDOWN_DURATION_MIN
        logs = []
        sched = self._scheduler(logs)
        t0 = 3_000_000.0
        sched.update(95, 75, t0)
        sched.update(95, 75, t0 + 21 * 60)
        assert sched.is_paused is True
        start = sched._cooldown_started_at
        # util sensor unavailable for the whole cool-down, temp stays hot
        sched.update(None, 75, start + 60)
        assert sched.is_paused is True
        sched.update(None, 75, start + COOLDOWN_DURATION_MIN * 60 + 1)
        assert sched.is_paused is False, (
            "the hard cap must end the cool-down even when utilization "
            "readings are unavailable"
        )

    def test_budget_forced_cooldown_uses_30min_cap(self):
        """force_cooldown (thermal budget) caps at 30 min, not 3 min."""
        from core.system.thermal_safety import THERMAL_BUDGET_REACHED_COOLDOWN_MIN
        logs = []
        sched = self._scheduler(logs)
        sched.force_cooldown("thermal budget exceeded")
        assert sched.is_paused is True
        assert sched._cooldown_max_duration_sec == (
            THERMAL_BUDGET_REACHED_COOLDOWN_MIN * 60
        )
        # +3 min (the regular cap) does NOT end a budget cool-down…
        t0 = sched._cooldown_started_at
        sched.update(10, 75, t0 + 3 * 60 + 1)   # idle util, temp still hot
        assert sched.is_paused is True
        # …but +30 min does.
        sched.update(10, 75, t0 + THERMAL_BUDGET_REACHED_COOLDOWN_MIN * 60 + 1)
        assert sched.is_paused is False

    def test_wait_if_paused_exits_promptly_on_cancel(self):
        """wait_if_paused(cancel_event=…) breaks immediately when cancelled."""
        logs = []
        sched = self._scheduler(logs)
        sched._start_cooldown(time.time(), 75)
        assert sched.is_paused is True

        cancel = threading.Event()
        cancel.set()
        t0 = time.monotonic()
        sched.wait_if_paused(timeout_per_check=5.0, cancel_event=cancel)
        elapsed = time.monotonic() - t0
        assert elapsed < 1.0, (
            "a cancelled run must exit the cool-down wait promptly "
            f"(took {elapsed:.2f}s)"
        )
        assert any("interrupted by cancellation" in m for m, _ in logs)

    def test_controller_wait_if_paused_forwards_cancel_event(self):
        """ThermalSafetyController.wait_if_paused forwards the cancel_event."""
        from core.system.thermal_safety import ThermalSafetyController
        logs = []
        ts = ThermalSafetyController(log_callback=lambda m, l="INFO": logs.append((m, l)))
        ts.start()
        ts._scheduler._start_cooldown(time.time(), 75)
        assert ts.is_paused is True

        cancel = threading.Event()
        cancel.set()
        t0 = time.monotonic()
        ts.wait_if_paused(cancel_event=cancel)
        assert time.monotonic() - t0 < 1.0
        assert any("interrupted by cancellation" in m for m, _ in logs)

    def test_update_not_wired_into_production(self):
        """A12 wiring discipline: ThermalSafetyController.update() must have
        ZERO production call sites (deferred to real-rig golden-master run).
        """
        src = (_project_root / "core" / "system" / "thermal_safety.py").read_text(
            encoding="utf-8"
        )
        assert "READY TO WIRE" in src, (
            "the deliberate not-wired-yet note on update() must stay until "
            "golden-master validation on the real rig"
        )
        # hardware_monitor's poll loop must NOT call a thermal controller
        hw_src = (_project_root / "core" / "system" / "hardware_monitor.py").read_text(
            encoding="utf-8"
        )
        assert "thermal_safety" not in hw_src, (
            "A5-note: thermal_safety wiring into production callers is "
            "explicitly out of scope for this batch"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A14 — cancel clicked in the thread-start window survives
# ═══════════════════════════════════════════════════════════════════════════

class TestA14CancelRace:
    """V18.20.2.0 (SWOT A14): no redundant cancel_event.clear() in the worker."""

    def test_worker_observes_cancel_set_after_start_conversion(self):
        """Simulate: start_conversion spawns the thread, the user clicks
        Cancel in the thread-start window, THEN the worker body runs.
        The worker must observe the cancel (pre-fix: line 153 cleared it).
        """
        import controller as controller_mod
        from core.models import ConversionResult
        from tests.fixtures import make_minimal_request

        captured = {}

        class _SpyConverter:
            def __init__(self, request=None, progress_callback=None,
                         status_callback=None, log_callback=None,
                         cancel_event=None):
                captured["cancel_set_at_worker_start"] = bool(
                    cancel_event and cancel_event.is_set()
                )

            def convert(self):
                return ConversionResult(success=False, error_msg="Cancelled by user")

        ctrl = controller_mod.Controller()
        # Cancel clicked AFTER start_conversion() cleared the event under the
        # lock but BEFORE the worker body runs:
        ctrl.cancel_event.set()

        request = make_minimal_request(input_path="/tmp/x.pdf", output_dir="/tmp/out")
        with patch.object(controller_mod, "Converter", _SpyConverter):
            ctrl._run_conversion(request)

        assert captured.get("cancel_set_at_worker_start") is True, (
            "a cancel clicked in the thread-start window must survive into "
            "the worker (the redundant clear() used to erase it)"
        )

    def test_no_redundant_clear_in_worker(self):
        """Source guard: _run_conversion must not clear cancel_event."""
        import re
        src = (_project_root / "controller.py").read_text(encoding="utf-8")
        start = src.index("def _run_conversion")
        end = src.index("def start_conversion")
        body = src[start:end]
        code_clears = re.findall(r"^\s*self\.cancel_event\.clear\(\)", body, re.M)
        assert code_clears == [], (
            "the only cancel_event.clear() lives under the lock in "
            "start_conversion()"
        )
        # …and the clear under the lock is still there:
        start2 = src.index("def start_conversion")
        body2 = src[start2:]
        assert "self.cancel_event.clear()" in body2


# ═══════════════════════════════════════════════════════════════════════════
# A15 — cancel observed during the chapter loop skips downstream phases
# ═══════════════════════════════════════════════════════════════════════════

class _SettingsStub:
    """Minimal settings stub: everything default/off."""

    def get(self, path, default=None):
        if path == "outputs_optin.screenshots":
            return False
        return default


class _FakeCheckpoint:
    """Checkpoint spy — records mark_done calls; load() finds nothing."""

    mark_done_calls: list = []

    def __init__(self, book_name="", input_path=""):
        self.phases = {}
        self.book_name = book_name
        self._dir = None

    @classmethod
    def load(cls, output_dir):
        return None

    def set_output_dir(self, d):
        self._dir = Path(d)

    @property
    def checkpoint_path(self):
        return (self._dir or Path(".")) / ".checkpoint.json"

    def mark_done(self, phase, **metadata):
        _FakeCheckpoint.mark_done_calls.append(phase)

    def mark_failed(self, phase, error, **kw):
        pass

    def mark_skipped(self, phase):
        pass


class TestA15CancelSkipsDownstreamPhases:
    """V18.20.2.0 (SWOT A15): cancelled runs skip every post-summary phase."""

    @pytest.fixture()
    def pipeline_env(self, tmp_path):
        """Build a Converter + patch every delegate phase with spies."""
        from core.models import Segment, SummaryResult
        from core.pipeline.converter_impl import Converter
        from tests.fixtures import make_minimal_request

        _FakeCheckpoint.mark_done_calls = []

        pdf = tmp_path / "test_book.pdf"
        pdf.write_text("%PDF-1.4 fake")
        out = tmp_path / "output"

        request = make_minimal_request(
            input_path=str(pdf),
            output_dir=str(out),
            source_type="normal_book",
            generate_docx=True,
            simplified_keypoints_enabled=True,
            use_llm_ocr=False,
        )
        conv = Converter(
            request=request,
            progress_callback=lambda p: None,
            status_callback=lambda m: None,
            log_callback=lambda m, l="INFO": None,
            cancel_event=threading.Event(),
        )
        conv.settings = _SettingsStub()
        conv._log_conversion_settings = lambda: None
        # run_output_save is patched below, so materialize the artifacts it
        # would have written (citation graph reads the temp markdown).
        conv.temp_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        conv.temp_markdown_path.write_text("# Chapter 1\n\nbody", encoding="utf-8")

        summary = SummaryResult(
            chapter_heading="Chapter 1",
            executive_summary="Exec summary text.",
            thorough_summary="Thorough summary text.",
            bullet_points=["bullet one", "bullet two"],
            success=True,
            model_used="test-model",
            input_tokens=900,
            output_tokens=200,
        )
        segment = Segment(
            heading="Chapter 1", content="Chapter body text.",
            start_page=1, end_page=3, segment_type="chapter",
        )
        raw_md = "# Chapter 1\n\nChapter body text."

        extract_ns = SimpleNamespace(
            analysis=MagicMock(), pages_to_ocr=set(),
            effective_start_page=1, effective_end_page=3,
            effective_total_pages=3, toc_entries=[],
            valid_pages=None, raw_markdown=raw_md,
            # V18.20.3.6: ExtractionResult.selected_pages — mirrors the real
            # dataclass contract (None = no chapter/range selection).
            selected_pages=None,
        )
        seg_ns = SimpleNamespace(segments=[segment], page_markers=[], total_pages=3)
        save_ns = SimpleNamespace(
            book_title="Test Book", detected_lang="en",
            source_name="test_book.pdf", segments_folder=tmp_path / "segments",
        )
        summ_ns = SimpleNamespace(summaries=[summary])

        spies = {}
        with patch("core.system.preflight_check.run_preflight_check",
                   return_value="") as spies["preflight"], \
             patch("core.pipeline.checkpoint.Checkpoint", _FakeCheckpoint), \
             patch("core.pipeline.conversion.extraction.run_extraction",
                   return_value=extract_ns) as spies["extraction"], \
             patch("core.pipeline.conversion.postprocess.run_postprocess",
                   return_value=raw_md) as spies["postprocess"], \
             patch("core.pipeline.conversion.segmentation.run_segmentation",
                   return_value=seg_ns) as spies["segmentation"], \
             patch("core.pipeline.conversion.segmentation.log_segment_summary",
                   ) as spies["seg_log"], \
             patch("core.pipeline.conversion.output_save.run_output_save",
                   return_value=save_ns) as spies["output_save"], \
             patch("core.pipeline.conversion.summarization.run_summarization",
                   return_value=summ_ns) as spies["summarization"], \
             patch("core.pipeline.converter_impl.DocxBuilder") as spies["docx"], \
             patch("core.summarisation.KeypointsBuilder") as spies["keypoints"], \
             patch("core.summarisation.SimplifiedKeypointsBuilder") as spies["simplified"], \
             patch("core.pipeline.conversion.output_runner.run_output_studio",
                   return_value={}) as spies["studio"], \
             patch("core.outputs.citation_graph.generate_citation_graph",
                   ) as spies["citation"], \
             patch("core.pdf.footnote_extractor.extract_footnotes",
                   return_value={"total_notes": 0, "footnotes": [], "endnotes": []}
                   ) as spies["footnotes"], \
             patch("core.pipeline.library_manager.LibraryManager") as spies["library"]:
            # Configure spy return values so the NON-cancelled control run
            # flows through each phase the way the real builders do.
            spies["docx"].return_value.build_report.return_value = True
            spies["keypoints"].return_value.build.return_value = (
                tmp_path / "keypoints.md", tmp_path / "keypoints.docx"
            )
            spies["simplified"].return_value.build.return_value = (
                tmp_path / "simplified.md"
            )
            spies["quality_report"] = MagicMock()
            conv._generate_quality_report = spies["quality_report"]
            yield conv, spies

    def test_cancelled_run_skips_all_downstream_phases(self, pipeline_env):
        conv, spies = pipeline_env
        # Cancel observed during the chapter loop → the (patched) run_summarization
        # returns partial summaries with the cancel flag still set.
        conv.cancel_event.set()

        result = conv.convert()

        # Downstream phases NOT invoked
        assert spies["docx"].call_count == 0, "DOCX build must be skipped"
        assert spies["keypoints"].call_count == 0, "keypoints must be skipped"
        assert spies["simplified"].call_count == 0, "simplified keypoints must be skipped"
        assert spies["studio"].call_count == 0, "output studio must be skipped"
        assert spies["citation"].call_count == 0, "citation graph must be skipped"
        assert spies["quality_report"].call_count == 0, "quality report must be skipped"
        assert spies["footnotes"].call_count == 0, "footnote extraction must be skipped"
        assert spies["library"].call_count == 0, "library tracking must be skipped"

        # Checkpoint: nothing marked done for skipped phases
        marked = list(_FakeCheckpoint.mark_done_calls)
        for phase in ("docx", "keypoints", "simplified_keypoints",
                      "summarization", "briefing", "podcast_script", "flashcards"):
            assert phase not in marked, (
                f"cancelled run must not mark '{phase}' checkpoint-done "
                f"(marked: {marked})"
            )

        # Result: reported via the existing cancelled plumbing
        assert result.success is False
        assert result.error_msg == "Cancelled by user"

    def test_uncancelled_run_invokes_downstream_phases(self, pipeline_env):
        """Control: the same wiring WITH cancel runs every phase (proves the
        skip assertions above are meaningful — the gates don't always skip)."""
        conv, spies = pipeline_env

        result = conv.convert()

        assert spies["docx"].call_count == 1
        assert spies["keypoints"].call_count == 1
        assert spies["simplified"].call_count == 1
        assert spies["studio"].call_count == 1
        assert spies["citation"].call_count == 1
        assert spies["quality_report"].call_count == 1
        assert spies["library"].call_count == 1
        assert result.success is True
        assert result.error_msg is None

    def test_summarization_checkpoint_not_marked_done_when_cancelled(self):
        """run_summarization leaves the summarization phase PENDING on a
        cancelled run (AST guard on summarization.py)."""
        src = (_project_root / "core" / "pipeline" / "conversion" /
               "summarization.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        guard_found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test_src = ast.unparse(node.test)
            if "cancel_event.is_set()" not in test_src:
                continue
            # guard body logs the pending note; orelse marks done
            body_src = ast.unparse(node)
            if "summarization checkpoint left pending" in body_src:
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr == "mark_done"):
                        for arg in sub.args:
                            if (isinstance(arg, ast.Constant)
                                    and arg.value == "summarization"):
                                guard_found = True
        assert guard_found, (
            "the mark_done('summarization') call must sit in the else-branch "
            "of a cancel_event.is_set() guard"
        )

    def test_phase_gates_wired_in_converter_impl(self):
        """Source guard: every post-summary phase has a _cancel_requested gate."""
        src = (_project_root / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        gates = [
            "DOCX build", "keypoints build", "simplified keypoints",
            "output studio", "citation graph", "quality report",
            "footnote extraction", "library tracking", "screenshots/graphs",
        ]
        for gate in gates:
            assert f'_cancel_requested("{gate}")' in src, (
                f"phase gate '{gate}' missing from converter_impl.py"
            )
        # Final result mirrors the existing cancelled early-exit plumbing
        assert 'error_msg=("Cancelled by user" if _cancelled' in src
        assert "and not _cancelled" in src


# ═══════════════════════════════════════════════════════════════════════════
# A28 — settings.py duplicate fast_model keys removed
# ═══════════════════════════════════════════════════════════════════════════

class TestA28SettingsFastModel:
    """V18.20.2.0 (SWOT A28): exactly one fast_model key per location."""

    def test_no_duplicate_dict_keys_anywhere_in_settings(self):
        """AST guard: no dict literal in settings.py repeats a string key."""
        src = (_project_root / "utils" / "settings.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        dups = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                seen = set()
                for k in keys:
                    if k in seen:
                        dups.append((node.lineno, k))
                    seen.add(k)
        assert dups == [], f"duplicate dict keys remain: {dups}"

    def test_no_duplicate_keys_in_ensure_lists(self):
        """AST guard: the 'ensure default exists' tuple lists have no dup keys."""
        src = (_project_root / "utils" / "settings.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        dups = []
        for node in ast.walk(tree):
            if isinstance(node, ast.List):
                firsts = []
                for el in node.elts:
                    if (isinstance(el, ast.Tuple) and el.elts
                            and isinstance(el.elts[0], ast.Constant)):
                        firsts.append(el.elts[0].value)
                for v in set(firsts):
                    if firsts.count(v) > 1:
                        dups.append((node.lineno, v))
        assert dups == [], f"duplicate ensure-list entries remain: {dups}"

    def test_effective_fast_model_default_unchanged(self):
        """Behavioral: the effective default stays "" (the value that was
        silently winning by dict-literal semantics pre-dedupe)."""
        from utils.settings import Settings
        defaults = Settings._defaults()
        assert defaults["summarisation"]["fast_model"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# A30 — atomic writes across the converter flow
# ═══════════════════════════════════════════════════════════════════════════

def _tmp_artifacts(directory: Path):
    return [p for p in Path(directory).rglob("*") if p.suffix == ".tmp"]


class TestA30AtomicWrites:
    """V18.20.2.0 (SWOT A30): converter-flow writes are atomic."""

    def test_atomic_json_identical_bytes_and_no_tmp(self, tmp_path):
        """atomic_write_json serializes exactly like the old json.dump call."""
        from utils.atomic_io import atomic_write_json
        data = {"name": "کتاب Test", "nested": {"fast_model": "", "n": 1}}
        p = tmp_path / "sub" / "config.json"
        atomic_write_json(p, data, indent=2, ensure_ascii=False)
        expected = json.dumps(data, indent=2, ensure_ascii=False)
        assert p.read_text(encoding="utf-8") == expected
        assert _tmp_artifacts(tmp_path) == []

    def test_atomic_text_preserves_unicode_and_no_tmp(self, tmp_path):
        from utils.atomic_io import atomic_write_text
        content = "# Book summary\n\nخلاصه — test ✔\n"
        p = tmp_path / "deep" / "nested" / "Book.summary.md"
        atomic_write_text(p, content)
        assert p.read_text(encoding="utf-8") == content
        assert _tmp_artifacts(tmp_path) == []

    def test_controller_save_book_settings_atomic(self, tmp_path):
        """controller.save_book_settings writes .conversion_config.json
        atomically (the regeneration contract) with identical payload."""
        import controller as controller_mod
        from tests.fixtures import make_minimal_request

        ctrl = controller_mod.Controller.__new__(controller_mod.Controller)
        ctrl._safe_log = lambda msg, level="INFO": None
        request = make_minimal_request(
            input_path=str(tmp_path / "book.pdf"),
            output_dir=str(tmp_path / "out"),
        )
        ctrl.save_book_settings(tmp_path, request)

        cfg = tmp_path / ".conversion_config.json"
        assert cfg.exists()
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["input_path"].endswith("book.pdf")
        assert data["fast_model"] == request.fast_model
        assert _tmp_artifacts(tmp_path) == [], "no .tmp leftovers"

    def test_chapter_manifest_atomic_identical_payload(self, tmp_path):
        from core.obs.conversion_manifest import write_chapter_manifest
        p = write_chapter_manifest(
            output_dir=tmp_path, chapter_index=1, chapter_total=2,
            chapter_heading="1 - TEST", model="test:latest", num_ctx=26758,
            coverage=0.89, phases_ran=["primary"], leak_guard_fires=0,
            post_check_fixes=1, post_check_flags=0, duration_seconds=123.4,
            bullet_count=7, exec_summary_chars=500, hallucinations=0,
        )
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["model"] == "test:latest"
        assert data["num_ctx"] == 26758
        assert data["duration_minutes"] == 2.06
        assert _tmp_artifacts(tmp_path) == []

    def test_quality_report_atomic(self, tmp_path):
        from core.models import Segment, SummaryResult
        from core.pipeline.converter_impl import Converter

        class _Paths:
            def __init__(self, p):
                self.quality_report = p

        fake = SimpleNamespace(
            request=SimpleNamespace(input_path=Path("My_Book.pdf")),
            paths=_Paths(tmp_path / "logs" / "quality_report.json"),
            _log=lambda m, l="INFO": None,
        )
        summaries = [SummaryResult(
            chapter_heading="Ch 1", executive_summary="e", thorough_summary="t",
            bullet_points=["b1", "b2"], success=True, model_used="m",
            input_tokens=900, output_tokens=100,
        )]
        segments = [Segment(heading="Ch 1", content="text " * 50,
                            start_page=1, end_page=2, segment_type="chapter")]
        Converter._generate_quality_report(fake, segments, summaries)

        qr = fake.paths.quality_report
        assert qr.exists()
        data = json.loads(qr.read_text(encoding="utf-8"))
        assert data["totals"]["chapters_summarized"] == 1
        assert data["totals"]["total_bullets"] == 2
        assert _tmp_artifacts(tmp_path) == []

    def test_output_save_and_book_summary_use_atomic_helpers(self):
        """Source guard: the full-markdown + Book.summary.md writes route
        through utils.atomic_io."""
        out_save = (_project_root / "core" / "pipeline" / "conversion" /
                    "output_save.py").read_text(encoding="utf-8")
        assert "atomic_write_text(converter.full_markdown_path, full_markdown)" in out_save
        assert "full_markdown_path).write_text(" not in out_save

        summ = (_project_root / "core" / "pipeline" / "conversion" /
                "summarization.py").read_text(encoding="utf-8")
        assert "atomic_write_text(converter.summary_md_path, book_summary)" in summ
        # the old plain write is gone
        assert "summary_md_path).write_text(" not in summ
