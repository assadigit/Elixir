"""V0.6.19 — the encoding-cascade + script-validator + CLI batch pins.

This file pins the three V0.6.19 new-feature additions, against the
gaps the V0.6.18 worklog's "Unresolved" section named:

Layer 1 — the EXTENDED ENCODING CASCADE (W-e1):
  - ``_detect_encoding_with_chardet`` — high-confidence chardet
    detection (>=0.7 confidence, optional dep — returns None if
    chardet isn't installed).
  - ``_read_text_with_encoding_fallback`` — the V0.6.19 twelve-step
    cascade: utf-8-sig → utf-16 → utf-32 → utf-8 → chardet → cp1252 →
    shift_jis → euc_jp → euc_kr → gb18030 → big5 → latin-1. Closes
    the V0.6.18 worklog's LOW priority item #6 (Asian encodings
    previously fell through to latin-1 as garbage).

Layer 2 — the SCRIPT VALIDATOR (W-e2):
  - ``ValidationIssue`` / ``ValidationResult`` dataclasses with the
    ``.ok`` property (True iff no errors).
  - ``validate_script(script, host_a_voice, host_b_voice,
    is_conversational)`` — 9 rules across ERROR/WARNING/INFO:
    E1 empty script, E2 invalid host, E2b Host B in lecture mode,
    E3 empty line, E4 Host B voice empty in conversational mode,
    W1 script too long, W2 too short, W3 no intro, W4 no conclusion,
    W5 Host A voice empty, I1 empty title, I2 bullets force-inserted,
    I3 empty source_ref.
  - ``format_issues_for_display`` — the multi-line formatter for the
    wizard's status banner.

Layer 3 — the CLI (W-e3):
  - ``core.podcast.cli`` — the headless ``python -m core.podcast.cli``
    entry point with ``validate`` / ``generate`` / ``info`` subcommands.
    The ``generate`` subcommand wires up a ``CancelToken`` (V0.6.18
    W-d3) and a Ctrl-C signal handler that calls ``token.cancel()``;
    the line loop exits at the next iteration boundary.

All tests are pure-Python (no PySide6 / no torch / no soundfile
needed for layers 1-2; layer 3's CLI tests stub generate_podcast_audio
so no TTS runs).
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


# ── Layer 1: the extended encoding cascade ──────────────────────────────────


def test_v0619_chardet_detection_returns_none_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chardet detection step must return None (not raise) if chardet
    isn't installed — the cascade must work in a minimal venv."""
    # Force the chardet import to fail.
    import builtins

    from core.pipeline import multi_format_reader as mfr

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "chardet":
            raise ImportError("simulated: chardet not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    result = mfr._detect_encoding_with_chardet(b"hello world")
    assert result is None, "chardet detection must return None when chardet is missing"


def test_v0619_chardet_detection_returns_none_for_low_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chardet detection step must return None if chardet's confidence
    is below 0.7 — a low-confidence guess is worse than the cascade."""
    from core.pipeline import multi_format_reader as mfr

    class _FakeResult:
        encoding = "shift_jis"
        confidence = 0.4  # below 0.7 threshold

    class _FakeChardet:
        @staticmethod
        def detect(_raw):
            return {"encoding": "shift_jis", "confidence": 0.4}

    monkeypatch.setitem(sys.modules, "chardet", _FakeChardet)
    result = mfr._detect_encoding_with_chardet(b"some bytes")
    assert result is None, "low-confidence chardet result must be ignored"


def test_v0619_chardet_detection_returns_normalized_encoding_for_high_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A high-confidence chardet result must return the normalized
    encoding name (lowercased + aliased to Python's preferred form)."""
    from core.pipeline import multi_format_reader as mfr

    class _FakeChardet:
        @staticmethod
        def detect(_raw):
            return {"encoding": "SHIFT-JIS", "confidence": 0.99}

    monkeypatch.setitem(sys.modules, "chardet", _FakeChardet)
    result = mfr._detect_encoding_with_chardet(b"some bytes")
    assert result == "shift_jis", (
        f"chardet returned 'SHIFT-JIS' at 0.99 confidence; expected "
        f"normalization to 'shift_jis' (Python's codec name); got {result!r}"
    )


def test_v0619_chardet_detection_aliases_gb2312_to_gb18030(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chardet often detects GB2312 / GBK; both must be aliased to
    gb18030 (the superset) so the decode step uses the right codec."""
    from core.pipeline import multi_format_reader as mfr

    class _FakeChardet:
        @staticmethod
        def detect(_raw):
            return {"encoding": "GB2312", "confidence": 0.99}

    monkeypatch.setitem(sys.modules, "chardet", _FakeChardet)
    result = mfr._detect_encoding_with_chardet(b"some bytes")
    assert result == "gb18030"


def test_v0619_read_text_with_encoding_fallback_utf16_le_bom(tmp_path: Path) -> None:
    """A UTF-16-LE file with BOM (FF FE prefix) must decode correctly.
    The V0.6.18 cascade didn't try UTF-16 — it would have fallen through
    to latin-1 with garbage. V0.6.19 (W-e1) adds UTF-16 BOM detection."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "UTF-16 LE with BOM — em-dash — and accented chars éàü."
    p = tmp_path / "utf16le.txt"
    # UTF-16-LE with BOM: FF FE prefix + the UTF-16-LE-encoded bytes.
    p.write_bytes(b"\xff\xfe" + original.encode("utf-16-le"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original, f"UTF-16-LE with BOM must round-trip; got {result!r}"


def test_v0619_read_text_with_encoding_fallback_utf16_be_bom(tmp_path: Path) -> None:
    """A UTF-16-BE file with BOM (FE FF prefix) must decode correctly."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "UTF-16 BE with BOM — em-dash — and accented chars éàü."
    p = tmp_path / "utf16be.txt"
    # UTF-16-BE with BOM: FE FF prefix + the UTF-16-BE-encoded bytes.
    p.write_bytes(b"\xfe\xff" + original.encode("utf-16-be"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original


def test_v0619_read_text_with_encoding_fallback_shift_jis(tmp_path: Path) -> None:
    """A Shift-JIS-encoded .txt (Japanese Windows default) must decode
    correctly. Pre-V0.6.19 this would have "decoded" as cp1252 garbage
    (most Shift-JIS bytes are in 0x80-0xFF, all defined in cp1252).

    NOTE: shift_jis can't encode the Unicode em-dash (U+2014) — the JIS
    X 0208 character set has its own em-dash character (U+2015, the
    "fullwidth em-dash" / "horizontal bar") at 0x815C. We use a
    simple ASCII dash here to keep the test pure-Python and avoid
    codec-alias confusion (cp932 vs shift_jis on different OSes)."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "こんにちは、世界 - Hello World"
    p = tmp_path / "sjis.txt"
    p.write_bytes(original.encode("shift_jis"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original, (
        f"Shift-JIS must round-trip; got {result!r} (the V0.6.18 cascade "
        f"would have returned cp1252 garbage here)."
    )


def test_v0619_read_text_with_encoding_fallback_gb18030(tmp_path: Path) -> None:
    """A GB18030-encoded .txt (Simplified Chinese) must decode correctly.
    GB18030 is the superset of GBK / GB2312 — covers Mainland Chinese.

    NOTE: the test string is long enough for chardet to detect (>= 0.7
    confidence) — chardet returns GB2312 at 0.99 confidence for ~80+
    non-ASCII bytes, which the cascade aliases to gb18030 (the superset).
    Shorter strings leave chardet at 0.0 confidence, and the permissive
    Asian cascade would mis-decode them (euc_jp "succeeds" on GB18030
    bytes as Japanese garbage before reaching gb18030). Real-world .txt
    files are 100s of bytes — the chardet path handles them; the test
    uses a realistic length to pin that."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = (
        "你好，世界 — Hello World. 这是一段中文文本，用来测试编码检测。"
        "光影如梭，岁月如歌。山川异域，风月同天。"
    )
    p = tmp_path / "gb18030.txt"
    p.write_bytes(original.encode("gb18030"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original


def test_v0619_read_text_with_encoding_fallback_big5(tmp_path: Path) -> None:
    """A Big5-encoded .txt (Traditional Chinese, Taiwan/HK) must decode."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "你好，世界 — Hello World"
    p = tmp_path / "big5.txt"
    p.write_bytes(original.encode("big5"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original


def test_v0619_read_text_with_encoding_fallback_euc_kr(tmp_path: Path) -> None:
    """An EUC-KR-encoded .txt (Korean, Unix-locale default) must decode.

    NOTE: euc_kr can't encode the Unicode em-dash (U+2014) — Korean's
    typographic dash is a different character. Use ASCII dash here."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "안녕하세요, 세계 - Hello World"
    p = tmp_path / "euckr.txt"
    p.write_bytes(original.encode("euc_kr"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original


def test_v0619_read_text_with_encoding_fallback_v0618_regression_western(
    tmp_path: Path,
) -> None:
    """The V0.6.19 cascade must NOT regress the V0.6.18 Western cases —
    UTF-8, UTF-8-BOM, cp1252, and pure-ASCII still round-trip correctly."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    # UTF-8
    utf8_text = "Modern UTF-8 — em-dash — and accented chars éàü."
    p1 = tmp_path / "utf8.txt"
    p1.write_bytes(utf8_text.encode("utf-8"))
    assert _read_text_with_encoding_fallback(p1) == utf8_text

    # UTF-8 with BOM
    p2 = tmp_path / "utf8bom.txt"
    p2.write_bytes(b"\xef\xbb\xbf" + utf8_text.encode("utf-8"))
    assert _read_text_with_encoding_fallback(p2) == utf8_text

    # cp1252 (Windows ANSI)
    cp1252_text = "It\N{RIGHT SINGLE QUOTATION MARK}s Windows \N{LEFT DOUBLE QUOTATION MARK}ANSI\N{RIGHT DOUBLE QUOTATION MARK} \N{EM DASH} \N{LATIN SMALL LETTER E WITH ACUTE}."
    p3 = tmp_path / "ansi.txt"
    p3.write_bytes(cp1252_text.encode("cp1252"))
    assert _read_text_with_encoding_fallback(p3) == cp1252_text

    # Pure ASCII
    p4 = tmp_path / "ascii.txt"
    p4.write_bytes(b"Plain ASCII - no surprises.")
    assert _read_text_with_encoding_fallback(p4) == "Plain ASCII - no surprises."


def test_v0619_read_text_with_encoding_fallback_garbage_never_raises(
    tmp_path: Path,
) -> None:
    """Garbage bytes that aren't valid in any encoding must STILL not raise
    — the latin-1 catch-all (step 12) handles them.

    NOTE: this test uses bytes that START with 0xFF 0xFE which IS the
    UTF-16-LE BOM — so the cascade's step 3 (UTF-16 BOM detection)
    would try to decode it as UTF-16-LE first. The 0x80 0x81 0x97 bytes
    don't form valid UTF-16-LE pairs, so it raises and falls through.
    The cascade MUST eventually reach the latin-1 catch-all (step 12)
    and return a string (even if garbage) — the function NEVER raises."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    p = tmp_path / "garbage.txt"
    # 0xff 0xfe is the UTF-16-LE BOM; the remaining bytes (0x80 0x81 0x97
    # Some text) don't form valid UTF-16-LE pairs (0x9780 is a CJK char,
    # but the next pair would be '  ' then 'Te' etc — mixed ASCII).
    # The cascade should fail UTF-16 (BOM detection step 3) and reach
    # latin-1 (step 12) which always succeeds.
    p.write_bytes(b"\xff\xfe\x80\x81\x97Some text")
    result = _read_text_with_encoding_fallback(p)
    # The function must NOT raise. The result is garbage but readable.
    assert isinstance(result, str)


# ── Layer 2: the script validator ────────────────────────────────────────────


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


def test_v0619_validate_script_clean_script_passes() -> None:
    """A clean script (3 lines, intro+conclusion, both voices set) must
    pass with zero errors."""
    from core.podcast.script_validator import validate_script

    script = _make_script()
    result = validate_script(
        script,
        host_a_voice="vibevoice:Carter",
        host_b_voice="vibevoice:Erin",
        is_conversational=True,
    )
    assert result.ok, f"clean script must pass; got issues: {result.issues}"
    assert result.errors == []


def test_v0619_validate_script_empty_script_blocks() -> None:
    """E1: an empty script (zero lines) must be an ERROR, and the
    validator must short-circuit (no per-line checks run)."""
    from core.podcast.script_validator import SEVERITY_ERROR, validate_script

    script = _make_script(lines=[], title="empty")
    result = validate_script(script)
    assert not result.ok
    assert len(result.errors) == 1
    assert result.errors[0].code == "E1_EMPTY_SCRIPT"
    assert result.errors[0].severity == SEVERITY_ERROR
    # Short-circuit: no per-line checks ran, so no warnings either.
    assert result.warnings == []


def test_v0619_validate_script_invalid_host_blocks() -> None:
    """E2: a line with host='C' (or any non-A/B value) must be an ERROR
    naming the offending line index."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("C", "line 2 (bad host)", "content"),
            _make_line("A", "line 3", "conclusion"),
        ]
    )
    result = validate_script(script, host_a_voice="vibevoice:Carter", host_b_voice="vibevoice:Erin")
    assert not result.ok
    e2 = [e for e in result.errors if e.code == "E2_INVALID_HOST"]
    assert len(e2) == 1
    assert e2[0].line_index == 1  # 0-based


def test_v0619_validate_script_host_b_in_lecture_mode_blocks() -> None:
    """E2b: a Host B line in lecture (1-host) mode is an ERROR — the
    audio generator would silently assign Host A's voice to it."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "intro", "intro"),
            _make_line("B", "this should be an error in lecture mode", "content"),
            _make_line("A", "conclusion", "conclusion"),
        ]
    )
    result = validate_script(
        script, host_a_voice="voice_a", host_b_voice="", is_conversational=False
    )
    assert not result.ok
    e2b = [e for e in result.errors if e.code == "E2_HOST_B_IN_LECTURE_MODE"]
    assert len(e2b) == 1
    assert e2b[0].line_index == 1


def test_v0619_validate_script_empty_line_blocks() -> None:
    """E3: a line with empty text (no cues either) is an ERROR — TTS
    would receive "" and crash or produce a 0-byte WAV."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "intro", "intro"),
            _make_line("A", "", "content"),  # empty text
            _make_line("A", "conclusion", "conclusion"),
        ]
    )
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    assert not result.ok
    e3 = [e for e in result.errors if e.code == "E3_EMPTY_LINE"]
    assert len(e3) == 1
    assert e3[0].line_index == 1


def test_v0619_validate_script_host_b_voice_empty_in_conversational_blocks() -> None:
    """E4: a conversational script with Host B lines but no Host B voice
    is an ERROR — the engine's `or "af_heart"` fallback would patch
    this SILENTLY; the validator makes it explicit."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "intro", "intro"),
            _make_line("B", "body from host b", "content"),
            _make_line("A", "conclusion", "conclusion"),
        ]
    )
    result = validate_script(
        script, host_a_voice="voice_a", host_b_voice="", is_conversational=True
    )
    assert not result.ok
    e4 = [e for e in result.errors if e.code == "E4_HOST_B_VOICE_EMPTY"]
    assert len(e4) == 1


def test_v0619_validate_script_too_long_warns() -> None:
    """W1: a script with > 50 lines must WARN about generation time."""
    from core.podcast.script_generator import ScriptLine, ScriptResult
    from core.podcast.script_validator import MAX_REASONABLE_LINE_COUNT, validate_script

    lines = [
        ScriptLine(host="A", text=f"line {i}", source_ref="ref", segment_type="content")
        for i in range(MAX_REASONABLE_LINE_COUNT + 10)
    ]
    script = ScriptResult(lines=lines, title="long")
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    assert result.ok, "long script must NOT block (warning only)"
    w1 = [w for w in result.warnings if w.code == "W1_SCRIPT_TOO_LONG"]
    assert len(w1) == 1


def test_v0619_validate_script_too_short_warns() -> None:
    """W2: a script with < 3 lines must WARN about likely over-editing."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[_make_line("A", "only one line", "intro")],
        title="short",
    )
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    assert result.ok
    w2 = [w for w in result.warnings if w.code == "W2_SCRIPT_TOO_SHORT"]
    assert len(w2) == 1


def test_v0619_validate_script_no_intro_warns() -> None:
    """W3: a script whose first line isn't tagged 'intro' must WARN."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "not an intro", "content"),  # not intro
            _make_line("A", "conclusion", "conclusion"),
        ],
        title="no-intro",
    )
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    w3 = [w for w in result.warnings if w.code == "W3_NO_INTRO"]
    assert len(w3) == 1


def test_v0619_validate_script_no_conclusion_warns() -> None:
    """W4: a script whose last line isn't tagged 'conclusion' must WARN."""
    from core.podcast.script_validator import validate_script

    script = _make_script(
        lines=[
            _make_line("A", "intro", "intro"),
            _make_line("A", "not a conclusion", "content"),  # not conclusion
        ],
        title="no-conclusion",
    )
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    w4 = [w for w in result.warnings if w.code == "W4_NO_CONCLUSION"]
    assert len(w4) == 1


def test_v0619_validate_script_host_a_voice_empty_warns() -> None:
    """W5: an empty Host A voice must WARN (lecture mode tolerates it
    via Kokoro 'af_heart' fallback, but the user should know)."""
    from core.podcast.script_validator import validate_script

    script = _make_script()
    result = validate_script(script, host_a_voice="", host_b_voice="voice_b")
    w5 = [w for w in result.warnings if w.code == "W5_HOST_A_VOICE_EMPTY"]
    assert len(w5) == 1


def test_v0619_validate_script_empty_title_is_info() -> None:
    """I1: an empty title is INFO (not a warning or error) — the audio
    file will just be saved with a timestamp name."""
    from core.podcast.script_validator import SEVERITY_INFO, validate_script

    script = _make_script(title="")
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    i1 = [i for i in result.infos if i.code == "I1_EMPTY_TITLE"]
    assert len(i1) == 1
    assert i1[0].severity == SEVERITY_INFO


def test_v0619_validate_script_force_inserted_bullets_is_info() -> None:
    """I2: a script whose bullets_missing > 0 must INFO that the
    anti-hallucination system force-inserted those bullets."""
    from core.podcast.script_generator import ScriptResult
    from core.podcast.script_validator import validate_script

    script = ScriptResult(
        lines=[
            _make_line("A", "line 1", "intro"),
            _make_line("A", "line 2", "content"),
            _make_line("A", "line 3", "conclusion"),
        ],
        bullets_input=["b1", "b2", "b3"],
        bullets_covered=[0, 1],
        bullets_missing=[2],
        coverage_pct=66.6,
        title="test",
    )
    result = validate_script(script, host_a_voice="voice_a", host_b_voice="voice_b")
    i2 = [i for i in result.infos if i.code == "I2_BULLETS_FORCE_INSERTED"]
    assert len(i2) == 1
    assert "1 of 3" in i2[0].message


def test_v0619_validate_result_ok_property_and_bool() -> None:
    """The .ok property is True iff no errors; bool(result) follows .ok."""
    from core.podcast.script_validator import (
        SEVERITY_ERROR,
        SEVERITY_INFO,
        SEVERITY_WARNING,
        ValidationIssue,
        ValidationResult,
    )

    clean = ValidationResult(issues=[])
    assert clean.ok is True
    assert bool(clean) is True

    with_warning = ValidationResult(
        issues=[
            ValidationIssue(SEVERITY_WARNING, "W1", "warn"),
            ValidationIssue(SEVERITY_INFO, "I1", "info"),
        ]
    )
    assert with_warning.ok is True, "warnings don't block; .ok must be True"
    assert bool(with_warning) is True

    with_error = ValidationResult(
        issues=[
            ValidationIssue(SEVERITY_ERROR, "E1", "err"),
            ValidationIssue(SEVERITY_WARNING, "W1", "warn"),
        ]
    )
    assert with_error.ok is False
    assert bool(with_error) is False
    assert len(with_error.errors) == 1
    assert len(with_error.warnings) == 1


def test_v0619_validation_issue_rejects_bad_severity() -> None:
    """ValidationIssue must reject severity values outside the canonical
    three (error/warning/info) — a typo here would silently break the
    wizard's severity-filtering logic."""
    from core.podcast.script_validator import ValidationIssue

    with pytest.raises(ValueError, match="severity"):
        ValidationIssue(severity="critical", code="X", message="bad")  # type: ignore[arg-type]


def test_v0619_format_issues_for_display_clean_message() -> None:
    """A clean result prints the canonical '✅ No issues found' message."""
    from core.podcast.script_validator import (
        ValidationResult,
        format_issues_for_display,
    )

    logs: list[tuple[str, str]] = []
    out = format_issues_for_display(
        ValidationResult(issues=[]), log=lambda m, l: logs.append((m, l))
    )
    assert "✅" in out
    assert "ready to generate" in out


def test_v0619_format_issues_for_display_groups_by_severity() -> None:
    """The display format groups issues by severity (ERROR first, then
    WARNING, then INFO) with counts and code prefixes."""
    from core.podcast.script_validator import (
        SEVERITY_ERROR,
        SEVERITY_INFO,
        SEVERITY_WARNING,
        ValidationIssue,
        ValidationResult,
        format_issues_for_display,
    )

    result = ValidationResult(
        issues=[
            ValidationIssue(SEVERITY_ERROR, "E1", "the error"),
            ValidationIssue(SEVERITY_WARNING, "W1", "the warning"),
            ValidationIssue(SEVERITY_INFO, "I1", "the info"),
        ]
    )
    out = format_issues_for_display(result)
    assert "ERROR (1):" in out
    assert "WARNING (1):" in out
    assert "INFO (1):" in out
    assert "[E1] the error" in out
    assert "[W1] the warning" in out
    assert "[I1] the info" in out


# ── Layer 3: the CLI ─────────────────────────────────────────────────────────


def _write_script_json(
    path: Path,
    lines: list[dict] | None = None,
    title: str = "test",
    bullets_input: list[str] | None = None,
    bullets_covered: list[int] | None = None,
    bullets_missing: list[int] | None = None,
    coverage_pct: float = 100.0,
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
        "bullets_input": bullets_input or [],
        "bullets_covered": bullets_covered or [],
        "bullets_missing": bullets_missing or [],
        "coverage_pct": coverage_pct,
        "retries": 0,
        "forced_segments": 0,
        "error": None,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_v0619_cli_info_subcommand_prints_metadata(tmp_path: Path) -> None:
    """The `info` subcommand prints the script's metadata without
    validating or generating — exits 0 on a valid JSON."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    exit_code = cli_main(["info", "--script", str(script_path)])
    assert exit_code == 0


def test_v0619_cli_info_missing_file_exits_2(tmp_path: Path) -> None:
    """The `info` subcommand exits 2 if the script file doesn't exist."""
    from core.podcast.cli import main as cli_main

    exit_code = cli_main(["info", "--script", str(tmp_path / "does_not_exist.json")])
    assert exit_code == 2


def test_v0619_cli_info_bad_json_exits_2(tmp_path: Path) -> None:
    """The `info` subcommand exits 2 if the script JSON is malformed."""
    from core.podcast.cli import main as cli_main

    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    exit_code = cli_main(["info", "--script", str(p)])
    assert exit_code == 2


def test_v0619_cli_validate_subcommand_clean_script_exits_0(tmp_path: Path) -> None:
    """The `validate` subcommand exits 0 on a clean script."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(tmp_path / "script.json")
    exit_code = cli_main(
        [
            "validate",
            "--script",
            str(script_path),
            "--voice-a",
            "vibevoice:Carter",
            "--voice-b",
            "vibevoice:Erin",
        ]
    )
    assert exit_code == 0


def test_v0619_cli_validate_subcommand_invalid_host_exits_1(tmp_path: Path) -> None:
    """The `validate` subcommand exits 1 when there's an ERROR-level
    issue (e.g., an invalid host value)."""
    from core.podcast.cli import main as cli_main

    script_path = _write_script_json(
        tmp_path / "script.json",
        lines=[
            {"host": "A", "text": "intro", "source_ref": "r", "segment_type": "intro"},
            {"host": "C", "text": "bad host", "source_ref": "r", "segment_type": "content"},
            {"host": "A", "text": "outro", "source_ref": "r", "segment_type": "conclusion"},
        ],
    )
    exit_code = cli_main(
        ["validate", "--script", str(script_path), "--voice-a", "va", "--voice-b", "vb"]
    )
    assert exit_code == 1


def test_v0619_cli_validate_strict_makes_warnings_fatal(tmp_path: Path) -> None:
    """The `--strict` flag on `validate` makes warnings exit 1 (vs 0
    without the flag). Triggered by a too-long script (W1)."""
    from core.podcast.cli import main as cli_main
    from core.podcast.script_validator import MAX_REASONABLE_LINE_COUNT

    lines = [
        {"host": "A", "text": f"line {i}", "source_ref": "r", "segment_type": "content"}
        for i in range(MAX_REASONABLE_LINE_COUNT + 5)
    ]
    script_path = _write_script_json(tmp_path / "long.json", lines=lines, title="long")
    # Without --strict: warnings don't block → exit 0.
    assert (
        cli_main(["validate", "--script", str(script_path), "--voice-a", "va", "--voice-b", "vb"])
        == 0
    )
    # With --strict: warnings ARE fatal → exit 1.
    assert (
        cli_main(
            [
                "validate",
                "--script",
                str(script_path),
                "--voice-a",
                "va",
                "--voice-b",
                "vb",
                "--strict",
            ]
        )
        == 1
    )


def test_v0619_cli_generate_subcommand_validates_first_then_calls_audio_gen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `generate` subcommand must call validate_script FIRST; if
    validation fails (an ERROR), it must NOT call generate_podcast_audio
    at all (no TTS subprocess spin-up)."""
    from core.podcast import audio_generator as audio_mod
    from core.podcast.cli import main as cli_main

    audio_calls = {"n": 0}

    def _fake_generate(*args, **kwargs):  # noqa: ANN001
        audio_calls["n"] += 1
        return None

    # The CLI does a deferred import (`from core.podcast.audio_generator
    # import generate_podcast_audio` inside _cmd_generate), so the lookup
    # goes through the audio_generator module — monkeypatch THERE.
    monkeypatch.setattr(audio_mod, "generate_podcast_audio", _fake_generate)

    script_path = _write_script_json(
        tmp_path / "bad.json",
        lines=[
            {"host": "A", "text": "intro", "source_ref": "r", "segment_type": "intro"},
            {"host": "X", "text": "bad host", "source_ref": "r", "segment_type": "content"},
        ],
    )
    exit_code = cli_main(
        [
            "generate",
            "--script",
            str(script_path),
            "--voice-a",
            "va",
            "--voice-b",
            "vb",
            "--out",
            str(tmp_path / "out.wav"),
        ]
    )
    assert exit_code == 1, "validation error must abort generation"
    assert audio_calls["n"] == 0, "generate_podcast_audio must NOT be called when validation fails"


def test_v0619_cli_generate_subcommand_passes_cancel_token_to_audio_gen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `generate` subcommand must pass a CancelToken to
    generate_podcast_audio (the V0.6.18 W-d3 contract)."""
    from core.podcast import audio_generator as audio_mod
    from core.podcast.cancel_token import CancelToken
    from core.podcast.cli import main as cli_main

    captured: dict = {}

    def _fake_generate(*args, **kwargs):  # noqa: ANN001
        captured["cancel_token"] = kwargs.get("cancel_token")
        return None

    # The CLI does a deferred import — monkeypatch on the source module.
    monkeypatch.setattr(audio_mod, "generate_podcast_audio", _fake_generate)

    script_path = _write_script_json(tmp_path / "script.json")
    cli_main(
        [
            "generate",
            "--script",
            str(script_path),
            "--voice-a",
            "va",
            "--voice-b",
            "vb",
            "--out",
            str(tmp_path / "out.wav"),
        ]
    )
    token = captured.get("cancel_token")
    assert isinstance(token, CancelToken), (
        f"generate must pass a CancelToken; got {type(token).__name__}"
    )
    assert token.cancelled is False, "token must start un-cancelled"


def test_v0619_cli_module_invocable_via_python_m() -> None:
    """The CLI must be invocable as ``python -m core.podcast.cli`` (the
    __main__ block must work) — runs ``--help`` and checks the exit code
    is 0 (argparse exits 0 on --help)."""
    result = subprocess.run(
        [sys.executable, "-m", "core.podcast.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=_project_root,
    )
    # argparse exits 0 on --help, prints usage to stdout.
    assert result.returncode == 0
    assert "validate" in result.stdout
    assert "generate" in result.stdout
    assert "info" in result.stdout
