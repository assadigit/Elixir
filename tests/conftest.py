"""Shared test fixtures for MarkItDown Pro."""
from __future__ import annotations

# ── V18.20.2.0 (SWOT test-infra): hermetic tiktoken gate ────────────────────
# 51 test files carry a copy-pasted ``if "tiktoken" not in sys.modules:`` stub
# block. Whichever file is collected FIRST installs ITS variant (some are
# MagicMock encoders) even when the REAL tiktoken is installed — poisoning
# ``utils.token_counter`` lazy ``_ENCODER`` init for the entire session
# (root cause of the order-dependent failures in test_map_reduce /
# test_primary_call / test_text_utils_ext). conftest is imported by pytest
# BEFORE any test module, so pinning the module here makes every one of those
# guards a no-op: real package when available, ONE functional stub otherwise.
import importlib.util as _ilu
import sys
import types as _types
from pathlib import Path

import pytest

if "tiktoken" not in sys.modules:
    try:
        _tk_real = _ilu.find_spec("tiktoken") is not None
    except Exception:  # pragma: no cover - defensive
        _tk_real = False
    if _tk_real:
        import tiktoken  # noqa: F401  — pin the real package before stubs can shadow it
    else:  # pragma: no cover - only on envs without tiktoken
        _tk = _types.ModuleType("tiktoken")

        class _TkEnc:
            def encode(self, s, disallowed_special=()):  # noqa: D401
                return (s or "").split()

            def decode(self, tokens):  # noqa: D401
                return " ".join(str(t) for t in tokens)

        _tk.Encoding = _TkEnc
        _tk.get_encoding = lambda *a, **k: _TkEnc()
        _tk.encoding_for_model = lambda *a, **k: _TkEnc()
        sys.modules["tiktoken"] = _tk
        del _TkEnc

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """A temporary output directory for conversion tests."""
    d = tmp_path / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d
