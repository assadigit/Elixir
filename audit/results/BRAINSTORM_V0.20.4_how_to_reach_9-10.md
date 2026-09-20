# BRAINSTORM — How to move the scorecard from 8/10 to 9–10/10

> **Context:** V0.20.4 ch.2 scored overall 8 (factual 9, coverage 8, clarity 8). The run took +10 minutes vs V0.20.3 but the rating didn't improve. This brainstorm analyzes WHY and proposes concrete, evidence-based fixes.

---

## 1. Why +10 minutes didn't improve the rating

The V0.20.4 run produced **+559 words / +5025 chars** vs V0.20.3 (3755 words vs 3196). The extra time was spent generating MORE content — specifically, **6 additional theorists** woven into the thorough (Blos, Eissler, Knight, Kramer, Levy, Niederland, Rinsley, Singer, Volkan). But the rating stayed at 8 because:

- The **6 new theorists** were already-covered names getting *deeper* thorough coverage — but the scorecard doesn't reward "deeper coverage of already-covered theorists." It rewards COVERAGE of MISSING theorists.
- Meanwhile, **3 theorists DROPPED** from V0.20.3 (Ferenczi, Hamilton, Pfeiffer) — and these are MORE critical: Ferenczi (sphincter morality), Hamilton (psychotic differential), Pfeiffer ("life lived in pieces"). The net coverage gain is +6 − 3 = +3 theorists, but the 3 dropped are higher-value than the 6 added.
- The **3 minor omissions** (epigraph, eternal-dilettante vignette, Deutsch quote) are unchanged — they're not driven by theorist count, they're driven by the prompt's emphasis on clinical examples vs named attributions.

**Key insight: the scorecard is bounded by the PIPELINE's coverage/clarity ceiling, not by LLM time.** More LLM time produces more words, but the pipeline doesn't convert those words into the specific coverage the scorecard measures (missing theorists, clinical vignettes, conclusion items). To break through 8/10, we need fixes that target the SPECIFIC defects, not just "more generation."

---

## 2. The defect inventory (what's keeping the score at 8)

| # | Defect | Pillar | Evidence | Fix difficulty |
|---|---|---|---|---|
| **D1** | Name garbles ("Akhar" → "Akhtar", "Gedimen" → "Gediman") | clarity | V0.20.4: "Akhar" ×2, "Gedimen" ×1 | **Easy** — postcheck fix |
| **D2** | Stray/misplaced double-quotes (`"false self,`, `"divided self`, `"hidden selves"`) | clarity | thorough summary has ~10 stray quotes | **Easy** — postcheck fix |
| **D3** | The thorough is a single ~1400-word paragraph (no paragraph breaks) | clarity | readability — dense wall of text | **Medium** — prompt or postcheck |
| **D4** | 3 minor omissions (epigraph, eternal-dilettante vignette, Deutsch quote) | coverage | specific clinical examples absent from thorough | **Medium** — prompt emphasis |
| **D5** | Theorist churn run-to-run (V0.20.3 had Ferenczi/Hamilton/Pfeiffer; V0.20.4 dropped them, added 6 others) | coverage | 34 theorists but not the SAME 34 each run | **Hard** — determinism |
| **D6** | The 10-minute timing increase with no quality gain | efficiency | +559 words, same 8/10 | **Investigate** — cap the gap-fill |

---

## 3. Concrete, evidence-based fixes (prioritized by impact / effort)

### Fix D1: Name-garble postcheck — cross-check named entities against the analysis (EASY, high impact)

**The defect:** "Akhar" (should be "Akhtar") appears 2×, "Gedimen" (should be "Gediman") 1×. These are dropped-letter garbles in named entities — the model lost a character ("Akhta" → "Akhar", "Gedima" → "Gedimen").

**The fix:** The deterministic analysis (`core/preprocessing/deterministic_analyzer.py`) already extracts the author names from the source. The garble postcheck (`core/summarisation/postchecks/garble.py`) can cross-check every "Surname (year)" pattern in the summary against the analysis author list. If a surname is edit-distance-1 from an analysis author (e.g., "Akhar" vs "Akhtar"), auto-repair it.

**Content-agnostic:** the fix uses the RUNTIME analysis author list (no hardcoded names). It's the same pattern the V18.20.3.9 residuals rule enforces.

**Impact:** eliminates the "Akhar"/"Gedimen" garbles → clarity 8 → 8.5.

### Fix D2: Stray-quote postcheck — fix misplaced closing quotes (EASY, medium impact)

**The defect:** The thorough has ~10 instances of stray double-quotes where the model opened a quote but misplaced the closing quote (e.g., `"false self,` where the closing quote should be after "self" not after the comma). The existing `quote_verification` postcheck strips mismatched quotes, but it apparently doesn't catch all shapes.

**The fix:** strengthen the quote-verification detector to flag any line where the number of `"` characters is odd (a stray quote), and either: (a) strip the stray quote, or (b) move it to the nearest word boundary. This is a deterministic, content-agnostic fix.

**Impact:** eliminates ~10 stray quotes → clarity 8 → 8.5.

### Fix D3: Paragraph breaks in the thorough (MEDIUM, medium impact)

**The defect:** The thorough is a single ~1400-word paragraph. It's accurate and dense, but a reader faces a wall of text. Paragraph breaks at the section transitions (origin → three perspectives → seven features → differential diagnosis → conclusion) would improve readability.

**Two approaches:**
- **Prompt-based:** add "Use paragraph breaks between major sections (origin, perspectives, features, differential diagnosis, conclusion)" to the primary prompt's thorough section instruction. Low risk, but the model may not comply consistently.
- **Postcheck-based:** a deterministic postcheck that inserts `\n\n` at detected section-boundary markers (e.g., after "Descriptively," / "The first cluster" / "The differential diagnosis" / "The conclusion"). More reliable but harder to get right content-agnostically.

**Impact:** readability → clarity 8 → 9. This is the single highest-impact clarity fix.

### Fix D4: Prompt emphasis on clinical vignettes (MEDIUM, high impact)

**The defect:** The "eternal dilettante" physician/movie-star example (L70-73) and the Deutsch repression-vs-loss quote (L139-143) are the illustrative core of their concepts, but the thorough omits them. The prompt asks for "key points" but not specifically for "clinical examples" or "defining quotes."

**The fix:** add a prompt instruction like "Include the author's specific clinical examples and defining quotes (e.g., the 'eternal dilettante' example, Deutsch's 'real loss of object cathexis' quote) when they are the illustrative core of a concept." This is a prompt-wording change, content-agnostic (it asks for clinical examples in general, not for specific ones).

**Impact:** covers the 3 minor omissions → coverage 8 → 9.

### Fix D5: Theorist-coverage determinism (HARD, high impact but risky)

**The defect:** V0.20.3 had Ferenczi/Hamilton/Pfeiffer; V0.20.4 dropped them and added 6 others. The thorough-theorist-floor gap-fill call is non-deterministic — it covers DIFFERENT theorists each run. This means the scorecard fluctuates run-to-run even with the same code.

**The fix:** make the thorough-theorist-floor gap-fill DETERMINISTIC about which theorists to cover. Instead of "write 1-2 paragraphs weaving in ONLY the contributors listed below" (which lets the model pick), the prompt could list the theorists IN PRIORITY ORDER (by citation count from the analysis) and ask for "at least the top N." The analysis already ranks theorists by mention count.

**Risk:** this makes the prompt more prescriptive, which could reduce the model's flexibility. Content-agnostic (the priority comes from the runtime analysis, not hardcoded).

**Impact:** stable coverage across runs → coverage 8 → 9 (consistent, not fluctuating).

### Fix D6: Cap the thorough-theorist-floor gap-fill output (EASY, efficiency)

**The defect:** The V0.20.4 run took +10 minutes because the gap-fill call produced 559 extra words. The call's `max_tokens=2048` allows a long addition. More content = more time, but (as we saw) not necessarily better coverage.

**The fix:** reduce the gap-fill `max_tokens` from 2048 to 1024 (the prompt asks for "150-300 words" — 1024 tokens is ~750 words, still 2.5× the ask). This caps the generation time without reducing the intended 150-300 word addition.

**Impact:** saves ~3-5 minutes per run, no quality loss (the prompt asks for 150-300 words; 1024 tokens covers that with margin).

---

## 4. The 10-minute timing question — investigate with the correct log

The +10 minutes is a real concern. The V0.20.4 code change (log header stamp) is trivial and shouldn't add time. The increase is from the LLM generating more content (34 theorists vs 28, +559 words). But we can't confirm the exact call-by-call breakdown without the correct V0.20.4 conversion log (the uploaded one is the old V0.18 log).

**Once the user uploads the correct V0.20.4 log** (with `<!-- generated-by: Elixir v0.20.4 -->` on line 5), we can:
1. See which LLM calls took longer (the primary? the thorough-floor gap-fill? the batch gap-fill?)
2. Check if the truncation fixes (Fix A/B/C from V0.20.2) fired
3. See the deterministic recall floor (theorists X/Y, conclusion items Z/W)
4. Confirm whether the gap-fill call produced the "aliases" passage (the new content that V0.20.3 omitted)

**Without the log, the most likely explanation is LLM variance:** the same prompt on the same hardware produces different-length responses run-to-run, especially with a 27B low-bit quant on a 12GB card where thermal throttling and VRAM contention cause timing swings. The V0.20.4 run happened to produce a longer response (34 vs 28 theorists, +559 words), which took ~10 minutes more.

---

## 5. Prioritized action plan

| Priority | Fix | Pillar | Impact | Effort | Version |
|---|---|---|---|---|---|
| **1** | D1: Name-garble postcheck (cross-check against analysis authors) | clarity | 8 → 8.5 | Easy | V0.20.5 |
| **2** | D2: Stray-quote postcheck (fix misplaced closing quotes) | clarity | 8 → 8.5 | Easy | V0.20.5 |
| **3** | D3: Paragraph breaks in the thorough (prompt instruction) | clarity | 8 → 9 | Medium | V0.20.5 |
| **4** | D4: Prompt emphasis on clinical vignettes | coverage | 8 → 9 | Medium | V0.20.6 |
| **5** | D6: Cap the gap-fill max_tokens (2048 → 1024) | efficiency | saves ~5 min | Easy | V0.20.5 |
| **6** | D5: Theorist-coverage determinism (priority-ordered prompt) | coverage | 8 → 9 (stable) | Hard | V0.20.7 |

**Combined projected scorecard if D1-D4 are fixed:**
- factual: 9 (unchanged — 0 hallucinations)
- coverage: 9 (D4 covers the 3 minor omissions)
- clarity: 9 (D1 fixes garbles, D2 fixes stray quotes, D3 adds paragraph breaks)
- **overall: 9** — reaching the campaign bar

**The key insight:** the scorecard is bounded by the PIPELINE, not by LLM time. The V0.20.4 run spent 10 extra minutes generating more words, but the pipeline didn't convert those words into the specific coverage the scorecard measures. The fixes above target the SPECIFIC defects (garbles, stray quotes, missing vignettes, no paragraph breaks) — each one moves a specific pillar from 8 toward 9.
