"""
Layout Analyzer – uses LayoutParser to detect text blocks and improve reading order.
This is a placeholder; full integration requires more work.
We'll provide a simple detection for multi‑column layouts and adjust paragraph order.
"""

from collections.abc import Callable
from pathlib import Path

from utils.logging import get_main_logger

logger = get_main_logger()


class LayoutAnalyzer:
    def __init__(
        self,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._layoutparser = None

    def _init_layoutparser(self) -> bool:
        try:
            import layoutparser as lp
            self._layoutparser = lp
            self.log("  ✅ LayoutParser loaded.", "INFO")
            return True
        except ImportError:
            self.log("  ⚠️ LayoutParser not installed. Run: pip install layoutparser", "WARNING")
            return False

    def analyze_layout(self, pdf_path: Path, pages: list[int]) -> dict[int, list[dict]]:
        """
        Analyze layout for specified pages.
        Returns dict: page_num -> list of block dicts with 'type' and 'text'.
        """
        if not self._init_layoutparser():
            return {}
        try:
            import layoutparser as lp
            import pdf2image
            # We'll use a simple Detectron2 model (needs installation)
            # For now, we'll just detect text regions.
            model = lp.models.Detectron2LayoutModel(
                'lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config',
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
            )
            results = {}
            images = pdf2image.convert_from_path(str(pdf_path), first_page=pages[0], last_page=pages[-1])
            for idx, img in enumerate(images):
                page_num = pages[idx]
                layout = model.detect(img)
                blocks = []
                for block in layout:
                    if block.type in ['Text', 'Title', 'List']:
                        # Extract text from this region (we need OCR)
                        # This is complex; we'll just record coordinates and type.
                        blocks.append({
                            'type': block.type,
                            'x1': block.x_1, 'y1': block.y_1,
                            'x2': block.x_2, 'y2': block.y_2,
                        })
                results[page_num] = blocks
                self.log(f"  📐 Layout analyzed page {page_num}: found {len(blocks)} text blocks", "DEBUG")
            return results
        except Exception as e:
            self.log(f"  ❌ Layout analysis failed: {e}", "WARNING")
            return {}

    def reorder_markdown_by_layout(self, markdown: str, layout_info: dict[int, list[dict]]) -> str:
        """
        Reorder markdown paragraphs based on layout analysis (e.g., multi‑column).
        For now, we'll just log and return unchanged.
        """
        if not layout_info:
            return markdown
        # This would require mapping paragraphs to coordinates, which is complex.
        # We'll just log that layout analysis was done.
        self.log("  ℹ️ Layout analysis completed – reordering not yet implemented.", "INFO")
        return markdown
