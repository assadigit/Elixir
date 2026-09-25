# Changelog

> 🗄️ **Archive:** entries older than the V0.4.x line (V0.20.x, V0.13–V0.19,
> V0.01–V0.12, and the whole legacy V18.x "MarkItDown Pro" era) now live in
> [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md) — moved verbatim, nothing
> deleted. The versioning-reset mapping (V0.01 = legacy V18.20.4.12) is in the
> archive's V0.01 entry.
>
> 🏷️ **Tag/release hygiene (V0.4.27 / SWOT T8):** two known gaps, both
> cosmetic, both documented here so a provenance-stamp audit isn't confused:
> 1. **Tags without a CHANGELOG heading:** `V0.3`, `V0.3.1`, `V0.4`, `V0.4.1`
>    exist as git tags but have no `## V…` heading in this file (their
>    entries are pre-V0.4.2 → archive-only, or were never separately
>    entered — V0.4.2 is the first heading kept here). Find them via
>    `git tag -l` + `git log <tag>`; the archive's Part 1 has the legacy
>    entries.
> 2. **Headings without a matching tag:** the `## V0.4.20`–`## V0.4.25`
>    headings below correspond to the `V0.20.1`–`V0.20.5` **tags** (a
>    versioning-reset naming split — the tags use the reset-era `V0.20.x`
>    form; the changelog uses the `V0.4.20`–`V0.4.25` form). The
>    `prompt_manifest_hash` + provenance stamps are the authoritative
>    version anchors regardless of the tag-naming form. A future
>    tag-normalization pass could retag, but that rewrites history →
>    deferred (Rule 2: smallest change the evidence supports).


## V0.4.29 — the startup-fix release: the `_warn_ollama` backend-guard + the `find_spec` dep-check fix

> **The release:** two startup-path fixes the owner surfaced by running
> V0.4.28 on the rig (per the `RIG_TEST_CHECKLIST`). Both are pre-existing
> bugs (NOT V0.4.28 regressions — verified: V0.4.28 touched the startup
> path 0 lines), now fixed.

**1. The `_warn_ollama` backend-guard (`ui_qt/app.py:468`):** the startup
  Ollama reachability check fired UNCONDITIONALLY at every launch, warning
  "Ollama not running — LLM OCR and summarisation will not work" for users
  whose configured backends don't use Ollama at all (llama.cpp / openrouter
  / openai / claude / freellmapi). Now: skip unless `summarisation.provider
  == 'ollama'` (the LLM needs it) OR OCR is on the Ollama path
  (`ocr.use_llm` True AND no alternative OCR configured: unlimited_ocr /
  deepseek_ocr2 / paddleocr). The warning message is also made accurate
  (only names what actually needs Ollama). Pre-existing since the initial
  commit (`76d438c`). Commit `5602b6b`.

**2. The `_check_dependencies` `find_spec` fix (`main.py:137`):**
  `_check_dependencies` did `__import__('markitdown')` on every startup,
  importing the ENTIRE `markitdown[all]` transitive tree
  (azure-ai-documentintelligence, youtube-transcript-api, python-pptx,
  openpyxl, onnxruntime, mammoth, magika, …). Compounded by the V18.2.37
  `PYTHONDONTWRITEBYTECODE=1` + `__pycache__`-deletion strategy forcing
  full re-import from source every launch, this was a multi-minute startup
  hang on a Windows rig with a cold `.pyc` cache. Now:
  `importlib.util.find_spec` (presence-check WITHOUT importing) — instant
  + behavior-identical for missing-dep detection. `main.py` stays under
  the 320-line pin (313 lines). Pre-existing. Commit `416dad7`.

**Net-green at the release tip:** ruff 0.16.8 clean; eval gate OK
(`prompt_manifest_hash ee5a61d0` flat); full suite 6,066 P / 0 F / 36 S
exit 0 (no-cov 166 s); `main.py` 313 < 320 (both line-count pins pass).

**Diagnosis note:** the owner should still run `python -X importtime
main.py 2>importtime.log` on the rig to confirm the markitdown import was
the 4-min hang (the `find_spec` fix removes the eager import regardless, so
the fix is correct even if markitdown wasn't the sole culprit). If startup
is still slow after V0.4.29, the importtime log will show the next slowest
import.

## V0.4.28 — the Track-B prep release: the `_summarize_inner` characterization net + the rig punch-list + the rig-test runbook + the E6 sync-only guards

> **The release:** completes the sandbox-doable portion of Track B (the
> Phase-7 SWOT top-5's rig-required track). The validation-dependent items
> (B1 items 1-4 implementation, B3 wire/delete decision, B4 extraction, B2
> execution) stay queued for the owner's Windows rig — this release ships
> the PREP that makes the rig work trivial.

**1. B4 — `summarizer._summarize_inner` characterization net (Phase-7
  O2/O10 / SWOT W2, the de-monolith prep):** +64 hermetic tests
  (`tests/test_summarize_inner_characterization.py`, +1,398 lines) pinning
  the 349-ln method's orchestration behavior: the stage sequence, the
  control-flow branches (empty-input gate, happy path, 4 primary-failure
  hints, map-reduce route, deadline-exceeded), the status strings + log
  skeletons, the return-value shape, the speculative-scholar machinery, +
  the coverage/theorist-floor invocations. The SWOT's recommended FIRST
  step before any extraction — the V18.6.3 crash froze `_build_prompt`
  extraction; this net is what makes `_summarize_inner` safely extractable
  next (ON THE RIG — output-equivalence validation needs the real LLM).
  First tranche (the exhaustive Phase-3-pattern net is a follow-up).
  Commit `1910d1e`.

**2. B2 — T1 rig-test checklist runbook (`docs/RIG_TEST_CHECKLIST.md`):**
  the runbook the owner executes on the Windows 10/11 rig: (a) the 36
  headless-skipped tests categorized (12 camelot/tabula + 14 missing ref
  zips + 9 missing source fixture + 1 rapidfuzz stub) + the
  install/fixture fixes; (b) the Qt GUI smoke procedure (wizard
  walk-through, real conversion, settings, output scanner, crash-report);
  (c) the Windows-specific fragility (torch-before-Qt import order,
  stale-`.pyc` purge, locked-file tolerance — untested headless); (d) the 6
  golden eval-gate chapters + the real-pipeline ch.1 benchmark target
  (≥8/8/7/7 vs the sandbox-rig's 8/8/6/7 conservative floor); (e) the
  sign-off checklist. Commit `3de9dfb`.

**3. B3 — E6 sync-only guard comments (the ADR's deferred follow-up):**
  comment-only guard comments at the 3 E6 blocking-sleep sites
  (`openai_compat_provider.py:265` Batch-API 60×10s poll — the highest-
  severity E6 hazard; `vision_figure_extractor.py:267,295` — the 2s×(n+1)
  retries) so a future async-wiring attempt doesn't miss them. The
  wire/delete decision itself stays the owner's (pending the 3 rig-data
  items in `docs/ASYNC_PROVIDER_DECISION.md`). Comment-only — zero
  behavior change. Commit `e163a3d`.

**4. B1 — Track-B rig punch-list (`docs/TRACK_B_RIG_PUNCHLIST.md`):** the
  consolidated executable plan for the V0.4.26 backlog items 1-4: for
  each, the defect, the fix spec, WHY rig-blocked (B1.1 = prompt change →
  eval re-baseline; B1.2 = heuristic pronoun replacement → needs rig;
  B1.3 = quote-pattern risk → flag-only first; B1.4 = anti-hallucination
  threat → DO NOT loosen the quote-guard blind), the rig data needed, +
  an implementation sketch. B1.4 has a critical Rule-1 compliance note
  (the sociocultural author list MUST come from `extract_citations`, never
  hardcoded). Commit `5ac7dcc`.

**Net-green at the release tip:** ruff 0.16.8 clean (693 files formatted);
eval gate OK (`prompt_manifest_hash ee5a61d0` flat, zero metric drift);
full suite **6,066 P / 0 F / 36 S / 3 warnings exit 0** (no-cov 164 s) —
the +64 tests are the B4 characterization net; the B3 guards are
comment-only; B1/B2/B4-prep are docs/test-only. Coverage TOTAL 66 % (the
`_summarize_inner` net's gains are in-package, under the core+utils total
gate).

**What's NOT in V0.4.28 (the genuinely rig-blocked items):** the B1
implementation (V0.4.26 backlog items 1-4 — see the punch-list), the B3
wire/delete decision (pending the ADR's rig data), the B4 EXTRACTION
(`_summarize_inner` → extracted modules — the characterization net is the
prep; the extraction needs the real LLM for output-equivalence
validation), + the B2 EXECUTION (the 36 rig tests + GUI smoke — the
runbook is the prep). See `docs/TRACK_B_RIG_PUNCHLIST.md` +
`docs/RIG_TEST_CHECKLIST.md` + `docs/ASYNC_PROVIDER_DECISION.md`.

## V0.4.27 — the Track-A release: 3 swallow-log fixes + 3 characterization nets + dead-module sweep + the async_provider ADR + changelog hygiene

> **The release:** executes Track A of the Phase-7 SWOT top-5 actions —
> the sandbox-doable, rig-independent subset. Track B (V0.4.26 backlog
> items 1-4 + the async_provider wiring + the `_summarize_inner`
> de-monolith + the T1 rig-test checklist) stays queued for the owner's
> Windows rig.

**1. The 3 P1 swallow-log fixes (Phase-5 P1 / W3-E1, SWOT top-5 #1):** the
  three load-bearing `except …: pass` sites now surface WARNINGs via the
  existing `log_swallow()` helper (`utils/error_trace.py:76`). Log-only,
  zero control-flow change (Phase-5 P1: "smallest change, no control-flow
  change"). Closes a silent Rule-4 violation.
  - `core/pipeline/conversion/summarization.py:1066` — the book-summary
    provenance-stamping block shipped an UNSTAMPED artifact silently on
    failure (Rule-4 violation, no log). Commit `684ed77`.
  - `core/pipeline/chapter_checkpoint.py:454-456` — the OSError → rewrite
    path could clobber a COMPLETED chapter on a transient AV/indexer lock
    (rewrite-on-true-corruption semantics kept; the WARNING surfaces it).
    Commit `b3c5a5d`.
  - `controller.py:944-947` — the transform-failure path kept the raw
    unvalidated value silently (value NOT logged — may be a secret).
    Commit `29f56c2`.

**2. The 3 conversion/\* characterization nets (Phase-5 P1 / W8, SWOT
  top-5 #3 — the "extracted ≠ tested" debt):** +149 hermetic tests
  (postprocess 52 + visual_features 48 + output_runner 49) following the
  Phase-3 131-test pattern (fake `ConversionContext`, no real pipeline).
  Coverage: postprocess 22 % → 69 % (+47 pp), visual_features 25 % → 70 %
  (+45 pp), output_runner 38 % → 91 % (+53 pp). Commits `b8788cb`,
  `9a65f9e`, `4731bc5`. First tranche (the exhaustive Phase-3-pattern net
  is a follow-up phase).

**3. Dead-module sweep (Phase-5 P3 / W12, F2):** removed
  `ui_qt/components/dialogs.py` (66 ln, zero importers, zero external
  `PasswordDialog` refs — the F2 correction to the "module used" claim).
  Commit `8c4b928`.

**4. The `async_provider.py` + E6 ADR (Phase-5 P3 / SWOT W13):**
  `docs/ASYNC_PROVIDER_DECISION.md` — an evidence-first decision document
  for the 445-ln runtime-dead async provider + the E6 blocking-sleep pair.
  Lays out the 30-40 % chapter-latency lever (case for wiring), the E6
  sleep hazard (case for not wiring blind), the case for deleting (7
  versions runtime-dead, single-GPU VRAM may negate the lever), + the
  decision DATA the owner must provide from the rig. Closes the two-SWOT
  re-discovery loop (V0.11 W8 → Phase-7 W13). Commit `3ac5979`.

**5. Changelog/tag hygiene (SWOT T8):** a header note documenting the two
  cosmetic gaps (4 oldest tags unheaded → archive; `V0.4.20`-`V0.4.25`
  headings ↔ `V0.20.1`-`V0.20.5` tags, a versioning-reset naming split).
  Commit `d7cdf83`.

**Net-green at the release tip:** ruff 0.16.8 clean (690 files formatted);
eval gate OK (`prompt_manifest_hash ee5a61d0` flat, zero metric drift);
full suite **6,002 P / 0 F / 36 S / 3 warnings exit 0** (no-cov 161 s) —
the +149 tests are the 3 characterization nets; the 3 swallow-log fixes +
deletion are behavior-preserving (log-only / dead-code). Coverage TOTAL
66 % (the conversion/\* runners' gains are in-package, under the
core+utils total gate).

**What's NOT in V0.4.27 (Track B, the rig-required queue):** V0.4.26
backlog items 1-4 (theoretical-tensions retry, stem self-containment,
quote-pair balancer, sociocultural floor), the `async_provider` wiring
(decision pending the owner's rig data per the ADR), the
`summarizer._summarize_inner` de-monolith round (after the
characterization net — the next de-monolith target), + the T1 rig-test
checklist. See `docs/ASYNC_PROVIDER_DECISION.md` + the Phase-7 top-5
actions.

## V0.4.26 — the post-SWOT release: markdown year formatting + the third SWOT + the V0.4.26 backlog triage

> **The release:** the third SWOT of the codebase (`docs/AUDIT_SWOT_V0.11.md`
> → Phase 1 baseline → Phase 7 post-session) shipped on `refactor/audit-session`
> in commit `812d14b`, delta-compared vs the Phase 1 baseline (@ `e6032ee`).
> Four Phase-1 items RESOLVED, four IMPROVED, zero regressions; the binding
> quality constraint **inverted** (coverage was the V0.18 ch.1 bottleneck;
> clarity is now). The V0.4.26 backlog (5 clarity fixes from the V0.4.25 ch.1
> benchmark) is triaged here: item 5 ships this release; items 1-4 are queued
> for the rig benchmark (they touch the LLM call path or the quote-guard,
> where a blind fix risks shipping fabricated quotes — the evidence-first
> rule forbids shipping without rig validation).

**1. Markdown year formatting (V0.4.26 backlog item 5 — `core/pipeline/
  chapter_checkpoint.py::format_years` + `_style_years_in_parens`):** emit
  `*YYYY*` (markdown italic emphasis) instead of
  `<em style="font-size:0.9em">YYYY</em>`. The V0.4.25 ch.1 audit flagged the
  HTML leakage (valid for the DOCX pipeline, but it shipped raw into the
  markdown output). Verified the DOCX builder does NOT consume `format_years`
  (zero `<em>`/`year`/`format_years` refs in `core/docx/builder.py`) — so the
  `<em>` was pure markdown-side leakage with no consumer. `*YYYY*` is the
  correct markdown form and renders italic in any compliant viewer. 8
  year-styling test assertions updated in-commit (Rule 3 — the audited quality
  fix); `strip_markup_tags` still handles legacy `<em>` input for robustness.
  Eval gate unchanged (uses stored fixtures; `prompt_manifest_hash ee5a61d0`
  flat). Commit `d164092`.

**2. The third SWOT (`SESSION_REPORT.md` §Phase 7 — commit `812d14b`):** a
  fresh, evidence-first SWOT of the post-refactor tree (@ `f628a43`),
  delta-compared vs the Phase 1 baseline. Census re-run on BOTH trees
  (current `f628a43` + baseline `e6032ee` via git worktree) with a fresh
  AST+grep instrument (`/home/z/audit-tools/census.py`); instruments re-run
  in a fresh venv. Validated against documented numbers (LOC
  142,059→139,598 exact, converter 2,175→1,577 exact, fan-out 38/31 exact,
  12 distinct timeout values exact). Net assessment: 4 RESOLVED (W1 doc load,
  W4 stale docs, W7 .venv hygiene, O1/O3 dead-code sweep), 4 IMPROVED (S1,
  S2, S4, W2), 0 regressions. Binding quality constraint inverted: coverage
  (6→8) → clarity (8→6). 5 NEW items folded from the Phase 5/6 catalog
  (S7-S8, W11-W13, O8-O10, T7-T8). See `SESSION_REPORT.md` §Phase 7 for the
  four SWOT tables + the Phase-1→now delta table + the top-5 actions.

**3. The V0.4.26 backlog triage (items 1-4 queued for the rig):** the five
  ch.1-clarity fixes from the V0.4.25 benchmark backlog:
  - **Item 5 (year format):** SHIPPED above.
  - **Item 1 (theoretical-tensions additive robustness):** the whole-call
    retry-on-mass-drop already exists (`additive_sections.py:373-390`,
    V18.20.3.2); the backlog wants a PER-SECTION retry for the tensions
    section with a structural prompt ("X vs. Y — one line, balanced quotes").
    Needs the rig benchmark to validate the structural prompt actually
    produces balanced tension lines (the sandbox can't run the real LLM).
    QUEUED.
  - **Item 2 (enumeration-stem self-containment):** V0.4.24 did the
    sentence/word alignment (`enumeration.py:528 _aligned_stem`); the
    self-containment part (the label must name its author, never "His work…"
    / "This he sees…") needs the author name threaded into the stem-builder
    — and that name must come from the RUNTIME analysis (Rule 1 forbids
    hardcoding book-derived names). Needs Rule-1-careful design + rig
    validation. QUEUED.
  - **Item 3 (quote-pair balancer):** `repair_stray_quotes_v2` (V0.20.6,
    three D1/D2/D3 detectors) + `repair_d3_quotes_via_llm` (V0.4.11/V0.4.13,
    content-agnostic LLM repair) ALREADY run on bullets/exec/thorough. The
    V0.4.25 ch.1 benchmark still had ~9 unbalanced quotes despite v2 → v2
    doesn't fully catch that defect class. A deterministic close-then-open
    swap detector risks shipping wrong fixes (v2's D3 is flag-only for this
    reason). Needs the rig to see the actual quote patterns + validate a new
    detector. QUEUED.
  - **Item 4 (sociocultural name floor):** the deterministic analyzer's
    `extract_citations` is category-agnostic (extracts ALL author-year
    citations via regex), and the theorist floor checks
    `check_coverage(analysis, thorough)` against whatever the analyzer found
    — so the floor ALREADY covers sociocultural authors IF they're cited
    with year parentheticals. The gap is the quote-guard (the audit noted
    Spitz/Loewenstein gap-fill drops for lacking a verbatim quote). Loosening
    the quote-guard risks shipping fabricated quotes — Rule 1 + the
    anti-hallucination design forbid that without rig validation. QUEUED.

> **Honest disclosure:** V0.4.26 ships one runtime fix (item 5 —
> self-evident, deterministic, no benchmark needed) + the third SWOT + the
> V0.4.26 backlog triage. Items 1-4 are queued for the rig benchmark (they
> touch the LLM call path, the stem-builder's author context, the quote-pair
> logic, or the quote-guard — all places where a blind fix risks shipping
> fabricated quotes or breaking the anti-hallucination guarantee). Per
> AGENTS.md Rule 2 (evidence-first; the fix is the smallest change the
> evidence supports), the sandbox cannot generate validating evidence for
> those four (no local LLM, no sentence-transformers); the rig must.

**Net-green at the release tip:** ruff 0.16.8 clean (exit 0); eval gate OK
(`prompt_manifest_hash ee5a61d0` flat, zero metric drift); full suite
5,853 P / 0 F / 36 S / 3 warnings exit 0 (no-cov 161 s, cov 214 s);
coverage TOTAL 66 % (core/llm 95 / pdf 81 / summarisation 91, all flat).

## V0.4.25 — the run-stamped outputs release: unique filenames per conversion (the 20× stale-upload killer)

> **The release:** the operator reported sending 20+ genuine re-runs that
> arrived as byte-identical stale files. Byte-level verification confirmed
> it: identical md5s, frozen timestamps, and the new version's stamp absent
> from every received file — while uniquely-named binaries transferred
> fine every time. Root cause: the chat/file-transfer layer caches
> attachments **by filename**, and Elixir's output artifacts have stable
> names (`{book}.conversion.log.md`, `{NNN}_{heading}_summary.md`,
> `{book}.summary.md`) — every re-run of the same book collided with the
> first upload's cache entry. The fix is the operator's own proposal: a
> version+run-id hash in every output filename, so each run's artifacts
> are unique and the filename alone proves which version + run produced
> it before the file is even opened.

**1. Run-stamped output filenames (`core/system/provenance.py` —
  `run_stamp_suffix()`):** every run-stamped artifact now carries
  `_v{version}_{run_id}` in its filename, e.g.
  `Broken Structures_v0.4.25_20260923-052332-b3e7f026.conversion.log.md`,
  `001_4_-_BORDERLINE_PERSONALITY_DISORDER_v0.4.25_20260923-052332-b3e7f026_summary.md`,
  `Broken Structures_v0.4.25_20260923-052332-b3e7f026.summary.md`. The
  run_id is unique per conversion (`YYYYMMDD-HHMMSS-<8hex>`) — a filename
  cache hit is impossible. Unstamped (legacy) results fall back to the
  exact legacy filename, so pre-V0.4.25 files, write-once checks, and
  resume globs stay byte-compatible.

**2. The conversion log (`utils/logging.py`):** `ConversionLogger` now
  generates its run_id BEFORE path construction and stamps the log AND
  diagnostic.jsonl filenames. Each conversion's log is its own file —
  runs coexist instead of overwriting, giving every conversion a
  preserved audit trail on disk. Every consumer that matters globs
  `*.conversion.log.md` (output scanner; the controller's crash-append
  takes the NEWEST by mtime), so coexistence is safe.

**3. Chapter summaries (`chapter_checkpoint.py` +
  `conversion/summarization.py`):** the incremental checkpoint saver and
  the end-of-run writer both name chapter summaries with the summary's
  OWN provenance stamp — an adopted (resume-reused) chapter keeps its
  ORIGINAL run's stamp, so the filename always tells the truth about
  which run produced the content. Files still end with `_summary.md`,
  so every resume/scanner glob matches.

**4. The book summary (dual-write):** the canonical `{stem}.summary.md`
  stays stable for every consumer (output scanner, validator,
  translation lookup, multi-PDF merge); a run-stamped sibling copy is
  written alongside it — the unique, attach-without-cache-collision
  artifact for audits. The conversion log names it: "💎 Run-stamped copy
  → …".

**5. ONE run id per conversion:** the Summarizer previously generated
  its own second run_id — one conversion ended up with a log stamped run
  X and chapter summaries stamped run Y (b3e7f026 vs 491d1bf4 in the
  V4.23 audit). The conversion-level id now overwrites it, so the log,
  every chapter summary, the book summary, and every output FILENAME
  stamp share one identifier — an audit correlates all artifacts by a
  single id.

**6. Deterministic newest-wins resume (`chapter_resume.py`):** with
  run-stamped files, multiple runs' chapter summaries coexist in one
  folder; `_find_summary_files()` now returns them NEWEST-FIRST and
  `detect_processed_chapters()` keeps the first valid hit per heading —
  the newest run's content wins deterministically (glob order was
  arbitrary). A crashed run's sentinel-less partial file still falls
  back to the older COMPLETE file — crash-safety holds.

**7. Version-mismatch resume escalation:** adopting an OLDER app
  version's chapter summaries into a newer-version conversion is still
  allowed (the V7.7.0 chapter-skip feature), but it now logs a WARNING
  with the actionable fix ("delete summaries/chapters/ or convert into
  a fresh output folder") — silent stale adoption is exactly how a
  "genuinely new" run ships old content.

**8. 24 new regression tests** (`tests/test_v00425_run_stamped_outputs.py`)
  covering the suffix format/fallback/sanitization, unique log names +
  glob compatibility + header↔filename id parity, stamped chapter names
  (stamped/unstamped/coexistence/manifest), deterministic newest-wins
  resume, legacy-file adoption, and the version-mismatch WARNING; the
  V0.20.4 overwrite test updated to the coexistence contract.

## V0.4.24 — the audit-backlog release: clean labels, the sealed guarantee, provider-aware routing

> **The release:** the V0.4.23 ch.4 audit scored 8/10 and left a 6-item
> deterministic-polish backlog ("every one of these is a mechanically
> fixable code bug — none is model whimsy"). The owner then uploaded the
> V4.23 **conversion log**, which pinned the backlog #3 escape path
> exactly (the ship-time truncation drop killed a guaranteed
> enumeration bullet) **and** revealed a second defect class the audit
> could not see: with `provider = llamacpp`, every model-availability
> probe queried Ollama — simplified keypoints failed 74/74, page OCR
> silently degraded to Tesseract, and figure extraction was skipped
> entirely while llama-server was serving the model. This release fixes
> all of it.

**1. Word/sentence-aligned stems (backlog #1 — the garbled labels):**
  the run-in/block stem extraction took a raw `[-150:]` character
  window, so 8 of 10 consolidated enumeration bullets shipped
  mid-word-sliced labels ("Rom others. unstable identity also found",
  "Tive, structural", "Ree types of", "-if,"). New
  `_aligned_stem()` aligns the window to a word boundary and then to
  the nearest preceding sentence boundary, and `stem_label()` now
  leads with the stem's FINAL sentence's opening words — the sentence
  that actually introduces the list. On the real ch.4 ground truth the
  Stern list's label is now "Stern's criteria" (was "O, classical
  <topic>. His list of").

**2. The thorough_addition truncation guard (backlog #2 — the unclosed
  tag):** the gap-fill call's tag regex required BOTH tags, so a
  max_tokens cut that ate `</thorough_addition>` fell back to shipping
  the RAW response — a visible opening tag and a mid-sentence tail.
  The regex is now unclosed-tag-safe and the cut tail is dropped by
  the SAME `strip_truncated_section_tail` the KD/TT additive path has
  used since V18.20.3.2. The 1024-token cap became 1536 (the honest
  ask is ~400 tokens; see #4 for why it blew up in V4.23).

**3. The sealed enumeration guarantee (backlog #3 — the Stern escape,
  three layers):** the conversion log pinned the exact chain — the
  detector saw Stern's ten criteria as an 8-item run (a PDF paragraph
  break fell inside item (8); items (9)-(10) dropped below the 3-item
  minimum), the guarantee's consolidated bullet therefore ended
  "…organic insecurity or a" (a dangling function-word tail), the
  ship-time truncation drop killed it as "an unverifiable cut claim",
  and the recall floor only LOGGED the 4 missing items. Fixed in
  depth:
  - **the detector joins split run-in lists** (`_join_split_runin_
    paragraphs`): a paragraph ending mid-item followed by a paragraph
    opening with the next sequential marker is re-joined before
    detection. On the real ground truth this recovers three lists the
    V4.23 run mis-saw: Stern's 10 criteria, an 8-criteria list split
    inside item (2), and a 4-position list split inside item (2) that
    was previously missed ENTIRELY — the machine-measured universe
    grew from 21 lists / 117 items to 22 / 125.
  - **guarantee bullets are exempt from the truncation drop** — their
    items are verbatim source text, verifiable against the source, so
    the "unverifiable cut claim" rationale does not apply; the
    exemption is logged as a flag Issue (never silent). The exact
    bullet texts are stashed by the guarantee and threaded through
    `run_post_checks`.
  - **the recall floor now REPAIRS, not just reports** — a
    last-chance `_final_enumeration_repair` re-runs the guarantee
    against the FINAL set (after every drop/dedup/cap stage) and the
    floor is re-measured so the logged number stays honest.

**4. The name-dump fix (backlog #4):** the thorough gap-fill asked ONE
  1024-token call to weave 47 missing names into "150-300 words" —
  the model's only way to comply was a 40-name roster paragraph, and
  the response was cut mid-sentence (defect #2). The call is now
  CHUNKED: ≤12 names per call, at most 3 calls, each with explicit
  anti-roster prompt constraints ("a name list in prose form is
  citation adjacency, not content"). Names beyond the 3-call bound are
  reported honestly (they remain covered by the bullets/recall floor).

**5. The filler floor verb list (backlog #5):** "appears in the same
  citation list" / "shared reference list" — the residual co-citation
  filler shape — joins the rejection patterns.

**6. The attribution-edge filter (backlog #6 — the welded
  attribution):** gap-fill prose sentences are now verified against the
  source before shipping: a sentence whose names NEVER co-occur
  (±600 chars) with any of its distinctive content words is dropped
  with a visible log line — the class that welded a theorist to a
  criticism he never appears near.

**7. Provider-aware model routing (the conversion-log findings —
  NEW, beyond the audit):** every llamacpp user lost three features to
  Ollama-only probes:
  - **simplified keypoints** — `_call_llm`/`_call_llm_single` routed
    every non-cloud provider into `_call_ollama`, whose
    `model_exists()` probe queried Ollama → "Model not found.
    Skipping simplified keypoints." 74/74 times. The llama.cpp server
    (OpenAI-compatible endpoint) is now a first-class route.
  - **vision OCR** — `_create_vision_provider` keyed off
    `request.model_architecture` only; with provider=llamacpp and a
    stale architecture value it probed Ollama, found nothing, and the
    scanned pages silently degraded to Tesseract. The ACTIVE provider
    setting (`summarisation.provider`) is now authoritative, and the
    misleading "not found in Ollama" load-gate warning no longer fires
    on the llamacpp path.
  - **figure extraction** — `VisionFigureExtractor` acquired the same
    provider-aware fallback: when the Ollama model is absent and the
    provider is llama.cpp, images route through llama-server's vision
    endpoint instead of the feature being skipped.

**8. Tesseract PSM retries (the p.107 finding — NEW):** a scanned page
  that returned nothing on the default pass had NO retry (the "OCR
  retries" setting only guarded the Qwen path) and silently vanished
  from the chapter text. `_tesseract_ocr` now retries with alternate
  page-segmentation modes (`--psm 6`, `--psm 4`) before giving up; a
  recovery is logged; the failure message honestly reports "3
  page-segmentation modes tried".

**Gates:** ruff check + format clean; pytest **5,801 passed / 0 failed
/ 43 skipped** (36 new regression tests in
`tests/test_v00424_audit_fixes.py`, including the audit-demanded
Stern-passage reproduction on the exact ground-truth text);
`make eval-check` OK — all 6 golden chapters PASS (fact 10 / cov 8-9),
no quality regressions vs baseline.

## V0.4.23 — the no-limit coverage release: every list item captured, no bullet caps, the 6-item audit backlog fixed

> **The release:** the V0.4.22 ch.4 audit (7/10 — the first sub-9 score
> since V0.3) produced a 6-item code-fix backlog, and the user added two
> directives of their own: **"make no limit for bullet point quantity or
> thorough summary — they can be as long as necessary for full
> coverage"**, and **"catch every listed text in any chapter — bullet
> points, a b c d, 1 2 3 4, II IV V VI — create a template for all
> possible ways authors and scientists might use; never miss any listed
> items; if they are seven, seven must be captured."** This release
> delivers all of it: the six audit fixes, the no-limit policy, and the
> universal enumeration-capture system.

**1. The author garbage filter (audit backlog #1 — kills H1 at the root):**

  - New `core/preprocessing/author_garbage.py`: month names ("May
    1975" matched the Author-Year citation patterns and shipped a
    fabricated theorist), ALL-CAPS tokens (BIOA, DSM), mixed-case
    mirrored-table strings (JOQuUI, aTQNJ), embedded digits
    (JeuoNes0A), non-Latin scripts, and (opt-in, summary side)
    implausible years ("8225") are filtered at the extraction root —
    every consumer (judge, gap-fill hunting, recall floor,
    check_coverage) sees a clean list.
  - Citation years are now ASCII-only (`[0-9]`, not `\d`): Python's
    `\d` matches Arabic-Indic digits, which let the mirrored TABLE 4-1
    fragments "BIOA 0۲۲۶" and "Tey ۸۶8۵" pass as citations.
  - The analysis report prints an honest "Garbage-filtered author
    candidates: N (name (reason); …)" line for the conversion log.
  - `validate_years` (summary side) gained the same stop-lists plus a
    raw-source verbatim exemption: a name quoted in the chapter prose
    (Prichard via a 1975 secondary source) is no longer flagged as
    "name corruption"; the real Dukhaim-class corruption still is.

**2. Page-ref estimate honesty (backlog #2 — H4):** the deterministic
  KD/TT page injector now ships `(p. ~77)` — the tilde visibly marks an
  ESTIMATED locator (position-based, from start_page/end_page), never a
  bare `(p. 77)` that reads as a verified citation. Idempotent on
  re-runs; model-derived refs are untouched.

**3. Active-subject veto precision (backlog #3 — both V0.4.22
  misfires):** the veto gained (a) a possessive-attribution escape —
  "AuthorB's (1969, 1973) attachment theory" attributes the theory
  possessively with no verb, so TRUE bullets are no longer killed
  because a NEARBY sentence attributes something else to another
  theorist; (b) the confirmation overlap is now measured against the
  holder's OWN SENTENCE (not the whole 2-sentence span); (c) "AuthorG
  et al.:" subjects parse the real surname. The real parenthetical-
  promotion vectors (Klein, Searles classes) still veto.

**4. The citation-filler floor (backlog #4 — 7 of 40 shipped bullets):**
  gap-fill bullets whose main assertion is citation adjacency ("is
  recognized for his important contributions…", "is cited in a list of
  sources…", "The text notes…") are rejected at acceptance time —
  wired into the batch gap-fill (with a `filler=` telemetry counter)
  and the scholar gap-fill merge.

**5. Statements-about-omissions (backlog #5):** the false-"missing"
  heuristic exempts omissions the SOURCE ITSELF asserts — "the
  'noteworthy omission' … of psychotic-like episodes" reported by the
  summary is faithful reporting, not a false missing claim. Genuine
  false-missing claims still flag.

**6. NO LIMITS (user directive — supersedes backlog #6):** every bullet
  cap is REMOVED — `bullet_cap()` returns 0, the V0.06 source-scaled
  ship-time cap and the V18.15.7.0 80-bullet cap are gone (replaced by
  honest reporting lines), and every insertion-site budget no-ops. The
  count reducers are the non-skippable semantic dedup, consolidation,
  and the filler floor — never a numeric cap. The prompt now states a
  coverage FLOOR ("at least N bullets — there is NO MAXIMUM"), the
  thorough summary lost its 1200-word ceiling (0.45x the source,
  floored at 800, uncapped) and F1's 1500-word truncation backstop
  scales with the target. The consolidated characteristics bullet that
  the 40-cap silently displaced in V0.4.22 now ships — nothing
  displaces it.

**7. The universal enumeration-capture system (user directive):** new
  `core/summarisation/enumeration.py` — the documented template of
  EVERY enumeration convention (bullets, Arabic 1./1)/(1), letters
  a./a)/(a), A./A), Roman I-IV / i-iv / (i), Greek α-γ, labeled "Step
  1:"/“Criterion A”, outline 1.1, run-in "(1) … ; (2) …" lists, and
  First/Second/Finally ordinal discourse) with a whole-chapter detector
  (sequential-marker validation, wrapped-item continuation, loose
  markdown lists, mirrored-table garbage guard) and a four-layer
  guarantee:

  - **Prompt injection:** an ENUMERATED-LIST COVERAGE block on every
    primary prompt — each detected list's items, with the contract "if
    a list has seven items, all seven must be captured, never six."
  - **Ship-time guarantee:** `_ensure_enumeration_bullets` — any list
    with an uncovered item gets ONE consolidated bullet carrying ALL
    its items verbatim (the V18.15.9.1 "consolidated, not scattered"
    design, generalized to every style and the whole chapter).
  - **Recall floor:** a new probe measures per-item recall across all
    detected lists (bullets + thorough) — the honest number in the
    conversion log ("enumerated items (all lists, whole chapter)
    X/Y").
  - On the real ch.4 ground truth the detector finds 21 lists,
    including the six-criteria, seven-feature, and DSM (i)(ii)(iii)(iv)
    lists, with zero false positives from the OCR-mirrored table.

  Suite: **5,784 passed / 0 failed** (was 5,679; +105 new — 5,679 + 105 = 5,784).
  Gates: ruff check + format clean; `make eval-check` OK (golden
  outputs + eval baseline re-frozen per the documented
  intentional-change procedure — the academic golden chapter now ships
  one previously-capped bullet).

## V0.4.22 — the ABI guard no longer locks you out (second field report, screenshot 4343.png)

> **The release:** the same user hit the V0.4.21 dialog — and this time
> the screenshot proved the message was COMPLETE and readable (cv2
> named, installed numpy 2.5.3 shown, both fix commands visible, nothing
> clipped)… and they still couldn't get past it. Two product defects,
> not message defects: the fix commands said `python -m pip …` (with
> several Pythons installed, bare `python` targets the wrong
> interpreter — the command "succeeds" and fixes nothing), and a broken
> OPTIONAL module (cv2 feeds only the rapidocr vision-OCR chain) was
> hard-blocking the ENTIRE app at startup.

**1. Fix commands now target the interpreter actually running Elixir:**

  - Every command embeds `sys.executable` (quoted, so paths with
    spaces survive cmd.exe): copy-paste it and it can only ever fix
    THE Python that is running Elixir — the classic
    "I ran pip and nothing changed" trap on multi-Python Windows
    machines is gone.

**2. Only numpy itself is fatal — optional modules offer "Continue
  anyway":**

  - cv2 (via markitdown[all] → rapidocr), torch (extras), onnxruntime,
    scipy, and pandas are all OPTIONAL to Elixir's core PDF→Markdown
    pipeline — none of them are imported by Elixir's own code at
    startup. A broken optional module now produces a STARTUP WARNING
    and a dialog with two buttons: **Continue anyway** (default — the
    app opens, everything except the affected features works) or
    **Exit and fix now**.
  - The message names the affected features per failing module
    (cv2/onnxruntime → rapidocr vision OCR; pandas → QuickConvert
    fallback; torch → vision OCR / TTS extras; scipy → TTS extras), and
    the same warning repeats on the console when you continue.
  - numpy ITSELF failing to import (mixed/corrupt install) remains
    fatal: STARTUP ERROR + SystemExit(1), single OK button.
  - Safety of the ambiguous paths: a dialog dismissed without a choice
    (clickedButton → None) and a dialog that cannot be built at all
    both take the exit branch — never a silent continue.

**3. Sharper diagnostics for the broken-numpy case:**

  - `_installed_numpy_version` gains an importlib.metadata fallback:
    when numpy itself cannot import, the distribution metadata still
    reports what is ACTUALLY installed — exactly what a mixed-install
    diagnosis needs (the V0.4.20 classic test now drives this: numpy
    import raises, the report still says "numpy 1.26.4 installed").

**4. The optional-case message is compact and fix-first** (the user's
  window is 816×510): one diagnostic line → the copy-paste commands →
  the affected-features line; tracebacks stay in Show Details. The
  direction-tailored command order (numpy 2.x → numpy restore
  recommended; numpy 1.x → module upgrade recommended) is unchanged
  from V0.4.21.

  Suite: **5,679 passed / 0 failed** (was 5,657; +22 new).
  Gates: ruff check + format clean (588 files); `make eval-check` OK.

## V0.4.21 — numpy ABI dialog: machine-specific report (first V0.4.20 field report)

> **The release:** the first V0.4.20 field report landed: the user's
> startup traceback showed `ImportError: numpy.core.multiarray failed
> to import` from cv2 (an opencv-python build compiled against the
> numpy 1.x ABI, with numpy 2.x installed by mistake — the user
> confirmed the wrong numpy). The V0.4.20 guard fired exactly as
> designed (the pasted traceback was the dialog's "Show Details"
> pane), but its fix dialog had three gaps: it enumerated four modules
> that had NOT failed while never naming cv2 (the module that had), it
> never showed which numpy was installed, and it offered only the
> numpy-downgrade fix. V0.4.21 rebuilds the report so it describes the
> machine that actually broke.

**numpy ABI report now machine-specific
  (`core/system/numpy_abi_check.py`):**

  - ALL ABI failures are collected (not just the first) — the report
    names every module broken on this machine, each with its pip
    package name (`cv2` → `opencv-python`, so the fix commands stay
    copy-pasteable — `pip install cv2` would install the wrong thing).
  - The installed numpy version is shown next to Elixir's own pin
    (`numpy>=1.26.0,<2.0.0`), and the fix advice is tailored to the
    actual mismatch direction:
    - numpy 2.x installed (the field report's case): [A] restore
      `numpy==1.26.4` (recommended), [B] upgrade the failing module(s)
      to numpy 2.x-compatible builds;
    - numpy 1.x installed with a module built against a different
      ABI: [A] upgrade the failing module(s), [B] restore numpy
      1.26.4 — the V0.4.20 dialog wrongly claimed "numpy 2.x" in this
      direction.
  - The console report mirrors the dialog (failing modules + installed
    numpy + the primary fix command), and the "Show Details" pane
    keeps the full traceback per failing module.
  - The report is built by a pure function
    (`_build_abi_error_report`) so the dialog content is unit-testable
    without Qt.
  - Probe list, find_spec pre-filter, ABI marker matching, lockfile
    warning, and the SystemExit(1) contract are all unchanged from
    V0.4.20.
  - New tests: `tests/test_v00421_numpy_abi_report.py` — 12 tests:
    builder pins (the field-report case verbatim, pip-name surfacing,
    no false module enumeration, all-failures collection, traceback
    details, both fix directions, lockfile warning kept,
    version-helper robustness) + an end-to-end run of the real check
    against a simulated copy of the user's machine (stubbed numpy
    2.5.3 + ABI-broken cv2 → console report AND dialog text verified
    via a recording QMessageBox stub). One V0.4.20 pin updated to the
    version-aware header wording (failing module + installed version +
    fix command now surfaced in the console report; the
    guard-firing property itself is unchanged).

  Suite: **5,657 passed / 0 failed** (was 5,645; +12 new).
  Gates: ruff check + format clean (587 files); `make eval-check` OK.

## V0.4.20 — user-reported fixes: type-card icon centering, wizard Step 5 scroll, numpy ABI hardening

> **The release:** three fixes from a real user session (screenshots
> 3434.png / 454545.png): document-type card icons rendered top-left
> instead of top-center, the llama.cpp backend details in wizard Step 5
> were cramped and unreachable, and a numpy 2.x ABI mismatch still
> crashed the app despite the V0.4.4 guard.

**1. Type-card icons now actually centered (top-center, above titles):**

  - A fixed-size `QLabel` added to a `QVBoxLayout` with default
    alignment keeps the ORIGIN-side position when it cannot fill the
    cell — Qt rendered the 64×64 icon at the left edge of every card,
    despite the V1.5 "centered design" docstring. The
    `setAlignment(Qt.AlignCenter)` on the label only centers the pixmap
    WITHIN the fixed 64×64 label, never the label within the card.
  - Fix: `lay.addWidget(self.icon_label, 0, Qt.AlignHCenter)` —
    geometry-verified offscreen: icon center 117–127px vs card centers
    121.5–128.5px on all six preset cards (≤1.5px error).

**2. Wizard Step 5 (llama.cpp backend): scrollable — nothing clipped
  anymore:**

  - Step5Models' content sizeHint (~733px) far exceeds the compact
    wizard's step viewport (~400px at the V7.4.0 740×540 minimum;
    the user's window was 816×510). Unlike Step4Outputs/Step7bFineTune,
    Step 5 hosted its five group boxes directly in the step layout —
    the bottom of "Local configuration" (Test connection button, server
    hint, model combos) and everything below (both API boxes,
    Parameters) were clipped and unreachable.
  - Fix: the house frameless `QScrollArea` host pattern (verbatim
    Step4Outputs shape): all five boxes moved into the scroll host;
    behavioral tests pin the pattern + all five box titles inside the
    host.
  - Polish: the llama.cpp endpoint rows' spacing 5→8 (the three
    label+field rows were visually fused) and the URL/model line edits
    get `setMinimumWidth(260)` so the endpoint stays readable in narrow
    windows.

**3. numpy 2.x ABI crash — the guard could never fire, and the lock file
  re-created the bug:**

  - The V0.4.4 startup probe list was `numpy / pypdf / pdfplumber /
    PIL` — none of which contain compiled numpy code, so the probe was
    structurally incapable of catching the mismatch; the real culprits
    (torch / pandas / onnxruntime / scipy / cv2) imported lazily in
    OCR/TTS workers and crashed later.
  - `requirements.lock` still pinned `numpy==2.5.3`, directly violating
    the app's own `numpy>=1.26.0,<2.0.0` requirement — anyone installing
    via the documented `pip install -r requirements.lock` path reproduced
    the ABI crash.
  - Fixes:
    - `core/system/numpy_abi_check.py`: probe list now covers the
      compiled numpy consumers (torch / pandas / onnxruntime / scipy /
      cv2, find_spec-prefiltered so absent modules skip instantly);
      torch is effectively free in the healthy case (main.py imports it
      before PySide6) and in the broken case the retry re-raises exactly
      what we want to catch. Marker matching broadened beyond the
      classic `RuntimeError: module compiled against ABI version …` to
      the other numpy 1.x/2.x shapes: "compiled using NumPy 1.x"
      (ImportError), "_ARRAY_API not found" (ValueError),
      "multiarray failed to import" (legacy). The fix dialog now also
      warns about the stale-lock install path.
    - `requirements.lock`: `numpy==2.5.3` → `numpy==1.26.4`
      (resolver-verified compatible with the lock's pandas 3.0.6 and
      onnxruntime 1.30.0).
  - New tests: `tests/test_v00420_crashfixes.py` — 24 tests across both
    house layers (source pins + offscreen behavioral), including
    widget-geometry proofs for the card centering and the scroll host,
    and every ABI marker shape driving the guard to its focused
    SystemExit(1) dialog (with non-ABI errors passing through).

  Suite: **5,645 passed / 0 failed** (was 5,610; +24 new, +11 Qt
  behavioral tests now runnable in the offscreen-capable rig).
  Gates: ruff check + format clean (585 files); `make eval-check` OK.

## V0.4.19 — SWOT campaign: heal the test gate, tidiness, safe de-monolithization

> **The release:** The post-V0.4.18 cleanup campaign. The full test suite
> had not been run for 18 releases — this release runs it, fixes all 8
> shipped regressions, completes the settings schema, makes the page-ref
> injector actually fire, and splits all five monolith files into focused
> packages/mixins with byte-identical (VERBATIM) moves, verified by the
> eval gate after every step.

**1. Test gate healed — 8 V0.4.x regressions fixed (the suite was never run during the 18-release campaign):**

  - `eval-check` was RED at HEAD: V0.4.13/V0.4.16 edited the prompts but
    never ran the documented intentional-change procedure
    (`prompt_manifest.py` + `eval --save-baseline`). Re-baselined;
    scorecards byte-identical.
  - main.py was 404 lines (pin <320): the V0.4.4 numpy-ABI check
    extracted VERBATIM to `core/system/numpy_abi_check.py` (319 lines).
  - V0.4.9 `_try_ollama_vision_endpoint` bypassed `safe_ollama_request`
    with a raw `session.post` — invisible to the test boundary AND a
    real-network-call hazard when Ollama runs. Rerouted through the
    monitored transport; 400 bodies still inspected.
  - prompts/default.md book-derived examples ("Kernberg",
    "pathological narcissism") genericized — deny-list tests green,
    prompts now content-agnostic.
  - PDF table tests updated to the intentional V0.4.14 unified `images/`
    folder + `page{N}_image{K}_{kind}` naming; the old "tables come back
    empty" REAL-BUG pin superseded (V0.4.14's PNG fallback now recovers
    the crop).
  - WC9 stale pin updated to the intentional `{endpoint}` form.

  Suite: 8 failed / 5588 passed → **0 failed / 5610 passed**.

**2. Settings schema completed:** 27 actively-read keys that were missing
  from the defaults tree (every read logged "Unknown setting" validator
  noise) are now declared with their exact code fallbacks — including the
  V0.4.x offenders `summarisation.primary_model`, `summarisation.cloud_provider`,
  `ocr.ollama_url`, the whole `observability` section, tts normalize keys,
  and the settings-page read/write keys. Schema: 369 → 397 keys.

**3. Page-ref injector FIXED (mission item: "coded but not appearing in
  outputs"):** the V0.4.13/16 prompts tell the model "The source text has
  YAML frontmatter with start_page and end_page", and the V0.4.16
  injector regexes that frontmatter — but `summarize_chapters` passed the
  RAW segment content, so the prompt's claim was false and the injector
  could never fire. `book_outer._chapter_text_with_page_frontmatter()`
  now materializes the frontmatter from the chapter dict's page info at
  both `_summarize_inner` call sites. First tests ever for the injector:
  `tests/test_page_ref_injector.py` (14 tests).

**4. Safe de-monolithization (all VERBATIM, eval-gate verified after each):**

  | File | Before | After |
  |---|---|---|
  | `postchecks/garble.py` | 3,043 | `garble/` package — 9 modules (lexicon, token_detectors, dropped_letter, author_garbles, quote_repair, fusion, conflation, page_refs + facade) |
  | `postchecks/orchestrator.py` | 1,154 | 526 + `field_phases.py` 796 (bullet/exec/thorough phases + PhaseCtx) |
  | `summarisation/summarizer.py` | 2,753 | 1,988 + `summarizer_coverage.py` 481 + `summarizer_chunking.py` 417 (2 new mixins; bases now 9) |
  | `pipeline/converter_impl.py` | 2,616 | 2,175 + `conversion/visual_features.py` 510 (ConverterVisualMixin: covers, OCR repair, cropper, footnotes) |
  | `ui_qt/settings/sections.py` | 2,303 | `sections/` package — 9 modules (17 QGroupBox classes split by domain + facade) |

  Every extraction moved bodies byte-identical (AST-verified); import
  paths preserved via facades (zero importer edits except pin tests,
  which followed the moved bodies per the house precedent).

**Also:** ruff 17→0 errors, 9 never-formatted V0.4.x files formatted,
  QwenOCREngine routed through `safe_ollama_request` (unified OCR
  transport), dead locals removed.

Full-suite + `make eval-check` green after every step.

## V0.4.18 — text-strategy fallback conditional on VLM availability

The pdfplumber text-strategy table fallback (vertical_strategy='text',
added in V0.4.13) is now CONDITIONAL on having a `vlm_callable`:

  - Without a VLM: lattice strategy only — finds bordered tables, no
    false positives, but misses borderless tables.
  - With a VLM: lattice + text strategy + VLM validation — finds
    borderless tables AND filters text paragraphs via the
    "Is this TABLE or TEXT?" VLM classification.

This eliminates the 24 false-positive text crops on runs without a
vision model configured. Borderless tables may still be detected by
PyMuPDF (Layer 0) when embedded as raster images. To get borderless
table detection via pdfplumber, configure a vision model
(Settings → OCR → Primary model).

## V0.4.17 — VLM-based table/figure validation (intelligent crop filtering)

New VLM-based validation: when a `vlm_callable` is available, each
detected table/figure region is rendered as a low-DPI image and sent to
the VLM with a classification prompt ("TABLE, CHART, DIAGRAM, FIGURE, or
TEXT — output ONLY one word"). Only regions the VLM confirms are saved;
regions classified as TEXT are rejected. Without a VLM, the V0.4.15
heuristic (`_is_real_table`) remains the fallback. The vlm_callable is
threaded from the converter → vision_region_cropper →
figure_table_cropper, reusing the V0.4.1 vision-probe infrastructure.
New: `_vlm_validate_region()`, `_VLM_CLASSIFY_PROMPT`.

## V0.4.16 — page-ref injector + stronger page-citation prompts

Fixes the persistent "0 page refs in KD/TT" issue across V0.4.2–V0.4.14.

  - Stronger prompts (default.md + default_lowbit.md): "Include the page
    number" → "MANDATORY: You MUST include the page number… NEVER omit";
    "Look at the page markers" → "The source text has YAML frontmatter
    with start_page and end_page — use these to estimate the page number"
    + positional examples.
  - New deterministic fallback `inject_page_refs()` (garble.py + orchestrator
    wiring): extracts start/end page from the source frontmatter, finds
    KD/TT bullets lacking (p. N), estimates the page from bullet position,
    appends the ref. Fail-open; no-op without frontmatter.
  - (V0.4.19 note: the injector could not fire in production until the
    V0.4.19 frontmatter wiring fix — see above.)

## V0.4.15 — table validator: reject text paragraphs misidentified as tables

The V0.4.13 text-strategy fallback was too aggressive — multi-column
text layouts were detected as "tables" (26 "table" crops in the V0.4.14
run, only 2 real). New `_is_real_table()` structural validator
(content-agnostic): 2+ columns; average cell length <80 chars; column
count consistent across rows (≥0.7 ratio to the mode); <15 words per
cell. Failing candidates are skipped with a DEBUG log.

## V0.4.14 — unified images/ folder + fix "cannot write mode P as JPEG"

  - Palette-mode fix: pdfplumber renders table crops in palette mode
    ("P") which JPEG doesn't support — the V0.4.13 code silently failed
    on all table crops. Now: try JPEG, fall back to PNG.
  - Unified `images/` folder (was: separate `graphs/` + `tables/`, with
    PyMuPDF classifying table images as "figures"): all crops land in
    one folder with descriptive names — `page48_image1_figure.jpg`,
    `page48_image3_table.jpg` + `.md` twin. Added `SUB_IMAGES` to
    output_paths.py.

## V0.4.13 — D3 LLM repair provider-agnostic + borderless table detection + page-citation prompts

  - D3 LLM repair rewritten to the provider abstraction
    (provider.complete()) — the V0.4.11 version used
    safe_ollama_request (/api/generate), which doesn't exist on
    llama.cpp; the repair silently failed on llama.cpp backends.
  - Borderless table detection: pdfplumber "text" strategy (whitespace
    based) fallback when the lattice strategy finds 0 tables — catches
    space-aligned borderless tables.
  - Page-number citations restored in KD/TT prompts (both default.md and
    default_lowbit.md) — lost in an earlier prompt rewrite.

## V0.4.12 — cross-backend OCR: use Ollama OCR model with llama.cpp main model

When the main summarization model runs on llama.cpp, the OCR model can
now be Ollama-hosted. `_create_vision_provider` falls back to an
Ollama provider when the llama.cpp provider doesn't support vision for
the OCR model (the OCR dropdown is populated from Ollama's /api/tags);
`complete_with_image` gained a `model` parameter so the request goes to
the correct OCR model, not the provider default.

## V0.4.11 — 6 audit fixes: proper-noun auto-repair, D3 LLM repair, cropper Layer 0, multi-author conflation, chunked stylize, Source Excerpts p. fix

  1. Proper-noun garble auto-repair (capitalized garble + capitalized
     source match repairs even when auto_repair=False — guarded against
     common-word false repairs).
  2. `repair_d3_quotes_via_llm()`: semantic LLM repair for flagged D3
     long-span quotes ("fix only the quote pairing"), fail-open, wired
     after repair_stray_quotes_v2 in the thorough post-check.
  3. Cropper Layer 0 fix: `enable_existing_extractors` False→True — the
     V0.4.3 code assumed figure_table_cropper ran above, but that block
     is gated behind the default-off screenshots opt-in, so Layer 0
     never fired on most runs.
  4. `detect_multi_author_conflation()`: flags 2+ authors credited with
     a concept the source attributes to only 1 (flag-only).
  5. Chunked Stylized Markdown: >5000-char documents stylized in
     paragraph-boundary chunks (frontmatter only on the first chunk) —
     prevents output-limit truncation on long PDFs.
  6. Source Excerpts sentence-split regex no longer truncates trailing
     page citations.

## V0.4.10 — OCR tool: Stylized Markdown output (Obsidian atomic notes)

> **The release:** One new feature for the OCR Service tool — a new
> output format that runs a second LLM pass on the OCR'd text to
> structure it into Obsidian-style atomic notes with YAML frontmatter,
> #tags, callouts, and wikilinks.

**Feature — Stylized Markdown (.md) output format**

  New format option in the OCR Service dialog's Format dropdown:
  ```
  Format: [Stylized Markdown (.md) — Obsidian atomic notes ▼]
  ```

  When selected, the OCR pipeline runs two passes:
  1. **Pass 1 — OCR extraction** (same as now): the selected engine
     (Ollama vision / Tesseract / pypdf) extracts raw text from the
     image/PDF.
  2. **Pass 2 — LLM structuring** (new): the raw text is sent to the
     user's configured **summarisation model** (not the OCR model) with
     a prompt that structures it into Obsidian-style atomic notes:
     - YAML frontmatter (`---` with title, source_type, ocr_date, tags)
     - H1/H2/H3 heading hierarchy
     - Atomic notes (1-3 sentences each, broken from dense paragraphs)
     - Markdown tables for tabular data
     - `> [!note]`, `> [!info]`, `> [!warning]`, `> [!tip]` callouts
     - `[[wikilinks]]` around key terms, names, concepts (3-7 per page)
     - `#tags` at the bottom (topic, content_type, source_format)
     - OCR artifact stripping (page markers, garbled characters)
     - OCR error correction (rn→m, 0→O in words)

  The output file is saved as `<filename>_ocr.md` — ready to drop into
  an Obsidian vault.

  **Use case:** you find an interesting infographic, OCR it, and
  instead of getting a flat `.md` file, you get a structured atomic
  note with frontmatter, tags, callouts, and wikilinks — ready for
  your knowledge base.

**Implementation details:**

  - `ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py`:
    - New format option: `.stylized.md` (internally; the file saves as
      `.md`)
    - New `_update_stylize_hint` method: shows/hides a one-line hint
      below the format dropdown when Stylized Markdown is selected
    - New `_stylize_text` method: sends the raw OCR text to the
      summarisation model via `safe_ollama_request` with the stylize
      prompt. Uses `summarisation.model` from settings (the same model
      used for book summaries). Fail-open: if the LLM call fails, the
      raw text is written as-is (the user still gets output).
    - Updated `_ocr_work`: when suffix is `.stylized.md`, calls
      `_stylize_text` after the OCR pass, then writes the stylized text
      as `.md`. Shows a "✨ Stylizing…" progress message during the
      second pass.
    - The `_STYLIZE_PROMPT` is a class-level constant with clear
      structuring rules (frontmatter, headings, callouts, wikilinks,
      tags, OCR artifact stripping, error correction). Content-
      agnostic — works on any source text.

**What was NOT done (deliberate scope limits):**
- Did not run the full PySide6 test suite (GUI tests skip in headless
  environments).
- The stylize prompt is fixed (not user-editable). A future
  enhancement could add a "Stylize prompt" field in the Advanced
  settings modal so users can customize the structuring rules.
- The second pass uses `num_predict=8192` (enough for most OCR'd
  pages). Very long documents (50+ pages) might hit the token limit —
  the output will be truncated. A future enhancement could chunk the
  text and stylize in batches.

---

## V0.4.9 — OCR 400 fix: /api/chat fallback + actual Ollama error body in diagnostics

> **The release:** One targeted fix for the Qwen VL 400 Bad Request
> error that affected custom GGUF models like
> `GLM-OCR-Q8_ggml-org:latest`. The V0.4.6 hint said "this usually
> means the model doesn't support vision" but didn't capture the
> actual Ollama error body — the user couldn't tell whether the model
> was missing, lacked a vision projector, or just needed a different
> API endpoint.

**Root cause:** the OCR code only tried `/api/generate` with the
`images` field. Some custom GGUF models (especially those imported
from ggml.org without their mmproj projector file) return 400 from
`/api/generate` but accept `/api/chat` (which uses a messages-array
format with `images` inside each message's `content` object). The old
code had no fallback, and `safe_ollama_request`'s `raise_for_status()`
discarded the Ollama error body (the specific reason for the 400),
leaving only a generic "400 Client Error" message.

**Fix 1 — `/api/chat` fallback** (`core/ocr/qwen_ocr.py` +
`core/ocr/service.py`):

  Both the `QwenOCREngine._call_ollama_vision` method (used by the OCR
  Service dialog) and the `OcrService._qwen_ocr_single` method (used by
  the main pipeline OCR prescan) now:
  1. Try `/api/generate` first (the traditional endpoint, with
     `prompt` + `images` at the top level).
  2. If that returns empty or 400, try `/api/chat` (with a messages
     array where the user message has `content` + `images`).
  3. If both fail, log the diagnostic.

  The `/api/chat` payload format:
  ```json
  {
    "model": "<model_name>",
    "messages": [
      {"role": "user", "content": "Extract all text...", "images": ["<b64>"]}
    ],
    "stream": false,
    "options": {"temperature": 0.0, "num_predict": 4096}
  }
  ```

  The response is extracted from `message.content` (vs `response` for
  `/api/generate`).

**Fix 2 — Actual Ollama error body in diagnostics** (both files):

  New `_Vision400Error` exception (in `qwen_ocr.py`) and a
  `_try_ollama_vision_endpoint` helper (in `service.py`) that:
  - Capture the **actual Ollama error body** from the 400 response
    (e.g., "model does not support images", "model not found", etc.).
  - The old code used `safe_ollama_request` which calls
    `raise_for_status()` — this discards the response body and only
    gives the generic HTTP status text.
  - The new code uses `get_shared_session().post()` directly and
    reads `resp.json()["error"]` on 400, so the user sees the SPECIFIC
    reason.

  The improved diagnostic message now shows:
  ```
  Qwen attempt N error: 400 Bad Request
    💡 The model 'GLM-OCR-Q8_ggml-org:latest' rejected image input from BOTH
    /api/generate and /api/chat. Ollama's error was:
      <actual error body, e.g., "model does not support images">
    This usually means one of:
      • The model was imported as a text-only GGUF without its
        vision projector (mmproj) file. Re-import with the mmproj:
        ollama create <model> -f Modelfile
        (where Modelfile includes a PROJECTOR line)
      • The model genuinely doesn't support vision. Use a model
        with a built-in vision projector (qwen2-vl, llava, minicpm-v,
        OlmOCR, etc.) — run 'ollama pull qwen2-vl:7b' for example.
      • In Elixir Settings → OCR, pick a vision-capable model.
  ```

**What was NOT done (deliberate scope limits):**
- Did not run the full test suite (OCR tests need a running Ollama
  server with a vision model — not available in the sandbox).
- The `/api/chat` fallback uses `get_shared_session()` directly
  (bypassing `safe_ollama_request`) so it can read the 400 body.
  This is intentional — the shared session is proxy-proof
  (`trust_env=False`, empty proxies) and thread-safe per the
  requests library docs.
- The V0.4.1 provider-agnostic path (`_provider_vision_ocr` in
  `service.py`) uses `provider.complete_with_image()` which routes
  through the LLM provider abstraction. That path is not affected by
  this fix — it's a separate code path that uses the provider's own
  vision call (Ollama or llama.cpp). The V0.4.9 fix targets the
  direct `/api/generate` + `/api/chat` calls.

---

## V0.4.8 — OCR tool: Test OCR feature + Advanced modal + Output folder as basic

> **The release:** Three UI fixes for the OCR Service tool from the
> user's screenshot 5454.png feedback:
>
> 1. Add a "Test OCR" button with a bundled test image so the user can
>    verify the OCR engine works before converting real files.
> 2. Replace the broken Advanced expander with a proper modal dialog
>    (the expander had a layout bug — labels overlapping with input
>    fields).
> 3. Move "Output folder" out of Advanced and into the main view (it's
>    a basic required setting, not advanced).

**Fix 1 — "Test OCR" feature** (`ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py`):

  - New "🧪 Test OCR" button in a dedicated "Test OCR engine" group box
    in the main dialog.
  - Uses a **bundled test image** (`assets/ocr_test_sample.png` — a
    400×200 PNG with clear English text: "Elixir OCR Test", "The quick
    brown fox jumps over the lazy dog.", "1234567890"). The user
    doesn't need to find their own file.
  - Click "Test OCR" → runs the currently-selected engine (Auto /
    Tesseract / Ollama model) on the test image, on a background
    `SimpleWorker` (5-30s, UI stays responsive).
  - Shows the extracted text inline in a monospace result panel:
    - `✅ OCR successful (N chars):` + the extracted text, or
    - `⚠️ No text extracted.` if the engine returned empty, or
    - `❌ Test failed: <error>` if the worker raised.
  - During the run, the button shows "🧪 Testing…" and is disabled.
  - The close guard now also protects the test worker (same
    "QThread: Destroyed while thread is still running" class as the
    convert worker).

**Fix 2 — Advanced is now a modal dialog** (not an expander):

  - The V0.4.5 inline expander had a layout bug (screenshot 5454.png
    showed labels overlapping with input fields — the QToolButton +
    hidden QWidget pattern didn't lay out cleanly inside the dialog's
    QVBoxLayout).
  - Replaced with a "⚙ Advanced…" button (bottom-right of the main
    view) that opens a **modal QDialog** with a proper QFormLayout:
    - Legacy engine (dropdown: pypdf / Local VLM)
    - Page range (text input: "all" / "1-10" / "1,3,5")
  - Each control has a one-line hint below it.
  - The state (range_edit + legacy_engine_combo) lives on `self` so
    `_do_convert` reads it the same way as before. The modal just
    reparents the widgets to itself while open, then back to `self`
    on close (try/finally ensures reparenting even on cancel).

**Fix 3 — Output folder is now a basic control** (was inside Advanced):

  - Moved the "Output folder: [____________] [Browse…]" row out of
    the Advanced section and into the main view, right after the
    Format dropdown.
  - It's a **required** setting for every conversion, so it belongs
    in the main view (the user's explicit feedback: "Output folder
    must be outside advanced because it's basic setting").
  - The Advanced modal now only contains the truly-advanced controls
    (legacy engine + page range).

**New bundled asset** (`assets/ocr_test_sample.png`):

  - 400×200 PNG, 13 KB, generated with Pillow.
  - Contains: "Elixir OCR Test" (title), "The quick brown fox jumps
    over the lazy dog." (pangram), "1234567890" (digits).
  - Clear, high-contrast text that any OCR engine (Tesseract, Ollama
    vision) can extract.
  - Path resolution is robust: tries 3 candidate paths (5-parents-up
    from the dialog file, 4-parents-up, cwd/assets) so it works
    regardless of install layout.

**What was NOT done (deliberate scope limits):**
- Did not run the full PySide6 test suite (GUI tests skip in headless
  environments — recommended as the next session's first step).
- The test image is English-only. A future enhancement could add a
  Persian/Arabic test image (the user's screenshot showed a Persian
  filename) to verify right-to-left OCR.

---

## V0.4.7 — fix Settings crash (lazy tab loading + async dependency check)

> **The release:** One targeted fix for the "Settings → Not Responding"
> crash. The root cause: `SettingsDialog.__init__` eagerly built every
> section class on dialog open — including the `DependenciesSection`
> which runs `check_all()` synchronously on the UI thread (17
> `importlib.import_module()` calls + 5 subprocess calls + 2 HTTP calls
> to Ollama = 30+ seconds of blocking on a cold Windows rig). Windows
> interprets this as "Not Responding".

**Fix 1 — Lazy tab loading** (`ui_qt/settings/settings_dialog.py`):

  - New `_LazyTabPlaceholder` class: each tab starts as a lightweight
    placeholder (just a "⏳ Loading…" label). On first `showEvent`, it
    builds the real section widgets and replaces the placeholder.
    Subsequent shows are no-ops.
  - `SettingsDialog.__init__` now creates placeholders instead of
    eagerly instantiating every section class. This defers ALL heavy
    work (imports, HTTP, subprocess) until the user actually clicks the
    tab. The dialog now opens **instantly**.
  - The placeholder's `save()` + `reload()` methods forward to the real
    sections (if built); if a tab was never shown, its save is a no-op
    (nothing to save).
  - `_PresetsPage` and `PromptsPage` (the special head groups) stay
    eager — they're lightweight (card grid + prompt-file reads, no
    imports or HTTP).

**Fix 2 — Async dependency check** (`ui_qt/settings/dependencies_page.py`):

  - `DependenciesSection._recheck()` now runs `check_all()` on a
    `SimpleWorker` (background thread), mirroring the pattern already
    used by the TTS Kokoro check (`_check_kokoro_async`) and the OCR
    models refresh (`_refresh_models_async`).
  - The UI shows an immediate "⏳ Checking dependencies…" placeholder
    (blue summary bar + centered hint) so the user sees the dialog is
    alive. The Recheck button is disabled + relabeled "🔄 Checking…"
    during the run.
  - When the worker finishes, `_on_check_finished` rebuilds the
    dashboard on the main thread (Qt's queued signal marshals there).
    If the worker raises, `_on_check_failed` shows the error.
  - Re-entrant guard: if a check is already in flight, subsequent
    Recheck clicks are ignored (don't stack workers).
  - The worker ref lives on `self._check_worker` to keep the QObject
    alive mid-run.

  **Before:** opening Settings ran 17 imports + 5 subprocess + 2 HTTP
  synchronously on the UI thread → 30s+ "Not Responding".
  **After:** opening Settings is instant; clicking the Dependencies
  tab shows "⏳ Checking…" immediately, then populates the dashboard
  when the background worker finishes (~5-30s depending on the rig,
  but the UI stays responsive throughout).

**What was NOT done (deliberate scope limits):**
- Did not run the full PySide6 test suite (GUI tests skip in headless
  environments — recommended as the next session's first step).
- The individual section __init__ methods (OCR models, AI local model,
  TTS engines) already use async workers for their HTTP/import probes
  (V18.20.4.5 W-b11, W-b8). The lazy-loading fix means these now only
  run when the user clicks the corresponding tab, not on dialog open.
- The `_check_ollama()` in `core/system/dependency_checker.py` still
  has a 2s timeout — combined with the other checks, the total
  background-worker time is the same as before, but it no longer
  blocks the UI.

---

## V0.4.6 — fix settings-schema warnings + suppress libpyside disconnect warnings + Qwen 400 hint

> **The release:** Three noise-reduction fixes from the user's V0.4.2 run
> log. The log showed:
> - 11 "Unknown setting" warnings for missing `tts.normalize_*`,
>   `podcast.*`, and `ai.*` keys (polluting every settings page load +
>   podcast/TTS generation).
> - 7 libpyside "Failed to disconnect" RuntimeWarnings on every
>   "Convert again" run (PySide6 6.x emits a warning when disconnect()
>   is called on a non-connected slot).
> - 2 Qwen VL 400 Bad Request errors with no diagnostic hint.

**Fix 1 — Missing settings keys added** (`utils/settings.py`):
  - `tts.normalize_model` (default ""), `tts.normalize_api_key` (default
    ""), `tts.normalize_context_mode` (default "sentence") — read by
    `core/tts/normalizer.py` + `ui_qt/settings/tts_page.py`. The api_key
    is stored in the OS keychain but falls back to `settings.get()` when
    the keychain is unavailable, so the key must exist in the schema.
  - `podcast.hosts` (2), `podcast.scope` ("per_chapter"),
    `podcast.depth_mode` ("exhaustive"), `podcast.target_minutes` (30),
    `podcast.exhaustive_cap_enabled` (True),
    `podcast.exhaustive_cap_minutes` (120), `podcast.include_intro`
    (True), `podcast.include_outro` (True) — read by
    `core/outputs/podcast_generator.py` + `ui_qt/settings/podcast_page.py`.
  - `ai.backend` ("Ollama"), `ai.custom_backend_url` ("") — legacy keys
    read by `ui_qt/settings/sections.py`. The actual backend config now
    lives under `summarisation` + `llm`, but the legacy keys are still
    read for backward compatibility.
  - All 13 keys also added to the settings merge-migration block so
    existing `settings.json` files get them on next load.

  Validated: fresh `Settings()` load now produces **0 "Unknown setting"
  warnings** (was 11).

**Fix 2 — libpyside disconnect warnings suppressed**
(`ui_qt/controller_bridge.py`):
  - `_connect_unique` wraps `signal.disconnect(slot)` in a
    `warnings.catch_warnings()` context that filters out the
    `RuntimeWarning` with message `.*Failed to disconnect.*`. PySide6 6.x
    emits this warning via the Python `warnings` module (not just the
    C++ side) when disconnect is called on a non-connected slot — the
    old code caught the exception but didn't suppress the warning.
  - 7 warnings per "Convert again" run → 0 warnings.

  Validated by simulating the PySide6 disconnect behavior: the
  suppression correctly hides the warning while the exception handler
  still catches the (rare) actual exception.

**Fix 3 — Qwen VL 400 error diagnostic hint** (`core/ocr/qwen_ocr.py`):
  - When `_call_ollama_vision` catches a 400 Bad Request from
    `/api/generate` with an images payload, it now logs a helpful hint:
    ```
    Qwen attempt N error: 400 Client Error: Bad Request for url: ...
      💡 This usually means the model '<model_name>' either doesn't
      support vision (image input) or isn't installed in Ollama. Check:
        1. ollama list  (is '<model_name>' present?)
        2. The model must be a vision model (e.g., qwen2-vl, llava,
           minicpm-v, OlmOCR).
        3. In Elixir Settings → OCR, pick a vision-capable model.
    ```
  - This directly addresses the user's Qwen VL 400 error — the most
    likely cause is a model-name mismatch or a non-vision model
    configured for OCR.

**What was NOT done (deliberate scope limits):**
- Did not run the full PySide6 test suite (GUI tests skip in headless
  environments — recommended as the next session's first step).
- Did not change the Qwen VL request format — the 400 error is a
  model-configuration issue, not a code bug. The user needs to verify
  their Ollama model supports vision input (the new hint makes this
  clear).

---

## V0.4.5 — OCR dialog redesign (minimize cognitive load) + auto-detect Ollama OCR models

> **The release:** One targeted UI fix for the OCR Service dialog the user
> found "too confusing" (screenshot 3434.png). The VLM analysis of the
> screenshot identified 5 cognitive-load problems:
>
> 1. The "Output fo" dropdown was visually broken — it displayed engine
>    names, not output formats (label was truncated too).
> 2. `Format` looked disabled (label said "Default (change in Settings)").
> 3. Redundant engine selection — two dropdowns both listing engines.
> 4. The "Auto" option forced users to understand the backend cascade
>    ("pypdf → Ollama → VLM → Tesseract") just to pick an engine.
> 5. Wasted vertical space (huge file-input box) vs. cramped config rows.
>
> **The redesign:** collapse 4 visible controls → 2 (Engine + Format),
> move Page range + Output folder + legacy engines under an "Advanced"
> expander, add "Auto (recommended)" as the default, auto-detect every
> Ollama model with an OCR-related name via live `/api/tags` probe, and
> show a one-line "why this engine" hint below the engine dropdown.

**Fix 1 — `OcrServiceDialog.__init__` redesigned** (`ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py`):

  Visible controls (was 4, now 2):
  - **Engine** dropdown — "Auto (recommended)" first + default, then
    auto-detected Ollama OCR models (see Fix 2), then "Tesseract" as a
    guaranteed offline fallback.
  - **Format** dropdown — 4 options, "Markdown (.md) — recommended"
    first + default (no "Default (change in Settings)" confusion).

  Hidden under the "⚙ Advanced" expander (default collapsed):
  - **Legacy engine** — pypdf + Local VLM (for users who specifically
    want them; most users don't need to touch this).
  - **Page range** — "all" by default, with the hint "💡 PDFs only".
  - **Output folder** — Browse… button.

  Other UI improvements:
  - One-line `engine_hint` label below the engine dropdown explains
    what the selected engine does (e.g., "💡 Tries the best engine
    automatically: digital PDFs use pypdf, scanned docs use Ollama
    vision, with Tesseract as a fallback."). The user no longer needs
    to understand the backend architecture.
  - Compact file-list (60–80px height, was 80–120px).
  - 🔄 refresh button beside the engine dropdown — re-probes Ollama
    if the user started it after opening the dialog.

**Fix 2 — Auto-detect Ollama OCR models** (new `_populate_ollama_models` method):

  On dialog open (and on 🔄 click), the dialog queries `GET /api/tags`
  via `utils.network.list_ollama_models()` and filters the returned
  model list by OCR-related name keywords (case-insensitive):

  `ocr`, `vision`, `vl`, `llava`, `minicpm`, `moondream`, `bakllava`,
  `llama-vision`, `qwen-vl`, `internvl`, `cogvlm`, `fuyu`, `kosmos`,
  `florence`.

  The discovered models are inserted into the engine dropdown right
  after "Auto (recommended)" and before "Tesseract", labeled
  `Ollama: <model_name>`. Content-agnostic — the keyword list covers
  all major OCR/vision model families; no hardcoded specific model
  versions.

  Validated against a simulated 11-model Ollama registry: correctly
  detected 6 OCR models (OlmOCR-2-7B, qwen2-vl:7b, llava:13b,
  minicpm-v:8b, moondream2:latest, qwen-vl:7b) and correctly excluded
  5 non-OCR models (qwen2.5-coder, llama3.1, phi3, tesseract, nomic-
  embed-text). 0 false positives, 0 false negatives.

**Fix 3 — Engine resolution logic updated** (`_do_convert`):

  The new UI structure means the main `engine_combo` can hold:
  - "auto" (the recommended default)
  - "tesseract" (the offline fallback)
  - an Ollama model name (from the live `/api/tags` probe)

  The legacy engines (pypdf, vlm) moved to the Advanced expander's
  `legacy_engine_combo`. If the user picked a legacy engine there,
  it overrides the main dropdown (explicit user choice takes
  precedence).

  When the user selects an Ollama model, the dialog saves it as
  `ocr.primary_model` in settings, so the `_ocr_ollama()` backend
  call picks it up automatically (no backend code changes needed).

**What was NOT done (deliberate scope limits):**
- Did not run the full PySide6 test suite (the GUI tests skip in
  headless environments — recommended as the next session's first
  step before the next rig run).
- The "Format" dropdown no longer has a "Default (change in Settings)"
  option — the V0.4.4 audit found this label was confusing (it made
  the control look disabled). The default is now "Markdown (.md) —
  recommended" which is the most common choice. Users who want to
  change the default globally can edit `quick_services.ocr.format`
  in settings.json (backward-compat resolution still works).

---

## V0.4.4 — fix numpy 2.x ABI mismatch (the "settings → OCR" crash)

> **The release:** One targeted fix for the crash the user reported when
> opening Settings → Independent OCR Tool. The screenshot (4545.png)
> showed:
>
> ```
> RuntimeError: module compiled against ABI version 0x1000009
> but this version of numpy is 0x2000000
> ```
>
> **Root cause:** `requirements.txt` had `numpy>=1.26.0` with no upper
> bound, so pip resolved `numpy==2.5.3` (per `requirements.lock`). A
> compiled C extension (torch / transformers / pandas / scipy / langextract)
> was built against numpy 1.x ABI. When the user opened Settings → OCR
> (which imports `torch` lazily), the import triggered the ABI mismatch
> → RuntimeError → the global `sys.excepthook` caught it as a generic
> "Unexpected error" dialog with no actionable fix.

**Fix 1 — Pin numpy to < 2.0.0** (root-cause fix for fresh installs):
  - `requirements.txt`: `numpy>=1.26.0` → `numpy>=1.26.0,<2.0.0`
  - `pyproject.toml`: same pin in the dependencies array.

  This ensures `pip install` resolves a numpy 1.x version that's
  compatible with all compiled dependencies. Existing installs with
  numpy 2.x need to run `pip install "numpy<2"` manually (see Fix 2).

**Fix 2 — Startup guard + runtime detection** (for existing installs
that already have numpy 2.x):
  - `main.py`: new `_check_numpy_abi_compatibility()` runs after
    `_check_dependencies()` and BEFORE the main window opens. It probes
    `numpy`, `pypdf`, `pdfplumber`, and `PIL` for the ABI error. If
    detected, it shows a focused dialog with the exact fix command
    (`pip install "numpy<2"`) instead of a generic crash report.
  - `main.py`: the global `sys.excepthook` now detects the ABI error at
    runtime (it fires lazily when the user opens Settings → OCR which
    imports `torch`) and shows the same focused fix dialog. This catches
    the case where the startup probe passed but the lazy import later
    fails (exactly the user's scenario).

  Detection is content-agnostic: catches ANY `RuntimeError` containing
  both `"ABI version"` and `"numpy"` (case-insensitive). No hardcoded
  module names or numpy version strings — works for any future numpy
  ABI mismatch, not just the 1.x→2.x one.

  Validated by simulating the exact error from the screenshot:
  - The simulated `RuntimeError("module compiled against ABI version
    0x1000009 but this version of numpy is 0x2000000")` is correctly
    detected (triggers the focused dialog).
  - A generic `RuntimeError("some other runtime error")` is correctly
    NOT detected (falls through to the generic "Unexpected error"
    dialog).

**Immediate fix for the user:** open a terminal and run:
```
pip install "numpy<2"
```
Then restart Elixir. V0.4.4 will prevent this issue on future fresh
installs (the pin ensures pip resolves a compatible numpy).

**What was NOT done (deliberate scope limits):**
- Did not regenerate `requirements.lock` (the lock file still shows
  `numpy==2.5.3` — the user should regenerate it with
  `pip-compile requirements.txt` after this change takes effect, OR
  just run `pip install "numpy<2"` to override the lock).

---

## V0.4.3 — vision-region cropper wired in (default ON) + sentence-fusion detector + padding-bullet suppression

> **The release:** Three fixes from the V0.4.2 audit follow-up. The headline
> is that the V0.4.2 vision-region cropper prototype is now WIRED INTO the
> conversion pipeline as a **default-ON** feature — the user's "crop the
> diagram and screenshot that specific region" request is now live. Two
> additional content-agnostic fixes address the V0.4.2 NPD audit's findings
> (sentence-fusion garbles + padding bullets).
>
> **Validation:** 5-step smoke test passes (imports, settings defaults,
> sentence-fusion detector catches both V0.4.2 fusions with 0 false positives,
> padding-bullet detector catches all 3 V0.4.2 padding bullets, cropper
> integration finds 2 regions on a synthetic 3-page PDF).

**Fix 1 — `extract_visual_regions` wired into the pipeline (default ON):**
the V0.4.2 `vision_region_cropper.py` was a standalone prototype. V0.4.3
wires it into `core/pipeline/converter_impl.py` as a default-ON feature
gated by the new `advanced.extract_visual_regions` setting (default
`True`). When enabled, the pipeline:
  1. Runs Layer A (vector-graphics clustering) — catches vector-drawn
     diagrams that PyMuPDF misses entirely.
  2. Auto-enables Layer B (VLM region detection) when a vision model is
     available — reuses V0.4.1's provider-agnostic vision probe via the
     new `build_vlm_callable_from_request` bridge.
  3. Crops all detected regions at high DPI (200) into `regions/`.
  4. Embeds `![Figure N: caption](path)` inline in the chapter markdown
     at the right `<!-- original page N -->` markers (Layer C).

Changes:
  - `core/models/models.py`: added `extract_visual_regions: bool = True`
    field to `ConversionRequest`.
  - `utils/settings.py`: added `advanced.extract_visual_regions: True`
    default + merge migration.
  - `controller.py`: added the settings→request field mapping (default
    `True`).
  - `core/pipeline/output_paths.py`: added `SUB_REGIONS = "regions"` +
    `regions_dir` property.
  - `core/pipeline/converter_impl.py`: wired the cropper call after the
    existing `table_graph_extractor` block (mirrors its page-selection
    logic + cancel gate).
  - `core/pipeline/conversion/settings_logger.py`: logs the new flag.
  - `core/pdf/vision_region_cropper.py`: added
    `build_vlm_callable_from_request` bridge + improved the clustering
    (two-pass with bbox-distance merge; threshold 50→80pt — the V0.4.2
    single-pass at 50pt split a 10-bar chart into 3-4 small clusters of
    3-4 bars each, none reaching the 5-min).

**Fix 2 — `detect_sentence_fusion` (audit D4):** new detector in
`core/summarisation/postchecks/garble.py` that catches sentence-boundary
fusion garbles the V0.4.2 NPD thorough shipped (`praiseity` = praise + ity,
`self-developmentstic-masochistic` = development + stic + masochistic).

Two patterns, both content-agnostic:
  - **Pattern A** — source-word prefix + short non-inflectional suffix at
    the end (catches `praiseity`). Skips legitimate English inflections
    only when the full word IS a real English word (the vendored
    `data/english_lexicon.txt.gz`).
  - **Pattern B** — 2 source-word substrings separated by a 3-8 char
    non-source gap (catches `self-developmentstic-masochistic`).

Validated on 3 uploaded chapter summaries:
  - Ch.3 (v0.4.2 NPD): 2 flags — `praiseity` + `self-developmentstic-
    masochistic` (both confirmed by manual audit).
  - Ch.1 (v0.18): 0 flags.
  - Ch.2 (v0.3): 0 flags.
  - 0 false positives.

Wired into the orchestrator at all 3 call sites (bullets/exec/thorough).

**Fix 3 — padding-bullet suppression (audit D5):** new
`_is_padding_bullet` helper in `core/summarisation/postchecks/orchestrator.py`
drops gap-fill bullets that convey no substantive claim, only co-citation.
Content-agnostic patterns (match the SHAPE, not specific author names):
  - "no specific contribution... is explicitly attributed to X"
  - "X's contribution is not clearly discernible from the provided source"
  - "X is cited in the source text alongside other ... references"

Validated on the V0.4.2 NPD output: catches 3 padding bullets (Waals,
Ayyedura-jo, Walsh). 0 false positives on Ch.1 and Ch.2.

**What was NOT done (deliberate scope limits):**
- The full Elixir test suite (`ruff check` + `make eval-check`) was not
  run in the sandbox — recommended as the next session's first step
  before the next rig run.
- The Jones/Waelder "God complex" multi-author conflation in the
  thorough summary (carried from V0.4.1) — extending
  `attribution.py`'s veto to multi-author-to-single-concept requires a
  dedicated audit; recommended for a follow-up.
- The page-number citation regression in Key Distinctions and
  Theoretical Tensions (V0.4.1 had 5 citations, V0.4.2 had 0) — this is
  a prompt-level issue, not a code-level issue; recommended investigating
  whether a prompt change between V0.4.1 and V0.4.2 removed the page-
  citation instruction.

---

## V0.4.2 — stray-quote repair v2 (even-count mismatches) + vision-region cropper prototype

> **The release:** Two system-strengthening deliverables from the V0.4.1 NPD
> audit follow-up. Both are **content-agnostic** (no hardcoded author
> names, book titles, or chapter-specific patterns) — they strengthen
> reliability across ANY book/chapter, not just the NPD chapter that
> triggered the audit.
>
> **Validation:** smoke-tested imports + a functional check on the
> stray-quote v2 detector. The vision cropper was validated on a synthetic
> 3-page PDF (vector bar chart + embedded raster image; all 4 expectations
> PASS). The full Elixir test suite (`ruff check` + `make eval-check`)
> should be run by the owner before the next rig run.

**Fix 1 — `repair_stray_quotes_v2` (`core/summarisation/postchecks/garble.py`):**
extends the V0.20.5 stray-quote repair to handle **even-count mismatches**
— a bug class that v0.20.5 entirely misses. The V0.20.5 detector only
fires on ODD ASCII `"` counts per line, and counts ALL `"` including
HTML attribute quotes (e.g., `style="font-size:0.9em"`). The V0.4.1 NPD
Thorough Summary line shipped with 44 ASCII `"` (even count) but contained
4 real mismatches — the LLM dropped both an opener AND a closer in each
case, keeping the count even, so v0.20.5 never fired.

Three content-agnostic detectors (D1/D2/D3):
- **D1 — HTML-aware odd-count repair:** strips HTML tags before counting;
  if the text-content quote count is odd, remove the last text-content
  `"`. Strict improvement over v0.20.5 (never breaks HTML attribute
  quotes).
- **D2 — State-machine stray detection on even-count lines:** walks
  text-content `"` chars with an open/closed state machine; auto-repairs
  1-sided orphans (stray closer → delete; final open → insert closer;
  opener-after-opener → insert closer before it).
- **D3 — Long-span pair FLAG:** if the state machine pairs an opener
  with a closer >250 chars apart, **flag** as suspicious (likely a
  "both dropped" case). Flag-only — no auto-repair (the state machine
  can't tell WHERE to insert the missing pair without semantic
  understanding; auto-repair would risk new errors).

Validated on 3 uploaded chapter summaries (all flags confirmed by
manual audit, 0 false positives):
- Ch.3 (v0.4.1 NPD): 4 D3 flags (matches the original audit's "broken
  cases" exactly).
- Ch.2 (v0.3 Identity Diffusion): 3 D3 flags (all confirmed).
- Ch.1 (v0.18 Identity & Its Origins): 1 D3 flag (confirmed).

Wired into the orchestrator at all 3 call sites (bullets/exec/thorough),
runs AFTER v0.20.5 and merges the issue lists. Purely additive — no
changes to v0.20.5 behavior.

**Fix 2 — `vision_region_cropper.py` (`core/pdf/vision_region_cropper.py`):**
prototype that fills the three gaps in the existing figure/table
extraction stack. Content-agnostic and composable.

- **Layer 0 — reuses** `figure_table_cropper.extract_figures_and_tables()`
  (PyMuPDF images + pdfplumber tables). No changes to existing behavior.
- **Layer A — NEW: vector-graphics clustering.** Clusters pdfplumber
  rects/lines/curves by spatial proximity (greedy agglomerative,
  distance threshold 50pt, min 5 shapes per cluster). Catches
  **vector-drawn diagrams** (charts drawn with PDF commands, no
  embedded raster) that PyMuPDF misses entirely. No hardcoded shapes.
- **Layer B — NEW (opt-in): VLM-driven region detection.** Renders
  page at low DPI, asks VLM for JSON bounding boxes of non-text
  regions, maps percentages back to PDF points, crops at high DPI.
  Provider-agnostic via `vlm_callable` parameter (reuses V0.4.1's
  vision-probe pattern in integration).
- **Layer C — NEW: inline markdown embedding.** Injects
  `![Figure N: caption](path)` at the right `<!-- original page N -->`
  markers in the chapter markdown.

Plus de-duplication (drops regions overlapping a higher-confidence
region by >50% of the smaller's area) and caption extraction (regex
for "Figure N" / "Table N" patterns near the region).

Validated on a synthetic 3-page PDF (reportlab): page 1 pure text,
page 2 vector bar chart (10 rects + 5 lines), page 3 embedded raster.
All 4 expectations PASS. Cropped files are real images (833×250px PNG
for the vector chart, 400×200px JPEG for the embedded raster).

**Doc — `docs/FEASIBILITY_vision_crop.md`:** full feasibility report
for the user's vision-cropping question. Covers what the existing
stack does, the three gaps, the three-layer architecture, validation
results, trade-offs of three integration approaches (PDF-metadata-only
/ VLM-driven / hybrid), and a recommended short/medium/long-term
integration path.

**What was NOT done (deliberate scope limits):**
- The full Elixir test suite (`ruff check` + `make eval-check`) was
  not run in the sandbox — recommended as the next session's first
  step before the next rig run.
- `vision_region_cropper.py` is a standalone prototype, not wired
  into `controller.py`'s conversion pipeline — recommended for a
  follow-up commit (gated by a settings flag, default off).
- The Jones/Waelder "God complex" multi-author conflation from the
  audit — the existing veto system handles single-author
  misattribution but not multi-author-to-single-concept. Extending
  `attribution.py`'s veto requires a dedicated audit; recommended
  for a follow-up.

---

## Key design decisions

1. **Explicit parameters, NOT context objects** — the V18.6.3 crash was caused by extracting `_build_prompt` via a `PromptContext` object. All V18.11+ extractions use explicit named parameters. 8 consecutive golden-master runs at 9/10 validate this pattern.
2. **More bullets > lower coverage** — no min/max on bullet count. The LLM consolidation (merges 95%+ identical) is the only consolidation. If skipped (deadline), all bullets pass through.
3. **Bullets are an independent unit** — checked separately from thorough. A user who only reads bullets must get 100% coverage. The gap-fill loop bypasses the deadline to guarantee this.
4. **Ollama embedder** — nomic-embed-text via Ollama's `/api/embeddings` endpoint. No sentence_transformers needed. No HuggingFace downloads. Works with the existing Ollama setup.
5. **Layout reorder sampling** — sample 1-2 pages before the full per-page loop. Skip if single-column. Saves ~24s for 95% of books.
