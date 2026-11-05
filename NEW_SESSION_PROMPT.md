# New Session Prompt — Elixir Wizard Rework, Phase 3 (the V0.7.0 Shell Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.6.86** (the wizard-translation hotfix
just shipped). Purely Python — any Next.js sandbox at
`/home/z/my-project` is disposable tooling, NOT part of the project.
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
- **Phase 2 (DONE, previous session):** the V0.6.86 hotfix — B1 (the
  missing `Controller.list_ollama_models` + the empty-selection guard)
  and B5 (the load-then-save translation round-trip) both fixed, 20
  pin tests, released. Commits `2a09376` (B1) + `11d9787` (B5) +
  `f72c05c` (release), tag `V0.6.86` published with the zip.
- **Phase 3 (THIS SESSION):** execute **Phase ② of the plan — V0.7.0,
  the wizard shell + Step 1** (plan §2, "Phase ②"). One phase per
  session; later sessions execute ③-⑦ one each (③ Steps 2-3 at V0.7.1,
  ④ Step 4 at V0.7.2, ⑤ Step 5 at V0.7.3, ⑥ Step 6 at V0.7.4,
  ⑦ Steps 7-7b at V0.7.5).

## THIS SESSION'S MISSION — PHASE ②: V0.7.0 (the shell opens the rework)

Ship **V0.7.0** executing plan §2-Phase② exactly. The five work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

1. **2a — the stage-chip header (V1).** Replace the 42px dot strip
   (`wizard_view.py:174-207`) with a new reusable `StageBar` widget
   (`ui_qt/components/stage_bar.py`): the 10 steps group into 5 named
   stages (SOURCE · OUTPUTS · MODELS · TUNING · REVIEW); per-stage
   segmented tracks, done/current/future states (filled amber +
   check-glyph / emphasis ring / muted border), stage labels in
   small-caps IBM Plex Sans SemiBold 11px, current stage label in the
   accent color, hover tooltips listing that stage's steps, sub-captions
   dropping below 780px width. All 10 steps keep their identity (D1) —
   presentation only.
2. **2b — the wizard chrome restyle (V2 shell).** The established
   identity (per `theme.py`: IBM Plex Sans + JetBrains Mono, amber
   accent, `palette()` tokens, the `StepHeader` numbered-badge
   pattern): every step gets the numbered `StepHeader`; nav bar
   Cancel (ghost) left, ‹ Back (secondary) + Next › (primary amber)
   right, 40px+ targets; the dialog frame/group boxes adopt the card
   language (rounded QFrame cards, SPACE tokens). The shell lands NOW
   so phases ③-⑦ build inside it; per-step polish lands with each
   phase's functional rework.
3. **2c — Step 1 becomes 3 cards (D1-D3).** Six `TypeCard`s → three:
   **Digital** (`assets/icons/normal_book.png` — today's pipeline +
   `extract_figure_text` + `extract_tables` ON, honest copy: charts on
   text pages are extracted, not re-OCR'd), **Scanned**
   (`assets/icons/full_ocr.png` — every page through the dedicated
   vision-OCR engine; engine set D2: vision-capable summarisation
   model → `primary_ocr_model` → OlmOCR → Qwen VL; Tesseract/Paddle/
   local-VLM excluded; copy promises *reading* pages, not describing
   imagery), **Auto** (`assets/icons/mixed.png`, "Recommended" badge,
   DEFAULT — today's page-level detection + the existing Step-1
   suggestion banner).
4. **2d — the `ocr_mode` backend (D3).** New
   `ConversionRequest.ocr_mode: str = "auto"` (`digital`/`scanned`/
   `auto`); `extraction.py` branches on it; `scanned` SUPERSEDES the
   academic-only `force_ocr_all_pages` branch (B2) — the old flag maps
   to `ocr_mode="scanned"` as a deprecated alias for one release, then
   purged. **Dead-flag purge in the same pass:** `auto_detect_scanned`
   (log-only), preset `content_filter.min_*`, `is_academic` from
   `to_ui_data` (pre-purge grep sweep per flag; pins assert zero
   readers). Settings-dialog preset applier unified with the wizard's
   (the split-brain note).
5. **2e — profiles retirement (D4).** Delete the Step-1 profiles box +
   its 3 handlers + `_refresh_profiles` (`step1_pdf.py:92-122`) and
   `core/pipeline/profiles.py` + its tests. With 3 cards and no
   profiles box, Step 1 fits its viewport (B10 closed).

### Test + release requirements (the phase gate, plan §3)

- AST-pins for `ocr_mode` on the request + the extraction branch;
  engine-set pin (scanned mode never constructs Tesseract/Paddle);
  dead-flag grep-pins (zero `auto_detect_scanned` readers); StageBar
  offscreen render + a state-transition sweep; Step-1 3-card grab at
  740×540 and 820×600, BOTH themes; profiles-module deletion reflected
  in the suite (delete tests with their modules in-commit; net green).
- Round-trip pins for every state field the phase touches
  (`to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest`).
- Full suite + `ruff check` clean; every file you touch must be
  `ruff format` clean; commits/pushes per Rule 7; one finding family →
  one conventional commit (Rule 2).
- **Release V0.7.0:** VERSION bump + tag + push + GitHub Release
  (body = `release_notes/V0.7.0.md` per Rule 6's human-readable style)
  + zip at `/home/z/my-project/download/Elixir-V0.7.0.zip` (Rule 5),
  via `python tools/publish_release.py V0.7.0 --zip ... --token
  <one-off>` — token from the session context, never committed/logged.
- At the end, write the next `NEW_SESSION_PROMPT.md` (Phase 4 =
  execution of plan Phase ③: Steps 2-3 at V0.7.1) and commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wiped parts of the repo venv and the offscreen Qt
libs. The previous session restored them; if the reset happened again,
rebuild as follows (all verified working):

1. **Venv:** `.venv/bin/pip install -r requirements.txt` then the
   extras the old venv carried: `PySide6==6.11.2 PySide6_Addons==
   6.11.2 PySide6_Essentials==6.11.2 shiboken6==6.11.2` (requirements
   .lock pins), plus `ebooklib genanki radon hypothesis ruff` (the
   optional/dev packages the test suite needs — their absence was
   PROVEN to cause 7 phantom failures: the output-rider/epub/anki
   tests and the CC-ceiling radon pins).
2. **Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0` +
   `dpkg-deb -x *.deb /tmp/qt-libs/extract`, then export
   `LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:
   $LD_LIBRARY_PATH` and `QT_QPA_PLATFORM=offscreen`.
3. **The 13 pre-existing suite failures** (at the V0.6.86 baseline,
   byte-identical before/after the hotfix — verified twice; NONE touch
   the wizard translation path). Do NOT try to fix them inside a phase
   session without asking me first (Rule 2 scope); run the suite
   differentially instead:
   - 3 stale golden/eval baselines (`test_golden_freeze::test_prompt_
     manifest_matches_prompt_bank`, both `test_p4_eval_gate` gates) —
     the V0.6.43/V0.6.55 transcribe prompt additions shipped without
     the re-freeze procedure. Fixing = `python scripts/prompt_manifest.py`
     + `--save-baseline` re-run + committing the numbers (the
     intentional-change procedure) — my call, not yours.
   - 5 vibevoice live-subprocess rig tests (`test_v0615/0616/0617` +
     the TTS constants contract) — subprocess/audio-stack dependent.
   - 5 stale source pins (`test_v182044_p3_tts_subprocess` ×2 — the
     600→3600 timeout constants; `test_v1820412_c_llm_errors` — the
     transcribe combo constant; `test_v182049_bk1_ui_threading` ×1;
     `test_v18_15_9_conclusions` — the Primary button outline).
   Also known-flaky: `test_v0600_internal_tabs_e2e::TestQueueViewDrive::
   test_full_sequential_run_two_books` failed once in a full-suite
   run, passed standalone + on re-run at both commits. And
   `tests/test_v0600_tool_transcribe_podcast_e2e.py` SEGFAULTS (exit
   139) when combined with the full suite on this rig — PROVEN to
   happen identically at the pre-hotfix baseline commit; run the full
   suite with `--deselect tests/test_v0600_tool_transcribe_podcast_
   e2e.py` and run that file in its own pytest invocation.
4. **`ruff format --check`** flags 12 pre-existing files (V0.6.76-
   0.6.82-era commits, verified pre-dating the hotfix). Do not
   reformat them inside a phase session (Rule 2); keep every file YOU
   touch format-clean.

**The differential gate (use it):** run the full suite (with the
deselect) at your session's baseline commit and record the failure
list; re-run after your work; the inventories must be identical apart
from tests you deliberately added/removed. Absolute "0 failures" is
NOT currently achievable on this rig — the 13 are documented above.

## THE LOOP (session mechanics)

1. **Recover:** `cd /home/z/elixir-repo` (clone with the session token
   if absent). `git log --oneline -5` — expect `f72c05c` (the V0.6.86
   release) on top, `11d9787` (B5) + `2a09376` (B1) below it; tag
   `V0.6.86` pushed.
2. **Baseline:** the venv + Qt notes above; reference harnesses:
   `scripts/wz_icons_check.py` (offscreen grabs),
   `tests/test_v0686_wizard_hotfix.py` (the hotfix pins — they must
   stay green; the B5 full-wizard characterization builds the REAL
   WizardView offscreen with a stub controller — your StageBar/shell
   changes must not break it, extend the stub if the build needs more
   controller surface).
3. **Orient:** read `AGENTS.md`, this prompt, the Round-2 plan (all of
   §0-§2, especially Phase ②), the audit's §3/§W-sections for B2/B10
   and the dead-code register. Skim `wizard_view.py`, `step1_pdf.py`,
   `core/models/models.py`, the extraction module, `theme.py`,
   `ui_qt/components/step_header.py` before editing.
4. **Implement → test → commit/push per unit → release V0.7.0 →
   write the Phase-4 prompt → commit/push it → report.** The phase
   phasing approval (plan §1) authorizes the V0.7.0 release.

## GITHUB Token (one-off, never commit it)

Use the token from the session context for git push. If it is expired,
ask me for a fresh one.
