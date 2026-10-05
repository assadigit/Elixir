"""V0.6.21 (W-g1): a pure-Python diff utility for podcast scripts.

Why this exists
---------------
The wizard's flow is: generate a script → the operator edits it in
the Script view (the QPlainTextEdit) → click "Generate Podcast".
Before V0.6.21, once the operator edited the script, the original
generated version was GONE — there was no way to see what they
changed, no way to undo a specific edit, no way to compare the
edits against the anti-hallucination contract (did the operator
delete a bullet's coverage line? did they change a host assignment
that breaks the voice mapping?).

The wizard has "Export Script" + "Import Script" buttons so the
operator can save/load the edited version, but no DIFF. This module
fills that gap. The operator can:

  1. Generate a script (the "before" state).
  2. Edit it (the "after" state).
  3. Call ``diff_scripts(before, after)`` to see exactly what changed:
     - Which lines were ADDED (new lines the operator wrote).
     - Which lines were DELETED (lines the operator removed).
     - Which lines were MODIFIED (text changed, host changed, or
       segment_type changed — each field reported separately).
     - The line-level + word-level diff (so a 1-word tweak in a
       50-word line shows just that 1 word, not the whole line as
       a delete+add pair).

The diff uses Python's stdlib ``difflib.SequenceMatcher`` — no
external dependency. The algorithm is the same one ``git diff`` uses
(Ratcliff-Obershel), which is good enough for script-sized inputs
(hundreds of lines, thousands of words).

Public API:
  - ``DiffOp`` — enum-like constants for the diff operation types.
  - ``LineDiff`` — dataclass for one line's diff result.
  - ``ScriptDiff`` — dataclass for the full diff (list of LineDiff).
  - ``diff_scripts(before, after)`` — compute the diff.
  - ``format_diff_for_display(diff, log)`` — multi-line formatter
    (the same style as ``git diff``: green +, red -, for context).
  - ``summarize_diff(diff)`` — one-line summary (e.g., "3 added,
    1 deleted, 2 modified").

The diff is deliberately line-based (not character-based) because
the script's unit of work is the line — each line is a host's turn
in the dialogue. Within a modified line, the WORD-level diff is
shown so the operator sees exactly which words changed.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass, field

from core.podcast.script_generator import ScriptLine, ScriptResult

# ── Diff operation types ────────────────────────────────────────────────────

# String constants (not an enum — keeps the module stdlib-only and
# makes the JSON serialization in the CLI's --json flag trivial).
OP_EQUAL = "equal"  # line unchanged
OP_REPLACE = "replace"  # line text/host/segment changed
OP_DELETE = "delete"  # line removed from `after`
OP_INSERT = "insert"  # line added to `after`


@dataclass
class WordDiff:
    """A word-level change within a MODIFIED line.

    ``op`` is one of ``OP_EQUAL`` / ``OP_REPLACE`` / ``OP_DELETE`` /
    ``OP_INSERT`` (same constants as the line-level diff). ``before``
    is the word(s) in the before-line (empty for OP_INSERT).
    ``after`` is the word(s) in the after-line (empty for OP_DELETE).
    """

    op: str
    before: str
    after: str


@dataclass
class LineDiff:
    """One line's diff result.

    ``op`` is one of OP_EQUAL / OP_REPLACE / OP_DELETE / OP_INSERT.
    ``before_index`` / ``after_index`` are 1-based line indices (0
    if the line doesn't exist on that side). ``before`` / ``after``
    are the ScriptLine objects (None if the line doesn't exist on
    that side). ``word_diffs`` is populated only for OP_REPLACE —
    the word-level diff within the modified line.
    """

    op: str
    before_index: int = 0
    after_index: int = 0
    before: ScriptLine | None = None
    after: ScriptLine | None = None
    word_diffs: list[WordDiff] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """A one-line summary of this line's diff (for the formatter)."""
        if self.op == OP_EQUAL:
            return f"  {self.after_index:3d}  {self.after.host}: {self.after.text[:60]}"
        if self.op == OP_INSERT:
            return f"+ {self.after_index:3d}  {self.after.host}: {self.after.text[:60]}"
        if self.op == OP_DELETE:
            return f"- {self.before_index:3d}  {self.before.host}: {self.before.text[:60]}"
        # OP_REPLACE
        return (
            f"~ {self.before_index:3d}->{self.after_index:3d}  "
            f"{self.before.host}->{self.after.host}: "
            f"{self.before.text[:30]}... -> {self.after.text[:30]}..."
        )


@dataclass
class ScriptDiff:
    """The full diff between two ScriptResult objects.

    ``lines`` is a list of LineDiff in line order (interleaved
    equal/insert/delete/replace). ``added_count`` / ``deleted_count`` /
    ``modified_count`` are the totals. ``equal_count`` is the unchanged
    line count (for the summary).
    """

    lines: list[LineDiff] = field(default_factory=list)
    added_count: int = 0
    deleted_count: int = 0
    modified_count: int = 0
    equal_count: int = 0

    # Metadata echoed from the scripts (for the formatter's header).
    before_title: str = ""
    after_title: str = ""

    @property
    def total_changes(self) -> int:
        """Total non-equal lines (added + deleted + modified)."""
        return self.added_count + self.deleted_count + self.modified_count

    @property
    def is_clean(self) -> bool:
        """True iff the two scripts are identical (zero changes)."""
        return self.total_changes == 0


# ── The word-level diff helper ───────────────────────────────────────────────


def _diff_words(before_text: str, after_text: str) -> list[WordDiff]:
    """Compute a word-level diff between two text strings.

    Uses ``difflib.SequenceMatcher`` on the word lists. Returns a list
    of WordDiff objects — each is a run of equal/inserted/deleted/
    replaced words. Replaced runs are reported as a delete+insert pair
    (so the operator sees both the old and new words).
    """
    before_words = before_text.split()
    after_words = after_text.split()
    matcher = difflib.SequenceMatcher(a=before_words, b=after_words, autojunk=False)
    diffs: list[WordDiff] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        before_chunk = " ".join(before_words[i1:i2])
        after_chunk = " ".join(after_words[j1:j2])
        if op == "equal":
            diffs.append(WordDiff(op=OP_EQUAL, before=before_chunk, after=after_chunk))
        elif op == "replace":
            # Report as a delete + insert pair so both old and new are visible.
            if before_chunk:
                diffs.append(WordDiff(op=OP_DELETE, before=before_chunk, after=""))
            if after_chunk:
                diffs.append(WordDiff(op=OP_INSERT, before="", after=after_chunk))
        elif op == "delete":
            diffs.append(WordDiff(op=OP_DELETE, before=before_chunk, after=""))
        elif op == "insert":
            diffs.append(WordDiff(op=OP_INSERT, before="", after=after_chunk))
    return diffs


# ── The main diff function ──────────────────────────────────────────────────


def _lines_match(a: ScriptLine, b: ScriptLine) -> bool:
    """Two lines "match" for difflib's purposes if their host + text +
    segment_type are all equal. (source_ref is metadata, not content —
    a source_ref change alone is NOT a line modification.)"""
    return a.host == b.host and a.text == b.text and a.segment_type == b.segment_type


def _line_signature(line: ScriptLine) -> tuple:
    """A hashable signature for difflib's line matching. Using host+text+
    segment_type (NOT source_ref — a source_ref change alone is metadata,
    not a content change the operator needs to see in the diff)."""
    return (line.host, line.text, line.segment_type)


def diff_scripts(before: ScriptResult, after: ScriptResult) -> ScriptDiff:
    """Compute the diff between two ScriptResult objects.

    Args:
        before: the original script (e.g., the generated version).
        after: the edited script (e.g., the operator's hand-edits).

    Returns:
        A ScriptDiff with .lines (list of LineDiff in line order),
        .added_count / .deleted_count / .modified_count / .equal_count,
        and .before_title / .after_title (echoed from the scripts).
    """
    result = ScriptDiff(
        before_title=before.title,
        after_title=after.title,
    )
    before_lines = before.lines
    after_lines = after.lines

    # Use difflib to find the longest matching blocks between the two
    # line sequences. The signature excludes source_ref (metadata).
    matcher = difflib.SequenceMatcher(
        a=[_line_signature(ln) for ln in before_lines],
        b=[_line_signature(ln) for ln in after_lines],
        autojunk=False,
    )

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            # Both ranges are identical — emit one LineDiff per line.
            for k in range(i2 - i1):
                bi = i1 + k
                ai = j1 + k
                result.lines.append(
                    LineDiff(
                        op=OP_EQUAL,
                        before_index=bi + 1,
                        after_index=ai + 1,
                        before=before_lines[bi],
                        after=after_lines[ai],
                    )
                )
                result.equal_count += 1
        elif op == "replace":
            # Lines on both sides but they differ. Pair them up 1:1 and
            # emit a OP_REPLACE with word-level diffs. If the counts
            # differ, the extras become pure inserts/deletes after the
            # paired replaces.
            n_before = i2 - i1
            n_after = j2 - j1
            n_paired = min(n_before, n_after)
            for k in range(n_paired):
                bi = i1 + k
                ai = j1 + k
                before_ln = before_lines[bi]
                after_ln = after_lines[ai]
                # The signatures differ (otherwise they'd be in the
                # "equal" block). Compute word-level diffs for the text.
                word_diffs = _diff_words(before_ln.text, after_ln.text)
                result.lines.append(
                    LineDiff(
                        op=OP_REPLACE,
                        before_index=bi + 1,
                        after_index=ai + 1,
                        before=before_ln,
                        after=after_ln,
                        word_diffs=word_diffs,
                    )
                )
                result.modified_count += 1
            # Handle the unpaired extras.
            for k in range(n_paired, n_before):
                bi = i1 + k
                result.lines.append(
                    LineDiff(
                        op=OP_DELETE,
                        before_index=bi + 1,
                        before=before_lines[bi],
                    )
                )
                result.deleted_count += 1
            for k in range(n_paired, n_after):
                ai = j1 + k
                result.lines.append(
                    LineDiff(
                        op=OP_INSERT,
                        after_index=ai + 1,
                        after=after_lines[ai],
                    )
                )
                result.added_count += 1
        elif op == "delete":
            # Lines only in `before` — removed.
            for k in range(i1, i2):
                result.lines.append(
                    LineDiff(
                        op=OP_DELETE,
                        before_index=k + 1,
                        before=before_lines[k],
                    )
                )
                result.deleted_count += 1
        elif op == "insert":
            # Lines only in `after` — added.
            for k in range(j1, j2):
                result.lines.append(
                    LineDiff(
                        op=OP_INSERT,
                        after_index=k + 1,
                        after=after_lines[k],
                    )
                )
                result.added_count += 1

    return result


# ── The formatters ───────────────────────────────────────────────────────────


def summarize_diff(diff: ScriptDiff) -> str:
    """A one-line summary of the diff.

    Examples:
      - "✅ No changes — the scripts are identical."
      - "3 added, 1 deleted, 2 modified (6 total changes)."
    """
    if diff.is_clean:
        return "✅ No changes — the scripts are identical."
    parts: list[str] = []
    if diff.added_count:
        parts.append(f"{diff.added_count} added")
    if diff.deleted_count:
        parts.append(f"{diff.deleted_count} deleted")
    if diff.modified_count:
        parts.append(f"{diff.modified_count} modified")
    summary = ", ".join(parts) + f" ({diff.total_changes} total changes)."
    return summary


def format_diff_for_display(
    diff: ScriptDiff,
    log: Callable[[str, str], None] | None = None,
    context: int = 2,
) -> str:
    """Format a ScriptDiff as a multi-line string (the same style as
    ``git diff``: green +, red -, ~ for modified, space for context).

    Args:
        diff: the ScriptDiff to format.
        log: optional callback(message, level) — each output line is
            echoed (the wizard can use this to write the diff to its
            live log).
        context: number of unchanged lines to show around each change
            (0 = no context, just the changes; default 2 = git's
            default). Set to a large number to show the whole diff.

    Returns:
        A multi-line string. If the diff is clean, returns the
        summarize_diff() one-liner.
    """
    if diff.is_clean:
        msg = summarize_diff(diff)
        if log:
            log(msg, "INFO")
        return msg

    parts: list[str] = []
    parts.append("📝 Script Diff")
    parts.append("═" * 60)
    parts.append(f"Before: {diff.before_title or '(untitled)'}")
    parts.append(f"After:  {diff.after_title or '(untitled)'}")
    parts.append(f"Summary: {summarize_diff(diff)}")
    parts.append("─" * 60)

    # If context is 0, just emit the changed lines.
    if context == 0:
        for line_diff in diff.lines:
            if line_diff.op == OP_EQUAL:
                continue
            line = _format_line_diff(line_diff)
            parts.append(line)
            if log:
                level = "INFO" if line_diff.op == OP_EQUAL else "WARNING"
                log(line, level)
        return "\n".join(parts)

    # Otherwise, emit changed lines + `context` unchanged lines around
    # each change (git diff style). Walk the lines, mark which indices
    # are "near a change", and emit only those.
    n = len(diff.lines)
    emit_flags = [False] * n
    for i, ld in enumerate(diff.lines):
        if ld.op != OP_EQUAL:
            # Emit this line + `context` lines on each side.
            for k in range(max(0, i - context), min(n, i + context + 1)):
                emit_flags[k] = True

    # Walk + emit, with a "..." separator when skipping a run of
    # unchanged lines.
    skipping = False
    for i, ld in enumerate(diff.lines):
        if emit_flags[i]:
            line = _format_line_diff(ld)
            parts.append(line)
            if log:
                level = "INFO" if ld.op == OP_EQUAL else "WARNING"
                log(line, level)
            skipping = False
        else:
            if not skipping:
                parts.append("  ...")
                skipping = True

    return "\n".join(parts)


def _format_line_diff(ld: LineDiff) -> str:
    """Format one LineDiff as a single line (the git-diff style)."""
    if ld.op == OP_EQUAL:
        return f"  {ld.after_index:3d}  [{ld.after.host}] {ld.after.text[:70]}"
    if ld.op == OP_INSERT:
        return f"+ {ld.after_index:3d}  [{ld.after.host}] {ld.after.text[:70]}"
    if ld.op == OP_DELETE:
        return f"- {ld.before_index:3d}  [{ld.before.host}] {ld.before.text[:70]}"
    # OP_REPLACE — show the before and after, plus word-level diffs if
    # the text changed (the common case). If only the host or segment
    # changed (text identical), show that explicitly.
    if ld.before.text == ld.after.text and ld.before.host != ld.after.host:
        return (
            f"~ {ld.before_index:3d}->{ld.after_index:3d}  "
            f"[{ld.before.host}->{ld.after.host}] {ld.before.text[:60]}"
        )
    if ld.before.text == ld.after.text and ld.before.segment_type != ld.after.segment_type:
        return (
            f"~ {ld.before_index:3d}->{ld.after_index:3d}  "
            f"[{ld.after.host}] {ld.before.text[:50]} "
            f"({ld.before.segment_type}->{ld.after.segment_type})"
        )
    # Text changed — show word-level diff inline.
    word_parts: list[str] = []
    for wd in ld.word_diffs:
        if wd.op == OP_EQUAL:
            word_parts.append(wd.before)
        elif wd.op == OP_DELETE:
            word_parts.append(f"[-{wd.before}-]")
        elif wd.op == OP_INSERT:
            word_parts.append(f"[+{wd.after}+]")
    word_summary = " ".join(word_parts)
    if len(word_summary) > 80:
        word_summary = word_summary[:77] + "..."
    host_str = (
        f"[{ld.before.host}->{ld.after.host}] "
        if ld.before.host != ld.after.host
        else f"[{ld.after.host}] "
    )
    return f"~ {ld.before_index:3d}->{ld.after_index:3d}  {host_str}{word_summary}"
