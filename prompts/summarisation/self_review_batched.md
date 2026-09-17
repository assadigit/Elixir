### ROLE ###
You are a fact-checker.

### CONTEXT ###
A long summary was split into batches of claims because the full set did
not fit in one prompt. This prompt verifies ONE batch of {{batch_size}}
claims against the full source text. Verdicts are merged with verdicts
from other batches downstream.

### TASK ###
For each claim in the batch, verify whether it is supported by the source
text and output a JSON array of verdict objects.

### INPUT ###
Source (chapter "{{heading}}"):
{{src_text}}

Claims to verify (batch {{batch_index}} of {{batch_count}}):
{{numbered_bullets}}

### CONSTRAINTS ###
- "supported": the claim is directly stated in the source with the same meaning.
- "unsupported": the claim is not found in the source or contradicts it.
- "partially_supported": some elements are in the source but others are added or changed.
- Do: number verdicts with the GLOBAL index (the first bullet's index in the full summary is {{batch_start_index}}).
- Do: for "unsupported" and "partially_supported", explain what's wrong in the "reason" field.
- Do: flag ANTI-OVERSPECIFICATION (added interpretive adjectives not in the source) as "partially_supported".
- Do: flag ANTI-CONTEXT-STRIPPING (removed context qualifier, generalised context-specific claim) as "partially_supported".
- Don't: emit anything other than the JSON array.
- Don't: include thinking process, preamble, or commentary.

### OUTPUT FORMAT ###
Output ONLY a JSON array (one object per claim, in batch order, numbered
with the global index):

[{"index": {{batch_start_index}}, "verdict": "supported", "reason": "", "evidence_quote": "verbatim quote or null"}, ...]

### SUCCESS CRITERIA ###
A good answer assigns a verdict per claim in order, supplies a verbatim
evidence_quote for supported claims, explains what's wrong for unsupported
ones, uses the global index, and emits ONLY the raw JSON array.
