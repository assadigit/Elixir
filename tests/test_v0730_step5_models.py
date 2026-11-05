"""V0.7.3 (wizard rework ⑤, Step 5) — the pin file.

5a — per-backend model listing (B6, D14 — no auto-pick): LM Studio lists
from its OWN base URL /v1/models (``utils/network.list_lmstudio_models``);
the Step-5 dispatch is per-backend (ollama → /api/tags, lmstudio → its
own server, llamacpp → the mixin worker); the "no models" hint names the
server that was actually asked.

5b — preference memory (D14): the combos open on the last-used picks
(settings), a refresh keeps the pick even when the server no longer
lists it, and a successful run re-confirms the picks in settings —
"manual picking, auto-remembered."

5c — single-owner limits (D12) + computed honesty: Step 5 keeps the ONLY
"Model context / Model output" inputs (Auto default + a read-only line
showing the effective values after the backend's clamp ladder); Step
7b's duplicate "Summarization limits" group is deleted; the defaults
agree across state/settings/request (coverage 85 / ctx 32768 / out
16000 — audit §5's table, one default per field).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP5 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step5_models.py"
_STEP7B = _project_root / "ui_qt" / "views" / "wizard_steps" / "step7b_fine_tune.py"
_NETWORK = _project_root / "utils" / "network.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_MODELS = _project_root / "core" / "models" / "models.py"
_SETTINGS = _project_root / "utils" / "settings.py"
_CONTROLLER = _project_root / "controller.py"
_EFFECTIVE = _project_root / "core" / "summarisation" / "effective_limits.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 5a — per-backend listing (B6): source pins
# ═══════════════════════════════════════════════════════════════════════════


class TestPerBackendListingSource:
    def test_lmstudio_lister_exists_in_network(self):
        src = _src(_NETWORK)
        assert "def list_lmstudio_models(" in src
        assert 'base_url: str = "http://localhost:1234/v1"' in src

    def test_step5_dispatches_lmstudio_to_its_own_server(self):
        body = _src(_STEP5)
        assert 'elif self._models_backend_snapshot == "lmstudio":' in body
        assert "from utils.network import list_lmstudio_models" in body
        # The URL is snapshotted on the MAIN thread (no widget access on
        # the worker) — the line edit read happens in _refresh_models.
        assert "self.lmstudio_url_edit.text().strip()" in body

    def test_ollama_path_unchanged(self):
        """The original Ollama worker stays the default branch (B6's fix
        adds a branch, it does not rewrite the Ollama route)."""
        body = _src(_STEP5)
        assert 'if self._models_backend_snapshot == "llamacpp":' in body
        assert "worker_fn = self._get_models" in body

    def test_no_models_hint_is_backend_aware(self):
        body = _src(_STEP5)
        assert '"No models found on {_hints[0]}' in body.replace('f"', '"')
        assert '"lmstudio": (' in body
        assert "Developer tab → Start Server" in body
        # The old lie: the Ollama-only copy shown for every backend.
        assert '"No Ollama models found.' not in body


# ═══════════════════════════════════════════════════════════════════════════
# 5a — the lister itself (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


class TestListLmstudioModels:
    def test_lists_openai_shape_from_own_base_url(self, monkeypatch):
        """GET {base}/models — LM Studio's OpenAI-compatible listing."""
        import utils.network as net

        seen = {}

        def _fake_get(url, timeout=None):
            seen["url"] = url
            seen["timeout"] = timeout
            return _Resp(
                200, {"data": [{"id": "qwen2.5-7b-instruct"}, {"id": "phi-4"}, {"no": "x"}]}
            )

        monkeypatch.setattr(net.requests, "get", _fake_get)
        out = net.list_lmstudio_models("http://localhost:1234/v1")
        assert out == ["qwen2.5-7b-instruct", "phi-4"]
        assert seen["url"] == "http://localhost:1234/v1/models"
        assert seen["timeout"] == 5

    def test_trailing_slash_normalized(self, monkeypatch):
        import utils.network as net

        seen = {}

        def _fake_get(url, timeout=None):
            seen["url"] = url
            return _Resp(200, {"data": [{"id": "m"}]})

        monkeypatch.setattr(net.requests, "get", _fake_get)
        assert net.list_lmstudio_models("http://lm:9999/v1/") == ["m"]
        assert seen["url"] == "http://lm:9999/v1/models"

    def test_never_raises(self, monkeypatch):
        import utils.network as net

        def _boom(url, timeout=None):
            raise ConnectionError("down")

        monkeypatch.setattr(net.requests, "get", _boom)
        assert net.list_lmstudio_models("http://localhost:1234/v1") == []
        monkeypatch.setattr(net.requests, "get", lambda url, timeout=None: _Resp(500, {}))
        assert net.list_lmstudio_models("http://localhost:1234/v1") == []


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6) — shared scaffolding for this file
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


class _StubController:
    """The controller surface Step 5 + the mixin touch during _build."""

    def __init__(self, settings=None):
        self._settings: dict = dict(settings or {})
        self.secrets: dict = {}

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value

    def get_secret(self, path, default=None):
        return self.secrets.get(path, default)

    def set_secret(self, path, value):
        self.secrets[path] = value


class _FakeSignal:
    def connect(self, *args, **kwargs):
        pass


class _FakeWorker:
    """Captures the worker fn instead of starting a thread — building the
    step offscreen must never touch the network (the W-b11 worker is also
    why the grabs stay modal-free: _on_models_loaded never fires)."""

    captured: list = []

    def __init__(self, fn, *args, **kwargs):
        type(self).captured.append(fn)

    finished = _FakeSignal()
    failed = _FakeSignal()

    def is_running(self):
        return False

    def start(self):
        pass


class TestStep5DispatchOffscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _build(self, settings=None):
        import ui_qt.views.wizard_steps.step5_models as step5_mod
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step5_models import Step5Models

        _FakeWorker.captured = []
        orig = step5_mod.SimpleWorker
        step5_mod.SimpleWorker = _FakeWorker
        try:
            step = Step5Models(_StubController(settings), WizardState())
        finally:
            step5_mod.SimpleWorker = orig
        return step

    def test_ollama_backend_lists_via_ollama_worker(self, app):
        step = self._build({"summarisation.provider": "ollama"})
        try:
            assert step._models_backend_snapshot == "ollama"
            assert _FakeWorker.captured, "the build starts a listing worker"
            assert _FakeWorker.captured[-1] == step._get_models
        finally:
            step.hide()
            step.deleteLater()

    def test_default_backend_is_the_house_default_llamacpp(self, app):
        """No settings → the provider default (llamacpp) drives the dispatch
        (the mixin worker, NOT the Ollama route)."""
        step = self._build()
        try:
            assert step._models_backend_snapshot == "llamacpp"
            assert _FakeWorker.captured[-1] == step.llamacpp_fetch_models
        finally:
            step.hide()
            step.deleteLater()

    def test_lmstudio_backend_lists_from_its_own_url(self, app, monkeypatch):
        """B6's core: with the LM Studio backend selected, the worker hits
        the LM Studio URL — never Ollama's /api/tags."""
        import utils.network as net

        step = self._build({"summarisation.provider": "lmstudio"})
        try:
            step.lmstudio_url_edit.setText("http://localhost:1234/v1")
            seen = {}

            def _fake_get(url, timeout=None):
                seen["url"] = url
                return _Resp(200, {"data": [{"id": "lmstudio-only-model"}, {"id": "gpt-oss-20b"}]})

            monkeypatch.setattr(net.requests, "get", _fake_get)
            # Simulate the user switching the backend (the combo drives
            # _on_backend_change → _refresh_models on the main thread).
            import ui_qt.views.wizard_steps.step5_models as step5_mod

            orig = step5_mod.SimpleWorker
            step5_mod.SimpleWorker = _FakeWorker
            try:
                step._refresh_models()
            finally:
                step5_mod.SimpleWorker = orig
            assert step._models_backend_snapshot == "lmstudio"
            worker_fn = _FakeWorker.captured[-1]
            models = worker_fn()
            assert models == ["lmstudio-only-model", "gpt-oss-20b"]
            # The LM Studio server was asked on ITS OWN endpoint…
            assert seen["url"] == "http://localhost:1234/v1/models"
            # …and Ollama's discovery route was never touched.
            assert "/api/tags" not in seen["url"]
        finally:
            step.hide()
            step.deleteLater()

    def test_llamacpp_backend_keeps_the_mixin_worker(self, app, monkeypatch):
        step = self._build({"summarisation.provider": "llamacpp"})
        try:
            import ui_qt.views.wizard_steps.step5_models as step5_mod

            orig = step5_mod.SimpleWorker
            step5_mod.SimpleWorker = _FakeWorker
            try:
                step._refresh_models()
            finally:
                step5_mod.SimpleWorker = orig
            assert step._models_backend_snapshot == "llamacpp"
            assert _FakeWorker.captured[-1] == step.llamacpp_fetch_models
        finally:
            step.hide()
            step.deleteLater()

    def test_lmstudio_hint_copy(self, app, monkeypatch):
        """The 'no models' hint names LM Studio when LM Studio was asked."""
        QtWidgets = _qt_or_skip()
        step = self._build({"summarisation.provider": "lmstudio"})
        try:
            shown = []
            monkeypatch.setattr(
                QtWidgets.QMessageBox, "information", lambda *a, **k: shown.append(a)
            )
            step._on_models_loaded([])
            assert shown, "the empty listing shows the hint"
            assert "LM Studio" in shown[0][2]
            assert "Ollama" not in shown[0][2]
        finally:
            step.hide()
            step.deleteLater()
