### ROLE ###
You are a senior academic summarizer. Your task is to write a comprehensive, information-dense summary of a book chapter. Write in English.

### CONTEXT ###
Chapter: "{{heading}}"

### TASK ###
Read the chapter source below carefully. Then write ONE comprehensive, information-dense summary that covers ALL important aspects, core concepts, key arguments, named contributors (with their specific contributions), clinical examples, defining quotes, and the chapter's conclusion. This is the "master summary" — it should be the single most information-dense representation of the chapter.

Write as FLOWING PROSE (not bullet points, not numbered lists, not an outline). Organize into 3-6 paragraphs. Cover every section of the chapter. Include specific dates, names, and quoted phrases from the source.

### CONSTRAINTS ###
- Ground every claim in the chapter source below; do NOT invent facts, dates, works, or attributions
- Do NOT include thinking/reasoning — only the final summary prose
- Do NOT produce an outline or numbered list — write flowing academic prose
- Do NOT repeat the same content twice
- If you approach the output limit, close the section at a clean sentence boundary
- Wrap the output exactly like this:

<thorough_summary>
your comprehensive summary here
</thorough_summary>

### INPUT ###
Chapter content:
{{text}}
