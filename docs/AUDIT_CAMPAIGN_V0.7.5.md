# The V0.6.86 → V0.7.5 Wizard-Rework Campaign — Independent Audit Report (V0.7.6/V0.7.7 session)

> **Verdict first: the campaign did what it claimed.** Every claim in the
> close-out table, the per-release notes, and the bug register was
> re-verified with this session's own runs — **all PASS, zero
> regressions**. The active bug-hunt into the combinations nobody had
> tried found **zero defects**. One real production bug was found during
> the pre-audit cleanup (VibeVoice broken on source installs since
> V0.6.64 — fixed in V0.7.6, not a campaign regression), and one hygiene
> finding was found by the audit itself (legacy settings noise — fixed
> in V0.7.7). The full evidence, per claim, is below.

**Session:** the cleanup + audit session (V0.7.6 then V0.7.7).
**Audited tree:** tag V0.7.6 (suite state identical through V0.7.7 —
the only between-tag changes are the HY-1 migration fix + pins + docs).
**Method:** every verification below is a fresh run from this session
(the exact command or harness is named); nothing was trusted from any
document's memory.

---

## 1. The cleanup that preceded the audit (V0.7.6 — context)

The audit ran against an honestly-green, format-clean tree because the
session's Part 1 first resolved the 13 documented pre-existing failures
and the transcribe e2e's 5 standalone failures. That diagnosis itself
produced a finding: **3 of the 13 "rig-variance" failures were a real
production bug** — VibeVoice TTS has been broken on every source install
since V0.6.64 (the subprocess dies at `ModuleNotFoundError: No module
named 'utils'`; the engine then waits out its 5-minute load timeout).
The three live-protocol tests that caught it had been misfiled as rig
noise in the V0.7.5 close-out. Fixed with a 3-line path bootstrap; the
three tests pass with their pins unchanged. Full root-cause table for
all 18: the V0.7.6 changelog entry + the per-finding commit bodies
(e1ce740 … 27d128d).

## 2. A1 — repo + release integrity: PASS

| Check | Evidence (this session) | Verdict |
|---|---|---|
| git log / tags / VERSION at the release | `git log --oneline -12` at V0.7.6: the release commit on top of the cleanup series; `git tag` shows V0.7.5 + V0.7.6; `VERSION` = 0.7.6 | PASS |
| All campaign releases on GitHub | authenticated API (token in the Authorization header): V0.6.86 → V0.7.6 all present, each with its zip; the `-windows` installer releases present (V0.7.5-windows carries Elixir-Setup-0.7.5.exe) | PASS |
| `/releases/latest` | authenticated call → **V0.7.6** (and V0.7.7 after its release) — the cosmetic quirk (resolving to the -windows variant) is resolved | PASS |
| The V0.7.5 zip asset vs a fresh archive | asset downloaded (33,339,252 bytes) vs `git archive ... V0.7.5`: **raw-byte identical** (and the extracted trees identical) | PASS |
| CHANGELOG / release_notes completeness | headings for V0.6.85/V0.6.86/V0.7.0-V0.7.6 all present; `release_notes/` carries all 8 campaign files + V0.7.6 | PASS |
| The 3 pre-known findings | (a) README badges current — refreshed in V0.7.6 (3580410); (b) scratch files — **PENDING the owner's 1d approval, see §6**; (c) `/releases/latest` → source release — verified above | 2 PASS, 1 PENDING |

## 3. A2 — the suite: PASS

At the V0.7.6 tag: full suite (transcribe e2e deselected per rig
mechanics) **9,196 passed / 0 failed / 51 skipped**; the e2e standalone
**66 passed / 0 failed / 3 skipped**; `ruff check` clean; `ruff format
--check` clean repo-wide (917 files — the 9-flag debt cleared); the
17-file campaign pin ladder (test_v0686 → test_v0750) **415 passed**.
The golden/eval trio (test_golden_freeze's prompt-manifest +
test_p4_eval_gate ×2) — the V0.7.5 re-freeze claims — green, and
`scripts/eval_summary.py --check` → **EVAL GATE: OK**.

## 4. A3 — the whole-campaign differential: PASS (zero regressions)

`git worktree add --detach /tmp/elixir-base 35f13c5` (the parent of the
V0.6.86 hotfix), same venv, both sides run with identical mechanics:
baseline **16 failed / 8,768 passed**; HEAD (V0.7.6) **0 failed / 9,196
passed**. The baseline's 16 = the 13 long-known + the 3 golden/eval
(the campaign's documented in-scope resolution). **Every HEAD-side
failure count is zero — there are no new failures to explain.** The e2e
standalone lists were byte-identical on both sides before this
session's refresh (5 = 5), then 0 after.

## 5. A4 — claim-by-claim: ALL PASS

**B1-B10 (the live-bug register).** Every disposition re-verified by
re-running its pins (all inside the 415-green ladder + the full suite)
and re-checking the original audit evidence no longer exhibits:

| Bug | Disposition claimed | Re-verification |
|---|---|---|
| B1 | fixed (hotfix: `Controller.list_ollama_models`) | test_v0686 pins green |
| B2 | fixed (`ocr_mode` backend) | test_v0700_ocr_mode green |
| B3 | fixed (timeout/paddle reach the backend) | test_v0710_ocr_controls_wiring green |
| B4 | closed by deletion (the slider) | comment-stripped zero-reader greps re-run clean (TOKEN_BUDGET_PRESETS, budget_slider, token_budget absent from runtime code — the remaining hits are the transcribe prompt-budget feature and the llamacpp probe's own token budget, different mechanisms) |
| B5 | fixed (translation round-trip) | test_v0686 pins green |
| B6 | fixed (LM Studio lists from its own URL) | test_v0730 pins green + the hunt's H2 worker-fn capture |
| B7 | fixed (the real translator in the VRAM check) | test_v0740 VRAM call-args pins green |
| B8 | fixed (registry-driven review/start-log) | test_v0720_registry_enumeration green + the sweep's review/start-log checks |
| B9 | fixed (the honest TTS label) | the briefing-based label pinned green |
| B10 | closed by the profiles retirement | `core/pipeline/profiles.py` absent; step1 mentions profiles only in the retirement comment |

**The honesty surfaces** — all re-verified green in the ladder + the
full sweep (34 checks, both themes): Step 7's strategy copy no-drift
pinned against segmenter.py's real AUTO cascade; the coverage caption
("±3 for model randomness, max 3 rounds."); Step 7b's self-consistency
absence + the Settings truthful copy ("Ollama-only; ~3-4× cost;
union-merge") + the provider log line; the harakat manual-review copy on
all five surfaces; Step 6's mode-A derivation + the Review "follows
Step 4" line; Step 5's "Effective after model limits" computed line;
the start-log's no-wizard-unset-values rule (also re-verified live by
the hunt's fully-defaulted run).

**The defaults** 85 / 32768 / 16000 / 2000 verified at every layer:
WizardState (shared.py:144,153,154,120), settings DEFAULTS
(settings.py:378,232 + the ocr/segmentation blocks), the request
(models.py:284,309,317).

**The dead keys.** `translation.outputs.packets` +
`translation.harakat_confident_only`: zero readers, no resurrection
vectors (pinned). `overdeliver_*`: inert legacy, verified precisely —
`_effective_target = coverage_threshold` (summarizer_init.py:421), the
gap-filler's loop condition uses `effective_target`, and the
overdeliver params are signature-only in `gap_fill_concepts` (accepted,
never read in the body).

**The 7d recommended button**: perturb → click → restore across every
control + the no-settings-owned-writes pin — green (ladder).

## 6. A5 — the rendered truth: PASS (0 real defects)

- `scripts/v0750_full_sweep.py` re-run: **34 checks, 0 failures**.
- 28 fresh grabs (the 7 reworked steps × light/dark × 740×540/820×600;
  one variant per process) → vision-model pass with a strict checklist:
  **25 PASS at first pass**.
- The 4 flags (all on the two designed scroll-host steps, all the
  "bottom card clipped" shape) investigated per the zoomed-crop
  discipline: three verified as designed below-the-fold behaviour
  (scroll-to-bottom renders confirmed FULL); the fourth (step 7b dark
  820×600 "content cut") **disproven by exact measurement** — widget
  height == viewport + scrollMax in all four variants (0px unreachable)
  — plus a 3× zoomed crop showing the clean rounded panel border below
  the last control. The third full-page-scale VLM misread this codebase
  has caught by zoom discipline.

## 7. Part 3 — the hunt: 0 defects (29 checks, all green)

`scripts/hunt_v0760.py` (H1-H6): Scanned mode + Token strategy + manual
limit round-trips through the REAL `_REQUEST_FIELD_MAP` into the
request; the LM Studio dispatch bakes its OWN URL into the worker fn;
translation mode B end-to-end (state + the per-key settings writes at
Start); the coverage-loop extremes on the REAL `run_coverage_close_loop`
(target 0 never loops at any coverage; 46% loops once to 56%; 47%
in-band; 96%@100% exhausts at exactly 3 rounds naming its gaps; both
stalled forms report honestly; the Tier-2 guards drop thinking-tainted
and near-duplicate fills); the Step-7 fold toggle rapid-clicked 21×
stays consistent; the fully-defaulted run Step 1 → start-log keeps
every default and prints no wizard-unset value.

**Leftovers sweep:** one benign historical TODO comment; no references
to the deleted controls in the wizard tree (the Settings page's
academic-rigor/self-consistency controls are the designed owners; the
document-type presets that write `summarisation.self_consistency` are
Settings-dialog-only — the wizard's Step-1 cards write state, verified);
no orphan imports (ruff clean). **The deferred backlog is cleanly
deferred** — all five items absent or unchanged (see §9).

## 8. The findings table (everything found this session, all fixed)

| # | Severity | Finding | Root cause | Fix commit | Pinned by |
|---|---|---|---|---|---|
| B11 | **BUG** (found in the cleanup's diagnosis) | VibeVoice TTS broken on every source install since V0.6.64 — the engine's subprocess dies at import (`No module named 'utils'`), the load times out; masked as "rig variance" for 10 releases | c0ee1da added a top-level import to a script spawned bare (sys.path[0] = its own dir) | e1ce740 (V0.7.6) | the 3 live-protocol tests, pins unchanged |
| HY-1 | HYGIENE | Pre-V0.7.0 settings.json files carry the purged OCR keys forever → two "Unknown setting" warnings on every start | the V0.7.4 legacy-pop pattern wasn't applied to the V0.7.0/V0.7.1 ocr purges | 12597e4 (V0.7.7) | tests/test_v0760_audit.py (4 tests) |
| — | (17 items) | The stale pins / library variances behind the 13+5 known failures | V0.6.31/V0.6.41/V0.6.55/V0.6.62/V0.6.77 deliberate design changes + chardet 7.7.0 / pypdf 6.21.x variance | 6a5eb3a, 082f02f, 3593069, dfe47ea+029357b, 245bcf5, 89cb9df, 27d128d | the refreshed pins themselves |

**Observations recorded, no action taken** (documented for the owner):
1. The Settings "Maximum" quality preset flips the truthfully-labelled
   self-consistency checkbox ON (visible, labelled, honest — but it
   enables an Ollama-only feature under a generic "Maximum" name).
2. The close-out's B3 phrasing ("whether any UI ever exposes it") is
   imprecise: the Settings AI-quality page has carried a default-off
   b3-voting checkbox since V0.4.19 — the open decision is really about
   NEW surfaces (the wizard).
3. `gap_fill_concepts` accepts two overdeliver params it never reads
   (signature-only legacy) — a future cleanup could drop them.

## 9. What remains (the menu)

**The deferred backlog (verified cleanly deferred, all still valid):**
1. Harakat → TTS/podcast wiring (D16) — the manual-review copy is on
   every surface; no wiring code exists.
2. Self-consistency on all engines + true majority voting (D10
   follow-up) — still Ollama-gated union-merge with the logged skip.
3. VL image-*description* pass for Scanned mode — absent (copy is
   transcription-truthful).
4. Embedding-based coverage recall metric — absent (the keyword/concept
   metric in use).
5. B3 bullet-voting exposure decision — engine path default-off,
   unexposed in the wizard; the pre-existing Settings checkbox is the
   current exposure.

**Awaiting the owner's 1d approval (presented before the V0.7.6 tag):
the scratch-file cleanup** — delete the 31 `now*.png` + `369.png` +
`508782d6….png` + the three nested zips (~21 MB tracked payload, zero
functional readers, only historical citations in the changelog and
correction MDs), rename `ELIXIR_UI_UX_CORRECTION_ROUND_2 (1).md`, and
add the `/now*.png` .gitignore rule — one chore commit when approved.

**Genuinely unfixable/deferred this session:** nothing else. The three
observations in §8 are candidates for a future micro-cleanup, not
defects.

## 10. The rig baseline (for the next session)

Verified at V0.7.7: venv from the base cpython-3.12 + requirements +
the full extras list; Qt offscreen via the three extracted debs;
suite ~4.5 min with `--no-cov`, foreground, `-p no:randomly`, the
transcribe e2e deselected from full runs (it now passes standalone,
66/0 — the segfault-in-combination quirk remains, so keep
deselecting); `ruff check` + `ruff format --check` both clean
repo-wide — new commits should keep both clean; the eval gate
(`scripts/eval_summary.py --check`) OK. GitHub pushes: the repo
redirects assadigit/elixir → assadigit/Elixir (both work).
