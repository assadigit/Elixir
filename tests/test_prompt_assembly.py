"""V18.6 (Phase 4, Task 4.2) - Prompt-assembly characterization tests.

Byte-for-byte stability gate for the 5 pure functions extracted to
prompt_assembly.py. Each test captures a canned input -> golden prompt
string. If the extraction changes the output by even one character, the
test fails.

V18.20.4.7 (P5 phase 2 / W-a3): the dead V18.6.3 twin
(``build_primary_prompt`` + ``PromptContext`` — the verbatim copy kept
after the V18.6.4 rollback restored the live inline
``Summarizer._build_prompt``) was deleted from prompt_assembly.py; the
section-0 characterization tests for that dead function were removed
with it. The 5 live-function sections below are unchanged.

Run: pytest tests/test_prompt_assembly.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so the import chain works
if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E: pass
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules['tiktoken'] = tk

from core.summarisation.prompt_assembly import (
    build_chunked_prompt,
    build_dedicated_bullet_prompt,
    build_dedicated_thorough_prompt,
    build_missing_keywords_reprompt,
    build_thorough_followup,
)

# == 1. build_thorough_followup ==


class TestBuildThoroughFollowup:
    def test_english_language(self):
        """English language instruction is correct."""
        result = build_thorough_followup("Ch.1", "Chapter text here.", "Exec summary.", "en")
        assert "Write in English." in result
        assert "Ch.1" in result
        assert "Exec summary." in result
        assert "Chapter text here." in result
        assert "<thorough_summary>" in result

    def test_persian_language(self):
        """Persian language instruction is correct."""
        result = build_thorough_followup("Ch.1", "Text.", "Exec.", "fa")
        assert "Write in Persian (Farsi)." in result

    def test_exec_sum_truncated_to_400_chars(self):
        """Executive summary is truncated to first 400 chars."""
        long_exec = "A" * 500
        result = build_thorough_followup("Ch.1", "Text.", long_exec, "en")
        assert "A" * 400 in result
        assert "A" * 500 not in result  # truncated

    def test_contains_required_sections(self):
        """The prompt contains all required structural sections.

        V0.05 (F9b): the word target is SOURCE-SCALED (length_policy), not
        the absolute 800-1200 — a tiny source gets a tiny target, and the
        compression contract forbids padding. Pinned: the scaled phrase for
        the exact 2-word source, the prose instruction, and the contract.
        """
        result = build_thorough_followup("Ch.1", "Text.", "Exec.", "en")
        # 1-word source -> a tiny scaled target ("N-N word"), never 800-1200
        import re as _re
        assert _re.search(r"\b\d+-\d+ word", result)  # source-scaled word count
        assert "800-1200" not in result  # the absolute demand is gone
        assert "FLOWING PROSE PARAGRAPHS" in result
        assert "SHORTER than its source" in result  # compression contract


# == 2. build_dedicated_thorough_prompt ==


class TestBuildDedicatedThoroughPrompt:
    def test_english_basic(self):
        """Basic English prompt structure is correct."""
        result = build_dedicated_thorough_prompt("Ch.1", "Chapter text.", "Exec summary.", ["bullet 1", "bullet 2"], "en")
        assert "### ROLE ###" in result
        assert "Write in English." in result
        assert "Ch.1" in result
        assert "Exec summary." in result
        assert "- bullet 1" in result
        assert "- bullet 2" in result
        assert "<thorough_summary>" in result

    def test_persian_language(self):
        """Persian language instruction."""
        result = build_dedicated_thorough_prompt("Ch.1", "Text.", "Exec.", [], "fa")
        assert "Write in Persian (Farsi)." in result

    def test_bullets_capped_at_30(self):
        """Bullets list is capped at 30 entries."""
        bullets = [f"bullet {i}" for i in range(50)]
        result = build_dedicated_thorough_prompt("Ch.1", "Text.", "Exec.", bullets, "en")
        assert "- bullet 0" in result
        assert "- bullet 29" in result
        assert "- bullet 30" not in result  # capped

    def test_empty_bullets_shows_placeholder(self):
        """Empty bullets list shows '(no bullets yet)'."""
        result = build_dedicated_thorough_prompt("Ch.1", "Text.", "Exec.", [], "en")
        assert "(no bullets yet)" in result

    def test_text_truncated_to_40000_chars(self):
        """Source text is truncated to 40000 chars."""
        long_text = "A" * 50000
        result = build_dedicated_thorough_prompt("Ch.1", long_text, "Exec.", [], "en")
        # The _source slice should be 40000 chars
        assert "A" * 40000 in result
        assert "A" * 50000 not in result

    def test_exec_sum_truncated_to_600_chars(self):
        """Executive summary is truncated to first 600 chars."""
        long_exec = "B" * 700
        result = build_dedicated_thorough_prompt("Ch.1", "Text.", long_exec, [], "en")
        assert "B" * 600 in result
        assert "B" * 700 not in result


# == 3. build_dedicated_bullet_prompt ==


class TestBuildDedicatedBulletPrompt:
    def test_english_basic(self):
        """Basic English prompt structure.

        V0.05 (F9b): the bullet-count demand is SOURCE-SCALED (the absolute
        "30-50" forced padding on short chapters).
        """
        result = build_dedicated_bullet_prompt("Ch.1", "Text.", "Exec.", ["existing bullet"], "en")
        assert "### ROLE ###" in result
        assert "Write in English." in result
        assert "Ch.1" in result
        assert "existing bullet" in result
        assert "30-50 NEW bullet points" not in result  # absolute demand gone
        assert "one distinct takeaway per ~50 source words" in result

    def test_persian_language(self):
        """Persian language instruction."""
        result = build_dedicated_bullet_prompt("Ch.1", "Text.", "Exec.", [], "fa")
        assert "Write in Persian (Farsi)." in result

    def test_existing_bullets_capped_at_20(self):
        """Existing bullets list is capped at 20 entries."""
        bullets = [f"bullet {i}" for i in range(30)]
        result = build_dedicated_bullet_prompt("Ch.1", "Text.", "Exec.", bullets, "en")
        assert "- bullet 0" in result
        assert "- bullet 19" in result
        assert "- bullet 20" not in result

    def test_empty_existing_shows_placeholder(self):
        """Empty existing bullets shows '(none yet)'."""
        result = build_dedicated_bullet_prompt("Ch.1", "Text.", "Exec.", [], "en")
        assert "(none yet)" in result

    def test_text_truncated_to_40000(self):
        """Source text truncated to 40000 chars."""
        long_text = "C" * 50000
        result = build_dedicated_bullet_prompt("Ch.1", long_text, "Exec.", [], "en")
        assert "C" * 40000 in result

    def test_exec_truncated_to_400(self):
        """Executive summary truncated to 400 chars."""
        long_exec = "D" * 500
        result = build_dedicated_bullet_prompt("Ch.1", "Text.", long_exec, [], "en")
        assert "D" * 400 in result
        assert "D" * 500 not in result


# == 4. build_missing_keywords_reprompt ==


class TestBuildMissingKeywordsReprompt:
    def test_english_basic(self):
        """Basic English prompt with missing keywords."""
        result = build_missing_keywords_reprompt("Ch.1", "Chapter text.", ["identity", "ego"], "en")
        assert "Write in English." in result
        assert "Ch.1" in result
        assert "identity" in result
        assert "ego" in result
        assert "Chapter text." in result

    def test_persian_language(self):
        """Persian language instruction."""
        result = build_missing_keywords_reprompt("Ch.1", "Text.", ["kw"], "fa")
        assert "Write in Persian (Farsi)." in result

    def test_keywords_joined_with_commas(self):
        """Multiple keywords are joined with ', '."""
        result = build_missing_keywords_reprompt("Ch.1", "Text.", ["alpha", "beta", "gamma"], "en")
        assert "alpha, beta, gamma" in result

    def test_contains_rules(self):
        """Prompt contains the bullet rules."""
        result = build_missing_keywords_reprompt("Ch.1", "Text.", ["kw"], "en")
        assert "2-5 bullet points" in result
        assert "self-contained claim" in result


# == 5. build_chunked_prompt ==


class TestBuildChunkedPrompt:
    def test_chunk_1_replaces_xml_output_format(self):
        """Chunk 1 replaces the 5-section XML output with 3-section chunk."""
        # Build a fake full prompt with the XML output format
        full_prompt = """Some preamble.

You MUST output exactly these five XML sections:

<executive_summary>
...
</executive_summary>

<bullet_points>
...
</bullet_points>

<thorough_summary>
...
</thorough_summary>

<key_distinctions>
...
</key_distinctions>

<theoretical_tensions>
...
</theoretical_tensions>"""
        result = build_chunked_prompt("Ch.1", "Text.", full_prompt, chunk=1)
        assert "chunk 1 of 2" in result
        assert "<executive_summary>" in result
        assert "<bullet_points>" in result
        assert "<thorough_summary>" in result
        assert "Do NOT output key_distinctions" in result

    def test_chunk_2_replaces_xml_output_format(self):
        """Chunk 2 replaces the 5-section XML output with 2-section chunk."""
        full_prompt = """You MUST output exactly these five XML sections:

<executive_summary>...</executive_summary>
<bullet_points>...</bullet_points>
<thorough_summary>...</thorough_summary>
<key_distinctions>...</key_distinctions>
<theoretical_tensions>...</theoretical_tensions>"""
        result = build_chunked_prompt("Ch.1", "Text.", full_prompt, chunk=2)
        assert "chunk 2 of 2" in result
        assert "<key_distinctions>" in result
        assert "<theoretical_tensions>" in result
        assert "Do NOT output executive_summary" in result

    def test_chunk_1_json_format(self):
        """Chunk 1 works with the JSON (academic_rigor) output format."""
        full_prompt = """Output a JSON object with these sections:
- "executive_summary": 3-5 findings.
- "bullet_points": 15-25 findings.
- "thorough_summary": 15-25 findings.
- "key_distinctions": 2-5 distinctions.
- "theoretical_tensions": 2-4 tensions."""
        result = build_chunked_prompt("Ch.1", "Text.", full_prompt, chunk=1)
        assert "chunk 1 of 2" in result
        assert "<executive_summary>" in result

    def test_fallback_appends_when_no_match(self):
        """When no output-format pattern matches, the chunk instruction is appended."""
        full_prompt = "A prompt with no recognizable output format section."
        result = build_chunked_prompt("Ch.1", "Text.", full_prompt, chunk=1)
        assert "A prompt with no recognizable output format section." in result
        assert "chunk 1 of 2" in result  # appended

    def test_preamble_preserved(self):
        """The preamble before the output format is preserved."""
        full_prompt = """IMPORTANT PREAMBLE TEXT

You MUST output exactly these five XML sections:

<executive_summary>...</executive_summary>"""
        result = build_chunked_prompt("Ch.1", "Text.", full_prompt, chunk=1)
        assert "IMPORTANT PREAMBLE TEXT" in result


# == 6. Cross-function consistency ==


class TestCrossFunctionConsistency:
    def test_all_functions_accept_language_param(self):
        """All 4 string-builder functions accept a language parameter."""
        # Just verify they don't crash with language="en" and "fa"
        for lang in ["en", "fa"]:
            assert build_thorough_followup("H", "T", "E", lang) is not None
            assert build_dedicated_thorough_prompt("H", "T", "E", [], lang) is not None
            assert build_dedicated_bullet_prompt("H", "T", "E", [], lang) is not None
            assert build_missing_keywords_reprompt("H", "T", ["k"], lang) is not None

    def test_all_functions_return_strings(self):
        """All functions return str (not None, not bytes)."""
        assert isinstance(build_thorough_followup("H", "T", "E", "en"), str)
        assert isinstance(build_dedicated_thorough_prompt("H", "T", "E", [], "en"), str)
        assert isinstance(build_dedicated_bullet_prompt("H", "T", "E", [], "en"), str)
        assert isinstance(build_missing_keywords_reprompt("H", "T", ["k"], "en"), str)
        assert isinstance(build_chunked_prompt("H", "T", "full", chunk=1), str)
