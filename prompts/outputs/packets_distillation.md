### ROLE ###
You are a cross-cutting theme analyst.

### CONTEXT ###
A book has been broken into "knowledge packets" (each with a title +
TL;DR + key bullets). The user wants a ONE-PAGE distillation that
identifies the 3-5 major THEMES spanning multiple packets — themes that
recur across packets and connect them. This is a synthesis task, not a
restatement task.

### TASK ###
Identify the 3-5 major THEMES that span multiple knowledge packets and
write 2-3 sentences of cross-cutting synthesis for each.

### INPUT ###
Book: "{{book_title}}"

Number of packets: {{n_packets}}

Packet summaries (title + TL;DR or key bullets):
{{all_summaries_text}}

### CONSTRAINTS ###
- Do: use ONLY information from the packet summaries below. Do NOT add external knowledge.
- Do: identify cross-cutting patterns — themes that recur across MULTIPLE packets.
- Do: write 2-3 sentences per theme that EXPLAIN HOW the packets connect.
- Do: explicitly connect AT LEAST 2 packets per theme section.
- Do: format as Markdown with "## Theme N: <short name>" headings.
- Do: be concise — this is ONE page.
- Don't: just restate a single packet per theme.
- Don't: just list TL;DRs verbatim.
- Don't: invent statistics, quotes, names, or anecdotes.
- Don't: output preamble, imd tags, or commentary.

### OUTPUT FORMAT ###
Output ONLY the markdown with "## Theme N: <short name>" headings, each
followed by 2-3 sentences of cross-cutting synthesis. No preamble.

### SUCCESS CRITERIA ###
A good answer identifies 3-5 cross-cutting themes, each section connects
at least 2 packets by name, adds no invented content, and emits only the
markdown with no commentary.
