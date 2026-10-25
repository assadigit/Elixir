"""V0.6.66: the Windows pin-lock + installer-hardening guards.

FIELD REPORT (V0.6.65, the second "doesn't open" report)
========================================================
"I've installed the latest version on my windows, it didn't open …
it goes silently fail."  The CI launch tests were green on a clean
runner, so the bundle itself CAN start — but the installer was built
from the UNPINNED ``requirements.txt`` and the 2026-10-24 build
silently picked up **PySide6 6.12.0 + mammoth 1.13.0 + markitdown
0.1.9** — the exact trio documented to SEGFAULT the Linux suite in
the lock-alignment incident (NEW_SESSION_PROMPT's recovery recipe).
The clean runner tolerated it; the first real consumer machine did
not.

These tests pin the V0.6.66 fixes so the hazard cannot silently
return:

* ``requirements.windows.lock`` exists, is installed by the Windows
  workflow (not ``requirements.txt``), and pins the three dangerous
  packages at the GLOBALLY verified versions (6.11.2 / 1.11.0 /
  0.1.7) — with the documented-bad versions (6.12.0 / 1.13.0 /
  0.1.9) forbidden by name.
* The Inno Setup template refuses Windows < 10 (``MinVersion=10.0``)
  — Python 3.12 cannot load there, and an installable-but-never-
  launching app is the worst possible failure mode — and force-closes
  a hung previous Elixir.exe during upgrade (``CloseApplications=
  force`` — the in-use-file trap that leaves the Start-menu shortcut
  pointing at the OLD exe until reboot).
* The Start-menu "Elixir - Collect Diagnostics" tool ships with the
  installer, so a non-technical user can attach evidence (startup
  logs, Defender history, install-dir integrity) in one double-click.

Headless-safe: pure file reads, no Qt, no network.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_WIN_LOCK = _project_root / "requirements.windows.lock"
_WORKFLOW = _project_root / ".github" / "workflows" / "windows-installer.yml"
_BUILDER = _project_root / "build_installer.py"
_DIAG_CMD = _project_root / "packaging" / "collect_diagnostics.cmd"

# The GLOBALLY verified trio (requirements.lock proves them on Linux —
# suite 8,613/16/25 at V0.6.65; the Windows lock pins the same versions).
_VERIFIED = {
    "PySide6": "6.11.2",
    "PySide6_Addons": "6.11.2",
    "PySide6_Essentials": "6.11.2",
    "shiboken6": "6.11.2",
    "mammoth": "1.11.0",
    "markitdown": "0.1.7",
}
# The documented-bad drift set (the 2026-10-24 unpinned Windows resolution
# that shipped inside Elixir-Setup-0.6.65.exe and produced the second
# "doesn't open" field report). Forbidden by name in the Windows lock.
_FORBIDDEN = {
    "PySide6": "6.12.0",
    "mammoth": "1.13.0",
    "markitdown": "0.1.9",
}


class TestWindowsLock:
    """requirements.windows.lock — the Windows build's pinned closure."""

    def test_lock_exists(self) -> None:
        assert _WIN_LOCK.is_file(), "requirements.windows.lock must exist (V0.6.66)"

    def test_verified_trio_pinned(self) -> None:
        """The three dangerous packages must sit at the globally
        verified versions — the ones requirements.lock proves on Linux
        (the lock-alignment incident documented them as the segfault
        set at 6.12.0 / 1.13.0 / 0.1.9)."""
        src = _WIN_LOCK.read_text(encoding="utf-8")
        for pkg, ver in _VERIFIED.items():
            assert re.search(rf"^{re.escape(pkg)}=={re.escape(ver)}\s*$", src, re.M), (
                f"requirements.windows.lock must pin {pkg}=={ver} "
                f"(the globally verified version; the 6.12.0-family drift "
                f"caused the V0.6.65 'doesn't open' field report)"
            )

    def test_documented_bad_versions_absent(self) -> None:
        """The exact versions that shipped inside the broken V0.6.65
        installer must never reappear in the Windows lock."""
        src = _WIN_LOCK.read_text(encoding="utf-8")
        for pkg, ver in _FORBIDDEN.items():
            assert not re.search(rf"^{re.escape(pkg)}=={re.escape(ver)}\s*$", src, re.M), (
                f"{pkg}=={ver} is the documented segfault/drift version — "
                f"it must not be pinned into the Windows build"
            )

    def test_lock_is_all_exact_pins(self) -> None:
        """Every package line must be an exact ``name==version`` pin —
        floating operators (>=, ~=) reintroduce the drift hazard one
        line at a time."""
        src = _WIN_LOCK.read_text(encoding="utf-8")
        for line in src.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[A-Za-z0-9.+\-]+", line), (
                f"requirements.windows.lock lines must be exact pins, got: {line!r}"
            )


class TestWindowsWorkflowInstallsTheLock:
    """The Windows workflow must build from the pinned lock, never the
    floating requirements.txt (the V0.6.65 hazard)."""

    def test_workflow_installs_windows_lock(self) -> None:
        src = _WORKFLOW.read_text(encoding="utf-8")
        assert "pip install -r requirements.windows.lock" in src, (
            "windows-installer.yml must install requirements.windows.lock "
            "(V0.6.65 shipped the unpinned drift set and the app stopped "
            "opening on the first real machine)"
        )
        # Guard the reverse direction too: requirements.txt is allowed in
        # the OTHER workflows (ci.yml's Linux job is lock-pinned already),
        # but must not appear as the Windows installer's install source.
        wf_install_blocks = re.findall(r"pip install (-r [^\n]+)", src)
        for block in wf_install_blocks:
            assert "requirements.txt" not in block, (
                "the Windows installer workflow must not install the "
                "floating requirements.txt — use requirements.windows.lock"
            )

    def test_workflow_pins_pyinstaller(self) -> None:
        src = _WORKFLOW.read_text(encoding="utf-8")
        assert re.search(r"pip install pyinstaller==[\d.]+", src), (
            "the workflow must pin pyinstaller (the bootloader builder is "
            "as much a dependency as any package)"
        )


class TestInstallerHardening:
    """The Inno Setup template's V0.6.66 hardening lines."""

    def _iss(self) -> str:
        src = _BUILDER.read_text(encoding="utf-8")
        m = re.search(r'ISS_TEMPLATE = """(.*?)"""', src, re.S)
        assert m, "ISS_TEMPLATE must exist in build_installer.py"
        return m.group(1)

    def test_min_version_windows_10(self) -> None:
        """Python 3.12 needs Windows 10+; installing onto Win 7/8.1
        produced a silently-never-launching app (the bootloader cannot
        load python312.dll there). The installer must refuse instead."""
        assert re.search(r"^MinVersion=10\.0\s*$", self._iss(), re.M), (
            "ISS_TEMPLATE must set MinVersion=10.0 — an installable app "
            "that can never launch is the worst failure mode"
        )

    def test_close_applications_force(self) -> None:
        """A hung previous Elixir.exe blocks the exe replacement (the
        in-use-file trap): without this the Start-menu shortcut keeps
        launching the OLD build until reboot."""
        assert re.search(r"^CloseApplications=force\s*$", self._iss(), re.M), (
            "ISS_TEMPLATE must set CloseApplications=force so upgrades "
            "replace a locked old Elixir.exe"
        )

    def test_diagnostics_cmd_shipped(self) -> None:
        iss = self._iss()
        assert "collect_diagnostics.cmd" in iss, (
            "the installer must ship packaging/collect_diagnostics.cmd into the app dir"
        )
        assert (
            re.search(r"Name: \"\{group\}\\\\Elixir - Collect Diagnostics\"", iss)
            or "Elixir - Collect Diagnostics" in iss
        ), "the installer must create the Start-menu 'Elixir - Collect Diagnostics' shortcut"


class TestDiagnosticsCollector:
    """packaging/collect_diagnostics.cmd — the one-double-click evidence
    collector for non-technical users."""

    def test_cmd_exists_ascii_crlf(self) -> None:
        assert _DIAG_CMD.is_file(), "packaging/collect_diagnostics.cmd must exist"
        raw = _DIAG_CMD.read_bytes()
        raw.decode("ascii")  # must be pure ASCII (no codepage surprises)
        assert b"\r\n" in raw, "the .cmd must use CRLF line endings"

    def test_cmd_collects_the_app_logs(self) -> None:
        """The app's own startup logs (%LOCALAPPDATA%\\Elixir\\*.log —
        startup.log / startup_crash.log / faulthandler.log) are the
        FIRST thing support reads on a 'doesn't open' report."""
        src = _DIAG_CMD.read_text(encoding="ascii")
        assert "%LOCALAPPDATA%\\Elixir" in src.replace("\\\\", "\\"), (
            "the collector must copy %LOCALAPPDATA%\\Elixir logs"
        )
        assert "defender" in src.lower(), (
            "the collector must include the Defender/AV checks (the "
            "classic silent killer of unsigned PyInstaller bundles)"
        )
        assert "qwindows.dll" in src, (
            "the collector must check qwindows.dll presence (the "
            "antivirus-stripped-bundle signature)"
        )
