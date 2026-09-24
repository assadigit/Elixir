"""V8.1.0: Hardware monitor — GPU/CPU/RAM monitoring during conversion.

Uses ``nvidia-smi`` (via subprocess) for NVIDIA GPU stats and ``psutil``
for CPU + RAM.  Runs in a background thread, polls every few seconds, and
emits warnings when thresholds are exceeded.

The monitor is non-blocking and read-only — it never throttles the
hardware directly (that's the OS/driver's job).  It just provides
visibility so the user knows if their RTX 3060 is hitting 90°C during a
6-hour conversion.

V10.1.3: Card-specific thermal profiles.  The monitor now detects the GPU
model name from nvidia-smi and applies thresholds appropriate to that
card's cooler quality.  The user's Zotac RTX 3060 Twin Edge OC is a
budget-tier card with known hotspot issues (core 84°C → hotspot 100°C+),
so it gets a conservative profile (85°C critical, not 88°C).  Premium
cards (ASUS TUF, MSI Gaming X) keep the standard 88°C profile.  See
``GpuThermalProfile`` below.

Thresholds (per-card profile, user can override via settings):
  - Zotac RTX 3060 Twin Edge OC (detected):
      warning: 78°C  (5°C below throttle — react early, protect hotspot)
      caution: 82°C  (at throttle — reduce workers / add cooldown)
      critical: 85°C (Zotac danger zone — hotspot ~100°C+, force pause)
  - Generic NVIDIA (default if card not specifically profiled):
      warning: 83°C, critical: 88°C
  - GPU utilization sustained >95% for >5 min: log info (not a warning)
  - CPU temp: not directly available via psutil on all platforms; we
    monitor CPU utilization instead (>90% sustained = info)
  - RAM usage >90%: warning (risk of swap/OOM)

nvidia-smi query format:
  ``nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,
  memory.total,fan.speed --format=csv,noheader,nounits``
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ════════════════════════════════════════════════════════════════════════════
# V10.1.3: Card-specific thermal profiles
# ════════════════════════════════════════════════════════════════════════════
#
# Research basis (2026-07-22):
#
# The user's card is a Zotac RTX 3060 Twin Edge OC 12GB.  This is a
# budget-tier cooler with known thermal issues:
#
#   - TechPowerUp: Zotac 3060 Ti Twin Edge runs 72°C under load (decent
#     but not great; premium cards run 65-68°C).
#   - Linus Tech Tips forum: "My Zotac RTX 3060 Twin Edge constantly
#     overheats — hotspot reaches 94°C, crashes at 79°C core."
#   - Reddit r/ZOTAC: "hotspot reaches 95.5 degrees" on a 3060 Twin Edge.
#   - Reddit r/pcmasterrace: "hotspot of ~100°C after 30-40 mins while
#     overall temp was around 84°C."
#   - PCPartPicker: "Running temps ~75°C (fine) but hotspot hitting 98°C."
#   - Tom's Hardware (3-year owner): temps increased 74°C → 80°C over 3
#     years (factory thermal paste degrades faster on Zotac).
#
# KEY INSIGHT: nvidia-smi's "temperature.gpu" is the CORE temp, not the
# HOTSPOT temp.  The hotspot (hottest point on the die) runs 15-20°C
# hotter on Zotac cards due to thinner thermal pads and inconsistent
# contact.  A core reading of 84°C on a Zotac = hotspot ~100-104°C,
# which is where VRAM degradation accelerates.
#
# The user explicitly stated: "I can't afford to buy a new VGA for years"
# and "zotac might be less robust."  The research confirms this.  So we
# apply a CONSERVATIVE profile for Zotac cards:
#
#   - 78°C warning  (5°C below NVIDIA's 83°C throttle — react early)
#   - 82°C caution  (at throttle — reduce load)
#   - 85°C critical (Zotac hotspot ~100°C+ — force pause to protect VRAM)
#
# For premium cards with better coolers (ASUS TUF, MSI Gaming X, etc.),
# we keep the standard 83°C / 88°C profile.
#
# The profile is auto-selected by matching the GPU name returned by
# nvidia-smi.  The user can override via settings (hardware.gpu_profile).


@dataclass
class GpuThermalProfile:
    """Thermal thresholds for a specific GPU model.

    Attributes:
        name: human-readable profile name.
        warning_c: log a WARNING at this temp (react early).
        caution_c: log a CAUTION + recommend reducing workers.
        critical_c: log CRITICAL + trigger auto-pause.
        optimal_c: target temp for indefinite sustained load.
        hotspot_delta_c: estimated core→hotspot delta (for logging).
        sustained_pause_interval_min: if >0, recommend a cool-down pause
            every N minutes even if temps are OK (thermal cycling
            protection for budget cards with degrading paste).
        emergency_mode: V10.1.4 — when True, the card has known VRAM
            thermal issues and the profile uses aggressively conservative
            thresholds.  Also forces max_safe_workers=1 (halves VRAM
            bandwidth load — critical for memory-bound AI inference
            workloads on cards with marginal VRAM cooling).
        max_safe_workers: V10.1.4 — the maximum number of parallel
            summarization workers safe for this card.  Budget cards with
            VRAM thermal issues should use 1 (not 2) because LLM inference
            is a memory-bandwidth-bound workload: 2 workers = 2x VRAM
            bandwidth = 2x VRAM heat.  Capping at 1 gives the VRAM chips
            brief rest periods between LLM calls, reducing sustained
            thermal stress.
        notes: human-readable explanation shown in the UI.
    """

    name: str
    warning_c: int = 78
    caution_c: int = 82
    critical_c: int = 85
    optimal_c: int = 72
    hotspot_delta_c: int = 18  # Zotac typical; premium cards ~10-12
    sustained_pause_interval_min: int = 30  # 0 = no periodic pause
    emergency_mode: bool = False  # V10.1.4
    max_safe_workers: int = 2  # V10.1.4
    notes: str = ""


# ── Built-in profiles ─────────────────────────────────────────────────────

# The default profile — used for unknown cards and premium cards with
# good coolers.  Matches the old V8.1.0 thresholds.
_PROFILE_DEFAULT = GpuThermalProfile(
    name="Generic NVIDIA (standard cooler)",
    warning_c=83,
    caution_c=85,
    critical_c=88,
    optimal_c=75,
    hotspot_delta_c=12,
    sustained_pause_interval_min=0,  # no periodic pause needed
    notes="Standard thermal profile. Safe for cards with adequate cooling.",
)

# The user's card — Zotac RTX 3060 Twin Edge OC 12GB.
# V10.1.4: EMERGENCY thresholds.  The user reported visual artifacts (red
# dots/lines on the monitor) during a 6-8 hour app summarization session,
# but NOT during 6-8 hours of Far Cry 6.  This is the classic signature
# of VRAM thermal errors under memory-bandwidth-bound workload:
#
#   - Far Cry 6 = compute-bound: GPU core does the work, VRAM bandwidth
#     ~30-50%, VRAM chips get micro-breaks between frames.  VRAM temp
#     ~85-90°C — safe.
#   - LLM inference = memory-bandwidth-bound: every attention head reads
#     KV cache, every FFN reads weights, VRAM bandwidth ~100% sustained
#     for hours.  VRAM temp climbs to 100-105°C — bit errors → red dots.
#
# At 87°C core (what the user's log showed), the Zotac's VRAM was likely
# at 100-105°C.  GDDR6's safe limit is ~95°C.  Above that, bit errors
# start and sustained operation degrades the memory cells.
#
# EMERGENCY thresholds (V10.1.4):
#   - 72°C warning  (was 78°C in V10.1.3)
#   - 76°C caution  (was 82°C)
#   - 80°C critical (was 85°C) — at 80°C core, VRAM is ~95°C (the safe
#     ceiling for GDDR6)
#   - max_safe_workers=1 (was 2) — halves VRAM bandwidth, the single
#     most effective software change for memory-bound workloads
_PROFILE_ZOTAC_3060_TWIN_EDGE = GpuThermalProfile(
    name="Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)",
    warning_c=72,
    caution_c=76,
    critical_c=80,
    optimal_c=68,
    hotspot_delta_c=18,
    sustained_pause_interval_min=20,  # V10.1.4: 20 min (was 30) — more frequent rests
    emergency_mode=True,
    max_safe_workers=1,
    notes=(
        "EMERGENCY profile for Zotac RTX 3060 Twin Edge OC.  Activated "
        "because the user reported visual artifacts (red dots/lines) "
        "during sustained AI inference — a VRAM thermal error symptom. "
        "This card's budget VRAM thermal pads cannot handle sustained "
        "memory-bandwidth-bound workloads (like LLM inference) at the "
        "temperatures that gaming (compute-bound) workloads tolerate. "
        "Thresholds lowered to keep VRAM below 95°C (GDDR6 safe limit). "
        "max_workers forced to 1 to halve VRAM bandwidth load. "
        "If artifacts persist even at these thresholds, STOP using the "
        "app on this card until the VRAM thermal pads are physically "
        "replaced — the hardware is the root cause, not the software."
    ),
)

# ── Profile registry: (name_pattern → profile) ────────────────────────────
# Patterns are matched case-insensitive against the GPU name from nvidia-smi.
# First match wins (so put more specific patterns first).
_PROFILE_PATTERNS: list[tuple] = [
    # Zotac RTX 3060 Twin Edge (the user's card) — match "ZOTAC" + "3060" + "Twin Edge"
    (r"zotac.*3060.*twin\s*edge", _PROFILE_ZOTAC_3060_TWIN_EDGE),
    # Other Zotac 3060 variants (non-Twin-Edge) — also conservative
    (r"zotac.*3060", _PROFILE_ZOTAC_3060_TWIN_EDGE),
    # Zotac 3060 Ti / 3070 Twin Edge — same cooler design, same profile
    (r"zotac.*30[67]0.*twin\s*edge", _PROFILE_ZOTAC_3060_TWIN_EDGE),
]


def detect_gpu_profile(gpu_name: str) -> GpuThermalProfile:
    """Auto-detect the thermal profile from the GPU name.

    Args:
        gpu_name: the GPU name returned by nvidia-smi (e.g.
            "ZOTAC GeForce RTX 3060 Twin Edge OC").

    Returns:
        The matching GpuThermalProfile, or the default profile if no
        specific match is found.
    """
    if not gpu_name:
        return _PROFILE_DEFAULT
    import re

    name_lower = gpu_name.lower()
    for pattern, profile in _PROFILE_PATTERNS:
        if re.search(pattern, name_lower):
            return profile
    return _PROFILE_DEFAULT


def detect_gpu_profile_from_system() -> tuple:
    """V10.1.4: One-shot detection of the GPU thermal profile.

    Does a single nvidia-smi query to get the GPU name, then returns
    the matching profile.  Used by the converter BEFORE summarization
    starts so it can cap max_workers based on the card's
    max_safe_workers field.

    V10.1.6: checks the manual override setting first.  Some Zotac cards
    report the generic NVIDIA name ("NVIDIA GeForce RTX 3060") instead
    of the board partner name ("ZOTAC GeForce RTX 3060 Twin Edge OC"),
    so auto-detection fails.  The override lets the user force the
    Zotac emergency profile.

    Returns:
        (gpu_name: str, profile: GpuThermalProfile)
        gpu_name is "" if nvidia-smi is unavailable.
        profile is _PROFILE_DEFAULT if no card-specific match.
    """
    import shutil
    import subprocess
    import sys

    # V10.1.6: check manual override first
    try:
        from utils.settings import Settings

        _s = Settings()
        _override = _s.get("hardware.gpu_profile_override", "auto")
        if _override and _override != "auto":
            # Map override keys to profiles
            _override_map = {
                "zotac_3060": _PROFILE_ZOTAC_3060_TWIN_EDGE,
                "zotac_3060_ti": _PROFILE_ZOTAC_3060_TWIN_EDGE,
                "zotac_3070": _PROFILE_ZOTAC_3060_TWIN_EDGE,
                "generic": _PROFILE_DEFAULT,
            }
            _profile = _override_map.get(_override, _PROFILE_DEFAULT)
            # Still read the GPU name for logging
            _gpu_name = ""
            nvidia_smi = shutil.which("nvidia-smi")
            if not nvidia_smi and sys.platform == "win32":
                from pathlib import Path

                for candidate in [
                    r"C:\Windows\System32\nvidia-smi.exe",
                    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                ]:
                    if Path(candidate).exists():
                        nvidia_smi = candidate
                        break
            if nvidia_smi:
                try:
                    result = subprocess.run(
                        [nvidia_smi, "--query-gpu=name", "--format=csv,noheader,nounits"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        _gpu_name = result.stdout.strip().split(", ")[0].strip()
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return (_gpu_name or f"(override: {_override})", _profile)
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # Auto-detection (original V10.1.4 path)
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi and sys.platform == "win32":
        from pathlib import Path

        for candidate in [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]:
            if Path(candidate).exists():
                nvidia_smi = candidate
                break
    if not nvidia_smi:
        return ("", _PROFILE_DEFAULT)
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split(", ")[0].strip()
            return (gpu_name, detect_gpu_profile(gpu_name))
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
    return ("", _PROFILE_DEFAULT)


# ── Backward-compatible module-level constants ────────────────────────────
# GPU_TEMP_WARNING is a legacy module-level default; the HardwareMonitor
# class uses the per-instance profile (which may differ).  The dead
# GPU_TEMP_CRITICAL / CPU_SUSTAINED_HIGH_SEC constants (zero refs) were
# removed in the V0.4.25 Phase-4 dead-code audit.
GPU_TEMP_WARNING = _PROFILE_DEFAULT.warning_c
RAM_PCT_WARNING = 90  # % — log a warning (swap/OOM risk)


@dataclass
class HardwareSnapshot:
    """A point-in-time snapshot of hardware stats."""

    timestamp: float = 0.0
    # GPU (None if nvidia-smi unavailable)
    gpu_name: str | None = None  # V10.1.3: card model for profile detection
    gpu_temp_c: int | None = None
    gpu_vram_temp_c: int | None = None  # V10.1.5: real VRAM temp (temperature.memory)
    gpu_utilization_pct: int | None = None
    gpu_memory_used_mb: int | None = None
    gpu_memory_total_mb: int | None = None
    gpu_fan_speed_pct: int | None = None
    # CPU (None if psutil unavailable)
    cpu_utilization_pct: float | None = None
    # RAM
    ram_used_gb: float | None = None
    ram_total_gb: float | None = None
    ram_pct: float | None = None

    def is_empty(self) -> bool:
        """True if no stats could be collected (no GPU + no psutil)."""
        return self.gpu_temp_c is None and self.cpu_utilization_pct is None and self.ram_pct is None

    def format_compact(self) -> str:
        """One-line compact summary for the UI status bar."""
        parts = []
        if self.gpu_temp_c is not None:
            # V10.1.5: show VRAM temp if available, else estimated hotspot
            if self.gpu_vram_temp_c is not None:
                parts.append(
                    f"GPU {self.gpu_temp_c}°C / VRAM {self.gpu_vram_temp_c}°C / {self.gpu_utilization_pct}%"
                )
            else:
                parts.append(f"GPU {self.gpu_temp_c}°C / {self.gpu_utilization_pct}%")
            if self.gpu_memory_total_mb:
                parts.append(f"VRAM {self.gpu_memory_used_mb}/{self.gpu_memory_total_mb}MB")
        if self.cpu_utilization_pct is not None:
            parts.append(f"CPU {self.cpu_utilization_pct:.0f}%")
        if self.ram_pct is not None:
            parts.append(f"RAM {self.ram_pct:.0f}%")
        return " · ".join(parts) if parts else "(no hardware stats)"


# ── (Thresholds are now per-card — see GpuThermalProfile above) ──────────


class HardwareMonitor:
    """Background hardware monitor.

    Polls nvidia-smi + psutil on a background thread.  Thread-safe: the
    snapshot is updated under a lock.  The UI can read the latest snapshot
    via :meth:`get_snapshot` from any thread.

    Usage::

        monitor = HardwareMonitor(log_callback=log, interval_sec=5)
        monitor.start()
        # ... during conversion ...
        snap = monitor.get_snapshot()
        monitor.stop()
    """

    def __init__(
        self,
        log_callback: LogFn | None = None,
        interval_sec: float = 5.0,
        auto_pause_callback: Callable[[], None] | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.interval = interval_sec
        # V9.0.0 E3: callback invoked when GPU temp reaches critical — the
        # wizard uses this to pause the conversion (set cancel_event).
        self._auto_pause_callback = auto_pause_callback
        self._auto_pause_triggered = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._snapshot: HardwareSnapshot = HardwareSnapshot()
        self._nvidia_smi_path = self._find_nvidia_smi()
        self._psutil_available = self._check_psutil()
        # pyNVML backend (preferred — no subprocess overhead).
        # Initialized lazily on first query.
        self._nvml_initialized = False
        self._nvml_available = False
        self._nvml_handle = None
        # Track sustained high utilization
        self._cpu_high_since: float | None = None
        self._gpu_high_since: float | None = None
        # Track if we've already warned (avoid spamming)
        self._gpu_temp_warned = False
        self._gpu_temp_caution_warned = False  # V10.1.3: new caution tier
        self._gpu_temp_critical_warned = False
        self._ram_warned = False
        # V10.1.3: card-specific thermal profile.  Starts as default; gets
        # updated to the detected card's profile on the first successful
        # nvidia-smi query (which returns the GPU name).
        self._profile: GpuThermalProfile = _PROFILE_DEFAULT
        self._profile_logged = False  # log the detected profile once
        # V10.1.3: sustained-load cool-down tracking.  For cards with
        # sustained_pause_interval_min > 0 (like Zotac), recommend a
        # cool-down pause every N minutes to reduce thermal cycling.
        self._sustained_load_start: float | None = None
        self._last_cooldown_time: float | None = None

    # ── pyNVML (preferred backend — no subprocess overhead) ─────────────

    def _init_nvml(self) -> bool:
        """Initialize pyNVML. Returns True if available."""
        if self._nvml_initialized:
            return self._nvml_available
        self._nvml_initialized = True
        # V18.20.2.0 (SWOT A10): pre-bind so the NVMLError guard below can
        # never hit an unbound local (defensive — ``import`` only re-binds
        # on success, so a broken install that raises a non-ImportError on
        # import leaves ``pynvml`` as None instead of raising NameError).
        pynvml = None
        try:
            import pynvml  # noqa: F811 — re-binds the local on success

            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_available = True
        except ImportError:
            pass  # pyNVML not installed — fall back to nvidia-smi
        except Exception as e:
            # V18.20.2.0 (SWOT A10): this clause was an unreachable duplicate
            # ``except ImportError:`` — the intended handler is for
            # ``pynvml.NVMLError`` raised by nvmlInit() (no NVIDIA driver,
            # library/driver version mismatch, etc.).  Swallow NVMLError and
            # fall back to nvidia-smi; anything else is logged at DEBUG and
            # also falls back (the monitor must never crash the poll loop).
            if pynvml is not None and isinstance(e, pynvml.NVMLError):
                pass  # NVML init failed (no NVIDIA driver, etc.)
            else:
                logger.debug(
                    "pyNVML init failed (%s: %s) — falling back to nvidia-smi",
                    type(e).__name__,
                    e,
                )
        return self._nvml_available

    def _query_gpu_nvml(self) -> dict:
        """Query GPU stats via pyNVML (preferred — no subprocess)."""
        if not self._init_nvml():
            return {}
        try:
            import pynvml

            h = self._nvml_handle
            # GPU name
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            # Core temp
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            gpu_util = util.gpu
            # Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            # Fan speed
            try:
                fan = pynvml.nvmlDeviceGetFanSpeed(h)
            except Exception as _e:
                fan = 0
            # VRAM temp (RTX 30+ only)
            vram_temp = None
            try:
                vram_temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_MEMORY)
            except Exception as _e:
                logger.debug(
                    "ignored %s: %s", type(_e).__name__, _e
                )  # not all cards expose this sensor
            return {
                "gpu_name": name,
                "gpu_temp_c": temp,
                "gpu_vram_temp_c": vram_temp,
                "gpu_utilization_pct": gpu_util,
                "gpu_memory_used_mb": mem.used // (1024 * 1024),
                "gpu_memory_total_mb": mem.total // (1024 * 1024),
                "gpu_fan_speed_pct": fan,
            }
        except Exception as _e:
            return {}

    # ── nvidia-smi (fallback backend) ───────────────────────────────────

    @staticmethod
    def _find_nvidia_smi() -> str | None:
        """Find the nvidia-smi binary on the system.

        On Windows it's typically at
        ``C:\\Windows\\System32\\nvidia-smi.exe`` or
        ``C:\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe``.
        On Linux it's usually on PATH.
        """
        import shutil
        import sys

        # Check PATH first
        path = shutil.which("nvidia-smi")
        if path:
            return path
        # Windows fallback locations
        if sys.platform == "win32":
            for candidate in [
                r"C:\Windows\System32\nvidia-smi.exe",
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                r"C:\Program Files\NVIDIA Corporation\nvidia-smi\nvidia-smi.exe",
            ]:
                from pathlib import Path

                if Path(candidate).exists():
                    return candidate
        return None

    def _query_gpu(self) -> dict:
        """Query nvidia-smi for GPU stats. Returns empty dict on failure.

        V10.1.3: now also queries the GPU name (first field) so we can
        auto-detect the card model and select the right thermal profile.
        V10.1.5: now also queries temperature.memory (VRAM temp) — the
        REAL memory junction temperature, available on RTX 30-series+
        with recent drivers.  This is the critical sensor for detecting
        VRAM thermal errors (the red dots/lines the user saw).
        """
        if not self._nvidia_smi_path:
            return {}
        try:
            result = subprocess.run(
                [
                    self._nvidia_smi_path,
                    # V10.1.5: added temperature.memory for VRAM temp
                    "--query-gpu=name,temperature.gpu,temperature.memory,utilization.gpu,memory.used,memory.total,fan.speed",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            # Parse: "NVIDIA GeForce RTX 3060, 65, 58, 45, 2048, 12288, 35"
            # temperature.memory may return "N/A" on some cards — handle it
            raw = result.stdout.strip()
            parts = raw.split(", ")
            if len(parts) >= 7:
                gpu_name = parts[0].strip()
                nums = parts[-6:]  # last 6 are the numbers
                # VRAM temp may be "N/A" or "[N/A]" on unsupported cards
                vram_raw = nums[1].strip()
                vram_temp = None
                if vram_raw and vram_raw.upper() not in ("N/A", "[N/A]", ""):
                    try:
                        vram_temp = int(vram_raw)
                    except ValueError:
                        vram_temp = None
                return {
                    "gpu_name": gpu_name,
                    "gpu_temp_c": int(nums[0]),
                    "gpu_vram_temp_c": vram_temp,  # V10.1.5: may be None
                    "gpu_utilization_pct": int(nums[2]),
                    "gpu_memory_used_mb": int(nums[3]),
                    "gpu_memory_total_mb": int(nums[4]),
                    "gpu_fan_speed_pct": int(nums[5]),
                }
            elif len(parts) >= 6:
                # No VRAM temp field — fall back to 6 fields without it
                gpu_name = parts[0].strip()
                nums = parts[-5:]
                return {
                    "gpu_name": gpu_name,
                    "gpu_temp_c": int(nums[0]),
                    "gpu_utilization_pct": int(nums[1]),
                    "gpu_memory_used_mb": int(nums[2]),
                    "gpu_memory_total_mb": int(nums[3]),
                    "gpu_fan_speed_pct": int(nums[4]),
                }
            elif len(parts) == 5:
                return {
                    "gpu_temp_c": int(parts[0]),
                    "gpu_utilization_pct": int(parts[1]),
                    "gpu_memory_used_mb": int(parts[2]),
                    "gpu_memory_total_mb": int(parts[3]),
                    "gpu_fan_speed_pct": int(parts[4]),
                }
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return {}

    # ── psutil ──────────────────────────────────────────────────────────

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil  # noqa: F401

            return True
        except ImportError:
            return False

    def _query_cpu_ram(self) -> dict:
        """Query CPU + RAM via psutil. Returns empty dict on failure."""
        if not self._psutil_available:
            return {}
        try:
            import psutil

            ram = psutil.virtual_memory()
            return {
                "cpu_utilization_pct": psutil.cpu_percent(interval=0.5),
                "ram_used_gb": ram.used / (1024**3),
                "ram_total_gb": ram.total / (1024**3),
                "ram_pct": ram.percent,
            }
        except ImportError:
            return {}

    # ── polling loop ────────────────────────────────────────────────────

    def _poll_once(self) -> HardwareSnapshot:
        """Collect one snapshot. Tries pyNVML first, falls back to nvidia-smi."""
        snap = HardwareSnapshot(timestamp=time.time())
        # pyNVML preferred (no subprocess overhead)
        gpu_data = self._query_gpu_nvml()
        if not gpu_data:
            # Fallback: nvidia-smi subprocess
            gpu_data = self._query_gpu()
        snap.__dict__.update(gpu_data)
        snap.__dict__.update(self._query_cpu_ram())
        # V10.1.3: detect / update the thermal profile once we have a GPU name
        if snap.gpu_name and not self._profile_logged:
            self._profile = detect_gpu_profile(snap.gpu_name)
            self._profile_logged = True
            self.log(
                f"  🎯 GPU detected: {snap.gpu_name}",
                "INFO",
            )
            self.log(
                f"  🌡️ Thermal profile: {self._profile.name} — "
                f"warning {self._profile.warning_c}°C, "
                f"caution {self._profile.caution_c}°C, "
                f"critical {self._profile.critical_c}°C "
                f"(hotspot delta ~{self._profile.hotspot_delta_c}°C)",
                "INFO",
            )
            if self._profile.sustained_pause_interval_min > 0:
                self.log(
                    f"  ⏱️ This card benefits from a {self._profile.sustained_pause_interval_min}-min "
                    f"cool-down cycle to reduce thermal-cycling stress on the thermal paste.",
                    "INFO",
                )
            # V10.1.4: emergency mode warning for cards with VRAM thermal issues
            if self._profile.emergency_mode:
                self.log(
                    f"  🚨 EMERGENCY MODE: This card has known VRAM thermal issues. "
                    f"AI inference is a memory-bandwidth-bound workload that stresses "
                    f"VRAM far more than gaming.  max_workers capped at "
                    f"{self._profile.max_safe_workers}.  If you see visual artifacts "
                    f"(red dots/lines on your monitor), STOP IMMEDIATELY — the VRAM "
                    f"is overheating and continued use will cause permanent damage.",
                    "WARNING",
                )
        return snap

    def _check_thresholds(self, snap: HardwareSnapshot) -> None:
        """Log warnings if thresholds are exceeded (with anti-spam).

        V10.1.3: uses the per-instance ``self._profile`` (auto-detected from
        the GPU name) instead of the old global constants.  Adds a CAUTION
        tier between warning and critical, and logs the estimated hotspot
        temperature (core + delta) so the user understands the real thermal
        stress on their card.

        V10.1.5: when ``gpu_vram_temp_c`` is available (RTX 30-series+),
        uses the REAL VRAM temp instead of the core+delta estimate.  Also
        adds a dedicated VRAM critical check — if the VRAM temp exceeds
        100°C, auto-pauses immediately regardless of the core temp.
        """
        now = snap.timestamp
        p = self._profile  # shorthand

        # V10.1.5: determine which temp to use for the "hotspot" display.
        # If we have the real VRAM temp, use it.  Otherwise, estimate.
        if snap.gpu_vram_temp_c is not None:
            vram_display = snap.gpu_vram_temp_c
            vram_source = "VRAM"
        else:
            vram_display = snap.gpu_temp_c + p.hotspot_delta_c if snap.gpu_temp_c else None
            vram_source = "est."

        # V10.1.5: dedicated VRAM temp critical check.
        # If the real VRAM temp exceeds 100°C, auto-pause immediately —
        # this is the temperature where GDDR6 bit errors start and the
        # user sees red dots/lines on the monitor.
        if snap.gpu_vram_temp_c is not None and snap.gpu_vram_temp_c >= 100:
            if not self._gpu_temp_critical_warned:
                self.log(
                    f"  🔴 VRAM temperature CRITICAL: {snap.gpu_vram_temp_c}°C! "
                    f"This is above GDDR6's safe limit (95°C) — bit errors are "
                    f"likely (this is what causes the red dots/lines on your "
                    f"monitor). Force-pausing to protect the VRAM from "
                    f"permanent damage. (profile: {p.name})",
                    "ERROR",
                )
                self._gpu_temp_critical_warned = True
                if self._auto_pause_callback and not self._auto_pause_triggered:
                    self._auto_pause_triggered = True
                    self.log(
                        f"  ⏸️ Auto-pausing: VRAM at {snap.gpu_vram_temp_c}°C "
                        f"is in the danger zone.",
                        "ERROR",
                    )
                    try:
                        self._auto_pause_callback()
                    except Exception as _e:
                        logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return  # skip the core-temp check — VRAM critical is more urgent

        # GPU core temperature — three tiers: warning → caution → critical
        if snap.gpu_temp_c is not None:
            vram_str = f" ({vram_source} VRAM ~{vram_display}°C)" if vram_display else ""

            if snap.gpu_temp_c >= p.critical_c:
                if not self._gpu_temp_critical_warned:
                    self.log(
                        f"  🔴 GPU temperature CRITICAL: {snap.gpu_temp_c}°C"
                        f"{vram_str}! "
                        f"Force-pausing to protect the card. "
                        f"(profile: {p.name}, critical: {p.critical_c}°C)",
                        "ERROR",
                    )
                    self._gpu_temp_critical_warned = True
                    # V9.0.0 E3: auto-pause if callback is registered
                    if self._auto_pause_callback and not self._auto_pause_triggered:
                        self._auto_pause_triggered = True
                        self.log(
                            f"  ⏸️ Auto-pausing conversion due to critical GPU "
                            f"temperature. The GPU needs to cool down before "
                            f"resuming. (profile: {p.name})",
                            "ERROR",
                        )
                        try:
                            self._auto_pause_callback()
                        except Exception as _e:
                            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            elif snap.gpu_temp_c >= p.caution_c:
                # V10.1.3: new caution tier — at/above throttle, recommend action
                if not self._gpu_temp_caution_warned:
                    self.log(
                        f"  🟠 GPU temperature CAUTION: {snap.gpu_temp_c}°C"
                        f"{vram_str}. "
                        f"At NVIDIA's throttle point — inference is slower and "
                        f"sustained load here degrades thermal paste faster. "
                        f"Recommend: reduce max_workers, improve airflow, or "
                        f"pause for 5 min to cool. "
                        f"(profile: {p.name}, caution: {p.caution_c}°C)",
                        "WARNING",
                    )
                    self._gpu_temp_caution_warned = True
            elif snap.gpu_temp_c >= p.warning_c:
                if not self._gpu_temp_warned:
                    self.log(
                        f"  ⚠️ GPU temperature high: {snap.gpu_temp_c}°C"
                        f"{vram_str}. Monitor closely. "
                        f"(profile: {p.name}, warning: {p.warning_c}°C)",
                        "WARNING",
                    )
                    self._gpu_temp_warned = True
            else:
                # Reset warnings when temp drops back to normal
                self._gpu_temp_warned = False
                self._gpu_temp_caution_warned = False
                self._gpu_temp_critical_warned = False
                # V18.20.2.0 (SWOT A11): reset the auto-pause latch too —
                # previously ``_auto_pause_triggered`` stayed True forever
                # after the first critical-temp pause, so a SECOND overheat
                # later in the same run never re-paused (the pause callback
                # was silently skipped while the CRITICAL warning still
                # fired).  Resetting here mirrors the three warned flags.
                self._auto_pause_triggered = False

            # V10.1.3: sustained-load cool-down recommendation.
            # For cards with sustained_pause_interval_min > 0 (Zotac etc.),
            # if the GPU has been under sustained load (>80% util) for longer
            # than the interval, log an INFO recommending a 5-min cool-down.
            # This is NOT an auto-pause — just a recommendation.  The user
            # can ignore it if their temps are in the safe zone.
            if (
                p.sustained_pause_interval_min > 0
                and snap.gpu_utilization_pct is not None
                and snap.gpu_utilization_pct > 80
            ):
                if self._sustained_load_start is None:
                    self._sustained_load_start = now
                elapsed_min = (now - self._sustained_load_start) / 60.0
                cooldown_elapsed = (
                    (now - self._last_cooldown_time) / 60.0
                    if self._last_cooldown_time
                    else elapsed_min
                )
                if (
                    elapsed_min >= p.sustained_pause_interval_min
                    and cooldown_elapsed >= p.sustained_pause_interval_min
                ):
                    # V18.20.2.0 (SWOT A9): ``est_hotspot`` was referenced
                    # here but never assigned (AST-verified) — the NameError
                    # crashed the log call, was swallowed at DEBUG by the
                    # polling loop, and the 20-min cool-down recommendation
                    # NEVER displayed.  ``vram_display`` holds the value the
                    # function already computed (real VRAM temp when the
                    # sensor is exposed, core + hotspot delta otherwise).
                    _hotspot_c = vram_display if vram_display is not None else snap.gpu_temp_c
                    self.log(
                        f"  ⏱️ Sustained load for {elapsed_min:.0f} min on {p.name}. "
                        f"Recommend a 5-min cool-down to reduce thermal-cycling "
                        f"stress. (Current: {snap.gpu_temp_c}°C core, "
                        f"~{_hotspot_c}°C hotspot. This is an INFO notice, "
                        f"not an error — ignore if temps are in the safe zone.)",
                        "INFO",
                    )
                    self._last_cooldown_time = now  # don't repeat for a while
            elif snap.gpu_utilization_pct is not None and snap.gpu_utilization_pct < 50:
                # GPU idle — reset the sustained-load tracker
                self._sustained_load_start = None

        # RAM usage
        if snap.ram_pct is not None:
            if snap.ram_pct >= RAM_PCT_WARNING:
                if not self._ram_warned:
                    self.log(
                        f"  ⚠️ RAM usage high: {snap.ram_pct:.0f}% "
                        f"({snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f} GB). "
                        f"Risk of swap/OOM — consider reducing max_workers.",
                        "WARNING",
                    )
                    self._ram_warned = True
            else:
                self._ram_warned = False

    def _run(self) -> None:
        """Background polling loop."""
        while not self._stop_event.is_set():
            try:
                snap = self._poll_once()
                if not snap.is_empty():
                    with self._lock:
                        self._snapshot = snap
                    self._check_thresholds(snap)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)  # never crash the monitor
            self._stop_event.wait(self.interval)

    # ── public API ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._thread is not None and self._thread.is_alive():
            return  # already running
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="HardwareMonitor")
        self._thread.start()
        if self._nvidia_smi_path:
            self.log("  📊 Hardware monitor started (nvidia-smi + psutil)", "DEBUG")
        elif self._psutil_available:
            self.log("  📊 Hardware monitor started (psutil only — no nvidia-smi)", "DEBUG")
        else:
            self.log("  ℹ️ Hardware monitor: no nvidia-smi or psutil available", "DEBUG")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def get_snapshot(self) -> HardwareSnapshot:
        """Return the latest snapshot (thread-safe)."""
        with self._lock:
            return self._snapshot

    @property
    def is_available(self) -> bool:
        """True if at least one monitoring source is available."""
        return self._nvidia_smi_path is not None or self._psutil_available


# ── Post-completion actions (shutdown/sleep/quit) ─────────────────────────


def execute_post_completion_action(
    action: str,
    delay_seconds: int = 60,
    log_callback: LogFn | None = None,
) -> None:
    """Execute a post-conversion system action (shutdown/sleep/quit).

    Args:
        action: "shutdown", "sleep", "hibernate", "quit", or "none".
        delay_seconds: grace period before the action (for shutdown/sleep).
            The caller should show a countdown dialog during this period.
        log_callback: ``fn(msg, level)``.

    This function blocks for ``delay_seconds`` then executes the command.
    It should be called from a background thread, not the UI thread.
    """
    import sys

    log = log_callback or (lambda msg, level: None)

    if action == "none":
        return

    if action == "quit":
        log("  👋 Quitting application as requested.", "INFO")
        # Post a quit to the Qt event loop (must be called from main thread
        # — the caller handles marshaling)
        return

    # For shutdown/sleep/hibernate — execute the platform command
    log(f"  ⏳ {action.capitalize()} in {delay_seconds}s…", "INFO")

    # V18.20.4.12 (W-c15/T-c5): each branch used to fire a blind
    # ``subprocess.Popen`` and never check the result.  The command lists
    # below are byte-identical to the old Popen args — only the execution
    # (bounded wait + honest rc/stderr reporting) is new; see
    # ``_run_post_completion_command``.
    if action == "shutdown":
        if sys.platform == "win32":
            # Windows: shutdown /s /t <seconds>
            cmd = ["shutdown", "/s", "/t", str(delay_seconds)]
        elif sys.platform == "darwin":
            # macOS: no built-in delayed shutdown; use shutdown directly
            cmd = ["sudo", "shutdown", "-h", "+1"]
        else:
            # Linux: shutdown -h +<minutes>
            cmd = ["shutdown", "-h", f"+{max(1, delay_seconds // 60)}"]
    elif action == "sleep":
        if sys.platform == "win32":
            # Windows: rundll32 powrprof.dll,SetSuspendState 0,1,0
            cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
        elif sys.platform == "darwin":
            cmd = ["pmset", "sleepnow"]
        else:
            cmd = ["systemctl", "suspend"]
    elif action == "hibernate":
        if sys.platform == "win32":
            cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,0"]
        elif sys.platform == "darwin":
            cmd = ["pmset", "hibernatenow"]
        else:
            cmd = ["systemctl", "hibernate"]
    else:
        # Unknown action — nothing to execute (pre-V18.20.4.12 the dispatch
        # silently fell through the if/elif chain without running anything;
        # preserve that behaviour).
        return

    _run_post_completion_command(action, cmd, log)


def _run_post_completion_command(action: str, cmd: list[str], log: LogFn) -> None:
    """Run one shutdown/sleep/hibernate command and report the outcome honestly.

    V18.20.4.12 (W-c15/T-c5): replaces the old fire-and-forget
    ``subprocess.Popen`` which never checked the return code — a macOS
    ``sudo shutdown`` without a TTY fails INSTANTLY and silently, so the
    user's overnight machine simply stayed on with no trace in the log.
    We now wait (bounded) for the command and report:

      - rc == 0        → INFO "scheduled/initiated successfully"
      - rc != 0        → LOUD WARNING: returncode + stderr (first ~200
                         chars; verbatim on Windows) + ONE actionable
                         platform hint
      - TimeoutExpired → NOT a failure (see the handler below)

    Any other exception (e.g. FileNotFoundError for a missing binary)
    propagates to the caller exactly as the old Popen did — the wizard's
    call site already wraps this in try/except.
    """
    import sys

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        # NOT a failure: ``rundll32 powrprof.dll,SetSuspendState`` can block
        # indefinitely while the machine is ALREADY suspending, and killing
        # the spawner process (which subprocess.run does on timeout) is
        # harmless but unnecessary — the suspend was likely initiated at
        # the OS level.  We simply stop waiting and treat it as scheduled.
        log(
            f"  ℹ️ {action.capitalize()} command still running after 20s "
            f"(suspend was likely initiated at the OS level — treating as scheduled)",
            "INFO",
        )
        return

    if result.returncode == 0:
        log(f"  ✅ {action.capitalize()} scheduled/initiated successfully", "INFO")
        return

    stderr_text = (result.stderr or "").strip()
    if sys.platform == "win32":
        # Windows: no single obvious hint — the VERBATIM stderr is the
        # diagnosis (e.g. "Command failed: 1190 (A system shutdown has
        # already been scheduled.)" (1190), shutdown error 1314, etc.).
        stderr_part = stderr_text or "(empty)"
        hint = ""
    else:
        stderr_part = stderr_text[:200] or "(empty)"
        if sys.platform == "darwin":
            hint = (
                " — hint: sudo needs a TTY — grant passwordless shutdown in "
                "sudoers (`youruser ALL=(ALL) NOPASSWD: /sbin/shutdown`) "
                "or use the Quit action"
            )
        else:
            hint = (
                " — hint: shutdown requires root — use `systemctl poweroff` polkit or run as root"
            )
    log(
        f"  ⚠️ {action.capitalize()} FAILED (rc={result.returncode}): "
        f"{' '.join(cmd)} — stderr: {stderr_part}{hint}",
        "WARNING",
    )
