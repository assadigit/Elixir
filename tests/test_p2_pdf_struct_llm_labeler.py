"""Phase 2 (Test-Net Deepening) — hermetic tests for ``core/pdf/llm_heading_labeler.py``.

``label_headings_with_llm`` sends the extracted markdown to a local Ollama
model and parses "heading (page N)" lines back into (heading, page) tuples.
The LLM HTTP boundary (``utils.network.safe_ollama_request``) is mocked;
parsing, truncation and prompt-building logic run for real.
"""

from __future__ import annotations

import sys
import types

from core.pdf.llm_heading_labeler import (
    _build_heading_label_prompt,
    _parse_heading_labels,
    label_headings_with_llm,
)


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    ``test_chapter_matcher_robust`` (and friends) install MagicMock stubs for
    heavy optional deps (docx among them) at collection time and never remove
    them; collection is alphabetical, so the stub can already be in place when
    this file is imported. The production code lazily imports
    ``core.summarisation.prompt_manager``, whose package ``__init__`` pulls in
    ``keypoints_builder`` -> ``from docx.shared import Inches, Pt`` — on the
    stubbed docx (a MagicMock with ``__path__ = []``) that raises
    ``AttributeError: __spec__``. Real modules are ``types.ModuleType``
    instances — MagicMocks are not — so drop the stub and let the lazy import
    resolve the real python-docx (a core requirement).
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("docx")


class _FakeResp:
    def __init__(self, text: str):
        self._text = text

    def json(self):
        return {"response": self._text}


class _OllamaStub:
    def __init__(self, text: str = "", raise_exc: Exception | None = None):
        self.text = text
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def __call__(self, method, url, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "json": json, "timeout": timeout})
        if self.raise_exc is not None:
            raise self.raise_exc
        return _FakeResp(self.text)


MARKERS = [(1, 0), (2, 42)]


# ── label_headings_with_llm ─────────────────────────────────────────────────


class TestLabelHeadingsWithLlm:
    def test_empty_markdown_returns_empty(self):
        assert label_headings_with_llm("", MARKERS, "model-x") == []

    def test_empty_model_returns_empty(self):
        assert label_headings_with_llm("some markdown", MARKERS, "") == []

    def test_llm_exception_returns_empty(self, monkeypatch):
        stub = _OllamaStub(raise_exc=ConnectionError("ollama down"))
        monkeypatch.setattr("utils.network.safe_ollama_request", stub)
        logs: list[tuple[str, str]] = []
        result = label_headings_with_llm(
            "# Heading\nbody text here",
            MARKERS,
            "model-x",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert result == []
        assert any("LLM call failed" in m for _, m in logs)
        assert stub.calls[0]["url"] == "http://localhost:11434/api/generate"
        assert stub.calls[0]["method"] == "POST"

    def test_empty_llm_response_returns_empty(self, monkeypatch):
        monkeypatch.setattr("utils.network.safe_ollama_request", _OllamaStub(""))
        logs: list[tuple[str, str]] = []
        result = label_headings_with_llm(
            "# Heading\nbody text here",
            MARKERS,
            "model-x",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert result == []
        assert any("empty response" in m for _, m in logs)

    def test_unparseable_response_returns_empty(self, monkeypatch):
        monkeypatch.setattr("utils.network.safe_ollama_request", _OllamaStub("no headings here"))
        logs: list[tuple[str, str]] = []
        result = label_headings_with_llm(
            "# Heading\nbody text here",
            MARKERS,
            "model-x",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert result == []
        assert any("no headings parsed" in m for _, m in logs)

    def test_successful_labeling(self, monkeypatch):
        response = (
            "1 Introduction (page 1)\n"
            "2 Currently Available New Treatments (page 2)\n"
            "2.1 Lasmiditan (page 3)\n"
            "2.1.1 Proposed Mode of Action (page 3)\n"
        )
        stub = _OllamaStub(response)
        monkeypatch.setattr("utils.network.safe_ollama_request", stub)
        logs: list[tuple[str, str]] = []
        headings = label_headings_with_llm(
            "<!-- original page 1 -->\n# Introduction\nbody",
            MARKERS,
            "qwen3:8b",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert headings == [
            ("1 Introduction", 1),
            ("2 Currently Available New Treatments", 2),
            # NOTE: the leading-number strip only removes the FIRST number,
            # so "2.1 Lasmiditan" keeps its ".1" tail as "1 Lasmiditan".
            ("1 Lasmiditan", 3),
            ("1.1 Proposed Mode of Action", 3),
        ]
        assert any("4 headings labeled" in m for _, m in logs)
        # payload shape: low temperature, capped num_predict
        payload = stub.calls[0]["json"]
        assert payload["model"] == "qwen3:8b"
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0.1
        assert payload["options"]["num_predict"] == 4096

    def test_long_markdown_is_truncated(self, monkeypatch):
        long_md = "heading word here " * 5000  # ~90k chars > 48k limit
        stub = _OllamaStub("Intro (page 1)")
        monkeypatch.setattr("utils.network.safe_ollama_request", stub)
        logs: list[tuple[str, str]] = []
        result = label_headings_with_llm(
            long_md,
            MARKERS,
            "model-x",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert result == [("Intro", 1)]
        prompt = stub.calls[0]["json"]["prompt"]
        assert "[... content truncated ...]" in prompt
        assert len(prompt) < len(long_md)
        assert any("truncated" in m for _, m in logs)

    def test_short_markdown_sent_whole(self, monkeypatch):
        md = "# Tiny Document\n\nbody"
        stub = _OllamaStub("Only Heading (page 1)")
        monkeypatch.setattr("utils.network.safe_ollama_request", stub)
        label_headings_with_llm(md, MARKERS, "model-x")
        prompt = stub.calls[0]["json"]["prompt"]
        assert "Tiny Document" in prompt
        assert "truncated" not in prompt

    def test_custom_ollama_url_used(self, monkeypatch):
        stub = _OllamaStub("A (page 1)")
        monkeypatch.setattr("utils.network.safe_ollama_request", stub)
        label_headings_with_llm("markdown", MARKERS, "m", ollama_url="http://other-host:1234")
        assert stub.calls[0]["url"] == "http://other-host:1234/api/generate"

    def test_more_than_ten_headings_log_summary(self, monkeypatch):
        response = "\n".join(f"Heading Number {i} (page {i + 1})" for i in range(12))
        monkeypatch.setattr("utils.network.safe_ollama_request", _OllamaStub(response))
        logs: list[tuple[str, str]] = []
        headings = label_headings_with_llm(
            "markdown",
            MARKERS,
            "m",
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        assert len(headings) == 12
        assert any("… and 2 more" in m for _, m in logs)


# ── _build_heading_label_prompt ─────────────────────────────────────────────


class TestBuildPrompt:
    def test_prompt_contains_markdown(self):
        prompt = _build_heading_label_prompt("# My Heading\nsome body text")
        assert prompt  # rendered from prompts/pdf/heading_label.md
        assert "My Heading" in prompt
        assert "some body text" in prompt

    def test_missing_template_returns_empty_string(self, monkeypatch):
        from core.summarisation.prompt_manager import PromptManager

        monkeypatch.setattr(PromptManager, "render_template", lambda self, name, **variables: None)
        assert _build_heading_label_prompt("anything") == ""


# ── _parse_heading_labels ───────────────────────────────────────────────────


class TestParseHeadingLabels:
    def test_primary_page_format(self):
        assert _parse_heading_labels("Introduction (page 5)") == [("Introduction", 5)]

    def test_abbreviated_p_variants(self):
        assert _parse_heading_labels("Methods (p. 7)") == [("Methods", 7)]
        assert _parse_heading_labels("Results (p 9)") == [("Results", 9)]

    def test_numbered_and_bulleted_lines(self):
        text = "1. Intro (page 1)\n2) Methods (page 2)\n- Results (page 3)\n* Discussion (page 4)"
        assert _parse_heading_labels(text) == [
            ("Intro", 1),
            ("Methods", 2),
            ("Results", 3),
            ("Discussion", 4),
        ]

    def test_comma_variant(self):
        assert _parse_heading_labels("Conclusion, page 12") == [("Conclusion", 12)]
        assert _parse_heading_labels("Conclusion, p. 13") == [("Conclusion", 13)]

    def test_dotted_variant(self):
        assert _parse_heading_labels("Appendix ... 22") == [("Appendix", 22)]

    def test_thinking_blocks_stripped(self):
        text = "<think>internal reasoning about the document</think>\nReal Heading (page 2)"
        assert _parse_heading_labels(text) == [("Real Heading", 2)]
        text2 = "<thinking>more reasoning</thinking>\nOther Heading (page 3)"
        assert _parse_heading_labels(text2) == [("Other Heading", 3)]

    def test_invalid_lines_rejected(self):
        text = "ab (page 1)\nValid Heading (page 0)\nNo pages here\nX (page 2)"
        # "ab" too short, page 0 invalid, plain text unparsed; "X" too short
        assert _parse_heading_labels(text) == []

    def test_deduplication_is_case_insensitive(self):
        text = "Methods (page 2)\nmethods (page 3)\nMETHODS (page 4)"
        assert _parse_heading_labels(text) == [("Methods", 2)]

    def test_empty_and_blank_lines(self):
        assert _parse_heading_labels("") == []
        assert _parse_heading_labels("\n\n   \n") == []
