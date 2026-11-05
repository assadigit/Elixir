# New Session Prompt — Elixir Wizard Rework: CAMPAIGN COMPLETE (V0.7.5 shipped; this is the close-out record, not a work order)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## THE HEADLINE (read this first)

**The wizard-rework campaign is FINISHED.** All 7 phases + the hotfix
shipped, one phase per session, exactly as the Round-2 plan sequenced
them. The repo is at **V0.7.5** (tag pushed, GitHub Release published
with the zip — release id 435620062, verified Latest via the
authenticated API). Every finding in the Round-1 audit is now **fixed,
deleted, or honestly documented** — there is no Phase 9. This file is
the campaign-complete record: what shipped, what is deliberately
deferred, and what is left for the owner to call. A future session
should read it as orientation + the backlog menu, then ask me which
item (if any) to pick up.

## WHAT SHIPPED, PHASE BY PHASE (V0.6.86 → V0.7.5)

| Phase | Version | Step(s) | What landed | Bugs closed |
|---|---|---|---|---|
| ① Hotfix | V0.6.86 | — | `Controller.list_ollama_models()` (B1) + the wizard's translation-wipe guard (B5) | B1, B5 |
| ② Shell + Step 1 | V0.7.0 | shell, 1 | StageBar stage-chip header (V1), chrome restyle (V2 shell), the 3 mode cards, `ocr_mode` backend (B2), dead-flag purge, profiles retirement (D4, B10) | B2, B10 |
| ③ Steps 2-3 | V0.7.1 | 2, 3 | Page-range card with the LIVE feedback line, TOC promotion, page-group wiring (D5), Step 3's auto-first disclosure | B3 |
| ④ Step 4 | V0.7.2 | 4 | Essentials locked by construction, 5 registry-driven category cards (D8), deprecated cull (D6), emoji→icons (D9), tooltips, honest TTS label, registry-driven Review + start-log | B8, B9 |
| ⑤ Step 5 | V0.7.3 | 5 | Per-backend model listing incl. LM Studio from its OWN URL (B6), preference memory (D14), single-owner limits (D12) + computed effective values, the §5 defaults unification (85/32768/16000) | B6 |
| ⑥ Step 6 | V0.7.4 | 6 | Two translation modes (D15) + the skip affordance, the harakat manual-review honesty (D16) + dead-key purge, the VRAM truth | B7 |
| ⑦ Steps 7-7b | V0.7.5 | 7, 7b | The advanced disclosure (D17-D19: one primary choice + folded drawer, honest strategy copy no-drift-pinned to segmenter.py, token gate under Token-only), the slider DELETED with its dead Step-4 sync + the deprecated-output presets, the self-consistency relocation (D10: Settings-owned, truthful copy, provider log line), the coverage close-the-loop (D11: ONE target, ±3, max 3 rounds, honest terminal reports; golden re-freeze + eval re-baseline in the same commit), the fine-tune recommended-defaults button (7d) | B4 (by deletion) |

Every live bug B1-B10 now has a disposition: **fixed** (B1, B2, B3,
B5, B6, B7, B8, B9), **closed by deletion** (B4 — the slider), **closed
by the profiles retirement** (B10). The dead-code register items were
purged or wired in their phases (streaming checkbox, auto_detect
scanned, content_filter presets, ocr.retries, is_academic in ui_data,
translation.outputs.packets, harakat_confident_only; QwenOCREngine
left as legacy; the KEYWORD enum left harmless — both by documented
choice).

## THE DEFERRED BACKLOG (recorded, not scheduled — plan §5)

1. **Harakat → TTS/podcast wiring (D16).** The `.harakat.md` output is
   documented as a manual-review file on every surface; wiring it into
   the TTS stack is the follow-up.
2. **Self-consistency on all engines + true majority voting (D10
   follow-up).** It is now honest (Ollama-only, union-merge, logged
   when skipped) — the all-engines fix and a real vote remain future
   work.
3. **VL image-*description* pass for Scanned mode (audit §6.1).** The
   copy is transcription-truthful; describing imagery is a separate
   feature.
4. **Embedding-based coverage recall metric (⑦c stretch).** The loop
   measures with the keyword/concept metric; if it proves gameable,
   swap in the semantic metric.
5. **B3 bullet-voting exposure decision.** The default-off path exists
   in the engine; whether any UI ever exposes it is the owner's call.

## THE OWNER'S-CALL LEFTOVERS

1. **The stale golden/eval baselines — RESOLVED at V0.7.5.** The rig's
   3 pre-existing golden/eval failures (test_golden_freeze's
   prompt-manifest + test_p4_eval_gate ×2) were fixed by 7c's
   in-scope re-freeze (bench --save-golden ×6 + prompt_manifest + eval
   --save-baseline, scorecards identical before/after; manifest hash
   887f44b5… → 0318d35b…). The differential at V0.7.5: **9,183 passed
   vs 9,112 at baseline**, failure inventory 13 = the baseline's 16
   minus exactly those 3 — zero new failures, podcast standalone
   byte-identical (5 = 5).
2. **The 9 pre-V0.6.83 format flags** (test_m2_dashboard,
   test_v0669_local_llm_lights, test_v182048_p6_icon_cache,
   components/icons.py, components/llamacpp_config.py,
   settings/sections/output_sections.py, settings/tts_page.py,
   views/about_system_dialog.py, views/token_cost_dialog.py). ruff
   format --check flags them on every checkout; they are
   byte-identical before/after V0.7.5 and deliberately NOT reformatted
   (Rule 2). A dedicated cleanup release could format them — one
   command, zero behavior change, but it touches 9 files so it needs
   its own commit.
3. **The rig's 13 remaining pre-existing failures** (after the
   golden/eval trio resolved): 5 vibevoice/TTS-constants rig tests, 5
   stale source pins (test_v1820412_c_llm_errors transcribe combo,
   test_v182044 ×2, test_v182049_wb12, test_v18_15_9 primary-button
   outline), and 3 rig quirks (test_p4_edge_cases_pdf Farsi
   presentation-forms; test_v0619 big5 + euc_kr chardet statistics).
   Do not chase them inside a feature session — they need their own
   source-pin refresh session (compare against the real current
   behavior, update the pins, never weaken the regression intent).

## KNOWN RIG STATE (the verified V0.7.5 baseline — for any future session)

The sandbox reset wipes the repo venv and the offscreen Qt libs.
Rebuild as follows (all proven at V0.7.5):

- **Venv:** use the base interpreter directly —
  `/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`,
  then `.venv/bin/pip install -r requirements.txt` PLUS the full
  extras list (each absence caused phantom failures historically):
  `PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2 shiboken6==6.11.2 ebooklib genanki radon hypothesis ruff pytest pytest-cov pytest-asyncio pytest-randomly pymupdf pydub soundfile scipy huggingface_hub chardet reportlab pikepdf arabic-reshaper python-bidi tiktoken`.
  A cosmetic pip warning about pyside6-webengine/pdf wanting 6.12 is
  expected and harmless.
- **Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0`, then
  `dpkg-deb -x <each>.deb /tmp/qt-libs/extract` (ONE deb per command),
  then `export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
  and `export QT_QPA_PLATFORM=offscreen`.
- **Suite mechanics:** ~4.5 min with `--no-cov` (the default addopts
  enable coverage — much slower). Run FOREGROUND (timeout 590) or in
  chunks; background processes are KILLED when a tool call times out.
  Use `-p no:randomly` for stable order. Deselect
  `tests/test_v0600_tool_transcribe_podcast_e2e.py` from full-suite
  runs (it SEGFAULTS in the combination; standalone it fails 5 = 5
  pre-existing). Differential baseline via
  `git worktree add --detach /tmp/elixir-base <pre-work-commit>`, same
  venv, compare sorted FAILED inventories.
- **Offscreen traps (all still true):** never `wizard._go_next()` with
  an invalid step (QMessageBox blocks forever) — drive `_current_step`
  + `_update_step()`; no processEvents for full-wizard grabs (a single
  step shown alone tolerates ONE); one variant per process for manual
  grabs (scripts/grab_v0750_steps7.py is the current driver); stub
  SimpleWorker in BOTH step5_models and step6_translation before any
  full-wizard build (the _FakeWorker in
  tests/test_v0750_steps7_7b.py + scripts/v0750_full_sweep.py cover
  both shapes).
- **GitHub API:** an anonymous /releases/latest call hits a 403 rate
  limit — verify with the token in the Authorization header, or use
  tools/publish_release.py's own output.
- **The golden-drift lesson (V0.7.3, restated):** the freeze harness
  pins its conditions explicitly (bench_chapter.py: 0.50/131072/4096),
  so defaults changes are safe; if a NEW golden drift appears, look
  for an unpinned path before assuming a pipeline regression.

## REFERENCE SURFACES THIS CAMPAIGN ESTABLISHED (copy these patterns)

- The registry-driven output enumeration + the Step-4→translation
  mapping (`core/outputs/registry.py` — no-drift pins against the
  backend's file map).
- The D14 combo memory (`_seed_model_combo`) + worker-threaded listing
  with graceful degradation; the never-a-modal empty case.
- The single-owner rule (Step 5's limits + `effective_limits.py`'s
  computed mirror); the B5-class overwrite lesson (a writer must never
  force a settings-owned value).
- The dead-key purge pattern (DEFAULTS + migration tuple-forms +
  legacy-file pop, pinned by the real-_defaults() data pin and
  comment-stripped zero-reader greps) — used at V0.7.4 (translation
  keys) and V0.7.5 (over-delivery controls removed; the overdeliver_*
  settings keys kept as documented inert legacy).
- The honest-copy no-drift pins (the V0.7.5 strategy copy vs
  segmenter.py's real cascade; the V0.7.4 label parity vs the Settings
  page).
- The close-the-loop pattern (coverage_loop.py): measure → targeted
  reprompt on the missing bits → re-measure → bounded rounds → honest
  terminal report. Reusable for any "make the number mean what it
  says" requirement.
- The pin-file ladder: test_v0686 → test_v0740 → test_v0750 must stay
  green; the M1 theme-token census enforces palette tokens everywhere.

## THE LOOP (any future session)

Recover: `cd /home/z/elixir-repo` (clone with a fresh token if absent —
the one in old session prompts is single-use). `git log --oneline -8`
should show, from the top: this close-out commit, then the V0.7.5
release commit (edcaa6f: VERSION + CHANGELOG + release_notes), then
387dbad (the mixin-census registration), 6ab56cb (the full sweep),
3cfc6a0 (the fold-chevron VLM fix), f1987cb (7d), 343e435 (7c),
3393544 (7b), 72f7d47 (7a); tag V0.7.5 pushed. Read AGENTS.md, this
file, the Round-2 plan (§5 backlog), then ASK ME what to work on —
the campaign is done and nothing is scheduled.
