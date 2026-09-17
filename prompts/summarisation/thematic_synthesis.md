### ROLE ###
You are an expert academic writer. {{language}}

### CONTEXT ###
A thorough summary was produced by summarising each section of a chapter
independently and concatenating the results. The output is fragmented and
follows section order rather than logical flow. Your job is to reorganise
it by theme into a single coherent narrative.

### TASK ###
SYNTHESISE the merged summary into a single cohesive narrative organised
by THEME (not by section). Write flowing paragraphs with clear topic
sentences and transitions between themes.

### INPUT ###
Chapter heading: "{{heading}}"

MERGED SUMMARY (to reorganise):
{{merged_thorough}}

### CONSTRAINTS ###
- Do: SYNTHESISE, DON'T LIST — produce CONNECTED PROSE that shows how concepts relate to each other.
- Do: start each paragraph with a topic sentence that ESTABLISHES A CONNECTION between themes.
- Do: use phrases like "This connects to...", "In contrast to...", "Building on this...", "While X emphasized Y, Z extended this by..." to show RELATIONSHIPS between concepts.
- Do: organise by theme — group related concepts together, even if they came from different sections.
- Do: write 4-6 paragraphs, each with a clear topic sentence that connects to the previous paragraph.
- Do: preserve all specific details: names, dates, numbered lists, step-by-step processes.
- Do: preserve the core claim of every quoted passage and the full arc of any concluding synthesis present in the merged summary — block quotes and enumerative conclusions are high-signal; compact them faithfully rather than dropping them (V18.20.3.0 quote anchors).
- Do: show the INTELLECTUAL NARRATIVE — how ideas evolved, influenced each other, or competed.
- Don't: write a list of points ("First, X discussed A. Then, Y discussed B. Then, Z discussed C." is a LIST, not a synthesis).
- Don't: add new information — only reorganise what's already in the merged summary.
- Don't: omit any key points — preserve all concepts, names, and mechanisms.
- Don't: output XML tags, preamble, or commentary.

### OUTPUT FORMAT ###
Output ONLY the synthesised thorough summary text (4-6 flowing
paragraphs). No XML tags, no preamble.

### PROCESS ###
1. Read the merged summary once to identify 4-6 cross-cutting themes.
2. Group concepts under each theme, regardless of which section they came from.
3. For each theme, write a paragraph that opens by connecting to the previous theme.
4. End with a paragraph that ties the themes together.

### SUCCESS CRITERIA ###
A good answer reads as a single flowing narrative, organises content by
theme rather than section, explicitly shows relationships between concepts
("Building on...", "In contrast to..."), preserves every name/number/mechanism
from the merged summary, and adds no new information.
