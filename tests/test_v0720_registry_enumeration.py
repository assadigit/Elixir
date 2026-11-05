"""V0.7.2 (wizard rework ④, item 4d — audit §3 B8) — the registry-driven
output enumeration.

Bug B8: the Review step's outputs line (step8_review.py:156-183) and the
conversion start-log (wizard_view.py:880-909) hand-enumerated the selected
outputs and silently omitted 9-10 of the newer ones (packets, qa, glossary,
patterns, cheatsheet, skill, evidence map, epub, quote_bank, compact).

The fix is STRUCTURAL, not enumerative: both surfaces now enumerate through
``core.outputs.registry.selected_output_names`` — driven from
``OUTPUT_REGISTRY``, so they can never drift from it again. B9's honest
TTS wording ("built from the executive briefing", podcast_audio.py:108-131)
rides along on every surface.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP8 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step8_review.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# The stub-registry pin (the never-drift guarantee)
# ═══════════════════════════════════════════════════════════════════════════


class TestStubRegistryEnumeration:
    """Feed a stub registry; EVERY key's short name must appear.

    If a future edit breaks the registry-driven wiring (e.g. someone
    re-hardcodes the list), these tests fail — that is their entire job.
    """

    def test_every_stub_key_appears(self, monkeypatch):
        from core.outputs import registry as reg

        stubs = [
            reg.OutputSpec(
                key="alpha",
                label="Alpha Output",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.alpha",
                wizard_attr="outputs_alpha",
                short_name="alpha one",
            ),
            reg.OutputSpec(
                key="beta",
                label="Beta Output",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.beta",
                wizard_attr="outputs_beta",
            ),
            reg.OutputSpec(
                key="gamma",
                label="Gamma Output",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.gamma",
                wizard_attr="outputs_gamma",
                short_name="gamma three",
            ),
        ]
        monkeypatch.setattr(reg, "OUTPUT_REGISTRY", stubs)
        state = SimpleNamespace(outputs_alpha=True, outputs_beta=True, outputs_gamma=True)
        # No generate_summaries attr → default True (duck-typed source).
        names = reg.selected_output_names(state)
        assert names == ["alpha one", "Beta Output", "gamma three"], (
            "every stub key must enumerate (label fallback when short_name empty)"
        )

    def test_deprecated_stub_never_appears(self, monkeypatch):
        from core.outputs import registry as reg

        stubs = [
            reg.OutputSpec(
                key="kept",
                label="Kept",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.kept",
                wizard_attr="outputs_kept",
                short_name="kept name",
            ),
            reg.OutputSpec(
                key="dead",
                label="Dead",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.dead",
                wizard_attr="outputs_dead",
                short_name="dead name",
                deprecated=True,
            ),
        ]
        monkeypatch.setattr(reg, "OUTPUT_REGISTRY", stubs)
        state = SimpleNamespace(outputs_kept=True, outputs_dead=True)
        assert reg.selected_output_names(state) == ["kept name"], (
            "deprecated outputs are never enumerated (D6)"
        )

    def test_summary_children_gated_by_master_switch(self, monkeypatch):
        from core.outputs import registry as reg

        stubs = [
            reg.OutputSpec(
                key="summaries",
                label="Summaries",
                subtitle="",
                icon_name="file-text",
                default=True,
                setting_key="summarisation.enabled",
                wizard_attr="generate_summaries",
            ),
            reg.OutputSpec(
                key="child",
                label="Child",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="summarisation.child",
                wizard_attr="child_flag",
                short_name="child name",
                summary_child=True,
            ),
            reg.OutputSpec(
                key="independent",
                label="Independent",
                subtitle="",
                icon_name="book",
                default=False,
                setting_key="outputs.independent",
                wizard_attr="independent_flag",
                short_name="independent name",
            ),
        ]
        monkeypatch.setattr(reg, "OUTPUT_REGISTRY", stubs)
        # Master ON: child + independent both listed; the master switch
        # itself is never an output.
        on_state = SimpleNamespace(generate_summaries=True, child_flag=True, independent_flag=True)
        assert reg.selected_output_names(on_state) == ["child name", "independent name"]
        # Master OFF: the child no-ops (audit §W6) and is not listed;
        # the independent output still is.
        off_state = SimpleNamespace(
            generate_summaries=False, child_flag=True, independent_flag=True
        )
        assert reg.selected_output_names(off_state) == ["independent name"]

    def test_unset_flags_never_appear(self):
        from core.outputs.registry import selected_output_names

        empty = SimpleNamespace(generate_summaries=True)
        assert selected_output_names(empty) == []


# ═══════════════════════════════════════════════════════════════════════════
# The real registry: completeness + honesty pins
# ═══════════════════════════════════════════════════════════════════════════


class TestRealRegistryEnumeration:
    def test_all_flags_on_lists_every_non_deprecated_output(self):
        """The never-drift pin: with every flag on, all 18 non-deprecated
        outputs appear — including the 10 the audit found omitted (B8)."""
        from core.outputs.registry import selected_output_names

        state = SimpleNamespace(
            generate_summaries=True,
            include_executive_summary=True,
            include_thorough_summary=True,
            include_keypoints=True,
            simplified_keypoints_enabled=True,
            compact_summaries=True,
            generate_docx=True,
            outputs_briefing=True,
            outputs_podcast=True,
            outputs_tts=True,
            outputs_flashcards=True,
            outputs_packets=True,
            outputs_obsidian=True,
            outputs_study_guide=True,
            outputs_mindmap=True,
            outputs_qa=True,
            outputs_glossary=True,
            outputs_epub=True,
            outputs_evidence_map=True,
            # deprecated: set True — must STILL not appear (D6)
            outputs_social=True,
            outputs_patterns=True,
            outputs_cheatsheet=True,
            outputs_skill=True,
            outputs_quote_bank=True,
        )
        names = selected_output_names(state)
        expected = {
            "exec summary",
            "thorough summary",
            "keypoints",
            "simplified keypoints",
            "compact summaries",
            "DOCX",
            "briefing",
            "podcast script",
            "TTS audio (from briefing)",
            "flashcards",
            "packets",
            "obsidian KB",
            "study guide",
            "mind map",
            "Q&A",
            "glossary",
            "EPUB",
            "evidence map",
        }
        assert set(names) == expected, (
            f"enumeration drifted from the registry: missing={expected - set(names)}, "
            f"extra={set(names) - expected}"
        )
        assert len(names) == 18

    def test_wizardstate_round_trip_source(self):
        """selected_output_names reads the REAL WizardState field names —
        pin the three flags that joined the registry (V0.7.2)."""
        from core.outputs.registry import get_output_by_key

        for key, attr in (
            ("executive_summary", "include_executive_summary"),
            ("thorough_summary", "include_thorough_summary"),
            ("keypoints", "include_keypoints"),
            ("simplified_keypoints", "simplified_keypoints_enabled"),
            ("compact_summaries", "compact_summaries"),
            ("docx", "generate_docx"),
        ):
            spec = get_output_by_key(key)
            assert spec is not None and spec.wizard_attr == attr

    def test_wizardstate_defaults_enumerate_honestly(self):
        """A default WizardState (no Qt needed via the dataclass fields):
        exec + thorough + keypoints + simplified on (children of the
        master switch); nothing else."""
        from core.outputs.registry import selected_output_names

        state = SimpleNamespace(
            generate_summaries=True,
            include_executive_summary=True,
            include_thorough_summary=True,
            include_keypoints=True,
            simplified_keypoints_enabled=True,
            compact_summaries=False,
            generate_docx=True,
            outputs_briefing=False,
            outputs_podcast=False,
            outputs_tts=False,
            outputs_flashcards=False,
            outputs_packets=False,
            outputs_obsidian=False,
            outputs_study_guide=False,
            outputs_mindmap=False,
            outputs_qa=False,
            outputs_glossary=False,
            outputs_epub=False,
            outputs_evidence_map=False,
        )
        assert selected_output_names(state) == [
            "exec summary",
            "thorough summary",
            "keypoints",
            "simplified keypoints",
            "DOCX",
        ]


# ═══════════════════════════════════════════════════════════════════════════
# B9 — the honest TTS copy (podcast_audio.py:108-131 reads the briefing)
# ═══════════════════════════════════════════════════════════════════════════


class TestB9HonestTTSCopy:
    def test_registry_tts_says_briefing_not_script(self):
        from core.outputs.registry import get_output_by_key

        tts = get_output_by_key("tts")
        assert tts is not None
        assert "briefing" in tts.label + tts.subtitle + tts.short_name
        assert "needs script" not in tts.label + tts.subtitle
        assert "Generate script first" not in tts.subtitle

    def test_evidence_map_copy_is_honest(self):
        from core.outputs.registry import get_output_by_key

        ev = get_output_by_key("evidence_map")
        assert ev is not None
        assert "langextract" in ev.subtitle
        assert "guidance page" in ev.subtitle, "the without-the-extra degradation"


# ═══════════════════════════════════════════════════════════════════════════
# Source pins: both surfaces consume the helper (B8, structurally)
# ═══════════════════════════════════════════════════════════════════════════


class TestB8SourcePins:
    def test_step8_review_enumerates_from_registry(self):
        src = _src(_STEP8)
        # V0.7.4 (rework ⑥): the import went multi-line (it gained the
        # translation mapping helpers) — the pin still asserts the
        # registry is the source of the enumeration.
        assert "from core.outputs.registry import (" in src
        assert "selected_output_names," in src
        assert "outs = selected_output_names(s)" in src
        # The old hand-enumerated lines are gone (the drift source).
        for gone in (
            'outs.append("exec summary")',
            'outs.append("social")',
            'outs.append("TTS audio")',
        ):
            assert gone not in src, f"hand-enumerated output line is back: {gone}"

    def test_wizard_start_log_enumerates_from_registry(self):
        src = _src(_WIZARD)
        assert "from core.outputs.registry import selected_output_names" in src
        assert "outs = selected_output_names(s)" in src
        for gone in (
            'outs.append("exec_summary")',
            'outs.append("podcast_audio")',
            'outs.append("social")',
        ):
            assert gone not in src, f"hand-enumerated output line is back: {gone}"


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer: the REAL Step 8 line enumerates everything (needs PySide6)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


class _StubController:
    def __init__(self):
        self._settings: dict = {}

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value


class TestStep8Offscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_review_line_lists_every_selected_output(self, app):
        """The B8 functional pin: with everything on, the review summary
        carries every name — including the ten the audit found omitted."""
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step8_review import Step8Review

        state = WizardState()
        state.include_executive_summary = True
        state.include_thorough_summary = True
        state.compact_summaries = True
        state.generate_docx = True
        state.outputs_briefing = True
        state.outputs_podcast = True
        state.outputs_tts = True
        state.outputs_flashcards = True
        state.outputs_packets = True
        state.outputs_obsidian = True
        state.outputs_study_guide = True
        state.outputs_mindmap = True
        state.outputs_qa = True
        state.outputs_glossary = True
        state.outputs_epub = True
        state.outputs_evidence_map = True
        # deprecated ones on — must NOT appear
        state.outputs_social = True
        state.outputs_quote_bank = True

        step = Step8Review(_StubController(), state)
        try:
            step.refresh()
            html = step.summary.toPlainText()
            for name in (
                "exec summary",
                "thorough summary",
                "keypoints",
                "simplified keypoints",
                "compact summaries",
                "DOCX",
                "briefing",
                "podcast script",
                "TTS audio (from briefing)",
                "flashcards",
                "packets",
                "obsidian KB",
                "study guide",
                "mind map",
                "Q&A",
                "glossary",
                "EPUB",
                "evidence map",
            ):
                assert name in html, f"B8 regression: {name!r} missing from the review line"
            assert "social" not in html, "deprecated output leaked into the review line"
            assert "quote bank" not in html.lower()
        finally:
            step.hide()
            step.deleteLater()

    def test_review_line_none_state(self, app):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step8_review import Step8Review

        state = WizardState()
        state.generate_summaries = False
        state.include_keypoints = False
        state.simplified_keypoints_enabled = False
        state.generate_docx = False
        step = Step8Review(_StubController(), state)
        try:
            step.refresh()
            assert "(none)" in step.summary.toPlainText()
        finally:
            step.hide()
            step.deleteLater()
