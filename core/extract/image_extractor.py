"""V11.72.0: Image extractor — extract all visuals from PDF/EPUB/DOCX.

Extracts:
- Embedded images (photos, graphics stored as-is in the PDF)
- Rendered page regions (vector graphics, charts, tables drawn with lines/text)
- Full page renders (raw page as JPEG — for reference)
- Cropped image regions (detects image areas and crops out surrounding text)

Classification by heuristics:
- photo: portrait or landscape, high color variance
- chart: wide aspect ratio, moderate text density
- table: grid-like structure, high text density
- diagram: line art, low color count
- figure: generic fallback

Output structure:
  output_folder/
    photos/      — page_005_img_003.jpg
    charts/      — page_012_img_001.jpg
    tables/      — page_008_img_002.jpg
    diagrams/    — page_015_img_001.jpg
    figures/     — page_020_img_001.jpg
    full_pages/  — page_005.jpg (raw full page render)
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Classification categories
CATEGORIES = ["photos", "charts", "tables", "diagrams", "figures"]


def extract_images_from_pdf(
    pdf_path: str,
    output_folder: str,
    page_range: tuple[int, int] | None = None,
    extract_full_pages: bool = True,
    extract_cropped: bool = True,
    dpi: int = 150,
    log_callback=None,
    progress_callback=None,
) -> dict:
    """Extract all images from a PDF.

    V11.74.0: complete rewrite to fix:
    - Duplication (each image extracted ONCE, not twice)
    - Text-only pages in full_pages (now properly skipped)
    - Speed (skip pages with no images early, lower default DPI)

    Args:
        pdf_path: Path to the PDF file.
        output_folder: Where to save extracted images.
        page_range: (start, end) 1-indexed, or None for all pages.
        extract_full_pages: If True, render pages with images as JPEG.
        extract_cropped: If True, crop image regions from page render.
        dpi: Resolution for page rendering (150 default = faster).
        log_callback: Optional callable(msg, level).
        progress_callback: Optional callable(pct, msg).

    Returns:
        Dict with counts per category + total.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    import fitz  # PyMuPDF
    from PIL import Image

    pdf_path = str(pdf_path)
    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)

    # Create category subfolders
    for cat in CATEGORIES:
        (output / cat).mkdir(exist_ok=True)
    if extract_full_pages:
        (output / "full_pages").mkdir(exist_ok=True)

    counts = dict.fromkeys(CATEGORIES, 0)
    counts["full_pages"] = 0
    counts["total"] = 0

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log(f"  ❌ Cannot open PDF: {e}", "ERROR")
        return counts

    total_pages = len(doc)
    start_page = (page_range[0] - 1) if page_range else 0
    end_page = page_range[1] if page_range else total_pages
    start_page = max(0, start_page)
    end_page = min(end_page, total_pages)

    log(f"  📖 Processing pages {start_page+1}-{end_page} of {total_pages}...", "INFO")

    # V11.74.0: track ALL extracted xrefs globally to prevent duplicates
    # across the entire document (same image reused on multiple pages)
    global_extracted_xrefs = set()

    pages_with_images = 0
    pages_skipped = 0

    for page_num in range(start_page, end_page):
        page_idx = page_num + 1  # 1-indexed for filenames
        pct = int((page_num - start_page) / max(end_page - start_page, 1) * 100)
        progress(pct, f"📄 Page {page_idx}/{end_page}")

        page = doc[page_num]

        # ── STEP 1: Quick check — does this page have ANY images? ───
        # V11.74.0: skip pages with no images entirely (speed boost)
        image_list = page.get_images(full=True)
        drawings = page.get_drawings() if extract_cropped else []

        # Filter to only meaningful images (skip tiny ones)
        meaningful_images = []
        for img_info in image_list:
            xref = img_info[0]
            if xref in global_extracted_xrefs:
                continue  # already extracted this exact image
            try:
                # Quick size check via the image info
                # img_info: [xref, smask, width, height, bpc, colorspace, ...]
                w = img_info[2] if len(img_info) > 2 else 0
                h = img_info[3] if len(img_info) > 3 else 0
                if w >= 50 and h >= 50:
                    meaningful_images.append(img_info)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                meaningful_images.append(img_info)  # check later

        # Check for meaningful vector drawings (not just text underlines)
        meaningful_drawings = []
        for draw in drawings:
            if "rect" in draw:
                r = draw["rect"]
                if r.width > 80 and r.height > 80:
                    meaningful_drawings.append(draw)

        if not meaningful_images and not meaningful_drawings:
            pages_skipped += 1
            continue  # SKIP — text-only page, no visuals

        pages_with_images += 1
        page_has_images = False

        # ── STEP 2: Extract embedded images (ONE TIME each) ─────────
        # V11.74.0: extract each unique image exactly ONCE.
        # No re-rendering of the same region — that was causing duplicates.
        for img_idx, img_info in enumerate(meaningful_images):
            xref = img_info[0]
            if xref in global_extracted_xrefs:
                continue  # already extracted

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                pil_img = Image.open(io.BytesIO(image_bytes))
                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")

                w, h = pil_img.size
                if w < 50 or h < 50:
                    continue

                global_extracted_xrefs.add(xref)
                page_has_images = True

                # V11.76.0: auto-trim whitespace from the image
                pil_img = _auto_trim_whitespace(pil_img)

                category = _classify_image(pil_img)

                filename = f"page_{page_idx:04d}_img_{img_idx+1:03d}.jpg"
                filepath = output / category / filename
                pil_img.save(str(filepath), "JPEG", quality=90)
                counts[category] += 1
                counts["total"] += 1
                log(f"  📷 {category}/{filename} ({pil_img.size[0]}x{pil_img.size[1]})", "DEBUG")

            except Exception as e:
                log(f"  ⚠️ Image {img_idx+1} on page {page_idx}: {e}", "WARNING")

        # ── STEP 3: Crop vector graphics regions (charts/tables) ─────
        # V11.74.0/V11.77.0: ONLY run vector crop if NO embedded images
        # were extracted from this page. If embedded images were found,
        # the page's visual content is already captured — running vector
        # crop would create DUPLICATES in different category folders.
        if extract_cropped and meaningful_drawings and not page_has_images:
            try:
                cropped = _crop_vector_regions(
                    page, page_idx, output, dpi, meaningful_drawings, log)
                for cat, count in cropped.items():
                    counts[cat] += count
                    counts["total"] += count
                    if count > 0:
                        page_has_images = True
            except Exception as e:
                log(f"  ⚠️ Vector crop failed on page {page_idx}: {e}", "WARNING")

        # ── STEP 3b: Smart-crop page (V11.75.0) ─────────────────────
        # Only if NO images were found by any previous step.
        # This is the last resort for pages PyMuPDF can't parse.
        if extract_cropped and not page_has_images and meaningful_drawings:
            try:
                smart_cropped = _smart_crop_page_v2(page, page_idx, output, dpi, log)
                for cat, count in smart_cropped.items():
                    counts[cat] += count
                    counts["total"] += count
                    if count > 0:
                        page_has_images = True
            except Exception as e:
                log(f"  ⚠️ Smart-crop failed on page {page_idx}: {e}", "WARNING")

        # ── STEP 4: Full page render (ONLY if page has images) ──────
        if extract_full_pages and page_has_images:
            try:
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("jpeg")
                filename = f"page_{page_idx:04d}.jpg"
                filepath = output / "full_pages" / filename
                Path(filepath).write_bytes(img_data)
                counts["full_pages"] += 1
                counts["total"] += 1
            except Exception as e:
                log(f"  ⚠️ Full page render failed on page {page_idx}: {e}", "WARNING")

    doc.close()
    progress(100, f"✅ Done! {counts['total']} images extracted")
    log(f"  ✅ Extraction complete: {counts['total']} total images", "INFO")
    log(f"     Photos: {counts['photos']}, Charts: {counts['charts']}, "
        f"Tables: {counts['tables']}, Diagrams: {counts['diagrams']}, "
        f"Figures: {counts['figures']}, Full pages: {counts['full_pages']}", "INFO")
    log(f"     Pages with images: {pages_with_images}, text-only pages skipped: {pages_skipped}", "INFO")
    return counts


def _auto_trim_whitespace(pil_img, threshold=10):
    """V11.76.0: Auto-trim white borders/margins from an image.

    Uses PIL's ImageChops.difference() + getbbox() to find the bounding
    box of non-white content, then crops to that box.

    Args:
        pil_img: PIL Image to trim.
        threshold: pixels within this distance of white are considered
                   "white" (0 = strict, 10 = tolerant of off-white).

    Returns:
        Cropped PIL Image (or original if no trimming needed).
    """
    from PIL import Image, ImageChops

    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # Create a white background of the same size
    bg = Image.new("RGB", pil_img.size, (255, 255, 255))

    # Compute the difference from white
    diff = ImageChops.difference(pil_img, bg)

    # Apply threshold: anything within `threshold` of white = white
    diff = diff.point(lambda x: 255 if x > threshold else 0)

    # Get the bounding box of non-zero (non-white) content
    bbox = diff.getbbox()

    if bbox is None:
        # Entire image is white — return as-is
        return pil_img

    # Add small padding (2px) so we don't cut off edges
    pad = 2
    bbox = (
        max(0, bbox[0] - pad),
        max(0, bbox[1] - pad),
        min(pil_img.size[0], bbox[2] + pad),
        min(pil_img.size[1], bbox[3] + pad),
    )

    # Only crop if it actually reduces the size significantly (>5%)
    orig_area = pil_img.size[0] * pil_img.size[1]
    crop_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    if crop_area < orig_area * 0.95:
        return pil_img.crop(bbox)

    return pil_img


def _smart_crop_page_v2(page, page_idx, output, dpi, log):
    """V11.76.0: Smart-crop using PIL getbbox + numpy gap detection.

    For pages with images that PyMuPDF doesn't detect as embedded:
    1. Render the full page at the specified DPI
    2. Use PIL ImageChops to find the content bounding box (trim whitespace)
    3. Use numpy to find row/column gaps → split into separate image regions
    4. For each region, check if it's an image (color variance) or text
    5. Save only image regions, auto-trimmed
    """
    import fitz
    import numpy as np
    from PIL import Image, ImageChops

    counts = dict.fromkeys(CATEGORIES, 0)

    # Render the full page
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")

    pil_img = Image.open(io.BytesIO(img_data))
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # Create a white background and compute difference
    bg = Image.new("RGB", pil_img.size, (255, 255, 255))
    diff = ImageChops.difference(pil_img, bg)
    diff_arr = np.array(diff)

    # Content mask: any pixel that differs from white by >10
    content_mask = diff_arr.max(axis=2) > 10

    # Find content rows (rows with any non-white content)
    row_has_content = content_mask.any(axis=1)
    content_rows = np.where(row_has_content)[0]

    if len(content_rows) == 0:
        return counts  # blank page

    # Find content blocks by detecting horizontal gaps (>20px = new block)
    blocks = []
    start = content_rows[0]
    prev = content_rows[0]
    for r in content_rows[1:]:
        if r - prev > 20:  # gap >20px = new block
            blocks.append((start, prev))
            start = r
        prev = r
    blocks.append((start, prev))

    # Process each block
    for block_idx, (row_start, row_end) in enumerate(blocks):
        block_height = row_end - row_start
        if block_height < 40:
            continue  # skip tiny blocks

        # Find content columns for this row range
        block_mask = content_mask[row_start:row_end + 1]
        col_has_content = block_mask.any(axis=0)
        content_cols = np.where(col_has_content)[0]

        if len(content_cols) == 0:
            continue

        # Split columns into sub-regions (for side-by-side images)
        col_blocks = []
        c_start = content_cols[0]
        c_prev = content_cols[0]
        for c in content_cols[1:]:
            if c - c_prev > 20:  # column gap
                col_blocks.append((c_start, c_prev))
                c_start = c
            c_prev = c
        col_blocks.append((c_start, c_prev))

        for col_start, col_end in col_blocks:
            block_width = col_end - col_start
            if block_width < 50 or block_height < 50:
                continue

            # Extract this region
            region = pil_img.crop((col_start, row_start, col_end + 1, row_end + 1))
            region_arr = np.array(region)

            # Check if it's an image (not text):
            # - High color variance (>25) = image
            # - Many unique colors (>80) = image
            color_std = float(region_arr.std())
            # Downsample for unique color count (faster)
            small_region = region.resize((30, 30)).convert("RGB")
            small_arr = np.array(small_region)
            unique_colors = len(np.unique(small_arr.reshape(-1, 3), axis=0))

            is_image = color_std > 25 or unique_colors > 80

            if not is_image:
                continue  # skip text blocks

            # Auto-trim whitespace from this region
            region = _auto_trim_whitespace(region)

            # Skip if too small after trimming
            if region.size[0] < 50 or region.size[1] < 50:
                continue

            # Classify and save
            category = _classify_image(region)
            filename = f"page_{page_idx:04d}_smart_{block_idx + 1:03d}.jpg"
            filepath = output / category / filename
            region.save(str(filepath), "JPEG", quality=90)
            counts[category] += 1
            log(f"  🎯 Smart-cropped: {category}/{filename} "
                f"({region.size[0]}x{region.size[1]})", "DEBUG")

    return counts


def _classify_image(pil_img) -> str:
    """Classify an image using heuristics.

    - photo: high color variance, natural colors
    - chart: wide aspect, moderate colors, some text
    - table: grid-like, high text density
    - diagram: low color count, line art
    - figure: generic fallback
    """
    import numpy as np

    w, h = pil_img.size
    aspect = w / h if h > 0 else 1.0

    # Convert to numpy array
    arr = np.array(pil_img.convert("RGB"))

    # Color analysis
    # Unique colors (downsampled for speed)
    small = pil_img.resize((50, 50)).convert("RGB")
    small_arr = np.array(small)
    unique_colors = len(np.unique(small_arr.reshape(-1, 3), axis=0))

    # Color variance (photos have high variance)
    color_std = float(arr.std())

    # Edge density (diagrams have many sharp edges)
    gray = np.array(pil_img.convert("L").resize((100, 100)))
    # Simple edge detection: difference between adjacent pixels
    edges_h = np.abs(np.diff(gray, axis=0))
    edges_v = np.abs(np.diff(gray, axis=1))
    edge_density = float((edges_h.mean() + edges_v.mean()) / 2)

    # Classification rules
    if unique_colors > 500 and color_std > 50:
        # Many colors + high variance = photo
        return "photos"
    elif aspect > 1.5 and unique_colors < 200:
        # Wide + few colors = chart or table
        if edge_density > 20:
            return "charts"
        else:
            return "tables"
    elif unique_colors < 50 and edge_density > 15:
        # Few colors + many edges = diagram
        return "diagrams"
    elif aspect < 0.8 and unique_colors > 200:
        # Portrait + many colors = photo
        return "photos"
    else:
        # Fallback
        return "figures"


def _crop_vector_regions(
    page, page_idx: int, output: Path, dpi: int, drawings: list, log
) -> dict:
    """V11.74.0: Crop vector graphics regions (charts, tables, diagrams).

    ONLY processes vector drawings — NOT embedded images (those are
    already extracted separately). This prevents the duplication issue.

    Text-block exclusion: skips regions that are >50% text.
    """
    import fitz
    from PIL import Image

    counts = dict.fromkeys(CATEGORIES, 0)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    page_rect = page.rect

    # Extract drawing rectangles
    draw_rects = []
    for draw in drawings:
        if "rect" in draw:
            r = draw["rect"]
            if r.width > 80 and r.height > 80:
                draw_rects.append(r)

    if not draw_rects:
        return counts

    # Merge nearby rectangles into clusters
    merged = _merge_rects(draw_rects, threshold=30)

    # Get text blocks for exclusion
    text_blocks = page.get_text("blocks")
    text_rects = [fitz.Rect(b[:4]) for b in text_blocks if len(b) >= 4]

    for rect in merged:
        # Skip small regions
        if rect.width < 100 or rect.height < 100:
            continue

        # Skip if region is mostly text (>50% overlap with text blocks)
        region_area = rect.width * rect.height
        text_overlap = 0
        for tr in text_rects:
            if tr.intersects(rect):
                overlap = fitz.Rect(
                    max(rect.x0, tr.x0),
                    max(rect.y0, tr.y0),
                    min(rect.x1, tr.x1),
                    min(rect.y1, tr.y1),
                )
                if overlap.width > 0 and overlap.height > 0:
                    text_overlap += overlap.width * overlap.height

        if region_area > 0 and text_overlap / region_area > 0.5:
            continue  # mostly text — skip

        try:
            clip = fitz.Rect(rect)
            # Add padding
            pad = 5
            clip.x0 = max(0, clip.x0 - pad)
            clip.y0 = max(0, clip.y0 - pad)
            clip.x1 = min(page_rect.width, clip.x1 + pad)
            clip.y1 = min(page_rect.height, clip.y1 + pad)

            pix = page.get_pixmap(matrix=mat, clip=clip)
            img_data = pix.tobytes("jpeg")

            pil_img = Image.open(io.BytesIO(img_data))
            # V11.76.0: auto-trim whitespace
            pil_img = _auto_trim_whitespace(pil_img)
            category = _classify_image(pil_img)

            filename = f"page_{page_idx:04d}_vec_{counts[category]+1:03d}.jpg"
            filepath = output / category / filename
            Path(filepath).write_bytes(img_data)
            counts[category] += 1
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            pass  # best-effort

    return counts


def _smart_crop_page(page, page_idx, output, dpi, log):
    """V11.75.0: Smart-crop a page render to find image-only regions.

    Uses content-aware whitespace detection:
    1. Render the page at low DPI
    2. Convert to grayscale
    3. Find non-white regions (content blocks)
    4. Filter to regions that are likely images (high color variance,
       not just text)
    5. Crop and save each region

    Also optionally uses smartcrop library if installed, for finding
    the "most interesting" region of a page (good for pages with one
    large image surrounded by text).

    Falls back gracefully if smartcrop is not installed.
    """
    import fitz
    import numpy as np
    from PIL import Image

    counts = dict.fromkeys(CATEGORIES, 0)

    # Render page at low DPI for analysis (fast)
    analyze_dpi = 72
    zoom = analyze_dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")

    pil_img = Image.open(io.BytesIO(img_data))
    arr = np.array(pil_img.convert("RGB"))

    # Convert to grayscale for whitespace detection
    gray = np.array(pil_img.convert("L"))

    # Threshold: pixels darker than 240 = content (not white)
    content_mask = gray < 240

    # Find content rows and columns
    row_has_content = content_mask.any(axis=1)
    col_has_content = content_mask.any(axis=0)

    # Find content blocks by detecting row-gaps
    # A "gap" is a row where no content exists
    content_rows = np.where(row_has_content)[0]
    if len(content_rows) == 0:
        return counts  # blank page

    # Group content rows into blocks (separated by gaps)
    blocks = []
    start = content_rows[0]
    prev = content_rows[0]
    for r in content_rows[1:]:
        if r - prev > 15:  # gap of >15px = new block
            blocks.append((start, prev))
            start = r
        prev = r
    blocks.append((start, prev))

    # For each block, find the content columns
    for block_idx, (row_start, row_end) in enumerate(blocks):
        block_height = row_end - row_start
        if block_height < 30:  # skip tiny blocks (single lines of text)
            continue

        # Get the content columns for this row range
        block_content = content_mask[row_start:row_end+1]
        block_cols = np.where(block_content.any(axis=0))[0]
        if len(block_cols) == 0:
            continue

        col_start = block_cols[0]
        col_end = block_cols[-1]
        block_width = col_end - col_start

        # Skip small blocks
        if block_width < 50 or block_height < 50:
            continue

        # Check if this block is an IMAGE (not text):
        # Images have high color variance, text has low variance
        block_arr = arr[row_start:row_end+1, col_start:col_end+1]
        color_std = float(block_arr.std())
        unique_colors = len(np.unique(block_arr.reshape(-1, 3), axis=0))

        # Text: low color variance (<30) and few unique colors (<100)
        # Image: high color variance (>30) or many unique colors (>100)
        is_image = color_std > 30 or unique_colors > 100

        if not is_image:
            continue  # skip text blocks

        # Render this region at full DPI
        # Convert pixel coordinates back to PDF points
        scale = dpi / analyze_dpi
        pdf_x0 = col_start / analyze_dpi * 72
        pdf_y0 = row_start / analyze_dpi * 72
        pdf_x1 = (col_end + 1) / analyze_dpi * 72
        pdf_y1 = (row_end + 1) / analyze_dpi * 72

        clip = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
        # Add padding
        pad = 5
        clip.x0 = max(0, clip.x0 - pad)
        clip.y0 = max(0, clip.y0 - pad)
        clip.x1 = min(page.rect.width, clip.x1 + pad)
        clip.y1 = min(page.rect.height, clip.y1 + pad)

        full_mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix_crop = page.get_pixmap(matrix=full_mat, clip=clip)
        crop_data = pix_crop.tobytes("jpeg")

        # Classify
        crop_img = Image.open(io.BytesIO(crop_data))
        category = _classify_image(crop_img)

        filename = f"page_{page_idx:04d}_smart_{block_idx+1:03d}.jpg"
        filepath = output / category / filename
        Path(filepath).write_bytes(crop_data)
        counts[category] += 1
        log(f"  🎯 Smart-cropped: {category}/{filename} "
            f"({block_width}x{block_height})", "DEBUG")

    return counts


def _merge_rects(rects, threshold=20):
    """Merge overlapping or nearby rectangles into larger regions."""
    if not rects:
        return []

    import fitz

    # Sort by x position
    sorted_rects = sorted(rects, key=lambda r: (r.x0, r.y0))
    merged = [sorted_rects[0]]

    for rect in sorted_rects[1:]:
        last = merged[-1]
        # Check if rect is near the last merged rect
        if (abs(rect.x0 - last.x1) < threshold and
                abs(rect.y0 - last.y1) < threshold):
            # Merge
            merged[-1] = fitz.Rect(
                min(last.x0, rect.x0),
                min(last.y0, rect.y0),
                max(last.x1, rect.x1),
                max(last.y1, rect.y1)
            )
        elif (abs(rect.x0 - last.x0) < threshold and
              abs(rect.y0 - last.y1) < threshold):
            # Vertically adjacent
            merged[-1] = fitz.Rect(
                min(last.x0, rect.x0),
                min(last.y0, rect.y0),
                max(last.x1, rect.x1),
                max(last.y1, rect.y1)
            )
        else:
            merged.append(rect)

    return merged


def extract_images_from_epub(
    epub_path: str,
    output_folder: str,
    log_callback=None,
    progress_callback=None,
) -> dict:
    """Extract images from EPUB (EPUBs store images as files in a zip)."""
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    import zipfile

    from PIL import Image

    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (output / cat).mkdir(exist_ok=True)

    counts = dict.fromkeys(CATEGORIES, 0)
    counts["full_pages"] = 0
    counts["total"] = 0

    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            image_files = [
                f for f in zf.namelist()
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'))
            ]
            total = len(image_files)
            log(f"  📖 Found {total} images in EPUB", "INFO")

            for i, img_path in enumerate(image_files):
                pct = int(i / max(total, 1) * 100)
                progress(pct, f"🖼️ {i+1}/{total}")
                try:
                    img_data = zf.read(img_path)
                    pil_img = Image.open(io.BytesIO(img_data))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")

                    category = _classify_image(pil_img)
                    filename = f"epub_{i+1:04d}.jpg"
                    filepath = output / category / filename
                    pil_img.save(str(filepath), "JPEG", quality=92)
                    counts[category] += 1
                    counts["total"] += 1
                except Exception as e:
                    log(f"  ⚠️ Failed to extract {img_path}: {e}", "WARNING")

    except Exception as e:
        log(f"  ❌ EPUB error: {e}", "ERROR")

    log(f"  ✅ EPUB extraction: {counts['total']} images", "INFO")
    return counts


def extract_images_from_docx(
    docx_path: str,
    output_folder: str,
    log_callback=None,
    progress_callback=None,
) -> dict:
    """Extract images from DOCX (stored in word/media/)."""
    log = log_callback or (lambda msg, level="INFO": None)
    progress = progress_callback or (lambda pct, msg: None)

    import zipfile

    from PIL import Image

    output = Path(output_folder)
    output.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (output / cat).mkdir(exist_ok=True)

    counts = dict.fromkeys(CATEGORIES, 0)
    counts["full_pages"] = 0
    counts["total"] = 0

    try:
        with zipfile.ZipFile(docx_path, 'r') as zf:
            media_files = [
                f for f in zf.namelist()
                if f.startswith("word/media/")
            ]
            total = len(media_files)
            log(f"  📖 Found {total} images in DOCX", "INFO")

            for i, media_path in enumerate(media_files):
                pct = int(i / max(total, 1) * 100)
                progress(pct, f"🖼️ {i+1}/{total}")
                try:
                    img_data = zf.read(media_path)
                    pil_img = Image.open(io.BytesIO(img_data))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")

                    category = _classify_image(pil_img)
                    filename = f"docx_{i+1:04d}.jpg"
                    filepath = output / category / filename
                    pil_img.save(str(filepath), "JPEG", quality=92)
                    counts[category] += 1
                    counts["total"] += 1
                except Exception as e:
                    log(f"  ⚠️ Failed to extract {media_path}: {e}", "WARNING")

    except Exception as e:
        log(f"  ❌ DOCX error: {e}", "ERROR")

    log(f"  ✅ DOCX extraction: {counts['total']} images", "INFO")
    return counts
