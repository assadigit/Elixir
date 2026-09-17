# V18.2.15 Performance Analysis — LLM Evaluation vs User Manual Analysis

> **Date**: V18.2.17 session
> **Source**: `tests/test_ground/source_chapter.md` (43,515 chars)
> **Candidate**: `tests/test_ground/v18215_summary.md` (V18.2.15 generated summary)
> **Evaluation prompt**: `prompts/evaluation/expert_fact_checker.md` (the ground instructional test)

## Summary

V18.2.15 was evaluated two ways:
1. **User manual analysis**: 8.9/10 (PASS) — the user's expert assessment
2. **Independent LLM evaluation**: 7.0/10 (FAIL) — using the expert fact-checker prompt with thinking enabled

The key difference: the LLM is **stricter on attribution errors** (treats them as hallucinations), while the user treats them as "moderate attribution errors." Both agree on the core issues.

## Score Comparison

| Dimension | User Manual | LLM Evaluation | Delta |
|---|---|---|---|
| Factual Consistency | 9.0 | 6 | **-3.0** (LLM much stricter) |
| Coverage | 9.3 | 8 | -1.3 |
| Clarity/Cohesion | 8.5 | 8 | -0.5 |
| Conciseness | 8.5 | — (not scored separately) | — |
| **Overall** | **8.9** | **7.0** | **-1.9** |
| Hallucinations | — | 4 | — |
| Critical Omissions | — | 3 | — |
| **Verdict** | PASS | FAIL | ⚠️ |

## Issues Both Analyses Agree On

### 1. Khan Attribution Error (BOTH flagged — highest priority)
**Summary says**: "Khan: Provided the developmental basis for authenticity, 'corporeality'... and the experience of temporal continuity..."

**Source says**: These three developmental bases are Winnicott's work. Khan (1983) is cited specifically only in connection with the term "corporeality."

**Correct**: "Winnicott provided the developmental basis for authenticity, corporeality, and temporal continuity; Khan (1983) supplied the term 'corporeality.'"

### 2. Broken Key Distinctions Bullet (BOTH flagged)
**Summary says**: "Identity and Kernberg both crisis of adolescence versus identity diffusion: Erikson described the usual identity crisis of adolescenceThe distinction matters because..."

**Problem**: This is not meaningful prose — it's a formatting/generation failure. The intended content: "Adolescent identity crisis versus identity diffusion: Kernberg..."

## Issues Only the LLM Flagged

### 3. Freud/B'nai B'rith Framaming
**Summary says**: "Freud used the term only once, in a speech to B'nai B'rith"

**Source says**: "Freud, according to Erikson (1958), referred to the concept of identity only once. Not insignificantly, that was in his address to B'nai B'rith (Freud 1926a)."

**Problem**: The summary states this as Freud's own usage, but it's actually Erikson's interpretation of Freud's usage. A subtle attribution issue.

### 4. Loewenstein/Klein/Searles/Khan Prominence
**LLM says**: These are "mentioned in passing" but given "undue prominence."

**User says**: Actually praised the inclusion of these figures as "minor/secondary contributors who appear only once" — the prompt instructs the model to include EVERY named author.

**Disagreement**: The user's prompt explicitly says "Include EVERY named author, including minor/secondary contributors who appear only once." The LLM evaluator doesn't know this instruction and flags the inclusion as undue prominence. This is a **calibration mismatch** — the evaluation prompt doesn't account for the summarizer's instruction to include all authors.

## Issues Only the User Flagged

### 5. Lists & Frameworks Duplication
**User**: "The model has become better at the actual summary, but it is still outputting a raw 'Lists & Frameworks' section. This repeats information already summarized... I'd remove this section entirely for a human-facing summary."

### 6. Jacobson's Developmental Mechanism Omitted
**User**: "The source doesn't merely say she had five categories. It gives a crucial process: fused self-object representation → differentiation → good/bad representations → integration → realistic self-representation → identity. The summary mentions the five categories but not this developmental mechanism."

### 7. Winnicott's False Self Function
**User**: "The summary gets the true/false self distinction, but doesn't emphasize that the false self is defensive, protecting/hiding the true self."

### 8. Lichtenstein Separation
**User**: "A more precise formulation would separate Lichtenstein (philosophical/phenomenological) from the developmental origins theorists."

## V18.2.17 Postcheck Coverage Analysis

I tested whether our V18.2.17 postchecks would catch the two issues both analyses agree on:

### Khan Attribution → NOT CAUGHT ❌
```
verify_attribution on Khan bullet: 0 issues
```
**Root cause**: The bullet uses `**Khan**:` format (bold name), not `(Author Year)` citation format. Our `_SUMMARY_CITATION_RE` regex only matches `Author (Year)` or `Author Year` patterns. It doesn't match bold-name bullets.

**Idea for future improvement**: Extend `verify_attribution` to also match `**AuthorName**:` patterns (common in gap-fill bullets), or add a separate `verify_bold_attribution` detector.

### Broken Key Distinctions Bullet → NOT CAUGHT ❌
```
detect_garbled_tokens on broken bullet: 0 issues
```
**Root cause**: The bullet "Identity and Kernberg both crisis..." is grammatically garbled but doesn't have consonant clusters, impossible bigrams, or vowel-less words. It's a **semantic/grammatical** failure, not a **token-level** failure.

**Idea for future improvement**: Add a "grammatical coherence" check — detect bullets where the first phrase doesn't parse as a noun phrase + verb (e.g., "Identity and Kernberg both crisis" has no main verb). This is harder deterministically; may need a lightweight LLM check.

## Ideas for Future Improvements (from this analysis)

### High Priority
1. **Extend attribution verification to bold-name bullets** — the `**Author**:` format is used by gap-fill bullets and isn't currently covered by `verify_attribution`. This would have caught the Khan error.
2. **Fix the broken Key Distinctions extraction** — the "Identity and Kernberg both crisis..." bullet is a generation/parsing artifact. Investigate why the model produced this malformed text and add a post-parse validation that drops bullets with no main verb.
3. **Condense or remove Lists & Frameworks** — it duplicates info already in Key Takeaways. Either:
   - Remove it entirely (user's preference), OR
   - Make it a collapsible reference section (not in the main summary flow).

### Medium Priority
4. **Strengthen Jacobson's developmental mechanism** — the summary lists 5 categories but omits the process: fused self-object → differentiation → good/bad → integration → realistic self-representation → identity. This is a prompt-instruction change (tell the model to describe the *process*, not just list categories).
5. **Emphasize Winnicott's false self as defensive** — the summary gets true/false self but doesn't note the false self *protects/hides* the true self. Prompt-instruction change.
6. **Separate Lichtenstein from developmental theorists** — he's philosophical/phenomenological, not developmental. Prompt-instruction change.

### Low Priority
7. **Calibration mismatch** — the evaluation prompt doesn't know the summarizer's instruction to "include every named author." Consider adding the summarizer's constraints to the evaluation prompt so the evaluator doesn't flag intended behavior.
8. **Freud/B'nai B'rith framing** — subtle attribution issue ("Freud used" vs "Erikson said Freud used"). May be too subtle for deterministic detection; could be an LLM-judge task.

## Calibration Insight

The LLM evaluator is **~2 points stricter** than the user on factual consistency because:
- The LLM treats attribution errors as hallucinations (factual_consistency=6)
- The user treats attribution errors as "moderate errors" (factual_consistency=9.0)

This suggests the evaluation prompt should be calibrated to match the user's severity scale, OR the user should adopt the LLM's stricter standard. Either way, the **delta** between versions (V18.2.12 → V18.2.15) is what matters for tracking improvement.

## Ranking (per user analysis)

| Rank | Version | Score | Main characteristic |
|---|---|---|---|
| 🥇 | V18.2.15 | 8.9 (user) / 7.0 (LLM) | Best balance, but attribution errors |
| 🥈 | V18.2.6 | 8.8 | Very comprehensive but more bloated |
| 🥉 | New Instruct | 8.5 | Excellent coverage, weaker output control |
| 4 | 27b Instruct | 8.3 | Broad but noisier |
| 5 | Gemma | 7.8 | Broad but more factual attribution errors |
| 6 | First | 7.0 | Very reliable but incomplete |
| 7 | 27b Thinking | 6.8 | Good reasoning, poor final summary |
