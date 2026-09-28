"""V0.6.0 (the dedicated-tools verification campaign) — Tool 2: the
Summarization service (standalone path), end-to-end.

Inventory + trace (evidence-first):
- Card: ``summarization`` — ``ui_qt/views/tool_dashboard.py:41`` TOOL_CARDS
  row 1 (PROCESS, entry at :51-58).
- Routing: ``ui_qt/views/convert_view.py:166-172`` ``_on_tool_clicked`` →
  ``SummarizationServiceDialog`` via the ``base_dialog`` facade.
- Dialog: ``ui_qt/views/service_dialogs/dialogs/summarization_service_dialog.py``
  (the V18.20.4.6 O-b2 split; 1026 lines pre-V0.6.0). The STANDALONE
  service path — the pipeline (``core/pipeline/``) is verified separately
  (V0.5.15-20) and is NOT re-verified here. Entrypoints:
  ``_do_summarize`` :678 (validation + SimpleWorker spawn :801),
  ``_summarize_work`` :821 (widget-free worker body: Ollama pre-flight
  :839 → per-input loop :877 → ``write_output`` :949),
  ``_on_summarize_finished`` :988 (modal + settings persistence),
  ``_call_llm`` :590 (``create_provider`` + ``complete_streaming``),
  ``_build_prompt`` :545 (``PromptManager.render("default", ...)``),
  ``_get_input_text`` / text-length gate :742.
- Service layer: ``core/summarisation/`` (prompt_manager, response_parser)
  + ``core/outputs/service_formatters.write_output`` — the dialog's
  delegates, characterized at Layer 1/2 through the dialog's own call
  sites.
- Existing coverage: source-pin only (test_v182045_p4a / test_v182046_p5
  assert the worker wiring via AST) — ZERO functional tests before this
  file.

Layers (house UI-test pattern, cf. test_v0600_tool_cutter_e2e):
1. Pure characterization: ``_build_prompt`` (prompt contract + quality →
   max_tokens), ``parse_response`` / ``strip_thinking`` (the dialog's LLM
   output parser), ``_ollama_base_url`` normalization.
2. Service-level: LIVE LLM through the real zai-llamacpp shim (:3031,
   model ``glm-4-plus``) via the dialog's actual ``_call_llm`` path with
   the real Settings DI hook (``Settings._test_override`` — the
   repeatability_run.py pattern); plus deterministic ``_summarize_work``
   drives with a fake ``_call_llm`` (output naming, formats, guards,
   defect regressions).
3. Dialog-level drive: the real SimpleWorker QThread + queued signals +
   ``_on_summarize_finished`` on the main thread, ``_show_success_modal``
   monkeypatched (msg.exec() would block headless), plus one LIVE
   end-to-end drive on the shim.

Live-LLM volume: 3 tests hit the shim (one Layer-2 call + two Layer-3
drives); all are gated on the shim health check so the suite stays green
when the shim is down.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Layer 0: availability gates ─────────────────────────────────────────────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _docx_available() -> bool:
    try:
        import docx  # noqa: F401

        return True
    except Exception:
        return False


def _reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401

        return True
    except Exception:
        return False


_SHIM_URL = "http://localhost:3031/v1"
_SHIM_BASE = "http://localhost:3031"


def _shim_live() -> bool:
    """Health-check the zai-llamacpp shim (the live-LLM gate)."""
    try:
        import requests

        sess = requests.Session()
        sess.trust_env = False
        return bool(sess.get("http://localhost:3031/health", timeout=2).ok)
    except Exception:
        return False


# ── Fixtures / helpers ──────────────────────────────────────────────────────

_DEAD_ENDPOINT = "http://127.0.0.1:1"  # instant connection-refused, hermetic
_MODEL = "glm-4-plus"

# Content-agnostic two-paragraph input (Rule 1: no book/author/domain text).
TEXT = (
    "Bees pollinate a large share of flowering plants, transferring pollen "
    "as they forage for nectar. Their activity supports both wild ecosystems "
    "and agricultural crops.\n\n"
    "Honeybee colonies divide labor among a queen, workers, and drones. "
    "Workers perform successive roles during their lifetime, from nursing "
    "brood to foraging in the field, and communicate food locations through "
    "dance movements."
)

_CANNED_XML = (
    "<executive_summary>The material states a main claim and a supporting "
    "elaboration across two paragraphs of generic reference text.</executive_summary>\n"
    "<bullet_points>\n"
    "- First key takeaway derived from the material.\n"
    "- Second key takeaway derived from the material.\n"
    "</bullet_points>\n"
    "<thorough_summary>A detailed restatement covering both paragraphs, their "
    "relationship, and the stated conclusions.</thorough_summary>"
)


class _StubController:
    """The dialog only stores the controller (grep: self.controller :83 only)."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


class _TestSettings:
    """Deterministic offline Settings (real ``Settings._test_override`` DI
    hook — the scripts/repeatability_run.py pattern). Records ``set``/``save``
    so the finished-handler's persistence can be asserted."""

    def __init__(self, values: dict | None = None):
        self._values = {
            "summarisation.provider": "ollama",
            "summarisation.endpoint": _DEAD_ENDPOINT,
            "summarisation.model": "",
            "summarisation.temperature": 0.6,
            "quick_services.defaults.summarize_model": "",
            "quick_services.defaults.summarize_quality": "standard",
            "quick_services.defaults.summarize_format": ".md",
            "quick_services.defaults.summarize_obsidian": False,
        }
        if values:
            self._values.update(values)
        self.set_calls: list[tuple[str, object]] = []
        self.saved = False

    def get(self, key: str, default=None):
        return self._values.get(key, default)

    def set(self, key: str, value) -> None:
        self._values[key] = value
        self.set_calls.append((key, value))

    def save(self) -> bool:
        self.saved = True
        return True

    def get_ollama_url(self) -> str:
        return str(self._values.get("summarisation.endpoint", _DEAD_ENDPOINT))


def _install_settings(values: dict | None = None) -> _TestSettings:
    from utils.settings import Settings

    ts = _TestSettings(values)
    Settings._test_override = ts  # type: ignore[assignment]
    return ts


def _fake_llm(canned: str = _CANNED_XML, calls: list | None = None, err: str | None = None):
    """A deterministic stand-in for the dialog's ``_call_llm`` instance method."""

    def _f(model, prompt, max_tokens, temp, report=None):
        if calls is not None:
            calls.append((model, prompt, max_tokens, temp))
        if err is not None:
            return None, err
        return canned, None

    return _f


def _make_dialog(controller=None):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
        SummarizationServiceDialog,
    )

    return SummarizationServiceDialog(
        controller if controller is not None else _StubController()
    ), app


def _spin_until_done(app, dlg, timeout_s: float = 30.0) -> bool:
    """Process events until the action button leaves ``Processing…``.

    NOTE: the dialog's init + model refresh set ⚠️/✅ statuses BEFORE any run,
    so status-prefix waiting (the cutter pattern) is unusable here — the
    button text is the reliable completion signal (``Close`` on success,
    ``Summarize`` on failure).
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if dlg.action_btn.text() != "Processing…":
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(autouse=True)
def _hermetic_env():
    """Offline Settings override for every test (restored on teardown)."""
    from utils.settings import Settings

    prev_override = Settings._test_override
    Settings._test_override = _TestSettings()  # type: ignore[assignment]
    yield
    Settings._test_override = prev_override


# ── Layer 1: pure characterization ──────────────────────────────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestBuildPromptCharacterization:
    """``_build_prompt`` — the dialog's PromptManager delegation (V13.25.0)."""

    def _build(self, quality: str, text: str = TEXT):
        from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
            SummarizationServiceDialog,
        )

        return SummarizationServiceDialog._build_prompt(text, quality)

    def test_prompt_contains_input_and_xml_contract(self):
        prompt, _ = self._build("standard")
        assert TEXT[:60] in prompt  # the source text rides the prompt (fenced)
        assert "<executive_summary>" in prompt
        assert "<bullet_points>" in prompt
        assert "<thorough_summary>" in prompt

    def test_prompt_wraps_untrusted_source(self):
        # V18.2.21 prompt-injection defense: the text variable is fenced.
        prompt, _ = self._build("standard")
        assert "<untrusted_source>" in prompt

    def test_quality_maps_to_max_tokens(self):
        assert self._build("fast")[1] == 1024
        assert self._build("standard")[1] == 2048
        assert self._build("thorough")[1] == 4096
        assert self._build("unknown-quality")[1] == 2048

    def test_fallback_prompt_when_render_returns_none(self, monkeypatch):
        from core.summarisation.prompt_manager import PromptManager

        monkeypatch.setattr(PromptManager, "render", lambda self, *a, **k: None, raising=True)
        prompt, max_tokens = self._build("fast")
        assert "expert summariser" in prompt
        assert "Pasted Text" in prompt
        assert TEXT[:60] in prompt
        assert "<executive_summary>" in prompt
        assert max_tokens == 1024


class TestResponseParsingCharacterization:
    """``parse_response`` / ``strip_thinking`` — what the dialog feeds every
    LLM response through (``_summarize_work`` → ``parse_response(raw,
    academic_rigor=False)``). Pure functions, no Qt."""

    def test_xml_tagged_response_parses_into_sections(self):
        from core.summarisation.response_parser import parse_response

        parsed = parse_response(_CANNED_XML, academic_rigor=False)
        assert "main claim" in parsed["executive_summary"]
        assert parsed["bullet_points"] == [
            "First key takeaway derived from the material.",
            "Second key takeaway derived from the material.",
        ]
        assert "detailed restatement" in parsed["thorough_summary"]

    def test_thinking_block_stripped_before_parsing(self):
        from core.summarisation.response_parser import parse_response

        raw = "<think>secret scratchpad</think>\n" + _CANNED_XML
        parsed = parse_response(raw, academic_rigor=False)
        assert "secret scratchpad" not in parsed["executive_summary"]
        assert "main claim" in parsed["executive_summary"]

    def test_strip_thinking_removes_block(self):
        from core.summarisation.response_parser import strip_thinking

        assert strip_thinking("<think>abc</think>Visible text.") == "Visible text."

    def test_plain_prose_still_salvages_content(self):
        from core.summarisation.response_parser import parse_response

        parsed = parse_response(
            "One plain paragraph of prose without any markup at all.", academic_rigor=False
        )
        combined = " ".join(
            [
                parsed["executive_summary"],
                " ".join(parsed["bullet_points"]),
                parsed["thorough_summary"],
            ]
        )
        assert "plain paragraph" in combined


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestOllamaBaseUrlNormalization:
    """``_ollama_base_url`` — the dialog's endpoint reader (:311-326)."""

    def test_strips_v1_suffix(self):
        from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
            SummarizationServiceDialog,
        )

        _install_settings({"summarisation.endpoint": f"{_SHIM_BASE}/v1"})
        assert SummarizationServiceDialog._ollama_base_url() == _SHIM_BASE

    def test_empty_and_missing_fall_back_to_default(self):
        from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
            SummarizationServiceDialog,
        )
        from utils.settings import Settings

        ts = _TestSettings({"summarisation.endpoint": ""})  # set-but-blank
        Settings._test_override = ts  # type: ignore[assignment]
        assert SummarizationServiceDialog._ollama_base_url() == "http://localhost:11434"
        del ts._values["summarisation.endpoint"]  # key absent → default param
        assert SummarizationServiceDialog._ollama_base_url() == "http://localhost:11434"

    def test_trailing_slash_rstripped(self):
        from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
            SummarizationServiceDialog,
        )

        _install_settings({"summarisation.endpoint": "http://host.example:11434/"})
        assert SummarizationServiceDialog._ollama_base_url() == "http://host.example:11434"


# ── Layer 2 (LIVE): the dialog's real LLM call path on the shim ─────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _shim_live(), reason="zai-llamacpp shim :3031 not reachable")
class TestCallLlmLiveShim:
    """``_call_llm`` → ``create_provider`` → ``complete_streaming`` on the
    real shim, driven through the real Settings DI hook (headless settings
    injection, the repeatability_run.py precedent)."""

    _LIVE = {
        "summarisation.provider": "llamacpp",
        "summarisation.llamacpp_base_url": _SHIM_URL,
        "summarisation.llamacpp_model": _MODEL,
        "summarisation.model": _MODEL,
        "summarisation.temperature": 0.6,
    }

    def test_call_llm_through_real_shim_returns_summary(self):
        _install_settings(self._LIVE)
        dlg, _app = _make_dialog()
        prompt, max_tokens = dlg._build_prompt(TEXT, "fast")
        text, err = dlg._call_llm(_MODEL, prompt, max_tokens, 0.6, report=lambda pct, msg: None)
        assert err is None, err
        assert text and len(text.strip()) >= 100, repr(text[:200]) if text else None
        assert "summary" in text.lower()


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestCallLlmErrorSurface:
    """S3 (V0.6.0) pin: the empty-response error must name the configured
    provider, not hardcode Ollama advice (a refused llama-server lands here
    because ``complete_streaming`` returns None on transport failure)."""

    def test_dead_backend_error_names_provider(self):
        _install_settings(
            {
                "summarisation.provider": "llamacpp",
                "summarisation.llamacpp_base_url": f"{_DEAD_ENDPOINT}/v1",
                "summarisation.llamacpp_model": "probe-model",
            }
        )
        dlg, _app = _make_dialog()
        text, err = dlg._call_llm(
            "probe-model", "Summarise this short text.", 64, 0.6, report=lambda p, m: None
        )
        assert text is None
        assert err is not None
        assert "<b>llamacpp</b>" in err
        assert "ollama" not in err.lower()


# ── Layer 2 (deterministic): _summarize_work through a fake _call_llm ──────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestSummarizeWorkServiceLevel:
    """The widget-free worker body — output naming, formats, guards, defect
    regressions — with ``_call_llm`` faked (no live LLM)."""

    _VALUES = {"summarisation.model": "fake-model"}

    def _work(self, tmp_path, values=None, llm=None, inputs=None, **kw):
        _install_settings({**self._VALUES, **(values or {})})
        dlg, _app = _make_dialog()
        if llm is not None:
            dlg._call_llm = llm
        default_inputs = [("pasted", TEXT)]
        return dlg._summarize_work(
            inputs if inputs is not None else default_inputs,
            kw.get("is_multi", False),
            kw.get("out_folder"),
            kw.get("out_path", str(tmp_path / "summary.md")),
            kw.get("model", "fake-model"),
            kw.get("model_data", "__default__"),
            kw.get("quality", "standard"),
            kw.get("ext", ".md"),
            kw.get("obsidian", False),
            kw.get("temp", 0.6),
        )

    def test_single_paste_writes_md_with_sections(self, tmp_path):
        out = tmp_path / "summary.md"
        result = self._work(tmp_path, out_path=str(out), llm=_fake_llm())
        assert result["total"] == 1
        assert result["persist_model"] is False  # __default__ never persists
        assert result["file_arg"] == str(out)
        assert len(result["results"]) == 1 and result["results"][0].startswith("✅")
        content = out.read_text(encoding="utf-8")
        assert "## Executive Summary" in content
        assert "## Key Takeaways" in content
        assert "## Detailed Summary" in content
        assert "- First key takeaway" in content
        assert "\n\n---\n\n" in content  # the section separator

    def test_fast_quality_omits_detailed_section(self, tmp_path):
        out = tmp_path / "fast.md"
        self._work(tmp_path, out_path=str(out), quality="fast", llm=_fake_llm())
        content = out.read_text(encoding="utf-8")
        assert "## Executive Summary" in content
        assert "## Detailed Summary" not in content

    def test_plain_prose_response_still_writes_output(self, tmp_path):
        out = tmp_path / "prose.md"
        result = self._work(
            tmp_path, out_path=str(out), llm=_fake_llm(canned="Just a plain prose answer.")
        )
        assert result["results"][0].startswith("✅")
        assert out.exists() and out.read_text(encoding="utf-8").strip()

    def test_out_path_directory_auto_names(self, tmp_path):
        folder = tmp_path / "outdir"
        folder.mkdir()
        result = self._work(tmp_path, out_path=str(folder), llm=_fake_llm())
        auto = folder / "pasted_standard_summary.md"
        assert auto.exists()
        assert result["file_arg"] == str(folder)

    def test_user_typed_docx_extension_wins(self, tmp_path):
        # V11.67.0: the user's typed extension overrides the combo's format.
        out = tmp_path / "typed.docx"
        self._work(tmp_path, out_path=str(out), ext=".md", llm=_fake_llm())
        assert out.exists()
        assert out.read_bytes()[:2] == b"PK"  # a real docx (zip) file

    @pytest.mark.skipif(not _reportlab_available(), reason="reportlab unavailable")
    def test_pdf_format_written(self, tmp_path):
        out = tmp_path / "summary.pdf"
        result = self._work(tmp_path, out_path=str(out), ext=".pdf", llm=_fake_llm())
        assert result["results"][0].startswith("✅")
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_multi_file_auto_names_each(self, tmp_path):
        folder = tmp_path / "multi"
        folder.mkdir()
        inputs = [("fileA", TEXT), ("fileB", TEXT)]
        result = self._work(
            tmp_path,
            is_multi=True,
            out_folder=str(folder),
            inputs=inputs,
            llm=_fake_llm(),
        )
        assert result["total"] == 2
        assert (folder / "fileA_standard_summary.md").exists()
        assert (folder / "fileB_standard_summary.md").exists()
        assert result["file_arg"] == str(folder)

    def test_obsidian_wrap_applied_for_md(self, tmp_path):
        out = tmp_path / "obs.md"
        self._work(tmp_path, out_path=str(out), obsidian=True, llm=_fake_llm())
        content = out.read_text(encoding="utf-8")
        assert content.startswith("---")  # YAML front-matter
        assert "> [!" in content  # Obsidian callout

    def test_model_missing_for_ollama_provider_blocks_run(self, tmp_path):
        # provider=ollama + a reachable Ollama that does NOT serve the model
        # → the pre-flight hard-stop (the intended V11.20 behavior).
        calls: list = []
        _install_settings({**self._VALUES})
        dlg, _app = _make_dialog()
        dlg._call_llm = _fake_llm(calls=calls)
        dlg._fetch_installed_models = lambda timeout=5.0: ["some-other-model"]
        result = dlg._summarize_work(
            [("pasted", TEXT)],
            False,
            None,
            str(tmp_path / "out.md"),
            "fake-model",
            "__default__",
            "standard",
            ".md",
            False,
            0.6,
        )
        assert result.get("model_missing") is True
        assert "fake-model" in result["error_html"]
        assert "ollama pull fake-model" in result["error_html"]
        assert not calls  # no LLM call happened
        assert not (tmp_path / "out.md").exists()

    def test_s1_preflight_skipped_for_non_ollama_providers(self, tmp_path):
        """V0.6.0 (S1 regression): the Ollama /api/tags pre-flight must NOT
        gate non-Ollama providers. Pre-fix, a healthy llama.cpp backend
        hard-stopped as ``model_missing`` whenever the legacy
        ``summarisation.endpoint`` key pointed at any non-Ollama server (or
        an Ollama hosting other models) — live-reproduced on the shim."""
        fetch_calls: list = []
        llm_calls: list = []
        _install_settings({**self._VALUES, "summarisation.provider": "llamacpp"})
        dlg, _app = _make_dialog()
        dlg._call_llm = _fake_llm(calls=llm_calls)

        def _fetch(timeout=5.0):
            fetch_calls.append(timeout)
            return ["some-other-model"]  # would hard-stop if consulted

        dlg._fetch_installed_models = _fetch
        out = tmp_path / "fixed.md"
        result = dlg._summarize_work(
            [("pasted", TEXT)],
            False,
            None,
            str(out),
            "fake-model",
            "__default__",
            "standard",
            ".md",
            False,
            0.6,
        )
        assert fetch_calls == []  # the pre-flight was skipped entirely
        assert len(llm_calls) == 1
        assert result.get("model_missing") is None
        assert result["results"][0].startswith("✅")
        assert out.exists()

    def test_llm_error_recorded_and_404_breaks_batch(self, tmp_path):
        err = "❌ LLM call failed: HTTPError: 404 not found"
        result = self._work(
            tmp_path,
            is_multi=True,
            out_folder=str(tmp_path),
            inputs=[("a", TEXT), ("b", TEXT)],
            llm=_fake_llm(err=err),
        )
        assert len(result["results"]) == 1  # the 404 break stops the batch
        assert result["results"][0].startswith("❌ a →")
        assert not (tmp_path / "a_standard_summary.md").exists()

    def test_non_404_error_continues_batch(self, tmp_path):
        err = "❌ LLM call failed: ValueError: bad temperature"
        result = self._work(
            tmp_path,
            is_multi=True,
            out_folder=str(tmp_path),
            inputs=[("a", TEXT), ("b", TEXT)],
            llm=_fake_llm(err=err),
        )
        assert len(result["results"]) == 2
        assert all(r.startswith("❌") for r in result["results"])

    def test_worker_body_takes_plain_values_only(self):
        # W-b5 contract spot-check: _summarize_work's signature accepts only
        # plain captured values (no widget reads inside the thread).
        import inspect

        from ui_qt.views.service_dialogs.dialogs.summarization_service_dialog import (
            SummarizationServiceDialog,
        )

        params = list(inspect.signature(SummarizationServiceDialog._summarize_work).parameters)
        assert params == [
            "self",
            "inputs",
            "is_multi",
            "out_folder",
            "out_path",
            "model",
            "model_data",
            "quality",
            "ext",
            "obsidian",
            "temp",
            "report",
        ]


# ── Layer 3: dialog-level drive (real SimpleWorker, fake LLM) ───────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDialogDriveFakeLlm:
    """Full dialog drives through the real worker thread — deterministic
    because ``_call_llm`` is faked on the instance; the worker, queued
    signals, finished handler and modal all run for real."""

    def _drive(self, tmp_path, monkeypatch, values=None, out_name="driven.md"):
        import ui_qt.views.service_dialogs.dialogs.summarization_service_dialog as summ_mod

        recorded: list[tuple] = []
        monkeypatch.setattr(
            summ_mod,
            "_show_success_modal",
            lambda parent, title, message, file_path=None, on_try_another=None: recorded.append(
                (title, message, file_path)
            ),
        )
        # V0.6.0: provider=llamacpp (NOT ollama) so the S1 pre-flight skip
        # applies — otherwise the worker QThread makes a real network call
        # to the default Ollama endpoint, which raced urllib3 pool teardown
        # and segfaulted the interpreter (observed in the full-suite run).
        # The pre-flight contract itself has its own dedicated tests above.
        _install_settings(
            {**{"summarisation.model": "fake-model", "summarisation.provider": "llamacpp"}, **(values or {})}
        )
        dlg, app = _make_dialog()
        dlg._call_llm = _fake_llm()
        out = tmp_path / out_name
        dlg.text_input.setPlainText(TEXT)
        dlg.out_edit.setText(str(out))
        return dlg, app, out, recorded

    def test_full_dialog_flow_lands_success(self, tmp_path, monkeypatch):
        dlg, app, out, recorded = self._drive(tmp_path, monkeypatch)
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        assert dlg.status_label.text().startswith("✅"), dlg.status_label.text()
        content = out.read_text(encoding="utf-8")
        assert "## Executive Summary" in content
        assert len(content) > 100
        assert recorded and recorded[0][0] == "Σ Summarization Complete"
        assert recorded[0][2] == str(out)
        assert dlg.action_btn.text() == "Close"
        assert not dlg.again_btn.isHidden()  # surfaced after a run (V11.18)

    def test_persist_model_when_concrete_model_picked(self, tmp_path, monkeypatch):
        from utils.settings import Settings

        dlg, app, out, _rec = self._drive(tmp_path, monkeypatch)
        # The finished handler reads Settings() AT CALL TIME — swap in the
        # recording override now (construction already happened in _drive).
        ts = _TestSettings({"summarisation.model": "fake-model"})
        Settings._test_override = ts  # type: ignore[assignment]
        dlg.model_combo.setCurrentIndex(1)  # the concrete "fake-model" item
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        assert dlg.status_label.text().startswith("✅")
        assert ("summarisation.model", "fake-model") in ts.set_calls
        assert ts.saved is True

    def test_guards_warn_without_spawning_worker(self, tmp_path, monkeypatch):
        _install_settings({"summarisation.model": ""})  # no model at all
        dlg, _app = _make_dialog()
        dlg._call_llm = _fake_llm()
        dlg.text_input.setPlainText(TEXT)
        dlg.out_edit.setText(str(tmp_path / "o.md"))
        dlg._do_summarize()
        assert dlg.status_label.text().startswith("⚠️ Please pick or type")
        assert dlg._worker is None

        _install_settings({"summarisation.model": "fake-model"})
        dlg2, _app = _make_dialog()
        dlg2._call_llm = _fake_llm()
        dlg2.text_input.setPlainText("")  # no text
        dlg2.out_edit.setText(str(tmp_path / "o.md"))
        dlg2._do_summarize()
        assert dlg2.status_label.text().startswith("⚠️ Please paste text")
        assert dlg2._worker is None

        dlg3, _app = _make_dialog()
        dlg3._call_llm = _fake_llm()
        dlg3.text_input.setPlainText("Too short.")  # < 100 chars gate
        dlg3.out_edit.setText(str(tmp_path / "o.md"))
        dlg3._do_summarize()
        assert dlg3.status_label.text().startswith("⚠️ Text too short")
        assert dlg3._worker is None

        dlg4, _app = _make_dialog()
        dlg4._call_llm = _fake_llm()
        dlg4.text_input.setPlainText(TEXT)
        dlg4.out_edit.setText("")  # no output path
        dlg4._do_summarize()
        assert dlg4.status_label.text().startswith("⚠️ Please choose where to save")
        assert dlg4._worker is None

    def test_multi_tab_guards(self, tmp_path, monkeypatch):
        _install_settings({"summarisation.model": "fake-model"})
        dlg, _app = _make_dialog()
        dlg._call_llm = _fake_llm()
        dlg.tabs.setCurrentIndex(1)
        dlg._do_summarize()  # no files
        assert dlg.status_label.text().startswith("⚠️ Add at least one file")
        assert dlg._worker is None

        dlg._files = [str(tmp_path / "missing.txt")]  # does not exist
        dlg.out_edit.setText(str(tmp_path))
        dlg._do_summarize()
        assert dlg.status_label.text().startswith("❌ Cannot read")
        assert dlg._worker is None

        empty = tmp_path / "empty.txt"
        empty.write_text("   \n \n", encoding="utf-8")
        dlg._files = [str(empty)]
        dlg._do_summarize()
        assert dlg.status_label.text().startswith("⚠️ None of the selected files")
        assert dlg._worker is None

    def test_multi_file_flow_auto_names_outputs(self, tmp_path, monkeypatch):
        dlg, app, _out, recorded = self._drive(tmp_path, monkeypatch)
        f1 = tmp_path / "notesA.txt"
        f2 = tmp_path / "notesB.txt"
        f1.write_text(TEXT, encoding="utf-8")
        f2.write_text(TEXT, encoding="utf-8")
        folder = tmp_path / "batch"
        folder.mkdir()
        dlg.tabs.setCurrentIndex(1)
        dlg._files = [str(f1), str(f2)]
        dlg.out_edit.setText(str(folder))
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        assert dlg.status_label.text().startswith("Done! 2 file(s) processed:")
        assert (folder / "notesA_standard_summary.md").exists()
        assert (folder / "notesB_standard_summary.md").exists()
        assert recorded and recorded[0][2] == str(folder)

    def test_reentrancy_guard_while_running(self, tmp_path, monkeypatch):
        dlg, _app, _out, _rec = self._drive(tmp_path, monkeypatch)

        class _RunningWorker:
            def is_running(self):
                return True

        running = _RunningWorker()
        dlg._worker = running
        dlg._do_summarize()
        assert dlg.status_label.text().startswith("⏳ Already summarizing")
        assert dlg._worker is running  # no second worker was spawned

    def test_model_missing_error_visible_after_refresh(self, tmp_path, monkeypatch):
        """V0.6.0 (S2 regression): the model_missing error must remain
        visible — ``_refresh_models`` used to clobber it with its own
        reachability status inside the same handler (live-reproduced: the
        user only ever saw 'Ollama is running but has no models installed')."""
        import ui_qt.views.service_dialogs.dialogs.summarization_service_dialog as summ_mod

        monkeypatch.setattr(summ_mod, "_show_success_modal", lambda *a, **k: None)
        _install_settings({"summarisation.model": "wanted-model"})
        dlg, app = _make_dialog()
        dlg._call_llm = _fake_llm()
        dlg._fetch_installed_models = lambda timeout=5.0: ["other-model"]
        out = tmp_path / "missing.md"
        dlg.text_input.setPlainText(TEXT)
        dlg.out_edit.setText(str(out))
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        # The actionable error survives the combo refresh (the label renders
        # RichText — the model name is wrapped in <b>):
        assert dlg.status_label.text().startswith("❌ Model '<b>wanted-model</b>' is not installed")
        assert "ollama pull wanted-model" in dlg.status_label.text()
        assert dlg.action_btn.text() == "Summarize" and dlg.action_btn.isEnabled()
        assert not out.exists()

    def test_worker_exception_lands_error_status(self, tmp_path, monkeypatch):
        import ui_qt.views.service_dialogs.dialogs.summarization_service_dialog as summ_mod

        monkeypatch.setattr(summ_mod, "_show_success_modal", lambda *a, **k: None)
        _install_settings({"summarisation.model": "fake-model"})
        dlg, app = _make_dialog()

        def _boom(model, prompt, max_tokens, temp, report=None):
            raise RuntimeError("worker-body boom")

        dlg._call_llm = _boom
        out = tmp_path / "boom.md"
        dlg.text_input.setPlainText(TEXT)
        dlg.out_edit.setText(str(out))
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        assert dlg.status_label.text().startswith("❌ Error:")
        assert "worker-body boom" in dlg.status_label.text()
        assert dlg.action_btn.text() == "Summarize" and dlg.action_btn.isEnabled()
        assert not out.exists()

    def test_try_another_resets_the_dialog(self, tmp_path, monkeypatch):
        dlg, app, out, _rec = self._drive(tmp_path, monkeypatch)
        dlg._do_summarize()
        assert _spin_until_done(app, dlg), dlg.status_label.text()
        assert dlg.action_btn.text() == "Close"

        dlg._on_try_another()
        assert dlg.text_input.toPlainText() == ""
        assert dlg.out_edit.text() == ""
        assert dlg._files == []
        assert dlg.action_btn.text() == "Summarize" and dlg.action_btn.isEnabled()
        assert dlg.again_btn.isHidden()
        assert dlg.status_label.text().startswith("Ready for the next file")


# ── Layer 3 (LIVE): full dialog drive through the real shim ─────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _shim_live(), reason="zai-llamacpp shim :3031 not reachable")
class TestDialogDriveLiveShim:
    """The full production path: paste text → Summarize → real SimpleWorker
    thread → real LlamaCppProvider streaming on the shim → parsed summary
    written to disk → success modal (recorded, never exec'd)."""

    _LIVE = {
        "summarisation.provider": "llamacpp",
        "summarisation.llamacpp_base_url": _SHIM_URL,
        "summarisation.llamacpp_model": _MODEL,
        "summarisation.model": _MODEL,
        "summarisation.temperature": 0.6,
    }

    def _drive_live(self, tmp_path, monkeypatch, values, out_name="live.md"):
        import ui_qt.views.service_dialogs.dialogs.summarization_service_dialog as summ_mod

        recorded: list[tuple] = []
        monkeypatch.setattr(
            summ_mod,
            "_show_success_modal",
            lambda parent, title, message, file_path=None, on_try_another=None: recorded.append(
                (title, message, file_path)
            ),
        )
        _install_settings(values)
        dlg, app = _make_dialog()
        out = tmp_path / out_name
        dlg.text_input.setPlainText(TEXT)
        dlg.out_edit.setText(str(out))
        return dlg, app, out, recorded

    def test_live_full_dialog_flow_produces_summary_file(self, tmp_path, monkeypatch):
        dlg, app, out, recorded = self._drive_live(tmp_path, monkeypatch, self._LIVE)
        dlg._do_summarize()
        assert _spin_until_done(app, dlg, timeout_s=300), dlg.status_label.text()
        assert dlg.status_label.text().startswith("✅"), dlg.status_label.text()
        content = out.read_text(encoding="utf-8")
        assert len(content) >= 200, content[:200]
        assert "## " in content  # the md assembly (exec/bullets/detailed sections)
        assert recorded and recorded[0][0] == "Σ Summarization Complete"
        assert recorded[0][2] == str(out)
        assert dlg.action_btn.text() == "Close"

    def test_s1_live_llamacpp_with_endpoint_at_same_server_succeeds(self, tmp_path, monkeypatch):
        """V0.6.0 (S1 live regression): provider=llamacpp with the legacy
        ``summarisation.endpoint`` pointing at the (non-Ollama) llama.cpp
        server — pre-fix this hard-stopped as ``model_missing`` (verified
        live before the fix); post-fix the run completes."""
        values = dict(self._LIVE)
        values["summarisation.endpoint"] = _SHIM_BASE
        dlg, app, out, _rec = self._drive_live(
            tmp_path, monkeypatch, values, out_name="live_endpoint.md"
        )
        dlg._do_summarize()
        assert _spin_until_done(app, dlg, timeout_s=300), dlg.status_label.text()
        assert dlg.status_label.text().startswith("✅"), dlg.status_label.text()
        assert out.exists() and len(out.read_text(encoding="utf-8")) >= 100
        assert dlg.action_btn.text() == "Close"
