"""V18.20.3.11 audit-fix regression tests (Phase 3.b cap right-sizing + F2 + F7).

Scope of this version (all approved by the user in the 2026-08-31 session):

  1. Consolidation skip — the LLM consolidation call merged 0 bullets in
     THREE consecutive rig runs (.3.7/.3.8/.3.9: "41 → 41, merged 0") while
     burning 218-290s/chapter. A deterministic probe (the same rapidfuzz
     0.92 pass used as the LLM-path fallback) now gates the call: probe
     finds 0 mergeable pairs → skip; probe finds candidates (or crashes)
     → the LLM runs exactly as before.
  2. Scholar compactness — the scholar response truncated at the 6144 cap
     2-of-3 rig runs (25-26k chars, cut before <gap_fill_bullets> closed),
     making its verdict unreliable. The prompt now carries an explicit
     compactness contract (≤8 reflections × ≤30 words; ≤12 gap-fill
     bullets × ≤45 words) sized to finish inside the cap.
  3. Thorough continuation — the primary's partial thorough (423-763
     words, cut at the 8192 cap in all three rig runs) was DISCARDED and
     the dedicated thorough call re-derived from scratch (~371s). The
     draft now travels into the dedicated prompt ("complete and deepen"),
     and the primary prompt instructs a clean-sentence close at the
     boundary. (The primary cap itself is NOT raised — the V18.3.6
     thermal history forbids it.)
  4. F2 — the shipped-summary semantic-dedup threshold aligns 0.92 → 0.85
     with the keypoints builder (the .3.8 conciseness cap: near-dup pairs
     in the 0.85-0.92 band shipped in the chapter summary but were
     dropped from keypoints).
  5. F7 — the estimator's typical band recalibrates 15 → 10 calls/chapter
     (rig-measured 9, minus the .3.11 consolidation skip).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Stub the optional heavy deps exactly like tests/test_v18203_incremental_checkpoint.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

ROOT = Path(__file__).resolve().parent.parent

from core.summarisation.bullet_consolidation import consolidate_bullets  # noqa: E402
from core.summarisation.prompt_assembly import (  # noqa: E402
    build_dedicated_thorough_prompt,
)


def _probe_passthrough(bullets):
    """Deterministic-probe stub: 0 mergeable pairs (the rig shape)."""
    return list(bullets)


def _probe_merges(bullets):
    """Deterministic-probe stub: 1 mergeable pair (candidates exist)."""
    return bullets[:-1]


def _probe_crashes(bullets):
    raise RuntimeError("probe backend down")


def _llm_never_called(prompt, model=None, temperature=None, max_tokens=None):
    raise AssertionError("LLM consolidation call fired when it must be skipped")


def _llm_returns_empty(prompt, model=None, temperature=None, max_tokens=None):
    return None  # recorded call; empty response keeps originals


class _StubPromptManager:
    def render_template(self, name, **kwargs):
        return "PROMPT"


def _make_deps(probe, call_llm):
    logs = []

    def log(msg, level="INFO"):
        logs.append((level, msg))

    return {
        "leak_guard_fire_count": 0,
        "prompt_manager": _StubPromptManager(),
        "select_prompt": lambda base: base,
        "call_llm_with_empty_retry": call_llm,
        "primary_model": "stub-model",
        "temperature": 0.2,
        "strip_thinking": lambda s: s,
        "consolidate_duplicate_claims": probe,
        "log": log,
    }, logs


# ═════════════════════════════════════════════════════════════════════════════
# 1) Consolidation skip — probe-gated LLM call
# ═════════════════════════════════════════════════════════════════════════════


class TestConsolidationSkip:
    BULLETS = [f"Distinct takeaway {i} about concept {chr(65 + i)}." for i in range(8)]

    def test_probe_zero_skips_llm(self):
        """The rig shape: 0 mergeable pairs at the deterministic probe →
        the 218-290s LLM call must NOT fire."""
        deps, logs = _make_deps(_probe_passthrough, _llm_never_called)
        out, _fire = consolidate_bullets(list(self.BULLETS), **deps)
        assert out == self.BULLETS
        assert any("SKIPPED" in m and "0 mergeable pairs" in m for _, m in logs)

    def test_probe_candidates_still_runs_llm(self):
        """Probe finds mergeable pairs → the LLM path runs unchanged."""
        calls = []

        def llm(prompt, model=None, temperature=None, max_tokens=None):
            calls.append(prompt)
            return None

        deps, logs = _make_deps(_probe_merges, llm)
        out, _fire = consolidate_bullets(list(self.BULLETS), **deps)
        assert len(calls) == 1
        assert calls[0] == "PROMPT"
        # empty LLM response → originals kept (existing behavior)
        assert out == self.BULLETS

    def test_probe_crash_never_skips_llm(self):
        """A probe failure must NOT disable the LLM call (fail to the
        known-good path, not to the cheap path)."""
        calls = []

        def llm(prompt, model=None, temperature=None, max_tokens=None):
            calls.append(prompt)
            return None

        deps, logs = _make_deps(_probe_crashes, llm)
        out, _fire = consolidate_bullets(list(self.BULLETS), **deps)
        assert len(calls) == 1

    def test_small_list_short_circuits_before_probe(self):
        """<5 bullets: unchanged early exit (probe and LLM never run)."""
        probe_calls = []

        def probe(bullets):
            probe_calls.append(bullets)
            return list(bullets)

        deps, logs = _make_deps(probe, _llm_never_called)
        out, _fire = consolidate_bullets(["a", "b"], **deps)
        assert out == ["a", "b"]
        assert probe_calls == []

    def test_real_rapidfuzz_probe_on_distinct_bullets_skips(self):
        """Integration: the REAL deterministic probe (rapidfuzz 0.92) on
        8 clearly-distinct synthetic bullets → skip. This is the exact
        decision shape the rig's 41-bullet list hits."""
        from core.summarisation.bullet_consolidation import (
            consolidate_duplicate_claims,
        )

        deps, logs = _make_deps(consolidate_duplicate_claims, _llm_never_called)
        out, _fire = consolidate_bullets(list(self.BULLETS), **deps)
        assert out == self.BULLETS
        assert any("SKIPPED" in m for _, m in logs)

    def test_real_rapidfuzz_probe_on_near_dups_runs_llm(self):
        """Integration: near-duplicate bullets (≥0.92 similar) → probe
        finds candidates → the LLM call fires."""
        from core.summarisation.bullet_consolidation import (
            consolidate_duplicate_claims,
        )

        bullets = [f"Takeaway {i} about concept X." for i in range(6)]
        # a near-exact duplicate pair (subject-swap class)
        bullets += [
            "AuthorA established the three-part framework for integration.",
            "AuthorB established the three-part framework for integration.",
        ]
        calls = []

        def llm(prompt, model=None, temperature=None, max_tokens=None):
            calls.append(prompt)
            return None

        deps, logs = _make_deps(consolidate_duplicate_claims, llm)
        consolidate_bullets(bullets, **deps)
        assert len(calls) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 2) Scholar compactness contract (cap-aware prompt shortening)
# ═════════════════════════════════════════════════════════════════════════════


class TestScholarPromptCompactness:
    def test_prompt_carries_compactness_contract(self):
        src = (ROOT / "prompts" / "summarisation" / "scholar_reflection.md").read_text(
            encoding="utf-8"
        )
        assert "KEEP THE RESPONSE COMPACT" in src
        assert "at most 8 reflection bullets" in src
        assert "at most 12 gap-fill bullets" in src
        # the truncation-unreliability warning must be stated in the prompt
        assert "discarded as unreliable" in src


# ═════════════════════════════════════════════════════════════════════════════
# 3) Thorough continuation (designated continuation, not a cold re-derivation)
# ═════════════════════════════════════════════════════════════════════════════


class TestThoroughContinuation:
    def test_prompt_with_draft_contains_continuation_block(self):
        prompt = build_dedicated_thorough_prompt(
            "Chapter One",
            "Chapter content here. " * 50,
            "Exec summary.",
            ["Bullet one.", "Bullet two."],
            draft="The chapter opens by framing identity as a lifelong",
        )
        assert "### DRAFT FROM THE PRIMARY PASS ###" in prompt
        assert "<draft>" in prompt
        assert "COMPLETE and DEEPEN this draft" in prompt
        # the draft text itself is embedded
        assert "identity as a lifelong" in prompt

    def test_prompt_without_draft_has_no_block(self):
        prompt = build_dedicated_thorough_prompt(
            "Chapter One",
            "Chapter content here. " * 50,
            "Exec summary.",
            ["Bullet one."],
        )
        assert "DRAFT FROM THE PRIMARY PASS" not in prompt
        # V0.05 (F9b): the classic contract is unchanged EXCEPT the word
        # target, which now scales to the source (this fixture is ~100
        # words → a ~45-word target) — never the absolute 800-1200.
        import re as _re

        assert _re.search(r"\b\d+-\d+ word thorough summary", prompt)
        assert "800-1200" not in prompt

    def test_empty_draft_is_inert(self):
        prompt = build_dedicated_thorough_prompt(
            "Chapter One", "content", "exec", ["b"], draft="   "
        )
        assert "DRAFT FROM THE PRIMARY PASS" not in prompt

    def test_oversized_draft_is_clamped(self):
        prompt = build_dedicated_thorough_prompt(
            "Chapter One", "content", "exec", ["b"], draft="x" * 20000
        )
        # clamped at 6000 chars — the draft must not eat the prompt budget
        draft_block = prompt.split("<draft>")[1].split("</draft>")[0]
        assert len(draft_block.strip()) <= 6000

    def test_summarizer_passes_partial_as_draft(self):
        """Policy pin: the call site must pass the primary's partial
        thorough into the dedicated prompt (the truncation-paid-twice
        fix)."""
        # V0.18 (Phase 5.1): moved VERBATIM to chapter_phases.py — pin follows.
        src = (ROOT / "core" / "summarisation" / "chapter_phases.py").read_text(encoding="utf-8")
        assert "draft=(thorough or None)" in src

    def test_primary_prompts_close_clean_at_boundary(self):
        """Both primary prompt variants instruct a clean-sentence close at
        the output limit so the partial is usable as the draft."""
        for name in ("default.md", "default_lowbit.md"):
            src = (ROOT / "prompts" / name).read_text(encoding="utf-8")
            assert "close </thorough_summary> at a clean sentence boundary" in src


# ═════════════════════════════════════════════════════════════════════════════
# 4) F2 — dedup threshold alignment (0.92 → 0.85, keypoints parity)
# ═════════════════════════════════════════════════════════════════════════════


class TestF2DedupThresholdAlignment:
    def test_shipped_dedup_default_is_085(self):
        """The shipped-summary semantic-dedup delegate must default to
        0.85 — parity with the keypoints embedding dedup."""
        src = (ROOT / "core" / "summarisation" / "summarizer.py").read_text(encoding="utf-8")
        assert "threshold: float = 0.85" in src
        assert "threshold: float = 0.92" not in src

    def test_validator_signature_unchanged_for_other_callers(self):
        """The validator function's own default stays untouched — only the
        shipped path (the Summarizer delegate) aligns."""
        import inspect

        from core.summarisation.summary_validator import semantic_dedup_bullets

        sig = inspect.signature(semantic_dedup_bullets)
        default = sig.parameters["threshold"].default
        assert default == 0.92

    def test_delegate_passes_threshold_through(self):
        """Behavioral: the delegate passes its threshold to the validator
        (monkeypatch the validator function the delegate binds)."""
        from core.summarisation import summarizer as sz_mod

        captured = {}

        def fake_dedup(bullets, threshold=None, log=None):
            captured["threshold"] = threshold
            return bullets

        original = sz_mod.sv_semantic_dedup_bullets
        sz_mod.sv_semantic_dedup_bullets = fake_dedup
        try:

            class _FakeSumm:
                _semantic_dedup_bullets = sz_mod.Summarizer._semantic_dedup_bullets
                log = staticmethod(lambda msg, level="INFO": None)

            _FakeSumm._semantic_dedup_bullets(_FakeSumm(), ["a bullet"])
        finally:
            sz_mod.sv_semantic_dedup_bullets = original
        assert captured["threshold"] == 0.85


# ═════════════════════════════════════════════════════════════════════════════
# 5) F7 — estimator band recalibration (15 → 10 typical)
# ═════════════════════════════════════════════════════════════════════════════


class TestF7EstimatorBand:
    def test_bands_are_10_and_40(self):
        src = (ROOT / "core" / "pipeline" / "token_estimator.py").read_text(encoding="utf-8")
        assert "base_calls_per_chapter = 10" in src
        assert "worst_calls_per_chapter = 40" in src
        assert "base_calls_per_chapter = 15" not in src
        assert "10 calls/chapter" in src
