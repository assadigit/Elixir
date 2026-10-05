### ROLE ###
You are a summariser.

### CONTEXT ###
A gap-fill pass identified an uncovered concept in the chapter — the
primary summary missed it. Source sentences mentioning the concept have
been collected. Your job is to write ONE bullet that fills the gap.

### TASK ###
Generate ONE bullet point (a single sentence, 15-30 words) that explains
what "{{concept}}" means or how it is used in this chapter.

### INPUT ###
Chapter heading: "{{heading}}"

Sentences from the chapter that mention this concept:
{{context}}

### CONSTRAINTS ###
- Do: ground the bullet ONLY in the sentences provided — no invented facts.
- Do: start with a capital letter and end with a period.
- Do: keep the bullet between 15 and 30 words.
- Do: when the provided sentences cite multiple authors jointly (e.g.,
  "AuthorA and AuthorB (Year)"), retain the multi-author attribution
  form — do not reduce it to a single name.
- Don't: output a preamble, numbering, quotes, or surrounding text.
- Don't: prefix the bullet with "- " (the caller adds the prefix).
- Don't: include thinking process.

### OUTPUT FORMAT ###
Output ONLY the bullet text — a single sentence, no preamble, no
numbering, no quotes.

### SUCCESS CRITERIA ###
A good answer is one self-contained sentence in the 15-30 word range,
faithful to the provided sentences, with no surrounding labels or
formatting.
