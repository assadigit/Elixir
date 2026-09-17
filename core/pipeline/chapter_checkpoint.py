"""V18.20.3.0: Incremental per-chapter checkpoint saving (crash-safe).

User requirement (verbatim): "Currently it user add a full book for
summarization, the app refuses to give outputs until the all books is
finished, but this method is not very efficient or reliable. we need to
plan a saving mechanism into app, for example after every chapter, save
the docx and outputs of that chapter (create a new folder as well), so if
by any means, like electricity problems/ sudden shutdowns etc, app got
stopped/cancelled, we have a backup and save until that point of
application. For example book is 10 chapter, 9 chapter is done, the app
crashes at the 10th chapter, we must have 9 chapters ready and untouched
by this crash, because they're already done and saved."

The gap this closes
-------------------
Before V18.20.3.0 the pipeline held ALL chapter summaries in memory and
only wrote them to disk AFTER the last chapter finished (the
"Incremental saving" loop in ``conversion/summarization.py`` — which was
atomic per file but ran once, post-loop). The full-book DOCX was built
even later (converter Step 10). A power cut / crash / user-cancel at
chapter 10 of 11 therefore lost chapters 1-10: nothing was on disk for
the chapter-resume system (V7.7.0) to find, and no DOCX existed at all.

What happens now
----------------
The moment each chapter's summary is produced,
:class:`ChapterCheckpointSaver` (wired as the ``chapter_done_callback`` of
``Summarizer.summarize_chapters``) writes — ATOMICALLY and WRITE-ONCE
(never rewrites a completed chapter):

    {output_dir}/
    ├── summaries/{NNN}_{heading}_summary.md      ← canonical summary file
    │                                                 (``<!-- COMPLETE -->``
    │                                                 marker → the V7.7.0
    │                                                 chapter-resume system
    │                                                 picks it up on re-run)
    └── checkpoints/
        ├── chapter_manifest.json                  ← crash-recovery state
        │                                             (chapters done, paths,
        │                                             timestamps, bullet counts)
        └── chapters/
            └── {NNN}_{heading}/
                ├── {NNN}_{heading}_summary.md     ← self-contained copy
                └── {NNN}_{heading}_summary.docx   ← per-chapter DOCX report

On restart after a crash, ``detect_processed_chapters()`` (V7.7.0) finds
the surviving summary files and the LLM processes ONLY the missing
chapters; whole-book outputs are then rebuilt from the merged set. The
user also has every completed chapter's DOCX available immediately —
readable mid-run, not just after the whole book finishes.

Design rules
------------
- **Best-effort, never fatal**: every write is wrapped; a checkpoint
  failure logs a WARNING and the conversion continues (checkpointing must
  never crash the pipeline).
- **Atomic**: ``utils.atomic_io.atomic_write_text`` / ``atomic_write_json``
  for .md/.json; DOCX is saved to a ``.tmp`` sibling then ``os.replace``d
  (python-docx's ``save()`` is not atomic by itself).
- **Write-once**: if the target summary file already exists WITH the
  COMPLETE marker it is never rewritten — completed chapters stay
  byte-identical across re-runs ("ready and untouched").
- **Positioning**: files are numbered by the chapter's FINAL position in
  the merged (loaded + new) summary list, computed upfront from the
  segment order — so checkpoint files match the end-of-run numbering and
  resume numbering stays stable. Fallback: the callback's 1-based index.
- **Failed chapters are not saved** (mirrors the end-of-loop rule: failed
  summaries never produce COMPLETE files, so they are reprocessed on
  resume).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import SummaryResult

logger = logging.getLogger(__name__)

# V18.2.7/V18.2.8 (shared with conversion/summarization.py): academic years
# in parentheses render italic + smaller in the summary markdown.
# V18.20.3.2 (audit N8 / P2-b): the old pattern `\((\d{4})\)` only matched
# parentheticals containing EXACTLY one bare year — "(1956)" was styled but
# "(1961, 1963)" and "(1950a, 1956, 1958, 1959)" were not, so the shipped
# markdown mixed styled and plain years inside the SAME bullet list. The new
# pattern styles EVERY 4-digit year inside ANY parenthetical group (single,
# multi-year, and year+letter citations), making the rendering consistent.
_YEAR_IN_PARENS_RE = re.compile(r"\(([^()]*)\)")
# V18.20.3.2: (?<!\d)/(?!\d) instead of \b — "1950a" has no word boundary
# between "0" and "a" (both word chars), so \b\d{4}\b MISSED year+letter
# citations while styling their bare-year siblings ("(1950a, 1956)" styled
# only 1956). The digit-lookarounds allow letter suffixes but reject longer
# digit runs.
_BARE_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")

_MANIFEST_VERSION = "18.20.3.0"


def _style_years_in_parens(match: re.Match) -> str:
    """Style every 4-digit year inside one parenthetical group."""
    inner = match.group(1)
    if not _BARE_YEAR_RE.search(inner):
        return match.group(0)  # no years — leave untouched
    return "(" + _BARE_YEAR_RE.sub(
        r'<em style="font-size:0.9em">\1</em>', inner
    ) + ")"


def format_years(text: str) -> str:
    """Wrap 4-digit years in parentheses with italic+smaller styling.

    Extracted verbatim from the (formerly inline) end-of-loop writer in
    ``conversion/summarization.py`` so the incremental checkpoint writer
    and the final writer produce byte-identical files.

    V18.20.3.2 (P2-b): every parenthesized year is styled — single years
    ("(1956)"), multi-year citations ("(1961, 1963)"), and year+letter
    citations ("(1950a, 1956)") — closing the styled/plain inconsistency
    the V18.20.3.1 audit flagged in the shipped Key Takeaways.
    """
    if not text:
        return text
    return _YEAR_IN_PARENS_RE.sub(_style_years_in_parens, text)


def render_summary_markdown(summ: SummaryResult) -> str:
    """Render a SummaryResult to the canonical chapter-summary markdown.

    Byte-identical to the end-of-loop writer in
    ``conversion/summarization.py`` (heading, Executive Summary, Key
    Takeaways with year-formatted bullets, Thorough Summary, optional
    additive sections, ``<!-- COMPLETE -->`` sentinel) — so a file written
    mid-run by the checkpoint saver is indistinguishable from one written
    at the end, and the V7.7.0 chapter-resume parser accepts both.

    V18.20.3.7: when the SummaryResult carries provenance
    (``run_id``/``app_version``/``run_started`` — set by the Summarizer,
    one id per conversion), the file becomes SELF-IDENTIFYING: a
    ``<!-- generated-by: ... -->`` comment sits under the title and the
    COMPLETE sentinel is stamped with the run id. Unstamped (legacy)
    summaries render exactly as before — byte-for-byte.
    """
    formatted_bullets = [format_years(str(bp)) for bp in summ.bullet_points]
    bullets_md = "\n".join(f"- {_fbp}" for _fbp in formatted_bullets)

    exec_formatted = format_years(summ.executive_summary or "")
    thorough_formatted = format_years(summ.thorough_summary or "")

    kd_md = ""
    if getattr(summ, "key_distinctions", None) and str(summ.key_distinctions).strip():
        kd_md = f"\n## Key Distinctions\n\n{summ.key_distinctions}\n\n"
    tt_md = ""
    if getattr(summ, "theoretical_tensions", None) and str(summ.theoretical_tensions).strip():
        tt_md = f"\n## Theoretical Tensions\n\n{summ.theoretical_tensions}\n\n"
    sr_md = ""
    if getattr(summ, "scholar_reflections", None) and str(summ.scholar_reflections).strip():
        sr_md = f"\n## Scholar's Reflections\n\n{summ.scholar_reflections}\n\n"

    # V18.20.3.7: provenance comment (self-identification) — only when the
    # summary is stamped with a real run-id STRING; legacy/unstamped output
    # (and duck-typed mocks without string fields) renders unchanged.
    prov_md = ""
    footer_md = ""
    _rid_raw = getattr(summ, "run_id", "")
    _run_id = _rid_raw if isinstance(_rid_raw, str) and _rid_raw else ""
    if _run_id:
        from core.system.provenance import provenance_comment, visible_footer
        _app_ver = getattr(summ, "app_version", "") or "unknown"
        _started = getattr(summ, "run_started", "") or "unknown"
        prov_md = (
            provenance_comment(
                _app_ver,
                _run_id,
                _started,
                len(formatted_bullets),
            )
            + "\n\n"
        )
        # V18.20.4.3 (P2 / G-3, the F8 follow-up): human-VISIBLE footer —
        # the HTML comment above is invisible in rendered markdown, which
        # is exactly how a stale artifact from an old app-version folder
        # got mistaken for fresh output. Rendered only for stamped
        # summaries; legacy output stays byte-identical.
        footer_md = visible_footer(
            _app_ver, _run_id, _started, len(formatted_bullets),
        )

    from core.system.provenance import complete_sentinel
    # (Type guard rationale above — a MagicMock run_id must render as a
    # legacy bare sentinel, never as garbage text.)
    return (
        f"# Summary: {summ.chapter_heading}\n\n"
        f"{prov_md}"
        f"## Executive Summary\n\n{exec_formatted}\n\n"
        f"## Key Takeaways\n\n{bullets_md}\n\n"
        f"## Thorough Summary\n\n{thorough_formatted}\n"
        f"{kd_md}{tt_md}{sr_md}"
        f"{footer_md}"
        f"{complete_sentinel(_run_id)}\n"
    )


class ChapterCheckpointSaver:
    """Incremental per-chapter checkpoint writer (V18.20.3.0).

    Constructed once per conversion (in ``conversion/summarization.py``)
    and invoked as the ``chapter_done_callback`` of
    ``Summarizer.summarize_chapters`` immediately after EACH chapter's
    summary is produced — sequentially or in parallel.
    """

    def __init__(
        self,
        converter: Any,
        heading_positions: dict[str, int] | None = None,
        chapters_total: int = 0,
        build_docx: bool = True,
        book_title: str = "",
    ) -> None:
        self._converter = converter
        self._log = getattr(converter, "_log", None) or (lambda msg, level="INFO": None)
        self._positions: dict[str, int] = heading_positions or {}
        self._chapters_total = chapters_total
        self._book_title = book_title
        self._request = getattr(converter, "request", None)
        self._output_dir: Path = Path(converter.output_dir)
        self._summaries_dir: Path = Path(converter.paths.summaries_dir)
        self._chapters_root: Path = self._output_dir / "checkpoints" / "chapters"
        self._manifest_path: Path = self._output_dir / "checkpoints" / "chapter_manifest.json"
        self._sanitize = getattr(converter, "_sanitize_filename", None) or (lambda h: re.sub(r"[^\w\s\-]", "", re.sub(r"\s+", "_", (h or "").strip()))[:80])
        self._build_docx = build_docx
        # Counters (for logging + tests)
        self.saved_count = 0
        self.skipped_existing = 0
        self.docx_count = 0
        self._logged_intro = False

    # ── public API (the callback) ────────────────────────────────────────

    def on_chapter_done(
        self,
        idx: int,
        summary: SummaryResult,
        chapter: dict[str, Any] | None = None,
    ) -> None:
        """Checkpoint one completed chapter. NEVER raises.

        Args:
            idx: 1-based index of the chapter within the chapters being
                summarized this run (fallback when no heading map).
            summary: the chapter's SummaryResult.
            chapter: the chapter dict (``heading``/``content``) — used for
                the per-chapter DOCX's full-content section.
        """
        try:
            self._on_chapter_done_impl(idx, summary, chapter)
        except Exception as e:  # best-effort — never crash the pipeline
            try:
                self._log(
                    f"  ⚠️ V18.20.3.0 chapter checkpoint failed for chapter "
                    f"{idx}: {e!r} — conversion continues (chapter outputs "
                    f"will still be written at the end of the phase).",
                    "WARNING",
                )
            except Exception:
                pass

    # ── internals ─────────────────────────────────────────────────────────

    def _on_chapter_done_impl(
        self,
        idx: int,
        summary: SummaryResult,
        chapter: dict[str, Any] | None,
    ) -> None:
        if not self._logged_intro:
            self._logged_intro = True
            self._log(
                f"  🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — "
                f"each chapter is saved (md + docx) the moment it completes; "
                f"crash-safe via {self._output_dir / 'checkpoints'}",
                "INFO",
            )

        # Mirror the end-of-loop rule: never checkpoint FAILED/empty summaries
        # (they must not produce COMPLETE files, or resume would skip them).
        if not getattr(summary, "success", True) or (
            not summary.executive_summary
            and not summary.bullet_points
            and not summary.thorough_summary
        ):
            self._log(
                f"  ⏭️ Checkpoint skip: chapter {idx} "
                f"('{(summary.chapter_heading or '?')[:40]}') failed/empty — "
                f"it will be reprocessed on resume.",
                "DEBUG",
            )
            return

        heading = (chapter or {}).get("heading") or summary.chapter_heading or f"Chapter {idx}"
        pos = self._positions.get(heading, idx)
        safe = self._sanitize(summary.chapter_heading or heading) or "chapter"
        sf_name = f"{pos:03d}_{safe}_summary.md"

        # 1) canonical summary file (resume-compatible) — write-once
        sf = self._summaries_dir / sf_name
        wrote_canonical = self._atomic_write_once(sf, render_summary_markdown(summary))
        if not wrote_canonical:
            self.skipped_existing += 1

        # 2) dedicated checkpoint folder: md copy + per-chapter DOCX
        chapter_folder = self._chapters_root / f"{pos:03d}_{safe}"
        chapter_folder.mkdir(parents=True, exist_ok=True)
        cp_md = chapter_folder / sf_name
        self._atomic_write_once(cp_md, render_summary_markdown(summary), quiet=True)

        docx_path: Path | None = None
        if self._build_docx:
            docx_path = self._build_chapter_docx(
                summary, chapter or {"heading": heading, "content": ""},
                chapter_folder / f"{pos:03d}_{safe}_summary.docx",
            )
            if docx_path is not None:
                self.docx_count += 1

        # 3) manifest + checkpoint phase progress
        self.saved_count += 1
        self._update_manifest(pos, heading, sf, chapter_folder, docx_path, summary)
        self._mark_checkpoint_progress()

        _docx_note = " + DOCX" if docx_path is not None else ""
        self._log(
            f"  🛟 Checkpoint saved: chapter {pos}"
            f"{f'/{self._chapters_total}' if self._chapters_total else ''} "
            f"'{heading[:40]}' → summaries/{sf_name}{_docx_note}",
            "DEBUG",
        )

    def _atomic_write_once(self, path: Path, content: str, quiet: bool = False) -> bool:
        """Atomic write with write-once semantics.

        Returns True if this call wrote the file, False if a COMPLETE file
        already existed (untouched guarantee). A file that exists WITHOUT
        the marker is rewritten (belt-and-suspenders for pre-atomic-era
        partial writes).
        """
        from utils.atomic_io import atomic_write_text

        if path.exists():
            try:
                _existing = path.read_text(encoding="utf-8")
                # V18.20.3.7: accepts BOTH the legacy bare sentinel and the
                # run-id-stamped form; when the existing file was produced
                # by a DIFFERENT run, the skip is logged with both run ids
                # (the V18.20.3.6 audit spent two sessions proving which
                # run wrote a file — now the log says it outright). Resume
                # semantics UNCHANGED: cross-run adoption is the documented
                # chapter-resume feature, so the run id is audit info, not
                # a write-once discriminator.
                from core.system.provenance import (
                    adoption_note,
                    has_complete_sentinel,
                )
                if has_complete_sentinel(_existing):
                    if not quiet:
                        _note = adoption_note(_existing, content)
                        self._log(
                            f"  🛟 Checkpoint intact — not rewriting {path.name} "
                            f"(completed chapters are never touched)."
                            + (f" 🪪 {_note}." if _note else ""),
                            "DEBUG",
                        )
                    return False
            except OSError:
                pass  # unreadable → rewrite
        atomic_write_text(path, content)
        return True

    def _build_chapter_docx(self, summary: SummaryResult, chapter: dict[str, Any], out_path: Path) -> Path | None:
        """Build the per-chapter DOCX report atomically (tmp + os.replace).

        V18.20.3.1 (real-rig audit D4): the builder's own "✅ DOCX saved to …"
        log line reported the TEMP path (``…_summary.docx.tmp``) because it
        received ``tmp_path`` — the user-facing log then showed a file that
        doesn't exist after the rename. The log callback now rewrites the
        tmp path to the final path, so the log stays truthful.
        """
        try:
            from core.docx.builder import DocxBuilder

            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

            def _truthful_log(msg: str, level: str = "INFO") -> None:
                # Rewrite the tmp path → final path in builder log lines.
                try:
                    if str(tmp_path) in str(msg):
                        msg = str(msg).replace(str(tmp_path), str(out_path))
                except Exception:
                    pass
                self._log(msg, level)

            builder = DocxBuilder(self._request, log_callback=_truthful_log)
            ok = builder.build_report(
                [summary],
                [{"heading": chapter.get("heading", summary.chapter_heading),
                  "content": chapter.get("content", "")}],
                getattr(self._request, "input_path", self._output_dir),
                tmp_path,
            )
            if not ok:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None
            os.replace(tmp_path, out_path)
            return out_path
        except Exception as e:
            self._log(
                f"  ⚠️ Per-chapter DOCX checkpoint failed for "
                f"'{summary.chapter_heading[:40]}': {e!r} — md checkpoint "
                f"still saved.",
                "WARNING",
            )
            return None

    def _update_manifest(
        self,
        pos: int,
        heading: str,
        canonical_md: Path,
        chapter_folder: Path,
        docx_path: Path | None,
        summary: SummaryResult,
    ) -> None:
        """Merge this chapter's record into checkpoints/chapter_manifest.json."""
        from utils.atomic_io import atomic_write_json

        manifest = self._load_manifest()
        chapters: dict[str, Any] = manifest.setdefault("chapters", {})
        chapters[str(pos)] = {
            "heading": heading,
            "done_at": datetime.now().isoformat(timespec="seconds"),
            "summary_md": str(canonical_md),
            "chapter_folder": str(chapter_folder),
            "docx": str(docx_path) if docx_path else None,
            "bullets": len(summary.bullet_points or []),
            "exec_chars": len(summary.executive_summary or ""),
            "success": bool(getattr(summary, "success", True)),
        }
        manifest["version"] = _MANIFEST_VERSION
        manifest["book"] = self._book_title or (self._output_dir.name)
        manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            atomic_write_json(self._manifest_path, manifest, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(
                f"  ⚠️ Chapter manifest update failed: {e!r} — chapter files "
                f"remain saved; only the manifest summary is stale.",
                "WARNING",
            )

    def _load_manifest(self) -> dict[str, Any]:
        """Load the manifest, tolerating absence/corruption (crash safety)."""
        try:
            if self._manifest_path.exists():
                import json

                data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _mark_checkpoint_progress(self) -> None:
        """Record chapters-done progress on the phase-level checkpoint.

        V18.20.3.0: uses ``Checkpoint.mark_progress`` — status stays
        "pending" (NEVER "done") until the whole summarization phase
        completes, preserving the A15 invariant: a partial/crashed run must
        re-enter the summarization phase on resume; the chapter-resume
        sentinels decide which chapters to skip.
        """
        try:
            cp = getattr(self._converter, "checkpoint", None)
            if cp is None:
                return
            done = self.saved_count + self.skipped_existing
            cp.mark_progress(
                "summarization",
                chapters_done=done,
                **({"chapters_total": self._chapters_total} if self._chapters_total else {}),
            )
        except Exception as e:
            self._log(f"  ⚠️ Checkpoint progress update failed: {e!r}", "DEBUG")
