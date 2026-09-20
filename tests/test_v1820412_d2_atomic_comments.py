"""V18.20.4.12 (batch D2) — atomic output writes (T-c3 half) + comment
de-jargon (W-a14 residual).

FIX 1 (T-c3 half) — every plain ``Path.write_text`` in the 15 owned output
files (14 ``core/outputs/`` generators + ``core/pipeline/conversion/
output_save.py``'s segment loop) is swapped for
``utils.atomic_io.atomic_write_text`` (same-dir temp file + fsync +
``os.replace``).  A crash / disk-full mid-write can therefore no longer
leave a truncated output file that downstream phases (footnotes, citation
graph, translation, packets, the chapter-resume system) would read as if
it were complete.  ``atomic_write_text`` re-raises OSError (incl.
disk-full) exactly like ``write_text``, so every caller's except-handling
is byte-for-byte unchanged.  The ONE deliberate exception is
``evidence_map.py``'s guidance-HTML fallback: a direct write that only
runs AFTER the atomic write already failed (V10.4.0 Phase 6A-4) — it is
kept non-atomic ON PURPOSE (repeating temp+replace would just fail the
same way) and is now spelled as an explicit ``open()/write()`` pair so
the intent stays visible.

FIX 2 (W-a14 residual) — ``text_preprocessor_impl.py`` comments/docstrings
no longer quote the specific book's jargon ('focus base', 'hourglass
conversation', …): they now describe the PATTERN generically.  The runtime
deny-list rule (no book-derived hardcoding — tests/test_v182047_p5_core_
decomp.py) extends to comments because they were the copy-paste leak
source.  ZERO runtime change — comments/docstrings only.

Hermetic: markitdown stubbed in sys.modules (the
tests/test_integration_pipeline.py:45-58 pattern); no Qt, no network.

Run: ``pytest tests/test_v1820412_d2_atomic_comments.py -v``
"""

from __future__ import annotations

import ast
import importlib
import py_compile
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Hermetic stub (before any core.pipeline import) ────────────────────────
# markitdown is imported at module level by core.pdf.adaptive_toc, which
# sits in the core.pipeline.conversion.output_save import chain.
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = type("MarkItDown", (), {})
    sys.modules["markitdown"] = _md

# ── The 15 FIX-1 owned files (packets/generator.py was done separately) ────
_OWNED_FILES = [
    "core/outputs/podcast_generator.py",
    "core/outputs/podcast_audio.py",
    "core/outputs/service_formatters.py",
    "core/outputs/study_guide.py",
    "core/outputs/citation_graph.py",
    "core/outputs/evidence_map.py",
    "core/outputs/mind_map.py",
    "core/outputs/packets_extensions.py",
    "core/outputs/new_outputs.py",
    "core/outputs/reference_outputs.py",
    "core/outputs/quote_bank.py",
    "core/outputs/chapters_export.py",
    "core/outputs/social_media.py",
    "core/outputs/obsidian_kb.py",
    "core/pipeline/conversion/output_save.py",
]

# Expected atomic_write_text CALL sites per file (evidence_map's 3 and
# output_save's full-markdown write pre-date this batch; the rest are the
# V18.20.4.12 T-c3 swaps).
_EXPECTED_ATOMIC_CALLS = {
    "core/outputs/podcast_generator.py": 1,
    "core/outputs/podcast_audio.py": 1,
    "core/outputs/service_formatters.py": 4,
    "core/outputs/study_guide.py": 1,
    "core/outputs/citation_graph.py": 1,
    "core/outputs/evidence_map.py": 3,
    "core/outputs/mind_map.py": 1,
    "core/outputs/packets_extensions.py": 1,
    "core/outputs/new_outputs.py": 4,
    "core/outputs/reference_outputs.py": 4,
    "core/outputs/quote_bank.py": 1,
    "core/outputs/chapters_export.py": 1,
    "core/outputs/social_media.py": 1,
    "core/outputs/obsidian_kb.py": 2,
    "core/pipeline/conversion/output_save.py": 2,
}

# FIX-2 owned files (comment de-jargon) + the book phrases that must not
# appear anywhere in them (comments and docstrings included, zero allowlist).
_COMMENT_FILES = [
    "core/summarisation/text_preprocessor_impl.py",
    "core/summarisation/postcheck_detectors.py",
    # V0.18 (Phase 5.2): the postchecks package files (verbatim moves from
    # postcheck_detectors.py) join the no-book-jargon scan.
    "core/summarisation/postchecks/shared.py",
    "core/summarisation/postchecks/leakage.py",
    "core/summarisation/postchecks/garble.py",
    "core/summarisation/postchecks/attribution.py",
    "core/summarisation/postchecks/coherence.py",
    "core/summarisation/postchecks/orchestrator.py",
    # V0.18 (Phase 5.3): the preprocessor split siblings (verbatim moves from
    # text_preprocessor_impl.py) join the no-book-jargon scan.
    "core/summarisation/text_preprocessor_concepts.py",
    "core/summarisation/text_preprocessor_structure.py",
]
_BOOK_PHRASES = (
    "focus base",
    "hourglass conversation",
    "identity theme",
    "warm introduction",
)


def _src(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


def _write_text_call_sites(rel: str) -> list[int]:
    """Line numbers of every real ``.write_text(`` CALL in the file.

    AST-based (the tests/test_v1820411_p2_tls_logs_literals.py scanner
    pattern) so comments/strings can't produce false positives.
    """
    tree = ast.parse(_src(rel))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]


def _atomic_call_sites(rel: str) -> list[int]:
    """Line numbers of every atomic_write_text(...) call in the file."""
    tree = ast.parse(_src(rel))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "atomic_write_text"
    ]


# ════════════════════════════════════════════════════════════════════════════
# FIX 1 (a) — source scan: zero plain write_text left in the owned files
# ════════════════════════════════════════════════════════════════════════════


class TestAtomicSourceScan:
    def test_zero_write_text_calls_in_owned_files(self):
        """No ``X.write_text(...)`` call may remain in the 15 owned output
        files — a plain write is exactly what T-c3 removes (a crash mid-write
        leaves a truncated file)."""
        for rel in _OWNED_FILES:
            sites = _write_text_call_sites(rel)
            assert not sites, (
                f"{rel}:{sites} still uses plain Path.write_text — "
                "route it through utils.atomic_io.atomic_write_text "
                "(V18.20.4.12 T-c3)"
            )

    def test_atomic_call_site_counts_pinned(self):
        """Mechanical regression pin: each owned file routes the expected
        number of writes through atomic_write_text (guards both silent
        regressions to write_text AND accidental loss of pre-existing
        atomic sites)."""
        for rel, expected in _EXPECTED_ATOMIC_CALLS.items():
            sites = _atomic_call_sites(rel)
            assert len(sites) == expected, (
                f"{rel}: expected {expected} atomic_write_text call(s), "
                f"found {len(sites)} at lines {sites}"
            )

    def test_atomic_import_wired_in_swapped_files(self):
        """The 13 swapped files import atomic_write_text at MODULE level
        (house style — core/outputs/packets/generator.py:25);
        output_save.py reuses its pre-existing function-local import."""
        module_level_files = [
            rel
            for rel in _OWNED_FILES
            if rel
            not in (
                "core/pipeline/conversion/output_save.py",
                "core/outputs/evidence_map.py",  # no new atomic site (fallback kept)
            )
        ]
        assert len(module_level_files) == 13
        for rel in module_level_files:
            tree = ast.parse(_src(rel))
            wired = any(
                isinstance(node, ast.ImportFrom)
                and node.module == "utils.atomic_io"
                and any(alias.name == "atomic_write_text" for alias in node.names)
                for node in tree.body
            )
            assert wired, f"{rel} lacks the module-level utils.atomic_io import"

    def test_evidence_map_fallback_is_deliberate_and_documented(self):
        """evidence_map.py's ONE remaining direct write is the documented
        last-resort fallback inside _write_guidance_html: it runs only AFTER
        atomic_write_text raised, so it must NOT repeat the temp+replace
        failure mode (V10.4.0 Phase 6A-4 rationale preserved)."""
        src = _src("core/outputs/evidence_map.py")
        # atomic-first, then the direct fallback
        assert "atomic_write_text(html_path, html)" in src
        assert 'html_path.open("w", encoding="utf-8")' in src
        assert src.count('.open("w"') == 1, (
            "evidence_map.py must carry exactly ONE direct write (the "
            "documented fallback) — new writes go through atomic_write_text"
        )
        # the intent is marked in-source
        assert "DELIBERATELY non-atomic" in src
        # the V10.4.0 diagnostic-logging rationale survives
        assert "Atomic write failed" in src

    def test_output_save_segment_writes_are_atomic(self):
        """output_save.py: the per-segment loop writes atomically, and the
        pre-existing V18.20.2.0 (A30) full-markdown atomic write stays."""
        src = _src("core/pipeline/conversion/output_save.py")
        assert 'atomic_write_text(seg_file, seg_text, encoding="utf-8")' in src
        assert "seg_file.write_text(" not in src
        assert "atomic_write_text(converter.full_markdown_path, full_markdown)" in src


# ════════════════════════════════════════════════════════════════════════════
# FIX 1 (b) — functional atomicity proof at a REAL swapped call site
# ════════════════════════════════════════════════════════════════════════════


def _one_summary() -> list:
    from core.models import SummaryResult

    return [
        SummaryResult(
            chapter_heading="Chapter 1: Test",
            executive_summary="Exec summary.",
            thorough_summary="Thorough summary.",
            bullet_points=["Bullet 1", "Bullet 2"],
            success=True,
        )
    ]


class TestAtomicFunctional:
    """Drives write_chapters_md (the simplest swapped generator — the same
    harness shape as tests/test_v13_modules.py::TestChaptersExport) and
    service_formatters.write_output (a pure module function)."""

    def test_chapters_md_write_atomic_no_tmp_litter(self, tmp_path):
        from core.outputs.chapters_export import write_chapters_md

        out_path = tmp_path / "nested" / "Book.Chapters.md"
        result = write_chapters_md(_one_summary(), "Book", out_path)

        assert result == out_path
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Book" in content and "Bullet 1" in content
        # atomic_write_text created the parent dir (old explicit mkdir kept
        # its contract) and left no temp file behind
        tmps = [p for p in tmp_path.rglob("*") if p.suffix == ".tmp"]
        assert tmps == [], f"temp litter: {tmps}"

    def test_chapters_md_midwrite_failure_leaves_old_content(self, tmp_path, monkeypatch):
        """The atomicity property, proven at the swapped call site: when the
        final os.replace fails (disk-full / OS refusal) AFTER the temp file
        was fully written, the target keeps its OLD content — never a
        partial file — and the OSError propagates (write_text parity)."""
        import os

        from core.outputs.chapters_export import write_chapters_md

        out_path = tmp_path / "Book.Chapters.md"
        out_path.write_text("OLD CONTENT", encoding="utf-8")

        def _boom(src, dst):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(os, "replace", _boom)
        with pytest.raises(OSError, match="No space left"):
            write_chapters_md(_one_summary(), "Book", out_path)
        # the interrupted write left the OLD file completely intact…
        assert out_path.read_text(encoding="utf-8") == "OLD CONTENT"
        # …and cleaned up its temp file
        tmps = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert tmps == [], f"temp litter after failed write: {tmps}"

    def test_write_output_md_atomic_and_creates_parents(self, tmp_path):
        """Second swapped site driven functionally: the service-formatters
        .md path writes atomically (incl. the parent-dir contract)."""
        from core.outputs.service_formatters import write_output

        out_path = tmp_path / "deep" / "nested" / "out.md"
        ok, msg = write_output("hello **world**", out_path, fmt=".md")

        assert ok is True and "out.md" in msg
        assert out_path.read_text(encoding="utf-8") == "hello **world**"
        tmps = [p for p in tmp_path.rglob("*") if p.suffix == ".tmp"]
        assert tmps == [], f"temp litter: {tmps}"


# ════════════════════════════════════════════════════════════════════════════
# FIX 1 (c) — import sanity: all touched files still compile + import clean
# ════════════════════════════════════════════════════════════════════════════


class TestImportSanity:
    def test_all_touched_files_py_compile(self):
        touched = _OWNED_FILES + [
            "core/summarisation/text_preprocessor_impl.py",
        ]
        assert len(touched) == 16
        for rel in touched:
            py_compile.compile(str(_project_root / rel), doraise=True)  # no exception = clean

    def test_all_touched_modules_import_clean(self):
        """Every touched module imports headless (markitdown stubbed above —
        the only optional dep in these import chains)."""
        mods = [
            "core.outputs.podcast_generator",
            "core.outputs.podcast_audio",
            "core.outputs.service_formatters",
            "core.outputs.study_guide",
            "core.outputs.citation_graph",
            "core.outputs.evidence_map",
            "core.outputs.mind_map",
            "core.outputs.packets_extensions",
            "core.outputs.new_outputs",
            "core.outputs.reference_outputs",
            "core.outputs.quote_bank",
            "core.outputs.chapters_export",
            "core.outputs.social_media",
            "core.outputs.obsidian_kb",
            "core.pipeline.conversion.output_save",
            "core.summarisation.text_preprocessor_impl",
            "core.summarisation.postcheck_detectors",
        ]
        for name in mods:
            assert importlib.import_module(name) is not None


# ════════════════════════════════════════════════════════════════════════════
# FIX 2 (W-a14 residual) — comment de-jargon in the preprocessor
# ════════════════════════════════════════════════════════════════════════════


class TestCommentDeJargon:
    def test_no_book_derived_phrases_in_comment_files(self):
        """The book's jargon must appear NOWHERE in
        text_preprocessor_impl.py / postcheck_detectors.py — comments and
        docstrings included, zero allowlist (they were the copy-paste leak
        source for the runtime deny-list rule)."""
        for rel in _COMMENT_FILES:
            src = _src(rel)
            for phrase in _BOOK_PHRASES:
                assert phrase not in src, (
                    f"{rel} still quotes the book's jargon {phrase!r} "
                    "(comments/docstrings count — describe the pattern "
                    "generically instead)"
                )

    def test_preprocessor_comments_describe_the_pattern_generically(self):
        """The rewritten comments keep the technical content (what the
        regexes match and why) without the book's vocabulary."""
        # V0.18 (Phase 5.3): the de-jargoned comments + the n-gram extractor
        # moved VERBATIM to text_preprocessor_concepts.py — the pins follow
        # the code (Phase 5.2 re-pointing discipline).
        src = _src("core/summarisation/text_preprocessor_concepts.py")
        # the V3.2.1 version-history line survives
        assert "# V3.2.1:" in src
        # the generic pattern description is in place…
        assert "single-quoted lowercase multi-word jargon" in src
        assert "Capitalized multi-word concept names" in src
        assert "book-specific jargon phrases" in src

    def test_comment_changes_are_comment_only(self):
        """ZERO runtime change: the two preprocessor regexes and the ngram
        extractor's shape are untouched (behavior pinned by the existing
        preprocessor regression files)."""
        src = _src("core/summarisation/text_preprocessor_concepts.py")
        assert "_QUOTED_TERM_PATTERN = re.compile(" in src
        assert (
            "r'[\"\\u201c\\u2018]([a-zA-Z][a-zA-Z]+(?:\\s+[a-zA-Z]+){0,3})"
            "[\"\\u201d\\u2019]'" in src
        )
        assert "def extract_ngram_keywords(text: str, n: int = 18) -> list[str]:" in src


if __name__ == "__main__":  # pragma: no cover — manual run convenience
    sys.exit(pytest.main([__file__, "-v"]))
