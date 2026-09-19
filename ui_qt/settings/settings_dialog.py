"""Two-level settings dialog: vertical head-group rail + per-head-group sub-tabs.

Layout::

    ┌─────────────────┬───────────────────────────────────────────┐
    │  ⚙ Settings     │  [ Sub1 ][ Sub2 ][ Sub3 ]                 │
    │                 │  ───────────────────────────────────────  │
    │  🎚 Presets     │                                           │
    │  🤖 AI          │           (active sub-tab's               │
    │  📖 OCR         │            grouped sections)              │
    │  📦 Output      │                                           │
    │                 │                                           │
    │ (•)Simple( )All │  [Reset]            [Cancel] [Save]       │
    └─────────────────┴───────────────────────────────────────────┘

The 4 head groups are: Presets, AI, OCR, Output.  System is NOT a head
group — it lives in its own "About & System" dialog under the Tools menu.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.icons import icon, pixmap_with_png_fallback
from ui_qt.settings.dependencies_page import DependenciesSection
from ui_qt.settings.podcast_page import (
    PodcastDepthSection,
    PodcastFormatSection,
    PodcastPreviewSection,
    PodcastStyleSection,
)
from ui_qt.settings.presets import PRESETS
from ui_qt.settings.prompts_page import PromptsPage
from ui_qt.settings.sections import (
    AiApiSection,
    AiLocalModelSection,
    AiOutputSelectionSection,
    AiPromptSection,
    AiQualitySection,
    DefaultsSection,
    OcrEngineSection,
    OcrFiguresSection,
    OcrModelSection,
    OutputDestinationSection,
    OutputGenerateSection,
    OutputKeywordsSection,
    OutputPostprocessSection,
    OutputRagSection,
    OutputSegmentationSection,
    OutputStudioSection,
)
from ui_qt.settings.translation_page import (
    TranslationGlossarySection,
    TranslationHarakatSection,
    TranslationLanguagesSection,
    TranslationModelSection,
    TranslationOutputSelectionSection,
    TranslationPreviewSection,
    TranslationValidationSection,
)
from ui_qt.settings.tts_page import (
    TtsCoquiSection,  # V10.37.0
    TtsEnginesSection,
    TtsNormalizationSection,
    TtsPreviewSection,
    TtsSpeedSection,
    TtsVoicesSection,
)
from ui_qt.theme import theme_manager

# ════════════════════════════════════════════════════════════════════════════
# Helpers for building a sub-tab page from a list of sections
# ════════════════════════════════════════════════════════════════════════════


def _make_page(sections: list, two_col: bool = False) -> QWidget:
    """Build a scrollable sub-tab page hosting the given sections."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    if two_col:
        lay = QVBoxLayout(host)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(10)
        # split sections into 2 columns
        mid = (len(sections) + 1) // 2
        cols = QHBoxLayout()
        cols.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(10)
        right = QVBoxLayout()
        right.setSpacing(10)
        for i, s in enumerate(sections):
            (left if i < mid else right).addWidget(s)
        left.addStretch()
        right.addStretch()
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        lay.addLayout(cols)
        lay.addStretch()
    else:
        lay = QVBoxLayout(host)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(10)
        for s in sections:
            lay.addWidget(s)
        lay.addStretch()
    scroll.setWidget(host)
    return scroll


class _HeadGroup(QWidget):
    """A single head-group button in the left rail.

    Emits :pyattr:`clicked` on left-click — the dialog connects this to its
    head-group switcher.  (Using a signal instead of ``self.parent()._head_clicked``
    is robust against intermediate layout widgets.)
    """

    from PySide6.QtCore import Signal

    clicked = Signal(object)  # _HeadGroup

    def __init__(self, icon_name: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeadGroup")
        self.setCursor(Qt.PointingHandCursor)
        self._icon_name = icon_name
        self._label = label
        self._selected = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(18, 18)
        lay.addWidget(self.icon_lbl)
        self.text_lbl = QLabel(label)
        lay.addWidget(self.text_lbl, 1)
        self._refresh()

    def _refresh(self) -> None:
        p = theme_manager.palette
        color = p.accent if self._selected else p.text_primary
        self.icon_lbl.setPixmap(icon(self._icon_name, color, 18).pixmap(18, 18))
        self.text_lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: "
            f"{'600' if self._selected else '500'}; background: transparent;"
        )
        if self._selected:
            self.setStyleSheet(
                f"QWidget#HeadGroup {{ background-color: {p.accent_soft};"
                f" border-left: 3px solid {p.accent};"
                f" border-top-right-radius: 8px; border-bottom-right-radius: 8px; }}"
            )
        else:
            self.setStyleSheet(
                f"QWidget#HeadGroup {{ background: transparent;"
                f" border-left: 3px solid transparent;"
                f" border-top-right-radius: 8px; border-bottom-right-radius: 8px; }}"
                f"QWidget#HeadGroup:hover {{ background-color: {p.bg_elevated}; }}"
            )

    def set_selected(self, sel: bool) -> None:
        self._selected = sel
        self._refresh()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        self._refresh()


# ════════════════════════════════════════════════════════════════════════════
# The Presets head-group page (card grid + per-preset sub-tabs)
# ════════════════════════════════════════════════════════════════════════════


class _PresetsPage(QWidget):
    """Card grid of presets; selecting one reveals its editable sub-tabs."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._sections: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(12)

        # ── card grid (responsive: wraps) ───────────────────────────────
        from PySide6.QtWidgets import QGridLayout

        self._grid = QGridLayout()
        self._grid.setSpacing(8)
        self._cards: dict[str, _PresetCard] = {}
        cols = 3
        for i, (key, preset) in enumerate(PRESETS.items()):
            card = _PresetCard(key, preset["icon"], preset["label"], preset["subtitle"])
            card.selected.connect(self._on_preset_selected)
            self._cards[key] = card
            self._grid.addWidget(card, i // cols, i % cols)
        lay.addLayout(self._grid)

        # ── sub-tab widget for the selected preset ──────────────────────
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setObjectName("PresetSubTabs")
        lay.addWidget(self.sub_tabs, 1)

        # restore selection
        src = controller.get_setting("source_type", "normal_book")
        # map source_type back to a preset key
        key_for_src = src
        if src not in self._cards:
            # infographics/visual_catalogue both set source_type=visual_catalogue;
            # pick by force_ocr flag
            key_for_src = (
                "infographics_slides"
                if controller.get_setting("ocr.force_ocr_all_pages", False)
                and src == "visual_catalogue"
                else "normal_book"
            )
        if key_for_src not in self._cards:
            key_for_src = "normal_book"
        self._on_preset_selected(key_for_src)

    def _on_preset_selected(self, key: str) -> None:
        # exclusive selection
        for k, c in self._cards.items():
            c.set_selected(k == key)
        # apply the preset's settings bundle
        preset = PRESETS.get(key, PRESETS["normal_book"])
        for sk, sv in preset["settings"].items():
            self.controller.update_setting(sk, sv)
        self.controller.update_setting(
            "source_type", preset["settings"].get("source_type", "normal_book")
        )
        # (re)build the sub-tabs for this preset's editable settings
        self.sub_tabs.clear()
        self._sections = []
        # Sub-tab 1: Engine
        engine_page = _make_page([OcrEngineSection(self.controller)])
        self.sub_tabs.addTab(engine_page, "Engine")
        # Sub-tab 2: Segmentation
        seg_page = _make_page(
            [
                OutputSegmentationSection(self.controller),
                OutputKeywordsSection(self.controller),
            ]
        )
        self.sub_tabs.addTab(seg_page, "Segmentation")
        # Sub-tab 3: Filter & output
        filt_page = _make_page(
            [
                AiQualitySection(self.controller),
                AiOutputSelectionSection(self.controller),
            ]
        )
        self.sub_tabs.addTab(filt_page, "Filter & output")
        # collect sections for save/reload
        self._sections = [engine_page, seg_page, filt_page]

    def save(self) -> None:
        # walk every section widget across all sub-tabs and call save()
        for i in range(self.sub_tabs.count()):
            page = self.sub_tabs.widget(i)
            self._save_page(page)

    @staticmethod
    def _save_page(page: QWidget) -> None:
        scroll = page
        host = scroll.widget()
        for child in host.findChildren(QWidget):
            if hasattr(child, "save") and callable(child.save):
                try:
                    child.save()
                except Exception:
                    pass  # best-effort (UI — never crash)

    def reload(self) -> None:
        # re-select the current preset to rebuild sub-tabs from fresh settings
        for k, c in self._cards.items():
            if c._selected:
                self._on_preset_selected(k)
                return
        self._on_preset_selected("normal_book")


class _PresetCard(QFrame):
    """A single selectable preset card in the grid.

    V4.7.25: Redesigned to vertical [icon]/[title]/[meta] layout (mirrors
    TypeCard on the home screen). Supports PNG icons from
    ``assets/icons/{value}.png`` with SVG fallback.
    """

    from PySide6.QtCore import Signal

    selected = Signal(str)

    def __init__(
        self, value: str, icon_name: str, title: str, subtitle: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._icon_name = icon_name
        self._selected = False
        self.setObjectName("PresetCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(110)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(5)

        # ── Icon (centered, 48×48) — PNG with SVG fallback ───────────
        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setFixedSize(48, 48)
        lay.addWidget(self.icon_lbl)

        # ── Title (centered) ──────────────────────────────────────────
        self.title_lbl = QLabel(title)
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet("font-size: 12px; font-weight: 600; background: transparent;")
        lay.addWidget(self.title_lbl)

        # ── Subtitle (centered, wraps) ────────────────────────────────
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setObjectName("Caption")
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setStyleSheet("font-size: 10px; background: transparent;")
        lay.addWidget(self.sub_lbl)

        lay.addStretch()
        self._refresh()

    def _refresh(self) -> None:
        p = theme_manager.palette
        color = p.accent if self._selected else p.text_primary
        # V4.7.25: PNG icon with SVG fallback (assets/icons/{value}.png)
        pm = pixmap_with_png_fallback(
            self._value, color=color, size=48, svg_fallback=self._icon_name
        )
        self.icon_lbl.setPixmap(pm)
        if self._selected:
            self.setStyleSheet(
                f"QFrame#PresetCard {{ background-color: {p.accent_soft};"
                f" border: 1.5px solid {p.accent}; border-radius: 8px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#PresetCard {{ background-color: {p.bg_surface};"
                f" border: 1px solid {p.border}; border-radius: 8px; }}"
                f"QFrame#PresetCard:hover {{ border: 1px solid {p.border_strong};"
                f" background-color: {p.bg_elevated}; }}"
            )

    def set_selected(self, sel: bool) -> None:
        changed = self._selected != sel
        self._selected = sel
        self._refresh()
        # only emit when transitioning to selected — avoids recursion through
        # _on_preset_selected → set_selected(True) → emit → _on_preset_selected …
        if sel and changed:
            self.selected.emit(self._value)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and not self._selected:
            self.set_selected(True)
        super().mousePressEvent(event)


# ════════════════════════════════════════════════════════════════════════════
# The settings dialog
# ════════════════════════════════════════════════════════════════════════════

# Head-group definitions: (icon, label, [sub-tab defs])
# Each sub-tab def = (title, [section classes], two_col?)
# None for subs means "special page" (Presets / Prompts).
_HEAD_GROUPS = [
    ("sliders-horizontal", "Presets", None),  # built specially via _PresetsPage
    (
        "list-checks",
        "Defaults",
        [  # V11.19: default engines/models
            ("All", [DefaultsSection], False),
        ],
    ),
    (
        "cpu",
        "AI",
        [
            ("Local Model", [AiLocalModelSection], False),
            ("API", [AiApiSection], False),
            ("Prompt", [AiPromptSection], False),
        ],
    ),
    ("message-square", "Prompts", None),  # built specially via PromptsPage (V3.1.3)
    (
        "scan",
        "OCR",
        [
            ("Engine", [OcrEngineSection], False),
            ("Models", [OcrModelSection], False),
            ("Figures", [OcrFiguresSection], False),
        ],
    ),
    (
        "file-output",
        "Output",
        [
            ("Output Types", [AiOutputSelectionSection], False),
            ("Quality", [AiQualitySection], False),
            ("Destination", [OutputDestinationSection], False),
            ("Generate", [OutputGenerateSection], False),
            ("Segmentation", [OutputSegmentationSection, OutputKeywordsSection], True),
            ("Post-process", [OutputPostprocessSection], False),
            ("RAG", [OutputRagSection], False),
            ("Output Studio", [OutputStudioSection], False),
        ],
    ),
    (
        "globe",
        "Translation",
        [
            ("Model", [TranslationModelSection], False),
            ("Languages", [TranslationLanguagesSection], False),
            ("Validation", [TranslationValidationSection, TranslationHarakatSection], True),
            ("Outputs", [TranslationOutputSelectionSection, TranslationGlossarySection], False),
            ("Preview", [TranslationPreviewSection], False),
        ],
    ),
    (
        "mic",
        "TTS",
        [
            ("Voices", [TtsVoicesSection], False),
            ("Engines", [TtsEnginesSection], False),
            ("Coqui XTTS v2", [TtsCoquiSection], False),  # V10.37.0
            ("Speed", [TtsSpeedSection], False),
            ("Normalization", [TtsNormalizationSection], False),
            ("Preview", [TtsPreviewSection], False),
        ],
    ),
    (
        "play",
        "Podcast",
        [
            ("Format", [PodcastFormatSection], False),
            ("Depth & Length", [PodcastDepthSection], False),
            ("Style", [PodcastStyleSection], False),
            ("Preview", [PodcastPreviewSection], False),
        ],
    ),
    (
        "check",
        "Dependencies",
        [
            ("All", [DependenciesSection], False),
        ],
    ),
]


class SettingsDialog(QDialog):
    """The application settings dialog (2-level: head groups → sub-tabs)."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Settings")
        self.setMinimumSize(780, 540)  # V7.4.0: was 920x660 — compact
        self.resize(860, 600)  # V7.4.0: was 1000x700

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ──────────────────────────────────────────────────────
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 12, 18, 8)  # V7.4.0: was (28,18,24,12) — compact
        hl.setSpacing(8)
        title = QLabel("Settings")
        title.setObjectName("H1")
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header)

        # ── body: head-group rail (left) + sub-tab stack (right) ────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # left rail
        rail = QWidget()
        rail.setObjectName("Rail")
        rail.setFixedWidth(140)
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(12, 4, 4, 12)
        rail_lay.setSpacing(4)
        self._head_groups: list[_HeadGroup] = []
        for icon_name, label, _subs in _HEAD_GROUPS:
            hg = _HeadGroup(icon_name, label)
            hg.clicked.connect(self._head_clicked)
            self._head_groups.append(hg)
            rail_lay.addWidget(hg)
        # V10.18.0 (E5): Settings search bar — filters head-group labels
        from PySide6.QtWidgets import QLineEdit

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_rail)
        rail_lay.insertWidget(0, self.search_edit)

        rail_lay.addStretch()
        body.addWidget(rail)

        # right: sub-tab stack (one QTabWidget per head group)
        self._pages: list[QWidget] = []
        self._sub_tabs: list[QTabWidget] = []
        self.stack = QStackedWidget()
        for _idx, (_ic, lbl, subs) in enumerate(_HEAD_GROUPS):
            if subs is None and lbl == "Presets":
                # Presets head group — special page
                page = _PresetsPage(controller)
                self._pages.append(page)
                self._sub_tabs.append(None)  # type: ignore[arg-type]
            elif subs is None and lbl == "Prompts":
                # Prompts head group — special page (V3.1.3)
                page = PromptsPage(controller)
                self._pages.append(page)
                self._sub_tabs.append(None)  # type: ignore[arg-type]
            else:
                sub = QTabWidget()
                for tab_title, section_classes, two_col in subs:
                    sections = [cls(controller) for cls in section_classes]
                    sub.addTab(_make_page(sections, two_col), tab_title)
                self._sub_tabs.append(sub)
                self._pages.append(sub)
            self.stack.addWidget(self._pages[-1])
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        # ── footer ──────────────────────────────────────────────────────
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 10, 16, 12)
        fl.setSpacing(12)
        self.reset_btn = QPushButton("  Reset to defaults")
        self.reset_btn.clicked.connect(self._on_reset)
        fl.addWidget(self.reset_btn)
        fl.addStretch()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Save).setObjectName("Primary")
        self.button_box.button(QDialogButtonBox.Cancel).setObjectName("Secondary")
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        fl.addWidget(self.button_box)
        root.addWidget(footer)

        # select the first head group
        self._head_group_idx = -1
        self._select_head_group(0)

    # ── head-group selection ────────────────────────────────────────────
    def _head_clicked(self, hg: _HeadGroup) -> None:
        idx = self._head_groups.index(hg)
        self._select_head_group(idx)

    def _select_head_group(self, idx: int) -> None:
        if idx == self._head_group_idx:
            return
        self._head_group_idx = idx
        for i, hg in enumerate(self._head_groups):
            hg.set_selected(i == idx)
        self.stack.setCurrentIndex(idx)

    # ── save / reset ────────────────────────────────────────────────────
    def _on_save(self) -> None:
        # save every section in every page
        _section_failures = 0
        for page in self._pages:
            if isinstance(page, (_PresetsPage, PromptsPage)):
                if not self._try_save(page):
                    _section_failures += 1
            elif isinstance(page, QTabWidget):
                for i in range(page.count()):
                    if not self._save_page(page.widget(i)):
                        _section_failures += 1
        # V18.20.4.3 (P2 / W-b6): settings-save failures are no longer
        # swallowed. ``Settings.save()`` returns success (never raises);
        # a failed disk write (disk-full / permission) now WARNS and
        # keeps the dialog OPEN — the user can free space / fix the
        # permission and click Save again instead of losing API keys +
        # model picks to a silent no-op. In-memory values are already
        # updated (fail-soft), so a retry just re-attempts the write.
        try:
            _saved = self.controller.settings.save()
        except Exception:
            _saved = False  # belt-and-braces: never crash the dialog
        if not _saved:
            QMessageBox.warning(
                self,
                "Settings were NOT saved",
                "The settings could not be written to disk (disk full or "
                "permission error).\n\n"
                "Your changes are active for this session only and will be "
                "lost on exit.\n\n"
                "Free disk space or fix the permissions, then click Save "
                "again.",
            )
            return  # keep the dialog open for a retry
        if _section_failures:
            # Per-section in-memory writes failed (rare — e.g. a widget
            # raising in its save()). Warn, but the disk file is saved.
            QMessageBox.warning(
                self,
                "Some sections were not applied",
                f"{_section_failures} settings section(s) reported an error "
                "while applying their values. The remaining sections were "
                "saved successfully.",
            )
        self.accept()

    @staticmethod
    def _try_save(page: QWidget) -> bool:
        try:
            page.save()
            return True
        except Exception:
            return False  # best-effort (UI — never crash)

    @staticmethod
    def _save_page(page: QWidget) -> bool:
        # page is a QScrollArea; its widget is the host
        host = page.widget() if hasattr(page, "widget") else page
        ok = True
        for child in host.findChildren(QWidget):
            if hasattr(child, "save") and callable(child.save):
                try:
                    child.save()
                except Exception:
                    ok = False  # best-effort (UI — never crash)
        return ok

    def _on_reset(self) -> None:
        ret = QMessageBox.question(
            self,
            "Reset settings",
            "Reset all settings to their defaults? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            self.controller.settings.reset_to_defaults()
        except Exception:
            pass
        # reload every section in every page
        for page in self._pages:
            if isinstance(page, (_PresetsPage, PromptsPage)):
                page.reload()
            elif isinstance(page, QTabWidget):
                for i in range(page.count()):
                    self._reload_page(page.widget(i))

    @staticmethod
    def _reload_page(page: QWidget) -> None:
        host = page.widget() if hasattr(page, "widget") else page
        for child in host.findChildren(QWidget):
            if hasattr(child, "reload") and callable(child.reload):
                try:
                    child.reload()
                except Exception:
                    pass

    # ── theme ───────────────────────────────────────────────────────────
    def refresh_theme(self) -> None:
        for hg in self._head_groups:
            hg.refresh_theme()

    def _filter_rail(self, text: str) -> None:
        """V10.18.0 (E5): Filter head-group rail buttons by search text."""
        text_lower = text.lower().strip()
        for btn in self._rail_buttons:
            if not text_lower or text_lower in btn.text().lower():
                btn.setVisible(True)
            else:
                btn.setVisible(False)
