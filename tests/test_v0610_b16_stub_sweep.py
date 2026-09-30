"""V0.6.10 (B16) — the tiktoken/markitdown stub-block sweep tests.

AUDIT_SWOT W4 (MEASURED): 91+ test files carried copy-pasted
``if "tiktoken" not in sys.modules:`` / ``if "markitdown" not in
sys.modules:`` stub blocks — inert since the conftest gates
(V18.20.2.0 / V0.6.0) install the module BEFORE any test module is
collected, but each block was 5-10 lines of dead weight per file, and the
conftest comments had drifted to 51/36 while reality was 78/37 (the W7
lying-docs find).

The V0.6.10 sweep removed all 109 blocks (87 files, AST-located at module
level, conftest itself excluded). These pins keep it that way: a NEW
copy-pasted stub block must never land again — stub in conftest only.

Run: pytest tests/test_v0610_b16_stub_sweep.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_STUB_GUARDS = {'"tiktoken" not in sys.modules', '"markitdown" not in sys.modules'}


def _module_level_stub_guards(py: Path) -> list[int]:
    """Direct module-level (tree.body) ``if "X" not in sys.modules:``
    guards for tiktoken/markitdown — the copy-pasted head-block family B16
    swept. Function-scoped guards (e.g. test_integration_pipeline's
    _stub_optional_deps, which also stubs modules with NO conftest gate)
    are a different family and stay."""
    tree = ast.parse(py.read_text(encoding="utf-8"))
    hits = []
    for stmt in tree.body:
        if isinstance(stmt, ast.If):
            try:
                test = ast.unparse(stmt.test)
            except Exception:
                continue
            if test in _STUB_GUARDS or test.replace('"', "'") in {
                g.replace('"', "'") for g in _STUB_GUARDS
            }:
                hits.append(stmt.lineno)
    return hits


class TestStubSweep:
    def test_no_per_file_tiktoken_stub_guards_remain(self):
        """No test file (except conftest — the gate itself) may carry a
        module-level ``if "tiktoken" not in sys.modules:`` guard: the
        conftest gate (V18.20.2.0) is the single installer and the per-file
        blocks were inert duplicates (removed V0.6.10 / B16)."""
        offenders = {}
        for py in sorted(_TESTS.glob("*.py")):
            if py.name == "conftest.py":
                continue
            hits = _module_level_stub_guards(py)
            # tiktoken-only for this test
            src = py.read_text(encoding="utf-8")
            tk_hits = [ln for ln in hits if "tiktoken" in src.split("\n")[ln - 1]]
            if tk_hits:
                offenders[py.name] = tk_hits
        assert not offenders, (
            f"copy-pasted tiktoken stub guard(s) found — stub in conftest "
            f"only (V0.6.10 / B16): {offenders}"
        )

    def test_no_per_file_markitdown_stub_guards_remain(self):
        offenders = {}
        for py in sorted(_TESTS.glob("*.py")):
            if py.name == "conftest.py":
                continue
            hits = _module_level_stub_guards(py)
            src = py.read_text(encoding="utf-8")
            md_hits = [ln for ln in hits if "markitdown" in src.split("\n")[ln - 1]]
            if md_hits:
                offenders[py.name] = md_hits
        assert not offenders, (
            f"copy-pasted markitdown stub guard(s) found — stub in conftest "
            f"only (V0.6.10 / B16): {offenders}"
        )

    def test_conftest_gates_still_present(self):
        """The two hermetic gates (the ONLY installers since the sweep) must
        stay: real package when available, one functional stub otherwise."""
        src = (_TESTS / "conftest.py").read_text(encoding="utf-8")
        assert 'if "tiktoken" not in sys.modules:' in src
        assert 'if "markitdown" not in sys.modules:' in src
        # the V0.6.10 history note (the honest count correction 51/36 → 78/37)
        assert "78/37" in src
        assert "the ONLY installer" in src

    def test_swept_files_still_importable_sample(self):
        """Spot-check a sample of swept files import cleanly without their
        stub blocks (the conftest gate provides the modules)."""
        import importlib

        for name in (
            "test_quality_fixes",
            "test_primary_call_checkpoint",
            "test_v18_15_6_timeout",
            "test_v006_rig_audit_fixes",
        ):
            mod = importlib.import_module(f"tests.{name}")
            assert mod is not None
