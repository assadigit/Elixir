"""V0.6.57 -- the GPU liveness probe: answer "is it on the CPU or the GPU?"
with DATA, not guesses.

THE TRIGGER (the operator's report, verbatim):
    "Why model is working on cpu? I have weak cpu and strong GPU!
     ... it used to transcribe in less than a minute by using the same
     transcribe.cpp! Something is broken"

The V0.6.56 live log PROVED the run goes silent for 3+ minutes between
[RUN] and any output. Combined with the parser fixtures (the REAL
transcribe-cli.exe format), the diagnosis is:

  1. transcribe-cli.exe prints its WHOLE summary -- audio/model/backend/
     text/segments/realtime -- only at the END of the run. Silence while
     working is that CLI's DESIGN, not a hang (the V0.6.52 fixture is the
     proof: "realtime: 0.4x" can only be computed after the full run).
  2. The app's CLI command is byte-identical since V0.6.40 (git-verified)
     -- V0.6.56 changed HOW output is read (Popen+stream), never WHAT the
     child receives. The app cannot have switched the CLI to CPU.
  3. The one thing the log could NOT answer: which device is actually
     computing. The operator guessed CPU from Task Manager; the log had
     no GPU evidence either way. THIS is the gap V0.6.57 closes.

WHAT V0.6.57 ADDS
-----------------
  - core/transcribe/gpu_probe.py (Qt-free leaf): nvidia-smi query ->
    util % + VRAM used, injectable runner, best-effort everywhere.
  - --list-devices PRE-FLIGHT: the operator supplied the upstream repo
    (github.com/handy-computer/transcribe.cpp); its CLI supports
    --list-devices, which registers the backends compiled INTO the exe
    and lists every device (no model, no audio, seconds). A plain
    'cmake -B build' on Windows is CPU-ONLY (-DTRANSCRIBE_VULKAN=ON is
    required for Vulkan) and the default 'auto' backend then silently
    picks CPU -- the most likely root cause of the report. The engine
    now runs the pre-flight BEFORE the model load and warns loudly when
    no GPU device is registered.
  - _stream_cli_output(gpu_probe_interval_s=...): the poll loop probes
    the GPU every interval and logs "  [GPU] ..." lines -- a growing
    VRAM number during model load, high util during transcription; a
    flat 0% for minutes is the honest "check the backend" signal. First
    failure (no nvidia-smi / not NVIDIA) logs ONE unavailable line and
    disables itself -- never spam, never a crash.
  - transcribe_with_cpp logs [MODEL] (name+size), [AUDIO] (duration of
    the temp WAV) and [CMD] (the exact command line) before [RUN] --
    the operator can finally SEE whether a 3 GB model is loading and
    reproduce the run manually against their transcribe.bat.
  - Backend verdict at the END: the parser already extracts "backend:";
    if it says CPU, a WARNING explains the slow run (Vulkan not used).
  - The heartbeat silence hint is now ENGINE-AWARE: transcribe.cpp runs
    explain end-only printing + the GPU line; LLM runs keep the old hint.

TEST LAYOUT
-----------
  A. gpu_probe leaf            -- dynamic, stdlib only
  B. _stream_cli_output probe  -- dynamic, FakeProc + monkeypatched probe
  C. engine run-config + verdict -- dynamic helpers + AST pins
  D. pipeline_log hint         -- dynamic, Qt-free
  E. dialog wiring             -- AST pins (the house style)
"""

from __future__ import annotations

import ast
import io
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_ENGINE = _project_root / "core" / "transcribe" / "transcribe_cpp_engine.py"
_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_PROBE = _project_root / "core" / "transcribe" / "gpu_probe.py"


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


def _dialog_tree() -> ast.Module:
    return ast.parse(_DIALOG.read_text(encoding="utf-8"))


# ═════════════════════════════════════════════════════════════════════════════
# A. gpu_probe -- the Qt-free leaf (dynamic)
# ═════════════════════════════════════════════════════════════════════════════


class TestGpuProbeParsing:
    def test_parses_the_nvidia_smi_csv_row(self):
        from core.transcribe.gpu_probe import parse_nvidia_smi_output

        state = parse_nvidia_smi_output("12, 3452\n")
        assert state == {"util_pct": 12, "mem_used_mb": 3452}

    def test_multi_gpu_output_uses_the_first_row(self):
        from core.transcribe.gpu_probe import parse_nvidia_smi_output

        state = parse_nvidia_smi_output("97, 2048\n0, 1024\n")
        assert state == {"util_pct": 97, "mem_used_mb": 2048}

    def test_garbage_is_none_not_a_crash(self):
        from core.transcribe.gpu_probe import parse_nvidia_smi_output

        for bad in ("", "\n", "NVIDIA-SMI has failed\n", "abc, def\n", "[N/A], [N/A]\n"):
            assert parse_nvidia_smi_output(bad) is None, repr(bad)

    def test_whitespace_tolerant(self):
        from core.transcribe.gpu_probe import parse_nvidia_smi_output

        assert parse_nvidia_smi_output(" 12 ,  3452 \n") == {"util_pct": 12, "mem_used_mb": 3452}


class TestGpuProbeState:
    def test_injected_runner_success(self):
        from core.transcribe.gpu_probe import probe_gpu_state

        state = probe_gpu_state(runner=lambda cmd, timeout_s: "12, 3452\n")
        assert state == {"util_pct": 12, "mem_used_mb": 3452}

    def test_injected_runner_returning_none_is_none(self):
        from core.transcribe.gpu_probe import probe_gpu_state

        assert probe_gpu_state(runner=lambda cmd, timeout_s: None) is None

    def test_injected_runner_raising_is_none(self):
        from core.transcribe.gpu_probe import probe_gpu_state

        def boom(cmd, timeout_s):
            raise FileNotFoundError("nvidia-smi")

        assert probe_gpu_state(runner=boom) is None

    def test_default_runner_queries_nvidia_smi(self, monkeypatch):
        # The REAL default path builds an nvidia-smi --query-gpu call;
        # with subprocess.run faked, the command must be visible.
        import core.transcribe.gpu_probe as gp

        calls: list[list[str]] = []
        kwargs_seen: list[dict] = []

        class _FakeCompleted:
            returncode = 0
            stdout = "10, 512\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            kwargs_seen.append(kwargs)
            return _FakeCompleted()

        monkeypatch.setattr(gp.subprocess, "run", fake_run)
        state = gp.probe_gpu_state()
        assert state == {"util_pct": 10, "mem_used_mb": 512}
        assert calls and "nvidia-smi" in calls[0]
        assert any("--query-gpu" in part for part in calls[0])
        # a timeout must be passed -- the probe can never hang the
        # worker thread on a wedged driver
        assert kwargs_seen and "timeout" in kwargs_seen[0]

    def test_default_runner_nonzero_exit_is_none(self, monkeypatch):
        import core.transcribe.gpu_probe as gp

        class _FakeCompleted:
            returncode = 1
            stdout = ""
            stderr = "err"

        monkeypatch.setattr(gp.subprocess, "run", lambda cmd, **kw: _FakeCompleted())
        assert gp.probe_gpu_state() is None

    def test_default_runner_timeout_is_none(self, monkeypatch):
        import core.transcribe.gpu_probe as gp

        def raise_timeout(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)

        monkeypatch.setattr(gp.subprocess, "run", raise_timeout)
        assert gp.probe_gpu_state() is None


class TestGpuFormatLine:
    def test_formats_util_and_vram(self):
        from core.transcribe.gpu_probe import format_gpu_line

        line = format_gpu_line({"util_pct": 97, "mem_used_mb": 3412})
        assert "97%" in line
        assert "3.3 GB" in line
        assert "GPU" in line

    def test_low_vram_stays_in_mb(self):
        from core.transcribe.gpu_probe import format_gpu_line

        line = format_gpu_line({"util_pct": 10, "mem_used_mb": 300})
        assert "300 MB" in line

    def test_idle_gpu_is_flagged(self):
        # 0% util for minutes is exactly the "fell back to CPU" signal
        # the operator needs to see, spelled out.
        from core.transcribe.gpu_probe import format_gpu_line

        line = format_gpu_line({"util_pct": 0, "mem_used_mb": 100})
        assert "idle" in line.lower()

    def test_busy_gpu_is_not_flagged_idle(self):
        from core.transcribe.gpu_probe import format_gpu_line

        line = format_gpu_line({"util_pct": 90, "mem_used_mb": 3400})
        assert "idle" not in line.lower()

    def test_none_state_is_the_unavailable_line(self):
        from core.transcribe.gpu_probe import format_gpu_line

        line = format_gpu_line(None)
        assert "unavailable" in line.lower()
        assert "GPU" in line


# ═════════════════════════════════════════════════════════════════════════════
# A2. gpu_probe -- the --list-devices pre-flight (dynamic; the format comes
#     from the upstream examples/cli/main.cpp the operator pointed us at)
# ═════════════════════════════════════════════════════════════════════════════

_DEVICES_SAMPLE = (
    "2 compute device(s):\n"
    "  [0] NVIDIA GeForce RTX 3060\n"
    "      name=NVIDIA GeForce RTX 3060  kind=vulkan  type=gpu  id=PCI:10:00.0\n"
    "      memory: 12.00 GiB total, 10.53 GiB free\n"
    "  [1] 12th Gen Intel(R) Core(TM) i7-12700K\n"
    "      name=cpu  kind=cpu  type=cpu  id=(none)\n"
    "      memory: 0.00 GiB total, 0.00 GiB free\n"
)

_DEVICES_CPU_ONLY = (
    "1 compute device(s):\n"
    "  [0] 12th Gen Intel(R) Core(TM) i7-12700K\n"
    "      name=cpu  kind=cpu  type=cpu  id=(none)\n"
    "      memory: 0.00 GiB total, 0.00 GiB free\n"
)


class TestListDevicesParsing:
    def test_gpu_device_is_found_with_kind_and_memory(self):
        from core.transcribe.gpu_probe import parse_list_devices_output

        state = parse_list_devices_output(_DEVICES_SAMPLE)
        assert state is not None
        assert state["device_count"] == 2
        gpu = state["gpu"]
        assert gpu is not None
        assert gpu["index"] == 0
        assert "RTX 3060" in gpu["description"]
        assert gpu["kind"] == "vulkan"
        assert gpu["type"] == "gpu"
        assert gpu["memory_free_gib"] == pytest.approx(10.53)

    def test_cpu_only_listing_reports_no_gpu(self):
        from core.transcribe.gpu_probe import parse_list_devices_output

        state = parse_list_devices_output(_DEVICES_CPU_ONLY)
        assert state is not None
        assert state["device_count"] == 1
        assert state["gpu"] is None

    def test_igpu_counts_as_gpu(self):
        from core.transcribe.gpu_probe import parse_list_devices_output

        text = (
            "2 compute device(s):\n"
            "  [0] Intel(R) Iris(R) Xe Graphics\n"
            "      name=Intel Iris Xe  kind=vulkan  type=igpu  id=(none)\n"
            "      memory: 8.00 GiB total, 7.10 GiB free\n"
            "  [1] cpu\n"
            "      name=cpu  kind=cpu  type=cpu  id=(none)\n"
        )
        state = parse_list_devices_output(text)
        assert state["gpu"] is not None
        assert state["gpu"]["type"] == "igpu"

    def test_old_exe_garbage_is_none(self):
        from core.transcribe.gpu_probe import parse_list_devices_output

        for bad in ("", "\n", "unknown option --list-devices\n", "NVIDIA-SMI failed\n"):
            assert parse_list_devices_output(bad) is None, repr(bad)

    def test_name_with_spaces_parses(self):
        # main.cpp prints name=%s kind=%s type=%s id=%s with the name free-form
        from core.transcribe.gpu_probe import parse_list_devices_output

        text = (
            "1 compute device(s):\n"
            "  [0] AMD Radeon RX 7900 XTX\n"
            "      name=AMD Radeon RX 7900 XTX  kind=rocm  type=gpu  id=gfx1100\n"
        )
        state = parse_list_devices_output(text)
        assert state["gpu"]["kind"] == "rocm"
        assert state["gpu"]["name"] == "AMD Radeon RX 7900 XTX"


class TestProbeCliDevices:
    def test_injected_runner_success(self):
        from core.transcribe.gpu_probe import probe_cli_devices

        seen: list[list[str]] = []

        def runner(cmd, timeout_s):
            seen.append(cmd)
            return _DEVICES_SAMPLE

        state = probe_cli_devices("C:/transcribe.cpp/transcribe-cli.exe", runner=runner)
        assert state is not None
        assert state["gpu"] is not None
        assert seen and "--list-devices" in seen[0]

    def test_runner_failure_is_none(self):
        from core.transcribe.gpu_probe import probe_cli_devices

        assert probe_cli_devices("x", runner=lambda cmd, t: None) is None

    def test_runner_raising_is_none(self):
        from core.transcribe.gpu_probe import probe_cli_devices

        def boom(cmd, timeout_s):
            raise RuntimeError("exe predates the flag")

        assert probe_cli_devices("x", runner=boom) is None


class TestDevicesFormatLine:
    def test_gpu_line_carries_device_kind_and_vram(self):
        from core.transcribe.gpu_probe import format_devices_line, parse_list_devices_output

        line = format_devices_line(parse_list_devices_output(_DEVICES_SAMPLE))
        assert "RTX 3060" in line
        assert "vulkan" in line
        assert "10.5 GiB free" in line
        assert "auto-select" in line

    def test_no_gpu_line_is_blunt(self):
        from core.transcribe.gpu_probe import format_devices_line, parse_list_devices_output

        line = format_devices_line(parse_list_devices_output(_DEVICES_CPU_ONLY))
        assert "NO GPU" in line
        assert "CPU" in line

    def test_none_state_is_unavailable(self):
        from core.transcribe.gpu_probe import format_devices_line

        line = format_devices_line(None)
        assert "unavailable" in line.lower()


class TestEnginePreflight:
    def test_engine_runs_the_preflight_before_the_run(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "probe_cli_devices(" in fn_src
        assert "_NO_GPU_DEVICE_WARNING" in fn_src
        assert "gpu_label" in fn_src
        # pre-flight and config precede the actual Popen
        assert fn_src.index("probe_cli_devices(") < fn_src.index("Popen(")
        assert fn_src.index("_format_run_config_lines(") < fn_src.index("Popen(")

    def test_the_run_label_is_now_honest_not_hardcoded(self):
        # "(Vulkan GPU)" was an assumption baked in since V0.6.40 — the
        # label must now be built from the pre-flight result
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert 'log(f"  [RUN] Running transcribe.cpp {gpu_label}..."' in fn_src
        assert 'progress(20, f"Transcribing with transcribe.cpp {gpu_label}...")' in fn_src

    def test_the_no_gpu_warning_names_the_real_build_flag(self):
        # The upstream repo (handy-computer/transcribe.cpp) uses
        # -DTRANSCRIBE_VULKAN=ON — NOT whisper.cpp's -DGGML_VULKAN=ON.
        # A wrong flag here would send the operator down a broken path.
        from core.transcribe.transcribe_cpp_engine import (
            _CPU_BACKEND_WARNING,
            _NO_GPU_DEVICE_WARNING,
        )

        assert "-DTRANSCRIBE_VULKAN=ON" in _NO_GPU_DEVICE_WARNING
        assert "-DTRANSCRIBE_VULKAN=ON" in _CPU_BACKEND_WARNING
        assert "GGML_VULKAN" not in _NO_GPU_DEVICE_WARNING
        assert "GGML_VULKAN" not in _CPU_BACKEND_WARNING

    def test_engine_imports_the_new_probe_helpers(self):
        src = _ENGINE.read_text(encoding="utf-8")
        assert "probe_cli_devices" in src
        assert "format_devices_line" in src


# ═════════════════════════════════════════════════════════════════════════════
# B. _stream_cli_output -- the periodic probe in the poll loop (dynamic)
# ═════════════════════════════════════════════════════════════════════════════


class _FakeProc:
    """The Popen surface _stream_cli_output touches (V0.6.56 harness,
    copied so this file stays standalone)."""

    def __init__(
        self, stdout: bytes, stderr: bytes = b"", returncode: int = 0, *, hangs: bool = False
    ):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.killed = False
        self.hangs = hangs

    def wait(self, timeout=None):  # noqa: ARG002 -- Popen signature
        if self.hangs and timeout is not None and not self.killed:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class TestStreamProbe:
    def test_probe_lines_land_in_the_log_while_the_cli_works(self, monkeypatch):
        import core.transcribe.transcribe_cpp_engine as eng

        calls: list[dict] = []

        def fake_probe():
            calls.append({"util_pct": 96, "mem_used_mb": 3412})
            return calls[-1]

        monkeypatch.setattr(eng, "probe_gpu_state", fake_probe)
        proc = _FakeProc(b"", hangs=True)
        echoed: list[str] = []
        _out, _err, _code, timed_out = eng._stream_cli_output(
            proc,
            log=lambda msg, level="INFO": echoed.append(msg),
            progress=lambda pct, msg: None,
            deadline_ts=time.monotonic() + 0.7,
            gpu_probe_interval_s=0.05,
        )
        assert timed_out is True
        joined = "\n".join(echoed)
        assert "96%" in joined
        assert "3.3 GB" in joined
        assert calls, "the probe must actually run during the run"

    def test_unavailable_probe_logs_once_then_disables(self, monkeypatch):
        import core.transcribe.transcribe_cpp_engine as eng

        calls: list[None] = []

        def fake_probe():
            calls.append(None)
            return None

        monkeypatch.setattr(eng, "probe_gpu_state", fake_probe)
        proc = _FakeProc(b"", hangs=True)
        echoed: list[str] = []
        eng._stream_cli_output(
            proc,
            log=lambda msg, level="INFO": echoed.append(msg),
            progress=lambda pct, msg: None,
            deadline_ts=time.monotonic() + 1.0,
            gpu_probe_interval_s=0.05,
        )
        joined = "\n".join(echoed)
        # one honest "cannot verify" line, never spam
        assert joined.count("unavailable") == 1
        assert len(calls) == 1, "after the first failure the probe must disable itself"

    def test_raising_probe_is_treated_as_unavailable(self, monkeypatch):
        import core.transcribe.transcribe_cpp_engine as eng

        def boom():
            raise RuntimeError("driver wedged")

        monkeypatch.setattr(eng, "probe_gpu_state", boom)
        proc = _FakeProc(b"", hangs=True)
        echoed: list[str] = []
        out, err, code, timed_out = eng._stream_cli_output(
            proc,
            log=lambda msg, level="INFO": echoed.append(msg),
            progress=lambda pct, msg: None,
            deadline_ts=time.monotonic() + 0.7,
            gpu_probe_interval_s=0.05,
        )
        assert timed_out is True
        assert out == "" and err == ""
        assert "\n".join(echoed).count("unavailable") == 1

    def test_no_interval_means_no_probe_calls(self, monkeypatch):
        # Backward compatibility: the V0.6.56 call sites (and all their
        # tests) pass no interval -- the probe must never fire there.
        import core.transcribe.transcribe_cpp_engine as eng

        def boom():
            raise AssertionError("probe must not run without an interval")

        monkeypatch.setattr(eng, "probe_gpu_state", boom)
        echoed: list[str] = []
        eng._stream_cli_output(
            _FakeProc(b"text: hi\n"),
            log=lambda msg, level="INFO": echoed.append(msg),
            progress=lambda pct, msg: None,
            deadline_ts=time.monotonic() + 2.0,
        )
        assert any("text: hi" in e for e in echoed)
        assert not any("GPU" in e for e in echoed)

    def test_probe_lines_are_not_progress_lines(self, monkeypatch):
        # The GPU line rides the LOG path only -- the progress bar maps
        # whisper percents, never GPU util.
        import core.transcribe.transcribe_cpp_engine as eng

        monkeypatch.setattr(eng, "probe_gpu_state", lambda: {"util_pct": 96, "mem_used_mb": 3412})
        progressed: list[tuple[int, str]] = []
        eng._stream_cli_output(
            _FakeProc(b"", hangs=True),
            log=lambda msg, level="INFO": None,
            progress=lambda pct, msg: progressed.append((pct, msg)),
            deadline_ts=time.monotonic() + 0.7,
            gpu_probe_interval_s=0.05,
        )
        assert progressed == []


# ═════════════════════════════════════════════════════════════════════════════
# C. ENGINE -- run-config lines + the backend verdict
# ═════════════════════════════════════════════════════════════════════════════


class TestRunConfigLines:
    def test_model_line_has_name_and_size(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        model = tmp_path / "whisper-large-v3-Q8_0.gguf"
        model.write_bytes(b"x" * (3 * 1024 * 1024 * 1024 // 10))  # 0.3 GB
        wav = tmp_path / "in.wav"
        wav.write_bytes(b"x")
        lines = _format_run_config_lines(
            str(model), str(wav), ["transcribe-cli.exe", "-m", str(model)]
        )
        joined = "\n".join(lines)
        assert "[MODEL]" in joined
        assert "whisper-large-v3-Q8_0.gguf" in joined
        assert "GB" in joined or "MB" in joined

    def test_cmd_line_is_the_manual_repro(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        model = tmp_path / "m.gguf"
        model.write_bytes(b"x" * 100)
        wav = tmp_path / "in.wav"
        wav.write_bytes(b"x")
        cmd = ["C:\\transcribe.cpp\\transcribe-cli.exe", "-m", str(model), str(wav)]
        joined = "\n".join(_format_run_config_lines(str(model), str(wav), cmd))
        assert "[CMD]" in joined
        assert "transcribe-cli.exe" in joined
        assert "-m" in joined

    def test_audio_duration_line_from_a_real_wav(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        model = tmp_path / "m.gguf"
        model.write_bytes(b"x" * 100)
        wav = tmp_path / "clip.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x01" * 16000 * 65)  # 65s
        joined = "\n".join(_format_run_config_lines(str(model), str(wav), ["exe"]))
        assert "[AUDIO]" in joined
        assert "01:05" in joined

    def test_non_wav_input_skips_the_audio_line(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        model = tmp_path / "m.gguf"
        model.write_bytes(b"x" * 100)
        bogus = tmp_path / "notawav.bin"
        bogus.write_bytes(b"nope")
        joined = "\n".join(_format_run_config_lines(str(model), str(bogus), ["exe"]))
        assert "[AUDIO]" not in joined
        assert "[MODEL]" in joined and "[CMD]" in joined

    def test_missing_model_file_still_logs_the_name(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        model = tmp_path / "ghost.gguf"  # never written
        wav = tmp_path / "in.wav"
        wav.write_bytes(b"x")
        joined = "\n".join(_format_run_config_lines(str(model), str(wav), ["exe"]))
        assert "[MODEL]" in joined
        assert "ghost.gguf" in joined


class TestBackendVerdict:
    def test_cpu_backends_are_detected(self):
        from core.transcribe.transcribe_cpp_engine import _backend_is_cpu

        assert _backend_is_cpu("CPU") is True
        assert _backend_is_cpu("cpu (fallback)") is True
        assert _backend_is_cpu("Vulkan") is False
        assert _backend_is_cpu("") is False

    def test_the_cpu_warning_names_vulkan(self):
        from core.transcribe.transcribe_cpp_engine import _CPU_BACKEND_WARNING

        assert "CPU" in _CPU_BACKEND_WARNING
        assert "Vulkan" in _CPU_BACKEND_WARNING

    def test_engine_wires_the_verdict_after_parse(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "_backend_is_cpu(" in fn_src
        assert "_CPU_BACKEND_WARNING" in fn_src

    def test_engine_logs_the_run_config_before_the_run(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "_format_run_config_lines(" in fn_src
        # the config (model/audio/cmd) must precede the actual run
        assert fn_src.index("_format_run_config_lines(") < fn_src.index("Popen(")

    def test_engine_passes_the_gpu_probe_interval(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "gpu_probe_interval_s=" in fn_src

    def test_stream_helper_gained_the_interval_kwarg(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "_stream_cli_output")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "gpu_probe_interval_s" in fn_src


# ═════════════════════════════════════════════════════════════════════════════
# D. pipeline_log -- the engine-aware silence hint
# ═════════════════════════════════════════════════════════════════════════════


class TestEngineAwareHint:
    def test_transcribe_cpp_hint_mentions_gpu_and_end_only_printing(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 3000.0
        line = format_heartbeat_line(
            run_started_ts=now - 300.0,
            last_update_ts=now - 200.0,
            now_ts=now,
            last_msg="Transcribing with transcribe.cpp (Vulkan GPU)...",
            engine="transcribe_cpp",
        )
        assert "engine silent" in line
        assert "GPU" in line
        # the operator-facing explanation: this CLI prints at the END
        assert "end" in line.lower() or "summary" in line.lower()

    def test_transcribe_cpp_hint_never_blames_a_missing_llm(self):
        # the triggering run was raw-transcript-only: hinting about an
        # LLM on CPU was actively misleading (the operator read "on CPU"
        # and concluded the whisper model was CPU-bound).
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 3000.0
        line = format_heartbeat_line(
            run_started_ts=now - 300.0,
            last_update_ts=now - 200.0,
            now_ts=now,
            last_msg="Transcribing...",
            engine="transcribe_cpp",
        )
        assert "LLM" not in line

    def test_the_llm_hint_survives_for_non_transcribe_engines(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 3000.0
        line = format_heartbeat_line(
            run_started_ts=now - 300.0,
            last_update_ts=now - 200.0,
            now_ts=now,
            last_msg="summarizing...",
            engine="faster_whisper",
        )
        assert "engine silent" in line
        assert "LLM" in line  # the V0.6.56 contract, unchanged

    def test_engine_kwarg_is_optional_backwards_compatible(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 3000.0
        line = format_heartbeat_line(
            run_started_ts=now - 300.0,
            last_update_ts=now - 200.0,
            now_ts=now,
            last_msg="summarizing...",
        )
        assert "engine silent" in line
        assert "LLM" in line

    def test_short_silence_still_has_no_hint(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 3000.0
        line = format_heartbeat_line(
            run_started_ts=now - 30.0,
            last_update_ts=now - 10.0,
            now_ts=now,
            last_msg="x",
            engine="transcribe_cpp",
        )
        assert "engine silent" not in line


# ═════════════════════════════════════════════════════════════════════════════
# E. DIALOG -- the engine reaches the heartbeat (AST pins)
# ═════════════════════════════════════════════════════════════════════════════


class TestDialogEngineWiring:
    def test_on_process_records_the_run_engine(self):
        fn = _method(_dialog_tree(), "_on_process")
        src = ast.unparse(fn)
        assert "self._run_engine" in src
        # stored BEFORE the worker exists (the heartbeat needs it 15s in)
        assert src.index("self._run_engine") < src.index("SimpleWorker(")

    def test_heartbeat_passes_the_engine_to_the_hint(self):
        fn = _method(_dialog_tree(), "_on_heartbeat")
        src = ast.unparse(fn)
        assert "engine=" in src
        assert "self._run_engine" in src
        # the V0.6.56 contracts survive untouched
        assert "format_heartbeat_line(" in src
        assert "_append_live_log(" in src
        assert "status_label" not in src
        assert "_worker_is_running(" in src
        assert "_heartbeat_timer.stop()" in src

    def test_init_seeds_the_run_engine(self):
        fn = _method(_dialog_tree(), "__init__")
        src = ast.unparse(fn)
        assert "self._run_engine" in src


# ═════════════════════════════════════════════════════════════════════════════
# F. the raw-transcript-only run header keeps its shape (regression guard)
# ═════════════════════════════════════════════════════════════════════════════


class TestHeaderRegression:
    def test_header_unchanged_for_cpp_runs(self):
        from core.transcribe.pipeline_log import format_run_header

        lines = format_run_header(
            filepath="C:/V/Obsidian.mp4",
            engine="transcribe.cpp (Vulkan GPU)",
            whisper_model=None,
            llm_model="whatever",
            save_raw=True,
            save_summary=False,
            save_tutorial=False,
        )
        joined = "\n".join(lines)
        assert "Obsidian.mp4" in joined
        assert "whatever" not in joined
