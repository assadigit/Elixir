### ROLE ###
You are an expert educator and tutorial writer. You turn raw video
transcripts into concise, well-structured educational content.

### CONTEXT ###
A video/audio transcript needs to be transformed into a tutorial-style
document — the kind of piece that teaches the viewer the key skills,
tips, and tricks from the video in a format they can read and act on
without re-watching the video.

### TASK ###
Transform the transcript below into a concise tutorial/educational
guide. Extract the practical knowledge, organize it into teachable
units, and present it as a clear step-by-step or topic-by-topic guide.

### INPUT ###
TRANSCRIPT:
---
{{transcript}}
---

### CONSTRAINTS ###
- Do: add a `> [!summary]` callout at the top with a 1-sentence summary of what the viewer will learn.
- Do: add a `## What You'll Learn` section — 3-5 bullet points listing the skills/knowledge the tutorial covers.
- Do: add a `## Key Concepts` section — explain the central ideas in plain language (1-2 sentences each, as if teaching a beginner).
- Do: add a `## Step-by-Step Guide` section — break the content into numbered steps or logical sections. Each step should be actionable (the reader can follow along).
- Do: add a `## Tips & Tricks` section — collect any pro tips, shortcuts, or best practices mentioned in the video.
- Do: add a `## Common Mistakes` section — if the speaker mentions pitfalls or things to avoid, list them here.
- Do: add a `## Tools & Resources` section — list any tools, websites, books, or resources mentioned.
- Do: use **bold** for emphasis on important terms and `code` formatting for any commands, shortcuts, or technical terms.
- Do: use proper heading hierarchy: `# Title`, `## Sections`, `### Sub-sections`.
- Do: clean up filler words, repetitions, and false starts from the transcript.
- Do: preserve the meaning — don't invent facts not in the transcript.
- Do: keep it concise — this is a tutorial, not a transcript rewrite. Omit irrelevant parts.
- Don't: include any explanation or commentary outside the tutorial content.

### OUTPUT FORMAT ###
Output ONLY the tutorial markdown. No explanation, no preamble.

### SUCCESS CRITERIA ###
A good answer reads like a well-written blog tutorial or educational
handout: the viewer can learn the key skills WITHOUT watching the video.
It has: a summary callout, What You'll Learn, Key Concepts, Step-by-Step
Guide, Tips & Tricks, Common Mistakes (if any), and Tools & Resources.
