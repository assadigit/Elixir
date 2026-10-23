"""V0.6.55 (P6) — the transcribe.cpp CLI output-parser edge-case pins.

THE PROBLEM (the operator's redesign item + the V0.6.52 history): the
parser was rewritten once already (V0.6.52) to match "the REAL CLI
output format", but only ONE dialect. The known remaining edge cases
(each silently DROPS transcript content when it hits):

  1. ``-->`` arrows (whisper.cpp prints double-arrow timestamps; the
     V0.6.52 regex only matches a single ``->``).
  2. ``HH:MM:SS.mmm`` / ``MM:SS.mmm`` timestamps inside the brackets
     (the regex only matched bare seconds — a whole whisper.cpp-style
     transcript parsed to ZERO segments).
  3. Continuation lines: the CLI wraps a long ``text:`` value onto
     following lines; every line after the first was silently DROPPED
     (the loop only collects ``text:``-prefixed lines and timestamped
     segments).
  4. A transcript that has ONLY timestamped segments and no ``text:``
     line fell to the raw-stdout fallback — info lines and all —
     instead of simply joining the segment texts.
  5. ``detected language:`` (space variant) was not recognized.
  6. A UTF-8 BOM on the first line poisoned the first prefix match.
  7. Progress bars (``12%|███| 00:12<00:34``) without the ``it/s``
     marker were not skipped.

THE PINS: each edge case is a crafted CLI output fed to
``_parse_transcribe_cpp_output`` (a PURE function — no subprocess, no
files) asserting the extracted text/segments/language. Plus V0.6.52
regression pins: the REAL format (single ``->``, bare seconds, the
info-line set) still parses byte-identically.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.transcribe.transcribe_cpp_engine import (  # noqa: E402
    _parse_transcribe_cpp_output,
)

# ── the V0.6.52 REAL format (regression floor) ─────────────────────────────


_REAL_FORMAT = """audio: input.wav
samples: 48000
duration: 12.5
sample rate: 16000
model: whisper-large-v3-Q8_0
backend: Vulkan
name: Whisper
license: MIT
max audio: 0.00
run: 1
text: There are three main things to consider when transcription works.
detected-language: en
segments: 2
[   0.00 ->    4.06] There are three main things.
[   4.06 ->   12.50] to consider when transcription works.
realtime: 0.4x
system_info: n_threads = 4
"""


class TestV0655RealFormatRegression:
    def test_v0652_format_still_parses(self):
        out = _parse_transcribe_cpp_output(_REAL_FORMAT, "")
        assert out["text"] == ("There are three main things to consider when transcription works.")
        assert out["language"] == "en"
        assert out["backend"] == "Vulkan"
        assert len(out["segments"]) == 2
        assert out["segments"][0] == {
            "start": 0.0,
            "end": pytest.approx(4.06),
            "text": "There are three main things.",
        }

    def test_info_lines_are_still_skipped(self):
        out = _parse_transcribe_cpp_output(_REAL_FORMAT, "")
        for info in ("audio:", "model:", "realtime:", "system_info:"):
            assert info not in out["text"]


# ── Edge 1+2: whisper.cpp-style timestamps (--> and HH:MM:SS.mmm) ──────────


class TestV0655WhisperCppStyleTimestamps:
    def test_double_arrow_timestamps_parse(self):
        out = _parse_transcribe_cpp_output(
            "[00:00:00.000 --> 00:00:05.000] hello there\n"
            "[00:00:05.000 --> 00:00:09.500] general kenobi\n",
            "",
        )
        assert len(out["segments"]) == 2
        assert out["segments"][0]["start"] == 0.0
        assert out["segments"][0]["end"] == pytest.approx(5.0)
        assert out["segments"][0]["text"] == "hello there"
        assert out["segments"][1]["end"] == pytest.approx(9.5)

    def test_mm_ss_mmm_two_part_timestamps_parse(self):
        out = _parse_transcribe_cpp_output("[00:01.500 --> 00:04.250] a two part stamp\n", "")
        assert out["segments"][0]["start"] == pytest.approx(1.5)
        assert out["segments"][0]["end"] == pytest.approx(4.25)

    def test_hh_mm_ss_mmm_values_convert_to_seconds(self):
        out = _parse_transcribe_cpp_output("[00:01:02.500 --> 00:01:07.000] one minute seven\n", "")
        assert out["segments"][0]["start"] == pytest.approx(62.5)
        assert out["segments"][0]["end"] == pytest.approx(67.0)


# ── Edge 3: continuation lines after text: ──────────────────────────────────


class TestV0655TextContinuation:
    def test_wrapped_text_lines_are_kept(self):
        """A long ``text:`` value wraps onto following lines — the wrap
        lines have NO prefix. Pre-fix they were silently dropped."""
        out = _parse_transcribe_cpp_output(
            "text: There are three main things\n"
            "to consider when transcription\n"
            "works correctly.\n"
            "detected-language: en\n",
            "",
        )
        assert "to consider when transcription" in out["text"]
        assert "works correctly." in out["text"]
        assert out["text"].startswith("There are three main things")

    def test_info_line_terminates_the_continuation(self):
        out = _parse_transcribe_cpp_output(
            "text: the transcript text\nbackend: Vulkan\nan unmarked line\n", ""
        )
        assert "the transcript text" in out["text"]
        # 'backend:' is an info line → stops the continuation; the line
        # AFTER it is not swallowed into the text.
        assert "an unmarked line" not in out["text"]
        assert out["backend"] == "Vulkan"

    def test_timestamp_line_terminates_the_continuation(self):
        """A segment line after a wrapped text block is a SEGMENT, not
        more text."""
        out = _parse_transcribe_cpp_output(
            "text: wrapped head\nwrapped tail\n[ 0.00 -> 2.00] first segment\n",
            "",
        )
        assert "wrapped tail" in out["text"]
        assert len(out["segments"]) == 1
        assert out["segments"][0]["text"] == "first segment"


# ── Edge 4: segments-only output builds its text from the segments ─────────


class TestV0655SegmentsOnlyFallback:
    def test_text_is_built_from_segments_when_no_text_line(self):
        """No ``text:`` line at all: the transcript is simply the joined
        segment texts — NOT the raw-stdout fallback (which drags info
        lines along)."""
        out = _parse_transcribe_cpp_output(
            "audio: x.wav samples: 1 duration: 2.0\n"
            "detected-language: en\n"
            "segments: 2\n"
            "[ 0.00 -> 1.00] alpha bravo\n"
            "[ 1.00 -> 2.00] charlie delta\n",
            "",
        )
        assert out["text"] == "alpha bravo charlie delta"
        assert "audio:" not in out["text"]
        assert "segments:" not in out["text"]
        assert len(out["segments"]) == 2


# ── Edge 5: the 'detected language' spacing variant ─────────────────────────


class TestV0655LanguageVariants:
    def test_space_variant_is_recognized(self):
        out = _parse_transcribe_cpp_output("detected language: fa\n", "")
        assert out["language"] == "fa"

    def test_hyphen_variant_still_recognized(self):
        out = _parse_transcribe_cpp_output("detected-language: en\n", "")
        assert out["language"] == "en"


# ── Edge 6+7: BOM + progress bars + CRLF ────────────────────────────────────


class TestV0655EncodingAndProgressNoise:
    def test_utf8_bom_does_not_poison_the_first_line(self):
        out = _parse_transcribe_cpp_output("\ufefftext: bommy\n", "")
        assert out["text"] == "bommy"

    def test_percent_bar_lines_are_skipped(self):
        """Progress bars that carry % and | but no it/s marker (the
        transcribe.cpp style) must not leak into the text."""
        out = _parse_transcribe_cpp_output(
            "text: real transcript\n12%|████████ | 00:12<00:34\n47%|██ | 00:20<00:24\n",
            "",
        )
        assert "00:12" not in out["text"]
        assert "████" not in out["text"]
        assert out["text"] == "real transcript"

    def test_crlf_output_parses_cleanly(self):
        out = _parse_transcribe_cpp_output(
            "text: windows line endings\r\ndetected-language: en\r\n[ 0.00 -> 1.00 ] crlf seg\r\n",
            "",
        )
        assert out["text"] == "windows line endings"
        assert out["language"] == "en"
        assert out["segments"][0]["text"] == "crlf seg"

    def test_stderr_is_still_merged(self):
        """The V0.6.52 contract: stdout + stderr are both searched."""
        out = _parse_transcribe_cpp_output("backend: Vulkan\n", "detected-language: de\n")
        assert out["backend"] == "Vulkan"
        assert out["language"] == "de"


# ── Task 9 review fix: the stdout/stderr stream boundary ────────────────────


class TestV0655StreamBoundary:
    def test_stderr_noise_never_pollutes_a_trailing_text_block(self):
        """THE REVIEW'S REPRODUCTION: stdout ENDING in a ``text:`` block
        used to leave the continuation flag on, so every unrecognized
        STDERR line (model-load chatter) was appended to the
        transcript. Streams are now parsed separately — the block can
        never cross the boundary."""
        out = _parse_transcribe_cpp_output(
            "backend: Vulkan\ntext: This is the transcript.",
            (
                "whisper_init_from_file_with_callbacks_no_state: loading model "
                "from 'ggml-base.bin'\n"
                "whisper_model_load: vocab size 51864\n"
                "whisper_model_load: comput = 466.13 MB\n"
            ),
        )
        assert out["backend"] == "Vulkan"
        assert out["text"] == "This is the transcript."
        assert "whisper_model_load" not in out["text"]
        assert "vocab" not in out["text"]

    def test_metadata_still_comes_from_either_stream(self):
        """The V0.6.52 contract survives the split: stderr's backend /
        language / segments still parse."""
        out = _parse_transcribe_cpp_output(
            "text: body\n", "backend: CPU\ndetected-language: de\n[ 1.00 -> 2.00 ] seg\n"
        )
        assert out["text"] == "body"
        assert out["backend"] == "CPU"
        assert out["language"] == "de"
        assert out["segments"][0]["text"] == "seg"
