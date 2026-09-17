"""Business logic extracted from the wizard view.

This module contains pure computation and decision logic that was
previously tangled with Qt widget access in wizard_view.py.

Each function takes plain data (no Qt types) and returns plain data,
making it trivially testable without a Qt application instance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class VRAMBudget:
    """Result of a VRAM budget calculation."""
    estimates: dict[str, float] = field(default_factory=dict)
    peak: float = 0.0
    total: float = 0.0
    recommendation: str = ""
    is_overbudget: bool = False

    def format_report(self) -> list[str]:
        """Format as a list of log lines (no Qt)."""
        lines = []
        for label, size in self.estimates.items():
            marker = "🔄" if size > 0 else "⏭️"
            lines.append(f"  {marker} {label}: ~{size:.1f} GB")
        lines.append("  " + "─" * 40)
        if self.total > 0:
            if self.peak > self.total:
                lines.append(f"  ⚠️ Peak: {self.peak:.1f} GB > VRAM: {self.total:.1f} GB — OVERBUDGET")
                self.is_overbudget = True
            else:
                lines.append(f"  Peak: {self.peak:.1f} GB (VRAM: {self.total:.1f} GB)")
        else:
            lines.append(f"  Peak: {self.peak:.1f} GB (GPU detection unavailable)")
        return lines


def calculate_vram_budget_from_state(state: Any) -> VRAMBudget:
    """Calculate VRAM budget from a WizardState-like object.

    This is a pure function — no Qt widgets, no side effects.
    The wizard calls this and then displays the result.
    """
    try:
        from core.vram_calculator import calculate_vram_budget
        estimates, peak, total, recommendation = calculate_vram_budget(
            ocr_model=getattr(state, 'primary_ocr_model', ''),
            summarization_model=getattr(state, 'summarisation_model', ''),
            fast_model=getattr(state, 'fast_model', ''),
            heavy_model=getattr(state, 'heavy_model', ''),
            translation_backend=getattr(state, 'translation_backend', '') if getattr(state, 'translation_enabled', False) else "",
            translation_model=getattr(state, 'summarisation_model', ''),
            harakat_model=getattr(state, 'translation_harakat_model', '') if getattr(state, 'translation_enabled', False) else "",
            judge_model=getattr(state, 'translation_judge_model', '') if getattr(state, 'translation_enabled', False) else "",
            tts_enabled=getattr(state, 'outputs_tts', False),
            tts_engine="neutts",
            max_workers=getattr(state, 'max_workers', 1),
        )
        return VRAMBudget(
            estimates=estimates,
            peak=peak,
            total=total,
            recommendation=recommendation,
            is_overbudget=(total > 0 and peak > total),
        )
    except Exception as _e:
        return VRAMBudget()


def should_show_workers_warning(workers: int, gpu_profile: Any | None = None) -> tuple[bool, str]:
    """Determine if a workers warning should be shown.

    Returns (should_warn, message).
    Pure function — no Qt.
    """
    if workers > 1:
        is_emergency = getattr(gpu_profile, 'emergency_mode', False) if gpu_profile else False
        if is_emergency:
            return True, (
                f"⚠️ {workers} workers = {workers}× VRAM heat. "
                f"This card has VRAM thermal issues. Only use >1 on cards "
                f"with good VRAM cooling."
            )
        return True, (
            f"⚠️ {workers} workers = {workers}× VRAM heat. "
            f"LLM inference is memory-bandwidth-bound — multiple workers "
            f"multiply VRAM thermal stress."
        )
    return False, "✓ safe"


def should_show_temp_warning(temp: float) -> tuple[bool, str, str]:
    """Determine if a temperature warning should be shown.

    Returns (should_warn, message, color_key).
    Pure function — no Qt.
    """
    if temp < 0.4:
        return True, (
            "⚠️ Low temp — many models produce empty/degenerate output "
            "below 0.4. Check your model's fine-tuner spec."
        ), "warning"
    return False, "", ""
