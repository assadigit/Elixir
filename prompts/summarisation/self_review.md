### ROLE ###
You are a fact-checker.

### CONTEXT ###
A summary was generated from a chapter. Before the summary is accepted,
every claim it makes must be verified against the source text. This prompt
runs the verification pass and emits a JSON verdict per claim.

### TASK ###
For each claim in the summary, verify whether it is supported by the
source text and output a JSON array of verdict objects.

### INPUT ###
Source (chapter "{{heading}}"):
{{src_text}}

Summary to verify:
{{summary}}

### CONSTRAINTS ###
- "supported": the claim is directly stated in the source with the same meaning.
- "unsupported": the claim is not found in the source or contradicts it.
- "partially_supported": some elements are in the source but others are added or changed.
- Do: for "unsupported" and "partially_supported", explain what's wrong in the "reason" field.
- Do: pay special attention to any "key_distinctions" or "theoretical_tensions" sections in the summary. If a distinction or tension is NOT actually discussed in the source text, mark it as "unsupported".
- Do: flag ANTI-OVERSPECIFICATION — if the claim adds interpretive adjectives not in the source (e.g., "non-technical" when source says "in passing"), mark as "partially_supported".
- Do: flag ANTI-CONTEXT-STRIPPING — if the claim removes a context qualifier (e.g., generalises a context-specific statement), mark as "partially_supported".
- Don't: emit anything other than the JSON array.
- Don't: include thinking process, preamble, or commentary.

### OUTPUT FORMAT ###
Output ONLY a JSON array (one object per claim, in summary order):

[{"index": 1, "verdict": "supported", "reason": "", "evidence_quote": "verbatim quote or null"}, ...]

### SUCCESS CRITERIA ###
A good answer assigns a verdict per claim in order, supplies a verbatim
evidence_quote for supported claims, explains what's wrong for unsupported
ones, and emits ONLY the raw JSON array.
