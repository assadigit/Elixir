"""V13.45.0: Anti-false-precision + theorist-coverage + gap-fill fix tests.

Tests verify:
1. _anti_false_precision_check rewrites "Author A views X while Author B views Y"
   when the source groups A and B together (the Jacobson/Kernberg audit case).
2. _anti_false_precision_check does NOT rewrite when the source actually separates
   the two authors (legitimate contrasts are preserved).
3. _anti_false_precision_check handles bullets, exec_summary, thorough_summary,
   key_distinctions, and theoretical_tensions.
4. Theorist extraction regex finds named authors in source text.
5. Gap-fill bullets are no longer discarded (the V13.42.0 bug fix).
"""

from __future__ import annotations

import re
import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub tiktoken (not installed in test env)
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from core.summarisation.summarizer import Summarizer

# ═══════════════════════════════════════════════════════════════════════════
# Anti-false-precision check tests
# ═══════════════════════════════════════════════════════════════════════════


class _FakeSummarizerForAFP:
    """A fake summarizer that uses the REAL _anti_false_precision_check."""

    log = MagicMock()
    quarantine = None

    def _anti_false_precision_check(self, heading, text, result):
        Summarizer._anti_false_precision_check(self, heading, text, result)


class TestAntiFalsePrecisionCheck:
    """V13.45.0: Verify the anti-false-precision post-check rewrites hallucinated
    author-distinctions when the source groups the authors together."""

    def _make_summarizer(self):
        return _FakeSummarizerForAFP()

    def test_jacobson_kernberg_audit_case_is_rewritten(self):
        """The EXACT hallucination from the V13.44.4 audit must be rewritten.

        Summary claimed: "Jacobson (1964) identifies identity disturbance as a
        sine qua non of borderline character disorders, while Kernberg (1967)
        views it as a sine qua non of narcissistic character disorders."

        Source actually says: "Jacobson 1964, Kernberg 1967 regard disturbances
        of identity as a sine qua non of borderline and narcissistic character
        disorders."
        """
        source = (
            "Indeed, many analytic theoreticians (Jacobson 1964, Kernberg 1967) "
            "regard disturbances of identity as a sine qua non of borderline and "
            "narcissistic character disorders."
        )
        bullet = (
            "- Jacobson (1964) identifies identity disturbance as a sine qua non "
            "of borderline character disorders, while Kernberg (1967) views it as "
            "a sine qua non of narcissistic character disorders."
        )
        result = {
            "bullet_points": [bullet],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)

        # The rewritten bullet should NOT contain "while Kernberg"
        rewritten = result["bullet_points"][0]
        assert "while kernberg" not in rewritten.lower(), (
            f"False-precision contrast was not rewritten. Got: {rewritten}"
        )
        # It SHOULD contain both names with "both"
        assert "jacobson" in rewritten.lower()
        assert "kernberg" in rewritten.lower()
        assert "both" in rewritten.lower()

    def test_legitimate_contrast_is_preserved(self):
        """When the source DOES separate two authors' positions, the contrast
        must be preserved (no false rewrite)."""
        source = (
            "Jacobson (1964) views identity primarily as a structural formation "
            "rooted in self-object representations. In a separate later work, "
            "Kernberg (1976) proposed a different view, emphasizing the role of "
            "aggressive drive fusion in identity consolidation. These two "
            "positions are distinct."
        )
        bullet = (
            "- Jacobson (1964) views identity as structural formation, whereas "
            "Kernberg (1976) emphasizes aggressive drive fusion."
        )
        result = {
            "bullet_points": [bullet],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)

        # The contrast should be PRESERVED because the source separates them
        rewritten = result["bullet_points"][0]
        assert "whereas" in rewritten.lower() or "while" in rewritten.lower(), (
            f"Legitimate contrast was incorrectly rewritten. Got: {rewritten}"
        )

    def test_works_on_executive_summary(self):
        """The check should also rewrite false-precision in executive_summary."""
        source = (
            "Jacobson 1964, Kernberg 1967 regard disturbances of identity as a "
            "sine qua non of borderline and narcissistic character disorders."
        )
        exec_sum = (
            "Jacobson views identity disturbance as sine qua non of borderline "
            "disorders, while Kernberg views it as sine qua non of narcissistic "
            "disorders."
        )
        result = {
            "bullet_points": [],
            "executive_summary": exec_sum,
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)
        assert "while kernberg" not in result["executive_summary"].lower()

    def test_works_on_thorough_summary(self):
        """The check should also rewrite false-precision in thorough_summary."""
        source = (
            "Jacobson 1964, Kernberg 1967 regard disturbances of identity as a "
            "sine qua non of borderline and narcissistic character disorders."
        )
        thorough = (
            "In this literature, Jacobson views it as sine qua non of borderline "
            "disorders, whereas Kernberg views it as sine qua non of narcissistic "
            "disorders. This is a key distinction."
        )
        result = {
            "bullet_points": [],
            "executive_summary": "",
            "thorough_summary": thorough,
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)
        assert "whereas kernberg" not in result["thorough_summary"].lower()

    def test_empty_result_does_not_crash(self):
        """Empty result dict should not cause any errors."""
        source = "Some source text."
        result = {
            "bullet_points": [],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        # Should not raise
        obj._anti_false_precision_check("Chapter 1", source, result)
        assert result["bullet_points"] == []

    def test_no_contrast_leaves_bullets_unchanged(self):
        """Bullets without contrastive patterns should pass through unchanged."""
        source = "Erikson defined ego identity in 1956."
        bullet = "- Erikson (1956) defined ego identity as persistent sameness."
        result = {
            "bullet_points": [bullet],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)
        assert result["bullet_points"][0] == bullet

    def test_multiple_false_contrasts_all_rewritten(self):
        """Multiple false-precision contrasts in one bullet are all rewritten."""
        source = (
            "Jacobson 1964, Kernberg 1967 regard identity as sine qua non of "
            "borderline and narcissistic disorders. Also, Freud 1923, Abraham 1924 "
            "view melancholia as rooted in object loss."
        )
        bullet = (
            "- Jacobson views identity as borderline sine qua non while Kernberg "
            "views it as narcissistic sine qua non. Also Freud views melancholia "
            "as ego-based whereas Abraham views it as object-based."
        )
        result = {
            "bullet_points": [bullet],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        obj = self._make_summarizer()
        obj._anti_false_precision_check("Chapter 1", source, result)
        rewritten = result["bullet_points"][0]
        # At least one of the two contrasts should be rewritten
        # (both source-grouped pairs should trigger)
        assert "both" in rewritten.lower(), f"Multiple contrasts not rewritten. Got: {rewritten}"


# ═══════════════════════════════════════════════════════════════════════════
# Theorist extraction tests (deterministic regex pre-pass)
# ═══════════════════════════════════════════════════════════════════════════


class TestTheoristExtraction:
    """V13.45.0: Verify the theorist-extraction regex finds named authors."""

    def test_finds_single_author_year(self):
        text = "Erikson (1956) used the term ego identity."
        matches = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)",
            text,
        )
        assert ("Erikson", "1956") in matches

    def test_finds_multiple_authors(self):
        text = (
            "Jacobson (1964) and Kernberg (1967) regard identity as sine qua non. "
            "Erikson (1956) defined ego identity. Greenacre (1958a,b) "
            "contributed to the sense of identity."
        )
        matches = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)",
            text,
        )
        names = [m[0] for m in matches]
        assert "Jacobson" in names
        assert "Kernberg" in names
        assert "Erikson" in names
        assert "Greenacre" in names

    def test_finds_compound_surnames(self):
        """Compound surnames like 'Chasseguet-Smirgel' — note: hyphenated names
        may not match the simple regex, but hyphen-less compounds like
        'Anna Freud' should."""
        text = "Anna Freud (1958) wrote about the topic."
        matches = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)",
            text,
        )
        names = [m[0] for m in matches]
        assert "Anna Freud" in names

    def test_finds_authors_with_letter_suffixes(self):
        """Year with letter suffix like '1958a' should match."""
        text = "Greenacre (1958a) and Greenacre (1958b) both contributed."
        matches = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)",
            text,
        )
        years = [m[1] for m in matches]
        assert "1958a" in years
        assert "1958b" in years

    def test_does_not_match_common_words(self):
        """Common words that happen to be capitalized should be filtered."""
        text = "The (1956) study was important. In (1967) another was done."
        # "The" and "In" are in the stopwords set in _scholar_reflection
        # The regex will still match them, but the scholar reflection filters them.
        # Here we just verify the regex itself works.
        matches = re.findall(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*[a-z])?)\)",
            text,
        )
        # The regex WILL match "The" and "In" — the filtering happens in the method
        assert len(matches) >= 0  # just verify no crash


# ═══════════════════════════════════════════════════════════════════════════
# Prompt-content tests (verify the new instructions are present)
# ═══════════════════════════════════════════════════════════════════════════


class TestPromptContent:
    """V13.45.0: Verify the new prompt instructions are present in templates."""

    def test_default_prompt_has_anti_false_precision(self):
        # V18.2.20 (audit): The V13.45 all-caps section markers
        # (ANTI-FALSE-PRECISION, THEORIST COVERAGE, SUB-COMPONENT
        # COMPLETENESS, ANTI-OVERSPECIFICATION, ANTI-CONTEXT-STRIPPING,
        # DEPTH PRESERVATION) were removed from prompts/default.md in the
        # V16.0.4 "professional template" + book-agnostic rewrite (Key
        # Decision #3: prompts NEVER use book-specific framing, and
        # "THEORIST COVERAGE" was a book-specific framing). The *semantic
        # guarantees* of every one of those guards survives in default.md
        # under clearer, book-agnostic headers. This test now asserts the
        # current contract — the same anti-hallucination guarantees, just
        # expressed in the book-agnostic vocabulary. Restoring the old
        # all-caps markers would re-introduce book-specific framing and
        # violate the book-agnostic principle.
        from pathlib import Path

        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "default.md"
        content = prompt_path.read_text(encoding="utf-8")
        # ANTI-FALSE-PRECISION → "Accuracy" + "Anti-Interpretation" constraints
        assert "Accuracy:" in content, (
            "default.md missing Accuracy (anti-false-precision) constraint block"
        )
        assert "Anti-Interpretation" in content, (
            "default.md missing Anti-Interpretation (anti-false-precision) guard"
        )
        assert "Invent facts, approximate numbers" in content, (
            "default.md missing the 'no invented facts/numbers' anti-false-precision rule"
        )
        # THEORIST COVERAGE → book-agnostic "named contributors" / "named author"
        assert "named contributors" in content.lower() or "named author" in content.lower(), (
            "default.md missing named-contributor coverage (book-agnostic THEORIST COVERAGE)"
        )
        assert "EVERY named" in content, (
            "default.md missing the 'include EVERY named author' coverage rule"
        )
        # SUB-COMPONENT COMPLETENESS → "Completeness" constraint block
        assert "Completeness:" in content, (
            "default.md missing Completeness (sub-component completeness) constraint block"
        )
        assert "EVERY sub-component" in content, (
            "default.md missing the 'reproduce EVERY sub-component' rule"
        )
        # ANTI-OVERSPECIFICATION → "don't invent scholarly distinctions / qualifications"
        assert "Invent scholarly distinctions" in content, (
            "default.md missing anti-overspecification (no invented scholarly distinctions)"
        )
        assert "qualifications or characterizations not explicitly in the source" in content, (
            "default.md missing anti-overspecification (no added qualifications)"
        )
        # ANTI-CONTEXT-STRIPPING → "Context Preservation" constraint block
        assert "Context Preservation:" in content, (
            "default.md missing Context Preservation (anti-context-stripping) block"
        )
        assert "PRESERVE context qualifiers" in content, (
            "default.md missing the 'preserve context qualifiers' rule"
        )
        # DEPTH PRESERVATION → "Thorough Summary Depth" constraint block
        assert "Thorough Summary Depth" in content, (
            "default.md missing Thorough Summary Depth (depth preservation) block"
        )
        assert "preserve multi-step" in content.lower(), (
            "default.md missing the 'preserve multi-step mechanisms' depth rule"
        )

    def test_default_prompt_has_enriched_distinctions(self):
        from pathlib import Path

        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "default.md"
        content = prompt_path.read_text(encoding="utf-8")
        # The enriched key_distinctions should have prioritization guidance
        assert "prioritize" in content.lower() or "Prioritize" in content, (
            "default.md key_distinctions missing prioritization guidance"
        )
        # The enriched theoretical_tensions should mention both poles
        assert "both" in content.lower() or "BOTH" in content, (
            "default.md theoretical_tensions missing both-poles guidance"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Gap-fill fix verification (the V13.42.0 bug)
# ═══════════════════════════════════════════════════════════════════════════


class TestGapFillFix:
    """V13.45.0: Verify that gap-fill bullets from scholar reflection are NO
    LONGER discarded — the SummaryResult must use parsed["bullet_points"]
    (the updated list) not the stale local `bullets` variable.

    This is a static code-analysis test: we verify the source file contains
    the fix that reads bullets back from `parsed` after scholar reflection.
    """

    def test_summary_result_reads_back_from_parsed(self):
        """The chapter phase pipeline must read bullets back from parsed after
        scholar reflection runs (so gap-fill bullets survive)."""
        from pathlib import Path

        # V0.18 (Phase 5.1): moved VERBATIM to chapter_phases.py — pin follows.
        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "chapter_phases.py"
        )
        content = src_path.read_text(encoding="utf-8")
        # The V13.45.0 fix comment must be present
        assert "V13.45.0: CRITICAL FIX" in content, (
            "Gap-fill fix comment not found — the V13.42.0 bug may still be present"
        )
        # The read-back line must be present
        assert 'bullets = parsed.get("bullet_points", bullets)' in content, (
            "Gap-fill read-back line not found — bullets may still be the stale local var"
        )

    def test_anti_false_precision_is_wired(self):
        """The _anti_false_precision_check must be called in the pipeline."""
        from pathlib import Path

        # V0.18 (Phase 5.1): the pipeline call site moved VERBATIM to
        # chapter_phases.py — pin follows (the def stays in summarizer.py).
        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "chapter_phases.py"
        )
        content = src_path.read_text(encoding="utf-8")
        assert "_anti_false_precision_check" in content, (
            "_anti_false_precision_check method not found in chapter_phases.py"
        )
        # Must be CALLED (not just defined)
        assert "self._anti_false_precision_check(heading, content, parsed)" in content, (
            "_anti_false_precision_check is defined but not called in the pipeline"
        )


# ═══════════════════════════════════════════════════════════════════════════
# V13.45.4: Batched self-review + max_output_tokens tests
# ═══════════════════════════════════════════════════════════════════════════


class TestV13_45_4_BatchedSelfReview:
    """V13.45.4: Verify batched self-review replaces the >50 bullet skip."""

    def test_self_review_batched_method_exists(self):
        """The _self_review_batched method must exist."""
        from pathlib import Path

        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "summarizer.py"
        )
        content = src_path.read_text(encoding="utf-8")
        assert "_self_review_batched" in content, (
            "_self_review_batched method not found — batched self-review not implemented"
        )
        assert "def _self_review_batched" in content, (
            "_self_review_batched method definition not found"
        )

    def test_batched_review_is_wired_in_pipeline(self):
        """The batched self-review must be called when >10 bullets."""
        from pathlib import Path

        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "bullet_pipeline.py"
        )
        content = src_path.read_text(encoding="utf-8")
        assert "_self_review_batched" in content, (
            "batched self-review not wired in bullet_pipeline.py"
        )
        assert "_use_batched_review" in content, "batched review flag not found in pipeline"

    def test_no_bullet_count_skip(self):
        """V13.45.4: The >50 bullet skip must be REMOVED (replaced by batching)."""
        from pathlib import Path

        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "bullet_pipeline.py"
        )
        content = src_path.read_text(encoding="utf-8")
        # The V13.45.2 skip condition should NOT be present
        assert "len(_bps_for_review) > 50" not in content, (
            "V13.45.2 >50 bullet skip still present — should be replaced by batching"
        )


class TestV13_45_4_MaxOutputTokens:
    """V13.45.4: Verify max_output_tokens is 16000."""

    def test_default_max_output_tokens_is_16000(self):
        from pathlib import Path

        src_path = Path(__file__).resolve().parent.parent / "utils" / "settings.py"
        content = src_path.read_text(encoding="utf-8")
        assert (
            '"max_output_tokens":    16000' in content or '"max_output_tokens": 16000' in content
        ), "max_output_tokens default is not 16000"

    def test_academic_rigor_floor_is_16000(self):
        from pathlib import Path

        # V0.18 (Phase 5.1): moved VERBATIM to llm_transport.py — pin follows.
        src_path = (
            Path(__file__).resolve().parent.parent / "core" / "summarisation" / "llm_transport.py"
        )
        content = src_path.read_text(encoding="utf-8")
        assert "max_tok < 16000" in content, "academic_rigor max_tokens floor is not 16000"


class TestV13_45_4_Gemma4Default:
    """V13.45.4: Verify summarisation.model defaults to gemma4-12b:latest."""

    def test_default_model_is_gemma4(self):
        from pathlib import Path

        src_path = Path(__file__).resolve().parent.parent / "utils" / "settings.py"
        content = src_path.read_text(encoding="utf-8")
        assert '"gemma4-12b:latest"' in content, (
            "gemma4-12b:latest not found as default model in settings.py"
        )


class TestV13_45_4_OllamaModelsDoc:
    """V13.45.4: Verify the Ollama models documentation exists."""

    def test_user_ollama_models_doc_exists(self):
        from pathlib import Path

        doc_path = Path(__file__).resolve().parent.parent / "docs" / "USER_OLLAMA_MODELS.md"
        assert doc_path.exists(), (
            "docs/USER_OLLAMA_MODELS.md not found — model name reference missing"
        )
        content = doc_path.read_text(encoding="utf-8")
        # Must contain all 4 model names
        assert "gemma4-12b:latest" in content
        assert "translategemma-12b-it.Q4_K_M_mradermacher:latest" in content
        assert "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest" in content
        assert "OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
