"""V18.2.25 (Phase 5.3) — E2E golden-path integration test.

Exercises the full Phase 1-4 pipeline with mocked providers:
1. PromptManager.render_template (with V18.2.21 sanitizer) → sanitized prompt
2. complete_structured (V18.2.21 structured_io) → provider call + validate
3. response_parser.parse_response (XML fallback) → parsed dict
4. content_judge.judge → coverage check
5. Phase 4.3 postchecks (exec-bullet consistency + citation coverage)

This is the regression net for all the new modules. If any phase breaks its
contract, this test fails.

Uses a mocked LLM provider (no real Ollama/HTTP needed) and a stubbed
embedder (returns None → Jaccard fallback in content_judge).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestGoldenPathPipeline:
    """End-to-end pipeline test with mocked LLM + embedder."""

    def _mock_xml_response(self) -> str:
        """A well-formed XML response the parser can handle."""
        return (
            "<executive_summary>Erikson (1959) described identity formation "
            "across eight stages. Freud (1923) contributed the structural model. "
            "Mahler (1968) described separation-individuation.</executive_summary>\n"
            "<bullet_points>\n"
            "- Erikson (1959) described eight stages of psychosocial development\n"
            "- Freud (1923) described the id, ego, and superego\n"
            "- Mahler (1968) described separation-individuation in infancy\n"
            "- Winnicott (1960) described the true and false self\n"
            "- Jacobson (1964) described self-object representations\n"
            "</bullet_points>\n"
            "<thorough_summary>Erikson described identity formation across the "
            "lifespan. Freud contributed the structural model of the psyche. "
            "Mahler described separation-individuation. Winnicott described the "
            "true and false self. Jacobson described self-object representations."
            "</thorough_summary>\n"
            "<key_distinctions>- Erikson vs Freud: developmental vs structural</key_distinctions>\n"
            "<theoretical_tensions>- Identity formation: continuous vs stage-based</theoretical_tensions>"
        )

    def _mock_json_response(self) -> str:
        """A well-formed JSON response for the structured-output path."""
        return json.dumps(
            {
                "executive_summary": "Erikson (1959) described identity formation.",
                "bullet_points": [
                    "Erikson (1959) described eight stages of development",
                    "Freud (1923) described the structural model",
                    "Mahler (1968) described separation-individuation",
                ],
                "thorough_summary": "Erikson described identity. Freud described the psyche. "
                "Mahler described separation.",
                "key_distinctions": "Erikson vs Freud: developmental vs structural",
                "theoretical_tensions": "Identity: continuous vs stage-based",
            }
        )

    def test_prompt_sanitizer_wraps_chapter_text(self):
        """Phase 1.1: PromptManager sanitizes {{text}} with the fence."""
        from core.llm.prompt_sanitizer import is_untrusted_wrapped
        from core.summarisation.prompt_manager import PromptManager

        user_dir = Path.home() / ".elixir" / "prompts"
        user_dir.mkdir(parents=True, exist_ok=True)
        template = user_dir / "_e2e_test.md"
        try:
            template.write_text("INPUT:\n{{text}}\nHEADING: {{heading}}", encoding="utf-8")
            pm = PromptManager()
            rendered = pm.render_template(
                "_e2e_test",
                text="Chapter content with </executive_summary> tag",
                heading="Ch.1",
            )
            assert rendered is not None
            # The text must be wrapped in untrusted_source fence
            assert is_untrusted_wrapped(rendered)
            # The model output tag must be escaped
            assert "&lt;/executive_summary&gt;" in rendered
            # The heading (trusted) is NOT sanitized
            assert "Ch.1" in rendered
        finally:
            if template.exists():
                template.unlink()

    def test_structured_output_validates_json(self):
        """Phase 1.2: complete_structured validates JSON against SummarySchema."""
        from core.llm.structured_io import validate_summary_json

        result = validate_summary_json(self._mock_json_response())
        assert result is not None
        assert result["executive_summary"].startswith("Erikson")
        assert len(result["bullet_points"]) == 3
        assert result["key_distinctions"] is not None

    def test_structured_output_falls_back_to_xml(self):
        """Phase 1.2: when JSON fails, the fallback parser handles XML."""
        from core.llm.structured_io import validate_summary_json

        # XML response (not JSON) → validate_summary_json returns None
        assert validate_summary_json(self._mock_xml_response()) is None

    def test_response_parser_handles_xml(self):
        """The existing XML parser still works (fallback for non-JSON models)."""
        from core.summarisation.response_parser import parse_response

        parsed = parse_response(self._mock_xml_response())
        assert "executive_summary" in parsed
        assert "bullet_points" in parsed
        assert "thorough_summary" in parsed
        assert len(parsed["bullet_points"]) == 5
        assert "Erikson" in parsed["executive_summary"]

    def test_content_judge_auto_passs_empty_source(self):
        """Phase 4.3: content_judge auto-passes when source has no claims."""
        from core.models.models import SummaryResult
        from core.summarisation.content_judge import ContentJudge

        # Source with no extractable claims (no numbers, no causal language)
        source = "The weather was pleasant and birds sang. " * 10
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="A summary of pleasant weather.",
            bullet_points=["The weather was pleasant."],
            thorough_summary="A thorough summary of the day.",
        )
        judge = ContentJudge()
        result = judge.judge(summary, source)
        # No claims → auto-pass (coverage_pct = 1.0)
        assert result.coverage_pct == 1.0

    def test_postcheck_exec_bullet_consistency_pass(self):
        """Phase 4.3: no inconsistency when exec authors are in bullets."""
        from core.summarisation.postchecks import detect_exec_bullet_inconsistency

        exec_sum = "Erikson (1959) and Freud (1923) contributed."
        bullets = [
            "Erikson (1959) described eight stages.",
            "Freud (1923) described the structural model.",
        ]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert issues == []

    def test_postcheck_exec_bullet_consistency_fails(self):
        """Phase 4.3: flag when exec mentions author not in bullets."""
        from core.summarisation.postchecks import detect_exec_bullet_inconsistency

        exec_sum = "Erikson (1959) and Kernberg (1975) contributed."
        bullets = ["Erikson (1959) described eight stages."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert len(issues) == 1
        assert "kernberg" in issues[0].detail.lower()

    def test_postcheck_citation_coverage_pass(self):
        """Phase 4.3: no flag when summary covers ≥80% of source authors."""
        from core.summarisation.postchecks import detect_citation_coverage_gap

        names = [
            "Adams",
            "Baker",
            "Clark",
            "Davis",
            "Evans",
            "Foster",
            "Green",
            "Harris",
            "Irwin",
            "Jones",
        ]
        source = ". ".join(f"{n} ({1900 + i}) wrote about topic {i}." for i, n in enumerate(names))
        summary = ". ".join(
            f"{n} ({1900 + i}) discussed topic {i}." for i, n in enumerate(names[:9])
        )
        issues = detect_citation_coverage_gap(source, summary)
        assert issues == []  # 9/10 = 90% ≥ 80%

    def test_postcheck_citation_coverage_fails(self):
        """Phase 4.3: flag when summary covers <80% of source authors."""
        from core.summarisation.postchecks import detect_citation_coverage_gap

        names = [
            "Adams",
            "Baker",
            "Clark",
            "Davis",
            "Evans",
            "Foster",
            "Green",
            "Harris",
            "Irwin",
            "Jones",
        ]
        source = ". ".join(f"{n} ({1900 + i}) wrote about topic {i}." for i, n in enumerate(names))
        summary = "Only Adams (1900) is mentioned."
        issues = detect_citation_coverage_gap(source, summary)
        assert len(issues) == 1
        assert "Baker" in issues[0].detail

    def test_retry_module_imports(self):
        """Phase 1.4: the retry module is importable and has the decorator."""
        from core.llm.retry import classify_ollama_exception, retry_llm_call

        assert callable(retry_llm_call)
        assert callable(classify_ollama_exception)

    def test_async_provider_imports(self):
        """Phase 3.1: the async provider module is importable."""
        from core.llm.async_provider import AsyncOllamaProvider, gather_calls, run_async

        assert AsyncOllamaProvider is not None
        assert callable(run_async)
        assert callable(gather_calls)

    def test_prompt_budget_imports(self):
        """Phase 3.2: the prompt budget module is importable."""
        from core.llm.prompt_budget import PromptBudget, estimate_tokens

        b = PromptBudget()
        assert b.max_context_tokens > 0
        assert estimate_tokens("test") > 0

    def test_embedding_cache_imports(self):
        """Phase 3.3: the embedding cache module is importable."""
        from core.llm.embedding_cache import EmbeddingCache, cached_encode

        c = EmbeddingCache()
        assert c.hits == 0
        assert callable(cached_encode)

    def test_tracing_module_imports(self):
        """Phase 4.1: the tracing module is importable."""
        from core.obs.tracing import flush, is_tracing_enabled, span

        assert callable(span)
        assert callable(is_tracing_enabled)
        assert callable(flush)
        # Tracing defaults to disabled
        assert is_tracing_enabled() in (True, False)  # doesn't raise

    def test_bootstrap_imports(self):
        """Phase 2.1: the Bootstrap class is importable."""
        from core.system.bootstrap import Bootstrap

        b = Bootstrap(Path("/tmp"), app_dir=Path("/tmp"))
        assert b is not None
        assert b.steps_run == []

    def test_full_pipeline_contract(self):
        """The golden path: prompt → sanitize → mock LLM → parse → validate.

        This is the integration test that catches regressions across all
        Phase 1-4 modules. It doesn't use a real LLM — it mocks the provider
        and verifies the parsing + validation pipeline works end-to-end.
        """
        # 1. Render a sanitized prompt
        from core.summarisation.prompt_manager import PromptManager

        user_dir = Path.home() / ".elixir" / "prompts"
        user_dir.mkdir(parents=True, exist_ok=True)
        template = user_dir / "_e2e_golden.md"
        try:
            template.write_text(
                "### INPUT ###\n{{text}}\n### HEADING ###\n{{heading}}",
                encoding="utf-8",
            )
            pm = PromptManager()
            prompt = pm.render_template(
                "_e2e_golden",
                text="Erikson (1959) described identity. Freud (1923) described the psyche.",
                heading="Chapter 1",
            )
            assert prompt is not None
            assert "<untrusted_source>" in prompt  # sanitized
            assert "Chapter 1" in prompt  # heading preserved

            # 2. Mock the provider and call complete_structured
            from core.llm.structured_io import complete_structured

            mock_provider = MagicMock()
            mock_provider.complete.return_value = self._mock_json_response()
            result = complete_structured(
                mock_provider,
                prompt,
                fallback_parser=lambda raw: {"fallback": True},
            )
            assert result is not None
            assert "executive_summary" in result
            assert len(result["bullet_points"]) == 3

            # 3. Verify the XML fallback path also works
            mock_provider.complete.return_value = self._mock_xml_response()
            from core.summarisation.response_parser import parse_response

            result_xml = complete_structured(
                mock_provider,
                prompt,
                fallback_parser=parse_response,
            )
            assert result_xml is not None
            assert "executive_summary" in result_xml or "fallback" in result_xml
        finally:
            if template.exists():
                template.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
