"""V0.04: LlamaCppProvider — llama.cpp server (``llama-server``) backend.

The FIRST non-Ollama local backend wired end-to-end through the provider
stack. ``llama-server`` exposes an OpenAI-compatible HTTP API
(``/v1/chat/completions``), but it is NOT "just another OpenAI-compat
endpoint" — three behavioural differences drove a dedicated provider
instead of reusing ``OpenAICompatProvider``:

1. **Streaming-first generation.** A dense local model (e.g. a 27B
   ternary on a 12 GB card) generates 2-6 tok/s; a 12,288-token output
   budget can legitimately run 30-60 minutes. A non-streaming POST would
   hit even a generous client timeout while the server is still happily
   generating. This provider ALWAYS requests ``stream: true`` and
   accumulates server-sent events — the read timeout then applies PER
   CHUNK (a chunk arrives every few hundred ms), so a healthy long
   generation can never time out client-side. A non-streaming retry is
   kept as the fallback for proxies/browsers that mangle SSE.

2. **The request must FIT the negotiated window.** llama.cpp errors with
   ``the request exceeds the available context size`` when
   ``prompt_tokens + max_tokens > n_ctx`` — it does not silently clamp
   (build-dependent). The Ollama path relies on Ollama-side clamps and
   the app's ``ctx_clamp`` caps (which are Ollama-model-specific and do
   not apply here). This provider does its own budget math:
   ``max_tokens = min(requested, output_cap, n_ctx - prompt_est - margin)``
   and logs every clamp loudly.

3. **Local-lab semantics.** ``api_key`` defaults to ``"local"`` (sent as
   ``Authorization: Bearer local`` — ignored unless the server was
   started with ``--api-key``), the base URL defaults to
   ``http://127.0.0.1:8080/v1``, and model discovery is
   ``GET /v1/models`` (which lists the loaded model(s) — unlike Ollama
   there is no ``/api/tags`` registry).

Settings (single source: ``utils/settings.py`` defaults)::

    summarisation.llamacpp_base_url           http://127.0.0.1:8080/v1
    summarisation.llamacpp_api_key            local
    summarisation.llamacpp_model              Ternary-Bonsai-2-27B-Instruct-Vision
    summarisation.llamacpp_context_tokens     65536   (the 65k window)
    summarisation.llamacpp_max_output_tokens  12288   (the 12k output cap)

Usage (the user's rig config, verbatim)::

    provider = LlamaCppProvider(
        model="Ternary-Bonsai-2-27B-Instruct-Vision",
        base_url="http://127.0.0.1:8080/v1",
        api_key="local",
        max_tokens=12288,
        context_tokens=65536,
    )
    text = provider.complete("Summarize this document accurately …")

Connection verification (wizard "Test connection", preflight, CLI)::

    ok, msg = test_llamacpp_connection(base_url, api_key, model)
    models = list_llamacpp_models(base_url, api_key)   # GET /v1/models
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable

import requests as _requests

from core.llm.context_budget import count_tokens as _count_tokens
from core.llm.llm_provider_impl import LLMProvider
from core.llm.retry import retry_llm_call

logger = logging.getLogger(__name__)

# Conservative generation-rate floor (tok/s) used ONLY by the non-streaming
# fallback to derive a wall-clock timeout from the output budget. Dense 27B
# quants on mid-range 12 GB cards measure 2-6 tok/s; 2.0 is the pessimistic
# floor so the fallback never kills a healthy generation.
LLAMACPP_MIN_TOKENS_PER_SEC = 2.0

# Safety margin (tokens) subtracted alongside the prompt estimate when
# fitting ``max_tokens`` into the context window — covers the chat template
# overhead (BOS/EOS, role markers) that a chars/4 estimate under-counts.
LLAMACPP_FIT_MARGIN_TOKENS = 512

# Hard floors/ceilings for the fitted output budget.
LLAMACPP_MIN_OUTPUT_TOKENS = 256
# Ceiling for context tokens a client may declare (llama.cpp supports
# multi-million-token windows with RoPE scaling; 1M is a sane app-side cap
# that comfortably admits 65k/128k/200k-class models).
LLAMACPP_MAX_CONTEXT_TOKENS = 1_048_576


def _no_proxy_session() -> _requests.Session:
    """A session that bypasses HTTP(S)_PROXY env vars.

    Same rationale as ``utils.network.create_no_proxy_session``: a local
    llama.cpp server on 127.0.0.1 must never be routed through a corporate
    proxy. Kept local (not imported) to avoid a utils dependency from the
    provider layer — matches the module-boundary style of the other
    providers (they import only llm_provider_impl + retry).
    """
    s = _requests.Session()
    s.trust_env = False
    s.proxies = {"http": "", "https": ""}
    return s


def _pin_utf8(resp: _requests.Response) -> _requests.Response:
    """V0.05 (rig audit F1): pin ``resp.encoding`` to UTF-8 before ANY text
    access.

    GENERAL rule: llama-server sends ``Content-Type: text/event-stream`` (and
    some error bodies) WITHOUT a charset parameter. requests'
    ``get_encoding_from_headers`` falls back to **ISO-8859-1** for ``text/*``
    types without charset, so ``iter_lines(decode_unicode=True)`` / ``.text``
    then latin-1-decode the UTF-8 bytes — every typographic character
    (’ — “ …) ships as mojibake (â€™, â€”). SSE and JSON are UTF-8 by spec;
    pinning is the only correct decode. Applied at EVERY decode site in this
    provider (streaming, non-streaming, probe, model list, error bodies).
    """
    try:
        resp.encoding = "utf-8"
    except Exception:
        pass  # a read-only response object must never break the call
    return resp


def _extract_error_message(resp: _requests.Response) -> str:
    """llama.cpp errors are ``{"error": {"code": …, "message": …, "type": …}}``.

    Best-effort extraction with a plain-text fallback so callers always get
    something actionable.
    """
    try:
        _pin_utf8(resp)
        payload = resp.json()
        err = payload.get("error") or {}
        if isinstance(err, dict):
            msg = str(err.get("message") or "").strip()
            code = err.get("code") or resp.status_code
            typ = err.get("type") or ""
            return f"HTTP {code}{' (' + typ + ')' if typ else ''}: {msg}" if msg else f"HTTP {code}"
        if isinstance(err, str) and err.strip():
            return f"HTTP {resp.status_code}: {err.strip()}"
    except Exception:
        pass
    body = (resp.text or "").strip()[:200]
    return f"HTTP {resp.status_code}: {body}" if body else f"HTTP {resp.status_code}"  # noqa: E501 — legacy line, kept verbatim below the F1 pin above


class LlamaCppProvider(LLMProvider):
    """llama.cpp server provider (OpenAI-compatible, streaming-first)."""

    def __init__(
        self,
        model: str = "",
        base_url: str = "http://127.0.0.1:8080/v1",
        api_key: str = "local",
        temperature: float = 0.6,
        max_tokens: int = 12288,
        context_tokens: int = 65536,
        output_cap: int | None = None,
        timeout: int = 600,
        retries: int = 1,
        log_callback: Callable[[str, str], None] | None = None,
        label: str = "llama.cpp",
    ):
        super().__init__(
            model, temperature, max_tokens, context_tokens, timeout, retries, log_callback
        )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "local"
        self.label = label
        # The model's hard output ceiling (llamacpp_max_output_tokens). When
        # None, defaults to max_tokens. complete() never requests more than
        # this — a cloud-style 16k academic-rigor floor must not push a 12k
        # model into a 400 "exceeds the model output limit".
        self.output_cap = int(output_cap) if output_cap else int(max_tokens)
        self.context_tokens = max(1, min(int(context_tokens), LLAMACPP_MAX_CONTEXT_TOKENS))

    # ── URL / headers helpers ────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # llama.cpp only enforces the key when started with --api-key;
        # otherwise the header is ignored. Always send it so both modes work.
        headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    # ── Output-budget fitting (the general rule) ─────────────────────────

    def fit_max_tokens(self, requested: int, prompt: str) -> int:
        """Fit ``requested`` output tokens into the negotiated window.

        GENERAL RULE (not llama.cpp-specific): a provider that KNOWS its
        window must make the request fit, not assume server-side clamping.
        Three constraints, tightest wins:

            1. the model's output ceiling (``output_cap`` — e.g. 12288);
            2. the context window: n_ctx − estimated_prompt − margin;
            3. sanity floor (256) so a huge prompt still yields a usable
               (if doomed-to-truncate) call rather than a 0/4096-error.

        Every clamp is logged — silent shrinking is how "the model ignored
        my settings" mysteries are born.
        """
        cap = self.output_cap if self.output_cap > 0 else requested
        # V0.09 (P5): tokenizer-aware prompt estimate (tiktoken cl100k_base
        # via core.llm.context_budget) — replaces the len(prompt)//4 heuristic,
        # which over-counted repetitive text ~2x (240k chars of 'x' is ~30k
        # tokens, not 60k) and under-counted CJK. Same margin as before.
        _prompt_tokens = _count_tokens(prompt)
        ctx_budget = self.context_tokens - _prompt_tokens - LLAMACPP_FIT_MARGIN_TOKENS
        fitted = min(requested, cap, ctx_budget)
        # Sanity floor — applies ONLY when it protects a REDUCED request
        # (a huge prompt squeezed the budget below usable). A deliberately
        # tiny request (smoke-test probes ask for 1-3 tokens) must never be
        # inflated: max(fitted, 256) would turn a 3-token probe into 256.
        if fitted < LLAMACPP_MIN_OUTPUT_TOKENS and requested >= LLAMACPP_MIN_OUTPUT_TOKENS:
            fitted = LLAMACPP_MIN_OUTPUT_TOKENS
        if fitted != requested:
            why = []
            if fitted == cap and requested > cap:
                why.append(f"model output cap {cap}")
            if fitted == ctx_budget and requested > ctx_budget:
                why.append(
                    f"context fit (ctx={self.context_tokens}, "
                    f"~{_prompt_tokens} prompt tokens, {LLAMACPP_FIT_MARGIN_TOKENS} margin)"
                )
            self.log(
                f"    🔧 llama.cpp output budget {requested}→{fitted}"
                + (f" ({'; '.join(why)})" if why else ""),
                "INFO",
            )
        return fitted

    # ── The one true generation path: SSE streaming ──────────────────────

    def _parse_sse_line(self, line: str, chunks: list[str]) -> str | None:
        """Parse one SSE line. Returns finished text or None (still going).

        Mutates ``chunks`` in place. Handles: ``data: {json}`` content
        deltas, ``data: [DONE]`` termination, and mid-stream
        ``{"error": …}`` payloads (raised as ConnectionError so the retry
        policy classifies them retryable).
        """
        if not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data:
            return None
        if data == "[DONE]":
            return "".join(chunks)
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return None  # keep-alive comment / partial line — ignore
        if isinstance(payload.get("error"), dict):
            raise _requests.exceptions.ConnectionError(
                f"llama.cpp mid-stream error: {payload['error'].get('message', payload['error'])}"
            )
        if isinstance(payload.get("error"), str):
            raise _requests.exceptions.ConnectionError(
                f"llama.cpp mid-stream error: {payload['error']}"
            )
        choices = payload.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                chunks.append(content)
        return None

    def _chat_streaming(
        self,
        payload: dict,
        on_chunk: Callable[[str], None] | None,
        timeout: int | None = None,
    ) -> str:
        """POST /chat/completions with stream=True and accumulate deltas.

        The read timeout applies PER CHUNK: as long as the server emits a
        delta every few hundred ms, a 60-minute generation never times out.

        Phase 4.4: optional ``timeout`` override (used by ``smoke_test`` so
        the preflight probe's ``min(self.timeout, 60)`` cap actually reaches
        the socket — previously the computed cap was never forwarded and the
        call always used the full ``self.timeout``).
        """
        url = self._chat_url()
        sess = _no_proxy_session()
        try:
            with sess.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=timeout if timeout is not None else self.timeout,
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    raise _requests.exceptions.HTTPError(
                        _extract_error_message(resp), response=resp
                    )
                # V0.05 (rig audit F1): pin UTF-8 BEFORE the first decoded
                # line — see _pin_utf8. Without this, every SSE chunk
                # decodes as latin-1 on charset-less text/event-stream.
                _pin_utf8(resp)
                chunks: list[str] = []
                last_emit = 0.0
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    finished = self._parse_sse_line(raw_line, chunks)
                    if finished is not None:
                        return finished
                    # Progress callback at most every 0.5s — the wizard log
                    # shows the summary growing without flooding the UI.
                    if on_chunk and chunks and (time.monotonic() - last_emit) > 0.5:
                        last_emit = time.monotonic()
                        try:
                            on_chunk("".join(chunks))
                        except Exception:
                            pass  # a UI callback must never kill generation
                # Server closed the stream without [DONE] — the accumulated
                # text is still valid (some builds omit the sentinel).
                if chunks:
                    return "".join(chunks)
                raise _requests.exceptions.ConnectionError(
                    "llama.cpp closed the stream without content"
                )
        finally:
            sess.close()

    def _chat_nonstreaming(self, payload: dict) -> str:
        """Fallback: a single non-streaming POST with a budget-derived timeout.

        Used when SSE is unavailable (proxy interference). The timeout is
        derived from the output budget at a pessimistic generation rate, so
        a slow-but-healthy dense model is not killed mid-generation.
        """
        url = self._chat_url()
        payload = dict(payload)
        payload["stream"] = False
        budget = int(payload.get("max_tokens") or self.max_tokens)
        effective_timeout = max(
            self.timeout,
            int(math.ceil(budget / LLAMACPP_MIN_TOKENS_PER_SEC)) + 60,
        )
        sess = _no_proxy_session()
        try:
            resp = sess.post(url, headers=self._headers(), json=payload, timeout=effective_timeout)
            if resp.status_code != 200:
                raise _requests.exceptions.HTTPError(_extract_error_message(resp), response=resp)
            # V0.05 (rig audit F1): pin UTF-8 before the JSON/text decode.
            _pin_utf8(resp)
            text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
            if not text:
                raise _requests.exceptions.ConnectionError("empty response from llama.cpp model")
            return text
        finally:
            sess.close()

    # ── LLMProvider interface ────────────────────────────────────────────

    def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str | None:
        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = self.fit_max_tokens(max_tokens or self.max_tokens, prompt)

        payload: dict = {
            "model": _model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _max_tok,
            "temperature": _temp,
            "stream": True,
        }
        # llama-server supports the OpenAI JSON-mode request (the prompt must
        # mention JSON, which structured_io's instruction guarantees).
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call() -> str:
            self.log(
                f"    🦙 {self.label} ({_model}) t={_temp:.2f} max={_max_tok} streaming…",
                "INFO",
            )
            try:
                return self._chat_streaming(payload, None)
            except _requests.exceptions.HTTPError as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 400 and "context" in str(e).lower():
                    # "the request exceeds the available context size" —
                    # the server's n_ctx is SMALLER than the configured
                    # window. Actionable message instead of a raw 400.
                    self.log(
                        f"    🚫 llama.cpp: request exceeds the server's context "
                        f"(configured ctx={self.context_tokens}). Start llama-server "
                        f"with a larger -c flag or lower the model context setting.",
                        "ERROR",
                    )
                raise
            except (_requests.exceptions.ConnectionError, _requests.exceptions.Timeout):
                # SSE path failed at the transport level (proxy mangling,
                # early reset). One non-streaming attempt with a
                # budget-derived timeout before the retry policy takes over.
                self.log(
                    "    ⚠️ llama.cpp streaming transport failed — retrying non-streaming",
                    "WARNING",
                )
                return self._chat_nonstreaming(payload)

        try:
            return _do_one_call()
        except Exception as e:
            self.log(f"    ⚠️ {self.label} call failed: {e}", "WARNING")
            return None

    # V0.4.1: vision capability for OCR — provider-agnostic, no hardcoded
    # model names. The probe checks llama-server's loaded model for a
    # vision adapter by looking at the /v1/models endpoint's model info
    # or by sending a minimal image+prompt test. Content-agnostic.

    def supports_vision(self) -> bool:
        """Check if the llama-server model supports image input.

        Content-agnostic: attempts a minimal vision call (a tiny 1x1
        pixel image + a 1-token prompt). If the server returns a 200
        response, the model has vision. If it returns a 400 error
        mentioning "image" or "vision", it doesn't. This is a LIVE
        capability probe, not a name-keyed check.
        """
        try:
            import base64 as _b64

            # A 1x1 transparent PNG (minimal valid image)
            _tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            b64 = _b64.b64encode(_tiny_png).decode("utf-8")
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hi"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 1,
                "temperature": 0,
                "stream": False,
            }
            url = self._chat_url()
            sess = _no_proxy_session()
            try:
                resp = sess.post(url, headers=self._headers(), json=payload, timeout=15)
                if resp.status_code == 200:
                    return True
                # A 400 error mentioning "image" or "vision" means the
                # model can't process images — not a vision model.
                err = resp.text.lower()
                if resp.status_code == 400 and (
                    "image" in err or "vision" in err or "multimodal" in err
                ):
                    return False
                # Other errors (server not running, model not loaded) →
                # fail-safe: return False
                return False
            finally:
                sess.close()
        except Exception:
            return False

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        """Send a prompt + image to llama-server (OpenAI-compatible
        multimodal format) and return the text response.

        Uses the /v1/chat/completions endpoint with a content array
        containing both a text part and an image_url part (base64 data URL).
        Content-agnostic — works with any vision-capable model on
        llama-server.
        """
        import base64 as _b64

        b64_image = _b64.b64encode(image_bytes).decode("utf-8")
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or 4096
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                        },
                    ],
                }
            ],
            "max_tokens": _max_tok,
            "temperature": _temp,
            "stream": False,
        }
        try:
            # Use non-streaming for OCR (simpler, the response is short)
            return self._chat_nonstreaming(payload)
        except Exception as e:
            self.log(f"    ⚠️ llama.cpp vision call failed: {e}", "WARNING")
            return None

    def complete_streaming(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str | None:
        """Streaming with progress callbacks (same path as complete())."""
        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = self.fit_max_tokens(max_tokens or self.max_tokens, prompt)
        payload: dict = {
            "model": _model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _max_tok,
            "temperature": _temp,
            "stream": True,
        }
        self.log(f"    🦙 {self.label} ({_model}) t={_temp:.2f} streaming…", "INFO")

        # Phase 4.4 (LLM-call hardening audit): the streaming-with-callback
        # path previously made ONE streaming attempt + ONE non-streaming
        # fallback with no classified retry — complete() had @retry_llm_call
        # but this sibling did not, so a transient ConnectionError here
        # returned None where complete() would have backed off and retried.
        # The combined attempt (streaming → non-streaming fallback) is now
        # wrapped in the SAME decorator as complete(): retryable transport
        # errors (ConnectionError / 429 / 5xx) back off with jitter and
        # retry; non-retryable ones (404 model not served, 400 context
        # overflow) surface immediately. With retries=0 (max_attempts=1)
        # the behavior is identical to the previous single-shot code.
        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call() -> str:
            try:
                return self._chat_streaming(payload, on_chunk)
            except Exception as e:
                self.log(
                    f"    ⚠️ {self.label} streaming failed ({e}) — non-streaming retry",
                    "WARNING",
                )
                return self._chat_nonstreaming(payload)

        try:
            return _do_one_call()
        except Exception as e:
            self.log(f"    ⚠️ {self.label} call failed: {e}", "WARNING")
            return None

    # ── Introspection / smoke test ───────────────────────────────────────

    def list_models(self, timeout: int = 10) -> list[str]:
        """GET /v1/models — the loaded model id(s) on this server."""
        return list_llamacpp_models(self.base_url, self.api_key, timeout=timeout)

    def smoke_test(self, prompt: str = "hello", timeout: int | None = None) -> bool:
        """Probe the server + model with a tiny request (never raises).

        Mirrors ``OllamaProvider.smoke_test``: catches server-down
        (ConnectionError), auth mismatch (401/403 — llama.cpp started with
        --api-key), model mismatch (404), and loaded-but-empty responses.
        """
        _to = timeout if timeout is not None else min(self.timeout, 60)
        try:
            text = self._chat_streaming(
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1,
                    "temperature": 0.0,
                    "stream": True,
                },
                None,
                # Phase 4.4: forward the capped probe timeout — the computed
                # ``_to`` was previously never used (dead variable), so a
                # cold model load could stall preflight for the FULL
                # provider timeout (e.g. 600s) instead of the intended 60s.
                timeout=_to,
            )
            self.log(
                f"    ✅ {self.label} smoke-test OK: '{self.model}' responded ({len(text)} chars)",
                "DEBUG",
            )
            return True
        except _requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (401, 403):
                self.log(
                    f"    🚫 {self.label} smoke-test FAILED: auth rejected ({e}). "
                    f"llama-server was started with --api-key — set the matching "
                    f"key in the llama.cpp backend settings.",
                    "ERROR",
                )
            elif status == 404:
                self.log(
                    f"    🚫 {self.label} smoke-test FAILED: model '{self.model}' "
                    f"not served by this server ({e}). Check the Model name field "
                    f"against `GET {self.base_url}/models`.",
                    "ERROR",
                )
            else:
                self.log(
                    f"    🚫 {self.label} smoke-test FAILED: {e}",
                    "ERROR",
                )
            return False
        except _requests.exceptions.ConnectionError as e:
            self.log(
                f"    🚫 {self.label} smoke-test FAILED: cannot reach llama.cpp at "
                f"{self.base_url} ({e}). Is `llama-server` running on this port?",
                "ERROR",
            )
            return False
        except Exception as e:
            self.log(
                f"    🚫 {self.label} smoke-test FAILED: {type(e).__name__}: {e}",
                "ERROR",
            )
            return False


# ── Module-level helpers (wizard / settings dialog / CLI use) ─────────────


def list_llamacpp_models(
    base_url: str = "http://127.0.0.1:8080/v1",
    api_key: str = "local",
    timeout: int = 10,
) -> list[str]:
    """GET ``{base_url}/models`` → the served model ids.

    llama.cpp returns the OpenAI shape ``{"data": [{"id": …}, …]}`` listing
    the loaded model(s). Never raises — returns ``[]`` on any failure
    (callers seed the UI from the configured model name instead).
    """
    url = f"{base_url.rstrip('/')}/models"
    sess = _no_proxy_session()
    try:
        resp = sess.get(
            url,
            headers={"Authorization": f"Bearer {api_key or 'local'}"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.debug("list_llamacpp_models: %s", _extract_error_message(resp))
            return []
        # V0.05 (rig audit F1): pin UTF-8 before the JSON decode.
        _pin_utf8(resp)
        data = resp.json().get("data", []) or []
        return [m.get("id", "") for m in data if m.get("id")]
    except Exception as e:
        logger.debug("list_llamacpp_models: %s: %s", type(e).__name__, e)
        return []
    finally:
        sess.close()


def test_llamacpp_connection(
    base_url: str = "http://127.0.0.1:8080/v1",
    api_key: str = "local",
    model: str = "",
) -> tuple[bool, str]:
    """End-to-end connectivity probe for the wizard's Test-connection button.

    Two stages with distinct messages:

      1. ``GET /v1/models`` — is a llama.cpp-shaped server alive HERE?
      2. a 1-token chat completion — is the MODEL loadable and generating?

    Returns ``(ok, human_message)`` — never raises. Mirrors
    ``core.llm.cloud_client.test_cloud_connection``'s contract.
    """
    base = (base_url or "").strip() or "http://127.0.0.1:8080/v1"

    # Stage 1 — server reachability + model listing.
    models = list_llamacpp_models(base, api_key, timeout=10)
    if not models:
        # Distinguish "server down" from "200 but empty list".
        sess = _no_proxy_session()
        try:
            resp = sess.get(
                f"{base.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key or 'local'}"},
                timeout=10,
            )
            if resp.status_code in (401, 403):
                return False, f"server reachable but rejected the API key (HTTP {resp.status_code})"
            if resp.status_code == 404:
                return False, "server reachable but /v1/models is missing — is this llama-server?"
            return False, "server reachable but returned no models"
        except _requests.exceptions.ConnectionError:
            return False, f"cannot reach {base} — is llama-server running?"
        except Exception as e:
            return False, f"connection failed: {type(e).__name__}: {e}"
        finally:
            sess.close()

    # Stage 2 — tiny generation through the real provider path.
    probe_model = model or models[0]
    logs: list[str] = []
    probe = LlamaCppProvider(
        model=probe_model,
        base_url=base,
        api_key=api_key,
        timeout=60,
        log_callback=lambda msg, level="INFO": logs.append(f"{level}: {msg}"),
    )
    ok = probe.smoke_test(timeout=60, prompt="hi")
    if ok:
        extra = f" (served: {', '.join(models[:3])})" if models else ""
        return True, f"llama.cpp OK — '{probe_model}' responded{extra}"
    # smoke_test logged its detailed reason into `logs` — surface the last
    # one so the wizard label shows WHY (auth / model mismatch / empty).
    detail = ""
    for line in reversed(logs):
        if line.startswith("ERROR:"):
            detail = " — " + line.split(":", 1)[1].strip()
            break
    return (
        False,
        f"server up (models: {', '.join(models[:3])}) but model "
        f"'{probe_model}' failed to respond{detail}",
    )
