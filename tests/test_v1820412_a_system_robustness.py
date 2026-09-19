"""V18.20.4.12 batch A (agent 7-a) — system robustness trio.

FIX 1 (W-c15/T-c5): ``execute_post_completion_action`` no longer fires
  blind ``subprocess.Popen`` calls.  Every shutdown/sleep/hibernate
  command now runs via ``subprocess.run(..., capture_output=True,
  text=True, timeout=20)`` with honest reporting: rc==0 → INFO success,
  rc!=0 → LOUD WARNING (returncode + stderr + ONE platform hint),
  TimeoutExpired → INFO (benign — the machine is likely already
  suspending).  Per-platform command lists are byte-identical to the
  pre-V18.20.4.12 Popen args (pinned here).
FIX 2 (W-c14): the append-only diagnostic logs (faulthandler.log,
  thread_crash.log, gpu_probe.log) are rotated at 1 MiB by
  ``core.system.crash_visibility.rotate_log_if_large`` (never-raise,
  single ``.old`` generation) before each append-open.
FIX 3 (W-c17): ``HF_HUB_OFFLINE`` / ``TRANSFORMERS_OFFLINE`` are scoped
  to the offline from-disk embedder load (snapshot → set → restore in
  ``finally``) instead of staying set process-wide after success.

All tests are pure Python — no PySide6 (the Qt-gated open sites are
pinned via source-scan, the house pattern from
tests/test_deadline_watchdog.py:149-157).
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parents[1]
_HW_SRC = (_project_root / "core" / "system" / "hardware_monitor.py").read_text(encoding="utf-8")
_CV_SRC = (_project_root / "core" / "system" / "crash_visibility.py").read_text(encoding="utf-8")
_MS_SRC = (_project_root / "core" / "llm" / "model_singletons.py").read_text(encoding="utf-8")
_MAIN_SRC = (_project_root / "main.py").read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1 (W-c15/T-c5) — honest post-completion shutdown/sleep/hibernate
# ═════════════════════════════════════════════════════════════════════════════


class _CmdRecorder:
    """Records log_callback traffic + subprocess.run calls (scripted rc/stderr)."""

    def __init__(self, rc: int = 0, stderr: str = "", raise_timeout: bool = False):
        self.logs: list[tuple[str, str]] = []
        self.calls: list[dict] = []
        self.rc = rc
        self.stderr = stderr
        self.raise_timeout = raise_timeout

    def log(self, msg: str, level: str) -> None:
        self.logs.append((msg, level))

    def run(self, cmd, capture_output=False, text=False, timeout=None):
        self.calls.append(
            {
                "cmd": list(cmd),
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
            }
        )
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(cmd, timeout=timeout)
        return types.SimpleNamespace(returncode=self.rc, stderr=self.stderr)


def _hw_with_recorder(monkeypatch, recorder: _CmdRecorder):
    """Patch hardware_monitor's subprocess namespace (run + TimeoutExpired)."""
    from core.system import hardware_monitor as hw

    monkeypatch.setattr(
        hw,
        "subprocess",
        types.SimpleNamespace(run=recorder.run, TimeoutExpired=subprocess.TimeoutExpired),
    )
    return hw


class TestPostCompletionReporting:
    def test_success_rc0_logs_info(self, monkeypatch):
        rec = _CmdRecorder(rc=0)
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("shutdown", log_callback=rec.log)
        assert rec.logs[-1] == ("  ✅ Shutdown scheduled/initiated successfully", "INFO")
        assert len(rec.calls) == 1
        assert rec.calls[0]["capture_output"] is True
        assert rec.calls[0]["text"] is True
        assert rec.calls[0]["timeout"] == 20

    def test_failure_darwin_warning_has_rc_stderr_and_hint(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        rec = _CmdRecorder(rc=1, stderr="sudo: a terminal is required\n")
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("shutdown", log_callback=rec.log)
        warnings = [m for m, lvl in rec.logs if lvl == "WARNING"]
        assert len(warnings) == 1, rec.logs
        msg = warnings[0]
        assert "rc=1" in msg
        assert "sudo: a terminal is required" in msg
        assert "sudo shutdown -h +1" in msg  # the exact command, for context
        assert "sudo needs a TTY" in msg
        assert "NOPASSWD: /sbin/shutdown" in msg
        assert "Quit action" in msg

    def test_failure_linux_warning_has_root_hint(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        rec = _CmdRecorder(rc=1, stderr="Permission denied\n")
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("sleep", log_callback=rec.log)
        warnings = [m for m, lvl in rec.logs if lvl == "WARNING"]
        assert len(warnings) == 1, rec.logs
        msg = warnings[0]
        assert "rc=1" in msg and "Permission denied" in msg
        assert "shutdown requires root" in msg
        assert "systemctl poweroff" in msg

    def test_failure_win32_stderr_verbatim(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        long_err = "Command failed: 1190 (A system shutdown has already been " + "x" * 300
        rec = _CmdRecorder(rc=1190, stderr=long_err)
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("shutdown", log_callback=rec.log)
        warnings = [m for m, lvl in rec.logs if lvl == "WARNING"]
        assert len(warnings) == 1, rec.logs
        msg = warnings[0]
        assert "rc=1190" in msg
        # Windows: no canned hint — the FULL stderr is included verbatim.
        assert long_err in msg

    def test_failure_stderr_truncated_to_200_chars_on_posix(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        err = "E" * 300
        rec = _CmdRecorder(rc=2, stderr=err)
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("hibernate", log_callback=rec.log)
        msg = [m for m, lvl in rec.logs if lvl == "WARNING"][0]
        assert "E" * 200 in msg  # first ~200 chars present…
        assert "E" * 201 not in msg  # …and nothing beyond that

    def test_timeout_is_info_not_warning(self, monkeypatch):
        rec = _CmdRecorder(raise_timeout=True)
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("sleep", log_callback=rec.log)
        assert rec.logs, "the countdown + outcome lines must both be logged"
        assert all(lvl == "INFO" for _, lvl in rec.logs), rec.logs
        assert not any(lvl == "WARNING" for _, lvl in rec.logs), (
            "a benign timeout (machine likely already suspending) must NOT be reported as a failure"
        )
        msg = rec.logs[-1][0]
        assert "still running after 20s" in msg
        assert "suspend was likely initiated at the OS level" in msg
        assert "treating as scheduled" in msg

    def test_none_and_quit_behaviour_unchanged(self, monkeypatch):
        rec = _CmdRecorder()
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("none", log_callback=rec.log)
        assert rec.logs == [] and rec.calls == []
        hw.execute_post_completion_action("quit", log_callback=rec.log)
        assert rec.calls == []
        assert rec.logs == [("  👋 Quitting application as requested.", "INFO")]

    def test_unknown_action_still_noop(self, monkeypatch):
        """Pre-V18.20.4.12 an unknown action logged the countdown line and
        silently fell through without executing anything — pinned."""
        rec = _CmdRecorder()
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("reboot", log_callback=rec.log)
        assert rec.calls == []
        assert rec.logs == [("  ⏳ Reboot in 60s…", "INFO")]

    def test_countdown_line_and_default_callback_unchanged(self, monkeypatch):
        rec = _CmdRecorder(rc=0)
        hw = _hw_with_recorder(monkeypatch, rec)
        hw.execute_post_completion_action("sleep", delay_seconds=90, log_callback=rec.log)
        assert rec.logs[0] == ("  ⏳ Sleep in 90s…", "INFO")
        # log_callback=None (default) must stay safe (silent sink)
        hw.execute_post_completion_action("shutdown")
        assert len(rec.calls) == 2  # both runs executed, nothing raised


class TestPostCompletionCommandConstruction:
    """Pin the per-platform command lists BYTE-IDENTICAL to the pre-V18.20.4.12
    Popen args (W-c15 fix must not change what actually runs)."""

    @pytest.mark.parametrize(
        "platform,action,expected",
        [
            ("win32", "shutdown", ["shutdown", "/s", "/t", "60"]),
            ("win32", "sleep", ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]),
            ("win32", "hibernate", ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,0"]),
            ("darwin", "shutdown", ["sudo", "shutdown", "-h", "+1"]),
            ("darwin", "sleep", ["pmset", "sleepnow"]),
            ("darwin", "hibernate", ["pmset", "hibernatenow"]),
            ("linux", "shutdown", ["shutdown", "-h", "+1"]),
            ("linux", "sleep", ["systemctl", "suspend"]),
            ("linux", "hibernate", ["systemctl", "hibernate"]),
        ],
    )
    def test_per_platform_commands_pinned(self, monkeypatch, platform, action, expected):
        rec = _CmdRecorder()
        hw = _hw_with_recorder(monkeypatch, rec)
        monkeypatch.setattr(sys, "platform", platform)
        hw.execute_post_completion_action(action, delay_seconds=60, log_callback=rec.log)
        assert rec.calls == [
            {"cmd": expected, "capture_output": True, "text": True, "timeout": 20},
        ]

    @pytest.mark.parametrize(
        "delay,win_t,linux_min",
        [
            (0, "0", "+1"),  # linux floor: max(1, 0//60) == 1
            (59, "59", "+1"),  # 59//60 == 0 → clamped to 1
            (120, "120", "+2"),  # 120//60 == 2
        ],
    )
    def test_shutdown_delay_semantics_pinned(self, monkeypatch, delay, win_t, linux_min):
        rec = _CmdRecorder()
        hw = _hw_with_recorder(monkeypatch, rec)
        monkeypatch.setattr(sys, "platform", "win32")
        hw.execute_post_completion_action("shutdown", delay_seconds=delay, log_callback=rec.log)
        assert rec.calls[0]["cmd"] == ["shutdown", "/s", "/t", win_t]
        # darwin ignores the delay entirely (fixed +1) — unchanged from pre-fix
        monkeypatch.setattr(sys, "platform", "darwin")
        hw.execute_post_completion_action("shutdown", delay_seconds=delay, log_callback=rec.log)
        assert rec.calls[1]["cmd"] == ["sudo", "shutdown", "-h", "+1"]
        monkeypatch.setattr(sys, "platform", "linux")
        hw.execute_post_completion_action("shutdown", delay_seconds=delay, log_callback=rec.log)
        assert rec.calls[2]["cmd"] == ["shutdown", "-h", linux_min]


class TestPostCompletionSourcePins:
    """Signature/contract pins (house source-scan pattern)."""

    @staticmethod
    def _code_only(text: str) -> str:
        """Drop comments so pins assert CODE, not fix-documentation
        (house pattern: tests/test_v182049_bk1_ui_threading.py:_strip_comments)."""
        out = []
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
        return "\n".join(out)

    def test_signature_unchanged(self):
        assert (
            "def execute_post_completion_action(\n"
            "    action: str,\n"
            "    delay_seconds: int = 60,\n"
            "    log_callback: LogFn | None = None,\n"
            ") -> None:" in _HW_SRC
        ), "the public signature must stay byte-identical"

    def test_background_thread_contract_documented(self):
        assert "should be called from a background thread" in _HW_SRC

    def test_no_blind_popen_left_in_section(self):
        section = _HW_SRC.split("# ── Post-completion actions", 1)[1]
        code = self._code_only(section)
        assert "subprocess.Popen(" not in code, (
            "the blind fire-and-forget Popen call must not come back (W-c15); "
            "mentions of the old behaviour only survive in comments/docstrings"
        )
        assert "subprocess.run(cmd, capture_output=True, text=True, timeout=20)" in code


# ═════════════════════════════════════════════════════════════════════════════
# FIX 2 (W-c14) — rotate the append-only diagnostic logs at 1 MiB
# ═════════════════════════════════════════════════════════════════════════════


class TestRotateLogIfLarge:
    def test_over_cap_rotates_to_old(self, tmp_path):
        from core.system.crash_visibility import rotate_log_if_large

        log = tmp_path / "gpu_probe.log"
        log.write_text("x" * 300, encoding="utf-8")
        rotate_log_if_large(log, max_bytes=100)
        assert not log.exists(), "original must be moved away"
        old = tmp_path / "gpu_probe.log.old"
        assert old.read_text(encoding="utf-8") == "x" * 300
        # the caller then opens fresh and starts small
        log.write_text("fresh start", encoding="utf-8")
        assert log.read_text(encoding="utf-8") == "fresh start"

    def test_exactly_at_cap_not_rotated(self, tmp_path):
        """Strictly-greater rule: a file of exactly max_bytes stays put."""
        from core.system.crash_visibility import rotate_log_if_large

        log = tmp_path / "at.log"
        log.write_text("a" * 100, encoding="utf-8")
        rotate_log_if_large(log, max_bytes=100)
        assert log.exists() and not (tmp_path / "at.log.old").exists()

    def test_under_cap_untouched(self, tmp_path):
        from core.system.crash_visibility import rotate_log_if_large

        log = tmp_path / "small.log"
        log.write_text("y" * 10, encoding="utf-8")
        rotate_log_if_large(log)
        assert log.read_text(encoding="utf-8") == "y" * 10
        assert not (tmp_path / "small.log.old").exists()

    def test_missing_file_noop_no_raise(self, tmp_path):
        from core.system.crash_visibility import rotate_log_if_large

        rotate_log_if_large(tmp_path / "nope.log")  # must not raise
        assert not (tmp_path / "nope.log.old").exists()

    def test_default_cap_is_one_mib(self):
        from core.system.crash_visibility import rotate_log_if_large

        assert rotate_log_if_large.__defaults__ == (1_048_576,)

    def test_single_generation_old_replaced(self, tmp_path):
        from core.system.crash_visibility import rotate_log_if_large

        log = tmp_path / "gen.log"
        log.write_text("z" * 50, encoding="utf-8")
        (tmp_path / "gen.log.old").write_text("PREVIOUS GENERATION", encoding="utf-8")
        rotate_log_if_large(log, max_bytes=10)
        assert (tmp_path / "gen.log.old").read_text(encoding="utf-8") == "z" * 50
        assert not (tmp_path / "gen.log.old.old").exists(), "single .old generation only"

    def test_os_replace_failure_never_raises(self, tmp_path, monkeypatch):
        """Crash-path safety: rotation must never break the crash handler."""
        from core.system import crash_visibility as cv

        log = tmp_path / "boom.log"
        log.write_text("x" * 100, encoding="utf-8")

        def _boom(*a, **k):
            raise OSError("disk on fire")

        monkeypatch.setattr(os, "replace", _boom)
        cv.rotate_log_if_large(log, max_bytes=10)  # must not raise
        assert log.exists(), "the original log is left untouched on failure"

    def test_stat_failure_never_raises(self, tmp_path):
        """A broken symlink (stat raises FileNotFoundError) is a silent no-op."""
        from core.system.crash_visibility import rotate_log_if_large

        link = tmp_path / "broken.log"
        link.symlink_to(tmp_path / "does-not-exist")
        rotate_log_if_large(link)  # must not raise
        assert not (tmp_path / "broken.log.old").exists()


class TestRotationCallSites:
    """Drive the real crash-path writers end-to-end (rotation actually fires)."""

    def test_thread_excepthook_rotates_before_append(self, tmp_path, monkeypatch):
        from core.system import crash_visibility as cv

        tc = tmp_path / "thread_crash.log"
        tc.write_text("old crashes " * 200_000, encoding="utf-8")  # 2.4 MB
        monkeypatch.setattr(cv, "THREAD_CRASH_LOG", tc)
        args = types.SimpleNamespace(
            thread=None, exc_type=ValueError, exc_value=ValueError("boom"), exc_traceback=None
        )
        cv._thread_excepthook(args)  # never raises
        assert (
            (tmp_path / "thread_crash.log.old")
            .read_text(encoding="utf-8")
            .startswith("old crashes ")
        ), "history moved to .old"
        fresh = tc.read_text(encoding="utf-8")
        assert not fresh.startswith("old crashes")
        assert "ValueError" in fresh and "boom" in fresh

    def test_arm_faulthandler_rotates_before_open(self, tmp_path):
        import faulthandler

        from core.system import crash_visibility as cv

        fh_log = tmp_path / "faulthandler.log"
        fh_log.write_text("junk " * 300_000, encoding="utf-8")  # 1.5 MB
        saved_fh_file = cv._fh_file
        try:
            assert cv.arm_faulthandler(log_path=fh_log) is True
            assert (
                (tmp_path / "faulthandler.log.old").read_text(encoding="utf-8").startswith("junk ")
            )
            fresh = fh_log.read_text(encoding="utf-8")
            assert "faulthandler armed" in fresh
            assert not fresh.startswith("junk")
        finally:
            # hygiene: restore the module global + re-arm faulthandler to
            # stderr (the pytest default) so later tests are unaffected.
            if cv._fh_file is not None and cv._fh_file is not saved_fh_file:
                try:
                    cv._fh_file.close()
                except Exception:
                    pass
            cv._fh_file = saved_fh_file
            faulthandler.enable()


class TestRotationSourcePins:
    """The open sites must call the helper BEFORE opening for append
    (house source-scan pattern — PySide6 is not importable headless)."""

    def test_arm_faulthandler_calls_rotate_before_open(self):
        body = _CV_SRC[_CV_SRC.index("def arm_faulthandler") : _CV_SRC.index("# ── Layer 2")]
        rot_i = body.index("rotate_log_if_large(log_path)")
        open_i = body.index("_fh_file = open(log_path")
        assert rot_i < open_i

    def test_thread_excepthook_calls_rotate_before_open(self):
        body = _CV_SRC[
            _CV_SRC.index("def _thread_excepthook") : _CV_SRC.index("def arm_thread_excepthook")
        ]
        rot_i = body.index("rotate_log_if_large(THREAD_CRASH_LOG)")
        open_i = body.index("open(THREAD_CRASH_LOG")
        assert rot_i < open_i

    def test_main_py_calls_rotate_before_gpu_probe_open(self):
        # V0.13: format-wrapped — anchor on the unique path expression
        probe_i = _MAIN_SRC.index('user_data_dir() / "gpu_probe.log"')
        rot_i = _MAIN_SRC.index("rotate_log_if_large(_probe_log)")
        open_i = _MAIN_SRC.index("with open(_probe_log")
        assert probe_i < rot_i < open_i

    def test_main_py_imports_the_helper(self):
        assert (
            "from core.system.crash_visibility import arm_crash_visibility, rotate_log_if_large"
        ) in _MAIN_SRC

    def test_main_py_still_under_260_lines(self):
        """Mirror of tests/test_bootstrap.py's thin-main pin — batch A edits
        were line-budget-neutral; keep it that way."""
        assert len(_MAIN_SRC.splitlines()) < 320, (  # V0.13: ruff-format expanded the file
            f"main.py is {len(_MAIN_SRC.splitlines())} lines (pin: < 320)"
        )

    def test_helper_exported(self):
        from core.system import crash_visibility as cv

        assert "rotate_log_if_large" in cv.__all__


# ═════════════════════════════════════════════════════════════════════════════
# FIX 3 (W-c17) — HF offline flags scoped to the from-disk embedder load
# ═════════════════════════════════════════════════════════════════════════════


class TestOfflineEnvHelpers:
    def test_snapshot_roundtrip_both_set(self, monkeypatch):
        from core.llm import model_singletons as ms

        monkeypatch.setenv("HF_HUB_OFFLINE", "0")
        monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
        snap = ms._snapshot_offline_env()
        assert snap == {"HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"}
        os.environ["HF_HUB_OFFLINE"] = "1"  # simulate the load
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        ms._restore_offline_env(snap)
        assert os.environ["HF_HUB_OFFLINE"] == "0"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "0"

    def test_snapshot_roundtrip_both_unset(self, monkeypatch):
        from core.llm import model_singletons as ms

        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
        snap = ms._snapshot_offline_env()
        assert snap == {"HF_HUB_OFFLINE": None, "TRANSFORMERS_OFFLINE": None}
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        ms._restore_offline_env(snap)
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_snapshot_roundtrip_one_set(self, monkeypatch):
        from core.llm import model_singletons as ms

        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
        monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
        snap = ms._snapshot_offline_env()
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        ms._restore_offline_env(snap)
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_restore_pops_previously_unset_keys(self, monkeypatch):
        from core.llm import model_singletons as ms

        monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
        snap = ms._snapshot_offline_env()
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        ms._restore_offline_env(snap)
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_restore_preserves_empty_string_value(self, monkeypatch):
        """An empty-string value is SET (not unset) — restore keeps it."""
        from core.llm import model_singletons as ms

        monkeypatch.setenv("HF_HUB_OFFLINE", "")
        snap = ms._snapshot_offline_env()
        os.environ["HF_HUB_OFFLINE"] = "1"
        ms._restore_offline_env(snap)
        assert os.environ["HF_HUB_OFFLINE"] == ""


class _FakeSentenceTransformer:
    """Stand-in injected into sys.modules['sentence_transformers'].

    Records the env state AT CONSTRUCTION TIME so tests can prove the
    offline flags are set DURING the load and restored AFTER it.
    """

    init_calls: list = []
    fail_local = False  # fail when constructed from the on-disk model dir
    fail_always = False

    def __init__(self, model_ref, device=None):
        _FakeSentenceTransformer.init_calls.append(
            (
                str(model_ref),
                {
                    "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
                    "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
                    "device": device,
                },
            )
        )
        if _FakeSentenceTransformer.fail_always or (
            _FakeSentenceTransformer.fail_local and ".elixir" in str(model_ref)
        ):
            raise RuntimeError("fake load failure")
        self.model_ref = str(model_ref)

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, **kw):
        import numpy as np

        return np.full(64, 0.25, dtype=np.float32)  # dim≥32, non-zero, non-NaN

    def save(self, path):
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        (p / "config.json").write_text("{}", encoding="utf-8")


_EMBED_MODEL = "fake-embed-model-v1.5"  # has dots → NOT ollama-shaped


@pytest.fixture()
def embed_env(tmp_path, monkeypatch):
    """Isolated home + fake sentence_transformers + clean singleton + clean env."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)
    from core.llm import model_singletons as ms

    monkeypatch.setattr(ms, "_embed_model", None)
    monkeypatch.setattr(ms, "_embed_model_name", None)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setattr(_FakeSentenceTransformer, "init_calls", [])
    monkeypatch.setattr(_FakeSentenceTransformer, "fail_local", False)
    monkeypatch.setattr(_FakeSentenceTransformer, "fail_always", False)
    return tmp_path


class TestOfflineEnvScopedToLoad:
    """Drive the REAL get_embed_model (lock + singleton + retry loop intact)."""

    def test_disk_load_success_sets_during_load_restores_after(self, embed_env):
        from core.llm import model_singletons as ms
        from core.llm.embedder_backend import SentenceTransformerBackend

        model_dir = embed_env / ".elixir" / "models" / _EMBED_MODEL
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        got = ms.get_embed_model(_EMBED_MODEL)
        assert isinstance(got, SentenceTransformerBackend)
        assert got._model.model_ref.endswith(_EMBED_MODEL)
        # DURING the load the flags were forced on (offline construction)…
        assert _FakeSentenceTransformer.init_calls[0][1]["HF_HUB_OFFLINE"] == "1"
        assert _FakeSentenceTransformer.init_calls[0][1]["TRANSFORMERS_OFFLINE"] == "1"
        # …and AFTER the successful load they are restored (previously they
        # stayed set process-wide — the W-c17 bug).
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_disk_load_success_preserves_user_set_values(self, embed_env, monkeypatch):
        from core.llm import model_singletons as ms

        model_dir = embed_env / ".elixir" / "models" / _EMBED_MODEL
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv("HF_HUB_OFFLINE", "0")
        monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")

        got = ms.get_embed_model(_EMBED_MODEL)
        assert got is not None
        assert os.environ["HF_HUB_OFFLINE"] == "0"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "0"

    def test_disk_failure_restores_env_before_download_path(self, embed_env, monkeypatch):
        """Disk load fails → env restored → download runs ONLINE (not forced
        offline) → succeeds → env still clean."""
        from core.llm import model_singletons as ms

        model_dir = embed_env / ".elixir" / "models" / _EMBED_MODEL
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(_FakeSentenceTransformer, "fail_local", True)

        got = ms.get_embed_model(_EMBED_MODEL)
        assert got is not None, "download fallback should succeed"
        disk_env = _FakeSentenceTransformer.init_calls[0][1]
        dl_env = _FakeSentenceTransformer.init_calls[1][1]
        assert disk_env["HF_HUB_OFFLINE"] == "1", "flags set during disk attempt"
        assert dl_env["HF_HUB_OFFLINE"] is None, (
            "download attempt must run with flags RESTORED (old failure path "
            "popped them — new code restores the prior state)"
        )
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_all_loads_fail_returns_none_env_clean(self, embed_env, monkeypatch):
        from core.llm import model_singletons as ms

        model_dir = embed_env / ".elixir" / "models" / _EMBED_MODEL
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(_FakeSentenceTransformer, "fail_always", True)

        assert ms.get_embed_model(_EMBED_MODEL) is None
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ

    def test_fresh_download_path_never_touches_flags(self, embed_env):
        """No local copy → straight to the download path, which (since
        V18.20.4.12) must NOT set the process-wide offline lock at all."""
        from core.llm import model_singletons as ms

        got = ms.get_embed_model("fresh-embed-model-v2.0")
        assert got is not None
        for _ref, env in _FakeSentenceTransformer.init_calls:
            assert env["HF_HUB_OFFLINE"] is None, (
                "the download path must not force offline mode (W-c17)"
            )
            assert env["TRANSFORMERS_OFFLINE"] is None
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ
        # the persistent copy was saved for next time
        saved_dir = embed_env / ".elixir" / "models" / "fresh-embed-model-v2.0"
        assert (saved_dir / "config.json").exists()


class TestOfflineEnvSourcePins:
    def test_offline_flags_set_exactly_once(self):
        """The only remaining set is the from-disk load (scoped); the old
        download-path process-wide lock and the raw pops are gone."""
        assert _MS_SRC.count('os.environ["HF_HUB_OFFLINE"] = "1"') == 1
        assert _MS_SRC.count('os.environ["TRANSFORMERS_OFFLINE"] = "1"') == 1
        assert _MS_SRC.count('os.environ.pop("HF_HUB_OFFLINE", None)') == 0
        assert _MS_SRC.count('os.environ.pop("TRANSFORMERS_OFFLINE", None)') == 0

    def test_snapshot_restore_wraps_disk_load(self):
        region = _MS_SRC[_MS_SRC.index("if _is_saved:") : _MS_SRC.index("# Not saved locally")]
        assert region.count("_snapshot_offline_env()") == 1
        assert region.count("_restore_offline_env(_offline_snapshot)") == 1
        snap_i = region.index("_snapshot_offline_env()")
        ret_i = region.index("return _embed_model")
        finally_i = region.index("finally:")
        restore_i = region.index("_restore_offline_env(_offline_snapshot)")
        assert snap_i < ret_i, "snapshot before the success return"
        assert ret_i < finally_i < restore_i, (
            "the finally-restore fires on BOTH success and failure paths"
        )

    def test_download_region_has_no_offline_lock(self):
        download_region = _MS_SRC[
            _MS_SRC.index("# Not saved locally") : _MS_SRC.index("def is_embedder_healthy")
        ]
        assert 'os.environ["HF_HUB_OFFLINE"]' not in download_region
        assert 'os.environ["TRANSFORMERS_OFFLINE"]' not in download_region

    def test_module_docstring_describes_new_scoping(self):
        assert "scoped to the offline from-disk load" in _MS_SRC
        assert "def _snapshot_offline_env() -> dict:" in _MS_SRC
        assert "def _restore_offline_env(snapshot: dict) -> None:" in _MS_SRC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
