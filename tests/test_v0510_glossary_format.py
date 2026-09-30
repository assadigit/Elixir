"""V0.5.10 (GLOSSARY-FORMAT) — change the glossary output format from XML
``<name_glossary>`` tags to plain markdown headers (the
Ternary-Bonsai-2-27B model can't reliably follow the XML-tag instruction
even with ``max=8192`` + ``strip_thinking`` + the explicit "start with
``<``" prompt).

The V0.5.9 audit found:
  - The 8192 fix worked (the glossary call now uses ``max=8192``, ran
    ~9 min).
  - BUT the glossary STILL didn't extract — the log shows
    ``ℹ️ V0.5.7: no <name_glossary> block parsed from the separate call``.
  - The root cause is the OUTPUT FORMAT: the model can't reliably
    follow the ``<name_glossary>...</name_glossary>`` XML-tag
    instruction, even with ``strip_thinking`` + the explicit "Start
    IMMEDIATELY with ``<name_glossary>``" prompt. The model likely
    outputs the glossary content as a plain markdown list (no XML
    wrapper) that the V0.5.9 parser doesn't recognize.

V0.5.10 fixes this by:
  1. REWRITING the ``prompts/summarisation/glossary_extraction.md`` prompt
     to ask for plain markdown headers (``## Source Glossary — Names`` /
     ``## Source Glossary — Dates`` / ``## Source Glossary — Terms``)
     instead of the XML wrapper. The "Start IMMEDIATELY" instruction is
     adapted to "Start IMMEDIATELY with ``## Source Glossary — Names``".
     A short few-shot example (Smith/Jones) is added.
  2. REWRITING ``parse_name_glossary`` in ``glossary_parser.py`` to
     cascade 3 tiers (all fail-open):
       - Tier 1: the OLD XML format (``<name_glossary>...</name_glossary>``)
         — kept for backward compatibility.
       - Tier 2: the NEW markdown-header format (``## Source Glossary —
         Names``) — the unified regex ALSO accepts the bare ``## Names``
         form (lenient fallback when the LLM omits the prefix).
       - Tier 3: the LENIENT bare-bullet fallback — scan for ANY line
         matching the ``- **Surname** (YYYY) — context`` shape (no
         headers needed).

This test module covers the V0510-GLOSSARY-FORMAT subagent's deliverables:
  - ``test_parse_markdown_header_format`` — a response with the new V0.5.10
    markdown headers (no XML wrapper) is parsed correctly.
  - ``test_parse_xml_format_backward_compat`` — a response with the OLD
    ``<name_glossary>...</name_glossary>`` XML wrapper is still parsed
    (backward compatibility — some runs may still produce it).
  - ``test_parse_lenient_header_fallback`` — a response with just ``## Names``
    /``## Dates``/``## Terms`` headers (no "Source Glossary —" prefix) is
    parsed via the lenient fallback (Tier 2's bare-form acceptance).
  - ``test_parse_lenient_bare_bullets_fallback`` — a response with just
    bullets (no headers at all) is parsed via Tier 3.
  - ``test_parse_fail_open_on_no_glossary`` — a response with no glossary
    at all → empty dict (fail-open).
  - ``test_glossary_prompt_uses_markdown_headers`` — the prompt contains
    ``## Source Glossary — Names`` (not the ``<name_glossary>`` XML
    wrapper instruction).
  - ``test_glossary_prompt_has_few_shot_example`` — the prompt contains
    the generic Smith/Jones few-shot example.

Content-agnostic (Rule 1 ✓): the prompt instruction is generic ("ALL
cited authors"); the few-shot example uses generic test-fixture names
(Smith / Jones, not book content); the parser uses generic regex
(``<name_glossary>``, ``## Source Glossary — Names``, ``## Names``,
``- **Surname** (YYYY) — context``). NO hardcoded book/author/chapter
names anywhere. The author names + dates + terms in these tests are
TEST FIXTURES (Smith / Jones / Alpha / Beta — Rule 1 exempt).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v056_glossary.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
from core.summarisation.glossary_parser import parse_name_glossary  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures (synthetic author names — Rule 1 exempt).
# The author names + dates + terms here are GENERIC TEST FIXTURES (Smith /
# Jones / Alpha / Beta / X framework) — they do NOT appear in runtime code
# or in any book's content. They are deliberately distinct from the V0.5.6
# glossary tests' fixtures (Bak / Freud / Klein) so a copy-paste leak across
# test files would be caught by the Rule 1 deny-list sweep.
# ─────────────────────────────────────────────────────────────────────────────

# V0.5.10 NEW format — plain markdown headers, NO XML wrapper.
# (This is what the V0.5.10 prompt asks the LLM to output.)
_MARKDOWN_HEADER_RESPONSE = """## Source Glossary — Names
- **Smith** (1984) — contributed the X framework
- **Jones** (1990a, 1990b) — extended the X framework
## Source Glossary — Dates
- **1980-1990** — the X framework's development decade
## Source Glossary — Terms
- **X framework** — a theoretical model for understanding Y
"""

# OLD V0.5.6-V0.5.9 format — the XML wrapper (kept for backward compat).
_XML_WRAPPER_RESPONSE = """<name_glossary>
## Names
- **Alpha** (1970) — introduced the Y concept
- **Beta** (1975a, 1980b) — refined the Y concept
## Dates
- **1960-1970** — the Y concept's foundational decade
## Terms
- **Y concept** — a theoretical model for understanding Z
</name_glossary>
"""

# LENIENT format — just the bare ``## Names`` (no "Source Glossary —"
# prefix). The LLM emitted the V0.5.6-era header shape but WITHOUT the
# XML wrapper (the V0.5.9 audit's failure mode — the model dropped the
# XML wrapper but kept the old header shape).
_LENIENT_HEADER_RESPONSE = """## Names
- **Alpha** (1970) — introduced the Y concept
- **Beta** (1975a, 1980b) — refined the Y concept
## Dates
- **1960-1970** — the Y concept's foundational decade
## Terms
- **Y concept** — a theoretical model for understanding Z
"""

# LENIENT bare-bullet format — no headers at all, just bullets. The
# Tier 3 fallback catches this (all bullets → names bucket).
_LENIENT_BARE_BULLET_RESPONSE = """- **Smith** (1984) — contributed the X framework
- **Jones** (1990a, 1990b) — extended the X framework
- **Alpha** (1970) — introduced the Y concept
"""

# A response with NO glossary at all (just some prose / a master summary).
# Used for the fail-open test.
_NO_GLOSSARY_RESPONSE = """<thorough_summary>
The chapter covers the X framework and the Y concept from multiple perspectives.
</thorough_summary>
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1) Tier 2: NEW markdown-header format (V0.5.10) — parsed correctly.
# ═══════════════════════════════════════════════════════════════════════════


class TestParseMarkdownHeaderFormat:
    """A response with the new V0.5.10 ``## Source Glossary — Names``
    headers (NO XML wrapper) → parsed correctly (Tier 2)."""

    def test_parse_markdown_header_format(self):
        g = parse_name_glossary(_MARKDOWN_HEADER_RESPONSE)
        # The dict has the 3 expected keys.
        assert set(g.keys()) == {"names", "dates", "terms"}, (
            f"expected 3 keys (names/dates/terms), got {set(g.keys())}"
        )
        # Names: 2 entries — Smith + Jones.
        assert len(g["names"]) == 2, f"expected 2 names, got {len(g['names'])}"
        smith = g["names"][0]
        assert smith["name"] == "Smith"
        assert smith["year"] == "1984"
        assert "X framework" in smith["context"]
        jones = g["names"][1]
        assert jones["name"] == "Jones"
        # Multi-year form is preserved (1990a, 1990b).
        assert "1990a" in jones["year"] and "1990b" in jones["year"]
        # Dates: 1 entry — the 1980-1990 range.
        assert len(g["dates"]) == 1, f"expected 1 date, got {len(g['dates'])}"
        assert g["dates"][0]["date"] == "1980-1990"
        assert "development decade" in g["dates"][0]["context"]
        # Terms: 1 entry — the X framework.
        assert len(g["terms"]) == 1, f"expected 1 term, got {len(g['terms'])}"
        assert g["terms"][0]["term"] == "X framework"
        assert "theoretical model" in g["terms"][0]["context"]


# ═══════════════════════════════════════════════════════════════════════════
# 2) Tier 1: XML format backward compat — still parsed.
# ═══════════════════════════════════════════════════════════════════════════


class TestParseXmlFormatBackwardCompat:
    """A response with the OLD ``<name_glossary>...</name_glossary>`` XML
    wrapper → still parsed (Tier 1 backward compatibility — some runs may
    still produce it even though the V0.5.10 prompt no longer asks for it)."""

    def test_parse_xml_format_backward_compat(self):
        g = parse_name_glossary(_XML_WRAPPER_RESPONSE)
        # The dict has the 3 expected keys.
        assert set(g.keys()) == {"names", "dates", "terms"}
        # Names: 2 entries — Alpha + Beta (from the XML-wrapped fixture).
        assert len(g["names"]) == 2, f"expected 2 names, got {len(g['names'])}"
        alpha = g["names"][0]
        assert alpha["name"] == "Alpha"
        assert alpha["year"] == "1970"
        assert "Y concept" in alpha["context"]
        beta = g["names"][1]
        assert beta["name"] == "Beta"
        # Multi-year form is preserved (1975a, 1980b).
        assert "1975a" in beta["year"] and "1980b" in beta["year"]
        # Dates: 1 entry — the 1960-1970 range.
        assert len(g["dates"]) == 1
        assert g["dates"][0]["date"] == "1960-1970"
        # Terms: 1 entry — the Y concept.
        assert len(g["terms"]) == 1
        assert g["terms"][0]["term"] == "Y concept"


# ═══════════════════════════════════════════════════════════════════════════
# 3) Tier 2 (lenient sub-path): bare ## Names headers (no prefix) — parsed.
# ═══════════════════════════════════════════════════════════════════════════


class TestParseLenientHeaderFallback:
    """A response with just the bare ``## Names`` / ``## Dates`` / ``## Terms``
    headers (NO "Source Glossary —" prefix) → parsed via the lenient
    sub-path of Tier 2 (the unified regex accepts both the prefixed and
    the bare forms). This is the V0.5.9 audit's failure mode — the LLM
    dropped the XML wrapper but kept the V0.5.6-era header shape."""

    def test_parse_lenient_header_fallback(self):
        g = parse_name_glossary(_LENIENT_HEADER_RESPONSE)
        # The dict has the 3 expected keys.
        assert set(g.keys()) == {"names", "dates", "terms"}
        # Names: 2 entries — Alpha + Beta (same as the XML-wrapped fixture
        # but WITHOUT the XML wrapper).
        assert len(g["names"]) == 2, (
            f"expected 2 names (lenient header fallback), got {len(g['names'])}"
        )
        alpha = g["names"][0]
        assert alpha["name"] == "Alpha"
        assert alpha["year"] == "1970"
        beta = g["names"][1]
        assert beta["name"] == "Beta"
        assert "1975a" in beta["year"]
        # Dates: 1 entry.
        assert len(g["dates"]) == 1
        assert g["dates"][0]["date"] == "1960-1970"
        # Terms: 1 entry.
        assert len(g["terms"]) == 1
        assert g["terms"][0]["term"] == "Y concept"


# ═══════════════════════════════════════════════════════════════════════════
# 4) Tier 3: LENIENT bare-bullet fallback — bullets with no headers at all.
# ═══════════════════════════════════════════════════════════════════════════


class TestParseLenientBareBulletsFallback:
    """A response with NO headers at all — just bare bullets matching the
    ``- **Surname** (YYYY) — context`` shape → parsed via Tier 3 (the
    LENIENT bare-bullet scan; all matches go into the ``names`` bucket)."""

    def test_parse_lenient_bare_bullets_fallback(self):
        g = parse_name_glossary(_LENIENT_BARE_BULLET_RESPONSE)
        # The dict has the 3 expected keys.
        assert set(g.keys()) == {"names", "dates", "terms"}
        # Names: all 3 bullets were caught (Smith, Jones, Alpha) — even
        # though there were NO section headers. They all go into ``names``
        # because the Tier 3 fallback can't distinguish dates/terms from
        # names without a header (better to catch them as names than to
        # lose them entirely).
        assert len(g["names"]) == 3, (
            f"expected 3 names (lenient bare-bullet fallback), got {len(g['names'])}"
        )
        names = [n["name"] for n in g["names"]]
        assert "Smith" in names
        assert "Jones" in names
        assert "Alpha" in names
        # Dates and Terms are empty (no headers → can't attribute bullets
        # to those buckets).
        assert g["dates"] == []
        assert g["terms"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 5) Fail-open on no glossary at all.
# ═══════════════════════════════════════════════════════════════════════════


class TestParseFailOpenOnNoGlossary:
    """A response with NO glossary at all (no XML wrapper, no markdown
    headers, no bullets matching the name-bullet shape) → returns the
    empty 3-key dict (fail-open)."""

    def test_parse_fail_open_on_no_glossary(self):
        g = parse_name_glossary(_NO_GLOSSARY_RESPONSE)
        assert g == {"names": [], "dates": [], "terms": []}, (
            "a response with no glossary at all must fail-open with the empty 3-key dict (no crash)"
        )

    def test_parse_fail_open_on_none_input(self):
        g = parse_name_glossary(None)
        assert g == {"names": [], "dates": [], "terms": []}

    def test_parse_fail_open_on_empty_input(self):
        g = parse_name_glossary("")
        assert g == {"names": [], "dates": [], "terms": []}

    def test_parse_fail_open_on_whitespace_only(self):
        g = parse_name_glossary("   \n   \t   ")
        assert g == {"names": [], "dates": [], "terms": []}


# ═══════════════════════════════════════════════════════════════════════════
# 6) The V0.5.10 prompt — uses markdown headers (NOT the <name_glossary> XML wrapper).
# ═══════════════════════════════════════════════════════════════════════════


class TestGlossaryPromptUsesMarkdownHeaders:
    """V0.5.10: the ``prompts/summarisation/glossary_extraction.md`` prompt
    uses the NEW markdown-header format (``## Source Glossary — Names``)
    as the output instruction — NOT the ``<name_glossary>`` XML wrapper
    that V0.5.6-V0.5.9 used (the model couldn't follow it)."""

    REL = "prompts/summarisation/glossary_extraction.md"

    def test_glossary_prompt_uses_markdown_headers(self):
        prompt_path = Path(self.REL)
        assert prompt_path.exists(), f"missing prompt file: {self.REL}"
        text = prompt_path.read_text(encoding="utf-8")
        # The 3 NEW V0.5.10 markdown headers are present (the LLM is told
        # to output these exact headers).
        assert "## Source Glossary — Names" in text, (
            f"{self.REL}: V0.5.10 must use the NEW markdown-header format "
            "(## Source Glossary — Names) — NOT the <name_glossary> XML "
            "wrapper (the model can't follow the XML format)"
        )
        assert "## Source Glossary — Dates" in text, (
            f"{self.REL}: V0.5.10 must use the '## Source Glossary — Dates' header"
        )
        assert "## Source Glossary — Terms" in text, (
            f"{self.REL}: V0.5.10 must use the '## Source Glossary — Terms' header"
        )
        # The "Start IMMEDIATELY with ## Source Glossary — Names"
        # instruction is present (the V0.5.10 adapted "Start IMMEDIATELY"
        # wording — tells the LLM to start with `#`, not `<`).
        assert "## Source Glossary — Names" in text
        assert "MUST be `#`" in text or "must be `#`" in text.lower(), (
            f"{self.REL}: V0.5.10 must instruct the LLM that the FIRST "
            "character of the response MUST be `#` (the start of the "
            "markdown header — NOT `<` as in V0.5.6-V0.5.9)"
        )
        # The OLD ``<name_glossary>`` OUTPUT instruction is GONE — the
        # prompt must NOT tell the LLM to OUTPUT the XML wrapper. (The
        # prompt MAY mention `<name_glossary>` in a "Do NOT use" instruction
        # — that's the V0.5.10 backward-guidance — but it must NOT instruct
        # the LLM to OUTPUT it as the wrapper.)
        # The cleanest check: the prompt must NOT contain the
        # "</name_glossary>" closer (only the "Do NOT use `<name_glossary>`
        # tags" instruction is allowed — that doesn't need the closer).
        assert "</name_glossary>" not in text, (
            f"{self.REL}: V0.5.10 must NOT instruct the LLM to OUTPUT the "
            "</name_glossary> closer (the XML wrapper is removed — the "
            "V0.5.10 format uses plain markdown headers)"
        )
        # The "Output a `<name_glossary>` block" instruction is GONE.
        # (The V0.5.10 prompt may mention `<name_glossary>` in a
        # "Do NOT use" instruction — that's a different statement.)
        low = text.lower()
        assert "output a `<name_glossary>`" not in low, (
            f"{self.REL}: V0.5.10 must NOT contain the V0.5.6-V0.5.9 "
            "'Output a <name_glossary> block' instruction (the XML "
            "wrapper is removed)"
        )
        assert "output a <name_glossary>" not in low, (
            f"{self.REL}: V0.5.10 must NOT contain the 'Output a "
            "<name_glossary>' instruction (the XML wrapper is removed)"
        )

    def test_glossary_prompt_keeps_generic_instruction(self):
        """Rule 1 ✓ — the prompt instruction stays generic ("ALL cited
        authors"); the V0.5.10 format change is structural (XML →
        markdown headers), not a content-specific change."""
        text = Path(self.REL).read_text(encoding="utf-8")
        low = text.lower()
        assert "all cited authors" in low, (
            f"{self.REL}: V0.5.10 must keep the generic 'ALL cited "
            "authors' phrasing (content-agnostic — lets the LLM pull the "
            "roster from the runtime source, NOT hardcoded names)"
        )
        # The {source_text} placeholder is still present (the pipeline
        # substitutes the runtime source).
        assert "{source_text}" in text, (
            f"{self.REL}: V0.5.10 must contain the {{source_text}} "
            "placeholder (the pipeline substitutes the runtime source text)"
        )

    def test_glossary_prompt_is_content_agnostic(self):
        """Rule 1 guard: the V0.5.10 prompt must NOT hardcode any
        book-specific author names, dates, or terms — the LLM pulls the
        roster from the runtime source. The few-shot example uses GENERIC
        test-fixture names (Smith / Jones), NOT book content."""
        # Forbidden: the 5 author names the V0.5.5 audit found missing
        # from the test chapter (they're book content, NOT generic).
        forbidden_names = ["jack", "morey", "ndtei", "rettersol", "bak"]
        # Forbidden: book-specific terms from the paranoid chapter.
        forbidden_terms = [
            "paranoid-schizoid position",
            "broken structures",
            "false self",
            "ego-syntonic",
        ]
        text = Path(self.REL).read_text(encoding="utf-8").lower()
        for name in forbidden_names:
            assert name not in text, (
                f"{self.REL}: V0.5.10 glossary prompt hardcodes book "
                f"author '{name}' — Rule 1 violation (must be generic "
                "'ALL cited authors' + the few-shot example uses "
                "Smith/Jones, NOT book content)"
            )
        for term in forbidden_terms:
            assert term not in text, (
                f"{self.REL}: V0.5.10 glossary prompt hardcodes book "
                f"term '{term}' — Rule 1 violation"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 7) The V0.5.10 prompt — has the generic Smith/Jones few-shot example.
# ═══════════════════════════════════════════════════════════════════════════


class TestGlossaryPromptHasFewShotExample:
    """V0.5.10: the prompt has a SHORT few-shot example (2-3 entries) at
    the end so the model understands the format. The example uses GENERIC
    test-fixture names (Smith / Jones, NOT book content) — Rule 1 ✓."""

    REL = "prompts/summarisation/glossary_extraction.md"

    def test_glossary_prompt_has_few_shot_example(self):
        text = Path(self.REL).read_text(encoding="utf-8")
        # The few-shot example uses the generic Smith/Jones names (NOT
        # book content — Rule 1 ✓).
        assert "Smith" in text, (
            f"{self.REL}: V0.5.10 must have a few-shot example with the "
            "generic Smith name (illustrates the bullet format — NOT book "
            "content)"
        )
        assert "Jones" in text, (
            f"{self.REL}: V0.5.10 must have a few-shot example with the "
            "generic Jones name (illustrates the multi-year form — "
            "(1990a, 1990b))"
        )
        # The few-shot example demonstrates the multi-year form
        # (1990a, 1990b) — this is the bullet SHAPE the parser expects.
        assert "1990a" in text and "1990b" in text, (
            f"{self.REL}: V0.5.10 few-shot example must show the "
            "multi-year form '(1990a, 1990b)' (illustrates the parser's "
            "year-group regex)"
        )
        # The few-shot example includes the 3 section headers (so the
        # model sees the FULL expected output shape).
        assert "## Source Glossary — Names" in text
        assert "## Source Glossary — Dates" in text
        assert "## Source Glossary — Terms" in text
        # The few-shot example includes a date range + a term definition.
        assert "1980-1990" in text, (
            f"{self.REL}: V0.5.10 few-shot example must show a date-range "
            "entry (illustrates the dates-bullet shape)"
        )
        assert "X framework" in text, (
            f"{self.REL}: V0.5.10 few-shot example must show a term "
            "definition (illustrates the terms-bullet shape)"
        )
        # The few-shot example is clearly marked as GENERIC (not book
        # content) — the prompt tells the LLM to pull from the source,
        # not to copy the example.
        low = text.lower()
        assert "generic" in low or "example" in low, (
            f"{self.REL}: V0.5.10 must clearly mark the few-shot example "
            "as generic/illustrative (tells the LLM to pull from the "
            "source, not to copy the example)"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
