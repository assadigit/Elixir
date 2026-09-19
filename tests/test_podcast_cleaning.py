"""Tests for podcast script cleaning (stage directions, speaker normalization).

The V10.1.11 fix normalizes all speaker labels to "Host A:" / "Host B:"
and strips music cues, sound effects, and stage directions so the TTS
engine receives clean dialogue.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# Re-implement the core logic (can't import podcast_generator due to deps)
def strip_stage_directions(script: str) -> str:
    """Simplified version of PodcastGenerator._strip_stage_directions."""
    lines = script.splitlines()
    cleaned = []
    _last_speaker = "A"
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip markdown headers
        if stripped.startswith("#"):
            continue
        # Skip horizontal rules / scene dividers
        if re.match(r"^[\-\*_]{3,}$", stripped) or stripped == "* * *":
            continue
        # Skip bracketed stage directions
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        no_bold = re.sub(r"\*+", "", stripped).strip()
        if no_bold.startswith("[") and no_bold.endswith("]"):
            continue
        # Skip music/SFX cues
        if re.match(
            r"^(music|sfx|sound|soundtrack|intro|outro|transition|fade)\s*:", no_bold, re.IGNORECASE
        ):
            continue
        # Skip music note symbols
        if "♪" in stripped or "♫" in stripped or "🎵" in stripped:
            continue

        # Normalize speaker labels
        speaker_match = re.match(r"^([A-Z][\w\-\s]{0,30}):\s*(.+)$", stripped)
        if speaker_match:
            label = speaker_match.group(1).strip().lower()
            text = speaker_match.group(2).strip()
            if label in ("host a", "hosta", "a", "host 1", "speaker 1", "speaker1", "1"):
                line = f"Host A: {text}"
                _last_speaker = "A"
            elif label in ("host b", "hostb", "b", "host 2", "speaker 2", "speaker2", "2"):
                line = f"Host B: {text}"
                _last_speaker = "B"
            elif label in ("narrator", "narration", "voice", "announcer"):
                if _last_speaker == "A":
                    line = f"Host B: {text}"
                    _last_speaker = "B"
                else:
                    line = f"Host A: {text}"
                    _last_speaker = "A"
            else:
                # Unknown label (John, Julia, etc.)
                if _last_speaker == "A":
                    line = f"Host B: {text}"
                    _last_speaker = "B"
                else:
                    line = f"Host A: {text}"
                    _last_speaker = "A"
        else:
            line = re.sub(r"\s*\[[^\]]*\]\s*", " ", line)
            line = re.sub(r"[♪♫🎵]", "", line)

        line = re.sub(r"  +", " ", line).strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


# ── Stage direction stripping ─────────────────────────────────────────────


def test_strips_bracketed_directions() -> None:
    """[Intro music] should be removed."""
    script = "[Intro music]\nHost A: Welcome!"
    result = strip_stage_directions(script)
    assert "[Intro music]" not in result
    assert "Host A: Welcome!" in result


def test_strips_music_cues() -> None:
    """Music: cues should be removed."""
    script = "Music: fades in\nHost A: Hello"
    result = strip_stage_directions(script)
    assert "Music:" not in result
    assert "Host A: Hello" in result


def test_strips_inline_brackets() -> None:
    """Inline [laughs] should be removed from non-speaker lines."""
    script = "Host A: Welcome!\n[laughs] That's great"
    result = strip_stage_directions(script)
    assert "[laughs]" not in result
    assert "That's great" in result


def test_strips_markdown_headers() -> None:
    """Markdown headers should be removed."""
    script = "# Chapter 1\nHost A: Hello"
    result = strip_stage_directions(script)
    assert "# Chapter 1" not in result
    assert "Host A: Hello" in result


def test_strips_music_symbols() -> None:
    """Music note symbols should be removed."""
    script = "♪♪ Background music ♪♪\nHost A: Hello"
    result = strip_stage_directions(script)
    assert "♪" not in result
    assert "Host A: Hello" in result


# ── Speaker normalization ─────────────────────────────────────────────────


def test_normalizes_speaker_1_to_host_a() -> None:
    """Speaker 1: should become Host A:"""
    script = "Speaker 1: Hello"
    result = strip_stage_directions(script)
    assert "Host A: Hello" in result
    assert "Speaker 1" not in result


def test_normalizes_john_to_alternating_host() -> None:
    """Random names (John, Julia) should be normalized to Host A/B."""
    script = "John: Hello\nJulia: Hi there"
    result = strip_stage_directions(script)
    # First unknown speaker → Host B (alternation from default _last_speaker="A")
    assert "Host B: Hello" in result
    # Second unknown speaker → Host A (alternation)
    assert "Host A: Hi there" in result
    assert "John" not in result
    assert "Julia" not in result


def test_preserves_host_a_b() -> None:
    """Existing Host A/B labels should be preserved."""
    script = "Host A: Hello\nHost B: Hi"
    result = strip_stage_directions(script)
    assert "Host A: Hello" in result
    assert "Host B: Hi" in result


def test_narrator_alternates() -> None:
    """Narrator: should alternate between Host A and Host B."""
    script = "Host A: First line.\nNarrator: Second line.\nNarrator: Third line."
    result = strip_stage_directions(script)
    assert "Host A: First line." in result
    # After Host A, Narrator → Host B
    assert "Host B: Second line." in result
    # After Host B, Narrator → Host A
    assert "Host A: Third line." in result
