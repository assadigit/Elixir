"""Markdown-aware chunker for translation.

Splits text on paragraph / heading boundaries while preserving:
  * YAML front-matter (kept as a single chunk, not translated)
  * Code blocks (`` ``` ``) — kept intact, not translated
  * List structure (bullet points stay grouped)
  * Heading hierarchy

Target chunk size is ~2k tokens (configurable). Each chunk carries a
1-paragraph sliding context window from the *previous* chunk so the
translator has continuity.

The chunker is token-aware via ``tiktoken`` (already a project dependency)
with a fallback to character-count estimation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

# ── Token estimation ──────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

_tiktoken_enc = None


def _estimate_tokens(text: str) -> int:
    """Estimate token count. Uses tiktoken if available, else ~4 chars/token."""
    global _tiktoken_enc
    if _tiktoken_enc is None:
        try:
            import tiktoken
            _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _tiktoken_enc = False  # mark as unavailable
    if _tiktoken_enc:
        try:
            return len(_tiktoken_enc.encode(text))
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
    # Fallback: ~4 characters per token for English, ~2 for Persian
    # Use a blended estimate
    return max(1, len(text) // 3)


# ── Data structures ───────────────────────────────────────────────────────

@dataclass
class Chunk:
    """A single translatable chunk of text.

    Attributes:
        index:        0-based position in the chunk list.
        text:         the chunk text to translate.
        context:      a short string from the previous chunk (for continuity).
        is_frontmatter: True if this is YAML front-matter (should NOT be translated).
        is_code:      True if this is a code block (should NOT be translated).
        token_estimate: estimated token count of ``text``.
    """
    index: int
    text: str
    context: str = ""
    is_frontmatter: bool = False
    is_code: bool = False
    token_estimate: int = 0

    def __post_init__(self) -> None:
        if self.token_estimate == 0:
            self.token_estimate = _estimate_tokens(self.text)


# ── Chunker ──────────────────────────────────────────────────────────────

class TranslationChunker:
    """Splits markdown text into translation-friendly chunks.

    Usage::

        chunker = TranslationChunker(max_tokens=2000)
        chunks = chunker.chunk(markdown_text)
        for c in chunks:
            if c.is_frontmatter or c.is_code:
                ...  # skip translation
            else:
                translated = translator.translate(c.text, ...)
    """

    # YAML front-matter: --- at the very start, ending with ---
    _FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)

    # Fenced code blocks: ```lang ... ```
    _CODEBLOCK_RE = re.compile(r"```[\s\S]*?```")

    # Markdown headings: # H1, ## H2, etc.
    _HEADING_RE = re.compile(r"^(#{1,6})\s+.+$", re.MULTILINE)

    def __init__(self, max_tokens: int = 2000) -> None:
        self.max_tokens = max_tokens

    def chunk(self, text: str) -> list[Chunk]:
        """Split ``text`` into a list of :class:`Chunk` objects.

        The algorithm:
          1. Extract YAML front-matter -> 1 chunk (is_frontmatter=True).
          2. Extract fenced code blocks -> separate chunks (is_code=True).
          3. Split the remaining text on double-newlines (paragraphs).
          4. Greedily merge paragraphs until we approach ``max_tokens``.
          5. Split on heading boundaries first (a heading starts a new chunk).
        """
        if not text or not text.strip():
            return []

        chunks: list[Chunk] = []
        remaining = text

        # ── Step 1: Extract YAML front-matter ──────────────────────────
        fm_match = self._FRONTMATTER_RE.match(remaining)
        if fm_match:
            fm_text = fm_match.group(0)
            chunks.append(Chunk(
                index=len(chunks),
                text=fm_text,
                is_frontmatter=True,
            ))
            remaining = remaining[fm_match.end():]

        # ── Step 2: Split out code blocks ──────────────────────────────
        # We use a split-and-keep approach: find all code blocks, and
        # interleave them with the text between them.
        parts: list[tuple] = []  # (text, is_code)
        last_end = 0
        for m in self._CODEBLOCK_RE.finditer(remaining):
            if m.start() > last_end:
                parts.append((remaining[last_end:m.start()], False))
            parts.append((m.group(0), True))
            last_end = m.end()
        if last_end < len(remaining):
            parts.append((remaining[last_end:], False))

        # ── Step 3-5: For each non-code part, split into chunks ────────
        prev_context = ""
        for part_text, is_code in parts:
            if is_code:
                chunks.append(Chunk(
                    index=len(chunks),
                    text=part_text,
                    is_code=True,
                    context=prev_context[-200:] if prev_context else "",
                ))
                prev_context = part_text[-200:]
                continue

            # Split this non-code part into paragraph/heading-based chunks
            sub_chunks = self._split_text(part_text)
            for sc in sub_chunks:
                sc.index = len(chunks)
                sc.context = prev_context[-300:] if prev_context else ""
                chunks.append(sc)
                prev_context = sc.text[-200:]

        return chunks

    def _split_text(self, text: str) -> list[Chunk]:
        """Split non-code text into chunks, respecting headings + paragraphs."""
        # Split on headings — each heading starts a new section
        # We keep the heading with its section body
        sections = self._split_on_headings(text)

        chunks: list[Chunk] = []
        current_buf: list[str] = []
        current_tokens = 0

        def flush() -> None:
            nonlocal current_buf, current_tokens
            if current_buf:
                text_joined = "\n\n".join(current_buf)
                chunks.append(Chunk(
                    index=0,  # will be set by caller
                    text=text_joined,
                ))
                current_buf = []
                current_tokens = 0

        for section in sections:
            section_tokens = _estimate_tokens(section)
            # If adding this section exceeds max_tokens, flush first
            if current_buf and current_tokens + section_tokens > self.max_tokens:
                flush()
            # If a single section is bigger than max_tokens, split it further
            if section_tokens > self.max_tokens:
                flush()
                sub_parts = self._split_large_section(section)
                for sp in sub_parts:
                    chunks.append(Chunk(index=0, text=sp))
            else:
                current_buf.append(section)
                current_tokens += section_tokens

        flush()
        return chunks

    def _split_on_headings(self, text: str) -> list[str]:
        """Split text into sections, each starting with a heading (if present).

        Text before the first heading is its own section.
        """
        lines = text.split("\n")
        sections: list[str] = []
        current: list[str] = []

        for line in lines:
            if self._HEADING_RE.match(line):
                # Start a new section
                if current:
                    sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append("\n".join(current).strip())

        # Now split each section on double-newlines (paragraphs) if the
        # section itself is large. But for now, keep sections as-is —
        # _split_text will handle merging/splitting.
        return [s for s in sections if s]

    def _split_large_section(self, section: str) -> list[str]:
        """Split a section that's too large by breaking on paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", section)
        if len(paragraphs) <= 1:
            # No paragraph breaks — split by sentences as last resort
            return self._split_by_sentences(section)

        parts: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            pt = _estimate_tokens(para)
            if current and current_tokens + pt > self.max_tokens:
                parts.append("\n\n".join(current))
                current = [para]
                current_tokens = pt
            else:
                current.append(para)
                current_tokens += pt
        if current:
            parts.append("\n\n".join(current))
        return parts

    def _split_by_sentences(self, text: str) -> list[str]:
        """Last-resort: split by sentence boundaries (EN + FA)."""
        # Split on . ! ? ؟ . (period, exclamation, question, Persian question mark)
        sentences = re.split(r"(?<=[\.!?؟。])\s+", text)
        parts: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            st = _estimate_tokens(sent)
            if current and current_tokens + st > self.max_tokens:
                parts.append(" ".join(current))
                current = [sent]
                current_tokens = st
            else:
                current.append(sent)
                current_tokens += st
        if current:
            parts.append(" ".join(current))
        return parts if parts else [text]
