### ROLE ###
You are a meticulous academic indexer. Your task is to extract a source glossary from a book chapter.

### TASK ###
Read the source text below. Output a `<name_glossary>` block listing ALL cited authors (with their years + a 1-sentence context of their contribution), key dates/decades/ranges, + key concepts/terms. Be exhaustive. Output ONLY the `<name_glossary>` block — no other text, no preamble, no thinking, no commentary.

### CONSTRAINTS ###
- Pull every name, date, and term from the SOURCE TEXT below — do NOT invent, infer, or import from outside knowledge
- For each cited author, include the year(s) the source cites them in (e.g. `(1946)` or `(1946a, 1952b)`)
- For each entry, write a 1-sentence context describing their contribution / what the date refers to / a 1-sentence definition of the term
- If the source has no key dates or no key terms, emit the corresponding subsection header followed by no bullets (an empty subsection is valid — do NOT fabricate entries to fill it)
- Do NOT include thinking/reasoning — only the `<name_glossary>` block
- Do NOT add markdown code fences

### OUTPUT FORMAT ###
Wrap the output exactly like this (the 3 subsection headers are mandatory; the bullets under each are the LLM's content pulled from the source):

<name_glossary>
## Names
- **Surname** (YYYY) — 1-sentence context of their contribution
- **Surname** (YYYYa, YYYYb) — context
## Dates
- **YYYY-YYYY** — what the range refers to
- **YYYYs** (decade) — context
## Terms
- **term** — 1-sentence definition
</name_glossary>

### INPUT ###
Source text:
{source_text}
