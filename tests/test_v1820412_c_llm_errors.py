"""V18.20.4.12 (batch C) — LLM error semantics unification (T-c7) + qwythos
de-magic (W-a10) + packets atomic writes (T-c3 tail).

T-c7 — "the configured Ollama model is not pulled" (HTTP 404) used to be
handled THREE different ways (typed raise in the providers, generic
WARNING→None in packets, silent generic catch in the TTS normalizer), each
with a DIFFERENT message. V18.20.4.12 unifies detection + message in the new
``core/llm/model_errors.py`` (stdlib-only leaf module):

  - ``ModelNotFound404Error`` moved there from ``core/llm/retry.py``
    (constructor + message byte-identical; retry + ollama_provider re-export).
  - ``model_not_found_hint(model)`` — THE canonical actionable message.
  - ``is_model_not_found(status, text)`` — tolerant detector for call sites
    that only have a response status and/or body.

W-a10 — the qwythos model literals are de-magicked into
``core/llm/model_taxonomy.py`` constants (``RIG_FALLBACK_MODEL`` — the
working case-sensitive ``-empero-v3`` tag; ``KNOWN_BAD_MODEL_ALIASES`` — the
two tags that 404), and every default site (packets generator, claim
extractor retry, 3 Qt dialogs/view) now references the constant instead of a
raw literal.

This file pins:
  1. model_errors unit semantics (hint format, detector table, constructor).
  2. Import-compat: retry / ollama_provider / model_errors expose ONE class.
  3. ollama_provider: raw HTTP 404 → typed ModelNotFound404Error whose
     message carries the ``ollama pull`` hint (driven end-to-end with a
     monkeypatched safe_ollama_request, test_retry.py trigger style).
  4. packets generator _call_llm: local+404 → canonical pull-hint WARNING,
     500 / cloud-404 → generic WARNING (pull advice is wrong for OpenRouter),
     None either way, no retry on HTTP errors (_FakeSession pattern from
     tests/test_v1820411_p3_llm_transport.py).
  5. TTS normalizer: 404 → canonical pull-hint WARNING *before*
     raise_for_status, deterministic fallback still applies (driven for
     real — the TextNormalizer harness is stdlib-light).
  6. The taxonomy constants (exact values, __all__, RIG ∉ KNOWN_BAD) and
     source-pins for every de-magicked site (claim_extractor retry, packets
     default, the 3 Qt dialogs/view — PySide6 is NOT installed, so those are
     source-pins per the test_deadline_watchdog.py precedent).
  7. Packets atomic writes: zero ``.write_text(`` calls remain in
     generator.py (all 4 sites → utils.atomic_io.atomic_write_text).

Run: ``python3 -m pytest tests/test_v1820412_c_llm_errors.py --no-cov -q``
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import pytest
import requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.model_errors import (
    ModelNotFound404Error,
    is_model_not_found,
    model_not_found_hint,
)

_REPO = _project_root


# ═══════════════════════════════════════════════════════════════════════════
# House helpers
# ═══════════════════════════════════════════════════════════════════════════


def _strip_comments(src: str) -> str:
    """Comment-free source (house pattern — tests/test_v1820411_p3_llm_transport.py)."""
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        line = re.sub(r"\s+#.*$", "", line)
        out.append(line)
    return "\n".join(out)


def _src(rel: str, *, comments: bool = True) -> str:
    text = (_REPO / rel).read_text(encoding="utf-8")
    return text if comments else _strip_comments(text)


class _FakeResp:
    """Minimal requests-like response that raises on raise_for_status."""

    def __init__(self, status: int, body: str = "") -> None:
        self.status_code = status
        self.text = body
        self.closed = False

    def json(self) -> dict:
        if self.text:
            return {"error": self.text}
        return {}

    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError(
            f"{self.status_code} Client Error: error for url http://localhost:11434/api/generate",
            response=self,
        )

    def iter_lines(self, decode_unicode: bool = True):  # pragma: no cover — 404 path never streams
        return iter([])

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    """Pooled-session stand-in (test_v1820411_p3_llm_transport.py pattern)."""

    def __init__(self, status: int, body: str = "") -> None:
        self._resp_factory = lambda: _FakeResp(status, body)
        self.calls: list[str] = []

    def post(self, url: str, **kwargs) -> _FakeResp:
        self.calls.append(url)
        return self._resp_factory()


class _FakeSettings:
    """Settings stand-in that returns the DEFAULT for every key — makes the
    endpoint/provider routing deterministic regardless of the rig's real
    settings.json (the generator imports Settings *inside* _call_llm)."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def get(self, key: str, default=None):
        return default


# ═══════════════════════════════════════════════════════════════════════════
# 1. model_not_found_hint + ModelNotFound404Error constructor semantics
# ═══════════════════════════════════════════════════════════════════════════


class TestHintAndConstructor:
    def test_hint_exact_format(self) -> None:
        """The canonical message, byte-exact (em-dash + backticks matter —
        existing tests across the tree pin 'ollama pull' inside it)."""
        assert model_not_found_hint("mymodel:latest") == (
            "Model 'mymodel:latest' not found in Ollama (HTTP 404) "
            "— run `ollama pull mymodel:latest`"
        )

    def test_hint_equals_exception_str_without_detail(self) -> None:
        model = "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest"
        assert str(ModelNotFound404Error(model)) == model_not_found_hint(model)

    def test_hint_mentions_pull_command_and_model(self) -> None:
        hint = model_not_found_hint("gemma3:12b")
        assert "ollama pull gemma3:12b" in hint
        assert "404" in hint

    def test_constructor_attrs(self) -> None:
        exc = ModelNotFound404Error("m1:latest", "model not found")
        assert exc.model == "m1:latest"
        assert exc.detail == "model not found"
        # default detail is the empty string
        exc2 = ModelNotFound404Error("m2:latest")
        assert exc2.detail == ""

    def test_message_without_detail(self) -> None:
        assert str(ModelNotFound404Error("m:latest")) == (
            "Model 'm:latest' not found in Ollama (HTTP 404) "
            "— run `ollama pull m:latest`"
        )

    def test_message_with_detail_spliced_before_hint(self) -> None:
        """Pre-move wording (core/llm/retry.py, V18.2.21) kept VERBATIM:
        detail is spliced after the status, BEFORE the pull hint."""
        assert str(ModelNotFound404Error("m:latest", "no such model")) == (
            "Model 'm:latest' not found in Ollama (HTTP 404): no such model "
            "— run `ollama pull m:latest`"
        )

    def test_subclass_of_runtime_error(self) -> None:
        assert issubclass(ModelNotFound404Error, RuntimeError)


# ═══════════════════════════════════════════════════════════════════════════
# 2. is_model_not_found — the recognition table
# ═══════════════════════════════════════════════════════════════════════════


class TestIsModelNotFound:
    @pytest.mark.parametrize(
        "status,text,expected",
        [
            # status == 404 → True regardless of body
            (404, "", True),
            (404, "model 'x' not found", True),
            (404, "some unrelated body", True),
            # status is None → body heuristic: BOTH "model" AND "not found"
            (None, "model xyz not found", True),
            (None, 'error: model "qwen" not found in registry', True),
            (None, "other error", False),          # neither keyword
            (None, "not found", False),            # missing "model"
            (None, "model loaded", False),         # missing "not found"
            (None, "", False),
            # any other explicit status → False even if the body matches
            (500, "model not found", False),
            (429, "model not found", False),
            (200, "", False),
            (200, "model not found", False),
        ],
    )
    def test_table(self, status, text, expected) -> None:
        assert is_model_not_found(status, text) is expected

    def test_body_heuristic_is_case_insensitive(self) -> None:
        assert is_model_not_found(None, "MODEL 'X' NOT FOUND") is True

    def test_none_status_with_none_text(self) -> None:
        # defensive: text=None must not raise (coerced to "")
        assert is_model_not_found(None, None) is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. Import-compat — ONE class behind three module names
# ═══════════════════════════════════════════════════════════════════════════


class TestImportCompat:
    def test_retry_ollama_provider_model_errors_same_class(self) -> None:
        """The V18.2.21→V18.20.4.12 move is invisible: every historical
        import path (async_provider + tests import from retry; the provider
        module itself) resolves to the SAME shared class."""
        from core.llm.model_errors import ModelNotFound404Error as C
        from core.llm.ollama_provider import ModelNotFound404Error as B
        from core.llm.retry import ModelNotFound404Error as A

        assert A is B is C

    def test_exported_in_dunder_all(self) -> None:
        import core.llm.model_errors as me
        import core.llm.retry as retry_mod

        assert "ModelNotFound404Error" in me.__all__
        assert "model_not_found_hint" in me.__all__
        assert "is_model_not_found" in me.__all__
        assert "ModelNotFound404Error" in retry_mod.__all__

    def test_classifier_still_recognizes_shared_class(self) -> None:
        """classify_ollama_exception must keep treating the (moved) class as
        non-retryable — pulling a model is a user action."""
        from core.llm.retry import classify_ollama_exception

        assert classify_ollama_exception(ModelNotFound404Error("m:latest")) is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. OllamaProvider — raw HTTP 404 → typed raise with the pull hint
# ═══════════════════════════════════════════════════════════════════════════


class TestOllamaProvider404:
    def test_404_converts_to_typed_error_with_pull_hint(self, monkeypatch) -> None:
        """End-to-end drive (test_retry.py trigger style: monkeypatch
        safe_ollama_request to raise requests.HTTPError with a fake 404
        response): the provider converts it to ModelNotFound404Error whose
        str() carries the canonical ``ollama pull`` hint.

        ``retry_with_oom_context_halving`` is replaced with a wrapper that is
        SEMANTICALLY TRANSPARENT for non-OOM errors (the real one only catches
        OllamaOOMError — a 404 flows through it identically); it captures the
        typed exception so the raise can be asserted even though complete()'s
        outer handler (V11.17 contract) catches it and returns None.
        """
        from core.llm.ollama_provider import OllamaProvider

        calls = {"n": 0}

        def _raise_404(*args, **kwargs):
            calls["n"] += 1
            raise requests.exceptions.HTTPError(
                "404 Client Error: Not Found for url "
                "http://localhost:11434/api/generate",
                response=_FakeResp(404, "model not found"),
            )

        monkeypatch.setattr(
            "core.llm.ollama_provider.safe_ollama_request", _raise_404
        )

        captured: dict = {}

        def _transparent_halving(call_fn, initial_ctx, **kwargs):
            try:
                return call_fn(initial_ctx)
            except ModelNotFound404Error as exc:
                captured["exc"] = exc
                raise

        monkeypatch.setattr(
            "core.llm.ollama_provider.retry_with_oom_context_halving",
            _transparent_halving,
        )
        # deterministic "installed models" listing — no network in the outer handler
        monkeypatch.setattr(
            "utils.network.list_ollama_models", lambda *a, **k: ["qwen2.5:latest"]
        )

        logs: list[tuple[str, str]] = []
        provider = OllamaProvider(
            model="missing-model:latest",
            base_url="http://localhost:11434",
            timeout=30,
            retries=1,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        result = provider.complete("hello")

        # the typed conversion happened, with the canonical message
        exc = captured.get("exc")
        assert isinstance(exc, ModelNotFound404Error), (
            "raw HTTP 404 must surface as ModelNotFound404Error (ollama_provider.py:533)"
        )
        assert exc.model == "missing-model:latest"
        assert exc.detail == "model not found"
        assert "ollama pull missing-model:latest" in str(exc)
        assert "404" in str(exc)
        # non-retryable: exactly ONE HTTP attempt (pulling is a user action)
        assert calls["n"] == 1, "404 must NOT be retried"
        # complete()'s outer contract (V11.17): actionable ERROR logs + None
        assert result is None
        assert any("NOT installed" in m for _, m in logs)
        assert any("ollama pull missing-model:latest" in m for _, m in logs)

    def test_500_not_treated_as_model_not_found(self, monkeypatch) -> None:
        """A non-404 HTTPError must NOT become ModelNotFound404Error — it
        falls to complete()'s generic handler (WARNING + None)."""
        from core.llm.ollama_provider import OllamaProvider

        def _raise_500(*args, **kwargs):
            raise requests.exceptions.HTTPError(
                "500 Server Error", response=_FakeResp(500, "boom")
            )

        monkeypatch.setattr(
            "core.llm.ollama_provider.safe_ollama_request", _raise_500
        )
        monkeypatch.setattr(
            "utils.network.list_ollama_models", lambda *a, **k: []
        )

        logs: list[tuple[str, str]] = []
        provider = OllamaProvider(
            model="m:latest",
            base_url="http://localhost:11434",
            timeout=30,
            retries=0,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        captured: dict = {}

        def _capture(call_fn, initial_ctx, **kwargs):
            try:
                return call_fn(initial_ctx)
            except ModelNotFound404Error as exc:
                captured["exc"] = exc
                raise

        monkeypatch.setattr(
            "core.llm.ollama_provider.retry_with_oom_context_halving", _capture
        )
        result = provider.complete("hello")
        assert result is None
        assert "exc" not in captured, "500 must not convert to ModelNotFound404Error"
        assert any("call failed" in m for _, m in logs)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Packets generator._call_llm — 404 unified into the canonical hint
# ═══════════════════════════════════════════════════════════════════════════


class TestPacketsGenerator404:
    """V18.20.4.12 (T-c7): the NEW ``except requests.exceptions.HTTPError``
    branch (generator.py:992-1006) — previously 404 fell into the blanket
    ``except Exception`` and logged only a raw "404 Client Error" line with
    no pull guidance (cited by the V18.20.4.0 SWOT)."""

    def _make_generator(self):
        from core.outputs.packets.generator import PacketGenerator

        logs: list[tuple[str, str]] = []
        gen = PacketGenerator(request=None, log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        return gen, logs

    def _drive(self, monkeypatch, status: int, provider: str, body: str = ""):
        session = _FakeSession(status, body)
        monkeypatch.setattr("utils.settings.Settings", _FakeSettings)
        monkeypatch.setattr("utils.network.session_for_url", lambda url: session)
        gen, logs = self._make_generator()
        result = gen._call_llm("prompt text", "missing-model:latest", provider, 0.1)
        return result, logs, session

    def test_local_404_logs_canonical_pull_hint_and_returns_none(self, monkeypatch) -> None:
        result, logs, session = self._drive(monkeypatch, 404, "ollama")
        assert result is None, "HTTP errors still return None (control flow preserved)"
        warnings = [m for lvl, m in logs if lvl == "WARNING"]
        assert any(
            "ollama pull missing-model:latest" in m for m in warnings
        ), f"expected the canonical pull hint in WARNING logs, got: {warnings}"
        assert any("not found in Ollama (HTTP 404)" in m for m in warnings)
        # the hint is the model_errors canonical message (single source)
        assert model_not_found_hint("missing-model:latest") in " ".join(warnings)

    def test_local_404_no_retry_single_http_attempt(self, monkeypatch) -> None:
        _, _, session = self._drive(monkeypatch, 404, "ollama")
        assert len(session.calls) == 1, "HTTP errors return None on the FIRST attempt (no retry)"

    def test_local_500_generic_message_no_pull_hint(self, monkeypatch) -> None:
        result, logs, _ = self._drive(monkeypatch, 500, "ollama")
        assert result is None
        warnings = [m for lvl, m in logs if lvl == "WARNING"]
        assert any("LLM call failed" in m for m in warnings), (
            f"non-404 HTTP errors keep the generic WARNING, got: {warnings}"
        )
        assert not any("ollama pull" in m for m in warnings), (
            "pull advice must NOT appear for a 500 (wrong fix for a server error)"
        )

    def test_cloud_404_keeps_generic_message(self, monkeypatch) -> None:
        """``ollama pull`` advice is wrong for OpenRouter/cloud providers —
        the T-c7 branch gates the hint on ``provider != "cloud"``."""
        result, logs, session = self._drive(monkeypatch, 404, "cloud")
        assert result is None
        warnings = [m for lvl, m in logs if lvl == "WARNING"]
        assert any("LLM call failed" in m for m in warnings)
        assert not any("ollama pull" in m for m in warnings), (
            "cloud 404 must keep the raw error — no Ollama-specific advice"
        )
        assert len(session.calls) == 1
        assert session.calls[0].startswith("https://"), (
            "the cloud path must hit the OpenAI-compat base URL, not localhost"
        )

    def test_httperror_branch_wired_to_model_errors(self) -> None:
        """Source pin: the branch exists, imports the shared helpers, gates on
        provider != "cloud", and returns None in both arms."""
        src = _src("core/outputs/packets/generator.py", comments=False)
        assert "from core.llm.model_errors import is_model_not_found, model_not_found_hint" in src
        assert "except requests.exceptions.HTTPError" in src
        assert 'is_model_not_found(_status, str(e))' in src
        assert 'provider != "cloud"' in src


# ═══════════════════════════════════════════════════════════════════════════
# 6. TTS normalizer — 404 hint BEFORE raise_for_status, fallback intact
# ═══════════════════════════════════════════════════════════════════════════


class TestTtsNormalizer404:
    def _make_normalizer(self):
        from core.tts.normalizer import TextNormalizer

        logs: list[tuple[str, str]] = []
        norm = TextNormalizer(
            endpoint="http://localhost:11434/v1",
            api_key="",
            model="missing-model:latest",
            context_mode="segment",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        return norm, logs

    def test_404_logs_canonical_hint_then_falls_back(
        self, monkeypatch, caplog
    ) -> None:
        norm, logs = self._make_normalizer()
        session = _FakeSession(404, "model not found")
        monkeypatch.setattr("core.tts.normalizer.session_for_url", lambda url: session)

        with caplog.at_level(logging.WARNING, logger="core.tts.normalizer"):
            result = norm.normalize("کتاب ۵ صفحه", "fa")

        # the canonical pull hint hit the LOGGER (module logger, not just the
        # dialog callback) before raise_for_status raised
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "ollama pull missing-model:latest" in m for m in warning_texts
        ), f"expected the canonical hint at WARNING, got: {warning_texts}"
        assert any("falling back to deterministic" in m for m in warning_texts)
        # deterministic fallback STILL applies (control flow unchanged):
        # Persian numeral ۵ → پنج
        assert "پنج" in result
        # the segment POST went through the pooled session (single attempt)
        assert len(session.calls) == 1

    def test_500_no_pull_hint(self, monkeypatch, caplog) -> None:
        norm, _ = self._make_normalizer()
        monkeypatch.setattr(
            "core.tts.normalizer.session_for_url",
            lambda url: _FakeSession(500, "boom"),
        )
        with caplog.at_level(logging.WARNING, logger="core.tts.normalizer"):
            result = norm.normalize("کتاب ۵ صفحه", "fa")
        # fallback still applies …
        assert "پنج" in result
        # … but no Ollama-specific pull advice for a 500
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert not any("ollama pull" in m for m in warning_texts)

    def test_hint_precedes_raise_for_status_source_pin(self) -> None:
        """Ordering pin: the is_model_not_found WARNING is logged BEFORE
        raise_for_status raises (otherwise the generic _normalize_chunk
        handler would swallow it first)."""
        src = _src("core/tts/normalizer.py", comments=False)
        check_idx = src.find("if is_model_not_found(resp.status_code):")
        raise_idx = src.find("resp.raise_for_status()")
        assert check_idx > 0, "normalizer must check is_model_not_found on the POST response"
        assert raise_idx > check_idx, "the 404 WARNING must fire BEFORE raise_for_status"

    def test_api_tags_discovery_failure_stays_debug(self) -> None:
        """The /api/tags auto-discovery failure handler stays at DEBUG (an
        unreachable daemon / wrong URL is not the model-missing case — a
        listing endpoint doesn't 404 for an unpulled model) — T-c7 brief."""
        src = _src("core/tts/normalizer.py")
        # the explanatory T-c7 comment documents WHY it stays DEBUG
        assert "V18.20.4.12 (T-c7): /api/tags discovery failure" in src
        tags_idx = src.find('_tags_url = f"{s.get_ollama_url()}/api/tags"')
        assert tags_idx > 0, "the /api/tags discovery call must exist"
        debug_idx = src.find('logger.debug("ignored %s: %s"', tags_idx)
        assert debug_idx > tags_idx, "the discovery failure handler must be a logger.debug"
        region = src[tags_idx : debug_idx + 200]
        assert "logger.warning" not in region, (
            "/api/tags discovery failure must stay DEBUG (Ollama-down ≠ model-missing)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 7. model_taxonomy constants (W-a10)
# ═══════════════════════════════════════════════════════════════════════════


class TestTaxonomyConstants:
    def test_rig_fallback_model_value(self) -> None:
        from core.llm.model_taxonomy import RIG_FALLBACK_MODEL

        assert RIG_FALLBACK_MODEL == (
            "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest"
        )

    def test_known_bad_model_aliases_value(self) -> None:
        from core.llm.model_taxonomy import KNOWN_BAD_MODEL_ALIASES

        assert KNOWN_BAD_MODEL_ALIASES == (
            "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest",
            "qwythos-9b-claude-mythos-5-1m-q4_k_m-empero-v3:latest",
        )

    def test_both_exported_in_all(self) -> None:
        import core.llm.model_taxonomy as mt

        assert "RIG_FALLBACK_MODEL" in mt.__all__
        assert "KNOWN_BAD_MODEL_ALIASES" in mt.__all__

    def test_working_tag_not_in_known_bad_list(self) -> None:
        """The WORKING (-empero-v3, case-exact) tag must not be blacklisted —
        this is the W-a10 bug class the dialogs had (defaulting to a 404 tag)."""
        from core.llm.model_taxonomy import KNOWN_BAD_MODEL_ALIASES, RIG_FALLBACK_MODEL

        assert RIG_FALLBACK_MODEL not in KNOWN_BAD_MODEL_ALIASES
        # NOTE (intentional): the lowercase empero entry IS a case-variant of
        # the rig tag — Ollama tags are case-sensitive, so it 404s and belongs
        # in the bad list. What must hold is only that the EXACT working tag
        # is not blacklisted (the W-a10 dialog bug was defaulting to a 404 tag).

    def test_legacy_default_model_untouched(self) -> None:
        """W-a10 must not disturb the V18.20.4.3 unification sentinel."""
        from core.llm.model_taxonomy import LEGACY_DEFAULT_MODEL

        assert LEGACY_DEFAULT_MODEL == "gemma3:12b"


# ═══════════════════════════════════════════════════════════════════════════
# 8. De-magic source pins (claim_extractor, generator default, dialogs)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeMagicSourcePins:
    def test_claim_extractor_retry_uses_constant(self) -> None:
        """The Pass-1 zero-extraction Qwythos retry must use the taxonomy
        constant (a full langextract harness is too heavy — source pin)."""
        src = _src("core/grounding/claim_extractor.py")
        assert "from core.llm.model_taxonomy import RIG_FALLBACK_MODEL" in src
        assert "_qwythos_model = RIG_FALLBACK_MODEL" in src
        # the retry actually SENDS the constant to the backend
        assert '_qwythos_kwargs["model_id"] = _qwythos_model' in src
        # no raw qwythos literal left at the retry site
        code = _strip_comments(src)
        assert "Qwythos-9B" not in code, "raw qwythos literal reintroduced in claim_extractor code"

    def test_generator_default_is_legacy_sentinel(self) -> None:
        """generator.py:697 — was a lowercase qwythos literal that 404s
        (case-sensitive tag); now the LEGACY_DEFAULT_MODEL sentinel."""
        src = _src("core/outputs/packets/generator.py", comments=False)
        assert 's.get("summarisation.model", LEGACY_DEFAULT_MODEL)' in src
        assert "from core.llm.model_taxonomy import LEGACY_DEFAULT_MODEL" in src

    def test_generator_has_no_qwythos_literals(self) -> None:
        code = _strip_comments(_src("core/outputs/packets/generator.py"))
        assert "qwythos" not in code.lower(), (
            "raw qwythos literal reintroduced in packets generator code"
        )

    def test_summarization_dialog_default_uses_constant(self) -> None:
        src = _src("ui_qt/views/service_dialogs/dialogs/summarization_service_dialog.py")
        assert "from core.llm.model_taxonomy import RIG_FALLBACK_MODEL" in src
        assert "_DEFAULT_MODEL = RIG_FALLBACK_MODEL" in src

    def test_transcribe_dialog_combo_uses_constant(self) -> None:
        src = _src("ui_qt/views/service_dialogs/dialogs/transcribe_service_dialog.py")
        assert "from core.llm.model_taxonomy import RIG_FALLBACK_MODEL" in src
        assert "self.llm_combo.addItem(RIG_FALLBACK_MODEL)" in src

    def test_podcast_maker_combo_default_uses_constant(self) -> None:
        src = _src("ui_qt/views/podcast_maker_view.py")
        assert "from core.llm.model_taxonomy import RIG_FALLBACK_MODEL" in src
        code = _strip_comments(src)
        assert '"summarisation.model",' in code
        # the get_setting fallback must be the constant, not a raw tag
        m = re.search(
            r'get_setting\(\s*"summarisation\.model",\s*(RIG_FALLBACK_MODEL)\s*\)', code
        )
        assert m and m.group(1) == "RIG_FALLBACK_MODEL", (
            "podcast maker combo default must fall back to RIG_FALLBACK_MODEL"
        )

    @pytest.mark.parametrize(
        "rel",
        [
            "ui_qt/views/service_dialogs/dialogs/summarization_service_dialog.py",
            "ui_qt/views/service_dialogs/dialogs/transcribe_service_dialog.py",
            "ui_qt/views/podcast_maker_view.py",
        ],
    )
    def test_no_raw_qwythos_literals_in_dialogs(self, rel) -> None:
        """Zero raw "Qwythos-9B-Claude-Mythos" literals in the 3 dialog/view
        files' CODE (comments documenting the known-bad tag are allowed)."""
        code = _strip_comments(_src(rel))
        assert "Qwythos-9B-Claude-Mythos" not in code, (
            f"{rel}: raw qwythos literal reintroduced (use core.llm.model_taxonomy constants)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9. Packets atomic writes (T-c3 tail) — no bare .write_text( remains
# ═══════════════════════════════════════════════════════════════════════════


class TestPacketsAtomicWrites:
    def test_zero_bare_write_text_calls(self) -> None:
        """All 4 output-write sites go through utils.atomic_io.atomic_write_text
        (temp file + fsync + os.replace) — a crash/disk-full mid-write can no
        longer leave a truncated .md behind."""
        code = _strip_comments(_src("core/outputs/packets/generator.py"))
        offenders = re.findall(r"\.write_text\(", code)
        assert not offenders, (
            f"bare .write_text() calls reintroduced in packets generator: {len(offenders)} "
            "(use utils.atomic_io.atomic_write_text)"
        )

    def test_atomic_write_text_imported_and_used(self) -> None:
        src = _src("core/outputs/packets/generator.py", comments=False)
        assert "from utils.atomic_io import atomic_write_text" in src
        assert src.count("atomic_write_text(") >= 4, (
            "expected ≥4 atomic write sites (one-page + 3 packet exports)"
        )
