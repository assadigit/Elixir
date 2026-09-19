"""V10.28.0 (Sprint 1): Unified bullet-quarantine system.

This module is the **single source of truth** for every bullet that is
dropped anywhere in the summarisation pipeline.  Before V10.28.0, bullets
were silently discarded at 9 separate sites (F4 source-overlap, Phase 2.2
semantic fact-check, thinking-filter, narrative filter, quality scorer,
B3 dedup, Content Judge grounding, cross-chapter dedup in converter, and
cross-chapter dedup in keypoints_builder).  There was no audit trail, no
recovery mechanism, and no way for the user to see what was removed.

The ``QuarantineLog`` fixes all three problems:

1. **Unified tracking** — every drop site calls
   :meth:`QuarantineLog.add` instead of silently ``continue``-ing past the
   bullet.  The entry records the bullet text, the pipeline stage that
   dropped it, the threshold that was applied, the measured source-overlap,
   and a human-readable reason.

2. **On-disk audit log** — each drop is appended as one JSON line to
   ``output/<book>/logs/drops.jsonl``.  The user can ``grep`` / ``jq`` it
   to audit exactly what the pipeline removed and why.

3. **Recovery** — :meth:`QuarantineLog.recover` re-scans the quarantined
   entries and resurrects any bullet whose ``source_overlap`` exceeds the
   recovery threshold (default 0.30).  Resurrected bullets are marked
   ``recovered: true`` in both the in-memory log and the on-disk file.

Design notes
------------
- **Thread-safe.**  Summarisation runs in a thread pool (``max_workers``).
  All public methods acquire ``self._lock``.
- **Lazy file creation.**  The ``drops.jsonl`` file is created on first
  write, not on construction — matching the V10.25.0 pattern for
  ``diagnostic.jsonl`` (empty files confused users).
- **Conservative-mode aware.**  When the request has
  ``conservative_drops=True``, the caller still *logs* drops to quarantine
  (for the audit trail) but does not actually remove the bullet from the
  output.  See :meth:`QuarantineLog.add` ``actually_dropped`` parameter.
- **No external deps.**  Uses only stdlib so it can be imported safely from
  any code path (including test fixtures).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────

#: Default source-overlap above which a quarantined bullet is resurrected
#: by the recovery pass.  The roadmap (Sprint 1.4) specifies 0.30 — bullets
#: with ≥30% content-word overlap with the source are likely genuine
#: paraphrases, not hallucinations, and should survive.
DEFAULT_RECOVERY_THRESHOLD = 0.30

#: Sub-folder (relative to the book's output root) where the drop log lives.
#: Matches ``OutputPaths.logs_dir`` (``SUB_LOGS = "logs"``).
_DROPS_SUBDIR = "logs"
_DROPS_FILENAME = "drops.jsonl"


# V18.15.8.0 (Fix 3): Prompt-instruction-pattern check for the recovery pass.
# A bullet matching any of these patterns is a prompt-instruction echo, NOT
# summary content — it must NEVER be resurrected regardless of source overlap.
# These patterns mirror the postchecks._PROMPT_LEAKAGE_PATTERNS but are a
# focused subset covering the prompt-instruction-echo class (the V18.15.7.0
# regression shipped bullets like "Reading level: IELTS 7-9" + "Executive
# summary: 150-250 words" + "5 sections in XML format").
_PROMPT_INSTRUCTION_PATTERNS = (
    re.compile(r"^Reading level:\s*IELTS", re.IGNORECASE),
    re.compile(r"^Keep sentences under \d+ words", re.IGNORECASE),
    re.compile(r"^Sentences under \d+ words", re.IGNORECASE),
    re.compile(r"^Preserve (?:technical|all)\s+(?:terms|citations)", re.IGNORECASE),
    re.compile(r"^Use active voice", re.IGNORECASE),
    re.compile(r"^Use common words", re.IGNORECASE),
    re.compile(r"^Executive summary:\s*\d+-\d+\s*words?", re.IGNORECASE),
    re.compile(r"^Bullet points:\s*\d+-\d+\s*items?", re.IGNORECASE),
    re.compile(r"^\d+\s+sections?\s+in\s+XML\s+format", re.IGNORECASE),
    re.compile(r"^Cover all named contributors", re.IGNORECASE),
    re.compile(r"^Include the full progression", re.IGNORECASE),
    re.compile(r"^End with the conclusion", re.IGNORECASE),
    re.compile(r"^Distinguish philosophical from developmental", re.IGNORECASE),
    re.compile(r"^Preserve developmental mechanisms", re.IGNORECASE),
    re.compile(r"^These two requirements seem contradictory", re.IGNORECASE),
    re.compile(r"^Theoretical tensions:\s*\d+-\d+", re.IGNORECASE),
    re.compile(r"^Key distinctions:\s*\d+-\d+", re.IGNORECASE),
    re.compile(r"^Active voice$", re.IGNORECASE),
    re.compile(r"^No invented facts$", re.IGNORECASE),
)


def _matches_prompt_leakage_pattern(bullet: str) -> bool:
    """V18.15.8.0 (Fix 3): Check if a bullet matches a prompt-instruction pattern.

    Returns True if the bullet is a prompt-instruction echo (NOT summary
    content). Used by the quarantine recovery pass to prevent resurrecting
    bullets that were dropped for being prompt-leakage content.

    Args:
        bullet: the bullet text to check.

    Returns:
        True if the bullet matches a prompt-instruction pattern.
    """
    if not bullet:
        return False
    _bullet_stripped = bullet.strip()
    # Check the first 200 chars (prompt-instruction echoes are short + at the start)
    _check = _bullet_stripped[:200]
    return any(pat.search(_check) for pat in _PROMPT_INSTRUCTION_PATTERNS)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class QuarantineEntry:
    """One dropped bullet + its full audit context.

    Fields are deliberately flat (no nested objects) so the entry
    serialises cleanly to a single JSON line in ``drops.jsonl``.
    """

    bullet: str
    stage: str  # e.g. "F4_source_overlap", "B3_dedup"
    threshold: float = 0.0  # the threshold that was applied
    source_overlap: float = 0.0  # measured overlap 0.0–1.0
    reason: str = ""  # human-readable explanation
    chapter: str = ""  # chapter heading ("" if unknown)
    actually_dropped: bool = True  # False in conservative mode (logged but kept)
    recovered: bool = False  # True after the recovery pass resurrects it
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Round floats for cleaner JSONL
        d["threshold"] = round(float(self.threshold), 4)
        d["source_overlap"] = round(float(self.source_overlap), 4)
        d["timestamp"] = round(float(self.timestamp), 3)
        return d


# ── QuarantineLog ────────────────────────────────────────────────────────────


class QuarantineLog:
    """Thread-safe, on-disk-backed log of every bullet dropped by the pipeline.

    Lifecycle
    ---------
    1. ``QuarantineLog(output_dir)`` — create once per conversion (the
       ``Summarizer`` does this in ``__init__``).
    2. ``add(...)`` — called from every drop site.  Appends to the in-memory
       list AND writes one JSON line to ``drops.jsonl``.
    3. ``recover(source_text)`` — called once after all drops.  Returns the
       list of bullets to resurrect (those with overlap > threshold).
    4. ``mark_recovered(bullet)`` — called for each resurrected bullet so the
       on-disk log reflects the recovery (``recovered: true``).

    The on-disk file is append-only JSONL — each line is one
    :class:`QuarantineEntry` dict.  This makes it greppable and safe to
    inspect mid-conversion.
    """

    def __init__(
        self,
        output_dir: Path | None,
        recovery_threshold: float = DEFAULT_RECOVERY_THRESHOLD,
        log_callback=None,
    ) -> None:
        # RLock (re-entrant) so mark_recovered() can hold the lock while
        # calling _rewrite_entry_on_disk() which also acquires it.
        self._lock = threading.RLock()
        self._entries: list[QuarantineEntry] = []
        self._recovery_threshold = float(recovery_threshold)
        self._log = log_callback or (lambda msg, level="DEBUG": None)
        # Resolve the drops.jsonl path.  output_dir may be None when the
        # summarizer is instantiated outside a real conversion (e.g. unit
        # tests) — in that case we keep the in-memory log but skip disk.
        if output_dir is not None:
            self._drops_path: Path | None = Path(output_dir) / _DROPS_SUBDIR / _DROPS_FILENAME
        else:
            self._drops_path = None

    # ── properties ──────────────────────────────────────────────────────

    @property
    def drops_path(self) -> Path | None:
        """Absolute path to ``drops.jsonl`` (None if no output_dir given)."""
        return self._drops_path

    @property
    def recovery_threshold(self) -> float:
        return self._recovery_threshold

    @property
    def entries(self) -> list[QuarantineEntry]:
        """Snapshot copy of all quarantine entries (thread-safe)."""
        with self._lock:
            return list(self._entries)

    @property
    def dropped_count(self) -> int:
        """Number of entries that were actually dropped (excludes conservative-logged)."""
        with self._lock:
            return sum(1 for e in self._entries if e.actually_dropped)

    @property
    def recovered_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._entries if e.recovered)

    # ── core API ────────────────────────────────────────────────────────

    def add(
        self,
        bullet: str,
        stage: str,
        threshold: float = 0.0,
        source_overlap: float = 0.0,
        reason: str = "",
        chapter: str = "",
        actually_dropped: bool = True,
    ) -> QuarantineEntry:
        """Record one dropped bullet.

        Parameters
        ----------
        bullet:
            The bullet text (truncated to 500 chars internally to keep the
            JSONL readable — full text is rarely needed for audit).
        stage:
            Short machine-readable stage id, e.g. ``"F4_source_overlap"``,
            ``"Phase2.2_semantic_fact_check"``, ``"B3_dedup"``,
            ``"thinking_filter"``, ``"quality_scorer"``,
            ``"judge_grounding"``, ``"cross_chapter_dedup"``.
        threshold:
            The threshold value that was applied at this drop site.
        source_overlap:
            The measured source overlap (0.0–1.0) at drop time.  Used by
            the recovery pass.
        reason:
            Human-readable explanation (shown in the UI panel).
        chapter:
            Chapter heading (best-effort context).
        actually_dropped:
            ``True`` (default) when the bullet was really removed from the
            output.  ``False`` in conservative mode — the drop is *logged*
            for audit but the bullet was kept in the output.  This lets the
            user see "in conservative mode, N bullets *would have been*
            dropped" without losing them.
        """
        entry = QuarantineEntry(
            bullet=str(bullet)[:500],
            stage=str(stage),
            threshold=float(threshold),
            source_overlap=float(source_overlap),
            reason=str(reason),
            chapter=str(chapter),
            actually_dropped=bool(actually_dropped),
            recovered=False,
        )
        with self._lock:
            self._entries.append(entry)
        self._append_to_disk(entry)
        return entry

    def recover(self, source_text: str = "") -> list[QuarantineEntry]:
        """Re-scan the quarantine and resurrect high-overlap bullets.

        A bullet is resurrected when its recorded ``source_overlap`` exceeds
        :attr:`recovery_threshold` (default 0.30).  If ``source_text`` is
        provided, the overlap is recomputed fresh (more accurate than the
        value recorded at drop time, which may have been computed against a
        truncated/earlier source).  If recomputation fails or the recorded
        value is higher, the recorded value is used.

        Returns
        -------
        list of :class:`QuarantineEntry`
            The entries that were resurrected (already marked
            ``recovered=True`` on disk).  The caller is responsible for
            re-inserting the ``.bullet`` text into the live bullet list.
        """
        resurrected: list[QuarantineEntry] = []
        # Snapshot under lock, then process outside (recompute may be slow).
        with self._lock:
            snapshot = list(self._entries)

        for entry in snapshot:
            if entry.recovered or not entry.actually_dropped:
                continue  # already recovered, or only logged (conservative)
            # V18.15.8.0 (Fix 2): Skip Phase 2.2 entries — these were dropped
            # for SEMANTIC reasons (prompt-instruction content, low semantic
            # similarity to the source), NOT source-overlap reasons. The
            # recovery pass is designed for the latter (bullets that were
            # dropped by F4_source_overlap but actually DO have decent overlap
            # when re-checked). Resurrecting Phase 2.2 entries defeats the
            # purpose of the semantic fact-check — the V18.15.7.0 golden-master
            # shipped 6 prompt-instruction bullets because the recovery pass
            # resurrected them via word-overlap false positives (prompt-
            # instruction bullets contain source vocabulary like "identity",
            # "development" → false-positive >0.30 overlap).
            if entry.stage == "Phase2.2_semantic_fact_check":
                continue  # don't resurrect semantic-fact-check drops
            # V18.16.0.1 (Fix 3): Skip thinking_filter.* entries — these were
            # dropped by _filter_thinking_bullets because they're THINKING
            # CONTENT (CoT, narrative, meta-commentary), NOT summary bullets.
            # The V18.16.0.0 regression: 95 thinking-filter drops were
            # resurrected by the recovery pass (via word-overlap false positives
            # — thinking content often contains source vocabulary). This caused
            # the 93→80 bullet explosion + extensive prompt-leakage bullets.
            # Thinking-filter drops should NEVER be resurrected — they were
            # dropped for being thinking content, not for low source overlap.
            if entry.stage.startswith("thinking_filter."):
                continue  # don't resurrect thinking-content drops
            # V18.15.8.0 (Fix 3): Prompt-instruction-pattern check. Even if a
            # bullet has high source overlap (word-overlap false positive), do
            # NOT resurrect it if it matches a prompt-leakage pattern. The
            # V18.15.7.0 run shipped bullets like "Reading level: IELTS 7-9,
            # sentences under 20 words" + "Executive summary: 150-250 words"
            # because the recovery pass saw decent word overlap. These are
            # prompt-instruction echoes, NOT summary content.
            if entry.bullet and _matches_prompt_leakage_pattern(entry.bullet):
                continue  # don't resurrect prompt-instruction bullets
            overlap = entry.source_overlap
            if source_text and entry.bullet:
                try:
                    from core.summarisation.text_preprocessor import (
                        compute_source_overlap,
                    )

                    fresh = compute_source_overlap(entry.bullet, source_text)
                    # V18.15.7.0 (Fix 2): PREFER the fresh computation when it's
                    # available. Pre-V18.15.7.0, this used `overlap = max(overlap,
                    # fresh)` — which was WRONG because some callers (e.g.,
                    # Phase2.2_semantic_fact_check in bullet_pipeline.py) mislabeled
                    # semantic similarity as source_overlap. The max() then picked
                    # the stale-high value (0.45 semantic sim) over the fresh-
                    # computed genuine overlap (~0.0 for "Keep sentences under 20
                    # words"), resurrecting prompt-instruction bullets. The V18.15.6.0
                    # golden-master shipped these 3 bullets because of this bug.
                    # Fresh is always more accurate than a stale recorded value.
                    overlap = fresh
                except Exception as _e:
                    # V18.20.3.8 (Phase 1 / W9): the recovery pass keeps the
                    # stale recorded overlap when the fresh computation
                    # fails — fail-safe is right, but the degraded value
                    # must be visible or an audit reads a resurrected (or
                    # non-resurrected) bullet as fully evaluated.
                    logger.warning(
                        "quarantine recovery: fresh overlap recompute failed "
                        "— keeping the stale recorded value for this entry: "
                        "%s: %s",
                        type(_e).__name__,
                        _e,
                    )
                    pass  # keep recorded value (fresh computation failed)
            if overlap > self._recovery_threshold:
                entry.recovered = True
                entry.source_overlap = overlap
                resurrected.append(entry)
                self._rewrite_entry_on_disk(entry)

        if resurrected:
            self._log(
                f"  ♻️  Recovery pass: resurrected {len(resurrected)} quarantined "
                f"bullet(s) with source overlap > {self._recovery_threshold:.0%}.",
                "INFO",
            )
        else:
            self._log(
                f"  ♻️  Recovery pass: no bullets eligible for recovery "
                f"(threshold {self._recovery_threshold:.0%}).",
                "DEBUG",
            )
        return resurrected

    def mark_recovered(self, bullet: str) -> bool:
        """Mark the first unrecovered entry matching ``bullet`` as recovered.

        Used by the quarantine UI panel's "Restore" button (manual recovery)
        and by :meth:`recover` for each resurrected bullet.

        Returns ``True`` if an entry was found and updated.
        """
        needle = str(bullet).strip()[:500]
        with self._lock:
            for entry in self._entries:
                if entry.bullet == needle and not entry.recovered:
                    entry.recovered = True
                    self._rewrite_entry_on_disk(entry)
                    return True
        return False

    def serialize(self) -> list[dict[str, Any]]:
        """Return all entries as a list of JSON-serialisable dicts."""
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def summary(self) -> dict[str, int]:
        """Return a {stage: count} breakdown of drops (for logging/UI)."""
        with self._lock:
            out: dict[str, int] = {}
            for e in self._entries:
                out[e.stage] = out.get(e.stage, 0) + 1
            return out

    # ── disk I/O ────────────────────────────────────────────────────────

    def _append_to_disk(self, entry: QuarantineEntry) -> None:
        """Append one entry as a JSON line to ``drops.jsonl`` (best-effort)."""
        if self._drops_path is None:
            return
        try:
            self._drops_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(entry.to_dict(), ensure_ascii=False)
            with open(self._drops_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as exc:  # pragma: no cover — disk is best-effort
            self._log(
                f"  ⚠️ Quarantine: failed to write drops.jsonl ({type(exc).__name__}: {exc})",
                "WARNING",
            )

    def _rewrite_entry_on_disk(self, entry: QuarantineEntry) -> None:
        """Update a single entry's ``recovered`` flag in the on-disk file.

        Because the file is append-only JSONL, we rewrite the whole file
        with the updated entry.  This is O(n) but n is small (typically
        < 100 drops per book) and only happens during the recovery pass
        (once per chapter) — not a hot path.
        """
        if self._drops_path is None or not self._drops_path.exists():
            # File not yet written (e.g. conservative-only entries that were
            # logged in-memory but the disk append failed).  Try a fresh append.
            self._append_to_disk(entry)
            return
        try:
            with self._lock:
                # Read all lines, rewrite the matching one.
                lines = self._drops_path.read_text(encoding="utf-8").splitlines()
                updated = False
                needle = entry.bullet
                for i, line in enumerate(lines):
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        obj.get("bullet") == needle
                        and not obj.get("recovered", False)
                        and obj.get("stage") == entry.stage
                    ):
                        obj["recovered"] = True
                        obj["source_overlap"] = round(float(entry.source_overlap), 4)
                        lines[i] = json.dumps(obj, ensure_ascii=False)
                        updated = True
                        break
                if updated:
                    self._drops_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            self._log(
                f"  ⚠️ Quarantine: failed to update drops.jsonl ({type(exc).__name__}: {exc})",
                "WARNING",
            )

    # ── static helpers (for the UI panel) ───────────────────────────────

    @staticmethod
    def load_from_disk(drops_path: Path) -> list[dict[str, Any]]:
        """Read a ``drops.jsonl`` file and return its entries as dicts.

        Used by :class:`ui_qt.views.quarantine_view.QuarantineView` to
        populate the table without holding a reference to the live
        ``QuarantineLog`` instance (the conversion may have finished).
        """
        if not drops_path or not Path(drops_path).exists():
            return []
        out: list[dict[str, Any]] = []
        unreadable = 0
        total_lines = 0
        try:
            for line in Path(drops_path).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    unreadable += 1
                    continue
        except Exception as _e:
            # V18.20.3.8 (Phase 1 / W9): a corrupted drops.jsonl used to read
            # as "no drops" at DEBUG — the quarantine audit trail silently
            # vanishing is exactly the silent-failure class the house rule
            # bans. Report the failure AND what was salvaged.
            logger.warning(
                "drops.jsonl unreadable (%s: %s) — treating as empty; "
                "salvaged %d entry(ies) before the failure",
                type(_e).__name__,
                _e,
                len(out),
            )
            return out
        if unreadable:
            logger.warning(
                "drops.jsonl: %d of %d line(s) unreadable (corrupt JSON) — salvaged %d entr%s",
                unreadable,
                total_lines,
                len(out),
                "y" if len(out) == 1 else "ies",
            )
        return out

    @staticmethod
    def find_drops_log(book_output_dir: Path) -> Path | None:
        """Locate ``drops.jsonl`` for a given book output directory."""
        if not book_output_dir:
            return None
        p = Path(book_output_dir) / _DROPS_SUBDIR / _DROPS_FILENAME
        return p if p.exists() else None


__all__ = [
    "QuarantineEntry",
    "QuarantineLog",
    "DEFAULT_RECOVERY_THRESHOLD",
]
