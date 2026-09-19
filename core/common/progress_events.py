"""V18.20.4.12 (W-b15): structured progress line for the live quality dashboard.

The wizard's live quality dashboard (``ui_qt/views/wizard_view.py::_on_log``)
used to regex-parse the HUMAN log line the Summarizer emits per completed
chapter::

    "  📊 Progress: 3/12 done | 31 bullets | 1,204 chars exec summary"

That regex (``_PROGRESS_RE``) breaks silently whenever the log wording
changes — the exact bug class W-b15 targets. This module adds a STRUCTURED,
wording-independent source: the emitter prepends one compact JSON line
immediately before the human line, and the parser tries the JSON FIRST
(human-regex stays as the back-compat fallback for older logs).

Contract (strict + documented):

* ``PROGRESS_PREFIX = "ELIXIR_PROGRESS "`` — the line starts with the exact
  prefix after ``lstrip()``-ing leading whitespace. NO tolerance for emoji
  or other prefixes: a line either IS a structured progress line or it is
  passed through untouched.
* ``progress_json_line(...)`` — compact ``json.dumps`` (``separators=(",", ":")``)
  with keys ``done``/``total``/``bullets``/``exec_chars`` (ints) plus
  ``"chapter_done": true`` (the emitter fires per completed chapter, so the
  parser can drive the chapter-status label from the SAME line).
* ``parse_progress_line(msg)`` — the inverse: the dict when the line is a
  well-formed structured progress line, else ``None``. Malformed JSON after
  the prefix NEVER raises (returns ``None``); a dict with non-int values is
  returned as-is and left for the caller to validate (the wizard treats an
  unusable dict as no-match and falls back to the regex paths).

Pure module (stdlib ``json`` only) — importable from both the core
summarisation pipeline and the Qt UI layer without cycles.
"""

from __future__ import annotations

import json

# The exact prefix that marks a structured progress line. Kept module-level
# and public so emitter-side and parser-side can never drift apart.
PROGRESS_PREFIX = "ELIXIR_PROGRESS "


def progress_json_line(done: int, total: int, bullets: int, exec_chars: int) -> str:
    """Build the structured progress line (one per completed chapter).

    Args:
        done: chapters completed so far (1-based index of the chapter that
            just finished).
        total: total chapters in the run.
        bullets: cumulative Key-Takeaways bullet count so far.
        exec_chars: cumulative executive-summary character count so far.

    Returns:
        ``PROGRESS_PREFIX + compact-json`` — a single line with no newline;
        the caller logs it at whatever level the human line uses (DEBUG),
        so both lines reach the same log bridge.
    """
    return PROGRESS_PREFIX + json.dumps(
        {
            "done": int(done),
            "total": int(total),
            "bullets": int(bullets),
            "exec_chars": int(exec_chars),
            # The emitter fires per COMPLETED chapter — the parser drives
            # the chapter-status label from this same line.
            "chapter_done": True,
        },
        separators=(",", ":"),
    )


def parse_progress_line(msg: str) -> dict | None:
    """Parse a structured progress line; ``None`` for anything else.

    Strict exact-prefix match on the ``lstrip()``'d line (documented
    contract — no emoji-prefix tolerance). Malformed JSON after the prefix
    returns ``None`` (never raises). A parsed-but-unusable payload (e.g.
    a hand-crafted line with missing keys) is returned as-is; the caller
    validates and falls back.
    """
    if not isinstance(msg, str):
        return None
    stripped = msg.lstrip()
    if not stripped.startswith(PROGRESS_PREFIX):
        return None
    payload = stripped[len(PROGRESS_PREFIX) :]
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


__all__ = ["PROGRESS_PREFIX", "progress_json_line", "parse_progress_line"]
