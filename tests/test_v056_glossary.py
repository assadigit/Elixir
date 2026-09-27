"""V0.5.6 Phase 0.5 — source glossary extraction (prompt + parser + persistence).

The V0.5.5 audit found 5 source authors still missing from the chapter 6
summary (the LAYER's ``extract_citations`` caught them but the gap-fill's
quote-guard dropped their bullets). V0.5.6 fuses a **source glossary**
extraction into the master-summary LLM call, persists it as a
``.glossary.md`` file, and uses it as the coverage ground truth (richer
than the regex).

This test module covers the V056-PROMPT-PARSER subagent's deliverables:
  1. The parser — ``parse_name_glossary`` extracts the 3 subsections
     (Names / Dates / Terms) from the LLM's ``<name_glossary>`` block,
     fail-open on missing OR malformed block.
  2. The persistence — ``persist_glossary`` writes the glossary dict to
     ``summaries/.glossaries/<slug>.glossary.md`` (auditable, Rule 4).
  3. The cross-reference — ``cross_reference_glossary`` compares the LLM
     glossary names against the regex ``extract_citations`` backstop
     (mitigates the hallucination risk).
  4. The prompt instruction — the master-summary prompt (default.md +
     default_lowbit.md + the actual Call-1/3 master_summary.md) carries
     the generic ``<name_glossary>`` output instruction.

Content-agnostic (Rule 1): the author names + dates + terms in these
tests are TEST FIXTURES (Bak / Freud / Klein / Shapiro) — they do NOT
appear in runtime code. The production parser uses generic regex
(``<name_glossary>``, ``## Names``, ``## Dates``, ``## Terms``); the
cross-reference compares two runtime-extracted name sets. NO hardcoded
book/author/chapter names.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

# Stub tiktoken (not installed in test env) — same pattern as conftest.
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = lambda *a, **k: None
    tk.encoding_for_model = lambda *a, **k: None
    tk.Encoding = type("_E", (), {})
    sys.modules["tiktoken"] = tk

from core.summarisation.glossary_parser import (  # noqa: E402
    cross_reference_glossary,
    extract_persist_and_cross_reference_glossary,
    parse_name_glossary,
    persist_glossary,
)

# ─────────────────────────────────────────────────────────────────────────────
# A realistic, well-formed <name_glossary> block (3 subsections — test fixture).
# The author names + dates + terms here are SYNTHETIC TEST FIXTURES (Rule 1
# exempt — they appear in tests only, not runtime code).
# ─────────────────────────────────────────────────────────────────────────────

_WELL_FORMED_GLOSSARY_RESPONSE = """<thorough_summary>
The chapter covers paranoid personality disorder from psychoanalytic,
descriptive, and DSM-III perspectives.
</thorough_summary>

<name_glossary>
## Names
- **Bak** (1946) — coined the higher level character organization concept
- **Freud** (1911, 1922) — originator of the psychoanalytic framework
- **Klein** (1946a, 1952b) — developed the paranoid-schizoid position
## Dates
- **1887-1902** — early foundational period of psychoanalysis
- **1920s** — the rise of ego psychology
## Terms
- **paranoid-schizoid position** — Klein's developmental substrate
- **projection** — defensive attribution of internal states to others
</name_glossary>
"""


_MALFORMED_GLOSSARY_RESPONSE = """<thorough_summary>The summary.</thorough_summary>

<name_glossary>
## Names
- this bullet has no bold marker so it should be skipped
- ** Valid name ** (broken — but the parser is fail-open + skips bad lines
## Dates
## Terms
- **orphan term with no closing context
</name_glossary>
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1) parse_name_glossary — extracts 3 sections
# ═══════════════════════════════════════════════════════════════════════════


class TestParseNameGlossaryExtractsThreeSections:
    """A well-formed ``<name_glossary>`` block → returns the 3 sections parsed."""

    def test_parse_name_glossary_extracts_3_sections(self):
        g = parse_name_glossary(_WELL_FORMED_GLOSSARY_RESPONSE)
        # The dict has the 3 expected keys.
        assert set(g.keys()) == {"names", "dates", "terms"}, (
            f"expected 3 keys (names/dates/terms), got {set(g.keys())}"
        )
        # Names: 3 entries, each with name/year/context.
        assert len(g["names"]) == 3
        bak = g["names"][0]
        assert bak["name"] == "Bak"
        assert bak["year"] == "1946"
        assert "higher level" in bak["context"]
        # Multi-year form is preserved (e.g. "1911, 1922" / "1946a, 1952b").
        freud = g["names"][1]
        assert freud["name"] == "Freud"
        assert "1911" in freud["year"] and "1922" in freud["year"]
        klein = g["names"][2]
        assert klein["name"] == "Klein"
        assert "1946a" in klein["year"] and "1952b" in klein["year"]
        # Dates: 2 entries — ranges + decades both supported.
        assert len(g["dates"]) == 2
        assert g["dates"][0]["date"] == "1887-1902"
        assert "early" in g["dates"][0]["context"].lower()
        assert g["dates"][1]["date"] == "1920s"
        # Terms: 2 entries.
        assert len(g["terms"]) == 2
        assert g["terms"][0]["term"] == "paranoid-schizoid position"
        assert g["terms"][1]["term"] == "projection"


# ═══════════════════════════════════════════════════════════════════════════
# 2) parse_name_glossary — fail-open on missing block
# ═══════════════════════════════════════════════════════════════════════════


class TestParseNameGlossaryFailOpenOnMissingBlock:
    """No ``<name_glossary>`` block → returns the empty 3-section dict (no crash)."""

    def test_parse_name_glossary_fail_open_on_missing_block(self):
        # A response with ONLY <thorough_summary> (no glossary block at all).
        raw_no_block = "<thorough_summary>Just the summary, no glossary.</thorough_summary>"
        g = parse_name_glossary(raw_no_block)
        assert g == {"names": [], "dates": [], "terms": []}, (
            "missing <name_glossary> block must fail-open with the empty dict"
        )

    def test_parse_name_glossary_fail_open_on_none_input(self):
        g = parse_name_glossary(None)
        assert g == {"names": [], "dates": [], "terms": []}

    def test_parse_name_glossary_fail_open_on_empty_input(self):
        g = parse_name_glossary("")
        assert g == {"names": [], "dates": [], "terms": []}

    def test_parse_name_glossary_fail_open_on_whitespace_only(self):
        g = parse_name_glossary("   \n   \t   ")
        assert g == {"names": [], "dates": [], "terms": []}


# ═══════════════════════════════════════════════════════════════════════════
# 3) parse_name_glossary — fail-open on malformed block
# ═══════════════════════════════════════════════════════════════════════════


class TestParseNameGlossaryFailOpenOnMalformed:
    """A malformed ``<name_glossary>`` block → fail-open (no crash, partial
    parse OK — every well-formed bullet still extracted, every malformed
    bullet skipped)."""

    def test_parse_name_glossary_fail_open_on_malformed(self):
        g = parse_name_glossary(_MALFORMED_GLOSSARY_RESPONSE)
        # The parser MUST NOT crash on the malformed block. It returns a
        # dict with the 3 keys (some possibly empty — the malformed bullets
        # are skipped, the well-formed ones are kept).
        assert set(g.keys()) == {"names", "dates", "terms"}
        # The first names bullet has no ``**bold**`` payload → no match →
        # skipped (the parser never raises on a non-matching bullet).
        # The "broken" bullet uses a different bullet shape → also skipped.
        # So names is empty (the only well-formed bullets were skipped
        # because the test fixture deliberately malforms them).
        assert isinstance(g["names"], list)
        assert isinstance(g["dates"], list)
        assert isinstance(g["terms"], list)

    def test_parse_name_glossary_partial_recovery_from_mixed_input(self):
        """A block with BOTH well-formed + malformed bullets keeps the
        well-formed ones (graceful per-bullet failure, not all-or-nothing)."""
        mixed = """<thorough_summary>x</thorough_summary>

<name_glossary>
## Names
- **Bak** (1946) — coined the higher level concept
- malformed bullet without bold
- **Freud** (1911) — originator
## Dates
## Terms
- **projection** — defensive attribution
</name_glossary>
"""
        g = parse_name_glossary(mixed)
        # 2 of 3 names-bullets are well-formed → kept (Bak + Freud).
        names = [n["name"] for n in g["names"]]
        assert "Bak" in names
        assert "Freud" in names
        # The malformed bullet (no bold) was silently skipped — it did
        # NOT become a fake "name" entry.
        assert len(g["names"]) == 2
        # Dates subsection is present but empty → empty list (fail-open).
        assert g["dates"] == []
        # Terms: 1 well-formed bullet kept.
        assert len(g["terms"]) == 1
        assert g["terms"][0]["term"] == "projection"

    def test_parse_name_glossary_unclosed_block_fail_open(self):
        """An unclosed ``<name_glossary>`` tag → fail-open via Tier 1 (the
        XML regex requires a closing tag — without it, the block match
        fails). V0.5.10: the parser then falls through to Tier 2 (the
        markdown-header scan), which catches the ``## Names`` header + the
        bullet underneath → ``g["names"]`` has 1 entry (Bak). The Tier 1
        block match is gone, but the markdown-header fallback recovers
        the bullets — the parser NEVER crashes on the unclosed XML tag."""
        raw_unclosed = (
            "<thorough_summary>x</thorough_summary>\n\n"
            "<name_glossary>\n## Names\n- **Bak** (1946) — context\n"
            # NO </name_glossary> closer
        )
        g = parse_name_glossary(raw_unclosed)
        # The parser MUST NOT crash on the unclosed XML tag. It returns a
        # dict with the 3 keys (the Tier 1 XML-block regex fails — no
        # closing tag — but the Tier 2 markdown-header fallback catches
        # the ## Names header + the bullet).
        assert set(g.keys()) == {"names", "dates", "terms"}
        # V0.5.10: the Tier 2 markdown-header fallback catches the
        # ``## Names`` header + the bullet → ``g["names"]`` has 1 entry.
        # (Pre-V0.5.10 the parser returned the empty dict — the Tier 1
        # failure was a hard fail-open. V0.5.10's lenient fallback recovers
        # the bullets even when the XML wrapper is malformed.)
        assert len(g["names"]) == 1, (
            f"expected 1 name (Tier 2 markdown-header fallback caught the "
            f"## Names bullet — V0.5.10 lenient recovery), got {len(g['names'])}"
        )
        assert g["names"][0]["name"] == "Bak"
        assert g["names"][0]["year"] == "1946"
        # No ## Dates / ## Terms headers in the fixture → empty lists.
        assert g["dates"] == []
        assert g["terms"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 4) persist_glossary — writes the .md file
# ═══════════════════════════════════════════════════════════════════════════


class TestPersistGlossaryWritesMdFile:
    """The glossary is written to the expected path with the right format."""

    def test_persist_glossary_writes_md_file(self, tmp_path):
        g = parse_name_glossary(_WELL_FORMED_GLOSSARY_RESPONSE)
        out_path = tmp_path / "summaries" / ".glossaries" / "ch.glossary.md"
        # The dir doesn't exist yet — persist_glossary must create it.
        assert not out_path.parent.exists()
        returned = persist_glossary(
            g,
            out_path,
            chapter_title="Test Chapter",
            run_id="run-abc123",
            app_version="0.5.6",
        )
        # The function returns the path (even on failure).
        assert returned == out_path
        # The file is now on disk.
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        # Header + provenance comment.
        assert content.startswith("# Source Glossary — Test Chapter")
        assert "generated-by: Elixir 0.5.6" in content
        assert "run_id=run-abc123" in content
        assert "chapter=Test Chapter" in content
        # 3 subsections.
        assert "## Names" in content
        assert "## Dates" in content
        assert "## Terms" in content
        # Names: each entry rendered as ``- **Name** (Year) — context``.
        assert "- **Bak** (1946) —" in content
        assert "- **Freud** (1911, 1922) —" in content
        assert "- **Klein** (1946a, 1952b) —" in content
        # Dates: ``- **Date** — context``.
        assert "- **1887-1902** —" in content
        assert "- **1920s** —" in content
        # Terms: ``- **Term** — context``.
        assert "- **paranoid-schizoid position** —" in content
        assert "- **projection** —" in content

    def test_persist_glossary_handles_empty_glossary(self, tmp_path):
        """An empty glossary still produces a valid file (3 empty subsections
        — fail-open, NOT a crash)."""
        out_path = tmp_path / "summaries" / ".glossaries" / "empty.glossary.md"
        persist_glossary(
            {"names": [], "dates": [], "terms": []},
            out_path,
            chapter_title="Empty",
        )
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert content.startswith("# Source Glossary — Empty")
        assert "## Names" in content
        assert "## Dates" in content
        assert "## Terms" in content

    def test_persist_glossary_handles_none_glossary(self, tmp_path):
        """A None glossary is treated as empty (fail-open)."""
        out_path = tmp_path / "x.glossary.md"
        persist_glossary(None, out_path, chapter_title="X")
        assert out_path.exists()


# ═══════════════════════════════════════════════════════════════════════════
# 5) cross_reference_glossary — confirmed / llm_only / regex_only buckets
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossReferenceGlossary:
    """Glossary names vs regex authors → confirmed/llm_only/regex_only buckets correct."""

    def test_cross_reference_glossary(self):
        # Glossary (LLM) extracted: Bak, Freud, Klein, Meissner.
        glossary_names = ["Bak", "Freud", "Klein", "Meissner"]
        # Regex extract_citations caught: Bak, Freud, Shapiro, Klein.
        regex_authors = {"Bak", "Freud", "Shapiro", "Klein"}
        x = cross_reference_glossary(glossary_names, regex_authors)
        # confirmed: in BOTH → Bak, Freud, Klein (3).
        assert set(x["confirmed"]) == {"Bak", "Freud", "Klein"}
        # llm_only: LLM caught but regex missed → Meissner (1).
        assert set(x["llm_only"]) == {"Meissner"}
        # regex_only: regex caught but LLM missed → Shapiro (1).
        assert set(x["regex_only"]) == {"Shapiro"}
        # Bucket sizes are consistent.
        assert len(x["confirmed"]) + len(x["llm_only"]) == len(glossary_names)
        assert len(x["confirmed"]) + len(x["regex_only"]) == len(regex_authors)

    def test_cross_reference_glossary_perfect_overlap(self):
        """When both sides return the same set, llm_only + regex_only are empty."""
        names = ["A", "B", "C"]
        regex = {"A", "B", "C"}
        x = cross_reference_glossary(names, regex)
        assert set(x["confirmed"]) == {"A", "B", "C"}
        assert x["llm_only"] == []
        assert x["regex_only"] == []

    def test_cross_reference_glossary_empty_inputs(self):
        """Empty inputs → all 3 buckets empty (no crash)."""
        x = cross_reference_glossary([], set())
        assert x == {"confirmed": [], "llm_only": [], "regex_only": []}
        # None inputs also tolerated.
        x2 = cross_reference_glossary(None, None)
        assert x2 == {"confirmed": [], "llm_only": [], "regex_only": []}

    def test_cross_reference_glossary_strips_whitespace(self):
        """Whitespace + empty entries are stripped before the set comparison
        (defensive — the LLM might emit a stray space)."""
        names = ["  Bak  ", "", "Freud", "   "]
        regex = {"Bak", "Freud"}
        x = cross_reference_glossary(names, regex)
        assert set(x["confirmed"]) == {"Bak", "Freud"}
        assert x["llm_only"] == []
        assert x["regex_only"] == []

    def test_extract_persist_and_cross_reference_glossary_end_to_end(self, tmp_path):
        """End-to-end: parse + persist + cross-reference in one call (the
        helper used by the master-summary call sites)."""
        # A glossary fixture with 4 names — 3 in the regex (Bak/Freud/Klein)
        # + 1 LLM-only (Meissner, the regex missed). The regex also has
        # Shapiro (the LLM missed — regex_only bucket).
        glossary_response = """<thorough_summary>summary</thorough_summary>

<name_glossary>
## Names
- **Bak** (1946) — coined the higher level character organization concept
- **Freud** (1911, 1922) — originator of the psychoanalytic framework
- **Klein** (1946a, 1952b) — developed the paranoid-schizoid position
- **Meissner** (1980) — LLM-caught; the regex extract_citations missed
## Dates
- **1887-1902** — early foundational period of psychoanalysis
## Terms
- **paranoid-schizoid position** — Klein's developmental substrate
</name_glossary>
"""
        logs: list[tuple[str, str]] = []

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        regex_authors = {"Bak", "Freud", "Shapiro", "Klein"}
        g = extract_persist_and_cross_reference_glossary(
            glossary_response,
            heading="Test Chapter",
            output_dir=tmp_path,
            run_id="run-xyz",
            app_version="0.5.6",
            regex_authors=regex_authors,
            log=log,
        )
        # The glossary was parsed correctly (4 names — 3 confirmed + 1 LLM-only).
        assert len(g["names"]) == 4
        # The .glossary.md file was written to the expected location.
        glossary_file = tmp_path / "summaries" / ".glossaries" / "Test Chapter.glossary.md"
        assert glossary_file.exists(), (
            f"glossary file not written at {glossary_file}; "
            f"actual files in .glossaries/: {list((tmp_path / 'summaries' / '.glossaries').glob('*'))}"
        )
        # The persist log line was emitted.
        persist_logs = [m for m, _ in logs if "V0.5.6 source glossary" in m]
        assert len(persist_logs) == 1, f"expected 1 persist log, got {persist_logs}"
        # The xref log lines were emitted for the LLM-only + regex-only names.
        llm_only_logs = [m for m, _ in logs if "Meissner" in m and "LLM catch" in m]
        assert len(llm_only_logs) == 1, f"expected 1 llm_only log for Meissner, got {llm_only_logs}"
        regex_only_logs = [m for m, _ in logs if "Shapiro" in m and "recall gap" in m]
        assert len(regex_only_logs) == 1, (
            f"expected 1 regex_only log for Shapiro, got {regex_only_logs}"
        )
        # The summary xref log line reports the bucket counts.
        summary_logs = [m for m, _ in logs if "glossary xref" in m]
        assert len(summary_logs) == 1
        assert "confirmed=3" in summary_logs[0]
        assert "llm_only=1" in summary_logs[0]
        assert "regex_only=1" in summary_logs[0]

    def test_extract_persist_and_cross_reference_fail_open_on_empty(self, tmp_path):
        """When the LLM emits no <name_glossary> block, the helper returns
        an empty glossary + DOES NOT write a file (no point persisting
        nothing)."""
        logs: list[tuple[str, str]] = []

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        g = extract_persist_and_cross_reference_glossary(
            "<thorough_summary>just the summary</thorough_summary>",
            heading="Empty Chapter",
            output_dir=tmp_path,
            run_id="",
            app_version="",
            regex_authors={"Bak"},
            log=log,
        )
        assert g == {"names": [], "dates": [], "terms": []}
        # No .glossary.md file written.
        assert not (tmp_path / "summaries" / ".glossaries").exists()


# ═══════════════════════════════════════════════════════════════════════════
# 6) The master-summary prompt CARRIED the <name_glossary> instruction at
#    V0.5.6 (fused into the master-summary call). V0.5.7 REVERTS this — the
#    <name_glossary> block is now extracted via a SEPARATE LLM call (the
#    fused approach overwhelmed the model + caused 3 empty returns).
#    The V057-SEPARATE-CALL subagent's test_v057_separate_call.py covers
#    the new contract (the 3 master-summary prompts do NOT contain
#    <name_glossary>; the new prompts/summarisation/glossary_extraction.md
#    prompt carries it instead).
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 7) SummaryResult carries the source_glossary field (coordination pin)
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryResultSourceGlossaryField:
    """The ``source_glossary`` field on SummaryResult (coordination with the
    V056-VERIFICATION-LAYER subagent — they read this field as the coverage
    ground truth)."""

    def test_source_glossary_field_default_empty_dict(self):
        from core.models.models import SummaryResult

        sr = SummaryResult(
            chapter_heading="x",
            executive_summary="e",
            thorough_summary="t",
        )
        # Default = empty dict (legacy / fail-open — the verification LAYER
        # falls back to the regex extract_citations when no glossary).
        assert sr.source_glossary == {}

    def test_source_glossary_field_can_be_set(self):
        from core.models.models import SummaryResult

        g = parse_name_glossary(_WELL_FORMED_GLOSSARY_RESPONSE)
        sr = SummaryResult(
            chapter_heading="x",
            executive_summary="e",
            thorough_summary="t",
            source_glossary=g,
        )
        assert sr.source_glossary is g
        assert len(sr.source_glossary["names"]) == 3


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
