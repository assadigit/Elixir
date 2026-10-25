"""Self-test — verifies the packed app (or a source checkout) is complete.

Invoked as::

    Elixir.exe --selftest <report_file>        # installed / packed build
    python main.py --selftest <report_file>    # running from source

What it does (and never opens a window — Qt runs on the offscreen platform):

1. Imports EVERY module of the app — ``core/**``, ``ui_qt/**``, ``utils/**``
   plus the top-level ``controller`` and ``app_paths``. In a frozen build the
   module list comes from the manifest baked in at build time
   (``_selftest_manifest.json``, written by ``build_installer.py`` while
   walking the source tree); from source the tree is walked live.
2. Verifies the third-party packages the app loads BY NAME at runtime
   (``find_spec`` — the same presence-check ``main.py`` does, extended to the
   lazy-import surface).
3. Loads the bundled DATA files (VERSION, the prompt bank via the real
   PromptManager, fonts, patterns.json, the lexicon, bundled tools).

For every failure ONE line is written to the report file. The process exit
code is 0 only when there were no failures at all.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

# V0.6.67b — THE root-cause fix of the "installed … doesn't open" saga.
# This module used to run, AT IMPORT TIME:
#
#     os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
#
# and main.py imports this module on EVERY launch (to dispatch --selftest),
# so EVERY NORMAL LAUNCH since V0.6.63 ran the whole GUI on Qt's OFFSCREEN
# platform: the app started perfectly, logged every startup step, answered
# the single-instance FOCUS protocol — and could never show a window, on
# ANY machine. Every Windows release V0.6.63 → V0.6.66 shipped headless
# (three field reports of "installed … doesn't open"). The env is now set
# INSIDE run_selftest — before its first PySide6 import, so the selftest's
# no-window guarantee is preserved — and a normal launch keeps its real
# platform. Pinned by tests/test_v0667_window_visibility.py.

# Third-party packages the app loads BY NAME at runtime (dynamic imports,
# plugin loaders, presence probes). A missing spec means the bundle is
# incomplete → failure. Optional heavyweights (torch, transformers, …) are
# deliberately absent from the installer and are NOT listed here — the app
# degrades gracefully without them.
_RUNTIME_PACKAGES = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
    "pypdf",
    "pdf2image",
    "pdfplumber",
    "markitdown",
    "pytesseract",
    "wordninja",
    "tiktoken",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    "docx",
    "requests",
    "PIL",
    "yaml",
    "rapidfuzz",
    "numpy",
    "keyring",
    "tenacity",
    "pydantic",
    "langextract",
    "arabic_reshaper",
    "bidi",
]

# Prompt templates that MUST load through the real PromptManager (exercises
# the exact resolution logic the app uses at runtime).
_KEY_PROMPTS = (
    "default",
    "default_lowbit",
    "academic",
    "technical",
    "creative",
    "simplified_default",
    "summarisation/glossary_extraction",
    "summarisation/additive_sections",
    "summarisation/master_summary",
    "outputs/podcast_script",
    "outputs/flashcards",
    "pdf/toc_extract",
    "pdf/heading_label",
    "transcribe/transcript_notes",
    "tts/normalize_en",
    "tts/normalize_fa",
)

_MANIFEST_NAME = "_selftest_manifest.json"


def _repo_root() -> Path:
    """Repository root / bundle root (works from source and frozen)."""
    try:
        from app_paths import bundle_dir

        return bundle_dir()
    except Exception:  # pragma: no cover
        return Path(__file__).resolve().parent.parent


def _walk_source_modules(root: Path) -> list[str]:
    """Every importable module under core/, ui_qt/, utils/ (source mode)."""
    modules: list[str] = []
    for package in ("core", "ui_qt", "utils"):
        pkg_dir = root / package
        if not pkg_dir.is_dir():
            continue
        for py in sorted(pkg_dir.rglob("*.py")):
            rel = py.relative_to(root)
            if "__pycache__" in rel.parts:
                continue
            stem = rel.stem
            parts = list(rel.with_suffix("").parts)
            if stem == "__init__":
                parts = parts[:-1]
            if not parts:
                continue
            modules.append(".".join(parts))
    modules.extend(["controller", "app_paths"])
    return modules


def _manifest_modules(root: Path) -> list[str] | None:
    """Frozen mode: module list baked in at build time, if present."""
    for candidate in (root / _MANIFEST_NAME, Path(sys.executable).parent / _MANIFEST_NAME):
        try:
            if candidate.is_file():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                mods = data.get("modules") or []
                if mods:
                    return list(mods)
        except Exception:
            continue
    return None


def _check_runtime_packages(fail: list[str]) -> None:
    for pkg in _RUNTIME_PACKAGES:
        try:
            if importlib.util.find_spec(pkg) is None:
                fail.append(f"runtime-package {pkg}: not present in the bundle")
        except Exception as exc:  # find_spec itself blew up
            fail.append(f"runtime-package {pkg}: find_spec raised {type(exc).__name__}: {exc}")


def _check_data_files(fail: list[str]) -> None:
    from app_paths import resource_path

    # VERSION — the single source of truth, read by four modules at runtime.
    version_file = resource_path("VERSION")
    try:
        if not version_file.read_text(encoding="utf-8").strip():
            fail.append(f"data VERSION: {version_file} is empty")
    except Exception as exc:
        fail.append(f"data VERSION: cannot read {version_file}: {exc}")

    # Prompt bank — through the REAL resolution logic (PromptManager).
    try:
        from core.summarisation.prompt_manager import PromptManager

        pm = PromptManager()  # also re-syncs the mirror into the user dir
        listed = pm.list_prompts()
        if len(listed) < 40:
            fail.append(
                f"data prompts: only {len(listed)} prompt(s) found — the prompt "
                f"bank should ship 50+ templates"
            )
        for name in _KEY_PROMPTS:
            try:
                content = pm.load_prompt(name)
                if not content or not content.strip():
                    fail.append(f"data prompts: {name}.md loaded empty")
            except Exception as exc:
                fail.append(f"data prompts: {name} raised {type(exc).__name__}: {exc}")
        missing = [n for n in _KEY_PROMPTS if n not in listed]
        if missing:
            fail.append(f"data prompts: missing from the bank: {', '.join(missing)}")
    except Exception as exc:
        fail.append(
            f"data prompts: PromptManager failed: {type(exc).__name__}: {exc}"
            + (f"\n    {traceback.format_exc(limit=3)}" if "-v" in sys.argv else "")
        )

    # Fonts — required for Farsi/Arabic PDF output.
    for font in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"):
        p = resource_path("assets") / "fonts" / font
        if not p.is_file():
            fail.append(f"data fonts: missing {p}")

    # Segmentation patterns — parsed as JSON at runtime.
    patterns = resource_path("utils") / "patterns.json"
    try:
        json.loads(patterns.read_text(encoding="utf-8"))
    except Exception as exc:
        fail.append(f"data patterns.json: {patterns} not loadable: {exc}")

    # Postcheck lexicon — gzip data inside the core package.
    lexicon = (
        resource_path("core") / "summarisation" / "postchecks" / "data" / ("english_lexicon.txt.gz")
    )
    if not lexicon.is_file():
        fail.append(f"data lexicon: missing {lexicon}")

    # Default chapter keywords file (the bundle ships a read-only copy).
    keywords = resource_path("config") / "chapter_keywords.md"
    if not keywords.is_file():
        fail.append(f"data config: missing {keywords}")

    # Bundled external tools (frozen only): the installer ships ffmpeg +
    # poppler so the transcribe/OCR pipelines work out of the box.
    try:
        from app_paths import bundled_tools_dir, is_frozen

        if is_frozen() and bundled_tools_dir().is_dir():
            for tool in ("ffmpeg.exe", "pdftoppm.exe"):
                if not (bundled_tools_dir() / tool).is_file():
                    fail.append(f"data tools: bundled {tool} missing from the bundle")
    except Exception as exc:
        fail.append(f"data tools: bundle check raised {type(exc).__name__}: {exc}")

    # Icon — optional, no failure when absent.
    return None


def run_selftest(report_file: str | Path = "selftest_report.txt") -> int:
    """Run the full self-test. Returns the number of failures (0 = pass).

    Writes one line per failure to ``report_file`` plus a summary; prints
    progress to stdout. Never opens a window, never starts the Qt event loop.
    """
    # V0.6.67b: the offscreen platform is a property of THE SELFTEST RUN —
    # set it here (before the first PySide6 import below), never at module
    # import time (see the module note: that poisoned every normal launch
    # since V0.6.63 into a headless GUI).
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    started = time.perf_counter()
    root = _repo_root()
    fail: list[str] = []
    lines: list[str] = []

    # Offscreen QApplication — defensive: if any imported module constructs a
    # QWidget at import time, this keeps it from crashing headlessly.
    _qapp = None
    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            _qapp = QApplication([])
    except Exception as exc:
        fail.append(f"PySide6: could not create offscreen QApplication: {exc}")

    # ── 1. import every app module ────────────────────────────────────────
    modules = _manifest_modules(root) or _walk_source_modules(root)
    if not modules:
        fail.append("module-walk: no app modules found (neither manifest nor source tree)")
        modules = []
    total = len(modules)
    import_fail = 0
    t0 = time.perf_counter()
    for i, mod in enumerate(modules, 1):
        try:
            importlib.import_module(mod)
        except Exception as exc:
            import_fail += 1
            tb = traceback.format_exc(limit=4).replace("\n", "\n    ")
            fail.append(f"import {mod}: {type(exc).__name__}: {exc}\n    {tb}")
        if i % 25 == 0 or i == total:
            print(f"  [selftest] imported {i}/{total} modules ...", flush=True)
    import_secs = time.perf_counter() - t0

    # ── 2. runtime packages loaded by name ────────────────────────────────
    _check_runtime_packages(fail)

    # ── 3. data files ─────────────────────────────────────────────────────
    _check_data_files(fail)

    # ── report ─────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - started
    frozen = bool(getattr(sys, "frozen", False))
    lines.append("Elixir self-test report")
    lines.append(
        f"  mode      : {'frozen (installed/packed) build' if frozen else 'source checkout'}"
    )
    lines.append(f"  root      : {root}")
    lines.append(f"  python    : {sys.version.split()[0]} ({sys.executable})")
    lines.append(
        f"  modules   : {total} imported in {import_secs:.1f}s ({import_fail} import failure(s))"
    )
    lines.append(f"  duration  : {elapsed:.1f}s")
    lines.append("")
    if fail:
        lines.append(f"FAILURES ({len(fail)}):")
        for f in fail:
            lines.append(f"  [FAIL] {f}")
    else:
        lines.append("RESULT: PASS — no failures.")
    lines.append("")

    report_path = Path(report_file)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        print(f"[selftest] could not write report {report_path}: {exc}", file=sys.stderr)

    print("\n".join(lines))
    return len(fail)


def maybe_run_cli(argv: list[str]) -> int | None:
    """CLI entry for ``--selftest``. Returns the process exit code when the
    flag is present (0 = pass, 1 = failures), or ``None`` when it is absent
    so the normal app launch continues. Called from ``main.py``'s
    ``__main__`` block — the first thing it does, before any window."""
    if "--selftest" not in argv:
        return None
    # V0.6.67b: the offscreen platform belongs to THE SELFTEST PROCESS
    # ONLY — set at dispatch time (never at module import time: main.py
    # imports this module on every launch, and the old import-time
    # setdefault ran every release V0.6.63 → V0.6.66 headless — the
    # "installed … doesn't open" saga). run_selftest re-asserts it for
    # direct callers.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    idx = argv.index("--selftest")
    report = (
        argv[idx + 1]
        if len(argv) > idx + 1 and not argv[idx + 1].startswith("-")
        else "selftest_report.txt"
    )
    return 0 if run_selftest(report) == 0 else 1


if __name__ == "__main__":  # pragma: no cover — manual use
    _path = sys.argv[sys.argv.index("--selftest") + 1] if "--selftest" in sys.argv[1:] else None
    sys.exit(run_selftest(_path or "selftest_report.txt"))
