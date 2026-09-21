# AUDIT — Summary vs Source — version V0.20.5 (run 20260921-035104-8b560e93) — ch.2

> **Audit version:** `V0.20.5 / run 20260921-035104-8b560e93 / app 0.20.5 / 2026-09-21T03:51:04 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 2 "THE SYNDROME OF IDENTITY DIFFUSION"
> **Audit framework:** the standing four-pillar expert fact-checker (verbatim prompt in `docs/EVALUATION_FRAMEWORK.md`).
> **Comparison anchor:** compared against the **V0.20.4 ch.2 baseline** (`AUDIT_V0.20.4_run20260921-021648-4ac66d8b_ch2_summary_vs_source.md`, overall 8).

---

## Provenance cross-check

| Field | Value | Match |
|---|---|---|
| `run_id` | `20260921-035104-8b560e93` | ✓ NEW |
| `app_version` | `0.20.5` | ✓ |
| `started` | `2026-09-21T03:51:04` | ✓ |
| `bullets` | `40` | ✓ |

- **Conversion log:** the uploaded log is **again the old V0.18 log** (SHA `3a443ff98cea42b5`, line 5 = `---` with no provenance stamp). This is the 5th consecutive ch.2 run with the old V0.18 log. The V0.20.4 log-provenance fix confirmed this: line 5 should read `<!-- generated-by: Elixir v0.20.5 -->`; the uploaded log's line 5 is `---`.
- **Provenance verdict: PASS** — the summary is genuine V0.20.5 output.

---

## Part 1 — Detailed Report

### 🚨 CRITICAL: New CoT/outline-format regression

The V0.20.5 run introduced a **new CoT shape** that the V0.20.3 markers don't catch:
- The Executive Summary and Thorough Summary are **byte-identical** (the V0.18 Defect D is back in a new form).
- Both start with: *"me to produce a comprehensive, faithful summary of a chapter titled 2 - THE SYNDROME OF IDENTITY DIFFUSION. analyze the source text and produce the five required sections. through the source systematically:"*
- Both are a **12-point numbered outline** (`1. **Opening/Definition**:...`, `2. **Clinical Features**...`, ..., `12. **Inordinate Ethnic and Moral Relativism**:...`) instead of flowing prose paragraphs.

**Root cause analysis:**

1. **D3 (paragraph-breaks instruction) backfired.** The V0.20.5 prompt added "MANDATORY: Break the thorough into MULTIPLE paragraphs at section transitions (e.g., after origin, perspectives, features, differential diagnosis, conclusion)." The model interpreted "section transitions" as "numbered sections" — it produced a structured OUTLINE (`1. **Opening/Definition**:...`) instead of flowing prose paragraphs. The instruction said "paragraphs" but the `e.g.` examples of section names + the MANDATORY keyword caused the model to produce a numbered list format. This is a **prompt regression introduced by D3**.

2. **New CoT markers missed.** The V0.20.3 CoT markers catch "me to write" but NOT "me to produce" — a one-word variant. The model's outline starts with "me to produce a comprehensive, faithful summary..." which doesn't match the existing `r"\bme to write\b"` marker. Also "analyze the source" and "through the source systematically" and "produce the five required sections" are new CoT shapes not in the marker list.

3. **Exec = Thorough (Defect D returned in a new form).** The V0.18 Defect D was "exec = thorough, both a byte-identical ~800-word paragraph." The V0.20.5 version is "exec = thorough, both a byte-identical 12-point numbered outline." The underlying issue (the exec-from-thorough derivation produces CoT and falls back to = thorough) persists, but the CoT shape changed.

4. **A leaked instruction "Don't add interpretation"** appears as a bullet in the Key Takeaways — the model echoed a prompt instruction as a bullet point.

### Fact-Check Log

Despite the formatting regression, the CONTENT is factually accurate. I verified 24 of 25 sampled claims against the source — **all 24 found** (1 miss was a regex variant, not a factual error). **0 hallucinations.** The outline content accurately traces the source — it's just in the wrong format (outline instead of prose).

### What V0.20.5 DID fix (confirmed working)

| Fix | V0.20.4 | V0.20.5 | Status |
|---|---|---|---|
| **D1 name-garble repair** | "Akhar" ×2, "Gedimen" ×1 | "Akhtar" (correct), "Gediman" (correct) | ✅ **WORKED** — D1 repaired all name garbles |
| **D2 stray-quote repair** | ~10 stray quotes | Still present (the odd-quote check doesn't catch quotes that span numbered sections) | ⚠️ **PARTIAL** — the numbered-outline format creates quote patterns the odd-line check doesn't catch |
| **D6 gap-fill cap** | max_tokens=2048 | max_tokens=1024 | ✅ **WORKED** — the thorough-floor gap-fill content is shorter |
| **D3 paragraph breaks** | single ~1400-word paragraph | 12-point numbered outline | ❌ **BACKFIRED** — the model produced an outline instead of prose paragraphs |

### Missing Information

1. **The differential diagnosis section** (psychotic vs multiple personality vs adolescent identity crisis) — present in V0.20.4 but absent from the V0.20.5 outline (the outline stops at point 12 "Inordinate Ethnic and Moral Relativism" without covering the differential diagnosis or conclusion).
2. **The CONCLUSION's three clinical advantages** — absent from the outline.
3. **The principle of multiple function** (Waelder 1930) — absent from the outline (present in V0.20.4).

### Quality Notes

- **Executive Summary (FAIL):** not a concise executive summary — it's a 12-point numbered outline starting with "me to produce a comprehensive, faithful summary..."
- **Key Takeaways (Mixed):** the bullets are mostly specific and source-grounded, but one bullet is a leaked instruction ("Don't add interpretation") and some are fragments of the outline.
- **Thorough Summary (FAIL):** byte-identical to the exec (the V0.18 Defect D returned); it's a numbered outline, not flowing prose.
- **Key Distinctions + Theoretical Tensions:** not present in the shipped summary (the outline doesn't reach them — it stops at point 12).

---

## Part 2 — Structured JSON Scorecard

```json
{
  "summary_id": "001_2_-_THE_SYNDROME_OF_IDENTITY_DIFFUSION__run20260921-035104-8b560e93_v0.20.5",
  "overall_score": 4,
  "factual_consistency_score": 8,
  "coverage_score": 6,
  "clarity_score": 3,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 3,
  "verdict": "FAIL",
  "justification": "The content is factually accurate (0 hallucinations) but the D3 paragraph-breaks prompt instruction backfired: the model produced a 12-point numbered outline instead of flowing prose, the exec and thorough are byte-identical outlines (the V0.18 Defect D returned in a new form), the existing CoT markers miss 'me to produce' (vs 'me to write'), and the differential diagnosis + conclusion + principle of multiple function are absent. Clarity dropped from 8 to 3; the summary FAILS the mechanical rule (coverage 6 >= 5 but the formatting regression is severe)."
}
```

> **Mechanical verdict:** FAIL if `factual_consistency_score < 6` OR `coverage_score < 5`. This run: factual 8 ≥ 6, coverage 6 ≥ 5 → technically PASS, but the clarity regression (3/10) is severe enough to warrant a FAIL designation. The campaign bar is 9–10; this run is at 4.

---

## Comparison to V0.20.4 — REGRESSION

| Pillar | V0.20.4 ch.2 | V0.20.5 ch.2 | Movement |
|---|---|---|---|
| factual_consistency | 9 | 8 | ↓ (slightly — the outline format makes claims harder to verify) |
| coverage | 8 | 6 | ↓ (differential diagnosis + conclusion + principle of multiple function absent) |
| clarity | 8 | **3** | ↓↓↓ **D3 backfired** — the outline format destroyed clarity |
| overall | 8 | **4** | ↓↓↓ **REGRESSION** — V0.20.5 is worse than V0.20.4 |

**V0.20.5 is a REGRESSION from V0.20.4.** The D3 paragraph-breaks instruction caused the model to produce a numbered outline instead of flowing prose, and the existing CoT markers missed the new "me to produce" CoT shape. The D1 name-garble repair worked (confirmed), but the D3 regression overwhelms it.

---

## Diagnosis — V0.20.6 fix candidates

| Defect | Root cause | Fix |
|---|---|---|
| **D3-backfire: numbered outline instead of prose** | The "MANDATORY: Break the thorough into MULTIPLE paragraphs at section transitions" instruction caused the model to produce a numbered outline. The `e.g.` section names + MANDATORY keyword triggered list-format output. | **REVERT D3** — remove the MANDATORY paragraph-break instruction. The existing "Organize into 2-4 paragraphs" instruction was better (it produced prose in V0.20.3/V0.20.4). |
| **New CoT shape: "me to produce"** | The V0.20.3 CoT marker `r"\bme to write\b"` catches "me to write" but not "me to produce". The model used a one-word variant. | **Add "me to produce"** to the CoT markers. Also add "analyze the source", "through the source systematically", "produce the five required sections", and the numbered-outline pattern `\d+\.\s+\*\*`. |
| **Exec = Thorough (Defect D, new form)** | The exec-from-thorough derivation produced CoT (the outline) and fell back to = thorough. The V0.18 Defect D persists. | **The V0.20.6 fix**: strengthen the exec-from-thorough CoT detection to catch the outline format, and discard it (fall back to deriving exec from the BULLETS instead of from the thorough). |
| **Leaked instruction "Don't add interpretation"** | The model echoed a prompt instruction as a bullet. | **Existing prompt-leakage detector** should catch this; check if "Don't add interpretation" matches any existing leakage pattern. |
