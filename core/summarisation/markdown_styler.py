"""V0.6.5 — the Markdown Styler's LLM structuring pipeline.

The user's requirement (the exact design, verbatim intent):

    "turning a raw article to markdown (assuming it has different
    headings) cannot be fully deterministic — it needs LLM
    intervention, SO FIRST the LLM must scan the article and find
    heading(s), (if there isn't a heading) generate a fitting heading
    for it, THEN stylize it based on the obsidian style."

The V11.71.0 deterministic regex styler could never satisfy this: its
"heading detector" (short line + Title Case + no terminal punctuation)
missed question-style headings ("How do we check if we're using Steam
Cloud?"), section markers in non-English scripts, and anything in a
noisy copy-paste — so the front-matter title fell back to
"Untitled Note" and the body shipped as a wall of raw text with
excessive blank lines. Exactly the user's report.

This module is the two-phase replacement (deterministic assembly,
LLM-only structure decisions):

  Phase 1 — SCAN (LLM): one call returns STRICT JSON describing the
  article's structure: a real detected title (or a fitting GENERATED
  one when the article has none), a 1–2 sentence tldr, key concepts,
  tags, and the sections (each with its own heading + level + cleaned
  markdown content). The prompt demands the original wording be kept
  — the LLM restructures, it never rewrites.

  Phase 2 — ASSEMBLY (pure Python): the JSON becomes the Obsidian note:
  YAML front-matter (title / date / tags / dir), the ``> [!tldr]
  Summary`` callout, the ``> [!info] Key Concepts`` callout, then the
  sections as ``##`` / ``###`` headings with collapsed blank lines.

Robustness:
  - ``parse_structure`` is lenient: ```json fences stripped, prose
    around the object tolerated, missing optional keys defaulted.
  - ``style_markdown_llm`` retries ONCE with a JSON-only reminder when
    the first reply is unparseable, then returns None — the caller
    (the dialog) falls back to the deterministic path and says so in
    the status line. Never an error dialog for a styling miss.
  - The ``llm_call`` callable is injected (the dialog passes a
    provider-backed closure) — this module has NO provider/thread
    knowledge, so it is unit-testable with a fake.

Content-agnostic (Rule 1): the scan prompt describes structure
detection generically — no vocabulary that favors any topic.
"""

from __future__ import annotations

import datetime
import json
import logging
import re

logger = logging.getLogger(__name__)


# ── Phase 1: the scan prompt ───────────────────────────────────────────

SCAN_PROMPT_TEMPLATE = """You are a document structure analyst. You will be given the raw text of an article that was copy-pasted from a website or a messy source. Your ONLY job is to analyze its STRUCTURE. You never write new content.

TASKS:
1. Find the article's real title if one is detectable (a visible heading, an opening title line, or an obvious topic statement). If the article has NO detectable title, WRITE a fitting title for it (short, descriptive, in the article's own language).
2. Scan the article body and identify its section headings — the lines (or short paragraphs) that act as section breaks. A heading may be a question, a short imperative line, a bolded fragment, or a standalone short line that introduces a new topic. If the article has NO internal headings, treat its paragraphs as a small number of logical sections and give each a fitting heading.
3. For every section, carry the article's own text into that section's content — keep the original wording. You may clean formatting (fix broken lines, collapse blank runs, turn list-shaped content into markdown bullets), but you NEVER add facts, examples or opinions, and you never summarize or shorten the body text.
4. Extract a 1-2 sentence TL;DR of what the article is about.
5. Extract 3-6 key concepts (the article's own important terms/names).
6. Produce 3-6 lowercase tags for the note.

OUTPUT — return ONLY a JSON object, no prose before or after, in this exact shape:
{{
  "title": "string",
  "is_rtl": false,
  "tldr": "string",
  "key_concepts": ["string", "string"],
  "tags": ["string", "string"],
  "sections": [
    {{"heading": "string", "level": 2, "content": "string"}}
  ]
}}

Rules for the JSON:
- "level" is 2 for main sections, 3 for subsections.
- "content" is markdown: paragraphs separated by blank lines, "- " bullets for list-shaped content.
- "is_rtl" is true when the article's script reads right-to-left (e.g. Persian, Arabic, Hebrew).
- Keep every string in the article's own language.

ARTICLE:
<<<ARTICLE
{article}
ARTICLE"""


REPAIR_PROMPT_SUFFIX = """

Your previous reply was not parseable JSON. Reply AGAIN with ONLY the JSON object — no prose, no code fences, no explanation."""


def build_scan_prompt(text: str, *, repair: bool = False) -> str:
    """Build the structure-scan prompt for the article text."""
    prompt = SCAN_PROMPT_TEMPLATE.format(article=text)
    if repair:
        prompt += REPAIR_PROMPT_SUFFIX
    return prompt


# ── Phase 1b: lenient JSON parsing ─────────────────────────────────────


def parse_structure(raw: str) -> dict | None:
    """Parse the LLM's scan reply into the structure dict.

    Lenient by design (models wrap JSON in fences/prose):
      - strips ``` / ```json fences
      - finds the outermost ``{ ... }`` block
      - validates the minimal contract (title + non-empty sections list)
      - defaults the optional keys (is_rtl, tldr, key_concepts, tags)

    Returns None when nothing parseable is found — the caller retries
    or falls back. Never raises.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # Strip code fences (```json ... ``` or ``` ... ```).
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    # Find the outermost {...} block.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        data = json.loads(candidate)
    except Exception:
        # One more try: trailing commas are the classic LLM JSON slip.
        try:
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            data = json.loads(fixed)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None

    title = str(data.get("title") or "").strip()
    sections_raw = data.get("sections")
    if not title or not isinstance(sections_raw, list) or not sections_raw:
        return None

    sections: list[dict] = []
    for i, s in enumerate(sections_raw):
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading") or "").strip()
        content = str(s.get("content") or "").strip()
        if not heading and not content:
            continue
        try:
            level = int(s.get("level") or 2)
        except (TypeError, ValueError):
            level = 2
        level = 2 if level < 2 else (3 if level > 3 else level)
        if not heading:
            heading = f"Section {i + 1}"
        sections.append({"heading": heading, "level": level, "content": content})

    if not sections:
        return None

    def _str_list(key: str, limit: int) -> list[str]:
        val = data.get(key)
        if not isinstance(val, list):
            return []
        out = []
        for v in val:
            v = str(v or "").strip()
            if v:
                out.append(v)
            if len(out) >= limit:
                break
        return out

    is_rtl = bool(data.get("is_rtl", False))
    if isinstance(data.get("is_rtl"), str):
        is_rtl = data.get("is_rtl", "").strip().lower() in ("true", "yes", "1")

    return {
        "title": title,
        "is_rtl": is_rtl,
        "tldr": str(data.get("tldr") or "").strip(),
        "key_concepts": _str_list("key_concepts", 8),
        "tags": [t.lower().lstrip("#").replace(" ", "-") for t in _str_list("tags", 8)],
        "sections": sections,
    }


# ── Phase 2: deterministic Obsidian assembly ──────────────────────────


def _clean_section_content(content: str) -> str:
    """Collapse blank-line runs + strip trailing whitespace (the user's
    "lots of spaces" report) — content text otherwise untouched."""
    lines = [ln.rstrip() for ln in content.split("\n")]
    out: list[str] = []
    blank_run = 0
    for ln in lines:
        if not ln.strip():
            blank_run += 1
            if blank_run <= 1:
                out.append("")
        else:
            blank_run = 0
            out.append(ln)
    cleaned = "\n".join(out).strip()
    return cleaned + "\n" if cleaned else ""


def assemble_obsidian_note(
    structure: dict,
    *,
    include_tldr: bool = True,
    include_concepts: bool = True,
    include_tags: bool = True,
) -> str:
    """Assemble the final Obsidian note from a validated structure dict.

    Layout (the house Obsidian style):
      ---
      title / date / tags [/ dir: rtl]
      ---
      > [!tldr] Summary
      > …
      ---
      > [!info] Key Concepts
      > - **…**
      ---
      ## Section
      content…
      ### Subsection
      …
    """
    parts: list[str] = []

    # Front-matter: always ships the title + date (tags/dir optional).
    fm = ["---"]
    title = structure["title"].replace("\\", "\\\\").replace('"', '\\"')
    fm.append(f'title: "{title}"')
    fm.append(f"date: {datetime.date.today().isoformat()}")
    tags = structure.get("tags") or []
    if include_tags and tags:
        fm.append(f"tags: [{', '.join(tags)}]")
    if structure.get("is_rtl"):
        fm.append("dir: rtl")
    fm.append("---")
    parts.append("\n".join(fm))

    # TLDR callout.
    if include_tldr and structure.get("tldr"):
        tldr = structure["tldr"].strip()
        parts.append(f"> [!tldr] Summary\n> {tldr}\n\n---")

    # Key Concepts callout.
    if include_concepts and structure.get("key_concepts"):
        concepts = "\n".join(f"> - **{c}**" for c in structure["key_concepts"][:6])
        parts.append(f"> [!info] Key Concepts\n{concepts}\n\n---")

    # Sections.
    body: list[str] = []
    for sec in structure["sections"]:
        prefix = "#" * int(sec.get("level", 2))
        body.append(f"{prefix} {sec['heading'].strip()}\n")
        content = _clean_section_content(sec.get("content", ""))
        if content:
            body.append(content)
    if body:
        parts.append("\n".join(body))

    note = "\n\n".join(p for p in parts if p and p.strip())
    return note.rstrip() + "\n"


# ── Orchestration ──────────────────────────────────────────────────────


def style_markdown_llm(
    text: str,
    llm_call,
    *,
    include_tldr: bool = True,
    include_concepts: bool = True,
    include_tags: bool = True,
) -> tuple[str, dict] | None:
    """Run the full LLM structuring pipeline over ``text``.

    ``llm_call(prompt: str) -> str | None`` is injected by the caller
    (the dialog's provider-backed closure). Returns ``(note, structure)``
    on success, or None when both attempts fail to produce a valid
    structure — the caller then falls back to the deterministic styler.

    One repair retry: an unparseable first reply gets a JSON-only
    reminder (models drift; the reminder is cheap and effective).
    """
    if not text or not text.strip():
        return None

    raw = llm_call(build_scan_prompt(text))
    structure = parse_structure(raw or "")
    if structure is None:
        logger.info("markdown styler: first scan unparseable — retrying with JSON reminder")
        raw2 = llm_call(build_scan_prompt(text, repair=True))
        structure = parse_structure(raw2 or "")
    if structure is None:
        logger.warning("markdown styler: LLM scan failed twice — falling back to deterministic")
        return None

    note = assemble_obsidian_note(
        structure,
        include_tldr=include_tldr,
        include_concepts=include_concepts,
        include_tags=include_tags,
    )
    return note, structure
