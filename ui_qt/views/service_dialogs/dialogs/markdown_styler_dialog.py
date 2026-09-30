"""Markdown Styler dialog (V18.20.4.6, P5 / O-b2 split).

MarkdownStylerDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. V0.6.5: LLM-STRUCTURED (the two-phase
pipeline in core/summarisation/markdown_styler.py — the LLM scans the
article, detects/generates the headings, then the deterministic
assembler emits the Obsidian note) with the V11.71.0 deterministic
regex path as the no-LLM fallback. ui_qt.views.service_dialogs.
base_dialog re-exports it (back-compat facade)."""

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
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from controller import Controller
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    PlainTextTextEdit,
    _confirm_close_with_running_worker,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.66.0/V11.71.0: Markdown Styler — messy notes → clean Obsidian markdown
# V11.71.0: DETERMINISTIC — no LLM, pure Python regex-based. Instant.
# ════════════════════════════════════════════════════════════════════════════


class MarkdownStylerDialog(QDialog):
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
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("✨ Markdown Styler")
        self.setMinimumSize(700, 620)
        self.setModal(True)
        self._worker: SimpleWorker | None = None

        from PySide6.QtWidgets import (
            QCheckBox as _QChB,
        )
        from PySide6.QtWidgets import (
            QGroupBox as _QGB,
        )
        from PySide6.QtWidgets import (
            QHBoxLayout as _HL,
        )
        from PySide6.QtWidgets import (
            QLabel as _QL,
        )
        from PySide6.QtWidgets import (
            QProgressBar as _QPB2,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("✨ Markdown Styler")
        title.setObjectName("H2")
        lay.addWidget(title)

        desc = _QL(
            "Paste a raw article — an LLM scans it, finds (or writes) the "
            "headings, and stylizes it into a clean Obsidian note. "
            "Uncheck LLM structuring for the instant offline (regex) path."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Input text
        input_group = _QGB("1. Paste messy article:")
        input_lay = _VL(input_group)
        self.text_input = PlainTextTextEdit()
        self.text_input.setPlaceholderText(
            "Paste your messy article here — copy-pasted from a website, "
            "with weird formatting, broken links, missing structure, etc."
        )
        self.text_input.setMinimumHeight(150)
        input_lay.addWidget(self.text_input)
        lay.addWidget(input_group)

        # Options
        opt_group = _QGB("2. Options:")
        opt_lay = _VL(opt_group)

        # V0.6.5: the LLM structuring row — model picker + toggle.
        from PySide6.QtWidgets import QComboBox as _QCB

        llm_row = _HL()
        self.llm_chk = _QChB("🤖 LLM structuring (scan → headings → Obsidian)")
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
        llm_row.addWidget(_QL("Model:"))
        self.model_combo = _QCB()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(220)
        llm_row.addWidget(self.model_combo, 1)
        refresh_btn = _QPB("🔄")
        refresh_btn.setFixedWidth(34)
        refresh_btn.setToolTip("Re-fetch the installed model list")
        refresh_btn.clicked.connect(self._refresh_models)
        llm_row.addWidget(refresh_btn)
        opt_lay.addLayout(llm_row)

        # Checkboxes for output options
        self.cb_tldr = _QChB("Add TLDR (1-2 sentence summary at the top)")
        self.cb_tldr.setChecked(True)
        opt_lay.addWidget(self.cb_tldr)

        self.cb_key_concepts = _QChB("Extract key concepts as a callout block")
        self.cb_key_concepts.setChecked(True)
        opt_lay.addWidget(self.cb_key_concepts)

        self.cb_tags = _QChB("Add YAML frontmatter + tags")
        self.cb_tags.setChecked(True)
        opt_lay.addWidget(self.cb_tags)

        lay.addWidget(opt_group)

        # Output
        out_group = _QGB("3. Output:")
        out_lay = _VL(out_group)
        self.output_preview = PlainTextTextEdit()
        self.output_preview.setReadOnly(True)
        self.output_preview.setPlaceholderText("Cleaned markdown will appear here after styling.")
        self.output_preview.setMinimumHeight(150)
        out_lay.addWidget(self.output_preview)

        out_btn_row = _HL()
        self.save_btn = _QPB("💾 Save as .md")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        out_btn_row.addStretch()
        out_btn_row.addWidget(self.save_btn)
        out_lay.addLayout(out_btn_row)
        lay.addWidget(out_group)

        # Process button
        self.process_btn = _QPB("✨ Style My Markdown")
        self.process_btn.setObjectName("Primary")
        self.process_btn.clicked.connect(self._on_process)
        lay.addWidget(self.process_btn)

        # Progress
        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        # V0.6.5: populate the model picker on open.
        self._refresh_models()

    def closeEvent(self, event) -> None:
        # V0.6.5, V18.20.4.5 (T-b2) shape: LLM runs ride a SimpleWorker —
        # guard against the "QThread: Destroyed while thread is still
        # running" abort class (the same T-b2 contract every
        # worker-owning dialog carries).
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    # ── V0.6.5: LLM structuring wiring ─────────────────────────────

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

        models: list[str] | None = None
        try:
            import requests as _req

            r = _req.get(f"{base}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
        except Exception:
            models = None  # unreachable — keep the default row

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
