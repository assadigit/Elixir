"""V0.6.19 (W-e3): a headless CLI for podcast generation.

Why this exists
---------------
Before V0.6.19, the ONLY way to generate a podcast was through the
PySide6 wizard. If the operator wanted to debug a script-generation
failure or a TTS-engine crash, they had to launch the full Qt app,
paste the script, click the button, wait for the spinner, read the
log in the bottom panel. That's slow for a one-off test and
impossible in a headless / SSH context (the rig's CI, a remote
debugging session, a cron job).

This module gives the operator a single command:

    python -m core.podcast.cli generate \\
        --script /path/to/script.json \\
        --voice-a vibevoice:Carter \\
        --voice-b vibevoice:Erin \\
        --out /path/to/podcast.wav

The script JSON is the same format ``ScriptResult.to_json()`` produces
(see ``core.podcast.script_generator``) — so the wizard's "Export
script" button creates a file the CLI can re-import. The CLI runs the
new ``validate_script`` FIRST (V0.6.19 W-e2); if there are errors, it
prints them and exits 1 without ever spinning up the TTS subprocess.
If there are only warnings, it prints them and proceeds unless
``--strict`` is set.

The CLI also wires up a ``CancelToken`` (V0.6.18 W-d3) — pressing
Ctrl-C in the terminal calls ``token.cancel()`` and the line loop
exits at the next iteration boundary (the same UX the wizard's Stop
button will have once it's wired in).

This module is deliberately pure-Python (no Qt dependency) so it can
run in any context. The TTS engines still need torch/transformers,
but those are only imported when generation actually starts — the
``validate`` subcommand needs nothing heavy.

Subcommands:
  validate   — validate a script JSON, print the issues, exit 0/1.
  generate   — validate, then generate audio.
  info       — print the script's metadata (line count, mode, title,
               coverage) without validating or generating.

Examples:
  # Validate a script (no TTS subprocess started):
  python -m core.podcast.cli validate --script my_podcast.json

  # Generate a podcast (validates first; --strict makes warnings fatal):
  python -m core.podcast.cli generate --script my_podcast.json \\
      --voice-a vibevoice:Carter --voice-b vibevoice:Erin \\
      --out podcast.wav

  # Print the script's metadata:
  python -m core.podcast.cli info --script my_podcast.json
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_script_json(path: Path):  # type: ignore[no-untyped-def]
    """Load a ScriptResult from a JSON file (the format
    ScriptResult.to_json() produces)."""
    from core.podcast.script_generator import ScriptLine, ScriptResult

    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        ScriptLine(
            host=line["host"],
            text=line["text"],
            source_ref=line.get("source_ref", ""),
            segment_type=line.get("segment_type", "content"),
        )
        for line in data.get("lines", [])
    ]
    return ScriptResult(
        lines=lines,
        bullets_input=data.get("bullets_input", []),
        bullets_covered=data.get("bullets_covered", []),
        bullets_missing=data.get("bullets_missing", []),
        coverage_pct=data.get("coverage_pct", 0.0),
        retries=data.get("retries", 0),
        forced_segments=data.get("forced_segments", 0),
        error=data.get("error"),
        title=data.get("title", ""),
    )


def _log_to_stdout(msg: str, level: str = "INFO") -> None:
    """The LogFn the audio generator expects — prints to stdout with a
    timestamp + level prefix."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level:7s}] {msg}", flush=True)


def _cmd_validate(args: argparse.Namespace) -> int:
    """The validate subcommand — validate a script, print issues, exit."""
    from core.podcast.script_validator import (
        format_issues_for_display,
        validate_script,
    )

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"❌ Script file not found: {script_path}", file=sys.stderr)
        return 2
    try:
        script = _load_script_json(script_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse script JSON: {e}", file=sys.stderr)
        return 2

    # Mode inference: if any line is Host B, it's conversational.
    is_conversational = any(line.host == "B" for line in script.lines)
    result = validate_script(
        script,
        host_a_voice=args.voice_a or "",
        host_b_voice=args.voice_b or "",
        is_conversational=is_conversational,
    )
    output = format_issues_for_display(result, log=_log_to_stdout)
    print(output)
    if not result.ok:
        print(f"\n❌ {len(result.errors)} error(s) — fix them before generating.")
        return 1
    if result.warnings and args.strict:
        print(f"\n❌ --strict is set and there are {len(result.warnings)} warning(s).")
        return 1
    print(f"\n✅ OK — {len(result.warnings)} warning(s), {len(result.infos)} info(s).")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    """The info subcommand — print script metadata, no validation."""
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"❌ Script file not found: {script_path}", file=sys.stderr)
        return 2
    try:
        script = _load_script_json(script_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse script JSON: {e}", file=sys.stderr)
        return 2

    is_conversational = any(line.host == "B" for line in script.lines)
    host_a_count = sum(1 for line in script.lines if line.host == "A")
    host_b_count = sum(1 for line in script.lines if line.host == "B")
    other_count = len(script.lines) - host_a_count - host_b_count
    print(f"Title:           {script.title or '(none)'}")
    print(f"Mode:            {'conversational' if is_conversational else 'lecture'}")
    print(f"Total lines:     {len(script.lines)}")
    print(f"  Host A lines:  {host_a_count}")
    print(f"  Host B lines:  {host_b_count}")
    if other_count:
        print(f"  Other (?!):    {other_count}")
    print(f"Coverage:        {script.coverage_pct:.0f}%")
    if script.bullets_input:
        print(
            f"Bullets:         {len(script.bullets_covered)}/"
            f"{len(script.bullets_input)} covered "
            f"({len(script.bullets_missing)} missing, force-inserted)"
        )
    print(f"Retries:         {script.retries}")
    print(f"Forced segments: {script.forced_segments}")
    if script.error:
        print(f"Generation error: {script.error}")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    """The generate subcommand — validate, then generate audio."""
    from core.podcast.audio_generator import generate_podcast_audio
    from core.podcast.cancel_token import CancelToken
    from core.podcast.script_validator import (
        format_issues_for_display,
        validate_script,
    )

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"❌ Script file not found: {script_path}", file=sys.stderr)
        return 2
    try:
        script = _load_script_json(script_path)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Failed to parse script JSON: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    is_conversational = any(line.host == "B" for line in script.lines)

    # Step 1: validate.
    result = validate_script(
        script,
        host_a_voice=args.voice_a or "",
        host_b_voice=args.voice_b or "",
        is_conversational=is_conversational,
    )
    _log_to_stdout("── Script validation ──────────────────────────────", "INFO")
    format_issues_for_display(result, log=_log_to_stdout)
    if not result.ok:
        print(f"\n❌ {len(result.errors)} error(s) — aborting generation.", file=sys.stderr)
        return 1
    if result.warnings and args.strict:
        print(
            f"\n❌ --strict is set and there are {len(result.warnings)} warning(s) — aborting.",
            file=sys.stderr,
        )
        return 1
    _log_to_stdout("✅ Validation passed — starting audio generation.", "INFO")

    # Step 2: set up the cancel token + Ctrl-C handler.
    token = CancelToken()

    def _on_sigint(_sig, _frame):  # noqa: ANN001
        _log_to_stdout(
            "⏹️ Ctrl-C received — cancelling at the next line boundary "
            "(mid-line cancel is NOT supported; the current line will finish).",
            "WARNING",
        )
        token.cancel("Ctrl-C from CLI")

    signal.signal(signal.SIGINT, _on_sigint)

    # Step 3: settings stub. The audio generator reads:
    #   tts.vibevoice_model_path, tts.vibevoice_voices_dir
    # from the settings object (a duck-type — only .get is needed).
    # The CLI passes them through --vv-model and --vv-voices flags.
    settings = {
        "tts.vibevoice_model_path": args.vv_model or "",
        "tts.vibevoice_voices_dir": args.vv_voices or "",
    }

    # Step 4: progress callback.
    def _progress(pct: int, msg: str) -> None:
        _log_to_stdout(f"[{pct:3d}%] {msg}", "INFO")

    # Step 5: generate.
    _log_to_stdout("── Audio generation ──────────────────────────────", "INFO")
    start = time.time()
    result_path = generate_podcast_audio(
        script=script,
        out_path=out_path,
        host_a_voice=args.voice_a or "",
        host_b_voice=args.voice_b or "",
        settings=settings,
        log_callback=_log_to_stdout,
        progress_callback=_progress,
        cancel_token=token,
    )
    elapsed = time.time() - start

    if result_path is None:
        if token.cancelled:
            print(
                f"\n⏹️ Generation cancelled ({token.reason}) after {elapsed:.1f}s. "
                f"No audio file produced.",
                file=sys.stderr,
            )
            return 130  # the conventional "killed by SIGINT" exit code
        print(
            f"\n❌ Generation failed after {elapsed:.1f}s. See the log above.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\n✅ Podcast generated in {elapsed:.1f}s: {result_path} "
        f"({result_path.stat().st_size:,} bytes)",
        flush=True,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Top-level subcommands: validate, generate, info."""
    parser = argparse.ArgumentParser(
        prog="python -m core.podcast.cli",
        description=(
            "V0.6.19 (W-e3): headless podcast CLI. Validates a script JSON, "
            "then generates audio without launching the Qt wizard. "
            "Ctrl-C cancels at the next line boundary (V0.6.18 CancelToken)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # validate
    p_validate = sub.add_parser("validate", help="Validate a script JSON; print issues; exit 0/1.")
    p_validate.add_argument("--script", required=True, help="Path to the script JSON.")
    p_validate.add_argument("--voice-a", default="", help="Host A voice (for E4/W5 checks).")
    p_validate.add_argument("--voice-b", default="", help="Host B voice (for E4 check).")
    p_validate.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as fatal (exit 1).",
    )
    p_validate.set_defaults(func=_cmd_validate)

    # generate
    p_gen = sub.add_parser("generate", help="Validate + generate a podcast WAV (Ctrl-C cancels).")
    p_gen.add_argument("--script", required=True, help="Path to the script JSON.")
    p_gen.add_argument("--voice-a", required=True, help="Voice for Host A (e.g. vibevoice:Carter).")
    p_gen.add_argument(
        "--voice-b",
        default="",
        help="Voice for Host B (may be empty in lecture mode).",
    )
    p_gen.add_argument(
        "--out",
        required=True,
        help="Output WAV path (will be created / overwritten).",
    )
    p_gen.add_argument(
        "--vv-model",
        default="",
        help="VibeVoice model path (Settings → TTS → VibeVoice model path).",
    )
    p_gen.add_argument(
        "--vv-voices",
        default="",
        help="VibeVoice voices dir (Settings → TTS → VibeVoice voices dir).",
    )
    p_gen.add_argument(
        "--strict",
        action="store_true",
        help="Treat validation warnings as fatal (don't generate).",
    )
    p_gen.set_defaults(func=_cmd_generate)

    # info
    p_info = sub.add_parser(
        "info", help="Print the script's metadata (no validation, no generation)."
    )
    p_info.add_argument("--script", required=True, help="Path to the script JSON.")
    p_info.set_defaults(func=_cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    """The CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
