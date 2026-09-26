"""V0.5.4 (Track D): verification-LAYER evolution tests.

Covers the 5 sub-tasks implemented in ``core/summarisation/verification_phase.py``:
  - B2: targeted gap-fill prompt names EACH missing author + their year
  - C3: prompt includes an explicit dedup instruction
  - D4: gap-fill hallucination guard drops fabricated-author bullets
  - D1: ``_apply_deterministic_fixes`` normalizes en-dash year ranges
  - A1: ``_strip_metadata_wrapper`` strips run-metadata before date-check

Content-agnostic (Rule 1): the author names + years in these tests are
TEST FIXTURES (Croewe / Jack / FabricatedAuthor) — they do NOT appear
in runtime code. The production prompt template uses runtime-extracted
``{missing_authors}`` placeholders, not hardcoded names.
"""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md


# ─────────────────────────────────────────────────────────────────────────────
# Shared test scaffolding (mirrors tests/test_v0500_date_extractor.py)
# ─────────────────────────────────────────────────────────────────────────────


class _MockVerifyProvider:
    """A mock LLM provider that returns a caller-supplied raw response."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls: list[dict] = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt, "temperature": temperature})
        return self._raw


class _MockSettings:
    """Minimal Settings stub returning a configured model + ollama arch."""

    def __init__(self, *, model="mock-model", arch="single_local"):
        self._model = model
        self._arch = arch

    def get(self, key, default=None):
        if key == "summarisation.model":
            return self._model
        if key == "summarisation.model_architecture":
            return self._arch
        return default


# ═══════════════════════════════════════════════════════════════════════════
# B2: targeted gap-fill prompt names EACH missing author + their year
# ═══════════════════════════════════════════════════════════════════════════


class TestB2TargetedGapFillPrompt:
    """V0.5.4 (B2): the coverage-targeting prompt names EACH missing
    source author + their year (specific, not generic).

    The AUDIT-V0.5.3-ground-truth found the previous generic "add missing
    authors" prompt produced 16 authors but missed the 7 the LAYER
    flagged. The fix: list each missing author + their year(s) so the
    LLM can produce a grounded bullet per author.
    """

    def test_coverage_prompt_names_missing_authors(self, monkeypatch):
        """The prompt names BOTH missing authors by name + their years."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        # Source has 3 authors: Croewe (1975), Jack (1984), Brown (1970).
        # Summary covers only Brown — Croewe + Jack are missing.
        source = (
            "Croewe (1975) described the early framework. "
            "Jack (1984) extended the synthesis. "
            "Brown (1970) summarized the field."
        )
        summary = "Brown (1970) summarized the field."  # Croewe + Jack missing

        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())

        # The coverage flag should fire.
        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert len(cov) >= 1, "missing source authors should be flagged"

        # B2: the prompt should name BOTH missing authors (Croewe + Jack)
        # AND their years (1975 + 1984). The previous generic prompt only
        # said "add missing authors" without naming them.
        prompt = provider.calls[0]["prompt"]
        assert "Croewe" in prompt, (
            "B2: prompt should name the missing author Croewe by name; "
            "the previous generic prompt did not."
        )
        assert "Jack" in prompt, "B2: prompt should name the missing author Jack by name"
        assert "1975" in prompt, "B2: prompt should include Croewe's year 1975"
        assert "1984" in prompt, "B2: prompt should include Jack's year 1984"

    def test_coverage_prompt_includes_year_for_each_author(self, monkeypatch):
        """The prompt pairs each author with their year (e.g. 'Croewe 1975'),
        not just a comma-separated name list."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = (
            "Smith (1971) wrote the early paper. "
            "Jones (1980) extended it. "
            "Brown (1985) provided the synthesis."
        )
        summary = "Smith (1971) wrote the early paper."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        verify_and_polish_summary(summary, source, settings=_MockSettings())
        prompt = provider.calls[0]["prompt"]
        # The prompt should contain "Author Year" pair (e.g. "Jones 1980")
        # for each missing author — not just a name list.
        assert "Jones 1980" in prompt or "Jones 1980" in prompt.replace("(", "").replace(")", "")
        assert "Brown 1985" in prompt or "Brown 1985" in prompt.replace("(", "").replace(")", "")


# ═══════════════════════════════════════════════════════════════════════════
# C3: prompt includes an explicit dedup instruction
# ═══════════════════════════════════════════════════════════════════════════


class TestC3DedupInstruction:
    """V0.5.4 (C3): the prompt explicitly tells the LLM not to re-cite
    authors already covered.

    The AUDIT-V0.5.3-ground-truth found Kretschmer/Shepherd/Polatin
    cited TWICE — the gap-fill re-cited authors already in the summary.
    The fix: a strong dedup instruction in the coverage-targeting prompt.
    """

    def test_coverage_prompt_includes_dedup_instruction(self, monkeypatch):
        """The prompt contains 'already cited' + 'do NOT add a duplicate'."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = "Smith (1971) described X. Jones (1980) extended it."
        summary = "Smith (1971) described X."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        verify_and_polish_summary(summary, source, settings=_MockSettings())
        prompt = provider.calls[0]["prompt"]
        # C3: the prompt should include a dedup instruction.
        assert "already cited" in prompt.lower(), (
            "C3: prompt should include 'already cited' dedup instruction"
        )
        assert "do NOT add a duplicate" in prompt, (
            "C3: prompt should include the explicit 'do NOT add a duplicate' instruction"
        )

    def test_coverage_prompt_says_do_not_recite(self, monkeypatch):
        """The prompt tells the LLM not to re-cite covered authors."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = "Alpha (1990) wrote it. Beta (1995) extended it."
        summary = "Alpha (1990) wrote it."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        verify_and_polish_summary(summary, source, settings=_MockSettings())
        prompt = provider.calls[0]["prompt"]
        # Case-insensitive: the prompt instructs the LLM "Do NOT re-cite
        # authors already covered" (sentence-case D, but the contract is
        # the dedup instruction is present, regardless of capitalization).
        assert "do not re-cite" in prompt.lower(), (
            "C3: prompt should include 'do NOT re-cite authors already covered'"
        )


# ═══════════════════════════════════════════════════════════════════════════
# D4: gap-fill hallucination guard drops fabricated-author bullets
# ═══════════════════════════════════════════════════════════════════════════


class TestD4GapFillHallucinationGuard:
    """V0.5.4 (D4): after the LLM applies the gap-fill corrections, re-run
    ``extract_citations`` on the polished text, diff the post-author set
    against the pre-author set, and for each newly-added author NOT in
    the source's author set, drop the bullet + flag a gap-fill
    hallucination. Prevents the coverage-targeting from introducing
    hallucinations while fixing coverage.
    """

    def test_gap_fill_hallucination_guard_drops_unsourced_author(self, monkeypatch):
        """The LLM returns a correction adding a bullet with a fabricated
        author 'FabricatedAuthor' (not in source) → the guard flags it +
        drops the bullet."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = "Smith (1971) described the mechanism."
        # Summary already has Smith — the LLM proposes adding a bullet
        # for a FABRICATED author "FabricatedAuthor" (not in source).
        summary = (
            "## Key Takeaways\n\n"
            "- Smith (1971) described the mechanism.\n"
            "- **Conclusions** bullet here.\n"
        )
        llm_response = json.dumps(
            [
                {
                    "original": "- **Conclusions** bullet here.",
                    "corrected": (
                        "- FabricatedAuthor (1984) introduced the false framework.\n"
                        "- **Conclusions** bullet here."
                    ),
                    "reason": "omission",
                }
            ]
        )
        provider = _MockVerifyProvider(llm_response)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())

        # D4: the gap-fill hallucination guard should flag the fabricated author.
        guard = [i for i in issues if i.detector == "verification_gap_fill_hallucination_guard"]
        assert len(guard) == 1, (
            f"D4: fabricated author should be flagged once; got {len(guard)}: "
            f"{[i.detail for i in guard]}"
        )
        assert "FabricatedAuthor" in guard[0].detail, (
            "D4: the flag detail should name the fabricated author"
        )
        # D4: the bullet containing the fabricated author should be DROPPED
        # from the polished output.
        assert "FabricatedAuthor" not in out, (
            "D4: the fabricated author bullet should be dropped from the output"
        )
        # The legitimate Smith bullet should still be present.
        assert "Smith (1971)" in out, "D4: the legitimate bullet should not be dropped"

    def test_gap_fill_guard_no_flag_when_author_in_source(self, monkeypatch):
        """A correction adding a SOURCE author should NOT be flagged —
        the guard only fires on authors NOT in the source set.

        The summary is sized so adding ONE bullet stays within the
        D3-style 85-115% length tolerance (so the polished output is
        actually returned, not rejected by the length guard)."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        # Source has BOTH Smith + Jones; summary covers only Smith.
        source = (
            "Smith (1971) described X. "
            "Jones (1980) extended the synthesis with new theoretical work. "
            "The framework was later applied in clinical settings."
        )
        # Sizable executive-summary body so adding ONE bullet (~40 chars)
        # stays well within the 1.15x length tolerance.
        summary = (
            "## Executive Summary\n\n"
            "This chapter introduces the foundational framework. The early "
            "work by Smith (1971) established the core theoretical model and "
            "its main empirical predictions. Subsequent research extended "
            "the synthesis in several directions, with implications for both "
            "theory and clinical practice.\n\n"
            "## Key Takeaways\n\n"
            "- Smith (1971) described X.\n"
            "- **Conclusions** bullet here.\n"
        )
        # LLM proposes adding a bullet for Jones — Jones IS in the source.
        llm_response = json.dumps(
            [
                {
                    "original": "- **Conclusions** bullet here.",
                    "corrected": (
                        "- Jones (1980) extended the synthesis.\n- **Conclusions** bullet here."
                    ),
                    "reason": "omission",
                }
            ]
        )
        provider = _MockVerifyProvider(llm_response)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())

        # D4: the guard should NOT fire — Jones is a real source author.
        guard = [i for i in issues if i.detector == "verification_gap_fill_hallucination_guard"]
        assert guard == [], f"D4: guard should not fire on a real source author; got {guard}"
        # The Jones bullet should be retained.
        assert "Jones (1980)" in out, "D4: the legitimate gap-fill bullet should be retained"


# ═══════════════════════════════════════════════════════════════════════════
# D1: _apply_deterministic_fixes normalizes en-dash year ranges
# ═══════════════════════════════════════════════════════════════════════════


class TestD1AutoApplyDeterministicFixes:
    """V0.5.4 (D1): ``_apply_deterministic_fixes`` applies rule-based
    corrections for issues where the fix is deterministic + unambiguous.
    Currently: en-dash normalization in year ranges
    (``"1887–1902"`` → ``"1887-1902"``).
    """

    def test_auto_apply_en_dash_normalization(self):
        """A summary with '1887–1902' (en-dash U+2013) → after
        _apply_deterministic_fixes, the text has '1887-1902' (hyphen
        U+002D) + an auto-apply log Issue."""
        from core.summarisation.postchecks.shared import Issue
        from core.summarisation.verification_phase import _apply_deterministic_fixes

        text = "The author lived from 1887–1902 and worked extensively."
        issues: list[Issue] = []
        fixed = _apply_deterministic_fixes(text, issues)

        # D1: en-dash should be normalized to ASCII hyphen.
        assert "1887-1902" in fixed, "D1: en-dash should be normalized to hyphen"
        assert "1887–1902" not in fixed, "D1: en-dash should NOT remain in the fixed text"

        # D1: an auto-apply log Issue should be added (severity="fix").
        auto = [i for i in issues if i.detector == "verification_auto_apply_en_dash"]
        assert len(auto) == 1, f"D1: exactly 1 auto-apply Issue expected; got {len(auto)}"
        assert auto[0].severity == "fix", "D1: auto-apply should be severity='fix'"
        assert "en-dash" in auto[0].detail, "D1: the detail should mention 'en-dash'"
        assert "1" in auto[0].detail, "D1: the detail should report the count"

    def test_auto_apply_preserves_non_year_en_dash(self):
        """En-dashes NOT between two 4-digit years are NOT touched
        (conservative — the fix targets only year-range normalization)."""
        from core.summarisation.verification_phase import _apply_deterministic_fixes

        # "page 5–7" is an en-dash but NOT a year range — must NOT be normalized.
        text = "See page 5–7 for context. The author lived 1887–1902."
        issues: list = []
        fixed = _apply_deterministic_fixes(text, issues)
        # Year range normalized.
        assert "1887-1902" in fixed
        # Non-year en-dash preserved.
        assert "5–7" in fixed, "D1: non-year-range en-dashes should NOT be touched"

    def test_auto_apply_no_op_when_no_en_dash(self):
        """No en-dash in the text → no auto-apply Issue added (no-op)."""
        from core.summarisation.verification_phase import _apply_deterministic_fixes

        text = "The author lived from 1887-1902 (already a hyphen)."
        issues: list = []
        fixed = _apply_deterministic_fixes(text, issues)
        assert fixed == text
        auto = [i for i in issues if "auto_apply" in i.detector]
        assert auto == [], "D1: no auto-apply when there's nothing to fix"

    def test_auto_apply_runs_on_no_model_path(self, monkeypatch):
        """D1 runs even when no model is configured (the en-dash fix is
        deterministic — doesn't need an LLM). The early-return paths
        all go through _apply_deterministic_fixes."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        # No model configured → early return, but en-dash should still
        # be normalized.
        summary = "The author lived 1887–1902."
        source = "The author lived 1887-1902."
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings(model=""))
        assert "1887-1902" in out, "D1: en-dash should be normalized even with no model"
        assert "1887–1902" not in out
        auto = [i for i in issues if i.detector == "verification_auto_apply_en_dash"]
        assert len(auto) == 1, "D1: auto-apply Issue should be added on the no-model path"


# ═══════════════════════════════════════════════════════════════════════════
# A1: metadata wrapper stripped before the date-check
# ═══════════════════════════════════════════════════════════════════════════


class TestA1MetadataWrapperStrip:
    """V0.5.4 (A1): ``_strip_metadata_wrapper`` removes the run-metadata
    wrapper (``<!-- generated-by -->``, ``---\\n*Generated by ...*``,
    ``<!-- COMPLETE -->``) before the date-check, so the wrapper's
    run-timestamp dates are no longer FP-flagged as hallucinations /
    omissions.

    The AUDIT-V0.5.3-ground-truth confirmed 4 of 5 date flags were
    wrapper- or range-component FP — the "2026-09" + "2026-09-26T..."
    strings came from the run-metadata wrapper, NOT the summary body.
    """

    def test_strip_metadata_wrapper_removes_provenance_comment(self):
        """The ``<!-- generated-by ... -->`` HTML comment is removed."""
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        rendered = (
            "# Summary: Chapter\n\n"
            "<!-- generated-by: Elixir v18.20.4.3 | run_id=20260926-211039-8b53ed76 "
            "| started=2026-09-26T21:10:39 | bullets=5 -->\n\n"
            "## Executive Summary\n\nBody text with 1980.\n"
        )
        stripped = _strip_metadata_wrapper(rendered)
        assert "generated-by" not in stripped, "A1: the generated-by comment should be stripped"
        assert "2026-09-26T21:10:39" not in stripped, (
            "A1: the run-timestamp inside the comment should be stripped"
        )
        # Body content preserved.
        assert "Body text with 1980." in stripped
        assert "## Executive Summary" in stripped

    def test_strip_metadata_wrapper_removes_visible_footer(self):
        """The ``---\\n*Generated by ...*`` visible footer block is removed."""
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        rendered = (
            "## Thorough Summary\n\nBody ends here.\n\n"
            "---\n\n"
            "*Generated by Elixir v18.20.4.3 · run 20260926-211039-8b53ed76 "
            "· 2026-09-26T21:10:39 · 5 bullets*\n\n"
            "<!-- COMPLETE run_id=20260926-211039-8b53ed76 -->\n"
        )
        stripped = _strip_metadata_wrapper(rendered)
        assert "Generated by Elixir" not in stripped, "A1: the visible footer should be stripped"
        assert "2026-09-26T21:10:39" not in stripped, "A1: the footer timestamp should be stripped"
        assert "COMPLETE" not in stripped, "A1: the COMPLETE sentinel should be stripped"
        # Body content preserved.
        assert "Body ends here." in stripped

    def test_strip_metadata_wrapper_preserves_body_dates(self):
        """Real summary-body dates (e.g. 1980) are NOT stripped — only
        the wrapper provenance dates are removed."""
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        rendered = (
            "# Summary: Chapter\n\n"
            "<!-- generated-by: Elixir v18.20.4.3 | started=2026-09-26T21:10:39 -->\n\n"
            "## Executive Summary\n\nThe mechanism was described in 1980.\n\n"
            "---\n\n*Generated by Elixir v18.20.4.3 · 2026-09-26T21:10:39 · 5 bullets*\n\n"
            "<!-- COMPLETE run_id=20260926-211039-8b53ed76 -->\n"
        )
        stripped = _strip_metadata_wrapper(rendered)
        # Real body date preserved.
        assert "1980" in stripped, "A1: body date 1980 should be preserved"
        # Wrapper run-metadata dates stripped.
        assert "2026" not in stripped, "A1: wrapper year 2026 should be stripped"
        assert "2026-09-26T21:10:39" not in stripped, "A1: wrapper timestamp should be stripped"

    def test_strip_metadata_wrapper_preserves_book_summary_blockquote(self):
        """The ``> Provider: ... | YYYY-MM-DD`` blockquote (book-level
        summaries) is also stripped (the helper is content-agnostic)."""
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        rendered = (
            "# Book Summary: Title\n\n"
            "> Provider: llamacpp | Language: en | Chapters: 1 | 2026-09-26\n\n"
            "---\n\n"
            "## Chapter 1\n\nBody text with 1980.\n"
        )
        stripped = _strip_metadata_wrapper(rendered)
        assert "Provider: llamacpp" not in stripped, (
            "A1: the book-summary blockquote should be stripped"
        )
        assert "2026-09-26" not in stripped, "A1: the blockquote date should be stripped"
        # Body preserved.
        assert "Body text with 1980." in stripped

    def test_metadata_wrapper_stripped_before_date_check(self, monkeypatch):
        """END-TO-END: a summary with the wrapper → the date-check does
        NOT flag the wrapper dates as hallucinated/omitted.

        This is the core A1 fix — the wrapper's run-timestamp dates were
        being FP-flagged as "hallucinated" (summary date not in source).
        After A1, the date-check operates on the wrapper-stripped body
        and only sees the real summary date (1980, which IS in the source).
        """
        from core.summarisation.verification_phase import verify_and_polish_summary

        summary = (
            "# Summary: Chapter\n\n"
            "<!-- generated-by: Elixir v18.20.4.3 | run_id=20260926-211039-8b53ed76 "
            "| started=2026-09-26T21:10:39 | bullets=5 -->\n\n"
            "## Executive Summary\n\nThe mechanism was described in 1980.\n\n"
            "## Thorough Summary\n\nEnd.\n\n"
            "---\n\n"
            "*Generated by Elixir v18.20.4.3 · run 20260926-211039-8b53ed76 "
            "· 2026-09-26T21:10:39 · 5 bullets*\n\n"
            "<!-- COMPLETE run_id=20260926-211039-8b53ed76 -->\n"
        )
        source = "The mechanism was described in 1980 by Smith."

        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())

        # A1: the date-check should NOT flag any wrapper date (2026 / 2026-09 / etc).
        date_issues = [i for i in issues if i.detector == "verification_date_check"]
        for i in date_issues:
            # The detail/snippet should not contain wrapper dates.
            assert "2026" not in i.detail, (
                f"A1: wrapper date 2026 should NOT be flagged; got: {i.detail}"
            )
            assert "2026" not in i.snippet, (
                f"A1: wrapper date 2026 should NOT be in the snippet; got: {i.snippet}"
            )

    def test_no_wrapper_no_strip(self, monkeypatch):
        """A summary WITHOUT a wrapper still works (the strip is a no-op
        on bare summaries — backward-compatible)."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        summary = "## Executive Summary\n\nThe mechanism was described in 1980.\n"
        source = "The mechanism was described in 1980 by Smith."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        # The body date 1980 is in BOTH summary + source → no FP.
        date_issues = [i for i in issues if i.detector == "verification_date_check"]
        # The body date 1980 should match the source's 1980 — no FP.
        for i in date_issues:
            assert "1980" not in i.detail, (
                f"A1: body date 1980 should match the source — no FP; got: {i.detail}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
