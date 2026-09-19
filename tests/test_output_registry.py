"""V10.30.0 (Sprint 3.8): Tests for the unified output registry.

Verifies the registry's structural integrity + the accessor functions
that the 4 UI surfaces (wizard, dialog, settings, controller) depend on.

Run: ``pytest tests/test_output_registry.py -v``
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load registry.py directly (it's pure dataclass + functions, no deps).
_spec = importlib.util.spec_from_file_location(
    "core.outputs.registry",
    _project_root / "core" / "outputs" / "registry.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)


class TestRegistryStructure:
    def test_registry_has_21_entries(self):
        """4 core + 17 studio = 21 total (V10.35.0: +2 for epub + quote_bank)."""
        assert len(_mod.OUTPUT_REGISTRY) == 21

    def test_core_outputs_count(self):
        assert len(_mod.get_core_outputs()) == 4

    def test_studio_outputs_count(self):
        assert len(_mod.get_studio_outputs()) == 17  # V10.35.0: +2 epub + quote_bank

    def test_core_keys(self):
        keys = [o.key for o in _mod.get_core_outputs()]
        assert keys == ["summaries", "keypoints", "simplified_keypoints", "docx"]

    def test_studio_keys_include_v10_20_21_35(self):
        """The V10.20.0/V10.21.0/V10.35.0 outputs must be present."""
        keys = [o.key for o in _mod.get_studio_outputs()]
        for k in [
            "qa",
            "glossary",
            "patterns",
            "cheatsheet",
            "skill",
            "evidence_map",
            "epub",
            "quote_bank",
        ]:
            assert k in keys, f"{k} missing from studio outputs"


class TestRegistryConsistency:
    def test_every_studio_output_has_all_metadata(self):
        """Every studio OutputSpec must have setting_key, request_attr,
        wizard_attr, generator_class_name, regenerate_key."""
        for o in _mod.get_studio_outputs():
            assert o.setting_key.startswith("outputs."), f"{o.key}: bad setting_key"
            assert o.request_attr.startswith("output_"), f"{o.key}: bad request_attr"
            assert o.wizard_attr.startswith("outputs_"), f"{o.key}: bad wizard_attr"
            assert o.generator_class_name, f"{o.key}: missing generator_class_name"
            assert o.regenerate_key, f"{o.key}: missing regenerate_key"

    def test_every_output_has_unique_regenerate_key(self):
        """No two outputs share a regenerate_key."""
        keys = [o.regenerate_key for o in _mod.get_studio_outputs()]
        assert len(keys) == len(set(keys)), "duplicate regenerate_key"

    def test_every_output_has_unique_setting_key(self):
        keys = [o.setting_key for o in _mod.OUTPUT_REGISTRY]
        assert len(keys) == len(set(keys)), "duplicate setting_key"


class TestAccessors:
    def test_get_output_by_key_found(self):
        o = _mod.get_output_by_key("briefing")
        assert o is not None
        assert o.label == "Executive Briefing"

    def test_get_output_by_key_not_found(self):
        assert _mod.get_output_by_key("nonexistent") is None

    def test_get_output_by_setting_found(self):
        o = _mod.get_output_by_setting("outputs.glossary")
        assert o is not None
        assert o.key == "glossary"

    def test_get_output_by_regenerate_key_found(self):
        o = _mod.get_output_by_regenerate_key("podcast_script")
        assert o is not None
        assert o.key == "podcast"

    def test_get_regenerate_map_has_17_entries(self):
        """The regenerate map must have all 17 studio outputs (V10.35.0: +2)."""
        m = _mod.get_regenerate_map()
        assert len(m) == 17
        for k in [
            "briefing",
            "podcast_script",
            "flashcards",
            "packets",
            "obsidian",
            "study_guide",
            "social",
            "mindmap",
            "podcast_audio",
            "evidence_map",
            "qa",
            "glossary",
            "patterns",
            "cheatsheet",
            "skill",
            "epub",
            "quote_bank",
        ]:
            assert k in m, f"{k} missing from regenerate map"

    def test_get_dialog_outputs_returns_21_tuples(self):
        """The dialog accessor returns (setting_key, label, subtitle, icon, default).
        V10.35.0: 21 entries (4 core + 17 studio)."""
        tuples = _mod.get_dialog_outputs()
        assert len(tuples) == 21
        for t in tuples:
            assert len(t) == 5

    def test_get_settings_section_outputs_returns_17_tuples(self):
        """The settings accessor returns (setting_key, label, default).
        V10.35.0: 17 studio outputs."""
        tuples = _mod.get_settings_section_outputs()
        assert len(tuples) == 17
        for t in tuples:
            assert len(t) == 3
