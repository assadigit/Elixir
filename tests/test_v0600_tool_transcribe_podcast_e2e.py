"""V0.6.0 (the dedicated-tools verification campaign) — Tools 11/12: the
Transcribe Service card + the Podcast Maker SCRIPT generator, end-to-end.

Inventory + trace (evidence-first):
- Cards: ``transcribe`` + ``podcast_maker`` — ``ui_qt/views/tool_dashboard.py:41``
  TOOL_CARDS row 4 (AUDIO).
- Routing: ``ui_qt/views/convert_view.py`` ``_on_tool_clicked`` →
  ``transcribe`` (base_dialog facade →
  ``ui_qt/views/service_dialogs/dialogs/transcribe_service_dialog.py``,
  the V18.20.4.6 O-b2 split) and ``podcast_maker`` → modal QDialog wrapping
  ``ui_qt/views/podcast_maker_view.PodcastMakerView`` (V13.31.0 #6).
- Transcribe: ``TranscribeServiceDialog._on_process`` :286 (validation +
  SimpleWorker spawn :304) → ``_do_transcribe`` :317 (widget-free worker
  body: ffmpeg video→wav :349, ``transcribe_audio`` :362, raw .md write
  :381, ``summarize_transcript`` :397) → ``_on_done`` :443.
  Engine acquisition: ``core/transcribe/transcribe_service.py:130`` does a
  function-level ``from faster_whisper import WhisperModel`` — ImportError
  → ``{"error": "faster-whisper not installed…"}`` (the contract shape);
  the model downloads from HF on first load (rig item). Audio extraction
  shells out to the ``ffmpeg`` binary (:42-55). Summary LLM:
  ``summarize_transcript`` :216 → ``create_provider`` factory
  (core/llm/llm_provider_impl.py:196).
- Podcast script: ``PodcastMakerView._on_generate_script`` :408 → worker
  ``_work`` :426 → ``generate_podcast_script`` (module-level import, the
  stub seam) with ``ollama_url=Settings().get("summarisation.ollama_url")``
  and the combo model → ``core/podcast/script_generator.py:1222`` → RAW
  Ollama-shape ``POST {ollama_url}/api/generate`` (:1287 — the zai-llamacpp
  shim :3031 speaks exactly this) → deterministic coverage + gap-fill +
  force-insert + human-element injection → ``_on_script_done`` :451.
  Pipeline-side riders (``core/outputs/podcast_generator.py`` /
  ``podcast_coverage.py``) get Layer-1 pins here.
- Existing coverage: source-pin only (test_v182045/test_v182046 AST) +
  pipeline orchestration (test_conversion_output_runner_characterization)
  — zero functional card-path tests before this file.

Layers (house pattern, cf. test_v0600_tool_cutter_e2e / _summarization_):
1. Pure characterization (no Qt): bullet extraction, pre-processing,
   multi-strategy response parsing, coverage verification, force-insert,
   human-element injection, vocal cues, dedup/number fixes, timestamp
   formatting, pipeline word-count helpers.
2. Service-level: transcribe CONTRACT (faster-whisper absent → error dict;
   faked ``faster_whisper`` module → real dispatch logic), REAL ffmpeg
   audio extraction, faked-engine end-to-end writing real output files,
   provider plumbing pins (T1/T2), and LIVE LLM for the podcast script
   through the real shim (:3031, /api/generate Ollama shape).
3. Full dialog/view drives through the REAL worker threads
   (SimpleWorker QThread for the dialog; the view's own threading.Thread +
   _SignalBridge) with the engine/LLM stubbed at the traced seams; a LIVE
   view drive through the shim. QMessageBox monkeypatched to recorders
   (never exec()).
"""

from __future__ import annotations

import inspect
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Layer 0: availability gates ─────────────────────────────────────────────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _faster_whisper_absent() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return False
    except Exception:
        return True


def _shim_live() -> bool:
    """Health-check the zai-llamacpp shim (the live-LLM gate)."""
    try:
        import requests

        sess = requests.Session()
        sess.trust_env = False
        return bool(sess.get("http://localhost:3031/health", timeout=2).ok)
    except Exception:
        return False


_SHIM_URL = "http://localhost:3031"  # Ollama-shape root (/api/generate)
_SHIM_V1 = "http://localhost:3031/v1"  # OpenAI-compat root (llamacpp)
_SHIM_MODEL = "glm-4-plus"
_DEAD_ENDPOINT = "http://127.0.0.1:1"  # instant connection-refused, hermetic


# ── Fixtures / helpers ──────────────────────────────────────────────────────


class _StubController:
    """The dialog/view only needs get_setting / update_setting / log."""

    def __init__(self, settings: dict | None = None) -> None:
        self._settings: dict[str, object] = dict(settings or {})

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def log(self, msg: str, level: str = "INFO") -> None:
        pass


class _TestSettings:
    """Deterministic offline Settings (real ``Settings._test_override`` DI
    hook — the batch-B pattern). ``get_ollama_url`` mirrors the canonical
    5-key resolver's contract (settings.py:1449)."""

    def __init__(self, values: dict | None = None):
        self._values = {
            "summarisation.provider": "ollama",
            "summarisation.ollama_url": _DEAD_ENDPOINT,
            "summarisation.endpoint": "",
            "llm.ollama_url": "",
            "summarisation.model": "",
            # V0.6.13: summarize_transcript + generate_podcast_script now
            # consult the llama.cpp-first policy, which probes this key —
            # pin it at a DEAD port (the V0.6.12 packets-shim precedent)
            # so every test in this file is deterministic even on a rig
            # with a real llama-server on 8080. Tests that WANT the live
            # shim override it explicitly (cf. TestLiveSummarizeTranscript).
            "summarisation.llamacpp_base_url": "http://127.0.0.1:9/v1",
        }
        if values:
            self._values.update(values)

    def get(self, key: str, default=None):
        return self._values.get(key, default)

    def set(self, key: str, value) -> None:
        self._values[key] = value

    def save(self) -> bool:
        return True

    def get_ollama_url(self) -> str:
        for k in ("llm.ollama_url", "summarisation.endpoint", "summarisation.ollama_url"):
            v = str(self._values.get(k, "") or "").rstrip("/")
            if v:
                return v
        return "http://localhost:11434"


def _install_settings(values: dict | None = None) -> _TestSettings:
    from utils.settings import Settings

    ts = _TestSettings(values)
    Settings._test_override = ts  # type: ignore[assignment]
    return ts


@pytest.fixture(autouse=True)
def _hermetic_env():
    """Offline Settings override for every test (restored on teardown)."""
    from utils.settings import Settings

    prev_override = Settings._test_override
    Settings._test_override = _TestSettings()  # type: ignore[assignment]
    yield
    Settings._test_override = prev_override


class _MsgRecorder:
    """Stub replacing QMessageBox on the dialog/view MODULES (never exec())."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def warning(self, parent, title, text, *a, **k):
        self.calls.append(("warning", f"{title} :: {text}"))

    def critical(self, parent, title, text, *a, **k):
        self.calls.append(("critical", f"{title} :: {text}"))

    def information(self, parent, title, text, *a, **k):
        self.calls.append(("information", f"{title} :: {text}"))


def _make_msg_recorder(module, monkeypatch) -> _MsgRecorder:
    rec = _MsgRecorder()
    monkeypatch.setattr(module, "QMessageBox", rec)
    return rec


def _spin(app, done, timeout_s: float = 60.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if done():
            return True
        time.sleep(0.02)
    return False


# Content-agnostic synthetic source (Rule 1: no book/author/domain text).
SOURCE_2B = (
    "- Bees pollinate a large share of flowering plants while foraging for "
    "nectar, which supports wild ecosystems and agricultural crops.\n"
    "- Honeybee colonies divide labor among a queen, workers, and drones, "
    "and workers change roles as they age, from nursing brood to foraging."
)


def _mkline(host: str, text: str, ref: str = "bullet 1", seg: str = "content"):
    from core.podcast.script_generator import ScriptLine

    return ScriptLine(host=host, text=text, source_ref=ref, segment_type=seg)


def _build_wav(tmp_path: Path, name: str = "sample.wav") -> Path:
    p = tmp_path / name
    p.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x00\x01\x00")
    return p


def _build_mp4(tmp_path: Path, name: str = "clip.mp4") -> Path:
    """A REAL 0.5s mp4 (ffmpeg lavfi testsrc + sine) — exercises the real
    ffmpeg extraction path."""
    import subprocess as _sp

    p = tmp_path / name
    _sp.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=0.5:size=64x64:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            "-shortest",
            str(p),
        ],
        check=True,
        timeout=60,
    )
    return p


# ── Layer 1: podcast script generator — pure logic ──────────────────────────


class TestExtractBullets:
    def test_markdown_bullets(self):
        from core.podcast.script_generator import extract_bullets

        assert extract_bullets("- alpha point here\n- beta point here") == [
            "alpha point here",
            "beta point here",
        ]

    def test_numbered_bullets(self):
        from core.podcast.script_generator import extract_bullets

        assert extract_bullets("1) first point here\n2) second point here") == [
            "first point here",
            "second point here",
        ]

    def test_continuation_lines_merge(self):
        from core.podcast.script_generator import extract_bullets

        out = extract_bullets("- a point that\n  wraps onto a second line")
        assert out == ["a point that wraps onto a second line"]

    def test_plain_paragraphs_split_on_blank_lines(self):
        from core.podcast.script_generator import extract_bullets

        out = extract_bullets("First standalone paragraph.\n\nSecond standalone one.")
        assert out == ["First standalone paragraph.", "Second standalone one."]

    def test_short_fragments_filtered(self):
        from core.podcast.script_generator import extract_bullets

        assert extract_bullets("- tiny\n- a much longer point here") == ["a much longer point here"]

    def test_markdown_headings_are_not_bullets(self):
        """P3 (V0.6.0): ``preprocess_source_text`` prepends its own
        "# Source Material" heading — the heading must NOT become a phantom
        bullet fed to the LLM as "[BULLET N] # Source Material"."""
        from core.podcast.script_generator import extract_bullets, preprocess_source_text

        processed = preprocess_source_text(SOURCE_2B)
        assert processed.startswith("# Source Material")
        bullets = extract_bullets(processed)
        assert len(bullets) == 2
        assert all(not b.startswith("#") for b in bullets)
        # a heading mid-text also breaks the bullet run, it doesn't merge
        out = extract_bullets("# A Heading\n- first real point here\n## Another\nsecond plain one.")
        assert out == ["first real point here", "second plain one."]


class TestPreprocessSourceText:
    def test_strips_html_tags(self):
        from core.podcast.script_generator import preprocess_source_text

        out = preprocess_source_text("<p>a plain sentence about insects.</p>")
        assert "<p>" not in out and "a plain sentence about insects." in out

    def test_normalizes_bullet_markers(self):
        from core.podcast.script_generator import preprocess_source_text

        out = preprocess_source_text("• a unicode bullet point here")
        assert "- a unicode bullet point here" in out
        assert "•" not in out

    def test_removes_standalone_page_numbers(self):
        from core.podcast.script_generator import preprocess_source_text

        out = preprocess_source_text("some meaningful sentence.\n12\nanother sentence here.")
        assert "\n12\n" not in out
        assert "another sentence here." in out

    def test_adds_source_heading(self):
        from core.podcast.script_generator import preprocess_source_text

        out = preprocess_source_text("just a plain sentence about topics.")
        assert out.startswith("# Source Material")


class TestScriptResultRoundtrip:
    def _result(self):
        from core.podcast.script_generator import ScriptResult

        return ScriptResult(
            lines=[
                _mkline("A", "Host A opening line.", "intro", "intro"),
                _mkline("B", "Host B response line.", "bullet 1", "content"),
                _mkline("A", "Host A closing line.", "conclusion", "conclusion"),
            ],
            bullets_input=["bullet one text", "bullet two text"],
            bullets_covered=[0, 1],
            coverage_pct=1.0,
            title="Sample Title",
        )

    def test_to_dialogue_text_prefixes(self):
        r = self._result()
        txt = r.to_dialogue_text()
        assert txt.split("\n\n")[0].startswith("[Host A] Host A opening line.")
        assert "[Host B] Host B response line." in txt

    def test_json_roundtrip(self):
        import json

        r = self._result()
        data = json.loads(r.to_json())
        assert [ln["host"] for ln in data["lines"]] == ["A", "B", "A"]
        assert data["coverage_pct"] == 1.0
        r2 = type(r).from_json(r.to_json())
        assert [ln.text for ln in r2.lines] == [ln.text for ln in r.lines]
        assert r2.coverage_pct == 1.0

    def test_from_json_strips_host_prefix_inside_text(self):
        from core.podcast.script_generator import ScriptResult

        raw = '[{"host": "A", "text": "[Host A] prefixed content line.", "source_ref": "intro"}]'
        r = ScriptResult.from_json(raw)
        assert r.lines[0].text == "prefixed content line."

    def test_from_json_jsonl_fallback(self):
        from core.podcast.script_generator import ScriptResult

        raw = (
            '{"host": "A", "text": "first jsonl line text", "source_ref": "intro"},\n'
            '{"host": "B", "text": "second jsonl line text", "source_ref": "bullet 1"}'
        )
        r = ScriptResult.from_json(raw)
        assert len(r.lines) == 2 and r.lines[1].host == "B"


class TestParseScriptResponse:
    def test_clean_json_array(self):
        from core.podcast.script_generator import _parse_script_response

        lines = _parse_script_response(
            '[{"host": "A", "text": "clean json line here", "source_ref": "bullet 1"}]'
        )
        assert len(lines) == 1 and lines[0].text == "clean json line here"

    def test_fenced_json_array(self):
        """The live shim's actual response shape (probed: ```json fenced)."""
        from core.podcast.script_generator import _parse_script_response

        lines = _parse_script_response(
            '```json\n[{"host": "B", "text": "fenced json line here", "source_ref": "bullet 2"}]\n```'
        )
        assert len(lines) == 1 and lines[0].host == "B"

    def test_json_with_preamble_and_trailing(self):
        from core.podcast.script_generator import _parse_script_response

        lines = _parse_script_response(
            'Here is the script:\n[{"host": "A", "text": "embedded array line", "source_ref": "intro"}]\nDone.'
        )
        assert len(lines) == 1 and lines[0].text == "embedded array line"

    def test_jsonl_response(self):
        from core.podcast.script_generator import _parse_script_response

        lines = _parse_script_response(
            '{"host": "A", "text": "jsonl first line", "source_ref": "bullet 1"}\n'
            '{"host": "B", "text": "jsonl second line", "source_ref": "bullet 2"}'
        )
        assert [ln.host for ln in lines] == ["A", "B"]

    def test_plain_dialogue_fallback(self):
        from core.podcast.script_generator import _parse_script_response

        lines = _parse_script_response("Host A: spoken plain line.\nHost B: reply plain line.")
        assert len(lines) == 2 and lines[0].host == "A"
        assert lines[0].text == "spoken plain line."

    def test_empty_returns_empty(self):
        from core.podcast.script_generator import _parse_script_response

        assert _parse_script_response("") == []
        assert _parse_script_response("   ") == []


class TestCoverageAndForceInsert:
    def test_verify_coverage_deterministic(self):
        from core.podcast.script_generator import verify_coverage

        lines = [
            _mkline("A", "x", "Bullet 1", "content"),
            _mkline("B", "y", "bullet 3", "content"),
        ]
        covered, missing = verify_coverage(lines, 3)
        assert covered == [0, 2] and missing == [1]

    def test_force_insert_conversational_adds_ab_pair_before_conclusion(self):
        from core.podcast.script_generator import _force_insert_segments

        lines = [
            _mkline("A", "intro line", "intro", "intro"),
            _mkline("A", "conclusion line", "conclusion", "conclusion"),
        ]
        out = _force_insert_segments(lines, ["bullet one text here"], [0], "conversational")
        # inserted before the conclusion
        assert [ln.segment_type for ln in out] == ["intro", "content", "content", "conclusion"]
        assert [ln.host for ln in out[1:3]] == ["A", "B"]
        assert out[1].source_ref == "bullet 1"
        assert "bullet one text here" in out[1].text

    def test_force_insert_lecture_single_line(self):
        from core.podcast.script_generator import _force_insert_segments

        lines = [_mkline("A", "only line", "intro", "intro")]
        out = _force_insert_segments(lines, ["a bullet text here"], [0], "lecture")
        assert len(out) == 2 and out[-1].source_ref == "bullet 1"
        assert out[-1].text.startswith("Another important point:")


class TestHumanElementsAndCues:
    def test_injection_is_deterministic_seed(self):
        from core.podcast.script_generator import inject_human_elements

        lines = [
            _mkline("A", "a reasonably long content line for the podcast host.", "bullet 1"),
            _mkline("B", "a reply line that is also long enough for cue insertion.", "bullet 1"),
        ] * 3
        a = inject_human_elements(list(lines), "conversational", intensity=0.3)
        b = inject_human_elements(list(lines), "conversational", intensity=0.3)
        assert [(ln.host, ln.text) for ln in a] == [(ln.host, ln.text) for ln in b]

    def test_injection_can_add_backchannel_or_reaction_lines(self):
        from core.podcast.script_generator import inject_human_elements

        lines = [
            _mkline("A", f"content line number {i} with some length in it.", f"bullet {i + 1}")
            for i in range(8)
        ]
        out = inject_human_elements(lines, "conversational", intensity=0.9)
        seg_types = {ln.segment_type for ln in out}
        assert seg_types & {"backchannel", "reaction"}
        assert len(out) > len(lines)

    def test_strip_vocal_cues_extracts_and_cleans(self):
        from core.podcast.script_generator import strip_vocal_cues

        clean, cues = strip_vocal_cues("Wait for it [pause 0.7s] then breathe [breath], okay?")
        assert "[pause" not in clean and "[breath]" not in clean
        kinds = {c[1] for c in cues}
        assert "pause" in kinds and "breath" in kinds
        pause = [c for c in cues if c[1] == "pause"][0]
        assert pause[2] == 0.7

    def test_strip_vocal_cues_laugh_becomes_haha(self):
        from core.podcast.script_generator import strip_vocal_cues

        clean, cues = strip_vocal_cues("that joke [laugh] was great")
        assert "haha" in clean and "[laugh]" not in clean
        assert any(c[1] == "laugh" for c in cues)


class TestPostProcessing:
    def test_duplicate_lines_removed(self):
        from core.podcast.script_generator import _remove_duplicate_lines

        lines = [
            _mkline("A", "the military police and law enforcement will be automated"),
            _mkline("B", "the military police and law enforcement will be automated"),
            _mkline("A", "a completely different observation about the topic"),
        ]
        out = _remove_duplicate_lines(lines, lambda *a: None)
        assert len(out) == 2

    def test_number_formatting_years_and_quantities(self):
        from core.podcast.script_generator import _fix_number_formatting

        lines = [
            _mkline("A", "this happened in two thousand twenty-two, honestly."),
            _mkline("A", "and also in two thousand and thirty-one maybe."),
            _mkline("B", "around one billion units were counted."),
        ]
        out = _fix_number_formatting(lines, lambda *a: None)
        assert "2022" in out[0].text
        assert "2031" in out[1].text
        assert "1 billion" in out[2].text

    def test_number_formatting_does_not_mangle_compound_years(self):
        """P2 (V0.6.0): the alternation used to try "twenty" before
        "twenty-two", so "two thousand twenty-two" became "2020-two"."""
        from core.podcast.script_generator import _fix_number_formatting

        lines = [_mkline("A", "the survey closed in two thousand twenty-two.")]
        out = _fix_number_formatting(lines, lambda *a: None)
        assert "2022" in out[0].text
        assert "2020-two" not in out[0].text

    def test_distinct_lines_kept_by_dedup(self):
        from core.podcast.script_generator import _remove_duplicate_lines

        lines = [
            _mkline("A", "a line about pollination of flowering plants"),
            _mkline("B", "another line about colony labor division"),
        ]
        out = _remove_duplicate_lines(lines, lambda *a: None)
        assert len(out) == 2


class TestPromptBuilders:
    def test_conversational_prompt_pins_bullets_and_format(self):
        from core.podcast.script_generator import _build_conversational_prompt

        p = _build_conversational_prompt(
            ["bullet one text", "bullet two text"], "casual", "balanced", "en"
        )
        assert "[BULLET 1] bullet one text" in p
        assert "[BULLET 2] bullet two text" in p
        assert '"host": "A"' in p and '"source_ref": "bullet 1"' in p
        assert "JSON array" in p

    def test_lecture_prompt_single_host(self):
        from core.podcast.script_generator import _build_lecture_prompt

        p = _build_lecture_prompt(["bullet one text"], "academic", "conservative", "en")
        assert "[BULLET 1] bullet one text" in p
        assert '"host": "A"' in p
        assert "SINGLE HOST" in p

    def test_farsi_instruction_included(self):
        from core.podcast.script_generator import _build_conversational_prompt

        p = _build_conversational_prompt(["bullet one text"], "casual", "balanced", "fa")
        assert "Persian (Farsi)" in p


class TestDefaultsGuard:
    """T1/P1 (V0.6.0): the service-level default model tags were the
    KNOWN-BAD Ollama tags (the W-a10 class — they 404 on the rig). Both now
    default to the shared RIG_FALLBACK_MODEL from model_taxonomy."""

    def test_transcribe_and_podcast_defaults_are_rig_fallback(self):
        from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
        from core.podcast.script_generator import generate_podcast_script
        from core.transcribe.transcribe_service import summarize_transcript

        assert (
            inspect.signature(summarize_transcript).parameters["model"].default
            == RIG_FALLBACK_MODEL
        )
        assert (
            inspect.signature(generate_podcast_script).parameters["model"].default
            == RIG_FALLBACK_MODEL
        )


# ── Layer 1: pipeline riders (outputs/podcast_generator) ────────────────────


class TestPipelinePodcastHelpers:
    def test_word_count_conversions(self):
        from core.outputs.podcast_generator import minutes_to_words, words_to_minutes

        assert minutes_to_words(30) == 4500
        assert words_to_minutes(4500) == 30
        assert words_to_minutes(1) == 1  # floor at 1 minute

    def test_prompt_builder_composes_fragments(self):
        from core.outputs.podcast_generator import PodcastPromptBuilder

        b = PodcastPromptBuilder(hosts=2, tone="conversational")
        p = b.build("- a keypoint about the topic\n- another keypoint", "A Book Title")
        assert "Host A" in p and "Host B" in p
        assert "Key Points from the book" in p
        assert "- a keypoint about the topic" in p
        assert "A Book Title" in p

    def test_prompt_builder_one_host(self):
        from core.outputs.podcast_generator import PodcastPromptBuilder

        p = PodcastPromptBuilder(hosts=1).build("- a keypoint", "A Book Title")
        assert "SINGLE narrator" in p or "single narrator" in p


# ── Layer 1: transcribe pure logic ──────────────────────────────────────────


class TestFormatTranscript:
    def test_timestamps_and_joining(self):
        from core.transcribe.transcribe_service import format_transcript_with_timestamps

        out = format_transcript_with_timestamps(
            [
                {"start": 0.0, "end": 2.5, "text": "hello there"},
                {"start": 65.0, "end": 67.0, "text": "second segment"},
            ]
        )
        lines = out.split("\n\n")
        assert lines[0] == "[00:00.00] hello there"
        assert lines[1] == "[01:05.00] second segment"

    def test_empty_segments(self):
        from core.transcribe.transcribe_service import format_transcript_with_timestamps

        assert format_transcript_with_timestamps([]) == ""


# ── Layer 2: transcribe contract + engine seams ─────────────────────────────


class TestTranscribeAudioContract:
    def test_engine_absent_returns_clear_error(self):
        """The card's headline contract: a parseable error dict, not an
        exception.

        V0.6.55 STALE-PIN REFRESH, documented: this pin asserted the
        PRE-V0.6.42 default engine (faster-whisper + its pip-install
        error). Since V0.6.42 the DEFAULT engine is transcribe.cpp — on
        a machine without the CLI binary the error names the exe path
        (the V0.6.40/V0.6.47 contract). The pin now pins the CURRENT
        default-engine contract; the faster-whisper dispatch path is
        pinned EXPLICITLY (engine="faster_whisper") by the next test.
        """
        from core.transcribe.transcribe_service import transcribe_audio

        out = transcribe_audio("whatever.wav")
        assert "error" in out
        assert "transcribe-cli.exe" in out["error"], out["error"]
        assert "Settings" in out["error"] or "path" in out["error"].lower()

    @pytest.mark.skipif(not _faster_whisper_absent(), reason="faster_whisper installed (rig)")
    def test_faked_engine_dispatch_full_result(self, monkeypatch):
        """Dispatch logic against a hermetic fake ``faster_whisper`` module:
        device resolution (torch absent → cpu), segment iteration, progress
        callbacks, and the result dict shape.

        V0.6.55 STALE-PIN REFRESH, documented: the call now passes
        engine="faster_whisper" EXPLICITLY — the test's original intent
        (pin the faked faster-whisper dispatch path) was silently
        broken by V0.6.42's default-engine flip to transcribe_cpp (the
        default now returns the transcribe-cli.exe-not-found error
        instead of dispatching to the faked module).
        """
        import types
        from types import SimpleNamespace

        calls: dict = {}

        class _FakeWhisperModel:
            def __init__(self, model_size, device="cpu", compute_type="int8"):
                calls["init"] = (model_size, device, compute_type)

            def transcribe(self, audio_path, language=None, beam_size=5, vad_filter=True):
                calls["transcribe"] = (audio_path, language, beam_size, vad_filter)
                segs = [
                    SimpleNamespace(start=0.0, end=2.0, text=" hello "),
                    SimpleNamespace(start=2.0, end=4.0, text=" world "),
                ]
                info = SimpleNamespace(duration=4.0, language="en")
                return iter(segs), info

        fake_mod = types.ModuleType("faster_whisper")
        fake_mod.WhisperModel = _FakeWhisperModel
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_mod)

        progress: list[tuple[int, str]] = []
        from core.transcribe.transcribe_service import transcribe_audio

        out = transcribe_audio(
            "in.wav",
            model_size="small",
            engine="faster_whisper",  # V0.6.55: explicit — the default is transcribe_cpp since V0.6.42
            log_callback=lambda msg, level="INFO": None,
            progress_callback=lambda pct, msg: progress.append((pct, msg)),
        )
        assert "error" not in out
        assert out["text"] == "hello world"
        assert out["duration"] == 4.0
        assert out["language"] == "en"
        assert [seg["text"] for seg in out["segments"]] == ["hello", "world"]
        assert calls["init"] == ("small", "cpu", "int8")
        assert calls["transcribe"][0] == "in.wav"
        assert progress and progress[0][0] == 5  # "Loading model" tick
        assert any(p == 20 for p, _ in progress)  # "Transcribing" tick


class TestExtractAudioReal:
    @pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
    def test_real_ffmpeg_extracts_wav_from_mp4(self, tmp_path):
        from core.transcribe.transcribe_service import extract_audio_from_video

        mp4 = _build_mp4(tmp_path)
        wav = tmp_path / "clip_audio.wav"
        logs: list[str] = []
        ok = extract_audio_from_video(
            str(mp4), str(wav), log_callback=lambda m, l="INFO": logs.append(m)
        )
        assert ok is True
        assert wav.exists() and wav.stat().st_size > 4000
        assert any("Audio extracted" in m for m in logs)

    @pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
    def test_corrupt_input_reports_failure(self, tmp_path):
        from core.transcribe.transcribe_service import extract_audio_from_video

        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"not a real video file at all")
        ok = extract_audio_from_video(str(bad), str(tmp_path / "out.wav"))
        assert ok is False
        assert not (tmp_path / "out.wav").exists()


class TestSummarizeTranscriptPlumbing:
    """T2 (V0.6.0): ``summarize_transcript`` used to hardcode
    provider="ollama" (ignoring ``summarisation.provider``) and its
    ``ollama_url`` parameter was dead (the factory pins
    localhost:11434). Both are now honored."""

    def _install_fake_factory(self, monkeypatch, response="# Notes\n\n- a point\n"):
        import core.llm.llm_provider as lp

        captured: dict = {}

        class _FakeProvider:
            base_url = "http://localhost:11434"

            def complete_streaming(
                self, prompt, temperature=None, max_tokens=None, model=None, on_chunk=None
            ):
                captured["call"] = {
                    "prompt": prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "model": model,
                }
                return response

        def _factory(provider, settings, log_callback=None, supervisor=None):
            captured["provider"] = provider
            captured["settings"] = settings
            prov = _FakeProvider()
            captured["instance"] = prov
            return prov

        monkeypatch.setattr(lp, "create_provider", _factory)
        return captured

    def test_provider_follows_settings_not_hardcoded(self, monkeypatch):
        captured = self._install_fake_factory(monkeypatch)
        _install_settings({"summarisation.provider": "llamacpp"})
        from core.transcribe.transcribe_service import summarize_transcript

        out = summarize_transcript("some transcript text", model="model-a")
        assert captured["provider"] == "llamacpp"
        assert captured["call"]["model"] == "model-a"
        assert out == "# Notes\n\n- a point"

    def test_explicit_ollama_url_is_honored(self, monkeypatch):
        captured = self._install_fake_factory(monkeypatch)
        _install_settings({"summarisation.provider": "ollama"})
        from core.transcribe.transcribe_service import summarize_transcript

        summarize_transcript("text", model="m", ollama_url="http://127.0.0.1:9")
        assert captured["instance"].base_url == "http://127.0.0.1:9"

    def test_default_url_leaves_factory_default_alone(self, monkeypatch):
        captured = self._install_fake_factory(monkeypatch)
        _install_settings({"summarisation.provider": "ollama"})
        from core.transcribe.transcribe_service import summarize_transcript

        summarize_transcript("text", model="m", ollama_url="http://localhost:11434")
        assert captured["instance"].base_url == "http://localhost:11434"

    def test_prompt_contains_transcript(self, monkeypatch):
        captured = self._install_fake_factory(monkeypatch)
        from core.transcribe.transcribe_service import summarize_transcript

        summarize_transcript("bees pollinate many flowering plants", model="m")
        assert "bees pollinate many flowering plants" in captured["call"]["prompt"]

    def test_code_fences_stripped_from_response(self, monkeypatch):
        self._install_fake_factory(monkeypatch, response="```markdown\n# Notes\n\n- a point\n```")
        from core.transcribe.transcribe_service import summarize_transcript

        out = summarize_transcript("text", model="m")
        assert out.startswith("# Notes") and "```" not in out

    def test_empty_response_raises_structured_error(self, monkeypatch):
        """V0.6.55 STALE-PIN REFRESH, documented: the empty-LLM-response
        failure contract changed from the ``"Error: ..."`` STRING return
        (which the dialog had to prefix-match) to the structured
        ``LLMEmptyResponseError`` (P5 — stage + message + fix, caught by
        the dialog's ``except TranscribeError``). The pin now asserts the
        RAISE (the old string contract cannot return)."""
        from core.transcribe.errors import LLMEmptyResponseError

        self._install_fake_factory(monkeypatch, response="   ")
        from core.transcribe.transcribe_service import summarize_transcript

        with pytest.raises(LLMEmptyResponseError):
            summarize_transcript("text", model="m")


# ── Layer 2: faked-engine dialog service E2E (real files written) ───────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDoTranscribeEndToEnd:
    def _stub_seam(
        self, monkeypatch, transcribe_ret=None, summarize_ret="# Summary\n\n- point", capture=None
    ):
        import core.transcribe.transcribe_service as ts

        def _fake_transcribe(audio_path, model_size="small", **kwargs):
            if capture is not None:
                capture["transcribe"] = (audio_path, model_size)
            if isinstance(transcribe_ret, dict):
                return transcribe_ret
            return {
                "text": "hello world from the fake engine",
                "segments": [{"start": 0.0, "end": 2.0, "text": "hello world"}],
                "language": "en",
                "duration": 2.0,
            }

        def _fake_summarize(transcript, model="m", ollama_url="http://localhost:11434", **kwargs):
            if capture is not None:
                capture["summarize"] = (transcript, model, ollama_url)
            return summarize_ret

        monkeypatch.setattr(ts, "transcribe_audio", _fake_transcribe)
        monkeypatch.setattr(ts, "summarize_transcript", _fake_summarize)
        return ts

    def _make_dialog(self):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog import (
            TranscribeServiceDialog,
        )

        return TranscribeServiceDialog(_StubController()), app

    def test_audio_flow_writes_raw_and_summary(self, tmp_path, monkeypatch):
        capture: dict = {}
        self._stub_seam(monkeypatch, capture=capture)
        self._install_settings_for_dialog()
        dlg, app = self._make_dialog()
        src = _build_wav(tmp_path)
        out_dir = tmp_path / "out"
        opts = {
            "filepath": str(src),
            "output_folder": str(out_dir),
            "engine": "faster_whisper",  # V0.6.62: explicit (the V0.6.55 stale-pin lesson) — the default is transcribe_cpp
            "whisper_model": "tiny",
            "llm_model": "model-a",
            "save_raw": True,
            "save_summary": True,
        }
        results = dlg._do_transcribe(opts)
        assert results["error"] is None
        raw = out_dir / "sample_transcript.md"
        summary = out_dir / "sample_summary.md"
        assert raw.exists() and summary.exists()
        body = raw.read_text(encoding="utf-8")
        assert body.startswith("# Transcript: sample")
        assert "**Duration:** 2.0s" in body and "**Language:** en" in body
        assert "[00:00.00] hello world" in body
        assert capture["transcribe"] == (str(src), "tiny")
        assert capture["summarize"][1] == "model-a"
        # T2: the dialog resolves the endpoint through the canonical
        # get_ollama_url() — the override's custom endpoint wins.
        assert capture["summarize"][2] == "http://127.0.0.1:9"
        app.processEvents()

    def test_subtitle_export_flow_writes_srt_and_vtt(self, tmp_path, monkeypatch):
        """V0.6.62: the subtitle deliverables — the engine's timestamped
        segments become <stem>.srt + <stem>.vtt beside the transcript.
        The stub returns segments [{"start": 0.0, "end": 2.0, ...}], so
        the SRT must carry exactly one comma-timestamped cue and the
        VTT the WEBVTT header + one dot-timestamped cue. engine is
        passed EXPLICITLY (the V0.6.55 stale-pin lesson: the default
        is transcribe_cpp since V0.6.42)."""
        self._stub_seam(monkeypatch)
        self._install_settings_for_dialog()
        dlg, app = self._make_dialog()
        src = _build_wav(tmp_path)
        out_dir = tmp_path / "out_sub"
        opts = {
            "filepath": str(src),
            "output_folder": str(out_dir),
            "engine": "faster_whisper",  # explicit — hits the stubbed transcribe_audio
            "whisper_model": "tiny",
            "llm_model": "model-a",
            "save_raw": False,
            "save_summary": False,
            "save_srt": True,
            "save_vtt": True,
        }
        results = dlg._do_transcribe(opts)
        assert results["error"] is None
        srt = out_dir / "sample.srt"
        vtt = out_dir / "sample.vtt"
        assert results["srt_path"] == str(srt) and results["vtt_path"] == str(vtt)
        assert srt.exists() and vtt.exists()
        srt_body = srt.read_text(encoding="utf-8")
        vtt_body = vtt.read_text(encoding="utf-8")
        assert srt_body == "1\n00:00:00,000 --> 00:00:02,000\nhello world\n"
        assert vtt_body == "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n"
        assert results["subtitle_cues"] == 1
        # V0.6.62 review finding 7: the flow is subtitle-ONLY — no
        # transcript/summary files may appear either.
        assert not (out_dir / "sample_transcript.md").exists()
        assert not (out_dir / "sample_summary.md").exists()
        app.processEvents()

    def _install_settings_for_dialog(self):
        return _install_settings(
            {"summarisation.ollama_url": "http://127.0.0.1:9", "summarisation.provider": "ollama"}
        )

    def test_summary_error_is_nonfatal_when_raw_saved(self, tmp_path, monkeypatch):
        self._stub_seam(monkeypatch, summarize_ret="Error: LLM returned empty response.")
        self._install_settings_for_dialog()
        dlg, app = self._make_dialog()
        src = _build_wav(tmp_path)
        opts = {
            "filepath": str(src),
            "output_folder": str(tmp_path / "o2"),
            "engine": "faster_whisper",  # V0.6.62: explicit (the V0.6.55 stale-pin lesson)
            "whisper_model": "tiny",
            "llm_model": "model-a",
            "save_raw": True,
            "save_summary": True,
        }
        results = dlg._do_transcribe(opts)
        assert results["raw_path"] and results["summary_path"] is None
        assert results["error"] == "Error: LLM returned empty response."
        assert (tmp_path / "o2" / "sample_transcript.md").exists()
        assert not (tmp_path / "o2" / "sample_summary.md").exists()
        app.processEvents()

    def test_transcribe_error_short_circuits(self, tmp_path, monkeypatch):
        self._stub_seam(
            monkeypatch,
            transcribe_ret={
                "error": "faster-whisper not installed. Run: pip install faster-whisper"
            },
        )
        self._install_settings_for_dialog()
        dlg, app = self._make_dialog()
        opts = {
            "filepath": str(_build_wav(tmp_path)),
            "output_folder": str(tmp_path / "o3"),
            "engine": "faster_whisper",  # V0.6.62: explicit (the V0.6.55 stale-pin lesson)
            "whisper_model": "tiny",
            "llm_model": "model-a",
            "save_raw": True,
            "save_summary": True,
        }
        results = dlg._do_transcribe(opts)
        assert "faster-whisper not installed" in results["error"]
        assert results["raw_path"] is None and results["summary_path"] is None
        assert not (tmp_path / "o3" / "sample_transcript.md").exists()
        app.processEvents()

    @pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
    def test_video_flow_real_ffmpeg_and_temp_cleanup(self, tmp_path, monkeypatch):
        import core.transcribe.transcribe_service as ts

        sizes: dict = {}

        def _fake_transcribe(audio_path, model_size="small", **kwargs):
            sizes["wav"] = Path(audio_path).stat().st_size
            return {
                "text": "hello world from the fake engine",
                "segments": [{"start": 0.0, "end": 2.0, "text": "hello world"}],
                "language": "en",
                "duration": 2.0,
            }

        monkeypatch.setattr(ts, "transcribe_audio", _fake_transcribe)
        monkeypatch.setattr(ts, "summarize_transcript", lambda *a, **k: "# Notes")
        self._install_settings_for_dialog()
        dlg, app = self._make_dialog()
        mp4 = _build_mp4(tmp_path)
        out_dir = tmp_path / "vid_out"
        opts = {
            "filepath": str(mp4),
            "output_folder": str(out_dir),
            "whisper_model": "tiny",
            "llm_model": "model-a",
            "save_raw": True,
            "save_summary": False,
        }
        results = dlg._do_transcribe(opts)
        assert results["error"] is None
        assert results["raw_path"] and Path(results["raw_path"]).exists()
        # the REAL ffmpeg extraction produced the temp wav fed to the engine…
        # (size captured at call time — the file is cleaned up after)
        assert sizes["wav"] > 4000
        # …and it was cleaned up afterwards
        assert not (out_dir / "clip_audio.wav").exists()
        app.processEvents()


# ── Layer 2: LIVE LLM — the podcast script through the real shim ────────────


@pytest.mark.live_llm
@pytest.mark.skipif(not _shim_live(), reason="zai-llamacpp shim :3031 not reachable")
class TestLivePodcastScript:
    def test_live_script_through_shim_full_pipeline(self):
        from core.podcast.script_generator import generate_podcast_script

        result = generate_podcast_script(
            source_text=SOURCE_2B,
            mode="conversational",
            tone="casual",
            temperature=0.7,
            language="en",
            ollama_url=_SHIM_URL,
            model=_SHIM_MODEL,
        )
        assert result.error is None, result.error
        assert result.bullets_input and len(result.bullets_input) == 2
        # Speaker turns: a real 2-host conversation.
        hosts = {ln.host for ln in result.lines}
        assert hosts == {"A", "B"}, hosts
        assert len(result.lines) >= 4
        # Segment structure: intro → content → conclusion.
        segs = {ln.segment_type for ln in result.lines}
        assert "content" in segs
        assert "intro" in segs and "conclusion" in segs
        # Deterministic coverage guarantee (gap-fill + force-insert).
        assert result.bullets_missing == []
        assert result.coverage_pct == 1.0
        assert result.title, "title should be generated (LLM or fallback)"
        txt = result.to_dialogue_text()
        assert txt.count("[Host A]") >= 1 and txt.count("[Host B]") >= 1


@pytest.mark.live_llm
@pytest.mark.skipif(not _shim_live(), reason="zai-llamacpp shim :3031 not reachable")
class TestLiveSummarizeTranscript:
    def test_live_llamacpp_provider_summary(self):
        """T2 live pin: with ``summarisation.provider=llamacpp`` pointed at
        the shim, the transcribe summary path runs through the REAL
        LlamaCppProvider → OpenAI-compatible /v1/chat/completions."""
        _install_settings(
            {
                "summarisation.provider": "llamacpp",
                "summarisation.llamacpp_base_url": _SHIM_V1,
                "summarisation.llamacpp_model": _SHIM_MODEL,
                "summarisation.llamacpp_api_key": "local",
            }
        )
        from core.transcribe.transcribe_service import summarize_transcript

        out = summarize_transcript(
            "The recording describes how bees pollinate plants and how a "
            "honeybee colony divides its labor. It mentions queens, workers, "
            "and drones as the three castes.",
            model=_SHIM_MODEL,
        )
        assert not out.startswith("Error:"), out
        assert len(out) > 40


# ── Layer 3: full dialog/view drives (real worker threads) ──────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTranscribeDialogDrive:
    def _stub_seam(
        self, monkeypatch, transcribe_ret=None, summarize_ret="# Summary\n\n- point", raise_exc=None
    ):
        import core.transcribe.transcribe_service as ts

        def _fake_transcribe(audio_path, model_size="small", **kwargs):
            if raise_exc:
                raise raise_exc
            if isinstance(transcribe_ret, dict):
                return transcribe_ret
            return {
                "text": "hello from the fake engine text",
                "segments": [{"start": 0.0, "end": 1.5, "text": "hello"}],
                "language": "en",
                "duration": 1.5,
            }

        def _fake_summarize(transcript, model="m", ollama_url="", **kwargs):
            return summarize_ret

        monkeypatch.setattr(ts, "transcribe_audio", _fake_transcribe)
        monkeypatch.setattr(ts, "summarize_transcript", _fake_summarize)
        return ts

    def _drive(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog as tmod

        rec = _make_msg_recorder(tmod, monkeypatch)
        dlg = tmod.TranscribeServiceDialog(_StubController())
        dlg.file_edit.setText(str(_build_wav(tmp_path)))
        dlg.out_edit.setText(str(tmp_path / "drive_out"))
        dlg._on_process()
        return dlg, app, rec

    def _spin_done(self, app, dlg, timeout_s=30.0):
        return _spin(app, lambda: dlg.process_btn.text() == "🎙️ Transcribe", timeout_s)

    def test_full_flow_success_status_and_modal(self, tmp_path, monkeypatch):
        self._stub_seam(monkeypatch)
        dlg, app, rec = self._drive(tmp_path, monkeypatch)
        assert self._spin_done(app, dlg)
        assert dlg._worker is not None
        dlg._worker.wait(5000)
        status = dlg.status_label.text()
        assert status.startswith("✅ Done!"), status
        assert "sample_transcript.md" in status and "sample_summary.md" in status
        assert (tmp_path / "drive_out" / "sample_transcript.md").exists()
        assert (tmp_path / "drive_out" / "sample_summary.md").exists()
        # information modal recorded, never exec'd
        assert rec.calls and rec.calls[0][0] == "information"
        assert "Transcription Complete" in rec.calls[0][1]
        app.processEvents()

    def test_engine_error_lands_critical_modal(self, tmp_path, monkeypatch):
        self._stub_seam(
            monkeypatch,
            transcribe_ret={
                "error": "faster-whisper not installed. Run: pip install faster-whisper"
            },
        )
        dlg, app, rec = self._drive(tmp_path, monkeypatch)
        assert self._spin_done(app, dlg)
        dlg._worker.wait(5000)
        assert dlg.status_label.text().startswith("❌")
        assert "faster-whisper" in dlg.status_label.text()
        assert rec.calls and rec.calls[0][0] == "critical"
        assert not (tmp_path / "drive_out" / "sample_transcript.md").exists()
        app.processEvents()

    def test_worker_exception_lands_failed_path(self, tmp_path, monkeypatch):
        self._stub_seam(monkeypatch, raise_exc=ValueError("engine blew up"))
        dlg, app, rec = self._drive(tmp_path, monkeypatch)
        assert self._spin_done(app, dlg)
        dlg._worker.wait(5000)
        assert dlg.status_label.text().startswith("❌ Error:")
        assert "engine blew up" in dlg.status_label.text()
        assert rec.calls and rec.calls[0][0] == "critical"
        assert dlg.process_btn.isEnabled()
        app.processEvents()

    def test_missing_file_guard_no_worker(self, monkeypatch):
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog as tmod

        rec = _make_msg_recorder(tmod, monkeypatch)
        dlg = tmod.TranscribeServiceDialog(_StubController())
        dlg.out_edit.setText("/tmp/whatever")
        dlg._on_process()
        assert rec.calls and rec.calls[0][0] == "warning"
        assert dlg._worker is None

        # point at a nonexistent path
        dlg.file_edit.setText("/nonexistent/nope.wav")
        dlg._on_process()
        assert len(rec.calls) == 2 and rec.calls[1][0] == "warning"
        assert dlg._worker is None

    def test_missing_output_guard_no_worker(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog as tmod

        rec = _make_msg_recorder(tmod, monkeypatch)
        dlg = tmod.TranscribeServiceDialog(_StubController())
        dlg.file_edit.setText(str(_build_wav(tmp_path)))
        dlg.out_edit.setText("")
        dlg._on_process()
        assert rec.calls and rec.calls[0][0] == "warning"
        assert dlg._worker is None


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestPodcastMakerViewDrive:
    def _canned_result(self, error=None):
        from core.podcast.script_generator import ScriptResult

        return ScriptResult(
            lines=[
                _mkline("A", "Opening hook line for the show.", "hook", "intro"),
                _mkline("B", "A reply that reacts to the hook.", "bullet 1", "content"),
                _mkline("A", "Closing takeaway for the listener.", "takeaways", "conclusion"),
            ],
            bullets_input=["bullet one text", "bullet two text"],
            bullets_covered=[0, 1],
            coverage_pct=1.0,
            title="Canned Show",
            error=error,
        )

    def _make_view(self, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.podcast_maker_view as pm

        _make_msg_recorder(pm, monkeypatch)
        view = pm.PodcastMakerView(_StubController())
        return view, app, pm

    def _drive(self, view, source=SOURCE_2B):
        view.input_text.setPlainText(source)
        view._on_generate_script()

    def _spin_done(self, app, view, timeout_s=30.0):
        return _spin(app, lambda: view.gen_script_btn.isEnabled(), timeout_s)

    def test_success_flow_populates_preview_and_coverage(self, tmp_path, monkeypatch):
        view, app, pm = self._make_view(monkeypatch)
        calls: list[dict] = []

        def _fake_generate(**kwargs):
            calls.append(kwargs)
            return self._canned_result()

        monkeypatch.setattr(pm, "generate_podcast_script", _fake_generate)
        self._drive(view)
        assert self._spin_done(app, view)
        assert view._worker is not None
        view._worker.join(5)
        preview = view.script_preview.toPlainText()
        assert preview.startswith("[Host A] Opening hook line")
        assert "[Host B] A reply that reacts" in preview
        cov = view.coverage_label.text()
        assert cov.startswith("✅ Coverage: 2/2 (100%)")
        assert view.gen_audio_btn.isEnabled() and view.export_script_btn.isEnabled()
        assert view.status_label.text().startswith("✅ Script ready!")
        # the worker forwarded the UI options (batch-B settings-injection
        # seam: ollama_url comes from Settings inside _work)
        assert calls[0]["mode"] == "conversational"
        assert calls[0]["source_text"] == SOURCE_2B
        app.processEvents()

    def test_options_forwarded_from_combos(self, monkeypatch):
        view, app, pm = self._make_view(monkeypatch)
        calls: list[dict] = []

        def _fake_generate(**kwargs):
            calls.append(kwargs)
            return self._canned_result()

        monkeypatch.setattr(pm, "generate_podcast_script", _fake_generate)
        view.mode_combo.setCurrentIndex(0)  # lecture
        view.lang_combo.setCurrentIndex(1)  # fa
        self._drive(view)
        assert self._spin_done(app, view)
        view._worker.join(5)
        assert calls[0]["mode"] == "lecture"
        assert calls[0]["language"] == "fa"
        app.processEvents()

    def test_error_result_lands_error_status(self, monkeypatch):
        view, app, pm = self._make_view(monkeypatch)
        monkeypatch.setattr(
            pm,
            "generate_podcast_script",
            lambda **kw: self._canned_result(error="LLM call failed: boom"),
        )
        self._drive(view)
        assert self._spin_done(app, view)
        view._worker.join(5)
        assert view.status_label.text().startswith("❌ LLM call failed: boom")
        assert not view.gen_audio_btn.isEnabled()
        app.processEvents()

    def test_worker_exception_lands_failed_status(self, monkeypatch):
        view, app, pm = self._make_view(monkeypatch)

        def _boom(**kw):
            raise RuntimeError("worker exploded")

        monkeypatch.setattr(pm, "generate_podcast_script", _boom)
        self._drive(view)
        assert self._spin_done(app, view)
        view._worker.join(5)
        assert view.status_label.text().startswith("❌ Script generation failed: worker exploded")
        app.processEvents()

    def test_empty_input_guard_no_worker(self, monkeypatch):
        view, app, pm = self._make_view(monkeypatch)
        rec = pm.QMessageBox
        view.input_text.setPlainText("   ")
        view._on_generate_script()
        assert view._worker is None
        assert rec.calls and rec.calls[0][0] == "warning"

    def test_import_script_roundtrip(self, tmp_path, monkeypatch):
        """The Import button path: ScriptResult.from_json → preview +
        audio button enabled (V11.49.0 contract)."""
        view, app, pm = self._make_view(monkeypatch)
        path = tmp_path / "script.json"
        path.write_text(self._canned_result().to_json(), encoding="utf-8")
        from core.podcast.script_generator import ScriptResult

        result = ScriptResult.from_json(path.read_text(encoding="utf-8"))
        view._script_result = result
        view.script_preview.setPlainText(result.to_dialogue_text())
        view.gen_audio_btn.setEnabled(True)
        assert "Opening hook line" in view.script_preview.toPlainText()
        app.processEvents()


@pytest.mark.live_llm
@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _shim_live(), reason="zai-llamacpp shim :3031 not reachable")
class TestLivePodcastMakerViewDrive:
    def test_live_drive_through_shim(self, tmp_path, monkeypatch):
        """The full view drive with the REAL LLM: Settings injection points
        ``summarisation.ollama_url`` at the shim's Ollama-shape endpoint;
        the worker thread makes the real /api/generate call."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.podcast_maker_view as pm

        _make_msg_recorder(pm, monkeypatch)
        _install_settings({"summarisation.ollama_url": _SHIM_URL})
        view = pm.PodcastMakerView(_StubController())
        view.model_combo.setCurrentText(_SHIM_MODEL)
        view.input_text.setPlainText(SOURCE_2B)
        view._on_generate_script()
        assert _spin(app, lambda: view.gen_script_btn.isEnabled(), 240.0)
        view._worker.join(10)
        assert view._script_result is not None
        assert view._script_result.error is None, view._script_result.error
        preview = view.script_preview.toPlainText()
        assert preview.count("[Host A]") >= 1 and preview.count("[Host B]") >= 1
        assert view.coverage_label.text().startswith("✅ Coverage: 2/2 (100%)")
        assert view.gen_audio_btn.isEnabled()
        app.processEvents()
