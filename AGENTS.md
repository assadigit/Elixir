# AGENTS.md — Standing Rules for AI Agents Working on Elixir

> **Purpose:** this file is the permanent, version-controlled record of the
> rules every AI agent (orchestrator, subagent, or future session) MUST
> follow when working on the Elixir codebase. Read this before starting any
> task; comply with it at every commit.

---

## Rule 1 — Never engineer or optimize for a specific book or chapter

> **Never engineer and optimize the system for a specific book or chapter,
> because that could be cheating and benchmaxing.** For example, do not
> create and hold a word/name list which helps the model and system do better
> for that specific chapter or book — that's called cheating. Just learn from
> the process and mistakes, and make the overall system more reliable and
> rigorous.

### What this means in practice

Every code or prompt change must be **content-agnostic** — it must work the
same way on ANY book, not just the one being audited. The audit findings are
book-specific (they're real defects found in a real book's output), but the
**fixes** must be generic: they must improve the system's reliability for all
books, not hardcode a solution for the test book.

### The enforcement layer

The standing test `tests/test_v182039_audit_fixes.py::TestResidualsDenyList`
enforces this rule mechanically:
- `test_runtime_contains_no_chapter_names` — scans every file in `core/`,
  `utils/`, `ui_qt/`, `controller.py`, `main.py`, `config/`, `prompts/`,
  `installer/`, `assets/` for book-derived proper nouns (43 names extracted
  from the test chapter). Any match fails the test.
- `test_runtime_contains_no_chapter_concept_phrases` — scans the same files
  for book-derived concept phrases (e.g., "false self", "identity diffusion",
  "ego identity", "Broken Structures"). Any match fails the test.

**Every commit must pass these tests.** If a code comment needs to cite the
audit evidence (e.g., "the V0.20.2 ch.2 audit found…"), use generic
placeholders (e.g., "[a name]", "a cited author's surname") instead of the
book-derived name. The audit FILES (in `audit/results/`) and the ground-truth
files (in `docs/ground_truth/`) are deliberately NOT scanned — they're the
evidence, not the runtime code.

### Compliance checklist (run before every commit)

1. **No hardcoded author/theorist/person names** in runtime code. Author
   lists must come from the RUNTIME deterministic analysis
   (`extract_citations` on the source text), not a hardcoded list. Example:
   `detect_and_repair_author_garbles(source_authors)` takes the author list
   as a parameter — it doesn't hardcode any names.

2. **No hardcoded concept phrases** in runtime code. Detectors must use
   generic patterns (regex, structural heuristics, edit-distance), not
   book-specific vocabulary. Example: the CoT markers ("Let me identify",
   "Hmm, could", "The user wants me to") are generic English reasoning
   phrases that would catch CoT on any book.

3. **No chapter-specific thresholds or branches.** Thresholds must be
   content-agnostic (token counts, edit distances, model properties). Example:
   the V0.20.2 chunking gate uses `is_low_bit_quant(model) AND input > 6000`
   — a model property + a size threshold, not a chapter-content check.

4. **Prompt instructions must be genre-agnostic.** Examples in prompt
   instructions may illustrate generic section types (e.g., "origin,
   perspectives, features, differential diagnosis, conclusion") but must
   not name specific books, chapters, or authors. The `e.g.` prefix makes
   examples illustrative, not mandatory.

5. **Audit evidence is book-specific; fixes are content-agnostic.** The
   campaign protocol says "evidence first; the fix is the smallest change
   the evidence supports." The EVIDENCE is a real audit finding on a real
   book. The FIX is a generic improvement that would help any book. This
   is the design of the campaign: learn from the mistakes on this book,
   make the overall system more reliable.

### Examples of compliance

| Fix | Evidence (book-specific) | Fix (content-agnostic) | Compliant? |
|---|---|---|---|
| D1 name-garble repair | V0.20.4 ch.2 had "Akhar"→"Akhtar" | `detect_and_repair_author_garbles(source_authors)` — cross-checks against the RUNTIME analysis author list, no hardcoded names | ✓ |
| D2 stray-quote repair | V0.20.4 ch.2 thorough had ~10 stray quotes | `repair_stray_quotes(text)` — counts double-quotes per line, removes the orphan on odd-count lines | ✓ |
| D3 paragraph breaks | V0.20.4 ch.2 thorough was a single ~1400-word paragraph | Prompt instruction: "Break the thorough into MULTIPLE paragraphs at section transitions" with generic `e.g.` examples | ✓ |
| CoT markers (V0.20.3) | V0.20.2 ch.2 thorough-floor gap-fill CoT leak | 12 new generic English reasoning-phrase markers ("Let me identify", "Hmm, could", etc.) | ✓ |
| Chunking gate (V0.20.2) | V0.18 ch.1 primary call truncated at 8192 output cap | `is_low_bit_quant(model) AND input > 6000` — model property + size threshold | ✓ |
| Coverage-aware cap (V0.20.1) | V0.18 ch.1 V0.06 cap trimmed sole-cover gap-fill bullets | `coverage_aware_cap(bullets, analysis)` — uses the runtime analysis, no hardcoded names | ✓ |

### What would NOT comply

- Hardcoding a list of "theorists to always cover" (e.g., a list of 37
  psychoanalyst names baked into the code). This would help the system do
  better on THIS book but not on a physics textbook or a novel.
- A detector that specifically looks for "identity diffusion" or "ego
  identity" (book-derived concept phrases). This would catch defects on
  THIS book but not on a chapter about quantum mechanics.
- A prompt instruction that says "always mention Erikson, Kernberg, and
  Mahler" (book-derived author names). This would inflate coverage on THIS
  book but not on a chapter that cites different authors.
- A threshold calibrated to THIS chapter's token count (e.g., "chunk at
  8566 tokens"). This would fire on THIS chapter but not on chapters of
  different sizes.

---

## Rule 2 — Evidence-first; the fix is the smallest change the evidence supports

> Every code or prompt change must cite the audit finding or conversion-log
> line that motivates it. No speculative changes. One audit-finding family
> → one conventional commit.

(Already enforced by the V0.20 campaign charter, `docs/ROADMAP_V0.20.md`.)

## Rule 3 — The net stays green at every commit

> Full suite passing (5,596+ local), `ruff check` + `format` clean, `make
> eval-check` → OK. Golden fixtures only change with an audited quality fix
> (re-freeze + eval re-baseline in the same commit).

(Already enforced by the V0.20 campaign charter.)

## Rule 4 — Provenance before audit

> Parse the stamp (`core.system.provenance.parse_provenance`) before auditing.
> A file without the stamp is a pre-.3.7 artifact and not evidence. The
> conversion log's line 5 (V0.20.4+) carries the same stamp — check it too.

(Already enforced by `docs/EVALUATION_FRAMEWORK.md`.)

## Rule 5 — Every revision gets a .zip in the download folder

> After every release (VERSION bump + tag + push), create a .zip of the tag
> in `/home/z/my-project/download/` for local storage (CI/CD is limited).
> The user stores these locally.

---

## Rule 6 — Every version gets a GitHub Release (V0.6.5)

> **The user directive:** "For every version you create, add a release
> version, like this one, with added changelogs and updates."

Every release (VERSION bump + tag + push) MUST also publish a GitHub
Release whose body is the version's release notes. The procedure:

1. **Notes file first:** `release_notes/VX.Y.Z.md` — one file per
   version, committed with the release. Style: the title line carries
   the version + a `headline · items` summary; body sections per fix
   with the user report that motivated it, the root cause, the fix
   approach, the numbers (tests, fail-on-pre-fix count, suite state),
   and a "Test path" section. Written for a human reading the release
   page, not a changelog dump.
2. **CHANGELOG entry** (the detailed engineering record) — the two
   documents have different audiences and both stay.
3. **Publish:** `python tools/publish_release.py VX.Y.Z --zip
   /home/z/my-project/download/Elixir-VX.Y.Z.zip --token <one-off
   token>` — or `--all` to backfill. The token is one-off in the
   command line only (never committed, never logged — the standing
   security procedure). `--dry-run` for a rehearsal.
4. **Latest badge:** only the newest version's release is marked
   Latest (`make_latest=true` in the API call).

Skipping the release breaks the user's contract for the version —
treat it as part of the release gate, not a follow-up.

---

## Rule 7 — Commit and push incrementally; never batch to session end (V0.6.69)

> **The user directive:** "From now on you must commit and push
> incrementally so nothing gets lost mid-session."

Work is durable only once it is on `origin/main`. A session can end
abruptly at any moment — context exhaustion, sandbox loss, crash — and
anything left in the working tree or in local-only commits is work the
user can lose. (Added after a milestone session ran out of context
mid-stream with nothing pushed: the repo sat at the M1 close while the
session's in-chat state was lost.)

### What this means in practice

1. **One unit of work → one commit → one push, immediately.** Follow
   Rule 2's cadence (one finding family → one conventional commit), and
   run `git push origin main` right after each commit — before starting
   the next unit. Never accumulate local commits; never defer pushes to
   a "session close" batch.

2. **Commits and pushes only — this does not unlock publishing.** Tags,
   GitHub Releases, and zips stay gated by Rules 5 and 6 (a release is
   VERSION bump + tag + push + Release + zip, on the user's explicit
   authorization). Mid-milestone pushes of `main` are now REQUIRED;
   mid-milestone publishing is not.

3. **This rule supersedes session prompts.** Any "no push this session"
   line in a rolling/session prompt is overridden by this rule — write
   the next session prompt to match.

4. **Push failures are reported, never silent.** If a push fails
   (auth, network), say so at once, retry, and do not keep building on
   top of unpushed commits without telling the user.

5. **A green WIP commit beats a lost session.** If a unit of work
   cannot be finished before a session might end, commit the partial
   state with a `wip:` prefix and push it — Rule 3's green gate still
   applies.

---

## Rule 8 — Never hardcode a specific TTS engine/model in logic (V0.7.8)

> **The user directive (post-V0.7.7 session):** "Never hardcode a
> specific tts model, so incidents like vibevoice — which is now
> deprecated — don't happen again."

TTS engines and models are external, fast-moving dependencies. This
codebase has already lived through the full cycle: Piper was removed by
user decision (V0.6.64), VibeVoice was broken on source installs for 10
releases while the failure hid as "rig variance" (V0.6.64 → V0.7.6), and
NeuTTS, Qwen3-TTS, Coqui XTTS v2, Kokoro, and Sherpa have all rotated
through as the recommended pick. Any place that bakes a specific
engine's name into LOGIC keeps working only until that engine changes
or dies.

### What this means in practice

1. **Logic reads the setting; it never assumes the engine.** Any code
   that needs to know "which TTS engine will run" must read the same
   setting the generator reads — `tts.en_engine`, single-sourced in the
   defaults registry (`utils/settings.py`). The pre-V0.7.8 wizard VRAM
   check hardcoded `tts_engine="neutts"`, so a Kokoro user's Phase-4
   estimate billed 1.5 GB instead of 0.5 GB — fixed in V0.7.8 with the
   B7 pattern (read the real setting, like the real translator fix).
2. **Model paths and names come from Settings, single-sourced.** Every
   engine takes its model path from a `tts.*` setting and fails with a
   clear "path not set" error when it is empty. Defaults live ONCE in
   the registry; call sites read the setting and never re-declare the
   literal (the V0.6.8 audit B18 single-sourcing rule, same shape).
3. **UI catalogs are the designed choice surface, not violations.** The
   Settings TTS page's engine dropdown and the quick-services default
   combo deliberately list engine names — adding or removing an entry
   there is a product decision made in the open.
4. **Engine-internal knowledge stays inside the engine.** Voice-preset
   lists (Kokoro's `af_heart`, VibeVoice's 25 presets) live in
   `core/tts/` next to the engine that owns them; the rest of the app
   never re-declares them.
5. **Deprecation must degrade, not break.** When an upstream engine
   dies, the app's answer is the honest error path (a clear message +
   the other engines still working) — and the rig tests keep pinning
   the REAL configured-engine behaviour, never a hardcoded stand-in.

### Enforcement

`tests/test_v0740_step6_translation.py::TestVramCheckPassesConfiguredTtsEngine`
pins the pattern: the hardcoded `tts_engine="neutts"` form is gone from
the wizard, the check reads `tts.en_engine`, the configured value flows
into the VRAM budget, and the missing-setting fallback matches the
router's own semantics. New TTS-touching code must follow the same
shape.
