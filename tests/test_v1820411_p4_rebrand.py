"""V18.20.4.11 (rebrand): Elixir rename — characterization pins.

The app formerly known as MarkItDown Pro is Elixir. This file pins:
  1. the rebrand is COMPLETE (no stray brand strings outside the two
     migration anchors + the historical record files)
  2. the markitdown LIBRARY references survive (it is a dependency)
  3. the ~/.markitdown_pro → ~/.elixir user-data migration behaves
     (moves once, preserves content, never raises, skips when target exists)
  4. the keychain legacy-service read-fallback works
"""

from __future__ import annotations

from pathlib import Path

import utils.settings as settings_mod

_REPO = Path(__file__).resolve().parent.parent

# The ONLY files allowed to mention the old brand after the rebrand:
#  - the two migration anchors (runtime code, deliberate)
#  - the historical record (what shipped, when — records are not rewritten)
_ALLOWED = {
    "utils/settings.py",  # _LEGACY_USER_DIR_NAME migration source
    "core/system/secrets.py",  # _LEGACY_KEYCHAIN_SERVICE read-fallback
    "CHANGELOG.md",  # historical entries + this release's note
    "docs/AUDIT_SWOT_V0.11.md",  # V0.12/V0.13 audit deliverable — historical references
    "Project-History.md",  # historical development log
    "README.md",  # the "previously known as" callout
    "NEW_SESSION_PROMPT.md",  # working-agreement history note (checked below)
}
_BRAND_PATTERNS = [
    "MarkItDown Pro Ultimate",
    "MarkItDown Pro",
    "MarkItDown-Pro",
    "MarkItDownPro",
    ".markitdown_pro",
    "markitdown-pro.local",
    "markitdown_pro_single_instance",
]


def _iter_repo_files():
    for p in sorted(_REPO.rglob("*")):
        if not p.is_file():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in p.parts):
            continue
        if (
            p.suffix.lower()
            not in {".py", ".md", ".toml", ".iss", ".txt", ".json", ".yml", ".bat", ".cfg"}
            and p.name != "Makefile"
        ):
            continue
        yield p


class TestRebrandSweepComplete:
    def test_no_stray_brand_strings(self):
        offenders = []
        for p in _iter_repo_files():
            rel = p.relative_to(_REPO).as_posix()
            if (
                rel in _ALLOWED
                or rel.startswith("tests/test_ground/")  # historical run records
                or rel == "tests/test_v1820411_p4_rebrand.py"  # this file's own pins
            ):
                continue
            try:
                src = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for pat in _BRAND_PATTERNS:
                if pat in src:
                    offenders.append(f"{rel}: contains {pat!r}")
        assert not offenders, "V18.20.4.11 rebrand regression: " + "; ".join(offenders)

    def test_migration_anchors_kept(self):
        """The two legacy constants MUST keep the old names — they are the
        migration sources. Renaming them orphans every existing user's
        settings and keychain secrets."""
        src = (_REPO / "utils/settings.py").read_text(encoding="utf-8")
        assert '_LEGACY_USER_DIR_NAME = ".markitdown_pro"' in src
        ssrc = (_REPO / "core/system/secrets.py").read_text(encoding="utf-8")
        # V0.13: format-wrapped — the string literal moved to its own line
        assert "_LEGACY_KEYCHAIN_SERVICE = (" in ssrc
        assert '"MarkItDownPro"  # pre-rebrand keychain service' in ssrc

    def test_markitdown_library_references_survive(self):
        """The markitdown PyPI library (Microsoft's extraction engine) is a
        DEPENDENCY — imports and requirements entries keep its name."""
        reqs = (_REPO / "requirements.txt").read_text(encoding="utf-8")
        assert "markitdown" in reqs
        # (V0.08 / P2: the module-level markitdown import in
        # core/pdf/adaptive_toc.py was removed with that dead module; the
        # live lazy import sites are core/ocr/service.py and
        # core/pdf/toc_extractor.py.)

    def test_runtime_identity_is_elixir(self):
        app = (_REPO / "ui_qt/app.py").read_text(encoding="utf-8")
        assert 'setApplicationName("Elixir")' in app
        assert "ElixirWindow" in app
        secrets = (_REPO / "core/system/secrets.py").read_text(encoding="utf-8")
        assert '_KEYCHAIN_SERVICE = "Elixir"' in secrets
        settings_src = (_REPO / "utils/settings.py").read_text(encoding="utf-8")
        assert '_USER_DIR_NAME = ".elixir"' in settings_src


class TestUserDataDirMigration:
    def _reset(self):
        settings_mod._user_dir_resolved = False

    def test_migrates_legacy_dir_once(self, tmp_path, monkeypatch):
        """Legacy ~/.markitdown_pro (with content) → ~/.elixir on first call;
        content preserved; idempotent on second call."""
        home = tmp_path / "home"
        home.mkdir()
        legacy = home / ".markitdown_pro"
        (legacy / "sub").mkdir(parents=True)
        (legacy / "settings.json").write_text('{"ocr": {}}', encoding="utf-8")
        (legacy / "sub" / "model.bin").write_bytes(b"\x00\x01")

        monkeypatch.setattr(settings_mod.Path, "home", classmethod(lambda cls: home))
        self._reset()
        try:
            new_dir = settings_mod.user_data_dir()
            assert new_dir == home / ".elixir"
            assert new_dir.exists(), "migration must create the new dir"
            assert (new_dir / "settings.json").read_text(encoding="utf-8") == '{"ocr": {}}'
            assert (new_dir / "sub" / "model.bin").read_bytes() == b"\x00\x01"
            assert not legacy.exists(), "legacy dir is MOVED, not copied"
            # idempotent: second call returns the same, no error
            assert settings_mod.user_data_dir() == new_dir
        finally:
            self._reset()

    def test_no_legacy_no_migration(self, tmp_path, monkeypatch):
        """Fresh install (no legacy dir) → just returns the new path."""
        home = tmp_path / "home2"
        home.mkdir()
        monkeypatch.setattr(settings_mod.Path, "home", classmethod(lambda cls: home))
        self._reset()
        try:
            d = settings_mod.user_data_dir()
            assert d == home / ".elixir"
            assert not d.exists(), "user_data_dir must not create the dir itself"
        finally:
            self._reset()

    def test_existing_new_dir_skips_migration(self, tmp_path, monkeypatch):
        """Both dirs exist → keep the new one untouched (never overwrite)."""
        home = tmp_path / "home3"
        home.mkdir()
        legacy = home / ".markitdown_pro"
        legacy.mkdir()
        (legacy / "old.txt").write_text("old", encoding="utf-8")
        new = home / ".elixir"
        new.mkdir()
        (new / "new.txt").write_text("new", encoding="utf-8")

        monkeypatch.setattr(settings_mod.Path, "home", classmethod(lambda cls: home))
        self._reset()
        try:
            assert settings_mod.user_data_dir() == new
            assert (new / "new.txt").read_text(encoding="utf-8") == "new"
            assert legacy.exists(), "legacy dir must NOT be deleted when new exists"
        finally:
            self._reset()

    def test_migration_failure_never_raises(self, tmp_path, monkeypatch):
        """A broken legacy dir (e.g. unreadable) → WARNING, no exception,
        fresh start."""
        home = tmp_path / "home4"
        home.mkdir()
        legacy = home / ".markitdown_pro"
        legacy.mkdir()

        real_move = settings_mod.shutil.move

        def _boom(*a, **k):
            raise OSError("simulated cross-device failure")

        monkeypatch.setattr(settings_mod.Path, "home", classmethod(lambda cls: home))
        monkeypatch.setattr(settings_mod.shutil, "move", _boom)
        self._reset()
        try:
            d = settings_mod.user_data_dir()  # must not raise
            assert d == home / ".elixir"
        finally:
            monkeypatch.setattr(settings_mod.shutil, "move", real_move)
            self._reset()


class TestKeychainLegacyFallback:
    def test_legacy_service_read_and_restore(self, monkeypatch):
        """Secret stored under the legacy MarkItDownPro service is returned
        AND re-stored under Elixir on first read."""
        import core.system.secrets as secrets

        store = {"Elixir": {}, "MarkItDownPro": {"summarisation.api_key": "sk-legacy"}}

        class _FakeKeyring:
            def get_password(self, service, path):
                return store.get(service, {}).get(path)

            def set_password(self, service, path, value):
                store.setdefault(service, {})[path] = value

        monkeypatch.setattr(secrets, "_HAS_KEYRING", True)
        # V0.13: raising=False — the _keyring module attribute only exists when
        # the real keyring package is installed; the CI test environment does
        # not install it (keyring becomes a core dependency in Phase 3), and
        # this test exercises the mocked path, not the real backend.
        monkeypatch.setattr(secrets, "_keyring", _FakeKeyring(), raising=False)

        class _Settings:
            def get(self, path, default=None):
                return default

        value = secrets.get_secret("summarisation.api_key", _Settings(), "")
        assert value == "sk-legacy"
        assert store["Elixir"]["summarisation.api_key"] == "sk-legacy", (
            "legacy secret must be re-stored under the Elixir service"
        )
        assert store["MarkItDownPro"]["summarisation.api_key"] == "sk-legacy"  # left in place
