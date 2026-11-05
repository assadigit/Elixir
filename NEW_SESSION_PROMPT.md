# New Session Prompt — Elixir Wizard Rework, Phase 2 (the V0.6.86 Hotfix Session)

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

**The campaign:** re-designing and reworking the **full wizard** (the
10-step "Process Wizard" window). The method I set and expect:

- **Phase 0 (DONE):** the audit —
  **`ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md`** at the repo root. The
  complete citation-backed record of the wizard today: the live-bug
  register (B1-B10), the dead-code register, the defaults table.
- **Phase 1 (DONE):** the implementation plan —
  **`ELIXIR_WIZARD_REWORK_ROUND_2_PLAN.md`** at the repo root. It
  carries my 21 locked decisions + the 2 visual asks (stage chips,
  wizard restyle) and the 7-phase sequence. **Read it in full before
  writing any code** — it is the contract for this whole campaign.
- **Phase 2 (THIS SESSION):** execute **Phase ① of the plan — the
  V0.6.86 hotfix** (plan §2, "Phase ①"). Later sessions execute one
  phase each (② Step 1 + shell at V0.7.0, ③ Steps 2-3, ④ Step 4,
  ⑤ Step 5, ⑥ Step 6, ⑦ Steps 7-7b — one per session).

## THIS SESSION'S MISSION — PHASE ①: THE V0.6.86 HOTFIX

Ship **V0.6.86** fixing exactly the two live data-loss bugs (audit §3,
plan §2-Phase①). Nothing else. Do not start Phase ② work.

1. **B1 — the missing `controller.list_ollama_models()`.**
   `step6_translation.py:85` and `translation_page.py:151` call
   `self.controller.list_ollama_models()` which does not exist; both
   catch the error and show empty model combos; the wizard's save then
   wipes `translation.harakat_model` to `""`
   (`wizard_view.py:949-959`). Fix:
   - Add `Controller.list_ollama_models() -> list[str]` delegating to
     `utils/network.list_ollama_models` (`utils/network.py:173`), with
     the base URL from settings and a 5s timeout. No new HTTP code.
   - Defensive guard in `_save_translation_settings`: never overwrite a
     non-empty `translation.harakat_model` / `translation.judge_model`
     setting with an empty string; log a line when the guard fires.

2. **B5 — the wizard silently disables translation every run.**
   `translation_enabled` defaults `False` (`shared.py:85`) and
   `_save_translation_settings` writes it unconditionally
   (`wizard_view.py:953`), killing translation for users who enabled it
   in Settings. Fix: load-then-save round-trip —
   `_load_settings_into_state` also reads `translation.enabled` (and
   the sibling translation fields) from settings at wizard open, so
   saving writes back what the user chose unless the step changed it.

### Test + release requirements (the phase gate)

- New pin tests: the controller method exists and returns a list
  (mocked); the empty-string guard preserves a non-empty harakat
  setting; wizard open→close with `translation.enabled=true` in
  settings keeps it true (characterization).
- Offscreen render: Step 6 combos populated from a stubbed controller.
- Full suite green + `ruff` clean (Rule 3). Every commit pushed
  immediately (Rule 7). One finding family → one conventional commit
  (Rule 2).
- **Release V0.6.86:** VERSION bump + tag + push + GitHub Release
  (body = `release_notes/V0.6.86.md`, written for a human: the user
  report, root cause, fix, numbers) + zip at
  `/home/z/my-project/download/Elixir-V0.6.86.zip` (Rules 5-6; my
  Phase-1 phasing approval authorizes this release). Use
  `python tools/publish_release.py V0.6.86 --zip ... --token <one-off>`
  — token from the session context, never committed or logged.
- At the end, write the next `NEW_SESSION_PROMPT.md` (Phase 3 =
  execution of plan Phase ②: the wizard shell + stage chips + the
  3-mode Step 1 + `ocr_mode` backend, V0.7.0) and commit+push it.

## THE LOOP (session mechanics)

1. **Recover:** `cd /home/z/elixir-repo` (clone with the session token
   if absent). `git log --oneline -5` — expect `3c7ae92` (the Round-2
   plan) on top, `65191d1` (the Phase-1 handoff) below it.
2. **Baseline:** the repo venv (`.venv/`) has the full requirements +
   PySide6. For offscreen Qt, export
   `LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
   (re-extract with `apt-get download libegl1 libglvnd0 libglx0` +
   `dpkg-deb -x` into /tmp/qt-libs if the sandbox reset). Reference
   harness: `scripts/wz_icons_check.py`.
3. **Orient:** read `AGENTS.md`, this prompt, the Round-2 plan (all of
   §0-§2), and the audit's §3 bug register. Skim the five files the
   hotfix touches before editing.
4. **Implement → test → commit/push per unit → release V0.6.86 →
   write the Phase-3 prompt → commit/push it → report.**

## GITHUB Token (one-off, never commit it)

Use the token from the session context for git push. If it is expired,
ask me for a fresh one.
