"""V18.20.4.4 (P3 / O-c2 + W-c2 + W-c11): shared hardening base for TTS
JSON-protocol subprocesses.

The V18.20.4.0 SWOT flagged the trio of persistent TTS engines
(``qwen_tts_engine.py``, ``vibevoice_engine.py``, ``neutts_engine.py``)
as ~300 duplicated Popen + drain-thread + JSON-handshake + quit lines
(W-c10) — and the drift was already live: neutts cleans its subprocess
up on failure, qwen/vibevoice leaked it with the VRAM still locked
(W-c2), and qwen's per-chunk timeout desynchronized the JSON protocol
because ``readline()`` on a *silent but alive* child blocks forever, so
the old ``while time.time() - start < N`` loops only fired when lines
kept arriving (W-c11 / T-c6).

This module writes the neutts cleanup pattern (quit → wait → escalate
to kill) ONCE, and fixes the silent-child blindspot structurally: a
background reader thread moves every stdout line into a
``queue.Queue``, so ``read_line(timeout=…)`` is a REAL timeout —
``queue.get`` — never a blocking ``readline()``.

Scope note: V18.20.4.4 ports qwen + vibevoice onto this base (the two
engines with live W-c2 defects). ``neutts_engine`` keeps its own
battle-tested path — its in-process mode is the primary path and its
opt-in subprocess mode already implements the cleanup contract; a
neutts port is a P5-class decomposition, not a bug fix.

Protocol contract (both ported engines):
  * parent writes one JSON object per line to stdin
    (``{"action": "load" | "generate" | "quit", …}``)
  * child answers one JSON object per line on stdout
    (``{"status": "loading" | "ready" | "generating" | "ok" | "error", …}``)
  * stderr is drained continuously by a daemon thread and logged
    (never allowed to fill the ~64 KB pipe buffer — the V11.32.0 lesson)
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]

# Sentinel pushed by the reader thread at stdout EOF. After it is
# consumed, read_line() returns None immediately (no timeout wait).
_EOF = object()

# Default graceful-quit wait before the kill escalation (neutts pattern).
_QUIT_WAIT_S = 5.0
# Default kill reap wait.
_KILL_WAIT_S = 3.0


class PersistentJsonSubprocess:
    """One persistent JSON-line-protocol subprocess with REAL timeouts.

    Usage::

        sub = PersistentJsonSubprocess(name="qwen-tts", log=my_log_fn)
        sub.spawn([sys.executable, script], env=my_env)
        sub.send({"action": "load", "model_path": "…"})
        msg = sub.read_json(timeout=SHORT_LLM_TIMEOUT_S)      # real timeout, no blocking readline
        …
        sub.close()                              # quit → wait → kill escalation

    Thread-safety: ``send``/``read_*``/``close``/``kill`` are meant to be
    called from the owning (TTS worker) thread — the same contract the
    engines already had. The internal reader/drain threads are daemons.
    """

    def __init__(
        self,
        name: str = "tts-subprocess",
        log: LogFn | None = None,
        stderr_prefix: str = "[tts-sub]",
        stderr_level: str = "DEBUG",
    ) -> None:
        self._name = name
        self._log = log or (lambda msg, level="INFO": None)
        self._stderr_prefix = stderr_prefix
        self._stderr_level = stderr_level
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._eof = False
        self._lock = threading.Lock()

    # ── lifecycle ──────────────────────────────────────────────────────

    def spawn(
        self,
        cmd: list[str],
        env: dict[str, str] | None = None,
    ) -> None:
        """Start the subprocess + the stderr drain + stdout reader threads.

        Standard kwargs: pipes, text mode, UTF-8, CREATE_NO_WINDOW on
        Windows (no console flash — the V11.38.6 pattern).
        """
        import os

        kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "env": env if env is not None else os.environ.copy(),
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._lines = queue.Queue()
        self._eof = False
        self._proc = subprocess.Popen(cmd, **kwargs)

        # Continuous stderr drain (V11.32.0 lesson: a full stderr pipe
        # deadlocks the child on its next print).
        def _drain_stderr() -> None:
            proc = self._proc
            if proc is None or proc.stderr is None:
                return
            try:
                for line in proc.stderr:
                    line = line.rstrip()
                    if line:
                        self._log(
                            f"  {self._stderr_prefix} {line}",
                            self._stderr_level,
                        )
            except Exception:
                logger.debug("stderr drain ended [%s]", self._name, exc_info=True)

        threading.Thread(
            target=_drain_stderr,
            daemon=True,
            name=f"{self._name}-stderr-drain",
        ).start()

        # Stdout reader → queue. This is what makes read timeouts REAL:
        # readline() blocks forever on a silent-but-alive child, but the
        # reader thread is allowed to block — the OWNER never calls
        # readline() directly, it pops the queue with a timeout.
        def _read_stdout() -> None:
            proc = self._proc
            if proc is None or proc.stdout is None:
                return
            try:
                for line in proc.stdout:
                    self._lines.put(line)
            except Exception:
                logger.debug("stdout reader ended [%s]", self._name, exc_info=True)
            finally:
                self._lines.put(_EOF)

        threading.Thread(
            target=_read_stdout,
            daemon=True,
            name=f"{self._name}-stdout-reader",
        ).start()

    @property
    def alive(self) -> bool:
        """True while the Popen handle exists and the child has not exited."""
        proc = self._proc
        return proc is not None and proc.poll() is None

    @property
    def eof(self) -> bool:
        """V18.20.4.4: True once the child's stdout closed (reader hit EOF).

        Lets the engines distinguish "child closed stdout / died"
        (W-c2 reap) from "child alive but silent" (real timeout, W-c11).
        """
        return self._eof

    @property
    def returncode(self) -> int | None:
        proc = self._proc
        return None if proc is None else proc.returncode

    # ── protocol I/O ───────────────────────────────────────────────────

    def send(self, obj: dict) -> bool:
        """Write one JSON line to stdin. Returns False (logged) if the
        child is gone or the pipe is broken — never raises."""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self._log(
                f"  ❌ {self._name} subprocess not running (cannot send)",
                "ERROR",
            )
            return False
        try:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
            return True
        except Exception as e:
            self._log(f"  ❌ {self._name} send failed: {e}", "ERROR")
            return False

    def read_line(self, timeout: float) -> str | None:
        """Pop one stdout line with a REAL timeout (queue-based).

        Returns None on timeout or after EOF. Lines that arrived before
        EOF are still delivered first.
        """
        if self._proc is None or self._eof:
            return None
        try:
            item = self._lines.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return None
        if item is _EOF:
            self._eof = True
            return None
        return item  # type: ignore[return-value]

    def read_json(self, timeout: float) -> dict | None:
        """Read the next JSON line, tolerating non-JSON noise lines.

        Keeps reading (within ``timeout``) past lines that do not parse,
        mirroring the engines' old ``if not line.startswith("{"): continue``
        loops. Returns None on timeout / EOF.
        """
        deadline = time.time() + max(0.0, timeout)
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            line = self.read_line(remaining)
            if line is None:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    # ── teardown — the neutts cleanup contract, written once ──────────

    def kill(self, reason: str = "") -> None:
        """Immediate kill + reap. Idempotent; logs the reason.

        V18.20.4.4 (W-c2): the engines MUST call this (or ``close``)
        before raising on any load/generate failure — dropping the
        Popen handle alone leaves a model-loading child running with
        the VRAM locked and no reference to it.
        """
        with self._lock:
            proc = self._proc
            if proc is None:
                return
            if reason:
                self._log(
                    f"  🔧 Killing {self._name} subprocess (reason: {reason}, "
                    f"exit code: {proc.returncode})",
                    "WARNING",
                )
            try:
                if proc.poll() is None:
                    proc.kill()
                try:
                    proc.wait(timeout=_KILL_WAIT_S)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                        proc.wait(timeout=_KILL_WAIT_S)
                    except Exception:
                        logger.debug("re-kill failed [%s]", self._name, exc_info=True)
            except Exception:
                logger.debug("kill failed [%s]", self._name, exc_info=True)
            self._proc = None
            self._eof = True

    def close(self) -> None:
        """Graceful quit → wait → escalate to kill. Idempotent.

        The exact ``neutts_engine._cleanup_process`` contract: send
        ``{"action": "quit"}``, wait up to 5s, kill on any failure.
        Safe to call from ``__del__`` (best-effort, never raises).
        """
        with self._lock:
            proc = self._proc
            if proc is None:
                return
            try:
                if proc.stdin is not None and not proc.stdin.closed:
                    proc.stdin.write('{"action": "quit"}\n')
                    proc.stdin.flush()
                proc.wait(timeout=_QUIT_WAIT_S)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    logger.debug("close-kill failed [%s]", self._name, exc_info=True)
            self._proc = None
            self._eof = True

    def __del__(self) -> None:  # pragma: no cover — best-effort
        try:
            self.close()
        except Exception:
            logger.debug("best-effort close in __del__ failed", exc_info=True)
