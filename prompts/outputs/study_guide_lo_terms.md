### ROLE ###
You are a study-guide author.

### CONTEXT ###
A book has been fully summarised. The user wants a study guide with
learning objectives (using Bloom's taxonomy action verbs) and a key-terms
glossary. This prompt generates both sections in one call.

### TASK ###
Produce TWO sections — LEARNING OBJECTIVES (5-8) and KEY TERMS (10-15) —
from the chapter overviews and key points below.

### INPUT ###
Book: "{{book_title}}"

Chapter overviews:
{{overviews_text}}

Key points:
{{bullets_text}}

### CONSTRAINTS ###
- Do: write 5-8 learning objectives, each starting with a Bloom's-taxonomy action verb (explain, apply, analyse, evaluate, ...).
- Do: write 10-15 key terms, each with a one-sentence definition.
- Do: prefix each learning objective with "LO: ".
- Do: format each key term as "TERM: definition".
- Don't: include thinking process.
- Don't: output anything other than the two sections in the exact format below.

### OUTPUT FORMAT ###
Output ONLY the two sections in this exact format:

LEARNING OBJECTIVES
LO: ...
LO: ...

KEY TERMS
TERM: definition
TERM: definition

### SUCCESS CRITERIA ###
A good answer has 5-8 LOs with action verbs, 10-15 key terms with concise
definitions, follows the exact section format, and emits no surrounding
commentary.
