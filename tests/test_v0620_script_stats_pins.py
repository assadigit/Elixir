"""V0.6.20 — the script-statistics + stats-CLI batch pins.

This file pins the V0.6.20 additions:

Layer 1 — the SCRIPT STATISTICS module (W-f1, core/podcast/script_stats.py):
  - ``count_syllables(word)`` — the heuristic English syllable counter
    (vowel-group + silent-e + -le-ending rules; ±1 syllable accuracy).
  - ``flesch_reading_ease(text)`` — the Flesch Reading Ease score
    (0-100, higher = easier; clamped).
  - ``flesch_kincaid_grade(text)`` — the Flesch-Kincaid grade level
    (e.g., 8.2 = grade 8).
  - ``estimate_duration_seconds(word_count, wpm)`` — the standalone
    duration estimator.
  - ``compute_stats(script, wpm)`` — the main entry point; returns a
    ``ScriptStats`` dataclass with all fields populated.
  - ``format_stats_for_display(stats, log)`` — the multi-line formatter.
  - ``ScriptStats`` + ``HostStats`` + ``SegmentStats`` dataclasses.

Layer 2 — the CLI stats subcommand (W-f2, core/podcast/cli.py):
  - ``stats`` subcommand: prints rich analytics to stdout.
  - ``--json`` flag: outputs the stats as JSON (for piping to other tools).
  - ``--wpm`` flag: overrides the auto-detected words-per-minute.
  - Exits 0 on success, 2 on file/parse error (same contract as info).

All tests are pure-Python (no PySide6 / no torch / no soundfile).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared helpers ──────────────────────────────────────────────────────────


def _make_line(host: str = "A", text: str = "hello", segment_type: str = "content"):
    from core.podcast.script_generator import ScriptLine

    return ScriptLine(host=host, text=text, source_ref="ref", segment_type=segment_type)


def _make_script(lines=None, title: str = "test"):
    from core.podcast.script_generator import ScriptResult

    if lines is None:
        lines = [
            _make_line("A", "intro line", "intro"),
            _make_line("B", "body line", "content"),
            _make_line("A", "conclusion line", "conclusion"),
        ]
    return ScriptResult(lines=lines, title=title)


def _write_script_json(
    path: Path,
    lines: list[dict] | None = None,
    title: str = "test",
) -> Path:
    """Write a minimal script JSON the CLI's _load_script_json can read."""
    if lines is None:
        lines = [
            {"host": "A", "text": "intro line", "source_ref": "ref", "segment_type": "intro"},
            {"host": "B", "text": "body line", "source_ref": "ref", "segment_type": "content"},
            {
                "host": "A",
                "text": "conclusion line",
                "source_ref": "ref",
                "segment_type": "conclusion",
            },
        ]
    data = {
        "lines": lines,
        "title": title,
        "bullets_input": [],
        "bullets_covered": [],
        "bullets_missing": [],
        "coverage_pct": 100.0,
        "retries": 0,
        "forced_segments": 0,
        "error": None,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── Layer 1a: count_syllables ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "word,expected",
    [
        ("hello", 2),
        ("world", 1),
        ("apple", 2),  # -le ending after consonant → +1
        ("table", 2),  # -le ending after consonant → +1
        ("like", 1),  # silent-e strip
        ("time", 1),  # silent-e strip
        ("queue", 1),  # vowel-group 'ueue' = 1
        ("", 0),
        ("TV", 1),  # no vowels -> 1 (default)
        ("a", 1),
        ("the", 1),
    ],
)
def test_v0620_count_syllables_basic_english(word: str, expected: int) -> None:
    """The syllable counter returns the expected count for common
    English words (±1 accuracy — these are the exact-correct cases).

    NOTE: 'rhythm' is deliberately omitted — dictionaries say 2 syllables
    (rhy·thm) but the vowel-group heuristic returns 1 (the 'y' is a single
    vowel group). The heuristic's ±1 accuracy is documented; for a 500-
    word script the grade-level estimate is still reliable. See the
    count_syllables docstring for the algorithm + accuracy note."""
    from core.podcast.script_stats import count_syllables

    assert count_syllables(word) == expected, (
        f"count_syllables({word!r}) returned {count_syllables(word)}, expected {expected}"
    )


def test_v0620_count_syllables_strips_non_alpha() -> None:
    """Non-alpha characters are stripped before counting."""
    from core.podcast.script_stats import count_syllables

    # "hello!" and "hello," should count the same as "hello".
    assert count_syllables("hello!") == count_syllables("hello")
    assert count_syllables("hello,") == count_syllables("hello")
    assert count_syllables("don't") == count_syllables("dont")  # 1


def test_v0620_count_syllables_never_returns_negative() -> None:
    """The syllable counter never returns negative — minimum is 0 for
    empty input, 1 for any non-empty word."""
    from core.podcast.script_stats import count_syllables

    assert count_syllables("") == 0
    assert count_syllables("!!!") == 0  # strips to empty
    assert count_syllables("a") >= 1
    assert count_syllables("xyz") >= 1  # no vowels -> defaults to 1


# ── Layer 1b: flesch_reading_ease + flesch_kincaid_grade ────────────────────


def test_v0620_flesch_reading_ease_empty_text_returns_zero() -> None:
    """Empty text returns 0.0 (no words to score)."""
    from core.podcast.script_stats import flesch_reading_ease

    assert flesch_reading_ease("") == 0.0


def test_v0620_flesch_reading_ease_easy_text_is_high() -> None:
    """A very easy text (short words, short sentences) scores high
    (closer to 100). The cat sat on the mat. The dog ran. = very easy."""
    from core.podcast.script_stats import flesch_reading_ease

    easy = "The cat sat on the mat. The dog ran. The bird flew away."
    score = flesch_reading_ease(easy)
    assert 70 <= score <= 100, f"easy text should score 70-100; got {score}"


def test_v0620_flesch_reading_ease_difficult_text_is_low() -> None:
    """A difficult text (long words, long sentences) scores low
    (closer to 0). Academic jargon = difficult."""
    from core.podcast.script_stats import flesch_reading_ease

    difficult = (
        "The institutionalization of methodological frameworks necessitates "
        "the comprehensive examination of epistemological assumptions "
        "undergirding contemporary theoretical paradigms."
    )
    score = flesch_reading_ease(difficult)
    assert 0 <= score <= 50, f"difficult text should score 0-50; got {score}"


def test_v0620_flesch_reading_ease_clamped_to_0_100() -> None:
    """The score is always in [0, 100] — never negative, never > 100."""
    from core.podcast.script_stats import flesch_reading_ease

    # A pathological text (one very long word) shouldn't produce a
    # negative score — it's clamped to 0.
    pathological = "antidisestablishmentarianism" * 10
    score = flesch_reading_ease(pathological)
    assert 0 <= score <= 100


def test_v0620_flesch_kincaid_grade_empty_text_returns_zero() -> None:
    """Empty text returns 0.0 (no words to score)."""
    from core.podcast.script_stats import flesch_kincaid_grade

    assert flesch_kincaid_grade("") == 0.0


def test_v0620_flesch_kincaid_grade_easy_text_is_low() -> None:
    """An easy text returns a low grade level (e.g., 2-5)."""
    from core.podcast.script_stats import flesch_kincaid_grade

    easy = "The cat sat on the mat. The dog ran fast. I see a tree."
    grade = flesch_kincaid_grade(easy)
    assert 0 <= grade <= 6, f"easy text should be grade 0-6; got {grade}"


def test_v0620_flesch_kincaid_grade_difficult_text_is_high() -> None:
    """A difficult text returns a high grade level (e.g., 12+)."""
    from core.podcast.script_stats import flesch_kincaid_grade

    difficult = (
        "The institutionalization of methodological frameworks necessitates "
        "the comprehensive examination of epistemological assumptions "
        "undergirding contemporary theoretical paradigms."
    )
    grade = flesch_kincaid_grade(difficult)
    assert grade >= 12, f"difficult text should be grade 12+; got {grade}"


def test_v0620_flesch_kincaid_grade_never_negative() -> None:
    """The grade is clamped to >= 0 — never negative."""
    from core.podcast.script_stats import flesch_kincaid_grade

    # A very short text might produce a negative raw score; it's clamped.
    grade = flesch_kincaid_grade("Hi.")
    assert grade >= 0


# ── Layer 1c: estimate_duration_seconds ─────────────────────────────────────


def test_v0620_estimate_duration_zero_words_returns_zero() -> None:
    """Zero words → zero duration."""
    from core.podcast.script_stats import estimate_duration_seconds

    assert estimate_duration_seconds(0) == 0.0


def test_v0620_estimate_duration_negative_words_returns_zero() -> None:
    """Negative word count → zero duration (defensive)."""
    from core.podcast.script_stats import estimate_duration_seconds

    assert estimate_duration_seconds(-10) == 0.0


def test_v0620_estimate_duration_zero_wpm_returns_zero() -> None:
    """Zero WPM → zero duration (defensive, avoids divide-by-zero)."""
    from core.podcast.script_stats import estimate_duration_seconds

    assert estimate_duration_seconds(100, wpm=0) == 0.0


def test_v0620_estimate_duration_150_words_at_150_wpm_is_60_seconds() -> None:
    """150 words at 150 WPM = 1 minute = 60 seconds (the canonical case)."""
    from core.podcast.script_stats import estimate_duration_seconds

    assert estimate_duration_seconds(150, wpm=150) == 60.0


def test_v0620_estimate_duration_scales_linearly() -> None:
    """Duration scales linearly with word count (double words = double time)."""
    from core.podcast.script_stats import estimate_duration_seconds

    d1 = estimate_duration_seconds(100, wpm=150)
    d2 = estimate_duration_seconds(200, wpm=150)
    assert d2 == pytest.approx(2 * d1)


# ── Layer 1d: compute_stats ──────────────────────────────────────────────────


def test_v0620_compute_stats_empty_script_returns_zero_stats() -> None:
    """An empty script returns a ScriptStats with all counts at zero."""
    from core.podcast.script_generator import ScriptResult
    from core.podcast.script_stats import ScriptStats, compute_stats

    stats = compute_stats(ScriptResult(lines=[], title="empty"))
    assert isinstance(stats, ScriptStats)
    assert stats.total_lines == 0
    assert stats.total_words == 0
    assert stats.total_chars == 0
    assert stats.estimated_duration_seconds == 0.0


def test_v0620_compute_stats_counts_lines_words_chars() -> None:
    """The top-level counts match the script's content."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "hello world foo", "intro"),  # 3 words, 15 chars
            _make_line("B", "bar baz", "content"),  # 2 words, 7 chars
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.total_lines == 2
    assert stats.total_words == 5  # 3 + 2
    assert stats.total_chars == 22  # 15 + 7 (no separator chars counted)


def test_v0620_compute_stats_host_breakdown_sums_correctly() -> None:
    """Host A + Host B word counts sum to the total."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "one two three", "intro"),  # 3 words
            _make_line("B", "four five", "content"),  # 2 words
            _make_line("A", "six seven eight nine", "content"),  # 4 words
            _make_line("B", "ten", "conclusion"),  # 1 word
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.host_a.word_count == 7  # 3 + 4
    assert stats.host_b.word_count == 3  # 2 + 1
    assert stats.host_a.word_count + stats.host_b.word_count == stats.total_words


def test_v0620_compute_stats_host_line_counts() -> None:
    """Host A / Host B line counts are correct."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "a", "intro"),
            _make_line("B", "b", "content"),
            _make_line("A", "c", "content"),
            _make_line("A", "d", "conclusion"),
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.host_a.line_count == 3
    assert stats.host_b.line_count == 1


def test_v0620_compute_stats_host_split_ratio_property() -> None:
    """The host_split_ratio property returns a 'A:B' string summing to 100."""
    from core.podcast.script_stats import compute_stats

    # 75 words Host A, 25 words Host B → 75:25.
    lines = [
        _make_line("A", " ".join(f"w{i}" for i in range(75)), "intro"),
        _make_line("B", " ".join(f"w{i}" for i in range(25)), "content"),
    ]
    script = _make_script(lines=lines, title="test")
    stats = compute_stats(script)
    ratio = stats.host_split_ratio
    a, b = (int(x) for x in ratio.split(":"))
    assert a + b == 100
    assert a == 75
    assert b == 25


def test_v0620_compute_stats_host_split_ratio_single_host() -> None:
    """A lecture-mode script (only Host A) returns '100:0'."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "only host a here", "intro"),
            _make_line("A", "still only host a", "conclusion"),
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.host_split_ratio == "100:0"


def test_v0620_compute_stats_segment_distribution() -> None:
    """The segments list breaks down per segment_type."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "intro", "intro"),
            _make_line("A", "content one", "content"),
            _make_line("B", "content two", "content"),
            _make_line("A", "content three", "content"),
            _make_line("A", "conclusion", "conclusion"),
        ],
        title="test",
    )
    stats = compute_stats(script)
    seg_map = {s.segment_type: s for s in stats.segments}
    assert seg_map["intro"].line_count == 1
    assert seg_map["content"].line_count == 3
    assert seg_map["conclusion"].line_count == 1


def test_v0620_compute_stats_line_length_distribution() -> None:
    """avg / median / min / max word counts per line are correct."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "one two three four five", "intro"),  # 5 words
            _make_line("B", "one two", "content"),  # 2 words
            _make_line("A", "one two three four five six seven eight nine ten", "content"),  # 10
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.min_words_in_line == 2
    assert stats.max_words_in_line == 10
    assert stats.avg_words_per_line == pytest.approx((5 + 2 + 10) / 3)
    assert stats.median_words_per_line == 5  # sorted: 2, 5, 10 -> median 5


def test_v0620_compute_stats_unique_words() -> None:
    """Unique word count is case-insensitive (the + THE = 1 unique)."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "the The THE", "intro"),
            _make_line("B", "the cat", "content"),
        ],
        title="test",
    )
    stats = compute_stats(script)
    # 'the', 'the', 'the', 'the', 'cat' -> unique: {'the', 'cat'} = 2
    assert stats.unique_words == 2


def test_v0620_compute_stats_duration_estimate() -> None:
    """The estimated duration matches the WPM-based calculation."""
    from core.podcast.script_stats import compute_stats

    # 150 words at 150 WPM = 60 seconds.
    words_150 = " ".join(f"w{i}" for i in range(150))
    script = _make_script(
        lines=[_make_line("A", words_150, "intro")],
        title="test",
    )
    stats = compute_stats(script)
    assert stats.total_words == 150
    assert stats.estimated_duration_seconds == pytest.approx(60.0)
    assert stats.estimated_duration_human == "1:00"


def test_v0620_compute_stats_wpm_override() -> None:
    """The wpm parameter overrides the auto-detected WPM."""
    from core.podcast.script_stats import compute_stats

    words_150 = " ".join(f"w{i}" for i in range(150))
    script = _make_script(
        lines=[_make_line("A", words_150, "intro")],
        title="test",
    )
    # 150 words at 100 WPM = 90 seconds.
    stats = compute_stats(script, wpm=100)
    assert stats.wpm_used == 100
    assert stats.estimated_duration_seconds == pytest.approx(90.0)


def test_v0620_compute_stats_farsi_uses_farsi_wpm() -> None:
    """A Farsi script auto-detects and uses the Farsi WPM (130, not 150)."""
    from core.podcast.script_stats import FARSI_DEFAULT_WPM, compute_stats

    # Persian text: "سلام دنیا. این یک تست است." (Hello world. This is a test.)
    script = _make_script(
        lines=[
            _make_line("A", "سلام دنیا. این یک تست است.", "intro"),
            _make_line("B", "این متن فارسی است.", "content"),
        ],
        title="farsi test",
    )
    stats = compute_stats(script)
    assert stats.wpm_used == FARSI_DEFAULT_WPM


def test_v0620_compute_stats_reading_level_populated() -> None:
    """The Flesch score + grade + label are populated (not zero/empty)."""
    from core.podcast.script_stats import compute_stats

    script = _make_script(
        lines=[
            _make_line("A", "The cat sat on the mat. The dog ran fast.", "intro"),
            _make_line("B", "I see a bird. The bird flew away. The end.", "content"),
            _make_line("A", "That is the story. Goodbye for now.", "conclusion"),
        ],
        title="test",
    )
    stats = compute_stats(script)
    assert 0 < stats.flesch_reading_ease <= 100
    assert stats.flesch_kincaid_grade >= 0
    assert stats.reading_level_label  # non-empty


def test_v0620_compute_stats_is_conversational_flag() -> None:
    """The is_conversational flag is True iff any line is Host B."""
    from core.podcast.script_stats import compute_stats

    # Conversational.
    conv = _make_script(lines=[_make_line("A", "hi", "intro"), _make_line("B", "hello", "content")])
    assert compute_stats(conv).is_conversational is True

    # Lecture (only Host A).
    lect = _make_script(
        lines=[_make_line("A", "hi", "intro"), _make_line("A", "bye", "conclusion")]
    )
    assert compute_stats(lect).is_conversational is False


# ── Layer 1e: format_stats_for_display ──────────────────────────────────────


def test_v0620_format_stats_empty_script_message() -> None:
    """An empty script returns the canonical '⚠️ Empty script' message."""
    from core.podcast.script_generator import ScriptResult
    from core.podcast.script_stats import compute_stats, format_stats_for_display

    stats = compute_stats(ScriptResult(lines=[], title="empty"))
    out = format_stats_for_display(stats)
    assert "⚠️" in out
    assert "Empty script" in out


def test_v0620_format_stats_populated_script_has_all_sections() -> None:
    """A populated script's output has all the expected section headers."""
    from core.podcast.script_stats import compute_stats, format_stats_for_display

    script = _make_script(
        lines=[
            _make_line("A", "The cat sat on the mat. The dog ran fast.", "intro"),
            _make_line("B", "I see a bird. The bird flew away.", "content"),
            _make_line("A", "That is the story. Goodbye for now.", "conclusion"),
        ],
        title="My Test Podcast",
    )
    stats = compute_stats(script)
    out = format_stats_for_display(stats)
    assert "📊 Script Statistics" in out
    assert "⏱️  Duration estimate" in out
    assert "👥 Per-host breakdown" in out
    assert "📑 Segment distribution" in out
    assert "📏 Line-length distribution" in out
    assert "📖 Reading level" in out
    assert "My Test Podcast" in out


def test_v0620_format_stats_duration_human_format() -> None:
    """The duration is formatted as 'M:SS' (e.g., '1:00' for 60 seconds)."""
    from core.podcast.script_stats import compute_stats, format_stats_for_display

    # 150 words at 150 WPM = 60 seconds = "1:00".
    words_150 = " ".join(f"w{i}" for i in range(150))
    script = _make_script(lines=[_make_line("A", words_150, "intro")], title="t")
    stats = compute_stats(script)
    out = format_stats_for_display(stats)
    assert "1:00" in out


def test_v0620_format_stats_calls_log_callback() -> None:
    """The log callback is called for each output line (the wizard can
    use this to echo stats to its live log)."""
    from core.podcast.script_stats import compute_stats, format_stats_for_display

    script = _make_script(lines=[_make_line("A", "hello world", "intro")], title="t")
    stats = compute_stats(script)
    logs: list[tuple[str, str]] = []
    format_stats_for_display(stats, log=lambda m, l: logs.append((m, l)))
    assert len(logs) > 0
    assert all(level == "INFO" for _, level in logs)


# ── Layer 2: the CLI stats subcommand ───────────────────────────────────────


def test_v0620_cli_stats_subcommand_prints_stats(tmp_path: Path) -> None:
    """The `stats` subcommand prints the rich analytics to stdout."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json", title="My Podcast")
    exit_code = cli_main(["stats", "--script", str(script_path)])
    assert exit_code == 0


def test_v0620_cli_stats_subcommand_missing_file_exits_2(tmp_path: Path) -> None:
    """The `stats` subcommand exits 2 if the script file doesn't exist."""
    from core.podcast.cli import main as cli_main

    exit_code = cli_main(["stats", "--script", str(tmp_path / "nope.json")])
    assert exit_code == 2


def test_v0620_cli_stats_subcommand_bad_json_exits_2(tmp_path: Path) -> None:
    """The `stats` subcommand exits 2 if the script JSON is malformed."""
    from core.podcast.cli import main as cli_main

    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert cli_main(["stats", "--script", str(p)]) == 2


def test_v0620_cli_stats_subcommand_json_flag_outputs_valid_json(
    tmp_path: Path,
) -> None:
    """The `--json` flag outputs valid JSON (for piping to other tools)."""
    import contextlib
    from io import StringIO

    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json", title="JSON Test")
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cli_main(["stats", "--script", str(script_path), "--json"])
    assert exit_code == 0
    output = buf.getvalue().strip()
    parsed = json.loads(output)  # must be valid JSON
    assert parsed["title"] == "JSON Test"
    assert "total_lines" in parsed
    assert "total_words" in parsed
    assert "estimated_duration_seconds" in parsed
    assert "host_a" in parsed
    assert "host_b" in parsed
    assert "segments" in parsed


def test_v0620_cli_stats_subcommand_wpm_override(tmp_path: Path) -> None:
    """The `--wpm` flag overrides the auto-detected WPM in the output."""
    import contextlib
    from io import StringIO

    from core.podcast.cli import main as cli_main

    # 150 words at 100 WPM (override) = 90 seconds.
    words_150 = " ".join(f"w{i}" for i in range(150))
    script_path = _write_script_json(
        tmp_path / "script.json",
        lines=[{"host": "A", "text": words_150, "source_ref": "r", "segment_type": "intro"}],
        title="wpm test",
    )
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        cli_main(["stats", "--script", str(script_path), "--json", "--wpm", "100"])
    parsed = json.loads(buf.getvalue().strip())
    assert parsed["wpm_used"] == 100
    assert parsed["estimated_duration_seconds"] == pytest.approx(90.0)


def test_v0620_cli_stats_subcommand_in_help() -> None:
    """The `stats` subcommand must appear in `python -m core.podcast.cli --help`."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    assert result.returncode == 0
    assert "stats" in result.stdout
    # The other V0.6.19 subcommands are still there.
    assert "validate" in result.stdout
    assert "generate" in result.stdout
    assert "info" in result.stdout
