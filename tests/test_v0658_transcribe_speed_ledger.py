"""V0.6.58 -- the speed ledger + bat parity: answer "how long SHOULD
this take, is the app slower than my transcribe.bat, and what would
make it fast again?" with data.

THE TRIGGER (the operator's report, verbatim):
    "Look it seems there is a problem: ... [GPU] GPU: 99% util, 11.7 GB
     VRAM used ... still working — 06:15 elapsed ... Note, dragging
     video to this bat file transcribe it under 1 minute, hope it gives
     you ideas."

The uploaded transcribe.bat settled the diagnosis: its CLI invocation
(line 25: ``"%CLI%" -m "%MODEL%" "%WAV%"``) is the SAME command the
app's [CMD] shows -- same exe, same model, same WAV, zero extra flags.
Combined with the upstream source fetched this session
(examples/cli/asr.cpp, handy-computer/transcribe.cpp): the CLI prints
its whole summary only at the END (no TTY/pipe-dependent output), and
the last line is its own throughput figure:

    std::printf("  realtime:   %.0fx (%.1f ms for %.1f s)\n",
                (duration_s * 1000.0) / total_ms, total_ms, duration_s);

So the app runs the same command the bat does, the GPU provably works
(V0.6.57's 99%-util lines), and a 14:43 video at ~2.4x realtime is
whisper-large-v3-on-Vulkan REALITY, not a regression. What was missing
from the log:
  1. a COMPUTED parity proof (the byte-equality was eyeballed, not on
     record),
  2. an expectation BEFORE the wait (the verdict only arrived after),
  3. the upstream's own faster-model recommendation
     (whisper-large-v3-turbo: 809M / 886 MB / WER 2.01% vs large-v3's
     1.5B / 1.67 GB / 1.82% -- docs/models/whisper.md: "the best
     accuracy/speed tradeoff").

WHAT V0.6.58 ADDS
-----------------
  - core/transcribe/speed_ledger.py (Qt-free leaf): parse the CLI's
    own realtime line, persist the last completed run's measured
    throughput per model (~/.elixir/transcribe_speed_ledger.json,
    best-effort everywhere), format the [SPEED] lines, and gate the
    slow-model hint on MEASURED data.
  - Engine: [PARITY] (the computed app-vs-bat command comparison) +
    [SPEED] (the last run's throughput and the wait it predicts for
    THIS audio) BEFORE the run; the CLI's realtime figure + the wall
    ratio + the ledger record AFTER it.
  - tests/fixtures/transcribe.bat: the operator's ACTUAL bat, frozen
    verbatim -- the parity claim is pinned against the real file, not
    a description of it.

TEST LAYOUT
-----------
  A. parse_realtime_line  -- the upstream printf format, exactly
  B. ledger IO            -- record/load round-trips, corruption, caps
  C. formatters           -- [SPEED] expectation + done lines
  D. slow-model gate      -- when the turbo hint is earned
  E. engine helpers       -- _format_speed_and_parity_lines, dynamic
  F. engine source pins   -- AST pins (the house style)
  G. the bat fixture      -- parity pinned to the operator's REAL bat
"""

from __future__ import annotations

import ast
import json
import re
import sys
import wave
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_ENGINE = _project_root / "core" / "transcribe" / "transcribe_cpp_engine.py"
_LEDGER = _project_root / "core" / "transcribe" / "speed_ledger.py"
_BAT = _project_root / "tests" / "fixtures" / "transcribe.bat"

from core.transcribe import speed_ledger as sl  # noqa: E402


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


def _make_wav(path: Path, seconds: float) -> Path:
    """A real 16 kHz mono PCM WAV of the given duration (stdlib wave)."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return path


# ═════════════════════════════════════════════════════════════════════════════
# A. parse_realtime_line -- the upstream printf format, exactly
# ═════════════════════════════════════════════════════════════════════════════


class TestParseRealtimeLine:
    def test_the_upstream_printf_format_exactly(self):
        # asr.cpp: "  realtime:   %.0fx (%.1f ms for %.1f s)" -- the
        # three numbers: multiple, compute ms, audio seconds.
        out = "  realtime:   2x (371234.5 ms for 883.0 s)\n"
        r = sl.parse_realtime_line(out)
        assert r == {"realtime_x": 2.0, "compute_ms": 371234.5, "audio_s": 883.0}

    def test_fast_run_variant(self):
        r = sl.parse_realtime_line("  realtime:   24x (60000.0 ms for 1440.0 s)\n")
        assert r is not None and r["realtime_x"] == 24.0
        assert r["audio_s"] == 1440.0

    def test_slow_run_variant(self):
        r = sl.parse_realtime_line("realtime: 0.4x (900000.0 ms for 360.0 s)")
        assert r is not None and r["realtime_x"] == 0.4

    def test_found_inside_a_full_summary(self):
        # The real stdout: run/text/segments first, realtime LAST.
        out = (
            "run: OK\n"
            "text: There are three main things...\n"
            "detected-language: en\n"
            "segments: 29\n"
            "  [    0.00 ->     6.20] There are three main things...\n"
            "  realtime:   2x (371234.5 ms for 883.0 s)\n"
        )
        r = sl.parse_realtime_line(out)
        assert r is not None and r["realtime_x"] == 2.0

    def test_spacing_tolerant(self):
        r = sl.parse_realtime_line("realtime:2x(1000ms for 2.0s)")
        assert r is not None and r["realtime_x"] == 2.0

    def test_no_realtime_line_is_none(self):
        assert sl.parse_realtime_line("run: OK\ntext: hi\n") is None

    def test_empty_and_garbage_is_none(self):
        assert sl.parse_realtime_line("") is None
        assert sl.parse_realtime_line(None) is None
        assert sl.parse_realtime_line("realtime: xx (yy ms for zz s)") is None

    def test_non_positive_numbers_are_none(self):
        # A 0x figure is printf's floor of a degenerate measurement --
        # not a throughput. Reject rather than record nonsense.
        assert sl.parse_realtime_line("realtime: 0x (100.0 ms for 0.0 s)") is None


# ═════════════════════════════════════════════════════════════════════════════
# B. the ledger -- record/load round-trips, corruption, caps
# ═════════════════════════════════════════════════════════════════════════════


class TestLedgerIO:
    def test_missing_file_is_empty_dict(self, tmp_path):
        assert sl.load_ledger(tmp_path / "nope.json") == {}

    def test_corrupt_json_is_empty_dict(self, tmp_path):
        p = tmp_path / "ledger.json"
        p.write_text("{corrupt", encoding="utf-8")
        assert sl.load_ledger(p) == {}

    def test_non_dict_payload_is_empty_dict(self, tmp_path):
        p = tmp_path / "ledger.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        assert sl.load_ledger(p) == {}

    def test_bom_tolerant(self, tmp_path):
        p = tmp_path / "ledger.json"
        p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"m.gguf": {"model": "m.gguf"}}).encode("utf-8"))
        ledger = sl.load_ledger(p)
        assert sl.last_entry(ledger, "m.gguf") is not None

    def test_record_run_round_trip(self, tmp_path):
        p = tmp_path / "ledger.json"
        entry = sl.record_run(
            p,
            model="whisper-large-v3-Q8_0.gguf",
            realtime_x=2.0,
            audio_s=883.0,
            elapsed_s=372.0,
            compute_ms=371234.5,
            backend="vulkan",
        )
        assert entry is not None
        assert entry["realtime_x"] == 2.0
        assert entry["wall_x"] == pytest.approx(883.0 / 372.0)
        assert entry["runs"] == 1
        assert entry["when"]  # a timestamp exists
        # And it persists:
        again = sl.last_entry(sl.load_ledger(p), "whisper-large-v3-Q8_0.gguf")
        assert again is not None and again["realtime_x"] == 2.0
        assert again["backend"] == "vulkan"

    def test_second_record_increments_runs_and_replaces(self, tmp_path):
        p = tmp_path / "ledger.json"
        sl.record_run(p, model="m.gguf", realtime_x=2.0, audio_s=100.0, elapsed_s=50.0)
        entry = sl.record_run(p, model="m.gguf", realtime_x=8.0, audio_s=100.0, elapsed_s=12.0)
        assert entry["runs"] == 2
        assert entry["realtime_x"] == 8.0
        assert sl.last_entry(sl.load_ledger(p), "m.gguf")["runs"] == 2

    def test_two_models_coexist(self, tmp_path):
        p = tmp_path / "ledger.json"
        sl.record_run(p, model="a.gguf", realtime_x=2.0)
        sl.record_run(p, model="b.gguf", realtime_x=30.0)
        ledger = sl.load_ledger(p)
        assert sl.last_entry(ledger, "a.gguf")["realtime_x"] == 2.0
        assert sl.last_entry(ledger, "b.gguf")["realtime_x"] == 30.0

    def test_unwritable_path_is_none_not_a_crash(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file, not a dir", encoding="utf-8")
        result = sl.record_run(blocker / "sub" / "ledger.json", model="m.gguf", realtime_x=2.0)
        assert result is None

    def test_none_figures_stored_as_none(self, tmp_path):
        p = tmp_path / "ledger.json"
        entry = sl.record_run(p, model="m.gguf")  # everything optional
        assert entry["realtime_x"] is None
        assert entry["wall_x"] is None
        assert entry["runs"] == 1

    def test_empty_model_name_is_none(self, tmp_path):
        assert sl.record_run(tmp_path / "l.json", model="") is None

    def test_last_entry_unknown_model_is_none(self):
        assert sl.last_entry({"other.gguf": {"runs": 1}}, "m.gguf") is None
        assert sl.last_entry({}, "m.gguf") is None
        assert sl.last_entry(None, "m.gguf") is None
        assert sl.last_entry({"m.gguf": "not-a-dict"}, "m.gguf") is None


class TestEntryRealtime:
    def test_prefers_the_cli_figure(self):
        assert sl.entry_realtime({"realtime_x": 2.0, "wall_x": 2.4}) == 2.0

    def test_falls_back_to_wall(self):
        assert sl.entry_realtime({"realtime_x": None, "wall_x": 2.4}) == 2.4

    def test_no_figures_is_none(self):
        assert sl.entry_realtime({}) is None
        assert sl.entry_realtime(None) is None
        assert sl.entry_realtime({"realtime_x": 0, "wall_x": 0}) is None


# ═════════════════════════════════════════════════════════════════════════════
# C. the formatters -- [SPEED] expectation + done lines
# ═════════════════════════════════════════════════════════════════════════════


class TestSpeedFormatters:
    def test_expectation_line_with_audio(self):
        # The operator's case: 883 s of audio, last wall ratio 2.37x
        # (CLI figure absent) → "2.4x realtime — expect ~6 min".
        entry = {"model": "whisper-large-v3-Q8_0.gguf", "wall_x": 883.0 / 372.0, "realtime_x": None}
        line = sl.format_speed_line(entry, 883.0)
        assert line.startswith("last run of whisper-large-v3-Q8_0.gguf: ")
        assert "2.4x realtime" in line
        assert "expect ~6 min for 14:43 of audio" in line

    def test_expectation_line_without_audio(self):
        line = sl.format_speed_line({"model": "m.gguf", "realtime_x": 2.0}, None)
        assert line == "last run of m.gguf: 2.0x realtime"

    def test_realtime_only_entry_uses_the_cli_figure(self):
        line = sl.format_speed_line({"model": "m.gguf", "realtime_x": 2.0}, None)
        assert "2.0x realtime" in line

    def test_cli_figure_preferred_over_wall(self):
        # entry_realtime prefers the CLI's own number when present.
        line = sl.format_speed_line({"model": "m.gguf", "realtime_x": 3.0, "wall_x": 2.4}, 883.0)
        assert "3.0x realtime" in line
        assert "expect ~5 min" in line  # 883/3.0 = 294 s = 4.9 min

    def test_no_figures_says_so_plainly(self):
        line = sl.format_speed_line({"model": "m.gguf"}, None)
        assert "no throughput figure" in line

    def test_expectation_rounding(self):
        # Fast model: 883 s at 40x → ~22s (sub-minute gets seconds).
        line = sl.format_speed_line({"model": "m.gguf", "realtime_x": 40.0}, 883.0)
        assert "expect ~22s for 14:43 of audio" in line

    def test_done_line_with_all_figures(self):
        line = sl.format_done_line(372.0, 883.0, 2.0)
        assert line == (
            "done in 06:12 — 2.4x realtime for 14:43 of audio "
            "(the CLI's own figure: 2.0x compute-only)"
        )

    def test_done_line_without_realtime(self):
        line = sl.format_done_line(372.0, 883.0, None)
        assert line == "done in 06:12 — 2.4x realtime for 14:43 of audio"

    def test_done_line_without_audio(self):
        assert sl.format_done_line(12.5, None, None) == "done in 00:12"

    def test_x_formatting(self):
        assert sl._fmt_x(0.4) == "0.4x"
        assert sl._fmt_x(2.37) == "2.4x"
        assert sl._fmt_x(24.0) == "24x"


# ═════════════════════════════════════════════════════════════════════════════
# D. the slow-model gate -- when is the turbo hint earned?
# ═════════════════════════════════════════════════════════════════════════════


class TestSlowModelGate:
    def test_slow_whisper_earns_the_hint(self):
        # The operator's measured reality: large-v3 at ~2.4x on Vulkan.
        assert sl.should_suggest_turbo("whisper-large-v3-Q8_0.gguf", 2.4) is True

    def test_fast_enough_does_not(self):
        assert sl.should_suggest_turbo("whisper-large-v3-Q8_0.gguf", 8.0) is False

    def test_already_turbo_does_not(self):
        assert sl.should_suggest_turbo("whisper-large-v3-turbo-Q8_0.gguf", 2.0) is False

    def test_non_whisper_family_does_not(self):
        assert sl.should_suggest_turbo("parakeet-tdt-0.6b-v2.gguf", 2.0) is False

    def test_no_data_no_verdict(self):
        # Never diagnose without a measurement.
        assert sl.should_suggest_turbo("whisper-large-v3-Q8_0.gguf", None) is False
        assert sl.should_suggest_turbo("whisper-large-v3-Q8_0.gguf", 0.0) is False

    def test_the_hint_is_the_upstreams_own_numbers(self):
        # docs/models/whisper.md: turbo 809M / 886 MB / WER 2.01% vs
        # large-v3 1.5B / 1.67 GB / 1.82%; cuda-windows.yml for the
        # CUDA build path; huggingface.co/handy-computer for the model.
        hint = sl.SLOW_MODEL_HINT
        assert "whisper-large-v3-turbo" in hint
        assert "886 MB" in hint
        assert "2.01%" in hint and "1.82%" in hint
        assert "cuda-windows.yml" in hint
        assert "huggingface.co/handy-computer" in hint

    def test_the_hint_explains_the_real_cause(self):
        # The run is NOT broken and NOT on the CPU — it is the model
        # choice on Vulkan. The hint must say so (the operator's fear
        # was "something is broken").
        assert "not a bug" in sl.SLOW_MODEL_HINT
        assert "Vulkan" in sl.SLOW_MODEL_HINT

    def test_the_hint_does_not_repeat_the_v0657_cpu_warning(self):
        # TRANSCRIBE_VULKAN belongs to the V0.6.57 CPU-warning world;
        # this hint is the model/build speed path.
        assert "TRANSCRIBE_VULKAN" not in sl.SLOW_MODEL_HINT


# ═════════════════════════════════════════════════════════════════════════════
# E. engine helpers -- _format_speed_and_parity_lines, dynamic
# ═════════════════════════════════════════════════════════════════════════════


class TestSpeedAndParityLines:
    def _engine(self):
        sys.path.insert(0, str(_project_root))
        from core.transcribe import transcribe_cpp_engine as engine

        return engine

    def test_byte_parity_line_when_cmd_matches_the_bat_form(self, tmp_path):
        engine = self._engine()
        exe = r"C:\transcribe.cpp\build\bin\Release\transcribe-cli.exe"
        model = r"C:\transcribe.cpp\models\whisper-large-v3-Q8_0.gguf"
        wav = r"C:\tmp\npm\transcribe_cpp_7qsah6b0.wav"
        cmd = [exe, "-m", model, wav]  # the app's form: language auto
        lines = engine._format_speed_and_parity_lines(model, wav, cmd, None)
        assert len(lines) == 1  # parity only -- no ledger data yet
        parity = lines[0]
        assert parity.startswith("  [PARITY] ")
        assert "byte-identical to your transcribe.bat command" in parity
        assert "NOT the command line" in parity

    def test_language_flag_line_names_the_extra(self, tmp_path):
        engine = self._engine()
        exe, model = "cli.exe", "m.gguf"
        cmd = [exe, "-m", model, "-l", "en", "audio.wav"]
        lines = engine._format_speed_and_parity_lines(model, "audio.wav", cmd, None)
        parity = lines[0]
        assert "transcribe.bat + -l en" in parity
        assert "language hint" in parity

    def test_speed_line_when_ledger_entry_exists(self, tmp_path):
        engine = self._engine()
        entry = {"model": "m.gguf", "realtime_x": 2.0, "wall_x": None}
        lines = engine._format_speed_and_parity_lines(
            "m.gguf", "audio.wav", ["cli.exe", "-m", "m.gguf", "audio.wav"], entry, audio_s=883.0
        )
        speed = [ln for ln in lines if ln.startswith("  [SPEED] ")]
        assert len(speed) == 1
        assert "2.0x realtime" in speed[0]
        # 883 s at 2.0x = 441.5 s → ~7 min
        assert "expect ~7 min for 14:43 of audio" in speed[0]

    def test_speed_line_duration_from_a_real_wav(self, tmp_path):
        engine = self._engine()
        wav = _make_wav(tmp_path / "a.wav", 30.0)
        entry = {"model": "m.gguf", "realtime_x": 2.0}
        lines = engine._format_speed_and_parity_lines(
            "m.gguf", str(wav), ["cli.exe", "-m", "m.gguf", str(wav)], entry, audio_s=None
        )
        speed = [ln for ln in lines if ln.startswith("  [SPEED] ")]
        assert len(speed) == 1
        assert "for 00:30 of audio" in speed[0]
        # 30 s at 2.0x = 15 s → sub-minute gets seconds, not minutes
        assert "expect ~15s" in speed[0]

    def test_no_entry_means_no_speed_line(self, tmp_path):
        engine = self._engine()
        lines = engine._format_speed_and_parity_lines(
            "m.gguf", "a.wav", ["cli.exe", "-m", "m.gguf", "a.wav"], None
        )
        assert all(not ln.startswith("  [SPEED] ") for ln in lines)

    def test_non_wav_path_speed_line_without_expectation(self, tmp_path):
        engine = self._engine()
        entry = {"model": "m.gguf", "realtime_x": 2.0}
        lines = engine._format_speed_and_parity_lines(
            "m.gguf",
            str(tmp_path / "garbage.bin"),
            ["cli.exe", "-m", "m.gguf", str(tmp_path / "garbage.bin")],
            entry,
            audio_s=None,
        )
        speed = [ln for ln in lines if ln.startswith("  [SPEED] ")]
        assert len(speed) == 1
        assert "realtime" in speed[0]
        assert "expect" not in speed[0]


# ═════════════════════════════════════════════════════════════════════════════
# F. engine source pins -- the V0.6.58 wiring, in the house AST style
# ═════════════════════════════════════════════════════════════════════════════


class TestEngineSourcePins:
    def _engine_src(self) -> str:
        return _ENGINE.read_text(encoding="utf-8")

    def test_engine_imports_the_speed_ledger(self):
        src = self._engine_src()
        assert "from core.transcribe.speed_ledger import (" in src
        for name in (
            "SLOW_MODEL_HINT",
            "format_speed_line",
            "format_done_line",
            "parse_realtime_line",
            "record_run",
            "should_suggest_turbo",
        ):
            assert name in src, f"missing import: {name}"

    def test_speed_and_parity_lines_run_before_popen(self):
        # The expectation must be on record BEFORE the wait starts.
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "_format_speed_and_parity_lines(" in fn_src
        assert fn_src.index("_format_speed_and_parity_lines(") < fn_src.index("Popen(")

    def test_v0657_run_config_lines_still_fire_first(self):
        # Regression guard: the V0.6.57 block stays intact AND precedes
        # the V0.6.58 speed block (model/audio/cmd, then parity/speed).
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "_format_run_config_lines(" in fn_src
        assert fn_src.index("_format_run_config_lines(") < fn_src.index(
            "_format_speed_and_parity_lines("
        )

    def test_record_run_happens_after_the_transcribed_log(self):
        # The ledger records a COMPLETED run -- after the [OK] line,
        # before progress(100) closes the pipeline.
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        ok_idx = fn_src.index("[OK] Transcribed in ")
        rec_idx = fn_src.index("record_run(")
        done_idx = fn_src.index('progress(100, "Transcription complete")')
        assert ok_idx < rec_idx < done_idx

    def test_the_speed_loop_is_wrapped_best_effort(self):
        # A ledger failure must NEVER fail a transcription: the
        # post-run block is inside a try/except.
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_nodes = [n for n in ast.walk(fn) if isinstance(n, ast.Try)]
        assert any(
            any(
                isinstance(call.func, ast.Name) and call.func.id == "record_run"
                for call in ast.walk(t)
                if isinstance(call, ast.Call)
            )
            for t in fn_nodes
        )

    def test_audio_duration_computed_before_the_run_not_after(self):
        # The temp WAV is deleted before the result dict is built; the
        # audio duration must be measured pre-run (the end-of-run
        # [SPEED] line reuses the precomputed value).
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        dur_idx = fn_src.index("audio_s = _wav_duration_s(")
        assert dur_idx < fn_src.index("Popen(")
        assert dur_idx < fn_src.index("_cleanup_temp(temp_wav)")

    def test_pre_run_hint_gates_on_measured_data(self):
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        # Up front: only when the ledger HAS a slow figure for a prior
        # run of this model (never a guess).
        assert "entry_realtime(_last_speed)" in fn_src
        assert fn_src.count("should_suggest_turbo(") >= 2  # pre-run + post-run

    def test_first_run_only_end_hint(self):
        # The end-of-run hint fires only when the pre-run one could not
        # have (no ledger entry yet) -- later runs get it up front.
        src = self._engine_src()
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "_last_speed is None" in fn_src


# ═════════════════════════════════════════════════════════════════════════════
# G. the bat fixture -- parity pinned to the operator's REAL file
# ═════════════════════════════════════════════════════════════════════════════


class TestBatFixtureParity:
    def test_the_operators_bat_is_on_record(self):
        # The operator's actual transcribe.bat, frozen verbatim -- the
        # ground truth the parity claim is checked against.
        assert _BAT.exists()
        bat = _BAT.read_text(encoding="utf-8")
        # The bat's own config: the same exe + model the app defaults to.
        assert "transcribe-cli.exe" in bat
        assert "whisper-large-v3-Q8_0.gguf" in bat

    def test_the_bats_cli_invocation_is_the_canonical_shape(self):
        # Line 25 of the bat: "%CLI%" -m "%MODEL%" "%WAV%" > "%OUT%"
        # → argv [cli, -m, model, wav] — exactly the four-element form
        # the engine's parity check treats as byte-identical.
        bat = _BAT.read_text(encoding="utf-8")
        m = re.search(r'"%CLI%"\s+(-m)\s+"%MODEL%"\s+"%WAV%"', bat)
        assert m is not None, "the bat's invocation line changed shape"
        assert m.group(1) == "-m"

    def test_the_bat_converts_the_same_way_the_engine_does(self):
        # The bat's ffmpeg line: -ar 16000 -ac 1 (via %FFMPEG%) — the
        # engine's _convert_to_wav16k uses exactly these (plus
        # pcm_s16le). The inputs to the CLI are identical, not just
        # the command.
        bat = _BAT.read_text(encoding="utf-8")
        m = re.search(r"-ar\s+16000\s+-ac\s+1", bat)
        assert m is not None
        # and the ffmpeg binary is plain PATH ffmpeg, like the engine's
        assert re.search(r'set "FFMPEG=ffmpeg"', bat) is not None

    def test_engine_default_model_is_the_bats_model(self):
        # The app's DEFAULT_TRANSCRIBE_CPP_MODEL is the very model the
        # operator's bat configures — the parity claim covers the real
        # rig, not a hypothetical one.
        bat = _BAT.read_text(encoding="utf-8")
        m = re.search(r'set "MODEL=(.+?)"', bat)
        assert m is not None
        sys.path.insert(0, str(_project_root))
        from core.transcribe import transcribe_cpp_engine as engine

        assert m.group(1) == engine.DEFAULT_TRANSCRIBE_CPP_MODEL
