"""V0.6.56 — the Transcribe Service live-log pins (the 10-minute freeze).

WHY THIS FILE EXISTS
--------------------
The operator ran a real video through the tool and waited 10 minutes
with NO idea whether it was frozen or progressing. Root causes (both
fixed by V0.6.56):

  1. DIALOG: BaseServiceDialog already ships a live-log panel
     (``_log_toggle_btn`` + ``live_log`` — the internal log container
     every other tool uses), but the transcribe dialog HID the toggle
     and its ``_on_progress`` override dropped every message on the
     floor (only the one-line status label survived).
  2. ENGINE: ``transcribe_with_cpp`` ran the whisper CLI via
     ``subprocess.run(capture_output=True)`` — the ENTIRE transcription
     completes with stdout trapped in memory. Between ``progress(20)``
     and ``progress(100)`` the pipeline is completely silent, which is
     exactly the 10-minute freeze the operator saw.

WHAT V0.6.56 PINS
-----------------
A. ENGINE (dynamic, Qt-free — real fake-process drives):
   - ``_stream_cli_output`` streams the CLI stdout/stderr LINE BY LINE
     to ``log_callback`` (each transcribed line is visible as it
     happens), collapses ``\\r`` spinner frames, maps percent lines to
     ``progress_callback`` (20..90), returns the ACCUMULATED text
     byte-faithfully (the P6 parser's input is unchanged), kills on
     deadline, and never kills on a normal exit.
   - ``transcribe_with_cpp`` no longer uses ``subprocess.run`` for the
     CLI call — Popen + the streaming helper (timeout error string
     contract preserved verbatim).
B. pipeline_log (dynamic, Qt-free): the heartbeat line format (elapsed
   + gap-since-last-update + a silence hint when the gap is large) and
   the run-header lines (file / engine / model / outputs).
C. DIALOG (AST pins — no PySide6 in this sandbox, the V0.6.54/V0.6.55
   source-pin precedent): the toggle is no longer hidden, every
   progress message lands in the log, the log auto-opens + clears on
   run start with a header, a 15s heartbeat timer answers "frozen or
   progressing?" while the run is alive, and the timer stops on every
   completion path.
"""

from __future__ import annotations

import ast
import io
import subprocess
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_ENGINE = _project_root / "core" / "transcribe" / "transcribe_cpp_engine.py"
_PIPELOG = _project_root / "core" / "transcribe" / "pipeline_log.py"


@pytest.fixture(scope="module")
def tree() -> ast.Module:
    return _dialog_tree()


_DIALOG_TREE_CACHE: dict[str, ast.Module] = {}


def _dialog_tree() -> ast.Module:
    """Parse the dialog source once (pytest 9 forbids calling fixtures
    directly, so the Part-C pins use this plain helper)."""
    if "t" not in _DIALOG_TREE_CACHE:
        _DIALOG_TREE_CACHE["t"] = ast.parse(
            _DIALOG.read_text(encoding="utf-8"), filename=str(_DIALOG)
        )
    return _DIALOG_TREE_CACHE["t"]


def _method(t: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(t):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    pytest.fail(f"method {name} not found in the dialog source")


def _first_line_with(src: str, needle: str) -> int:
    for i, line in enumerate(src.splitlines(), 1):
        if needle in line:
            return i
    pytest.fail(f"{needle!r} not found in source")


# ═════════════════════════════════════════════════════════════════════════════
# A. ENGINE — the streaming seam (dynamic; a fake Popen-ish process)
# ═════════════════════════════════════════════════════════════════════════════


class _FakeProc:
    """The Popen surface _stream_cli_output touches: stdout/stderr binary
    streams, wait(timeout=), kill(), returncode.

    ``hangs`` simulates a live process: wait(timeout=...) raises
    TimeoutExpired (the poll loop keeps polling) until kill() is called.
    """

    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0, *, hangs: bool = False):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.killed = False
        self.hangs = hangs

    def wait(self, timeout=None):  # noqa: ARG002 — Popen signature
        if self.hangs and timeout is not None and not self.killed:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def _stream(proc: _FakeProc, deadline_ts=None):
    from core.transcribe.transcribe_cpp_engine import _stream_cli_output

    echoed: list[str] = []
    progressed: list[tuple[int, str]] = []
    out, err, code, timed_out = _stream_cli_output(
        proc,
        log=lambda msg, level="INFO": echoed.append(msg),
        progress=lambda pct, msg: progressed.append((pct, msg)),
        deadline_ts=deadline_ts,
    )
    return out, err, code, timed_out, echoed, progressed


class TestStreamCliOutput:
    def test_helper_exists_and_streams_stdout_lines(self):
        stdout = b"backend: Vulkan\nsystem_info: n_threads = 8\ntext: Hello world\n"
        out, err, code, timed_out, echoed, _ = _stream(_FakeProc(stdout))
        assert code == 0 and not timed_out
        joined = "\n".join(echoed)
        assert "text: Hello world" in joined
        assert "backend: Vulkan" in joined

    def test_every_stdout_line_is_visible_as_it_arrives(self):
        # The operator's core complaint: transcribed lines must APPEAR
        # while the CLI works, not after it exits.
        stdout = b"".join(f"text: line {i}\n".encode() for i in range(5))
        _, _, _, _, echoed, _ = _stream(_FakeProc(stdout))
        assert sum("text: line" in e for e in echoed) == 5

    def test_stderr_lines_are_streamed_too(self):
        proc = _FakeProc(b"text: hi\n", stderr=b"whisper_init_state: loading model\n")
        _, _, _, _, echoed, _ = _stream(proc)
        assert any("whisper_init_state" in e for e in echoed)

    def test_carriage_return_spinner_collapses_to_the_latest_frame(self):
        # spinners write "10%\r15%\r20%\n" — one readline blob; the log
        # must show the LATEST frame, not the intermediate junk.
        stdout = b"### 10%\r### 15%\r### 20%\ntext: done\n"
        _, _, _, _, echoed, _ = _stream(_FakeProc(stdout))
        joined = "\n".join(echoed)
        assert "### 20%" in joined
        assert "### 15%\r" not in joined

    def test_percent_lines_map_to_progress_between_20_and_90(self):
        stdout = b"### 0%\n### 50%\n### 100%\n"
        _, _, _, _, _, progressed = _stream(_FakeProc(stdout))
        pcts = sorted(p for p, _ in progressed)
        assert 20 in pcts
        assert 55 in pcts          # 20 + int(50 * 0.7)
        assert 90 in pcts          # 20 + int(100 * 0.7)
        assert all(20 <= p <= 90 for p, _ in progressed)

    def test_progress_callback_percent_lines_map_too(self):
        # whisper.cpp-style callbacks: "... progress = 10%"
        stdout = b"whisper_print_progress_callback: progress = 10%\n"
        _, _, _, _, _, progressed = _stream(_FakeProc(stdout))
        assert [p for p, _ in progressed] == [27]  # 20 + int(10 * 0.7)

    def test_transcript_text_percentages_do_not_move_the_bar(self):
        # Task 14 review SHOULD-FIX 1: "text: I am 100% sure" contains a
        # percent but is TRANSCRIPT, not progress — the old naive regex
        # moved the bar BACKWARD (48 -> 90 -> 55) on such lines.
        stdout = b"### 40%\ntext: I am 100% sure it works\n### 50%\n"
        _, _, _, _, _, progressed = _stream(_FakeProc(stdout))
        assert [p for p, _ in progressed] == [48, 55]
        # and the transcript line is still ECHOED (visible progress)
        _, _, _, _, echoed, _ = _stream(_FakeProc(stdout))
        assert any("100% sure" in e for e in echoed)

    def test_repeated_identical_percent_lines_do_not_flood_the_log(self):
        stdout = b"### 50%\n### 50%\n### 50%\ntext: x\n"
        _, _, _, _, echoed, _ = _stream(_FakeProc(stdout))
        assert sum("### 50%" in e for e in echoed) == 1

    def test_accumulated_text_is_byte_faithful_for_the_parser(self):
        # The P6 parser's INPUT must be identical to what the old
        # capture_output=True produced — \r frames and all.
        stdout = b"### 10%\r### 20%\ntext: Hello\n[00:01.000 --> 00:02.000] Hi\n"
        out, err, _, _, _, _ = _stream(_FakeProc(stdout, stderr=b"noise\n"))
        assert out == stdout.decode()
        assert err == "noise\n"

    def test_normal_exit_never_kills_the_process(self):
        proc = _FakeProc(b"text: ok\n")
        _stream(proc)
        assert proc.killed is False

    def test_deadline_expiry_kills_and_flags_timeout(self):
        proc = _FakeProc(b"text: slow\n", hangs=True)
        # MONOTONIC deadline (time.monotonic() — the engine passes
        # monotonic; an already-expired monotonic deadline trips the kill
        # on the first poll).
        _, _, code, timed_out, _, _ = _stream(proc, deadline_ts=time.monotonic() - 1)
        assert timed_out is True
        assert proc.killed is True

    def test_echo_prefix_marks_whisper_provenance(self):
        # In a log shared with [LLM]/[CONVERT]/ffmpeg lines, CLI lines
        # need their own provenance marker.
        _, _, _, _, echoed, _ = _stream(_FakeProc(b"text: hi\n"))
        assert any("[whisper]" in e for e in echoed)


class TestEngineWiring:
    def test_transcribe_with_cpp_uses_popen_and_the_stream_helper(self):
        src = _ENGINE.read_text(encoding="utf-8")
        fn = _method(ast.parse(src), "transcribe_with_cpp")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "Popen(" in fn_src, "the CLI must run via Popen (streamable)"
        assert "_stream_cli_output(" in fn_src, "the CLI run must stream line-by-line"
        # CALL-node level (comments can legitimately mention the old
        # subprocess.run — the ban is on the CALL itself):
        run_calls = [
            c
            for c in ast.walk(fn)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "run"
            and isinstance(c.func.value, ast.Name)
            and c.func.value.id == "subprocess"
        ]
        assert not run_calls, (
            "capture_output=True traps stdout for the whole run — the "
            "10-minute silent freeze"
        )

    def test_timeout_error_string_contract_survives(self):
        src = _ENGINE.read_text(encoding="utf-8")
        assert "transcribe-cli.exe timed out" in src


# ═════════════════════════════════════════════════════════════════════════════
# B. pipeline_log — the heartbeat + run-header formats (dynamic, Qt-free)
# ═════════════════════════════════════════════════════════════════════════════


class TestHeartbeatLine:
    def test_line_carries_elapsed_gap_and_last_message(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 1000.0
        line = format_heartbeat_line(
            run_started_ts=now - 195.0,  # 3m15s in
            last_update_ts=now - 45.0,   # 45s silent
            now_ts=now,
            last_msg="🎙️ Transcribing with transcribe.cpp (Vulkan GPU)...",
        )
        assert line.startswith("⏱")
        assert "03:15" in line
        assert "45s" in line
        assert "transcribe.cpp" in line

    def test_long_silence_appends_the_engine_hint(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 2000.0
        line = format_heartbeat_line(
            run_started_ts=now - 600.0,
            last_update_ts=now - 300.0,  # 5 minutes silent
            now_ts=now,
            last_msg="loading model",
        )
        assert "model load" in line.lower() or "cpu" in line.lower()

    def test_short_silence_has_no_hint(self):
        from core.transcribe.pipeline_log import format_heartbeat_line

        now = 2000.0
        line = format_heartbeat_line(
            run_started_ts=now - 30.0, last_update_ts=now - 10.0, now_ts=now, last_msg="x"
        )
        # the real no-hint contract (the old assert was tautological —
        # Task 14 review): 10s of silence is normal pipeline cadence,
        # never the "engine silent" triage hint
        assert "engine silent" not in line
        assert "kill + retry" not in line
        assert line.count("⏱") == 1


class TestRunHeader:
    def test_header_lists_file_engine_model_and_outputs(self):
        from core.transcribe.pipeline_log import format_run_header

        lines = format_run_header(
            filepath="C:/Videos/meeting.mp4",
            engine="transcribe.cpp (Vulkan GPU)",
            whisper_model=None,
            llm_model="Ternary-Bonsai-2-27B",
            save_raw=True,
            save_summary=True,
            save_tutorial=True,
        )
        joined = "\n".join(lines)
        assert "meeting.mp4" in joined
        assert "transcribe.cpp" in joined
        assert "Ternary-Bonsai" in joined
        # all three outputs named
        assert "raw" in joined.lower()
        assert "summary" in joined.lower()
        assert "tutorial" in joined.lower()

    def test_header_omits_llm_line_when_no_llm_outputs(self):
        from core.transcribe.pipeline_log import format_run_header

        lines = format_run_header(
            filepath="/tmp/a.wav",
            engine="faster-whisper (CTranslate2)",
            whisper_model="small",
            llm_model="whatever",
            save_raw=True,
            save_summary=False,
            save_tutorial=False,
        )
        joined = "\n".join(lines)
        assert "whatever" not in joined
        assert "small" in joined

    def test_header_reports_the_file_size_when_statable(self, tmp_path):
        from core.transcribe.pipeline_log import format_run_header

        f = tmp_path / "clip.mp4"
        f.write_bytes(b"x" * 2048)
        lines = format_run_header(
            filepath=str(f),
            engine="e",
            whisper_model=None,
            llm_model=None,
            save_raw=True,
            save_summary=False,
            save_tutorial=False,
        )
        joined = "\n".join(lines)
        assert "2.0 KB" in joined or "2.0" in joined


# ═════════════════════════════════════════════════════════════════════════════
# C. DIALOG — the live-log container wiring (AST pins, the house precedent)
# ═════════════════════════════════════════════════════════════════════════════


class TestDialogLiveLog:
    def test_the_dead_toggle_is_no_longer_hidden(self):
        src = _DIALOG.read_text(encoding="utf-8")
        assert "_log_toggle_btn.setVisible(False)" not in src, (
            "the live-log toggle was hidden as 'dead' — V0.6.56 makes it "
            "the tool's internal log container"
        )

    def test_on_progress_appends_every_message_to_the_log(self):
        fn = _method(_dialog_tree(), "_on_progress")
        src = ast.unparse(fn)
        assert "_append_live_log(" in src
        # the pinned plain-status contract survives (e2e drive tests)
        assert "self.status_label.setText(msg)" in src
        # the heartbeat gap clock resets on every real update
        assert "_last_update_ts" in src

    def test_on_process_clears_and_auto_opens_the_log(self):
        fn = _method(_dialog_tree(), "_on_process")
        src = ast.unparse(fn)
        assert "self.live_log.clear()" in src
        assert "_toggle_live_log(True)" in src

    def test_on_process_logs_a_run_header(self):
        fn = _method(_dialog_tree(), "_on_process")
        src = ast.unparse(fn)
        assert "format_run_header(" in src
        assert "_append_live_log(" in src

    def test_the_heartbeat_timer_starts_before_the_worker_spawns(self):
        fn = _method(_dialog_tree(), "_on_process")
        src = ast.unparse(fn)
        assert "_heartbeat_timer.start()" in src
        # ordering: timer running BEFORE the worker exists (the header +
        # heartbeat must cover the whole worker lifetime)
        assert src.index("_heartbeat_timer.start()") < src.index("SimpleWorker(")

    def test_init_creates_the_heartbeat_timer_with_an_interval(self):
        fn = _method(_dialog_tree(), "__init__")
        src = ast.unparse(fn)
        assert "QTimer(" in src
        assert "setInterval(" in src
        assert "_heartbeat_timer" in src


class TestHeartbeat:
    def test_the_heartbeat_handler_exists_and_logs_only_to_the_log(self):
        fn = _method(_dialog_tree(), "_on_heartbeat")
        src = ast.unparse(fn)
        assert "format_heartbeat_line(" in src
        assert "_append_live_log(" in src
        # the pinned plain-status contract: heartbeats never touch the
        # status label (they are diagnostic, not pipeline state)
        assert "status_label" not in src

    def test_the_heartbeat_stops_when_the_worker_is_gone(self):
        fn = _method(_dialog_tree(), "_on_heartbeat")
        src = ast.unparse(fn)
        # Task 14 review BLOCKER fix: SimpleWorker is a BaseWorker=QObject
        # (is_running()), NOT a QThread (isRunning()) — the house
        # _worker_is_running helper normalizes both; calling isRunning()
        # crashed 15s into every run and this pin now bans it forever.
        assert "_worker_is_running(" in src
        assert "isRunning()" not in src
        assert "_heartbeat_timer.stop()" in src

    def test_the_timer_stops_on_every_completion_path(self):
        done = ast.unparse(_method(_dialog_tree(), "_on_done"))
        failed = ast.unparse(_method(_dialog_tree(), "_on_failed"))
        assert "_heartbeat_timer.stop()" in done
        assert "_heartbeat_timer.stop()" in failed


class TestLlmTestLogging:
    def test_the_test_verdict_lands_in_the_log_too(self):
        fn = _method(_dialog_tree(), "_on_test_llm_done")
        src = ast.unparse(fn)
        assert "_append_live_log(" in src
