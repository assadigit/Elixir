"""V18.20.4.11 (P3 / O-c5): LLM transport unification — characterization pins.

The ~14 hand-rolled LLM HTTP call sites (podcast, packets, new_outputs, TTS
normalizer + VRAM manager, adaptive TOC, toc_extractor, translation engine/
translator/harakat/validator, cloud_client, llm_dispatcher cloud paths) now
all go through the shared pooled sessions in utils.network:

  - localhost endpoints → the no-proxy pooled session (proxy-immune, as
    safe_ollama_request has always been)
  - cloud endpoints     → the NEW pooled cloud session (proxy-TRUSTING —
    corporate proxies are legitimate for cloud APIs)
  - every OpenAI-compat deep-index parse goes through the NEW shape-safe
    extract_openai_content ("" on any malformed payload instead of
    KeyError/IndexError/TypeError)

This file pins: session routing, session properties, pooling identity,
payload-shape safety, and (source-scan) that no bare requests.post/get call
remains in the unified modules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import utils.network as net

_REPO = Path(__file__).resolve().parent.parent

# Every module whose LLM HTTP transport was unified in V18.20.4.11 (P3).
_UNIFIED_MODULES = [
    "core/podcast/script_generator.py",
    "core/outputs/packets/generator.py",
    "core/outputs/new_outputs.py",
    "core/tts/normalizer.py",
    "core/tts/vram_manager.py",
    # (V0.08 / P2: "core/pdf/adaptive_toc.py" removed with the dead module.)
    "core/pdf/toc_extractor.py",
    "core/translation/translation_engine.py",
    "core/translation/translator.py",
    "core/translation/harakat.py",
    "core/translation/validator.py",
    "core/llm/cloud_client.py",
    "core/summarisation/llm_dispatcher.py",
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. session_for_url — the ONE routing rule
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionForUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/api/generate",
            "http://127.0.0.1:11434/v1/chat/completions",
            "http://[::1]:11434/api/tags",
            "http://0.0.0.0:11500/api/generate",
            "http://localhost:11500",
        ],
    )
    def test_localhost_routes_to_no_proxy_session(self, url):
        sess = net.session_for_url(url)
        assert sess is net.get_shared_session()
        # the no-proxy invariants (as safe_ollama_request has always had)
        assert sess.trust_env is False
        assert sess.proxies == {"http": "", "https": ""}

    @pytest.mark.parametrize(
        "url",
        [
            "https://openrouter.ai/api/v1/chat/completions",
            "https://api.openai.com/v1/chat/completions",
            "https://api.anthropic.com/v1/messages",
            "http://llama-server.lan:8080/v1/chat/completions",  # non-local host
        ],
    )
    def test_cloud_routes_to_cloud_session(self, url):
        sess = net.session_for_url(url)
        assert sess is net.get_shared_cloud_session()
        # cloud endpoints legitimately use env proxies
        assert sess.trust_env is True

    def test_pooled_identity(self):
        """Both sessions are process-lifetime singletons — repeated routing
        returns the SAME object (connection reuse, no per-call sessions)."""
        assert net.session_for_url("http://localhost:11434") is net.session_for_url(
            "http://localhost:99999"
        )
        assert net.session_for_url("https://a.example.com") is net.session_for_url(
            "https://b.example.org"
        )
        assert net.session_for_url("http://localhost:1") is not net.session_for_url("https://x.com")

    def test_cloud_and_local_sessions_are_distinct(self):
        assert net.get_shared_session() is not net.get_shared_cloud_session()

    def test_garbage_url_never_raises(self):
        # fail-open to the cloud session (worst case: a proxied attempt)
        assert net.session_for_url("") is net.get_shared_cloud_session()
        assert net.session_for_url("not a url") is net.get_shared_cloud_session()


# ═══════════════════════════════════════════════════════════════════════════
# 2. extract_openai_content — shape-safe deep-index
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractOpenAIContent:
    def test_valid_payload(self):
        assert (
            net.extract_openai_content({"choices": [{"message": {"content": "  hello  "}}]})
            == "hello"
        )

    @pytest.mark.parametrize(
        "bad",
        [
            None,
            "not a dict",
            42,
            [],
            {},
            {"choices": []},
            {"choices": "nope"},
            {
                "choices": [
                    None,
                ]
            },
            {"choices": [{"no_message": 1}]},
            {"choices": [{"message": "not-a-dict"}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": 123}}]},
            {"error": {"message": "provider error payload"}},
        ],
    )
    def test_malformed_payloads_return_empty(self, bad):
        assert net.extract_openai_content(bad) == ""

    def test_real_provider_error_shape(self):
        # OpenRouter-style error body: no choices key at all
        assert net.extract_openai_content({"error": {"code": 429, "message": "Rate limited"}}) == ""


# ═══════════════════════════════════════════════════════════════════════════
# 3. Source pins — the unification is complete and stays complete
# ═══════════════════════════════════════════════════════════════════════════


def _strip_comments(src: str) -> str:
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # strip trailing comments (crude but conservative: only when the #
        # is preceded by whitespace and outside obvious string context)
        line = re.sub(r"\s+#.*$", "", line)
        out.append(line)
    return "\n".join(out)


class TestSourcePins:
    def test_no_bare_requests_calls_remain(self):
        """Every LLM HTTP call in the unified modules goes through the
        pooled sessions — a bare requests.post/get would be a regression
        to per-call TCP sessions (and, on localhost, proxy-sensitive)."""
        offenders = []
        for rel in _UNIFIED_MODULES:
            src = _strip_comments((_REPO / rel).read_text(encoding="utf-8"))
            for m in re.finditer(r"\brequests\.(post|get)\s*\(", src):
                offenders.append(f"{rel}: bare requests.{m.group(1)}()")
        assert not offenders, (
            "V18.20.4.11 (P3) regression — bare requests calls reintroduced: "
            + "; ".join(offenders)
        )

    def test_every_unified_module_imports_session_for_url(self):
        for rel in _UNIFIED_MODULES:
            src = (_REPO / rel).read_text(encoding="utf-8")
            assert "session_for_url" in src, f"{rel} lost its pooled transport"

    def test_deep_index_choices_parse_is_gone(self):
        """The old crash-prone one-liner must not come back in the unified
        modules (extract_openai_content is the only sanctioned parse)."""
        offenders = []
        for rel in _UNIFIED_MODULES:
            src = _strip_comments((_REPO / rel).read_text(encoding="utf-8"))
            if re.search(r'\["choices"\]\s*\[\s*0\s*\]', src):
                offenders.append(rel)
        assert not offenders, f"deep-index choices[0] parse reintroduced: {offenders}"

    def test_packets_streaming_contract_intact(self):
        """The V13.31/V13.35 packets contract (tuple timeout, stream=True,
        2-attempt loop) must survive the transport swap — it was lost 3
        times by rewrites before being pinned."""
        src = _strip_comments(
            (_REPO / "core/outputs/packets/generator.py").read_text(encoding="utf-8")
        )
        assert "timeout = (10, 300)" in src
        assert src.count("stream=True") >= 3  # payload flag + transport kwarg ×3 branches
        assert "max_retries = 2" in src
        # every streamed response is closed (pooled-connection hygiene)
        assert src.count("resp.close()") == 3

    def test_timeouts_everywhere(self):
        """No LLM call without an explicit timeout kwarg in the unified
        modules (W-c7 class of bug — adaptive_toc once hung forever)."""
        for rel in _UNIFIED_MODULES:
            src = _strip_comments((_REPO / rel).read_text(encoding="utf-8"))
            for m in re.finditer(r"\.post\(\s*\n", src):
                # multi-line call — look ahead for a timeout= within the call
                window = src[m.start() : m.start() + 700]
                if "def " in window.split("(")[0]:
                    continue
                assert "timeout" in window, (
                    f"{rel}: .post( call without timeout near: {window[:80]!r}"
                )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Behavioral pin — the retry-on-empty semantics survived the swap
# ═══════════════════════════════════════════════════════════════════════════


class TestDispatcherEmptyRetrySemantics:
    def test_openai_compat_malformed_payload_retries_then_none(self):
        """A malformed provider payload (no choices) previously raised
        KeyError straight to the outer except → None. Now it flows into
        the SAME empty-response retry path (strictly better: one retry
        before giving up), then None — never a crash."""
        from unittest.mock import MagicMock, patch

        from core.summarisation.llm_dispatcher import call_openai_compat

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": {"message": "boom"}}
        mock_response.raise_for_status = MagicMock()

        attempts = []

        def _fake_post(url, json=None, timeout=None, headers=None):
            attempts.append(url)
            return mock_response

        class _Sess:
            post = staticmethod(_fake_post)

        logs = []
        with patch(
            "core.summarisation.llm_dispatcher.session_for_url",
            return_value=_Sess(),
        ):
            result = call_openai_compat(
                prompt="p",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                model="gpt-4",
                label="OpenAI",
                temp=0.7,
                max_tokens=100,
                timeout=600,
                retries=1,  # 2 attempts total
                provider="openai",
                log=lambda m, l: logs.append((l, m)),
            )
        assert result is None
        assert len(attempts) == 2, "malformed payload must retry once before None"
        assert any(l == "WARNING" for l, _ in logs)
