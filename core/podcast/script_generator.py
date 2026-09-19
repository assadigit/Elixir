"""V11.37.0: Podcast script generator with deterministic coverage.

The anti-hallucination system has THREE layers:

1. **Constrained generation prompt** — the LLM is told to ONLY use source
   material, with each line tagged with a source_ref (which bullet it covers).

2. **Deterministic coverage verification** — after generation, we check
   that EVERY input bullet point has at least one script line referencing it.
   Bullets are matched by number (bullet N must be referenced by at least
   one line with source_ref="bullet N"). This is 100% deterministic — no
   semantic similarity, no LLM judgment.

3. **Forced gap-fill** — if any bullet is uncovered after 2 retries, we
   programmatically insert a template segment for that bullet. The model
   CANNOT skip a bullet — we force coverage as a last resort.

Structure: intro → content (one segment per bullet) → conclusion.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────


@dataclass
class ScriptLine:
    """One line of dialogue in the podcast script."""

    host: str  # "A" or "B"
    text: str
    source_ref: str  # e.g. "bullet 1", "bullet 3", "intro", "conclusion"
    segment_type: str  # "intro", "content", "conclusion"


@dataclass
class ScriptResult:
    """The generated podcast script + coverage info."""

    lines: list[ScriptLine] = field(default_factory=list)
    bullets_input: list[str] = field(default_factory=list)
    bullets_covered: list[int] = field(default_factory=list)
    bullets_missing: list[int] = field(default_factory=list)
    coverage_pct: float = 0.0
    retries: int = 0
    forced_segments: int = 0  # how many segments were force-inserted
    error: str | None = None
    title: str = ""  # V11.51.0: LLM-generated title for the podcast

    def to_dialogue_text(self) -> str:
        """Render as readable dialogue text."""
        parts = []
        for line in self.lines:
            prefix = f"[Host {line.host}]" if line.host in ("A", "B") else "[Host]"
            parts.append(f"{prefix} {line.text}")
        return "\n\n".join(parts)

    def to_json(self) -> str:
        """Render as JSON for editing/saving."""
        return json.dumps(
            {
                "lines": [
                    {
                        "host": ln.host,
                        "text": ln.text,
                        "source_ref": ln.source_ref,
                        "segment_type": ln.segment_type,
                    }
                    for ln in self.lines
                ],
                "coverage_pct": self.coverage_pct,
                "bullets_covered": self.bullets_covered,
                "bullets_missing": self.bullets_missing,
            },
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> ScriptResult:
        """V11.49.0: Reconstruct a ScriptResult from a JSON string.

        Used by the podcast maker's Import Script button.
        Also accepts JSONL (one object per line) for flexibility.
        """
        import json as _json

        try:
            data = _json.loads(json_str)
        except _json.JSONDecodeError:
            # Try JSONL — parse each line as a standalone object
            data = []
            for raw in json_str.strip().split("\n"):
                raw = raw.strip().rstrip(",").strip()
                if not raw.startswith("{"):
                    continue
                try:
                    data.append(_json.loads(raw))
                except _json.JSONDecodeError:
                    continue
            if not data:
                raise
        if isinstance(data, list):
            # Raw array of line objects
            line_objs = data
            meta = {}
        elif isinstance(data, dict):
            line_objs = data.get("lines", [])
            meta = data
        else:
            raise ValueError("Expected a JSON array or object with 'lines'")

        lines = []
        for obj in line_objs:
            if not isinstance(obj, dict):
                continue
            text_val = obj.get("text", "").strip()
            if not text_val:
                continue
            # V11.54.0: strip [Host A] prefix that LLMs sometimes include
            text_val = _strip_host_prefix(text_val)
            if not text_val:
                continue
            lines.append(
                ScriptLine(
                    host=str(obj.get("host", "A")).strip().upper()[:1] or "A",
                    text=text_val,
                    source_ref=str(obj.get("source_ref", "")).strip().lower(),
                    segment_type=str(obj.get("segment_type", "content")).strip(),
                )
            )
        return cls(
            lines=lines,
            bullets_input=meta.get("bullets_input", []),
            bullets_covered=meta.get("bullets_covered", []),
            bullets_missing=meta.get("bullets_missing", []),
            coverage_pct=meta.get("coverage_pct", 0.0),
        )


# ── Deterministic bullet extraction ────────────────────────────────────


def extract_bullets(text: str) -> list[str]:
    """Extract bullet points from text (deterministic, no LLM).

    Handles:
    - Markdown bullets: "- item", "* item", "+ item"
    - Numbered: "1. item", "1) item"
    - Plain text paragraphs (split on double-newline)
    """
    lines = text.strip().split("\n")
    bullets = []
    current_bullet = ""

    for line in lines:
        stripped = line.strip()
        # Markdown bullet or numbered list
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            if current_bullet:
                bullets.append(current_bullet.strip())
            # Remove the bullet marker
            current_bullet = re.sub(r"^[-*+]\s+", "", stripped)
            current_bullet = re.sub(r"^\d+[.)]\s+", "", current_bullet)
        elif stripped and current_bullet:
            # Continuation of the current bullet
            current_bullet += " " + stripped
        elif not stripped and current_bullet:
            # Empty line — flush
            bullets.append(current_bullet.strip())
            current_bullet = ""
        elif stripped and not current_bullet:
            # Plain text (no bullet marker) — treat as a bullet
            current_bullet = stripped

    if current_bullet:
        bullets.append(current_bullet.strip())

    # Filter out empty/too-short bullets
    return [b for b in bullets if len(b) > 5]


# ── Text pre-processing ────────────────────────────────────────────────


def preprocess_source_text(text: str) -> str:
    """Pre-process raw text into clean markdown for the LLM.

    V11.37.2: This stage runs BEFORE bullet extraction and LLM script
    generation. It normalizes the input so the LLM has an easier time:

    1. Strip HTML tags (if pasted from a web page)
    2. Normalize whitespace (multiple blank lines → one)
    3. Detect and declare headings (lines that look like titles)
    4. Normalize bullet markers (•, ‣, ▪ → -)
    5. Remove page numbers, footers, headers
    6. Merge broken sentences (line ends without punctuation)
    7. Add a "# Source Material" heading if none exists
    """
    import re

    # 1. Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 2. Normalize whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 3. Normalize bullet markers
    text = re.sub(r"^[•‣▪◦○●]\s*", "- ", text, flags=re.MULTILINE)

    # 4. Remove page numbers (standalone numbers on a line)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # 5. Remove common headers/footers
    text = re.sub(r"^\s*(?:Page|Pg|P\.)\s*\d+\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(
        r"^\s*(?:©|Copyright|All rights reserved).*$", "", text, flags=re.MULTILINE | re.IGNORECASE
    )

    # 6. Detect headings — short lines (< 80 chars) with no ending punctuation
    # that are followed by a blank line or content. Add # if not already markdown.
    lines = text.split("\n")
    processed_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            processed_lines.append(line)
            continue
        # Skip if already a markdown heading
        if stripped.startswith("#"):
            processed_lines.append(line)
            continue
        # Skip if it's a bullet
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            processed_lines.append(line)
            continue
        # Detect heading: short, no terminal punctuation, title-case or ALL CAPS
        is_short = len(stripped) < 80
        no_terminal = not re.search(r"[.!?:,;]$", stripped)
        has_caps = stripped == stripped.upper() or re.match(r"^[A-Z]", stripped)
        # Look ahead: next non-empty line should be content (not another heading)
        next_is_content = False
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j].strip()
            if nxt:
                next_is_content = len(nxt) > 20 or re.match(r"^[-*+]\s+", nxt)
                break
        if is_short and no_terminal and has_caps and next_is_content:
            processed_lines.append(f"## {stripped}")
        else:
            processed_lines.append(line)

    text = "\n".join(processed_lines)

    # 7. Add a top-level heading if none exists
    if not re.search(r"^#\s+", text, re.MULTILINE):
        text = "# Source Material\n\n" + text

    # 8. Final cleanup
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Tone profiles ──────────────────────────────────────────────────────

TONE_PROFILES = {
    "academic": {
        "desc": "Formal, precise, citation-style",
        "instruction": "Use formal academic language. Be precise and cite which bullet point you're discussing.",
    },
    "inspiring": {
        "desc": "Motivational, big-picture",
        "instruction": "Be inspiring and motivational. Connect each point to the bigger picture. Use uplifting language.",
    },
    "casual": {
        "desc": "Friendly, everyday language",
        "instruction": "Be casual and friendly, like two friends chatting. Use everyday language and conversational tone.",
    },
    "journalistic": {
        "desc": "NPR/BBC style, neutral",
        "instruction": "Use a journalistic NPR/BBC style. Neutral, informative, well-structured. Ask probing questions.",
    },
    "energetic": {
        "desc": "Fast-paced, enthusiastic",
        "instruction": "Be energetic and enthusiastic. Fast-paced delivery. Use exclamation points sparingly but show excitement.",
    },
    "storytelling": {
        "desc": "Narrative, anecdotal",
        "instruction": "Use a storytelling approach. Weave the points into a narrative. Use anecdotes and examples from the source.",
    },
}

# Qwythos-compatible temperature ranges (from settings.py model_temperatures)
# Qwythos: min=0.6, max=0.8, recommended=0.7
# For podcasts we want MORE creativity, so we use the upper end.
TEMPERATURE_PROFILES = {
    "conservative": 0.6,  # Qwythos min — safe, predictable
    "balanced": 0.7,  # Qwythos recommended
    "creative": 0.8,  # Qwythos max — most creative within safe range
    "very_creative": 0.9,  # Slightly above Qwythos max (for non-Qwythos models)
}


# ── Prompt builders ────────────────────────────────────────────────────


def _build_lecture_prompt(
    bullets: list[str],
    tone: str,
    temperature_label: str,
    language: str,
) -> str:
    """Build the prompt for lecture mode (1 host)."""
    tone_profile = TONE_PROFILES.get(tone, TONE_PROFILES["casual"])
    bullets_text = "\n".join(f"[BULLET {i + 1}] {b}" for i, b in enumerate(bullets))
    lang_instruction = ""
    if language == "fa":
        lang_instruction = "\n\nIMPORTANT: Write the ENTIRE script in Persian (Farsi). All dialogue must be in Farsi."

    return f"""You are creating a podcast script for a SINGLE HOST (lecture format).

SOURCE MATERIAL — these are the bullet points you MUST cover. EVERY single
bullet point MUST appear in your script. You may NOT skip any bullet point.
Do not add any facts, examples, or details that are not in the source.

{bullets_text}

TONE: {tone_profile["desc"]}
{tone_profile["instruction"]}

HUMAN CHARACTERISTICS — make this sound like a REAL person talking, not a robot:
- Use filler words naturally: "um", "uh", "well", "so", "I mean", "you know"
- Add thinking pauses: "Let me think... [pause]", "Hmm... [pause]"
- Use contractions: "don't" not "do not", "gonna" not "going to"
- Add breath markers between long thoughts: "[breath]"
- Use colloquialisms: "kinda", "sorta", "basically", "the thing is"
- Show genuine reactions: "Oh wow", "Honestly?", "Here's the thing"
- Use dramatic pauses for emphasis: "And then... [pause] everything changed."
- Trail off sometimes: "...if that makes sense"
- Self-correct: "It's like... actually, it IS like that"
- Add "[laugh]" when something is amusing
- Use rhetorical questions: "Makes you think, right?"

STRUCTURE:
1. INTRO: Hook the listener, introduce the topic (2-3 lines)
2. CONTENT: For EACH bullet point (1 through {len(bullets)}), create 1-2 lines
   explaining it. You MUST cover every single bullet.
3. CONCLUSION: Key takeaways + closing thought (2-3 lines)

OUTPUT FORMAT — output ONLY a JSON array, no markdown, no explanation:
[
  {{"host": "A", "text": "...", "source_ref": "intro", "segment_type": "intro"}},
  {{"host": "A", "text": "...", "source_ref": "bullet 1", "segment_type": "content"}},
  {{"host": "A", "text": "...", "source_ref": "bullet 2", "segment_type": "content"}},
  ...
  {{"host": "A", "text": "...", "source_ref": "conclusion", "segment_type": "conclusion"}}
]

RULES:
- source_ref MUST be "intro", "bullet 1", "bullet 2", ..., "conclusion"
- You MUST have at least one line with source_ref="bullet N" for EVERY N from 1 to {len(bullets)}
- Do NOT invent facts not in the source
- Keep each line to 1-3 sentences (natural speech length)
- Embed vocal cues DIRECTLY in the text: [pause], [breath], [laugh], [hmm]
- Use filler words sparingly (1-2 per line max) — don't overdo it
- Creativity level: {temperature_label}{lang_instruction}"""


def _build_conversational_prompt(
    bullets: list[str],
    tone: str,
    temperature_label: str,
    language: str,
) -> str:
    """Build the prompt for conversational mode (2 hosts)."""
    tone_profile = TONE_PROFILES.get(tone, TONE_PROFILES["casual"])
    bullets_text = "\n".join(f"[BULLET {i + 1}] {b}" for i, b in enumerate(bullets))
    lang_instruction = ""
    if language == "fa":
        lang_instruction = "\n\nIMPORTANT: Write the ENTIRE script in Persian (Farsi). All dialogue must be in Farsi."

    return f"""You are creating a podcast script for TWO HOSTS (Host A and Host B).

SOURCE MATERIAL — these are the bullet points you MUST cover. EVERY single
bullet point MUST appear in your script. You may NOT skip any bullet point.

CRITICAL ANTI-HALLUCINATION RULE: You may ONLY use facts, names, numbers,
and examples that appear EXACTLY in the source material below. You may NOT:
- Invent company names (e.g. "Cursor", "OpenAI") unless they appear in the source
- Invent dollar amounts (e.g. "$60B") unless they appear in the source
- Invent people's names (e.g. "Elon") unless they appear in the source
- Add examples or analogies not present in the source
- Paraphrase the source into facts it doesn't state
You MAY: rephrase for conversational tone, add filler words, add questions,
add reactions — but the SUBSTANTIVE CONTENT must come only from the source.

CRITICAL CONVERSATIONAL RULE — DO NOT READ THE SOURCE ALOUD:
- You must EXPLAIN the concepts in your OWN WORDS, not copy-paste the source text.
- BAD: "The entire world—markets, governments, militaries, companies, people—are all trying to make sense of AI in terms of the recent past's production efficiencies."
- GOOD: "So basically, everyone — governments, companies, even the military — they're all looking at AI through the lens of what's already happened. But that's the wrong lens."
- BAD: "There are many algorithmic OOMs left to go in the production of intelligence"
- GOOD: "There's still a LOT of room for AI to get smarter — like, orders of magnitude smarter. We're not near the ceiling."
- If a term needs explaining (OOMs, METR, Move 37), EXPLAIN IT briefly for the listener.
- Keep numbers as DIGITS: write "2022" not "two thousand twenty-two", "100 million" not "one hundred million"
- Do NOT spell out years, quantities, or measurements — keep them as digits

{bullets_text}

TONE: {tone_profile["desc"]}
{tone_profile["instruction"]}

HUMAN CHARACTERISTICS — make this sound like a REAL, ENGAGING conversation:
- Use filler words SPARINGLY (max 1-2 per line): "um", "well", "so", "I mean"
- Use contractions: "don't" not "do not", "gonna" not "going to"
- Show GENUINE reactions to surprising things:
  * "Wooow!" "Whaaat?" "Are you kidding me?!" "That's insane!"
  * "No way!" "Hold on — say that again?" "Wait, really?"
  * "Dude." "That's wild." "That blows my mind."
- Do NOT repeat the same reaction more than once in the entire script
- Do NOT use "Oh, that's good" or "Hmm." as standalone lines — they add nothing
- Sometimes INTERRUPT each other: "Wait, can I—" "Sorry, go on."
- Show personality — be curious, skeptical, amazed, or amused
- Ask questions to co-host: "Does that make sense?" "What do you think?"
- Show mild disagreement: "Hmm, I'm not sure about that part"
- Use colloquialisms: "kinda", "sorta", "basically", "the thing is"

VOCAL CUES — use SPARINGLY (max 1 per line, many lines should have NONE):
- [pause] — only for dramatic effect, not every line
- [breath] — only before long clauses, not every line
- [laugh] — only when something is genuinely amusing
- Do NOT put [pause 0.5s] after every sentence — it sounds robotic

NO SLOP OPENERS — the FIRST line must be a HOOK:
- FORBIDDEN: "You know," "Hey everyone," "Welcome back," "So today we're..."
- INSTEAD: Start with a bold claim, provocative question, or surprising fact
- Example: "What if I told you we're not even close to the ceiling of what AI can do?"
- Example: "Everyone's pricing in a gradual AI improvement. They're wrong."

STRUCTURE — the podcast MUST follow this exact flow:
1. HOOK (1-2 lines, source_ref="hook", segment_type="intro"):
   Start with a BOLD, attention-grabbing statement or question.
   Host A delivers the hook, Host B reacts with genuine surprise.

2. INTRODUCTION (1-2 lines, source_ref="intro", segment_type="intro"):
   Briefly set up the topic. What are we discussing? Why does it matter?

3. MAIN CONTENT (multiple lines, source_ref="bullet N", segment_type="content"):
   For EACH bullet point (1 through {len(bullets)}), create a short
   dialogue where Host A EXPLAINS the concept (in own words) and Host B
   asks a question or reacts. You MUST cover every single bullet.

4. KEY TAKEAWAYS (2-3 lines, source_ref="takeaways", segment_type="conclusion"):
   Both hosts summarize the 2-3 most important points. Be specific.

5. GOODBYE (1-2 lines, source_ref="goodbye", segment_type="conclusion"):
   A natural, warm sign-off. NOT "thanks for listening" — instead:
   "Go try this. Seriously." or "Share it with someone who needs to hear it."

OUTPUT FORMAT — output ONLY a JSON array, no markdown, no explanation:
[
  {{"host": "A", "text": "...", "source_ref": "hook", "segment_type": "intro"}},
  {{"host": "B", "text": "...", "source_ref": "hook", "segment_type": "intro"}},
  {{"host": "A", "text": "...", "source_ref": "intro", "segment_type": "intro"}},
  {{"host": "B", "text": "...", "source_ref": "bullet 1", "segment_type": "content"}},
  ...
  {{"host": "A", "text": "...", "source_ref": "takeaways", "segment_type": "conclusion"}},
  {{"host": "A", "text": "...", "source_ref": "goodbye", "segment_type": "conclusion"}}
]

RULES:
- source_ref MUST be "hook", "intro", "bullet 1", "bullet 2", ..., "takeaways", "goodbye"
- The FIRST 1-2 lines MUST be source_ref="hook" (attention-grabbing opener)
- You MUST have at least one line with source_ref="bullet N" for EVERY N from 1 to {len(bullets)}
- Alternate hosts naturally (A, B, A, B...) — don't let one host dominate
- Do NOT invent facts, names, numbers, or examples not in the source
- Keep each line to 1-3 sentences (natural speech length)
- EXPLAIN concepts in your own words — do NOT copy-paste source text
- Keep numbers as DIGITS (2022, not "two thousand twenty-two")
- Do NOT repeat the same reaction phrase more than once in the entire script
- Do NOT use [pause] or [breath] more than once every 3 lines
- Creativity level: {temperature_label}{lang_instruction}"""


def _build_gap_fill_prompt(
    bullets: list[str],
    missing_indices: list[int],
    mode: str,
    language: str,
) -> str:
    """Build a gap-fill reprompt for uncovered bullets."""
    missing_text = "\n".join(f"[BULLET {i + 1}] {bullets[i]}" for i in missing_indices)
    host_instruction = (
        "Host A only (lecture mode)" if mode == "lecture" else "Host A and Host B (conversational)"
    )
    lang_instruction = "\nWrite in Persian (Farsi)." if language == "fa" else ""

    return f"""Your previous podcast script MISSED these bullet points. You MUST
cover them now. Do not skip any.

MISSING BULLETS:
{missing_text}

Create podcast lines for EACH missing bullet above. {host_instruction}.
Each bullet MUST get at least one line.

OUTPUT FORMAT — JSON array only:
[
  {{"host": "A", "text": "...", "source_ref": "bullet {missing_indices[0] + 1}", "segment_type": "content"}},
  ...
]

RULES:
- source_ref MUST match the bullet number (e.g. "bullet {missing_indices[0] + 1}")
- Do NOT invent facts — use only the source material above
- Keep each line to 1-3 sentences{lang_instruction}"""


# ── Script parsing & coverage verification ─────────────────────────────


def _parse_script_response(response: str) -> list[ScriptLine]:
    """Parse the LLM's response into ScriptLine objects.

    V11.37.3: robust multi-strategy parser. LLMs often return:
    - Clean JSON array ✅
    - JSON in markdown code fences ```json ... ```
    - JSON with preamble text ("Here's the script:\n[...]")
    - JSON with trailing text
    - Malformed JSON (missing quotes, trailing commas)
    - Plain dialogue text ("Host A: ...\nHost B: ...")
    - Numbered lines ("1. Host A: ...")

    V11.37.4: strip <think>...</think> tags (Qwythos outputs these).

    We try each strategy in order until one works.
    """
    if not response or not response.strip():
        return []

    response = response.strip()

    # V11.37.4: strip <think>...</think> tags (Qwythos thinking output)
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE)
    # Also strip unclosed <think> tags
    response = re.sub(r"<think>.*", "", response, flags=re.DOTALL | re.IGNORECASE)
    response = response.strip()

    # ── Strategy 1: Direct JSON parse ──────────────────────────────
    lines = _try_parse_json(response)
    if lines:
        return lines

    # ── Strategy 1b: JSONL (one JSON object per line, no array) ───
    # V11.49.0: many LLMs return JSONL instead of a JSON array. This
    # must come BEFORE the tagged-lines fallback, otherwise the raw
    # JSON strings end up as line.text and TTS reads them literally.
    lines = _try_parse_jsonl(response)
    if lines:
        return lines

    # ── Strategy 2: Strip markdown code fences and retry ───────────
    fenced = re.sub(r"^```(?:json)?\s*", "", response)
    fenced = re.sub(r"\s*```$", "", fenced)
    if fenced != response:
        lines = _try_parse_json(fenced)
        if lines:
            return lines

    # ── Strategy 3: Extract JSON array from surrounding text ───────
    # Find the first [ and the last ] — extract everything between
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if match:
        lines = _try_parse_json(match.group())
        if lines:
            return lines

    # ── Strategy 4: Fix common JSON errors and retry ───────────────
    fixed = _fix_json_errors(response)
    if fixed != response:
        lines = _try_parse_json(fixed)
        if lines:
            return lines
        # Also try extracting array from fixed text
        match = re.search(r"\[.*\]", fixed, re.DOTALL)
        if match:
            lines = _try_parse_json(match.group())
            if lines:
                return lines

    # ── Strategy 5: Parse as plain dialogue text ───────────────────
    # Handles: "Host A: text", "A: text", "[Host A] text"
    lines = _parse_plain_dialogue(response)
    if lines:
        return lines

    # ── Strategy 6: Parse as numbered/speaker-tagged lines ─────────
    lines = _parse_tagged_lines(response)
    if lines:
        return lines

    # All strategies failed
    return []


def _strip_host_prefix(text: str) -> str:
    """V11.54.0: Remove [Host A]/[Host B]/Host A:/Host B: prefixes from text.

    LLMs sometimes include the speaker label INSIDE the text field:
        {"host": "A", "text": "[Host A] You know that thing..."}
    This strips the prefix so TTS doesn't read "[Host A]" literally.
    """
    if not text:
        return text
    import re as _re

    # Strip [Host A], [Host B], [Host], Host A:, Host B:, A:, B: at the start
    text = _re.sub(
        r"^\s*(?:\[Host\s+[AB]\]\s*|Host\s+[AB]\s*[:\)]\s*|[AB]\s*[:\)]\s*)",
        "",
        text,
        flags=_re.IGNORECASE,
    )
    return text.strip()


def _try_parse_json(text: str) -> list[ScriptLine]:
    """Try to parse text as JSON and convert to ScriptLine objects."""
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    lines = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text_val = item.get("text", "").strip()
        if not text_val:
            continue
        # V11.54.0: strip [Host A] prefix that LLMs sometimes include
        text_val = _strip_host_prefix(text_val)
        if not text_val:
            continue
        lines.append(
            ScriptLine(
                host=str(item.get("host", "A")).strip().upper()[:1] or "A",
                text=text_val,
                source_ref=str(item.get("source_ref", "")).strip().lower(),
                segment_type=str(item.get("segment_type", "content")).strip(),
            )
        )
    return lines


def _try_parse_jsonl(text: str) -> list[ScriptLine]:
    """V11.49.0: Parse JSONL (one JSON object per line, no array wrapper).

    Many LLMs return podcast scripts as JSONL instead of a JSON array:
        {"host": "A", "text": "Welcome...", ...}
        {"host": "B", "text": "Thanks...", ...}

    The existing _try_parse_json fails because json.loads expects a
    single JSON document. This function parses each line independently.

    Also handles the case where objects are separated by commas (but not
    wrapped in []), by stripping trailing commas before parsing.
    """
    text = text.strip()
    if not text:
        return []

    lines = []
    for raw_line in text.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line or not raw_line.startswith("{"):
            continue
        # Strip trailing commas (from pseudo-array without brackets)
        clean = raw_line.rstrip(",").strip()
        if not clean.endswith("}"):
            # Maybe the JSON object spans multiple lines — try accumulating
            # until we find a closing }. But for simple JSONL, each line
            # is a complete object.
            continue
        try:
            obj = json.loads(clean)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        text_val = obj.get("text", "").strip()
        if not text_val:
            continue
        # V11.54.0: strip [Host A] prefix that LLMs sometimes include
        text_val = _strip_host_prefix(text_val)
        if not text_val:
            continue
        lines.append(
            ScriptLine(
                host=str(obj.get("host", "A")).strip().upper()[:1] or "A",
                text=text_val,
                source_ref=str(obj.get("source_ref", "")).strip().lower(),
                segment_type=str(obj.get("segment_type", "content")).strip(),
            )
        )
    return lines


def _fix_json_errors(text: str) -> str:
    """Fix common JSON errors produced by LLMs.

    - Remove trailing commas before ] or }
    - Add missing closing brackets
    - Fix single quotes → double quotes
    - Remove comments (// or /* */)
    - Remove [Host A] / [Host B] prefixes (LLM sometimes adds these)
    - Fix missing array wrapper (if response is just objects, wrap in [])
    """
    # Remove comments
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # V11.37.4: remove [Host A] / [Host B] prefixes that the LLM sometimes
    # adds before JSON objects
    text = re.sub(r"^\s*\[Host\s+[AB]\]\s*", "", text, flags=re.MULTILINE)

    # Fix single quotes → double quotes (only outside of strings)
    text = re.sub(r"'([^']+)':", r'"\1":', text)

    # Remove trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # V11.37.4: if the text looks like multiple JSON objects but isn't
    # wrapped in an array, wrap it
    stripped = text.strip()
    if stripped.startswith("{") and not stripped.startswith("["):
        # Check if there are multiple objects separated by commas/newlines
        # Wrap in array
        text = "[" + stripped + "]"
        # Fix any double-wrapping
        text = text.replace("[{", "[{").replace("}]", "}]")

    # If the text ends without a closing ], try adding it
    stripped = text.rstrip()
    if not stripped.endswith("]") and not stripped.endswith("}"):
        # Count brackets
        opens = text.count("[") - text.count("]")
        if opens > 0:
            text = text + "]" * opens

    return text


def _parse_plain_dialogue(text: str) -> list[ScriptLine]:
    """Parse plain dialogue text as a fallback.

    Handles formats like:
      Host A: Hello and welcome...
      A: Hello and welcome...
      [Host A] Hello and welcome...
      Host A: Hello and welcome...

    V11.37.5: if the captured text looks like JSON (starts with {), extract
    the "text" field from it instead of using the raw JSON as the line text.
    This prevents TTS from reading JSON tags like "source_ref bullet 12".

    Also infers source_ref from context (intro/content/conclusion) based
    on position in the text.
    """
    lines = []
    # Match: optional "Host ", then A or B, then ":" or "]" or newline
    pattern = re.compile(
        r"(?:Host\s+)?([AB])(?:\]?\s*[:\]\n]\s*|\n)(.+?)(?=(?:Host\s+)?[AB](?:\]?\s*[:\]\n])|$)",
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    total = len(matches)
    for i, m in enumerate(matches):
        host = m.group(1).strip().upper()[:1]
        line_text = m.group(2).strip()
        if not line_text or len(line_text) < 5:
            continue

        # V11.37.5: if the captured text is JSON, extract the fields
        if line_text.startswith("{"):
            try:
                obj = json.loads(line_text.rstrip(","))
                # Use the JSON's host if present, otherwise keep the matched host
                if "host" in obj:
                    host = str(obj["host"]).strip().upper()[:1] or host
                line_text = obj.get("text", "").strip()
                source_ref = str(obj.get("source_ref", "")).strip().lower()
                segment_type = str(obj.get("segment_type", "content")).strip()
                if not line_text:
                    continue
                lines.append(
                    ScriptLine(
                        host=host, text=line_text, source_ref=source_ref, segment_type=segment_type
                    )
                )
                continue
            except json.JSONDecodeError:
                # Not valid JSON — treat as plain text
                pass

        # Infer segment type from position
        if i == 0:
            segment_type = "intro"
            source_ref = "intro"
        elif i >= total - 2:
            segment_type = "conclusion"
            source_ref = "conclusion"
        else:
            segment_type = "content"
            source_ref = ""  # unknown — will be caught by coverage check
        lines.append(
            ScriptLine(host=host, text=line_text, source_ref=source_ref, segment_type=segment_type)
        )
    return lines


def _parse_tagged_lines(text: str) -> list[ScriptLine]:
    """Parse numbered or tagged lines as a last resort.

    Handles:
      1. Some text...
      2. Another line...
      - Some text...
    """
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Remove numbering or bullet markers
        cleaned = re.sub(r"^\d+[.)]\s*", "", stripped)
        cleaned = re.sub(r"^[-*+]\s*", "", cleaned)
        if len(cleaned) < 5:
            continue
        lines.append(ScriptLine(host="A", text=cleaned, source_ref="", segment_type="content"))
    return lines if len(lines) >= 2 else []


def verify_coverage(
    lines: list[ScriptLine],
    num_bullets: int,
) -> tuple[list[int], list[int]]:
    """Determine which bullets are covered (deterministic).

    A bullet N is "covered" if at least one line has
    source_ref == "bullet N" (case-insensitive, whitespace-trimmed).

    Returns (covered_indices, missing_indices) — 0-based.
    """
    # Collect all source_refs mentioned in the script
    refs_found = set()
    for line in lines:
        ref = line.source_ref.strip().lower()
        # Normalize: "bullet 1", "Bullet 1", "bullet1" → "bullet 1"
        ref = re.sub(r"\s+", " ", ref)
        refs_found.add(ref)

    covered = []
    missing = []
    for i in range(num_bullets):
        bullet_ref = f"bullet {i + 1}"
        if bullet_ref in refs_found:
            covered.append(i)
        else:
            missing.append(i)

    return covered, missing


# V11.41.0: Deterministic human element injection
# Backchannels, fillers, and pauses inserted AFTER LLM generation to
# guarantee a natural conversational feel even if the LLM forgets.

import random as _random

_BACKCHANNELS = [
    "Yeah.",
    "Right.",
    "Mhm.",
    "Exactly.",
    "Oh?",
    "Hmm.",
    "That's interesting.",
    "Right, right.",
    "Mm-hmm.",
    "For sure.",
]
_FILLERS = ["um", "well", "so", "I mean", "you know", "honestly", "like", "basically"]
_REACTIONS = [
    "Oh wow.",
    "No way.",
    "That's so true.",
    "100%.",
    "Absolutely.",
    "Makes sense.",
    "Oh, that's good.",
    "Wow, okay.",
    "Hmm, interesting.",
    "That hits home.",
]

# V11.52.0: Expanded vocal cues with variable durations
# Each entry: (cue_tag, duration_range_seconds)
# The cue_tag is what appears in the text: [pause 0.7s], [breath], [sigh], etc.
_VOCAL_CUES_EXPANDED = [
    ("[pause 0.3s]", (0.3, 0.3)),  # short pause (comma-level)
    ("[pause 0.5s]", (0.5, 0.5)),  # medium pause (sentence-level)
    ("[pause 0.7s]", (0.7, 0.7)),  # thinking pause
    ("[pause 1.0s]", (1.0, 1.0)),  # dramatic pause
    ("[breath]", (0.3, 0.4)),  # quick breath
    ("[sigh]", (0.6, 0.8)),  # longer exhale
    ("[chuckle]", (0.4, 0.6)),  # short laugh
    ("[hmm]", (0.0, 0.0)),  # word-level (stays in text)
    ("[um]", (0.0, 0.0)),  # word-level (stays in text)
    ("[gasp]", (0.3, 0.4)),  # surprised intake
    ("[throat_clear]", (0.4, 0.5)),  # before speaking
]


def inject_human_elements(
    lines: list[ScriptLine],
    mode: str,
    intensity: float = 0.5,
) -> list[ScriptLine]:
    """V11.41.0/V11.52.0: Inject backchannels, fillers, pauses, and vocal cues.

    V11.52.0: increased default intensity 0.3→0.5, added variable-length
    pauses ([pause 0.3s], [pause 0.7s], [pause 1.0s]), added [sigh],
    [chuckle], [gasp], [throat_clear] cues. Cues are inserted MID-TEXT
    at natural breakpoints (after commas, periods, before long clauses)
    so the TTS engine pauses naturally.

    Args:
        lines: The script lines from the LLM.
        mode: "lecture" or "conversational".
        intensity: 0.0-1.0, probability of injecting an element at each
                   opportunity. 0.5 = 50% chance per opportunity.

    Returns:
        Enhanced lines with human elements.
    """
    rng = _random.Random(42)  # deterministic seed for reproducibility
    enhanced = []

    for i, line in enumerate(lines):
        text = line.text

        # Phase 1: Insert vocal cues at natural breakpoints
        # V11.52.0: insert [pause] after commas/periods, [breath] before
        # long clauses, [sigh]/[chuckle] at emotional moments.
        if rng.random() < intensity:
            text = _insert_vocal_cues_in_text(text, rng)

        # Phase 2a: Add filler word at the start of some lines
        if rng.random() < intensity * 0.4:
            filler = rng.choice(_FILLERS)
            # Don't add if the line already starts with a filler
            if not any(text.lower().startswith(f.lower()) for f in _FILLERS):
                text = f"{filler.capitalize()}, {text[0].lower()}{text[1:]}"

        # Update the line with the enhanced text
        line = ScriptLine(
            host=line.host,
            text=text,
            source_ref=line.source_ref,
            segment_type=line.segment_type,
        )
        enhanced.append(line)

        # Phase 2b: Add backchannel responses (conversational mode only)
        if mode == "conversational" and line.host == "A" and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.host == "B" and rng.random() < intensity * 0.5:
                backchannel = rng.choice(_BACKCHANNELS)
                enhanced.append(
                    ScriptLine(
                        host="B",
                        text=backchannel,
                        source_ref=line.source_ref,
                        segment_type="backchannel",
                    )
                )

        # Phase 2c: Add reaction after content lines
        if line.segment_type == "content" and rng.random() < intensity * 0.35:
            reaction = rng.choice(_REACTIONS)
            reacting_host = "B" if line.host == "A" else "A"
            enhanced.append(
                ScriptLine(
                    host=reacting_host,
                    text=reaction,
                    source_ref=line.source_ref,
                    segment_type="reaction",
                )
            )

    return enhanced


def _insert_vocal_cues_in_text(text: str, rng: _random.Random) -> str:
    """V11.52.0: Insert vocal cues at natural breakpoints in the text.

    Inserts [pause Xs] after commas and periods, [breath] before long
    clauses, and occasionally [sigh], [chuckle], or [gasp] at emotional
    moments. This makes the TTS output sound more natural and human.
    """
    import re as _re

    # Don't over-cue very short lines
    if len(text) < 30:
        return text

    # Insert pauses after commas (30% chance each)
    def _maybe_pause_comma(m):
        if rng.random() < 0.3:
            dur = rng.choice(["0.3", "0.3", "0.5"])
            return f", [pause {dur}s]"
        return m.group(0)

    text = _re.sub(r",", _maybe_pause_comma, text)

    # Insert pauses after sentence-ending punctuation (50% chance)
    def _maybe_pause_sentence(m):
        if rng.random() < 0.5:
            dur = rng.choice(["0.5", "0.5", "0.7", "1.0"])
            return f"{m.group(1)} [pause {dur}s]"
        return m.group(0)

    text = _re.sub(r"([.!?])\s", _maybe_pause_sentence, text)

    # Insert [breath] before long clauses (after "and", "but", "so", "because")
    if rng.random() < 0.3:
        text = _re.sub(
            r"\b(and|but|so|because|which|where|when)\s",
            r"\1 [breath] ",
            text,
            count=1,
            flags=_re.IGNORECASE,
        )

    # Occasionally add [sigh], [chuckle], or [gasp] (10% chance)
    if rng.random() < 0.10:
        cue = rng.choice(["[sigh]", "[chuckle]", "[gasp]"])
        # Insert at a natural point — after the first sentence
        parts = text.split(". ", 1)
        if len(parts) == 2:
            text = parts[0] + f". {cue} " + parts[1]

    # Clean up any double spaces
    text = _re.sub(r"  +", " ", text).strip()
    return text


def strip_vocal_cues(text: str) -> str:
    """V11.41.0/V11.52.0: Remove vocal cue tags from text for TTS generation.

    [pause], [breath], [laugh], [hmm], [sigh], [chuckle], [gasp],
    [throat_clear] are handled by the audio generator (inserting silence
    or words), so they must be stripped from the text passed to the TTS
    engine.

    Returns a tuple of (clean_text, cues) where cues is a list of
    (position, cue_type, duration_seconds) tuples.
    """
    import re

    cues = []

    # Extract [pause X.Ys] or [pause] — variable durations
    for m in re.finditer(r"\[pause\s*(\d*\.?\d*)s?\]", text, re.IGNORECASE):
        duration = float(m.group(1)) if m.group(1) else 0.5
        cues.append((m.start(), "pause", duration))

    # Extract [breath] — 0.3s
    for m in re.finditer(r"\[breath\]", text, re.IGNORECASE):
        cues.append((m.start(), "breath", 0.3))

    # Extract [sigh] — 0.7s (longer exhale)
    for m in re.finditer(r"\[sigh\]", text, re.IGNORECASE):
        cues.append((m.start(), "sigh", 0.7))

    # Extract [chuckle] — 0.5s
    for m in re.finditer(r"\[chuckle\]", text, re.IGNORECASE):
        cues.append((m.start(), "chuckle", 0.5))

    # Extract [gasp] — 0.3s
    for m in re.finditer(r"\[gasp\]", text, re.IGNORECASE):
        cues.append((m.start(), "gasp", 0.3))

    # Extract [throat_clear] — 0.4s
    for m in re.finditer(r"\[throat_clear\]", text, re.IGNORECASE):
        cues.append((m.start(), "throat_clear", 0.4))

    # Extract [laugh] — V11.64.0: replace with "haha" so TTS speaks it
    for m in re.finditer(r"\[laugh\]", text, re.IGNORECASE):
        cues.append((m.start(), "laugh", 0.0))

    # Extract [hmm] — 0.0s (word-level)
    for m in re.finditer(r"\[hmm\]", text, re.IGNORECASE):
        cues.append((m.start(), "hmm", 0.0))

    # Extract [um] — 0.0s (word-level)
    for m in re.finditer(r"\[um\]", text, re.IGNORECASE):
        cues.append((m.start(), "um", 0.0))

    # Sort by position
    cues.sort(key=lambda x: x[0])

    # V11.64.0: Replace [laugh] with "haha" BEFORE stripping, so TTS
    # speaks the laugh. Other cues are stripped (handled by audio generator).
    clean = re.sub(r"\[laugh\]", "haha", text, flags=re.IGNORECASE)

    # Remove all OTHER cue tags from text
    # V11.52.0: expanded to include sigh, chuckle, gasp, throat_clear
    # V11.64.0: laugh is already replaced above, so don't strip it here
    clean = re.sub(
        r"\[(?:pause|breath|hmm|um|sigh|chuckle|gasp|throat_clear)\s*\d*\.?\d*s?\]",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    # Clean up double spaces left behind
    clean = re.sub(r"\s+", " ", clean).strip()

    return clean, cues


def _force_insert_segments(
    lines: list[ScriptLine],
    bullets: list[str],
    missing_indices: list[int],
    mode: str,
) -> list[ScriptLine]:
    """Force-insert template segments for uncovered bullets.

    This is the LAST RESORT — if the LLM still misses bullets after
    retries, we programmatically insert segments. The model CANNOT skip
    a bullet.
    """
    # Find the index of the last content line (before conclusion)
    insert_pos = len(lines)
    for i, line in enumerate(lines):
        if line.segment_type == "conclusion":
            insert_pos = i
            break

    new_lines = []
    for idx in missing_indices:
        bullet_text = bullets[idx]
        bullet_ref = f"bullet {idx + 1}"
        if mode == "lecture":
            new_lines.append(
                ScriptLine(
                    host="A",
                    text=f"Another important point: {bullet_text}",
                    source_ref=bullet_ref,
                    segment_type="content",
                )
            )
        else:
            new_lines.append(
                ScriptLine(
                    host="A",
                    text=f"Let's talk about this point: {bullet_text}",
                    source_ref=bullet_ref,
                    segment_type="content",
                )
            )
            new_lines.append(
                ScriptLine(
                    host="B",
                    text="That's a great point. Can you elaborate on that?",
                    source_ref=bullet_ref,
                    segment_type="content",
                )
            )

    # Insert before the conclusion
    result = lines[:insert_pos] + new_lines + lines[insert_pos:]
    return result


# ── Main generation function ───────────────────────────────────────────


def generate_podcast_script(
    source_text: str,
    mode: str = "conversational",  # "lecture" or "conversational"
    tone: str = "casual",
    temperature: float = 0.7,
    language: str = "en",
    ollama_url: str = "http://localhost:11434",
    model: str = "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest",
    max_retries: int = 2,
    log_callback=None,
) -> ScriptResult:
    """Generate a podcast script with deterministic coverage guarantee.

    Args:
        source_text: The source material (bullet points, keypoints, text).
        mode: "lecture" (1 host) or "conversational" (2 hosts).
        tone: One of TONE_PROFILES keys.
        temperature: LLM temperature (0.6-0.9 for Qwythos compatibility).
        language: "en" or "fa".
        ollama_url: Ollama API URL.
        model: Ollama model name.
        max_retries: Max gap-fill retries before forced insertion.
        log_callback: Optional logging callback.

    Returns:
        ScriptResult with the script + coverage info.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    result = ScriptResult()

    # Step 0: Pre-process the source text (V11.37.2)
    log("  📝 Pre-processing source text...", "INFO")
    processed_text = preprocess_source_text(source_text)
    log(f"  ✅ Pre-processed: {len(processed_text)} chars", "DEBUG")

    # Step 1: Extract bullets deterministically
    bullets = extract_bullets(processed_text)
    if not bullets:
        result.error = "No bullet points found in source text"
        return result
    result.bullets_input = bullets
    log(f"  📝 Extracted {len(bullets)} bullet points from source", "INFO")
    for i, b in enumerate(bullets):
        log(f"     [{i + 1}] {b[:80]}...", "DEBUG")

    # Determine temperature label
    temp_label = "balanced"
    for label, val in TEMPERATURE_PROFILES.items():
        if abs(temperature - val) < 0.05:
            temp_label = label
            break

    # Step 2: Build prompt and generate script
    if mode == "lecture":
        prompt = _build_lecture_prompt(bullets, tone, temp_label, language)
    else:
        prompt = _build_conversational_prompt(bullets, tone, temp_label, language)

    import requests

    # V18.20.4.11 (P3 / O-c5): pooled transport — every LLM/endpoint call in
    # this module goes through the shared session selected by endpoint
    # locality (localhost → no-proxy pooled, cloud → proxy-trusting pooled).
    # Same timeouts/status handling as before; connection reuse added.
    from utils.network import session_for_url as _session_for_url

    def _call_ollama(prompt_text: str) -> str:
        """Call Ollama and return the response text.

        V11.37.2: better error reporting for 404 (model not found).
        """
        try:
            resp = _session_for_url(ollama_url).post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt_text,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 4096,
                        "num_ctx": 131072,
                    },
                },
                timeout=300,
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Could not connect to Ollama at {ollama_url}. "
                f"Is Ollama running? Start it with: ollama serve"
            ) from e
        if resp.status_code == 404:
            err_detail = ""
            try:
                err_detail = resp.json().get("error", "")
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                pass
            # List available models to help the user
            available = []
            try:
                tags_resp = _session_for_url(ollama_url).get(f"{ollama_url}/api/tags", timeout=5)
                if tags_resp.status_code == 200:
                    available = [m.get("name", "") for m in tags_resp.json().get("models", [])]
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                pass
            avail_str = "\n  ".join(available[:10]) if available else "(none found)"
            raise RuntimeError(
                f"Model '{model}' not found in Ollama (HTTP 404). "
                f"{'Ollama says: ' + err_detail if err_detail else ''}\n"
                f"Fix: ollama pull {model}\n"
                f"Available models:\n  {avail_str}"
            )
        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}"
            try:
                err_body = resp.json().get("error", "")
                if err_body:
                    err += f": {err_body}"
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                pass
            raise RuntimeError(f"Ollama error: {err}")
        return resp.json().get("response", "")

    # First generation
    log(f"  🎙️ Generating podcast script ({mode}, {tone}, temp={temperature})...", "INFO")
    log(f"  🤖 Model: {model}", "INFO")
    try:
        response = _call_ollama(prompt)
    except Exception as e:
        result.error = f"LLM call failed: {e}"
        return result

    # V11.37.4: strip <think> tags before parsing (Qwythos outputs these)
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE)
    response = re.sub(r"<think>.*", "", response, flags=re.DOTALL | re.IGNORECASE)
    response = response.strip()

    lines = _parse_script_response(response)
    if not lines:
        # V11.37.3: log the raw response so we can debug parsing failures
        log("  ❌ Failed to parse LLM response", "ERROR")
        log(f"  📋 Raw response (first 500 chars): {response[:500]}", "DEBUG")
        result.error = (
            "Failed to parse the LLM response. The model may not have "
            "returned valid JSON. Try a different model (e.g. qwen2.5:7b) "
            "or lower the creativity setting."
        )
        return result
    log(f"  ✅ Parsed {len(lines)} script lines", "INFO")
    result.lines = lines

    # Step 3: Verify coverage (deterministic)
    covered, missing = verify_coverage(lines, len(bullets))
    result.bullets_covered = covered
    result.bullets_missing = missing
    result.coverage_pct = len(covered) / len(bullets) if bullets else 0.0
    log(f"  📊 Coverage: {len(covered)}/{len(bullets)} ({result.coverage_pct:.0%})", "INFO")
    if missing:
        log(f"  ⚠️ Missing bullets: {[m + 1 for m in missing]}", "WARNING")

    # Step 4: Gap-fill retries
    while missing and result.retries < max_retries:
        result.retries += 1
        log(
            f"  🔄 Gap-fill retry {result.retries}/{max_retries} for "
            f"{len(missing)} missing bullets...",
            "INFO",
        )

        gap_prompt = _build_gap_fill_prompt(bullets, missing, mode, language)
        try:
            gap_response = _call_ollama(gap_prompt)
        except Exception as e:
            log(f"  ⚠️ Gap-fill call failed: {e}", "WARNING")
            break

        new_lines = _parse_script_response(gap_response)
        if new_lines:
            # Insert the new lines before the conclusion
            insert_pos = len(result.lines)
            for i, line in enumerate(result.lines):
                if line.segment_type == "conclusion":
                    insert_pos = i
                    break
            result.lines = result.lines[:insert_pos] + new_lines + result.lines[insert_pos:]

            # Re-verify
            covered, missing = verify_coverage(result.lines, len(bullets))
            result.bullets_covered = covered
            result.bullets_missing = missing
            result.coverage_pct = len(covered) / len(bullets) if bullets else 0.0
            log(
                f"  📊 Coverage after retry {result.retries}: "
                f"{len(covered)}/{len(bullets)} ({result.coverage_pct:.0%})",
                "INFO",
            )

    # Step 5: Force-insert any remaining missing bullets (LAST RESORT)
    if missing:
        log(
            f"  🔧 Force-inserting {len(missing)} uncovered bullets (deterministic guarantee)",
            "WARNING",
        )
        result.lines = _force_insert_segments(result.lines, bullets, missing, mode)
        result.forced_segments = len(missing)
        # Final verification
        covered, missing = verify_coverage(result.lines, len(bullets))
        result.bullets_covered = covered
        result.bullets_missing = missing
        result.coverage_pct = len(covered) / len(bullets) if bullets else 0.0
        log(
            f"  ✅ Final coverage: {len(covered)}/{len(bullets)} ({result.coverage_pct:.0%})",
            "INFO",
        )

    # V11.41.0/V11.52.0/V11.60.0: Inject human elements
    # V11.60.0: reverted intensity 0.5→0.3 (0.5 added too many extra lines,
    # making podcasts 40% longer to generate — especially painful on CPU)
    log("  🎭 Injecting human elements (backchannels, fillers, pauses)...", "INFO")
    original_count = len(result.lines)
    result.lines = inject_human_elements(result.lines, mode, intensity=0.3)
    added = len(result.lines) - original_count
    log(f"  ✅ Added {added} human element lines (total: {len(result.lines)})", "INFO")

    # V11.70.0: Post-processing — duplicate detection + number formatting
    result.lines = _remove_duplicate_lines(result.lines, log)
    result.lines = _fix_number_formatting(result.lines, log)

    # V11.51.0: Generate a short title for the podcast from the script content
    result.title = _generate_podcast_title(result.lines, ollama_url, model, temperature, log)

    return result


def _remove_duplicate_lines(lines: list[ScriptLine], log) -> list[ScriptLine]:
    """V11.70.0: Remove duplicate/near-duplicate lines from the script.

    The LLM sometimes repeats the same line (e.g., "The military, police, and
    law enforcement will be automated" appeared twice in the audit). This
    removes lines that are >80% similar to a previous line.
    """
    if not lines:
        return lines
    import re as _re

    seen_texts = []
    deduped = []
    removed = 0
    for line in lines:
        # Normalize: lowercase, strip vocal cues, strip punctuation
        normalized = _re.sub(r"\[.*?\]", "", line.text.lower())
        normalized = _re.sub(r"[^a-z0-9\s]", "", normalized).strip()
        # Check if this is too similar to any seen text
        is_dup = False
        for seen in seen_texts:
            # Simple similarity: if one contains the other (and both >20 chars)
            if len(normalized) > 20 and len(seen) > 20:
                if normalized in seen or seen in normalized:
                    is_dup = True
                    break
                # Word overlap check
                words1 = set(normalized.split())
                words2 = set(seen.split())
                if len(words1) > 3 and len(words2) > 3:
                    overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                    if overlap > 0.8:
                        is_dup = True
                        break
        if is_dup:
            removed += 1
            log(f"  🗑️ Removed duplicate line: '{line.text[:50]}...'", "DEBUG")
        else:
            seen_texts.append(normalized)
            deduped.append(line)
    if removed > 0:
        log(f"  ✅ Removed {removed} duplicate line(s)", "INFO")
    return deduped


def _fix_number_formatting(lines: list[ScriptLine], log) -> list[ScriptLine]:
    """V11.70.0: Fix spelled-out numbers → digits.

    The LLM sometimes spells out years and quantities ("two thousand twenty-two"
    instead of "2022"). This converts common patterns back to digits so the
    TTS engine reads them naturally.
    """
    import re as _re

    # Mapping of common spelled-out years and numbers
    YEAR_PATTERN = _re.compile(
        r"\b(two thousand (?:and )?)(twenty|twenty-one|twenty-two|twenty-three|"
        r"twenty-four|twenty-five|twenty-six|twenty-seven|twenty-eight|twenty-nine|"
        r"thirty|thirty-one|thirty-two|thirty-three|thirty-four|thirty-five|"
        r"thirty-six|thirty-seven|thirty-eight|thirty-nine|forty|forty-one|"
        r"forty-two|forty-three|forty-four|forty-five|forty-six|forty-seven|"
        r"forty-eight|forty-nine|fifty)\b",
        _re.IGNORECASE,
    )

    # Year word → digit mapping
    YEAR_WORDS = {
        "twenty": "20",
        "twenty-one": "21",
        "twenty-two": "22",
        "twenty-three": "23",
        "twenty-four": "24",
        "twenty-five": "25",
        "twenty-six": "26",
        "twenty-seven": "27",
        "twenty-eight": "28",
        "twenty-nine": "29",
        "thirty": "30",
        "thirty-one": "31",
        "thirty-two": "32",
        "thirty-three": "33",
        "thirty-four": "34",
        "thirty-five": "35",
        "thirty-six": "36",
        "thirty-seven": "37",
        "thirty-eight": "38",
        "thirty-nine": "39",
        "forty": "40",
        "forty-one": "41",
        "forty-two": "42",
        "forty-three": "43",
        "forty-four": "44",
        "forty-five": "45",
        "forty-six": "46",
        "forty-seven": "47",
        "forty-eight": "48",
        "forty-nine": "49",
        "fifty": "50",
    }

    fixed_count = 0
    for line in lines:
        original = line.text

        # Fix "two thousand twenty-two" → "2022"
        def _replace_year(m):
            year_word = m.group(2).lower()
            year_digits = YEAR_WORDS.get(year_word, "")
            if year_digits:
                return f"20{year_digits}"
            return m.group(0)

        line.text = YEAR_PATTERN.sub(_replace_year, line.text)

        # Fix common spelled-out numbers
        line.text = _re.sub(
            r"\bone hundred million\b", "100 million", line.text, flags=_re.IGNORECASE
        )
        line.text = _re.sub(r"\bone billion\b", "1 billion", line.text, flags=_re.IGNORECASE)
        line.text = _re.sub(r"\bone million\b", "1 million", line.text, flags=_re.IGNORECASE)
        line.text = _re.sub(r"\bten million\b", "10 million", line.text, flags=_re.IGNORECASE)

        if line.text != original:
            fixed_count += 1

    if fixed_count > 0:
        log(f"  ✅ Fixed number formatting in {fixed_count} line(s)", "INFO")
    return lines


def _generate_podcast_title(
    lines: list[ScriptLine], ollama_url: str, model: str, temperature: float, log
) -> str:
    """V11.51.0/V11.53.0/V11.62.0: Ask the LLM for a 3-6 word podcast title.

    V11.62.0: the <think> tags were consuming the ENTIRE response, leaving
    an empty title after stripping. Now: (a) use a stronger prompt that
    explicitly forbids <think> tags, (b) if the stripped title is empty,
    extract any text AFTER the </think> tag, (c) retry with a raw format
    prompt if the first attempt fails.
    """
    import re

    # V18.20.4.11 (P3 / O-c5): pooled transport — same session selection
    # as _call_ollama above (localhost → no-proxy pooled, cloud → pooled).
    from utils.network import session_for_url as _session_for_url

    # Build a summary of the script content for the LLM
    script_text = " ".join(ln.text for ln in lines[:10])[:500]
    prompt = (
        "Generate a SHORT podcast title (3-6 words) based on this script. "
        "The title should capture the main topic.\n\n"
        "IMPORTANT RULES:\n"
        "- Output ONLY the title text\n"
        "- NO <think> tags, NO reasoning, NO explanation\n"
        "- NO quotes, NO punctuation at the end\n"
        "- 3-6 words maximum\n\n"
        f"Script excerpt: {script_text}\n\n"
        "Title:"
    )
    try:
        resp = _session_for_url(ollama_url).post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": max(0.3, temperature),
                    "num_predict": 50,
                    "num_ctx": 4096,
                },
            },
            timeout=30,
        )
        if resp.status_code == 200:
            title = resp.json().get("response", "").strip()
            # V11.62.0: extract text AFTER </think> if present
            think_match = re.search(r"</think>\s*(.*)", title, re.DOTALL | re.IGNORECASE)
            if think_match:
                title = think_match.group(1).strip()
            else:
                # Strip <think>...</think> tags
                title = re.sub(r"<think>.*?</think>", "", title, flags=re.DOTALL | re.IGNORECASE)
                # Also strip unclosed <think> tags
                title = re.sub(r"<think>.*", "", title, flags=re.DOTALL | re.IGNORECASE)
            # Strip "The user wants..." reasoning text
            title = re.sub(
                r"^The user wants.*?(?:\.|!|\?)\s*", "", title, flags=re.IGNORECASE | re.DOTALL
            )
            # Clean up: remove quotes, newlines, extra whitespace
            title = title.strip("\"'").strip().replace("\n", " ")
            # Take first line only
            title = title.split("\n")[0].strip()
            # Remove any remaining tags
            title = re.sub(r"<[^>]+>", "", title).strip()
            # Limit to 60 chars
            if len(title) > 60:
                title = title[:57].rstrip() + "..."
            if title and len(title) >= 3:
                log(f"  📌 Podcast title: '{title}'", "INFO")
                return title
            log("  (title was empty after stripping <think> tags)", "DEBUG")
    except Exception as e:
        log(f"  (title generation failed: {e})", "DEBUG")

    # V11.62.0: better fallback — use the source_ref of the first content line
    for line in lines:
        if line.segment_type == "content" and line.text and len(line.text) > 10:
            # Take the first 5 meaningful words
            words = [w for w in line.text.split() if len(w) > 2][:5]
            if words:
                title = "-".join(w.strip(".,!?;:()[]") for w in words)
                log(f"  📌 Podcast title (fallback): '{title}'", "INFO")
                return title
    return "Untitled-Podcast"
