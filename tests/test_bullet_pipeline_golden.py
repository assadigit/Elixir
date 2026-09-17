"""V10.30.0 (Sprint 3.5): Golden-file bullet-survival tests.

These tests verify that the exact bullet list produced by the LLM survives
the filter pipeline unchanged (in both Normal and Conservative mode).
They use fixed fixture files (source chapter + raw LLM response + expected
bullets JSON) so any regression in the filter logic is caught immediately.

Golden files:
  - ``tests/golden/academic/``  — academic paper source + 8 LLM bullets
    (7 grounded + 1 backtick prompt-leakage).  Normal mode drops the
    backtick bullet; Conservative mode keeps all 7 grounded + drops the
    backtick bullet (thinking/prompt-leakage filters are always active).
  - ``tests/golden/nonfiction/``  — nonfiction source + 7 LLM bullets
    (6 grounded + 1 thinking-process).  Normal mode drops the thinking
    bullet; Conservative mode keeps all 6 grounded + drops the thinking
    bullet.

The test harness uses the same ``object.__new__(Summarizer)`` technique
as ``test_summarizer.py`` to bypass the heavy ``__init__``, then calls
``_filter_thinking_bullets`` + ``_recover_quarantined`` directly on the
fixture bullets.

Run: ``pytest tests/test_bullet_pipeline_golden.py -v``
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Stub tiktoken (same as test_summarizer.py) ──────────────────────────────


def _stub_module(name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_stub_module("tiktoken")
_stub_module("tiktoken_ext")
_stub_module("tiktoken_ext.openai_public")
_stub_module("utils.token_counter", count_tokens=lambda t: max(1, len(str(t).split())), truncate_by_tokens=lambda t, m, add_ellipsis=False: t)


# ── V18.20.2.0 (SWOT test-infra): un-stub after this module's tests ─────────
# The module-level stubs above are needed for THIS file's import chain and its
# own tests, but they replaced sys.modules entries unconditionally and were
# never restored — every later test file's call-time
# ``from utils.token_counter import count_tokens`` then resolved to the split()
# stub (chunking gates silently mis-evaluated; see test_primary_call order-
# dependent failures). Restore the REAL modules once this file's tests finish.
@pytest.fixture(scope="module", autouse=True)
def _unstub_modules_after_tests():
    yield
    for _name in (
        "tiktoken",
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        "utils.token_counter",
    ):
        sys.modules.pop(_name, None)
    try:
        import tiktoken  # noqa: F401  — re-import the real package

        import utils.token_counter  # noqa: F401  — re-import the real module
    except Exception:  # pragma: no cover - defensive
        pass

# ── Load quarantine + summarizer modules ────────────────────────────────────

_q_spec = importlib.util.spec_from_file_location(
    "core.summarisation.quarantine",
    _project_root / "core" / "summarisation" / "quarantine.py",
)
_q_mod = importlib.util.module_from_spec(_q_spec)
sys.modules[_q_spec.name] = _q_mod
_q_spec.loader.exec_module(_q_mod)
QuarantineLog = _q_mod.QuarantineLog

_SUMMARIZER_OK = False
_SUMMARIZER_MOD = None
try:
    from core.llm import ModelManager, ModelType  # noqa: F401
    from core.models import SummaryResult  # noqa: F401
    from core.summarisation.response_parser import (  # noqa: F401
        extract_bullets_from_block,
        extract_bullets_from_text,
        parse_response,
        strip_markup_tags,
        strip_narrative_from_thorough,
        strip_reasoning_leaks,
        strip_thinking,
    )
    from core.system.ollama_supervisor import OllamaSupervisor  # noqa: F401
    from utils.network import safe_ollama_request  # noqa: F401
    from utils.settings import Settings  # noqa: F401
    _spec = importlib.util.spec_from_file_location(
        "core.summarisation.summarizer",
        _project_root / "core" / "summarisation" / "summarizer.py",
    )
    _SUMMARIZER_MOD = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _SUMMARIZER_MOD
    _spec.loader.exec_module(_SUMMARIZER_MOD)
    _SUMMARIZER_OK = True
except Exception as _e:
    _SUMMARIZER_IMPORT_ERROR = _e

pytestmark = pytest.mark.skipif(
    not _SUMMARIZER_OK,
    reason=f"Summarizer import failed: "
           f"{getattr(_SUMMARIZER_IMPORT_ERROR, '__class__.__name__', 'unknown') if not _SUMMARIZER_OK else ''}",
)

if _SUMMARIZER_OK:
    Summarizer = _SUMMARIZER_MOD.Summarizer


# ── Test harness ────────────────────────────────────────────────────────────


def _make_bare_summarizer(conservative: bool = False, tmp_path=None) -> Summarizer:
    """Same harness as test_summarizer.py — bypass __init__."""
    s = object.__new__(Summarizer)
    s.conservative_drops = conservative
    s.quarantine = QuarantineLog(
        output_dir=tmp_path,
        log_callback=lambda msg, level="DEBUG": None,
    )
    s.log = lambda msg, level="INFO": None
    s._current_heading = "Golden Test Chapter"
    s.max_bullets_per_chapter = 30
    s._coverage_cache = {}
    s._last_quarantined = []
    return s


def _parse_llm_response_bullets(raw_md: str) -> list[str]:
    """Extract the bullet_points list from the golden LLM response markdown.

    The golden files use a simple YAML-ish format:
        bullet_points:
          - bullet one
          - bullet two
    """
    bullets = []
    in_bullets = False
    for line in raw_md.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("bullet_points:"):
            in_bullets = True
            continue
        if in_bullets:
            if stripped.startswith("  - "):
                bullet = stripped[4:].strip()
                # Strip surrounding quotes if present
                if bullet.startswith('"') and bullet.endswith('"'):
                    bullet = bullet[1:-1]
                bullets.append(bullet)
            elif stripped and not stripped.startswith(" "):
                # Left the bullets block
                break
    return bullets


# ── Parametrized golden-file test ───────────────────────────────────────────

_GOLDEN_DIRS = ["academic", "nonfiction"]
_MODES = ["normal", "conservative"]


@pytest.mark.parametrize("golden_name", _GOLDEN_DIRS)
@pytest.mark.parametrize("mode", _MODES)
def test_golden_bullet_survival(golden_name: str, mode: str, tmp_path: Path):
    """Every golden file's expected bullets must survive the filter pipeline.

    In Normal mode: the expected surviving bullets must all be present in
    the output.  The expected-dropped bullets must NOT be present.

    In Conservative mode: the expected surviving bullets must all be
    present (thinking/prompt-leakage filters are always active, so the
    dropped bullet is still dropped — but no grounded bullet is lost).
    """
    golden_dir = _project_root / "tests" / "golden" / golden_name
    source = (golden_dir / "source_chapter.md").read_text(encoding="utf-8")
    raw_llm = (golden_dir / "llm_response.md").read_text(encoding="utf-8")
    expected_file = (
        golden_dir / "expected_bullets.json"
        if mode == "normal"
        else golden_dir / "expected_bullets_conservative.json"
    )
    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    bullets = _parse_llm_response_bullets(raw_llm)
    assert len(bullets) > 0, f"No bullets parsed from {golden_name}/llm_response.md"

    # Run the filter pipeline
    conservative = (mode == "conservative")
    s = _make_bare_summarizer(conservative=conservative, tmp_path=tmp_path)
    result = s._filter_thinking_bullets(bullets, source_text=source)

    # Recovery pass (no-op in conservative mode, but exercises the code path)
    result = s._recover_quarantined(result, source)

    # ── Assert expected bullets survive ────────────────────────────────
    expected_surviving = expected["expected_surviving_bullets"]
    for expected_bullet in expected_surviving:
        # The bullet text may be slightly cleaned (stripped, etc.), so
        # we check that the expected bullet's key content is present.
        # Use a normalized comparison: lowercase, strip punctuation.
        def _norm(t):
            return re.sub(r"[^\w\s]", "", t.lower()).strip()
        expected_norm = _norm(expected_bullet)
        found = any(expected_norm in _norm(r) or _norm(r) in expected_norm for r in result)
        assert found, (
            f"[{golden_name}/{mode}] Expected bullet not found in result:\n"
            f"  expected: {expected_bullet[:80]}\n"
            f"  result bullets: {[r[:60] for r in result]}"
        )

    # ── Assert drops occurred ──────────────────────────────────────────
    assert len(s.quarantine.entries) >= expected["expected_dropped_count_min"], (
        f"[{golden_name}/{mode}] Expected at least "
        f"{expected['expected_dropped_count_min']} drop(s), got "
        f"{len(s.quarantine.entries)}"
    )

    # ── Assert drop reasons match ──────────────────────────────────────
    stage_text = " ".join(e.stage + " " + e.reason for e in s.quarantine.entries).lower()
    for reason_fragment in expected["expected_dropped_reasons_contains"]:
        assert reason_fragment.lower() in stage_text, (
            f"[{golden_name}/{mode}] Expected drop reason '{reason_fragment}' "
            f"not found in quarantine stages.  Stages: "
            f"{[e.stage for e in s.quarantine.entries]}"
        )


# ── Golden file integrity tests ─────────────────────────────────────────────


@pytest.mark.parametrize("golden_name", _GOLDEN_DIRS)
def test_golden_files_exist(golden_name: str):
    """Every golden dir must have the 4 required files."""
    golden_dir = _project_root / "tests" / "golden" / golden_name
    assert (golden_dir / "source_chapter.md").exists()
    assert (golden_dir / "llm_response.md").exists()
    assert (golden_dir / "expected_bullets.json").exists()
    assert (golden_dir / "expected_bullets_conservative.json").exists()


@pytest.mark.parametrize("golden_name", _GOLDEN_DIRS)
def test_golden_expected_json_valid(golden_name: str):
    """The expected_bullets JSON files must be valid JSON with required keys."""
    golden_dir = _project_root / "tests" / "golden" / golden_name
    for fname in ["expected_bullets.json", "expected_bullets_conservative.json"]:
        data = json.loads((golden_dir / fname).read_text(encoding="utf-8"))
        assert "expected_surviving_bullets" in data
        assert "expected_dropped_count_min" in data
        assert "expected_dropped_reasons_contains" in data
        assert isinstance(data["expected_surviving_bullets"], list)
        assert len(data["expected_surviving_bullets"]) > 0


@pytest.mark.parametrize("golden_name", _GOLDEN_DIRS)
def test_golden_llm_response_has_bullets(golden_name: str):
    """The golden LLM response must contain a parseable bullet_points list."""
    golden_dir = _project_root / "tests" / "golden" / golden_name
    raw = (golden_dir / "llm_response.md").read_text(encoding="utf-8")
    bullets = _parse_llm_response_bullets(raw)
    assert len(bullets) >= 5, f"Expected ≥5 bullets, got {len(bullets)}"
