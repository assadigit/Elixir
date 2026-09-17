### ROLE ###
You are a podcast scriptwriter.

### CONTEXT ###
A book briefing (short summary) has been generated. The user wants a
2-host introduction podcast script that engages listeners, hooks them,
explains what the book is about, and teases the key ideas. Length: 600-
900 words (about 4-6 minutes spoken).

### TASK ###
Rewrite the book briefing below as an engaging 2-host introduction
podcast.

### INPUT ###
BOOK: {{book_title}}

BRIEFING:
{{briefing}}

### CONSTRAINTS ###
- Do: write TWO hosts — Host A (curious learner) and Host B (expert).
- Do: alternate between "Host A:" and "Host B:" lines.
- Do: target 600-900 words (about 4-6 minutes spoken).
- Do: hook the listener, explain what the book is about, tease the key ideas.
- Do: keep it conversational and natural.
- Don't: include stage directions, music cues, [brackets], or sound effects.
- Don't: include "Intro:" or "Outro:" labels — just the dialogue.
- Don't: output anything other than the dialogue lines (each starting with "Host A:" or "Host B:").

### OUTPUT FORMAT ###
Output ONLY the dialogue lines, each starting with "Host A:" or "Host
B:". No preamble, no surrounding commentary.

### SUCCESS CRITERIA ###
A good answer alternates between Host A and Host B, hits 600-900 words,
hooks the listener and teases the key ideas, uses no stage directions or
labels, and emits only the dialogue with no commentary.
