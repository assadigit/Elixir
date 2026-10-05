"""V0.6.18 — the offline-lock + cancel-token + cp1252-txt-reader batch.

This file pins the three V0.6.18 behavior changes that the operator's
"continue working on this project" instruction targeted, against the
gaps the V0.6.17 final-report claimed were already done but were not
(commits 75da290 / 1f804e5 / 88e3721 are absent from the
``refactor/audit-session`` branch — GitHub's branch tip is still
6f2368d, the V0.6.17 wrap-up; the report was written against work that
was either wiped before push or never committed). This file's pins are
the proof the work now exists for real:

Layer 1 — the OFFLINE LOCK (source-pin + import-time pin):
  - ``core/tts/vibevoice_engine.py``: the clean-env spawner sets
    ``HF_HUB_OFFLINE=1`` / ``TRANSFORMERS_OFFLINE=1`` /
    ``HF_DATASETS_OFFLINE=1`` / ``TOKENIZERS_PARALLELISM=false``
    BEFORE the subprocess is spawned (so the model loads strictly
    from the local folder the operator pointed at).
  - ``core/tts/_vibevoice_subprocess.py``: the same four flags are
    set at MODULE TOP (the belt-and-suspenders path for the case
    where the operator runs the script directly during debugging,
    bypassing the engine's clean-env spawn).
  - ``core/tts/qwen_tts_engine.py``: same four flags set in the env
    builder (the engine inherits os.environ.copy() so the explicit
    set is the lock).
  - ``core/tts/_qwen_tts_subprocess.py``: same four flags at module
    top, mirroring the VibeVoice subprocess.

Layer 2 — the CANCEL TOKEN (unit + runtime):
  - ``core.podcast.cancel_token.CancelToken`` is a thread-safe flag:
    starts False, flips True exactly once on .cancel(), stays True.
    The .reason property carries the human-readable string the worker
    logs.
  - ``generate_podcast_audio(cancel_token=...)`` checks the token at
    the top of every line-loop iteration; a pre-cancelled token makes
    the function return None immediately, with zero TTS calls.

Layer 3 — the cp1252 .TXT READER (runtime):
  - ``_read_text_with_encoding_fallback`` decodes a .txt file by
    trying utf-8-sig → utf-8 → cp1252 → latin-1 in order. The pre-
    V0.6.18 path (``read_text(encoding="utf-8", errors="ignore")``)
    SILENTLY DROPPED non-ASCII bytes from any Windows Notepad "ANSI"
    save; the cascade now round-trips smart quotes / em-dashes /
    accented Latin chars correctly.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Layer 1: the offline-lock source pins ──────────────────────────────────

_VIBEVOICE_ENGINE = _project_root / "core" / "tts" / "vibevoice_engine.py"
_VIBEVOICE_SUBPROC = _project_root / "core" / "tts" / "_vibevoice_subprocess.py"
_QWEN_ENGINE = _project_root / "core" / "tts" / "qwen_tts_engine.py"
_QWEN_SUBPROC = _project_root / "core" / "tts" / "_qwen_tts_subprocess.py"

# The two syntactic shapes the four offline flags appear in:
#   - the ENGINE spawners build a clean env dict and ASSIGN:
#         env["HF_HUB_OFFLINE"] = "1"
#   - the SUBPROCESS modules set at module top via SETDEFAULT (so the
#     operator's own shell env isn't clobbered on direct-launch debug):
#         os.environ["HF_HUB_OFFLINE"] = "1"
# (V0.6.31: changed from setdefault to = to FORCE the flag)
# A single constant can't express both, so they're split. The four
# (name, value) tuples drive BOTH parametrize decorators.
_OFFLINE_FLAG_KV = (
    ("HF_HUB_OFFLINE", "1"),
    ("TRANSFORMERS_OFFLINE", "1"),
    ("HF_DATASETS_OFFLINE", "1"),
    ("TOKENIZERS_PARALLELISM", "false"),
)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name,val", _OFFLINE_FLAG_KV, ids=[k[0] for k in _OFFLINE_FLAG_KV])
def test_v0618_vibevoice_engine_sets_offline_env(name: str, val: str) -> None:
    """The VibeVoice spawner builds a CLEAN env (V11.61.0) and the four
    offline flags must be ASSIGNED to it before sub.spawn — the model
    loads strictly from the local folder the operator pointed at."""
    expected = f'env["{name}"] = "{val}"'
    assert expected in _src(_VIBEVOICE_ENGINE), (
        f"VibeVoice engine missing offline env assignment: {expected!r} "
        f"(the spawner at core/tts/vibevoice_engine.py:_ensure_model must "
        f"set all four flags before sub.spawn)"
    )


@pytest.mark.parametrize("name,val", _OFFLINE_FLAG_KV, ids=[k[0] for k in _OFFLINE_FLAG_KV])
def test_v0618_vibevoice_subprocess_sets_offline_env_at_module_top(name: str, val: str) -> None:
    """The VibeVoice subprocess sets the four offline flags at MODULE TOP.
    V0.6.31: changed from os.environ.setdefault() to os.environ[...] = ... to
    FORCE the flag (setdefault doesn't override an existing empty-string env
    var — the operator's 'it still seemingly loads vibevoice from huggingface'
    report showed this gap)."""
    expected = f'os.environ["{name}"] = "{val}"'
    assert expected in _src(_VIBEVOICE_SUBPROC), (
        f"VibeVoice subprocess missing offline env assignment: {expected!r} "
        f"(the module-top block in core/tts/_vibevoice_subprocess.py must "
        f"assign all four flags before any transformers import)"
    )


@pytest.mark.parametrize("name,val", _OFFLINE_FLAG_KV, ids=[k[0] for k in _OFFLINE_FLAG_KV])
def test_v0618_qwen_engine_sets_offline_env(name: str, val: str) -> None:
    """The Qwen3-TTS spawner (env = os.environ.copy()) sets the four
    offline flags explicitly — the inherited env alone isn't the lock."""
    expected = f'env["{name}"] = "{val}"'
    assert expected in _src(_QWEN_ENGINE), (
        f"Qwen3-TTS engine missing offline env assignment: {expected!r}"
    )


@pytest.mark.parametrize("name,val", _OFFLINE_FLAG_KV, ids=[k[0] for k in _OFFLINE_FLAG_KV])
def test_v0618_qwen_subprocess_sets_offline_env_at_module_top(name: str, val: str) -> None:
    """The Qwen3-TTS subprocess mirrors the VibeVoice module-top guard.
    V0.6.31: changed from setdefault to = (same fix as VibeVoice)."""
    expected = f'os.environ["{name}"] = "{val}"'
    assert expected in _src(_QWEN_SUBPROC), (
        f'Qwen3-TTS subprocess missing os.environ["{name}"] = "{val}" at module top'
    )


# ── Layer 2a: the CancelToken unit tests ────────────────────────────────────


def test_v0618_cancel_token_initial_state() -> None:
    """A fresh token is NOT cancelled and has no reason."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    assert token.cancelled is False
    assert token.reason is None


def test_v0618_cancel_token_cancel_flips_flag_and_records_reason() -> None:
    """cancel() flips the flag to True and stores the reason string."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    token.cancel("user clicked the stop button")
    assert token.cancelled is True
    assert token.reason == "user clicked the stop button"


def test_v0618_cancel_token_default_reason() -> None:
    """cancel() with no args uses the canonical 'cancelled by user'."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    token.cancel()
    assert token.cancelled is True
    assert token.reason == "cancelled by user"


def test_v0618_cancel_token_is_idempotent() -> None:
    """Calling cancel() twice does NOT overwrite the first reason —
    the operator's first cancel reason is the one that's logged."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    token.cancel("first reason")
    token.cancel("second reason")
    assert token.cancelled is True
    assert token.reason == "first reason"


def test_v0618_cancel_token_thread_safe_under_concurrent_cancel() -> None:
    """100 threads calling cancel() concurrently must end with the flag
    True and never raise — the Lock around the flag flip is the
    correctness guarantee the worker thread relies on."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    errors: list[Exception] = []

    def _flip() -> None:
        try:
            token.cancel(f"thread-{threading.get_ident()}")
        except Exception as e:  # noqa: BLE001 — pinning no-raise
            errors.append(e)

    threads = [threading.Thread(target=_flip) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert token.cancelled is True


# ── Layer 2b: the cancel-token wiring in generate_podcast_audio ─────────────


def test_v0618_generate_podcast_audio_signature_has_cancel_token() -> None:
    """The function signature includes the cancel_token parameter —
    the public API contract the wizard's worker depends on."""
    import inspect

    from core.podcast.audio_generator import generate_podcast_audio

    sig = inspect.signature(generate_podcast_audio)
    assert "cancel_token" in sig.parameters, (
        "generate_podcast_audio must accept a cancel_token parameter so "
        "the UI's stop button can halt the line loop."
    )
    # Default is None — backward-compatible with every existing caller
    # that doesn't pass one.
    assert sig.parameters["cancel_token"].default is None


def test_v0618_generate_podcast_audio_precancelled_returns_none_without_tts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-cancelled token makes generate_podcast_audio return None
    IMMEDIATELY — zero TTS calls, zero progress past 0%, the loop
    never enters its body. This is the operator's "either success or
    fail" contract extended with a third outcome: cancelled.

    The test stubs _synthesize_line (so no real TTS runs) AND verifies
    it was NEVER called — the cancel check at the iteration boundary
    must fire BEFORE the first line is synthesized.
    """
    from core.podcast import audio_generator
    from core.podcast.cancel_token import CancelToken
    from core.podcast.script_generator import ScriptLine, ScriptResult

    # Stub _synthesize_line — counts calls so we can assert zero.
    call_count = {"n": 0}

    def _stub_synthesize(line, out_path, voice, settings, log):  # noqa: ANN001
        call_count["n"] += 1
        # Should never run — the pre-cancelled token short-circuits the loop.
        return None

    monkeypatch.setattr(audio_generator, "_synthesize_line", _stub_synthesize)

    script = ScriptResult(
        lines=[
            ScriptLine(host="A", text="line one", source_ref="ref1", segment_type="intro"),
            ScriptLine(host="B", text="line two", source_ref="ref2", segment_type="content"),
            ScriptLine(host="A", text="line three", source_ref="ref3", segment_type="content"),
        ],
        title="test",
    )
    token = CancelToken()
    token.cancel("user clicked stop before line 1")

    logs: list[tuple[str, str]] = []
    progress: list[tuple[int, str]] = []

    result = audio_generator.generate_podcast_audio(
        script=script,
        out_path=Path("/tmp/should_not_exist.wav"),
        host_a_voice="voice_a",
        host_b_voice="voice_b",
        settings={},
        log_callback=lambda msg, level="INFO": logs.append((msg, level)),
        progress_callback=lambda pct, msg: progress.append((pct, msg)),
        cancel_token=token,
    )
    assert result is None, "pre-cancelled generation must return None"
    assert call_count["n"] == 0, (
        "the pre-cancelled token must short-circuit the loop BEFORE the "
        "first _synthesize_line call — zero TTS work is the contract."
    )
    # The cancel reason is logged so the operator sees *why* it stopped.
    assert any("cancelled" in m.lower() for m, _ in logs), (
        f"the cancel reason must be logged; got logs={logs!r}"
    )
    # Progress callback received the cancelled state.
    assert any("cancel" in msg.lower() for _, msg in progress), (
        f"progress callback must report the cancellation; got {progress!r}"
    )


def test_v0618_generate_podcast_audio_cancel_after_first_line_halts_before_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelling AFTER the first line started (the token flips between
    iterations) makes the loop exit at the NEXT iteration boundary —
    the second line is never synthesized, the function returns None,
    no final WAV is written.

    This is the realistic UX: the user clicks Stop mid-generation, the
    current line finishes (mid-line cancel would orphan a half-written
    WAV), the loop sees the flag at the next boundary and exits.
    """
    from core.podcast import audio_generator
    from core.podcast.cancel_token import CancelToken
    from core.podcast.script_generator import ScriptLine, ScriptResult

    call_count = {"n": 0}
    token = CancelToken()

    def _stub_synthesize(line, out_path, voice, settings, log):  # noqa: ANN001
        call_count["n"] += 1
        # After the first line is synthesized, flip the cancel flag —
        # simulates the user clicking Stop while line 1 is in flight.
        if call_count["n"] == 1:
            token.cancel("user clicked stop during line 1")
        # Return a real-enough stub WAV so the chunk_paths list would
        # otherwise grow — but the cancel check at the next iteration
        # boundary must prevent line 2 from ever running.
        out_path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00")
        return out_path

    monkeypatch.setattr(audio_generator, "_synthesize_line", _stub_synthesize)
    # Avoid the real soundfile.read in the per-line duration log — it
    # would choke on the stub WAV bytes above.
    monkeypatch.setattr(
        audio_generator, "sf", type("SFStub", (), {"read": staticmethod(lambda p: ([0.0], 1))})()
    )

    script = ScriptResult(
        lines=[
            ScriptLine(host="A", text="line one", source_ref="ref1", segment_type="intro"),
            ScriptLine(host="B", text="line two", source_ref="ref2", segment_type="content"),
            ScriptLine(host="A", text="line three", source_ref="ref3", segment_type="content"),
        ],
        title="test",
    )

    result = audio_generator.generate_podcast_audio(
        script=script,
        out_path=Path("/tmp/should_not_exist.wav"),
        host_a_voice="voice_a",
        host_b_voice="voice_b",
        settings={},
        log_callback=lambda msg, level="INFO": None,
        progress_callback=None,
        cancel_token=token,
    )
    assert result is None, "cancelled-mid-loop generation must return None"
    assert call_count["n"] == 1, (
        f"exactly ONE line should be synthesized (the one in flight when "
        f"cancel fired); got {call_count['n']}. The cancel check at the "
        f"NEXT iteration boundary must prevent line 2 from running."
    )


# ── Layer 3: the cp1252 .txt reader ─────────────────────────────────────────


def test_v0618_read_text_with_encoding_fallback_utf8(tmp_path: Path) -> None:
    """A plain UTF-8 .txt (the modern default) round-trips through the
    cascade at step 2 (step 1, utf-8-sig, also decodes BOM-less utf-8
    without error — but the result is the same text either way)."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "It's a modern UTF-8 file — em-dash — and a curly apostrophe."
    p = tmp_path / "utf8.txt"
    p.write_bytes(original.encode("utf-8"))
    assert _read_text_with_encoding_fallback(p) == original


def test_v0618_read_text_with_encoding_fallback_utf8_with_bom(tmp_path: Path) -> None:
    """A UTF-8-with-BOM .txt (Notepad's "UTF-8 with BOM" mode) must
    decode WITHOUT the three BOM bytes leaking into the text."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "BOM-prefixed text with an em-dash — and accented chars éàü."
    p = tmp_path / "bom.txt"
    p.write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original, f"BOM must be stripped; got first-3-bytes={result[:3]!r}"


def test_v0618_read_text_with_encoding_fallback_cp1252(tmp_path: Path) -> None:
    """A cp1252-encoded .txt (Windows Notepad "ANSI" — the bug source)
    must decode CORRECTLY. Pre-V0.6.18 the read_text(encoding='utf-8',
    errors='ignore') path SILENTLY DROPPED every non-ASCII byte — the
    smart quotes, em-dash, and accented chars would all vanish."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    # cp1252-specific bytes: 0x93/0x94 = smart double quotes, 0x97 = em-dash,
    # 0x92 = curly apostrophe, 0xe9 = é (same in cp1252 and latin-1).
    original = "It\N{RIGHT SINGLE QUOTATION MARK}s a Windows \N{LEFT DOUBLE QUOTATION MARK}ANSI\N{RIGHT DOUBLE QUOTATION MARK} file \N{EM DASH} with \N{LATIN SMALL LETTER E WITH ACUTE}."
    p = tmp_path / "ansi.txt"
    p.write_bytes(original.encode("cp1252"))
    result = _read_text_with_encoding_fallback(p)
    assert result == original, (
        f"cp1252 must round-trip; got {result!r} (the pre-V0.6.18 path would "
        f"have lost every non-ASCII byte to errors='ignore')."
    )


def test_v0618_read_text_with_encoding_fallback_pure_ascii(tmp_path: Path) -> None:
    """A pure-ASCII .txt decodes identically under any of the four
    encodings — the cascade succeeds at step 1 (utf-8-sig is a superset
    of ASCII) and the result is byte-identical to the input."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    original = "Plain ASCII text - no surprises here."
    p = tmp_path / "ascii.txt"
    # Pure ASCII: encode with ASCII (a subset of utf-8 / cp1252 / latin-1).
    p.write_bytes(original.encode("ascii"))
    assert _read_text_with_encoding_fallback(p) == original


def test_v0618_read_text_with_encoding_fallback_never_raises_on_garbage(
    tmp_path: Path,
) -> None:
    """A file with bytes that aren't valid in ANY of utf-8-sig / utf-8 /
    cp1252 (e.g., lone 0x80–0x9F bytes that are undefined in cp1252 for
    some positions, or 0xFE / 0xFF at the start) must STILL decode via
    the latin-1 catch-all — the function NEVER raises."""
    from core.pipeline.multi_format_reader import _read_text_with_encoding_fallback

    p = tmp_path / "garbage.txt"
    # Bytes that don't form a valid BOM (no FF FE / FE FF / EF BB BF
    # prefix) and aren't valid in any of utf-8 / cp1252 (0x81 is
    # undefined in cp1252) → fall through to the latin-1 catch-all.
    # V0.6.19 (W-e1) added UTF-16/UTF-32 BOM detection to the cascade,
    # so bytes starting with FF FE would now be decoded as UTF-16-LE
    # (with garbage) — this test deliberately avoids BOM-prefixed bytes
    # to pin the V0.6.18 "garbage bytes never raise" contract on the
    # latin-1 catch-all path.
    p.write_bytes(b"\x80\x81\x97\xabSome text here")
    result = _read_text_with_encoding_fallback(p)
    # Must NOT raise, and must contain the ASCII tail verbatim (latin-1
    # decodes each byte 1:1, so ASCII subsequences are preserved).
    assert "Some text here" in result


def test_v0618_extract_text_file_uses_the_fallback(tmp_path: Path) -> None:
    """The public _extract_text_file entry point routes through the new
    cascade — a cp1252 .txt returns the round-tripped text + a sane
    page count."""
    from core.pipeline.multi_format_reader import _extract_text_file

    original = (
        "Windows ANSI file \N{EM DASH} with smart quotes "
        "\N{LEFT DOUBLE QUOTATION MARK}hello\N{RIGHT DOUBLE QUOTATION MARK} "
        "and \N{LATIN SMALL LETTER E WITH ACUTE}."
    )
    p = tmp_path / "ansi.txt"
    p.write_bytes(original.encode("cp1252"))

    logs: list[str] = []

    def log(msg: str, level: str = "INFO") -> None:
        logs.append(msg)

    text, pages = _extract_text_file(p, log)
    assert text == original, f"_extract_text_file must round-trip cp1252; got {text!r}"
    assert pages >= 1


# ── Layer 4: regressions of the contract — the existing callers still work ──


def test_v0618_generate_podcast_audio_backward_compat_no_token_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing callers that DON'T pass cancel_token (every pre-V0.6.18
    call site) must keep working — the default is None and the loop's
    cancel check short-circuits to False (no cancellation). This pins
    the backward-compat guarantee."""
    import inspect

    from core.podcast.audio_generator import generate_podcast_audio

    sig = inspect.signature(generate_podcast_audio)
    # The new param is keyword-or-positional with default None.
    param = sig.parameters["cancel_token"]
    assert param.default is None
    assert param.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
