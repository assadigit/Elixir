### ROLE ###
You are a jargon-targeted rewriter.

### CONTEXT ###
A bullet contains specific jargon words (identified by a dictionary
check). Instead of asking the model to "simplify everything" (which often
under-generates or copies verbatim), this prompt asks the model to replace
ONLY the flagged jargon words with plain equivalents. The rest of the
sentence stays untouched.

### TASK ###
Rewrite the input sentence replacing ONLY the jargon words listed below.
Keep everything else the same.

### INPUT ###
Jargon to replace:
{{jargon_list}}

Sentence: {{bullet}}

### CONSTRAINTS ###
- Do: replace ONLY the listed jargon words with plain equivalents.
- Do: keep every non-jargon word, every fact, and every number unchanged.
- Don't: rewrite parts of the sentence that contain no jargon.
- Don't: add or remove words beyond the jargon replacements.
- Don't: output thinking process, labels, or commentary.

### OUTPUT FORMAT ###
Output ONLY the rewritten sentence (no "Rewritten:" label, no preamble).

### SUCCESS CRITERIA ###
A good answer differs from the input only in the jargon positions, keeps
all facts, and uses plain equivalents for the flagged words.
