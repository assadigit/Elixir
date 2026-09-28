"""Shared test fixtures for Elixir."""

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

# ── V0.6.0 (campaign 4-b, test-infra): hermetic markitdown gate ────────────
# 36 test files carry a copy-pasted ``if "markitdown" not in sys.modules:`` stub
# block — the exact tiktoken-poisoning class conftest fixed above (V18.20.2.0).
# Whichever file is collected FIRST installs ITS fake MarkItDown even when the
# REAL markitdown is installed (a core requirements.txt dep) — real conversions
# then fail session-wide, order-dependently (observed live during the V0.6.0
# tools campaign: the doc-to-md e2e suite passed alone and failed when a
# stubbing file was collected first). Pinning the real package here (one
# functional stub when absent) makes every guarded stub a no-op.
if "markitdown" not in sys.modules:
    try:
        _md_real = _ilu.find_spec("markitdown") is not None
    except Exception:  # pragma: no cover - defensive
        _md_real = False
    if _md_real:
        import markitdown  # noqa: F401  — pin the real package before stubs can shadow it
    else:  # pragma: no cover - only on envs without markitdown
        _md = _types.ModuleType("markitdown")
        _md.MarkItDown = lambda *a, **k: None
        sys.modules["markitdown"] = _md
        del _md

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── P0 (test-infra): pin real PROJECT modules against import-time swaps ──────
# Root cause of the flaky xdist ``test_primary_call`` chunking failures:
# test files (test_bullet_pipeline_golden.py, test_summarizer.py) used to
# replace ``sys.modules["utils.token_counter"]`` (and tiktoken) UNCONDITION-
# ALLY at module level. Under xdist every worker imports ALL test modules at
# collection, but their un-stub fixtures only fire when that file's own tests
# run in that worker — so a worker that merely collected the stubbing file
# kept the stub for the whole session. Worse, the swap is SPLIT-BRAINED:
# ``import utils.token_counter as x`` binds the REAL module via the package
# attribute (``getattr(utils, "token_counter")``), while call-time
# ``from utils.token_counter import count_tokens`` resolves the STUB from
# sys.modules — so monkeypatches landed on one module while production code
# read the other (token counts silently became word counts → chunking,
# map-reduce and budget gates mis-evaluated, order-dependently).
# Fix: conftest is imported by pytest BEFORE any test module, so pinning the
# real project module here makes every ``if name not in sys.modules``-guarded
# stub in test files a guaranteed no-op in every pytest invocation.
if "utils.token_counter" not in sys.modules:
    try:
        import utils.token_counter as _tc_pin  # noqa: F401

        _tc_pin.count_tokens("warmup")  # force lazy _ENCODER init NOW
    except Exception:  # pragma: no cover - defensive
        pass


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """A temporary output directory for conversion tests."""
    d = tmp_path / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── V0.16 (Phase 3): hermetic keyring for EVERY test ────────────────────────
# keyring became a core dependency (Phase 3 / task 3.1). On machines with a
# working OS keychain (the user's Windows rig) the REAL backend would other-
# wise be used by core.system.secrets — tests would write junk credentials
# into the real Windows Credential Manager, and get_secret's migration would
# CLEAR plaintext settings mid-test (order-dependent fallout).
#
# The raising stub below mirrors headless CI exactly: keyring importable
# (_HAS_KEYRING True) but every backend op raises, so get_secret/set_secret
# exercise the keyring path and deterministically fall back to plaintext.
# Tests that WANT a working keychain (tests/test_p3_secrets_wiring.py) install
# their own in-memory backend on top — their monkeypatch teardown restores
# this stub, never the real keyring.
@pytest.fixture(autouse=True)
def _hermetic_keyring(monkeypatch):
    import core.system.secrets as _secrets

    class _RaisingKeyring:
        """Stand-in that behaves like keyring.backends.fail.Keyring."""

        class PasswordDeleteError(Exception):
            pass

        @staticmethod
        def get_password(service, username):
            raise RuntimeError("hermetic test keyring: no backend")

        @staticmethod
        def set_password(service, username, password):
            raise RuntimeError("hermetic test keyring: no backend")

        @staticmethod
        def delete_password(service, username):
            raise _RaisingKeyring.PasswordDeleteError("hermetic test keyring: no backend")

    monkeypatch.setattr(_secrets, "_keyring", _RaisingKeyring, raising=False)
    monkeypatch.setattr(_secrets, "_HAS_KEYRING", True)
    yield
