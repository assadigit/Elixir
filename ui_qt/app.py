"""Main application window — slim top bar + fixed sidebar + stacked pages.

  ┌──────────────────────────────────────────────────────────────────────┐
  │  ( drag region )                                        │ ─ □ ✕ │ top bar
  ├──────────────┬───────────────────────────────────────────────────────┤
  │ ◆ Elixir     │                                                       │
  │ ▤ Home       │                                                       │
  │ PROCESSING   │        ( stacked page — Home / Queue / Scanner /      │
  │ ▤ ▤ ▤       │          Bullet Audit / Hallucination / Convert )     │
  │ UTILITIES    │                                                       │
  │ ▤ ▤ ▤ ▤ ▤   │                                                       │
  │ AUDIO        │                                                       │
  │ ▤ ▤ ▤       │                                                       │
  │ ──────────── │                                                       │
  │ ⚙ Settings   │  ──────────────────────────────────────────────────────  │
  │ ℹ About      │  ● Connected                                   ☀ Light ▾ │ status strip
  └──────────────┴───────────────────────────────────────────────────────┘

M2 (UI/UX redesign): the fixed compact left rail is the primary nav (spec
§5); the experimental four are unlisted (decision Q2 — reachable via About
& System + DnD → Queue); the header is reduced to the frameless window
controls over the drag region (decision Q7 — the wizard button is gone;
the home hero owns the conversion entry).  V0.6.85 (Round-5 §4): the
duplicate header Settings action AND the backend/provider pill are RETIRED
from the bar — Settings lives ONLY in the sidebar footer, and provider
selection lives ONLY in the Settings dialog (AI → Local Model / API); the
bottom status strip carries the truthful backend connection state
(Round-5 §5: core.system.backend_connection — never a hardcoded 'Ready').
Closing the window while a conversion is running asks for confirmation
first.  Window size + position persist between launches.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.system import backend_connection
from ui_qt.components.icons import icon
from ui_qt.components.modal_button_fit import install_modal_button_fit
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings import SettingsDialog
from ui_qt.theme import rgba, theme_manager
from ui_qt.views.convert_view import ConvertView
from ui_qt.views.output_scanner_view import OutputScannerView
from ui_qt.views.quarantine_view import QuarantineView
from ui_qt.views.queue_view import QueueView
from ui_qt.views.validate_dialog import ValidateDialog
from utils.geometry import (
    DEFAULT_H,
    DEFAULT_W,
    GEOMETRY_SCHEMA_VERSION,
    minimum_window_size,
    restored_geometry_is_visible,
    sanitize_restore_plan,
    target_default_size,
)
from utils.settings import user_data_dir
from utils.single_instance import focus_ack_indicates_visible, primary_reply

logger = logging.getLogger(__name__)


# PACKAGING (build_installer.py): resolved via user_data_dir() so the frozen
# (installed) build reads/writes %LOCALAPPDATA%\Elixir\window_geometry.json
# instead of ~/.elixir (source behavior unchanged).
_GEOMETRY_FILE = user_data_dir() / "window_geometry.json"


class ElixirWindow(QMainWindow):
    """Top-level window for the PySide6 UI."""

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"Elixir  ·  v{self._app_version()}")
        # V0.6.68: the ORIGINAL container size is back. V13.31.0 had shrunk
        # the default 20% ("was 760x540, now 608x432 — more compact"), and
        # the 2026-10-26 field report landed on exactly that: a fresh
        # install has no saved geometry, so every new user met the compact
        # default — "not in the original container size … very compact and
        # small … it has scroll". The 760x540 default (and the 1600x1000
        # restore ceiling) live in utils.geometry — the single source of
        # truth.
        #
        # V0.6.81: the minimum rose 560x400 → 760x440 (the one-column
        # no-clip floor); the default OPENING size became screen-aware.
        #
        # V0.6.83 (Round-3 §2.2): the minimum is now SCREEN-DERIVED — the
        # 1100x720 band minimum wherever the work area supports it (the
        # Round-3 composition: at 1100 the responsive rail is ~198 and the
        # Quick Tools grid holds two comfortable columns), scaling down to
        # ~96% of the work area on smaller screens, never below the 760x440
        # absolute floor. utils.geometry owns the decision (pure, tested).
        self.setMinimumSize(*self._window_minimum())
        self._restore_geometry()

        # V0.6.77 (visual-fidelity pass): the reference presents ELIXIR as
        # one unified, softly elevated surface — rounded outer corners,
        # a subtle border/shadow, integrated top chrome, and working
        # min/max/close controls in the top bar's right end. The native
        # frame goes frameless; the backdrop + AppShell reproduce the
        # mockup's ~21 px floating margin (0 when maximized — see
        # _apply_chrome_state). Drag = the top bar; resize = the window's
        # edges via the native system resize (startSystemResize), so Snap
        # layouts and DPI behaviour stay the platform's own.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._settings_dialog: SettingsDialog | None = None
        self._validate_dialog: ValidateDialog | None = None

        # V0.6.69/V0.6.77: the poll-loop state — initialised BEFORE the UI
        # builds (the backend pill paints from the cached verdict during
        # shell construction, before the first probe lands).
        # V0.6.85 (Round-5 §5): the poll now feeds the STATUS STRIP's
        # connection state (the header pill is retired); the one-shot API
        # provider check has its own worker ref here.
        self._llm_poll_timer = None
        self._llm_probe_worker = None
        self._llm_endpoints_snapshot = None
        self._llm_last_statuses: list | None = None
        self._api_check_worker = None
        self._backend_state: str | None = None
        self._backend_detail: str = ""

        # ── the floating shell (V0.6.77) ───────────────────────────
        # backdrop (the desktop-like ground) → AppShell (the rounded
        # surface) → [sidebar | topbar+content] / status strip.
        backdrop = QFrame()
        backdrop.setObjectName("WindowBackdrop")
        self._backdrop = backdrop
        self._backdrop_lay = QVBoxLayout(backdrop)
        self._backdrop_lay.setContentsMargins(21, 21, 21, 21)
        self._backdrop_lay.setSpacing(0)

        self._shell = QFrame()
        self._shell.setObjectName("AppShell")
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        self._shell_shadow = QGraphicsDropShadowEffect(self)
        self._shell_shadow.setBlurRadius(34)
        self._shell_shadow.setOffset(0, 9)
        # The drop shadow derives from the palette's backdrop token — the
        # reference's measured density (darkest ~#AFAFAA at the shell's
        # bottom edge on a #F2EFE8 ground ⇒ a ~17% luminance wash at ~35%
        # opacity, offset down, blurred) — token-driven in both themes.
        _bd = QColor(theme_manager.palette.bg_backdrop)
        _sh = QColor(
            max(0, _bd.red() * 17 // 100),
            max(0, _bd.green() * 17 // 100),
            max(0, _bd.blue() * 17 // 100),
        )
        _sh.setAlpha(88)
        self._shell_shadow.setColor(_sh)
        self._shell.setGraphicsEffect(self._shell_shadow)
        shell_lay = QVBoxLayout(self._shell)
        shell_lay.setContentsMargins(1, 1, 1, 1)  # keep children off the hairline
        shell_lay.setSpacing(0)

        # The reference's body grid: the fixed sidebar on the left, the
        # top bar + stacked pages in the right column (the bar belongs to
        # the content area, NOT the full window width).
        self._build_content()  # creates self.sidebar + self.content_stack
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        body_lay.addWidget(self.sidebar)
        body_col = QVBoxLayout()
        body_col.setContentsMargins(0, 0, 0, 0)
        body_col.setSpacing(0)
        body_col.addWidget(self._build_top_bar())
        body_col.addWidget(self.content_stack, 1)
        body_lay.addLayout(body_col, 1)
        shell_lay.addWidget(body, 1)
        shell_lay.addWidget(self._build_status_strip())
        self._backdrop_lay.addWidget(self._shell)
        # V0.6.83 (Round-3 §3.1): seed the responsive rail from the current
        # window size — resizeEvent keeps it tracking clamp(180, 0.18*w, 260)
        # from here on.
        self._update_sidebar_rail()

        self.setCentralWidget(backdrop)

        # enable window-wide drag-and-drop
        self.setAcceptDrops(True)

        # V0.6.69: the live local-LLM status lights + their poll loop —
        # this REPLACES the removed startup "Ollama not running" warning
        # dialog (a missing local server is a state to show, never a
        # load-time error to nag with; the 2026-10-26 field report).
        # V0.6.77: the top bar carried the reference's backend pill fed by
        # the same loop. V0.6.85 (Round-5 §4/§5): the pill is RETIRED —
        # the loop's PRIMARY sink is now the status strip's connection
        # state (plus the About & System lights, unchanged); for API
        # providers the state comes from the one-shot bounded check
        # instead (see _run_api_backend_check).
        self._setup_llm_lights_monitoring()
        # Round-5 §5.2: "Trigger checks on application startup" — local
        # providers resolve from the poll loop's immediate first tick;
        # API providers get their one bounded check here.
        self._run_api_backend_check()

        # V0.6.77: the frameless chrome interactions — drag the top bar,
        # double-click it to maximise/restore, grab the backdrop edges to
        # resize (native system operations; children keep their clicks).
        self._top_bar.installEventFilter(self)
        self._backdrop.installEventFilter(self)

        self._apply_chrome_state()

    # ══════════════════════════════════════════════════════════════════════
    # Top bar
    # ══════════════════════════════════════════════════════════════════════
    def _build_top_bar(self) -> QWidget:
        """The reference's top bar — chrome over the MAIN CONTENT ONLY.

        V0.6.77 (visual-fidelity pass): the brand moved into the sidebar
        (the reference's leaf + wordmark row); the top bar's left ~60% is
        intentionally empty in the reference, with the controls clustered
        right. V0.6.84 (Round-4 §5): the top-bar theme toggle was REMOVED
        (the status strip's Light/Dark selector is the app's single visible
        theme control). V0.6.85 (Round-5 §4.3): the backend/provider pill
        AND the duplicate labelled Settings action are REMOVED as well —
        provider selection lives ONLY in Settings (AI → Local Model /
        API), Settings itself lives ONLY in the sidebar footer, and the
        header keeps just the subtle divider + the frameless window
        controls (min / max-restore / close). The empty bar area remains
        the window drag region (press to startSystemMove; double-click
        toggles maximise) — its spacing redistributes naturally with the
        two retired controls gone (no placeholder slots are left behind).
        """
        bar = QFrame()
        bar.setObjectName("TopBar")
        # V0.6.83 (Round-3 §3.3/§6): 68 → 50. The correction spec pins the
        # header at "roughly 44–52 logical px" (§6: "Header: around 44–52
        # px") — the V0.6.77 68 was the reference mockup's chunkier frame;
        # every control fits at 50 and the drag region stays ≥ 40 px tall.
        bar.setFixedHeight(50)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 10, 0)
        lay.setSpacing(0)

        # The reference's empty left stretch — and the drag region.
        lay.addStretch(1)

        # ── the subtle divider before the window controls ─────────────
        # V0.6.85 (Round-5 §4.3): with the pill and the Settings action
        # retired, the divider is the natural seam between the app's empty
        # drag region and the frameless window controls — the retired
        # controls' spacing folds into the drag region ("redistribute
        # remaining header spacing naturally").
        divider = QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedHeight(32)
        lay.addWidget(divider)
        lay.addSpacing(18)

        # ── the frameless window controls (V0.6.77) ───────────────────
        # Real controls, not decoration: min/max-restore/close with the
        # reference's ~54 px pitch; the close hover gets the standard red.
        self.min_btn = QPushButton()
        self.min_btn.setObjectName("WinCtrl")
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setToolTip("Minimize")
        self.min_btn.clicked.connect(self.showMinimized)
        lay.addWidget(self.min_btn)

        self.max_btn = QPushButton()
        self.max_btn.setObjectName("WinCtrl")
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.setToolTip("Maximize / restore")
        self.max_btn.clicked.connect(self._toggle_maximize)
        lay.addWidget(self.max_btn)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.close)
        lay.addWidget(self.close_btn)

        self._refresh_top_bar_icons()
        self._top_bar = bar
        return bar

    def _refresh_top_bar_icons(self) -> None:
        p = theme_manager.palette
        # V0.6.84 (Round-4 §5): no top-bar theme glyph anymore — the status
        # strip's sun/moon selector (StatusThemeBtn) is the one control.
        # V0.6.85 (Round-5 §4.3): no Settings glyph either — the sidebar's
        # footer destination is the app's only Settings entry.
        self.min_btn.setIcon(icon("minus", p.text_secondary, 15))
        self.max_btn.setIcon(
            icon(
                "restore" if self.isMaximized() else "square",
                p.text_secondary,
                13,
            )
        )
        self.close_btn.setIcon(icon("x", p.text_secondary, 15))

    def _toggle_theme(self) -> None:
        theme_manager.toggle()
        self._refresh_top_bar_icons()
        self._refresh_status_strip()
        self.convert_view.refresh_theme()
        # M2: the home view re-flattens the hero illustration against the
        # new surface colour; the fixed rail's nav items re-tint.
        if hasattr(self, "home_view"):
            self.home_view.refresh_theme()
        if hasattr(self, "sidebar"):
            self.sidebar.refresh_theme()
        if hasattr(self, "queue_view"):
            self.queue_view.refresh_theme()
        if hasattr(self, "output_scanner_view"):
            self.output_scanner_view.refresh_theme()
        if hasattr(self, "quarantine_view"):
            self.quarantine_view.refresh_theme()
        # V18.20.4.6 (W-b20): the dead branch that used to sit here was
        # removed — it refreshed a hallucination-audit view attribute
        # that is never assigned anywhere (the hallucination audit opens
        # from convert_view, not the main window).

    # ══════════════════════════════════════════════════════════════════════
    # The bottom status strip (V0.6.77, visual-fidelity pass;
    # V0.6.85 Round-5 §5 — the truthful connection state)
    # ══════════════════════════════════════════════════════════════════════
    def _build_status_strip(self) -> QWidget:
        """The reference's thin persistent strip across the whole inner
        shell: the BACKEND CONNECTION STATE (dot + truthful label, left)
        + the transient app-activity word, a divider, the sun/moon glyph,
        the theme name and a chevron on the right. The theme control is
        REAL (a menu with Light / Dark).

        V0.6.85 (Round-5 §5): the left side no longer shows a hardcoded
        'Ready' — it renders the explicit connection-state model from
        ``core.system.backend_connection`` (Checking… / Connected /
        Backend offline / API unavailable / Not configured / Model
        unavailable), each with its own dot tint (muted green / amber /
        muted red / gray). The wizard's conversion lifecycle keeps its own
        DISTINCT activity word beside it ("Converting…" while a run is in
        flight) — "the UI is running" is never conflated with "AI
        operations can run" (spec §5.1).
        """
        strip = QFrame()
        strip.setObjectName("StatusStrip")
        # V0.6.83 (Round-3 §6): 56 → 42. The correction spec pins the bottom
        # strip at "approximately 38–44 px" — 42 sits mid-band with the dot,
        # status word, divider and theme control all clearing it comfortably.
        strip.setFixedHeight(42)
        self._status_strip = strip
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(36, 0, 20, 0)
        lay.setSpacing(8)

        # ── the backend connection state (Round-5 §5.3: dot + label) ──
        self._backend_dot = QLabel()
        self._backend_dot.setFixedSize(14, 14)
        lay.addWidget(self._backend_dot)

        self._backend_label = QLabel("")
        self._backend_label.setObjectName("SidebarLabel")
        lay.addWidget(self._backend_label)

        # ── the transient activity word (a run in flight) — hidden when
        #    idle, ALWAYS conceptually distinct from the backend state.
        self._activity_sep = QLabel("·")
        self._activity_sep.setObjectName("SidebarLabel")
        self._activity_sep.setVisible(False)
        lay.addWidget(self._activity_sep)
        self._activity_label = QLabel("")
        self._activity_label.setObjectName("SidebarLabel")
        self._activity_label.setVisible(False)
        lay.addWidget(self._activity_label)
        lay.addStretch(1)

        divider = QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedHeight(24)
        lay.addWidget(divider)
        lay.addSpacing(10)

        self._status_theme_btn = QPushButton("Light Theme")
        self._status_theme_btn.setObjectName("StatusThemeBtn")
        self._status_theme_btn.setCursor(Qt.PointingHandCursor)
        self._status_theme_btn.setToolTip("Switch between the light and dark themes")
        self._status_theme_btn.clicked.connect(self._show_theme_menu)
        lay.addWidget(self._status_theme_btn)

        # The honest opening word: a check is about to run (never 'Ready').
        self.set_backend_state(backend_connection.CHECKING, "starting the first backend probe…")
        self._refresh_status_strip()
        return strip

    def _refresh_status_strip(self) -> None:
        """Re-paint the connection dot + theme control from the CURRENT
        palette (the state LABEL itself is only ever set by
        ``set_backend_state`` — the model owns the word)."""
        p = theme_manager.palette
        if not hasattr(self, "_backend_dot"):
            return
        self._paint_backend_dot()
        glyph = "sun" if not p.is_dark else "moon"
        label = "Light Theme" if not p.is_dark else "Dark Theme"
        self._status_theme_btn.setText(label + "  \u25be")  # the reference's dropdown chevron
        self._status_theme_btn.setIcon(icon(glyph, p.text_secondary, 14))
        self._status_theme_btn.setIconSize(QSize(14, 14))

    def _backend_state_color(self) -> QColor:
        """The dot tint for the CURRENT state + theme (spec §5.3: muted
        green / amber / muted red / gray — the label always carries the
        state too, never color alone)."""
        p = theme_manager.palette
        sev = backend_connection.STATE_SEVERITY.get(self._backend_state, "neutral")
        return QColor(
            {
                "ok": p.success,
                "warn": p.warning,
                "bad": p.error,
                "neutral": p.text_muted,
            }.get(sev, p.text_muted)
        )

    def _paint_backend_dot(self) -> None:
        pm = QPixmap(14, 14)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._backend_state_color())
        painter.drawEllipse(3, 3, 8, 8)
        painter.end()
        self._backend_dot.setPixmap(pm)

    def set_backend_state(self, state: str, detail: str = "") -> None:
        """Round-5 §5: render the connection state — the truthful word +
        tinted dot + a detail tooltip (never a secret; never 'Ready').

        ``state`` is one of ``backend_connection``'s constants; a no-op
        when the strip is not built yet or the state is unchanged."""
        if not hasattr(self, "_backend_label"):
            return
        label = backend_connection.STATE_LABELS.get(state, state)
        if self._backend_state == state and self._backend_detail == detail:
            return
        self._backend_state = state
        self._backend_detail = detail
        self._backend_label.setText(label)
        self._paint_backend_dot()
        # The tooltip: the provider + the one-line evidence behind the
        # state (the same probe text the About & System lights show).
        cfg = getattr(self, "_backend_cfg", None)
        head = f"{cfg.display_name} — {label}" if cfg is not None else label
        tip = [head]
        if detail:
            tip.append(detail)
        tip.append("Provider selection lives in Settings → AI (Local Model / API).")
        self._backend_label.setToolTip("\n".join(tip))
        self._backend_dot.setToolTip("\n".join(tip))

    # ── the state model's drivers (Round-5 §5.2) ─────────────────────
    def _refresh_backend_state_from_statuses(self) -> None:
        """Local providers: derive the state from the poll loop's latest
        REAL verdicts (the V0.6.69 loop — loopback GETs, worker thread,
        5 s cadence; nothing new is polled)."""
        cfg = self._snapshot_backend_config()
        if cfg is None or cfg.is_api:
            return
        state, detail = backend_connection.derive_local_backend_state(
            self._llm_last_statuses, cfg.client_key, cfg.model
        )
        self.set_backend_state(state, detail)

    def _snapshot_backend_config(self):
        """Main-thread snapshot of the provider configuration (fail-soft)."""
        try:
            from core.system.backend_connection import snapshot_backend_config

            cfg = snapshot_backend_config(self.controller.settings)
            self._backend_cfg = cfg
            return cfg
        except Exception:
            logger.debug("backend config snapshot failed", exc_info=True)
            return None

    def _run_api_backend_check(self) -> None:
        """API providers: ONE bounded async check (startup + after a
        Settings close — a configuration change). NEVER a repeating poll
        against a paid endpoint (spec §5.2: "Avoid aggressive polling");
        the request runs on a SimpleWorker so the UI never freezes.
        """
        cfg = self._snapshot_backend_config()
        if cfg is None or not cfg.is_api:
            return
        if not cfg.api_base_url or not cfg.api_key or not cfg.api_model:
            missing = (
                "base URL" if not cfg.api_base_url else "API key" if not cfg.api_key else "model"
            )
            self.set_backend_state(
                backend_connection.NOT_CONFIGURED,
                f"{cfg.display_name}: no {missing} configured (Settings → AI → API).",
            )
            return
        self.set_backend_state(backend_connection.CHECKING, f"checking {cfg.display_name}…")
        prev = self._api_check_worker
        if prev is not None:
            try:
                if prev.is_running():
                    return  # a check is already in flight — bounded, no stacking
            except RuntimeError:
                pass
        spec = (cfg.provider, cfg.api_base_url, cfg.api_key, cfg.api_model)

        def _probe():
            return backend_connection.test_api_provider_connection(*spec)

        worker = SimpleWorker(_probe)
        self._api_check_worker = worker  # Python ref (GC hazard)
        worker.finished.connect(self._on_api_check_finished)
        worker.failed.connect(self._on_api_check_failed)
        worker.start()

    @Slot(object)
    def _on_api_check_finished(self, result) -> None:
        """Worker done — classify the REAL outcome (never a guess)."""
        self._api_check_worker = None
        ok, msg = result if isinstance(result, tuple) else (False, str(result))
        cfg = getattr(self, "_backend_cfg", None)
        name = cfg.display_name if cfg is not None else "API provider"
        if ok:
            self.set_backend_state(backend_connection.CONNECTED, f"{name}: {msg}")
        else:
            self.set_backend_state(backend_connection.API_UNAVAILABLE, f"{name}: {msg}")

    @Slot(str)
    def _on_api_check_failed(self, error: str) -> None:
        """The probe itself exploded — an unavailable API is the honest
        verdict (fail-soft, quiet log)."""
        self._api_check_worker = None
        cfg = getattr(self, "_backend_cfg", None)
        name = cfg.display_name if cfg is not None else "API provider"
        self.set_backend_state(backend_connection.API_UNAVAILABLE, f"{name}: {error}")
        logger.debug("api backend check failed: %s", error)

    def _show_theme_menu(self) -> None:
        """The theme selector's Light / Dark menu (the chevron's promise)."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setObjectName("StatusThemeMenu")
        light = menu.addAction("Light Theme")
        dark = menu.addAction("Dark Theme")
        current = theme_manager.mode
        light.setChecked(current == "light")
        dark.setChecked(current == "dark")
        light.setCheckable(True)
        dark.setCheckable(True)
        chosen = menu.exec(
            self._status_theme_btn.mapToGlobal(self._status_theme_btn.rect().bottomLeft())
        )
        if chosen is light and current != "light" or chosen is dark and current != "dark":
            self._toggle_theme()

    def set_status(self, text: str, busy: bool = False) -> None:
        """The ACTIVITY surface — the wizard's conversion lifecycle (and
        any future worker) drives this transient word beside the backend
        state. V0.6.85 (Round-5 §5.1): conceptually DISTINCT from backend
        readiness — "Converting…" never implies the backend is up, and the
        connection state keeps its own label; an empty text hides the
        word (there is no hardcoded 'Ready' anywhere)."""
        if not hasattr(self, "_activity_label"):
            return
        self._activity_label.setText(text)
        shown = bool(text)
        self._activity_label.setVisible(shown)
        self._activity_sep.setVisible(shown)

    # ══════════════════════════════════════════════════════════════════════
    # Frameless-window chrome (V0.6.77)
    # ══════════════════════════════════════════════════════════════════════
    _RESIZE_EDGE_PX = 10  # the grab band around the true window edges

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _apply_chrome_state(self) -> None:
        """Floating-when-normal, edge-to-edge-when-maximized: the ~21 px
        backdrop margin + the shell's rounded corners + shadow exist only
        in the windowed state (the standard frameless convention — a
        maximized surface must own the work area, square corners, no
        gap). The QSS `[maximized=true]` variants zero the radii."""
        maximized = self.isMaximized()
        m = 0 if maximized else 21
        self._backdrop_lay.setContentsMargins(m, m, m, m)
        self._shell_shadow.setEnabled(not maximized)
        for w in (self._shell, self.sidebar, self._top_bar):
            w.setProperty("maximized", maximized)
            w.style().unpolish(w)
            w.style().polish(w)
        strip = getattr(self, "_status_strip", None)
        if strip is not None:
            strip.setProperty("maximized", maximized)
            strip.style().unpolish(strip)
            strip.style().polish(strip)
        if hasattr(self, "max_btn"):
            self._refresh_top_bar_icons()

    def changeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802
        super().changeEvent(event)
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.WindowStateChange:
            self._apply_chrome_state()

    # ── drag + edge-resize (native system operations) ─────────────────
    def _start_system_move(self) -> None:
        handle = self.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def _edge_at(self, pos) -> Qt.Edge:
        """The resize edge under a window-relative point (None-safe)."""
        from PySide6.QtCore import QPoint

        assert isinstance(pos, QPoint)
        band = self._RESIZE_EDGE_PX
        edges = Qt.Edge(0)
        if self.isMaximized():
            return Qt.Edge(0)
        if pos.x() <= band:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - band:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= band:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - band:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _start_system_resize(self, edges) -> None:
        handle = self.windowHandle()
        if handle is not None and int(edges) != 0:
            handle.startSystemResize(edges)

    def _cursor_for_edges(self, edges) -> Qt.CursorShape:
        from PySide6.QtCore import QEvent  # noqa: F401

        combo = int(edges)
        table = {
            int(Qt.Edge.LeftEdge): Qt.CursorShape.SizeHorCursor,
            int(Qt.Edge.RightEdge): Qt.CursorShape.SizeHorCursor,
            int(Qt.Edge.TopEdge): Qt.CursorShape.SizeVerCursor,
            int(Qt.Edge.BottomEdge): Qt.CursorShape.SizeVerCursor,
            int(Qt.Edge.LeftEdge | Qt.Edge.TopEdge): Qt.CursorShape.SizeFDiagCursor,
            int(Qt.Edge.RightEdge | Qt.Edge.BottomEdge): Qt.CursorShape.SizeFDiagCursor,
            int(Qt.Edge.RightEdge | Qt.Edge.TopEdge): Qt.CursorShape.SizeBDiagCursor,
            int(Qt.Edge.LeftEdge | Qt.Edge.BottomEdge): Qt.CursorShape.SizeBDiagCursor,
        }
        return table.get(combo, Qt.CursorShape.ArrowCursor)

    def _open_wizard(self) -> None:
        """V5.3.2: Open the Process Wizard as a modal dialog.

        V0.6.77: the wizard's conversion lifecycle drives the ACTIVITY
        word in the status strip (Converting… / Conversion finished).
        V0.6.85 (Round-5 §5.1): the activity word is conceptually distinct
        from the backend connection state — the strip's left side keeps
        rendering the truthful backend state (Connected / Backend
        offline / …) the whole time, and the activity word clears when the
        dialog closes (there is no 'Ready' to fall back to)."""
        from ui_qt.views.wizard_view import WizardView

        dlg = WizardView(self.controller, self)
        try:
            dlg.conversion_started.connect(lambda: self.set_status("Converting…"))
            dlg.conversion_complete.connect(lambda _r: self.set_status("Conversion finished"))
        except Exception:
            logger.debug("wizard status wiring unavailable", exc_info=True)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        self.set_status("")

    def _open_merge_dialog(self) -> None:
        """V10.21.0: Open the multi-PDF merge dialog.

        V18.20.4.9 (W-b12): the merge itself used to run synchronously in
        this click slot (the UI froze for the whole merge). It now runs on
        a SimpleWorker (P4 W-b11 pattern: worker ref on self, re-entrancy
        guard, merge button disabled while running and re-enabled in BOTH
        outcome handlers); on failure the traceback is logged at WARNING
        BEFORE the user box (W-b17 crash-visibility — was str(e)-only).
        """
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        # Let user select multiple book output directories
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder containing book conversions to merge",
            "",
            QFileDialog.ShowDirsOnly,
        )
        if not folder:
            return

        # Find all book subdirectories
        base = Path(folder)
        book_dirs = [d for d in base.iterdir() if d.is_dir() and (d / "summaries").exists()]
        if not book_dirs:
            QMessageBox.information(
                self,
                "No books found",
                f"No book conversion directories found in: {folder}\n\n"
                f"Each book should have a 'summaries' subfolder.",
            )
            return

        # Let user select output location
        output_folder = QFileDialog.getExistingDirectory(
            self,
            "Select output folder for merged result",
            str(base),
            QFileDialog.ShowDirsOnly,
        )
        if not output_folder:
            return

        # Run the merge (W-b12: off the UI thread)
        worker = getattr(self, "_merge_worker", None)
        try:
            in_flight = worker is not None and worker.is_running()
        except RuntimeError:
            in_flight = False  # worker already deleteLater'd itself
        if in_flight:
            return  # a merge is already in flight — don't stack workers

        btn = getattr(self, "merge_btn", None)
        if btn is not None:
            btn.setEnabled(False)
        # The finished handler quotes the book count in its box.
        self._merge_book_dirs = book_dirs

        def _work():
            from core.pipeline.multi_pdf_merge import merge_books

            try:
                return merge_books(book_dirs, Path(output_folder), log_callback=None)
            except Exception:
                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE
                # the "Merge error" box (was str(e)-only — zero
                # diagnostics for support).
                logger.warning("library merge raised — traceback follows", exc_info=True)
                raise

        w = SimpleWorker(_work)
        self._merge_worker = w  # Python ref — the QObject can't be GC'd mid-run
        w.finished.connect(self._on_merge_finished)
        w.failed.connect(self._on_merge_failed)
        w.start()

    def _on_merge_finished(self, result) -> None:
        """W-b12: main-thread handler — re-enable + the identical boxes."""
        btn = getattr(self, "merge_btn", None)
        if btn is not None:
            btn.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox

        book_dirs = self._merge_book_dirs
        if result:
            QMessageBox.information(
                self, "Merge complete", f"Merged {len(book_dirs)} books.\nResult: {result}"
            )
        else:
            QMessageBox.warning(self, "Merge failed", "No summaries found to merge.")

    def _on_merge_failed(self, error: str) -> None:
        """W-b12/W-b18: a raising merge must never leave the button stuck
        disabled — re-enable + the existing error box (same title/text
        shape; the diagnostics went to the log via the W-b17 wrapper)."""
        btn = getattr(self, "merge_btn", None)
        if btn is not None:
            btn.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Merge error", error)

    # V13.31.0 (#9): Quick Convert removed per user request
    # The full Process Wizard covers all use cases.

    # ══════════════════════════════════════════════════════════════════════
    # Content
    # ══════════════════════════════════════════════════════════════════════
    def _build_content(self) -> QWidget:
        # M2 (UI/UX redesign): the north QTabWidget is RETIRED — the shell is
        # now a fixed compact LEFT sidebar (spec §5; user decision Q1 — the
        # Audio group is IN) + a QStackedWidget content area. All five former
        # tab pages are kept in the stack, code intact; the experimental four
        # (Queue / Output Scanner / Bullet Audit / Hallucination Audit) are
        # simply UNLISTED from primary navigation (decision Q2 — hiding ≠
        # removing; they stay reachable via the navigation facade, DnD →
        # Queue, and the About & System "Experimental tools…" section).
        # V13.31.0 history: Podcast Maker tab removed (modal from the
        # dashboard); Hallucination Audit tab added; tools menu → About.
        from PySide6.QtWidgets import QStackedWidget

        from ui_qt.components.sidebar import Sidebar

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("MainStack")
        self._page_index: dict[str, int] = {}
        self._page_active: list[str | None] = []  # stack index → sidebar key

        def _add_page(key: str, page: QWidget, active_key: str | None = None) -> None:
            """Register a stack page under ``key`` (facade lookups) and note
            which sidebar item (if any) shows as active while it is shown."""
            self._page_index[key] = self.content_stack.addWidget(page)
            self._page_active.append(active_key)

        def _wrap_scroll(view: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            scroll.setWidget(view)
            return scroll

        # Page: Home (M2 landing — purpose line + Full Conversion hero;
        # the Quick Tools grid lands with the grid commit). The convert
        # view is CONSTRUCTED first: the home view's hero CTA and tool
        # cards route through the existing wizard entry + tool dispatch.
        self.convert_view = ConvertView(self.controller)
        from ui_qt.views.home_view import HomeView

        self.home_view = HomeView()
        # Decision Q7: the hero CTA opens the SAME modal WizardView the
        # removed header button used — connect, never fork.
        self.home_view.start_requested.connect(self._open_wizard)
        # Quick Tool cards route through the EXISTING convert_view
        # tool-key dispatch (no re-implementation).
        self.home_view.tool_clicked.connect(self.convert_view._on_tool_clicked)
        # V0.6.78: "View all tools →" lands on the existing full tool
        # dashboard page (the audio group lives there).
        self.home_view.view_all_requested.connect(lambda: self.switch_to_page("convert"))
        _add_page("home", _wrap_scroll(self.home_view), active_key="home")

        # Page: Convert (the legacy tool-dashboard page — UNLISTED since
        # the home view took over as the landing page; kept intact as the
        # controller-bridge + progress-panel + completion host, and still
        # reachable through the navigation facade.)
        _add_page("convert", _wrap_scroll(self.convert_view))

        # Page: Queue (batch processing — unlisted, decision Q2)
        self.queue_view = QueueView(self.controller)
        _add_page("queue", _wrap_scroll(self.queue_view))

        # Page: Output Scanner (unlisted, decision Q2)
        self.output_scanner_view = OutputScannerView(self.controller)
        _add_page("output_scanner", _wrap_scroll(self.output_scanner_view))

        # Page: Bullet Audit (quarantine — dropped-bullet audit & restore;
        # unlisted, decision Q2)
        self.quarantine_view = QuarantineView(self.controller)
        _add_page("quarantine", _wrap_scroll(self.quarantine_view))

        # Page: Hallucination Audit (V13.31.0 #1 — a lightweight launcher
        # wrapper around the HallucinationAuditDialog, kept verbatim;
        # unlisted, decision Q2)
        hallucination_widget = QWidget()
        h_lay = QVBoxLayout(hallucination_widget)
        h_lay.setContentsMargins(20, 16, 20, 16)
        h_lay.setSpacing(10)
        h_title = QLabel("🛡️ Hallucination Audit")
        h_title.setObjectName("H2")
        h_lay.addWidget(h_title)
        h_desc = QLabel(
            "Check bullets against source text using 4 signals: verbatim match, "
            "semantic similarity, content-word overlap, and number/quote verification.\n\n"
            "Paste source text and bullets below, then click Audit."
        )
        h_desc.setObjectName("Caption")
        h_desc.setWordWrap(True)
        h_lay.addWidget(h_desc)
        h_btn = QPushButton("🛡️ Open Hallucination Audit Dialog")
        h_btn.setObjectName("Primary")
        h_btn.clicked.connect(lambda: self._open_hallucination_audit())
        h_lay.addWidget(h_btn)
        h_lay.addStretch()
        _add_page("hallucination_audit", _wrap_scroll(hallucination_widget))

        # The fixed rail (spec §5): emits navigate(key); the window routes.
        # V0.6.77: the rail no longer wraps the stack itself — __init__'s
        # shell grid places it beside the top-bar+content column and the
        # status strip spans the full inner width below both.
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self._on_sidebar_navigate)

        # Page-switch hooks — the _on_tab_changed equivalents must keep
        # firing (queue badge refresh, quarantine auto-reload).
        self.content_stack.currentChanged.connect(self._on_page_changed)
        # V0.6.77: the initial page (home) never fires currentChanged —
        # paint the reference's pale-sage Home pill explicitly.
        self.sidebar.set_active("home")
        return None

    # ── M2 navigation: sidebar routing + the stacked-page facade ─────────

    def _on_sidebar_navigate(self, key: str) -> None:
        """Route a sidebar click. The window owns routing (the sidebar only
        emits): Settings/About stay dialogs, pages switch through the
        facade, and every tool key dispatches through the EXISTING
        ``convert_view._on_tool_clicked`` routing (no re-implementation)."""
        if key == "settings":
            self._open_settings()
            return
        if key == "about":
            self._open_about_system()
            return
        if key in self._page_index:
            self.switch_to_page(key)
            return
        self.convert_view._on_tool_clicked(key)

    def switch_to_page(self, key: str) -> bool:
        """The M2 navigation facade — the QStackedWidget successor of the
        old north-tab walk (``convert_view._switch_to_tab`` calls this).
        Returns True when the switch happened; the per-page open hooks
        (queue badge refresh, quarantine auto-reload) fire through
        ``_on_page_changed`` on the stack's ``currentChanged``."""
        idx = self._page_index.get(key)
        if idx is None:
            logger.debug("navigation facade: unknown page key %r", key)
            return False
        self.content_stack.setCurrentIndex(idx)
        return True

    def _on_page_changed(self, idx: int) -> None:
        """The ``QTabWidget.currentChanged`` equivalent (V4.3.0: queue badge
        refresh; V10.28.0: quarantine auto-reload) + the sidebar's active
        destination (spec §5 "restrained green for the active
        destination")."""
        if 0 <= idx < len(self._page_active):
            self.sidebar.set_active(self._page_active[idx])
        widget = self.content_stack.widget(idx)
        if widget is None:
            return
        # Convert / Queue / Output Scanner are wrapped in QScrollArea — unwrap.
        inner = widget.widget() if isinstance(widget, QScrollArea) else widget
        if inner is getattr(self, "queue_view", None):
            self.queue_view.refresh()
        if inner is getattr(self, "quarantine_view", None):
            # Auto-detect the latest book's drops.jsonl if nothing is loaded,
            # then refresh the table.
            try:
                self.quarantine_view._reload()
            except Exception:
                logger.debug("quarantine reload failed", exc_info=True)
            if not getattr(self.quarantine_view, "_drops_path", None):
                try:
                    self.quarantine_view._auto_detect()
                except Exception:
                    logger.debug("quarantine auto-detect failed", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════════
    def _open_hallucination_audit(self) -> None:
        """V13.31.0 (#1): Open the Hallucination Audit dialog."""
        from ui_qt.views.service_dialogs.base_dialog import HallucinationAuditDialog

        dlg = HallucinationAuditDialog(self.controller, self)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()

    def _open_about_system(self) -> None:
        from ui_qt.views.about_system_dialog import AboutSystemDialog

        dlg = AboutSystemDialog(self.controller, self)
        # M2 (decision Q2): the dialog's "Experimental tools…" rows route
        # through the navigation facade; the full LLM lights (decision Q3)
        # start from the latest poll snapshot and then ride the poll loop
        # (see _on_llm_probe_finished — both sinks are fed in parallel).
        dlg.open_page.connect(self.switch_to_page)
        # V0.6.77: the header Merge link retired with the reference top
        # bar — About & System is its new home (an existing status
        # surface), alongside the audio tools that left the sidebar.
        if hasattr(dlg, "open_tool"):
            dlg.open_tool.connect(self._on_about_tool_requested)
        last = getattr(self, "_llm_last_statuses", None)
        if last:
            dlg.apply_llm_statuses(last)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        self._about_dialog = dlg
        dlg.exec()
        self._about_dialog = None

    def _on_about_tool_requested(self, key: str) -> None:
        """Route the About & System 'more tools' rows: the window-owned
        merge flow, else the EXISTING convert_view tool dispatch."""
        if key == "merge":
            self._open_merge_dialog()
            return
        self.convert_view._on_tool_clicked(key)

    def _open_validate(self) -> None:
        dlg = ValidateDialog(self.controller, self)
        self._validate_dialog = dlg
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        # (The post-exec line below touches self, not dlg — safe to delete the dialog.)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        self._validate_dialog = None

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.controller, self)
        self._settings_dialog = dlg
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        # (The post-exec lines below touch self, not dlg — safe to delete the dialog.)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        # after the dialog closes, refresh UI prefs the user may have changed
        # (output-folder override, live-log visibility, engine indicator).
        self.convert_view.apply_ui_preferences()
        self._settings_dialog = None
        # V0.6.85 (Round-5 §5.2): "Trigger checks on … provider/configuration
        # changes" — the Settings dialog is where provider selection now
        # lives (§4.2), so a close re-verifies the (possibly new) backend:
        # local providers re-derive from the cached verdicts (the 5 s poll
        # re-probes liveness on its own cadence); API providers get ONE
        # fresh bounded check. Fail-soft — a broken snapshot never blocks
        # the settings close path.
        try:
            self._refresh_backend_state_from_statuses()
            self._run_api_backend_check()
        except Exception:
            logger.debug("post-settings backend re-check failed", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # V0.6.69 — live local-LLM status lights (the poll loop)
    # ══════════════════════════════════════════════════════════════════════
    def _setup_llm_lights_monitoring(self) -> None:
        """Actively watch for locally-running LLM servers (Ollama,
        llama.cpp, LM Studio) and paint the verdict on the top-bar lights.

        Replaces the pre-V0.6.69 startup path — a background
        ``is_ollama_reachable`` check that popped a modal "Ollama not
        running" QMessageBox at load. The 2026-10-26 field report retired
        that design: a missing local server is an ordinary state to SHOW
        (a gray light), not an error to raise before the user has done
        anything, and the lights must notice a server STARTED mid-session
        (green on the next tick). The loop:

        * every ``LLM_LIGHTS_POLL_INTERVAL_S`` seconds: snapshot the
          endpoints on THIS (main) thread, then hand a SimpleWorker the
          frozen spec — the probe layer never touches settings off-thread
          and never raises;
        * the probes are loopback GETs with the 2 s subsecond budget (a
          dead port answers instantly) and deliberately bypass the
          routing layer's 30 s probe cache — a status light must be FRESH;
        * verdicts are applied on the main thread via the worker's queued
          ``finished`` signal; a probe that EXPLODES is log-debug only
          (the lights keep the last known state — no dialog, ever).
        """
        # V0.6.77: the status strip's connection state is the primary sink
        # (the per-client lights live on in the About & System dialog) —
        # the strip is built unconditionally, so the poll always runs.
        try:
            from PySide6.QtCore import QTimer

            from core.system.local_llm_monitor import (
                LLM_LIGHTS_POLL_INTERVAL_S,
                probe_local_llm_clients,
                snapshot_endpoints,
            )
        except Exception:
            logger.warning("local-LLM lights monitoring unavailable", exc_info=True)
            # Honest degradation: without the probe layer the state cannot
            # be verified — "Not configured"-class neutral gray, never a
            # fake Connected and never a stale 'Ready'.
            self.set_backend_state(
                backend_connection.NOT_CONFIGURED,
                "backend status monitoring is unavailable in this build",
            )
            return

        def _probe():
            # Worker thread — the frozen snapshot + pure probes only.
            return probe_local_llm_clients(self._llm_endpoints_snapshot)

        def _tick() -> None:
            prev = self._llm_probe_worker
            if prev is not None:
                try:
                    if prev.is_running():
                        return  # previous probe still in flight — skip
                except RuntimeError:
                    pass  # the finished worker was auto-deleted — replace
                self._llm_probe_worker = None
            try:
                # Main-thread read of the configured endpoints (DESIGN
                # RULE 2 in core.system.local_llm_monitor).
                self._llm_endpoints_snapshot = snapshot_endpoints(self.controller.settings)
            except Exception:
                logger.debug("llm-lights endpoint snapshot failed", exc_info=True)
                return
            worker = SimpleWorker(_probe)
            self._llm_probe_worker = worker  # Python ref (GC hazard)
            worker.finished.connect(self._on_llm_probe_finished)
            worker.failed.connect(self._on_llm_probe_failed)
            worker.start()

        timer = QTimer(self)
        timer.setInterval(LLM_LIGHTS_POLL_INTERVAL_S * 1000)
        timer.timeout.connect(_tick)
        self._llm_poll_timer = timer
        timer.start()
        _tick()  # first verdict immediately — the splash is barely closed

    @Slot(object)
    def _on_llm_probe_finished(self, statuses) -> None:
        self._llm_probe_worker = None
        # M2 (decision Q3): cache the latest verdict so the About & System
        # dialog can show it IMMEDIATELY on open (its full lights would
        # otherwise wait for the next poll tick).
        self._llm_last_statuses = list(statuses) if statuses else []
        # V0.6.85 (Round-5 §5): the STATUS STRIP's connection state is the
        # poll's primary sink now (the header pill is retired) — derived
        # from the REAL verdicts, fail-soft (an exploded probe keeps the
        # last painted state).
        self._refresh_backend_state_from_statuses()
        # M2 (decision Q3): the About & System dialog's full lights are the
        # second sink of this same poll loop — feed it while the dialog is
        # alive (W-b9 WA_DeleteOnClose: the C++ object may already be gone,
        # so the apply is RuntimeError-guarded like the merge-worker ref).
        dlg = getattr(self, "_about_dialog", None)
        if dlg is not None and statuses:
            try:
                dlg.apply_llm_statuses(statuses)
            except RuntimeError:
                self._about_dialog = None  # deleted wrapper — drop the ref

    @Slot(str)
    def _on_llm_probe_failed(self, error: str) -> None:
        """Fail-soft (the W-b18 lesson, kept): keep the last painted
        verdict, log QUIETLY — a dead probe repeating every few seconds
        must never spam the log the way a warning would."""
        self._llm_probe_worker = None
        logger.debug("local-LLM liveness probe failed: %s", error)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        # V0.6.85 (Round-5 §4.3): the top-bar width adaptation is RETIRED
        # with the pill and the Settings action — the remaining header
        # chrome (divider + window controls) is width-invariant, so the
        # drag region simply absorbs the whole bar at any width.
        # V0.6.83 (Round-3 §3.1): the rail tracks the window width —
        # clamp(180, 0.18*w, 260) logical px. The window owns the rule
        # (Qt layout propagation, no absolute positioning); the rail's
        # compact profile follows its own RAIL_COMPACT_BELOW switch.
        self._update_sidebar_rail()

    def _update_sidebar_rail(self) -> None:
        """V0.6.83 (Round-3 §3.1): the responsive rail — 17–19% of the
        window between 180 and 260 logical px, exactly the correction
        spec's ``clamp(180, 0.18 * window_width, 260)``. Called from
        resizeEvent (and once after the shell build) so every geometry
        change re-flows it through the Qt layout system."""
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None:
            return
        try:
            target = max(180, min(260, round(self.width() * 0.18)))
            sidebar.set_rail_width(target)
        except Exception:
            logger.debug("sidebar rail update failed", exc_info=True)

    def _window_minimum(self) -> tuple[int, int]:
        """V0.6.83 (Round-3 §2.2): the screen-derived window minimum —
        utils.geometry.minimum_window_size (1100x720 where the work area
        supports it, ~96% of it on smaller screens, 760x440 floor). The
        no-screen fallback keeps the V0.6.81 absolute floor."""
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None and app.primaryScreen() is not None:
                avail = app.primaryScreen().availableGeometry()
                return minimum_window_size(avail.width(), avail.height())
        except Exception:
            logger.debug("window minimum probe failed", exc_info=True)
        return (760, 440)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        # V0.6.77: the pill's first verdict paints as soon as the QSS has
        # been polished (harmless no-op if the poll already fed it).
        # V0.6.85 (Round-5 §5): the connection dot re-paints from the
        # CURRENT palette once the strip is polished (the state label is
        # owned by set_backend_state and is already truthful).
        if hasattr(self, "_backend_dot"):
            self._paint_backend_dot()

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        """V0.6.77 frameless chrome: the top bar drags (and double-click
        maximises); the backdrop's edges resize. Everything else — every
        child button, the content, the scroll areas — keeps its events."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        try:
            if obj is getattr(self, "_top_bar", None):
                if event.type() == QEvent.Type.MouseButtonDblClick:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._toggle_maximize()
                        return True
                elif event.type() == QEvent.Type.MouseButtonPress:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._start_system_move()
                        return True
            elif obj is getattr(self, "_backdrop", None) and isinstance(event, QMouseEvent):
                if event.type() == QEvent.Type.MouseButtonPress:
                    if event.button() == Qt.MouseButton.LeftButton:
                        edges = self._edge_at(event.position().toPoint())
                        if int(edges) != 0:
                            self._start_system_resize(edges)
                            return True
                        self._start_system_move()
                        return True
                elif event.type() == QEvent.Type.MouseMove:
                    edges = self._edge_at(event.position().toPoint())
                    self._backdrop.setCursor(self._cursor_for_edges(edges))
        except Exception:
            logger.debug("frameless chrome event filter failed", exc_info=True)
        return super().eventFilter(obj, event)

    # ══════════════════════════════════════════════════════════════════════
    # Drag-and-drop — dropped PDFs go to the Queue view (any tab)
    # ══════════════════════════════════════════════════════════════════════
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    # V18.20.4.1 (P0 / W-b1): PDF only — the Queue view is the
                    # sole drop consumer and it is PDF-focused, matching the
                    # overlay's "Drop a PDF here" promise. (The old set
                    # .pdf/.md/.txt/.docx advertised drops that no live view
                    # could accept.)
                    if Path(url.toLocalFile()).suffix.lower() == ".pdf":
                        event.acceptProposedAction()
                        self._show_drop_overlay(True)
                        return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._show_drop_overlay(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self._show_drop_overlay(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            event.ignore()
            return
        # V18.20.4.1 (P0 / W-b1): the Queue view is the ONLY live drop
        # consumer — route drops from ANY tab to it. The old non-Queue path
        # forwarded to ``convert_view.handle_dropped_file``, which crashed
        # with ``AttributeError: 'NoneType' object has no attribute
        # 'set_path'``: the Convert page's file picker was removed in
        # V11.0.0 (``input_picker = None``), the same V11.0.0-latent class
        # as the V18.20.3.14 ``_on_complete`` crash, and this path was
        # reachable on EVERY drop outside the Queue tab while the drop
        # overlay advertised the feature. The queue accepts PDFs (adds them
        # as queued books); anything else falls through to ignore().
        if self.queue_view.handle_dropped_files(paths):
            # M2 (decision Q2): the dropped books land in the queue AND the
            # Queue page opens — with the page unlisted from primary
            # navigation, the page switch is the drop's visible effect (the
            # old north tab bar at least kept the Queue tab in sight).
            self.switch_to_page("queue")
            event.acceptProposedAction()
            return
        event.ignore()

    def _show_drop_overlay(self, show: bool) -> None:
        """Show/hide a translucent drop-zone overlay with 'Drop a PDF here' text."""
        if not hasattr(self, "_drop_overlay"):
            from PySide6.QtWidgets import QLabel

            p = theme_manager.palette
            self._drop_overlay = QLabel("📄  Drop a PDF here", self)
            self._drop_overlay.setAlignment(Qt.AlignCenter)
            self._drop_overlay.setStyleSheet(
                f"QLabel {{ background-color: {rgba(p.accent, 0.12)};"
                f" color: {p.accent}; border: 3px dashed {p.accent};"
                f" border-radius: 16px; font-size: 16px; font-weight: 600; }}"
            )
            self._drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        if show:
            self._drop_overlay.setGeometry(self.rect())
            self._drop_overlay.raise_()
            self._drop_overlay.show()
        else:
            self._drop_overlay.hide()

    # ══════════════════════════════════════════════════════════════════════
    # Version (read from VERSION file alongside main.py)
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def _app_version() -> str:
        from pathlib import Path

        try:
            vf = Path(__file__).resolve().parent.parent / "VERSION"
            if vf.exists():
                return vf.read_text().strip() or "1.0.0"
        except Exception:
            logger.debug("version read failed", exc_info=True)
        return "1.0.0"

    # ══════════════════════════════════════════════════════════════════════
    # Geometry persistence
    # ══════════════════════════════════════════════════════════════════════
    def _restore_geometry(self) -> None:
        # V0.6.67: the off-screen decision logic lives in the pure
        # utils.geometry.sanitize_restore_plan (unit-testable, Qt-free).
        # Two fixes over V18.20.4.5: (1) the visibility validation now
        # applies to MAXIMIZED restores too — the old code skipped it, so a
        # window saved as "maximized on monitor #2" maximized onto a
        # detached monitor and stayed invisible forever; (2) whenever there
        # is no validated saved position the window is CENTERED on the
        # primary screen instead of trusting Qt's default placement.
        from PySide6.QtWidgets import QApplication

        try:
            data = {}
            if _GEOMETRY_FILE.exists():
                with open(_GEOMETRY_FILE) as f:
                    data = json.load(f)
            # V0.6.83 (Round-3 §2.1): the no-preference size is the 1440×900
            # target wherever the work area comfortably supports it (the
            # correction spec's §2.1 desktop composition), falling back to
            # the V0.6.81 ~92%-of-work-area rule on smaller screens — a
            # fresh install OPENS at a size that composes the hero and the
            # full 3×3 grid with no scrollbar. Pure decision logic stays in
            # utils.geometry (testable).
            default_wh = None
            min_wh = None
            try:
                _app = QApplication.instance()
                if _app is not None and _app.primaryScreen() is not None:
                    _avail = _app.primaryScreen().availableGeometry()
                    default_wh = target_default_size(_avail.width(), _avail.height())
                    min_wh = minimum_window_size(_avail.width(), _avail.height())
            except Exception:
                logger.debug("screen-aware default geometry unavailable", exc_info=True)
            plan = sanitize_restore_plan(
                data,
                _screens_rects(QApplication.instance()),
                default_wh=default_wh,
                min_wh=min_wh,
            )
            if plan["rejected"] and "x" in data:  # T-b5's warning, kept alive
                logger.warning(
                    "restored window geometry (%s,%s %sx%s) is not "
                    "visible on any screen — resetting to default",
                    data.get("x"),
                    data.get("y"),
                    plan["w"],
                    plan["h"],
                )
            self.resize(plan["w"], plan["h"])
            if plan["move_to"] is not None:
                self.move(*plan["move_to"])
            elif plan["center_default"]:
                self._center_on_primary(plan["w"], plan["h"])
            if plan["maximized"]:
                self.showMaximized()
        except Exception:
            self.resize(DEFAULT_W, DEFAULT_H)
            self._center_on_primary(DEFAULT_W, DEFAULT_H)

    def _center_on_primary(self, w: int, h: int) -> None:
        """V0.6.67: deterministic default placement — centered on the
        primary screen's work area (the screen with the taskbar, i.e. the
        one the user is looking at). Best-effort."""
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None or app.primaryScreen() is None:
                return
            primary = app.primaryScreen().availableGeometry()
            self.move(
                primary.x() + max(0, (primary.width() - w) // 2),
                primary.y() + max(0, (primary.height() - h) // 2),
            )
        except Exception:
            logger.debug("default centering failed", exc_info=True)

    def _save_geometry(self) -> None:
        # V0.6.67: never persist minimized coordinates (Windows reports
        # -32000 for a minimized window — restoring them next launch puts
        # the window off-screen), and save the NORMAL geometry when
        # maximized so the restore target is the window's remembered
        # on-screen rect, not the current maximized position.
        try:
            if self.isMinimized():
                return  # keep the previous (good) file
            geo = self.normalGeometry() if self.isMaximized() else self.frameGeometry()
            data = {
                "w": self.width(),
                "h": self.height(),
                "x": geo.x(),
                "y": geo.y(),
                "maximized": self.isMaximized(),
                # V0.6.68: the schema stamp marks this save as POST-migration —
                # a deliberate hand-resize to the old compact default is a real
                # preference from now on (unstamped saves at exactly 608x432
                # were "never resized" and receive the restored 760x540 default;
                # see utils.geometry's LEGACY_COMPACT_W note).
                "v": GEOMETRY_SCHEMA_VERSION,
            }
            with open(_GEOMETRY_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            logger.debug("geometry save failed", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # Close handling — confirm if a conversion is running
    # ══════════════════════════════════════════════════════════════════════
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        # ask before killing a running conversion or queue
        try:
            is_conv = self.controller.is_converting()
            is_queue = hasattr(self, "queue_view") and self.queue_view.is_running()
            if is_conv or is_queue:
                from PySide6.QtWidgets import QMessageBox

                what = "queue" if is_queue else "conversion"
                ret = QMessageBox.question(
                    self,
                    "Processing in progress",
                    f"A {what} is still running. Cancel it and quit?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    event.ignore()
                    return
                if is_queue:
                    self.queue_view.stop()
                else:
                    self.controller.cancel_conversion()
        except Exception:
            logger.debug("close-event cancel failed", exc_info=True)
        # V18.20.4.9 (T-b6): the conversion/queue workers are daemon
        # threads that WRITE output files — quitting without a join used
        # to kill one mid-write (atomic writes mitigate most, but the
        # W-c4 reset path can still be triggered). Stop was requested
        # above; now stop-and-wait + park, the T-b2 retire pattern.
        self._retire_conversion_workers()
        # persist settings + window geometry
        try:
            self.controller.settings.save()
        except Exception:
            logger.debug("settings save on close failed", exc_info=True)
        self._save_geometry()
        # V0.6.69: stop the local-LLM liveness poll loop — no probes after
        # the window is gone (an in-flight worker's queued verdict simply
        # lands on a dead receiver and is discarded by Qt).
        try:
            if getattr(self, "_llm_poll_timer", None) is not None:
                self._llm_poll_timer.stop()
        except Exception:
            pass
        # V18.20.4.12 (W-c12): release cached TTS engines (subprocesses +
        # VRAM) before process teardown. Never-raise: shutdown must not be
        # blocked by a stuck engine (engines have their own quit→wait→kill
        # teardown contract).
        try:
            from core.tts.engine_cache import clear_cache

            clear_cache()
        except Exception:
            pass
        super().closeEvent(event)

    def _retire_conversion_workers(self, wait_ms: int = 2000) -> None:
        """V18.20.4.9 (T-b6): stop-and-wait for the daemon writer threads.

        The queue worker (``queue_view._worker_thread``, daemon=True) and
        the controller's conversion thread
        (``controller.current_conversion_thread``, daemon=True — the SAME
        object while a queue runs) are the two background writers a
        cancel-and-quit used to kill mid-write. The cancel was already
        requested by the confirmation branch above; here we join each
        (best-effort, ``wait_ms``) and park any still-winding-down thread
        on ``self._retired_workers`` so its last reference is never
        dropped while it is alive (the T-b2 retire pattern).
        """
        candidates: list[threading.Thread] = []
        try:
            queue_thread = (
                getattr(self.queue_view, "_worker_thread", None)
                if hasattr(self, "queue_view")
                else None
            )
            if queue_thread is not None and queue_thread.is_alive():
                candidates.append(queue_thread)
            conv_thread = getattr(self.controller, "current_conversion_thread", None)
            if conv_thread is not None and conv_thread.is_alive() and conv_thread not in candidates:
                candidates.append(conv_thread)
        except Exception:
            logger.debug("worker retire scan failed", exc_info=True)
            return
        if not candidates:
            return
        retired: list[threading.Thread] = []
        for t in candidates:
            try:
                t.join(wait_ms)
            except Exception:
                pass  # best-effort — never hang the close on a stuck writer
            if t.is_alive():
                retired.append(t)
        # Park still-running threads (T-b2 retire list). They are daemons,
        # so if the process exits anyway they die like before — but with
        # the join, the common case is a clean finish of the in-flight
        # write instead of a mid-write kill.
        self._retired_workers = retired
        if retired:
            logger.warning(
                "conversion worker(s) still writing after the %sms retire "
                "wait — parked %d thread(s) on close (T-b6)",
                wait_ms,
                len(retired),
            )


# ── Public entry point ──────────────────────────────────────────────────────

# V18.1 (B6): single-instance lock state. Held at module scope so the
# QLocalServer isn't garbage-collected (which would close the socket and
# silently allow a second instance to start).
_INSTANCE_KEY = "elixir_single_instance_v18"
_lock_server = None
_lock_socket = None
# V0.6.65: the primary instance's main window, set by run() before exec().
# The lock server's FOCUS handler raises THIS window when a second launch
# asks for attention — the V18.1 protocol promised that, but the server
# side was never wired: a second double-click wrote FOCUS into a pipe
# nobody read and exited silently. On a machine where the FIRST launch was
# still starting (or hung), every later click did nothing at all — one
# face of the V0.6.64 "installed … doesn't open" field report.
_primary_window = None


def _step(name: str) -> None:
    """V0.6.67: startup.log visibility from the UI layer (the launcher
    guard's step log — best-effort, never raises, no-op in tests that never
    armed the guard)."""
    try:
        from core.system.launcher_guard import startup_step

        startup_step(name)
    except Exception:
        pass


def _screens_rects(app) -> list[tuple[int, int, int, int]]:
    """The CURRENT attached screens as (x, y, w, h) available-geometry
    tuples (taskbar-free work areas). Empty when app/Qt is unavailable —
    every consumer degrades fail-safe (centered default / rescue off)."""
    try:
        if app is None:
            return []
        return [
            (
                scr.availableGeometry().x(),
                scr.availableGeometry().y(),
                scr.availableGeometry().width(),
                scr.availableGeometry().height(),
            )
            for scr in app.screens()
        ]
    except Exception:
        return []


def _window_is_onscreen(window) -> bool:
    """V0.6.67: True when the window's FRAME overlaps any attached screen
    by at least 100×100 px (a window grazing an edge is still effectively
    invisible)."""
    try:
        from PySide6.QtWidgets import QApplication

        frame = window.frameGeometry()
        return restored_geometry_is_visible(
            frame.x(),
            frame.y(),
            frame.width(),
            frame.height(),
            _screens_rects(QApplication.instance()),
            min_overlap_area=100 * 100,
        )
    except Exception:
        return False  # fail-safe: report not-visible so callers act


def _ensure_window_onscreen(window) -> bool:
    """V0.6.67 — THE POST-SHOW GUARANTEE: a window stranded off-screen
    (restored onto a detached monitor, DPI-shifted, whatever the cause) is
    moved to the center of the PRIMARY screen's work area, preserving its
    maximized state.  Returns True when a rescue move was performed.

    Field evidence (2026-10-25 diagnostics): the first launch reached
    exec() with a shown-but-invisible window and every later double-click
    deferred to it via the FOCUS protocol — "the app doesn't open" while a
    healthy invisible window ran.  Whatever put the window off-screen, this
    check runs on the FINAL, post-show position and is therefore
    cause-agnostic.  Best-effort — never raises."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or window is None:
            return False
        frame = window.frameGeometry()
        if restored_geometry_is_visible(
            frame.x(),
            frame.y(),
            frame.width(),
            frame.height(),
            _screens_rects(app),
            min_overlap_area=100 * 100,
        ):
            return False
        logger.warning(
            "main window is off-screen (frame %s, screens %s) — moving it onto the primary screen",
            frame.getRect(),
            _screens_rects(app),
        )
        was_maximized = window.isMaximized()
        if was_maximized:
            window.showNormal()  # un-maximize from the phantom screen first
        primary = app.primaryScreen().availableGeometry()
        window.move(
            primary.center().x() - window.width() // 2,
            primary.center().y() - window.height() // 2,
        )
        if was_maximized:
            window.showMaximized()  # re-maximize on the (real) primary screen
        return True
    except Exception:
        logger.debug("on-screen rescue failed", exc_info=True)
        return False


def _on_lock_connection() -> None:
    """V0.6.65: primary side of the single-instance protocol.

    Answers ``FOCUS`` by raising the main window, then replies — V0.6.67:
    HONESTLY — whether its window is actually on a visible screen AFTER a
    self-heal attempt, so a stranded-off-screen primary can no longer
    swallow every later double-click (the 2026-10-25 field report: the
    primary ACKed, raised an invisible window, and the second instance
    exited into nothing). Best-effort — never raises.
    """
    if _lock_server is None:
        return
    try:
        sock = _lock_server.nextPendingConnection()
        if sock is None:
            return
        try:
            if sock.waitForReadyRead(300):
                if b"FOCUS" in bytes(sock.readAll()) and _primary_window is not None:
                    # V0.6.67: heal FIRST — never raise an invisible window.
                    _ensure_window_onscreen(_primary_window)
                    if _primary_window.isMinimized():
                        _primary_window.showNormal()
                    _primary_window.raise_()
                    _primary_window.activateWindow()
                    sock.write(primary_reply(_window_is_onscreen(_primary_window)))
                else:
                    sock.write(b"OK")  # no window yet (still starting) — legacy reply
            else:
                sock.write(b"OK")
            sock.flush()
            sock.waitForBytesWritten(500)
        finally:
            sock.disconnectFromServer()
    except Exception:
        logger.debug("single-instance FOCUS handling failed", exc_info=True)


def _acquire_single_instance_lock(app) -> bool:
    """Try to become the sole running instance.

    Returns True if this process should continue starting the GUI; exits
    the process when a live primary instance ACKs.

    Protocol (V0.6.67 — the honest-ACK release):

    * connect to the existing server → send ``FOCUS`` → wait up to 2.5 s
      for the reply.  ``OK-VISIBLE`` (or the legacy ``OK``) → the primary
      raised a window that is ON a screen; exit quietly.
      ``OK-INVISIBLE`` → the primary answered but its window is stranded
      off-screen even after its self-heal — exiting here is exactly how
      "the app stopped opening" becomes permanent (the 2026-10-25 field
      report).  Take the name over and keep starting; our own window is
      force-checked on-screen after show().
    * NO reply → the primary is a hung/zombie process whose event loop
      cannot answer — same takeover as before (V0.6.65).
    * No server at all → the normal first launch: listen and continue.

    Implemented with a Qt ``QLocalServer``/``QLocalSocket`` pair so we
    don't add a platform-specific dep (named pipes / fcntl / win32 mutex).
    If PySide6.QtNetwork isn't installed, the lock is skipped with a
    WARNING — better to start the app unguarded than to crash on import.
    """
    import sys

    try:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
    except Exception as _e:  # pragma: no cover — env-specific
        logging.getLogger(__name__).warning(
            "single-instance lock disabled (PySide6.QtNetwork unavailable: %s) "
            "— running multiple instances may corrupt output dirs",
            _e,
        )
        return True

    global _lock_server, _lock_socket
    _lock_socket = QLocalSocket()
    _lock_socket.connectToServer(_INSTANCE_KEY)
    if _lock_socket.waitForConnected(300):
        # A primary exists — ask it to focus, then wait for its reply.
        _lock_socket.write(b"FOCUS")
        _lock_socket.flush()
        _lock_socket.waitForBytesWritten(500)
        reply = b""
        if _lock_socket.waitForReadyRead(2500):
            reply = bytes(_lock_socket.readAll())
        if focus_ack_indicates_visible(reply):
            _step("focus handed to the running instance — exiting")
            sys.exit(0)  # the primary raised a window that is on a screen
        logger.warning(
            "single-instance primary replied %r (no visible window) — "
            "taking over the instance lock; two windows may briefly coexist",
            reply or b"(no reply)",
        )
        _step(f"primary did not present a visible window ({reply!r}) — taking over")
    # No live primary (or a zombie one) — own the name so future launches
    # detect us, and answer FOCUS for them.
    QLocalServer.removeServer(_INSTANCE_KEY)
    _lock_server = QLocalServer()
    _lock_server.newConnection.connect(_on_lock_connection)  # V0.6.65
    if not _lock_server.listen(_INSTANCE_KEY):
        # Name held by something we could not remove — never trap the user
        # out of their app; run unguarded (same degradation as the
        # QtNetwork-missing path above).
        logger.warning("single-instance lock could not listen (%s)", _lock_server.errorString())
    return True


class _StartupSplash(QWidget):
    """V0.6.65: instant liveness feedback while the app builds.

    Shown the moment the single-instance lock is acquired and closed when
    the main window appears, so a slow first launch (cold disk, antivirus
    scanning every bundled DLL as it loads) shows liveness instead of a
    silent desktop — the other face of the V0.6.64 "doesn't open at all"
    field report (the app WAS starting; it just took long enough to look
    dead, and every extra double-click made it worse via the broken
    single-instance path). V0.6.68: the plain "◆ Elixir is starting…"
    text label became the branded splash the 2026-10-26 field report
    asked for — the app icon, a constant "Elixir is loading…" label (no
    technical stage names like "Loading interface"), and an indeterminate
    progress bar. Still deliberately dependency-free (plain widgets,
    fixed palette, no theme imports — the theme is applied only moments
    later) and best-effort — constructed inside run()'s try/except so a
    splash failure can never block startup.
    """

    _TEXT = "Elixir is loading…"

    def __init__(self, app) -> None:
        from PySide6.QtWidgets import QProgressBar

        super().__init__(None)
        self._app = app
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("StartupSplash")
        # M1 de-hardcode: the splash follows the persisted palette instead of
        # fixed slate/amber values (ivory+forest in light, charcoal+sage in dark).
        p = theme_manager.palette
        self.setStyleSheet(
            f"#StartupSplash {{ background: {p.bg_window}; "
            f"border: 1px solid {p.border}; border-radius: 14px; }} "
            f"QLabel {{ background: transparent; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 26)
        lay.setSpacing(14)

        icon_label = QLabel()
        logo = self._icon_pixmap(76)
        if logo is not None:
            icon_label.setPixmap(logo)
            lay.addWidget(icon_label, 0, Qt.AlignHCenter)

        text = QLabel(self._TEXT)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(f"color: {p.text_primary}; font-size: 15px; font-weight: 600;")
        lay.addWidget(text, 0, Qt.AlignHCenter)
        self._text = text  # handle for tests/pinning (the label itself never changes)

        bar = QProgressBar()
        bar.setRange(0, 0)  # indeterminate — animated liveness while the UI builds
        bar.setTextVisible(False)
        bar.setFixedSize(230, 4)
        bar.setStyleSheet(
            f"QProgressBar {{ background: {p.bg_elevated}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background: {p.accent}; border-radius: 2px; }}"
        )
        lay.addWidget(bar, 0, Qt.AlignHCenter)

        self.adjustSize()
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
        self.show()
        app.processEvents()

    def pump(self) -> None:
        """Process events now — keeps the indeterminate bar animating while
        the main window is constructed (no event loop is running yet; the
        V0.6.65 ``message()`` repaint hook survives as this text-less pump
        because the label deliberately never changes)."""
        self._app.processEvents()

    @staticmethod
    def _icon_pixmap(size: int):
        """The app icon (``assets/elixir.png``, ``.ico`` as fallback) scaled
        to ``size``, or None — an omitted icon must never block the splash.
        Best-effort by contract (called inside run()'s try/except anyway)."""
        try:
            from PySide6.QtGui import QPixmap

            from app_paths import bundled_icon_path, resource_path

            for candidate in (resource_path("assets", "elixir.png"), bundled_icon_path()):
                if candidate is None:
                    continue
                pm = QPixmap(str(candidate))
                if not pm.isNull():
                    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception:
            return None
        return None


def run() -> None:
    """Create the QApplication, apply the theme, and show the main window."""
    import sys

    global _primary_window

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    # PACKAGING: give the window/taskbar the bundled app icon (assets/elixir.ico)
    # when present. Best-effort — from source it simply picks up the committed
    # icon; nothing changes when the file is absent.
    try:
        from app_paths import bundled_icon_path

        _icon_path = bundled_icon_path()
        if _icon_path is not None:
            from PySide6.QtGui import QIcon

            app.setWindowIcon(QIcon(str(_icon_path)))
    except Exception:
        logger.debug("window icon not applied", exc_info=True)

    # V18.1 (B6): enforce single-instance — launching twice can corrupt the
    # same output dir / Ollama model state. Must come AFTER QApplication is
    # created because QLocalServer needs a QCoreApplication.
    _acquire_single_instance_lock(app)

    theme_manager.apply(app)

    # V0.6.3: fit every modal's buttons to their full label width. The
    # success modal's "📂 Open File Location" clipped its tail whenever the
    # message text was short (QMessageBox can settle below its own sizeHint
    # when the text label is narrow). Installed here — one call covers every
    # message box the process will ever show.
    install_modal_button_fit(app)

    # V0.6.65: instant "starting…" feedback (see _StartupSplash). Placed
    # AFTER the single-instance lock so a blocked second launch never
    # flashes a splash of its own.
    splash = None
    try:
        splash = _StartupSplash(app)
    except Exception:
        logger.debug("startup splash unavailable", exc_info=True)

    controller = Controller()
    if splash is not None:
        splash.pump()  # V0.6.68: repaint/keep the bar animating — the label
        # stays the branded "Elixir is loading…" (no technical stage names)
    window = ElixirWindow(controller)
    _primary_window = window  # V0.6.65: the lock server raises this on FOCUS
    window.show()
    # V0.6.67 — the post-show guarantee: whatever put the window off-screen
    # (a restored geometry aimed at a detached monitor, a DPI shift, Qt
    # default placement), exec() is only entered with a window that is
    # actually ON a screen — and it comes to the front on launch.
    _ensure_window_onscreen(window)
    window.raise_()
    window.activateWindow()
    _step(
        f"window shown — frame={window.frameGeometry().getRect()} screens={len(_screens_rects(app))}"
    )
    if splash is not None:
        splash.close()
    rc = app.exec()
    # V0.6.67: any future "the app closed itself" report now shows whether
    # the event loop exited cleanly (and with what code) vs the process
    # dying inside it — the boundary used to be invisible in startup.log.
    _step(f"event loop finished (rc={rc})")
    sys.exit(rc)
