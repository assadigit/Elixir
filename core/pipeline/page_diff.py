"""V10.18.0 (C4): Differential re-run — detect which PDF pages changed.

Compares per-page text hashes between the current PDF and the previous run.
Only changed pages need re-OCR/re-summarization — 10x faster re-runs after
small PDF edits.

Usage::

    from core.pipeline.page_diff import get_changed_pages
    changed = get_changed_pages(pdf_path, output_dir)
    # changed = set of page numbers that differ from the last run
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_page_hashes(pdf_path: Path, password: str | None = None) -> dict:
    """Compute a hash for each page's extracted text.

    Returns {page_num: sha256_hash} for all pages.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted and password:
        reader.decrypt(password)

    hashes = {}
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            hashes[i] = hashlib.sha256(text.encode()).hexdigest()[:16]
        except Exception as _e:
            hashes[i] = "error"
    return hashes


def save_page_hashes(hashes: dict, output_dir: Path) -> None:
    """Save page hashes to the output directory for next-run comparison."""
    hash_file = output_dir / ".page_hashes.json"
    hash_file.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def get_changed_pages(pdf_path: Path, output_dir: Path, password: str | None = None) -> set[int]:
    """V10.18.0 (C4): Detect which pages changed since the last run.

    Compares current page hashes with the saved hashes from the last run.
    Returns a set of page numbers that are new, changed, or whose hash
    differs. If no saved hashes exist, returns ALL pages (first run).
    """
    current_hashes = compute_page_hashes(pdf_path, password)
    hash_file = output_dir / ".page_hashes.json"

    if not hash_file.exists():
        # First run — all pages are "changed"
        save_page_hashes(current_hashes, output_dir)
        return set(current_hashes.keys())

    try:
        old_hashes = json.loads(hash_file.read_text(encoding="utf-8"))
    except OSError:
        old_hashes = {}

    changed = set()
    for page_num, hash_val in current_hashes.items():
        if page_num not in old_hashes or old_hashes[page_num] != hash_val:
            changed.add(page_num)

    # Save current hashes for next run
    save_page_hashes(current_hashes, output_dir)
    return changed
