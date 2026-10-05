# Rig-test checklist (T1 — the headless-UI blindness threat)

> **Status:** a RUNBOOK for the owner. The sandbox cannot execute this
> (no Windows, no real Qt GUI, the 36 skips are absent deps/fixtures). The
> owner runs it on the Windows 10/11 rig. Opened V0.4.28 (SWOT T1, sev 4).
>
> **The threat (SWOT T1):** the headless sandbox skips 36 Qt tests (GUI
> regressions invisible in CI) — the app targets Windows 10/11, so the rig
> is the only place UI changes are validated. No UI-layer edits were made
> this session (V0.4.26/V0.4.27/V0.4.28 are all post-processing / tests /
> docs), but the next UI-touching change MUST run this checklist.

## 1. The 36 headless-skipped tests — install the missing deps/fixtures

The sandbox skip breakdown (categorized from the V0.4.27 full-suite run):

| Count | Skip reason | Fix on the rig |
|---|---|---|
| 12 | `camelot`/`tabula` not installed (`test_p2_pdf_tables_extractors.py` ×11, `test_p4_edge_cases_pdf.py` ×1) — optional PDF table extractors | `pip install ".[formats]"` (camelot-py + tabula-py + their Java deps); or `pip install camelot-py[cv] tabula-py` directly. Confirm Java (JRE) is installed for the tabula backend. |
| 14 | reference `.zip` artifacts absent: `/home/download/Elixir-V18.20.4.5.zip` + `Elixir-V18.20.4.6.zip` (`test_v182046_p5_dialog_split.py`, `test_v182046_p5_wizard_split.py`, `test_v182047_p5_core_decomp.py`, `test_v182047_p5_services_decomp.py`) | place the two pre-split zip artifacts at the expected paths (these are the V18.20.4.5/4.6 pre-decomposition reference trees the split tests diff against). |
| 9 | "Salman Akhtar source not found" (`test_v18_15_9_conclusions.py` ×9) | place the source-PDF fixture (the ch.1 ground-truth source) at the path the test expects — `audit/trust-ground/001_1 - IDENTITY AND ITS ORIGINS_source.md` (or the test's configured fixture path; read `test_v18_15_9_conclusions.py:60` for the exact expected path). |
| 1 | "rapidfuzz is stubbed (returns constant)" (`test_quality_fixes.py:204`) — the test runner's own stub, by design | no fix — this is the test runner's deliberate stub for deterministic results; the skip is expected. |

**After installing the above:** re-run `QT_QPA_PLATFORM=offscreen pytest --no-cov -q` and confirm the skip count drops to ~1 (the rapidfuzz stub). The pass count should rise from 6,002 to ~6,047 (the 12 camelot/tabula + 14 zip-ref + 9 source-fixture tests now collected+passing; the 1 rapidfuzz-stub stays skipped).

## 2. The Qt GUI smoke (the real UI regression net)

The headless run uses `QT_QPA_PLATFORM=offscreen` (no real rendering). The rig
MUST run a real GUI smoke to catch widget/render regressions:

```powershell
# On the Windows 10/11 rig, from the elixir checkout (V0.4.28):
.venv\Scripts\python.exe main.py
```

**Smoke procedure:**
1. **Launch:** the app window renders (no crash, no missing-DLL popup, no
   `libEGL`/`libGL` error — the rig has the system Qt deps the sandbox lacked).
2. **Wizard walk-through:** Step 1 (PDF select) → Step 2 (OCR options) →
   Step 3 (segmentation) → Step 4 (outputs — the 21 OutputSpecs render, the
   16 active checkboxes toggle) → Step 5 (model selection — the
   `create_provider` factory resolves the configured backend) → Step 6
   (settings).
3. **Convert:** run a real conversion on a small PDF (the V0.4.25 ch.1
   ground truth, or any 5-10 page book); confirm the QThread worker starts,
   the progress bar advances, the conversion log streams, + the output
   artifacts land in the output folder with run-stamped filenames
   (`{book}_v0.4.28_{run_id}.summary.md` etc.).
4. **Settings dialog:** open Settings → each tab loads (the lazy-tab loading
   from V0.4.7 + the async dependency check from V0.4.7 don't crash); the
   Output Studio section shows the 16 active OutputSpecs; the secrets paths
   resolve via the keychain (keyring IS installed on Windows — the
   `_HAS_KEYRING` check passes, unlike the headless fallback).
5. **Output Scanner:** open the scanner on the output folder; confirm it lists
   the run-stamped artifacts + the regenerate-map works
   (`controller._REGENERATE_MAP` derives from the registry).
6. **Crash report:** if anything crashes, the crash-report zip
   (`core/system/crash_report.py`) generates with redacted settings; attach
   it to the bug report.

## 3. The Windows-specific fragility (T6 from the V0.11 SWOT, mitigated but load-bearing)

These are untested in the headless sandbox + MUST be confirmed on the rig after
any startup-order change:

- **torch-before-Qt import order** (`main.py:67-110`): the DLL-shadowing fix.
  A refactor that reorders the `import torch` / `from PySide6 import` lines can
  reintroduce the CUDA DLL conflict. No test pins the import order.
- **stale-`.pyc` purge** (`main.py:21-51`): the strategy that clears stale
  bytecode before the app starts.
- **locked-file tolerance** (`ignore_errors=True`): the Windows file-locking
  tolerance (AV/indexer locks on the output folder).
- **high-DPI env** + **keychain service rename with read-fallback**
  (`core/system/secrets.py:33-38`).

**Rig check:** after the GUI smoke, confirm the app starts cleanly from a
cold boot (no stale `.pyc` errors) + that a second launch (while the first
is still running on the same output folder) handles the file-lock gracefully.

## 4. The 6 golden eval-gate chapters (the quality regression net, re-runnable)

The eval gate (`scripts/eval_summary.py --check`) uses STORED fixtures
(`tests/golden/*/`) — it does NOT re-run the pipeline. To validate output
quality on the rig's real LLM + embedder (the sandbox benchmark skipped the 3
embedder-dependent phases — the rig has them):

```powershell
# Re-run the deterministic gate (the CI half):
.venv\Scripts\python.exe scripts\eval_summary.py --check
# Expected: EVAL GATE: OK, prompt_manifest_hash ee5a61d0ebb3 (flat)

# Re-run the REAL pipeline on the ch.1 ground truth (the V0.4.25 benchmark,
# now on the rig's 27B quantized model + the embedder):
.venv\Scripts\python.exe main.py  # convert the ch.1 ground truth; the 3
# skipped phases (semantic fact-check, semantic dedup, LLM-judge gap-fill)
# now run — compare the scorecard to the V0.4.25 sandbox-rig's 8/8/6/7
# (the rig should score HIGHER — the 3 skipped phases are quality-raising).
```

**Rig validation target:** the V0.4.25 ch.1 sandbox-rig scored 8/8/6/7 PASS
(conservative floor — the 3 embedder phases skipped). The rig (with the
embedder) should score ≥8/8/7/7 (clarity ≥7 because the semantic fact-check +
dedup + LLM-judge gap-fill raise quality). If the rig scores LOWER than the
sandbox floor, that's a regression — investigate before releasing.

## 5. Sign-off

- [ ] 36 → ~1 skip (deps + fixtures installed; the rapidfuzz stub stays)
- [ ] GUI smoke passes (wizard walk-through + real conversion + settings + scanner)
- [ ] Cold-boot clean (stale .pyc + file-lock tolerance)
- [ ] Eval gate OK (hash flat) + real-pipeline ch.1 benchmark ≥8/8/7/7
- [ ] Attach the crash-report zip if any step crashed

**Only after this checklist passes** is a UI-touching release shippable. The
V0.4.26/V0.4.27/V0.4.28 releases made no UI-layer edits (by policy), so this
checklist was not blocking for them — but it IS blocking for the next
UI-touching release.
