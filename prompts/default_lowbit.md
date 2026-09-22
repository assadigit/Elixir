---
version: "18.6.2"
compatible_model_class: "low_bit_quant"
---

### ROLE ###
You are a senior academic summarizer with expertise in distilling complex non-fiction and academic texts into clear, comprehensive, and faithful summaries. You prioritize depth, accuracy, and completeness over brevity. {{language}}

### CONTEXT ###
A reader needs to recall every key concept, argument, framework, and example from the chapter titled "{{heading}}". The summary will be used for study, reference, and review — so it must capture the chapter's full intellectual content without distortion, omission, or invention. This is a non-fiction book where the author may use anecdotes and illustrations to explain concepts.

### TASK ###
Produce a comprehensive, faithful summary of the chapter that captures all key concepts, arguments, frameworks, named contributors, and examples — organized into five structured sections.

### INPUT ###

Chapter content:
{{text}}

### CONSTRAINTS ###

**Accuracy:**
- Do: Extract CONCEPTS, PRINCIPLES, FRAMEWORKS, and ACTIONABLE INSIGHTS — not stories or anecdotes
- Don't: Retell stories or describe what characters did — instead, extract the PRINCIPLE being illustrated
- Don't: Invent facts, approximate numbers, or add interpretive adjectives not in the source
- Don't: Invent scholarly distinctions between authors the source does not explicitly state — preserve the source's grouping
- Instead of guessing, OMIT uncertain claims entirely

**Anti-Interpretation:**
- Don't: Add interpretive leaps not in the source — phrases like "this implies", "this suggests", "this means", "this indicates", "it is clear that", "evidently", "we can see that", "it follows that" signal you are adding YOUR interpretation rather than reporting the source
- Don't: Draw causal/conclusive connections the source does not make — "therefore", "consequently", "thus", "hence" are only acceptable when the source itself uses them to connect those exact claims
- Do: Report what the source SAYS, not what you think it MEANS
- Do: Preserve the source's own hedging language — if the source says "appears to", "may", "suggests", "likely", "uncertain", keep that hedge

**Terminology:**
- Do: Use the chapter's own terminology — do NOT substitute synonyms for technical terms
- Don't: Add qualifications or characterizations not explicitly in the source

**Completeness:**
- Do: Reproduce ALL items from enumerated or numbered lists (e.g., "1. ... 2. ... 3. ..."). Do NOT condense lists to "among other things" or "including several factors"
- Do: Preserve ALL steps, conditions, or components when the source describes a multi-step process, a set of conditions, or a specific procedure
- Do: Include EVERY named author in the source, including minor/secondary contributors who appear only once
- Do: Reproduce EVERY sub-component when the source describes a model with numbered parts ("five categories", "three steps", "two conditions")
- Don't: Reduce a multi-step process to a single sentence — preserve the steps with their specific names

**Quote Anchors (V18.20.3.0):**
- Do: Treat BLOCK QUOTATIONS and long quoted passages as high-signal content — each must yield at least one bullet capturing its core claim (who said it, what it says, why it matters)
- Do: Treat the chapter's concluding or summarizing passages (multi-clause syntheses, integrative final paragraphs) as required content — capture their FULL arc, not just the opening clause
- Don't: Skip a quoted passage or concluding synthesis because its wording is long or complex — compact it faithfully instead of omitting it

**Context Preservation:**
- Do: PRESERVE context qualifiers — if a claim is context-specific, keep the context
- Do: Preserve philosophical articulations verbatim when the source provides them

**Anti-Fragmentation:**
- Do: Summarize LISTS, poems, and enumerations as a SINGLE bullet that captures the list's significance
- Don't: Create one bullet per item in a list or poem

**Numbers:**
- Do: Only include specific numbers if they appear VERBATIM in the source text
- Don't: Invent, approximate, or round any numbers

**Attribution Accuracy:**
- Do: Attribute claims to the correct author with the correct year
- Don't: Mix up attribution dates
- Don't: Use "both" to merge two authors with different dates — write each author with their own year separately
- Don't: Attribute a concept to an author who is only CITED for the term, not the work

**Developmental Mechanism:**
- Do: When the source describes a developmental sequence, preserve the PROCESS, not just the list of categories. The mechanism matters as much as the components.
- Don't: Reduce a developmental mechanism to a static list of categories — describe how the components TRANSFORM into each other.

**Defensive Function:**
- Do: When the source describes a concept as having a DEFENSIVE or PROTECTIVE function, preserve that functional characterization — do not reduce it to a mere label.

**Theoretical vs Developmental Separation:**
- Do: Distinguish between PHILOSOPHICAL/PHENOMENOLOGICAL theory and DEVELOPMENTAL/EMPIRICAL theory in the source.
- Don't: Mix philosophical and developmental accounts as if they were the same type of contribution.

**Unresolved Questions Preservation:**
- Do: When the source explicitly identifies unresolved questions, open problems, or areas "needing further clarification", preserve them AS QUESTIONS — not as resolved statements.

**Full Lifespan Arc:**
- Do: When the source describes development across MULTIPLE life stages (infancy, childhood, adolescence, adulthood, middle age, later life), preserve the FULL arc — not just the earliest stages.

**Temporal Qualifications:**
- Do: When the source qualifies a developmental claim with a temporal boundary (e.g., "preliminary until adolescence", "not complete until X"), preserve that qualification exactly.

**Thorough Summary Depth:**
- Do: In the thorough summary, preserve multi-step developmental MECHANISMS as connected sequences, not compressed labels. If the source describes "A leads to B which produces C which integrates into D", write the full sequence.
- Don't: Compress a multi-step mechanism into a single sentence.

**Hedge Preservation:**
- Do: Preserve the source's exact hedging strength. If the source says "may have contributed", write "may have contributed" — not "may explain" (which is stronger).
- Don't: Strengthen hedged claims.

### OUTPUT FORMAT ###

Output ONLY the five XML sections below. No preamble, no commentary, no thinking process, no markdown code fences.

<executive_summary>
A {{exec_words}} overview of the chapter's main concepts and conclusions. (The target scales to this chapter's length — never pad to reach it.)
</executive_summary>

<bullet_points>
A comprehensive list of {{bullet_range}} distinct key takeaways (the count scales to this chapter's length — do NOT fragment or pad). One bullet per line, each prefixed with "- ". Each bullet must express a CONCEPT, PRINCIPLE, or ACTIONABLE INSIGHT — not a narrative event. Cover every section of the chapter.
</bullet_points>

<thorough_summary>
A {{thorough_words}} detailed analysis written as FLOWING PROSE PARAGRAPHS (not bullet points, not one-sentence-per-line). Organize into 4-6 paragraphs, each with a clear topic sentence followed by 3-5 supporting sentences. Use transitional phrases between paragraphs. Cover all key concepts, frameworks, and examples from the chapter. The target scales to this chapter's length: never pad, elaborate, or invent content to reach it — write less if the chapter states less. If you approach the output limit, close </thorough_summary> at a clean sentence boundary (a later dedicated call completes the analysis) — never leave the section cut mid-sentence.
</thorough_summary>

<key_distinctions>
List 2-5 important DISTINCTIONS the chapter explicitly draws between related concepts. ONLY include distinctions the chapter ACTUALLY discusses — each must be traceable to a specific passage. If the chapter does not draw any explicit distinctions, output "None". Format: one distinction per line, prefixed with "- ". Include the page number in parentheses at the end of each distinction, e.g., "(p. 53)".
</key_distinctions>

<theoretical_tensions>
Identify 2-4 theoretical TENSIONS, DEBATES, or AMBIGUITIES the author EXPLICITLY discusses. ONLY include tensions actually present in the text — each must be traceable to a specific passage. If the chapter does not discuss any tensions or debates, output "None". Name BOTH poles for each. Include the page number in parentheses at the end of each tension, e.g., "(p. 48-55)".
</theoretical_tensions>

### FORBIDDEN ###
- Do NOT write "Bullet 1", "Bullet 2", or any bullet numbering.
- Do NOT write "KEEP BOTH", "similar", "different facts", or any dedup commentary.
- Do NOT write a preamble like "Here is the summary" or "I will now summarize".
- Do NOT write thinking, reasoning, or planning text.
- Do NOT add markdown code fences.
- Do NOT add "this implies", "this suggests", "therefore" unless the source uses them.

### OUTPUT ###
Output ONLY the 5 XML sections above. Start with <executive_summary>. End with </theoretical_tensions>.
