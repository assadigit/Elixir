"""V0.6.8+ — the review-loop fixes (B-wave backlog from
docs/AUDIT_SWOT_V0.6.7.md). House 3-layer pattern
(test_v067_review_loop_fixes.py is the reference).

B4 — the dual_api override no-op (silent-routing bug):
  core/pipeline/conversion/summarization.py:793-798 checked
  ``hasattr(_provider, "_base_url"/"_api_key"/"_model")`` but every
  provider stores PUBLIC attributes (OpenAICompatProvider.__init__:
  ``self.base_url``/``self.api_key`` — openai_compat_provider.py:39-40;
  the model comes from the base class). The guards were always False, so
  the dual_api fast-API override NEVER applied: the concept-extraction
  calls silently kept hitting the settings cloud endpoint with the
  primary key while passing the fast model name per-call. The 5 sibling
  ``hasattr(_provider, "_model")`` sites (:821,837,861,903,924) were the
  same dead pattern on Ollama providers (masked because the per-call
  ``model=`` argument usually matched the settings default anyway).

  These tests pin the two contracts that make the routing honest:
  1. the PROVIDER contract — public base_url/api_key/model/timeout attrs
     (a rename back to private attrs must fail here and force a visit to
     every call site), and
  2. the WIRING contract — run_summarization assigns the PUBLIC attrs
     (source-pin style, the house test_gap_fill_veto_wired_in_summarizer
     precedent in test_v182032_audit_fixes.py).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.llm.ollama_provider import OllamaProvider  # noqa: E402
from core.llm.openai_compat_provider import OpenAICompatProvider  # noqa: E402
from core.pipeline.conversion.summarization import run_summarization  # noqa: E402

# ── B4: the provider attribute contract (public, not private) ───────────────


class TestProviderAttributeContract:
    """Every provider the dual_api/ollama override sites talk to exposes
    PUBLIC ``base_url``/``api_key``/``model``/``timeout``. Pre-fix, the
    code probed the private spellings — always False — so the overrides
    were no-ops."""

    def test_openai_compat_provider_attrs_are_public(self):
        p = OpenAICompatProvider(
            model="fast-cloud",
            base_url="http://fast/v1",
            api_key="fk",
            timeout=120,
        )
        assert p.base_url == "http://fast/v1"
        assert p.api_key == "fk"
        assert p.model == "fast-cloud"
        assert p.timeout == 120
        # The private spellings the pre-fix code probed must NOT exist.
        assert not hasattr(p, "_base_url")
        assert not hasattr(p, "_api_key")
        assert not hasattr(p, "_model")

    def test_ollama_provider_attrs_are_public(self):
        p = OllamaProvider(model="local-model", base_url="http://localhost:11434")
        assert p.model == "local-model"
        assert p.base_url == "http://localhost:11434"
        assert hasattr(p, "timeout")
        assert not hasattr(p, "_model")


# ── B4: the run_summarization wiring contract (source-pin) ─────────────────


class TestDualApiOverrideWiring:
    """The dual_api override must set the PUBLIC provider attributes, and
    no private-attr hasattr guard may remain in run_summarization."""

    @property
    def _src(self) -> str:
        return inspect.getsource(run_summarization)

    def test_dual_api_override_sets_public_attrs(self):
        src = self._src
        assert "_provider.base_url = _api_url" in src, (
            "the dual_api override must set the PUBLIC base_url "
            "(openai_compat_provider stores self.base_url, not _base_url)"
        )
        assert "_provider.api_key = _api_key" in src
        assert "_provider.model = _api_model" in src

    def test_no_private_attr_hasattr_guards_remain(self):
        src = self._src
        for dead in ('hasattr(_provider, "_base_url")', 'hasattr(_provider, "_api_key")'):
            assert dead not in src, f"dead guard still present: {dead}"
        assert 'hasattr(_provider, "_model")' not in src, (
            "dead _model guard still present — providers expose PUBLIC self.model"
        )

    def test_model_assignments_use_public_attr(self):
        src = self._src
        # The ollama fallback/dual_local/single_local branches assign the
        # model via the public attribute (the :888 llamacpp precedent).
        assert "_provider.model = _summ_model" in src
        assert "_provider.model = _fast_model" in src


# ── B4 behavioral: the override actually reaches the wire ───────────────────


class TestDualApiOverrideBehavioral:
    """End-to-end-ish: a provider instance whose attrs are overridden the
    way run_summarization now does it must route complete() at the
    overridden URL — the exact silent failure mode the audit found
    (settings cloud endpoint kept, fast API ignored)."""

    def test_overridden_provider_routes_at_fast_url(self, monkeypatch):
        import requests

        import core.llm.openai_compat_provider as prov_mod

        seen: dict = {}
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b'{"choices": [{"message": {"content": "ok"}}]}'

        class _Sess:
            def get(self, url, **kw):
                seen["get"] = url
                return resp

            def post(self, url, **kw):
                seen["post"] = url
                return resp

            def close(self):
                pass

        monkeypatch.setattr(prov_mod, "session_for_url", lambda url: _Sess())
        p = OpenAICompatProvider(
            model="primary-cloud",
            base_url="http://primary/v1",
            api_key="primary-key",
        )
        # The run_summarization override sequence (public attrs):
        p.base_url = "http://fast/v1"
        p.api_key = "fast-key"
        p.model = "fast-cloud"
        p.complete(prompt="hi", model="fast-cloud")
        assert seen.get("post", "").startswith("http://fast/v1"), (
            "complete() must route at the OVERRIDDEN base_url — pre-fix the "
            "override was a no-op and the primary endpoint was kept"
        )


# ── B5: the six bare-requests UI sites → shared transports ──────────────────
#
# utils/network.py provides the proxy-proof Ollama transports
# (is_ollama_reachable / list_ollama_models via safe_ollama_request) and
# core/llm/llamacpp_provider.py provides list_llamacpp_models (OpenAI-style
# /v1/models, proxy-proof). Six UI/system sites still probed /api/tags with
# bare requests.get / self-built sessions — breaking on HTTP_PROXY machines
# and duplicating the transport. House source-pin style (UI modules are not
# imported; see tests/test_v182045_p4a_service_dialog_threads.py).

import re  # noqa: E402

_B5_FILES = {
    "translation_service_dialog.py": REPO
    / "ui_qt/views/service_dialogs/dialogs/translation_service_dialog.py",
    "podcast_maker_view.py": REPO / "ui_qt/views/podcast_maker_view.py",
    "transcribe_service_dialog.py": REPO
    / "ui_qt/views/service_dialogs/dialogs/transcribe_service_dialog.py",
    "summarization_service_dialog.py": REPO
    / "ui_qt/views/service_dialogs/dialogs/summarization_service_dialog.py",
    "dependency_checker.py": REPO / "core/system/dependency_checker.py",
    "ai_model_section.py": REPO / "ui_qt/settings/sections/ai_model_section.py",
}


def _method_src(path: Path, name: str) -> str:
    """Slice a method's source (def name → the next same-indent def/docstring
    boundary). Asserts the method exists — a rename fails loudly here."""
    src = path.read_text(encoding="utf-8")
    m = re.search(rf"^([ \t]*)def {re.escape(name)}\(", src, re.M)
    assert m, f"{path.name}: def {name} not found"
    start = m.start()
    rest = src[m.end() :]
    nxt = re.search(r"^([ \t]*)(def |class |@)", rest, re.M)
    end = m.end() + (nxt.start() if nxt else len(rest))
    return src[start:end]


class TestB5BareRequestsSwept:
    """Every one of the six audited sites must fetch through the shared
    transports — no lazy ``import requests`` inside the method (the
    tell-tale of the bare-call pattern: each file imports requests ONLY
    inside these methods)."""

    def test_refresh_models_translation_dialog(self):
        s = _method_src(_B5_FILES["translation_service_dialog.py"], "_refresh_models")
        assert "import requests" not in s, "bare requests import remains"
        assert "list_ollama_models(" in s, "must route through list_ollama_models"

    def test_refresh_models_podcast_maker_view(self):
        s = _method_src(_B5_FILES["podcast_maker_view.py"], "_refresh_models")
        assert "import requests" not in s
        assert "list_ollama_models(" in s
        assert "is_ollama_reachable(" in s  # the no-models vs down distinction

    def test_refresh_models_transcribe_dialog(self):
        s = _method_src(_B5_FILES["transcribe_service_dialog.py"], "_refresh_models")
        assert "import requests" not in s
        assert "list_ollama_models(" in s

    def test_fetch_installed_models_summarization_dialog(self):
        s = _method_src(_B5_FILES["summarization_service_dialog.py"], "_fetch_installed_models")
        assert "import requests" not in s, "the bare _req.get pre-check remains"
        assert "is_ollama_reachable(" in s, (
            "the reachability pre-check must use the SAME proxy-proof "
            "transport as the list call (pre-fix: proxy could answer the "
            "bare pre-check while the proxy-proof list call failed)"
        )

    def test_check_ollama_dependency_checker(self):
        s = _method_src(_B5_FILES["dependency_checker.py"], "_check_ollama")
        assert "import requests" not in s
        assert "list_ollama_models(" in s
        assert "is_ollama_reachable(" in s

    def test_fetch_models_from_ai_model_section(self):
        s = _method_src(_B5_FILES["ai_model_section.py"], "_fetch_models_from")
        assert "import requests" not in s, "self-built session remains"
        assert "requests.Session()" not in s
        assert "list_ollama_models(" in s, "the Ollama branch must use the helper"
        assert "list_llamacpp_models(" in s, (
            "the LM Studio OpenAI-style /v1/models branch must use the shared proxy-proof lister"
        )


# ── B6: the RTL deps on all three install surfaces ─────────────────────────
#
# V0.6.5 added arabic-reshaper + python-bidi for RTL PDF shaping
# (core/outputs/service_formatters.py) but only to requirements.txt — the
# pyproject [project.dependencies] and requirements.lock surfaces lacked
# them (audit B6 / dependency drift). All three must carry them.


class TestB6RtlDepsOnAllSurfaces:
    def test_rtl_deps_present_everywhere(self):
        surfaces = {
            "pyproject.toml": REPO / "pyproject.toml",
            "requirements.txt": REPO / "requirements.txt",
            "requirements.lock": REPO / "requirements.lock",
        }
        for name, path in surfaces.items():
            src = path.read_text(encoding="utf-8")
            assert "arabic-reshaper" in src, f"{name}: arabic-reshaper missing"
            assert "python-bidi" in src, f"{name}: python-bidi missing"

    def test_lock_pins_exact_versions(self):
        lock = (REPO / "requirements.lock").read_text(encoding="utf-8")
        assert "arabic-reshaper==3.0.1" in lock
        assert "python-bidi==0.6.11" in lock


# ── B8-B11: the highest-value exception swallows → WARNING + narrow ─────────
#
# The audit's Wave 4: silent failure paths whose failure mode is invisible
# (resume disabled, stale cache surviving, guards not guarding, coverage
# contracts vanishing). Each fix logs at WARNING and narrows the caught
# family; B10 additionally fails SAFE (health-check failure = unhealthy).


class TestB8CorruptManifestWarning:
    def _saver(self, tmp_path):
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        conv = SimpleNamespace(
            output_dir=str(tmp_path),
            paths=SimpleNamespace(summaries_dir=str(tmp_path / "summaries")),
            _log=lambda msg, level="INFO": None,
            request=None,
        )
        return ChapterCheckpointSaver(conv)

    def test_corrupt_manifest_returns_empty_and_warns(self, tmp_path, caplog, monkeypatch):
        import logging

        saver = self._saver(tmp_path)
        manifest = tmp_path / "checkpoints" / "chapter_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"chapters": [truncated', encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            assert saver._load_manifest() == {}
        assert any("chapter_manifest_load" in r.message for r in caplog.records), (
            "a corrupt manifest must log at WARNING — pre-fix it silently "
            "returned {} and invisibly disabled chapter resume"
        )

    def test_non_dict_manifest_warns(self, tmp_path, caplog):
        import logging

        saver = self._saver(tmp_path)
        manifest = tmp_path / "checkpoints" / "chapter_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("[1, 2, 3]", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            assert saver._load_manifest() == {}
        assert any("not an object" in r.message for r in caplog.records)

    def test_valid_manifest_still_loads(self, tmp_path):
        saver = self._saver(tmp_path)
        manifest = tmp_path / "checkpoints" / "chapter_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"chapters": {"c1": {}}}', encoding="utf-8")
        assert saver._load_manifest() == {"chapters": {"c1": {}}}


