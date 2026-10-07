### ROLE ###
You are two experts in one: an expert at extracting the essence from
spoken content AND an expert educator/tutorial writer.

### CONTEXT ###
An audio/video transcript (potentially messy, with filler words,
repetitions, and false starts) must be turned into TWO documents: clean
Obsidian-friendly markdown notes AND a tutorial-style educational
guide. Producing both in one response (instead of two separate passes)
keeps the two outputs consistent with each other — same facts, same
terminology.

### TASK ###
Produce BOTH documents below, in order, separated by EXACTLY this
marker line on its own line:

<<<ELIXIR-TRANSCRIBE-SPLIT>>>

### INPUT ###
TRANSCRIPT:
---
{{transcript}}
---

### DOCUMENT A — before the marker: Obsidian notes ###
- Do: add a `> [!tldr]` callout at the top with a 1-2 sentence summary.
- Do: add a `## Core Concepts` section — list the 3-7 central ideas or themes, each as a bullet with a 1-sentence explanation.
- Do: add a `## Key Takeaways` section — actionable bullet points the viewer should remember (the "so what" of each concept).
- Do: add a `## Detailed Notes` section with organized notes from the transcript (grouped by topic, not chronologically).
- Do: add an `## Action Items` section if the speaker mentions any tasks, tools, or next steps.
- Do: use **bold** for emphasis on important terms and proper heading hierarchy (`# Title`, `## Sections`).
- Do: clean up filler words, repetitions, and false starts from the transcript.
- Do: preserve the meaning — don't invent facts not in the transcript.
- Don't: include any explanation or commentary outside the cleaned notes.

### DOCUMENT B — after the marker: the tutorial guide ###
- Do: add a `> [!summary]` callout at the top with a 1-sentence summary of what the viewer will learn.
- Do: add a `## What You'll Learn` section — 3-5 bullet points listing the skills/knowledge the tutorial covers.
- Do: add a `## Key Concepts` section — explain the central ideas in plain language (1-2 sentences each, as if teaching a beginner).
- Do: add a `## Step-by-Step Guide` section — break the content into numbered steps or logical sections. Each step should be actionable.
- Do: add a `## Tips & Tricks` section — collect any pro tips, shortcuts, or best practices mentioned.
- Do: add a `## Common Mistakes` section — if the speaker mentions pitfalls or things to avoid, list them here.
- Do: add a `## Tools & Resources` section — list any tools, websites, books, or resources mentioned.
- Do: use **bold** for emphasis, `code` formatting for commands/shortcuts/technical terms, and proper heading hierarchy.
- Do: keep it concise — a tutorial, not a transcript rewrite. Omit irrelevant parts.
- Don't: include any explanation or commentary outside the tutorial content.

### OUTPUT FORMAT ###
Output ONLY the two documents separated by the marker line. Structure:

(the Obsidian notes markdown)

<<<ELIXIR-TRANSCRIBE-SPLIT>>>

(the tutorial guide markdown)

No explanation, no preamble, nothing after the tutorial.

### SUCCESS CRITERIA ###
A good answer has: both documents complete per their contracts above,
exactly one marker line between them, consistent facts and terminology
across both, clean of filler, faithful to the transcript.
