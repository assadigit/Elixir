"""V0.6.26 (W-k1): export a podcast script to SRT / HTML / Markdown.

Why this exists
---------------
The wizard's "Export Script" button (V11.37.0) writes a JSON file
(the `ScriptResult.to_json()` format from V0.6.24). That's the
machine-readable format — useful for re-importing into the wizard or
feeding to the CLI's `generate` subcommand, but NOT useful for:

  - **Subtitles**: the operator wants to overlay the dialogue as
    subtitles on the generated podcast audio (for accessibility, for
    silent viewing, for a video version). The SRT format is the de-
    facto standard for subtitles; it needs timestamped cue entries.
  - **A blog post / show notes**: the operator wants to publish the
    transcript as an HTML page or a Markdown file alongside the
    podcast. The JSON format is useless for this.

Before V0.6.26, the only non-JSON export was `to_dialogue_text()`
(V11.37.0) — a plain-text render with `[Host A]` prefixes. No SRT,
no HTML, no Markdown. This module fills the gap.

The SRT exporter uses the V0.6.20 `estimate_duration_seconds()`
function to compute per-line timestamps (word_count × WPM). This is
an ESTIMATE — the actual audio duration depends on the TTS engine's
pacing, pauses, and overlap. The operator can adjust the SRT
timestamps after generation if needed. The estimate is good enough
for a draft (the typical error is ±10-15% per line, which compounds
across a long script — but for a 20-line podcast the drift is usually
under 30 seconds, acceptable for a draft subtitle).

Public API:
  - ``export_to_srt(script, wpm=None)`` — SRT subtitle format with
    estimated timestamps.
  - ``export_to_html(script)`` — a standalone HTML page with the
    dialogue.
  - ``export_to_markdown(script)`` — a Markdown page with the dialogue.
  - ``EXPORT_FORMATS`` — dict of {name: (description, exporter_func)}.
  - ``export(script, format, wpm=None)`` — dispatch by format name.
"""

from __future__ import annotations

from collections.abc import Callable

from core.podcast.script_generator import ScriptResult
from core.podcast.script_stats import (
    DEFAULT_WPM,
    FARSI_DEFAULT_WPM,
    _is_farsi_text,
    estimate_duration_seconds,
)

# ── SRT timestamp helpers ──────────────────────────────────────────────────


def _format_srt_timestamp(seconds: float) -> str:
    """Format a duration in seconds as an SRT timestamp: HH:MM:SS,mmm.

    SRT uses commas (not periods) for the milliseconds separator.
    Example: 73.5 -> "00:01:13,500".
    """
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


# ── SRT exporter ───────────────────────────────────────────────────────────


def export_to_srt(script: ScriptResult, wpm: int | None = None) -> str:
    """Export a ScriptResult to SRT subtitle format.

    Each script line becomes one SRT cue:
      - The cue index (1-based).
      - The start + end timestamps (estimated from word count × WPM).
      - The cue text: "[Host A] line text" (so the viewer knows who's
        speaking).

    Args:
        script: the ScriptResult to export.
        wpm: optional WPM override (default: 150 EN / 130 FA, auto-detected).

    Returns:
        A string in SRT format. Empty script → empty string.
    """
    if not script.lines:
        return ""

    # Auto-detect Farsi for the WPM (same logic as V0.6.20 compute_stats).
    all_text = " ".join(ln.text for ln in script.lines)
    if wpm is None:
        wpm = FARSI_DEFAULT_WPM if _is_farsi_text(all_text) else DEFAULT_WPM

    cues: list[str] = []
    current_time = 0.0  # cumulative time across all lines

    for i, line in enumerate(script.lines):
        word_count = len(line.text.split())
        duration = estimate_duration_seconds(word_count, wpm)
        start = current_time
        end = current_time + duration
        # The cue text includes the host prefix so the viewer knows who's
        # speaking (SRT doesn't have a separate "speaker" field).
        cue_text = f"[Host {line.host}] {line.text}"
        cues.append(
            f"{i + 1}\n"
            f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n"
            f"{cue_text}\n"
        )
        current_time = end

    return "\n".join(cues)


# ── HTML exporter ───────────────────────────────────────────────────────────


def export_to_html(script: ScriptResult) -> str:
    """Export a ScriptResult to a standalone HTML page.

    The page has:
      - A `<title>` + `<h1>` with the script's title (or "Untitled Podcast").
      - A `<dialog>` or `<dl>` structure with each line as a
        `<dt>[Host A]</dt><dd>line text</dd>` pair.
      - Minimal inline CSS (no external stylesheet dependency).

    Args:
        script: the ScriptResult to export.

    Returns:
        A string of standalone HTML.
    """
    title = script.title or "Untitled Podcast"
    lines_html: list[str] = []
    for line in script.lines:
        host_class = "host-a" if line.host == "A" else "host-b"
        lines_html.append(
            f'    <div class="line {host_class}">\n'
            f'      <span class="speaker">Host {line.host}:</span>\n'
            f'      <span class="text">{_html_escape(line.text)}</span>\n'
            f"    </div>"
        )
    lines_block = (
        "\n".join(lines_html) if lines_html else ('    <p class="empty">(empty script)</p>')
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{_html_escape(title)}</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, sans-serif; max-width: 720px; "
        "margin: 2em auto; padding: 0 1em; line-height: 1.6; color: #333; }\n"
        "    h1 { border-bottom: 2px solid #ddd; padding-bottom: 0.3em; }\n"
        "    .line { margin: 1em 0; padding: 0.5em 0.75em; border-radius: 4px; }\n"
        "    .host-a { background: #f0f7ff; border-left: 3px solid #4a90d9; }\n"
        "    .host-b { background: #fff5f0; border-left: 3px solid #d9754a; }\n"
        "    .speaker { font-weight: bold; margin-right: 0.5em; }\n"
        "    .text { white-space: pre-wrap; }\n"
        "    .empty { color: #999; font-style: italic; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{_html_escape(title)}</h1>\n"
        f"{lines_block}\n"
        "</body>\n"
        "</html>"
    )


# ── Markdown exporter ───────────────────────────────────────────────────────


def export_to_markdown(script: ScriptResult) -> str:
    """Export a ScriptResult to a Markdown page.

    The page has:
      - An `# Title` H1 heading.
      - Each line as a blockquote with `**Host A:** line text`.

    Args:
        script: the ScriptResult to export.

    Returns:
        A string of Markdown.
    """
    title = script.title or "Untitled Podcast"
    parts: list[str] = [f"# {title}", ""]
    if not script.lines:
        parts.append("*(empty script)*")
        return "\n".join(parts)
    for line in script.lines:
        parts.append(f"> **Host {line.host}:** {line.text}")
        parts.append("")  # blank line between blockquotes
    return "\n".join(parts).rstrip() + "\n"


# ── HTML escaping helper ────────────────────────────────────────────────────


def _html_escape(text: str) -> str:
    """Escape HTML special characters (&, <, >, \", ')."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ── The format registry + dispatcher ────────────────────────────────────────


# The registry: {format_name: (description, exporter_func)}.
# The exporter_func takes (script, wpm) — the wpm param is only used by SRT;
# HTML and Markdown ignore it.
EXPORT_FORMATS: dict[str, tuple[str, Callable[..., str]]] = {
    "srt": (
        "SRT subtitle format with estimated timestamps (word count × WPM).",
        export_to_srt,
    ),
    "html": (
        "Standalone HTML page with the dialogue (inline CSS, no external deps).",
        export_to_html,
    ),
    "markdown": (
        "Markdown page with the dialogue (blockquote per line).",
        export_to_markdown,
    ),
}


def export(
    script: ScriptResult,
    format: str,
    wpm: int | None = None,
) -> str:
    """Export a ScriptResult to the named format.

    Args:
        script: the ScriptResult to export.
        format: one of "srt", "html", "markdown".
        wpm: optional WPM override (only used by SRT; HTML/Markdown ignore it).

    Returns:
        The exported string.

    Raises:
        ValueError: if the format is unknown (lists the available formats).
    """
    if format not in EXPORT_FORMATS:
        available = ", ".join(sorted(EXPORT_FORMATS.keys()))
        raise ValueError(f"Unknown export format: {format!r}. Available: {available}.")
    _description, exporter_func = EXPORT_FORMATS[format]
    # HTML and Markdown exporters take only (script); SRT takes (script, wpm).
    # Use inspect to call with the right signature — or just try/except.
    if format == "srt":
        return exporter_func(script, wpm)
    return exporter_func(script)


def list_formats() -> list[tuple[str, str]]:
    """List the available export formats as [(name, description), ...]."""
    return [(name, desc) for name, (desc, _func) in EXPORT_FORMATS.items()]


def format_formats_for_display(
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format the available export formats as a multi-line listing."""
    parts: list[str] = []
    parts.append("📤 Available Podcast Script Export Formats")
    parts.append("═" * 60)
    for name, (desc, _func) in EXPORT_FORMATS.items():
        parts.append(f"  {name:10s}  {desc}")
    parts.append("")
    parts.append(
        "Use `python -m core.podcast.cli export --script FILE --format "
        "<NAME> [--out FILE]` to export."
    )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out
