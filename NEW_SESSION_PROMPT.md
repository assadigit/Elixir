# New Session Prompt — Elixir V0.6.3+ (the post-campaign hardening session)

## Context

You are continuing work on **Elixir** — a PySide6 desktop app + local LLM (llama.cpp) that summarizes books. The project is at `https://github.com/assadigit/elixir` on branch `refactor/audit-session` (tag `V0.6.3`).

**STANDING RULE**: the elixir project is PURELY PYTHON (PySide6 desktop app + local LLM). Any Next.js sandbox at `/home/z/my-project` is disposable tooling only — NOT part of the elixir project. Never describe elixir with web-framework framing.

## AGENTS.md rules (NON-NEGOTIABLE)

1. **Rule 1 (content-agnostic)**: NO hardcoded book/author/chapter/domain strings. The system must find authors itself via the runtime `extract_citations` (the deterministic regex) + the runtime glossary (the LLM-extracted source roster). Never hardcode or cheat by adding missing author names to the LLM or prompt.
2. **Rule 2 (evidence-first)**: every claim cites file:line.
3. **Rule 3 (net-green)**: ruff clean + eval gate OK + pytest suite passing.
4. **Rule 4 (provenance)**: changes traceable in CHANGELOG + commits.
5. **Rule 5 (zip-per-release)**: zip per release in `/home/z/my-project/download/`.

## Where the campaigns stand (V0.5.15 → V0.5.20 CLOSED · V0.6.0 tools CLOSED · V0.6.1 backlog CLOSED · V0.6.2 user-bugfixes CLOSED · V0.6.3 modal-fit CLOSED)

The V0.5.x repeatability campaign PROVED the source-glossary
summarization architecture (LLM glossary → gap-fill → final-check →
deterministic verification LAYER) and then closed its known defect
families. The benchmark record, all filed on `main`:

- **4 configurations, one band:** ch.6 rig 94.6% → ch.1 sandbox 100%
  (repeated exactly, ±0pp) → ch.9 rig 95.65% → ch.9 rig full-book
  94.5% individual-level — 0 fabricated claims on every run.
- **The ceiling lift:** the V0.5.18 same-chapter re-run hit 73/73 = 100%
  floor AND full-text with an honest verification flag (3/0, was 8/6).
- **V0.5.19 + V0.5.19.1** shipped the six-item backlog (append-mode
  corrections, normalized anchors, structural-name glossary filter,
  prose-year check, criteria continuation rules, the wrapped-marker join).
- **The full-book rig run #2** (run `20260928-155851-011587f0`, the whole
  397-page PDF with ch.9 TOC-selected) fired the V0.5.18 semantic-dedup
  veto LIVE for the first time (Kallman + Widiger rescued) and exposed
  four extraction-layout defects → **V0.5.20 shipped all four** (the
  marker-sequence continuation join, the terminal-shape lint, the
  keypoints-layer author-coverage veto, the glossary handoff path, the
  thin colon-less flag) — 37 new tests, zero new suite failures,
  real-source verified (the six-grounds 6/6, the criteria 8/8 across
  page furniture, item (iv) complete for the first time in any run).

Full detail: `CHANGELOG.md` (the V0.5.18 / V0.5.19 / V0.5.19.1 / V0.5.20
entries) + the audit mds on `main` (`audit/results/AUDIT_V0.5.1*_*.md` +
the `bench_v05*` folders). Do NOT re-litigate the campaigns — the V0.5.21
backlog is SHIPPED (V0.6.1) and the tools campaign is CLOSED (V0.6.0).

## THE NEXT SESSION AGENDA (primary): the rig LIVE verification + whatever the next audit surfaces

**V0.6.2 status:** the two USER-REPORTED bugs from a real ~2h40m book
run shipped — (1) the Step-9 elapsed timer went NEGATIVE when a
conversion crossed midnight (`QTime.secsTo` is time-of-day arithmetic;
fixed on `time.monotonic()`); (2) a thin-chapter book (1-2 page
chapters) shipped exec + bullets + thorough ABOVE the source word
count with rephrased near-duplicate gap-fill bullets (four stacked
length-policy defects: the thorough/exec floors broke their 45%/20%
fraction caps for W < 267/300; `bullet_cap` = 0 unbounded the ADDITIVE
machinery; "at least N — NO MAXIMUM" on thin chapters; no combined
budget + Tier-2 insertions bypassed the near-dup check). 34 tests, 19
defect-driven; golden nonfiction/academic re-frozen + eval re-baselined
(academic ROUGE-L IMPROVED). See the V0.6.2 CHANGELOG entry.

**V0.6.3 status:** the USER-REPORTED modal button clipping shipped —
"Open file location is truncated" on the Summarization success modal:
QMessageBox can settle 19px BELOW its own sizeHint when the message
text is short (355 rendered vs 374 needed; "📂 Open File Location"
132/142px, "🔄 Try Another" 95/104px), so QPushButton clips its label.
THE FIX: per-button `minimumWidth` = `sizeHint().width()` (propagates
up the layout chain; a dialog-level floor was tried and REJECTED —
layout activation overwrites it, pinned by a test) applied globally
via a `QApplication` Show-event filter (`ui_qt/components/modal_button_fit.py`,
installed in `ui_qt.app.run`) + belt-and-braces in
`shared._show_success_modal`. 17 tests (15 defect-driven). Pure
geometry — content-agnostic. See the V0.6.3 CHANGELOG entry.

What remains is inherently OPERATOR territory:

1. **The rig LIVE verification** — re-run the full-book rig benchmark
   (the run shape that exposed the V0.5.20 defects) to confirm: the
   marker-sequence joins fire on the real layout, the see-also bound
   accepts/rejects correctly on the real glossary contexts (expect a
   see-also-only author or two to finish honestly missing rather than
   inflated — the documented precision-over-coverage trade), the pair
   forms appear once, the thin one-liner count drops. NOW ALSO: run one
   THIN-chapter book (1-2 page chapters) and confirm the combined
   sections stay under the source word count + no rephrased duplicate
   bullets (the V0.6.2 contract — expect the 📏 F1 combined line + any
   ⚠️ combined over-generation WARNING in the log).
2. **The V0.6.0 rig checklist** (the CHANGELOG V0.6.0 entry): live
   qwen/OlmOCR via Ollama + Persian `fas.traineddata` + UnlimitedOCR
   torch/transformers + PaddleOCR CPU + provider-vision; real-Ollama
   translation; live qwen/vibevoice GPU + sherpa + Kokoro/Piper;
   faster-whisper; anydoc.
3. **Audit whatever the run surfaces** — the backlog discipline:
   evidence → backlog item → fix → release entry. `audit/results/` is
   the precedent; move rig uploads to `bench_v*` folders + write the
   audit md.

If a sandbox session is asked to continue code work: the standing
method still applies (evidence-first trace → characterization tests
FIRST → content-agnostic fix → net-green → CHANGELOG + zip). The tool
inventory + per-tool method below remain the reference for
RE-verification or for any NEW tool card.

**Historical context — the V0.6.0 campaign charter (completed):**

The V0.5.x campaign verified ONE tool end-to-end (the Full Conversion
pipeline's summarization quality). The app's ToolDashboard ships TWELVE
tool cards + 3 internal tabs; most have NEVER had an end-to-end
verification pass, and the SWOT already knows parts of them are untested
(**W8 coverage deserts:** `core/extract` 0%, `core/ocr/unlimited_ocr` 0%,
`core/models/config_views` 0%, outputs service formatters 8–52%).

### The canonical tool inventory (`ui_qt/views/tool_dashboard.py` `TOOL_CARDS`)

| Card (key) | What it does | UI entry | Service layer |
|---|---|---|---|
| Full Conversion (`full_conversion`) | the 10-step wizard, all outputs | `ui_qt/views/wizard_steps/` | `core/pipeline/` — VERIFIED V0.5.15–20 |
| Summarization (`summarization`) | paste text → summary + keypoints | `dialogs/summarization_service_dialog.py` | `core/summarisation/` (the standalone service path — NOT yet verified) |
| Document → Markdown (`pdf_to_markdown`) | AnyDoc/markitdown: PDF/DOCX/EPUB → MD | `quick_convert_dialog.py` | `core/extract/anydoc_extractor.py` — 0% coverage |
| Translation (`translation`) | EN ↔ FA, auto best-backend | `dialogs/translation_service_dialog.py` | `core/translation/` (service, translator, engine, validator, cache, chunker, glossary, harakat) |
| Markdown Styler (`markdown_styler`) | messy notes → clean Obsidian MD | `dialogs/markdown_styler_dialog.py` | LLM-driven (check the dialog's provider path) |
| Packets of Knowledge (`packets_tool`) | cluster notes → knowledge packets | `dialogs/packets_tool_dialog.py` | `core/outputs/packets/` |
| OCR Service (`ocr_service`) | text from PDFs/images, auto-cascade | `dialogs/ocr_service_dialog.py` | `core/ocr/` (service, base, ocr_prescan, qwen_ocr, unlimited_ocr) — `unlimited_ocr` 0% coverage |
| PDF/DOCX Cutter (`pdf_docx_cutter`) | extract a page range | `dialogs/pdf_docx_cutter_dialog.py` | `core/pdf/` + `core/docx/` |
| Image Extractor (`image_extractor`) | images/charts/tables from books | `dialogs/image_extractor_dialog.py` | `core/extract/image_extractor.py` — 0% coverage |
| TTS Service (`tts_service`) | text → natural speech | `dialogs/tts_service_dialog.py` | `core/tts/` (engine, engine_cache + engines: neutts, qwen, vibevoice, persian_vits, sherpa; voice_manager, normalizer) |
| Podcast Maker (`podcast_maker`) | script → multi-voice podcast audio | `views/podcast_maker_view.py` (modal) + `settings/podcast_page.py` | `core/podcast/` (script_generator, audio_generator) + `core/outputs/podcast_{generator,audio,coverage}.py` |
| Transcribe Service (`transcribe`) | video/audio → transcript + summary | `dialogs/transcribe_service_dialog.py` + `live_transcribe.py` | `core/transcribe/transcribe_service.py` |

Internal tabs: **Output Scanner** (`output_scanner_view.py`), **Batch
Queue** (`queue_view.py`), **Hallucination Audit**
(`dialogs/hallucination_audit_dialog.py`). Routing for every card key
lives in `ui_qt/views/convert_view.py`.

Riding Full Conversion (output flags on `ConversionRequest`, invoked from
`core/pipeline/converter.py`): anki export, citation graph, epub,
evidence map, mind map, obsidian KB, quote bank, study guide, social
media pack, executive briefing, flashcards (`core/outputs/`).

### The per-tool method (the established discipline, adapted)

1. **Inventory + trace** — card key → routing → dialog/view → service
   entry point. Evidence-first: file:line for every claim (Rule 2).
2. **Characterization tests FIRST for anything touched** — the W8 deserts
   are the priority map; a tool cannot be called "verified" without a net
   (Rule 3).
3. **Headless verification in this sandbox:**
   - PySide6 runs offscreen: `QT_QPA_PLATFORM=offscreen` (dialog-split
     test precedent: `tests/test_v182046_p5_dialog_split.py`).
   - The LLM endpoint is the **zai-llamacpp-shim (port 3031** —
     `http://localhost:3031/v1`, model `glm-4-plus`) — it speaks the
     OpenAI-compatible API the app's `LlamaCppProvider` expects; the
     whole pipeline ran on it, so any LLM-driven tool (Summarization
     service, Styler, Packets, podcast script, translation) can too.
4. **GPU/external-model engines** (qwen OCR, qwen/vibevoice/sherpa TTS,
   whisper-class transcribe, torch embedders) verify at the CONTRACT
   level in-sandbox (unit tests, fallback paths, provider-adapter shapes)
   + a **RIG CHECKLIST** item for the operator
   (`docs/RIG_TEST_CHECKLIST.md` is the precedent).
5. **Fix what's broken** — content-agnostic, net-green, one logical
   change per commit; file defects the V0.5.x backlog way (evidence →
   backlog item → fix → release entry). Ship **V0.6.0** when the campaign
   lands (zip per Rule 5).

### Suggested campaign order (cheapest evidence first)

1. **Pure-deterministic tools** (no LLM, no GPU): PDF/DOCX Cutter, Image
   Extractor, Document → Markdown, OCR prescan + tesseract paths.
2. **LLM-driven tools** (shim `:3031`): Summarization service, Markdown
   Styler, Packets of Knowledge, podcast script generator, Translation.
3. **The audio chain**: TTS engines + podcast audio assembly + transcribe
   — contract-level in-sandbox, rig checklist for the live engines.
4. **The Full-Conversion output riders** (`core/outputs/`): a smoke pass
   with each output flag on a small fixture.
5. **The internal tabs** (Output Scanner, Batch Queue, Hallucination Audit).

### Known state going in

- **Suite baseline on this sandbox:** 17 pre-existing environment failures
  (converter/segmentation VRAM + the llamacpp dropdown + 2 v182032
  postchecks + hypothesis flakiness — see CHANGELOG V0.5.20's net-green
  note). Net-green = no NEW failures + ruff clean.
- The venv lives at `/home/z/.venv` (pypdf, rapidfuzz, wordninja,
  pytesseract, tenacity, …) — check what each tool additionally needs
  before concluding "broken" vs "missing dep" (a missing dep in THIS
  sandbox is a rig-checklist note, not necessarily an app bug — but if
  `requirements.txt`/`requirements.lock` don't carry a runtime import,
  THAT is a bug).
- Translation is EN ↔ FA (Persian — `core/translation/harakat.py`);
  TTS ships 5+ engines (check which are bundled vs external binaries).

## Secondary agenda — the V0.5.21 backlog (SHIPPED in V0.6.1 — kept for the record)

1. **Thin roster-gap-fill bullet quality** — ✅ SHIPPED (V0.6.1): both
   roster gap-fill prompts (the main batch + the final-check round 4)
   now demand the author's SPECIFIC contribution + ban the generic
   registry phrases (the V0.5.19 detector's set). The backlog's "or a
   quality gate at the merge" option was deliberately NOT taken (a
   merge-time drop would re-open the coverage-gap problem; the flags
   stay the safety net).
2. **Glossary pair-form dedup** — ✅ SHIPPED (V0.6.1): commuted
   two-surname pair-forms ("A and B" vs "B and A", "and"/"&") deduped
   keep-first at ingestion, in `_parse_name_bullets` (all 3 parse
   tiers + persist + cross-reference + verification downstream).
3. **The Searles see-also bound** — ✅ SHIPPED (V0.6.1): the loosened
   quote-guard's glossary-backed acceptance (the V0.5.6 main-loop
   override + the round-4 final-check) now requires ≥55% content-token
   coverage of the bullet by the glossary context (light-verb-stripped,
   name/year-excluded, prefix/plural-tolerant); a bound-rejected author
   finishes honestly missing (the veto/mention-only escalation applies).
   The V0.5.10 regex fallback is deliberately unbounded (no glossary
   context exists on that path).
4. **Rig LIVE verification of the V0.5.20 fixes** — ☑ REMAINS THE
   OPERATOR'S: the next full-book rig run should confirm the joins fire
   on the real layout AND now the V0.5.21 fixes' live behavior (the
   see-also bound's accept/reject on real glossary contexts; pair forms
   once; fewer thin one-liners). The sandbox live leg was blocked by
   upstream LLM rate-limits (documented in the V0.6.1 CHANGELOG entry)
   — the hermetic + deterministic-pipeline evidence stands.

## Key files (current)

**The tools layer (this session's focus):**
- `ui_qt/views/tool_dashboard.py` — `TOOL_CARDS`, the canonical inventory
- `ui_qt/views/convert_view.py` — the card-key routing
- `ui_qt/views/service_dialogs/dialogs/*.py` — the ten tool dialogs
- `ui_qt/views/podcast_maker_view.py` + `ui_qt/settings/podcast_page.py`
- `core/ocr/` · `core/extract/` · `core/translation/` · `core/tts/` ·
  `core/podcast/` + `core/outputs/podcast_*` · `core/transcribe/` ·
  `core/outputs/packets/` · `core/outputs/service_formatters.py`

**The pipeline (V0.5.x campaign, reference):**
- `scripts/repeatability_run.py` + `scripts/repeatability_audit.py` —
  the headless end-to-end chapter run + the deterministic coverage audit
- `core/summarisation/author_anchor.py` — the shared boundary-safe author
  anchoring (every author-coverage veto + the verification check)
- `core/summarisation/summary_validator.py` — `semantic_dedup_bullets`
  (the V0.5.18 veto); `core/summarisation/keypoints_builder.py` — the
  V0.5.20 keypoints-layer veto
- `core/summarisation/enumeration.py` — the V0.5.20 marker-sequence join;
  `core/common/layout_furniture.py` — the shared furniture shapes
- `core/summarisation/verification_phase.py` — the glossary-grounded
  coverage check; `core/summarisation/gap_fill_batch.py` — the loosened
  quote-guard + final-check round 4
- `core/preprocessing/deterministic_analyzer.py` — `extract_citations`
- `core/summarisation/glossary_parser.py` + `primary_call.py` — the
  glossary extract + persistence (V0.5.20: run-dir + path field)
- `tests/test_v0518_*.py` / `test_v0519_*.py` / `test_v0520_*.py` — the
  campaign's characterization suites

## Token + repo

- GitHub token: `[REDACTED:github_token]` (one-off URL, scrub after use per Rule 4)
- Repo: `https://github.com/assadigit/elixir` (branch `refactor/audit-session`)
- Zips: `/home/z/my-project/download/` — `Elixir-V0.5.16.zip` … `Elixir-V0.5.20.zip`, `Elixir-V0.6.0.zip`, `Elixir-V0.6.1.zip`, `Elixir-V0.6.2.zip`, `Elixir-V0.6.3.zip`

## Sandbox benchmarking note (the reaper)

The z.ai sandbox reaps background processes spawned from tool-call shells
(setsid/nohup/disown strays die within ~a minute of the spawning call
ending). For headless benchmark runs use the **bench-spawner** mini-service
(`mini-services/bench-spawner/`, port 3032, launched with the subshell
pattern `(bun run dev > spawner.log 2>&1 &)` — services launched that way
persist):

```bash
curl -X POST "http://localhost:3032/run?out=<name>&chapter=<path>&label=<label>&model=glm-4-plus"
curl "http://localhost:3032/status?log=/home/z/elixir/runs/<name>_run.log"   # alive + log tail
```

The LLM endpoint is the zai-llamacpp-shim (port 3031) — do NOT restart it
(it persists from its original launch; a fresh stray would be reaped).
Both mini-services auto-start at sandbox boot; health-check before use:
`curl http://localhost:3031/v1/models` / `curl http://localhost:3032/status`.

## Session workflow

1. Clone the repo (if not already): `git clone https://ghp_...@github.com/assadigit/elixir.git elixir` (one-off token URL, then scrub the remote — `git remote set-url origin https://github.com/assadigit/elixir.git`)
2. Checkout `refactor/audit-session` (the V0.5.x lineage)
3. Read this file + CHANGELOG.md (the V0.5.x entries at the top)
4. Work the primary agenda (the tools campaign) per the method above; the
   repeatability scripts remain available for any pipeline re-verification:
   `python scripts/repeatability_run.py --chapter <path> --out runs/<name> --llamacpp-url <endpoint> --llamacpp-model <model>`
5. Audit any rig upload (move files to `audit/results/bench_v0XXX/` + create the audit md on `main`)
6. Keep net-green at every commit; commit + push (one-off token URL) + zip per release (Rule 5)
7. **Append the session's work to `/home/z/my-project/worklog.md`** (the shared agent worklog — read it first, append a `--- Task ID:` section when done)
