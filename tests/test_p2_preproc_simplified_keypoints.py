"""P2 (Test-Net Deepening): hermetic tests for
``core/summarisation/simplified_keypoints.py`` (SimplifiedKeypointsBuilder).

Covers (567 stmts, 12% baseline coverage):

  - ``__init__``               — settings wiring, model resolution, swap logic
  - ``_call_llm`` / ``_call_llm_single`` — provider dispatch
  - ``_call_ollama``           — model_exists guard, payload, timeouts,
                                  empty-response fail-soft, Qwen /no_think
  - ``_call_openai_compat``    — delegation to the shared dispatcher
  - ``_strip_thinking``        — CoT / preamble / meta-line stripping
  - ``_validate_simplification`` — the 14-guardrail gatekeeper (accept +
                                  reject matrix)
  - ``_build_jargon_cache`` / ``_identify_jargon`` — pyenchant absent path
                                  + fake-dict path
  - ``_translate_single_bullet`` (D1), ``_translate_single_bullet_targeted``
                                  (D2), ``_translate_batch``
  - ``_build_markdown`` / ``_build_clean_markdown`` / ``_build_docx``
  - ``build``                  — preset skip, aggregation, sequential loop,
                                  model swap, retry branch, DOCX failure

Hermeticity:
  - ``Settings`` replaced by a FakeSettings stand-in (group_b pattern).
  - LLM calls stubbed at the ``_call_llm_single`` / ``_call_llm`` / dispatcher
    boundaries; Ollama HTTP stubbed via ``safe_ollama_request``.
  - ModelManager (process-wide singleton) methods are monkeypatched per-test
    (instance attributes — auto-restored).
  - python-docx (real package) writes into tmp_path only.

Run: pytest tests/test_p2_preproc_simplified_keypoints.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.summarisation.simplified_keypoints as sk
from core.models import ConversionRequest, SummaryResult


class _FakeSettings:
    """Hermetic Settings stand-in (group_b pattern)."""

    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_ollama_url(self):
        url = self._values.get("_ollama_url")
        if url == "RAISE":
            raise RuntimeError("no url")
        return url or "http://localhost:9999"


@pytest.fixture()
def builder(monkeypatch):
    """A SimplifiedKeypointsBuilder wired to hermetic FakeSettings."""
    monkeypatch.setattr(sk, "Settings", _FakeSettings)
    req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
    b = sk.SimplifiedKeypointsBuilder(req)
    b.retries = 0  # single-attempt fail-soft (keeps tests fast, no backoff)
    return b


def _summary(bullets, success=True):
    return SummaryResult(
        chapter_heading="C1",
        executive_summary="e",
        thorough_summary="t",
        bullet_points=list(bullets),
        success=success,
    )


# ═══════════════════════════════════════════════════════════════════════════
# __init__ wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_defaults(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        b = sk.SimplifiedKeypointsBuilder(req)
        assert b.provider == "ollama"
        assert b.model == req.summarisation_model
        assert b.ollama_base_url == "http://localhost:9999"
        assert b.temperature == 0.1
        assert b.batch_size == 10
        assert b.timeout == 420
        assert b.max_batch_tokens == 8000
        assert b.max_output_tokens_per_batch == 4096
        # No simplification model configured → swap flag is the empty string
        # (falsy) — the expression returns "" rather than a bool.
        assert not b._needs_model_swap
        assert b._jargon_cache == {}
        assert b._jargon_cache_built is False

    def test_settings_values_wired(self, monkeypatch):
        values = {
            "summarisation.provider": "openrouter",
            "summarisation.api_key": "KEY",
            "summarisation.api_base_url": "https://example.test/v1",
            "summarisation.cloud_model": "some/model",
            "summarisation.cloud_max_tokens": 1234,
            "summarisation.freellmapi_url": "http://free.test/v1",
            "summarisation.freellmapi_key": "FREEKEY",
            "summarisation.freellmapi_model": "automodel",
        }
        monkeypatch.setattr(sk, "Settings", lambda: _FakeSettings(values))
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        b = sk.SimplifiedKeypointsBuilder(req)
        assert b.provider == "openrouter"
        assert b.api_key == "KEY"
        assert b.api_base_url == "https://example.test/v1"
        assert b.cloud_model == "some/model"
        assert b.cloud_max_tokens == 1234
        assert b.freellmapi_url == "http://free.test/v1"
        assert b.freellmapi_key == "FREEKEY"
        assert b.freellmapi_model == "automodel"

    def test_get_ollama_url_failure_falls_back(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", lambda: _FakeSettings({"_ollama_url": "RAISE"}))
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        b = sk.SimplifiedKeypointsBuilder(req)
        assert b.ollama_base_url == "http://localhost:11434"

    def test_model_resolution_simplification_model(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        b = sk.SimplifiedKeypointsBuilder(req)
        assert b.model == "qwythos:latest"
        assert b._needs_model_swap is True

    def test_no_swap_when_same_as_summarisation_model(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = req.summarisation_model
        b = sk.SimplifiedKeypointsBuilder(req)
        assert not b._needs_model_swap

    def test_no_swap_when_same_as_fast_model(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.fast_model = "fastmodel:latest"
        req.simplification_model = "fastmodel:latest"
        b = sk.SimplifiedKeypointsBuilder(req)
        assert not b._needs_model_swap

    def test_fast_model_used_when_no_simplification_model(self, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.fast_model = "fastmodel:latest"
        b = sk.SimplifiedKeypointsBuilder(req)
        assert b.model == "fastmodel:latest"


# ═══════════════════════════════════════════════════════════════════════════
# Provider dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestCallLLMDispatch:
    def test_freellmapi(self, builder, monkeypatch):
        builder.provider = "freellmapi"
        seen = {}

        def fake(prompt, base_url, api_key, model, label):
            seen.update(locals())
            return "ok"

        monkeypatch.setattr(builder, "_call_openai_compat", fake)
        assert builder._call_llm("P") == "ok"
        assert seen["label"] == "FreeLLMAPI"
        assert seen["base_url"] == builder.freellmapi_url
        assert seen["model"] == builder.freellmapi_model

    @pytest.mark.parametrize("provider", ["openrouter", "openai"])
    def test_cloud_providers(self, builder, monkeypatch, provider):
        builder.provider = provider
        seen = {}

        def fake(prompt, base_url, api_key, model, label):
            seen.update(locals())
            return "ok"

        monkeypatch.setattr(builder, "_call_openai_compat", fake)
        assert builder._call_llm("P") == "ok"
        assert seen["label"] == provider.capitalize()
        assert seen["base_url"] == builder.api_base_url
        assert seen["model"] == builder.cloud_model

    def test_ollama_default(self, builder, monkeypatch):
        builder.provider = "ollama"
        monkeypatch.setattr(builder, "_call_ollama", lambda p, **k: "ollama-ok")
        assert builder._call_llm("P") == "ollama-ok"

    def test_single_freellmapi(self, builder, monkeypatch):
        builder.provider = "freellmapi"
        monkeypatch.setattr(builder, "_call_openai_compat", lambda *a, **k: "ok")
        assert builder._call_llm_single("P") == "ok"

    def test_single_cloud(self, builder, monkeypatch):
        builder.provider = "openai"
        monkeypatch.setattr(builder, "_call_openai_compat", lambda *a, **k: "ok")
        assert builder._call_llm_single("P") == "ok"

    def test_single_ollama_uses_no_think_and_512(self, builder, monkeypatch):
        builder.provider = "ollama"
        seen = {}

        def fake(prompt, no_think=False, max_predict=None):
            seen.update(locals())
            return "ok"

        monkeypatch.setattr(builder, "_call_ollama", fake)
        assert builder._call_llm_single("P") == "ok"
        assert seen["no_think"] is False
        assert seen["max_predict"] == 512


# ═══════════════════════════════════════════════════════════════════════════
# _call_ollama (HTTP stubbed at safe_ollama_request)
# ═══════════════════════════════════════════════════════════════════════════


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestCallOllama:
    def test_model_missing_returns_none(self, builder, monkeypatch):
        logs = []
        builder.log = lambda msg, level="INFO": logs.append((msg, level))
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: False)
        assert builder._call_ollama("prompt") is None
        assert any("not found" in m and level == "WARNING" for m, level in logs)

    def test_success_batch_call(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)
        seen = {}

        def fake_request(method, url, json=None, timeout=None, **kw):
            seen.update({"method": method, "url": url, "json": json, "timeout": timeout})
            return _FakeResp({"response": "  translated text  "})

        monkeypatch.setattr(sk, "safe_ollama_request", fake_request)
        out = builder._call_ollama("PROMPT")
        assert out == "translated text"
        assert seen["method"] == "POST"
        assert seen["url"].endswith("/api/generate")
        assert seen["timeout"] == 420  # batch call
        payload = seen["json"]
        assert payload["model"] == builder.model
        assert payload["prompt"] == "PROMPT"
        assert payload["stream"] is False
        assert payload["options"]["num_predict"] == 4096
        assert payload["options"]["temperature"] == 0.1
        assert payload["options"]["num_ctx"] == max(
            8000, builder.request.summarisation_max_context_tokens
        )

    def test_single_call_timeout_and_max_predict(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)
        seen = {}

        def fake_request(method, url, json=None, timeout=None, **kw):
            seen["timeout"] = timeout
            return _FakeResp({"response": "short text output"})

        monkeypatch.setattr(sk, "safe_ollama_request", fake_request)
        assert builder._call_ollama("PROMPT", max_predict=512) == "short text output"
        assert seen["timeout"] == 120

    def test_qwen_no_think_prefix(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)
        builder.model = "qwen3.5:latest"
        seen = {}

        def fake_request(method, url, json=None, timeout=None, **kw):
            seen["json"] = json
            return _FakeResp({"response": "ok text here"})

        monkeypatch.setattr(sk, "safe_ollama_request", fake_request)
        builder._call_ollama("PROMPT", no_think=True, max_predict=512)
        assert seen["json"]["prompt"].endswith("/no_think")

    def test_non_qwen_no_think_untouched(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)
        seen = {}

        def fake_request(method, url, json=None, timeout=None, **kw):
            seen["json"] = json
            return _FakeResp({"response": "ok text here"})

        monkeypatch.setattr(sk, "safe_ollama_request", fake_request)
        builder.model = "gemma3:12b"
        builder._call_ollama("PROMPT", no_think=True, max_predict=512)
        assert seen["json"]["prompt"] == "PROMPT"

    def test_empty_response_fails_soft(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)
        logs = []
        builder.log = lambda msg, level="INFO": logs.append((msg, level))
        monkeypatch.setattr(
            sk, "safe_ollama_request", lambda *a, **k: _FakeResp({"response": "   "})
        )
        assert builder._call_ollama("PROMPT") is None
        assert any("call failed" in m for m, _ in logs)

    def test_http_error_fails_soft(self, builder, monkeypatch):
        monkeypatch.setattr(builder.model_manager, "model_exists", lambda name: True)

        def boom(*a, **k):
            raise TimeoutError("ollama timed out")

        monkeypatch.setattr(sk, "safe_ollama_request", boom)
        assert builder._call_ollama("PROMPT") is None


class TestCallOpenAICompat:
    def test_delegates_to_dispatcher(self, builder, monkeypatch):
        import core.summarisation.llm_dispatcher as dispatcher

        seen = {}

        def fake(prompt, base_url, api_key, model, label, temperature, max_tokens, **kw):
            seen.update(locals())
            return "dispatched"

        monkeypatch.setattr(dispatcher, "call_openai_compat", fake)
        out = builder._call_openai_compat("P", "http://b", "K", "m", "Lbl")
        assert out == "dispatched"
        assert seen["prompt"] == "P"
        assert seen["base_url"] == "http://b"
        assert seen["api_key"] == "K"
        assert seen["model"] == "m"
        assert seen["label"] == "Lbl"
        assert seen["temperature"] == 0.1
        assert seen["max_tokens"] == 4096


# ═══════════════════════════════════════════════════════════════════════════
# _strip_thinking
# ═══════════════════════════════════════════════════════════════════════════


# The _strip_thinking think-block marker (source builds it via an f-string
# to avoid literal tag fragments in this file): "abd" is a no-op marker on
# this machine — the REAL guard is the <thinking> tag path exercised below.
THINK_OPEN = "<think" + "ing>"
THINK_CLOSE = "</think" + "ing>"


class TestStripThinking:
    def test_think_block_removed(self):
        b = builder_none()
        out = b._strip_thinking(
            f"{THINK_OPEN}internal reasoning{THINK_CLOSE}Done. Here is the answer text."
        )
        assert out == "Done. Here is the answer text."

    def test_thinking_tag_closed_removed(self):
        b = builder_none()
        out = b._strip_thinking("<thinking>reasoning</thinking>Visible output.")
        assert out == "Visible output."

    def test_preamble_removed(self):
        b = builder_none()
        out = b._strip_thinking("Sure, I'll help with that.\n\n1. Real content here.")
        assert out == "1. Real content here."

    def test_inline_reasoning_suffix_removed(self):
        b = builder_none()
        out = b._strip_thinking("1. Real item text here. I'll keep the term in quotes.")
        assert out == "1. Real item text here."

    def test_parenthetical_original_note_removed(self):
        b = builder_none()
        out = b._strip_thinking("1. Real item text (Original: 'term') stays.")
        assert "Original" not in out
        assert out.startswith("1. Real item text")

    def test_sub_bullet_analysis_removed(self):
        b = builder_none()
        out = b._strip_thinking("*Jargon: something\n1. Real item.")
        assert out == "1. Real item."

    def test_standalone_thinking_lines_removed(self):
        b = builder_none()
        out = b._strip_thinking("Analyze the input first.\nProcess each item.\n1. Real item.")
        assert out == "1. Real item."

    def test_plain_text_preserved(self):
        b = builder_none()
        assert b._strip_thinking("1. Just a normal item.") == "1. Just a normal item."


def builder_none() -> sk.SimplifiedKeypointsBuilder:
    """Build a builder without pytest fixtures (for plain helper use)."""
    orig = sk.Settings
    sk.Settings = _FakeSettings
    try:
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        b = sk.SimplifiedKeypointsBuilder(req)
    finally:
        sk.Settings = orig
    return b


# ═══════════════════════════════════════════════════════════════════════════
# _validate_simplification — the 14-guardrail gatekeeper
# ═══════════════════════════════════════════════════════════════════════════


ORIG = "The organizational strategy requires multifaceted implementation."
ACCEPT = "The plan needs many steps to carry out properly."


class TestValidateSimplification:
    def test_accept_valid(self, builder):
        assert builder._validate_simplification(ORIG, ACCEPT) == ACCEPT

    def test_accept_adds_period(self, builder):
        assert builder._validate_simplification(ORIG, ACCEPT[:-1]) == ACCEPT

    def test_reject_empty(self, builder):
        assert builder._validate_simplification(ORIG, "   ") is None

    @pytest.mark.parametrize(
        "response",
        [
            "Simplified: The plan needs many steps.",  # reasoning prefix
            "I replaced the jargon with plain words here.",  # meta commentary
            "The plan becomes something -> else entirely here.",  # arrow
            "The plan becomes something → else entirely here.",  # unicode arrow
            "The plan works.\n- step one detail here",  # newline bullet list
            "The plan works well.\nSecond line appears here.",  # multiline
            "The plan works well 索取 today.",  # CJK leakage
            "Too short.",  # < 5 words
            "The plan needs many steps instead of",  # truncation word ending
            "The plan needs (many steps to work out properly.",  # unbalanced paren
            'The plan needs "many steps to work properly.',  # odd quote count
            "The plan needs many steps instead of just.",  # ends with 'just.'
            "One sentence here. Two sentence here. Three sentence here.",  # 3+ sentences
            ("word " * 61).strip() + ".",  # > 60 words
            "This translation keeps the meaning intact today.",  # reasoning indicator
            ORIG,  # verbatim copy (>0.90 similarity)
        ],
    )
    def test_rejects(self, builder, response):
        assert builder._validate_simplification(ORIG, response) is None

    def test_reject_unclosed_thinking_tag(self, builder):
        # Unclosed tag → the whole response is dropped → too-short → None.
        assert (
            builder._validate_simplification(ORIG, f"{THINK_OPEN}reasoning never closed output")
            is None
        )

    def test_reject_dissimilar(self, builder):
        # < 0.10 similarity needs disjoint alphabets: original has no 'w'.
        assert builder._validate_simplification("qqqqqqqqqq", "wwww wwww wwww wwww wwww.") is None

    def test_reject_overlong_response(self, builder):
        # Passes the 60-word gate but exceeds the final 500-char cleanup bound.
        response = ("understanding " * 40).strip() + " period ends."
        assert len(response) > 500
        assert builder._validate_simplification(ORIG + " understanding.", response) is None

    def test_unicode_normalised(self, builder):
        out = builder._validate_simplification(
            ORIG, "The plan needs \u201cmany steps\u201d to work properly."
        )
        assert out == 'The plan needs "many steps" to work properly.'

    def test_numbering_and_bullet_prefix_stripped(self, builder):
        assert builder._validate_simplification(ORIG, f"1. {ACCEPT}") == ACCEPT
        assert builder._validate_simplification(ORIG, f"- {ACCEPT}") == ACCEPT

    def test_surrounding_quotes_stripped(self, builder):
        assert builder._validate_simplification(ORIG, f'"{ACCEPT}"') == ACCEPT


# ═══════════════════════════════════════════════════════════════════════════
# Jargon cache + identification (pyenchant absent → length fallback)
# ═══════════════════════════════════════════════════════════════════════════


class TestJargon:
    def test_cache_skipped_without_enchant(self, builder):
        if builder._enchant_dict is not None:
            pytest.skip("pyenchant installed on this machine — absent path not reachable")
        logs = []
        builder.log = lambda msg, level="INFO": logs.append((msg, level))
        builder._build_jargon_cache(["some bullet text here"])
        assert builder._jargon_cache_built is False
        assert any("pyenchant not available" in m for m, _ in logs)

    def test_identify_jargon_fallback_twelve_chars(self, builder):
        # No enchant, cache not built → 12+ char words are jargon.
        if builder._enchant_dict is not None:
            pytest.skip("pyenchant installed on this machine — absent path not reachable")
        out = builder._identify_jargon(
            "The multifaceted paradigm demonstrates organizational capabilities."
        )
        assert out == ["multifaceted", "demonstrates", "organizational", "capabilities"]

    def test_identify_jargon_cache_hit(self, builder):
        builder._jargon_cache.update({"multifaceted": True, "organizational": False})
        builder._jargon_cache_built = True
        out = builder._identify_jargon("multifaceted organizational")
        assert out == ["multifaceted"]

    def test_identify_jargon_cache_miss_with_fake_enchant(self, builder):
        class _Dict:
            def check(self, word):
                return word == "organizational"  # dictionary word

        builder._enchant_dict = _Dict()
        builder._jargon_cache_built = False
        out = builder._identify_jargon("organizational multifaceted")
        assert out == ["multifaceted"]
        # The miss was cached for subsequent lookups.
        assert builder._jargon_cache["organizational"] is False
        assert builder._jargon_cache["multifaceted"] is True

    def test_jargon_capped_at_five(self, builder):
        if builder._enchant_dict is not None:
            pytest.skip("pyenchant installed on this machine — absent path not reachable")
        words = " ".join(f"wordlong{c}xyz" for c in "abcdefgh")
        assert len(builder._identify_jargon(words)) == 5

    def test_build_cache_with_fake_enchant(self, builder):
        class _Dict:
            def check(self, word):
                return word not in ("zzznotaword", "multifaceted")

        builder._enchant_dict = _Dict()
        logs = []
        builder.log = lambda msg, level="INFO": logs.append((msg, level))
        builder._build_jargon_cache(
            ["organizational behavior", "ryan went home", "multifaceted zzznotaword"]
        )
        assert builder._jargon_cache_built is True
        assert builder._jargon_cache["organizational"] is False
        # NOTE: the _COMMON_NAMES allowlist ("ryan", "amsterdam", ...) is
        # dead code — the scan regex only matches 10+ char words and every
        # listed name is shorter, so "ryan" never even enters the cache.
        assert "ryan" not in builder._jargon_cache
        assert builder._jargon_cache["multifaceted"] is True
        assert builder._jargon_cache["zzznotaword"] is True
        assert any("Jargon cache built" in m for m, _ in logs)

    def test_build_cache_empty_wordset(self, builder):
        class _Dict:
            def check(self, word):
                return True

        builder._enchant_dict = _Dict()
        builder._build_jargon_cache(["short words only"])
        assert builder._jargon_cache_built is True
        assert builder._jargon_cache == {}


# ═══════════════════════════════════════════════════════════════════════════
# D1 / D2 / batch translation (LLM stubbed at the call boundary)
# ═══════════════════════════════════════════════════════════════════════════


class TestTranslateSingleBullet:
    def test_empty_returns_none(self, builder):
        assert builder._translate_single_bullet("") is None
        assert builder._translate_single_bullet("   ") is None

    def test_llm_none_returns_none(self, builder, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: None)
        assert builder._translate_single_bullet("A reasonable length bullet.") is None

    def test_valid_response_returned(self, builder, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: ACCEPT)
        assert builder._translate_single_bullet(ORIG) == ACCEPT

    def test_invalid_response_rejected(self, builder, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: "Simplified: nope nope nope.")
        assert builder._translate_single_bullet(ORIG) is None

    def test_custom_prompt_template_used(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        monkeypatch.setattr(
            sk, "Settings", lambda: _FakeSettings({"summarisation.simplified_prompt": "my_custom"})
        )
        seen = {}

        def fake_load(self, name):
            seen["name"] = name
            return "CUSTOM {{keypoints}} TEMPLATE"

        monkeypatch.setattr(pm_mod.PromptManager, "load_prompt", fake_load)
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: seen.update(prompt=p) or ACCEPT)
        assert builder._translate_single_bullet(ORIG) == ACCEPT
        assert seen["name"] == "my_custom"
        assert "CUSTOM" in seen["prompt"]
        assert f"1. {ORIG}" in seen["prompt"]

    def test_render_template_fallback(self, builder, monkeypatch):
        seen = {}
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: seen.update(prompt=p) or ACCEPT)
        builder._translate_single_bullet(ORIG)
        # The built-in simplified_d1 template was rendered with the bullet.
        assert ORIG in seen["prompt"]

    def test_render_failure_still_calls_llm(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        def boom(self, name, **kw):
            raise RuntimeError("pm down")

        monkeypatch.setattr(pm_mod.PromptManager, "render_template", boom)
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: ACCEPT)
        # prompt falls back to None; _call_llm_single receives None.
        assert builder._translate_single_bullet(ORIG) == ACCEPT


class TestTranslateSingleBulletTargeted:
    def test_empty_returns_none(self, builder):
        assert builder._translate_single_bullet_targeted("") is None

    def test_no_jargon_returns_original(self, builder, monkeypatch):
        monkeypatch.setattr(
            builder,
            "_call_llm_single",
            lambda p: (_ for _ in ()).throw(AssertionError("must not call LLM")),
        )
        bullet = "The difficult technical terminology confuses readers."
        assert builder._translate_single_bullet_targeted(bullet) == bullet

    def test_jargon_translated(self, builder, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: ACCEPT)
        assert builder._translate_single_bullet_targeted(ORIG) == ACCEPT

    def test_invalid_response_rejected(self, builder, monkeypatch):
        monkeypatch.setattr(
            builder, "_call_llm_single", lambda p: "I'll replace jargon here for you."
        )
        assert builder._translate_single_bullet_targeted(ORIG) is None


class TestTranslateBatch:
    def _patch_llm(self, builder, resp):
        def fake(prompt):
            return fake.resp

        fake.resp = resp
        builder._call_llm = fake

    def test_none_response(self, builder):
        self._patch_llm(builder, None)
        assert builder._translate_batch("kps") is None

    def test_single_item(self, builder):
        self._patch_llm(builder, "1. Single item only here.")
        assert builder._translate_batch("kps") == ["Single item only here."]

    def test_best_run_selected(self, builder):
        self._patch_llm(
            builder,
            "Analyze input.\n"
            "1. First translated keypoint about things.\n"
            "2. Second translated keypoint here.\n"
            "Check facts.\n"
            "1. First run alternative item text.\n"
            "2. Second run alternative item text.\n"
            "3. Third run alternative item here.\n"
            "Final Review\n"
            "1. Another new run starts here now.\n"
            "2. Another second item in run.\n",
        )
        out = builder._translate_batch("kps")
        assert out == [
            "First run alternative item text.",
            "Second run alternative item text.",
            "Third run alternative item here.",
        ]

    def test_no_numbered_lines_returns_none(self, builder):
        self._patch_llm(builder, "no numbers at all here")
        assert builder._translate_batch("kps") is None

    def test_continuation_line_appended(self, builder):
        self._patch_llm(builder, "1. Item with continuation\non the next line here.")
        assert builder._translate_batch("kps") == ["Item with continuation on the next line here."]

    def test_inline_thinking_stripped_from_items(self, builder):
        self._patch_llm(
            builder,
            "1. First item text here. Original: 'term' note.\n2. Second item text follows now.",
        )
        out = builder._translate_batch("kps")
        assert out == ["First item text here.", "Second item text follows now."]

    def test_custom_prompt_template(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        monkeypatch.setattr(
            sk,
            "Settings",
            lambda: _FakeSettings({"summarisation.simplified_prompt": "custom_batch"}),
        )
        seen = {}

        def fake_load(self, name):
            seen["name"] = name
            return "BATCH {{keypoints}} TEMPLATE"

        monkeypatch.setattr(pm_mod.PromptManager, "load_prompt", fake_load)
        self._patch_llm(builder, "1. Single item only here.")
        assert builder._translate_batch("THE-KEYPOINTS") == ["Single item only here."]
        assert seen["name"] == "custom_batch"

    def test_prompt_receives_keypoints(self, builder):
        prompts = []
        builder._call_llm = lambda p: prompts.append(p) or "1. Single item only here."
        builder._translate_batch("THE-KEYPOINTS")
        assert any("THE-KEYPOINTS" in p for p in prompts)


# ═══════════════════════════════════════════════════════════════════════════
# Output builders
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputBuilders:
    def test_markdown_with_stats(self, builder):
        md = builder._build_markdown(
            "BookX",
            ["First point.", "Second point."],
            simplified_count=2,
            preserved_count=1,
            failed_count=3,
        )
        assert md.startswith("# Simplified Keypoints Digest: BookX")
        assert "**Total keypoints:** 2" in md
        assert "**2 Simplified**" in md
        assert "**1 Preserved**" in md
        assert "**3 Failed**" in md
        assert "1. First point." in md and "2. Second point." in md

    def test_markdown_without_stats(self, builder):
        md = builder._build_markdown("BookX", ["Only point."])
        assert "📊" not in md
        assert "1. Only point." in md

    def test_clean_markdown(self, builder):
        clean = builder._build_clean_markdown("BookX", ["A point.", "B point."])
        assert clean == "1. A point.\n2. B point."

    def test_docx_written(self, builder, tmp_path):
        out = tmp_path / "out.docx"
        builder._build_docx("BookX", ["Point one.", "Point two."], out)
        assert out.exists() and out.stat().st_size > 1000

    def test_docx_comparison_table(self, builder, tmp_path):
        from docx import Document

        out = tmp_path / "out.docx"
        builder._build_docx(
            "BookX",
            ["Simplified one.", "Original kept."],
            out,
            original_bullets=["Original one.", "Original kept."],
            was_simplified=[True, False],
        )
        doc = Document(str(out))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Side-by-Side Comparison" in text
        assert "Simplified List" in text
        table = doc.tables[0]
        assert table.rows[1].cells[1].text == "Original one."
        assert table.rows[2].cells[2].text == "Original kept."


# ═══════════════════════════════════════════════════════════════════════════
# build() — end-to-end (LLM stubbed, files into tmp_path)
# ═══════════════════════════════════════════════════════════════════════════


SKIP_PLAIN = "You can see the way out if you look."  # already plain → skipped
JARGON_BULLET = "The organizational implementation requires multifaceted coordination."
JARGON_SIMPLE = "The plan needs many steps to work together."
NEEDS_D1 = "The difficult technical terminology confuses readers."
D1_SIMPLE = "Hard words make reading tough for people."


class TestBuild:
    def test_academic_preset_skips_simplification(self, builder, tmp_path):
        builder.request.source_type = "academic_paper"
        assert builder.build([_summary([JARGON_BULLET])], "Book", tmp_path) is None

    def test_no_bullets_returns_none(self, builder, tmp_path):
        assert builder.build([], "Book", tmp_path) is None
        assert builder.build([_summary([], success=False)], "Book", tmp_path) is None

    def test_success_end_to_end(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(
            builder,
            "_call_llm_single",
            lambda p: JARGON_SIMPLE if "organizational" in p else D1_SIMPLE,
        )
        md = builder.build([_summary([SKIP_PLAIN, JARGON_BULLET, NEEDS_D1])], "MyBook", tmp_path)
        assert md == tmp_path / "MyBook.Keypoints.Simplified.md"
        content = md.read_text(encoding="utf-8")
        assert SKIP_PLAIN in content  # preserved as-is
        assert JARGON_SIMPLE in content
        assert D1_SIMPLE in content
        assert "**2 Simplified**" in content
        assert "**1 Preserved**" in content  # the already-plain bullet
        assert "Failed" not in content
        clean = (tmp_path / "MyBook.Keypoints.Simplified.Clean.md").read_text(encoding="utf-8")
        assert clean.splitlines()[0] == f"1. {SKIP_PLAIN}"
        assert (tmp_path / "MyBook.Keypoints.Simplified.docx").exists()

    def test_llm_failure_keeps_originals(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: None)
        md = builder.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        content = md.read_text(encoding="utf-8")
        assert JARGON_BULLET in content
        assert "**1 Failed**" in content

    def test_docx_failure_is_non_fatal(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: JARGON_SIMPLE)

        def boom(*a, **k):
            raise RuntimeError("docx exploded")

        monkeypatch.setattr(builder, "_build_docx", boom)
        logs = []
        builder.log = lambda msg, level="INFO": logs.append((msg, level))
        md = builder.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert md is not None and md.exists()
        assert any("Could not save DOCX" in m for m, _ in logs)

    def test_empty_bullets_filtered(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: JARGON_SIMPLE)
        md = builder.build([_summary([JARGON_BULLET, "   ", ""])], "Book", tmp_path)
        content = md.read_text(encoding="utf-8")
        assert "**Total keypoints:** 1" in content

    def test_access_violation_retry_branch(self, builder, tmp_path, monkeypatch):
        import core.summarisation.text_preprocessor as tp_mod

        calls = {"n": 0}

        def flaky(text):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("access violation detected")
            return (True, "already simple")

        monkeypatch.setattr(tp_mod, "should_skip_simplification", flaky)
        monkeypatch.setattr(builder, "_translate_single_bullet", lambda b: JARGON_SIMPLE)
        monkeypatch.setattr(time, "sleep", lambda s: None)
        md = builder.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert md is not None
        assert JARGON_SIMPLE in md.read_text(encoding="utf-8")
        # First call raised inside _simplify_one; the retry succeeded, so the
        # reassembly loop never needs a second skip-check (result != original).
        assert calls["n"] == 1

    def test_non_retryable_exception_branch(self, builder, tmp_path, monkeypatch):
        import core.summarisation.text_preprocessor as tp_mod

        calls = {"n": 0}

        def flaky(text):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("boom")
            return (True, "already simple")

        monkeypatch.setattr(tp_mod, "should_skip_simplification", flaky)
        monkeypatch.setattr(builder, "_translate_single_bullet", lambda b: None)
        md = builder.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        content = md.read_text(encoding="utf-8")
        assert JARGON_BULLET in content  # fell back to original

    def test_model_swap_success(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0
        monkeypatch.setattr(b.model_manager, "get_loaded_models", lambda: ["gemma3:12b"])
        unloaded = []
        monkeypatch.setattr(
            b.model_manager, "force_unload", lambda name: unloaded.append(name) or True
        )
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: name == "qwythos:latest")
        monkeypatch.setattr(
            b.model_manager,
            "acquire_model",
            lambda name, mtype, skip_vram_check=False: True,
        )
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        md = b.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert b.model == "qwythos:latest"
        assert unloaded == ["gemma3:12b", "qwythos:latest"]  # unload before + after
        assert md is not None

    def test_model_swap_acquire_failure_falls_back(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0
        monkeypatch.setattr(b.model_manager, "get_loaded_models", lambda: [])
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: True)
        monkeypatch.setattr(
            b.model_manager, "acquire_model", lambda name, mtype, skip_vram_check=False: False
        )
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        md = b.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert b.model == "gemma3:12b"  # fallback
        assert md is not None

    def test_model_swap_missing_model_falls_back(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0
        monkeypatch.setattr(b.model_manager, "get_loaded_models", lambda: [])
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: False)
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        logs = []
        b.log = lambda msg, level="INFO": logs.append((msg, level))
        assert b.build([_summary([JARGON_BULLET])], "Book", tmp_path) is not None
        assert b.model == "gemma3:12b"
        assert any("not found — using fallback" in m for m, _ in logs)

    def test_model_swap_get_loaded_models_error_is_tolerated(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0

        def boom():
            raise RuntimeError("ollama down")

        monkeypatch.setattr(b.model_manager, "get_loaded_models", boom)
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: True)
        monkeypatch.setattr(
            b.model_manager, "acquire_model", lambda name, mtype, skip_vram_check=False: True
        )
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        assert b.build([_summary([JARGON_BULLET])], "Book", tmp_path) is not None


class TestGapClosingBuilder:
    """Second-wave branch coverage for SimplifiedKeypointsBuilder."""

    def test_validate_rejects_result_prefix(self, builder):
        # "Result:" survives _strip_thinking and is caught by guardrail 4.
        assert (
            builder._validate_simplification(ORIG, "Result: The plan needs many clear steps.")
            is None
        )

    def test_validate_rejects_arrow_notation(self, builder):
        # "->" without any meta-commentary word → guardrail 6.
        assert (
            builder._validate_simplification(
                ORIG, "The plan goes from this -> that entirely today."
            )
            is None
        )

    def test_validate_rejects_three_sentences(self, builder):
        # Ends with a non-truncation word so guardrail 10c passes; the 3+
        # sentence structural check (guardrail 11) rejects it.
        resp = "One statement follows. Two statements follow. Three statements follow."
        assert builder._validate_simplification(ORIG, resp) is None

    def test_validate_rejects_overlong_single_sentence(self, builder):
        # Passes every guardrail (51 words, single sentence, similarity in
        # range) but exceeds the final 500-char cleanup bound.
        resp = ("The organizational strategy requires multifaceted implementation and " * 7).strip()
        resp += " sustained oversight."
        assert len(resp) > 500
        assert builder._validate_simplification(ORIG, resp) is None

    def test_d1_custom_prompt_load_failure(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        monkeypatch.setattr(
            sk, "Settings", lambda: _FakeSettings({"summarisation.simplified_prompt": "custom"})
        )

        def boom(self, name):
            raise RuntimeError("pm down")

        monkeypatch.setattr(pm_mod.PromptManager, "load_prompt", boom)
        monkeypatch.setattr(builder, "_call_llm_single", lambda p: ACCEPT)
        assert builder._translate_single_bullet(ORIG) == ACCEPT

    def test_batch_custom_prompt_load_failure(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        monkeypatch.setattr(
            sk, "Settings", lambda: _FakeSettings({"summarisation.simplified_prompt": "custom"})
        )

        def boom(self, name):
            raise RuntimeError("pm down")

        monkeypatch.setattr(pm_mod.PromptManager, "load_prompt", boom)
        builder._call_llm = lambda p: "1. Single item only here."
        assert builder._translate_batch("kps") == ["Single item only here."]

    def test_batch_render_failure_falls_back(self, builder, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        def boom(self, name, **kw):
            raise RuntimeError("pm down")

        monkeypatch.setattr(pm_mod.PromptManager, "render_template", boom)
        builder._call_llm = lambda p: "1. Single item only here."
        assert builder._translate_batch("kps") == ["Single item only here."]

    def test_batch_numbered_thinking_content_flushes_run(self, builder):
        builder._call_llm = lambda p: (
            "1. Real first item text here.\n"
            "2. Check facts and review the data.\n"
            "1. Another restart item text.\n"
            "2. Another second item text.\n"
        )
        assert builder._translate_batch("kps") == [
            "Another restart item text.",
            "Another second item text.",
        ]

    def test_batch_meta_line_flushes_run(self, builder):
        # "Point 1:meta" (no space after the colon — so the \b-anchored marker
        # regex matches) survives _strip_thinking and flushes the current run.
        builder._call_llm = lambda p: (
            "1. First item text here now.\n"
            "2. Second real item text.\n"
            "Point 1:meta note line here.\n"
            "1. Restarted item one text.\n"
            "2. Restarted item two text.\n"
        )
        assert builder._translate_batch("kps") == [
            "First item text here now.",
            "Second real item text.",
        ]

    def test_build_all_whitespace_bullets_returns_none(self, builder, tmp_path):
        assert builder.build([_summary(["   ", ""])], "Book", tmp_path) is None

    def test_build_retry_fails_again_returns_original(self, builder, tmp_path, monkeypatch):
        import core.summarisation.text_preprocessor as tp_mod

        monkeypatch.setattr(
            tp_mod, "should_skip_simplification", lambda text: (False, "needs work")
        )
        attempts = {"n": 0}

        def always_boom(bullet):
            attempts["n"] += 1
            raise RuntimeError("access violation again")

        monkeypatch.setattr(builder, "_translate_single_bullet", always_boom)
        monkeypatch.setattr(time, "sleep", lambda s: None)
        md = builder.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert attempts["n"] == 2  # initial + one retry
        assert JARGON_BULLET in md.read_text(encoding="utf-8")  # kept original

    def test_build_swap_unload_failure_logged(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0

        def bad_unload(name):
            raise RuntimeError("unload refused")

        monkeypatch.setattr(b.model_manager, "get_loaded_models", lambda: ["gemma3:12b"])
        monkeypatch.setattr(b.model_manager, "force_unload", bad_unload)
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: True)
        monkeypatch.setattr(
            b.model_manager, "acquire_model", lambda name, mtype, skip_vram_check=False: True
        )
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        logs = []
        b.log = lambda msg, level="INFO": logs.append((msg, level))
        md = b.build([_summary([JARGON_BULLET])], "Book", tmp_path)
        assert md is not None
        assert any("Could not unload" in m for m, _ in logs)

    def test_build_final_unload_failure_tolerated(self, builder, tmp_path, monkeypatch):
        monkeypatch.setattr(sk, "Settings", _FakeSettings)
        req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
        req.simplification_model = "qwythos:latest"
        req.summarisation_model = "gemma3:12b"
        b = sk.SimplifiedKeypointsBuilder(req)
        b.retries = 0
        unload_calls = []

        def unload_sometimes(name):
            unload_calls.append(name)
            if len(unload_calls) > 1:  # the final after-use unload
                raise RuntimeError("final unload refused")
            return True

        # A loaded summarisation model is required for the swap-in unload to
        # fire (build() only unloads models returned by get_loaded_models);
        # the second force_unload is the final after-use unload of the
        # simplification model, whose failure must be tolerated.
        monkeypatch.setattr(b.model_manager, "get_loaded_models", lambda: ["gemma3:12b"])
        monkeypatch.setattr(b.model_manager, "force_unload", unload_sometimes)
        monkeypatch.setattr(b.model_manager, "model_exists", lambda name: True)
        monkeypatch.setattr(
            b.model_manager, "acquire_model", lambda name, mtype, skip_vram_check=False: True
        )
        monkeypatch.setattr(b, "_call_llm_single", lambda p: JARGON_SIMPLE)
        assert b.build([_summary([JARGON_BULLET])], "Book", tmp_path) is not None
        assert len(unload_calls) == 2  # swap-in unload + final unload
        assert unload_calls == ["gemma3:12b", "qwythos:latest"]
