"""V18.20.4.6 (P5, O-b1) — the wizard_view.py per-step split + W-b20.

Per the approved V18.20.4.0 SWOT roadmap (P5 cluster):

- **O-b1:** ``ui_qt/views/wizard_view.py`` was a ~3,850-line / 12-class
  monolith — the single biggest file in the UI. It is decomposed
  per-step: every step class moved VERBATIM (byte-identical bodies;
  only top-of-file imports differ) into the new
  ``ui_qt/views/wizard_steps/`` package — one module per step plus
  ``shared.py`` for the step-common ``WizardState`` dataclass and the
  ``WizardStep`` base. ``wizard_view.py`` keeps the ``WizardView``
  orchestrator (navigation, ``_start_conversion`` with the W-b10
  owner-tagged bridge install, ``closeEvent`` with the queue-owner
  guard, the hardware-monitor bridge wiring, the elapsed timer) and
  re-exports every pre-split public name — a back-compat facade (the
  external importers, app.py and convert_view.py, only ever imported
  ``WizardView``; every step name stays importable from
  ``ui_qt.views.wizard_view``).
- **W-b20:** ``app.py``'s dead ``hallucination_audit_view`` branch in
  ``_toggle_theme`` — the attribute is never assigned anywhere in the
  tree (the hallucination audit opens from convert_view, not the main
  window) — is deleted.

All pins are headless-safe source/AST parsing (PySide6 is NOT installed
on this rig — no ``ui_qt`` module is imported here); the verbatim
spot-checks read the PRE-SPLIT file out of the shipped V18.20.4.5 zip
and are skipped when that reference zip is absent. No line-number
peeking — everything is located by name via ``ast``.
"""
from __future__ import annotations

import ast
import zipfile
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_STEPS = _project_root / "ui_qt" / "views" / "wizard_steps"
_APP = _project_root / "ui_qt" / "app.py"
_CONVERT_VIEW = _project_root / "ui_qt" / "views" / "convert_view.py"
_UI_QT = _project_root / "ui_qt"

# The shipped pre-split reference (the O-b1 move happened after .4.5).
_REF_ZIP = _project_root.parent.parent / "download" / (
    "Elixir-V18.20.4.5.zip")
_REF_MEMBER = "Elixir-V18.20.4.5/ui_qt/views/wizard_view.py"

# Every top-level class the pre-split wizard_view.py defined, and its
# new home module (the O-b1 decomposition map).
_STEP_CLASSES = {
    "Step1Pdf": "step1_pdf.py",
    "Step2Range": "step2_range.py",
    "Step3Ocr": "step3_ocr.py",
    "Step4Outputs": "step4_outputs.py",
    "Step5Models": "step5_models.py",
    "Step6Translation": "step6_translation.py",
    "Step7Advanced": "step7_advanced.py",
    "Step7bFineTune": "step7b_fine_tune.py",
    "Step8Review": "step8_review.py",
    "Step9Logs": "step9_logs.py",
}
_SHARED_CLASSES = ("WizardState", "WizardStep")
_ALL_PRE_SPLIT_CLASSES = (
    *_SHARED_CLASSES, *_STEP_CLASSES.keys(), "WizardView")


# ── helpers (headless-safe: source text + AST only, by name) ────────────────

def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.Module:
    return ast.parse(_src(path))


def _classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    classes = _classes(tree)
    assert name in classes, f"class {name!r} not found"
    return classes[name]


def _segment(src: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(src, node)
    assert seg is not None
    return seg


def _method_src(path: Path, func_name: str, class_name: str) -> str:
    """Full source of a class method, located by name via AST."""
    src = _src(path)
    node = None
    for n in ast.walk(_class(ast.parse(src), class_name)):
        if isinstance(n, ast.FunctionDef) and n.name == func_name:
            node = n
            break
    assert node is not None, f"{class_name}.{func_name} not found"
    return _segment(src, node)


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """name -> source module for every top-level ``from X import name``."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                out[alias.asname or alias.name] = node.module or ""
    return out


def _wizard_imports_of(path: Path) -> set[str]:
    """Every name any module-level or nested ``from
    ui_qt.views.wizard_view import ...`` in ``path`` pulls in."""
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom):
            if node.module == "ui_qt.views.wizard_view":
                names.update(alias.asname or alias.name for alias in node.names)
    return names


# ═══════════════════════════════════════════════════════════════════════════
# (a) The split structure — one module per step under wizard_steps/
# ═══════════════════════════════════════════════════════════════════════════

class TestSplitStructure:
    def test_package_has_one_module_per_step_plus_shared(self):
        expected = {"__init__.py", "shared.py"} | set(_STEP_CLASSES.values())
        actual = {p.name for p in _STEPS.glob("*.py")}
        assert actual == expected, (
            f"wizard_steps/ file set drifted: {actual ^ expected}"
        )

    def test_every_step_module_defines_exactly_its_step_class(self):
        for cls, mod in _STEP_CLASSES.items():
            classes = _classes(_tree(_STEPS / mod))
            assert set(classes) == {cls}, (
                f"{mod} must define exactly {cls} (found {set(classes)})"
            )

    def test_shared_holds_state_and_base(self):
        assert set(_classes(_tree(_STEPS / "shared.py"))) == set(
            _SHARED_CLASSES)

    def test_wizard_view_now_defines_only_the_orchestrator(self):
        assert set(_classes(_tree(_WIZARD))) == {"WizardView"}, (
            "the step classes must MOVE OUT of wizard_view.py (O-b1), "
            "not be duplicated there"
        )

    def test_step_classes_subclass_the_shared_base(self):
        for cls, mod in _STEP_CLASSES.items():
            node = _class(_tree(_STEPS / mod), cls)
            base_names = {
                b.id if isinstance(b, ast.Name)
                else b.attr if isinstance(b, ast.Attribute) else ""
                for b in node.bases
            }
            assert "WizardStep" in base_names, (
                f"{cls} must still derive from WizardStep"
            )

    def test_step_modules_import_the_shared_base_not_wizard_view(self):
        """The package must be acyclic: steps reach the base via
        wizard_steps.shared; nothing under wizard_steps/ imports back
        into wizard_view."""
        for mod in _STEP_CLASSES.values():
            bindings = _import_bindings(_tree(_STEPS / mod))
            assert bindings.get("WizardStep") == (
                "ui_qt.views.wizard_steps.shared"), (
                f"{mod} must import WizardStep from wizard_steps.shared"
            )
            assert not any(
                m == "ui_qt.views.wizard_view"
                for m in bindings.values()
            ), f"{mod} imports wizard_view back (import cycle)"

    def test_all_new_modules_parse(self):
        for path in (_WIZARD, *sorted(_STEPS.glob("*.py"))):
            ast.parse(_src(path))  # headless syntax guard

    def test_wizard_view_is_no_longer_the_monolith(self):
        """The O-b1 goal: the former ~3,850-line file is decomposed; the
        orchestrator module stays comfortably under 2,000 lines."""
        assert len(_src(_WIZARD).splitlines()) < 2000
        for mod in _STEP_CLASSES.values():
            n = len(_src(_STEPS / mod).splitlines())
            assert n < 1000, f"{mod} grew past the per-step budget ({n})"


# ═══════════════════════════════════════════════════════════════════════════
# (b) The facade — every pre-split public name still importable
# ═══════════════════════════════════════════════════════════════════════════

class TestFacade:
    def test_facade_provides_every_pre_split_public_name(self):
        """All 13 top-level classes of the pre-split module are provided
        by wizard_view.py — defined there (WizardView) or bound by a
        from-import from the wizard_steps package."""
        tree = _tree(_WIZARD)
        defined = set(_classes(tree))
        imported = _import_bindings(tree)
        for name in _ALL_PRE_SPLIT_CLASSES:
            assert name in defined or name in imported, (
                f"{name} is no longer importable from "
                "ui_qt.views.wizard_view (facade contract)"
            )
        for name in (*_SHARED_CLASSES, *_STEP_CLASSES):
            assert imported.get(name, "").startswith(
                "ui_qt.views.wizard_steps"), (
                f"{name} must be re-exported from the wizard_steps package"
            )

    def test_facade_all_is_explicit(self):
        """__all__ documents the re-export surface verbatim."""
        tree = _tree(_WIZARD)
        all_node = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        all_node = node.value
        assert all_node is not None, "wizard_view must declare __all__"
        names = {
            e.value for e in all_node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
        assert names == set(_ALL_PRE_SPLIT_CLASSES)

    def test_external_importers_names_resolve(self):
        """The recorded external importers (app.py, convert_view.py)
        import from ui_qt.views.wizard_view — every name they pull must
        still be provided by the facade/definition."""
        provided = set(_classes(_tree(_WIZARD))) | set(
            _import_bindings(_tree(_WIZARD)))
        for path in (_APP, _CONVERT_VIEW):
            for name in _wizard_imports_of(path):
                assert name in provided, (
                    f"{path.name} imports {name} from wizard_view — the "
                    "facade must keep providing it"
                )

    def test_external_importers_are_unchanged(self):
        """The two import sites stay exactly as recorded (a lazy import
        inside _open_wizard in each file)."""
        assert _wizard_imports_of(_APP) == {"WizardView"}
        assert _wizard_imports_of(_CONVERT_VIEW) == {"WizardView"}


# ═══════════════════════════════════════════════════════════════════════════
# (c) Verbatim move — byte-identical bodies vs the pre-split .4.5 file
# ═══════════════════════════════════════════════════════════════════════════

class TestVerbatimMove:
    @classmethod
    def _pre_split_src(cls) -> str:
        if not _REF_ZIP.exists():
            pytest.skip(
                f"pre-split reference zip not present: {_REF_ZIP}")
        with zipfile.ZipFile(_REF_ZIP) as zf:
            return zf.read(_REF_MEMBER).decode("utf-8")

    def _new_home(self, name: str) -> Path:
        if name in _SHARED_CLASSES:
            return _STEPS / "shared.py"
        if name in _STEP_CLASSES:
            return _STEPS / _STEP_CLASSES[name]
        assert name == "WizardView"
        return _WIZARD

    def test_every_moved_class_body_is_byte_identical(self):
        old = self._pre_split_src()
        old_classes = _classes(ast.parse(old))
        assert set(old_classes) == set(_ALL_PRE_SPLIT_CLASSES), (
            "the reference .4.5 file must still match the pre-split shape"
        )
        for name in _ALL_PRE_SPLIT_CLASSES:
            path = self._new_home(name)
            new_src = _src(path)
            new_seg = _segment(new_src, _class(ast.parse(new_src), name))
            old_seg = _segment(old, old_classes[name])
            if name in ("Step5Models", "WizardView"):
                # V18.20.4.9 (BK1 / W-b18 remainder + W-b14/W-b15/W-b17):
                # the two cloud TEST workers gained kept refs + ``failed``
                # handlers (Step5Models), and the WizardView log hot path
                # hoisted its per-line imports/regexes (W-b14), gained the
                # JSON-first quality-dashboard source (W-b15) and the
                # traceback-before-box log (W-b17). Both class bodies are
                # therefore no longer byte-identical — byte-identity is
                # still enforced METHOD-by-method with guarded, documented
                # substitutions (the P6 test_v182047 evolution pattern;
                # every additional drift still fails).
                self._assert_documented_evolution(
                    name, new_seg, old_seg,
                    self._WB18R_NEW_METHODS if name == "Step5Models"
                    else self._WB15_NEW_METHODS,
                    self._STEP5_SUBS if name == "Step5Models"
                    else self._WIZARD_SUBS)
                continue
            assert new_seg == old_seg, (
                f"{name}'s body drifted in the O-b1 split (must be "
                "byte-identical; only top-of-file imports differ)"
            )

    def _assert_documented_evolution(
        self, class_name: str, new_seg: str, old_seg: str,
        allowed_new: set[str], substitutions: dict[str, list[tuple[str, str]]],
    ) -> None:
        """Byte-identity per METHOD with only the documented exceptions:
        the methods named in ``substitutions`` (each replacement guarded —
        the OLD text is asserted present in the reference first, so any
        additional drift still fails) + the NEW methods in
        ``allowed_new``."""
        def _methods_of(seg: str) -> dict[str, str]:
            cls = ast.parse(seg).body[0]
            assert isinstance(cls, ast.ClassDef)
            return {n.name: _segment(seg, n) for n in cls.body
                    if isinstance(n, ast.FunctionDef)}

        new_m = _methods_of(new_seg)
        old_m = _methods_of(old_seg)
        assert set(new_m) - set(old_m) == allowed_new, (
            f"only the documented BK1 additions may be NEW on {class_name}: "
            f"{sorted(set(new_m) - set(old_m))}"
        )
        assert set(old_m) - set(new_m) == set(), (
            f"no pre-split {class_name} method may be deleted"
        )
        for name, new_body in new_m.items():
            if name in allowed_new:
                continue
            expected = old_m[name]
            for old_frag, new_frag in substitutions.get(name, []):
                assert old_frag in expected, (
                    f"{class_name}.{name}: guarded anchor missing in the "
                    "reference (drift beyond the documented evolution)"
                )
                expected = expected.replace(old_frag, new_frag, 1)
            assert new_body == expected, (
                f"{class_name}.{name} drifted beyond the documented BK1 "
                "evolution (byte-identity is still enforced for every "
                "other method)"
            )

    # V18.20.4.9 (BK1 / W-b18 remainder) — the ONLY sanctioned Step5Models
    # drift since the O-b1 split: the two cloud TEST methods' docstring
    # notes + the bare ``SimpleWorker(_run).start()`` became kept-ref
    # spawns with ``failed`` connected, plus the two NEW fail-soft
    # handlers (re-enable via the EXISTING result slots — no new
    # user-visible strings).
    _WB18R_NEW_METHODS = {"_on_cloud_test_failed", "_on_fast_cloud_test_failed"}
    _STEP5_SUBS: dict[str, list[tuple[str, str]]] = {
        "_test_cloud_connection": [
            (
                "        Runs in a background thread so the UI doesn't freeze; marshals the\n"
                "        result back to the UI thread via a no-arg queued slot.\n"
                '        """\n',
                "        Runs in a background thread so the UI doesn't freeze; marshals the\n"
                "        result back to the UI thread via a no-arg queued slot.\n"
                "\n"
                "        V18.20.4.9 (W-b18 remainder): the worker's ``failed`` signal is now\n"
                "        connected (``_on_cloud_test_failed``) and the ref is kept on self.\n"
                "        The result slot is only reached on success — a raising test used\n"
                "        to leave ``cloud_test_btn`` disabled forever with the worker\n"
                "        GC'd mid-run.\n"
                '        """\n',
            ),
            (
                "        SimpleWorker(_run).start()",
                "        w = SimpleWorker(_run)\n"
                "        self._cloud_test_worker = w  # Python ref (GC hazard, W-b11 pattern)\n"
                "        w.failed.connect(self._on_cloud_test_failed)\n"
                "        w.start()",
            ),
        ],
        "_test_fast_cloud_connection": [
            (
                '        """V16.0.9: Send a tiny request to verify the fast cloud endpoint works."""\n',
                '        """V16.0.9: Send a tiny request to verify the fast cloud endpoint works.\n'
                "\n"
                "        V18.20.4.9 (W-b18 remainder): same shape as the heavy test above —\n"
                "        ``failed`` connected + ref kept, so a raising test re-enables the\n"
                "        button instead of sticking it disabled.\n"
                '        """\n',
            ),
            (
                "        SimpleWorker(_run).start()",
                "        w = SimpleWorker(_run)\n"
                "        self._fast_cloud_test_worker = w  # Python ref (GC hazard, W-b11 pattern)\n"
                "        w.failed.connect(self._on_fast_cloud_test_failed)\n"
                "        w.start()",
            ),
        ],
    }

    # V18.20.4.9 (BK1 / W-b14 + W-b15 + W-b17) — the ONLY sanctioned
    # WizardView drift since the O-b1 split: the log hot path's per-line
    # imports/regexes hoisted to module level, the JSON-first quality
    # dashboard landing at completion (one NEW method + its call), and
    # the traceback-before-box log on the build-request failure.
    _WB15_NEW_METHODS = {"_update_quality_dashboard_from_report"}
    _WIZARD_SUBS: dict[str, list[tuple[str, str]]] = {
        "_start_conversion": [
            (
                '        except Exception as e:\n'
                '            QMessageBox.critical(self, "Error", f"Failed to build conversion request: {e}")\n',
                '        except Exception as e:\n'
                '            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the\n'
                '            # user box (was str(e)-only — zero diagnostics).\n'
                '            logger.warning("failed to build conversion request",\n'
                '                           exc_info=True)\n'
                '            QMessageBox.critical(self, "Error", f"Failed to build conversion request: {e}")\n',
            ),
        ],
        "_on_status": [
            (
                "        # V7.1.0 S15: Track phase start time for time estimates\n"
                "        import time\n",
                "        # V7.1.0 S15: Track phase start time for time estimates\n"
                "        # (W-b14: ``time`` is a module-level import — was per-call.)\n",
            ),
        ],
        "_update_time_estimate": [
            (
                '        """V7.1.0 S15: Calculate and display estimated time remaining."""\n'
                "        import time\n",
                '        """V7.1.0 S15: Calculate and display estimated time remaining."""\n'
                "        # (W-b14: ``time`` is a module-level import — was per-call.)\n",
            ),
        ],
        "_on_log": [
            (
                "        # V10.21.0: Update quality dashboard from log messages\n"
                "        import re as _re\n",
                "        # V10.21.0: Update quality dashboard from log messages\n"
                "        # (W-b14: module-level compiled regex — was ``import re`` + two\n"
                "        # recompiles per log line. The JSON-first structured source lands\n"
                "        # at completion via _update_quality_dashboard_from_report, W-b15;\n"
                "        # this log-string parse stays as the LIVE-progress fallback.)\n",
            ),
            (
                "            m = _re.search(r'Progress: (\\d+)/(\\d+) done.*?(\\d+) bullets', msg)",
                "            m = _PROGRESS_RE.search(msg)",
            ),
            (
                "                m = _re.search(r'Chapter (\\d+)/(\\d+)', msg)",
                "                m = _CHAPTER_RE.search(msg)",
            ),
        ],
        "_show_completion_modal": [
            (
                "            self.step9.progress.setValue(100)\n",
                "            self.step9.progress.setValue(100)\n"
                "            # V18.20.4.9 (W-b15): land the FINAL measured numbers from\n"
                "            # logs/quality_report.json (the same file the P0 W-a2 coverage\n"
                "            # fix reads) — JSON-first, with the _on_log log-string parse as\n"
                "            # the live in-run fallback. Success-gated so a failed run never\n"
                "            # paints a STALE report's numbers; displayed format identical.\n"
                "            self._update_quality_dashboard_from_report()\n",
            ),
        ],
    }

    def test_dataclass_decorator_moved_with_wizard_state(self):
        """ast.get_source_segment excludes decorators — pin the
        ``@dataclass`` line explicitly (WizardState is a dataclass!)."""
        shared = _src(_STEPS / "shared.py")
        assert "\n@dataclass\nclass WizardState:" in shared

    def test_step9_open_summaries_affordance_survived(self):
        """The user-visible completion button + its wiring: the label
        lives in step9_logs.py, the handler + click wiring in
        wizard_view.py (unchanged strings)."""
        step9 = _src(_STEPS / "step9_logs.py")
        assert 'QPushButton("Open summaries folder")' in step9
        wv = _src(_WIZARD)
        assert "def _open_summaries_folder" in wv
        assert "self.step9.open_summaries_btn.clicked.connect(" \
               "self._open_summaries_folder)" in wv


# ═══════════════════════════════════════════════════════════════════════════
# (d) The P4 contracts survive the split verbatim (W-b10 / W-b11 /
#     W-b2 / W-b4 — all live on WizardView / Step5Models, both moved
#     byte-identically; these pins keep proving it)
# ═══════════════════════════════════════════════════════════════════════════

def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    out: list[ast.Call] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == name) or (
                    isinstance(f, ast.Attribute) and f.attr == name):
                out.append(n)
    return out


def _call_keywords(call: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg}


class TestP4ContractsSurvive:
    def test_exactly_one_owner_tag_across_all_wizard_modules(self):
        """W-b10: the wizard tags itself ``owner="wizard"`` exactly once
        (the conversion-start bridge install) — now counted across
        wizard_view.py + every wizard_steps module."""
        tagged = []
        for path in (_WIZARD, *sorted(_STEPS.glob("*.py"))):
            for call in _calls_named(_tree(path), "set_callbacks"):
                if "owner" in _call_keywords(call):
                    tagged.append(call)
        assert len(tagged) == 1, (
            "exactly one owner-tagged set_callbacks call in the wizard "
            "modules (the conversion-start bridge)"
        )
        kw = _call_keywords(tagged[0])["owner"]
        assert isinstance(kw, ast.Constant) and kw.value == "wizard"

    def test_start_conversion_tags_wizard_and_wires_bridge(self):
        body = _method_src(_WIZARD, "_start_conversion", "WizardView")
        tagged = [c for c in _calls_named(ast.parse(body), "set_callbacks")
                  if "owner" in _call_keywords(c)]
        assert len(tagged) == 1
        kw = _call_keywords(tagged[0])["owner"]
        assert isinstance(kw, ast.Constant) and kw.value == "wizard"
        assert "on_complete=self.bridge.emit_complete" in body

    def test_close_event_queue_owner_guard(self):
        """W-b10: the restore is conditional — closeEvent reads
        controller.callback_owner and refuses to steal from "queue"."""
        body = _method_src(_WIZARD, "closeEvent", "WizardView")
        assert 'getattr(self.controller, "callback_owner", None)' in body
        assert 'owner == "queue"' in body
        assert "Queue owns the controller callbacks" in body
        assert "W-b10" in body

    def test_close_event_restore_only_in_else_branch(self):
        """W-b10: the convert_view._register_callbacks restore may only
        run in the guard's else branch (AST orelse-subtree proof)."""
        src = _src(_WIZARD)
        node = _class(ast.parse(src), "WizardView")
        close = None
        for n in ast.walk(node):
            if isinstance(n, ast.FunctionDef) and n.name == "closeEvent":
                close = n
                break
        assert close is not None
        restores = _calls_named(close, "_register_callbacks")
        assert len(restores) == 1, (
            "closeEvent must contain exactly one _register_callbacks call"
        )
        restore = restores[0]
        guard = None
        for n in ast.walk(close):
            if isinstance(n, ast.If):
                cond = ast.unparse(n.test).replace("'", '"')
                if 'owner == "queue"' in cond:
                    guard = n
                    break
        assert guard is not None, 'owner == "queue" guard If not found'
        in_else = any(
            restore is sub or restore in ast.walk(sub)
            for sub in guard.orelse
        )
        assert in_else, (
            "the _register_callbacks restore must live ONLY in the "
            "guard's else branch (W-b10)"
        )
        in_body = any(
            restore is sub or restore in ast.walk(sub)
            for sub in guard.body
        )
        assert not in_body

    def test_close_event_stops_monitor_and_timer_first(self):
        """W-b4: closeEvent stops the hw monitor + elapsed timer, and the
        stops happen BEFORE the bridge signal disconnects."""
        body = _method_src(_WIZARD, "closeEvent", "WizardView")
        assert "self._stop_hardware_monitor()" in body
        assert "self._stop_elapsed_timer()" in body
        assert body.find("self._stop_hardware_monitor()") < body.find(
            "sig.disconnect()")

    def test_hw_monitor_bridge_wiring(self):
        """W-b2: the monitor's callbacks never touch Qt widgets from the
        polling thread — the log goes through the bridge signal and
        auto-pause through the class-level queued signal."""
        start = _method_src(_WIZARD, "_start_hardware_monitor",
                            "WizardView")
        assert "self.bridge.emit_log" in start
        assert "self.auto_pause_requested.emit()" in start
        slot = _method_src(_WIZARD, "_on_auto_pause", "WizardView")
        assert "self._on_log" in slot
        assert "self.controller.cancel_conversion()" in slot
        assert "self.auto_pause_requested.connect(self._on_auto_pause)" in (
            _src(_WIZARD))
        assert "auto_pause_requested = Signal()" in _src(_WIZARD)

    def test_step5_models_async_refresh_shape(self):
        """W-b11: the 5s Ollama fetch runs on SimpleWorker with a kept
        ref, a re-entrancy guard, and the button disabled in-flight."""
        path = _STEPS / "step5_models.py"
        body = _method_src(path, "_refresh_models", "Step5Models")
        assert "SimpleWorker(self._get_models)" in body
        assert "self._models_worker = SimpleWorker" in body
        assert ".finished.connect(self._on_models_loaded)" in body
        assert ".failed.connect(self._on_models_failed)" in body
        assert ".start()" in body
        assert "is_running()" in body
        assert "self.refresh_btn.setEnabled(False)" in body
        assert "self._get_models()" not in body


# ═══════════════════════════════════════════════════════════════════════════
# W-b20 — the dead hallucination_audit_view branch is gone from app.py
# ═══════════════════════════════════════════════════════════════════════════

class TestWb20DeadBranchRemoved:
    def test_hallucination_audit_view_gone_from_ui_qt(self):
        """The attribute is never assigned anywhere (the audit opens
        from convert_view) — after W-b20 no reference may remain."""
        offenders = []
        for path in _UI_QT.rglob("*.py"):
            if "hallucination_audit_view" in path.read_text(
                    encoding="utf-8"):
                offenders.append(str(path.relative_to(_project_root)))
        assert not offenders, (
            f"hallucination_audit_view still referenced: {offenders}"
        )

    def test_toggle_theme_still_refreshes_the_live_views(self):
        """The deletion must not take the LIVE refreshes with it:
        convert_view always, the three lazily-created views guarded."""
        body = _method_src(_APP, "_toggle_theme", "ElixirWindow")
        assert "self.convert_view.refresh_theme()" in body
        for guarded in ("self.queue_view", "self.output_scanner_view",
                        "self.quarantine_view"):
            assert f'hasattr(self, "{guarded.split(".")[-1]}")' in body
            assert f"{guarded}.refresh_theme()" in body
