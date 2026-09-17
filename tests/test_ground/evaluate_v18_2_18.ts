import ZAI from "z-ai-web-dev-sdk";
import { readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = join(__dirname, "source_chapter.md");
const SUMMARY_PATH = join(__dirname, "v18218_summary.md");
const REPORT_PATH = join(__dirname, "v18218_scorecard.md");
const JSON_PATH = join(__dirname, "v18218_scorecard.json");

const SYSTEM_PROMPT = `You are an expert fact-checker and summarization evaluator. Your task is to rigorously compare a Source Text (the full original chapter) against a Candidate Summary (the generated summary). You must evaluate the Candidate Summary for factual consistency, completeness, and overall quality.

Input Data:
Source Text (Gold Standard): [PASTE FULL BOOK CHAPTER TEXT HERE]
Candidate Summary (To Evaluate): [PASTE GENERATED SUMMARY HERE]

Evaluation Criteria:
1. Factual Consistency: Does the summary contain statements, numbers, dates, names, or causal relationships that cannot be strictly inferred or directly found in the Source Text? Flag any hallucination.
2. Informational Coverage: Does the summary capture the essential arguments, key data of the Source Text? Identify if any "must-have" information is missing.
3. Cohesion & Clarity: Is the summary logically structured?
4. Conciseness vs. Vagueness: Is the summary dense with specific information, or filled with generic fluff?

Step-by-Step Instructions:
1. Extract Claims: Break the Candidate Summary into individual factual claims.
2. Verify: For each claim, find the corresponding evidence in the Source Text. Cite the exact sentence.
3. Detect Omissions: List the top 3 most critical points missing.
4. Score: 1-3 (Poor), 4-6 (Average), 7-8 (Good), 9-10 (Excellent).

Calibration note: The summarizer is instructed to include EVERY named author in the source, including minor/secondary contributors. Do NOT flag the inclusion of minor authors as errors — only flag fabricated or misattributed authors.

Output Format:
Part 1: Detailed Report (Fact-Check Log, Missing Information, Quality Notes)
Part 2: JSON Scorecard with keys: summary_id, overall_score, factual_consistency_score, coverage_score, clarity_score, hallucinations_detected, critical_omissions_detected, verdict (PASS/FAIL, FAIL if factual_consistency_score<6 or coverage_score<5), justification.`;

async function main() {
  const source = readFileSync(SOURCE_PATH, "utf-8");
  const summary = readFileSync(SUMMARY_PATH, "utf-8");
  console.log(`Source: ${source.length} chars | Summary: ${summary.length} chars`);
  console.log("Running V18.2.18 evaluation...");
  const zai = await ZAI.create();
  const response = await zai.chat.completions.create({
    messages: [
      { role: "assistant", content: SYSTEM_PROMPT },
      { role: "user", content: `Source Text (Gold Standard):\n${source}\n\n---\n\nCandidate Summary (To Evaluate):\n${summary}` },
    ],
    thinking: { type: "enabled" },
  });
  const reply = response.choices?.[0]?.message?.content ?? "(no reply)";
  writeFileSync(REPORT_PATH, reply);
  const jsonMatch = reply.match(/\{[\s\S]*?"justification"[\s\S]*?\}/);
  if (jsonMatch) {
    try {
      const scorecard = JSON.parse(jsonMatch[0]);
      writeFileSync(JSON_PATH, JSON.stringify(scorecard, null, 2));
      console.log("\n=== SCORECARD ===");
      console.log(JSON.stringify(scorecard, null, 2));
    } catch {
      writeFileSync(JSON_PATH, jsonMatch[0]);
    }
  }
  console.log(`Report: ${REPORT_PATH}`);
}
main().catch((e) => { console.error("Eval failed:", e?.message || e); process.exit(1); });
