"""V0.7.1 (wizard rework ③) — the deprecated-alias purge pins.

V0.7.0 (wizard rework ②, D3) mapped ``force_ocr_all_pages`` →
``ocr_mode="scanned"`` for ONE release — the B2 fix's compatibility
window. V0.7.1, one version later, purges it everywhere (the V0.7.0
dead-flag purge pattern, tests/test_v0700_dead_flags_purged.py):

- the ConversionRequest field, the _REQUEST_FIELD_MAP row, the
  settings.json default, the ContentPreset dataclass field (dead,
  never read), resolve_ocr_mode's alias branch, the Step-3 checkbox,
  Step 1's reset line, Step 8's review line, the queue-view ui_data
  entry, the start-log line, the save_book_settings entry, and the
  settings_logger line — ALL gone.

The pins use the audit's method: a pre-purge grep sweep, then assert
zero (scoped) readers — the literal name may not appear in ANY runtime
file or non-pin test (comments included; the historical record lives
in the CHANGELOG and the release notes, which are not scanned).

NOTE on the literal below: this pin file is the ONE place the name may
appear — it IS the grep needle.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

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

# The purge needle — the deprecated alias purged in V0.7.1 after its
# one-release compatibility window (V0.7.0).
_ALIAS = "force" + "_ocr" + "_all" + "_pages"  # assembled: this file may name it
_DEAD_FLAG = "auto" + "_detect" + "_scanned"  # assembled (the v0700 sweep is raw-string)


def _runtime_sources() -> list[Path]:
    out: list[Path] = []
    for d in _RUNTIME_DIRS:
        if d.exists():
            out.extend(p for p in d.rglob("*.py") if p.is_file())
    out.extend(p for p in _RUNTIME_FILES if p.exists())
    return out


def _read_runtime(p: Path) -> str:
    """V0.7.7 amendment (audit HY-1): utils/settings.py's legacy-file
    migration del-loop is the SANCTIONED purge of the dead OCR keys (the
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
# Zero readers anywhere in runtime code
# ═══════════════════════════════════════════════════════════════════════════


class TestAliasPurged:
    def test_zero_runtime_readers(self):
        offenders = [
            str(p.relative_to(_project_root))
            for p in _runtime_sources()
            if _ALIAS in _read_runtime(p)
        ]
        assert offenders == [], (
            "the deprecated full-OCR alias was purged in V0.7.0+V0.7.1 "
            "(mapped → ocr_mode='scanned' for one release, then removed) — "
            "these runtime files still reference it: " + ", ".join(offenders)
        )

    def test_zero_test_references(self):
        """The test tree keeps no stale stubs for the purged alias either
        (this pin file + the V0.7.7 legacy-pop pin are the grep needles)."""
        _needles = {Path(__file__).name, "test_v0760_audit.py"}
        offenders = []
        for p in (_project_root / "tests").glob("*.py"):
            if p.name in _needles:
                continue
            if _ALIAS in p.read_text(encoding="utf-8"):
                offenders.append(p.name)
        assert offenders == [], f"stale alias test stubs: {offenders}"

    def test_request_field_gone(self):
        from core.models import ConversionRequest

        names = {f.name for f in dataclasses.fields(ConversionRequest)}
        assert _ALIAS not in names, "the request field is purged (V0.7.1)"

    def test_settings_default_gone(self):
        # V0.7.7 amendment (audit HY-1): the intent is the DEFAULTS dict
        # carries no such key and no migration list can re-add it. The
        # legacy-file pop (the sanctioned purge, V0.7.7) legitimately
        # names the key — the v0740 reader-vs-purge pattern. The pin now
        # asserts the DATA (the real _defaults()) + the no-resurrection
        # tuple form, not whole-file string absence.
        from utils.settings import Settings

        defaults = Settings.__new__(Settings)._defaults()
        assert _ALIAS not in defaults.get("ocr", {}), "the settings default key is purged (V0.7.1)"
        assert _DEAD_FLAG not in defaults.get("ocr", {})
        src = (_project_root / "utils" / "settings.py").read_text(encoding="utf-8")
        assert f"({_ALIAS!r}" not in src, "no migration add-missing-keys list re-adds the alias"

    def test_content_preset_field_gone(self):
        """ContentPreset carried the field dead (never read by anything)."""
        from dataclasses import fields as dc_fields

        from core.llm.content_presets import ContentPreset

        names = {f.name for f in dc_fields(ContentPreset)}
        assert _ALIAS not in names, "the ContentPreset field is purged (V0.7.1)"

    def test_wizard_state_field_gone(self):
        from dataclasses import fields as dc_fields

        from ui_qt.views.wizard_steps.shared import WizardState

        names = {f.name for f in dc_fields(WizardState)}
        assert _ALIAS not in names, "the WizardState field is purged (V0.7.1)"

    def test_to_ui_data_key_gone(self):
        """AST-scoped: to_ui_data's returned dict carries no purged key."""
        import ast

        src = (_project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "to_ui_data":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                        for k in sub.value.keys:
                            if isinstance(k, ast.Constant):
                                assert k.value != _ALIAS, "to_ui_data key purged (V0.7.1)"


# ═══════════════════════════════════════════════════════════════════════════
# The post-purge resolution contract (relocated from test_v0700_ocr_mode)
# ═══════════════════════════════════════════════════════════════════════════


class TestPostPurgeResolution:
    def test_stray_alias_attribute_is_ignored(self):
        """A stray attribute with the purged name (e.g. an object built by
        an older caller) must NOT affect resolution — ocr_mode is the only
        reading axis; unknown attributes are invisible to the resolver."""
        from core.pipeline.conversion.extraction import resolve_ocr_mode

        for mode in ("auto", "digital", "scanned"):
            req = SimpleNamespace(ocr_mode=mode)
            setattr(req, _ALIAS, True)  # the stray, post-purge attribute
            assert resolve_ocr_mode(req) == mode, (
                "a stray purged attribute must never override an explicit mode"
            )
        # And from auto, the stray attribute no longer forces scanned.
        req = SimpleNamespace(ocr_mode="auto")
        setattr(req, _ALIAS, True)
        assert resolve_ocr_mode(req) == "auto"

    def test_saved_config_with_the_key_still_builds(self):
        """A .conversion_config.json saved by V0.7.0 (which carried the
        key) loads through build_request_from_ui without it ever reaching
        the request — the map row is gone, so the key is ignored."""
        pytest.importorskip("controller")
        import controller as controller_mod

        class _FakeSettings:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, path, default=None):
                return self._data.get(path, default)

            def set(self, path, value):
                self._data[path] = value

        saved = {
            "input_path": "book.pdf",
            "output_dir": "out",
            "ocr_mode": "scanned",
            _ALIAS: True,  # a V0.7.0-era config would carry this
        }
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
            request = controller_mod.Controller().build_request_from_ui(saved)
            assert request.ocr_mode == "scanned"
            assert not hasattr(request, _ALIAS), (
                "the stray key must never reach the request (no map row)"
            )
        finally:
            monkeypatch.undo()
