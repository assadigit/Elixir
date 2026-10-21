"""V0.6.63 ``--selftest``: import-walk + bundled-data smoke test.

``main.py`` invokes this BEFORE any QApplication exists (and before the
torch import) when the command line contains ``--selftest <report_file>``.
The installer build (``build_installer.py``) runs it against the packed
``Elixir.exe``:

* imports EVERY module of the app (walks the ``core``, ``utils`` and
  ``ui_qt`` packages plus the top-level ``controller`` module),
* loads every bundled read-only data file (prompts tree, fonts, icons,
  ``utils/patterns.json``, the garble lexicon, ``VERSION``,
  ``config/chapter_keywords.md``, the vendored tiktoken encoding),
* imports the critical third-party dependencies,
* writes ONE LINE PER FAILURE to the report file,
* exits with code 0 only when nothing failed.

No window is opened and no Qt application object is created — importing
``ui_qt`` modules defines classes, it does not instantiate widgets.
"""

from __future__ import annotations

import gzip
import importlib
import json
import pkgutil
import sys
import time
from datetime import datetime
from pathlib import Path

from app_paths import bundle_dir, is_frozen, resource_path

# Walked in this order: non-Qt packages first so unrelated failures surface
# before any Qt import issue.
_APP_PACKAGES = ("core", "utils", "ui_qt")
_APP_MODULES = ("controller",)

# Critical third-party imports — a missing hidden import in the PyInstaller
# bundle shows up here as a plain line in the report instead of a mysterious
# crash on the user's machine.
_CRITICAL_THIRD_PARTY = (
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "markitdown",
    "pypdf",
    "pdf2image",
    "pdfplumber",
    "pytesseract",
    "PIL",
    "tiktoken",
    "docx",
    "requests",
    "yaml",
    "rapidfuzz",
    "numpy",
    "keyring",
    "wordninja",
    "arabic_reshaper",
    "bidi",
)

# Per-module import timings (seconds) — reported as the slowest imports so
# startup work has data behind it.
_import_timings: list[tuple[float, str]] = []

# Import failures raised while pkgutil walks the package tree (a package
# whose __init__ raises is never yielded by the walk — onerror is the only
# place its failure can be recorded).
_walk_failures: list[str] = []


def _on_walk_error(name: str) -> None:
    """Record a package that failed to import during the walk."""
    line = _check_import(name)  # re-import to capture the failure line
    if line is not None:
        _walk_failures.append(line)


def _walk_module_names() -> list[str]:
    """Every importable module of the app, in deterministic order."""
    names: list[str] = list(_APP_PACKAGES)  # the root packages themselves
    for pkg in _APP_PACKAGES:
        try:
            mod = importlib.import_module(pkg)
        except Exception:  # noqa: BLE001 — recorded when imported below
            continue
        paths = getattr(mod, "__path__", None)
        if not paths:
            continue
        sub = sorted(
            info.name
            for info in pkgutil.walk_packages(paths, prefix=f"{pkg}.", onerror=_on_walk_error)
        )
        names.extend(sub)
    names.extend(_APP_MODULES)
    return names


def _check_import(name: str) -> str | None:
    """Import one module; return a failure line or None."""
    try:
        t0 = time.perf_counter()
        importlib.import_module(name)
        _import_timings.append((time.perf_counter() - t0, name))
        return None
    except Exception as exc:  # noqa: BLE001 — the report must never crash
        return f"[FAIL] import {name}: {type(exc).__name__}: {exc}"


def _data_file_checks() -> list[tuple[str, Path, object]]:
    """(label, path, loader) triples for every bundled data file.

    ``loader`` takes the path and raises on any problem — a plain read for
    text/binary files, a parse for structured ones.
    """

    def _text(p: Path) -> None:
        text = p.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("file is empty")

    def _json(p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data:
            raise ValueError("no JSON object at top level")

    def _lexicon(p: Path) -> None:
        words = gzip.decompress(p.read_bytes()).decode("ascii").split()
        if len(words) < 1000:
            raise ValueError(f"lexicon suspiciously small: {len(words)} words")

    def _font(p: Path) -> None:
        blob = p.read_bytes()
        if len(blob) < 1000:
            raise ValueError(f"font suspiciously small: {len(blob)} bytes")

    def _tiktoken_blob(p: Path) -> None:
        blob = p.read_bytes()
        if len(blob) < 100_000:
            raise ValueError(f"encoding file suspiciously small: {len(blob)} bytes")

    checks: list[tuple[str, Path, object]] = [
        ("VERSION", resource_path("VERSION"), _text),
        ("utils/patterns.json", resource_path("utils", "patterns.json"), _json),
        (
            "postchecks/english_lexicon.txt.gz",
            resource_path("core", "summarisation", "postchecks", "data", "english_lexicon.txt.gz"),
            _lexicon,
        ),
        ("config/chapter_keywords.md", resource_path("config", "chapter_keywords.md"), _text),
        (
            "config/voice_samples/README.md",
            resource_path("config", "voice_samples", "README.md"),
            _text,
        ),
    ]

    prompts = resource_path("prompts")
    if prompts.is_dir():
        for md in sorted(prompts.rglob("*.md")):
            checks.append((str(md.relative_to(bundle_dir())), md, _text))
    else:
        checks.append(("prompts/", prompts, _text))  # forced failure: dir missing

    fonts_dir = resource_path("assets", "fonts")
    font_files = sorted(fonts_dir.glob("*.ttf"))
    if not font_files and not fonts_dir.is_dir():
        # Required: the repo ships Vazirmatn (Persian PDF output depends on
        # it) — a bundle without assets/fonts is build drift.
        checks.append(("assets/fonts/", fonts_dir, _font))
    for font in font_files:
        checks.append((str(font.relative_to(bundle_dir())), font, _font))

    icons_dir = resource_path("assets", "icons")
    if icons_dir.is_dir():
        for icon in sorted(icons_dir.iterdir()):
            if icon.is_file():
                checks.append((str(icon.relative_to(bundle_dir())), icon, _text))

    tiktoken_dir = resource_path("assets", "tiktoken")
    tiktoken_blobs = sorted(tiktoken_dir.glob("*.tiktoken"))
    if not tiktoken_blobs:
        # Required: the offline token-counting contract (main.py seeds
        # DATA_GYM_CACHE_DIR from this file in frozen builds).
        checks.append(
            ("assets/tiktoken/*.tiktoken", tiktoken_dir / "cl100k_base.tiktoken", _tiktoken_blob)
        )
    for blob in tiktoken_blobs:
        checks.append((str(blob.relative_to(bundle_dir())), blob, _tiktoken_blob))

    return checks


def run_selftest(argv: list[str]) -> int:
    """Execute the self-test; write the report; return the exit code."""
    report_path = _report_path(argv)
    lines: list[str] = [
        f"Elixir selftest — {datetime.now().isoformat(timespec='seconds')}",
        f"frozen={is_frozen()} python={sys.version.split()[0]}",
        f"bundle_dir={bundle_dir()}",
        "-" * 60,
    ]
    failures = 0

    # 0. Packages whose import failed during the tree walk itself.
    for line in _walk_failures:
        failures += 1
        lines.append(line)

    # 1. Import every module of the app.
    module_ok = 0
    module_fail = 0
    for name in _walk_module_names():
        line = _check_import(name)
        if line is None:
            module_ok += 1
        else:
            module_fail += 1
            failures += 1
            lines.append(line)
    lines.append(f"modules: {module_ok} imported OK, {module_fail} failed")

    # 2. Load every bundled data file.
    data_ok = 0
    data_fail = 0
    for label, path, loader in _data_file_checks():
        try:
            loader(path)
            data_ok += 1
        except Exception as exc:  # noqa: BLE001 — one line per failure
            data_fail += 1
            lines.append(f"[FAIL] data {label}: {type(exc).__name__}: {exc}")
    failures += data_fail
    lines.append(f"data files: {data_ok} loaded OK, {data_fail} failed")

    # 3. Critical third-party imports.
    tp_ok = 0
    tp_fail = 0
    for name in _CRITICAL_THIRD_PARTY:
        line = _check_import(name)
        if line is None:
            tp_ok += 1
        else:
            tp_fail += 1
            lines.append(line)
    failures += tp_fail
    lines.append(f"third-party: {tp_ok} imported OK, {tp_fail} failed")

    # 4. Slowest app-module imports (startup evidence).
    lines.append("-" * 60)
    lines.append("slowest module imports (seconds):")
    for secs, name in sorted(_import_timings, reverse=True)[:10]:
        lines.append(f"  {secs:8.3f}  {name}")

    lines.append("-" * 60)
    lines.append(f"RESULT: {'PASS' if failures == 0 else f'FAIL ({failures} failures)'}")

    report = "\n".join(lines) + "\n"
    try:
        Path(report_path).write_text(report, encoding="utf-8")
    except OSError as exc:
        print(f"could not write selftest report {report_path}: {exc}", file=sys.stderr)
        return 2
    print(report)
    return 0 if failures == 0 else 1


def _report_path(argv: list[str]) -> str:
    """``--selftest <report_file>`` → the next argument; else a default."""
    for i, arg in enumerate(argv):
        if arg == "--selftest":
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                return argv[i + 1]
            return "selftest_report.txt"
    return "selftest_report.txt"
