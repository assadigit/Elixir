"""V10.30.0 (Sprint 3.3): Unit tests for the unified quarantine system.

Tests the ``QuarantineLog`` class (``core/summarisation/quarantine.py``)
introduced in V10.28.0 Sprint 1.2.  Covers:

  - add() writes entries to in-memory list + drops.jsonl on disk
  - recover() resurrects only high-source-overlap actually-dropped bullets
  - conservative-mode entries (actually_dropped=False) are NOT recovered
  - load_from_disk() reads JSONL back
  - mark_recovered() updates the on-disk file
  - summary() returns a {stage: count} breakdown
  - DEFAULT_RECOVERY_THRESHOLD is 0.30
  - find_drops_log() locates the file for a book
  - None output_dir → in-memory only (no disk writes)
  - thread-safe: concurrent adds from multiple threads

The quarantine module is pure stdlib (json, threading, dataclasses).  We
load it directly via importlib to avoid the ``core.summarisation.__init__``
import chain (which pulls in ``Summarizer`` → ``tiktoken``, not installed
in the sandbox).

Run: ``pytest tests/test_quarantine.py -v``
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load quarantine.py directly, bypassing core.summarisation.__init__
# (which imports Summarizer → tiktoken, not available in the sandbox).
# The quarantine module is pure stdlib so this works cleanly.
_spec = importlib.util.spec_from_file_location(
    "core.summarisation.quarantine",
    _project_root / "core" / "summarisation" / "quarantine.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

DEFAULT_RECOVERY_THRESHOLD = _mod.DEFAULT_RECOVERY_THRESHOLD
QuarantineEntry = _mod.QuarantineEntry
QuarantineLog = _mod.QuarantineLog


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_log(tmp_path: Path) -> QuarantineLog:
    """A QuarantineLog pointing at a tmp output dir."""
    return QuarantineLog(output_dir=tmp_path)


@pytest.fixture
def no_disk_log() -> QuarantineLog:
    """A QuarantineLog with no output_dir (in-memory only)."""
    return QuarantineLog(output_dir=None)


# ── 1. add() writes to drops.jsonl ──────────────────────────────────────────


class TestAdd:
    def test_add_creates_drops_jsonl(self, tmp_log: QuarantineLog):
        """add() must create drops.jsonl on first write."""
        tmp_log.add("test bullet", stage="F4_source_overlap", source_overlap=0.18)
        assert tmp_log.drops_path is not None
        assert tmp_log.drops_path.exists()

    def test_add_writes_one_json_line_per_drop(self, tmp_log: QuarantineLog):
        """Each add() appends exactly one JSON line."""
        tmp_log.add("bullet A", stage="F4_source_overlap")
        tmp_log.add("bullet B", stage="B3_dedup")
        tmp_log.add("bullet C", stage="judge_grounding.ungrounded")
        lines = tmp_log.drops_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3

    def test_add_entry_has_all_fields(self, tmp_log: QuarantineLog):
        """The JSON line must contain all documented fields."""
        tmp_log.add(
            "test bullet", stage="F4_source_overlap",
            threshold=0.25, source_overlap=0.18, reason="overlap too low",
            chapter="Chapter 5", actually_dropped=True,
        )
        entry = json.loads(tmp_log.drops_path.read_text().splitlines()[0])
        assert entry["bullet"] == "test bullet"
        assert entry["stage"] == "F4_source_overlap"
        assert entry["threshold"] == 0.25
        assert entry["source_overlap"] == 0.18
        assert entry["reason"] == "overlap too low"
        assert entry["chapter"] == "Chapter 5"
        assert entry["actually_dropped"] is True
        assert entry["recovered"] is False
        assert "timestamp" in entry

    def test_add_returns_entry(self, tmp_log: QuarantineLog):
        """add() returns the QuarantineEntry for chaining."""
        e = tmp_log.add("x", stage="test")
        assert isinstance(e, QuarantineEntry)
        assert e.bullet == "x"
        assert e.stage == "test"

    def test_add_truncates_long_bullets(self, tmp_log: QuarantineLog):
        """Bullets >500 chars are truncated to keep the JSONL readable."""
        long_bullet = "A" * 800
        tmp_log.add(long_bullet, stage="test")
        entry = json.loads(tmp_log.drops_path.read_text().splitlines()[0])
        assert len(entry["bullet"]) == 500

    def test_add_count_property(self, tmp_log: QuarantineLog):
        """dropped_count tracks actually-dropped entries."""
        tmp_log.add("dropped", stage="t", actually_dropped=True)
        tmp_log.add("logged", stage="t", actually_dropped=False)
        tmp_log.add("dropped2", stage="t", actually_dropped=True)
        assert tmp_log.dropped_count == 2


# ── 2. recover() resurrects high-overlap bullets ───────────────────────────


class TestRecover:
    def test_recover_high_overlap_only(self, tmp_log: QuarantineLog):
        """recover() resurrects bullets with source_overlap > 0.30."""
        tmp_log.add("low overlap", stage="F4", source_overlap=0.10, actually_dropped=True)
        tmp_log.add("high overlap", stage="F4", source_overlap=0.45, actually_dropped=True)
        resurrected = tmp_log.recover(source_text="")
        assert len(resurrected) == 1
        assert resurrected[0].bullet == "high overlap"
        assert resurrected[0].recovered is True

    def test_recover_skips_conservative_logged(self, tmp_log: QuarantineLog):
        """conservative-mode entries (actually_dropped=False) are NOT recovered."""
        tmp_log.add("conservative", stage="B3", source_overlap=0.90, actually_dropped=False)
        resurrected = tmp_log.recover(source_text="")
        assert len(resurrected) == 0

    def test_recover_skips_already_recovered(self, tmp_log: QuarantineLog):
        """An already-recovered entry is not recovered again."""
        tmp_log.add("high", stage="F4", source_overlap=0.50, actually_dropped=True)
        first = tmp_log.recover(source_text="")
        assert len(first) == 1
        second = tmp_log.recover(source_text="")
        assert len(second) == 0

    def test_recover_threshold_is_0_30(self):
        """DEFAULT_RECOVERY_THRESHOLD must be 0.30 (Sprint 1.4 spec)."""
        assert DEFAULT_RECOVERY_THRESHOLD == 0.30

    def test_recover_updates_disk_file(self, tmp_log: QuarantineLog):
        """recover() marks the on-disk entry as recovered=true."""
        tmp_log.add("resurrect me", stage="F4", source_overlap=0.40, actually_dropped=True)
        tmp_log.recover(source_text="")
        entries = QuarantineLog.load_from_disk(tmp_log.drops_path)
        assert entries[0]["recovered"] is True

    def test_recover_logs_message(self, tmp_log: QuarantineLog):
        """recover() logs an INFO message when bullets are resurrected."""
        messages = []
        tmp_log._log = lambda msg, level="DEBUG": messages.append((msg, level))
        tmp_log.add("high", stage="F4", source_overlap=0.50, actually_dropped=True)
        tmp_log.recover(source_text="")
        assert any("resurrected" in m[0].lower() for m in messages)

    def test_recover_empty_log(self, tmp_log: QuarantineLog):
        """recover() on an empty log returns [] without crashing."""
        assert tmp_log.recover(source_text="") == []


# ── 3. load_from_disk + find_drops_log ──────────────────────────────────────


class TestDiskIO:
    def test_load_from_disk_reads_entries(self, tmp_log: QuarantineLog):
        """load_from_disk returns the entries as dicts."""
        tmp_log.add("a", stage="F4", source_overlap=0.1)
        tmp_log.add("b", stage="B3", source_overlap=0.0)
        entries = QuarantineLog.load_from_disk(tmp_log.drops_path)
        assert len(entries) == 2
        assert entries[0]["bullet"] == "a"
        assert entries[1]["stage"] == "B3"

    def test_load_from_disk_missing_file(self, tmp_path: Path):
        """load_from_disk returns [] for a non-existent file."""
        assert QuarantineLog.load_from_disk(tmp_path / "nonexistent.jsonl") == []

    def test_load_from_disk_skips_malformed_lines(self, tmp_log: QuarantineLog):
        """Malformed JSON lines are skipped (not crash)."""
        tmp_log.add("good", stage="F4")
        # Append a malformed line
        with open(tmp_log.drops_path, "a", encoding="utf-8") as f:
            f.write("{not valid json\n")
            f.write("\n")  # blank line
        entries = QuarantineLog.load_from_disk(tmp_log.drops_path)
        assert len(entries) == 1
        assert entries[0]["bullet"] == "good"

    def test_find_drops_log_locates_file(self, tmp_log: QuarantineLog):
        """find_drops_log returns the path when drops.jsonl exists."""
        tmp_log.add("x", stage="t")
        found = QuarantineLog.find_drops_log(tmp_log.drops_path.parent.parent)
        assert found is not None
        assert found.exists()
        assert found.name == "drops.jsonl"

    def test_find_drops_log_returns_none_when_missing(self, tmp_path: Path):
        """find_drops_log returns None when no drops.jsonl exists."""
        assert QuarantineLog.find_drops_log(tmp_path) is None


# ── 4. mark_recovered (manual restore) ──────────────────────────────────────


class TestMarkRecovered:
    def test_mark_recovered_updates_disk(self, tmp_log: QuarantineLog):
        """mark_recovered flips recovered=true on disk."""
        tmp_log.add("restore me", stage="F4", source_overlap=0.15)
        ok = tmp_log.mark_recovered("restore me")
        assert ok is True
        entries = QuarantineLog.load_from_disk(tmp_log.drops_path)
        assert entries[0]["recovered"] is True

    def test_mark_recovered_returns_false_for_missing(self, tmp_log: QuarantineLog):
        """mark_recovered returns False when the bullet isn't found."""
        tmp_log.add("present", stage="F4")
        assert tmp_log.mark_recovered("absent") is False

    def test_mark_recovered_idempotent(self, tmp_log: QuarantineLog):
        """mark_recovered on an already-recovered entry returns False."""
        tmp_log.add("once", stage="F4")
        assert tmp_log.mark_recovered("once") is True
        assert tmp_log.mark_recovered("once") is False


# ── 5. summary() breakdown ──────────────────────────────────────────────────


class TestSummary:
    def test_summary_counts_by_stage(self, tmp_log: QuarantineLog):
        """summary() returns {stage: count}."""
        tmp_log.add("a", stage="F4_source_overlap")
        tmp_log.add("b", stage="F4_source_overlap")
        tmp_log.add("c", stage="B3_dedup")
        tmp_log.add("d", stage="judge_grounding.ungrounded")
        s = tmp_log.summary()
        assert s == {
            "F4_source_overlap": 2,
            "B3_dedup": 1,
            "judge_grounding.ungrounded": 1,
        }

    def test_summary_empty(self, tmp_log: QuarantineLog):
        """summary() on an empty log returns {}."""
        assert tmp_log.summary() == {}


# ── 6. None output_dir (in-memory only) ─────────────────────────────────────


class TestInMemoryOnly:
    def test_none_output_dir_no_disk(self, no_disk_log: QuarantineLog):
        """When output_dir=None, no disk file is created."""
        assert no_disk_log.drops_path is None
        no_disk_log.add("in memory", stage="test")
        assert len(no_disk_log.entries) == 1

    def test_none_output_dir_recover_still_works(self, no_disk_log: QuarantineLog):
        """Recovery still works in-memory (no disk roundtrip)."""
        no_disk_log.add("high", stage="F4", source_overlap=0.50, actually_dropped=True)
        r = no_disk_log.recover(source_text="")
        assert len(r) == 1


# ── 7. Thread safety ────────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_adds(self, tmp_log: QuarantineLog):
        """1000 concurrent adds from 10 threads must all land."""
        def adder(n):
            for i in range(100):
                tmp_log.add(f"b-{n}-{i}", stage="concurrent")
        threads = [threading.Thread(target=adder, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(tmp_log.entries) == 1000
        lines = tmp_log.drops_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1000


# ── 8. entries property returns a copy ──────────────────────────────────────


class TestEntriesProperty:
    def test_entries_returns_copy(self, tmp_log: QuarantineLog):
        """entries returns a snapshot list — mutating it doesn't affect the log."""
        tmp_log.add("a", stage="t")
        snapshot = tmp_log.entries
        snapshot.clear()
        # The internal list is unchanged
        assert len(tmp_log.entries) == 1
