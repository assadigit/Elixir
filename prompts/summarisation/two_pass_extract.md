### ROLE ###
You are an expert book summariser. {{language}}

### CONTEXT ###
This is Pass 1 of a two-pass summarisation. The job of this pass is
extraction only: pull every concept, principle, technique, and actionable
insight out of the chapter as a numbered checklist. Pass 2 will use the
checklist to write the full summary, ensuring nothing is dropped.

### TASK ###
Extract ALL concepts, principles, techniques, and actionable insights
from the chapter below as a numbered list.

### INPUT ###
Chapter: "{{heading}}"

Chapter content:
{{text}}

### CONSTRAINTS ###
- Do: output one concept per line, numbered (1., 2., 3., ...).
- Do: write each item as a complete sentence expressing a CONCEPT, PRINCIPLE, TECHNIQUE, or ACTIONABLE INSIGHT — never a narrative event.
- Do: cover EVERY section of the chapter.
- Don't: output thinking process, preamble, or commentary.
- Don't: condense enumerated lists into phrases like "and several other factors".

### OUTPUT FORMAT ###
Numbered list, one concept per line, starting with "1.". No preamble.

### SUCCESS CRITERIA ###
A good answer is exhaustive (covers every section), expresses each item
as a concept rather than a story beat, and is purely a numbered list with
no surrounding text.
