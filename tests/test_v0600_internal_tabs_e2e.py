"""V0.6.0 (Task 7-b) — the ToolDashboard's three INTERNAL TABS, end-to-end.

Inventory + trace (evidence-first):
- Output Scanner — ``ui_qt/views/output_scanner_view.py`` (constructed at
  ``ui_qt/app.py:343`` ``OutputScannerView(self.controller)``; reached via
  ``convert_view.py:247`` ``_switch_to_tab("output_scanner")``).  Data
  source: ``core/pipeline/output_scanner.py::scan_output_folder`` called
  SYNCHRONOUSLY at ``output_scanner_view.py:179`` (file checks only).
  Primary actions: ``_pick_folder`` :160 (QFileDialog + auto-scan +
  ``output.last_output_dir`` persistence), ``_run_scan`` :173,
  ``_regenerate`` :538 + ``_complete_all_requested`` :367 (both spawn a
  ``SimpleWorker`` via ``_spawn_regen_worker`` :437 →
  ``controller.regenerate_output``; results marshalled back with
  ``QMetaObject.invokeMethod(..., QueuedConnection)``).
- Batch Queue — ``ui_qt/views/queue_view.py`` (constructed at
  ``ui_qt/app.py:330``).  Queue model: the in-memory ``self._queue`` list
  of ``QueueItem`` (:100) — NO disk persistence.  Processing: a plain
  ``threading.Thread`` ``_queue_worker`` (:691) over
  ``_build_request_for_item`` (:965 → ``controller.build_request_from_ui``)
  + ``_run_one_conversion`` (:930 → ``core.pipeline.Converter``); cloud
  providers may take the bounded-parallel path (:763, ``ui_qt/queue_parallel``).
- Hallucination Audit — ``ui_qt/views/service_dialogs/dialogs/
  hallucination_audit_dialog.py`` (routed from ``convert_view.py:201``
  'hallucination_audit' via the base_dialog facade).  Worker
  ``_HallucinationAuditWorker`` (:34, raw QThread) →
  ``core/summarisation/hallucination_detector.py::detect_and_filter``
  (4 local deterministic signals — content-word overlap, semantic
  similarity, number/quote verification, rapidfuzz verbatim grounding;
  NOT LLM-driven → no live_llm leg).  Semantic similarity is faked at the
  traced seam (``core.summarisation.text_preprocessor.semantic_fact_check``,
  imported lazily inside ``detect_and_filter``) so no embed-model network
  call ever happens in these tests.

Layers (house UI-test pattern, cf. test_v0600_tool_cutter_e2e.py):
1. Pure characterization (no Qt): scanner path helpers, queue shapes +
   parallel-resolution semantics, audit verdict logic with injected fakes.
2. Service-level: the scanner against real synthetic run-dir trees; the
   audit worker's core analysis on a synthetic source+bullets pair; the
   queue's in-memory round-trip contract.
3. View-level drives (offscreen QApplication + stub controllers): the
   primary actions of all three tabs with modals stubbed and workers
   joined before test exit (the batch B/C isolation lessons).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Layer 0: availability gates ─────────────────────────────────────────────


def _qt_available() -> bool:
    try:
        os_env = __import__("os")
        os_env.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


# ── Shared synthetic fixtures ───────────────────────────────────────────────

_SOURCE = (
    "The committee reviewed the quarterly pipeline report and approved the "
    "revised budget. Field measurements were collected across seventeen "
    "stations during the observation window. The auditor noted that three "
    "records lacked signatures and requested a follow-up review."
)
_BULLET_VERBATIM = (
    "The committee reviewed the quarterly pipeline report and approved the "
    "revised budget."
)  # 86 chars — also exercises the display-truncation path
_BULLET_FABRICATED = "The wizard summoned 42 dragons to guard the underground vault entrance."
_BULLET_BAD_NUMBER = (
    "The auditor noted that 42 records lacked signatures during the "
    "observation window."
)  # 83 chars, near-copy of source sentence 3 with a fabricated number


def _make_v75_run(
    tmp_path: Path,
    name: str = "runA",
    *,
    packets_folder: bool = False,
    evidence_map: bool = False,
    settings: dict | None = None,
    checkpoint: dict | None = None,
) -> Path:
    """A synthetic V7.5-subfolder book-output dir for the scanner."""
    d = tmp_path / name
    (d / "markdown" / "chapters").mkdir(parents=True)
    (d / "markdown" / f"{name}.md").write_text(f"# {name}\n" + "content " * 60, encoding="utf-8")
    (d / "markdown" / "chapters" / "ch01.md").write_text("chapter one text", encoding="utf-8")
    (d / "summaries").mkdir()
    (d / "summaries" / f"{name}.summary.md").write_text("summary text", encoding="utf-8")
    (d / "keypoints").mkdir()
    (d / "keypoints" / f"{name}.keypoints.md").write_text("- kp one", encoding="utf-8")

    if packets_folder:
        (d / "packets").mkdir()
        (d / "packets" / "p1.md").write_text("packet", encoding="utf-8")
    if evidence_map:
        (d / "evidence").mkdir()
        (d / "evidence" / f"{name}.EvidenceMap.md").write_text("map", encoding="utf-8")

    (d / ".checkpoint.json").write_text(
        json.dumps(
            checkpoint
            if checkpoint is not None
            else {
                "book_name": name,
                "phases": {
                    "pdf_extraction": {"status": "done"},
                    "segmentation": {"status": "done"},
                    "summarization": {"status": "done"},
                    "keypoints": {"status": "done"},
                },
            }
        ),
        encoding="utf-8",
    )
    (d / ".conversion_config.json").write_text(
        json.dumps(
            settings
            if settings is not None
            else {
                "generate_summaries": True,
                "output_packets": True,
                "output_evidence_map": True,
                "output_flashcards": False,
            }
        ),
        encoding="utf-8",
    )
    return d


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1 — pure characterization (no Qt)
# ═══════════════════════════════════════════════════════════════════════════


class TestScannerPureHelpers:
    """core/pipeline/output_scanner.py path helpers — pure file-system logic."""

    def _mod(self):
        from core.pipeline import output_scanner as m

        return m

    def test_detect_layout_v75_via_markdown_dir(self, tmp_path):
        (tmp_path / "markdown").mkdir()
        assert self._mod().detect_layout(tmp_path) == "v7.5_subfolders"

    def test_detect_layout_v75_via_summaries_dir(self, tmp_path):
        (tmp_path / "summaries").mkdir()
        assert self._mod().detect_layout(tmp_path) == "v7.5_subfolders"

    def test_detect_layout_legacy_flat_via_root_md(self, tmp_path):
        (tmp_path / "book.md").write_text("x")
        assert self._mod().detect_layout(tmp_path) == "legacy_flat"

    def test_detect_layout_unknown_when_empty(self, tmp_path):
        (tmp_path / "sub").mkdir()
        assert self._mod().detect_layout(tmp_path) == "unknown"

    def test_detect_stem_from_markdown_dir(self, tmp_path):
        (tmp_path / "markdown").mkdir()
        (tmp_path / "markdown" / "MyBook.md").write_text("x")
        assert self._mod().detect_stem(tmp_path) == "MyBook"

    def test_detect_stem_skips_temp_and_summary_suffixes(self, tmp_path):
        (tmp_path / "markdown").mkdir()
        (tmp_path / "markdown" / "MyBook.temp.md").write_text("x")
        (tmp_path / "markdown" / "Other.summary.md").write_text("x")
        (tmp_path / "markdown" / "Real.md").write_text("x")
        assert self._mod().detect_stem(tmp_path) == "Real"

    def test_detect_stem_legacy_excludes_summary_keypoints(self, tmp_path):
        (tmp_path / "Book.summary.md").write_text("x")
        (tmp_path / "Book.keypoints.md").write_text("x")
        (tmp_path / "Book.md").write_text("x")
        assert self._mod().detect_stem(tmp_path) == "Book"

    def test_detect_stem_falls_back_to_dir_name(self, tmp_path):
        assert self._mod().detect_stem(tmp_path) == tmp_path.name

    def test_check_file_sizes_and_ghosts(self, tmp_path):
        m = self._mod()
        f = tmp_path / "a.md"
        f.write_text("hello")
        assert m._check_file(f) == (True, 5, "5 bytes")
        g = tmp_path / "ghost.md"
        g.write_text("")
        assert m._check_file(g) == (True, 0, "0 bytes (empty/ghost)")
        assert m._check_file(tmp_path / "nope.md") == (False, 0, "not found")

    def test_check_dir_counts_and_empty(self, tmp_path):
        m = self._mod()
        sub = tmp_path / "pk"
        sub.mkdir()
        (sub / "a.md").write_text("x")
        (sub / "nested").mkdir()
        (sub / "nested" / "b.md").write_text("y")
        # glob("**/*") yields a.md, nested/ (a dir), nested/b.md → 2 FILES
        assert m._check_dir(sub) == (True, 2, "2 file(s)")
        empty = tmp_path / "empty"
        empty.mkdir()
        assert m._check_dir(empty) == (True, 0, "empty folder")
        assert m._check_dir(tmp_path / "missing") == (False, 0, "folder not found")

    def test_check_glob_matches_and_misses(self, tmp_path):
        m = self._mod()
        (tmp_path / "Book.English.footnotes.md").write_text("x")
        exists, n, detail = m._check_glob(tmp_path / "Book.*footnotes*.md")
        assert exists and n == 1
        assert not m._check_glob(tmp_path / "Book.*nope*.md")[0]

    def test_load_checkpoint_and_settings_roundtrip(self, tmp_path):
        m = self._mod()
        (tmp_path / ".checkpoint.json").write_text(json.dumps({"book_name": "B", "phases": {}}))
        (tmp_path / ".conversion_config.json").write_text(json.dumps({"output_packets": True}))
        assert m.load_checkpoint(tmp_path) == {"book_name": "B", "phases": {}}
        assert m.load_settings(tmp_path) == {"output_packets": True}
        assert m.load_checkpoint(tmp_path / "sub") is None
        assert m.load_settings(tmp_path / "sub") is None

    def test_output_types_have_unique_keys(self):
        m = self._mod()
        keys = [o.key for o in m.OUTPUT_TYPES]
        assert len(keys) == len(set(keys))
        assert all(
            o.category in {"markdown", "summaries", "outputs", "translation", "logs"}
            for o in m.OUTPUT_TYPES
        )


class TestQueuePureShapes:
    """QueueItem dataclass + the Phase 6.3 parallel-resolution contract."""

    def test_queue_item_defaults(self):
        from ui_qt.views.queue_view import QueueItem

        it = QueueItem(path=Path("/tmp/book.pdf"))
        assert it.status == "pending"
        assert it.progress == 0.0
        assert it.error == ""
        assert it.result is None

    def test_status_constants(self):
        import ui_qt.views.queue_view as qv

        assert {
            qv.STATUS_PENDING,
            qv.STATUS_PROCESSING,
            qv.STATUS_DONE,
            qv.STATUS_FAILED,
            qv.STATUS_CANCELLED,
        } == {
            "pending",
            "processing",
            "done",
            "failed",
            "cancelled",
        }

    def test_local_provider_always_sequential(self):
        from ui_qt.queue_parallel import resolve_parallel_books

        for provider in ("", "ollama", "llamacpp", "typo-provider", "CLAUDE"):
            assert resolve_parallel_books(provider, 4, 5) == 1

    def test_cloud_needs_more_than_one_pending_book(self):
        from ui_qt.queue_parallel import resolve_parallel_books

        assert resolve_parallel_books("openai", 3, 1) == 1
        assert resolve_parallel_books("openai", 3, 3) == 3

    def test_cloud_clamped_to_absolute_max(self):
        from ui_qt.queue_parallel import ABSOLUTE_MAX_PARALLEL_BOOKS, resolve_parallel_books

        assert resolve_parallel_books("openrouter", 99, 4) == ABSOLUTE_MAX_PARALLEL_BOOKS

    def test_cloud_bad_or_small_setting(self):
        from ui_qt.queue_parallel import DEFAULT_MAX_PARALLEL_BOOKS, resolve_parallel_books

        assert resolve_parallel_books("openai", "garbage", 3) == DEFAULT_MAX_PARALLEL_BOOKS
        assert resolve_parallel_books("openai", 1, 3) == 1
        assert resolve_parallel_books("openai", 0, 3) == 1

    def test_run_books_parallel_input_order_and_crash_isolation(self):
        from ui_qt.queue_parallel import BookOutcome, run_books_parallel

        def job_ok(evt: threading.Event):
            evt.wait(0.05)

        def job_crash(evt: threading.Event):
            raise RuntimeError("book exploded")

        outcomes = run_books_parallel(
            [(0, job_ok), (1, job_crash), (2, job_ok)],
            max_workers=3,
        )
        assert [o.idx for o in outcomes] == [0, 1, 2]  # input order preserved
        assert outcomes[0].ok and outcomes[2].ok
        assert isinstance(outcomes[1], BookOutcome) and not outcomes[1].ok
        assert "book exploded" in outcomes[1].error

    def test_run_books_parallel_hands_each_book_a_cancel_event(self):
        from ui_qt.queue_parallel import run_books_parallel

        seen: dict[int, threading.Event] = {}
        started: list[tuple[int, threading.Event]] = []

        def make(i):
            def fn(evt):
                seen[i] = evt
                evt.set()

            return fn

        run_books_parallel(
            [(i, make(i)) for i in range(3)],
            max_workers=3,
            on_started=lambda i, e: started.append((i, e)),
        )
        assert len(seen) == 3
        assert len({id(e) for e in seen.values()}) == 3  # distinct events
        assert all(e.is_set() for _, e in started)

    def test_run_books_parallel_on_finished_sees_outcomes(self):
        from ui_qt.queue_parallel import run_books_parallel

        finished: list[tuple[int, bool]] = []
        out = run_books_parallel(
            [(0, lambda e: None), (1, lambda e: 1 / 0)],
            max_workers=2,
            on_finished=lambda o: finished.append((o.idx, o.ok)),
        )
        assert sorted(finished) == [(0, True), (1, False)]
        assert [o.ok for o in out] == [True, False]


class TestAuditVerdictLogic:
    """HallucinationDetector._check_single_bullet — the verdict ladder with
    injected signal fakes (pure: the four signal callables are parameters)."""

    def _det(self):
        from core.summarisation.hallucination_detector import HallucinationDetector

        return HallucinationDetector()

    @staticmethod
    def _signals(
        *,
        overlap=1.0,
        sem_grounded=True,
        sem_sim=0.93,
        num_ok=True,
        num_reasons=(),
    ):
        def _overlap(b, s):
            return overlap

        def _sem(b, s, threshold=0.5):
            return {"is_grounded": sem_grounded, "best_similarity": sem_sim}

        def _num(b, s):
            return (num_ok, list(num_reasons))

        return _overlap, _sem, _num

    def test_all_signals_pass_is_kept(self):
        ov, sem, num = self._signals()
        r = self._det()._check_single_bullet(_BULLET_VERBATIM, _SOURCE, ov, sem, num, None)
        assert r["action"] == "kept"
        assert r["reason"] == "All 4 signals passed"
        assert r["source_overlap"] == 1.0
        assert r["semantic_similarity"] == 0.93

    def test_one_failure_is_flagged(self):
        ov, sem, num = self._signals(num_ok=False, num_reasons=["number '42' not found in source"])
        r = self._det()._check_single_bullet(_BULLET_BAD_NUMBER, _SOURCE, ov, sem, num, None)
        assert r["action"] == "flagged"
        assert "numbers/quotes" in r["reason"]
        assert "42" in r["reason"]

    def test_two_failures_is_dropped_with_both_reasons(self):
        ov, sem, num = self._signals(overlap=0.1, sem_grounded=False, sem_sim=0.1)
        r = self._det()._check_single_bullet(_BULLET_FABRICATED, _SOURCE, ov, sem, num, None)
        assert r["action"] == "dropped"
        assert "F4 overlap" in r["reason"] and "semantic sim" in r["reason"]

    def test_raising_signals_fail_open(self):
        def boom(*a, **k):
            raise RuntimeError("signal down")

        r = self._det()._check_single_bullet(_BULLET_VERBATIM, _SOURCE, boom, boom, boom, None)
        # overlap/sem/num fail-open; verbatim via rapidfuzz still passes on a
        # near-verbatim bullet → 0 failures → kept.
        assert r["action"] == "kept"
        assert r["source_overlap"] == 1.0

    def test_threshold_constants_pinned(self):
        d = self._det()
        assert d.OVERLAP_THRESHOLD == 0.25
        assert d.SEMANTIC_THRESHOLD == 0.42
        assert d.PARTIAL_RATIO_THRESHOLD == 0.50

    def test_rapidfuzz_verbatim_substring_passes_unrelated_fails(self):
        d = self._det()
        assert d._rapidfuzz_verbatim_check(_BULLET_VERBATIM, _SOURCE) is True
        assert (
            d._rapidfuzz_verbatim_check(
                "An unrelated long bullet about submarines and coffee plantations entirely absent from the text here",
                _SOURCE,
            )
            is False
        )

    def test_claim_extractor_verbatim_span_passes(self):
        class _FakeExtractor:
            def extract(self, bullet, source):
                return [{"char_interval": (0, 10), "text": bullet[:10]}]

        ov, sem, num = self._signals(overlap=0.1, num_ok=False)
        # overlap fails + numbers fail; verbatim passes via the extractor's
        # char_interval → exactly 2 failures → dropped with BOTH reasons, and
        # the verbatim signal is NOT among the failures.
        r = self._det()._check_single_bullet(
            _BULLET_FABRICATED, _SOURCE, ov, sem, num, _FakeExtractor()
        )
        assert r["action"] == "dropped"
        assert "F4 overlap" in r["reason"]
        assert "numbers/quotes" in r["reason"]
        assert "no verbatim grounding" not in r["reason"]

    def test_claim_extractor_no_span_fails_verbatim(self):
        class _NoSpanExtractor:
            def extract(self, bullet, source):
                return [{"char_interval": None, "text": bullet[:10]}]

        ov, sem, num = self._signals()
        r = self._det()._check_single_bullet(
            _BULLET_FABRICATED, _SOURCE, ov, sem, num, _NoSpanExtractor()
        )
        # only the verbatim signal fails → flagged; the reason must match the
        # verdict (V0.6.0: claims-without-a-span used to report "span found"
        # on a FAILED verbatim check).
        assert r["action"] == "flagged"
        assert "no verbatim grounding (no verbatim span)" in r["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2 — service level
# ═══════════════════════════════════════════════════════════════════════════


class TestScannerService:
    """scan_output_folder against real synthetic run-dir trees."""

    def _mod(self):
        from core.pipeline import output_scanner as m

        return m

    def test_v75_full_report_shape(self, tmp_path):
        d = _make_v75_run(tmp_path, packets_folder=True)
        r = self._mod().scan_output_folder(d)
        assert r.layout == "v7.5_subfolders"
        assert r.stem == "runA"
        assert r.book_title == "runA"  # from checkpoint.book_name
        assert r.checkpoint_found and r.settings_found
        by_key = {res.key: res for res in r.results}
        assert by_key["full_markdown"].status == "generated"
        assert by_key["chapters"].status == "generated"
        assert by_key["book_summary"].status == "generated"
        assert by_key["keypoints"].status == "generated"
        assert by_key["packets"].status == "generated"
        assert by_key["flashcards"].status == "not_requested"  # setting off
        # always-on outputs with no file are missing (never not_requested)
        assert by_key["footnotes"].status == "missing"
        assert by_key["docx"].status == "missing"  # generate_docx default-on
        assert r.summary_counts["generated"] == 5
        assert r.summary_counts["not_requested"] == 8
        assert r.summary_counts["missing"] == 8
        assert r.total == len(self._mod().OUTPUT_TYPES)

    def test_requested_but_absent_is_missing(self, tmp_path):
        d = _make_v75_run(tmp_path, packets_folder=False)
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["packets"].status == "missing"
        assert r.missing_count >= 1

    def test_setting_off_is_not_requested(self, tmp_path):
        d = _make_v75_run(tmp_path, settings={"generate_summaries": True, "output_packets": False})
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["packets"].status == "not_requested"
        assert r.summary_counts.get("not_requested", 0) >= 1

    def test_checkpoint_failed_is_failed_with_error(self, tmp_path):
        cp = {
            "book_name": "runA",
            "phases": {
                "pdf_extraction": {"status": "done"},
                "segmentation": {"status": "done"},
                "docx": {"status": "failed", "error": "docx writer crashed"},
            },
        }
        d = _make_v75_run(tmp_path, checkpoint=cp)
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["docx"].status == "failed"
        assert "docx writer crashed" in by_key["docx"].detail
        assert r.failed_count == 1

    def test_checkpoint_skipped_is_skipped(self, tmp_path):
        cp = {
            "phases": {
                "pdf_extraction": {"status": "done"},
                "segmentation": {"status": "done"},
                "summarization": {"status": "skipped"},
            }
        }
        d = _make_v75_run(tmp_path, checkpoint=cp)
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["chapter_summaries"].status == "skipped"

    def test_zero_byte_ghost_file_is_failed(self, tmp_path):
        d = _make_v75_run(tmp_path)
        (d / "summaries" / "runA.summary.md").write_text("")  # ghost
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["book_summary"].status == "failed"
        assert by_key["book_summary"].detail == "empty/ghost file"

    def test_checkpoint_done_but_file_gone_is_missing(self, tmp_path):
        d = _make_v75_run(tmp_path)
        (d / "keypoints" / "runA.keypoints.md").unlink()
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["keypoints"].status == "missing"
        assert "checkpoint says done but file not found" in by_key["keypoints"].detail
        assert by_key["keypoints"].checkpoint_status == "done"

    def test_legacy_flat_layout(self, tmp_path):
        d = tmp_path / "legacy"
        d.mkdir()
        (d / "Old.md").write_text("# old\ncontent")
        (d / "Old.summary.md").write_text("summary")
        r = self._mod().scan_output_folder(d)
        assert r.layout == "legacy_flat"
        assert r.stem == "Old"
        by_key = {res.key: res for res in r.results}
        assert by_key["full_markdown"].status == "generated"
        assert by_key["book_summary"].status == "generated"

    def test_unknown_layout(self, tmp_path):
        d = tmp_path / "nothing"
        d.mkdir()
        (d / "notes.txt").write_text("x")
        r = self._mod().scan_output_folder(d)
        assert r.layout == "unknown"

    def test_missing_dir_short_circuits_to_error(self, tmp_path):
        r = self._mod().scan_output_folder(tmp_path / "nope")
        assert r.results == []
        assert r.summary_counts == {"error": 1}
        assert r.layout == "unknown"

    def test_book_title_from_settings_input_path(self, tmp_path):
        d = _make_v75_run(
            tmp_path, checkpoint={"phases": {}}, settings={"input_path": "/books/some_title.pdf"}
        )
        r = self._mod().scan_output_folder(d)
        assert r.book_title == "Some Title"

    def test_nested_setting_key_flattened_lookup(self, tmp_path):
        # "summarisation.include_book_summary" is read via the flat tail too.
        d = _make_v75_run(tmp_path, settings={"include_book_summary": False})
        r = self._mod().scan_output_folder(d)
        by_key = {res.key: res for res in r.results}
        assert by_key["book_summary"].status == "not_requested"


class TestAuditService:
    """The detector's full 4-signal run on a synthetic pair, with the
    semantic signal faked at the traced seam (no embed-model network)."""

    @pytest.fixture(autouse=True)
    def _patch_semantic(self, monkeypatch):
        import core.summarisation.text_preprocessor as tp

        monkeypatch.setattr(
            tp,
            "semantic_fact_check",
            lambda b, s, threshold=0.5: {
                "is_grounded": True,
                "best_similarity": 0.93,
                "best_source_sentence": "",
            },
        )

    def _det(self):
        from core.summarisation.hallucination_detector import HallucinationDetector

        return HallucinationDetector()

    def test_verbatim_bullet_is_grounded(self):
        filtered, reports = self._det().detect_and_filter([_BULLET_VERBATIM], _SOURCE, "Audit")
        assert reports[0]["action"] == "kept"
        assert reports[0]["source_overlap"] == 1.0
        assert reports[0]["semantic_similarity"] == 0.93
        assert filtered == [_BULLET_VERBATIM]

    def test_fabricated_bullet_is_dropped(self):
        filtered, reports = self._det().detect_and_filter([_BULLET_FABRICATED], _SOURCE, "Audit")
        r = reports[0]
        assert r["action"] == "dropped"
        assert r["source_overlap"] == 0.0
        assert "42" in r["reason"]
        assert _BULLET_FABRICATED not in filtered

    def test_number_only_failure_is_flagged(self):
        filtered, reports = self._det().detect_and_filter([_BULLET_BAD_NUMBER], _SOURCE, "Audit")
        assert reports[0]["action"] == "flagged"
        assert "number '42' not found in source" in reports[0]["reason"]
        assert _BULLET_BAD_NUMBER in filtered  # flagged bullets are NOT filtered out

    def test_filtered_keeps_grounded_and_flagged_only(self):
        bullets = [_BULLET_VERBATIM, _BULLET_FABRICATED, _BULLET_BAD_NUMBER]
        filtered, reports = self._det().detect_and_filter(bullets, _SOURCE, "Audit")
        assert filtered == [_BULLET_VERBATIM, _BULLET_BAD_NUMBER]
        assert [r["action"] for r in reports] == ["kept", "dropped", "flagged"]

    def test_empty_inputs_short_circuit(self):
        assert self._det().detect_and_filter([], _SOURCE) == ([], [])
        assert self._det().detect_and_filter(["b"], "") == (["b"], [])

    def test_worker_run_emits_reports_and_no_error(self):
        from ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog import (
            _HallucinationAuditWorker,
        )

        got: list[tuple[list, str]] = []
        w = _HallucinationAuditWorker(_SOURCE, [_BULLET_VERBATIM, _BULLET_BAD_NUMBER], None)
        w.done_signal.connect(lambda reps, err: got.append((reps, err)))
        w.run()  # synchronous call — no thread started
        ((reports, err),) = got
        assert err == ""
        assert [r["action"] for r in reports] == ["kept", "flagged"]

    def test_worker_run_emits_error_when_detector_raises(self, monkeypatch):
        import core.summarisation.hallucination_detector as hd

        class _Boom:
            def detect_and_filter(self, bullets, source, label="Audit"):
                raise RuntimeError("detector exploded")

        monkeypatch.setattr(hd, "HallucinationDetector", _Boom)

        from ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog import (
            _HallucinationAuditWorker,
        )

        got: list[tuple[list, str]] = []
        w = _HallucinationAuditWorker(_SOURCE, [_BULLET_VERBATIM], None)
        w.done_signal.connect(lambda reps, err: got.append((reps, err)))
        w.run()
        ((reports, err),) = got
        assert reports == []
        assert "RuntimeError" in err and "detector exploded" in err


class TestQueuePersistenceContract:
    """The queue is IN-MEMORY ONLY — pin that contract (no disk persistence
    exists to round-trip; add/remove/clear semantics are pinned in L3)."""

    def test_queue_view_has_no_disk_persistence(self):
        src = Path(_project_root / "ui_qt" / "views" / "queue_view.py").read_text(encoding="utf-8")
        for forbidden in ("json.dump", "json.load", "pickle", ".write_text", ".write_bytes"):
            assert forbidden not in src, forbidden


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3 — view-level drives (offscreen QApplication)
# ═══════════════════════════════════════════════════════════════════════════


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _drain(app, cond, timeout_ms=15000):
    """processEvents until cond() or timeout (queued signals get delivered)."""
    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
        waited += 20
    app.processEvents()
    return cond()


class _RecorderQMB:
    """QMessageBox stand-in — records every call, never blocks."""

    Yes, No = 16384, 65536  # the real QMessageBox button codes

    def __init__(self):
        self.calls: list[str] = []

    def question(self, *a, **k):
        self.calls.append("question")
        return self.Yes

    def information(self, *a, **k):
        self.calls.append("information")
        return None

    def warning(self, *a, **k):
        self.calls.append("warning")
        return None

    def critical(self, *a, **k):
        self.calls.append("critical")
        return None


class _StubController:
    """The scanner view's controller seam: settings + regenerate_output."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}
        self.regen_calls: list[tuple[str, str]] = []
        self.regen_effect: object = None  # None → success default

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def regenerate_output(self, output_dir, output_key, log_callback=None):
        self.regen_calls.append((str(output_dir), output_key))
        if callable(self.regen_effect):
            return self.regen_effect(output_dir, output_key)
        if isinstance(self.regen_effect, Exception):
            raise self.regen_effect
        # default: really create the on-disk artefact the scanner looks for
        # (folder AND filename patterns — e.g. evidence_map lives in
        # evidence/{stem}.EvidenceMap*, like the real generators).
        folder = "evidence" if output_key == "evidence_map" else output_key
        out = Path(output_dir) / folder
        out.mkdir(exist_ok=True)
        if output_key == "evidence_map":
            fname = f"{Path(output_dir).name}.EvidenceMap.md"
        else:
            fname = "out.md"
        (out / fname).write_text("regenerated", encoding="utf-8")
        return (True, f"Regenerated {output_key}")


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestScannerViewDrive:
    def _view(self, controller=None):
        from ui_qt.views.output_scanner_view import OutputScannerView

        return OutputScannerView(controller or _StubController())

    def _scan(self, view, folder):
        view._selected_folder = folder
        view._run_scan()
        return view

    def test_scan_populates_summary_rows_and_reenables(self, tmp_path):
        _app()
        d = _make_v75_run(tmp_path)  # packets + evidence_map requested but absent
        view = self._scan(self._view(), d)
        assert view.summary_lbl.text().startswith("<b>runA</b>")
        assert "layout: v7.5_subfolders" in view.summary_lbl.text()
        assert "❌ 9 missing" in view.summary_lbl.text()
        assert view.scan_btn.isEnabled()
        # results rows were built (category headers + one row per result)
        widgets = [view.results_lay.itemAt(i).widget() for i in range(view.results_lay.count())]
        labels = [w for w in widgets if w is not None]
        assert len(labels) > 10  # ~20 outputs + category headers

    def test_missing_regenerable_shows_complete_all_button(self, tmp_path):
        _app()
        d = _make_v75_run(tmp_path)
        view = self._scan(self._view(), d)
        assert not view.complete_all_btn.isHidden()

    def test_all_generated_hides_complete_all(self, tmp_path):
        _app()
        d = _make_v75_run(
            tmp_path,
            packets_folder=True,
            evidence_map=True,
            settings={
                "generate_summaries": True,
                "output_packets": True,
                "output_evidence_map": True,
            },
        )
        view = self._scan(self._view(), d)
        # nothing regenerable is missing (the 7 missing are non-regenerable)
        assert view.complete_all_btn.isHidden()
        assert "❌ 7 missing" in view.summary_lbl.text()

    def test_unknown_layout_warns(self, tmp_path):
        _app()
        d = tmp_path / "strange"
        d.mkdir()
        view = self._scan(self._view(), d)
        assert "doesn't look like a Elixir output directory" in view.summary_lbl.text()

    def test_pick_folder_persists_last_dir_and_autoscans(self, tmp_path, monkeypatch):
        _app()
        import ui_qt.views.output_scanner_view as scanner_mod

        d = _make_v75_run(tmp_path)
        ctrl = _StubController()
        view = self._view(ctrl)
        monkeypatch.setattr(
            scanner_mod.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(d))
        )
        view._pick_folder()
        assert ctrl.get_setting("output.last_output_dir") == str(d)
        assert view.folder_lbl.text() == str(d)
        assert view.scan_btn.isEnabled()
        assert view.summary_lbl.text().startswith("<b>runA</b>")

    def test_regenerate_flow_rescans_with_new_output(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        _app()
        d = _make_v75_run(
            tmp_path,
            settings={
                "generate_summaries": True,
                "output_packets": True,
                "output_evidence_map": False,
            },
        )
        ctrl = _StubController()
        view = self._scan(self._view(ctrl), d)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
        view._regenerate("packets")

        app = _app()
        ok = _drain(
            app,
            lambda: (
                ctrl.regen_calls
                and view.scan_btn.isEnabled()
                and view._report is not None
                and {r.key: r for r in view._report.results}["packets"].status == "generated"
            ),
        )
        assert ok, view.summary_lbl.text()
        assert ctrl.regen_calls == [(str(d), "packets")]
        assert (d / "packets" / "out.md").exists()
        # nothing regenerable is missing anymore → the button hides again
        assert view.complete_all_btn.isHidden()
        # the worker is joined before the test ends (GC-hazard lesson)
        w = view._regen_worker
        if w is not None:
            try:
                w.wait(2000)
            except RuntimeError:
                pass  # already deleteLater'd itself

    def test_regenerate_worker_failure_reenables_and_shows_error(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        _app()
        d = _make_v75_run(
            tmp_path,
            settings={
                "generate_summaries": True,
                "output_packets": True,
                "output_evidence_map": False,
            },
        )
        ctrl = _StubController()
        ctrl.regen_effect = RuntimeError("generator exploded")
        view = self._scan(self._view(ctrl), d)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
        view._regenerate("packets")

        app = _app()
        ok = _drain(
            app,
            lambda: view.summary_lbl.text().startswith("❌") and view.scan_btn.isEnabled(),
        )
        assert ok, view.summary_lbl.text()
        assert "generator exploded" in view.summary_lbl.text()
        assert view.complete_all_btn.isEnabled()
        w = view._regen_worker
        if w is not None:
            try:
                w.wait(2000)
            except RuntimeError:
                pass

    def test_complete_all_batch_processes_every_missing_regenerable(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        _app()
        d = _make_v75_run(tmp_path)  # packets + evidence_map missing, both requested
        ctrl = _StubController()
        view = self._scan(self._view(ctrl), d)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
        view._complete_all_requested()

        app = _app()
        ok = _drain(
            app,
            lambda: (
                len(ctrl.regen_calls) == 2
                and view.scan_btn.isEnabled()
                and view.summary_lbl.text().startswith("<b>runA</b>")
            ),
        )
        assert ok, view.summary_lbl.text()
        assert [k for _, k in ctrl.regen_calls] == ["packets", "evidence_map"]
        assert view.complete_all_btn.isEnabled()
        assert view.complete_all_btn.text() == "  ✅ Complete All Requested"
        # both regenerated on disk → the re-scan sees them as generated
        assert (d / "packets" / "out.md").exists()
        assert (d / "evidence" / "runA.EvidenceMap.md").exists()
        res = {r.key: r for r in view._report.results}
        assert res["packets"].status == "generated"
        assert res["evidence_map"].status == "generated"
        assert "❌ 7 missing" in view.summary_lbl.text()
        w = view._regen_worker
        if w is not None:
            try:
                w.wait(2000)
            except RuntimeError:
                pass

    def test_row_regen_button_present_for_every_missing_regenerable(self, tmp_path):
        """Pins the unified regenerable-key set: a missing evidence_map row
        (a controller-regenerable output) must offer the 🔄 button too —
        the three hard-coded sets had drifted apart."""
        from PySide6.QtWidgets import QPushButton

        _app()
        d = _make_v75_run(tmp_path)  # packets + evidence_map missing
        view = self._scan(self._view(), d)
        rows = [view.results_lay.itemAt(i).widget() for i in range(view.results_lay.count())]
        named: dict[str, object] = {}
        label_cls = type(view.folder_lbl)
        for r in rows:
            if r is None:
                continue
            for lbl in r.findChildren(label_cls):
                if lbl.text() in ("Packets of Knowledge", "Scientific Evidence Map"):
                    named[lbl.text()] = r
        for display_name in ("Packets of Knowledge", "Scientific Evidence Map"):
            row = named.get(display_name)
            assert row is not None, display_name
            assert row.findChildren(QPushButton), f"no 🔄 button on {display_name}"


class _QueueStubController:
    """Everything QueueView touches on the controller."""

    def __init__(self) -> None:
        self._settings = {"ui.playSuccess_sound": False}
        self.on_progress = lambda v: None
        self.on_status = lambda m: None
        self.on_log = lambda m, l="INFO": None
        self.on_complete = lambda r: None
        self.callback_owner = "convert_view"
        self.owners: list[str | None] = []
        self.current_conversion_thread = None
        self.cancel_event = threading.Event()
        self.converter = None
        self.converting = False
        self.cancel_calls = 0
        self.saved_settings: list[tuple[str, object]] = []
        self.built_requests: list[dict] = []

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def is_converting(self):
        return self.converting

    def cancel_conversion(self):
        self.cancel_calls += 1
        return True

    def set_callbacks(
        self, on_progress=None, on_status=None, on_log=None, on_complete=None, owner=None
    ):
        if on_progress:
            self.on_progress = on_progress
        if on_status:
            self.on_status = on_status
        if on_log:
            self.on_log = on_log
        if on_complete:
            self.on_complete = on_complete
        self.callback_owner = owner
        self.owners.append(owner)

    def _safe_progress(self, v):
        self.on_progress(v)

    def _safe_status(self, m):
        self.on_status(m)

    def _safe_log(self, m, level="INFO"):
        self.on_log(m, level)

    def _safe_complete(self, r):
        self.on_complete(r)

    def build_request_from_ui(self, ui_data):
        self.built_requests.append(dict(ui_data))
        return ("request-marker", ui_data["input_path"])

    def save_book_settings(self, output_dir, request):
        self.saved_settings.append((str(output_dir), request))


class _FakeConverter:
    """Stands in for core.pipeline.Converter (monkeypatched at that seam)."""

    result_factory = None
    progress_at = 0.5
    on_convert = None

    def __init__(
        self,
        request=None,
        progress_callback=None,
        status_callback=None,
        log_callback=None,
        cancel_event=None,
    ):
        self.request = request
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.cancel_event = cancel_event

    def convert(self):
        if self.progress_callback:
            self.progress_callback(_FakeConverter.progress_at)
        if _FakeConverter.on_convert:
            _FakeConverter.on_convert(self)
        return _FakeConverter.result_factory(self.request)


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestQueueViewDrive:
    def _view(self, controller=None):
        from ui_qt.views.queue_view import QueueView

        return QueueView(controller or _QueueStubController())

    def _pdfs(self, tmp_path, n=2):
        ps = []
        for i in range(n):
            p = tmp_path / f"book{i}.pdf"
            p.write_bytes(b"%PDF-1.4 fake")
            ps.append(p)
        return ps

    def test_add_books_dedupes_and_updates_count(self, tmp_path):
        _app()
        pdfs = self._pdfs(tmp_path, 2)
        view = self._view()
        view._add_books(pdfs)
        view._add_books(pdfs)  # duplicates skipped
        assert len(view._queue) == 2
        assert view.count_lbl.text() == "2 books in queue"
        assert len(view._rows) == 2
        assert view.empty_lbl.isHidden()

    def test_handle_dropped_files_accepts_only_pdfs(self, tmp_path):
        _app()
        pdfs = self._pdfs(tmp_path, 1)
        txt = tmp_path / "notes.txt"
        txt.write_text("x")
        view = self._view()
        assert view.handle_dropped_files([*pdfs, txt]) is True
        assert [it.path for it in view._queue] == pdfs
        assert view.handle_dropped_files([txt]) is False

    def test_remove_book_updates_rows(self, tmp_path):
        _app()
        pdfs = self._pdfs(tmp_path, 2)
        view = self._view()
        view._add_books(pdfs)
        view._remove_book(0)
        assert [it.path for it in view._queue] == [pdfs[1]]
        assert len(view._rows) == 1
        assert view._rows[0]._index == 0

    def test_clear_all_with_confirmation(self, tmp_path, monkeypatch):
        _app()
        import ui_qt.views.queue_view as qv_mod

        pdfs = self._pdfs(tmp_path, 2)
        view = self._view()
        view._add_books(pdfs)
        rec = _RecorderQMB()
        monkeypatch.setattr(qv_mod, "QMessageBox", rec)
        view._on_clear_all()
        assert view._queue == []
        assert view.count_lbl.text() == "0 books in queue"
        assert not view.empty_lbl.isHidden()

    def test_start_refused_on_empty_queue(self, tmp_path, monkeypatch):
        _app()
        import ui_qt.views.queue_view as qv_mod

        view = self._view()
        rec = _RecorderQMB()
        monkeypatch.setattr(qv_mod, "QMessageBox", rec)
        view._on_start()
        assert rec.calls == ["information"]
        assert view._worker_thread is None
        assert view.is_running() is False

    def test_start_refused_when_controller_converting(self, tmp_path, monkeypatch):
        _app()
        import ui_qt.views.queue_view as qv_mod

        pdfs = self._pdfs(tmp_path, 1)
        ctrl = _QueueStubController()
        ctrl.converting = True
        view = self._view(ctrl)
        view._add_books(pdfs)
        rec = _RecorderQMB()
        monkeypatch.setattr(qv_mod, "QMessageBox", rec)
        view._on_start()
        assert rec.calls == ["warning"]
        assert view._worker_thread is None

    def test_start_refused_when_nothing_pending(self, tmp_path, monkeypatch):
        _app()
        import ui_qt.views.queue_view as qv_mod

        pdfs = self._pdfs(tmp_path, 1)
        view = self._view()
        view._add_books(pdfs)
        view._queue[0].status = "done"
        rec = _RecorderQMB()
        monkeypatch.setattr(qv_mod, "QMessageBox", rec)
        view._on_start()
        assert rec.calls == ["information"]
        assert view._worker_thread is None

    def test_full_sequential_run_two_books(self, tmp_path, monkeypatch):
        _app()
        from core.models import ConversionResult

        pdfs = self._pdfs(tmp_path, 2)
        out_md = tmp_path / "out.md"
        _FakeConverter.result_factory = lambda req: ConversionResult(
            success=True, full_markdown_path=out_md
        )
        monkeypatch.setattr("core.pipeline.Converter", _FakeConverter)

        ctrl = _QueueStubController()
        view = self._view(ctrl)
        view._add_books(pdfs)
        view._on_start()
        assert view.is_running()

        app = _app()
        ok = _drain(app, lambda: view.status_lbl.text().startswith("Finished"))
        view._worker_thread.join(5000)
        assert ok, view.status_lbl.text()
        assert view.status_lbl.text() == "Finished — 2 of 2 books done"
        assert not view.is_running()
        assert view.start_btn.isEnabled() and not view.stop_btn.isEnabled()
        assert [it.status for it in view._queue] == ["done", "done"]
        assert [row.status_label.text() for row in view._rows] == ["done", "done"]
        assert all(row.progress.value() == 100 for row in view._rows)
        assert view.overall_progress_bar.value() == 100
        assert all(it.progress == 1.0 for it in view._queue)
        assert ctrl.current_conversion_thread is None
        # requests built from the item paths + the item's parent folder
        assert [r["input_path"] for r in ctrl.built_requests] == [str(p) for p in pdfs]
        assert all(r["output_dir"] == str(tmp_path) for r in ctrl.built_requests)
        # book settings saved once per successful book
        assert len(ctrl.saved_settings) == 2
        # callbacks: installed with owner "queue", restored with "convert_view"
        assert ctrl.owners == ["queue", "convert_view"]
        assert ctrl.callback_owner == "convert_view"
        assert "Queue finished: 2 of 2 books done." in view.log_viewer.toPlainText()
        assert not view.has_pending()

    def test_failed_book_marks_row_and_logs_error(self, tmp_path, monkeypatch):
        _app()
        from core.models import ConversionResult

        pdfs = self._pdfs(tmp_path, 1)
        _FakeConverter.result_factory = staticmethod(
            lambda req: ConversionResult(success=False, error_msg="extraction failed")
        )
        monkeypatch.setattr("core.pipeline.Converter", _FakeConverter)

        view = self._view()
        view._add_books(pdfs)
        view._on_start()
        app = _app()
        ok = _drain(app, lambda: view.status_lbl.text().startswith("Finished"))
        view._worker_thread.join(5000)
        assert ok, view.status_lbl.text()
        assert view.status_lbl.text() == "Finished — 0 done, 1 failed, 0 cancelled of 1"
        assert view._queue[0].status == "failed"
        assert "extraction failed" in view._queue[0].error
        assert "✗ Failed: book0.pdf — extraction failed" in view.log_viewer.toPlainText()

    def test_stop_mid_conversion_cancels_all_books(self, tmp_path, monkeypatch):
        _app()
        from core.models import ConversionResult

        pdfs = self._pdfs(tmp_path, 2)
        _FakeConverter.result_factory = lambda req: ConversionResult(success=True)

        holder = {}

        def _on_convert(conv):
            holder["view"]._cancel.set()  # the user pressed Stop mid-conversion

        _FakeConverter.on_convert = _on_convert
        monkeypatch.setattr("core.pipeline.Converter", _FakeConverter)

        view = self._view()
        holder["view"] = view
        view._add_books(pdfs)
        view._on_start()
        app = _app()
        ok = _drain(app, lambda: view.status_lbl.text().startswith("Finished"))
        view._worker_thread.join(5000)
        assert ok, view.status_lbl.text()
        assert view.status_lbl.text() == "Finished — 0 done, 0 failed, 2 cancelled of 2"
        assert [it.status for it in view._queue] == ["cancelled", "cancelled"]
        assert "⊘ Cancelled: book0.pdf" in view.log_viewer.toPlainText()

    def teardown_method(self):
        _FakeConverter.result_factory = None
        _FakeConverter.on_convert = None


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestAuditDialogDrive:
    @pytest.fixture(autouse=True)
    def _patch_semantic(self, monkeypatch):
        import core.summarisation.text_preprocessor as tp

        monkeypatch.setattr(
            tp,
            "semantic_fact_check",
            lambda b, s, threshold=0.5: {
                "is_grounded": True,
                "best_similarity": 0.93,
                "best_source_sentence": "",
            },
        )

    def _dlg(self):
        from ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog import (
            HallucinationAuditDialog,
        )

        return HallucinationAuditDialog(_StubController())

    def _audit(self, dlg, source=_SOURCE, bullets=None):
        dlg.source_input.setPlainText(source)
        dlg.bullets_input.setPlainText(
            bullets
            if bullets is not None
            else "\n".join(
                [
                    f"- {_BULLET_VERBATIM}",
                    f"* {_BULLET_FABRICATED}",
                    f"• {_BULLET_BAD_NUMBER}",
                ]
            )
        )
        dlg._on_audit()

    def test_full_audit_flow_populates_table_and_status(self):
        _app()
        dlg = self._dlg()
        self._audit(dlg)
        app = _app()
        ok = _drain(app, lambda: dlg.status_label.text().startswith(("✅ Audit complete", "❌")))
        assert ok, dlg.status_label.text()
        if dlg._worker is not None:
            dlg._worker.wait(5000)
        assert dlg.status_label.text() == (
            "✅ Audit complete: 1 grounded, 1 flagged, 1 dropped (of 3 total)"
        )
        assert dlg.results_table.rowCount() == 3
        assert dlg.audit_btn.isEnabled()
        assert dlg.audit_btn.text() == "🛡️ Audit Bullets"
        verdicts = [dlg.results_table.item(i, 1).text() for i in range(3)]
        assert verdicts == ["✅ Grounded", "🗑️ Dropped", "⚠️ Flagged"]
        reasons = [dlg.results_table.item(i, 2).text() for i in range(3)]
        assert reasons[0] == "All 4 signals passed"
        assert "number '42' not found in source" in reasons[2]
        # the long bullet is display-truncated with an ellipsis
        assert dlg.results_table.item(0, 0).text().endswith("...")
        assert len(dlg.results_table.item(0, 0).text()) <= 84

    def test_bullet_parsing_accepts_all_prefixes_and_skips_short_lines(self):
        _app()
        dlg = self._dlg()
        text = f"- {_BULLET_VERBATIM}\n* {_BULLET_FABRICATED}\n• {_BULLET_BAD_NUMBER}\nshort\n"
        dlg.source_input.setPlainText(_SOURCE)
        dlg.bullets_input.setPlainText(text)
        # parse happens inside _on_audit; drive it and count rows
        self._audit(dlg, bullets=text)
        app = _app()
        ok = _drain(app, lambda: dlg.status_label.text().startswith(("✅ Audit complete", "❌")))
        assert ok, dlg.status_label.text()
        if dlg._worker is not None:
            dlg._worker.wait(5000)
        assert dlg.results_table.rowCount() == 3  # the short line was skipped

    def test_missing_input_warns_without_spawning_worker(self, monkeypatch):
        _app()
        import ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog as ha_mod

        rec = _RecorderQMB()
        monkeypatch.setattr(ha_mod, "QMessageBox", rec)
        dlg = self._dlg()
        dlg._on_audit()  # both inputs empty
        assert rec.calls == ["warning"]
        assert dlg._worker is None

    def test_no_bullets_warns_without_spawning_worker(self, monkeypatch):
        _app()
        import ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog as ha_mod

        rec = _RecorderQMB()
        monkeypatch.setattr(ha_mod, "QMessageBox", rec)
        dlg = self._dlg()
        dlg.source_input.setPlainText(_SOURCE)
        dlg.bullets_input.setPlainText("ab")  # < 10 chars, no prefix
        dlg._on_audit()
        assert rec.calls == ["warning"]
        assert dlg._worker is None

    def test_worker_exception_lands_error_status_and_critical(self, monkeypatch):
        _app()
        import core.summarisation.hallucination_detector as hd
        import ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog as ha_mod

        class _Boom:
            def detect_and_filter(self, bullets, source, label="Audit"):
                raise RuntimeError("detector exploded")

        monkeypatch.setattr(hd, "HallucinationDetector", _Boom)
        rec = _RecorderQMB()
        monkeypatch.setattr(ha_mod, "QMessageBox", rec)

        dlg = self._dlg()
        self._audit(dlg)
        app = _app()
        ok = _drain(app, lambda: dlg.status_label.text().startswith("❌"))
        assert ok, dlg.status_label.text()
        if dlg._worker is not None:
            dlg._worker.wait(5000)
        assert "detector exploded" in dlg.status_label.text()
        assert rec.calls == ["critical"]
        assert dlg.audit_btn.isEnabled()

    def test_copy_filtered_puts_full_bullets_on_clipboard(self):
        """The copy button must copy the FULL grounded bullet text — the
        table cell shows a truncated version (80 chars + '...'), and
        copying the display text corrupts the paste."""
        from PySide6.QtWidgets import QApplication

        app = _app()
        dlg = self._dlg()
        self._audit(dlg)
        ok = _drain(app, lambda: dlg.status_label.text().startswith("✅ Audit complete"))
        assert ok, dlg.status_label.text()
        if dlg._worker is not None:
            dlg._worker.wait(5000)
        dlg._copy_filtered()
        clipboard = QApplication.clipboard().text()
        assert clipboard == f"- {_BULLET_VERBATIM}"
        assert "..." not in clipboard
        assert dlg.status_label.text().startswith("📋 Copied 1 grounded")

    def test_copy_filtered_with_nothing_grounded(self):
        _app()
        dlg = self._dlg()
        dlg._copy_filtered()
        assert dlg.status_label.text() == "No grounded bullets to copy."
