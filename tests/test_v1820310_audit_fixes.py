"""V18.20.3.10 audit-fix regression tests (rig-audit F6 + SWOT riders).

Scope of this version (all approved by the user in the 2026-08-31 session):

  1. F6  — the B1 stamp-check false-positives: the .3.9 diagnostic peeked
           line 2, but chapter files stamp LINE 3 (title/blank/stamp) and
           book files stamp LINE 1, so every fresh file was flagged
           "NO generated-by stamp". Fixed by delegating to the canonical
           whole-text parser: ``provenance.stamp_diagnostic`` — behavioral
           tests below render a real stamped SummaryResult through
           ``render_summary_markdown`` and assert the checker finds it.
  2. W11 — library keypoints count recorded the RAW bullet count (41)
           while the keypoints file ships the DEDUPED count (36). The
           builder now exposes ``final_keypoint_count`` and the library
           uses it.
  3. F5  — known-cosmetic visibility classes: the empty-response retry
           line was DEBUG (invisible — the .3.7 rig had one), the
           models-at-exit line was a fake WARNING on every clean run.
  4. O7  — the opt-in response cache existed since V10.33/V13.35 but its
           effect was invisible (DEBUG-only hits, no run-level stats).
           The diagnostic now reports per-run hits/misses.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Stub the optional heavy deps exactly like tests/test_v18203_incremental_checkpoint.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

ROOT = Path(__file__).resolve().parent.parent


# ═════════════════════════════════════════════════════════════════════════════
# 1) F6 — stamp_diagnostic (behavioral: real render → real parse)
# ═════════════════════════════════════════════════════════════════════════════

from core.system.provenance import parse_provenance, stamp_diagnostic  # noqa: E402


def _mk_stamped_summary():
    from core.models import SummaryResult

    return SummaryResult(
        chapter_heading="Test Chapter",
        executive_summary="Exec summary (1980).",
        thorough_summary="Thorough summary.",
        bullet_points=[
            "Bullet one (1975).",
            "Bullet two (1983).",
            "Bullet three (1990).",
        ],
        success=True,
        error_msg=None,
        run_id="20260831-120000-deadbeef",
        app_version="18.20.3.10",
        run_started="2026-08-31T12:00:00",
    )


class TestF6StampDiagnostic:
    def test_stamped_chapter_file_is_found(self):
        """The exact failure of the .3.9 rig run: a FRESH chapter file
        (title / blank / stamp on line 3) was false-flagged by the line-2
        peek. The parser-based checker must return INFO with the run id."""
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        text = render_summary_markdown(_mk_stamped_summary())
        # ground truth: stamp sits on line 3 of the rendered chapter file
        lines = text.splitlines()
        assert lines[0].startswith("# Summary:")
        assert lines[1] == ""
        assert lines[2].startswith("<!-- generated-by:")

        level, msg = stamp_diagnostic("ch.md", text)
        assert level == "INFO"
        assert "run_id=20260831-120000-deadbeef" in msg
        assert "18.20.3.10" in msg
        assert "bullets=3" in msg
        assert "NO generated-by stamp" not in msg

    def test_unstamped_legacy_file_warns(self):
        legacy = (
            "# Summary: Old\n\n"
            "## Executive Summary\n\nOld exec.\n\n"
            "<!-- COMPLETE -->\n"
        )
        level, msg = stamp_diagnostic("old.md", legacy)
        assert level == "WARNING"
        assert "NO generated-by stamp" in msg

    def test_sentinel_only_file_is_self_identified(self):
        """A file with only a run-id-stamped sentinel (no comment) still
        self-identifies — INFO, version unknown, run id present."""
        text = "# Summary: X\n\nbody\n<!-- COMPLETE run_id=20260831-130000-cafe1234 -->\n"
        level, msg = stamp_diagnostic("sent.md", text)
        assert level == "INFO"
        assert "run_id=20260831-130000-cafe1234" in msg
        assert "unknown" in msg

    def test_book_file_stamp_on_line_1_is_found(self):
        """Book-level files stamp line 1 — also missed by the old line-2
        peek."""
        text = (
            "<!-- generated-by: Elixir v18.20.3.10"
            " | run_id=20260831-140000-feed0000"
            " | started=2026-08-31T14:00:00"
            " | bullets=41 -->\n\n# Book summary\n\nbody\n"
        )
        level, msg = stamp_diagnostic("book.md", text)
        assert level == "INFO"
        assert "run_id=20260831-140000-feed0000" in msg

    def test_none_and_empty_text_never_raise(self):
        assert stamp_diagnostic("a.md", None)[0] == "WARNING"
        assert stamp_diagnostic("b.md", "")[0] == "WARNING"
        # parser contract: never raises, empty fields on no match
        prov = parse_provenance(None)
        assert prov == {
            "run_id": "", "app_version": "", "started": "", "bullets": "",
        }

    def test_converter_uses_parser_not_line_peek(self):
        """Policy pin: the diagnostic block must delegate to the canonical
        parser — no fixed-line peeking may return."""
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        # V18.20.4.3 (P2 / G-1 + G-2): the scan now passes the file's full
        # path and the running app version (stale-artifact escalation) —
        # still delegating to the canonical parser, never line-peeking.
        assert "stamp_diagnostic(" in src
        assert "current_version=_app_ver" in src
        # the line-2 peek must be gone
        assert "_sl[1]" not in src


# ═════════════════════════════════════════════════════════════════════════════
# 2) W11 — library keypoints count = the deduped count that shipped
# ═════════════════════════════════════════════════════════════════════════════

class TestW11KeypointCount:
    def _build(self, tmp_path, bullets):
        from core.models import SummaryResult
        from core.summarisation import KeypointsBuilder

        logs = []

        def log(msg, level="INFO"):
            logs.append((level, msg))

        summ = SummaryResult(
            chapter_heading="Ch",
            executive_summary="Exec.",
            thorough_summary="Thorough.",
            bullet_points=bullets,
            success=True,
            error_msg=None,
        )
        kp = KeypointsBuilder(log_callback=log)
        md, docx = kp.build([summ], book_title="Book", output_dir=tmp_path)
        return kp, md, docx, logs

    def test_final_count_is_deduped_count(self, tmp_path):
        """41-vs-36 class: exact-duplicate bullets must NOT count toward
        the builder's final keypoint count."""
        bullets = [f"Distinct point {i} (1975)." for i in range(4)]
        bullets.append(bullets[0])  # exact duplicate — must be dropped
        kp, md, docx, logs = self._build(tmp_path, bullets)

        assert kp.final_keypoint_count == 4
        # the shipped file agrees with the reported count
        if md and md.exists():
            shipped = md.read_text(encoding="utf-8")
            assert "**Total keypoints:** 4" in shipped

    def test_converter_library_uses_builder_count(self):
        """Policy pin: the library call must prefer the builder's deduped
        count over the raw bullet sum."""
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        assert "final_keypoint_count" in src
        assert "_kp_final_count" in src

    def test_builder_exposes_count_attribute(self):
        from core.summarisation import KeypointsBuilder

        kp = KeypointsBuilder()
        assert kp.final_keypoint_count is None


# ═════════════════════════════════════════════════════════════════════════════
# 3) F5 — known-cosmetic visibility classes
# ═════════════════════════════════════════════════════════════════════════════

class TestF5Visibility:
    def test_empty_response_retry_is_warning(self):
        """The .3.7 rig's invisible 1.9s empty round-1 response — the
        retry line must be WARNING-level so the anomaly is operator-
        visible."""
        src = (ROOT / "core" / "summarisation" / "summarizer.py").read_text(
            encoding="utf-8"
        )
        assert (
            'self.log("    ⚠️ Empty/short LLM response — retrying with nudge'
            in src
        )
        # must NOT be the old DEBUG form
        assert 'retrying with nudge after 2s delay", "DEBUG")' not in src

    def test_models_at_exit_is_info_not_warning(self):
        """Models resident in the Ollama server at exit are a known
        cosmetic class — a WARNING on every clean run masks nothing and
        makes runs look failed."""
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        assert "Models still in Ollama server memory at exit" in src
        assert "server-managed" in src
        assert "Models still loaded at exit" not in src


# ═════════════════════════════════════════════════════════════════════════════
# 4) O7 — opt-in response cache made visible
# ═════════════════════════════════════════════════════════════════════════════

class TestO7CacheVisibility:
    def test_cache_hit_logs_info(self):
        src = (ROOT / "core" / "summarisation" / "summarizer.py").read_text(
            encoding="utf-8"
        )
        assert "Response cache HIT — LLM call skipped" in src

    def test_diagnostic_reports_run_cache_stats(self):
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        assert "_cache_stats_start" in src
        assert "Response cache:" in src
        assert "opt-in" in src

    def test_response_cache_roundtrip_hermetic(self):
        """Behavioral: the cache the diagnostic reports on — put/get
        round-trip, stats accounting, empty responses not cached (all
        in-memory, no home-dir pollution)."""
        from core.llm.response_cache import ResponseCache

        rc = ResponseCache(max_entries=8, persist_to_disk=False)
        assert rc.get("p", "m", 0.0) is None
        rc.put("p", "m", 0.0, "response text")
        assert rc.get("p", "m", 0.0) == "response text"
        # different key axis → miss
        assert rc.get("p", "other-model", 0.0) is None
        # empty responses never cached
        rc.put("q", "m", 0.0, "")
        assert rc.get("q", "m", 0.0) is None
        st = rc.stats()
        assert st["hits"] == 1
        assert st["size"] == 1

    def test_cache_enabled_is_opt_in_default(self):
        """The visibility layer must not silently change the opt-in
        contract: the request model still defaults to cache OFF."""
        from core.models import ConversionRequest

        field = ConversionRequest.__dataclass_fields__.get(
            "summarisation_cache_enabled"
        )
        assert field is not None
        assert field.default is False
