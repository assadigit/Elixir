# New Session Prompt — Elixir Wizard Rework, Phase 6 (the V0.7.3 Step-5 Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.7.2** (the Step-4 rework just shipped).
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
- **Phase 4 (DONE):** **V0.7.1** — Phase ③ executed: Step 2's
  page-range card with the LIVE feedback line, the TOC action
  promotion, the page-group wiring (D5, behavior first:
  `core/segmentation/page_group_segmenter.py` + the
  degenerate-heading gate), Step 3's auto-first mode-aware disclosure,
  **B3 closed** (ocr_timeout + use_paddleocr flow both directions),
  the deprecated full-OCR alias purged. 80 new pin tests across 5
  files; differential zero new failures; VLM-verified grabs. Commits
  `6ceb120` + `395f7ec` + `37ec41e` + `34249d6` + `1ef6110` +
  `9270519` + `a5740f0` + `59754a3` + `10f16c2`, tag `V0.7.1`
  published with the zip.
- **Phase 5 (DONE, previous session):** **V0.7.2** — Phase ④ executed:
  Step 4 became the Core card (master "Generate summaries" switch +
  executive + thorough **locked BY CONSTRUCTION** — checked + disabled
  in `_build`, `save_to_state` writes literal True, caption "Always
  included — every other output builds on these.") plus five
  registry-driven category cards (**AUDIO / LEARNING / KNOWLEDGE /
  DOCUMENTS / REFERENCE** — D8, with simplified keypoints + compact
  summaries relocated to REFERENCE per §W8); the 5 deprecated outputs
  gone from the wizard (D6); the dead streaming checkbox deleted
  (state field + to_ui_data key purged, grep-pins assert zero ui_qt
  readers); every checkbox carries a tooltip (§W7); **B9 closed**
  (the TTS label says "built from the executive briefing" —
  `podcast_audio.py:108-131` reads the briefing file; honest on the
  checkbox, the registry, review, and the start-log); the
  evidence-map label admits the langextract extra; **B8 closed
  STRUCTURALLY**: the registry grew to 24 specs (17 studio + 7 core —
  executive_summary, thorough_summary, compact_summaries joined; every
  wizard output flag carries `wizard_attr` + `short_name` + a
  distinct `icon_name`) and the new
  `core.outputs.registry.selected_output_names()` is the ONE
  enumeration reader for both the Review outputs line and the
  conversion start-log — feed it a stub registry and the pin asserts
  every key appears, so they can never drift again; **4c** the
  emoji→icons sweep (nine new Lucide glyphs in `icons.py`: package,
  link, graduation-cap, network, map, help-circle, book-open,
  minimize-2, plug; Refresh/Test-connection/Start buttons carry
  professional icons on palette tokens; Steps 5-8 combo items +
  group-box titles + the Review section headers went plain). 61 new
  pin tests across 3 files; full-suite differential **byte-identical
  failure inventories** (the documented 16, zero new); the phase-gate
  grabs VLM-verified (the pass caught one real defect — the bare `&`
  in "Q&A" eaten as a Qt mnemonic — fixed, re-verified, and pinned).
  Commits `c1f5d76` (4d registry/B8) + `bae86cb` (4a+4b+4c Step 4) +
  `76fef66` (Steps 5-8 icons) + `62caeb2` (release), tag `V0.7.2`
  published with the zip (release id 435256935, verified via the
  authenticated API).
- **Phase 6 (THIS SESSION):** execute **Phase ⑤ of the plan — V0.7.3,
  Step 5** (plan §2, "Phase ⑤"). One phase per session; later sessions
  execute ⑥-⑦ one each (⑥ Step 6 at V0.7.4, ⑦ Steps 7-7b at V0.7.5).

## THIS SESSION'S MISSION — PHASE ⑤: V0.7.3 (Step 5)

Ship V0.7.3 executing plan §2-Phase⑤ exactly. The three work items
(all decision numbers and file:line evidence live in the plan — follow
it, not this summary):

**5a — per-backend model listing (B6, D14 — NO auto-pick).**
Ollama → `/api/tags` (the existing path); **LM Studio → its own base
URL `/v1/models`** (today it silently lists Ollama's — the audit's B6:
`step5_models.py:413-427,452-458` — the LM Studio URL is never used
for discovery); llama.cpp → `/v1/models` + the served-model
autodetect (the existing mixin path). All listing stays on
`SimpleWorker` (the established pattern). No "pick best model" logic —
D14 is manual picking, auto-remembered.

**5b — preference memory (D14).** The wizard pre-fills the
summarisation/OCR combos from settings (last-used), and saves the
selections on a successful run — "manual picking, auto-remembered."

**5c — single-owner limits (D12) + computed honesty.**
- Step 5 keeps the ONLY "Model context / Model output" inputs;
  **Step 7b's duplicate "Summarization limits" group is deleted in
  this phase** (its save-order overwrite — audit §W12 — must not
  survive the single-owner change).
- Under the inputs, a read-only computed line shows the *effective*
  values after the backend's clamps (VRAM ladder, ≥32768 context
  floor, 2048/8192/16000 output by model class —
  `summarizer_init.py:538-674`): "Effective after model limits:
  32,768 ctx / 16,000 out".
- Defaults unified (audit §5 table): one default per field, one owner
  — coverage 85 everywhere (state/settings/request 0.85), token-limit
  per segment → Auto (see Phase ⑦), context/output → Auto with the
  computed line as truth.

**Test + release requirements (the phase gate, plan §3):** LM-Studio
listing pin (mocked HTTP per backend); preference-persistence
round-trip pin; Step-7b duplicate-group absence pin; computed
effective-value unit tests mirroring the clamp ladder; full-Step-5
offscreen grabs at 740×540 + 820×600, both themes, VLM-verified (the
V0.7.2 pattern — `tests/test_v0720_step4_outputs.py`; the VLM pass is
`z-ai vision -i <png> -o <json>` from `/home/z/my-project`, then read
the JSON's `choices[0].message.content`); round-trip pins for every
field the phase touches (`to_ui_data` → `_REQUEST_FIELD_MAP` →
`ConversionRequest`); full suite differential + ruff per Rule 2/3;
commits/pushes per Rule 7; one finding family → one conventional
commit. Release V0.7.3 per Rules 5-6 (VERSION bump + tag + push +
GitHub Release with `release_notes/V0.7.3.md` + the zip at
`/home/z/my-project/download/Elixir-V0.7.3.zip`, built with
`git archive --format=zip --prefix=Elixir-V0.7.3/ -o <path> V0.7.3`
BEFORE calling `tools/publish_release.py` — the tool uploads an
existing zip, it does not build one). At the end, write the next
NEW_SESSION_PROMPT.md (Phase 7 = plan Phase ⑥: Step 6 at V0.7.4) and
commit+push it.

## KNOWN RIG STATE (the previous session's verified baseline — read this)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all verified working in the V0.7.2 session):

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
PDF-write / repair / RTL tests). A cosmetic pip warning about
pyside6-webengine/pdf wanting 6.12 is expected and harmless.

**Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0` +
`dpkg-deb -x *.deb /tmp/qt-libs/extract`, then
`export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
and `export QT_QPA_PLATFORM=offscreen`.

**Suite mechanics (verified):** the full suite takes ~4.5 min with
`--no-cov` (the default addopts enable coverage — much slower).
Background processes are KILLED when a tool call times out — run the
suite FOREGROUND (timeout 590) or in chunks; never rely on nohup/setsid
surviving. ONE transient stall was seen at V0.7.2: a large combined
pytest invocation sat 400s with no output once, then the identical
command passed in 6s on retry — if a run seems hung, RETRY or chunk it
before diagnosing. THREE offscreen traps, all proven:
1. **Modal trap:** never call `wizard._go_next()` offscreen with an
   invalid step (QMessageBox blocks forever). Drive `_current_step` +
   `_update_step()` directly.
2. **processEvents trap:** `app.processEvents()` after `show()` on a
   built step sequence natively crashes ("double free or corruption")
   — this happens identically at the pre-V0.7.0 baseline, it is a
   rig/PySide quirk, NOT a regression. Grab directly without
   processEvents for full-wizard grabs; a SINGLE step shown alone
   tolerates one processEvents before grab (the passing grab tests do
   exactly this).
3. **Two-steps-one-process trap (new at V0.7.2):** building step 5,
   showing + processEvents-ing it, then building ANOTHER step in the
   same Python process natively crashed. For manual grab scripts,
   render each step in its own process (the pytest harness is fine).

The pre-existing failure inventory on THIS rig (**16 at the V0.7.2
differential — byte-identical both sides, re-verified**): the
documented 3 stale golden/eval baselines (test_golden_freeze +
test_p4_eval_gate ×2, the intentional-change procedure is the owner's
call), 5 vibevoice/TTS-constants rig tests (tts_e2e GPU contracts,
vibevoice diagnostics ×2, transformers v5, meta init), 5 stale source
pins (test_v1820412_c_llm_errors transcribe combo, test_v182044 ×2,
test_v182049_wb12, test_v18_15_9 primary-button outline), and 3 rig
quirks (test_p4_edge_cases_pdf Farsi presentation-forms — an invisible
codepoint normalization difference; test_v0619 big5 + euc_kr —
chardet-version statistics on short inputs). Do NOT try to fix them
inside a phase session (Rule 2 scope); run the suite differentially
(baseline worktree via
`git worktree add --detach /tmp/elixir-base <pre-work-commit>`, same
venv, `--deselect tests/test_v0600_tool_transcribe_podcast_e2e.py`,
compare sorted FAILED inventories). Absolute 0 failures is not
achievable on this rig. `tests/test_v0600_tool_transcribe_podcast_e2e.py`
SEGFAULTS in the full-suite combination — deselect it there, run it
standalone (its own 5 standalone failures are pre-existing, identical
both sides — re-verified at V0.7.2). `ruff format --check` flags **9
pre-V0.6.83 files** on this checkout (icons.py is one of them — it was
already unformatted BEFORE V0.7.2; do not reformat them (Rule 2); keep
every file YOU touch format-clean, and when extending an already-
unclean file, add only ruff-clean lines and leave the pre-existing
flagged entries untouched). ONE MORE rig quirk: an anonymous GitHub API
call (`/releases/latest`) hits a 403 rate limit — verify releases with
the token in the Authorization header (verified working at V0.7.2), or
use `tools/publish_release.py`'s own output.

V0.7.2 reference surfaces (the patterns to copy): the stub-registry
never-drift pin (`tests/test_v0720_registry_enumeration.py` —
monkeypatch `OUTPUT_REGISTRY`, assert every key appears), the AST
locked-essentials pin + category-card grabs
(`tests/test_v0720_step4_outputs.py`), the icon-set render check +
control-label emoji sweep (`tests/test_v0720_icon_emoji_purge.py` —
reusable for any future step's labels), the mode-aware disclosure
pattern (`step3_ocr.py` — `_effective_mode()` + showEvent refresh),
the live-feedback pattern (`step2_range.py`), and the registry itself
(`core/outputs/registry.py` — 24 specs; `selected_output_names()` is
the ONE reader for review + start-log; Step 4's cards render
`spec.icon_name` via `icon()`, and every registry icon_name must exist
in `ui_qt/components/icons.py` — the render check enforces it). The
V0.6.86 / V0.7.0 / V0.7.1 / V0.7.2 pin files must stay green. The M1
de-hardcode census
(`test_m1_theme_tokens.py::test_zero_theme_dependent_colour_literals_outside_theme`)
enforces the no-colour-literals rule — use theme_manager.palette tokens
everywhere (button icon tints: text_primary on Secondary,
text_on_accent on Primary).

THE LOOP (session mechanics)
Recover: `cd /home/z/elixir-repo` (clone with the session token if
absent). `git log --oneline -5` — expect the Phase-6 handoff docs
commit (this file, on top), then `87728b8` (a docs-only errata: the
V0.7.2 pin-test count corrected 66→61 / registry 29→13, verified by
pytest collect + a green re-run of all 61 — the GitHub release body
was patched to match), then `62caeb2` (the V0.7.2 release); tag
`V0.7.2` pushed. Baseline per the venv + Qt notes above.
Orient: read `AGENTS.md`, this prompt, the Round-2 plan (all of §0-§2,
especially Phase ⑤), the audit's §W9 section (the models step) + §3
bug B6 + the §5 defaults table. Skim `step5_models.py` (the listing
path at 413-427/452-458, the arch combo, the Parameters box),
`step7b_fine_tune.py` (the duplicate "Summarization limits" group at
~150-181 that this phase DELETES), `core/summarisation/summarizer_init.py:538-674`
(the clamp ladder the computed line mirrors), `wizard_view.py`'s
`_load_settings_into_state` (the load-then-save pattern from B5), and
the V0.7.2 test files before editing. Implement → test → commit/push
per unit → release V0.7.3 → write the Phase-7 prompt → commit+push it
→ report. The phase-phasing approval (plan §1) authorizes the V0.7.3
release.
GITHUB Token (one-off, never commit it)
Use the token from the session context for git push. If it is expired,
ask me for a fresh one.

One tip for when you start the new session: paste the prompt above,
then add your GitHub token on a separate line (the same one you gave me
— or a fresh one if it expires). The token never goes in the repo; it
only lives in the chat.

What Phase 6 will deliver in plain words: Step 5 stops lying about
where your models come from. Today, picking "LM Studio" quietly lists
Ollama's models — the LM Studio server is never actually asked. After
this release, each backend (Ollama, LM Studio, llama.cpp) is asked on
its own server, the combos remember the models you picked last time,
and there is exactly ONE place to set the model's context and output
limits — Step 5 — with an honest read-only line underneath showing
what you'll really get after the backend's safety clamps (the copy in
Step 7b that silently overwrites Step 5's values at Start is deleted).
It ships as V0.7.3.

Two quick notes before you start the next session:

Paste the block above first, then your token on its own line below it. The token never goes into the repo — it only lives in the chat.
This is the exact same file that was committed and pushed to the repo as NEW_SESSION_PROMPT.md, so the next session will find matching state on GitHub when it checks.
If your token has expired by then, just ask the next session for a fresh one — it will tell you exactly when it needs it.
