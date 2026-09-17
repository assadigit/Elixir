"""V11.0.0: Standalone service dialogs — shared base + service dialogs.

V18.20.4.6 (P5 / O-b2): the per-dialog decomposition. Everything below
the imports moved VERBATIM into ui_qt/views/service_dialogs/dialogs/
(one module per dialog + shared.py for the shared plumbing: the
PlainTextTextEdit paste widget, the V11.25 success modal, the
V18.20.4.5 (T-b2) close-event guard helpers, and BaseServiceDialog).
This module is now a pure back-compat facade: every name that was
importable from ui_qt.views.service_dialogs.base_dialog before the
split still is — the external importers (ui_qt/app.py +
ui_qt/views/convert_view.py, the 11 dialog classes) are untouched.
No class definitions remain here."""

from __future__ import annotations

# V18.20.4.6 (P5 / O-b2): the dialog classes now live in
# ui_qt/views/service_dialogs/dialogs/ (one module per dialog, bodies
# verbatim). These imports are the back-compat facade — every
# pre-split public name stays importable from this module.
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    PlainTextTextEdit,
    _confirm_close_with_running_worker,
    _detach_worker_signals,
    _show_success_modal,
    _worker_is_running,
)
from ui_qt.views.service_dialogs.dialogs.ocr_service_dialog import (
    OcrServiceDialog,
)
from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
    SummarizationServiceDialog,
)
from ui_qt.views.service_dialogs.dialogs.translation_service_dialog import (
    TranslationServiceDialog,
)
from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import (
    TtsServiceDialog,
    _is_cpu_tts_error,
    _show_cpu_tts_warning_modal,
    _show_tts_gpu_error_modal,
    _tts_cuda_available,
    _tts_torch_cuda_tag,
)
from ui_qt.views.service_dialogs.dialogs.quick_convert_dialog import (
    QuickConvertDialog,
)
from ui_qt.views.service_dialogs.dialogs.pdf_docx_cutter_dialog import (
    PdfDocxCutterDialog,
)
from ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog import (
    MarkdownStylerDialog,
)
from ui_qt.views.service_dialogs.dialogs.packets_tool_dialog import (
    PacketsToolDialog,
    _PacketWorker,
)
from ui_qt.views.service_dialogs.dialogs.hallucination_audit_dialog import (
    HallucinationAuditDialog,
    _HallucinationAuditWorker,
)
from ui_qt.views.service_dialogs.dialogs.image_extractor_dialog import (
    ImageExtractorDialog,
)
from ui_qt.views.service_dialogs.dialogs.transcribe_service_dialog import (
    TranscribeServiceDialog,
)

__all__ = [
    # the 11 service dialogs (what app.py / convert_view.py import)
    "OcrServiceDialog",
    "SummarizationServiceDialog",
    "TranslationServiceDialog",
    "TtsServiceDialog",
    "QuickConvertDialog",
    "PdfDocxCutterDialog",
    "MarkdownStylerDialog",
    "PacketsToolDialog",
    "HallucinationAuditDialog",
    "ImageExtractorDialog",
    "TranscribeServiceDialog",
    # shared plumbing (pre-split public names)
    "BaseServiceDialog",
    "PlainTextTextEdit",
    "_show_success_modal",
    # the V18.20.4.5 (T-b2) close-event guard helpers
    "_worker_is_running",
    "_detach_worker_signals",
    "_confirm_close_with_running_worker",
    # the private worker / TTS guardrail helpers (same-module re-exports)
    "_PacketWorker",
    "_HallucinationAuditWorker",
    "_tts_cuda_available",
    "_tts_torch_cuda_tag",
    "_is_cpu_tts_error",
    "_show_cpu_tts_warning_modal",
    "_show_tts_gpu_error_modal",
]
