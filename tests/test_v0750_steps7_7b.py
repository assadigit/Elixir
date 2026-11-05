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


# ═══════════════════════════════════════════════════════════════════════════
# 7b — self-consistency relocation (D10): out of the wizard, into
# Settings with truthful copy, default off, provider log line
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfConsistencyRelocation:
    """Removed from the wizard; backend kept; default off; the Settings →
    AI-quality control carries truthful copy; a log line fires when it is
    requested on an unsupported provider (no more silent no-op)."""

    def test_checkbox_gone_from_step7b(self):
        stripped = _strip_comments(_src(_STEP7B))
        assert "self_consist_cb" not in stripped
        assert "Self-consistency" not in stripped, "no self-consistency control on Step 7b"

    def test_state_field_and_round_trip_key_gone(self):
        stripped = _strip_comments(_src(_SHARED))
        assert "self_consistency" not in stripped, "the wizard state no longer carries it"

        from ui_qt.views.wizard_steps.shared import WizardState

        ui = WizardState().to_ui_data()
        assert "self_consistency" not in ui

    def test_settings_choice_survives_a_wizard_run(self):
        """The B5-class overwrite is gone: a Settings-enabled True flows
        through build_request_from_ui when the wizard path doesn't carry
        the key (the map row is settings-backed)."""
        from ui_qt.views.wizard_steps.shared import WizardState

        stub = _StubController({"summarisation.self_consistency": True})
        req = stub.build_request_from_ui(WizardState().to_ui_data())
        assert req.self_consistency is True
        # And the wizard-open default (no settings entry) stays off.
        req_off = _StubController().build_request_from_ui(WizardState().to_ui_data())
        assert req_off.self_consistency is False

    def test_default_off_everywhere(self):
        """Backend kept, default OFF: the settings schema, the request
        dataclass, and the Settings page's fallback all carry False."""
        from core.models import ConversionRequest
        from utils.settings import Settings

        defaults = Settings.__new__(Settings)._defaults()
        assert defaults["summarisation"]["self_consistency"] is False
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        assert req.self_consistency is False
        page = _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        assert 'get_setting("summarisation.self_consistency", False)' in page

    def test_settings_page_carries_the_truthful_copy(self):
        """The plan-mandated copy: Ollama-only; ~3-4× cost; union, not
        majority vote (audit §W12: silently no-ops unless provider ==
        'ollama', bullet_pipeline.py:992; the 'vote' is a union-merge
        with fuzzy dedup, summarizer_chunking.py:274-327)."""
        page = _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        for phrase in (
            "Ollama-only",
            "~3-4× cost",
            "union, not majority vote",
        ):
            assert phrase in page, f"the truthful copy must carry {phrase!r}"
        # The old lying labels are gone.
        assert "3× slower, more robust" not in page
        assert "(temp 0, self-review, structured JSON)" not in page

    def test_academic_rigor_label_no_longer_lies(self):
        """Same finding family (§W11): the Settings page's rigor label
        dropped the 'temperature=0' claim (it no longer happens,
        summarizer_init.py:512-516)."""
        page = _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        assert "temp 0" not in page
        assert "auto-enables for academic papers" in page

    def test_start_log_and_review_no_longer_print_it(self):
        for path in (_WIZARD, _STEP8):
            stripped = _strip_comments(_src(path))
            assert "Self-consistency:" not in stripped, f"{path.name} still prints it"


class TestProviderLogLine:
    """The silent no-op is gone: requesting self-consistency on a
    non-Ollama provider logs a WARNING (bullet_pipeline.py's
    run_self_consistency_and_review, the elif branch added V0.7.5)."""

    @staticmethod
    def _run(provider: str, self_consistency: bool) -> tuple[list[str], dict]:
        from types import SimpleNamespace

        from core.summarisation.bullet_pipeline import BulletPipeline

        lines: list[str] = []

        def log(msg, level="INFO"):
            lines.append(f"{level}: {msg}")

        fake_s = SimpleNamespace(
            provider=provider,
            self_consistency=self_consistency,
            temperature=0.2,
            academic_rigor=False,
            primary_model="stub-model",
            _summarize_with_model=lambda *a, **k: None,
            log=log,
        )
        host = SimpleNamespace(s=fake_s)
        result: dict = {
            "executive_summary": "e",
            "bullet_points": ["- b"],
            "thorough_summary": "t",
        }
        BulletPipeline.run_self_consistency_and_review(
            host, SimpleNamespace(), result, "Heading", "text"
        )
        return lines, result

    def test_requested_on_llamacpp_logs_the_warning(self):
        lines, result = self._run("llamacpp", True)
        assert any(
            "Self-consistency was requested but the provider is 'llamacpp'" in ln
            and ln.startswith("WARNING")
            for ln in lines
        ), "the silent no-op must now be a loud skip"
        assert any("only runs on Ollama" in ln for ln in lines)

    def test_requested_on_ollama_still_runs(self):
        lines, result = self._run("ollama", True)
        # The Ollama path proceeds to the multi-sample loop (the sampler
        # stub returns None → no merge); it must NOT hit the elif log.
        assert not any("was requested but the provider is" in ln for ln in lines)

    def test_off_on_any_provider_is_silent(self):
        lines, _ = self._run("llamacpp", False)
        assert not any("Self-consistency" in ln for ln in lines)
        lines2, _ = self._run("ollama", False)
        assert not any("Self-consistency" in ln for ln in lines2)


class TestSelfConsistencyBackendUntouched:
    """The backend stays (D10): the merge machinery + the Settings-page
    save/reload keep working; only the wizard surface changed."""

    def test_merge_is_still_the_union_not_a_vote(self):
        """summarizer_chunking._merge_summaries keeps the union-merge with
        fuzzy dedup (the honest description's referent)."""
        chunking = _src(_project_root / "core" / "summarisation" / "summarizer_chunking.py")
        assert "def _merge_summaries" in chunking
        assert "token_set_ratio" in chunking, "the fuzzy dedup stays"

    def test_settings_page_save_and_reload_survive(self):
        page = _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        assert '"summarisation.self_consistency", self.self_consist_cb.isChecked()' in page


# ═══════════════════════════════════════════════════════════════════════════
# 7c — the honest coverage close-the-loop (D11): ONE target, ±3, ≤3 rounds
# ═══════════════════════════════════════════════════════════════════════════


class TestCoverageLoop:
    """Function-level pins on coverage_loop.run_coverage_close_loop with
    stub deps (deterministic); the REAL-Summarizer agreement test lives in
    TestCoverageLoopRealSummarizer below."""

    @staticmethod
    def _deps(calls, gap_fill_result=None, never_improves=False):
        from types import SimpleNamespace

        from core.summarisation.coverage_loop import run_coverage_close_loop

        log_lines: list[str] = []

        def log(msg, level="INFO"):
            log_lines.append(f"{level}: {msg}")

        def extract_keywords(text, n=18):
            # A fixed, content-agnostic keyword universe for the test.
            return [f"kw{i}" for i in range(n)]

        def targeted_gap_fill(heading, text, missing):
            calls.append(list(missing))
            if gap_fill_result is not None:
                return list(gap_fill_result)
            # Default: a bullet covering every missing concept (in the
            # combined text they appear verbatim → the re-measure sees them).
            return [f"- covers {k}" for k in missing]

        def compute_coverage(source, summary):
            # Deterministic proxy: coverage = fraction of keywords present.
            present = sum(1 for i in range(18) if f"kw{i}" in summary)
            return present / 18

        def filter_thinking_bullets(bullets, *a, **k):
            return list(bullets)

        def is_near_duplicate(bullet, existing):
            return False

        return run_coverage_close_loop, SimpleNamespace(
            log=log,
            log_lines=log_lines,
            extract_keywords=extract_keywords,
            targeted_gap_fill=targeted_gap_fill,
            compute_coverage=compute_coverage,
            filter_thinking_bullets=filter_thinking_bullets,
            is_near_duplicate=is_near_duplicate,
        )

    @staticmethod
    def _run(coverage, threshold, **deps_kwargs):
        fn, d = TestCoverageLoop._deps(deps_kwargs.pop("calls", []), **deps_kwargs)
        bullets, cov, rounds = fn(
            "Heading",
            "text",
            "content",
            ["- existing bullet"],
            "exec says kw0 and kw1",
            "thorough says kw2",
            coverage,
            coverage_threshold=threshold,
            extract_keywords=d.extract_keywords,
            targeted_gap_fill=d.targeted_gap_fill,
            filter_thinking_bullets=d.filter_thinking_bullets,
            compute_coverage=d.compute_coverage,
            is_near_duplicate=d.is_near_duplicate,
            log=d.log,
        )
        return bullets, cov, rounds, d.log_lines

    def test_below_target_triggers_gap_fill(self):
        """Initial coverage below the band → the loop gap-fills the MISSING
        concepts (only the ones absent from the combined summary)."""
        calls: list = []
        fn, d = self._deps(calls)
        # Combined text covers kw0, kw1 (exec), kw2 (thorough) → 3/18 ≈ 17%.
        bullets, cov, rounds, lines = self._run(0.17, 0.85, calls=calls)
        assert rounds >= 1, "below target − 3 must trigger the loop"
        assert calls, "the gap-fill machinery must have been called"
        first_missing = calls[0]
        assert "kw0" not in first_missing and "kw1" not in first_missing
        assert "kw2" not in first_missing
        assert "kw3" in first_missing, "the truly missing concept is targeted"
        assert cov > 0.17, "the re-measure must see the filled concepts"

    def test_three_round_bound(self):
        """A gap-fill that never covers anything: the loop is bounded at
        MAX_COVERAGE_ROUNDS (3) — never an infinite spin."""
        calls: list = []
        # The stub returns bullets that DON'T contain the kw tokens.
        bullets, cov, rounds, lines = self._run(
            0.10,
            0.85,
            calls=calls,
            gap_fill_result=["- filler that names nothing"],
        )
        assert rounds == 3, "the 3-round bound (cost-bounded)"
        assert len(calls) == 3, "one gap-fill batch per round, no more"
        assert any(
            "Reached" in ln and "after 3 attempts" in ln and ln.startswith("WARNING")
            for ln in lines
        ), "the honest exhausted report"

    def test_tolerance_pm3_acceptance(self):
        """D11: threshold 85 must deliver ≥ ~85% ± a few points — the band
        is target − 3. 83% with target 85 is ACCEPTED (target met, within
        ±3); 81% is NOT (0.81 < 0.82) and enters the loop."""
        calls: list = []
        # 83% with target 85% → within the band → 0 rounds, the met report.
        _, cov, rounds, lines = self._run(0.83, 0.85, calls=calls)
        assert rounds == 0 and not calls
        assert any("Coverage 83% — target met" in ln for ln in lines), lines
        assert any("within ±3 of the 85% target" in ln for ln in lines), lines

        calls2: list = []
        _, _, rounds2, lines2 = self._run(0.81, 0.85, calls=calls2)
        assert rounds2 >= 1 and calls2, "0.81 < 0.85 − 0.03 → the loop runs"

    def test_above_target_reports_met_immediately(self):
        _, _, rounds, lines = self._run(0.92, 0.85)
        assert rounds == 0
        assert any("Coverage 92% — target met" in ln and ln.startswith("INFO") for ln in lines)
        assert not any("WARNING" in ln for ln in lines)

    def test_rounds_exhausted_report_names_the_remaining_gaps(self):
        """The plan's honest form: 'Reached X% after 3 attempts; remaining
        gaps: …' — the still-missing concepts are named."""
        calls: list = []

        # Cover only a fixed small set every round → coverage plateaus
        # below the band; the exhausted report must list the gaps.
        def plateau_fill(heading, text, missing):
            return [f"- covers {k}" for k in missing[:2]]

        fn, d = self._deps(calls)
        d.targeted_gap_fill = plateau_fill
        bullets, cov, rounds = fn(
            "Heading",
            "text",
            "content",
            [],
            "exec",
            "thorough",
            0.05,
            coverage_threshold=0.95,
            extract_keywords=d.extract_keywords,
            targeted_gap_fill=d.targeted_gap_fill,
            filter_thinking_bullets=d.filter_thinking_bullets,
            compute_coverage=d.compute_coverage,
            is_near_duplicate=d.is_near_duplicate,
            log=d.log,
        )
        assert rounds == 3
        exhausted = [ln for ln in d.log_lines if "after 3 attempts" in ln]
        assert exhausted, d.log_lines
        assert "remaining gaps:" in exhausted[0]

    def test_stalled_no_candidates_is_honest(self):
        """Every sampled keyword already covered but the metric says below
        target → the no-candidates report (the metric is the bottleneck,
        not the loop) — never a fake 'target met'."""

        from core.summarisation.coverage_loop import run_coverage_close_loop

        lines: list[str] = []

        def log(msg, level="INFO"):
            lines.append(f"{level}: {msg}")

        # Keywords: only kw0 (already in the combined text) → missing is
        # empty on round 1 → the no-candidates break.
        def extract_keywords(text, n=18):
            return ["kw0"]

        def compute_coverage(source, summary):
            return 0.40  # the metric disagrees with the keyword sample

        bullets, cov, rounds = run_coverage_close_loop(
            "Heading",
            "text",
            "content",
            ["- bullet mentioning kw0"],
            "exec mentions kw0",
            "thorough mentions kw0 too",
            0.40,
            coverage_threshold=0.85,
            extract_keywords=extract_keywords,
            targeted_gap_fill=lambda *a: [],
            filter_thinking_bullets=lambda b, *a, **k: list(b),
            compute_coverage=compute_coverage,
            is_near_duplicate=lambda *a: False,
            log=log,
        )
        assert rounds == 1
        assert any("no fillable gaps remain" in ln and ln.startswith("WARNING") for ln in lines), (
            lines
        )
        assert not any("target met" in ln for ln in lines), "no fake success"

    def test_guards_drop_thinking_and_near_duplicates(self):
        """The loop's insertion path mirrors the Tier-2 guards: a
        thinking-contaminated bullet and a near-duplicate are dropped."""
        from core.summarisation.coverage_loop import run_coverage_close_loop

        lines: list[str] = []

        def log(msg, level="INFO"):
            lines.append(f"{level}: {msg}")

        def extract_keywords(text, n=18):
            return [f"kw{i}" for i in range(n)]

        def compute_coverage(source, summary):
            present = sum(1 for i in range(18) if f"kw{i}" in summary)
            return present / 18

        seen: list[str] = []

        def filter_thinking_bullets(bullets, *a, **k):
            seen.extend(bullets)
            # Drop anything containing 'thinking:'; keep the rest.
            return [b for b in bullets if "thinking:" not in b]

        dropped_by_dup: list[str] = []

        def is_near_duplicate(bullet, existing):
            if "dup-me" in bullet:
                dropped_by_dup.append(bullet)
                return True
            return False

        bullets, cov, rounds = run_coverage_close_loop(
            "Heading",
            "text",
            "content",
            ["- existing bullet"],
            "exec kw0",
            "thorough kw1",
            0.10,
            coverage_threshold=0.30,
            extract_keywords=extract_keywords,
            targeted_gap_fill=lambda h, t, missing: [
                f"- thinking: leak about {missing[0]}",
                "- dup-me redundant bullet",
                f"- covers {missing[0]}",
            ],
            filter_thinking_bullets=filter_thinking_bullets,
            compute_coverage=compute_coverage,
            is_near_duplicate=is_near_duplicate,
            log=log,
        )
        assert seen, "the filter was consulted"
        assert dropped_by_dup, "the near-dup guard fired"
        assert all("thinking:" not in b for b in bullets)
        assert all("dup-me" not in b for b in bullets)


class TestOneTarget:
    """The over-delivery domination is removed: the user threshold is THE
    target everywhere (summarizer_init / chapter_phases / gap_filler)."""

    def test_effective_target_source_pin(self):
        init = _src(_project_root / "core" / "summarisation" / "summarizer_init.py")
        assert "self._effective_target = self.coverage_threshold" in init
        # The domination form is gone.
        assert "self.overdeliver_target if self.overdeliver_enabled" not in init

    def test_the_t_minus_10_floor_is_gone(self):
        phases = _code_only(_project_root / "core" / "summarisation" / "chapter_phases.py")
        assert "max(0.60" not in phases
        assert "_coverage_retry_counts" not in phases
        assert "self.coverage_threshold - 0.10" not in phases

    def test_over_delivery_note_gone_from_gap_filler(self):
        gf = _code_only(_project_root / "core" / "summarisation" / "gap_filler.py")
        assert "over-deliver target" not in gf
        assert "_od_note" not in gf

    def test_3tier_trigger_line_is_honest(self):
        phases = _code_only(_project_root / "core" / "summarisation" / "chapter_phases.py")
        assert "over-deliver: floor" not in phases
        assert "effective target" not in phases.replace("_effective_target", "X")

    def test_settings_page_over_delivery_controls_gone(self):
        page = _strip_comments(
            _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        )
        for gone in ("overdeliver_cb", "overdeliver_target_spin", "Over-deliver"):
            assert gone not in page, f"{gone} must be gone from the Settings page"

    def test_settings_keys_stay_inert_legacy(self):
        """The schema keys survive as inert legacy (nothing reads them into
        behavior anymore) — documented, not purged, per the nllb_model
        precedent; a future release may purge them."""
        from utils.settings import Settings

        defaults = Settings.__new__(Settings)._defaults()
        summ = defaults["summarisation"]
        assert summ["overdeliver_enabled"] is True  # inert legacy
        assert summ["overdeliver_target"] == 100  # inert legacy


class TestCoverageLoopRealSummarizer:
    """The REAL-Summarizer agreement test (the V0.7.3 pattern): a hermetic
    real Summarizer, the REAL close-the-loop, the REAL coverage metric and
    keyword extractor — only the LLM sampler is stubbed."""

    @pytest.fixture(autouse=True)
    def _reset_runtime_singletons(self):
        """Mirror of test_group_b_characterization's fixture (constructing a
        Summarizer pollutes module-level singletons; reset after)."""
        yield
        try:
            from core.summarisation import content_judge_impl

            content_judge_impl._warned_embedding_disabled = False
            content_judge_impl._warned_semantic_fallback = False
            content_judge_impl._st_model = None
        except Exception:
            pass
        try:
            from core.summarisation import text_preprocessor_impl

            text_preprocessor_impl._SPACY_NLP = None
        except Exception:
            pass
        try:
            from core.llm import llm_provider_impl

            llm_provider_impl._keep_alive_cache = {}
        except Exception:
            pass

    @staticmethod
    def _fake_settings_class(overrides=None):
        class _FakeSettings:
            _DEFAULTS = {
                "summarisation.provider": "ollama",
                "local.http_timeout_sec": 600,
                "local.chapter_deadline_sec": 600,
                "model_temperatures": {},
            }

            def __init__(self, values=None):
                self._values = dict(self._DEFAULTS)
                if values:
                    self._values.update(values)

            def get(self, key, default=None):
                return self._values.get(key, default)

        return _FakeSettings(overrides)

    def _summarizer(
        self,
        monkeypatch,
        coverage_threshold=0.85,
        od_enabled=True,
        od_target=1.0,
    ):
        from pathlib import Path as _P

        from core.models import ConversionRequest
        from core.summarisation.summarizer import Summarizer

        fake = self._fake_settings_class()
        monkeypatch.setattr("core.summarisation.summarizer.Settings", lambda: fake)
        monkeypatch.setattr("utils.settings.Settings", lambda: fake)

        req = ConversionRequest(input_path=_P("/tmp/x.pdf"), output_dir=_P("/tmp/out"))
        req.summarisation_model = "qwen2.5:14b"
        req.coverage_threshold = coverage_threshold
        req.overdeliver_enabled = od_enabled
        req.overdeliver_target = od_target
        req.include_keypoints = False  # no bullet expansion (no LLM calls)
        req.include_thorough_summary = False  # no dedicated thorough call
        return Summarizer(
            request=req,
            log_callback=lambda m, l="INFO": None,
            language="en",
            claim_extractor=None,
        )

    def test_one_target_even_with_overdelivery_on(self, monkeypatch):
        """The domination-removed pin: over-delivery ON with target 1.0 —
        the OLD code gave _effective_target=1.0; now it is the user
        threshold."""
        s = self._summarizer(monkeypatch, coverage_threshold=0.85)
        assert s.overdeliver_enabled is True
        assert s.overdeliver_target == 1.0
        assert s._effective_target == s.coverage_threshold == 0.85

    def test_phase_runs_the_real_loop(self, monkeypatch):
        """The REAL _phase_thorough_and_coverage: a synthetic chapter whose
        summary covers ~half the keywords; the sampler stub returns bullets
        covering the missing concepts → the loop lifts MEASURED coverage to
        the target and reports honestly."""
        s = self._summarizer(monkeypatch, coverage_threshold=0.85)
        lines: list[str] = []
        s.log = lambda msg, level="INFO": lines.append(f"{level}: {msg}")

        # A synthetic chapter: 18 keyword-bearing sentences.
        content = " ".join(f"Topic kw{i} is discussed in depth here. " for i in range(18))
        text = content
        # The summary covers kw0-kw7 only (via exec) → low measured coverage.
        parsed = {
            "executive_summary": " ".join(f"Covers kw{i}." for i in range(8)),
            "bullet_points": [],
            "thorough_summary": "Also covers kw0 and kw1 in the thorough section.",
        }

        sampler_calls: list[list[str]] = []

        def stub_gap_fill(heading, text_arg, missing):
            sampler_calls.append(list(missing))
            return [f"- Filled: covers {k} plainly." for k in missing[:6]]

        s._targeted_gap_fill = stub_gap_fill

        result = s._phase_thorough_and_coverage("Chapter 1", content, text, parsed)
        (
            _ie,
            _ik,
            _it,
            _sw,
            _th,
            bullets,
            coverage,
            exec_sum,
            final_summary,
            thorough,
        ) = result
        assert sampler_calls, "the real loop must call the (stubbed) sampler"
        assert coverage > 0 or not sampler_calls
        # The combined summary now carries the stubbed fill bullets.
        for k in sampler_calls[0][:3]:
            assert f"covers {k}" in final_summary
        # The honest terminal report fired (met or the honest failure —
        # never silence).
        assert any(
            ("target met" in ln) or ("Reached" in ln) or ("no fillable gaps" in ln) for ln in lines
        ), lines
        # _last_coverage reflects the loop result (the self-review skip
        # decision reads it).
        assert s._last_coverage == coverage

    def test_phase_within_band_skips_the_loop(self, monkeypatch):
        """Coverage already inside the band → 0 rounds; the met report."""
        s = self._summarizer(monkeypatch, coverage_threshold=0.85)
        lines: list[str] = []
        s.log = lambda msg, level="INFO": lines.append(f"{level}: {msg}")
        # The combined summary carries the source VERBATIM → every keyword
        # and concept the metric extracts from the source is present →
        # measured coverage ≈ 1.0 → inside the band, the loop no-ops.
        content = " ".join(f"Topic kw{i} is discussed in depth here. " for i in range(18))
        parsed = {
            "executive_summary": content,
            "bullet_points": [],
            "thorough_summary": content,
        }

        def boom(*a, **k):
            raise AssertionError("the sampler must not fire inside the band")

        s._targeted_gap_fill = boom
        s._phase_thorough_and_coverage("Chapter 1", content, content, parsed)
        assert any("target met" in ln for ln in lines), lines
        assert not any("WARNING" in ln for ln in lines)


class TestCoverageTruthInUI:
    """7c item 3: Step 7b's spin says what the loop now really does."""

    def test_step7b_label_and_caption(self):
        src = _code_only(_STEP7B)
        assert '"Coverage target:"' in src
        assert "reprompt trigger" not in src, "the overstating label is gone"
        raw = _src(_STEP7B)
        assert "Regenerates until measured coverage reaches this level" in raw
        assert "±3 for model randomness, max 3 rounds" in raw

    def test_review_and_start_log_carry_the_target_semantics(self):
        review = _src(_STEP8)
        assert "Coverage target:" in review
        assert "regenerate to measured, ±3, max 3 rounds" in review
        wizard = _src(_WIZARD)
        assert "Coverage target:" in wizard
        assert "regenerate to measured, ±3, max 3 rounds" in wizard
        assert "reprompt trigger" not in wizard

    def test_settings_page_target_semantics(self):
        page = _src(_project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py")
        assert 'f.addRow("Coverage target", self.coverage_spin)' in page
        assert 'get_setting("summarisation.coverage_threshold", 85)' in page
        assert "the over-delivery controls are GONE" in page

    def test_constants_pinned(self):
        from core.summarisation.coverage_loop import (
            COVERAGE_TOLERANCE,
            MAX_COVERAGE_ROUNDS,
        )

        assert MAX_COVERAGE_ROUNDS == 3
        assert COVERAGE_TOLERANCE == 0.03
