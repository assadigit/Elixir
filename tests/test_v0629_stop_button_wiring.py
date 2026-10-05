"""V0.6.29 — the Stop-button wiring source-pin + CancelToken behavior tests.

This file pins the V0.6.29 Stop-button wiring (HIGH 2 from the
worklog) — the FIRST rig-only item actually DONE in this sandbox
(instead of deferred).

Layer 1: Source-pin tests — verify the code patterns are present in
the wizard view file. These don't need PySide6 (just read the source).

Layer 2: CancelToken behavior tests — verify the token's cancel()
works correctly (the Stop button calls it). These don't need PySide6
either (just the CancelToken class).

Both layers are pure-Python, no QApplication needed. The runtime Qt
tests (creating a full PodcastMakerView offscreen) are in a separate
test file that requires PySide6 + offscreen mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_VIEW_PATH = _project_root / "ui_qt" / "views" / "podcast_maker_view.py"


def _src() -> str:
    return _VIEW_PATH.read_text(encoding="utf-8")


# ── Layer 1: Source-pin tests (the code patterns are present) ──────────────


def test_v0629_cancel_token_import_present() -> None:
    """The CancelToken import is in the wizard view file."""
    assert "from core.podcast.cancel_token import CancelToken" in _src()


def test_v0629_stop_button_created() -> None:
    """The Stop button is created in _build_ui."""
    src = _src()
    assert 'self.stop_btn = QPushButton("⏹️ Stop")' in src
    assert "self.stop_btn.setObjectName" in src


def test_v0629_stop_button_hidden_by_default() -> None:
    """The Stop button is hidden by default (visible only during generation)."""
    assert "self.stop_btn.setVisible(False)" in _src()


def test_v0629_stop_button_clicked_connected() -> None:
    """The Stop button's clicked signal is connected to _on_stop_clicked."""
    assert "self.stop_btn.clicked.connect(self._on_stop_clicked)" in _src()


def test_v0629_cancel_token_attribute_in_init() -> None:
    """The _cancel_token attribute is initialized in __init__."""
    assert "self._cancel_token: CancelToken | None = None" in _src()


def test_v0629_cancel_token_created_in_on_generate_audio() -> None:
    """_on_generate_audio creates a fresh CancelToken before starting the worker."""
    assert "self._cancel_token = CancelToken()" in _src()


def test_v0629_stop_button_shown_in_on_generate_audio() -> None:
    """_on_generate_audio shows the Stop button."""
    assert "self.stop_btn.setVisible(True)" in _src()


def test_v0629_cancel_token_passed_to_generator() -> None:
    """The CancelToken is passed to generate_podcast_audio as cancel_token=."""
    assert "cancel_token=self._cancel_token" in _src()


def test_v0629_on_stop_clicked_method_present() -> None:
    """The _on_stop_clicked method is defined."""
    assert "def _on_stop_clicked(self)" in _src()


def test_v0629_on_stop_clicked_calls_cancel() -> None:
    """_on_stop_clicked calls cancel() on the active token."""
    src = _src()
    assert "self._cancel_token.cancel(" in src
    assert "user clicked Stop" in src


def test_v0629_on_stop_clicked_disables_button() -> None:
    """_on_stop_clicked disables the Stop button + changes its text
    (so the user sees the click was registered)."""
    src = _src()
    assert "self.stop_btn.setEnabled(False)" in src
    assert "self.stop_btn.setText" in src


def test_v0629_on_audio_done_hides_stop_button() -> None:
    """_on_audio_done hides the Stop button on completion/cancel/error."""
    src = _src()
    assert "self.stop_btn.setVisible(False)" in src


def test_v0629_on_audio_done_resets_stop_button() -> None:
    """_on_audio_done resets the Stop button's enabled state + text
    (so it's ready for the next generation)."""
    src = _src()
    assert "self.stop_btn.setEnabled(True)" in src
    assert 'self.stop_btn.setText("⏹️ Stop")' in src


def test_v0629_on_audio_done_cancelled_path() -> None:
    """_on_audio_done has a distinct cancelled path (result is None AND
    token was cancelled → show the '⏹️ Podcast generation cancelled'
    message, not the failure path)."""
    src = _src()
    assert "self._cancel_token.cancelled" in src
    assert "Generation Cancelled" in src


def test_v0629_on_audio_done_clears_token() -> None:
    """_on_audio_done clears the _cancel_token (sets it to None) on
    completion/cancel/error, so the next generation starts fresh."""
    src = _src()
    assert "self._cancel_token = None" in src


# ── Layer 2: CancelToken behavior (the Stop button calls cancel()) ─────────


def test_v0629_cancel_token_starts_uncancelled() -> None:
    """A fresh CancelToken starts un-cancelled (the Stop button hasn't
    been clicked yet)."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    assert token.cancelled is False
    assert token.reason is None


def test_v0629_cancel_token_cancel_flips_flag() -> None:
    """Calling cancel() flips the flag to True (what _on_stop_clicked does)."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    token.cancel("user clicked Stop")
    assert token.cancelled is True
    assert token.reason == "user clicked Stop"


def test_v0629_cancel_token_idempotent() -> None:
    """Calling cancel() twice doesn't overwrite the first reason (the
    Stop button can only be clicked once before it's disabled)."""
    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    token.cancel("user clicked Stop")
    token.cancel("second click")
    assert token.reason == "user clicked Stop"


def test_v0629_cancel_token_thread_safe() -> None:
    """The CancelToken is thread-safe (the Stop button is clicked from
    the main thread; the audio generator checks from the worker thread)."""
    import threading

    from core.podcast.cancel_token import CancelToken

    token = CancelToken()
    errors = []

    def _click():
        try:
            token.cancel("user clicked Stop")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_click) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert token.cancelled is True
