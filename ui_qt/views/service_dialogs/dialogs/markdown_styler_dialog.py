"""Markdown Styler dialog (V18.20.4.6, P5 / O-b2 split).

MarkdownStylerDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. V0.6.5: LLM-STRUCTURED (the two-phase
pipeline in core/summarisation/markdown_styler.py — the LLM scans the
article, detects/generates the headings, then the deterministic
assembler emits the Obsidian note) with the V11.71.0 deterministic
regex path as the no-LLM fallback. ui_qt.views.service_dialogs.
base_dialog re-exports it (back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ delegates the common
skeleton (title, paste-text area, options container, progress, status,
buttons) to the base and folds its byte-identical closeEvent guard
away (inherited). The LLM row + option checkboxes + the output
preview/save row fold into _build_options; the base's "Save to:" row
is hidden (the styler previews FIRST and picks the save location at
save time via _on_save — the reverse of the base's
pick-output-first flow, so nothing would ever read out_path_edit).
The V0.6.5 LLM worker launch keeps its pinned shape: _run_llm_styling
spawns the SimpleWorker (the base's _process/_collect_options flow
does not fit the preview-then-save contract)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from core.system.timeouts import UI_PROBE_TIGHT_TIMEOUT_S
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    PlainTextTextEdit,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.66.0/V11.71.0: Markdown Styler — messy notes → clean Obsidian markdown
# V11.71.0: DETERMINISTIC — no LLM, pure Python regex-based. Instant.
# ════════════════════════════════════════════════════════════════════════════


class MarkdownStylerDialog(BaseServiceDialog):
    """V0.6.5: Markdown Styler — LLM-STRUCTURED first, deterministic fallback.

    The user's requirement: turning a raw article into markdown cannot
    be fully deterministic — FIRST an LLM scans the article and finds
    the headings (generating a fitting title when the article has none),
    THEN the note is stylized into the Obsidian shape (front-matter,
    ``> [!tldr]`` / ``> [!info]`` callouts, ``##``/``###`` sections,
    clean spacing). That is exactly what
    ``core.summarisation.markdown_styler.style_markdown_llm`` does.

    Unchecking "LLM structuring" runs the V11.71.0 deterministic regex
    path (instant, offline); an LLM failure also falls back to it with
    a ⚠️ in the status line — the tool never hard-fails on a model miss.

    V11.71.0 heritage (kept): removes HTML/CSS artifacts, fixes broken
    formatting, normalizes bullets/links, YAML front-matter + tags,
    TLDR + Key Concepts callouts.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options (the LLM row + checkboxes +
        # output preview), which needs nothing pre-set. The base also
        # initializes self._worker (its closeEvent guards it).
        super().__init__(
            controller, "✨ Markdown Styler", parent, accept_files=False, accept_text=True
        )
        # V0.6.10 (B17): this dialog's original geometry over the base's
        # generic 560×480, its taller paste area + guidance placeholder,
        # and the styler trigger label on the base Process button.
        self.setMinimumSize(700, 620)
        self.text_input.setPlaceholderText(
            "Paste your messy article here — copy-pasted from a website, "
            "with weird formatting, broken links, missing structure, etc."
        )
        self.text_input.setMinimumHeight(150)
        self.process_btn.setText("✨ Style My Markdown")
        # V0.6.10 (B17): hide the base "Save to:" row — the styler picks
        # the save location AT save time (via _on_save's QFileDialog); the
        # row's pre-picked path would never be read.
        self._hide_base_output_row()
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (its _on_llm_progress override
        # only sets status text) — hide the dead toggle (the transcribe
        # B17 precedent).
        self._log_toggle_btn.setVisible(False)

        # V0.6.5: populate the model picker on open.
        self._refresh_models()

    def _hide_base_output_row(self) -> None:
        """V0.6.10 (B17): hide the base class's "Save to:" row — the
        styler previews the note first and picks the save location at
        save time (``_on_save``), so the row's pre-picked path would be
        dead UI (nothing in this dialog ever reads ``out_path_edit``)."""
        root = self.layout()
        if root is None:
            return
        for i in range(root.count()):
            item = root.itemAt(i)
            row = item.layout() if item is not None else None
            if row is None or row.indexOf(self.out_path_edit) < 0:
                continue
            for j in range(row.count()):
                w = row.itemAt(j).widget()
                if w is not None:
                    w.setVisible(False)
            return

    def _build_options(self, layout: QVBoxLayout) -> None:
        """V0.6.10 (B17): the styler's option rows (the V0.6.5 LLM
        structuring row + the V11.71.0 output checkboxes) and its result
        surface (the output preview + save row) folded into the base's
        options container. The preview-then-save flow is the reverse of
        the base's pick-output-first flow — the base's result_preview
        stays hidden and this dialog's output_preview is the live one."""
        desc = QLabel(
            "Paste a raw article — an LLM scans it, finds (or writes) the "
            "headings, and stylizes it into a clean Obsidian note. "
            "Uncheck LLM structuring for the instant offline (regex) path."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # V0.6.5: the LLM structuring row — model picker + toggle.
        llm_row = QHBoxLayout()
        self.llm_chk = QCheckBox("🤖 LLM structuring (scan → headings → Obsidian)")
        self.llm_chk.setToolTip(
            "The LLM reads the article, detects its real headings (or writes "
            "a fitting title when there is none), then the note is assembled "
            "in the Obsidian style. Falls back to the instant regex path when "
            "the model is unreachable."
        )
        self.llm_chk.setChecked(True)
        self.llm_chk.toggled.connect(self._on_llm_toggled)
        llm_row.addWidget(self.llm_chk)
        llm_row.addSpacing(12)
        llm_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(220)
        llm_row.addWidget(self.model_combo, 1)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(34)
        refresh_btn.setToolTip("Re-fetch the installed model list")
        refresh_btn.clicked.connect(self._refresh_models)
        llm_row.addWidget(refresh_btn)
        layout.addLayout(llm_row)

        # Checkboxes for output options
        self.cb_tldr = QCheckBox("Add TLDR (1-2 sentence summary at the top)")
        self.cb_tldr.setChecked(True)
        layout.addWidget(self.cb_tldr)

        self.cb_key_concepts = QCheckBox("Extract key concepts as a callout block")
        self.cb_key_concepts.setChecked(True)
        layout.addWidget(self.cb_key_concepts)

        self.cb_tags = QCheckBox("Add YAML frontmatter + tags")
        self.cb_tags.setChecked(True)
        layout.addWidget(self.cb_tags)

        # Output preview + save row (the styler's result surface).
        self.output_preview = PlainTextTextEdit()
        self.output_preview.setReadOnly(True)
        self.output_preview.setPlaceholderText("Cleaned markdown will appear here after styling.")
        self.output_preview.setMinimumHeight(150)
        layout.addWidget(self.output_preview)

        out_btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save as .md")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        out_btn_row.addStretch()
        out_btn_row.addWidget(self.save_btn)
        layout.addLayout(out_btn_row)

    # V0.6.10 (B17): the closeEvent guard (identical to the base's —
    # _confirm_close_with_running_worker(self, self._worker)) is now
    # INHERITED from BaseServiceDialog; the pre-B17 copy was
    # byte-equivalent and was deleted.

    # ── V0.6.5: LLM structuring wiring ─────────────────────────────

    def _get_service_name(self) -> str:
        # V0.6.10 (B17): base-class identity hook. This dialog persists no
        # controller settings (grep: zero controller.update_setting /
        # controller.get_setting calls — the model defaults are read via
        # Settings() with their legacy key shapes:
        # quick_services.defaults.summarize_model / summarisation.model),
        # so the name is identity-only.
        return "markdown_styler"

    def _on_llm_toggled(self, checked: bool) -> None:
        """The model picker only matters for the LLM path."""
        self.model_combo.setEnabled(checked)

    def _refresh_models(self) -> None:
        """V0.6.5: populate the model combo (the summarizer dialog's
        pattern — /api/tags via the canonical get_ollama_url, "Default
        Model" sentinel first, configured model kept visible when
        missing)."""
        from utils.settings import Settings

        try:
            s = Settings()
            configured = s.get("summarisation.model", RIG_FALLBACK_MODEL) or RIG_FALLBACK_MODEL
            base = s.get_ollama_url()
        except Exception:
            configured, base = RIG_FALLBACK_MODEL, "http://localhost:11434"

        models: list[str] = []
        # V0.6.8 (review-loop follow-up, B5 class — the 7th site the fresh
        # reviewer found): routed through the shared proxy-proof transport
        # (was a bare requests.get that broke on HTTP_PROXY machines);
        # UI_PROBE_TIGHT_TIMEOUT_S (3 s; V0.6.11 wave 8: the named constant)
        # preserves the original latency budget. The [] vs None
        # distinction was vestigial (both took the same else-branch below).
        try:
            from utils.network import list_ollama_models

            models = [m for m in list_ollama_models(base, timeout=UI_PROBE_TIGHT_TIMEOUT_S) if m]
        except Exception:
            models = []  # unreachable/bad response — keep the default row

        current = self.model_combo.currentText().strip()
        self.model_combo.clear()
        self.model_combo.addItem("Default Model (change in Settings)", "__default__")
        if models:
            for m in models:
                self.model_combo.addItem(m, m)
            if configured not in models:
                self.model_combo.addItem(configured, configured)
        else:
            self.model_combo.addItem(configured, configured)

        # Restore the selection.
        if current and current != "Default Model (change in Settings)":
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(current)
        else:
            self.model_combo.setCurrentIndex(0)

    def _resolve_model(self) -> str:
        """The combo's current model, resolving the "__default__" sentinel
        through quick_services → summarisation → RIG_FALLBACK."""
        from utils.settings import Settings

        data = self.model_combo.currentData()
        if data and data != "__default__":
            return str(data)
        s = Settings()
        return (
            s.get("quick_services.defaults.summarize_model", "")
            or s.get("summarisation.model", "")
            or RIG_FALLBACK_MODEL
        )

    def _on_process(self):
        """V0.6.5: route to the LLM structuring pipeline (default) or the
        V11.71.0 deterministic path (unchecked / fallback)."""
        # V0.6.10 (B17): kept override — the base's _on_process validates a
        # generic text/output-path pair and spawns
        # SimpleWorker(self._process, …); this dialog's contract is the
        # ≥20-char guard, its own options dict, and the deterministic /
        # LLM routing with the preview-then-save completion pair (no
        # base-equivalent flow). Body unchanged.
        text = self.text_input.toPlainText().strip()
        if not text or len(text) < 20:
            QMessageBox.warning(
                self, "Need more text", "Please paste some text (at least 20 characters)."
            )
            return

        options = {
            "tldr": self.cb_tldr.isChecked(),
            "key_concepts": self.cb_key_concepts.isChecked(),
            "tags": self.cb_tags.isChecked(),
        }

        if self.llm_chk.isChecked():
            self._run_llm_styling(text, options)
            return

        # ── Deterministic path (V11.71.0, unchanged) ─────────────
        self.process_btn.setEnabled(False)
        self.process_btn.setText("⚡ Styling...")
        self.status_label.setText("✨ Styling markdown (instant, offline)...")
        self.output_preview.clear()
        try:
            result = self._style_markdown_deterministic(text, options)
            if result and not result.startswith("Error:"):
                self.output_preview.setPlainText(result)
                self.save_btn.setEnabled(True)
                self.status_label.setText(
                    f"✅ Styled! {len(result)} chars — instant. Review and save."
                )
            else:
                self.status_label.setText(f"❌ {result}")
        except Exception as e:
            logger.warning("markdown styling failed", exc_info=True)
            self.status_label.setText(f"❌ Error: {e}")
            QMessageBox.critical(self, "❌ Markdown Styler Failed", f"Error:\n\n{e}")
        finally:
            self.process_btn.setEnabled(True)
            self.process_btn.setText("✨ Style My Markdown")

    def _run_llm_styling(self, text: str, options: dict) -> None:
        """V0.6.5: the LLM path on a worker thread (the streaming call can
        take a minute — never on the UI thread; the W-b5 contract)."""
        model = self._resolve_model()

        self.process_btn.setEnabled(False)
        self.process_btn.setText("🤖 Scanning structure…")
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"🤖 LLM scanning the article for headings (model: {model})…")
        self.output_preview.clear()

        self._worker = SimpleWorker(
            lambda: self._llm_styling_work(text, options, model, report=self._worker.progress.emit)
        )
        self._worker.progress.connect(self._on_llm_progress)
        self._worker.finished.connect(self._on_llm_finished)
        self._worker.failed.connect(self._on_llm_failed)
        self._worker.start()

    def _llm_styling_work(self, text: str, options: dict, model: str, report=None) -> dict:
        """Worker body: pure LLM/file work, no widget access. Falls back to
        the deterministic path INSIDE the worker when the LLM fails, so the
        finished handler only ever renders a result."""
        from core.summarisation.markdown_styler import style_markdown_llm

        def _llm_call(prompt: str) -> str | None:
            from core.llm.llm_provider import create_provider
            from utils.settings import Settings

            if report is not None:
                report(0, "🤖 LLM scanning the article…")
            try:
                provider = create_provider(
                    provider=Settings().get("summarisation.provider", "ollama"),
                    settings=Settings(),
                    log_callback=lambda msg, level="INFO": None,
                )
            except Exception as e:
                logger.warning("styler: provider creation failed: %s", e)
                return None
            try:
                return provider.complete_streaming(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=6144,
                    model=model,
                )
            except Exception as e:
                logger.warning("styler: LLM call failed: %s", e)
                return None

        result = style_markdown_llm(
            text,
            _llm_call,
            include_tldr=options.get("tldr", True),
            include_concepts=options.get("key_concepts", True),
            include_tags=options.get("tags", True),
        )

        if result is not None:
            note, structure = result
            return {
                "note": note,
                "llm": True,
                "title": structure.get("title", ""),
                "sections": len(structure.get("sections", [])),
                "model": model,
            }

        # Fallback: the deterministic path, flagged.
        logger.warning("styler: LLM structuring failed — deterministic fallback")
        det = self._style_markdown_deterministic(text, options)
        return {"note": det, "llm": False, "model": model}

    def _on_llm_progress(self, pct: int, msg: str) -> None:
        self.status_label.setText(msg)

    def _on_llm_finished(self, result: dict) -> None:
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("✨ Style My Markdown")
        result = result or {}
        note = result.get("note", "")
        if note and not note.startswith("Error:"):
            self.output_preview.setPlainText(note)
            self.save_btn.setEnabled(True)
            if result.get("llm"):
                self.status_label.setText(
                    f"✅ Styled by LLM — title: “{result.get('title', '')}’, "
                    f"{result.get('sections', 0)} section(s), model {result.get('model')}. "
                    "Review and save."
                )
            else:
                self.status_label.setText(
                    "⚠️ LLM structuring unavailable — styled with the instant "
                    "offline path. Check the model/backend and retry."
                )
        else:
            self.status_label.setText(f"❌ {note or 'Styling failed.'}")

    def _on_llm_failed(self, err: str) -> None:
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("✨ Style My Markdown")
        self.status_label.setText(f"❌ Error: {err}")

    def _style_markdown_deterministic(self, text: str, options: dict) -> str:
        """V11.71.0: Deterministic markdown styling — pure Python, instant.

        No LLM needed. Uses regex to:
        1. Remove HTML tags, CSS, JavaScript
        2. Fix broken formatting (excessive blank lines, weird spacing)
        3. Detect and format headings
        4. Normalize bullet lists
        5. Add YAML frontmatter + tags (if enabled)
        6. Add TLDR callout (if enabled)
        7. Add Key Concepts callout (if enabled)
        8. Normalize links, code blocks, blockquotes
        """
        import datetime

        # ── Step 1: Remove HTML tags ──────────────────────────────────
        # Remove <script> and <style> blocks entirely
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Remove all HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Remove HTML entities
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"&[a-z]+;", "", text, flags=re.IGNORECASE)

        # ── Step 2: Fix whitespace ────────────────────────────────────
        # Replace tabs with spaces
        text = text.replace("\t", "    ")
        # Remove trailing whitespace on each line
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        # Collapse runs of 2+ spaces after a word character to a single
        # space (line-start indentation is preserved). V0.6.0: the old
        # ``(?<= ) +`` → " " always left TWO spaces behind (one lookbehind
        # anchor + the replacement) — double spaces never collapsed.
        text = re.sub(r"(?<=\S) {2,}", " ", text)
        # Limit consecutive blank lines to 2
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Remove leading/trailing blank lines
        text = text.strip()

        # ── Step 3: Detect and format headings ────────────────────────
        # Lines that are short, no terminal punctuation, and look like titles
        lines = text.split("\n")
        formatted_lines = []
        heading_count = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                formatted_lines.append("")
                continue

            # Skip lines that are already markdown headings
            if stripped.startswith("#"):
                formatted_lines.append(stripped)
                continue

            # Skip lines that are bullet points
            if stripped.startswith(("- ", "* ", "+ ", "• ")):
                formatted_lines.append(stripped)
                continue

            # Skip lines that are numbered lists
            if re.match(r"^\d+\.\s", stripped):
                formatted_lines.append(stripped)
                continue

            # Detect headings: short line (<80 chars), no period at end,
            # next line is blank or another heading
            is_heading = (
                len(stripped) < 80
                and not stripped.endswith(".")
                and not stripped.endswith(",")
                and not stripped.endswith(";")
                and not stripped.endswith(":")
                and not stripped.endswith("?")
                and not stripped.endswith("!")
                and not re.search(r"[.!?]\s", stripped)  # no sentence-ending
                and len(stripped) > 3
                and
                # Must be Title Case or ALL CAPS or has ## already
                (stripped.istitle() or stripped.isupper() or re.match(r"^#{1,6}\s", stripped))
            )

            # Also check: is the previous line blank or start of text?
            prev_blank = i == 0 or not lines[i - 1].strip()

            if is_heading and prev_blank:
                heading_count += 1
                # Use ## for first-level headings, ### for sub-sections
                prefix = "##" if heading_count <= 5 else "###"
                formatted_lines.append(f"{prefix} {stripped}")
            else:
                formatted_lines.append(stripped)

        text = "\n".join(formatted_lines)

        # ── Step 4: Normalize bullet lists ────────────────────────────
        # Convert various bullet markers to standard markdown -
        text = re.sub(r"^[•·▪◦‣]\s", "- ", text, flags=re.MULTILINE)
        text = re.sub(r"^\*\s", "- ", text, flags=re.MULTILINE)
        text = re.sub(r"^\+\s", "- ", text, flags=re.MULTILINE)

        # ── Step 5: Normalize numbered lists ──────────────────────────
        # Ensure consistent format: "1. " not "1)" or "1."
        text = re.sub(r"^(\d+)\)\s", r"\1. ", text, flags=re.MULTILINE)
        text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)

        # ── Step 6: Normalize links ───────────────────────────────────
        # Convert bare URLs to markdown links
        text = re.sub(r"(?<![\[\(])(https?://[^\s\)\]]+)", r"[\1](\1)", text)

        # ── Step 7: Add YAML frontmatter (if enabled) ─────────────────
        frontmatter = ""
        if options.get("tags"):
            # Extract a title from the first heading or first line
            title_match = re.search(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
            title = title_match.group(1) if title_match else "Untitled Note"
            # V0.6.0: escape YAML double-quoted scalars — a heading
            # containing a ``"`` produced invalid frontmatter
            # (``title: "The "Fast" Track"``).
            title = title.replace("\\", "\\\\").replace('"', '\\"')
            # Generate tags from common words in the text
            words = re.findall(r"\b[A-Z][a-z]{3,}\b", text)
            from collections import Counter

            word_counts = Counter(words)
            # Top 5 most common capitalized words as tags
            tags = [w.lower() for w, _ in word_counts.most_common(5)]
            today = datetime.date.today().isoformat()
            frontmatter = f"""---
title: "{title}"
date: {today}
tags: [{", ".join(tags)}]
---

"""

        # ── Step 8: Add TLDR callout (if enabled) ─────────────────────
        tldr_block = ""
        if options.get("tldr"):
            # Extract first meaningful sentence. V0.6.0: heading lines are
            # dropped first — the sentence splitter glues a heading to the
            # following paragraph (headings carry no terminal punctuation),
            # so the first CONTENT sentence was skipped whenever a heading
            # preceded it and the TL;DR fell through to a later sentence.
            tldr_source = "\n".join(
                ln for ln in text.split("\n") if not ln.lstrip().startswith("#")
            )
            sentences = re.split(r"(?<=[.!?])\s+", tldr_source)
            first_sentence = ""
            for s in sentences:
                s = s.strip()
                if len(s) > 20 and not s.startswith("#") and not s.startswith("-"):
                    first_sentence = s
                    break
            if first_sentence:
                tldr_block = f"""> [!tldr] Summary
> {first_sentence}

---

"""

        # ── Step 9: Add Key Concepts callout (if enabled) ─────────────
        concepts_block = ""
        if options.get("key_concepts"):
            # Extract bold text or capitalized terms
            bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
            if not bold_terms:
                # Fall back to capitalized words
                bold_terms = re.findall(r"\b([A-Z][a-z]{4,}(?:[ \t]+[A-Z][a-z]+)*)\b", text)
                # V0.6.0: ``[ \t]`` (not ``\s``) in the continuation —
                # ``\s`` matched across the newline, so a term spanning
                # two lines emitted an un-prefixed line INSIDE the ``> -
                # **...**`` callout, breaking the Obsidian callout block.
                bold_terms = list(dict.fromkeys(bold_terms))[:5]  # unique, top 5
            if bold_terms:
                concepts = "\n".join(f"> - **{t}**" for t in bold_terms[:5])
                concepts_block = f"""> [!info] Key Concepts
{concepts}

---

"""

        # ── Step 10: Assemble final output ────────────────────────────
        result = frontmatter + tldr_block + concepts_block + text

        # Final cleanup: ensure single trailing newline
        result = result.rstrip() + "\n"

        return result

    def _on_save(self):
        text = self.output_preview.toPlainText()
        if not text.strip():
            return
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_path = str(Path.home() / "Desktop" / f"Styled-{ts}.md")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save styled markdown", default_path, "Markdown files (*.md);;All files (*.*)"
        )
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                self.status_label.setText(f"✅ Saved to: {path}")
            except Exception as e:
                # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE
                # the user box (was str(e)-only — zero diagnostics).
                logger.warning("styled markdown save failed", exc_info=True)
                QMessageBox.critical(self, "Save failed", str(e))
