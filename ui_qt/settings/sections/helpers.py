"""V0.4.19 — shared model-picker helpers for the settings sections.

The badge / model-list / async-fetch helpers used by every model-picking
section (``OcrModelSection``, ``AiLocalModelSection``, ``DefaultsSection``)
moved VERBATIM from ``ui_qt/settings/sections.py`` during the V0.4.19
de-monolithization — bodies byte-identical; only this docstring and the
re-homed imports are new.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox

from core.llm.model_taxonomy import is_vision_model
from ui_qt.components.simple_worker import SimpleWorker

# V18.20.3.12 follow-up (W-b11): module logger for the async model-fetch
# fail-softs — silent swallowed fetches are the W-c13 lesson.
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Helper: badge prefix for model pickers
# ════════════════════════════════════════════════════════════════════════════


def _badge(model: str) -> str:
    # V0.6.7 (review-loop B4): the vision badge routes through the
    # model_taxonomy SSOT (was a 4th copy of the keyword list — a minicpm-v
    # badged 📝 here while the OCR dialog listed it as an OCR model).
    return "🔍 " if is_vision_model(model) else "📝 "


def _get_ollama_models(controller) -> list:
    """V17.0.0: Fetch available Ollama models."""
    try:
        from utils.dependencies import DependencyChecker

        return DependencyChecker().get_ollama_models() or []
    except Exception:
        return []


def _populate_models(
    combo: QComboBox,
    models: list[str],
    current: str = "",
    allow_empty: bool = False,
    prefer_ocr: bool = False,
) -> None:
    """Fill a combo with all models (badged), selecting ``current`` or — if
    ``prefer_ocr`` — the first model whose name contains 'ocr'."""
    combo.clear()
    if allow_empty:
        combo.addItem("  (disabled)", "")
    for m in models:
        combo.addItem(_badge(m) + m, m)
    # selection priority: saved current → first 'ocr' model → first item
    if current:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
    if prefer_ocr:
        for m in models:
            if "ocr" in m.lower():
                idx = combo.findData(m)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    return
    if combo.count() > 0:
        combo.setCurrentIndex(0)


def _populate_models_async(
    combo: QComboBox,
    controller,
    current: str = "",
    allow_empty: bool = False,
    prefer_ocr: bool = False,
) -> None:
    """V18.20.4.5 (W-b11): fetch models OFF the UI thread; populate the
    combo on the main thread when done. Opening Settings no longer freezes
    the UI for up to 5s when Ollama is down."""
    worker = SimpleWorker(_get_ollama_models, controller)
    # Keep a ref on the combo so the worker isn't GC'd mid-run.
    combo._models_worker = worker

    def _apply(models):
        _populate_models(
            combo, models or [], current=current, allow_empty=allow_empty, prefer_ocr=prefer_ocr
        )

    worker.finished.connect(_apply)
    worker.failed.connect(lambda _err: None)  # fail-soft: combo keeps its items
    worker.start()


def _refresh_models_async(section, fetch_fn, on_loaded, refresh_btn=None) -> None:
    """V18.20.4.5 (W-b11): shared async model refresh for the settings
    sections (OcrModel / AiLocalModel / Defaults).

    ``fetch_fn`` (zero-arg, widget-free — pure HTTP) runs on a background
    SimpleWorker; ``on_loaded(models)`` populates the combos and runs on
    the MAIN thread (SimpleWorker's ``finished`` signal marshals there),
    so each section keeps its own populate semantics exactly. The worker
    is stored on ``section._models_worker`` (a Python ref — without it the
    QObject can be GC'd mid-run); ``refresh_btn`` is disabled while
    loading and re-enabled in BOTH outcome handlers (W-b18 class: a
    raising worker must never leave the button stuck disabled). Failure
    is fail-soft — the combos keep their current items.
    """
    worker = getattr(section, "_models_worker", None)
    try:
        in_flight = worker is not None and worker.is_running()
    except RuntimeError:
        in_flight = False  # worker already deleteLater'd itself — not running
    if in_flight:
        return  # a fetch is already in flight — don't stack workers
    if refresh_btn is not None:
        refresh_btn.setEnabled(False)
    w = SimpleWorker(fetch_fn)
    section._models_worker = w

    def _done(models):
        if refresh_btn is not None:
            refresh_btn.setEnabled(True)
        on_loaded(models or [])

    def _fail(err):
        logger.debug("Model refresh failed (W-b11 fail-soft): %s", err)
        if refresh_btn is not None:
            refresh_btn.setEnabled(True)

    w.finished.connect(_done)
    w.failed.connect(_fail)
    w.start()
