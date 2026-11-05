"""V0.6.86 (wizard hotfix) — the B1 + B5 data-loss bug pins.

The two live bugs (Round-2 plan §2 Phase ①, audit §3 B1/B5 — both
evidence-verified at main@35f13c5):

- **B1** — ``Controller.list_ollama_models()`` never existed, yet
  ``step6_translation.py:85`` and ``translation_page.py:151`` call it
  (both wrap it in ``except Exception`` → empty model combos). The
  wizard's translation save then wrote ``""`` over the saved
  ``translation.harakat_model`` / ``judge_model`` — a data wipe on
  every wizard run with Ollama unreachable (``wizard_view.py``
  ``_save_translation_settings``).
  Fix: the controller method (delegating to
  ``utils/network.list_ollama_models`` — no new HTTP code) + an
  empty-selection guard in the wizard save.
- **B5** — the wizard force-disabled translation every run:
  ``WizardState.translation_enabled`` defaults ``False``
  (``shared.py:85``), ``_load_settings_into_state`` never read the
  translation settings, and ``_save_translation_settings`` writes
  them unconditionally → every Start silently wrote
  ``translation.enabled=false`` over the user's saved choice.
  Fix: load-then-save round-trip — the wizard loads the translation
  settings at open, so the save writes back what the user chose
  unless Step 6 changed it.

Pin layers (the house pattern, cf. test_v182046_p5_wizard_split.py):
AST/source pins run on ANY rig (no PySide6 import needed — the default
CI suite is Qt-less); the behavioural + offscreen-render layers are
gated on PySide6 availability (``pytest.importorskip``) and only add
depth where Qt exists.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_CONTROLLER = _project_root / "controller.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_STEP6 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step6_translation.py"
_TR_PAGE = _project_root / "ui_qt" / "settings" / "translation_page.py"
_NETWORK = _project_root / "utils" / "network.py"


# ── helpers (headless-safe: source text + AST only, by name) ────────────────


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_src(path: Path, func_name: str, class_name: str) -> str:
    """Full source of a class method, located by name via AST (no line peek)."""
    src = _src(path)
    classes = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.ClassDef)}
    assert class_name in classes, f"class {class_name!r} not found in {path}"
    node = None
    for n in ast.walk(classes[class_name]):
        if isinstance(n, ast.FunctionDef) and n.name == func_name:
            node = n
            break
    assert node is not None, f"{class_name}.{func_name} not found in {path}"
    seg = ast.get_source_segment(src, node)
    assert seg is not None
    return seg


def _stub_settings_class():
    """The Settings._test_override shape: a get()-only dict-backed fake.

    Importing utils.settings is safe headless (no Qt).
    """

    class _FakeSettings:
        def __init__(self, data: dict | None = None):
            self._data = dict(data or {})

        def get(self, path: str, default=None):
            return self._data.get(path, default)

        def set(self, path: str, value) -> None:
            self._data[path] = value

    return _FakeSettings


class _FakeSignal:
    def connect(self, *args, **kwargs):
        pass


class _FakeWorker:
    """Captures the worker fn instead of starting a thread — building Step 6
    offscreen must never touch the network (the V0.7.4 listing worker; the
    same stub test_v0730 uses for Step 5's)."""

    captured: list = []

    def __init__(self, fn, *args, **kwargs):
        type(self).captured.append(fn)

    finished = _FakeSignal()
    failed = _FakeSignal()

    def is_running(self):
        return False

    def start(self):
        pass


# ═══════════════════════════════════════════════════════════════════════════
# B1 — source/AST pins (run on every rig, Qt-less CI included)
# ═══════════════════════════════════════════════════════════════════════════


class TestB1ControllerMethodPins:
    """The controller method exists, delegates, and stays bounded."""

    def test_method_exists_on_controller(self):
        src = _method_src(_CONTROLLER, "list_ollama_models", "Controller")
        assert "def list_ollama_models" in src

    def test_delegates_to_utils_network_helper(self):
        """The body calls the shared helper (no new HTTP code) with the
        settings-derived base URL and the 5s UI budget."""
        src = _method_src(_CONTROLLER, "list_ollama_models", "Controller")
        tree = ast.parse(src)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        helper_calls = [
            n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "list_ollama_models"
        ]
        assert helper_calls, "must delegate to utils.network.list_ollama_models"
        kw = {k.arg: k.value for k in helper_calls[0].keywords if k.arg}
        assert "timeout" in kw, "the UI-facing call must pin its own timeout"
        assert isinstance(kw["timeout"], ast.Constant) and kw["timeout"].value == 5
        # The base URL is resolved from the canonical settings key.
        str_consts = [
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        assert "llm.ollama_url" in str_consts, "base URL must come from settings"
        assert "http://localhost:11434" in str_consts, "canonical default URL"

    def test_call_sites_no_longer_hit_a_missing_method(self):
        """Both UI call sites (step6 + the Settings translation page) call the
        method that now exists — the AttributeError→empty-combo path is gone
        whenever the controller is the real one (stubs keep their own)."""
        for path, needle in (
            (_STEP6, "self.controller.list_ollama_models()"),
            (_TR_PAGE, "self.controller.list_ollama_models()"),
        ):
            assert needle in _src(path), f"{path} call site changed — repin"

    def test_utils_network_helper_unchanged_shape(self):
        """The audited fix route (network.py list_ollama_models) keeps its
        never-raise-on-transport contract and /api/tags endpoint."""
        src = _src(_NETWORK)
        start = src.index("def list_ollama_models")
        nxt = src.find("\ndef ", start + 10)
        body = src[start:] if nxt == -1 else src[start:nxt]
        assert "/api/tags" in body
        assert "ConnectionError" in body and "TimeoutError" in body


class TestB1GuardPins:
    """The wizard save never wipes a saved model with an empty string."""

    def test_guard_in_save_translation_settings(self):
        src = _method_src(_WIZARD, "_save_translation_settings", "WizardView")
        # The wipe path (unconditional write of the raw state field) is gone…
        assert (
            'c.update_setting("translation.harakat_model", '
            "self.state.translation_harakat_model)" not in src
        ), "the unconditional harakat write must be gone (the B1 wipe path)"
        # …the guarded pair loop is in…
        for needle in (
            "translation_harakat_model",
            "translation_judge_model",
            "translation.harakat_model",
            "translation.judge_model",
            "logger.info",
        ):
            assert needle in src, f"guard pin {needle!r} missing"
        # …and the skip is LOGGED (the plan's observability requirement).
        assert "wizard save kept" in src

    def test_guard_only_fires_on_empty_new_value(self):
        """A non-empty selection still writes through (the normal path)."""
        src = _method_src(_WIZARD, "_save_translation_settings", "WizardView")
        # V0.7.4 (rework ⑥): the method gained a local ``s = self.state``
        # alias — the guard still reads the STATE field for the new value.
        assert "new_value = str(getattr(s, state_field)" in src or (
            "new_value = str(getattr(self.state, state_field)" in src
        )
        assert "if not new_value:" in src


# ═══════════════════════════════════════════════════════════════════════════
# B1 — behavioural layer (needs the real modules; Qt-free for the logic)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    """Import-gate for everything that pulls ui_qt (PySide6-backed)."""
    return pytest.importorskip("PySide6.QtWidgets")


class _StubController:
    """Dict-backed controller stub (the wz_icons_check.py pattern):

    get_setting/update_setting cover every step-build read/write;
    list_ollama_models is the B1 method under test (stubbed value).
    """

    def __init__(self, settings: dict | None = None, models: list[str] | None = None):
        self._settings: dict = dict(settings or {})
        self._models = list(models or [])

    def get_setting(self, path: str, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path: str, value) -> None:
        self._settings[path] = value

    def get_secret(self, path: str, default: str = "") -> str:
        return default

    def set_secret(self, path: str, value: str) -> None:
        pass

    def list_ollama_models(self) -> list[str]:
        return list(self._models)


class TestB1ControllerBehaviour:
    """The real Controller method against a mocked network helper."""

    def test_returns_a_list_from_the_helper(self, monkeypatch):
        """The plan's mocked-socket pin: the method exists, delegates with
        the settings URL + 5s budget, and returns a list."""
        pytest.importorskip("controller")
        import controller as controller_mod

        fake_settings = _stub_settings_class()({"llm.ollama_url": "http://ollama-rig:11500"})
        monkeypatch.setattr(controller_mod.Settings, "_test_override", fake_settings)

        recorded: dict = {}

        def _fake_list(base_url="http://localhost:11434", timeout=10):
            recorded["base_url"] = base_url
            recorded["timeout"] = timeout
            return ("model-a:1b", "model-b:7b")  # tuple: list() coercion pinned too

        monkeypatch.setattr(controller_mod, "list_ollama_models", _fake_list)

        from controller import Controller

        ctl = Controller()
        result = ctl.list_ollama_models()

        assert isinstance(result, list), "must return a list (the UI loops it)"
        assert result == ["model-a:1b", "model-b:7b"]
        assert recorded["base_url"] == "http://ollama-rig:11500", (
            "base URL must flow from the llm.ollama_url setting"
        )
        assert recorded["timeout"] == 5, "UI-facing call must keep the 5s budget"

    def test_transport_failure_returns_empty_list(self, monkeypatch):
        """The helper's transport-failure contract ([] not an exception) flows
        through the controller method — the UI populates an empty combo, the
        guard keeps the saved model (utils.network never raises on transport
        errors; the UI call sites keep their own except as belt-and-braces).
        """
        pytest.importorskip("controller")
        import controller as controller_mod

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _stub_settings_class()({}))
        monkeypatch.setattr(controller_mod, "list_ollama_models", lambda *_a, **_k: [])
        from controller import Controller

        assert Controller().list_ollama_models() == []


class TestB1GuardBehaviour:
    """_save_translation_settings never wipes a saved model (the __new__
    harness: the method touches only self.controller + self.state, so no
    full-wizard build is needed for the logic pin)."""

    @pytest.fixture
    def wizard_pair(self):
        _qt_or_skip()
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_view import WizardView

        stub = _StubController(
            settings={
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "llama3.1:8b",
            }
        )
        view = WizardView.__new__(WizardView)
        view.controller = stub
        view.state = WizardState()
        return view, stub

    def test_empty_selection_preserves_saved_models(self, wizard_pair, caplog):
        view, stub = wizard_pair
        # The exact B1 repro: combos empty (listing failed) → state fields "".
        assert view.state.translation_harakat_model == ""
        assert view.state.translation_judge_model == ""

        with caplog.at_level("INFO", logger="ui_qt.views.wizard_view"):
            view._save_translation_settings()

        assert stub._settings["translation.harakat_model"] == "qwen2.5:7b", (
            "an empty wizard selection must NEVER wipe the saved harakat model"
        )
        assert stub._settings["translation.judge_model"] == "llama3.1:8b"
        assert any("wizard save kept" in rec.message for rec in caplog.records), (
            "the plan requires a log line when the guard fires"
        )

    def test_nonempty_selection_writes_through(self, wizard_pair, caplog):
        view, stub = wizard_pair
        view.state.translation_harakat_model = "translategemma:12b"
        view.state.translation_judge_model = "translategemma:12b"
        with caplog.at_level("INFO", logger="ui_qt.views.wizard_view"):
            view._save_translation_settings()
        assert stub._settings["translation.harakat_model"] == "translategemma:12b"
        assert stub._settings["translation.judge_model"] == "translategemma:12b"
        assert not any("wizard save kept" in rec.message for rec in caplog.records), (
            "the normal path must stay log-silent"
        )

    def test_both_empty_writes_through_unchanged(self, wizard_pair):
        """No saved model + empty selection → the write happens (a no-op) and
        must not raise — the guard only protects EXISTING values."""
        view, stub = wizard_pair
        stub._settings["translation.harakat_model"] = ""
        stub._settings["translation.judge_model"] = ""
        view._save_translation_settings()
        assert stub._settings["translation.harakat_model"] == ""


class TestB1Step6OffscreenRender:
    """The phase-gate render: Step 6 combos POPULATED from a stubbed
    controller (the pre-fix state rendered them empty every time)."""

    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_combos_populated_and_saved_model_selected(self, app, tmp_path):
        from ui_qt.views.wizard_steps import step6_translation as step6_mod
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step6_translation import Step6Translation

        stub = _StubController(
            settings={
                "translation.backend": "ollama",
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "translategemma:4b",
            },
            models=["qwen2.5:7b", "translategemma:4b"],
        )
        state = WizardState()
        # V0.7.4 (rework ⑥): the listing moved OFF the UI thread (the
        # W-b11 pattern — the old build-time sync HTTP call could freeze
        # the wizard open for the 5s timeout).  Stub the worker (no HTTP,
        # no stray thread), then drive the main-thread slot — the combos
        # seed from settings at build and the listing confirms them.
        orig = step6_mod.SimpleWorker
        step6_mod.SimpleWorker = _FakeWorker
        try:
            step6 = Step6Translation(stub, state)
        finally:
            step6_mod.SimpleWorker = orig
        try:
            # Seeded at build: the saved picks are already selected BEFORE
            # any listing runs (the V0.7.3 D14 pattern).
            assert step6.harakat_combo.currentData() == "qwen2.5:7b"
            assert step6.judge_combo.currentData() == "translategemma:4b"
            # The listing lands (the pre-fix B1 regression: both combos
            # were ALWAYS empty because the controller method didn't exist).
            step6._on_models_loaded(["qwen2.5:7b", "translategemma:4b"])
            assert step6.harakat_combo.count() == 2, "harakat combo must list the models"
            assert step6.judge_combo.count() == 3, (
                "judge combo = 2 models + the '(use summarization model)' empty item"
            )
            # The saved models stay selected after the listing.
            assert step6.harakat_combo.currentData() == "qwen2.5:7b"
            assert step6.judge_combo.currentData() == "translategemma:4b"
            # Backend + language keep their saved values.
            assert step6.backend_combo.currentData() == "ollama"
            assert step6.lang_combo.currentData() == "fa"
            # Render evidence (the wz_icons_check.py pattern): a real
            # offscreen grab proves the populated step actually paints.
            step6.resize(740, 540)
            grab = step6.grab()
            assert not grab.isNull()
            out = tmp_path / "v0686_step6_combos.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 0
        finally:
            step6.hide()
            step6.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════
# B5 — the wizard force-disabled translation every run
# ═══════════════════════════════════════════════════════════════════════════


class TestB5LoadPins:
    """_load_settings_into_state reads the translation settings (the
    load-then-save round-trip the plan locks)."""

    def test_load_reads_all_translation_settings(self):
        src = _method_src(_WIZARD, "_load_settings_into_state", "WizardView")
        for needle in (
            '"translation.enabled"',
            '"translation.backend"',
            '"translation.default_target_lang"',
            '"translation.harakat_model"',
            '"translation.judge_model"',
            '"translation.outputs.{_key}"',
        ):
            assert needle in src, f"load pin {needle!r} missing — the B5 round-trip is broken"

    def test_state_default_still_false_without_settings(self):
        """The dataclass default (shared.py translation_enabled=False) is
        unchanged — B5 fixes the LOAD, not the default (a fresh install with
        no saved settings still opens with translation off)."""
        src = _src(_SHARED)
        assert "translation_enabled: bool = False" in src


class TestB5RoundTripBehaviour:
    """The state-level characterization: open (load) → Start (save) keeps the
    user's saved translation settings unless Step 6 changed them."""

    @pytest.fixture
    def wizard_pair(self):
        _qt_or_skip()
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_view import WizardView

        stub = _StubController(
            settings={
                "translation.enabled": True,
                "translation.backend": "ollama",
                "translation.default_target_lang": "en",
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "translategemma:4b",
                # V0.7.4 (rework ⑥, D15): these pins protect the MANUAL
                # outputs round-trip — in mode A (the new default) the
                # outputs are intentionally derived from Step 4 at Start,
                # which is pinned separately in test_v0740_step6_translation.
                "translation.selection_mode": "manual",
                "translation.outputs.chapter_summaries": False,
                "translation.outputs.keypoints": True,
                "translation.outputs.mindmap": True,
            }
        )
        view = WizardView.__new__(WizardView)
        view.controller = stub
        view.state = WizardState()
        return view, stub

    def test_open_start_keeps_translation_enabled(self, wizard_pair):
        """The exact B5 repro: translation.enabled=true in settings must
        survive a wizard open→Start with the step untouched."""
        view, stub = wizard_pair
        view._load_settings_into_state()
        assert view.state.translation_enabled is True
        view._save_translation_settings()
        assert stub._settings["translation.enabled"] is True, (
            "the wizard must write back what the user chose (B5 wipe)"
        )

    def test_all_sibling_fields_round_trip(self, wizard_pair):
        view, stub = wizard_pair
        view._load_settings_into_state()
        view._save_translation_settings()
        assert stub._settings["translation.backend"] == "ollama"
        assert stub._settings["translation.default_target_lang"] == "en"
        assert stub._settings["translation.harakat_model"] == "qwen2.5:7b"
        assert stub._settings["translation.judge_model"] == "translategemma:4b"

    def test_output_selections_round_trip(self, wizard_pair):
        """The per-output choices survive too: pre-fix, a wizard Start reset
        translation.outputs.* to the dataclass defaults ({chapter_summaries,
        keypoints, podcast} True, the other eight False) — the same silent
        override family (the save writes these keys unconditionally)."""
        view, stub = wizard_pair
        view._load_settings_into_state()
        # chapter_summaries was UNchecked in settings; the dataclass default
        # says True — the load must win.
        assert view.state.translation_outputs["chapter_summaries"] is False
        assert view.state.translation_outputs["keypoints"] is True
        assert view.state.translation_outputs["mindmap"] is True
        view._save_translation_settings()
        assert stub._settings["translation.outputs.chapter_summaries"] is False
        assert stub._settings["translation.outputs.keypoints"] is True
        assert stub._settings["translation.outputs.mindmap"] is True

    def test_step_change_wins_over_loaded_value(self, wizard_pair):
        """The 'unless the step changed it' half: load enabled=True, the
        user UNchecks Step 6 (save_to_state) → the save writes the change."""
        view, stub = wizard_pair
        view._load_settings_into_state()
        view.state.translation_enabled = False  # the user's explicit choice
        view._save_translation_settings()
        assert stub._settings["translation.enabled"] is False

    def test_empty_settings_load_defaults(self):
        """Fresh install (nothing saved): the load keeps the dataclass
        defaults — translation still OFF until the user turns it on."""
        _qt_or_skip()
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_view import WizardView

        stub = _StubController()
        view = WizardView.__new__(WizardView)
        view.controller = stub
        view.state = WizardState()
        view._load_settings_into_state()
        assert view.state.translation_enabled is False
        assert view.state.translation_backend == "ollama"
        assert view.state.translation_target_lang == "fa"
        assert view.state.translation_harakat_model == ""


class TestB5FullWizardCharacterization:
    """The strongest form: the REAL full WizardView (all 10 steps built
    offscreen, isolated HOME per the wz_icons_check.py pattern) — open it,
    run the Start-path save, and the user's translation settings survive."""

    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_open_start_round_trip_on_the_real_wizard(self, app, tmp_path, monkeypatch):
        import tempfile

        monkeypatch.setenv("HOME", tempfile.mkdtemp(prefix="elixir-v0686-home-"))
        from ui_qt.views.wizard_steps import step6_translation as step6_mod
        from ui_qt.views.wizard_view import WizardView

        stub = _StubController(
            settings={
                "translation.enabled": True,
                "translation.backend": "ollama",
                "translation.default_target_lang": "fa",
                "translation.harakat_model": "qwen2.5:7b",
                "translation.judge_model": "translategemma:4b",
                "translation.outputs.chapter_summaries": False,
                # V0.7.4 (rework ⑥, D15): manual mode — this pin protects
                # the B5 outputs round-trip; mode A derives at Start (pinned
                # in test_v0740_step6_translation.py).
                "translation.selection_mode": "manual",
            },
            models=["qwen2.5:7b", "translategemma:4b"],
        )
        # V0.7.4: Step 6's listing now starts a worker at build — stub it
        # (no HTTP, no stray thread; the V0.7.3 Step-5 lesson).
        orig = step6_mod.SimpleWorker
        step6_mod.SimpleWorker = _FakeWorker
        try:
            view = WizardView(stub)
        finally:
            step6_mod.SimpleWorker = orig
        try:
            # Open: the state loaded the user's settings BEFORE the steps
            # were built, so Step 6 shows the truth.
            assert view.state.translation_enabled is True
            assert view.step6.enable_cb.isChecked(), (
                "Step 6's enable checkbox must reflect the loaded setting"
            )
            assert view.step6.harakat_combo.currentData() == "qwen2.5:7b"
            # Start: the exact _start_conversion save sequence for the
            # translation block (steps' save_to_state + the settings save).
            view.step6.save_to_state()
            view._save_translation_settings()
            assert stub._settings["translation.enabled"] is True, (
                "the real wizard's Start must keep translation enabled (B5)"
            )
            assert stub._settings["translation.harakat_model"] == "qwen2.5:7b"
            assert stub._settings["translation.outputs.chapter_summaries"] is False
        finally:
            view.hide()
            view.deleteLater()
