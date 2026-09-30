"""V18.20.4.5 (P4, task 2-b) — callback ownership tags (W-b10) + async
model refresh (W-b11).

Per the approved V18.20.4.0 SWOT roadmap (P4 cluster), the UI half of the
release (the dialogs/geometry/lifecycle half is task 2-c, base_dialog is
2-a):

- **W-b10:** three UI components fight over the Controller's SINGLE
  ``set_callbacks(on_progress, on_status, on_log, on_complete)`` slot —
  ConvertView (owner ``"convert_view"``, registered by task 2-c), the
  QueueView worker (owns them for the whole queue run) and the wizard
  bridge. ``WizardView.closeEvent`` used to UNCONDITIONALLY re-register
  ConvertView's callbacks on close: while a queue was running that
  silently STOLE the queue's callbacks — the queue's ``on_complete``
  result-capture stopped firing and per-book success modals popped from
  a hidden tab; ``_restore_convert_callbacks`` then restored stale
  callbacks. Fix: ``Controller.set_callbacks`` gained a fully
  backward-compatible ``owner: str | None = None`` keyword tag; the
  wizard tags itself ``"wizard"``; the queue tags itself ``"queue"`` and
  saves/restores the previous owner; ``closeEvent`` only restores when
  the current owner is NOT the queue (and logs the hold).
- **W-b11:** ``DependencyChecker().get_ollama_models()`` is a 5s-timeout
  HTTP call that ran ON the UI thread in the wizard's Step5Models
  ``_refresh_models`` and in THREE settings sections — opening Settings
  (or the wizard) could freeze the UI for 5s when Ollama was down. Fix:
  all fetches moved onto ``SimpleWorker`` (background QThread;
  ``finished``/``failed`` marshal to the MAIN thread), with a Python ref
  kept on the owner (``self._models_worker`` / ``combo._models_worker``)
  so the QObject can't be GC'd mid-run, refresh buttons disabled while
  loading and re-enabled in BOTH outcome handlers (the W-b18
  stuck-disabled class), and fail-soft failure (combos keep their items).
  The new module-level ``_populate_models_async`` replaces every
  constructor-time blocking populate site in sections.py.

Two layers, per the house pattern: headless-safe source pins (PySide6 is
NOT installed on this rig — the pinned files are read as text/AST, never
imported) + pure-Python behavioral tests on the REAL ``Controller``
(constructed with the markitdown sys.modules stub + hermetic Settings,
the tests/test_v182043_p2_settings_integrity.py pattern). No line-number
peeking — every function is sliced out by name via ``ast``.

V18.20.4.6 (P5 / O-b1) pin evolution, per the house "code moved → pin
slicing follows, assertion unchanged" precedent: wizard_view.py was
decomposed per-step into ui_qt/views/wizard_steps/ — the Step5Models
pins now slice ``wizard_steps/step5_models.py``, and the
exactly-one-owner-tag count spans wizard_view.py + every
``wizard_steps/*.py`` module. The WizardView pins (owner tag, closeEvent
guard, restore-only-in-else) still slice ``wizard_view.py``, which kept
the orchestrator. No assertion changed.
"""

from __future__ import annotations

import ast
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like
# tests/test_v182043_p2_settings_integrity.py (markitdown is not installed
# in this sandbox; the stub keeps the eager core.pipeline import chain
# loadable so the controller behavioral tests can construct a REAL
# Controller).
from utils.settings import Settings  # noqa: E402

_CONTROLLER = _project_root / "controller.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
# V18.20.4.6 (P5 / O-b1) pin evolution: the wizard's step classes moved
# to ui_qt/views/wizard_steps/ (bodies verbatim) — the Step5Models pins
# now slice the step module; the WizardView pins still slice
# wizard_view.py (the orchestrator stayed there). Assertions unchanged.
_WIZARD_STEPS = _project_root / "ui_qt" / "views" / "wizard_steps"
_STEP5_MODELS = _WIZARD_STEPS / "step5_models.py"
_QUEUE = _project_root / "ui_qt" / "views" / "queue_view.py"
# V0.4.19 (de-monolithization) pin evolution: sections.py became the
# sections/ package (17 section classes + helpers moved VERBATIM into
# per-family modules) — the W-b11 pins follow the moved bodies: the
# module-level async helpers now live in helpers.py; the three refresh
# sections live in ocr_sections.py / ai_model_section.py /
# defaults_section.py. Assertions unchanged.
_SECTIONS = _project_root / "ui_qt" / "settings" / "sections"
_HELPERS = _SECTIONS / "helpers.py"
_OCR_SECTIONS = _SECTIONS / "ocr_sections.py"
_AI_MODEL_SECTION = _SECTIONS / "ai_model_section.py"
_DEFAULTS_SECTION = _SECTIONS / "defaults_section.py"

_SECTION_CLASSES = ("OcrModelSection", "AiLocalModelSection", "DefaultsSection")
_SECTION_MODULES = {
    "OcrModelSection": _OCR_SECTIONS,
    "AiLocalModelSection": _AI_MODEL_SECTION,
    "DefaultsSection": _DEFAULTS_SECTION,
}


# ═══════════════════════════════════════════════════════════════════════════
# Helpers — source access WITHOUT line numbers (AST slicing by name)
# ═══════════════════════════════════════════════════════════════════════════


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sections_all_src() -> str:
    """V0.4.19: sections.py became the sections/ package — every module
    concatenated, so the whole-module pins keep their original file-wide
    semantics (the moved bodies are byte-identical)."""
    return "\n".join(_src(p) for p in sorted(_SECTIONS.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(_src(path))


def _class_node(tree: ast.Module, class_name: str) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    pytest.fail(f"class {class_name!r} not found")


def _func_node(
    tree: ast.Module,
    func_name: str,
    class_name: str | None = None,
) -> ast.FunctionDef:
    scope: ast.AST = tree
    if class_name is not None:
        scope = _class_node(tree, class_name)
    for node in ast.walk(scope):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return node
    where = f"{class_name}.{func_name}" if class_name else func_name
    pytest.fail(f"function {where!r} not found")


def _func_src(path: Path, func_name: str, class_name: str | None = None) -> str:
    """Full source of a module-level function or a class method, located
    purely by name via AST (the no-line-peeking contract)."""
    src = _src(path)
    node = _func_node(ast.parse(src), func_name, class_name)
    seg = ast.get_source_segment(src, node)
    assert seg is not None
    return seg


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    """Every Call in ``node``'s subtree whose callee is ``name`` (whether
    a plain name or an attribute, e.g. ``self._register_callbacks``)."""
    out: list[ast.Call] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == name) or (
                isinstance(f, ast.Attribute) and f.attr == name
            ):
                out.append(n)
    return out


def _call_keywords(call: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg}


def _kw_is_str(value: ast.expr, text: str) -> bool:
    return isinstance(value, ast.Constant) and value.value == text


def _contains_call_with_owner_kw(
    node: ast.AST,
    owner: str,
    callee: str,
) -> bool:
    for call in _calls_named(node, callee):
        kw = _call_keywords(call)
        if "owner" in kw and _kw_is_str(kw["owner"], owner):
            return True
    return False


@contextmanager
def _hermetic_settings(tmp_dir: Path):
    """Point the Settings singleton at a temp dir for the duration (the
    tests/test_v182043_p2_settings_integrity.py pattern), resetting it
    after."""
    Settings._instance = None
    Settings._test_override = None
    try:
        with (
            patch.object(Settings, "_settings_dir", tmp_dir),
            patch.object(Settings, "_settings_file", tmp_dir / "settings.json"),
        ):
            yield
    finally:
        Settings._instance = None
        Settings._test_override = None


# ═══════════════════════════════════════════════════════════════════════════
# W-b10 — Controller: the ``owner`` tag (source pins)
# ═══════════════════════════════════════════════════════════════════════════


class TestControllerOwnerPin:
    def test_set_callbacks_signature_has_owner_kwarg(self):
        node = _func_node(_tree(_CONTROLLER), "set_callbacks")
        args = node.args
        names = [a.arg for a in args.args if a.arg != "self"]
        assert names == ["on_progress", "on_status", "on_log", "on_complete", "owner"], (
            "set_callbacks must keep the four callback params and add a "
            "trailing ``owner`` param (W-b10)"
        )
        assert args.defaults[-1].value is None, (
            "owner must default to None (fully backward-compatible)"
        )
        ann = ast.unparse(args.args[-1].annotation)
        assert "str" in ann and "None" in ann

    def test_set_callbacks_stores_callback_owner(self):
        body = _func_src(_CONTROLLER, "set_callbacks")
        assert "self.callback_owner = owner" in body, (
            "set_callbacks must store the ownership tag (W-b10)"
        )

    def test_init_initializes_callback_owner_to_none(self):
        body = _func_src(_CONTROLLER, "__init__")
        assert "self.callback_owner" in body
        assert "self.callback_owner: str | None = None" in body, (
            "__init__ must initialize callback_owner to None (W-b10)"
        )

    def test_set_callbacks_still_assigns_the_four_callbacks(self):
        # The four assignments must survive unchanged (W-b10 is additive).
        # Whitespace-normalized: the legacy file aligns the '=' signs.
        flat = " ".join(_func_src(_CONTROLLER, "set_callbacks").split())
        for name in ("on_progress", "on_status", "on_log", "on_complete"):
            assert f"self.{name} = {name}" in flat, (
                f"callback assignment for {name} must be preserved"
            )


# ═══════════════════════════════════════════════════════════════════════════
# W-b10 — Controller: the ``owner`` tag (behavioral, REAL Controller)
# ═══════════════════════════════════════════════════════════════════════════


class TestControllerOwnerBehavior:
    def test_fresh_controller_owner_is_none(self, tmp_path):
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            assert c.callback_owner is None

    def test_owner_kwarg_sets_tag(self, tmp_path):
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            c.set_callbacks(on_progress=lambda v: None, owner="x")
            assert c.callback_owner == "x"

    def test_call_without_owner_resets_tag_to_none(self, tmp_path):
        """Backward compatibility: a legacy caller (no owner kwarg) resets
        the tag — the old call shape must behave exactly as before."""
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            c.set_callbacks(on_log=lambda m, lv: None, owner="queue")
            assert c.callback_owner == "queue"
            c.set_callbacks(on_log=lambda m, lv: None)
            assert c.callback_owner is None

    def test_positional_callers_unaffected(self, tmp_path):
        """All-arg positional callers (tests, legacy front-ends) must keep
        working — the new param is trailing + defaulted."""
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            p, s, lg, k = (lambda v: None, lambda m: None, lambda m, lv: None, lambda r: None)
            c.set_callbacks(p, s, lg, k)
            assert c.on_progress is p
            assert c.on_status is s
            assert c.on_log is lg
            assert c.on_complete is k
            assert c.callback_owner is None

    def test_callbacks_stored_exactly_when_owner_passed(self, tmp_path):
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            p, s, lg, k = (lambda v: None, lambda m: None, lambda m, lv: None, lambda r: None)
            c.set_callbacks(on_progress=p, on_status=s, on_log=lg, on_complete=k, owner="wizard")
            assert c.on_progress is p
            assert c.on_status is s
            assert c.on_log is lg
            assert c.on_complete is k
            assert c.callback_owner == "wizard"

    def test_convert_view_call_shape_is_valid(self, tmp_path):
        """The exact call task 2-c already placed in convert_view
        (``_register_callbacks``) must be accepted verbatim."""
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            c.set_callbacks(
                on_progress=lambda v: None,
                on_status=lambda m: None,
                on_log=lambda m, lv: None,
                on_complete=lambda r: None,
                owner="convert_view",
            )
            assert c.callback_owner == "convert_view"

    def test_wb10_queue_steal_scenario_at_controller_level(self, tmp_path):
        """The W-b10 sequence, simulated on a REAL Controller with the
        queue_view save/install/restore call shapes:

        ConvertView registers → queue installs (saves + tags "queue") →
        wizard registers mid-queue (the steal that used to happen on
        close) → the CLOSE GUARD sees owner "queue" and leaves them →
        queue ends → restore with the SAVED owner.

        After the (now guarded) wizard close + queue restore, the
        callbacks are ConvertView's again and the owner tag round-trips.
        """
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            cv = (lambda v: None, lambda m: None, lambda m, lv: None, lambda r: None)
            # convert_view._register_callbacks (task 2-c's call shape)
            c.set_callbacks(
                on_progress=cv[0],
                on_status=cv[1],
                on_log=cv[2],
                on_complete=cv[3],
                owner="convert_view",
            )
            # queue_view._install_queue_callbacks (save + install)
            saved = (c.on_progress, c.on_status, c.on_log, c.on_complete)
            saved_owner = getattr(c, "callback_owner", None)
            q = (lambda v: None, lambda m: None, lambda m, lv: None, lambda r: None)
            c.set_callbacks(
                on_progress=q[0], on_status=q[1], on_log=q[2], on_complete=q[3], owner="queue"
            )
            # wizard registers mid-queue (the wizard's own start call) —
            # in the buggy world, closeEvent then re-registered
            # convert_view's callbacks UNCONDITIONALLY, stealing from the
            # queue. The guard reads exactly this attribute:
            assert c.callback_owner == "queue", (
                "closeEvent's guard condition — queue must still own the "
                "callbacks, so the wizard close must leave them alone"
            )
            # queue_view._restore_convert_callbacks (restore + saved owner)
            c.set_callbacks(
                on_progress=saved[0],
                on_status=saved[1],
                on_log=saved[2],
                on_complete=saved[3],
                owner=saved_owner,
            )
            assert c.on_progress is cv[0]
            assert c.on_complete is cv[3]
            assert c.callback_owner == "convert_view"


# ═══════════════════════════════════════════════════════════════════════════
# W-b10 — wizard_view.py pins
# ═══════════════════════════════════════════════════════════════════════════


class TestWizardOwnerPins:
    def test_conversion_start_tags_owner_wizard(self):
        """The wizard's bridge set_callbacks (in _start_conversion) must
        tag itself as the wizard's (W-b10)."""
        start = _func_src(_WIZARD, "_start_conversion", "WizardView")
        assert _contains_call_with_owner_kw(ast.parse(start), "wizard", "set_callbacks"), (
            '_start_conversion must call set_callbacks with owner="wizard" (W-b10)'
        )
        # the same call wires the bridge handlers
        assert "on_complete=self.bridge.emit_complete" in start

    def test_wizard_has_exactly_one_owner_tag(self):
        # V18.20.4.6 (O-b1): the wizard now spans wizard_view.py + the
        # wizard_steps package — the count covers ALL of the wizard's
        # modules (assertion unchanged).
        tagged = []
        for path in (_WIZARD, *sorted(_WIZARD_STEPS.glob("*.py"))):
            for c in _calls_named(_tree(path), "set_callbacks"):
                if "owner" in _call_keywords(c):
                    tagged.append(c)
        assert len(tagged) == 1, (
            "exactly one set_callbacks call in the wizard modules carries "
            "an owner tag (the conversion-start bridge)"
        )
        assert _kw_is_str(_call_keywords(tagged[0])["owner"], "wizard")

    def test_close_event_reads_callback_owner(self):
        body = _func_src(_WIZARD, "closeEvent", "WizardView")
        assert 'getattr(self.controller, "callback_owner", None)' in body, (
            "closeEvent must consult controller.callback_owner (W-b10)"
        )
        assert 'owner == "queue"' in body, "the guard must refuse to steal from the queue owner"

    def test_close_event_restore_only_in_else_branch(self):
        """The ``convert_view._register_callbacks()`` restore must be
        conditional — it may only run in the else branch of the
        ``owner == "queue"`` guard, never unconditionally."""
        src = _src(_WIZARD)
        node = _func_node(ast.parse(src), "closeEvent", "WizardView")
        restores = _calls_named(node, "_register_callbacks")
        assert len(restores) == 1, "closeEvent must contain exactly one _register_callbacks call"
        restore = restores[0]
        # find the guard If: ``if owner == "queue":`` (ast.unparse quotes
        # string constants with single quotes — normalize)
        guard = None
        for n in ast.walk(node):
            if isinstance(n, ast.If):
                cond = ast.unparse(n.test).replace("'", '"')
                if 'owner == "queue"' in cond or '"queue" == owner' in cond:
                    guard = n
                    break
        assert guard is not None, 'owner == "queue" guard If not found'
        in_else = any(restore is sub or restore in ast.walk(sub) for sub in guard.orelse)
        assert in_else, (
            "the _register_callbacks restore must live ONLY in the "
            "guard's else branch (W-b10) — an unconditional restore "
            "steals the queue's callbacks mid-run"
        )
        # and the guard branch itself must NOT restore
        in_body = any(restore is sub or restore in ast.walk(sub) for sub in guard.body)
        assert not in_body

    def test_close_event_logs_the_queue_hold(self):
        body = _func_src(_WIZARD, "closeEvent", "WizardView")
        assert "Queue owns the controller callbacks" in body, (
            "the queue-owns hold must be visible in the wizard log (the "
            "W-c13 silent-fail-soft lesson)"
        )
        assert "W-b10" in body  # fix-documentation citation survives


# ═══════════════════════════════════════════════════════════════════════════
# W-b10 — queue_view.py pins
# ═══════════════════════════════════════════════════════════════════════════


class TestQueueOwnerPins:
    def test_install_tags_queue_owner(self):
        body = _func_src(_QUEUE, "_install_queue_callbacks", "QueueView")
        assert _contains_call_with_owner_kw(ast.parse(body), "queue", "set_callbacks"), (
            '_install_queue_callbacks must install with owner="queue"'
        )

    def test_install_saves_previous_owner(self):
        body = _func_src(_QUEUE, "_install_queue_callbacks", "QueueView")
        assert (
            'self._saved_callback_owner = getattr(self.controller, "callback_owner", None)'
        ) in body, "the previous owner tag must be saved alongside the callbacks"

    def test_install_still_saves_the_four_callbacks(self):
        # the save-restore mechanism is unchanged (W-b10 is additive)
        body = _func_src(_QUEUE, "_install_queue_callbacks", "QueueView")
        for attr in ("on_progress", "on_status", "on_log", "on_complete"):
            assert f"self.controller.{attr}" in body, (
                f"{attr} must still be saved for the post-queue restore"
            )

    def test_restore_uses_saved_owner(self):
        body = _func_src(_QUEUE, "_restore_convert_callbacks", "QueueView")
        assert "owner=self._saved_callback_owner" in body, (
            "the restore must hand the callbacks back with their ORIGINAL "
            'owner tag (usually "convert_view")'
        )

    def test_restore_resets_saved_owner(self):
        body = _func_src(_QUEUE, "_restore_convert_callbacks", "QueueView")
        assert "self._saved_callback_owner = None" in body

    def test_init_initializes_saved_owner(self):
        body = _func_src(_QUEUE, "__init__", "QueueView")
        assert "self._saved_callback_owner: str | None = None" in body, (
            "the owner tag must be initialized in __init__ alongside self._saved_callbacks"
        )


# ═══════════════════════════════════════════════════════════════════════════
# W-b11 — wizard_view.py: async model refresh
# ═══════════════════════════════════════════════════════════════════════════


class TestWizardAsyncModelsPins:
    def test_refresh_models_uses_simple_worker(self):
        body = _func_src(_STEP5_MODELS, "_refresh_models", "Step5Models")
        # V0.04: the worker fn is now backend-dispatched (worker_fn =
        # llamacpp_fetch_models | self._get_models) — the W-b11 intent is
        # that the FETCH runs on a SimpleWorker, whichever fn it is.
        assert "SimpleWorker(worker_fn)" in body, (
            "the 5s-timeout HTTP fetch must run on a SimpleWorker (W-b11)"
        )
        assert "self._models_worker = SimpleWorker" in body
        assert ".finished.connect(self._on_models_loaded)" in body
        assert ".failed.connect(self._on_models_failed)" in body
        assert ".start()" in body

    def test_refresh_models_keeps_worker_ref_and_guards(self):
        """A Python ref must keep the worker alive (the QObject GC hazard)
        and a re-entrancy guard must prevent stacking fetches."""
        body = _func_src(_STEP5_MODELS, "_refresh_models", "Step5Models")
        assert "is_running()" in body, "re-entrancy guard: don't stack model fetches"
        assert "self._models_worker" in body

    def test_refresh_models_no_longer_blocks(self):
        """The old body fetched synchronously on the UI thread
        (``models = self._get_models()``) — that call must be GONE from
        the method; _get_models only survives as the worker fn."""
        body = _func_src(_STEP5_MODELS, "_refresh_models", "Step5Models")
        assert "self._get_models()" not in body, (
            "_refresh_models must not call the blocking fetch directly"
        )

    def test_models_worker_initialized_in_build(self):
        body = _func_src(_STEP5_MODELS, "_build", "Step5Models")
        assert "self._models_worker = None" in body

    def test_refresh_button_disabled_while_loading(self):
        body = _func_src(_STEP5_MODELS, "_refresh_models", "Step5Models")
        assert "self.refresh_btn.setEnabled(False)" in body, (
            "the refresh button must be disabled while a fetch is in flight"
        )

    def test_on_models_loaded_reenables_and_populates(self):
        """finished handler: re-enable the button, keep the exact
        populate semantics (remember selections → clear → addItems →
        findData/setCurrentIndex) on the MAIN thread."""
        body = _func_src(_STEP5_MODELS, "_on_models_loaded", "Step5Models")
        assert "self.refresh_btn.setEnabled(True)" in body
        assert "No models found" in body, "the empty-models information box must survive verbatim"
        assert "ollama pull gemma4-12b:latest" in body
        for attr in ("summ_combo", "ocr_combo", "fast_combo"):
            assert f"self.{attr}.currentData()" in body
        assert "combo.clear()" in body
        assert "combo.addItem" in body
        assert "combo.findData(current)" in body
        assert "combo.setCurrentIndex(idx)" in body

    def test_on_models_failed_fail_soft(self):
        """failed handler: re-enable the button (the W-b18
        stuck-disabled class), keep the combos' items, never raise."""
        body = _func_src(_STEP5_MODELS, "_on_models_failed", "Step5Models")
        assert "self.refresh_btn.setEnabled(True)" in body
        assert "raise" not in body

    def test_get_models_stays_the_pure_worker_fn(self):
        body = _func_src(_STEP5_MODELS, "_get_models", "Step5Models")
        assert "DependencyChecker().get_ollama_models()" in body
        # widget-free: the fn must not ACCESS widgets — no combo/button
        # METHOD CALLS (V0.04: the fn reads plain snapshot attributes
        # stashed by _refresh_models on the main thread; its docstring
        # merely MENTIONS the combo, which the old literal 'combo'
        # substring pin false-positived on).
        assert ".currentData()" not in body
        assert ".currentText()" not in body
        assert ".text()" not in body
        assert "refresh_btn" not in body


# ═══════════════════════════════════════════════════════════════════════════
# W-b11 — sections.py: async model refresh
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionsAsyncModelsPins:
    def test_imports_simple_worker(self):
        src = _src(_HELPERS)
        assert "from ui_qt.components.simple_worker import SimpleWorker" in src

    def test_populate_models_async_helper_shape(self):
        """The module-level constructor-site helper: fetch on the worker,
        populate on the main thread, worker ref kept on the combo,
        fail-soft on error."""
        body = _func_src(_HELPERS, "_populate_models_async")
        assert "SimpleWorker(_get_ollama_models, controller)" in body
        assert "combo._models_worker = worker" in body, (
            "the combo must hold a Python ref to the worker (QObject GC)"
        )
        assert "worker.finished.connect(_apply)" in body
        assert "worker.failed.connect" in body
        assert "worker.start()" in body
        # V0.13: format-wrapped — pin the arg list on its continuation line
        assert (
            "combo, models or [], current=current, allow_empty=allow_empty, prefer_ocr=prefer_ocr"
            in body
        )

    def test_no_sync_populate_receives_get_ollama_models(self):
        """THE W-b11 core regression pin: no synchronous ``_populate_models``
        call may receive the blocking fetch (``_get_ollama_models(...)``)
        as a direct argument anymore — every such site must go through
        ``_populate_models_async``."""
        tree = ast.parse(_sections_all_src())
        offenders = []
        for call in _calls_named(tree, "_populate_models"):
            # skip the call inside _populate_models_async's finished
            # handler (that one receives the fetched list, not a fetch)
            for arg in call.args:
                for sub in ast.walk(arg):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Name)
                        and sub.func.id == "_get_ollama_models"
                    ):
                        offenders.append(ast.unparse(call))
        assert not offenders, (
            "blocking model fetch passed directly to _populate_models "
            f"(must be _populate_models_async): {offenders}"
        )

    def test_shared_refresh_helper_contract(self):
        """The one shared helper the three sections use: re-entrancy guard,
        button disable before spawn, re-enable in BOTH outcome handlers,
        worker ref on the section, fail-soft."""
        body = _func_src(_HELPERS, "_refresh_models_async")
        assert "is_running()" in body
        assert "refresh_btn.setEnabled(False)" in body
        assert body.count("refresh_btn.setEnabled(True)") == 2, (
            "both the finished AND failed handlers must re-enable the "
            "button (W-b18 stuck-disabled class)"
        )
        assert "section._models_worker = w" in body
        assert "w.start()" in body
        assert "on_loaded(models or [])" in body

    def test_three_sections_refresh_via_shared_helper(self):
        for cls in _SECTION_CLASSES:
            body = _func_src(_SECTION_MODULES[cls], "_refresh_models", cls)
            assert "_refresh_models_async(" in body, (
                f"{cls}._refresh_models must route through the shared async helper (W-b11)"
            )
            # no blocking fetch CALL inside the method (AST, so the
            # W-b11 fix comments can't false-trigger the pin)
            node = _func_node(ast.parse(_src(_SECTION_MODULES[cls])), "_refresh_models", cls)
            assert not _calls_named(node, "get_ollama_models"), (
                f"{cls}._refresh_models must not run the blocking HTTP fetch on the UI thread"
            )

    def test_three_sections_have_models_loaded_handler(self):
        for cls in _SECTION_CLASSES:
            _func_src(_SECTION_MODULES[cls], "_on_models_loaded", cls)  # must exist

    def test_ocr_section_populate_semantics_kept(self):
        body = _func_src(_OCR_SECTIONS, "_on_models_loaded", "OcrModelSection")
        assert "self.primary_combo" in body
        assert "self.fallback_combo" in body
        assert body.count("prefer_ocr=True") == 2
        assert "ocr.primary_model" in body
        assert "ocr.fallback_model" in body

    def test_ai_local_section_populate_semantics_kept(self):
        body = _func_src(_AI_MODEL_SECTION, "_on_models_loaded", "AiLocalModelSection")
        for combo in ("summary_combo", "fast_model_combo", "heavy_combo", "simplification_combo"):
            assert f"self.{combo}" in body
        assert body.count("allow_empty=True") == 2
        assert "summarisation.model" in body
        assert "summarisation.fast_model" in body
        assert "summarisation.heavy_model" in body
        assert "summarisation.simplification_model" in body

    def test_defaults_section_populate_semantics_kept(self):
        body = _func_src(_DEFAULTS_SECTION, "_on_models_loaded", "DefaultsSection")
        assert "self.summ_model_combo" in body
        assert "self.ocr_model_combo" in body
        assert "setEditText(target)" in body, (
            "the editable-combo typed-text restore must survive verbatim"
        )
        assert "Default (use summarisation.model)" in body
        assert "Default (use ocr.primary_model)" in body
        assert "quick_services.defaults.summarize_model" in body
        assert "quick_services.defaults.ocr_model" in body

    def test_three_sections_store_refresh_btn_for_disable_enable(self):
        for cls in _SECTION_CLASSES:
            init = _func_src(_SECTION_MODULES[cls], "__init__", cls)
            assert "self.refresh_btn = QPushButton" in init, (
                f"{cls} must keep the refresh button on self so the async "
                "refresh can disable/re-enable it"
            )
            refresh = _func_src(_SECTION_MODULES[cls], "_refresh_models", cls)
            assert "self.refresh_btn" in refresh, (
                f"{cls} must pass its refresh button to the async helper"
            )

    def test_three_sections_init_models_worker_none(self):
        for cls in _SECTION_CLASSES:
            init = _func_src(_SECTION_MODULES[cls], "__init__", cls)
            assert "self._models_worker = None" in init, (
                f"{cls} must initialize the worker ref (GC hazard)"
            )

    def test_constructor_time_populates_are_async(self):
        """The blocking constructor-time sites (~337/347/354 + reload
        ~613/621 in the SWOT) are replaced by _populate_models_async."""
        init = _func_src(_AI_MODEL_SECTION, "__init__", "AiLocalModelSection")
        # V0.13: format-wrapped — combo + controller on the following line
        assert (
            "_populate_models_async(\n            self.fast_model_combo,\n            controller,"
            in init
        )
        # the fast-combo ↻ refresh click routes through the async helper
        assert "lambda: _populate_models_async(" in init
        reload_src = _func_src(_AI_MODEL_SECTION, "reload", "AiLocalModelSection")
        assert "_populate_models_async(\n            self.fast_model_combo, c," in reload_src
        # ...and the synchronous shapes are gone everywhere in the package
        src = _sections_all_src()
        assert "lambda: _populate_models(" not in src

    def test_fetch_models_from_is_widget_free(self):
        """AiLocalModelSection's fetch must be callable on the worker
        thread: the URL is snapshotted on the main thread and the actual
        fetch takes it as a plain argument (no combo reads).

        V0.6.8 (audit B5, contract evolution): the fetch now routes through
        the shared proxy-proof transports (list_llamacpp_models for the
        OpenAI-style LM Studio probe, list_ollama_models for /api/tags)
        instead of a self-built requests.Session — the old
        ``assert "requests" in body`` pin was updated to the new transport
        contract. The widget-free property is unchanged."""
        body = _func_src(_AI_MODEL_SECTION, "_fetch_models_from", "AiLocalModelSection")
        assert "def _fetch_models_from(self, url: str)" in body
        assert "list_llamacpp_models(" in body
        assert "list_ollama_models(" in body
        assert "self." not in body.replace("def _fetch_models_from(self, url: str)", ""), (
            "_fetch_models_from must not touch any widget (worker-safe)"
        )
        wrapper = _func_src(_AI_MODEL_SECTION, "_fetch_models", "AiLocalModelSection")
        assert "return self._fetch_models_from(self._backend_url())" in wrapper

    def test_ai_local_refresh_snapshots_url_on_main_thread(self):
        """_refresh_models must read the backend combos (widget reads) on
        the MAIN thread and hand the widget-free fn to the worker."""
        body = _func_src(_AI_MODEL_SECTION, "_refresh_models", "AiLocalModelSection")
        assert "self._backend_url()" in body
        assert "_fetch_models_from" in body
        assert "_refresh_models_async(" in body
