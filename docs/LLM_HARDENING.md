# LLM-Call Hardening Audit — Phase 4.4 (V0.12 roadmap)

**Scope.** Every provider path reachable from `create_provider` (`core/llm/llm_provider_impl.py:165`):
`ollama`, `llamacpp`, `openrouter` / `openai` / `openai_compatible` (one class), `freellmapi`
(factory class **and** the inline dispatcher path), `claude` — plus the adjacent LLM-call
surfaces that share the same guarantees (`async_provider`, `cloud_client` preflight, the
summarizer's `llm_dispatcher` leaf functions, the fast-model paths).

**Method.** Source audit of every HTTP call site in `core/llm/` + `core/summarisation/`
(AST scan for `post/get/request` calls lacking a `timeout` kwarg, plus manual review of
every retry loop), cross-referenced with the existing suites
(`tests/test_retry.py`, `tests/test_p2_llm_*`, `tests/test_structured_io.py`,
`tests/test_v011_audit_fixes.py`, `tests/test_v18_15_6_timeout.py`), and pinned by the new
evidence suite **`tests/test_p4_llm_hardening.py`** (36 tests) which asserts — per provider,
at the mocked HTTP boundary — that the timeout actually reaches the transport and that
retry classification behaves (ConnectionError retried with a recorded backoff sleep;
404 never retried).

**The five guarantees audited** (roadmap task 4.4):

| # | Guarantee | Canonical implementation |
|---|-----------|--------------------------|
| a | Explicit timeout on every HTTP call | per-call `timeout=` kwarg (or client-level for httpx) |
| b | Retry w/ exponential backoff + jitter, retryable/non-retryable classification | `core/llm/retry.py` — `@retry_llm_call` (tenacity `wait_exponential_jitter`, 2 s → 30 s ± 2 s; linear 2-attempt fallback when tenacity is absent) + `classify_ollama_exception` (`retry.py:257`) |
| c | Non-retryable handling: 404 model-not-found, OOM context-halving, timeout-stall | `ModelNotFound404Error` (`core/llm/model_errors.py`, re-exported `retry.py:127`), `retry_with_oom_context_halving` (`retry.py:358`), `OllamaTimeoutError` (`retry.py:170`) |
| d | Response validation (empty-response retry; JSON/XML parse) | per-provider empty→`ConnectionError` (retryable); `core/llm/structured_io.py` schema validation; `core/summarisation/response_parser.py` universal parser |
| e | Lenient JSON repair (V0.11) | `response_parser._repair_llm_json` (`response_parser.py:210`): `\'` escapes, smart quotes, trailing commas; **now also** `structured_io._lenient_json_repair` (`structured_io.py:261`, Phase 4.4) |

---

## 1. Provider × guarantee matrix

Legend: ✅ guaranteed (evidence cited) · 🟡 guaranteed with a documented nuance ·
🔧 gap found in this audit → fixed (see §3).

### ollama — `core/llm/ollama_provider.py` (factory: `llm_provider_impl.py:186`, timeout 300 s)

| Guarantee | Evidence (file:line) | Tests |
|---|---|---|
| (a) timeout | `ollama_provider.py:545` (`complete`), `:773` (`complete_streaming`), `:123` (smoke-test, capped `min(timeout,60)`), `:404` (`/api/ps` VRAM probe, 5 s); all through `safe_ollama_request` (`utils/network.py:126`, default 300 s) | `test_p4_llm_hardening.py::TestOllamaProviderHardening::test_timeout_reaches_http_layer` |
| (b) classified retry | `ollama_provider.py:533` `@retry_llm_call(max_attempts=self.retries+1)` wrapping `_do_one_call`; backoff+jitter via `retry.py:444/466`; classifier `retry.py:257` (ConnectionError/429/5xx retryable; 404/401/403/400, Timeout, OOM, programming errors non-retryable) | `test_retry.py` (49 tests: `TestRetryThenSucceed`, `TestJitter`, `TestGracefulDegradation`…); `test_p4_llm_hardening.py::test_connection_error_retried_with_backoff_then_succeeds` |
| (c) non-retryable | 404 → `ModelNotFound404Error` (`:546-558`) → actionable `ollama pull` log + installed-model list, returns None (`:668-687`); OOM (500 + "out of memory") → `OllamaOOMError` (`:559-569`) → `retry_with_oom_context_halving` halves `num_ctx` once, min 8192 (`:662-667`, `retry.py:358`); Timeout → `OllamaTimeoutError` (`:571-576`, V18.2.19 stall rule; IQ2_S exemption `retry.py:307-319`) | `test_p4_llm_hardening.py::test_http_404_model_not_found_not_retried`, `test_oom_halves_num_ctx_and_retries_once`, `test_timeout_returns_none_without_retry`; `test_v18_15_6_timeout.py` (22 tests) |
| (d) response validation | empty response → `ConnectionError` (retryable) `:650-653`; JSON body parse + truncation observability (`done_reason=length` WARNING + ContextVar, `:612-649`); streaming fallback: any streaming failure → `complete()` (`:804`), empty → non-streaming | `test_p4_llm_hardening.py::test_empty_response_is_retryable`; `test_ollama_provider_smoke.py` (22 tests) |
| (e) lenient JSON repair | via the caller's parse path — `structured_io.validate_summary_json` (see §2) and `response_parser.parse_response` (`response_parser.py:447`) | §2 below |

`complete_streaming` note: no decorator of its own — by design it **falls back to
`complete()`** (`:804`), which carries the full retry + OOM-halving. When `on_chunk is
None` it delegates directly to `complete()` (`:725-726`) — the transcribe feature
(`core/transcribe/transcribe_service.py:257`) uses exactly that safe route.

### llamacpp — `core/llm/llamacpp_provider.py` (factory: `llm_provider_impl.py:215`, timeout from `local.http_timeout_sec`, default 600 s)

| Guarantee | Evidence | Tests |
|---|---|---|
| (a) timeout | streaming: `_chat_streaming` `:279`, POST `timeout=…` `:302` (**🔧 fixed** — the smoke-test cap was previously never forwarded, see §3.3); non-streaming fallback: budget-derived `timeout=effective_timeout` `:339-356` (`max(self.timeout, ceil(max_tokens/2 tok/s)+60)` so a slow-but-healthy 27B is never killed); model list `:555` (10 s); connection probe `:588` (10 s + 60 s) | `test_p4_llm_hardening.py::TestLlamaCppProviderHardening::test_streaming_timeout_reaches_http_layer`, `test_nonstreaming_fallback_timeout_is_budget_derived`, `test_smoke_test_timeout_cap_reaches_http_layer` |
| (b) classified retry | `complete()`: `@retry_llm_call` `:394` around streaming + non-streaming fallback (`:394-423`); mid-stream `{"error": …}` payloads → `ConnectionError` (retryable) `:263-270`; **🔧 fixed** `complete_streaming()` now carries the same decorator (`:463`, was a single unclassified shot, §3.1) | `test_p2_llm_llamacpp.py` (58 tests: `TestCompleteErrorRouting`, `TestCompleteStreaming`, `TestChatStreamingEdges`…); `test_p4_llm_hardening.py::test_connection_error_retried_with_backoff_then_succeeds`, `test_complete_streaming_connection_error_retried_after_hardening` |
| (c) non-retryable | 404 (model not served) → `HTTPError(response=…)` `:305-308` → classifier non-retryable → None with actionable smoke-test message (`:524-530`); 400 "request exceeds the available context size" → actionable `-c` hint, no retry (`:396-412`); 401/403 auth → actionable `--api-key` hint (`:517-523`) | `test_p4_llm_hardening.py::test_http_404_not_retried`, `test_context_400_actionable_message_no_retry`, `test_complete_streaming_404_not_retried`; `test_p2_llm_llamacpp.py::TestSmokeTest` |
| (d) response validation | UTF-8 pinned before every decode (`_pin_utf8` `:110-127`, rig audit F1 — charset-less `text/event-stream` otherwise latin-1 mojibakes); `[DONE]`-less empty streams → `ConnectionError` (retryable) `:329-335`; empty non-streaming body → `ConnectionError` `:362-363`; shape-safe `choices[0].message.content` via `extract_openai_content` (`utils/network.py:98`) | `test_p2_llm_llamacpp.py::TestChatNonStreaming`, `TestParseSseLine`; `test_v004_llamacpp.py` (localhost mock server) |
| (e) lenient JSON repair | `json_mode=True` maps to `response_format={"type":"json_object"}` (`:391-392`); the response is validated/repaired by the caller's structured_io / response_parser path | §2 |

### openai-compat — `core/llm/openai_compat_provider.py` (serves **openrouter / openai / openai_compatible**: factory `llm_provider_impl.py:249`, timeout 300 s)

| Guarantee | Evidence | Tests |
|---|---|---|
| (a) timeout | `complete()` POST `timeout=self.timeout` `:92`; Batch API: upload `:230-237` (30 s), batch create `:252` (30 s), poll `:266-270` (30 s), download `:286` (60 s) | `test_p2_llm_openai_compat.py::TestComplete`; `test_p4_llm_hardening.py::TestOpenAICompatHardening::test_timeout_reaches_http_layer` |
| (b) classified retry | `complete()`: `@retry_llm_call` `:86-99` (429/5xx/ConnectionError retried; 400/401/403/404 propagate immediately → outer except → None, preserving the pre-V18.2.21 contract). 🟡 Batch API: no decorator — by design; the poll loop (`:264-282`) is itself a bounded retry and the whole path fails soft to the parallel mode (`batch_complete` `:146-150`, `_batch_api_complete` returns None on ANY failure `:311-313`) | `test_p2_llm_openai_compat.py::test_retryable_error_retried_then_success`; `test_p4_llm_hardening.py::test_connection_error_retried_with_backoff_then_succeeds` |
| (c) non-retryable | `resp.raise_for_status()` `:93` → classifier routes 401/403/404/400 to immediate None (`:103-108`); 401 surfaces an actionable message at the dispatcher level (below) | `test_p4_llm_hardening.py::test_http_404_not_retried` |
| (d) response validation | empty content → `ConnectionError` (retryable) `:94-98`; shape errors (KeyError/IndexError on error payloads) are non-retryable programming-class → None | `test_p2_llm_openai_compat.py::test_empty_response_returns_none_after_retry`, `test_malformed_json_returns_none`; `test_p4_llm_hardening.py::test_empty_response_is_retryable` |
| (e) lenient JSON repair | `response_format={"type":"json_object"}` when `json_mode=True` `:72-73`; validation/repair by the caller's structured_io / response_parser path | §2 |

### freellmapi — TWO paths

**Path 1 (factory):** `create_provider("freellmapi", …)` (`llm_provider_impl.py:263-276`)
returns an `OpenAICompatProvider` with `label="FreeLLMAPI"`, `base_url` from
`summarisation.freellmapi_url` (default `http://localhost:3001/v1`), keyring-backed key
(`summarisation.freellmapi_key`), **timeout 300 s** (`:272`). Every guarantee therefore
inherits the openai-compat row above verbatim.
Evidence: `test_p2_llm_providers.py::TestCreateProviderFactory::test_freellmapi_provider`;
`test_p4_llm_hardening.py::TestOpenAICompatHardening::test_freellmapi_factory_wires_class_timeout_and_label`.

**Path 2 (inline dispatcher):** the Summarizer's `_call_cloud` ladder dispatches
freellmapi through `llm_dispatcher.call_openai_compat` (`llm_dispatcher.py:435`, the 🔌
icon branch `:478`):

| Guarantee | Evidence | Tests |
|---|---|---|
| (a) timeout | pooled-session POST `timeout=timeout` `:494` (`session_for_url` picks no-proxy for localhost / proxy-trusting for remote, `utils/network.py:72`) | `test_p4_llm_hardening.py::TestDispatcherOpenAICompatHardening::test_timeout_reaches_pooled_session` |
| (b) classified retry | `@retry_llm_call(max_attempts=retries+1)` `:480`; shape-safe `extract_openai_content` routes malformed bodies into the SAME empty-response retry path (`:496-501`) | `test_p4_llm_hardening.py::test_connection_error_retried_404_not`; `test_p2_sumtail_llm_dispatcher.py` |
| (c) non-retryable | `raise_for_status()` `:495` → 401/403/404/400 immediate None `:505-508` | ibid. |
| (d) response validation | empty → `ConnectionError` (retryable) `:497-500` | `test_p2_summarizer_llm_transport.py` (transport seam, 40+ tests) |
| (e) lenient JSON repair | caller-side (§2) | §2 |

### claude — `core/llm/claude_provider.py` (factory: `llm_provider_impl.py:277`, timeout 180 s)

| Guarantee | Evidence | Tests |
|---|---|---|
| (a) timeout | POST `timeout=self.timeout` `:83`; inline dispatcher path `llm_dispatcher.call_claude` POST `timeout=180` `:564` | `test_p4_llm_hardening.py::TestClaudeProviderHardening::test_timeout_reaches_http_layer` |
| (b) classified retry | `@retry_llm_call` `:77` (provider) and `llm_dispatcher.py:557` (inline path); the pre-V18.2.21 double-sleep 429 hack (5 s + 2 s) collapsed into the single exponential wait; 401 "invalid key" propagates immediately instead of being pointlessly retried | `test_p2_llm_providers.py::TestClaudeComplete::test_retryable_500_retried_then_success`; `test_p4_llm_hardening.py::test_connection_error_retried_with_backoff_then_succeeds` |
| (c) non-retryable | 401 → actionable "API key invalid or expired" (`:104-106`, dispatcher `:584-586`); 429 exhaustion → explicit log (`:107-108`); other statuses → body excerpt `:109-110` | `test_p4_llm_hardening.py::test_http_401_not_retried_actionable_log`; `test_p2_llm_providers.py::test_http_401_actionable_log` |
| (d) response validation | content-block list parsed defensively (`:86-93`); empty → `ConnectionError` (retryable) `:94-96` (dispatcher `:575-577`) | `test_p2_llm_providers.py::TestClaudeComplete` (12 tests); `test_p4_llm_hardening.py::test_empty…` (openai-compat analogue) |
| (e) lenient JSON repair | claude is in `supports_json_mode` (`structured_io.py:146-147`); repair is caller-side (§2) | §2 |

---

## 2. Response validation & the lenient-JSON repair ladder (structured_io + response_parser)

Production uses a **strict → repair → universal-fallback** ladder; the structured/JSON
provider mode itself is intentionally disabled (`core/summarisation/structured_llm.py:58`,
`_STRUCTURED_PATH_ENABLED = False` — SWOT A16 decision), so the ladder's entry point in
production is `response_parser.parse_response`, with `structured_io` as the opt-in
validated contract for the future path.

| Rung | Implementation | Behavior |
|---|---|---|
| 1. extract | `structured_io._extract_json` (`structured_io.py:310`) | fenced ```` ```json ```` blocks, preambles, trailing text, brace-walking with string/escape awareness; unbalanced (truncated) → None |
| 2. strict validate | `structured_io._validate_clean_json` (`:281`) | pydantic `SummarySchema.model_validate_json`; no-pydantic degrade → `_manual_validate` (`:354`, dict-shape check) |
| 3. **lenient repair (V0.11, now in structured_io too)** | `structured_io._lenient_json_repair` (`:261`) → delegates to `response_parser._repair_llm_json` (`response_parser.py:210`) | ONE pass, only after strict failure: `\'` escapes → `'`, smart quotes `“”` → `"`, trailing commas `,}` / `,]` removed. Can only upgrade None → validated dict. |
| 4. XML fallback | `complete_structured(fallback_parser=parse_response)` (`structured_io.py:400-416`); in production, `parse_response` directly | strict JSON (`response_parser.py:435`) → repair (`:447`) → claims salvage (`_salvage_json_claims` `:234`) → universal tag/plain-text parser (`_parse_universal` `:514`); an unrepairable claims blob is NEVER banked as thorough_summary (V0.11 BUG-PRIMARY-FORMAT guard) |

**Pre-existing tests:** `test_structured_io.py` (34 tests — extraction, validation,
never-raises, adapter fallback chain), `test_v011_audit_fixes.py`
(`TestRepairLlmJson`, `TestParseClaimsJsonBlob`, `TestLeftoverJsonGuard` — the rig-failure
shapes), `test_e2e_golden_path.py` (adapter integration).

**Phase 4.4 added** (`test_p4_llm_hardening.py::TestStructuredIoLenientRepair` +
`TestResponseParserLenientRepair`): trailing commas, fenced-```json```-with-trailing-commas,
Python-style `\'` escapes (the V0.10 rig failure), smart-quote delimiters, truncated JSON →
None (bare and fenced), valid JSON provably untouched (repair spy), the no-pydantic manual
path sharing the repair, `complete_structured` repairing **without** invoking the XML
fallback, and the production `parse_response` ladder end-to-end.

**Honest scope note.** The V0.11 repair covers `\'` escapes, smart quotes and trailing
commas. It deliberately does **not** rewrite single-quoted *delimiters* (`{'a': 'b'}`) —
those are not one of the three canonical malformations observed on the rig and remain a
fallback-parser concern (the universal parser salvages the content).

---

## 3. Gaps found & fixes applied

All three fixes are minimal and behavior-compatible; the full affected suites were re-run
green (§4). Production call paths keep identical behavior at today's settings
(`retries=1` / `retries=0` semantics preserved; the structured/JSON path is disabled in
production, so fix 3.2 cannot change any production output).

### 3.1 🔧 `LlamaCppProvider.complete_streaming` had no classified retry
**Was:** one streaming attempt + one non-streaming fallback, no `@retry_llm_call` — a
transient `ConnectionError` returned `None` where `complete()` (same class, same
transport) would back off and retry. Every other provider path already had the decorator.
**Fix:** `core/llm/llamacpp_provider.py:463` — the combined attempt (streaming →
non-streaming fallback) is wrapped in the same `@retry_llm_call(max_attempts=self.retries+1)`
as `complete()`. With `retries=0` behavior is byte-identical to the old single-shot code;
with `retries=1` retryable transport errors now back off with jitter and retry.
**Tests:** `test_complete_streaming_connection_error_retried_after_hardening` (3 HTTP
calls + 1 recorded backoff sleep vs the old 2-calls-then-None),
`test_complete_streaming_404_not_retried`; the pre-existing
`test_p2_llm_llamacpp.py::TestCompleteStreaming` (3 tests) still pass unchanged.

### 3.2 🔧 `structured_io.validate_summary_json` lacked the lenient-repair rung
**Was:** a fenced ```` ```json ```` block with a single trailing comma (or a `\'` escape,
or smart-quote delimiters) failed pydantic validation → `None` → the caller's XML
fallback had to salvage it, even though the V0.11 repair (one module over) fixes exactly
these three malformations. The roadmap task 4.4 explicitly pairs "response validation
(structured_io)" with "the V0.11 lenient-JSON repair".
**Fix:** `core/llm/structured_io.py:248-258` — after a strict failure, ONE lenient pass
(`_lenient_json_repair` `:261` → `response_parser._repair_llm_json`, lazily imported to
keep the module import-light; `response_parser` imports nothing from `core.llm`, so no
cycle) then re-validation via the shared `_validate_clean_json` (`:281`). Valid JSON
never enters the repair path (pinned by a spy test); truncated JSON still returns None.
**Tests:** 9 new tests in `TestStructuredIoLenientRepair` (all four malformation classes,
truncation safety, repair-spy, manual-path parity, adapter end-to-end).

### 3.3 🔧 `LlamaCppProvider.smoke_test` computed a probe-timeout cap it never sent
**Was:** `_to = min(self.timeout, 60)` (`llamacpp_provider.py:493`) was dead — the probe
called `_chat_streaming(...)` without it, so preflight always used the FULL provider
timeout (default 600 s from `local.http_timeout_sec`): a cold model load could stall the
wizard/preflight for 10 minutes, exactly what the docstring promises cannot happen.
(`OllamaProvider.smoke_test` forwards its cap correctly — `ollama_provider.py:123`.)
**Fix:** `_chat_streaming` gained an optional `timeout` parameter
(`llamacpp_provider.py:283`, applied at `:302`); `smoke_test` forwards `_to` (`:508`).
All existing `_chat_streaming` callers keep the previous `self.timeout` behavior.
**Tests:** `test_smoke_test_timeout_cap_reaches_http_layer` (60 s cap with a 600 s
provider; explicit `timeout=9` override also honored).

### Not gaps (verified, documented for the record)

- **`AsyncOllamaProvider`** (`core/llm/async_provider.py`): timeout is client-level
  (`httpx.AsyncClient(timeout=self.timeout)` `:184` — httpx applies it to every request;
  `client.post` at `:276` needs no per-call kwarg), retry is the classified
  `_async_retry` (`:93`, exponential + jitter, `classify_ollama_exception`, httpx→requests
  exception translation `:283-304`). Public API currently unused in production (vulture
  finding, Phase-1 audit) but fully hardened.
- **`cloud_client.test_cloud_connection`** (preflight probe): explicit `timeout` param
  (`cloud_client.py:59`, POST `:99`); granular 401/404/400 messages; never raises.
  Covered by `test_p2_llm_providers.py::TestTestCloudConnectionNetwork` (14 tests).
- **Batch API poll loop** (openai-compat): no decorator, but every call has an explicit
  timeout, the poll is bounded (60×10 s), and the whole path fails soft to parallel
  `complete()` — classified retry would be redundant there.
- **Ollama streaming path**: falls back to `complete()` (full retry + OOM halving);
  `on_chunk=None` goes straight to `complete()` (`ollama_provider.py:725-726`) — the
  transcribe feature uses that route.
- **`llm_dispatcher` leaf functions** (the Summarizer's inline transports):
  `_call_ollama_nonstreaming` (`:275`, `@retry_llm_call` `:353`, timeout `:360`,
  V18.2.19 timeout rule `:361-379`), `call_openai_compat` (`:435`), `call_claude`
  (`:514`), `call_fast_ollama` (`:713`, `@retry_llm_call(max_attempts=2)` `:758`,
  timeout 120 s `:761`), `call_via_llm_provider` (`:608` — delegates to the hardened
  providers, overrides `provider.timeout` `:656-657`, inline fallback for claude/openai).
  All 8 legacy ad-hoc retry loops named in `retry.py`'s docstring have been migrated
  (5 provider sites in V18.2.21, the 3 summarizer sites in V18.8 Phase 5.1/5.3); the AST
  scan found **zero** remaining `time.sleep(N*(attempt+1))` LLM retry loops.
- **`simplified_keypoints` fast path** uses `@retry_llm_call`
  (`core/summarisation/simplified_keypoints.py:242`).

---

## 4. Test evidence

| Suite | Tests | Status |
|---|---|---|
| **`tests/test_p4_llm_hardening.py`** (NEW — this audit) | **36** | all pass (1.1 s) |
| `tests/test_p2_llm_llamacpp.py` | 58 | pass (regression for fixes 3.1/3.3) |
| `tests/test_p2_llm_openai_compat.py` | 28 | pass |
| `tests/test_p2_llm_providers.py` | 50 | pass |
| `tests/test_structured_io.py` | 45 | pass (regression for fix 3.2) |
| `tests/test_structured_llm.py` | 6 | pass |
| `tests/test_retry.py` | 49 | pass |
| `tests/test_p2_summarizer_llm_transport.py` | 42 | pass |
| `tests/test_p2_sumtail_llm_dispatcher.py` (29) + `test_llm_dispatcher.py` (33) | 62 | pass |
| `tests/test_v004_llamacpp.py` (55), `test_v011_audit_fixes.py` (21), `test_v18_15_6_timeout.py` (22), `test_fast_llm.py` (12), `test_v1820412_c_llm_errors.py` (52), `test_v1820411_p3_llm_transport.py` (33), `test_ollama_provider_smoke.py` (22) | 217 | pass |

Combined LLM-surface run after the fixes: **593 passed, 0 failed** (17 files, incl. the
new suite) plus 79 in the e2e/summarizer-adjacent files — hermetic throughout (HTTP
boundaries mocked; the autouse raising-keyring stub from `tests/conftest.py` keeps
factory tests off the real OS keychain).

Hermeticity pattern of the new suite: fake `requests.Session`/`safe_ollama_request`/
`requests.post`/`session_for_url` boundaries that **record the `timeout` kwarg** (the
Phase-2 fakes recorded method/url/json but not the timeout — the one assertion this audit
needed); retry tests force `core.llm.retry._HAS_TENACITY = False` + a recording
`time.sleep` stub so the deterministic 2-attempt linear fallback runs identically with or
without tenacity (the tenacity-specific wait curve is covered by `test_retry.py`).

---

## 5. Residual risks / follow-ups (not blocking)

1. `OpenAICompatProvider._batch_api_complete` sleeps 10 s per poll tick with no jitter —
   acceptable for a single overnight batch job; revisit only if batch mode becomes
   multi-tenant.
2. `LlamaCppProvider.complete_streaming` retries re-emit `on_chunk` progress from the
   start of the retried attempt (the UI sees a progress restart, not corruption) — same
   UX as Ollama's streaming→non-streaming fallback.
3. `structured_io`'s repair does not handle single-quoted delimiters (see §2 scope note)
   — intentional; the universal parser owns that salvage.
