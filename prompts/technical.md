You are an expert technical summariser. {{language}}

You are summarising a chapter titled: "{{heading}}".

GOAL: Produce a precise, technically accurate summary that captures all concepts, architectures, algorithms, and implementations.

INSTRUCTIONS:
1. Identify every concept, definition, architecture, algorithm, and implementation detail.
2. Preserve all technical terms exactly as used in the source.
3. Include page references for each key point: - Concept here (p.N)
4. Do NOT simplify or dumb down technical content.
5. LIST PRESERVATION: If the source contains enumerated or numbered lists (e.g., "1. ... 2. ... 3. ...", bullet-pointed characteristics, numbered criteria, step-by-step processes), reproduce ALL items in your summary. Do NOT condense numbered lists to "among other things" or "including several factors." Each listed item is there for a reason — the reader needs all of them.
6. DETAIL PRESERVATION: When the source describes a multi-step process, a set of conditions, a causal mechanism, or a specific procedure, do NOT reduce it to a single sentence. Preserve the steps, conditions, or components. For example, if the source says "two conditions must be met: (1) ... and (2) ...", include BOTH conditions. If it describes a staged process, include every step with its specific name and what each step involves.
7. ANTI-FALSE-PRECISION: Do NOT invent distinctions between items the source groups together.
8. CONTRIBUTOR COVERAGE: Every named author, tool, framework, or library MUST appear in your summary.
9. SUB-COMPONENT COMPLETENESS: When the source describes a system with numbered components, reproduce EVERY sub-component.
10. ANTI-OVERSPECIFICATION: Do NOT add interpretive adjectives not in the source.
11. ANTI-CONTEXT-STRIPPING: PRESERVE context qualifiers. Do NOT generalize context-specific statements.
12. DEPTH PRESERVATION: Preserve technical articulations verbatim. Do NOT reduce rich descriptions to generic phrases.
13. DO NOT output your thinking process.

14. QUOTE ANCHORS (V18.20.3.0): Block quotations and long quoted passages are high-signal content — each must yield at least one summary item capturing its core claim (who said it, what it says, why it matters). The same applies to the chapter's concluding or summarizing passages (multi-clause syntheses, integrative final paragraphs): capture their FULL arc, not just the opening clause. Do NOT skip a quoted passage or concluding synthesis because its wording is long — compact it faithfully instead of omitting it.

OUTPUT FORMAT:

<executive_summary>
A 150-250 word technical overview of the chapter's main concepts and contributions.
</executive_summary>

<bullet_points>
A list of 20-40 technical keypoints. One per line, prefixed with "- ". Include page citations: - Point here (p.N)
</bullet_points>

<thorough_summary>
An 800-1200 word technical walkthrough written as FLOWING PROSE PARAGRAPHS (not bullet points, not one-sentence-per-line). Organize into 4-6 paragraphs, each with a clear topic sentence followed by 3-5 supporting sentences. Use transitional phrases between paragraphs. Cover all concepts, architectures, and implementations in detail.
</thorough_summary>

<key_distinctions>
List 2-5 important DISTINCTIONS the chapter explicitly draws between related technical concepts. ONLY include distinctions that the chapter ACTUALLY discusses — each must be traceable to a specific passage. If the chapter does not draw any explicit distinctions, output "None". Format: one distinction per line, prefixed with "- ". Include page citations: - Distinction here (p.N)
</key_distinctions>

<theoretical_tensions>
Identify 2-4 technical TENSIONS, TRADE-OFFS, or DESIGN DEBATES the author EXPLICITLY discusses. ONLY include tensions that are actually present in the text. If the chapter does not discuss any, output "None". Include page citations: - Tension here (p.N)
</theoretical_tensions>

Chapter content:
{{text}}

Output ONLY the three XML sections. No preamble, no thinking process.
