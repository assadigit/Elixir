"""V0.6.56 — Transcribe pipeline live-log formatting (Qt-free leaf).

WHY: the operator ran a real 15-minute video through the Transcribe
Service and waited 10 minutes with no way to tell FROZEN from
PROGRESSING. The dialog now ships the internal log container every
other tool already has, fed by two things this module provides:

  - ``format_run_header``: the lines logged when a run starts (what
    file, what engine, what model, which outputs) — the operator can
    verify the run is configured the way they think it is.
  - ``format_heartbeat_line``: a periodic "still alive" line that
    carries the elapsed time, how long the pipeline has been SILENT
    (the real frozen-vs-progressing signal), and — when the silence is
    long — the hint about what is usually silently slow (whisper model
    load, an LLM that fell back to CPU after a GPU-fit failure).

This module is deliberately stdlib-only (no Qt, no app imports): the
dialog imports it lazily, and the test suite imports it directly in
sandboxes without PySide6.
"""

from __future__ import annotations

from pathlib import Path

# Silence gap (seconds) after which the heartbeat appends the "what is
# usually silently slow" hint. 2 minutes: short silences (ffmpeg
# conversion, segment flushes) are normal; 2+ minutes of zero pipeline
# output is exactly the ambiguity the operator reported.
SILENCE_HINT_AFTER_S = 120.0

# Heartbeat cadence (ms) — the dialog's QTimer interval. Every 15s the
# log gains a timestamped heartbeat, so a working run visibly ticks and
# a silent phase is measurable (vs. a hard hang, which stops time
# itself only for the pipeline — the log keeps proving the UI is alive).
HEARTBEAT_INTERVAL_MS = 15_000


def _fmt_mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def _fmt_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 ** 3):.1f} GB"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 ** 2):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def format_heartbeat_line(
    *,
    run_started_ts: float,
    last_update_ts: float,
    now_ts: float,
    last_msg: str,
) -> str:
    """Build the ``⏱`` heartbeat line for the live log.

    ``*_ts`` are ``time.time()`` epoch seconds. The line reads::

        ⏱ still working — 03:15 elapsed, last pipeline update 45s ago
        (whisper model load / LLM on CPU can be silent for minutes;
        use 🔌 Test to check the LLM)

    The parenthesized hint appears only when the silence gap exceeds
    :data:`SILENCE_HINT_AFTER_S` — a 15s gap between normal updates
    would be noise, not signal.
    """
    elapsed = max(0.0, now_ts - run_started_ts)
    gap = max(0.0, now_ts - last_update_ts)
    last = (last_msg or "").strip().replace("\n", " ")
    if len(last) > 80:
        last = last[:77] + "..."
    line = (
        f"⏱ still working — {_fmt_mmss(elapsed)} elapsed, "
        f"last pipeline update {int(gap)}s ago"
    )
    if last:
        line += f": {last}"
    if gap >= SILENCE_HINT_AFTER_S:
        line += (
            " — engine silent (whisper model load / LLM on CPU can take "
            "minutes; 🔌 Test checks the LLM, kill + retry if it never advances)"
        )
    return line


def format_run_header(
    *,
    filepath: str,
    engine: str | None,
    whisper_model: str | None,
    llm_model: str | None,
    save_raw: bool,
    save_summary: bool,
    save_tutorial: bool,
) -> list[str]:
    """The run-start log lines: what is about to happen, to what file.

    Returns a list (not one blob) so the dialog appends each line with
    its own timestamp — the live log stays line-addressable.
    """
    lines: list[str] = []
    p = Path(filepath)
    try:
        size = _fmt_size(p.stat().st_size)
        lines.append(f"🎙️ Run started: {p.name} ({size})")
    except OSError:
        lines.append(f"🎙️ Run started: {p.name}")

    if engine:
        lines.append(f"⚙️ Engine: {engine}")
    if whisper_model:
        lines.append(f"🧠 Whisper model: {whisper_model}")

    needs_llm = save_summary or save_tutorial
    if needs_llm:
        lines.append(f"🤖 LLM: {llm_model or '(auto-detected)'}")

    outputs = []
    if save_raw:
        outputs.append("raw transcript")
    if save_summary:
        outputs.append("summary")
    if save_tutorial:
        outputs.append("tutorial")
    if outputs:
        lines.append(f"📦 Outputs: {' + '.join(outputs)}")
    return lines
