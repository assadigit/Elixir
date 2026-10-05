"""V18.19.2.4 (Crash Fix): characterization tests for the primary-call checkpoint.

The V18.19.2.3 golden-master run crashed during the additive-sections followup
LLM call (log ended at "num_ctx=17179 attempt…" with no traceback — a hard
process kill, likely GPU thermal/OOM). The primary call had already produced
good output (exec=1342, bullets=33, thorough=2887) but it was held in a local
`result` dict inside `_summarize_inner` — when the process died, that output
was LOST.

V18.19.2.4 fix: write the primary-call output to a checkpoint file
(``summaries/.checkpoints/primary_<heading>_summary.md``) BEFORE the
additive-sections / judge / postchecks phases. If any later phase crashes the
process, the user still has the recovered primary output.

These tests verify the checkpoint logic in isolation (without running the full
summarization pipeline, which needs Ollama).

Run: ``pytest tests/test_primary_call_checkpoint.py -v``
"""

from __future__ import annotations

from pathlib import Path

from utils.atomic_io import atomic_write_text

# ═══════════════════════════════════════════════════════════════════════════
# 1. The checkpoint logic (pure function mirror of summarizer.py:3000-3033)
# ═══════════════════════════════════════════════════════════════════════════


def _save_primary_checkpoint(
    output_dir: Path,
    heading: str,
    exec_summary: str,
    bullets: list,
    thorough: str,
) -> Path:
    """Mirror of the V18.19.2.4 checkpoint logic at summarizer.py:3000-3033.

    Writes the primary-call output to ``summaries/.checkpoints/`` so a later-
    phase crash doesn't lose it. Returns the checkpoint path.
    """
    import re

    _ckpt_dir = output_dir / "summaries" / ".checkpoints"
    _ckpt_dir.mkdir(parents=True, exist_ok=True)
    _safe_h = re.sub(r"[^A-Za-z0-9_\-]+", "_", heading)[:60].strip("_")
    _ckpt_path = _ckpt_dir / f"primary_{_safe_h}_summary.md"
    _bp_text = "\n".join(f"- {b}" for b in bullets)
    _ckpt_content = (
        f"# Summary (PRIMARY-CALL CHECKPOINT — V18.19.2.4)\n\n"
        f"## Chapter: {heading}\n\n"
        f"## Executive Summary\n\n{exec_summary}\n\n"
        f"## Key Takeaways\n\n{_bp_text}\n\n"
        f"## Thorough Summary\n\n{thorough}\n\n"
        f"<!-- PRIMARY-CALL CHECKPOINT — {len(bullets)} bullets -->\n"
    )
    atomic_write_text(_ckpt_path, _ckpt_content, encoding="utf-8")
    return _ckpt_path


class TestPrimaryCallCheckpoint:
    """The V18.19.2.4 checkpoint saves the primary output before later phases."""

    def test_checkpoint_written_with_all_sections(self, tmp_path):
        """The checkpoint file contains exec + bullets + thorough."""
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="1 - IDENTITY AND ITS ORIGINS",
            exec_summary="This chapter traces identity concepts.",
            bullets=["Tausk (1919) introduced identity.", "Erikson defined ego identity."],
            thorough="The thorough summary covers developmental origins.",
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "PRIMARY-CALL CHECKPOINT" in content
        assert "Executive Summary" in content
        assert "Key Takeaways" in content
        assert "Thorough Summary" in content
        assert "Tausk (1919)" in content
        assert "Erikson" in content

    def test_checkpoint_path_uses_safe_heading(self, tmp_path):
        """The heading is sanitized for the filename (no spaces/special chars)."""
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="1 - IDENTITY AND ITS ORIGINS",
            exec_summary="x",
            bullets=[],
            thorough="x",
        )
        assert "primary_1_-_IDENTITY_AND_ITS_ORIGINS" in path.name
        assert path.suffix == ".md"

    def test_checkpoint_in_checkpoints_subfolder(self, tmp_path):
        """The checkpoint goes to summaries/.checkpoints/ (not the main summaries/)."""
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="Test Chapter",
            exec_summary="x",
            bullets=[],
            thorough="x",
        )
        assert path.parent.name == ".checkpoints"
        assert path.parent.parent.name == "summaries"

    def test_checkpoint_creates_dirs_if_missing(self, tmp_path):
        """The summaries/.checkpoints/ dir is created if it doesn't exist."""
        output_dir = tmp_path / "deeply" / "nested" / "output"
        # Don't pre-create the dir — the function should make it
        path = _save_primary_checkpoint(
            output_dir=output_dir,
            heading="Test",
            exec_summary="x",
            bullets=[],
            thorough="x",
        )
        assert path.exists()

    def test_checkpoint_handles_empty_sections(self, tmp_path):
        """Empty exec/bullets/thorough don't crash the checkpoint."""
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="Test",
            exec_summary="",
            bullets=[],
            thorough="",
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "0 bullets" in content  # the marker shows 0 bullets

    def test_checkpoint_overwrites_on_rerun(self, tmp_path):
        """A second checkpoint write replaces the first (idempotent)."""
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="Test",
            exec_summary="first",
            bullets=[],
            thorough="",
        )
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="Test",
            exec_summary="second",
            bullets=[],
            thorough="",
        )
        content = path.read_text(encoding="utf-8")
        assert "second" in content
        assert "first" not in content

    def test_checkpoint_atomic(self, tmp_path):
        """The checkpoint uses atomic_write_text (no partial files on crash).

        Verifies atomic_write_text is used (the temp-file + os.replace pattern)
        — if the process crashes mid-write, the original file is untouched.
        """
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="Test",
            exec_summary="content",
            bullets=["b1"],
            thorough="t",
        )
        # No leftover .tmp files in the directory
        tmp_files = list(path.parent.glob(".*.tmp"))
        assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"


class TestV181923CrashScenario:
    """The exact V18.19.2.3 crash scenario: primary call succeeded, additive
    sections crashed — the checkpoint must have the primary output."""

    def test_primary_output_recovered_after_simulated_crash(self, tmp_path):
        """Simulate: primary call produces good output, then the process would
        crash at additive-sections. The checkpoint must contain the primary output."""
        # The primary-call output (from the V18.19.2.3 log at 15:20:43)
        exec_sum = (
            "This chapter synthesizes psychoanalytic and developmental "
            "writings on personal identity. Tausk (1919) first introduced "
            "the term into psychoanalytic literature."
        )
        bullets = [
            "Tausk (1919) introduced the term identity into psychoanalytic literature.",
            "Erikson (1956) defined ego identity as persistent sameness.",
            "Freud rarely used identity technically; 91 of 92 uses were colloquial.",
        ]
        thorough = (
            "The chapter traces identity from Tausk through Erikson to seven characteristics."
        )

        # Save the checkpoint (this happens BEFORE the additive-sections call)
        path = _save_primary_checkpoint(
            output_dir=tmp_path,
            heading="1 - IDENTITY AND ITS ORIGINS",
            exec_summary=exec_sum,
            bullets=bullets,
            thorough=thorough,
        )

        # Simulate the crash: the process dies. No final save happens.
        # But the checkpoint file exists on disk.
        assert path.exists(), "Checkpoint must exist after primary call"

        # The recovered output matches the primary call
        recovered = path.read_text(encoding="utf-8")
        assert "Tausk (1919)" in recovered
        assert "Erikson (1956)" in recovered
        assert "91 of 92" in recovered
        assert "PRIMARY-CALL CHECKPOINT" in recovered
