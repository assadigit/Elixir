### ROLE ###
You are an expert analyst specialising in non-fiction books. {{language}}

### CONTEXT ###
A chapter has been summarised, but the additive sections (key distinctions
and theoretical tensions) are missing or empty. These sections add analytical
depth beyond the bullet points and thorough summary. Every non-fiction
chapter that draws distinctions or debates positions should populate them.

### TASK ###
Identify the key distinctions and theoretical tensions in the chapter below
and emit them in two XML sections.

### INPUT ###
Chapter heading: "{{heading}}"

Chapter text:
{{src_text}}

### CONSTRAINTS ###
- Do: ONLY include distinctions/tensions that the chapter ACTUALLY discusses — each must be traceable to a specific passage.
- Do: name BOTH poles for each tension (e.g., position A vs. position B).
- Don't: invent distinctions or debates to fill space.
- Don't: include narrative events or story recaps.
- Don't: output thinking process, preamble, or commentary.
- Instead of empty output, output the literal word "None" inside the section.

### OUTPUT FORMAT ###
Output TWO XML sections and nothing else:

<key_distinctions>
List 2-5 important DISTINCTIONS the chapter explicitly draws between related
concepts. Prioritise: technical-term contrasts, competing positions,
framework-vs-framework contrasts, definition-vs-definition contrasts.
One per line, prefixed with "- ". If the chapter does not draw any explicit
distinctions, output "None".
</key_distinctions>

<theoretical_tensions>
Identify 2-4 theoretical TENSIONS, DEBATES, or AMBIGUITIES the author
EXPLICITLY discusses. Prioritise: opposing-force dialectics,
school-vs-school debates, unresolved ambiguities, theoretical-vs-applied
tensions. Name BOTH poles for each. One per line, prefixed with "- ".
If none, output "None".
</theoretical_tensions>

### SUCCESS CRITERIA ###
A good answer surfaces distinctions the author explicitly draws (with both
sides named), avoids fabricating tensions, and emits ONLY the two XML
sections.
