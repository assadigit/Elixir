"""V18.20.4.6 (P5, O-b2) — the base_dialog.py per-dialog split.

Per the approved V18.20.4.0 SWOT roadmap (P5 cluster):

- **O-b2:** ``ui_qt/views/service_dialogs/base_dialog.py`` was a
  ~6,680-line / 15-class / 11-dialog monolith (the largest file in the
  UI after O-b1 closed). It is decomposed per-dialog: every class and
  module-level helper moved VERBATIM (byte-identical bodies; only each
  new module's top-of-file imports differ) into the new
  ``ui_qt/views/service_dialogs/dialogs/`` package — one module per
  service dialog plus ``shared.py`` for the cross-dialog plumbing (the
  ``PlainTextTextEdit`` paste widget, the V11.25 success modal, the
  V18.20.4.5 (T-b2) close-event guard helpers, and the
  ``BaseServiceDialog`` base). ``base_dialog.py`` is now a PURE
  back-compat facade: zero class definitions, re-exporting every
  pre-split public name — the external importers (``ui_qt/app.py`` +
  ``ui_qt/views/convert_view.py``, the 11 dialog classes) are
  untouched.

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
_SERVICE_DIALOGS = _project_root / "ui_qt" / "views" / "service_dialogs"
_BASE_DIALOG = _SERVICE_DIALOGS / "base_dialog.py"
_DIALOGS = _SERVICE_DIALOGS / "dialogs"
_APP = _project_root / "ui_qt" / "app.py"
_CONVERT_VIEW = _project_root / "ui_qt" / "views" / "convert_view.py"
_UI_QT = _project_root / "ui_qt"

# The shipped pre-split reference (the O-b2 move happened after .4.5).
_REF_ZIP = _project_root.parent.parent / "download" / ("Elixir-V18.20.4.5.zip")
_REF_MEMBER = "Elixir-V18.20.4.5/ui_qt/views/service_dialogs/base_dialog.py"

# The 11 service dialogs, each in its own module (the O-b2 split map).
_DIALOG_TO_FILE = {
    "OcrServiceDialog": "ocr_service_dialog.py",
    "SummarizationServiceDialog": "summarization_service_dialog.py",
    "TranslationServiceDialog": "translation_service_dialog.py",
    "TtsServiceDialog": "tts_service_dialog.py",
    "QuickConvertDialog": "quick_convert_dialog.py",
    "PdfDocxCutterDialog": "pdf_docx_cutter_dialog.py",
    "MarkdownStylerDialog": "markdown_styler_dialog.py",
    "PacketsToolDialog": "packets_tool_dialog.py",
    "HallucinationAuditDialog": "hallucination_audit_dialog.py",
    "ImageExtractorDialog": "image_extractor_dialog.py",
    "TranscribeServiceDialog": "transcribe_service_dialog.py",
}
# The non-dialog pre-split classes and where they moved.
_OTHER_CLASS_TO_FILE = {
    "PlainTextTextEdit": "shared.py",
    "BaseServiceDialog": "shared.py",
    "_PacketWorker": "packets_tool_dialog.py",
    "_HallucinationAuditWorker": "hallucination_audit_dialog.py",
}
# The module-level helper functions and where they moved.
_FUNC_TO_FILE = {
    "_show_success_modal": "shared.py",
    "_worker_is_running": "shared.py",
    "_detach_worker_signals": "shared.py",
    "_confirm_close_with_running_worker": "shared.py",
    "_tts_cuda_available": "tts_service_dialog.py",
    "_tts_torch_cuda_tag": "tts_service_dialog.py",
    "_is_cpu_tts_error": "tts_service_dialog.py",
    "_show_cpu_tts_warning_modal": "tts_service_dialog.py",
    "_show_tts_gpu_error_modal": "tts_service_dialog.py",
}
_CLASS_TO_FILE = {**_DIALOG_TO_FILE, **_OTHER_CLASS_TO_FILE}
_GUARD_HELPERS = (
    "_worker_is_running",
    "_detach_worker_signals",
    "_confirm_close_with_running_worker",
)
_DIALOG_MODULES = sorted(set(_DIALOG_TO_FILE.values()))


# ── helpers (headless-safe: source text + AST only, by name) ────────────────


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.Module:
    return ast.parse(_src(path))


def _top_level_defs(tree: ast.Module) -> dict[str, ast.AST]:
    """Top-level classes + functions, by name."""
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
    return out


def _facade_reexports() -> set[str]:
    """Names the facade imports from the dialogs/ package."""
    tree = _tree(_BASE_DIALOG)
    names: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module.startswith("ui_qt.views.service_dialogs.dialogs."))
        ):
            names.update(a.name for a in node.names)
    return names


def _facade_all() -> list[str]:
    tree = _tree(_BASE_DIALOG)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and (isinstance(node.targets[0], ast.Name) and node.targets[0].id == "__all__")
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# (a) base_dialog.py is a pure facade
# ═══════════════════════════════════════════════════════════════════════════


class TestPureFacade:
    def test_zero_class_definitions(self):
        tree = _tree(_BASE_DIALOG)
        assert [n for n in tree.body if isinstance(n, ast.ClassDef)] == []

    def test_zero_module_function_definitions(self):
        # A pure re-export facade: nothing is DEFINED here, only imported.
        tree = _tree(_BASE_DIALOG)
        assert [
            n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ] == []

    def test_facade_imports_only_from_the_dialogs_package(self):
        tree = _tree(_BASE_DIALOG)
        allowed = {"__future__"}
        allowed.add("ui_qt.views.service_dialogs.dialogs.shared")
        allowed.update(f"ui_qt.views.service_dialogs.dialogs.{m[:-3]}" for m in _DIALOG_MODULES)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed, node.module

    def test_all_is_explicit_and_matches_the_reexports(self):
        reexports = _facade_reexports()
        assert reexports, "facade re-exports nothing"
        assert _facade_all(), "__all__ missing"
        assert set(_facade_all()) == reexports
        assert len(_facade_all()) == len(set(_facade_all()))  # no dups


# ═══════════════════════════════════════════════════════════════════════════
# (b) the facade covers every externally-imported name
# ═══════════════════════════════════════════════════════════════════════════


class TestExternalImportersCovered:
    def _external_importers(self):
        """Every (file, name) imported from ...service_dialogs.base_dialog
        anywhere in the tree (runtime code + tests)."""
        found: set[tuple[str, str]] = set()
        for py in sorted(_project_root.rglob("*.py")):
            rel = py.relative_to(_project_root).as_posix()
            if rel.startswith(("ui_qt/views/service_dialogs/dialogs/", ".git", ".venv")):
                continue
            try:
                tree = ast.parse(_src(py))
            except SyntaxError:  # pragma: no cover — malformed non-code
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == (
                    "ui_qt.views.service_dialogs.base_dialog"
                ):
                    for a in node.names:
                        found.add((rel, a.name))
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        assert a.name != "ui_qt.views.service_dialogs.base_dialog", (
                            "plain-module import of the facade"
                        )
        return found

    @pytest.mark.slow  # Phase 2.5: 2.2 s AST sweep over the ui_qt tree
    def test_every_external_name_is_reexported(self):
        reexports = _facade_reexports()
        for _file, name in self._external_importers():
            assert name in reexports, f"{_file} imports {name!r}"

    @pytest.mark.slow  # Phase 2.5: 2.1 s AST sweep over the ui_qt tree
    def test_external_importers_are_exactly_the_11_dialogs(self):
        # The step-1 inventory: app.py (HallucinationAuditDialog) +
        # convert_view.py (all 11 dialogs, lazy per-service imports).
        names = {name for _f, name in self._external_importers()}
        assert names == set(_DIALOG_TO_FILE), sorted(names)

    def test_importer_sites_unchanged(self):
        # app.py still lazily imports the audit dialog from the facade.
        app_imports = [
            node
            for node in ast.walk(_tree(_APP))
            if isinstance(node, ast.ImportFrom)
            and node.module == "ui_qt.views.service_dialogs.base_dialog"
        ]
        assert [a.name for n in app_imports for a in n.names] == ["HallucinationAuditDialog"]
        # convert_view.py still opens every service dialog through the
        # facade — all 11, one lazy import each.
        cv_imports = [
            a.name
            for node in ast.walk(_tree(_CONVERT_VIEW))
            if isinstance(node, ast.ImportFrom)
            and node.module == "ui_qt.views.service_dialogs.base_dialog"
            for a in node.names
        ]
        assert sorted(cv_imports) == sorted(_DIALOG_TO_FILE)

    def test_only_the_facade_imports_the_dialogs_package(self):
        # No one bypasses the facade (the split added no new importers).
        for py in sorted(_UI_QT.rglob("*.py")):
            rel = py.relative_to(_project_root).as_posix()
            if rel == "ui_qt/views/service_dialogs/base_dialog.py":
                continue
            if rel.startswith("ui_qt/views/service_dialogs/dialogs/"):
                continue  # intra-package imports are fine (shared only)
            tree = ast.parse(_src(py))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and (node.module.startswith("ui_qt.views.service_dialogs.dialogs"))
                ):
                    raise AssertionError(f"{rel} bypasses the facade: {node.module}")


# ═══════════════════════════════════════════════════════════════════════════
# (c) each dialog class lives in its own module under dialogs/
# ═══════════════════════════════════════════════════════════════════════════


class TestPerDialogModules:
    def test_package_file_set(self):
        assert (_DIALOGS / "__init__.py").is_file()
        assert sorted(p.name for p in _DIALOGS.glob("*.py")) == sorted(
            ["__init__.py", "shared.py"] + _DIALOG_MODULES
        )

    def test_each_dialog_class_defined_in_its_own_module(self):
        for cls, fname in _DIALOG_TO_FILE.items():
            defs = _top_level_defs(_tree(_DIALOGS / fname))
            assert cls in defs, f"{cls} not in dialogs/{fname}"

    def test_no_dialog_class_leaks_into_another_module(self):
        # Each class is defined exactly once across the whole package.
        seen: dict[str, str] = {}
        for py in sorted(_DIALOGS.glob("*.py")):
            for name in _top_level_defs(_tree(py)):
                if name in ("logger",):
                    continue
                assert name not in seen, f"{name} defined in both {seen[name]} and {py.name}"
                seen[name] = py.name
        assert set(seen) == set(_CLASS_TO_FILE) | set(_FUNC_TO_FILE), sorted(
            set(seen) ^ (set(_CLASS_TO_FILE) | set(_FUNC_TO_FILE))
        )

    def test_worker_classes_stay_with_their_dialogs(self):
        for cls, fname in _OTHER_CLASS_TO_FILE.items():
            defs = _top_level_defs(_tree(_DIALOGS / fname))
            assert cls in defs, f"{cls} not in dialogs/{fname}"

    def test_shared_holds_the_shared_classes_and_modal(self):
        defs = _top_level_defs(_tree(_DIALOGS / "shared.py"))
        assert set(defs) == {
            "PlainTextTextEdit",
            "BaseServiceDialog",
            "_show_success_modal",
            *_GUARD_HELPERS,
        }

    def test_translation_and_tts_subclass_the_shared_base(self):
        for fname in ("translation_service_dialog.py", "tts_service_dialog.py"):
            tree = _tree(_DIALOGS / fname)
            cls = [
                n
                for n in tree.body
                if isinstance(n, ast.ClassDef)
                and n.name in ("TranslationServiceDialog", "TtsServiceDialog")
            ][0]
            assert any(
                isinstance(b, ast.Name) and b.id == ("BaseServiceDialog") for b in cls.bases
            ), fname

    def test_dialogs_import_shared_not_base_dialog(self):
        # Acyclic: the package never imports the facade back.
        for py in sorted(_DIALOGS.glob("*.py")):
            for node in ast.walk(_tree(py)):
                if isinstance(node, ast.ImportFrom):
                    assert node.module != ("ui_qt.views.service_dialogs.base_dialog"), py.name
                    if node.module and node.module.startswith(
                        "ui_qt.views.service_dialogs.dialogs."
                    ):
                        assert node.module == ("ui_qt.views.service_dialogs.dialogs.shared"), (
                            f"{py.name} imports sibling {node.module}"
                        )

    def test_every_module_parses_and_defines_something(self):
        for py in sorted(_DIALOGS.glob("*.py")):
            if py.name == "__init__.py":
                continue
            assert _top_level_defs(_tree(py)), py.name

    def test_dialog_family_close_event_guards_survived(self):
        # The 11 T-b2 closeEvent guards span the family (p4a pins the
        # shapes; this pins the family union stayed intact). V0.6.5: the
        # MarkdownStyler joined the family (its LLM path owns a worker).
        union = _src(_BASE_DIALOG) + "\n".join(
            _src(_DIALOGS / p) for p in sorted(q.name for q in _DIALOGS.glob("*.py"))
        )
        assert union.count("def closeEvent") == 11


# ═══════════════════════════════════════════════════════════════════════════
# (d) the P4 guard helpers live in shared.py + are re-exported
# ═══════════════════════════════════════════════════════════════════════════


class TestSharedGuardHelpers:
    def test_guard_helpers_live_in_shared(self):
        defs = _top_level_defs(_tree(_DIALOGS / "shared.py"))
        for helper in _GUARD_HELPERS:
            assert helper in defs, helper
            assert isinstance(defs[helper], ast.FunctionDef), helper

    def test_guard_helpers_are_reexported_by_the_facade(self):
        reexports = _facade_reexports()
        for helper in _GUARD_HELPERS:
            assert helper in reexports, helper
        assert set(_GUARD_HELPERS) <= set(_facade_all())

    def test_confirm_guard_calls_the_other_two(self):
        # The shared trio's internal wiring moved together.
        node = _top_level_defs(_tree(_DIALOGS / "shared.py"))["_confirm_close_with_running_worker"]
        seg = ast.get_source_segment(_src(_DIALOGS / "shared.py"), node)
        assert "_worker_is_running(" in seg
        assert "_detach_worker_signals(" in seg


# ═══════════════════════════════════════════════════════════════════════════
# (e) verbatim move vs the pre-split V18.20.4.5 base_dialog.py
# ═══════════════════════════════════════════════════════════════════════════


def _pre_split_source() -> str:
    if not _REF_ZIP.is_file():
        pytest.skip(f"pre-split reference zip absent: {_REF_ZIP}")
    with zipfile.ZipFile(_REF_ZIP) as zf:
        return zf.read(_REF_MEMBER).decode("utf-8")


class TestVerbatimMove:
    # V18.20.4.9 (BK1 / W-b17) — the ONLY sanctioned MarkdownStylerDialog
    # drift since the O-b2 split: its two str(e)-only except blocks gained
    # the traceback-at-WARNING log line before the user-visible message
    # (the SWOT W-b17 crash-visibility class). Both substitutions are
    # guarded (the OLD text is asserted present in the reference first,
    # so any additional drift still fails), per the P6 test_v182047
    # evolution pattern.
    _STYLER_SUBS = {
        "_on_process": [
            (
                "        except Exception as e:\n"
                '            self.status_label.setText(f"❌ Error: {e}")\n',
                "        except Exception as e:\n"
                "            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the\n"
                "            # status + user box (was str(e)-only — zero diagnostics).\n"
                '            logger.warning("markdown styling failed", exc_info=True)\n'
                '            self.status_label.setText(f"❌ Error: {e}")\n',
            )
        ],
        "_on_save": [
            (
                "            except Exception as e:\n"
                '                QMessageBox.critical(self, "Save failed", str(e))',
                "            except Exception as e:\n"
                "                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE\n"
                "                # the user box (was str(e)-only — zero diagnostics).\n"
                '                logger.warning("styled markdown save failed", exc_info=True)\n'
                '                QMessageBox.critical(self, "Save failed", str(e))',
            )
        ],
    }

    def test_every_class_body_byte_identical(self):
        pre = _pre_split_source()
        pre_tree = ast.parse(pre)
        pre_defs = {n.name: n for n in pre_tree.body if isinstance(n, ast.ClassDef)}
        assert set(pre_defs) == set(_CLASS_TO_FILE)
        for cls, fname in _CLASS_TO_FILE.items():
            new_src = _src(_DIALOGS / fname)
            new_node = _top_level_defs(_tree(_DIALOGS / fname))[cls]
            expected = ast.get_source_segment(pre, pre_defs[cls]) or ""
            actual = ast.get_source_segment(new_src, new_node) or ""
            if cls == "MarkdownStylerDialog":
                # W-b17 evolution: reconstruct the expected body from the
                # reference with the two guarded substitutions.
                cls_tree = ast.parse(expected)
                styler = cls_tree.body[0]
                assert isinstance(styler, ast.ClassDef)
                old_methods = {
                    n.name: ast.get_source_segment(expected, n) or ""
                    for n in styler.body
                    if isinstance(n, ast.FunctionDef)
                }
                new_tree = ast.parse(actual)
                new_styler = new_tree.body[0]
                new_methods = {
                    n.name: ast.get_source_segment(actual, n) or ""
                    for n in new_styler.body
                    if isinstance(n, ast.FunctionDef)
                }
                assert set(new_methods) == set(old_methods), (
                    "no MarkdownStylerDialog method may be added/deleted beyond the W-b17 evolution"
                )
                for name, new_body in new_methods.items():
                    exp = old_methods[name]
                    for old_frag, new_frag in self._STYLER_SUBS.get(name, []):
                        assert old_frag in exp, (
                            f"guarded anchor missing in the reference "
                            f"({name}) — drift beyond the documented "
                            "W-b17 evolution"
                        )
                        exp = exp.replace(old_frag, new_frag, 1)
                    assert new_body == exp, (
                        f"MarkdownStylerDialog.{name} drifted beyond the "
                        "documented W-b17 evolution (byte-identity is still "
                        "enforced for every other method)"
                    )
                continue
            assert expected == actual, f"{cls} body changed"

    def test_every_module_function_body_byte_identical(self):
        pre = _pre_split_source()
        pre_tree = ast.parse(pre)
        pre_defs = {
            n.name: n
            for n in pre_tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert set(pre_defs) == set(_FUNC_TO_FILE)
        for func, fname in _FUNC_TO_FILE.items():
            new_src = _src(_DIALOGS / fname)
            new_node = _top_level_defs(_tree(_DIALOGS / fname))[func]
            assert ast.get_source_segment(pre, pre_defs[func]) == ast.get_source_segment(
                new_src, new_node
            ), f"{func} body changed"

    def test_tts_cuda_caches_still_module_level(self):
        # The session caches moved with the TTS helpers (mutated via
        # ``global`` inside the tts module — same semantics as before).
        pre = _pre_split_source()
        pre_tree = ast.parse(pre)
        pre_caches = {
            t.id
            for n in pre_tree.body
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            for t in [n.target]
        }
        new_tree = _tree(_DIALOGS / "tts_service_dialog.py")
        new_caches = {n.target.id for n in new_tree.body if isinstance(n, ast.AnnAssign)}
        assert pre_caches <= new_caches, sorted(pre_caches - new_caches)

    def test_wb5_spawns_survived_verbatim(self):
        # Spot-check: the four W-b5 SimpleWorker spawn sites still spawn
        # from their _do_* methods (see p4a for the full contracts).
        for cls, do in (
            ("OcrServiceDialog", "_do_convert"),
            ("SummarizationServiceDialog", "_do_summarize"),
            ("QuickConvertDialog", "_do_convert"),
            ("PdfDocxCutterDialog", "_do_cut"),
        ):
            src = _src(_DIALOGS / _DIALOG_TO_FILE[cls])
            assert "self._worker = SimpleWorker(" in src, cls
            assert f"def {do}(" in src, f"{cls}.{do}"


# ═══════════════════════════════════════════════════════════════════════════
# (f) the latent _QTI NameError fix (V18.20.4.6 rider)
# ═══════════════════════════════════════════════════════════════════════════

_HALLUCINATION = _DIALOGS / "hallucination_audit_dialog.py"


class TestQtiLatentBugFix:
    """HallucinationAuditDialog._on_done calls ``_QTI(...)`` at 5 sites
    (the results-table fill) but ``_QTI`` was defined NOWHERE in the tree
    since V13.20.x — a botched rename that made every completed audit
    crash with NameError before the table filled. V18.20.4.6 pins the
    alias fix: ``_QTI = QTableWidgetItem``."""

    def test_qti_is_assigned_qtablewidgetitem(self):
        tree = _tree(_HALLUCINATION)
        assigns = [
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "_QTI"
        ]
        assert assigns, "_QTI alias removed — _on_done would NameError"
        (assign,) = assigns
        assert isinstance(assign.value, ast.Name), assign.value
        assert assign.value.id == "QTableWidgetItem", assign.value.id

    def test_qtablewidgetitem_is_imported_in_that_module(self):
        # The alias must resolve: QTableWidgetItem is imported from
        # PySide6.QtWidgets in this module (its existing import style).
        for node in _tree(_HALLUCINATION).body:
            if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets":
                names = {a.name for a in node.names}
                if "QTableWidgetItem" in names:
                    return
        raise AssertionError(
            "QTableWidgetItem not imported from PySide6.QtWidgets in "
            "hallucination_audit_dialog.py — the _QTI alias would NameError"
        )

    def test_the_five_call_sites_survived(self):
        # The fill sites moved verbatim; they now resolve via the alias.
        src = _src(_HALLUCINATION)
        assert src.count("_QTI(") == 5, src.count("_QTI(")
