"""V18.10 (Phase 6.6): Pytest golden-master audit plugin.

Ports the TypeScript eval scripts (``tests/test_ground/evaluate_*.ts``) to
a pytest plugin. Runs the 4-pillar audit framework against a candidate
summary using the z-ai-web-dev-sdk LLM.

Usage::

    pytest --audit --audit-summary=path/to/summary.md --audit-source=path/to/source.md

Or programmatically::

    from tests.plugins.golden_master_audit import run_audit
    score = run_audit(summary_path="summary.md", source_path="source.md")
    assert score["overall_score"] >= 9

The plugin is ADDITIVE — it doesn't change existing test behavior. It only
activates when the ``--audit`` flag is passed.

Requirements:
    - z-ai-web-dev-sdk (installed via ``bun add z-ai-web-dev-sdk``)
    - The trust-ground source at ``audit/trust-ground/001_1_..._source.md``

Exit gate: ``overall_score >= 9`` for PASS, ``< 9`` for FAIL.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

__all__ = ["run_audit", "AUDIT_SYSTEM_PROMPT"]


# ── The 4-pillar audit prompt (reconstructed from evaluate_baseline.ts) ─────

AUDIT_SYSTEM_PROMPT = """You are an expert fact-checker and summarization evaluator. Your task is to rigorously compare a Source Text (the full original chapter) against a Candidate Summary (the generated summary). You must evaluate the Candidate Summary for factual consistency, completeness, and overall quality.

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
  "summary_id": "candidate",
  "overall_score": 0,
  "factual_consistency_score": 0,
  "coverage_score": 0,
  "clarity_score": 0,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 0,
  "verdict": "PASS or FAIL",
  "justification": "Brief one-sentence summary of the evaluation."
}"""


def _extract_json_scorecard(reply: str) -> dict[str, Any] | None:
    """Extract the JSON scorecard from the end of the LLM reply."""
    matches = list(re.finditer(r'\{[^{}]*"justification"[^{}]*\}', reply, re.DOTALL))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        return None


def run_audit(
    summary_path: str | Path,
    source_path: str | Path,
    use_sdk: bool = True,
) -> dict[str, Any]:
    """Run the 4-pillar audit on a candidate summary.

    Args:
        summary_path: Path to the candidate summary .md file.
        source_path: Path to the trust-ground source .md file.
        use_sdk: If True, use z-ai-web-dev-sdk via bun. If False, return a
            stub scorecard (for testing the plugin without LLM calls).

    Returns:
        A dict with keys: overall_score, factual_consistency_score,
        coverage_score, clarity_score, hallucinations_detected,
        critical_omissions_detected, verdict, justification.
    """
    # Underscore names: the reads double as existence/permission validation.
    _summary = Path(summary_path).read_text(encoding="utf-8")
    _source = Path(source_path).read_text(encoding="utf-8")

    if not use_sdk:
        return {
            "overall_score": 9,
            "factual_consistency_score": 10,
            "coverage_score": 10,
            "clarity_score": 9,
            "hallucinations_detected": 0,
            "critical_omissions_detected": 0,
            "verdict": "PASS",
            "justification": "Stub audit (no LLM call).",
        }

    # Build a small TS script that runs the audit via z-ai-web-dev-sdk
    audit_script = f"""
import ZAI from "z-ai-web-dev-sdk";
import {{ readFileSync }} from "fs";

const source = readFileSync({json.dumps(str(source_path))}, "utf-8");
const summary = readFileSync({json.dumps(str(summary_path))}, "utf-8");

const SYSTEM_PROMPT = {json.dumps(AUDIT_SYSTEM_PROMPT)};

const userPrompt = `Input Data:

Source Text (Gold Standard):
${{source}}

---

Candidate Summary (To Evaluate):
${{summary}}`;

const zai = await ZAI.create();
const response = await zai.chat.completions.create({{
    messages: [
        {{ role: "assistant", content: SYSTEM_PROMPT }},
        {{ role: "user", content: userPrompt }},
    ],
    thinking: {{ type: "enabled" }},
}});

const reply = response.choices?.[0]?.message?.content ?? "(no reply)";
console.log(reply);
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
        f.write(audit_script)
        script_path = f.name

    try:
        result = subprocess.run(
            ["bun", "run", script_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return {
                "overall_score": 0,
                "factual_consistency_score": 0,
                "coverage_score": 0,
                "clarity_score": 0,
                "hallucinations_detected": -1,
                "critical_omissions_detected": -1,
                "verdict": "ERROR",
                "justification": f"Audit script failed: {result.stderr[:200]}",
            }

        reply = result.stdout
        scorecard = _extract_json_scorecard(reply)
        if scorecard is None:
            return {
                "overall_score": 0,
                "factual_consistency_score": 0,
                "coverage_score": 0,
                "clarity_score": 0,
                "hallucinations_detected": -1,
                "critical_omissions_detected": -1,
                "verdict": "ERROR",
                "justification": "Could not extract JSON scorecard from LLM reply.",
            }

        return scorecard

    except FileNotFoundError:
        return {
            "overall_score": 0,
            "factual_consistency_score": 0,
            "coverage_score": 0,
            "clarity_score": 0,
            "hallucinations_detected": -1,
            "critical_omissions_detected": -1,
            "verdict": "ERROR",
            "justification": "bun not found — install bun to run audits.",
        }
    except subprocess.TimeoutExpired:
        return {
            "overall_score": 0,
            "factual_consistency_score": 0,
            "coverage_score": 0,
            "clarity_score": 0,
            "hallucinations_detected": -1,
            "critical_omissions_detected": -1,
            "verdict": "ERROR",
            "justification": "Audit script timed out (5 min).",
        }
    finally:
        Path(script_path).unlink(missing_ok=True)


# ── Pytest plugin hooks ────────────────────────────────────────────────────


def pytest_addoption(parser):
    """Add the --audit command-line options."""
    parser.addoption(
        "--audit",
        action="store_true",
        default=False,
        help="Run the golden-master audit on a candidate summary.",
    )
    parser.addoption(
        "--audit-summary",
        action="store",
        default=None,
        help="Path to the candidate summary .md file.",
    )
    parser.addoption(
        "--audit-source",
        action="store",
        default=None,
        help="Path to the trust-ground source .md file.",
    )
    parser.addoption(
        "--audit-min-score",
        action="store",
        type=int,
        default=9,
        help="Minimum overall_score for PASS (default: 9).",
    )


def pytest_configure(config):
    """Register the audit marker."""
    config.addinivalue_line("markers", "audit: run the golden-master 4-pillar audit")


@pytest.fixture
def audit_score(request):
    """Fixture that runs the audit and returns the scorecard dict.

    Usage in a test::

        def test_golden_master(audit_score):
            assert audit_score["overall_score"] >= 9
            assert audit_score["verdict"] == "PASS"
    """
    config = request.config
    if not config.getoption("--audit"):
        pytest.skip("--audit not specified")

    summary_path = config.getoption("--audit-summary")
    source_path = config.getoption("--audit-source")

    if not summary_path or not source_path:
        pytest.skip("--audit-summary and --audit-source required")

    return run_audit(summary_path=summary_path, source_path=source_path)
