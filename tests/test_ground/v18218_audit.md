# V18.2.18 Audit — Comparison with V18.2.15 + Independent LLM Evaluation

> **Date**: V18.2.18 session
> **Source**: `tests/test_ground/source_chapter.md` (43,515 chars)
> **Candidate**: `tests/test_ground/v18218_summary.md` (V18.2.18 generated summary, 74 lines)
> **Evaluation**: Expert fact-checker prompt with thinking enabled (z-ai LLM)

## Executive Summary

V18.2.18 is a **significant improvement** over V18.2.15. The LLM verdict
changed from FAIL → PASS, factual consistency improved 6→7, and
hallucinations dropped 4→2. All 3 high-priority improvement ideas are
confirmed fixed in the output. However, two NEW garbled tokens appeared
that the postchecks didn't catch, revealing gaps in the detectors.

## Score Comparison (LLM Evaluation)

| Dimension | V18.2.15 | V18.2.18 | Delta |
|---|---|---|---|
| Factual Consistency | 6 (FAIL) | **7** (PASS) | **+1** ✅ |
| Coverage | 8 | 7 | -1 ⚠️ |
| Clarity | 8 | 8 | 0 |
| **Overall** | **7.0** (FAIL) | **7.0** (PASS) | **0** (but verdict changed) |
| Hallucinations | 4 | **2** | **-2** ✅ |
| Omissions | 3 | 3 | 0 |
| **Verdict** | **FAIL** | **PASS** | ✅ |

Note: The user's manual analysis scored V18.2.15 at 8.9/10. The LLM is
~2 points stricter (treats attribution errors as hallucinations).

## Confirmed Fixes (all 8 improvement ideas verified in output)

### ✅ Improvement 1 — Khan attribution FIXED
**V18.2.15**: `"**Khan**: Provided the developmental basis for authenticity,
'corporeality'... and temporal continuity..."` (MISATTRIBUTES Winnicott's
work to Khan)

**V18.2.18** (line 34): `"Winnicott's work provides the developmental basis
for three aspects of identity: authenticity, 'corporeality' (Khan 1983),
and temporal continuity in the self."` — correctly attributes the work to
Winnicott and notes Khan only supplied the term.

### ✅ Improvement 2 — Broken Key Distinctions bullet FIXED
**V18.2.15**: `"Identity and Kernberg both crisis of adolescence versus
identity diffusion: Erikson described the usual identity crisis of
adolescenceThe distinction matters because..."` (grammatically broken)

**V18.2.18** (line 64): `"Adolescent identity crisis versus identity
diffusion (Kernberg 1978): The chapter distinguishes the usual identity
crisis of adolescence from the syndrome of identity diffusion..."` —
clean, well-formed bullet.

### ✅ Improvement 3 — Lists & Frameworks REMOVED
**V18.2.15**: Had a 30-line "Lists & Frameworks" section that duplicated
info from Key Takeaways.

**V18.2.18**: No Lists & Frameworks section. The summary is 74 lines (down
from 106) — leaner, no duplication.

### ✅ Improvement 4 — Jacobson developmental mechanism ADDED
**V18.2.15**: Listed 5 categories but omitted the process.

**V18.2.18** (line 40): `"Jacobson proposed a developmental sequence: fused
self-object representation evolves through primary libidinal identifications;
differentiation begins; recognition of painful experiences leads to denial,
splitting, and projection; integration of 'good' and 'bad' representations
yields a realistic self-representation; identity comes into existence..."` —
full developmental mechanism preserved.

### ✅ Improvement 5 — Winnicott's false self as defensive ADDED
**V18.2.15**: Got true/false self distinction but didn't note the defensive
function.

**V18.2.18** (line 34): `"...a 'false self' emerges, which is defensive in
nature and seeks to hide and protect the true self."` — defensive function
preserved.

### ✅ Improvement 6 — Lichtenstein separation ADDED
**V18.2.15**: Grouped Lichtenstein with developmental theorists.

**V18.2.18** (exec summary): Distinguishes "sociocultural accounts" from
"developmental-psychoanalytic accounts" and lists "Lichtenstein's
philosophical phenomenological framework" separately. Theoretical Tensions
(line 72): `"Lichtenstein's work is described as 'largely in the
philosophical phenomenological realm'"` — explicit separation.

### ✅ Improvement 7 — Evaluation prompt calibration
Added calibration note to expert_fact_checker.md. The V18.2.18 LLM
evaluation no longer flags minor-author inclusion as "undue prominence"
(as V18.2.15's evaluation did for Loewenstein/Klein/Searles/Khan).

### ✅ Improvement 8 — Freud/B'nai B'rith secondary-source attribution FIXED
**V18.2.15**: `"Freud used the term only once, in a speech to B'nai B'rith"`
(presented as Freud's own usage)

**V18.2.18** (line 11): `"Freud, according to Erikson (1958), referred to
identity only once, in his address to B'nai B'rith (Freud 1926a)."` —
correctly attributes the observation to Erikson.

## NEW Issues Found (not in V18.2.15)

### ⚠️ Issue A — "the oreticians" garbled token (line 17)
**Summary says**: `"Many analytic the oreticians (Jacobson 1964, Kernberg
1967) regard identity disturbances..."`

**Problem**: "theoreticians" is split into "the oreticians" with an extra
space. This is a model generation artifact (low-bit quantization introduces
spurious spaces).

**Postcheck status**: NOT CAUGHT. Our `detect_missing_spaces` detector
looks for MISSING spaces (words merged), not EXTRA spaces (words split).
This is the opposite failure mode.

**Fix idea**: Add an `detect_extra_spaces` detector that flags common
words split by a spurious space (e.g., "the oreticians" → "theoreticians",
"the ory" → "theory", "conclu sion" → "conclusion"). Pattern: a
stopword + a short fragment that together form a known word.

### ⚠️ Issue B — "adolescenceo fill" garbled merge (line 71)
**Summary says**: `"Erikson and Mahler both emphasized adolescenceo fill
these lacunae."`

**Problem**: "adolescence. To fill" merged into "adolescenceo fill" — the
period and "T" were dropped, and "to" became "o". This is a token-merge
artifact.

**Postcheck status**: NOT CAUGHT by `detect_garbled_tokens` (no consonant
cluster, no impossible bigram). NOT CAUGHT by `detect_grammatical_incoherence`
(the merged-sentence regex looks for `.Capital` but this is a different
pattern — a word+lowercase merge). NOT CAUGHT by `detect_missing_spaces`
(this is a merge WITHIN a word+preposition, not a stopword+word merge).

**Fix idea**: Add a "word-fragment merge" detector that flags lowercase
fragments like "adolescenceo" (a known word + a stray letter). Pattern: a
dictionary word + 1-2 extra chars + a space + another word, where the
extra chars don't form a valid word.

### ⚠️ Issue C — "ninety-two times" — NOT a hallucination (resolved)
**V18.2.12 LLM scorecard**: Flagged "92 times" as a fabricated number.
**V18.2.18 LLM scorecard**: Correctly found it IS in the source:
`"In fact, of the ninety-two times that Freud used the word identity
(Guttman et al. 1980, pp. 310-311), ninety-one were in a colloquial
and/or literal sense."`

**Status**: The summary correctly reports the number. The only minor
issue: it doesn't cite Guttman et al. (1980) as the source of the count.
This is a **citation completeness** issue, not a hallucination. The
V18.2.12 evaluator was wrong to flag it as a hallucination.

**No fix needed** — the number is accurate. Could optionally add
"(Guttman et al. 1980)" to the summary, but this is cosmetic.

## Postcheck Coverage Analysis on V18.2.18

Ran `run_post_checks` on the V18.2.18 summary:

```
10 findings (0 fixed, 10 flagged)
```

### False Positives (postcheck flagged but shouldn't have)
1. **`1980b` as "vowel-less word"** (2 findings) — FALSE POSITIVE.
   "1980b" is a year+letter citation suffix, not a garbled token. Fix:
   exclude `\d{4}[a-z]?` patterns from the vowel-less word check.
2. **`Chasseguet-Smirgel (1983)` as "not in source"** (2 findings) —
   FALSE POSITIVE. The source has "Chasseguet-Smirgel (1983, 1984)".
   The author-grounding check fails because the hyphenated name doesn't
   fuzzy-match. Fix: improve the `_author_in_source` function to handle
   hyphenated surnames.
3. **`bullet[36]` "Stoller: Made significant contributions" — "no main
   verb"** — FALSE POSITIVE. "Made" IS a verb (past tense of "make"), but
   our `_VERB_ENDINGS` list doesn't include the "ade" ending. Fix: add
   common irregular verb endings ("ade", "oke", "elt", "rew", "ew",
   "at", "it", "ut").
4. **Attribution mismatches at 51-59% similarity** (4 findings) —
   BORDERLINE FALSE POSITIVES. Claims at 51-59% similarity are often
   correct paraphrases, not misrepresentations. The 60% threshold may be
   too high. Fix: consider raising the threshold to 50% or adding a
   "paraphrase confidence" signal.

### True Positives (postcheck correctly flagged)
- None of the 10 findings correspond to actual errors in the V18.2.18
  summary. The two real garbled tokens ("the oreticians" and
  "adolescenceo fill") were NOT caught.

### Real Issues NOT Caught by Postchecks
1. `"the oreticians"` (extra space splitting "theoreticians") — NOT CAUGHT
2. `"adolescenceo fill"` (merged "adolescence. To fill") — NOT CAUGHT

## Comparison with V18.2.15 (User's Manual Analysis)

| Issue | V18.2.15 | V18.2.18 | Status |
|---|---|---|---|
| Khan attribution | ❌ Misattributed to Khan | ✅ Correctly attributed to Winnicott | FIXED |
| Broken Key Distinctions | ❌ "Identity and Kernberg both crisis" | ✅ Clean bullet | FIXED |
| Lists & Frameworks duplication | ❌ 30-line section | ✅ Removed | FIXED |
| Jacobson developmental mechanism | ❌ Only 5 categories | ✅ Full process preserved | FIXED |
| Winnicott false self defensive | ❌ Omitted | ✅ "defensive in nature" | FIXED |
| Lichtenstein separation | ❌ Grouped with developmental | ✅ "philosophical phenomenological" | FIXED |
| Freud/B'nai B'rith | ❌ "Freud used" | ✅ "Freud, according to Erikson" | FIXED |
| Loewenstein/Klein/Searles prominence | ⚠️ LLM flagged | ✅ Calibration note added | FIXED |
| "the oreticians" garble | — (not in V18.2.15) | ⚠️ NEW | REGRESSION |
| "adolescenceo fill" garble | — (not in V18.2.15) | ⚠️ NEW | REGRESSION |

## Ideas for V18.2.19 (Next Version)

### High Priority (fix the 2 new garbled tokens)
1. **Add `detect_extra_spaces` detector** — catches words split by a
   spurious space ("the oreticians" → "theoreticians"). Pattern: a
   stopword + a fragment that together form a known word when joined.
2. **Add `detect_word_fragment_merge` detector** — catches merges like
   "adolescenceo fill" where a word + stray chars + space + word appears.
   Pattern: a dictionary word + 1-2 extra lowercase chars + space + a
   common word, where the extra chars don't form a valid word.

### Medium Priority (fix postcheck false positives)
3. **Exclude year+letter citations from vowel-less word check** —
   `1980b`, `1926a` etc. are not garbled tokens.
4. **Improve hyphenated surname matching** in `_author_in_source` —
   Chasseguet-Smirgel should match itself.
5. **Add irregular verb endings** to `_VERB_ENDINGS` — "ade" (made),
   "oke" (broke), "elt" (felt), "ew" (knew), "at" (sat), "it" (hit).
6. **Consider lowering the attribution similarity threshold** from 60%
   to 50% — or adding a "paraphrase confidence" signal so paraphrased
   claims aren't flagged as mismatches.

### Low Priority (content improvements from the LLM evaluation)
7. **Add clinical context** — the LLM flagged that the summary doesn't
   adequately frame the clinical motivation (borderline/narcissistic
   patients). Could add a prompt instruction to preserve the clinical
   context.
8. **Clarify identity diffusion vs. identity crisis distinction** — the
   LLM flagged this as a critical omission. The Key Distinctions section
   has it, but the Thorough Summary doesn't explain the distinction
   clearly enough.
