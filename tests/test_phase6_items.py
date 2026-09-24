"""V18.10 (Phase 6) - Tests for the 6 low-risk Phase 6 items.

Tests:
- 6.5: Modelfile integrity check (presence_penalty=1.5 for Qwen3)
- 6.6: Pytest golden-master audit plugin (stub mode)
- 6.7: GitHub Actions CI config exists

Run: pytest tests/test_phase6_items.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ════════════════════════════════════════════════════════════════════════════
# 6.5 — Modelfile integrity check
# ════════════════════════════════════════════════════════════════════════════


class TestModelfileIntegrity:
    """Tests for Modelfile integrity check (Phase 6.5)."""

    def test_module_imports(self):
        from core.llm.modelfile_integrity import (
            check_modelfile_integrity,
            parse_modelfile,
        )

        assert callable(check_modelfile_integrity)
        assert callable(parse_modelfile)

    def test_parse_modelfile(self):
        """parse_modelfile should extract PARAMETER lines."""
        from core.llm.modelfile_integrity import parse_modelfile

        modelfile = """
FROM ./qwen3.gguf
PARAMETER temperature 0.7
PARAMETER presence_penalty 1.5
PARAMETER num_ctx 32768
ADAPTER ./mmproj.gguf
"""
        params = parse_modelfile(modelfile)
        assert params["temperature"] == "0.7"
        assert params["presence_penalty"] == "1.5"
        assert params["num_ctx"] == "32768"

    def test_parse_modelfile_empty(self):
        """Empty modelfile should produce empty params."""
        from core.llm.modelfile_integrity import parse_modelfile

        assert parse_modelfile("") == {}

    def test_check_qwen3_presence_penalty_correct(self):
        """Qwen3 with presence_penalty=1.5 should pass."""
        from core.llm.modelfile_integrity import check_modelfile_integrity

        modelfile = """
PARAMETER temperature 0.7
PARAMETER presence_penalty 1.5
PARAMETER num_ctx 32768
"""
        with patch("core.llm.modelfile_integrity._run_ollama_show", return_value=modelfile):
            is_ok, issues = check_modelfile_integrity("qwen3:32b")
            assert is_ok is True
            assert len(issues) == 0

    def test_check_qwen3_presence_penalty_missing(self):
        """Qwen3 without presence_penalty should ERROR."""
        from core.llm.modelfile_integrity import check_modelfile_integrity

        modelfile = """
PARAMETER temperature 0.7
PARAMETER num_ctx 32768
"""
        with patch("core.llm.modelfile_integrity._run_ollama_show", return_value=modelfile):
            is_ok, issues = check_modelfile_integrity("qwen3:32b")
            assert is_ok is False
            assert any(i.param == "presence_penalty" for i in issues)

    def test_check_qwen3_presence_penalty_wrong(self):
        """Qwen3 with presence_penalty=0.0 should ERROR (thinking mode)."""
        from core.llm.modelfile_integrity import check_modelfile_integrity

        modelfile = """
PARAMETER temperature 0.7
PARAMETER presence_penalty 0.0
PARAMETER num_ctx 32768
"""
        with patch("core.llm.modelfile_integrity._run_ollama_show", return_value=modelfile):
            is_ok, issues = check_modelfile_integrity("qwen3:32b")
            assert is_ok is False
            pp_issues = [i for i in issues if i.param == "presence_penalty"]
            assert len(pp_issues) == 1
            assert pp_issues[0].actual == "0.0"

    def test_check_non_qwen_no_presence_penalty_check(self):
        """Non-Qwen models should NOT require presence_penalty."""
        from core.llm.modelfile_integrity import check_modelfile_integrity

        modelfile = """
PARAMETER temperature 0.7
PARAMETER num_ctx 8192
"""
        with patch("core.llm.modelfile_integrity._run_ollama_show", return_value=modelfile):
            is_ok, issues = check_modelfile_integrity("llama3:8b")
            # No presence_penalty check for non-Qwen
            assert not any(i.param == "presence_penalty" for i in issues)

    def test_check_ollama_unavailable_returns_ok(self):
        """If ollama show fails, should return (True, []) — fail-open."""
        from core.llm.modelfile_integrity import check_modelfile_integrity

        with patch("core.llm.modelfile_integrity._run_ollama_show", return_value=None):
            is_ok, issues = check_modelfile_integrity("qwen3:32b")
            assert is_ok is True
            assert len(issues) == 0


# ════════════════════════════════════════════════════════════════════════════
# 6.6 — Pytest golden-master audit plugin
# ════════════════════════════════════════════════════════════════════════════


class TestGoldenMasterAuditPlugin:
    """Tests for the pytest golden-master audit plugin (Phase 6.6)."""

    def test_module_imports(self):
        from tests.plugins.golden_master_audit import (
            AUDIT_SYSTEM_PROMPT,
            run_audit,
        )

        assert callable(run_audit)
        assert "Factual Consistency" in AUDIT_SYSTEM_PROMPT
        assert "Coverage" in AUDIT_SYSTEM_PROMPT
        assert "Clarity" in AUDIT_SYSTEM_PROMPT
        assert "Conciseness" in AUDIT_SYSTEM_PROMPT

    def test_extract_json_scorecard(self):
        """_extract_json_scorecard should extract the JSON from the end of a reply."""
        from tests.plugins.golden_master_audit import _extract_json_scorecard

        reply = """
Part 1: Detailed Report
Some analysis here.

Part 2: JSON Scorecard
```json
{
  "summary_id": "test",
  "overall_score": 9,
  "factual_consistency_score": 10,
  "coverage_score": 10,
  "clarity_score": 9,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 0,
  "verdict": "PASS",
  "justification": "Test audit."
}
```
"""
        scorecard = _extract_json_scorecard(reply)
        assert scorecard is not None
        assert scorecard["overall_score"] == 9
        assert scorecard["verdict"] == "PASS"

    def test_extract_json_scorecard_no_json(self):
        """Should return None if no JSON found."""
        from tests.plugins.golden_master_audit import _extract_json_scorecard

        assert _extract_json_scorecard("no json here") is None

    def test_run_audit_stub_mode(self, tmp_path):
        """run_audit with use_sdk=False should return a stub passing scorecard."""
        from tests.plugins.golden_master_audit import run_audit

        summary = tmp_path / "summary.md"
        summary.write_text("# Test Summary\n\n- Test bullet")
        source = tmp_path / "source.md"
        source.write_text("# Test Source\n\nSource text.")
        result = run_audit(summary, source, use_sdk=False)
        assert result["overall_score"] == 9
        assert result["verdict"] == "PASS"
        assert result["hallucinations_detected"] == 0

    def test_audit_prompt_has_4_pillars(self):
        """The audit prompt should mention all 4 pillars."""
        from tests.plugins.golden_master_audit import AUDIT_SYSTEM_PROMPT

        pillars = [
            "Factual Consistency",
            "Informational Coverage",
            "Cohesion & Clarity",
            "Conciseness vs. Vagueness",
        ]
        for pillar in pillars:
            assert pillar in AUDIT_SYSTEM_PROMPT, f"Missing pillar: {pillar}"

    def test_pytest_addoption_exists(self):
        """The plugin should define pytest_addoption for --audit."""
        from tests.plugins.golden_master_audit import pytest_addoption

        assert callable(pytest_addoption)


# ════════════════════════════════════════════════════════════════════════════
# 6.7 — GitHub Actions CI config
# ════════════════════════════════════════════════════════════════════════════


class TestCIConfig:
    """Tests for the GitHub Actions CI config (Phase 6.7)."""

    def test_ci_yml_exists(self):
        """The .github/workflows/ci.yml file should exist."""
        ci_path = _project_root / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), "ci.yml should exist"

    def test_ci_yml_has_lint_job(self):
        """ci.yml should have a lint job using ruff."""
        ci_path = _project_root / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()
        assert "lint" in content.lower()
        assert "ruff" in content.lower()

    def test_ci_yml_has_typecheck_job(self):
        """ci.yml should have a typecheck job using mypy."""
        ci_path = _project_root / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()
        assert "mypy" in content.lower()

    def test_ci_yml_has_test_job(self):
        """ci.yml should have a test job using pytest with coverage."""
        ci_path = _project_root / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()
        assert "pytest" in content.lower()
        assert "cov-fail-under=30" in content

    def test_ci_yml_uses_python_312(self):
        """ci.yml should use Python 3.12."""
        ci_path = _project_root / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()
        assert "3.12" in content
