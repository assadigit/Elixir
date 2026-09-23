"""V0.4.19 — page-ref injector tests (the V0.4.16 feature that never fired).

Background: the V0.4.16 page-citation prompts tell the model "The source
text has YAML frontmatter with start_page and end_page", and
``inject_page_refs`` (postchecks/garble.py) regex-matches that frontmatter
as its deterministic fallback when the model ignores the instruction.
But ``summarize_chapters`` passed the RAW segment content — the frontmatter
never existed in the summarizer input, so the prompt's claim was FALSE and
the injector could never fire in production (coded but never appearing in
outputs — the V0.4.19 audit finding).

Tests for:
1. ``inject_page_refs`` — the detector itself (never tested since V0.4.16):
   injects into KD/TT bullets lacking refs, respects existing refs,
   estimates pages from the frontmatter range, and no-ops gracefully.
2. ``_chapter_text_with_page_frontmatter`` — the V0.4.19 production wiring
   in book_outer.py: prepends the frontmatter from the chapter dict's
   start_page/end_page (threaded from the Segment model).
3. The full ``summarize_chapters`` path passes frontmatter-wrapped content
   into ``_summarize_inner``.

Run: pytest tests/test_page_ref_injector.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.book_outer import _chapter_text_with_page_frontmatter
from core.summarisation.postchecks.garble import inject_page_refs

# ════════════════════════════════════════════════════════════════════════════
# 1. inject_page_refs — the detector
# ════════════════════════════════════════════════════════════════════════════

_SOURCE_WITH_FM = (
    "---\nstart_page: 48\nend_page: 58\n---\n\n"
    "Chapter body text. First concept here. Second concept follows. "
    "A third concept appears near the middle of the chapter. "
    "The final concept closes the chapter near the end."
)


class TestInjectPageRefs:
    def test_injects_into_bullets_lacking_refs(self):
        text = (
            "- First distinction between two related concepts\n"
            "- Second distinction drawn by the author\n"
            "- Third distinction with different scope"
        )
        out, issues = inject_page_refs(text, "key_distinctions", _SOURCE_WITH_FM)
        # every bullet now carries a (p. N) ref
        for line in out.split("\n"):
            assert "(p. " in line, f"missing page ref in: {line!r}"
        # pages estimated across the 48–58 range: with 3 bullets the
        # position ratios are 0/3, 1/3, 2/3 → 48, 51, 54 (the injector's
        # (idx/total) math never reaches the end page for the last bullet)
        assert "(p. ~48)" in out  # V0.4.23: estimates carry the ~ mark
        assert "(p. ~51)" in out
        assert "(p. ~54)" in out
        # one issue recorded (severity=fix, detector=page_ref_injector)
        assert len(issues) == 1
        assert issues[0].detector == "page_ref_injector"
        assert issues[0].severity == "fix"
        assert "3 bullet" in issues[0].detail or "3 bullet(s)" in issues[0].detail

    def test_respects_bullets_that_already_have_refs(self):
        text = "- First distinction (p. 50)\n- Second distinction drawn by the author\n"
        out, issues = inject_page_refs(text, "theoretical_tensions", _SOURCE_WITH_FM)
        # the first line is untouched
        assert "- First distinction (p. 50)\n" in out
        # only the second gained a ref
        assert "(p. 50)" in out.split("\n")[0]
        assert out.count("(p.") == 2

    def test_no_page_info_no_op(self):
        text = "- A distinction without page info available"
        out, issues = inject_page_refs(text, "key_distinctions", "plain source, no frontmatter")
        assert out == text
        assert issues == []

    def test_empty_inputs_no_op(self):
        for text, src in (("", _SOURCE_WITH_FM), ("- bullet", ""), (None or "", "")):
            out, issues = inject_page_refs(text, "key_distinctions", src)
            assert out == (text or "")
            assert issues == []

    def test_non_bullet_text_no_op(self):
        text = "Flowing prose paragraph with no bullet list."
        out, issues = inject_page_refs(text, "key_distinctions", _SOURCE_WITH_FM)
        assert out == text
        assert issues == []

    def test_zero_page_range_no_op(self):
        src = "---\nstart_page: 48\nend_page: 48\n---\n\nbody"
        text = "- A distinction"
        out, issues = inject_page_refs(text, "key_distinctions", src)
        assert out == text
        assert issues == []

    def test_never_raises_on_garbage(self):
        # the detector is fail-open by design (crash guard logs + returns)
        out, issues = inject_page_refs("- bullet", "kd", object())  # type: ignore[arg-type]
        assert issues == []


# ════════════════════════════════════════════════════════════════════════════
# 2. _chapter_text_with_page_frontmatter — the production wiring
# ════════════════════════════════════════════════════════════════════════════


class TestChapterTextWithPageFrontmatter:
    def test_prepends_frontmatter_when_pages_known(self):
        chap = {"heading": "Ch 1", "content": "Body text.", "start_page": 12, "end_page": 20}
        out = _chapter_text_with_page_frontmatter(chap)
        assert out.startswith("---\nstart_page: 12\nend_page: 20\n---\n\n")
        assert out.endswith("Body text.")

    def test_no_page_info_returns_content_unchanged(self):
        chap = {"heading": "Ch 1", "content": "Body text."}
        assert _chapter_text_with_page_frontmatter(chap) == "Body text."

    def test_none_pages_return_content_unchanged(self):
        chap = {"heading": "Ch 1", "content": "Body text.", "start_page": None, "end_page": None}
        assert _chapter_text_with_page_frontmatter(chap) == "Body text."

    def test_existing_frontmatter_left_alone(self):
        content = "---\nstart_page: 1\nend_page: 2\n---\n\nBody."
        chap = {"heading": "Ch 1", "content": content, "start_page": 9, "end_page": 10}
        assert _chapter_text_with_page_frontmatter(chap) == content

    def test_garbage_page_values_never_raise(self):
        chap = {"heading": "Ch 1", "content": "Body.", "start_page": "abc", "end_page": object()}
        out = _chapter_text_with_page_frontmatter(chap)
        assert out == "Body."

    def test_string_numeric_pages_coerced(self):
        chap = {"heading": "Ch 1", "content": "Body.", "start_page": "7", "end_page": "9"}
        out = _chapter_text_with_page_frontmatter(chap)
        assert out.startswith("---\nstart_page: 7\nend_page: 9\n---")


# ════════════════════════════════════════════════════════════════════════════
# 3. End-to-end wiring: summarize_chapters → _summarize_inner sees frontmatter
# ════════════════════════════════════════════════════════════════════════════


class TestSummarizeChaptersFrontmatterWiring:
    def test_sequential_path_passes_frontmatter(self, tmp_path, monkeypatch):
        """The V0.4.19 regression pin: summarize_chapters (sequential mode,
        the default on the target rig) must pass frontmatter-wrapped content
        to _summarize_inner when the chapter dict carries page info —
        otherwise the page-citation prompts lie and the injector can't
        fire."""
        from core.summarisation.book_outer import SummarizerBookMixin

        seen: dict[str, str] = {}

        class _Fake(SummarizerBookMixin):
            def __init__(self):
                self.log = lambda msg, level="INFO": None
                self.max_workers = 1
                self._chapter_deadline_start = None
                # deadline-check attrs (book_outer.py:230 reads these)
                self.is_local = True
                self.local_chapter_deadline = 0

            def _summarize_inner(self, heading, text, concepts=None, callouts=None, **kw):
                seen["text"] = text
                from core.models import SummaryResult

                return SummaryResult(
                    chapter_heading=heading,
                    executive_summary="exec",
                    bullet_points=["b1"],
                    thorough_summary="thorough",
                )

        chapters = [
            {
                "heading": "Chapter One",
                "content": "The chapter body.",
                "start_page": 33,
                "end_page": 41,
            }
        ]
        _Fake().summarize_chapters(chapters)
        assert seen["text"].startswith("---\nstart_page: 33\nend_page: 41\n---\n\n")
        assert "The chapter body." in seen["text"]
