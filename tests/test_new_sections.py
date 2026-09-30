"""V13.38.0: Regression tests for the new additive summary sections.

Tests verify:
1. parse_response extracts key_distinctions from XML format
2. parse_response extracts theoretical_tensions from XML format
3. parse_response extracts key_distinctions from JSON format (academic rigor)
4. parse_response extracts theoretical_tensions from JSON format (academic rigor)
5. Old sections (exec, bullets, thorough) still work — additive, not replacing
6. Empty new sections don't break parsing (backward compat with old model output)
"""

from __future__ import annotations

import pytest

from core.summarisation.response_parser import parse_response

# ═══════════════════════════════════════════════════════════════════════════
# XML format tests
# ═══════════════════════════════════════════════════════════════════════════


class TestParseNewSectionsXML:
    """V13.38.0: Verify parse_response extracts the new XML sections."""

    def test_extracts_key_distinctions_from_xml(self):
        """parse_response should extract <key_distinctions> from XML format."""
        raw = """<executive_summary>
This chapter discusses identity formation.
</executive_summary>

<bullet_points>
- Identity develops through multiple stages.
- Erikson defined ego identity.
</bullet_points>

<thorough_summary>
A thorough analysis of identity formation across psychoanalytic traditions.
</thorough_summary>

<key_distinctions>
- Ego identity vs. existential identity: the former is inner sameness, the latter is social continuity.
- Adolescent crisis vs. identity diffusion: the former is a developmental phase, the latter is pathology.
</key_distinctions>

<theoretical_tensions>
- Debate over infantile vs. adolescent origins of identity.
- Tension between clinical and social conceptions of identity.
</theoretical_tensions>"""

        result = parse_response(raw, academic_rigor=False)

        assert "key_distinctions" in result
        assert "theoretical_tensions" in result
        assert "ego identity vs. existential identity" in result["key_distinctions"].lower()
        assert "adolescent crisis vs. identity diffusion" in result["key_distinctions"].lower()
        assert "infantile vs. adolescent" in result["theoretical_tensions"].lower()
        assert "clinical and social" in result["theoretical_tensions"].lower()

    def test_old_sections_still_extracted(self):
        """The new sections are ADDITIVE — old sections must still work."""
        raw = """<executive_summary>
Executive summary text.
</executive_summary>

<bullet_points>
- Bullet 1.
- Bullet 2.
</bullet_points>

<thorough_summary>
Thorough summary text.
</thorough_summary>

<key_distinctions>
- A vs. B: distinction matters.
</key_distinctions>

<theoretical_tensions>
- Debate about X.
</theoretical_tensions>"""

        result = parse_response(raw, academic_rigor=False)

        # Old sections must still be present and correct
        assert "executive_summary" in result
        assert "Executive summary text" in result["executive_summary"]
        assert "bullet_points" in result
        assert len(result["bullet_points"]) == 2
        assert "thorough_summary" in result
        assert "Thorough summary text" in result["thorough_summary"]

        # New sections also present
        assert "key_distinctions" in result
        assert "A vs. B" in result["key_distinctions"]
        assert "theoretical_tensions" in result
        assert "Debate about X" in result["theoretical_tensions"]

    def test_empty_new_sections_dont_break_parsing(self):
        """When the model doesn't output the new sections, parsing must still work."""
        raw = """<executive_summary>
Executive summary text.
</executive_summary>

<bullet_points>
- Bullet 1.
</bullet_points>

<thorough_summary>
Thorough summary text.
</thorough_summary>"""

        result = parse_response(raw, academic_rigor=False)

        # Old sections must work
        assert "executive_summary" in result
        assert "Executive summary text" in result["executive_summary"]
        assert len(result["bullet_points"]) == 1
        assert "thorough_summary" in result

        # New sections should be empty strings (not None, not missing)
        assert result.get("key_distinctions", "") == ""
        assert result.get("theoretical_tensions", "") == ""


# ═══════════════════════════════════════════════════════════════════════════
# JSON format tests (academic rigor)
# ═══════════════════════════════════════════════════════════════════════════


class TestParseNewSectionsJSON:
    """V13.38.0: Verify parse_response extracts the new sections from JSON."""

    def test_extracts_key_distinctions_from_json(self):
        """parse_response should extract key_distinctions from JSON (academic rigor)."""
        raw = """{
  "executive_summary": [
    {"claim": "Identity is a key psychoanalytic concept.", "supporting_text": "...", "source_reference": "p.1"}
  ],
  "bullet_points": [
    {"claim": "Erikson defined ego identity.", "supporting_text": "...", "source_reference": "p.2"}
  ],
  "thorough_summary": [
    {"claim": "The chapter traces identity from Freud to Kernberg.", "supporting_text": "...", "source_reference": "p.3"}
  ],
  "key_distinctions": [
    {"claim": "Ego identity vs. existential identity: inner sameness vs. social continuity.", "supporting_text": "...", "source_reference": "p.4"}
  ],
  "theoretical_tensions": [
    {"claim": "Debate over infantile vs. adolescent origins.", "supporting_text": "...", "source_reference": "p.5"}
  ]
}"""

        result = parse_response(raw, academic_rigor=True)

        assert "key_distinctions" in result
        assert "theoretical_tensions" in result
        assert "ego identity vs. existential identity" in result["key_distinctions"].lower()
        assert "infantile vs. adolescent" in result["theoretical_tensions"].lower()

    def test_json_without_new_sections_still_works(self):
        """JSON without the new keys should still parse (backward compat)."""
        raw = """{
  "executive_summary": [
    {"claim": "Summary claim.", "supporting_text": "...", "source_reference": "p.1"}
  ],
  "bullet_points": [
    {"claim": "Bullet claim.", "supporting_text": "...", "source_reference": "p.2"}
  ],
  "thorough_summary": [
    {"claim": "Thorough claim.", "supporting_text": "...", "source_reference": "p.3"}
  ]
}"""

        result = parse_response(raw, academic_rigor=True)

        # Old sections must work
        assert "executive_summary" in result
        assert "Summary claim" in result["executive_summary"]
        assert len(result["bullet_points"]) == 1
        assert "thorough_summary" in result

        # New sections should be empty strings
        assert result.get("key_distinctions", "") == ""
        assert result.get("theoretical_tensions", "") == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
