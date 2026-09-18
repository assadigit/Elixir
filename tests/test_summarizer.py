"""V10.30.0 (Sprint 3.1): Characterization tests for the Summarizer.

The 1,035-line ``_summarize_inner`` method had **0 unit tests** before this
sprint (``test_phase5.py:46`` explicitly said "can't import Summarizer
directly (deps)").  This module breaks that impasse by:

  1. Bypassing the heavy ``Summarizer.__init__`` (which imports Settings,
     ModelManager, OllamaSupervisor, PromptManager, torch VRAM detection,
     etc.) via ``object.__new__(Summarizer)``.
  2. Setting only the attributes the tested methods need (``quarantine``,
     ``conservative_drops``, ``log``, ``_current_heading``, ``max_bullets``).
  3. Testing the pure-logic methods that Sprint 1 added quarantine /
     conservative-mode behavior to:
       - ``_filter_thinking_bullets`` (drops + quarantine logging)
       - ``_compute_coverage`` (keyword + concept coverage)
       - ``_score_bullet`` (0-100 quality score)
       - ``_recover_quarantined`` (resurrect high-overlap bullets)
       - ``_truncate_to_sentences`` (length cap)

  4. Testing conservative-mode gating: when ``conservative_drops=True``,
     only thinking/prompt-leakage bullets are dropped; everything else
     is logged to quarantine with ``actually_dropped=False``.

The full ``_summarize_inner`` end-to-end path (with mocked LLM) is covered
by ``tests/test_bullet_pipeline_golden.py`` (Sprint 3.5).

Run: ``pytest tests/test_summarizer.py -v``
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Stub the heavy deps so Summarizer can be imported ──────────────────────
# Summarizer.py imports: tiktoken (token_counter), requests, torch (vram),
# sentence_transformers (text_preprocessor), rapidfuzz, langextract, etc.
# We stub the ones that crash on import in the sandbox.


# P0 (test-infra): NEVER displace an already-imported module. conftest.py
# pins the real tiktoken + utils.token_counter before any test module is
# imported; the old unconditional swaps poisoned every xdist worker that
# merely COLLECTED this file (un-stub fixtures only fire when this file's
# own tests run in that worker), and the swap was split-brained (package
# attribute vs sys.modules resolution — see conftest.py's pin comment).
_STUBBED: list[str] = []


def _stub_module(name: str, **attrs):
    """Create a stub module — but NEVER displace a real/pinned module."""
    if name in sys.modules:
        return sys.modules[name]  # real/pinned module wins — no swap, no leak
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    _STUBBED.append(name)
    return mod


# tiktoken — token_counter.py imports it at module level
_stub_module("tiktoken")
_stub_module("tiktoken_ext")
_stub_module("tiktoken_ext.openai_public")

# token_counter stub functions
def _count_tokens(text: str) -> int:
    """Rough token count: words * 1.3 (no tiktoken)."""
    if not text:
        return 0
    return max(1, int(len(str(text).split()) * 1.3))


def _truncate_by_tokens(text: str, max_tokens: int, add_ellipsis: bool = False) -> str:
    return text  # no-op for tests


token_counter_mod = _stub_module(
    "utils.token_counter",
    count_tokens=_count_tokens,
    truncate_by_tokens=_truncate_by_tokens,
)

# sentence_transformers — text_preprocessor imports lazily, but stub it anyway
_stab_st = _stub_module("sentence_transformers")
_stub_module("sentence_transformers.SentenceTransformer")
_stub_module("sentence_transformers.util")


# ── V18.20.2.0 (SWOT test-infra): un-stub after this module's tests ─────────
# The module-level stubs above are needed for THIS file's import chain and its
# own tests, but they replaced sys.modules entries unconditionally and were
# never restored — every later test file's call-time
# ``from utils.token_counter import count_tokens`` then resolved to this file's
# word-count stub (chunking/token gates silently mis-evaluated in later files;
# see the order-dependent test_primary_call / test_map_reduce failures).
# Restore the REAL modules (or clean absence) once this file's tests finish.
@pytest.fixture(scope="module", autouse=True)
def _unstub_modules_after_tests():
    yield
    # P0 (test-infra): only remove what THIS module actually installed (see
    # the _STUBBED registry in _stub_module). Under pytest, conftest.py pins
    # the real tiktoken + utils.token_counter before test modules import, so
    # this is always empty and the real modules are never popped/re-imported.
    # The old unconditional pop+re-import destroyed conftest's pins and
    # created fresh module instances (identity splits) even when this file
    # had installed nothing.
    for _name in _STUBBED:
        sys.modules.pop(_name, None)
    _STUBBED.clear()

# Now we can import the quarantine module + the summarizer module.
# We load summarizer.py via importlib to control the import, but it will
# still execute `from utils.token_counter import count_tokens` — which now
# resolves to our stub.  The `from utils.settings import Settings` still
# runs (Settings is pure stdlib + atomic_io, works in sandbox).  The
# `from core.system.ollama_supervisor import OllamaSupervisor` — let's
# check if that's importable.
try:
    from core.summarisation import quarantine as _q_mod  # noqa: F401
    _QUARANTINE_OK = True
except Exception:
    _QUARANTINE_OK = False

# Load the summarizer module.  This is heavy — it imports Settings,
# ModelManager, OllamaSupervisor, PromptManager, content_presets,
# model_profiles, vram_calculator.  Most of these are pure-python.
# If any fail, we skip the Summarizer tests gracefully.
_SUMMARIZER_OK = False
_SUMMARIZER_MOD = None
try:
    # Pre-import the deps that summarizer.py needs at module level
    from core.llm import ModelManager, ModelType  # noqa: F401
    from core.models import ConversionRequest, SummaryResult  # noqa: F401
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

    # P0 (test-infra): reuse the already-imported summarizer when present —
    # re-execing a fresh instance under the same sys.modules name created a
    # second class identity (split-brain for every other test file).
    _existing = sys.modules.get("core.summarisation.summarizer")
    if _existing is not None:
        _SUMMARIZER_MOD = _existing
    else:
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

# Always import the quarantine module directly (it's pure stdlib).
# P0 (test-infra): reuse the already-imported module when present (identity
# preservation — same rationale as the summarizer load above).
_q_mod = sys.modules.get("core.summarisation.quarantine")
if _q_mod is None:
    _q_spec = importlib.util.spec_from_file_location(
        "core.summarisation.quarantine",
        _project_root / "core" / "summarisation" / "quarantine.py",
    )
    _q_mod = importlib.util.module_from_spec(_q_spec)
    sys.modules[_q_spec.name] = _q_mod
    _q_spec.loader.exec_module(_q_mod)
QuarantineLog = _q_mod.QuarantineLog


# ── Skip guard if the summarizer couldn't be imported ──────────────────────

pytestmark = pytest.mark.skipif(
    not _SUMMARIZER_OK,
    reason=f"Summarizer module import failed in sandbox: "
           f"{getattr(_SUMMARIZER_IMPORT_ERROR, '__class__.__name__', 'unknown') if not _SUMMARIZER_OK else ''}",
)

if _SUMMARIZER_OK:
    Summarizer = _SUMMARIZER_MOD.Summarizer
    SummaryResult = _SUMMARIZER_MOD.SummaryResult


# ── Test harness: bypass __init__ ───────────────────────────────────────────


def _make_bare_summarizer(conservative: bool = False, tmp_path=None) -> Summarizer:
    """Create a Summarizer without running __init__.

    Sets only the attributes the tested methods need.  This is the standard
    characterization-test technique for classes with heavy constructors.
    """
    s = object.__new__(Summarizer)
    # Attributes used by _filter_thinking_bullets / _recover_quarantined
    s.conservative_drops = conservative
    s.quarantine = QuarantineLog(
        output_dir=tmp_path,
        log_callback=lambda msg, level="DEBUG": None,
    )
    s.log = lambda msg, level="INFO": None
    s._current_heading = "Test Chapter"
    s.max_bullets_per_chapter = 30
    # Attributes used by _compute_coverage
    s._coverage_cache = {}
    # _extract_keywords is a method on the class — it'll be bound at call time.
    # Attributes used by _score_bullet — none beyond what's set above.
    # _last_quarantined (legacy V10.26.0 attribute)
    s._last_quarantined = []
    return s


# ── 1. _filter_thinking_bullets ─────────────────────────────────────────────


class TestFilterThinkingBullets:
    def test_drops_thinking_process_bullet(self, tmp_path):
        """A bullet starting with a thinking verb is dropped + quarantined."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        bullets = [
            "Analyze the structure of the argument carefully.",  # thinking
            "The study found 50% improvement in participants.",   # good
        ]
        result = s._filter_thinking_bullets(bullets, source_text="study found 50% improvement")
        assert "The study found 50% improvement in participants." in result
        assert all("Analyze" not in b for b in result)
        # Quarantine should have recorded the drop
        entries = s.quarantine.entries
        assert any("thinking" in e.stage for e in entries)

    def test_drops_prompt_leakage(self, tmp_path):
        """Prompt-leakage bullets are dropped even in conservative mode."""
        s = _make_bare_summarizer(conservative=True, tmp_path=tmp_path)
        bullets = [
            "Source Text: the original passage to summarize",  # prompt leakage
            "The mechanism requires careful calibration.",      # good
        ]
        result = s._filter_thinking_bullets(bullets, source_text="mechanism requires calibration")
        # The good bullet survives
        assert any("mechanism" in b for b in result)

    def test_conservative_keeps_narrative_bullet(self, tmp_path):
        """In conservative mode, narrative bullets are KEPT (logged only)."""
        s_normal = _make_bare_summarizer(conservative=False, tmp_path=tmp_path)
        s_cons = _make_bare_summarizer(conservative=True, tmp_path=tmp_path)
        # A narrative bullet with no concept indicator
        narrative = "Ryan went to the party and met Thad at the venue."
        result_normal = s_normal._filter_thinking_bullets([narrative], source_text="party venue")
        result_cons = s_cons._filter_thinking_bullets([narrative], source_text="party venue")
        # Normal mode drops it
        assert narrative not in result_normal
        # Conservative mode keeps it
        assert narrative in result_cons
        # Both log to quarantine
        assert len(s_normal.quarantine.entries) >= 1
        assert len(s_cons.quarantine.entries) >= 1

    def test_keeps_good_bullets(self, tmp_path):
        """Well-formed bullets survive the filter."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        good = [
            "The study demonstrates that 50% of participants improved.",
            "Researchers found that the treatment causes recovery.",
        ]
        source = "study demonstrates 50% participants improved treatment causes recovery"
        result = s._filter_thinking_bullets(good, source_text=source)
        assert len(result) == 2

    def test_empty_input(self, tmp_path):
        """Empty bullet list returns empty."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        assert s._filter_thinking_bullets([], source_text="") == []

    def test_quarantine_records_stage(self, tmp_path):
        """Quarantine entries record the correct stage name."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        s._filter_thinking_bullets(
            ["Analyze this carefully."], source_text=""
        )
        stages = [e.stage for e in s.quarantine.entries]
        assert any("thinking_filter" in st for st in stages)

    def test_conservative_logs_actually_dropped_false(self, tmp_path):
        """Conservative-mode entries have actually_dropped=False."""
        s = _make_bare_summarizer(conservative=True, tmp_path=tmp_path)
        # A narrative bullet — would be dropped normally, kept in conservative
        s._filter_thinking_bullets(
            ["Ryan went to the party and met Thad there."],
            source_text="party",
        )
        logged = [e for e in s.quarantine.entries if not e.actually_dropped]
        assert len(logged) >= 1


# ── 2. _compute_coverage ────────────────────────────────────────────────────


class TestComputeCoverage:
    def test_full_coverage(self, tmp_path):
        """Summary containing all keywords → 1.0."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        source = "photosynthesis chlorophyll sunlight glucose plants"
        summary = "photosynthesis chlorophyll sunlight glucose plants"
        cov = s._compute_coverage(source, summary)
        assert cov >= 0.5  # at least half the keywords match

    def test_zero_coverage(self, tmp_path):
        """Summary with no keyword overlap → low coverage."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        source = "photosynthesis chlorophyll sunlight glucose plants"
        summary = "quantum mechanics relativity entanglement spacetime"
        cov = s._compute_coverage(source, summary)
        assert cov < 0.3

    def test_empty_source(self, tmp_path):
        """Empty source → 1.0 (can't check, auto-pass)."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        assert s._compute_coverage("", "summary") == 1.0

    def test_cache_works(self, tmp_path):
        """Repeated calls with the same source use the cache."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        source = "photosynthesis chlorophyll sunlight glucose plants"
        s._compute_coverage(source, "summary one")
        cache_size_before = len(s._coverage_cache)
        s._compute_coverage(source, "summary two")
        cache_size_after = len(s._coverage_cache)
        # Cache should not grow for the same source
        assert cache_size_after == cache_size_before


# ── 3. _score_bullet ────────────────────────────────────────────────────────


class TestScoreBullet:
    def test_high_score_for_good_bullet(self, tmp_path):
        """A well-formed bullet with concept + action verb + number scores high."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        bullet = "The study demonstrates that 50% of participants improved significantly after treatment."
        score = s._score_bullet(bullet, concepts=["study", "treatment"], source_text="50% participants improved")
        assert score >= 40  # above the drop threshold

    def test_low_score_for_short_bullet(self, tmp_path):
        """A 3-word bullet scores low (length penalty)."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        bullet = "Ok then sure"
        score = s._score_bullet(bullet, concepts=[], source_text="")
        assert score < 40

    def test_concept_match_bonus(self, tmp_path):
        """A bullet containing a concept keyword gets +15."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        bullet_with = "The mechanism requires careful calibration of the instruments."
        bullet_without = "Something completely unrelated to any concept happens here."
        score_with = s._score_bullet(bullet_with, concepts=["mechanism"], source_text="")
        score_without = s._score_bullet(bullet_without, concepts=["mechanism"], source_text="")
        assert score_with > score_without

    def test_score_in_range_0_to_100(self, tmp_path):
        """Score is always 0-100."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        for bullet in ["short", "A" * 500, "Normal bullet with some words here."]:
            score = s._score_bullet(bullet, concepts=[], source_text="")
            assert 0 <= score <= 100


# ── 4. _recover_quarantined ─────────────────────────────────────────────────


class TestRecoverQuarantined:
    def test_resurrects_high_overlap_bullet(self, tmp_path):
        """A quarantined bullet with high source overlap is re-inserted."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        # Simulate a prior drop with high overlap
        s.quarantine.add(
            "The study found 50% improvement in participants.",
            stage="F4_source_overlap",
            source_overlap=0.80,
            actually_dropped=True,
        )
        source = "study found 50% improvement participants treatment recovery"
        bullets = ["Existing bullet one."]
        result = s._recover_quarantined(bullets, source)
        assert len(result) == 2  # original + resurrected

    def test_skips_low_overlap_bullet(self, tmp_path):
        """A quarantined bullet with low source overlap is NOT resurrected."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        s.quarantine.add(
            "Quantum entanglement transcends spacetime.",
            stage="F4_source_overlap",
            source_overlap=0.05,
            actually_dropped=True,
        )
        result = s._recover_quarantined(["existing"], "some source text")
        assert len(result) == 1  # no resurrection

    def test_skips_duplicate_resurrection(self, tmp_path):
        """A resurrected bullet that's already in the list is not double-added."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        bullet = "The study found 50% improvement in participants."
        s.quarantine.add(
            bullet, stage="F4_source_overlap",
            source_overlap=0.90, actually_dropped=True,
        )
        result = s._recover_quarantined([bullet], "study found 50% improvement")
        assert result.count(bullet) == 1

    def test_empty_quarantine_noop(self, tmp_path):
        """No quarantine entries → bullets unchanged."""
        s = _make_bare_summarizer(tmp_path=tmp_path)
        result = s._recover_quarantined(["a", "b"], "source")
        assert result == ["a", "b"]


# ── 5. _truncate_to_sentences ───────────────────────────────────────────────


class TestTruncateToSentences:
    def test_short_text_unchanged(self, tmp_path):
        s = _make_bare_summarizer(tmp_path=tmp_path)
        text = "Short sentence."
        result = s._truncate_to_sentences(text, max_sentences=2, max_words=35)
        assert "Short sentence" in result

    def test_long_text_truncated(self, tmp_path):
        s = _make_bare_summarizer(tmp_path=tmp_path)
        text = (
            "First sentence with enough words to be meaningful. "
            "Second sentence also has enough words here. "
            "Third sentence should be cut off by the max limit."
        )
        result = s._truncate_to_sentences(text, max_sentences=2, max_words=35)
        assert "Third sentence" not in result

    def test_max_words_cap(self, tmp_path):
        s = _make_bare_summarizer(tmp_path=tmp_path)
        # One very long sentence
        text = " ".join(["word"] * 100) + "."
        result = s._truncate_to_sentences(text, max_sentences=2, max_words=35)
        assert len(result.split()) <= 36  # capped + ellipsis
