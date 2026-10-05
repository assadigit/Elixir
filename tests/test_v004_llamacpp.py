"""V0.04 — llama.cpp backend: provider, wiring, settings migration, GUI.

The rig's primary LLM moves from Ollama to a local ``llama-server``
(127.0.0.1:8080/v1, model Ternary-Bonsai-2-27B-Instruct-Vision,
65k context / 12k output). This batch pins:

  A. LlamaCppProvider against a FAITHFUL mock of llama-server
     (tests/mock_llamacpp_server.py): streaming generation, the
     user's exact config, output-budget fitting (the 12k cap + the
     65k window), JSON mode, auth/model/context error shapes, the
     two-stage connection probe, model discovery.
  B. Factory + dispatcher wiring: create_provider("llamacpp") reads
     the llamacpp_* settings; call_via_llm_provider applies the
     endpoint overrides; the re-export surface.
  C. Settings: the llamacpp_* defaults, the one-time activation
     migration (ollama→llamacpp ONLY at the untouched default; never
     re-flipped after an explicit user choice), and the V18.1 output
     floor guard (legacy migrations must not fight backend caps).
  D. Wizard/settings-dialog surfaces (PySide6-absent source pins):
     the backend combo, the 65k/12k-accepting spinboxes, the llama.cpp
     endpoint box + Test-connection, backend-aware model discovery,
     save() provider preservation, and the state→request token flow.
  E. VRAM: the ternary (1.58-bit) size class — a 27B ternary is ~8 GB,
     not the ~18 GB the Q4_K_M fallback claimed.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── helpers ────────────────────────────────────────────────────────────────


def _src(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments + inline fragments so pins assert CODE."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


@contextmanager
def _hermetic_settings(tmp_dir: Path):
    """Point the Settings singleton at a temp dir (test_v182043 pattern)."""
    from utils.settings import Settings

    Settings._instance = None
    Settings._test_override = None
    try:
        with (
            patch.object(Settings, "_settings_dir", tmp_dir),
            patch.object(Settings, "_settings_file", tmp_dir / "settings.json"),
        ):
            yield
    finally:
        Settings._instance = None
        Settings._test_override = None


@pytest.fixture
def llamacpp_server():
    """A running mock llama-server with the rig's exact model served."""
    from tests.mock_llamacpp_server import MockLlamaCppServer

    srv = MockLlamaCppServer(models=["Ternary-Bonsai-2-27B-Instruct-Vision"]).start()
    try:
        yield srv
    finally:
        srv.stop()


def _rig_provider(srv, **overrides):
    """LlamaCppProvider built from the user's exact rig config."""
    from core.llm.llamacpp_provider import LlamaCppProvider

    kwargs = dict(
        model="Ternary-Bonsai-2-27B-Instruct-Vision",
        base_url=srv.base_url,
        api_key="local",
        temperature=0.6,
        max_tokens=12288,
        context_tokens=65536,
        output_cap=12288,
        timeout=30,
        retries=0,
    )
    kwargs.update(overrides)
    return LlamaCppProvider(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# A. LlamaCppProvider — functional, against the mock server
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderComplete:
    """The user's exact config → complete() round-trips through llama.cpp."""

    def test_user_config_complete(self, llamacpp_server):
        p = _rig_provider(llamacpp_server)
        out = p.complete("Summarize this document accurately and structurally.")
        assert out is not None
        assert "MOCK-LLAMACPP[Ternary-Bonsai-2-27B-Instruct-Vision]" in out

    def test_streaming_is_the_default_path(self, llamacpp_server):
        """complete() always requests stream=True (the 60-minute-generation
        rule: per-chunk timeouts, never a whole-request timeout). A slow
        stream (20ms/chunk) must produce throttled on_chunk progress
        callbacks carrying the GROWING text, and the final result is the
        full accumulated stream."""
        from tests.mock_llamacpp_server import MockLlamaCppServer

        words = " ".join(f"w{i}" for i in range(80))
        srv = MockLlamaCppServer(response_text=words, chunk_delay=0.02).start()
        try:
            p = _rig_provider(srv, max_tokens=80, output_cap=80)
            seen: list[str] = []
            out = p.complete_streaming("chapter text", on_chunk=seen.append)
            assert out is not None and out.strip()
            assert seen, "on_chunk progress callbacks must fire during a long stream"
            # every callback is a prefix of the final accumulated text
            for snap in seen:
                assert out.startswith(snap.rstrip()), "progress must be the growing text"
            # the returned text is the COMPLETE stream (all 80 words), even
            # though the last throttled callback fired mid-stream.
            assert len(out.split()) == 80
        finally:
            srv.stop()

    def test_max_tokens_cap_respected_on_wire(self, llamacpp_server):
        """The server caps generation at max_tokens — the mock enforces it,
        proving the provider actually sends the (fitted) budget."""
        p = _rig_provider(llamacpp_server, max_tokens=3, output_cap=3)
        out = p.complete("one two three four five six seven eight nine ten")
        assert out is not None
        assert len(out.split()) <= 3, f"server should stop at max_tokens=3: {out!r}"

    def test_json_mode_returns_valid_json(self, llamacpp_server):
        p = _rig_provider(llamacpp_server)
        out = p.complete("Give me json", json_mode=True)
        assert out is not None
        parsed = json.loads(out)
        assert parsed["ok"] is True

    def test_bearer_token_sent(self, llamacpp_server):
        """llama.cpp without --api-key ignores the header; with it, the key
        must arrive as 'Authorization: Bearer local' (the user's config)."""
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(api_key="local").start()
        try:
            p = _rig_provider(srv, api_key="local")
            assert p.complete("hi") is not None
            # wrong key → 401 → provider returns None (never raises)
            p_bad = _rig_provider(srv, api_key="wrong-key")
            assert p_bad.complete("hi") is None
        finally:
            srv.stop()

    def test_server_down_returns_none(self):
        from core.llm.llamacpp_provider import LlamaCppProvider

        p = LlamaCppProvider(model="x", base_url="http://127.0.0.1:9/v1", timeout=2, retries=0)
        assert p.complete("hi") is None  # port 9 = discard, nothing listens


class TestOutputBudgetFitting:
    """fit_max_tokens: a knowing provider makes the request FIT."""

    def test_output_cap_16000_to_12288(self, llamacpp_server):
        """The academic-rigor 16000 floor must not exceed the 12k model cap."""
        p = _rig_provider(llamacpp_server, output_cap=12288)
        assert p.fit_max_tokens(16000, "short prompt") == 12288

    def test_context_fit_huge_prompt(self, llamacpp_server):
        """A prompt that nearly fills the 65k window shrinks the budget to
        what actually fits (ctx − prompt_est − margin)."""
        p = _rig_provider(llamacpp_server, context_tokens=65536, output_cap=12288)
        # V0.09 (P5): fit_max_tokens now counts REAL tokens (tiktoken via
        # core.llm.context_budget) instead of chars//4. The old prompt
        # ("x" * 4 * 60000) only counts ~30k tokens now (tiktoken merges
        # x-runs), so it no longer nearly fills the window — "word " * 60000
        # is a genuine ~60k-token prompt, preserving this test's intent.
        huge = "word " * 60000  # ~60k actual tokens
        fitted = p.fit_max_tokens(12288, huge)
        assert 256 <= fitted < 12288

    def test_floor_256_on_absurd_prompt(self, llamacpp_server):
        p = _rig_provider(llamacpp_server, context_tokens=1024, output_cap=12288)
        assert p.fit_max_tokens(12288, "y" * 100000) == 256

    def test_no_clamp_when_it_fits(self, llamacpp_server):
        p = _rig_provider(llamacpp_server)
        assert p.fit_max_tokens(12288, "normal chapter text") == 12288

    def test_complete_never_400s_on_configured_window(self, llamacpp_server):
        """End-to-end: the old 16000 default + a real prompt must NOT trip
        the server's ctx check (the provider fits it first)."""
        p = _rig_provider(llamacpp_server, max_tokens=16000, output_cap=12288)
        out = p.complete("Summarize this document accurately and structurally.")
        assert out is not None

    def test_server_ctx_smaller_than_configured(self, llamacpp_server):
        """When llama-server was started with a SMALLER -c than configured,
        the 400 arrives and the provider surfaces the actionable message
        (start llama-server with a larger -c) instead of a raw error."""
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(n_ctx=1024).start()
        try:
            p = _rig_provider(srv, context_tokens=65536, max_tokens=12288, output_cap=12288)
            logs: list[str] = []
            p.log = lambda msg, level="INFO": logs.append(msg)
            out = p.complete("a reasonably sized chapter prompt" * 40)
            assert out is None
            assert any("context" in m.lower() for m in logs), logs
        finally:
            srv.stop()


class TestModelDiscoveryAndConnection:
    """list_llamacpp_models + the two-stage test_llamacpp_connection."""

    def test_list_models(self, llamacpp_server):
        from core.llm.llamacpp_provider import list_llamacpp_models

        models = list_llamacpp_models(llamacpp_server.base_url, "local")
        assert models == ["Ternary-Bonsai-2-27B-Instruct-Vision"]

    def test_list_models_server_down(self):
        from core.llm.llamacpp_provider import list_llamacpp_models

        assert list_llamacpp_models("http://127.0.0.1:9/v1", "local") == []

    def test_connection_probe_ok(self, llamacpp_server):
        from core.llm.llamacpp_provider import test_llamacpp_connection

        ok, msg = test_llamacpp_connection(
            llamacpp_server.base_url, "local", "Ternary-Bonsai-2-27B-Instruct-Vision"
        )
        assert ok, msg
        assert "Ternary-Bonsai-2-27B-Instruct-Vision" in msg

    def test_connection_probe_server_down(self):
        from core.llm.llamacpp_provider import test_llamacpp_connection

        ok, msg = test_llamacpp_connection("http://127.0.0.1:9/v1", "local", "x")
        assert not ok
        assert "cannot reach" in msg.lower()

    def test_connection_probe_auth_rejected(self):
        from core.llm.llamacpp_provider import test_llamacpp_connection
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(api_key="real-key").start()
        try:
            ok, msg = test_llamacpp_connection(srv.base_url, "wrong-key", "m")
            assert not ok
            assert "api key" in msg.lower()
        finally:
            srv.stop()

    def test_connection_probe_model_mismatch(self):
        from core.llm.llamacpp_provider import test_llamacpp_connection
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(models=["bonsai"], strict_model=True).start()
        try:
            ok, msg = test_llamacpp_connection(srv.base_url, "local", "not-served")
            assert not ok
        finally:
            srv.stop()

    def test_smoke_test_ok(self, llamacpp_server):
        p = _rig_provider(llamacpp_server)
        assert p.smoke_test() is True

    def test_smoke_test_model_404(self):
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(models=["bonsai"], strict_model=True).start()
        try:
            p = _rig_provider(srv)
            assert p.smoke_test() is False
        finally:
            srv.stop()


# ═══════════════════════════════════════════════════════════════════════════
# B. Factory + dispatcher wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestFactoryWiring:
    def test_create_provider_llamacpp_from_settings(self, llamacpp_server, tmp_path):
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            s = Settings()
            s.set("summarisation.llamacpp_base_url", llamacpp_server.base_url)
            s.set("summarisation.llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision")
            s.set("summarisation.llamacpp_context_tokens", 65536)
            s.set("summarisation.llamacpp_max_output_tokens", 12288)

            from core.llm.llm_provider import create_provider

            p = create_provider("llamacpp", s)
            assert type(p).__name__ == "LlamaCppProvider"
            assert p.base_url == llamacpp_server.base_url
            assert p.model == "Ternary-Bonsai-2-27B-Instruct-Vision"
            assert p.context_tokens == 65536
            assert p.max_tokens == 12288
            assert p.output_cap == 12288
            assert p.api_key == "local"

    def test_create_provider_llamacpp_detects_served_model(self, tmp_path):
        """V0.4.30 (multi-backend): create_provider queries /v1/models + uses
        the ACTUAL served model, not the hardcoded ``llamacpp_model`` setting
        — so a llama-server on a different port serving a different model
        (e.g. 8080=Ternary-Bonsai, 8081=Qwen3.8) is identified + addressed
        correctly. Falls back to the configured model if /v1/models is empty.
        """
        from tests.mock_llamacpp_server import MockLlamaCppServer

        # Server serves Qwen, but settings are configured for Ternary-Bonsai.
        srv = MockLlamaCppServer(models=["Qwen3.8-27B-Instruct"]).start()
        try:
            with _hermetic_settings(tmp_path):
                from utils.settings import Settings

                s = Settings()
                s.set("summarisation.llamacpp_base_url", srv.base_url)
                s.set(
                    "summarisation.llamacpp_model",
                    "Ternary-Bonsai-2-27B-Instruct-Vision",  # configured ≠ served
                )
                s.set("summarisation.llamacpp_context_tokens", 65536)
                s.set("summarisation.llamacpp_max_output_tokens", 12288)

                from core.llm.llm_provider import create_provider

                p = create_provider("llamacpp", s)
                # The DETECTED model wins over the configured.
                assert p.model == "Qwen3.8-27B-Instruct"

                # Fallback: a server serving NOTHING → use the configured model.
                srv_empty = MockLlamaCppServer(models=[]).start()
                try:
                    s.set("summarisation.llamacpp_base_url", srv_empty.base_url)
                    p2 = create_provider("llamacpp", s)
                    assert (
                        p2.model == "Ternary-Bonsai-2-27B-Instruct-Vision"
                    )  # the configured fallback
                finally:
                    srv_empty.stop()
        finally:
            srv.stop()

    def test_reexport_surface(self):
        from core.llm import llm_provider
        from core.llm.llamacpp_provider import LlamaCppProvider as _Direct

        assert llm_provider.LlamaCppProvider is _Direct
        assert llm_provider.create_provider is not None

    def test_dispatcher_applies_llamacpp_endpoint(self, llamacpp_server, tmp_path):
        """call_via_llm_provider routes llamacpp through the factory AND
        applies the caller's endpoint overrides (unlike the inert
        openai_compat _base_url branch)."""
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            Settings()  # initialise inside the hermetic dir
            from core.summarisation.llm_dispatcher import call_via_llm_provider

            out = call_via_llm_provider(
                "llamacpp",
                "Summarize this document accurately and structurally.",
                "Ternary-Bonsai-2-27B-Instruct-Vision",
                llamacpp_server.base_url,
                "local",
                0.6,
                12288,
                timeout=30,
                supervisor=None,
                log=None,
            )
            assert out is not None
            assert "MOCK-LLAMACPP" in out


class TestSummarizerDispatchPins:
    """Source pins: the Summarizer routes llamacpp through the provider
    abstraction (NOT the Ollama /api/generate path)."""

    def test_call_llm_llamacpp_branch(self):
        # V0.18 (Phase 5.1): _call_llm moved VERBATIM to llm_transport.py — pin follows.
        src = _strip_comments(_src("core/summarisation/llm_transport.py"))
        assert 'elif self.provider == "llamacpp":' in src
        # V0.13: the _call_via_llm_provider("llamacpp", prompt, …) call is
        # format-wrapped — pin the provider string + prompt arg on their lines.
        assert '"llamacpp",' in src
        assert "prompt," in src
        # V0.13: kwargs are one-per-line now — pin them individually
        assert "base_url=self.llamacpp_base_url," in src
        assert "api_key=self.llamacpp_api_key," in src
        assert "model=self.llamacpp_model or model" in src

    def test_llamacpp_attrs_initialized(self):
        # V0.18 (Phase 5.1): the _init_* sub-constructors moved VERBATIM to
        # summarizer_init.py — pin follows.
        src = _strip_comments(_src("core/summarisation/summarizer_init.py"))
        assert "self.llamacpp_base_url = settings.get(" in src
        assert "self.llamacpp_model = settings.get(" in src
        assert "self.llamacpp_max_output = int(" in src

    def test_is_local_includes_llamacpp(self):
        # V0.18 (Phase 5.1): moved VERBATIM to summarizer_init.py — pin follows.
        src = _strip_comments(_src("core/summarisation/summarizer_init.py"))
        assert '"llamacpp"' in src.split("self.is_local = ")[1].splitlines()[0]

    def test_reading_level_excludes_llamacpp(self):
        # V0.18 (Phase 5.1): moved VERBATIM to prompt_builders.py — pin follows.
        src = _strip_comments(_src("core/summarisation/prompt_builders.py"))
        assert 'self.provider not in ("ollama", "lmstudio", "llamacpp", "")' in src

    def test_concept_extraction_branch(self):
        src = _strip_comments(_src("core/pipeline/conversion/summarization.py"))
        assert 'if _prov == "llamacpp":' in src
        assert 'provider="llamacpp",' in src
        assert '"summarisation.llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision"' in src

    def test_structured_io_json_mode(self):
        from core.llm.structured_io import supports_json_mode

        assert supports_json_mode("llamacpp", "Ternary-Bonsai-2-27B-Instruct-Vision") is True
        assert supports_json_mode("unknown_provider", "m") is False

    def test_dispatcher_endpoint_override_branch(self):
        src = _strip_comments(_src("core/summarisation/llm_dispatcher.py"))
        assert 'if provider_type == "llamacpp":' in src
        assert 'provider.base_url = base_url.rstrip("/")' in src


# ═══════════════════════════════════════════════════════════════════════════
# C. Settings — defaults + the one-time activation migration
# ═══════════════════════════════════════════════════════════════════════════


class TestSettingsDefaults:
    def test_llamacpp_defaults_present(self, tmp_path):
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            d = Settings()._defaults()["summarisation"]
            assert d["llamacpp_base_url"] == "http://127.0.0.1:8080/v1"
            assert d["llamacpp_api_key"] == "local"
            assert d["llamacpp_model"] == "Ternary-Bonsai-2-27B-Instruct-Vision"
            assert d["llamacpp_context_tokens"] == 65536
            assert d["llamacpp_max_output_tokens"] == 12288
            assert d["provider"] == "llamacpp"


class TestActivationMigration:
    def _write_settings(self, tmp_path, summarisation: dict):
        (tmp_path / "settings.json").write_text(
            json.dumps({"summarisation": summarisation}), encoding="utf-8"
        )

    def test_untouched_ollama_installs_flip(self, tmp_path):
        """The rig's case: provider=ollama at the old defaults → llamacpp,
        65k ctx, 12k output, Bonsai as the summarisation model."""
        self._write_settings(
            tmp_path,
            {
                "provider": "ollama",
                "model": "gemma4-12b:latest",
                "max_context_tokens": 32768,
                "max_output_tokens": 16000,
                "llamacpp_activation_done": False,
            },
        )
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            s = Settings()
            assert s.get("summarisation.provider") == "llamacpp"
            assert s.get("summarisation.model") == "Ternary-Bonsai-2-27B-Instruct-Vision"
            assert s.get("summarisation.max_context_tokens") == 65536
            assert s.get("summarisation.max_output_tokens") == 12288
            assert s.get("summarisation.llamacpp_activation_done") is True

    def test_old_8192_output_migrates_to_12288(self, tmp_path):
        """8192 → V18.1 floor (16000) → V0.04 clamp (12288): the migrations
        compose without fighting."""
        self._write_settings(
            tmp_path,
            {
                "provider": "ollama",
                "max_output_tokens": 8192,
                "llamacpp_activation_done": False,
            },
        )
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            assert Settings().get("summarisation.max_output_tokens") == 12288

    def test_explicit_choice_not_flipped(self, tmp_path):
        """A user who chose lmstudio/cloud explicitly is NEVER overridden."""
        self._write_settings(tmp_path, {"provider": "lmstudio", "llamacpp_activation_done": False})
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            s = Settings()
            assert s.get("summarisation.provider") == "lmstudio"
            # …but the llamacpp_* keys exist (deep-merged from defaults)
            assert s.get("summarisation.llamacpp_base_url") == "http://127.0.0.1:8080/v1"
            assert s.get("summarisation.llamacpp_activation_done") is True

    def test_no_reflip_after_user_reverts(self, tmp_path):
        """After activation, a user switching BACK to ollama stays on ollama."""
        self._write_settings(
            tmp_path,
            {
                "provider": "ollama",
                "max_context_tokens": 32768,
                "llamacpp_activation_done": True,
            },
        )
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            s = Settings()
            assert s.get("summarisation.provider") == "ollama"
            assert s.get("summarisation.max_context_tokens") == 32768

    def test_v18_1_floor_guarded_for_llamacpp(self, tmp_path):
        """The legacy 16000 output floor must NOT re-raise the llamacpp
        12288 cap on every subsequent load."""
        self._write_settings(
            tmp_path,
            {
                "provider": "llamacpp",
                "max_output_tokens": 12288,
                "llamacpp_activation_done": True,
            },
        )
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            assert Settings().get("summarisation.max_output_tokens") == 12288

    def test_custom_ctx_survives_activation(self, tmp_path):
        """A user's custom 16384 ctx is not stomped by the 65k default."""
        self._write_settings(
            tmp_path,
            {
                "provider": "ollama",
                "max_context_tokens": 16384,
                "llamacpp_activation_done": False,
            },
        )
        with _hermetic_settings(tmp_path):
            from utils.settings import Settings

            assert Settings().get("summarisation.max_context_tokens") == 16384


# ═══════════════════════════════════════════════════════════════════════════
# D. Wizard + Settings-dialog surfaces (PySide6-absent source pins)
# ═══════════════════════════════════════════════════════════════════════════


class TestWizardStep5Pins:
    STEP5 = "ui_qt/views/wizard_steps/step5_models.py"
    MIXIN = "ui_qt/components/llamacpp_config.py"

    def test_backend_combo_has_llamacpp(self):
        src = _strip_comments(_src(self.STEP5))
        assert 'addItem("llama.cpp server", "llamacpp")' in src
        assert '_saved_backend not in ("ollama", "llamacpp", "lmstudio")' in src

    def test_step5_mixes_in_llamacpp_config(self):
        """The llama.cpp surface lives in the components mixin (O-b1 line
        budget) and Step5Models inherits it."""
        src = _strip_comments(_src(self.STEP5))
        assert "class Step5Models(LlamaCppConfigMixin, WizardStep):" in src
        assert "self.llamacpp_widget = self.build_llamacpp_box()" in src

    def test_llamacpp_endpoint_box(self):
        src = _strip_comments(_src(self.MIXIN))
        assert "self.llamacpp_url_edit" in src
        assert "self.llamacpp_key_edit" in src
        assert "self.llamacpp_model_edit" in src
        assert "self.llamacpp_test_btn" in src
        assert "def _test_llamacpp_connection" in src
        assert "test_llamacpp_connection(base, key, model)" in src

    def test_ctx_spinbox_accepts_65k(self):
        """Range 1024–262144 covers 65536 — the GUI cannot cap the model."""
        src = _strip_comments(_src(self.STEP5))
        assert "self.heavy_ctx_spin.setRange(1024, 262144)" in src

    def test_output_spinbox_accepts_12k(self):
        """The NEW heavy-model output spinbox covers 12288 (256–65536)."""
        src = _strip_comments(_src(self.STEP5))
        assert "self.heavy_out_spin.setRange(256, 65536)" in src
        assert "self.state.max_output_tokens = self.heavy_out_spin.value()" in src
        # V0.13: format-wrapped — pin the key + the spinbox source together
        assert '"summarisation.max_output_tokens", self.heavy_out_spin.value()' in src

    def test_backend_aware_model_discovery(self):
        """llamacpp lists models via the mixin's Settings-only worker fn;
        the dispatch happens in _refresh_models on the main thread."""
        src5 = _strip_comments(_src(self.STEP5))
        src_mix = _strip_comments(_src(self.MIXIN))
        assert 'if self._models_backend_snapshot == "llamacpp":' in src5
        assert "worker_fn = self.llamacpp_fetch_models" in src5
        assert "list_llamacpp_models" in src_mix
        assert "def llamacpp_fetch_models" in src_mix

    def test_backend_change_aligns_token_budgets(self):
        src_mix = _strip_comments(_src(self.MIXIN))
        assert "def _on_backend_change" in src_mix
        assert '"summarisation.llamacpp_context_tokens", 65536' in src_mix
        assert '"summarisation.llamacpp_max_output_tokens", 12288' in src_mix
        # …and Step5 wires the combo signal to it
        src5 = _strip_comments(_src(self.STEP5))
        assert "self.backend_combo.currentIndexChanged.connect(self._on_backend_change)" in src5

    def test_save_persists_llamacpp_block(self):
        src5 = _strip_comments(_src(self.STEP5))
        src_mix = _strip_comments(_src(self.MIXIN))
        assert "_lc_model = self.save_llamacpp_settings()" in src5
        assert 'update_setting("summarisation.llamacpp_base_url"' in src_mix
        assert 'update_setting("summarisation.llamacpp_model"' in src_mix
        assert 'update_setting("summarisation.provider", backend)' in src5

    def test_visibility_wiring(self):
        src5 = _strip_comments(_src(self.STEP5))
        src_mix = _strip_comments(_src(self.MIXIN))
        assert "self.llamacpp_set_visible(is_local, backend)" in src5
        assert 'self.llamacpp_widget.setVisible(is_local and backend == "llamacpp")' in src_mix


class TestSettingsDialogPins:
    # V0.4.19 (de-monolithization) pin evolution: sections.py became the
    # sections/ package — AiLocalModelSection (the backend picker, the
    # provider-aware save, and the llama.cpp model fetch these pins slice)
    # moved VERBATIM to ai_model_section.py. Assertions unchanged.
    SECTIONS = "ui_qt/settings/sections/ai_model_section.py"

    def test_backend_list_has_llamacpp(self):
        src = _strip_comments(_src(self.SECTIONS))
        assert '"llama.cpp server"' in src
        assert 'BACKENDS = ["Ollama", "llama.cpp server", "LM Studio", "Custom"]' in src

    def test_save_preserves_llamacpp_provider(self):
        """The old unconditional provider="ollama" write clobbered llamacpp
        on every Settings save — the branch must be backend-aware now."""
        src = _strip_comments(_src(self.SECTIONS))
        assert 'update_setting("summarisation.provider", "llamacpp")' in src

    def test_llamacpp_model_fetch(self):
        src = _strip_comments(_src(self.SECTIONS))
        assert "def _fetch_llamacpp_models" in src
        assert "list_llamacpp_models" in src
        # the async dispatch sends the Settings-only fn to the worker
        assert "fetch = self._fetch_llamacpp_models" in src


class TestWizardStateFlow:
    def test_state_carries_65k_12k_to_request(self):
        """WizardState → to_ui_data: the 65k/12k numbers survive into the
        request dict that build_request_from_ui consumes. (Source pin —
        importing the module pulls ui_qt → PySide6, absent on this rig;
        the established PySide6-absent pattern from V0.02/V0.03.)"""
        src = _strip_comments(_src("ui_qt/views/wizard_steps/shared.py"))
        assert '"summarisation_max_context_tokens": self.max_context_tokens,' in src
        assert '"summarisation_max_output_tokens": self.max_output_tokens,' in src

    def test_wizard_loads_token_settings_into_state(self):
        """_load_settings_into_state must reflect the persisted 65k/12k
        (the old hardcoded 32768/8192 state defaults used to mask them)."""
        src = _strip_comments(_src("ui_qt/views/wizard_view.py"))
        # V0.13: format-wrapped — pin the setting key + default instead
        assert 's.get_setting("summarisation.max_context_tokens", 32768)' in src
        assert 's.get_setting("summarisation.max_output_tokens", 16000)' in src

    def test_step7b_spinboxes_cover_new_numbers(self):
        """Step 7b's ctx/out spins (the fine-tune surface) accept 65k/12k."""
        src = _strip_comments(_src("ui_qt/views/wizard_steps/step7b_fine_tune.py"))
        assert "setRange(1000, 128000)" in src  # 65536 ✓
        assert "setRange(256, 32768)" in src  # 12288 ✓


# ═══════════════════════════════════════════════════════════════════════════
# E. VRAM — the ternary size class
# ═══════════════════════════════════════════════════════════════════════════


class TestTernaryVramClass:
    def test_parse_ternary(self):
        from core.vram_calculator import _parse_quantization

        name, mult = _parse_quantization("Ternary-Bonsai-2-27B-Instruct-Vision")
        assert name == "ternary"
        assert mult == 0.31

    def test_27b_ternary_estimate_sane(self):
        """27B ternary ≈ 8.4 GB weights + KV + overhead ≈ 12.9 GB at 32k ctx —
        NOT the ~20.2 GB the Q4_K_M fallback claimed (bogus overbudget; the
        real fix is the WEIGHTS class: 27 × 0.31, not 27 × 0.58). At 65k the
        estimate grows by the app's fp16-KV model (+4 GB) — that part is
        architecture math, not the quant class."""
        from core.vram_calculator import _estimate_model_vram

        est32k = _estimate_model_vram(
            "Ternary-Bonsai-2-27B-Instruct-Vision",
            role="summarisation",
            context_tokens=32768,
        )
        # 27*0.31 (weights) + 27*0.15 (KV@32k) + 0.5 (overhead) ≈ 12.9 GB
        assert 10.0 <= est32k <= 14.5, f"ternary 27B@32k out of sane range: {est32k}"
        # The Q4_K_M fallback counterfactual would be ≈ 20.2 GB — the
        # ternary class must keep the estimate well below it.
        assert est32k < 16.0

    def test_tn23_tag(self):
        from core.vram_calculator import _parse_quantization

        name, _ = _parse_quantization("model-27b-tn23")
        assert name == "tn23"


class TestLlamaCppEndpointDropdown:
    """V0.4.31 (B1): the build_llamacpp_endpoint_options helper that builds
    the wizard's endpoint-dropdown options (Primary + llamacpp_endpoints)."""

    def test_primary_only_when_no_endpoints(self):
        from ui_qt.components.llamacpp_config import build_llamacpp_endpoint_options

        opts = build_llamacpp_endpoint_options("http://127.0.0.1:8080/v1", "local", [])
        assert len(opts) == 1
        assert opts[0] == {
            "label": "Primary",
            "base_url": "http://127.0.0.1:8080/v1",
            "api_key": "local",
        }

    def test_primary_plus_configured_endpoints(self):
        from ui_qt.components.llamacpp_config import build_llamacpp_endpoint_options

        opts = build_llamacpp_endpoint_options(
            "http://127.0.0.1:8080/v1",
            "local",
            [
                {
                    "base_url": "http://127.0.0.1:8081/v1",
                    "api_key": "local",
                    "label": "Qwen 8081",
                },
                {
                    "base_url": "http://127.0.0.1:8082/v1",
                    "api_key": "secret",
                    "label": "Third",
                },
            ],
        )
        assert len(opts) == 3
        assert opts[0]["label"] == "Primary"
        assert opts[1] == {
            "label": "Qwen 8081",
            "base_url": "http://127.0.0.1:8081/v1",
            "api_key": "local",
        }
        assert opts[2]["api_key"] == "secret"

    def test_skips_empty_and_malformed_endpoints(self):
        from ui_qt.components.llamacpp_config import build_llamacpp_endpoint_options

        opts = build_llamacpp_endpoint_options(
            "http://127.0.0.1:8080/v1",
            "local",
            [
                {"base_url": "", "label": "empty"},  # skipped (empty url)
                "not-a-dict",  # skipped (not a dict)
                {"base_url": "   ", "label": "whitespace"},  # skipped (whitespace)
                {"base_url": "http://127.0.0.1:8081/v1"},  # kept (label defaults to url)
            ],
        )
        assert len(opts) == 2  # Primary + the one valid endpoint
        assert opts[1]["label"] == "http://127.0.0.1:8081/v1"  # label defaults to url
        assert opts[1]["api_key"] == "local"  # api_key defaults to "local"
