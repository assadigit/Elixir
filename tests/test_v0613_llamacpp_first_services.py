"""V0.6.13 — the llama.cpp-first policy extended to the services.

THE OPERATOR'S FOLLOW-UP REPORT (verbatim): "ALSO TAKE NOTE THAT tts,
TRANSCRIBE SERVICE AND PODCAST HAVE SAME PROBLEM, THEY FIND LLM ON
OLLAMA ONLY." Under the V0.6.12 policy (llama-server up = route to it
and the model it serves; Ollama = the always-on fallback), this file
pins the three newly-wired sites:

1. The Podcast Maker script generator — ``generate_podcast_script`` is
   Ollama-native (raw ``/api/generate``), so the policy applies when its
   ``ollama_url`` is LOCAL (``is_local_url`` — a deliberately remote
   URL is never probed, the same treatment cloud providers get).
2. The transcribe summary — ``summarize_transcript`` already followed
   ``summarisation.provider``; the policy now takes over local
   selections with the DETECTED served model.
3. The TTS text normalizer — ``create_normalizer_from_settings``
   (also the podcast-audio normalize step) + the Settings→TTS "Test
   normalization" worker: the OpenAI-compat TextNormalizer is simply
   pointed at the live llama-server, and the Ollama ``/api/tags``
   model discovery is SKIPPED on takeover (with Ollama down it used to
   fail and DISABLE normalization — the reported defect).

Layers:
1. ``is_local_url`` — the V0.6.13 URL-locality predicate.
2. ``generate_podcast_script`` routing (end-to-end, transport faked).
3. ``_generate_podcast_title`` routing (direct — the call site now
   passes ``llamacpp=``; before completion the kwarg did not exist and
   EVERY title call would have raised TypeError).
4. ``summarize_transcript`` routing (the create_provider factory faked).
5. ``create_normalizer_from_settings`` routing (takeover skips the
   Ollama discovery and never persists the served model).
6. The tts_page "Test normalization" worker wiring (source pin — the
   decide lives in the WORKER, never the UI thread, keeping the W-b8
   widget-free-worker and main-thread-snapshot contracts).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared hermetic helpers (the V0.6.12 file's pattern) ────────────────────


class _SettingsStub:
    """The duck-type the decision module + call sites need (``get``/``set``).

    Absent keys fall through to the CALLER's default (the same semantics
    the real Settings has for these reads), so tests exercise the
    production defaults by omission.
    """

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)

    def set(self, key: str, value) -> bool:
        self._v[key] = value
        return True


class _OllamaUrlSettingsStub(_SettingsStub):
    """Adds the get_ollama_url() surface the TTS discovery path reads
    (minimal honest mirror of the canonical 5-key resolver: canonical
    key → legacy keys → default, /v1 stripped)."""

    def get_ollama_url(self) -> str:
        url = str(self.get("llm.ollama_url", "") or "")
        if not url:
            for legacy in (
                "summarisation.endpoint",
                "summarisation.ollama_url",
                "ocr.ollama_url",
                "translation.endpoint",
            ):
                url = str(self.get(legacy, "") or "")
                if url:
                    break
        if not url:
            url = "http://localhost:11434"
        if url.endswith("/v1"):
            url = url[:-3]
        return url.rstrip("/")


class _ProbeSpy:
    """Monkeypatch stand-in for list_llamacpp_models that records calls."""

    def __init__(self, models: list[str] | None = None, raise_on_call: bool = False) -> None:
        self.models = list(models or [])
        self.raise_on_call = raise_on_call
        self.calls: list[tuple[str, str, int]] = []

    def __call__(self, base_url: str, api_key: str, timeout: int = 10) -> list[str]:
        self.calls.append((base_url, api_key, timeout))
        if self.raise_on_call:
            raise RuntimeError("probe exploded")
        return list(self.models)


class _FakeResp:
    """The status_code/json contract every wired site needs."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    """Records every POST/GET; returns (or raises) the installed answer."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str, dict]] = []  # (method, url, kwargs)

    def _record(self, method: str, url: str, kwargs: dict):
        self.calls.append((method, url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response

    def post(self, url: str, **kwargs):
        return self._record("POST", url, kwargs)

    def get(self, url: str, **kwargs):
        return self._record("GET", url, kwargs)

    def posts(self) -> list[tuple[str, dict]]:
        return [(url, kw) for _m, url, kw in self.calls if _m == "POST"]

    def gets(self) -> list[tuple[str, dict]]:
        return [(url, kw) for _m, url, kw in self.calls if _m == "GET"]


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    """Every test starts with an empty probe cache (and leaves it empty)."""
    from core.llm import local_fallback

    local_fallback.clear_llamacpp_probe_cache()
    yield
    local_fallback.clear_llamacpp_probe_cache()


_LLAMACPP_URL = "http://127.0.0.1:8080/v1"
_OLLAMA_URL = "http://localhost:11434"

# One input bullet; the fake script JSON covers "bullet 1" so no
# gap-fill retries fire — the run makes exactly TWO LLM POSTs
# (script + title).
_SOURCE_ONE_BULLET = "- The single key point of this chapter"
_SCRIPT_JSON = (
    '[{"host": "A", "text": "Welcome to the show.", '
    '"source_ref": "intro", "segment_type": "intro"}, '
    '{"host": "B", "text": "The single key point, expanded.", '
    '"source_ref": "bullet 1", "segment_type": "content"}, '
    '{"host": "A", "text": "Wrapping up now.", '
    '"source_ref": "conclusion", "segment_type": "conclusion"}]'
)


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — is_local_url (the V0.6.13 URL-locality predicate)
# ═════════════════════════════════════════════════════════════════════════════


class TestIsLocalUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434",
            "http://localhost:11434/v1",
            "http://127.0.0.1:8080/v1",
            "http://0.0.0.0:9000",
            "http://[::1]:8080/v1",
            "https://LOCALHOST:443/v1",
        ],
    )
    def test_loopback_hosts_are_local(self, url):
        from core.llm.local_fallback import is_local_url

        assert is_local_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openrouter.ai/v1",
            "http://192.168.1.50:11434",  # a LAN Ollama — a deliberate remote choice
            "http://10.0.0.5:11434",
            "http://example.com",
            "",
            "   ",
            "not a url",
            None,
        ],
    )
    def test_non_loopback_malformed_and_empty_are_not_local(self, url):
        from core.llm.local_fallback import is_local_url

        assert is_local_url(url) is False


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — generate_podcast_script routing (the reported call site)
# ═════════════════════════════════════════════════════════════════════════════


class _PodcastHarness:
    """generate_podcast_script + faked transport + faked probe + Settings."""

    def __init__(
        self,
        monkeypatch,
        values: dict,
        probe_models: list[str],
        takeover: bool = False,
    ) -> None:
        import utils.network as net_mod
        from utils.settings import Settings

        self.settings = _SettingsStub(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        self.spy = _ProbeSpy(models=probe_models)
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)

        payload = (
            {"choices": [{"message": {"content": _SCRIPT_JSON}}]}
            if takeover
            else {"response": _SCRIPT_JSON}
        )
        self.session = _FakeSession(response=_FakeResp(payload))
        monkeypatch.setattr(net_mod, "session_for_url", lambda url: self.session)

        self.logs: list[tuple[str, str]] = []

    def run(self, ollama_url: str = _OLLAMA_URL, model: str = "req-model"):
        from core.podcast.script_generator import generate_podcast_script

        return generate_podcast_script(
            source_text=_SOURCE_ONE_BULLET,
            mode="conversational",
            tone="casual",
            temperature=0.7,
            language="en",
            ollama_url=ollama_url,
            model=model,
            max_retries=1,
            log_callback=lambda m, level="INFO": self.logs.append((level, m)),
        )

    def info_logs(self) -> list[str]:
        return [m for _lvl, m in self.logs]


class TestPodcastScriptRouting:
    def test_live_llamacpp_takes_over_local_ollama_url(self, monkeypatch):
        """THE POLICY at the reported site: the Podcast Maker's Ollama-native
        call, with a live llama-server, routes to llama.cpp — script AND
        title — with the DETECTED served model + bearer key."""
        h = _PodcastHarness(
            monkeypatch,
            values={
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
                "summarisation.llamacpp_api_key": "sekrit",
            },
            probe_models=["served-27b"],
            takeover=True,
        )
        result = h.run()
        assert result.error is None, result.error
        assert result.lines, "the script must parse"
        assert result.title, "the title call must produce a title"
        # exactly the two LLM POSTs: script + title (no gap-fill — the
        # fake script covers the single bullet)
        assert len(h.session.posts()) == 2, h.session.calls
        urls = {url for url, _kw in h.session.posts()}
        assert urls == {f"{_LLAMACPP_URL}/chat/completions"}, urls
        assert all("/api/generate" not in url for url, _kw in h.session.posts())
        first_url, first_kw = h.session.posts()[0]
        assert first_kw["json"]["model"] == "served-27b"  # detected wins (V0.4.30)
        assert first_kw["json"]["stream"] is False
        assert first_kw["headers"] == {"Authorization": "Bearer sekrit"}
        # the title call (the second POST) routes through the takeover too
        _t_url, title_kw = h.session.posts()[1]
        assert title_kw["json"]["model"] == "served-27b"
        assert title_kw["json"]["max_tokens"] == 50
        # the served model replaced the request's model pick (the log says so)
        assert any("🤖 Model: served-27b" in m for m in h.info_logs())
        assert any("llama.cpp detected" in m for m in h.info_logs())

    def test_dead_llamacpp_runs_configured_ollama_byte_identical(self, monkeypatch):
        """llama.cpp off → the configured Ollama path runs exactly as
        V0.6.12: the native /api/generate payload, no auth header."""
        h = _PodcastHarness(monkeypatch, values={}, probe_models=[])
        result = h.run(model="req-model")
        assert result.error is None, result.error
        assert result.lines
        assert len(h.session.posts()) == 2, h.session.calls
        urls = {url for url, _kw in h.session.posts()}
        assert urls == {f"{_OLLAMA_URL}/api/generate"}, urls
        first_url, first_kw = h.session.posts()[0]
        assert first_kw["json"]["model"] == "req-model"
        assert first_kw["json"]["stream"] is False
        assert first_kw["json"]["options"] == {
            "temperature": 0.7,
            "num_predict": 4096,
            "num_ctx": 131072,
        }
        assert "headers" not in first_kw
        assert any("not reachable" in m for m in h.info_logs())

    def test_remote_ollama_url_is_never_probed(self, monkeypatch):
        """A deliberately-remote ollama_url (a LAN Ollama) gets the cloud
        treatment: no probe, the configured URL gets the calls."""
        h = _PodcastHarness(
            monkeypatch,
            values={"summarisation.llamacpp_base_url": _LLAMACPP_URL},
            probe_models=["would-take-over"],
        )
        result = h.run(ollama_url="http://192.168.1.50:11434")
        assert result.error is None, result.error
        assert h.spy.calls == []  # never probed
        urls = {url for url, _kw in h.session.posts()}
        assert urls == {"http://192.168.1.50:11434/api/generate"}, urls

    def test_kill_switch_restores_pre_v0612_behavior(self, monkeypatch):
        """local.llamacpp_first=false → no probe, straight passthrough."""
        h = _PodcastHarness(
            monkeypatch,
            values={
                "local.llamacpp_first": False,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-would-take-over"],
        )
        result = h.run()
        assert result.error is None, result.error
        assert h.spy.calls == []
        urls = {url for url, _kw in h.session.posts()}
        assert urls == {f"{_OLLAMA_URL}/api/generate"}, urls

    def test_connection_error_names_the_backend(self, monkeypatch):
        """The reported failure shape (Ollama off, llama.cpp off) — the
        raw urllib3 blob is replaced by a line naming llama.cpp."""
        import requests

        h = _PodcastHarness(
            monkeypatch,
            values={"summarisation.llamacpp_base_url": _LLAMACPP_URL},
            probe_models=["served-27b"],
            takeover=True,
        )
        h.session.error = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded (WinError 10061)"
        )
        result = h.run()
        assert result.error is not None
        assert "llama-server" in result.error or "llama.cpp" in result.error
        assert "HTTPConnectionPool" not in result.error


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — _generate_podcast_title routing (the completion of the wiring)
# ═════════════════════════════════════════════════════════════════════════════


class TestPodcastTitleRouting:
    def _lines(self):
        from core.podcast.script_generator import ScriptLine

        return [
            ScriptLine(
                host="A",
                text="Welcome to the show everyone.",
                source_ref="intro",
                segment_type="content",  # the fallback-title loop reads ONLY content lines
            )
        ]

    def _install(self, monkeypatch, payload=None, error=None):
        import utils.network as net_mod

        session = _FakeSession(
            response=_FakeResp(payload) if payload is not None else None, error=error
        )
        monkeypatch.setattr(net_mod, "session_for_url", lambda url: session)
        return session

    def test_default_none_keeps_the_ollama_path(self, monkeypatch):
        """The pre-V0.6.13 contract, pinned: llamacpp=None (the default)
        POSTs the native Ollama payload. (Pre-completion the call site
        passed ``llamacpp=`` into a signature without it — TypeError on
        EVERY title call.)"""
        session = self._install(monkeypatch, {"response": "A Great Podcast Title"})
        from core.podcast.script_generator import _generate_podcast_title

        title = _generate_podcast_title(
            self._lines(), _OLLAMA_URL, "m", 0.7, lambda m, level="INFO": None
        )
        assert title == "A Great Podcast Title"
        url, kw = session.posts()[0]
        assert url == f"{_OLLAMA_URL}/api/generate"
        assert kw["json"]["model"] == "m"
        assert kw["json"]["options"]["num_predict"] == 50
        assert "headers" not in kw

    def test_takeover_routes_the_title_call(self, monkeypatch):
        from core.llm.local_fallback import LlamacppFirstDecision
        from core.podcast.script_generator import _generate_podcast_title

        session = self._install(
            monkeypatch, {"choices": [{"message": {"content": "An Even Better Title"}}]}
        )
        decision = LlamacppFirstDecision(True, _LLAMACPP_URL, "served-x", "sekrit", "")
        title = _generate_podcast_title(
            self._lines(), _OLLAMA_URL, "m", 0.7, lambda m, level="INFO": None, llamacpp=decision
        )
        assert title == "An Even Better Title"
        url, kw = session.posts()[0]
        assert url == f"{_LLAMACPP_URL}/chat/completions"
        assert kw["json"]["model"] == "served-x"  # the DETECTED served model
        assert kw["json"]["max_tokens"] == 50
        assert kw["headers"] == {"Authorization": "Bearer sekrit"}

    def test_takeover_connection_error_falls_back_to_source_ref(self, monkeypatch):
        """The pre-existing fail-soft survives the takeover: an exception
        in the title call → the first content line's words become the
        title (never a crash, never an empty title)."""
        import requests

        from core.llm.local_fallback import LlamacppFirstDecision
        from core.podcast.script_generator import _generate_podcast_title

        self._install(
            monkeypatch, error=requests.exceptions.ConnectionError("refused (WinError 10061)")
        )
        decision = LlamacppFirstDecision(True, _LLAMACPP_URL, "served-x", "local", "")
        title = _generate_podcast_title(
            self._lines(), _OLLAMA_URL, "m", 0.7, lambda m, level="INFO": None, llamacpp=decision
        )
        assert title == "Welcome-the-show-everyone"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 4 — summarize_transcript routing (the transcribe service)
# ═════════════════════════════════════════════════════════════════════════════


class _TranscribeHarness:
    """summarize_transcript + faked create_provider + faked probe."""

    def __init__(self, monkeypatch, values: dict, probe_models: list[str]) -> None:
        import core.llm.llm_provider as lp
        from utils.settings import Settings

        self.settings = _SettingsStub(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        self.spy = _ProbeSpy(models=probe_models)
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)

        self.captured: dict = {}
        captured = self.captured

        class _FakeProvider:
            base_url = "http://localhost:11434"

            def complete_streaming(
                self, prompt, temperature=None, max_tokens=None, model=None, on_chunk=None
            ):
                captured["call"] = {"prompt": prompt, "model": model}
                return "# Notes\n\n- a point"

        def _factory(provider, settings, log_callback=None, supervisor=None):
            captured["provider"] = provider
            captured["settings"] = settings
            prov = _FakeProvider()
            captured["instance"] = prov
            return prov

        monkeypatch.setattr(lp, "create_provider", _factory)
        self.logs: list[tuple[str, str]] = []

    def run(self, model: str = "picked-m", ollama_url: str = _OLLAMA_URL):
        from core.transcribe.transcribe_service import summarize_transcript

        return summarize_transcript(
            "some transcript text",
            model=model,
            ollama_url=ollama_url,
            log_callback=lambda m, level="INFO": self.logs.append((level, m)),
        )

    def info_logs(self) -> list[str]:
        return [m for _lvl, m in self.logs]


class TestTranscribeSummarizeRouting:
    def test_live_llamacpp_takes_over_with_served_model(self, monkeypatch):
        """THE REPORT ("TRANSCRIBE SERVICE ... FIND[S] LLM ON OLLAMA ONLY"):
        a live llama-server takes the call through the factory's llamacpp
        branch with the DETECTED served model, overriding the dialog's
        model pick (the V0.4.30 precedent)."""
        h = _TranscribeHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-70b"],
        )
        out = h.run(model="picked-m")
        assert out == "# Notes\n\n- a point"
        assert h.captured["provider"] == "llamacpp"
        assert h.captured["call"]["model"] == "served-70b"
        assert any("llama.cpp detected" in m for m in h.info_logs())

    def test_dead_llamacpp_uses_configured_provider_and_model(self, monkeypatch):
        h = _TranscribeHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=[],
        )
        out = h.run(model="picked-m")
        assert out == "# Notes\n\n- a point"
        assert h.captured["provider"] == "ollama"
        assert h.captured["call"]["model"] == "picked-m"

    def test_cloud_provider_is_never_probed(self, monkeypatch):
        h = _TranscribeHarness(
            monkeypatch,
            values={
                "summarisation.provider": "openrouter",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["would-take-over"],
        )
        h.run(model="picked-m")
        assert h.spy.calls == []
        assert h.captured["provider"] == "openrouter"
        assert h.captured["call"]["model"] == "picked-m"

    def test_kill_switch_restores_configured_path(self, monkeypatch):
        h = _TranscribeHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "local.llamacpp_first": False,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-70b"],
        )
        h.run(model="picked-m")
        assert h.spy.calls == []
        assert h.captured["provider"] == "ollama"
        assert h.captured["call"]["model"] == "picked-m"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 5 — create_normalizer_from_settings routing (the TTS normalizer)
# ═════════════════════════════════════════════════════════════════════════════


class _TtsFactoryHarness:
    """create_normalizer_from_settings + faked transport + faked probe."""

    def __init__(self, monkeypatch, values: dict, probe_models: list[str]) -> None:
        import utils.network as net_mod
        from utils.settings import Settings

        self.settings = _OllamaUrlSettingsStub(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        self.spy = _ProbeSpy(models=probe_models)
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)

        # the /api/tags discovery answer (the V4.7.24 auto-discovery path).
        # NOTE: normalizer.py binds session_for_url at MODULE level (line 47)
        # — patching utils.network is NOT enough (the module may already be
        # imported, freezing the first binding); patch the name where it is
        # USED: core.tts.normalizer.session_for_url.
        import core.tts.normalizer as norm_mod

        self.session = _FakeSession(
            response=_FakeResp({"models": [{"name": "olmocr:v0.1"}, {"name": "qwen3:8b"}]})
        )
        monkeypatch.setattr(norm_mod, "session_for_url", lambda url: self.session)
        monkeypatch.setattr(net_mod, "session_for_url", lambda url: self.session)

        self.logs: list[tuple[str, str]] = []

    def create(self):
        from core.tts.normalizer import create_normalizer_from_settings

        return create_normalizer_from_settings(
            log_callback=lambda m, level="INFO": self.logs.append((level, m))
        )

    def info_logs(self) -> list[str]:
        return [m for _lvl, m in self.logs]


class TestTtsNormalizerFactoryRouting:
    def test_live_llamacpp_takes_over_endpoint_model_and_key(self, monkeypatch):
        """THE REPORT ("TTS ... FIND[S] LLM ON OLLAMA ONLY"): the
        TextNormalizer — already OpenAI-compat — is pointed at the live
        llama-server with the DETECTED served model + bearer key, and
        the Ollama /api/tags discovery NEVER fires (with Ollama down it
        used to fail and disable normalization)."""
        h = _TtsFactoryHarness(
            monkeypatch,
            values={
                "tts.normalize_enabled": True,
                "tts.normalize_model": "ollama-m",
                "tts.normalize_endpoint": "http://localhost:11434/v1",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
                "summarisation.llamacpp_api_key": "sekrit",
            },
            probe_models=["served-qwen"],
        )
        norm = h.create()
        assert norm is not None
        assert norm.endpoint == _LLAMACPP_URL
        assert norm.model == "served-qwen"  # detected wins over "ollama-m"
        assert norm.api_key == "sekrit"
        assert h.session.calls == []  # no /api/tags discovery on takeover
        # the served model is NOT persisted (that setting names the
        # configured backend's model for the no-llama.cpp case)
        assert h.settings.get("tts.normalize_model") == "ollama-m"
        assert any("llama.cpp detected" in m for m in h.info_logs())

    def test_dead_llamacpp_keeps_configured_path(self, monkeypatch):
        h = _TtsFactoryHarness(
            monkeypatch,
            values={
                "tts.normalize_enabled": True,
                "tts.normalize_model": "ollama-m",
                "tts.normalize_api_key": "sk-norm",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=[],
        )
        norm = h.create()
        assert norm is not None
        assert norm.endpoint == "http://localhost:11434/v1"
        assert norm.model == "ollama-m"
        assert norm.api_key == "sk-norm"
        assert h.session.calls == []  # model set → no discovery needed

    def test_dead_llamacpp_ollama_discovery_still_works(self, monkeypatch):
        """Pin: the V4.7.24 auto-discovery survives the wiring — empty
        model + dead llama.cpp → /api/tags → first non-OCR model,
        persisted exactly as before."""
        h = _TtsFactoryHarness(
            monkeypatch,
            values={
                "tts.normalize_enabled": True,
                "tts.normalize_model": "",
                "summarisation.model": "",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=[],
        )
        norm = h.create()
        assert norm is not None
        assert norm.model == "qwen3:8b"
        assert h.settings.get("tts.normalize_model") == "qwen3:8b"  # V4.7.24 persistence
        assert len(h.session.gets()) == 1
        tags_url, _kw = h.session.gets()[0]
        assert tags_url == "http://localhost:11434/api/tags"

    def test_remote_endpoint_is_never_probed(self, monkeypatch):
        h = _TtsFactoryHarness(
            monkeypatch,
            values={
                "tts.normalize_enabled": True,
                "tts.normalize_model": "ollama-m",
                "tts.normalize_endpoint": "https://api.openrouter.ai/v1",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["would-take-over"],
        )
        norm = h.create()
        assert norm is not None
        assert h.spy.calls == []
        assert norm.endpoint == "https://api.openrouter.ai/v1"
        assert norm.model == "ollama-m"

    def test_kill_switch_keeps_configured_path(self, monkeypatch):
        h = _TtsFactoryHarness(
            monkeypatch,
            values={
                "tts.normalize_enabled": True,
                "tts.normalize_model": "ollama-m",
                "local.llamacpp_first": False,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["would-take-over"],
        )
        norm = h.create()
        assert norm is not None
        assert h.spy.calls == []
        assert norm.endpoint == "http://localhost:11434/v1"
        assert norm.model == "ollama-m"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 6 — the Settings→TTS "Test normalization" worker (source pin)
# ═════════════════════════════════════════════════════════════════════════════


_TTS_PAGE = _project_root / "ui_qt" / "settings" / "tts_page.py"


def _normalization_section_src() -> str:
    src = _TTS_PAGE.read_text(encoding="utf-8")
    start = src.index("class TtsNormalizationSection")
    end = src.index("\nclass ", start + 10)
    return src[start:end]


class TestTtsPageTestButtonWiring:
    """The Settings→TTS "Test normalization" button consults the policy
    (V0.6.13) — in the WORKER, never the UI thread, keeping the W-b8 /
    W-b11 contracts (widget-free worker body, main-thread snapshot)."""

    def test_worker_consults_the_policy(self):
        src = _normalization_section_src()
        assert "decide_llamacpp_first" in src
        assert "is_local_url(endpoint)" in src

    def test_policy_lives_inside_the_worker_closure(self):
        src = _normalization_section_src()
        before_work, _, work = src.partition("def _work")
        # the decide block is INSIDE the worker body (after its def line)…
        assert "decide_llamacpp_first" in work
        # …and the snapshot lines stay in the click slot BEFORE it
        assert "endpoint = self.endpoint_edit.text()" in before_work
        assert "api_key = self.apikey_edit.text()" in before_work
        assert "model = self.model_edit.text()" in before_work

    def test_worker_policy_block_reads_no_widgets(self):
        """The V0.6.13 block must not reintroduce widget reads into the
        worker (the W-b11 contract test_v182049 pins repo-wide; this is
        the local mirror for the new block)."""
        src = _normalization_section_src()
        _before, _, work = src.partition("def _work")
        work_body = work.split("norm = TextNormalizer", 1)[0]
        for widget in ("endpoint_edit", "apikey_edit", "model_edit", "context_combo"):
            assert f"self.{widget}" not in work_body, widget
