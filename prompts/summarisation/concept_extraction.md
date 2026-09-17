### ROLE ###
You are a concept-extraction analyst.

### CONTEXT ###
A chapter is about to be summarised. To make sure the summary does not
miss anything critical, this pre-flight call identifies the 12-15 most
important concepts, named authors/theorists, and key ideas that any
complete summary of the chapter MUST cover. These concepts are later
used to drive gap-fill (so uncovered concepts get a generated bullet).

### TASK ###
Analyse the chapter text below and list the 12-15 most important
concepts, named authors/theorists, and key ideas that a summary MUST
cover.

### INPUT ###
Chapter text:
{{truncated}}

### CONSTRAINTS ###
- Do: include BOTH topical concepts AND named authors/theorists cited in the source.
- Do: include key theoretical contributions (named models, named frameworks, named processes — e.g., "the staged process of X", "the enumerated principles of Y").
- Do: prioritise specific, named concepts over generic terms.
- Do: output ONLY the bullet list, no preamble.
- Don't: include narrative events or story recaps.
- Don't: invent concepts not present in the source.
- Don't: include more than 15 items.
- Don't: output thinking process, reasoning, or commentary.

### OUTPUT FORMAT ###
For each concept, output one line in this exact format:

- Concept Name

(One bullet per line, prefixed with "- ". No numbering, no preamble.)

### SUCCESS CRITERIA ###
A good answer lists 12-15 specific named concepts/authors/frameworks from
the source, prioritises named items over generic terms, and emits ONLY a
bullet list with no surrounding prose.
