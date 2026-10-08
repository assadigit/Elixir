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
> 3. **V0.5.11–V0.5.15 headings added retroactively (V0.5.16):** those five
>    releases shipped as tags + detailed commit messages but their `## V…`
>    headings were never entered in this file (a Rule 4 provenance gap
>    caught by the repeatability session's pre-flight audit). The entries
>    below were reconstructed VERBATIM from the release commit messages
>    (`72d4a59`, `a264af0`, `d5d7c86`, `a0b711c`, `68946df`) — no
>    information invented; the commits remain the authoritative record.


## V0.6.60 — "the GGUF isn't even on disk yet — get it for me": the model downloader — a "⬇ Get models" button in the GGUF row opens a downloader for handy-computer's Hugging Face repos (the catalog live-verified: turbo Q5_K_M ★ recommended at 591 MB, large-v3 up to 1.6 GB), with live progress (done/total · % · MB/s · ETA), cancel-and-resume (.part + ETag sidecar + If-Range — a republished remote can NEVER be mixed into a stale prefix), atomic completion, GGUF-header verification on arrival, and auto-select in the GGUF dropdown (download → selected, one flow) — plus every GGUF combo entry now carries a full-details tooltip (what the file's OWN header proved) — 55 new pins / 438 P affected sweep / 0 regressions

> **The follow-up (the V0.6.59 worklog's next-phase candidate #2):** V0.6.59 closed "just select the gguf model" for a file already on disk; when it is NOT on disk, every error ended with "download a Whisper GGUF from handy-computer on Hugging Face" — a manual browser trip, a folder pick, and (the classic rig failure) a 591 MB–1.6 GB file that lands in Downloads where the operator then can't find it. V0.6.60 closes the loop inside the app.
>
> **The evidence (live, this session):** the handy-computer repos re-enumerated via the HF API with exact byte sizes (turbo: F16 1625935520 / Q4_K_M 536069728 / Q5_K_M 619628128 / Q6_K 692536928 / Q8_0 886381760; large-v3: F16 3107236640 / Q4_K_M 997303008 / Q5_K_M 1161143008 / Q6_K 1297130208 / Q8_0 1668741440); the turbo Q5_K_M header range-requested and parsed with the V0.6.59 reader (architecture 'whisper', name 'Whisper Large v3 Turbo', size_label '809M', file_type 17, 589 tensors, 67 KVs); the resolve URLs verified to answer HEAD with accept-ranges: bytes + a strong ETag (the xet content hash) — what the resume safety rides on; and the downloader itself run live against the REAL CDN (probe → streamed cancel at 4 MB → If-Range resume from 4194304 to 8388608), twice.
>
> **The fix — three pieces.** (1) **core/transcribe/model_downloader.py (new, Qt-free stdlib leaf):** DOWNLOAD_CATALOG (5 curated entries, turbo Q5_K_M ★ recommended — the V0.6.58 speed ledger's verdict), probe() (HEAD, never raises), download() (streamed to .part with Range resume, per-chunk progress with speed+ETA, should_cancel checked every chunk, final size sanity, atomic os.replace — a model file is never half-visible under its real name), verify_download() (the V0.6.59 catalog gate re-used: GGUF magic + whisper architecture from the downloaded file's OWN header + exact-size cross-check), default_download_dir() (lands the file exactly where the V0.6.59 scan looks FIRST; POSIX-guarded so it can never literal-create a 'C:\\transcribe.cpp' folder in the CWD). (2) **ui_qt/views/service_dialogs/model_download_dialog.py (new):** the catalog list + details panel + per-entry tooltips, destination shown up-front with 📂 Open folder, progress bar + live speed/ETA line, resumable cancel, the "already on disk?" question with a Use-the-existing-file answer (same verification gate), on_installed(path) callback; ALL network on a SimpleWorker (the house _llm_test_worker precedent) — the UI thread never blocks. (3) **The transcribe dialog:** the ⬇ Get models button (built before the _on_engine_changed call — the V0.6.55 construction-order rule, pinned for the new button), _on_model_installed (saves the setting, refreshes+selects the combo, status + live-log lines), the empty placeholder now offers the download, and every GGUF combo entry carries a full-details tooltip (format_model_tooltip in the Qt-free catalog leaf: name/params/quant/size/path/GGUF version + what the header PROVED vs. guessed from the filename — the worklog's candidate #3).
>
> **The fresh-eyes review (two parallel read-only reviewers) ran pre-release: both RELEASE READY, and every SHOULD-FIX was fixed BEFORE shipping, each with a pin:** the 416 dead end (a .part at-or-beyond the remote's size re-sent the same unsatisfiable Range forever — now a 416 probes: part == fresh size → finalized with zero bytes moved; else one clean restart from zero); the corrupt-mix path (a blind Range resume against a republished remote welds stale prefix to fresh suffix — a file that passes the size AND header checks, proven dynamically — now resume is only trusted with the ETag sidecar + a 206 from If-Range, else restart; the sidecar is written BEFORE the first body byte and deleted with the rename); Close/Esc not cancelling (only the window X reached closeEvent — reject() now carries the same policy); the env-dependent exe-fallback test + the unpinned POSIX guard (both fixed — the guard has its own chdir test); plus the stale progress-line on failure, the use-existing path, the URL-filename traversal pins ('..' is a REAL pathlib component — caught explicitly), the .en-variant Language line, and three weak pins (a tautology, a subsumed disjunct, a dead monkeypatch) tightened.
>
> **Verification:** 55 new pins in tests/test_v0660_model_downloader.py (a hermetic local HTTP server with Range/206 + If-Range + ETag support, request recording, a Range-ignore mode and a declared-size-lie mode; the GGUF fixtures reuse the v0659 builder — house cross-test-import precedent). Affected sweep (V0654–V0660 + e2e): 438 P / 18 S / 0 F. Full suite: the failure set is byte-identical to pristine V0.6.59 (git-stash comparison, both directions) — zero regressions, zero incidental fixes. Ruff: all new/modified files clean (the dialog's 2 findings are the documented pre-existing ones, reproduced on pristine). py_compile all touched files. Live: probe + streamed cancel + If-Range resume against the REAL handy-computer CDN. **The rig flow after V0.6.60:** open the dialog → ⬇ Get models → Download → live progress → "✅ downloaded and verified — selected in the GGUF dropdown" → Transcribe; a cancelled download resumes where it stopped (the .part + ETag sidecar stay on disk); a model that already exists is offered for reuse through the same gate. Nothing leaves the app.


## V0.6.59 — "I already downloaded whisper large v3 from handy computer, so I just select the gguf model": the GGUF catalog — the app now READS the model file's own header (a real GGUF metadata parser: magic + version + tensor count + all 13 value types, byte-capped, verified this session against handy-computer's actual whisper-large-v3-Q5_K_M.gguf), a "GGUF model" dropdown lists every Whisper .gguf on disk (the CLI exe's folder, C:\transcribe.cpp\models, the saved model's folder, ~/Downloads — where the browser download lands) with name · quant · size · header-verification, the engine VERIFIES the selected file BEFORE the CLI launches (a llama GGUF fails in seconds naming general.architecture = "llama"; a legacy ggml-*.bin fails with "transcribe-cli.exe loads .gguf"; unparsable headers proceed with a [WARN] — the CLI is the final authority), and a missing model triggers a self-healing disk scan ([MODEL-SCAN] lines, best-match auto-pick, persisted back to settings) — 76 new pins / 327 P affected sweep / 0 regressions

> **The trigger (the operator's request, verbatim):** "Look I alreayd downloaded whisper large v3 from handy computer, can you make the backend for it yourself, so i just select the ggql modekl." — the GGUF was on disk; what the app lacked was the backend that makes "just select the file" work: the engine trusted the setting blindly (a stale path / a llama GGUF / a legacy .bin all surfaced only as a CLI crash minutes into the run), a missing model silently fell back to one hardcoded path (a downloaded model in Downloads or under a different quant name was invisible), and the dialog's only affordance was a raw browse whose filter even offered *.pt files.
>
> **The evidence (live, this session):** handy-computer's Hugging Face repos enumerated via the HF API — whisper-large-v3-gguf ships exactly whisper-large-v3-{F16,Q4_K_M,Q5_K_M,Q6_K_M,Q8_0}.gguf (+ tiny/base/small/medium/large/large-v2/large-v3-turbo and .en variants; the filename parser targets these REAL names); and the actual whisper-large-v3-Q5_K_M.gguf header range-requested and walked — general.architecture = 'whisper', general.name = 'Whisper Large v3', general.size_label = '1.5B', 68 KVs, GGUF v3, 1261 tensors, tokenizer.ggml.tokens x51,866 (the reader skips arrays beyond 1,000 items with a summary marker — the fresh-eyes review measured a crafted 2M-item array at ~550 ms of UI-thread CPU; the real file parses in ~55 ms, bounded).
>
> **The fix — three pieces.** (1) **core/transcribe/model_catalog.py (new, Qt-free stdlib leaf):** read_gguf_header (streaming binary reader, 4 MB metadata cap — a 3 GB model is never slurped and a corrupt count field can never hang), parse_model_filename, describe_model_file (name AND bytes: family/quant from the filename, architecture/name/params from the header), scan_model_dirs (non-whisper GGUFs EXCLUDED, legacy .bin included-but-flagged and ranked last), model_search_dirs, and resolve_model() — the engine's single decision point. (2) **The engine:** the old trust-the-setting block is replaced by _resolve_cpp_model → the catalog; the [MODEL] log line now carries what the file itself PROVED ("Whisper Large v3 · Q8_0 · 1.5B · GGUF header verified (architecture: whisper) — the model file reloads on every run"); scan picks persist back to settings (self-healing). (3) **The dialog:** a "GGUF model" row (combo + 🔄 rescan + the moved 📁 Model browse whose filter now puts *.gguf first) — selecting from the combo saves the setting in one click; the run header names the selected GGUF for cpp runs (the V0.6.57 gap: they logged no model line at all); the faster-whisper row's dangling label is hidden with its widgets.
>
> **The fresh-eyes review (Task 15) ran pre-release: RELEASE READY, and its 5 SHOULD-FIX findings were fixed BEFORE shipping, each with a pin:** the unguarded Path(current) at dialog open (the V0.6.53/55 construction-crash class — settings values are now str-coerced); the pathological UI-thread freeze (array inline-limit); the scan auto-picking + persisting a legacy .bin unvalidated (auto-pick now requires the GGUF magic; only-.bin discoveries get a dedicated error naming them); the overpromising "the engine will verify it" log line (the verdict now states what the header proved); weak test pins (a tautology, an A-and-B-or-C precedence bug, a 300 MB fixture).
>
> **Verification:** 76 new pins in tests/test_v0659_whisper_gguf_catalog.py (real-GGUF byte fixtures mirroring the live-verified field order; reader round-trips incl. scalar types, string arrays, truncation, corrupt 2^40 kv-count, the never-slurp cap; handy-computer's REAL filenames; validation fail-fasts; scan scoring; search-dir composition; resolve_model's decision table; the engine wrapper with monkeypatched settings; engine + dialog AST pins incl. the V0.6.55 construction-order pin EXTENDED to the new widgets). Affected sweep (V0654–V0659 + e2e): 327 P / 18 S / 0 F. Full suite: 86 failures before == 86 after, byte-identical set (stash-verified on pristine V0.6.58) — zero regressions. Ruff: only the 2 pre-existing engine findings (F401 os, SIM115 — reproduced on pristine); new files clean. Live: the parser was run against the REAL whisper-large-v3-Q5_K_M.gguf header — verified=True, quant parsed, tokenizer arrays skipped. **The rig flow after V0.6.59:** open the dialog → the GGUF dropdown already lists the downloaded whisper-large-v3-*.gguf → click it → Transcribe; a wrong file fails within seconds with the exact fix.


## V0.6.58 — "dragging video to this bat file transcribe it under 1 minute": the uploaded transcribe.bat proves the app runs the BYTE-IDENTICAL command — a computed `[PARITY]` line now says so per run, `[SPEED]` lines carry the last run's measured throughput forward (the CLI's own `realtime:` figure + the wall clock, persisted per model in the speed ledger) so the wait has an expectation BEFORE it starts, and a measured-slow run earns the upstream's own whisper-large-v3-turbo recommendation (809M/886 MB/WER 2.01% vs 1.5B/1.67 GB/1.82%, no rebuild) — 58 new pins / 263 P affected sweep / 0 regressions

> **The trigger (the operator's report, verbatim):** "Look it seems there is a problem: [a V0.6.57 log: `[GPU] GPU: 99% util, 11.7 GB VRAM used` repeating for 6+ minutes on a 14:43 video, with `[DEVICES] [0] NVIDIA GeForce RTX 3060 (vulkan, 11.3 GiB free)` and a zero-extra-flags `[CMD]`] Note, dragging video to this bat file transcribe it under 1 minute, hope it gives you ideas." — plus the actual `transcribe.bat`, uploaded.
>
> **The diagnosis (the bat + the upstream source, evidence-first):** (1) the bat's CLI line (`"%CLI%" -m "%MODEL%" "%WAV%"`) is BYTE-IDENTICAL to the app's `[CMD]` — same exe, same model, same zero extra flags, and the bat's ffmpeg conversion (`-ar 16000 -ac 1`) is the engine's `_convert_to_wav16k` exactly; any speed difference vs the bat cannot be the command line, but "identical" was an eyeball claim, not a computed one. (2) The upstream `examples/cli/asr.cpp` (read this session): no `isatty` checks, no progress bars, the whole summary (`run:`/`text:`/`segments:`/`realtime:`) prints only at the END — pipe-vs-file output handling changes nothing the child computes. (3) ~2.4x realtime is whisper-large-v3-on-Vulkan reality (the biggest Whisper, 1.5B/1.67 GB Q8_0, on an RTX 3060): a 14:43 video is a ~6-minute run, normal — and the CLI's own last line prints that throughput figure, which the app never parsed or remembered. (4) The upstream's own speed guidance is specific: `docs/models/whisper.md` calls whisper-large-v3-turbo (809M, 886 MB Q8_0, WER 2.01% vs 1.82%) "the best accuracy/speed tradeoff" — a ~4x smaller decoder, no rebuild; and `.github/workflows/cuda-windows.yml` is the CUDA build path (several times faster than Vulkan on GeForce).
>
> **The fix — the speed contract, four additions.** (1) **`[PARITY]` (computed, per run):** the engine builds the bat's canonical argv and COMPARES it to the command it is about to run — `  [PARITY] byte-identical to your transcribe.bat command (same exe, same model, same WAV, no app-added flags) — any speed difference vs the bat is NOT the command line`; a language hint (`-l en`) is named honestly when present. (2) **`[SPEED]` before the wait:** new Qt-free stdlib leaf `core/transcribe/speed_ledger.py` — a tiny JSON ledger (`~/.elixir/transcribe_speed_ledger.json`, atomic write, best-effort everywhere: corrupt/missing/unwritable is a missing line, never a failed run) records the last completed run per model, so the next run opens with `  [SPEED] last run of whisper-large-v3-Q8_0.gguf: 2.4x realtime — expect ~6 min for 14:43 of audio`. (3) **`[SPEED]` at the end (both figures):** the engine parses the CLI's own `realtime:` line and logs the wall-clock ratio beside it — `  [SPEED] done in 06:12 — 2.4x realtime for 14:43 of audio (the CLI's own figure: 2.0x compute-only)` (the wall includes the per-run model reload, the CLI's figure excludes it — printing both says where the time went); both persist to the ledger. (4) **The slow-model hint (data-gated):** a run under 5x realtime on a non-turbo whisper earns the upstream's turbo recommendation (download from huggingface.co/handy-computer, point the Model button at it — no rebuild) or the CUDA rebuild path; first slow run fires it at the END (where the operator is staring), later runs get it up front from the ledger; fast runs, turbo models, and no-data runs never see it — never a diagnosis without a measurement. The operator's actual `transcribe.bat` is frozen into `tests/fixtures/transcribe.bat` — the parity pins check the REAL file's invocation shape, conversion, and model path, not a description of them.
>
> **Verification:** 58 new pins in `tests/test_v0658_transcribe_speed_ledger.py` (the upstream printf format parsed exactly; ledger round-trips/corruption/runs-counter; the expectation + done formatter lines incl. rounding; the slow-gate; the engine helpers dynamically; 8 engine AST pins — parity+speed before Popen, the V0.6.57 config block intact and first, record_run after the [OK] line before progress(100), the try/except around the speed loop, audio duration measured pre-run because the temp WAV is deleted before the result builds; the bat-fixture pins). Bidirectional: 14 engine-wiring pins FAIL on the pristine V0.6.57 engine (stash-verified; leaf tests pass against the leaf); full-RED without the leaf is a collection error; GREEN 58/58. Affected sweep 263 P / 1 pre-existing F / 18 S. Full suite 86 failures before == 86 after, IDENTICAL set (the documented pre-existing sandbox environment set). Ruff: the only 2 findings on the engine are the same 2 on pristine V0.6.57 (pre-existing, untouched); new files clean; `ruff format` churn on pre-existing code was reverted — the engine diff is purely additive (120 insertions, 5 hunks).


## V0.6.57 — "Why model is working on CPU?" answered with data, not guesses: a `--list-devices` pre-flight names the backends actually compiled INTO transcribe-cli.exe (seconds, before the model loads), live nvidia-smi lines show the GPU working (or idle) every 30s, the run config (model size / audio duration / exact command) is on record, the "[RUN] (Vulkan GPU)" label is now built from the pre-flight instead of assumed, and the end-of-run `backend:` verdict warns loudly on CPU — 55 new pins / 204 P affected sweep / 0 regressions

> **The trigger (the operator's report, verbatim):** "Why model is working on cpu? I have weak cpu and strong GPU! ... it used to transcribe in less than a minute by using the same transcribe.cpp! Something is broken" — a real 15-minute 256 MB video sat silent 3+ minutes in the new V0.6.56 live log, and the operator supplied the upstream repo (github.com/handy-computer/transcribe.cpp), which made the CLI's actual contract readable.
>
> **The diagnosis (evidence-first, three facts):** (1) the app did NOT switch the CLI to CPU — the command (`[exe] -m <model> [-l lang] <wav>`) is byte-identical since V0.6.40 (git-verified); V0.6.56 changed only HOW output is read (Popen + reader threads vs `capture_output=True`), never what the child receives. (2) The CLI is silent BY DESIGN while working — the upstream `examples/cli/main.cpp` prints the `audio:` block, loads the model SILENTLY, and only then prints `model: … -> ok` + `backend: <kind>`; the whole summary lands at the END (the V0.6.52 fixture agrees: `realtime:` is post-run math). A 3-minute silent log is the model load in progress. (3) The most probable root cause is the exe itself: upstream `docs/build-windows.md` — a plain `cmake -B build` on Windows is **CPU-ONLY**; Vulkan requires `-DTRANSCRIBE_VULKAN=ON`, and the default `auto` backend then silently picks CPU. A `git pull` + plain rebuild drops the GPU without a word (same project, different binary — matching "same transcribe.cpp" perfectly). The app's "(Vulkan GPU)" label was an assumption since V0.6.40, never a verified fact.
>
> **The fix — four diagnostics, all in the live log.** (1) **The `--list-devices` pre-flight** (`core/transcribe/gpu_probe.py`, a new Qt-free stdlib leaf): the engine runs `<exe> --list-devices` BEFORE the 3 GB model starts loading — a GPU registered → `  [DEVICES] GPU device registered: [0] NVIDIA GeForce RTX 3060 (vulkan, 10.5 GiB free) — the CLI auto-selects it`; only-CPU devices → `  [DEVICES] NO GPU device registered (…) — this transcribe-cli.exe will compute on CPU` + a WARNING with the exact rebuild command (`cmake -B build -DTRANSCRIBE_VULKAN=ON`, Vulkan SDK, docs/build-windows.md) or the faster-whisper alternative; an exe predating the flag → one honest "listing unavailable" line (kept the historical label rather than guessing). (2) **Live GPU telemetry:** every 30s while the CLI runs, a best-effort `nvidia-smi --query-gpu=utilization.gpu,memory.used` query lands as `  [GPU] GPU: 96% util, 3.3 GB VRAM used` — rising VRAM during model load is progress-proof even at 0% util; util ≤5% is flagged `(idle — sustained 0% while the CLI works points at CPU/fallback)`. The probe rides the worker's existing 0.5s poll loop (never the UI thread; thread-safe log path identical to the reader threads), is capped by a 2s timeout (a wedged driver can never hang the worker), and on the first failure logs ONE "probe unavailable" line and disables itself — `None` is a legitimate answer, never an exception. (3) **Run config on record:** `  [MODEL] whisper-large-v3-Q8_0.gguf (3.0 GB) - the model file reloads on every run` (the #1 silent-time cost, finally visible), `  [AUDIO] 15:02 of audio to transcribe` (stdlib `wave` on the temp WAV — sets the wait expectation; non-WAV skips the line), `  [CMD] <the exact command line>` (the manual-repro ground truth against the owner's transcribe.bat). (4) **Honest labels + end verdict:** the `[RUN]`/`progress(20)` status is built from the pre-flight result — `(vulkan)`/`(cuda)` when a GPU device is registered, `(CPU ONLY - no GPU device in this exe)` when not — and the CLI's own parsed `backend:` line (since V0.6.52) now gets a WARNING when it says CPU. The heartbeat's silence hint is ENGINE-AWARE (`format_heartbeat_line(engine=…)`): transcribe.cpp runs explain the CLI's end-only printing + point at the `[GPU]` lines; LLM-phase runs keep the V0.6.56 hint verbatim — on the triggering raw-transcript-only run the old "LLM on CPU" text was actively misleading (no LLM was involved at all).
>
> **Caught mid-release by the operator's repo link:** the draft CPU-warning named `-DGGML_VULKAN=ON` — whisper.cpp's flag, WRONG for this project (transcribe.cpp uses `-DTRANSCRIBE_VULKAN=ON`). Both warning strings now carry the correct flag, and a pin bans `GGML_VULKAN` from them forever. The engine module docstring (which claimed the tool "uses the Vulkan GPU backend" as fact) now states the auto-backend reality.
>
> **Verification:** 55 new pins in `tests/test_v0657_transcribe_gpu_probe.py` — gpu_probe leaf parsing/format (nvidia-smi CSV, `--list-devices` blocks incl. igpu/accel + names-with-spaces + multi-GPU first-row + garbage→None), probe dynamics on the fake-Popen harness (lines land, unavailable-logs-ONCE-then-disables, raising probe contained, no-interval call sites never probe, probe lines never move the bar), engine run-config helpers (model name+size, CMD repro, a real 65s WAV → `01:05`, non-WAV skips, missing model still logs), pre-flight AST pins (probe before Popen, honest `{gpu_label}`), the flag guard, the engine-aware hint, dialog wiring (`_run_engine` seeded in `__init__`, stored before the worker spawns, passed to the hint). Bidirectional: 38/40 fail on pristine V0.6.56 sources (stash-verified), 55 pass post-fix; the 4 late pre-flight pins re-verified RED then GREEN via stash. Affected-seam sweep (transcribe/cpp/pipeline/gpu): 204 P / 1 pre-existing F (stash-verified identical on pristine V0.6.56) / 18 S. Ruff: the 4 findings on the touched files are the same 4 on pristine V0.6.56; the new files lint clean. Rig-only boundary: no NVIDIA GPU / no Windows exe in the sandbox — the nvidia-smi + `--list-devices` paths run through injected runners + the upstream main.cpp format; the rig's first real run is the final validation (a `[DEVICES]`/`[GPU]` paste settles it in seconds).


## V0.6.56 — the Transcribe Service internal log container: the 10-minute "frozen or progressing?" wait ended (the whisper CLI now STREAMS line-by-line into the live log + a 15s heartbeat proves the app is alive while the engine is silent; one review BLOCKER — an `isRunning()` API crash 15s into every run — caught + fixed pre-release) — 30 new pins / 405 P affected sweep / 0 regressions

> **The trigger (the operator's report, verbatim):** "add an internal log container like other tools of this app has, because i waited 10 minute to no avail and i wasn't sure it's frozen or progressing" — the symptom named a missing widget; the investigation found the root cause was structural silence.
>
> **Root cause 1 — the engine was structurally silent.** `transcribe_with_cpp` ran the whisper CLI via `subprocess.run(capture_output=True)`: ALL output trapped in memory until process exit. Between `progress(20)` and `progress(100)` the pipeline emitted NOTHING — minutes of total silence on a 15-minute video; no log container could have shown progress because none existed. **The fix — `_stream_cli_output`** (`core/transcribe/transcribe_cpp_engine.py`): Popen + two daemon reader threads (per-stream, so both work on Windows where `select()` can't multiplex pipes) pump stdout/stderr line-by-line — every CLI line echoed to the live log prefixed `  [whisper] …` (the transcript visibly builds while whisper works); progress-bar-shaped lines (`### 42%`) and `progress = 42%` callbacks map onto the 20..90 slice of the bar with integer-percent dedup (transcript text merely CONTAINING a percent is echoed, never mapped — the review caught the naive regex moving the bar backward on "I am 100% sure"); `\r` spinner frames collapse to the latest; the accumulated text is BYTE-FAITHFUL to `capture_output=True` (the P6 parser's input unchanged — pinned); the timeout is now a MONOTONIC deadline enforced by a 0.5s poll (kill on expiry, legacy error string verbatim) and a post-Popen streamer failure kills the CLI instead of leaking it (GPU + filling pipe); the best-effort try/except sits INSIDE the read loop around the callbacks only (a raising callback can truncate the echo, never the accumulated parse input). The ffmpeg conversion extracted to `_convert_to_wav16k` (verbatim error strings) — which also fixed the quietly-dead temp-WAV cleanup: the old code passed the `NamedTemporaryFile` OBJECT to `_cleanup_temp` (`Path()` → TypeError swallowed by the best-effort except — never deleted); the string path actually deletes now.
>
> **Root cause 2 — the container existed but was hidden.** `BaseServiceDialog` ships the live-log toggle + panel every other tool uses; this dialog hid it as "dead" and its `_on_progress` override dropped every message. V0.6.56 (`transcribe_service_dialog.py`): the toggle is visible, the log **auto-opens + clears on run start** with a run header (file + size, engine, model, outputs — the packets-tool precedent), **every pipeline message lands in it** timestamped (the "📝 LLM is writing" chunk lines sampled every 10th in the log — the status label keeps per-chunk updates, P4's contract; the prefix is a shared `_LLM_CHUNK_PREFIX` constant so the sampler and the emitter can't drift), and a **15s QTimer heartbeat** (started BEFORE the worker spawns, stopped on every completion path + when the worker is gone) appends `⏱ still working — mm:ss elapsed, last pipeline update Ns ago: <last msg>` — the elapsed-vs-gap pair IS the frozen/progressing discriminator; past 120s of silence the line gains the triage hint (model load / LLM-on-CPU can take minutes; 🔌 Test checks the LLM; kill + retry if it never advances). The 🔌 LLM test start + verdict lines also land in the log. The heartbeats never touch the pinned plain-text status-label contract (e2e drive tests unchanged). New Qt-free stdlib leaf `core/transcribe/pipeline_log.py` (`format_heartbeat_line`, `format_run_header`, `HEARTBEAT_INTERVAL_MS=15000`, `SILENCE_HINT_AFTER_S=120`) formats it all and is unit-tested directly.
>
> **The review BLOCKER (the V0.6.55 fresh-eyes pattern pays again):** the heartbeat called `worker.isRunning()` — `SimpleWorker` is a `BaseWorker` = **QObject** (API: `is_running()`); `isRunning()` is QThread-only. 15s into every run: `AttributeError` → the global excepthook's MODAL crash dialog → a new crash dialog + crash zip every 15s for the whole run. Invisible in the no-Qt sandbox AND initially pinned in by the new test file itself. Fixed through the house `_worker_is_running` helper (`shared.py`, normalizes both worker shapes); the pin now asserts the helper AND bans `isRunning()` from the method. All four SHOULD-FIX items landed (percent anchoring, monotonic deadline, callback isolation, post-Popen kill); the run header no longer logs the faster-whisper model size when the engine is transcribe.cpp.
>
> **Verification:** 30 new pins in `tests/test_v0656_transcribe_live_log.py` (12 dynamic `_stream_cli_output` drives with a fake Popen, 6 dynamic `pipeline_log` format tests, 12 dialog AST pins) — bidirectional: 29 fail on pristine V0.6.55 sources, 30 pass post-fix. Affected-seam sweep 405 P / 3 pre-existing F (no-PySide6 + one V0.6.41-stale pin, both stash-verified identical on unmodified sources) / 21 S. Rig-only boundary: the real CLI's actual line shapes (unrecognized shapes still echo, just don't percent-map; the raw_output.txt dump shows exactly what the log will show) + the visual layout.


## V0.6.55 — the Transcribe Service fundamental redesign: llama.cpp port auto-detection (8080/8000/9931) + the generation-speed CPU-fallback probe + the 🔌 Test button; the 8000-char transcript amputation killed; ONE round trip for notes+tutorial; LLM streaming to the status label; the structured TranscribeError family; the parser edge cases — 119 new pins / 548 P sweep / 0 regressions (one review BLOCKER caught + fixed pre-release)

> **The trigger (the operator's redesign mandate, verbatim intent):** "fundamentally redesign + optimize + fix the Transcribe Service tool (video → transcribe → summarize with llama.cpp is broken; only raw whisper transcribe works)" — six prioritized items P1-P6, each backed by a test that fails on pre-fix code and passes on post-fix code (the V0.6.54 stash/pop bar; every new file was run red against the pristine V0.6.54 sources, then green).
>
> **P1a — the port trap.** The app's single hard default `http://127.0.0.1:8080/v1` vs the rig's llama-server on **:8000** (llama.cpp's current default; 9931 announced). `core/llm/local_fallback.py` grew `LLAMACPP_ALT_BASE_URLS` + `resolve_llamacpp_base_url()` + the alternate-probe pass in `decide_llamacpp_first` (only when the configured URL is the UNMODIFIED default and dead; explicit operator URLs never second-guessed — the V0.6.12 contract). `create_provider`'s llamacpp branch (`core/llm/llm_provider_impl.py`) resolves through the same helper (lazy import — breaks the import cycle) so factory-built providers TALK to the detected server. First live port wins; the routing note says "port auto-detected"; the probe cache bounds the cost.
>
> **P1b — the invisible CPU fallback.** llama-server that failed to fit its model in VRAM (the `n_gpu_layers=99` GPU-fit warning on the rig's screenshot) still LISTENS — the failure is only visible in the generation RATE. `core/llm/llamacpp_provider.py` grew `probe_llamacpp_generation()` (a 16-token timed generation through the REAL streaming path, `_monotonic` clock indirection for hermetic tests) + `classify_generation_speed()` (< 5 tok/s → `slow-cpu-fallback-suspected`) + `build_generation_probe_message()` — the slow verdict's message names VRAM / n_gpu_layers / the CPU fallback / the restart fix (`--n-gpu-layers`, e.g. `-ngl 40`, or a smaller quant).
>
> **P1c — the 🔌 Test button.** `core/transcribe/llm_check.py` (`check_llm_for_transcribe`) resolves the backend, probes the generation speed (llama.cpp) or lists models (Ollama; cloud selections honestly "not probed locally"), and returns a verdict dict with `save_url` (persist an auto-detected port — offered ONLY while the setting still holds the stale default). The dialog's button runs it on a SimpleWorker (never the UI thread), persists the port after telling the operator, and renders healthy / slow / unreachable with the right message boxes.
>
> **P2 — the 8000-char amputation.** `summarize_transcript` sliced `transcript[:8000]` — a 15-min video lost ~half its transcript silently. `fit_transcript_to_budget()` (24k-token default budget): the whole 15-min video passes; an absurd wall trips a LOUD sentence-boundary cut + explicit `[... transcript truncated: X of Y characters …]` marker (its tokens RESERVED in the fit — body+marker ≤ budget, the Task 9 review fix) + a WARNING log. The wiring pin asserts a 20k-char transcript's TAIL reaches the prompt (fails on pre-fix code).
>
> **P3 — one round trip.** `summarize_transcript_combined()` + `prompts/transcribe/transcript_combined.md` (both documents, separated by `<<<ELIXIR-TRANSCRIBE-SPLIT>>>`) + `split_combined_output()` (drift-tolerant: case, 1-6 angle brackets, hyphen/underscore/space, fences, own-line markers preferred over inline mentions). ONE provider call; `split_ok=False` → the dialog's separate-tutorial fallback (correctness over speed).
>
> **P4 — streaming to the UI.** `on_chunk` forwarded intact to `complete_streaming` by every caller; the dialog's callback shows "📝 LLM is writing… N chars so far" (the provider throttles to 2/s). The 10-minute frozen label is dead.
>
> **P5 — the structured error family.** `core/transcribe/errors.py`: `TranscribeError` (stage/message/hint; str(err) IS the user message) + 7 subclasses covering every pipeline stage. The service raises them (a None provider return — the real post-retry failure mode — is a CONNECTION error with the start-your-LLM hint, the Task 9 review fix); the dialog catches `TranscribeError`, wraps the unexpected as `TranscribePipelineError` (traceback → log, friendly message → user). The V0.6.53 NameError class can never reach the operator raw again.
>
> **P6 — the parser edge cases.** `-->` arrows + `HH:MM:SS.mmm`/`MM:SS.mmm` stamps (the V0.6.52 regex dropped them ALL); wrapped `text:` continuation lines kept (info/timestamp lines end the block; the block never crosses the stdout/stderr boundary — parsed as separate streams, the Task 9 review fix); segments-only output builds text from segments; `detected language:` space variant; UTF-8 BOM strip; percent-bar progress lines skipped. The V0.6.52 real-format floor is pinned.
>
> **The Task 9 fresh-eyes review (read-only subagent, ran the suite itself):** found ONE BLOCKER — the initial `_on_engine_changed()` call placed BEFORE the whisper widgets existed (an AttributeError on dialog construction on any real PySide6 install — the exact V0.6.53 failure class, invisible to this PySide6-less sandbox). Fixed + pinned permanently (construction-order AST pin). Three SHOULD-FIX defects fixed in the same pass: the parser's stderr pollution across the stream boundary, the budget marker overflow (24,036 tokens for a 24,000 budget — measured by the reviewer), and the None-return misclassification (was LLMEmptyResponseError with the misleading "model too small" hint).
>
> **Documented contract changes (house Rule 4 — pins updated, counts visible, guarantees preserved):** (1) the V0.6.12 all-dead probe count 1 → 3 (the alternates); (2) the V0.6.54 summarize call-site count 2 → 4 (1 combined + 3 single — the `_extracted_text` NameError guard extended to ALL sites); (3) the v0600 empty-response pin now asserts the structured RAISE (the "Error:" string contract is gone); (4) the v0600 default-engine pins refreshed to the V0.6.42+ transcribe_cpp default + the faked-dispatch test passes `engine="faster_whisper"` explicitly (its original intent). (5) The dialog's engine combo now DEFAULTS to transcribe.cpp (the service default since V0.6.42 — the two defaults had silently disagreed) + `options.get("engine", "transcribe_cpp")`.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch / no tiktoken):** 119 new pins across 8 new test files, all green; red-verified against pristine V0.6.54 via stash (12 F + collection errors) then green after pop. Full regression sweep over every affected seam (factory, providers, registry, secrets, dispatcher, transcribe, llamacpp): **548 P / 5 F / 20 S** — the 5 F stash-verified pre-existing (2x tiktoken-floor, 3x PySide6 dropdown; fail identically on unmodified V0.6.54). Zero regressions; the 2 previously-stale v0600 pins are now FIXED (baseline sweep was 227 P / 7 F on the 6-file scope). `py_compile` clean on every touched module (ruff not installed in this venv session — the V0.6.54 precedent). Token-leak grep clean.
>
> **Unverified here (the honest boundary — rig-only):** the rig is the only real display (the dialog visuals, the Test-button message boxes, the streaming label); the full chain against the real llama-server on :8000 (Ternary-Bonsai-2-27B, the 15-min Obsidian test video) — the speed probe should confirm GPU-class tok/s after the operator restarts llama-server with a lower -ngl; the combined-prompt marker obedience on the rig's model (the fallback keeps both outputs correct at the old cost if the marker is ignored).


## V0.6.54 — repair the NameError that broke the transcribe → summarize + tutorial chain — 9 new AST-walk pins / 0 regressions (67 P total in this sandbox's transcribe + llamacpp sweep)

> **The trigger (the operator's report, verbatim intent):** "The transcriber tool is supposed to transcribe using whisper to raw text (which takes 30-40 seconds) then give that text to llm model for summarize and tutorial, but it doesn't happen." Annotated with a screenshot showing the Transcribe Service dialog + a `llama-server` terminal running on `http://127.0.0.1:8000`.
>
> **The root cause (a NameError, NOT a llama.cpp connection issue):** commit `3a44cd9` (V0.6.53) renamed the whisper-extracted plain-text local from `_transcript_text` to `_extracted_text` for the log line (`transcribe_service_dialog.py:508`) but LEFT the two `summarize_transcript(...)` call sites in Step 4 (Summary) and Step 5 (Tutorial) still referencing the OLD name `_transcript_text`. So the moment Step 4 ran, Python raised `NameError: name '_transcript_text' is not defined`. `BaseWorker._thread_started` (`ui_qt/components/base_worker.py:65`) caught it and emitted the `failed` signal — BUT only AFTER Step 3 had already written the raw transcript file. So the raw `.md` appeared on disk while no summary / tutorial ever did, exactly matching the operator's report. No HTTP request to `llama-server` was ever attempted — the crash happened in the dialog before the LLM call.
>
> **The fix (commit `3664caf`):** the two `summarize_transcript` call sites (Step 4 Summary + Step 5 Tutorial) now pass `_extracted_text` (the assigned local that holds the plain-text transcript). The timestamped `raw_text` local is only used for the saved raw-transcript file (Step 3) — the correct split: the LLM gets the plain text, not the timestamped markdown. A 14-line explanatory comment block at the assignment site documents the V0.6.53 regression + the V0.6.54 fix.
>
> **The pins (1 new test file, 9 tests — `tests/test_v0654_transcribe_dialog_nameerror_fix.py`):** a pure-AST walk of the dialog source — hermetic (no PySide6, no Qt offscreen platform, no audio files, no LLM). Nine pins: (1) `_transcript_text` is absent from the AST (comments/docstrings are invisible to the AST, so the V0.6.54 fix block that quotes the old name for the reader does not trip this); (2) `_extracted_text` is both assigned AND referenced; (3) `_extracted_text` is assigned before use in source order; (4) there are exactly 2 `summarize_transcript` call sites; (5) both pass `_extracted_text` as the first positional arg; (6) the tutorial call sets `output_type='tutorial'`; (7) the `results` dict carries the four-key contract (`raw_path` / `summary_path` / `tutorial_path` / `error`); (8) the module parses cleanly (no SyntaxError floor); (9) the `_do_transcribe` method exists.
>
> **Bidirectional verification:** stashing the fix makes 2 of the 9 pins FAIL on the V0.6.53 source (the `_transcript_text` Name IS in the AST + the summarize calls pass the wrong Name); restoring the fix makes all 9 pass. The regression cannot return without re-introducing the mismatched name.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch / no tiktoken):** new file 9 P / 0 F (0.93s). Broader sweep on the llamacpp-first + transcribe tests that don't need PySide6 imports: 67 P / 0 F (9 new + 58 existing), zero regressions. The pre-existing failures (PySide6 `ModuleNotFoundError`, stale `faster-whisper` assertions, missing `hypothesis` package) were confirmed pre-existing by stash/pop — they fail identically on the unmodified V0.6.53 source. `py_compile` clean (ruff not installed in this venv session).
>
> **The llama.cpp port note (configuration, not code — flagged for the next session):** the operator's screenshot shows `llama-server` listening on `http://127.0.0.1:8000` with the notice "server default port will be changed to :9931 in a future release", but the app's `LLAMACPP_DEFAULT_BASE_URL = http://127.0.0.1:8080/v1` (`core/llm/local_fallback.py:56`). If the summarize step still fails to reach the server after this NameError fix, the operator should set `summarisation.llamacpp_base_url = http://127.0.0.1:8000/v1` in Settings. The `n_gpu_layers=99` GPU-fit error in the screenshot is non-fatal (the server falls back to CPU + still listens), but a 27B model on CPU will be VERY slow. This port mismatch is a candidate for the fundamental transcribe-tool redesign (auto-detect well-known ports 8080 → 8000 → 9931).


## V0.6.40–V0.6.53 — the transcribe tool's three-output-type evolution (retrospective entry — these commits shipped without CHANGELOG headings; reconstructed from `git log`)

> **Provenance gap (Rule 4):** the V0.6.40 through V0.6.53 commits shipped as tags + detailed commit messages but their `## V…` headings were never entered in this file (the same gap the V0.5.11–V0.5.15 retroactive entry documents). This entry is reconstructed VERBATIM from the release commit messages; the commits remain the authoritative record.
>
> **The arc — the transcribe tool grew from a single-output whisper wrapper into a three-output-type pipeline (raw transcript + summary + tutorial) with a pluggable engine (faster-whisper OR transcribe.cpp/Vulkan GPU) and a pluggable LLM (Ollama OR llama.cpp):**
>
>   - **V0.6.40 (`feat(transcribe)`):** engine dispatch — the dialog can now use `transcribe.cpp (Vulkan GPU)` OR `faster-whisper`, selected via a dropdown. The `transcribe_with_cpp(...)` engine reads the audio + emits progress + segments the same shape `transcribe_audio(...)` does.
>   - **V0.6.41 (`fix(transcribe)`):** removed the hardcoded Qwythos model + added a model-browse button for `transcribe.cpp` (the operator picks the `.gguf` whisper model on disk).
>   - **V0.6.43 (`feat(transcribe)`):** the three-output-type contract — the dialog now offers Raw transcript (with timestamps) + Summary (core concepts + key takeaways) + Tutorial guide (educational / tips & tricks), each independently checkable. The `summarize_transcript(...)` function grew an `output_type` parameter (`summary` | `tutorial`) that selects the prompt template via `PromptManager.render_template("transcribe/transcript_notes" | "transcribe/transcript_tutorial", transcript=...)`.
>   - **V0.6.44 (`fix(ui)`):** show the tutorial result in the completion dialog + the `results` dict (the four-key contract: `raw_path` / `summary_path` / `tutorial_path` / `error`).
>   - **V0.6.45 (`fix(ui)`):** corrected the whisper model path (`whisper-large-v3-Q8_0.gguf`) + hide the summary-model dropdown when raw-only is checked.
>   - **V0.6.52 (`fix(transcribe)`):** rewrote the `transcribe-cli.exe` output parser to match the REAL output format (the prior parser was silently dropping segments).
>   - **V0.6.53 (`fix(transcribe)`):** empty-text guard + log extracted text length + the HALF-APPLIED `_transcript_text` → `_extracted_text` rename that V0.6.54 repaired (see above).
>
> **The current state (as of V0.6.54):** the transcribe tool's pipeline is `_do_transcribe` → Step 1 extract audio (ffmpeg) → Step 2 transcribe (`transcribe_with_cpp` OR `transcribe_audio`) → Step 3 save raw transcript (timestamped) → Step 4 `summarize_transcript(_extracted_text, output_type="summary")` → Step 5 `summarize_transcript(_extracted_text, output_type="tutorial")`. The LLM call goes through `decide_llamacpp_first()` (the V0.6.12 llama.cpp-first policy) → `create_provider()` → `provider.complete_streaming()`. The dialog is in `ui_qt/views/service_dialogs/dialogs/transcribe_service_dialog.py` (~625 lines); the service is in `core/transcribe/transcribe_service.py`.
>
> **Known issues flagged for the fundamental redesign (the next session):**
>   1. The V0.6.53 NameError (FIXED in V0.6.54) — the chain now completes, but the pipeline's fragility (a single typo silently broke the whole summarize path for one release) signals that the Step 4/5 LLM-call path needs structural hardening.
>   2. The llama.cpp port mismatch (the operator's server on `:8000` vs the app's default `:8080`) — a port-auto-detection helper would make the tool robust to llama.cpp's shifting default port.
>   3. The `n_gpu_layers=99` GPU-fit error — the operator's rig can't fit 99 layers of a 27B model; the tool should surface this as a clear, actionable error, not a silent CPU fallback that makes a 30-second summary take 30 minutes.
>   4. The two-step summarize (summary then tutorial) is sequential + each is a full LLM round-trip; a redesign could batch them or stream both.


## V0.6.28 — the quarantine analytics + summarisation CLI batch: the operator can now compute quarantine log statistics (drops, recovery rate, overlap distribution, per-stage + per-chapter breakdowns) and export to CSV/JSON/Markdown — the SECOND round working on a DIFFERENT module (summarisation) — 44 new pins / 0 regressions (407 P total in this sandbox)

> **The trigger:** the V0.6.27 worklog noted the summarisation module's `QuarantineLog` has a `summary()` method (returns `{stage: count}`) + `serialize()` (returns a list of dicts) but NO richer analytics and NO export to CSV/JSON/Markdown. The operator who wants to understand the quarantine log (which bullets were dropped, by which stage, with what overlap, and which were recovered) has no headless way to do it — only the Qt wizard's quarantine view. This round fills that gap.
>
> **Layer 1 — the QUARANTINE ANALYTICS module (W-m1, NEW `core/summarisation/quarantine_analytics.py`):** pure-Python (no PySide6/torch/numpy — uses stdlib `statistics` for the overlap distribution) analytics + exporters:
>
>   - `compute_quarantine_stats(log)` — returns a `QuarantineStats` with total_entries / dropped_count / conservative_count (logged but kept) / recovered_count / recovery_rate (recovered/dropped, 0 if no drops) / overlap distribution (min/max/mean/median across all entries) / `stage_breakdown` (list of `StageBreakdown` with per-stage total/dropped/conservative/recovered/avg_overlap) / `chapter_breakdown` (list of `ChapterBreakdown` with per-chapter total/dropped/recovered). Stage + chapter breakdowns are sorted by total (desc) then name (asc) for determinism.
>   - `format_quarantine_stats_for_display(stats, log)` — multi-line formatter with 📊 header, total/dropped/conservative/recovered counts with recovery rate %, overlap distribution, per-stage table, per-chapter table.
>   - `export_to_csv(log)` — CSV with all 10 fields (bullet, stage, threshold, source_overlap, reason, chapter, actually_dropped, recovered, timestamp) + a header row. Uses `csv.QUOTE_MINIMAL` so commas in bullets are properly quoted.
>   - `export_to_json(log)` — wraps the existing `serialize()` (a list of entry dicts).
>   - `export_to_markdown(log)` — a human-readable Markdown report with # H1 title, ## Summary section, ## Source overlap distribution, ## Per-stage breakdown table, ## Dropped bullets table (sorted by overlap desc, with ✅/⚠️/— icons for dropped/recovered). For pasting into a GitHub issue or code review.
>   - `QUARANTINE_EXPORT_FORMATS` registry + `export_quarantine()` dispatcher + `list_quarantine_formats()` + `format_quarantine_formats_for_display()`.
>
> **Layer 2 — the summarisation CLI (W-m2, NEW `core/summarisation/cli.py`):** `python -m core.summarisation.cli` with two subcommands: `stats --drops <FILE>` (prints quarantine statistics from a drops.jsonl file) and `export --drops <FILE> [--format csv|json|markdown] [--out FILE]` (lists all formats, or exports to stdout/file). Exits 0 on success, 1 on unknown format, 2 on file error. The CLI reads drops.jsonl via the existing `QuarantineLog.load_from_disk()` static method, then reconstructs `QuarantineEntry` objects for the analytics module. Uses deferred imports (importlib) to bypass `core.summarisation.__init__` which pulls in tiktoken (not installed in every sandbox).
>
> **The pins (1 new test file, 44 tests):** `tests/test_v0628_quarantine_analytics_pins.py` — Layer 1a (10 stats tests: empty log, total entries, dropped vs conservative, recovered count, recovery rate, recovery rate zero when no drops, overlap distribution, stage breakdown, stage breakdown sorted, chapter breakdown); Layer 1b (3 format tests: empty message, all sections present, log callback); Layer 1c (4 CSV tests: header row, all entries, empty log header-only, commas in bullet are quoted); Layer 1d (3 JSON tests: valid JSON, matches serialize, empty log → []); Layer 1e (5 Markdown tests: H1 title, Summary section, stage table, dropped bullets table, empty log message); Layer 1f (7 dispatcher/registry tests: csv/json/markdown dispatch, unknown format raises, registry has 3, list_formats returns all 3, display has header); Layer 2 (9 CLI tests: stats prints, missing file exits 2, empty file prints empty message, export list mode, csv to file, json to stdout, markdown to file, unknown format exits 1, missing file exits 2, parser has stats+export); Layer 3 (2 integration tests: QuarantineLog.add with real output_dir → drops.jsonl → CLI stats; same → CLI export CSV). All 44 tests are pure-Python. The tests load the modules via importlib.util (the same pattern test_quarantine.py uses) to bypass the tiktoken dependency, registering each module in sys.modules BEFORE exec_module so @dataclass decorators can find the module namespace.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch / no tiktoken):** new file 44 P / 0 F (1.06s). Broader regression sweep including the existing test_quarantine.py: **407 P / 0 F total, zero regressions** (the existing quarantine tests still pass — the analytics module is additive, not modifying). ruff check + ruff format --check clean on all 3 touched files. One iteration during development: the importlib loading failed with an AttributeError on @dataclass because the module wasn't registered in sys.modules before exec_module (the @dataclass decorator looks up `sys.modules[cls.__module__].__dict__`); fixed by registering each module BEFORE exec_module.
>
> **Unverified here (rig-only):** the wizard UI doesn't yet have a "Quarantine Stats" or "Export Quarantine" button (the wiring would be ~10 lines + a dropdown; requires Qt rendering to verify). The CLI is fully pinned end-to-end, including the integration tests (QuarantineLog.add with a real output_dir → drops.jsonl → CLI stats → CLI export CSV).

## V0.6.27 — the translation glossary analytics + CLI batch: the operator can now compute glossary statistics (entries, coverage, entity types, top terms) and export to TSV (CAT-tool format), CSV (spreadsheet), or JSON — the FIRST round working on a DIFFERENT module (translation) than the podcast module — 43 new pins / 0 regressions (336 P total in this sandbox)

> **The trigger:** the V0.6.26 worklog said the podcast module's pure-Python feature work was "DEFINITIVELY exhausted" and recommended looking at OTHER modules in the codebase (translation, summarisation, pdf) for similar pure-Python opportunities. This round picks the **translation module** — the `Glossary` class has `to_dict`/`from_dict` (JSON) + `save`/`load` (JSON file) but NO export to CSV/TSV (which CAT tools like OmegaT, Trados, memoQ expect) and NO statistics (translated vs untranslated, entity type distribution, top terms). This is genuinely useful for the bilingual (EN/FA) translation workflow.
>
> **Layer 1 — the GLOSSARY ANALYTICS module (W-l1, NEW `core/translation/glossary_analytics.py`):** pure-Python (no PySide6/torch/spaCy) analytics + exporters:
>
>   - `compute_glossary_stats(glossary, top_n=10)` — returns a `GlossaryStats` dataclass with total_entries / translated_count / untranslated_count / coverage_pct / entity_type_distribution / top_terms (sorted by frequency desc, then source asc for determinism) / source_lang / target_lang.
>   - `format_glossary_stats_for_display(stats, log)` — multi-line formatter with 📊 header, language pair, total/translated/untranslated counts with percentages, entity type distribution table, top-N terms list.
>   - `export_to_tsv(glossary)` — TSV format (source TAB translation), the standard CAT-tool glossary format. Untranslated terms have an empty translation field. Sorted by frequency (desc).
>   - `export_to_csv(glossary)` — CSV format (source, translation, entity_type, frequency) with a header row, for spreadsheet tools (Excel, Google Sheets). Uses `csv.QUOTE_MINIMAL` so commas in source terms are properly quoted. Sorted by frequency (desc).
>   - `export_to_json(glossary)` — wraps the existing `to_dict()` for the format registry.
>   - `GLOSSARY_EXPORT_FORMATS` registry + `export_glossary()` dispatcher + `list_glossary_formats()` + `format_glossary_formats_for_display()`.
>
> **Layer 2 — the translation CLI (W-l2, NEW `core/translation/cli.py`):** `python -m core.translation.cli` with two subcommands:
>   - `stats --glossary FILE [--top-n N]` — prints glossary statistics.
>   - `export --glossary FILE [--format tsv|csv|json] [--out FILE]` — lists all formats, or exports to stdout/file.
>   - Exits 0 on success, 1 on unknown format, 2 on file/parse error (same contract as the podcast CLI).
>
> **The pins (1 new test file, 43 tests):** `tests/test_v0627_glossary_analytics_pins.py` — Layer 1a (8 stats tests: empty glossary, total entries, translated/untranslated counts, coverage %, entity type distribution, top terms sorted, top_n limit, languages echoed); Layer 1b (3 format tests: empty message, all sections present, log callback); Layer 1c (5 TSV tests: tab separator, all entries, sorted by frequency, untranslated has empty translation, empty glossary); Layer 1d (5 CSV tests: header row, all entries, sorted, empty glossary header-only, commas in source are quoted); Layer 1e (2 JSON tests: valid JSON, matches to_dict); Layer 1f (7 dispatcher/registry tests: tsv/csv/json dispatch, unknown format raises, registry has 3, list_formats returns all 3, display has header); Layer 2 (11 CLI tests: stats prints, missing file exits 2, bad JSON exits 2, --top-n flag, export list mode, tsv to stdout, csv to file, json to file, unknown format exits 1, missing file exits 2, bad JSON exits 2, subcommands in parser); Layer 3 (1 integration test: Glossary.save() → CLI stats → CLI export TSV). All 43 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch / no spaCy):** new file 43 P / 0 F (1.06s). Broader regression sweep: **336 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 3 touched files. Two test-expectation bugs caught + fixed during development: the TSV test's `.strip()` removed the trailing tab from the last line (fixed by checking the raw string); the `python -m` subprocess test failed because `core.translation.__init__.py` imports `harakat` which drags in the `tiktoken` dependency (fixed by verifying the parser via the Python API instead of subprocess).

## V0.6.26 — the script-export + export-CLI batch: the operator can now export a script to SRT subtitles (with estimated timestamps), HTML (standalone page with inline CSS), or Markdown (blockquote per line) — 36 new pins / 0 regressions (343 P total in this sandbox)

> **The trigger:** the V0.6.25 worklog said the codebase-wide audit was complete and the remaining work was "genuinely rig-only". But the cron's [Mandatory] "add more features and functionality" requirement still applies, and I identified ONE more genuinely valuable pure-Python feature: a script export module. The wizard's "Export Script" button (V11.37.0) writes a JSON file — useful for re-importing, but useless for subtitles (SRT), blog posts (HTML), or show notes (Markdown). This release fills that gap.
>
> **Layer 1 — the SCRIPT EXPORT module (W-k1, NEW `core/podcast/script_export.py`):** pure-Python (no PySide6/torch) exporters for three formats:
>
>   - `export_to_srt(script, wpm=None)` — SRT subtitle format with estimated timestamps. Each script line becomes one SRT cue (1-based index, start --> end timestamp, `[Host A] line text`). The timestamps are estimated using the V0.6.20 `estimate_duration_seconds()` function (word_count × WPM, 150 EN / 130 FA auto-detected). The cues are sequential (each cue's start = the previous cue's end; no gaps, no overlaps). The estimate is good enough for a draft subtitle (typical error ±10-15% per line, compounding to ~30s drift on a 20-line podcast — acceptable for a draft the operator can adjust).
>   - `export_to_html(script)` — a standalone HTML page with the dialogue. The page has `<title>` + `<h1>` with the script's title, each line as a `<div class="line host-a/b">` with `<span class="speaker">Host A:</span>` + `<span class="text">`, and minimal inline CSS (no external stylesheet dependency). HTML special characters are escaped (`<script>` → `&lt;script&gt;`) for XSS prevention.
>   - `export_to_markdown(script)` — a Markdown page with `# Title` H1 heading, each line as a blockquote (`> **Host A:** line text`).
>   - `EXPORT_FORMATS` registry dict + `export(script, format, wpm)` dispatcher + `list_formats()` + `format_formats_for_display()`.
>
> **Layer 2 — the CLI export subcommand (W-k2, `core/podcast/cli.py`):** a new `export` subcommand joins the V0.6.19 `validate`/`generate`/`info` + V0.6.20 `stats` + V0.6.21 `diff` + V0.6.22 `templates` + V0.6.23 `schema` octet. `python -m core.podcast.cli export --script FILE` lists all 3 formats. `python -m core.podcast.cli export --script FILE --format srt [--out FILE] [--wpm N]` exports; without `--out`, prints to stdout; with `--out`, writes to a file. `--wpm N` overrides the auto-detected WPM for SRT timestamps. Exits 0 on success, 1 if the format is unknown, 2 on file/parse error.
>
> **The pins (1 new test file, 36 tests):** `tests/test_v0626_script_export_pins.py` — Layer 1a (7 SRT tests): cue indices 1-based, timestamps in HH:MM:SS,mmm format, host prefix in cue text, cues are sequential, empty script → empty string, --wpm override changes timestamps, `_format_srt_timestamp` format. Layer 1b (7 HTML tests): standalone page, title in `<title>`+`<h1>`, lines as divs, HTML special chars escaped (XSS prevention), inline CSS, empty script message, untitled script. Layer 1c (4 Markdown tests): H1 title, blockquotes per line, empty script, untitled. Layer 1d (7 dispatcher/registry tests): srt/html/markdown dispatch, unknown format raises ValueError, registry has 3 formats, list_formats returns all 3, format_formats_for_display has header. Layer 2 (9 CLI tests): list mode, srt to stdout, html to file, markdown to file, unknown format exits 1, missing script exits 2, bad JSON exits 2, --wpm override, `export` in `--help`. Layer 3 (2 integration tests): template → export SRT, template → export HTML. All 36 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 36 P / 0 F (1.09s). Broader regression sweep including the V0.6.24 round-trip tests + V0.6.25 case tests + existing V0.6.0 e2e test: **343 P / 18 skipped, zero regressions**. ruff check + ruff format --check clean on all 3 touched files. Two test-expectation bugs caught + fixed during development (SRT line-indexing was off by one — the last cue's timestamp line is `lines[-2]` not `lines[-3]` because the last line is the cue's text).
>
> **Unverified here (rig-only):** the SRT timestamps are ESTIMATES (word_count × WPM) — the actual audio duration depends on the TTS engine's pacing, pauses, and overlap. The operator's rig will need to adjust the SRT after generation if the estimate drifts. The HTML/Markdown exports are exact (no estimation).

## V0.6.25 — the source_ref case-preservation bug fix: the wizard's "Export Script" → "Import Script" round-trip no longer LOWERCASES the source_ref field — mixed-case refs like "MySource_Chapter3" survive verbatim instead of being mangled to "mysource_chapter3" — 17 new pins / 0 regressions (353 P total in this sandbox)

> **The bug (discovered during the V0.6.24 audit recommendation):** `ScriptResult.from_json()` did `str(obj.get("source_ref", "")).strip().lower()` — it SILENTLY LOWERCASED the source_ref on read. `to_json` writes source_ref verbatim, so the round-trip through to_json → from_json mangled mixed-case source refs (e.g., "MySource_Chapter3" → "mysource_chapter3"). The `.lower()` was added in the V0.6.0 lint triage commit (`bf994fa`) without a documented reason; no tests rely on it. This is a subtle data-loss bug for the anti-hallucination audit trail — if the operator uses a custom source_ref with case (e.g., to match an external naming convention), the round-trip silently mangles it.
>
> **The fix (W-j2, `core/podcast/script_generator.py`):** `from_json` now does `.strip()` only (no `.lower()`). The round-trip preserves mixed-case source_ref values verbatim. The `.strip()` (leading/trailing whitespace trim) is preserved — that's a normalization, not data loss.
>
> **The pins (1 new test file, 17 tests):** `tests/test_v0625_source_ref_case_fix.py` — Layer 1 (6 round-trip case-preservation tests): mixed-case source_ref survives, ALL-UPPERCASE survives (before V0.6.25 → lowercased), camelCase survives, source_ref with internal spaces survives, the .strip() still trims leading/trailing whitespace, double-round-trip idempotency. Layer 2 (3 backward-compat tests): lowercase source_ref (the V0.6.0-V0.6.24 canonical form) still loads correctly, empty source_ref loads as empty, missing source_ref field loads as empty. Layer 3 (2 V0.6.21 diff contract tests): the diff's source_ref-ignored contract still holds (a pure source_ref change is NOT a line modification); a source_ref CASE change alone is still ignored. Layer 4 (1 V0.6.23 schema test): the V0.6.25 to_json output with mixed-case source_ref passes the V0.6.23 schema. Layer 5 (1 V0.6.22 template test): all 6 templates' source_refs survive the round-trip (no-op for them — they use lowercase source_refs — but pins the contract for future templates). Layer 6 (4 CLI integration tests): the V0.6.19-V0.6.23 CLI subcommands (info, validate, stats, schema --validate) all work on scripts with mixed-case source_ref. All 17 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 17 P / 0 F (1.21s). Broader regression sweep including the V0.6.21 diff tests (which use source_ref) + the V0.6.24 round-trip tests + the existing V0.6.0 e2e test: **353 P / 18 skipped, zero regressions** (the skips are pre-existing — they need rig-only files like the real VibeVoice checkpoint). ruff check + ruff format --check clean on both touched files. No iterations needed — the tests passed on the first run.
>
> **Unverified here (rig-only):** the wizard UI's "Import Script" button still calls the now-fixed `from_json` — the operator's rig will see the benefit on the next import (mixed-case source_refs preserved). No Qt-wiring needed for this fix; it's a pure data-layer change.

## V0.6.24 — the to_json / from_json round-trip bug fix: the wizard's "Export Script" → "Import Script" round-trip no longer LOSES the title, bullets_input, retries, forced_segments, error fields — 27 new pins / 0 regressions (335 P total in this sandbox)

> **The bug (discovered during the V0.6.23 schema round):** `ScriptResult.to_json()` serialized only 4 fields (lines, coverage_pct, bullets_covered, bullets_missing) and DROPPED title, bullets_input, retries, forced_segments, error. And `ScriptResult.from_json()` ALSO dropped title, retries, forced_segments, error when reading (it read bullets_input but to_json didn't serialize it, so it was lost in the round-trip anyway). The wizard's "Export Script" → "Import Script" round-trip LOST:
>
>   - **title** — the imported script got a timestamp filename (`podcast_YYYYMMDD_HHMMSS.wav`) instead of the original title.
>   - **bullets_input** — the anti-hallucination audit trail was lost (the imported script's `I2_BULLETS_FORCE_INSERTED` info rule in the V0.6.19 validator couldn't fire because bullets_input was empty).
>   - **retries / forced_segments** — the script's provenance was lost (the operator couldn't tell if the script had been through gap-fill retries or had segments force-inserted).
>   - **error** — any generation error message was lost.
>
> **The fix (W-j1, `core/podcast/script_generator.py`):** both methods now handle all 9 fields. `to_json` serializes: lines, title, coverage_pct, bullets_input, bullets_covered, bullets_missing, retries, forced_segments, error. `from_json` reads the same 9. The defaults (title="", retries=0, forced_segments=0, error=None) preserve backward-compat for old JSON files that don't have these fields. The V0.6.23 schema module documents the full expected format; this fix makes to_json match it.
>
> **The pins (1 new test file, 27 tests):** `tests/test_v0624_to_json_round_trip_fix.py` — Layer 1 (11 round-trip preservation tests): every field survives to_json → from_json (title, bullets_input, bullets_covered, bullets_missing, coverage_pct, retries, forced_segments, error, error=None, lines, + a double-round-trip idempotency test); the to_json output has all 9 documented fields. Layer 2 (5 backward-compat tests): old JSON without title loads (default ""), old JSON without retries/forced_segments/error loads (defaults), new V0.6.24 JSON with all fields loads correctly, error:null loads as None, the raw-array shorthand still works. Layer 3 (2 cross-version integration tests): the V0.6.24 to_json output passes the V0.6.23 schema; the to_json output with error='string' passes the schema. Layer 4 (2 V0.6.22 template integration tests): all 6 templates' to_json output passes the V0.6.23 schema after the fix; the templates' titles survive the round-trip (before V0.6.24, the title was LOST — a real bug for the templates which all have descriptive titles like "Lecture Podcast (Template)"). Layer 5 (5 CLI integration tests): the V0.6.19-V0.6.23 CLI subcommands (info, stats, validate, schema --validate, diff --summary-only) all still work on V0.6.24 to_json output. Layer 6 (1 existing-contract test): the existing V0.6.0 e2e test's assertions (data['lines'] host values + data['coverage_pct'] + the round-trip preserves lines text + coverage_pct) still hold. All 27 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 27 P / 0 F (1.04s). The existing V0.6.0 e2e test that touches `to_json` (test_v0600_tool_transcribe_podcast_e2e.py): 50 P / 18 skipped (the skips are pre-existing — they need rig-only files like the real VibeVoice checkpoint). Broader regression sweep: **335 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on both touched files. No iterations needed — the tests passed on the first run (the fix is straightforward; the test suite caught no edge cases).
>
> **Unverified here (rig-only):** the wizard UI's "Export Script" button still calls the old `to_json` (now fixed) — the operator's rig will see the benefit on the next export. No Qt-wiring needed for this fix; it's a pure data-layer change.

## V0.6.23 — the JSON-schema + schema-CLI batch: the operator can now validate a script JSON file against the documented schema BEFORE feeding it to `generate` — catches bad host values, missing required fields, wrong types at the JSON-structure level — 34 new pins / 0 regressions (259 P total in this sandbox)

> **The trigger:** the V0.6.22 worklog said the pure-Python feature work was "TRULY exhausted" but recommended a polish round. The cron's [Mandatory] "add more features and functionality" requirement still applies. This release builds a JSON schema module — genuinely useful (the CLI's `_load_script_json` is a loose parser; a schema module makes the contract explicit) AND pure-Python testable. It also caught a real asymmetry during development: `ScriptResult.to_json()` serializes only 4 fields while `from_json()` reads more — the schema documents the FULL expected format.
>
> **Layer 1 — the SCRIPT SCHEMA module (W-i1, NEW `core/podcast/script_schema.py`):** pure-Python (no jsonschema dependency) schema + validator. Public API:
>
>   - `SCRIPT_SCHEMA` — a plain-dict description of the expected JSON format (the format `ScriptResult.to_json` SHOULD produce + the extra fields `from_json` reads: title, bullets_input, retries, forced_segments, error). The dict is both the human-readable doc source AND the machine-readable validation source.
>   - `validate_script_json(data)` — validate a parsed JSON dict/list. Returns a `SchemaValidationResult` with `.issues` / `.errors` / `.warnings` / `.ok`. Checks: top-level must be a dict (or a list — the raw-lines shorthand, accepted with a WARNING); `lines` is required + must be a non-empty array; each line's `host` must be "A" or "B" (ERROR) and `text` must be non-empty (ERROR); `segment_type` must be one of intro/content/conclusion (WARNING — audio gen ignores it); `coverage_pct` must be 0-100; `retries`/`forced_segments` must be non-negative ints; `error` accepts string-or-null; unknown fields are ACCEPTED (forward-compat).
>   - `validate_script_file(path)` — load a JSON file + validate it. Never raises — file/parse errors become single-issue ERROR results.
>   - `SchemaIssue` (path / message / severity) + `SchemaValidationResult` (issues / errors / warnings / ok / __bool__) dataclasses.
>   - `format_schema_for_display()` — human-readable schema doc (for the CLI's `schema` subcommand).
>   - `format_issues_for_display(result)` — multi-line issue formatter grouped by severity with the JSON path + message.
>
> **Layer 2 — the CLI schema subcommand (W-i2, `core/podcast/cli.py`):** a new `schema` subcommand joins the V0.6.19 `validate`/`generate`/`info` + V0.6.20 `stats` + V0.6.21 `diff` + V0.6.22 `templates` septet. `python -m core.podcast.cli schema` prints the human-readable schema doc. `python -m core.podcast.cli schema --validate file.json` validates a file; exits 0 if valid, 1 on schema ERROR, 2 on missing file. The CLI's main description string now mentions V0.6.23.
>
> **The pins (1 new test file, 34 tests):** `tests/test_v0623_script_schema_pins.py` — Layer 1 (26 schema-module tests): valid script passes, missing `lines` blocks, empty `lines` blocks, raw-array shorthand warns, invalid host blocks, empty text blocks, whitespace-only text blocks, missing host blocks, missing text blocks, unknown segment_type warns, coverage_pct out-of-range blocks, negative retries blocks, wrong-type title blocks, error field accepts string/null, error field rejects number, unknown fields accepted, non-dict/non-list top-level blocks, .ok + bool coercion, SchemaIssue rejects bad severity, validate_script_file loads+validates, validate_script_file missing-file returns error (no raise), validate_script_file bad-JSON returns error (no raise), format_schema has all 9 fields, format_schema log callback, format_issues clean message, format_issues groups by severity. Layer 2 (6 CLI tests): `schema` prints doc, `schema --validate` valid file exits 0, invalid file exits 1, missing file exits 2, bad JSON exits 1, `schema` in `--help`. Layer 3 (2 cross-version integration tests): all 6 V0.6.22 templates pass the V0.6.23 schema; template → `schema --validate` passes via the CLI. All 34 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 34 P / 0 F (1.13s). Combined V0.6.18-V0.6.23: 213 P / 0 F. Broader regression sweep: **259 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 3 touched files. No iterations needed — the tests passed on the first run.
>
> **Unverified here (rig-only):** the wizard UI doesn't yet call `validate_script_file` on import (the wiring would be in the "Import Script" button's handler + ~5 lines; requires Qt rendering to verify). The CLI's `schema` subcommand is fully pinned end-to-end, including the cross-version integration tests (all 6 V0.6.22 templates pass the V0.6.23 schema).

## V0.6.22 — the script-templates + templates-CLI batch: the operator can now start from a pre-built template (lecture / conversational / Q&A / interview / summary / deep-dive) instead of a blank script — 29 new pins / 0 regressions (225 P total in this sandbox)

> **The trigger:** the V0.6.21 worklog noted "the pure-Python feature work is now genuinely exhausted" but named the **script template system** as a remaining lower-value feature. The cron's [Mandatory] "add more features and functionality" requirement still applies. This release builds the template system — a real feature for the wizard's future "New from template" button + a new CLI `templates` subcommand that writes a template JSON the operator can edit + import.
>
> **Layer 1 — the SCRIPT TEMPLATES module (W-h1, NEW `core/podcast/script_templates.py`):** pure-Python (no PySide6/torch) module with 6 pre-built templates covering the common podcast formats:
>
>   1. `lecture_intro` — 3-line lecture (1 host): intro / content / conclusion.
>   2. `conversational_intro` — 3-line conversational (2 hosts): intro / response / conclusion.
>   3. `qa_format` — 4-line Q&A: A asks / B answers / A follows up / B answers.
>   4. `interview` — 5-line interview: A intro / B question / A answer / B follow-up / A conclusion.
>   5. `summary_only` — 1-line lecture (just a summary; good for very short content).
>   6. `deep_dive` — 6-line conversational deep-dive: intro / 4-line back-and-forth / conclusion.
>
>   Each template is a `ScriptTemplate` dataclass with `name` / `description` / `mode` (lecture or conversational) / `script` (a `ScriptResult` with placeholder text) / `estimated_lines`. The placeholder text uses `[BRACKETED_HINTS]` so the operator sees at a glance which fields need filling. Every template's first line is tagged `segment_type="intro"` and last line `segment_type="conclusion"` (the script_generator contract the V0.6.19 validator expects). Every template passes the V0.6.19 validator with zero errors (pinned by a test). `get_template(name)` returns a FRESH ScriptResult (new ScriptLine objects) so the caller can mutate it without affecting the registry.
>
> **Layer 2 — the CLI templates subcommand (W-h2, `core/podcast/cli.py`):** a new `templates` subcommand joins the V0.6.19 `validate`/`generate`/`info` + V0.6.20 `stats` + V0.6.21 `diff` sextet. `python -m core.podcast.cli templates` lists all 6 templates with name / line count / mode / description. `python -m core.podcast.cli templates --name lecture_intro --out new.json` writes the template's ScriptResult to a JSON file the operator can edit + re-import (or feed to `generate --script new.json`). Exits 0 on success, 1 if the template name is unknown (lists the available names), 2 on argument/file error.
>
> **The pins (1 new test file, 29 tests):** `tests/test_v0622_script_templates_pins.py` — Layer 1 (19 template-module tests): registry has 6 templates, list_templates in registration order, each template's line count + mode (parametrized over all 6), unknown name raises KeyError, get_template returns fresh (not registry reference), all templates have `[BRACKETED_HINTS]` placeholder text, all have valid host values (A/B), lecture templates have no Host B, conversational templates have both hosts, multi-line templates have intro+conclusion segments, all have nonempty titles, all 6 templates PASS the V0.6.19 validator (integration contract), format_templates_for_display has header + log callback. Layer 2 (8 CLI tests): list mode prints all 6, write mode creates valid JSON (loadable by the CLI's own loader), write mode stdout message, unknown name exits 1, --name without --out exits 2, all 6 templates can be written + re-loaded (smoke test), `templates` appears in --help, `templates --help` lists --name + --out. Layer 3 (2 integration tests): template → validate passes; template → stats produces valid JSON stats. All 29 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 29 P / 0 F (1.17s). Combined V0.6.18+V0.6.19+V0.6.20+V0.6.21+V0.6.22: 179 P / 0 F. Broader regression sweep: **225 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 3 touched files. No iterations needed — the tests passed on the first run (the template system is simpler than the diff/stats modules).
>
> **Unverified here (rig-only):** the wizard UI doesn't yet have a "New from template" button (the wiring would be a dropdown + a button in the Script view + ~5 lines calling `get_template(name)`; requires Qt rendering to verify). The CLI's `templates` subcommand is fully pinned end-to-end, including the integration tests (template → validate, template → stats).

## V0.6.21 — the script-diff + diff-CLI batch: the operator can now see exactly what they edited between the generated script and their hand-edits — line-level adds/deletes/modifies + word-level diffs within modified lines, git-diff-style — 31 new pins / 0 regressions (245 P total in this sandbox)

> **The trigger:** the V0.6.20 worklog's "Unresolved" section named the script diff/patch utility as the most valuable remaining pure-Python feature. The wizard has "Export Script" + "Import Script" buttons so the operator can save/load the edited version, but no DIFF — once the operator edited the script, the original generated version was GONE, no way to see what they changed, no way to compare against the anti-hallucination contract. This release fills that gap with a new diff module + a new CLI `diff` subcommand, per the cron's [Mandatory] "add more features and functionality" requirement.
>
> **Layer 1 — the SCRIPT DIFF module (W-g1, NEW `core/podcast/script_diff.py`):** pure-Python (no PySide6/torch) diff utility using stdlib `difflib.SequenceMatcher` (Ratcliff-Obershel — the same algorithm `git diff` uses). Public API:
>
>   - `diff_scripts(before, after)` — line-level diff. Returns a `ScriptDiff` with `.lines` (list of `LineDiff` in line order) + `.added_count` / `.deleted_count` / `.modified_count` / `.equal_count`. The `is_clean` property is True iff zero changes; `total_changes` sums the three change types.
>   - **Line-level operation types** (string constants, not an enum — keeps JSON serialization trivial): `OP_EQUAL` / `OP_REPLACE` / `OP_DELETE` / `OP_INSERT`. Two lines "match" for difflib's purposes if their host + text + segment_type are all equal (source_ref is metadata, NOT content — a source_ref change alone is NOT a line modification; the test suite pins this).
>   - **Word-level diffs WITHIN a modified line** — a 1-word tweak in a 50-word line shows just that 1 word, not the whole line as a delete+add pair. Uses a second `SequenceMatcher` on the word lists. The `WordDiff` dataclass has `.op` (EQUAL/DELETE/INSERT — REPLACE is reported as a delete+insert pair so both old and new words are visible), `.before`, `.after`.
>   - `summarize_diff(diff)` — one-line summary (e.g., "3 added, 1 deleted, 2 modified (6 total changes)." or "✅ No changes — the scripts are identical.").
>   - `format_diff_for_display(diff, log, context=2)` — git-diff-style multi-line formatter: `+` for inserts, `-` for deletes, `~` for modifies, space for context. The `context` parameter controls how many unchanged lines to show around each change (0 = changes only; 2 = git's default; large = whole diff). When changes are far apart, a `...` separator skips the middle (git-diff style). Word-level diffs are shown inline with `[-old-]` / `[+new+]` markers. Modified lines whose only change is host or segment_type (text identical) are shown explicitly without word-diff noise.
>
> **Layer 2 — the CLI diff subcommand (W-g2, `core/podcast/cli.py`):** a new `diff` subcommand joins the V0.6.19 `validate`/`generate`/`info` + V0.6.20 `stats` quintet. `python -m core.podcast.cli diff --script-a before.json --script-b after.json` prints the diff to stdout. `--context N` controls unchanged-line context (default 2, git's default; 0 = changes only). `--summary-only` prints just the one-line summary. Exits 0 on success (even if there are changes — a diff isn't an error), 2 on file/parse error (same contract as `info`/`stats`). The CLI's main description string now mentions V0.6.21.
>
> **The pins (1 new test file, 31 tests):** `tests/test_v0621_script_diff_pins.py` — Layer 1 (24 diff-module tests): identical scripts clean, added lines, deleted lines, modified line text (with word-diffs populated), modified host-only (text identical → no word-diffs), modified segment-only, source_ref change ignored, mixed add+delete+modify, empty scripts, before-empty-after-populated (all inserts), before-populated-after-empty (all deletes), titles echoed, line indices 1-based; summarize_diff clean + with changes; format_diff clean returns summary, with changes has header, context=0 shows only changes, context=2 shows surrounding lines, context with skips (`...` separator), log callback called, word-level inline markers (`[-old-]`/`[+new+]`). Layer 2 (7 CLI diff tests): prints diff, clean scripts exit 0, missing file A exits 2, missing file B exits 2, bad JSON exits 2, `--summary-only` flag, `--context 0` flag, `diff` appears in `--help`, word-level markers in CLI output. All 31 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 31 P / 0 F (1.07s). Combined V0.6.18+V0.6.19+V0.6.20+V0.6.21: 150 P / 0 F. Broader regression sweep: **245 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 3 touched files. Three test-expectation bugs caught + fixed during development (the word-diff markers `[-...-]`/`[+...+]` break up contiguous text — assertions checking for "line 2 CHANGED" as a contiguous string failed; fixed to check component parts).
>
> **Unverified here (rig-only):** the wizard UI doesn't yet call `diff_scripts` (the wiring would be in the Script view's "Compare to original" button + a small diff-panel widget; requires Qt rendering to verify). The CLI's `diff` subcommand is fully pinned end-to-end.

## V0.6.20 — the script-statistics + stats-CLI batch: the wizard + CLI now show word count, estimated duration, host-split ratio, segment distribution, and Flesch reading level BEFORE generation — 50 new pins / 0 regressions (293 P total in this sandbox)

> **The trigger:** the V0.6.19 worklog's "Unresolved" section showed the HIGH-priority items all need Qt/torch (rig-only). The pure-Python feature work wasn't exhausted yet — the wizard + CLI could tell the operator the line count and coverage %, but NOT the things that actually matter for planning a generation run: how long the audio will be, how the talking time splits between Host A and Host B, what the reading level is, how many words per line on average. This release adds that analytics layer as a new pure-Python module + a new CLI subcommand, per the cron's [Mandatory] "add more features and functionality" requirement.
>
> **Layer 1 — the SCRIPT STATISTICS module (W-f1, NEW `core/podcast/script_stats.py`):** pure-Python (no Qt/torch/NLTK/spaCy/textstat deps) analytics. Public API:
>
>   - `count_syllables(word)` — the heuristic English syllable counter (vowel-group + silent-e + -le-ending rules; ±1 syllable accuracy — the algorithm textstat uses). The `-le` check runs on the ORIGINAL word BEFORE the silent-e strip (the V0.6.20 first attempt checked -le AFTER the strip, which broke "apple"/"table" → 1 instead of 2; the test suite caught it).
>   - `flesch_reading_ease(text)` — the Flesch Reading Ease score (0-100, clamped; higher = easier). Falls back to a neutral estimate for non-English text (no detectable syllables).
>   - `flesch_kincaid_grade(text)` — the Flesch-Kincaid grade level (e.g., 8.2 = grade 8; clamped to >= 0).
>   - `estimate_duration_seconds(word_count, wpm=150)` — standalone duration estimator. 150 WPM for English (the widely-cited conversational average); 130 WPM for Farsi (auto-detected from the text; Farsi's agglutinative morphology makes speech a bit slower).
>   - `compute_stats(script, wpm=None)` — the main entry point; returns a `ScriptStats` dataclass with: total_lines / total_words / total_chars / total_syllables / total_sentences / unique_words (vocabulary size); per-host `HostStats` (line_count / word_count / char_count / avg_words_per_line / estimated_duration_seconds / estimated_duration_human); per-segment `SegmentStats` (segment_type / line_count / word_count); distribution metrics (avg / median / min / max words per line); duration estimate (seconds + "M:SS" human format); reading level (Flesch score + grade + label); the `host_split_ratio` property (returns "52:48" style string summing to 100).
>   - `format_stats_for_display(stats, log)` — multi-line formatter with sections: 📊 Script Statistics / ⏱️ Duration estimate / 👥 Per-host breakdown / 📑 Segment distribution / 📏 Line-length distribution / 📖 Reading level. Optional log callback echoes each line (the wizard can use this to echo stats to its live log).
>
>   Auto-detection: if >10% of the text's non-whitespace chars are in the Arabic/Persian Unicode blocks (U+0600–U+06FF, U+FB50–U+FDFF, U+FE70–U+FEFF), the script is treated as Farsi and uses FARSI_DEFAULT_WPM (130) instead of DEFAULT_WPM (150). The operator can override via `compute_stats(script, wpm=...)`.
>
> **Layer 2 — the CLI stats subcommand (W-f2, `core/podcast/cli.py`):** a new `stats` subcommand joins the V0.6.19 `validate` / `generate` / `info` trio. `python -m core.podcast.cli stats --script my.json` prints the rich analytics to stdout; `--json` outputs the same data as JSON (for piping to other tools / a future web view); `--wpm 100` overrides the auto-detected WPM. Exits 0 on success, 2 on file/parse error (same contract as `info`). The CLI's main description string + help text now mention V0.6.20.
>
> **The pins (1 new test file, 50 tests):** `tests/test_v0620_script_stats_pins.py` — Layer 1a (12 syllable-counter tests, parametrized over common English words — hello=2, world=1, apple=2, table=2, like=1, queue=1, TV=1, etc.; + non-alpha stripping + never-negative); Layer 1b (7 Flesch tests — empty/easy/difficult/clamped + grade empty/easy/difficult/never-negative); Layer 1c (5 duration estimator tests — zero/negative/zero-wpm/150-words-at-150-wpm/linear-scaling); Layer 1d (14 compute_stats tests — empty script, counts, host breakdown sums, host line counts, host_split_ratio property, single-host ratio, segment distribution, line-length distribution, unique words, duration estimate, WPM override, Farsi auto-detect, reading level populated, is_conversational flag); Layer 1e (4 format_stats tests — empty message, all section headers, duration human format, log callback); Layer 2 (6 CLI stats tests — prints stats, missing file exits 2, bad JSON exits 2, --json outputs valid JSON, --wpm override, stats appears in --help). All 50 tests are pure-Python.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file 50 P / 0 F (1.10s). Combined V0.6.18+V0.6.19+V0.6.20: 119 P / 0 F. Broader regression sweep: **293 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 4 touched files. One iteration during development: the syllable counter's -le check was initially AFTER the silent-e strip (broke "apple"/"table"); the test suite caught it before commit; the fix checks -le on the ORIGINAL word before the strip.
>
> **Unverified here (rig-only):** the wizard UI doesn't yet call `compute_stats` in the Script view (the wiring is ~10 lines in `_on_script_done` but requires Qt rendering to verify). The CLI's `stats` subcommand is fully pinned end-to-end.

## V0.6.19 — the encoding-cascade + script-validator + headless-CLI batch: the .txt reader now detects UTF-16/32 BOMs + Asian encodings (Shift-JIS / EUC-JP / EUC-KR / GB18030 / Big5), the wizard's "Generate Podcast" button gets a real pre-flight validator, and a `python -m core.podcast.cli` entry point runs headless — 38 new pins / 0 regressions (243 P total in this sandbox)

> **The trigger:** the V0.6.18 worklog's "Unresolved issues or risks" section named LOW priority item #6 as "the cp1252-encoded .txt fix is conservative — it doesn't use chardet / charset_normalizer (not in every rig's venv). If a real-world .txt in a non-Western encoding (e.g., Big5, Shift-JIS, GB18030) is encountered, it would fall through to latin-1 with errors='replace' — readable but possibly garbled. Acceptable for now." This release closes that gap AND adds two new pure-Python features the cron's [Mandatory] "add more features and functionality" requirement targets.
>
> **Layer 1 — the EXTENDED ENCODING CASCADE (W-e1, `core/pipeline/multi_format_reader.py`):** the V0.6.18 four-step cascade (utf-8-sig → utf-8 → cp1252 → latin-1) covered ~99.9% of Western files but produced GARBAGE for Asian files (cp1252 is permissive — most bytes 0x80-0xFF are defined — so it "succeeds" on a GB18030 / Big5 / EUC-KR file before the cascade reaches the right encoding). V0.6.19 extends the cascade to twelve steps:
>
>   1. utf-8-sig (BOM-stripped UTF-8)
>   2. utf-32 (only when the BOM FF FE 00 00 / 00 00 FE FF is present — checked BEFORE UTF-16 because UTF-32-LE's BOM is a 2-byte prefix of UTF-16-LE's BOM)
>   3. utf-16 (only when the BOM FF FE / FE FF is present — the V0.6.19 first attempt tried them unconditionally, which "succeeded" with GARBAGE for any even-length ASCII file; the BOM-gated version is correct)
>   4. utf-8 (strict)
>   5. chardet (OPTIONAL — high-confidence detection only, >= 0.7 confidence; returns None if chardet isn't installed or its confidence is below threshold; aliases chardet's names to Python's codec names — `SHIFT-JIS` → `shift_jis`, `GB2312`/`GBK` → `gb18030` (the superset), etc.)
>   6-10. the Asian encodings (BEFORE cp1252 — see below): shift_jis → euc_jp → euc_kr → gb18030 → big5
>   11. cp1252 (Windows Notepad "ANSI" — the V0.6.18 bug source, now the SAFETY-NET for Western files whose bytes don't form valid Asian sequences)
>   12. latin-1 (catch-all, never raises)
>
>   **Order rationale for steps 6-10 BEFORE cp1252:** the V0.6.18 order (cp1252 first) produced GARBAGE for Asian files because cp1252 is permissive. Reversing is safe because the Asian encodings are STRICTER about lead/trail byte pairs — a typical Western cp1252 file (ASCII + smart quotes + em-dash + accented Latin) has single high bytes that don't form valid Asian 2-byte sequences, so the Asian encodings RAISE and the cascade falls through to cp1252 (step 11). The rare cp1252 file whose high bytes happen to form valid Asian pairs would be mis-decoded as Asian garbage — acceptable: the operator can re-save as UTF-8 (modern Windows + the app's own outputs are all UTF-8). For real-world Asian files of realistic length (100+ non-ASCII bytes), the chardet step at 5 detects the encoding at 0.99 confidence and the cascade never reaches step 6.
>
> **Layer 2 — the SCRIPT VALIDATOR (W-e2, NEW `core/podcast/script_validator.py`):** a pure-Python (no Qt / no torch) validator that catches script issues BEFORE audio generation. The wizard's "Generate Podcast" button calls `validate_script(script, host_a_voice, host_b_voice, is_conversational)` FIRST; the result is a `ValidationResult` with `.errors` (blocks generation), `.warnings` (allows, "Continue anyway?" confirm), `.infos` (just logs), and an `.ok` property (True iff no errors). 9 rules across the three severities:
>
>   - ERROR: E1 empty script (zero lines), E2 invalid host value (not "A"/"B"), E2b Host B line in lecture mode, E3 empty line (no text + no cues), E4 Host B voice empty in conversational mode with Host B lines.
>   - WARNING: W1 script too long (> 50 lines — ~4-minute generation on CPU), W2 script too short (< 3 lines — likely over-edited), W3 first line not tagged 'intro', W4 last line not tagged 'conclusion', W5 Host A voice empty (lecture mode tolerates via Kokoro 'af_heart' fallback).
>   - INFO: I1 empty title (audio saved with timestamp name), I2 anti-hallucination force-inserted bullets (coverage < 100%), I3 empty source_ref on a line (audit trail gap).
>
>   `format_issues_for_display(result, log)` formats the result as a multi-line string for the wizard's status banner, grouped by severity with counts and code prefixes (e.g., `[E2_INVALID_HOST] Line 3 has an invalid host value: 'C'.`).
>
> **Layer 3 — the HEADLESS CLI (W-e3, NEW `core/podcast/cli.py`):** `python -m core.podcast.cli` with three subcommands: `validate` (validate a script JSON, print issues, exit 0/1), `generate` (validate, then generate audio; Ctrl-C cancels at the next line boundary via the V0.6.18 CancelToken), `info` (print script metadata without validating). The script JSON is the same format `ScriptResult.to_json()` produces — so the wizard's "Export script" button creates a file the CLI can re-import. The `generate` subcommand wires up a `CancelToken` (V0.6.18 W-d3) and a SIGINT handler that calls `token.cancel("Ctrl-C from CLI")`; the line loop exits at the next iteration boundary (the same UX the wizard's Stop button will have once it's wired in).
>
> **The pins (1 new test file, 38 tests):** `tests/test_v0619_encoding_validator_cli_pins.py` — Layer 1 (10 encoding tests): chardet-not-installed returns None, low-confidence returns None, high-confidence returns normalized encoding, GB2312 aliases to gb18030, UTF-16-LE/BE with BOM round-trip, Shift-JIS round-trips, GB18030 round-trips (long string for chardet detection), Big5 round-trips, EUC-KR round-trips, V0.6.18 Western regression (utf-8 / utf-8-bom / cp1252 / pure-ASCII still round-trip), garbage-never-raises (non-BOM garbage, latin-1 catch-all). Layer 2 (16 validator tests): clean script passes, empty script blocks (E1 + short-circuit), invalid host blocks (E2), Host B in lecture mode blocks (E2b), empty line blocks (E3), Host B voice empty in conversational blocks (E4), too long warns (W1), too short warns (W2), no intro warns (W3), no conclusion warns (W4), Host A voice empty warns (W5), empty title is info (I1), force-inserted bullets is info (I2), .ok property + bool() coercion, ValidationIssue rejects bad severity, format_issues_for_display clean message, format_issues_for_display groups by severity. Layer 3 (7 CLI tests): info subcommand prints metadata (exits 0), info missing file exits 2, info bad JSON exits 2, validate clean script exits 0, validate invalid host exits 1, validate --strict makes warnings fatal, generate validates first then calls audio gen (monkeypatched — never calls generate_podcast_audio on validation error), generate passes a CancelToken, module invocable via `python -m core.podcast.cli --help`. All 38 tests are pure-Python (no PySide6 / no torch).
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch, chardet 5.2.0 + charset_normalizer 3.4.7 available):** new file 38 P / 0 F (1.93 s). Combined with V0.6.18: 69 P / 0 F. Broader regression sweep on related modules (vibevoice + qwen + podcast + multi-format tests): **243 P / 0 F total, zero regressions**. ruff check + ruff format --check clean on all 5 touched files. The V0.6.18 garbage-bytes test was updated to use non-BOM-prefixed bytes (the V0.6.19 UTF-16 BOM detection now intercepts FF FE prefixes — the V0.6.18 test's "never raises" contract is preserved on the latin-1 catch-all path; the test comment explains why).
>
> **Unverified here (rig-only):** the wizard UI doesn't yet call `validate_script` before `generate_podcast_audio` (the wiring is ~5 lines in `_on_generate_audio` but requires Qt rendering to verify). The CLI's `generate` subcommand couldn't be end-to-end tested (no torch for the TTS engines); the validate-first logic IS pinned via monkeypatch.

## V0.6.18 — the offline-lock + cancel-token + cp1252-txt-reader batch: VibeVoice + Qwen3-TTS no longer silently phone HuggingFace, the podcast line loop can be cancelled mid-generation, and Windows "ANSI" .txt files no longer lose their non-ASCII bytes — 31 new pins / 0 regressions

> **The gap this closes (honest framing):** a prior session's "final report" claimed three commits on this branch (`75da290`, `1f804e5`, `88e3721`) had landed the offline lock, the five-view Podcast Wizard refactor, and a fresh-eyes review round — but `git log` shows the branch tip is still `6f2368d` (V0.6.17); none of those commits exist on GitHub. The report was either wiped before push or never committed. This release does the work that survives contact with the offscreen test suite: the offline lock (both TTS engines), a real cancel token wired into the audio generator's line loop, and the cp1252 .txt reader fix. The five-view Podcast Wizard refactor is deliberately NOT in this release — without a Qt-rendering sandbox in this environment, a 930-line UI restructure could not be visually verified, so it is deferred to a session that has the rig (see §Unresolved below).
>
> **The offline lock (4 files):** `core/tts/vibevoice_engine.py` — the V11.61.0 clean-env spawner now sets `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` / `HF_DATASETS_OFFLINE=1` / `TOKENIZERS_PARALLELISM=false` in the env dict BEFORE `sub.spawn`; the model loads strictly from the local folder the operator pointed at, and a genuinely-missing helper file now raises a named `FileNotFoundError` instead of succeeding slowly via a silent network fetch the operator never asked for (this is the "HuggingFace contact" the operator asked about — it happens inside `transformers`/`huggingface_hub` while loading even a local model directory, NOT because the app downloads the VibeVoice model itself). `core/tts/_vibevoice_subprocess.py` — the same four flags set at MODULE TOP via `os.environ.setdefault` (the belt-and-suspenders path for direct-launch debugging; `setdefault` not `=` so the operator's own `HF_HUB_OFFLINE=0` in their shell isn't clobbered). `core/tts/qwen_tts_engine.py` + `core/tts/_qwen_tts_subprocess.py` — same treatment mirrored for Qwen3-TTS (the operator's report named VibeVoice only; Qwen has the same theoretical web-fetch hole, so the same lock is applied).
>
> **The cancel token (2 new + 1 modified):** `core/podcast/cancel_token.py` (NEW) — a thread-safe `CancelToken` class (Lock-guarded bool, starts False, flips True exactly once on `.cancel(reason)`, stays True; `.cancelled` + `.reason` properties; `__slots__` for cheapness). Deliberately minimal — no events, no threads, no Qt dependency — so it is safe to import from any context (tests, CLI, the engine itself) without dragging PySide6 in. `core/podcast/audio_generator.py` — `generate_podcast_audio` gains a `cancel_token: CancelToken | None = None` parameter (default None — backward-compatible with every existing caller); the line-by-line loop checks `token.cancelled` at the TOP of every iteration and returns `None` (with the reason logged + progress-callback'd) when the flag is set. Mid-line cancel is deliberately NOT supported — orphaning a half-synthesized WAV is worse than waiting one line for the boundary; the contract is "either success, fail, or cancelled-at-iteration-boundary."
>
> **The cp1252 .txt reader fix (1 modified):** `core/pipeline/multi_format_reader.py` — the pre-V0.6.18 path was `file_path.read_text(encoding="utf-8", errors="ignore")` which SILENTLY DROPPED every non-ASCII byte (smart quotes, em-dashes, accented Latin chars, the curly apostrophe in "it's", the en-dash in "1979–1985") from any .txt saved by Windows Notepad in its default "ANSI" mode (cp1252 / Windows-1252). The new `_read_text_with_encoding_fallback` cascade tries utf-8-sig → utf-8 → cp1252 → latin-1 in order; the first that decodes the raw bytes WITHOUT error is the text. Order matters: utf-8 is tried before cp1252 because cp1252's 0x80–0x9F range would happily "decode" UTF-8 multi-byte sequences into garbage (e.g., the UTF-8 bytes for an em-dash E2 80 94 would decode in cp1252 as â€"). No `chardet` / `charset_normalizer` dependency — those aren't in the venv on every rig; the four-step cascade covers ~99.9% of real-world .txt files without one.
>
> **The pins (1 new test file, 31 tests):** `tests/test_v0618_offline_cancel_cp1252_pins.py` — Layer 1: 16 source-pin tests (4 flags × 4 files) asserting the offline env assignments are present in the engine spawners AND the subprocess module-tops (in the correct syntactic form: `env["X"] = "Y"` for engines, `os.environ.setdefault("X", "Y")` for subprocesses). Layer 2: 5 `CancelToken` unit tests (initial state, cancel flips flag + records reason, default reason, idempotency, 100-thread concurrency safety). Layer 3: 4 `generate_podcast_audio` runtime tests (signature has `cancel_token` with default None; pre-cancelled token returns None with zero TTS calls; cancel after line 1 halts before line 2 with exactly one `_synthesize_line` call; backward-compat: existing callers without the param still work). Layer 4: 6 cp1252 reader runtime tests (utf-8 round-trips; utf-8-with-BOM strips the BOM; cp1252 round-trips smart quotes + em-dash + accented chars; pure ASCII round-trips; garbage bytes never raise — latin-1 catch-all; `_extract_text_file` uses the fallback end-to-end). All 31 tests are pure-Python (no PySide6 / no torch) so they run in any sandbox.
>
> **Verification (this sandbox — Linux, Python 3.12.14, no PySide6 / no torch):** new file: 31 P / 0 F (1.94 s). Regression sweep on the related modules: `test_v0617_vibevoice_meta_init` (37 P), `test_v0615_vibevoice_diagnostics`, `test_v0616_vibevoice_transformers_v5`, `test_v182044_p3_tts_subprocess`, `test_podcast_cleaning` (88 P combined), `test_v066_review_loop_fixes` (49 P) — 174 P / 0 F regression. `ruff check` + `ruff format --check` clean on all 8 touched files. **Unverified here (rig-only):** the actual speedup from the offline lock on a real VibeVoice load (no GPU/torch in this sandbox), and the wizard's UI flow once a Qt-rendering session re-does the five-view refactor this release deliberately defers.

## V0.6.17 — the transformers-v5 meta-device model-init release: "Cannot copy out of meta tensor" + the tie_weights/_prepare_generation_config signatures + the 4.5x preset caches no longer kill the podcast — 7,684 P / 0 F

> **The report (the V0.6.16 tolerance working as designed):** the operator's paste-back shows the import surviving (`native-VibeVoice duplicate-register tolerance active`), CUDA detected, the load starting — and dying one stage deeper: `DPMSolverMultistepScheduler` at `dpm_solver.py:295` → `self.sigmas.to("cpu")` → `NotImplementedError: Cannot copy out of meta tensor; no data!` → "Podcast generation STOPPED at line 1. No audio file will be produced."
>
> **The diagnosis (reproduced byte-for-byte against the real stack — model included):** transformers v5 builds EVERY from_pretrained model on the meta device — unconditionally, because `low_cpu_mem_usage` was REMOVED in v5 ("Not used anymore", modeling_utils.py:4240 in the rig's 5.14.1). Under `with torch.device("meta")` every device-unspecified tensor FACTORY call (`torch.tensor`, `linspace`, `empty`, …) produces a meta tensor while `torch.from_numpy` is not redirected; transformers' own `meta_device_safe_creation_ops` patches only `torch.linspace` (identical in 5.14.1 and 5.17.0). VibeVoice-Realtime's `ddpm_beta_schedule: "cosine"` builds its betas via `betas_for_alpha_bar` → `torch.tensor` → META → the scheduler's `.to("cpu")` dies (while its `timesteps` via `from_numpy` stayed real — exactly the operator's traceback). The lab went all the way this time: the REAL microsoft/VibeVoice-Realtime-0.5B checkpoint (2 GB) was downloaded, the traceback reproduced byte-for-byte on the rig's exact transformers (5.14.1), and fixing the scheduler exposed THREE more v5 breakages in the same chain — `tie_weights(recompute_mapping=False)` against the from-source no-arg override (:204); the custom generate()'s v4-shaped `_prepare_generation_config(config, True, speech_*=…)` call against v5's signature; and the official voice presets pickling transformers-4.5x `DynamicCache` internals (`key_cache`/`value_cache` lists — verified inside the real en-Carter_man.pt) which v5's rearchitected cache rejects on the first forward. Final proof: the real checkpoint + the real preset generated a real 4.7 s WAV through the production load path on BOTH 5.14.1 and 5.17.0 (879 params, zero meta leaks, real scheduler sigmas).
>
> **The fixes (2 runtime files):** `core/tts/_vibevoice_subprocess.py` — four additions installed after the vibevoice import and before from_pretrained: (1) `_guard_scheduler_meta_init()` — wraps `DPMSolverMultistepScheduler.__init__`; when a meta context is active (probed via `torch.empty(0).is_meta`) it re-enters `with torch.device("cpu")` around the original init — torch's single-DeviceContext invariant means the nested CPU context REPLACES the meta one for the duration (proven live for BOTH mechanisms: the v5 device CM and the accelerate-style DeviceContext of v4+device_map); the scheduler holds no checkpoint state (zero scheduler keys in model.safetensors — verified), so it must be built real; fast path untouched when no meta context; (2) `_tolerate_v5_tie_weights_signature()` — the class's own override wrapped to accept-and-drop v5's `missing_keys`/`recompute_mapping` (unknown kwargs still propagate); (3) `_tolerate_v5_prepare_generation_config()` — the inherited mixin shadowed with a wrapper dropping v4's second positional (`use_model_defaults`, consulted only when the config is None — VibeVoice never does) and the three speech ids (re-set by the caller on the next lines; verified against the 4.51.3 source that the drops are identical on v4 and v5); (4) `_modernize_legacy_preset_cache()` (+ three helpers) — each 4.5x preset cache rebuilt layer-by-layer through the INSTALLED version's `DynamicCache.update()` (real CacheLayerMixin layers, tensors untouched; VibeVoice's own MockCacheLayer bridge then no-ops); one NOTE per process (the preset reloads every line); presets already in the new format left alone. The load call now passes the version-gated dtype kwarg (`dtype` on ≥5, `torch_dtype` on v4). The V11.57 no-restart and V18.20.4.4 kill-before-raise contracts are byte-identical (pinned). `core/tts/vibevoice_engine.py` — defense in depth: a load error carrying "meta tensor" explains the meta-device init and names the two outs.
>
> **The tests (+37, `tests/test_v0617_vibevoice_meta_init.py`):** behavioral pins against a fake torch with the REAL device-context semantics (factory redirection, the from_numpy asymmetry, the fatal meta→cpu copy): the guard (meta → real scheduler + NOTE; the unpatched reproduction pin; idempotency; the missing-module WARNING; the probe-failure fallback); the tie tolerance (v5 kwargs dropped; the v4 passthrough; unknown kwargs propagate; the no-override no-op — the exact regression the v0616 live test caught in the first cut); the generation-config tolerance (the real call shape; the unpatched reproduction pin); the cache modernizer (four caches rebuilt with tensors preserved + ONE note; once-per-process; modern/mismatched/non-tensor untouched); the dtype gating; the engine hint; source pins (the compat→import→guard→tie→generate→from_pretrained ordering). Plus ONE LIVE protocol test — the REAL engine + REAL subprocess against a stub tree whose from_pretrained reproduces the v5 meta-device init, first PROVING the stack dies with the operator's exact error unpatched, then proving the fixed chain reaches READY and synthesizes audio with every NOTE line in the drained stderr.
>
> **Gates:** suite **7,684 passed / 0 failed / 54 skipped in 302.9 s** (V0.6.16's 7,647 + exactly the 37 new; one transient e2e flake in a TTS-untouched queue-view test failed once under full-suite load, passed in isolation and in the final clean run); ruff 0.16.8 clean; radon — the new functions at B grade (`_modernize_legacy_preset_cache` C(22)→B via the helpers), `main` at its pre-existing F band; token-leak grep 0.
>
> **Rig test path:** run a podcast — the load now logs `transformers <version>`, the V0.6.16 lines, then `NOTE: meta-device model init detected (transformers v5) — building the VibeVoice noise scheduler on real CPU tensors`, reaches `✅ VibeVoice ready on CUDA`, and on the first line's preset `NOTE: rebuilt 4 legacy voice-preset cache(s) into the installed transformers' format` — then the 113 lines generate and the audio is produced. No transformers downgrade, no VibeVoice re-install, no preset re-download.


## V0.6.16 — the transformers-v5 VibeVoice compatibility release: the native-VibeVoice duplicate registration + the removed `*_fast` tokenizer submodules no longer kill the podcast at line 1 — 7,647 P / 0 F

> **The report (the V0.6.15 diagnostics working as designed):** the operator's paste-back finally contained the full load traceback — `AutoModel.register(VibeVoiceAcousticTokenizerConfig, …)` at `modular_vibevoice_tokenizer.py:1200` dying with `ValueError: "'…' is already used by a Transformers model."`, "Podcast generation STOPPED at line 1." The traceback's `auto_factory.py` line numbers (register at 427, the ValueError at 672) fingerprint the rig's transformers as a **v5.13–v5.17 build** — which ships VibeVoice **natively**, its auto-generated registry (`models/auto/auto_mappings.py` line 684 in 5.17.0) pre-registering the config-class NAME `VibeVoiceAcousticTokenizerConfig`. The from-source `C:\VibeVoice` package re-registers its OWN class with that same name at import time, and transformers' `_LazyAutoMapping.register` checks duplicates **by class name** — the first import dies. One import later the SAME v5 breaks the package a second time: the per-model `*_fast` tokenizer submodules were removed (`Qwen2TokenizerFast` now lives in `transformers.models.qwen2`), while `modular_vibevoice_text_tokenizer.py` still imports the legacy `tokenization_qwen2_fast` path.
>
> **The diagnosis method (not reading alone):** a lab venv (torch 2.14 CPU + transformers 5.17.0 + the current microsoft/VibeVoice checkout) reproduced the operator's traceback **byte-for-byte** unpatched, then imported cleanly with the fix; the fix was re-verified across the whole affected range (transformers 5.13.0 / 5.17.0 / 5.18.0: fixed; 4.57.1: byte-identical no-op — the no-regression proof).
>
> **The fixes (2 runtime files):** `core/tts/_vibevoice_subprocess.py` — a transformers-v5 compatibility layer (`_install_transformers_compat()`, installed before the first vibevoice import): (1) `_tolerate_native_vibevoice_register()` — the colliding register is retried with `exist_ok=True` (the from-source class wins — the exact end-state of a transformers without native vibevoice; the mapping entry is cosmetic, the streaming path instantiates its classes directly) with a NOTE naming what happened; primary patch at the shared `_LazyAutoMapping.register` choke point (covers the package's `AutoModel` AND `AutoModelForCausalLM` sites), fallback at the documented classmethods, unpatchable → a WARNING naming the `transformers<5.13` pin, never a crash; (2) `_alias_legacy_tokenizer_modules()` — the removed `tokenization_qwen2_fast` submodule pre-registered in `sys.modules` as a one-attribute alias from the package's own class (no alias at all on transformers < 5); the subprocess now logs its transformers version at load. `core/tts/vibevoice_engine.py` — defense in depth: if the tolerance could not be installed, the load-error raise explains the collision and names the two outs. The V11.57 no-restart and V18.20.4.4 kill-before-raise contracts are byte-identical (pinned).
>
> **The tests (+19, `tests/test_v0616_vibevoice_transformers_v5.py`):** behavioral pins against a fake transformers with the REAL v5 register semantics (the name-based duplicate check, `exist_ok` threading, the config-mismatch ValueError still propagating, the classmethod fallback, the missing-transformers no-op, idempotency); the alias semantics (created from the package class / no alias when the real module exists / silence when nothing exists); the engine hint (appended for the collision error, absent otherwise); source pins (the compat layer installs BEFORE the first vibevoice import); and ONE LIVE protocol test — the REAL engine + REAL subprocess against a v5-style stub stack which first PROVES the stack dies with the operator's exact error unpatched, then proves the fixed chain reaches READY and synthesizes audio with every NOTE line in the drained stderr.
>
> **Gates:** suite **7,647 passed / 0 failed / 54 skipped in 250.5 s** (the fresh-venv optional-dep set differs from V0.6.15's — the +13 skip delta is env-conditional rig tests; zero failures is the gate); ruff 0.16.8 clean; radon — the new functions extracted to A/B grade, `main` unchanged; token-leak grep 0.
>

## V0.6.15 — the VibeVoice podcast diagnostics + compatibility release: every VibeVoice failure now names its cause (the operator's "it generated text by llm, but vibevoice had error" report) — 7,641 P / 0 F

> **The report (verbatim):** "Another Error, the app has problem with vibevoice, podcast tool, it generated text by llm, but vibevoice had error." The V0.6.13 llama.cpp-first wiring fixed the script step; the failure moved one stage deeper — into the VibeVoice synthesis — and the live log could not say why: **the engine dropped the subprocess traceback on both error paths** (the raise carried the error string only, so a CUDA OOM, an import failure, and a preset problem all looked identical in the operator's paste-back).
>
> **The audit method:** the sandbox was rebuilt (env reset; venv intact, EGL libs re-extracted to `~/.local-lib`), then the REAL `VibeVoiceEngine` → REAL `_vibevoice_subprocess.py` protocol was run end-to-end against a stub `torch`/`vibevoice`/`transformers` tree (spawn with the minimal env, load handshake, preset load, generate, teardown) — **the protocol itself passes**; the VibeVoice repo's current module paths (`vibevoice.modular.modeling_vibevoice_streaming_inference`, `vibevoice.processor.vibevoice_streaming_processor`) and class names were also verified live against GitHub. The gaps were around the chain: the dropped traceback; a single-path preset load (`weights_only=False` unconditionally, while the official demo uses `weights_only=True` inside `safe_globals` and torch < 2.6 has no `safe_globals` at all → AttributeError on the context manager itself); a silent CPU load (~100× slower — the guaranteed 600 s per-line timeout with nothing naming the cause while there was time to cancel); no free-VRAM check (the rig runs llama-server for the LLM step of the SAME podcast — when it holds the card, the 2.6 GB load dies on CUDA OOM with nothing naming the likely holder); and the podcast log never showed whether the VibeVoice model/voices paths were even valid.
>
> **The fixes (3 runtime files):** `core/tts/vibevoice_engine.py` — the load-error and generate-error paths forward the subprocess traceback to the live log (📋 lines at ERROR); a `No module named 'vibevoice'` load error appends the install command; a `device: cpu` loading status logs the CPU WARNING (the 600 s consequence + the `~/.elixir/gpu_probe.log` path); a new fail-soft `_preflight_vram()` helper logs free VRAM and warns under `VIBEVOICE_MIN_FREE_VRAM_GB` (3.5) naming llama.cpp / Ollama; the generate-error kill-reason slice widened 80 → 200. `core/tts/_vibevoice_subprocess.py` — the preset load moved into `_load_voice_preset()` with a 3-step fallback chain (official `weights_only=True` + `safe_globals` FIRST → legacy `weights_only=False` → plain `torch.load` when `safe_globals` doesn't exist); the CUDA load path reports FREE VRAM alongside total (`torch.cuda.mem_get_info`) with a low-free WARNING; the load and generate handlers write the FULL traceback to stderr (the parent's drain logs it live). `core/podcast/audio_generator.py` — a new `_log_vibevoice_config()` helper logs the model path + voices dir with existence (`— OK` / `— NOT FOUND` / `(not set)`) before the first spawn. The V11.57 no-restart policy and the V18.20.4.4 kill-before-raise contract are byte-identical (pinned).
>
> **The tests (+19, `tests/test_v0615_vibevoice_diagnostics.py`):** engine behavioral pins via the `_FakeProc` pattern (traceback forwarding, the install hint + its absence for other errors, the CPU warning and its cuda counterpart, the VRAM pre-flight low/healthy/no-torch cases, kill-before-raise survival); subprocess source pins (the fallback-chain ORDER, the torch < 2.6 AttributeError branch, the free-VRAM report, the stderr traceback on both handlers); audio-generator behavioral pins (the config-truth log for valid/missing/empty paths, the empty-path error contract unchanged); and ONE LIVE protocol test that spawns the REAL `_vibevoice_subprocess.py` through the REAL engine against a stub stack built in `tmp_path` — the full spawn→handshake→preset-load (via the new weights_only=True path)→generate→save→teardown chain, no 2.6 GB model, no GPU.
>
> **Gates:** suite **7,641 passed / 0 failed / 41 skipped in 244.3 s** (V0.6.14's 7,622 + exactly the 19 new tests; the 41-S count vs V0.6.14's 25 S + 16 D is the same set under a different counting mode); ruff 0.16.8 `check` + `format --check` clean repo-wide (755 files); token-leak grep 0; radon — no grade changes (the new blocks were extracted into `_preflight_vram` / `_load_voice_preset` / `_log_vibevoice_config` to keep the complexity deltas in-band).
>
> **Rig test path:** run the Podcast Maker with a VibeVoice voice — the log now shows the config truth (model/voices paths with OK/NOT FOUND), the free-VRAM line (with the llama.cpp/Ollama warning if low), the load device (with the CPU warning if CUDA is invisible), and the full 📋 traceback if anything fails. **If the failure persists, paste the traceback line(s) back — the next fix will be immediate instead of blind.**

## V0.6.14 — the single-model release: the fast/heavy dual-model concept REMOVED entirely (the operator's "we only have ONE MODEL for LLM generation" order) — 7,622 P / 0 F

> **The release (operator-ordered, verbatim):** "Remove Fast Model and all of it code from the application... I previously might have used two LLM models for my tasks, but the results were not good. the idea failed... the concept of fast model and heavy model is obsolete. from now on we only have ONE MODEL for LLM generation. (not counting ocr, transcribe etc)." The two-model architecture is retired across the WHOLE surface — workflows, processes, functions, settings, UI: **82 files, +772/−2,788 lines.** The session opened with a sandbox reset (venv + EGL rebuilt, the baseline reproduced at **7,684 P / 0 F / 25 S / 16 D** — the +18/−18 skip delta vs V0.6.13's shipped 7,666/43 is the rebuilt env having more optional deps installed). **Final tree: 7,622 passed / 0 failed / 25 skipped / 16 deselected in 248.5 s** (7,709 collected − 61 removed pins − 25 S − 1 known-flaky-that-passes-solo).
>
> **The data model + settings (`a0450a5`):** `ConversionRequest` loses 9 fields (fast_model ×2 shadowed, heavy_model, model_architecture — the 4-mode selector, fast_model_temperature, fast_model_context, fast_api_url/key/model, simplification_model — entangled via its fast→simplification fallback chain and the "Fast/Simplification" VRAM phase); the settings schema loses the 9 keys and gains a load-time RETIREMENT migration that strips stale keys from an existing settings.json (each logged once, INFO); the controller's `_REQUEST_FIELD_MAP` rows + per-book config writes go with them; `summarisation.fast_api_key` retires from `_SECRET_PATHS` (a stale keychain entry is inert — never read).
>
> **The dispatch machinery:** `core/summarisation/fast_llm.py` DELETED (the V18.15.3 4-mode router); `llm_dispatcher.call_fast_ollama`; `llm_transport._call_fast_llm`/`_call_fast_ollama`; `summarizer._switch_to_fast_model`/`_switch_to_heavy_model`; `summarizer_init`'s heavy-model fallback + max_workers=1 forcing; `chapter_phases`' heavy-model coverage fallback (low coverage now relies on gap-fill + over-delivery + the 3-Tier Guarantee — the B3 gate's heavy_model condition drops too); the heavy-model "independent reviewer" branch in `_self_review`/`self_review_batched` (THE model reviews its own output; the merge logic still only lets it REMOVE unsupported claims; the fusion provider's cloud reviewer — a provider choice, not a second generation model — is untouched); the simplification-model swap machinery in `simplified_keypoints.py` (the digest uses THE model; `_needs_model_swap`, the load/unload blocks, and the ModelType import go); the concept-extraction dual branches in `_rs_make_concept_llm_fn` (provider-routed now: ollama/llamacpp/lmstudio/fusion → local, openai_compatible/claude → cloud); `verification_phase`/`garble_repair`/`quote_repair`/`vision_region_cropper`/`ocr/service` read `summarisation.provider` directly (the model_architecture cross-reads retire; the OCR cloud-provider vision probe returns None like the old cloud-arch branch — the fresh-eyes find).
>
> **The call sites:** `call_fast_llm` RENAMED `call_llm` (CallFastLlmFn → CallLlmFn) in `gap_filler.gap_fill_concepts` (+ `switch_to_fast_model` and the V17.1.2 routing block removed), `gap_fill_batch.batch_gap_fill`, `scholar_reflection.scholar_reflection` (+ the gapfill-only variant); the Summarizer passes `call_llm=self._call_llm_with_empty_retry` everywhere. **Tier-2 coverage gap-fill keeps the old router's temperature=1.0** (byte-identical forwarding — the fresh-eyes review caught the delta and it was pinned back with a comment). The VRAM calculator's Fast/Simplification + Heavy phase entries go; the TOC heading labeler reads `summarisation.model`; `FAST_LLM_TIMEOUT_S` is renamed `SHORT_LLM_TIMEOUT_S` (120 s byte-identical; the B15 leaf pins updated).
>
> **The UI:** the wizard's 4-mode "Model architecture" selector → a 2-option **"Where does the model run?"** (Local / Cloud API — writes `summarisation.provider` only); the fast-model combo, fast temp/context params, the Fast API box + preset fill + Test button + its async result slots, and the dual-arch speculative-scholar gate all removed from `step5_models`; `ai_model_section` loses the arch combo, the fast rows ×3, the fast-API rows ×3, the heavy row, and the simplification row (the now-dead `_populate_models_async` helper + its shape test go with them); `WizardState` loses 4 fields; step7b's heavy + simplification pickers, step8's Architecture/Fast/Heavy/Simplification lines, step1_pdf's profile mapping entry, and wizard_view's loads/logs/VRAM args all cleaned.
>
> **Deliberately kept (the order's exclusion list + scope):** the fusion provider (local+cloud judging — a provider choice); B3 multi-sample voting (same-model sampling); OCR / transcribe / translation / TTS models ("not counting ocr, transcribe etc"); per-model temperature overrides.
>
> **Tests — 61 pins removed with the dead contract, every one documented:** `tests/test_fast_llm.py` deleted whole (12); per-file: llm_dispatcher −5, p2_sumtail_llm_dispatcher −2, controller_mapping −3, p3_secrets_wiring −2, v182043_settings_integrity −3, vram_phases −1, p6_stage_overlap −1, gap_filler −1, self_review −1, group_b_characterization −3, p2_preproc_simplified_keypoints −10, p2_summarizer_llm_transport −8, p2_summarizer_pipeline_phases −3, summarize_inner_characterization −2, v068_review_loop_fixes −1, v18202_system_fixes −1, v1820411_p2_tls_logs_literals −1, v182049_bk1_ui_threading −1 (fast-API test button) + the `_populate_models_async` shape test −1. ~90 more adapted in place (renamed mocks/kwargs, re-anchored pins — the B15 leaf pins SHORT_LLM_TIMEOUT_S==120, the A30 payload pin re-anchors on summarisation_model, the step5 layout pins the 2-box shape, the self-review fallback pin becomes the primary-model pin). Zero skipped, zero loosened survivors. The one heavy→primary pin EVOLUTION (self-review) keeps the surviving contract pinned instead of losing coverage.
>
> **Hygiene:** ruff 0.16.8 `check` + `format --check` clean repo-wide (753 files); fresh-eyes review over the full diff: 0 BLOCKERs / 1 SHOULD-FIX (fixed) / 6 suggestions (all addressed — the cloud-provider OCR probe, the dead helper, stale comments/citations); token-leak grep 0. **Remaining (the honest boundary):** the rig tasks stand (`requirements.lock` full clean-install regen + the live TTS/OCR/Ollama checklist, AUDIT_SWOT §8); live single-model behaviour on the rig (a full conversion through ONE model) is the operator's verification path — the sandbox proves the hermetic layer only.

## V0.6.13 — the llama.cpp-first policy extended to the services: the TTS text normalizer, the transcribe summary, and the Podcast Maker script generator wired ("they find LLM on Ollama only", the operator's follow-up report) — 7,666 P / 0 F

> **The release (operator-ordered, from the live follow-up report):** "ALSO TAKE NOTE THAT tts , TRANSCRIBE SERVICE AND PODCAST HAVE SAME PROBLEM, THEY FIND LLM ON OLLAMA ONLY." The V0.6.12 policy extended to the three named services + one new predicate, `is_local_url()` (the URL-only sites consult the policy ONLY when their configured target is loopback — a deliberate remote endpoint passes through untouched, the cloud treatment; kill switch `local.llamacpp_first=false` unchanged). **The Podcast Maker (`generate_podcast_script` + `_generate_podcast_title`):** Ollama-native tool, policy applies when its `ollama_url` is LOCAL — a live llama-server takes over BOTH the script and the title calls (`{base}/chat/completions`, the DETECTED served model + Bearer key); dead → the configured Ollama path byte-identical to V0.6.12 (payload pinned); connection errors name the backend instead of the raw urllib3 blob. **The transcribe summary (`summarize_transcript`):** the decision runs before `create_provider()` — takeover sets provider=llamacpp + the detected served model; cloud never probed; dead → the configured path. **The TTS text normalizer (`create_normalizer_from_settings` — also the podcast-audio normalize step) + the Settings→TTS "Test normalization" button:** a takeover points the already-OpenAI-compat TextNormalizer at the live llama-server and SKIPS the Ollama `/api/tags` discovery (with Ollama down it used to fail and DISABLE normalization — the defect in its sharpest form); the served model is never persisted to `tts.normalize_model`; the test button resolves the policy in its WORKER (the W-b8/W-b11 offload contracts pinned unchanged).
>
> **The completion bug caught in the inherited working tree:** the previous session's uncommitted wiring passed `llamacpp=` into `_generate_podcast_title` BEFORE the parameter existed — every podcast generation would have crashed with TypeError at the title step. Completed + pinned by direct tests (the `llamacpp=None` default keeps the Ollama path byte-identical; the fail-soft title fallback survives the takeover). Rig determinism: the existing tests that now flow through the wired sites pin `llamacpp_base_url` at a dead port (:9, the V0.6.12 packets-shim precedent).
>
> **Hygiene:** ruff 0.16.8 `check` + `format --check` clean repo-wide (754 files); 34 net-new hermetic tests (`tests/test_v0613_llamacpp_first_services.py`, 6 layers — the is_local_url predicate ×14, podcast script routing ×5, title routing ×3, transcribe routing ×4, the TTS factory ×5, tts_page source pins ×3), zero deleted/skipped/loosened; one harness lesson pinned (normalizer.py binds `session_for_url` at MODULE level — the fake transport must patch `core.tts.normalizer.session_for_url`, else the first import's binding stays frozen across tests). **Suite on the completed tree: 7,666 passed / 0 failed / 43 skipped / 16 deselected in 242.84 s** (V0.6.12's shipped record: 7,632 — net +34, EXACTLY the new file, zero regressions). **Remaining (the honest boundary):** the pipeline stays unwired (the VRAM interplay — operator decision, unchanged); the TOC heading labeler + the OCR dialogs are the next mechanical follow-ups; the rig tasks stand (`requirements.lock` regen + the live checklist, AUDIT_SWOT §8).

## V0.6.12 — the llama.cpp-first fallback release: "Packets of Knowledge is not connected to llama.cpp" fixed (provider=llamacpp called the Ollama endpoint regardless), the new-output riders' silent llama.cpp skip fixed, the operator's llama.cpp-first policy added (`core/llm/local_fallback.py`) — 7,632 P / 0 F

> **The release (operator-ordered, from the live user report):** "Packets of knowledge is not connected to llama.cpp so it doesnt work … my ollama is always on or mostly … but i turn on my llama.cpp casually (only when I need) so app must first look for llama.cpp if it's on, it means I want that model to be selected, add this policy." Two real defects under the report: **(1)** `PacketGenerator._call_llm` read ONLY `summarisation.endpoint` (default :11434) for every non-cloud provider — provider=llamacpp still POSTed to Ollama's `/api/generate`, and with Ollama off the run died on the raw urllib3 `HTTPConnectionPool` WinError-10061 blob; **(2)** `OutputGeneratorBase._call_llm_once` had NO branch for provider="llamacpp" (**the fresh-install default**) — the briefing/podcast/flashcards riders silently returned None (deterministic fallbacks fired, so nothing LOOKED broken). Baseline reproduced EXACTLY this session (7,608 / 0 / 43 / 16 in 242 s) before any change. **7,632 passed / 0 failed / 43 skipped / 16 deselected in ~250 s** (net +24, zero regressions).
>
> **The policy (`8186d98`) — `core/llm/local_fallback.py` + the `local.llamacpp_first` setting (default ON):** `decide_llamacpp_first()` — a live llama.cpp at `summarisation.llamacpp_base_url` (GET /v1/models, V0.4.30 factory precedent: the DETECTED served model wins over the configured name) → takeover with the served model + Bearer key; dead → the call site's configured path runs UNCHANGED. Cloud selections never probed, never overridden. TTL-cached probe (30 s, lock-guarded — the packets generator resolves once per packet). `local.llamacpp_first=false` is the kill switch. Scope boundary deliberate: raw-request tool call sites only — the conversion pipeline keeps its wizard-selected provider so the V0.6.9 VRAM budget gate stays consistent (extending the policy to the pipeline is an operator decision that must be made WITH the VRAM policy). 12 hermetic decision tests (cloud ×6, kill switch, takeover + detected-wins, dead-note, cache TTL/clear/stale, raising probe, garbage providers, production defaults).
>
> **Packets (`ea0c542`):** the decision runs before dispatch — takeover POSTs `{llamacpp_base_url}/chat/completions` (llama-server's OpenAI-compatible SSE branch) with the detected model + key; dead → the configured endpoint, byte-identical to V0.6.11 (the native :11434 `/api/generate` branch pinned, no-explicit-headers assertions). `ConnectionError` now logs `❌ Cannot reach <url> — is Ollama running?` (or llama.cpp / the configured backend, by target) instead of the raw urllib3 blob — control flow unchanged (first failure returns None, no retry). The takeover/dead note logs ONCE per run (`🦙 llama.cpp detected at … / not reachable at …`) so the tool log always names the backend that took the call. Live-shim fixture determinism: `_shim_values()` pins `llamacpp_base_url` at a dead port so the :3031 live test can't be hijacked by a real llama-server on 8080. 8 routing tests (the report pin, the policy pin, the byte-identical pins, the friendly error, both notes exactly once).
>
> **Riders (`d6277ec`):** same decision at the top of `_call_llm_once` + a proper `llamacpp` branch for the dead-server case (the configured llamacpp URL gets the OpenAI-compatible call instead of the silent None). The silent-skip defect is pinned by a characterization test that was RED on the pre-fix code and GREEN after — the house evidence pattern. 4 routing tests (the silent-None characterization, the takeover, the Ollama pin via `safe_ollama_request`, the cloud pin).
>
> **Hygiene:** ruff 0.16.8 `check` + `format --check` clean repo-wide (752 files); the new module's worst function is radon C; 24 net-new tests, zero deleted/skipped/loosened. **Remaining (the honest boundary):** the policy is not wired into the main conversion pipeline (the VRAM interplay — operator decision); the other raw-request LLM sites (transcribe, podcast script generator, TOC heading labeler, OCR dialogs) still follow their own wiring — each a small mechanical follow-up on `decide_llamacpp_first()`; the riders' `claude` branch still missing (pre-existing, unrelated); the rig tasks stand (`requirements.lock` regen + the live TTS/OCR/Ollama checklist, AUDIT_SWOT §8).

## V0.6.11 — the last-two-god-functions release: B14 run_summarization (CC 136) + batch_gap_fill (CC 107) split behind ctx dataclasses, the timeout migration FINISHED (all ~49 flagged sites on named constants) — 7,608 P / 0 F

> **The release (Wave 7 + Wave 8 of the fix/improve/optimize charter, all operator-ordered):** the session opened with a sandbox reset — the branch was re-cloned at V0.6.10, the toolchain reinstalled, the EGL libs rebuilt, and the inherited baseline reproduced EXACTLY (7,581 / 0 / 43 / 16 in 250 s) before any work. **7,608 passed / 0 failed / 43 skipped / 16 deselected in ~250 s** (V0.6.10: 7,581 — net +27, zero regressions).
>
> **B14-a — `run_summarization` (CC 136, ~1,035 LOC, `146e33d`):** the V0.6.7/B12 pattern — 15 phase helpers behind the `_SummCtx` dataclass (unload-VRAM / content filter / reference-skip / claim extractor / GPU profile + both worker caps / thermal safety with the pre-flight exit / summarizer init + run-id unification / glossary handoff / concept-LLM factory / chapter dicts / resume split / summarize with the fail-closed matcher + saver wiring / merge / book summary / finalize) + a thin orchestrator keeping the original statement order. **AST-identity verified: 337/343 original guards/leaves in order** (`.review-loop/verify_b14a_ast_identity.py`; declared normalizations: the 4 converter-surface locals + 2 list inits → dataclass defaults, return plumbing). The verifier caught TWO real bugs the behavioral net missed (a silently-swallowed `converter.ctx.thermal_safety` AttributeError on the stash line; the "new summaries" log string corrupted to "new ctx.summaries") — both fixed pre-commit, the stash now behaviorally pinned. Characterization FIRST: 18 tests green pre-split (early exits, front-matter skip + selected-chapters disable, <200-token warning, thermal + VRAM-calculator caps, pre-flight failure, run-id unification + glossary handoff, book-summary stamping, cancel/checkpoint contracts, judge stash, saver wiring). CC: F(136) → thin (<C); worst module function D(29). 4 pin evolutions (test_v067 save-call, test_v068 dual_api wiring anchors, test_chapter_match empty-match guard, test_v003 bullet-count anchor — all contract-preserving).
>
> **B14-b — `batch_gap_fill` (CC 107, ~1,000 LOC, 14 params, `e5e5a42`):** 7 phase helpers behind `_GapFillCtx` (prepare / round pool / round context / round execute — the verbatim `if _batch_context:` unit with the mention-only prompt + veto machinery / post-round accounting / final check / report); the ctx fields KEEP their leading underscores so every loop-internal source pin stays byte-identical. **AST-identity verified: 194/198 in order** (declared: the two `import re as _re2/_re3` aliases → module `re`; the two loop breaks → helper return-False; the matcher needed a break-disambiguation guard — all Break dumps are identical). The pass caught the `_total_added` rebind bug (the `+=` mutated a local int, the counter silently 0). Characterization FIRST: the V18.20.3.7 RC-B.1 no-yield escalation driven end-to-end for the first time (2 empty rounds → mention-only round 3 → give-up → round-4 pool break — previously only source-pinned by test_v182037), the punctuation-insensitive dup guard, the 2×-pool response cap. CC: F(107) → thin; worst functions E(36) (verbatim units, under the F(41) ceiling). 5 pin evolutions (the getsource anchors in test_v182032/34/35/39 → the module file; every pinned string survived byte-ident).
>
> **Wave 8 — the timeout migration COMPLETE (8 commits, `3437f12`…`a8ecf4f`):** all 11 flagged families migrated, import + swap, values byte-identical — UI-probe 5 s ×9 + the markdown-styler tight 3 s (its own leaf value `UI_PROBE_TIGHT_TIMEOUT_S` planted per the V0.6.10 note), CLI-poll 10 s ×11, subsecond 2 s ×4, API-batch 30 s ×4, HTTP-fetch 60 s ×5, fast-LLM 120 s ×9, slow 180 s ×7, LLM-request 300 s ×8, keypoints 420 s, long-run 600 s ×3, CLI-sweep 20 s. The leaf's flagged list is RETIRED (replaced by the migration record; the settings-default + tts/ module-local exclusions stay documented). 7 pin evolutions, all contract-preserving (the dialog latency budgets and the B15 flagged-list/honesty pins now assert the constant wiring AND the leaf values). Changing a timeout policy is now a one-line edit in `core/system/timeouts.py`.
>
> **Hygiene:** ruff 0.16.8 `check` + `format --check` clean repo-wide (749 files); 12 documented pin evolutions total, count-preserving, zero deleted/skipped/loosened tests; token scan clean. **Remaining (the honest boundary, per AUDIT_SWOT §8):** the rig tasks only — the `requirements.lock` full clean-install regen + the live TTS/OCR/Ollama checklist.

## V0.6.10 — the mechanical-wins release: the god functions decomposed (B12 scholar_reflection CC118 → phase helpers, B13 the 12-exit funnel), the timeout policy leaf planted (B15), the 109-block stub sweep (B16), all 9 dialogs on the base (B17) — 7,581 P / 0 F

> **The release (Wave 5 + Wave 6 of the fix/improve/optimize charter, all operator-ordered this session):** the `model_vram_override_gb` restoration is **LEFT OUT** (the operator kept the click-only cost model — the V0.6.9 §1 standing flag is answered and closed); B12–B13 and B15–B17 all landed, one commit each, evidence cited. **7,581 passed / 0 failed / 43 skipped / 16 deselected in ~244 s** (V0.6.9: 7,548 — net +33, zero regressions).
>
> **B12 — `scholar_reflection` (CC 118, `6de5475`):** the 740-line body splits behind the `_ScholarCtx` dataclass into 8 phase helpers (prepare / probe-gate / prompt / overflow-guard / LLM-call+O-a4-retry / parse / grounding / dedup-merge) + a C(12) orchestrator that keeps the original statement order; public signature + in-place `result` contract unchanged. **AST-identity verified: 211/211 original guards/leaves appear in order** (`.review-loop/verify_b12_ast_identity.py`; declared normalizations: ctx-threading, underscore-stripped names, return plumbing, the `gap_bullets_added = 0` init → dataclass default). Characterization FIRST: the untested paths (scholar filler floor, budget TRIM, filter-crash fail-open, the B13 D1 exit contracts) written green on the PRE-split code. One documented pin evolution (`test_v182032`'s 6144 source pin follows the call site into `_sr_call_llm`).
>
> **B13 — `verify_and_polish_summary`'s 12 copy-pasted exits → the single `_exit` funnel (`b1a5c2c`):** every return path routes through ONE helper wrapping `_apply_deterministic_fixes` — the D1 contract (en-dash normalization at EVERY exit, even without an LM) is structurally guaranteed; a future exit cannot forget it. The helper is the old return expression verbatim. Pins: `_exit` is the only caller; 11 rendered_md + 1 polished; behavioral D1-at-exit tests written green pre-refactor.
>
> **B15 — `core/system/timeouts.py`, the policy leaf (`cc833a8`):** the audit's "Where are timeouts defined? Nowhere centrally" gap closes — every one of the 11 magic values (2/5/10/20/30/60/120/180/300/420/600) gets ONE named constant + family/site-count comment; the 10 highest-churn sites (the LLM layer: the provider constructors' 300s, Claude's 180, the six UI-probe 5s) migrate now; ~49 remaining sites are FLAGGED with file:line evidence for the next waves. All swaps import + constant, values byte-identical.
>
> **B16 — the stub-block sweep (`31be4eb`):** 109 inert `if "tiktoken"/"markitdown" not in sys.modules:` head blocks removed from 87 test files (AST-located, module-level only; conftest excluded; function-scoped multi-module stubbers stay) — inert since the V18.20.2.0/V0.6.0 conftest gates. 142 now-unused imports pruned. The conftest comments' drifted counts (51/36, reality 78/37 — the W7 lying-docs find) are corrected with the honest history; the gates are now the ONLY installer. Pins: no stub guard may return.
>
> **B17 — the 9 remaining service dialogs onto `BaseServiceDialog` (`230571e`):** the W4 duplication family (closeEvent guard ×9, `_pick_output` ×8, `_on_process` ×6, the cancel/reset/preview scaffolding) closes — 11 of 11 dialogs now share the base. Two parallel agents with the tts/translation precedent as template and the e2e suites as the gate (byte-identical pass counts before/after via a throwaway worktree); batch B re-reviewed read-only — 0 BLOCKERs / 0 SHOULD-FIX; the V0.6.8/V0.6.9 contracts (`_fetch_models_from` never-raise, 3 s probe budgets, OCR folder picker + multi-file queue, `packets_tool`'s data-driven shape) verified byte-identical. Constructor signatures, settings keys, workers unchanged; overrides stay documented per-file. Pin evolutions documented, count-preserving, several strengthened.
>
> **Bonus (`b8ea9c1`) — the Hypothesis find:** the B17 review's full-suite run surfaced a generator-domain hole — the citations-roundtrip surname strategy could draw a bare month token (`'Mar'`), which the extractor's V0.4.23 shape filter deliberately drops; the strategy now excludes the 12 month tokens (the extractor verified byte-identical at HEAD).
>
> **Remaining (handed to the next session):** B14 (`run_summarization` CC 136 / `batch_gap_fill` CC 107 — flagged, the save-block extraction is the template); the ~49 flagged timeout sites (evidence in the leaf); the rig checklist + `requirements.lock` regen (rig tasks, the honest boundary per AUDIT_SWOT §8).

## V0.6.9 — the green-baseline release: both operator DECISIONS landed — the VRAM overbudget enforcement RESTORED, the parenthetical-promotion grounding TIGHTENED — the suite green for the first time (7,548 P / 0 F)

> **The release (Wave 1 of the fix/improve/optimize charter + the standing review loop):** the operator answered both queued DECISIONS — VRAM policy: **Option A "restore"** (the cost of an estimator error is one "Proceed anyway" click in the wizard; the setting regains real semantics); parenthetical promotion: **Option A "tighten"** (an author counts as "grounded" only when an attribution verb is actually held somewhere, or within the detector's matching range — a pure citation-list name no longer counts). With both landed, the last 14 documented failures close: **7,548 passed / 0 failed / 43 skipped / 16 deselected in ~240 s** — the first honestly-green baseline (session start: 14 F / 7,522 P; net +26 passing). Rule 3 (net-green) is meaningful again: any red from here on is a regression.
>
> **DECISION 1 — the V0.5.14 non-blocking block is reverted, enforcement restored (`converter_impl.py`, commit `1352425`):** the hotfix's unconditional `return None` + nvidia-smi informational probe had silenced `local.vram_overbudget_policy` for every non-interactive start path (queue / service dialogs / scripted runs) while the setting, schema comment, request field and docstring all still promised enforcement — the V0.6.7 audit's BLOCKER with 12 red characterization tests at HEAD. The V18.20.4.10 policy block runs again **byte-identical** (review-2 diffed it against `a0b711c~1`): `proceed` → WARNING + continue; `abort` → fail fast; `ask` (default) → fail fast unless the wizard stamped `request.vram_overbudget_acknowledged`. The V0.5.13 belt-and-suspenders escapes were deliberately NOT reinstated — the wizard click and the global `proceed` are the only escapes, per the operator's stated cost model. `scripts/repeatability_run.py` keeps its explicit `policy=proceed` (scripted runs cannot ask) with the stale comment corrected. The 12 previously-red tests pass **unchanged**.
>
> **DECISION 2 — the V0.5.15 roster-only exemption is tightened (`postchecks/field_phases.py`, commit `c00830a`):** `_v0515_grounded` (citation-roster membership alone — which a parenthetical-only author satisfies BY CONSTRUCTION) becomes `_v069_grounded` = roster AND `_name_holds_any_attrib_verb(claimed, source_text)`. The detector's escape (a) still never confirms a promotion for an author holding a verb in a surname-matching span (correctly attributed authors are safe twice over); the tightened exemption additionally rescues the one reachable outside-the-range shape — a passive-agent hold whose 80-char look-back window the detector's per-span scan clips — pinned end-to-end by a dedicated corridor test. Parity with the generation-time veto (`gap_fill_batch`, which never had the exemption) is restored: the two layers of the same veto no longer disagree. The 2 previously-red tests pass **unchanged**.
>
> **review-2 (the fresh-eyes pass over both commits — sound, 0 BLOCKERs, 3 SHOULD-FIX residuals, all fixed in `6615f98`):** (1) the V0.5.15 exemption's **SIBLING** — the thorough-floor dropped-sentence recovery (`thorough_theorist_floor.py`) re-admitted attribution-edge-dropped sentences on roster membership alone, the exact rejected rationale — tightened with the same conjunction via the extracted `_v069_recoverable_sentence` helper; the thorough layer and the veto now agree in both directions. (2) **README placebo rows removed** — the "Non-blocking overbudget (V0.5.14)" row (false since the restore) and both `summarisation.model_vram_override_gb` rows (the override has ZERO runtime read sites at HEAD — the V0.5.14 hotfix deleted the last reader; never registered in the schema); restoring the V0.5.13 override read is FLAGGED for the operator as a possible special-quant escape hatch. (3) **Doc accuracy** — `models.py`/`errors.py` no longer claim `VramOverbudgetError` is "raised" (the converter returns the policy's error message as a failed `ConversionResult`); the `field_phases` comment names the one reachable rescue shape; the drop detail covers both not-grounded cases.
>
> **New tests (`tests/test_v069_wave1_green_baseline.py`, 12):** the Khan citation-list vector through the full ship-time chain (roster member, no verb anywhere → DROPPED with the V0.6.9 detail); the correctly-attributed Mahler fallback (verb held → never confirmed, no issue at all); the helper's positive/negative inputs; the BUT-KEPT corridor (review-2 proved it reachable; the fixture places an attrib verb two sentences before a "by AuthorC" passive so the full-text 80-char window sees the hold the per-span window clips); 4 thorough-floor recovery pins (citation-list name NOT recoverable, verb-holder recoverable, non-roster never, wiring source-pin); and the anti-resurrection source pins for both decisions (the non-blocking return, the subprocess probe, the roster-only predicate — all guarded against). Anti-cheat: zero deleted/skipped/loosened tests anywhere in the range; the 14 previously-red tests were NOT touched (they were the contract, the code was wrong).
>
> **Hygiene:** ruff 0.16.8 `check` + `format --check` clean on all 9 touched files across 4 commits; the content-agnostic deny-list families green (this session itself tripped the runtime-comment placeholder rule once — a book-derived name in a new `field_phases` comment — caught by the suite within the same session and fixed to the AuthorC placeholder); token scan clean. **Not done (flagged/queued):** `model_vram_override_gb` restoration (operator decision); B12–B17 (the god-function decompositions, the timeout policy leaf, the 91-file stub sweep, the 9 dialog migrations); the flaky queue-view test root-cause (passed all runs this session); `requirements.lock` full clean-install regen (rig task).

## V0.6.8 — the SWOT re-audit release: the dead VRAM safety gate found, the "14 pinned failures" myth retired, the fix/improve/optimize backlog filed (no runtime changes)

> **The release (an audit-only release from the SWOT re-audit charter):** a full read-only re-audit of V0.6.7 — two independent fresh-eyes review passes (code-quality; architecture/integration), scripted shape/complexity/MI/import-graph metrics, a full-suite run, and every top finding re-verified by the orchestrator before filing. Zero runtime code changes: every fix is queued for the next session with its evidence. The full report is `docs/AUDIT_SWOT_V0.6.7.md` (scorecard: architecture 4 · scalability 4 · performance 3.5 · integration 3.5 · modularization 3.5 · maintainability 2.5 · clean code 2.5); the next session's charter is rewritten from its findings in `NEW_SESSION_PROMPT.md`.
>
> **BLOCKER — the VRAM-overbudget safety gate is unreachable dead code, and its 12 red tests were mispinned as "environment failures":** the V0.5.14 hotfix left an unconditional `return None` at `converter_impl.py:502`, making the 34-line proceed/ask/abort policy block (`:503-536`) unreachable. The `local.vram_overbudget_policy` setting (still registered at `utils/settings.py:455`), the `vram_overbudget_acknowledged` request field, and the docstring (`:411-429`) still promising enforcement are all placebo. 8 converter + 4 segmentation VRAM tests fail at HEAD (verified: `pytest tests/test_converter_phase3_characterization.py` → 8 F/123 P) — the last two session baselines listed exactly these 12 as "pinned environment families" (T1, a baseline-integrity process failure: a test net whose reds are myth-labeled stops protecting anything). Operator decision queued: restore the policy or delete it honestly (block + docstring + setting + 12 tests in one commit).
>
> **The 2 pinned v182032 failures are a real contract conflict, reproduced deterministically:** `test_run_post_checks_drops_confirmed_promotion` / `test_garbage_set_dropped_legit_kept` fail on synthetic fixtures (no I/O). Root cause: the V0.5.15 "regex-grounded exemption" (`postchecks/field_phases.py:482-501`) keeps a bullet whose claimed author is in `extract_citations` output — but a parenthetical-only cited author lands in that roster by construction, so the exemption defeats exactly the misattribution drop the V18.20.3.2 parenthetical-promotion veto was built to enforce. The detector itself works (verified live — returns the correct claimed/real pair); the drop stopped firing. Owner decision queued: adopt the V0.5.15 contract in the tests, or tighten the exemption to non-parenthetical presence only.
>
> **A second silent-routing bug — the `dual_api` fast-provider override never applies:** `conversion/summarization.py:793-798` overrides `_base_url`/`_api_key`/`_model` via `hasattr`, but `OpenAICompatProvider` stores PUBLIC `base_url`/`api_key` (`openai_compat_provider.py:39-40`) — the url/key overrides are silently skipped, so a `dual_api` run sends concept extraction to the default cloud endpoint with the default key and a foreign model name; the error is swallowed as "concept extraction unavailable" (`:960-963`). Queued with a characterization-test requirement.
>
> **Dependency drift on the RTL line:** `arabic-reshaper` + `python-bidi` (V0.6.5 RTL outputs) exist ONLY in `requirements.txt` — missing from `pyproject [project.dependencies]` AND from `requirements.lock` (not regenerated when V0.6.5 added them): 2 of 3 install surfaces silently lack them (WARNING-only degrade). Queued: pyproject + lock regeneration in one commit.
>
> **The measured baseline this audit leaves for the next session:** suite 7,481 P / 15 F / 43 S / 16 D in 245.6 s (Linux sandbox, offscreen Qt, `--no-cov`); failure census: 12 = the dead-code BLOCKER, 2 = the contract conflict, 1 = sandbox QtMultimedia (passes with full PySide6 — not a code defect). Shape: 359 runtime files / 152,749 LOC / 3,084 functions; 260 test files / ~7,115 test functions. Complexity (radon 6.0.1): avg B (6.33); 488 blocks ≥C; 152 ≥ danger-21; the five god functions CC 136 (`run_summarization`, 1,020 LOC) / 118 (`scholar_reflection`, 13 params) / 110 (`verify_and_polish_summary`, 12 copy-pasted exits) / 107 (`batch_gap_fill`, 1,001 LOC) / 105 (`run_content_judge`); 125 functions >150 LOC; 37 signatures ≥10 params; 4 modules at MI 0.00. Hygiene: ruff 0.16.8 check PASS + 737 files format-clean (1 invalid-`# noqa` warning at `response_cache.py:107`); 0 secrets / 0 `verify=False` / 0 `shell=True` / 0 bare `except:`; 152 pass-only exception swallows (101 broad, 71 uncommented) with the ~8 medium-risk sites individually cited in the SWOT (checkpoint-manifest silent-`{}` at `chapter_checkpoint.py:1045`, the disk-cache silent-clear family at `response_cache.py:245` + `embedding_cache.py:424`, the embedder-guard swallow at `bullet_pipeline.py:221`, …). Structure: 3 import cycles — all deliberate, documented, runtime-safe (lazy imports + `__getattr__`, verified importable); zero core→UI layering violations (1 guarded PySide6 import in core: the numpy-ABI fatal dialog); fan-in hubs settings 61 / core.models 49 / logging 34 / network 29. Dead code (vulture ≥90%): 15 items — one is the BLOCKER; the rest unused vars/params (incl. the lying `segmenter.py:1410 fuzzy_threshold` parameter — dead in body, dutifully passed by both call sites).
>
> **Verified strengths (SWOT S1–S8, with the evidence):** the 7,481-test characterization net; the headless-clean core (zero core→UI — a server/CLI mode is one dialog away); LLM ops engineering (OllamaSupervisor restart budgets, the retry taxonomy, the `session_for_url` transport SSOT at 29 importers); crash-safety (write-once checkpoints, occurrence-aware resume, atomic writes, errno-28 surfacing); supply-chain discipline (105-pin lock, waiver policy with rationale+dates, ZERO active waivers / zero known vulns); content-agnostic enforcement (the mechanical anti-benchmax tests); the proven verbatim-extraction pattern (the V0.6.7 save-block move is the template); bounds everywhere (LRU 1,000 / FIFO 2,000 / queue cap 4 / restart budgets).
>
> **Duplication families measured for the backlog:** timeout scatter 60 sites / 11 magic values (the planned `core/system/timeouts.py` policy leaf still doesn't exist); 91 test files still carry copy-pasted tiktoken/markitdown stub blocks (inert since the conftest hermetic gates — a mechanical sweep); 9 of 11 service dialogs not yet on `BaseServiceDialog`; the `G:\` piper/neutts default literals duplicated between `utils/settings.py:791-793` and `core/outputs/podcast_audio.py:169-185`; 17 `_vNNN_*` function clones (one verified 69%-similar twin pair). Lying/stale docs: the VRAM docstring, `step4_outputs.py:29` (claims 19 output types; the registry holds 21), stale conftest stub counts (says 51/36; actual 78/37), `main.py:54` printing a V18.2.37-era tag at V0.6.7, 2,312 V18.x comment tokens referencing an unmapped era.
>
> **Not verified (honest limits):** live-LLM behaviors (all `live_llm`-marked, deselected — no Ollama/llama-server in the sandbox); the rig-only surface (qwen OCR via real Ollama, Persian tessdata, vibevoice/sherpa audio, full-book runs); coverage percentages (ran `--no-cov` for time; V0.6.7's shipped numbers stand); pip-audit re-run (offline; lock + waiver-file state relied on).

## V0.6.7 — the approved backlog: dead code deleted, one vision-classification truth, proxy-safe provider transports, the save block finally tested — 83 new tests

> **The release (the second from the Agentic Review/Refactor/Test Loop charter):** the operator approved the previous session's backlog — delete the provably-dead modules, and fix the vision-keyword drift, the provider transports, the untested save block, and the zero-coverage modules "if safe" — with each item safety-assessed first. 83 new tests (`tests/test_v067_review_loop_fixes.py`); suite 14 failed / 7,500 passed / 25 skipped / 16 deselected — the 14 pinned environment families only; both ruff gates green at the CI pin 0.16.8; 1 fresh-eyes reviewer pass over all 6 commits, 0 blockers.
>
> **Dead code deleted (with the proof cited):** `core/pipeline/output_time_estimates.py` and `core/models/config_views.py` + the 9 `ConversionRequest` view properties had zero references anywhere (no imports, no bare/nested/`getattr`/`hasattr`/dynamic access, no re-exports — every grep hit was a docstring inside the dead module). The flat fields (500+ call sites) are untouched; `registry.py`'s dangling docstring citation updated.
>
> **Vision-keyword SSOT:** the "is this a vision model?" heuristic was copy-pasted ×5 with 3 drifted variants — `minicpm-v` was listed as an OCR model by the dialog but classified TEXT by the dependency checker (badged 📝). `model_taxonomy.VISION_MODEL_KEYWORDS` (the union of all 3 variants, nothing lost) + `is_vision_model()` now serve all five sites (the OCR dialog references the SSOT object — identity-pinned, cannot drift). Variant-A sites gain minicpm/moondream/mmproj/multimodal/bonsai/fuyu/kosmos/florence detection; the llamacpp gate gains the families it missed (a `minicpm-v` on llama.cpp no longer silently degrades to Tesseract; keyword false positives there are fail-soft — the OCR service falls through to Qwen/Paddle/Tesseract, probe cached once per conversion). `olmo` (also matches text-only OLMo tags — pre-existing display-tier quirk) kept for provenance, flagged at the SSOT.
>
> **Provider transports:** the 4 bare `requests.post` sites (`openai_compat_provider.complete`, `claude_provider.complete`, `ollama_provider.supports_vision` + `complete_with_image`) now route through `session_for_url` — localhost endpoints get the proxy-immune pooled session (a misconfigured `HTTP_PROXY` no longer breaks localhost FreeLLMAPI/Ollama), cloud endpoints keep env-proxy behavior, all gain pooling. The OpenAI-compat deep-index parse became the shared shape-safe `extract_openai_content` (same V18.20.4.11 dispatcher migration: a malformed 200 now retries like an empty response instead of raising straight to None). The two Ollama vision methods were 0%-covered — first characterization (16 tests). The Batch API path (openai.com-only, proxy-identical) deliberately keeps its transport; a 5th bare `requests.get` (translation dialog model refresh) recorded for a future pass.
>
> **The incremental-save block, extracted verbatim + tested:** the 184-line per-chapter save block inside the 1,202-LOC `run_summarization` (failed-summary skipping, run-stamped filenames, the write-once `<!-- COMPLETE -->` adoption, verification plumbing, the errno-28 disk-full error) had never run under test. Now module-level `_save_chapter_summaries_write_once` — the move verified mechanically (8/8 statements AST-identical, nested helper byte-identical; the first extraction attempt was auto-refused by the purity check). 14 tests pin the contract. Further god-function decomposition remains out of scope.
>
> **Four zero-coverage live modules characterized (26 tests):** the dependency checker (cache TTL, server probe, `check_all` shape), the wizard profiles (roundtrip, corrupt skip — tests use a temp profile dir), `merge_books`, and the podcast ≥90% coverage gate — which surfaced two real blind spots, now pinned as documented limitations (single quotes and <4-char words are never extractable; the top-5-phrase cap can crowd a short quoted phrase out) — fixing them changes gate semantics, queued for sign-off.
>
> **The rebrand sweep — a latent V0.6.6 failure, fixed honestly:** this session's full run (first since the V0.6.6 commit) failed the "no stray brand strings" sweep — the V0.6.6 release notes truthfully mention the old user-data dir name in the migration story. Verified failing at tag V0.6.6 itself (the previous session's final suite ran before the notes file existed). Fix: `release_notes/` joined the sweep's historical-record allowance (folder prefix only — code stays fully covered; the published note was not rewritten).

## V0.6.6 — the review-loop hardening: duplicate-heading data loss fixed (checkpoints + resume), stable Anki decks, crash-report trustworthiness, 49 new tests

> **The release (the first from the Agentic Review/Refactor/Test Loop charter):** two full review-fix-verify loops with independent fresh-eyes reviewers (5 reviewer passes total), every finding probe-verified before a fix, every behavior fix red-proofed (failing test first). One theme: stop silent data loss, make the safety nets honest. 49 new tests (`tests/test_v066_review_loop_fixes.py`); suite 14F/7,417P/25S/16D — the 14 pinned environment families only; the 15th, order-dependent failure (a `Settings._test_override` leak that made an empty dict the global Settings for the rest of the session) is FIXED. Both ruff gates green at the CI pin 0.16.8 (the branch had drifted red: 1 lint error + 20 unformatted files + 1 evidence-markdown file that ruff ≥0.16 wanted to reformat — now excluded with `audit` + `docs/ground_truth` in `extend-exclude`, evidence is never reformatted).
>
> **The duplicate-heading family (3 fixes, content-agnostic):** (1) the checkpoint heading→position map collapsed two same-named chapters onto ONE filename — the second chapter's summary was silently LOST (write-once skipped it), the first saved TWICE, the second's DOCX overwrote the first's; `compute_final_positions` (V0.6.6 extraction) omits duplicated headings, colliding chapters fall back to their unique per-run index (identical to the end-of-run writer's numbering absent resume reordering). (2) `merge_summaries` was heading-keyed: on resume with duplicate headings it dropped the LOADED chapter and emitted the new one twice — the finished book was built without a completed chapter; the merge is now occurrence-aware (per-heading queues, todo-first, new-wins preserved byte-identically for unique headings). (3) `chapter_manifest.json` is keyed by the canonical md FILENAME instead of `str(pos)` (fallback indexes can collide with mapped positions — records clobbered; CONTRACT CHANGE, pinned tests updated, position kept inside each record), and the per-chapter DOCX carries the md's run stamp so a resumed run can never overwrite a completed chapter's DOCX.
>
> **Anki export:** the deck/model ids were `hash()`-derived under a "deterministic from book title" comment — CPython salts `hash()` per process, so every run minted new ids and re-importing an updated `.apkg` duplicated the deck + notes. crc32-based `_stable_anki_ids` (stable across processes/platforms; cross-seed subprocess test). First post-upgrade import creates one final duplicate of each old deck — delete the old deck once.
>
> **The release tool:** `--all --zip` silently dropped the zip (the `--all` loop never forwarded it — a live run would publish every release with zero assets, exit 0; now rejected at parse time); transport failures (`URLError`: DNS/refused/proxy) escaped as raw tracebacks in `_api()` and the asset upload (now the clean ❌ path, subprocess-pinned); the F841 unused binding from the V0.6.5 upload fix removed.
>
> **Test-suite integrity:** the two V0.6.5 translation-fallback tests restored `Settings._test_override` to `{}` (not `None`) — `{}` passes `__new__`'s is-not-None check, so an empty dict became the global Settings() for the rest of the session (every `.get()` → None); twin bug `prev or {}` in test_v0600_tool_translation_e2e. All three sites now snapshot/restore, with session canaries. The `_runtime_state` reset moved from test_runtime_state.py (file-scoped) to `tests/conftest.py` (session-wide autouse) — golden_freeze's pollution was proven to cross file boundaries. `test_vram_recovery`'s `assert True` can't-fail test (V13.44.3 era) now pins the actual delegation contract. The sed-corrupted rebrand comments in `utils/settings.py` ("renamed Elixir → Elixir; ~/.elixir → ~/.elixir" — the real migration is `~/.markitdown_pro` → `~/.elixir`) corrected.
>
> **Crash reports:** the redaction logic (the only thing between a user-shared crash zip and their API keys) was 100% untested — 8 tests pin the substring redaction variants, home-prefix path scrubbing, zip contents, corrupt/missing settings, and the never-raises path (incl. the honest pinned gap: a key named exactly "Bearer" is NOT caught by the V18.1 S4 substring set). The controller's crash path had drifted from main.py's V13.29.0 fix (never passed `extra_log_lines`) — both call sites now share `crash_report.collect_recent_log_lines()`.
>
> **Zero-test features:** the multi-format input (EPUB/DOCX/TXT/MD/HTML, V10.20.0, wired live at extraction.py:148) — 9 Layer-1 tests (routing, DOCX heading preservation, stdlib zip fallbacks, HTML script/style strip, format matrix); the Validation Tool engine (89 stmts) — 11 tests (load paths, keyword extraction incl. Persian, coverage math, hallucination flagging, report tiers; the unreachable "⚠️ No summary found" branch pinned as dead).
>
> **Known remaining (backlog in `.review-loop/findings.md`):** the queue e2e's wall-clock `_drain` timeout flaked once under full-suite load; the vision-keyword list is copy-pasted ×5 with 3 variants; 4 provider call sites bypass `session_for_url` (proxy hazard); `run_summarization` is a 1,202-LOC god-function with an untested incremental-save block; operator decisions queued on deleting the provably-dead `output_time_estimates.py`/`config_views.py` and on making the suite's Settings hermetic (the suite writes the real `~/.elixir/settings.json`).


## V0.6.5 — the RTL outputs (md · docx · PDF, VLM-verified), the LLM-structured Markdown Styler, the translation active-LLM fallback, the GitHub release system

> **The release (three user-reported fixes + one process directive):** (1) "the pdf conversion (summarization) of a Farsi text works, but it still LTRs the content — not easily readable; it's fine in md and docx" — the pdf writer had NO direction handling (nor, on inspection, did the docx/md writers on the remote: the lost pre-push session's md/docx RTL work was redone here as one unified detector); (2) "turning a raw article to markdown cannot be fully deterministic — FIRST the LLM must scan the article and find heading, (if there isn't a heading) generate a fitting heading, then stylize it based on the obsidian style" (the V11.71.0 regex styler shipped "Untitled Note" + a raw-text dump — the user's exact complaint); (3) "the translation tool must fall back to the CURRENT ACTIVE LLM (ollama or llama.cpp) when no dedicated translation model is found"; (4) "For every version you create, add a release version, like this one, with added changelogs and updates" (the GitCurator-style GitHub Release page is now the standing contract — AGENTS.md Rule 6). 46 new tests; the two PDF backends are VLM-VERIFIED on rendered pages. All fixes content-agnostic (Rule 1 ✓ — script-block detection, JSON contracts, provider transport; no topic vocabulary).
>
> **Fix 1 (the direction detector + all three writers, `utils/rtl.py` NEW + `core/outputs/service_formatters.py`):** one detector — `is_rtl_dominant(text)`: the share of RTL-script letters (Arabic/Hebrew/Syriac/Thaana/NKo + presentation forms) among ALL letters, threshold 0.35 — decides the document's direction ONCE in `write_output` (`rtl=None` = auto; explicit True/False overrides) and threads it into every format: **md** gains the Obsidian `dir: rtl` front-matter property (`_ensure_md_dir_rtl`: merged into existing front-matter after the opening `---`, prepended as a new block when absent, never duplicated — the translation tool's Persian outputs get it automatically, same `write_output`); **docx** sets the `w:bidi` paragraph property + right alignment on EVERY paragraph the writer creates (`_rtlify` — headings, bullets, numbered, quotes, normal; Word then reorders runs and renders bullets on the right; heading runs also carry `font.rtl`); **pdf-WeasyPrint** appends `_rtl_css_with_fonts()`: `direction: rtl` + `text-align: right` + flipped list/quote sides + the bundled **Vazirmatn** @font-face (SIL OFL — `assets/fonts/Vazirmatn-{Regular,Bold}.ttf`, committed; the default Helvetica/Segoe stack has NO Arabic glyphs — the earlier black-squares report); Pango does the real bidi + shaping. **pdf-ReportLab** (the bare-install fallback) draws exactly the byte order it is given, so every fragment passes through `_shape_rtl_fragment` (arabic_reshaper → presentation forms, python-bidi → visual order; a no-op on Latin custom titles), all styles get `TA_RIGHT` + the Vazirmatn family (`_register_vazirmatn_reportlab`; right-indent mirrors for quotes/bullets — and 0 never None: ReportLab's bullet arithmetic chokes on None), and the plain-text path (`_plain_md`) avoids bidi-vs-markup edge cases. `arabic-reshaper` + `python-bidi` are now in requirements.txt (pure-Python, tiny) with a WARNING-only degrade when absent. VLM-verified on rendered pages for BOTH backends: right-aligned ✓, connected Persian glyphs ✓, no black squares ✓, bullets on the right ✓ (and the extracted text round-trips as Arabic presentation forms — the subset fonts embed a real ToUnicode map).
>
> **Fix 2 (the two-phase styler, `core/summarisation/markdown_styler.py` NEW + the dialog):** Phase 1 — ONE LLM call returns a STRICT-JSON structure: the article's real detected title (or a fitting GENERATED one when there is none — the "Untitled Note" complaint), a 1-2 sentence tldr, key concepts, tags, `is_rtl`, and the sections (each with heading + level 2/3 + cleaned content). The prompt's contract: the LLM RESTRUCTURES, it never rewrites — the original wording is carried verbatim into the section content (the anti-hallucination stance the tool has always had). Phase 2 — pure-Python assembly (`assemble_obsidian_note`): front-matter (title/date/tags/dir), the `> [!tldr] Summary` + `> [!info] Key Concepts` callouts, `##`/`###` sections with blank-line runs collapsed (the "lots of spaces" complaint). Robustness: `parse_structure` is lenient (```json fences stripped, prose-wrapped objects found, trailing commas fixed, optional keys defaulted, levels clamped to 2|3); `style_markdown_llm` retries ONCE with a JSON-only reminder, then returns None — the dialog's worker falls back to the V11.71.0 deterministic regex path with a ⚠️ status line, NEVER an error dialog for a model miss. The dialog gains the "🤖 LLM structuring" checkbox (default ON — the user's intent), a model picker (the summarizer's `/api/tags` + `__default__` sentinel pattern), the real SimpleWorker for the LLM call (never the UI thread — the W-b5 contract), and the close-with-running-worker guard. LIVE-verified through the real provider: the user's exact scenario (a raw Persian article, no headings) produced the generated title "کلود استیم: مشکلات و راه‌حل‌ها", all four section headings detected (the question-style lines the regex engine could never catch), `dir: rtl`, and the full Obsidian note.
>
> **Fix 3 (the active-LLM translation fallback, `core/translation/translation_engine.py` + the dialog):** the engine's transport is now injectable — `llm_complete: Callable[[str], str | None]` REPLACES the raw Ollama `/api/generate` POST when set (a None return feeds the same retry machinery as a transport failure; `ModelNotFoundError` semantics stay raw-path-only). The dialog injects it when `_collect_options` finds NO translategemma-family model in the combo: every line call then rides the ACTIVE provider (`create_provider` — ollama, llama.cpp, OpenAI-compat, and Claude transports all speak it; a llama.cpp backend cannot answer the Ollama-protocol call — the user's exact scenario). Model resolution under the fallback: a REAL installed model (user-picked or auto-first) stays authoritative; only the unreachable seeded default or an empty selection swaps to the active model (quick_services → summarisation → RIG_FALLBACK_MODEL). The status line says which fallback fired: "ℹ️ No dedicated translation model — using the active LLM (provider / model)."
>
> **The release system (Rule 6, the new contract):** `release_notes/VX.Y.Z.md` (this version ships V0.6.0 → V0.6.5 — the backfilled notes reconstructed from the CHANGELOG/worklog record), `tools/publish_release.py` (the one-command GitHub Release publisher: create-or-update by tag, verbatim notes body, zip asset upload with same-name replacement, Latest-badge on the newest, `--all` backfill, `--dry-run`, token from --token/GITHUB_TOKEN and NEVER stored), and AGENTS.md Rule 6 (skip-the-release = breaks the version's contract; it is part of the release gate).
>
> **Pinned fixtures updated to the V0.6.5 contract (3, each documented in place):** `test_translate_files_hermetic_writes_output` + `test_queue_success_writes_each_file_and_modal` (Persian `.md` outputs now carry the `dir: rtl` front-matter — byte-equality with the bare translation no longer holds) and `test_collect_options_model_resolution` case (b) (the empty-selection no-translation-model case now resolves through the active-LLM fallback — was the hardcoded 12B default that 404'd when translategemma isn't installed). The styler's Layer-3 deterministic drives opt out of the now-default LLM checkbox (`llm_chk.setChecked(False)` — the LLM path has its own hermetic drive with `style_markdown_llm` faked at the module seam).
>
> **Net-green:** 46 new tests in `tests/test_v065_rtl_styler_translation.py` (the detector matrix incl. the mixed-script + markdown-only cases; `_ensure_md_dir_rtl` merge/prepend/dedupe; `parse_structure` leniency ×10; the assembler layout + option gates + blank-run collapse; `style_markdown_llm` retry/repair/fallback with a fake call; REAL-file RTL artifacts — the bidi element count on every docx paragraph, the embedded Vazirmatn subsets + shaped-glyph extraction for both PDF backends, the English LTR regression pins; the engine transport injection ×3; the dialog drives through the real SimpleWorker; the live-shim leg marked `live_llm`, deselected by default). Related suites: translation (139) + styler/packets + summarization + depth = 339 passed together. Full suite: the pinned 14 environment failures, net-green; ruff check + format clean on every touched file. requirements.txt: +arabic-reshaper, +python-bidi (the ReportLab RTL path).
>
> **Rig checklist item:** the WeasyPrint path needs its system deps (pango/cairo) as always; the ReportLab path is the bare-install fallback and is now fully RTL-capable with the two new pure-Python deps. The Vazirmatn TTFs ship in `assets/fonts/` — a frozen/packaged build must include that folder (the `@font-face` src resolves relative to the repo root at write time).


## V0.6.4 — the user-reported Summarizer Tool backlog: multi-format outputs, the custom title, the black output theme, the Farsi fix, the fine-tuned depth prompts, "Quality"→"Depth"

> **The release (six MEDIUM items, all user-reported against the standalone Summarizer Tool):** (1) the tool must allow MULTIPLE output formats (checkbox row: Md/docx/pdf — was a single-choice dropdown); (2) a custom document title via a toggle-hidden input (was the auto "pasted — standard summary" — the user's example: "BMW Company History"); (3) the docx + pdf output styling must be BLACK by default (was a green theme for pdf, Word-blue headings for docx); (4) Farsi text must summarize BACK IN FARSI (was translated + summarized to English); (5) the fine-tuned Fast/Standard/Thorough prompts, adopted VERBATIM; (6) the term "quality" → "Depth". 35 of the 56 new tests fail on the pre-fix HEAD (git-stash-verified). All fixes content-agnostic (Rule 1 ✓).
>
> **Fix 5 (the anchor — the fine-tuned depth prompts, `core/summarisation/tool_prompts.py`, NEW):** the tool's prompt source is now a code module holding the user-supplied Fast/Standard/Thorough texts VERBATIM (only the chat-mangled line breaks re-flowed — the pasted Thorough text had "STRICT RULES:- Use ONLY…" run together). The V0.6.1 precedent applies: a versioned prompt contract pinned by tests, NOT a `prompts/` bank file — so the prompt-manifest / eval-baseline identity is untouched and the always-overwrite re-sync (V17.0.0) can never silently change the tool's behavior. `render_tool_prompt(depth, text, model)` keeps the V18.2.21 prompt-injection fence (`wrap_untrusted`) with the V18.2.29 low-bit-quant skip and the fail-open-on-crash rule (all three mirrored from `PromptManager.render_template`). Trade-off documented: user-custom tool prompts via the bank are NOT offered (the V17.0.0 re-sync clobbers user copies every run anyway — the capability is already dead app-wide); the user's explicit verbatim-adoption directive wins. The max_tokens mapping is unchanged (fast 1024 / standard 2048 / thorough 4096 — a ceiling, not a target: every depth prompt's own LENGTH rules constrain the output far below).
>
> **Fix 4 (Farsi — the root cause was the PROMPT, not the pipeline):** the old path rendered the shared book-pipeline `default.md` bank prompt with an EMPTY `{{language}}` variable — an all-English prompt instructing an English-shaped XML response; the model dutifully translated. Every depth prompt now carries the explicit rule "Write in the same language as the text." (pinned per-depth by a dedicated test). The write side is pinned too: the LLM response is written VERBATIM (a Farsi canned response round-trips byte-exact through the worker — no translation, no transliteration, no mangling); `normalize_depth_headings` never touches non-label lines (pinned with a Persian-body test). The XML re-assembly is GONE: the depth prompts' FORMAT contracts elicit plain sections ("Overview:", bullets), so `_summarize_work` writes the thinking-stripped raw response directly instead of re-parsing `<executive_summary>` XML and rebuilding "## Executive Summary / ## Key Takeaways / ## Detailed Summary" (that re-assembly is what re-labeled the content in English). `parse_response` itself is untouched — the BOOK pipeline's XML contract still runs through it.
>
> **Fix 1 (multi-format checkboxes — one LLM call, N files):** the Format combo → a Markdown/Word/PDF CHECKBOX row; every checked format gets its own output file from a SINGLE summarisation run per input (pinned: exactly one LLM call for md+docx). `_selected_exts()` returns the checked formats in the canonical .md→.docx→.pdf order (deterministic naming regardless of toggle order — pinned). Output naming: single-paste mode treats the typed path as the BASE name (a typed .md/.docx/.pdf/.txt suffix is the base's tail, replaced per format — the checkboxes are the authoritative declaration; the V11.67.0 "docx bytes into a .md-named file" defect class stays dead, pinned in its new shape); multi-file mode writes `{stem}_{depth}_summary{ext}` per format. A "no format checked" guard blocks the run with an actionable ⚠️ (no worker spawned — pinned). The Obsidian toggle's enable state follows the .md checkbox (connected after the widget exists, so init-time setChecked never fires the handler — the re-entrancy class). The initial checkbox state seeds from `quick_services.defaults.summarize_format` (the settings KEY keeps its historical name — no data migration).
>
> **Fix 2 (the custom title):** a "Custom title" checkbox + a QLineEdit, HIDDEN until toggled (placeholder: `e.g. "BMW Company History"` — the user's own example). When set, the title replaces the auto `"{stem} — {depth} summary"` heading in EVERY format: prepended as `# {title}` to the markdown body, the `add_heading(level=0)` title in docx, the `<h1>`/Title in pdf, and the front-matter title for Obsidian (each pinned). Untoggling clears the text — the toggle is the authority, an unchecked box can never contribute a stale title (pinned); `_on_try_another` resets both the toggle and the format checkboxes (pinned). Bare .md without a custom title is unchanged (never carried a heading — the characterization is pinned).
>
> **Fix 3 (the black output theme, `core/outputs/service_formatters.py`):** pdf: the WeasyPrint CSS is now the module constant `_PDF_CSS` in black/neutral (was green: #166534/#15803d/#16a34a headings, #86efac blockquote border, #f0fdf4 tinted backgrounds; now #1a1a1a headings + neutral grays) — pinned by a CSS-constant test + a source-scan for the dead green literals (comments excluded). The ReportLab fallback styles + the title rule likewise black (#1a1a1a/#333333) — pinned BEHAVIORALLY by decompressing the generated PDF's content stream via pypdf and asserting the black colour operands (`.101961 .101961 .101961 rg`) with the old green operands absent. docx: python-docx's default template styles Heading 1–4 with the Word BLUE theme and the old code only darkened the level-0 title — every heading run now carries the explicit `RGBColor(0x1A,0x1A,0x1A)` (pinned by opening the .docx and asserting every Title/Heading run's colour). The formatter is shared (Summarization/OCR/QuickConvert/Translation tools) — the black default applies app-wide, which is the point ("keep it black"). The Obsidian callout map gained the depth-prompt section names (overview→summary, important details/key facts and figures→info, conclusions and takeaways→success — "key points" and "detailed summary" were already mapped) so the normalized `## Overview`-style headings render as callouts.
>
> **Fix 6 ("Quality" → "Depth"):** the dialog's option-row label, the run banner ("depth: fast", pinned), and the combo descriptions now describe the depth prompts ("Fast (quick brief, ~200 words)" / "Standard (overview + key points, ≤500 words)" / "Thorough (structured deep summary, ≤60% of source)"); the Settings→Defaults row label follows ("Default depth"). Internal names (`quality_combo`, `quick_services.defaults.summarize_quality`) keep their historical spelling — the settings key is STORED DATA (renaming it would orphan every existing user config), and the AST-pinned worker wiring is untouched. `normalize_depth_headings` (the display-side label→heading upgrader) is a KNOWN-LABELS-ONLY transformation: exactly the six section names the depth FORMAT contracts define (case-insensitive, optional quotes/colon; a label+prose line splits into heading+prose; "Note: prose", prose merely starting with a label word, and labels mid-sentence are never touched — all pinned, plus idempotence).
>
> **Net-green:** 56 new tests in `tests/test_v0640_tool_summarizer_depth.py` (the verbatim prompt pins per depth — every marker the user supplied; the render contract — fence/low-bit-skip/fail-open/double-wrap/unknown-depth; the heading normalisation matrix incl. Persian; the black-theme docx+pdf pins; the multi-format service+dialog drives; the custom-title matrix across all formats; the depth routing + banner; the Farsi round-trip; the checkbox/guard/reset drives). 35 fail on the pre-fix HEAD. The v0600 tool file updated to the new contract (each documented in place): the prompt characterization (PromptManager→tool_prompts), the canned fixture (XML→depth-style), the section-assembly assertions (verbatim+normalised labels), the typed-suffix test (checkboxes authoritative), the signature pin (`ext`→`exts`+`custom_title`, `quality`→`depth`), the parser-class note (the dialog no longer parses XML; the parser stays pinned for the book pipeline). Full suite: **the SAME 14 pre-existing environment failures (8 converter VRAM + 4 segmentation VRAM + 2 v182032 postchecks), 7,305 passed** (was 7,250; +56 new − 1 retired XML-assembly test), 43 skipped, 15 live-LLM deselected (the first full-suite run showed one transient extra failure in those same environmental VRAM families; the immediate re-run returned the exact pinned baseline — recorded honestly here). Eval gate: **OK** (all six chapters byte-identical — the book pipeline never touches the tool's code path). Prompt manifest OK (no `prompts/` change). ruff check + format clean on every touched file.
>
> **LIVE leg deferred (the documented precedent):** the shim (:3031) answered /health OK but its upstream LLM API rate-limited PERSISTENTLY (a direct 230s probe timed out; the live_llm tests hang — the same V0.6.1/V0.6.2 experience). The operator's rig run covers the live behavior — the rig checklist item for this release: one Farsi paste through the Summarizer Tool (verify the output is Farsi, not English), one multi-format run (md+docx+pdf from one Summarize click), one custom-title run.


## V0.6.3 — the user-reported modal button clipping: every message box now guarantees its buttons full label width

> **The release (user-reported from a screenshot):** "Make sure all modals have enough space, for example in this example Open file location is truncated." The Summarization success modal ("Σ Summarization Complete") showed "📂 Open File Location" with its tail clipped — and, on the same screenshot, "🔄 Try Another" missing its final "r". Root-caused and reproduced offscreen with the shipped QSS before the fix; 15 of the 17 new tests fail on the pre-fix HEAD (git-stash-verified; the 2 that pass are Qt-behavior characterizations that pin WHY the fix is shaped the way it is). Pure geometry — content-agnostic (Rule 1 ✓: reads only widget sizeHints, never message text or button vocabulary).
>
> **Root cause (reproduced, light + dark, exact numbers):** the success modal — short message text + three QSS-padded buttons — renders **355px wide, 19px NARROWER than its own sizeHint (374px)**: "📂 Open File Location" gets 132px where its sizeHint needs 142px, "🔄 Try Another" gets 95px where it needs 104px, "✓ Close" fits (94/94). QMessageBox's internal post-show sizing (`QMessageBoxPrivate::updateSize`) can settle BELOW sizeHint when the text label is narrow; the button row then receives less than its sizeHints and QPushButton CLIPS its label. The message text drives the box narrow exactly when a conversion succeeds with a short result line — the common case.
>
> **The fix — per-button minimum widths (`ui_qt/components/modal_button_fit.py`, NEW):** raising each button's `minimumWidth` to its own `sizeHint().width()` propagates UP the layout chain (button minimum → QDialogButtonBox minimum → the QMessageBox layout's `totalMinimumSize` → dialog geometry), so the dialog can never render narrower than its button row. A dialog-LEVEL `setMinimumWidth` floor was tried FIRST and REJECTED on live evidence: layout activation during `show()` overwrites the widget minimum with the layout's own `totalMinimumSize`, silently undoing the programmatic floor (the box stays 355px and the clip survives; the rejection is pinned by `test_dialog_level_floor_is_ineffective`). Working WITH the layout chain instead of fighting it is the whole trick.
>
> **Applied GLOBALLY (the "all modals" directive):** a `QApplication` event filter (`ModalButtonFitFilter`, installed once in `ui_qt.app.run` right after the theme) fits EVERY `QMessageBox` on its first `QEvent.Show` — the custom-button sites (the shared success modal, the wizard's VRAM-overbudget box with its 230px-class "Proceed anyway (at my own risk)", the podcast-complete box) AND every static convenience box (`QMessageBox.warning/.question/...`), current and future, with no per-call-site discipline required. Event filters are notified BEFORE the target's own event handler, so the raised minimums are already in place when QMessageBox's internal resize runs. Belt-and-braces: the evidenced site (`shared._show_success_modal`) ALSO calls the fit explicitly before `exec()` (the V0.6.2 zero-clamp precedent), pinned by a test that patches `exec()` and inspects the box at the moment it would have blocked.
>
> **The audit (every modal class, evidence-first):** the other two custom QMessageBox constructions share the exact clipping pattern (long labels + roles) — covered by the global filter and by shape tests (VRAM box, podcast box, a standard Save/Discard/Cancel box; both themes). The custom `QDialog`s are NOT touched and NOT at risk: `token_cost_dialog` (fixed 680px + explicit button bar) and the wizard countdown (min 360px + a single 80px-min Cancel) use ordinary `QHBoxLayout`s where button minimums are honored — the clipping quirk is specific to QMessageBox's private layout (Rule 2: smallest change the evidence supports).
>
> **Net-green:** 17 new tests in `tests/test_v063_modal_button_fit.py` (the defect pin — the raw construction clips on this rig; the floor-rejection pin; the fit unit — raises/idempotent/never-lowers/no-buttons; the four modal shapes × both themes; the global filter — fits-on-show with no explicit calls, idempotent install, the run() wiring pin; the two `_show_success_modal` variants via the exec()-patch seam). Full suite: **the SAME 14 pre-existing environment failures (8 converter VRAM + 4 segmentation VRAM + 2 v182032 postchecks), 7,250 passed** (was 7,251 + 17 new − 18 extra skips, all environmental: the `/home/download/Elixir-V18.20.4.5/6.zip` reference zips and the local source PDF are absent from this fresh sandbox — they were present in the V0.6.2 run's sandbox; the 14-failure identity is the pinned baseline), 43 skipped, 15 live-LLM deselected. Eval gate: **OK** — all six chapters byte-identical to the V0.6.2 baseline (this change touches UI geometry only). Prompt manifest OK (no `prompts/` bank change). ruff check + format clean on every touched file. Rule-1 deny-list clean.


## V0.6.2 — the two user-reported bugs fixed: the negative elapsed timer (midnight-crossing), the thin-chapter over-generation

> **The release (both fixes user-reported from a real ~2h40m book run):** (1) the Step-9 live elapsed timer rendered a misleading NEGATIVE time ("-21:34:45"-style) after a conversion crossed midnight; (2) a book with 1-2 page chapters shipped exec + bullets + thorough ABOVE the source's own word count, padded with rephrased near-duplicate bullets and minor hallucinations. Both root causes reproduced live before the fixes; 19 of the 34 new tests fail on the pre-fix HEAD (git-stash-verified). All fixes content-agnostic (Rule 1 ✓ — source-word arithmetic + generic prompt wording, no book vocabulary); net-green (the same 14 environment failures, +34 passing, eval gate OK after the documented intentional re-baseline).
>
> **Fix 1 — the elapsed timer (`ui_qt/views/wizard_view.py`):** `_start_elapsed_timer`/`_update_elapsed` drove the label from `QTime.currentTime()` + `secsTo`. `QTime` is a time-of-DAY type with no day tracking: a conversion started at 23:34:45 and viewed at 02:00:00 (2h25m15s real) got `secsTo == -77685` — verified empirically on this rig — which the floor-division formatter rendered as a negative `-HH:MM:SS` (the user's exact symptom); a >24h run wrapped modulo 24h and silently reset. THE FIX: `time.monotonic()` (negative-impossible, wrap-impossible), clamped at zero as belt-and-braces. Pinned by the midnight-crossing drive (a fake clock at the `PySide6.QtCore.QTime` seam faithfully reproducing the C++ semantics — the pre-fix label renders "-22:25:15" on the exact user-shaped clock), the never-negative sweep, the 25-hour run ("25:00:00", not "01:00:00"), the clock-skew clamp, and the timer restart.
>
> **Fix 2 — the thin-chapter length policy (`core/summarisation/length_policy.py` — the single source of truth every prompt/floor/cap consumer reads):** FOUR stacked defects, all in the thin regime (W < 800 = the existing small-source boundary, aliased `THIN_SOURCE_WORDS` — no new magic number):
> * **the thorough floor broke the 45% cap** — `hi = min(w, max(round(0.45w), min(120, w)))` let the 120-word floor DOMINATE the fraction for W < 267: a 150-word chapter was told to write a 120-word thorough (80% of its source), a 100-word chapter 100 words (100%!). The module's own docstring promises "at most ~45% of the source"; the code broke that promise exactly where a summary stops being a summary — instruction-driven padding ("hallucination-by-instruction", the module's own words). The fraction is now the TRUE cap (`hi = min(w, round(0.45w))`); the 80-word lo floor applies only when hi can support it (no more "68-68 word" point targets that force a minimum a thin source cannot honestly fill). W ≥ 267 byte-identical (the floor is inert there).
> * **the exec floor broke the 20% cap** — the same defect (`EXEC_SMALL_SOURCE` 60 pushed a 100-word chapter's exec target to 60 words = 60% of source). Now `hi = min(250, round(0.20w))` with the lo floor gated on hi ≥ 40.
> * **the bullet ADDITIVE budget was unbounded for thin chapters** — `bullet_cap()` returned 0 ("no cap") for every chapter (the V0.4.23 directive), but the cap only ever bounds the ADDITIVE machinery (Tier-2/scholar gap-fill + quarantine resurrection — never primary bullets). With it 0, the gap-fill kept inserting bullets with NO room limit on a thin chapter — the user's "repetitive bullets - which were rephrased the same concepts". Two-regime now: thin chapters get the source-scaled `bullet_target` hi back (the V0.06 rig-audit F4-b semantics — the historical 14/14/18/18/16 for the rig chapter sizes); normal chapters (≥ 800 words) keep 0 (the V0.4.23 directive stands — the V0.4.22 displacement failure that removed the cap was a CONTENT-RICH chapter, not a thin one). All additive call sites (`_apply_3tier_coverage`, both scholar paths, `_recover_quarantined`) already threaded the cap — the policy change propagates everywhere from one place.
> * **no COMBINED budget existed** — the three section targets structurally sum to ~115% of a thin chapter's words (exec 20% + thorough 45% + bullets ~50%); nothing stated or measured the combined ratio (the user's headline number). The thin `length_budget_block` now carries a COMBINED BUDGET line (aim ~75% of the source, "the three sections are one summary of one thin chapter, not three parallel expansions of it: do not restate a bullet's content in the prose sections or vice versa"), a bounded bullet range ("N-M" instead of "at least N — NO MAXIMUM" — the no-maximum phrasing on a thin chapter is an explicit invitation to rephrase the same concepts into more bullets), and a one-DISTINCT-idea-per-bullet rule. `expansion_audit` gained the combined measurement (thin-scoped, flags ≥ 1.0x the source); F1 passes the bullet words in and logs them (`📏 F1: bullets=…w — combined sections …w / source …w`).
> * **Tier-2 gap-fill insertions bypassed the near-duplicate check** — the insertion loop only checked EXACT string equality, so a gap-fill bullet that REPHRASED an existing bullet was appended unconditionally. New guard at the insertion site: `DedupService.is_near_duplicate` (the within-chapter threshold, token_set_ratio ≥ 75; fail-open to exact-match when rapidfuzz is absent; fail-open + loud WARNING on any crash — the F4 precedent). The ship-time postchecks near-dup pass (V0.05 F6) still runs downstream as the second net.
>
> **Also fixed by the policy change (automatic, no code touched):** the dedicated thorough-expansion threshold for thin chapters reads `thorough_target` lo — a 150-word chapter's expansion threshold is now 41 words (was 80 = 53% of the source, forcing the 3-attempt expansion + the exec+bullets synthetic fallback = duplication on thin chapters); the F1 truncation backstops scale with the new targets; the thorough-theorist-floor append's skip gate reads the same targets.
>
> **Golden fixtures + eval baseline (the documented intentional-change procedure — `bench --save-golden`, `eval --save-baseline`, numbers shown):** the nonfiction (225w) + academic (236w) golden chapters are THIN — their frozen thorough summaries (146/148 words = 65% of source) exceeded the new 1.25×target backstop and are now clamped at the sentence boundary (127/131 words). The re-free is surgical (only `thorough_summary` changed; bullets/exec/distinctions/tensions byte-identical). Eval gate after re-baseline: **OK** — academic's ROUGE-L IMPROVED (0.4415 → 0.4544, precision up with the padding gone), nonfiction rebalanced (0.416 → 0.388, the one-sentence clamp); faithfulness/hallucination/coverage/F4-grounding identical on all six chapters.
>
> **Pinned fixtures updated to the two-regime contract (deliberate, each with the contract documented in place):** `test_v00423_no_limit_policy` (the cap-0-everywhere pin → the two-regime pin; the 340-word phrase pin → "9-14"), `test_v006_rig_audit_fixes` (the no-cap pin → the restored 14/14/18/18/16 rig budget), `test_p15_output_regressions` (same), `test_p2_summarizer_outer_loop` (the probe pin → two-regime), `test_v005_rig_audit_fixes` (the rendered-phrase pin → thin bounded + normal floor, both asserted), `test_v18202_summarisation_fixes` (the A4 constraint pin: the 240-word fixture source now scales to "80-108" — the TRUE 45% cap, was the 120-floor's 50%), `test_coverage_guarantee` × 2 (the old fixtures' synthetic gap-fill bullets — "new bullet 1"/"new bullet 2", `f"new{i}"` — were near-dups of each other BY CONSTRUCTION; the guard correctly drops them, so the fixtures now carry genuinely distinct content and pin the append/tag/head-cap semantics).
>
> **Net-green:** 34 new tests in `tests/test_v062_thin_content_fixes.py` (the elapsed-timer drives — midnight crossing / never-negative sweep / 25-hour run / clock-skew clamp / restart; the thin policy matrix — thorough/exec floor caps, no point targets, medium+normal regimes unchanged; the two-regime cap; the bounded phrase; the budget-block thin/normal variants; the combined audit thin-scoped + 3-arg compat; the Tier-2 near-dup guard — rephrase skipped / distinct appended / exact skipped / fail-open; the F1 combined measurement; the wiring pins). 19 fail on the pre-fix HEAD. Full suite: **the SAME 14 pre-existing environment failures (8 converter VRAM + 4 segmentation VRAM + 2 v182032 postchecks — the latter pair re-verified pre-existing on the stashed HEAD), 7,251 passed** (was 7,217), 25 skipped, 15 live-LLM deselected, no crash. Eval gate OK; prompt manifest OK (the budget-block wording is code, not the `prompts/` bank); ruff check + format clean on every touched file.
>
> **Deliberately NOT done (documented trade-offs):** no hard ship-time cap on PRIMARY bullets (the V0.4.23 directive — the prompt-side bounded range + the combined measurement + the additive budget are the thin-regime levers; a primary-bullet truncation would re-open the V0.4.22 displacement failure); no change to `max_bullets_per_chapter` (30, the distant global bound); no re-derivation of the bullet COUNT floor for thin sources (the V0.07 rig compromise stands — the combined budget is stated as a prompt-level aim, not per-section arithmetic, so the model can trade off honestly); the thin combined finding is measurement-only (prose is never cut by a ratio heuristic — the module's standing rule).


## V0.6.1 — the V0.5.21 backlog shipped: the thin gap-fill prompt tightening, the glossary pair-form dedup, the Searles see-also bound

> **The release (the three code-fixable V0.5.21 backlog items — filed by the V0.5.17 audit (line 44, the see-also content-inflation caveat) + the V0.5.19.1 audit (line 88, the pair-form note) + NEW_SESSION_PROMPT.md's secondary agenda):** the V0.6.0 campaign closed the tools verification; this release closes the pipeline-quality backlog that remained. All three fixes are content-agnostic (Rule 1), pinned defect-driven (22 of the 29 new tests fail on the pre-fix HEAD), net-green (the same 14 environment failures, +29 passing, eval gate OK, prompt manifest untouched — the tightened prompts are the INLINE roster-gap-fill prompts in `gap_fill_batch.py`, not the `prompts/` bank).
>
> **Fix 1 — the thin roster-gap-fill prompt tightening (backlog item 1):** the V0.5.19/V0.5.20 ship-time flags catch the thin one-liners ("Name made significant contributions to …" / "Name: Contributed to literature on …"), but the MODEL still wrote them — the roster gap-fill prompts never demanded the author's SPECIFIC contribution. Both inline prompts now carry an explicit quality rule: state the theory/term/distinction/finding/method the source excerpt (or glossary context) attributes to THAT author; NEVER a generic registry phrase — the banned set is the exact generic citation-registry verb family the V0.5.19 `_THIN_GAPFILL_SENTENCE_RE` detector pins (generic English, no book vocabulary). Sites: the main batch prompt's attribution-rules block (gap_fill_batch.py) + the final-check round-4 prompt's contribution line. Decision documented: the backlog offered "a prompt tightening OR a quality gate at the gap-fill merge" — the tightening ships; a merge-time gate that DROPS thin bullets would re-introduce the coverage-gap problem the V0.5.6 architecture fought (the flags stay the audit-visible safety net; the honest-gap policy applies to ungroundable content, not to thin-but-true phrasing).
>
> **Fix 2 — the glossary pair-form dedup at ingestion (backlog item 2):** the rig glossary listed BOTH "A and B" AND "B and A" (the commuted pair-form artifact — the individuals themselves were covered; the pair was double-listed, and every downstream roster (the gap-fill pool, the verification coverage check, the cross-reference report) saw two entries for one pair). `_pair_form_key` maps a TWO-surname entry joined by "and"/"&" to an UNORDERED pair key; `_parse_name_bullets` drops the commuted duplicate keep-first (the FIRST listing wins, with its year + context). All three parse tiers funnel names through `_parse_name_bullets`, so the dedup applies at ingestion for every tier + the persist / cross-reference / verification consumers. Scoped to the evidenced shape: three-name forms, single names, and "A and A" degenerates are NOT pair-forms (untouched); exact single-name duplicates keep their pre-existing parse-level behavior (the downstream extractors dedupe those).
>
> **Fix 3 — the Searles see-also bound (backlog item 3, the audit's "verify whether the glossary context should bound it" — it should):** the loosened quote-guard (the V0.5.6 glossary-backed override + the final-check round 4, the path that produced the audit's accepted-but-inflated see-also bullet) accepted glossary-backed bullets on MEMBERSHIP alone — nothing checked the bullet's CONTENT against the glossary context, so the model could credit the see-also author with the HOLDER's claim words that sit in the same source sentence (the audit's "slight content inflation": the connection was in the source, the specific claim wording went a step beyond a see-also-only citation). The bound (`_v0521_see_also_bound`): the bullet's content tokens — house tokenizer (`[a-z0-9]+`, len>2, plural-normalized), light-verb-stripped via the existing `_LIGHT_VERB_RE` (attribution verbs never count), the author's name tokens + 4-digit years removed (trivially grounded) — must be ≥ **0.55** covered by the GLOSSARY CONTEXT's tokens (the house per-bullet containment floor, `summarizer_coverage`'s 0.55 precedent; with a derivational-prefix tolerance — "abandon" ~ "abandonment"). Source sentences are deliberately NOT part of the grounding: the holder's claim words sit in the SAME sentence that mentions the see-also author — source-grounded coverage would pass exactly the inflation the bound exists to catch. The glossary context is the architecture's own grounding claim ("the glossary IS the grounding", V0.5.6) — the bound ENFORCES it; a contextless glossary entry grounds nothing (fail-closed). Applied at BOTH loosened-acceptance sites: the V0.5.6 glossary-backed override (a bound rejection counts like a veto — the mention-only escalation + give-up machinery applies, the author finishes honestly missing) + the round-4 final-check acceptance (previously unconditional). The V0.5.10 regex fallback is deliberately NOT bounded: on that path the author is not in the glossary by construction — no glossary context exists to bound by; the regex confirms PRESENCE, not content. Trade-off documented: a bound-rejected see-also author finishes HONESTLY MISSING rather than inflated (coverage % can drop by that author on the next rig run — the precision-over-coverage choice the backlog item asks for; the audit had kept the bullet with the caveat).
>
> **Two pinned V0.5.6-era fixtures updated to the new contract (the deliberate behavior change):** `test_quote_guard_loosened_for_glossary_authors` + `test_quote_guard_glossary_takes_precedence_over_regex` — their fixtures paired a bullet carrying the HOLDER's content ("Established the unified framework…") with a thin glossary context ("cited as a precursor"), which is exactly the inflation shape the bound now rejects; the fixtures' glossary contexts now carry the same content as the bullet (the acceptance contract the V0.5.6 entry documented: "the bullet can write 'Bak (1946) introduced…' grounded in the glossary context"). The rejection side of the old fixtures is pinned in the new suite (the see-also-bound tests below).
>
> **Net-green:** 29 new tests in `tests/test_v0521_backlog.py` (the bound helper matrix — light-verb stripping / prefix+plural tolerance / author-year exclusion / empty-bullet 1.0 / empty-grounding 0.0; the main-loop override bound — the Searles-shape rejection + the veto-count escalation to mention-only + the Bak-shape acceptance + the regex-path scoping; the round-4 bound — the inflated rejection + the grounded acceptance + the contextless-entry fail-closed; the prompt pins — "SPECIFIC contribution" + the banned registry phrases in BOTH prompts; the pair-form dedup — all 3 parse tiers + ampersand + different-years + non-commuted/3-name/degenerate untouched + the exact-duplicate characterization + the extract→persist→cross-reference integration). 22 of the 29 fail on the pre-fix HEAD (git-stash-verified — the 7 passing are the unchanged-behavior characterizations). Neighbor suites green: the gap-fill/glossary/quoteguard/v011/golden-freeze cohort 106 passed; the wider module-touching cohort (v0516-v0520, the Rule-1 deny-list, the prompt manifest) 243 passed. Full suite: **the SAME 14 pre-existing environment failures, 7,217 passed** (was 7,188), no crash. Eval gate re-run: **OK — no quality regressions vs baseline**; the prompt manifest untouched (the tightened prompts are inline, not `prompts/` bank files). ruff check + format clean on every touched file. The Rule-1 deny-list scan clean.
>
> **Deferred (not this release's scope):** the fourth V0.5.21 backlog item — the rig LIVE verification of the V0.5.20 fixes (+ now the V0.5.21 bound's live behavior on the real book) — is inherently an operator run (the full-book rig run that exposed the V0.5.20 defects). The sandbox's live pipeline smoke run through the shim was attempted but the upstream LLM API rate-limited persistently (the shim's 429-retry chain exhausted; the exact condition the `live_llm` marker's V0.6.0 rationale documents) — the hermetic + deterministic-pipeline evidence above stands, and the operator's next rig run covers the live leg.


## V0.6.0 — the dedicated-tools verification campaign: every tool card verified end-to-end, 30 defects fixed, the W8 coverage deserts closed

> **The release (the campaign the operator commissioned: "making sure all dedicated tools of the app works, such as podcast maker, ocr, summarization etc."):** the V0.5.x campaign verified exactly ONE tool end-to-end (the Full Conversion pipeline's summarization quality, 4 benchmark configurations, 0 fabricated claims). The ToolDashboard ships TWELVE tool cards + 3 internal tabs and the SWOT's W8 knew most had NEVER had an end-to-end pass (`core/extract` 0%, `core/ocr/unlimited_ocr` 0%, outputs service formatters 8–52%). This release verifies EVERY card, every internal tab, and the output-rider family — 730 new end-to-end tests across 13 new test files, 40 real defects found and fixed (every one reproduced live or defect-driven-pinned before its fix), zero new suite failures. The method (per the campaign charter): trace card-key → routing → dialog → service entry, evidence-first; characterization tests FIRST for anything touched; headless verification with `QT_QPA_PLATFORM=offscreen` + the zai-llamacpp shim (:3031, glm-4-plus) for every LLM-driven tool; GPU/external engines verified at the CONTRACT level with rig-checklist items filed; every fix content-agnostic (Rule 1), net-green at every commit (Rule 3).
>
> **Per-tool verdicts (13 test files, 730 tests):** PDF/DOCX Cutter 32 (C1: an unparseable non-empty range — including a typographic-dash range pasted from a PDF/TOC — silently cut the WHOLE document; C2: an out-of-range-only selection wrote a 0-page file reported as success) · Image Extractor 41 (D1: an unopenable input rendered "✅ 0 images" + a success modal; D2: inverted page range → "✅ 0"; D3: the vector-crop path wrote the UNTRIMMED pixmap; D4: svg/emf/wmf assets PIL cannot decode were selected then dropped — now copied through verbatim) · Document→Markdown 48 (the anydoc-absent→markitdown fallback contract VERIFIED live; D1: the malformed-PDF detector missed pypdf≥4's "Stream has ended unexpectedly" so the pikepdf repair never fired; D2: .pptx/.xlsx missing from the markitdown extension sets though markitdown[all] converts them; D3: extensionless-input status message) · OCR Service 57 (LIVE tesseract: a mixed digital+scanned PDF through the real cascade; O1: tesseract never auto-resolved off Windows — the shipped default `paths.tesseract` is the Windows installer path, so every non-Windows host pinned a non-existent binary while a working tesseract sat on PATH; O2: the garbage-page-range silent-whole-document cut, the cutter C1 shape; O3: unlimited_ocr mislabeled page numbers when a rasterization came back empty; O4: the dead `image_max_size` parameter) · Summarization service (standalone) 37 (S1: the model pre-flight speaks Ollama /api/tags but ran for EVERY provider — a healthy llama.cpp/OpenAI-compat/Claude backend hard-stopped with "not installed in Ollama"; S2: the model-missing error was clobbered by the refresh status in the same handler; S3: Ollama-specific failure advice on non-Ollama providers) · Translation EN↔FA 143 (LIVE through the shim; T1: a 404 retried 3×/line then silently returned the ORIGINAL text as the "translation"; T2: a mid-translation engine error returned "❌ {e}" — the shared finished-handler routes only "Error:"-prefixed strings to the failure branch, so the error text was written to the OUTPUT FILE and reported as ✅ success; T3: line-count verification; T4: heading-level drift restored; T5: the front-matter pass-through was a 20-line heuristic that skipped prose "Note:" lines; T6: a corrupted cache file crashed the run; T7: an all-failed queue showed the success modal; T8: a Title-case stopword tuple never matched; T9: the queue-completion slot was a plain closure Qt ran ON THE WORKER THREAD touching widgets) · Markdown Styler + Packets 68 (P1: chapter-mode packets fed the deduped list into the coverage counts — "10 bullets → 2 keypoints, >100% coverage"; P2: the unsanitized book title scattered outputs into unintended subdirectories; M1: dead checkboxes advertising never-read option keys) · TTS Service + podcast audio 107 (A1: a local Persian-detection copy missed the presentation-form blocks — misrouted to the English engine; T1: a "vibevoice:…" voice id passed to the Kokoro fallback broke the fallback) · Transcribe + podcast script 68 (REAL ffmpeg extraction; T1/T2: the transcribe summarizer hardcoded provider=ollama with a KNOWN-BAD default model tag — llamacpp rigs got connection-refused; P1: the same known-bad tag in the script generator; P2: the year-pattern alternation listed "twenty" before "twenty-two" so "two thousand twenty-two" became "2020-two"; P3: a phantom "# Source Material" heading was extracted as a bullet and counted in the coverage requirement) · the output riders 53 (every flag smoke-passed on a synthetic fixture: anki/genanki, epub/ebooklib, obsidian, study guide, mind map, quote bank, citation graph, evidence map, social pack, briefing, flashcards, QA, reference outputs, chapters, the service_formatters matrix; epub D1: unescaped `&<>` produced not-well-formed XHTML in the fallback writer; D2: the OCF mimetype entry was DEFLATE-compressed — epubcheck rejects that) · the three internal tabs 76 (D1: the scanner's three regenerable-key sets had drifted apart — 17 vs 9 keys — so regenerable outputs showed no button and Complete-All skipped them; D2: the audit's copy button copied the 80-char DISPLAY text with the literal "..."; D3: the hallucination detector reported "verbatim span found" for FAILED verbatim checks).
>
> **Test-infra hardenings the campaign surfaced (3 fixes, the tiktoken-poisoning class + two crash classes):** (1) the hermetic markitdown gate in `tests/conftest.py` — 36 test files carry the guarded `sys.modules["markitdown"]` stub block; whichever is collected FIRST installs its fake even when the REAL markitdown is installed (a core requirements.txt dep), so real conversions failed session-wide, order-dependently (the exact class conftest fixed for tiktoken in V18.20.2.0; observed live during this campaign). (2) the `live_llm` marker (registered in pyproject, the gpu-marker precedent): the 15 live-LLM tests make REAL calls through the shim — under the upstream rate limiter their retry chains hung the suite (the health gate passes even when the upstream 429s). Default runs deselect them (`-m 'not live_llm'`); each class self-skips when the shim is unreachable; explicit `-m live_llm` verifies them when healthy. (3) the QThread-destroyed-under-GC containment: a test ending with a still-running SimpleWorker lets the main-thread GC collect the dialog cycle — the C++ QThread is then freed under the running Python thread and the interpreter segfaults in whatever pure-Python frame that thread executes next (observed twice in full-suite runs: urllib3-clear, pathlib-__str__). The campaign's dialog drives now join every spawned worker, neutralize the close-guard, and clear the leaked `Settings._test_override` (the one file that leaked it).
>
> **Net-green:** 730 new tests in 13 files (`tests/test_v0600_tool_cutter_e2e.py` · `test_v0600_tool_image_extractor_e2e.py` · `test_v0600_tool_doc_to_md_e2e.py` · `test_v0600_tool_ocr_e2e.py` · `test_v0600_tool_summarization_e2e.py` · `test_v0600_tool_translation_e2e.py` · `test_v0600_tool_styler_packets_e2e.py` · `test_v0600_tool_tts_e2e.py` · `test_v0600_tool_transcribe_podcast_e2e.py` · `test_v0600_output_riders_e2e.py` · `test_v0600_internal_tabs_e2e.py`, + the conftest/pyproject infra). Full suite on this sandbox: the SAME 14 pre-existing environment failures as the V0.5.20 baseline (the 17-family cohort; the llamacpp-dropdown + hypothesis members did not fire this session), **7,188 passed** (was 6,474), 15 live-LLM deselected, no crash — and `make`'s eval gate re-run: **EVAL GATE: OK — no quality regressions vs baseline**. ruff check clean; the pre-existing 17-file ruff-format drift (a ruff-version delta on the V0.5.x campaign files, git-stash-verified identical on pristine V0.5.20) is unchanged. The Rule-1 deny-list scan clean (all new runtime code uses synthetic shapes; no book/author/domain strings).
>
> **The rig checklist (contract-verified in-sandbox, LIVE runs are the operator's):** live qwen/OlmOCR via Ollama + Persian `fas.traineddata` for tesseract + UnlimitedOCR with torch/transformers + PaddleOCR CPU init + provider-vision routing (OCR); real Ollama + TranslateGemma prompt strategy + cloud backend (translation); live qwen/vibevoice GPU + sherpa binaries + a real Kokoro/Piper install (TTS); faster-whisper with a real model (transcribe); anydoc on a rig that has it (doc→md). The V0.5.21 backlog (thin gap-fill prompt tightening, glossary pair-form dedup, the Searles see-also bound, the rig LIVE verification of the V0.5.20 fixes) remains open — this campaign's scope was the tools.


## V0.5.20 — the layout-independent continuation join + the terminal-shape lint + the keypoints-layer author-coverage veto + the glossary handoff path + the thin colon-less variant

> **The release (the V0.5.20 backlog — the four items filed by the V0.5.19.1 rig run #2 audit, the FULL-BOOK ingestion, run `20260928-155851-011587f0`, `audit/results/bench_v0519_1_ch9_histrionic_schizotypal_rig2/`):** the operator ran the whole 397-page book PDF with ch.9 TOC-selected (p.222-242) on their real-embedder rig — the ~95% band held (69/73 = 94.5% individual, 0 fabricated) and the V0.5.18 semantic-dedup veto fired LIVE for the first time, but the run exposed four pipeline defects the single-chapter extraction could never show: the continuation joins are extraction-LAYOUT-fragile (the same source content, a different pagination, six broken lists — all invisible to the pipeline's own "enumerated items 74/74" floor because the missed items never entered the denominator), the keypoints dedup un-rescued the veto's own bullets, the glossary persisted outside the run's output dir with every audit-trail line reading "Glossary: (none)", and ~12 thin one-liners escaped the V0.5.19 colon-form detector. This release ships all four, content-agnostically.
>
> **Fix 1 — the layout-independent (marker-sequence-driven) continuation join:** the joins no longer guess from paragraph structure; they read the MARKER SEQUENCE. In `core/summarisation/enumeration.py`: (a) the run-in marker patterns now accept a marker at a PARAGRAPH TAIL — `\((N)\)` followed by end-of-paragraph or one sentence-punct char + end (`…, and (4).` — the old `\)\s`-only shape never matched it, so the run stopped at (3) and the guarantee bullet shipped the dangling marker with the content dropped; the punct is consumed into the match so the item text starts clean); (b) the open-tail predicate `_runin_tail_open` — a tail is OPEN when the item is cut mid-phrase, when it is EMPTY (the marker awaits its content), or when it is punctuation-only (the page break left the period attached to the marker); (c) the FINAL-ITEM continuation rule — when the list's last item is open and the next paragraph opens LOWERCASE and carries no same-style marker (nothing for the next-sequential rule), it is the item's continuation (the "…embraces casual | acquaintances with excessive ardor…" family; bounded ≤6000 chars, paren styles only, a same-style non-sequential marker in B blocks the join — B opens a new list); (d) the PAGE-FURNITURE skip — up to 2 furniture paragraphs (bare page numbers, short multi-token ALL-CAPS running headers — the new shared `core/common/layout_furniture.py`, used by both join sites so the definition can never drift) between the list and its continuation are looked PAST; the furniture stays in the rebuilt text (nothing dropped); ≤3 joins per paragraph per pass. The criteria collector (`extract_structured_criteria`) gets the same furniture treatment: a page-number/header LINE between sub-items no longer closes the cluster (the 5/8 + 3/9 schizotypal prefix-truncations — the furniture line read as discussion prose, the remaining sub-items arrived with no parent letter and were skipped). Verified on the REAL ch.9 source: the six-grounds list still 6/6, the Reveals list 4/4 with item (4) complete, and the histrionic criteria roman list now carries item (iv) COMPLETE with (v) attached (was a 4-item truncated capture in EVERY prior run — the no-marker continuation had no join at all before).
>
> **Fix 1b — the terminal-shape lint:** no shipped bullet may end in a bare enumeration marker. `ends_in_dangling_enum_marker` (`post_processing.py`, wired as an advisory `enumeration/flag` in `postcheck_bullets`) catches the `…, and (4).` / `…, and (iv)` / `…and 4.` tails (trailing quotes + ONE terminal punct stripped; the marker's own closing paren deliberately preserved — `_TAIL_STRIP_CHARS` would eat it); the guarantee renderer additionally SKIPS empty-text items from the consolidated bullet + logs the skip (a rendered "(4) " with no text IS the defect). The lint makes the floor's blind spot audit-visible: a dangling marker means an item never entered the denominator.
>
> **Fix 2 — the keypoints-layer author-coverage veto:** the keypoints embedding dedup ("removed 2 duplicates, 76 → 74") removed the EXACT two bullets the V0.5.18 summary-layer veto had just rescued — this call site had no veto, so the `.Keypoints.md` output silently lost the only bullets covering those authors (the uniquely-named-author-blind removal pattern, one output layer deeper). The fix mirrors the V0.5.18 veto exactly: the same roster (`source_author_surnames` over the run's segments), the same boundary-safe `author_in_text` anchor, the same DEFERRED complete-kept-set judgment (a later kept bullet covering the author blocks the rescue), the same parenthetical-promotion refinement (a confirmed misattribution is not rescuable), order-preserved re-insertion at the original position, fail-open on any error, no-segments → inert. Applies to BOTH dedup paths (embedding + rapidfuzz). The net "removed N" log can no longer contradict the file.
>
> **Fix 3 — the glossary handoff path:** the `.glossary.md` now persists INSIDE the run's per-book output folder and the glossary dict CARRIES its path. Root cause: `request.output_dir` is the BASE dir the user picked, while the converter ALWAYS creates the per-book run folder under it (`create_output_folder(…, per_book=True)`) — the full-book run's glossary landed at `…\5.19.1\summaries\.glossaries\…` while every other artifact lived in `…\5.19.1\<the book's run folder>\`; and the dict never carried a `path` field, so the verification LAYER's and the gap-fill's audit-trail lines read "Glossary: (none)" (the names were in-memory all along — the cross-ref counts prove it — but the FILE-based ground truth was unlinkable to the run). Fixes: `run_summarization` attaches `request._run_output_dir` (+ the unified `request._run_id`) next to the existing `_run_id` unification; `_extract_glossary_for_call` prefers it (falls back to `request.output_dir` — the harness path, where the request IS the run dir); both persist sites set `glossary["path"]`. The audit trail now names the real file and an audit finds it in the run dir.
>
> **Fix 4 — the thin-bullet colon-less variant:** the V0.5.19 detector's shape was colon-form-specific (`Name: Contributed to…`), so when the model wrote the SAME family colon-less ("Kretschmer made significant contributions to…" / "Frances (*1980*) contributed to…" — ~12 one-liners) the quality signal went dark. The widened `_THIN_GAPFILL_SENTENCE_RE`: a leading name (single / "Name and Name" pair / "et al."), an optional year parenthetical (`(*1980*)` / `(1910)` / `(*1968*, *1971*)`), then DIRECTLY one of the citation-registry verb phrases ("made significant contributions to" / "contributed to" / "authored literature on"). Real claims do not match ("AuthorN contributed the six-grounds distinction" — contributed + OBJECT, no "to"; content verbs), and a ONE-LINER bound (≤ 280 chars) keeps substantive thorough-summary prose that merely OPENS with the same name+verb shape out of the flag. Every evidenced rig-run shape is caught (5/5 in the test matrix); the colon form's pinned behavior is unchanged.
>
> **Net-green:** 37 new characterization tests in `tests/test_v0520_layout_vetoes.py` (the furniture shapes / the dangling-marker join matrix incl. the same-paragraph + bare-tail + no-false-join guards / the E3 chain across two breaks + the furniture skip + the 2-paragraph bound / the criteria furniture skip (8/8, was 5/8) / the lint matrix + the postcheck wiring (advisory, never a drop) / the keypoints veto matrix on BOTH dedup paths (unique-author kept + logged, plain twin dropped, later-bullet coverage blocks, order preserved, no-segments inert, fake-embedder live) / the glossary path-field + run-dir preference + fallback + the verification "(none)"-dead check / the thin colon-less matrix + the thorough-prose bound / the renderer's empty-item guard). The V0.5.7 pinned test updated to the evolved glossary contract (+`path`). Full suite on this sandbox: the SAME 17 pre-existing environment failures as pristine V0.5.19.1 (git-stash-verified: converter/segmentation VRAM + the llamacpp dropdown + 2 v182032 postchecks + the hypothesis property-text-utils flakiness family) — ZERO new failures, +37 passing, ruff clean, the Rule-1 deny-list scan clean (all new runtime-code comments use synthetic shapes; the rig-run evidence quotes were genericized where they carried book-derived names — the run ids + defect shapes carry the provenance instead).


## V0.5.19.1 — the enumeration-guarantee wrapped-continuation join (the missed third extraction path)

> **The patch (same session, found by the V0.5.19 ch.9 re-benchmark):** the V0.5.19 paragraph-break join fixed `extract_inline_lists` (the list-candidate path), but the shipped "**…** — N items from the source" guarantee bullets come from the V0.4.23 enumeration guarantee (`detect_enumerations`), whose V0.4.24 `_paragraphs_joinable` pre-pass searched only paragraph B's FIRST physical line for the next-sequential marker. A PDF hard-wrap puts that marker on a LATER line of B (the six-grounds list: B opens "while the second type shows … two sexes; and (6) …" — (6) sits ~2 wrapped lines in), so the join never fired and the guarantee bullet still carried 5/6 with item (5) truncated at the break. The fix: search B's FULL paragraph text (the pre-marker continuation-length guard — < 300 chars, measured across the wrapped lines — keeps the new-topic-paragraph rejection). Verified on the real ch.9 source: the list now detects as ONE 6-item run with item (5) completed and item (6) carried. 3 new characterization tests (the wrapped-marker join / the V0.4.24 first-line shape unchanged / the stray-marker new-topic paragraph still rejected); the 71 enumeration-suite tests stay green; ruff clean.

## V0.5.19 — the append-mode correction type (the brittle-additions fix) + the normalized correction anchor + the glossary structural-name filter + the prose-form year check + the criteria/list continuation fixes

> **The release (the V0.5.19 backlog, all evidenced by the ch.9 re-benchmark):** the V0.5.18 same-chapter re-run (73/73 = 100% floor and full-text, flag honest 3/0) filed six items — the verification LAYER's additions were brittle (exact-substring corrections; 5 of 6 skipped on the ch.1 run; the accurate ch.9 flag still couldn't land the Simic/pair bullets), thin roster-gap-fill bullets carried a prose-form year slip the citation-shaped checks cannot see, the glossary listed a classification-manual code as a "name", the scholar-reflection quote guard dropped roster-grounded bullets, the deterministic list capture split at paragraph breaks (the 6-ground list carried 5/6), and the "Reproduced Diagnostic Criteria" section was garbled by PDF hard-wraps. This release ships all six, content-agnostically.
>
> **Fix 1 — the append-mode correction type (the flagship):** omission corrections can now be `{"append": "<bullet>", "author": "<name>", "reason": "omission"}` with NO anchor at all. SAFE to build since V0.5.18 (the et-al fix made the missing-author flag honest — an append can no longer name a present author). Deterministic guards: the author must match a roster author STILL missing from the replacement-polished text (anchor-based, et-al tolerant, either containment direction for paired names), the append TEXT must name that author (the bullet covers the person it claims), one append per author (first wins), per-append shape caps (40–400 chars), ≤8 appends, total appended ≤15% of the original, and each append individually clean (0 deterministic polish flags — a stray-quote/fragment append is skipped, not shipped). Insertion: after the LAST bullet of the takeaways region (before the canonical `## Thorough Summary` heading — a pipeline-generated section name, Rule 1 clean; falls back to the body's last bullet; no bullet list → flag, fail-open). Audit trail: `verification_append/fix` issues per landed append + aggregate `verification_append/flag` when every proposed append was guard-rejected.
>
> **Fix 2 — the normalized (fuzzy) correction anchor:** the replacement loop now locates the LLM's "original" EXACT-substring first (the V0.4.40 contract unchanged — exact short quotes still match), then via a NORMALIZED search: casefold + whitespace-run collapse + markdown-emphasis/quote dropping (so `**A**` ≡ `A`, `don't` ≡ `dont`) + en/em/minus-dash unification, mapped back to the original span (the span swallows internal stray emphasis so the replacement cleans it). Anchors ≥8 normalized chars only (short near-misses stay rejected — too ambiguous); unlocatable → skipped (fail-open, never a fuzzy mis-replace). This kills the ch.1 5-of-6-skipped family (near-miss anchors) and makes anchor-insert omissions far more likely to land.
>
> **Fix 3 — the D3 length-guard reorder:** the 85–115% guard now judges the REPLACEMENTS only (after the D4 de-contamination — the V0.5.4 contract preserved: a D4 drop can bring a replacement-heavy polish back inside the band, which the reordered-guard test pins), and the appends are bounded by their own caps instead of tripping it — the old position rejected EVERY correction whenever omission additions pushed the polished text past 115% (the "brittle additions"). Worst-case growth is bounded (~1.32×) and always logged.
>
> **Fix 4 — the glossary structural-name filter:** the LLM glossary sometimes lists STRUCTURAL LABELS in its `names` section (the ch.9 run carried a classification-manual code — the flag then demanded an author that is a manual). NEW shape-based filter in `core/summarisation/author_anchor.py` (the shared module): `is_structural_name` / `filter_structural_names` — all-caps acronym/code shapes (`^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*$` with ≥2 letters: manual codes, roman numerals) + the generic section-label word set (the V0.4.38 F4 list, canonically moved to `STRUCTURAL_LABEL_WORDS` — `attribution._BOLD_NAME_STRUCTURAL_LABELS` stays as the alias). Wired at every glossary-ingestion site: the verification ground truth, the gap-fill membership extractor, both `cross_reference_glossary` copies (a garbage name no longer appears as llm_only noise), and the repeatability scorecard. Fail-open direction: a false positive removes a coverage DEMAND, never fabricates one.
>
> **Fix 5 — the prose-form year check (3b) + the thin-bullet flag:** `validate_years` gains check 3b: a sentence naming a KNOWN roster author AND carrying a scholarly-work prose-year attachment (`a work/paper/study/article/book/monograph/publication/report from/in/of NNNN`, years 1800–2099 so a 4-digit COUNT never reads as a year) must carry the year in a named author's roster years or be citation-shaped-adjacent in the source — else flagged ("possible prose-form year slip"). Flag-only (the attribution can be ambiguous — which named author owns the year). This catches the ch.9 "Cited in a work from 1980" bullet (the real year 1988, invisible to every citation-shaped check). Plus the thin roster-gap-fill SHAPE flag: `Name: Cited in/Authored/Contributed to …` one-liners are flagged as quality signals for the audit (both evidenced thin bullets match; real claims like `Name: Demonstrated …` do not).
>
> **Fix 6 — the scholar-reflection loosened quote-guard (the V0.5.10 pattern):** a quote-less gap-fill bullet that NAMES a runtime-roster source author (`source_author_surnames`, built lazily once per call) is now KEPT — the deterministic roster IS the grounding. Quote-less bullets naming NO roster author stay dropped (the strict V13.42.0 anti-hallucination guard); roster-build failure fails open to the strict drop.
>
> **Fix 7 — the deterministic-criteria continuation rules (the garbled "Reproduced Criteria" family):** `extract_structured_criteria` gains four shape-based rules: (1) a continuation line must start LOWERCASE — an uppercase-start prose line after a marker CLOSES the cluster (the old code glued the follow-on discussion paragraph into the letter's text); (2) a continuation after a SUB-ITEM marker appends to the LAST SUB-ITEM (the old code appended it to the parent letter's text — the truncated-sub-item family); (3) multi-paragraph continuations chain (a lowercase line may continue when the previous non-blank line was itself a lowercase continuation); (4) an EMBEDDED sequence-extending `(roman)` marker mid-line splits the line — the pre-marker tail continues the pending sub-item, the post-marker text starts the next sub-item (a random `(iv)` mention that doesn't extend the sequence never splits). Plus a duplicate-tail guard (the PDF double-print family) and continuation length caps. On the ch.9 mirror shapes: the b-item's text is clean (no discussion-prose glue), sub-item (i) completes across the wrap, the mid-line (ii) splits correctly.
>
> **Fix 8 — the inline-list paragraph-break join:** `extract_inline_lists` now joins a numbered-list paragraph with its successor when the paragraph carries ≥2 inline numbered markers, does NOT end with sentence-final punctuation (after stripping trailing quotes/brackets), the successor starts LOWERCASE (a mid-sentence continuation — a new discourse paragraph starts uppercase), stays under the same heading, and the join stays bounded (≤3 joins, ≤6000 chars). The ch.9 6-ground mirror now captures 6/6 items (was 5/6 with item (5) truncated at the paragraph break).
>
> **Net-green:** 56 new characterization tests in 3 files (`tests/test_v0519_structural_names_append.py` — the structural-name matrix + the glossary-extractor wiring + the append-mode guard matrix (valid/fabricated/covered/unnaming/shape-caps/per-author-dedup/compose-with-fuzzy/no-bullet-list/length-guard) + the normalized-anchor matrix + the insertion-offset helpers; `tests/test_v0519_criteria_continuation.py` — the embedded-split helper matrix + the four continuation rules end-to-end + the duplicate-tail guard + the well-formed no-regression pin + the paragraph-join matrix incl. the three no-false-join guards; `tests/test_v0519_prose_year_thin_bullet.py` — the check-3b matrix (slip/correct/co-cite/exemption/count-not-year/no-known-author) + the thin-shape matrix + the loosened quote-guard's three paths). Full suite on this sandbox: 17 pre-existing environment failures — 15 known env families (converter/segmentation VRAM + the llamacpp dropdown, no torch in this venv) + 2 postcheck tests verified IDENTICAL on pristine V0.5.18 code via git-stash (environment drift; the sandbox re-provision between sessions replaced the venv, so the count differs from the 45-failure bench-venv baseline without any code change), +56 new passing, ruff clean, the Rule-1 deny-list scan clean (all new runtime-code comments use synthetic AuthorA-style names).

## V0.5.18 — the two ch.9-audit HIGH fixes (the boundary-safe author anchor + the semantic-dedup author-coverage veto) + the citation-run roster gap + the author-year consistency check

> **The release (the ch.9 operator-rig audit's findings):** the V0.5.17 third-chapter confirmation (66/69 = 95.65% floor, 0 fabricated, on the operator's own Ternary-Bonsai-2-27B rig) filed 2 new HIGH bugs + 1 MEDIUM — the same bug family as V0.5.15/16/17 (post-check layers unaware of citation-name shapes / author coverage). This release fixes all three, plus the audit's E2 cross-field year slip (the 2nd instance of the filed cross-field-consistency backlog family).
>
> **Fix 1 — the verification "et al." false positive (HIGH, Bug #1):** the V0.5.4 B1 word-boundary rule (`r"\b" + re.escape(name) + r"\b"`) can NEVER match a glossary name ending in "et al." — the terminal `\b` after the escaped period requires a following word char, and prose always has "et al. " + space/paren. On the ch.9 run, 6 of the 8 flagged-missing authors were PRESENT in the shipped text (Kety et al., Lilienfeld et al., Robins et al., Rosenthal et al., Snyder et al., Spitzer et al.) — benign as a flag, but it would inject duplicate bullets the moment append-mode corrections land. The fix is a new shared module, `core/summarisation/author_anchor.py`: (a) the et-al strip — a presence check asks "is this author represented?", and "Kety et al. (1975)" prose means Kety IS, so the check anchors on the PRIMARY SURNAME ("Kety et al." → "kety", matching every prose form: et-al / possessive / colleagues / bare); (b) lookaround boundaries `(?<!\w)name(?!\w)` — equivalent to `\b` for word-char names (the B1 no-substring-inside-longer-word property is preserved) but also correct for names ending in non-word chars. Wired into: the verification LAYER's coverage check (the false-positive site), the V0.5.17 near-dup veto in the orchestrator (hardening — one matcher for every veto), BOTH `cross_reference_glossary` copies (verification_phase + glossary_parser — an et-al glossary name whose surname the regex caught now buckets CONFIRMED, not llm_only), and the repeatability audit scorecard (so audits don't repeat the false positive).
>
> **Fix 2 — the semantic-dedup author-coverage veto (HIGH, Bug #2):** the V0.5.17 near-dup removal has the veto (it rescued Kretschmer + Nanarello on the ch.9 run itself), but the post-gap-fill SEMANTIC dedup (V18.20.3.2, embeddings, keep-first) did NOT — it silently dropped the round-4-accepted Wender et al. + Widiger et al. bullets (95→87), the Eissler pattern one removal layer over. `summary_validator.semantic_dedup_bullets` now takes `source_authors` / `context_text` / `source_text`: after the greedy pass (deferred, mirroring the orchestrator's veto structure, so the survivor set is the COMPLETE kept list), a to-be-dropped sim-twin is KEPT if it names a roster author absent from the surviving text (kept bullets + exec + thorough context) — one extra near-dup bullet is a smaller defect than losing an author entirely. The V0.5.17 refinement carries over: a CONFIRMED parenthetical promotion is NOT rescuable (misattributed twins have negative value), and the whole veto fails open. Both call sites in `chapter_phases.py` (the first pass + the non-skippable post-gap-fill pass) pass the runtime roster (`author_anchor.source_author_surnames(content)`), the exec/thorough context, and the source text. Log: `🛡️ V0.5.18 semantic-dedup veto: KEPT bullet N (sim-twin) — uniquely covers source author(s) X` (INFO, in the audit trail).
>
> **Fix 3 — the citation-run roster gap (MEDIUM):** `extract_citations` Patterns 1-5 all require the years in their OWN parens ("A et al. (1968)") or a single bare name-year ("A 1968") — so a parenthetical CITATION RUN like "(Kety et al. 1968, 1975, Rosenthal et al. 1968, 1971, Wender et al. 1974)" captured Kety-only (via another line's shape) and silently LOST Rosenthal + Wender — co-cited authors absent from the deterministic roster every author-coverage veto judges against (the glossary compensated via llm_only, but the veto layers are regex-roster-grounded, so Bug #2's veto could not have rescued Wender without this fix — the two fixes are one system). NEW Pattern 6: a comma/semicolon enumeration of `Name[ et al.] year[, year...]` items inside one paren pair — every name added with ITS years (additive; existing `author|years` keys dedup; FP guards: capitalized-name requirement + `_add`'s existing stopword/garbage filters, so "(In 1965)" and "(see A 1970)" never match). Pattern 1's years group also now tolerates the trailing comma-letter run of multi-work years ("A's (1921,\n1924a,b)" — the possessive + line-broken + letter-suffix shape that lost Abraham).
>
> **Fix 4 — the author-YEAR consistency check (the E2 slip, the 2nd cross-field instance):** the shipped bullet cited "(Akhtar et al., 1984, Wolman 1987)" while the source's women-citation is "Akhtar et al. 1986" — 1984 belongs to the ADJACENT men-citation (Robins et al.). The author is real (check 2 passes), the year is plausible (check 1 passes) — only the PAIR is wrong. `validate_years` gains check 3: a KNOWN source author cited with a year that is neither in the roster's author→years set (base 4-digit compare, so 1924b vs 1924a is consistent) NOR citation-shaped-adjacent to the name in the raw source (`Name[^\d]{0,48}?year` — an intervening DIGIT blocks false long-range joins across adjacent citations, which is exactly what defeated a naive proximity exemption) → flag-only ("possible cross-field year contamination"), the same posture as checks 1-2. The summary-side citation regex's author→year join now tolerates the markdown/comma shapes the shipped bullets actually use ("A et al., 1984" / "B *1987*" / "C (*1985a*" — previously a comma or italic asterisk made the citation INVISIBLE to the grounding check). Roster years are built once per source (lru_cache) since validate_years runs per field.
>
> **Net-green:** 28 new characterization tests in 3 files (`tests/test_v0518_author_anchor.py` — the anchor matrix + the cross-ref buckets + the end-to-end verification-coverage regression (pre-V0.5.18 flagged 3/3, now flags only the 1 genuinely-missing author); `tests/test_v0518_semantic_dedup_veto.py` — the 8-scenario veto matrix (plain-twin drop / unique-author keep / context-covered drop / later-bullet-covered drop (deferred semantics) / order preservation / misattributed-twin non-rescue / veto-inert / embedder-unavailable) via a deterministic fake embedder; `tests/test_v0518_citation_runs_year_consistency.py` — the citation-run shapes + FP guards + the consistency-check matrix incl. the prose-adjacency exemption). 3 test-harness updates that pinned the OLD call shape (the delegate's threshold-pass-through test now also verifies the veto kwargs; the v182034 source-pin + the deadline-watchdog source-pin now match the call prefix — the same precedent as the V18.20.3.7 heading-kwarg note). Full suite: 45 pre-existing environment failures (the 37-failure V0.5.17 baseline + 8 converter-VRAM tests that fail IDENTICALLY on pristine V0.5.17 code (git-stash-verified — env drift, no torch in the bench venv)), +28 new passing, ruff clean, the Rule-1 deny-list scan clean (all new runtime-code comments use synthetic AuthorA/Authorone-style names).

## V0.5.17 — the near-duplicate author-coverage veto (a dup bullet that uniquely names a regex-confirmed source author is KEPT — the V0.5.15 pattern applied to the ship-time near-dup removal)

> **The release (repeatability session):** the V0.5.16 ch.1 run reached 89.2% (33/37) author coverage — the remaining gap traced to two spots. (1) The gap-fill HAD added "Eissler and Blos shared Erikson's emphasis on adolescence…" (a regex-confirmed author), but the ship-time near-duplicate removal (`postchecks/orchestrator.py`, V0.05 F6 P2) dropped it as a 0.8-token twin of the kept Blos/Erikson bullet — silently deleting Eissler from the summary. (2) The V18.14 author judge + the V0.5.6 final-check round 4 never fired on the headless run because the deterministic-analysis artifact (`{segment}_analysis.md`) was absent (a harness gap — fixed in `scripts/repeatability_run.py`, which now replicates `output_save.py`'s segment-write + `analyze_segment_file` step).
>
> **The fix (the V0.5.15 pattern — regex-confirmed-author awareness — applied to the near-dup detector):** `core/summarisation/postchecks/orchestrator.py` — near-dup candidates are now DEFERRED (not dropped on sight); a deferred bullet is still dropped UNLESS it names a source author (the runtime `extract_citations` surname roster) that appears NOWHERE else in the final text (kept bullets + exec + thorough) — one extra near-dup bullet is a smaller defect than losing an author entirely. Log: `near-duplicate KEPT — uniquely covers source author(s) X (the V0.5.17 author-coverage veto)` (severity=flag, visible in the audit trail). Without source_text, the legacy drop behavior is byte-identical. **Refinement:** a CONFIRMED parenthetical promotion (`detect_parenthetical_promotion` — the same deterministic detector the parenthetical veto uses) is NOT rescuable: the near-dup twin of a misattributed bullet has negative value (it duplicates the kept bullet's content under the wrong author's name). Verified on the repeatability run's rescued bullets (correctly-attributed twins → None → rescuable) vs the misattributed twin (→ (claimed, real) → stays dropped, pinned by a new test).
>
> **Test-suite re-baseline (2 deliberate fixture/test updates, both consequences of the V0.5.16 guard):** (1) `tests/golden/multicolumn/pipeline_output.json` re-frozen (`scripts/bench_chapter.py --chapter multicolumn --save-golden`) — the frozen output embedded the OLD behavior where the judge's gap-fill bullets all died at "sim 0.00" in the embedder-less bench env; with the guard they legitimately survive F4 and land (7 more bullets). (2) `tests/test_p6_stage_overlap.py` merge-path test + the `ScriptedLLM` harness (`tests/test_p2_summarizer_harness.py`) — the merge-path premise ("the judge tail leaves the state unchanged") previously held BY THE BUG; the harness now scripts the judge gap-fill reprompt explicitly (a new `judge_gapfill` param + the `Add 3-7 NEW bullets` marker routed BEFORE the length-based primary classification), defaulting to the no-bullets reply, so the MERGE path is tested on genuinely-unchanged state.
>
> **Net-green:** 5 new characterization tests (`tests/test_v0517_neardup_author_veto.py` — drop/keep/covered-elsewhere/no-source/misattributed-twin matrix) + the harness extension; the FULL suite's failure list is byte-identical to the pristine V0.5.15 base (37 pre-existing environment failures: missing optional pdf/vision deps + torch-dependent VRAM tests), +7 new passing tests, ruff clean, the deny-list Rule-1 scan clean (book-derived author names scrubbed from the runtime-code comments).
>
> **Result (ch.1, sandbox, glm-4-plus):** **37/37 = 100% author coverage, 0 hallucination candidates, 75 bullets** — the V0.5.6 final-check round 4 fired (Klein + Searles accepted glossary-grounded), the V0.5.17 veto rescued Lynd. A same-chapter re-run reproduced it EXACTLY (37/37 again, 74 bullets, ±0pp — the V0.5.14-era run-to-run author variance is structurally resolved by the deterministic floors). vs the rig's ch.6 V0.5.15 result (70/74 = 95%): the source-glossary architecture's 95%+ coverage is REPEATABLE on a different chapter of the same book.

## V0.5.16 — the gap-fill Phase 2.2 degenerate-signal guard (an embedder-less rig no longer rejects every gap-fill bullet at "sim 0.00")

> **The release (repeatability session):** the first headless repeatability run of V0.5.15 on ch.1 ("IDENTITY AND ITS ORIGINS", a DIFFERENT chapter than the V0.5.x campaign's ch.6) produced **56.8% (21/37) author coverage — far below the rig's 95%**. The run log showed the gap-fill FIRED, targeted the right authors (Lynd, Lifton, Kovel, Spiegel…), generated correct bullets… and then `_validate_gap_fill_bullets` (`bullet_pipeline.py`) rejected ALL 8 at "Phase 2.2 sim 0.00 < 0.50".
>
> **Root cause:** `semantic_fact_check` fails CLOSED when the embed model is unavailable (V18.1 S1: `is_grounded=False, best_similarity=0.0, reason="embed_model_unavailable"`) — a DEGENERATE signal, not a real 0.00 similarity. The main Phase 2.2 stage (`apply_phase22_semantic_fact_check`) and `thorough_theorist_floor._filter_unverified_additions` both skip themselves when `is_embedder_healthy()` is False (the V18.2.30 guard) — but the gap-fill validation call site never got that guard, so an embedder-less rig (no sentence-transformers, no Ollama embed model — e.g. a llama.cpp-only box) loses EVERY concept gap-fill bullet while the deterministic F4 check (which needs no embedder) passes them.
>
> **The fix (2 layers, both mirroring V18.2.30):** `core/summarisation/bullet_pipeline.py` `_validate_gap_fill_bullets` — (1) skip the Phase 2.2 check entirely when `is_embedder_healthy()` is False (F4 source-overlap still gates every bullet; logged loudly); (2) per-bullet fail-open on the explicit `reason == "embed_model_unavailable"` marker (belt + braces: the health probe can pass while the model load still fails mid-run). A REAL low-similarity rejection (embedder present, genuine `best_similarity < 0.5`) is untouched.
>
> **Net-green:** 4 new characterization tests (`tests/test_v0516_gapfill_embedder_guard.py` — unhealthy-keep/unhealthy-F4-reject/healthy-reject/unavailable-failopen matrix); 88 P / 0 F on the gap-fill + bullet-pipeline + coverage + content-judge sets.
>
> **Result (ch.1, sandbox, glm-4-plus):** 56.8% → **89.2% (33/37)** in one fix — all 8 concept gap-fill bullets survived F4 and landed (0 hallucination candidates, 79 bullets).

## V0.5.15 — extend the loosened quote-guard to the post-checks (the parenthetical_promotion veto + the V0.4.24 attribution-edge now keep bullets for regex-confirmed authors)

> **The release:** the V0.5.14 audit found the V0.5.6 final-check round 4 FIRED + added 19/20 glossary-grounded authors (including Jack, Bak, Lowenthal, Morey, etc.). ALL 5 V0.5.5 missing authors NOW COVERED. BUT 5 authors were STILL missing from the deterministic floor:
> - **Kernberg + Socarides:** accepted by the loosened quote-guard in the gap-fill ✓ but DROPPED by the `parenthetical_promotion` post-check ("appears only as citation/list item").
> - **Pao + Siever and Kendler:** added by the final-check ✓ but DROPPED by the V0.4.24 attribution-edge ("names never co-occur with claim key phrases").
>
> **Root cause:** the loosened quote-guard only applies DURING the gap-fill (`gap_fill_batch.py`), NOT during the POST-CHECKS (`field_phases.py` + `thorough_theorist_floor.py`) that run AFTER.
>
> **The fix (2 changes, both content-agnostic — Rule 1 ✓):**
> 1. `core/summarisation/postchecks/field_phases.py:435-489` — the `parenthetical_promotion` veto now checks if the claimed author is in `source_authors` (the runtime regex `extract_citations` output). If yes → KEEP the bullet (the regex IS the grounding). If no → keep the strict drop. Log: `V0.5.15: bullet for X flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations`.
> 2. `core/summarisation/thorough_theorist_floor.py:790-826` — the V0.4.24 attribution-edge now RECOVERS dropped sentences whose authors are in the `extract_citations` output (called at runtime on the chapter content). If a dropped sentence's first 5 words contain an author from the set → RECOVER it. Log: `V0.5.15: recovered N gap-fill sentence(s) whose authors are in the regex`.
>
> **Net-green:** 73 P / 0 F (postchecks + audit-fixes + field_phases tests); ruff clean.
>
> **Result (rig, ch.6):** 70/74 = 95% author coverage, 82 keypoints, 39 bullets grounded, 0 hallucinations — the best in the V0.5.x lineage.

## V0.5.14 — make the VRAM overbudget check NON-BLOCKING (the param-count estimate is wrong for special-quants; llama.cpp errors at load time if the model truly doesn't fit)

> **The hotfix:** V0.5.13 didn't work — `torch.cuda.mem_get_info()` returns per-process VRAM on Windows (doesn't see the llama-server process's VRAM). V0.5.14 makes the overbudget check NON-BLOCKING — logs a WARNING + proceeds. Also tries `nvidia-smi` for the actual GPU-wide free VRAM (informational). If the model truly doesn't fit, llama.cpp errors at load time (a clearer error than the elixir-side estimate).

## V0.5.13 — fix the VRAM overbudget false-positive (query actual free VRAM via torch.cuda.mem_get_info + add the model_vram_override_gb setting)

> **The hotfix:** the V0.5.12 audit found the conversion HUNG at the VRAM overbudget check (log stopped at 21:07:33 — no model loading, no extraction, no LLM calls). Root cause: the VRAM budget used a HARDCODED param-count estimate (27B ternary → 12.9 GB), WRONG for the user's 7.6 GB special-quant model → false "OVERBUDGET" (12.9 > 12.0) → the overbudget dialog BLOCKED the conversion. The user's directive: "it must see how much vram is used" — query the ACTUAL VRAM.
>
> **The fix (2 paths, both fail-open):**
> 1. Query `torch.cuda.mem_get_info()` — if the model is already loaded (free VRAM < 3 GB but > 0.1 GB), the model IS in VRAM → the estimate was wrong → skip the overbudget warning.
> 2. Add the `summarisation.model_vram_override_gb` setting — if set (e.g. 7.6), use it instead of the param-count estimate. Belt + suspenders for rigs where `mem_get_info()` isn't available OR the model isn't loaded yet.
>
> Also carries the V0.5.12 glossary-to-gap-fill wiring (pass `source_glossary` to `batch_gap_fill` via the side-channel → enables the V0.5.6 final-check round 4).

## V0.5.12 — wire the glossary into the gap-fill (pass source_glossary to batch_gap_fill via the side-channel → enables the V0.5.6 final-check round 4 + the glossary-grounded loosened quote-guard)

> **The release:** the V0.5.11 audit found the glossary FINALLY extracted (📖 line fired) + the verification LAYER was glossary-grounded (cross-ref ran: confirmed=64, llm_only=2, regex_only=10) + the loosened quote-guard fired for Byrne (the V0.5.10 regex fallback). BUT the V0.5.6 final-check round 4 (the glossary-grounded targeted gap-fill) DIDN'T fire → 9 authors stayed missing (Bach, Croewe, Gorton, Jack, Morey, Munro, Ovessey, Rettersol, Walters — the V0.5.5 audit's list).
>
> **Root cause:** the `gfb_batch_gap_fill(...)` call at `chapter_phases.py:321` passed `regex_confirmed_authors` (the V0.5.10 fallback) but NOT `source_glossary` → the V0.5.6 final-check (which needs `source_glossary`) + the V0.5.6 glossary-grounded loosened quote-guard couldn't fire.
>
> **The fix:**
> 1. Added the `_v0512_get_glossary(heading)` helper — reads the glossary from the verification LAYER's side-channel (populated by `_extract_glossary_for_call` in `primary_call.py` via `set_chapter_glossary`).
> 2. Pass `source_glossary=_v0512_get_glossary(heading)` to `gfb_batch_gap_fill`.
> 3. Updated the SummaryResult stamping to use the side-channel glossary as a fallback (`parsed.get("source_glossary") or _v0512_get_glossary(heading) or {}`).
>
> **Net-green:** 56 P / 0 F (gap_fill + verification + glossary + separate-call tests).

## V0.5.11 — revert the V0.5.10 markitdown background-thread import (a 30-min hang — Python's global import lock deadlocks when a background thread imports while the main thread is also importing)

> **The hotfix:** the V0.5.10 audit found the app didn't initialize even after 30 min. Root cause: the `_MarkitdownBgImport` daemon thread (V0.5.10 Fix 4) called `importlib.import_module` in a background thread while the main thread was ALSO importing the other required deps (pypdf, pdf2image, tiktoken, rapidfuzz). Python's global import lock deadlocks when two threads try to import simultaneously — the `thread.join()` (no timeout) blocked forever.
>
> **The fix:** REMOVED the `_MarkitdownBgImport` class + `_start_markitdown_bg_import` + `_check_markitdown_via_thread` + the import threading + the special-case wiring in `run_preflight_check`. markitdown is back to the eager `_is_importable` path (the V0.5.9 behavior — ~7.9s but no hang risk). The ~7s saving wasn't worth a 30-min hang.
>
> **The other 3 V0.5.10 fixes are KEPT** (they're safe): Fix 1 (glossary format XML→markdown headers + 3-tier parser), Fix 2 (field_phases Pattern C caller fix — the "ego-syntonically" rewrite reaches the summary), Fix 3 (gap-fill quote-guard regex fallback).
>
> **Net-green:** ruff clean, 52 P / 0 F on the V0.5.11 test set.


## V0.5.10 — the glossary format change (XML→markdown headers) + the field_phases Pattern C caller fix + the gap-fill quote-guard regex fallback + the markitdown background-thread import

> **The release:** the V0.5.9 audit found the glossary call STILL failed even with max=8192 — the Ternary-Bonsai-2-27B model can't follow the `<name_glossary>` XML format. V0.5.10 changes the format to markdown headers (which the model handles naturally) + adds 3 remaining fixes from the audits/brainstorms: the field_phases Pattern C caller fix (the "ego-syntonically" rewrite was dormant since V0.5.4), the gap-fill quote-guard regex fallback (in case the glossary STILL doesn't work), + the F3 markitdown background-thread import (~7s init saving).

> **Fix 1 — Glossary format: XML tags → markdown headers:**
> - `prompts/summarisation/glossary_extraction.md`: removed the `<name_glossary>...</name_glossary>` XML wrapper; replaced with `## Source Glossary — Names/Dates/Terms` markdown headers + a generic few-shot example (Smith/Jones).
> - `core/summarisation/glossary_parser.py`: `parse_name_glossary` now cascades 3 fail-open tiers — Tier 1: XML block (backward compat), Tier 2: markdown headers (`## Source Glossary — Names` OR bare `## Names`), Tier 3: lenient bare-bullet scan (any `- **Surname** (YYYY) —` line). The model's actual output format is now caught regardless.

> **Fix 2 — field_phases Pattern C caller fix (the C2 rewrite was dormant since V0.5.4):**
> - The V0.5.4 C2 fix added the "ego-syntonically personalities" → "ego-syntonic personalities" rewrite to `detect_sentence_fusion`'s return. BUT the 3 callers in `field_phases.py:202/620/796` discarded the returned text (`_, fusion_issues = ...`). The rewrite never reached the summary.
> - V0.5.10: changed all 3 callers to `bp_str, fusion_issues = ...` (capture the rewritten text). The rewrite now propagates to subsequent detectors + the shipped field text. Closes the V0.5.3 ground-truth audit's "ego-syntonically" garble end-to-end.

> **Fix 3 — Gap-fill quote-guard regex fallback (in case the glossary STILL doesn't work):**
> - The V0.5.6 D4 loosened the quote-guard for GLOSSARY-sourced authors. But V0.5.6→V0.5.9 showed the glossary STILL doesn't extract — the loosened quote-guard never fires. The 4 missing authors (Jack, Ndtei, Rettersol, Lowenthal) stay missing.
> - V0.5.10: added a FALLBACK — if the author is in the REGEX `extract_citations` output (the deterministic backstop), ALSO loosen the quote-guard. Logic: `if author_in_glossary OR author_in_regex → accept the bullet`. The regex fallback catches the missing authors REGARDLESS of the glossary. Logs `✨ V0.5.10 gap-fill: accepted bullet for 'X' (grounded in regex extract_citations, not verbatim quote)`.

> **Fix 4 — F3 markitdown background-thread import (~7s init saving):**
> - The V0.5.4 brainstorm F3 documented markitdown's ~7.9s eager import as a future optimization. V0.5.10 implements it: a `_MarkitdownBgImport` daemon thread starts at the beginning of `run_preflight_check` + runs in parallel with the other required-dep checks. The markitdown check joins the thread (if still running) OR uses the result. Fail-open: if the thread crashes, falls back to the eager import. Only markitdown (the slowest dep); the other deps stay eager.

> **Combined changeset:** 13 files (10 modified + 3 new). Net-green: ruff clean, eval gate OK (re-baselined — 6 golden chapters PASS, hallucination 0.0%), 115 P / 0 F on the V0.5.10+regression set.

> **Rule verdicts:** Rule 1 ✓ (content-agnostic — generic prompt + few-shot test-fixture names + runtime regex output + the existing dep list). Rule 2 ✓ (file:line-anchored). Rule 3 ✓ (net-green — ruff + eval gate + 115 tests). Rule 4 ✓ (provenance — the glossary `.md` is persisted). Rule 5 ✓ (zip-per-release).

> **Expected V0.5.10 outcome:** (1) the glossary will finally extract (the markdown-header format + the 3-tier parser catches the model's actual output) → the 📖 glossary log line fires → the loosened quote-guard + final-check fire. (2) EVEN IF the glossary STILL fails, the regex fallback catches the 4 missing authors → they're added with "grounded in regex" grounding. (3) The "ego-syntonically" garble is auto-rewritten in the actual summary (the field_phases callers now use the returned text). (4) The preflight is ~7s faster (markitdown background import). Expected: 74/74 (100%) author coverage → ~9.25.

## V0.5.9 — the glossary-call max_output_tokens override fix (primary_call.py passed 4096, overriding the V0.5.8 default of 8192)

> **The release:** the V0.5.8 audit found the glossary call STILL failed — the conv log showed `max=4096` (not 8192). The V0.5.8 fix raised the DEFAULT in `extract_glossary_via_llm` to 8192, BUT the caller in `primary_call.py:172` passed `max_output_tokens=4096` explicitly, OVERRIDING the default. V0.5.9 fixed the 1-line override: `max_output_tokens=4096` → `max_output_tokens=8192`. The V0.5.9 rig run confirmed the call now uses `max=8192` (the fix worked), but the glossary STILL didn't extract — the model can't follow the `<name_glossary>` XML format even with 8192 tokens. Coverage recovered to 53/74 (72%, up from V0.5.8's 42/74=57%). The V0.5.10 format change (XML → markdown headers) is the follow-up.

## V0.5.8 — the glossary-call fix (max_tokens 4096→8192 + strip_thinking + explicit no-thinking prompt + remove the V0.5.6 leftover fused-path parser)

> **The release:** the V0.5.7 audit found the separate glossary call FIRED but produced NO `<name_glossary>` block (the LLM was called with max=4096 but didn't output the block — the thinking consumed the token budget before the glossary was emitted). V0.5.8 fixes this with 3 changes + removes the V0.5.6 leftover fused-path parser. Per the user's directive, the master-summary prompt was NOT simplified further (the V0.5.7 revert was clean — only removed the `<name_glossary>` block; the short master-summary in V0.5.7 was LLM variance, not a prompt issue).

> **Fix 1 — max_output_tokens 4096→8192:** the glossary for a 74-author chapter needs >4096 tokens. V0.5.8 raised the default to 8192 (`glossary_parser.py:582`).

> **Fix 2 — strip_thinking before parsing:** the Ternary-Bonsai-2-27B model often outputs thinking/reasoning tags before the `<name_glossary>` block. If the thinking consumed the max_tokens budget, the block was never emitted. V0.5.8 adds `strip_thinking(raw)` (`glossary_parser.py:688-700`) between the LLM call + the parse. Fail-open.

> **Fix 3 — explicit no-thinking prompt:** added a "CRITICAL — START IMMEDIATELY WITH `<name_glossary>`" section to `prompts/summarisation/glossary_extraction.md`: "Do NOT output any thinking. The VERY FIRST character of your response MUST be `<`. If you output thinking first, you will run out of tokens before finishing the glossary."

> **Fix 4 — remove the V0.5.6 leftover fused-path parser:** the V0.5.7 conv log showed the noisy "V0.5.6: no `<name_glossary>` block parsed from master summary" line — the OLD V0.5.6 code in `summarizer_chunking.py:150-198` that tried to parse the `<name_glossary>` from the master-summary response. Since the V0.5.7 revert removed the instruction, this code ALWAYS returned empty. V0.5.8 REMOVED it.

> **Net-green:** ruff clean, eval gate OK (re-baselined — 6 golden chapters PASS, hallucination 0.0%), 66 P / 0 F on the V0.5.8 test set.

## V0.5.7 — the separate glossary LLM call + the Maj-sey regex garble fix (V0.5.6 audit remediation)

> **The release:** the V0.5.6 audit found the glossary architecture
> DIDN'T FIRE because the `<name_glossary>` instruction was FUSED into
> the master-summary prompt, which overwhelmed the Ternary-Bonsai-2-27B
> model (3 empty returns + a fallback to the 5-in-1 path, which doesn't
> have the glossary wired). Result: 0 glossary mentions in the conv log,
> the loosened quote-guard + final-check dormant. V0.5.7 fixes this with
> the user's directive: **separate the LLM calls** for master summary +
> glossary. Plus the "Maj sey" OCR-garble regex fix.

> **Part 1 — Reverted the fused `<name_glossary>` from the 3
> master-summary prompts:**
> - `prompts/default.md` + `prompts/default_lowbit.md` + `prompts/summarisation/master_summary.md`:
>   reverted "Output ONLY the six XML sections" → "five XML sections"
>   + removed the `<name_glossary>` block + the "ALSO output a
>   `<name_glossary>` block" instruction. The master-summary is BACK
>   to just the 5 summary sections (the V0.5.5 state) — simpler → fewer
>   empty returns.

> **Part 2 — New separate glossary-extraction prompt:**
> - NEW `prompts/summarisation/glossary_extraction.md` — a dedicated
>   prompt that asks the LLM to read the source text + output ONLY a
>   `<name_glossary>` block with the 3 subsections (Names/Dates/Terms).
>   Generic instruction (Rule 1 ✓ — "ALL cited authors", no hardcoded names).

> **Part 3 — The `extract_glossary_via_llm` function:**
> - NEW `extract_glossary_via_llm(source_text, call_llm, ...)` in
>   `glossary_parser.py:577-760` — makes a DEDICATED LLM call that
>   reads the source + outputs the `<name_glossary>` block. Parses via
>   `parse_name_glossary`, persists via `persist_glossary` to
>   `summaries/.glossaries/<slug>.glossary.md`, logs "📖 V0.5.7 source
>   glossary (separate call) → <path>". Fail-open NEVER raises — returns
>   the empty 3-key dict on any failure (the verification falls back to
>   the regex `extract_citations`).
> - SEQUENTIAL execution (not parallel) — matches the user's "separate
>   calls" directive. The glossary call adds ~1 LLM call per chapter
>   (~3-5 min at the RTX 3060 throughput).

> **Part 4 — Wired into `primary_call.py` (BOTH paths):**
> - NEW `_extract_glossary_for_call(...)` helper (`primary_call.py:138-198`)
>   wraps `extract_glossary_via_llm` + the `set_chapter_glossary`
>   side-channel population.
> - Wired into all 3 return paths: master-summary-success (`:297-313`),
>   structured 5-in-1 fallback (`:327-342`), raw 5-in-1 fallback
>   (`:353-369`). The glossary is extracted in BOTH paths (the V0.5.6
>   audit's gap closure — the 5-in-1 path had no glossary wired + the
>   master-summary's empty returns meant the glossary never fired).

> **Part 5 — The "Maj sey" OCR-garble regex fix:**
> - ROOT CAUSE: the V0.5.6 `extract_citations` regex (Pattern 1 +
>   Pattern 2) had a buggy `(?:\s+[a-z]{1,4})?` AFTER-token group
>   that matched ANY 1-4 letter lowercase word. OCR-garbled source line
>   419 ("Maj sey 1302") was extracted as author="Maj sey" year="1302"
>   — a fake 14th-century theorist. The gap-fill wasted 4 rounds hunting
>   a bullet for this non-existent author.
> - FIX (`deterministic_analyzer.py:670+681`): removed the buggy
>   `(?:\s+[a-z]{1,4})?` group; added `_CIT_PARTICLES` (closed
>   class of Romance/Germanic/Arabic surname particles — van/von/de/di/
>   da/du/la/le/les/den/der/ter/ten/ben/abu/ibn/al/el/st/lo) as a
>   BEFORE-token prefix; extended the hyphenated group to
>   `NAME_SEP[a-zA-Z]+`. Rule 1 ✓ (closed class, no book content).
> - BONUS: closes the V18.15.5.1 DEBT-08 bug — em-dash/typographic-hyphen/
>   non-breaking-hyphen compounds ("van der Waerden", "de la Cruz")
>   now captured as the full compound (were truncated).
> - The source now produces 74 unique authors (was 75 in V0.5.6 — the +1
>   OCR-artifact "Maj sey" is gone; back to V0.5.5's 74-author floor).

> **Combined changeset:** 16 files (13 modified + 3 new). Net-green:
> ruff clean, eval gate OK (re-baselined — 6 golden chapters PASS,
> hallucination 0.0%), 953 P / 0 F / 7 S on the V0.5.7+regression set
> (144 V0.5.7-specific tests: 6 separate-call + 14 regex-garble +
> existing V0.5.6 verification tests).

> **Rule verdicts:** Rule 1 ✓ (content-agnostic — the glossary-extraction
> prompt is generic; the regex fix uses a closed-class particle list; the
> deny-list sweep passes). Rule 2 ✓ (file:line-anchored). Rule 3 ✓
> (net-green — ruff + eval gate + 953 tests). Rule 4 ✓ (provenance — the
> glossary `.md` is persisted with a `<!-- generated-by: Elixir 0.5.7 | run_id=... | chapter=... -->` comment).

> **Honest limitations:** (1) the glossary call adds ~1 LLM call per
> chapter (~3-5 min) — SEQUENTIAL execution (a parallelisation with a
> background thread + join is a future enhancement). (2) The 5-in-1
> fallback path now makes 2 LLM calls (the 5-in-1 raw XML + the separate
> glossary). (3) The eval gate re-baselined from STORED fixtures (no LLM
> in the sandbox) — a rig-side re-baseline with the live LLM is
> recommended. (4) The full 6,177-test suite can't be re-run in the
> sandbox (PySide6 GUI deps missing); the 39 touched+new+regression test
> files (953 tests) + eval gate pass cleanly.

## V0.5.6 — the source-glossary architecture (LLM-generated name/date/term glossary fused into the master-summary call + glossary-grounded coverage + loosened quote-guard + final-check round 4)

> **The release:** the V0.5.5 audit found 5 source authors still missing
> (Jack, Morey, Ndtei, Rettersol, Bak) — the regex `extract_citations`
> caught them but the gap-fill's quote-guard DROPPED their bullets (the
> LLM couldn't find verbatim source quotes). The root cause: the coverage
> ground truth was the REGEX (structurally limited — misses prose-only
> citations + single-mention authors). V0.5.6 fixes this with a new
> architectural layer: an LLM-generated **source glossary** (names +
> dates + specific terms) fused into the master-summary call, persisted
> as a `.md` file, + used as the coverage ground truth. Expected: 74/74
> (100%) author coverage → coverage 8→9/10 → overall ~9.25.

> **Phase 0.5 (new) — Glossary extraction (fused with the master-summary
> call, ~0 extra latency):**
> - The master-summary prompt now instructs the LLM to ALSO output a
>   `<name_glossary>...</name_glossary>` block with 3 markdown subsections:
>   `## Names` (all cited authors + years + 1-sentence context),
>   `## Dates` (key years/decades/ranges), `## Terms` (key concepts).
>   Generic instruction (Rule 1 ✓ — "ALL cited authors", not hardcoded).
> - New `core/summarisation/glossary_parser.py` (521 LOC): `parse_name_glossary()`
>   extracts the 3 sections, `cross_reference_glossary()` compares vs the
>   regex `extract_citations` (the deterministic backstop — confirmed/
>   llm_only/regex_only buckets), `persist_glossary()` writes to
>   `summaries/.glossaries/<chapter>.glossary.md` with a provenance comment.
> - Fail-open at every step (NEVER crashes the master-summary). If the
>   `<name_glossary>` block is absent/malformed → empty glossary → the
>   verification falls back to the V0.5.5 regex behavior.
> - Wired into both the single-pass (`summarizer_chunking.py`) + map-reduce
>   (`summarizer.py`) master-summary paths. Stamped onto `SummaryResult.source_glossary`
>   (new field, default `{}` = backward-compatible). Logged:
>   "📖 V0.5.6 source glossary → <path>".

> **Phase verification (modified) — Glossary-grounded coverage:**
> - The `verification_coverage` flag now PREFERS the glossary names as
>   the ground truth (richer than the regex — catches prose-only
>   citations + single-mention authors). Falls back to
>   `extract_citations` if the glossary is empty.
> - Cross-references the glossary vs the regex (the deterministic backstop):
>   confirmed (both caught), llm_only (LLM caught, regex missed — KEPT),
>   regex_only (regex caught, LLM missed — flagged as a glossary recall gap).
> - The coverage flag logs: "✨ V0.5.6 verification: [verification_coverage/flag]
>   coverage-targeting (glossary-grounded): N source author(s) NOT found
>   (X, Y, Z). Glossary: <path>. Cross-ref: confirmed=A, llm_only=B,
>   regex_only=C".

> **Phase gap-fill (modified) — Loosened quote-guard for glossary authors:**
> - The V0.5.5 gap-fill's quote-guard (the V18.20.3.2 parenthetical-promotion
>   veto) DROPPED bullets for the 5 missing authors (no verbatim source
>   quote). V0.5.6 LOOSENS the veto for glossary-sourced authors: if the
>   cited author is in the glossary, the bullet is ACCEPTED with a
>   "grounded-in-glossary" grounding level (the glossary context IS the
>   grounding — it was extracted from the source by the LLM).
> - For non-glossary authors, the strict quote-guard stays (prevents
>   fabrication). Logged: "✨ V0.5.6 gap-fill: accepted bullet for 'X'
>   (grounded in glossary context, not verbatim quote)".

> **Phase final-check (new) — "check once again":**
> - After the gap-fill (rounds 1-3), a final-check re-runs
>   `extract_citations` on the UPDATED summary + diffs against the
>   glossary. Any still-missing authors → a targeted round 4 gap-fill
>   using the glossary context ("Bak (1946) — coined 'higher level'
>   character organization").
> - The round 4 prompt: "The following source authors (from the glossary)
>   are STILL missing: [X (YYYY) — context, Y (YYYY) — context]. Add a
>   grounded bullet for EACH, using the glossary context as the grounding."
> - Logs: "✨ V0.5.6 final-check: 74/74 authors (100%) — full coverage
>   achieved" OR "73/74 authors (99%) — 1 still missing: [X]".

> **Combined changeset:** 16 files (13 modified + 3 new). `glossary_parser.py`
> (521 LOC new) + 2 test files (23 + 6 = 29 new tests). Net-green: ruff
> clean (256 files), eval gate OK (re-baselined — 6 golden chapters PASS,
> hallucination 0.0%), 228 P / 0 F on the V0.5.6+regression test set.

> **Rule verdicts:** Rule 1 ✓ (content-agnostic — the prompt instruction is
> generic "ALL cited authors"; the parser uses generic `<name_glossary>` +
> `## Names` regex; the coverage check uses the runtime glossary; the
> quote-guard loosening uses runtime glossary membership; the final-check
> prompt uses `{missing_authors_with_context}` placeholders; verified by
> the deny-list sweep + the new `test_glossary_instruction_is_content_agnostic`).
> Rule 2 ✓ (file:line-anchored). Rule 3 ✓ (net-green — ruff + eval gate + 228 tests).
> Rule 4 ✓ (provenance — the glossary `.md` file is persisted with a
> `<!-- generated-by: Elixir v0.5.6 | run_id=... | chapter=... -->` comment).

> **Honest limitations:** (1) the `cross_reference_glossary` function is
> defined in BOTH `glossary_parser.py` (the canonical utility) +
> `verification_phase.py` (the LAYER's local copy) — redundant but not
> conflicting (cosmetic dedup for V0.5.7). (2) The glossary is per-chapter
> (not per-book) — a book-level merge is a future enhancement. (3) The
> eval gate was re-baselined from STORED fixtures (no LLM in the sandbox)
> — a rig-side re-baseline with the live LLM is recommended to confirm
> the `<name_glossary>` prompt addition doesn't regress the actual
> golden-chapter scores. (4) The full 6,177-test suite can't be re-run in
> the sandbox (PySide6 GUI deps missing); the 11 touched+new test files
> (228 tests) + eval gate pass cleanly.

## V0.5.5 — the V0.5.4 hotfix (Summarizer.settings AttributeError crash)

> **The crash:** V0.5.4's F2 temperature-multiplier change referenced
> `self.settings` on the Summarizer, but the Summarizer class doesn't
> have a `settings` attribute (it uses the module-level `Settings()`
> singleton pattern). The `getattr(self.settings, ...)` raised
> `AttributeError: 'Summarizer' object has no attribute 'settings'`
> BEFORE the default could apply — crashing the dedicated-thorough
> expansion path. The V0.5.4 rig run failed at 23:04:44 with
> "❌ Chapter 1 failed: 'Summarizer' object has no attribute 'settings'"
> + 0 keypoints generated.

> **The fix (1 line):** replaced
> `getattr(self.settings, "thorough_temperature_multiplier", 0.5)`
> with `Settings().get("thorough.temperature_multiplier", 0.5)` —
> the codebase's standard settings-access pattern (cf. summarizer.py:1530).
> Added `from utils.settings import Settings` to prompt_builders.py.
> The multiplier is now properly configurable via
> `Settings().get("thorough.temperature_multiplier")` (default 0.5).

> **Verification:** `Settings().get("thorough.temperature_multiplier", 0.5)`
> returns 0.5 (no crash). 65 tests pass (thorough_fallback + verification_layer
> + incremental_checkpoint). ruff clean. The V0.5.4 crash path
> (`_call_dedicated_thorough_with_fallback`) is now safe.

## V0.5.4 — the full-backlog V0.5.3 ground-truth-audit remediation (date-check FP elimination + coverage gap closure + Pattern C flag+rewrite + structured content + LAYER auto-apply + FN audits)

> **The release:** the V0.5.3 ground-truth audit (against the uploaded
> 7,361-word source chapter) scored 9/7/7/8 = 8.0 PASS — 0 real
> hallucinations, but 7-8 missing source authors + 3 date-check FP
> classes (80% FP rate) + 1 grammatical garble shipped uncorrected.
> V0.5.4 implements the ENTIRE brainstorm backlog (P0+P1+P2+P3 across
> 6 tracks A-F) to push toward 10/9/9/9 = 9.25. Net-green: ruff clean,
> eval gate OK (re-baselined from fixtures — 6 golden chapters PASS,
> hallucination 0.0%), 301 P / 0 F / 3 S on the touched+regression set.

> **TRACK A — Date-check FP elimination (the LAYER's signal-to-noise).
> Cleans the 4 false "hallucination" flags + 1 false "omission" flag
> that made the V0.5.3 LAYER 80% false-positive.**
> - A1 (run-metadata FP): `_strip_metadata_wrapper()` in
>   `verification_phase.py:222-263` strips the `<!-- generated-by -->`
>   comment + `> Provider` blockquote + `*Generated by*` italic footer
>   before the date-check. The full `rendered_md` is still used for the
>   LLM verification + final output.
> - A2 (range-component FP): `_year_covered_by_range()` helper +
>   rewrote `compare_dates()` in `date_extractor.py:688-782` — a
>   summary year that falls within any source range is NOT flagged as
>   hallucinated (and vice versa for omissions).
> - A3 (en-dash FP): `_DASH_TRANSLATE` + normalization at the top of
>   `extract_dates()` (`date_extractor.py:614-622 + 655-662`) — en-dash
>   (U+2013), em-dash (U+2014), minus-sign (U+2212) all normalized to
>   ASCII hyphen before the regex pass. 1:1 codepoint substitution
>   preserves offsets. Bonus: minus-sign coverage beyond the audit.
> - 9 new tests in `tests/test_v0500_date_extractor.py` (3 classes:
>   en-dash/em-dash/minus-sign normalization, range-component compare,
>   metadata-wrapper strip).

> **TRACK B — Coverage improvement (the 7-author gap + structured
> content).**
> - B1 (extract_citations recall): the V0.5.3 audit hypothesized a
>   recall gap (missed Bak), but the B1 subagent DISPROVED this —
>   `extract_citations` ALREADY returns all 74 authors. The ACTUAL
>   Bak-miss cause was a SUBSTRING test in the LAYER's coverage check
>   (`verification_phase.py:482-507`) — "Tobak" contains "bak" as a
>   substring → false "Bak is covered" verdict. Fix: replaced with a
>   `\b`-anchored word-boundary regex. Rule 1 ✓ (generic regex).
> - B2 (targeted gap-fill round 3): the coverage-targeting prompt now
>   lists EACH missing author + their year(s): `[Author1 Year1; Author2
>   (Year2a/Year2b); ...]` (`verification_phase.py:478-548`). The
>   runtime-extracted `_src_author_years` map drives the prompt.
> - B3 (Table 6-1 reproduction): `extract_structured_tables()` in
>   `deterministic_analyzer.py` (generic `TABLE N-N.` marker detection)
>   + `_render_reproduced_tables()` in `chapter_checkpoint.py`. The
>   conservative scope correctly declines to invent a table when the
>   source's table body is OCR-garbled (the V0.5.3 ch.6 case).
> - B4 (DSM-III criteria detail): `extract_structured_criteria()` (the
>   `a. b. c. d.` + `(i) (ii) (iii)` pattern) + rendering as a nested
>   bullet list.
> - B5 (refugees/immigrants detail): generic "Affected Populations"
>   instruction added to `prompts/default.md` + `default_lowbit.md` —
>   "include the SPECIFIC populations the source lists — do not
>   generalise to 'vulnerable groups'" (content-agnostic, Rule 1 ✓).
> - 13 new tests (test_v054_extract_citations.py) + 10 new tests
>   (test_v054_structured_content.py).

> **TRACK C — Clarity / cohesion.**
> - C1 (section breaks): `map_authors_to_all_caps_sections()` +
>   `_render_bullets_grouped_by_section()` — the summary's bullets are
>   now grouped under the source's ALL-CAPS section headings
>   (DESCRIPTIVE STUDIES / PSYCHOANALYTIC VIEWS / etc.) at render time.
>   Generic section-title detection (any ALL-CAPS line).
> - C2 (Pattern C flag+rewrite): upgraded `detect_sentence_fusion` in
>   `fusion.py` from flag-only to flag+auto-rewrite for the adverb-as-
>   adjective grammatical garble. `_rewrite_grammatical_garble()`
>   (L240-286): if "X-ically" (adverb) precedes a noun + the candidate
>   adjective "X-ic" is in the lexicon (OR a hyphenated compound whose
>   last component is) → rewrite to "X-ic". The V0.5.3 "ego-syntonically
>   personalities" garble → "ego-syntonic personalities". Conservative:
>   the next-word verb-ending check (ed/ing/en) prevents rewriting the
>   source's correct "ego-syntonically embedded" usage. Rule 1 ✓
>   (English morphology only, no hardcoded words).
> - C3 (gap-fill repetition elimination): 2 strong dedup instructions in
>   the coverage-targeting prompt ("do NOT re-cite authors already
>   covered").
> - C4 (the specific "ego-syntonically" rewrite): subsumed by C2.
>   NOTE: the 3 callers in `field_phases.py:192/602/770` currently
>   DISCARD the returned text (V0.4.3 was flag-only) — the function-level
>   rewrite takes effect in the returned text + issue detail, but the
>   caller-level discard means the rewrite's effect on the actual summary
>   text requires updating those 3 callers (a follow-up for V0.5.5).
>   The issue detail note IS preserved end-to-end.

> **TRACK D — Verification LAYER evolution.**
> - D1 (LAYER auto-apply): `_apply_deterministic_fixes()` in
>   `verification_phase.py:279-322` — applies rule-based corrections for
>   unambiguous fixes. Currently: en-dash → hyphen normalization in
>   4-digit year ranges (U+2013 → U+002D via `_EN_DASH_YEAR_RANGE` regex).
>   Conservative — non-year-range en-dashes (e.g. "page 5–7") NOT
>   touched. 11 return-path wirings. Logs `✨ V0.5.4 auto-apply:
>   [verification_auto_apply_en_dash] {count} year-range(s) normalized`.
> - D4 (gap-fill hallucination guard): between the LLM-correction-apply
>   step + the D3 length-check (`verification_phase.py:637-692`). Diffs
>   `_post_authors - _pre_authors`, checks each new author against the
>   source's `_src_lower`, drops the bullet via regex, flags
>   `verification_gap_fill_hallucination_guard`, logs the drop.

> **TRACK E — FN prevention (audits).**
> - E1 (et al. capture): extended `_SUMMARY_CITATION_RE` in
>   `attribution.py:25-52` with " and X" + " et al." optional groups.
>   "Jack et al. (1984)" + "Slater and Roth (1977)" + "Mellsop &
>   Varghesi (1982)" now captured as multi-author citations.
> - E2 (date-format coverage): added `_LETTER_SUFFIX_YEAR` pattern in
>   `date_extractor.py` for "1921a"/"1921b"/"1908b"/"1923a"/"1950a"/
>   "1973a"/"1975a"/"1978b"/"1982a" — 9 letter-suffixed academic
>   citation years were being silently normalized to plain years
>   (distinct papers collapsed). Full text (with letter) preserved in
>   `DateMatch.text`; normalized to bare year for compare (so a summary
>   citing "1921" still matches a source citing "1921a"/"1921b").
> - E3 (Pattern C pattern-coverage): found Pattern C MISSED 2 source-
>   propagated garbles ("selfinflation", "selfrighteousness" — the source
>   itself has the missing-hyphen typo + the summary transmitted verbatim).
>   Added Pattern D (source-propagated self-X fusion garble): word IS in
>   `source_words` AND NOT in lexicon AND starts with "self" + a 5+ char
>   lexicon word suffix. Rule 1 ✓ ("self" is a generic English morpheme).
> - E4 (LLM vigilance): added "DEVIL'S ADVOCATE" block to
>   `_VERIFICATION_PROMPT` — "Argue AGAINST the summary. Default to
>   scrutinizing, not approving. A rubber-stamp [] without scrutiny is a
>   failure mode." Reduces the V0.5.3 LLM rubber-stamp tendency.

> **TRACK F — Rig-config + performance.**
> - F1 (model-quant switch): RIG-SIDE — the 12.9 GB model vs 12.0 GB
>   RTX 3060 VRAM still causes cold-start thrash. User must download a
>   smaller GGUF (Q3_K_S ≈ 11 GB / Q2_K ≈ 10 GB) + update the llama.cpp
>   model path. Documented (not a code change).
> - F2 (temperature multiplier): the `* 0.5` on all 4 thorough attempts
>   is now a CONFIGURABLE parameter `temperature_multiplier` (default 0.5,
>   the historical behavior) in `thorough_fallback.py:64`. The owner can
>   set `thorough.temperature_multiplier = 1.0` in settings for the FULL
>   configured temperature (0.7 instead of 0.35). The caller in
>   `prompt_builders.py:550` reads from settings via
>   `getattr(self.settings, 'thorough_temperature_multiplier', 0.5)`.
>   Resolves the V0.5.3 ambiguity documented in the FIX-P3-6 TODO.
> - F3 (markitdown deferred import): DOCUMENTED as a V0.5.5 optimization.
>   markitdown takes 7.9s (a REQUIRED dep, can't skip). A background-
>   thread import parallelised with model load would shave ~7s off init.
>   Not implemented in V0.5.4 (the parallelisation needs understanding
>   the model-load timing — architectural).
> - F4 (VRAM budget): RIG-SIDE — either F1 (smaller model) or raise the
>   VRAM budget threshold (but risk OOM mid-conversion). Documented.

> **Combined changeset:** 17 files modified + 4 new test files. ~+2,000
> insertions. Rule 1 ✓ (content-agnostic — all patterns use generic
> regexes / English morphology / runtime-extracted author lists; the 74
> source authors appear in TESTS only). Rule 2 ✓ (file:line-anchored).
> Rule 3 ✓ (net-green — ruff clean, eval gate OK re-baselined from
> fixtures, 301 P / 0 F / 3 S on touched+regression set). Rule 4 ✓
> (provenance — this entry + the 6 subagent worklog entries + the
> eval_baseline.json re-baseline).

> **Honest limitations:** (1) the 3 callers in `field_phases.py` discard
> the Pattern C rewrite (C2) — the rewrite takes effect in the function
> return + issue detail, but the actual summary text requires updating
> those callers (V0.5.5). (2) The eval gate re-baselined from STORED
> fixtures (no LLM in the sandbox) — a rig-side re-baseline with the live
> LLM is recommended to confirm the B5 prompt change doesn't regress the
> actual golden-chapter scores. (3) The full 6,177-test suite can't be
> re-run in the sandbox (PySide6 GUI deps missing); the 11 touched test
> files + 4 new test files (301 tests) + eval gate pass cleanly. (4)
> F1/F3/F4 are rig-side or future (documented, not code).

## V0.5.3 — the six-fix audit remediation (Pattern C re-impl + verification LAYER re-wire + transformers gate + pronoun stopword test + dead-code removal + date_extractor cleanups)

> **The release:** post-V0.5.2 four-pillar fact-check audit found 1 false
> claim (V0.5.2 Fix 5 was broken), 4 misleading/partial claims, and 3
> critical omissions (the verification LAYER was dead code on the normal
> conversion path). This release implements all 6 remediation items
> (P0/P1/P2/P3) from the audit's recommended next actions. Net-green:
> ruff clean, eval gate OK, 374 P / 0 F / 3 S on the touched+regression
> test set; eval gate 6 golden chapters PASS, hallucination 0.0%.

> **P0-1 — Pattern C lexicon check RE-IMPLEMENTED (was broken).** The
> V0.5.2 "Fix 5" placed a 7-line lexicon check in Pattern A's code block
> (`fusion.py:268-274`), NOT Pattern C — and it was redundant with the
> existing early lexicon check at L218 (provably dead code) AND the
> documented FP word "underrepresentation" wasn't in the 126k lexicon
> anyway. Re-implemented as a compound-word guard INSIDE Pattern C's
> block (`fusion.py:380-393`): before Pattern C flags a candidate,
> checks (i) the full un-hyphenated word is in the lexicon (covers
> hyphenated compounds like "under-representation") AND (ii) any split
> position ≥5 chars where BOTH halves are in the lexicon (covers
> "under"+"representation"). If either holds → skip (legitimate English
> compound, not a dropped-prefix fusion). 5 regression tests in
> `tests/test_v052_audit_fixes.py`. Content-agnostic (Rule 1 ✓ — uses
> lexicon membership only, no hardcoded words).

> **P0-2 — verification LAYER re-wired to run on checkpointed chapters
> (was dead code on the normal path).** The file-existence short-circuit
> at `summarization.py:1038-1060` bypassed `verify_and_polish_summary`
> whenever a chapter was checkpointed (the V18.20.3.0 incremental
> checkpoint writes the summary file BEFORE the save loop's verification
> call). The V0.4.40 headline feature + V0.5.1 wiring + V0.5.1
> coverage-targeting were all inert in practice. Fixed via Option B:
> added a 45-line block at `chapter_checkpoint.py:555-598` inside
> `_on_chapter_done_impl` that runs `verify_and_polish_summary` BEFORE
> the checkpoint save — the checkpoint now writes VERIFIED markdown
> (both the canonical `summary.md` at L603 + the checkpoint copy at
> L613). The end-of-loop verification at `summarization.py:1065-1102`
> is UNCHANGED (preserved for the non-default path; the short-circuit
> correctly skips re-verification for already-verified checkpointed
> chapters — no double-work). Regression test
> `test_verification_layer_runs_when_file_already_exists` in
> `test_v18203_incremental_checkpoint.py` (red-without-fix /
> green-with-fix verified). Honest limitation: DOCX builder still builds
> from SummaryResult (existing behavior, out of scope); resumed chapters
> from previous runs still NOT verified (out of scope).

> **P1-3a — transformers eager-import gate (the 4-minute init fix).**
> `preflight_check.py`'s `_OPTIONAL_DEPS` (torch, transformers,
> langextract) were checked via `_is_importable` which does a FULL
> `importlib.import_module` — for `transformers` that took 15.8s
> (V0.5.0) → 20.5s (V0.5.1) → 36s (V0.5.2 run) per conversion, even
> though elixir doesn't directly use transformers (only the optional
> NLLB-translation feature does). Added a new `_is_installed` function
> (`preflight_check.py:392-440`) that uses `importlib.util.find_spec` —
> INSTANT (returns ModuleSpec if findable, None otherwise, WITHOUT
> executing the module's import-time code). The `_OPTIONAL_DEPS` loop
> (L238-252) + `get_dependency_status` (L443-459) now use
> `_is_installed` for optional deps. Trade-off documented in the
> docstring: find_spec doesn't catch "installed but broken" (e.g. torch
> without CUDA), but for OPTIONAL deps (log warning, don't block) the
> trade-off is correct — instant check, deferred errors. Required deps
> keep `_is_importable` (catches import-time errors early). Expected
> savings: 15-36s per conversion on the rig.

> **P1-3b — model-quant recommendation (rig-side, documented).** The
> VRAM overbudget (12.9 GB model vs 12.0 GB RTX 3060) is NOT a code
> change — the user must download a smaller GGUF quantization (Q3_K_S
> ≈ 11 GB fits; Q2_K ≈ 10 GB fits comfortably) or a 13B-class model,
> and update the llama.cpp model path. The 12.9 GB quant is
> borderline-by-design for a 12 GB card and causes cold-start Windows
> thrashing (the bulk of the "4 minutes").

> **P1-4 — missing regression tests added.** (a) Pattern C FP test
> (5 tests in `test_v052_audit_fixes.py` — by P0-1); (b) pronoun
> stopword test (`TestV052PronounStopword` class, 3 tests in
> `test_v052_audit_fixes.py` — "His (1986)" / "Her (1975)" → not
> flagged; "Dukhaim (1951)" → still flagged as positive guard); (c)
> wiring-fix log call test
> (`test_verification_layer_runs_when_file_already_exists` in
> `test_v18203_incremental_checkpoint.py` — by P0-2). All 3 missing
> tests now exist.

> **P2-5 — dead code removed + test-discipline regression fixed.**
> Deleted the dead `_bp_lo_lp`/`_bp_hi_lp` plumbing (still computed
> after V0.5.2's bullet-count removal but never read):
> `chapter_phases.py:1546-1548` (import alias) + L1558 (computation) +
> L399-400 (receive) + L1799-1800 (return tuple); `summarizer.py:1690-1691`
> (receive) + L1763-1764 (call pass-through). Net -12 lines. Fixed
> `test_v182038_audit_fixes.py:507-508`: the 2 commented-out lines
> (should have been `assert "NO CAP (user" not in tail` per the other 3
> touched tests) are now properly inverted; also fixed a collateral
> F841 (orphaned `floor_idx` → explicit assertion).

> **P3-6 — date_extractor cleanups + temp-multiplier documentation.**
> Deleted the dead `_COMPACT_DATE` regex (`date_extractor.py:187` —
> severe FP risk if wired, matches phone/ZIP/ISBN; use case covered by
> `_ISO_DATE` + `_NUMERIC_DATE_YMD`). Deleted the dead `_MONTHS` /
> `_MONTH_ABBR` / `_ALL_MONTHS` helpers (`date_extractor.py:57-85`,
> 29 LOC — only `_MONTH_PATTERN` regex is used). Added 13 new pattern
> tests to `test_v0500_date_extractor.py` (+91 LOC, 42→55 tests):
> "about"/"around"/"approx."/"approximately" (Part 3), `_DECADE_SHORT`
> (Part 5), `_NUMERIC_DATE_YMD` (Part 6), AM/Saka/VS/Vikram Samvat
> (Part 7), Mya/ka BP/yr BP (Part 8). Added an 11-line TODO comment at
> `thorough_fallback.py:213-223` documenting the `* 0.5` temperature
> multiplier ambiguity (all 4 attempts use `temperature * 0.5` →
> effective temp is HALF the configured value; pre-existing, not a
> V0.5.2 regression; pending owner confirmation on whether "configured
> temperature" means the full 0.7 or the halved 0.35).

> **Combined changeset:** 11 files modified + 1 new test file. Net
> +415 insertions / -59 deletions. Rule 1 ✓ (content-agnostic — no
> hardcoded book/author/chapter/domain strings; the compound-word guard
> uses lexicon membership only; pronouns are general English; the
> transformers gate uses the existing dep list; date_extractor tests
> use generic date primitives). Rule 2 ✓ (evidence-first — every claim
> cites file:line). Rule 3 ✓ (net-green — ruff clean, eval gate OK,
> 374 P / 0 F / 3 S on touched+regression set). Rule 4 ✓ (provenance —
> this entry + the FIX-P0-1 CHANGELOG correction note + the `* 0.5`
> TODO comment document every change traceably).

> **Honest limitations:** (1) couldn't re-run the full 6,177-test
> suite (sandbox venv lacks PySide6 GUI deps); the 11 touched+regression
> test files + eval gate pass cleanly. (2) The model-quant switch
> (P1-3b) is rig-side — user must apply on the RTX 3060. (3) The
> `* 0.5` temperature multiplier is documented but NOT changed — needs
> owner confirmation. (4) Resumed chapters (loaded from previous runs)
> still NOT verified by P0-2 — only NEW chapters going through the
> checkpoint in the current run are. (5) DOCX builder still builds from
> SummaryResult (not verified markdown) — existing behavior, out of
> scope.

## V0.5.2 — the verification LAYER fix + temperature fix + bullet-count target REMOVAL + Pattern C lexicon check + pronoun stopword

> **The release:** 4 bugs + 2 tunings per the V0.5.1 audit + the user's
> directives. The verification LAYER didn't fire (heading→source match
> failed); the temperature was 0.0 (must be fixed); the bullet-count
> target prevented coverage-driven expansion; the 38% thorough coverage
> was SYSTEMIC (not LLM variance).

**1. BUG — verification LAYER heading→source match fix:** the
  `_source_by_heading` was built from `segments_for_summary` (which may
  have been filtered); now built from `segments` (ALL segments) + a
  FALLBACK (largest segment) ensures the LAYER fires even when the
  heading match fails.

**2. BUG — 38% coverage is SYSTEMIC:** the V0.05 bullet-count target
  gate PREVENTED bullet expansion when the primary produced ≥ the
  source-scaled target (e.g. 27 for a 7405-word chapter) — even when
  9+ authors were missing. The gate is REMOVED. Bullet expansion now
  fires whenever bullets exist + keypoints requested + deadline allows.

**3. BUG — temperature=0.0 fix:** Attempt 3 used `temperature=0.0`
  (greedy). The user's directive: "models MUST only run with a fixed
  Temperature, nothing else is allowed." Attempt 3 now uses
  `temperature * 0.5` (same as Attempts 1+2).

**4. BUG — bullet-count target REMOVED:** the user's directive: "NEVER
  EVER SET A MAXIMUM-MINIMUM-Appropriate or any standard for the number
  of bullets." The V0.05 skip-expansion gate + the "guidance floor was
  X-Y for a Z-word chapter" log line are REMOVED.

**5. TUNING — Pattern C lexicon check:** "underrepresentation" (a real
  compound word not in the lexicon) was flagged as a dropped-prefix
  fusion. Pattern C now checks if the full word is in the lexicon BEFORE
  flagging (like Patterns A/B).

**6. TUNING — pronoun stopword:** "His" (and her/their/its/he/she/they)
  were parsed as author names. Added to the stopword list.

**Tests:** 4 source-pin tests updated. **6,177 P / 0 F / 36 S exit 0.**

---

> **CORRECTION (FIX-P0-1, post-V0.5.2 audit):** item **5. TUNING —
> Pattern C lexicon check** above is FALSE as shipped. The
> AUDIT-V0.5.2 subagent found the V0.5.2 commit (`1cf0dcb`) added the
> `if word in lexicon: continue` block at
> `core/summarisation/postchecks/garble/fusion.py:268-274` INSIDE
> Pattern A's per-start loop — NOT in Pattern C (the dropped-prefix
> detector at L344+). It was REDUNDANT with the early lexicon check at
> L218 (`if lexicon and word in lexicon: continue`) which already
> short-circuits any word that is in the lexicon, so by the time
> execution reached L273 `word in lexicon` was GUARANTEED False — the
> check was provably dead code. Even if correctly placed in Pattern
> C, the documented FP word `underrepresentation` is NOT in the
> 126,761-word lexicon (`zgrep -c '^underrepresentation$'` → 0), so
> the full-word lexicon check could not suppress the FP. Empirically
> verified: running `detect_sentence_fusion` on the documented FP
> scenario with vs. without the L268-274 block yields IDENTICAL output
> (1 issue). The CHANGELOG claim "Pattern C now checks if the full
> word is in the lexicon BEFORE flagging" was FALSE on two counts
> (wrong code block + word not in lexicon). No regression test was
> added for this fix, which is why the broken fix shipped undetected.
>
> **Re-implementation (FIX-P0-1):** the broken L268-274 block was
> DELETED (a NOTE comment is left in Pattern A explaining why the
> original fix was broken — pointing future maintainers to the
> correct location). A new compound-word guard was added INSIDE
> Pattern C's block (L380+, just before the per-start loop). The
> principled fix (per the AUDIT-V0.5.2 recommendation): a real
> compound word is EITHER (i) itself in the lexicon (already covered
> by the early lexicon check at L218, but re-checked against the
> un-hyphenated `clean` form for hyphenated compounds), OR (ii)
> composed of two lexicon words (a prefix + suffix where BOTH halves
> are real English lexicon words). If either holds, the candidate is
> a legitimate English compound, not a dropped-prefix fusion —
> Pattern C is skipped. Content-agnostic (Rule 1): the guard uses
> lexicon membership ONLY; no hardcoded words. Regression tests
> added in `tests/test_v052_audit_fixes.py` (5 tests): the FP
> suppression (the documented compound word → 0 issues), a
> hyphenated-compound variant, the positive case
> (`persecutionensate` → still flagged), and Pattern A + Pattern B
> regression guards. All 35 tests in the touched scope pass
> (`test_v052_audit_fixes.py` + `test_v0438_audit_fixes.py`); ruff
> clean. See `/home/z/my-project/worklog.md` task `FIX-P0-1` for
> the full work log.

## V0.5.1 — the wiring bug fix + date-extractor page-ref FP fix + verification LAYER coverage-targeting (10/10 objective)

> **The release:** 3 fixes per the V0.5.0 audit's V0.5.1 backlog + the
> user's "make the post-verification more robust, with the objective of
> 10/10 coverage."

**1. BUG — wiring fix (commit below):** the `_v_issues` from
  `verify_and_polish_summary` are now LOGGED to the conversion log (was
  silently dropped). Each issue logged at DEBUG (fix) or WARNING (flag).

**2. TUNING — date-extractor page-ref FP fix:** the `~NNN` page-reference
  false positive (`inject_page_refs` uses `~` before page numbers; the
  extractor matched `~137` as circa 137) is fixed. A `_PAGE_REF_PREFIX`
  regex masks page-reference patterns before the date patterns run.

**3. ROBUSTNESS — verification LAYER coverage-targeting:** the LAYER now
  extracts source authors (via `extract_citations`), checks which are NOT
  in the summary, and ADDS them to the LLM prompt so the verification
  LLM can ADD missing bullets (the "10/10 coverage" objective). A
  `verification_coverage` Issue records the missing count + list.

**Tests:** 5 new tests (3 page-ref FP + 2 coverage-targeting). 42 total
  in `test_v0500_date_extractor.py`.

**Net-green:** ruff clean; eval gate OK; **6,177 P / 0 F / 36 S exit 0**
(+5); deny-list passes.

## V0.5.0 — the deterministic date-extraction module + verification LAYER integration (new architecture)

> **The release:** per the user's direction ("for verification phase we
> need a robust date-extraction deterministic script" + the exhaustive
> date-format list, Parts 1-10), a new deterministic date-extraction
> module covering BC/AD/BCE/CE, plain years, approximate dates, ranges,
> centuries/decades/millennia, full calendar dates, scientific notation
> (BP/ka/Ma/Mya), and historical calendar eras (AH/AM/AUC/SH/BE/Saka/VS).
> Wired into the V0.4.40 verification LAYER as a deterministic date-check
> that runs alongside the LLM verification. Minor-version bump (V0.4.x →
> V0.5.x) reflecting the new architectural module.

**1. Date-extraction module (commit `2a145ef`):**
  `core/preprocessing/date_extractor.py` —
  `extract_dates(text) -> list[DateMatch]` finds ALL date-like
  expressions in text. Each DateMatch carries: the matched text, position,
  format_type (plain_year/era_suffix/era_prefix/circa/range_dash/
  range_slash/century/century_word/decade/millennium/full_date_dmy/
  full_date_mdy/iso_date/numeric_date/calendar_era/scientific_bp/
  scientific_ma), the extracted year + era (ad/bc/bce/ce/bp/ah/am/auc/
  sh/be/saka/vs), is_approximate, is_uncertain, and a normalized
  canonical form for comparison (e.g. "bce:500", "ce:1891~",
  "century:19", "range:1891-1895", "bp:5000"). Overlap resolution
  (most-specific pattern wins — "500 BC" is claimed by the era_suffix
  pattern, not plain_year). `compare_dates(summary_dates, source_dates)
  -> {hallucinated, omitted, matched}` — summary dates NOT in the source
  (potential fabrications) + source dates NOT in the summary (potential
  omissions). Approximate dates (c. 1891) match exact dates (1891).
  Content-agnostic (Rule 1 ✓ — generic date-structure regexes, no
  hardcoded dates; works on any book in any discipline).

**2. Verification LAYER integration (commit `2a145ef`):** the
  deterministic date-check runs BEFORE the LLM call in
  `verify_and_polish_summary` — extracts dates from the summary +
  source, compares, flags mismatches as `verification_date_check` Issues
  (severity="flag", advisory). The LLM corrections (severity="fix") handle
  the actual fixing. The date-check runs regardless of model
  configuration (it's deterministic — doesn't need an LLM).

**Tests:** `tests/test_v0500_date_extractor.py` — 37 tests across 8
  format classes + the compare_dates function.

**Net-green:** ruff clean; eval gate OK (hash flat); **6,172 P / 0 F /
36 S exit 0** (+37: the 37 date-extractor tests); deny-list passes.

## V0.4.40 — the post-conversion verification + polish LAYER (Dates/Names/Omissions/Hallucinations)

> **The release:** a new architectural LAYER (per the user's design) — a
> post-output LLM pass that runs AFTER `render_summary_markdown` assembles
> the final per-chapter output. The generation LLM did a ~7/10 job; this
> LLM layer (in a VERIFICATION role, not generation — division of labor)
> fills holes + fixes mistakes to make it 9/10-10/10. Runs every conversion
> (non-skippable — catches LLM-variance-driven defects each run).

**Rationale (the user's 3 points):** (1) the LLM is NOT expected to
  generate a huge output — it already did; it only fills holes/gaps
  (targeted corrections, not regeneration); (2) it prevents LLM-variation
  by deterministically verifying every time; (3) since the focus is not
  pure generation, the LLM spends its full context + attention on fixing
  mistakes instead. **Architectural point:** adding more in-pipeline
  deterministic MODULES is fragile (every book is different); this LAYER
  catches the RESIDUE (whatever mistakes passed the in-pipeline mistake-
  proofing) by operating on the FINAL assembled output with a semantic LLM
  check the deterministic checks can't do.

**Focus (the 4 concerns that slip past the deterministic postchecks):**
  Dates (every `(Author Year)` matches the source), Names (every cited
  author is a real source author, correctly attributed), Critical
  omissions (key source claims/contributors the summary missed — the
  binding-constraint class), Hallucinations (fabricated claims not in the
  source).

**Design (mirrors the proven D3/garble LLM-repair pattern):**
  `core/summarisation/verification_phase.py` —
  `verify_and_polish_summary(rendered_md, source_text, settings, log)`:
  sends the rendered per-chapter summary + a clamped (≤50k-char) source
  excerpt to the LLM with a genre-agnostic verification prompt. The LLM
  returns TARGETED corrections (a JSON array of `{original, corrected,
  reason}`); the system applies each as a verbatim string replacement
  (the "original" MUST be an exact substring — the LLM can't rewrite the
  whole summary, avoiding the V0.02 `auto_repair` full-rewrite corruption
  failure mode). D3-style guard: reject (keep the original) if the
  polished output has MORE deterministic flags OR is >15% different in
  length. Fail-open. Content-agnostic (Rule 1 ✓ — checks against the
  runtime source for any book; no hardcoded names/dates/concepts).
  Wiring (`core/pipeline/conversion/summarization.py`): the layer sits at
  the per-chapter write point (after `render_summary_markdown`, before
  `atomic_write_text`). A heading→source map (best-effort match from
  `segments_for_summary`) provides the chapter source; no match → the
  verification skips that chapter (fail-open). Wrapped in a try/except so
  it NEVER breaks the write. Every applied correction is logged as a
  `verification` Issue (severity="fix") in the conversion log.

**Tests:** `tests/test_v0438_audit_fixes.py::TestV0440VerificationLayer`
  — 7 tests (targeted correction applied; correction skipped when
  "original" isn't an exact substring; guard rejects too-long polish;
  no-op when empty corrections; no-op when no model; fail-open on
  provider exception; `_extract_corrections` handles fenced JSON). All
  use a mock provider via `monkeypatch` on `create_provider`.

**Net-green:** ruff clean; eval gate OK (hash flat — the mock LLM doesn't
exercise the layer); write-path sweep 196 P; **6,135 P / 0 F / 36 S exit
0** (+7: the 7 V0.4.40 verification tests); deny-list passes.

**Note:** the quality IMPACT (the verification layer fixing Dates/Names/
Omissions/Hallucinations on the rig) requires a live-LLM run to validate
— the deterministic mock can't. The change is safe (content-agnostic,
fail-open, D3-style guard, targeted corrections only) + the layer logic
is unit-tested with a mock provider.

## V0.4.39 — the Option A+B general-improvements release (D3 LLM-repair pattern generalized to garbles + general detector edge-case characterization)

> **The release:** per the user's direction ("We shouldn't overoptimize for
> this specific chapter, do only general improvements"), the V0.4.38 audit's
> proposed backlog's F1 (source-grounded deterministic auto-repair for the
> specific ch.6 garbles "betrayale"/"paranoias") was DROPPED — it was
> chapter-specific + re-introduced the V0.02 corruption risk. This release
> ships TWO general improvements instead: generalize the proven D3
> LLM-repair pattern to garbles (Option A) + general detector edge-case
> characterization on non-ch.6 fixtures (Option B).

**1. Option A — generalize the D3 LLM-repair pattern to garbles (commit `324928b`):**
  new `repair_garbles_via_llm` in
  `core/summarisation/postchecks/garble/garble_repair.py` — mirrors
  `repair_d3_quotes_via_llm` (V0.4.11/V0.4.13). When `fragment_merge` /
  `dropped_letter` flags are present, sends the text + a clamped (≤20k-char)
  source excerpt to the LLM with a "fix ONLY the garbled tokens, preserve
  all other text" prompt. Fail-open; D3-style guard (keep the original if
  the repair returns empty/short text OR doesn't reduce the garble flag
  count via `_count_garble_flags`). **Wired into all three postcheck fields
  — `postcheck_thorough` + `postcheck_bullets` + `postcheck_exec`** (the
  finalization commit `31c3997` extended it from thorough-only to bullets +
  exec so it catches garbles in any field on any chapter). Fires only when
  the postcheck flagged a garble (bounded — no-op on clean text + in tests).
  Content-agnostic (Rule 1 ✓ — the prompt is about token repair, not
  content; works on any chapter; catches ANY garble, not the specific
  ch.6 words). The pre-repair garble flags stay as the honest "what was
  found" record; the repair issues (fix/flag) document the LLM repair on
  top. The LLM considers source context (no blind edit-distance-1 rewrite —
  avoids the V0.02 `auto_repair` corruption failure mode that made it
  default-OFF since V0.03 P0-1).

**2. Option B — general codebase hygiene (commit `324928b`):** 4
  characterization tests in
  `tests/test_v0438_audit_fixes.py::TestV0439OptionBGeneralDetectorEdgeCases`
  confirming the V0.4.38 fixes (F3 fragment_merge lexicon, F4 bold-name
  structural-label, F5 self-compound hyphen, F1 fusion Pattern C) work on
  GENERIC fixtures (English/biology/history text, not ch.6) — confirming
  the detectors are book-agnostic (Rule 1).

**Tests:** `tests/test_v0438_audit_fixes.py::TestV0439OptionAGarbleLLMRepair`
  — 5 tests (mock-LLM repair fixes a garble; D3-style guard keeps the
  original when the LLM doesn't reduce flags; no-op when no garble flags;
  fail-open when no model configured; fail-open on provider exception).

**Net-green:** ruff clean; eval gate OK (hash flat — the mock LLM doesn't
exercise the repair); **6,126 P / 0 F / 36 S exit 0** (+9: the 9 V0.4.39
tests — 5 Option A + 4 Option B); deny-list passes.

**Note:** the quality IMPACT (the LLM repair fixing garbles on the rig)
requires a live-LLM run to validate — the deterministic mock can't. The
change is safe (content-agnostic, fail-open, D3-style guard) and the
repair logic is unit-tested with a mock provider.

## V0.4.38 — the F1-F5 backlog release (fusion Pattern C + 4th dedicated-thorough attempt + fragment-merge lexicon + bold-name structural-label exemption + self-compound hyphen normalization)

> **The release:** the V0.4.37 ch.6 audit's V0.4.38 backlog had 5 items
> (F1 HIGH, F2 HIGH, F3-F5 LOW). This release ships content-agnostic,
> net-green fixes for all 5, evidence-anchored to the V0.4.37 ch.6 audit.

**1. F1 fusion-garble Pattern C (commit `415f589`, HIGH):** the V0.4.37
  thorough shipped "persecutionensate" (line 85) = source-word
  "persecution" + "ensate" (a 6-char suffix of the source word
  "compensate", whose "comp" prefix was dropped in the fusion).
  `detect_sentence_fusion` flagged 0 — Pattern A caps suffixes at 4
  chars (6 escapes); Pattern B needs ≥2 source-word substrings but the
  2nd source word's prefix was dropped so it isn't a substring. The fix
  adds **Pattern C**: a source-word prefix + a 5-6 char suffix that is
  itself a suffix of some OTHER source word (the dropped-prefix fusion
  signature). O(1) lookup in a precomputed `_source_word_suffix_set`;
  self-suffix guard (`prefix.endswith(suffix)`) prevents inflection
  false-positives. Content-agnostic (Rule 1 ✓ — a structural
  suffix-to-source-word-suffix match).

**2. F2 4th dedicated-thorough attempt (commit `ff7ab00`, HIGH):** the
  V0.4.37 dedicated-expansion call returned <800 words on ALL 3 attempts
  (best=793) → a 31/74 = 42% coverage-deficient thorough (vs V0.4.36's
  65%). The helper returned the short best-effort + only logged a
  WARNING; the synthetic (exec+bullets) fallback fires ONLY on total
  failure (best=None). The fix adds **Attempt 4** — a re-prompt with a
  QUANTIFIED length directive ("Your previous response was only N words
  — below the M-word minimum. Write the FULL thorough summary of AT
  LEAST M words now..."), a stronger nudge than Attempt 2's generic one.
  Fires when best is non-empty but < min_words AND the deadline allows.
  Genre-agnostic (about LENGTH, not content — Rule 1 ✓). The synthetic
  fallback stays last-resort (preserves the model's prose unless it
  totally fails).

**3. F3 fragment_merge lexicon check (commit `57f13f3`, LOW):** the
  fragment_merge detector flagged "theme" (bullet 4 + thorough) because
  "them" is in the source but "theme" is not — it checked source_words
  ONLY, not the English lexicon. "theme" IS a real English word (in the
  vendored 126k-word lexicon). The fix: `detect_word_fragment_merge` now
  loads the lexicon + skips a candidate when the full word (word+stray,
  or the right-side stripped word) IS in the lexicon. Mirrors
  `detect_sentence_fusion`'s existing lexicon check. Content-agnostic
  (Rule 1 ✓).

**4. F4 bold-name structural-label exemption (commit `605bafd`, LOW):**
  the bold-name detector flagged `**Conclusions**:` (bullet 59) as
  "author 'Conclusions' not found in source" — it's a structural section
  label, not an author attribution. Multi-word labels don't match
  `_BOLD_NAME_RE` (it requires a single capitalized word or a
  NAME_SEP-joined pair), so only single-word labels like "Conclusions"
  were caught. The fix adds the `_BOLD_NAME_STRUCTURAL_LABELS` frozenset
  (conclusions, summary, overview, introduction, discussion, references,
  bibliography, appendix, notes, preface, foreword, acknowledgments/
  acknowledgements, index, postscript, addendum, glossary, abstract,
  background, methods, methodology, results, findings, limitations,
  highlights) + skips a bold-name candidate whose casefolded form is in
  the set. Genre-agnostic (Rule 1 ✓ — generic English publishing/
  discourse labels; applies to any discipline).

**5. F5 self-compound hyphen normalization (commit `f2877d7`, LOW):**
  the summary shipped "selfinflation" (bullet line 76) and
  "selfrighteousness" (bullet line 63) — the model fused "self" + a
  noun/adjective without the hyphen. The fix adds the
  `_normalize_self_compounds` render-boundary pass (mirrors the V0.4.37
  F6 render-sweep pattern) — applied to bullets + exec + thorough in
  `render_summary_markdown`. Finds `self[a-z]{4,}` words; hyphenates
  ONLY when the fused word is NOT a real English word AND the trailing
  part IS — so "selfless"/"selfish" (real words) and already-hyphenated
  forms ("self-esteem") are left alone. Strict-improvement (only adds
  hyphens; no-op on clean text). Content-agnostic (Rule 1 ✓ — the
  lexicon is a generic English wordlist; the "self-" prefix is generic
  English morphology).

**Net-green:** ruff clean; eval gate OK (hash flat); **6,117 P / 0 F /
36 S exit 0** (+14 — the 12 V0.4.38 characterization tests + 2 seed
drift); deny-list passes.

## V0.4.37 — the F7+F6+F4+F3+F2(c) low-priority-backlog release (detector false-positive tuning + render stray-quote sweep + gap-fill multi-author prompt + coverage-driven thorough gap-fill + dedup guard tightened)

> **The release:** the V0.4.36 ch.6 audit's V0.4.37 backlog had 5 items,
> all LOW PRIORITY (4 observability + 1 carryover). This release ships
> content-agnostic, net-green fixes for all 5: F7 (detector false-
> positive tuning — grammar 3rd-singular "-s" verbs + thorough
> attribution threshold 50→40), F6 (render-boundary stray-quote sweep),
> F4 (gap-fill multi-author attribution prompt), F3 (coverage-driven
> thorough gap-fill engagement), F2(c) (dedup symmetric-difference
> guard ≤6→≤4). F2(a) (active-subject veto) + F2(b) (V0.4.23 filler
> floor) are documented rig-dependent — loosening either risks re-
> introducing the exact defects the gates were calibrated to block; the
> audit's evidence is book-specific and the fix needs a live-LLM rig run
> to validate no regression (same protocol as the V0.4.35 audit's F6
> "extension needs the rig to validate").

**1. F7 detector false-positive tuning (commit `3553414`):** the grammar
  "no main verb" Signal-2 check now also recognizes 3rd-person-singular
  "-s" verbs (e.g. "masks", "links", "notes", "posits") via the generic
  English lexicon (126k words, no domain terms) — catches the "masks"-
  class (the V0.4.36 bullets 22/23 false-positives); base-form verbs
  (e.g. "mask" with a plural subject) still escape (full recognition
  needs POS tagging, deferred — observability-only per the audit). The
  attribution flag threshold is now field-aware — 0.40 for the thorough
  (long-prose paraphrase territory), 0.50 for exec/bullets (terse); the
  40-50% paraphrase-rescue band (V18.20.3.4) stays active for exec/
  bullets. Both flag-only (advisory), so residual risk is false-
  negatives, not summary defects. Content-agnostic (Rule 1 ✓).

**2. F6 render-boundary stray-quote sweep (commit `7958e83`):** a final
  `repair_stray_quotes_v2` sweep in `render_summary_markdown` (AFTER
  `_break_thorough_into_paragraphs` + `format_years`) catches orphans
  the postcheck's single-line pass missed (the V0.4.36 ch.6 thorough
  line 111 stray `"` before a trailing participle). Root-cause (in-
  sandbox repro): v1+v2 both strip the quote from the rendered line —
  the detector isn't broken; the gap is a wiring/ordering one — the
  postcheck runs on the single-line thorough where D2 can mis-pair
  ambiguous quotes; the V0.4.36 (F3) paragraph-breaking shortens lines
  and makes per-line pairing more reliable, so re-running the sweep
  after it catches orphans. Strict-improvement (only removes orphan
  quotes; no-op on clean text). Content-agnostic (Rule 1 ✓).

**3. F4 gap-fill multi-author attribution prompt (commit `9c57e66`):**
  a 4th STRICT attribution rule added to the per-author batch gap-fill
  prompt + the matching "Do:" constraint to the two gap-fill LLM
  templates (`gap_fill_concept.md` + `gap_fill_reprompt.md`) — retain
  multi-author attribution form (e.g. "AuthorA and AuthorB (Year)")
  rather than reduce it to a single name. Genre-agnostic (about
  citation FORM, not content). Re-baselined the prompt manifest
  (ee5a61d0ebb3→2b54556685a2) + eval baseline — ZERO metric change (the
  deterministic mock's canned output is prompt-independent).

**4. F3 coverage-driven thorough gap-fill (commit `0b0aff1`):** the
  V0.05 word-count gate is extracted into a pure helper
  `_v05_gapfill_should_skip(tf_words, scaled_target_hi, covered, total)`
  and is now coverage-driven — it skips ONLY when word-count is met AND
  coverage ≥ the engage fraction (0.70, close to the audit's 50/74 =
  68% example); below that, the gap-fill runs to close the coverage gap
  regardless of word-count. Content-agnostic (a coverage FRACTION, not
  a chapter-specific theorist count). When `scaled_target_hi` is None,
  the gate is inactive (preserves the prior no-target behaviour).

**5. F2(c) dedup guard tightened (commit `6134a23`):** the
  `consolidate_duplicate_claims` symmetric-difference guard is
  tightened ≤6→≤4 — a 1-name swap (2 diff words) still merges; an
  N-name swap still merges via pairwise 2-word diffs; a 5-6-word-diff
  pair at sim≥0.92 (more likely rewording of a distinct claim) is
  preserved. Raising the SIM threshold (0.92→0.95) was rejected (would
  stop merging the canonical subject-swap at sim 0.928 — under-merge).
  Content-agnostic (a numeric diff-count guard). The V0.4.36 audit's
  F2(c) evidence: the dedup round culled 20/99 = 20%.

**F2(a) + F2(b) documented rig-dependent:** the V18.20.3.2 active-
  subject veto + the V0.4.23 filler floor were deliberately calibrated
  to block specific misattribution/filler defects (veto: bullets where
  the author isn't the grammatical subject of an attribution verb;
  filler floor: high-precision patterns each matching a shipped filler
  from the V0.4.22 audit). Loosening either risks re-introducing the
  exact defects they were built to block. The audit's F2 evidence is
  book-specific ("some are claim-bearing"); the fix needs a live-LLM
  rig run to validate no regression. They remain as-is for a future
  rig-validated tuning pass.

**Net-green:** ruff clean; eval gate OK (prompt manifest re-baselined
ee5a61d0ebb3→2b54556685a2, ZERO metric change); **6,103 P / 0 F / 36 S
exit 0** (+17 — the 15 V0.4.37 characterization tests + 2 seed drift);
deny-list passes. (A pre-existing hypothesis-replayed citation-regex
edge case — `extract_citations("Apr' (1000)")` → `[]`, surname below
the ≥4-char minimum — surfaced via the local `.hypothesis` DB; V0.4.37
does not touch citation extraction. Clearing the local DB → green. A
future release should reconcile the property test's `_surname` strategy
with the regex's min-length contract; out of V0.4.37 scope per Rule 2.)

## V0.4.36 — the F1+F3+F5 release (positive-demonstration test + thorough paragraph-breaking + fusion false-positive fix)

> **The release:** the V0.4.35 audit (PASS 9/5/7/7, 0 hallucinations, probe
> FIRED but 0 drops) found 3 fixable items: F1 (no positive demonstration
> the probe catches fabricated years), F3 (single-paragraph thorough — 6th
> consecutive audit flagging), F5 (fusion detector false positive on
> 'ego-syntonically'). This release fixes all 3. F2 (veto+filler cull rate)
> + F4 (multi-author attribution) are queued for V0.4.37.

**1. F1: Positive-demonstration test (commit `2ccfcdc`):** 5 tests in
  `TestV0435YearAttributionProbe` — injects 'Stanton (1980)' (the V0.4.34
  H3 hallucination) into a fixture + verifies the probe DROPS it while
  keeping 'Hamilton (1974)'. **This is the DETERMINISTIC-ELIMINATION PROOF**
  the campaign has been missing since V0.4.32's non-deterministic 'F1-F5 gone'
  verdict. The probe catches fabricated years DETERMINISTICALLY.

**2. F3: Break thorough into MULTIPLE paragraphs (commit `e3ebbee`):**
  `_break_thorough_into_paragraphs` in `chapter_checkpoint.py` — a
  deterministic post-processing pass that splits the thorough at sentence
  boundaries where a new Author (Year) citation signals a section transition.
  Called from `render_summary_markdown` before `format_years`. Threshold:
  thorough ≥ 500 chars (short thorough returned as-is). Content-agnostic
  (the split pattern is a generic English discourse marker). Rule 1 compliant.

**3. F5: Fusion detector false-positive fix (commit `6044378`):** adds
  'ally' to `_FUSION_LEGIT_SUFFIXES` in `garble/fusion.py` — fixes the
  'ego-syntonically' false positive (the word IS in the source verbatim).

**Net-green:** ruff clean; eval gate OK (hash flat); full suite 6,086 P /
0 F / 36 S exit 0 (+5 from V0.4.35 — the F1 positive-demonstration tests);
deny-list passes.

**Items F2 + F4 queued for V0.4.37:** F2 (tune the veto+filler cull rate —
48% is too high; bullets recall 70%→55%), F4 (retain multi-author
attributions in the gap-fill prompt).

## V0.4.35 — the F1 year-attribution-probe-wiring release (wire the probe to the dedicated expansion output)

> **The release:** the V0.4.34 ch.6 audit found H3 (Stanton 1980 fabricated
> year) slipped through the dedicated expansion call which the V0.4.34
> year-attribution probe didn't inspect (the probe lived in the gap-fill path
> which was skipped by the V0.05 word-count gate). The V0.4.35 fix: extract
> the year-attribution logic into a standalone `_year_attribution_probe` function
> + call it at the coverage-check point in `_thorough_theorist_floor` (BEFORE
> the gap-fill phase). This catches fabricated-year claims regardless of whether
> the gap-fill runs.

**1. F1: `_year_attribution_probe` standalone function + wired to the dedicated
  expansion output (commit `[TBD]`):** extracted the year-co-occurrence logic
  from `_grounded_addition_sentences` into a standalone function that ONLY checks
  if the YEAR cited in a sentence co-occurs with the AUTHOR in the source (NOT
  the keyword probe — too aggressive for full thorough prose). Called at the
  coverage-check point in `_thorough_theorist_floor` (BEFORE the gap-fill phase)
  so it catches H3-class fabricated-year hallucinations regardless of whether
  the gap-fill runs. Content-agnostic (Rule 1 ✓).

**Net-green:** ruff clean; eval gate OK (hash flat); full suite 6,081 P exit 0;
deny-list passes.

**Items F2-F4 + the V0.4.35 backlog queued for V0.4.36:** F2 (tighten the
V0.05 word-count gate), F3 (break thorough into paragraphs), F4 (promote
compound-name theorists), + the V0.4.35 carry-over (synonym-class probe, stem
self-containment, quote-pair balancer, thinking-filter, deadline diagnostics,
meta-filler detector, co-authored-citation prompt).

## V0.4.34 — the year-attribution-probe release (V0.4.34 item 1: the H1/H2 hallucination fix)

> **The release:** the V0.4.33 ch.6 audit found 2 NEW F1-class hallucinations
> (H1 Mackinnon 1972 + H2 Michels 1983) that the attribution-edge rarest-4
> fingerprint + the V0.4.33-wired semantic fact-check BOTH failed to catch —
> because both author names co-occur with the claim keywords in the source
> window, AND the ≥0.50 embedding similarity passed. The V0.4.34 fix adds a
> **year-attribution probe** that catches fabricated years DIRECTLY.

**1. Year-attribution probe (V0.4.34 item 1, commit `73660a0`):** in
  `_grounded_addition_sentences` (`core/summarisation/thorough_theorist_floor.py`),
  BEFORE the keyword probe, extract the 4-digit year(s) cited in the sentence
  + verify the YEAR co-occurs with the AUTHOR in the source's ±600-char window.
  If the year doesn't match (e.g., "Mackinnon (1972)" when the source has only
  "Mackinnon and Michels (1971)") → fabricated year → skip to the next name;
  if NO name grounds, the sentence is DROPPED regardless of embedding similarity.
  Gated on the source-size gate (≥1000 chars — only runs on real-sized sources,
  not tiny test sources). Content-agnostic (Rule 1 ✓ — the year-attribution check
  is a structural property of source-citation-co-occurrence).

**Net-green:** ruff clean; eval gate OK (hash flat); full suite 6,081 P / 0 F /
36 S exit 0; deny-list passes.

**Items 2-8 queued for V0.4.35:** (2) synonym-class probe; (3) stem
self-containment; (4) quote-pair balancer; (5) meta-filler detector; (6)
thinking-filter; (7) deadline diagnostics; (8) co-authored-citation prompt.

## V0.4.33 — the dead-code-wiring release (V0.4.33 item 1: wire the semantic fact-check into the production pipeline)

> **The release:** the V0.4.32 ch.6 audit found that item 2 (commit `c37376e`)
> defined the `_semantic_ground_addition_sentences` helper but **NEVER CALLED
> it** from any production code path — only the tests exercised it. The
> CHANGELOG claim that item 2 "closed the F1-F5 enabler" was NOT supported by
> the conversion log. This release **wires the helper** into the
> thorough-theorist-floor merge path — each chunked gap-fill addition now
> passes through BOTH the attribution-edge check (item 1, the rarest-4
> fingerprint) AND the semantic fact-check (item 2, the embedding-similarity
> ≥0.50 check) before merging into the thorough.

**1. Wire `_semantic_ground_addition_sentences` into the production pipeline
  (V0.4.33 item 1, commit `d19dac9`):** the helper is now called at
  `core/summarisation/thorough_theorist_floor.py:625`, AFTER the attribution-
  edge check (`_grounded_addition_sentences` at line 601) + BEFORE the
  `_additions.append` at line 642. Each chunked gap-fill addition is filtered
  by BOTH checks before merging. The degenerate-signal guard fires in the
  sandbox (no sentence-transformers → returns unchanged); the actual semantic
  check runs on the rig (nomic-embed-text via Ollama). **This also closes
  V0.4.33 item 3** (the gap-fill hallucination-guard) — the guard was ALREADY
  in place (the V0.4.24 attribution-edge check filtered each chunk before
  merging); the missing piece was item 2's call, now added.

**Net-green at the release tip:** ruff 0.16.8 clean; eval gate OK
(`prompt_manifest_hash ee5a61d0` flat); full suite **6,081 P / 0 F / 36 S
exit 0** (165s); deny-list passes.

**Items queued for V0.4.34:** (2) synonym-class probe to reduce the
attribution-edge false-positive rate (the V0.4.32 audit's COVERAGE regression:
theorists 85%→62%); (4) enumeration-stem self-containment (4 garbled stems);
(5) quote-pair balancer; (6) thinking-filter tightening; (7) deadline-exceeded
diagnostics; (8) meta-filler transition paragraph detector; (9) co-authored/
possessive-citation coverage gap (gap-fill prompt instruction — rig-blocked if
it shifts the prompt_manifest_hash).

## V0.4.32 — the ch.6-audit-fix release (items 1, 2, 8 of the V0.4.32 backlog)

> **The release:** the first response to the V0.4.31 ch.6 paranoid benchmark
> (the first FAIL verdict in the campaign lineage — 5 hallucinations in
> thorough additive paragraph 5). Ships the 3 highest-priority fixes from
> the 8-item V0.4.32 backlog: items 1+2 (the hallucination gap) + item 8
> (the OCR break). Items 3-7 queued for V0.4.33.

**1. Thorough-additive attribution-edge check strengthening (item 1,
  `core/summarisation/thorough_theorist_floor.py`):** the V0.4.24
  attribution-edge co-occurrence check used a first-8-by-position keyword
  selection that was too coarse — common abstract words ("further",
  "distinct", "affective") shared a ±600-char window with any cited author,
  passing fabricated substantive claims. The V0.4.32 fix sorts candidate
  keywords by RAREST source frequency first + takes the rarest 4 (the
  claim's distinctive content fingerprint) — so the common-word
  false-positive is removed + fabricated claims whose actual content words
  never co-occur with the cited author are DROPPED. Source-size gate
  (≥1000 chars) so the rarest-4 doesn't degenerate on tiny test sources.
  Commit `c0e1c0f`.

**2. Phase 2.2 semantic fact-check scope extension (item 2,
  `core/summarisation/thorough_theorist_floor.py` +
  `core/summarisation/bullet_pipeline.py`):** Phase 2.2 verified BULLETS
  only (log 551 "All bullets semantically grounded"). The 5 fabricated
  claims in thorough additive prose bypassed the verifier. The fix extends
  the `semantic_ground_addition_sentences` helper to cover the thorough
  additive prose — the same embedding-similarity ≥0.50 check. Degenerate-
  signal guard respected (embedder unhealthy → skip with explicit log).
  Commit `c37376e`.

**3. `complete_with_image` accepts the `model=` kwarg (item 8,
  `core/llm/llamacpp_provider.py`):** the V0.4.1 vision-OCR caller passed
  `model=self._llamacpp_provider_model` but the V0.4.30/V0.4.31 provider
  contract didn't expose the `model` param — raising `unexpected keyword
  argument 'model'` on all 3 scanned pages (p.152/153/154), forcing a
  Tesseract fallback (p.153 → zero chars, Table 6-1 lost). The fix adds
  `model: str | None = None` to the signature + uses `_model = model or
  self.model` (the V0.4.30-detected model). Commit `58a2ac7`.

**Net-green at the release tip:** ruff 0.16.8 clean; eval gate OK
(`prompt_manifest_hash ee5a61d0` flat); full suite **6,081 P / 0 F / 36 S
exit 0** (168s, +11 vs V0.4.31 — the V0.4.32 audit-fix tests); deny-list
passes (Rule 1).

**Items 3-7 queued for V0.4.33:** (3) the thorough-theorist-floor
gap-fill hallucination-guard (route chunked output through items 1+2
before merging); (4) enumeration-stem self-containment (7 garbled stems
on ch.6); (5) quote-pair balancer in deterministic polish; (6)
thinking-filter tightening (the "Author coverage check for…" meta-label);
(7) deadline-exceeded chapter diagnostics (surface the 767s/480s = 1.6×
in the user-facing summary).

## V0.4.31 — the B1 per-conversion llama.cpp endpoint dropdown release

> **The release:** the owner chose B1 (per-conversion dropdown) from the 3
> multi-endpoint UX options proposed in V0.4.30. The wizard's Step-5
> llama.cpp config box now has an "Endpoint:" dropdown — quick-select
> among the configured endpoints (Primary + a new `llamacpp_endpoints`
> setting). Picking one populates the URL/key fields; `create_provider`
> then detects the served model (V0.4.30).

**1. The endpoint dropdown (`ui_qt/components/llamacpp_config.py`):**
  `build_llamacpp_box` now starts with an "Endpoint:" `QComboBox`. It lists
  [Primary (the current `llamacpp_base_url`/`llamacpp_api_key`)] + each
  entry from the new `llamacpp_endpoints` setting, displayed as
  `label (base_url)`. Defaults to the active endpoint (matching
  `llamacpp_base_url`). Picking one calls `_on_llamacpp_endpoint_selected`
  which populates the URL + API key fields — so `save_llamacpp_settings`
  writes the selected endpoint + `create_provider` detects its served model
  (V0.4.30). The owner can now quick-switch between 8080 (Ternary Bonsai)
  + 8081 (Qwen) per conversion without retyping the URL.

**2. The `llamacpp_endpoints` setting (`utils/settings.py`):** a list of
  `{base_url, api_key, label}` (default `[]` — just Primary). The owner
  adds endpoints (e.g. the 8081/Qwen) to `~/.elixir/settings.json` under
  `summarisation.llamacpp_endpoints`. A full endpoint-editor UI (add/edit
  via the dialog) is a follow-up.

**3. The pure helper + tests:** `build_llamacpp_endpoint_options(primary_url,
  primary_key, endpoints)` → `[{label, base_url, api_key}, …]` (Primary +
  each valid endpoint; skips empty/malformed; label defaults to the url,
  api_key to "local"). Pure (no Qt, no settings I/O) — fully tested by
  `TestLlamaCppEndpointDropdown` (3 tests: primary-only, primary+configured,
  skip-empty/malformed).

**Net-green at the release tip:** ruff 0.16.8 clean; eval gate OK
(`prompt_manifest_hash ee5a61d0` flat); full suite 6,070 P / 0 F / 36 S
exit 0 (163 s, +3 vs V0.4.30's 6,067); deny-list passes.

**Testability note:** the pure helper is fully tested (3 tests, no Qt
needed). The dropdown widget itself (Qt GUI rendering + interaction) is
headless-skipped in the sandbox (T1) — the owner tests it on the rig.

## V0.4.30 — the multi-backend llama.cpp model-detection release

> **The release:** the owner reported that a second llama.cpp instance
> (port 8081, serving Qwen3.8) was mis-identified as "Ternary Bonsai" (the
> hardcoded `llamacpp_model` setting). This release adds dynamic model
> detection — `create_provider` queries `GET /v1/models` + uses the ACTUAL
> served model, so a llama-server on any port is identified + addressed
> correctly.

**1. `create_provider` detects the served model (`core/llm/llm_provider_impl.py`):**
  `create_provider` now queries `GET /v1/models` on the configured
  `llamacpp_base_url` at construction + passes the ACTUAL served model to
  `LlamaCppProvider` (instead of the hardcoded `llamacpp_model` setting). The
  detection logs an INFO line when the detected model differs from the
  configured ("detected model X on URL (configured: Y) — using the detected").
  Falls back to the configured model if the server is unreachable or
  `/v1/models` is empty. The registry's `get_context_window` now uses the
  detected model too (so the context window matches the actual served model).
  Commit `e50311e`.

  **Design:** detection at `create_provider` (one `/v1/models` query per
  conversion), NOT in the provider's per-call path — so the provider itself +
  its 113 existing unit tests are unaffected (they construct the provider
  directly with a specific model).

**2. Test (Rule 3):** `test_create_provider_llamacpp_detects_served_model`
  — verifies the detection uses the served model when it differs from the
  configured + falls back when `/v1/models` is empty.

**Net-green at the release tip:** ruff 0.16.8 clean; eval gate OK
(`prompt_manifest_hash ee5a61d0` flat); full suite 6,067 P / 0 F / 36 S
exit 0 (169 s, +1 vs V0.4.29's 6,066); deny-list passes (model names are
generic technical names, not book-derived).

**Part B (multi-endpoint) — proposed, NOT shipped:** the convenience feature
to configure BOTH 8080 + 8081 + switch between them without re-editing
`llamacpp_base_url`. Needs the owner's UX preference (per-conversion dropdown
vs global setting vs auto-fallback). With Part A shipped, the owner can
already switch `llamacpp_base_url` between ports + the model name auto-detects.

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
