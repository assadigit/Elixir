"""Ollama supervisor — monitors Ollama health and restarts on crash.

If Ollama becomes unreachable during a conversion (process crash, OOM,
Windows service stop), the supervisor detects it and attempts to restart
the Ollama service before the next LLM call.

Usage (from the converter or summarizer)::

    supervisor = OllamaSupervisor(log_callback=log)
    if not supervisor.ensure_running():
        # Ollama is down and couldn't be restarted — abort
        raise RuntimeError("Ollama is not running and could not be restarted")
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


class OllamaSupervisor:
    """Monitors and restarts Ollama when it crashes.

    Tracks consecutive failures. After ``max_consecutive_failures``,
    attempts to restart the Ollama process.

    V18.20.2.0 (SWOT A13): restart rate-limiting and the crash-loop breaker
    are PROCESS-WIDE (class-level, lock-guarded). Two or more supervisor
    instances coexist in production (the Summarizer constructs one at
    summarizer.py:206 and OllamaProvider constructs another at
    ollama_provider.py:51) — the old PER-INSTANCE ``_last_restart_time``
    let each instance independently spawn ``ollama serve``, so two servers
    could appear within 60s. All instances now share:
      - the 60s restart rate limit,
      - a cumulative per-process restart budget (``MAX_RESTARTS_PER_PROCESS``)
        — after the budget is exhausted a CRITICAL is logged and no further
        restarts are attempted (an unattended overnight crash loop would
        otherwise burn CPU + leave orphaned processes forever).
    """

    # ── V18.20.2.0 (SWOT A13): process-wide shared restart state ──────────
    # Class attributes: shared by ALL OllamaSupervisor instances in this
    # process. Guarded by _SHARED_RESTART_LOCK for thread safety.
    _SHARED_LAST_RESTART: float = 0.0
    _SHARED_RESTART_COUNT: int = 0
    _SHARED_RESTART_LOCK = threading.Lock()

    #: V18.1 (S5): no restart more than once per 60s (now process-wide).
    RESTART_RATE_LIMIT_SEC: float = 60.0
    #: V18.20.2.0 (SWOT A13): cumulative crash-loop breaker.
    MAX_RESTARTS_PER_PROCESS: int = 5
    #: V18.20.2.0 (SWOT A13): poll readiness up to 30s after a restart
    #: (a cold Ollama start can exceed the old fixed 5s sleep).
    RESTART_READY_TIMEOUT_SEC: float = 30.0
    RESTART_READY_POLL_SEC: float = 1.0

    def __init__(
        self,
        url: str = "http://localhost:11434",
        max_consecutive_failures: int = 3,
        restart_command: list | None = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self._url = url
        self._max_failures = max_consecutive_failures
        self._restart_cmd = restart_command or self._detect_restart_command()
        self._log = log_callback or (lambda msg, level="INFO": None)
        self._consecutive_failures = 0
        # Backward-compat instance mirror of the shared timestamp (the
        # rate limit itself reads the CLASS-level value — see restart()).
        self._last_restart_time: float = 0

    @staticmethod
    def _detect_restart_command() -> list:
        """Detect the platform-appropriate restart command."""
        if sys.platform == "win32":
            # On Windows, try "ollama serve" (starts the service)
            ollama_exe = shutil.which("ollama")
            if ollama_exe:
                return [ollama_exe, "serve"]
            return []
        else:
            # Linux/macOS: try systemctl, then ollama serve
            if shutil.which("systemctl"):
                return ["systemctl", "restart", "ollama"]
            ollama_exe = shutil.which("ollama")
            if ollama_exe:
                return [ollama_exe, "serve"]
            return []

    @classmethod
    def reset_restart_state(cls) -> None:
        """V18.20.2.0 (SWOT A13): reset the shared restart state.

        Test/ops helper — clears the shared rate-limit timestamp and the
        cumulative restart budget. Production code should never call this.
        """
        with cls._SHARED_RESTART_LOCK:
            cls._SHARED_LAST_RESTART = 0.0
            cls._SHARED_RESTART_COUNT = 0

    def record_failure(self) -> bool:
        """Record a failed LLM call. Returns True if Ollama should be restarted."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_failures:
            self._log(
                f"  🔄 Ollama: {self._consecutive_failures} consecutive failures — "
                f"attempting restart...",
                "WARNING",
            )
            return self.restart()
        return False

    def record_success(self) -> None:
        """Record a successful LLM call — resets the failure counter."""
        self._consecutive_failures = 0

    def restart(self) -> bool:
        """Attempt to restart Ollama. Returns True if successful."""
        # No restart command on this platform (ollama/systemctl absent) —
        # nothing to do, and no shared rate-limit/budget is consumed (a
        # restart was never attempted).
        if not self._restart_cmd:
            self._log("  ❌ Ollama: no restart command available.", "ERROR")
            return False

        # V18.20.2.0 (SWOT A13): the rate limit + crash-loop budget are
        # evaluated under the SHARED lock so ALL supervisor instances in
        # this process see the same window (the old per-instance
        # ``self._last_restart_time`` allowed concurrent double-spawns).
        with OllamaSupervisor._SHARED_RESTART_LOCK:
            now = time.time()
            # V18.1 (S5): Don't restart more than once per 60 seconds —
            # process-wide. Prevents a crash loop from respawning Ollama
            # repeatedly (which would burn CPU + leave orphaned processes).
            if now - OllamaSupervisor._SHARED_LAST_RESTART < self.RESTART_RATE_LIMIT_SEC:
                self._log("  🔄 Ollama: restart attempted recently — waiting.", "DEBUG")
                return False
            # V18.20.2.0 (SWOT A13): cumulative crash-loop breaker — once the
            # per-process budget is spent, stop restarting (log CRITICAL so
            # the operator sees WHY Ollama stays down) and report failure.
            if OllamaSupervisor._SHARED_RESTART_COUNT >= self.MAX_RESTARTS_PER_PROCESS:
                self._log(
                    f"  🚨 Ollama: restart budget exhausted "
                    f"({OllamaSupervisor._SHARED_RESTART_COUNT}/{self.MAX_RESTARTS_PER_PROCESS} "
                    f"restarts this process) — NOT restarting. Persistent Ollama crash "
                    f"loop suspected; manual intervention required.",
                    "CRITICAL",
                )
                logger.critical(
                    "OllamaSupervisor restart budget exhausted (%d restarts) — "
                    "crash-loop breaker engaged",
                    OllamaSupervisor._SHARED_RESTART_COUNT,
                )
                return False
            OllamaSupervisor._SHARED_LAST_RESTART = now
            OllamaSupervisor._SHARED_RESTART_COUNT += 1
            # Backward-compat instance mirror (pre-V18.20.2.0 attribute).
            self._last_restart_time = now

        try:
            self._log(f"  🔄 Ollama: running restart: {' '.join(self._restart_cmd)}", "INFO")
            # Start the restart command (non-blocking — ollama serve runs forever).
            #
            # V18.1 (S5): process-group isolation so the restarted Ollama
            # is properly detached from this process's signal group:
            #   - Windows: CREATE_NEW_PROCESS_GROUP lets us manage the child
            #     as a distinct group (so it isn't killed mid-call when
            #     the parent's console session ends, and so it can be
            #     cleanly terminated via GenerateConsoleCtrlEvent if we
            #     ever add explicit shutdown). Combined with CREATE_NO_WINDOW
            #     so no console flashes on the user's screen.
            #   - Unix:   start_new_session=True makes the child its own
            #     session leader so SIGINT/SIGHUP delivered to the app's
            #     process group don't tear down the freshly-restarted
            #     ollama serve mid-request.
            popen_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                )
            else:
                popen_kwargs["start_new_session"] = True
            subprocess.Popen(self._restart_cmd, **popen_kwargs)
            # V18.20.2.0 (SWOT A13): poll for readiness up to 30s instead of
            # the old fixed 5s sleep + single check. A cold Ollama start
            # (model load on HDD, service manager latency) can exceed 5s;
            # the old code then logged a FALSE "restart failed" while the
            # process was still coming up — and the 60s rate limit then
            # blocked the legitimate retry for a full minute.
            _deadline = time.time() + self.RESTART_READY_TIMEOUT_SEC
            while time.time() < _deadline:
                if self.is_running():
                    self._consecutive_failures = 0
                    self._log("  ✅ Ollama: restart successful.", "SUCCESS")
                    return True
                time.sleep(self.RESTART_READY_POLL_SEC)
            self._log("  ❌ Ollama: restart failed — still not reachable.", "ERROR")
            return False
        except (OSError, FileNotFoundError) as exc:
            self._log(f"  ❌ Ollama: restart command failed: {exc}", "ERROR")
            return False

    def is_running(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            from utils.network import is_ollama_reachable

            return is_ollama_reachable(self._url)
        except Exception as _e:
            return False

    def ensure_running(self) -> bool:
        """Ensure Ollama is running. Restart if necessary."""
        if self.is_running():
            return True
        self._log("  🔄 Ollama: not reachable — attempting restart...", "WARNING")
        return self.restart()
