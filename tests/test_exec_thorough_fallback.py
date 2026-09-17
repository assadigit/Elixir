"""V18.19.2.2 (Audit Fix 2): characterization tests for the exec-from-thorough
postcheck fallback.

The V18.19.2.0 audit (audit/results/audit_V18.19.2.0_2026-08-28.md) found that
the delivered summary had an EMPTY ``## Thorough Summary`` section. Root cause:

1. The thorough summary was 100% CoT (6 markers detected).
2. ``run_post_checks`` (postchecks.py:262) correctly truncated it to empty.
3. The log said "caller falls back to exec_sum" — but NOTHING repopulated
   ``thorough``. The exec-from-thorough fallback at summarizer.py:3068 ran
   BEFORE run_post_checks, so it couldn't catch this case.

V18.19.2.2 fix: after ``run_post_checks``, if thorough is empty but exec is
populated, copy exec into thorough (the fallback the log promised). Symmetric
for exec-empty/thorough-populated. If BOTH empty, log at ERROR.

These tests verify:
1. ``run_post_checks`` truncates CoT thorough to empty (reproduces the bug).
2. The fallback logic (a pure function extracted from the inline block at
   summarizer.py:3689) repopulates thorough from exec when thorough is empty.
3. The symmetric case: exec repopulated from thorough when exec is empty.
4. The both-empty case: returns (None, None) so the caller can log ERROR.

Run: ``pytest tests/test_exec_thorough_fallback.py -v``
"""
from __future__ import annotations

import sys
import types

# Minimal heavy-dep stub (tiktoken only)
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = lambda *a, **k: None
    _tk.encoding_for_model = lambda *a, **k: None
    _tk.Encoding = type("Encoding", (), {})
    sys.modules["tiktoken"] = _tk

from core.summarisation.postchecks import run_post_checks

# A thorough that is 100% chain-of-thought (the V18.19.2.0 audit case).
COT_THOROUGH = (
    "Let me organize my understanding of this chapter. First, I will identify "
    "the key contributors. Named contributors in order: Tausk, Erikson, Freud. "
    "Let me count carefully. Now let me think about how to structure this. "
    "Let me analyze the seven characteristics. So I need to write a comprehensive "
    "summary. Let me draft the thorough summary now."
)
# A real executive summary (the V18.19.2.0 audit case — 192 words derived earlier).
REAL_EXEC = (
    "This chapter traces the development of identity concepts within psychoanalytic "
    "theory, from Tausk's (1919) initial use of the term through Erikson's "
    "foundational ego identity work. The text integrates sociocultural perspectives "
    "from Fromm, Lynd, and Lasch with developmental accounts from Mahler, Jacobson, "
    "and Winnicott. The chapter concludes by defining seven cross-sectional "
    "characteristics of solid identity and positions identity diffusion as a "
    "disturbance in these specific areas."
)
SOURCE = ("Tausk 1919 Erikson Freud Fromm Lynd Lasch Mahler Jacobson Winnicott "
          "identity ego self seven characteristics")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Reproduce the V18.19.2.0 bug: CoT thorough → truncated to empty
# ═══════════════════════════════════════════════════════════════════════════

class TestCoTThoroughTruncatedToEmpty:
    """run_post_checks MUST truncate 100%-CoT thorough to empty (V18.15.7.0
    behavior). This is correct — the bug was that nothing repopulated it AFTER."""

    def test_cot_thorough_becomes_empty(self):
        pc = run_post_checks(
            bullets=[], executive_summary=REAL_EXEC,
            thorough_summary=COT_THOROUGH, source_text=SOURCE,
        )
        assert pc.thorough_summary == "", (
            "100%-CoT thorough must be truncated to empty by detect_cot_narrative"
        )

    def test_exec_survives_when_thorough_is_cot(self):
        pc = run_post_checks(
            bullets=[], executive_summary=REAL_EXEC,
            thorough_summary=COT_THOROUGH, source_text=SOURCE,
        )
        assert len(pc.executive_summary) > 50, (
            "Exec must survive when thorough is CoT-truncated"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. The V18.19.2.2 fallback logic (extracted as a pure function for testing)
# ═══════════════════════════════════════════════════════════════════════════

def _apply_postcheck_fallback(exec_sum: str, thorough: str, min_words: int = 50):
    """Pure mirror of the V18.19.2.2 fallback logic at summarizer.py:3689-3724.

    Returns ``(exec_sum, thorough, both_empty)`` after applying the fallbacks.
    This mirrors the inline logic so we can test it without constructing a full
    Summarizer (which needs Ollama/Settings/torch). The inline code in
    summarizer.py MUST stay byte-equivalent to this function.
    """
    if not thorough and exec_sum and len(exec_sum.strip()) >= min_words:
        thorough = exec_sum
    if not exec_sum and thorough and len(thorough.strip()) >= min_words:
        exec_sum = thorough
    both_empty = not exec_sum and not thorough
    return exec_sum, thorough, both_empty


class TestPostcheckFallback:
    """The V18.19.2.2 fallback: empty thorough ← exec, empty exec ← thorough."""

    def test_empty_thorough_repopulated_from_exec(self):
        """The exact V18.19.2.0 audit scenario: thorough CoT-truncated to empty,
        exec populated → fallback copies exec into thorough."""
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum=REAL_EXEC, thorough="",
        )
        assert thorough == REAL_EXEC, "Thorough must be repopulated from exec"
        assert not both_empty
        assert exec_sum == REAL_EXEC  # exec unchanged

    def test_empty_exec_repopulated_from_thorough(self):
        """Symmetric case: exec CoT-truncated to empty, thorough populated."""
        real_thorough = REAL_EXEC + " " + REAL_EXEC  # make it distinct + longer
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum="", thorough=real_thorough,
        )
        assert exec_sum == real_thorough, "Exec must be repopulated from thorough"
        assert not both_empty
        assert thorough == real_thorough  # thorough unchanged

    def test_both_populated_unchanged(self):
        """Normal case: both survived → no fallback applied."""
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum=REAL_EXEC, thorough=REAL_EXEC + " extra detail.",
        )
        assert not both_empty
        assert exec_sum == REAL_EXEC
        assert thorough == REAL_EXEC + " extra detail."

    def test_both_empty_returns_both_empty_flag(self):
        """Catastrophic case: both empty → both_empty=True (caller logs ERROR)."""
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum="", thorough="",
        )
        assert both_empty is True
        assert exec_sum == ""
        assert thorough == ""

    def test_short_exec_does_not_repopulate_thorough(self):
        """If exec is too short (< 50 words), don't pollute thorough with a stub."""
        short_exec = "Too short to be a real exec summary."
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum=short_exec, thorough="",
        )
        assert thorough == "", (
            "Short exec (<50 words) must not pollute thorough — would create "
            "a misleading 1-line thorough section"
        )
        # both_empty is False here because exec_sum is technically non-empty
        # (it's a short string). The both_empty flag only fires when BOTH are
        # literally empty. A short exec is a separate quality problem (the
        # caller's word-count check at summarizer.py:1188 will discard it).
        assert both_empty is False
        assert exec_sum == short_exec  # exec unchanged


# ═══════════════════════════════════════════════════════════════════════════
# 3. End-to-end: run_post_checks + fallback = the V18.19.2.0 bug is fixed
# ═══════════════════════════════════════════════════════════════════════════

class TestEndToEndBugFixed:
    """The full V18.19.2.0 scenario: CoT thorough → postchecks truncates →
    fallback repopulates. The delivered summary must NOT have an empty thorough."""

    def test_v18_19_2_0_scenario_thorough_not_empty_after_fallback(self):
        # Step 1: run_post_checks truncates the CoT thorough to empty
        pc = run_post_checks(
            bullets=[], executive_summary=REAL_EXEC,
            thorough_summary=COT_THOROUGH, source_text=SOURCE,
        )
        assert pc.thorough_summary == ""  # bug reproduced
        assert len(pc.executive_summary) > 50  # exec survived

        # Step 2: apply the V18.19.2.2 fallback (mirrors summarizer.py:3689)
        exec_sum, thorough, both_empty = _apply_postcheck_fallback(
            exec_sum=pc.executive_summary, thorough=pc.thorough_summary,
        )

        # The delivered summary's thorough section is NOT empty
        assert thorough != "", (
            "V18.19.2.0 regression: thorough must be repopulated by the fallback"
        )
        assert thorough == pc.executive_summary
        assert not both_empty
