"""V0.6.7 — the review-loop Loop-3 fixes. House 3-layer pattern
(test_v065_rtl_styler_translation.py is the reference; the per-fix ID
map lives in .review-loop/findings.md).

A5 — provider transport routing (the 4 bare requests.post sites):
  openai_compat_provider.complete / claude_provider.complete /
  ollama_provider.supports_vision + complete_with_image now route through
  ``session_for_url`` — the ONE routing rule (V18.20.4.11). The routing
  rule itself is pinned by tests/test_v1820411_p3_llm_transport.py
  (localhost → the proxy-immune no-proxy session, cloud → the
  proxy-trusting pooled session); these tests pin that the PROVIDERS
  actually go through the seam with the full URL — pre-fix, all four
  sites called bare ``requests.post`` (trust_env=True always), so a
  misconfigured HTTP_PROXY broke localhost FreeLLMAPI/Ollama calls.

  The two Ollama vision methods were 0%-covered before this file —
  their response parsing (mmproj/adapter detection, image b64 payload)
  is characterized here for the first time.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.llm.claude_provider import ClaudeProvider  # noqa: E402
from core.llm.ollama_provider import OllamaProvider  # noqa: E402
from core.llm.openai_compat_provider import OpenAICompatProvider  # noqa: E402


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(payload).encode() if payload is not None else text.encode()
    return r


# ── A5: ollama_provider.supports_vision + complete_with_image ──────────────


def _ollama_sess_patch(**post_kwargs):
    """Patch the Ollama transport seam (top-level session_for_url import in
    core.llm.ollama_provider — V0.6.7 A5) with a mock pooled session."""
    sess = MagicMock()
    sess.post = MagicMock(**post_kwargs)
    return patch("core.llm.ollama_provider.session_for_url", return_value=sess), sess


@pytest.fixture
def logs() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def ollama(logs) -> OllamaProvider:
    return OllamaProvider(
        model="vision-model",
        base_url="http://localhost:11434",
        timeout=30,
        retries=0,
        log_callback=lambda msg, level="INFO": logs.append((level, msg)),
    )


class TestSupportsVision:
    """V0.4.1 vision probe — first characterization (was 0% covered)."""

    def test_model_info_vision_key_true(self, ollama):
        patcher, _sess = _ollama_sess_patch(
            return_value=_resp(200, {"model_info": {"vision.encoder.context_length": 8192}})
        )
        with patcher:
            assert ollama.supports_vision() is True

    def test_model_info_mmproj_key_true(self, ollama):
        patcher, _sess = _ollama_sess_patch(
            return_value=_resp(200, {"model_info": {"general.mmproj": "v"}})
        )
        with patcher:
            assert ollama.supports_vision() is True

    def test_architecture_value_mentioning_vision_true(self, ollama):
        """Some Ollama versions store the projector type as a
        general.architecture VALUE (not key) — the val check catches it."""
        patcher, _sess = _ollama_sess_patch(
            return_value=_resp(200, {"model_info": {"general.architecture": "clip-vision"}})
        )
        with patcher:
            assert ollama.supports_vision() is True

    def test_projector_info_fallback_true(self, ollama):
        patcher, _sess = _ollama_sess_patch(
            return_value=_resp(
                200, {"model_info": {"general.architecture": "llama"}, "projector_info": {"k": 1}}
            )
        )
        with patcher:
            assert ollama.supports_vision() is True

    def test_plain_text_model_false(self, ollama):
        patcher, _sess = _ollama_sess_patch(
            return_value=_resp(200, {"model_info": {"general.architecture": "llama"}})
        )
        with patcher:
            assert ollama.supports_vision() is False

    def test_non_200_false(self, ollama):
        patcher, _sess = _ollama_sess_patch(return_value=_resp(404, {"error": "no"}))
        with patcher:
            assert ollama.supports_vision() is False

    def test_transport_error_false_fail_safe(self, ollama):
        """Fail-safe: if the probe can't confirm vision, don't attempt it."""
        patcher, _sess = _ollama_sess_patch(side_effect=requests.exceptions.ConnectionError("down"))
        with patcher:
            assert ollama.supports_vision() is False

    def test_routes_full_url_through_the_seam(self, ollama):
        """A5 pin: the probe goes through session_for_url with the full
        localhost URL (pre-fix: bare requests.post, proxy-hazard)."""
        patcher, sess = _ollama_sess_patch(return_value=_resp(200, {"model_info": {}}))
        with patcher:
            ollama.supports_vision()
        assert sess.post.call_args.args[0] == "http://localhost:11434/api/show"
        assert sess.post.call_args.kwargs["json"] == {"name": "vision-model"}
        assert sess.post.call_args.kwargs["timeout"] == 10


class TestCompleteWithImage:
    """V0.4.12 image call — first characterization (was 0% covered)."""

    def test_success_stripped(self, ollama):
        patcher, _sess = _ollama_sess_patch(return_value=_resp(200, {"response": "  hello  "}))
        with patcher:
            assert ollama.complete_with_image("describe", b"imgbytes") == "hello"

    def test_whitespace_only_response_none(self, ollama):
        patcher, _sess = _ollama_sess_patch(return_value=_resp(200, {"response": "   "}))
        with patcher:
            assert ollama.complete_with_image("p", b"x") is None

    def test_missing_response_key_none(self, ollama):
        patcher, _sess = _ollama_sess_patch(return_value=_resp(200, {"done": True}))
        with patcher:
            assert ollama.complete_with_image("p", b"x") is None

    def test_non_200_none(self, ollama):
        patcher, _sess = _ollama_sess_patch(return_value=_resp(500, {"error": "boom"}))
        with patcher:
            assert ollama.complete_with_image("p", b"x") is None

    def test_transport_error_none_logged(self, ollama, logs):
        patcher, _sess = _ollama_sess_patch(side_effect=requests.exceptions.Timeout("t"))
        with patcher:
            assert ollama.complete_with_image("p", b"x") is None
        assert any("vision call failed" in m for (_, m) in logs)

    def test_payload_image_b64_model_override_options(self, ollama):
        raw = b"\x89PNG-fake-bytes"
        patcher, sess = _ollama_sess_patch(return_value=_resp(200, {"response": "ok"}))
        with patcher:
            assert (
                ollama.complete_with_image(
                    "describe",
                    raw,
                    temperature=0.25,
                    max_tokens=123,
                    model="other-vl",
                )
                == "ok"
            )
        kwargs = sess.post.call_args.kwargs
        assert sess.post.call_args.args[0] == "http://localhost:11434/api/generate"
        assert kwargs["json"]["model"] == "other-vl"  # V0.4.12 override honored
        assert kwargs["json"]["prompt"] == "describe"
        assert kwargs["json"]["images"] == [base64.b64encode(raw).decode("utf-8")]
        assert kwargs["json"]["stream"] is False
        assert kwargs["json"]["options"] == {"temperature": 0.25, "num_predict": 123}
        assert kwargs["timeout"] == 30


# ── A5: openai_compat + claude routing pins (the localhost hazard case) ─────


class TestProviderSeamRouting:
    """The provider-level pin that complete() goes through session_for_url
    with the full URL. The URL→session routing itself (localhost → no-proxy
    session) is pinned in tests/test_v1820411_p3_llm_transport.py; these
    compose with it into the end-to-end guarantee."""

    def test_openai_compat_local_freellmapi_url_hits_the_seam(self):
        """THE A5 hazard: a localhost /v1 endpoint (FreeLLMAPI) behind a
        misconfigured HTTP_PROXY — pre-fix this bare requests.post call was
        routed through the proxy and broke."""
        p = OpenAICompatProvider(
            model="m",
            base_url="http://localhost:3031/v1",
            api_key="k",
            retries=0,
        )
        sess = MagicMock()
        sess.post = MagicMock(return_value=_resp(200, {"choices": [{"message": {"content": "x"}}]}))
        with patch("core.llm.openai_compat_provider.session_for_url", return_value=sess):
            assert p.complete("p") == "x"
        assert sess.post.call_args.args[0] == "http://localhost:3031/v1/chat/completions"

    def test_claude_url_hits_the_seam(self):
        p = ClaudeProvider(api_key="k", retries=0)
        sess = MagicMock()
        sess.post = MagicMock(return_value=_resp(200, {"content": [{"type": "text", "text": "x"}]}))
        with patch("core.llm.claude_provider.session_for_url", return_value=sess):
            assert p.complete("p") == "x"
        assert sess.post.call_args.args[0] == "https://api.anthropic.com/v1/messages"


# ── B4: the vision-keyword SSOT (model_taxonomy.VISION_MODEL_KEYWORDS) ──────


from core.llm.model_taxonomy import VISION_MODEL_KEYWORDS, is_vision_model  # noqa: E402


class TestIsVisionModel:
    """Layer 1 — the SSOT predicate (the union of the 3 drifted variants)."""

    @pytest.mark.parametrize(
        "name",
        [
            "minicpm-v",  # THE drift bug: classified TEXT by dependencies, listed by the OCR dialog
            "MiniCPM-V-2.6:latest",  # case-insensitive
            "qwen2.5-vl:7b",
            "llava:13b",
            "bakllava",
            "olmocr:latest",  # caught by both 'ocr' and 'olmo'
            "deepseek-ocr",
            "moondream2",
            "fuyu-8b",  # variant C family the llamacpp gate previously missed
            "kosmos-2",
            "florence-2",
            "GLM-OCR-Q8",  # caught by 'ocr'
            "mmproj-test",
            "multimodal-v1",
        ],
    )
    def test_vision_families_true(self, name):
        assert is_vision_model(name) is True

    @pytest.mark.parametrize(
        "name", ["llama3.1:8b", "gemma3:12b", "mistral:7b", "qwen3:8b", "codellama:13b"]
    )
    def test_text_families_false(self, name):
        assert is_vision_model(name) is False

    def test_empty_and_none_false(self):
        assert is_vision_model("") is False
        assert is_vision_model(None) is False

    def test_ssot_superset_of_every_legacy_variant(self):
        """The union policy pin: every keyword from each of the 3 legacy
        variants is present in the SSOT."""
        variant_a = ("vl", "vision", "deepseek-ocr", "llava", "bakllava", "ocr", "olmo")
        variant_b = (
            "vision",
            "vl",
            "vlm",
            "mmproj",
            "multimodal",
            "llava",
            "bakllava",
            "qwen-vl",
            "gemma-vl",
            "instruct-vision",
            "bonsai",
        )
        variant_c = (
            "ocr",
            "vision",
            "vl",
            "llava",
            "minicpm",
            "moondream",
            "bakllava",
            "llama-vision",
            "qwen-vl",
            "internvl",
            "cogvlm",
            "fuyu",
            "kosmos",
            "florence",
        )
        for kw in variant_a + variant_b + variant_c:
            assert kw in VISION_MODEL_KEYWORDS, kw


class TestBadgeUsesSSOT:
    """Layer 2 — the settings badge helper (was variant A)."""

    def test_minicpm_badged_vision(self):
        from ui_qt.settings.sections.helpers import _badge

        assert _badge("minicpm-v") == "🔍 "  # pre-fix: 📝 (the drift symptom)
        assert _badge("qwen2.5-vl:7b") == "🔍 "
        assert _badge("llama3.1:8b") == "📝 "
        assert _badge("gemma3:12b") == "📝 "


class TestOcrDialogKeywordsAreSSOT:
    """The anti-drift pin: the OCR dialog references the SSOT object itself,
    so its engine list can never silently diverge from the badge /
    dependencies / llamacpp classifications again."""

    def test_dialog_references_the_ssot(self):
        import core.llm.model_taxonomy as mt
        from ui_qt.views.service_dialogs.dialogs.ocr_service_dialog import OcrServiceDialog

        assert OcrServiceDialog._OCR_KEYWORDS is mt.VISION_MODEL_KEYWORDS


class TestLlamacppGateUsesSSOT:
    """Layer 2 — the llama.cpp vision-attempt gate (was variant B)."""

    @staticmethod
    def _alive_session(monkeypatch, status=200):
        class _Sess:
            def get(self, url, headers=None, timeout=None):
                return _resp(status, {})

            def close(self):
                pass

        monkeypatch.setattr("core.llm.llamacpp_provider._no_proxy_session", lambda: _Sess())

    def test_minicpm_gated_vision(self, monkeypatch):
        """Pre-fix (variant B): False — a minicpm-v on llama.cpp silently
        degraded to the Tesseract OCR path."""
        from core.llm.llamacpp_provider import LlamaCppProvider

        self._alive_session(monkeypatch)
        p = LlamaCppProvider(model="minicpm-v", retries=0)
        assert p.supports_vision() is True

    def test_text_model_gated_false(self, monkeypatch):
        from core.llm.llamacpp_provider import LlamaCppProvider

        self._alive_session(monkeypatch)
        p = LlamaCppProvider(model="llama3.1:8b", retries=0)
        assert p.supports_vision() is False

    def test_server_down_returns_false(self, monkeypatch):
        from core.llm.llamacpp_provider import LlamaCppProvider

        self._alive_session(monkeypatch, status=503)
        p = LlamaCppProvider(model="qwen2.5-vl:7b", retries=0)
        assert p.supports_vision() is False


class TestDependenciesVisionSplit:
    """Layer 2 — DependencyChecker.get_ollama_models (was variant A ×2)."""

    MODELS = [
        "minicpm-v",
        "llama3.1:8b",
        "qwen2.5-vl:7b",
        "gemma3:12b",
        "moondream2",  # variant C family dependencies previously missed
    ]

    def test_split_uses_ssot(self, monkeypatch):
        from utils.dependencies import DependencyChecker

        checker = DependencyChecker()
        monkeypatch.setattr(checker, "_get_cached", lambda key, fetcher: list(self.MODELS))
        assert checker.get_ollama_models("vision") == [
            "minicpm-v",
            "qwen2.5-vl:7b",
            "moondream2",
        ]
        assert checker.get_ollama_models("text") == ["llama3.1:8b", "gemma3:12b"]
        assert checker.get_ollama_models() == self.MODELS


# ── B6: the run_summarization incremental-save block, extracted + pinned ────


from core.models.models import SummaryResult  # noqa: E402
from core.pipeline.conversion.summarization import (  # noqa: E402
    _save_chapter_summaries_write_once,
)
from core.system.provenance import run_stamp_suffix  # noqa: E402


class _SaveSettings:
    """The minimal ``settings.get(path, default)`` surface the block needs."""

    def __init__(self, data: dict | None = None) -> None:
        self._d = data or {}

    def get(self, key, default=None):
        return self._d.get(key, default)


class _SaveConverter:
    """The minimal converter surface the extracted save block touches:
    ``settings``, ``paths.book_summary`` (the summaries/ folder is its
    parent) and ``_sanitize_filename``."""

    def __init__(self, root: Path) -> None:
        self.settings = _SaveSettings({})
        self.paths = SimpleNamespace(book_summary=root / "summaries" / "Book.summary.md")
        self._sanitize_filename = lambda heading: heading.replace(" ", "_")


def _mk_summary(heading: str = "Chapter One", **overrides) -> SummaryResult:
    kw = dict(
        chapter_heading=heading,
        executive_summary="EXE summary text.",
        thorough_summary="THOROUGH summary body.",
        bullet_points=["Point one", "Point two"],
        success=True,
    )
    kw.update(overrides)
    return SummaryResult(**kw)


def _mk_segments():
    return [
        SimpleNamespace(heading="Chapter One", content="src text chapter one"),
        SimpleNamespace(heading="Other", content="y" * 100),
    ]


@pytest.fixture
def save_logs() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def save_env(tmp_path, save_logs):
    conv = _SaveConverter(tmp_path)
    log = lambda msg, level="INFO": save_logs.append((level, msg))  # noqa: E731
    return conv, log, tmp_path / "summaries"


class TestSaveChapterSummariesWriteOnce:
    """B6 — the previously-untested end-of-run save block (V0.6.6
    run_summarization lines 992-1175), moved VERBATIM to module level in
    V0.6.7 and characterized here for the first time."""

    def test_success_stamped_filename_and_sentinel(self, save_env, save_logs):
        conv, log, folder = save_env
        summ = _mk_summary(app_version="0.6.7", run_id="20260101-120000-abcdef12")
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        stamp = run_stamp_suffix("0.6.7", "20260101-120000-abcdef12")
        sf = folder / f"001_Chapter_One{stamp}_summary.md"
        assert sf.exists()
        content = sf.read_text(encoding="utf-8")
        assert "<!-- COMPLETE" in content  # the sentinel (write-once marker)
        assert "EXE summary text." in content
        assert any("Saved summary 1/1" in m for (_, m) in save_logs)

    def test_legacy_unstamped_result_keeps_exact_legacy_name(self, save_env):
        conv, log, folder = save_env
        summ = _mk_summary()  # no app_version/run_id → stamp ""
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        assert (folder / "001_Chapter_One_summary.md").exists()
        assert not list(folder.glob("*_v*_summary.md"))

    def test_failed_summary_skipped_with_warning(self, save_env, save_logs):
        conv, log, folder = save_env
        summ = _mk_summary(success=False)
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        assert not list(folder.glob("*.md"))
        assert any("Skipped saving FAILED summary" in m for (_, m) in save_logs)

    def test_empty_summary_skipped(self, save_env, save_logs):
        conv, log, folder = save_env
        summ = _mk_summary(executive_summary="", thorough_summary="", bullet_points=[])
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        assert not list(folder.glob("*.md"))
        assert any("Skipped saving FAILED summary" in m for (_, m) in save_logs)

    def test_write_once_complete_file_never_rewritten(self, save_env, save_logs):
        """The crash-safety contract: a file WITH the COMPLETE sentinel is
        left byte-identical; the adoption note names the producing run."""
        conv, log, folder = save_env
        summ = _mk_summary(app_version="0.6.7", run_id="20260101-120000-abcdef12")
        stamp = run_stamp_suffix("0.6.7", "20260101-120000-abcdef12")
        sf = folder / f"001_Chapter_One{stamp}_summary.md"
        folder.mkdir(parents=True, exist_ok=True)
        sf.write_text(
            "# OLD CHAPTER ONE\n\nold bytes\n\n<!-- COMPLETE v0.6.6_20250101-000000-00000000 -->\n",
            encoding="utf-8",
        )
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        assert "old bytes" in sf.read_text(encoding="utf-8")  # untouched
        assert any("already saved — leaving untouched" in m for (_, m) in save_logs)

    def test_incomplete_existing_file_is_rewritten(self, save_env):
        """No sentinel (crash mid-write) → the file IS rewritten fresh."""
        conv, log, folder = save_env
        summ = _mk_summary()
        folder.mkdir(parents=True, exist_ok=True)
        sf = folder / "001_Chapter_One_summary.md"
        sf.write_text("partial garbage without a sentinel", encoding="utf-8")
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        content = sf.read_text(encoding="utf-8")
        assert "EXE summary text." in content
        assert "<!-- COMPLETE" in content
        assert "partial garbage" not in content

    def test_empty_heading_filename_without_heading(self, save_env):
        conv, log, folder = save_env
        summ = _mk_summary(
            heading="",
            app_version="0.6.7",
            run_id="20260101-120000-abcdef12",
        )
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        stamp = run_stamp_suffix("0.6.7", "20260101-120000-abcdef12")
        assert (folder / f"001{stamp}_summary.md").exists()

    def test_disk_full_raises_actionable_error(self, save_env, monkeypatch):
        conv, log, folder = save_env

        def _full(path, text):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr("core.pipeline.conversion.summarization.atomic_write_text", _full)
        with pytest.raises(OSError) as ei:
            _save_chapter_summaries_write_once(conv, _mk_segments(), [_mk_summary()], log)
        assert "Disk is full" in str(ei.value)
        assert "resume will skip" in str(ei.value)  # the actionable hint

    def test_other_oserror_propagates_unchanged(self, save_env, monkeypatch):
        conv, log, folder = save_env

        def _denied(path, text):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr("core.pipeline.conversion.summarization.atomic_write_text", _denied)
        with pytest.raises(OSError) as ei:
            _save_chapter_summaries_write_once(conv, _mk_segments(), [_mk_summary()], log)
        assert "Disk is full" not in str(ei.value)

    def test_verification_polish_applied_and_issues_logged(self, save_env, save_logs, monkeypatch):
        import core.summarisation.verification_phase as vp

        captured = {}

        def _polish(rendered, source, settings, log_cb):
            captured["rendered"], captured["source"] = rendered, source
            return "POLISHED OUTPUT\n<!-- COMPLETE -->", [
                SimpleNamespace(detector="dates", severity="fix", detail="fixed the year 1999")
            ]

        monkeypatch.setattr(vp, "verify_and_polish_summary", _polish)
        conv, log, folder = save_env
        _save_chapter_summaries_write_once(conv, _mk_segments(), [_mk_summary()], log)
        sf = folder / "001_Chapter_One_summary.md"
        assert sf.read_text(encoding="utf-8") == "POLISHED OUTPUT\n<!-- COMPLETE -->"
        assert any("V0.5.1 verification: [dates/fix]" in m for (_, m) in save_logs)
        # exact heading match → that segment's content is the verification source
        assert captured["source"] == "src text chapter one"
        assert "EXE summary text." in captured["rendered"]

    def test_verification_crash_fail_open(self, save_env, save_logs, monkeypatch):
        import core.summarisation.verification_phase as vp

        def _crash(rendered, source, settings, log_cb):
            raise RuntimeError("verify boom")

        monkeypatch.setattr(vp, "verify_and_polish_summary", _crash)
        conv, log, folder = save_env
        summ = _mk_summary()
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        content = (folder / "001_Chapter_One_summary.md").read_text(encoding="utf-8")
        assert "EXE summary text." in content  # original render ships
        assert any("verification crashed (non-fatal)" in m for (_, m) in save_logs)

    def test_source_matcher_falls_back_to_largest_segment(self, save_env, monkeypatch):
        import core.summarisation.verification_phase as vp

        captured = {}

        def _noop(rendered, source, settings, log_cb):
            captured["source"] = source
            return rendered, []

        monkeypatch.setattr(vp, "verify_and_polish_summary", _noop)
        conv, log, folder = save_env
        summ = _mk_summary(heading="A Heading That Matches No Segment")
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        assert captured["source"] == "y" * 100  # the largest segment wins

    def test_unreadable_existing_file_rewritten(self, save_env, monkeypatch):
        """The OSError-on-read path (line 1123-1124): unreadable existing
        file → fall through to the rewrite below."""
        conv, log, folder = save_env
        summ = _mk_summary()
        folder.mkdir(parents=True, exist_ok=True)
        sf = folder / "001_Chapter_One_summary.md"
        sf.write_text("cannot read this", encoding="utf-8")

        real_read = Path.read_text

        def _boom(self, *a, **k):
            if self == sf:
                raise OSError(5, "Input/output error")
            return real_read(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", _boom)
        _save_chapter_summaries_write_once(conv, _mk_segments(), [summ], log)
        # read via open() — the monkeypatched Path.read_text is still active
        with open(sf, encoding="utf-8") as fh:
            content = fh.read()
        assert "EXE summary text." in content  # rewritten


class TestSaveBlockWiring:
    """run_summarization is not headless-drivable (house precedent:
    tests/test_v1820412_b_semantics.py TestWa11SourcePins) — the wiring of
    the extracted block is source-pinned."""

    def test_run_summarization_calls_the_extracted_helper(self):
        src = (REPO / "core" / "pipeline" / "conversion" / "summarization.py").read_text(
            encoding="utf-8"
        )
        assert "_save_chapter_summaries_write_once(converter, segments, summaries, log)" in src
        # the moved code lives in exactly one place (the module-level helper)
        assert src.count("def _save_chapter_summaries_write_once(") == 1
        # the write-once contract marker survived the move
        assert "has_complete_sentinel(_existing_sf)" in src
        assert "errno == 28" in src
