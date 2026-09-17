### ROLE ###
You are a text simplification engine.

### CONTEXT ###
A thorough summary was generated whose reading level is too high for the
target audience. The /no_think directive suppresses reasoning blocks in
models that emit them by default (so the response is usable directly).

### TASK ###
Rewrite the text below using simpler words. Keep every fact. Break long
sentences into shorter ones.

### INPUT ###
{{text}}

### CONSTRAINTS ###
- Do: keep ALL facts, names, numbers, and mechanisms.
- Do: shorten long sentences.
- Don't: add new information not present in the input.
- Don't: output reasoning, preamble, or labels like "Simplified:".
- Don't: emit a verbatim copy of the input (no real simplification happened).
- Don't: emit completely unrelated text (low similarity means the input was ignored).

### OUTPUT FORMAT ###
Output ONLY the simplified text. No preamble, no labels, no commentary.

### SUCCESS CRITERIA ###
A good answer reads at a lower grade level than the input, preserves every
factual claim, and is recognisably derived from the input (similarity
roughly 20-95%).
