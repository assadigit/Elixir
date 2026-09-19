"""V18.2.21 (Phase 1.2) — Tests for the structured-output adapter.

Covers:
1. SummarySchema validates well-formed JSON
2. _extract_json handles bare JSON, markdown fences, preambles, trailing text
3. validate_summary_json returns None on malformed input (never raises)
4. supports_json_mode detects provider capabilities + low-bit quant exclusion
5. build_json_instruction produces the format directive
6. complete_structured adapter: success path, fallback path, provider-error path
7. Manual validation path (when pydantic absent) — simulated
8. Book-agnostic: schema is structural, no book-specific fields
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

from core.llm.structured_io import (
    SummarySchema,
    _extract_json,
    _manual_validate,
    build_json_instruction,
    complete_structured,
    supports_json_mode,
    validate_summary_json,
)


class TestExtractJson:
    def test_bare_json(self):
        raw = '{"a": 1}'
        assert _extract_json(raw) == '{"a": 1}'

    def test_markdown_fenced_json(self):
        raw = '```json\n{"a": 1}\n```'
        assert _extract_json(raw) == '{"a": 1}'

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"a": 1}\n```'
        assert _extract_json(raw) == '{"a": 1}'

    def test_preamble_before_json(self):
        raw = 'Here is the summary:\n{"a": 1}'
        assert _extract_json(raw) == '{"a": 1}'

    def test_trailing_text_after_json(self):
        raw = '{"a": 1}\n\nDone.'
        assert _extract_json(raw) == '{"a": 1}'

    def test_nested_braces(self):
        raw = '{"outer": {"inner": "value"}, "x": 1}'
        assert _extract_json(raw) == '{"outer": {"inner": "value"}, "x": 1}'

    def test_braces_inside_strings_ignored(self):
        raw = '{"text": "this { is not a close } really"}'
        assert _extract_json(raw) == '{"text": "this { is not a close } really"}'

    def test_escaped_quotes_in_strings(self):
        raw = '{"text": "he said \\"hi\\""}'
        result = _extract_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["text"] == 'he said "hi"'

    def test_no_json_returns_none(self):
        assert _extract_json("plain text no json") is None

    def test_empty_returns_none(self):
        assert _extract_json("") is None

    def test_unbalanced_braces_returns_none(self):
        assert _extract_json('{"a": 1') is None


class TestValidateSummaryJson:
    def _valid_json(self) -> str:
        return json.dumps(
            {
                "executive_summary": "A 150-word overview of the chapter.",
                "bullet_points": ["Bullet 1", "Bullet 2", "Bullet 3"],
                "thorough_summary": "An 800-word detailed analysis.",
                "key_distinctions": "Distinction A vs Distinction B.",
                "theoretical_tensions": "Tension X vs Tension Y.",
            }
        )

    def test_valid_json_returns_dict(self):
        result = validate_summary_json(self._valid_json())
        assert result is not None
        assert result["executive_summary"].startswith("A 150-word")
        assert len(result["bullet_points"]) == 3
        assert result["thorough_summary"].startswith("An 800-word")

    def test_optional_fields_null(self):
        data = json.loads(self._valid_json())
        data["key_distinctions"] = None
        data["theoretical_tensions"] = None
        result = validate_summary_json(json.dumps(data))
        assert result is not None
        assert result["key_distinctions"] is None
        assert result["theoretical_tensions"] is None

    def test_optional_fields_absent(self):
        data = json.loads(self._valid_json())
        del data["key_distinctions"]
        del data["theoretical_tensions"]
        result = validate_summary_json(json.dumps(data))
        assert result is not None
        # Optional absent → None in result
        assert result.get("key_distinctions") is None

    def test_missing_required_field_returns_none(self):
        data = json.loads(self._valid_json())
        del data["executive_summary"]
        assert validate_summary_json(json.dumps(data)) is None

    def test_wrong_type_returns_none(self):
        data = json.loads(self._valid_json())
        data["bullet_points"] = "not a list"
        assert validate_summary_json(json.dumps(data)) is None

    def test_bullet_points_not_strings_returns_none(self):
        data = json.loads(self._valid_json())
        data["bullet_points"] = ["valid", 123, "invalid"]
        assert validate_summary_json(json.dumps(data)) is None

    def test_malformed_json_returns_none(self):
        assert validate_summary_json("{not json}") is None

    def test_empty_returns_none(self):
        assert validate_summary_json("") is None
        assert validate_summary_json("   ") is None

    def test_markdown_fenced_json(self):
        raw = "```json\n" + self._valid_json() + "\n```"
        result = validate_summary_json(raw)
        assert result is not None
        assert result["executive_summary"].startswith("A 150-word")

    def test_never_raises(self):
        # Must never raise — always returns None on failure
        assert validate_summary_json(None) is None  # type: ignore[arg-type]
        assert validate_summary_json("{") is None
        assert validate_summary_json("}{}{") is None


class TestSupportsJsonMode:
    def test_ollama_gemma(self):
        assert supports_json_mode("ollama", "gemma4-12b:latest") is True

    def test_ollama_qwen_instruct(self):
        assert supports_json_mode("ollama", "Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest") is True

    def test_ollama_iq2_xxs_excluded(self):
        # Key Decision #5: low-bit quants can't follow complex JSON
        assert (
            supports_json_mode("ollama", "Qwen3.8-27B-UD-IQ2_XXS_Unsloth-instruct:latest") is False
        )

    def test_ollama_iq2_xs_excluded(self):
        assert supports_json_mode("ollama", "model-IQ2_XS:latest") is False

    def test_ollama_iq1_excluded(self):
        assert supports_json_mode("ollama", "model-IQ1_S:latest") is False

    def test_openai_compat(self):
        assert supports_json_mode("openai_compat", "gpt-4o") is True

    def test_claude(self):
        assert supports_json_mode("claude", "claude-3-5-sonnet") is True

    def test_freellmapi(self):
        assert supports_json_mode("freellmapi", "free-model") is True

    def test_unknown_provider(self):
        assert supports_json_mode("unknown", "some-model") is False

    def test_empty_inputs(self):
        assert supports_json_mode("", "model") is False
        assert supports_json_mode("ollama", "") is False


class TestBuildJsonInstruction:
    def test_contains_json_keys(self):
        instr = build_json_instruction(SummarySchema)
        assert "executive_summary" in instr
        assert "bullet_points" in instr
        assert "thorough_summary" in instr
        assert "key_distinctions" in instr
        assert "theoretical_tensions" in instr

    def test_mentions_json_format(self):
        instr = build_json_instruction(SummarySchema)
        assert "JSON" in instr
        assert "json" in instr.lower()


class TestManualValidate:
    """Test the no-pydantic fallback path directly."""

    def test_valid_dict(self):
        data = json.dumps(
            {
                "executive_summary": "x",
                "bullet_points": ["a", "b"],
                "thorough_summary": "y",
            }
        )
        result = _manual_validate(data)
        assert result is not None
        assert result["executive_summary"] == "x"
        assert result["bullet_points"] == ["a", "b"]

    def test_missing_required(self):
        data = json.dumps({"executive_summary": "x"})
        assert _manual_validate(data) is None

    def test_non_string_bullets(self):
        data = json.dumps(
            {
                "executive_summary": "x",
                "bullet_points": [1, 2, 3],
                "thorough_summary": "y",
            }
        )
        assert _manual_validate(data) is None


class TestCompleteStructured:
    def _valid_response(self) -> str:
        return json.dumps(
            {
                "executive_summary": "Overview.",
                "bullet_points": ["Point 1", "Point 2"],
                "thorough_summary": "Detailed analysis.",
                "key_distinctions": None,
                "theoretical_tensions": None,
            }
        )

    def test_success_path(self):
        provider = MagicMock()
        provider.complete.return_value = self._valid_response()
        result = complete_structured(provider, "Summarize this chapter.")
        assert result is not None
        assert result["executive_summary"] == "Overview."
        assert len(result["bullet_points"]) == 2
        # Verify json instruction was appended
        call_args = provider.complete.call_args
        assert (
            "JSON" in call_args.kwargs.get("prompt", call_args.args[0])
            or "JSON" in call_args.args[0]
        )

    def test_markdown_fenced_response(self):
        provider = MagicMock()
        provider.complete.return_value = f"```json\n{self._valid_response()}\n```"
        result = complete_structured(provider, "prompt")
        assert result is not None
        assert result["executive_summary"] == "Overview."

    def test_fallback_parser_on_invalid_json(self):
        provider = MagicMock()
        # Model returned XML instead of JSON (common with low-bit quants)
        provider.complete.return_value = (
            "<executive_summary>XML content</executive_summary>"
            "<bullet_points><point>b1</point></bullet_points>"
            "<thorough_summary>thorough</thorough_summary>"
        )
        fallback = MagicMock(return_value={"executive_summary": "XML content"})
        result = complete_structured(provider, "prompt", fallback_parser=fallback)
        assert result == {"executive_summary": "XML content"}
        fallback.assert_called_once()

    def test_none_response_returns_none(self):
        provider = MagicMock()
        provider.complete.return_value = None
        assert complete_structured(provider, "prompt") is None

    def test_empty_response_returns_none(self):
        provider = MagicMock()
        provider.complete.return_value = ""
        assert complete_structured(provider, "prompt") is None

    def test_provider_raises_returns_none(self):
        """When the provider raises, there's no response to fall back to."""
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("network error")
        result = complete_structured(provider, "prompt")
        assert result is None

    def test_provider_raises_with_fallback_still_none(self):
        """fallback_parser parses a *response*; if provider raised, there's
        no response to parse, so result is None (not the fallback)."""
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("network error")
        fallback = MagicMock(return_value={"executive_summary": "fallback"})
        result = complete_structured(provider, "prompt", fallback_parser=fallback)
        # No response was produced, so fallback_parser can't run.
        assert result is None
        fallback.assert_not_called()

    def test_provider_none(self):
        assert complete_structured(None, "prompt") is None


class TestBookAgnostic:
    """The schema must be structural-only — no book-specific fields."""

    def test_schema_has_no_book_fields(self):
        # The schema fields should be generic summary structure, not
        # psychology/biology/history-specific terms.
        from core.llm.structured_io import SummarySchema

        # Check the field names are generic
        if hasattr(SummarySchema, "model_fields"):
            field_names = set(SummarySchema.model_fields.keys())
        else:
            # Fallback for the no-pydantic shim
            field_names = {
                "executive_summary",
                "bullet_points",
                "thorough_summary",
                "key_distinctions",
                "theoretical_tensions",
            }
        forbidden = {"erikson", "freud", "darwin", "chapter_1", "psychoanalysis"}
        assert not any(f.lower() in field_names for f in forbidden), (
            f"Schema has book-specific fields: {field_names}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
