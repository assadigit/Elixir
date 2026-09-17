"""Tests for BaseWorker and hardware_monitor pyNVML integration."""
from __future__ import annotations

import pytest

# ── BaseWorker tests ───────────────────────────────────────────────────────

def test_base_worker_importable() -> None:
    """BaseWorker must be importable (Qt available in test env)."""
    try:
        from ui_qt.components.base_worker import BaseWorker
        assert BaseWorker is not None
    except ImportError:
        pytest.skip("PySide6 not available in test environment")


def test_base_worker_has_signals() -> None:
    """BaseWorker must have progress, finished, failed signals."""
    try:
        from ui_qt.components.base_worker import BaseWorker
        # Check class attributes exist (signals are descriptors)
        assert hasattr(BaseWorker, 'progress')
        assert hasattr(BaseWorker, 'finished')
        assert hasattr(BaseWorker, 'failed')
    except ImportError:
        pytest.skip("PySide6 not available in test environment")


# ── HardwareMonitor pyNVML tests ──────────────────────────────────────────

def test_hardware_monitor_importable() -> None:
    """HardwareMonitor must be importable."""
    from core.system.hardware_monitor import HardwareMonitor
    assert HardwareMonitor is not None


def test_hardware_monitor_has_nvml_methods() -> None:
    """HardwareMonitor must have pyNVML backend methods."""
    from core.system.hardware_monitor import HardwareMonitor
    assert hasattr(HardwareMonitor, '_init_nvml')
    assert hasattr(HardwareMonitor, '_query_gpu_nvml')


def test_hardware_monitor_nvml_not_initialized_by_default() -> None:
    """HardwareMonitor should not initialize NVML until first query."""
    from core.system.hardware_monitor import HardwareMonitor
    hm = HardwareMonitor()
    assert hm._nvml_initialized is False
    assert hm._nvml_available is False


def test_hardware_monitor_poll_uses_nvml_first() -> None:
    """_poll_once should try NVML before nvidia-smi."""
    from core.system.hardware_monitor import HardwareMonitor
    hm = HardwareMonitor()
    # Mock NVML to return data, nvidia-smi to return empty
    hm._query_gpu_nvml = lambda: {"gpu_name": "Test GPU", "gpu_temp_c": 50}
    hm._query_gpu = lambda: {}
    hm._query_cpu_ram = lambda: {}
    snap = hm._poll_once()
    assert snap.gpu_name == "Test GPU"
    assert snap.gpu_temp_c == 50


def test_hardware_monitor_falls_back_to_nvidia_smi() -> None:
    """If NVML returns empty, should fall back to nvidia-smi."""
    from core.system.hardware_monitor import HardwareMonitor
    hm = HardwareMonitor()
    hm._query_gpu_nvml = lambda: {}  # NVML unavailable
    hm._query_gpu = lambda: {"gpu_name": "Fallback GPU", "gpu_temp_c": 60}
    hm._query_cpu_ram = lambda: {}
    snap = hm._poll_once()
    assert snap.gpu_name == "Fallback GPU"
    assert snap.gpu_temp_c == 60
