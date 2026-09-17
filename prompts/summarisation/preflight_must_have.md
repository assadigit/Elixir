### ROLE ###
You are an expert academic reviewer. {{language}}

### CONTEXT ###
Before a chapter is summarised section-by-section (B4 map-reduce), this
pre-flight call identifies the 5-7 items that ANY acceptable summary of
this chapter MUST include. These items are injected as explicit
requirements into each section's prompt, so nothing critical is dropped.

### TASK ###
Identify the 5-7 most important items that any summary of this chapter
MUST include to be considered complete.

### INPUT ###
Chapter heading: "{{heading}}"

Chapter excerpt (first 200 chars):
{{text_excerpt}}

CHAPTER TEXT (excerpt):
{{src_text}}

### CONSTRAINTS ###
- Do: look for enumerated lists (e.g., "four characteristics", "five phases", "six stages").
- Do: look for key definitions or conceptual frameworks.
- Do: look for critical conclusions or summary statements.
- Do: look for specific conditions, mechanisms, or causal relationships.
- Do: look for important direct quotes or seminal passages.
- Do: output each item as a short phrase (max 15 words), one per line, prefixed with "- ".
- Don't: include more than 7 items.
- Don't: include narrative events or story recaps.
- Don't: output thinking process, preamble, or commentary.

### OUTPUT FORMAT ###
A list of 5-7 short phrases, one per line, prefixed with "- ". No
preamble, no surrounding prose.

### SUCCESS CRITERIA ###
A good answer identifies 5-7 specific, named, must-have items that any
complete summary of THIS chapter must reproduce (e.g., "the three
conditions of X", "the four-stage process of Y"), with no filler.
