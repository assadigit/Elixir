"""V0.7.0 (wizard rework ②) — the dead-flag purge pins (D3's same-pass list).

Per the Round-2 plan §2 item 2d + the Round-1 audit's dead-code register:

- ``auto_detect_scanned`` — carried on the request but NEVER read
  (log-only, settings_logger.py:119; page detection always runs). Purged:
  ZERO readers may remain in runtime code.
- preset ``content_filter.min_*`` — hardcoded 80/0.40 inside the filter;
  the preset values never reached it. Purged from the preset bundles.
- ``is_academic`` in ``to_ui_data`` — never in the request map; the
  converter re-derives it from source_type. Purged from the ui_data dict
  (the ContentFilter PARAM and its settings.py default are a different,
  functional layer and stay).

The pins use the audit's method: a pre-purge grep sweep per flag, then
assert zero (scoped) readers.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# The Rule-1 deny-list scope (tests/test_v182039_audit_fixes.py): the
# runtime tree. Docs, release notes, and the audit/plan files are the
# evidence, not the runtime; tests are pinned separately below.
_RUNTIME_DIRS = [
    _project_root / "core",
    _project_root / "utils",
    _project_root / "ui_qt",
    _project_root / "config",
    _project_root / "prompts",
    _project_root / "installer",
    _project_root / "assets",
]
_RUNTIME_FILES = [
    _project_root / "controller.py",
    _project_root / "main.py",
]


def _runtime_sources() -> list[Path]:
    out: list[Path] = []
    for d in _RUNTIME_DIRS:
        if d.exists():
            out.extend(p for p in d.rglob("*.py") if p.is_file())
    out.extend(p for p in _RUNTIME_FILES if p.exists())
    return out


def _read_runtime(p: Path) -> str:
    """V0.7.7 amendment (audit HY-1): utils/settings.py's legacy-file
    migration del-loop is the SANCTIONED purge of the dead keys (the
    v0740 'no reader outside the purge itself' pattern) — its lines are
    stripped before the zero-reader sweep; every other mention anywhere
    still fails the pin."""
    src = p.read_text(encoding="utf-8")
    if p.name == "settings.py" and p.parent.name == "utils":
        kept, skipping = [], False
        for line in src.splitlines(keepends=True):
            if "for _ocr_dead_key in (" in line:
                skipping = True
                continue
            if skipping:
                if line.strip().startswith(")"):
                    skipping = False
                continue
            kept.append(line)
        src = "".join(kept)
    return src


# ═══════════════════════════════════════════════════════════════════════════
# auto_detect_scanned — zero readers anywhere in runtime code
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoDetectScannedPurged:
    def test_zero_runtime_readers(self):
        offenders = [
            str(p.relative_to(_project_root))
            for p in _runtime_sources()
            if "auto_detect_scanned" in _read_runtime(p)
        ]
        assert offenders == [], (
            "auto_detect_scanned is dead (log-only) and was purged in "
            "V0.7.0 — these runtime files still reference it: " + ", ".join(offenders)
        )

    def test_zero_test_references(self):
        """The test tree keeps no stale stubs for the dead flag either
        (the purge pins + the V0.7.7 legacy-pop pin are the grep needles)."""
        _needles = {Path(__file__).name, "test_v0760_audit.py"}
        offenders = []
        for p in (_project_root / "tests").glob("test_*.py"):
            if p.name in _needles:
                continue
            if "auto_detect_scanned" in p.read_text(encoding="utf-8"):
                offenders.append(p.name)
        for p in (_project_root / "tests").glob("*.py"):
            if p.name not in _needles and "auto_detect_scanned" in p.read_text(encoding="utf-8"):
                offenders.append(p.name)
        assert offenders == [], f"stale auto_detect_scanned test stubs: {offenders}"

    def test_request_field_gone(self):
        import dataclasses

        from core.models import ConversionRequest

        names = {f.name for f in dataclasses.fields(ConversionRequest)}
        assert "auto_detect_scanned" not in names


# ═══════════════════════════════════════════════════════════════════════════
# preset content_filter.min_* — purged from the bundles
# ═══════════════════════════════════════════════════════════════════════════


class TestPresetContentFilterKeysPurged:
    def test_no_content_filter_keys_in_presets(self):
        from ui_qt.settings.presets import PRESETS

        offenders = []
        for key, preset in PRESETS.items():
            for setting_key in preset.get("settings", {}):
                if setting_key.startswith("content_filter."):
                    offenders.append(f"{key}.{setting_key}")
        assert offenders == [], f"dead content_filter.min_* preset keys: {offenders}"

    def test_presets_speak_ocr_mode(self):
        """Every preset bundle carries the 3-mode vocabulary; the two
        full-OCR presets map to scanned (the deprecated flag's meaning)."""
        from ui_qt.settings.presets import PRESETS

        for key, preset in PRESETS.items():
            assert "ocr.mode" in preset["settings"], f"{key}: no ocr.mode"
            assert preset["settings"]["ocr.mode"] in ("auto", "digital", "scanned")
        assert PRESETS["full_ocr"]["settings"]["ocr.mode"] == "scanned"
        assert PRESETS["infographics_slides"]["settings"]["ocr.mode"] == "scanned"
        assert PRESETS["normal_book"]["settings"]["ocr.mode"] == "auto"

    def test_unified_applier_exists_and_applies(self):
        from ui_qt.settings.presets import apply_preset_settings

        applied: dict = {}
        bundle = apply_preset_settings(lambda k, v: applied.__setitem__(k, v), "full_ocr")
        assert applied["ocr.mode"] == "scanned"
        assert applied["source_type"] == "normal_book"
        assert bundle is not None

    def test_settings_dialog_uses_the_unified_applier(self):
        """The split-brain fix: the Settings page routes through
        apply_preset_settings, not its own hand-rolled loop."""
        src = (_project_root / "ui_qt" / "settings" / "settings_dialog.py").read_text(
            encoding="utf-8"
        )
        assert "apply_preset_settings(self.controller.update_setting, key)" in src
        assert 'for sk, sv in preset["settings"].items():' not in src, (
            "the hand-rolled applier loop must be gone"
        )


# ═══════════════════════════════════════════════════════════════════════════
# is_academic in to_ui_data — purged from the ui_data dict
# ═══════════════════════════════════════════════════════════════════════════


class TestIsAcademicPurgedFromUiData:
    def test_to_ui_data_has_no_is_academic_key(self):
        """AST-scoped: the dict literal returned by WizardState.to_ui_data
        carries no is_academic key (the request map never read it; the
        converter re-derives it from source_type — converter_impl.py)."""
        src = (_project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        to_ui = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "to_ui_data":
                to_ui = node
                break
        assert to_ui is not None, "WizardState.to_ui_data not found"
        keys = set()
        for node in ast.walk(to_ui):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant):
                        keys.add(k.value)
        assert "is_academic" not in keys, "is_academic must stay out of to_ui_data"
        # The round-trip discipline: the new mode key IS in the dict.
        assert "ocr_mode" in keys
