#!/usr/bin/env python3
"""Elixir — one-command Windows installer builder.

    python build_installer.py

What it does, in order:

 1. Preflight  — checks Python, installs PyInstaller/Pillow if missing, runs
                 the SOURCE self-test (`python main.py --selftest`).
 2. Assets     — generates ``assets/elixir.ico`` if absent, downloads the
                 external tools (ffmpeg, poppler) whose licence allows
                 redistribution, writes the self-test manifest.
 3. PyInstaller— packs the app (ONEDIR mode for fast startup, windowed).
 4. Self-test  — runs ``Elixir.exe --selftest`` against the packed build.
 5. Launch test— launches ``Elixir.exe``, waits for the main window.
 6. Installer  — generates the Inno Setup script (auto-installs Inno Setup
                 via winget if missing) and compiles
                 ``dist_installer/Elixir-Setup-<version>.exe``.
 7. Silent test— installs the built installer silently, self-tests + launch-
                 tests the INSTALLED app, then uninstalls silently.
 8. Timing     — measures startup time (window visible) for the installed
                 app and for ``python main.py``, and lists the top-5 slowest
                 imports at startup (``python -X importtime``).

Everything is logged to ``build_installer.log``. The build FAILS (non-zero
exit) if any enabled test fails — "the build finished" is not success.

Flags:
    --debug        run the packed Elixir.exe attached to this console so a
                   crash prints its traceback here (for "closes right after
                   starting" situations).
    --fast         skip the test phases (self-test / launch / silent install).
    --icon-only    only (re)generate assets/elixir.ico — works on any OS.
    --skip-source-selftest   don't run the pre-build source self-test.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — edit this block only
# ═══════════════════════════════════════════════════════════════════════════

APP_NAME = "Elixir"
ENTRY_SCRIPT = "main.py"
VERSION_FILE = "VERSION"

# Icon for the exe / installer / window. If missing, a simple one is
# generated from scratch (the repo ships no logo image, only placeholders).
ICON_FILE = "assets/elixir.ico"

# Packages walked (recursively) for the self-test manifest + top-level
# modules that are not inside a package.
APP_PACKAGES = ["core", "ui_qt", "utils"]
TOP_LEVEL_MODULES = ["controller", "app_paths"]

# Read-only data shipped inside the bundle (relative to the repo root).
DATA_FOLDERS = ["prompts", "assets", "config"]
DATA_FILES = ["VERSION", "utils/patterns.json"]
PACKAGE_DATA = ["core/summarisation/postchecks/data"]

# Modules loaded dynamically at runtime (importlib/plugin-style) that
# PyInstaller's static analysis cannot see.
HIDDEN_IMPORTS = [
    "core.llm.ollama_provider",
    "core.llm.llamacpp_provider",
    "core.llm.openai_compat_provider",
    "core.llm.claude_provider",
    "tiktoken_ext.openai_public",
    "keyring.backends.Windows",
    "PySide6.QtSvg",
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
]

# Small external tools bundled with the app (licence permits redistribution;
# the app finds them in the bundle first — see app_paths.find_bundled_tool).
# Model weights, Ollama and API keys are NEVER bundled.
BUNDLE_FFMPEG = True
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_FALLBACK_URLS = [
    # latest essentials build from the gyan.dev GitHub mirror
    "https://github.com/GyanD/codexffmpeg/releases/latest/download/"
    "ffmpeg-latest-essentials_build.zip",
]
BUNDLE_POPPLER = True
POPPLER_URL = (
    "https://github.com/oschwartz10612/poppler-windows/releases/download/"
    "v26.09.0-0/Release-26.09.0-0.zip"
)

# Test switches.
SELFTEST_ENABLED = True
LAUNCH_TEST_ENABLED = True
SILENT_INSTALL_TEST_ENABLED = True

# Output layout.
BUILD_DIR = "build_pyinstaller"
DIST_APP_DIR = "dist_app"
DIST_INSTALLER_DIR = "dist_installer"
INSTALLER_BASENAME = "Elixir-Setup-{version}"
LOG_FILE = "build_installer.log"
SELFTEST_REPORT = "selftest_report.txt"

# How Inno Setup is auto-installed when missing (winget -> choco -> direct).
INNO_SETUP_WINGET_ID = "JRSoftware.InnoSetup"
INNO_SETUP_CHOCO_ID = "innosetup"
INNO_SETUP_DIRECT_URL = "https://jrsoftware.org/download.php/is.exe"

# ═══════════════════════════════════════════════════════════════════════════
#  END CONFIGURATION — implementation below
# ═══════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parent
LOG_LINES: list[str] = []


def log(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # cp1252 console (Windows) can't encode some chars (arrows, check
        # marks) — degrade to ASCII instead of crashing the build over a
        # log line.
        print(msg.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    LOG_LINES.append(msg)
    try:
        (ROOT / LOG_FILE).write_text("\n".join(LOG_LINES) + "\n", encoding="utf-8")
    except Exception:
        pass


def die(msg: str) -> None:
    log(f"\n*** BUILD FAILED: {msg}")
    log(f"*** See {LOG_FILE} and {SELFTEST_REPORT} for details.")
    sys.exit(1)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 1800,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess, streaming or capturing output."""
    log(f"$ {' '.join(str(c) for c in cmd)}" + (f"  (cwd={cwd})" if cwd else ""))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
        text=True,
        capture_output=capture,
        encoding="utf-8",
        errors="replace",
    )
    if capture and proc.stdout:
        for line in proc.stdout.splitlines()[:200]:
            log(f"    {line}")
    if capture and proc.stderr:
        for line in proc.stderr.splitlines()[:200]:
            log(f"    [stderr] {line}")
    if check and proc.returncode != 0:
        die(f"command failed with exit code {proc.returncode}: {cmd}")
    return proc


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0: preflight
# ─────────────────────────────────────────────────────────────────────────────


def read_version() -> str:
    try:
        v = (ROOT / VERSION_FILE).read_text(encoding="utf-8").strip()
    except OSError as exc:
        die(f"cannot read {VERSION_FILE}: {exc}")
    if not re.fullmatch(r"[\dA-Za-z.\-]+", v or ""):
        die(f"invalid version in {VERSION_FILE}: {v!r}")
    return v


def ensure_build_deps() -> None:
    """Make sure PyInstaller + Pillow are importable in this interpreter."""
    missing = []
    for mod in ("PyInstaller", "PIL"):
        if importlib_util_find_spec(mod) is None:
            missing.append(mod)
    if missing:
        pkgs = {"PyInstaller": "pyinstaller", "PIL": "pillow"}  # module -> pip name
        log(f"[preflight] installing missing build deps: {missing}")
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                *[pkgs[m] for m in missing],
            ],
            timeout=600,
        )


def importlib_util_find_spec(name: str):
    import importlib.util

    return importlib.util.find_spec(name)


def source_selftest() -> None:
    """Run `python main.py --selftest` BEFORE packing — catches broken code
    and missing data early, on the build machine."""
    report = ROOT / BUILD_DIR / "selftest_source.txt"
    log("[preflight] running the SOURCE self-test ...")
    proc = subprocess.run(
        [sys.executable, ENTRY_SCRIPT, "--selftest", str(report)],
        cwd=str(ROOT),
        timeout=900,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = (proc.stdout or "").strip().splitlines()[-25:]
    for line in tail:
        log(f"    {line}")
    if proc.returncode != 0:
        die(f"source self-test failed (exit {proc.returncode}) — see {report}")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: assets — icon, tools, manifest
# ─────────────────────────────────────────────────────────────────────────────


def generate_icon(out_path: Path) -> None:
    """Draw a simple, clean app icon from scratch (no logo image ships with
    the repo). Rounded emerald tile + white flask with amber liquid."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        die("Pillow is required to generate the icon (pip install pillow)")

    S = 1024  # master size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # ── rounded-square tile with a vertical teal->emerald gradient ──────────
    top = Image.new("RGBA", (S, S), (13, 148, 136, 255))  # teal-600
    bottom = Image.new("RGBA", (S, S), (6, 78, 59, 255))  # emerald-900
    grad = Image.linear_gradient("L").resize((S, S))  # 0 top -> 255 bottom
    tile = Image.composite(bottom, top, grad)
    mask = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([16, 16, S - 16, S - 16], radius=224, fill=255)
    img.paste(tile, (0, 0), mask)

    # ── flask glyph (white silhouette) ─────────────────────────────────────
    flask = Image.new("L", (S, S), 0)
    fd = ImageDraw.Draw(flask)
    cx = S // 2
    neck_w, neck_top, neck_bot = 148, 150, 380
    fd.rectangle([cx - neck_w // 2, neck_top, cx + neck_w // 2, neck_bot], fill=255)
    fd.rectangle(
        [cx - neck_w // 2 - 36, neck_top - 8, cx + neck_w // 2 + 36, neck_top + 74], fill=255
    )
    fd.polygon(
        [
            (cx - neck_w // 2 - 14, neck_bot - 10),
            (cx + neck_w // 2 + 14, neck_bot - 10),
            (cx + 350, 830),
            (cx - 350, 830),
        ],
        fill=255,
    )
    fd.ellipse([cx - 350, 760, cx + 350, 900], fill=255)
    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    img.paste(white, (0, 0), flask)

    # ── amber liquid clipped to the flask ─────────────────────────────────
    liquid = Image.new("L", (S, S), 0)
    ld = ImageDraw.Draw(liquid)
    ld.rectangle([cx - 260, 600, cx + 260, 800], fill=255)
    ld.ellipse([cx - 322, 640, cx + 322, 880], fill=255)
    liquid = Image.composite(liquid, Image.new("L", (S, S), 0), flask)
    ltop = Image.new("RGBA", (S, S), (251, 191, 36, 255))  # amber-400
    lbot = Image.new("RGBA", (S, S), (217, 119, 6, 255))  # amber-600
    lgrad = Image.linear_gradient("L").resize((S, S))
    limg = Image.composite(lbot, ltop, lgrad)
    # keep the liquid inside the flask walls (erode a little for the rim)
    img.paste(limg, (0, 0), liquid)

    # ── bubbles + neck highlight + sparkle ────────────────────────────────
    d2 = ImageDraw.Draw(img)
    d2.ellipse([cx - 60, 660, cx - 6, 714], fill=(255, 244, 214, 235))
    d2.ellipse([cx + 40, 700, cx + 92, 752], fill=(255, 248, 227, 220))
    d2.ellipse([cx - 8, 560, cx + 16, 584], fill=(255, 248, 227, 200))
    d2.rounded_rectangle(
        [cx - neck_w // 2 + 18, neck_top + 30, cx - neck_w // 2 + 40, neck_bot],
        radius=11,
        fill=(255, 255, 255, 120),
    )
    # 4-point sparkle top-right
    sx, sy, r1, r2 = 780, 190, 120, 34
    d2.polygon(
        [
            (sx, sy - r1),
            (sx + r2, sy - r2),
            (sx + r1, sy),
            (sx + r2, sy + r2),
            (sx, sy + r1),
            (sx - r2, sy + r2),
            (sx - r1, sy),
            (sx - r2, sy - r2),
        ],
        fill=(255, 255, 255, 240),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(out_path, format="ICO", sizes=sizes)
    # also keep a big PNG next to it for humans
    img.resize((256, 256), Image.LANCZOS).save(out_path.with_suffix(".png"))
    log(f"[icon] wrote {out_path} (and .png preview)")


def download_file(urls: list[str], dest: Path, timeout: int = 900) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        log(f"[tools] using cached {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"[tools] downloading {urls[0]}")

    def _get(u: str) -> None:
        req = urllib.request.Request(u, headers={"User-Agent": "ElixirBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            t0 = time.time()
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total and (got % (50 << 20) < (1 << 20)):
                    pct = 100 * got // total
                    log(f"    {pct:3d}%  {got / 1e6:8.1f} MB  ({time.time() - t0:.0f}s)")

    last_exc: Exception | None = None
    for u in urls:
        try:
            _get(u)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log(f"    download failed ({exc}); trying next mirror ...")
            dest.unlink(missing_ok=True)
    die(f"could not download {urls[0]}: {last_exc}")


def prepare_tools(tools_dir: Path) -> list[str]:
    """Download + extract the bundled external tools into ``tools_dir``.
    Returns the license lines to embed in the bundle."""
    tools_dir.mkdir(parents=True, exist_ok=True)
    downloads = ROOT / BUILD_DIR / "downloads"
    licenses: list[str] = []

    if BUNDLE_FFMPEG and not (tools_dir / "ffmpeg.exe").exists():
        z = downloads / "ffmpeg-essentials.zip"
        download_file([FFMPEG_URL, *FFMPEG_FALLBACK_URLS], z)
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            bin_prefix = next(
                (n.rsplit("/bin/", 1)[0] + "/bin/" for n in names if n.endswith("/bin/ffmpeg.exe")),
                None,
            )
            if bin_prefix is None:
                die("unexpected ffmpeg zip layout (no */bin/ffmpeg.exe)")
            for n in names:
                if n.startswith(bin_prefix) and not n.endswith("/"):
                    rel = n[len(bin_prefix) :]
                    if "/" in rel:
                        continue  # keep the flat bin/ contents only
                    if rel.split(".")[-1].lower() in {"exe", "txt"}:
                        out = tools_dir / rel
                        out.write_bytes(zf.read(n))
        licenses.append(
            "ffmpeg (https://ffmpeg.org) — GPL-2.0-or-later builds by Gyan Dhandensia "
            "(https://www.gyan.dev/ffmpeg/builds/). Source code: "
            "https://git.ffmpeg.org/ffmpeg.git and https://github.com/GyanD/codexffmpeg."
        )

    if BUNDLE_POPPLER and not (tools_dir / "pdftoppm.exe").exists():
        z = downloads / "poppler-windows.zip"
        download_file([POPPLER_URL], z)
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            bin_prefix = next(
                (
                    n.rsplit("/bin/", 1)[0] + "/bin/"
                    for n in names
                    if n.endswith("/bin/pdftoppm.exe")
                ),
                None,
            )
            if bin_prefix is None:
                die("unexpected poppler zip layout (no */bin/pdftoppm.exe)")
            for n in names:
                if n.startswith(bin_prefix) and not n.endswith("/"):
                    rel = n[len(bin_prefix) :]
                    if "/" in rel:
                        continue
                    out = tools_dir / rel
                    out.write_bytes(zf.read(n))
        licenses.append(
            "poppler (https://poppler.freedesktop.org) — GPL-2.0-or-later Windows builds by "
            "oschwartz10612 (https://github.com/oschwartz10612/poppler-windows)."
        )

    if licenses:
        (tools_dir / "LICENSES-bundled-tools.txt").write_text(
            "Elixir bundles the following third-party tools.\n"
            "Their licences (GPL) permit redistribution; source code is\n"
            "available at the URLs below.\n\n" + "\n\n".join(f"- {lic}" for lic in licenses) + "\n",
            encoding="utf-8",
        )
    return licenses


def walk_app_modules() -> list[str]:
    """Every module of the app — the manifest the frozen self-test imports."""
    modules: list[str] = []
    for package in APP_PACKAGES:
        pkg_dir = ROOT / package
        if not pkg_dir.is_dir():
            die(f"package folder missing: {pkg_dir}")
        for py in sorted(pkg_dir.rglob("*.py")):
            rel = py.relative_to(ROOT)
            if "__pycache__" in rel.parts:
                continue
            parts = list(rel.with_suffix("").parts)
            if rel.stem == "__init__":
                parts = parts[:-1]
            if parts:
                modules.append(".".join(parts))
    modules.extend(TOP_LEVEL_MODULES)
    return modules


def write_manifest(build_dir: Path) -> Path:
    manifest = build_dir / "_selftest_manifest.json"
    modules = walk_app_modules()
    manifest.write_text(json.dumps({"modules": modules}, indent=1), encoding="utf-8")
    log(f"[manifest] {len(modules)} modules -> {manifest}")
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: PyInstaller
# ─────────────────────────────────────────────────────────────────────────────


def pyi(pathstr: str) -> str:
    return str((ROOT / pathstr).resolve()).replace("\\", "/")


def write_spec(build_dir: Path, tools_dir: Path | None) -> Path:
    datas = []
    for folder in DATA_FOLDERS:
        datas.append((pyi(folder), folder))
    for f in DATA_FILES:
        datas.append((pyi(f), str(Path(f).parent)))
    for pkg_data in PACKAGE_DATA:
        datas.append((pyi(pkg_data), pkg_data))
    if tools_dir is not None and tools_dir.is_dir() and any(tools_dir.iterdir()):
        datas.append((str(tools_dir.resolve()).replace("\\", "/"), "tools"))
    datas.append((str((build_dir / "_selftest_manifest.json").resolve()), "."))

    datas_repr = ",\n        ".join(f"({json.dumps(src)}, {json.dumps(dst)})" for src, dst in datas)

    # COLLECT-ALL-MODULES strategy: PyInstaller's static analysis misses
    # modules that are loaded dynamically (importlib plugin loaders,
    # subprocess helper scripts, optional dev CLIs). Bundling EVERY app
    # module as a hidden import is cheap (pure Python) and makes the frozen
    # app a complete drop-in for the source tree — the packed self-test
    # then verifies exactly that.
    all_hidden = sorted({*HIDDEN_IMPORTS, *walk_app_modules()})
    hidden = ",\n        ".join(json.dumps(h) for h in all_hidden)

    icon_arg = f", icon={json.dumps(pyi(ICON_FILE))}" if (ROOT / ICON_FILE).is_file() else ""

    spec = f"""# -*- mode: python ; coding: utf-8 -*-
# AUTO-GENERATED by build_installer.py — do not edit; re-run the builder.

a = Analysis(
    [{json.dumps(pyi(ENTRY_SCRIPT))}],
    pathex=[{json.dumps(str(ROOT.resolve()))}],
    binaries=[],
    datas=[
        {datas_repr},
    ],
    hiddenimports=[
        {hidden},
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name={json.dumps(APP_NAME)},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None{icon_arg},
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name={json.dumps(APP_NAME)},
)
"""
    spec_path = build_dir / "elixir.spec"
    spec_path.write_text(spec, encoding="utf-8")
    log(f"[spec] wrote {spec_path} ({len(datas)} data entries)")
    return spec_path


def run_pyinstaller(spec_path: Path) -> None:
    exe = ROOT / DIST_APP_DIR / APP_NAME / f"{APP_NAME}.exe"
    if exe.exists():
        log(f"[pyinstaller] removing previous build {exe}")
        shutil.rmtree(ROOT / DIST_APP_DIR / APP_NAME, ignore_errors=True)
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            str(spec_path),
            "--distpath",
            str(ROOT / DIST_APP_DIR),
            "--workpath",
            str(ROOT / BUILD_DIR / "work"),
        ],
        timeout=3600,
    )
    if not exe.is_file():
        die(f"PyInstaller finished but {exe} was not produced")
    size_mb = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file()) / 1e6
    log(f"[pyinstaller] OK — {exe.parent} ({size_mb:.0f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: tests — self-test, launch test, timing
# ─────────────────────────────────────────────────────────────────────────────


def run_packed_selftest(exe: Path, report: Path) -> bool:
    log(f"[selftest] {exe.name} --selftest ...")
    proc = subprocess.run(
        [str(exe), "--selftest", str(report)],
        cwd=str(exe.parent),
        timeout=1200,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.strip().splitlines()[-40:]:
        log(f"    {line}")
    if proc.returncode != 0:
        log(f"[selftest] FAILED (exit {proc.returncode}) — report: {report}")
        return False
    log("[selftest] PASS")
    return True


LAUNCH_PS = r"""
param(
    [string]$Exe,
    [string]$Args = "",
    [string]$WorkDir = "",
    [int]$TimeoutSec = 150,
    [string]$StderrFile = ""
)
if (-not $WorkDir) { $WorkDir = Split-Path -Parent $Exe }
$sw = [System.Diagnostics.Stopwatch]::StartNew()
if ($StderrFile) {
    $p = Start-Process -FilePath $Exe -ArgumentList $Args -PassThru `
        -WorkingDirectory $WorkDir -RedirectStandardError $StderrFile
} else {
    $p = Start-Process -FilePath $Exe -ArgumentList $Args -PassThru `
        -WorkingDirectory $WorkDir
}
$result = "NO_WINDOW_TIMEOUT"
$windowMs = -1
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Milliseconds 150
    try { $p.Refresh() } catch {}
    if ($p.HasExited) { $result = "EXITED code=$($p.ExitCode)"; break }
    if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
        $result = "WINDOW_SHOWN"
        $windowMs = [math]::Round($sw.Elapsed.TotalMilliseconds)
        break
    }
}
if ($result -eq "WINDOW_SHOWN") { Write-Output "RESULT=$result ms=$windowMs" }
else { Write-Output "RESULT=$result ms=$([math]::Round($sw.Elapsed.TotalMilliseconds))" }
try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 2
"""


def _write_launch_ps() -> Path:
    ps1 = ROOT / BUILD_DIR / "launch_test.ps1"
    ps1.parent.mkdir(parents=True, exist_ok=True)
    ps1.write_text(LAUNCH_PS, encoding="utf-8")
    return ps1


def _run_launch_ps(
    exe: str,
    args: str = "",
    work_dir: str = "",
    timeout: int = 150,
    stderr_file: str = "",
) -> str:
    ps1 = _write_launch_ps()
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-Exe",
        str(exe),
        "-TimeoutSec",
        str(timeout),
    ]
    if args:
        cmd += ["-Args", args]
    if work_dir:
        cmd += ["-WorkDir", work_dir]
    if stderr_file:
        cmd += ["-StderrFile", stderr_file]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout + 90,
        encoding="utf-8",
        errors="replace",
    )
    return ((proc.stdout or "").strip()) or (proc.stderr or "").strip()[:400]


def launch_test(exe: Path, label: str, timeout: int = 150) -> bool:
    """Launch the app and wait for its main window to become visible."""
    log(f"[launch:{label}] starting {exe} ...")
    out = _run_launch_ps(str(exe), timeout=timeout)
    log(f"[launch:{label}] {out}")
    return "RESULT=WINDOW_SHOWN" in out


def measure_startup(exe: Path, label: str, args: str = "", work_dir: str = "") -> str:
    """Measure double-click -> main-window-visible. Returns the ps result line."""
    out = _run_launch_ps(str(exe), args=args, work_dir=work_dir, timeout=180)
    log(f"[timing:{label}] {out}")
    return out


def profile_importtime() -> list[tuple[int, str]]:
    """Run `python -X importtime main.py` for ~20 s, kill it once startup
    imports are long done, and parse the top slowest imports (self-time).

    Pure-Python capture (no PowerShell redirect quirks): the app is allowed
    to reach its window; imports complete in the first seconds, then the
    process is killed and the captured stderr is parsed.
    """
    stderr_file = ROOT / BUILD_DIR / "importtime.log"
    stderr_file.unlink(missing_ok=True)
    time.sleep(2)  # let the previous launch's single-instance lock settle
    with open(stderr_file, "wb") as err:
        proc = subprocess.Popen(
            [sys.executable, "-X", "importtime", ENTRY_SCRIPT],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=err,
        )
        try:
            proc.wait(timeout=25)  # if it exits early (crash), still parse
        except subprocess.TimeoutExpired:
            pass  # still running with its window up — imports are done
        finally:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception:
                pass
    imports: list[tuple[int, str]] = []
    for line in stderr_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"import time:\s+(\d+) \|\s+\d+ \| (\s*)(\S+)", line)
        if m:
            imports.append((int(m.group(1)), m.group(3)))
    return sorted(imports, key=lambda t: -t[0])[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Inno Setup
# ─────────────────────────────────────────────────────────────────────────────


def find_iscc() -> str | None:
    p = shutil.which("iscc") or shutil.which("ISCC")
    if p:
        return p
    for base in (
        r"C:\Program Files (x86)\Inno Setup 6",
        r"C:\Program Files\Inno Setup 6",
        r"C:\Program Files (x86)\Inno Setup 7",
        r"C:\Program Files\Inno Setup 7",
    ):
        cand = Path(base) / "ISCC.exe"
        if cand.is_file():
            return str(cand)
    return None


def ensure_inno_setup() -> str:
    iscc = find_iscc()
    if iscc:
        return iscc
    log("[inno] Inno Setup not found — installing it (winget) ...")
    subprocess.run(
        [
            "winget",
            "install",
            "--id",
            INNO_SETUP_WINGET_ID,
            "-e",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        timeout=1200,
    )
    iscc = find_iscc()
    if iscc:
        return iscc
    log("[inno] winget failed — trying chocolatey ...")
    subprocess.run(["choco", "install", "-y", INNO_SETUP_CHOCO_ID], timeout=1200)
    iscc = find_iscc()
    if iscc:
        return iscc
    log("[inno] choco failed — direct download ...")
    z = ROOT / BUILD_DIR / "downloads" / "innosetup.exe"
    download_file(INNO_SETUP_DIRECT_URL, z)
    subprocess.run([str(z), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=1200)
    iscc = find_iscc()
    if not iscc:
        die("could not install Inno Setup (tried winget, choco, direct download)")
    return iscc


ISS_TEMPLATE = """; AUTO-GENERATED by build_installer.py — do not edit by hand.
#define SourceRoot "{root}"

[Setup]
AppName={app}
AppVersion={version}
AppPublisher={app}
DefaultDirName={{autopf}}\\{app}
DefaultGroupName={app}
DisableProgramGroupPage=yes
OutputDir={dist_installer}
OutputBaseFilename={basename}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
; V0.6.66 (second "doesn't open" field report): Python 3.12 requires
; Windows 10+ — on anything older the installer used to install fine and
; the app then died SILENTLY at every launch (the bootloader cannot load
; python312.dll on Win 7/8.1). Refuse to install there instead, with a
; clear message.
MinVersion=10.0
; V0.6.66: a hung Elixir.exe from a previous install keeps the old exe
; open — without this, Inno cannot replace it and the Start-menu shortcut
; keeps launching the OLD (possibly broken) build until the next reboot
; (the in-use-file trap; Restart Manager force-closes it instead).
CloseApplications=force
UninstallDisplayIcon={{app}}\\{app}.exe
SetupIconFile={icon}
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "{{#SourceRoot}}\\{dist_app}\\{app}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs
; V0.6.66: the Start-menu diagnostics collector (see its header comment
; — turns any future "doesn't open" report into evidence a non-technical
; user can attach in one double-click).
Source: "{{#SourceRoot}}\\packaging\\collect_diagnostics.cmd"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\{app}"; Filename: "{{app}}\\{app}.exe"
Name: "{{group}}\\Elixir - Collect Diagnostics"; Filename: "{{app}}\\collect_diagnostics.cmd"; WorkingDir: "{{app}}"
Name: "{{group}}\\Uninstall {app}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\{app}"; Filename: "{{app}}\\{app}.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{app}.exe"; Description: "Launch {app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the empty install tree only — user data in %LOCALAPPDATA%\\{app} is kept.

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  OllamaFound: Boolean;
  TesseractFound: Boolean;
  UserConfigDir: String;
begin
  Result := True;

  // INTERACTIVE-ONLY PROMPTS: WizardSilent() is True for /SILENT and
  // /VERYSILENT installs. A plain MsgBox() is NOT suppressed by
  // /SUPPRESSMSGBOXES and would block a silent install forever — so the
  // prompts and tool checks are skipped entirely in silent mode.
  if WizardSilent() then
  begin
    UserConfigDir := ExpandConstant('{{localappdata}}') + '\\{app}';
    if not DirExists(UserConfigDir) then
    begin
      CreateDir(UserConfigDir);
      CreateDir(UserConfigDir + '\\prompts');
      CreateDir(UserConfigDir + '\\crash_reports');
    end;
    exit;
  end;

  // ── Ollama (required for local LLM summarisation) ──────────────────────
  OllamaFound := RegKeyExists(HKLM, 'SOFTWARE\\Ollama') or
                 RegKeyExists(HKCU, 'SOFTWARE\\Ollama');
  if not OllamaFound then
  begin
    try
      if Exec(ExpandConstant('{{cmd}}'), '/C ollama --version > nul 2>&1', '',
                 SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        OllamaFound := (ResultCode = 0);
    except
    end;
  end;
  if not OllamaFound then
  begin
    if MsgBox('Ollama is not detected. Elixir uses Ollama for local LLM ' +
              'summarisation.' + #13#10 + #13#10 +
              'You can install it later — Elixir will remind you. ' +
              'Download it now?', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://ollama.com/download', '', '', SW_SHOW, ewNoWait, ResultCode);
  end;

  // ── Tesseract (OPTIONAL — only for the classic Tesseract OCR engine) ──
  TesseractFound := FileExists(ExpandConstant('{{pf}}\\Tesseract-OCR\\tesseract.exe')) or
                    FileExists(ExpandConstant('{{pf32}}\\Tesseract-OCR\\tesseract.exe'));
  if not TesseractFound then
  begin
    try
      if Exec(ExpandConstant('{{cmd}}'), '/C tesseract --version > nul 2>&1', '',
                 SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        TesseractFound := (ResultCode = 0);
    except
    end;
  end;
  if not TesseractFound then
  begin
    if MsgBox('Tesseract OCR is not installed (optional).' + #13#10 + #13#10 +
              'It is only needed if you want the classic Tesseract OCR engine; ' +
              'the default AI-based OCR and the bundled Poppler work without it. ' +
              'Open the download page now?', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://github.com/UB-Mannheim/tesseract/wiki', '',
                '', SW_SHOW, ewNoWait, ResultCode);
  end;

  // ── Pre-create the per-user data directory ────────────────────────────
  UserConfigDir := ExpandConstant('{{localappdata}}') + '\\{app}';
  if not DirExists(UserConfigDir) then
  begin
    CreateDir(UserConfigDir);
    CreateDir(UserConfigDir + '\\prompts');
    CreateDir(UserConfigDir + '\\crash_reports');
  end;
end;
"""


def build_installer(version: str, tool_licenses: list[str]) -> Path:
    iscc = ensure_inno_setup()
    dist_installer = (ROOT / DIST_INSTALLER_DIR).resolve()
    dist_installer.mkdir(parents=True, exist_ok=True)
    icon_abs = (ROOT / ICON_FILE).resolve() if (ROOT / ICON_FILE).is_file() else None
    iss = ISS_TEMPLATE.format(
        root=str(ROOT.resolve()),
        app=APP_NAME,
        version=version,
        dist_installer=str(dist_installer),
        dist_app=DIST_APP_DIR,
        basename=INSTALLER_BASENAME.format(version=version),
        icon=str(icon_abs) if icon_abs else "",
    )
    if not icon_abs:
        # drop the SetupIconFile line when there is no icon
        iss = iss.replace("SetupIconFile=\n", "")
    iss_path = ROOT / BUILD_DIR / "Elixir.iss"
    iss_path.write_text(iss, encoding="utf-8")
    log(f"[inno] script -> {iss_path}")
    run([iscc, str(iss_path)], timeout=3600)
    out = dist_installer / f"{INSTALLER_BASENAME.format(version=version)}.exe"
    if not out.is_file():
        die(f"Inno Setup finished but {out} was not produced")
    log(f"[inno] OK -> {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def kill_running_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", f"{APP_NAME}.exe"], capture_output=True)
    time.sleep(1)


def silent_install_test(installer: Path, version: str) -> dict:
    """Install silently, self-test + launch-test the installed app, uninstall."""
    results: dict[str, object] = {}
    kill_running_app()
    log(f"[install-test] running {installer.name} /VERYSILENT ...")
    try:
        run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=900)
    except subprocess.TimeoutExpired:
        # e.g. a [Code] MsgBox blocking a silent install — kill the stuck
        # installer and fail with an actionable message.
        subprocess.run(["taskkill", "/F", "/IM", installer.name], capture_output=True)
        die(
            "silent install did not finish within 15 minutes — most likely a "
            "message box in the Inno [Code] section blocking it (custom "
            "MsgBox calls are NOT suppressed by /SUPPRESSMSGBOXES; guard "
            "them with WizardSilent())"
        )

    localapp = os.environ.get("LOCALAPPDATA", "")
    installed = Path(localapp) / "Programs" / APP_NAME / f"{APP_NAME}.exe"
    if not installed.is_file():
        # fallback: look in both Program Files
        for pf in (
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        ):
            cand = pf / APP_NAME / f"{APP_NAME}.exe"
            if cand.is_file():
                installed = cand
                break
    if not installed.is_file():
        die("silent install finished but the installed exe was not found")
    log(f"[install-test] installed at {installed}")
    results["installed_exe"] = str(installed)

    ok = run_packed_selftest(installed, ROOT / BUILD_DIR / "selftest_installed.txt")
    results["installed_selftest"] = "PASS" if ok else "FAIL"
    if not ok:
        die("installed-app self-test failed")

    ok = launch_test(installed, "installed")
    results["installed_launch"] = "PASS" if ok else "FAIL"
    if not ok:
        die("installed-app launch test failed")

    # startup timing on the INSTALLED app: first launch, then warm re-launch
    kill_running_app()
    out1 = measure_startup(installed, "installed-first-launch")
    results["installed_startup_first"] = out1
    out2 = measure_startup(installed, "installed-warm")
    results["installed_startup_warm"] = out2

    # ── silent uninstall ──────────────────────────────────────────────────
    kill_running_app()
    unins = installed.parent / "unins000.exe"
    if unins.is_file():
        log("[install-test] silent uninstall ...")
        run([str(unins), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
        # the uninstaller copies itself to %TEMP% and returns immediately
        deadline = time.time() + 120
        while time.time() < deadline:
            if not installed.is_file():
                break
            time.sleep(2)
        results["uninstall"] = "PASS" if not installed.is_file() else "LEFTOVERS"
        log(f"[install-test] uninstall: {results['uninstall']}")
    else:
        results["uninstall"] = "UNINSTALLER NOT FOUND"
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Debug mode
# ─────────────────────────────────────────────────────────────────────────────


def debug_run() -> None:
    exe = ROOT / DIST_APP_DIR / APP_NAME / f"{APP_NAME}.exe"
    if not exe.is_file():
        die(f"packed app not found ({exe}) — run a normal build first")
    log(f"[debug] running {exe} attached to this console for up to 120 s ...")
    log("[debug] (crash tracebacks appear below; Ctrl+C stops waiting)")
    try:
        proc = subprocess.run(
            [str(exe)],
            cwd=str(exe.parent),
            timeout=120,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log(f"[debug] process EXITED with code {proc.returncode}")
        if proc.stdout:
            log("---- stdout ----")
            log(proc.stdout[-4000:])
        if proc.stderr:
            log("---- stderr ----")
            log(proc.stderr[-8000:])
    except subprocess.TimeoutExpired as exc:
        log("[debug] the app was STILL RUNNING after 120 s — no crash observed.")
        if exc.stdout:
            log("---- stdout so far ----")
            log((exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else exc.stdout)
        if exc.stderr:
            log("---- stderr so far ----")
            log((exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else exc.stderr)
        subprocess.run(["taskkill", "/F", "/IM", f"{APP_NAME}.exe"], capture_output=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--debug", action="store_true", help="run the packed app attached to this console"
    )
    parser.add_argument("--fast", action="store_true", help="skip the test phases")
    parser.add_argument("--icon-only", action="store_true", help="only generate assets/elixir.ico")
    parser.add_argument("--skip-source-selftest", action="store_true")
    args = parser.parse_args()

    started = time.time()

    if args.icon_only:
        generate_icon(ROOT / ICON_FILE)
        return

    if sys.platform != "win32":
        die("the installer build must run on Windows (PyInstaller cannot cross-compile)")

    version = read_version()
    log("=" * 74)
    log(f"{APP_NAME} installer build — version {version}")
    log(f"python {sys.version.split()[0]} @ {sys.executable}")
    log("=" * 74)

    if args.debug:
        debug_run()
        return

    # Phase 0 — preflight
    ensure_build_deps()
    if not args.skip_source_selftest:
        source_selftest()

    build_dir = ROOT / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1 — assets
    if not (ROOT / ICON_FILE).is_file():
        log(f"[icon] {ICON_FILE} missing — generating a simple one")
        generate_icon(ROOT / ICON_FILE)
    tools_dir = build_dir / "tools"
    tool_licenses = prepare_tools(tools_dir)
    write_manifest(build_dir)

    # Phase 2 — PyInstaller
    spec = write_spec(build_dir, tools_dir)
    run_pyinstaller(spec)
    packed_exe = ROOT / DIST_APP_DIR / APP_NAME / f"{APP_NAME}.exe"

    # Phase 3 — tests on the packed build
    test_results: dict[str, str] = {}
    if not args.fast:
        if SELFTEST_ENABLED:
            if not run_packed_selftest(packed_exe, ROOT / SELFTEST_REPORT):
                die("packed self-test failed — run with --debug to see the crash text")
            test_results["packed_selftest"] = "PASS"
        if LAUNCH_TEST_ENABLED:
            if not launch_test(packed_exe, "packed"):
                die("packed launch test failed — run with --debug to see the crash text")
            test_results["packed_launch"] = "PASS"
            kill_running_app()

    # Phase 4 — installer
    installer = build_installer(version, tool_licenses)

    # Phase 5 — silent install test on the installer itself
    results: dict[str, object] = {}
    if not args.fast and SILENT_INSTALL_TEST_ENABLED:
        results = silent_install_test(installer, version)

    # Phase 6 — source startup timing + import profile
    if not args.fast:
        log("[timing] source run: python main.py (window poll) ...")
        results["source_startup"] = measure_startup(
            sys.executable, "source", args=ENTRY_SCRIPT, work_dir=str(ROOT)
        )
        log("[timing] source run: python -X importtime main.py (import profile) ...")
        top_imports = profile_importtime()
        results["top_imports"] = [f"{name}: {us / 1000:.0f} ms" for us, name in top_imports]

    # ── summary ───────────────────────────────────────────────────────────
    log("")
    log("=" * 74)
    log("BUILD SUMMARY")
    log("=" * 74)
    log(f"  installer          : {installer}")
    log(f"  installer size     : {installer.stat().st_size / 1e6:.1f} MB")
    log(
        f"  packed app         : {packed_exe.parent} "
        f"({sum(f.stat().st_size for f in packed_exe.parent.rglob('*') if f.is_file()) / 1e6:.0f} MB)"
    )
    for k, v in test_results.items():
        log(f"  {k.replace('_', ' '):19}: {v}")
    if not args.fast:
        for k, v in results.items():
            if k == "top_imports":
                continue
            log(f"  {k.replace('_', ' '):19}: {v}")
        if results.get("top_imports"):
            log("  top-5 slowest imports (source run, by self time):")
            for t in results["top_imports"]:
                log(f"      {t}")
    log(f"  total build time   : {(time.time() - started) / 60:.1f} min")
    log("=" * 74)
    log(f"DONE — installer is at {installer}")
    log(f"Full log: {ROOT / LOG_FILE}")


if __name__ == "__main__":
    main()
