"""V18.20.4.11 (P1 / T-a2) — response_parser logging (dead logger revived).

The audit (SWOT T-a2, sweep 2-a) found ``core/summarisation/response_parser.py``
defined a module logger at line 27 but NEVER used it — every fallback in the
parse ladder was silent:

    JSON (:~228-324) → universal tag/text (:~326-420) → sentence
    fallback (:~533-545); strip_thinking (:96-127).

V18.20.4.11 adds logging WITHOUT changing any signature, return value, or
parse behavior:

  - routine transitions (non-JSON response → universal; JSON decode failure
    → universal; which rung produced the bullets) → DEBUG one-liners with
    counts/sizes, content only at DEBUG (capped at 80 chars)
  - exceptional/degenerate outcomes → WARNING with counts only:
      * non-empty input parsed to ZERO content
      * sentence fallback had to salvage (last rung of the ladder)
      * sentence fallback zero-yield
      * strip_thinking removed >50% of text (CoT leak past /no_think)

Run: pytest tests/test_v1820411_p1_parser_logging.py -v
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.response_parser import (
    extract_sentences_as_bullets,
    parse_response,
    strip_thinking,
)

_LOGGER = "core.summarisation.response_parser"


def _records(caplog, level=None):
    """Response-parser records captured by caplog, optionally level-filtered."""
    out = [r for r in caplog.records if r.name == _LOGGER]
    if level is not None:
        out = [r for r in out if r.levelno == level]
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Routine transitions — tagged (non-JSON) response → DEBUG fallback trace
# ═══════════════════════════════════════════════════════════════════════════

class TestTaggedResponseTrace:
    TAGGED = (
        "<executive_summary>The chapter links anxiety to defence mechanisms.</executive_summary>\n"
        "<bullet_points>\n"
        "- First bullet point that is definitely long enough\n"
        "- Second bullet point that is also long enough\n"
        "</bullet_points>\n"
        "<thorough_summary>A thorough discussion of the two bullets above.</thorough_summary>"
    )

    def test_fallback_trace_records_present(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            result = parse_response(self.TAGGED)
        # behavior unchanged
        assert len(result["bullet_points"]) == 2
        assert "anxiety" in result["executive_summary"]
        assert "thorough discussion" in result["thorough_summary"]
        # fallback trace: non-JSON → universal (routine → DEBUG)
        debug_msgs = [r.message for r in _records(caplog, logging.DEBUG)]
        assert any("non-JSON response" in m and "universal parser" in m for m in debug_msgs), debug_msgs
        # ...and the universal parser's outcome line naming the winning rung
        assert any("universal parser" in m and "2 bullets" in m for m in debug_msgs), debug_msgs

    def test_no_warning_for_clean_tagged_response(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            parse_response(self.TAGGED)
        assert not _records(caplog, logging.WARNING), "clean parse must not WARN"


# ═══════════════════════════════════════════════════════════════════════════
# JSON paths
# ═══════════════════════════════════════════════════════════════════════════

class TestJsonPaths:
    def test_json_decode_failure_traced_at_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            result = parse_response("{bad json}", academic_rigor=True)
        # salvaged by the universal parser → thorough carries the text
        assert isinstance(result, dict)
        debug_msgs = [r.message for r in _records(caplog, logging.DEBUG)]
        assert any("JSON decode failed" in m and "universal parser" in m for m in debug_msgs), debug_msgs

    def test_json_success_traced_at_debug(self, caplog):
        raw = (
            '{"executive_summary": ["Core claim one"], '
            '"bullet_points": ["B1 long enough", "B2 long enough"], '
            '"thorough_summary": ["Deep dive text"]}'
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            result = parse_response(raw, academic_rigor=True)
        assert len(result["bullet_points"]) == 2
        debug_msgs = [r.message for r in _records(caplog, logging.DEBUG)]
        assert any("JSON path OK" in m and "2 bullets" in m for m in debug_msgs), debug_msgs


# ═══════════════════════════════════════════════════════════════════════════
# Degenerate outcomes — WARNING records
# ═══════════════════════════════════════════════════════════════════════════

class TestDegenerateWarnings:
    def test_zero_content_parse_warns(self, caplog):
        """Non-empty input, ALL fields empty → WARNING (was completely
        silent). '<response></response>' strips to nothing in the leftover
        thorough path."""
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            result = parse_response("<response>\n\n</response>")
        assert result["executive_summary"] == ""
        assert result["bullet_points"] == []
        assert result["thorough_summary"] == ""
        warnings = [r.message for r in _records(caplog, logging.WARNING)]
        assert any("ZERO content" in w for w in warnings), warnings
        # counts only — no response content at WARNING
        assert not any("<response>" in w for w in warnings)

    def test_sentence_fallback_salvage_warns(self, caplog):
        """The sentence fallback is the LAST rung (bullet_pipeline reaches it
        only after every structured parser found nothing) → WARNING."""
        text = (
            "This is a long sentence that certainly exceeds twenty characters. "
            "Another sentence here also exceeds the minimum threshold easily."
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            bullets = extract_sentences_as_bullets(text)
        assert len(bullets) == 2  # behavior unchanged
        warnings = [r.message for r in _records(caplog, logging.WARNING)]
        assert any("sentence fallback" in w and "salvaged 2 bullets" in w for w in warnings), warnings

    def test_sentence_fallback_zero_yield_warns(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            bullets = extract_sentences_as_bullets("short. tiny. no.")
        assert bullets == []
        warnings = [r.message for r in _records(caplog, logging.WARNING)]
        assert any("sentence fallback" in w and "0 bullets" in w for w in warnings), warnings


# ═══════════════════════════════════════════════════════════════════════════
# strip_thinking — pathological removal WARNING, no false alarms
# ═══════════════════════════════════════════════════════════════════════════

class TestStripThinkingLogging:
    def test_majority_removal_warns_with_counts(self, caplog):
        raw = (
            "<think lang=\"x\">" + ("reasoning " * 500) + "</think"
            ">\n<executive_summary>Short but real.</executive_summary>"
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            out = strip_thinking(raw)
        assert out == "<executive_summary>Short but real.</executive_summary>"
        warnings = [r.message for r in _records(caplog, logging.WARNING)]
        assert any("removed >50%" in w for w in warnings), warnings
        # counts in the message, not content — derive from the fixture so
        # the pin survives future fixture edits (author's hardcode was off by 9)
        assert any(f"{len(raw)} ->" in w for w in warnings), warnings

    def test_normal_text_no_warning(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            out = strip_thinking("<executive_summary>Nothing to remove here.</executive_summary>")
        assert "Nothing to remove" in out
        assert not _records(caplog, logging.WARNING)

    def test_whitespace_only_no_false_warning(self, caplog):
        """Whitespace-only input loses only the cosmetic final .strip() —
        that must NOT count as a >50% thinking removal."""
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            out = strip_thinking("   \n   ")
        assert out == ""
        assert not _records(caplog, logging.WARNING)

    def test_double_strip_warns_once(self, caplog):
        """primary_call strips the raw response before parse_response strips
        it again — the second pass must be a no-op (no duplicate WARNING)."""
        raw = (
            "<think lang=\"x\">" + ("reasoning " * 500) + "</think"
            ">\n<executive_summary>Short but real.</executive_summary>"
        )
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            once = strip_thinking(raw)
            strip_thinking(once)
        warnings = [r.message for r in _records(caplog, logging.WARNING)]
        assert len([w for w in warnings if "removed >50%" in w]) == 1, warnings


# ═══════════════════════════════════════════════════════════════════════════
# Behavior preservation — logging only, no parse changes
# ═══════════════════════════════════════════════════════════════════════════

class TestBehaviorUnchanged:
    def test_parse_response_shapes(self):
        r = parse_response(
            "<bullet_points>\n- One bullet that is long enough\n- Two bullet that is long enough\n</bullet_points>"
        )
        assert set(r) == {
            "executive_summary", "bullet_points", "thorough_summary",
            "key_distinctions", "theoretical_tensions",
        }
        assert len(r["bullet_points"]) == 2

    def test_plain_text_bullets(self):
        r = parse_response("Summary line.\n\n- First plain bullet is long enough\n- Second plain bullet is long enough")
        assert len(r["bullet_points"]) == 2

    def test_empty_and_none_safe(self):
        assert strip_thinking("") == ""
        assert extract_sentences_as_bullets("") == []
        assert extract_sentences_as_bullets("   ") == []
