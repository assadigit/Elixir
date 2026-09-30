# Elixir — SWOT Re-Audit Session Report (V0.6.7 → V0.6.8)

- **Repo:** https://github.com/assadigit/elixir @ refactor/audit-session, tag V0.6.7 (`7cb180c`) audited → **V0.6.8** released (audit-only: docs + charter, zero runtime changes).
- **Method:** read-only audit — scripted shape/complexity/MI/import-graph metrics (stdlib AST + radon 6.0.1), vulture dead-code scan, security greps, full-suite run, per-failure root-cause diagnosis, two independent fresh-eyes subagent review passes (code-quality; architecture/integration), every top finding re-verified by the orchestrator before filing. AGENTS.md rules honored (read-only on runtime code; evidence-first; no history rewrite).
- **The full report:** `docs/AUDIT_SWOT_V0.6.7.md` — scorecard (A 2.5 / B 4 / C 3.5 / D 4 / E 2.5 / F 3.5 / G 3.5, overall 3.4), SWOT quadrants with IDs + evidence + confidence labels, top-10 hotspot map, integration/dependency registry with reliability ratings, findability spot-test, and the honest not-verified list.

## Headline findings (all MEASURED/OBSERVED, none speculative)

1. **BLOCKER — the VRAM-overbudget safety gate is unreachable dead code** (`converter_impl.py:502` unconditional return; policy block `:503-536` dead; setting + request field + docstring are placebo). Its **12 red tests were mispinned as "environment failures"** by the last two session baselines — the "14 pinned families" myth is retired; the census: 12 = this defect, 2 = the contract conflict below, 0 true environment failures with a complete Qt install.
2. **The 2 v182032 "environment" failures are a real contract conflict** — the V0.5.15 regex-grounded exemption (`field_phases.py:482-501`) defeats the V18.20.3.2 parenthetical-promotion drop for parenthetical-only authors; reproduced deterministically; owner decision required.
3. **`dual_api` fast-provider override is a silent no-op** — `hasattr(_base_url/_api_key)` vs public attrs (`summarization.py:793-798` vs `openai_compat_provider.py:39-40`): wrong-endpoint routing on a supported architecture, errors swallowed.
4. **RTL dependency drift** — arabic-reshaper/python-bidi only in requirements.txt (missing from pyproject + lock).
5. **The structural debt is quantified for the next session** — five god functions CC 105–136; 125 functions >150 LOC; 4 modules at MI 0.00; 152 pass-only exception swallows (~8 medium-risk sites cited); timeout scatter 60 sites/11 values; 91 inert stub-block test files; 9/11 dialogs un-migrated; lying docs incl. a safety-gate docstring.
6. **The strengths are equally strong** — 7,481-test net; zero core→UI layering violations (headless core); LLM ops engineering (supervisor + retry taxonomy + transport SSOT); crash-safety architecture; zero known vulns with a waiver policy; the proven verbatim-extraction pattern.

## What shipped in V0.6.8

- `docs/AUDIT_SWOT_V0.6.7.md` (the audit) · `release_notes/V0.6.8.md` · the CHANGELOG entry · the rewritten `NEW_SESSION_PROMPT.md` (the fix/improve/optimize charter: 2 operator decisions + the B1–B19 prioritized backlog in 6 waves) · this session report · VERSION bump + tag + zip + push + GitHub Release (per AGENTS.md Rules 5–6).

## Baseline handed to the next session

Suite 7,481 P / 14 F / 43 S / 16 D (~4 min, offscreen Qt, full PySide6) — with every failure decomposed and a path to green (B1–B3). Ruff clean at the CI pin. The next session's success criterion: an honestly-green suite first, then the waves in order.

## Not verified (honest limits)

Live-LLM behaviors (deselected `live_llm`), the rig-only surface (real OCR/TTS/full-book runs), coverage percentages (ran `--no-cov`), pip-audit re-run (offline; lock + waiver state relied on). Full list: `docs/AUDIT_SWOT_V0.6.7.md` §8.
