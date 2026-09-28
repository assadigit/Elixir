"""Markdown Styler dialog (V18.20.4.6, P5 / O-b2 split).

MarkdownStylerDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. Deterministic (V11.71.0): no LLM, no
worker, hence no closeEvent guard. ui_qt.views.service_dialogs.
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
from ui_qt.views.service_dialogs.dialogs.shared import (
    PlainTextTextEdit,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.66.0/V11.71.0: Markdown Styler — messy notes → clean Obsidian markdown
# V11.71.0: DETERMINISTIC — no LLM, pure Python regex-based. Instant.
# ════════════════════════════════════════════════════════════════════════════


class MarkdownStylerDialog(QDialog):
    """V11.71.0: Markdown Styler — DETERMINISTIC (no LLM, instant).

    Cleans up messy notes (copy-pasted from websites) into clean
    Obsidian-friendly markdown using Python regex — no LLM needed,
    so it's instant and reliable.

    Features:
    - Removes HTML tags, CSS, website artifacts
    - Fixes broken formatting (excessive blank lines, weird spacing)
    - Detects headings and formats them properly (#, ##, ###)
    - Converts bullet lists to proper markdown (- )
    - Adds YAML frontmatter with title + date + tags
    - Adds TLDR callout (extracts first sentence)
    - Adds Key Concepts callout (extracts bold/important terms)
    - Normalizes links, code blocks, blockquotes
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("✨ Markdown Styler")
        self.setMinimumSize(700, 600)
        self.setModal(True)
        self._worker = None

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
            "Paste messy notes (copy-pasted from a website) and get "
            "clean, Obsidian-friendly markdown INSTANTLY — no LLM, "
            "no waiting. Pure Python formatting."
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

        # V11.71.0: no model selection — deterministic, no LLM

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

        # V11.71.0: no model refresh needed — deterministic, no LLM

    def _on_process(self):
        """V11.71.0: Deterministic styling — instant, no LLM, no timeout."""
        text = self.text_input.toPlainText().strip()
        if not text or len(text) < 20:
            QMessageBox.warning(
                self, "Need more text", "Please paste some text (at least 20 characters)."
            )
            return

        self.process_btn.setEnabled(False)
        self.process_btn.setText("⚡ Styling...")
        self.status_label.setText("✨ Styling markdown (instant)...")
        self.output_preview.clear()

        # V0.6.0: the "bullets"/"links" keys are gone — the deterministic
        # engine never read them (dead checkboxes advertising unimplemented
        # LLM-era features since the V11.71.0 rewrite).
        options = {
            "tldr": self.cb_tldr.isChecked(),
            "key_concepts": self.cb_key_concepts.isChecked(),
            "tags": self.cb_tags.isChecked(),
        }

        # V11.71.0: deterministic — no worker thread needed, runs instantly
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
            # V18.20.4.9 (W-b17): the traceback reaches the log BEFORE the
            # status + user box (was str(e)-only — zero diagnostics).
            logger.warning("markdown styling failed", exc_info=True)
            self.status_label.setText(f"❌ Error: {e}")
            QMessageBox.critical(self, "❌ Markdown Styler Failed", f"Error:\n\n{e}")
        finally:
            self.process_btn.setEnabled(True)
            self.process_btn.setText("✨ Style My Markdown")

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
