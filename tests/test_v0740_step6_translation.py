"""V0.7.4 (wizard rework ⑥, Step 6) — the pin file.

6a — two selection modes (D15): the master "Translate outputs" switch
carries the "optional — runs after conversion" caption (skipability is
visible, audit §W10); "What to translate" is a radio — "The outputs I
selected in step 4" (the default) vs "Let me choose" (the manual
checkbox list).  Mode A derives ``translation.outputs`` from the Step-4
selection AT START through the registry-driven mapping layer
(``core.outputs.registry.selected_translation_outputs``); the backend
needs no change (translation is a settings-driven post-conversion
phase, controller.py:432-492).  The harakat/judge combos open on the
last-used picks (the V0.7.3 ``_seed_model_combo`` pattern, D14's
"manual picking, auto-remembered") and list live off the UI thread.

6b — honesty: the ``.harakat.md`` output is documented as a
manual-review file (D16 deferred the TTS wiring to the backlog); the
dead settings keys (``translation.outputs.packets``,
``translation.harakat_confident_only``) are purged.

6c — VRAM truth (B7): the conversion-start VRAM check passes the REAL
translator model (the ``translation.model`` setting), not
``summarisation_model`` standing in for the translator.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP6 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step6_translation.py"
_STEP8 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step8_review.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_REGISTRY = _project_root / "core" / "outputs" / "registry.py"
_SETTINGS = _project_root / "utils" / "settings.py"
_TR_PAGE = _project_root / "ui_qt" / "settings" / "translation_page.py"
_HARAKAT = _project_root / "core" / "translation" / "harakat.py"
_SERVICE = _project_root / "core" / "translation" / "service.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the mapping layer (registry-driven, pure, Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


def _selection(**overrides) -> SimpleNamespace:
    """A Step-4-shaped selection source (the wizard_attr flags)."""
    base = dict(
        generate_summaries=True,
        include_executive_summary=True,
        include_thorough_summary=True,
        include_keypoints=True,
        simplified_keypoints_enabled=False,
        compact_summaries=False,
        generate_docx=False,
        outputs_briefing=False,
        outputs_podcast=False,
        outputs_flashcards=False,
        outputs_packets=False,
        outputs_obsidian=False,
        outputs_study_guide=False,
        outputs_social=False,
        outputs_mindmap=False,
        outputs_tts=False,
        outputs_evidence_map=False,
        outputs_qa=False,
        outputs_glossary=False,
        outputs_epub=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestSelectedTranslationOutputs:
    def test_default_selection_derives_summaries_and_keypoints(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert out["chapter_summaries"] is True, "exec+thorough → chapter summaries"
        assert out["keypoints"] is True
        assert out["simplified_keypoints"] is False
        for k in (
            "full_markdown",
            "briefing",
            "podcast",
            "flashcards",
            "obsidian",
            "study_guide",
            "social",
            "mindmap",
        ):
            assert out[k] is False, f"{k} must stay off for the default selection"

    def test_studio_selections_map_one_to_one(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(
                outputs_briefing=True,
                outputs_podcast=True,
                outputs_flashcards=True,
                outputs_obsidian=True,
                outputs_study_guide=True,
                outputs_mindmap=True,
                simplified_keypoints_enabled=True,
            )
        )
        for k in (
            "briefing",
            "podcast",
            "flashcards",
            "obsidian",
            "study_guide",
            "mindmap",
            "simplified_keypoints",
        ):
            assert out[k] is True, f"{k} must follow its Step-4 selection"

    def test_master_switch_gates_the_summary_family(self):
        """generate_summaries off → the summary-family translations no-op
        (audit §W6) — studio outputs are unaffected."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(generate_summaries=False, outputs_briefing=True)
        )
        assert out["chapter_summaries"] is False
        assert out["keypoints"] is False
        assert out["simplified_keypoints"] is False
        assert out["briefing"] is True

    def test_summaries_off_with_both_essentials_on(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(generate_summaries=False))
        assert out["chapter_summaries"] is False

    def test_essentials_off_kills_chapter_summaries(self):
        """Both include flags off (a settings-forced state) → no summary
        files exist → nothing to translate."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(include_executive_summary=False, include_thorough_summary=False)
        )
        assert out["chapter_summaries"] is False
        assert out["keypoints"] is True, "keypoints is a separate flag"

    def test_either_essential_suffices(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(include_thorough_summary=False))
        assert out["chapter_summaries"] is True

    def test_deprecated_social_never_maps(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(outputs_social=True))
        assert out["social"] is False, "deprecated outputs are unselectable on Step 4 (D6)"

    def test_full_markdown_never_derived(self):
        """The whole-book translation is a manual-only choice — it is not a
        Step-4 selection and must never be implicit (the most expensive
        translation job)."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert out["full_markdown"] is False

    def test_result_covers_every_map_key(self):
        """A mode-A Start rewrites the WHOLE selection — every
        translation.outputs key is present (no stale carryover)."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP, selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert set(out) == set(_TRANSLATION_OUTPUT_MAP)
        assert all(isinstance(v, bool) for v in out.values())

    def test_untranslatable_outputs_are_not_keys(self):
        """qa/glossary/packets/tts/epub/docx/compact have no translation
        counterpart (no backend glob) — they must not appear in the map."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP

        for k in (
            "qa",
            "glossary",
            "packets",
            "tts",
            "evidence_map",
            "epub",
            "docx",
            "compact_summaries",
        ):
            assert k not in _TRANSLATION_OUTPUT_MAP


class TestTranslationMapIntegrity:
    """The mapping can never drift from the two lists it mirrors."""

    def test_map_keys_match_the_backend_file_map(self):
        """Every derivation key is a real translation.outputs key the
        backend globs for (core.translation.service._OUTPUT_FILE_MAP)."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP
        from core.translation.service import _OUTPUT_FILE_MAP

        assert set(_TRANSLATION_OUTPUT_MAP) == set(_OUTPUT_FILE_MAP), (
            "the registry mapping and the service file map must list the same keys"
        )

    def test_every_source_key_exists_in_the_registry(self):
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP, OUTPUT_REGISTRY

        reg_keys = {spec.key for spec in OUTPUT_REGISTRY}
        for _label, sources in _TRANSLATION_OUTPUT_MAP.values():
            for src in sources:
                assert src in reg_keys, f"mapping source {src!r} is not a registry key (typo?)"

    def test_labels_match_the_settings_page_list(self):
        """The labels shown in the mode-A review copy are the same labels
        the Settings translation page shows for the manual list."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP

        page_labels = {}
        exec_ns = {}
        src = _src(_TR_PAGE)
        start = src.index("_TRANSLATABLE_OUTPUTS = [")
        end = src.index("]", start) + 1
        exec(src[start:end], exec_ns)  # noqa: S102 — test-local literal parse
        for key, label, _sub in exec_ns["_TRANSLATABLE_OUTPUTS"]:
            page_labels[key] = label
        assert {k: v[0] for k, v in _TRANSLATION_OUTPUT_MAP.items()} == page_labels


class TestTranslationOutputLabel:
    def test_known_keys(self):
        from core.outputs.registry import translation_output_label

        assert translation_output_label("chapter_summaries") == "Chapter summaries"
        assert translation_output_label("full_markdown") == "Full book Markdown"

    def test_unknown_key_passthrough(self):
        from core.outputs.registry import translation_output_label

        assert translation_output_label("anything-else") == "anything-else"


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6) — the V0.7.3 scaffolding pattern
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


class _StubController:
    """The controller surface Step 6 touches (settings + the B1 lister)."""

    def __init__(self, settings=None, models=None, with_lister=True):
        self._settings: dict = dict(settings or {})
        self._models = list(models or [])
        self._with_lister = with_lister

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value

    def list_ollama_models(self):
        if not self._with_lister:
            raise AttributeError("no lister on this stub")
        return list(self._models)


class _FakeSignal:
    def connect(self, *args, **kwargs):
        pass


class _FakeWorker:
    """Captures the worker fn instead of starting a thread — building the
    step offscreen must never touch the network."""

    captured: list = []

    def __init__(self, fn, *args, **kwargs):
        type(self).captured.append(fn)

    finished = _FakeSignal()
    failed = _FakeSignal()

    def is_running(self):
        return False

    def start(self):
        pass


def _build_step6(settings=None, state=None, models=None):
    """Build Step 6 offscreen with the listing worker stubbed (no HTTP)."""
    import ui_qt.views.wizard_steps.step6_translation as step6_mod
    from ui_qt.views.wizard_steps.shared import WizardState
    from ui_qt.views.wizard_steps.step6_translation import Step6Translation

    _FakeWorker.captured = []
    orig = step6_mod.SimpleWorker
    step6_mod.SimpleWorker = _FakeWorker
    try:
        step = Step6Translation(_StubController(settings, models=models), state or WizardState())
    finally:
        step6_mod.SimpleWorker = orig
    return step


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the master switch + the optional caption (§W10 skip visibility)
# ═══════════════════════════════════════════════════════════════════════════


class TestSkipVisibility:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_source_pins_the_optional_caption(self):
        src = _src(_STEP6)
        assert 'QCheckBox("Translate outputs")' in src
        assert '"Optional — runs after conversion."' in src

    def test_the_old_bare_switch_is_gone(self):
        src = _src(_STEP6)
        assert "Translate selected outputs after conversion" not in src

    def test_caption_renders_and_settings_grey_out(self, app):
        step = _build_step6()
        try:
            assert step.enable_cb.text() == "Translate outputs"
            assert step.optional_caption.text() == "Optional — runs after conversion."
            assert step.optional_caption.isVisibleTo(step)
            # Off by default: everything below the switch is disabled.
            assert not step.enable_cb.isChecked()
            assert not step.settings_widget.isEnabled()
            step.enable_cb.setChecked(True)
            assert step.settings_widget.isEnabled()
        finally:
            step.hide()
            step.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the two selection modes (D15)
# ═══════════════════════════════════════════════════════════════════════════


class TestStep6Modes:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_mode_a_is_the_default_and_hides_the_manual_list(self, app):
        step = _build_step6()
        try:
            assert step.mode_a_rb.isChecked(), "mode A ('step 4 selection') is the default"
            assert not step.mode_b_rb.isChecked()
            assert not step.manual_widget.isVisibleTo(step), "the checkbox list is hidden in mode A"
        finally:
            step.hide()
            step.deleteLater()

    def test_mode_b_reveals_the_manual_list(self, app):
        step = _build_step6()
        try:
            step.mode_b_rb.setChecked(True)
            assert step.manual_widget.isVisibleTo(step)
            assert not step.mode_a_rb.isChecked()
        finally:
            step.hide()
            step.deleteLater()

    def test_the_manual_list_is_todays_surface(self, app):
        """Mode B keeps the pre-rework checkbox list (all 11 outputs)."""
        from ui_qt.settings.translation_page import _TRANSLATABLE_OUTPUTS

        step = _build_step6()
        try:
            assert set(step._tr_cbs) == {k for k, _l, _s in _TRANSLATABLE_OUTPUTS}
            assert len(step._tr_cbs) == 11
        finally:
            step.hide()
            step.deleteLater()

    def test_remembered_manual_mode_reopens(self, app):
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        state.translation_selection_mode = "manual"
        step = _build_step6(state=state)
        try:
            assert step.mode_b_rb.isChecked()
            assert step.manual_widget.isVisibleTo(step)
        finally:
            step.hide()
            step.deleteLater()

    def test_mode_round_trips_through_save(self, app):
        step = _build_step6()
        try:
            step.mode_b_rb.setChecked(True)
            step.save_to_state()
            assert step.state.translation_selection_mode == "manual"
            step.mode_a_rb.setChecked(True)
            step.save_to_state()
            assert step.state.translation_selection_mode == "selected"
        finally:
            step.hide()
            step.deleteLater()

    def test_manual_checkboxes_round_trip(self, app):
        step = _build_step6()
        try:
            step._tr_cbs["briefing"].setChecked(True)
            step._tr_cbs["chapter_summaries"].setChecked(False)
            step.save_to_state()
            assert step.state.translation_outputs["briefing"] is True
            assert step.state.translation_outputs["chapter_summaries"] is False
        finally:
            step.hide()
            step.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the model pickers: seeded picks + live listing (the D14 reuse)
# ═══════════════════════════════════════════════════════════════════════════


class TestStep6ComboSeeding:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    _SAVED = {
        "translation.harakat_model": "qwen2.5:7b",
        "translation.judge_model": "translategemma:4b",
    }

    def test_combos_open_on_last_used_picks(self, app):
        """The combos show what the user last chose, BEFORE any listing."""
        step = _build_step6(self._SAVED)
        try:
            assert step.harakat_combo.currentData() == "qwen2.5:7b"
            assert step.judge_combo.currentData() == "translategemma:4b"
        finally:
            step.hide()
            step.deleteLater()

    def test_no_pick_no_junk(self, app):
        step = _build_step6()
        try:
            assert step.harakat_combo.count() == 0
            assert step.judge_combo.count() == 1  # the "(use summarization model)" item
            assert step.judge_combo.currentData() == ""
        finally:
            step.hide()
            step.deleteLater()

    def test_seeded_pick_survives_save_without_refresh(self, app):
        step = _build_step6(dict(self._SAVED))
        try:
            step.save_to_state()
            assert step.state.translation_harakat_model == "qwen2.5:7b"
            assert step.state.translation_judge_model == "translategemma:4b"
        finally:
            step.hide()
            step.deleteLater()


class TestStep6LiveListing:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_listing_repopulates_and_keeps_the_picks(self, app):
        step = _build_step6(
            {
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "translategemma:4b",
            }
        )
        try:
            step._on_models_loaded(["qwen2.5:7b", "translategemma:4b", "gemma3:12b"])
            assert step.harakat_combo.count() == 3
            assert step.judge_combo.count() == 4  # placeholder + 3 models
            assert step.harakat_combo.currentData() == "qwen2.5:7b"
            assert step.judge_combo.currentData() == "translategemma:4b"
            assert "3 model(s) listed" in step.models_hint.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_listing_readds_a_pick_the_server_no_longer_lists(self, app):
        step = _build_step6({"translation.harakat_model": "qwen2.5:7b"})
        try:
            step._on_models_loaded(["some-other-model"])
            assert step.harakat_combo.currentData() == "qwen2.5:7b", (
                "the last-used pick must survive a server that doesn't list it"
            )
            assert step.harakat_combo.findData("qwen2.5:7b") == 0
        finally:
            step.hide()
            step.deleteLater()

    def test_empty_listing_is_never_a_modal(self, app, monkeypatch):
        """The empty case is a muted hint label — a QMessageBox here would
        trap every offscreen test that builds this step (Step 5's modal is
        the cautionary tale)."""
        QtWidgets = _qt_or_skip()

        def _boom(*a, **k):
            raise AssertionError("Step 6's empty listing must not open a modal")

        monkeypatch.setattr(QtWidgets.QMessageBox, "information", _boom)
        monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _boom)
        step = _build_step6()
        try:
            step._on_models_loaded([])
            assert "No models listed" in step.models_hint.text()
            step._on_models_failed(ConnectionError("down"))
            assert "Could not reach" in step.models_hint.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_refresh_rides_the_worker_and_delegates_to_the_b1_method(self, app):
        import ui_qt.views.wizard_steps.step6_translation as step6_mod

        step = _build_step6({"llm.ollama_url": "http://localhost:11434"}, models=["m1", "m2"])
        try:
            assert _FakeWorker.captured, "the build starts a listing worker"
            assert _FakeWorker.captured[-1] == step._fetch_models
            # The worker fn goes through the controller's B1 method.
            assert step._fetch_models() == ["m1", "m2"]
            # A refresh while idle starts another worker (no in-flight
            # stack) — under the stub again (the build window restored
            # the real SimpleWorker).
            orig = step6_mod.SimpleWorker
            step6_mod.SimpleWorker = _FakeWorker
            try:
                step._refresh_models()
            finally:
                step6_mod.SimpleWorker = orig
            assert len(_FakeWorker.captured) == 2
        finally:
            step.hide()
            step.deleteLater()

    def test_worker_fn_degrades_gracefully_without_the_lister(self, app):
        """A stub controller with no lister (or a raising one) must not
        crash the build — the listing degrades to empty."""
        import ui_qt.views.wizard_steps.step6_translation as step6_mod
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step6_translation import Step6Translation

        _FakeWorker.captured = []
        orig = step6_mod.SimpleWorker
        step6_mod.SimpleWorker = _FakeWorker
        try:
            step = Step6Translation(_StubController(with_lister=False), WizardState())
        finally:
            step6_mod.SimpleWorker = orig
        try:
            assert step._fetch_models() == []
        finally:
            step.hide()
            step.deleteLater()

    def test_no_sync_http_on_the_ui_thread(self):
        """The build path never calls the lister synchronously — the only
        call site lives inside the worker fn (the W-b11 pattern)."""
        src = _src(_STEP6)
        assert "models = self.controller.list_ollama_models()" not in src
        assert "return list(self.controller.list_ollama_models() or [])" in src


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the mode-A derivation at Start (the wizard-level behaviour)
# ═══════════════════════════════════════════════════════════════════════════


class TestModeADerivationAtStart:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @staticmethod
    def _wizard(settings=None):
        """A WizardView shell (no full build — the save path only needs
        controller + state, the v0686 wizard_pair pattern)."""
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_view import WizardView

        view = WizardView.__new__(WizardView)
        view.controller = _StubController(settings)
        view.state = WizardState()
        return view

    def test_mode_a_derives_the_outputs_at_start(self, app):
        from core.outputs.registry import selected_translation_outputs

        view = self._wizard({"translation.enabled": True})
        view.state.translation_enabled = True  # the master box is ON
        # A Step-4 shape: summaries family + briefing/podcast selected,
        # keypoints UNselected — very different from the old defaults.
        view.state.include_keypoints = False
        view.state.outputs_briefing = True
        view.state.outputs_podcast = True
        view.state.translation_outputs = {"chapter_summaries": True, "podcast": True}
        view._save_translation_settings()
        expected = selected_translation_outputs(view.state)
        assert expected["chapter_summaries"] is True
        assert expected["keypoints"] is False
        assert expected["briefing"] is True
        assert expected["podcast"] is True
        ctrl = view.controller
        for key, val in expected.items():
            assert ctrl._settings[f"translation.outputs.{key}"] is val
        # The state dict itself was replaced — the start-log and the
        # completion UI report the derived truth.
        assert view.state.translation_outputs == expected

    def test_mode_a_rewrites_the_whole_selection(self, app):
        """No stale carryover: a previously-manual full_markdown=True is
        cleared by a mode-A Start (the whole-book translation is
        manual-mode-only)."""
        view = self._wizard({"translation.enabled": True})
        view.state.translation_enabled = True
        view.state.translation_outputs = {"full_markdown": True, "social": True}
        view._save_translation_settings()
        ctrl = view.controller
        assert ctrl._settings["translation.outputs.full_markdown"] is False
        assert ctrl._settings["translation.outputs.social"] is False

    def test_mode_b_preserves_the_manual_list(self, app):
        view = self._wizard({"translation.enabled": True, "translation.selection_mode": "manual"})
        view.state.translation_enabled = True
        view.state.translation_selection_mode = "manual"  # the loaded mode
        view.state.translation_outputs = {"mindmap": True, "keypoints": True}
        view._save_translation_settings()
        ctrl = view.controller
        assert ctrl._settings["translation.outputs.mindmap"] is True
        assert ctrl._settings["translation.outputs.keypoints"] is True
        assert "translation.outputs.full_markdown" not in ctrl._settings

    def test_disabled_never_derives(self, app):
        """Translation off: the outputs round-trip untouched (the B5
        contract) even in mode A."""
        view = self._wizard({"translation.enabled": False})
        view.state.translation_outputs = {"chapter_summaries": False, "mindmap": True}
        view._save_translation_settings()
        ctrl = view.controller
        assert ctrl._settings["translation.outputs.chapter_summaries"] is False
        assert ctrl._settings["translation.outputs.mindmap"] is True

    def test_the_mode_setting_round_trips(self, app):
        view = self._wizard({"translation.enabled": True})
        view.state.translation_enabled = True
        view.state.translation_selection_mode = "manual"
        view._save_translation_settings()
        assert view.controller._settings["translation.selection_mode"] == "manual"

    def test_load_reads_the_mode(self):
        src = _src(_WIZARD)
        assert 's.get_setting("translation.selection_mode", "selected")' in src

    def test_the_derivation_runs_after_every_step_saved(self):
        """The Start order: steps' save_to_state → _save_translation_settings
        (a Step-4 change made after visiting Step 6 still counts)."""
        src = _src(_WIZARD)
        i_loop = src.index("for s in self.steps[:9]:")
        i_save = src.index("self._save_translation_settings()")
        assert i_loop < i_save

    def test_state_default_is_mode_a(self):
        from ui_qt.views.wizard_steps.shared import WizardState

        assert WizardState().translation_selection_mode == "selected"


# ═══════════════════════════════════════════════════════════════════════════
# 6a — honesty downstream: the start-log + the Review step
# ═══════════════════════════════════════════════════════════════════════════


class TestModeAHonestyDownstream:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_start_log_names_the_mode(self):
        src = _src(_WIZARD)
        assert '"follows the Step-4 selection"' in src
        assert "Selection mode: " in src

    def test_review_shows_the_derived_truth(self, app):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step8_review import Step8Review

        state = WizardState()
        state.translation_enabled = True
        state.translation_selection_mode = "selected"
        state.include_keypoints = False  # differs from the checkbox defaults
        state.outputs_briefing = True
        # Stale manual state — must NOT be what the review shows.
        state.translation_outputs = {"podcast": True, "full_markdown": True}
        step = Step8Review(_StubController(), state)
        try:
            step.refresh()
            text = step.summary.toPlainText()
            assert "follows Step 4 —" in text
            assert "Chapter summaries" in text
            assert "Executive briefing" in text
            assert "Full book Markdown" not in text, "the stale manual list must not show"
            assert "Podcast script" not in text
        finally:
            step.hide()
            step.deleteLater()

    def test_review_manual_mode_keeps_the_list(self, app):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step8_review import Step8Review

        state = WizardState()
        state.translation_enabled = True
        state.translation_selection_mode = "manual"
        state.translation_outputs = {"mindmap": True}
        step = Step8Review(_StubController(), state)
        try:
            step.refresh()
            text = step.summary.toPlainText()
            assert "Translate outputs: mindmap" in text
            assert "follows Step 4" not in text
        finally:
            step.hide()
            step.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# The phase-gate grabs (the V0.7.3 pattern): 740×540 + 820×600, both themes
# ═══════════════════════════════════════════════════════════════════════════


class TestStep6Grabs:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size):
        from ui_qt.theme import theme_manager

        theme_manager.apply(app, theme)
        step = _build_step6(
            {
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "translategemma:4b",
            }
        )
        try:
            step._on_models_loaded(["qwen2.5:7b", "translategemma:4b", "gemma3:12b"])
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step6_{theme}_{size[0]}x{size[1]}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default

    def test_mode_b_also_renders(self, app, tmp_path):
        """The manual list + the radios visible — mode B's render is part
        of the phase gate (the list is the taller layout)."""
        from ui_qt.theme import theme_manager

        theme_manager.apply(app, "light")
        step = _build_step6()
        try:
            step.enable_cb.setChecked(True)
            step.mode_b_rb.setChecked(True)
            step.resize(740, 540)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / "step6_mode_b_740x540.png"
            assert grab.save(str(out))
            assert out.stat().st_size > 500
        finally:
            step.hide()
            step.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# 6b — honesty: the .harakat.md output is a manual-review file (D16)
# ═══════════════════════════════════════════════════════════════════════════


class TestHarakatManualReviewTruth:
    """The audit's finding (§W10): the .harakat.md output has NO downstream
    consumer — podcast/TTS never reads it; the 'feeds the Podcast Maker'
    claim was aspirational.  D16 defers the wiring to the backlog; every
    user-facing surface now says manual-review."""

    def test_harakat_module_docstring_honest(self):
        src = _src(_HARAKAT)
        assert "MANUAL-REVIEW" in src
        assert "feeds directly into" not in src
        assert "Podcast Maker for Farsi audio generation" not in src

    def test_service_file_map_comments_honest(self):
        src = _src(_SERVICE)
        assert "TTS-ready" not in src
        assert "ready for Podcast Maker" not in src
        assert "manual-review copy" in src

    def test_settings_page_harakat_copy_honest(self):
        src = _src(_TR_PAGE)
        assert "automatically used when generating Farsi podcast audio" not in src
        assert "MANUAL-REVIEW copy" in src

    def test_translatable_podcast_subtitle_honest(self):
        src = _src(_TR_PAGE)
        assert "+ harakat for TTS" not in src
        assert "+ a .harakat.md review copy" in src

    def test_step6_harakat_tooltip_honest(self):
        src = _src(_STEP6)
        assert "MANUAL-REVIEW" in src
        assert "not yet wired into the Podcast Maker / TTS" in src


# ═══════════════════════════════════════════════════════════════════════════
# 6b — the dead settings keys purged (the audit's dead-code register)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeadKeysPurged:
    """translation.outputs.packets (no _OUTPUT_FILE_MAP entry — the key
    never selected anything) and translation.harakat_confident_only
    (never read by any backend) are gone from every runtime surface.

    The pins assert CODE, not comments (the purge code and its
    documentation legitimately name the keys); the resurrection vectors
    are the DEFAULTS dict, the migration add-missing-keys lists, and any
    get()/[…] reader — each is pinned separately."""

    _RUNTIME_READERS = ("ui_qt", "core")

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Drop full-line comments and docstrings' '# …' fragments (the
        test_v182043 _strip_comments pattern)."""
        out = []
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
        return "\n".join(out)

    def test_translation_defaults_carry_no_dead_keys(self):
        """The strongest pin: the REAL defaults dict has neither dead key
        (a fresh install never sees them)."""
        from utils.settings import Settings

        defaults = Settings.__new__(Settings)._defaults()
        tr = defaults["translation"]
        assert "harakat_confident_only" not in tr
        assert "packets" not in tr["outputs"]
        # The living keys stay exactly as they were.
        assert tr["outputs"]["chapter_summaries"] is True
        assert tr["outputs"]["podcast"] is True
        assert tr["outputs"]["mindmap"] is False
        assert tr["harakat_enabled"] is True
        # The Output Studio's own packets toggle is a DIFFERENT, living key.
        assert defaults["outputs"]["packets"] is False

    def test_harakat_confident_only_has_zero_readers(self):
        """No runtime reader outside the purge itself (comment-stripped —
        the migration's del/if lines in utils/settings.py are the purge,
        not a reader)."""
        for root in self._RUNTIME_READERS:
            for f in (_project_root / root).rglob("*.py"):
                assert "harakat_confident_only" not in self._strip_comments(_src(f)), (
                    f"{f} still reads the dead key"
                )
        for single in ("controller.py", "main.py"):
            assert "harakat_confident_only" not in self._strip_comments(
                _src(_project_root / single)
            )

    def test_confident_checkbox_deleted_from_the_settings_page(self):
        src = _src(_TR_PAGE)
        assert "self.confident_cb" not in src
        # Comment-stripped: the checkbox's user-facing label is gone from
        # CODE (the purge's documentation comment may name it).
        assert "Confidence-first" not in self._strip_comments(src)

    def test_no_resurrection_vectors_in_the_migration(self):
        """The add-missing-keys lists (the tuple form) can no longer
        re-add either dead key to an existing settings.json; the purge
        pops are in place (the nllb_model pattern)."""
        stripped = self._strip_comments(_src(_SETTINGS))
        assert '("harakat_confident_only"' not in stripped
        assert '("packets"' not in stripped, "no migration list re-adds the packets key"
        # The purge itself.
        assert 'if "harakat_confident_only" in tr:' in stripped
        assert 'del tr["harakat_confident_only"]' in stripped
        assert 'if "packets" in tr_out:' in stripped
        assert 'del tr_out["packets"]' in stripped

    def test_migration_purges_a_legacy_settings_file(self, tmp_path):
        """The real Settings._load: a legacy settings.json carrying both
        dead keys comes back without them (the nllb_model pattern)."""
        import json

        legacy = {
            "translation": {
                "backend": "ollama",
                "harakat_confident_only": True,
                "outputs": {
                    "chapter_summaries": True,
                    "keypoints": True,
                    "packets": True,  # the dead key, ON, in a legacy file
                    "mindmap": False,
                },
            }
        }
        (tmp_path / "settings.json").write_text(json.dumps(legacy), encoding="utf-8")

        from unittest.mock import patch

        from utils.settings import Settings

        Settings._instance = None
        Settings._test_override = None
        try:
            with (
                patch.object(Settings, "_settings_dir", tmp_path),
                patch.object(Settings, "_settings_file", tmp_path / "settings.json"),
            ):
                s = Settings()
                tr = s.get("translation", {})
                assert "harakat_confident_only" not in tr, "the dead key must be purged on load"
                tr_out = tr.get("outputs", {})
                assert "packets" not in tr_out, "the dead outputs key must be purged on load"
                # The LIVING keys survive the purge untouched.
                assert tr_out["chapter_summaries"] is True
                assert tr_out["keypoints"] is True
                assert tr_out["mindmap"] is False
                assert tr["backend"] == "ollama"
        finally:
            Settings._instance = None
            Settings._test_override = None
