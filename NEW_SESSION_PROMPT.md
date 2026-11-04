# New Session Prompt — Elixir Wizard Rework, Phase 1 (the Implementation-Planning Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
converts and summarizes books, at `https://github.com/assadigit/elixir`,
branch **`main`**, version **V0.6.85**. Purely Python — any Next.js
sandbox at `/home/z/my-project` is disposable tooling, NOT part of the
project. **Read `AGENTS.md` first** — its 7 rules are non-negotiable
(Rule 1 content-agnostic, Rule 2 evidence-first, Rule 3 net-green,
Rule 4 provenance, Rule 5 zip-per-release, Rule 6 GitHub-Release-per-
version, Rule 7 commit-and-push-incrementally).

**The campaign:** we are re-designing and reworking the **full wizard**
(the 10-step "Process Wizard" window). The working method, which I set
and expect you to follow:

- **Phase 0 (DONE, previous session):** the audit. Read
  **`ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md`** at the repo root — it is
  the complete, citation-backed record of what the wizard is today and
  what its backend actually does, plus a live-bug register (B1-B10), a
  dead-code register, and a defaults-disagreement table.
- **Phase 1 (THIS SESSION):** the implementation plan. You turn my 12
  change requests + the audit's findings into a concrete, phased
  implementation spec I can approve.
- Later phases execute the plan step by step, one phase per session,
  each ending with a fresh session prompt. Everything documented,
  committed and pushed incrementally.

## WHAT PHASE 0 SHIPPED (the record)

- Commit `e25eac6` — the document-type PNG icons: the six hand-drawn
  mode artworks extracted from `Elixir-Document-Type-Modes.zip` into
  `assets/icons/{preset_key}.png`, placeholders deleted, README
  updated, verified with `scripts/wz_icons_check.py` (real offscreen
  render; 6/6 load; VLM-verified grab).
- Commit `95a1e18` — the Phase-0 audit document itself.

## THIS SESSION'S MISSION — PHASE 1: THE IMPLEMENTATION PLAN

Produce **`ELIXIR_WIZARD_REWORK_ROUND_2_PLAN.md`** at the repo root:
a complete implementation plan for my 12 wizard changes (W1-W12 in the
audit doc), grounded in the audit's findings. W1 (icons) is already
shipped — the plan covers W2-W12.

My 12 requests, in my original words (the audit's §W2-W12 has the
backend truth for each):

- **W2** — concentrate document types into 3: fully-digital (OCR only
  auto-activates for charts/imagery/tables), scanned (VL + OCR engines
  100% essential), auto (system detects). LESS COGNITIVE LOAD is the
  theme of this whole rework.
- **W3** — remove the configuration-profile option from step one.
- **W4** — make the page-range item bigger and more visible; make
  "detect chapters from TOC" larger and more visible; explain the
  optimal page group size; keep it auto with a toggle.
- **W5** — OCR settings: a primary auto-detect option (one reassuring
  button; novices never touch checkboxes).
- **W6** — essential outputs (exec + thorough) pre-checked and NOT
  cancellable; remove emojis (like the compact-summaries item).
- **W7** — output studio: categorize outputs (Audio, Learning, etc.).
- **W8** — move "simplified keypoints" to the output studio; investigate
  "streaming llm output" (audit verdict: dead code, remove); move
  compact summaries to the output studio.
- **W9** — models step: an auto-detect button that finds models and
  their engine config from the backend local LLM intelligently;
  default config + advanced manual option.
- **W10** — translation: make skip-ability visible; verify harakat and
  judge models are technical (audit: both REAL — but the combos are
  broken by the `list_ollama_models` bug, fix first); two selection
  modes: translate my desired outputs (from step 4) OR manually select.
- **W11** — advanced panel: token limit per segment = Auto + advanced
  manual with explanation; clearly explain strategies (auto/heading/
  semantic/token); decide the semantic toggle's necessity (audit: only
  gates AUTO's stage-4 fallback — fold into advanced); remove
  "academic rigor" (audit: auto-enable stays, checkbox goes);
  investigate conservative drop mode (audit: works, niche — your call
  with reasons); token-budget slider display-off by default.
- **W12** — fine-tune: an auto-mode button (system sets it); make sure
  self-consistency REALLY works (audit: Ollama-only + union-merge +
  3-4× cost — plan must make it honest or fix it); make sure coverage
  threshold works (audit: soft floor — plan must decide); resolve the
  summarization-limits confusion (audit: redundant with step 5 and
  overridden by backend clamps — collapse to one owner).

### What the plan must contain

1. **A phasing** — ordered implementation phases (I execute one phase
   per session), each phase independently shippable, commit-by-commit,
   with the bug-register fixes (B1-B10) sequenced INTO the right phases
   (B1 translation-wipe and B2 force-OCR are user-facing data bugs —
   early).
2. **Per-item design** — for each of W2-W12: the new UI (controls,
   copy, layout — in plain words + ASCII sketches), the exact state/
   settings/request fields touched, the backend changes (or "none
   needed"), and which audit findings it relies on.
3. **The open decisions** — the audit's §6 questions answered with a
   recommendation each (scanned-mode VL promise scope; profiles retire
   vs relocate; page-group-size remove vs wire; deprecated outputs
   cull; self-consistency honest gating; coverage semantics;
   limits single-owner; step architecture). Mark each "NEEDS MY
   APPROVAL" or "SAFE TO DECIDE" — I approve the marked ones.
4. **Test + verification plan** — per phase, following the repo's
   existing patterns (AST-pin tests, offscreen render harnesses like
   `scripts/wz_icons_check.py`, functional sweeps).
5. **Risk register** — what each phase can break (the audit's findings
   are the map: dead flags, save-order overwrites, defaults
   disagreements).

### Rules for this session

- **Do not implement W2-W12 yet.** This session PLANS. (Small,
  obviously-safe repairs from the bug register may be hotfixed if they
  are one-liners and you verify them — but prefer planning first.)
- Commit and push incrementally (Rule 7). The plan document itself goes
  in as its own commit.
- At the end, write the next `NEW_SESSION_PROMPT.md` (Phase 2 =
  execution of the first implementation phase).
- Be fully autonomous. Ask me only what is critical — the audit's §6
  "NEEDS MY APPROVAL" list is exactly the right short list.

## THE LOOP (session mechanics)

1. **Recover:** `cd /home/z/elixir-repo` (clone with the token from the
   session context if absent). `git log --oneline -5` — expect
   `95a1e18` (the audit) on top, `e25eac6` (icons) below it.
2. **Baseline:** the repo venv (`.venv/`) has the full requirements +
   PySide6 installed. For offscreen Qt work, export
   `LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
   (libEGL etc. extracted from debs — re-extract with
   `apt-get download libegl1 libglvnd0 libglx0` + `dpkg-deb -x` into
   /tmp/qt-libs if the sandbox reset). Reference harness:
   `scripts/wz_icons_check.py`.
3. **Orient:** read `AGENTS.md`, this prompt,
   `ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md` (the whole thing), and skim
   the wizard step modules it cites when a plan decision needs the
   code in front of you.
4. **Plan, write the plan doc, commit, push, verify, write the next
   session prompt.**

## GITHUB Token (one-off, never commit it)

Use the token from the session context for git push. If it is expired,
ask me for a fresh one.
