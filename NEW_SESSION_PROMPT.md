# New Session Prompt — Elixir Wizard Rework, Phase 5 (the V0.7.2 Step-4 Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.1** (the Steps 2-3 rework just
shipped). Purely Python — any Next.js sandbox at
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
- **Phase 3 (DONE):** **V0.7.0** — Phase ②: the StageBar stage-chip
  header (V1), the wizard chrome restyle (V2 shell), Step 1's three
  mode cards, the `ocr_mode` backend (**B2 closed**), the D2
  scanned-mode engine set, the dead-flag purge, the profiles
  retirement (D4, **B10 closed**). 57 new pin tests. Tag `V0.7.0`
  published with the zip.
- **Phase 4 (DONE, previous session):** **V0.7.1** — Phase ③ executed:
  Step 2's page-range card (15px labels, 32px spinboxes, the LIVE
  feedback line — "Pages 12-340 — 329 of 397 pages (~83%) will be
  processed."; the page total read best-effort from Step 1's PDF,
  never guessed), the TOC action promotion (Primary button + list
  icon + honest caption "Most accurate — reads the book's own
  outline"; the dialog mechanics untouched), the page-group wiring
  (D5 — **behavior first**): new
  `core/segmentation/page_group_segmenter.py` in the AUTO cascade
  between semantic and tokens (N-page blocks, cuts pulled back to the
  last blank line), AUTO sizing from measured page density (target
  ≈ 5,000 tokens/block, clamped 4-25 pages), `page_group_size` 0=AUTO
  unified on all four surfaces, `chunk_by_page_groups` got its first
  real reader, and the **degenerate-heading gate** (a single segment
  spanning >60% of the book — HeadingSegmenter's "Introduction"
  catch-all — is rejected as no-structure; without the gate the new
  stage was unreachable); Step 3's auto-first rework (one primary
  choice + a MODE-AWARE disclosure that respects Step 1's `ocr_mode`:
  auto shows the full drawer, digital hides page-OCR controls,
  scanned shows the locked D2 engine set as information); **B3
  closed** (ocr_timeout + use_paddleocr now flow both directions:
  request fields + map rows + OCRService preferring the request,
  settings fallback for pre-field callers; the honest 120/180/300
  band); the deprecated full-OCR alias PURGED one release after
  V0.7.0 (request field, map row, settings default, ContentPreset
  field, resolver branch, checkbox, review/queue/start-log lines —
  grep-pins assert zero readers). 80 new pin tests across 5 files;
  full-suite differential zero new failures; the phase-gate grabs
  VLM-verified (the pass caught two real defects: a bare `&` eaten as
  a Qt mnemonic, and a hardcoded icon tint — both fixed and pinned).
  Commits `6ceb120` (3c backend) + `395f7ec` (alias purge) +
  `37ec41e` (B3) + `34249d6` (3a+3b) + `1ef6110` (3d) + `9270519`
  (ampersand) + `a5740f0` (palette token) + `59754a3` (format) +
  `10f16c2` (release), tag `V0.7.1` published with the zip.
- **Phase 5 (THIS SESSION):** execute **Phase ④ of the plan — V0.7.2,
  Step 4** (plan §2, "Phase ④"). One phase per session; later sessions
  execute ⑤-⑦ one each (⑤ Step 5 at V0.7.3, ⑥ Step 6 at V0.7.4,
  ⑦ Steps 7-7b at V0.7.5).

## THIS SESSION'S MISSION — PHASE ④: V0.7.2 (Step 4)

Ship V0.7.2 executing plan §2-Phase④ exactly. The four work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

**4a — essentials locked (D7).** Executive + thorough summaries
pre-checked and **disabled** (locked on), caption "Always included —
every other output builds on these." The master "Generate summaries"
switch stays above them as the SINGLE off-switch (audit §W6:
`generate_summaries=False` cleanly no-ops every downstream output).

**4b — five category cards (D8, D6).** The 25 flat checkboxes
reorganize into the five planned categories —
**CORE (always on):** executive + thorough;
**AUDIO** (podcast script, TTS audio); **LEARNING** (flashcards, Q&A,
study guide, glossary, packets); **KNOWLEDGE** (Obsidian KB, mind
map); **DOCUMENTS** (DOCX, EPUB); **REFERENCE** (executive briefing,
evidence map, + the relocated simplified keypoints / compact
summaries). The 5 deprecated outputs (social, patterns, cheatsheet,
skill, quote_bank — `registry.py:261-412`) are **gone from the
wizard** (D6; the backend generators stay for old files). The
**streaming checkbox is deleted** (dead code, audit §W8). **B9 fix:**
the TTS label says "built from the executive briefing" (audit:
`podcast_audio.py:108-131` — the generator reads the *briefing* file,
not the podcast script). Honest evidence-map copy: "needs the
langextract extra — falls back to a guidance page without it."
**Every checkbox gets a tooltip** (audit §W7: none exist today).

**4c — icons (D9).** All control-label emojis (the 10 on Step 4 +
the scattered ones through Steps 2-8, audit §W6 inventory) replaced
with professional SVG line-icons from `ui_qt/components/icons.py`
(extend the set where a glyph is missing). Emoji survive ONLY in log
lines. Note: V0.7.1 already cleaned Step 2's button emoji — inventory
what remains (Steps 4-8 + Review/Start) and do not regress what
landed.

**4d — review + start-log completeness (B8).** Step 8's outputs line
and the start-log enumerate **all non-deprecated selected outputs**
(`step8_review.py:156-183`, `wizard_view.py:880-909`) — driven from
the registry (`core/outputs/registry.py`) so it can never drift again
(the audit found 9-10 newer outputs silently omitted). B9's TTS
wording fix applies on these surfaces too.

**Test + release requirements (the phase gate, plan §3):** AST-pin
the locked essentials (checkboxes disabled + checked BY
CONSTRUCTION); deprecated-absence pin (Step 4 builds no deprecated
checkbox); the W8-moves pin (simplified/compact relocated; the
streaming control gone); registry-driven enumeration pin for review +
start-log (feed a stub registry, assert every key appears); the
B9-copy pin (TTS says briefing); tooltip-presence pin (every output
checkbox has one); full-Step-4 offscreen grabs at 740×540 + 820×600,
both themes, VLM-verified (the V0.7.1 pattern —
`tests/test_v0710_step2_promotion.py`); an icon-set render check;
round-trip pins for every output flag the phase touches
(`to_ui_data` → `_REQUEST_FIELD_MAP` → `ConversionRequest`); full
suite differential + ruff per Rule 2/3; commits/pushes per Rule 7;
one finding family → one conventional commit. Release V0.7.2 per
Rules 5-6 (VERSION bump + tag + push + GitHub Release with
`release_notes/V0.7.2.md` + the zip at
`/home/z/my-project/download/Elixir-V0.7.2.zip`, built with
`git archive --format=zip --prefix=Elixir-V0.7.2/ -o <path> V0.7.2`
BEFORE calling `tools/publish_release.py` — the tool uploads an
existing zip, it does not build one). At the end, write the next
NEW_SESSION_PROMPT.md (Phase 6 = plan Phase ⑤: Step 5 at V0.7.3) and
commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all verified working in the V0.7.1 session):

**Venv:** `python3 -m venv .venv` — CAREFUL: the sandbox's `python3`
IS a venv itself; use the base interpreter directly:
`/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`.
Then: `.venv/bin/pip install -r requirements.txt` plus the FULL extras
list (each absence caused phantom failures historically, all proven):
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
   directly without processEvents for full-wizard grabs; a SINGLE
   step shown alone tolerates one processEvents before grab (the
   passing V0.7.0/V0.7.1 grab tests do exactly this).

**The pre-existing failure inventory on THIS rig (16-17 at the V0.7.1
differential — the documented set, unchanged by V0.7.1):** the
documented 13 (3 stale golden/eval baselines — `test_golden_freeze` +
`test_p4_eval_gate` ×2, the intentional-change procedure is the
owner's call; 5 vibevoice/TTS-constants rig tests; 5 stale source
pins) + 4 rig quirks (the known-flaky
`test_v0600_internal_tabs_e2e::test_full_sequential_run_two_books`
— fails some full-suite runs, passes standalone — it appeared in the
V0.7.1 final run and passed standalone, re-verified; `test_v0619`
big5 + euc_kr — chardet-version statistics on short inputs;
`test_p4_edge_cases_pdf` Farsi presentation-forms — an invisible
codepoint normalization difference). Do NOT try to fix them inside a
phase session (Rule 2 scope); run the suite differentially (baseline
worktree via `git worktree add --detach /tmp/elixir-base HEAD~N`,
same venv, `--deselect tests/test_v0600_tool_transcribe_podcast_e2e.py`,
compare sorted FAILED inventories). Absolute 0 failures is not
achievable on this rig. `tests/test_v0600_tool_transcribe_podcast_e2e.py`
SEGFAULTS in the full-suite combination — deselect it there, run it
standalone (its own 5 standalone failures are pre-existing, identical
both sides — re-verified at V0.7.1). `ruff format --check` flags 12
pre-V0.6.83 files — do not reformat them (Rule 2); keep every file
YOU touch format-clean. ONE MORE rig quirk proven at V0.7.1: an
anonymous GitHub API call (`/releases/latest`) hits a 403 rate limit
— verify releases with the token in the Authorization header, or use
`tools/publish_release.py`'s own output.

**V0.7.1 reference surfaces:** `tests/test_v0710_*.py` (the pin
patterns: source/AST pins, grep-pins, offscreen stub-controller
builds, both-theme grabs at 740×540 + 820×600), the mode-aware
disclosure pattern (`step3_ocr.py` — `_effective_mode()` +
`showEvent` refresh), the live-feedback pattern
(`step2_range.py`), and the PhaseGroupSegmenter +
degenerate-heading gate (`core/segmentation/segmenter.py`,
`page_group_segmenter.py`). The V0.6.86 hotfix pins
(`tests/test_v0686_wizard_hotfix.py`) and the V0.7.0 pin files must
stay green. The M1 de-hardcode census
(`test_m1_theme_tokens.py::test_zero_theme_dependent_colour_literals_outside_theme`)
enforces the no-colour-literals rule — it caught a real regression at
V0.7.1; use `theme_manager.palette` tokens everywhere (the on-accent
token for content on accent fills).

## THE LOOP (session mechanics)

Recover: `cd /home/z/elixir-repo` (clone with the session token if
absent). `git log --oneline -5` — expect the Phase-5 handoff docs
commit (this file, on top) and `10f16c2` (the V0.7.1 release)
directly below it; tag `V0.7.1` pushed. Baseline per the venv + Qt
notes above. Orient: read AGENTS.md, this prompt, the Round-2 plan
(all of §0-§2, especially Phase ④), the audit's §W6/§W7/§W8 sections
+ the dead-code register + §3 bug B8/B9. Skim `step4_outputs.py`,
`step8_review.py`, `wizard_view.py`'s start-log, the outputs registry
(`core/outputs/registry.py`), `core/outputs/podcast_audio.py:108-131`
(the B9 evidence), and the V0.7.1 test files before editing.
Implement → test → commit/push per unit → release V0.7.2 → write the
Phase-6 prompt → commit/push it → report. The phase-phasing approval
(plan §1) authorizes the V0.7.2 release.

## GITHUB Token (one-off, never commit it)

Use the token from the session context for git push. If it is expired,
ask me for a fresh one.

One tip for when you start the new session: paste the prompt above,
then add your GitHub token on a separate line (the same one you gave me
— or a fresh one if it expires). The token never goes in the repo; it
only lives in the chat.

What Phase 5 will deliver in plain words: Step 4 stops being a wall
of 25 cryptic checkboxes with emoji labels. It becomes five tidy
category cards — Audio, Learning, Knowledge, Documents, Reference —
with the two essentials (executive + thorough) locked on and
explained ("every other output builds on these"), the five
deprecated outputs gone, every remaining checkbox carrying a tooltip
that tells the truth (the TTS label finally admits it is built from
the executive briefing; the evidence map admits it needs an extra
package). The emoji on control labels become professional icons. And
the Review step plus the start log stop silently forgetting 9-10 of
your selected outputs — they now list them ALL, straight from the
registry so they can never drift again. It ships as V0.7.2.
