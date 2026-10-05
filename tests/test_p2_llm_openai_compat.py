"""Phase 2 (Test-Net Deepening) — ``core/llm/openai_compat_provider.py`` push.

Characterization tests for :class:`OpenAICompatProvider`. Baseline: 117/129
statements missed (9%).

Hermetic: the ``complete()`` transport is patched at the provider's
``session_for_url`` seam (V0.6.7 review-loop A5: complete() routes through
the pooled session instead of bare ``requests.post``) — assertions are the
same as the old requests.post patches, redirected to the mock session's
``.post``. The Batch API path (still ``requests.post`` / ``requests.get``)
keeps its module-level patches, and the Batch API poll loop's
``time.sleep`` is neutralised. No real HTTP ever leaves the process.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.llm.openai_compat_provider import OpenAICompatProvider  # noqa: E402


def _resp(status: int = 200, payload: dict | None = None, text: str = ""):
    r = requests.Response()
    r.status_code = status
    r._content = (
        __import__("json").dumps(payload).encode() if payload is not None else text.encode()
    )
    return r


def _chat_payload(content: str = "hello answer") -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _sess_patch(**post_kwargs):
    """Patch the provider transport seam with a mock pooled session.

    ``core.llm.openai_compat_provider`` imports ``session_for_url`` at module
    top (V0.6.7), so the seam is the provider module attribute. The mock
    session's ``.post`` accepts the same ``return_value=`` / ``side_effect=``
    kwargs as ``unittest.mock.patch("requests.post", ...)`` did.
    """
    sess = MagicMock()
    sess.post = MagicMock(**post_kwargs)
    return patch("core.llm.openai_compat_provider.session_for_url", return_value=sess), sess


@pytest.fixture
def logs() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def provider(logs) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        model="test-model",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-test",
        timeout=30,
        retries=0,
        log_callback=lambda msg, level="INFO": logs.append((level, msg)),
    )


# ── complete() ──────────────────────────────────────────────────────────────


class TestComplete:
    def test_success_returns_content(self, provider):
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload("  answer  ")))
        with patcher:
            assert provider.complete("prompt") == "answer"
        assert sess.post.call_args.kwargs["timeout"] == 30

    def test_headers_openrouter_referer(self, provider):
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload()))
        with patcher:
            provider.complete("p")
        headers = sess.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-test"
        assert headers["HTTP-Referer"] == "https://elixir.local"
        assert headers["X-Title"] == "Elixir"

    def test_headers_no_openrouter_extras(self, logs):
        p = OpenAICompatProvider(
            model="m",
            base_url="https://api.example.com/v1",
            api_key="k",
            retries=0,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload()))
        with patcher:
            p.complete("p")
        headers = sess.post.call_args.kwargs["headers"]
        assert "HTTP-Referer" not in headers
        assert "X-Title" not in headers

    def test_no_api_key_no_auth_header(self, logs):
        p = OpenAICompatProvider(
            model="m",
            base_url="https://api.example.com/v1",
            api_key="",
            retries=0,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload()))
        with patcher:
            p.complete("p")
        assert "Authorization" not in sess.post.call_args.kwargs["headers"]

    def test_payload_overrides(self, provider):
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload()))
        with patcher:
            provider.complete(
                "p", temperature=0.1, max_tokens=77, model="other-model", json_mode=True
            )
        payload = sess.post.call_args.kwargs["json"]
        assert payload["model"] == "other-model"
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] == 77
        assert payload["response_format"] == {"type": "json_object"}
        assert sess.post.call_args.args[0].endswith("/chat/completions")

    def test_defaults_used_when_no_overrides(self, provider):
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload()))
        with patcher:
            provider.complete("p")
        payload = sess.post.call_args.kwargs["json"]
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.6
        assert payload["max_tokens"] == 4096
        assert "response_format" not in payload

    def test_empty_response_returns_none_after_retry(self, provider):
        """Empty content → ConnectionError → with retries=0 the single attempt
        exhausts and complete() returns None (the legacy contract)."""
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload("   ")))
        with patcher:
            assert provider.complete("p") is None
        assert sess.post.call_count == 1

    def test_http_401_returns_none(self, provider):
        patcher, _sess = _sess_patch(return_value=_resp(401, {"error": "bad key"}))
        with patcher:
            assert provider.complete("p") is None

    def test_http_error_401_logged(self, provider, logs):
        patcher, _sess = _sess_patch(return_value=_resp(401, {"error": "bad key"}))
        with patcher:
            assert provider.complete("p") is None
        assert any("call failed" in msg for (_, msg) in logs)

    def test_connection_error_returns_none(self, provider):
        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("refused")

        patcher, _sess = _sess_patch(side_effect=boom)
        with patcher:
            assert provider.complete("p") is None

    def test_retryable_error_retried_then_success(self, logs):
        """429 is retryable — with retries=1 the second attempt wins."""
        p = OpenAICompatProvider(
            model="m",
            api_key="k",
            retries=1,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        responses = [_resp(429, {}), _resp(200, _chat_payload("second try"))]
        patcher, _sess = _sess_patch(side_effect=responses)
        with (
            patcher,
            patch("core.llm.retry._HAS_TENACITY", False),
            patch("core.llm.retry.time.sleep"),
        ):
            assert p.complete("p") == "second try"

    def test_malformed_json_returns_none(self, provider):
        """A 200 with an unexpected body → extract_openai_content "" → the
        empty-response ConnectionError path → retries=0 exhausts → None.
        (V0.6.7 A5: previously the deep-index KeyError went straight to the
        outer except; the shape-safe extract routes it through retry.)"""
        patcher, _sess = _sess_patch(return_value=_resp(200, {"unexpected": "shape"}))
        with patcher:
            assert provider.complete("p") is None


# ── batch_complete() — parallel path ────────────────────────────────────────


class TestBatchCompleteParallel:
    def test_empty_prompts_returns_empty(self, provider):
        assert provider.batch_complete([]) == []

    def test_parallel_results_in_order(self, provider):
        def fake_post(url, headers=None, json=None, timeout=None):
            return _resp(200, _chat_payload(f"ans::{json['messages'][0]['content']}"))

        patcher, _sess = _sess_patch(side_effect=fake_post)
        with patcher:
            results = provider.batch_complete(["p1", "p2", "p3"])
        assert results == ["ans::p1", "ans::p2", "ans::p3"]

    def test_parallel_item_failure_becomes_none(self, provider, logs):
        def fake_post(url, headers=None, json=None, timeout=None):
            if "p2" in json["messages"][0]["content"]:
                raise requests.exceptions.ConnectionError("boom")
            return _resp(200, _chat_payload("ok"))

        patcher, _sess = _sess_patch(side_effect=fake_post)
        with patcher:
            results = provider.batch_complete(["p1", "p2", "p3"])
        assert results[0] == "ok"
        assert results[1] is None
        assert results[2] == "ok"

    def test_batch_api_unavailable_falls_back_to_parallel(self, provider, logs):
        """use_batch_api=True with a non-OpenAI base URL → immediate None →
        parallel fallback (the 'Batch API unavailable' log line)."""
        patcher, sess = _sess_patch(return_value=_resp(200, _chat_payload("par")))
        with patcher:
            results = provider.batch_complete(["p1"], use_batch_api=True)
        assert results == ["par"]
        # Only the parallel call — no /files or /batches upload happened
        # (the batch path still uses bare requests.post; nothing touched it).
        assert all(
            "/chat/completions" in str(c.args[0]) or "chat" in str(c.args[0])
            for c in sess.post.call_args_list
        )


# ── _batch_api_complete() — the OpenAI Batch API path ──────────────────────


def _jsonl(entries: list[dict]) -> str:
    import json

    return "\n".join(json.dumps(e) for e in entries)


class TestBatchApi:
    @pytest.fixture
    def openai_provider(self, logs) -> OpenAICompatProvider:
        return OpenAICompatProvider(
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            api_key="sk-openai",
            retries=0,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )

    def test_non_openai_base_url_returns_none(self, provider):
        assert provider._batch_api_complete(["p"]) is None

    def test_missing_api_key_returns_none(self, logs):
        p = OpenAICompatProvider(
            model="m",
            base_url="https://api.openai.com/v1",
            api_key="",
            retries=0,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert p._batch_api_complete(["p"]) is None

    def test_upload_failure_returns_none(self, openai_provider, logs):
        with patch("requests.post", return_value=_resp(500, {})):
            assert openai_provider._batch_api_complete(["p"]) is None
        assert any("file upload failed" in msg for (_, msg) in logs)

    def test_upload_without_file_id_returns_none(self, openai_provider):
        with patch("requests.post", return_value=_resp(200, {"id": None})):
            assert openai_provider._batch_api_complete(["p"]) is None

    def test_batch_creation_failure_returns_none(self, openai_provider, logs):
        posts = [_resp(200, {"id": "file-1"}), _resp(403, {})]
        with patch("requests.post", side_effect=posts):
            assert openai_provider._batch_api_complete(["p"]) is None
        assert any("batch creation failed" in msg for (_, msg) in logs)

    def test_poll_failed_status_returns_none(self, openai_provider, logs, monkeypatch):
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        posts = [
            _resp(200, {"id": "file-1"}),  # upload
            _resp(200, {"id": "batch-1"}),  # create batch
        ]
        gets = [_resp(200, {"status": "failed"})]
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=gets),
        ):
            assert openai_provider._batch_api_complete(["p"]) is None
        assert any("job failed" in msg for (_, msg) in logs)

    def test_poll_timeout_returns_none(self, openai_provider, logs, monkeypatch):
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        posts = [_resp(200, {"id": "file-1"}), _resp(200, {"id": "batch-1"})]
        # 60 polls, none completed → the for/else timeout branch.
        gets = [_resp(200, {"status": "in_progress"})] * 60
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=gets),
        ):
            assert openai_provider._batch_api_complete(["p"]) is None
        assert any("timed out after 10 minutes" in msg for (_, msg) in logs)

    def test_poll_non_200_continues_then_completes(self, openai_provider, monkeypatch):
        """A transient non-200 poll is skipped (continue), then success."""
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        download = _resp(
            200,
            text=_jsonl(
                [
                    {
                        "custom_id": "request-0",
                        "response": {
                            "status_code": 200,
                            "body": _chat_payload("batched answer"),
                        },
                    }
                ]
            ),
        )
        posts = [_resp(200, {"id": "file-1"}), _resp(200, {"id": "batch-1"})]
        gets = [
            _resp(500, {}),  # poll error → continue
            _resp(200, {"status": "completed", "output_file_id": "out-1"}),
        ]
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=[*gets, download]),
        ):
            result = openai_provider._batch_api_complete(["p"])
        assert result == ["batched answer"]

    def test_full_flow_with_malformed_lines(self, openai_provider, logs, monkeypatch):
        """Malformed JSONL lines are skipped; non-200 entries left as None.

        NOTE (suspected production bug, reported not fixed): a JSONL line
        that parses to a NON-DICT (e.g. a bare JSON string) makes
        ``entry.get("custom_id", "")`` raise AttributeError, which is NOT in
        the caught ``(JSONDecodeError, KeyError, ValueError, IndexError)``
        tuple — it aborts the whole download parse. The line below is
        therefore deliberately UNPARSEABLE garbage (JSONDecodeError path),
        not a valid non-dict JSON value.
        """
        import json
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        good = [
            {
                "custom_id": "request-0",
                "response": {"status_code": 200, "body": _chat_payload("a")},
            },
            {
                "custom_id": "request-1",
                "response": {"status_code": 500, "body": _chat_payload("b")},
            },
            {"custom_id": "request-2", "response": {"status_code": 200, "body": _chat_payload("")}},
        ]
        download_text = "\n".join(
            [
                *(json.dumps(e) for e in good),
                "{not json at all",  # JSONDecodeError → skipped
                "custom_id: request-9",  # not JSON either
            ]
        )
        download = _resp(200, text=download_text)
        posts = [_resp(200, {"id": "file-1"}), _resp(200, {"id": "batch-1"})]
        gets = [_resp(200, {"status": "completed", "output_file_id": "out-1"})]
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=[*gets, download]),
        ):
            result = openai_provider._batch_api_complete(["p0", "p1", "p2"])
        assert result == ["a", None, None]
        assert any("1/3 completed" in msg for (_, msg) in logs)

    def test_download_failure_returns_none(self, openai_provider, monkeypatch):
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        posts = [_resp(200, {"id": "file-1"}), _resp(200, {"id": "batch-1"})]
        gets = [
            _resp(200, {"status": "completed", "output_file_id": "out-1"}),
            _resp(404, {}),
        ]
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=gets),
        ):
            assert openai_provider._batch_api_complete(["p"]) is None

    def test_outer_exception_returns_none(self, openai_provider, monkeypatch):
        """Any unexpected exception inside the Batch API flow → None."""
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)

        def boom(*a, **k):
            raise RuntimeError("surprise")

        with patch("requests.post", side_effect=boom):
            assert openai_provider._batch_api_complete(["p"]) is None

    def test_batch_complete_uses_batch_api_when_available(self, openai_provider, monkeypatch):
        """batch_complete(use_batch_api=True) returns the Batch API result
        (no parallel fallback log)."""
        import time as _time_mod

        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        download = _resp(
            200,
            text=_jsonl(
                [
                    {
                        "custom_id": "request-0",
                        "response": {"status_code": 200, "body": _chat_payload("B")},
                    }
                ]
            ),
        )
        posts = [_resp(200, {"id": "file-1"}), _resp(200, {"id": "batch-1"})]
        gets = [_resp(200, {"status": "completed", "output_file_id": "out-1"})]
        with (
            patch("requests.post", side_effect=posts),
            patch("requests.get", side_effect=[*gets, download]),
        ):
            assert openai_provider.batch_complete(["p"], use_batch_api=True) == ["B"]
