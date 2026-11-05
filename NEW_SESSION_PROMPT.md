# New Session Prompt — Elixir Wizard Rework, Phase 7 (the V0.7.4 Step-6 Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.3** (the Step-5 rework just shipped).
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
- **Phase 6 (DONE, previous session):** **V0.7.3** — Phase ⑤: Step 5
  reworked. 5a per-backend model listing (**B6 closed** — LM Studio
  now lists from its OWN base URL `/v1/models` via the new
  `utils/network.list_lmstudio_models`; the Step-5 dispatch is
  per-backend with the URL snapshotted on the main thread; the
  "No models found" hint names the server that was actually asked).
  5b preference memory (**D14**: the summarisation/OCR combos open on
  the last-used picks (`_seed_model_combo`), a refresh re-adds a pick
  the server no longer lists, and `_on_complete` re-confirms the picks
  on a SUCCESSFUL run only — no auto-pick anywhere). 5c single-owner
  limits (**D12**): the new
  `core/summarisation/effective_limits.py` is the shared mirror of the
  backend clamp ladder (the Summarizer's `_auto_detect_context_limit`
  delegates to it — one ladder, no drift); Step 5's Parameters box
  carries "Auto — let the model class decide" (on by default; the
  spins disable and CARRY the computed values — save still reads the
  spins, so the V0.04 pins stayed literally intact) plus the read-only
  **"Effective after model limits: 32,768 ctx / 16,000 out"** line,
  live-wired to every mirror input and refreshed on showEvent;
  **Step 7b's duplicate "Summarization limits" group is DELETED** (the
  §W12 save-order overwrite cannot recur; its cache checkbox relocated
  into Quality controls); the audit §5 defaults unified (coverage 85
  everywhere, ctx 32768 everywhere, out 16000 everywhere — one
  default per field, one owner). **Bonus fix found live:** the bare
  "token" keyword in `core/system/secrets._is_secret_path` routed
  four numeric/boolean request fields through the KEYCHAIN branch
  (string-coerced defaults; on keyring machines a plaintext numeric
  setting could be migrated into the keychain and wiped from
  settings.json) — the keyword now matches only auth-token compounds.
  The golden-freeze harness (`scripts/bench_chapter.py`)
  now pins its freeze conditions explicitly (0.50/131072/4096) so
  defaults changes can never silently drift the fixtures again. 67 new
  pin tests in 1 file (`tests/test_v0730_step5_models.py`), incl.
  REAL-Summarizer agreement tests for the mirror. Full-suite
  differential 9,048 passed vs 8,981 at baseline, byte-identical
  failure inventories (the documented 16, zero new). Commits
  `ddb1331` + `99584b5` + `553dfab` + `2b2aa6f` + `be8868e` +
  `26e2fee` + `1ece81c` + `2d24355` (release), tag `V0.7.3` published
  with the zip (release id 435415159, verified via the authenticated
  API). The VLM pass caught one real defect (the computed line one
  row under the fold at 820×600 — the limits block now precedes the
  workers/temperature row; fixed, re-verified, pinned).
- **Phase 7 (THIS SESSION):** execute Phase ⑥ of the plan — **V0.7.4,
  Step 6** (plan §2, "Phase ⑥"). One phase per session; the final
  session executes ⑦ (Steps 7-7b at V0.7.5).

## THIS SESSION'S MISSION — PHASE ⑥: V0.7.4 (Step 6)

Ship V0.7.4 executing plan §2-Phase⑥ exactly. The three work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

**6a — two selection modes (D15).** The master "Translate outputs"
checkbox + an "optional — runs after conversion" caption makes
skipability visible (audit §W10). Target language combo. "What to
translate": radio **"The outputs I selected in step 4"** (default) vs
**"Let me choose"** (today's checkbox list). Mode A derives
`translation.outputs` from the Step-4 selection at Start — a NEW
mapping layer (registry-driven, like `selected_output_names()`; the
backend needs NO change — translation is a settings-driven
post-conversion phase, `controller.py:432-492`). The harakat/judge
model combos are live (B1 was fixed in ①) with defaults from
settings — reuse the V0.7.3 `_seed_model_combo` pre-fill pattern
(D14's "manual picking, auto-remembered").

**6b — honesty fixes.** The `.harakat.md` output documented as a
manual-review file (D16 deferred the TTS wiring to the backlog). The
dead settings keys purged (`translation.outputs.packets`,
`harakat_confident_only` — the audit's dead-code register).

**6c — VRAM truth (B7).** The conversion-start VRAM check passes the
REAL harakat/judge models, not `summarisation_model` standing in for
the translator (`wizard_view.py:662` — the
`translation_model=s.summarisation_model` line inside
`_check_vram_budget`).

Test + release requirements (the phase gate, plan §3): mode-A
derivation pin (Step-4 selection → translation outputs mapping);
skip-visibility render; VRAM call-args pin (mock the calculator,
assert the real models flow); dead-key absence pins (grep-style, the
V0.7.1 alias-purge pattern); full-Step-6 offscreen grabs at 740×540 +
820×600, both themes, VLM-verified (the V0.7.3 pattern —
`scripts/grab_v0730_step5.py` is the one-variant-per-process driver
to copy; the VLM pass is `z-ai vision -i <png> -o <json>` from
/home/z/my-project, then read the JSON's
choices[0].message.content — investigate every flag on a zoomed crop
before acting); round-trip pins for every field the phase touches
(to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest — NOTE:
translation is NOT part of ConversionRequest, it's settings-driven,
so the round-trip is state → _save_translation_settings → settings);
full suite differential + ruff per Rule 2/3; commits/pushes per Rule
7; one finding family → one conventional commit. Release V0.7.4 per
Rules 5-6 (VERSION bump + tag + push + GitHub Release with
release_notes/V0.7.4.md + the zip at
/home/z/my-project/download/Elixir-V0.7.4.zip, built with
`git archive --format=zip --prefix=Elixir-V0.7.4/ -o <path> V0.7.4`
BEFORE calling tools/publish_release.py — the tool uploads an
existing zip, it does not build one). At the end, write the next
NEW_SESSION_PROMPT.md (Phase 8 = plan Phase ⑦: Steps 7-7b at
V0.7.5 — the FINAL phase) and commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all verified working in the V0.7.3 session):

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
(encoding / PDF-write / repair / RTL tests) + **`tiktoken`** (NEW at
V0.7.3: the eval-check script imports it — without it,
`scripts/eval_summary.py` dies on import; note the Makefile's
`eval-check` target uses the SYSTEM python3, so run it as
`.venv/bin/python scripts/eval_summary.py --check --json
eval_scorecards.json` directly). A cosmetic pip warning about
pyside6-webengine/pdf wanting 6.12 is expected and harmless.

**Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0` +
`dpkg-deb -x *.deb /tmp/qt-libs/extract`, then
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
process (`scripts/grab_v0730_step5.py` is the working driver — argv
theme/width/height/out, stubbed SimpleWorker, populated combos, one
processEvents, grab). (4) **The QMessageBox.information in Step 5's
`_on_models_loaded`** — when building Step 5 (or the full wizard) in
tests, stub `SimpleWorker` in the step5 module namespace BEFORE
construction (the `_FakeWorker` in tests/test_v0730_step5_models.py)
so no HTTP runs and no modal can fire.

**The pre-existing failure inventory on THIS rig (16 at the V0.7.3
differential — byte-identical both sides, re-verified):** the
documented 3 stale golden/eval baselines (test_golden_freeze +
test_p4_eval_gate ×2, the intentional-change procedure is the owner's
call), 5 vibevoice/TTS-constants rig tests, 5 stale source pins
(test_v1820412_c_llm_errors transcribe combo, test_v182044 ×2,
test_v182049_wb12, test_v18_15_9 primary-button outline), and 3 rig
quirks (test_p4_edge_cases_pdf Farsi presentation-forms;
test_v0619 big5 + euc_kr chardet statistics). Do NOT try to fix them
inside a phase session (Rule 2 scope); run the suite differentially
(baseline worktree via
`git worktree add --detach /tmp/elixir-base <pre-work-commit>`, same
venv, `--deselect tests/test_v0600_tool_transcribe_podcast_e2e.py`,
compare sorted FAILED inventories). Absolute 0 failures is not
achievable on this rig.
`tests/test_v0600_tool_transcribe_podcast_e2e.py` SEGFAULTS in the
full-suite combination — deselect it there, run it standalone (its
own 5 standalone failures are pre-existing, identical both sides —
re-verified at V0.7.3). `ruff format --check` flags 9 pre-V0.6.83
files on this checkout (llamacpp_config.py is one — V0.7.3 added only
clean lines to it and left the pre-existing flag untouched; do not
reformat them (Rule 2); keep every file YOU touch format-clean).
ONE MORE rig quirk: an anonymous GitHub API call (/releases/latest)
hits a 403 rate limit — verify releases with the token in the
Authorization header (verified working at V0.7.3), or use
tools/publish_release.py's own output. **A NEW lesson from V0.7.3:**
changing REQUEST-LAYER DEFAULTS can drift the golden fixtures (the
coverage 0.50→0.85 change made the guarantee's Tier-3 excerpt
insertion fire on the nonfiction chapter) — the freeze harness now
pins its conditions explicitly (bench_chapter.py: 0.50/131072/4096),
so defaults changes are safe; if a NEW golden drift appears, look for
an unpinned path before assuming a pipeline regression.

**V0.7.3 reference surfaces (the patterns to copy):**
`utils/network.list_lmstudio_models` + the per-backend dispatch in
step5's `_refresh_models` (main-thread URL snapshot baked into a
functools.partial worker); `_seed_model_combo` + the re-add-missing
pick in `_on_models_loaded` (the D14 memory pattern — REUSE for
Step 6's harakat/judge combos); `core/summarisation/effective_limits.py`
(the shared-mirror pattern: pure functions, constants from
IQ2_S_PROFILE, injectable auto_ctx for determinism, REAL-backend
agreement tests); the Auto checkbox + computed-line + showEvent
refresh in step5_models.py; the Auto-aware guard in the mixin's
`_on_backend_change`; the success-gated persistence in
wizard_view._on_complete; the secrets keyword fix
(core/system/secrets.py `_is_secret_path`); the freeze-condition pins
in scripts/bench_chapter.py; and the pin file
tests/test_v0730_step5_models.py (the stub-controller +
_FakeWorker + grab scaffolding is directly reusable). The
V0.6.86 / V0.7.0 / V0.7.1 / V0.7.2 / V0.7.3 pin files must stay
green. The M1 de-hardcode census
(test_m1_theme_tokens.py::test_zero_theme_dependent_colour_literals_outside_theme)
enforces the no-colour-literals rule — use theme_manager.palette
tokens everywhere.

**THE LOOP (session mechanics).** Recover: `cd /home/z/elixir-repo`
(clone with the session token if absent). `git log --oneline -6` —
expect, in order from the top: a docs-only session touch-up (this
file's Recover-expectation fix — possibly more than one if later
docs commits landed), then `7f86019` (a docs-only errata: the V0.7.3
lint claim in the release notes + CHANGELOG corrected to admit the
grab-script ruff catch — the GitHub release body was patched to
match), then `dabf167` (the fix itself: scripts/grab_v0730_step5.py
shipped with an unused import + one format nit, caught by the
post-release Rule-3 gate — re-grab renders byte-identical), then
`b64b167` (the Phase-7 handoff docs commit — this file's main body),
then `2d24355` (the V0.7.3 release); tag `V0.7.3` pushed. Baseline
per the venv + Qt notes above. Orient: read AGENTS.md, this prompt, the
Round-2 plan (all of §0-§2, especially Phase ⑥), the audit's §W10
section (the translation step) + §3 bug B7 + the dead-code register
(two translation keys). Skim step6_translation.py (the master
checkbox, the 11-checkbox `_TRANSLATABLE_OUTPUTS` list, the combos at
~:85), wizard_view.py's `_save_translation_settings` (~:949-959, the
B5-hardened load-then-save) + `_check_vram_budget` (~:632-700, the
B7 line at ~:662), controller.py:432-492 (the translation phase —
settings-driven, post-conversion), core/translation/service.py:825-944
(the glob + freshness filter), the registry (core/outputs/registry.py
— the mode-A mapping should be registry-driven), and the V0.7.3 test
file before editing. Implement → test → commit/push per unit →
release V0.7.4 → write the Phase-8 prompt → commit+push it → report.
The phase-phasing approval (plan §1) authorizes the V0.7.4 release.
**GITHUB Token (one-off, never commit it):** use the token from the
session context for git push. If it is expired, ask me for a fresh
one.

One tip for when you start the new session: paste the prompt above,
then add your GitHub token on a separate line (the same one you gave
me — or a fresh one if it expires). The token never goes in the repo;
it only lives in the chat.

What Phase 7 will deliver in plain words: Step 6 stops hiding that
translation is optional. A clear "Translate outputs" switch with an
"optional" caption, a target language, and a simple choice —
"translate the outputs I already picked in step 4" (the default, so
you never re-tick a dozen boxes) or "let me choose" for the old
manual list. The Persian-diacritics and judge model boxes fill with
real models and remember your picks. The `.harakat.md` file stops
pretending it feeds the Podcast Maker (it's a manual-review file for
now). Two settings keys that do nothing are deleted. And the VRAM
warning before Start finally estimates the REAL translation models,
not the summariser wearing a fake moustache. It ships as V0.7.4.

That's everything — the campaign stands at 6 of 8 phases done (V0.6.86
→ V0.7.0 → V0.7.1 → V0.7.2 → V0.7.3 released, all verified live), and
the next session picks up at Step 6 / V0.7.4 with a fully clean repo.
When you start it, paste the block above and put your GitHub token on
its own line right below it.
