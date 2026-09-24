# ROADMAP V0.20 — The Quality Campaign: 9–10/10 summaries on real books

> **STATUS (V0.4.25 audit):** COMPLETED charter (V0.20.1–V0.20.5 shipped). The
> §6 campaign protocols remain normative for audit sessions (AGENTS.md Rules 2–4
> cite them).

> **Status:** charter approved by the project owner at the wrap of the V0.12
> campaign (session of the V0.19 release). Supersedes nothing — the V0.12
> roadmap (`ROADMAP_V0.12.md`) is fully executed and closed.
>
> **Nature of this campaign: TESTING AND DEBUGGING.** The V0.12 campaign
> built the machinery — gates, baselines, a 5,573-test net, keychain
> security, a deterministic quality harness, a de-monolithized pipeline,
> performance levers. This campaign spends that machinery on the product
> question it was all built for: **is the summary actually good — book
> after book, genre after genre?**

---

## 1. Mission

Increase the **reliability**, **factual accuracy**, and **coverage** of
Elixir's chapter summaries **across different books**, and prove it with the
standing four-pillar expert fact-checker framework
([`EVALUATION_FRAMEWORK.md`](EVALUATION_FRAMEWORK.md)).

**Objective: every audited book scores 10/10 — or at least 9/10 — on the
scorecard, verdict `PASS`.** (The framework's mechanical FAIL rule is
`factual_consistency_score < 6 OR coverage_score < 5`; the campaign bar sits
far above that floor.)

## 2. Non-goals (hard constraints — carry the V0.12 discipline)

- **No refactoring, no modularization, no re-architecture.** The code shape
  is frozen at the V0.18 acceptance (no core file over 2,500 lines;
  `_summarize_inner` stays a ≤300-line orchestrator). File moves are not
  fixes.
- **No speculative changes.** Every code or prompt change must cite the
  audit finding or the conversion-log line that motivates it. Evidence
  first; the fix is the smallest change the evidence supports.
- **The net stays green at every commit:** full suite passing (5,573 local /
  5,561 CI at charter time), `ruff check` + `format` clean, and
  `make eval-check` → OK. Golden fixtures may only change as part of an
  audited, deliberate quality fix (re-freeze protocol, §6).
- **Performance levers stay default OFF** (V0.19). This campaign changes
  QUALITY, not timing. (A fix that incidentally enables overlap during
  audits is fine — it must not change bytes.)
- Deferred known bugs stay deferred unless an audit trips over them (then
  they become evidence and get fixed): the map-reduce `_pipeline`/`_pstate`
  `UnboundLocalError` (pinned-failing by design), the
  `core/translation/service.py:205` keyring path mismatch.

## 3. The campaign loop (evidence-first, per book)

1. **CONVERT** — run the real pipeline (real LLM, real settings) on an
   experiment book. Keep everything: the summary files AND the conversion
   log at `output/{book}/logs/*.conversion.log.md`.
2. **AUDIT** — for each audited chapter, run the four-pillar fact-checker
   (the verbatim prompt in `EVALUATION_FRAMEWORK.md`; do not paraphrase it)
   with Source Text = the ground-truth chapter, Candidate Summary = the
   generated file. Record Part 1 (fact-check log / missing information /
   quality notes) and Part 2 (the JSON scorecard) under
   `audit/results/AUDIT_V<version>_<book>.md`.
3. **CROSS-CHECK** — before trusting any audit: verify the output's
   provenance stamp with `core.system.provenance.parse_provenance` (never
   peek fixed lines — the .3.9 lesson), confirm the run_id matches the log,
   and read the log's deterministic recall-floor lines ("theorists X/Y,
   conclusion items Z/W") as the honest coverage number alongside the LLM
   judge's verdict.
4. **DIAGNOSE** — map every flagged hallucination / omission / clarity
   defect to the pipeline stage that owns it: grounding check, gap-fill
   reprompt, judge/scholar reflection, length policy, postchecks, chapter
   chunking / map-reduce legs on long chapters, or the prompt itself. The
   Phase-6 five-call dependency chain (primary → grounding → gap-fill →
   scholar → truncation retry) is the map of where quality is decided.
5. **FIX** — smallest change the evidence supports: prompt wording, a
   threshold, a recall floor, a postcheck detector, an ordering. One
   audit-finding family → one conventional commit.
6. **VERIFY** — re-run the SAME chapter end-to-end; audit again; suite +
   eval-check green; score must move toward 9–10/10 **without regressing
   the other books** (re-audit at least one previously-passing book per
   fix).

## 4. The book matrix (different books, different failure modes)

The standing corpus (`tests/golden/`) already spans academic,
academic_tables, farsi, multicolumn, nonfiction, and scanned_ocr chapters.
The campaign experiments with **real full books** chosen to stress
different failure modes:

| Genre | What it stresses |
|---|---|
| Narrative fiction | plot-event ordering, character names, temporal flow (clarity pillar) |
| Expository nonfiction / pop-science | causal claims, numbers, named studies (hallucination pillar) |
| Academic textbook (tables + citations) | data fidelity, structure preservation, coverage on long chapters |
| Translated / Farsi | bilingual faithfulness, entity transliteration |
| Very long chapters | chunking + map-reduce legs (where coverage is hardest) |

Every book in the matrix gets the full loop of §3; the campaign is done
when the books on hand score 9–10/10, not when a checklist is ticked.

## 5. Operating modes

- **Sandbox mode:** cloud provider via the keychain (V0.16) if a key is
  provisioned in the environment; conversions run through the real
  controller (GUI is unavailable headless — drive `core/controller.py` /
  the converter API programmatically, as `scripts/eval_summary.py` does
  with the mock).
- **User-rig mode:** the owner runs books on the real rig and provides the
  outputs + conversion logs; the session audits, cross-checks provenance,
  diagnoses, and lands the fixes. (Precedent: the 2026-08-31 session's
  stale-upload find — always parse the stamp first.)

## 6. Protocols the campaign relies on (all standing, do not re-invent)

- **Freeze / re-freeze:** golden pipeline outputs are byte-pinned. An
  intentional quality fix that changes outputs re-records the affected
  fixtures IN THE SAME COMMIT and states why in the message.
- **Eval baseline:** intentional metric changes re-baseline via
  `python scripts/eval_summary.py --save-baseline` (same commit, with the
  audit evidence cited) — `make eval-check` must stay OK.
- **Provenance before audit:** parse the stamp; a file without one is a
  pre-.3.7 artifact and not evidence.
- **Release ritual per wrap:** VERSION + installer + README badges synced,
  CHANGELOG entry, zip backup to `/home/z/elixir-backups/`, worklog update,
  push, CI verified green.

## 7. Rituals (unchanged from the V0.12 campaign)

Conventional commits; push after every meaningful change; the suite runs
in the FOREGROUND (background test processes get killed in this sandbox);
zip backup at every release; `/home/z/my-project/worklog.md` updated at
every stage boundary; CI polled to green before declaring a phase done.
