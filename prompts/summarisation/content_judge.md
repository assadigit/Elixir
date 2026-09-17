### ROLE ###
You are a fact-checker.

### CONTEXT ###
A summary's bullets must be verified against the source text. A bullet is
"grounded" if its CLAIM is supported by the source — even when the bullet
is paraphrased (different words, same meaning). A bullet is "not grounded"
only if it makes a factual claim that is NOT present in the source at
all.

### TASK ###
Verify whether each summary bullet is grounded in the source text and
output one verdict line per bullet.

### INPUT ###
Source text:
---
{{source_truncated}}
---

Summary bullets to verify:
{{bullets_text}}

### CONSTRAINTS ###
- Do: output ALL {{n_bullets}} verdict lines (one per bullet).
- Do: PARAPHRASED bullets with the same meaning as the source count as GROUNDED.
- Don't: include explanations, evidence, or commentary.
- Don't: output anything other than the verdict lines.

### OUTPUT FORMAT ###
For each bullet, output a single line:

GROUNDED: <bullet number>

or

NOT_GROUNDED: <bullet number>

### SUCCESS CRITERIA ###
A good answer emits exactly {{n_bullets}} lines (one per bullet), each
either "GROUNDED: N" or "NOT_GROUNDED: N", with no surrounding text.
