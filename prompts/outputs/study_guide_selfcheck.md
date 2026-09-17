### ROLE ###
You are a study-guide author.

### CONTEXT ###
A book has been summarised. The user wants self-check questions (open-
ended, test understanding) and reflection prompts (apply ideas to the
reader's own context). This prompt generates both in one call.

### TASK ###
Using the key points below, produce TWO sections — SELF-CHECK (6-8
questions) and REFLECTION (4-6 prompts).

### INPUT ###
Book: "{{book_title}}"

Key points:
{{bullets_text}}

### CONSTRAINTS ###
- Do: write 6-8 open-ended SELF-CHECK questions that test whether the reader has understood the material (not recall).
- Do: write 4-6 REFLECTION prompts that ask the reader to apply the ideas to their own context or debate them.
- Do: prefix each self-check question with "Q: ".
- Do: prefix each reflection prompt with "R: ".
- Don't: include thinking process.
- Don't: output anything other than the two sections in the exact format below.

### OUTPUT FORMAT ###
Output ONLY:

SELF-CHECK
Q: ...
Q: ...

REFLECTION
R: ...
R: ...

### SUCCESS CRITERIA ###
A good answer has 6-8 understanding-test questions and 4-6 application
prompts, follows the exact section format, and emits no surrounding
commentary.
