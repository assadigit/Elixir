"""V0.6.69 — the local-LLM status lights pins.

THE FIELD REPORT (2026-10-26, on top of the shipped V0.6.68): the startup
"Ollama not running" QMessageBox had to go, replaced by live lights that
actively watch for locally-running LLM clients::

    "do not show the error of ollama when app loads. instead show a green
     light that shows whether ollama or any other locally famous LLM client
     is on or not, it must actively look for ollama or llama.cpp server as
     they're online and show a green light for them on ui instead"

THE FIX (three layers, all pinned here):

  1. ``core/system/local_llm_monitor.py`` — the Qt-free probe layer:
     a main-thread endpoint snapshot (``snapshot_endpoints``) + pure
     never-raise probes for the three locally-famous clients (Ollama on
     :11434, llama.cpp server on the V0.6.55 port ladder 8080→8000→9931,
     LM Studio on :1234). FRESH by design — it must NOT go through
     ``local_fallback._probe_llamacpp`` (the routing layer's 30 s TTL
     cache exists to bound ROUTING cost, not to keep a status light
     honest: a server started mid-session goes green on the NEXT tick).
  2. ``ui_qt/components/llm_lights.py`` — LocalLLMLights: one chip per
     client (green = answered, gray = not running, amber = checking),
     rich tooltips, and a width-adaptive mode ladder (full → dots → one
     aggregate dot) so the crowded top bar never clips.
  3. ``ui_qt/app.py`` — the old ``_warn_ollama``/``_show_ollama_warning``
     dialog pair is DELETED; a QTimer poll loop (``LLM_LIGHTS_POLL_
     INTERVAL_S``) probes off a SimpleWorker, applies verdicts on the
     main thread, stops on close, and the lights re-paint on theme
     toggle + adapt on every resize.

THE PINS: layer-1 tests are hermetic (network helpers monkeypatched at
the module under test, the test_v0655 pattern — no sockets ever open);
layers 2/3 are source pins (the V0.6.65/V0.6.67 pattern — the suite is
deliberately Qt-free; widget BEHAVIOR was proven by the offscreen smoke
that shipped this change)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_APP_SRC = (_project_root / "ui_qt" / "app.py").read_text(encoding="utf-8")
_LIGHTS_SRC = (_project_root / "ui_qt" / "components" / "llm_lights.py").read_text(encoding="utf-8")
_MON_SRC = (_project_root / "core" / "system" / "local_llm_monitor.py").read_text(encoding="utf-8")

# The well-known endpoints (single source with the module under test).
_OLLAMA_URL = "http://localhost:11434"
_LLAMACPP_DEFAULT = "http://127.0.0.1:8080/v1"
_ALT_8000 = "http://127.0.0.1:8000/v1"
_ALT_9931 = "http://127.0.0.1:9931/v1"
_LMSTUDIO_URL = "http://localhost:1234/v1"


class _SettingsStub:
    """The duck-type the monitor needs (``.get``) — the test_v0655
    pattern: absent keys fall through to the CALLER's default so tests
    exercise production defaults by omission."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)


class _OllamaSpy:
    """Stand-in for is_ollama_reachable + list_ollama_models."""

    def __init__(self, reachable: bool = True, models: list | None = None) -> None:
        self.reachable = reachable
        self.models = list(models or [])
        self.reach_calls: list[tuple[str, int]] = []
        self.list_calls: list[str] = []

    def reach(self, base_url: str = _OLLAMA_URL, timeout: int = 5) -> bool:
        self.reach_calls.append((base_url, timeout))
        return self.reachable

    def list_models(self, base_url: str = _OLLAMA_URL, timeout: int = 10) -> list:
        self.list_calls.append(base_url)
        return list(self.models)

    def explode(self, *a, **k):
        raise RuntimeError("simulated probe crash")


class _ModelsSpy:
    """Stand-in for list_llamacpp_models (llama.cpp AND LM Studio — the
    same OpenAI-shape listing call, answered per-URL). Records the
    (url, api_key) of every probe."""

    def __init__(self, live: dict[str, list[str]] | None = None) -> None:
        self.live = dict(live or {})
        self.calls: list[tuple[str, str]] = []

    def __call__(self, base_url: str, api_key: str = "local", timeout: int = 10):
        self.calls.append((base_url, api_key))
        return list(self.live.get(base_url, []))


def _install(monkeypatch, ollama: _OllamaSpy | None, models: _ModelsSpy | None):
    """Patch the transport helpers AT the module under test (its own
    imported names — the test_v0655 hermetic pattern)."""
    from core.system import local_llm_monitor as mon

    if ollama is not None:
        monkeypatch.setattr(mon, "is_ollama_reachable", ollama.reach)
        monkeypatch.setattr(mon, "list_ollama_models", ollama.list_models)
    if models is not None:
        monkeypatch.setattr(mon, "list_llamacpp_models", models)
    return mon


def _secret(monkeypatch, value: str):
    """Freeze the llamacpp api-key secret (the snapshot reads it on the
    main thread via get_secret)."""
    import core.system.secrets as secrets_mod

    monkeypatch.setattr(secrets_mod, "get_secret", lambda *a, **k: value)


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1a — the endpoint snapshot (main-thread, defaults, secrets)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0669SnapshotEndpoints:
    def test_fresh_settings_snapshot_the_well_known_defaults(self, monkeypatch):
        """Absence of configuration = the well-known ports (the production
        defaults by omission — the _SettingsStub contract)."""
        _secret(monkeypatch, "")
        from core.system.local_llm_monitor import snapshot_endpoints

        spec = snapshot_endpoints(_SettingsStub())
        assert spec.ollama_url == _OLLAMA_URL
        assert spec.llamacpp_base_url == _LLAMACPP_DEFAULT
        assert spec.lmstudio_url == _LMSTUDIO_URL

    def test_explicit_urls_win_and_blank_falls_back(self, monkeypatch):
        _secret(monkeypatch, "")
        from core.system.local_llm_monitor import snapshot_endpoints

        spec = snapshot_endpoints(
            _SettingsStub(
                {
                    "summarisation.ollama_url": "  http://127.0.0.1:11500  ",
                    "summarisation.llamacpp_base_url": "",  # blank → default
                    "summarisation.lmstudio_url": "http://127.0.0.1:1235/v1",
                }
            )
        )
        assert spec.ollama_url == "http://127.0.0.1:11500"  # stripped
        assert spec.llamacpp_base_url == _LLAMACPP_DEFAULT  # blank → default
        assert spec.lmstudio_url == "http://127.0.0.1:1235/v1"

    def test_api_key_secret_with_local_fallback(self, monkeypatch):
        """The bearer mirrors resolve_llamacpp_base_url's 'local' fallback
        — the light probes EXACTLY what a real call would."""
        _secret(monkeypatch, "sekret")
        from core.system.local_llm_monitor import snapshot_endpoints

        assert snapshot_endpoints(_SettingsStub()).llamacpp_api_key == "sekret"
        _secret(monkeypatch, "")
        assert snapshot_endpoints(_SettingsStub()).llamacpp_api_key == "local"

    def test_settings_layer_explosion_falls_back_to_defaults(self, monkeypatch):
        """DESIGN RULE 3 starts at the snapshot: a raising settings layer
        still yields a fully-formed spec (probe the well-known ports)."""

        class _Boom:
            def get(self, *a, **k):
                raise RuntimeError("settings layer down")

        _secret(monkeypatch, "")
        from core.system.local_llm_monitor import snapshot_endpoints

        spec = snapshot_endpoints(_Boom())  # type: ignore[arg-type]
        assert spec.ollama_url == _OLLAMA_URL
        assert spec.llamacpp_base_url == _LLAMACPP_DEFAULT
        assert spec.lmstudio_url == _LMSTUDIO_URL

    def test_secret_layer_explosion_defaults_the_key(self, monkeypatch):
        import core.system.secrets as secrets_mod

        def _boom(*a, **k):
            raise RuntimeError("secrets layer down")

        monkeypatch.setattr(secrets_mod, "get_secret", _boom)
        from core.system.local_llm_monitor import snapshot_endpoints

        assert snapshot_endpoints(_SettingsStub()).llamacpp_api_key == "local"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1b — the probes (hermetic: no socket ever opens)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0669OllamaProbe:
    def test_online_with_models_reports_the_count(self, monkeypatch):
        _install(monkeypatch, _OllamaSpy(True, ["llama3", "qwen2.5"]), None)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [ollama, *_] = probe_local_llm_clients(LocalLLMEndpoints())
        assert ollama.key == "ollama" and ollama.online is True
        assert "2 models" in ollama.detail
        assert ollama.endpoint == _OLLAMA_URL

    def test_online_with_zero_models_is_honest(self, monkeypatch):
        _install(monkeypatch, _OllamaSpy(True, []), None)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [ollama, *_] = probe_local_llm_clients(LocalLLMEndpoints())
        assert ollama.online is True
        assert "no models pulled yet" in ollama.detail

    def test_offline_names_the_start_command(self, monkeypatch):
        _install(monkeypatch, _OllamaSpy(False), None)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [ollama, *_] = probe_local_llm_clients(LocalLLMEndpoints())
        assert ollama.online is False
        assert "not running" in ollama.detail
        assert "ollama serve" in ollama.detail  # actionable, but a light — not a dialog

    def test_probe_explosion_is_offline_not_crash(self, monkeypatch):
        """DESIGN RULE 3: a status light that can crash the app is worse
        than no light."""
        boom = _OllamaSpy(False)
        boom.reach = boom.explode
        _install(monkeypatch, boom, None)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [ollama, *_] = probe_local_llm_clients(LocalLLMEndpoints())
        assert ollama.online is False

    def test_configured_url_is_probed_not_the_default(self, monkeypatch):
        spy = _OllamaSpy(True, ["m"])
        _install(monkeypatch, spy, None)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        probe_local_llm_clients(LocalLLMEndpoints(ollama_url="http://127.0.0.1:11500"))
        assert spy.reach_calls and spy.reach_calls[0][0] == "http://127.0.0.1:11500"


def _ladder_calls(spy: _ModelsSpy) -> list[str]:
    """The llama.cpp-ladder probe calls (the spy is SHARED with the LM
    Studio probe — both go through list_llamacpp_models — so the LM
    Studio URL is filtered out; in these tests it is always the
    well-known default, disjoint from every ladder URL)."""
    return [u for u, _k in spy.calls if u != _LMSTUDIO_URL]


class TestV0669LlamacppProbe:
    def test_default_dead_8000_live_probes_in_order_and_stops(self, monkeypatch):
        """The V0.6.55 ladder, mirrored: 8080 first, then 8000, then 9931
        — and the first LIVE port wins (9931 never probed)."""
        spy = _ModelsSpy({_ALT_8000: ["gpt-oss-20b"]})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, llamacpp, _] = probe_local_llm_clients(LocalLLMEndpoints())
        assert _ladder_calls(spy) == [_LLAMACPP_DEFAULT, _ALT_8000]
        assert llamacpp.online is True
        assert llamacpp.endpoint == _ALT_8000
        assert "port auto-detected" in llamacpp.detail
        assert "gpt-oss-20b" in llamacpp.detail  # what the server actually serves

    def test_default_live_never_probes_alternates(self, monkeypatch):
        spy = _ModelsSpy({_LLAMACPP_DEFAULT: ["model-x"]})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, llamacpp, _] = probe_local_llm_clients(LocalLLMEndpoints())
        assert _ladder_calls(spy) == [_LLAMACPP_DEFAULT]
        assert llamacpp.online is True
        assert "port auto-detected" not in llamacpp.detail

    def test_explicit_url_is_probed_alone(self, monkeypatch):
        """The V0.6.12 contract, mirrored: an explicitly configured URL is
        a deliberate operator choice — never second-guessed, never probed
        beyond itself."""
        spy = _ModelsSpy({})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, llamacpp, _] = probe_local_llm_clients(
            LocalLLMEndpoints(llamacpp_base_url="http://127.0.0.1:9000/v1")
        )
        assert _ladder_calls(spy) == ["http://127.0.0.1:9000/v1"]
        assert llamacpp.online is False  # dead explicit URL stays dead

    def test_all_ladder_ports_dead_lists_every_probe(self, monkeypatch):
        spy = _ModelsSpy({})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, llamacpp, _] = probe_local_llm_clients(LocalLLMEndpoints())
        assert llamacpp.online is False
        assert llamacpp.probed == (_LLAMACPP_DEFAULT, _ALT_8000, _ALT_9931)
        assert "probed: " in llamacpp.tooltip

    def test_bearer_key_flows_from_the_snapshot(self, monkeypatch):
        spy = _ModelsSpy({_LLAMACPP_DEFAULT: ["m"]})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        probe_local_llm_clients(LocalLLMEndpoints(llamacpp_api_key="sekret"))
        assert spy.calls[0][1] == "sekret"

    def test_probe_explosion_is_offline_not_crash(self, monkeypatch):
        class _Boom(_ModelsSpy):
            def __call__(self, *a, **k):
                raise RuntimeError("simulated crash")

        _install(monkeypatch, None, _Boom())
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, llamacpp, _] = probe_local_llm_clients(LocalLLMEndpoints())
        assert llamacpp.online is False


class TestV0669LmstudioProbe:
    def test_online_reports_served_model(self, monkeypatch):
        spy = _ModelsSpy({_LMSTUDIO_URL: ["qwen2.5-7b-instruct"]})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, _, lmstudio] = probe_local_llm_clients(LocalLLMEndpoints())
        assert lmstudio.key == "lmstudio" and lmstudio.online is True
        assert lmstudio.endpoint == _LMSTUDIO_URL
        assert "qwen2.5-7b-instruct" in lmstudio.detail

    def test_offline_is_ordinary(self, monkeypatch):
        spy = _ModelsSpy({})
        _install(monkeypatch, None, spy)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        [_, _, lmstudio] = probe_local_llm_clients(LocalLLMEndpoints())
        assert lmstudio.online is False
        assert "not running" in lmstudio.detail


class TestV0669ProbeContract:
    def test_three_clients_in_display_order(self, monkeypatch):
        """Display order = probe order = the lights' chip order."""
        _install(monkeypatch, _OllamaSpy(False), _ModelsSpy({}))
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        statuses = probe_local_llm_clients(LocalLLMEndpoints())
        assert [s.key for s in statuses] == ["ollama", "llamacpp", "lmstudio"]
        assert [s.name for s in statuses] == ["Ollama", "llama.cpp", "LM Studio"]

    def test_poll_interval_is_short_and_constant(self):
        """ "actively look for ollama or llama.cpp server as they're
        online" — a short constant cadence (loopback GETs are ~free)."""
        from core.system.local_llm_monitor import LLM_LIGHTS_POLL_INTERVAL_S

        assert LLM_LIGHTS_POLL_INTERVAL_S == 5

    def test_timeout_is_the_subsecond_probe_budget(self, monkeypatch):
        """Every probe runs on the 2 s subsecond budget (the policy leaf),
        never the 5-10 s UI-probe family — the loop ticks every 5 s."""
        ollama = _OllamaSpy(True, ["m"])
        models = _ModelsSpy({_LLAMACPP_DEFAULT: ["m"], _LMSTUDIO_URL: ["m"]})
        _install(monkeypatch, ollama, models)
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients
        from core.system.timeouts import SUBSECOND_PROBE_TIMEOUT_S

        probe_local_llm_clients(LocalLLMEndpoints())
        assert ollama.reach_calls[0][1] == SUBSECOND_PROBE_TIMEOUT_S

    def test_offline_tooltip_carries_the_probed_line_online_does_not(self, monkeypatch):
        _install(monkeypatch, _OllamaSpy(False), _ModelsSpy({}))
        from core.system.local_llm_monitor import LocalLLMEndpoints, probe_local_llm_clients

        statuses = probe_local_llm_clients(LocalLLMEndpoints())
        for s in statuses:
            assert "probed: " in s.tooltip  # offline → evidence of what was tried
        _install(monkeypatch, _OllamaSpy(True, ["m"]), _ModelsSpy({}))
        statuses = probe_local_llm_clients(LocalLLMEndpoints())
        assert "probed: " not in statuses[0].tooltip  # online → just the verdict


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — the widget source pins (the suite is Qt-free by doctrine)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0669LightsSourcePins:
    def test_one_chip_per_locally_famous_client(self):
        for name in ("Ollama", "llama.cpp", "LM Studio"):
            assert name in _LIGHTS_SRC
        # the chip keys are IMPORTED from the monitor (single source),
        # never re-defined — the import block names all three.
        assert "from core.system.local_llm_monitor import" in _LIGHTS_SRC
        for key in ("OLLAMA_KEY", "LLAMACPP_KEY", "LMSTUDIO_KEY"):
            assert key in _LIGHTS_SRC

    def test_color_semantics_green_gray_amber(self):
        """green = answered (palette success), gray = not running (text
        secondary), amber = first probe in flight (warning)."""
        assert "color = p.success" in _LIGHTS_SRC
        assert "color = p.text_secondary" in _LIGHTS_SRC
        assert "color = p.warning" in _LIGHTS_SRC

    def test_adaptive_mode_ladder_exists(self):
        for const in ('MODE_FULL = "full"', 'MODE_DOTS = "dots"', 'MODE_MINI = "mini"'):
            assert const in _LIGHTS_SRC
        # the richest-that-fits chooser + measured widths
        assert "def set_budget" in _LIGHTS_SRC
        assert "def mode_widths" in _LIGHTS_SRC

    def test_tooltips_carry_the_poll_note_and_details(self):
        assert "_POLL_NOTE" in _LIGHTS_SRC
        assert "status.tooltip + _POLL_NOTE" in _LIGHTS_SRC
        assert "setToolTip" in _LIGHTS_SRC

    def test_widget_owns_no_threads_or_timers(self):
        """The poll loop belongs to the WINDOW; the widget only renders
        (trivially testable, never owns threads). Pinned on call sites —
        the DOCSTRING mentions the window's QTimer by design."""
        assert "QTimer(" not in _LIGHTS_SRC
        assert "QThread(" not in _LIGHTS_SRC
        assert "SimpleWorker(" not in _LIGHTS_SRC

    def test_factory_never_blocks_startup(self):
        """The build_status_lights factory is best-effort (the splash
        precedent): a broken light must never block the app."""
        assert "def build_status_lights" in _LIGHTS_SRC
        assert "except Exception" in _LIGHTS_SRC


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — the app wiring (the old dialog is GONE; the loop is honest)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0669AppSourcePins:
    def test_the_startup_ollama_error_dialog_is_gone(self):
        """THE headline pin: "do not show the error of ollama when app
        loads" — the whole _warn_ollama trio deleted from the startup
        path. (The removal is DOCUMENTED in comments that quote the old
        title — the pins target the identifiers, not the prose.)"""
        for absent in (
            "def _warn_ollama",
            "def _show_ollama_warning",
            "def _on_ollama_check_failed",
            "_ollama_check_worker",
            "_ollama_needed_for",
            'QMessageBox.warning(\n            self,\n            "Ollama not running"',
        ):
            assert absent not in _APP_SRC, absent

    def test_lights_are_built_into_the_top_bar(self):
        assert "self.llm_lights, _ = build_status_lights()" in _APP_SRC
        assert "lay.addWidget(self.llm_lights)" in _APP_SRC

    def test_the_poll_loop_is_wired_and_ticks_immediately(self):
        assert "self._setup_llm_lights_monitoring()" in _APP_SRC
        assert "LLM_LIGHTS_POLL_INTERVAL_S * 1000" in _APP_SRC
        assert "timer.timeout.connect(_tick)" in _APP_SRC
        assert "_tick()  # first verdict immediately" in _APP_SRC

    def test_probes_run_off_thread_on_the_frozen_snapshot(self):
        """Main-thread snapshot → SimpleWorker → pure probes (DESIGN RULE
        2: no cross-thread settings access)."""
        assert "snapshot_endpoints(self.controller.settings)" in _APP_SRC
        assert "worker = SimpleWorker(_probe)" in _APP_SRC
        assert "probe_local_llm_clients(self._llm_endpoints_snapshot)" in _APP_SRC

    def test_overlapping_ticks_are_skipped_and_dead_workers_replaced(self):
        assert "if prev.is_running():" in _APP_SRC
        assert "except RuntimeError:" in _APP_SRC

    def test_verdicts_apply_on_the_main_thread_fail_soft(self):
        assert "@Slot(object)" in _APP_SRC
        assert "def _on_llm_probe_finished" in _APP_SRC
        assert "lights.apply_statuses(statuses)" in _APP_SRC
        # the failed probe is QUIET — a repeating probe must never spam
        # the log (the old path used logger.warning)
        assert 'logger.debug("local-LLM liveness probe failed: %s", error)' in _APP_SRC

    def test_close_stops_the_loop(self):
        assert "self._llm_poll_timer.stop()" in _APP_SRC

    def test_resize_adapts_and_theme_toggles_repaint(self):
        assert "def resizeEvent(self, event) -> None:" in _APP_SRC
        assert "def _adapt_llm_lights(self) -> None:" in _APP_SRC
        assert "self.llm_lights.refresh_theme()" in _APP_SRC
        # the budget is MEASURED (bar minimumSizeHint with lights hidden)
        assert "bar.minimumSizeHint().width()" in _APP_SRC

    def test_budget_cushion_and_fallback(self):
        # the measured-static-min fallback for the pre-polish phase
        assert "(self._topbar_static_min or 700)" in _APP_SRC


class TestV0669MonitorSourcePins:
    def test_fresh_not_cached(self):
        """DESIGN RULE 1: the monitor must call the transport helpers
        directly — the routing layer's 30 s probe cache would delay a
        mid-session server going green by up to 30 s. Pinned on the CALL
        SITE shape (the docstring cites ``_probe_llamacpp`` by name)."""
        assert "from core.llm.local_fallback import _probe_llamacpp" not in _MON_SRC
        assert "_probe_llamacpp(" not in _MON_SRC
        assert "list_llamacpp_models(" in _MON_SRC

    def test_the_port_ladder_is_the_single_source(self):
        """The alternates are IMPORTED from local_fallback (the V0.6.55
        single source), never re-typed."""
        assert (
            "from core.llm.local_fallback import LLAMACPP_ALT_BASE_URLS, "
            "LLAMACPP_DEFAULT_BASE_URL" in _MON_SRC
        )
        assert '"http://127.0.0.1:8000/v1"' not in _MON_SRC  # no re-typed URLs

    def test_timeout_constant_is_imported_not_inlined(self):
        assert "SUBSECOND_PROBE_TIMEOUT_S" in _MON_SRC

    def test_never_raises_doctrine_is_documented_and_guarded(self):
        assert "Never raises" in _MON_SRC or "never raises" in _MON_SRC
        assert "except Exception:" in _MON_SRC

    def test_qt_free_by_doctrine(self):
        """No PySide6 import and no Qt call sites (the poll-interval
        comment MENTIONS the window's QTimer — prose, not usage)."""
        assert "PySide6" not in _MON_SRC
        assert "QTimer(" not in _MON_SRC
        assert "QWidget" not in _MON_SRC


@pytest.mark.parametrize(
    "src_name,src",
    [("app", _APP_SRC), ("lights", _LIGHTS_SRC), ("monitor", _MON_SRC)],
)
def test_no_stray_debug_prints(src_name, src):
    """Log via logging, never bare print (the Phase 2 log-hygiene rule)."""
    for line in src.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("print("), f"{src_name}: {stripped[:60]}"
