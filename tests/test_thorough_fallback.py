"""V18.11 (Phase 5 Stage 3, Batch 2.3) — thorough_fallback characterization tests.

Byte-for-byte stability gate for ``call_dedicated_thorough_with_fallback``
extracted from ``Summarizer._call_dedicated_thorough_with_fallback``. Uses
mocked ``call_llm`` / ``strip_thinking`` / ``deadline_exceeded`` to capture
the 3-attempt + synthetic-fallback flow.

Run: pytest tests/test_thorough_fallback.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest

# Phase 2 (task 2.5): every test in this file exercises the REAL 3-attempt
# retry ladder, which sleeps its backoff (~3 s per test, ~38 s for the file)
# — structurally slow, tag the whole module.
pytestmark = pytest.mark.slow

from core.summarisation.thorough_fallback import call_dedicated_thorough_with_fallback


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _make_deps(
    *,
    llm_responses=None,
    strip_result=None,
    deadline_exceeded_returns=False,
    llm_raises=None,
):
    """Build mock deps. llm_responses is a list cycled through (attempt 1, 2, 3).
    strip_thinking defaults to identity."""
    if llm_responses is None:
        llm_responses = []
    responses = list(llm_responses)
    idx = {"i": 0}
    llm_calls = []
    de_calls = []

    def call_llm(prompt, model=None, temperature=None, max_tokens=None, **kw):
        i = idx["i"]
        idx["i"] += 1
        llm_calls.append({"prompt": prompt, "temp": temperature, "max_tokens": max_tokens})
        if llm_raises is not None and i < len(llm_raises) and llm_raises[i]:
            raise llm_raises[i]
        if i < len(responses):
            return responses[i]
        return None

    def strip_thinking(text):
        return strip_result if strip_result is not None else text

    def deadline_exceeded(phase_name):
        de_calls.append(phase_name)
        return deadline_exceeded_returns

    return {
        "call_llm": call_llm,
        "strip_thinking": strip_thinking,
        "deadline_exceeded": deadline_exceeded,
        "_llm_calls": llm_calls,
        "_de_calls": de_calls,
    }


def _common_kwargs(deps):
    return dict(
        max_output_tokens=8192,
        primary_model="test-model",
        temperature=0.7,
        strip_thinking=deps["strip_thinking"],
        call_llm=deps["call_llm"],
        deadline_exceeded=deps["deadline_exceeded"],
        synthetic_fallback_count=0,
        log=_CapturingLog(),
    )


# ── 1. attempt-1 success ──────────────────────────────────────────────────


class TestAttempt1Success:
    def test_attempt1_meets_min_words_returned(self):
        """If attempt 1 returns >= min_words, it's returned immediately and
        the fallback count is unchanged."""
        long_thorough = " ".join([f"word{i}" for i in range(900)]) + "."
        deps = _make_deps(llm_responses=[long_thorough])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1", "b2"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out == long_thorough
        assert count == 0  # no fallback fire
        # Only 1 LLM call (attempt 2 + 3 skipped)
        assert len(deps["_llm_calls"]) == 1

    def test_thorough_summary_tags_extracted(self):
        """If the LLM response contains <thorough_summary>...</thorough_summary>
        tags, the content inside is extracted (the _parse_thorough inner fn)."""
        inner = " ".join([f"word{i}" for i in range(900)]) + "."
        tagged = f"<think>planning</think><thorough_summary>{inner}</thorough_summary>tail"
        deps = _make_deps(llm_responses=[tagged])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out == inner  # the tag content, stripped of thinking + tags
        assert count == 0


# ── 2. multi-attempt escalation ──────────────────────────────────────────


class TestAttemptEscalation:
    def test_attempt2_used_when_attempt1_short(self):
        """If attempt 1 is short (< min_words) and attempt 2 is longer, attempt
        2 is returned."""
        short = "short response."
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        deps = _make_deps(llm_responses=[short, long_t])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out == long_t
        assert count == 0
        # 2 LLM calls (attempt 1 + 2; attempt 3 skipped since attempt 2 met min)
        assert len(deps["_llm_calls"]) == 2

    def test_attempt3_greedy_temp_used_when_2_fail(self):
        """If attempts 1 + 2 both fail/short, attempt 3 runs (V0.5.2:
        at the user's temperature, NOT 0.0 greedy) and is returned if
        it succeeds."""
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        deps = _make_deps(llm_responses=[None, None, long_t])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out == long_t
        assert count == 0
        # 3 LLM calls; attempt 3 used the user's temperature (V0.5.2: was 0.0)
        assert len(deps["_llm_calls"]) == 3
        assert deps["_llm_calls"][2]["temp"] == 0.35  # V0.5.2: temperature * 0.5 (was 0.0)

    def test_best_effort_kept_when_under_min_words(self):
        """If all 4 attempts (V0.4.38 F2 added the 4th length-directive
        attempt) return something but all < min_words, the best (longest)
        is kept and a WARNING is logged (best-effort)."""
        best = " ".join([f"w{i}" for i in range(100)]) + "."  # 100 words < 800
        deps = _make_deps(llm_responses=["short.", "medium response.", best, best])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # best = the 100-word one (longest of the 4)
        assert out == best
        assert count == 0  # no synthetic fallback
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("best-effort" in w for w in warnings)


# ── 3. deadline skip ──────────────────────────────────────────────────────


class TestDeadlineSkip:
    def test_deadline_exceeded_skips_attempts_2_and_3(self):
        """When deadline_exceeded returns True, attempts 2 and 3 are skipped
        (only attempt 1 runs). If attempt 1 failed, we fall straight to the
        synthetic fallback."""
        deps = _make_deps(llm_responses=[None], deadline_exceeded_returns=True)
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec summary text here",
            ["bullet one", "bullet two"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        # Only attempt 1 ran (attempts 2 + 3 skipped due to deadline)
        assert len(deps["_llm_calls"]) == 1
        # deadline_exceeded was called for attempt 2 and 3
        assert len(deps["_de_calls"]) == 2
        # Synthetic fallback fired (exec + bullets)
        assert out is not None
        assert "exec summary text here" in out
        assert "bullet one" in out
        assert count == 1


# ── 4. synthetic fallback ────────────────────────────────────────────────


class TestSyntheticFallback:
    def test_all_attempts_fail_synthesizes_from_exec_and_bullets(self):
        """When all 3 attempts fail (None), the synthetic fallback is built
        from exec_sum + bullets (as '• bullet.' prose), and the fallback
        count increments by 1."""
        deps = _make_deps(llm_responses=[None, None, None])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "The executive summary text.",
            ["Bullet one.", "Bullet two."],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out is not None
        assert "The executive summary text." in out
        assert "Bullet one." in out
        assert "Bullet two." in out
        assert count == 1  # fallback fired once

    def test_synthetic_escalation_at_two_fires(self):
        """When the fallback count crosses >=2 (this fire makes it 2), the
        escalated WARNING is logged (SYSTEMATICALLY failing + diagnostics)."""
        deps = _make_deps(llm_responses=[None, None, None])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        kw["synthetic_fallback_count"] = 1
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec text",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        assert count == 2  # was 1, now 2
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        # The escalated WARNING mentions SYSTEMATICALLY + diagnostics
        assert any("SYSTEMATICALLY" in w for w in warnings)
        assert any("Modelfile" in w for w in warnings)

    def test_no_exec_no_bullets_returns_none(self):
        """If all attempts fail AND exec_sum + bullets are empty, returns
        (None, fallback_count_unchanged) — no synthetic fallback possible."""
        deps = _make_deps(llm_responses=[None, None, None])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "",
            [],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out is None
        assert count == 0  # no synthetic fallback fired (nothing to synthesize from)

    def test_bullets_only_synthetic_when_exec_empty(self):
        """If exec_sum is empty but bullets exist, the synthetic fallback is
        built from bullets only."""
        deps = _make_deps(llm_responses=[None, None, None])
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "",
            ["Bullet one.", "Bullet two."],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out is not None
        assert "Bullet one." in out
        assert "Bullet two." in out
        assert count == 1


# ── 5. byte-for-byte stability ────────────────────────────────────────────


class TestByteForByte:
    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same (out, count) across calls."""
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."

        def _run():
            deps = _make_deps(llm_responses=[long_t])
            return call_dedicated_thorough_with_fallback(
                "p",
                "e",
                ["b"],
                min_words=800,
                **{k: v for k, v in _common_kwargs(deps).items()},
            )

        assert _run() == _run()

    def test_returns_tuple_of_optional_str_and_int(self):
        """Returns (Optional[str], int) — the delegate unpacks this."""
        deps = _make_deps(llm_responses=[" ".join([f"w{i}" for i in range(900)]) + "."])
        out, count = call_dedicated_thorough_with_fallback(
            "p",
            "e",
            ["b"],
            min_words=800,
            **{k: v for k, v in _common_kwargs(deps).items()},
        )
        assert out is None or isinstance(out, str)
        assert isinstance(count, int)

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        deps = _make_deps(llm_responses=[long_t])
        kw = _common_kwargs(deps)
        kw.pop("log")
        out, count = call_dedicated_thorough_with_fallback(
            "p",
            "e",
            ["b"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        assert out == long_t


# ── 6. V18.12.1 hotfix: call_llm raises → falls through (no crash) ────────


class TestCallLlmRaisesFallthrough:
    """V18.12.1 hotfix: if call_llm RAISES (e.g. Ollama 500 that exhausts the
    retry_llm_call decorator), the 3-attempt fallback must catch the exception
    and fall through to the next attempt / synthetic fallback — NOT crash the
    conversion. This was a pre-existing gap in V18.10.1 (the 3-attempt fallback
    only handled call_llm returning None, not call_llm raising). The V18.12.0
    golden-master run hit this when Ollama 500'd after the 7-min primary call."""

    def test_attempt1_raises_falls_through_to_attempt2_then_synthetic(self):
        """Attempt 1 raises HTTPError → caught → attempt 2 also raises → caught
        → attempt 3 also raises → caught → synthetic fallback from exec+bullets.
        The conversion must NOT crash; the synthetic thorough is the last resort."""
        deps = _make_deps(
            llm_responses=[None, None, None],
            llm_raises=[
                RuntimeError("500 Server Error: Internal Server Error"),
                RuntimeError("500 Server Error: Internal Server Error"),
                RuntimeError("500 Server Error: Internal Server Error"),
            ],
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "The executive summary text.",
            ["Bullet one.", "Bullet two."],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # All 3 attempts raised → synthetic fallback built from exec + bullets
        assert out is not None
        assert "The executive summary text." in out
        assert "Bullet one." in out
        assert "Bullet two." in out
        assert count == 1  # synthetic fallback fired once
        # 3 WARNINGs about the crashes (one per attempt)
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        crash_warnings = [w for w in warnings if "crashed" in w and "falling through" in w]
        assert len(crash_warnings) == 3, (
            f"expected 3 crash warnings, got {len(crash_warnings)}: {crash_warnings}"
        )

    def test_attempt1_raises_attempt2_succeeds(self):
        """Attempt 1 raises → caught → attempt 2 succeeds → attempt 2's thorough
        is returned. The exception from attempt 1 does NOT prevent attempt 2."""
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        deps = _make_deps(
            llm_responses=[None, long_t, None],  # attempt 2 returns the long thorough
            llm_raises=[
                RuntimeError("500 Server Error"),
                None,  # attempt 2 does NOT raise
                None,
            ],
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # Attempt 2 succeeded → its thorough returned
        assert out == long_t
        assert count == 0  # no synthetic fallback
        # 1 WARNING about attempt 1 crashing
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        crash_warnings = [w for w in warnings if "Attempt 1/3" in w and "crashed" in w]
        assert len(crash_warnings) == 1

    def test_attempt1_raises_attempt2_raises_attempt3_succeeds(self):
        """Attempts 1 + 2 raise → caught → attempt 3 (greedy temp 0.0) succeeds →
        attempt 3's thorough returned. Both exceptions caught, no crash."""
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        deps = _make_deps(
            llm_responses=[None, None, long_t],  # attempt 3 returns the long thorough
            llm_raises=[
                RuntimeError("500 Server Error"),
                ConnectionError("Ollama unreachable"),
                None,  # attempt 3 does NOT raise
            ],
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # Attempt 3 succeeded → its thorough returned
        assert out == long_t
        assert count == 0  # no synthetic fallback
        # 2 WARNINGs about attempts 1 + 2 crashing
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        crash_warnings = [w for w in warnings if "crashed" in w and "falling through" in w]
        assert len(crash_warnings) == 2

    def test_all_attempts_raise_no_exec_no_bullets_returns_none_no_crash(self):
        """All 3 attempts raise AND exec_sum + bullets are empty → returns
        (None, 0) — no synthetic fallback possible, but NO crash."""
        deps = _make_deps(
            llm_responses=[None, None, None],
            llm_raises=[
                RuntimeError("500 Server Error"),
                RuntimeError("500 Server Error"),
                RuntimeError("500 Server Error"),
            ],
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "",
            [],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # No synthetic fallback possible (nothing to synthesize from)
        assert out is None
        assert count == 0  # no synthetic fallback fired
        # 3 WARNINGs about the crashes + 1 WARNING about "all 3 failed"
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        crash_warnings = [w for w in warnings if "crashed" in w and "falling through" in w]
        assert len(crash_warnings) == 3

    def test_http_error_exception_type_preserved_in_log(self):
        """The exception type (e.g. HTTPError) is preserved in the WARNING log
        message so the user can diagnose the root cause (Ollama 500 vs OOM vs etc)."""

        class _FakeHTTPError(RuntimeError):
            """Simulates requests.exceptions.HTTPError from Ollama 500."""

            pass

        deps = _make_deps(
            llm_responses=[None, None, None],
            llm_raises=[_FakeHTTPError("500 Server Error: Internal Server Error")] * 3,
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        call_dedicated_thorough_with_fallback(
            "prompt",
            "exec text",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        crash_warnings = [w for w in warnings if "crashed" in w]
        # The exception type name appears in at least one warning
        assert any("_FakeHTTPError" in w for w in crash_warnings), (
            f"exception type name should appear in warning; got: {crash_warnings}"
        )


# ── V0.4.38 (F2): the 4th length-directive attempt ────────────────────────


class TestV0438F2Attempt4LengthDirective:
    """V0.4.38 (F2): a 4th attempt with a quantified length directive fires
    when attempts 1-3 all return non-empty but < min_words (the V0.4.37
    ch.6 case: best=793 < 800 on all 3 prior attempts → a 31/74 = 42%
    coverage-deficient thorough). The 4th re-prompts with the ACTUAL
    shortfall (the model's best word count + the minimum). Genre-agnostic
    (about LENGTH, not content — Rule 1)."""

    def test_attempt4_recovers_length_when_1_3_persistently_short(self):
        """Attempts 1-3 short (<min_words); attempt 4 (length directive)
        returns >= min_words → the long result is returned."""
        short = " ".join([f"w{i}" for i in range(100)]) + "."  # 100 words < 800
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."  # 900 >= 800
        deps = _make_deps(llm_responses=[short, short, short, long_t])
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # 4 LLM calls; the 4th returned the long result.
        assert len(deps["_llm_calls"]) == 4
        assert out == long_t
        assert count == 0  # no synthetic fallback
        # The 4th prompt carried the quantified length directive.
        assert "Your previous response was only" in deps["_llm_calls"][3]["prompt"]
        assert "100 words" in deps["_llm_calls"][3]["prompt"]
        assert "800" in deps["_llm_calls"][3]["prompt"]
        # The recovery was logged.
        assert any("length-directive recovered" in m for m, _l in cap.calls)

    def test_attempt4_skipped_when_deadline_exceeded(self):
        """When deadline_exceeded returns True, attempt 4 is skipped (the
        best-effort from attempts 1-3 is kept)."""
        short = " ".join([f"w{i}" for i in range(100)]) + "."
        long_t = " ".join([f"w{i}" for i in range(900)]) + "."
        # deadline_exceeded returns True → attempts 2,3,4 all skipped.
        # Only attempt 1 runs (returns short) → best-effort kept.
        deps = _make_deps(
            llm_responses=[short, long_t, long_t, long_t],
            deadline_exceeded_returns=True,
        )
        cap = _CapturingLog()
        kw = _common_kwargs(deps)
        kw["log"] = cap
        out, count = call_dedicated_thorough_with_fallback(
            "prompt",
            "exec",
            ["b1"],
            min_words=800,
            **{k: v for k, v in kw.items()},
        )
        # Only attempt 1 ran (deadline skips 2,3,4); best-effort kept.
        assert len(deps["_llm_calls"]) == 1
        assert out == short
        assert count == 0
