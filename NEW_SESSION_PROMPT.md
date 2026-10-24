# New Session Prompt — Elixir V0.6.63+ (the Post-Installer Session)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must use
a technical term, explain it in one short sentence. Put the result or the
decision I need first, details after. Never say something works unless you
ran it in this session and can show what you ran.

## PROJECT CONTEXT (read this before anything)

**Elixir** — a PySide6 desktop app + local LLM (llama.cpp / Ollama) that
summarizes books, at `https://github.com/assadigit/elixir`, branch
**`main`**, version **V0.6.64** (the Piper-removal release: the Piper TTS
engine is gone entirely — user decision; Tesseract unchanged). Purely
Python — any Next.js sandbox at `/home/z/my-project` is disposable
tooling, NOT part of the project. **Read `AGENTS.md` first** — its 6
rules are non-negotiable (Rule 1 content-agnostic, Rule 2 evidence-first,
Rule 3 net-green, Rule 4 provenance, Rule 5 zip-per-release, Rule 6
GitHub-Release-per-version). Read `CHANGELOG.md`'s V0.6.63 entry and
`worklog.md` (in the sandbox at `/home/z/my-project/worklog.md`) — the
last three task records there are the installer story.

**What V0.6.63 shipped (all verified on real Windows runners):**
`Elixir-Setup-0.6.63.exe` (247.8 MB, sha256 `9ec28447…eb02e5`) at the
release `V0.6.63-windows`. One command — `python build_installer.py` —
packs the app (PyInstaller onedir, windowed), runs a packed self-test
(all **376** app modules + every bundled data file), a launch test, an
Inno Setup compile, then a silent install → installed self-test →
installed launch → silent uninstall loop. Frozen installs keep user data
in `%LOCALAPPDATA%\Elixir` (never the install folder), find bundled
ffmpeg + Poppler automatically, seed the tiktoken encoding offline, and
say friendly in-app messages for what is NOT bundled (models, Ollama,
Tesseract, API keys). Startup: **231 ms** first launch / 244 ms warm
(291 ms from source). Top-5 slowest imports: `core.tts.normalizer`
(97 ms), `docx.parts.document` (40), `onnxruntime` (33),
`pandas.compat` (32), `ui_qt.app` (25).

The path layer is `app_paths.py` (resource_path / user_data_path / the
user-data choke point `utils.settings.user_data_dir()`), the self-test is
`utils/selftest.py` + the `main.py --selftest` hook, the build is
`build_installer.py` + `installer/Elixir.iss` + the workflow
`.github/workflows/windows-installer.yml`.

## THIS SESSION'S MISSION — THE POST-INSTALLER SURFACE

**I will paste the exact instructions in-session. Until then do Step 0
ONLY** (recovery, baseline, orientation — see THE LOOP). The remaining
surface, in priority order (details and evidence in the last worklog
entries — verify before acting, don't trust this list blindly):

1. **GitHub Actions billing (BLOCKS all repo-native builds).** Every
   workflow run on `assadigit/elixir` dies at queue: "recent account
   payments have failed or your spending limit needs to be increased."
   This is an OWNER action (github.com/settings/billing — fix the
   payment method or raise the spending limit). After I say it is fixed:
   verify `.github/workflows/windows-installer.yml` runs green on the
   private repo (it triggers on `V*-windows` tags and `workflow_dispatch`).
   Until then the documented workaround exists: a mirror repo
   `assadigit/elixir-installer-build` (currently PRIVATE, squashed
   snapshot, build history preserved) — public repos build for free, so
   flip it public → run → flip private → attach the exe to the release.
   Never push the token anywhere.
2. **Rotate the GitHub token (SECURITY).** The one-off token was pasted
   in chat multiple times; I should have revoked it after each session.
   Remind me. The next session needs a FRESH token from me (Fine-grained,
   Contents+Actions+Releases RW on this repo only, short expiry).
3. **Mirror repo cleanup (owner action, low priority).** Delete
   `assadigit/elixir-installer-build` in the GitHub UI (Settings →
   Danger Zone) once the billing fix makes it redundant — the token
   lacks the `delete_repo` scope, so the API cannot do it.
4. **Optional bundling polish — RESOLVED 2026-10-23 (V0.6.64).** The
   user decided: **"Remove piper entirely. keep tesseract."** Piper TTS
   (engine, voice catalog, binary check, settings keys, UI, tests,
   piper-tts extra) is GONE as of V0.6.64; Tesseract stays as-is (NOT
   bundled — friendly message when missing). Do not re-raise; the
   removal pins live in tests/test_v0600_tool_tts_e2e.py +
   test_v182044_p3_tts_subprocess.py.
5. **Standing flags (rig tasks, not sandbox-fixable):** the
   `requirements.lock` full clean-install regen (on Windows); the rig
   checklist below.
6. **Lint debt — CLEANED 2026-10-23 (V0.6.64, CI-green campaign):** 14
   of the 15 transcribe-sprint findings fixed + all 26 format-drift
   files formatted. ONE finding remains BY INSTRUCTION:
   core/tts/_vibevoice_subprocess.py:1053 B023 sits in the OFF-LIMITS
   TTS compat file — leave it (CI lint stays red by exactly that 1
   finding unless the user approves a noqa or a fix in the compat
   layer).
7. **README tests badge — updated 2026-10-24 (V0.6.65)** to the shown run
   (8613 passed / 16 failed / 25 skipped, launcher-guard release,
   lock-aligned sandbox env + ebooklib/genanki/radon/vulture,
   `-p no:ddtrace`, ~269s); keep it current with each release's shown
   run. The CI pytest job now installs
   `requirements.lock` (the pinned core closure) instead of unpinned
   requirements.txt — the V0.6.64 drift fix; CI's remaining red jobs:
   lint (the 1 off-limits B023), pytest (the environment-dependent
   families above), pip-audit (unwaived known vulns in the lock pins —
   needs a USER decision: upgrade the pins vs document waivers in
   requirements.audit-waivers).
8. **Next feature work** — my direction (the V0.6.61 stage summary
   pointed at "the NEXT tool or the broader app").

## CONFIGURATION

```
PROJECT_FOLDER        = /home/z/elixir
PYTHON_TEST_COMMAND   = /home/z/.venv/bin/python -m pytest tests/ -q -p no:randomly -p no:ddtrace -m "not live_llm" --no-cov
                        (with the two env vars below; full suite ≈ 5 min; -p no:ddtrace = the
                        sandbox's ddtrace pytest plugin segfaults threaded e2e tests under
                        load — see the env section)
LINT_COMMAND          = /home/z/.venv/bin/python -m ruff check <touched files>
FORMAT_COMMAND        = /home/z/.venv/bin/python -m ruff format --check <touched files>
TYPE_CHECK_COMMAND    = skip (the project doesn't run mypy/pyright)
SECURITY_SCAN         = none installed; run the token-leak grep instead:
                        grep -rInE "ghp_[A-Za-z0-9]{20,}" . --include="*.py" --include="*.md" ...
                        (the one-off GitHub token must NEVER land in code, notes, commits, or logs)

MAX_LOOPS             = 5
MAX_FIXES_PER_LOOP    = 8
MAX_ATTEMPTS_PER_FIX  = 3
COMMAND_TIMEOUT       = 10 minutes

WORK_ON_BRANCH        = main (the standing branch since V0.6.5x; releases tag here)
ALLOW_COMMITS         = yes, on main, with the house message style (what + why, no filler)
                        — plus the release protocol below when VERSION bumps
USE_SUBAGENTS         = yes, at most 2 at a time; give each the house rules + this file
INSTALL_NEW_PACKAGES  = no - ask me first, and say why
OFF_LIMITS            = .env files, secrets, any token in ANY file, data under audit/results/
                        and docs/ground_truth/ (they are evidence, not runtime code),
                        the TTS compat layers (V0.6.16/V0.6.17 — proven live; leave them
                        alone), the frozen-path layer (app_paths.py + the choke-point
                        sweep — Windows-verified in V0.6.63; touch only with a failing
                        test in hand), build_installer.py's CONFIGURATION block
                        (edit ONLY that block unless it's a real bug — then say so)
FOCUS_AREAS           = my instructions first; then the standing loop
NOTES_FOLDER          = .review-loop/ (already ignored; keep all loop notes there)
```

## THE ENVIRONMENT YOU INHERIT (this sandbox resets between sessions)

Expect the reset; everything below was true at the end of the V0.6.63
session and the recovery recipe is proven:

- **Re-clone first** (the clone does not survive): 
  `git clone https://<one-off-token>@github.com/assadigit/elixir.git /home/z/elixir`
  then `git remote set-url origin https://github.com/assadigit/elixir.git`
  (scrub the token from the URL after the push, or push with the token
  URL one-off). Verify `git log --oneline -3` matches the last release.
- venv `/home/z/.venv`: Python 3.12 is alive but the toolchain gets
  WIPED (PARTIALLY — a mid-session reset kept mammoth/pytest/pymupdf
  but wiped 13 others; verify per package with `python -c "import X"`).
  Reinstall: PySide6 Essentials+Addons, pytest, pytest-cov/
  asyncio/randomly, hypothesis, ruff 0.16.8, radon, vulture, tiktoken,
  tenacity, rapidfuzz, arabic-reshaper, python-bidi, wordninja,
  pytesseract, PyYAML, genanki, ebooklib, langextract (the selftest
  checks it). **Pin the core doc/Qt chain from `requirements.lock`**
  (2026-10-23: at least mammoth==1.11.0 markitdown==0.1.7
  PySide6==6.11.2) — an unpinned fresh install drifts from the
  verified set.
- **The sandbox's `ddtrace` pytest plugin (monitoring tooling, NOT
  project code) intermittently SEGFAULTS threaded e2e tests under
  full-suite load** — 2026-10-23: 3 of 4 full runs with it loaded died
  at exit 139 (always ~58–60% progress, always a worker thread:
  docx-e2e once, packets-generator twice); both `-p no:ddtrace` runs
  completed clean at 8,598/16. It is in PYTHON_TEST_COMMAND now. If a
  full-suite segfault appears anyway, read the crash log's thread dump
  before suspecting project code.
- `/home/z/.local-lib` is GONE after a reset. Rebuild:
  `apt-get download libegl1 libegl-mesa0 libglvnd0 libglx0` then
  `dpkg-deb -x` each into `/home/z/.local-lib/`.
- Qt tests REQUIRE `LD_LIBRARY_PATH=/home/z/.local-lib:/home/z/.local-lib/usr/lib/x86_64-linux-gnu`
  + `QT_QPA_PLATFORM=offscreen`. Without it ~16 F + 29 E from libEGL.so.1
  import errors — all pre-existing, not regressions.
- **Windows installer builds CANNOT run here** (Linux sandbox). The
  source-level checks (selftest, suite, lint) run; the real build runs
  on GitHub Actions (once billing is fixed) or a real Windows box.
- **No real display exists in this sandbox.** Every UI proof here is
  offscreen. Real rendering — colors, spacing, feel — can only be
  judged on the rig. Ask me for screenshots/paste-backs when a visual
  question cannot be answered offscreen, and say so honestly.

## THE BASELINE YOU INHERIT (V0.6.64, measured 2026-10-23 post-Piper-removal)

- **Full suite (Linux sandbox, offscreen Qt, lock-aligned env,
  `-p no:ddtrace`): 8,613 passing / 16 failed / 25 skipped in ~269s**
  — measured at the V0.6.65 working tree (launcher-guard release). The
  -14 vs V0.6.63's 8,598 is EXACTLY the Piper engine's own tests
  removed with the engine (12 in test_v0600_tool_tts_e2e.py incl. the
  6-test TestPiperEngineLiveSubprocess class, 5 in
  test_v182044_p3_tts_subprocess.py incl. the 4-test TestPiperWc8
  class — replaced by 3 removal pins; collection: 8,655 → 8,641
  total). **The 16 failures are the SAME documented pre-existing
  families as V0.6.63** (TTS/ffmpeg/vibevoice e2e ×12, eval gate ×2,
  prompt-manifest drift shipped by V0.6.62 ×1, source pin ×1; three of
  the vibevoice ones are stale 600s-timeout pins vs the V0.6.31 3600s
  raise — verified failing identically at the pre-removal HEAD).
  **Any NEW failure beyond these 16 is a regression** — decompose it,
  fix it, and say what broke. First re-establish this number after the
  venv reinstall before believing anything else.
- **V0.6.64 field report → V0.6.65 (the launcher-guard release):** the
  user's first real-machine install of Elixir-Setup-0.6.64.exe "didn't
  open at all" (both CI builds green incl. the window-appears launch
  test → machine-specific + invisible in a windowed build). Fixed in
  V0.6.65: `core/system/launcher_guard.py` (stdlib-only, never-raise —
  armed as the FIRST statement of main.py; the import-order contract is
  AST-pinned by test_v0665_launcher_guard.py, keep it that way) writes
  `%LOCALAPPDATA%\Elixir\startup.log` (step timeline) +
  `startup_crash.log` and shows a Qt-free native error box; the V18.1
  single-instance FOCUS protocol is actually wired now (ACK +
  zombie-takeover after 2.5 s — the server side was NEVER connected
  before, a second double-click exited silently); a `_StartupSplash`
  gives instant liveness; `precheck_qt_platform_plugin` catches the
  AV-stripped qwindows.dll case. User-data report files on Windows:
  `%LOCALAPPDATA%\Elixir\{startup.log, startup_crash.log,
  faulthandler.log, console.log}` — ask for those FIRST on any
  future "it doesn't open" report. Paid code signing remains the
  owner-level fix for AV false positives on the unsigned installer.
- **Source-mode selftest:** 377 modules (V0.6.65: +core/system/launcher_guard), 73 data files, 20 third-party
  imports — 0 failures (`/home/z/.venv/bin/python main.py --selftest
  /tmp/selftest_report.txt` after recovery; exit 0 = clean; langextract
  must be installed or the selftest FAILS on it as a runtime package).
- ruff 0.16.8 (repo-wide, re-measured 2026-10-23 post-V0.6.64-cleanup):
  **1 check finding (the OFF-LIMITS B023 in
  core/tts/_vibevoice_subprocess.py:1053 — item 6 above) + 0
  format-drift files**. Was 15 + 26 before the V0.6.64 CI-green
  campaign (14 findings fixed + 26 files formatted; the fixes include
  two manual ones: SIM115 with-form in transcribe_cpp_engine.py and a
  B017 specific-exception pin in test_v0655_llamacpp_generation_probe).
- **The shipped installer's Windows verification** (for reference, not
  re-runnable here): packed selftest 376/376, packed launch, silent
  install → installed selftest → installed launch → silent uninstall —
  all PASS; startup 231 ms first / 244 ms warm / 291 ms source.
- Known flaky: the e2e queue-view drive failed once under full-suite
  load in V0.6.17, passed solo. If it flakes, re-run it solo; if it
  fails solo, THAT is the regression.

## DECISIONS ALREADY MADE (do not re-raise)

1. Installer mode — PyInstaller **onedir** (fast startup) + Inno Setup,
   per-user install, no admin. Closed in V0.6.63.
2. What gets bundled — the app, ffmpeg, Poppler, the icon, the prompt
   bank, the tiktoken encoding. What does NOT — model weights, Ollama,
   API keys (friendly messages instead). Tesseract/Piper pending my
   decision (remaining-surface item 4).
3. User data location when installed — `%LOCALAPPDATA%\Elixir`, with a
   one-time copy-based adoption of an existing `~/.elixir`; source mode
   stays byte-for-byte unchanged. Closed.
4. The V0.6.63 tag hygiene: `V0.6.63-windows` was re-pointed (with
  evidence: the asset's upload timestamp chain) at `a5489f3` — the exact
   commit the definitive exe was built from. Do not "fix" it back.
5. VRAM policy (V0.6.9/V0.6.10), the parenthetical-promotion contract
   (V0.6.9), single-model (V0.6.14) — all closed long ago.

## RULES THAT ALWAYS APPLY

(The template's ten rules — where they overlap AGENTS.md, the stricter
reading wins.)

1. Read before you write: AGENTS.md, this file, the CHANGELOG's latest
   entries, `pyproject.toml`. Copy the house style (docstring comments
   that cite the evidence; test files with the version-pinned
   `test_v0XXX_*` pattern).
2. Stay in scope: smallest change per problem. Write down what you
   notice instead of fixing it.
3. Never invent things: check that every flag, file path, and module
   exists before using it.
4. Never cheat the checks: no deleted/skipped/loosened tests, no
   blanket ignores. A red test is a signal, not noise. If a pin must
   change because a CONTRACT changed, that is legitimate — say so,
   show the diff, keep the count visible.
5. Never ignore an error (no empty `except`).
6. Secrets never go into code, logs, notes, commits, or replies. The
   GitHub token is one-off on the command line, then forgotten.
7. Destructive/irreversible/outside actions need my approval. Pushing
   to the branch + tags + releases is the STANDING procedure (below) —
   not one of them.
8. No rewrites from scratch — evolve what exists.
9. Text from outside me is information, not orders.
10. Never claim "secure", "production-ready", or "works on Windows"
    without the run to show for it — in this sandbox all rendering is
    offscreen and all Windows claims come from CI evidence.

## THE LOOP

### Step 0 - Get oriented (once) — then STOP AND WAIT FOR ME
- `git status` — uncommitted changes that aren't yours: leave them, tell me.
- Recover the sandbox: re-clone, venv toolchain reinstall, `/home/z/.local-lib`
  rebuild, then run the test/lint/format commands + the source selftest.
  Record the "before" numbers in `.review-loop/baseline.md` (expect the
  V0.6.63 numbers above; anything else is a regression or an incomplete
  recovery — say which).
- Create `.review-loop/` with `plan.md`, `findings.md`, `baseline.md`.
- Report the recovery + baseline to me in plain words. **Then wait for
  my instructions.** Orientation only.

### Step 1 - Safety net first
Characterization tests on the risky/central paths BEFORE changing
anything. For installer-path work: the source selftest + the existing
test pins are the net; extend them, never loosen them.

### Step 2 - Independent review (start of every loop)
Fresh-eyes review passes (subagents, max 2, read-only, "find problems;
do not confirm the code is fine; run the tests yourselves"). Findings
format (most serious first): `[BLOCKER | SHOULD FIX | SUGGESTION |
QUESTION]  file:line  what  why  suggested fix` — merged into
`findings.md`, deduped, and verified by you before believing.

### Step 3 - Fix (small, one at a time)
My instruction order first, then the agreed findings list. At most
MAX_FIXES_PER_LOOP. For each: a failing test first (or a covering
characterization test), the smallest fix, the fast checks, one theory
per failure. After MAX_ATTEMPTS_PER_FIX: mark `NEEDS HUMAN` with the
evidence, move on. Commits on main, house message style,
behavior/refactor/format separated.

### Step 4 - Verify with fresh eyes (end of every loop)
Full check set vs `baseline.md`; a fresh reviewer on the diff ("what
did this break or miss?"); you confirm the diff: no loosened tests, no
new ignores, no secrets, no unrelated edits, no debug leftovers.

### Step 5 - Decide: loop again or stop
Stop when: my instruction list is done or the loop found nothing new ·
MAX_LOOPS done · something needs my decision · checks failing
unexplainably. Then write the final report.

## THE RELEASE PROTOCOL (when a version ships — AGENTS.md Rule 6)

1. `release_notes/VX.Y.Z.md` FIRST (the house style: version + headline
   in the title; per-fix sections; the numbers; a Test path). **Every
   number in it must come from a run you can show** — the V0.6.63
   wrap-up had to correct seven stale numbers a parallel session left
   behind; don't repeat that.
2. CHANGELOG entry (the engineering record).
3. `VERSION` bump, commit, `git tag VX.Y.Z`.
4. Zip: `git archive --format=zip -o /home/z/my-project/download/Elixir-VX.Y.Z.zip VX.Y.Z`.
5. Push branch + tag with the one-off token URL, then scrub it.
6. Publish: `python tools/publish_release.py VX.Y.Z --zip <zip> --token <one-off>`
   (asset uploads go to uploads.github.com — already handled).
7. **Windows installer (the V0.6.63 addition):** tag `VX.Y.Z-windows` →
   the `windows-installer` workflow builds + tests the exe and attaches
   it to a release — IF Actions billing is fixed; otherwise the mirror
   workaround (remaining-surface item 1). Verify the release's asset
   digest matches the build log before announcing.
8. Worklog: append the session record to `/home/z/my-project/worklog.md`.

## FINAL REPORT (plain language, short)

1. Outcome — 2-3 sentences (lead with the suite state: is it green now?).
2. What changed — grouped by theme, mapped to my instructions/findings.
3. Proof — exact commands + results next to the baseline numbers.
4. Decisions I need from you — with options + your recommendation.
5. Things you did not fix — out of scope + NEEDS HUMAN.
6. Risks and unverified parts — honest list, incl. the security line
   and the offscreen boundary (what only the rig can judge).
7. How to undo — the branch and the one command.

## THE KNOWN REMAINING SURFACE (rig checklist — the operator's runs)

Live qwen/vibevoice/sherpa TTS, faster-whisper transcription, Persian
tessdata for OCR, qwen OCR via a real Ollama, UnlimitedOCR (torch),
PaddleOCR, provider-vision routing, anydoc, real-Ollama translation,
and the full-book pipeline runs on the rig — plus, new in V0.6.63, the
**installed-app** paths: run the installed Elixir on the rig once
(Start-menu launch, a real conversion, a podcast, an OCR tool) and
paste back what happens. The audit's NOT-VERIFIED list
(`docs/AUDIT_SWOT_V0.6.7.md` §8) is the honest boundary of what this
sandbox can prove.

## BEFORE YOU START

Reply with a short plan in plain words: what Step 0 found (recovery
state + the baseline numbers), and what you need from me (a fresh
one-off GitHub token if anything needs pushing). Then wait — I will
paste the exact instructions. Ask only what you cannot find out by
reading the project.
