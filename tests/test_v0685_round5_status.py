"""V0.6.85 — Round-5 characterization pins (the truthful status model).

Round-5 spec (ELIXIR_UI_UX_CORRECTION_ROUND_5.md):

* §3  — the Full Conversion Wizard card's icon + text group + arrow are
        vertically centered (text left-aligned, arrow right-aligned).
* §4  — the duplicate header Settings + the provider pill are retired;
        provider selection + a connection test live in Settings.
* §5  — the bottom status is a REAL connection-state model, never a
        hardcoded "Ready"; checks are async and bounded.

These pins keep the contract mechanical: the pure state model is tested
DIRECTLY (no Qt), the UI wiring is pinned on the source shape (the house
pattern), and the card centering is pinned on the equal-stretch structure
that scripts/r5_alignment.py measures live.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
_APP = _project_root / "ui_qt" / "app.py"
_PRIMS = _project_root / "ui_qt" / "components" / "dashboard_primitives.py"
_MON = _project_root / "core" / "system" / "local_llm_monitor.py"
_CONN = _project_root / "core" / "system" / "backend_connection.py"
_LOCAL_MODEL = _project_root / "ui_qt" / "settings" / "sections" / "ai_model_section.py"
_API_SECTION = _project_root / "ui_qt" / "settings" / "sections" / "ai_api_section.py"

_APP_SRC = _APP.read_text(encoding="utf-8")
_PRIMS_SRC = _PRIMS.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# §5 — the connection-state model (pure, Qt-free)
# ════════════════════════════════════════════════════════════════════════════


class TestBackendStateModel:
    def test_the_six_states_and_their_labels(self):
        from core.system import backend_connection as bc

        for state, label in (
            (bc.CHECKING, "Checking backend…"),
            (bc.CONNECTED, "Connected"),
            (bc.BACKEND_OFFLINE, "Backend offline"),
            (bc.API_UNAVAILABLE, "API unavailable"),
            (bc.NOT_CONFIGURED, "Not configured"),
            (bc.MODEL_UNAVAILABLE, "Model unavailable"),
        ):
            assert bc.STATE_LABELS[state] == label
            assert bc.STATE_SEVERITY[state] in ("ok", "warn", "bad", "neutral")

    def test_severity_tints_match_the_spec(self):
        """§5.3: green=ok, amber=checking/partial, red=unavailable,
        gray=not configured."""
        from core.system import backend_connection as bc

        assert bc.STATE_SEVERITY[bc.CONNECTED] == "ok"
        assert bc.STATE_SEVERITY[bc.CHECKING] == "warn"
        assert bc.STATE_SEVERITY[bc.MODEL_UNAVAILABLE] == "warn"
        assert bc.STATE_SEVERITY[bc.BACKEND_OFFLINE] == "bad"
        assert bc.STATE_SEVERITY[bc.API_UNAVAILABLE] == "bad"
        assert bc.STATE_SEVERITY[bc.NOT_CONFIGURED] == "neutral"

    def test_no_verdict_yet_is_checking_never_connected(self):
        from core.system import backend_connection as bc

        state, _ = bc.derive_local_backend_state(None, "ollama", "m")
        assert state == bc.CHECKING

    def test_offline_backend_is_backend_offline(self):
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="ollama", name="Ollama", online=False, detail="not running", endpoint="x"
            )
        ]
        state, _ = bc.derive_local_backend_state(statuses, "ollama", "m")
        assert state == bc.BACKEND_OFFLINE

    def test_online_with_the_model_is_connected(self):
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="ollama",
                name="Ollama",
                online=True,
                detail="running",
                endpoint="x",
                models=("llama3", "gemma2"),
            )
        ]
        state, _ = bc.derive_local_backend_state(statuses, "ollama", "llama3")
        assert state == bc.CONNECTED

    def test_online_without_the_model_is_model_unavailable(self):
        """Only claimed when the listing is EVIDENCE (Ollama's /api/tags is
        authoritative — §5.1's "if the backend exposes enough information")."""
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="ollama",
                name="Ollama",
                online=True,
                detail="running",
                endpoint="x",
                models=("llama3",),
            )
        ]
        state, detail = bc.derive_local_backend_state(statuses, "ollama", "gemma2")
        assert state == bc.MODEL_UNAVAILABLE
        assert "gemma2" in detail

    def test_ollama_online_with_zero_models_is_model_unavailable(self):
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="ollama", name="Ollama", online=True, detail="no models", endpoint="x"
            )
        ]
        state, _ = bc.derive_local_backend_state(statuses, "ollama", "llama3")
        assert state == bc.MODEL_UNAVAILABLE

    def test_llamacpp_empty_listing_is_not_evidence(self):
        """Older llama.cpp builds serve no /v1/models — an empty list must
        stay CONNECTED (never a false MODEL_UNAVAILABLE)."""
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="llamacpp", name="llama.cpp", online=True, detail="running", endpoint="x"
            )
        ]
        state, _ = bc.derive_local_backend_state(statuses, "llamacpp", "some-model")
        assert state == bc.CONNECTED

    def test_llamacpp_nonempty_listing_missing_model_is_model_unavailable(self):
        from core.system import backend_connection as bc
        from core.system.local_llm_monitor import LocalLLMStatus

        statuses = [
            LocalLLMStatus(
                key="llamacpp",
                name="llama.cpp",
                online=True,
                detail="running",
                endpoint="x",
                models=("served-model",),
            )
        ]
        state, _ = bc.derive_local_backend_state(statuses, "llamacpp", "other-model")
        assert state == bc.MODEL_UNAVAILABLE

    def test_the_monitor_now_carries_the_model_evidence(self):
        """LocalLLMStatus.models — the field the state model derives from."""
        from core.system.local_llm_monitor import LocalLLMStatus

        st = LocalLLMStatus(key="ollama", name="Ollama", online=True, detail="d", endpoint="e")
        assert st.models == ()  # default: not verifiable

    def test_snapshot_maps_providers_to_clients(self):
        from core.system.backend_connection import snapshot_backend_config

        class _S:
            def __init__(self, d):
                self._d = d

            def get(self, k, default=None):
                return self._d.get(k, default)

        s = _S({"summarisation.provider": "ollama"})
        cfg = snapshot_backend_config(s)
        assert cfg.client_key == "ollama" and not cfg.is_api
        s = _S({"summarisation.provider": "llamacpp"})
        assert snapshot_backend_config(s).client_key == "llamacpp"
        # LM Studio is configured as ai.backend (the provider stays ollama)
        s = _S({"summarisation.provider": "ollama", "ai.backend": "LM Studio"})
        assert snapshot_backend_config(s).client_key == "lmstudio"
        # the API family
        s = _S({"summarisation.provider": "openai_compatible"})
        cfg = snapshot_backend_config(s)
        assert cfg.is_api and cfg.provider == "openai_compatible"
        s = _S({"summarisation.provider": "claude"})
        assert snapshot_backend_config(s).is_api
        # unknown providers fall back to the factory's own ollama branch
        s = _S({"summarisation.provider": "nonexistent"})
        assert snapshot_backend_config(s).provider == "ollama"

    def test_api_probe_classifies_missing_configuration(self):
        """The app's own verifier (test_cloud_connection) refuses to run
        without base/key/model — a config gap, never a fake pass."""
        from core.system.backend_connection import test_api_provider_connection

        ok, msg = test_api_provider_connection("openai_compatible", "", "k", "m")
        assert not ok and "base URL" in msg
        ok, msg = test_api_provider_connection("openai_compatible", "https://x/v1", "", "m")
        assert not ok and "API key" in msg
        ok, msg = test_api_provider_connection("openai_compatible", "https://x/v1", "k", "")
        assert not ok and "model" in msg

    def test_claude_probe_shape(self):
        """The Claude probe mirrors ClaudeProvider's exact header contract
        (x-api-key + anthropic-version) — pinned on the source so the
        shape can never silently drift."""
        src = _CONN.read_text(encoding="utf-8")
        assert '"x-api-key": api_key' in src
        assert '"anthropic-version": "2023-06-01"' in src


# ════════════════════════════════════════════════════════════════════════════
# §5 — the app wiring (source pins; the house pattern)
# ════════════════════════════════════════════════════════════════════════════


class TestStatusStripWiring:
    def test_no_hardcoded_ready_anywhere(self):
        code = _strip(_APP_SRC)
        assert '"Ready"' not in code, "Round-5 §5: never a hardcoded Ready"
        assert 'QLabel("Ready")' not in code

    def test_the_strip_opens_in_checking(self):
        assert "self.set_backend_state(backend_connection.CHECKING" in _APP_SRC

    def test_the_state_render_path_exists(self):
        for pin in (
            "def set_backend_state",
            "def _paint_backend_dot",
            "def _backend_state_color",
            'self._backend_label.setObjectName("SidebarLabel")',
        ):
            assert pin in _APP_SRC, pin

    def test_local_state_derives_from_the_real_poll(self):
        for pin in (
            "def _refresh_backend_state_from_statuses",
            "derive_local_backend_state(",
            "self._llm_last_statuses, cfg.client_key, cfg.model",
        ):
            assert pin in _APP_SRC, pin

    def test_api_check_is_one_shot_bounded_and_async(self):
        """§5.2: non-blocking (SimpleWorker), no stacking, triggered at
        startup + on a Settings close — never a repeating paid-endpoint
        poll."""
        for pin in (
            "def _run_api_backend_check",
            "worker = SimpleWorker(_probe)",
            "def _on_api_check_finished",
            "def _on_api_check_failed",
            "self._run_api_backend_check()",
        ):
            assert pin in _APP_SRC, pin
        # startup + settings-close triggers (exactly the two call sites)
        assert _APP_SRC.count("self._run_api_backend_check()") == 2

    def test_api_config_gap_is_not_configured(self):
        assert "backend_connection.NOT_CONFIGURED" in _APP_SRC

    def test_activity_word_is_distinct_from_backend_state(self):
        """§5.1: the wizard lifecycle keeps its own transient word; it
        clears when the dialog closes (no Ready fallback)."""
        for pin in (
            "self._activity_label",
            'set_status("Converting…")',
            'set_status("Conversion finished")',
            'self.set_status("")',
        ):
            assert pin in _APP_SRC, pin

    def test_monitor_unavailable_degrades_honestly(self):
        assert "backend status monitoring is unavailable" in _APP_SRC

    def test_the_monitor_probe_carries_models(self):
        src = _MON.read_text(encoding="utf-8")
        assert "models: tuple[str, ...] = field(default_factory=tuple)" in src
        assert "models=tuple(models)" in src


# ════════════════════════════════════════════════════════════════════════════
# §4 — provider selection lives in Settings (+ its connection tests)
# ════════════════════════════════════════════════════════════════════════════


class TestSettingsProviderHome:
    def test_local_model_section_has_the_test_row(self):
        src = _LOCAL_MODEL.read_text(encoding="utf-8")
        for pin in (
            '"  Test connection"',
            "def _test_connection",
            "test_local_backend_connection(",
            "SimpleWorker(_run)",
        ):
            assert pin in src, pin

    def test_api_section_has_the_test_row(self):
        src = _API_SECTION.read_text(encoding="utf-8")
        for pin in (
            '"  Test connection"',
            "def _test_connection",
            "test_api_provider_connection(",
            "SimpleWorker(_run)",
        ):
            assert pin in src, pin

    def test_settings_close_rechecks_the_backend(self):
        assert "_refresh_backend_state_from_statuses()" in _APP_SRC
        assert "post-settings backend re-check" in _APP_SRC

    def test_the_backends_are_the_supported_set_only(self):
        """§4.2: "only show options the application actually supports" —
        the picker's vocabulary is the pre-existing BACKENDS list."""
        src = _LOCAL_MODEL.read_text(encoding="utf-8")
        assert 'BACKENDS = ["Ollama", "llama.cpp server", "LM Studio", "Custom"]' in src


# ════════════════════════════════════════════════════════════════════════════
# §3 — the featured card's vertical centering (structure pins; the live
# geometry is measured by scripts/r5_alignment.py)
# ════════════════════════════════════════════════════════════════════════════


class TestWizardCardCentering:
    def test_equal_bookend_stretches_center_the_text_block(self):
        """The defect: addStretch(1) over addStretch() gave ALL the slack to
        the TOP spacer (factors 1 vs 0), pinning the text toward the card's
        bottom. The fix: EQUAL factors."""
        body = _card_constructor(_PRIMS_SRC)
        stretches = re.findall(r"text_col\.addStretch\((\d*)\)", body)
        assert stretches == ["1", "1"], (
            f"the text column's bookend stretches must be equal (got {stretches})"
        )

    def test_icon_and_arrow_are_vcentered_in_the_row(self):
        body = _card_constructor(_PRIMS_SRC)
        assert "lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)" in body
        # §3: the arrow is RIGHT-aligned independently of the text block
        assert (
            "lay.addWidget(\n"
            "            self._arrow,\n"
            "            0,\n"
            "            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,\n"
            "        )"
            in body
            or "AlignVCenter | Qt.AlignmentFlag.AlignRight" in body
        )

    def test_the_labels_stay_left_aligned(self):
        """No AlignHCenter anywhere in the text column (the reference keeps
        left-aligned text; "middle alignment" is vertical only)."""
        body = _card_constructor(_PRIMS_SRC)
        assert "AlignHCenter" not in body

    def test_the_text_block_takes_the_stretch_between_icon_and_arrow(self):
        body = _card_constructor(_PRIMS_SRC)
        assert "lay.addLayout(text_col, 1)" in body


# ── helpers ─────────────────────────────────────────────────────────────────


def _strip(code: str) -> str:
    """Drop # comments (keep strings) — the house _strip_comments shape."""
    out = []
    for line in code.splitlines():
        cleaned = re.sub(r"#.*$", "", line)
        out.append(cleaned)
    return "\n".join(out)


def _card_constructor(src: str) -> str:
    """QuickToolCard.__init__'s body only."""
    m = re.search(r"class QuickToolCard.*?def __init__\(.*?\n(.*?)\n    @property", src, re.S)
    assert m, "QuickToolCard constructor not found"
    return m.group(1)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
