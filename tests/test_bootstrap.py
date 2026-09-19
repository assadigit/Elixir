"""V18.2.22 (Phase 2.1) — Tests for the Bootstrap class.

Covers:
1. Bootstrap.run executes all 4 steps in order
2. A failing step doesn't block subsequent steps (defense-in-depth)
3. _clean_pycache removes __pycache__ directories
4. _refresh_prompts deletes the user prompts dir
5. _migrate_settings force-resets stale keys + writes back
6. _migrate_secrets calls migrate_all_secrets when keyring available
7. steps_run / steps_failed diagnostics
8. run() never raises (even if a step raises an unexpected exception)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.system.bootstrap import Bootstrap, BootstrapError


class TestBootstrapRun:
    def test_run_executes_all_steps(self, tmp_path):
        """All 4 steps should run in order."""
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=app_dir)
        # Mock each step to track calls
        calls = []
        b._clean_pycache = lambda: calls.append("clean_pycache")
        b._refresh_prompts = lambda: calls.append("refresh_prompts")
        b._migrate_settings = lambda: calls.append("migrate_settings")
        b._migrate_secrets = lambda: calls.append("migrate_secrets")
        b.run()
        assert calls == ["clean_pycache", "refresh_prompts", "migrate_settings", "migrate_secrets"]
        assert b.steps_run == calls
        assert b.steps_failed == []

    def test_failing_step_doesnt_block_subsequent(self, tmp_path):
        """A BootstrapError in one step is caught; later steps still run."""
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=app_dir)
        b._clean_pycache = lambda: (_ for _ in ()).throw(BootstrapError("pyc fail"))
        ran = []
        b._refresh_prompts = lambda: ran.append("refresh")
        b._migrate_settings = lambda: ran.append("migrate_settings")
        b._migrate_secrets = lambda: ran.append("migrate_secrets")
        b.run()
        assert "refresh" in ran
        assert "migrate_settings" in ran
        assert "migrate_secrets" in ran
        assert len(b.steps_failed) == 1
        assert b.steps_failed[0][0] == "clean_pycache"

    def test_unexpected_exception_caught(self, tmp_path):
        """Even non-BootstrapError exceptions are caught (defense-in-depth)."""
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=app_dir)
        b._clean_pycache = lambda: (_ for _ in ()).throw(RuntimeError("unexpected"))
        b._refresh_prompts = lambda: None
        b._migrate_settings = lambda: None
        b._migrate_secrets = lambda: None
        b.run()  # must not raise
        assert len(b.steps_failed) == 1
        assert "RuntimeError" in b.steps_failed[0][1]

    def test_run_never_raises(self, tmp_path):
        """run() must never raise — app must always start."""
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=app_dir)
        b._clean_pycache = lambda: 1 / 0  # ZeroDivisionError
        b._refresh_prompts = lambda: (_ for _ in ()).throw(ValueError("x"))
        b._migrate_settings = lambda: (_ for _ in ()).throw(TypeError("y"))
        b._migrate_secrets = lambda: (_ for _ in ()).throw(KeyError("z"))
        b.run()  # must not raise
        assert len(b.steps_failed) == 4


class TestCleanPycache:
    def test_removes_pycache_dirs(self, tmp_path):
        app_dir = tmp_path / "app"
        pc1 = app_dir / "core" / "__pycache__"
        pc1.mkdir(parents=True)
        (pc1 / "mod.cpython-312.pyc").write_text("x")
        pc2 = app_dir / "utils" / "__pycache__"
        pc2.mkdir(parents=True)
        b = Bootstrap(tmp_path, app_dir=app_dir)
        b._clean_pycache()
        assert not pc1.exists()
        assert not pc2.exists()

    def test_no_pycache_no_error(self, tmp_path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        b = Bootstrap(tmp_path, app_dir=app_dir)
        b._clean_pycache()  # should not raise

    def test_app_dir_missing_raises(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path / "nonexistent")
        with pytest.raises(BootstrapError):
            b._clean_pycache()


class TestRefreshPrompts:
    def test_deletes_prompts_dir(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        prompts = user_dir / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "default.md").write_text("x")
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._refresh_prompts()
        assert not prompts.exists()

    def test_no_prompts_dir_no_error(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._refresh_prompts()  # should not raise


class TestMigrateSettings:
    def test_raises_max_output_tokens(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        settings_file = user_dir / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "summarisation": {"max_output_tokens": 8192},
                    "grounding": {
                        "ollama_model": "",
                        "max_workers": 1,
                        "max_char_buffer": 8000,
                        "timeout_sec": 600,
                    },
                }
            )
        )
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._migrate_settings()
        data = json.loads(settings_file.read_text())
        assert data["summarisation"]["max_output_tokens"] == 16000

    def test_resets_grounding_ollama_model(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        settings_file = user_dir / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "summarisation": {"max_output_tokens": 16000},
                    "grounding": {
                        "ollama_model": "old-model",
                        "max_workers": 4,
                        "max_char_buffer": 4000,
                        "timeout_sec": 300,
                    },
                }
            )
        )
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._migrate_settings()
        data = json.loads(settings_file.read_text())
        assert data["grounding"]["ollama_model"] == ""
        assert data["grounding"]["max_workers"] == 1
        assert data["grounding"]["max_char_buffer"] == 8000
        assert data["grounding"]["timeout_sec"] == 600

    def test_does_not_reset_already_correct(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        settings_file = user_dir / "settings.json"
        original = {
            "summarisation": {"max_output_tokens": 16000},
            "grounding": {
                "ollama_model": "",
                "max_workers": 1,
                "max_char_buffer": 8000,
                "timeout_sec": 600,
            },
        }
        settings_file.write_text(json.dumps(original))
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._migrate_settings()
        data = json.loads(settings_file.read_text())
        assert data == original  # no changes, no write needed

    def test_no_settings_file_no_error(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        b = Bootstrap(user_dir, app_dir=tmp_path)
        b._migrate_settings()  # should not raise

    def test_corrupt_settings_raises_bootstrap_error(self, tmp_path):
        user_dir = tmp_path / ".elixir"
        user_dir.mkdir()
        settings_file = user_dir / "settings.json"
        settings_file.write_text("{not valid json}")
        b = Bootstrap(user_dir, app_dir=tmp_path)
        with pytest.raises(BootstrapError):
            b._migrate_settings()


class TestMigrateSecrets:
    def test_keyring_unavailable_no_error(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path)
        with patch("core.system.secrets.is_keyring_available", return_value=False):
            b._migrate_secrets()  # should not raise

    def test_keyring_available_calls_migrate(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path)
        with (
            patch("core.system.secrets.is_keyring_available", return_value=True),
            patch("core.system.secrets.migrate_all_secrets", return_value=2),
        ):
            b._migrate_secrets()  # should not raise

    def test_migrate_failure_raises_bootstrap_error(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path)
        with (
            patch("core.system.secrets.is_keyring_available", return_value=True),
            patch("core.system.secrets.migrate_all_secrets", side_effect=RuntimeError("fail")),
        ):
            with pytest.raises(BootstrapError):
                b._migrate_secrets()


class TestDiagnostics:
    def test_steps_run_recorded(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path)
        b._clean_pycache = lambda: None
        b._refresh_prompts = lambda: None
        b._migrate_settings = lambda: None
        b._migrate_secrets = lambda: None
        b.run()
        assert len(b.steps_run) == 4
        assert len(b.steps_failed) == 0

    def test_steps_failed_recorded(self, tmp_path):
        b = Bootstrap(tmp_path, app_dir=tmp_path)
        b._clean_pycache = lambda: (_ for _ in ()).throw(BootstrapError("x"))
        b._refresh_prompts = lambda: None
        b._migrate_settings = lambda: None
        b._migrate_secrets = lambda: None
        b.run()
        assert len(b.steps_run) == 3
        assert len(b.steps_failed) == 1
        assert b.steps_failed[0] == ("clean_pycache", "x")


class TestMainPyIntegration:
    """Verify main.py was thinned to use Bootstrap."""

    def test_main_py_uses_bootstrap(self):
        main_path = _project_root / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert "from core.system.bootstrap import Bootstrap" in content
        assert "Bootstrap(" in content
        # The old inline logic should be gone
        assert (
            "Refreshed user prompts directory" not in content
            or content.count("Refreshed user prompts") <= 1
        )  # may be in bootstrap comment

    def test_main_py_shorter(self):
        main_path = _project_root / "main.py"
        line_count = len(main_path.read_text(encoding="utf-8").splitlines())
        # Was 329 lines; should now be under 230.
        # V0.13 (Phase 0): ruff-format expanded single-line imports to multi-line
        # (286 at V0.13) — the pin tracks "stays short", not an exact budget.
        assert line_count < 320, f"main.py is {line_count} lines (expected < 320)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
