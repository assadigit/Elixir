"""V18.20.3.7 (audit v182036, Part 5 item 7 / Part 6): output provenance.

Two audit sessions (V18.20.3.5 and V18.20.3.6) were spent establishing WHICH
run produced an uploaded summary file: the user keeps one output folder per
app version on the Desktop, each containing identically-named per-chapter
summary files for the same book, and a stale older-version file was
uploaded twice as "the newest version's output". The files carried NO
self-identification, so provenance could only be established by
cross-referencing log internals (bullet counts, exec word counts, veto
lines).

This module makes every generated output file self-identifying:

1. **Provenance comment** — in every chapter-summary markdown (line 3:
   title, blank, stamp) and every book-level summary (line 1)::

       <!-- generated-by: MarkItDown Pro v18.20.3.7 | run_id=20260831-021017-ab12cd34
            | started=2026-08-31T02:10:17 | bullets=41 -->

   V18.20.3.10 correction: the stamp position differs by file class, so
   consumers must locate it with ``parse_provenance`` (whole-text regex),
   never by peeking a fixed line — the .3.9 diagnostic's line-2 peek
   false-flagged every fresh file (rig audit F6).

2. **Stamped COMPLETE sentinel** — the write-once/resume marker gains the
   run id::

       <!-- COMPLETE run_id=20260831-021017-ab12cd34 -->

   Legacy bare sentinels (``<!-- COMPLETE -->``) remain valid everywhere
   (resume must adopt files written by older versions — the documented
   chapter-resume feature is INTENTIONALLY cross-run: "I processed
   chapters 1-3 yesterday; today I want chapters 4-10"). The run id in the
   sentinel is AUDIT INFORMATION — which run wrote this file — NOT a
   write-once discriminator: resume semantics are unchanged by design.

3. **Adoption visibility** — when write-once/resume reuses a file stamped
   with a DIFFERENT run id, the caller logs it ("adopting existing file
   from run X, app vY"). Had this existed in the V18.20.3.6 run, the log
   would have shown the .3.6 folder adopting a .3.4 file, and the
   provenance confusion would have been impossible.

Stdlib-only (AST-verified policy for core/system modules).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

# Cached app version (read once per process — the VERSION file does not
# change mid-run).
_version_cache: str | None = None

# Provenance comment: generated-by line embedded in output markdown.
_PROVENANCE_RE = re.compile(
    r"<!--\s*generated-by:\s*MarkItDown Pro\s*v(?P<version>[^|>]+?)\s*"
    r"\|\s*run_id=(?P<run_id>[A-Za-z0-9_-]+)\s*"
    r"\|\s*started=(?P<started>[^|>]+?)\s*"
    r"\|\s*bullets=(?P<bullets>\d+)\s*-->"
)

# Stamped sentinel: <!-- COMPLETE run_id=... --> (legacy bare form accepted
# by has_complete_sentinel below).
_SENTINEL_RUN_ID_RE = re.compile(
    r"<!--\s*COMPLETE\s+run_id=([A-Za-z0-9_-]+)\s*-->"
)

_LEGACY_SENTINEL = "<!-- COMPLETE -->"


def get_app_version() -> str:
    """Read the app version from the VERSION file (single source of truth).

    Same lookup as ``Converter._get_app_version`` (project root relative to
    this file: core/system/provenance.py → root), extracted here so the
    summarisation layer can stamp it without importing the converter.
    Falls back to ``"unknown"`` — a stamp must never crash a conversion.
    """
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        vpath = Path(__file__).resolve().parent.parent.parent / "VERSION"
        if vpath.exists():
            _version_cache = vpath.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    if not _version_cache:
        _version_cache = "unknown"
    return _version_cache


def make_run_id() -> str:
    """One-per-conversion identifier: ``YYYYMMDD-HHMMSS-<8 hex>``.

    Generated once per Summarizer instance (= per conversion) so every
    chapter file, checkpoint copy and sentinel in that run shares it.
    """
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def run_started_iso() -> str:
    """Conversion start timestamp (ISO, seconds precision)."""
    return datetime.now().isoformat(timespec="seconds")


def provenance_comment(
    app_version: str,
    run_id: str,
    run_started: str,
    bullets: int,
) -> str:
    """The self-identification comment embedded in output markdown."""
    return (
        f"<!-- generated-by: MarkItDown Pro v{app_version}"
        f" | run_id={run_id}"
        f" | started={run_started}"
        f" | bullets={bullets} -->"
    )


def complete_sentinel(run_id: str | None) -> str:
    """The write-once/resume sentinel, stamped with the run id.

    Empty/None run_id → legacy bare sentinel (backward-compatible: files
    from SummaryResults built without provenance, e.g. legacy tests).
    """
    if run_id:
        return f"<!-- COMPLETE run_id={run_id} -->"
    return _LEGACY_SENTINEL


def has_complete_sentinel(text: str) -> bool:
    """True if the text carries ANY valid COMPLETE sentinel.

    Accepts both the legacy bare form and the run-id-stamped form — resume
    must adopt files written by older app versions (the documented
    cross-run chapter-resume feature).
    """
    return bool(text) and "<!-- COMPLETE" in text


def parse_provenance(text: str) -> dict[str, str]:
    """Extract provenance fields from a summary file's text.

    Returns ``{run_id, app_version, started, bullets}`` — each empty string
    when absent (legacy files have no provenance comment / bare sentinel).
    Never raises.
    """
    out: dict[str, str] = {
        "run_id": "", "app_version": "", "started": "", "bullets": "",
    }
    if not text:
        return out
    m = _PROVENANCE_RE.search(text)
    if m:
        out["app_version"] = m.group("version").strip()
        out["run_id"] = m.group("run_id").strip()
        out["started"] = m.group("started").strip()
        out["bullets"] = m.group("bullets").strip()
    if not out["run_id"]:
        s = _SENTINEL_RUN_ID_RE.search(text)
        if s:
            out["run_id"] = s.group(1).strip()
    return out


def stamp_diagnostic(
    file_name: str,
    text: str,
    current_version: str | None = None,
) -> tuple[str, str]:
    """(level, message) describing one summary file's provenance stamp.

    V18.20.3.10 (rig audit F6): the stamp is located by parsing the WHOLE
    file with ``parse_provenance`` — chapter files stamp line 3 (title /
    blank / stamp) and book files stamp line 1, so the .3.9 diagnostic's
    line-2 peek false-flagged every fresh file as "unstamped". Warn only
    when the parser finds no run id anywhere (a true pre-V18.20.3.7
    artifact); a stamped COMPLETE sentinel alone also counts as
    self-identified (run id present, version unknown). Never raises.

    V18.20.4.3 (P2 / G-1, the F8 follow-up): when ``current_version`` is
    supplied and the file's stamp names a DIFFERENT app version, the
    diagnostic escalates to WARNING — a stale artifact from an older
    (or newer) app sitting in this run's summaries folder. That is the
    exact confusion class that burned three consecutive rig-audit
    uploads (identical filenames across per-version output folders):
    the file is NOT this run's output regardless of which folder it
    landed in, and the log now says so in plain words. Version
    "unknown"/missing never escalates (legacy sentinel-only files stay
    INFO); run-id equality is irrelevant here (cross-run ADOPTION is
    legal, intentional resume behavior).
    """
    try:
        prov = parse_provenance(text or "")
    except Exception:
        prov = {}
    if prov.get("run_id"):
        _stamp_ver = (prov.get("app_version") or "").strip()
        _cur = (current_version or "").strip()
        if _stamp_ver and _cur and _stamp_ver != _cur:
            return (
                "WARNING",
                f"⚠️ {file_name} — STALE ARTIFACT: generated-by v{_stamp_ver}"
                f" (this app is v{_cur}) | run_id={prov['run_id']}"
                f" | started={prov.get('started') or '?'}"
                f" | bullets={prov.get('bullets') or '?'} —"
                " a file left by ANOTHER app version; do NOT upload or"
                " audit it as this run's output",
            )
        return (
            "INFO",
            f"✓ {file_name} — generated-by "
            f"v{prov.get('app_version') or 'unknown'}"
            f" | run_id={prov['run_id']}"
            f" | started={prov.get('started') or '?'}"
            f" | bullets={prov.get('bullets') or '?'}",
        )
    return (
        "WARNING",
        f"⚠️ {file_name} — NO generated-by stamp (pre-V18.20.3.7 artifact "
        "— verify before trusting or uploading it)",
    )


def visible_footer(
    app_version: str,
    run_id: str,
    run_started: str,
    bullets: int,
) -> str:
    """V18.20.4.3 (P2 / G-3, the F8 follow-up): human-VISIBLE provenance
    footer rendered at the end of every stamped summary file.

    The ``<!-- generated-by -->`` comment is invisible in every markdown
    renderer/preview — a user opening two identically-named files from
    two app-version folders could not tell the fresh one from the stale
    one without reading raw source. This plain-text line (it renders as
    an italic caption under a rule) makes the version + run + timestamp
    visible wherever the file is opened, in preview or raw form:

        ---
        *Generated by MarkItDown Pro v18.20.4.3 · run 20260901-154401-fe4399da · 2026-09-01T15:44:01 · 46 bullets*

    Only ever appended for STAMPED summaries (same gate as the comment);
    legacy unstamped output renders byte-identically to before.
    ``parse_provenance`` is unaffected (it regex-matches the HTML
    comment, which stays authoritative).
    """
    return (
        "\n---\n\n"
        f"*Generated by MarkItDown Pro v{app_version}"
        f" · run {run_id}"
        f" · {run_started}"
        f" · {bullets} bullets*\n\n"
    )


def adoption_note(existing_text: str, incoming_text: str) -> str | None:
    """Compare provenance of an existing COMPLETE file vs the content the
    current run is about to (not) write.

    Returns a log line when the existing file belongs to a DIFFERENT run
    (the write-once "adoption" case), else None. This is the visibility
    fix for the V18.20.3.6 confusion: the log now says, in plain words,
    that a previous run's output is being reused.
    """
    try:
        existing = parse_provenance(existing_text)
        incoming = parse_provenance(incoming_text)
    except Exception:
        return None
    e_rid, i_rid = existing.get("run_id", ""), incoming.get("run_id", "")
    if e_rid and i_rid and e_rid != i_rid:
        e_ver = existing.get("app_version") or "unknown version"
        return (
            f"existing file is from run {e_rid} (app v{e_ver}, "
            f"{existing.get('started') or 'unknown start'}, "
            f"{existing.get('bullets') or '?'} bullets); current run is "
            f"{i_rid} — reusing it (resume/write-once semantics)"
        )
    return None


__all__ = [
    "get_app_version",
    "make_run_id",
    "run_started_iso",
    "provenance_comment",
    "visible_footer",
    "complete_sentinel",
    "has_complete_sentinel",
    "parse_provenance",
    "stamp_diagnostic",
    "adoption_note",
]
