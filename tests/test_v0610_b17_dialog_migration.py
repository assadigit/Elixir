"""V0.6.10 (B17) — the service-dialog migration tests.

AUDIT_SWOT W4 (MEASURED): 9 of the 11 service dialogs were NOT on
``BaseServiceDialog`` — each carried its own copy of the shared plumbing
(``closeEvent`` worker-guard ×9, ``_pick_output`` ×8, ``_on_process`` ×6,
plus the cancel/reset/result-preview scaffolding). The tts/translation
precedent (V11.0.0) showed the target shape.

The V0.6.10 migration moved all 9 onto the base (batch A: markdown_styler,
quick_convert, pdf_docx_cutter, image_extractor, hallucination_audit —
verified line-by-line by the 6-a agent; batch B: transcribe_service,
summarization_service, ocr_service, packets_tool — verified by the 6-b
reviewer against the V0.6.8/V0.6.9 contracts: the _fetch_models_from
never-raise + the 3 s probe budgets). These pins keep the migration in
place: every dialog subclasses the base, and the worker-guard family is
inherited from ONE place.

The deep behavioral net is the e2e suites (test_v0600_tool_* — pinned
byte-identical before/after by the agents) + the split/thread pin files.

Run: pytest tests/test_v0610_b17_dialog_migration.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like the swept files do (conftest
# provides the modules; this file stays stub-free per the V0.6.10 / B16 rule).

_THE_NINE = (
    "markdown_styler_dialog.MarkdownStylerDialog",
    "quick_convert_dialog.QuickConvertDialog",
    "pdf_docx_cutter_dialog.PdfDocxCutterDialog",
    "image_extractor_dialog.ImageExtractorDialog",
    "hallucination_audit_dialog.HallucinationAuditDialog",
    "transcribe_service_dialog.TranscribeServiceDialog",
    "summarization_service_dialog.SummarizationServiceDialog",
    "ocr_service_dialog.OcrServiceDialog",
    "packets_tool_dialog.PacketsToolDialog",
)

_DIALOGS_DIR = _project_root / "ui_qt" / "views" / "service_dialogs" / "dialogs"


def _mro_of(module_name: str, class_name: str) -> list[str]:
    import importlib

    mod = importlib.import_module(f"ui_qt.views.service_dialogs.dialogs.{module_name}")
    cls = getattr(mod, class_name)
    return [c.__name__ for c in cls.__mro__]


class TestAllNineOnTheBase:
    def test_every_dialog_subclasses_base_service_dialog(self):
        """All 9 migrated dialogs inherit BaseServiceDialog (the B17 goal —
        one shared closeEvent guard, worker scaffolding, and UI frame)."""
        for qual in _THE_NINE:
            module_name, class_name = qual.split(".")
            mro = _mro_of(module_name, class_name)
            assert "BaseServiceDialog" in mro, (
                f"{class_name} must subclass BaseServiceDialog (V0.6.10 / B17): MRO={mro}"
            )

    def test_the_precedent_pair_still_on_the_base(self):
        """tts + translation (the V11.0.0 precedent) stay on the base — the
        migration must not have regressed its own template."""
        for qual in (
            "tts_service_dialog.TtsServiceDialog",
            "translation_service_dialog.TranslationServiceDialog",
        ):
            module_name, class_name = qual.split(".")
            assert "BaseServiceDialog" in _mro_of(module_name, class_name)

    def test_the_worker_guard_family_is_inherited_not_copied(self):
        """The B17 fold-in: the duplicated closeEvent worker-guard family
        shrinks to the base's ONE definition + legitimate overrides. A raw
        ``def closeEvent`` in a migrated dialog must cite the V0.6.10 (B17)
        reason (the tts preview-worker precedent pattern)."""
        base_src = (_DIALOGS_DIR / "shared.py").read_text(encoding="utf-8")
        assert "def closeEvent" in base_src  # the ONE canonical guard
        copied = []
        for qual in _THE_NINE:
            module_name, class_name = qual.split(".")
            src = (_DIALOGS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
            if "def closeEvent" in src and "V0.6.10 (B17)" not in src:
                copied.append(module_name)
        assert not copied, (
            f"unexplained closeEvent copies (the guard must come from the "
            f"base or carry the B17 override reason): {copied}"
        )

    def test_base_dialog_facade_untouched(self):
        """The back-compat facade still re-exports all 11 dialog classes —
        the external importers (app.py, convert_view.py) are untouched."""
        facade = (
            _project_root / "ui_qt" / "views" / "service_dialogs" / "base_dialog.py"
        ).read_text(encoding="utf-8")
        for qual in _THE_NINE:
            class_name = qual.split(".")[1]
            assert class_name in facade
        assert "BaseServiceDialog" in facade
