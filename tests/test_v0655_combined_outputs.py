"""V0.6.55 (P3) — the combined single-round-trip summary+tutorial pins.

THE PROBLEM (the operator's redesign item): when both outputs were
checked, the dialog ran TWO sequential full LLM generations over the
SAME transcript — Step 4 summary, then Step 5 tutorial. On the rig's
dense 27B at 2-6 tok/s each round trip is minutes; the two-pass flow
doubled the wait for zero quality benefit (both documents describe the
same transcript).

THE FIX (core/transcribe/transcribe_service.py):

  1. ``prompts/transcribe/transcript_combined.md`` — ONE prompt that
     asks for BOTH documents separated by an EXACT marker line:
     ``<<<ELIXIR-TRANSCRIBE-SPLIT>>>`` (before: the Obsidian notes;
     after: the tutorial guide).
  2. ``split_combined_output(text)`` — the robust splitter (tolerates
     marker drift: case, extra angle brackets, hyphens/underscores/
     spaces, stray code fences around either document).
  3. ``summarize_transcript_combined(...)`` — renders the combined
     prompt, makes ONE provider call, splits. On a clean split both
     documents come back (``split_ok`` True). On a missing/garbled
     marker the RAW response is returned as the summary with
     ``split_ok`` False and the CALLER falls back to a separate
     tutorial call — correctness is never sacrificed to save a round
     trip.

THE PINS: the pure splitter (exact marker / drift variants / fences /
missing marker / empty sides), the prompt template (exists, carries
the marker + BOTH document contracts + the transcript), and the
wiring (ONE provider call, both outputs delivered, the fallback
signal, on_chunk forwarded — the V0.6.13 harness pattern).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.transcribe.transcribe_service import (  # noqa: E402
    split_combined_output,
    summarize_transcript_combined,
)

_MARKER = "<<<ELIXIR-TRANSCRIBE-SPLIT>>>"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — the pure splitter
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655SplitCombinedOutput:
    def test_exact_marker_splits_both_sides(self):
        text = f"# Notes\n\n- point one\n\n{_MARKER}\n\n# Tutorial\n\n1. step"
        out = split_combined_output(text)
        assert out["ok"] is True
        assert out["summary"] == "# Notes\n\n- point one"
        assert out["tutorial"] == "# Tutorial\n\n1. step"

    def test_marker_case_and_delimiter_drift_is_tolerated(self):
        """Predictable model drift: case, underscores/hyphens/spaces,
        extra angle brackets — all still split."""
        for marker in (
            "<<<elixir-transcribe-split>>>",
            "<<<<ELIXIR_TRANSCRIBE_SPLIT>>>>",
            "<<< Elixir Transcribe Split >>>",
            "<<elixir transcribe split>>",
        ):
            text = f"summary body\n\n{marker}\n\ntutorial body"
            out = split_combined_output(text)
            assert out["ok"] is True, marker
            assert out["summary"] == "summary body"
            assert out["tutorial"] == "tutorial body"

    def test_code_fences_around_either_document_are_stripped(self):
        text = f"```markdown\n# Notes\n- a\n```\n\n{_MARKER}\n\n```markdown\n# Tutorial\n1. b\n```"
        out = split_combined_output(text)
        assert out["ok"] is True
        assert out["summary"] == "# Notes\n- a"
        assert out["tutorial"] == "# Tutorial\n1. b"

    def test_missing_marker_is_not_ok(self):
        out = split_combined_output("# Notes only\n\n- no tutorial here")
        assert out["ok"] is False
        assert out["summary"] is None
        assert out["tutorial"] is None

    def test_empty_side_is_not_ok(self):
        """A marker with nothing after it is not a valid split — the
        caller must get the fallback signal, not a half-delivered
        contract."""
        out = split_combined_output(f"summary only\n\n{_MARKER}\n\n")
        assert out["ok"] is False
        assert out["summary"] == "summary only"  # the salvageable side
        assert out["tutorial"] is None

    def test_empty_text_is_not_ok(self):
        assert split_combined_output("")["ok"] is False
        assert split_combined_output("   \n  ")["ok"] is False

    def test_marker_inside_body_text_is_preferred_at_first_occurrence(self):
        """A model that MENTIONS the marker inside the notes text
        still splits at the first occurrence (the contract line, not
        the discussion of it)."""
        text = f"notes mention {_MARKER} in passing\n\n{_MARKER}\n\ntutorial"
        out = split_combined_output(text)
        assert out["ok"] is True
        assert "notes mention" in out["summary"]
        assert out["tutorial"] == "tutorial"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — the combined prompt template
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655CombinedPromptTemplate:
    def test_template_file_exists(self):
        assert (_project_root / "prompts" / "transcribe" / "transcript_combined.md").exists()

    def test_render_contains_marker_and_both_contracts(self):
        from core.summarisation.prompt_manager import PromptManager

        prompt = PromptManager().render_template(
            "transcribe/transcript_combined", transcript="TRANSCRIPT_BODY_XYZ"
        )
        assert prompt is not None
        assert "ELIXIR-TRANSCRIBE-SPLIT" in prompt
        # Document A contract (the Obsidian notes).
        assert "Core Concepts" in prompt
        assert "Key Takeaways" in prompt
        # Document B contract (the tutorial).
        assert "What You'll Learn" in prompt
        assert "Step-by-Step" in prompt
        # The transcript is substituted in.
        assert "TRANSCRIPT_BODY_XYZ" in prompt


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — the wiring: ONE round trip, both outputs
# ═════════════════════════════════════════════════════════════════════════════


class _CombinedHarness:
    """summarize_transcript_combined + faked create_provider + faked
    probe (the test_v0613_llamacpp_first_services.py pattern)."""

    def __init__(self, monkeypatch, fake_output: str, values: dict | None = None) -> None:
        import core.llm.llm_provider as lp
        from utils.settings import Settings

        class _S:
            def __init__(self, v):
                self._v = dict(v or {})

            def get(self, key, default=None):
                return self._v.get(key, default)

            def set(self, key, value):
                return True

        monkeypatch.setattr(Settings, "_test_override", _S(values), raising=False)

        from core.llm import local_fallback

        class _ProbeSpy:
            def __call__(self, base_url, api_key, timeout=10):
                return []  # dead → passthrough, provider stays "ollama"

        monkeypatch.setattr(local_fallback, "list_llamacpp_models", _ProbeSpy())
        local_fallback.clear_llamacpp_probe_cache()

        self.captured: dict = {}
        captured = self.captured
        self.chunk_events: list[str] = []

        class _FakeProvider:
            base_url = "http://localhost:11434"

            def complete_streaming(
                self, prompt, temperature=None, max_tokens=None, model=None, on_chunk=None
            ):
                captured.setdefault("calls", []).append(
                    {"prompt": prompt, "model": model, "on_chunk": on_chunk}
                )
                if on_chunk is not None:
                    on_chunk(fake_output[: len(fake_output) // 2])
                    on_chunk(fake_output)
                return fake_output

        def _factory(provider, settings, log_callback=None, supervisor=None):
            captured["provider"] = provider
            return _FakeProvider()

        monkeypatch.setattr(lp, "create_provider", _factory)
        self.logs: list[str] = []

    def run(self, transcript: str = "the transcript text about concepts"):
        return summarize_transcript_combined(
            transcript,
            model="picked-m",
            ollama_url="http://localhost:11434",
            log_callback=lambda m, level="INFO": self.logs.append(m),
            on_chunk=lambda partial: self.chunk_events.append(partial),
        )


class TestV0655CombinedWiring:
    def test_one_round_trip_delivers_both_outputs(self, monkeypatch):
        """THE P3 CONTRACT: both documents, ONE provider call (the
        pre-fix flow made TWO sequential calls for the same
        transcript)."""
        fake = (
            "> [!tldr] tl\n\n## Core Concepts\n- a\n\n"
            f"{_MARKER}\n\n"
            "> [!summary] ts\n\n## What You'll Learn\n- b"
        )
        h = _CombinedHarness(monkeypatch, fake)
        out = h.run("a transcript")
        assert h.captured["provider"] == "ollama"
        assert len(h.captured["calls"]) == 1, "must be exactly ONE LLM call"
        assert out["split_ok"] is True
        assert "Core Concepts" in out["summary"]
        assert "What You'll Learn" in out["tutorial"]

    def test_the_whole_transcript_reaches_the_combined_prompt(self, monkeypatch):
        """P2 + P3 interplay: the combined prompt gets the budget-fit
        transcript (the tail too — no [:8000] amputation)."""
        tail = "COMBINED_TAIL_MARKER_" + "qz" * 400
        h = _CombinedHarness(monkeypatch, f"notes\n\n{_MARKER}\n\ntutorial")
        h.run("head text. " * 200 + tail)
        assert "COMBINED_TAIL_MARKER_" in h.captured["calls"][0]["prompt"]

    def test_missing_marker_signals_the_fallback(self, monkeypatch):
        """No marker in the response → split_ok False, the raw text as
        summary, tutorial None, and a WARNING log — the caller then
        runs the separate tutorial call (correctness over speed)."""
        h = _CombinedHarness(monkeypatch, "just one document, no marker")
        out = h.run("a transcript")
        assert out["split_ok"] is False
        assert out["summary"] == "just one document, no marker"
        assert out["tutorial"] is None
        assert any("marker" in m.lower() for m in h.logs)

    def test_on_chunk_is_forwarded_through_the_single_call(self, monkeypatch):
        """P4 interplay: the streaming callback rides the ONE call —
        the UI shows the combined generation growing."""
        fake = f"notes\n\n{_MARKER}\n\ntutorial"
        h = _CombinedHarness(monkeypatch, fake)
        h.run("a transcript")
        assert h.captured["calls"][0]["on_chunk"] is not None
        assert len(h.chunk_events) == 2  # mid + final partials delivered

    def test_llm_failures_raise_the_structured_family(self, monkeypatch):
        """P5 interplay: the combined path raises the same structured
        errors as the single-output path."""
        import core.llm.llm_provider as lp
        from core.transcribe.errors import LLMConnectionError
        from utils.settings import Settings

        class _S:
            def get(self, key, default=None):
                return None if key == "local.llamacpp_first" else default

        monkeypatch.setattr(Settings, "_test_override", _S(), raising=False)

        from core.llm import local_fallback

        class _Dead:
            def __call__(self, base_url, api_key, timeout=10):
                return []

        monkeypatch.setattr(local_fallback, "list_llamacpp_models", _Dead())
        local_fallback.clear_llamacpp_probe_cache()

        class _Boom:
            def complete_streaming(self, prompt, **kwargs):
                raise RuntimeError("ConnectionError: refused")

        monkeypatch.setattr(lp, "create_provider", lambda *a, **k: _Boom())
        with pytest.raises(LLMConnectionError):
            summarize_transcript_combined("t", model="m")
