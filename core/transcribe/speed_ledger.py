"""V0.6.58 — the speed ledger (Qt-free leaf, stdlib only).

THE TRIGGER (the operator's report, verbatim):
    "Look it seems there is a problem: ... [GPU] GPU: 99% util, 11.7 GB
     VRAM used ... still working — 06:15 elapsed ... Note, dragging
     video to this bat file transcribe it under 1 minute, hope it gives
     you ideas."

The V0.6.57 telemetry answered the FIRST question — the GPU provably
IS computing (99% util, VRAM full), so the run is not on the CPU and
not hung. What the log still could not answer:

  1. How long SHOULD this take? A 14:43 video at ~2.4x realtime is a
     ~6-minute run — normal for whisper-large-v3 (1.5B) on a Vulkan
     RTX 3060, but indistinguishable from "broken" without a number.
  2. Is the app slower than the owner's transcribe.bat? The app's
     [CMD] is byte-identical to the bat's command (both are
     ``transcribe-cli.exe -m <model> <wav>`` with zero extra flags —
     the bat the operator uploaded proves it), but "identical" was an
     eyeball claim, not a computed one.
  3. What would make it fast again? The upstream's own model table
     (docs/models/whisper.md) names whisper-large-v3-turbo "the best
     accuracy/speed tradeoff" (809M params, 886 MB Q8_0, WER 2.01% vs
     large-v3's 1.82%) — a 4x-smaller decoder, no rebuild required.

WHAT THIS MODULE ADDS
---------------------
  - ``parse_realtime_line`` — the CLI prints its OWN throughput figure
    at the end of every run (examples/cli/asr.cpp:
    ``"  realtime:   %.0fx (%.1f ms for %.1f s)"`` — compute-only,
    mel+encode+decode, model load excluded). One regex, stdout only.
  - A tiny JSON ledger (``~/.elixir/transcribe_speed_ledger.json``)
    that carries the last completed run's measured throughput forward
    per model, so the NEXT run can state its expectation BEFORE the
    wait instead of after it. Best-effort by contract: corrupt file,
    unwritable path, missing home — {} / None, never an exception into
    the transcription pipeline.
  - ``format_speed_line`` / ``format_done_line`` — the [SPEED] log
    lines (expectation up front, verdict at the end).
  - ``should_suggest_turbo`` — the data gate for the slow-model hint:
    a run under REALTIME_SLOW_X on a non-turbo whisper earns the
    upstream's own recommendation; fast runs and turbo models never
    see it.

Design follows the V0.6.56/V0.6.57 precedents (pipeline_log,
gpu_probe): a stdlib-only leaf the engine imports and the tests import
directly in sandboxes without PySide6.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

# The CLI's own end-of-run line (examples/cli/asr.cpp, handy-computer/
# transcribe.cpp):
#   std::printf("  realtime:   %.0fx (%.1f ms for %.1f s)\n",
#               (duration_s * 1000.0) / total_ms, total_ms, duration_s);
# Tolerant of the spacing variants printf can produce and of a missing
# leading indent; anchored on the three numbers (multiple, ms, s).
_REALTIME_RE = re.compile(
    r"realtime:\s*([0-9]+(?:\.[0-9]+)?)\s*x\s*\(\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*ms\s+for\s+"
    r"([0-9]+(?:\.[0-9]+)?)\s*s",
    re.IGNORECASE,
)

LEDGER_FILE_NAME = "transcribe_speed_ledger.json"

# A run slower than this (audio length / compute time, the CLI's own
# "realtime" figure) earns the slow-model hint. large-v3 on Vulkan
# lands around 2-4x; CUDA/turbo land 10x+. 5x splits the worlds.
REALTIME_SLOW_X = 5.0

# The slow-model hint — every number is sourced from the upstream repo
# (docs/models/whisper.md: large-v3 1.5B/1.67 GB/WER 1.82% vs turbo
# 809M/886 MB/WER 2.01%, "the best accuracy/speed tradeoff"; README +
# .github/workflows/cuda-windows.yml for the CUDA build path).
SLOW_MODEL_HINT = (
    "this model is the SLOW option on this rig, not a bug: "
    "whisper-large-v3 is the biggest Whisper (1.5B params, 1.67 GB "
    "Q8_0) and Vulkan is several times slower than CUDA on GeForce. "
    "Two proven faster paths, near-identical accuracy (WER 2.01% vs "
    "1.82% on the upstream's own table): (1) swap the model for "
    "whisper-large-v3-turbo (809M params, 886 MB Q8_0, ~4x smaller "
    "decoder) — the upstream's recommended speed/accuracy tradeoff; "
    "download from huggingface.co/handy-computer and point the Model "
    "button at it; (2) rebuild transcribe-cli.exe with the CUDA "
    "backend (the repo ships .github/workflows/cuda-windows.yml; CUDA "
    "on GeForce is several times faster than Vulkan). Option (1) "
    "needs no rebuild and is the quick win."
)


# ============================================================================
# PARSING — the CLI's own throughput figure
# ============================================================================


def parse_realtime_line(stdout: str) -> dict | None:
    """Extract the CLI's ``realtime:`` summary line from stdout.

    Returns ``{"realtime_x": float, "compute_ms": float,
    "audio_s": float}`` — the CLI's own numbers: the realtime multiple,
    the compute time in ms (mel + encode + decode, model load EXCLUDED)
    and the audio duration it was measured on. No line / garbage /
    non-positive numbers → ``None``, never an exception.
    """
    if not stdout:
        return None
    m = _REALTIME_RE.search(stdout)
    if not m:
        return None
    try:
        realtime_x = float(m.group(1))
        compute_ms = float(m.group(2))
        audio_s = float(m.group(3))
    except ValueError:
        return None
    if realtime_x <= 0 or compute_ms <= 0 or audio_s <= 0:
        return None
    return {"realtime_x": realtime_x, "compute_ms": compute_ms, "audio_s": audio_s}


# ============================================================================
# THE LEDGER — last run's measured throughput, per model
# ============================================================================


def default_ledger_path() -> Path:
    """The ledger file (``~/.elixir/transcribe_speed_ledger.json``).

    Uses the app's user-data dir when importable (honors the rebrand
    migration); ANY failure falls back to ``~/.elixir`` — the ledger is
    a cache, never a dependency.
    """
    try:
        from utils.settings import user_data_dir  # lazy: leaf stays app-free

        return user_data_dir() / LEDGER_FILE_NAME
    except Exception:
        return Path.home() / ".elixir" / LEDGER_FILE_NAME


def load_ledger(path=None) -> dict:
    """Load the ledger dict (``{model_name: entry}``). Missing file,
    corrupt JSON, non-dict payload, unwritable world → ``{}`` — never
    an exception. ``path=None`` means :func:`default_ledger_path`."""
    try:
        target = Path(path) if path is not None else default_ledger_path()
        text = target.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def last_entry(ledger: dict, model_name: str) -> dict | None:
    """The last recorded entry for ``model_name`` (None when absent)."""
    if not isinstance(ledger, dict) or not model_name:
        return None
    entry = ledger.get(model_name)
    return entry if isinstance(entry, dict) else None


def record_run(
    path=None,
    *,
    model: str,
    realtime_x: float | None = None,
    audio_s: float | None = None,
    elapsed_s: float | None = None,
    compute_ms: float | None = None,
    backend: str | None = None,
) -> dict | None:
    """Record one completed run into the ledger; returns the stored
    entry (``None`` on any failure — the ledger never breaks a
    transcription).

    ``realtime_x`` is the CLI's own compute-only figure (may be None on
    CLIs that print no summary); ``wall_x`` (audio/elapsed, model load
    included) is derived here when both inputs exist — the honest
    number for predicting the NEXT run's total wait.
    """
    if not model:
        return None
    try:
        target = Path(path) if path is not None else default_ledger_path()
        ledger = load_ledger(target)
        prev = last_entry(ledger, model) or {}
        wall_x = None
        if audio_s and elapsed_s and elapsed_s > 0:
            wall_x = audio_s / elapsed_s
        entry = {
            "model": model,
            "realtime_x": float(realtime_x) if realtime_x else None,
            "wall_x": float(wall_x) if wall_x else None,
            "audio_s": float(audio_s) if audio_s else None,
            "elapsed_s": float(elapsed_s) if elapsed_s else None,
            "compute_ms": float(compute_ms) if compute_ms else None,
            "backend": str(backend) if backend else None,
            "runs": int(prev.get("runs") or 0) + 1,
            "when": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        ledger[model] = entry
        try:
            from utils.atomic_io import atomic_write_json  # lazy: leaf stays app-free

            writer = atomic_write_json
        except Exception:
            writer = None
        target.parent.mkdir(parents=True, exist_ok=True)
        if writer is not None:
            writer(target, ledger)
        else:
            target.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        return entry
    except Exception:
        return None


def entry_realtime(entry: dict | None) -> float | None:
    """The throughput figure for an entry — the CLI's own realtime when
    present, else the wall ratio. Both absent → None (no verdict)."""
    if not isinstance(entry, dict):
        return None
    for key in ("realtime_x", "wall_x"):
        val = entry.get(key)
        if isinstance(val, (int, float)) and float(val) > 0:
            return float(val)
    return None


# ============================================================================
# FORMATTERS — the [SPEED] log lines
# ============================================================================


def _fmt_x(x: float) -> str:
    return f"{x:.1f}x" if x < 10 else f"{x:.0f}x"


def _fmt_mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def _fmt_expect(audio_s: float, realtime_x: float) -> str:
    """ "~6 min" / "~22s" — the honest wait for this audio at this
    throughput (floors at 1 so it never promises the impossible)."""
    total_s = audio_s / realtime_x if realtime_x > 0 else 0.0
    if total_s >= 60.0:
        return f"~{max(1, round(total_s / 60.0))} min"
    return f"~{max(1, round(total_s))}s"


def format_speed_line(entry: dict, audio_s: float | None = None) -> str:
    """The pre-run [SPEED] content (the engine adds the tag):

    "last run of whisper-large-v3-Q8_0.gguf: 2.4x realtime — expect
     ~6 min for 14:43 of audio"

    Prefers the CLI's own figure, falls back to the wall ratio; without
    a duration the expectation part is dropped; without any figure the
    line says so plainly (no numbers, no vibes).
    """
    model = str(entry.get("model") or "this model")
    ratio = entry_realtime(entry)
    if not ratio:
        return f"last run of {model}: no throughput figure on record"
    line = f"last run of {model}: {_fmt_x(ratio)} realtime"
    if audio_s and audio_s > 0:
        line += f" — expect {_fmt_expect(audio_s, ratio)} for {_fmt_mmss(audio_s)} of audio"
    return line


def format_done_line(
    elapsed_s: float,
    audio_s: float | None,
    realtime_x: float | None = None,
) -> str:
    """The end-of-run [SPEED] content:

    "done in 06:12 — 2.4x realtime for 14:43 of audio (the CLI's own
     figure: 2x compute-only)"

    The wall ratio includes the model reload; the CLI's figure excludes
    it — printing both explains where the difference went.
    """
    line = f"done in {_fmt_mmss(elapsed_s)}"
    if audio_s and elapsed_s and elapsed_s > 0:
        wall_x = audio_s / elapsed_s
        line += f" — {_fmt_x(wall_x)} realtime for {_fmt_mmss(audio_s)} of audio"
    if realtime_x and realtime_x > 0:
        line += f" (the CLI's own figure: {_fmt_x(realtime_x)} compute-only)"
    return line


# ============================================================================
# THE SLOW-MODEL GATE — when does the turbo hint fire?
# ============================================================================


def should_suggest_turbo(model_name: str, realtime_x: float | None) -> bool:
    """True when the run earned the slow-model hint: a measured figure
    slower than REALTIME_SLOW_X on a whisper model that is not already
    the turbo. No figure → False (never diagnose without data); turbo /
    non-whisper models → False (nothing left to suggest)."""
    if not realtime_x or float(realtime_x) <= 0:
        return False
    name = str(model_name or "").lower()
    if "whisper" not in name or "turbo" in name:
        return False
    return float(realtime_x) < REALTIME_SLOW_X
