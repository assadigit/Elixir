# New Session Prompt — Elixir: THE POST-AUDIT SESSION (V0.7.7 shipped; the campaign verified; pick what's next)

## WHO I AM AND HOW TO TALK TO ME

I am not a programmer and I cannot read or patch code myself. You do all
the work end to end. Explain everything in plain words. When you must
use a technical term, explain it in one short sentence. Put the result
or the decision I need first, details after. Never say something works
unless you ran it in this session and can show what you ran.

## THE HEADLINE (read this first)

**The wizard-rework campaign is verified, and the repo is in the best
shape of its life.** The cleanup session shipped **V0.7.6** (the suite
honestly green for the first time — 13 known failures + 5 e2e failures
root-caused and resolved, zero xfail; the repo format-clean; the README
truthful; and one real production bug found hiding among the "rig
failures" and fixed: **VibeVoice TTS had been broken on every source
install since V0.6.64**). The audit session then shipped **V0.7.7**: the
entire V0.6.86→V0.7.5 campaign independently re-verified claim-by-claim
(**verdict: it did what it claimed** — every bug fix still in place,
every honest label still honest, the differential shows zero
regressions), the untried corners actively hunted (**0 defects**), and
the one hygiene finding fixed (legacy settings files now self-clean
their dead OCR keys). The full evidence: `docs/AUDIT_CAMPAIGN_V0.7.5.md`.

Current state: **V0.7.7** (tag pushed, GitHub Release id 435901577 with
the zip). Full suite **9,200 passed / 0 failed** + the transcribe e2e
**66 passed / 0 failed**; `ruff check` clean; `ruff format --check`
clean repo-wide; the eval gate OK.

## THE MENU — WHAT YOU CAN PICK NEXT

1. **The scratch-file cleanup (the one pending approval).** At the
   V0.7.6 checkpoint I presented the inventory + per-item greps and
   waited; no answer arrived by the tag point, so it is recorded, not
   done. APPROVE IT and it lands as one chore commit (~21 MB out of the
   repo): delete the 31 `now*.png` working screenshots, `369.png`,
   `508782d6-4b80-48be-9046-d081ce258b75.png`, and the three nested zips
   (ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip,
   Elixir-Document-Type-Modes.zip, Elixir-diagnostics.zip); rename
   `ELIXIR_UI_UX_CORRECTION_ROUND_2 (1).md` (drop the " (1)"); add
   `/now*.png` to .gitignore. Alternative per item: move under
   `docs/evidence/` instead of deleting.

2. **The deferred backlog (any item, one session each):**
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
      V0.4.19 (an audit observation); decide the exposure story.

3. **The micro-cleanup batch (the audit's three observations):** the
   "Maximum" quality preset silently-ish enabling the Ollama-only
   self-consistency (it is visible and truthfully labelled, but the
   preset name over-promises); dropping `gap_fill_concepts`' two unused
   overdeliver params; harmonizing the close-out's B3 phrasing. None are
   defects; all are small.

4. **A new feature / a new book conversion / anything else** — the rig
   baseline below is verified; the campaign's reference patterns are in
   the close-out doc.

## KNOWN RIG STATE (verified at V0.7.7)

- **Venv:** `/home/z/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12 -m venv .venv`,
  then `pip install -r requirements.txt` PLUS the full extras list
  (`PySide6==6.11.2 PySide6_Addons==6.11.2 PySide6_Essentials==6.11.2
  shiboken6==6.11.2 ebooklib genanki radon hypothesis ruff pytest
  pytest-cov pytest-asyncio pytest-randomly pymupdf pydub soundfile
  scipy huggingface_hub chardet reportlab pikepdf arabic-reshaper
  python-bidi tiktoken`). The pyside6-webengine/pdf 6.12 warning is
  cosmetic.
- **Qt offscreen:** `apt-get download libegl1 libglvnd0 libglx0`, then
  `dpkg-deb -x <each>.deb /tmp/qt-libs/extract` (ONE deb per command),
  then `export LD_LIBRARY_PATH=/tmp/qt-libs/extract/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
  and `export QT_QPA_PLATFORM=offscreen`.
- **Suite:** ~4.5 min with `--no-cov`, FOREGROUND (timeout 590),
  `-p no:randomly`; **deselect tests/test_v0600_tool_transcribe_podcast_e2e.py
  from full runs** (it passes standalone, 66/0, but segfaults in the
  combination). Both `ruff check` AND `ruff format --check` are now
  clean repo-wide — keep them clean.
- **Offscreen traps (all still true):** never `wizard._go_next()` with
  an invalid step; no processEvents for full-wizard grabs (one is fine
  for a single step alone); one variant per process for manual grabs;
  stub SimpleWorker in BOTH step5_models and step6_translation before
  any full-wizard build (`scripts/hunt_v0760.py` is the current
  reference driver).
- **GitHub:** the repo answers at both assadigit/elixir and
  assadigit/Elixir (a redirect); pushes work with either. Use the
  session token in the Authorization header for API calls (anonymous
  hits 403 rate limits).
- **The VLM discipline (proven three times now):** investigate every
  vision-model flag on a 2-4× zoomed crop or by pixel/geometry
  measurement before believing it — full-page-scale misreads are the
  norm, not the exception.

## THE LOOP (any future session)

Recover: `cd /home/z/elixir-repo` (clone with a fresh token if absent).
`git log --oneline -8` should show, from the top: the audit-report
commit (0e20fd9), the V0.7.7 release (ad7fa20), a0383fd (the pin
amendment), 46eb41f (the audit tooling), 12597e4 (the HY-1 fix), the
V0.7.6 release (5ca0cb8), then the cleanup series; tags V0.7.6 + V0.7.7;
VERSION 0.7.7. Read AGENTS.md → this prompt →
docs/AUDIT_CAMPAIGN_V0.7.5.md (the verification record) →
docs/CAMPAIGN_CLOSEOUT_V0.7.5.md. Then ASK ME which menu item to work
on.
