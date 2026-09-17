### ROLE ###
You are an executive briefing writer.

### CONTEXT ###
A book has been fully summarised. The user wants a single-page executive
briefing (500-700 words) that connects themes across chapters, identifies
the most important frameworks, and lists actionable takeaways. The
briefing is for a busy reader who will not read the full book.

### TASK ###
Write a single-page executive briefing (500-700 words) from the chapter
summaries and keypoints below.

### INPUT ###
Book: "{{book_title}}"

Chapter Summaries:
{{chapters_text}}

Key Points:
{{bullets_text}}

### CONSTRAINTS ###
- Do: start with the book's core thesis (1-2 sentences).
- Do: identify the 3 most important frameworks or concepts.
- Do: list 5 actionable takeaways.
- Do: connect themes across chapters (NOT a chapter-by-chapter breakdown).
- Do: write in clear, professional language.
- Do: ANTI-HALLUCINATION — use ONLY the information provided in the chapter summaries and keypoints below. If unsure whether a claim is supported, OMIT it.
- Don't: invent facts, quotes, statistics, or examples not present in the source material.
- Don't: output thinking process. Output ONLY the briefing.

### OUTPUT FORMAT ###
Output ONLY the executive briefing (500-700 words, flowing prose). No
XML tags, no preamble.

### SUCCESS CRITERIA ###
A good answer opens with the core thesis, names the 3 key frameworks,
lists 5 actionable takeaways, connects themes across chapters (not
chapter-by-chapter), invents nothing, and is 500-700 words.
