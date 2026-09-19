"""V18.20.3.13 (Phase 5 / W7+O3) — thorough-theorist floor + ONE targeted
gap-fill: characterization tests.

The .3.7 SWOT W7 gap: the recall floor (37/37) guarantees theorist coverage
in the BULLETS and the V18.14 thorough-only judge line is purely
informational — when the thorough missed theorists, nothing repaired it and
nothing enforced a floor. V18.20.3.13 adds ``Summarizer._thorough_theorist_floor``
(called from ``_summarize_inner`` on the FINAL thorough, right before the
recall-floor probe):

  1. floor MET (thorough mentions all analysis authors) → the floor line
     logs INFO, NO LLM call fires.
  2. floor UNMET → ONE targeted call (``_call_llm_with_empty_retry``) with
     a prompt containing the missing author name(s) + the source excerpt +
     the thorough tail; the canned response is appended; the after-line
     logs the measured improvement.
  3. deadline exceeded + floor unmet → no call, honest WARNING floor line
     (+ the ``_deadline_exceeded`` skip WARNING).
  4. the LLM call returns empty → WARNING, thorough unchanged, no crash.
  5. the floor machinery crashes (poisoned analysis) → WARNING, chapter
     continues (fail-soft).
  6. source-pin: the floor derives its missing list from the RUNTIME
     deterministic analysis (``check_coverage(analysis, thorough)`` wired
     through ``_analysis_rf``) — not a hardcoded list.
  7. (bonus) trivial thorough (< 50 words) → repair skipped honestly.
  8. (bonus) CoT-shaped response → discarded (the V18.16.0.1 guard class).

Synthetic names ("AuthorA"/"AuthorB") live ONLY in this fixtures file —
tests are fixtures, allowed by the V18.20.3.9 classification; the runtime
path under test must stay book-agnostic (enforced separately by the
residuals deny-list in tests/test_v182039_audit_fixes.py).

Hermetic: markitdown stubbed in sys.modules
(tests/test_v18203_incremental_checkpoint.py:36-39 pattern) + tiktoken stub
(tests/test_thorough_fallback.py:20-25 pattern); the Summarizer is built via
``object.__new__`` with only the attrs the method needs
(tests/test_summarizer.py:188 pattern) — no Qt, no network, no __init__.

Run: ``pytest tests/test_v1820313_thorough_floor.py -v``
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Hermetic stubs (order matters: before the summarizer import) ───────────
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")

    class _Enc:  # noqa: D401 — placeholder class, not a docstring subject
        pass

    _tk.Encoding = _Enc
    _tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = _tk

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.summarisation.summarizer import Summarizer  # noqa: E402

_SUMMARIZER_SRC = (PROJECT_ROOT / "core" / "summarisation" / "summarizer.py").read_text(
    encoding="utf-8"
)

# V18.20.4.7 (P5 / O-a2): ``_thorough_theorist_floor`` moved VERBATIM
# (byte-identical body) from summarizer.py to
# core/summarisation/thorough_theorist_floor.py (SummarizerThoroughFloorMixin).
# The method-source pin below now reads the new module; the call-site +
# ordering pins still read summarizer.py (the call site stayed in
# _summarize_inner). Assertions unchanged — only the slicing follow moved
# with the code (house precedent: V18.20.3.12 gap_fill_batch move).
_FLOOR_MODULE_SRC = (
    PROJECT_ROOT / "core" / "summarisation" / "thorough_theorist_floor.py"
).read_text(encoding="utf-8")

# ── Fixtures: synthetic analysis / source / thorough ───────────────────────
# Synthetic surnames Voss/Ibarra (the house placeholder pair the .3.9
# prompt-scrub established — never real book names, never in the residuals
# deny-list). NOTE: placeholder names of the literal "AuthorA"/"AuthorB"
# shape CANNOT be used here: they are mutual edit-distance-1 neighbours,
# so check_coverage's garble-tolerant matcher (V18.20.3.5) treats the one
# as a dropped-letter garble of the other and reports both covered — these
# fixtures need names the real matcher distinguishes.

# The deterministic analysis "## Citations" section is what
# extract_authors_from_analysis parses — the SAME runtime machinery the
# V18.14 judge and the recall floor use.
_ANALYSIS = (
    "## Segment Analysis\n\n### Overview\nSynthetic test analysis.\n\n"
    "## Citations\n\n"
    "1. **Voss** (5 mentions): 1980\n"
    "2. **Ibarra** (3 mentions): 1967\n"
)

# Source text with a distinctive marker so the test can prove the prompt
# carried the (clamped) chapter content.
_SOURCE = (
    "Chapter One body. Voss formulated the layered model of structure "
    "formation in 1980. The distinctive contribution of Ibarra appears in "
    "section four SOURCE_MARKER_Q7, where the modular consolidation "
    "mechanism is documented with longitudinal evidence. Ibarra's later "
    "work reinforced the same account."
)

# A non-trivial thorough (>= 50 words) that covers Voss but NOT Ibarra.
_THOROUGH = (
    "This chapter traces the layered model of structure formation as "
    "proposed by Voss, whose early formulation established the baseline "
    "vocabulary for the whole field. The narrative then surveys the "
    "competing frameworks and resolves them into an integrative account. "
    "Voss's position remains the reference point throughout the "
    "discussion, and the closing phrase of the thorough anchors the "
    "integrative arc."
)

# A non-trivial thorough that covers BOTH authors (floor met).
_THOROUGH_FULL = _THOROUGH + (
    " Ibarra closes the arc by supplying the modular consolidation "
    "mechanism documented in the chapter's fourth section."
)

# A canned model response (the house <thorough_addition> wrapper the
# prompt requests) — >= 20 words, mentions the missing Ibarra.
_ADDITION = (
    "Ibarra extended the account by documenting the modular mechanism "
    "described in section four, showing how each layer consolidates before "
    "the next one forms. The chapter credits Ibarra with the longitudinal "
    "evidence that settled the dispute, SOURCE_MARKER_Q7 included."
)
_CANNED = f"<thorough_addition>\n{_ADDITION}\n</thorough_addition>"

# A canned CoT response (3+ detect_cot_narrative markers, > 50 chars).
_COT_CANNED = (
    "Let me organize my understanding of this chapter first. "
    "Let me count carefully how many contributors are missing. "
    "Let me draft each section now before writing the addition."
)


def _make_bare(
    *,
    responses: list | None = None,
    deadline_dead: bool = False,
    analysis: str | int = _ANALYSIS,
) -> tuple:
    """Bare Summarizer + captured log/LLM calls (no __init__, no Qt/net).

    ``responses`` cycles through the canned ``_call_llm`` returns; the real
    ``_call_llm_with_empty_retry`` wrapper runs on top of them (so the
    empty-retry nudge path is exercised for real). ``deadline_dead`` arms
    the REAL ``_deadline_exceeded`` machinery (is_local + elapsed > limit).
    """
    s = object.__new__(Summarizer)
    s.log_lines: list[tuple[str, str]] = []

    def _log(msg: str, level: str = "INFO") -> None:
        s.log_lines.append((level, msg))

    s.log = _log
    s.language = "en"
    s.primary_model = "test-model"
    s.temperature = 0.2
    llm_calls: list[dict] = []
    _queue = list(responses or [])

    def _call_llm(prompt, model=None, temperature=None, max_tokens=None):
        llm_calls.append(
            {
                "prompt": prompt,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if _queue:
            return _queue.pop(0)
        return None

    s._call_llm = _call_llm
    # The REAL deadline machinery (not an override): 10s budget, started
    # 100s ago → exceeded when deadline_dead, never otherwise.
    s.is_local = True
    s.local_chapter_deadline = 10 if deadline_dead else 0
    s._chapter_deadline_start = time.time() - 100.0
    return s, llm_calls, analysis


def _floor_lines(log_lines):
    return [(lvl, msg) for lvl, msg in log_lines if "V18.20.3.13" in msg]


# ═══════════════════════════════════════════════════════════════════════════
# 1) Floor met → INFO floor line, NO LLM call
# ═══════════════════════════════════════════════════════════════════════════


def test_floor_met_logs_info_and_fires_no_call(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare()
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH_FULL, analysis)
    assert result == _THOROUGH_FULL
    assert llm_calls == [], "floor met must NOT fire any LLM call"
    fl = _floor_lines(s.log_lines)
    assert len(fl) == 1
    lvl, msg = fl[0]
    assert lvl == "INFO"
    assert "V18.20.3.13 Thorough theorist floor: 2/2 authors in thorough" in msg
    assert "ALL IN THOROUGH" in msg


# ═══════════════════════════════════════════════════════════════════════════
# 2) Floor unmet → ONE targeted call, prompt carries names + source, append,
#    after-line reports the measured improvement
# ═══════════════════════════════════════════════════════════════════════════


def test_floor_unmet_fires_one_targeted_call_and_appends(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare(responses=[_CANNED])
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, analysis)
    # ONE logical call (first response non-empty → no nudge retry).
    assert len(llm_calls) == 1
    call = llm_calls[0]
    assert call["model"] == "test-model"
    assert call["max_tokens"] == 2048
    # Prompt carries the missing author name from the RUNTIME analysis…
    assert "Ibarra" in call["prompt"]
    # …ONLY the missing contributor (Voss is already covered — the
    # contributor list must not ask for it)…
    _names_line = (
        call["prompt"]
        .split("as described in the chapter source:\n\n", 1)[1]
        .split("\n\n### CONSTRAINTS", 1)[0]
    )
    assert _names_line.strip() == "Ibarra"
    # …the source excerpt (clamped chapter content)…
    assert "SOURCE_MARKER_Q7" in call["prompt"]
    assert "Chapter One body" in call["prompt"]
    # …the thorough tail (style anchor) and the heading…
    assert "closing phrase of the thorough" in call["prompt"]
    assert 'Chapter: "Chapter One"' in call["prompt"]
    # …and the house prompt shape + no-think instruction slot.
    assert "<thorough_addition>" in call["prompt"]
    assert "### ROLE ###" in call["prompt"]
    # The canned addition is appended with a paragraph break.
    assert result == _THOROUGH + "\n\n" + _ADDITION
    # Floor line = WARNING (unmet), after-line = INFO with the measured
    # before/after and the author count.
    fl = _floor_lines(s.log_lines)
    assert any(
        lvl == "WARNING" and "Thorough theorist floor: 1/2 authors in thorough" in msg
        for lvl, msg in fl
    )
    assert any(
        lvl == "INFO"
        and "V18.20.3.13 Thorough gap-fill: floor 1/2 → 2/2 (added paragraphs for 1 authors)" in msg
        for lvl, msg in fl
    )


def test_source_clamped_to_40k_chars(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare(responses=[_CANNED])
    big_source = "x" * 100_000 + _SOURCE
    s._thorough_theorist_floor("Chapter One", big_source, _THOROUGH, analysis)
    # The prompt's chapter-content block is clamped like the
    # dedicated-thorough prompt (~40k chars), not the full 100k source.
    assert len(llm_calls) == 1
    assert "x" * 41_000 not in llm_calls[0]["prompt"]
    assert len(llm_calls[0]["prompt"]) < 60_000


# ═══════════════════════════════════════════════════════════════════════════
# 3) Deadline exceeded + floor unmet → no call, honest WARNING floor line
# ═══════════════════════════════════════════════════════════════════════════


def test_deadline_exceeded_no_call_honest_warning(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare(deadline_dead=True)
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, analysis)
    assert llm_calls == [], "deadline exceeded must suppress the repair call"
    assert result == _THOROUGH
    fl = _floor_lines(s.log_lines)
    # The floor verdict is recorded honestly as unmet (WARNING)…
    assert any(
        lvl == "WARNING" and "Thorough theorist floor: 1/2 authors in thorough" in msg
        for lvl, msg in fl
    )
    # …and the real _deadline_exceeded skip line fired for this phase.
    assert any(
        "skipping optional phase: thorough theorist floor gap-fill" in msg
        for _lvl, msg in s.log_lines
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4) LLM call returns empty → WARNING, thorough unchanged, no crash
# ═══════════════════════════════════════════════════════════════════════════


def test_empty_llm_response_warning_thorough_unchanged(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    # Empty first response → the real empty-retry wrapper fires one nudge
    # retry (also empty) → _call_llm_with_empty_retry returns None.
    s, llm_calls, analysis = _make_bare(responses=["", ""])
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, analysis)
    assert len(llm_calls) == 2, "one logical call (initial + empty-retry nudge)"
    assert result == _THOROUGH
    fl = _floor_lines(s.log_lines)
    assert any(
        lvl == "WARNING" and "Thorough gap-fill call returned empty" in msg for lvl, msg in fl
    )
    assert any("floor stays 1/2" in msg for _lvl, msg in fl)


# ═══════════════════════════════════════════════════════════════════════════
# 5) Floor machinery crashes → WARNING, chapter continues (fail-soft)
# ═══════════════════════════════════════════════════════════════════════════


def test_floor_crash_fails_soft(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    # A poisoned analysis (non-string) makes check_coverage raise inside
    # the floor — the house fail-soft pattern must absorb it.
    s, llm_calls, _bad_analysis = _make_bare(analysis=12345)
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, _bad_analysis)
    assert result == _THOROUGH, "crash must return the thorough unchanged"
    assert llm_calls == []
    assert any(
        lvl == "WARNING" and "Thorough theorist floor failed (non-fatal)" in msg
        for lvl, msg in s.log_lines
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6) Source-pin: the floor is wired to check_coverage + the runtime analysis
#    (NOT a hardcoded list) and called on the FINAL thorough in the flow
# ═══════════════════════════════════════════════════════════════════════════


class TestFloorWiringSourcePins:
    def test_method_uses_runtime_check_coverage(self):
        # V18.20.4.7 (P5 / O-a2): the method lives in its own module now —
        # it is the mixin's whole body, so one split suffices.
        method_src = _FLOOR_MODULE_SRC.split("def _thorough_theorist_floor", 1)[1]
        # The missing list is DERIVED at runtime from the deterministic
        # analysis via check_coverage — never a hardcoded name list.
        assert "from core.preprocessing.deterministic_analyzer import check_coverage" in method_src
        assert "_cov = check_coverage(analysis, thorough)" in method_src
        assert '", ".join(_missing)' in method_src
        # ONE logical LLM call, deadline-gated, CoT-guarded.
        assert "self._call_llm_with_empty_retry(" in method_src
        assert 'self._deadline_exceeded("thorough theorist floor gap-fill")' in method_src
        assert "detect_cot_narrative" in method_src
        # The exact floor/after log-line formats.
        assert "V18.20.3.13 Thorough theorist floor: " in method_src
        assert "V18.20.3.13 Thorough gap-fill: floor " in method_src

    def test_call_site_passes_the_runtime_analysis(self):
        # The delegate in _summarize_inner runs on the FINAL thorough and
        # reuses the SAME analysis lookup the recall floor uses.
        assert "thorough = self._thorough_theorist_floor(" in _SUMMARIZER_SRC
        assert '_analysis_rf or ""' in _SUMMARIZER_SRC
        # The floor runs right before the recall-floor probe (final-set
        # ordering: measure-on-final, floor-before-probe).
        floor_pos = _SUMMARIZER_SRC.index("thorough = self._thorough_theorist_floor(")
        probe_pos = _SUMMARIZER_SRC.index(
            "from core.summarisation.recall_floor import deterministic_recall_floor"
        )
        assert floor_pos < probe_pos

    def test_no_hardcoded_author_names_in_runtime(self):
        # Belt-and-suspenders for THIS change (the permanent tree-wide
        # guard lives in tests/test_v182039_audit_fixes.py): the fixtures'
        # synthetic names must never appear in the runtime file(s).
        # V18.20.4.7 (P5 / O-a2): the floor method moved to its own module —
        # scan BOTH files (assertion unchanged).
        for _src in (_SUMMARIZER_SRC, _FLOOR_MODULE_SRC):
            assert "AuthorA" not in _src
            assert "AuthorB" not in _src


# ═══════════════════════════════════════════════════════════════════════════
# 7) Bonus: trivial thorough → repair skipped honestly (floor line stays)
# ═══════════════════════════════════════════════════════════════════════════


def test_trivial_thorough_skips_repair_honestly(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare()
    stub_thorough = "Short."  # < 50 words — not safely extendable
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, stub_thorough, analysis)
    assert result == stub_thorough
    assert llm_calls == []
    fl = _floor_lines(s.log_lines)
    assert any(
        lvl == "WARNING" and "Thorough theorist floor: 0/2 authors in thorough" in msg
        for lvl, msg in fl
    )
    assert any("Thorough gap-fill skipped — thorough too short" in msg for _lvl, msg in fl)


# ═══════════════════════════════════════════════════════════════════════════
# 8) Bonus: CoT-shaped response → discarded (V18.16.0.1 guard class)
# ═══════════════════════════════════════════════════════════════════════════


def test_cot_response_discarded(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, analysis = _make_bare(responses=[_COT_CANNED])
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, analysis)
    assert len(llm_calls) == 1
    assert result == _THOROUGH, "CoT output must never be appended as prose"
    assert any(
        lvl == "WARNING" and "looks like CoT" in msg for lvl, msg in _floor_lines(s.log_lines)
    )


def test_missing_analysis_is_a_noop(monkeypatch):
    """No analysis → nothing measurable → no log line, no call (recall-floor
    house style: the floor logs nothing when the theorist list is absent)."""
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    s, llm_calls, _ = _make_bare(analysis="")
    result = s._thorough_theorist_floor("Chapter One", _SOURCE, _THOROUGH, "")
    assert result == _THOROUGH
    assert llm_calls == []
    assert _floor_lines(s.log_lines) == []


if __name__ == "__main__":  # pragma: no cover — manual run convenience
    sys.exit(pytest.main([__file__, "-v"]))
