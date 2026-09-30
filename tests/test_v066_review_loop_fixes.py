"""V0.6.6 — the review-loop Loop-1 fixes. House 3-layer pattern
(test_v065_rtl_styler_translation.py is the reference).

Layer 1 — pure helpers:
  compute_final_positions (core/pipeline/conversion/summarization.py) —
  duplicate headings are excluded from the heading→position map (A1),
  unique headings keep exact end-of-run numbering;
  _stable_anki_ids (core/outputs/anki_export.py) — crc32-based, stable
  across processes (A2; hash() is salted per PYTHONHASHSEED run).

Layer 2 — the saver on REAL files:
  two SAME-heading chapters through the REAL ChapterCheckpointSaver with
  the map the fixed builder produces → both survive with distinct files
  (pre-fix: the second chapter's summary was silently lost — write-once
  skipped it — and the first was saved twice while the second's DOCX
  overwrote the first's).

Canaries (session-order pins for the test-infra fixes):
  Settings._test_override is None at test time (the v065/v0600 leak
  class — an empty dict left in the slot becomes the global Settings()
  and returns None for every .get());
  core.summarisation._runtime_state holds its defaults at test time
  (the golden_freeze cross-file pollution class, B1 — fixed by the
  session-wide conftest reset).

CLI guard:
  tools/publish_release.py --all --zip is rejected (A3) — the --all
  loop never forwarded --zip, so a live run would have published six
  releases with zero assets, silently.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


# ── shared harness (mirrors tests/test_v18203_incremental_checkpoint.py) ──


class _StubPaths:
    def __init__(self, root: Path):
        self.root = root
        self.summaries_dir = root / "summaries"
        self.book_summary = self.summaries_dir / "Book.summary.md"


class _StubCheckpoint:
    def __init__(self):
        self.calls = []

    def mark_progress(self, phase, **metadata):
        self.calls.append((phase, dict(metadata)))


class _StubRequest:
    generate_docx = True
    docx_author = "Elixir"
    docx_include_toc = True

    def __init__(self, p: Path):
        self.input_path = p


class _StubConverter:
    """Minimal converter surface used by ChapterCheckpointSaver."""

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


def _summary(heading: str, marker: str, success: bool = True):
    from core.models import SummaryResult

    return SummaryResult(
        chapter_heading=heading,
        executive_summary=f"Executive summary for {heading} — {marker}.",
        thorough_summary=f"Thorough summary for {heading} — {marker}.",
        bullet_points=[f"{marker} bullet {i} about {heading} (1975)." for i in range(3)],
        success=success,
        error_msg=None if success else "boom",
    )


# ═══════════════════════════════════════════════════════════════════════
# A1 — duplicate chapter headings (checkpoint collision, silent data loss)
# ═══════════════════════════════════════════════════════════════════════


class TestComputeFinalPositions:
    """Layer 1 — the heading→position map builder (V0.6.6 extraction)."""

    @staticmethod
    def _segs(*headings: str):
        return [SimpleNamespace(heading=h) for h in headings]

    def test_unique_headings_keep_exact_positions(self):
        from core.pipeline.conversion.summarization import compute_final_positions

        segs = self._segs("Introduction", "Chapter One", "Chapter Two")
        pos = compute_final_positions(segs, {"Introduction", "Chapter One", "Chapter Two"}, set())
        assert pos == {"Introduction": 1, "Chapter One": 2, "Chapter Two": 3}

    def test_duplicate_headings_are_excluded_from_the_map(self):
        """The A1 fix: a heading carried by two summarized chapters must
        NOT enter the map — the saver falls back to its per-run chapter
        index (unique per chapter) instead of collapsing both chapters
        onto one filename."""
        from core.pipeline.conversion.summarization import compute_final_positions

        segs = self._segs("Introduction", "Chapter One", "Introduction")
        pos = compute_final_positions(segs, {"Introduction", "Chapter One"}, set())
        assert "Introduction" not in pos
        assert pos == {"Chapter One": 2}

    def test_resume_mixed_duplicate_is_excluded(self):
        """One todo + one loaded chapter sharing a heading is equally
        ambiguous for a heading-keyed map — excluded too."""
        from core.pipeline.conversion.summarization import compute_final_positions

        segs = self._segs("Notes", "Chapter One", "Notes")
        pos = compute_final_positions(segs, {"Chapter One", "Notes"}, {"Notes"})
        assert "Notes" not in pos
        assert pos == {"Chapter One": 2}

    def test_loaded_only_headings_are_positioned(self):
        from core.pipeline.conversion.summarization import compute_final_positions

        segs = self._segs("Loaded One", "Chapter One", "Loaded Two")
        pos = compute_final_positions(segs, {"Chapter One"}, {"Loaded One", "Loaded Two"})
        assert pos == {"Loaded One": 1, "Chapter One": 2, "Loaded Two": 3}


class TestDuplicateHeadingCheckpointSurvival:
    """Layer 2 — the real saver, end to end on REAL files.

    Regression pin for the A1 defect: two same-heading chapters through
    the checkpoint saver with the map the FIXED builder produces. Pre-fix
    (heading-keyed map with the collision) the second chapter's summary
    was silently lost and the first was written twice.
    """

    def test_two_same_heading_chapters_both_survive(self, tmp_path):
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver
        from core.pipeline.conversion.summarization import compute_final_positions

        root = tmp_path / "MyBook"
        root.mkdir()
        conv = _StubConverter(root)
        chapters = [
            {"heading": "Introduction", "content": "First intro content. " * 40},
            {"heading": "Chapter One", "content": "Content one. " * 40},
            {"heading": "Introduction", "content": "Second intro content. " * 40},
        ]
        segs = [SimpleNamespace(heading=c["heading"]) for c in chapters]
        positions = compute_final_positions(segs, {c["heading"] for c in chapters}, set())
        assert positions == {"Chapter One": 2}  # duplicates omitted (A1)

        saver = ChapterCheckpointSaver(conv, positions, 3, build_docx=True, book_title="MyBook")
        saver.on_chapter_done(1, _summary("Introduction", "FIRST"), chapters[0])
        saver.on_chapter_done(2, _summary("Chapter One", "MID"), chapters[1])
        saver.on_chapter_done(3, _summary("Introduction", "SECOND"), chapters[2])

        sdir = conv.output_dir / "summaries"
        files = sorted(p.name for p in sdir.glob("*_summary.md"))
        assert files == [
            "001_Introduction_summary.md",
            "002_Chapter_One_summary.md",
            "003_Introduction_summary.md",
        ]
        first = (sdir / "001_Introduction_summary.md").read_text(encoding="utf-8")
        second = (sdir / "003_Introduction_summary.md").read_text(encoding="utf-8")
        assert "FIRST" in first and "SECOND" not in first
        assert "SECOND" in second and "FIRST" not in second
        # both per-chapter DOCX folders exist (pre-fix the second's DOCX
        # overwrote the first's at the shared position)
        chapters_root = conv.output_dir / "checkpoints" / "chapters"
        assert (chapters_root / "001_Introduction" / "001_Introduction_summary.docx").exists()
        assert (chapters_root / "003_Introduction" / "003_Introduction_summary.docx").exists()
        assert saver.saved_count == 3
        assert saver.skipped_existing == 0

    def test_duplicate_positions_are_never_shared_in_manifest(self, tmp_path):
        """The manifest is keyed by str(pos) — distinct fallback positions
        mean distinct manifest records (no chapter record is clobbered)."""
        import json

        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver
        from core.pipeline.conversion.summarization import compute_final_positions

        root = tmp_path / "MyBook"
        root.mkdir()
        conv = _StubConverter(root)
        chapters = [
            {"heading": "Notes", "content": "First notes. " * 40},
            {"heading": "Notes", "content": "Second notes. " * 40},
        ]
        segs = [SimpleNamespace(heading=c["heading"]) for c in chapters]
        positions = compute_final_positions(segs, {"Notes"}, set())
        assert positions == {}  # both excluded → idx fallback 1 and 2

        saver = ChapterCheckpointSaver(conv, positions, 2, build_docx=False, book_title="MyBook")
        saver.on_chapter_done(1, _summary("Notes", "FIRST"), chapters[0])
        saver.on_chapter_done(2, _summary("Notes", "SECOND"), chapters[1])

        manifest = json.loads(
            (conv.output_dir / "checkpoints" / "chapter_manifest.json").read_text(encoding="utf-8")
        )
        # V0.6.6 (L2-3): keyed by canonical filename — the two duplicate
        # "Notes" chapters get distinct records even at distinct fallback
        # positions (pre-L2-3 a colliding pos clobbered records).
        assert set(manifest["chapters"].keys()) == {
            "001_Notes_summary.md",
            "002_Notes_summary.md",
        }


# ═══════════════════════════════════════════════════════════════════════
# L2-2 — merge_summaries: duplicate headings + resume (data loss)
# ═══════════════════════════════════════════════════════════════════════


class TestMergeSummariesDuplicates:
    """chapter_resume.merge_summaries — occurrence-aware merge (V0.6.6).

    The old heading-keyed dict dropped a LOADED chapter's summary whenever
    duplicate headings + resume coincided, and emitted the NEW summary
    twice instead (fresh-eyes probe: merged=[NEW, NEW], OLD lost — the
    final book outputs build on the merged list, so the loaded chapter
    silently vanished from Book.summary.md / DOCX).
    """

    def test_duplicate_headings_resume_keeps_both(self):
        from core.pipeline.chapter_resume import merge_summaries

        x_new = _summary("Notes", "NEW")
        y = _summary("Chapter One", "LOADED")
        x_old = _summary("Notes", "OLD")
        merged = merge_summaries([x_new], [y, x_old], ["Notes", "Chapter One", "Notes"])
        assert [id(s) for s in merged] == [id(x_new), id(y), id(x_old)]

    def test_unique_heading_new_still_wins_over_loaded(self):
        """Regression: the "don't overwrite new with loaded" rule for
        UNIQUE headings is byte-identical to the old dict behavior."""
        from core.pipeline.chapter_resume import merge_summaries

        x_new = _summary("Chapter One", "NEW")
        x_old = _summary("Chapter One", "OLD")
        merged = merge_summaries([x_new], [x_old], ["Chapter One"])
        assert [id(s) for s in merged] == [id(x_new)]

    def test_no_phantom_duplication_when_order_repeats(self):
        """A heading appearing twice in chapter_order with ONE summary
        must not emit the same summary object twice (the old dict did)."""
        from core.pipeline.chapter_resume import merge_summaries

        x = _summary("Notes", "ONLY")
        merged = merge_summaries([x], [], ["Notes", "Notes"])
        assert len(merged) == 1
        assert merged[0] is x

    def test_unique_headings_merge_in_book_order(self):
        from core.pipeline.chapter_resume import merge_summaries

        a = _summary("Alpha", "NEW")
        b = _summary("Beta", "LOADED")
        c = _summary("Gamma", "NEW")
        merged = merge_summaries([a, c], [b], ["Alpha", "Beta", "Gamma"])
        assert [id(s) for s in merged] == [id(a), id(b), id(c)]


# ═══════════════════════════════════════════════════════════════════════
# L2-3 — checkpoint manifest keys + the run-stamped per-chapter DOCX
# ═══════════════════════════════════════════════════════════════════════


class TestManifestKeysAndDocxStamp:
    def test_manifest_survives_colliding_positions(self, tmp_path):
        """A duplicate-heading chapter's fallback index can EQUAL another
        chapter's mapped position — the manifest must keep both records
        (pre-L2-3 they clobbered each other under the shared str(pos) key)."""
        import json

        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver
        from core.pipeline.conversion.summarization import compute_final_positions

        root = tmp_path / "MyBook"
        root.mkdir()
        conv = _StubConverter(root)
        # Run order (chapter_dicts, e.g. a reordered user selection):
        # [Beta, Beta, Alpha] — callback idxs 1, 2, 3.
        chapters = [
            {"heading": "Beta", "content": "Beta one. " * 40},
            {"heading": "Beta", "content": "Beta two. " * 40},
            {"heading": "Alpha", "content": "Alpha. " * 40},
        ]
        # SEGMENT order: [Alpha, Beta, Beta] — Alpha is unique → mapped
        # position 1; Beta is duplicated → excluded, falls back to idx.
        segs = [
            SimpleNamespace(heading="Alpha"),
            SimpleNamespace(heading="Beta"),
            SimpleNamespace(heading="Beta"),
        ]
        positions = compute_final_positions(segs, {"Alpha", "Beta"}, set())
        assert positions == {"Alpha": 1}
        # Beta #1's fallback index (1) collides with Alpha's mapped pos (1).

        saver = ChapterCheckpointSaver(conv, positions, 3, build_docx=False, book_title="MyBook")
        saver.on_chapter_done(1, _summary("Beta", "B1"), chapters[0])
        saver.on_chapter_done(2, _summary("Beta", "B2"), chapters[1])
        saver.on_chapter_done(3, _summary("Alpha", "A"), chapters[2])

        manifest = json.loads(
            (conv.output_dir / "checkpoints" / "chapter_manifest.json").read_text(encoding="utf-8")
        )
        assert set(manifest["chapters"].keys()) == {
            "001_Beta_summary.md",
            "002_Beta_summary.md",
            "001_Alpha_summary.md",
        }
        # the pos collision is visible but harmless — records are intact
        assert manifest["chapters"]["001_Beta_summary.md"]["pos"] == 1
        assert manifest["chapters"]["001_Alpha_summary.md"]["pos"] == 1

    def test_stamped_docx_carries_the_run_stamp(self, tmp_path, monkeypatch):
        """The per-chapter DOCX filename carries the SAME run stamp as its
        sibling md (pre-L2-3 it never did — an un-stamped name shared
        across runs let a later run overwrite a completed chapter's DOCX)."""
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root = tmp_path / "MyBook"
        root.mkdir()
        conv = _StubConverter(root)
        chapter = {"heading": "Notes", "content": "Notes content. " * 40}
        saver = ChapterCheckpointSaver(conv, {"Notes": 1}, 1, build_docx=True, book_title="MyBook")

        class _StubBuilder:
            def __init__(self, request, log_callback=None):
                pass

            def build_report(self, summaries, chapters, input_path, out_path):
                out_path.write_bytes(b"PK docx bytes")
                return True

        import core.docx.builder as builder_mod

        monkeypatch.setattr(builder_mod, "DocxBuilder", _StubBuilder)

        summ = _summary("Notes", "STAMPED")
        summ.run_id = "20260930-010000-aaaaaaaa"
        summ.app_version = "0.6.6"
        saver.on_chapter_done(1, summ, chapter)

        expected_md = "001_Notes_v0.6.6_20260930-010000-aaaaaaaa_summary.md"
        expected_docx = "001_Notes_v0.6.6_20260930-010000-aaaaaaaa_summary.docx"
        folder = conv.output_dir / "checkpoints" / "chapters" / "001_Notes"
        assert (conv.output_dir / "summaries" / expected_md).exists()
        assert (folder / expected_docx).exists(), sorted(p.name for p in folder.iterdir())

    def test_resumed_run_never_overwrites_completed_docx(self, tmp_path, monkeypatch):
        """The fresh-eyes repro: RUN2 writing the same pos+heading chapter
        must leave RUN1's completed DOCX untouched (names differ by stamp)."""
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        root = tmp_path / "MyBook"
        root.mkdir()
        conv = _StubConverter(root)
        chapter = {"heading": "Notes", "content": "Notes content. " * 40}

        class _MarkerBuilder:
            def __init__(self, request, log_callback=None):
                pass

            def build_report(self, summaries, chapters, input_path, out_path):
                out_path.write_bytes(summaries[0].executive_summary.encode("utf-8"))
                return True

        import core.docx.builder as builder_mod

        monkeypatch.setattr(builder_mod, "DocxBuilder", _MarkerBuilder)

        def _run(run_id, marker):
            saver = ChapterCheckpointSaver(
                conv, {"Notes": 1}, 1, build_docx=True, book_title="MyBook"
            )
            summ = _summary("Notes", marker)
            summ.run_id = run_id
            summ.app_version = "0.6.6"
            saver.on_chapter_done(1, summ, chapter)

        _run("20260930-010000-aaaaaaaa", "RUN1")
        _run("20260930-020000-bbbbbbbb", "RUN2")

        folder = conv.output_dir / "checkpoints" / "chapters" / "001_Notes"
        docx_files = sorted(folder.glob("*_summary.docx"))
        assert len(docx_files) == 2, "both runs' DOCX coexist (audit trail)"
        by_name = {p.name: p.read_bytes() for p in docx_files}
        run1_name = "001_Notes_v0.6.6_20260930-010000-aaaaaaaa_summary.docx"
        assert run1_name in by_name
        assert b"RUN1" in by_name[run1_name], "RUN1's completed DOCX must be untouched"


# ═══════════════════════════════════════════════════════════════════════
# A2 — Anki deck/model ids must be stable across processes
# ═══════════════════════════════════════════════════════════════════════


class TestStableAnkiIds:
    def _ids_in_subprocess(self, seed: str, title: str) -> str:
        """Load anki_export.py BY PATH (bypassing the heavy package
        __init__) in a fresh interpreter with a fixed hash seed."""
        code = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location("
            "'anki_export_under_test', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "print(mod._stable_anki_ids(sys.argv[2]))\n"
        )
        env = {**os.environ, "PYTHONHASHSEED": seed}
        r = subprocess.run(
            [sys.executable, "-c", code, str(REPO / "core" / "outputs" / "anki_export.py"), title],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    def test_same_title_same_ids_across_hash_seeds(self):
        """The A2 defect: hash()-derived ids differed per process
        (PYTHONHASHSEED salts str hash) → Anki duplicated the deck on
        every re-import of an updated .apkg."""
        id_run_1 = self._ids_in_subprocess("1", "A Book Title")
        id_run_2 = self._ids_in_subprocess("2", "A Book Title")
        id_run_3 = self._ids_in_subprocess("42", "A Book Title")
        assert id_run_1 == id_run_2 == id_run_3

    def test_different_titles_get_different_ids(self):
        from core.outputs.anki_export import _stable_anki_ids

        a = _stable_anki_ids("One Book")
        b = _stable_anki_ids("Another Book")
        assert a[0] != b[0]
        assert a[1] != b[1]

    def test_ids_stay_in_the_documented_range(self):
        from core.outputs.anki_export import _stable_anki_ids

        model_id, deck_id = _stable_anki_ids("Any Book")
        assert 1607392319 <= model_id < 1607392319 + 100000
        assert 1607392319 <= deck_id < 1607392319 + 100000
        assert model_id != deck_id


# ═══════════════════════════════════════════════════════════════════════
# A3 — publish_release.py: --all must reject --zip (silently dropped it)
# ═══════════════════════════════════════════════════════════════════════


class TestPublishReleaseCliGuard:
    def test_all_plus_zip_is_rejected(self):
        """Pre-fix: `--all --zip X` printed 6 × 'would create/update
        release' with NO asset mention and exited 0 — a live run would
        have published every release with zero assets (Rule-6 break)."""
        r = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "publish_release.py"),
                "--all",
                "--zip",
                "some.zip",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 2
        assert "--zip" in r.stderr

    def test_all_alone_still_works_in_dry_run(self):
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "publish_release.py"), "--all", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0
        assert "would create/update release" in r.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test-infra canaries (session-order pins)
# ═══════════════════════════════════════════════════════════════════════


class TestSessionStateCanaries:
    """In-suite canaries: this file runs AFTER test_v065_*/test_v0600_*
    alphabetically, so any Settings._test_override leak (the empty-dict
    bug class fixed in V0.6.6) or _runtime_state pollution (the B1
    cross-file leak fixed by the conftest reset) trips these BEFORE the
    downstream characterization tests notice."""

    def test_settings_test_override_is_none(self):
        from utils.settings import Settings

        assert Settings._test_override is None

    def test_runtime_state_holds_defaults(self):
        """Pins that state.reset() restores the documented defaults and
        that the defaults keep their shape (a tripwire for reset()
        itself breaking or the default set drifting — cross-test
        pollution is prevented by the conftest autouse reset, which runs
        before this test too, so pollution alone cannot trip this)."""
        from core.summarisation import _runtime_state as rts

        assert rts.state.warned_embedding_disabled is False
        assert rts.state.warned_semantic_fallback is False
        assert rts.state.warned_no_embed_model is False
        assert rts.state.spacy_nlp is None
        assert rts.state.keep_alive_cache is None


# ═══════════════════════════════════════════════════════════════════════
# B2 — multi_format_reader: the multi-format INPUT feature had ZERO tests
# ═══════════════════════════════════════════════════════════════════════


class TestMultiFormatReader:
    """core/pipeline/multi_format_reader.py — Layer-1 coverage for the
    V10.20.0 multi-format input (EPUB/DOCX/TXT/MD/HTML), live-wired into
    the conversion route at extraction.py:148 with 0% coverage before
    V0.6.6 (review-loop B2). Real files, real parsing, stdlib-built
    fixtures — no optional deps required except the ones already in the
    test env (python-docx, bs4)."""

    def test_txt_roundtrip(self, tmp_path):
        from core.pipeline.multi_format_reader import extract_text

        p = tmp_path / "book.txt"
        p.write_text("Chapter one text.\n\nChapter two text.", encoding="utf-8")
        text, pages = extract_text(p)
        assert text == "Chapter one text.\n\nChapter two text."
        assert pages == max(1, len(text) // 3000)

    def test_md_and_rst_route_as_text(self, tmp_path):
        from core.pipeline.multi_format_reader import extract_text

        for name in ("note.md", "doc.rst", "doc.asciidoc", "doc.adoc"):
            p = tmp_path / name
            p.write_text("Some long enough content here. " * 10, encoding="utf-8")
            text, pages = extract_text(p)
            assert "long enough content" in text
            assert pages >= 1

    def test_pdf_suffix_routes_to_main_pipeline_placeholder(self):
        from core.pipeline.multi_format_reader import extract_text

        # The contract: PDF never extracts here — the main PDF pipeline
        # owns it (extraction.py checks the suffix first).
        text, pages = extract_text(Path("whatever.pdf"))
        assert text == "" and pages == 0

    def test_docx_primary_path_preserves_headings(self, tmp_path):
        import docx as docx_lib

        from core.pipeline.multi_format_reader import extract_text

        d = docx_lib.Document()
        d.add_heading("A Section Title", level=2)
        d.add_paragraph("Body paragraph one.")
        d.add_paragraph("Body paragraph two.")
        p = tmp_path / "book.docx"
        d.save(str(p))

        text, pages = extract_text(p)
        assert "## A Section Title" in text, "heading structure must survive"
        assert "Body paragraph one." in text
        assert "Body paragraph two." in text
        assert pages >= 1

    def test_docx_stdlib_fallback(self, tmp_path, monkeypatch):
        """The ImportError path (no python-docx on the machine): parse
        word/document.xml straight out of the zip."""
        import zipfile

        from core.pipeline.multi_format_reader import extract_text

        xml = (
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            "<w:p><w:r><w:t>Fallback paragraph alpha</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Fallback paragraph beta</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        p = tmp_path / "book.docx"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("word/document.xml", xml)

        monkeypatch.setitem(sys.modules, "docx", None)  # force ImportError
        text, _pages = extract_text(p)
        assert "Fallback paragraph alpha" in text
        assert "Fallback paragraph beta" in text

    def test_epub_stdlib_fallback(self, tmp_path, monkeypatch):
        import zipfile

        from core.pipeline.multi_format_reader import extract_text

        p = tmp_path / "book.epub"
        chapter_html = "<html><body><p>" + "Epub chapter content here. " * 20 + "</p></body></html>"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("OEBPS/ch1.xhtml", chapter_html)

        monkeypatch.setitem(sys.modules, "ebooklib", None)  # force ImportError
        text, pages = extract_text(p)
        assert "Epub chapter content here." in text
        assert "<p>" not in text, "HTML tags must be stripped in the fallback"
        assert "<html>" not in text
        assert pages >= 1

    def test_html_strips_script_and_style(self, tmp_path):
        from core.pipeline.multi_format_reader import extract_text

        p = tmp_path / "page.html"
        p.write_text(
            "<html><head><style>body{color:red}</style>"
            "<script>var secret_token = 1;</script></head>"
            "<body><p>Visible page content.</p></body></html>",
            encoding="utf-8",
        )
        text, _pages = extract_text(p)
        assert "Visible page content." in text
        assert "secret_token" not in text
        assert "color:red" not in text

    def test_unknown_suffix_falls_back_to_text_with_warning(self, tmp_path):
        from core.pipeline.multi_format_reader import extract_text

        p = tmp_path / "data.weird"
        p.write_text("Unknown-format body text. " * 10, encoding="utf-8")
        logs = []
        text, _pages = extract_text(p, log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert "Unknown-format body text." in text
        assert any("Unknown format" in m and lvl == "WARNING" for lvl, m in logs)

    def test_is_supported_format_matrix(self, tmp_path):
        from core.pipeline.multi_format_reader import is_supported_format

        for ok in (
            ".pdf",
            ".epub",
            ".docx",
            ".txt",
            ".md",
            ".rst",
            ".asciidoc",
            ".adoc",
            ".html",
            ".htm",
        ):
            assert is_supported_format(Path(f"x{ok}")), ok
        assert not is_supported_format(Path("x.doc"))
        assert not is_supported_format(Path("x.epub2"))


# ═══════════════════════════════════════════════════════════════════════
# B5 — core/validation/validator.py: the Validation Tool engine (0% → tested)
# ═══════════════════════════════════════════════════════════════════════


class TestValidationEngine:
    """core/validation/validator.py — the engine behind the Validate
    dialog (ui_qt/views/validate_dialog.py), 89 stmts at 0% before
    V0.6.6 (review-loop B5). Pure Python — load → validate → report on
    tmp files."""

    @staticmethod
    def _write(path: Path, content: str) -> Path:
        path.write_text(content, encoding="utf-8")
        return path

    def test_load_missing_source_returns_false(self, tmp_path):
        from core.validation.validator import Validator

        v = Validator(tmp_path / "nope.md")
        assert v.load() is False

    def test_load_auto_discovers_sibling_summary(self, tmp_path):
        from core.validation.validator import Validator

        src = self._write(tmp_path / "book.md", "source content with words.")
        self._write(tmp_path / "book.summary.md", "summary content with words.")
        v = Validator(src)
        assert v.load() is True
        assert v.summary_text == "summary content with words."

    def test_validate_without_summary_reports_keywords_only(self, tmp_path):
        from core.validation.validator import Validator

        src = self._write(tmp_path / "solo.md", "asteroid telescope observatory. " * 5)
        v = Validator(src)
        assert v.load() is True
        result = v.validate()
        assert result["summary_found"] is False
        assert result["source_keywords"], "keywords extracted from source alone"

    def test_extract_keywords_excludes_stopwords_and_orders_by_frequency(self, tmp_path):
        from core.validation.validator import Validator

        v = Validator(self._write(tmp_path / "s.md", "x"))
        text = "the and of zebra zebra zebra apple apple pear"
        kws = v._extract_keywords(text, n=10)
        assert kws[0] == "zebra", "frequency ordering"
        assert "apple" in kws and "pear" in kws
        assert "the" not in kws and "chapter" not in kws  # stopwords stay out

    def test_extract_keywords_includes_persian_when_dominant(self, tmp_path):
        from core.validation.validator import Validator

        v = Validator(self._write(tmp_path / "s.md", "x"))
        persian = "کتاب‌ها و فصل‌های ستاره‌شناسی " * 5  # dominant Persian text
        kws = v._extract_keywords(persian, n=10)
        assert any("\u0600" <= ch <= "\u06ff" for kw in kws for ch in kw), (
            "Persian words must join the keyword pool for Persian sources"
        )

    def test_compute_coverage_math(self, tmp_path):
        from core.validation.validator import Validator

        v = Validator(self._write(tmp_path / "s.md", "x"))
        cov = v.compute_coverage(["alpha", "beta", "gamma"], "alpha and gamma appear")
        assert cov["coverage"] == 2 / 3
        assert cov["present"] == ["alpha", "gamma"]
        assert cov["missing"] == ["beta"]
        # empty keyword list → perfect coverage by definition
        assert v.compute_coverage([], "anything")["coverage"] == 1.0

    def test_validate_end_to_end_coverage_and_hallucination(self, tmp_path):
        from core.validation.validator import Validator

        src = self._write(
            tmp_path / "book.md",
            "Magnetism attracts iron. Magnetism repels nickel. Gravity bends light. "
            "Entropy always increases. " * 3,
        )
        summ = self._write(
            tmp_path / "book.summary.md",
            "Magnetism attracts iron and repels nickel. Unicorn glitter abounds.",
        )
        v = Validator(src, summ)
        assert v.load() is True
        result = v.validate()
        assert result["summary_found"] is True
        assert 0.0 < result["coverage"] < 1.0
        assert "magnetism" in result["present"]
        assert "gravity" in result["missing"] or "entropy" in result["missing"]
        assert "unicorn" in result["hallucinated"], "summary-only term is flagged"

    def test_generate_report_error_path(self, tmp_path):
        from core.validation.validator import Validator

        v = Validator(tmp_path / "missing.md")  # never loaded
        assert "❌ Error" in v.generate_report()

    def test_generate_report_full_path_tiers(self, tmp_path):
        from core.validation.validator import Validator

        # high coverage → the "Excellent" recommendation tier
        src = self._write(tmp_path / "b.md", "Magnetism iron nickel. " * 10)
        summ = self._write(tmp_path / "b.summary.md", "Magnetism iron nickel. " * 10)
        v = Validator(src, summ)
        v.load()
        report = v.generate_report()
        assert "📊 VALIDATION REPORT" in report
        assert "Excellent coverage" in report
        assert "No obvious hallucinated terms" in report

        # low coverage → the "low" tier
        summ2 = self._write(tmp_path / "b2.summary.md", "Completely unrelated words here.")
        v2 = Validator(src, summ2)
        v2.load()
        assert "Coverage is low" in v2.generate_report()

    def test_generate_report_no_summary_path(self, tmp_path):
        from core.validation.validator import Validator

        src = self._write(tmp_path / "lonely.md", "asteroid telescope observatory.")
        v = Validator(src)
        v.load()
        report = v.generate_report()
        # Pinned ACTUAL behavior: validate()'s no-summary shape carries an
        # "error" key, so generate_report's error branch fires FIRST — the
        # "⚠️ No summary found" branch (validator.py:298) is unreachable
        # dead code (noted in findings; behavior left unchanged).
        assert "❌ Error: No summary text provided" in report


# ═══════════════════════════════════════════════════════════════════════
# B3 — crash_report: the redaction logic was 100% untested (security-critical)
# ═══════════════════════════════════════════════════════════════════════


class TestCrashReportRedaction:
    """core/system/crash_report.py — the only thing between a user-shared
    crash zip and their API keys (70 stmts, 0% before V0.6.6; review-loop
    B3). Runs exactly when everything else is broken."""

    def test_redaction_variants_nested_and_case_insensitive(self):
        from core.system.crash_report import _redact_settings

        out = _redact_settings(
            {
                "summarisation": {
                    "api_key": "sk-live-123",
                    "API_KEY": "sk-upper-456",
                    "claude_api_key": "sk-ant",
                    "AuthToken": "tok-1",
                    "password": "hunter2",
                },
                "translation": {"secret_phrase": "s", "Bearer": "b"},
                "plain": "untouched",
                "count": 7,
            }
        )
        s = out["summarisation"]
        assert s["api_key"] == "***REDACTED***"
        assert s["API_KEY"] == "***REDACTED***"
        assert s["claude_api_key"] == "***REDACTED***"
        assert s["AuthToken"] == "***REDACTED***"
        assert s["password"] == "***REDACTED***"
        assert out["translation"]["secret_phrase"] == "***REDACTED***"
        # NOTE (pinned): a key named exactly "Bearer" is NOT caught — the
        # V18.1 S4 set matches substrings {api_key, apikey, token, secret,
        # password, auth}, and "bearer" contains none of them. The real
        # settings schema has no such key (Authorization-style headers are
        # "auth"-flavored).
        assert out["translation"]["Bearer"] == "b"
        assert out["plain"] == "untouched"
        assert out["count"] == 7

    def test_redaction_reaches_into_lists(self):
        from core.system.crash_report import _redact_settings

        out = _redact_settings({"profiles": [{"api_key": "k1"}, {"name": "safe", "token": "t"}]})
        assert out["profiles"][0]["api_key"] == "***REDACTED***"
        assert out["profiles"][1]["name"] == "safe"
        assert out["profiles"][1]["token"] == "***REDACTED***"

    def test_empty_secret_value_still_redacted(self):
        """The PRESENCE of the field stays visible without leaking even an
        empty value (the V18.1 S4 contract)."""
        from core.system.crash_report import _redact_settings

        out = _redact_settings({"api_key": ""})
        assert out["api_key"] == "***REDACTED***"

    def test_path_values_scrub_home_prefix(self, tmp_path, monkeypatch):
        from core.system import crash_report as cr

        # The scrubber replaces occurrences of the module's _HOME (bound at
        # import from the real Path.home()) — monkeypatch it for the test.
        home = "/home/someuser"
        monkeypatch.setattr(cr, "_HOME", home)
        out = cr._redact_settings(
            {
                "glossary": f"{home}/docs/glossary.json",
                "output_dir": f"{home}/out",
                "name": f"{home}/inside-a-name",  # not a path key — untouched
                "weird_path": 42,  # non-str path key — untouched
            }
        )
        assert out["glossary"] == "~/docs/glossary.json"
        assert out["output_dir"] == "~/out"
        assert out["name"] == f"{home}/inside-a-name"
        assert out["weird_path"] == 42

    def test_generate_crash_report_end_to_end(self, tmp_path, monkeypatch):
        """Real zip on disk: traceback + system info + REDACTED settings +
        recent_log.txt when lines are passed; absent when not."""
        import json
        import zipfile

        from core.system import crash_report as cr

        crash_dir = tmp_path / "crash_reports"
        monkeypatch.setattr(cr, "_CRASH_DIR", crash_dir)
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps({"summarisation": {"api_key": "sk-super-secret"}}), encoding="utf-8"
        )
        monkeypatch.setattr(cr, "_SETTINGS_FILE", settings_file)

        try:
            raise ValueError("boom-for-the-report")
        except ValueError as e:
            report = cr.generate_crash_report(
                type(e), e, e.__traceback__, extra_log_lines=["a", "b"]
            )

        assert report is not None and report.exists()
        with zipfile.ZipFile(report) as zf:
            names = zf.namelist()
            assert "traceback.txt" in names
            assert "boom-for-the-report" in zf.read("traceback.txt").decode("utf-8")
            assert "system_info.json" in names
            settings_json = json.loads(zf.read("settings_redacted.json").decode("utf-8"))
            assert settings_json["summarisation"]["api_key"] == "***REDACTED***"
            assert "sk-super-secret" not in zf.read("settings_redacted.json").decode("utf-8")
            assert "recent_log.txt" in names
            assert zf.read("recent_log.txt").decode("utf-8") == "a\nb"

    def test_recent_log_absent_without_extra_lines(self, tmp_path, monkeypatch):
        import json
        import zipfile

        from core.system import crash_report as cr

        monkeypatch.setattr(cr, "_CRASH_DIR", tmp_path / "crash_reports")
        monkeypatch.setattr(cr, "_SETTINGS_FILE", tmp_path / "missing-settings.json")
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            report = cr.generate_crash_report(type(e), e, e.__traceback__)
        assert report is not None
        with zipfile.ZipFile(report) as zf:
            assert "recent_log.txt" not in zf.namelist()
            # missing settings file → empty settings dict in the bundle
            assert json.loads(zf.read("settings_redacted.json").decode("utf-8")) == {}

    def test_corrupt_settings_reported_not_crashed(self, tmp_path, monkeypatch):
        import zipfile

        from core.system import crash_report as cr

        monkeypatch.setattr(cr, "_CRASH_DIR", tmp_path / "crash_reports")
        bad = tmp_path / "settings.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(cr, "_SETTINGS_FILE", bad)
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            report = cr.generate_crash_report(type(e), e, e.__traceback__)
        assert report is not None
        with zipfile.ZipFile(report) as zf:
            body = zf.read("settings_redacted.json").decode("utf-8")
            assert "could not parse" in body

    def test_failure_returns_none_never_raises(self, tmp_path, monkeypatch):
        from core.system import crash_report as cr

        blocker = tmp_path / "blocker"  # a FILE where the DIR should be
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setattr(cr, "_CRASH_DIR", blocker)
        try:
            raise RuntimeError("x")
        except RuntimeError as e:
            assert cr.generate_crash_report(type(e), e, e.__traceback__) is None

    def test_collect_recent_log_lines(self, tmp_path, monkeypatch):
        from core.system import crash_report as cr

        log = tmp_path / "system.log"
        log.write_text("\n".join(f"line{i}" for i in range(1, 351)), encoding="utf-8")
        monkeypatch.setattr(cr, "_LOG_FILE", log)

        lines = cr.collect_recent_log_lines(max_lines=200)
        assert lines is not None and len(lines) == 200
        # deque keeps the trailing newline of each line (pinned)
        assert lines[0].rstrip("\n") == "line151"
        assert lines[-1].rstrip("\n") == "line350"

        monkeypatch.setattr(cr, "_LOG_FILE", tmp_path / "absent.log")
        assert cr.collect_recent_log_lines() is None
