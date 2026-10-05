"""Phase-5 P1 / W8 (first tranche): characterization net for
``core/pipeline/conversion/output_runner.py`` (``run_output_studio``).

WHY THIS FILE EXISTS
--------------------
The Phase-7 SWOT (Task 12-19) flagged the 3 ``conversion/*`` stage runners
as the "extracted ≠ tested" debt (W8 / Phase-5 P1): ``postprocess`` (22%
cov), ``visual_features`` (25%), ``output_runner`` (38%).  This file is the
output_runner installment — the sibling of
``test_conversion_postprocess_characterization.py`` and
``test_conversion_visual_features_characterization.py``.

The runner (V8.0.0 #9 / V10.6.0 Phase 8A-1: synced with the inline
converter version) iterates over enabled output generators from the
17-entry ``OUTPUT_PLAN``, calls each one, and collects results.
``test_conversion_modules.py:583-664`` already pins the signature + the
17-entry count + the empty-summaries-returns-{} contract; this file pins
the RUNTIME BEHAVIOR of the runner: the actual OUTPUT_PLAN entries
(attr/status/msg/cls/subfolder), the chapters_md write path, the
evidence_map 4-arg call, the flashcards judge_results kwarg, the TTS
diagnostics call, the progress_callback contract, the retry/backoff
logic, the checkpoint phase-level resume, and the packets-extensions
runner.

All hermetic (no ~/.elixir, no network, no Qt, no real conversion —
fake ``paths`` + ``request`` + a ``_FakeGen`` class swapped in via
``monkeypatch`` on ``core.outputs.<ClassName>`` so the test pins the
runner's behavior without invoking the real generators' LLM/PDF stacks).

All expected values were probed empirically against the live code before
writing (no invented expected values); all fixtures use generic content
("MyBook", "Chapter One") per AGENTS.md Rule 1.

Run: ``pytest tests/test_conversion_output_runner_characterization.py -v --no-cov``
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.outputs as _outputs
from core.pipeline.conversion.output_runner import (
    OUTPUT_PLAN,
    _log_tts_diagnostics,
    _run_packets_extensions,
    run_output_studio,
)

# ════════════════════════════════════════════════════════════════════════════
# Section 0 — hermetic fakes (Phase-3 _RecordingSelf precedent)
# ════════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_RUNNER_SRC_PATH = _PROJECT_ROOT / "core" / "pipeline" / "conversion" / "output_runner.py"


def output_runner_src() -> str:
    """The current output_runner.py source (for source-pin tests)."""
    return _OUTPUT_RUNNER_SRC_PATH.read_text(encoding="utf-8")


class _FakePaths:
    """Stand-in for OutputPaths — provides packets_dir, podcast_script(), and
    every OUTPUT_PLAN subfolder_attr (briefing_dir, podcast_dir, etc.)."""

    def __init__(self, base_dir=None):
        self._base = base_dir or Path("/tmp/_or_char_probe")
        self._base.mkdir(parents=True, exist_ok=True)
        self.packets_dir = self._base / "packets"
        self.packets_dir.mkdir(parents=True, exist_ok=True)
        # All the OUTPUT_PLAN subfolder_attrs (must exist so the enabled-list
        # comprehension `getattr(paths, sub_attr)` doesn't AttributeError).
        for sub in (
            "briefing_dir",
            "podcast_dir",
            "flashcards_dir",
            "obsidian_dir",
            "study_guide_dir",
            "social_dir",
            "mindmap_dir",
            "evidence_dir",
            "qa_dir",
            "glossary_dir",
            "patterns_dir",
            "cheatsheet_dir",
            "skill_dir",
            "epub_dir",
            "quote_bank_dir",
        ):
            d = self._base / sub
            d.mkdir(parents=True, exist_ok=True)
            setattr(self, sub, d)

    def podcast_script(self, book_title):
        return self._base / f"{book_title}.podcast.md"


class _FakeRequest:
    """Stand-in for ConversionRequest — has all 17 output_* flags (OFF by
    default)."""

    _OUTPUT_ATTRS = (
        "output_briefing",
        "output_podcast",
        "output_packets",
        "output_flashcards",
        "output_obsidian",
        "output_study_guide",
        "output_social",
        "output_mindmap",
        "output_tts",
        "output_evidence_map",
        "output_qa",
        "output_glossary",
        "output_patterns",
        "output_cheatsheet",
        "output_skill",
        "output_epub",
        "output_quote_bank",
    )

    def __init__(self, **overrides):
        for attr in self._OUTPUT_ATTRS:
            setattr(self, attr, False)
        for k, v in overrides.items():
            setattr(self, k, v)


class _FakeGen:
    """Fake generator class — records the generate() call (args + kwargs)
    and supports the fail-then-succeed + always-fail patterns for the
    retry tests. Class-level state so tests can reset between runs."""

    instances_created: list = []
    generate_calls: list = []
    raise_on_generate: Exception | None = None
    fail_n_times: int = 0

    def __init__(self, request, log_callback=None):
        self.request = request
        self.log = log_callback
        _FakeGen.instances_created.append(self)

    def generate(self, *args, **kwargs):
        _FakeGen.generate_calls.append({"args": list(args), "kwargs": kwargs})
        if _FakeGen.raise_on_generate is not None:
            raise _FakeGen.raise_on_generate
        if _FakeGen.fail_n_times > 0:
            _FakeGen.fail_n_times -= 1
            raise RuntimeError(f"transient failure ({_FakeGen.fail_n_times + 1} left)")


@pytest.fixture(autouse=True)
def _reset_fake_gen():
    """Reset _FakeGen class-level state before each test."""
    _FakeGen.instances_created = []
    _FakeGen.generate_calls = []
    _FakeGen.raise_on_generate = None
    _FakeGen.fail_n_times = 0
    yield


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Stub time.sleep so retry-backoff tests don't actually sleep."""
    monkeypatch.setattr(time, "sleep", lambda s: None)


def _stub_outputs(monkeypatch, mapping):
    """Patch core.outputs.<ClassName> = _FakeGen for each cls_name in mapping."""
    for cls_name in mapping:
        monkeypatch.setattr(_outputs, cls_name, _FakeGen, raising=True)


def _make_summary(heading="Ch1"):
    """Build a minimal SummaryResult stand-in (the runner reads
    chapter_heading/bullet_points/executive_summary/thorough_summary/success)."""
    return SimpleNamespace(
        chapter_heading=heading,
        bullet_points=[],
        executive_summary="exec text",
        thorough_summary="thorough text",
        success=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. OUTPUT_PLAN — the 17 entries (attr, status, msg, cls, subfolder)
# ════════════════════════════════════════════════════════════════════════════


class TestOutputPlanEntries:
    """Pin the exact 17 OUTPUT_PLAN entries — attr, status_label, log_message,
    generator_class_name, subfolder_attr (V10.35.0: +2 epub + quote_bank)."""

    def test_output_plan_has_17_entries(self):
        assert len(OUTPUT_PLAN) == 17

    def test_output_plan_attrs_in_order(self):
        attrs = [e[0] for e in OUTPUT_PLAN]
        assert attrs == [
            "output_briefing",
            "output_podcast",
            "output_packets",
            "output_flashcards",
            "output_obsidian",
            "output_study_guide",
            "output_social",
            "output_mindmap",
            "output_tts",
            "output_evidence_map",
            "output_qa",
            "output_glossary",
            "output_patterns",
            "output_cheatsheet",
            "output_skill",
            "output_epub",
            "output_quote_bank",
        ]

    def test_output_plan_status_labels_in_order(self):
        statuses = [e[1] for e in OUTPUT_PLAN]
        # Spot-check a few key ones (full list pinned via the attrs test).
        assert statuses[0] == "Generating Executive Briefing…"
        assert statuses[8] == "Generating Podcast Audio (TTS)…"
        assert statuses[9] == "Generating Scientific Evidence Map…"
        assert statuses[15] == "Generating EPUB…"
        assert statuses[16] == "Generating Quote Bank…"

    def test_output_plan_generator_class_names_in_order(self):
        clss = [e[3] for e in OUTPUT_PLAN]
        # Pin a few key generator class names.
        assert clss[0] == "ExecutiveBriefingGenerator"
        assert clss[8] == "PodcastAudioGenerator"
        assert clss[9] == "EvidenceMapGenerator"
        assert clss[15] == "EPUBGenerator"
        assert clss[16] == "QuoteBankGenerator"

    def test_output_plan_subfolder_attrs_in_order(self):
        subs = [e[4] for e in OUTPUT_PLAN]
        assert subs[0] == "briefing_dir"
        assert subs[8] == "podcast_dir"  # TTS uses podcast_dir (same as podcast script)
        assert subs[9] == "evidence_dir"
        assert subs[15] == "epub_dir"
        assert subs[16] == "quote_bank_dir"

    def test_output_plan_log_messages_pin_key_emojis(self):
        """Pin a few key log-message skeletons (the visible-to-user status
        lines). A future wording change breaks the test."""
        msgs = [e[2] for e in OUTPUT_PLAN]
        assert msgs[0].startswith("📄 Generating executive briefing")
        assert msgs[2].startswith("📦 Generating Packets of Knowledge")
        assert msgs[3].startswith("🎴 Generating flashcards")
        assert msgs[8].startswith("🎙️ Generating podcast audio")
        assert msgs[9].startswith("🗺️ Generating scientific evidence map")


# ════════════════════════════════════════════════════════════════════════════
# 2. Empty summaries + no enabled outputs (the no-op paths)
# ════════════════════════════════════════════════════════════════════════════


class TestEmptyAndNoEnabledPaths:
    """The two no-op paths: empty summaries (early return {} silently) and
    no enabled outputs (DEBUG log + return {})."""

    def test_empty_summaries_returns_empty_dict_silently(self):
        """`if not summaries: return results` (empty dict) — no logs, no
        statuses (the chapters_md path is also skipped)."""
        logs = []
        statuses = []
        result = run_output_studio(
            request=_FakeRequest(output_briefing=True),  # enabled but no summaries
            summaries=[],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: statuses.append(s),
        )
        assert result == {}
        assert logs == []
        assert statuses == []

    def test_no_enabled_outputs_emits_debug_log(self):
        """When no output_* flag is True, the DEBUG 'No Output Studio
        outputs enabled' log fires + returns {}."""
        logs = []
        statuses = []
        result = run_output_studio(
            request=_FakeRequest(),  # all outputs OFF
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: statuses.append(s),
        )
        assert result == {}
        debug_msgs = [m for m, l in logs if l == "DEBUG"]
        assert any("No Output Studio outputs enabled" in m for m in debug_msgs), (
            f"expected 'No Output Studio outputs enabled' DEBUG log, got: {debug_msgs}"
        )


# ════════════════════════════════════════════════════════════════════════════
# 3. The chapters_md write path (output_packets=True)
# ════════════════════════════════════════════════════════════════════════════


class TestChaptersMdWritePath:
    """When output_packets=True, the runner writes a {Book}.Chapters.md file
    + adds 'chapters_md' = '✅ done' to the results dict (V13.23.0)."""

    def test_chapters_md_info_log(self, monkeypatch):
        _stub_outputs(monkeypatch, {"PacketGenerator": _FakeGen})
        logs = []
        run_output_studio(
            request=_FakeRequest(output_packets=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        info_msgs = [m for m, l in logs if l == "INFO"]
        assert any("📄 Chapters file written: MyBook.Chapters.md" in m for m in info_msgs), (
            f"expected 'Chapters file written' INFO log, got: {info_msgs}"
        )

    def test_chapters_md_result_entry(self, monkeypatch):
        _stub_outputs(monkeypatch, {"PacketGenerator": _FakeGen})
        result = run_output_studio(
            request=_FakeRequest(output_packets=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        # The chapters_md entry is added BEFORE the packets generator runs.
        assert result.get("chapters_md") == "✅ done"

    def test_chapters_md_file_actually_written(self, monkeypatch):
        _stub_outputs(monkeypatch, {"PacketGenerator": _FakeGen})
        paths = _FakePaths()
        run_output_studio(
            request=_FakeRequest(output_packets=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=paths,
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        chapters_md = paths.packets_dir / "MyBook.Chapters.md"
        assert chapters_md.exists()

    def test_chapters_md_failure_records_failed_entry(self, monkeypatch):
        """When write_chapters_md raises, the runner records
        'chapters_md' = '❌ failed: <error>' + WARNING log."""
        # Patch write_chapters_md to raise.
        from core.outputs import chapters_export

        def _raise(*args, **kwargs):
            raise RuntimeError("chapters export failed")

        monkeypatch.setattr(chapters_export, "write_chapters_md", _raise)
        logs = []
        result = run_output_studio(
            request=_FakeRequest(output_packets=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        warn_msgs = [m for m, l in logs if l == "WARNING"]
        assert any("Chapters file export failed" in m for m in warn_msgs)
        assert result.get("chapters_md", "").startswith("❌ failed:")


# ════════════════════════════════════════════════════════════════════════════
# 4. The standard 3-arg generate() call shape (most outputs)
# ════════════════════════════════════════════════════════════════════════════


class TestStandardGenerateCallShape:
    """Most outputs call gen.generate(summaries, book_title, out_subdir)
    — the 3-arg shape. Pin it on output_briefing (the simplest case)."""

    def test_standard_generate_called_with_3_args(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        summaries = [_make_summary()]
        run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=summaries,
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        assert len(_FakeGen.generate_calls) == 1
        call = _FakeGen.generate_calls[0]
        # 3 positional args: summaries, book_title, out_subdir.
        assert call["args"][0] is summaries
        assert call["args"][1] == "MyBook"
        # The out_subdir is paths.briefing_dir (a Path).
        assert call["args"][2].name == "briefing_dir"
        # No kwargs on the standard path.
        assert call["kwargs"] == {}

    def test_standard_generate_status_and_info_log(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        logs = []
        statuses = []
        run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: statuses.append(s),
        )
        info_msgs = [m for m, l in logs if l == "INFO"]
        # The msg from OUTPUT_PLAN[0]: "📄 Generating executive briefing (1-page synthesis)…"
        assert any("📄 Generating executive briefing" in m for m in info_msgs)
        # The success log uses gen_cls.__name__ (_FakeGen — with the leading
        # underscore, since that's the test's class name).
        assert any(f"✅ {_FakeGen.__name__} completed successfully" in m for m in info_msgs)
        # Status update from OUTPUT_PLAN[0][1]: "Generating Executive Briefing…"
        assert "Generating Executive Briefing…" in statuses

    def test_standard_generate_success_records_done_entry(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        result = run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        assert result["output_briefing"] == "✅ done"


# ════════════════════════════════════════════════════════════════════════════
# 5. The 4-arg evidence_map call + the flashcards judge_results kwarg
# ════════════════════════════════════════════════════════════════════════════


class TestSpecialCaseGenerateSignatures:
    """Two outputs have special-case generate() signatures: evidence_map
    (4-arg: summaries, segments, book_title, out_subdir) and flashcards
    (3-arg + judge_results kwarg)."""

    def test_evidence_map_generate_called_with_4_args(self, monkeypatch):
        _stub_outputs(monkeypatch, {"EvidenceMapGenerator": _FakeGen})
        summaries = [_make_summary()]
        segments = [SimpleNamespace(name="Seg1", content="seg content")]
        run_output_studio(
            request=_FakeRequest(output_evidence_map=True),
            summaries=summaries,
            segments=segments,
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        assert len(_FakeGen.generate_calls) == 1
        call = _FakeGen.generate_calls[0]
        # 4 positional args: summaries, segments, book_title, out_subdir.
        assert len(call["args"]) == 4
        assert call["args"][0] is summaries
        assert call["args"][1] is segments
        assert call["args"][2] == "MyBook"
        assert call["args"][3].name == "evidence_dir"

    def test_flashcards_generate_called_with_judge_results_kwarg(self, monkeypatch):
        _stub_outputs(monkeypatch, {"FlashcardGenerator": _FakeGen})
        judge_results = [SimpleNamespace(verdict="PASS")]
        run_output_studio(
            request=_FakeRequest(output_flashcards=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            judge_results=judge_results,
        )
        assert len(_FakeGen.generate_calls) == 1
        call = _FakeGen.generate_calls[0]
        # 3 positional args + the judge_results kwarg.
        assert len(call["args"]) == 3
        assert call["kwargs"] == {"judge_results": judge_results}

    def test_flashcards_judge_results_defaults_to_none(self, monkeypatch):
        """When judge_results is not passed to run_output_studio, it
        defaults to None and is passed as judge_results=None to gen.generate."""
        _stub_outputs(monkeypatch, {"FlashcardGenerator": _FakeGen})
        run_output_studio(
            request=_FakeRequest(output_flashcards=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
        )
        assert _FakeGen.generate_calls[0]["kwargs"] == {"judge_results": None}


# ════════════════════════════════════════════════════════════════════════════
# 6. The TTS diagnostics path (output_tts → _log_tts_diagnostics)
# ════════════════════════════════════════════════════════════════════════════


class TestTtsDiagnosticsCall:
    """When output_tts is enabled, the runner calls _log_tts_diagnostics
    AFTER instantiating the generator but BEFORE calling generate(). Pin
    that the 12 TTS-diagnostic INFO logs fire."""

    def test_tts_diagnostics_logs_fire(self, monkeypatch):
        _stub_outputs(monkeypatch, {"PodcastAudioGenerator": _FakeGen})
        logs = []
        run_output_studio(
            request=_FakeRequest(output_tts=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        info_msgs = [m for m, l in logs if l == "INFO"]
        # The 12 TTS-diagnostic INFO logs.
        assert any("🎙️ TTS Audio Generation Details:" in m for m in info_msgs)
        assert any(m.strip().startswith("TTS enabled:") for m in info_msgs)
        assert any(m.strip().startswith("EN engine:") for m in info_msgs)
        assert any(m.strip().startswith("Piper binary:") for m in info_msgs)
        assert any(m.strip().startswith("Speed:") for m in info_msgs)

    def test_log_tts_diagnostics_function_directly(self):
        """_log_tts_diagnostics is also a public function — pin its
        12-INFO-log behavior directly (no run_output_studio needed)."""
        logs = []
        _log_tts_diagnostics(
            log=lambda m, l: logs.append((m, l)),
            paths=_FakePaths(),
            book_title="MyBook",
        )
        info_msgs = [m for m, l in logs if l == "INFO"]
        # Empirically: 12 INFO logs (the header + 11 settings).
        assert len(info_msgs) == 12
        assert info_msgs[0] == "  🎙️ TTS Audio Generation Details:"
        assert info_msgs[1] == "    TTS enabled: True"


# ════════════════════════════════════════════════════════════════════════════
# 7. The progress_callback contract (V10.35.0)
# ════════════════════════════════════════════════════════════════════════════


class TestProgressCallbackContract:
    """progress_callback(attr, 0.0) fires BEFORE generate() + (attr, 1.0)
    fires AFTER (both on success AND on final failure)."""

    def test_progress_0_then_1_on_success(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        progress_calls = []
        run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            progress_callback=lambda attr, frac: progress_calls.append((attr, frac)),
        )
        assert progress_calls == [("output_briefing", 0.0), ("output_briefing", 1.0)]

    def test_progress_1_on_final_failure(self, monkeypatch):
        """All 3 retries fail → progress_callback still fires (attr, 1.0)
        at the end (the 'even on failure' comment in the source)."""
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        _FakeGen.raise_on_generate = RuntimeError("permanent")
        progress_calls = []
        run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            progress_callback=lambda attr, frac: progress_calls.append((attr, frac)),
        )
        # 0.0 before, 1.0 at the end (after all retries exhausted).
        assert progress_calls == [("output_briefing", 0.0), ("output_briefing", 1.0)]


# ════════════════════════════════════════════════════════════════════════════
# 8. The retry-with-backoff logic (V10.34.0)
# ════════════════════════════════════════════════════════════════════════════


class TestRetryWithBackoff:
    """3 attempts: 1s / 2s / 4s exponential backoff (V10.34.0). On
    transient failure, the WARNING log fires per attempt with the
    backoff seconds + the attempt number; on success-after-retries, the
    SUCCESS log includes '(attempt N/N)'; on all-fail, the ERROR log
    + 'failed after 3 retries' result string fire."""

    def test_transient_failure_then_success_logs_warning_per_attempt(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        _FakeGen.fail_n_times = 2  # fail first 2 attempts, succeed on 3rd
        logs = []
        result = run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        warn_msgs = [m for m, l in logs if l == "WARNING"]
        # Empirically: 2 WARNINGs (attempt 1 + 2), backoff 1s then 2s.
        assert any("attempt 1/3" in m and "retrying in 1s" in m for m in warn_msgs)
        assert any("attempt 2/3" in m and "retrying in 2s" in m for m in warn_msgs)
        # SUCCESS on attempt 3/3.
        info_msgs = [m for m, l in logs if l == "INFO"]
        assert any(
            f"✅ {_FakeGen.__name__} completed successfully (attempt 3/3)" in m for m in info_msgs
        )
        # generate() called 3 times (once per attempt).
        assert len(_FakeGen.generate_calls) == 3
        # Result records success.
        assert result["output_briefing"] == "✅ done"

    def test_all_retries_fail_logs_error_and_records_failed_entry(self, monkeypatch):
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        _FakeGen.raise_on_generate = RuntimeError("permanent failure")
        logs = []
        result = run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        error_msgs = [m for m, l in logs if l == "ERROR"]
        # Empirically: ERROR log "❌ _FakeGen failed after 3 attempts: permanent failure"
        # (the log uses gen_cls.__name__, which is '_FakeGen' here).
        assert any(
            f"❌ {_FakeGen.__name__} failed after 3 attempts: permanent failure" in m
            for m in error_msgs
        )
        # Result records the failure with the 'failed after 3 retries:' prefix.
        assert result["output_briefing"] == "❌ failed after 3 retries: permanent failure"
        # generate() called 3 times.
        assert len(_FakeGen.generate_calls) == 3

    def test_no_retry_log_on_first_attempt_success(self, monkeypatch):
        """When the first attempt succeeds, no WARNING retry log fires."""
        _stub_outputs(monkeypatch, {"ExecutiveBriefingGenerator": _FakeGen})
        logs = []
        run_output_studio(
            request=_FakeRequest(output_briefing=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
        )
        warn_msgs = [m for m, l in logs if l == "WARNING"]
        assert not any("retrying in" in m for m in warn_msgs)


# ════════════════════════════════════════════════════════════════════════════
# 9. The checkpoint phase-level resume (V13.25.0 P1.1)
# ════════════════════════════════════════════════════════════════════════════


class _FakeCheckpoint:
    """Fake CheckpointManager — is_done returns True for phases in
    _done_phases."""

    def __init__(self, done_phases=()):
        self._done_phases = set(done_phases)

    def is_done(self, phase):
        return phase in self._done_phases


class TestCheckpointPhaseResume:
    """When a checkpoint is provided, output phases already marked done are
    skipped — the '⏭️ Phase-level resume' INFO log + the '✅ already done
    (skipped — resume)' result string. The special phase-name mappings
    (output_tts → podcast_audio, output_evidence_map → evidence_map,
    output_podcast → podcast_script, etc.) are pinned."""

    def test_skipped_phase_logs_info_message(self, monkeypatch):
        _stub_outputs(monkeypatch, {"GlossaryGenerator": _FakeGen})
        logs = []
        result = run_output_studio(
            request=_FakeRequest(output_glossary=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            update_status=lambda s: None,
            checkpoint=_FakeCheckpoint(done_phases={"glossary"}),
        )
        info_msgs = [m for m, l in logs if l == "INFO"]
        assert any(
            "⏭️ Phase-level resume: skipping 1 already-completed output(s): glossary" in m
            for m in info_msgs
        ), f"expected 'Phase-level resume' INFO log, got: {info_msgs}"
        # Result records the skip.
        assert result["output_glossary"] == "✅ already done (skipped — resume)"
        # The fake generator was NOT instantiated (skip path).
        assert len(_FakeGen.instances_created) == 0

    def test_skipped_phase_fires_progress_1_0(self, monkeypatch):
        """progress_callback fires (attr, 1.0) for the skipped phase."""
        _stub_outputs(monkeypatch, {"GlossaryGenerator": _FakeGen})
        progress_calls = []
        run_output_studio(
            request=_FakeRequest(output_glossary=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            progress_callback=lambda attr, frac: progress_calls.append((attr, frac)),
            checkpoint=_FakeCheckpoint(done_phases={"glossary"}),
        )
        assert progress_calls == [("output_glossary", 1.0)]

    def test_tts_phase_name_maps_to_podcast_audio(self, monkeypatch):
        """The output_tts attr maps to the 'podcast_audio' checkpoint phase
        (the special-mapping dict in the source)."""
        _stub_outputs(monkeypatch, {"PodcastAudioGenerator": _FakeGen})
        result = run_output_studio(
            request=_FakeRequest(output_tts=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            checkpoint=_FakeCheckpoint(done_phases={"podcast_audio"}),
        )
        # TTS was skipped (the special mapping output_tts → podcast_audio).
        assert result["output_tts"] == "✅ already done (skipped — resume)"

    def test_evidence_map_phase_name_maps_to_evidence_map(self, monkeypatch):
        _stub_outputs(monkeypatch, {"EvidenceMapGenerator": _FakeGen})
        result = run_output_studio(
            request=_FakeRequest(output_evidence_map=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            checkpoint=_FakeCheckpoint(done_phases={"evidence_map"}),
        )
        assert result["output_evidence_map"] == "✅ already done (skipped — resume)"

    def test_podcast_phase_name_maps_to_podcast_script(self, monkeypatch):
        _stub_outputs(monkeypatch, {"PodcastGenerator": _FakeGen})
        result = run_output_studio(
            request=_FakeRequest(output_podcast=True),
            summaries=[_make_summary()],
            segments=[],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            update_status=lambda s: None,
            checkpoint=_FakeCheckpoint(done_phases={"podcast_script"}),
        )
        assert result["output_podcast"] == "✅ already done (skipped — resume)"


# ════════════════════════════════════════════════════════════════════════════
# 10. _run_packets_extensions — the V8.0.0 #10 packets-extensions runner
# ════════════════════════════════════════════════════════════════════════════


class TestRunPacketsExtensions:
    """The V8.0.0 #10 packets-extensions runner (PDF, lecture, audio). Run
    after packets are generated. The function tries 3 extensions; each
    has its own fail-soft path."""

    def test_packs_pdf_attempted_first(self):
        """When called directly, the function tries PacketsPDFExporter.export
        first. Failure (no reportlab) records a WARNING + the result string
        (the success vs failure result depends on whether export() raises
        vs swallows internally — pin both possible outcomes via the call
        itself happening, not the exact result)."""
        logs = []
        results = {}
        # Call directly (not via run_output_studio — that gates on
        # packets_md existence).
        _run_packets_extensions(
            request=_FakeRequest(),
            summaries=[_make_summary()],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: logs.append((m, l)),
            results=results,
        )
        # The 'packets_pdf' key is always recorded (success or failure).
        assert "packets_pdf" in results
        # The 'packets_lecture' key is also always recorded.
        assert "packets_lecture" in results
        # packets_audio is only recorded when output_tts is True.

    def test_packs_audio_only_recorded_when_tts_enabled(self):
        """The 3rd extension (per-packet audio) only runs when output_tts is
        also enabled."""
        results = {}
        _run_packets_extensions(
            request=_FakeRequest(output_tts=True),
            summaries=[_make_summary()],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            results=results,
        )
        assert "packets_audio" in results

    def test_packs_audio_skipped_when_tts_disabled(self):
        results = {}
        _run_packets_extensions(
            request=_FakeRequest(output_tts=False),
            summaries=[_make_summary()],
            book_title="MyBook",
            paths=_FakePaths(),
            log=lambda m, l: None,
            results=results,
        )
        assert "packets_audio" not in results


# ════════════════════════════════════════════════════════════════════════════
# 11. Source-pin: the exact log-message literals are present in the source
# (Phase-3 source-pin precedent)
# ════════════════════════════════════════════════════════════════════════════


def _skeletons_of(source: str) -> set[str]:
    """Every string literal in source with f-string holes removed (Phase-3
    literal_skeletons() precedent)."""
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.add("".join(v.value for v in node.values if isinstance(v, ast.Constant)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


class TestSourcePinLogLiterals:
    """Pin the exact log-message skeletons present in output_runner.py
    source (Phase-3 source-pin precedent)."""

    def test_no_outputs_enabled_debug_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert (
            "  ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio)."
            in skeletons
        )

    def test_chapters_file_written_info_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  📄 Chapters file written: " in skeletons

    def test_chapters_file_export_failed_warning_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ⚠️ Chapters file export failed: " in skeletons

    def test_phase_level_resume_info_skeleton(self):
        """The 'Phase-level resume' INFO log is a multi-line f-string — use
        the 'any skeleton CONTAINING' check (constants are joined)."""
        skeletons = _skeletons_of(output_runner_src())
        matching = [
            s
            for s in skeletons
            if "⏭️ Phase-level resume: skipping " in s and " already-completed output(s): " in s
        ]
        assert matching, "expected 'Phase-level resume' log skeleton"

    def test_already_done_skipped_resume_result_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "✅ already done (skipped — resume)" in skeletons

    def test_generator_completed_successfully_info_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ✅ " in skeletons
        assert " completed successfully" in skeletons

    def test_generator_failed_attempt_warning_skeleton(self):
        """The retry WARNING log is a multi-line f-string."""
        skeletons = _skeletons_of(output_runner_src())
        matching = [
            s
            for s in skeletons
            if "  ⚠️ " in s
            and " failed (attempt " in s
            and "/" in s
            and "): " in s
            and " — retrying in " in s
            and "s…" in s
        ]
        assert matching, "expected retry WARNING log skeleton"

    def test_generator_failed_after_max_attempts_error_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ❌ " in skeletons
        assert " failed after " in skeletons
        assert " attempts: " in skeletons

    def test_failed_after_max_retries_result_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "❌ failed after " in skeletons
        assert " retries: " in skeletons

    def test_tts_diagnostics_header_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  🎙️ TTS Audio Generation Details:" in skeletons
        assert "    TTS enabled: True" in skeletons
        assert "    EN engine: " in skeletons
        assert "    Piper binary: " in skeletons
        assert "    Speed: " in skeletons

    def test_output_studio_module_unavailable_info_skeleton(self):
        """The ImportError branch log."""
        skeletons = _skeletons_of(output_runner_src())
        assert "  ℹ️ Output Studio module not available (V4.1.0)" in skeletons

    def test_output_studio_generation_skipped_debug_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ⚠️ Output Studio generation skipped: " in skeletons

    def test_packs_pdf_failed_warning_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ⚠️ Packets PDF export failed: " in skeletons

    def test_packs_lecture_failed_warning_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ⚠️ Packets lecture failed: " in skeletons

    def test_packs_audio_failed_warning_skeleton(self):
        skeletons = _skeletons_of(output_runner_src())
        assert "  ⚠️ Packets audio failed: " in skeletons

    def test_max_retries_constant_3(self):
        """The _max_retries = 3 constant (V10.34.0: 3 attempts with 1s/2s/4s
        exponential backoff)."""
        src = output_runner_src()
        assert "_max_retries = 3" in src
