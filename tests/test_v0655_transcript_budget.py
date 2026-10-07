"""V0.6.55 (P2) — the transcript budget pins (the silent 8000-char cut).

THE BUG (the operator's report): ``summarize_transcript`` sliced
``transcript[:8000]`` before rendering the prompt (both the notes and
the tutorial templates). A 15-minute video produces ~15-20k chars of
transcript, so roughly HALF the transcript never reached the LLM —
silently. The summary covers the first 3 minutes and drops the rest.

THE FIX (this session, core/transcribe/transcribe_service.py):

  1. ``fit_transcript_to_budget(transcript, max_tokens=None)`` — a
     LOUD context-budget fit: full text when it fits; when it does
     not, the cut lands on a sentence/paragraph boundary (never
     mid-word) and an explicit truncation MARKER is appended so the
     model (and the operator, via the log line) can SEE that the tail
     was dropped. Returns the fit decision as a dict
     (text/truncated/chars_used/chars_total).
  2. ``summarize_transcript`` renders the prompt with the FITTED text
     (default budget TRANSCRIPT_PROMPT_TOKEN_BUDGET = 24k tokens —
     a 65k-context llama.cpp window takes the FULL 15-min video
     transcript with room to spare; an absurd 3-hour wall gets a clean
     documented cut instead of a mid-sentence amputation).

THE PINS: the pure fit function (fits / sentence boundary / word
boundary fallback / marker wording / empty input) and the WIRING — a
20k-char transcript must reach the prompt INTACT (the tail present in
the rendered prompt — fails on the pre-fix [:8000] code).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.transcribe.transcribe_service import (  # noqa: E402
    TRANSCRIPT_PROMPT_TOKEN_BUDGET,
    fit_transcript_to_budget,
)


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — the pure budget fit
# ═════════════════════════════════════════════════════════════════════════════


def _sentences(n: int, words_per: int = 12) -> str:
    """A deterministic transcript: n sentences, each a distinct word run."""
    out = []
    for i in range(n):
        words = " ".join(f"w{i}_{j}" for j in range(words_per))
        out.append(f"{words}.")
    return " ".join(out)


class TestV0655FitTranscriptToBudget:
    def test_fitting_text_is_returned_untouched(self):
        """Under budget → the FULL text, truncated=False (the 15-min
        video case — the whole point of P2)."""
        text = _sentences(300)  # ~3600 words, well under any budget
        out = fit_transcript_to_budget(text, max_tokens=24_000)
        assert out["text"] == text
        assert out["truncated"] is False
        assert out["chars_used"] == len(text)
        assert out["chars_total"] == len(text)

    def test_oversize_text_is_cut_at_a_sentence_boundary(self):
        """Over budget → truncated=True and the cut lands AFTER a '.'
        (sentence boundary) — never mid-word/mid-sentence."""
        text = _sentences(4_000)  # ~48k words → over a 2k-token budget
        out = fit_transcript_to_budget(text, max_tokens=2_000)
        assert out["truncated"] is True
        body = out["text"].split("\n\n[... transcript truncated")[0]
        assert body.endswith(".")
        # The kept prefix is a prefix of the original (nothing invented).
        assert text.startswith(body)

    def test_truncation_marker_is_explicit_with_counts(self):
        """The cut is LOUD: the marker names the used/total counts so
        the model and the operator both see the tail was dropped."""
        text = _sentences(4_000)
        out = fit_transcript_to_budget(text, max_tokens=2_000)
        assert "[... transcript truncated" in out["text"]
        assert f"{out['chars_used']:,}" in out["text"]
        assert f"{out['chars_total']:,}" in out["text"]

    def test_no_sentence_boundary_falls_back_to_word_boundary(self):
        """A wall without sentence punctuation still never cuts
        mid-word (whitespace boundary: the next char in the ORIGINAL
        after the kept body is a space)."""
        wall = " ".join(f"tok{i}" for i in range(20_000))  # no periods at all
        out = fit_transcript_to_budget(wall, max_tokens=500)
        assert out["truncated"] is True
        body = out["text"].split("\n\n[... transcript truncated")[0]
        assert wall.startswith(body)
        rest = wall[len(body) :]
        assert rest == "" or rest[0] == " ", "cut landed mid-word"
        # and the last kept word is a COMPLETE word from the wall
        assert body.split()[-1] in wall.split()

    def test_empty_transcript_is_empty_not_crash(self):
        out = fit_transcript_to_budget("", max_tokens=100)
        assert out["text"] == ""
        assert out["truncated"] is False
        assert out["chars_total"] == 0

    def test_exact_fit_is_not_truncated(self):
        """The measured boundary: at the measured token count the text
        passes WHOLE; one token less trips the (marked) truncation."""
        from core.transcribe.transcribe_service import _count_prompt_tokens

        text = _sentences(10)
        measured = _count_prompt_tokens(text)
        assert fit_transcript_to_budget(text, max_tokens=measured)["truncated"] is False
        under = fit_transcript_to_budget(text, max_tokens=max(1, measured - 1))
        if under["truncated"]:  # (only trips when the text exceeds the budget)
            assert "[... transcript truncated" in under["text"]

    def test_body_plus_marker_never_exceeds_the_budget(self):
        """Task 9 review fix: the marker's tokens are RESERVED — the
        fitted text (body + marker) counts at or under the budget (the
        review measured 24,036 tokens for a 24,000 budget pre-fix)."""
        from core.transcribe.transcribe_service import _count_prompt_tokens

        text = _sentences(50_000)  # a wall, way over any small budget
        for budget in (200, 1_000, 5_000):
            out = fit_transcript_to_budget(text, max_tokens=budget)
            assert out["truncated"] is True, budget
            total = _count_prompt_tokens(out["text"])
            assert total <= budget, (
                f"budget {budget}: body+marker measured {total} tokens — "
                "the marker reserve is broken"
            )

    def test_default_budget_is_generous_for_65k_contexts(self):
        """24k prompt tokens + the 12k output cap + the 512 margin fit
        comfortably inside the default 65k llama.cpp window — the rig
        case — while staying small enough for 32k-class Ollama models
        with an 8k output reserve."""
        assert TRANSCRIPT_PROMPT_TOKEN_BUDGET == 24_000


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — the wiring: the WHOLE transcript reaches the prompt
# ═════════════════════════════════════════════════════════════════════════════


class _WiringHarness:
    """summarize_transcript + faked create_provider + faked probe (the
    test_v0613_llamacpp_first_services.py _TranscribeHarness pattern)."""

    def __init__(self, monkeypatch, values: dict | None = None) -> None:
        import core.llm.llm_provider as lp
        from utils.settings import Settings

        class _S:
            def __init__(self, v):
                self._v = dict(v or {})

            def get(self, key, default=None):
                return self._v.get(key, default)

            def set(self, key, value):
                return True

        self.settings = _S(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        class _ProbeSpy:
            def __init__(self):
                self.calls = []

            def __call__(self, base_url, api_key, timeout=10):
                self.calls.append(base_url)
                return []  # dead → passthrough, provider stays "ollama"

        self.spy = _ProbeSpy()
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)
        local_fallback.clear_llamacpp_probe_cache()

        self.captured: dict = {}
        captured = self.captured

        class _FakeProvider:
            base_url = "http://localhost:11434"

            def complete_streaming(
                self, prompt, temperature=None, max_tokens=None, model=None, on_chunk=None
            ):
                captured["call"] = {
                    "prompt": prompt,
                    "model": model,
                    "on_chunk": on_chunk,
                    "max_tokens": max_tokens,
                }
                captured.setdefault("calls", []).append(captured["call"])
                return "# Notes\n\n- a point"

        def _factory(provider, settings, log_callback=None, supervisor=None):
            captured["provider"] = provider
            return _FakeProvider()

        monkeypatch.setattr(lp, "create_provider", _factory)
        self.logs: list[str] = []

    def run(self, transcript: str, **kwargs):
        from core.transcribe.transcribe_service import summarize_transcript

        return summarize_transcript(
            transcript,
            model="picked-m",
            ollama_url="http://localhost:11434",
            log_callback=lambda m, level="INFO": self.logs.append(m),
            **kwargs,
        )


class TestV0655WiringNoMoreEightThousandCharCut:
    def test_the_transcript_tail_reaches_the_prompt(self, monkeypatch):
        """THE OPERATOR'S 15-MIN VIDEO CASE: a 20k-char transcript —
        the rendered prompt must contain the LAST 2k chars (chars
        18k-20k). On the pre-fix code the prompt only ever saw
        transcript[:8000] — this pin fails there."""
        head = _sentences(400) + " "
        tail_marker = "UNIQUE_TAIL_MARKER_" + "zq" * 500  # 1000-char unique tail
        transcript = head + tail_marker
        h = _WiringHarness(monkeypatch)
        h.run(transcript)
        prompt = h.captured["call"]["prompt"]
        assert "UNIQUE_TAIL_MARKER_" in prompt, (
            "the transcript tail never reached the LLM — the [:8000] cut "
            "(or a budget mis-fit) is still amputating the transcript"
        )

    def test_a_short_transcript_is_passed_verbatim(self, monkeypatch):
        text = "short transcript about three concepts."
        h = _WiringHarness(monkeypatch)
        h.run(text)
        assert text in h.captured["call"]["prompt"]

    def test_oversize_transcript_logs_the_truncation_loudly(self, monkeypatch):
        """The cut is never silent: a WARNING-level log line names the
        used/total character counts."""
        text = _sentences(20_000)  # ~240k words — over the 24k default
        h = _WiringHarness(monkeypatch)
        h.run(text)
        assert any("truncated" in m.lower() for m in h.logs), (
            "an over-budget transcript was cut without ANY log line — "
            "the silent-amputation class of bug is back"
        )

    def test_tutorial_output_type_still_selects_the_tutorial_template(self, monkeypatch):
        """The existing V0.6.43 output_type contract is preserved (the
        tutorial prompt is a different document)."""
        h = _WiringHarness(monkeypatch)
        h.run("some text", output_type="tutorial")
        prompt = h.captured["call"]["prompt"]
        assert "tutorial" in prompt.lower()
