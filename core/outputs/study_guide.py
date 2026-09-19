"""V4.1.0: Study Guide generator.

Produces a structured, pedagogically-organised study guide from the chapter
summaries and key points. Unlike flashcards (isolated Q→A pairs), the study
guide groups content into a learning workflow:

  1. Learning Objectives  — what the reader should be able to do after studying
  2. Key Terms Glossary    — definitions of the book's core vocabulary
  3. Concept Review (Q&A)  — grouped by chapter, with richer answers
  4. Self-Check Questions  — open-ended prompts to test understanding
  5. Further Reflection    — discussion / application prompts

The generator makes 2 + ⌈bullets/15⌉ LLM calls:
  · one combined call for objectives + glossary
  · batched calls for concept Q&A (15 keypoints per batch)
  · one combined call for self-check + reflection

All sections degrade gracefully: if an LLM call fails, that section is
omitted with a note rather than crashing the whole guide.

Output: ``<BookTitle>.StudyGuide.md``
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

logger = logging.getLogger(__name__)


class StudyGuideGenerator(OutputGeneratorBase):
    """V4.1: Generate a structured study guide from keypoints."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate ``BookName.StudyGuide.md`` and return its path."""
        chapters = [s for s in summaries if s.success]
        if not chapters:
            self.log("  ℹ️ Study guide: No chapter summaries available.", "INFO")
            return None

        # Gather (chapter, bullet) pairs and a chapter overview sample.
        chapter_bullets: list[tuple[str, str]] = []
        chapter_overviews: list[str] = []
        for s in chapters:
            if s.executive_summary:
                chapter_overviews.append(f"- {s.chapter_heading}: {s.executive_summary.strip()}")
            if s.bullet_points:
                for bp in s.bullet_points:
                    chapter_bullets.append((s.chapter_heading, bp.strip()))

        if not chapter_bullets and not chapter_overviews:
            self.log("  ℹ️ Study guide: No keypoints or summaries to build from.", "INFO")
            return None

        self.log(
            f"  📚 Generating study guide from {len(chapters)} chapters, "
            f"{len(chapter_bullets)} keypoints…",
            "INFO",
        )

        # ── Section 1+2: Objectives + Glossary (one call) ────────────────
        objectives, glossary = self._gen_objectives_and_glossary(
            book_title, chapter_overviews, chapter_bullets
        )

        # ── Section 3: Concept Q&A (batched) ─────────────────────────────
        qa_sections = self._gen_concept_qa(book_title, chapter_bullets)

        # ── Section 4+5: Self-check + Reflection (one call) ──────────────
        self_check, reflection = self._gen_selfcheck_and_reflection(book_title, chapter_bullets)

        # ── Assemble the markdown ────────────────────────────────────────
        md = self._assemble_markdown(
            book_title=book_title,
            chapter_count=len(chapters),
            objectives=objectives,
            glossary=glossary,
            qa_sections=qa_sections,
            self_check=self_check,
            reflection=reflection,
        )

        output_path = output_dir / f"{book_title}.StudyGuide.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        try:
            atomic_write_text(output_path, md, encoding="utf-8")
        except Exception as e:
            self.log(f"  ⚠️ Study guide: failed to write file: {e}", "WARNING")
            return None

        self.log(f"  ✅ Study guide saved to: {output_path}", "SUCCESS")
        return output_path

    # ══════════════════════════════════════════════════════════════════════
    # LLM-driven section generators
    # ══════════════════════════════════════════════════════════════════════

    def _gen_objectives_and_glossary(
        self,
        book_title: str,
        chapter_overviews: list[str],
        chapter_bullets: list[tuple[str, str]],
    ) -> tuple[list[str], list[tuple[str, str]]]:
        """One LLM call → (learning objectives, key-terms glossary).

        Returns ([objective strings], [(term, definition), ...]).
        Falls back to deterministic extraction on failure.
        """
        overviews_text = "\n".join(chapter_overviews[:20])
        bullets_text = "\n".join(f"- [{chap[:40]}] {bp}" for chap, bp in chapter_bullets[:40])

        prompt = self.prompt_manager.render_template(
            "outputs/study_guide_lo_terms",
            book_title=book_title,
            overviews_text=overviews_text,
            bullets_text=bullets_text,
        )
        resp = self._call_llm(prompt, temperature=0.3, max_tokens=2048)
        objectives: list[str] = []
        glossary: list[tuple[str, str]] = []

        if resp:
            resp = self._strip_thinking(resp)
            section = None
            for line in resp.splitlines():
                line = line.strip()
                if not line:
                    continue
                upper = line.upper()
                if "LEARNING OBJECTIVES" in upper and len(line) < 40:
                    section = "lo"
                    continue
                if "KEY TERMS" in upper and len(line) < 40:
                    section = "terms"
                    continue
                if section == "lo" and upper.startswith("LO:"):
                    obj = line.split(":", 1)[1].strip().lstrip("-• ").strip()
                    if obj:
                        objectives.append(obj)
                elif section == "terms" and ":" in line:
                    # Distinguish "TERM: def" from accidental prose.
                    term, _, defn = line.partition(":")
                    term = term.strip().lstrip("-• ").strip()
                    defn = defn.strip()
                    if term and defn and len(term) <= 60:
                        glossary.append((term, defn))

        # Deterministic fallbacks so sections are never empty.
        if not objectives:
            objectives = self._fallback_objectives(chapter_bullets)
        if not glossary:
            glossary = self._fallback_glossary(chapter_bullets)

        return objectives, glossary

    def _gen_concept_qa(
        self,
        book_title: str,
        chapter_bullets: list[tuple[str, str]],
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """Batched LLM calls → [(chapter, [(question, answer), ...]), ...].

        Reuses the flashcard batching pattern (15 per batch) but asks for
        richer 1-3 sentence answers and groups results by chapter.
        """
        batch_size = 15
        # Accumulate Q&A per chapter, preserving chapter order of first hit.
        by_chapter: list[tuple[str, list[tuple[str, str]]]] = []
        chapter_index: dict = {}

        total_batches = (len(chapter_bullets) + batch_size - 1) // batch_size
        for i in range(0, len(chapter_bullets), batch_size):
            batch = chapter_bullets[i : i + batch_size]
            batch_num = i // batch_size + 1
            self.log(
                f"    📖 Study guide Q&A batch {batch_num}/{total_batches}…",
                "INFO",
            )

            bullets_list = "\n".join(
                f"{j + 1}. [{chap[:30]}] {bp}" for j, (chap, bp) in enumerate(batch)
            )

            prompt = self.prompt_manager.render_template(
                "outputs/study_guide_qa",
                bullets_list=bullets_list,
            )
            resp = self._call_llm(prompt, temperature=0.2, max_tokens=2048)
            if not resp:
                self.log(
                    f"    ⚠️ Study guide batch {batch_num}: no response, skipping.",
                    "DEBUG",
                )
                continue
            resp = self._strip_thinking(resp)

            for line in resp.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Strip leading numbering.
                line = re.sub(r"^\d+[\.\)]\s*", "", line)
                parts = [p.strip() for p in line.split("::")]
                if len(parts) == 3 and all(parts):
                    chap, q, a = parts
                elif "\t" in line:
                    bits = line.split("\t")
                    if len(bits) >= 3:
                        chap, q, a = bits[0].strip(), bits[1].strip(), bits[2].strip()
                    else:
                        continue
                else:
                    continue
                if not (chap and q and a):
                    continue
                if chap not in chapter_index:
                    chapter_index[chap] = len(by_chapter)
                    by_chapter.append((chap, []))
                by_chapter[chapter_index[chap]][1].append((q, a))

            time.sleep(0.4)  # brief pause between batches

        return by_chapter

    def _gen_selfcheck_and_reflection(
        self,
        book_title: str,
        chapter_bullets: list[tuple[str, str]],
    ) -> tuple[list[str], list[str]]:
        """One LLM call → (self-check questions, reflection prompts)."""
        bullets_text = "\n".join(f"- {bp}" for _, bp in chapter_bullets[:35])

        prompt = self.prompt_manager.render_template(
            "outputs/study_guide_selfcheck",
            book_title=book_title,
            bullets_text=bullets_text,
        )
        resp = self._call_llm(prompt, temperature=0.4, max_tokens=1536)
        self_check: list[str] = []
        reflection: list[str] = []

        if resp:
            resp = self._strip_thinking(resp)
            section = None
            for line in resp.splitlines():
                line = line.strip()
                if not line:
                    continue
                upper = line.upper()
                if "SELF-CHECK" in upper and len(line) < 40:
                    section = "sc"
                    continue
                if "REFLECTION" in upper and len(line) < 40:
                    section = "rf"
                    continue
                if section == "sc" and upper.startswith("Q:"):
                    q = line.split(":", 1)[1].strip().lstrip("-• ").strip()
                    if q:
                        self_check.append(q)
                elif section == "rf" and upper.startswith("R:"):
                    r = line.split(":", 1)[1].strip().lstrip("-• ").strip()
                    if r:
                        reflection.append(r)

        if not self_check:
            self_check = [
                "In your own words, what is the central thesis of the book?",
                "Which key idea did you find most surprising, and why?",
                "Where do you disagree with the author's argument?",
            ]
        if not reflection:
            reflection = [
                "Pick one concept and describe how you could apply it this week.",
                "Which idea would be hardest to implement in your context, and why?",
            ]
        return self_check, reflection

    # ══════════════════════════════════════════════════════════════════════
    # Deterministic fallbacks
    # ══════════════════════════════════════════════════════════════════════

    def _fallback_objectives(self, chapter_bullets: list[tuple[str, str]]) -> list[str]:
        """Build objectives from the first few keypoints if LLM fails."""
        objectives: list[str] = []
        for _, bp in chapter_bullets[:6]:
            bp_clean = bp.strip().lstrip("-•* ").strip()
            if len(bp_clean) > 20:
                # Turn "X is Y" into "Explain X".
                first_clause = re.split(r"[.;,—]", bp_clean)[0][:80]
                objectives.append(f"Explain the following idea: {first_clause}")
        if not objectives:
            objectives = [
                "Explain the central thesis of the book.",
                "Identify the key frameworks introduced across chapters.",
                "Apply the core concepts to a real-world scenario.",
            ]
        return objectives

    def _fallback_glossary(self, chapter_bullets: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Pick capitalised terms from bullets as a minimal glossary."""
        seen = set()
        glossary: list[tuple[str, str]] = []
        for _, bp in chapter_bullets:
            for m in re.finditer(r"\b([A-Z][a-z]{3,}(?:\s[A-Z][a-z]{3,})?)\b", bp):
                term = m.group(1)
                if term.lower() in {"the", "this", "that", "they", "their"}:
                    continue
                if term not in seen:
                    seen.add(term)
                    # Use the surrounding sentence as a crude definition.
                    glossary.append((term, f"Mentioned in: {bp.strip()[:120]}"))
                if len(glossary) >= 12:
                    return glossary
        if not glossary:
            glossary = [("Key concept", "See chapter summaries for details.")]
        return glossary

    # ══════════════════════════════════════════════════════════════════════
    # Assembly
    # ══════════════════════════════════════════════════════════════════════

    def _assemble_markdown(
        self,
        book_title: str,
        chapter_count: int,
        objectives: list[str],
        glossary: list[tuple[str, str]],
        qa_sections: list[tuple[str, list[tuple[str, str]]]],
        self_check: list[str],
        reflection: list[str],
    ) -> str:
        """Assemble the final study-guide markdown document."""
        lines: list[str] = []
        lines.append(f"# Study Guide: {book_title}")
        lines.append("")
        lines.append(
            f"> A structured learning companion synthesised from "
            f"{chapter_count} chapters. Work through the sections in order."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # How to use
        lines.append("## How to Use This Guide")
        lines.append("")
        lines.append("1. **Learning Objectives** — read first; these frame what to focus on.")
        lines.append("2. **Key Terms** — skim to lock in vocabulary.")
        lines.append("3. **Concept Review** — test yourself with the Q&A, grouped by chapter.")
        lines.append("4. **Self-Check** — open-ended questions; answer without notes.")
        lines.append("5. **Further Reflection** — apply the ideas to your own context.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Learning objectives
        lines.append("## Learning Objectives")
        lines.append("")
        lines.append("After working through this guide, you should be able to:")
        lines.append("")
        for i, obj in enumerate(objectives, 1):
            lines.append(f"{i}. {obj}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Key terms glossary
        lines.append("## Key Terms")
        lines.append("")
        lines.append("| Term | Definition |")
        lines.append("|------|------------|")
        for term, defn in glossary:
            # Escape pipe characters inside table cells.
            t = term.replace("|", "\\|")
            d = defn.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| **{t}** | {d} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Concept Q&A
        lines.append("## Concept Review (Q&A)")
        lines.append("")
        if qa_sections:
            for chap, pairs in qa_sections:
                lines.append(f"### {chap}")
                lines.append("")
                for i, (q, a) in enumerate(pairs, 1):
                    lines.append(f"**Q{i}.** {q}")
                    lines.append("")
                    lines.append(f"*A:* {a}")
                    lines.append("")
            lines.append("---")
            lines.append("")
        else:
            lines.append("_No concept Q&A could be generated for this book._")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Self-check
        lines.append("## Self-Check Questions")
        lines.append("")
        lines.append(
            "Answer these without referring back to the material. "
            "If you struggle, revisit the relevant chapter."
        )
        lines.append("")
        for i, q in enumerate(self_check, 1):
            lines.append(f"{i}. {q}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Reflection
        lines.append("## Further Reflection")
        lines.append("")
        lines.append(
            "Use these prompts to connect the material to your own "
            "experience or debate it with others."
        )
        lines.append("")
        for i, r in enumerate(reflection, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

        return "\n".join(lines)
