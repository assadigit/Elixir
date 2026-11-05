# New Session Prompt — Elixir Wizard Rework, Phase 8 (the V0.7.5 Steps-7-7b Session — the FINAL phase)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.4** (the Step-6 rework just shipped).
Purely Python — any Next.js sandbox at `/home/z/my-project` is
disposable tooling, NOT part of the project.
**Read `AGENTS.md` first** — its 7 rules are non-negotiable (Rule 1
content-agnostic, Rule 2 evidence-first, Rule 3 net-green, Rule 4
provenance, Rule 5 zip-per-release, Rule 6 GitHub-Release-per-version,
Rule 7 commit-and-push-incrementally).

**The campaign:** re-designing and reworking the **full wizard** (the
10-step "Process Wizard" window). The method I set and expect:

- **Phase 0 (DONE):** the audit —
  **`ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md`** (the B1-B10 live-bug
  register, the dead-code register, the defaults table).
- **Phase 1 (DONE):** the implementation plan —
  **`ELIXIR_WIZARD_REWORK_ROUND_2_PLAN.md`**. **Read it in full before
  writing any code** — it is the contract: my 21 locked decisions
  (D1-D21), the 2 visual asks (V1 stage chips, V2 restyle), the
  7-phase sequence, per-phase test matrices.
- **Phase 2 (DONE):** the V0.6.86 hotfix — B1 + B5, released
  (`2a09376` + `11d9787` + `f72c05c`).
- **Phase 3 (DONE):** **V0.7.0** — Phase ②: the StageBar stage-chip
  header (V1), the wizard chrome restyle (V2 shell), Step 1's three
  mode cards, the `ocr_mode` backend (**B2 closed**), the D2
  scanned-mode engine set, the dead-flag purge, the profiles
  retirement (D4, **B10 closed**). 57 new pin tests. Tag `V0.7.0`
  published with the zip.
- **Phase 4 (DONE):** **V0.7.1** — Phase ③: Step 2's page-range card
  with the LIVE feedback line, the TOC action promotion, the
  page-group wiring (D5: core/segmentation/page_group_segmenter.py +
  the degenerate-heading gate), Step 3's auto-first mode-aware
  disclosure, **B3 closed**, the deprecated full-OCR alias purged.
  80 new pin tests across 5 files. Tag `V0.7.1` published with the
  zip.
- **Phase 5 (DONE):** **V0.7.2** — Phase ④: Step 4's Core card with
  the essentials locked BY CONSTRUCTION, five registry-driven category
  cards (D8), the 5 deprecated outputs gone (D6), the dead streaming
  checkbox deleted, tooltips everywhere (§W7), **B9 + B8 closed** (the
  honest TTS label; the registry-driven Review/start-log
  enumeration), the emoji→icons sweep. 61 new pin tests across 3
  files. Tag `V0.7.2` published with the zip (release id 435256935).
- **Phase 6 (DONE):** **V0.7.3** — Phase ⑤: Step 5 reworked. 5a
  per-backend model listing (**B6 closed** — LM Studio now lists from
  its OWN base URL `/v1/models` via `utils/network.
  list_lmstudio_models`). 5b preference memory (**D14** —
  `_seed_model_combo`, refresh re-adds a missing pick, success-gated
  persistence; no auto-pick anywhere). 5c single-owner limits
  (**D12**): `core/summarisation/effective_limits.py` is the shared
  mirror of the clamp ladder; Step 5's "Auto — let the model class
  decide" + the computed "Effective after model limits" line;
  Step 7b's duplicate limits group DELETED; the audit §5 defaults
  unified (coverage 85 / ctx 32768 / out 16000 everywhere). Bonus:
  the bare "token" keyword in `secrets._is_secret_path` fixed (four
  numeric fields were routed through the KEYCHAIN branch). 67 new pin
  tests incl. REAL-Summarizer agreement tests. 9,048 passed vs 8,981
  at baseline, byte-identical failure inventories (the documented 16).
  Tag `V0.7.3` published with the zip (release id 435415159).
- **Phase 7 (DONE, previous session):** **V0.7.4** — Phase ⑥: Step 6
  reworked. 6a two selection modes (**D15**): the master "Translate
  outputs" switch + the visible **"Optional — runs after conversion."**
  caption (§W10's invisible-skip finding); "What to translate" is a
  radio — **"The outputs I selected in step 4"** (the DEFAULT) vs "Let
  me choose" (the old 11-checkbox list, hidden in mode A); mode A
  derives `translation.outputs` from the Step-4 selection AT START
  through the NEW registry-driven mapping layer
  (`core/outputs/registry.py`:
  `_TRANSLATION_OUTPUT_MAP` + `selected_translation_outputs()` +
  `translation_output_label()` — pinned no-drift against the
  backend's `_OUTPUT_FILE_MAP`; full_markdown and social are
  manual-mode-only, never derived; a mode-A Start rewrites the whole
  selection); a new `translation.selection_mode` setting
  ('selected' | 'manual') rides the B5 round-trip; the harakat/judge
  combos open on the last-used picks (the V0.7.3 D14 pattern) and
  list live OFF the UI thread — the old build-time sync HTTP call
  could freeze the wizard open for 5s (the W-b11 antipattern, now
  gone); a "Refresh models" button re-lists; the empty case is a
  muted hint label, NEVER a modal; Step 8's Review + the start-log
  show the derived truth ("follows Step 4 — …"). 6b honesty
  (**D16 + dead-code register**): the `.harakat.md` output documented
  as a MANUAL-REVIEW file on all five surfaces (harakat.py's
  docstring, service.py's file map, the Settings page's info label,
  the wizard tooltip, the podcast subtitle); the dead keys
  `translation.outputs.packets` + `translation.harakat_confident_only`
  purged (DEFAULTS + migration lists + legacy-file pop on load; the
  dead "Confidence-first" checkbox deleted with its key). 6c VRAM
  truth (**B7 closed**): the conversion-start VRAM check passes the
  REAL translator (the `translation.model` setting, the same source
  the service reads, fallback translategemma:4b) — not
  `summarisation_model` standing in; the wizard check now agrees with
  the converter-side re-check. 64 new pin tests in 1 file
  (`tests/test_v0740_step6_translation.py`); two legacy pins updated
  in-commit with intent preserved (test_v0686's B1 render + B5
  round-trips now pin the manual mode; test_v0720's step8 import pin
  accepts the multi-line form). Full-suite differential 9,112 passed
  vs 9,048 at baseline, byte-identical failure inventories (the
  documented 16, zero new). Commits `b51d5ea` + `7247f9d` + `08addd3`
  + `00e2167` + `494e688` (release), tag `V0.7.4` published with the
  zip (release id 435527729, verified Latest via the authenticated
  API). The VLM pass over 6 renders (both themes × both sizes + both
  manual-mode variants): one flag (the mode-A radio "not selected")
  investigated on a 2× zoomed crop and disproven — the house styled
  CHECKED state (a bold dark ring) misread at full-page scale.
- **Phase 8 (THIS SESSION — the FINAL phase):** execute Phase ⑦ of
  the plan — **V0.7.5, Steps 7-7b** (plan §2, "Phase ⑦"). One phase
  per session; this is the last one — the campaign close-out.

## THIS SESSION'S MISSION — PHASE ⑦: V0.7.5 (Steps 7-7b, the final phase)

Ship V0.7.5 executing plan §2-Phase⑦ exactly. The four work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

**7a — the advanced disclosure (W11, D17-D19, D13).** Step 7 becomes
one primary choice + a folded advanced disclosure: **token limit per
segment: Auto (default) + manual** — the manual field enabled ONLY
when the TOKEN strategy is actually in play (it only feeds
`TokenSegmenter`, `token_segmenter.py:21`); **honest strategy copy**
(the AUTO cascade spelled out: chapters → located-TOC → fuzzy-TOC →
headings → semantic → page-groups → tokens → whole-document, with
semantic noted as "one extra AI call that samples the first ~3,500
tokens", `semantic_segmenter.py:52-113`); the `enable_semantic` toggle
folds into the disclosure, default on; **the academic-rigor checkbox
is REMOVED** (its label lied — "temperature=0" no longer happens —
but the source-driven auto-enable STAYS, `summarizer_init.py:496-511`);
**conservative drops removed from the wizard** (D18 — backend +
quarantine panel untouched); **the token-budget slider is DELETED**
(D13/**B4 closed by deletion**) — with it dies the dead Step-4 sync
(`step7_advanced.py:206,211` — `hasattr(self,"step4")` on the Step-7
widget) and the deprecated-output presets (`presets.py:192-215`).

**7b — self-consistency relocation (D10).** Removed from the wizard;
backend kept; **default off**; a Settings → AI-quality control carries
truthful copy: "Ollama-only; ~3-4× cost; merges sample agreement
(union), not majority vote" (audit §W12: silently no-ops unless
provider == "ollama", `bullet_pipeline.py:992`; the "vote" is a
union-merge with fuzzy dedup, `summarizer_chunking.py:274-327`). A log
line fires when it's requested on an unsupported provider (no more
silent no-op). The all-engines fix stays on the backlog.

**7c — coverage honesty (D11 — the REAL rework, read the plan §2-⑦
in full).** Owner's requirement: *threshold 85 must mean ≥ ~85%
measured coverage, within a few points of LLM randomness.* Today:
keyword-overlap metric, no regeneration loop, over-delivery target 1.0
dominates, floor `max(0.60, t−0.10)` WARNING-only (`chapter_phases.py:
1478-1567`; `summarizer_init.py:413-415`, `:1876-1917`). Rework
(content-agnostic, Rule 1): (1) ONE target — the user threshold is
*the* target; over-delivery domination removed; the t−0.10 floor goes.
(2) Close-the-loop: measure (the existing concept-coverage metric,
`summary_validator.py:810-856`) → below `target − 3` → targeted
gap-fill reprompt on the MISSING concepts (existing gap-fill machinery
+ prompts) → re-measure → up to 3 rounds (cost-bounded) → honest
terminal report ("Coverage 87% — target met" / "Reached 83% after 3
attempts; remaining gaps: …"). (3) Truth in UI: Step 7b's spin says
what it now really does ("regenerates until measured coverage reaches
this level, ±3 for model randomness, max 3 rounds"). (4) Backlog:
embedding-based recall if the keyword metric proves gameable.
**CAREFUL: this item touches PROMPTS — the plan §3 requires the golden
fixtures re-freeze + eval re-baseline IN THE SAME COMMIT (bench
--save-golden, prompt_manifest, eval --save-baseline, with the
scorecard diff shown in the commit); that finally resolves the stale
golden/eval baselines in the rig's pre-existing failure inventory.**

**7d — fine-tune recommended defaults (W12).** A "Use recommended
settings" button on Step 7b applies the post-rework audited defaults
(coverage loop on, self-consistency off, Auto limits) — the precedent
is the Step-1 detector banner pattern.

Test + release requirements (the phase gate, plan §3): coverage-loop
unit tests (below-target triggers gap-fill; 3-round bound; honest
report strings; tolerance ±3); strategy-copy AST-pins; slider /
rigor-checkbox / drops absence pins (grep-style, the V0.7.1
alias-purge pattern — the V0.7.4 dead-key pins show the scoped,
comment-stripping form); self-consistency default-off + the
provider-log pin; the fine-tune defaults pin; round-trip pins for
every state field the phase touches (to_ui_data →
_REQUEST_FIELD_MAP → ConversionRequest); full-Step-7 + full-Step-7b
offscreen grabs at 740×540 + 820×600, both themes, VLM-verified (the
V0.7.3/V0.7.4 pattern — `scripts/grab_v0740_step6.py` is the current
one-variant-per-process driver to copy; the VLM pass is `z-ai vision
-i <png> -o <json>` from /home/z/my-project, then read the JSON's
choices[0].message.content — investigate every flag on a zoomed crop
before acting); **the campaign close-out: a full-wizard functional
sweep driving all 10 steps in both themes** (the `scripts/
r4_functional.py` modal-recorder pattern; the final phase runs the
all-steps sweep per plan §3); full suite differential + ruff per Rule
2/3; commits/pushes per Rule 7; one finding family → one conventional
commit. Release V0.7.5 per Rules 5-6 (VERSION bump + tag + push +
GitHub Release with release_notes/V0.7.5.md + the zip at
/home/z/my-project/download/Elixir-V0.7.5.zip, built with
`git archive --format=zip --prefix=Elixir-V0.7.5/ -o <path> V0.7.5`
BEFORE calling tools/publish_release.py — the tool uploads an
existing zip, it does not build one). At the end, since this is the
FINAL phase, write the closing NEW_SESSION_PROMPT.md as a
**campaign-complete document**: what shipped (V0.6.86 → V0.7.5, every
phase, every bug B1-B10's disposition), the deferred backlog (plan §5
— harakat→TTS wiring D16, self-consistency all-engines, the VL
description pass, the embedding recall metric, B3 bullet-voting), and
the owner's-call leftovers (the stale baselines that 7c may have just
resolved, the 9 pre-V0.6.83 format flags, the rig's 16 pre-existing
failures) — then commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all verified working in the V0.7.4 session):

**Venv:** `python3 -m venv .venv` — CAREFUL: the sandbox's python3
IS a venv itself; use the base interpreter directly:
`/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`.
Then: `.venv/bin/pip install -r requirements.txt` plus the FULL extras
list (each absence caused phantom failures historically, all proven):
`PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2
shiboken6==6.11.2` (the lock pins) + `ebooklib genanki radon hypothesis
ruff` (optional dev) + `pytest pytest-cov pytest-asyncio pytest-randomly`
(the test runner — NOT in requirements.txt) + `pymupdf` (test-only PDF
builder) + `pydub soundfile scipy huggingface_hub` (the TTS-stack
tests) + `chardet reportlab pikepdf arabic-reshaper python-bidi`
(encoding / PDF-write / repair / RTL tests) + `tiktoken` (the
eval-check script imports it; the Makefile's eval-check target uses
the SYSTEM python3, so run it as `.venv/bin/python
scripts/eval_summary.py --check --json eval_scorecards.json`
directly). A cosmetic pip warning about pyside6-webengine/pdf wanting
6.12 is expected and harmless.

**Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0` (then
`dpkg-deb -x <each>.deb /tmp/qt-libs/extract` — one deb per command,
NOT `dpkg-deb -x *.deb` which fails) then
`export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
and `export QT_QPA_PLATFORM=offscreen`.

**Suite mechanics (verified):** the full suite takes ~4.5 min with
`--no-cov` (the default addopts enable coverage — much slower).
Background processes are KILLED when a tool call times out — run the
suite FOREGROUND (timeout 590) or in chunks; never rely on
nohup/setsid surviving. Use `-p no:randomly` for stable order. The
offscreen traps, all proven: (1) **Modal trap** — never call
`wizard._go_next()` offscreen with an invalid step (QMessageBox blocks
forever); drive `_current_step` + `_update_step()` directly. (2)
**processEvents trap** — grab directly without processEvents for
full-wizard grabs; a SINGLE step shown alone tolerates ONE
processEvents before grab. (3) **Two-steps-one-process trap** — for
manual grab scripts, render each step (each VARIANT) in its own
process (`scripts/grab_v0740_step6.py` is the current working driver
— argv theme/width/height/out + a --mode-b style flag, stubbed
SimpleWorker, populated combos, one processEvents, grab). (4) **The
listing-worker trap (UPDATED at V0.7.4):** Step 5 AND Step 6 BOTH
start a SimpleWorker at build — when building either step or the full
wizard in tests, stub `SimpleWorker` in BOTH module namespaces
(`step5_models` and `step6_translation`) BEFORE construction (the
`_FakeWorker` in tests/test_v0740_step6_translation.py covers both
shapes). Step 6's `_on_models_loaded` is deliberately modal-free
(a muted hint label), so bare navigation past Step 6 cannot trap — but
stub anyway for determinism.

**The pre-existing failure inventory on THIS rig (16 at the V0.7.4
differential — byte-identical both sides, re-verified):** the
documented 3 stale golden/eval baselines (test_golden_freeze +
test_p4_eval_gate ×2 — NOTE: 7c's prompt changes + re-freeze should
FINALLY resolve these; if you re-freeze, the differential baseline is
the PRE-WORK commit's inventory), 5 vibevoice/TTS-constants rig tests,
5 stale source pins (test_v1820412_c_llm_errors transcribe combo,
test_v182044 ×2, test_v182049_wb12, test_v18_15_9 primary-button
outline), and 3 rig quirks (test_p4_edge_cases_pdf Farsi
presentation-forms; test_v0619 big5 + euc_kr chardet statistics). Do
NOT try to fix them inside a phase session (Rule 2 scope — 7c's
in-scope re-freeze is the exception for the golden/eval trio); run the
suite differentially (baseline worktree via
`git worktree add --detach /tmp/elixir-base <pre-work-commit>`, same
venv, `--deselect tests/test_v0600_tool_transcribe_podcast_e2e.py`,
compare sorted FAILED inventories). Absolute 0 failures is not
achievable on this rig.
`tests/test_v0600_tool_transcribe_podcast_e2e.py` SEGFAULTS in the
full-suite combination — deselect it there, run it standalone (its
own 5 standalone failures are pre-existing, identical both sides —
re-verified at V0.7.4). `ruff format --check` flags 9 pre-V0.6.83
files on this checkout (the set: test_m2_dashboard,
test_v0669_local_llm_lights, test_v182048_p6_icon_cache,
components/icons.py, components/llamacpp_config.py,
settings/sections/output_sections.py, settings/tts_page.py,
views/about_system_dialog.py, views/token_cost_dialog.py — verified
byte-identical before/after at V0.7.4; do not reformat them (Rule 2);
keep every file YOU touch format-clean). ONE MORE rig quirk: an
anonymous GitHub API call (/releases/latest) hits a 403 rate limit —
verify releases with the token in the Authorization header (verified
working at V0.7.4), or use tools/publish_release.py's own output.
**The V0.7.3 golden-drift lesson stands:** the freeze harness pins
its conditions explicitly (bench_chapter.py: 0.50/131072/4096), so
defaults changes are safe; if a NEW golden drift appears, look for an
unpinned path before assuming a pipeline regression.

**V0.7.4 reference surfaces (the patterns to copy):** the registry's
`_TRANSLATION_OUTPUT_MAP` + `selected_translation_outputs()` (the
pure mapping layer with no-drift pins against the consumer's key
list); `translation_output_label()` (labels shared by review + log);
step6's `_seed_combo` + `_on_models_loaded` (the D14 memory pattern,
modal-free) + `_fetch_models`/`_refresh_models` (the worker listing
with graceful degradation); `_save_translation_settings`'s mode-A
derivation (the whole-dict replace — no stale carryover); the
dead-key purge in utils/settings.py (DEFAULTS + migration tuple-forms
+ the legacy-file pop, pinned by the real-`_defaults()` data pin and
comment-stripped zero-readers greps); the B7 VRAM call-args pins (the
mocked-calculator capture on the REAL full WizardView); and the pin
file tests/test_v0740_step6_translation.py (the _StubController now
carries get_secret/set_secret for full-wizard builds, and the
_wizard helper stubs BOTH step workers). The
V0.6.86 / V0.7.0 / V0.7.1 / V0.7.2 / V0.7.3 / V0.7.4 pin files must
stay green. The M1 de-hardcode census
(test_m1_theme_tokens.py::test_zero_theme_dependent_colour_literals_outside_theme)
enforces the no-colour-literals rule — use theme_manager.palette
tokens everywhere.

**THE LOOP (session mechanics).** Recover: `cd /home/z/elixir-repo`
(clone with the session token if absent). `git log --oneline -8` —
expect, in order from the top: the Phase-8 handoff docs commit (this
file — its hash is the parent of whatever you read there), then
`494e688` (the V0.7.4 release: VERSION + CHANGELOG +
release_notes/V0.7.4.md), then `00e2167` (6c B7 VRAM), `08addd3` (6b
honesty + dead keys), `7247f9d` (6a Step-6 rework), `b51d5ea` (the
registry mapping layer); tag `V0.7.4` pushed. Baseline per the venv +
Qt notes above. Orient: read AGENTS.md, this prompt, the Round-2 plan
(all of §0-§2, especially Phase ⑦ — 7a-7d), the audit's §W11 (the
advanced panel) + §W12 (fine-tune: auto mode, self-consistency,
coverage, limits) + §3 bug B4 + §0.7 (the slider), and the V0.7.4
test file before editing. Skim step7_advanced.py (the strategy combo
+ `_STRAT_DESC`, the token-limit spin, the rigor + drops checkboxes,
the slider at ~:128-155 + the dead Step-4 sync at ~:206,211),
step7b_fine_tune.py (the coverage spin, the self-consistency
checkbox, the Quality controls group), `core/segmentation/
token_segmenter.py:21` + `segmenter.py:1879-2087` (the AUTO cascade),
`semantic_segmenter.py:52-113` (the 3500-token sample),
`chapter_phases.py:1478-1567` + `summarizer_init.py:413-415,496-511,
538-674,1876-1917` (the coverage machinery + the rigor auto-enable),
`summary_validator.py:810-856` (the coverage metric),
`presets.py:192-215` (the deprecated-output presets), and
`scripts/bench_chapter.py` (the freeze harness you'll re-run for 7c).
Implement → test → commit/push per unit → release V0.7.5 → write the
campaign-complete closing prompt → commit+push it → report. The
phase-phasing approval (plan §1) authorizes the V0.7.5 release.
**GITHUB Token (one-off, never commit it):** use the token from the
session context for git push. If it is expired, ask me for a fresh
one.

One tip for when you start the new session: paste the prompt above,
then add your GitHub token on a separate line (the same one you gave
me — or a fresh one if it expires). The token never goes in the repo;
it only lives in the chat.

What Phase 8 will deliver in plain words: the wizard's last two
steps stop over-promising. Step 7 folds its junk into one honest
"advanced" drawer — the token-limit field only unlocks when token
chunking is actually in play, the strategy list says what each method
really costs (including the AI call that semantic detection makes),
the academic-rigor checkbox goes away (the automatic detection stays),
and the doubly-broken token-budget slider is deleted outright
(closing the last live bug, B4). Step 7b gets the campaign's biggest
honesty fix: the coverage number finally MEANS something — if you set
85, the system measures the real coverage, re-generates the missing
bits up to 3 times, and tells you plainly whether it reached the
target; the self-consistency switch moves to Settings with truthful
cost copy and stops silently doing nothing on non-Ollama engines; a
"Use recommended settings" button applies the sane defaults. It ships
as V0.7.5 with the full 10-step, both-themes sweep as the campaign's
close-out — after 8 phases, every one of the audit's findings is
either fixed, deleted, or honestly documented, and every step of the
wizard has been rebuilt inside the new shell.

That's everything — the campaign stands at 7 of 8 phases done
(V0.6.86 → V0.7.0 → V0.7.1 → V0.7.2 → V0.7.3 → V0.7.4 released, all
verified live), and the next session picks up at Steps 7-7b / V0.7.5
— the FINAL phase — with a fully clean repo. When you start it, paste
the block above and put your GitHub token on its own line right below
it.
