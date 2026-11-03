"""Shared test fixtures for Elixir."""

from __future__ import annotations

# ── V18.20.2.0 (SWOT test-infra): hermetic tiktoken gate ────────────────────
# (V0.6.10 / B16 history) 51→78 test files HAD carried a copy-pasted
# ``if "tiktoken" not in sys.modules:`` stub block — the count comments here
# had drifted to 51/36 while the reality was 78/37 (the AUDIT_SWOT W7
# lying-docs find; 79/38 at sweep time — this session's new
# test_v0610_wave5_godfunction_decomp.py had added one of each). The V0.6.10
# sweep REMOVED all 109 inert per-file blocks (87 files) — this gate is now
# the ONLY installer. Whichever file was collected FIRST used to install ITS
# variant (some were MagicMock encoders) even when the REAL tiktoken was
# installed — poisoning
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
# (V0.6.10 / B16) 36→37 test files HAD carried a copy-pasted
# ``if "markitdown" not in sys.modules:`` stub block — removed by the V0.6.10
# sweep; this gate is the only installer. The exact tiktoken-poisoning class
# conftest fixed above (V18.20.2.0):
# Whichever file was collected FIRST used to install ITS fake MarkItDown even
# when the REAL markitdown was installed (a core requirements.txt dep) — real
# conversions then failed session-wide, order-dependently (observed live during
# the V0.6.0
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


# ── V0.6.6 (review-loop B1): session-wide _runtime_state reset ─────────
# The V18.20.1.0 (D3) refactor moved the shared summarisation singletons
# onto core.summarisation._runtime_state.state, but the reset fixture
# lived ONLY in tests/test_runtime_state.py — file-scoped. Other files'
# fixtures (test_golden_freeze / test_group_b_characterization /
# test_p2_summarizer_harness) still snapshot/restore the DEAD module-
# level proxies, so a run that polluted the state (e.g. golden_freeze's
# warned_embedding_disabled=True) leaked it into every LATER file —
# the same cross-file poisoning class as the Settings._test_override
# leak (proven live: golden_freeze + a state-asserting victim → 1
# failed). Resetting here, autouse for EVERY test, makes the whole
# class impossible regardless of which file pollutes.
@pytest.fixture(autouse=True)
def _reset_runtime_state():
    from core.summarisation._runtime_state import state

    state.reset()
    yield
    state.reset()


# ── V0.6.83.1 (Round-3 CI hotfix): per-test top-level widget cleanup ─────────
# The Qt-enabled CI run (run 226) exposed the second order-dependent crash
# the V0.6.83 release notes documented but never repaired: the behavioural
# dialog tests (TtsServiceDialog and every other BaseServiceDialog driver)
# create top-level dialogs that are never closed or deleted — the dialog's
# Python name simply goes out of scope while the C++ QWidget lives on under
# the QApplication. At interpreter shutdown Shiboken then destroys those
# widgets around/after the QApplication itself — the classic PySide6
# use-after-free (reproduced standalone: TestTtsServiceDialogWorkerDrive
# alone → 9 passed, then SIGSEGV; TestTtsServiceDialogProcessEngineMatrix
# alone → same; the corrupted heap also detonated mid-suite at the podcast
# e2e's ffmpeg fork, exit 139 with no summary, on the first Qt-enabled
# full-suite run). close() alone does NOT free the C++ object — and close()
# is also WRONG in teardown (the dialogs' closeEvent guards raise a modal
# QMessageBox no headless run can answer). The fix is hide + deleteLater +
# a DeferredDelete-ONLY event pass (a plain processEvents drain delivers
# still-queued application events onto the half-torn-down dialog — the
# third crash, SIGABRT inside image_extractor_dialog._on_done) after EVERY
# test. The QApplication singleton itself
# is deliberately kept (the suite's ``QApplication.instance() or
# QApplication([])`` pattern depends on it); only the per-test widgets are
# released. Pure tests pay one guarded import+instance check; Qt tests gain
# the teardown hygiene pytest-qt's qtbot would otherwise provide.
@pytest.fixture(autouse=True)
def _dispose_qt_toplevel_widgets():
    yield
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        for w in list(app.topLevelWidgets()):
            # hide() not close(): close() runs closeEvent, and the dialog
            # guards ("a background task is still running — close anyway?")
            # raise a MODAL QMessageBox whose nested event loop nobody can
            # click in a headless run — an instant suite hang. Teardown is
            # mechanical: hide now, schedule the C++ deletion.
            try:
                w.hide()
            except Exception:
                pass
            try:
                w.deleteLater()
            except Exception:
                pass
        # Process ONLY the deferred deletions — a plain processEvents()
        # drain would also deliver still-queued APPLICATION events the
        # finished test never wanted processed (a worker's finished signal
        # landing on the half-torn-down dialog: _on_done shows a modal /
        # touches dead children — the third shutdown-class crash, SIGABRT
        # inside image_extractor_dialog._on_done during this very drain).
        # The stale queued signals are then discarded with their object:
        # QObject's destructor drops its pending events.
        try:
            app.sendPostedEvents(None, QEvent.DeferredDelete)
        except Exception:
            pass
    except Exception:
        # Never let cleanup break a test's own teardown.
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
