"""V0.6.33 — the GPU-only gate source-pin tests.

THE FIX
-------
V0.6.33 (W-q2): the wizard's _on_generate_audio now checks
torch.cuda.is_available() BEFORE starting generation. If CUDA is not
available, it shows a confirmation modal:

  "VibeVoice will run on CPU at ~4 tokens/second (~34 minutes per
   line, ~100x slower than GPU). A 50-line podcast could take 28+
   HOURS. ... Do you want to proceed on CPU anyway?"

If the user clicks "No" → generation aborts. If "Yes" → proceeds
on CPU (the operator's explicit choice).

The gate is in the UI layer (the wizard), not the engine — the
engine doesn't know about Qt dialogs. The gate uses a try/except for
the torch import (torch might not be installed at all → definitely
CPU → the modal fires).

These are SOURCE-PIN tests (read the source + verify the patterns).
No QApplication needed — the patterns are verified by reading the
file, not by instantiating the view (which would segfault offscreen
with the downloaded libEGL).
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_VIEW_PATH = _project_root / "ui_qt" / "views" / "podcast_maker_view.py"


def _src() -> str:
    return _VIEW_PATH.read_text(encoding="utf-8")


# ── Source-pin tests ────────────────────────────────────────────────────────


def test_v0633_gpu_gate_exists() -> None:
    """The GPU gate code exists in the wizard view."""
    assert "GPU-ONLY GATE" in _src()


def test_v0633_gpu_gate_checks_cuda_available() -> None:
    """The gate calls torch.cuda.is_available()."""
    src = _src()
    assert "import torch as _torch_check" in src
    assert "_torch_check.cuda.is_available()" in src


def test_v0633_gpu_gate_handles_no_torch() -> None:
    """If torch isn't importable, the gate treats it as CPU (shows the modal)."""
    src = _src()
    assert "except ImportError:" in src
    assert "_cuda_ok = False" in src


def test_v0633_gpu_gate_shows_confirmation_modal() -> None:
    """The gate shows a QMessageBox.question when CUDA is not available."""
    src = _src()
    assert "QMessageBox.question" in src
    assert "No GPU Detected" in src or "CPU Generation" in src


def test_v0633_gpu_modal_warns_about_speed() -> None:
    """The modal message warns about CPU speed (~4 tokens/second, ~34 min/line)."""
    src = _src()
    assert "4 tokens" in src or "34 minutes" in src or "100x slower" in src


def test_v0633_gpu_modal_shows_fix_command() -> None:
    """The modal message shows the pip install command to fix the issue."""
    src = _src()
    assert "download.pytorch.org/whl/cu126" in src
    assert "pip install torch" in src


def test_v0633_gpu_modal_default_is_no() -> None:
    """The modal's default button is 'No' (the safe choice — don't proceed on CPU)."""
    src = _src()
    assert "QMessageBox.StandardButton.No" in src
    # The default button is the last argument to QMessageBox.question
    assert "QMessageBox.StandardButton.No," in src  # the trailing comma = default


def test_v0633_gpu_gate_aborts_on_no() -> None:
    """If the user clicks 'No', generation aborts (return without starting)."""
    src = _src()
    assert "if _reply != QMessageBox.StandardButton.Yes:" in src
    assert "return  # abort" in src


def test_v0633_gpu_gate_proceeds_on_yes() -> None:
    """If the user clicks 'Yes' (or if CUDA is available), generation proceeds."""
    src = _src()
    # After the gate, the gen_audio_btn is disabled + the worker starts.
    assert "self.gen_audio_btn.setEnabled(False)" in src
    assert "_SimpleWorker" in src


def test_v0633_gpu_gate_before_worker_starts() -> None:
    """The gate runs BEFORE the audio _SimpleWorker is created (not after)."""
    src = _src()
    gate_pos = src.find("GPU-ONLY GATE")
    # Find the _SimpleWorker AFTER the gate (there's also one in the
    # script-generation section that comes before the audio section).
    worker_pos = src.find("_SimpleWorker", gate_pos)
    assert gate_pos > 0 and worker_pos > 0
    assert gate_pos < worker_pos, "The GPU gate must come BEFORE the _SimpleWorker creation"


def test_v0633_gpu_gate_shows_torch_version_in_modal() -> None:
    """The modal shows the torch version + CUDA version so the user can diagnose."""
    src = _src()
    assert "_torch_ver" in src
    assert "_cuda_ver" in src
    assert "torch.version.cuda" in src
