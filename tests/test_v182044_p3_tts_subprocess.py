"""V18.20.4.4 (P3) — TTS subprocess hardening: W-c2 / W-c11 / W-c8 + O-c2.

Hermetic characterization + behavioral tests for the TTS subprocess
lifecycle fixes and the new shared base:

* O-c2 — ``core/tts/_json_subprocess.py``: the shared
  ``PersistentJsonSubprocess`` base (Popen + stderr drain + stdout
  reader thread → queue). The reader thread is what makes read timeouts
  REAL: a blocking ``readline()`` on a *silent-but-alive* child never
  returns, so the old ``while time.time() - start < N`` loops only fired
  when lines kept arriving (the T-c6 wedge). The base is ported into
  qwen + vibevoice; neutts keeps its own battle-tested path.
* W-c2 — engine-ready timeout/load-error ORPHANS the subprocess (Popen
  handle dropped without terminate/kill → the still-loading model keeps
  holding VRAM; T-c1). Fix: kill-before-raise (the neutts
  cleanup-before-raise pattern) on every load-failure path.
* W-c11 — qwen per-chunk timeout left the subprocess mid-generation; the
  stale JSON response line was consumed by the NEXT command (protocol
  desync → mis-attributed cascade; T-c6). Fix: kill + reset on chunk
  timeout / dead stdout so the batch fails fast and the next
  ``synthesize()`` reloads a fresh, in-sync subprocess.
* W-c8 — piper ``subprocess.run`` had no timeout; a wedged piper.exe
  blocked the TTS thread indefinitely. Fix: ``PIPER_SYNTH_TIMEOUT_S``
  bound + TimeoutExpired → RuntimeError (fail-soft through
  ``TTSEngine.synthesize``).

Tests are pure-Python / hermetic: fake Popen objects (real reader
threads + queues, no real model/GPU/packages) + source pins on the
runtime files. No book-derived content (deny-list test enforces; all
names here are synthetic engine/bookkeeping strings).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

QWEN_SRC = (PROJECT_ROOT / "core" / "tts" / "qwen_tts_engine.py").read_text(encoding="utf-8")
VIBE_SRC = (PROJECT_ROOT / "core" / "tts" / "vibevoice_engine.py").read_text(encoding="utf-8")
ENGINE_SRC = (PROJECT_ROOT / "core" / "tts" / "engine.py").read_text(encoding="utf-8")
NEUTTS_SRC = (PROJECT_ROOT / "core" / "tts" / "neutts_engine.py").read_text(encoding="utf-8")
BASE_SRC = (PROJECT_ROOT / "core" / "tts" / "_json_subprocess.py").read_text(encoding="utf-8")


# ── Fake subprocess machinery (hermetic) ───────────────────────────────────


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[str] = []
        self.closed = False

    def write(self, data: str) -> int:
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        return None


class _FakeStdout:
    """Iterable stdout: the base's reader thread iterates this (never
    readline), yields the scripted lines, then ends (EOF)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _SilentStdout:
    """A silent-but-alive child's stdout: the iterator never yields —
    exactly the T-c6 wedge the old blocking-readline loops missed."""

    def __iter__(self):
        _evt = threading.Event()
        _evt.wait()  # never set — the (daemon) reader thread blocks here
        return iter(())


class _FakeStderr:
    def __iter__(self):
        return iter(())


class _FakeProc:
    """Stands in for subprocess.Popen. Records kill()/wait() calls."""

    def __init__(self, lines: list[str] | _SilentStdout) -> None:
        self.stdin = _FakeStdin()
        self.stdout = lines if isinstance(lines, _SilentStdout) else _FakeStdout(lines)
        self.stderr = _FakeStderr()
        self.killed = 0
        self.waits = 0
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def kill(self) -> None:
        self.killed += 1
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        self._alive = False
        return 0

    @property
    def returncode(self) -> int:
        return 0 if not self._alive else None  # type: ignore[return-value]


class _LogCollector:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def __call__(self, msg: str, level: str = "INFO") -> None:
        self.lines.append((msg, level))

    def joined(self) -> str:
        return "\n".join(msg for msg, _lvl in self.lines)


def _install_fake_popen(monkeypatch, procs: list[_FakeProc]):
    """Patch subprocess.Popen to hand out the given fakes in order."""
    calls: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return procs.pop(0)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return calls


def _spawned_sub(name: str, logs, proc: _FakeProc) -> object:
    """A real PersistentJsonSubprocess spawned onto a fake Popen."""
    from core.tts._json_subprocess import PersistentJsonSubprocess

    sub = PersistentJsonSubprocess(
        name=name, log=logs, stderr_prefix=f"[{name}]", stderr_level="DEBUG"
    )
    sub.spawn([sys.executable, "fake-script.py"], env={"PATH": ""})
    return sub


@pytest.fixture()
def qwen_engine(tmp_path):
    """A QwenTtsEngine whose model dir exists; Popen is faked per-test."""
    from core.tts.qwen_tts_engine import QwenTtsEngine

    model_dir = tmp_path / "qwen-model"
    model_dir.mkdir()
    logs = _LogCollector()
    engine = QwenTtsEngine(model_path=str(model_dir), log_callback=logs)
    return engine, logs


@pytest.fixture()
def vibe_engine(tmp_path):
    """A VibeVoiceEngine with a model path; Popen is faked per-test."""
    from core.tts.vibevoice_engine import VibeVoiceEngine

    logs = _LogCollector()
    engine = VibeVoiceEngine(model_path=str(tmp_path / "vibe-model"), log_callback=logs)
    return engine, logs


# ── Source pins (no line numbers — content + ordering contract) ────────────


class TestSourcePins:
    def test_o_c2_shared_base_exists_with_queue_reader(self):
        """O-c2: the shared base with the queue-based reader thread."""
        assert "class PersistentJsonSubprocess" in BASE_SRC
        assert "queue.Queue" in BASE_SRC
        assert "def read_json(self, timeout: float)" in BASE_SRC
        assert 'def kill(self, reason: str = "")' in BASE_SRC
        assert "def close(self" in BASE_SRC
        # Reader thread moves stdout lines into the queue — REAL timeouts.
        assert "self._lines.put(line)" in BASE_SRC
        assert "queue.Empty" in BASE_SRC
        # eof property distinguishes dead child from silent child.
        assert "def eof(self)" in BASE_SRC

    def test_o_c2_both_engines_use_the_base(self):
        for src in (QWEN_SRC, VIBE_SRC):
            assert "from core.tts._json_subprocess import " in src
            assert "PersistentJsonSubprocess(" in src
            assert ".spawn(" in src
            assert ".read_json(" in src
            assert ".send(" in src

    def test_o_c2_no_blocking_readline_left_in_the_engines(self):
        """The silent-child blindspot is structurally gone: neither
        ported engine reads the child's stdout directly anymore."""
        assert "self._proc.stdout.readline()" not in QWEN_SRC
        assert "self._proc.stdout.readline()" not in VIBE_SRC
        assert "self._proc" not in QWEN_SRC
        assert "self._proc" not in VIBE_SRC

    def test_timeout_constants_exist_unchanged(self):
        from core.tts.qwen_tts_engine import QWEN_CHUNK_TIMEOUT_S as q_chunk
        from core.tts.qwen_tts_engine import QWEN_LOAD_TIMEOUT_S as q_load
        from core.tts.vibevoice_engine import VIBEVOICE_LINE_TIMEOUT_S as v_line
        from core.tts.vibevoice_engine import VIBEVOICE_LOAD_TIMEOUT_S as v_load

        assert (q_load, q_chunk, v_load, v_line) == (120, 120, 300, 600)

    def test_w_c2_qwen_timeout_path_kills_before_raise(self):
        kill_idx = QWEN_SRC.find("model load not ready (timeout,")
        raise_idx = QWEN_SRC.find('"Qwen3-TTS subprocess failed to load model (timeout)"')
        assert kill_idx != -1, "qwen load-timeout must call _kill_subprocess"
        assert raise_idx != -1
        assert kill_idx < raise_idx, "kill must precede the raise (W-c2)"
        # The orphaning pattern `self._proc = None` right before the raise
        # must be GONE from the not-ready path.
        orphan = 'self._proc = None\n            raise RuntimeError("Qwen3-TTS'
        assert orphan not in QWEN_SRC

    def test_w_c2_qwen_load_error_path_kills_before_raise(self):
        kill_idx = QWEN_SRC.find('f"load error:')
        raise_idx = QWEN_SRC.find('"Model load failed: {')
        assert kill_idx != -1
        assert raise_idx != -1
        assert kill_idx < raise_idx

    def test_w_c2_vibevoice_timeout_path_kills_before_raise(self):
        kill_idx = VIBE_SRC.find("model load not ready (timeout,")
        raise_idx = VIBE_SRC.find('"VibeVoice subprocess failed to load model (timeout)"')
        assert kill_idx != -1, "vibevoice load-timeout must call _kill_subprocess"
        assert raise_idx != -1
        assert kill_idx < raise_idx

    def test_w_c2_vibevoice_load_error_path_kills_before_raise(self):
        kill_idx = VIBE_SRC.find('f"load error:')
        raise_idx = VIBE_SRC.find('"Model load failed: {')
        assert kill_idx != -1
        assert raise_idx != -1
        assert kill_idx < raise_idx

    def test_w_c11_qwen_chunk_timeout_kills(self):
        timeout_log = QWEN_SRC.find("s per chunk)")
        kill_idx = QWEN_SRC.find("chunk timeout ({QWEN_CHUNK_TIMEOUT_S}s per chunk)")
        assert timeout_log != -1
        assert kill_idx != -1, "chunk-timeout must call _kill_subprocess"
        assert timeout_log < kill_idx

    def test_w_c11_qwen_dead_stdout_reaps_handle(self):
        closed_log = QWEN_SRC.find('"  ❌ Subprocess closed unexpectedly"')
        kill_idx = QWEN_SRC.find('"stdout closed mid-generation"')
        assert closed_log != -1
        assert kill_idx != -1
        assert closed_log < kill_idx

    def test_qwen_kill_subprocess_resets_both_markers(self):
        assert 'def _kill_subprocess(self, reason: str = "")' in QWEN_SRC
        method = QWEN_SRC[QWEN_SRC.find("def _kill_subprocess") :]
        method = method[: method.find("def _cleanup")]
        assert "sub.kill(reason)" in method
        assert "self._sub = None" in method
        assert "self._model = None" in method

    def test_w_c8_piper_timeout_in_kwargs(self):
        """W-c8: piper subprocess.run call carries a timeout bound."""
        assert "PIPER_SYNTH_TIMEOUT_S = 120" in ENGINE_SRC
        kw_idx = ENGINE_SRC.find('"timeout": PIPER_SYNTH_TIMEOUT_S')
        run_idx = ENGINE_SRC.find("proc = subprocess.run(cmd, **kwargs)")
        assert kw_idx != -1, "piper kwargs must include the timeout"
        assert run_idx != -1
        assert kw_idx < run_idx, "timeout must be set before the run call"

    def test_w_c8_piper_timeout_expired_converted(self):
        # V0.13 (B904 fix): the handler now captures the exception
        # (`as e`) so the RuntimeError chains with `from e`.
        assert "except subprocess.TimeoutExpired as e:" in ENGINE_SRC
        assert "Piper timed out after" in ENGINE_SRC

    def test_neutts_deliberately_not_ported(self):
        """Scope note: neutts keeps its own battle-tested path (its
        in-process mode is primary; its subprocess mode already has the
        cleanup contract)."""
        assert "_json_subprocess" not in NEUTTS_SRC
        assert "def _cleanup_process" in NEUTTS_SRC
        # The neutts load-failure cleanup-before-raise reference remains.
        ensure = NEUTTS_SRC[NEUTTS_SRC.find("def _ensure_process") :]
        ensure = ensure[: ensure.find("def _cleanup_process")]
        assert "self._cleanup_process()" in ensure

    def test_vibevoice_line_timeout_kill_unchanged_shape(self):
        """V11.55/V11.57 vibevoice per-line timeout kill remains, now via
        the shared base with a REAL timeout."""
        assert 'f"timeout ({VIBEVOICE_LINE_TIMEOUT_S}s)"' in VIBE_SRC
        assert "VibeVoice subprocess timed out (600s)" in VIBE_SRC


# ── Behavioral: the shared base itself (O-c2) ───────────────────────────────


class TestJsonSubprocessBase:
    def _sub(self, logs, proc):
        from core.tts._json_subprocess import PersistentJsonSubprocess

        sub = PersistentJsonSubprocess(
            name="base-test", log=logs, stderr_prefix="[t]", stderr_level="DEBUG"
        )
        sub.spawn([sys.executable, "x.py"], env={"PATH": ""})
        return sub

    def test_send_writes_json_line(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc([])
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        assert sub.send({"action": "load"}) is True
        assert proc.stdin.written == ['{"action": "load"}\n']

    def test_read_json_yields_scripted_json_and_skips_noise(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc(
            [
                "noise from some library\n",
                json.dumps({"status": "loading", "device": "cpu"}) + "\n",
            ]
        )
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        msg = sub.read_json(timeout=2.0)
        assert msg == {"status": "loading", "device": "cpu"}

    def test_read_line_real_timeout_on_silent_child(self, monkeypatch):
        """THE T-c6 wedge: silent-but-alive child → read_line must return
        None after the timeout, NOT block forever (old readline hung)."""
        logs = _LogCollector()
        proc = _FakeProc(_SilentStdout())
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        t0 = time.monotonic()
        assert sub.read_line(timeout=0.2) is None
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, "read_line must honor the timeout"
        assert sub.alive, "the child is silent, not dead"

    def test_eof_delivered_then_immediate_none(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc([json.dumps({"status": "ready"}) + "\n"])
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        assert sub.read_json(timeout=2.0) == {"status": "ready"}
        # Lines exhausted → EOF → immediate None (no timeout wait).
        t0 = time.monotonic()
        assert sub.read_json(timeout=5.0) is None
        assert time.monotonic() - t0 < 1.0
        assert sub.eof is True

    def test_kill_is_immediate_and_idempotent(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc(_SilentStdout())
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        sub.kill("wedged")
        assert proc.killed == 1
        assert proc.waits >= 1
        assert sub.alive is False
        assert "🔧 Killing base-test subprocess (reason: wedged" in logs.joined()
        # Idempotent: second kill is a no-op (no crash, no double kill).
        sub.kill("again")
        assert proc.killed == 1
        # After kill: send fail-soft, read fail-soft.
        assert sub.send({"action": "quit"}) is False
        assert sub.read_json(timeout=0.1) is None

    def test_close_sends_quit_then_waits(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc(_SilentStdout())
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        sub.close()
        assert any("quit" in w for w in proc.stdin.written)
        assert proc.waits >= 1
        assert sub.alive is False

    def test_send_fails_soft_on_dead_child(self, monkeypatch):
        logs = _LogCollector()
        proc = _FakeProc([])
        proc._alive = False  # already exited
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = self._sub(logs, proc)

        assert sub.send({"action": "load"}) is False
        assert "not running" in logs.joined()


# ── Behavioral: W-c2 (qwen) ─────────────────────────────────────────────────


class TestQwenWc2:
    def test_load_eof_kills_subprocess(self, qwen_engine, monkeypatch):
        """Child closes stdout before ready → RuntimeError AND the proc
        is killed (the old code dropped the handle — W-c2)."""
        engine, logs = qwen_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "loading", "device": "cpu"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError, match="failed to load model"):
            engine._ensure_model()

        assert proc.killed == 1, "orphaned subprocess must be killed (W-c2)"
        assert proc.waits >= 1
        assert engine._sub is None
        assert engine._model is None
        assert "Killing Qwen3-TTS subprocess" in logs.joined()

    def test_load_silent_child_real_timeout_kills(self, qwen_engine, monkeypatch):
        """THE T-c6-class wedge at LOAD time: child alive but silent —
        the old blocking-readline handshake would hang FOREVER."""
        import core.tts.qwen_tts_engine as qmod

        engine, logs = qwen_engine
        proc = _FakeProc(_SilentStdout())
        _install_fake_popen(monkeypatch, [proc])
        monkeypatch.setattr(qmod, "QWEN_LOAD_TIMEOUT_S", 0.2)

        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match="failed to load model"):
            engine._ensure_model()
        assert time.monotonic() - t0 < 5.0, "the load timeout must be REAL"

        assert proc.killed == 1
        assert engine._sub is None
        assert "model load not ready (timeout" in logs.joined()

    def test_load_error_status_kills_subprocess(self, qwen_engine, monkeypatch):
        engine, logs = qwen_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "error", "error": "OOM on load"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError, match="Model load failed: OOM"):
            engine._ensure_model()

        assert proc.killed == 1, "load-error must not leave the subprocess holding VRAM (W-c2)"
        assert engine._sub is None

    def test_ready_load_is_unchanged(self, qwen_engine, monkeypatch):
        """Golden path: ready handshake still works, no kill."""
        engine, logs = qwen_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "loading", "device": "cuda"}),
                json.dumps({"status": "ready", "device": "cuda", "speakers": ["Vivian", "Ryan"]}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert engine._model is True
        assert proc.killed == 0
        assert proc.stdin.written and "load" in proc.stdin.written[0]
        assert "Qwen3-TTS ready on cuda" in logs.joined()


# ── Behavioral: W-c11 (qwen) ────────────────────────────────────────────────


class TestQwenWc11:
    def _armed_engine(self, qwen_engine, monkeypatch, proc):
        """Engine with a 'loaded' live sub spawned onto the fake proc."""
        engine, logs = qwen_engine
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        sub = _spawned_sub("Qwen3-TTS", logs, proc)
        engine._sub = sub
        engine._model = True
        return engine, logs, sub

    def test_chunk_timeout_on_silent_child_kills_and_resets(self, qwen_engine, monkeypatch):
        """THE T-c6 wedge at GENERATE time: silent-but-alive child → the
        per-chunk timeout must actually FIRE (the old blocking readline
        hung forever), then kill + reset (W-c11 protocol resync)."""
        import core.tts.qwen_tts_engine as qmod

        proc = _FakeProc(_SilentStdout())
        engine, logs, _sub = self._armed_engine(qwen_engine, monkeypatch, proc)
        monkeypatch.setattr(qmod, "QWEN_CHUNK_TIMEOUT_S", 0.2)

        t0 = time.monotonic()
        result = engine._run_subprocess("hello", "Vivian", "out.wav")
        assert time.monotonic() - t0 < 5.0, "the chunk timeout must be REAL"
        assert result is False
        assert proc.killed == 1, "timed-out chunk must kill (W-c11)"
        assert engine._sub is None, "kill must reset the engine (W-c11)"
        assert engine._model is None, "loaded marker must reset so the next synthesize reloads"
        assert "timed out" in logs.joined()
        assert "chunk timeout" in logs.joined()

    def test_dead_stdout_reaps_and_resets(self, qwen_engine, monkeypatch):
        """stdout EOF mid-generation → kill + reset (not a bricked engine)."""
        engine, logs, _sub = self._armed_engine(qwen_engine, monkeypatch, _FakeProc([]))

        result = engine._run_subprocess("hello", "Vivian", "out.wav")
        assert result is False
        assert "closed unexpectedly" in logs.joined()
        assert "stdout closed mid-generation" in logs.joined()
        assert engine._sub is None
        assert engine._model is None

    def test_next_ensure_reloads_fresh_subprocess(self, qwen_engine, monkeypatch):
        """After a dead-stdout kill, _ensure_model starts a FRESH proc
        (recovery contract — the engine is not permanently bricked)."""
        import core.tts.qwen_tts_engine as qmod  # noqa: F401

        engine, logs = qwen_engine
        dead = _FakeProc([])
        fresh = _FakeProc(
            [
                json.dumps({"status": "ready", "device": "cuda", "speakers": []}),
            ]
        )
        calls = _install_fake_popen(monkeypatch, [dead, fresh])
        engine._sub = _spawned_sub("Qwen3-TTS", logs, dead)
        engine._model = True

        assert engine._run_subprocess("x", "Vivian", "o.wav") is False
        assert engine._model is None
        assert dead.killed == 1

        # Next call: fresh load handshake succeeds on the NEW proc.
        engine._ensure_model()
        assert engine._model is True
        assert len(calls) == 2, "one spawn for the armed sub + one reload"
        assert fresh.killed == 0

    def test_error_response_keeps_protocol_running(self, qwen_engine, monkeypatch):
        """A reported generation error is a terminal response to OUR
        command — protocol stays in sync, so NO kill (bounded change)."""
        engine, logs, _sub = self._armed_engine(
            qwen_engine,
            monkeypatch,
            _FakeProc([json.dumps({"status": "error", "error": "bad chunk"})]),
        )

        result = engine._run_subprocess("hello", "Vivian", "out.wav")
        assert result is False
        assert "Generation error: bad chunk" in logs.joined()
        assert engine._sub is not None, "synced error responses must not kill"
        assert engine._model is True

    def test_not_running_when_sub_is_none(self, qwen_engine):
        engine, logs = qwen_engine
        result = engine._run_subprocess("hello", "Vivian", "out.wav")
        assert result is False
        assert "Subprocess not running" in logs.joined()


# ── Behavioral: W-c2 (vibevoice) ────────────────────────────────────────────


class TestVibeVoiceWc2:
    def test_load_eof_kills_subprocess(self, vibe_engine, monkeypatch):
        engine, logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "loading", "device": "cpu"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError, match="failed to load model"):
            engine._ensure_model()

        assert proc.killed == 1, "300s timeout must kill the still-loading 2.6 GB model (W-c2)"
        assert engine._sub is None
        assert engine._loaded is False
        assert "Killing VibeVoice subprocess" in logs.joined()

    def test_load_silent_child_real_timeout_kills(self, vibe_engine, monkeypatch):
        import core.tts.vibevoice_engine as vmod

        engine, logs = vibe_engine
        proc = _FakeProc(_SilentStdout())
        _install_fake_popen(monkeypatch, [proc])
        monkeypatch.setattr(vmod, "VIBEVOICE_LOAD_TIMEOUT_S", 0.2)

        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match="failed to load model"):
            engine._ensure_model()
        assert time.monotonic() - t0 < 5.0, "the load timeout must be REAL"
        assert proc.killed == 1
        assert "model load not ready (timeout" in logs.joined()

    def test_load_error_status_kills_subprocess(self, vibe_engine, monkeypatch):
        engine, _logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "error", "error": "CUDA init failed"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError, match="Model load failed"):
            engine._ensure_model()

        assert proc.killed == 1
        assert engine._sub is None

    def test_ready_load_is_unchanged(self, vibe_engine, monkeypatch):
        engine, _logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "ready", "device": "cuda"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert engine._loaded is True
        assert proc.killed == 0
        assert engine.get_device() == "cuda"

    def test_line_timeout_on_silent_child_kills_and_raises(
        self, vibe_engine, monkeypatch, tmp_path
    ):
        """The 600s per-line timeout must be REAL (silent child), then
        kill + raise per the V11.57 no-restart policy."""
        import core.tts.vibevoice_engine as vmod

        engine, logs = vibe_engine
        proc = _FakeProc(_SilentStdout())
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        engine._sub = _spawned_sub("VibeVoice", logs, proc)
        engine._loaded = True
        monkeypatch.setattr(vmod, "VIBEVOICE_LINE_TIMEOUT_S", 0.3)

        out = tmp_path / "line.wav"
        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match="timed out"):
            engine.synthesize("hello line", out, voice="en-Carter_man")
        assert time.monotonic() - t0 < 5.0, "the line timeout must be REAL"
        assert proc.killed == 1
        assert engine._sub is None
        assert engine._loaded is False

    def test_line_ok_golden_path_unchanged(self, vibe_engine, monkeypatch, tmp_path):
        engine, logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "ok", "duration": 12}),
            ]
        )
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)
        engine._sub = _spawned_sub("VibeVoice", logs, proc)
        engine._loaded = True

        out = tmp_path / "ok.wav"
        out.write_bytes(b"WAV" * 64)
        result = engine.synthesize("hello line", out, voice="en-Carter_man")
        assert result == out
        assert proc.killed == 0
        assert "VibeVoice complete: 12s audio" in logs.joined()
        assert "Verified: ok.wav" in logs.joined()


# ── Behavioral: W-c8 (piper) ───────────────────────────────────────────────


class TestPiperWc8:
    def _engine(self, tmp_path):
        from core.tts.engine import PiperEngine

        binary = tmp_path / "piper.exe"
        binary.write_bytes(b"fake")
        logs = _LogCollector()
        return PiperEngine(binary_path=binary, voices_dir=tmp_path, log_callback=logs)

    def test_timeout_kwarg_is_passed(self, tmp_path, monkeypatch):
        engine = self._engine(tmp_path)
        monkeypatch.setattr(engine, "_ensure_voice", lambda voice: tmp_path / "v.onnx")

        captured: dict = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="timed out after 120s"):
            engine._synthesize("سلام", tmp_path / "out.wav", "fa_FA", 1.0)
        assert captured.get("timeout") == 120, "piper subprocess.run must be bounded (W-c8)"

    def test_timeout_is_fail_soft_through_synthesize(self, tmp_path, monkeypatch):
        """The house fail-soft contract: synthesize() returns None and
        records last_error (the TTS thread never sees a raw exception)."""
        engine = self._engine(tmp_path)
        monkeypatch.setattr(engine, "_ensure_voice", lambda voice: tmp_path / "v.onnx")

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = engine.synthesize("سلام", tmp_path / "out.wav", "fa_FA", 1.0)
        assert result is None
        assert engine.last_error and "timed out" in engine.last_error

    def test_successful_run_is_unchanged(self, tmp_path, monkeypatch):
        engine = self._engine(tmp_path)
        monkeypatch.setattr(engine, "_ensure_voice", lambda voice: tmp_path / "v.onnx")
        out = tmp_path / "out.wav"
        # Write a >44-byte "wav" so the base-class size check passes.
        out.write_bytes(b"WAV" * 64)

        class _FakeCompleted:
            returncode = 0
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: _FakeCompleted())
        result = engine.synthesize("سلام", out, "fa_FA", 1.0)
        assert result == out
        assert engine.last_error is None

    def test_piper_timeout_constant_value(self):
        from core.tts.engine import PIPER_SYNTH_TIMEOUT_S

        assert PIPER_SYNTH_TIMEOUT_S == 120
