"""V13.19.0: Packets of Knowledge — synthesized knowledge from keypoints.

Transforms hundreds of scattered bullet points into a structured, hierarchical
knowledge document with TL;DRs, importance scoring, cross-references,
contradiction detection, one-page distillation, and reader's journey.

V13.19.0 CHANGES (audit fixes):
- Q&A section removed entirely (saves 1 LLM call per packet).
- Pre-clustering deduplication (rapidfuzz, 85% threshold) keeps clean input.
- Failed-validation packets are NO LONGER DROPPED — they fall back to a
  formatted bullet list so 100% of source bullets remain visible.
- A new coverage report ({book}.Packets.Coverage.md) maps every input
  bullet → packet + status (✅ Synthesized / ⚠️ Bullet-list fallback).
- One-page distillation now performs a REAL cross-cutting-themes LLM call
  (instead of copy-pasting TL;DRs).
- Mermaid knowledge map: node IDs are sanitized (alphanumeric + underscore,
  ≤30 chars), so commas / punctuation no longer break Mermaid syntax.
- Synthesis + TL;DR are produced in ONE LLM call (JSON output), halving the
  per-packet LLM call count from 4 → 2 (synthesis+TL;DR combined + importance).

Pipeline:
  1. Collect all keypoints from all chapters
  2. Deduplicate near-identical bullets (rapidfuzz, 85%)
  3. Cluster into packets (5-8 bullets each)
  4. For each packet:
     a. Generate paragraph synthesis + TL;DR in ONE LLM call (JSON output)
     b. Score importance (Critical/Important/Contextual)
     c. Detect contradictions (tension points)
     d. Validate claims (semantic similarity to source bullets)
        - On failure: fall back to bullet-list (packet is NOT dropped)
  5. Build hierarchy: packets → concepts → themes
  6. Generate cross-references (Obsidian-friendly wikilinks)
  7. Generate one-page distillation (real theme synthesis)
  8. Generate reader's journey path
  9. Output: .Packets.md, .Packets.OnePage.md, .Packets.Map.md,
            .Packets.Coverage.md

Output structure:
  output/MyBook/
  ├── MyBook.Packets.md           ← Full document (all packets, TL;DRs)
  ├── MyBook.Packets.OnePage.md   ← One-page distillation
  ├── MyBook.Packets.Map.md       ← Mermaid knowledge map
  ├── MyBook.Packets.Coverage.md  ← Bullet → packet coverage report
  └── fa/
      └── MyBook.Packets.fa.md    ← Farsi translation (if enabled)
"""

from __future__ import annotations

# V18.20.4.6+ (P5-2b / O-c4): the former 1,708-line packets.py monolith was
# split into this package. This __init__ is a pure facade: it re-exports the
# pre-split public names so every ``from core.outputs.packets import ...``
# site (core/outputs/__init__.py, the packets tool dialog, tests) resolves
# unchanged. The classes live in per-class modules:
#   * models.py   — LogFn + Packet + PacketCollection (shared data model)
#   * generator.py — PacketGenerator
# Importers must import names from this package (core.outputs.packets),
# not from the submodules directly.
from core.outputs.packets.generator import PacketGenerator
from core.outputs.packets.models import LogFn, Packet, PacketCollection

__all__ = [
    "Packet",
    "PacketCollection",
    "PacketGenerator",
    "LogFn",
]
