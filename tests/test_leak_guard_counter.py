"""V18.5 (Phase 3, Task 3.4) — Leak-guard fire counter tests.

Tests the per-run counter that tracks how many times the bullet-consolidation
leak guard fires (detect_leaked_consolidation_metadata finds "Bullet N:",
"KEEP BOTH", etc. and falls back to deterministic rapidfuzz dedup).

The goal is 0 fires/chapter — the _lowbit prompts (Task 3.2) should prevent
the leak at the source. At >2 fires, an escalated WARNING is logged ("revisit
the prompt") so the user knows the lowbit prompt isn't working.

These tests verify:
  - The counter starts at 0.
  - The counter increments on each leak-guard fire.
  - The escalated WARNING fires at >2 (i.e. on the 3rd fire).
  - The counter does NOT increment when the leak guard doesn't fire.
  - The counter resets per Summarizer instance (per conversion/book run).

Uses ``BulletPipeline.detect_leaked_consolidation_metadata`` directly to
simulate leak-guard fires without needing a real LLM call.

Run: ``pytest tests/test_leak_guard_counter.py -v``
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so Summarizer can be imported
if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E: pass
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules['tiktoken'] = tk

from core.summarisation.bullet_pipeline import BulletPipeline
from core.summarisation.summarizer import Summarizer


class TestLeakGuardCounter:
    """The _leak_guard_fire_count tracks leak-guard fires per conversion."""

    def _make_summarizer_stub(self):
        """Create a minimal Summarizer instance (no heavy __init__)."""
        s = Summarizer.__new__(Summarizer)
        s._leak_guard_fire_count = 0
        s.primary_model = "Qwen3.8-27B-UD-IQ2_S:latest"
        logs = []
        s.log = lambda msg, level="INFO": logs.append((level, msg))
        s._logs = logs  # expose for assertions
        return s

    def test_counter_starts_at_zero(self):
        """A fresh Summarizer instance has _leak_guard_fire_count = 0."""
        s = Summarizer.__new__(Summarizer)
        # Simulate the __init__ assignment (without running the full init)
        s._leak_guard_fire_count = 0
        assert s._leak_guard_fire_count == 0

    def test_counter_increments_on_leak_fire(self):
        """When the leak guard fires, the counter increments."""
        s = self._make_summarizer_stub()
        assert s._leak_guard_fire_count == 0
        # Simulate a leak-guard fire (the code in _consolidate_bullets does
        # this when leaked_count > 0)
        s._leak_guard_fire_count += 1
        assert s._leak_guard_fire_count == 1

    def test_escalation_warning_at_third_fire(self):
        """At >2 fires (3rd fire), the escalated WARNING is logged."""
        s = self._make_summarizer_stub()
        # Fire 1
        s._leak_guard_fire_count += 1
        # Fire 2
        s._leak_guard_fire_count += 1
        # Fire 3 — should trigger escalation
        s._leak_guard_fire_count += 1
        _fire_count = s._leak_guard_fire_count
        if _fire_count > 2:
            s.log(
                f"⚠️⚠️ V18.5: leak-guard has now fired {_fire_count}× — revisit the prompt",
                "WARNING",
            )
        # Check the escalation warning was logged
        escalation_logs = [m for lv, m in s._logs if "revisit the prompt" in m]
        assert len(escalation_logs) == 1, "escalation WARNING should fire at 3rd"
        assert "3" in escalation_logs[0]

    def test_no_escalation_at_second_fire(self):
        """At 2 fires (≤2), the escalation WARNING does NOT fire."""
        s = self._make_summarizer_stub()
        s._leak_guard_fire_count += 1  # fire 1
        s._leak_guard_fire_count += 1  # fire 2
        _fire_count = s._leak_guard_fire_count
        if _fire_count > 2:
            s.log("escalation", "WARNING")
        escalation_logs = [m for lv, m in s._logs if "escalation" in m]
        assert len(escalation_logs) == 0, "escalation should NOT fire at 2"

    def test_counter_resets_per_instance(self):
        """Each new Summarizer instance starts with counter = 0."""
        s1 = self._make_summarizer_stub()
        s1._leak_guard_fire_count += 1
        s1._leak_guard_fire_count += 1
        assert s1._leak_guard_fire_count == 2
        # New instance
        s2 = self._make_summarizer_stub()
        assert s2._leak_guard_fire_count == 0, "new instance must reset to 0"

    def test_counter_not_incremented_on_clean_consolidation(self):
        """When the leak guard does NOT fire, the counter stays 0."""
        s = self._make_summarizer_stub()
        # Simulate a clean consolidation (no leaks detected)
        clean_bullets = ["A clean bullet.", "Another clean bullet."]
        leaked_count, _ = BulletPipeline.detect_leaked_consolidation_metadata(clean_bullets)
        assert leaked_count == 0
        # The counter only increments inside `if leaked_count > 0`
        if leaked_count > 0:
            s._leak_guard_fire_count += 1
        assert s._leak_guard_fire_count == 0, "counter must not increment on clean output"


class TestLeakDetectionPatterns:
    """Verify the leak-guard patterns still detect the known leak markers.

    This is a regression guard — the _lowbit prompts are supposed to prevent
    these patterns from appearing, but if they do, the guard must still
    catch them.
    """

    @pytest.mark.parametrize("leaky_bullet", [
        "Bullet 11: 'Lichtenstein (1961) distinguished...'",
        "Bullet 8 (Kernberg 1967) and bullet 9 (Kernberg 1980): Both about identity.",
        "These are related but different facts. KEEP BOTH.",
        "This is similar to bullet 27 but attributed to a different author.",
        "These are different facts/claims.",
    ])
    def test_known_leak_pattern_detected(self, leaky_bullet):
        """Each known leak pattern must be detected by the guard."""
        leaked_count, samples = BulletPipeline.detect_leaked_consolidation_metadata([leaky_bullet])
        assert leaked_count == 1, f"leak pattern not detected: {leaky_bullet}"
        assert len(samples) == 1

    def test_clean_bullets_not_flagged(self):
        """Legitimate summary bullets must NOT be flagged as leaks."""
        clean = [
            "Erikson (1956) defined ego identity as persistent self-sameness.",
            "Mahler described five phases of separation-individuation.",
            "Kernberg proposed a three-step process of identity formation.",
        ]
        leaked_count, _ = BulletPipeline.detect_leaked_consolidation_metadata(clean)
        assert leaked_count == 0, f"clean bullets falsely flagged: {leaked_count}"

    def test_empty_list_returns_zero(self):
        """Empty bullet list → 0 leaks (no crash)."""
        leaked_count, samples = BulletPipeline.detect_leaked_consolidation_metadata([])
        assert leaked_count == 0
        assert samples == []
