"""V0.6.30 — the JSON-metadata-leak-into-dialogue bug fix.

THE BUG (the operator's report)
------------------------------
The AI generated a podcast script where JSON metadata key-value pairs
appeared as separate lines in the dialogue text:

    [Host A] You know, "host": "A",
    [Host A] "text": "Imagine your liver is starting to shut down..."
    [Host A] "source_ref": "hook",
    [Host A] "segment_type": "intro"

The TTS model then literally read "host", "source_ref", "pause" as
speech instead of using them as instructions.

ROOT CAUSE
----------
The LLM output JSON key-value pairs on separate lines WITHOUT ``{...}``
wrappers. The parser's JSONL strategy skipped them (they don't start
with ``{``), and the plain-dialogue fallback captured the JSON fragments
as dialogue text.

THE FIX (W-o1, core/podcast/script_generator.py)
------------------------------------------------
NEW ``_clean_json_metadata_from_text(text)`` function:
  1. Extracts the VALUE from ``"text": "actual dialogue"`` → the real
     speech.
  2. Strips ``"host": "A"`` / ``"host": "B"`` → metadata (already
     captured separately).
  3. Strips ``"source_ref": "..."`` → metadata.
  4. Strips ``"segment_type": "..."`` → metadata.
  5. Cleans up leftover commas / whitespace / empty lines.

Called in ``_parse_plain_dialogue`` after extracting the line text,
before the JSON-object check. If the line was pure JSON metadata (no
dialogue left after cleanup), it's skipped entirely.

All tests are pure-Python (no PySide6 / no torch).
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── _clean_json_metadata_from_text unit tests ────────────────────────────────


def test_v0630_clean_extracts_text_value() -> None:
    """The "text": "value" pattern is replaced with just the value
    (the actual dialogue)."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text('"text": "Imagine your liver."')
    assert result == "Imagine your liver."


def test_v0630_clean_strips_host_metadata() -> None:
    """The "host": "A" pattern is stripped entirely."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text('"host": "A",')
    assert result == ""  # pure metadata → empty after cleanup


def test_v0630_clean_strips_source_ref_metadata() -> None:
    """The "source_ref": "hook" pattern is stripped entirely."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text('"source_ref": "hook",')
    assert result == ""


def test_v0630_clean_strips_segment_type_metadata() -> None:
    """The "segment_type": "intro" pattern is stripped entirely."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text('"segment_type": "intro"')
    assert result == ""


def test_v0630_clean_mixed_dialogue_plus_metadata() -> None:
    """When dialogue text is mixed with JSON metadata (e.g., the LLM
    prefixed real dialogue with a filler + then output JSON keys), the
    JSON is stripped and the dialogue is kept."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text(
        'You know, "host": "A",\n"text": "Imagine your liver.",\n'
        '"source_ref": "hook",\n"segment_type": "intro"'
    )
    assert "You know" in result
    assert "Imagine your liver." in result
    assert '"host"' not in result
    assert '"source_ref"' not in result
    assert '"segment_type"' not in result
    assert '"text"' not in result


def test_v0630_clean_preserves_non_json_text() -> None:
    """Non-JSON text (actual dialogue with no metadata) is preserved
    verbatim."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    text = "Welcome to the show. Today we talk about testing."
    result = _clean_json_metadata_from_text(text)
    assert result == text


def test_v0630_clean_preserves_vocal_cues() -> None:
    """Vocal cue markers like [pause 0.5s] are NOT stripped (they're
    handled separately by strip_vocal_cues in the audio generator)."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    text = "Welcome [pause 0.5s] to the show."
    result = _clean_json_metadata_from_text(text)
    assert "[pause 0.5s]" in result


def test_v0630_clean_empty_string() -> None:
    """Empty string input returns empty string."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    assert _clean_json_metadata_from_text("") == ""


def test_v0630_clean_handles_escaped_quotes_in_text_value() -> None:
    """The "text" value may contain escaped quotes (\") which are
    unescaped to real quotes in the output."""
    from core.podcast.script_generator import _clean_json_metadata_from_text

    result = _clean_json_metadata_from_text(r'"text": "She said \"hello\"."')
    assert 'She said "hello".' in result


# ── End-to-end: _parse_script_response with the buggy LLM output ────────────


def test_v0630_parse_strips_json_metadata_from_llm_output() -> None:
    """The full _parse_script_response pipeline strips JSON metadata
    that leaked into the LLM's dialogue-format output."""
    from core.podcast.script_generator import _parse_script_response

    # This is the exact pattern the operator reported: the LLM output
    # JSON key-value pairs on separate lines, mixed with dialogue.
    llm_output = (
        'A: You know, "host": "A",\n'
        '"text": "Imagine your liver is starting to shut down.",\n'
        '"source_ref": "hook",\n'
        '"segment_type": "intro"\n'
        'B: "host": "B",\n'
        '"text": "Wait, really? That sounds incredibly stressful.",\n'
        '"source_ref": "hook",\n'
        '"segment_type": "intro"'
    )
    lines = _parse_script_response(llm_output)
    assert len(lines) >= 2
    # NO JSON metadata should be in any line's text.
    for line in lines:
        assert '"host"' not in line.text, f"JSON metadata leaked: {line.text!r}"
        assert '"source_ref"' not in line.text, f"JSON metadata leaked: {line.text!r}"
        assert '"segment_type"' not in line.text, f"JSON metadata leaked: {line.text!r}"
        assert '"text"' not in line.text, f"JSON key leaked: {line.text!r}"


def test_v0630_parse_recovers_actual_dialogue() -> None:
    """The actual dialogue is recovered from the "text" field value."""
    from core.podcast.script_generator import _parse_script_response

    llm_output = (
        'A: "host": "A",\n'
        '"text": "Imagine your liver is starting to shut down.",\n'
        '"source_ref": "hook",\n'
        '"segment_type": "intro"'
    )
    lines = _parse_script_response(llm_output)
    assert len(lines) >= 1
    # The actual dialogue should be in the text.
    all_text = " ".join(line.text for line in lines)
    assert "Imagine your liver" in all_text


def test_v0630_parse_clean_dialogue_still_works() -> None:
    """Clean dialogue WITHOUT any JSON metadata is still parsed correctly
    (the fix doesn't break the normal case)."""
    from core.podcast.script_generator import _parse_script_response

    llm_output = (
        "A: Welcome to the show. Today we talk about testing.\n"
        "B: That's right. Testing is very important.\n"
        "A: Thanks for listening. See you next time."
    )
    lines = _parse_script_response(llm_output)
    assert len(lines) == 3
    assert "Welcome to the show" in lines[0].text
    assert "Testing is very important" in lines[1].text
    assert "Thanks for listening" in lines[2].text


def test_v0630_parse_json_array_still_works() -> None:
    """Clean JSON array format (the canonical LLM output) still parses
    correctly — the fix doesn't break the JSON path."""
    import json

    from core.podcast.script_generator import _parse_script_response

    llm_output = json.dumps(
        [
            {"host": "A", "text": "Hello world.", "source_ref": "intro", "segment_type": "intro"},
            {
                "host": "B",
                "text": "Goodbye world.",
                "source_ref": "outro",
                "segment_type": "conclusion",
            },
        ]
    )
    lines = _parse_script_response(llm_output)
    assert len(lines) == 2
    assert lines[0].text == "Hello world."
    assert lines[1].text == "Goodbye world."


def test_v0630_parse_jsonl_still_works() -> None:
    """JSONL format (one JSON object per line) still parses correctly."""
    from core.podcast.script_generator import _parse_script_response

    llm_output = (
        '{"host": "A", "text": "Hello world.", "source_ref": "intro", "segment_type": "intro"}\n'
        '{"host": "B", "text": "Goodbye world.", "source_ref": "outro", "segment_type": "conclusion"}'
    )
    lines = _parse_script_response(llm_output)
    assert len(lines) == 2
    assert lines[0].text == "Hello world."
    assert lines[1].text == "Goodbye world."


# ── The full operator's bug scenario ────────────────────────────────────────


def test_v0630_operator_bug_scenario_no_json_keys_in_output() -> None:
    """The EXACT scenario the operator reported: the LLM output a long
    script with JSON metadata on separate lines. After the fix, NO JSON
    keys should appear in any line's text (the TTS would read them
    literally without the fix)."""
    from core.podcast.script_generator import _parse_script_response

    # A representative fragment of the operator's paste — JSON metadata
    # mixed with dialogue, [Host A]/[Host B] prefixes.
    llm_output = """A: You know, "host": "A",
"text": "Imagine your liver is starting to shut down in just a few years, [pause 0.5s] and [breath] the only clue we have is that your relatives are all fighting with autoimmune disease. [sigh] [pause 1.0s]It's a medical mystery.",
"source_ref": "hook",
"segment_type": "intro"
B: "host": "B",
"text": "Wait, [pause 0.3s] really? [pause 0.7s]Just family history and no other obvious cause? That sounds incredibly stressful to figure out.", [pause 0.3s]
"source_ref": "hook",
"segment_type": "intro"
A: "host": "A",
"text": "Exactly. Today we're diving into the medical literature on autoimmune liver diseases.",
"source_ref": "intro",
"segment_type": "intro\""""

    lines = _parse_script_response(llm_output)

    # The critical assertion: NO JSON metadata keys in any line's text.
    json_keys = ('"host"', '"text"', '"source_ref"', '"segment_type"')
    for i, line in enumerate(lines):
        for key in json_keys:
            assert key not in line.text, (
                f"Line {i}: JSON key {key!r} leaked into text: {line.text!r}"
            )

    # The actual dialogue should be recovered.
    all_text = " ".join(line.text for line in lines)
    assert "Imagine your liver" in all_text
    assert "Wait" in all_text or "really" in all_text
    assert "Exactly" in all_text or "diving" in all_text

    # Vocal cues should be preserved (they're handled by strip_vocal_cues
    # in the audio generator, not by the parser).
    assert "[pause" in all_text or "[breath]" in all_text or "[sigh]" in all_text
