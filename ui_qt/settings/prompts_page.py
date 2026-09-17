"""Prompt Bank Head Group — a top-level settings head group with two tabs:

  1. **Active Prompts** — shows every place in the app where a prompt
     influences output (Summarisation, Simplified Keypoints, etc.).
     Each context is a card with a dropdown to switch the active prompt.

  2. **Saved Prompts** — a card grid of all saved prompt templates.
     Each card shows the name, a preview, and Edit / Duplicate / Delete
     buttons. Clicking a card opens the full :class:`PromptEditorDialog`.

This gives pro users manual control over every prompt that influences
the conversion pipeline.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.summarisation.prompt_manager import PromptManager
from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager

# ════════════════════════════════════════════════════════════════════════════
# Prompt contexts — every place in the app where a prompt is used
# ════════════════════════════════════════════════════════════════════════════

# Each context: (key, icon, display_name, description, settings_key)
# settings_key is where the active prompt name is stored in settings.json
PROMPT_CONTEXTS = [
    (
        "summarisation",
        "book",
        "Summarisation",
        "Controls the executive summary, bullet points, and thorough summary for each chapter.",
        "summarisation.prompt",
    ),
    (
        "simplified_keypoints",
        "sparkles",
        "Simplified Keypoints",
        "Controls how technical keypoints are translated into plain, everyday language.",
        "summarisation.simplified_prompt",
    ),
]

# Built-in prompts that cannot be deleted
_BUILTIN_PROMPTS = frozenset({"default", "academic", "technical", "creative"})


# ════════════════════════════════════════════════════════════════════════════
# Prompt Editor Dialog — view / edit a full prompt template
# ════════════════════════════════════════════════════════════════════════════

class PromptEditorDialog(QDialog):
    """Full-screen editor for a single prompt template.

    Shows the prompt name, a variables hint, a large text editor, and
    Save / Cancel buttons. Variables ``{{heading}}``, ``{{text}}``,
    ``{{language}}`` are highlighted in the hint.
    """

    def __init__(self, prompt_name: str, content: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Prompt: {prompt_name}")
        self.setMinimumSize(620, 460)  # V7.4.0: was 720x560
        self.resize(700, 520)           # V7.4.0: was 800x640
        self._name = prompt_name
        self._original_content = content

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── Header ─────────────────────────────────────────────────────
        from PySide6.QtGui import QFont
        header = QHBoxLayout()
        header.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon("file-text", theme_manager.palette.accent, 22).pixmap(22, 22))
        header.addWidget(icon_lbl)
        title = QLabel(prompt_name)
        title.setFont(QFont("", 14, QFont.Bold))
        title.setStyleSheet(f"color: {theme_manager.palette.text_primary};")
        header.addWidget(title)
        header.addStretch()
        builtin_badge = QLabel("BUILT-IN") if prompt_name in _BUILTIN_PROMPTS else QLabel("CUSTOM")
        builtin_badge.setObjectName("Caption")
        builtin_badge.setStyleSheet(
            f"padding: 3px 10px; border-radius: 10px; font-size: 10px; font-weight: 600;"
            f" background: {theme_manager.palette.accent_soft}; color: {theme_manager.palette.accent};"
        )
        header.addWidget(builtin_badge)
        root.addLayout(header)

        # ── Variables hint ─────────────────────────────────────────────
        hint = QLabel(
            "Variables: <code style='background:rgba(168,198,229,0.18);padding:1px 5px;border-radius:3px;'>{{heading}}</code> "
            "<code style='background:rgba(168,198,229,0.18);padding:1px 5px;border-radius:3px;'>{{text}}</code> "
            "<code style='background:rgba(168,198,229,0.18);padding:1px 5px;border-radius:3px;'>{{keypoints}}</code> "
            "<code style='background:rgba(168,198,229,0.18);padding:1px 5px;border-radius:3px;'>{{language}}</code> "
            "<span style='color: #888; font-size: 11px;'>&nbsp; — chapter heading, content, keypoints list, language instruction</span>"
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # ── Editor ─────────────────────────────────────────────────────
        self.editor = QTextEdit()
        self.editor.setPlainText(content)
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setStyleSheet(
            f"QTextEdit {{ background-color: {theme_manager.palette.bg_surface};"
            f" color: {theme_manager.palette.text_primary};"
            f" border: 1px solid {theme_manager.palette.border};"
            f" border-radius: 8px; padding: 12px; font-family: Consolas, 'Courier New', monospace; }}"
        )
        root.addWidget(self.editor, 1)

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("  Save")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _on_save(self) -> None:
        content = self.editor.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Empty prompt", "Prompt content cannot be empty.")
            return
        self._content = content
        self.accept()

    def get_content(self) -> str:
        return getattr(self, "_content", self._original_content)


# ════════════════════════════════════════════════════════════════════════════
# Saved Prompt Card — a single card in the Saved Prompts grid
# ════════════════════════════════════════════════════════════════════════════

class _SavedPromptCard(QFrame):
    """A card showing a single saved prompt with preview + action buttons."""

    edit_requested = Signal(str)      # prompt name
    duplicate_requested = Signal(str)  # prompt name
    delete_requested = Signal(str)     # prompt name
    activate_requested = Signal(str)   # prompt name

    def __init__(
        self,
        name: str,
        content: str,
        is_active: bool,
        active_context: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._content = content
        self._is_builtin = name in _BUILTIN_PROMPTS
        self.setObjectName("SavedPromptCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(180)
        self.setMaximumHeight(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # ── Header: icon + name + active badge ─────────────────────────
        head = QHBoxLayout()
        head.setSpacing(8)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(18, 18)
        head.addWidget(self.icon_lbl)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 600; background: transparent;")
        head.addWidget(name_lbl)
        head.addStretch()

        # Active badge
        if is_active:
            badge = QLabel("● ACTIVE")
            badge.setStyleSheet(
                f"font-size: 10px; font-weight: 700; color: {theme_manager.palette.accent};"
                f" background: {theme_manager.palette.accent_soft}; padding: 2px 8px;"
                f" border-radius: 8px; letter-spacing: 0.5px;"
            )
            head.addWidget(badge)

        # Built-in badge
        if self._is_builtin:
            bi_badge = QLabel("BUILT-IN")
            bi_badge.setStyleSheet(
                f"font-size: 10px; font-weight: 600; color: {theme_manager.palette.text_secondary};"
                f" background: {theme_manager.palette.bg_elevated}; padding: 2px 8px;"
                f" border-radius: 8px; letter-spacing: 0.5px;"
            )
            head.addWidget(bi_badge)

        lay.addLayout(head)

        # ── Preview (first 4 lines, truncated) ─────────────────────────
        preview_lines = content.strip().splitlines()[:4]
        preview = "\n".join(preview_lines)
        if len(preview) > 200:
            preview = preview[:197] + "…"
        self.preview_lbl = QLabel(preview)
        self.preview_lbl.setObjectName("Caption")
        self.preview_lbl.setWordWrap(True)
        self.preview_lbl.setStyleSheet(
            f"font-size: 11px; color: {theme_manager.palette.text_secondary};"
            f" background: transparent; font-family: Consolas, monospace;"
        )
        lay.addWidget(self.preview_lbl, 1)

        # ── Action buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self.edit_btn = self._make_btn("pencil", "Edit", self._on_edit)
        btn_row.addWidget(self.edit_btn)

        self.dup_btn = self._make_btn("copy", "Duplicate", self._on_duplicate)
        btn_row.addWidget(self.dup_btn)

        if not self._is_builtin:
            self.del_btn = self._make_btn("trash", "Delete", self._on_delete)
            btn_row.addWidget(self.del_btn)

        btn_row.addStretch()

        self.activate_btn = QPushButton("  Set Active")
        self.activate_btn.setObjectName("Compact")
        self.activate_btn.setCursor(Qt.PointingHandCursor)
        self.activate_btn.setStyleSheet(self._compact_btn_style())
        self.activate_btn.clicked.connect(lambda: self.activate_requested.emit(self._name))
        if is_active:
            self.activate_btn.setEnabled(False)
            self.activate_btn.setText("✓ Active")
        btn_row.addWidget(self.activate_btn)

        lay.addLayout(btn_row)
        self._refresh()

    def _make_btn(self, icon_name: str, tooltip: str, handler) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(icon(icon_name, theme_manager.palette.text_secondary, 14))
        btn.setFixedSize(30, 28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(self._icon_btn_style())
        btn.clicked.connect(handler)
        return btn

    def _icon_btn_style(self) -> str:
        p = theme_manager.palette
        return (
            f"QPushButton {{ background: {p.bg_elevated}; border: 1px solid {p.border};"
            f" border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {p.accent_soft}; border-color: {p.accent}; }}"
        )

    def _compact_btn_style(self) -> str:
        p = theme_manager.palette
        return (
            f"QPushButton {{ background: {p.bg_elevated}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
            f" color: {p.text_primary}; }}"
            f"QPushButton:hover {{ background: {p.accent_soft}; border-color: {p.accent}; }}"
            f"QPushButton:disabled {{ color: {p.accent}; border-color: {p.accent};"
            f" background: {p.accent_soft}; }}"
        )

    def _refresh(self) -> None:
        p = theme_manager.palette
        color = p.accent if self._is_builtin else p.text_primary
        self.icon_lbl.setPixmap(icon("file-text", color, 18).pixmap(18, 18))
        self.setStyleSheet(
            f"QFrame#SavedPromptCard {{ background-color: {p.bg_surface};"
            f" border: 1px solid {p.border}; border-radius: 10px; }}"
            f"QFrame#SavedPromptCard:hover {{ border: 1px solid {p.border_strong};"
            f" background-color: {p.bg_elevated}; }}"
        )

    def refresh_theme(self) -> None:
        self._refresh()

    # ── Handlers ───────────────────────────────────────────────────────
    def _on_edit(self) -> None:
        self.edit_requested.emit(self._name)

    def _on_duplicate(self) -> None:
        self.duplicate_requested.emit(self._name)

    def _on_delete(self) -> None:
        self.delete_requested.emit(self._name)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.edit_requested.emit(self._name)
        super().mouseDoubleClickEvent(event)


# ════════════════════════════════════════════════════════════════════════════
# Active Prompts Tab — shows which prompt is active per context
# ════════════════════════════════════════════════════════════════════════════

class _ActivePromptsTab(QWidget):
    """Tab showing each prompt context as a card with a prompt switcher."""

    prompts_changed = Signal()

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._pm = PromptManager()
        self._combos: dict[str, QComboBox] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(12)

        # ── Intro banner ───────────────────────────────────────────────
        intro = QLabel(
            "Each card below represents a place in the app where a prompt influences "
            "the output. Use the dropdown to switch which saved prompt is active for "
            "that context."
        )
        intro.setObjectName("Caption")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"font-size: 12px; color: {theme_manager.palette.text_secondary};")
        lay.addWidget(intro)

        # ── Context cards ──────────────────────────────────────────────
        for key, icon_name, display_name, description, settings_key in PROMPT_CONTEXTS:
            card = self._build_context_card(
                key, icon_name, display_name, description, settings_key
            )
            lay.addWidget(card)

        lay.addStretch()

        # ── Hint ───────────────────────────────────────────────────────
        hint = QLabel(
            "💡 Tip: Create custom prompts in the 'Saved Prompts' tab, then switch to "
            "them here. Changes apply on the next conversion."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"font-size: 11px; color: {theme_manager.palette.text_secondary};"
            f" background: {theme_manager.palette.accent_soft};"
            f" padding: 10px 14px; border-radius: 8px;"
        )
        lay.addWidget(hint)

        scroll.setWidget(host)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_context_card(
        self, key: str, icon_name: str, display_name: str, description: str, settings_key: str
    ) -> QFrame:
        """Build a single context card with icon, description, and prompt switcher."""
        p = theme_manager.palette
        card = QFrame()
        card.setObjectName("ContextCard")
        card.setStyleSheet(
            f"QFrame#ContextCard {{ background-color: {p.bg_surface};"
            f" border: 1px solid {p.border}; border-radius: 10px; }}"
        )

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        # Header: icon + title
        head = QHBoxLayout()
        head.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon(icon_name, p.accent, 22).pixmap(22, 22))
        head.addWidget(icon_lbl)
        title = QLabel(display_name)
        title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {p.text_primary}; background: transparent;")
        head.addWidget(title)
        head.addStretch()
        lay.addLayout(head)

        # Description
        desc = QLabel(description)
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 12px; color: {p.text_secondary}; background: transparent;")
        lay.addWidget(desc)

        # Prompt switcher row
        switch_row = QHBoxLayout()
        switch_row.setSpacing(10)
        label = QLabel("Active prompt:")
        label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {p.text_primary}; background: transparent;")
        switch_row.addWidget(label)

        combo = QComboBox()
        prompts = self._pm.list_prompts()
        combo.addItems(prompts)
        saved = self.controller.get_setting(settings_key, "default")
        if saved not in prompts:
            saved = "default" if "default" in prompts else (prompts[0] if prompts else "")
        idx = combo.findText(saved)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(lambda name, sk=settings_key: self._on_prompt_changed(sk, name))
        combo.setMinimumWidth(240)
        switch_row.addWidget(combo)
        switch_row.addStretch()

        # "Edit current" button
        edit_btn = QPushButton("  Edit")
        edit_btn.setObjectName("Compact")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setStyleSheet(
            f"QPushButton {{ background: {p.bg_elevated}; border: 1px solid {p.border};"
            f" border-radius: 6px; padding: 5px 14px; font-size: 11px; font-weight: 600;"
            f" color: {p.text_primary}; }}"
            f"QPushButton:hover {{ background: {p.accent_soft}; border-color: {p.accent}; }}"
        )
        edit_btn.clicked.connect(lambda _, c=combo: self._edit_current(c.currentText()))
        switch_row.addWidget(edit_btn)

        lay.addLayout(switch_row)
        self._combos[key] = combo
        return card

    def _on_prompt_changed(self, settings_key: str, prompt_name: str) -> None:
        self.controller.update_setting(settings_key, prompt_name)
        self.prompts_changed.emit()

    def _edit_current(self, prompt_name: str) -> None:
        """Open the editor for the currently-selected prompt in a context.

        V3.1.4 fix: If the named prompt can't be loaded (e.g. path issue or
        empty selection), fall back to 'default' and show an info message.
        Never open an empty editor — always show SOMETHING.
        """
        if not prompt_name:
            QMessageBox.warning(
                self, "No prompt selected",
                "Please select a prompt from the dropdown first.",
            )
            return

        content = self._pm.load_prompt(prompt_name)
        if not content:
            # Fallback: try 'default' — the built-in prompt should always exist
            content = self._pm.load_prompt("default")
            if content:
                QMessageBox.information(
                    self, "Prompt not found",
                    f"Prompt '{prompt_name}' could not be loaded from disk.\n"
                    f"Showing the built-in 'default' prompt instead.",
                )
                prompt_name = "default"
            else:
                # Last resort: show a minimal hardcoded template so the editor
                # is never empty. This should never happen, but it's a safety net.
                content = (
                    "You are an expert book summariser. {{language}}\n\n"
                    'You are summarising a chapter titled: "{{heading}}".\n\n'
                    "Extract CONCEPTS, PRINCIPLES, FRAMEWORKS, and ACTIONABLE INSIGHTS.\n\n"
                    "Chapter content:\n{{text}}\n"
                )
                QMessageBox.warning(
                    self, "Prompt files not found",
                    "Could not load any prompt files from disk.\n"
                    "Showing a minimal fallback template.\n"
                    "Check that the 'prompts/' folder exists in the app directory.",
                )

        dlg = PromptEditorDialog(prompt_name, content, self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_content = dlg.get_content()
            self._pm.save_prompt(prompt_name, new_content)

    def reload(self) -> None:
        """Re-read settings and refresh combo boxes."""
        for key, _icon, _name, _desc, settings_key in PROMPT_CONTEXTS:
            combo = self._combos.get(key)
            if not combo:
                continue
            prompts = self._pm.list_prompts()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(prompts)
            saved = self.controller.get_setting(settings_key, "default")
            if saved not in prompts:
                saved = "default" if "default" in prompts else (prompts[0] if prompts else "")
            idx = combo.findText(saved)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)


# ════════════════════════════════════════════════════════════════════════════
# Saved Prompts Tab — card grid of all saved prompts
# ════════════════════════════════════════════════════════════════════════════

class _SavedPromptsTab(QWidget):
    """Tab showing all saved prompts as a card grid."""

    prompts_changed = Signal()

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._pm = PromptManager()
        self._cards: list[_SavedPromptCard] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        host = QWidget()
        self._host_lay = QVBoxLayout(host)
        self._host_lay.setContentsMargins(8, 10, 8, 10)
        self._host_lay.setSpacing(12)

        # ── Toolbar ────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        title = QLabel("Saved Prompts")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {theme_manager.palette.text_primary};"
        )
        toolbar.addWidget(title)

        count_lbl = QLabel()
        count_lbl.setObjectName("Caption")
        count_lbl.setStyleSheet(f"color: {theme_manager.palette.text_secondary}; font-size: 11px;")
        toolbar.addWidget(count_lbl)
        self._count_lbl = count_lbl

        toolbar.addStretch()

        # New prompt button
        new_btn = QPushButton("  New Prompt")
        new_btn.setObjectName("Primary")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._new_prompt)
        toolbar.addWidget(new_btn)
        self._host_lay.addLayout(toolbar)

        # ── Card grid ──────────────────────────────────────────────────
        self._grid_container = QWidget()
        self._grid_lay = QGridLayout(self._grid_container)
        self._grid_lay.setSpacing(12)
        self._host_lay.addWidget(self._grid_container)

        self._host_lay.addStretch()

        scroll.setWidget(host)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._rebuild_grid()

    def _get_active_prompts(self) -> set:
        """Return the set of prompt names that are active in any context."""
        active = set()
        for _key, _icon, _name, _desc, settings_key in PROMPT_CONTEXTS:
            name = self.controller.get_setting(settings_key, "default")
            active.add(name)
        return active

    def _rebuild_grid(self) -> None:
        """Rebuild the card grid from the PromptManager."""
        # Clear existing cards
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        prompts = self._pm.list_prompts()
        active_set = self._get_active_prompts()
        self._count_lbl.setText(f"({len(prompts)} prompts, {len(active_set)} active)")

        cols = 3
        for i, name in enumerate(prompts):
            content = self._pm.load_prompt(name) or ""
            is_active = name in active_set
            card = _SavedPromptCard(name, content, is_active)
            card.edit_requested.connect(self._edit_prompt)
            card.duplicate_requested.connect(self._duplicate_prompt)
            card.delete_requested.connect(self._delete_prompt)
            card.activate_requested.connect(self._activate_prompt)
            self._cards.append(card)
            self._grid_lay.addWidget(card, i // cols, i % cols)

    def _edit_prompt(self, name: str) -> None:
        content = self._pm.load_prompt(name)
        if not content:
            # Fallback: try 'default'
            content = self._pm.load_prompt("default") or ""
            if content:
                QMessageBox.information(
                    self, "Prompt not found",
                    f"Prompt '{name}' could not be loaded. Showing 'default' instead.",
                )
                name = "default"
            else:
                QMessageBox.warning(
                    self, "Prompt not found",
                    f"Could not load prompt '{name}' or 'default' from disk.",
                )
                return
        dlg = PromptEditorDialog(name, content, self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_content = dlg.get_content()
            self._pm.save_prompt(name, new_content)
            self._rebuild_grid()
            self.prompts_changed.emit()

    def _duplicate_prompt(self, name: str) -> None:
        """Duplicate a prompt with a new name."""
        content = self._pm.load_prompt(name) or ""
        suggested = f"{name}_copy"
        new_name, ok = QInputDialog.getText(
            self, "Duplicate Prompt", "New prompt name:", text=suggested
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        existing = set(self._pm.list_prompts())
        if new_name in existing:
            QMessageBox.warning(self, "Name exists", f"A prompt named '{new_name}' already exists.")
            return
        self._pm.save_prompt(new_name, content)
        self._rebuild_grid()
        self.prompts_changed.emit()

    def _delete_prompt(self, name: str) -> None:
        if name in _BUILTIN_PROMPTS:
            QMessageBox.warning(self, "Cannot delete", f"'{name}' is a built-in preset and cannot be deleted.")
            return
        ret = QMessageBox.question(
            self, "Delete prompt",
            f"Delete prompt '{name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self._pm.delete_prompt(name)
        # If this was an active prompt, switch to default
        for _key, _icon, _name, _desc, settings_key in PROMPT_CONTEXTS:
            if self.controller.get_setting(settings_key, "default") == name:
                self.controller.update_setting(settings_key, "default")
        self._rebuild_grid()
        self.prompts_changed.emit()

    def _activate_prompt(self, name: str) -> None:
        """Set this prompt as active for the primary summarisation context."""
        self.controller.update_setting("summarisation.prompt", name)
        self._rebuild_grid()
        self.prompts_changed.emit()
        QMessageBox.information(
            self, "Prompt activated",
            f"'{name}' is now the active summarisation prompt.\n"
            f"It will be used on the next conversion."
        )

    def _new_prompt(self) -> None:
        """Create a new prompt from scratch (starting from default template)."""
        name, ok = QInputDialog.getText(self, "New Prompt", "Prompt name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        existing = set(self._pm.list_prompts())
        if name in existing:
            QMessageBox.warning(self, "Name exists", f"A prompt named '{name}' already exists.")
            return
        default_content = self._pm.load_prompt("default") or ""
        dlg = PromptEditorDialog(name, default_content, self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            content = dlg.get_content()
            self._pm.save_prompt(name, content)
            self._rebuild_grid()
            self.prompts_changed.emit()

    def reload(self) -> None:
        self._rebuild_grid()


# ════════════════════════════════════════════════════════════════════════════
# Prompts Page — the Head Group page with two tabs
# ════════════════════════════════════════════════════════════════════════════

class PromptsPage(QWidget):
    """The Prompt Bank head-group page: Active Prompts + Saved Prompts tabs."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(10)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setObjectName("PromptSubTabs")

        self._active_tab = _ActivePromptsTab(controller)
        self._saved_tab = _SavedPromptsTab(controller)

        # When saved prompts change, refresh the active tab's combo boxes
        self._saved_tab.prompts_changed.connect(self._active_tab.reload)
        self._active_tab.prompts_changed.connect(self._saved_tab._rebuild_grid)

        self.sub_tabs.addTab(self._active_tab, "Active Prompts")
        self.sub_tabs.addTab(self._saved_tab, "Saved Prompts")

        lay.addWidget(self.sub_tabs)

    def save(self) -> None:
        """Called when settings dialog saves. Prompt changes are already
        persisted to settings.json + ~/.elixir/prompts/ in real-time,
        so nothing extra needed here."""
        pass

    def reload(self) -> None:
        self._active_tab.reload()
        self._saved_tab.reload()
