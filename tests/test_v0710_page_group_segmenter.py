"""V0.7.1 (wizard rework ③, item 3c / D5) — the page-group block chunker.

``page_group_size`` becomes the block size of a page-group chunking
fallback in the AUTO cascade: when TOC/heading/semantic segmentation all
fail, pages chunk into N-page blocks (paragraph boundaries respected)
instead of raw fixed-token chunks. ``chunk_by_page_groups`` gets its
FIRST real reader (audit §W4 logged both as vestigial, zero consumers).

Semantics (this version): ``page_group_size == 0`` → AUTO (N computed
from the measured page token density, target ≈ 5,000 tokens/block —
the plan's 4-6k band midpoint — clamped 4-25 pages); a positive int →
manual override. ``chunk_by_page_groups=False`` disables the fallback
entirely (cascade falls to the token chunker).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.models import ConversionRequest
from core.segmentation.page_group_segmenter import (
    PAGE_GROUP_FALLBACK_SIZE,
    PAGE_GROUP_MAX_PAGES,
    PAGE_GROUP_MIN_PAGES,
    PageGroupSegmenter,
    compute_auto_page_group_size,
    resolve_page_group_size,
)

_SEGMENTER = _project_root / "core" / "segmentation" / "segmenter.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _synthetic_doc(pages: int, words_per_page: int = 40) -> tuple[str, list[tuple[int, int]]]:
    """A marker-ful markdown doc: ``<!-- original page N -->`` headers,
    ``\\n\\n``-joined pages (exactly what OCRService.build_markdown
    produces), neutral filler text (no headings, no chapter words)."""
    parts = []
    for p in range(1, pages + 1):
        body = " ".join(f"filler{p}{i}" for i in range(words_per_page))
        parts.append(f"<!-- original page {p} -->\n{body}")
    text = "\n\n".join(parts)
    markers = []
    for p in range(1, pages + 1):
        idx = text.index(f"<!-- original page {p} -->")
        markers.append((p, idx))
    return text, markers


# ═══════════════════════════════════════════════════════════════════════════
# AUTO density math (pure functions)
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoDensity:
    def test_typical_density_gives_midband_blocks(self):
        # ~625 tokens/page → 5000/625 = 8 pages per block.
        assert compute_auto_page_group_size([625] * 20) == 8

    def test_dense_pages_clamp_to_min(self):
        # ~1250 tokens/page → 4 (exact); even denser → floor clamp.
        assert compute_auto_page_group_size([1250] * 20) == 4
        assert compute_auto_page_group_size([2500] * 20) == 4

    def test_sparse_pages_clamp_to_max(self):
        assert compute_auto_page_group_size([200] * 20) == 25
        assert compute_auto_page_group_size([100] * 20) == 25

    def test_no_data_falls_back_to_historical_default(self):
        assert compute_auto_page_group_size([]) == PAGE_GROUP_FALLBACK_SIZE == 10
        assert compute_auto_page_group_size([0, 0, 0]) == 10

    def test_result_always_within_bounds(self):
        for density in (1, 50, 150, 200, 625, 1250, 5000, 50000):
            n = compute_auto_page_group_size([density] * 30)
            assert PAGE_GROUP_MIN_PAGES <= n <= PAGE_GROUP_MAX_PAGES, (
                f"density {density} → {n} outside 4-25"
            )

    def test_manual_override_wins_in_resolve(self):
        req = SimpleNamespace(page_group_size=12)
        assert resolve_page_group_size(req, [625] * 20) == 12

    def test_zero_and_negative_mean_auto(self):
        for bad in (0, -3, None):
            req = SimpleNamespace(page_group_size=bad)
            assert resolve_page_group_size(req, [625] * 20) == 8


# ═══════════════════════════════════════════════════════════════════════════
# Block construction (sizing, boundaries, headings)
# ═══════════════════════════════════════════════════════════════════════════


class TestPageGroupBlocks:
    def _request(self, page_group_size: int = 0, chunk_by_page_groups: bool = True):
        return ConversionRequest(
            input_path=Path("book.pdf"),
            output_dir=Path("out"),
            page_group_size=page_group_size,
            chunk_by_page_groups=chunk_by_page_groups,
        )

    def test_manual_n_splits_into_n_page_blocks(self):
        text, markers = _synthetic_doc(pages=10)
        seg = PageGroupSegmenter(self._request(page_group_size=3), lambda m, l: None)
        blocks = seg.segment(text, 10, markers)
        assert [b.heading for b in blocks] == [
            "Pages 1-3",
            "Pages 4-6",
            "Pages 7-9",
            "Pages 10-10",
        ]
        assert all(b.segment_type == "chunk" for b in blocks)
        for b in blocks:
            assert b.content.strip()
            assert b.start_page <= b.end_page

    def test_block_contents_partition_the_document(self):
        text, markers = _synthetic_doc(pages=9)
        seg = PageGroupSegmenter(self._request(page_group_size=4), lambda m, l: None)
        blocks = seg.segment(text, 9, markers)
        assert len(blocks) == 3
        # No page marker lost, none duplicated: every marker appears in
        # exactly one block's content.
        for p in range(1, 10):
            owners = [b for b in blocks if f"<!-- original page {p} -->" in b.content]
            assert len(owners) == 1, f"page {p} owned by {len(owners)} blocks"

    def test_boundary_respects_paragraph_breaks(self):
        # Pages joined by "\n\n" (the build_markdown format): the cut
        # lands on the blank line BEFORE the next page's marker — no
        # line is ever split, no marker leaks into the wrong block.
        text, markers = _synthetic_doc(pages=6, words_per_page=40)
        seg = PageGroupSegmenter(self._request(page_group_size=3), lambda m, l: None)
        blocks = seg.segment(text, 6, markers)
        first = blocks[0].content
        # Block 1 covers pages 1-3 and ends with page 3's filler text —
        # NOT with the next page's marker or a stray blank line.
        assert "<!-- original page 4 -->" not in first
        assert "<!-- original page 1 -->" in first
        assert "<!-- original page 3 -->" in first
        assert not first.endswith("\n\n") and not first.endswith("\n")
        # Page 3's body is 40 words "filler3" + i; the last is filler339.
        assert first.rstrip().endswith("filler339")

    def test_no_blank_line_falls_back_to_raw_page_boundary(self):
        # A pathological doc where pages are joined with single "\n":
        # no "\n\n" inside the block → the cut is the next marker itself.
        parts = []
        for p in range(1, 7):
            parts.append(f"<!-- original page {p} -->\nbody text page {p} paragraph one.")
        text = "\n".join(parts)
        markers = []
        for p in range(1, 7):
            markers.append((p, text.index(f"<!-- original page {p} -->")))
        seg = PageGroupSegmenter(self._request(page_group_size=2), lambda m, l: None)
        blocks = seg.segment(text, 6, markers)
        assert len(blocks) == 3
        assert blocks[1].content.startswith("<!-- original page 3 -->")
        assert "page 3 paragraph one." in blocks[1].content

    def test_auto_zero_resolves_from_measured_density(self):
        # 40 filler words/page ≈ 60-90 tokens/page → AUTO clamps to 25.
        text, markers = _synthetic_doc(pages=30, words_per_page=40)
        logs: list = []
        seg = PageGroupSegmenter(
            self._request(page_group_size=0), lambda m, l="INFO": logs.append(m)
        )
        blocks = seg.segment(text, 30, markers)
        # 30 pages / 25-per-block → 2 blocks (25 + 5).
        assert len(blocks) == 2
        assert blocks[0].heading == "Pages 1-25"
        assert blocks[1].heading == "Pages 26-30"
        assert any("AUTO" in m for m in logs)

    def test_empty_markers_return_empty_for_fallthrough(self):
        seg = PageGroupSegmenter(self._request(), lambda m, l: None)
        assert seg.segment("some text", 5, []) == []

    def test_blank_block_is_skipped(self):
        # Pages whose bodies are all blank still yield markers; a block
        # that ends up empty contributes no segment.
        parts = []
        for p in range(1, 7):
            body = "" if p <= 3 else "real body text"
            parts.append(f"<!-- original page {p} -->\n{body}")
        text = "\n\n".join(parts)
        markers = [(p, text.index(f"<!-- original page {p} -->")) for p in range(1, 7)]
        seg = PageGroupSegmenter(self._request(page_group_size=3), lambda m, l: None)
        blocks = seg.segment(text, 6, markers)
        # Block 1 (pages 1-3) is entirely blank → only block 2 survives.
        assert [b.heading for b in blocks] == ["Pages 4-6"]


# ═══════════════════════════════════════════════════════════════════════════
# Cascade pin — page-groups sit between semantic and the token chunker
# ═══════════════════════════════════════════════════════════════════════════


class TestCascadePin:
    def _segmenter_logs(self, request: ConversionRequest):
        from core.segmentation.segmenter import Segmenter

        logs: list = []

        def log(msg, level="INFO"):
            logs.append(msg)

        return Segmenter(request, log_callback=log, toc_entries=None), logs

    def _flat_request(self, **kw):
        # AUTO strategy, no TOC, no headings, semantic OFF → the page-group
        # stage is the first one that can fire on marker-ful text.
        return ConversionRequest(
            input_path=Path("book.pdf"),
            output_dir=Path("out"),
            segment_strategy="auto",
            enable_semantic_segmentation=False,
            **kw,
        )

    def test_page_groups_used_before_token_fallback(self):
        text, markers = _synthetic_doc(pages=12, words_per_page=60)
        request = self._flat_request(page_group_size=3, chunk_by_page_groups=True)
        segmenter, logs = self._segmenter_logs(request)
        segments = segmenter.segment(text, 12, markers)
        assert [s.heading for s in segments][:3] == ["Pages 1-3", "Pages 4-6", "Pages 7-9"]
        assert any("Page-groups produced" in m for m in logs)
        # …and the token chunker never ran.
        assert not any("token-based" in m for m in logs)

    def test_disabled_flag_falls_through_to_tokens(self):
        text, markers = _synthetic_doc(pages=12, words_per_page=60)
        request = self._flat_request(page_group_size=3, chunk_by_page_groups=False)
        segmenter, logs = self._segmenter_logs(request)
        segments = segmenter.segment(text, 12, markers)
        assert any("Falling back to token-based" in m for m in logs)
        assert all(not s.heading.startswith("Pages ") for s in segments)

    def test_cascade_source_pin(self):
        """The AUTO cascade names page-groups before tokens."""
        src = _src(_SEGMENTER)
        assert "from core.segmentation.page_group_segmenter import PageGroupSegmenter" in src
        assert "self.page_group_segmenter = PageGroupSegmenter(request, log_callback)" in src
        assert "if self.request.chunk_by_page_groups:" in src
        # …and the stage sits between semantic and the token fallback.
        semantic_idx = src.index("# 4. Semantic (LLM-based)")
        pagegroup_idx = src.index("if self.request.chunk_by_page_groups:")
        token_idx = src.index("# 5. Token-based (fallback)")
        assert semantic_idx < pagegroup_idx < token_idx


# ═══════════════════════════════════════════════════════════════════════════
# Round-trip pin — page_group_size 0/auto and manual both reach the request
# ═══════════════════════════════════════════════════════════════════════════


class TestPageGroupRoundTrip:
    def test_request_field_default_is_zero_auto(self):
        fields = {f.name: f for f in dataclasses.fields(ConversionRequest)}
        assert fields["page_group_size"].default == 0, "0 = AUTO is the D5 default on the request"

    def test_map_row_default_is_zero(self):
        src = _src(_project_root / "controller.py")
        assert (
            '("page_group_size", "page_group_size", "segmentation.page_group_size", 0, None)' in src
        )

    def test_settings_default_is_zero(self):
        src = _src(_project_root / "utils" / "settings.py")
        assert '"page_group_size": 0,' in src

    def test_state_to_request_round_trip(self, monkeypatch):
        """WizardState.page_group_size (0 and manual) → to_ui_data →
        _REQUEST_FIELD_MAP → ConversionRequest (the dead-control lesson)."""
        pytest.importorskip("controller")
        import controller as controller_mod

        class _FakeSettings:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, path, default=None):
                return self._data.get(path, default)

            def set(self, path, value):
                self._data[path] = value

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        from ui_qt.views.wizard_steps.shared import WizardState

        for value, expected in ((0, 0), (8, 8), (25, 25)):
            state = WizardState()
            state.page_group_size = value
            state.input_path = "book.pdf"
            ui_data = state.to_ui_data()
            assert ui_data["page_group_size"] == value
            request = controller_mod.Controller().build_request_from_ui(ui_data)
            assert request.page_group_size == expected, f"{value} must round-trip to the request"

    def test_chunk_by_page_groups_flows_from_settings(self, monkeypatch):
        """The wizard carries no chunk toggle — the flag flows from the
        settings default via the map's setting path (True)."""
        pytest.importorskip("controller")
        import controller as controller_mod

        class _FakeSettings:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, path, default=None):
                return self._data.get(path, default)

            def set(self, path, value):
                self._data[path] = value

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        from ui_qt.views.wizard_steps.shared import WizardState

        state = WizardState()
        state.input_path = "book.pdf"
        request = controller_mod.Controller().build_request_from_ui(state.to_ui_data())
        assert request.chunk_by_page_groups is True
