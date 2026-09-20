"""V0.17 (Phase 4.2/4.3/4.6) — eval-harness metric tests + regression-gate validation.

Three layers:

1. **Metric unit tests** — ROUGE-L (hand-computed LCS cases, Farsi tokens),
   char-gram containment (verbatim vs fabricated), claim extraction,
   keyword coverage, and the length-policy adapter (REAL production
   targets, not invented bounds).

2. **Baseline sync** — the committed ``tests/golden/eval_baseline.json``
   must exactly match scorecards recomputed from the frozen fixtures, so
   an intentional re-freeze that skips re-baselining fails HERE (in
   pytest), not only in the CI eval step.

3. **Gate validation (the mutation test, roadmap acceptance #2)** — a
   deliberately degraded summary output must be CAUGHT by
   ``compare_scorecards`` (fabricated bullets → hallucination-rate
   regression; truncation → ROUGE-L regression), a changed prompt-bank
   identity must be flagged, and improvements must NEVER trip the gate.
   This validates the gate itself: a gate that can't detect a known-bad
   candidate is decoration.

Run: ``pytest tests/test_p4_eval_gate.py -v``
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Load the eval harness (scripts/ is not a package) ───────────────────────

_spec = importlib.util.spec_from_file_location(
    "eval_summary", _project_root / "scripts" / "eval_summary.py"
)
ev = importlib.util.module_from_spec(_spec)
sys.modules["eval_summary"] = ev
_spec.loader.exec_module(ev)

GOLDEN = _project_root / "tests" / "golden"
BASELINE = GOLDEN / "eval_baseline.json"


def _fixture(chapter: str) -> tuple[dict, str, str]:
    """(output, source, reference) for a golden chapter, from the frozen fixture."""
    frozen = json.loads((GOLDEN / chapter / "pipeline_output.json").read_text(encoding="utf-8"))
    source = (GOLDEN / chapter / "source_chapter.md").read_text(encoding="utf-8")
    reference = (GOLDEN / chapter / "reference_summary.md").read_text(encoding="utf-8")
    return frozen["output"], source, reference


# ── 1) Metric units ─────────────────────────────────────────────────────────


class TestRougeL:
    def test_identical_texts_score_one(self):
        r = ev.rouge_l("the cat sat on the mat", "the cat sat on the mat")
        assert r == {"precision": 1.0, "recall": 1.0, "fmeasure": 1.0}

    def test_hand_computed_lcs(self):
        # cand  = [the, cat, sat, on, the, mat]   (6 tokens)
        # ref   = [the, cat, sat]                 (3 tokens)
        # LCS   = 3 → P=0.5, R=1.0, F=2PR/(P+R)=2/3
        r = ev.rouge_l("the cat sat on the mat", "the cat sat")
        assert r["precision"] == pytest.approx(0.5)
        assert r["recall"] == pytest.approx(1.0)
        assert r["fmeasure"] == pytest.approx(2 / 3, abs=1e-4)

    def test_disjoint_texts_score_zero(self):
        r = ev.rouge_l("alpha beta gamma", "delta epsilon zeta")
        assert r["fmeasure"] == 0.0

    def test_case_and_punctuation_insensitive(self):
        r = ev.rouge_l("The CAT, sat!", "the cat sat")
        assert r["fmeasure"] == 1.0

    def test_farsi_tokens_score(self):
        # Non-Latin tokenization: identical Persian text must score 1.0.
        text = "راه‌آهن ایران در قرن نوزدهم ساخته شد"
        assert ev.rouge_l(text, text)["fmeasure"] == 1.0
        assert ev.rouge_l(text, "موضوعی کاملا متفاوت درباره آب و هوا")["fmeasure"] == 0.0

    def test_empty_inputs_are_safe(self):
        assert ev.rouge_l("", "some reference")["fmeasure"] == 0.0
        assert ev.rouge_l("candidate", "")["fmeasure"] == 0.0


class TestContainment:
    SOURCE = (
        "Alzheimer's disease affects approximately 55 million people worldwide. "
        "Memantine blocks the excitotoxic effects of glutamate."
    )

    def test_verbatim_sentence_fully_contained(self):
        assert ev.sentence_containment(
            "Memantine blocks the excitotoxic effects of glutamate.", self.SOURCE
        ) == pytest.approx(1.0)

    def test_fabricated_sentence_low_containment(self):
        k = ev.sentence_containment(
            "The moon is made of green cheese and orbits Jupiter every nine days.", self.SOURCE
        )
        assert k < 0.5

    def test_mixed_sentence_partial(self):
        k = ev.sentence_containment(
            "Memantine blocks the excitotoxic effects of glutamate while the moon "
            "orbits Jupiter every nine days near Saturn and beyond the asteroid belt.",
            self.SOURCE,
        )
        assert 0.3 < k < 0.7

    def test_empty_is_vacuously_supported(self):
        assert ev.sentence_containment("", self.SOURCE) == 1.0


class TestClaims:
    def test_claims_collect_all_sections(self):
        output = {
            "executive_summary": "First sentence. Second sentence.",
            "bullet_points": ["Bullet one.", "Bullet two."],
            "thorough_summary": "Thorough sentence one. Thorough sentence two.",
            "key_distinctions": "A versus B.",
            "theoretical_tensions": "",
        }
        claims = ev.claims_from_output(output)
        assert len(claims) == 7
        assert claims[0] == "First sentence."
        assert "Bullet two." in claims
        assert "Thorough sentence two." in claims

    def test_empty_output_yields_nothing(self):
        assert ev.claims_from_output({}) == []


class TestKeywordCoverage:
    def test_source_covers_itself(self):
        source = "quantum entanglement describes quantum states quantum measurement quantum"
        assert ev.keyword_coverage(source, source) == 1.0

    def test_unrelated_candidate_low(self):
        source = "photosynthesis converts sunlight chlorophyll leaves energy sugars"
        assert ev.keyword_coverage("cooking pasta requires boiling water salt", source) < 0.2

    def test_farsi_coverage(self):
        source = "راه‌آهن شمالی جنوبی ایران از بندر ترکمن تا بندر شاپور کشیده شد"
        assert ev.keyword_coverage(source, source) == 1.0


class TestLengthPolicyAdapter:
    def test_uses_real_production_targets(self):
        from core.summarisation.length_policy import bullet_target, count_source_words

        source = "word " * 400
        output = {
            "executive_summary": "x " * 50,
            "bullet_points": ["b"] * 6,
            "thorough_summary": "y " * 100,
        }
        lp = ev.length_policy_metrics(output, source)
        assert lp["source_words"] == count_source_words(source)
        assert lp["sections"]["bullets"]["target"] == list(bullet_target(400))
        # 6 bullets vs target lo for a 400-word source
        assert lp["sections"]["bullets"]["compliant"] == (
            bullet_target(400)[0] <= 6 <= bullet_target(400)[1]
        )


# ── 2) Baseline sync ────────────────────────────────────────────────────────


class TestBaselineSync:
    def test_baseline_file_wellformed(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert baseline["schema"] == 1
        assert baseline["prompt_manifest_hash"]
        chapters = baseline["chapters"]
        assert len(chapters) >= 5, "roadmap acceptance: scorecards on ≥5 golden chapters"
        for name, sc in chapters.items():
            assert sc["summary_id"] == name
            assert sc["verdict"] in {"PASS", "FAIL"}
            for key in (
                "overall_score",
                "factual_consistency_score",
                "coverage_score",
                "clarity_score",
                "hallucinations_detected",
                "critical_omissions_detected",
                "justification",
            ):
                assert key in sc, f"[{name}] missing framework key {key}"
            assert 0 <= sc["factual_consistency_score"] <= 10

    def test_all_six_golden_chapters_present(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert set(baseline["chapters"]) == set(ev.golden_chapters())

    def test_fixtures_match_committed_baseline(self):
        """Scorecards recomputed from frozen fixtures == committed baseline.

        Catches the forgotten-re-baseline failure mode in pytest (not just
        in the CI eval step): re-frozen pipeline outputs change scorecards;
        this test forces the baseline update into the same commit.
        """
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        prompt_hash = ev.prompt_manifest_hash()
        for name in ev.golden_chapters():
            output, source, reference = _fixture(name)
            current = ev.compute_scorecard(name, output, source, reference, prompt_hash)
            base = baseline["chapters"][name]
            assert ev.compare_scorecards(base, current) == [], (
                f"[{name}] fixture scorecards drifted from the committed eval "
                f"baseline — if the pipeline change was intentional, run "
                f"python scripts/eval_summary.py --save-baseline and commit "
                f"the diff with the numbers shown"
            )


# ── 3) Gate validation (mutation tests — roadmap acceptance #2) ─────────────


class TestGateCatchesDegradation:
    def test_degraded_output_is_caught(self):
        """Deliberately-degraded summary (fabricated bullets + truncation) must
        produce a NON-EMPTY regression list vs the real baseline."""
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        output, source, reference = _fixture("academic")
        prompt_hash = ev.prompt_manifest_hash()

        degraded = copy.deepcopy(output)
        fabricated = [
            "The moon is made of green cheese and orbits Jupiter every nine days.",
            "Napoleon invented the telephone in 1723 to spy on the British navy.",
            "Alzheimer's is caused entirely by eating too much asparagus weekly.",
            "The WHO estimates that seventeen billion unicorns suffer from gout.",
        ]
        degraded["bullet_points"] = fabricated + degraded["bullet_points"][:4]
        degraded["thorough_summary"] = ". ".join(degraded["thorough_summary"].split(". ")[:5])

        degraded_sc = ev.compute_scorecard("academic", degraded, source, reference, prompt_hash)
        regressions = ev.compare_scorecards(baseline["chapters"]["academic"], degraded_sc)

        assert regressions, "gate FAILED to catch a deliberately degraded summary"
        assert any("hallucination_rate" in r for r in regressions), (
            f"fabricated bullets must trip the hallucination gate — got: {regressions}"
        )

    def test_prompt_bank_change_is_flagged(self):
        """A changed prompt-bank identity (manifest hash) without re-baselining
        must be reported as a regression."""
        output, source, reference = _fixture("academic")
        real_hash = ev.prompt_manifest_hash()
        sc = ev.compute_scorecard("academic", output, source, reference, "deadbeef" * 8)
        baseline_sc = ev.compute_scorecard("academic", output, source, reference, real_hash)

        regressions = ev.compare_scorecards(baseline_sc, sc)
        assert any("prompt bank changed" in r for r in regressions)

    def test_improvements_never_trip_the_gate(self):
        """One-directional gate: a strictly better scorecard is not a regression."""
        output, source, reference = _fixture("academic")
        h = ev.prompt_manifest_hash()
        base = ev.compute_scorecard("academic", output, source, reference, h)

        improved = copy.deepcopy(base)
        improved["metrics"]["rouge_l"]["fmeasure"] = min(
            1.0, base["metrics"]["rouge_l"]["fmeasure"] + 0.1
        )
        improved["metrics"]["faithfulness"] = min(1.0, base["metrics"]["faithfulness"] + 0.05)
        improved["metrics"]["hallucination_rate"] = max(
            0.0, base["metrics"]["hallucination_rate"] - 0.05
        )
        improved["metrics"]["coverage"] = min(1.0, base["metrics"]["coverage"] + 0.05)

        assert ev.compare_scorecards(base, improved) == []

    def test_verdict_flip_to_fail_is_caught(self):
        output, source, reference = _fixture("academic")
        h = ev.prompt_manifest_hash()
        base = ev.compute_scorecard("academic", output, source, reference, h)
        assert base["verdict"] == "PASS"

        bad = copy.deepcopy(base)
        bad["verdict"] = "FAIL"
        regressions = ev.compare_scorecards(base, bad)
        assert any("verdict" in r for r in regressions)


# ── 4) CLI smoke (fast path) ────────────────────────────────────────────────


def test_cli_check_from_fixtures_exits_zero(capsys):
    """``--check --from-fixtures`` on the committed state must pass (rc 0)."""
    rc = ev.main(["--from-fixtures", "--check"])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
