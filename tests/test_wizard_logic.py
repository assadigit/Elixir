"""Tests for core/pipeline/wizard_logic.py — extracted business logic."""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import directly (bypasses core/pipeline/__init__.py which pulls in Converter
# → markitdown, not installed in the test environment).
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "core.pipeline.wizard_logic", _project_root / "core" / "pipeline" / "wizard_logic.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["core.pipeline.wizard_logic"] = _mod
_spec.loader.exec_module(_mod)

VRAMBudget = _mod.VRAMBudget
calculate_vram_budget_from_state = _mod.calculate_vram_budget_from_state
should_show_workers_warning = _mod.should_show_workers_warning
should_show_temp_warning = _mod.should_show_temp_warning


# ── should_show_workers_warning ───────────────────────────────────────────

def test_workers_1_no_warning() -> None:
    """1 worker should not trigger a warning."""
    warn, msg = should_show_workers_warning(1)
    assert warn is False
    assert "safe" in msg


def test_workers_2_warning() -> None:
    """2 workers should trigger a warning."""
    warn, msg = should_show_workers_warning(2)
    assert warn is True
    assert "VRAM heat" in msg


def test_workers_2_emergency_warning() -> None:
    """2 workers on an emergency-mode card should show a stronger warning."""
    class FakeProfile:
        emergency_mode = True
    warn, msg = should_show_workers_warning(2, FakeProfile())
    assert warn is True
    assert "thermal issues" in msg


# ── should_show_temp_warning ──────────────────────────────────────────────

def test_temp_06_no_warning() -> None:
    """0.6 temperature should not trigger a warning."""
    warn, msg, color = should_show_temp_warning(0.6)
    assert warn is False


def test_temp_02_warning() -> None:
    """0.2 temperature should trigger a warning."""
    warn, msg, color = should_show_temp_warning(0.2)
    assert warn is True
    assert "Low temp" in msg
    assert color == "warning"


# ── VRAMBudget ────────────────────────────────────────────────────────────

def test_vram_budget_format_report() -> None:
    """format_report should return a list of strings."""
    budget = VRAMBudget(
        estimates={"OCR": 6.0, "Summarization": 5.0},
        peak=11.0,
        total=12.0,
    )
    lines = budget.format_report()
    assert isinstance(lines, list)
    assert len(lines) >= 3
    assert any("OCR" in line for line in lines)
    assert budget.is_overbudget is False  # 11 < 12


def test_vram_budget_overbudget() -> None:
    """Overbudget detection should work."""
    budget = VRAMBudget(peak=15.0, total=12.0)
    lines = budget.format_report()
    assert budget.is_overbudget is True
    assert any("OVERBUDGET" in line for line in lines)


def test_vram_budget_no_gpu() -> None:
    """No GPU detection should not crash."""
    budget = VRAMBudget(peak=10.0, total=0.0)
    lines = budget.format_report()
    assert budget.is_overbudget is False
    assert any("unavailable" in line for line in lines)


# ── calculate_vram_budget_from_state ──────────────────────────────────────

def test_calculate_vram_budget_empty_state() -> None:
    """Empty state should not crash — returns a budget with zeros."""
    class EmptyState:
        primary_ocr_model = ""
        summarisation_model = ""
        fast_model = ""
        heavy_model = ""
        translation_enabled = False
        translation_backend = ""
        translation_harakat_model = ""
        translation_judge_model = ""
        outputs_tts = False
        max_workers = 1

    budget = calculate_vram_budget_from_state(EmptyState())
    assert isinstance(budget, VRAMBudget)
