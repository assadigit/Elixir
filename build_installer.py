"""Elixir — one-command Windows installer build (V0.6.63).

    python build_installer.py

Pipeline (each step must pass before the next runs):

  1. PACK        PyInstaller --onedir --windowed -> dist_app\\Elixir\\Elixir.exe
                 (fast startup, no console flash; bundled data: prompts/,
                 assets/, config/, VERSION, patterns.json, lexicon, tiktoken)
  2. SELF-TEST   dist_app\\Elixir\\Elixir.exe --selftest selftest_report.txt
                 (imports every module + loads every bundled data file;
                 exit 0 only when clean)
  3. LAUNCH TEST start the exe, expect it alive after LAUNCH_TEST_SECONDS
  4. INSTALLER   ISCC.exe installer\\Elixir.iss -> dist_installer\\
                 Elixir-Setup-<version>.exe (Inno Setup auto-installed via
                 winget when missing)
  5. SILENT TEST Setup.exe /VERYSILENT into a temp dir -> installed
                 --selftest -> silent uninstall

Success = all five green + dist_installer\\Elixir-Setup-<version>.exe exists.

    python build_installer.py --debug
        builds with a CONSOLE attached to Elixir.exe so a crash at startup
        prints its traceback (the windowed build swallows it).

    python build_installer.py --print-pyinstaller-args
        (internal) prints the PyInstaller argument list — used by the Linux
        dry-run that validates the bundle layout without a Windows machine.

Everything configurable lives in the CONFIGURATION block below.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

# ══════════════════════════════ CONFIGURATION ══════════════════════════════

APP_NAME = "Elixir"
VERSION_FILE = "VERSION"  # single source of truth (read at build time)
ENTRY_SCRIPT = "main.py"
ICON_FILE = "installer/elixir.ico"  # "" -> no icon

# Build output layout (all gitignored; see .gitignore)
DIST_APP = "dist_app"  # PyInstaller --distpath (onedir app lands in DIST_APP/Elixir)
DIST_INSTALLER = "dist_installer"  # Inno Setup output
BUILD_WORK = "build_pyinstaller"  # PyInstaller workpath + generated .spec

SELFTEST_ENABLED = True  # run Elixir.exe --selftest against the packed app
SELFTEST_REPORT = "selftest_report.txt"
LAUNCH_TEST_SECONDS = 20  # exe must stay alive this long (main window up)

# Inno Setup
INNO_SETUP_WINGET_ID = "JRSoftware.InnoSetup"
ISS_SCRIPT = "installer/Elixir.iss"

# Data bundled into the app (source, dest-in-bundle); Windows separator is
# inserted at runtime (os.pathsep) so the same list works on the Linux
# dry-run. Keep in sync with app_paths.resource_path call sites.
ADD_DATA: list[tuple[str, str]] = [
    ("prompts", "prompts"),
    ("assets", "assets"),
    ("config", "config"),
    ("VERSION", "."),
    ("utils/patterns.json", "utils"),
    ("core/summarisation/postchecks/data", "core/summarisation/postchecks/data"),
]

# Modules PyInstaller's static analysis cannot see (computed-name or
# lazy imports in the app: tiktoken's plugin registry, the lazy LLM provider
# table, keyring's entry-point backends, and the dynamically-imported app
# modules proven missing from the bundle by the V0.6.63 module-gap audit —
# without these, conversions crash at runtime while the import-walk stays
# green because the walk only sees collected modules).
HIDDEN_IMPORTS: list[str] = [
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    "core.llm.ollama_provider",
    "core.llm.llamacpp_provider",
    "core.llm.openai_compat_provider",
    "core.llm.claude_provider",
    "core.llm.async_provider",
    "keyring.backends.Windows",
    # dynamically imported at runtime (module-gap audit, V0.6.63):
    "core.pipeline.conversion_context",
    "core.summarisation.postchecks.orchestrator",
    "core.summarisation.postchecks.field_phases",
    "core.summarisation.quarantine_analytics",
    "core.translation.glossary_analytics",
    "core.podcast.script_diff",
    "core.podcast.script_export",
    "core.podcast.script_schema",
    "core.podcast.script_stats",
    "core.podcast.script_templates",
    "core.podcast.script_validator",
]

# Deliberately NOT bundled (reachable only via CLI entry points or the TTS
# subprocess engines that are frozen-guarded off): core.*.cli,
# core.tts._qwen_tts_subprocess, core.tts._vibevoice_subprocess.

# Package data PyInstaller misses. wordninja 2.x ships a bare module
# (wordninja.py) with its wordlist in a SIBLING wordninja/ dir — no hook and
# no collect-data flag can see that shape, so build_installer resolves the
# sibling dir from the build environment at build time. tiktoken's encoding
# blob ships in assets/tiktoken via ADD_DATA (seeded at runtime by main.py).
DATA_BESIDE_MODULE: list[str] = [
    "wordninja",
]

# Never bundled (kept out even if present in the build environment — the
# ML/TTS stack is deliberately not part of the installer; see AGENTS.md and
# the frozen guards in core/tts/*).
EXCLUDE_MODULES: list[str] = [
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "matplotlib",
    "tkinter",
    "pytest",
    "IPython",
    "sphinx",
    "pymupdf",
    "fitz",
]

# ════════════════════════════════════════════════════════════════════════════


def _say(step: str, msg: str) -> None:
    print(f"\n=== [{step}] {msg}", flush=True)


def _fail(step: str, msg: str) -> None:
    print(f"\n!!! [{step}] FAILED: {msg}", flush=True)
    sys.exit(1)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, **kwargs)  # noqa: S603 — fixed argv, no shell


def app_version() -> str:
    v = (REPO / VERSION_FILE).read_text(encoding="utf-8").strip()
    if not v:
        _fail("config", f"{VERSION_FILE} is empty")
    return v


def _beside_module_data() -> list[tuple[str, str]]:
    """(absolute_src, dest) pairs for data dirs sitting NEXT to a module.

    wordninja 2.x layout: <site-packages>/wordninja.py plus
    <site-packages>/wordninja/wordninja_words.txt.gz — the module loads the
    gz relative to its own file, so the bundle must reproduce that layout.
    """
    pairs: list[tuple[str, str]] = []
    for mod in DATA_BESIDE_MODULE:
        try:
            imported = __import__(mod)
            base = Path(imported.__file__).resolve().parent
            data_dir = base / mod
            if not data_dir.is_dir():
                _fail("config", f"data dir for '{mod}' not found next to {imported.__file__}")
            for f in sorted(data_dir.rglob("*")):
                if f.is_file():
                    pairs.append((str(f), str(f.parent.relative_to(base))))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 — clear build error, not a crash
            _fail("config", f"could not locate data for module '{mod}': {exc}")
    return pairs


def pyinstaller_args(console: bool) -> list[str]:
    """The full PyInstaller argument list (also printed by --print-pyinstaller-args)."""
    sep = os.pathsep
    args = [
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed" if not console else "--console",
        "--name",
        APP_NAME,
        "--workpath",
        BUILD_WORK,
        "--distpath",
        DIST_APP,
        "--specpath",
        BUILD_WORK,
    ]
    icon = REPO / ICON_FILE
    if ICON_FILE and icon.exists():
        args += ["--icon", str(icon)]
    for src, dst in [*ADD_DATA, *_beside_module_data()]:
        # Absolute sources: PyInstaller resolves relative --add-data paths
        # against the .spec's directory (--specpath), not the CWD.
        src_path = Path(src) if os.path.isabs(str(src)) else REPO / src
        args += ["--add-data", f"{src_path}{sep}{dst}"]
    for mod in HIDDEN_IMPORTS:
        args += ["--hidden-import", mod]
    for mod in EXCLUDE_MODULES:
        args += ["--exclude-module", mod]
    args.append(str(REPO / ENTRY_SCRIPT))
    return args


def step_pack(console: bool) -> Path:
    _say("1/5 pack", f"PyInstaller onedir build (console={console})")
    try:
        import PyInstaller  # noqa: F401 — presence check with a clear error
    except ImportError:
        _fail("1/5 pack", "PyInstaller is not installed (pip install pyinstaller==6.22.3)")

    exe_dir = REPO / DIST_APP / APP_NAME
    if exe_dir.exists():
        shutil.rmtree(exe_dir)
    result = _run([sys.executable, *pyinstaller_args(console)], cwd=REPO)
    if result.returncode != 0:
        _fail("1/5 pack", f"PyInstaller exited {result.returncode}")
    exe = exe_dir / f"{APP_NAME}.exe"
    if sys.platform != "win32":
        exe = exe_dir / APP_NAME  # Linux dry-run: ELF binary, no .exe suffix
    if not exe.exists():
        _fail("1/5 pack", f"expected packed app not found: {exe}")
    print(f"    packed: {exe}")
    return exe


def step_selftest(exe: Path, report_name: str) -> None:
    if not SELFTEST_ENABLED:
        _say("2/5 selftest", "SKIPPED (SELFTEST_ENABLED = False)")
        return
    _say("2/5 selftest", f"{exe.name} --selftest {report_name}")
    report = REPO / report_name
    if report.exists():
        report.unlink()
    result = subprocess.run(  # noqa: S603 — fixed argv
        [str(exe), "--selftest", report_name],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if report.exists():
        print(report.read_text(encoding="utf-8").strip()[-2000:])
    if result.returncode != 0:
        _fail("2/5 selftest", f"selftest exited {result.returncode} (see {report_name})")
    print("    selftest clean")


def step_launch_test(exe: Path) -> None:
    _say("3/5 launch", f"start {exe.name}, expect alive after {LAUNCH_TEST_SECONDS}s")
    proc = subprocess.Popen(  # noqa: S603 — fixed argv
        [str(exe)], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.time() + LAUNCH_TEST_SECONDS
        while time.time() < deadline:
            if proc.poll() is not None:
                _fail(
                    "3/5 launch",
                    f"the packed app exited early with code {proc.returncode} "
                    "(run with --debug to see the crash text)",
                )
            time.sleep(1.0)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("    launch test OK (process stayed alive)")


def _find_iscc() -> Path | None:
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return Path(found)
    for candidate in (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ):
        if candidate.exists():
            return candidate
    return None


def _ensure_iscc() -> Path:
    iscc = _find_iscc()
    if iscc:
        return iscc
    _say("4/5 installer", "Inno Setup not found — installing via winget")
    result = _run(
        [
            "winget",
            "install",
            "--id",
            INNO_SETUP_WINGET_ID,
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
    if result.returncode != 0:
        _fail("4/5 installer", "winget could not install Inno Setup (see output above)")
    iscc = _find_iscc()
    if not iscc:
        _fail("4/5 installer", "Inno Setup installed but ISCC.exe still not found")
    return iscc


def step_installer(version: str) -> Path:
    _say("4/5 installer", f"Inno Setup compile (version {version})")
    iscc = _ensure_iscc()
    out_dir = REPO / DIST_INSTALLER
    out_dir.mkdir(exist_ok=True)
    result = _run(
        [str(iscc), f"/DAppVersion={version}", str(REPO / ISS_SCRIPT)], cwd=REPO
    )
    if result.returncode != 0:
        _fail("4/5 installer", f"ISCC exited {result.returncode}")
    setup = out_dir / f"{APP_NAME}-Setup-{version}.exe"
    if not setup.exists():
        _fail("4/5 installer", f"expected installer not found: {setup}")
    size_mb = setup.stat().st_size / (1024 * 1024)
    print(f"    installer: {setup} ({size_mb:.1f} MB)")
    return setup


def step_silent_install(setup: Path) -> None:
    if sys.platform != "win32":
        _say("5/5 silent-install", "SKIPPED (non-Windows dry-run)")
        return
    _say("5/5 silent-install", f"{setup.name} /VERYSILENT into a temp dir")
    target = REPO / BUILD_WORK / "silent-install-test"
    if target.exists():
        shutil.rmtree(target)
    result = _run(
        [
            str(setup),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={target}",
        ],
        timeout=600,
    )
    if result.returncode != 0:
        _fail("5/5 silent-install", f"installer exited {result.returncode}")
    installed_exe = target / f"{APP_NAME}.exe"
    if not installed_exe.exists():
        _fail("5/5 silent-install", f"installed exe not found: {installed_exe}")

    report = "selftest_report_installed.txt"
    res = subprocess.run(  # noqa: S603 — fixed argv
        [str(installed_exe), "--selftest", report],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    installed_report = REPO / report
    if installed_report.exists():
        tail = installed_report.read_text(encoding="utf-8").strip().splitlines()
        print("    installed selftest: " + (tail[-1] if tail else "(empty report)"))
    if res.returncode != 0:
        _fail("5/5 silent-install", f"INSTALLED app selftest exited {res.returncode}")

    uninstaller = target / "unins000.exe"
    if uninstaller.exists():
        _run([str(uninstaller), "/VERYSILENT", "/NORESTART"], timeout=600)
    print("    silent install + installed selftest + uninstall OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Elixir Windows installer.")
    parser.add_argument(
        "--debug", action="store_true", help="build a console exe so crashes print"
    )
    parser.add_argument(
        "--print-pyinstaller-args",
        action="store_true",
        help="(internal) print the PyInstaller args and exit",
    )
    opts = parser.parse_args()

    if opts.print_pyinstaller_args:
        print("\n".join(pyinstaller_args(console=False)))
        return

    version = app_version()
    print(f"Elixir installer build — version {version} ({sys.platform})")

    exe = step_pack(console=opts.debug)
    step_selftest(exe, SELFTEST_REPORT)
    step_launch_test(exe)
    if sys.platform == "win32":
        setup = step_installer(version)
        step_silent_install(setup)
    else:
        _say("4/5 installer", "SKIPPED (non-Windows dry-run — Inno Setup is Windows-only)")
        _say("5/5 silent-install", "SKIPPED (non-Windows dry-run)")

    print(
        f"\n{'=' * 60}\nBUILD OK — steps 1-3 green"
        + (" + installer + silent install" if sys.platform == "win32" else " (dry-run)")
        + f"\nversion {version}"
    )


if __name__ == "__main__":
    main()
