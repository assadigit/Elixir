"""V18.10 (Phase 6) - Tests for the 6 low-risk Phase 6 items.

Tests:
- 6.1: Structured-log sink (gated by settings.observability.structured)
- 6.2: Per-chapter conversion manifest (JSON output)
- 6.3: GGUF checksum verification (SHA-256 first/last 1MB)
- 6.5: Modelfile integrity check (presence_penalty=1.5 for Qwen3)
- 6.6: Pytest golden-master audit plugin (stub mode)
- 6.7: GitHub Actions CI config exists

Run: pytest tests/test_phase6_items.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ════════════════════════════════════════════════════════════════════════════
# 6.1 — Structured-log sink
# ════════════════════════════════════════════════════════════════════════════

class TestStructuredLogSink:
    """Tests for the structured-log sink (Phase 6.1)."""

    def test_module_imports(self):
        from utils.structured_log_sink import (
            is_structured_logging_enabled,
            setup_main_logger_gated,
        )
        assert callable(is_structured_logging_enabled)
        assert callable(setup_main_logger_gated)

    def test_is_structured_logging_disabled_by_default(self):
        """When the setting is missing, structured logging should be OFF."""
        from utils.structured_log_sink import is_structured_logging_enabled
        with patch("utils.structured_log_sink.Settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = False
            mock_settings.return_value = mock_instance
            assert is_structured_logging_enabled() is False

    def test_is_structured_logging_enabled_when_setting_true(self):
        """When settings.observability.structured=True, it should be ON."""
        from utils.structured_log_sink import is_structured_logging_enabled
        with patch("utils.structured_log_sink.Settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.get.return_value = True
            mock_settings.return_value = mock_instance
            assert is_structured_logging_enabled() is True

    def test_setup_gated_no_jsonl_when_disabled(self):
        """When structured=False, the JSONL handler should NOT be attached."""
        from utils.structured_log_sink import setup_main_logger_gated
        logger = setup_main_logger_gated(structured=False)
        # Check that no handler has StructuredJsonFormatter
        has_json = any(
            hasattr(h, 'formatter') and h.formatter and
            type(h.formatter).__name__ == 'StructuredJsonFormatter'
            for h in logger.handlers
        )
        assert not has_json, "JSONL handler should not be attached when structured=False"

    def test_setup_gated_has_jsonl_when_enabled(self):
        """When structured=True, the JSONL handler should be attached."""
        from utils.structured_log_sink import setup_main_logger_gated
        logger = setup_main_logger_gated(structured=True)
        has_json = any(
            hasattr(h, 'formatter') and h.formatter and
            type(h.formatter).__name__ == 'StructuredJsonFormatter'
            for h in logger.handlers
        )
        assert has_json, "JSONL handler should be attached when structured=True"


# ════════════════════════════════════════════════════════════════════════════
# 6.2 — Per-chapter conversion manifest
# ════════════════════════════════════════════════════════════════════════════

class TestConversionManifest:
    """Tests for the per-chapter conversion manifest (Phase 6.2)."""

    def test_module_imports(self):
        from core.obs.conversion_manifest import (
            ChapterManifest,
            write_chapter_manifest,
        )
        assert callable(write_chapter_manifest)
        assert ChapterManifest is not None

    def test_manifest_to_dict(self):
        """ChapterManifest.to_dict should produce the expected fields."""
        from core.obs.conversion_manifest import ChapterManifest
        m = ChapterManifest(
            chapter_index=1,
            chapter_total=1,
            chapter_heading="Test Chapter",
            model="qwen3:32b",
            num_ctx=26758,
            coverage=0.89,
            phases_ran=["primary", "gap_fill", "post_checks"],
            leak_guard_fires=0,
            post_check_fixes=6,
            post_check_flags=1,
            duration_seconds=1398.0,
            bullet_count=36,
            exec_summary_chars=1295,
            hallucinations=0,
        )
        d = m.to_dict()
        assert d["chapter_index"] == 1
        assert d["model"] == "qwen3:32b"
        assert d["num_ctx"] == 26758
        assert d["coverage"] == 0.89
        assert d["phases_ran"] == ["primary", "gap_fill", "post_checks"]
        assert d["leak_guard_fires"] == 0
        assert d["duration_seconds"] == 1398.0
        assert d["duration_minutes"] == 23.3
        assert d["bullet_count"] == 36
        assert d["hallucinations"] == 0

    def test_manifest_to_json(self):
        """ChapterManifest.to_json should produce valid JSON."""
        from core.obs.conversion_manifest import ChapterManifest
        m = ChapterManifest(
            chapter_index=1, chapter_total=1, chapter_heading="Test",
            model="qwen3", num_ctx=32768, coverage=0.85,
            phases_ran=["primary"], leak_guard_fires=0,
            post_check_fixes=0, post_check_flags=0, duration_seconds=600.0,
        )
        j = m.to_json()
        parsed = json.loads(j)
        assert parsed["model"] == "qwen3"
        assert parsed["coverage"] == 0.85

    def test_write_chapter_manifest_creates_file(self, tmp_path):
        """write_chapter_manifest should create the JSON file."""
        from core.obs.conversion_manifest import write_chapter_manifest
        path = write_chapter_manifest(
            output_dir=tmp_path,
            chapter_index=1,
            chapter_total=1,
            chapter_heading="Test Chapter",
            model="qwen3:32b",
            num_ctx=26758,
            coverage=0.89,
            phases_ran=["primary", "post_checks"],
            leak_guard_fires=0,
            post_check_fixes=6,
            post_check_flags=1,
            duration_seconds=1398.0,
            bullet_count=36,
        )
        assert path.exists()
        assert path.name == "chapter_1_manifest.json"
        assert "logs" in str(path)
        data = json.loads(path.read_text())
        assert data["model"] == "qwen3:32b"
        assert data["coverage"] == 0.89

    def test_write_chapter_manifest_creates_logs_dir(self, tmp_path):
        """Should create the logs/ subdirectory if it doesn't exist."""
        from core.obs.conversion_manifest import write_chapter_manifest
        path = write_chapter_manifest(
            output_dir=tmp_path, chapter_index=2, chapter_total=5,
            chapter_heading="Ch 2", model="qwen3", num_ctx=16000,
            coverage=0.90, phases_ran=["primary"], leak_guard_fires=0,
            post_check_fixes=0, post_check_flags=0, duration_seconds=500.0,
        )
        assert path.exists()
        assert (tmp_path / "logs").is_dir()


# ════════════════════════════════════════════════════════════════════════════
# 6.3 — GGUF checksum verification
# ════════════════════════════════════════════════════════════════════════════

class TestGGUFChecksum:
    """Tests for GGUF checksum verification (Phase 6.3)."""

    def test_module_imports(self):
        from core.llm.gguf_checksum import (
            compute_gguf_checksum,
            verify_gguf_checksum,
        )
        assert callable(compute_gguf_checksum)
        assert callable(verify_gguf_checksum)

    def test_compute_checksum_small_file(self, tmp_path):
        """A small file should produce a stable checksum."""
        from core.llm.gguf_checksum import compute_gguf_checksum
        test_file = tmp_path / "test.gguf"
        test_file.write_bytes(b"hello world" * 100)
        cs1 = compute_gguf_checksum(test_file)
        cs2 = compute_gguf_checksum(test_file)
        assert cs1 == cs2
        assert len(cs1) == 64  # SHA-256 hex

    def test_compute_checksum_large_file(self, tmp_path):
        """A large file (>2MB) should hash first + last 1MB."""
        from core.llm.gguf_checksum import compute_gguf_checksum
        test_file = tmp_path / "large.gguf"
        # Write 3MB of data
        test_file.write_bytes(b"A" * (1024 * 1024) + b"B" * (1024 * 1024) + b"C" * (1024 * 1024))
        cs = compute_gguf_checksum(test_file)
        assert len(cs) == 64

    def test_verify_first_load_registers(self, tmp_path):
        """First load should register the checksum."""
        from core.llm.gguf_checksum import verify_gguf_checksum
        # Use a temp cache
        with patch("core.llm.gguf_checksum.get_checksum_cache_path") as mock_path:
            cache_file = tmp_path / "checksums.json"
            mock_path.return_value = cache_file
            test_file = tmp_path / "model.gguf"
            test_file.write_bytes(b"model data" * 1000)
            is_ok, reason = verify_gguf_checksum(test_file)
            assert is_ok is True
            assert "registered" in reason

    def test_verify_subsequent_load_matches(self, tmp_path):
        """Second load should match."""
        from core.llm.gguf_checksum import verify_gguf_checksum
        with patch("core.llm.gguf_checksum.get_checksum_cache_path") as mock_path:
            cache_file = tmp_path / "checksums.json"
            mock_path.return_value = cache_file
            test_file = tmp_path / "model.gguf"
            test_file.write_bytes(b"model data" * 1000)
            verify_gguf_checksum(test_file)  # register
            is_ok, reason = verify_gguf_checksum(test_file)  # verify
            assert is_ok is True
            assert "matched" in reason

    def test_verify_detects_change(self, tmp_path):
        """A changed file should produce a mismatch."""
        from core.llm.gguf_checksum import verify_gguf_checksum
        with patch("core.llm.gguf_checksum.get_checksum_cache_path") as mock_path:
            cache_file = tmp_path / "checksums.json"
            mock_path.return_value = cache_file
            test_file = tmp_path / "model.gguf"
            test_file.write_bytes(b"original data" * 1000)
            verify_gguf_checksum(test_file)  # register
            test_file.write_bytes(b"corrupted data" * 1000)  # change
            is_ok, reason = verify_gguf_checksum(test_file)
            assert is_ok is False
            assert "mismatch" in reason

    def test_verify_missing_file(self, tmp_path):
        """A missing file should return (False, 'file not found')."""
        from core.llm.gguf_checksum import verify_gguf_checksum
        is_ok, reason = verify_gguf_checksum(tmp_path / "nonexistent.gguf")
        assert is_ok is False
        assert "not found" in reason


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
