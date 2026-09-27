### ROLE ###
You are a meticulous academic indexer. Your task is to extract a source glossary from a book chapter.

### TASK ###
Read the source text below. Output a glossary as PLAIN MARKDOWN with the 3 section headers below, listing ALL cited authors (with their years + a 1-sentence context of their contribution), key dates/decades/ranges, + key concepts/terms. Be exhaustive. Output ONLY the 3 sections — no other text, no preamble, no thinking, no commentary, no XML tags.

### CRITICAL — START IMMEDIATELY WITH `## Source Glossary — Names` ###
Do NOT output any thinking, reasoning, or preamble. Do NOT use `<think>` tags. Do NOT explain your approach. Do NOT use `<name_glossary>` tags (the XML wrapper is NOT used — output plain markdown headers). The VERY FIRST character of your response MUST be `#` (the start of `## Source Glossary — Names`). If you output thinking or XML tags first, you will run out of tokens before finishing the glossary.

### CONSTRAINTS ###
- Pull every name, date, and term from the SOURCE TEXT below — do NOT invent, infer, or import from outside knowledge
- For each cited author, include the year(s) the source cites them in (e.g. `(1946)` or `(1946a, 1952b)`)
- For each entry, write a 1-sentence context describing their contribution / what the date refers to / a 1-sentence definition of the term
- If the source has no key dates or no key terms, emit the corresponding section header followed by no bullets (an empty section is valid — do NOT fabricate entries to fill it)
- Do NOT include thinking/reasoning — only the 3 sections
- Do NOT add markdown code fences
- Do NOT wrap the output in `<name_glossary>` tags — use plain markdown headers

### OUTPUT FORMAT ###
Output exactly like this (the 3 section headers are mandatory; the bullets under each are the LLM's content pulled from the source):

## Source Glossary — Names
- **Surname** (YYYY) — 1-sentence context of their contribution
- **Surname** (YYYYa, YYYYb) — context
## Source Glossary — Dates
- **YYYY-YYYY** — what the range refers to
- **YYYYs** (decade) — context
## Source Glossary — Terms
- **term** — 1-sentence definition

### FEW-SHOT EXAMPLE ###
(This is a GENERIC example to illustrate the format — your output must reflect THIS source's content, not the example. Do NOT copy these names/dates/terms; pull them from the source text below.)

## Source Glossary — Names
- **Smith** (1984) — contributed the X framework
- **Jones** (1990a, 1990b) — extended the X framework
## Source Glossary — Dates
- **1980-1990** — the X framework's development decade
## Source Glossary — Terms
- **X framework** — a theoretical model for understanding Y

### INPUT ###
Source text:
{source_text}
