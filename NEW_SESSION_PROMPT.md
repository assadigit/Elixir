# New Session Prompt — Elixir Wizard-Rework Campaign: THE AUDIT SESSION (V0.7.5 shipped — verify everything, hunt bugs, prove nothing is unfinished)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.5** (tag pushed, GitHub Release
published — release id 435620062). The wizard-rework campaign
(**V0.6.86 → V0.7.5**, the hotfix + 7 phases, one phase per session) is
**SHIPPED and CLOSED**: every Round-1 audit finding is fixed, deleted,
or honestly documented, and every live bug B1-B10 has a disposition.
The full record is **`docs/CAMPAIGN_CLOSEOUT_V0.7.5.md`** (moved there
verbatim from the previous NEW_SESSION_PROMPT.md — it is your
verification list).

Purely Python — any Next.js sandbox at `/home/z/my-project` is
disposable tooling, NOT part of the project. **Read `AGENTS.md`
first** — its 7 rules are non-negotiable (especially Rule 2
evidence-first; this session's report is nothing without evidence, and
Rule 3 net-green applies to docs commits too).

**This session is NOT a feature session and NOT a release session.**
It is the campaign audit I (the owner) am ordering: independently
re-verify what the campaign claims, hunt for bugs the campaign may
have missed, and make sure nothing is unfinished, missing, or not
fixed yet. **NO VERSION bump, NO re-release, NO changes to core/,
ui_qt/, utils/, tests/ — unless a REGRESSION FINDING emerges, in which
case you STOP and report it to me with evidence before touching
anything.**

## THE AUDIT'S SOURCE-OF-TRUTH DOCUMENTS (read in full before running anything)

1. `docs/CAMPAIGN_CLOSEOUT_V0.7.5.md` — the campaign record: the
   phase-by-phase table (what shipped, per release), every bug's
   disposition, the deferred backlog, the owner's-call leftovers, the
   verified rig baseline. Every claim in it goes on your
   verification list.
2. `ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md` — the original findings
   register (the B1-B10 evidence lines, the §W findings).
3. `ELIXIR_WIZARD_REWORK_ROUND_2_PLAN.md` — the contract (D1-D21, the
   7-phase sequence, §5 the deferred backlog).
4. `release_notes/V0.6.86.md` … `release_notes/V0.7.5.md` — each
   release's own claims and numbers.
5. `CHANGELOG.md` — the campaign entries' consistency.

## THIS SESSION'S MISSION — THE AUDIT

Verdict-first: the deliverable is **`docs/AUDIT_CAMPAIGN_V0.7.5.md`**,
every claim marked **VERIFIED / FAILED / COULD-NOT-VERIFY** with the
exact command + output that proves it, plus every new finding ranked
by severity (REGRESSION > BUG > STALENESS > HYGIENE). Work through:

### Phase A — the record vs the repo (read-only)

**A1 — repo + release integrity.**
- `git log --oneline -10` from the top: the audit-prompt docs commit
  (this file), `3563ff7` (the campaign close-out), `edcaa6f` (the
  V0.7.5 release), `387dbad`, `6ab56cb`, `3cfc6a0`, `f1987cb`,
  `343e435`, `3393544`, `72f7d4`; tag `V0.7.5` present; VERSION =
  0.7.5.
- GitHub (token in the Authorization header — anonymous calls hit 403
  rate limits): Releases V0.6.86 → V0.7.5 all exist with their zips,
  plus the `-windows` installer releases (V0.7.5-windows carries
  Elixir-Setup-0.7.5.exe). The V0.7.5 zip asset must be byte-identical
  to a fresh `git archive --format=zip --prefix=Elixir-V0.7.5/ V0.7.5`
  (sha256 both sides; if the sandbox's `/home/z/my-project/download/`
  copy is absent, fetch the asset with the token).
- CHANGELOG carries every campaign entry; `release_notes/` complete
  for all 8 releases.
- **Pre-known findings to confirm and quantify** (found in the
  pre-audit check; they go in the report):
  (a) the README badges are stale — the version badge says 0.6.69 and
  the tests badge says 8618 passed / 18 failed, while the truth is
  0.7.5 and the V0.7.5 differential numbers (9,183 passed / the
  documented 13-failure inventory) — this is a Phase-B fix;
  (b) the repo root carries ~35 scratch files committed on main:
  the now*.png working screenshots (≈30 of them), 369.png,
  508782d6-4b80-48be-9046-d081ce258b75.png, three nested zips
  (ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip, Elixir-Document-Type-Modes.zip,
  Elixir-diagnostics.zip), and the working-session MDs (including
  ELIXIR_UI_UX_CORRECTION_ROUND_2 (1).md with its duplicate " (1)"
  download suffix) — they all ship inside every release zip (the 33 MB
  size). Inventory them and PROPOSE the cleanup (Phase C decision —
  do not delete anything yet);
  (c) `/releases/latest` currently resolves to the V0.7.5-windows
  installer release rather than the V0.7.5 source release (cosmetic;
  verify + note it — no action unless I say so).

**A2 — the suite on this rig** (rebuild first — KNOWN RIG STATE below):
- Full suite with the documented mechanics: expect **≥ 9,183 passed**;
  the failure inventory must be byte-identical to the documented 13:
  5 vibevoice/TTS-constants rig tests, 5 stale source pins
  (test_v1820412_c_llm_errors' transcribe combo, test_v182044 ×2,
  test_v182049_wb12, test_v18_15_9's primary-button outline), 3 rig
  quirks (test_p4_edge_cases_pdf Farsi presentation-forms; test_v0619
  big5 + euc_kr chardet statistics). **REDISCOVER the exact list by
  running it — do not trust the doc's memory.**
- The transcribe e2e standalone: 5 = 5 pre-existing.
- `ruff check` clean repo-wide; `ruff format --check` flags EXACTLY
  the 9 documented pre-V0.6.83 files (test_m2_dashboard,
  test_v0669_local_llm_lights, test_v182048_p6_icon_cache,
  components/icons.py, components/llamacpp_config.py,
  settings/sections/output_sections.py, settings/tts_page.py,
  views/about_system_dialog.py, views/token_cost_dialog.py).
- The campaign's pin-file ladder green: test_v0686_wizard_hotfix,
  the V0.7.0-V0.7.3 pin files, test_v0740_step6_translation,
  test_v0750_steps7_7b.

**A3 — the whole-campaign differential (the core no-regression claim).**
- Worktree at the pre-campaign commit (the parent of `2a09376`, the
  V0.6.86 hotfix): `git worktree add --detach /tmp/elixir-base <sha>`;
  same venv; full suite both sides (the transcribe e2e deselected from
  the full runs, run standalone both sides).
- Compare sorted FAILURE INVENTORIES, not pass counts (the campaign
  added ~700 tests, so pass counts legitimately differ). The claim to
  verify: **every HEAD-side failure is either in the pre-campaign
  inventory or one of the documented rig items.** Anything else = a
  REGRESSION FINDING — the highest severity; stop and report before
  touching anything.

**A4 — claim-by-claim verification (the close-out table + release notes).**
- **B1-B10, one by one:** for each disposition (fixed /
  closed-by-deletion / closed-by-retirement) locate the fixing
  commit(s), re-run its pin tests, and re-check the original audit
  evidence line no longer exhibits — e.g. B4: comment-stripped
  zero-reader greps for the token-budget slider + TOKEN_BUDGET_PRESETS
  + the dead Step-4 sync; B7: the VRAM call-args pin; B10: the
  profiles retirement; B1/B5: the hotfix pins.
- **The honesty surfaces, still honest:** Step 7's strategy copy vs
  segmenter.py's real AUTO cascade (the no-drift pin); the coverage
  caption (±3, max 3 rounds) + the honest terminal-report strings;
  Step 7b's self-consistency ABSENCE from the wizard + the Settings →
  AI-quality copy (Ollama-only; ~3-4× cost; union-merge, not majority
  vote) + the provider log line; the harakat manual-review copy on all
  five surfaces; the honest TTS label; Step 6's mode-A derivation +
  the Review "follows Step 4 — …" line; Step 5's "Effective after
  model limits" line; the start-log's no-wizard-unset-values rule.
- **The defaults:** 85 / 32768 / 16000 / 2000 everywhere (wizard
  state, settings DEFAULTS, the request, effective_limits).
- **The dead-key purges:** translation.outputs.packets +
  translation.harakat_confident_only — zero readers, no resurrection
  vectors (migration lists, legacy-file pop); the overdeliver_*
  settings stay inert legacy (clamp tests pin them; no UI readers).
- **The 7d recommended button:** perturb → click → restore, and the
  no-settings-owned-writes pin.
- **The golden/eval baselines:** the 3 formerly-stale tests
  (test_golden_freeze's prompt-manifest + test_p4_eval_gate ×2) now
  PASS (the 7c re-freeze); the eval gate reports OK.

**A5 — the rendered truth (visual).**
- Re-run `scripts/v0750_full_sweep.py` — the REAL full WizardView, all
  10 steps, both themes, the 34 checks, 0 failures expected.
- Fresh grabs of the reworked steps (1, 2, 4, 5, 6, 7, 7b) — both
  themes, both sizes (740×540 + 820×600), one variant per process
  (the grab_v0750_steps7.py pattern) — then the VLM pass
  (`z-ai vision -i <png> -o <json>` from /home/z/my-project, read the
  JSON's choices[0].message.content) with the zoomed-crop discipline:
  investigate every flag on a 2-4× crop before believing it (the
  campaign disproved 3 of its 4 VLM flags that way — at V0.7.5 one
  flag was real and got fixed, one was disproven by pixel
  measurement).

### Phase B — bug hunting (the campaign's blind spots)

Beyond re-verification, actively hunt (offscreen, the modal-recorder
pattern, every offscreen trap honoured):
- **Untried combinations:** Scanned mode + Token strategy + a manual
  token limit; the LM Studio backend (its own /v1/models listing);
  translation mode B (manual) end-to-end; coverage targets 0 / 50 /
  100 (the extremes — check the ±3 tolerance and max-3-rounds math at
  both ends, and that target 0 never loops); the fold toggle
  rapid-clicked; a fully-defaulted run (no human input on any step)
  from Step 1 through to the start-log.
- **Leftovers:** grep the campaign-touched files for TODO/FIXME, for
  references to deleted controls (token budget, the academic-rigor
  checkbox, conservative drops in ui_qt/, self_consistency in wizard
  state, overdeliver in the Settings UI), and for orphan imports.
- **The lying-log pattern:** the start-log + Step 8's Review under
  every mode — no wizard-unset values printed, no crashes, no stale
  carryover between steps.
- **The coverage loop's edge cases:** in-band no-op (target met on
  round 0), the two stalled forms (no fillable candidates / gap-fill
  produced nothing usable), the exhausted report naming the remaining
  gaps, the Tier-2 guards (thinking filter + near-dup) on insertion.
- **The deferred backlog's cleanliness:** each of the 5 deferred items
  (harakat→TTS wiring, self-consistency all-engines, the VL
  description pass, the embedding recall metric, B3 bullet-voting)
  must be CLEANLY absent or unchanged — deferred, not half-shipped;
  any orphan code from them is a finding.

### Phase C — the deliverables

1. **`docs/AUDIT_CAMPAIGN_V0.7.5.md`** — the verdict-first audit
   report: per-claim PASS/FAIL with evidence, the findings ranked
   (REGRESSION > BUG > STALENESS > HYGIENE), and the final "what
   remains" menu (the deferred backlog + the owner's-call leftovers +
   this audit's new findings, each with a recommendation). One docs
   commit, pushed.
2. **Pre-approved bounded fixes — documentation-only:** the README
   badge staleness and similar doc/config drift as ONE `docs(readme)`
   commit. NOTHING under core/, ui_qt/, utils/, tests/ changes without
   my explicit approval of the specific finding first.
3. The closing **NEW_SESSION_PROMPT.md** (the post-audit menu for
   whatever I choose next — a cleanup session, a backlog pickup, or
   nothing), committed + pushed.
4. Report to me in plain words: the verdict, the findings, the menu.

## KNOWN RIG STATE (the verified V0.7.5 baseline — the sandbox reset wipes it)

- **Venv:** use the base interpreter directly —
  `/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`,
  then `.venv/bin/pip install -r requirements.txt` PLUS the full
  extras list (each absence caused phantom failures historically):
  `PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2
  shiboken6==6.11.2 ebooklib genanki radon hypothesis ruff pytest
  pytest-cov pytest-asyncio pytest-randomly pymupdf pydub soundfile
  scipy huggingface_hub chardet reportlab pikepdf arabic-reshaper
  python-bidi tiktoken`. A cosmetic pip warning about
  pyside6-webengine/pdf wanting 6.12 is expected and harmless.
- **Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0`, then
  `dpkg-deb -x <each>.deb /tmp/qt-libs/extract` (ONE deb per command,
  NOT `dpkg-deb -x *.deb` which fails), then
  `export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
  and `export QT_QPA_PLATFORM=offscreen`.
- **Suite mechanics:** ~4.5 min with `--no-cov` (the default addopts
  enable coverage — much slower). Run FOREGROUND (timeout 590) or in
  chunks; background processes are KILLED when a tool call times out.
  Use `-p no:randomly` for stable order. Deselect
  `tests/test_v0600_tool_transcribe_podcast_e2e.py` from full-suite
  runs (it SEGFAULTS in the combination; standalone it fails 5 = 5
  pre-existing). Differential baselines via
  `git worktree add --detach /tmp/elixir-base <commit>`, same venv,
  compare sorted FAILED inventories.
- **Offscreen traps (all still true):** never `wizard._go_next()` with
  an invalid step (QMessageBox blocks forever) — drive `_current_step`
  + `_update_step()`; no processEvents for full-wizard grabs (a single
  step shown alone tolerates ONE); one variant per process for manual
  grabs (scripts/grab_v0750_steps7.py is the current driver); stub
  SimpleWorker in BOTH step5_models and step6_translation before any
  full-wizard build (the _FakeWorker in tests/test_v0750_steps7_7b.py
  + scripts/v0750_full_sweep.py cover both shapes).
- **GitHub API:** an anonymous /releases/latest call hits a 403 rate
  limit — verify with the token in the Authorization header, or use
  tools/publish_release.py's own output.
- **The golden-drift lesson (V0.7.3, restated):** the freeze harness
  pins its conditions explicitly (bench_chapter.py: 0.50/131072/4096),
  so defaults changes are safe; if a NEW golden drift appears, look
  for an unpinned path before assuming a pipeline regression.

## THE LOOP (session mechanics)

Recover: `cd /home/z/elixir-repo` (clone with the session token if
absent). Baseline per the rig notes above. Orient: AGENTS.md → this
prompt → docs/CAMPAIGN_CLOSEOUT_V0.7.5.md → the Round-1 audit §0/§3
(the bug register) → the Round-2 plan §5 (the backlog) →
release_notes/V0.7.5.md. Then Phase A → B → C, one commit per unit,
push per Rule 7, conventional commits with the evidence in the body.
**GITHUB Token (one-off, never commit it):** use the token from the
session context for git push and the API calls. If it is expired, ask
me for a fresh one.

What this session delivers in plain words: an independent,
evidence-backed answer to "did the campaign do everything it claimed,
and is anything still broken, missing, or half-done?" — plus a short
ranked list of anything found, and a menu of what I might order next.
Nothing ships and nothing in the app itself changes, unless you find a
regression and I say so.
