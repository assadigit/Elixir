"""V0.6.22 (W-h1): pre-built podcast script templates.

Why this exists
---------------
The wizard's flow is: click "Generate Script" → the LLM produces a
script → the operator edits it → click "Generate Podcast". But what
if the operator wants to SKIP the LLM step and just write a script
by hand? Before V0.6.22, the only way was to type the whole thing
into the QPlainTextEdit from scratch — no starting point, no
structure to follow.

The wizard has an "Import Script" button (loads a JSON file), so the
operator COULD write a JSON file by hand, but that's tedious (the
JSON schema has host + text + source_ref + segment_type per line).
A template system gives the operator a starting point: pick a
template, get a valid ScriptResult with placeholder text, edit the
text in place.

This module provides 6 templates covering the common podcast formats:

  1. ``lecture_intro`` — a 3-line lecture-mode template (1 host):
       Host A: intro / content / conclusion.
  2. ``conversational_intro`` — a 3-line conversational template (2 hosts):
       Host A: intro / Host B: response / Host A: conclusion.
  3. ``qa_format`` — a 4-line Q&A template:
       Host A: question / Host B: answer / Host A: follow-up / Host B: answer.
  4. ``interview`` — a 5-line interview template:
       Host A: intro / Host B: question / Host A: answer / Host B: follow-up
       / Host A: conclusion.
  5. ``summary_only`` — a 1-line lecture template (just a summary).
  6. ``deep_dive`` — a 6-line conversational deep-dive template.

Each template is a ``ScriptTemplate`` dataclass with:
  - ``name`` — the registry key (e.g., "lecture_intro").
  - ``description`` — one-line description for the --help listing.
  - ``mode`` — "lecture" or "conversational" (determines Host B usage).
  - ``script`` — the ScriptResult with placeholder text.

The placeholder text uses ``[BRACKETED_HINTS]`` so the operator can
see at a glance which fields need filling (e.g., "[INTRO: 1-2 sentences
introducing the topic]"). The hints are deliberately short — the
operator replaces them with real content.

Public API:
  - ``TEMPLATES`` — the registry dict {name: ScriptTemplate}.
  - ``get_template(name)`` — get a template's ScriptResult by name
    (raises KeyError if not found; the CLI catches this).
  - ``list_templates()`` — list all templates in registration order.
  - ``format_templates_for_display()`` — multi-line listing for the
    CLI's ``templates`` subcommand.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.podcast.script_generator import ScriptLine, ScriptResult


@dataclass
class ScriptTemplate:
    """One pre-built podcast script template.

    ``name`` is the registry key (e.g., "lecture_intro"). ``description``
    is a one-line description for the --help listing. ``mode`` is
    "lecture" or "conversational". ``script`` is the ScriptResult with
    placeholder text the operator replaces.
    """

    name: str
    description: str
    mode: str  # "lecture" or "conversational"
    script: ScriptResult
    estimated_lines: int = 0  # populated by _build; for the --help listing


# ── Template builders ────────────────────────────────────────────────────────


def _line(host: str, text: str, segment_type: str, source_ref: str = "") -> ScriptLine:
    """Shortcut to build a ScriptLine with a source_ref."""
    return ScriptLine(host=host, text=text, source_ref=source_ref, segment_type=segment_type)


def _template_lecture_intro() -> ScriptTemplate:
    """Template 1: a 3-line lecture-mode template (1 host)."""
    return ScriptTemplate(
        name="lecture_intro",
        description="3-line lecture (1 host): intro / content / conclusion.",
        mode="lecture",
        estimated_lines=3,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[INTRO: 1-2 sentences introducing the topic and why it matters.]",
                    "intro",
                    "intro",
                ),
                _line(
                    "A",
                    "[CONTENT: 3-5 sentences explaining the main point with an example.]",
                    "content",
                    "content",
                ),
                _line(
                    "A",
                    "[CONCLUSION: 1 sentence summarizing + a question for the listener.]",
                    "conclusion",
                    "conclusion",
                ),
            ],
            title="Lecture Podcast (Template)",
        ),
    )


def _template_conversational_intro() -> ScriptTemplate:
    """Template 2: a 3-line conversational template (2 hosts)."""
    return ScriptTemplate(
        name="conversational_intro",
        description="3-line conversational (2 hosts): intro / response / conclusion.",
        mode="conversational",
        estimated_lines=3,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[HOST A INTRO: 1-2 sentences introducing the topic.]",
                    "intro",
                    "intro",
                ),
                _line(
                    "B",
                    "[HOST B RESPONSE: 1-2 sentences reacting to A's intro.]",
                    "content",
                    "content",
                ),
                _line(
                    "A",
                    "[HOST A CONCLUSION: 1 sentence wrapping up + a teaser.]",
                    "conclusion",
                    "conclusion",
                ),
            ],
            title="Conversational Podcast (Template)",
        ),
    )


def _template_qa_format() -> ScriptTemplate:
    """Template 3: a 4-line Q&A template (Host A asks, Host B answers)."""
    return ScriptTemplate(
        name="qa_format",
        description="4-line Q&A: A asks / B answers / A follows up / B answers.",
        mode="conversational",
        estimated_lines=4,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[HOST A QUESTION 1: Ask a clear, specific question about the topic.]",
                    "intro",
                    "q1",
                ),
                _line(
                    "B",
                    "[HOST B ANSWER 1: 2-3 sentences answering the question with an example.]",
                    "content",
                    "a1",
                ),
                _line(
                    "A",
                    "[HOST A FOLLOW-UP: A related question or request for clarification.]",
                    "content",
                    "q2",
                ),
                _line(
                    "B",
                    "[HOST B ANSWER 2: 2-3 sentences answering the follow-up.]",
                    "conclusion",
                    "a2",
                ),
            ],
            title="Q&A Podcast (Template)",
        ),
    )


def _template_interview() -> ScriptTemplate:
    """Template 4: a 5-line interview template."""
    return ScriptTemplate(
        name="interview",
        description="5-line interview: A intro / B question / A answer / B follow-up / A conclusion.",
        mode="conversational",
        estimated_lines=5,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[HOST A INTRO: Welcome the guest + introduce the topic.]",
                    "intro",
                    "intro",
                ),
                _line(
                    "B",
                    "[GUEST QUESTION: The guest asks a question about the topic.]",
                    "content",
                    "q1",
                ),
                _line(
                    "A",
                    "[HOST A ANSWER: 2-3 sentences answering the guest's question.]",
                    "content",
                    "a1",
                ),
                _line(
                    "B",
                    "[GUEST FOLLOW-UP: A deeper question building on the answer.]",
                    "content",
                    "q2",
                ),
                _line(
                    "A",
                    "[HOST A CONCLUSION: Thank the guest + wrap up the topic.]",
                    "conclusion",
                    "conclusion",
                ),
            ],
            title="Interview Podcast (Template)",
        ),
    )


def _template_summary_only() -> ScriptTemplate:
    """Template 5: a 1-line lecture template (just a summary)."""
    return ScriptTemplate(
        name="summary_only",
        description="1-line lecture: just a summary (good for very short content).",
        mode="lecture",
        estimated_lines=1,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[SUMMARY: 2-3 sentences summarizing the key point of the source material.]",
                    "intro",
                    "summary",
                ),
            ],
            title="Summary Podcast (Template)",
        ),
    )


def _template_deep_dive() -> ScriptTemplate:
    """Template 6: a 6-line conversational deep-dive template."""
    return ScriptTemplate(
        name="deep_dive",
        description="6-line conversational deep-dive: intro / 4-line back-and-forth / conclusion.",
        mode="conversational",
        estimated_lines=6,
        script=ScriptResult(
            lines=[
                _line(
                    "A",
                    "[HOST A INTRO: Introduce the deep-dive topic + what listeners will learn.]",
                    "intro",
                    "intro",
                ),
                _line(
                    "B",
                    "[HOST B POINT 1: First major point or perspective on the topic.]",
                    "content",
                    "point1",
                ),
                _line(
                    "A",
                    "[HOST A REACT: React to B's point + add a detail or counterexample.]",
                    "content",
                    "react1",
                ),
                _line(
                    "B",
                    "[HOST B POINT 2: Second major point, building on the first.]",
                    "content",
                    "point2",
                ),
                _line(
                    "A",
                    "[HOST A SYNTHESIZE: Synthesize the two points + draw a conclusion.]",
                    "content",
                    "synthesis",
                ),
                _line(
                    "B",
                    "[HOST B OUTRO: Wrap up + tease the next episode.]",
                    "conclusion",
                    "outro",
                ),
            ],
            title="Deep Dive Podcast (Template)",
        ),
    )


# ── The registry ────────────────────────────────────────────────────────────

# Order matters — the --help listing + the wizard's "New from template"
# dropdown show templates in this order. Most-useful first.
TEMPLATES: dict[str, ScriptTemplate] = {}


def _register(template: ScriptTemplate) -> ScriptTemplate:
    """Register a template in TEMPLATES (internal helper)."""
    TEMPLATES[template.name] = template
    return template


# Register all six templates at import time.
_register(_template_lecture_intro())
_register(_template_conversational_intro())
_register(_template_qa_format())
_register(_template_interview())
_register(_template_summary_only())
_register(_template_deep_dive())


# ── Public API ───────────────────────────────────────────────────────────────


def get_template(name: str) -> ScriptResult:
    """Get a template's ScriptResult by name.

    Args:
        name: the template name (e.g., "lecture_intro").

    Returns:
        A fresh ScriptResult (the caller can mutate it without
        affecting the registry — the lines are new ScriptLine objects).

    Raises:
        KeyError: if the name isn't in TEMPLATES.
    """
    if name not in TEMPLATES:
        available = ", ".join(sorted(TEMPLATES.keys()))
        raise KeyError(f"Unknown template name: {name!r}. Available: {available}.")
    template = TEMPLATES[name]
    # Return a FRESH ScriptResult with new ScriptLine objects so the
    # caller can mutate it without affecting the registry.
    return ScriptResult(
        lines=[
            ScriptLine(
                host=ln.host,
                text=ln.text,
                source_ref=ln.source_ref,
                segment_type=ln.segment_type,
            )
            for ln in template.script.lines
        ],
        title=template.script.title,
    )


def list_templates() -> list[ScriptTemplate]:
    """List all templates in registration order."""
    return list(TEMPLATES.values())


def format_templates_for_display(
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format the template list as a multi-line string for the CLI's
    ``templates`` subcommand. Each line:

        lecture_intro           3 lines   lecture          3-line lecture (1 host): intro / content / conclusion.
        conversational_intro   3 lines   conversational  3-line conversational (2 hosts): intro / response / conclusion.
        ...

    The name is left-padded to the longest name; the line count + mode
    are in fixed-width columns for alignment.
    """
    if not TEMPLATES:
        msg = "⚠️ No templates registered."
        if log:
            log(msg, "WARNING")
        return msg

    parts: list[str] = []
    parts.append("📝 Available Podcast Script Templates")
    parts.append("═" * 60)
    # Compute the column widths.
    name_width = max(len(name) for name in TEMPLATES)
    parts.append(f"{'NAME':<{name_width}}  {'LINES':>5}  {'MODE':<15}  DESCRIPTION")
    parts.append("-" * (name_width + 5 + 15 + 4 + 40))
    for template in TEMPLATES.values():
        line = (
            f"{template.name:<{name_width}}  "
            f"{template.estimated_lines:>5}  "
            f"{template.mode:<15}  "
            f"{template.description}"
        )
        parts.append(line)
    parts.append("")
    parts.append(
        "Use `python -m core.podcast.cli templates --name <NAME> --out <FILE>` "
        "to write a template to a JSON file."
    )
    out = "\n".join(parts)
    if log:
        for line in out.split("\n"):
            log(line, "INFO")
    return out
