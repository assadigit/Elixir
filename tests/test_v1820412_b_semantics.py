"""V18.20.4.12 batch B — summarisation-semantic fixes (characterization pins).

Four fixes, all per the V18.20.4.12 batch-B task:

- **O-a4 (Fix 1):** ``scholar_reflection`` ports the additive
  mass-truncation ONE-continuation-retry shape (additive_sections P1-e):
  truncation detected (provider flag OR tag heuristic) → ONE continuation
  call (original prompt + suffix pointing at where the output stopped) →
  ADDITIVE concatenation → truncation re-evaluated on the combined text.
  Still truncated → the existing parse + verdict-qualification path runs
  unchanged; retry crash → fail-open single-parse path (WARNING).
- **W-a11 (Fix 2):** the four remaining UNCONDITIONAL ``/no_think``
  injections (conversion/summarization.py ``_llm_call_fn``,
  translation/translator.py, translation/harakat.py,
  summarisation/simplified_keypoints.py ``_call_ollama``) are gated on the
  Qwen family via the shared ``qwen_no_think`` helper — the directive is a
  Qwen3 soft-switch; for other models it is prompt pollution.
- **W-b15 (Fix 3):** a structured ``ELIXIR_PROGRESS {...}`` JSON line
  (core/common/progress_events.py) is emitted immediately before the human
  "📊 Progress:" line, and the wizard's ``_on_log`` parses it JSON-FIRST
  (the regex paths stay as the old-log fallback).
- **W-a10 part (Fix 4):** dead uppercase entries removed from the
  ``_init_max_workers`` model-size membership test (``model_lower`` is
  lowercased — the uppercase variants could never match). Zero behavior
  change.

Headless-safe: no PySide6 import (Qt sites are source/AST-pinned per the
house pattern, precedent tests/test_deadline_watchdog.py:149-157).
"""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk

from core.common.progress_events import (
    PROGRESS_PREFIX,
    parse_progress_line,
    progress_json_line,
)
from core.llm.call_meta import mark_call_truncated
from core.summarisation.scholar_reflection import scholar_reflection

# ── source paths (house pattern: pins assert source text, no line numbers) ──
_P_SUMMARIZATION = _project_root / "core" / "pipeline" / "conversion" / "summarization.py"
_P_TRANSLATOR = _project_root / "core" / "translation" / "translator.py"
_P_HARAKAT = _project_root / "core" / "translation" / "harakat.py"
_P_SK = _project_root / "core" / "summarisation" / "simplified_keypoints.py"
_P_SUMMARIZER = _project_root / "core" / "summarisation" / "summarizer.py"
# V0.18 (Phase 5.1): the pinned code moved VERBATIM out of summarizer.py —
# the progress-emitter loop to book_outer.py (SummarizerBookMixin), the
# _init_* sub-constructors to summarizer_init.py (SummarizerInitMixin).
_P_BOOK_OUTER = _project_root / "core" / "summarisation" / "book_outer.py"
_P_SUMMARIZER_INIT = _project_root / "core" / "summarisation" / "summarizer_init.py"
_P_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it (house pattern:
    tests/test_v182049_bk1_ui_threading.py)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _method_src(path: Path, class_name: str, method_name: str) -> str:
    """Exact source segment of one method, located by name via AST
    (house pattern — no line-number peeking)."""
    src = _src(path)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    node = next(
        n for n in ast.walk(cls) if isinstance(n, ast.FunctionDef) and n.name == method_name
    )
    seg = ast.get_source_segment(src, node)
    assert seg is not None
    return seg


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1 (O-a4) — scholar gap-fill: one additive continuation retry
# ═══════════════════════════════════════════════════════════════════════════

_SRC_GROUNDED = (
    "Erikson described identity as persistent sameness within oneself "
    "and sharing of essential character."
)


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))

    def warnings(self):
        return [m for m, l in self.calls if l == "WARNING"]

    def infos(self):
        return [m for m, l in self.calls if l == "INFO"]


class _FakePromptManager:
    def render_template(self, name, **kw):
        return f"PROMPT name={name} heading={kw.get('heading')}"


class _ScriptedLLM:
    """call_fast_llm fake: pops one (flag, response) per call — the flag is
    marked on the call_meta ContextVar exactly like the provider layer
    (mark on EVERY response so no stale True can leak)."""

    def __init__(self, script):
        # script: list of (truncated_flag, response_or_Exception)
        self.script = list(script)
        self.calls = []

    def __call__(self, prompt, temperature=None, max_tokens=None, **kw):
        self.calls.append({"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens})
        if not self.script:
            raise AssertionError("unexpected extra LLM call")
        flag, resp = self.script.pop(0)
        mark_call_truncated(flag)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _run_scholar(script, *, text=_SRC_GROUNDED, max_context_tokens=32768):
    llm = _ScriptedLLM(script)
    log = _CapturingLog()
    result = {
        "executive_summary": "e",
        "bullet_points": ["b1"],
        "thorough_summary": "t",
    }
    scholar_reflection(
        "Ch",
        text,
        result,
        max_context_tokens=max_context_tokens,
        language="en",
        temperature=0.7,
        prompt_manager=_FakePromptManager(),
        recover_vram=lambda **kw: None,
        call_fast_llm=llm,
        strip_thinking=lambda t: t,
        log=log,
    )
    return llm, log, result


class TestOa4ScholarContinuationRetry:
    def test_truncated_then_complete_two_calls_combined_parse(self):
        """(a) First response truncated (tag heuristic: reflections opened,
        never closed) → ONE continuation retry → combined text parses with
        BOTH sections closed → gap-fill bullet recovered, NO 'VERDICT
        UNRELIABLE' qualification."""
        first = "<scholar_reflections>- Missing coverage of Erikson\n"
        second = (
            "rest of the analysis\n"
            "</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Erikson described identity as "persistent sameness within '
            'oneself and sharing of essential character"\n'
            "</gap_fill_bullets>"
        )
        llm, log, result = _run_scholar([(False, first), (False, second)])
        assert len(llm.calls) == 2, "exactly one continuation retry"
        assert any("continuation retry" in i for i in log.infos())
        # combined parse: the gap-fill bullet was recovered + grounded
        assert len(result["bullet_points"]) == 2
        assert "Erikson described identity" in result["bullet_points"][1]
        # the verdict is NOT qualified as unreliable
        assert not any("VERDICT UNRELIABLE" in w for w in log.warnings())
        assert not any("dropped the incomplete" in w for w in log.warnings())

    def test_truncated_twice_qualification_preserved(self):
        """(b) Truncated on BOTH attempts (the .3.4 rig shape: cut before
        any section ever closed) → exactly 2 calls, then the EXISTING
        verdict-qualification path runs unchanged."""
        llm, log, result = _run_scholar(
            [
                (False, "<scholar_refle"),  # cut mid-open-tag
                (False, "ctions>none"),  # continuation also cut (no close)
            ]
        )
        assert len(llm.calls) == 2
        # the existing drop/qualification behavior is preserved
        assert any("VERDICT UNRELIABLE" in w for w in log.warnings())
        assert result["scholar_reflections"] == ""
        assert len(result["bullet_points"]) == 1  # nothing added

    def test_non_truncated_exactly_one_call(self):
        """(c) A complete, closed response → exactly 1 call, ZERO retry
        overhead."""
        llm, log, result = _run_scholar(
            [
                (False, "<scholar_reflections>none</scholar_reflections>"),
            ]
        )
        assert len(llm.calls) == 1
        assert not any("continuation retry" in i for i in log.infos())
        assert any("no significant gaps" in i for i in log.infos())

    def test_retry_crash_falls_back_to_single_parse(self):
        """(d) The continuation call RAISES → fail-open: WARNING logged,
        the original single-parse path runs on the FIRST response, no
        crash propagates."""
        llm, log, result = _run_scholar(
            [
                (False, "<scholar_reflections>none"),  # unclosed → truncated
                (False, RuntimeError("ollama died mid-retry")),
            ]
        )
        assert len(llm.calls) == 2
        assert any("continuation retry failed" in w for w in log.warnings())
        # the single-parse path still ran (original verdict qualification)
        assert any("VERDICT UNRELIABLE" in w for w in log.warnings())
        assert result["scholar_reflections"] == ""

    def test_provider_flag_drives_retry_and_clears(self):
        """The provider truncation flag (done_reason=length, ContextVar)
        drives the retry even when the tag heuristic sees closed tags —
        and the flag is re-read AFTER the second call: cleared → the
        COMBINED text is trusted."""
        first = "<scholar_reflections>none</scholar_reflections>"
        second = (
            "\n<gap_fill_bullets>\n"
            '- Erikson described identity as "persistent sameness within '
            'oneself and sharing of essential character"\n'
            "</gap_fill_bullets>"
        )
        llm, log, result = _run_scholar([(True, first), (False, second)])
        assert len(llm.calls) == 2
        assert not any("VERDICT UNRELIABLE" in w for w in log.warnings())
        assert len(result["bullet_points"]) == 2

    def test_provider_flag_persists_after_retry_qualification(self):
        """Provider flag True on BOTH calls → combined still qualified as
        unreliable (the flag is consume-on-read and re-read after the
        second call)."""
        llm, log, result = _run_scholar(
            [
                (True, "<scholar_reflections>none</scholar_reflections>"),
                (True, ""),
            ]
        )
        assert len(llm.calls) == 2
        assert any("VERDICT UNRELIABLE" in w for w in log.warnings())

    def test_retry_empty_response_no_concat(self):
        """An empty continuation response → nothing concatenated, the
        original truncation state stands (existing qualification path)."""
        llm, log, result = _run_scholar(
            [
                (False, "<scholar_reflections>none"),  # unclosed → truncated
                (False, ""),  # empty continuation
            ]
        )
        assert len(llm.calls) == 2
        assert any("VERDICT UNRELIABLE" in w for w in log.warnings())
        assert result["scholar_reflections"] == ""

    def test_continuation_prompt_shape_and_budget(self):
        """The continuation prompt is the ORIGINAL prompt plus a short
        suffix: continue where the output stopped, do not repeat, close
        open tags — and the tail of the partial output is included so the
        model knows where it stopped. max_tokens stays 6144 on BOTH calls."""
        first = "<scholar_reflections>- Missing coverage of Erikson\n"
        second = "</scholar_reflections>"
        llm, log, result = _run_scholar([(False, first), (False, second)])
        assert len(llm.calls) == 2
        orig, cont = llm.calls[0]["prompt"], llm.calls[1]["prompt"]
        assert cont.startswith(orig), "continuation prompt must be the original prompt + suffix"
        assert "CONTINUATION REQUEST" in cont
        assert "do NOT repeat" in cont
        assert "close all open section tags" in cont
        assert cont.endswith(first), "the partial output tail must be included"
        assert llm.calls[0]["max_tokens"] == 6144
        assert llm.calls[1]["max_tokens"] == 6144
        # ONE retry max — the script has no third response; a third call
        # would have raised AssertionError inside the fake.
        assert len(llm.calls) == 2


# ═══════════════════════════════════════════════════════════════════════════
# V0.20.2 (Quality Campaign, conversion-log audit Defect L2) — skip the
# O-a4 retry when the scholar prompt is near the context cap
# ═══════════════════════════════════════════════════════════════════════════


class TestV0202SkipOa4RetryNearContextCap:
    """The O-a4 continuation retry is COUNTERPRODUCTIVE when the scholar
    prompt is already near the context cap: the retry prompt = original
    prompt + ~60-token suffix + last 2000 chars of the truncated response,
    so it ALWAYS grows. Near the context cap, the retry hits the CONTEXT
    window (not the output cap) and produces even less output. The V0.18
    rig run (run 20260920-084745-c0874728) showed this: call 6 prompt grew
    13418→14003 tok + output 2125 = 16128 > 16000 num_ctx → done_reason=length
    AGAIN, output dropped (no quotes), 133s wasted. The guard skips the
    retry when the continuation prompt would leave < 25% of the retry's
    max_tokens (1536 of 6144) of output headroom under the context cap.
    Content-agnostic — no chapter-specific thresholds."""

    def test_retry_skipped_when_prompt_near_context_cap(self):
        """When the prompt + continuation overhead + min output room would
        exceed the context cap, the retry is SKIPPED (exactly 1 call, a
        WARNING, and the V18.14.1 batch gap-fill is the fallback).

        The real scholar prompt = the source text (truncated to
        max_src*4 chars) + the FULL summary overview (exec + all bullets
        + thorough) + theorists hint + template. On the V0.18 rig run
        (run 20260920-084745-c0874728) this was 13418 tok against a 16000
        context cap. This test reproduces that shape: a large summary
        overview (the 40-bullet + 800-word-thorough shape that made the
        real prompt near-cap) plus a source text, against
        max_context_tokens=16000. The _FakePromptManager is patched to
        include src_text + summary_overview so the guard sees a
        realistic near-cap prompt."""
        # Large summary overview (the V0.18 rig shape: 40 bullets +
        # 800-word thorough ≈ 9700 tok).
        big_result = {
            "executive_summary": "The chapter synthesizes the scattered literature on identity. "
            * 60,
            "bullet_points": ["Erikson (1956) defined ego identity as persistent sameness. "] * 40,
            "thorough_summary": "The chapter traces identity from Tausk through Blos. " * 320,
        }
        big_text = "Erikson described identity sameness within oneself. " * 1200

        class _BigPromptManager(_FakePromptManager):
            def render_template(self, name, **kw):
                return (
                    f"PROMPT name={name} heading={kw.get('heading')}\nSOURCE:\n"
                    f"{kw.get('src_text', '')}\nSUMMARY_OVERVIEW:\n"
                    f"{kw.get('summary_overview', '')}"
                )

        llm = _ScriptedLLM([(False, "<scholar_reflections>- Missing coverage of Erikson\n")])
        log = _CapturingLog()
        scholar_reflection(
            "Ch",
            big_text,
            big_result,
            max_context_tokens=16000,
            language="en",
            temperature=0.7,
            prompt_manager=_BigPromptManager(),
            recover_vram=lambda **kw: None,
            call_fast_llm=llm,
            strip_thinking=lambda t: t,
            log=log,
        )
        # Exactly 1 call (the primary); the retry was SKIPPED.
        assert len(llm.calls) == 1, (
            "the O-a4 retry must be SKIPPED when the prompt is near the context cap "
            "(V0.20.2 Defect L2: the retry is counterproductive — it grows the prompt "
            "and hits the context window)"
        )
        # The skip WARNING fired.
        assert any("O-a4 retry SKIPPED" in w and "context window" in w for w in log.warnings()), (
            "the V0.20.2 skip WARNING must fire when the retry is counterproductive"
        )

    def test_retry_still_fires_when_prompt_has_room(self):
        """When the context cap is large (32768, the default), the retry
        fires as before — the guard is inert when there is room. This is
        the existing O-a4 behavior, preserved unchanged."""
        first = "<scholar_reflections>- Missing coverage of Erikson\n"
        second = (
            "</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            '- Erikson described identity as "persistent sameness"\n'
            "</gap_fill_bullets>"
        )
        llm, log, result = _run_scholar(
            [(False, first), (False, second)],
            max_context_tokens=32768,  # the default — plenty of room
        )
        assert len(llm.calls) == 2, "the retry must fire when the context cap has room"
        assert any("continuation retry" in i for i in log.infos())
        # the gap-fill bullet was recovered (the existing O-a4 happy path)
        assert len(result["bullet_points"]) == 2

    def test_guard_never_breaks_chapter_on_token_counter_crash(self):
        """If the token counter crashes, the guard degrades to
        _retry_would_overflow=False (the retry fires as before). The
        chapter is never broken by the guard itself."""
        import utils.token_counter as tc_mod

        _orig = tc_mod.count_tokens

        def _boom(_text):
            raise RuntimeError("token counter exploded")

        tc_mod.count_tokens = _boom
        try:
            first = "<scholar_reflections>- Missing coverage of Erikson\n"
            second = "</scholar_reflections>"
            llm, log, result = _run_scholar(
                [(False, first), (False, second)],
                max_context_tokens=16000,
            )
            # The guard crashed → _retry_would_overflow=False → the retry
            # fires (the existing O-a4 path, fail-open).
            assert len(llm.calls) == 2, (
                "a token-counter crash must NOT skip the retry (fail-open: the "
                "guard degrades to _retry_would_overflow=False)"
            )
        finally:
            tc_mod.count_tokens = _orig


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2 (W-a11) — /no_think gated on the Qwen family at the 4 raw sites
# ═══════════════════════════════════════════════════════════════════════════


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, content="ok"):
        self._resp = _FakeResp({"choices": [{"message": {"content": content}}]})
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return self._resp


class TestWa11Translator:
    def test_qwen_model_gets_directive(self, monkeypatch):
        import core.translation.translator as tr

        sess = _FakeSession(content="سلام")
        monkeypatch.setattr(tr, "session_for_url", lambda url: sess)
        t = tr.Translator(endpoint="http://localhost:11434/v1", model="qwen3:8b", no_think=True)
        out = t._call_llm("Hello world", "en", "fa", "", "")
        assert out == "سلام"
        prompt = sess.calls[0]["json"]["messages"][0]["content"]
        assert prompt.endswith(" /no_think")
        assert sess.calls[0]["json"]["model"] == "qwen3:8b"

    def test_non_qwen_model_ships_clean(self, monkeypatch):
        """The DEFAULT translator model (TranslateGemma) no longer gets the
        directive — V18.20.4.12 (W-a11): gated on Qwen — was unconditional."""
        import core.translation.translator as tr

        sess = _FakeSession(content="سلام")
        monkeypatch.setattr(tr, "session_for_url", lambda url: sess)
        t = tr.Translator(
            endpoint="http://localhost:11434/v1", model="translategemma:4b", no_think=True
        )
        t._call_llm("Hello world", "en", "fa", "", "")
        prompt = sess.calls[0]["json"]["messages"][0]["content"]
        assert "/no_think" not in prompt

    def test_no_think_false_never_injects(self, monkeypatch):
        import core.translation.translator as tr

        sess = _FakeSession(content="سلام")
        monkeypatch.setattr(tr, "session_for_url", lambda url: sess)
        t = tr.Translator(model="qwen3:8b", no_think=False)
        t._call_llm("Hello world", "en", "fa", "", "")
        assert "/no_think" not in sess.calls[0]["json"]["messages"][0]["content"]


class TestWa11Harakat:
    def test_qwen_model_gets_directive(self, monkeypatch):
        import core.translation.harakat as hk

        sess = _FakeSession(content="سَلام")
        monkeypatch.setattr(hk, "session_for_url", lambda url: sess)
        hg = hk.HarakatGenerator(
            endpoint="http://localhost:11434/v1", model="qwen3:8b", no_think=True
        )
        hg._call_llm("سلام دنیا")
        prompt = sess.calls[0]["json"]["messages"][0]["content"]
        assert prompt.endswith(" /no_think")

    def test_non_qwen_model_ships_clean(self, monkeypatch):
        import core.translation.harakat as hk

        sess = _FakeSession(content="سَلام")
        monkeypatch.setattr(hk, "session_for_url", lambda url: sess)
        hg = hk.HarakatGenerator(model="translategemma:4b", no_think=True)
        hg._call_llm("سلام دنیا")
        assert "/no_think" not in sess.calls[0]["json"]["messages"][0]["content"]

    def test_override_model_gates_the_call_not_self_model(self, monkeypatch):
        """The fallback retry's ``model_override`` is the model THIS call
        uses — the gate must follow it, not ``self.model``."""
        import core.translation.harakat as hk

        sess = _FakeSession(content="سَلام")
        monkeypatch.setattr(hk, "session_for_url", lambda url: sess)
        hg = hk.HarakatGenerator(model="translategemma:4b", no_think=True)
        hg._call_llm("سلام دنیا", model_override="qwen3:8b")
        prompt = sess.calls[0]["json"]["messages"][0]["content"]
        assert prompt.endswith(" /no_think")
        assert sess.calls[0]["json"]["model"] == "qwen3:8b"


class TestWa11SimplifiedKeypoints:
    @staticmethod
    def _ollama_builder(model):
        # House harness: object.__new__ skips ModelManager/Settings
        # (precedent: tests/test_v182048_p6_perf_polish.py _ollama_builder).
        from core.summarisation.simplified_keypoints import (
            SimplifiedKeypointsBuilder,
        )

        b = object.__new__(SimplifiedKeypointsBuilder)
        b.provider = "ollama"
        b.model = model
        b.temperature = 0.1
        b.max_output_tokens_per_batch = 4096
        b.retries = 1
        b.timeout = 420
        b.log = lambda msg, level="INFO": None
        b.ollama_base_url = "http://localhost:11434"

        class _MM:
            def model_exists(self, m):
                return True

        class _Req:
            summarisation_max_context_tokens = 8192

        b.model_manager = _MM()
        b.request = _Req()
        return b

    def test_qwen_model_gets_directive(self, monkeypatch):
        """The Qwen counterpart of the updated pin in
        test_v182048_p6_perf_polish.py (which now asserts the non-Qwen
        clean prompt)."""
        import core.summarisation.simplified_keypoints as sk

        captured = {}

        def _capture(method, url, json=None, timeout=None):
            captured.update(payload=json, timeout=timeout)
            return _FakeResp({"response": "  ok  "})

        monkeypatch.setattr(sk, "safe_ollama_request", _capture)
        b = self._ollama_builder("qwen3:8b")
        assert b._call_ollama("hello", no_think=True, max_predict=512) == "ok"
        assert captured["payload"]["prompt"] == "hello /no_think"
        assert captured["payload"]["model"] == "qwen3:8b"


class TestWa11SourcePins:
    """conversion/summarization.py's ``_llm_call_fn`` is nested inside the
    900-line run_summarization orchestration — not headless-drivable, so
    the site is source-pinned (house precedent:
    tests/test_deadline_watchdog.py:149-157)."""

    def test_summarization_llm_call_fn_uses_helper(self):
        src = _strip_comments(_src(_P_SUMMARIZATION))
        assert "from core.summarisation.filter_thinking import qwen_no_think" in src
        assert "qwen_no_think(prompt, _summ_model)" in src
        # the raw unconditional injection is gone
        assert '"/no_think\\n\\n" + prompt' not in src

    def test_no_raw_no_think_literals_remain(self):
        """None of the four formerly-raw sites may inject a /no_think
        string literal directly (they must go through the shared helper).
        Scans CODE only — the W-a11 fix-documentation comments quote the
        old literal and are stripped first."""
        for path in (_P_SUMMARIZATION, _P_TRANSLATOR, _P_HARAKAT, _P_SK):
            src = _strip_comments(_src(path))
            assert '"/no_think' not in src, (
                f"{path.name}: raw /no_think literal must be gone (use qwen_no_think)"
            )
            assert "qwen_no_think(" in src, f"{path.name}: the shared helper must be wired"

    def test_empty_retry_nudge_untouched(self):
        """The empty-response nudge-retry logic at the summarization site
        is byte-identical (still appends to _actual_prompt)."""
        src = _src(_P_SUMMARIZATION)
        assert "Please output the response now." in src


# ═══════════════════════════════════════════════════════════════════════════
# Fix 3 (W-b15) — structured progress line: emitter + JSON-first parser
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressEventsPure:
    def test_round_trip(self):
        line = progress_json_line(3, 12, 31, 1204)
        assert line.startswith(PROGRESS_PREFIX)
        d = parse_progress_line(line)
        assert d == {
            "done": 3,
            "total": 12,
            "bullets": 31,
            "exec_chars": 1204,
            "chapter_done": True,
        }

    def test_compact_separators_and_keys(self):
        line = progress_json_line(1, 2, 3, 4)
        payload = line[len(PROGRESS_PREFIX) :]
        assert ", " not in payload and ": " not in payload, "compact JSON (separators=(',', ':'))"
        assert '"chapter_done":true' in payload

    def test_malformed_json_returns_none(self):
        assert parse_progress_line("ELIXIR_PROGRESS {not json") is None
        assert parse_progress_line("ELIXIR_PROGRESS ") is None

    def test_non_dict_json_returns_none(self):
        assert parse_progress_line("ELIXIR_PROGRESS [1,2,3]") is None
        assert parse_progress_line("ELIXIR_PROGRESS 42") is None

    def test_non_matching_lines_return_none(self):
        assert parse_progress_line("  📊 Progress: 3/12 done | 31 bullets") is None
        assert parse_progress_line("✅ Chapter 3/12: 'The self…' complete") is None
        assert parse_progress_line("") is None
        assert parse_progress_line(None) is None  # type: ignore[arg-type]

    def test_prefix_strictness(self):
        """Documented contract: exact prefix match on the lstrip()'d line —
        leading whitespace is tolerated, any OTHER prefix (emoji, prose) is
        NOT."""
        line = progress_json_line(1, 1, 5, 100)
        assert parse_progress_line("   " + line) is not None  # leading ws ok
        assert parse_progress_line("📊 " + line) is None  # emoji prefix NO
        assert parse_progress_line("x" + line) is None  # any prefix NO

    def test_unusable_dict_is_returned_as_is(self):
        """A hand-crafted line whose JSON parses but lacks int keys is
        returned as-is — the CALLER validates and falls back (the wizard
        treats it as no-match)."""
        d = parse_progress_line('ELIXIR_PROGRESS {"done":"x"}')
        assert d == {"done": "x"}


class TestWb15EmitterSourcePin:
    def test_summarizer_imports_and_calls_progress_json_line(self):
        # V0.18 (Phase 5.1): moved VERBATIM to book_outer.py — pin follows.
        src = _src(_P_BOOK_OUTER)
        assert "from core.common.progress_events import progress_json_line" in src
        assert "progress_json_line(idx, total, _bp_count, _exec_len)" in src

    def test_structured_line_emitted_immediately_before_human_line(self):
        # V0.18 (Phase 5.1): moved VERBATIM to book_outer.py — pin follows
        # (both lines moved together).
        src = _src(_P_BOOK_OUTER)
        structured = src.index("progress_json_line(idx, total, _bp_count, _exec_len)")
        human = src.index('f"  📊 Progress: {idx}/{total} done | "')
        assert structured < human, "the structured line must be logged BEFORE the human line"

    def test_human_line_byte_identical(self):
        """The human '📊 Progress:' line is pinned byte-identical (logs and
        the regex fallback parse it)."""
        # V0.18 (Phase 5.1): moved VERBATIM to book_outer.py — pin follows.
        src = _src(_P_BOOK_OUTER)
        assert 'f"  📊 Progress: {idx}/{total} done | "' in src
        assert 'f"{_bp_count} bullets | {_exec_len:,} chars exec summary",' in src


class TestWb15ParserSourcePin:
    def test_wizard_imports_parse_progress_line(self):
        src = _src(_P_WIZARD)
        assert "from core.common.progress_events import parse_progress_line" in src

    def test_json_first_before_regex_fallback(self):
        body = _method_src(_P_WIZARD, "WizardView", "_on_log")
        structured = body.index("parse_progress_line(msg)")
        regex = body.index("_PROGRESS_RE.search(msg)")
        assert structured < regex, "the structured parse must run BEFORE the regex fallback"

    def test_regex_paths_gated_on_no_structured_match(self):
        """When the structured line matches, the regex paths are SKIPPED
        for that message; None → the existing regex fallbacks run
        unchanged."""
        body = _method_src(_P_WIZARD, "WizardView", "_on_log")
        # no per-line imports on the hot path (W-b14 invariant kept) —
        # comments stripped: the W-b14 comment quotes ``import re``.
        assert "import re" not in _strip_comments(body)
        assert '_pd is None and hasattr(self.step9, "quality_label")' in body
        assert '_pd is None and hasattr(self.step9, "chapter_status_label")' in body
        # the fallback regexes themselves are untouched
        assert "_PROGRESS_RE.search(msg)" in body
        assert "_CHAPTER_RE.search(msg)" in body

    def test_structured_branch_reuses_the_display_formats_verbatim(self):
        """The JSON-first branch updates BOTH labels with the EXACT format
        strings the regex fallback uses (display parity)."""
        body = _method_src(_P_WIZARD, "WizardView", "_on_log")
        quality_fmt = 'f"Quality: {done}/{total} chapters done | {bullets} bullets total"'
        chapter_fmt = 'f"Chapters: {done}/{total} " + "✅" * min(done, 8) + "🔄"'
        assert body.count(quality_fmt) >= 2, (
            "both the structured branch AND the regex fallback must use "
            "the identical quality format"
        )
        assert body.count(chapter_fmt) >= 2, (
            "both the structured branch AND the regex fallback must use "
            "the identical chapter format"
        )

    def test_display_parity_with_emitted_line(self):
        """End-to-end (pure): the emitted structured line drives the same
        displayed strings the human-line regex parse produced."""
        line = progress_json_line(3, 12, 31, 1204)
        d = parse_progress_line(line)
        done, total, bullets = d["done"], d["total"], d["bullets"]
        assert (
            f"Quality: {done}/{total} chapters done | {bullets} bullets total"
        ) == "Quality: 3/12 chapters done | 31 bullets total"
        assert (
            f"Chapters: {done}/{total} " + "✅" * min(done, 8) + "🔄"
        ) == "Chapters: 3/12 ✅✅✅🔄"


# ═══════════════════════════════════════════════════════════════════════════
# Fix 4 (W-a10 part) — dead uppercase entries in _init_max_workers
# ═══════════════════════════════════════════════════════════════════════════


class TestWa10DeadUppercaseEntries:
    def test_lowercase_only_tuples_pinned(self):
        # V0.18 (Phase 5.1): _init_max_workers moved VERBATIM to
        # summarizer_init.py (SummarizerInitMixin) — pin follows.
        body = _method_src(_P_SUMMARIZER_INIT, "SummarizerInitMixin", "_init_max_workers")
        # V18.20.4.12 (W-a10): dropped dead uppercase entries — model_lower
        # is lowercased
        assert 'for k in ("14b", "32b", "70b")' in body
        assert 'for k in ("9b", "8b", "12b", "13b")' in body
        # the dead uppercase variants are gone
        for dead in ('"14B"', '"32B"', '"70B"', '"9B"', '"8B"', '"12B"', '"13B"'):
            assert dead not in body, f"dead entry {dead} must be gone"

    def test_uppercase_entries_could_never_match(self):
        """Proof the removal is behavior-neutral: model_lower is
        ``.lower()``ed, so an uppercase needle can never appear in it."""
        for model in ("Qwen2.5:14B", "llama3:70B", "gemma3:12B"):
            model_lower = model.lower()
            assert "14B" not in model_lower
            assert "70B" not in model_lower
            assert "12B" not in model_lower

    def test_membership_semantics_unchanged(self):
        """The lowercase-only tuples classify the same models the old
        (mixed-case) tuples did — every model the uppercase entries could
        have matched is already covered by its lowercase twin."""
        t1 = ("14b", "32b", "70b")
        t2 = ("9b", "8b", "12b", "13b")
        old_t1 = ("14b", "14B", "32b", "32B", "70b", "70B")
        old_t2 = ("9b", "9B", "8b", "8B", "12b", "12B", "13b", "13B")
        for model in (
            "qwen2.5:14b",
            "Qwen2.5:14B",
            "llama3:70b",
            "gemma2:9b",
            "qwen3:8b",
            "gemma3:12b",
            "mistral:7b",
        ):
            m = model.lower()
            assert any(k in m for k in t1) == any(k in m for k in old_t1)
            assert any(k in m for k in t2) == any(k in m for k in old_t2)
