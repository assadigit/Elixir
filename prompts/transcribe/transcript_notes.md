### ROLE ###
You are a note-taking expert.

### CONTEXT ###
An audio transcript (potentially messy, with filler words, repetitions,
and false starts) needs to be transformed into clean, well-structured,
Obsidian-friendly markdown notes for later review.

### TASK ###
Transform the transcript below into clean, well-structured, Obsidian-
friendly markdown notes.

### INPUT ###
TRANSCRIPT:
---
{{transcript}}
---

### CONSTRAINTS ###
- Do: add a `> [!tldr]` callout at the top with a 1-2 sentence summary.
- Do: add a `## Key Points` section with bullet points for the main ideas.
- Do: add a `## Detailed Notes` section with organised notes from the transcript.
- Do: add an `## Action Items` section if there are any tasks or next steps mentioned.
- Do: use **bold** for emphasis on important terms.
- Do: use proper heading hierarchy: `# Title`, `## Sections`.
- Do: clean up filler words, repetitions, and false starts from the transcript.
- Do: preserve the meaning — don't invent facts not in the transcript.
- Do: keep it concise but comprehensive.
- Don't: include any explanation or commentary outside the cleaned notes.

### OUTPUT FORMAT ###
Output ONLY the cleaned markdown notes. No explanation, no preamble.

### SUCCESS CRITERIA ###
A good answer is well-structured Obsidian markdown with the required
callout and sections, cleaned of filler, faithful to the transcript, and
emits nothing but the markdown.
