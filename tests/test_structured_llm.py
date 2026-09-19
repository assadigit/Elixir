"""V18.15.3 (Phase 5 Stage 3, Batch 4.1) — structured_llm characterization tests.

Byte-for-byte stability gate for ``call_llm_structured`` extracted from
``Summarizer._call_llm_structured``. Each test captures a branch of the
original method with mocked ``core.llm.structured_io`` /
``core.llm.llm_provider`` so the LLM stack is never actually invoked.

Branches covered:
1. ``core.llm.structured_io`` import unavailable → returns None (XML path)
2. ``supports_json_mode`` returns False (IQ2_XXS) → returns None
3. provider build raises → returns None
4. success path → returns the dict + logs the bullet count
5. result is None → no log call

Run: pytest tests/test_structured_llm.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so the import chain works (matches sibling tests).
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk

from core.summarisation.structured_llm import call_llm_structured

# V18.20.2.0 (SWOT test-debt): the ``_install_*`` helpers below REPLACE
# ``sys.modules`` entries ('core.llm.structured_io', 'core.llm.llm_provider',
# 'utils.settings') with bare assignments that were never restored. The stubs
# leaked into every test file that ran after this one (alphabetical order):
# test_v18_2_15_performance.py's Settings tests hit the attribute-less
# ``_Settings`` stub (AttributeError: no 'set'/'get'), test_v18202_llm_fixes.py's
# structured-path gate saw a stubbed ``supports_json_mode`` returning False
# (the one-time INFO notice never fired), and test_v18202_system_fixes.py's
# settings/cancel tests errored. The autouse fixture below snapshots the three
# entries and restores them after every test in this file, making the file
# hermetic while keeping every assertion unchanged.
_STUBBED_MODULES = (
    "core.llm.structured_io",
    "core.llm.llm_provider",
    "utils.settings",
    "core.llm",
)
_MISSING = object()


@pytest.fixture(autouse=True)
def _restore_stubbed_sys_modules():
    """Snapshot/restore the sys.modules entries the helpers replace."""
    _saved = {name: sys.modules.get(name, _MISSING) for name in _STUBBED_MODULES}
    yield
    for name, mod in _saved.items():
        if mod is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


def _install_structured_io(supports_json=True, complete_result=None):
    """Inject a fake ``core.llm.structured_io`` module into sys.modules."""
    mod = types.ModuleType("core.llm.structured_io")
    mod.supports_json_mode = lambda provider, model: supports_json
    mod.complete_structured = lambda *a, **k: complete_result
    sys.modules["core.llm.structured_io"] = mod
    return mod


def _install_llm_provider(raises=False):
    """Inject a fake ``core.llm.llm_provider`` + ``utils.settings.Settings``."""
    pkg = sys.modules.get("core.llm")
    if pkg is None:
        pkg = types.ModuleType("core.llm")
        sys.modules["core.llm"] = pkg
    lp = types.ModuleType("core.llm.llm_provider")

    def _create(*a, **k):
        if raises:
            raise RuntimeError("boom")
        return object()

    lp.create_provider = _create
    sys.modules["core.llm.llm_provider"] = lp
    # Settings stub
    s = types.ModuleType("utils.settings")

    class _Settings:
        def __init__(self):
            pass

    s.Settings = _Settings
    sys.modules["utils.settings"] = s


def _setup_chain(supports_json=True, complete_result=None, provider_raises=False):
    _install_structured_io(supports_json=supports_json, complete_result=complete_result)
    _install_llm_provider(raises=provider_raises)


class TestStructuredLlmBranches:
    def test_structured_io_unavailable_returns_none(self, monkeypatch):
        """Branch 1: core.llm.structured_io import fails → None (XML path)."""
        # Remove the module so the inline import raises ImportError.
        monkeypatch.delitem(sys.modules, "core.llm.structured_io", raising=False)
        # Force the inline ``from core.llm.structured_io import ...`` to fail.
        import builtins

        real_import = builtins.__import__

        def _blocking_import(name, *a, **k):
            if name == "core.llm.structured_io":
                raise ImportError("blocked for test")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _blocking_import)
        result = call_llm_structured("p", "m", 0.7, 4096, provider="ollama")
        assert result is None

    def test_unsupported_model_returns_none(self, monkeypatch):
        """Branch 2: supports_json_mode False (IQ2_XXS) → None."""
        _setup_chain(supports_json=False, complete_result={"bullet_points": ["x"]})
        result = call_llm_structured("p", "iq2_xxs", 0.7, 4096, provider="ollama")
        assert result is None

    def test_provider_build_failure_returns_none(self, monkeypatch):
        """Branch 3: create_provider raises → None."""
        _setup_chain(
            supports_json=True, complete_result={"bullet_points": ["x"]}, provider_raises=True
        )
        result = call_llm_structured("p", "m", 0.7, 4096, provider="ollama")
        assert result is None

    def test_success_returns_result_and_logs(self, monkeypatch):
        """Branch 4: success path returns dict + logs bullet count.

        V18.20.2.0 (SWOT A16): the structured path is DISABLED in production
        (``_STRUCTURED_PATH_ENABLED = False`` — behavior preservation, see
        structured_llm.py's header). This test flips the flag ON to keep
        characterizing the underlying success flow (correct provider
        construction → complete_structured → dict + DEBUG log). The
        production-off contract (returns None, one-time INFO notice) is
        covered in tests/test_v18202_llm_fixes.py.
        """
        import core.summarisation.structured_llm as _sl

        monkeypatch.setattr(_sl, "_STRUCTURED_PATH_ENABLED", True)
        _setup_chain(supports_json=True, complete_result={"bullet_points": ["a", "b", "c"]})
        logs = []
        result = call_llm_structured(
            "p",
            "m",
            0.7,
            4096,
            provider="ollama",
            parse_response=lambda r: {"bullet_points": []},
            log=lambda msg, level="INFO": logs.append((msg, level)),
        )
        assert result == {"bullet_points": ["a", "b", "c"]}
        # Exactly one DEBUG log mentioning the bullet count.
        assert len(logs) == 1
        msg, level = logs[0]
        assert level == "DEBUG"
        assert "3 bullets" in msg
        assert "Structured output" in msg

    def test_none_result_no_log(self, monkeypatch):
        """Branch 5: complete_structured returns None → no log call.

        V18.20.2.0 (SWOT A16): flag flipped ON to keep exercising the
        complete_structured flow (in production the disabled gate returns
        None earlier — see tests/test_v18202_llm_fixes.py for that gate).
        """
        import core.summarisation.structured_llm as _sl

        monkeypatch.setattr(_sl, "_STRUCTURED_PATH_ENABLED", True)
        _setup_chain(supports_json=True, complete_result=None)
        logs = []
        result = call_llm_structured(
            "p",
            "m",
            0.7,
            4096,
            provider="ollama",
            parse_response=lambda r: {},
            log=lambda msg, level="INFO": logs.append(msg),
        )
        assert result is None
        assert logs == []

    def test_provider_defaults_to_ollama(self, monkeypatch):
        """provider=None → defaults to 'ollama' (getattr behaviour preserved)."""
        captured = {}
        mod = _install_structured_io(supports_json=True, complete_result=None)

        def _supports(provider, model):
            captured["provider"] = provider
            return False  # short-circuit to None

        mod.supports_json_mode = _supports
        _install_llm_provider(raises=False)
        call_llm_structured("p", "m", 0.7, 4096, provider=None)
        assert captured["provider"] == "ollama"
