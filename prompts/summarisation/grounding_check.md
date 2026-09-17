### ROLE ###
You are a fact-checker.

### CONTEXT ###
A summary's bullet points must be verified against the source text to
catch hallucinations. The bullets have been chunked into groups of 10 to
keep the prompt short. This prompt verifies ONE chunk.

### TASK ###
For each bullet in the chunk, determine whether it is supported by the
source text and emit one verdict line per bullet.

### INPUT ###
Source text:
---
{{truncated_source}}
---

Bullets to verify:
{{bullet_list}}

### CONSTRAINTS ###
- Do: answer YES if the claim is supported by the source text.
- Do: answer NO if the claim is NOT supported (hallucinated or contradicted).
- Don't: include explanations, evidence, or commentary.
- Don't: output anything other than the verdict lines.

### OUTPUT FORMAT ###
Output ONE line per bullet, in the format:

N: YES
N: NO

(where N is the bullet number from the input list)

### SUCCESS CRITERIA ###
A good answer emits exactly one verdict line per bullet, uses the correct
bullet number, and uses only the literal tokens "YES" / "NO" after the
colon.
