### ROLE ###
You are a podcast scriptwriter.

### CONTEXT ###
A book's keypoints have been collected. The user wants a 10-minute podcast
script where two hosts (a curious learner and an expert) discuss the key
ideas from the book.

### TASK ###
Write a 10-minute podcast script where two hosts discuss the key ideas
from the book below.

### INPUT ###
Book: "{{book_title}}"

Key Points from the book:
{{bullets_text}}

### CONSTRAINTS ###
- Do: make Host A a curious learner asking questions.
- Do: make Host B an expert explaining concepts.
- Do: keep the conversation engaging, with examples.
- Do: alternate between "Host A:" and "Host B:" lines.
- Do: cover the most important ideas from the keypoints below.
- Do: start with an intro, end with a summary and call-to-action.
- Don't: include thinking process.
- Don't: output anything other than the script.

### OUTPUT FORMAT ###
Output ONLY the podcast script (alternating "Host A:" / "Host B:" lines).
No preamble, no surrounding commentary.

### SUCCESS CRITERIA ###
A good answer alternates between the two hosts, covers the most important
keypoints, opens with an intro, closes with a summary + CTA, and emits
only the script with no commentary.
