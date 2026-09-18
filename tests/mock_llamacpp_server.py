"""V0.04: an in-process mock of ``llama-server`` (llama.cpp's HTTP server).

Implements exactly the surface ``LlamaCppProvider`` touches, with the
FAITHFUL error shapes of the real server:

  GET  /health            → {"status": "ok"}
  GET  /v1/models         → OpenAI list shape (the loaded model ids)
  POST /v1/chat/completions
       • auth: when ``api_key`` is set (simulating ``--api-key``), a wrong
         or missing Bearer token → 401 + ``{"error": {…}}``.
       • model: when ``strict_model`` is set, an unserved model → 404 +
         the llama.cpp error shape.
       • context: ``est_prompt_tokens + max_tokens > n_ctx`` → 400 with
         the real message text ("the request exceeds the available context
         size …") so the provider's diagnostic path is exercised.
       • stream=true → SSE ``data: {delta}`` chunks + ``data: [DONE]``
         (one chunk per "token", capped at ``max_tokens``).
       • stream=false → a full OpenAI-shaped completion.
       • ``response_format: {"type": "json_object"}`` → valid JSON text.

Usage::

    from tests.mock_llamacpp_server import MockLlamaCppServer

    srv = MockLlamaCppServer(models=["Ternary-Bonsai-2-27B-Instruct-Vision"])
    srv.start()
    try:
        provider = LlamaCppProvider(base_url=srv.base_url, …)
        ...
    finally:
        srv.stop()
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MODEL = "Ternary-Bonsai-2-27B-Instruct-Vision"


def _error_body(code: int, message: str, err_type: str = "api_error") -> bytes:
    """The llama.cpp error shape: {"error": {"code", "message", "type"}}."""
    return json.dumps(
        {"error": {"code": code, "message": message, "type": err_type}}
    ).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    server_version = "llama.cpp-mock/1.0"

    # Populated by MockLlamaCppServer via closure in __init__.
    _cfg: dict = {}

    def log_message(self, *args):  # silence — tests don't want stderr noise
        pass

    # ── helpers ──────────────────────────────────────────────────────────

    def _send(self, status: int, body: bytes, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        required = self._cfg.get("api_key")
        if not required:
            return True  # llama-server without --api-key ignores the header
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {required}"

    # ── routes ──────────────────────────────────────────────────────────

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path in ("/health", "/v1/health"):
            self._send(200, b'{"status":"ok"}')
            return
        if path == "/v1/models":
            data = [{"id": m, "object": "model"} for m in self._cfg["models"]]
            self._send(200, json.dumps({"object": "list", "data": data}).encode())
            return
        self._send(404, _error_body(404, f"Unknown path: {path}", "api_error"))

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path != "/v1/chat/completions":
            self._send(404, _error_body(404, f"Unknown path: {path}", "api_error"))
            return
        if not self._authorized():
            self._send(401, _error_body(401, "Invalid API key", "api_error"))
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, _error_body(400, "Malformed request body", "invalid_request_error"))
            return

        model = payload.get("model", "")
        if self._cfg.get("strict_model") and model not in self._cfg["models"]:
            self._send(
                404,
                _error_body(404, f"model not found: {model}", "api_error"),
            )
            return

        messages = payload.get("messages") or []
        prompt = "".join(str(m.get("content", "")) for m in messages)
        max_tokens = int(payload.get("max_tokens") or 0)
        est_prompt_tokens = max(1, len(prompt) // 4)
        n_ctx = int(self._cfg.get("n_ctx", 65536))
        if est_prompt_tokens + max_tokens > n_ctx:
            self._send(
                400,
                _error_body(
                    400,
                    "the request exceeds the available context size. "
                    "Try increasing the context size or enable context shift",
                    "invalid_request_error",
                ),
            )
            return

        if payload.get("stream"):
            self._stream_response(payload, prompt, max_tokens)
            return

        content = self._build_content(payload, prompt)
        # Real llama.cpp stops generation at n_predict/max_tokens on the
        # non-streaming path too — cap the "generated" words likewise.
        if max_tokens > 0:
            words = content.split()
            content = " ".join(words[:max_tokens])
        body = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": est_prompt_tokens,
                "completion_tokens": len(content.split()),
                "total_tokens": est_prompt_tokens + len(content.split()),
            },
        }
        self._send(200, json.dumps(body).encode())

    # ── response building ────────────────────────────────────────────────

    def _build_content(self, payload: dict, prompt: str) -> str:
        if (payload.get("response_format") or {}).get("type") == "json_object":
            return json.dumps({"ok": True, "echo": prompt[:32], "model": payload.get("model", "")})
        custom = self._cfg.get("response_text")
        if custom:
            return custom
        return f"MOCK-LLAMACPP[{payload.get('model', '?')}]: {prompt[:48]}"

    def _stream_response(self, payload: dict, prompt: str, max_tokens: int):
        content = self._build_content(payload, prompt)
        # One SSE chunk per "token" (word), capped at max_tokens — models
        # stop generating at the output budget exactly like the real server.
        words = content.split()
        if max_tokens > 0:
            words = words[:max_tokens]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for w in words:
                chunk = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "model": payload.get("model", "?"),
                    "choices": [{"index": 0, "delta": {"content": w + " "}}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                delay = float(self._cfg.get("chunk_delay") or 0)
                if delay:
                    time.sleep(delay)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client hung up mid-stream — real servers see this too


class MockLlamaCppServer:
    """Start/stop wrapper around the ThreadingHTTPServer handler above."""

    def __init__(
        self,
        models: list[str] | None = None,
        api_key: str | None = None,
        n_ctx: int = 65536,
        strict_model: bool = False,
        response_text: str | None = None,
        chunk_delay: float = 0.0,
    ):
        self.models = models or [DEFAULT_MODEL]
        cfg = {
            "models": self.models,
            "api_key": api_key,
            "n_ctx": n_ctx,
            "strict_model": strict_model,
            "response_text": response_text,
            "chunk_delay": chunk_delay,
        }
        handler = type("CfgHandler", (_Handler,), {"_cfg": cfg})
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        """The OpenAI-style base URL (…/v1) — exactly the user's config shape."""
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def start(self) -> "MockLlamaCppServer":
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
