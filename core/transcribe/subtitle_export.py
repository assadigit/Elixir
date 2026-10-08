"""V0.6.62 -- the subtitle export leaf: segments -> SRT / WebVTT.

WHY THIS MODULE EXISTS
----------------------
The transcribe tool's engine has parsed timestamped segments since
the V0.6.55 P6 parser work, but the only outputs were transcript.md
/ summary.md / tutorial.md -- the app that transcribes VIDEO could
not emit the one deliverable video tools actually consume: subtitle
files. This leaf turns the engine's ``segments`` list (``{"start":
float, "end": float, "text": str}``) into the two universal subtitle
formats:

  - SRT   (``HH:MM:SS,mmm`` -- the COMMA standard; VLC, Premiere,
    YouTube, every editor)
  - WebVTT (``HH:MM:SS.mmm`` -- the DOT standard; HTML5 ``<track>``,
    web players)

DESIGN RULES (each pinned in tests/test_v0662_subtitle_export.py)
------------------------------------------------------------------
  - WORDS ARE NEVER DROPPED. ``wrap_cue_text`` wraps at word
    boundaries up to the broadcast-standard 2 x 42-char cue; content
    that does not fit MERGES INTO THE LAST LINE (growing it past 42)
    rather than being ellipsized away. For a TRANSCRIPT, missing
    words are worse than a long line (players wrap long lines
    themselves).
  - Honesty over invention: no segments -> ``cues: 0`` and NO file
    (an empty .srt is a broken deliverable); a write failure ->
    ``error`` key, never a raise (the transcription already
    succeeded by the time subtitles are written -- a bad output
    folder must not retro-fail the run).
  - Cue hygiene: empty-text segments are skipped with CONTIGUOUS
    numbering; inverted timestamps (end < start, a parser edge)
    clamp to zero length; a stray ``-->`` inside cue text (the SRT
    structure delimiter) is sanitized so it can never forge a
    phantom timing line; ``\\r`` is normalized away.
  - Timestamp rounding: ``int(ms + 0.5)`` after clamping negatives
    and non-finite values. THE HALF-UP CHOICE IS LOAD-BEARING: the
    ``seconds * 1000`` product CAN land exactly on k+0.5 (proved:
    ``0.0025 * 1000.0 == 2.5`` exactly — the float representation
    error cancels), and Python's ``round()`` would round such halves
    to EVEN (``round(2.5) == 2``). Never refactor ``int(ms + 0.5)``
    into ``round()`` — the pinned observable is the carry
    (59.9999999 -> 00:01:00,000) and the half-up boundary
    (0.0025 -> 00:00:00,003).

Qt-free, stdlib-only (the house leaf rule): importable and testable
without PySide6, and reusable by any future headless/batch caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

# The broadcast-standard cue shape: at most 2 lines of ~42 chars.
MAX_CUE_LINE_CHARS = 42
MAX_CUE_LINES = 2

# The sanitized replacement for a stray "-->" inside cue text (an
# arrow glyph -- visually close, structurally inert).
_ARROW = "-\u203a"  # "-›"


# ── timestamps ──────────────────────────────────────────────────────────────


def _to_ms(seconds: object) -> int:
    """Seconds (tolerant: negative/non-finite/None -> 0) -> int ms,
    rounded half-up. The never-exact-half-ms property (see module
    docstring) makes this deterministic for every float input."""
    try:
        sec = float(seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    if sec != sec or sec in (float("inf"), float("-inf")):  # nan / +-inf
        return 0
    if sec < 0.0:
        return 0
    return int(sec * 1000.0 + 0.5)


def _srt_ts(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def _vtt_ts(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def format_srt_timestamp(seconds: float) -> str:
    """``3661.5`` -> ``"01:01:01,500"`` (the SRT comma standard)."""
    return _srt_ts(_to_ms(seconds))


def format_vtt_timestamp(seconds: float) -> str:
    """``3661.5`` -> ``"01:01:01.500"`` (the WebVTT dot standard)."""
    return _vtt_ts(_to_ms(seconds))


# ── cue text hygiene ────────────────────────────────────────────────────────


def _sanitize_cue_text(text: object) -> str:
    """Normalize one segment's text for cue display: str() coercion
    (None -> ""), CR/CRLF -> LF, a stray '-->' sanitized (it is the
    SRT/VTT timing delimiter -- a transcript line like 'drag a --> b'
    must not forge a phantom cue header), outer whitespace stripped."""
    t = str(text) if text is not None else ""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    if "-->" in t:
        t = t.replace("-->", _ARROW)
    return t.strip()


def wrap_cue_text(
    text: str, max_chars: int = MAX_CUE_LINE_CHARS, max_lines: int = MAX_CUE_LINES
) -> str:
    """Wrap cue text to the broadcast-standard shape.

    Greedy word wrap up to ``max_lines`` lines of ``max_chars``; a
    single word longer than ``max_chars`` (a URL, an unbroken token)
    is hard-split at the limit. Content that still does not fit
    MERGES INTO THE LAST LINE (which may exceed ``max_chars``) --
    words are never dropped (see the module docstring: honest over
    pretty). All whitespace (including the segment's internal
    newlines) folds to single spaces: display reflow, not data loss.
    Degenerate params are clamped (``max_chars``/``max_lines`` < 1
    become 1) -- the hard-split loop could never shrink a word
    otherwise. ``None`` -> the empty string. The caller of a
    multi-pass pipeline should pass a re-iterable ``segments`` (a
    list); a bare generator is consumed by the first pass.
    """
    words = ("" if text is None else str(text)).split()
    if not words:
        return ""

    max_chars = max(1, int(max_chars))
    max_lines = max(1, int(max_lines))
    lines: list[str] = []
    cur = ""
    for word in words:
        # Hard-split an over-long unbroken token, flushing the line
        # under construction first so the pieces align at the limit.
        while len(word) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(word[:max_chars])
            word = word[max_chars:]
        cand = f"{cur} {word}".strip()
        if len(cand) <= max_chars or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    if len(lines) > max_lines:
        # Never drop: the tail becomes part of the last kept line.
        head = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :])
        lines = head + [tail]
    return "\n".join(lines)


# ── cue iteration ───────────────────────────────────────────────────────────

_Cue = tuple[int, int, int, str]  # (number, start_ms, end_ms, text)


def _iter_cues(segments: Iterable[object] | None) -> Iterator[_Cue]:
    """Yield the displayable cues: empty-text segments skipped,
    numbering contiguous, end clamped up to start."""
    n = 0
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        text = _sanitize_cue_text(seg.get("text", ""))
        if not text:
            continue
        start = _to_ms(seg.get("start", 0.0))
        end = max(_to_ms(seg.get("end", 0.0)), start)
        n += 1
        yield n, start, end, text


def _srt_from_cues(cues: list[_Cue], *, wrap: bool) -> str:
    blocks = []
    for n, start, end, text in cues:
        body = wrap_cue_text(text) if wrap else _fold_blank_lines(text)
        blocks.append(f"{n}\n{_srt_ts(start)} --> {_srt_ts(end)}\n{body}\n")
    return "\n".join(blocks)


def _vtt_from_cues(cues: list[_Cue], *, wrap: bool) -> str:
    if not cues:
        return "WEBVTT\n"
    blocks = []
    for _n, start, end, text in cues:
        body = wrap_cue_text(text) if wrap else _fold_blank_lines(text)
        blocks.append(f"{_vtt_ts(start)} --> {_vtt_ts(end)}\n{body}\n")
    return "WEBVTT\n\n" + "\n".join(blocks)


def _fold_blank_lines(text: str) -> str:
    """The wrap=False path still must not emit a blank line inside a
    cue -- a blank line TERMINATES an SRT/VTT cue, so the block would
    split in two. Drop blank lines entirely, keep the real lines."""
    return "\n".join(ln.rstrip() for ln in str(text).split("\n") if ln.strip())


# ── public API ──────────────────────────────────────────────────────────────


def segments_to_srt(segments: Iterable[object] | None, *, wrap: bool = True) -> str:
    """Segments -> the SRT document (numbered comma-timestamp cues,
    one blank line between blocks, single trailing newline). Empty
    input -> the empty string."""
    return _srt_from_cues(list(_iter_cues(segments)), wrap=wrap)


def segments_to_vtt(segments: Iterable[object] | None, *, wrap: bool = True) -> str:
    """Segments -> the WebVTT document (``WEBVTT`` header + dot-
    timestamp cues, no cue identifiers -- the minimal valid form).
    Empty input -> the bare header."""
    return _vtt_from_cues(list(_iter_cues(segments)), wrap=wrap)


def subtitle_stats(segments: Iterable[object] | None) -> dict:
    """The honest summary for callers that want it: how many cues the
    subtitles carry and where the coverage ends (the FURTHEST cue
    end, in seconds -- max, not last, so an unsorted segment list
    cannot under-report). Re-iterable ``segments`` required."""
    cues = list(_iter_cues(segments))
    if not cues:
        return {"cues": 0, "end": 0.0}
    return {"cues": len(cues), "end": max(c[2] for c in cues) / 1000.0}


def write_subtitle_files(
    segments: Iterable[object] | None,
    out_folder: object,
    file_stem: str,
    *,
    want_srt: bool = True,
    want_vtt: bool = True,
    wrap: bool = True,
) -> dict:
    """Write ``<stem>.srt`` / ``<stem>.vtt`` into ``out_folder``.

    Returns ``{"srt_path": str | None, "vtt_path": str | None,
    "cues": int, "error": str | None}`` -- no segments (or neither
    format wanted) -> no files and no directory created; an OSError
    (or a hostile stem/path argument) -> the ``error`` key (NEVER a
    raise: the transcription already succeeded; a bad output folder
    must not retro-fail the run). Existing files are replaced (an
    idempotent re-run over a reused output folder). Re-iterable
    ``segments`` required (a generator is consumed by the cue pass).
    """
    out: dict = {"srt_path": None, "vtt_path": None, "cues": 0, "error": None}
    if not (want_srt or want_vtt):
        return out
    # V0.6.62 review hardening: the stem is a PATH COMPONENT -- a
    # caller-supplied "../escape" must never write outside dest (the
    # V0.6.60 traversal-precedent class). Path().name strips any
    # directory part on every platform; an empty or all-dots result
    # ("", "..", "/", ".") is rejected honestly (a ".." stem would
    # otherwise land as a confusing "...srt" file inside dest).
    stem = Path(file_stem).name if file_stem else ""
    if not stem or set(stem) == {"."}:
        out["error"] = f"Invalid subtitle file name: {file_stem!r}"
        return out
    cues = list(_iter_cues(segments))
    out["cues"] = len(cues)
    if not cues:
        return out
    try:
        folder = Path(out_folder)  # type: ignore[arg-type]
        folder.mkdir(parents=True, exist_ok=True)
        if want_srt:
            srt_path = folder / f"{stem}.srt"
            srt_path.write_text(_srt_from_cues(cues, wrap=wrap), encoding="utf-8")
            out["srt_path"] = str(srt_path)
        if want_vtt:
            vtt_path = folder / f"{stem}.vtt"
            vtt_path.write_text(_vtt_from_cues(cues, wrap=wrap), encoding="utf-8")
            out["vtt_path"] = str(vtt_path)
    except (OSError, ValueError, TypeError) as exc:
        out["srt_path"] = None
        out["vtt_path"] = None
        out["error"] = f"Could not write the subtitle files: {exc}"
    return out
