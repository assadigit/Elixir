"""Headless smoke: instantiate every tool dialog offscreen with a stub
controller. Catches import errors, missing deps, constructor crashes.

Run: QT_QPA_PLATFORM=offscreen python scripts/tmp_dialog_smoke.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


class _Settings:
    _data: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._data.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._data[key] = value


class StubController(_Settings):
    """Minimal controller stand-in — dialogs only need get/update_setting
    plus attribute storage (verified via grep across dialogs/*.py)."""


CTRL = StubController()

DIALOGS = [
    ("QuickConvertDialog", "ui_qt.views.service_dialogs.dialogs.quick_convert_dialog"),
    ("PdfDocxCutterDialog", "ui_qt.views.service_dialogs.dialogs.pdf_docx_cutter_dialog"),
    ("ImageExtractorDialog", "ui_qt.views.service_dialogs.dialogs.image_extractor_dialog"),
    ("OcrServiceDialog", "ui_qt.views.service_dialogs.dialogs.ocr_service_dialog"),
    (
        "SummarizationServiceDialog",
        "ui_qt.views.service_dialogs.dialogs.summarization_service_dialog",
    ),
    ("TranslationServiceDialog", "ui_qt.views.service_dialogs.dialogs.translation_service_dialog"),
    ("MarkdownStylerDialog", "ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog"),
    ("PacketsToolDialog", "ui_qt.views.service_dialogs.dialogs.packets_tool_dialog"),
    ("TtsServiceDialog", "ui_qt.views.service_dialogs.dialogs.tts_service_dialog"),
    ("TranscribeServiceDialog", "ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog"),
    ("HallucinationAuditDialog", "ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog"),
]

results: list[tuple[str, str]] = []
for cls_name, mod_name in DIALOGS:
    try:
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        dlg = cls(CTRL)
        dlg.close()
        dlg.deleteLater()
        results.append((cls_name, "OK"))
    except Exception:
        tb = traceback.format_exc(limit=4)
        results.append((cls_name, "FAIL:\n" + tb))

# PodcastMakerView (the modal view)
try:
    from ui_qt.views.podcast_maker_view import PodcastMakerView

    v = PodcastMakerView(CTRL)
    v.deleteLater()
    results.append(("PodcastMakerView", "OK"))
except Exception:
    results.append(("PodcastMakerView", "FAIL:\n" + traceback.format_exc(limit=4)))

fails = 0
for name, status in results:
    if status == "OK":
        print(f"  {name:35s} OK")
    else:
        fails += 1
        print(f"  {name:35s} {status}")

print(f"\n{len(results) - fails}/{len(results)} dialogs constructed cleanly")
sys.exit(1 if fails else 0)
