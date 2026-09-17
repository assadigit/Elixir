"""V10.20.0: Glossary + Patterns + Cheatsheet generators.

Three new output types inspired by the book-to-skill project:

1. GlossaryGenerator — extracts all key terms + definitions with chapter refs
2. PatternsGenerator — extracts algorithms, design patterns, decision rules
3. CheatsheetGenerator — generates decision tables + quick-reference rules

All three use the LLM to extract structured information from chapter summaries
(different from keypoints which are general bullets).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 1. Glossary Generator
# ════════════════════════════════════════════════════════════════════════════

class GlossaryGenerator(OutputGeneratorBase):
    """V10.20.0: Extract all key terms + definitions with chapter references.

    Inspired by book-to-skill's glossary.md — every key term alphabetically
    sorted with chapter references.  More structured than keypoints (which
    are general bullets) — this is a reference tool.
    """

    def generate(self, summaries: list[SummaryResult], book_title: str, output_dir: Path) -> Path | None:
        """Generate a glossary from chapter summaries."""
        chapter_summaries = []
        for s in summaries:
            if s.success:
                text = s.thorough_summary or s.executive_summary or ""
                if text:
                    chapter_summaries.append((s.chapter_heading, text[:3000]))

        if not chapter_summaries:
            self.log("  ℹ️ Glossary: No chapter summaries to process.", "INFO")
            return None

        self.log(f"  📖 Generating glossary from {len(chapter_summaries)} chapters…", "INFO")

        # Build prompt — ask for structured glossary entries
        chapters_text = "\n\n".join(
            f"## {heading}\n{text}" for heading, text in chapter_summaries
        )

        prompt = self.prompt_manager.render_template(
            "outputs/glossary",
            chapters_text=chapters_text[:12000],
        )

        response = self._call_llm(prompt, temperature=0.2, max_tokens=4096)
        if not response:
            self.log("  ⚠️ Glossary: No response from LLM.", "WARNING")
            return None

        response = self._strip_thinking(response)
        entries = self._parse_glossary(response)
        if not entries:
            self.log("  ⚠️ Glossary: No entries parsed.", "WARNING")
            return None

        # Sort alphabetically
        entries.sort(key=lambda e: e[0].lower())

        # Build markdown
        md_lines = [
            f"# Glossary: {book_title}",
            "",
            f"**{len(entries)} terms**",
            "",
            "---",
            "",
        ]
        for term, definition, chapter in entries:
            md_lines.append(f"## {term}")
            md_lines.append("")
            md_lines.append(f"{definition}")
            if chapter:
                md_lines.append("")
                md_lines.append(f"*Chapter: {chapter}*")
            md_lines.append("")

        md_content = "\n".join(md_lines)
        output_path = output_dir / f"{book_title}.Glossary.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_content, encoding="utf-8")
        self.log(f"  ✅ Glossary: {len(entries)} terms → {output_path.name}", "SUCCESS")
        return output_path

    def _parse_glossary(self, text: str) -> list[tuple]:
        """Parse LLM response into [(term, definition, chapter), ...]."""
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            # Strip leading numbering/bullets
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            line = re.sub(r'^[-\*]\s*', '', line)
            # Try format: "Term: Definition (Chapter: heading)"
            m = re.match(r'^(.+?):\s*(.+?)\s*\(Chapter:\s*(.+?)\)\s*$', line)
            if m:
                entries.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
                continue
            # Try format: "Term: Definition" (no chapter)
            m2 = re.match(r'^(.+?):\s*(.+)$', line)
            if m2 and len(m2.group(1)) < 50:  # term should be short
                entries.append((m2.group(1).strip(), m2.group(2).strip(), ""))
        return entries


# ════════════════════════════════════════════════════════════════════════════
# 2. Patterns/Techniques Generator
# ════════════════════════════════════════════════════════════════════════════

class PatternsGenerator(OutputGeneratorBase):
    """V10.20.0: Extract algorithms, design patterns, and decision rules.

    Inspired by book-to-skill's patterns.md — separates techniques from
    general keypoints.  This is a practitioner's reference, not a summary.
    """

    def generate(self, summaries: list[SummaryResult], book_title: str, output_dir: Path) -> Path | None:
        """Generate a patterns/techniques reference from chapter summaries."""
        chapter_summaries = []
        for s in summaries:
            if s.success:
                text = s.thorough_summary or s.executive_summary or ""
                if text:
                    chapter_summaries.append((s.chapter_heading, text[:3000]))

        if not chapter_summaries:
            self.log("  ℹ️ Patterns: No chapter summaries to process.", "INFO")
            return None

        self.log(f"  🔧 Generating patterns/techniques from {len(chapter_summaries)} chapters…", "INFO")

        chapters_text = "\n\n".join(
            f"## {heading}\n{text}" for heading, text in chapter_summaries
        )

        prompt = self.prompt_manager.render_template(
            "outputs/patterns",
            chapters_text=chapters_text[:12000],
        )

        response = self._call_llm(prompt, temperature=0.2, max_tokens=4096)
        if not response:
            self.log("  ⚠️ Patterns: No response from LLM.", "WARNING")
            return None

        response = self._strip_thinking(response)
        patterns = self._parse_patterns(response)
        if not patterns:
            self.log("  ⚠️ Patterns: No entries parsed.", "WARNING")
            return None

        # Group by category
        categories: dict = {}
        for category, name, description, chapter in patterns:
            if category not in categories:
                categories[category] = []
            categories[category].append((name, description, chapter))

        # Build markdown
        md_lines = [
            f"# Patterns & Techniques: {book_title}",
            "",
            f"**{len(patterns)} patterns across {len(categories)} categories**",
            "",
            "---",
            "",
        ]
        for category in sorted(categories.keys()):
            md_lines.append(f"## {category}")
            md_lines.append("")
            for name, desc, chapter in categories[category]:
                md_lines.append(f"### {name}")
                md_lines.append("")
                md_lines.append(f"{desc}")
                if chapter:
                    md_lines.append("")
                    md_lines.append(f"*Chapter: {chapter}*")
                md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        md_content = "\n".join(md_lines)
        output_path = output_dir / f"{book_title}.Patterns.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_content, encoding="utf-8")
        self.log(f"  ✅ Patterns: {len(patterns)} patterns → {output_path.name}", "SUCCESS")
        return output_path

    def _parse_patterns(self, text: str) -> list[tuple]:
        """Parse LLM response into [(category, name, description, chapter), ...]."""
        patterns = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            line = re.sub(r'^[-\*]\s*', '', line)
            # Try format: "[Category] Name: Description (Chapter: heading)"
            m = re.match(r'^\[([^\]]+)\]\s*(.+?):\s*(.+?)\s*\(Chapter:\s*(.+?)\)\s*$', line)
            if m:
                patterns.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()))
                continue
            # Try format: "[Category] Name: Description" (no chapter)
            m2 = re.match(r'^\[([^\]]+)\]\s*(.+?):\s*(.+)$', line)
            if m2:
                patterns.append((m2.group(1).strip(), m2.group(2).strip(), m2.group(3).strip(), ""))
        return patterns


# ════════════════════════════════════════════════════════════════════════════
# 3. Cheatsheet Generator
# ════════════════════════════════════════════════════════════════════════════

class CheatsheetGenerator(OutputGeneratorBase):
    """V10.20.0: Generate decision tables + quick-reference rules.

    Inspired by book-to-skill's cheatsheet.md — practical decision tables
    and quick-reference rules for practitioners.
    """

    def generate(self, summaries: list[SummaryResult], book_title: str, output_dir: Path) -> Path | None:
        """Generate a cheatsheet from chapter summaries."""
        chapter_summaries = []
        for s in summaries:
            if s.success:
                text = s.thorough_summary or s.executive_summary or ""
                if text:
                    chapter_summaries.append((s.chapter_heading, text[:3000]))

        if not chapter_summaries:
            self.log("  ℹ️ Cheatsheet: No chapter summaries to process.", "INFO")
            return None

        self.log(f"  📋 Generating cheatsheet from {len(chapter_summaries)} chapters…", "INFO")

        chapters_text = "\n\n".join(
            f"## {heading}\n{text}" for heading, text in chapter_summaries
        )

        prompt = self.prompt_manager.render_template(
            "outputs/cheatsheet",
            chapters_text=chapters_text[:12000],
        )

        response = self._call_llm(prompt, temperature=0.3, max_tokens=4096)
        if not response:
            self.log("  ⚠️ Cheatsheet: No response from LLM.", "WARNING")
            return None

        response = self._strip_thinking(response)

        md_content = f"""# Cheatsheet: {book_title}

> Quick-reference decision tables and rules for practitioners.

---

{response}
"""

        output_path = output_dir / f"{book_title}.Cheatsheet.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_content, encoding="utf-8")
        self.log(f"  ✅ Cheatsheet → {output_path.name}", "SUCCESS")
        return output_path


# ════════════════════════════════════════════════════════════════════════════
# V10.21.0: Agent Skill export (SKILL.md format)
# ════════════════════════════════════════════════════════════════════════════

class AgentSkillGenerator(OutputGeneratorBase):
    """V10.21.0: Generate a SKILL.md file for AI coding assistants.

    Inspired by book-to-skill — converts summaries + keypoints into a
    compact "agent skill" format that Claude Code, GitHub Copilot CLI,
    and Amp can load on-demand.

    Output: SKILL.md (~4000 tokens) + per-chapter files.
    """

    def generate(self, summaries: list[SummaryResult], book_title: str, output_dir: Path) -> Path | None:
        """Generate a SKILL.md from chapter summaries."""
        chapter_summaries = []
        for s in summaries:
            if s.success:
                text = s.executive_summary or s.thorough_summary or ""
                bullets = s.bullet_points or []
                if text or bullets:
                    chapter_summaries.append((s.chapter_heading, text, bullets))

        if not chapter_summaries:
            self.log("  ℹ️ Agent Skill: No summaries to process.", "INFO")
            return None

        self.log(f"  🤖 Generating Agent Skill from {len(chapter_summaries)} chapters…", "INFO")

        # Build the SKILL.md content
        md_lines = [
            f"# {book_title}",
            "",
            "## Core Mental Models",
            "",
        ]

        # Extract core frameworks from each chapter
        for heading, text, bullets in chapter_summaries:
            md_lines.append(f"### {heading}")
            md_lines.append("")
            if text:
                # Take first 200 chars as the core model
                md_lines.append(text[:500].strip())
                md_lines.append("")
            if bullets:
                md_lines.append("**Key principles:**")
                for bp in bullets[:5]:  # top 5 bullets
                    md_lines.append(f"- {bp}")
            md_lines.append("")

        # Chapter index
        md_lines.extend([
            "## Chapter Index",
            "",
        ])
        for i, (heading, _, _) in enumerate(chapter_summaries, 1):
            md_lines.append(f"{i}. {heading}")

        md_lines.extend([
            "",
            "---",
            "",
            "*Generated by Elixir V10.21.0 · Agent Skill format*",
        ])

        md_content = "\n".join(md_lines)
        output_path = output_dir / f"{book_title}.SKILL.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_content, encoding="utf-8")
        self.log(f"  ✅ Agent Skill → {output_path.name}", "SUCCESS")
        return output_path
