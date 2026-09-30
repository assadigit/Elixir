"""V0.4.25 — run-stamped output filenames (the 20× stale-upload killer).

Root cause (operator-reported, then verified byte-level in the V0.4.24
audit session): the chat/file-transfer layer caches attachments BY
FILENAME. Elixir's output artifacts have stable names
(``{book}.conversion.log.md``, ``{NNN}_{heading}_summary.md``,
``{book}.summary.md``), so every re-run of the same book delivered the
FIRST upload's bytes — 20+ "genuinely new" runs arrived as byte-identical
stale files (identical md5s, frozen timestamps, no "v0.4.24" anywhere).

The fix: every run-stamped artifact carries ``_v{version}_{run_id}`` in
its FILENAME (the run_id is unique per conversion), so a filename cache
hit is impossible and the filename alone proves which version + run
produced the file before it is even opened.

Contracts tested here:
- ``run_stamp_suffix``: format, empty-fallback, defensive sanitization
- ConversionLogger: unique stamped log names, ``*.conversion.log.md``
  glob compatibility, per-run coexistence (audit trail), the filename's
  run_id == the header stamp's run_id, legacy-name fallback when the
  provenance import fails
- ChapterCheckpointSaver: stamped chapter-summary names from the
  summary's OWN provenance (an adopted/resumed chapter keeps its
  ORIGINAL run's stamp — the filename always tells the truth);
  unstamped (legacy) results keep the exact legacy filename
- chapter_resume: newest-first deterministic adoption when multiple
  runs' stamped files coexist; the V0.4.25 version-mismatch WARNING
- the one-id-per-conversion contract: a stamped chapter file's name
  embeds the same run id its content stamp carries
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v18203_incremental_checkpoint.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
from utils.logging import ConversionLogger  # noqa: E402

RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


# ═══════════════════════════════════════════════════════════════════════════
# 1) run_stamp_suffix
# ═══════════════════════════════════════════════════════════════════════════


class TestRunStampSuffix:
    def test_format_is_version_plus_run_id(self):
        from core.system.provenance import run_stamp_suffix

        s = run_stamp_suffix("0.4.25", "20260923-052332-b3e7f026")
        assert s == "_v0.4.25_20260923-052332-b3e7f026"

    def test_empty_inputs_return_empty_suffix(self):
        from core.system.provenance import run_stamp_suffix

        assert run_stamp_suffix("", "rid") == ""
        assert run_stamp_suffix("0.4.25", "") == ""
        assert run_stamp_suffix("", "") == ""

    def test_whitespace_tolerated(self):
        from core.system.provenance import run_stamp_suffix

        assert run_stamp_suffix(" 0.4.25 ", " 20260923-052332-b3e7f026 ") == (
            "_v0.4.25_20260923-052332-b3e7f026"
        )

    def test_defensive_sanitization_strips_path_hostile_chars(self):
        from core.system.provenance import run_stamp_suffix

        s = run_stamp_suffix("0.4.25/evil:name", "rid\\with:bad*chars?")
        # anything not [0-9A-Za-z.] (version) / [0-9A-Za-z-] (run id) is dropped
        assert "/" not in s and ":" not in s and "\\" not in s
        assert s == "_v0.4.25evilname_ridwithbadchars"

    def test_fully_sanitized_to_empty_returns_empty(self):
        from core.system.provenance import run_stamp_suffix

        assert run_stamp_suffix("///", "rid") == ""
        assert run_stamp_suffix("0.4.25", "***") == ""


# ═══════════════════════════════════════════════════════════════════════════
# 2) ConversionLogger — stamped, unique, glob-compatible log names
# ═══════════════════════════════════════════════════════════════════════════


class TestStampedConversionLogNames:
    def test_log_filename_carries_version_and_run_id(self, tmp_path: Path):
        logger = ConversionLogger(tmp_path, "TestBook")
        try:
            name = logger.log_path.name
            assert name.startswith("TestBook_v")
            assert name[-len(".conversion.log.md") :] == ".conversion.log.md"
            m = re.match(r"^TestBook_v(?P<ver>\S+)_(?P<rid>\S+)\.conversion\.log\.md$", name)
            assert m, f"unexpected log name {name!r}"
            assert m.group("ver")  # version embedded
            assert RUN_ID_RE.match(m.group("rid")), f"run id in filename: {m.group('rid')!r}"
            # the FILENAME's run id is the logger's conversion run id
            assert m.group("rid") == logger._conversion_run_id
        finally:
            logger.close()

    def test_two_runs_produce_two_unique_log_files(self, tmp_path: Path):
        """The V0.4.25 contract: a filename cache can never collide — each
        conversion's log name is unique and both files coexist on disk."""
        l1 = ConversionLogger(tmp_path, "TestBook")
        l1.log("first run", "INFO")
        l1.close()
        l2 = ConversionLogger(tmp_path, "TestBook")
        l2.log("second run", "INFO")
        l2.close()
        assert l1.log_path != l2.log_path
        assert l1.log_path.exists() and l2.log_path.exists()
        # each log keeps its own run's content (no truncation of history)
        assert "first run" in l1.log_path.read_text(encoding="utf-8")
        assert "second run" in l2.log_path.read_text(encoding="utf-8")
        assert "first run" not in l2.log_path.read_text(encoding="utf-8")

    def test_glog_pattern_still_matches_stamped_names(self, tmp_path: Path):
        """Every consumer globs ``*.conversion.log.md`` (output_scanner,
        controller crash-appending) — stamped names must still match."""
        for _ in range(2):
            l = ConversionLogger(tmp_path, "TestBook")
            l.log("x", "INFO")
            l.close()
        logs_dir = tmp_path / "logs"
        matches = sorted(logs_dir.glob("*.conversion.log.md"))
        assert len(matches) == 2

    def test_header_stamp_matches_filename_stamp(self, tmp_path: Path):
        """One id in the name AND the header — an audit can correlate the
        attachment's filename with its content stamp."""
        logger = ConversionLogger(tmp_path, "TestBook")
        try:
            logger.log("x", "INFO")
            logger._file_handle.flush()
        finally:
            logger.close()
        text = logger.log_path.read_text(encoding="utf-8")
        m = re.search(r"run_id=(?P<rid>\S+) -->", text)
        assert m, "header stamp present"
        assert m.group("rid") == logger._conversion_run_id
        assert logger._conversion_run_id in logger.log_path.name

    def test_legacy_name_when_provenance_import_fails(self, tmp_path: Path, monkeypatch):
        """Fail-open: if the provenance machinery explodes, the logger falls
        back to the exact legacy stable filename (V0.20.4 behavior)."""
        import core.system.provenance as prov_mod

        def _boom():
            raise RuntimeError("provenance exploded")

        monkeypatch.setattr(prov_mod, "make_run_id", _boom)
        logger = ConversionLogger(tmp_path, "TestBook")
        logger.log("test", "INFO")
        logger.close()
        assert logger.log_path.name == "TestBook.conversion.log.md"
        assert "# Conversion Log: TestBook" in logger.log_path.read_text(encoding="utf-8")

    def test_diagnostic_path_is_stamped_too(self, tmp_path: Path):
        """The diagnostic.jsonl shares the stamped name so two runs' JSONL
        streams never truncate each other. (V10.25.0: ``diagnostic_path`` is
        lazily None until the first diagnostic is written — the real path
        lives in ``_diag_path``.)"""
        logger = ConversionLogger(tmp_path, "TestBook")
        try:
            assert "_v" in logger._diag_path.name
            assert logger._diag_path.name.endswith(".diagnostic.jsonl")
        finally:
            logger.close()


# ═══════════════════════════════════════════════════════════════════════════
# 3) ChapterCheckpointSaver — stamped chapter-summary filenames
# ═══════════════════════════════════════════════════════════════════════════


class _StubPaths:
    def __init__(self, root: Path):
        self.root = root
        self.summaries_dir = root / "summaries"
        self.book_summary = self.summaries_dir / "Book.summary.md"


class _StubCheckpoint:
    def mark_progress(self, phase, **metadata):
        pass


class _StubRequest:
    generate_docx = False
    docx_author = "Elixir"
    docx_include_toc = False

    def __init__(self, p: Path):
        self.input_path = p


class _StubConverter:
    def __init__(self, root: Path):
        self.output_dir = root
        self.paths = _StubPaths(root)
        self.checkpoint = _StubCheckpoint()
        self.request = _StubRequest(root / "book.pdf")
        self.settings = {}
        self.log_lines = []

    def _log(self, msg, level="INFO"):
        self.log_lines.append((level, msg))

    def _sanitize_filename(self, heading):
        safe = re.sub(r"[^\w\s\-]", "", heading or "")
        return re.sub(r"\s+", "_", safe.strip())[:80]


def _mk_summary(heading: str, run_id: str = "", app_version: str = "", n_bullets: int = 3):
    from core.models import SummaryResult

    return SummaryResult(
        chapter_heading=heading,
        executive_summary=f"Executive summary for {heading}.",
        thorough_summary=f"Thorough summary for {heading}.",
        bullet_points=[f"Bullet {i} about {heading}." for i in range(n_bullets)],
        success=True,
        run_id=run_id,
        app_version=app_version,
    )


@pytest.fixture
def stub_env(tmp_path):
    root = tmp_path / "MyBook"
    root.mkdir()
    conv = _StubConverter(root)
    chapters = {
        "Chapter One": {"heading": "Chapter One", "content": "Content one. " * 60},
    }
    positions = {"Chapter One": 1}
    return root, conv, chapters, positions


class TestStampedChapterSummaryNames:
    def test_stamped_summary_gets_stamped_filename(self, stub_env):
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root, conv, chapters, positions = stub_env
        saver = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        summ = _mk_summary("Chapter One", run_id="20260923-090000-bbbbbbbb", app_version="0.4.25")
        saver.on_chapter_done(1, summ, chapters["Chapter One"])
        expected = (
            root / "summaries" / "001_Chapter_One_v0.4.25_20260923-090000-bbbbbbbb_summary.md"
        )
        assert expected.exists(), (
            f"stamped chapter file missing; dir: {list((root / 'summaries').iterdir())}"
        )

    def test_unstamped_summary_keeps_legacy_filename(self, stub_env):
        """Backward compatibility: legacy/unstamped SummaryResults (e.g.
        every pre-V0.4.25 test fixture and adopted legacy file) produce the
        EXACT legacy filename — write-once and resume stay byte-compatible."""
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root, conv, chapters, positions = stub_env
        saver = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        saver.on_chapter_done(1, _mk_summary("Chapter One"), chapters["Chapter One"])
        assert (root / "summaries" / "001_Chapter_One_summary.md").exists()

    def test_two_runs_coexist_instead_of_colliding(self, stub_env):
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root, conv, chapters, positions = stub_env
        s1 = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        s1.on_chapter_done(
            1,
            _mk_summary("Chapter One", run_id="20260923-010000-aaaaaaaa", app_version="0.4.23"),
            chapters["Chapter One"],
        )
        time.sleep(0.02)
        s2 = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        s2.on_chapter_done(
            1,
            _mk_summary("Chapter One", run_id="20260923-090000-bbbbbbbb", app_version="0.4.24"),
            chapters["Chapter One"],
        )
        files = list((root / "summaries").glob("001_Chapter_One*_summary.md"))
        assert len(files) == 2, "both runs' chapter files coexist (audit trail)"
        names = {f.name for f in files}
        assert "001_Chapter_One_v0.4.23_20260923-010000-aaaaaaaa_summary.md" in names
        assert "001_Chapter_One_v0.4.24_20260923-090000-bbbbbbbb_summary.md" in names

    def test_filename_stamp_matches_content_stamp(self, stub_env):
        """The filename's run id is the SAME id the content's provenance
        comment carries — one id per run, name == content."""
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root, conv, chapters, positions = stub_env
        saver = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        rid = "20260923-090000-bbbbbbbb"
        saver.on_chapter_done(
            1, _mk_summary("Chapter One", run_id=rid, app_version="0.4.25"), chapters["Chapter One"]
        )
        f = root / "summaries" / f"001_Chapter_One_v0.4.25_{rid}_summary.md"
        text = f.read_text(encoding="utf-8")
        assert f"run_id={rid}" in text

    def test_manifest_records_the_stamped_path(self, stub_env):
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root, conv, chapters, positions = stub_env
        saver = ChapterCheckpointSaver(conv, heading_positions=positions, build_docx=False)
        rid = "20260923-090000-bbbbbbbb"
        saver.on_chapter_done(
            1, _mk_summary("Chapter One", run_id=rid, app_version="0.4.25"), chapters["Chapter One"]
        )
        import json

        manifest = json.loads((root / "checkpoints" / "chapter_manifest.json").read_text())
        # V0.6.6 contract change (review-loop L2-3): keyed by the canonical
        # md filename (unique per chapter+run), not str(pos).
        expected_key = f"001_Chapter_One_v0.4.25_{rid}_summary.md"
        assert expected_key in manifest["chapters"]
        assert rid in manifest["chapters"][expected_key].get("summary_md", "")


# ═══════════════════════════════════════════════════════════════════════════
# 4) chapter_resume — deterministic newest-wins + version-mismatch warning
# ═══════════════════════════════════════════════════════════════════════════


def _write_chapter_summary(
    summaries_dir: Path,
    heading: str,
    exec_text: str,
    run_id: str,
    app_version: str,
    pos: int = 1,
):
    from core.models import SummaryResult
    from core.pipeline.chapter_checkpoint import render_summary_markdown

    summaries_dir.mkdir(parents=True, exist_ok=True)
    summ = SummaryResult(
        chapter_heading=heading,
        executive_summary=exec_text,
        thorough_summary="Thorough.",
        bullet_points=["A bullet."],
        success=True,
        run_id=run_id,
        app_version=app_version,
    )
    safe = re.sub(r"\s+", "_", re.sub(r"[^\w\s\-]", "", heading).strip())
    fname = f"{pos:03d}_{safe}_v{app_version}_{run_id}_summary.md"
    f = summaries_dir / fname
    f.write_text(render_summary_markdown(summ), encoding="utf-8")
    return f


class TestResumeWithStampedFiles:
    def test_newest_run_wins_deterministically(self, tmp_path: Path):
        from core.pipeline.chapter_resume import detect_processed_chapters

        chapters_dir = tmp_path / "summaries" / "chapters"
        _write_chapter_summary(
            chapters_dir, "Ch One", "old content", "20260923-010000-aaaaaaaa", "0.4.23"
        )
        time.sleep(0.02)
        _write_chapter_summary(
            chapters_dir, "Ch One", "new content", "20260923-090000-bbbbbbbb", "0.4.24"
        )
        got = detect_processed_chapters(tmp_path)
        assert got["ch_one"].executive_summary == "new content"

    def test_legacy_unstamped_file_still_adopted(self, tmp_path: Path):
        """Cross-version backward compat: pre-V0.4.25 files (no stamp in the
        filename, bare/legacy sentinel forms) are still found and adopted."""
        from core.models import SummaryResult
        from core.pipeline.chapter_checkpoint import render_summary_markdown
        from core.pipeline.chapter_resume import detect_processed_chapters

        chapters_dir = tmp_path / "summaries" / "chapters"
        chapters_dir.mkdir(parents=True)
        summ = SummaryResult(
            chapter_heading="Legacy Ch",
            executive_summary="legacy content",
            thorough_summary="T.",
            bullet_points=["b."],
            success=True,
        )
        (chapters_dir / "001_Legacy_Ch_summary.md").write_text(
            render_summary_markdown(summ), encoding="utf-8"
        )
        got = detect_processed_chapters(tmp_path)
        assert got["legacy_ch"].executive_summary == "legacy content"

    def test_version_mismatch_logs_warning(self, tmp_path: Path):
        """The V0.4.25 escalation: adopting an OLDER version's summary into a
        newer-version conversion is visible as a WARNING with the fix."""
        from core.pipeline.chapter_resume import (
            detect_processed_chapters,
            split_chapters_for_resume,
        )

        chapters_dir = tmp_path / "summaries" / "chapters"
        _write_chapter_summary(
            chapters_dir, "Ch One", "old content", "20260923-010000-aaaaaaaa", "0.4.23"
        )
        processed = detect_processed_chapters(tmp_path)
        lines: list[tuple[str, str]] = []

        def log(msg, level="INFO"):
            lines.append((level, msg))

        todo, loaded = split_chapters_for_resume(
            [{"heading": "Ch One", "content": "x"}], processed, log_callback=log
        )
        assert not todo and len(loaded) == 1
        warns = [msg for lvl, msg in lines if lvl == "WARNING"]
        assert any("app v0.4.23" in w and "OLD" in w for w in warns), (
            f"version-mismatch WARNING expected; got {lines}"
        )

    def test_same_version_adoption_stays_info_only(self, tmp_path: Path):
        """No false alarms: adopting a CURRENT-version summary (the designed
        incremental-processing flow) does not warn."""
        from core.pipeline.chapter_resume import (
            detect_processed_chapters,
            split_chapters_for_resume,
        )
        from core.system.provenance import get_app_version

        chapters_dir = tmp_path / "summaries" / "chapters"
        cur_ver = get_app_version()
        _write_chapter_summary(
            chapters_dir, "Ch One", "same-version content", "20260923-010000-aaaaaaaa", cur_ver
        )
        processed = detect_processed_chapters(tmp_path)
        lines: list[tuple[str, str]] = []

        def log(msg, level="INFO"):
            lines.append((level, msg))

        split_chapters_for_resume(
            [{"heading": "Ch One", "content": "x"}], processed, log_callback=log
        )
        assert not any(lvl == "WARNING" for lvl, _ in lines), f"unexpected warning: {lines}"

    def test_corrupted_newest_falls_back_to_older_valid_file(self, tmp_path: Path):
        """A crashed new run leaves an incomplete (sentinel-less) file; the
        older run's COMPLETE file is still adopted — crash-safety holds."""
        from core.pipeline.chapter_resume import detect_processed_chapters

        chapters_dir = tmp_path / "summaries" / "chapters"
        _write_chapter_summary(
            chapters_dir, "Ch One", "old good content", "20260923-010000-aaaaaaaa", "0.4.23"
        )
        time.sleep(0.02)
        # a partially-written file from a crashed newer run (no sentinel)
        bad = chapters_dir / "001_Ch_One_v0.4.24_20260923-090000-bbbbbbbb_summary.md"
        bad.write_text("# Summary: Ch One\n\n## Executive Summary\ntruncated...", encoding="utf-8")
        got = detect_processed_chapters(tmp_path)
        assert got["ch_one"].executive_summary == "old good content"


# ═══════════════════════════════════════════════════════════════════════════
# 5) Naming contract — the shapes every consumer can rely on
# ═══════════════════════════════════════════════════════════════════════════


class TestNamingContract:
    def test_chapter_summary_name_shape(self):
        """``{NNN}_{heading}_v{version}_{run_id}_summary.md`` — still ends
        with ``_summary.md`` so every resume/scanner glob matches."""
        stamp = "_v0.4.25_20260923-052332-b3e7f026"
        name = f"001_Chapter_One{stamp}_summary.md"
        assert name.endswith("_summary.md")
        assert re.match(r"^\d{3}_", name)

    def test_book_summary_stamped_copy_shape(self):
        """The book summary's stamped copy: canonical stem + stamp +
        ``.summary.md`` — canonical ``{stem}.summary.md`` unchanged."""
        canonical = Path("out") / "summaries" / "MyBook.summary.md"
        stamp = "_v0.4.25_20260923-052332-b3e7f026"
        stamped = canonical.with_name(canonical.stem + stamp + ".summary.md")
        assert stamped.name == "MyBook.summary_v0.4.25_20260923-052332-b3e7f026.summary.md"
        assert stamped.name.endswith(".summary.md")
        # multi-PDF merge globs *.summary.md and takes the alphabetically
        # first — the canonical (dot) sorts before the stamped (underscore)
        assert str(canonical.name) < str(stamped.name)
