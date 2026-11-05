"""V0.7.2 (wizard rework ④, items 4a+4b+4c on Step 4) — the pin file.

4a — essentials locked (D7): executive + thorough pre-checked AND
disabled BY CONSTRUCTION; the master "Generate summaries" switch stays
above them as the single off-switch (audit §W6).

4b — five category cards (D8, D6): AUDIO / LEARNING / KNOWLEDGE /
DOCUMENTS / REFERENCE, driven from the registry; the 5 deprecated
outputs gone from the wizard; the streaming checkbox deleted (§W8);
simplified keypoints + compact summaries relocated to REFERENCE; every
checkbox carries a tooltip (§W7); the TTS label says "built from the
executive briefing" (B9) and the evidence map admits the langextract
extra.

4c — icons (D9): every checkbox renders its SVG line-icon (the
registry's icon_name); no emoji on any control label.

Grabs: 740×540 and 820×600, BOTH themes (the phase-gate render, the
test_v0710_step2_promotion.py pattern).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP4 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step4_outputs.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_ICONS = _project_root / "ui_qt" / "components" / "icons.py"

# The §W6 inventory emoji that lived on Step 4's control labels.
_STEP4_EMOJI = ["📦", "📡", "❓", "📖", "🔧", "📋", "🤖", "🗺", "📚", "💬", "🎧", "🎙", "🎓"]


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 4a — the locked essentials (AST pin: checked + disabled BY CONSTRUCTION)
# ═══════════════════════════════════════════════════════════════════════════


class TestEssentialsLockedASt:
    """Parse _build; the two locked checkboxes must be constructed with
    setChecked(True) AND setEnabled(False) following them — the lock is
    structural, not a runtime accident."""

    @staticmethod
    def _locked_calls() -> dict[str, set[str]]:
        tree = ast.parse(_src(_STEP4))
        calls: dict[str, set[str]] = {}
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name == "_build":
                stmts = fn.body
                for i, stmt in enumerate(stmts):
                    # self.<attr> = QCheckBox(<label>)
                    if (
                        isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Name)
                        and stmt.value.func.id == "QCheckBox"
                        and isinstance(stmt.targets[0], ast.Attribute)
                    ):
                        attr = stmt.targets[0].attr
                        label = ""
                        if stmt.value.args and isinstance(stmt.value.args[0], ast.Constant):
                            label = str(stmt.value.args[0].value)
                        if "Executive summary" in label or "Thorough summary" in label:
                            made = set()
                            # scan the next statements for the lock calls
                            for later in stmts[i + 1 : i + 6]:
                                if isinstance(later, ast.Expr) and isinstance(
                                    later.value, ast.Call
                                ):
                                    call = later.value
                                    if (
                                        isinstance(call.func, ast.Attribute)
                                        and isinstance(call.func.value, ast.Attribute)
                                        and call.func.value.attr == attr
                                    ):
                                        if call.args and isinstance(call.args[0], ast.Constant):
                                            made.add(f"{call.func.attr}({call.args[0].value!r})")
                            calls[attr] = made
        return calls

    def test_both_essentials_found(self):
        calls = self._locked_calls()
        assert set(calls) == {"exec_cb", "thorough_cb"}, (
            f"the two locked essentials must be built as exec_cb/thorough_cb, got {set(calls)}"
        )

    def test_checked_and_disabled_by_construction(self):
        for attr, made in self._locked_calls().items():
            assert "setChecked(True)" in made, f"{attr}: not checked by construction"
            assert "setEnabled(False)" in made, f"{attr}: not disabled by construction"
            assert "setChecked(False)" not in made
            assert "setEnabled(True)" not in made

    def test_save_to_state_writes_literal_true(self):
        """The state lock: save_to_state carries literal True for both
        essentials — no checkbox read can ever write False."""
        src = _src(_STEP4)
        assert "self.state.include_executive_summary = True" in src
        assert "self.state.include_thorough_summary = True" in src
        assert "include_executive_summary = self." not in src.replace(
            "self.state.include_executive_summary = True", ""
        )

    def test_essentials_caption(self):
        src = _src(_STEP4)
        assert "Always included — every other output builds on these." in src

    def test_master_switch_above_essentials(self):
        """The master 'Generate summaries' switch is built BEFORE the two
        locked essentials (source order = visual order)."""
        src = _src(_STEP4)
        i_master = src.index('QCheckBox("Generate summaries")')
        i_exec = src.index('QCheckBox("Executive summary')
        assert i_master < i_exec, "the master switch must sit above the essentials"


# ═══════════════════════════════════════════════════════════════════════════
# 4b — the five category cards, the cull, the W8 moves
# ═══════════════════════════════════════════════════════════════════════════


class TestCategoryCards:
    def test_five_categories_declared(self):
        src = _src(_STEP4)
        for title in ("Audio", "Learning", "Knowledge", "Documents", "Reference"):
            assert f'"{title}",' in src, f"the {title} category card is missing"

    def test_category_membership(self):
        """D8's exact membership — registry keys per card."""
        src = _src(_STEP4)
        expected = {
            "Audio": ["podcast", "tts"],
            "Learning": ["flashcards", "qa", "study_guide", "glossary", "packets"],
            "Knowledge": ["obsidian", "mindmap"],
            "Documents": ["docx", "epub"],
            "Reference": [
                "briefing",
                "evidence_map",
                "compact_summaries",
                "simplified_keypoints",
            ],
        }
        # Extract each card tuple from the _CATEGORY_CARDS literal
        # (an AnnAssign: ``_CATEGORY_CARDS: list[...] = [...]``).
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "_CATEGORY_CARDS":
                    cards = ast.literal_eval(node.value)
                    got = {t[0]: t[3] for t in cards}
                    assert got == expected, f"category membership drifted: {got}"
                    return
        raise AssertionError("_CATEGORY_CARDS literal not found")

    def test_no_deprecated_key_in_cards(self):
        """D6: Step 4 builds no deprecated checkbox."""
        src = _src(_STEP4)
        for gone in ("social", "patterns", "cheatsheet", "skill", "quote_bank"):
            assert f'"{gone}"' not in src, f"deprecated output {gone} is back on Step 4"
        assert "outputs_social" not in src
        assert "outputs_quote_bank" not in src

    def test_streaming_control_gone_everywhere_in_ui(self):
        """§W8: the dead streaming checkbox is deleted — zero readers of
        _streaming_enabled anywhere under ui_qt/."""
        for py in (_project_root / "ui_qt").rglob("*.py"):
            assert "_streaming_enabled" not in py.read_text(encoding="utf-8"), (
                f"{py.name} still references the dead _streaming_enabled flag"
            )

    def test_streaming_state_field_purged(self):
        src = _src(_SHARED)
        assert "_streaming_enabled" not in src, "the WizardState field must be gone"

    def test_w8_relocations(self):
        """simplified keypoints + compact summaries live in the REFERENCE
        card (§W8 — both independent gates, moved out of Core)."""
        src = _src(_STEP4)
        ref = src.split('"Reference",', 1)[1].split("]", 1)[0]
        assert "simplified_keypoints" in ref
        assert "compact_summaries" in ref
        # …and NOT in the Core card anymore.
        core = src.split('QGroupBox("Core outputs")', 1)[1].split("_build_category_card", 1)[0]
        assert "Simplified keypoints" not in core
        assert "Compact summaries" not in core

    def test_b9_tts_label_says_briefing(self):
        src = _src(_STEP4)
        assert "TTS audio — built from the executive briefing" in src
        assert "requires podcast script" not in src

    def test_ampersand_escaped_no_qt_mnemonic(self):
        """The V0.7.1 lesson (commit 9270519): a bare & in a checkbox label
        is eaten as a Qt mnemonic — "Q&A" rendered as "QA" with the A
        underlined. The VLM pass caught this exact defect pre-fix."""
        src = _src(_STEP4)
        assert "Study questions (Q&&A)" in src
        # No other bare & in the card labels (the && escape excepted).
        labels = src.split("_CARD_LABELS", 1)[1].split("}", 1)[0]
        bare = [ln for ln in labels.splitlines() if "&" in ln and "&&" not in ln]
        assert not bare, f"bare ampersand (Qt mnemonic) in a label: {bare}"

    def test_evidence_map_honest_label(self):
        src = _src(_STEP4)
        assert "needs the langextract extra" in src
        assert "guidance page" in src, "the without-the-extra degradation"

    def test_no_emoji_on_any_control_label(self):
        src = _src(_STEP4)
        for emo in _STEP4_EMOJI:
            assert emo not in src, f"emoji {emo} is back on a Step-4 control label"


# ═══════════════════════════════════════════════════════════════════════════
# 4c — icons (D9)
# ═══════════════════════════════════════════════════════════════════════════


class TestIcons:
    def test_every_registry_icon_name_exists_in_icon_set(self):
        """The registry's icon_name values must all render — the icon-set
        render contract (a typo'd name raises KeyError in icons.icon)."""
        from core.outputs.registry import OUTPUT_REGISTRY

        icons_src = _src(_ICONS)
        names = re.findall(r'^\s{4}"([a-z0-9-]+)":', icons_src, re.MULTILINE)
        known = set(names)
        for spec in OUTPUT_REGISTRY:
            assert spec.icon_name in known, (
                f"{spec.key}: icon_name {spec.icon_name!r} missing from icons.py"
            )

    def test_new_glyphs_added(self):
        src = _src(_ICONS)
        for glyph in (
            "package",
            "link",
            "graduation-cap",
            "network",
            "map",
            "help-circle",
            "book-open",
            "minimize-2",
            "plug",
        ):
            assert f'"{glyph}":' in src, f"the {glyph} glyph is missing"

    def test_step4_renders_registry_icons(self):
        src = _src(_STEP4)
        assert "from ui_qt.components.icons import icon, pixmap" in src
        assert "icon(spec.icon_name" in src, "checkbox icons come from the registry"


# ═══════════════════════════════════════════════════════════════════════════
# Round-trip pins: every output flag the phase touches
# (WizardState → to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest)
# ═══════════════════════════════════════════════════════════════════════════


class _FakeSettings:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self, path, default=None):
        return self._data.get(path, default)

    def set(self, path, value):
        self._data[path] = value


class TestRoundTrips:
    # (state attr, ui_data key, request attr)
    _FLAGS = [
        ("generate_summaries", "generate_summaries", "generate_summaries"),
        ("include_executive_summary", "include_executive_summary", "include_executive_summary"),
        ("include_thorough_summary", "include_thorough_summary", "include_thorough_summary"),
        ("include_keypoints", "include_keypoints", "include_keypoints"),
        (
            "simplified_keypoints_enabled",
            "simplified_keypoints_enabled",
            "simplified_keypoints_enabled",
        ),
        ("compact_summaries", "compact_summaries", "compact_summaries"),
        ("generate_docx", "generate_docx", "generate_docx"),
        ("outputs_briefing", "output_briefing", "output_briefing"),
        ("outputs_podcast", "output_podcast", "output_podcast"),
        ("outputs_tts", "output_tts", "output_tts"),
        ("outputs_flashcards", "output_flashcards", "output_flashcards"),
        ("outputs_packets", "output_packets", "output_packets"),
        ("outputs_obsidian", "output_obsidian", "output_obsidian"),
        ("outputs_study_guide", "output_study_guide", "output_study_guide"),
        ("outputs_mindmap", "output_mindmap", "output_mindmap"),
        ("outputs_qa", "output_qa", "output_qa"),
        ("outputs_glossary", "output_glossary", "output_glossary"),
        ("outputs_epub", "output_epub", "output_epub"),
        ("outputs_evidence_map", "output_evidence_map", "output_evidence_map"),
    ]

    def test_every_touched_flag_round_trips(self, monkeypatch):
        """The dead-control lesson (§1/B3-class): every flag Step 4 writes
        must flow state → to_ui_data → map → request."""
        pytest.importorskip("controller")
        import controller as controller_mod

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        state.input_path = "book.pdf"
        for attr, _ui_key, _req_attr in self._FLAGS:
            setattr(state, attr, True)
        ui_data = state.to_ui_data()
        request = controller_mod.Controller().build_request_from_ui(ui_data)
        for attr, ui_key, req_attr in self._FLAGS:
            assert ui_data.get(ui_key) is True, f"{attr}: dropped by to_ui_data"
            assert getattr(request, req_attr) is True, f"{attr}: dropped by the map"

    def test_to_ui_data_carries_no_streaming_key(self):
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        assert "_streaming_enabled" not in state.to_ui_data()


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6)
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


class TestStep4Offscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _build(self):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step4_outputs import Step4Outputs

        state = WizardState()
        return Step4Outputs(_StubController(), state), state

    def test_nineteen_checkboxes_no_deprecated_no_streaming(self, app):
        """25 old checkboxes − 5 deprecated − 1 streaming = 19."""
        QtWidgets = _qt_or_skip()
        step, _ = self._build()
        try:
            cbs = step.findChildren(QtWidgets.QCheckBox)
            assert len(cbs) == 19, f"expected 19 checkboxes, got {len(cbs)}"
            texts = " | ".join(cb.text() for cb in cbs)
            for gone in ("Social media", "Patterns", "Cheatsheet", "Agent Skill", "Quote Bank"):
                assert gone not in texts, f"deprecated checkbox built: {gone}"
            assert "Streaming" not in texts, "the dead streaming checkbox is back"
        finally:
            step.hide()
            step.deleteLater()

    def test_essentials_checked_and_disabled(self, app):
        step, _ = self._build()
        try:
            for cb in (step.exec_cb, step.thorough_cb):
                assert cb.isChecked(), "locked on (D7)"
                assert not cb.isEnabled(), "disabled (D7)"
            assert step.master_cb.isEnabled() and step.master_cb.isChecked()
            assert step.keypoints_cb.isEnabled()
        finally:
            step.hide()
            step.deleteLater()

    def test_every_checkbox_has_tooltip_and_icon(self, app):
        """§W7 (tooltips) + D9 (icons): every output checkbox carries both."""
        QtWidgets = _qt_or_skip()
        step, _ = self._build()
        try:
            cbs = step.findChildren(QtWidgets.QCheckBox)
            assert cbs
            for cb in cbs:
                assert cb.toolTip().strip(), f"no tooltip on {cb.text()!r}"
                assert not cb.icon().isNull(), f"no icon on {cb.text()!r}"
        finally:
            step.hide()
            step.deleteLater()

    def test_no_emoji_in_any_label_text(self, app):
        step, _ = self._build()
        try:
            pat = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")
            QtWidgets = _qt_or_skip()
            for cb in step.findChildren(QtWidgets.QCheckBox):
                assert not pat.search(cb.text()), f"emoji on control: {cb.text()!r}"
        finally:
            step.hide()
            step.deleteLater()

    def test_card_state_round_trip(self, app):
        """Every category checkbox writes its registry wizard_attr."""
        step, state = self._build()
        try:
            assert len(step._category_cbs) == 15, "5+2+2+2+4 category checkboxes"
            for _attr, cb in step._category_cbs.items():
                cb.setChecked(True)
            step.master_cb.setChecked(False)
            step.keypoints_cb.setChecked(False)
            step.save_to_state()
            for attr in step._category_cbs:
                assert getattr(state, attr) is True, f"{attr} did not round-trip"
            assert state.generate_summaries is False
            assert state.include_keypoints is False
            # The lock: essentials stay True regardless of any checkbox.
            assert state.include_executive_summary is True
            assert state.include_thorough_summary is True
        finally:
            step.hide()
            step.deleteLater()

    def test_fits_its_viewport_min_size(self, app):
        step, _ = self._build()
        try:
            step.resize(740, 540)
            hint = step.minimumSizeHint() if hasattr(step, "minimumSizeHint") else None
            # The scroll area hosts the content — the step itself must
            # never demand more than the shell gives it.
            assert hint is None or hint.height() <= 560, (
                f"Step 4 needs {hint.height()}px — check the scroll host"
            )
        finally:
            step.hide()
            step.deleteLater()

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size):
        """The phase-gate render: Step 4 at 740×540 and 820×600, BOTH
        themes (the plan's per-phase visual-regression gate)."""
        from ui_qt.theme import theme_manager
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step4_outputs import Step4Outputs

        theme_manager.apply(app, theme)
        state = WizardState()
        step = Step4Outputs(_StubController(), state)
        try:
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step4_{theme}_{size[0]}x{size[1]}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default
