"""V0.6.57 — GPU liveness probe (Qt-free leaf, stdlib only).

THE TRIGGER: the operator ran a 15-minute video through the Transcribe
Service, watched the live log go silent for 3+ minutes, saw the CPU
pinned in Task Manager and asked:

    "Why model is working on cpu? I have weak cpu and strong GPU!"

The log could not answer — no line said which DEVICE was computing.
This module is the answer: ask the GPU itself. ``nvidia-smi`` ships
with every NVIDIA driver install and reports, in one cheap query:

  - ``utilization.gpu``  — the % the GPU is busy RIGHT NOW
  - ``memory.used``      — VRAM in use (a GROWING number during model
                           load is proof of progress even at 0% util)

The probe is best-effort by contract: no nvidia-smi / not an NVIDIA
rig / a wedged driver → ``None``, NEVER an exception into the caller.
``probe_gpu_state`` takes an injectable ``runner`` so the test suite
exercises the real logic without an NVIDIA GPU in the sandbox.

Design follows the V0.6.56 ``pipeline_log`` precedent: a stdlib-only
leaf the engine imports (and the tests import directly in sandboxes
without PySide6).
"""

from __future__ import annotations

import re
import subprocess
import sys

# One row per GPU: "12, 3452" (util %, VRAM MB used). ``noheader`` keeps
# it machine-parseable, ``nounits`` strips the " %" / " MiB" suffixes.
_NVIDIA_SMI_CMD = [
    "nvidia-smi",
    "--query-gpu=utilization.gpu,memory.used",
    "--format=csv,noheader,nounits",
]

# The probe runs inside the worker thread's poll loop — it must NEVER
# hang it on a wedged driver. 2s is generous (warm nvidia-smi answers
# in ~50-150 ms) and far below the 30s probe cadence.
PROBE_TIMEOUT_S = 2.0

# util <= this is "idle" — a GPU idle for minutes while the CLI works
# is the honest "check the backend/driver" signal.
GPU_IDLE_PCT = 5

# ``--list-devices`` only initializes the compute backends (a Vulkan
# instance + device enumeration — a second or two); no model, no audio.
# 15s is generous even for a wedged driver; the probe must never hang
# the worker thread.
LIST_DEVICES_TIMEOUT_S = 15.0

# "12, 3452" — two ints, optional whitespace around the comma.
_CSV_ROW_RE = re.compile(r"^\s*(\d{1,3})\s*,\s*(\d{1,9})\s*$")

# --list-devices output (examples/cli/main.cpp, handy-computer/transcribe.cpp):
#   "2 compute device(s):"
#   "  [0] NVIDIA GeForce RTX 3060"
#   "      name=NVIDIA GeForce RTX 3060  kind=vulkan  type=gpu  id=..."
#   "      memory: 12.00 GiB total, 10.53 GiB free"
_DEVICES_HEADER_RE = re.compile(r"^(\d+)\s+compute device\(s\):")
_DEVICE_LINE_RE = re.compile(r"^\s*\[(\d+)\]\s+(.*)$")
# name is lazy (it can contain spaces); kind/type/id are single tokens.
_DEVICE_META_RE = re.compile(r"name=(.*?)\s+kind=(\S+)\s+type=(\S+)(?:\s+id=(.*))?$")
_DEVICE_MEM_RE = re.compile(r"memory:\s*([\d.]+)\s*GiB total,\s*([\d.]+)\s*GiB free")

# Device types that mean "not the CPU" (main.cpp: cpu | gpu | igpu | accel).
_GPU_TYPES = ("gpu", "igpu", "accel")


def parse_nvidia_smi_output(text: str) -> dict | None:
    """Parse nvidia-smi CSV output into ``{"util_pct": int,
    "mem_used_mb": int}``.

    Multi-GPU rigs print one row per GPU — the FIRST row is the one
    doing the whisper compute (device 0, the ggml-vulkan default).
    Anything that is not a clean two-int row (driver error text,
    ``[N/A]``, empty output) is ``None`` — never an exception.
    """
    if not text:
        return None
    for line in text.splitlines():
        m = _CSV_ROW_RE.match(line)
        if m:
            return {
                "util_pct": int(m.group(1)),
                "mem_used_mb": int(m.group(2)),
            }
    return None


def _default_runner(cmd: list[str], timeout_s: float) -> str | None:
    """Run the query with subprocess; best-effort, returns stdout text
    or ``None`` on any failure (missing binary, timeout, nonzero exit)."""
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout or ""


def probe_gpu_state(runner=None, timeout_s: float = PROBE_TIMEOUT_S) -> dict | None:
    """Query the GPU's live state, best-effort.

    Args:
        runner: injectable ``runner(cmd, timeout_s) -> str | None`` for
            the test suite (the sandbox has no NVIDIA GPU). ``None``
            uses the real :func:`_default_runner`.
        timeout_s: hard cap on the nvidia-smi call.

    Returns ``{"util_pct": int, "mem_used_mb": int}`` or ``None`` when
    the state cannot be determined (no nvidia-smi / not NVIDIA / wedged
    driver / unparseable output). ``None`` is a legitimate answer, not
    an error — callers log ONE "unavailable" line and move on.
    """
    run = runner or _default_runner
    try:
        stdout = run(list(_NVIDIA_SMI_CMD), timeout_s)
    except Exception:
        return None
    return parse_nvidia_smi_output(stdout or "")


def _fmt_vram(mem_used_mb: int) -> str:
    if mem_used_mb >= 1024:
        return f"{mem_used_mb / 1024:.1f} GB"
    return f"{mem_used_mb} MB"


def format_gpu_line(state: dict | None) -> str:
    """Render the probe state as ONE log line.

    - a live state: ``"GPU: 97% util, 3.3 GB VRAM used"`` (+" (idle)"
      when util is at/below :data:`GPU_IDLE_PCT` — the CPU-fallback
      suspect spelled out);
    - ``None``: the honest "cannot verify" line.

    The line carries NO log prefix — the engine adds ``"  [GPU] "``
    like every other provenance-tagged line.
    """
    if not state:
        return (
            "GPU probe unavailable (no nvidia-smi / not an NVIDIA rig) — "
            "CPU-vs-GPU cannot be verified from the app"
        )
    util = state.get("util_pct")
    mem = state.get("mem_used_mb")
    if util is None or mem is None:
        return (
            "GPU probe unavailable (no nvidia-smi / not an NVIDIA rig) — "
            "CPU-vs-GPU cannot be verified from the app"
        )
    line = f"GPU: {util}% util, {_fmt_vram(int(mem))} VRAM used"
    if util <= GPU_IDLE_PCT:
        line += " (idle — sustained 0% while the CLI works points at CPU/fallback)"
    return line


# ── the --list-devices pre-flight (V0.6.57) ─────────────────────────────────
#
# The upstream CLI (handy-computer/transcribe.cpp, examples/cli/main.cpp)
# supports ``--list-devices``: it registers every compute backend compiled
# INTO the exe and prints each device — no model load, no audio, seconds.
# That is the definitive answer to "why is it on CPU?": a plain
# ``cmake -B build`` on Windows builds CPU-ONLY (Vulkan needs
# -DTRANSCRIBE_VULKAN=ON), and the CLI's default ``auto`` backend then has
# no GPU to select — silently.


def parse_list_devices_output(text: str) -> dict | None:
    """Parse ``--list-devices`` stdout into a device report.

    Returns ``{"device_count": int, "devices": [block, ...], "gpu": block
    | None}`` where a block is ``{"index": int, "description": str,
    "kind": str, "type": str, "memory_total_gib": float,
    "memory_free_gib": float}`` (memory keys omitted when unparsed).
    ``gpu`` is the FIRST device whose ``type`` is gpu/igpu/accel.
    Anything without the ``"N compute device(s):"`` header is ``None``
    (an exe predating the flag, a hard failure, garbage).
    """
    if not text:
        return None
    header: int | None = None
    blocks: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        if header is None:
            m = _DEVICES_HEADER_RE.match(line.strip())
            if m:
                header = int(m.group(1))
            continue
        dm = _DEVICE_LINE_RE.match(line)
        if dm:
            current = {"index": int(dm.group(1)), "description": dm.group(2).strip()}
            blocks.append(current)
            continue
        if current is None:
            continue
        mm = _DEVICE_META_RE.search(line)
        if mm:
            current["name"] = mm.group(1).strip()
            current["kind"] = mm.group(2)
            current["type"] = mm.group(3)
            continue
        mem = _DEVICE_MEM_RE.search(line)
        if mem:
            current["memory_total_gib"] = float(mem.group(1))
            current["memory_free_gib"] = float(mem.group(2))
    if header is None:
        return None
    gpu = next(
        (b for b in blocks if str(b.get("type", "")).lower() in _GPU_TYPES),
        None,
    )
    return {"device_count": header, "devices": blocks, "gpu": gpu}


def probe_cli_devices(
    exe_path, runner=None, timeout_s: float = LIST_DEVICES_TIMEOUT_S
) -> dict | None:
    """Run ``<exe> --list-devices`` and parse the report, best-effort.

    Same contract as :func:`probe_gpu_state`: ``None`` means "cannot
    determine" (exe predates the flag / failed / unparseable) — callers
    log ONE line and keep the run going.
    """
    run = runner or _default_runner
    try:
        stdout = run([str(exe_path), "--list-devices"], timeout_s)
    except Exception:
        return None
    return parse_list_devices_output(stdout or "")


def format_devices_line(state: dict | None) -> str:
    """Render the pre-flight device report as ONE log line.

    - a GPU is registered: which one, its backend kind, free VRAM;
    - only CPU devices: the plain truth — this exe will compute on CPU;
    - ``None``: the exe predates ``--list-devices`` (cannot determine).
    """
    if not state:
        return "device listing unavailable (this exe predates --list-devices)"
    gpu = state.get("gpu")
    if not gpu:
        n = state.get("device_count", "?")
        return (
            f"NO GPU device registered ({n} device(s), all CPU) — this "
            "transcribe-cli.exe will compute on CPU"
        )
    kind = gpu.get("kind") or "gpu"
    desc = gpu.get("description") or gpu.get("name") or "GPU"
    free = gpu.get("memory_free_gib")
    mem = f", {free:.1f} GiB free" if isinstance(free, (int, float)) else ""
    return (
        f"GPU device registered: [{gpu.get('index', 0)}] {desc} "
        f"({kind}{mem}) — the CLI auto-selects it"
    )
