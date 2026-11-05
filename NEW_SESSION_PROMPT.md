# New Session Prompt — Elixir Wizard Rework, Phase 4 (the V0.7.1 Steps 2-3 Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.0** (the wizard shell + Step-1 rework
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
- **Phase 2 (DONE):** the V0.6.86 hotfix — B1 + B5, released
  (`2a09376` + `11d9787` + `f72c05c`).
- **Phase 3 (DONE, previous session):** **V0.7.0** — Phase ② executed:
  the StageBar stage-chip header (V1), the wizard chrome restyle (V2
  shell: numbered StepHeaders 1-10, 20px frame margins, the
  Cancel/‹ Back/Next › nav with 40px+ targets), Step 1's three mode
  cards (Digital/Scanned/Auto-RECOMMENDED), the `ocr_mode` backend
  (digital/scanned/auto; the scanned branch supersedes the
  academic-only force gate — **B2 closed**; `force_ocr_all_pages` is
  now a deprecated alias mapped to scanned, purged next release), the
  D2 scanned-mode engine set (Tesseract/PaddleOCR/local-VLM excluded —
  never constructed, never called), the dead-flag purge
  (`auto_detect_scanned`, preset `content_filter.min_*`, `is_academic`
  from `to_ui_data`) with the unified `apply_preset_settings()` applier
  (the split-brain fix), and the profiles retirement (D4 — the Step-1
  box + `core/pipeline/profiles.py` deleted; **B10 closed**). 57 new
  pin tests; full-suite differential clean. Commits `3ac3bbe` (2a) +
  `8a6b10a` (2b) + `112f082` (2d) + `371235f` (purge) + `a97f954`
  (.gitignore) + `316923f` (2e) + `b519ebe` (2c) + `b641d5b` (release),
  tag `V0.7.0` published with the zip.
- **Phase 4 (THIS SESSION):** execute **Phase ③ of the plan — V0.7.1,
  Steps 2-3** (plan §2, "Phase ③"). One phase per session; later
  sessions execute ④-⑦ one each (④ Step 4 at V0.7.2, ⑤ Step 5 at
  V0.7.3, ⑥ Step 6 at V0.7.4, ⑦ Steps 7-7b at V0.7.5).

## THIS SESSION'S MISSION — PHASE ③: V0.7.1 (Steps 2-3)

Ship V0.7.1 executing plan §2-Phase③ exactly. The four work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

**3a — the page-range card (W4).** The "Page range" group
(`step2_range.py:47-73`) grows into a proper card: 15px-ish labels,
larger spinboxes, a live feedback line ("Pages 12-340 — 329 pages,
~estimated chapters detected: 14"), tooltips. "Process all pages"
stays the default with the range fields enabling on uncheck.

**3b — the TOC button promotion (W4).** The `🔍 Detect chapters from
TOC` secondary button (`step2_range.py:87-108`) becomes a prominent
card-level action: a professional icon (per D9 — no emoji on controls)
+ "Detect chapters from table of contents" + caption "Most accurate —
reads the book's own outline". Backend is solid (audit §W4); pure UI
promotion.

**3c — the page-group wiring (D5 — wire the backend BEFORE the UI).**
`page_group_size` becomes the block size of a **page-group chunking
fallback**: when TOC/heading/semantic segmentation fail, pages chunk
into N-page blocks (paragraph boundaries respected within the block)
instead of raw token-fixed chunks. AUTO computes N from measured page
token density (target ≈ 4-6k tokens/block, clamped 4-25 pages); the
manual value overrides. `chunk_by_page_groups` gets its first real
reader. UI (inside Step 2's segmentation card): "Processing blocks:
**Auto (≈ 8 pages)**" with an advanced override spin and honest copy
("used only when chapter structure can't be detected").

**3d — the OCR step rework (W5, B3).** One primary choice + a collapsed
advanced disclosure: "◉ Automatic — recommended" (big radio, caption "I
scan every page and OCR only the ones that need it, with the best
available engine.") vs "○ Manual control" (opens the disclosure: engine
overrides [vision model ▾] [OlmOCR ▾] [Qwen VL ▾], figure & table text
extraction [on], tables (camelot/tabula) [on], PaddleOCR fallback
[off], OCR timeout [120 s ▾] — floor-clamped, honest). **B3 fix:**
`ocr_timeout` + `use_paddleocr` enter `_REQUEST_FIELD_MAP` so the
wizard controls actually reach the backend; timeout items become
120/180/300 (the backend clamps ≥120 — audit §W5). Auto = the honest
auto copy from the audit. NOTE the new context: Step 1 now owns the
mode axis (`ocr_mode` — landed V0.7.0); Step 3's rework must respect it
(e.g. the disclosure's defaults follow the mode; a Scanned-mode run
shows the engine set, not the Paddle toggle).

**The deprecated-alias purge (carry-over):** V0.7.0 mapped
`force_ocr_all_pages` → `ocr_mode="scanned"` for one release. This
session (a release later) PURGES it: the request field, the Step-3
checkbox, the `_REQUEST_FIELD_MAP` row, the settings key + default,
the `resolve_ocr_mode` alias branch, and `ContentPreset.force_ocr_all_pages`
(core/llm/content_presets.py — dead, never read) all go; grep-pins
assert zero readers (the V0.7.0 dead-flag purge pattern,
`tests/test_v0700_dead_flags_purged.py`).

**Test + release requirements (the phase gate, plan §3):** request-map
pins (timeout/paddle now round-trip — the audit's dead-control
lesson); page-group chunker unit tests (block sizing, boundary
respect, AUTO density math); segmentation-cascade pin (page-group sits
BEFORE the token fallback); Step-2/3 offscreen grabs at 740×540 +
820×600, both themes, VLM-verified (the V0.7.0 pattern —
`tests/test_v0700_step1_three_cards.py`); round-trip pins for every
state field the phase touches (`to_ui_data` → `_REQUEST_FIELD_MAP` →
`ConversionRequest`); full suite differential + ruff per Rule 2/3;
commits/pushes per Rule 7; one finding family → one conventional
commit. Release V0.7.1 per Rules 5-6 (VERSION bump + tag + push +
GitHub Release with `release_notes/V0.7.1.md` + the zip at
`/home/z/my-project/download/Elixir-V0.7.1.zip`, built with
`git archive --format=zip --prefix=Elixir-V0.7.1/ -o <path> V0.7.1`
BEFORE calling `tools/publish_release.py` — the tool uploads an
existing zip, it does not build one). At the end, write the next
NEW_SESSION_PROMPT.md (Phase 5 = plan Phase ④: Step 4 at V0.7.2) and
commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all verified working this session):

**Venv:** `python3 -m venv .venv` — CAREFUL: the sandbox's `python3`
IS a venv itself; use the base interpreter directly:
`/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`.
Then: `.venv/bin/pip install -r requirements.txt` plus the FULL extras
list (the V0.6.86 session's list was incomplete — each absence caused
phantom failures, all proven this session):
`PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2 shiboken6==6.11.2`
(the lock pins) + `ebooklib genanki radon hypothesis ruff` (optional
dev) + `pytest pytest-cov pytest-asyncio pytest-randomly` (the test
runner — NOT in requirements.txt) + `pymupdf` (test-only PDF builder) +
`pydub soundfile scipy huggingface_hub` (the TTS-stack tests) +
`chardet reportlab pikepdf arabic-reshaper python-bidi` (encoding /
PDF-write / repair / RTL tests).

**Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0` +
`dpkg-deb -x *.deb /tmp/qt-libs/extract`, then
`export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
and `export QT_QPA_PLATFORM=offscreen`.

**Suite mechanics (verified):** the full suite takes ~4.5 min with
`--no-cov` (the default addopts enable coverage — much slower).
Background processes are KILLED when a tool call times out — run the
suite FOREGROUND (timeout 590) or in chunks; never rely on nohup/setsid
surviving. TWO offscreen traps, both proven:
1. **Modal trap:** never call `wizard._go_next()` offscreen with an
   invalid step (QMessageBox blocks forever). Drive `_current_step` +
   `_update_step()` directly.
2. **processEvents trap:** `app.processEvents()` after `show()` on a
   built step sequence (3→4→5→6) natively crashes ("double free or
   corruption") — **this happens identically at the pre-V0.7.0
   baseline**, it is a rig/PySide quirk, NOT a regression. Grab
   directly without processEvents (that is what the passing tests do).

**The pre-existing failure inventory on THIS rig (17 at the V0.7.0
baseline — byte-verified via the differential):** the documented 13
(3 stale golden/eval baselines — `test_golden_freeze` +
`test_p4_eval_gate` ×2, the intentional-change procedure is the
owner's call; 5 vibevoice/TTS-constants rig tests; 5 stale source
pins) + 4 rig quirks (the known-flaky
`test_v0600_internal_tabs_e2e::test_full_sequential_run_two_books`
— fails some full-suite runs, passes standalone; `test_v0619` big5 +
euc_kr — chardet-version statistics on short inputs; `test_p4_edge_cases_pdf`
Farsi presentation-forms — an invisible codepoint normalization
difference). Do NOT try to fix them inside a phase session (Rule 2
scope); run the suite differentially (baseline worktree via
`git worktree add --detach /tmp/elixir-base HEAD~N`, same venv,
`--deselect tests/test_v0600_tool_transcribe_podcast_e2e.py`, compare
sorted FAILED inventories). Absolute 0 failures is not achievable on
this rig. `tests/test_v0600_tool_transcribe_podcast_e2e.py` SEGFAULTS
in the full-suite combination — deselect it there, run it standalone
(its own 5 standalone failures are pre-existing, identical both sides).
`ruff format --check` flags 12 pre-V0.6.83 files — do not reformat
them (Rule 2); keep every file YOU touch format-clean.

**V0.7.0 reference surfaces:** `tests/test_v0700_*.py` (the pin
patterns: source/AST pins, offscreen stub-controller builds, both-theme
grabs), `scripts/wz_icons_check.py` (the grab harness), and the
StageBar/StepHeader components (`ui_qt/components/stage_bar.py`,
`step_header.py`) — build Phase-③ UI inside them. The V0.6.86 hotfix
pins (`tests/test_v0686_wizard_hotfix.py`) must stay green.

## THE LOOP (session mechanics)

Recover: `cd /home/z/elixir-repo` (clone with the session token if
absent). `git log --oneline -5` — expect the Phase-4 handoff docs commit
(this file, `a79691e` or a later docs touch-up) on top and `b641d5b`
(the V0.7.0 release) directly below it; tag `V0.7.0` pushed. Baseline
per the venv + Qt notes
above. Orient: read AGENTS.md, this prompt, the Round-2 plan (all of
§0-§2, especially Phase ③), the audit's §W4/§W5 sections + the
dead-code register. Skim `step2_range.py`, `step3_ocr.py`, the
segmentation cascade (`core/segmentation/segmenter.py`, especially the
AUTO fallback order + `chunk_by_page_groups`), `controller.py`'s
`_REQUEST_FIELD_MAP`, and the V0.7.0 test files before editing.
Implement → test → commit/push per unit → release V0.7.1 → write the
Phase-5 prompt → commit/push it → report. The phase-phasing approval
(plan §1) authorizes the V0.7.1 release.

## GITHUB Token (one-off, never commit it)

Use the token from the session context for git push. If it is expired,
ask me for a fresh one.

One tip for when you start the new session: paste the prompt above,
then add your GitHub token on a separate line (the same one you gave me
— or a fresh one if it expires). The token never goes in the repo; it
only lives in the chat.

What Phase 4 will deliver in plain words: Step 2 becomes a proper
card — a bigger, clearer page-range picker with live feedback, a
prominent "Detect chapters from table of contents" action, and honest
"processing blocks" copy wired to a NEW page-group fallback so that
books with no detectable chapters still get sensible multi-page blocks
instead of arbitrary token slices. Step 3's five cryptic checkboxes
collapse into one "Automatic — recommended" choice with an advanced
drawer for people who want engine control — and the timeout and
PaddleOCR toggles finally reach the backend (they never did). It ships
as V0.7.1.
