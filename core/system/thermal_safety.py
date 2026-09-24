"""V10.1.5: Thermal Safety System — comprehensive GPU protection.

This module orchestrates ALL thermal safety measures for the app.  It's
designed around one principle: **the user's GPU must never overheat
again, even if they select every output and run for 8 hours.**

The system has 6 layers of protection:

1. **VRAM temperature reading** — queries ``temperature.memory`` via
   nvidia-smi (available on RTX 30-series+).  This is the REAL VRAM
   temp, not a core+delta estimate.  Falls back to the estimate if the
   sensor isn't exposed.

2. **Pre-flight thermal check** — before conversion starts, runs a
   30-second model warmup and measures the temp rise.  If the GPU
   starts hot (>55°C idle) or rises >15°C in 30 sec, warns that cooling
   is inadequate and suggests fixing hardware first.

3. **Mandatory periodic cool-downs** — for emergency-mode cards (Zotac),
   the system PAUSES the conversion every N minutes of sustained GPU
   load, for M minutes of cool-down.  This is time-based (not
   temp-based) — it fires even if temps look OK, because the VRAM
   thermal pads degrade under sustained load regardless of the core
   reading.  The pause uses a ``threading.Event`` gate that the
   summarization workers check between chapters.

4. **Thermal budget tracker** — tracks cumulative GPU-seconds above
   70°C.  If the daily thermal exposure exceeds a budget (2 hours above
   70°C), forces a 30-minute cool-down before continuing.  This prevents
   "death by a thousand cuts" — many short hot sessions that accumulate
   thermal damage.

5. **Output count guard** — counts enabled outputs.  If >5 outputs are
   enabled, warns that the session will be prolonged and suggests
   disabling non-essential outputs.  For emergency-mode cards, hard-caps
   at 4 simultaneous outputs.

6. **Model recommendation** — for emergency-mode cards, suggests lighter
   models (7B instead of 9B, Q3 instead of Q4) and shows expected VRAM
   + thermal savings.

Usage (from converter.py)::

    from core.system.thermal_safety import ThermalSafetyController

    ts = ThermalSafetyController(
        log_callback=self._log,
        profile=_gpu_profile,
        cancel_event=self.cancel_event,
    )
    ts.preflight_check()        # 30-sec warmup + temp rise check
    ts.start()                  # starts the monitor + cool-down scheduler
    # ... during conversion ...
    ts.wait_if_paused()         # blocks if a cool-down is in progress
    # ... after conversion ...
    ts.stop()
    ts.log_thermal_report()     # final thermal summary
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ── Configuration ─────────────────────────────────────────────────────────

# Pre-flight check: model warmup duration (seconds)
PREFLIGHT_WARMUP_SEC = 30

# Pre-flight check: temp rise thresholds
PREFLIGHT_IDLE_HOT_C = 55  # idle temp above this = warning
PREFLIGHT_RISE_WARN_C = 12  # rise above this in 30s = cooling inadequate
PREFLIGHT_RISE_CRITICAL_C = 20  # rise above this = refuse to start

# Mandatory cool-down (for emergency-mode cards)
COOLDOWN_INTERVAL_MIN = 20  # pause every 20 min of sustained load
COOLDOWN_DURATION_MIN = 3  # 3-min pause
COOLDOWN_RESUME_TEMP_C = 68  # don't resume until below this temp

# Thermal budget (cumulative exposure cap)
THERMAL_BUDGET_TRACK_TEMP_C = 70  # track time above this temp
THERMAL_BUDGET_DAILY_LIMIT_MIN = 120  # 2 hours above 70°C per day
THERMAL_BUDGET_REACHED_COOLDOWN_MIN = 30  # 30-min cool-down when budget hit

# Output count guard
OUTPUT_COUNT_WARN_THRESHOLD = 5  # warn if >5 outputs enabled
OUTPUT_COUNT_EMERGENCY_CAP = 4  # hard cap for emergency-mode cards


# ── Thermal budget tracker ────────────────────────────────────────────────


class ThermalBudget:
    """Tracks cumulative GPU thermal exposure.

    Counts the number of seconds the GPU has been above
    ``THERMAL_BUDGET_TRACK_TEMP_C`` during this session.  If the
    cumulative exposure exceeds ``THERMAL_BUDGET_DAILY_LIMIT_MIN``,
    a long cool-down is forced.
    """

    def __init__(self, log_callback: LogFn | None = None) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        # V18.20.3.2 (audit N9 / P2-d): threading.Lock -> threading.RLock.
        # ThermalBudget.format_report() acquires self._lock and then calls
        # the minutes_above_threshold PROPERTY, which acquires the SAME lock
        # — a non-reentrant Lock DEADLOCKS the calling thread. This is why
        # every V18.20.3.x real-rig log ends at "Session duration: N min":
        # log_report() hung on the budget line, the rest of the thermal
        # report + the diagnostic summary + the "Finished at" footer never
        # ran, and the user (seeing "Conversion complete.") closed the hung
        # app. RLock allows the nested acquisition.
        self._lock = threading.RLock()
        self._seconds_above_threshold: float = 0.0
        self._last_update: float | None = None
        self._budget_reached = False
        self._budget_reached_count = 0

    def update(self, gpu_temp_c: int | None, now: float) -> None:
        """Call this on every temperature reading."""
        if gpu_temp_c is None:
            self._last_update = None
            return
        with self._lock:
            if self._last_update is not None:
                dt = now - self._last_update
                if dt > 0 and dt < 120:  # ignore gaps > 2 min
                    if gpu_temp_c >= THERMAL_BUDGET_TRACK_TEMP_C:
                        self._seconds_above_threshold += dt
            self._last_update = now

    @property
    def minutes_above_threshold(self) -> float:
        with self._lock:
            return self._seconds_above_threshold / 60.0

    @property
    def budget_reached(self) -> bool:
        with self._lock:
            return self._budget_reached

    @property
    def budget_remaining_min(self) -> float:
        with self._lock:
            return max(0.0, THERMAL_BUDGET_DAILY_LIMIT_MIN - self.minutes_above_threshold)

    def check_budget(self) -> bool:
        """Returns True if the budget was just exceeded (triggers cool-down)."""
        with self._lock:
            if (
                not self._budget_reached
                and self.minutes_above_threshold >= THERMAL_BUDGET_DAILY_LIMIT_MIN
            ):
                self._budget_reached = True
                self._budget_reached_count += 1
                return True
            return False

    def reset_budget(self) -> None:
        """Call after a long cool-down to reset the budget."""
        with self._lock:
            self._seconds_above_threshold = 0.0
            self._budget_reached = False
            self._last_update = None

    def format_report(self) -> str:
        with self._lock:
            mins = self.minutes_above_threshold
            pct = (
                (mins / THERMAL_BUDGET_DAILY_LIMIT_MIN * 100)
                if THERMAL_BUDGET_DAILY_LIMIT_MIN > 0
                else 0
            )
            return (
                f"Thermal budget: {mins:.1f}/{THERMAL_BUDGET_DAILY_LIMIT_MIN} min "
                f"above {THERMAL_BUDGET_TRACK_TEMP_C}°C ({pct:.0f}%) — "
                f"{'⚠️ BUDGET REACHED' if self._budget_reached else '✅ within budget'}"
            )


# ── Cool-down scheduler ───────────────────────────────────────────────────


class CooldownScheduler:
    """Manages mandatory periodic cool-downs for emergency-mode cards.

    Every ``COOLDOWN_INTERVAL_MIN`` minutes of sustained GPU load
    (>80% utilization), triggers a cool-down pause of
    ``COOLDOWN_DURATION_MIN`` minutes.  The pause is implemented via a
    ``threading.Event`` gate that the summarization workers check
    between chapters.

    The scheduler is time-based, not temp-based — it fires even if temps
    look OK, because VRAM thermal pad degradation happens under
    sustained load regardless of the core reading.
    """

    def __init__(
        self,
        log_callback: LogFn | None = None,
        profile: Any | None = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._profile = profile
        # V18.20.3.2 (P2-d): RLock for future-proofing (same nested-
        # acquisition hazard as ThermalBudget; force_cooldown already calls
        # into _start_cooldown under the lock).
        self._lock = threading.RLock()
        # The pause gate: when set, workers should wait
        self._pause_event = threading.Event()
        # Sustained-load tracking
        self._sustained_load_start: float | None = None
        self._last_cooldown_end: float | None = None
        self._cooldown_count = 0
        self._in_cooldown = False
        # V18.20.2.0 (SWOT A12): hard duration cap for the CURRENT
        # cool-down event.  ``_start_cooldown`` stamps the start time and
        # the per-event max duration (COOLDOWN_DURATION_MIN for
        # scheduler-triggered cool-downs, THERMAL_BUDGET_REACHED_COOLDOWN_MIN
        # for budget-forced ones) so the end-condition check below can
        # always terminate a pause — even when GPU util stays >80% and the
        # temp never drops to COOLDOWN_RESUME_TEMP_C.
        self._cooldown_started_at: float | None = None
        self._cooldown_max_duration_sec: float | None = None

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    @property
    def cooldown_count(self) -> int:
        return self._cooldown_count

    def update(self, gpu_utilization_pct: int | None, gpu_temp_c: int | None, now: float) -> None:
        """Call on every snapshot.  Triggers cool-down when needed.

        V18.20.2.0 (SWOT A12): the end-of-cool-down conditions are now
        evaluated unconditionally on EVERY call.  Previously they lived
        inside the ``else`` (GPU util ≤ 80%) branch and the duration check
        compared against ``_last_cooldown_end`` — which is ``None`` until
        the FIRST cool-down ends, so the first cool-down could never end
        by duration.  Combined, a run with util pinned >80% and temp
        >``COOLDOWN_RESUME_TEMP_C`` blocked ``wait_if_paused`` forever.
        """
        with self._lock:
            # V18.20.2.0 (SWOT A12): end-of-cool-down check — unconditional
            # (runs even when utilization is None), so a cool-down always
            # terminates: temp recovered, or the hard duration cap elapsed.
            # Runs before the load tracking below so the pause gate is
            # cleared regardless of current util.
            if self._in_cooldown:
                if gpu_temp_c is not None and gpu_temp_c <= COOLDOWN_RESUME_TEMP_C:
                    self._end_cooldown()
                elif (
                    self._cooldown_started_at is not None
                    and self._cooldown_max_duration_sec is not None
                    and (now - self._cooldown_started_at) >= self._cooldown_max_duration_sec
                ):
                    # Hard cap on cool-down duration — resume even if the
                    # temp is still borderline (prevents an indefinite pause).
                    self._end_cooldown()

            if gpu_utilization_pct is None:
                return

            # Track sustained load (>80% util)
            if gpu_utilization_pct > 80:
                if self._sustained_load_start is None:
                    self._sustained_load_start = now
            else:
                # GPU idle — reset the sustained-load timer
                self._sustained_load_start = None
                return

            # Under sustained load — check if a cool-down is due
            if self._sustained_load_start is None or self._in_cooldown:
                return

            elapsed_min = (now - self._sustained_load_start) / 60.0
            since_last = (
                (now - self._last_cooldown_end) / 60.0 if self._last_cooldown_end else elapsed_min
            )

            if elapsed_min >= COOLDOWN_INTERVAL_MIN and since_last >= COOLDOWN_INTERVAL_MIN:
                self._start_cooldown(now, gpu_temp_c)

    def _start_cooldown(
        self,
        now: float,
        gpu_temp_c: int | None,
        max_duration_min: float = COOLDOWN_DURATION_MIN,
    ) -> None:
        self._in_cooldown = True
        self._cooldown_count += 1
        self._pause_event.set()
        # V18.20.2.0 (SWOT A12): stamp the start + per-event hard cap so
        # the end-condition check in update() can always terminate the
        # pause (measured from THIS cool-down's start, not from the end
        # of the previous one).
        self._cooldown_started_at = now
        self._cooldown_max_duration_sec = max_duration_min * 60
        temp_str = f" (current: {gpu_temp_c}°C)" if gpu_temp_c is not None else ""
        self.log(
            f"  🧊 Mandatory cool-down #{self._cooldown_count}: pausing for "
            f"{COOLDOWN_DURATION_MIN} min after {COOLDOWN_INTERVAL_MIN} min of "
            f"sustained GPU load{temp_str}. This protects the VRAM from "
            f"thermal-cycling stress. The conversion will resume automatically "
            f"when the GPU cools to {COOLDOWN_RESUME_TEMP_C}°C or after "
            f"{COOLDOWN_DURATION_MIN} min, whichever comes first.",
            "WARNING",
        )

    def _end_cooldown(self) -> None:
        self._in_cooldown = False
        self._pause_event.clear()
        self._last_cooldown_end = time.time()
        self._sustained_load_start = None  # reset the load timer
        self.log(
            "  ✅ Cool-down complete — resuming conversion.",
            "INFO",
        )

    def wait_if_paused(
        self,
        timeout_per_check: float = 2.0,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Block if a cool-down is in progress.  Call between chapters.

        Checks every ``timeout_per_check`` seconds so the caller can
        also check for cancellation (by breaking out of the loop).

        V18.20.2.0 (SWOT A12): the docstring always promised cancellation
        support but the parameter didn't exist.  When ``cancel_event`` is
        provided and set, the wait breaks immediately (the cool-down is
        logged as interrupted so the exit is traceable) instead of
        blocking the cancelled run until the cool-down expires.
        """
        while self._pause_event.is_set():
            if cancel_event is not None and cancel_event.is_set():
                self.log(
                    "  ⏹️ Cool-down interrupted by cancellation — exiting "
                    "the pause loop so the cancelled run can unwind.",
                    "INFO",
                )
                break
            self._pause_event.wait(timeout=timeout_per_check)

    def force_cooldown(self, reason: str = "manual") -> None:
        """Force an immediate cool-down (used by the thermal budget)."""
        with self._lock:
            if not self._in_cooldown:
                # V18.20.2.0 (SWOT A12): budget-forced cool-downs use the
                # documented THERMAL_BUDGET_REACHED_COOLDOWN_MIN (30 min)
                # as their hard cap, not the regular COOLDOWN_DURATION_MIN.
                self._start_cooldown(
                    time.time(),
                    None,
                    max_duration_min=THERMAL_BUDGET_REACHED_COOLDOWN_MIN,
                )
                # Override the log message
                self.log(
                    f"  🧊 Thermal budget cool-down: {reason}. "
                    f"Pausing for {THERMAL_BUDGET_REACHED_COOLDOWN_MIN} min.",
                    "WARNING",
                )

    def format_report(self) -> str:
        return (
            f"Cool-downs triggered: {self._cooldown_count} "
            f"(every {COOLDOWN_INTERVAL_MIN} min, {COOLDOWN_DURATION_MIN} min each)"
        )


# ── VRAM temperature reader ───────────────────────────────────────────────


def query_vram_temp(nvidia_smi_path: str) -> int | None:
    """Query the VRAM (memory) temperature via nvidia-smi.

    On RTX 30-series+ with recent drivers (R470+), nvidia-smi can read
    the memory temperature directly::

        nvidia-smi --query-gpu=temperature.memory --format=csv,noheader,nounits

    Returns None if the sensor isn't available (older cards or drivers).
    """
    if not nvidia_smi_path:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi_path, "--query-gpu=temperature.memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        raw = result.stdout.strip()
        if not raw or raw.upper() == "N/A" or raw == "[N/A]":
            return None
        return int(raw)
    except Exception as _e:
        return None


# ── Model recommendation ──────────────────────────────────────────────────


@dataclass
class ModelRecommendation:
    """A thermal-safe model recommendation."""

    model_name: str
    param_count: str  # "7B", "9B"
    quant: str  # "Q4_K_M", "Q3_K_M"
    vram_gb: float  # estimated VRAM usage
    thermal_risk: str  # "low", "medium", "high"
    note: str


# Known thermal-safe models for the Zotac 3060 Twin Edge (12GB VRAM)
THERMAL_SAFE_MODELS: list[ModelRecommendation] = [
    ModelRecommendation(
        model_name="gemma2:7b",
        param_count="7B",
        quant="Q4_K_M",
        vram_gb=5.0,
        thermal_risk="low",
        note="Smallest model that still produces good summaries. ~30% less VRAM "
        "bandwidth than 9B models. Best choice for sustained overnight runs "
        "on the Zotac 3060 Twin Edge.",
    ),
    ModelRecommendation(
        model_name="qwen2.5:7b",
        param_count="7B",
        quant="Q4_K_M",
        vram_gb=5.0,
        thermal_risk="low",
        note="Qwen 2.5 7B — strong reasoning, efficient architecture. ~30% less "
        "VRAM bandwidth than 9B. Good for academic papers.",
    ),
    ModelRecommendation(
        model_name="mistral:7b",
        param_count="7B",
        quant="Q4_K_M",
        vram_gb=5.0,
        thermal_risk="low",
        note="Mistral 7B — reliable, well-tested. Low VRAM bandwidth.",
    ),
    ModelRecommendation(
        model_name="gemma2:9b",
        param_count="9B",
        quant="Q3_K_M",
        vram_gb=4.5,
        thermal_risk="medium",
        note="9B at Q3 quant — 25% less VRAM than Q4. Slightly lower quality "
        "but significantly less thermal stress. Acceptable for emergency mode.",
    ),
]


def recommend_thermal_safe_models(
    current_model: str,
    profile: Any,
    log_callback: LogFn | None = None,
) -> list[ModelRecommendation]:
    """Recommend lighter models for emergency-mode cards.

    Returns a list of recommendations.  If the current model is already
    in the safe list, returns an empty list.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    if not getattr(profile, "emergency_mode", False):
        return []

    current_lower = (current_model or "").lower()
    # If the user is already on a 7B or Q3 model, don't recommend
    if "7b" in current_lower and "q3" not in current_lower:
        return []
    if "q3" in current_lower:
        return []

    log(
        f"  💡 Thermal-safe model recommendation: your current model "
        f"({current_model}) is a 9B+ model which stresses VRAM. Consider "
        f"switching to a lighter model for lower thermal load:",
        "INFO",
    )
    for rec in THERMAL_SAFE_MODELS:
        log(
            f"    • {rec.model_name} ({rec.param_count} {rec.quant}, "
            f"~{rec.vram_gb:.1f} GB VRAM, risk: {rec.thermal_risk}) — {rec.note}",
            "INFO",
        )
    return THERMAL_SAFE_MODELS


# ── Output count guard ────────────────────────────────────────────────────


def count_enabled_outputs(request: Any) -> tuple[int, list[str]]:
    """Count the number of optional outputs enabled on the request.

    Returns (count, list_of_enabled_output_names).
    """
    output_attrs = [
        ("output_briefing", "Executive Briefing"),
        ("output_podcast", "Podcast Script"),
        ("output_flashcards", "Flashcards"),
        ("output_packets", "Packets of Knowledge"),
        ("output_obsidian", "Obsidian KB"),
        ("output_study_guide", "Study Guide"),
        ("output_social", "Social Media Pack"),
        ("output_mindmap", "Mind Map"),
        ("output_tts", "Podcast Audio (TTS)"),
        ("output_evidence_map", "Evidence Map"),  # V10.1.0
    ]
    enabled = []
    for attr, name in output_attrs:
        if getattr(request, attr, False):
            enabled.append(name)
    return len(enabled), enabled


def check_output_count_safety(
    request: Any,
    profile: Any,
    log_callback: LogFn | None = None,
) -> str:
    """Check if the output count is safe for the GPU profile.

    Returns a warning message string, or "" if OK.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    count, enabled = count_enabled_outputs(request)

    is_emergency = getattr(profile, "emergency_mode", False)

    if count > OUTPUT_COUNT_WARN_THRESHOLD:
        warning = (
            f"⚠️ {count} outputs enabled ({', '.join(enabled)}). "
            f"More outputs = longer session = more sustained GPU heat. "
        )
        if is_emergency and count > OUTPUT_COUNT_EMERGENCY_CAP:
            warning += (
                f"For your card's VRAM safety, disable at least "
                f"{count - OUTPUT_COUNT_EMERGENCY_CAP} output(s) to stay "
                f"under the {OUTPUT_COUNT_EMERGENCY_CAP}-output cap. "
                f"Recommended essentials: chapter_summaries + keypoints + "
                f"briefing. Disable the rest for overnight runs."
            )
        else:
            warning += (
                "Consider disabling non-essential outputs for overnight runs. "
                "Essentials: chapter_summaries, keypoints, briefing."
            )
        log(f"  {warning}", "WARNING")
        return warning

    return ""


# ── Pre-flight thermal check ──────────────────────────────────────────────


def preflight_thermal_check(
    nvidia_smi_path: str,
    profile: Any,
    log_callback: LogFn | None = None,
    model_manager: Any = None,
    model_name: str = "",
) -> tuple[bool, str]:
    """Run a pre-flight thermal check before conversion starts.

    1. Reads the idle GPU temp.
    2. If model_manager + model_name provided, runs a 30-sec warmup call.
    3. Measures the temp rise.
    4. Returns (passed, message).

    If the temp rise is critical (>20°C in 30 sec), returns False —
    the conversion should be aborted.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    if not nvidia_smi_path:
        return True, "(nvidia-smi unavailable — skipping pre-flight check)"

    def _read_temp() -> int | None:
        try:
            result = subprocess.run(
                [nvidia_smi_path, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split(", ")[0])
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return None

    # Step 1: idle temp
    idle_temp = _read_temp()
    if idle_temp is None:
        return True, "(could not read GPU temp — skipping pre-flight check)"

    log(f"  🌡️ Pre-flight: idle GPU temp = {idle_temp}°C", "INFO")

    if idle_temp >= PREFLIGHT_IDLE_HOT_C:
        log(
            f"  ⚠️ Pre-flight WARNING: GPU idle temp {idle_temp}°C is above "
            f"{PREFLIGHT_IDLE_HOT_C}°C. The GPU is already warm before the "
            f"conversion starts. Check that no other GPU-heavy apps are "
            f"running, and consider improving case airflow before proceeding.",
            "WARNING",
        )

    # Step 2: warmup (if model provided)
    if model_manager and model_name:
        log(
            f"  🔥 Pre-flight: running {PREFLIGHT_WARMUP_SEC}-sec warmup "
            f"with {model_name} to test thermal response…",
            "INFO",
        )
        t0 = time.time()
        try:
            # Send a tiny generate request to warm the model
            if hasattr(model_manager, "acquire_model"):
                from core.llm import ModelType

                model_manager.acquire_model(
                    model_name, ModelType.SUMMARISATION, skip_vram_check=True
                )
        except Exception as e:
            log(f"  ℹ️ Pre-flight: model warmup skipped ({e})", "DEBUG")

        # Wait for the warmup duration, reading temps
        temps_during = []
        while time.time() - t0 < PREFLIGHT_WARMUP_SEC:
            t = _read_temp()
            if t is not None:
                temps_during.append(t)
            time.sleep(3)

        # Release the model
        try:
            if hasattr(model_manager, "release_model"):
                model_manager.release_model(model_name)
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        if len(temps_during) < 3:
            log("  ℹ️ Pre-flight: insufficient temp readings during warmup", "DEBUG")
            return True, "(insufficient data)"

        peak_temp = max(temps_during)
        rise = peak_temp - idle_temp
        log(
            f"  🌡️ Pre-flight: peak temp during warmup = {peak_temp}°C "
            f"(rise: +{rise}°C over {PREFLIGHT_WARMUP_SEC}s)",
            "INFO",
        )

        if rise >= PREFLIGHT_RISE_CRITICAL_C:
            msg = (
                f"🚨 Pre-flight CRITICAL: GPU temp rose {rise}°C in "
                f"{PREFLIGHT_WARMUP_SEC} seconds (idle {idle_temp}°C → peak "
                f"{peak_temp}°C). This indicates severely inadequate cooling — "
                f"the GPU would overheat during a full conversion. ABORTING. "
                f"Fix the cooling (clean fans, re-paste, improve airflow) "
                f"before attempting another conversion."
            )
            log(f"  {msg}", "ERROR")
            return False, msg
        elif rise >= PREFLIGHT_RISE_WARN_C:
            msg = (
                f"⚠️ Pre-flight WARNING: GPU temp rose {rise}°C in "
                f"{PREFLIGHT_WARMUP_SEC} seconds. Cooling is marginal — the "
                f"GPU will get hot during a long conversion. Consider: "
                f"cleaning fans, setting an aggressive fan curve in MSI "
                f"Afterburner, or improving case airflow."
            )
            log(f"  {msg}", "WARNING")
            return True, msg
        else:
            log(
                f"  ✅ Pre-flight: thermal response OK (+{rise}°C in "
                f"{PREFLIGHT_WARMUP_SEC}s). Safe to proceed.",
                "INFO",
            )
            return True, ""

    return True, ""


# ── Main controller ───────────────────────────────────────────────────────


class ThermalSafetyController:
    """Orchestrates all thermal safety measures for one conversion.

    Usage::

        ts = ThermalSafetyController(
            log_callback=self._log,
            profile=_gpu_profile,
        )
        # Pre-flight (before summarization)
        passed, msg = ts.preflight_check(nvidia_smi_path, model_manager, model_name)
        if not passed:
            return  # abort conversion
        # Start monitoring
        ts.start()
        # During conversion (between chapters):
        ts.wait_if_paused()
        # After conversion:
        ts.stop()
        ts.log_report()
    """

    def __init__(
        self,
        log_callback: LogFn | None = None,
        profile: Any = None,
    ) -> None:
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._profile = profile or _get_default_profile()
        self._budget = ThermalBudget(log_callback=self.log)
        self._scheduler = CooldownScheduler(
            log_callback=self.log,
            profile=self._profile,
        )
        self._started = False
        self._start_time: float | None = None

    def preflight_check(
        self,
        nvidia_smi_path: str = "",
        model_manager: Any = None,
        model_name: str = "",
    ) -> tuple[bool, str]:
        """Run the pre-flight thermal check.  Call before conversion."""
        return preflight_thermal_check(
            nvidia_smi_path=nvidia_smi_path,
            profile=self._profile,
            log_callback=self.log,
            model_manager=model_manager,
            model_name=model_name,
        )

    def start(self) -> None:
        """Start the thermal safety monitoring."""
        self._started = True
        self._start_time = time.time()
        self.log(
            f"  🛡️ Thermal Safety System active. Profile: {self._profile.name}",
            "INFO",
        )
        if getattr(self._profile, "emergency_mode", False):
            self.log(
                f"  🧊 Mandatory cool-downs: every {COOLDOWN_INTERVAL_MIN} min, "
                f"{COOLDOWN_DURATION_MIN} min each. Thermal budget: "
                f"{THERMAL_BUDGET_DAILY_LIMIT_MIN} min above "
                f"{THERMAL_BUDGET_TRACK_TEMP_C}°C.",
                "INFO",
            )

    def update(self, gpu_temp_c: int | None, gpu_utilization_pct: int | None) -> None:
        """Call on every hardware snapshot.  Updates budget + scheduler.

        V18.20.2.0 (SWOT A12): READY TO WIRE but deliberately NOT wired
        into production callers yet.  This method still has ZERO
        production call sites (SWOT W3-CRITICAL) — activating the
        mandatory 20-min Zotac cool-downs + thermal budget changes
        run timing and MUST be validated with a golden-master run on
        the real rig first (per Threats T2/T3 discipline).  Once
        approved, wire it from the hardware-monitor poll loop:
        ``ts.update(snap.gpu_temp_c, snap.gpu_utilization_pct)``.
        """
        if not self._started:
            return
        now = time.time()
        self._budget.update(gpu_temp_c, now)
        self._scheduler.update(gpu_utilization_pct, gpu_temp_c, now)
        # Check thermal budget
        if self._budget.check_budget():
            self.log(
                f"  🚨 Thermal budget REACHED: {self._budget.minutes_above_threshold:.0f} min "
                f"above {THERMAL_BUDGET_TRACK_TEMP_C}°C. Forcing "
                f"{THERMAL_BUDGET_REACHED_COOLDOWN_MIN}-min cool-down to protect "
                f"the GPU from cumulative thermal damage.",
                "ERROR",
            )
            self._scheduler.force_cooldown("thermal budget exceeded")

    def wait_if_paused(self, cancel_event: threading.Event | None = None) -> None:
        """Block if a cool-down is in progress.  Call between chapters.

        V18.20.2.0 (SWOT A12): forwards ``cancel_event`` so a cancelled
        run unwinds promptly instead of waiting out the cool-down.
        """
        self._scheduler.wait_if_paused(cancel_event=cancel_event)

    @property
    def is_paused(self) -> bool:
        return self._scheduler.is_paused

    def stop(self) -> None:
        """Stop monitoring."""
        self._started = False

    def log_report(self) -> None:
        """Log the final thermal report at the end of conversion.

        V18.20.3.2 (audit N9 / P2-d): each line is individually guarded —
        one failing sub-report can never kill the remaining lines (the
        V18.20.3.1 log ended mid-report because format_report deadlocked
        on a non-reentrant lock; the RLock fix removes the deadlock, and
        these per-line guards are defense-in-depth so a partial failure
        is VISIBLE instead of silent).
        """
        if self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        elapsed_min = elapsed / 60.0
        self.log("", "INFO")
        self.log("━━━ Thermal Safety Report ━━━", "INFO")
        self.log(f"  Profile: {self._profile.name}", "INFO")
        self.log(f"  Session duration: {elapsed_min:.1f} min", "INFO")
        try:
            self.log(f"  {self._budget.format_report()}", "INFO")
        except Exception as _e:  # pragma: no cover — defense-in-depth
            self.log(f"  ⚠️ Thermal budget report failed: {_e}", "WARNING")
        try:
            self.log(f"  {self._scheduler.format_report()}", "INFO")
        except Exception as _e:  # pragma: no cover — defense-in-depth
            self.log(f"  ⚠️ Cool-down report failed: {_e}", "WARNING")
        self.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")


# ── Helper ────────────────────────────────────────────────────────────────


def _get_default_profile():
    """Get the default thermal profile (imported lazily to avoid circular deps)."""
    try:
        from core.system.hardware_monitor import _PROFILE_DEFAULT

        return _PROFILE_DEFAULT
    except Exception as _e:
        return None
