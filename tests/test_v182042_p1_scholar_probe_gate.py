"""V18.20.4.2 (P1) — the F9 scholar-reflection probe-gate (Phase 3.c).

The banked top perf item: the scholar-reflection call burned 479.5s = 30%
of all LLM time on the V18.20.3.14 rig for ZERO usable output (truncated
at the 6144 cap mid-gap-analysis, verdict UNRELIABLE in 3/5 runs), while
the deterministic theorist judge + batch gap-fill performed the entire gap
detection for 62s. The approved P1 lever: a deterministic probe-gate that
mirrors the V18.20.3.11 consolidation skip
(``bullet_consolidation.py:263-288``: rapidfuzz probe → 0 mergeable pairs
→ skip the 218-290s LLM call).

The probe: ``scholar_reflection`` already extracts ``theorists_found``
(the deterministic "Surname (year)" list from the source). The prompt asks
the LLM to verify EACH appears in the summary. If they are ALL already
covered by the primary bullets (a well-parsing primary), the LLM call has
nothing to add for its scope → skip it entirely (no recover_vram, no
6144-token call). A probe CRASH never skips (``_probe_missing = -1``
falls through to the LLM call — the same fail-soft contract as the .3.11
consolidation skip).

Scope note (documented in the CHANGELOG): this gate fires on the "already
complete" path. The .3.14-specific burn (gaps existed, the call
ramble-truncated) needs the larger budget-cut / reorder — flagged as
Phase-3.c continued, NOT in this release (surgical P1 = the .3.11 mirror
only; no output caps touched, the 6144 cap stands).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Hermeticity stub (same as test_v18202_system_fixes / test_v182041):
# markitdown + tiktoken are not installed in this sandbox; the eager
# core.summarisation import chain pulls them.
_SCHOLAR = _project_root / "core" / "summarisation" / "scholar_reflection.py"
_BCONS = _project_root / "core" / "summarisation" / "bullet_consolidation.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source-pin layer (headless, always runs)
# ═══════════════════════════════════════════════════════════════════════════


class TestScholarProbeGateSourcePins:
    def test_file_parses(self):
        ast.parse(_src(_SCHOLAR))

    def test_probe_gate_present_before_llm_call(self):
        """The probe-gate must run BEFORE the 6144-token call_llm."""
        src = _src(_SCHOLAR)
        probe_pos = src.find("_probe_missing = -1")
        call_pos = src.find("call_llm(prompt, temperature=temperature, max_tokens=6144)")
        assert probe_pos != -1 and call_pos != -1
        assert probe_pos < call_pos, "the probe-gate must run BEFORE the 6144-token LLM call"

    def test_skip_path_returns_before_recover_vram(self):
        """Skip saves the 15s pre-scholar recover_vram too."""
        src = _src(_SCHOLAR)
        skip_pos = src.find('result["scholar_reflections"] = ""\n        return')
        recover_pos = src.find('recover_vram(context="pre-scholar-reflection"')
        assert skip_pos != -1 and recover_pos != -1
        assert skip_pos < recover_pos, (
            "the probe-gate skip must return BEFORE recover_vram (the 15s "
            "delay is pointless when the LLM call is skipped)"
        )

    def test_probe_never_skips_on_crash(self):
        """``_probe_missing = -1`` (probe crash) must fall through to the
        LLM call — the same fail-soft contract as the .3.11 consolidation
        skip's ``_probe_merged = -1``."""
        src = _src(_SCHOLAR)
        assert "_probe_missing = -1" in src
        assert "except Exception:\n            _probe_missing = -1" in src
        # the only skip condition is == 0 (probe said "all covered")
        assert "if _probe_missing == 0:" in src

    def test_skip_logs_the_311_mirror(self):
        """The skip INFO line must name the .3.11 consolidation skip
        (the proven precedent this gate mirrors)."""
        src = _src(_SCHOLAR)
        skip_pos = src.find("if _probe_missing == 0:")
        block = src[skip_pos : src.find("\n    theorists_hint", skip_pos)]
        assert "Scholar reflection SKIPPED (probe-gate)" in block
        assert "V18.20.3.11" in block
        assert "consolidation skip" in block

    def test_consolidation_skip_still_intact(self):
        """The .3.11 template this gate mirrors must still be present in
        bullet_consolidation.py (regression guard for the reference pattern)."""
        src = _src(_BCONS)
        assert "_probe_merged = -1" in src
        assert "Bullet consolidation SKIPPED" in src
        assert "if _probe_merged == 0:" in src


# ═══════════════════════════════════════════════════════════════════════════
# Behavioral layer (pure Python — scholar_reflection is a module function)
# ═══════════════════════════════════════════════════════════════════════════


def _make_call():
    """A MagicMock call_llm that records invocations + returns a
    truncated-looking empty response (the .3.14 shape)."""
    call = MagicMock(return_value="")
    return call


def _make_fns(call_llm):
    """Build the dependency tuple scholar_reflection expects."""
    pm = MagicMock()
    pm.render_template.return_value = "prompt"
    recover = MagicMock()
    strip = MagicMock(side_effect=lambda x: x)
    return dict(
        max_context_tokens=32768,
        language="en",
        temperature=0.7,
        prompt_manager=pm,
        recover_vram=recover,
        call_llm=call_llm,
        strip_thinking=strip,
    )


class TestScholarProbeGateBehavior:
    def _result_with_bullets(self, bullets):
        return {
            "executive_summary": "An exec summary.",
            "bullet_points": list(bullets),
            "thorough_summary": "A thorough summary.",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }

    def test_skips_when_all_theorists_already_covered(self):
        """The .3.14 no-yield case on the 'already complete' path: the
        primary bullets already mention every cited theorist → the scholar
        call has nothing to add for its scope → SKIPPED."""
        from core.summarisation.scholar_reflection import scholar_reflection

        # source cites Voss (1948) and Ibarra (1952) — synthetic names
        # (the deny-list rule: no book-derived hardcoding in runtime; the
        # TEST fixture using synthetic names is the house pattern, see
        # gap_fill_batch.py:271-273).
        text = "Voss (1948) discussed identity. Ibarra (1952) extended it."
        bullets = [
            "Voss (1948) — origins of identity.",
            "Ibarra (1952) — the extension.",
        ]
        result = self._result_with_bullets(bullets)
        call = _make_call()
        logs: list[tuple[str, str]] = []
        scholar_reflection(
            "Chapter 1",
            text,
            result,
            **_make_fns(call),
            log=lambda msg, level="INFO": logs.append((msg, level)),
        )
        assert call.call_count == 0, "the LLM call must be SKIPPED (probe-gate)"
        assert result["scholar_reflections"] == ""
        assert any("SKIPPED (probe-gate)" in m for m, _ in logs), "the skip must log the INFO line"

    def test_runs_when_theorists_are_missing(self):
        """The .3.14 case where gaps exist: the probe finds missing
        theorists → falls through to the LLM call (the gate does NOT skip
        when the call MIGHT contribute)."""
        from core.summarisation.scholar_reflection import scholar_reflection

        # 'Smith (1960)' matches the scholar regex's [A-Z][a-z]+ \(year\)
        # pattern; the bullets cover Voss + Ibarra but NOT Smith.
        text = (
            "Voss (1948) discussed identity. Ibarra (1952) extended it. Smith (1960) added nuance."
        )
        bullets = ["Voss (1948) — origins.", "Ibarra (1952) — extension."]
        result = self._result_with_bullets(bullets)
        call = _make_call()
        scholar_reflection(
            "Chapter 1",
            text,
            result,
            **_make_fns(call),
            log=lambda msg, level="INFO": None,
        )
        assert call.call_count == 1, "the LLM call must run when the probe finds missing theorists"

    def test_runs_when_no_theorists_in_source(self):
        """No theorists_found → the probe block is skipped (``if
        theorists_found:`` False) → ``_probe_missing`` stays -1 → run the
        LLM call (no probe data, can't skip)."""
        from core.summarisation.scholar_reflection import scholar_reflection

        text = "A source with no cited authors at all."
        result = self._result_with_bullets(["A bullet."])
        call = _make_call()
        scholar_reflection(
            "Chapter 1",
            text,
            result,
            **_make_fns(call),
            log=lambda msg, level="INFO": None,
        )
        assert call.call_count == 1

    def test_probe_crash_never_skips(self):
        """A probe crash → ``_probe_missing = -1`` → fall through to the
        LLM call (the .3.11 fail-soft)."""
        from core.summarisation.scholar_reflection import scholar_reflection

        text = "Voss (1948) and Ibarra (1952)."
        result = {
            "executive_summary": "x",
            "bullet_points": ["Voss (1948)", object()],
            "thorough_summary": "y",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        # ``object()`` is fine for the _summary_overview generator
        # (f'- {bp}' formats it) but ``str.join`` raises TypeError on the
        # non-string element inside the probe → caught → _probe_missing=-1.
        call = _make_call()
        scholar_reflection(
            "Chapter 1",
            text,
            result,
            **_make_fns(call),
            log=lambda msg, level="INFO": None,
        )
        assert call.call_count == 1, "a probe crash must NEVER skip the LLM call (fail-soft, .3.11)"

    def test_skip_path_skips_recover_vram(self):
        """The skip must return BEFORE the 15s recover_vram delay."""
        from core.summarisation.scholar_reflection import scholar_reflection

        text = "Voss (1948). Ibarra (1952)."
        bullets = ["Voss (1948) — x.", "Ibarra (1952) — y."]
        result = self._result_with_bullets(bullets)
        call = _make_call()
        fns = _make_fns(call)
        recover = fns["recover_vram"]
        scholar_reflection(
            "Chapter 1",
            text,
            result,
            **fns,
            log=lambda msg, level="INFO": None,
        )
        assert recover.call_count == 0, (
            "recover_vram must not run when the call is skipped (saves the 15s pre-scholar delay)"
        )

    def test_gapfill_only_also_skips(self):
        """The gapfill-only path delegates to scholar_reflection — the
        probe-gate covers it too."""
        from core.summarisation.scholar_reflection import (
            scholar_reflection_gapfill_only,
        )

        text = "Voss (1948). Ibarra (1952)."
        bullets = ["Voss (1948) — x.", "Ibarra (1952) — y."]
        result = self._result_with_bullets(bullets)
        call = _make_call()
        scholar_reflection_gapfill_only(
            "Chapter 1",
            text,
            result,
            **_make_fns(call),
            log=lambda msg, level="INFO": None,
        )
        assert call.call_count == 0
        assert result["scholar_reflections"] == ""
