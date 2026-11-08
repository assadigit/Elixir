# New Session Prompt — Elixir: THE POST-APPROVALS SESSION (V0.7.8 shipped; the menu is the backlog)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## THE HEADLINE (read this first)

**V0.7.8 shipped, and the repo is the cleanest it has ever been.** The
post-audit session landed everything I approved: the scratch-file
cleanup (exactly as proposed — ~21 MB out, the ROUND_2 rename, the
screenshot ignore rule; **the release zip is 12 MB vs V0.7.7's 32 MB —
the first clean zip**), my standing **"never hardcode a specific TTS
model"** reminder (now **AGENTS.md Rule 8**, with the one runtime
violation it caught — the wizard's VRAM check assuming NeuTTS — already
fixed and pinned), and the audit's three tiny observations (the
"Maximum" preset tooltip now spells out the Ollama-only truth, the
close-out's B3 phrasing harmonized, the gap-filler's two dead params
dropped). I also confirmed the five deferred backlog items stay valid
picks. Evidence: `release_notes/V0.7.8.md` + the CHANGELOG entry.

Current state: **V0.7.8** (tag pushed, GitHub Release id 435943161,
Latest). Full suite **9,211 passed / 0 failed** + the transcribe e2e
**66 passed / 0 failed** (badge total 9,277); `ruff check` clean;
`ruff format --check` clean repo-wide; the eval gate OK.

## THE MENU — WHAT YOU CAN PICK NEXT

1. **The deferred backlog (I confirmed all five as valid picks — any
   item, one session each):**
   a. Harakat → TTS/podcast wiring (D16) — wire the `.harakat.md`
      output into the Farsi TTS stack (currently a manual-review file,
      honestly labelled).
   b. Self-consistency on all engines + true majority voting (D10
      follow-up) — lift the Ollama-only gate, replace the union-merge.
   c. VL image-*description* pass for Scanned mode (audit §6.1) —
      describing imagery, not just transcribing it.
   d. Embedding-based coverage recall metric (⑦c stretch) — swap in if
      the keyword metric proves gameable.
   e. B3 bullet-voting exposure decision — the engine path exists,
      default-off; the Settings page has carried a checkbox since
      V0.4.19; decide the NEW-surface (wizard) story.

2. **A new feature / a new book conversion / anything else** — the rig
   baseline below is verified; the campaign's reference patterns are in
   `docs/CAMPAIGN_CLOSEOUT_V0.7.5.md`.

## STANDING RULES RECAP (the ones this session added or exercised)

- **Rule 8 (new, V0.7.8):** never hardcode a specific TTS engine/model
  in logic — logic reads `tts.en_engine` (or the matching setting),
  paths stay single-sourced in the registry, UI dropdowns are the
  designed choice surface, deprecation degrades to a clear message.
  Enforced by `TestVramCheckPassesConfiguredTtsEngine`.
- **Rule 1 reminder:** every fix stays content-agnostic — no
  book-specific names, lists, or thresholds in runtime code.
- **Rules 5-6:** every release = VERSION + tag + push + release notes +
  CHANGELOG + the zip in `/home/z/my-project/download/` (built with
  `git archive` FROM THE TAG, before `tools/publish_release.py` — the
  publisher only uploads an existing zip) + the GitHub Release.

## KNOWN RIG STATE (verified at V0.7.8)

- **Venv:** `/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`,
  then `pip install -r requirements.txt` PLUS the full extras list
  (`PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2
  shiboken6==6.11.2 ebooklib genanki radon hypothesis ruff pytest
  pytest-cov pytest-asyncio pytest-randomly pymupdf pydub soundfile
  scipy huggingface_hub chardet reportlab pikepdf arabic-reshaper
  python-bidi tiktoken`).
- **Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0`, then
  `dpkg-deb -x <each>.deb /tmp/qt-libs/extract` (ONE deb per command),
  then `export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
  and `export QT_QPA_PLATFORM=offscreen`.
- **Suite:** ~4.5 min with `--no-cov`, FOREGROUND (timeout 590),
  `-p no:randomly`, `--ignore=tests/test_v0600_tool_transcribe_podcast_e2e.py`
  in full runs (the e2e passes standalone, 66/0, but segfaults in the
  combination). Both `ruff check` AND `ruff format --check` must stay
  clean repo-wide. The eval gate: `scripts/eval_summary.py --check`.
- **Offscreen traps (all still true):** never `wizard._go_next()` with
  an invalid step; no processEvents for full-wizard grabs (one is fine
  for a single step alone); one variant per process for manual grabs;
  stub SimpleWorker in BOTH step5_models and step6_translation before
  any full-wizard build (`scripts/hunt_v0760.py` is the reference
  driver).
- **GitHub:** the repo answers at both assadigit/elixir and
  assadigit/Elixir (a redirect); pushes work with either. Use the
  session token in the Authorization header for API calls (anonymous
  hits 403 rate limits).
- **The VLM discipline:** investigate every vision-model flag on a 2-4×
  zoomed crop or by pixel/geometry measurement before believing it.

## THE LOOP (any future session)

Recover: `cd /home/z/elixir-repo` (clone with a fresh token if absent).
`git log --oneline -8` should show, from the top: the V0.7.8 release
(5f5f63f), fffbe01 (the preset tooltip + B3 phrasing + the batch pins),
2e9b61d (the overdeliver drop), 78ec068 (the TTS engine fix + Rule 8),
922f51a (the approved scratch purge), then the V0.7.7-era commits; tags
V0.7.6 + V0.7.7 + V0.7.8; VERSION 0.7.8. Read AGENTS.md (now EIGHT
rules) → this prompt → docs/AUDIT_CAMPAIGN_V0.7.5.md →
release_notes/V0.7.8.md. Then ASK ME which menu item to work on.
