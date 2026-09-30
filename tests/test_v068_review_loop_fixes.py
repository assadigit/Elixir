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
