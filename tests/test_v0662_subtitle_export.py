"""V0.6.62 -- the subtitle export (SRT + WebVTT).

THE TRIGGER (the V0.6.61 stage summary's "next natural focus"): the
transcribe tool's model arc is complete (V0.6.53 crash ->
V0.6.54-58 UX/telemetry -> V0.6.59 catalog -> V0.6.60 downloader ->
V0.6.61 off-thread scan + sha256), but the OUTPUT story still only
writes transcript.md / summary.md / tutorial.md. The engine has
parsed timestamped segments since the V0.6.55 P6 parser work --
yet the app that transcribes VIDEO cannot emit the one deliverable
video tools actually consume: SUBTITLE FILES.

WHAT V0.6.62 ADDS
-----------------
  1. A Qt-free stdlib leaf ``core/transcribe/subtitle_export.py``:
     ``format_srt_timestamp`` (HH:MM:SS,mmm -- the comma standard),
     ``format_vtt_timestamp`` (HH:MM:SS.mmm -- the dot standard),
     ``wrap_cue_text`` (the broadcast-standard 42-char x 2-line cue
     wrap; word boundaries; over-long words hard-split; words are
     NEVER dropped -- the tail merges into the last line rather than
     being ellipsized away), ``segments_to_srt`` / ``segments_to_vtt``
     (contiguous cue numbering, empty-text segments skipped, inverted
     timestamps clamped, "-->" inside cue text sanitized so a stray
     arrow can never forge a second timing line), ``subtitle_stats``
     (cue count + coverage end), and ``write_subtitle_files`` (the
     dialog-facing writer: <stem>.srt + <stem>.vtt, honest ``cues: 0``
     + no file when the engine produced no segments, OSError ->
     ``error`` key, never a raise).
  2. Dialog wiring: a 🎬 subtitle checkbox row (SRT default ON -- it
     is the natural companion of the raw transcript; VTT opt-in),
     ``save_srt`` / ``save_vtt`` in the options dict + the run header,
     and a "Step 3b" in ``_do_transcribe`` that writes the subtitles
     BEFORE the LLM steps -- an LLM failure never costs the subtitles
     (the V0.6.54 raw-transcript non-fatal contract, extended).
  3. The completion-dialog styling upgrade (the mandatory styling
     item): the plain-text file list becomes a rich-text HTML table
     (icon + bold file name + per-file description, subtitle rows
     carry the cue count) while KEEPING the QMessageBox.information
     + "Transcription Complete" recorder contract the rig e2e pins.

ROUNDING NOTE (why no banker's-rounding pin): a float ``seconds`` can
NEVER land exactly on a half-millisecond boundary after ``* 1000``
(a half-ms needs seconds == odd/2000, whose denominator's factor of
125 makes it non-dyadic -- not exactly representable), so
``int(ms + 0.5)`` and ``round(ms)`` are equivalent for every input
this function can receive. The observable behavior pinned below is
the CARRY through the boundary (59.9999999 -> 00:01:00,000).

TEST LAYOUT
-----------
  A. timestamp formatting     -- SRT comma / VTT dot standards
  B. SRT structure            -- exact canonical blocks
  C. VTT structure            -- WEBVTT header + cue blocks
  D. cue hygiene              -- empty skip, clamp, -->, \r, wrap
  E. write_subtitle_files     -- the writer contract
  F. subtitle_stats           -- cue count + coverage
  G. dialog AST pins          -- house style (no PySide6 needed)
  H. pipeline_log             -- the run-header subtitle line
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parents[1]
_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_PIPELOG = _project_root / "core" / "transcribe" / "pipeline_log.py"


# ═══════════════════════════════════════════════════════════════════════════
# A. timestamp formatting
# ═══════════════════════════════════════════════════════════════════════════


class TestSrtTimestamps:
    def test_zero(self):
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(0.0) == "00:00:00,000"

    def test_plain_seconds_use_the_comma_standard(self):
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(2.5) == "00:00:02,500"
        assert format_srt_timestamp(3661.5) == "01:01:01,500"

    def test_hours_beyond_99_widen_not_truncate(self):
        """A 100-hour file must print 100:00:05,000 (f"{h:02d}" widens
        naturally) -- truncating the hours would corrupt the cue."""
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(3600 * 100 + 5) == "100:00:05,000"

    def test_negative_clamps_to_zero(self):
        """A malformed segment (start=-3) must not print -00:00:03,000."""
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(-3.0) == "00:00:00,000"

    def test_carry_through_the_second_boundary(self):
        """59.9999999 (the float-artifact shape a parser can emit) must
        round UP through the carry: 00:01:00,000, not 00:00:59,999."""
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(59.9999999) == "00:01:00,000"
        assert format_srt_timestamp(0.9999999) == "00:00:01,000"

    def test_the_half_up_boundary_is_pinned_never_swap_in_round(self):
        """V0.6.62 review finding 4: the product CAN land exactly on
        k+0.5 (0.0025 * 1000.0 == 2.5 EXACTLY -- the float error
        cancels), where Python's round() goes to EVEN (round(2.5)==2)
        but the broadcast world rounds half-UP. A silent refactor to
        round() would shift this by a millisecond -- pin it."""
        from core.transcribe.subtitle_export import format_srt_timestamp, format_vtt_timestamp

        assert 0.0025 * 1000.0 == 2.5  # the premise, proved
        assert format_srt_timestamp(0.0025) == "00:00:00,003"
        assert format_vtt_timestamp(0.0025) == "00:00:00.003"

    def test_nonfinite_does_not_crash(self):
        """nan/inf must clamp to zero -- an OverflowError from int(inf)
        would kill the whole export over one bad segment."""
        from core.transcribe.subtitle_export import format_srt_timestamp

        assert format_srt_timestamp(float("nan")) == "00:00:00,000"
        assert format_srt_timestamp(float("inf")) == "00:00:00,000"


class TestVttTimestamps:
    def test_dot_standard(self):
        from core.transcribe.subtitle_export import format_vtt_timestamp

        assert format_vtt_timestamp(0.0) == "00:00:00.000"
        assert format_vtt_timestamp(3661.5) == "01:01:01.500"

    def test_carry_and_clamp_match_the_srt_semantics(self):
        from core.transcribe.subtitle_export import format_vtt_timestamp

        assert format_vtt_timestamp(59.9999999) == "00:01:00.000"
        assert format_vtt_timestamp(-1.0) == "00:00:00.000"

    def test_half_up_boundary(self):
        from core.transcribe.subtitle_export import format_vtt_timestamp

        assert format_vtt_timestamp(0.0025) == "00:00:00.003"


# ═══════════════════════════════════════════════════════════════════════════
# B. SRT structure
# ═══════════════════════════════════════════════════════════════════════════

_SEGS = [
    {"start": 0.0, "end": 2.0, "text": "Hello world."},
    {"start": 2.0, "end": 4.5, "text": "Second line"},
]


class TestSrtStructure:
    def test_two_segments_exact_canonical_output(self):
        """Numbered cues, comma timestamps, one blank line between
        blocks, single trailing newline after the last text line."""
        from core.transcribe.subtitle_export import segments_to_srt

        assert segments_to_srt(_SEGS) == (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "Hello world.\n"
            "\n"
            "2\n"
            "00:00:02,000 --> 00:00:04,500\n"
            "Second line\n"
        )

    def test_empty_segments_produce_the_empty_string(self):
        from core.transcribe.subtitle_export import segments_to_srt

        assert segments_to_srt([]) == ""

    def test_wrapping_can_be_disabled(self):
        from core.transcribe.subtitle_export import segments_to_srt

        long_seg = [{"start": 0.0, "end": 5.0, "text": " ".join(["word"] * 30)}]
        wrapped = segments_to_srt(long_seg)
        unwrapped = segments_to_srt(long_seg, wrap=False)
        assert "\n" in wrapped.split(" --> ")[1].split("\n", 1)[1]  # 2 lines
        assert " ".join(["word"] * 30) in unwrapped  # one long line

    def test_wrap_false_still_never_emits_a_blank_line_inside_a_cue(self):
        """A blank line TERMINATES an SRT cue -- interior blanks in the
        raw text (wrap=False path) must be dropped, or the block
        splits in two and every player after the first misparses."""
        from core.transcribe.subtitle_export import segments_to_srt

        segs = [{"start": 0.0, "end": 3.0, "text": "line one\n\nline two\n"}]
        out = segments_to_srt(segs, wrap=False)
        assert out == "1\n00:00:00,000 --> 00:00:03,000\nline one\nline two\n"


# ═══════════════════════════════════════════════════════════════════════════
# C. VTT structure
# ═══════════════════════════════════════════════════════════════════════════


class TestVttStructure:
    def test_header_and_cues(self):
        from core.transcribe.subtitle_export import segments_to_vtt

        assert segments_to_vtt(_SEGS) == (
            "WEBVTT\n"
            "\n"
            "00:00:00.000 --> 00:00:02.000\n"
            "Hello world.\n"
            "\n"
            "00:00:02.000 --> 00:00:04.500\n"
            "Second line\n"
        )

    def test_empty_segments_produce_the_bare_header(self):
        """A zero-cue WebVTT file is legal; an empty SRT is not written."""
        from core.transcribe.subtitle_export import segments_to_vtt

        assert segments_to_vtt([]) == "WEBVTT\n"


# ═══════════════════════════════════════════════════════════════════════════
# D. cue hygiene
# ═══════════════════════════════════════════════════════════════════════════


class TestCueHygiene:
    def test_empty_text_segments_are_skipped_numbering_stays_contiguous(self):
        from core.transcribe.subtitle_export import segments_to_srt

        segs = [
            {"start": 0.0, "end": 1.0, "text": "one"},
            {"start": 1.0, "end": 2.0, "text": "   "},  # whitespace-only
            {"start": 2.0, "end": 3.0, "text": None},  # engine quirk
            {"start": 3.0, "end": 4.0, "text": "two"},
        ]
        out = segments_to_srt(segs)
        assert "one" in out and "two" in out
        assert out.startswith("1\n") and "\n\n2\n" in out and "3\n" not in out

    def test_inverted_timestamps_clamp_to_zero_length(self):
        """end < start (parser edge) must clamp to end == start -- a
        NEGATIVE duration line like '00:00:05,000 --> 00:00:02,000'
        makes players reject the whole file."""
        from core.transcribe.subtitle_export import segments_to_srt

        out = segments_to_srt([{"start": 5.0, "end": 2.0, "text": "x"}])
        assert "00:00:05,000 --> 00:00:05,000" in out

    def test_a_stray_arrow_cannot_forge_a_timing_line(self):
        """'-->' inside cue text is the SRT structure delimiter -- a
        transcript line like 'drag the slider a --> b' would create a
        phantom cue header in some parsers. It must be sanitized."""
        from core.transcribe.subtitle_export import segments_to_srt, segments_to_vtt

        segs = [{"start": 0.0, "end": 1.0, "text": "drag a --> b here"}]
        srt = segments_to_srt(segs)
        vtt = segments_to_vtt(segs)
        # exactly ONE timing arrow per file (the real one)
        assert srt.count("-->") == 1
        assert vtt.count("-->") == 1
        # the words survive
        assert "drag a" in srt and "b here" in srt

    def test_carriage_returns_are_normalized(self):
        """A CRLF transcript must not leak \r into the cue (players on
        POSIX render it as a visible artifact)."""
        from core.transcribe.subtitle_export import segments_to_srt

        segs = [{"start": 0.0, "end": 1.0, "text": "line one\r\nline two\r"}]
        out = segments_to_srt(segs)
        assert "\r" not in out
        assert "line one" in out and "line two" in out


class TestCueWrapping:
    def test_short_text_unchanged(self):
        from core.transcribe.subtitle_export import wrap_cue_text

        assert wrap_cue_text("short text") == "short text"

    def test_word_wrap_fits_two_lines(self):
        from core.transcribe.subtitle_export import wrap_cue_text

        text = " ".join(["aaaa"] * 14)  # 14 words = 69 chars -> 2 lines
        out = wrap_cue_text(text)
        lines = out.split("\n")
        assert len(lines) == 2
        assert all(len(ln) <= 42 for ln in lines)
        assert out.split() == text.split()  # no words lost

    def test_over_long_tail_merges_into_the_last_line_never_drops(self):
        """20 words cannot fit 2x42 -- the LAST line grows past 42
        rather than losing transcript words (honest over pretty)."""
        from core.transcribe.subtitle_export import wrap_cue_text

        words = ["aaaa"] * 20
        out = wrap_cue_text(" ".join(words))
        lines = out.split("\n")
        assert len(lines) == 2
        assert lines[0] == " ".join(["aaaa"] * 8)  # 8 words = 39 chars
        assert out.split() == words  # every word survived
        assert len(lines[1]) > 42  # the honest overflow

    def test_an_over_long_single_word_hard_splits(self):
        """A 100-char unbroken token (a URL, a German compound) hard-
        splits at the limit instead of overflowing line one."""
        from core.transcribe.subtitle_export import wrap_cue_text

        out = wrap_cue_text("w" * 100)
        lines = out.split("\n")
        assert len(lines) == 2
        assert lines[0] == "w" * 42
        assert "".join(out.split()) == "w" * 100  # no chars lost

    def test_degenerate_params_are_clamped_not_hung(self):
        """V0.6.62 review finding 1: max_chars<=0 made the hard-split
        loop slice zero bytes forever (an 8s+ hang proved). The clamp
        floors both params at 1; the observable: TERMINATES, every
        char survives, exactly max_lines lines (the tail-merge rule
        still dominates -- line one carries the single-char split)."""
        from core.transcribe.subtitle_export import wrap_cue_text

        out = wrap_cue_text("abc", max_chars=0)
        assert out == "a\nb c"  # chars 1-per-line then merged tail
        assert "".join(out.split()) == "abc"  # nothing lost
        out2 = wrap_cue_text("ab cd", max_chars=1, max_lines=2)
        assert out2 == "a\nb c d"  # hard-split 'ab' -> a|b, tail merges
        assert "".join(out2.split()) == "abcd"

    def test_none_text_is_empty_not_the_string_none(self):
        from core.transcribe.subtitle_export import wrap_cue_text

        assert wrap_cue_text(None) == ""


# ═══════════════════════════════════════════════════════════════════════════
# E. write_subtitle_files
# ═══════════════════════════════════════════════════════════════════════════


class TestWriteSubtitleFiles:
    def test_both_formats_written(self, tmp_path):
        from core.transcribe.subtitle_export import write_subtitle_files

        res = write_subtitle_files(_SEGS, tmp_path, "sample")
        assert res["error"] is None
        assert res["cues"] == 2
        srt = tmp_path / "sample.srt"
        vtt = tmp_path / "sample.vtt"
        assert srt.exists() and vtt.exists()
        assert res["srt_path"] == str(srt) and res["vtt_path"] == str(vtt)
        assert srt.read_text(encoding="utf-8").startswith("1\n00:00:00,000 --> ")
        assert vtt.read_text(encoding="utf-8").startswith("WEBVTT\n")

    def test_srt_only(self, tmp_path):
        from core.transcribe.subtitle_export import write_subtitle_files

        res = write_subtitle_files(_SEGS, tmp_path, "sample", want_srt=True, want_vtt=False)
        assert res["srt_path"] and res["vtt_path"] is None
        assert (tmp_path / "sample.srt").exists()
        assert not (tmp_path / "sample.vtt").exists()

    def test_no_segments_writes_nothing_and_says_so(self, tmp_path):
        """The segments-as-text fallback produced no timestamps -- an
        empty .srt would be a broken deliverable; skip honestly."""
        from core.transcribe.subtitle_export import write_subtitle_files

        res = write_subtitle_files([], tmp_path, "sample")
        assert res["cues"] == 0
        assert res["srt_path"] is None and res["vtt_path"] is None
        assert res["error"] is None
        assert not (tmp_path / "sample.srt").exists()

    def test_existing_files_are_replaced_idempotent_rerun(self, tmp_path):
        """Re-running over a previous export must replace, not append
        or fail (the out folder is user-chosen and usually reused)."""
        from core.transcribe.subtitle_export import write_subtitle_files

        (tmp_path / "sample.srt").write_text("GARBAGE\n", encoding="utf-8")
        write_subtitle_files(_SEGS, tmp_path, "sample")
        body = (tmp_path / "sample.srt").read_text(encoding="utf-8")
        assert "GARBAGE" not in body and body.startswith("1\n")

    def test_oserror_is_reported_not_raised(self, tmp_path):
        """A bad out folder (a FILE where a dir belongs) must surface
        as res['error'] -- a raise would kill the whole run AFTER the
        transcription already succeeded."""
        from core.transcribe.subtitle_export import write_subtitle_files

        blocker = tmp_path / "blocker.txt"
        blocker.write_text("x", encoding="utf-8")
        res = write_subtitle_files(_SEGS, blocker / "sub", "sample")
        assert res["error"] is not None
        assert res["srt_path"] is None and res["vtt_path"] is None

    def test_hostile_arguments_error_not_raise(self, tmp_path):
        """V0.6.62 review findings 2+7: a null-byte stem raises
        ValueError and an int out_folder raises TypeError straight
        out of pathlib -- the never-raise contract must hold for
        hostile callers too."""
        from core.transcribe.subtitle_export import write_subtitle_files

        res = write_subtitle_files(_SEGS, tmp_path, "bad\x00stem")
        assert res["error"] is not None and res["srt_path"] is None
        res2 = write_subtitle_files(_SEGS, 12345, "sample")
        assert res2["error"] is not None and res2["srt_path"] is None

    def test_a_traversal_stem_writes_only_inside_dest(self, tmp_path):
        """V0.6.62 review finding 2 (the V0.6.60 precedent class): a
        caller-supplied '../escape' stem must never write OUTSIDE the
        destination; an empty/dot-dot stem is rejected honestly."""
        from core.transcribe.subtitle_export import write_subtitle_files

        dest = tmp_path / "dest"
        res = write_subtitle_files(_SEGS, dest, "../escape")
        assert res["error"] is None
        assert res["srt_path"] == str(dest / "escape.srt")
        assert (dest / "escape.srt").exists()
        assert not (tmp_path / "escape.srt").exists()
        for bad in ("", "..", "/"):
            res_bad = write_subtitle_files(_SEGS, dest, bad)
            assert res_bad["error"] is not None, bad
            assert res_bad["srt_path"] is None

    def test_neither_format_wanted_creates_nothing(self, tmp_path):
        """V0.6.62 review finding 6: both flags off -> not even the
        directory may appear (the dialog guards, but the headless
        API must not surprise a script with mkdir side effects)."""
        from core.transcribe.subtitle_export import write_subtitle_files

        dest = tmp_path / "never"
        res = write_subtitle_files(_SEGS, dest, "sample", want_srt=False, want_vtt=False)
        assert res == {"srt_path": None, "vtt_path": None, "cues": 0, "error": None}
        assert not dest.exists()

    def test_five_hundred_segment_round_trip(self, tmp_path):
        """The realistic shape: a long video's full segment list."""
        from core.transcribe.subtitle_export import write_subtitle_files

        segs = [
            {"start": float(i * 2), "end": float(i * 2 + 1.8), "text": f"cue number {i}"}
            for i in range(500)
        ]
        res = write_subtitle_files(segs, tmp_path, "long")
        assert res["cues"] == 500
        body = (tmp_path / "long.srt").read_text(encoding="utf-8")
        assert body.count(" --> ") == 500
        assert "\n500\n" in body  # the last cue number


# ═══════════════════════════════════════════════════════════════════════════
# F. subtitle_stats
# ═══════════════════════════════════════════════════════════════════════════


class TestSubtitleStats:
    def test_cue_count_and_coverage_end(self):
        from core.transcribe.subtitle_export import subtitle_stats

        stats = subtitle_stats(_SEGS + [{"start": 8.0, "end": 10.5, "text": "third"}])
        assert stats == {"cues": 3, "end": 10.5}

    def test_empty_text_segments_do_not_count(self):
        from core.transcribe.subtitle_export import subtitle_stats

        stats = subtitle_stats(_SEGS + [{"start": 8.0, "end": 9.0, "text": " "}])
        assert stats["cues"] == 2

    def test_empty(self):
        from core.transcribe.subtitle_export import subtitle_stats

        assert subtitle_stats([]) == {"cues": 0, "end": 0.0}

    def test_end_is_the_furthest_not_the_last(self):
        """V0.6.62 review finding 8: an unsorted segment list must not
        under-report coverage -- end is max(), not last."""
        from core.transcribe.subtitle_export import subtitle_stats

        stats = subtitle_stats(
            [
                {"start": 50.0, "end": 60.0, "text": "late but first"},
                {"start": 0.0, "end": 5.0, "text": "early"},
            ]
        )
        assert stats == {"cues": 2, "end": 60.0}


# ═══════════════════════════════════════════════════════════════════════════
# G. dialog AST pins (house style -- the sandbox has no PySide6)
# ═══════════════════════════════════════════════════════════════════════════

_DIALOG_TREE_CACHE: dict[str, ast.Module] = {}


def _dialog_tree() -> ast.Module:
    if "t" not in _DIALOG_TREE_CACHE:
        _DIALOG_TREE_CACHE["t"] = ast.parse(
            _DIALOG.read_text(encoding="utf-8"), filename=str(_DIALOG)
        )
    return _DIALOG_TREE_CACHE["t"]


def _method(t: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(t):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    pytest.fail(f"method {name!r} not found in the dialog source")


def _unparse(t: ast.Module, name: str) -> str:
    return ast.unparse(_method(t, name))


class TestDialogSubtitleCheckboxes:
    def test_build_options_creates_both_checkboxes(self):
        build = _method(_dialog_tree(), "_build_options")
        assigned = {
            t.attr
            for t in ast.walk(build)
            if isinstance(t, ast.Attribute)
            and isinstance(t.ctx, ast.Store)
            and t.attr in ("cb_srt", "cb_vtt")
        }
        assert assigned == {"cb_srt", "cb_vtt"}, "cb_srt/cb_vtt must be created in _build_options"

    def test_srt_defaults_on_vtt_defaults_off(self):
        """SRT is the natural companion of the raw transcript (default
        ON, matching cb_raw); WebVTT is the web-only opt-in (OFF)."""
        src = _unparse(_dialog_tree(), "_build_options")
        assert "self.cb_srt.setChecked(True)" in src
        assert "self.cb_vtt.setChecked(False)" in src

    def test_both_carry_tooltips(self):
        """A subtitle format is jargon -- the tooltip says what each
        format is FOR (players/editors vs web), per the house
        accessibility standard."""
        src = _unparse(_dialog_tree(), "_build_options")
        assert "self.cb_srt.setToolTip(" in src
        assert "self.cb_vtt.setToolTip(" in src

    def test_the_pair_sits_on_one_compact_row(self):
        """V0.6.62 review finding 2 (the V0.6.61 finding-1 class): the
        old addStretch() substring pin was VACUOUS -- the pre-existing
        engine/model-row stretches satisfied it, and a mutant that
        split the pair onto two full-width rows survived every pin.
        STRUCTURAL now: some single _HL() row must receive BOTH
        cb_srt and cb_vtt via addWidget AND carry an addStretch."""
        build = _method(_dialog_tree(), "_build_options")
        # 1. the local names bound to a fresh _HL() row
        row_names = {
            a.targets[0].id
            for a in ast.walk(build)
            if isinstance(a, ast.Assign)
            and len(a.targets) == 1
            and isinstance(a.targets[0], ast.Name)
            and isinstance(a.value, ast.Call)
            and isinstance(a.value.func, ast.Name)
            and a.value.func.id == "_HL"
        }
        assert row_names, "_build_options must build _HL() rows"
        # 2. for each row: which checkboxes does it addWidget, does it
        #    addStretch?
        for name in row_names:
            added: set[str] = set()
            stretched = False
            for call in ast.walk(build):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                    continue
                base = call.func.value
                if not (isinstance(base, ast.Name) and base.id == name):
                    continue
                if call.func.attr == "addWidget":
                    arg = call.args[0] if call.args else None
                    if isinstance(arg, ast.Attribute) and arg.attr in ("cb_srt", "cb_vtt"):
                        added.add(arg.attr)
                elif call.func.attr == "addStretch":
                    stretched = True
            if added == {"cb_srt", "cb_vtt"}:
                assert stretched, f"the subtitle row ({name}) must end with addStretch()"
                return
        pytest.fail("no single _HL() row receives BOTH cb_srt and cb_vtt")


class TestDialogOptionsAndRunHeader:
    def test_options_dict_carries_the_subtitle_keys_with_guards(self):
        """The options dict gains save_srt/save_vtt read from the
        checkboxes with the hasattr guard (the cb_tutorial pattern --
        a stale pickled/older dialog instance must not crash)."""
        src = _unparse(_dialog_tree(), "_on_process")
        # ast.unparse renders strings single-quoted -> check the call
        # sites textually, the DICT KEYS structurally (below).
        assert "self.cb_srt.isChecked()" in src and "self.cb_vtt.isChecked()" in src
        assert "hasattr(self, 'cb_srt')" in src and "hasattr(self, 'cb_vtt')" in src
        run = _method(_dialog_tree(), "_on_process")
        opts_dicts = [
            n
            for n in ast.walk(run)
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "save_raw" for k in n.keys)
        ]
        assert opts_dicts, "the options dict must exist in _on_process"
        keys = {k.value for k in opts_dicts[0].keys if isinstance(k, ast.Constant)}
        assert "save_srt" in keys and "save_vtt" in keys

    def test_the_run_header_sees_the_subtitle_flags(self):
        """format_run_header is called with save_srt=/save_vtt= so the
        live log's run header records the subtitle intent."""
        src = _unparse(_dialog_tree(), "_on_process")
        assert "save_srt=" in src and "save_vtt=" in src


class TestDialogRunWiring:
    def test_do_transcribe_calls_the_leaf_writer(self):
        src = _unparse(_dialog_tree(), "_do_transcribe")
        assert "write_subtitle_files(" in src
        assert "save_srt" in src and "save_vtt" in src

    def test_subtitles_are_written_before_the_llm_steps(self):
        """ORDERING PIN (the V0.6.54 contract extended): the subtitle
        write must precede EVERY summarize call -- an LLM failure (the
        slow rig's 10-minute frozen-summary failure mode) must never
        cost the subtitle files, exactly like the raw transcript."""
        run = _method(_dialog_tree(), "_do_transcribe")
        sub_lines = [
            n.lineno
            for n in ast.walk(run)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "write_subtitle_files"
        ]
        llm_lines = [
            n.lineno
            for n in ast.walk(run)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id.startswith("summarize_transcript")
        ]
        assert sub_lines, "write_subtitle_files must be called in _do_transcribe"
        assert llm_lines, "the summarize calls must exist for the ordering pin"
        assert max(sub_lines) < min(llm_lines), (
            "subtitles must be written BEFORE the LLM steps "
            f"(sub at {sub_lines}, llm at {llm_lines})"
        )

    def test_results_dict_gains_the_subtitle_keys(self):
        run = _method(_dialog_tree(), "_do_transcribe")
        results_dicts = [
            n
            for n in ast.walk(run)
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "raw_path" for k in n.keys)
        ]
        assert results_dicts, "the results init dict must exist"
        keys = {k.value for k in results_dicts[0].keys if isinstance(k, ast.Constant)}
        assert "srt_path" in keys and "vtt_path" in keys

    def test_no_segments_skips_with_an_honest_message(self):
        """The segments-as-text fallback (no timestamps) must tell the
        operator WHY no subtitles appeared -- not a silent no-file."""
        src = _unparse(_dialog_tree(), "_do_transcribe")
        assert "No timestamped segments" in src

    def test_subtitle_write_failures_reach_the_results(self):
        """V0.6.62 review finding 4: a subtitle OSError used to be a
        live-log ⚠️ line ONLY -- the completion box said "complete!"
        with no files. It must surface as results['subtitle_error']
        so _on_done renders it (status part + box row)."""
        src = _unparse(_dialog_tree(), "_do_transcribe")
        assert "subtitle_error" in src

    def test_subtitle_cues_inits_to_zero(self):
        """V0.6.62 review finding 5: the counter's 0-init is a stated
        contract (the "no subtitles" sentinel) -- pin the value, not
        just the key's existence."""
        run = _method(_dialog_tree(), "_do_transcribe")
        init_dicts = [
            n
            for n in ast.walk(run)
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "raw_path" for k in n.keys)
        ]
        assert init_dicts
        val = {
            k.value: v
            for k, v in zip(init_dicts[0].keys, init_dicts[0].values, strict=True)
            if isinstance(k, ast.Constant) and k.value == "subtitle_cues"
        }
        assert val == {"subtitle_cues": ast.Constant(value=0)} or (
            "subtitle_cues" in val
            and isinstance(val["subtitle_cues"], ast.Constant)
            and val["subtitle_cues"].value == 0
        ), "subtitle_cues must init to the constant 0"


class TestCompletionDialogUpgrade:
    def test_on_done_lists_the_subtitle_files(self):
        src = _unparse(_dialog_tree(), "_on_done")
        assert "srt_path" in src and "vtt_path" in src
        assert "Subtitles" in src

    def test_the_completion_box_is_now_rich_text(self):
        """The styling upgrade: the plain file list becomes an HTML
        table (bold file names, per-file descriptions)."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "<b>" in src
        assert "<table" in src or "<tr" in src

    def test_the_early_critical_branch_honors_subtitles_too(self):
        """V0.6.62 review finding 1: the stale V0.6.54 condition keyed
        ONLY on raw_path -- with save_raw off + 🎬 on + an LLM error,
        the user got a bare "❌ Failed" while the .srt/.vtt WERE on
        disk. The branch must consider EVERY on-disk deliverable."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "not any(" in src
        assert "'raw_path', 'srt_path', 'vtt_path'" in src
        # the nothing-saved path still goes critical
        assert "QMessageBox.critical" in src

    def test_a_subtitle_error_gets_its_own_box_row(self):
        """The subtitle write failure must render in the completion box
        (status part + HTML row), not just the live log."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "subtitle_error" in src

    def test_every_interpolated_string_is_html_escaped(self):
        """V0.6.62 review finding 3: file names / the error text / the
        output path are externally-controlled strings injected into
        Qt rich text -- a dropped escape is an HTML-injection ship.
        The three exact call sites (note ast.unparse single-quotes)."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "html.escape(Path(p).name)" in src
        assert "html.escape(str(results['error']))" in src
        assert "html.escape(str(results['subtitle_error']))" in src
        assert "html.escape(self.out_edit.text())" in src

    def test_the_recorder_contract_survives_the_upgrade(self):
        """The rig e2e pins record QMessageBox.information with a
        'Transcription Complete' title (test_v0600 line 1149-1150) --
        the rich-text upgrade must keep that exact call shape."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "QMessageBox.information" in src
        assert "Transcription Complete" in src

    def test_heartbeat_stop_survives(self):
        """The V0.6.56 pin: _heartbeat_timer.stop() on every
        completion path (untouched by this release's edits)."""
        src = _unparse(_dialog_tree(), "_on_done")
        assert "_heartbeat_timer.stop()" in src


# ═══════════════════════════════════════════════════════════════════════════
# H. pipeline_log -- the run-header subtitle line
# ═══════════════════════════════════════════════════════════════════════════


class TestRunHeaderSubtitles:
    def _header(self, **kw):
        from core.transcribe.pipeline_log import format_run_header

        base = dict(
            filepath="clip.mp4",
            engine="transcribe_cpp",
            whisper_model="m.gguf",
            llm_model="llm",
            save_raw=True,
            save_summary=True,
            save_tutorial=False,
        )
        base.update(kw)
        return format_run_header(**base)

    def test_both_formats_name_them(self):
        lines = self._header(save_srt=True, save_vtt=True)
        assert any("🎬 Subtitles: SRT + VTT" in ln for ln in lines), lines

    def test_srt_only(self):
        lines = self._header(save_srt=True, save_vtt=False)
        # V0.6.62 review finding 3: the substring form was subsumed by
        # the SRT + VTT line -- a save_vtt-ignoring implementation
        # passed. EXACT equality now.
        assert "🎬 Subtitles: SRT" in lines, lines

    def test_off_by_default_backward_compatible(self):
        """The pre-V0.6.62 callers pass no subtitle kwargs -- the
        header must be unchanged for them (no subtitle line)."""
        lines = self._header()
        assert not any("Subtitles" in ln for ln in lines), lines

    def test_the_new_kwargs_default_false_in_the_signature(self):
        src = ast.parse(_PIPELOG.read_text(encoding="utf-8"))
        fn = next(
            n
            for n in ast.walk(src)
            if isinstance(n, ast.FunctionDef) and n.name == "format_run_header"
        )
        # kwonly defaults live in args.kw_defaults (position-aligned,
        # None for a missing default) -- not on the arg nodes.
        defaults = {
            a.arg: d.value
            for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True)
            if a.arg in ("save_srt", "save_vtt") and isinstance(d, ast.Constant)
        }
        assert defaults == {"save_srt": False, "save_vtt": False}
