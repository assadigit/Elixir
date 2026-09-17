# Evaluation Framework — Four-Pillar Expert Fact-Checker

> **This file is the standing evaluation framework for MarkItDown Pro summary audits.**
> Provided by the project owner (2026-08-31 session) as the permanent, reusable
> evaluation prompt. Do NOT ask for it again — it lives here and ships with every
> version. The ground-truth source chapter for the standing test book
> ("Broken Structures", Salman Akhtar — chapter "1 - IDENTITY AND ITS ORIGINS")
> lives at `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md`.
>
> **How to use:** for every real-run audit, run this prompt with
> Source Text = the ground-truth chapter (or the chapter of the run under audit)
> and Candidate Summary = the generated summary file. Record results as
> `audit/results/AUDIT_V<version>_realrig.md` (or the download folder in the
> sandbox) in exactly the two-part output format defined below.

---

## The Prompt (verbatim — use as-is)

You are an expert fact-checker and summarization evaluator. Your task is to rigorously compare a Source Text (the full original chapter) against a Candidate Summary (the generated summary). You must evaluate the Candidate Summary for factual consistency, completeness, and overall quality.

Input Data:

Source Text (Gold Standard): [PASTE FULL BOOK CHAPTER TEXT HERE]

Candidate Summary (To Evaluate): [PASTE GENERATED SUMMARY HERE]

Evaluation Criteria:

Please analyze the Candidate Summary based on the following four pillars:

Factual Consistency (Reliability & Validity): Does the summary contain any statements, numbers, dates, names, or causal relationships that cannot be strictly inferred or directly found in the Source Text? (High Priority). Flag any hallucination.

Informational Coverage (Quantity): Does the summary capture the essential arguments, key plot points, or critical data of the Source Text? Identify if any "must-have" information is missing.

Cohesion & Clarity (Quality): Is the summary logically structured? Does it maintain the original context and temporal/causal flow, or does it misrepresent the sequence of events?

Conciseness vs. Vagueness: Is the summary dense with specific information, or is it filled with generic fluff (e.g., "The chapter discusses various important topics") that lacks substance?

Step-by-Step Instructions:

Extract Claims: Read the Candidate Summary and break it down into individual factual claims (entities, actions, results).

Verify: For each claim, find the corresponding evidence in the Source Text. Cite the exact sentence/phrase from the Source Text that supports it.

Detect Omissions: Compare the main thesis and key sub-points of the Source Text against the summary. List the top 3 most critical points missing from the summary.

Score: Assign numerical scores based on the scale below.

Scoring Scale (1 to 10):

1-3 (Poor): Contains major hallucinations, ignores main thesis, or is entirely vague.

4-6 (Average): Mostly accurate but misses several key details or has minor factual slips.

7-8 (Good): Highly accurate, covers most main points, and is clearly written.

9-10 (Excellent): Flawless factual alignment, captures all critical nuances, and is perfectly concise.

Output Format:

You must provide your analysis in two parts:

Part 1: Detailed Report (Human-Readable)

Fact-Check Log: (List of verified claims vs. flagged hallucinations with quotes).

Missing Information: (Critical points from the source absent in the summary).

Quality Notes: (Feedback on writing style, readability, and logical flow).

Part 2: Structured JSON Scorecard (Machine-Parsable)

Output a valid JSON object at the very end of your response with the following exact keys:

```json
{
  "summary_id": "[Optional: Insert ID]",
  "overall_score": 0,
  "factual_consistency_score": 0,
  "coverage_score": 0,
  "clarity_score": 0,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 0,
  "verdict": "PASS or FAIL /* FAIL if factual_consistency_score < 6 or coverage_score < 5 */",
  "justification": "Brief one-sentence summary of the evaluation."
}
```

---

## House notes (audit mechanics, not part of the prompt)

- The four pillars map to the standing quality objectives: factual consistency =
  no misattributions/fabrications (pillar 1), coverage = deterministic recall
  floors + content audit (pillar 2), clarity + conciseness = summary quality
  (pillars 3–4).
- The verdict rule is mechanical: FAIL if `factual_consistency_score < 6` OR
  `coverage_score < 5`.
- Cross-check every audit against the run's conversion log: the deterministic
  recall-floor line ("theorists X/Y, conclusion items Z/W") is the honest
  coverage number; the LLM judge's claim-recall measures a different thing.
- Verify file provenance BEFORE auditing: since V18.20.3.7 every summary file
  self-identifies with a `<!-- generated-by: MarkItDown Pro v<version> |
  run_id=… | started=… | bullets=N -->` comment (chapter files: line 3, after
  title+blank; book files: line 1), and the sentinel is `<!-- COMPLETE
  run_id=… -->`. Locate the stamp with the whole-text parser
  (`core.system.provenance.parse_provenance`), never by peeking a fixed
  line — the .3.9 diagnostic's line-2 peek false-flagged every fresh file
  (rig audit F6, fixed in V18.20.3.10). A file without the stamp is a
  pre-.3.7 file (see the V18.20.3.7 CHANGELOG, P6-7). The uploaded file in the
  2026-08-31 session was a stale V18.20.3.4 output (third occurrence) — the
  provenance check catches this in seconds.
- Ground truth for the standing test chapter:
  `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md` (6,425 words,
  9,120 tokens, PDF pages 15–32).
