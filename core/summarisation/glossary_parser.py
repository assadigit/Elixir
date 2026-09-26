"""V0.5.6 Phase 0.5 — source glossary extraction (parser + persistence + cross-ref).

The V0.5.5 audit found 5 source authors still missing from the chapter 6
summary (the LAYER's ``extract_citations`` caught them but the gap-fill's
quote-guard dropped their bullets — see the ``AUDIT-V0.5.5`` worklog
entry's "V0.5.6 BACKLOG"). V0.5.6 fuses a **source glossary** extraction
into the master-summary LLM call (Call 1/3 in ``_chunked_summarize`` /
``_summarize_inner``'s map-reduce master-summary derivation), persists it
as a ``.glossary.md`` file under ``summaries/.glossaries/``, and uses it
as the coverage ground truth (richer than the regex).

The glossary has 3 markdown subsections (per the user's directive
"glossary (dates, names, specific terms)"):

    <name_glossary>
    ## Names
    - **Surname** (YYYY) — 1-sentence context of their contribution
    - **Surname** (YYYYa, YYYYb) — context
    ## Dates
    - **YYYY-YYYY** — what the range refers to
    - **YYYYs** (decade) — context
    ## Terms
    - **term** — 1-sentence definition
    </name_glossary>

``parse_name_glossary`` extracts the block + parses the 3 subsections into
the dict::

    {
        "names": [{"name": "Bak", "year": "1946", "context": "..."}],
        "dates": [{"date": "1887-1902", "context": "..."}],
        "terms": [{"term": "paranoid-schizoid position", "context": "..."}],
    }

Fail-open: a missing OR malformed block returns
``{"names": [], "dates": [], "terms": []}`` (never crashes the
master-summary — the LLM might omit the block on a quant that can't
follow the prompt).

``cross_reference_glossary`` is the deterministic backstop that keeps
the LLM honest (mitigates the hallucination risk): every glossary name
is checked against the regex ``extract_citations`` output, and any
LLM-only name (regex missed — kept, flagged) or regex-only name (LLM
missed — flagged as a recall gap) is reported.

``persist_glossary`` writes the glossary dict to disk as
``summaries/.glossaries/<chapter_slug>.glossary.md`` (auditable —
Rule 4 provenance).

Content-agnostic (Rule 1 ✓): the prompt instruction is generic ("ALL
cited authors"); the parser uses generic regex (``<name_glossary>``,
``## Names``, ``## Dates``, ``## Terms``); the cross-reference compares
two sets of runtime-extracted names. NO hardcoded book/author/chapter
names.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

# Type aliases.
LogCallback = Callable[[str, str], None]

# ── The empty-glossary sentinel (returned by every fail-open path) ──────────

_EMPTY_GLOSSARY: dict[str, list] = {"names": [], "dates": [], "terms": []}


# ── Block + section-header regexes ───────────────────────────────────────────
#
# Generic XML-block + markdown-header regexes (no book/author content —
# Rule 1 ✓). The block regex is non-greedy + DOTALL so a single block is
# captured even when the response spans multiple ``<...>`` tags. The
# section-header regexes are case-insensitive + MULTILINE so the LLM's
# markdown subsection headers (``## Names`` / ``## Dates`` / ``## Terms``)
# are matched regardless of case/whitespace variation.

_GLOSSARY_BLOCK_RE = re.compile(r"<name_glossary>(.*?)</name_glossary>", re.DOTALL | re.IGNORECASE)

_SECTION_HEADERS: dict[str, re.Pattern[str]] = {
    "names": re.compile(r"^##\s*Names\s*$", re.IGNORECASE | re.MULTILINE),
    "dates": re.compile(r"^##\s*Dates\s*$", re.IGNORECASE | re.MULTILINE),
    "terms": re.compile(r"^##\s*Terms\s*$", re.IGNORECASE | re.MULTILINE),
}


# ── Bullet-line regexes (one per subsection — the bullet SHAPE differs) ──────
#
# Names: ``- **Surname** (YYYY) — context``  (year group is optional — the
#   LLM may write ``- **Surname** — context`` without a year)
# Dates: ``- **YYYY-YYYY** — context`` / ``- **YYYYs** — context`` (no year
#   group — the "date" payload is free-form, may be a range, decade, or
#   plain year)
# Terms: ``- **term** — context`` (no year — the "term" payload is the
#   bolded text)

# The em-dash separator after the bold is optional: some LLMs use a hyphen,
# colon, or just a space. The bullet MUST start with ``-`` or ``*`` and have
# a ``**bold**`` payload at the front.

_BULLET_PREFIX_RE = r"^\s*[-*]\s+\*\*(?P<payload>[^*]+?)\*\*\s*"

_NAME_BULLET_RE = re.compile(
    _BULLET_PREFIX_RE
    # Optional year group: ``(YYYY)`` or ``(YYYYa, YYYYb)`` — the LLM may
    # omit it for authors whose year is unknown / for an organization.
    + r"(?:\((?P<year>\d{4}[a-z]?(?:\s*,\s*\d{4}[a-z]?)*)\))?\s*"
    # Optional separator (em-dash, hyphen, colon) before the context.
    + r"(?:[\u2014\-\u2013:]\s*)?"
    + r"(?P<context>.*)$"
)

_DATE_BULLET_RE = re.compile(_BULLET_PREFIX_RE + r"(?:[\u2014\-\u2013:]\s*)?" + r"(?P<context>.*)$")

_TERM_BULLET_RE = re.compile(_BULLET_PREFIX_RE + r"(?:[\u2014\-\u2013:]\s*)?" + r"(?P<context>.*)$")


# ── parse_name_glossary ─────────────────────────────────────────────────────


def parse_name_glossary(raw_response: str | None) -> dict[str, list[dict[str, str]]]:
    """Parse a ``<name_glossary>`` block from an LLM response.

    Args:
        raw_response: the FULL raw master-summary LLM response (the same
            string the master-summary parser sees — the ``<name_glossary>``
            block lives alongside ``<thorough_summary>``, NOT inside it).
            Accepts ``None`` / empty (fail-open).

    Returns:
        A dict with 3 keys (``names``, ``dates``, ``terms``), each a list
        of ``{...}`` dicts:

            {
                "names": [{"name": "Bak", "year": "1946", "context": "..."}],
                "dates": [{"date": "1887-1902", "context": "..."}],
                "terms": [{"term": "paranoid-schizoid position", "context": "..."}],
            }

        Fail-open: if the ``<name_glossary>`` block is absent OR malformed,
        returns ``{"names": [], "dates": [], "terms": []}`` (NEVER raises —
        the master-summary has already succeeded; the glossary is a
        best-effort add-on).
    """
    if not raw_response or not raw_response.strip():
        return _copy_empty()
    block_match = _GLOSSARY_BLOCK_RE.search(raw_response)
    if not block_match:
        return _copy_empty()
    block = block_match.group(1)
    try:
        return _parse_sections(block)
    except Exception as _e:  # noqa: BLE001 — fail-open
        logger.debug(
            "V0.5.6 glossary parse crashed (non-fatal — returning empty): %s: %s",
            type(_e).__name__,
            _e,
        )
        return _copy_empty()


def _copy_empty() -> dict[str, list]:
    """Return a fresh empty glossary dict (independent of the module sentinel)."""
    return {
        "names": list(_EMPTY_GLOSSARY["names"]),
        "dates": list(_EMPTY_GLOSSARY["dates"]),
        "terms": list(_EMPTY_GLOSSARY["terms"]),
    }


def _parse_sections(block: str) -> dict[str, list[dict[str, str]]]:
    """Split a glossary block on its 3 ## headers + parse each subsection.

    The block may carry any subset of the 3 subsection headers (a model
    might emit only ``## Names`` if the chapter has no key dates). Missing
    subsections return an empty list — fail-open, not fail-loud.
    """
    found: list[tuple[str, int, int]] = []  # (key, match_start, header_end)
    for key, hdr_re in _SECTION_HEADERS.items():
        m = hdr_re.search(block)
        if m:
            found.append((key, m.start(), m.end()))
    found.sort(key=lambda t: t[1])

    sections_text: dict[str, str] = dict.fromkeys(_SECTION_HEADERS, "")
    for i, (key, _start, hdr_end) in enumerate(found):
        body_end = found[i + 1][1] if i + 1 < len(found) else len(block)
        sections_text[key] = block[hdr_end:body_end]

    return {
        "names": _parse_name_bullets(sections_text["names"]),
        "dates": _parse_date_bullets(sections_text["dates"]),
        "terms": _parse_term_bullets(sections_text["terms"]),
    }


def _parse_name_bullets(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        m = _NAME_BULLET_RE.match(line)
        if not m:
            continue
        name = (m.group("payload") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "year": (m.group("year") or "").strip(),
                "context": (m.group("context") or "").strip(),
            }
        )
    return out


def _parse_date_bullets(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        m = _DATE_BULLET_RE.match(line)
        if not m:
            continue
        date = (m.group("payload") or "").strip()
        if not date:
            continue
        out.append(
            {
                "date": date,
                "context": (m.group("context") or "").strip(),
            }
        )
    return out


def _parse_term_bullets(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        m = _TERM_BULLET_RE.match(line)
        if not m:
            continue
        term = (m.group("payload") or "").strip()
        if not term:
            continue
        out.append(
            {
                "term": term,
                "context": (m.group("context") or "").strip(),
            }
        )
    return out


# ── cross_reference_glossary (deterministic backstop) ──────────────────────


def cross_reference_glossary(
    glossary_names: Iterable[str] | None,
    regex_authors: Iterable[str] | set[str] | None,
) -> dict[str, list[str]]:
    """Cross-reference the LLM glossary names against the regex backstop.

    The LLM glossary is the rich coverage ground truth (richer than the
    regex), but the LLM can hallucinate. The deterministic
    ``extract_citations`` regex keeps the LLM honest — every glossary
    name is checked against the regex output, and any LLM-only or
    regex-only name is flagged.

    Args:
        glossary_names: the ``name`` field of every parsed glossary entry
            (the LLM-extracted source roster).
        regex_authors: the ``author`` field of every ``extract_citations``
            entry (the regex-extracted author set — the deterministic
            backstop).

    Returns:
        ``{"confirmed": [...], "llm_only": [...], "regex_only": [...]}``:

          - ``confirmed``  — names in BOTH (LLM glossary + regex)
          - ``llm_only``   — LLM-extracted names the regex MISSED
            (kept — the regex might legitimately have missed them, e.g.
            multi-word surnames the regex doesn't catch); flagged in
            the log so the user can audit.
          - ``regex_only``  — regex-caught names the LLM MISSED
            (a recall gap to flag — the LLM glossary should have
            caught them).
    """
    g = {n.strip() for n in (glossary_names or []) if n and n.strip()}
    r = {a.strip() for a in (regex_authors or set()) if a and a.strip()}
    return {
        "confirmed": sorted(g & r),
        "llm_only": sorted(g - r),
        "regex_only": sorted(r - g),
    }


# ── persist_glossary (write the .glossary.md file) ──────────────────────────


def persist_glossary(
    glossary: dict[str, list[dict[str, str]]] | None,
    out_path: Path | str,
    *,
    chapter_title: str = "",
    run_id: str = "",
    app_version: str = "",
) -> Path:
    """Write a glossary dict to disk as a markdown file.

    Creates the parent dir if absent (lazy — the
    ``summaries/.glossaries/`` folder is created only when a chapter
    actually has a glossary to persist). Fail-open: if writing fails,
    logs a WARNING and returns the path anyway (the master-summary has
    already succeeded — persistence is best-effort).

    The format::

        # Source Glossary — <chapter title>
        <!-- generated-by: Elixir <version> | run_id=... | chapter=... -->

        ## Names
        - **Name** (Year) — context
        ...

        ## Dates
        - **Date** — context
        ...

        ## Terms
        - **Term** — context
        ...
    """
    out_path = Path(out_path)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as _e:
        logger.warning(
            "V0.5.6 glossary persist: could not create %s: %s",
            out_path.parent,
            _e,
        )
        return out_path

    lines: list[str] = []
    title = (chapter_title or "").strip() or "Source Glossary"
    lines.append(f"# Source Glossary — {title}")
    _meta_parts = [f"generated-by: Elixir {app_version}".strip()]
    if run_id:
        _meta_parts.append(f"run_id={run_id}")
    if chapter_title:
        _meta_parts.append(f"chapter={chapter_title}")
    lines.append(f"<!-- {' | '.join(_meta_parts)} -->")
    lines.append("")

    glossary = glossary or {}
    lines.append("## Names")
    for n in glossary.get("names", []):
        name = n.get("name", "")
        year = n.get("year", "")
        ctx = n.get("context", "")
        if year:
            lines.append(f"- **{name}** ({year}) — {ctx}".rstrip())
        else:
            lines.append(f"- **{name}** — {ctx}".rstrip())
    lines.append("")
    lines.append("## Dates")
    for d in glossary.get("dates", []):
        date = d.get("date", "")
        ctx = d.get("context", "")
        lines.append(f"- **{date}** — {ctx}".rstrip())
    lines.append("")
    lines.append("## Terms")
    for t in glossary.get("terms", []):
        term = t.get("term", "")
        ctx = t.get("context", "")
        lines.append(f"- **{term}** — {ctx}".rstrip())
    lines.append("")

    try:
        out_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as _e:
        logger.warning(
            "V0.5.6 glossary persist: could not write %s: %s",
            out_path,
            _e,
        )
    return out_path


# ── High-level helper (used by the master-summary call sites) ───────────────


def extract_persist_and_cross_reference_glossary(
    raw_response: str | None,
    *,
    heading: str,
    output_dir: Path | str,
    run_id: str = "",
    app_version: str = "",
    regex_authors: Iterable[str] | set[str] | None = None,
    log: LogCallback | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Parse + persist + cross-reference a glossary in one call.

    Used by the master-summary call sites (the single-pass
    ``_chunked_summarize`` + the map-reduce ``_summarize_inner``
    master-summary derivation) so the wiring is one line at each site.
    Fail-open: NEVER raises — every step is wrapped in try/except and
    returns an empty glossary on any error.

    Side-effects (best-effort, all logged):
      1. Parses the ``<name_glossary>`` block from the raw response.
      2. Persists it to ``<output_dir>/summaries/.glossaries/<slug>.glossary.md``
         (creates the dir if absent) — logs ``📖 V0.5.6 source glossary → <path>``.
      3. Cross-references the glossary names against ``regex_authors`` (the
         ``extract_citations`` output for THIS chapter's source) — logs
         ``⚠️ glossary name 'X' not in regex extract_citations — kept (LLM
         catch, regex missed)`` for every LLM-only name, and
         ``⚠️ regex-caught name 'Y' not in LLM glossary — recall gap`` for
         every regex-only name.
    """
    if log is None:
        log = _noop_log
    # Step 1: parse (fail-open).
    try:
        glossary = parse_name_glossary(raw_response)
    except Exception as _e:  # noqa: BLE001 — fail-open
        logger.warning(
            "V0.5.6 glossary parse crashed (non-fatal — empty glossary): %s: %s",
            type(_e).__name__,
            _e,
        )
        glossary = _copy_empty()

    # Step 2: persist (fail-open). Skip if the glossary is empty (the
    # LLM didn't emit a block OR emitted a malformed one) — no point
    # writing an empty file to disk.
    _is_empty = not (glossary.get("names") or glossary.get("dates") or glossary.get("terms"))
    if _is_empty:
        log(
            "    ℹ️ V0.5.6: no <name_glossary> block parsed from master summary "
            "(skipping persistence + cross-reference)",
            "DEBUG",
        )
        return glossary

    try:
        from core.common.heading_utils import segment_filename_slug

        slug = segment_filename_slug(heading) or "chapter"
    except Exception:  # noqa: BLE001 — fail-open
        slug = "chapter"
    out_path = Path(output_dir) / "summaries" / ".glossaries" / f"{slug}.glossary.md"
    try:
        persist_glossary(
            glossary,
            out_path,
            chapter_title=heading,
            run_id=run_id,
            app_version=app_version,
        )
        log(f"    📖 V0.5.6 source glossary → {out_path}", "INFO")
    except Exception as _e:  # noqa: BLE001 — fail-open
        logger.warning(
            "V0.5.6 glossary persist crashed (non-fatal): %s: %s",
            type(_e).__name__,
            _e,
        )
        log(
            f"    ⚠️ V0.5.6: glossary persist crashed ({type(_e).__name__}: {_e})",
            "WARNING",
        )

    # Step 3: cross-reference (fail-open — only if regex_authors supplied).
    if regex_authors is not None:
        try:
            glossary_names = [n.get("name", "") for n in glossary.get("names", [])]
            xref = cross_reference_glossary(glossary_names, regex_authors)
            for name in xref["llm_only"]:
                log(
                    f"    ⚠️ glossary name '{name}' not in regex extract_citations "
                    f"— kept (LLM catch, regex missed)",
                    "WARNING",
                )
            for name in xref["regex_only"]:
                log(
                    f"    ⚠️ regex-caught name '{name}' not in LLM glossary — recall gap",
                    "WARNING",
                )
            _confirmed = len(xref["confirmed"])
            _llm_only = len(xref["llm_only"])
            _regex_only = len(xref["regex_only"])
            log(
                f"    📊 V0.5.6 glossary xref: confirmed={_confirmed}, "
                f"llm_only={_llm_only}, regex_only={_regex_only}",
                "INFO",
            )
        except Exception as _e:  # noqa: BLE001 — fail-open
            logger.warning(
                "V0.5.6 glossary cross-reference crashed (non-fatal): %s: %s",
                type(_e).__name__,
                _e,
            )

    return glossary


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


__all__ = [
    "parse_name_glossary",
    "cross_reference_glossary",
    "persist_glossary",
    "extract_persist_and_cross_reference_glossary",
]
