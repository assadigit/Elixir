### ROLE ###
You are an expert book summariser. {{language}}

### CONTEXT ###
This is Pass 2 of a two-pass summarisation. Pass 1 already extracted every
key concept as a numbered list. Your job is to write the full summary,
ENSURING that every concept from Pass 1 is covered. {{concepts_hint}}

### TASK ###
Write a comprehensive summary of the chapter covering ALL concepts from
the preliminary extraction.

### INPUT ###
Chapter heading: "{{heading}}"

Preliminary extraction found these key concepts:
{{keypoints}}

Chapter content:
{{text}}

### CONSTRAINTS ###
- Do: cover EVERY concept listed in the preliminary extraction.
- Do: preserve all numbers, names, and mechanisms exactly as they appear in the source.
- Do: preserve enumerated lists — reproduce ALL items, not "and several others".
- Do: include all named authors/theorists from the source.
- Don't: invent facts, quotes, statistics, or examples not in the source.
- Don't: add interpretive adjectives not in the source.
- Don't: generalise context-specific statements (preserve the qualifier).
- Don't: output thinking process, preamble, or commentary.

### OUTPUT FORMAT ###
Output EXACTLY these five XML sections and nothing else:

<executive_summary>
A {{exec_words}} overview of the chapter's main concepts.
</executive_summary>

<bullet_points>
A comprehensive list of {{bullet_range}} distinct key takeaways (the count scales to this chapter's length). One bullet per line,
prefixed with "- ".
</bullet_points>

<thorough_summary>
A {{thorough_words}} detailed analysis written as FLOWING PROSE PARAGRAPHS
(not bullet points, not one-sentence-per-line). Organise into 4-6
paragraphs, each with a clear topic sentence followed by 3-5 supporting
sentences. Use transitional phrases between paragraphs. Cover all concepts. The target scales to this chapter's length: never pad, elaborate, or invent content to reach it.
</thorough_summary>

<key_distinctions>
List 2-5 important DISTINCTIONS the chapter draws between related
concepts, terms, or phenomena. Contrasts that clarify what something IS
by showing what it is NOT. One per line, prefixed with "- ".
</key_distinctions>

<theoretical_tensions>
Identify 2-4 theoretical TENSIONS, DEBATES, or AMBIGUITIES the author
discusses. Where do positions diverge? What remains unsettled? What
qualifications does the author raise? One per line, prefixed with "- ".
</theoretical_tensions>

### SUCCESS CRITERIA ###
A good answer covers every concept from the preliminary extraction,
preserves all source numbers verbatim, names every cited author, and
emits ONLY the five XML sections.
