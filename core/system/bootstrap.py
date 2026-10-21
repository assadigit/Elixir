"""V18.2.22 (Phase 2.1) — Bootstrap: ordered startup lifecycle for Elixir.

Extracts the 90+ lines of inline startup logic from ``main.py``'s
``if __name__ == "__main__":`` block into a clean, testable class with
explicit ordered steps.

Before (main.py, V18.2.21):
    if __name__ == "__main__":
        _check_dependencies()
        _install_excepthook()
        try:
            # 30 lines: pycache cleanup
        except Exception: ...
        try:
            # 60 lines: prompt refresh + settings force-reset
        except Exception: ...
        try:
            # 10 lines: keyring migration
        except Exception: ...
        from ui_qt.app import run; run()

After:
    if __name__ == "__main__":
        _check_dependencies()
        _install_excepthook()
        Bootstrap(Path.home() / ".elixir").run()
        from ui_qt.app import run; run()

Each step is a method that can be unit-tested independently. The ``run``
method executes them in order, catching ``BootstrapError`` per-step so one
failing step doesn't block the others (defense-in-depth — the app should
always start, even if a migration fails).

Steps (in execution order):
1. ``_clean_pycache`` — delete stale __pycache__ from previous versions
2. ``_refresh_prompts`` — delete user prompt copies so they get refreshed
3. ``_migrate_settings`` — force-reset known-stale settings keys
4. ``_migrate_secrets`` — move plaintext API keys to OS keychain

All steps are best-effort: a failure logs a DEBUG message and continues.
The app launches regardless of bootstrap step outcomes.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class BootstrapError(Exception):
    """A non-fatal bootstrap step failure. Caught per-step, logged, continued."""


class Bootstrap:
    """Ordered startup lifecycle for Elixir.

    Usage::

        from core.system.bootstrap import Bootstrap
        from pathlib import Path
        Bootstrap(Path.home() / ".elixir").run()

    Each step is a separate method so it can be unit-tested. The ``run``
    method calls them in order, catching ``BootstrapError`` per-step.

    Args:
        user_dir: the ``~/.elixir`` directory.
        app_dir: the application source root (for pycache cleanup).
            Defaults to the parent of this file's parent's parent
            (core/system/bootstrap.py → project root).
    """

    def __init__(
        self,
        user_dir: Path,
        app_dir: Path | None = None,
    ) -> None:
        self.user_dir = Path(user_dir)
        self.app_dir = Path(app_dir) if app_dir else self._default_app_dir()
        self._steps_run: list[str] = []
        self._steps_failed: list[tuple[str, str]] = []

    @staticmethod
    def _default_app_dir() -> Path:
        """Resolve the project root from this file's location."""
        # core/system/bootstrap.py → ../../ = project root
        return Path(__file__).resolve().parent.parent.parent

    def run(self) -> None:
        """Execute all bootstrap steps in order.

        Each step is wrapped in try/except BootstrapError. Failures are logged
        at DEBUG and recorded in ``self._steps_failed``. The method never
        raises — the app must always be able to start.
        """
        for step_name, step_fn in [
            ("clean_pycache", self._clean_pycache),
            ("refresh_prompts", self._refresh_prompts),
            ("migrate_settings", self._migrate_settings),
            ("migrate_secrets", self._migrate_secrets),
        ]:
            try:
                step_fn()
                self._steps_run.append(step_name)
            except BootstrapError as exc:
                logger.debug(
                    "bootstrap step %s failed: %s (continuing — non-fatal)",
                    step_name,
                    exc,
                )
                self._steps_failed.append((step_name, str(exc)))
            except Exception as exc:
                # Catch ALL exceptions — a bootstrap failure must never block
                # app launch. This is the defense-in-depth principle.
                logger.debug(
                    "bootstrap step %s raised %s: %s (continuing — non-fatal)",
                    step_name,
                    type(exc).__name__,
                    exc,
                )
                self._steps_failed.append((step_name, f"{type(exc).__name__}: {exc}"))
        if self._steps_failed:
            logger.info(
                "Bootstrap completed: %d step(s) ok, %d failed: %s",
                len(self._steps_run),
                len(self._steps_failed),
                [s for s, _ in self._steps_failed],
            )
        else:
            logger.debug(
                "Bootstrap completed: all %d step(s) ok",
                len(self._steps_run),
            )

    # ── Step 1: pycache cleanup ────────────────────────────────────────────

    def _clean_pycache(self) -> None:
        """Delete stale ``__pycache__`` directories from previous versions.

        V13.42.1: runs AFTER imports (not before) to avoid deleting .pyc
        files being actively imported (the V13.33.0 bug that caused silent
        crashes). Now it runs after all imports are complete, deleting stale
        .pyc files from previous versions so new code is always used after
        extracting a new zip.

        PACKAGING: skipped in a frozen build — there are no .py/.pyc files
        on disk, and walking the whole install folder wastes startup time.
        """
        import sys as _sys

        if getattr(_sys, "frozen", False):
            return
        if not self.app_dir.exists():
            raise BootstrapError(f"app_dir does not exist: {self.app_dir}")
        deleted = 0
        for pc in self.app_dir.rglob("__pycache__"):
            try:
                shutil.rmtree(pc)
                deleted += 1
            except Exception as exc:
                logger.debug(
                    "could not remove %s: %s: %s",
                    pc,
                    type(exc).__name__,
                    exc,
                )
        if deleted > 0:
            logger.info("Cleaned %d stale __pycache__ directory(ies).", deleted)

    # ── Step 2: prompt refresh ────────────────────────────────────────────

    def _refresh_prompts(self) -> None:
        """Delete user prompt copies so they get refreshed from built-ins.

        The user prompts directory (``~/.elixir/prompts/``) is a mirror
        of the built-in ``prompts/`` tree. On each startup we delete the user
        copies so the latest built-ins are always used (not stale copies from
        a previous version).
        """
        prompts_dir = self.user_dir / "prompts"
        if not prompts_dir.exists():
            return  # nothing to refresh
        try:
            shutil.rmtree(prompts_dir)
            logger.info("Refreshed user prompts directory (deleted stale copies).")
        except Exception as exc:
            raise BootstrapError(f"could not delete prompts dir {prompts_dir}: {exc}") from exc

    # ── Step 3: settings migration ────────────────────────────────────────

    def _migrate_settings(self) -> None:
        """Force-reset known-stale settings keys to current defaults.

        This is more aggressive than ``Settings._migrate_defaults`` — it
        handles keys that need to be DELETED (not just updated). The specific
        resets are documented inline.

        V18.1 (audit B1/B2): we do NOT force-reset ``summarisation.model`` —
        the user's model choice is respected. Only token-count and grounding
        config are force-reset (they're not user-facing model selections).
        """
        settings_file = self.user_dir / "settings.json"
        if not settings_file.exists():
            return  # nothing to migrate
        try:
            with open(settings_file, encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise BootstrapError(f"could not read settings.json: {exc}") from exc

        reset_count = 0

        # V13.45.4: Raise max_output_tokens to 16000 (was 8192). Token count,
        # not a model name — safe to force-reset.
        summ = settings.get("summarisation", {})
        if summ.get("max_output_tokens", 16000) < 16000:
            summ["max_output_tokens"] = 16000
            reset_count += 1
        settings["summarisation"] = summ

        # Reset grounding settings to defaults (force langextract to use the
        # correct model + timeout + chunk size).
        gr = settings.get("grounding", {})
        # V13.45.2: Force grounding.ollama_model to "" ALWAYS. The fallback
        # in claim_extractor.py uses the summarisation model when empty.
        if gr.get("ollama_model", "") != "":
            gr["ollama_model"] = ""
            reset_count += 1
        if gr.get("max_workers", 1) != 1:
            gr["max_workers"] = 1
            reset_count += 1
        if gr.get("max_char_buffer", 8000) != 8000:
            gr["max_char_buffer"] = 8000
            reset_count += 1
        if gr.get("timeout_sec", 600) != 600:
            gr["timeout_sec"] = 600
            reset_count += 1
        settings["grounding"] = gr

        # V18.2.26 (A14): Delete the deprecated b3_voting_enabled key.
        # B3 voting has been disabled-by-default since V15.1.1 (damages
        # depth). The _multi_sample_summarize + _b3_cloud_judge methods
        # are formally deprecated in V18.2.26 and slated for removal in V19.
        # Deleting the key here ensures new installs never see it, and
        # existing users who toggled it on get migrated cleanly.
        if "b3_voting_enabled" in summ:
            del summ["b3_voting_enabled"]
            reset_count += 1
            logger.info("Removed deprecated b3_voting_enabled setting (V18.2.26 A14).")
        settings["summarisation"] = summ

        # V18.2.26 (A14): Delete the deprecated translation.backend='nllb'
        # setting if present. NLLB has been removed from the UI since V13.31.0
        # (#13); the module is kept as a fallback for legacy settings.json
        # entries. Deleting the key here routes those users to TranslateGemma.
        tr = settings.get("translation", {})
        if tr.get("backend", "").lower() == "nllb":
            tr["backend"] = "ollama"  # default — TranslateGemma via Ollama
            reset_count += 1
            logger.info(
                "Migrated deprecated translation.backend='nllb' to 'ollama' (V18.2.26 A14)."
            )
        settings["translation"] = tr

        if reset_count > 0:
            try:
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                logger.info(
                    "Force-reset %d stale setting(s) to current defaults.",
                    reset_count,
                )
            except OSError as exc:
                raise BootstrapError(f"could not write settings.json: {exc}") from exc

    # ── Step 4: secret migration ──────────────────────────────────────────

    def _migrate_secrets(self) -> None:
        """Migrate plaintext API keys to OS keychain (best-effort).

        V13.30.0 (P3.5): if ``keyring`` is installed, move API keys from
        ``settings.json`` to the OS keychain. If keyring isn't installed,
        keys stay in settings.json (with a WARNING from secrets.py).
        """
        try:
            from core.system.secrets import (
                is_keyring_available,
                migrate_all_secrets,
            )
        except ImportError as exc:
            raise BootstrapError(f"secrets module unavailable: {exc}") from exc
        if not is_keyring_available():
            logger.debug(
                "keyring not installed — secrets stay in settings.json "
                "(install `keyring` to migrate to OS keychain)"
            )
            return
        try:
            from utils.settings import Settings

            migrated = migrate_all_secrets(Settings())
            if migrated > 0:
                logger.info(
                    "Migrated %d API key(s) to OS keychain on startup.",
                    migrated,
                )
        except Exception as exc:
            raise BootstrapError(f"keyring migration failed: {exc}") from exc

    # ── Diagnostics ──────────────────────────────────────────────────────

    @property
    def steps_run(self) -> list[str]:
        """Return the list of step names that ran successfully."""
        return list(self._steps_run)

    @property
    def steps_failed(self) -> list[tuple[str, str]]:
        """Return the list of (step_name, error_message) for failed steps."""
        return list(self._steps_failed)
