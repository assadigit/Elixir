"""V18.20.4.6+ (P5-2b, services decomposition) — packets split, translate_file
decompose, NLLB retirement.

Per the approved V18.20.4.0 SWOT roadmap (P5 phase 2):

- **O-c4:** ``core/outputs/packets.py`` (1,708 lines, 3 classes) was split
  into the ``core/outputs/packets/`` package — ``models.py`` (the shared
  data model: ``LogFn`` + ``Packet`` + ``PacketCollection``),
  ``generator.py`` (``PacketGenerator`` + its own logger) and a pure
  ``__init__.py`` facade re-exporting every pre-split public name, so all
  ``from core.outputs.packets import PacketGenerator`` sites resolve
  unchanged. Bodies moved VERBATIM (byte-identical; only each new
  module's docstring + import block differ).
- **O-c7:** ``TranslationService.translate_file`` (365 lines) was
  decomposed into three cohesive private methods on the same class in the
  same module — ``_extract_glossary_context``, ``_translate_chunks_parallel``
  and ``_write_translation_outputs`` — with the public entry signature
  untouched and the extracted bodies byte-identical (whole logical
  blocks; only the def/params/return glue is new).
- **O-c10:** the deprecated NLLB translator vestige
  (``core/translation/nllb_translator.py``, deprecated since V13.31.0
  #13) was deleted: its only two import sites were provably dead (the
  ``backend == "nllb"`` branch in ``from_settings`` — unreachable because
  ``utils.settings.Settings._load()`` (V13.31.0) and bootstrap (V18.2.26
  A14) migrate legacy ``translation.backend='nllb'`` to 'ollama' before
  any read, and no UI offers 'nllb'; plus the zero-user lazy
  ``__getattr__`` shim in ``core/translation/__init__.py``). The dead
  ``translation.nllb_model`` settings default was removed with a
  load-time deletion migration (bootstrap b3_voting_enabled A14 pattern).

All pins are headless-safe source/AST parsing (+ one pure-Python import
check — no PySide6, no network); the verbatim spot-checks read the
PRE-CHANGE files out of the shipped V18.20.4.6 zip and are skipped when
that reference zip is absent. No line-number peeking — everything is
located by name/anchor via ``ast``.
"""

from __future__ import annotations

import ast
import importlib.util
import zipfile
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
_PACKETS_DIR = _project_root / "core" / "outputs" / "packets"
_PACKETS_FACADE = _PACKETS_DIR / "__init__.py"
_PACKETS_MODELS = _PACKETS_DIR / "models.py"
_PACKETS_GENERATOR = _PACKETS_DIR / "generator.py"
_OLD_PACKETS = _project_root / "core" / "outputs" / "packets.py"
_OUTPUTS_INIT = _project_root / "core" / "outputs" / "__init__.py"
_PACKETS_TOOL_DIALOG = (
    _project_root / "ui_qt" / "views" / "service_dialogs" / "dialogs" / "packets_tool_dialog.py"
)
_PACKETS_INTEGRATION_TEST = _project_root / "tests" / "test_packets_integration.py"

_SERVICE = _project_root / "core" / "translation" / "service.py"
_TRANSLATION_INIT = _project_root / "core" / "translation" / "__init__.py"
_NLLB_MODULE = _project_root / "core" / "translation" / "nllb_translator.py"
_SETTINGS = _project_root / "utils" / "settings.py"

# The shipped pre-change reference (the P5-2b moves happened after .4.6).
_REF_ZIP = _project_root.parent.parent / "download" / ("Elixir-V18.20.4.6.zip")
_REF_ROOT = "Elixir-V18.20.4.6/"


# ── helpers (headless-safe: source text + AST only, by name) ──────────────


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.Module:
    return ast.parse(_src(path))


def _top_level_defs(tree: ast.Module) -> dict[str, ast.AST]:
    """Top-level classes + functions + simple assignments, by name."""
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node
    return out


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    node = _top_level_defs(tree).get(name)
    assert isinstance(node, ast.ClassDef), f"no top-level class {name!r}"
    return node


def _methods(cls: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}


def _ref_member(name: str) -> str | None:
    """Read a source file out of the shipped .4.6 reference zip."""
    if not _REF_ZIP.exists():
        return None
    with zipfile.ZipFile(_REF_ZIP) as zf:
        return zf.read(_REF_ROOT + name).decode("utf-8")


def _skip_without_ref(ref: str | None) -> str:
    if ref is None:
        pytest.skip(f"reference zip absent: {_REF_ZIP}")
    return ref


def _func_source(src: str, cls_name: str, func_name: str) -> str:
    tree = ast.parse(src)
    cls = _class(tree, cls_name)
    fn = _methods(cls)[func_name]
    seg = ast.get_source_segment(src, fn)
    assert seg is not None
    return seg


def _signature(fn: ast.FunctionDef) -> tuple:
    args = fn.args
    return (
        [a.arg for a in args.args],
        [a.arg for a in args.kwonlyargs],
        [ast.unparse(d) for d in args.defaults],
        ast.unparse(fn.returns) if fn.returns else None,
    )


# ══════════════════════════════════════════════════════════════════════════
# O-c4 — packets.py split into the core/outputs/packets/ package
# ══════════════════════════════════════════════════════════════════════════


class TestOc4PacketsSplit:
    def test_old_module_gone_package_present(self):
        assert not _OLD_PACKETS.exists(), (
            "the pre-split core/outputs/packets.py must be gone (the package "
            "core/outputs/packets/ replaces it — both cannot coexist)"
        )
        assert _PACKETS_DIR.is_dir()
        assert sorted(p.name for p in _PACKETS_DIR.glob("*.py")) == [
            "__init__.py",
            "generator.py",
            "models.py",
        ]

    def test_per_class_modules(self):
        # models.py = the shared data model (LogFn + the two dataclasses)
        models_defs = _top_level_defs(_tree(_PACKETS_MODELS))
        assert set(models_defs) == {"LogFn", "Packet", "PacketCollection"}
        for cls_name in ("Packet", "PacketCollection"):
            deco = [ast.unparse(d) for d in models_defs[cls_name].decorator_list]
            assert deco == ["dataclass"], (cls_name, deco)
        # generator.py = the engine, plus its own module logger
        gen_defs = _top_level_defs(_tree(_PACKETS_GENERATOR))
        assert set(gen_defs) == {"PacketGenerator", "logger"}
        # the class inventory matches the pre-split 3 classes exactly
        ref = _skip_without_ref(_ref_member("core/outputs/packets.py"))
        ref_defs = _top_level_defs(ast.parse(ref))
        assert set(ref_defs) == {"LogFn", "Packet", "PacketCollection", "PacketGenerator", "logger"}

    def test_facade_is_pure_and_reexports(self):
        tree = _tree(_PACKETS_FACADE)
        assert not [
            n
            for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ], "the packets facade must define nothing — pure re-export"
        reexported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module == "__future__" or node.module.startswith(
                    "core.outputs.packets."
                ), node.module
                if node.module.startswith("core.outputs.packets."):
                    reexported.update(a.name for a in node.names)
        assert reexported == {"Packet", "PacketCollection", "PacketGenerator", "LogFn"}
        all_node = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "__all__"
        )
        assert sorted(ast.literal_eval(all_node.value)) == [
            "LogFn",
            "Packet",
            "PacketCollection",
            "PacketGenerator",
        ]

    def test_acyclic_module_graph(self):
        # models.py: no imports from the generator or the facade
        for node in _tree(_PACKETS_MODELS).body:
            if isinstance(node, ast.ImportFrom):
                assert "packets.generator" not in (node.module or "")
                assert "core.outputs.packets import" not in ast.unparse(node)
        # generator.py: imports models, never the facade/parent package
        gen_imports = [
            ast.unparse(n) for n in _tree(_PACKETS_GENERATOR).body if isinstance(n, ast.ImportFrom)
        ]
        assert any("from core.outputs.packets.models import" in s for s in gen_imports)
        assert not any(
            s.startswith("from core.outputs.packets import") or "core.outputs import" in s
            for s in gen_imports
        )

    def test_real_importer_sites_unchanged(self):
        # The grep-verified external importers (pre-split) still import
        # PacketGenerator from core.outputs.packets — facade contract.
        assert "from core.outputs.packets import PacketGenerator" in _src(_OUTPUTS_INIT)
        assert "from core.outputs.packets import PacketGenerator" in _src(_PACKETS_TOOL_DIALOG)
        ti = _src(_PACKETS_INTEGRATION_TEST)
        assert ti.count("from core.outputs.packets import PacketGenerator") == 3

    def test_facade_runtime_import(self):
        # headless + hermetic: pure-Python package import (no Qt, no network)
        import core.outputs.packets as pk

        assert pk.__all__ == ["Packet", "PacketCollection", "PacketGenerator", "LogFn"]
        assert pk.PacketGenerator.__module__ == "core.outputs.packets.generator"
        assert pk.Packet.__module__ == "core.outputs.packets.models"
        assert pk.PacketCollection.__module__ == "core.outputs.packets.models"
        import core.outputs

        assert core.outputs.PacketGenerator is pk.PacketGenerator

    def test_class_bodies_verbatim_vs_zip(self):
        ref = _skip_without_ref(_ref_member("core/outputs/packets.py"))
        ref_tree = ast.parse(ref)
        # all three classes + LogFn byte-identical vs the pre-split file
        for name, path in (
            ("Packet", _PACKETS_MODELS),
            ("PacketCollection", _PACKETS_MODELS),
            ("PacketGenerator", _PACKETS_GENERATOR),
        ):
            ref_seg = ast.get_source_segment(ref, _top_level_defs(ref_tree)[name])
            new_seg = ast.get_source_segment(_src(path), _top_level_defs(_tree(path))[name])
            assert ref_seg is not None and new_seg is not None
            assert new_seg == ref_seg, f"{name} body not byte-identical"
        ref_logfn = ast.get_source_segment(ref, _top_level_defs(ref_tree)["LogFn"])
        new_logfn = ast.get_source_segment(
            _src(_PACKETS_MODELS), _top_level_defs(_tree(_PACKETS_MODELS))["LogFn"]
        )
        assert new_logfn == ref_logfn == "LogFn = Callable[[str, str], None]"

    def test_method_spot_checks_verbatim_vs_zip(self):
        # spot-check representative methods (incl. the O-c5/T-c7 open-item
        # bodies: _call_llm raw-request site + generic WARNING) — moved
        # verbatim, so those open items stay OPEN unchanged.
        ref = _skip_without_ref(_ref_member("core/outputs/packets.py"))
        ref_methods = _methods(_class(ast.parse(ref), "PacketGenerator"))
        new_methods = _methods(_class(_tree(_PACKETS_GENERATOR), "PacketGenerator"))
        for name in (
            "generate",
            "_deduplicate_bullets",
            "_cluster_bullets",
            "_call_llm",
            "_validate_packet",
            "_write_full_document",
            "_write_knowledge_map",
            "_write_coverage_report",
        ):
            ref_seg = ast.get_source_segment(ref, ref_methods[name])
            new_seg = ast.get_source_segment(_src(_PACKETS_GENERATOR), new_methods[name])
            assert new_seg == ref_seg, f"PacketGenerator.{name} differs"
        assert set(new_methods) == set(ref_methods), "method inventory drift"

    def test_logger_continuity(self):
        # the pre-split module had one module-level logger used by 4
        # logger.debug sites inside PacketGenerator; the class carries its
        # own logger now (V18.20.3.12 F821 pattern) and utils/logging.py
        # prefix-matches "core.outputs.packets" either way.
        gen_src = _src(_PACKETS_GENERATOR)
        assert "logger = logging.getLogger(__name__)" in gen_src
        assert gen_src.count("logger.debug(") == 4


# ══════════════════════════════════════════════════════════════════════════
# O-c7 — TranslationService.translate_file decomposition
# ══════════════════════════════════════════════════════════════════════════

_EXTRACTED_HELPERS = {
    "_extract_glossary_context",
    "_translate_chunks_parallel",
    "_write_translation_outputs",
}


def _ref_translate_file() -> str:
    ref = _skip_without_ref(_ref_member("core/translation/service.py"))
    return _func_source(ref, "TranslationService", "translate_file")


class TestOc7TranslateFileDecompose:
    def test_translate_file_signature_unchanged(self):
        ref = _skip_without_ref(_ref_member("core/translation/service.py"))
        ref_sig = _signature(
            _methods(_class(ast.parse(ref), "TranslationService"))["translate_file"]
        )
        new_sig = _signature(
            _methods(_class(_tree(_SERVICE), "TranslationService"))["translate_file"]
        )
        assert new_sig == ref_sig

    def test_extracted_helpers_exist_on_the_class(self):
        methods = _methods(_class(_tree(_SERVICE), "TranslationService"))
        assert set(methods) >= _EXTRACTED_HELPERS
        # same-module decomposition: helpers are methods, not free functions
        tree = _tree(_SERVICE)
        assert not [
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in _EXTRACTED_HELPERS
        ]

    def test_translate_file_shrunk_not_gutted(self):
        new_src = _src(_SERVICE)
        tf = _func_source(new_src, "TranslationService", "translate_file")
        n_lines = tf.count("\n") + 1
        assert 90 <= n_lines <= 160, n_lines
        # kept phases: guards + chunking + chunk-state setup + reassemble +
        # final progress + the return contract
        for anchor in (
            "source_path = Path(source_path)",
            "chunks = self.chunker.chunk(text)",
            "translated_chunks: list[str] = []",
            # V0.13: "validation_pairs: list[tuple] = []" anchor removed —
            # that dead assignment was an F841 unused variable, deleted in the
            # Phase 0 lint triage. Replacement anchor below proves the
            # validation plumbing itself is intact.
            "report = ValidationReport(",
            "translatable_indices = []",
            'translated_text = "\\n".join(translated_chunks)',
            "return translated_path, report if self.validation_enabled else None",
        ):
            assert anchor in tf, anchor
        # the extracted bodies are no longer inline in translate_file
        for anchor in (
            "glossary_mgr = GlossaryManager(",
            "ThreadPoolExecutor(max_workers=max_workers)",
            'translated_path.write_text(translated_text, encoding="utf-8")',
            "harakat_path = output_dir /",
        ):
            assert anchor not in tf, anchor

    def test_extracted_bodies_byte_identical_vs_zip(self):
        ref_tf = _ref_translate_file()
        ref_lines = ref_tf.splitlines(keepends=True)

        def block(start_pred: str, end_pred: str) -> str:
            """Slice the pre-split translate_file between two line prefixes
            (anchor-located — no line-number pins); both ends INCLUSIVE."""
            start = next(i for i, ln in enumerate(ref_lines) if ln.startswith(start_pred))
            end = next(i for i, ln in enumerate(ref_lines) if i > start and ln.startswith(end_pred))
            return "".join(ref_lines[start : end + 1])

        block_glossary = block(
            "        # ── Glossary extraction",
            "        glossary_context = glossary_mgr.get_context_for_prompt()"
            ' if glossary_mgr else ""',
        )
        # the parallel block runs from the guard to the LAST
        # avg_judge_score recompute (after the retry pass)
        start = next(
            i for i, ln in enumerate(ref_lines) if ln.strip() == "if translatable_indices:"
        )
        end = max(
            i
            for i, ln in enumerate(ref_lines)
            if ln.strip().startswith("report.avg_judge_score = sum(cv.judge_score")
        )
        block_parallel = "".join(ref_lines[start : end + 1])
        block_outputs = block(
            "        # ── Determine output path",
            "            glossary_mgr.glossary.save(glossary_path)",
        )

        new_src = _src(_SERVICE)
        methods = _methods(_class(_tree(_SERVICE), "TranslationService"))

        def helper_body(name: str) -> str:
            fn = methods[name]
            seg = ast.get_source_segment(new_src, fn)
            assert seg is not None
            doc_end = fn.body[0].end_lineno  # body[0] = the extraction docstring
            body_lines = new_src.splitlines(keepends=True)[doc_end : fn.end_lineno]
            return "".join(body_lines)

        assert helper_body("_extract_glossary_context") == (
            block_glossary + "        return glossary_mgr, glossary_context\n"
        )
        assert helper_body("_translate_chunks_parallel") == block_parallel
        assert helper_body("_write_translation_outputs") == (
            block_outputs + "        return translated_path\n"
        )

    def test_sibling_methods_untouched_vs_zip(self):
        ref = _skip_without_ref(_ref_member("core/translation/service.py"))
        for name in (
            "translate_book_outputs",
            "_generate_bilingual_html",
            "translate_text",
            "translate_standalone_text",
            "__init__",
        ):
            assert _func_source(_src(_SERVICE), "TranslationService", name) == _func_source(
                ref, "TranslationService", name
            ), name

    def test_translate_file_call_contract(self):
        tf = _func_source(_src(_SERVICE), "TranslationService", "translate_file")
        # the three call sites wire the pre-split locals through explicitly
        assert "glossary_mgr, glossary_context = self._extract_glossary_context(" in tf
        assert "self._translate_chunks_parallel(" in tf
        assert "translated_path = self._write_translation_outputs(" in tf
        # translate_book_outputs still calls translate_file (public entry)
        assert "self.translate_file(" in _func_source(
            _src(_SERVICE), "TranslationService", "translate_book_outputs"
        )


# ══════════════════════════════════════════════════════════════════════════
# O-c10 — NLLB translator vestige retired
# ══════════════════════════════════════════════════════════════════════════


class TestOc10NllbRetired:
    def test_module_absent(self):
        assert not _NLLB_MODULE.exists()

    def test_no_imports_of_the_module_anywhere(self):
        """Whole-tree AST scan: no import statement references
        core.translation.nllb_translator (comments citing the retirement
        are fine — this checks live imports only)."""
        offenders: list[str] = []
        for py in sorted(_project_root.rglob("*.py")):
            rel = py.relative_to(_project_root)
            if str(rel).startswith(("tests/", ".venv")):
                continue  # this very test file cites the name in docstrings
            try:
                tree = ast.parse(_src(py))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (
                    node.module == "core.translation.nllb_translator"
                ):
                    offenders.append(f"{rel}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "core.translation.nllb_translator" or alias.name.endswith(
                            "nllb_translator"
                        ):
                            offenders.append(f"{rel}:{node.lineno}")
        assert not offenders, offenders

    def test_translation_init_shim_gone(self):
        src = _src(_TRANSLATION_INIT)
        tree = ast.parse(src)
        assert not [
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "__getattr__"
        ]
        all_node = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "__all__"
        )
        names = ast.literal_eval(all_node.value)
        assert "NLLBTranslator" not in names
        assert "TranslationService" in names and "Translator" in names

    def test_service_nllb_branch_gone(self):
        src = _src(_SERVICE)
        tree = ast.parse(src)
        top = _top_level_defs(tree)
        assert "_get_nllb_translator" not in top
        # from_settings: no backend=="nllb" branch and no NLLB names —
        # AST-based so the O-c10 retirement citation comments (which name
        # the removed branch) don't false-positive.
        fs = _methods(_class(tree, "TranslationService"))["from_settings"]
        used_names = {n.id for n in ast.walk(fs) if isinstance(n, ast.Name)}
        assert not used_names & {"NLLBTranslator", "_get_nllb_translator", "nllb_model", "backend"}
        nllb_consts = [
            n.value for n in ast.walk(fs) if isinstance(n, ast.Constant) and n.value == "nllb"
        ]
        assert not nllb_consts, nllb_consts
        seg = ast.get_source_segment(src, fs)
        assert seg is not None
        assert "translator = Translator(" in seg

    def test_settings_nllb_model_default_removed_with_migration(self):
        src = _src(_SETTINGS)
        tree = ast.parse(src)
        settings_cls = _class(tree, "Settings")
        defaults_fn = _methods(settings_cls)["_defaults"]
        defaults_seg = ast.get_source_segment(src, defaults_fn)
        assert defaults_seg is not None
        assert '"nllb_model"' not in defaults_seg, (
            "the dead translation.nllb_model DEFAULTS entry must be gone"
        )
        load_fn = _methods(settings_cls)["_load"]
        # no ("nllb_model", ...) entry in any _load ensure-list tuple
        tuple_keys = [
            t.elts[0].value
            for t in ast.walk(load_fn)
            if isinstance(t, ast.Tuple)
            and t.elts
            and isinstance(t.elts[0], ast.Constant)
            and isinstance(t.elts[0].value, str)
        ]
        assert "nllb_model" not in tuple_keys
        # load-time deletion migration for legacy settings.json files
        assert 'if "nllb_model" in tr:' in src
        assert 'del tr["nllb_model"]' in src
        # the LIVE legacy-backend guard stays (it is what keeps the retired
        # branch unreachable for hand-edited files)
        assert 'tr.get("backend") == "nllb"' in src
        assert 'tr["backend"] = "ollama"' in src

    def test_runtime_import_contract(self):
        # headless + hermetic: the package imports, the class is gone
        import core.translation as translation

        assert not hasattr(translation, "NLLBTranslator")
        assert importlib.util.find_spec("core.translation.nllb_translator") is None
        assert translation.TranslationService is not None

    def test_model_settings_still_live_for_ollama_backend(self):
        # the LIVE translation keys survive (UI + controller + service read
        # them); only the NLLB-only key was retired
        src = _src(_SETTINGS)
        for key in (
            '"backend"',
            '"model"',
            '"harakat_model"',
            '"max_chunk_tokens"',
            '"judge_model"',
        ):
            assert key in src
