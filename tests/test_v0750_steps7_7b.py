"""V0.7.5 (wizard rework ⑦, Steps 7-7b) — the pin file.

7a — the advanced disclosure (audit §W11, D17-D19 + D13/B4): Step 7
collapses to ONE primary choice (the split strategy, Auto default) plus
a folded disclosure (token limit Auto+manual — the manual field enabled
ONLY under the Token strategy, which is the only consumer
``TokenSegmenter``; the semantic toggle, default on, with honest copy
about what it actually gates). The academic-rigor and
conservative-drops checkboxes are REMOVED from the wizard (their
labels lied / a debugging stance) — the backend mechanisms stay, the
Settings page is the only UI writer, and the request builder resolves
both from settings (the B5-class forced-False overwrite is gone). The
token-budget slider is DELETED (B4 closed by deletion): with it die the
dead Step-4 sync and ``TOKEN_BUDGET_PRESETS`` (whose presets force
deprecated outputs on). The request-layer token-limit default unifies
to 2,000 (the last disagreeing row of the audit §5 defaults table).

7b/7c/7d sections are appended below with their own commits
(self-consistency relocation + provider log; the honest coverage
close-the-loop; the fine-tune recommended-defaults button).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP7 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step7_advanced.py"
_STEP7B = _project_root / "ui_qt" / "views" / "wizard_steps" / "step7b_fine_tune.py"
_STEP8 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step8_review.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_PRESETS = _project_root / "ui_qt" / "settings" / "presets.py"
_SEGMENTER = _project_root / "core" / "segmentation" / "segmenter.py"
_TOKEN_SEGMENTER = _project_root / "core" / "segmentation" / "token_segmenter.py"
_MODELS = _project_root / "core" / "models" / "models.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and trailing '# …' fragments (the
    test_v182043 / test_v0740 pattern — pins assert CODE, not the
    documentation that legitimately names the dead thing)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _code_only(path: Path) -> str:
    """_strip_comments PLUS the module docstring dropped — module-level
    prose is documentation, not code (the purge's own docstrings
    legitimately name the dead things they describe)."""
    text = _src(path)
    if '"""' in text:
        parts = text.split('"""', 2)
        if len(parts) == 3:
            text = parts[0] + parts[2]
    return _strip_comments(text)


def _strat_desc() -> dict:
    """Exec the _STRAT_DESC literal from Step 7 (the V0.7.4
    _TRANSLATABLE_OUTPUTS exec pattern — the joined copy is what the
    user reads; raw source lines must not be matched)."""
    src = _src(_STEP7)
    start = src.index("_STRAT_DESC = {")
    end = src.index("\n}\n", start) + 3
    ns: dict = {}
    exec(src[start:end], ns)  # noqa: S102 — test-local literal parse
    return ns["_STRAT_DESC"]


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6) — the V0.7.3/V0.7.4 scaffolding pattern
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


def _make_stub_class():
    """Build the offscreen stub: a REAL-Controller subclass whose
    __init__ is overridden to skip the heavy chain (Converter, Settings
    IO) — the class-level machinery (_REQUEST_FIELD_MAP,
    build_request_from_ui) is inherited verbatim, so round-trip pins
    exercise the REAL mapping, not a mirrored copy that can drift."""
    from controller import Controller

    class _StubController(Controller):
        def __init__(self, settings=None):
            self._settings: dict = dict(settings or {})
            self.secrets: dict = {}

        def get_setting(self, path, default=None):
            return self._settings.get(path, default)

        def update_setting(self, path, value):
            self._settings[path] = value

        def get_secret(self, path, default=None):
            return self.secrets.get(path, default)

        def set_secret(self, path, value):
            self.secrets[path] = value

    return _StubController


_StubController = _make_stub_class()


def _build_step7(settings=None, state=None):
    """Build Step 7 offscreen (no workers to stub — this step starts none)."""
    from ui_qt.views.wizard_steps.shared import WizardState
    from ui_qt.views.wizard_steps.step7_advanced import Step7Advanced

    return Step7Advanced(_StubController(settings), state or WizardState())


# ═══════════════════════════════════════════════════════════════════════════
# 7a — the honest strategy copy (AST-pinned, no-drift vs the real cascade)
# ═══════════════════════════════════════════════════════════════════════════


class TestStrategyCopy:
    """The AUTO entry must spell the REAL cascade out (audit §W11: the old
    copy was thin, and never named semantic's cost or its 3,500-token
    sample). The no-drift pin ties the copy's stage order to the actual
    ``segmenter.py`` AUTO cascade."""

    def test_auto_copy_spells_the_full_cascade(self):
        auto = _strat_desc()["auto"]
        for stage in (
            "chapter outline",
            "located table of contents",
            "fuzzy TOC",
            "headings",
            "semantic",
            "page-group blocks",
            "fixed tokens",
            "whole document",
        ):
            assert stage in auto, f"the AUTO copy must name the '{stage}' stage"

    def test_semantic_cost_is_named_honestly(self):
        desc = _strat_desc()
        assert "one extra AI call" in desc["auto"]
        assert "~3,500 tokens" in desc["auto"], (
            "semantic samples the first ~3,500 tokens (semantic_segmenter.py:52-113) — "
            "the copy must say so"
        )
        assert "~3,500 tokens" in desc["semantic"]

    def test_token_entry_names_the_only_consumer(self):
        token = _strat_desc()["token"]
        assert "last resort" in token
        assert "the only setting this strategy reads" in token

    def test_no_drift_the_copy_order_matches_the_real_cascade(self):
        """The copy's stage order must match segmenter.py's AUTO order —
        the copy can never drift from the code it describes (the V0.7.4
        map-integrity pattern)."""
        seg_full = _src(_SEGMENTER)
        # Scope to the segment() method body — the markers must not match
        # prose or helpers elsewhere in the file. segment() runs to EOF
        # (no following method) — fall back to the file end.
        s0 = seg_full.index("def segment(self, markdown_text")
        s1 = seg_full.find("\n    def ", s0)
        if s1 == -1:
            s1 = seg_full.find("\nclass ", s0)
        if s1 == -1:
            s1 = len(seg_full)
        seg = seg_full[s0:s1]
        # The real AUTO cascade markers, in execution order.
        markers = [
            ("chapter-level segmentation", "chapter outline"),
            ("Located TOC", "located table of contents"),
            ("TOC-driven segmentation", "fuzzy TOC"),
            ("heading-based segmentation", "headings"),
            ("semantic segmentation…", "semantic"),
            ("page-group block segmentation", "page-group blocks"),
            ("token-based segmentation", "fixed tokens"),
            ("full-document fallback", "whole document"),
        ]
        auto = _strat_desc()["auto"]
        last_seg = -1
        last_copy = -1
        for seg_marker, copy_stage in markers:
            si = seg.find(seg_marker)
            assert si > last_seg, f"segmenter.py marker {seg_marker!r} out of order"
            last_seg = si
            ci = auto.find(copy_stage)
            assert ci > last_copy, f"copy stage {copy_stage!r} out of order"
            last_copy = ci
            assert si != -1 and ci != -1

    def test_semantic_sample_size_matches_the_segmenter(self):
        """The ~3,500-token claim must match semantic_segmenter's actual
        truncation (truncate_by_tokens(text_sample, 3500))."""
        sem = _src(_project_root / "core" / "segmentation" / "semantic_segmenter.py")
        assert "truncate_by_tokens(text_sample, 3500)" in sem
        assert "~3,500 tokens" in _src(_STEP7)


# ═══════════════════════════════════════════════════════════════════════════
# 7a — the deletions (B4 closed by deletion; D19/D18 gone from the wizard)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeletions:
    """The dead / lying controls are gone from every runtime surface. The
    pins assert CODE with comments stripped (the purge's documentation
    legitimately names the dead things)."""

    def test_no_token_budget_slider(self):
        stripped = _strip_comments(_src(_STEP7))
        for gone in ("QSlider", "budget_slider", "budget_label", "_on_budget_changed"):
            assert gone not in stripped, f"{gone} must be gone from Step 7"

    def test_the_dead_step4_sync_is_gone(self):
        """B4's dead half: the hasattr(self, 'step4') sync on the STEP-7
        widget (never true — the Step-7 widget has no step4 attribute)."""
        stripped = _code_only(_STEP7)
        assert 'hasattr(self, "step4")' not in stripped
        assert "hasattr(self, 'step4')" not in stripped

    def test_no_rigor_or_conservative_checkboxes(self):
        stripped = _strip_comments(_src(_STEP7))
        for gone in ("rigor_cb", "conservative_cb", "Academic rigor", "Conservative drop"):
            assert gone not in stripped, f"{gone} must be gone from Step 7"

    def test_presets_module_has_no_token_budget_presets(self):
        """D13/B4: TOKEN_BUDGET_PRESETS deleted with its only consumer —
        and its presets that force deprecated outputs on."""
        stripped = _strip_comments(_src(_PRESETS))
        assert "TOKEN_BUDGET_PRESETS = [" not in stripped
        assert "TOKEN_BUDGET_PRESETS: list" not in stripped
        # The preset bundles that forced deprecated outputs are gone too.
        assert '"outputs.social": True' not in stripped
        assert '"outputs.patterns": True' not in stripped
        assert '"outputs.cheatsheet": True' not in stripped
        assert '"outputs.quote_bank": True' not in stripped

    def test_no_importer_of_the_dead_presets_anywhere(self):
        for f in (_project_root / "ui_qt").rglob("*.py"):
            assert "TOKEN_BUDGET_PRESETS" not in _code_only(f), (
                f"{f} still references the deleted presets"
            )

    def test_state_fields_gone(self):
        """D19/D18: the wizard state no longer carries the two fields —
        the Settings layer owns them (the B5-class forced-False overwrite
        over the Settings choice is gone)."""
        stripped = _strip_comments(_src(_SHARED))
        assert "academic_rigor" not in stripped
        assert "conservative_drops" not in stripped

    def test_round_trip_omits_them_and_settings_resolve(self):
        """The relocation round-trip: to_ui_data omits both keys. academic_rigor
        resolves from settings (its map row is settings-backed) — a
        Settings-enabled value now survives a wizard run instead of being
        forced to False. conservative_drops has no settings twin (its map
        row is a plain field) — the request simply carries its default;
        no UI anywhere forces it either way."""
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        ui = state.to_ui_data()
        assert "academic_rigor" not in ui
        assert "conservative_drops" not in ui

        stub = _StubController(
            {
                "summarisation.academic_rigor": True,
                "summarisation.conservative_drops": True,
            }
        )
        req = stub.build_request_from_ui(ui)
        assert req.academic_rigor is True, "the settings-backed row resolves"
        assert req.conservative_drops is False, "no settings twin — the default stands"

    def test_backend_auto_enable_stays(self):
        """D19: the source-driven auto-enable stays in the backend
        (summarizer_init.py:496-511) — only the wizard checkbox died."""
        init = _src(_project_root / "core" / "summarisation" / "summarizer_init.py")
        assert 'source_type", "") == "academic_paper"' in init
        assert "self.academic_rigor = True" in init

    def test_start_log_and_review_no_longer_print_them(self):
        for path in (_WIZARD, _STEP8):
            stripped = _strip_comments(_src(path))
            assert "Academic rigor:" not in stripped, f"{path.name} still prints it"
            assert "Conservative drops:" not in stripped, f"{path.name} still prints it"
        # The honest replacements are present.
        assert "token limit/segment:" in _src(_WIZARD)
        assert "Token limit/segment:" in _src(_STEP8)
        assert "Semantic fallback:" in _src(_STEP8)


# ═══════════════════════════════════════════════════════════════════════════
# 7a — the disclosure + the token-limit gate (offscreen behaviour)
# ═══════════════════════════════════════════════════════════════════════════


class TestDisclosureAndGate:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_folded_by_default(self, app):
        step = _build_step7()
        try:
            assert not step.disclosure.isVisibleTo(step), "the disclosure is folded by default"
            assert not step.fold_btn.isChecked()
            assert step.fold_btn.text() == "Show advanced settings"
            step.fold_btn.setChecked(True)
            assert step.disclosure.isVisibleTo(step)
            assert step.fold_btn.text() == "Hide advanced settings"
        finally:
            step.hide()
            step.deleteLater()

    def test_auto_is_the_default_and_gates_the_spin(self, app):
        step = _build_step7()
        try:
            assert step.strat_combo.currentText() == "auto"
            assert step.token_auto_cb.isChecked(), "Auto is the default (D17)"
            assert not step.token_spin.isEnabled(), "under Auto + non-token the field is dead"
            assert "default (2,000) applies" in step.token_note.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_manual_enables_only_under_the_token_strategy(self, app):
        """The plan's rule: the manual field is enabled ONLY when the TOKEN
        strategy is actually in play — under auto/heading/semantic the
        limit is never read (it only feeds TokenSegmenter)."""
        step = _build_step7()
        try:
            # Manual ON but strategy != token → still disabled.
            step.token_auto_cb.setChecked(False)
            step.strat_combo.setCurrentText("semantic")
            assert not step.token_spin.isEnabled()
            assert "never" in step.token_note.text()
            # Strategy token + manual → live.
            step.strat_combo.setCurrentText("token")
            assert step.token_spin.isEnabled()
            assert "TokenSegmenter" in step.token_note.text()
            # Auto checked again → dead again.
            step.token_auto_cb.setChecked(True)
            assert not step.token_spin.isEnabled()
        finally:
            step.hide()
            step.deleteLater()

    def test_semantic_default_on_and_folds_in(self, app):
        step = _build_step7()
        try:
            assert step.semantic_cb.isChecked(), "default on (D17, as today)"
            # The toggle lives INSIDE the disclosure.
            assert step.semantic_cb.parentWidget() is step.disclosure
        finally:
            step.hide()
            step.deleteLater()

    def test_save_round_trips_strategy_token_semantic(self, app):
        state_mod = __import__("ui_qt.views.wizard_steps.shared", fromlist=["WizardState"])
        state = state_mod.WizardState()
        step = _build_step7(state=state)
        try:
            step.strat_combo.setCurrentText("token")
            step.token_auto_cb.setChecked(False)
            step.token_spin.setValue(4000)
            step.semantic_cb.setChecked(False)
            step.save_to_state()
            assert state.segment_strategy == "token"
            assert state.token_limit == 4000
            assert state.enable_semantic is False
        finally:
            step.hide()
            step.deleteLater()

    def test_seeded_state_opens_the_widgets(self, app):
        state_mod = __import__("ui_qt.views.wizard_steps.shared", fromlist=["WizardState"])
        state = state_mod.WizardState()
        state.segment_strategy = "heading"
        state.token_limit = 6000
        state.enable_semantic = False
        step = _build_step7(state=state)
        try:
            assert step.strat_combo.currentText() == "heading"
            assert step.token_spin.value() == 6000
            assert not step.semantic_cb.isChecked()
            assert "Splits at markdown headings" in step.strat_desc_label.text()
        finally:
            step.hide()
            step.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# 7a — the round-trip + defaults-unification pins
# ═══════════════════════════════════════════════════════════════════════════


class TestRoundTrip7a:
    """Every state field the phase touches, pinned through
    to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest."""

    def test_strategy_token_semantic_round_trip(self):
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        state.segment_strategy = "token"
        state.token_limit = 3000
        state.enable_semantic = False
        req = _StubController().build_request_from_ui(state.to_ui_data())
        assert req.segment_strategy == "token"
        assert req.token_limit_per_segment == 3000
        assert req.enable_semantic_segmentation is False

    def test_token_limit_default_2000_everywhere(self):
        """The audit §5 row resolved by this phase: the request-layer
        default now matches the settings schema and the wizard seed
        (2,000 everywhere — the last disagreeing row)."""
        from core.models import ConversionRequest
        from ui_qt.views.wizard_steps.shared import WizardState

        assert (
            ConversionRequest(
                input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out")
            ).token_limit_per_segment
            == 2000
        )
        assert WizardState().token_limit == 2000
        req_src = _src(_MODELS)
        assert "token_limit_per_segment: int = 2000" in req_src

    def test_strategy_label_copy_on_the_step_header(self):
        src = _src(_STEP7)
        assert '"How the book is split into sections' in src


# ═══════════════════════════════════════════════════════════════════════════
# 7a — the phase-gate grabs (the V0.7.3/V0.7.4 pattern):
# 740×540 + 820×600, both themes — folded + open variants
# ═══════════════════════════════════════════════════════════════════════════


class TestStep7PhaseGateGrabs:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    @pytest.mark.parametrize("fold", [False, True], ids=["folded", "open"])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size, fold):
        from ui_qt.theme import theme_manager

        theme_manager.apply(app, theme)
        step = _build_step7()
        try:
            if fold:
                step.fold_btn.setChecked(True)
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step7_{theme}_{size[0]}x{size[1]}_{'open' if fold else 'folded'}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default
