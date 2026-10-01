"""Phase 3 (V0.16) — Security & Config Hardening: keychain wiring tests.

Covers the roadmap Phase-3 acceptance criteria (docs/ROADMAP_V0.12.md):

  1. Roundtrip: set_secret → get_secret via a (mocked) keyring backend.
  2. Fresh-install: a key stored via set_secret NEVER persists to the
     plaintext settings store (cleared after the keychain write).
  3. Migration: a plaintext key found on first access moves to the
     keychain, is removed from settings, and logs exactly one WARNING.
  4. Path-mismatch fix (task 3.3): the translation service reads the
     canonical ``translation.cloud_api_key`` with the legacy
     ``translation.api_key`` as fallback, and migrates legacy → canonical.
  5. Wiring (task 3.2): provider factory / grounding / TTS / controller
     resolve keys through the keychain — a key visible ONLY via the
     keychain resolves everywhere a plaintext-only key would have.

Hermeticity: tests/conftest.py installs a RAISING keyring stub for every
test (mirrors headless CI). The ``memory_keyring`` fixture here installs
a WORKING in-memory backend on top of that stub, so these tests exercise
the real keychain code path without ever touching a real OS keychain.

Run: ``pytest tests/test_p3_secrets_wiring.py -v``
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.system.secrets as secrets_mod
from core.system.secrets import get_secret, set_secret
from utils.settings import set_test_settings

# ── Test doubles ────────────────────────────────────────────────────────────


class _MemoryKeyring:
    """In-memory keyring backend (service, username) → password."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    class PasswordDeleteError(Exception):
        pass

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise self.PasswordDeleteError(f"no entry for {username}")
        del self.store[(service, username)]


class _SettingsStub:
    """Minimal settings store: get/set only (what secrets.py consumes)."""

    def __init__(self, initial: dict | None = None):
        self.data: dict = dict(initial or {})

    def get(self, path: str, default=None):
        return self.data.get(path, default)

    def set(self, path: str, value) -> bool:
        self.data[path] = value
        return True


@pytest.fixture
def memory_keyring(monkeypatch):
    """A WORKING in-memory keychain (overrides the conftest raising stub)."""
    kr = _MemoryKeyring()
    monkeypatch.setattr(secrets_mod, "_keyring", kr, raising=False)
    monkeypatch.setattr(secrets_mod, "_HAS_KEYRING", True)
    return kr


@pytest.fixture
def settings_stub():
    return _SettingsStub()


# ── 1+2. Roundtrip + fresh-install never-plaintext ─────────────────────────


class TestKeychainRoundtrip:
    def test_set_then_get_roundtrip(self, memory_keyring, settings_stub):
        set_secret("summarisation.api_key", "sk-roundtrip", settings_stub)
        assert get_secret("summarisation.api_key", settings_stub, "") == "sk-roundtrip"
        # Landed in the keychain under the Elixir service name…
        assert memory_keyring.store[("Elixir", "summarisation.api_key")] == "sk-roundtrip"
        # …and the plaintext store was cleared (fresh-install criterion).
        assert settings_stub.data["summarisation.api_key"] == ""

    def test_every_secret_path_never_persists_plaintext(self, memory_keyring, settings_stub):
        """Fresh-install acceptance: iterate ALL secret paths — none may
        retain key material in the plaintext store after set_secret."""
        for i, path in enumerate(sorted(secrets_mod._SECRET_PATHS)):
            value = f"sk-{i}"
            set_secret(path, value, settings_stub)
            assert get_secret(path, settings_stub, "") == value
            stored = settings_stub.data.get(path)
            assert not stored, f"{path} retained plaintext {stored!r}"

    def test_empty_set_deletes_from_keychain(self, memory_keyring, settings_stub):
        set_secret("summarisation.api_key", "sk-del", settings_stub)
        set_secret("summarisation.api_key", "", settings_stub)
        assert ("Elixir", "summarisation.api_key") not in memory_keyring.store
        assert get_secret("summarisation.api_key", settings_stub, "dflt") == "dflt"

    def test_non_secret_path_bypasses_keychain(self, memory_keyring, settings_stub):
        set_secret("summarisation.provider", "ollama", settings_stub)
        assert settings_stub.data["summarisation.provider"] == "ollama"
        assert memory_keyring.store == {}


# ── 3. Plaintext → keychain migration (task 3.4) ───────────────────────────


class TestPlaintextMigration:
    def test_first_access_migrates_and_warns_once(self, memory_keyring, settings_stub, caplog):
        settings_stub.data["summarisation.api_key"] = "sk-legacy-plain"
        with caplog.at_level("WARNING", logger="core.system.secrets"):
            value = get_secret("summarisation.api_key", settings_stub, "")
        assert value == "sk-legacy-plain"
        # Migrated: keychain populated, plaintext cleared.
        assert memory_keyring.store[("Elixir", "summarisation.api_key")] == "sk-legacy-plain"
        assert settings_stub.data["summarisation.api_key"] == ""
        # Exactly ONE migration WARNING (task 3.4: one WARNING log).
        warnings = [
            r for r in caplog.records if "migrated" in r.getMessage() and r.levelname == "WARNING"
        ]
        assert len(warnings) == 1

    def test_migrate_all_secrets_covers_new_paths(self, memory_keyring, settings_stub):
        """fast_api_key / llamacpp / tts.normalize / translation.api_key are
        now in _SECRET_PATHS — migrate_all_secrets must move them too."""
        legacy = {
            "summarisation.fast_api_key": "sk-fast",
            "summarisation.llamacpp_api_key": "tok-llama",
            "tts.normalize_api_key": "sk-tts",
            "translation.api_key": "sk-tr-old",
        }
        settings_stub.data.update(legacy)
        migrated = secrets_mod.migrate_all_secrets(settings_stub)
        assert migrated == len(legacy)
        for path, value in legacy.items():
            assert memory_keyring.store[("Elixir", path)] == value
            assert not settings_stub.data.get(path)


# ── Fallback safety (no data loss, no crash) ────────────────────────────────


class TestBackendFailureFallback:
    def test_keychain_read_failure_falls_back_to_settings(self, monkeypatch, settings_stub):
        settings_stub.data["summarisation.api_key"] = "sk-fallback"

        class _BrokenGet:
            @staticmethod
            def get_password(service, username):
                raise RuntimeError("backend exploded")

        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenGet, raising=False)
        monkeypatch.setattr(secrets_mod, "_HAS_KEYRING", True)
        assert get_secret("summarisation.api_key", settings_stub, "") == "sk-fallback"

    def test_keychain_write_failure_keeps_plaintext(self, monkeypatch, settings_stub):
        class _BrokenSet:
            @staticmethod
            def set_password(service, username, password):
                raise RuntimeError("backend exploded")

        monkeypatch.setattr(secrets_mod, "_keyring", _BrokenSet, raising=False)
        monkeypatch.setattr(secrets_mod, "_HAS_KEYRING", True)
        set_secret("summarisation.api_key", "sk-kept", settings_stub)
        # No data loss: value survives in plaintext when the keychain write fails.
        assert settings_stub.data["summarisation.api_key"] == "sk-kept"

    def test_llamacpp_default_placeholder_preserved(self, memory_keyring, settings_stub):
        """Nothing stored anywhere → the "local" placeholder default wins
        (and is NOT migrated into the keychain)."""
        assert get_secret("summarisation.llamacpp_api_key", settings_stub, "local") == "local"
        assert memory_keyring.store == {}


# ── 4. Translation path-mismatch fix (task 3.3) ─────────────────────────────


class TestTranslationDualPath:
    def _service(self, settings_stub):
        set_test_settings(settings_stub)  # from_settings resolves Settings()
        from core.translation.service import TranslationService

        try:
            return TranslationService.from_settings(log_callback=None)
        finally:
            set_test_settings(None)

    def test_canonical_path_wins(self, memory_keyring, settings_stub):
        set_secret("translation.cloud_api_key", "sk-canonical", settings_stub)
        svc = self._service(settings_stub)
        assert svc.translator.api_key == "sk-canonical"

    def test_legacy_path_fallback_and_migration(self, memory_keyring, settings_stub):
        """The pre-V0.16 reality: a key stored under the LEGACY
        translation.api_key path must still resolve (migration), and be
        copied to the canonical path for future reads."""
        settings_stub.data["translation.api_key"] = "sk-legacy-tr"
        svc = self._service(settings_stub)
        assert svc.translator.api_key == "sk-legacy-tr"
        # One-time legacy → canonical migration.
        assert memory_keyring.store.get(("Elixir", "translation.cloud_api_key")) == "sk-legacy-tr"

    def test_keychain_only_legacy_key_resolves(self, memory_keyring, settings_stub):
        """A key that was ALREADY migrated to the keychain under the legacy
        path (by an earlier get_secret) still resolves via the fallback."""
        set_secret("translation.api_key", "sk-kc-legacy", settings_stub)
        svc = self._service(settings_stub)
        assert svc.translator.api_key == "sk-kc-legacy"


# ── 5. Wiring: keychain-only keys resolve at every consumer (task 3.2) ─────


@pytest.fixture
def recording_model_config(monkeypatch):
    """Capture ModelConfig kwargs regardless of langextract availability.

    Some test modules swap sys.modules["langextract"] with a MagicMock at
    collection time (same pattern as the tiktoken pin in conftest); in those
    collection orders ``from langextract.factory import ModelConfig`` inside
    ``_cloud_config`` yields a Mock whose fields are unassertable. This
    fixture installs a RECORDING stand-in for the ``langextract.factory``
    sys.modules entry so the assertion works in every collection order.
    """
    calls: list[dict] = []

    class _ModelConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            calls.append(kwargs)

    mod = types.ModuleType("langextract.factory")
    mod.ModelConfig = _ModelConfig
    monkeypatch.setitem(sys.modules, "langextract.factory", mod)
    return calls


class TestConsumerWiring:
    def test_provider_factory_cloud_key(self, memory_keyring, settings_stub):
        from core.llm.llm_provider_impl import create_provider

        set_secret("summarisation.api_key", "sk-factory", settings_stub)
        provider = create_provider("openai_compatible", settings_stub)
        assert provider.api_key == "sk-factory"

    def test_provider_factory_claude_key(self, memory_keyring, settings_stub):
        from core.llm.llm_provider_impl import create_provider

        set_secret("summarisation.claude_api_key", "sk-claude", settings_stub)
        provider = create_provider("claude", settings_stub)
        assert provider.api_key == "sk-claude"

    def test_provider_factory_llamacpp_key(self, memory_keyring, settings_stub):
        from core.llm.llm_provider_impl import create_provider

        set_secret("summarisation.llamacpp_api_key", "tok-llama", settings_stub)
        provider = create_provider("llamacpp", settings_stub)
        assert provider.api_key == "tok-llama"

    def test_provider_factory_llamacpp_default(self, memory_keyring, settings_stub):
        from core.llm.llm_provider_impl import create_provider

        provider = create_provider("llamacpp", settings_stub)
        assert provider.api_key == "local"

    def test_grounding_cloud_config_key(
        self, memory_keyring, settings_stub, recording_model_config
    ):
        pytest.importorskip("langextract")
        from core.grounding.claim_extractor import ClaimExtractor

        set_secret("grounding.cloud_api_key", "sk-ground", settings_stub)
        ex = ClaimExtractor(settings=settings_stub)
        ex._cloud_config()
        assert recording_model_config, "ModelConfig was never constructed"
        assert recording_model_config[0]["provider_kwargs"]["api_key"] == "sk-ground"

    def test_grounding_falls_back_to_summarisation_key(
        self, memory_keyring, settings_stub, recording_model_config
    ):
        pytest.importorskip("langextract")
        from core.grounding.claim_extractor import ClaimExtractor

        set_secret("summarisation.api_key", "sk-shared", settings_stub)
        ex = ClaimExtractor(settings=settings_stub)
        ex._cloud_config()
        assert recording_model_config, "ModelConfig was never constructed"
        assert recording_model_config[0]["provider_kwargs"]["api_key"] == "sk-shared"

    def test_tts_normalizer_key(self, memory_keyring, settings_stub):
        from core.tts.normalizer import create_normalizer_from_settings

        settings_stub.data.update(
            {
                "tts.normalize_enabled": True,
                "tts.normalize_model": "qwen2.5:3b",
                # V0.6.13: the factory now consults the llama.cpp-first
                # policy when the (default-local) endpoint is local — pin
                # the probe at a dead port so this test is deterministic
                # on a rig with a live llama-server (the V0.6.12 precedent).
                "summarisation.llamacpp_base_url": "http://127.0.0.1:9/v1",
            }
        )
        set_secret("tts.normalize_api_key", "sk-tts-norm", settings_stub)
        norm = create_normalizer_from_settings(log_callback=None)
        assert norm is not None
        assert norm.api_key == "sk-tts-norm"


# ── Custom-provider catalog hardening (task 3.2 extension) ─────────────────


class _CatalogStub:
    """Controller stand-in exercising the real sections.py catalog helpers."""

    def __init__(self, settings, providers=None):
        self.settings = settings
        self.data = {"ai.custom_providers": providers or []}

    def get_setting(self, path, default=None):
        return self.data.get(path, default)

    def update_setting(self, path, value):
        self.data[path] = value

    def get_secret(self, path, default=""):
        return get_secret(path, self.settings, default)

    def set_secret(self, path, value):
        set_secret(path, value, self.settings)


class TestCustomProviderCatalog:
    def _helpers(self):
        # V0.16: the catalog helpers live in a Qt-free module (utils/) so
        # they are importable (and testable) without PySide6 GUI libs.
        from utils.provider_catalog import load_custom_providers, save_custom_providers

        return load_custom_providers, save_custom_providers

    def test_legacy_inline_key_migrates_to_keychain(self, memory_keyring, settings_stub):
        load, _ = self._helpers()
        stub = _CatalogStub(
            settings_stub,
            providers=[
                {
                    "name": "9Router",
                    "base_url": "https://x/v1",
                    "api_key": "sk-inline",
                    "model": "m",
                }
            ],
        )
        catalog = load(stub)
        # The key resolved for the UI…
        assert catalog[0]["api_key"] == "sk-inline"
        # …landed in the keychain under the per-provider path…
        assert (
            memory_keyring.store[("Elixir", "ai.custom_providers.9Router.api_key")] == "sk-inline"
        )
        # …and the persisted blob was rewritten WITHOUT key material.
        persisted = stub.data["ai.custom_providers"]
        assert "api_key" not in persisted[0]

    def test_save_strips_keys_into_keychain(self, memory_keyring, settings_stub):
        _, save = self._helpers()
        stub = _CatalogStub(
            settings_stub,
            providers=[
                {"name": "MyCloud", "base_url": "https://y/v1", "api_key": "sk-new", "model": "m"}
            ],
        )
        save(stub, stub.data["ai.custom_providers"])
        persisted = stub.data["ai.custom_providers"]
        assert "api_key" not in persisted[0]
        assert memory_keyring.store[("Elixir", "ai.custom_providers.MyCloud.api_key")] == "sk-new"

    def test_plaintext_fallback_never_loses_a_key(self, settings_stub):
        """Backend-less system (the conftest raising stub): catalog keys
        degrade to individual plaintext settings paths — the roundtrip
        still works and no key is ever lost."""
        load, save = self._helpers()
        stub = _CatalogStub(
            settings_stub, providers=[{"name": "P", "api_key": "sk-plain", "model": "m"}]
        )
        save(stub, stub.data["ai.custom_providers"])
        # Plaintext fallback: the key degraded to an individual settings
        # path (settings_stub backs the controller's get/set_secret).
        assert settings_stub.data["ai.custom_providers.P.api_key"] == "sk-plain"
        catalog = load(stub)
        assert catalog[0]["api_key"] == "sk-plain"


# ── Controller wiring (get_secret/set_secret + request table) ──────────────


class TestControllerWiring:
    def _controller(self, settings_stub):
        """Real Controller methods, no heavy __init__."""
        import controller as controller_mod

        ctrl = controller_mod.Controller.__new__(controller_mod.Controller)
        ctrl.settings = settings_stub
        ctrl.on_log = None  # _safe_log probes this attribute
        return ctrl

    def test_controller_get_set_secret(self, memory_keyring, settings_stub):
        ctrl = self._controller(settings_stub)
        ctrl.set_secret(
            "summarisation.api_key",
            "sk-ctrl",
        )
        assert ctrl.get_secret("summarisation.api_key", "") == "sk-ctrl"
        assert not settings_stub.data.get("summarisation.api_key")

    def test_build_request_resolves_keychain_only_fast_key(self, memory_keyring, settings_stub):
        """A fast_api_key that exists ONLY in the keychain must land in the
        ConversionRequest (the old plaintext read resolved it as "")."""
        ctrl = self._controller(settings_stub)
        set_secret("summarisation.fast_api_key", "sk-fast-req", settings_stub)
        request = ctrl.build_request_from_ui({"input_path": "/tmp/book.pdf"})
        assert request.fast_api_key == "sk-fast-req"

    def test_save_book_settings_omits_fast_key(self, memory_keyring, settings_stub, tmp_path):
        """V0.16: the per-book config must not leak the API key to disk."""
        import json

        ctrl = self._controller(settings_stub)
        from core.models import ConversionRequest

        req = ConversionRequest(
            input_path=tmp_path / "in.pdf",
            output_dir=tmp_path,
            fast_api_key="sk-should-not-leak",
        )
        ctrl.save_book_settings(tmp_path, req)
        cfg_path = tmp_path / ".conversion_config.json"
        assert cfg_path.exists()
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert "fast_api_key" not in raw
        assert "sk-should-not-leak" not in cfg_path.read_text(encoding="utf-8")
