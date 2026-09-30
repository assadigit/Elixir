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
        assert set(manifest["chapters"].keys()) == {"1", "2"}


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
        from core.summarisation import _runtime_state as rts

        assert rts.state.warned_embedding_disabled is False
        assert rts.state.warned_semantic_fallback is False
        assert rts.state.warned_no_embed_model is False
        assert rts.state.spacy_nlp is None
        assert rts.state.keep_alive_cache is None
