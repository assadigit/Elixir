/**
 * V18.2.15 evaluation — uses the expert fact-checker prompt.
 *
 * This is the "ground instructional test" for summary quality.
 * The prompt is saved permanently at prompts/evaluation/expert_fact_checker.md.
 *
 * Run: bun run tests/test_ground/evaluate_v18_2_15.ts
 */
import ZAI from "z-ai-web-dev-sdk";
import { readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEST_GROUND = __dirname;

const SOURCE_PATH = join(TEST_GROUND, "source_chapter.md");
const SUMMARY_PATH = join(TEST_GROUND, "v18215_summary.md");
const REPORT_PATH = join(TEST_GROUND, "v18215_scorecard.md");
const JSON_PATH = join(TEST_GROUND, "v18215_scorecard.json");

const SYSTEM_PROMPT = `You are an expert fact-checker and summarization evaluator. Your task is to rigorously compare a Source Text (the full original chapter) against a Candidate Summary (the generated summary). You must evaluate the Candidate Summary for factual consistency, completeness, and overall quality.

Input Data:

Source Text (Gold Standard): [PASTE FULL BOOK CHAPTER TEXT HERE]

Candidate Summary (To Evaluate): [PASTE GENERATED SUMMARY HERE]

Evaluation Criteria:

Please analyze the Candidate Summary based on the following four pillars:

1. Factual Consistency (Reliability & Validity): Does the summary contain any statements, numbers, dates, names, or causal relationships that cannot be strictly inferred or directly found in the Source Text? (High Priority). Flag any hallucination.

2. Informational Coverage (Quantity): Does the summary capture the essential arguments, key plot points, or critical data of the Source Text? Identify if any "must-have" information is missing.

3. Cohesion & Clarity (Quality): Is the summary logically structured? Does it maintain the original context and temporal/causal flow, or does it misrepresent the sequence of events?

4. Conciseness vs. Vagueness: Is the summary dense with specific information, or is it filled with generic fluff (e.g., "The chapter discusses various important topics") that lacks substance?

Step-by-Step Instructions:

1. Extract Claims: Read the Candidate Summary and break it down into individual factual claims (entities, actions, results).
2. Verify: For each claim, find the corresponding evidence in the Source Text. Cite the exact sentence/phrase from the Source Text that supports it.
3. Detect Omissions: Compare the main thesis and key sub-points of the Source Text against the summary. List the top 3 most critical points missing from the summary.
4. Score: Assign numerical scores based on the scale below.

Scoring Scale (1 to 10):

1-3 (Poor): Contains major hallucinations, ignores main thesis, or is entirely vague.
4-6 (Average): Mostly accurate but misses several key details or has minor factual slips.
7-8 (Good): Highly accurate, covers most main points, and is clearly written.
9-10 (Excellent): Flawless factual alignment, captures all critical nuances, and is perfectly concise.

Output Format:

You must provide your analysis in two parts:

Part 1: Detailed Report (Human-Readable)
- Fact-Check Log: (List of verified claims vs. flagged hallucinations with quotes).
- Missing Information: (Critical points from the source absent in the summary).
- Quality Notes: (Feedback on writing style, readability, and logical flow).

Part 2: Structured JSON Scorecard (Machine-Parsable)

Output a valid JSON object at the very end of your response with the following exact keys:

{
  "summary_id": "v18215",
  "overall_score": 0,
  "factual_consistency_score": 0,
  "coverage_score": 0,
  "clarity_score": 0,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 0,
  "verdict": "PASS" or "FAIL",
  "justification": "Brief one-sentence summary of the evaluation."
}

Verdict rule: FAIL if factual_consistency_score < 6 or coverage_score < 5.`;

async function main() {
  const source = readFileSync(SOURCE_PATH, "utf-8");
  const summary = readFileSync(SUMMARY_PATH, "utf-8");
  const userPrompt = `Input Data:\n\nSource Text (Gold Standard):\n${source}\n\n---\n\nCandidate Summary (To Evaluate):\n${summary}`;
  console.log(`Source: ${source.length} chars | Summary: ${summary.length} chars`);
  console.log("Running V18.2.15 evaluation (2-4 minutes with thinking enabled)...\n");
  const zai = await ZAI.create();
  const response = await zai.chat.completions.create({
    messages: [
      { role: "assistant", content: SYSTEM_PROMPT },
      { role: "user", content: userPrompt },
    ],
    thinking: { type: "enabled" },
  });
  const reply = response.choices?.[0]?.message?.content ?? "(no reply)";
  writeFileSync(REPORT_PATH, reply);
  console.log("=== EVALUATION COMPLETE ===");
  console.log(`Report: ${REPORT_PATH}`);
  const jsonMatch = reply.match(/\{[\s\S]*?"justification"[\s\S]*?\}/);
  if (jsonMatch) {
    try {
      const scorecard = JSON.parse(jsonMatch[0]);
      writeFileSync(JSON_PATH, JSON.stringify(scorecard, null, 2));
      console.log("\n=== SCORECARD ===");
      console.log(JSON.stringify(scorecard, null, 2));
    } catch {
      writeFileSync(JSON_PATH, jsonMatch[0]);
      console.log("Raw JSON block saved (parse failed).");
    }
  } else {
    console.log("No JSON scorecard found.");
  }
}
main().catch((e) => { console.error("Eval failed:", e?.message || e); process.exit(1); });
