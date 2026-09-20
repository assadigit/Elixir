"""V0.18 (Phase 5.2) — shared postcheck primitives.

Moved VERBATIM (byte-identical bodies) from ``postcheck_detectors.py`` when
that 4,762-LOC monolith was regrouped into the ``postchecks/`` package by
detector family (leakage/COT, garble/space, attribution/years, coherence).
``logger`` keeps its historical channel name so log-record ``name`` fields
are unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

# V0.18 (Phase 5.2): literal historical channel name (was
# ``logging.getLogger(__name__)`` in postcheck_detectors.py) — preserves the
# exact log-record ``name`` so log filters/formatters see no change.
logger = logging.getLogger("core.summarisation.postcheck_detectors")


@dataclass
class Issue:
    """A single post-check finding."""

    detector: str
    severity: str
    field: str
    snippet: str
    detail: str


@dataclass
class PostCheckReport:
    """Result of running all post-checks."""

    bullets: list[str] = field(default_factory=list)
    executive_summary: str = ""
    thorough_summary: str = ""
    key_distinctions: str = ""
    theoretical_tensions: str = ""
    issues: list[Issue] = field(default_factory=list)
    fixed_count: int = 0
    flagged_count: int = 0

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)
        if issue.severity == "fix":
            self.fixed_count += 1
        else:
            self.flagged_count += 1

    @property
    def total_findings(self) -> int:
        return len(self.issues)


def _snippet(text: str, pos: int, width: int = 60) -> str:
    """Return a ~``width``-char context window around ``pos``."""
    if not text:
        return ""
    start = max(0, pos - width // 2)
    end = min(len(text), pos + width // 2)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return re.sub(r"\s+", " ", snippet).strip()


def _is_subsequence(short: str, long: str) -> bool:
    """Check if ``short`` is a subsequence of ``long`` (not necessarily contiguous)."""
    it = iter(long)
    return all(c in it for c in short)
