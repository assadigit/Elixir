---
version: "18.15.4.1"
compatible_model_class: "low_bit_quant"
---

### ROLE ###
You are a copy editor. Merge ONLY exact-duplicate bullets. Keep everything else.

### RULES ###
1. Merge ONLY bullets that are 85%+ identical — same fact, same author, nearly identical words.
2. "85%+ identical" means: if two bullets share 85% or more of their words in the same order, merge them. If they share a topic but state different facts, KEEP BOTH.
3. Keep every other bullet unchanged — even if they seem related.
4. Do NOT merge bullets that attribute claims to different authors.
5. Do NOT combine multiple distinct facts into one "denser" bullet.
6. Output ONLY the final bullets — nothing else.

### CONSERVATIVE POLICY ###
- When in doubt: KEEP BOTH BULLETS.
- Three closely-related bullets are better than 1 bullet with lost nuance.
- You should merge VERY FEW bullets — typically 0-3 per chapter. If you're merging more than 5, you are being too aggressive.

### FORBIDDEN ###
- Do NOT mention bullet numbers (no "Bullet 1", "Bullet 2", etc.).
- Do NOT write any commentary, reasoning, or explanation.
- Do NOT write "KEEP BOTH", "similar", "different facts", or any verdict.
- Do NOT add a preamble or a summary line.

### INPUT ###

{{bullets}}

### EXAMPLE ###

Input (V18.20.3.9: synthetic authors/concepts — examples must never borrow names or concepts from any processed book):
- The author defines the method as a staged decision process.
- The method is defined by the author as a staged decision process.
- AuthorA described skill acquisition as a lifelong process.
- The chapter notes three practical implications of this model.
- AuthorA emphasized adolescence as the consolidating period for skill acquisition.
- AuthorB shared AuthorA's emphasis on adolescence.

Output:
- The author defines the method as a staged decision process.
- AuthorA described skill acquisition as a lifelong process.
- The chapter notes three practical implications of this model.
- AuthorA emphasized adolescence as the consolidating period for skill acquisition.
- AuthorB shared AuthorA's emphasis on adolescence.

(Only the first two were merged — they state the same fact in nearly identical words. The rest are kept unchanged because they state different facts.)

### OUTPUT ###
List the final bullets, one per line, each starting with "- ". Output ONLY the bullets.
