"""V0.6.5 — the RTL outputs + the LLM-structured Markdown Styler + the
translation active-LLM fallback. House 3-layer pattern
(test_v0600_tool_cutter_e2e.py is the reference).

Layer 1 — pure helpers:
  utils/rtl.py (rtl_ratio / is_rtl_dominant — letters-only voting),
  service_formatters._ensure_md_dir_rtl (merge/prepend, no duplicates),
  core/summarisation/markdown_styler.py (parse_structure leniency,
  assemble_obsidian_note options, build_scan_prompt repair flag,
  style_markdown_llm retry/fallback with a FAKE llm_call).

Layer 2 — service end-to-end on REAL files:
  write_output md/docx/pdf with a real Persian fixture → the RTL
  artifacts (dir: rtl property, w:bidi paragraphs, Vazirmatn subset
  embedded in the PDF, right-aligned reportlab styles via the direct
  write_pdf rtl=True path); English fixtures stay LTR (regression);
  TranslationEngine with an injected llm_complete callable (no HTTP).

Layer 3 — dialog drives through the real SimpleWorker:
  the styler's LLM path (style_markdown_llm monkeypatched at the module
  seam — the worker imports it at call time), the deterministic
  fallback when the LLM returns None, the checkbox-off instant path.

Live-LLM leg (marked live_llm, deselected by default): the styler
pipeline through the real provider at the :3031 shim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# ── shared helpers ────────────────────────────────────────────────────

_PERSIAN_ARTICLE = (
    "## خلاصه مدیریتی\n\n"
    "استیم کلود قابلیتی است که بازی‌های شما را با سرورهای استیم همگام‌سازی می‌کند.\n\n"
    "- ذخیره‌سازی ابری فایل‌های بازی\n"
    "- همگام‌سازی تنظیمات بین دستگاه‌ها\n\n"
    "گاهی اوقات نرم‌افزاری که فعالیت سیستم را تغییر می‌دهد اختلال ایجاد می‌کند."
)

_ENGLISH_TEXT = (
    "## Executive Summary\n\nSteam Cloud syncs your games automatically.\n\n"
    "- Cloud saves\n"
    "- Settings sync\n"
)


def _skip_qt():
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except Exception:
        return True
    return False


def _qt_available() -> bool:
    return not _skip_qt()


# ═══════════════════════════════════════════════════════════════════════
# Layer 1 — pure helpers
# ═══════════════════════════════════════════════════════════════════════


class TestRtlDetection:
    """utils/rtl.py — the content-agnostic direction detector."""

    def test_persian_article_is_rtl(self):
        from utils.rtl import is_rtl_dominant

        assert is_rtl_dominant(_PERSIAN_ARTICLE) is True

    def test_english_is_ltr(self):
        from utils.rtl import is_rtl_dominant

        assert is_rtl_dominant(_ENGLISH_TEXT) is False

    def test_rtl_with_embedded_english_terms_stays_rtl(self):
        from utils.rtl import is_rtl_dominant

        mixed = "استیم کلود Steam Cloud قابلیتی است که بازی‌ها را همگام‌سازی می‌کند."
        assert is_rtl_dominant(mixed) is True

    def test_english_with_one_rtl_quote_stays_ltr(self):
        from utils.rtl import is_rtl_dominant

        mostly_en = (
            "The report opens with a Persian greeting, namely سلام, then continues "
            "in English for the whole document body and analysis."
        )
        assert is_rtl_dominant(mostly_en) is False

    def test_empty_and_markdown_only_text_is_ltr(self):
        from utils.rtl import is_rtl_dominant, rtl_ratio

        assert rtl_ratio("") == 0.0
        assert is_rtl_dominant("") is False
        assert is_rtl_dominant("- - -\n# # #\n* * *") is False

    def test_digits_and_markdown_do_not_vote(self):
        from utils.rtl import rtl_ratio

        # Numbers/bullets alone → 0.0; with one Persian letter the ratio
        # is that letter's share of LETTERS (markdown never counts).
        assert rtl_ratio("12345 - ** ** ` `") == 0.0
        assert 0.0 < rtl_ratio("سلام 12345") <= 1.0


class TestMdDirRtl:
    """_ensure_md_dir_rtl — the Obsidian ``dir: rtl`` property."""

    def test_prepends_new_frontmatter(self):
        from core.outputs.service_formatters import _ensure_md_dir_rtl

        out = _ensure_md_dir_rtl("Body text without frontmatter.")
        assert out.startswith("---\ndir: rtl\n---\n\n")
        assert "Body text without frontmatter." in out

    def test_merges_into_existing_frontmatter(self):
        from core.outputs.service_formatters import _ensure_md_dir_rtl

        src = '---\ntitle: "Note"\ntags: [a]\n---\n\nBody.'
        out = _ensure_md_dir_rtl(src)
        assert out.startswith("---\ndir: rtl\ntitle:")
        assert out.count("dir: rtl") == 1
        assert "Body." in out

    def test_never_duplicates(self):
        from core.outputs.service_formatters import _ensure_md_dir_rtl

        src = "---\ndir: rtl\n---\n\nBody."
        assert _ensure_md_dir_rtl(src) == src


class TestParseStructure:
    """markdown_styler.parse_structure — lenient JSON recovery."""

    def _valid(self) -> dict:
        return {
            "title": "Steam Cloud Guide",
            "is_rtl": False,
            "tldr": "How Steam Cloud works.",
            "key_concepts": ["Steam Cloud"],
            "tags": ["steam"],
            "sections": [{"heading": "Checking", "level": 2, "content": "Open the library."}],
        }

    def test_plain_json(self):
        from core.summarisation.markdown_styler import parse_structure

        st = parse_structure(json.dumps(self._valid()))
        assert st["title"] == "Steam Cloud Guide"
        assert st["sections"][0]["heading"] == "Checking"

    def test_fenced_json(self):
        from core.summarisation.markdown_styler import parse_structure

        raw = "```json\n" + json.dumps(self._valid()) + "\n```"
        assert parse_structure(raw)["title"] == "Steam Cloud Guide"

    def test_prose_wrapped_json(self):
        from core.summarisation.markdown_styler import parse_structure

        raw = "Here is the structure you asked for:\n" + json.dumps(self._valid()) + "\nDone."
        assert parse_structure(raw) is not None

    def test_trailing_comma_json(self):
        from core.summarisation.markdown_styler import parse_structure

        raw = json.dumps(self._valid()).replace("}", ",}")
        assert parse_structure(raw) is not None

    def test_is_rtl_string_form(self):
        from core.summarisation.markdown_styler import parse_structure

        data = self._valid()
        data["is_rtl"] = "true"
        assert parse_structure(json.dumps(data))["is_rtl"] is True

    def test_level_clamped_to_2_or_3(self):
        from core.summarisation.markdown_styler import parse_structure

        data = self._valid()
        data["sections"] = [
            {"heading": "A", "level": 1, "content": "x"},
            {"heading": "B", "level": 5, "content": "y"},
        ]
        st = parse_structure(json.dumps(data))
        assert [s["level"] for s in st["sections"]] == [2, 3]

    def test_garbage_returns_none(self):
        from core.summarisation.markdown_styler import parse_structure

        assert parse_structure("no json here at all") is None
        assert parse_structure("") is None
        assert parse_structure("{broken json") is None

    def test_missing_title_or_sections_returns_none(self):
        from core.summarisation.markdown_styler import parse_structure

        no_title = self._valid()
        del no_title["title"]
        assert parse_structure(json.dumps(no_title)) is None
        no_secs = self._valid()
        no_secs["sections"] = []
        assert parse_structure(json.dumps(no_secs)) is None

    def test_tags_normalized_lowercase_dashed(self):
        from core.summarisation.markdown_styler import parse_structure

        data = self._valid()
        data["tags"] = ["Steam Cloud", "#sync", "Persian گیما"]
        st = parse_structure(json.dumps(data))
        assert st["tags"][0] == "steam-cloud"
        assert st["tags"][1] == "sync"


class TestAssembleNote:
    """markdown_styler.assemble_obsidian_note — the Obsidian layout."""

    STRUCTURE = {
        "title": 'The "Fast" Track',
        "is_rtl": True,
        "tldr": "A note about tracks.",
        "key_concepts": ["Fast", "Track"],
        "tags": ["fast", "track"],
        "sections": [
            {"heading": "Main", "level": 2, "content": "Para one.\n\n\n\nPara two."},
            {"heading": "Sub", "level": 3, "content": "- bullet"},
        ],
    }

    def test_full_layout(self):
        from core.summarisation.markdown_styler import assemble_obsidian_note

        note = assemble_obsidian_note(self.STRUCTURE)
        assert note.startswith('---\ntitle: "The \\"Fast\\" Track"')
        assert "date: " in note
        assert "tags: [fast, track]" in note
        assert "dir: rtl" in note
        assert "> [!tldr] Summary\n> A note about tracks." in note
        assert "> [!info] Key Concepts\n> - **Fast**" in note
        assert "## Main" in note and "### Sub" in note

    def test_blank_runs_collapsed(self):
        from core.summarisation.markdown_styler import assemble_obsidian_note

        note = assemble_obsidian_note(self.STRUCTURE)
        assert "\n\n\n" not in note.split("## Main", 1)[1]

    def test_option_gates(self):
        from core.summarisation.markdown_styler import assemble_obsidian_note

        note = assemble_obsidian_note(
            self.STRUCTURE, include_tldr=False, include_concepts=False, include_tags=False
        )
        assert "[!tldr]" not in note
        assert "[!info]" not in note
        assert "tags:" not in note
        assert 'title: "The \\"Fast\\" Track"' in note  # front-matter stays

    def test_single_trailing_newline(self):
        from core.summarisation.markdown_styler import assemble_obsidian_note

        note = assemble_obsidian_note(self.STRUCTURE)
        assert note.endswith("\n") and not note.endswith("\n\n")


class TestStyleMarkdownLlm:
    """style_markdown_llm with a FAKE llm_call (hermetic)."""

    def _structure_json(self) -> str:
        return json.dumps(
            {
                "title": "Trains",
                "is_rtl": False,
                "tldr": "About trains.",
                "key_concepts": ["Rail"],
                "tags": ["trains"],
                "sections": [{"heading": "History", "level": 2, "content": "Railways grew."}],
            }
        )

    def test_success_first_try(self):
        from core.summarisation.markdown_styler import style_markdown_llm

        calls = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return self._structure_json()

        result = style_markdown_llm("Railways changed the world.", fake)
        assert result is not None
        note, structure = result
        assert structure["title"] == "Trains"
        assert "## History" in note
        assert len(calls) == 1

    def test_one_repair_retry_on_garbage(self):
        from core.summarisation.markdown_styler import style_markdown_llm

        replies = ["oops not json", self._structure_json()]

        def fake(prompt: str) -> str:
            return replies.pop(0)

        result = style_markdown_llm("Railways changed the world.", fake)
        assert result is not None
        assert result[1]["title"] == "Trains"

    def test_retry_prompt_carries_json_reminder(self):
        from core.summarisation.markdown_styler import style_markdown_llm

        prompts = []

        def fake(prompt: str) -> str:
            prompts.append(prompt)
            return "garbage"

        assert style_markdown_llm("Some article text here.", fake) is None
        assert len(prompts) == 2
        assert "not parseable JSON" in prompts[1]
        # The base prompt carries the article + the structure contract.
        assert "ARTICLE" in prompts[0]
        assert '"sections"' in prompts[0]

    def test_llm_none_returns_none(self):
        from core.summarisation.markdown_styler import style_markdown_llm

        assert style_markdown_llm("text", lambda p: None) is None
        assert style_markdown_llm("", lambda p: "x") is None


# ═══════════════════════════════════════════════════════════════════════
# Layer 2 — service end-to-end (real files)
# ═══════════════════════════════════════════════════════════════════════


class TestWriteOutputRtl:
    """write_output auto-detects RTL and threads it into every format."""

    def test_md_gets_dir_rtl_for_persian(self, tmp_path):
        from core.outputs.service_formatters import write_output

        out = tmp_path / "fa.md"
        ok, _msg = write_output(_PERSIAN_ARTICLE, out, fmt=".md", title="خلاصه")
        assert ok
        text = out.read_text(encoding="utf-8")
        assert "dir: rtl" in text

    def test_md_stays_ltr_for_english(self, tmp_path):
        from core.outputs.service_formatters import write_output

        out = tmp_path / "en.md"
        write_output(_ENGLISH_TEXT, out, fmt=".md")
        assert "dir: rtl" not in out.read_text(encoding="utf-8")

    def test_obsidian_persian_frontmatter_has_dir(self, tmp_path):
        from core.outputs.service_formatters import write_output

        out = tmp_path / "fa_obs.md"
        ok, _msg = write_output(
            _PERSIAN_ARTICLE, out, fmt=".md", title="خلاصه", obsidian=True, tags=["بازی"]
        )
        assert ok
        text = out.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "dir: rtl" in text.split("---")[1]
        assert 'title: "خلاصه"' in text
        # Unknown (Persian) headings stay as ## headings — correct: the
        # callout_map only maps the known English section names.

    def test_explicit_rtl_false_overrides_detection(self, tmp_path):
        from core.outputs.service_formatters import write_output

        out = tmp_path / "forced.md"
        write_output(_PERSIAN_ARTICLE, out, fmt=".md", rtl=False)
        assert "dir: rtl" not in out.read_text(encoding="utf-8")

    def test_docx_rtl_bidi_on_every_paragraph(self, tmp_path):
        pytest.importorskip("docx")
        from core.outputs.service_formatters import write_output

        out = tmp_path / "fa.docx"
        ok, _msg = write_output(_PERSIAN_ARTICLE, out, fmt=".docx", title="خلاصه")
        assert ok

        from docx import Document

        d = Document(str(out))
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paras = [p for p in d.paragraphs if p.text.strip()]
        assert len(paras) >= 5  # title + 2 headings + 2 bullets + body
        bidi = 0
        for p in paras:
            pPr = p._p.find(W + "pPr")
            assert pPr is not None, "paragraph missing pPr"
            if pPr.find(W + "bidi") is not None:
                bidi += 1
        assert bidi == len(paras), f"only {bidi}/{len(paras)} paragraphs are bidi"

    def test_docx_english_ltr_has_no_bidi(self, tmp_path):
        pytest.importorskip("docx")
        from core.outputs.service_formatters import write_output

        out = tmp_path / "en.docx"
        write_output(_ENGLISH_TEXT, out, fmt=".docx")
        from docx import Document

        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        d = Document(str(out))
        for p in d.paragraphs:
            if not p.text.strip():
                continue
            pPr = p._p.find(W + "pPr")
            if pPr is not None:
                assert pPr.find(W + "bidi") is None, "LTR docx must not carry bidi"

    def test_pdf_weasy_embeds_vazirmatn_and_shaping(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        weasy = pytest.importorskip("weasyprint")
        _ = (fitz, weasy)
        from core.outputs.service_formatters import write_output

        out = tmp_path / "fa.pdf"
        ok, _msg = write_output(_PERSIAN_ARTICLE, out, fmt=".pdf", title="خلاصه")
        assert ok and out.exists()

        doc = fitz.open(str(out))
        fonts = [f[3] for f in doc[0].get_fonts()]
        assert any("Vazirmatn" in f for f in fonts), fonts
        # The shaped text extracts as Arabic presentation forms.
        text = doc[0].get_text()
        assert any("\ufb50" <= c <= "\ufeff" or "\u0600" <= c <= "\u06ff" for c in text)

    def test_pdf_reportlab_rtl_path(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        reportlab = pytest.importorskip("reportlab")
        _ = (fitz, reportlab)
        from core.outputs.service_formatters import write_pdf

        out = tmp_path / "fa_rl.pdf"
        assert write_pdf(_PERSIAN_ARTICLE, out, title="خلاصه", rtl=True) is True
        doc = fitz.open(str(out))
        fonts = [f[3] for f in doc[0].get_fonts()]
        assert any("Vazirmatn" in f for f in fonts), fonts
        text = doc[0].get_text()
        # ReportLab draws the visual (reshaped) order — presentation forms.
        assert any("\ufb50" <= c <= "\ufeff" for c in text), text[:80]

    def test_pdf_english_ltr_no_vazirmatn(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        from core.outputs.service_formatters import write_pdf

        out = tmp_path / "en.pdf"
        assert write_pdf(_ENGLISH_TEXT, out, title="Summary") is True
        fonts = [f[3] for f in fitz.open(str(out))[0].get_fonts()]
        assert not any("Vazirmatn" in f for f in fonts), fonts


class TestTranslationEngineTransport:
    """TranslationEngine with the injected llm_complete (no HTTP)."""

    def test_llm_complete_transport_used(self):
        from core.translation.translation_engine import TranslationEngine

        seen: list[str] = []

        def fake_complete(prompt: str) -> str:
            seen.append(prompt)
            return "سلام دنیا"

        engine = TranslationEngine(
            ollama_url="http://localhost:1",
            model="whatever",
            source_lang="en",
            target_lang="fa",
            llm_complete=fake_complete,
        )
        out = engine.translate_text("Hello world")
        assert out == "سلام دنیا"
        assert len(seen) >= 1

    def test_llm_complete_exception_is_not_fatal(self):
        from core.translation.translation_engine import TranslationEngine

        def boom(prompt: str) -> str:
            raise RuntimeError("backend down")

        engine = TranslationEngine(
            ollama_url="http://localhost:1",
            model="m",
            source_lang="en",
            target_lang="fa",
            llm_complete=boom,
        )
        # Retries exhausted → the original line survives (the documented
        # engine contract: never lose the user's text on model failure).
        out = engine.translate_text("Hello world")
        assert "Hello world" in out

    def test_no_llm_complete_keeps_raw_transport(self, monkeypatch):
        from core.translation import translation_engine as te

        posted: list[str] = []

        class _FakeResp:
            status_code = 200

            def json(self):
                return {"response": "سلام"}

        monkeypatch.setattr(
            te,
            "session_for_url",
            lambda url: type(
                "S",
                (),
                {"post": staticmethod(lambda *a, **k: (posted.append(a[0]), _FakeResp())[1])},
            )(),
        )
        engine = te.TranslationEngine(
            ollama_url="http://localhost:9", model="m", source_lang="en", target_lang="fa"
        )
        out = engine.translate_text("Hello world")
        assert out == "سلام"
        assert posted and posted[0].endswith("/api/generate")


# ═══════════════════════════════════════════════════════════════════════
# Layer 3 — dialog drives (real SimpleWorker)
# ═══════════════════════════════════════════════════════════════════════


class _MsgBoxRecorder:
    """Stub QMessageBox — headless dialogs must never block."""

    def __init__(self):
        self.calls: list[tuple] = []

    def warning(self, *a, **k):
        self.calls.append(("warning", a))

    def critical(self, *a, **k):
        self.calls.append(("critical", a))

    def information(self, *a, **k):
        self.calls.append(("information", a))

    def question(self, *a, **k):
        return self.calls.append(("question", a)) or 0x00004000

    def titles(self):
        return [c[1][1] if len(c[1]) > 1 else "" for c in self.calls]


class _StubController:
    """Minimal controller stub (the service-dialog base class calls
    get_setting; the translation test file's precedent)."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestStylerDialogLlmPath:
    """The V0.6.5 styler dialog: LLM path via the real SimpleWorker with
    style_markdown_llm monkeypatched at the module seam (the worker
    imports it at call time)."""

    def _make(self, monkeypatch, tmp_path):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog as styler_mod

        rec = _MsgBoxRecorder()
        monkeypatch.setattr(styler_mod, "QMessageBox", rec)
        dlg = styler_mod.MarkdownStylerDialog(_StubController())

        # No network from the refresh probe.
        monkeypatch.setattr(dlg, "_refresh_models", lambda: None)
        return dlg, app, rec, styler_mod

    def _flush(self, app, rounds: int = 400):
        from PySide6.QtCore import QCoreApplication

        for _ in range(rounds):
            app.processEvents()
            QCoreApplication.sendPostedEvents()

    def test_llm_path_lands_styled_note(self, monkeypatch, tmp_path):
        dlg, app, _rec, _mod = self._make(monkeypatch, tmp_path)

        import core.summarisation.markdown_styler as ms

        structure = {
            "title": "Steam Cloud Guide",
            "is_rtl": True,
            "tldr": "How cloud sync works.",
            "key_concepts": ["Steam Cloud"],
            "tags": ["steam"],
            "sections": [{"heading": "Checking", "level": 2, "content": "Open the library."}],
        }
        note = ms.assemble_obsidian_note(structure)

        def fake_style(text, llm_call, **k):
            return note, structure

        monkeypatch.setattr(ms, "style_markdown_llm", fake_style)

        dlg.text_input.setPlainText(
            "Steam Cloud article body with enough text to clear the guard easily."
        )
        assert dlg.llm_chk.isChecked()  # the new default
        dlg._on_process()

        # Wait for the worker to finish (queued signals).
        if dlg._worker is not None:
            dlg._worker.wait(8000)
        self._flush(app)

        out = dlg.output_preview.toPlainText()
        assert 'title: "Steam Cloud Guide"' in out
        assert "## Checking" in out
        assert "dir: rtl" in out
        assert dlg.save_btn.isEnabled()
        assert "Steam Cloud Guide" in dlg.status_label.text()
        assert dlg.process_btn.text() == "✨ Style My Markdown"
        assert dlg.process_btn.isEnabled()

    def test_llm_failure_falls_back_to_deterministic(self, monkeypatch, tmp_path):
        dlg, app, _rec, _mod = self._make(monkeypatch, tmp_path)

        import core.summarisation.markdown_styler as ms

        monkeypatch.setattr(ms, "style_markdown_llm", lambda *a, **k: None)

        messy = "<div>Study Notes On Trains</div>\n\nRailways changed the world.\n"
        dlg.text_input.setPlainText(messy)
        dlg._on_process()
        if dlg._worker is not None:
            dlg._worker.wait(8000)
        self._flush(app)

        out = dlg.output_preview.toPlainText()
        assert "## Study Notes On Trains" in out  # the deterministic engine ran
        assert "⚠️" in dlg.status_label.text()
        assert dlg.save_btn.isEnabled()

    def test_llm_unchecked_runs_instant_path(self, monkeypatch, tmp_path):
        dlg, app, rec, _mod = self._make(monkeypatch, tmp_path)
        dlg.llm_chk.setChecked(False)
        dlg.text_input.setPlainText(
            "<div>Study Notes On Trains</div>\n\nRailways changed the world.\n"
        )
        dlg._on_process()  # synchronous — no worker
        assert dlg._worker is None or not dlg._worker.is_running()
        out = dlg.output_preview.toPlainText()
        assert "## Study Notes On Trains" in out
        assert dlg.status_label.text().startswith("✅")
        assert rec.calls == []

    def test_model_row_wiring(self, monkeypatch, tmp_path):
        dlg, _app, _rec, _mod = self._make(monkeypatch, tmp_path)
        assert dlg.model_combo.count() >= 1
        dlg.llm_chk.setChecked(False)
        assert not dlg.model_combo.isEnabled()
        dlg.llm_chk.setChecked(True)
        assert dlg.model_combo.isEnabled()


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTranslationFallbackResolution:
    """The dialog's active-LLM fallback resolution (no HTTP — the combo
    list is simulated via _installed_models)."""

    def _make(self, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as tr_mod

        dlg = tr_mod.TranslationServiceDialog(_StubController())
        return dlg, app, tr_mod

    def test_no_dedicated_model_flags_fallback(self, monkeypatch):
        dlg, _app, _tr = self._make(monkeypatch)
        # Simulate: Ollama unreachable → no dedicated model in the combo.
        dlg._installed_models = []
        dlg.model_combo.clear()
        dlg.model_combo.addItem("translategemma-12b  (Ollama unreachable)", "translategemma-12b")

        from utils.settings import Settings

        # V0.6.6 (review-loop): snapshot/restore — restoring to {} (not
        # None) left a truthy-for-__new__ empty dict as the global
        # Settings() for the rest of the session (every .get() → None;
        # the 15th baseline failure — test_incremental_chapter_save_
        # default_true — was the first victim).
        _prev_override = Settings._test_override
        Settings._test_override = {
            "summarisation.provider": "llamacpp",
            "summarisation.model": "active-model-x",
            "quick_services.defaults.summarize_model": "",
        }
        try:
            dlg._collect_options()
            assert dlg._active_llm_fallback is True
            assert dlg._resolved_model == "active-model-x"
            assert "llamacpp" in dlg._active_llm_info
        finally:
            Settings._test_override = _prev_override

    def test_dedicated_model_present_no_fallback(self, monkeypatch):
        dlg, _app, _tr = self._make(monkeypatch)
        dlg._installed_models = ["translategemma-12b-it.Q4_K_M:latest", "llama3.1:8b"]
        dlg.model_combo.clear()
        dlg.model_combo.addItem(
            "translategemma-12b-it.Q4_K_M:latest", "translategemma-12b-it.Q4_K_M:latest"
        )

        from utils.settings import Settings

        _prev_override = Settings._test_override
        Settings._test_override = {"summarisation.provider": "llamacpp"}
        try:
            dlg._collect_options()
            assert dlg._active_llm_fallback is False
        finally:
            Settings._test_override = _prev_override

    def test_real_installed_pick_survives_fallback(self, monkeypatch):
        dlg, _app, _tr = self._make(monkeypatch)
        # Healthy Ollama with NO translation model; combo auto-picked the
        # first installed one — the user's real model choice stays.
        dlg._installed_models = ["llama3.1:8b"]
        dlg.model_combo.clear()
        dlg.model_combo.addItem("llama3.1:8b", "llama3.1:8b")
        dlg.model_combo.setCurrentIndex(0)

        dlg._collect_options()
        assert dlg._active_llm_fallback is True
        assert dlg._resolved_model == "llama3.1:8b"


# ═══════════════════════════════════════════════════════════════════════
# Live-LLM leg (deselected by default: -m 'not live_llm')
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.live_llm
class TestStylerLiveThroughShim:
    """The styler pipeline through the real provider at the :3031 shim
    (provider=llamacpp → OpenAI-compat transport). The user's exact
    scenario: a raw Persian article with no headings → real title +
    real section headings + Obsidian note."""

    _SHIM = "http://localhost:3031"

    def test_persian_article_gets_real_structure(self):
        import requests

        try:
            requests.get(f"{self._SHIM}/health", timeout=3)
        except Exception:
            pytest.skip("shim :3031 not running")

        from core.llm.llm_provider import create_provider
        from core.summarisation.markdown_styler import style_markdown_llm
        from utils.settings import Settings

        s = Settings()
        provider = create_provider(
            provider="llamacpp", settings=s, log_callback=lambda msg, level="INFO": None
        )

        article = (
            "گاهی ممکن است نرم‌افزاری که فعالیت سیستم را تغییر می‌دهد باعث اختلال در "
            "همگام‌سازی کلود استیم شود.\n\n"
            "چگونه بررسی کنیم که از کلود استیم استفاده می‌کنیم؟\n\n"
            "وارد Steam Library شوید و روی بازی راست کلیک کنید.\n\n"
            "چگونه کلود استیم را فعال یا غیرفعال کنیم؟\n\n"
            "در صفحه Properties می‌توانید تیک Steam Cloud را تغییر دهید."
        )

        def llm_call(prompt: str) -> str:
            return provider.complete_streaming(
                prompt=prompt, temperature=0.2, max_tokens=6144, model="glm-4-plus"
            )

        result = style_markdown_llm(article, llm_call)
        assert result is not None, "live scan must succeed"
        note, structure = result
        assert structure["title"].strip()
        assert "Untitled" not in structure["title"]
        assert len(structure["sections"]) >= 2
        assert "## " in note
