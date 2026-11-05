"""V0.7.6/0.7.7 audit pins — the findings the cleanup+audit session fixed.

HY-1: the V0.7.0/V0.7.1-purged OCR dead keys (ocr.auto_detect_scanned,
ocr.force_ocr_all_pages) lingered in every pre-V0.7.0 settings.json and
tripped two "Unknown setting" validator warnings on every app start —
the V0.7.4 dead-key pop pattern (translation.outputs.packets /
harakat_confident_only) was not applied to them. Fixed in V0.7.7: the
migration pops them so legacy files self-clean on load.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestOcrDeadKeyLegacyPurge:
    """Audit finding HY-1 — the legacy-file pop, pinned the V0.7.4 way."""

    def test_migration_purges_the_ocr_dead_keys_from_a_legacy_file(self, tmp_path):
        """The real Settings._load: a legacy settings.json carrying both
        V0.7.0/V0.7.1-purged OCR keys comes back without them, with the
        living ocr keys intact (the nllb_model / translation-dead-key
        pattern)."""
        legacy = {
            "ocr": {
                "mode": "auto",  # the living axis
                "use_llm": True,  # a living key
                "auto_detect_scanned": True,  # the dead key, ON, in a legacy file
                "force_ocr_all_pages": False,  # the dead key, off, in a legacy file
                "timeout": 120,
            }
        }
        (tmp_path / "settings.json").write_text(json.dumps(legacy), encoding="utf-8")

        from utils.settings import Settings

        Settings._instance = None
        Settings._test_override = None
        try:
            with (
                patch.object(Settings, "_settings_dir", tmp_path),
                patch.object(Settings, "_settings_file", tmp_path / "settings.json"),
            ):
                s = Settings()
                ocr = s.get("ocr", {})
                assert "auto_detect_scanned" not in ocr, (
                    "the dead OCR key must be purged on load (audit HY-1)"
                )
                assert "force_ocr_all_pages" not in ocr, (
                    "the purged full-OCR alias must be purged on load (audit HY-1)"
                )
                # The living keys survive the purge untouched.
                assert ocr.get("mode") == "auto"
                assert ocr.get("use_llm") is True
                assert ocr.get("timeout") == 120
        finally:
            Settings._instance = None
            Settings._test_override = None

    def test_the_pop_lives_in_the_migration_path(self):
        """The pop itself is present in the migration (source pin, the
        V0.7.4 dead-key-pin style)."""
        src = (Path(__file__).resolve().parent.parent / "utils" / "settings.py").read_text(
            encoding="utf-8"
        )
        assert 'for _ocr_dead_key in ("auto_detect_scanned", "force_ocr_all_pages"):' in src
        assert "del ocr[_ocr_dead_key]" in src


@pytest.mark.parametrize(
    "key",
    ["auto_detect_scanned", "force_ocr_all_pages"],
)
def test_ocr_dead_keys_have_zero_runtime_readers(key):
    """Comment-stripped, zero readers in runtime code (the reader-purge
    side of HY-1 — re-asserting the V0.7.0/V0.7.1 purge held; the
    migration's own del is the sanctioned writer)."""
    import re

    root = Path(__file__).resolve().parent.parent
    for p in (
        list((root / "core").rglob("*.py"))
        + list((root / "ui_qt").rglob("*.py"))
        + list((root / "utils").rglob("*.py"))
    ):
        src = p.read_text(encoding="utf-8", errors="ignore")
        code = re.sub(r'"""[\s\S]*?"""', "", src)
        code = re.sub(r"#.*$", "", code, flags=re.M)
        if "settings.py" in str(p) and "del ocr[_ocr_dead_key]" in code:
            continue  # the migration pop is the sanctioned writer
        assert key not in code, f"{key} resurrected in {p}"
