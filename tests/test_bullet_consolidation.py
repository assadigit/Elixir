"""V18.11 (Phase 5 Stage 3, Batch 1.3 + 1.4) — bullet_consolidation tests.

Byte-for-byte stability gate for the two consolidation functions extracted
from ``Summarizer``:

- ``consolidate_duplicate_claims`` (Batch 1.3) — deterministic rapidfuzz
  near-dup merge (no LLM).
- ``consolidate_bullets`` (Batch 1.4) — LLM-assisted consolidation with a
  leak-guard that falls back to ``consolidate_duplicate_claims``.

Run: pytest tests/test_bullet_consolidation.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so the import chain (if anything pulls in token_counter) works.
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")

    class _E:
        pass

    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = tk

from core.summarisation.bullet_consolidation import (
    consolidate_bullets,
    consolidate_duplicate_claims,
)

# ── helper: capturing log ──────────────────────────────────────────────────


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


# ── 1. consolidate_duplicate_claims — edge cases ──────────────────────────


class TestConsolidateDuplicateClaimsEdge:
    def test_empty_list(self):
        assert consolidate_duplicate_claims([]) == []

    def test_single_bullet_unchanged(self):
        b = ["Only one bullet here with enough content."]
        assert consolidate_duplicate_claims(b) == b

    def test_two_identical_bullets_deduped(self):
        """Exact duplicates (after punctuation normalization) are deduped to 1."""
        b = [
            "Erikson defined identity as a lifelong process.",
            "Erikson defined identity as a lifelong process.",
        ]
        out = consolidate_duplicate_claims(b)
        assert len(out) == 1

    def test_punctuation_normalization_in_exact_dedup(self):
        """'Erikson (1956) said...' and 'Erikson 1956 said...' (punctuation-stripped
        equal) dedup to 1 — the first-pass exact dedup normalizes punctuation."""
        b = [
            "Erikson (1956) said identity is a lifelong process.",
            "Erikson 1956 said identity is a lifelong process",
        ]
        out = consolidate_duplicate_claims(b)
        # Punctuation-normalized both become "erikson 1956 said identity is a
        # lifelong process" → deduped to 1.
        assert len(out) == 1

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        b = ["Erikson defined identity as a lifelong process."] * 2
        out = consolidate_duplicate_claims(b)  # no log kwarg
        assert isinstance(out, list)


# ── 2. consolidate_duplicate_claims — fuzzy subject merge ─────────────────


class TestConsolidateDuplicateClaimsFuzzy:
    def test_near_dup_different_subject_merged(self):
        """Two bullets differing only in the subject name (≥0.92 similarity,
        ≤6 diff words) merge into 'X and Y both [claim]'."""
        b = [
            "Jacobson views identity consolidation as sine qua non of pathology.",
            "Kernberg views identity consolidation as sine qua non of pathology.",
        ]
        out = consolidate_duplicate_claims(b)
        # Should merge to 1 bullet combining both subjects.
        assert len(out) == 1
        merged = out[0]
        assert "Jacobson" in merged
        assert "Kernberg" in merged
        assert "both" in merged

    def test_unrelated_bullets_preserved(self):
        """Bullets with <0.92 similarity are all preserved (no false merge)."""
        b = [
            "Erikson defined identity as a lifelong developmental process.",
            "Kernberg described borderline personality organisation with splitting.",
            "Lichtenstein proposed identity-as-a-theme recurring across life.",
        ]
        out = consolidate_duplicate_claims(b)
        assert len(out) == 3  # all preserved

    def test_low_similarity_bullets_not_merged(self):
        """Bullets that are topically related but structurally different do NOT
        merge (the 0.92 threshold + ≤6 diff-words guard prevents false merges)."""
        b = [
            "The chapter traces identity from early origins to middle age.",
            "Three clinical frameworks are compared in detail throughout.",
        ]
        out = consolidate_duplicate_claims(b)
        assert len(out) == 2


# ── 3. consolidate_duplicate_claims — log callback ────────────────────────


class TestConsolidateDuplicateClaimsLog:
    def test_log_called_on_merge(self):
        """When a fuzzy merge happens, the log is called with DEBUG level and
        a message containing 'Consolidated' or 'Merged'."""
        cap = _CapturingLog()
        b = [
            "Jacobson views identity consolidation as sine qua non of pathology.",
            "Kernberg views identity consolidation as sine qua non of pathology.",
        ]
        consolidate_duplicate_claims(b, log=cap)
        # At least one DEBUG call (Consolidated + Merged)
        debug_msgs = [m for m, l in cap.calls if l == "DEBUG"]
        assert len(debug_msgs) >= 1
        joined = " ".join(debug_msgs)
        assert "Consolidated" in joined or "Merged" in joined

    def test_no_log_calls_when_no_merge(self):
        """Unrelated bullets → no fuzzy merge → no DEBUG log calls."""
        cap = _CapturingLog()
        b = [
            "Erikson defined identity as a lifelong developmental process.",
            "Kernberg described borderline personality organisation with splitting.",
        ]
        consolidate_duplicate_claims(b, log=cap)
        debug_msgs = [m for m, l in cap.calls if l == "DEBUG"]
        assert debug_msgs == []


# ── 4. consolidate_duplicate_claims — byte-for-byte stability ──────────────


class TestConsolidateDuplicateClaimsByteForByte:
    def test_deterministic_output(self):
        """The same input must produce byte-for-byte identical output."""
        b = [
            "Jacobson views identity consolidation as sine qua non of pathology.",
            "Kernberg views identity consolidation as sine qua non of pathology.",
            "Erikson defined identity as a lifelong developmental process.",
        ]
        r1 = consolidate_duplicate_claims(b, log=_CapturingLog())
        r2 = consolidate_duplicate_claims(b, log=_CapturingLog())
        assert r1 == r2

    def test_order_preserved_for_unrelated(self):
        """Unrelated bullets are returned in their original (deduped) order."""
        b = [
            "Erikson defined identity as a lifelong developmental process.",
            "Kernberg described borderline personality organisation with splitting.",
            "Lichtenstein proposed identity-as-a-theme recurring across life.",
        ]
        out = consolidate_duplicate_claims(b)
        assert out[0].startswith("Erikson")
        assert out[1].startswith("Kernberg")
        assert out[2].startswith("Lichtenstein")

    def test_returns_list_of_strings(self):
        """Output is always a list of str (even if input has non-str)."""
        b = ["Erikson defined identity.", "Erikson defined identity."]
        out = consolidate_duplicate_claims(b)
        assert isinstance(out, list)
        assert all(isinstance(x, str) for x in out)


# ── 5. consolidate_bullets — mocks + edge cases ────────────────────────────


class _FakePromptManager:
    """Minimal prompt_manager stub: render_template returns the bullets
    placeholder-filled, or '' if the template name is 'missing'."""

    def __init__(self, template_result: str = "CONSOLIDATE: {bullets}"):
        self.template_result = template_result
        self.calls = []

    def render_template(self, name, bullets=""):
        self.calls.append((name, bullets))
        if self.template_result is None:
            return ""
        return self.template_result.replace("{bullets}", bullets)


def _make_deps(
    *,
    llm_response: str = "",
    strip_thinking_result: str = "",
    dedup_result=None,
    template_result: str = "CONSOLIDATE: {bullets}",
    llm_raises: Exception = None,
):
    """Build the 8 dependency callables/objects consolidate_bullets needs."""
    pm = _FakePromptManager(template_result=template_result)

    def select_prompt(name):
        return name  # pass-through (no _lowbit variant in tests)

    def call_llm_with_empty_retry(prompt, model=None, temperature=None, max_tokens=None):
        if llm_raises is not None:
            raise llm_raises
        return llm_response

    def strip_thinking(text):
        return strip_thinking_result if strip_thinking_result else text

    def consolidate_duplicate_claims(bullets):
        if dedup_result is not None:
            return dedup_result
        # V18.20.3.11: the default probe reports ONE mergeable pair so the
        # LLM path under test actually runs (the new probe-gate SKIPS the
        # LLM call when the probe finds 0 candidates — see
        # test_v1820311_perf_fixes.py for the skip-path tests). Pass
        # dedup_result=list(bullets) to simulate the probe-zero shape.
        return bullets[:-1] if len(bullets) > 1 else list(bullets)

    return {
        "prompt_manager": pm,
        "select_prompt": select_prompt,
        "call_llm_with_empty_retry": call_llm_with_empty_retry,
        "primary_model": "test-model",
        "temperature": 0.7,
        "strip_thinking": strip_thinking,
        "consolidate_duplicate_claims": consolidate_duplicate_claims,
    }


class TestConsolidateBulletsEdge:
    def test_under_five_bullets_returned_unchanged(self):
        """< 5 bullets short-circuits: returns (bullets, fire_count) with no
        LLM call and fire count unchanged."""
        deps = _make_deps(llm_response="should-not-be-called")
        bullets = [
            "One bullet here.",
            "Two bullet here.",
            "Three bullet here.",
            "Four bullet here.",
        ]
        out, fire = consolidate_bullets(
            bullets, leak_guard_fire_count=0, log=_CapturingLog(), **deps
        )
        assert out == bullets
        assert fire == 0
        # No LLM call was made
        assert deps["prompt_manager"].calls == []

    def test_prompt_not_found_returns_bullets(self):
        """When render_template returns '', returns (bullets, fire_count) with
        no LLM call and fire count unchanged."""
        deps = _make_deps(template_result=None, llm_response="should-not-be-called")
        bullets = [f"Bullet number {i} with enough content." for i in range(5)]
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        assert out == bullets
        assert fire == 0
        # A WARNING about missing prompt was logged
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("prompt file not found" in w for w in warnings)

    def test_empty_llm_response_returns_bullets(self):
        """When the LLM returns empty/short (<50 chars), returns (bullets, fire)."""
        deps = _make_deps(llm_response="short")  # 5 chars < 50
        bullets = [f"Bullet number {i} with enough content." for i in range(5)]
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        assert out == bullets
        assert fire == 0
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("empty response" in w for w in warnings)

    def test_llm_exception_returns_bullets(self):
        """When the LLM call raises, the exception is caught and (bullets, fire)
        returned with fire count unchanged."""
        deps = _make_deps(llm_raises=RuntimeError("ollama down"))
        bullets = [f"Bullet number {i} with enough content." for i in range(5)]
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        assert out == bullets
        assert fire == 0
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("Bullet consolidation failed" in w for w in warnings)


# ── 6. consolidate_bullets — clean LLM consolidation path ──────────────────


class TestConsolidateBulletsCleanLlm:
    def test_clean_consolidated_bullets_returned(self):
        """When the LLM returns clean consolidated bullets (no leaked
        metadata), they are returned and fire count stays 0."""
        # 5 input bullets; LLM returns 3 clean merged bullets
        bullets = [f"Bullet number {i} with enough content here." for i in range(5)]
        llm_resp = (
            "- First consolidated bullet with enough content.\n"
            "- Second consolidated bullet with enough content.\n"
            "- Third consolidated bullet with enough content."
        )
        deps = _make_deps(llm_response=llm_resp)
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        assert len(out) == 3
        assert fire == 0
        infos = [m for m, l in cap.calls if l == "INFO"]
        assert any("Bullet consolidation:" in i and "→" in i for i in infos)

    def test_no_improvement_keeps_original(self):
        """When the LLM returns MORE bullets than input (no improvement),
        the original bullets are kept (consolidated > len(bullets) branch)."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        # LLM returns 7 bullets (more than 5) → no improvement → keep original
        llm_resp = "\n".join(f"- Consolidated bullet number {i} here." for i in range(7))
        deps = _make_deps(llm_response=llm_resp)
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        assert out == bullets
        assert fire == 0


# ── 7. consolidate_bullets — leak-guard fallback path ──────────────────────


class TestConsolidateBulletsLeakGuard:
    def test_leaked_metadata_falls_back_and_increments_fire_count(self):
        """When the LLM output contains leaked dedup-metadata (e.g.
        'Bullet 11:', 'KEEP BOTH'), the leak-guard fires: the LLM output is
        rejected, the deterministic fallback runs, and the fire count is
        incremented by 1."""
        bullets = [f"Bullet {i} content here for the test." for i in range(5)]
        # LLM returns bullets WITH leaked metadata ("Bullet 1:", "KEEP BOTH")
        llm_resp = (
            "- Bullet 1: this is the first consolidated bullet here.\n"
            "- KEEP BOTH: the second and third bullets are similar here.\n"
            "- The fourth consolidated bullet with enough content."
        )
        fallback = ["Deterministic merged bullet one.", "Deterministic merged bullet two."]
        deps = _make_deps(llm_response=llm_resp, dedup_result=fallback)
        cap = _CapturingLog()
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, log=cap, **deps)
        # Fallback result is returned (not the LLM output)
        assert out == fallback
        # Fire count incremented
        assert fire == 1
        # WARNING about leaked metadata
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        assert any("leaked" in w and "REJECTING" in w for w in warnings)

    def test_fire_count_passthrough_when_no_leak(self):
        """When no leak is detected, the input fire count is returned unchanged
        (even if it was already > 0 from prior fires)."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        llm_resp = "- Clean consolidated bullet one with content.\n- Clean consolidated bullet two with content."
        deps = _make_deps(llm_response=llm_resp)
        out, fire = consolidate_bullets(
            bullets, leak_guard_fire_count=2, log=_CapturingLog(), **deps
        )
        assert fire == 2  # unchanged

    def test_escalated_warning_at_over_two_fires(self):
        """When the fire count crosses >2 (i.e. this fire makes it 3), the
        escalated WARNING is logged ('leak-guard has now fired 3×...')."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        llm_resp = "- Bullet 1: leaked metadata here.\n- KEEP BOTH: similar bullets."
        deps = _make_deps(llm_response=llm_resp, dedup_result=["Fallback bullet."])
        cap = _CapturingLog()
        # Start at fire_count=2; this leak makes it 3 (>2 → escalate)
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=2, log=cap, **deps)
        assert fire == 3
        warnings = [m for m, l in cap.calls if l == "WARNING"]
        # Both the initial leak WARNING and the escalated WARNING are present
        assert any("leak-guard has now fired" in w and "3" in w for w in warnings)


# ── 8. consolidate_bullets — byte-for-byte / contract ──────────────────────


class TestConsolidateBulletsContract:
    def test_returns_tuple_of_list_and_int(self):
        """The function must return a (List[str], int) tuple — the delegate
        on Summarizer unpacks this to re-assign self._leak_guard_fire_count."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        llm_resp = "- Clean consolidated bullet one with content.\n- Clean consolidated bullet two with content."
        deps = _make_deps(llm_response=llm_resp)
        out, fire = consolidate_bullets(
            bullets, leak_guard_fire_count=0, log=_CapturingLog(), **deps
        )
        assert isinstance(out, list)
        assert all(isinstance(x, str) for x in out)
        assert isinstance(fire, int)

    def test_deterministic_for_fixed_inputs(self):
        """Same inputs → same (out, fire) across calls."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        llm_resp = "- Clean consolidated bullet one with content.\n- Clean consolidated bullet two with content."
        deps = _make_deps(llm_response=llm_resp)
        r1 = consolidate_bullets(bullets, leak_guard_fire_count=0, log=_CapturingLog(), **deps)
        deps2 = _make_deps(llm_response=llm_resp)
        r2 = consolidate_bullets(bullets, leak_guard_fire_count=0, log=_CapturingLog(), **deps2)
        assert r1 == r2

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        bullets = [f"Bullet {i} content here." for i in range(5)]
        llm_resp = "- Clean consolidated bullet one with content.\n- Clean consolidated bullet two with content."
        deps = _make_deps(llm_response=llm_resp)
        out, fire = consolidate_bullets(bullets, leak_guard_fire_count=0, **deps)
        assert isinstance(out, list)
        assert isinstance(fire, int)
