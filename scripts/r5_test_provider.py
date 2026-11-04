"""Round-5 evidence — a REAL minimal OpenAI-compatible test provider.

This is a genuine local HTTP server implementing the OpenAI API shape the
app already speaks (the ``openai_compatible`` provider family — the same
interface LM Studio / vLLM / llama-server expose):

  GET  /v1/models           → the model listing ({"data": [{"id": …}]})
  POST /v1/chat/completions → a REAL completion response

It is used ONLY for the now6_backend_connected.png evidence: the app's own
connection-state model (``core.system.backend_connection``) sends its real
tiny verification POST, this server genuinely answers it, and the app
genuinely derives CONNECTED from that exchange — nothing is faked, no
state is hardcoded (spec §9: "Do not fake a successful connection for
screenshot purposes").

Run:  python scripts/r5_test_provider.py [port]   (default 8090)
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_ID = "elixir-test-model"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.rstrip("/")
        if path.endswith("/models"):
            self._json(
                200,
                {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]},
            )
        elif path.endswith("/api/tags"):
            # The Ollama shape (for the Model-unavailable evidence: the
            # server is reachable and lists models — just not the one the
            # profile configures).
            self._json(200, {"models": [{"name": "a-real-model:latest"}]})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            payload = {}
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) < 10:
            self._json(401, {"error": {"message": "missing bearer key"}})
            return
        model = payload.get("model", MODEL_ID)
        self._json(
            200,
            {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"test provider listening on http://127.0.0.1:{port}/v1 (model: {MODEL_ID})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
