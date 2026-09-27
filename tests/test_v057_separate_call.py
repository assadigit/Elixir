"""V0.5.7 (SEPARATE-CALL) — the source-glossary extraction is now a
DEDICATED LLM call, NOT fused into the master-summary call.

The V0.5.6 audit found the fused approach (the master-summary LLM call
also asked for the ``<name_glossary>`` block) overwhelmed the
Ternary-Bonsai-2-27B model — 3 empty master-summary returns + a fall-back
to the 5-in-1 single-pass path (which had no glossary wired). Result: 0
glossary mentions in the conversion log; the 📖 .glossary.md
persistence + the loosened quote-guard + the V0.5.6 final-check round 4
all stayed DORMANT.

V0.5.7 fixes this by:
  1. REVERTING the ``<name_glossary>`` block instruction from the 3
     master-summary prompts (default.md + default_lowbit.md +
     summarisation/master_summary.md) — the master-summary is back to
     just the 5 summary sections (V0.5.5 state).
  2. Creating a NEW dedicated glossary-extraction prompt
     (``prompts/summarisation/glossary_extraction.md``) that asks the
     LLM ONLY for the ``<name_glossary>`` block.
  3. Adding ``extract_glossary_via_llm`` to ``glossary_parser.py`` —
     makes a SEPARATE LLM call, parses the ``<name_glossary>`` block,
     persists the ``.glossary.md`` file, + returns the dict.
  4. Wiring ``extract_glossary_via_llm`` into ``primary_call.py`` in
     BOTH the master-summary-success path AND the 5-in-1-fallback
     path (3 return points: chunked success, structured fallback, raw
     fallback) — so the glossary is extracted even when the
     master-summary failed + the 5-in-1 fallback fired.

Content-agnostic (Rule 1): the glossary-extraction prompt is generic
("ALL cited authors"); the parser uses generic regex; the new
``extract_glossary_via_llm`` function uses the runtime source text.
NO hardcoded book/author/chapter names. The author names + dates +
terms in these tests are TEST FIXTURES (Bak / Freud / Klein / Alpha /
Beta / Gamma — Rule 1 exempt).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

# Stub tiktoken (not installed in test env) — same pattern as conftest.
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = lambda *a, **k: None
    tk.encoding_for_model = lambda *a, **k: None
    tk.Encoding = type("_E", (), {})
    sys.modules["tiktoken"] = tk

from core.summarisation import primary_call as pc_mod  # noqa: E402
from core.summarisation.glossary_parser import (  # noqa: E402
    extract_glossary_via_llm,
)

# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures (synthetic author names — Rule 1 exempt).
# ─────────────────────────────────────────────────────────────────────────────

# A realistic, well-formed <name_glossary> block returned by a (mocked) LLM.
_GLOSSARY_LLM_RESPONSE = """<name_glossary>
## Names
- **Bak** (1946) — coined the higher level character organization concept
- **Freud** (1911, 1922) — originator of the psychoanalytic framework
- **Klein** (1946a, 1952b) — developed the paranoid-schizoid position
## Dates
- **1887-1902** — early foundational period of psychoanalysis
- **1920s** — the rise of ego psychology
## Terms
- **paranoid-schizoid position** — Klein's developmental substrate
- **projection** — defensive attribution of internal states to others
</name_glossary>
"""

# A small synthetic source text (the LLM input — content-agnostic, just a
# fixture so the test doesn't depend on a real book's content).
_SOURCE_TEXT_FIXTURE = (
    "Bak (1946) introduced the higher level character organization concept. "
    "Freud (1911, 1922) originated the psychoanalytic framework. "
    "Klein (1946a, 1952b) developed the paranoid-schizoid position. "
    "The 1887-1902 period was the early foundational period of psychoanalysis. "
    "The 1920s saw the rise of ego psychology. "
    "Projection is the defensive attribution of internal states to others."
)


# ═══════════════════════════════════════════════════════════════════════════
# 1) The 3 master-summary prompts are REVERTED — no <name_glossary> block.
# ═════════════════════════════════════════════════════════════════════════


class TestMasterSummaryPromptRevertedNoNameGlossary:
    """V0.5.7: the 3 master-summary prompts do NOT contain the
    ``<name_glossary>`` block instruction (reverted from V0.5.6's fused
    approach). The glossary is now extracted via a SEPARATE LLM call
    (``prompts/summarisation/glossary_extraction.md``)."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "prompts/default.md",
            "prompts/default_lowbit.md",
        ],
    )
    def test_master_summary_prompt_reverted_no_name_glossary(self, relpath):
        """The 5-section default prompts (default.md + default_lowbit.md)
        — the OUTPUT FORMAT preamble is back to 'five XML sections' (NOT
        'six') AND no ``<name_glossary>`` block."""
        prompt_path = Path(relpath)
        assert prompt_path.exists(), f"missing prompt file: {relpath}"
        text = prompt_path.read_text(encoding="utf-8")
        # The <name_glossary> block instruction is GONE (V0.5.7 reverted it).
        assert "<name_glossary>" not in text, (
            f"{relpath}: V0.5.7 must REMOVE the <name_glossary> block "
            "instruction from the master-summary prompt (the fused approach "
            "overwhelmed the model — the glossary is now a separate LLM call)"
        )
        assert "</name_glossary>" not in text, (
            f"{relpath}: V0.5.7 must REMOVE the </name_glossary> closer "
            "from the master-summary prompt"
        )
        # The "ALSO output a <name_glossary>" instruction is GONE.
        low = text.lower()
        assert "also output a `<name_glossary>`" not in low, (
            f"{relpath}: V0.5.7 must REMOVE the 'ALSO output a "
            "<name_glossary>' instruction from the master-summary prompt"
        )
        # The OUTPUT FORMAT preamble is back to "five XML sections" (NOT six).
        assert "five xml sections" in low, (
            f"{relpath}: V0.5.7 reverted the OUTPUT FORMAT preamble back to "
            "'five XML sections' (the <name_glossary> block is no longer the "
            "6th section)"
        )
        assert "six xml sections" not in low, (
            f"{relpath}: V0.5.7 must NOT reference 'six XML sections' (the "
            "master-summary no longer carries the <name_glossary> block)"
        )

    def test_master_summary_prompt_master_summary_md_reverted(self):
        """The single-section master_summary.md prompt — the
        ``<name_glossary>`` block instruction is GONE (the master_summary.md
        prompt asks ONLY for the ``<thorough_summary>`` block — it never
        had a 'five/six XML sections' preamble, so we just check the
        ``<name_glossary>`` block + the 'GLOSSARY' section are gone)."""
        relpath = "prompts/summarisation/master_summary.md"
        text = Path(relpath).read_text(encoding="utf-8")
        assert "<name_glossary>" not in text, (
            f"{relpath}: V0.5.7 must REMOVE the <name_glossary> block "
            "instruction from the master_summary.md prompt"
        )
        assert "</name_glossary>" not in text
        # The 'GLOSSARY (V0.5.6)' section header is GONE.
        low = text.lower()
        assert "### glossary (v0.5.6)" not in low, (
            f"{relpath}: V0.5.7 must REMOVE the '### GLOSSARY (V0.5.6)' "
            "section header from the master_summary.md prompt"
        )
        assert "also output a `<name_glossary>`" not in low
        # The master_summary.md prompt still carries the <thorough_summary>
        # block (the single section it asks for — the V0.5.6 fusion added
        # <name_glossary> as a 2nd; V0.5.7 reverted to the single section).
        assert "<thorough_summary>" in text
        assert "</thorough_summary>" in text


# ═══════════════════════════════════════════════════════════════════════════
# 2) The NEW glossary-extraction prompt exists + is content-agnostic.
# ═══════════════════════════════════════════════════════════════════════════


class TestGlossaryExtractionPrompt:
    """V0.5.7 created the ``prompts/summarisation/glossary_extraction.md``
    prompt file as a DEDICATED glossary-extraction prompt (separate from
    the master-summary call). V0.5.10 changed the prompt's OUTPUT FORMAT
    from the ``<name_glossary>`` XML wrapper to plain markdown headers
    (``## Source Glossary — Names``). This test asserts the V0.5.10
    contract: the prompt carries the markdown-header instruction + the
    ``{source_text}`` placeholder + is GENERIC (content-agnostic —
    Rule 1)."""

    REL = "prompts/summarisation/glossary_extraction.md"

    def test_glossary_extraction_prompt_exists(self):
        prompt_path = Path(self.REL)
        assert prompt_path.exists(), (
            f"V0.5.7: missing glossary-extraction prompt {self.REL} — "
            "the new dedicated glossary-extraction prompt file must exist "
            "(the master-summary prompt no longer carries the instruction)"
        )
        text = prompt_path.read_text(encoding="utf-8")
        # V0.5.10: the prompt uses the NEW markdown-header format (NOT the
        # <name_glossary> XML wrapper that V0.5.6-V0.5.9 used — the model
        # couldn't reliably follow the XML-tag instruction). The 3 section
        # headers are present (the LLM is told to output these exact
        # headers).
        assert "## Source Glossary — Names" in text, (
            f"{self.REL}: V0.5.10 must use the NEW markdown-header format "
            "(## Source Glossary — Names) — NOT the <name_glossary> XML "
            "wrapper (the model can't follow the XML format)"
        )
        assert "## Source Glossary — Dates" in text, (
            f"{self.REL}: V0.5.10 must use the '## Source Glossary — Dates' header"
        )
        assert "## Source Glossary — Terms" in text, (
            f"{self.REL}: V0.5.10 must use the '## Source Glossary — Terms' header"
        )
        # V0.5.10: the </name_glossary> closer is GONE (the XML wrapper is
        # removed). The prompt MAY mention `<name_glossary>` in a "Do NOT
        # use" instruction, but the `</name_glossary>` closer must NOT
        # appear (it would only appear if the prompt instructed the LLM
        # to OUTPUT the XML wrapper, which V0.5.10 doesn't).
        assert "</name_glossary>" not in text, (
            f"{self.REL}: V0.5.10 must NOT instruct the LLM to OUTPUT the "
            "</name_glossary> closer (the XML wrapper is removed — the "
            "V0.5.10 format uses plain markdown headers)"
        )
        # The instruction is GENERIC (Rule 1) — it tells the LLM to list
        # "ALL cited authors" (not specific names).
        low = text.lower()
        assert "all cited authors" in low, (
            f"{self.REL}: the instruction must use the generic 'ALL cited "
            "authors' phrasing (content-agnostic — lets the LLM pull the "
            "roster from the runtime source, NOT hardcoded names)"
        )
        # The {source_text} placeholder is present (the pipeline substitutes
        # the runtime source).
        assert "{source_text}" in text, (
            f"{self.REL}: must contain the {{source_text}} placeholder "
            "(the pipeline substitutes the runtime source text)"
        )

    def test_glossary_extraction_prompt_is_content_agnostic(self):
        """Rule 1 guard: the glossary-extraction prompt must NOT hardcode any
        book-specific author names, dates, or terms — the LLM pulls the
        roster from the runtime source."""
        # Forbidden: the 5 author names the V0.5.5 audit found missing
        # from the test chapter (they're book content, NOT generic).
        forbidden_names = ["jack", "morey", "ndtei", "rettersol", "bak"]
        # Forbidden: book-specific terms from the paranoid chapter.
        forbidden_terms = [
            "paranoid-schizoid position",
            "broken structures",
            "false self",
            "ego-syntonic",
        ]
        text = Path(self.REL).read_text(encoding="utf-8").lower()
        for name in forbidden_names:
            assert name not in text, (
                f"{self.REL}: glossary-extraction prompt hardcodes book "
                f"author '{name}' — Rule 1 violation (must be generic 'ALL "
                "cited authors')"
            )
        for term in forbidden_terms:
            assert term not in text, (
                f"{self.REL}: glossary-extraction prompt hardcodes book "
                f"term '{term}' — Rule 1 violation (must be generic)"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3) extract_glossary_via_llm returns the parsed dict + persists the .md.
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractGlossaryViaLlmReturnsParsedDict:
    """A mocked ``call_llm`` returning a ``<name_glossary>`` block →
    ``extract_glossary_via_llm`` returns the parsed dict + persists the
    ``.glossary.md`` file."""

    def test_extract_glossary_via_llm_returns_parsed_dict(self, tmp_path):
        logs: list[tuple[str, str]] = []

        def call_llm(prompt, model=None, temperature=None, max_tokens=None):
            # Record the call args (for the prompt-substitution assertion).
            logs.append(("call_llm-invoked", f"model={model} temp={temperature}"))
            return _GLOSSARY_LLM_RESPONSE

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        glossary = extract_glossary_via_llm(
            source_text=_SOURCE_TEXT_FIXTURE,
            call_llm=call_llm,
            primary_model="test-model",
            temperature=0.3,
            max_output_tokens=4096,
            log=log,
            chapter_heading="Test Chapter",
            output_dir=str(tmp_path),
            run_id="run-v057-test",
        )
        # The glossary is parsed (3 names + 2 dates + 2 terms).
        assert set(glossary.keys()) == {"names", "dates", "terms"}
        assert len(glossary["names"]) == 3
        assert glossary["names"][0]["name"] == "Bak"
        assert glossary["names"][0]["year"] == "1946"
        assert len(glossary["dates"]) == 2
        assert glossary["dates"][0]["date"] == "1887-1902"
        assert len(glossary["terms"]) == 2
        assert glossary["terms"][0]["term"] == "paranoid-schizoid position"
        # The .glossary.md file was written.
        glossary_file = tmp_path / "summaries" / ".glossaries" / "Test Chapter.glossary.md"
        assert glossary_file.exists(), (
            f"glossary file not written at {glossary_file}; "
            f"actual files: {list((tmp_path / 'summaries' / '.glossaries').glob('*'))}"
        )
        content = glossary_file.read_text(encoding="utf-8")
        assert "# Source Glossary — Test Chapter" in content
        assert "- **Bak** (1946) —" in content
        assert "- **paranoid-schizoid position** —" in content
        # The persist log line was emitted.
        persist_logs = [m for m, _ in logs if "V0.5.7 source glossary" in m]
        assert len(persist_logs) == 1, f"expected 1 V0.5.7 persist log, got {persist_logs}"
        # The call_llm was invoked exactly once with the right model+temp.
        invocations = [m for m, _ in logs if m == "call_llm-invoked"]
        assert len(invocations) == 1
        # The prompt was built from the glossary_extraction.md template
        # (the source text was substituted into the {source_text} placeholder).
        # We can't capture the prompt arg directly via the log fixture, so
        # we verify the call_llm signature by re-invoking with a recorder.
        captured: dict = {}

        def recording_call_llm(prompt, model=None, temperature=None, max_tokens=None):
            captured["prompt"] = prompt
            captured["model"] = model
            captured["temperature"] = temperature
            captured["max_tokens"] = max_tokens
            return _GLOSSARY_LLM_RESPONSE

        extract_glossary_via_llm(
            source_text=_SOURCE_TEXT_FIXTURE,
            call_llm=recording_call_llm,
            primary_model="test-model",
            temperature=0.3,
            max_output_tokens=4096,
            log=lambda m, l="INFO": None,
            chapter_heading="Test Chapter",
            output_dir=str(tmp_path),
        )
        # The prompt is the glossary_extraction.md template with the source
        # text substituted in.
        assert _SOURCE_TEXT_FIXTURE in captured["prompt"], (
            "the prompt must contain the source text (substituted into the "
            "{source_text} placeholder)"
        )
        # V0.5.10: the prompt uses the NEW markdown-header format (NOT the
        # <name_glossary> XML wrapper that V0.5.6-V0.5.9 used). The 3
        # section headers are present in the prompt.
        assert "## Source Glossary — Names" in captured["prompt"], (
            "the prompt must contain the V0.5.10 '## Source Glossary — "
            "Names' markdown-header instruction (NOT the <name_glossary> "
            "XML wrapper — the model can't follow the XML format)"
        )
        assert captured["model"] == "test-model"
        assert captured["temperature"] == 0.3
        assert captured["max_tokens"] == 4096


# ═══════════════════════════════════════════════════════════════════════════
# 4) extract_glossary_via_llm fail-open on empty LLM response.
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractGlossaryViaLlmFailOpenOnEmptyResponse:
    """A mocked ``call_llm`` returning an empty string OR None →
    ``extract_glossary_via_llm`` returns the empty 3-key dict (no crash,
    no .md file written)."""

    @pytest.mark.parametrize("empty_value", ["", None, "   \n   \t   "])
    def test_extract_glossary_via_llm_fail_open_on_empty_response(self, tmp_path, empty_value):
        logs: list[tuple[str, str]] = []

        def call_llm(prompt, model=None, temperature=None, max_tokens=None):
            return empty_value

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        glossary = extract_glossary_via_llm(
            source_text=_SOURCE_TEXT_FIXTURE,
            call_llm=call_llm,
            primary_model="test-model",
            log=log,
            chapter_heading="Empty Chapter",
            output_dir=str(tmp_path),
        )
        # The empty 3-key dict is returned (no crash, no .md file written).
        assert glossary == {"names": [], "dates": [], "terms": []}, (
            "empty LLM response must fail-open with the empty 3-key dict"
        )
        # No .glossary.md file written (the parsed glossary is empty).
        assert not (tmp_path / "summaries" / ".glossaries").exists()
        # The DEBUG log noting the empty parse was emitted.
        debug_logs = [m for m, lvl in logs if lvl == "DEBUG" and "no <name_glossary>" in m]
        assert len(debug_logs) == 1, f"expected 1 DEBUG log for empty parse, got {debug_logs}"


# ═══════════════════════════════════════════════════════════════════════════
# 5) extract_glossary_via_llm fail-open on exception.
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractGlossaryViaLlmFailOpenOnException:
    """A mocked ``call_llm`` raising an exception →
    ``extract_glossary_via_llm`` fail-opens (returns the empty 3-key
    dict, logs a WARNING, NEVER raises)."""

    def test_extract_glossary_via_llm_fail_open_on_call_llm_exception(self, tmp_path):
        logs: list[tuple[str, str]] = []

        def call_llm(prompt, model=None, temperature=None, max_tokens=None):
            raise RuntimeError("simulated LLM timeout")

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        # Must NOT raise — fail-open returns the empty 3-key dict.
        glossary = extract_glossary_via_llm(
            source_text=_SOURCE_TEXT_FIXTURE,
            call_llm=call_llm,
            primary_model="test-model",
            log=log,
            chapter_heading="Crash Chapter",
            output_dir=str(tmp_path),
        )
        assert glossary == {"names": [], "dates": [], "terms": []}, (
            "call_llm exception must fail-open with the empty 3-key dict"
        )
        # The WARNING log noting the failure was emitted.
        warning_logs = [
            m for m, lvl in logs if lvl == "WARNING" and "V0.5.7 glossary extraction failed" in m
        ]
        assert len(warning_logs) == 1, (
            f"expected 1 WARNING log for extraction failure, got {warning_logs}"
        )
        # No .glossary.md file written (extraction failed before parse).
        assert not (tmp_path / "summaries" / ".glossaries").exists()

    def test_extract_glossary_via_llm_fail_open_on_no_source_text(self, tmp_path):
        """An empty source_text → extract_glossary_via_llm skips the call
        entirely + returns the empty dict (fail-open, never raises)."""
        logs: list[tuple[str, str]] = []

        def call_llm(prompt, model=None, temperature=None, max_tokens=None):
            raise AssertionError("call_llm must NOT be invoked when source_text is empty")

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        # Empty source text → skip the call entirely.
        glossary = extract_glossary_via_llm(
            source_text="",
            call_llm=call_llm,
            primary_model="test-model",
            log=log,
            chapter_heading="Empty Source",
            output_dir=str(tmp_path),
        )
        assert glossary == {"names": [], "dates": [], "terms": []}
        # The DEBUG log noting the skip was emitted.
        debug_logs = [m for m, lvl in logs if lvl == "DEBUG" and "no source text" in m]
        assert len(debug_logs) == 1

    def test_extract_glossary_via_llm_fail_open_on_no_call_llm(self, tmp_path):
        """A None call_llm → extract_glossary_via_llm skips the call
        entirely + returns the empty dict (fail-open, never raises)."""
        logs: list[tuple[str, str]] = []

        def log(msg: str, level: str = "INFO") -> None:
            logs.append((msg, level))

        glossary = extract_glossary_via_llm(
            source_text=_SOURCE_TEXT_FIXTURE,
            call_llm=None,
            primary_model="test-model",
            log=log,
            chapter_heading="No LLM",
            output_dir=str(tmp_path),
        )
        assert glossary == {"names": [], "dates": [], "terms": []}
        debug_logs = [m for m, lvl in logs if lvl == "DEBUG" and "no call_llm" in m]
        assert len(debug_logs) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6) The glossary is extracted in BOTH paths (master-summary-success +
#    5-in-1-fallback) — primary_call.py wiring.
# ═════════════════════════════════════════════════════════════════════════


class TestGlossaryExtractedInBothPaths:
    """V0.5.7: ``primary_call.summarize_with_model`` extracts the glossary
    in BOTH the master-summary-success path AND the 5-in-1-fallback path
    (the V0.5.6 audit's gap — the 5-in-1 fallback had no glossary wired +
    the master-summary's empty returns meant the glossary never fired).

    These tests DO NOT monkeypatch ``_extract_glossary_for_call`` — they
    let the real implementation run with a mocked ``call_llm_with_empty_retry``
    that returns a ``<name_glossary>`` block. This exercises the FULL
    wiring (prompt build → LLM call → parse → persist → side-channel
    cache population)."""

    def _reset_gpu_temp_cache(self):
        pc_mod._gpu_temp_cache["valid"] = 0.0
        pc_mod._gpu_temp_cache["temp"] = 0.0
        pc_mod._gpu_temp_cache["ts"] = 0.0

    def _no_gpu(self, monkeypatch):
        import subprocess

        def _fake_run(*a, **kw):
            raise FileNotFoundError("no nvidia-smi in test env")

        monkeypatch.setattr(subprocess, "run", _fake_run)

    def _set_tokens(self, monkeypatch, n):
        import utils.token_counter as tc

        monkeypatch.setattr(tc, "count_tokens", lambda text: n)

    def test_glossary_extracted_in_master_summary_success_path(self, monkeypatch, tmp_path):
        """When ``chunked_summarize`` returns a non-None result (the master-
        summary succeeded), ``_extract_glossary_for_call`` is invoked + the
        result carries the ``source_glossary`` key + the side-channel cache
        is populated."""
        from core.summarisation.verification_phase import (
            clear_glossary_cache,
            get_chapter_glossary,
        )

        # Test isolation: reset the GPU temp cache + the glossary side-channel.
        self._reset_gpu_temp_cache()
        self._no_gpu(monkeypatch)
        self._set_tokens(monkeypatch, 5000)
        clear_glossary_cache()

        # The call_llm_with_empty_retry mock returns the glossary block —
        # _extract_glossary_for_call will call it via extract_glossary_via_llm,
        # parse the <name_glossary> block, persist the .md, + stash the
        # glossary in the side-channel cache via set_chapter_glossary.
        def call_llm_with_empty_retry(prompt, model=None, temperature=None, max_tokens=None):
            return _GLOSSARY_LLM_RESPONSE

        # The chunked_summarize mock returns a non-None result (master-summary
        # SUCCESS path).
        def chunked(*a, **k):
            return {"bullet_points": ["master-summary-bullet"], "from_chunked": True}

        result = pc_mod.summarize_with_model(
            "Test Chapter Heading",
            _SOURCE_TEXT_FIXTURE,
            "test-model",
            0.7,
            request=_FakeRequest(output_dir=str(tmp_path)),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,
            call_llm_with_empty_retry=call_llm_with_empty_retry,
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        # The result carries the source_glossary key (the master-summary-
        # success path stashed it).
        assert "source_glossary" in result, (
            "the master-summary-success path must stash the source_glossary "
            "key on the result dict (V0.5.7 wiring)"
        )
        # The glossary was parsed (3 names from the mocked LLM response).
        assert len(result["source_glossary"]["names"]) == 3
        assert result["source_glossary"]["names"][0]["name"] == "Bak"
        # The .glossary.md file was written under tmp_path (no CWD pollution).
        glossary_file = tmp_path / "summaries" / ".glossaries" / "Test Chapter Heading.glossary.md"
        assert glossary_file.exists(), (
            f"glossary file not written at {glossary_file}; actual files: "
            f"{list((tmp_path / 'summaries' / '.glossaries').glob('*'))}"
        )
        # The side-channel cache was populated (the verification LAYER picks
        # this up via get_chapter_glossary(chapter_heading)).
        stashed = get_chapter_glossary("Test Chapter Heading")
        assert stashed is not None, (
            "the master-summary-success path must populate the verification "
            "LAYER's side-channel cache (set_chapter_glossary)"
        )
        assert len(stashed["names"]) == 3
        clear_glossary_cache()

    def test_glossary_extracted_in_5_in_1_fallback_path(self, monkeypatch, tmp_path):
        """When ``chunked_summarize`` returns None (the master-summary
        failed) + the 5-in-1 fallback path fires, the glossary is STILL
        extracted via ``_extract_glossary_for_call`` (the V0.5.6 audit's
        gap — the 5-in-1 path had no glossary wired). The result carries
        the ``source_glossary`` key."""
        from core.summarisation.verification_phase import (
            clear_glossary_cache,
            get_chapter_glossary,
        )

        # Test isolation: reset the GPU temp cache + the glossary side-channel.
        self._reset_gpu_temp_cache()
        self._no_gpu(monkeypatch)
        self._set_tokens(monkeypatch, 5000)
        clear_glossary_cache()

        # The call_llm_with_empty_retry mock returns the glossary block.
        def call_llm_with_empty_retry(prompt, model=None, temperature=None, max_tokens=None):
            return _GLOSSARY_LLM_RESPONSE

        # chunked_summarize returns None → master-summary FAILED → the 5-in-1
        # fallback fires. The structured path returns a dict (simulating the
        # 5-in-1 fallback succeeding via the structured-JSON branch).
        def chunked(*a, **k):
            return None  # master-summary failed

        result = pc_mod.summarize_with_model(
            "Fallback Chapter Heading",
            _SOURCE_TEXT_FIXTURE,
            "test-model",
            0.7,
            request=_FakeRequest(output_dir=str(tmp_path)),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: {"bullet_points": ["5-in-1-bullet"]},
            call_llm_with_empty_retry=call_llm_with_empty_retry,
            strip_thinking=lambda x: x,
            parse_response=lambda x: {},
        )
        # The 5-in-1 fallback succeeded → result is the structured dict.
        assert result["bullet_points"] == ["5-in-1-bullet"]
        # The result carries the source_glossary key (the 5-in-1 fallback
        # path stashed it — the V0.5.6 audit's gap closure).
        assert "source_glossary" in result, (
            "the 5-in-1 fallback path must ALSO stash the source_glossary "
            "key on the result dict (the V0.5.6 audit's gap — the 5-in-1 "
            "path had no glossary wired)"
        )
        assert len(result["source_glossary"]["names"]) == 3
        assert result["source_glossary"]["names"][0]["name"] == "Bak"
        # The .glossary.md file was written under tmp_path.
        glossary_file = (
            tmp_path / "summaries" / ".glossaries" / "Fallback Chapter Heading.glossary.md"
        )
        assert glossary_file.exists()
        # The side-channel cache was populated.
        stashed = get_chapter_glossary("Fallback Chapter Heading")
        assert stashed is not None
        assert len(stashed["names"]) == 3
        clear_glossary_cache()

    def test_glossary_extracted_in_5_in_1_raw_fallback_path(self, monkeypatch, tmp_path):
        """When ``chunked_summarize`` returns None AND the structured-JSON
        branch returns None (the raw XML fallback fires), the glossary is
        STILL extracted via ``_extract_glossary_for_call`` (the 3rd return
        path in primary_call.py)."""
        from core.summarisation.verification_phase import (
            clear_glossary_cache,
            get_chapter_glossary,
        )

        # Test isolation: reset the GPU temp cache + the glossary side-channel.
        self._reset_gpu_temp_cache()
        self._no_gpu(monkeypatch)
        self._set_tokens(monkeypatch, 5000)
        clear_glossary_cache()

        # Track which call_llm_with_empty_retry invocation returns the
        # glossary (the 5-in-1 raw-fallback path makes 2 LLM calls: the
        # main 5-in-1 raw XML call + the separate glossary-extraction call).
        # The FIRST call (the 5-in-1 raw XML) returns "<xml>raw</xml>";
        # the SECOND call (the glossary) returns the glossary block.
        call_count = {"n": 0}

        def call_llm_with_empty_retry(prompt, model=None, temperature=None, max_tokens=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "<xml>raw</xml>"  # the 5-in-1 raw XML response
            return _GLOSSARY_LLM_RESPONSE  # the glossary response

        # chunked returns None (master-summary failed) + structured returns
        # None (structured-JSON branch failed) → the raw XML fallback fires.
        def chunked(*a, **k):
            return None

        result = pc_mod.summarize_with_model(
            "Raw Fallback Heading",
            _SOURCE_TEXT_FIXTURE,
            "test-model",
            0.7,
            request=_FakeRequest(output_dir=str(tmp_path)),
            log=lambda m, l="INFO": None,
            chunked_summarize=chunked,
            build_prompt=lambda *a, **k: "P",
            call_llm_structured=lambda *a, **k: None,  # structured failed
            call_llm_with_empty_retry=call_llm_with_empty_retry,  # raw + glossary
            strip_thinking=lambda x: x,
            parse_response=lambda x: {"bullet_points": ["raw-bullet"]},
        )
        # The raw XML fallback succeeded → result is the parsed dict.
        assert result["bullet_points"] == ["raw-bullet"]
        # The result carries the source_glossary key (the 3rd return path —
        # the raw 5-in-1 fallback).
        assert "source_glossary" in result, (
            "the raw 5-in-1 fallback path must ALSO stash the source_glossary "
            "key on the result dict (the 3rd return path in primary_call.py)"
        )
        assert len(result["source_glossary"]["names"]) == 3
        assert result["source_glossary"]["names"][0]["name"] == "Bak"
        # The side-channel cache was populated.
        stashed = get_chapter_glossary("Raw Fallback Heading")
        assert stashed is not None
        assert len(stashed["names"]) == 3
        # The .glossary.md file was written under tmp_path.
        glossary_file = tmp_path / "summaries" / ".glossaries" / "Raw Fallback Heading.glossary.md"
        assert glossary_file.exists()
        clear_glossary_cache()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (mirror of tests/test_primary_call.py's _FakeRequest — the
# test_v057 file uses the same pattern).
# ─────────────────────────────────────────────────────────────────────────────


class _FakeRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
