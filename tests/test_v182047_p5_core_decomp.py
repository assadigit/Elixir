"""V18.20.4.7 (P5 phase 2 / P5-2a) — core/summarisation decomposition pins.

Covers the four P5-2a work items, headless-safe (pure source/AST parsing
plus one stub-guarded Summarizer import — the house hermeticity pattern
from tests/test_v1820313_thorough_floor.py; no Qt, no network, no GPU):

  (a) O-a2 — the two NEW mixin modules exist and every moved method body
      is BYTE-IDENTICAL to the pre-split V18.20.4.6 zip's summarizer.py
      (ast.get_source_segment, decorators included in the check for the
      @staticmethod pair). The reference zip is
      download/Elixir-V18.20.4.6.zip; the verbatim comparisons
      skip (not fail) when it is absent.
  (b) O-a2 — Summarizer inherits both mixins; the 6 methods resolve
      through the MRO onto the mixin classes; the methods are GONE from
      summarizer.py itself; the NOT-moved neighbours stayed.
  (c) W-a3 — the dead V18.6.3 primary-prompt twin (build_primary_prompt +
      PromptContext) is GONE from prompt_assembly.py; the module still
      compiles, its live functions are intact and byte-identical to the
      .4.6 reference, and __all__ no longer exports the dead names.
  (d) W-a13 — _generate_ab_comparison is gone tree-wide (no def, no live
      call; a citation comment may name it).
  (e) Deny-list belt-and-suspenders for the TOUCHED files (the permanent
      tree-wide guard stays tests/test_v182039_audit_fixes.py — the
      vocabulary below is a copy of its lists) + the W-a14
      neutralizations: no 'identity theme' quote in postcheck_detectors.py
      comments, no book-adjacent few-shot concept in gap_fill_batch.py.

No line-number peeking — everything is located by name via ast.
"""

from __future__ import annotations

import ast
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent

# ── Hermetic stubs (order matters: before the summarizer import) ───────────
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.Encoding = MagicMock
    _tk.get_encoding = MagicMock(return_value=MagicMock())
    _tk.encoding_for_model = MagicMock(return_value=MagicMock())
    sys.modules["tiktoken"] = _tk
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Paths ──────────────────────────────────────────────────────────────────
_SUM = _project_root / "core" / "summarisation" / "summarizer.py"
_ADD = _project_root / "core" / "summarisation" / "additive_sections.py"
_FLOOR = _project_root / "core" / "summarisation" / "thorough_theorist_floor.py"
_PA = _project_root / "core" / "summarisation" / "prompt_assembly.py"
_PB = _project_root / "core" / "summarisation" / "prompt_builders.py"  # V0.18 (Phase 5.1, step 6)
_DET = _project_root / "core" / "summarisation" / "postcheck_detectors.py"
_GFB = _project_root / "core" / "summarisation" / "gap_fill_batch.py"
_CI = _project_root / "core" / "pipeline" / "converter_impl.py"
_PKG_INIT = _project_root / "core" / "summarisation" / "__init__.py"
_EXT_IMPORTER = _project_root / "core" / "pipeline" / "conversion" / "summarization.py"

# The shipped pre-split reference (the P5-2a moves happened after .4.6).
_REF_ZIP = _project_root.parent.parent / "download" / ("Elixir-V18.20.4.6.zip")
_REF_MEMBER_SUM = "Elixir-V18.20.4.6/core/summarisation/summarizer.py"
_REF_MEMBER_PA = "Elixir-V18.20.4.6/core/summarisation/prompt_assembly.py"

_MOVED_TO_ADDITIVE = (
    "_ensure_conclusion_bullets",
    "_normalize_empty_section",
    "_verify_additive_section_item",
    "_verify_additive_sections",
    "_ensure_additive_sections",
)
_MOVED_TO_FLOOR = ("_thorough_theorist_floor",)
# V0.18 (Phase 5.1, step 1): the post-judge phases of _summarize_inner moved
# VERBATIM to chapter_phases (SummarizerChapterPhasesMixin).
# V0.18 (Phase 5.1, steps 2-4): + the setup gate, single-pass primary,
# thorough/coverage, and validation/judge phases — _summarize_inner is now a
# 170-line orchestrator (strategy dispatch + state threading only).
_MOVED_TO_CHAPTER_PHASES = (
    "_phase_recovery_pass",
    "_phase_deterministic_judge",
    "_phase_postchecks_and_floors",
    "_phase_finalize",
    "_phase_setup_and_gate",
    "_phase_single_pass_primary",
    "_phase_thorough_and_coverage",
    "_phase_validation_and_judge",
)
_NOT_MOVED_NEIGHBOURS = (
    "_recover_vram",  # generic VRAM recovery — deliberately NOT moved
    "_scholar_reflection",  # P1 scholar wiring — stays in summarizer.py
    "_summarize_inner",  # the orchestrator — stays in summarizer.py (V0.18: 170 lines)
    # V0.18 (Phase 5.1, step 6): _build_prompt moved VERBATIM to
    # prompt_builders.py (SummarizerPromptMixin) — removed from this list.
)
_LIVE_PA_FUNCTIONS = (
    "build_thorough_followup",
    "build_dedicated_thorough_prompt",
    "build_dedicated_bullet_prompt",
    "build_missing_keywords_reprompt",
    "build_chunked_prompt",
)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _methods(cls: ast.ClassDef) -> dict:
    return {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _seg(src: str, node: ast.AST) -> str:
    return ast.get_source_segment(src, node)


# ═══════════════════════════════════════════════════════════════════════════
# (a) O-a2 — verbatim mixin extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestMixinModulesExist:
    def test_both_new_modules_exist_and_parse(self):
        for path in (_ADD, _FLOOR):
            assert path.is_file(), f"{path.name} missing"
            ast.parse(_src(path))

    def test_mixin_classes_defined(self):
        add_cls = _class(ast.parse(_src(_ADD)), "SummarizerAdditiveMixin")
        floor_cls = _class(ast.parse(_src(_FLOOR)), "SummarizerThoroughFloorMixin")
        assert set(_methods(add_cls)) == set(_MOVED_TO_ADDITIVE), sorted(_methods(add_cls))
        assert set(_methods(floor_cls)) == set(_MOVED_TO_FLOOR)

    def test_mixins_do_not_import_summarizer(self):
        """Acyclic: the mixin modules never import their host module."""
        for path in (_ADD, _FLOOR):
            tree = ast.parse(_src(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert "summarizer" not in (node.module or ""), path.name

    def test_mixins_only_imported_by_summarizer(self):
        """No runtime module bypasses the Summarizer re-homing (AST import
        check — mentions of the ``summarisation/additive_sections`` PROMPT
        TEMPLATE name are not imports)."""
        offenders = []
        for p in _project_root.glob("core/**/*.py"):
            if p in (_ADD, _FLOOR, _SUM):
                continue
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in (
                    "core.summarisation.additive_sections",
                    "core.summarisation.thorough_theorist_floor",
                ):
                    offenders.append(f"{p.relative_to(_project_root)}:{node.lineno}")
        assert not offenders, offenders


class TestVerbatimBodiesVsV182046:
    """Every moved method byte-identical to the .4.6 zip's summarizer.py."""

    def _ref_sum_src(self) -> str:
        if not _REF_ZIP.exists():
            pytest.skip(f"reference zip not present: {_REF_ZIP}")
        with zipfile.ZipFile(_REF_ZIP) as zf:
            return zf.read(_REF_MEMBER_SUM).decode("utf-8")

    def test_moved_methods_byte_identical_to_reference(self):
        ref_src = self._ref_sum_src()
        ref_methods = _methods(_class(ast.parse(ref_src), "Summarizer"))
        add_src = _src(_ADD)
        add_methods = _methods(_class(ast.parse(add_src), "SummarizerAdditiveMixin"))
        floor_src = _src(_FLOOR)
        floor_methods = _methods(_class(ast.parse(floor_src), "SummarizerThoroughFloorMixin"))
        for name in _MOVED_TO_ADDITIVE:
            assert _seg(add_src, add_methods[name]) == _seg(ref_src, ref_methods[name]), (
                f"{name} drifted in the O-a2 move (must be byte-identical)"
            )
            assert [d.id for d in add_methods[name].decorator_list if isinstance(d, ast.Name)] == [
                d.id for d in ref_methods[name].decorator_list if isinstance(d, ast.Name)
            ], f"{name} decorator drift"
        for name in _MOVED_TO_FLOOR:
            assert _seg(floor_src, floor_methods[name]) == _seg(ref_src, ref_methods[name]), (
                f"{name} drifted in the O-a2 move (must be byte-identical)"
            )

    def test_all_surviving_summarizer_methods_byte_identical(self):
        """The strongest non-drift proof: every method that stayed is
        byte-identical to the .4.6 reference too — EXCEPT the two
        intentional documented exceptions:

        - ``_build_prompt`` (P5 / W-a3): its docstring carries the ONE
          intentional correction (the stale "the twin remains in
          prompt_assembly.py" sentence became the "the dead twin was
          deleted there" note; the code body is byte-identical).
        - ``_call_llm`` (V18.20.4.8 / P6 / O-a8, fixes W-a9): max_tokens
          joined the response-cache key — the stale "max_tokens is NOT
          part of the cache key" comment block was replaced by the P6
          note, and the two ``response_cache.get/put`` calls gained the
          4th ``max_tok`` argument. Nothing else in the method body
          changed; the pinned substitutions below are guarded (each
          asserts the OLD text exists in the reference first, so any
          additional drift still fails).
        """
        ref_src = self._ref_sum_src()
        ref_methods = _methods(_class(ast.parse(ref_src), "Summarizer"))
        new_src = _src(_SUM)
        new_methods = _methods(_class(ast.parse(new_src), "Summarizer"))
        moved = set(_MOVED_TO_ADDITIVE) | set(_MOVED_TO_FLOOR)
        assert set(ref_methods) - set(new_methods) == moved
        ref_note = (
            "to restore stability. The prompt_assembly.build_primary_prompt\n"
            "        function + PromptContext class remain in prompt_assembly.py for\n"
            "        future re-extraction once the crash is diagnosed."
        )
        new_note = (
            "to restore stability. V18.20.4.7 (P5 / W-a3): the dead twin that\n"
            "        stayed behind in prompt_assembly.py after this rollback was\n"
            "        deleted there — this inline builder is the only one."
        )
        ref_cache_note = (
            "        # Note: max_tokens is NOT part of the cache key — a longer max_tokens\n"
            "        # for the same prompt+model+temperature would return a truncated cached\n"
            "        # response.  This is acceptable because temperature=0 (the common case\n"
            "        # for gap-fill/grounding) produces deterministic output regardless of\n"
            "        # max_tokens.  For temperature>0, the cache is still useful (the first\n"
            "        # response is as good as any)."
        )
        new_cache_note = (
            "        # V18.20.4.8 (P6 / O-a8, fixes W-a9): max_tokens IS part of the cache\n"
            "        # key now (passed as the 4th arg below). The old key\n"
            "        # (prompt+model+temperature) let a call with a larger max_tokens\n"
            "        # return a truncated cached response — call sites vary max_tokens\n"
            "        # 2048/4096/6144/16000 (academic-rigor floor, scholar reflection).\n"
            "        # Old cache entries simply miss under the new key — safe."
        )
        for name, node in new_methods.items():
            expected = _seg(ref_src, ref_methods[name])
            if name == "_build_prompt":
                assert ref_note in expected
                expected = expected.replace(ref_note, new_note, 1)
            if name == "_call_llm":
                # P6 / O-a8: comment block + the two cache-key call sites.
                assert ref_cache_note in expected
                expected = expected.replace(ref_cache_note, new_cache_note, 1)
                assert 'response_cache.get(prompt, model or "", temp)' in expected
                expected = expected.replace(
                    'response_cache.get(prompt, model or "", temp)',
                    'response_cache.get(prompt, model or "", temp, max_tok)',
                    1,
                )
                assert 'response_cache.put(prompt, model or "", temp, _result)' in expected
                expected = expected.replace(
                    'response_cache.put(prompt, model or "", temp, _result)',
                    'response_cache.put(prompt, model or "", temp, _result, max_tok)',
                    1,
                )
            assert _seg(new_src, node) == expected, name

    def test_summarizer_class_level_assigns_unchanged(self):
        """Every class-level assign is byte-identical to the .4.6 reference
        — EXCEPT ``_STRUCTURAL_FUNCTION_WORDS`` (V18.20.4.8 / P6 / O-a5,
        fixes W-a5): the 93-word literal became the alias of the canonical
        ``core.summarisation.structural_stopwords`` import. Evolved, not
        weakened: the alias form is pinned exactly, every OTHER assign
        must still match the reference byte-for-byte, and the canonical
        set's MEMBERSHIP must equal the .4.6 reference literal (no drift
        in the move)."""
        ref_src = self._ref_sum_src()
        ref_cls = _class(ast.parse(ref_src), "Summarizer")
        new_cls = _class(ast.parse(_src(_SUM)), "Summarizer")
        ref_a = [ast.unparse(n) for n in ref_cls.body if isinstance(n, ast.Assign)]
        new_a = [ast.unparse(n) for n in new_cls.body if isinstance(n, ast.Assign)]
        ref_stop = [s for s in ref_a if s.startswith("_STRUCTURAL_FUNCTION_WORDS =")]
        new_stop = [s for s in new_a if s.startswith("_STRUCTURAL_FUNCTION_WORDS =")]
        assert len(ref_stop) == 1 and len(new_stop) == 1
        assert [s for s in ref_a if not s.startswith("_STRUCTURAL_FUNCTION_WORDS =")] == (
            [s for s in new_a if not s.startswith("_STRUCTURAL_FUNCTION_WORDS =")]
        )
        assert new_stop == ["_STRUCTURAL_FUNCTION_WORDS = STRUCTURAL_FUNCTION_WORDS"]
        # membership parity with the .4.6 reference literal (93 words, no drift)
        ref_assign = next(
            n
            for n in ref_cls.body
            if isinstance(n, ast.Assign)
            and ast.unparse(n).startswith("_STRUCTURAL_FUNCTION_WORDS =")
        )
        ref_set = ast.literal_eval(ref_assign.value.args[0])
        from core.summarisation.structural_stopwords import STRUCTURAL_FUNCTION_WORDS

        assert ref_set == STRUCTURAL_FUNCTION_WORDS, (
            "the canonical set must carry the exact .4.6 reference membership"
        )


# ═══════════════════════════════════════════════════════════════════════════
# (b) O-a2 — Summarizer inherits the mixins
# ═══════════════════════════════════════════════════════════════════════════


class TestSummarizerInheritance:
    def test_class_bases_are_exactly_the_mixins(self):
        cls = _class(ast.parse(_src(_SUM)), "Summarizer")
        # V0.18 (Phase 5.1, step 1): SummarizerChapterPhasesMixin joined the
        # bases (the post-judge phases of _summarize_inner moved VERBATIM to
        # core.summarisation.chapter_phases).
        # V0.18 (Phase 5.1, step 5): + SummarizerInitMixin (the _init_*
        # sub-constructors moved to core.summarisation.summarizer_init).
        # V0.18 (Phase 5.1, step 6): + SummarizerPromptMixin (the prompt
        # builders moved to core.summarisation.prompt_builders).
        assert [ast.unparse(b) for b in cls.bases] == [
            "SummarizerPromptMixin",
            "SummarizerInitMixin",
            "SummarizerChapterPhasesMixin",
            "SummarizerAdditiveMixin",
            "SummarizerThoroughFloorMixin",
        ]

    def test_summarizer_imports_both_mixins(self):
        src = _src(_SUM)
        assert "from core.summarisation.additive_sections import SummarizerAdditiveMixin" in src
        assert "SummarizerThoroughFloorMixin" in src

    def test_moved_methods_gone_from_summarizer_file(self):
        methods = _methods(_class(ast.parse(_src(_SUM)), "Summarizer"))
        for name in _MOVED_TO_ADDITIVE + _MOVED_TO_FLOOR:
            assert name not in methods, f"{name} must be re-homed, not copied"

    def test_not_moved_neighbours_stayed(self):
        methods = _methods(_class(ast.parse(_src(_SUM)), "Summarizer"))
        for name in _NOT_MOVED_NEIGHBOURS:
            assert name in methods, f"{name} must stay in summarizer.py"

    def test_runtime_mro_resolution(self):
        """Import the real module (hermetic stubs above) — the 6 methods
        must resolve through the MIXINS on the Summarizer MRO."""
        from core.summarisation.additive_sections import SummarizerAdditiveMixin
        from core.summarisation.summarizer import Summarizer
        from core.summarisation.thorough_theorist_floor import (
            SummarizerThoroughFloorMixin,
        )

        assert issubclass(Summarizer, SummarizerAdditiveMixin)
        assert issubclass(Summarizer, SummarizerThoroughFloorMixin)
        for name in _MOVED_TO_ADDITIVE:
            home = next(c for c in Summarizer.__mro__ if name in vars(c))
            assert home is SummarizerAdditiveMixin, name
        home = next(c for c in Summarizer.__mro__ if "_thorough_theorist_floor" in vars(c))
        assert home is SummarizerThoroughFloorMixin

    def test_mixin_loggers_are_the_main_app_logger(self):
        """The re-homed ``logger`` must be the SAME object summarizer.py
        holds (fail-soft debug lines behave identically)."""
        from core.summarisation.additive_sections import logger as add_logger
        from core.summarisation.chapter_phases import logger as phases_logger
        from core.summarisation.summarizer import logger as sum_logger
        from core.summarisation.thorough_theorist_floor import logger as floor_logger

        assert add_logger is sum_logger
        assert floor_logger is sum_logger
        assert phases_logger is sum_logger  # V0.18 (Phase 5.1, step 1)

    def test_chapter_phase_methods_rehomed_in_mixin(self):
        """V0.18 (Phase 5.1, step 1): the phase methods live in the mixin,
        not in summarizer.py's class body."""
        from core.summarisation.chapter_phases import SummarizerChapterPhasesMixin
        from core.summarisation.summarizer import Summarizer

        methods = _methods(_class(ast.parse(_src(_SUM)), "Summarizer"))
        for name in _MOVED_TO_CHAPTER_PHASES:
            assert name not in methods, f"{name} must be re-homed, not copied"
            home = next(c for c in Summarizer.__mro__ if name in vars(c))
            assert home is SummarizerChapterPhasesMixin, name

    def test_external_import_surface_unchanged(self):
        """The one real runtime importer (core/pipeline/conversion/
        summarization.py) and the package re-export are untouched."""
        init_src = _src(_PKG_INIT)
        assert "from .summarizer import Summarizer" in init_src
        ext_src = _src(_EXT_IMPORTER)
        assert "from core.summarisation import Summarizer" in ext_src


# ═══════════════════════════════════════════════════════════════════════════
# (c) W-a3 — the dead primary-prompt twin is GONE
# ═══════════════════════════════════════════════════════════════════════════


class TestWa3DeadTwinGone:
    def test_module_compiles(self):
        compile(_src(_PA), str(_PA), "exec")

    def test_twin_names_gone(self):
        tree = ast.parse(_src(_PA))
        names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        assert "build_primary_prompt" not in names
        assert "PromptContext" not in names

    def test_all_exports_gone_from_dunder_all(self):
        tree = ast.parse(_src(_PA))
        all_node = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "__all__"
        )
        exported = ast.literal_eval(all_node.value)
        assert "build_primary_prompt" not in exported
        assert "PromptContext" not in exported
        assert set(exported) == set(_LIVE_PA_FUNCTIONS)

    def test_live_functions_intact(self):
        tree = ast.parse(_src(_PA))
        names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        for name in _LIVE_PA_FUNCTIONS:
            assert name in names, f"live function {name} went missing"
        # The delegates summarizer.py actually calls (all live):
        for name in ("build_exec_from_thorough_prompt", "_lang_str"):
            assert name in names, name

    def test_live_function_bodies_byte_identical_to_reference(self):
        if not _REF_ZIP.exists():
            pytest.skip(f"reference zip not present: {_REF_ZIP}")
        with zipfile.ZipFile(_REF_ZIP) as zf:
            ref_src = zf.read(_REF_MEMBER_PA).decode("utf-8")
        ref_tree = ast.parse(ref_src)
        new_src = _src(_PA)
        new_tree = ast.parse(new_src)
        ref_defs = {
            n.name: n for n in ref_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        }
        new_defs = {
            n.name: n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        }
        assert set(ref_defs) - set(new_defs) == {"PromptContext", "build_primary_prompt"}
        for name, node in new_defs.items():
            assert _seg(new_src, node) == _seg(ref_src, ref_defs[name]), name

    def test_no_runtime_twin_references_remain(self):
        """AST scan: nothing in core/ imports or calls the twin names
        (comment citations are allowed)."""
        offenders = []
        for p in _project_root.glob("core/**/*.py"):
            if p == _PA:
                continue
            src = p.read_text(encoding="utf-8", errors="replace")
            if "build_primary_prompt" not in src and "PromptContext" not in src:
                continue
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name in ("build_primary_prompt", "PromptContext"):
                            offenders.append(f"{p.name}:{node.lineno}")
                if isinstance(node, ast.Call):
                    fn = node.func
                    nm = (
                        fn.id
                        if isinstance(fn, ast.Name)
                        else (fn.attr if isinstance(fn, ast.Attribute) else None)
                    )
                    if nm in ("build_primary_prompt", "PromptContext"):
                        offenders.append(f"{p.name}:{node.lineno}")
        assert not offenders, offenders

    def test_live_inline_builder_still_in_summarizer(self):
        """The LIVE inline _build_prompt builder still exists (V0.18 Phase
5.1 step 6: moved VERBATIM to prompt_builders.py — the pin follows)."""

        methods = _methods(
            _class(ast.parse(_src(_PB)), "SummarizerPromptMixin")
        )
        assert "_build_prompt" in methods


# ═══════════════════════════════════════════════════════════════════════════
# (d) W-a13 — dead A/B comparison method deleted
# ═══════════════════════════════════════════════════════════════════════════


class TestWa13DeadMethodGone:
    def test_no_definition_or_live_call_tree_wide(self):
        offenders = []
        for p in _project_root.glob("core/**/*.py"):
            src = p.read_text(encoding="utf-8", errors="replace")
            if "_generate_ab_comparison" not in src:
                continue
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "_generate_ab_comparison":
                    offenders.append(f"{p.relative_to(_project_root)}:DEF:{node.lineno}")
                if isinstance(node, ast.Call):
                    fn = node.func
                    nm = (
                        fn.id
                        if isinstance(fn, ast.Name)
                        else (fn.attr if isinstance(fn, ast.Attribute) else None)
                    )
                    if nm == "_generate_ab_comparison":
                        offenders.append(f"{p.relative_to(_project_root)}:CALL:{node.lineno}")
        assert not offenders, offenders

    def test_quality_report_path_still_live(self):
        """The deletion took only the dead method: the LIVE quality-report
        machinery in converter_impl.py is untouched."""
        src = _src(_CI)
        assert "_generate_quality_report" in src
        assert "atomic_write_json" in src


# ═══════════════════════════════════════════════════════════════════════════
# (e) deny-list green check for the touched files + W-a14 neutralizations
# ═══════════════════════════════════════════════════════════════════════════

# Vocabulary copied from tests/test_v182039_audit_fixes.py (the permanent
# tree-wide guard — this local copy keeps this file self-contained).
_DENY_NAMES = [
    "Jacobson",
    "Freud",
    "Erikson",
    "Kernberg",
    "Mahler",
    "Blos",
    "Winnicott",
    "Lichtenstein",
    "Greenacre",
    "Chasseguet",
    "Smirgel",
    "Fenichel",
    "Hartmann",
    "Searles",
    "Eissler",
    "Fromm",
    "Wheelis",
    "Lynd",
    "Lifton",
    "Lasch",
    "Kovel",
    "Tausk",
    "Glover",
    "Stoller",
    "Galenson",
    "Roiphe",
    "Kris",
    "Loewenstein",
    "Spitz",
    "Khan",
    "Klein",
    "Loewald",
    "Guttman",
    "Whitman",
    "Marx",
    "Durkheim",
    "Akhtar",
    "Salman",
    "Oedipus",
    "oedipal",
    "Jews",
    "Jewry",
    "WINNICOTT",
    "Ryan",
    "Thad",
    "Clive",
    "Tyler",
    "Bernard",
    "Georgina",
    "Brad",
]
_DENY_CONCEPTS = [
    "false self",
    "true self",
    "identity diffusion",
    "ego identity",
    "identity principle",
    "corporeality",
    "sine qua non",
    "psychoanalytic",
    "psychoanalysis",
    "psychoanalysts",
    "metapsychological",
    "object relations",
    "self psychology",
    "Broken Structures",
    "IDENTITY AND ITS ORIGINS",
    "identity and its origins",
    "Song of Myself",
    "das Ich",
    "second individuation",
    "psychic structure",
    "self-object",
    "developmental basis",
    "three-step process",
    "entrepreneurs",
    "operatives",
    "spies",
]
# V0.18 (Phase 5.2): the postchecks package files (verbatim moves from
# postcheck_detectors.py) join the deny-list scan — same rule, new homes.
_POSTCHECKS_PKG = _project_root / "core" / "summarisation" / "postchecks"
_TOUCHED = (
    _SUM,
    _ADD,
    _FLOOR,
    _PA,
    _DET,
    _GFB,
    _CI,
    _POSTCHECKS_PKG / "shared.py",
    _POSTCHECKS_PKG / "leakage.py",
    _POSTCHECKS_PKG / "garble.py",
    _POSTCHECKS_PKG / "attribution.py",
    _POSTCHECKS_PKG / "coherence.py",
    _POSTCHECKS_PKG / "orchestrator.py",
    _POSTCHECKS_PKG / "__init__.py",
)


class TestDenyListTouchedFiles:
    def test_no_book_derived_names_or_concepts_in_touched_files(self):
        import re as _re

        name_rx = _re.compile(r"\b(?:" + "|".join(_re.escape(n) for n in _DENY_NAMES) + r")\b")
        offenders = []
        for p in _TOUCHED:
            for i, line in enumerate(
                p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if name_rx.search(line):
                    offenders.append(f"{p.name}:{i}")
                    continue
                for term in _DENY_CONCEPTS:
                    rx = _re.compile(_re.escape(term), _re.IGNORECASE if term[0].islower() else 0)
                    if rx.search(line):
                        offenders.append(f"{p.name}:{i} [{term}]")
                        break
        assert not offenders, (
            "book-derived vocabulary in a P5-2a touched file "
            f"(the no-hardcoding rule): {offenders[:10]}"
        )

    def test_wa14_identity_theme_quotes_neutralized(self):
        """W-a14: postcheck_detectors.py no longer quotes the chapter's
        'identity theme' in its comments (a neutral placeholder is used)."""
        assert "'identity theme'" not in _src(_DET)
        assert '"identity theme"' not in _src(_DET)

    def test_wa14_gap_fill_example_neutral(self):
        """W-a14: the gap-fill few-shot example keeps the house synthetic
        names + structure, but its concept phrase is book-neutral now (the
        old phrase mirrored the test chapter's staged-process concept)."""
        src = _src(_GFB)
        # structure + synthetic names kept (the .3.9 pin in
        # test_v182039_audit_fixes.py asserts the same names):
        assert "Voss" in src and "Ibarra" in src
        assert "integrated Ibarra" in src
        # the book-adjacent concept surface is gone:
        assert "three-stage model" not in src
        assert "model of consolidation" not in src
        # its replacement is a neutral concept:
        assert "two-factor model of" in src


if __name__ == "__main__":  # pragma: no cover — manual run convenience
    sys.exit(pytest.main([__file__, "-v"]))
