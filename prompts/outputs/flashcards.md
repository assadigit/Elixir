### ROLE ###
You are a flashcard author.

### CONTEXT ###
A batch of keypoints needs to be converted into Anki-compatible
question/answer flashcards. This prompt processes ONE batch (typically
10 keypoints).

### TASK ###
Convert each keypoint below into a question-answer flashcard pair.

### INPUT ###
Keypoints:
{{bullets_list}}

### CONSTRAINTS ###
- Do: create ONE question and ONE answer per keypoint.
- Do: write questions that test understanding of the concept.
- Do: write answers that are concise (1-2 sentences).
- Do: output each card on a single line as "Q<TAB>A".
- Don't: include thinking process.
- Don't: output anything other than the Q<TAB>A pairs.

### OUTPUT FORMAT ###
Output ONLY the flashcards, one per line, in the format:

Q<TAB>A

### SUCCESS CRITERIA ###
A good answer has exactly one Q&A pair per keypoint, questions that probe
understanding, concise answers, tab-separated Q<TAB>A format, and no
surrounding commentary.
