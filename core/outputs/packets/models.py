"""Packets of Knowledge — data model (shared helpers).

V18.20.4.6+ (P5-2b / O-c4): extracted VERBATIM from the former
core/outputs/packets.py monolith (lines 64-106 of the pre-split file) —
only this module docstring + import block differ. Holds the shared data
model consumed by core.outputs.packets.generator.PacketGenerator (and
available to any future packets consumer via the core.outputs.packets
facade): the LogFn type alias + the Packet / PacketCollection dataclasses.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

LogFn = Callable[[str, str], None]


# ════════════════════════════════════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class Packet:
    """A single Packet of Knowledge — synthesized from 5-8 keypoints."""

    index: int
    title: str = ""
    tldr: str = ""
    question: str = ""
    paragraph: str = ""
    source_bullets: list[str] = field(default_factory=list)
    source_chapters: list[str] = field(default_factory=list)
    importance: str = "contextual"  # "critical", "important", "contextual"
    has_tension: bool = False
    tension_description: str = ""
    cross_refs: list[int] = field(default_factory=list)  # indices of related packets
    validation_passed: bool = False
    validation_details: str = ""
    concept: str = ""  # Level 2 grouping
    theme: str = ""  # Level 1 grouping
    # V13.23.0: Supplementary context from executive summary — used when a
    # chapter has fewer than MIN_BULLETS_PER_PACKET bullets.  These sentences
    # are NOT primary bullets; they provide context so the LLM doesn't
    # hallucinate to fill the gap.  Tracked separately so validation can
    # trace against both bullets + supplementary context.
    supplementary_context: list[str] = field(default_factory=list)


@dataclass
class PacketCollection:
    """All packets for a book + metadata."""

    book_title: str
    packets: list[Packet] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    total_bullets: int = 0
    total_packets: int = 0
    generation_time_s: float = 0.0
