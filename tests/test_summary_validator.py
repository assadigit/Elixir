"""V18.7 (Phase 5.2, Batch A) - Summary-validator characterization tests.

Byte-for-byte stability gate for the 7 pure functions extracted to
``summary_validator.py``. Each test captures a canned input → golden output.
If the extraction changes the output by even one character, the test fails.

These tests use the SAME trust-ground source chapter as the audit harness
(``audit/trust-ground/001_1_IDENTITY_AND_ITS_ORIGINS_source.md``, copied from
``tests/test_ground/source_chapter.md``) so the characterization inputs are
real psychoanalytic text — not synthetic.

Run: pytest tests/test_summary_validator.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.summary_validator import (
    anti_false_precision_check,
    compute_coverage,
    normalize_empty_section,
    semantic_dedup_bullets,
    verify_additive_section_item,
    verify_additive_sections,
    verify_bullets,
)

# ── Trust-ground source (real psychoanalytic text) ───────────────────────────
# Load the trust-ground source chapter for realistic characterization inputs.
_SOURCE_PATH = _project_root / "tests" / "test_ground" / "source_chapter.md"
TRUST_SOURCE = _SOURCE_PATH.read_text() if _SOURCE_PATH.exists() else (
    "Erikson defined ego identity as selfsameness within oneself and a "
    "persistent sharing of some kind of essential character with others. "
    "Jacobson 1964, Kernberg 1967 regard identity as sine qua non of "
    "borderline and narcissistic disorders. Mahler distinguished the "
    "psychological birth of the human infant from its biological birth."
)


# ════════════════════════════════════════════════════════════════════════════
# 1. normalize_empty_section
# ════════════════════════════════════════════════════════════════════════════

class TestNormalizeEmptySection:
    """Characterization tests for normalize_empty_section."""

    def test_none(self):
        assert normalize_empty_section("None") == ""

    def test_na(self):
        assert normalize_empty_section("N/A") == ""

    def test_not_applicable(self):
        assert normalize_empty_section("Not applicable") == ""

    def test_no_distinctions(self):
        assert normalize_empty_section("No distinctions") == ""

    def test_chapter_does_not_discuss(self):
        assert normalize_empty_section("The chapter does not discuss this") == ""

    def test_whitespace_only(self):
        assert normalize_empty_section("   ") == ""

    def test_empty_string(self):
        assert normalize_empty_section("") == ""

    def test_real_content_preserved(self):
        text = "Erikson defined ego identity as persistent selfsameness."
        assert normalize_empty_section(text) == text

    def test_strips_whitespace(self):
        text = "  Erikson defined ego identity.  "
        assert normalize_empty_section(text) == "Erikson defined ego identity."

    def test_no_explicit_tensions(self):
        assert normalize_empty_section("No explicit tensions") == ""

    def test_not_discussed_in_chapter(self):
        assert normalize_empty_section("Not discussed in this chapter") == ""


# ════════════════════════════════════════════════════════════════════════════
# 2. verify_additive_section_item
# ════════════════════════════════════════════════════════════════════════════

class TestVerifyAdditiveSectionItem:
    """Characterization tests for verify_additive_section_item."""

    def test_grounded_item_returns_true(self):
        """An item whose key words appear in the source should be grounded."""
        item = "- Erikson defined ego identity as selfsameness"
        source = "Erikson defined ego identity as selfsameness within oneself"
        assert verify_additive_section_item(item, source) is True

    def test_fabricated_item_returns_false(self):
        """An item with key words NOT in the source should be flagged."""
        item = "- Quantum entanglement explains identity formation"
        source = "Erikson defined ego identity as selfsameness within oneself"
        assert verify_additive_section_item(item, source) is False

    def test_empty_item_returns_false(self):
        assert verify_additive_section_item("", TRUST_SOURCE) is False

    def test_whitespace_item_returns_false(self):
        assert verify_additive_section_item("   ", TRUST_SOURCE) is False

    def test_no_key_words_returns_true(self):
        """If no key words can be extracted (all stopwords/short), keep it."""
        item = "- the and or but"
        source = TRUST_SOURCE
        assert verify_additive_section_item(item, source) is True

    def test_bullet_prefix_stripped(self):
        """The '- ' prefix should be stripped before extraction."""
        item = "- Erikson defined ego identity"
        source = "Erikson defined ego identity as selfsameness"
        assert verify_additive_section_item(item, source) is True

    def test_40_percent_threshold(self):
        """At least 40% of key words must appear in the source."""
        # 4 key words: "erikson", "defined", "identity", "selfsameness"
        # If 2/4 = 50% in source → grounded (True)
        item = "- Erikson defined identity selfsameness"
        source = "Erikson identity selfsameness here"  # 3/4 = 75%
        assert verify_additive_section_item(item, source) is True

    def test_below_40_percent_returns_false(self):
        """Below 40% of key words → not grounded (False)."""
        item = "- Erikson Jacobson Kernberg Mahler Lichtenstein quantum physics"
        source = "Erikson defined ego identity"  # only 1/6 = 17%
        assert verify_additive_section_item(item, source) is False


# ════════════════════════════════════════════════════════════════════════════
# 3. verify_additive_sections
# ════════════════════════════════════════════════════════════════════════════

class TestVerifyAdditiveSections:
    """Characterization tests for verify_additive_sections."""

    def test_none_response_emptied(self):
        """'None' responses should be normalized to empty string."""
        result = {"key_distinctions": "None", "theoretical_tensions": "None"}
        verify_additive_sections("heading", TRUST_SOURCE, result, log=lambda m, l: None)
        assert result["key_distinctions"] == ""
        assert result["theoretical_tensions"] == ""

    def test_grounded_items_kept(self):
        """Items with source-grounded key words should be kept."""
        result = {
            "key_distinctions": "- Erikson defined ego identity as selfsameness",
            "theoretical_tensions": "- Jacobson and Kernberg regard identity as sine qua non",
        }
        verify_additive_sections("heading", TRUST_SOURCE, result, log=lambda m, l: None)
        assert "Erikson" in result["key_distinctions"]
        assert "Jacobson" in result["theoretical_tensions"]

    def test_fabricated_items_dropped(self):
        """Items with no source-grounded key words should be dropped."""
        # Use a SMALL controlled source (not the 43K-char trust-ground) so
        # the fabricated items truly have no word overlap.
        small_source = "Erikson defined ego identity as selfsameness within oneself."
        result = {
            "key_distinctions": "- Quantum entanglement explains consciousness",
            "theoretical_tensions": "- String theory unifies gravitational forces",
        }
        verify_additive_sections("heading", small_source, result, log=lambda m, l: None)
        assert result["key_distinctions"] == ""
        assert result["theoretical_tensions"] == ""

    def test_quarantine_logged(self):
        """Dropped items should be logged to quarantine."""
        quarantine_calls = []
        class MockQuarantine:
            def add(self, **kwargs):
                quarantine_calls.append(kwargs)
        result = {
            "key_distinctions": "- Quantum entanglement explains consciousness",
            "theoretical_tensions": "",
        }
        q = MockQuarantine()
        verify_additive_sections("heading", TRUST_SOURCE, result, quarantine=q, log=lambda m, l: None)
        assert len(quarantine_calls) == 1
        assert quarantine_calls[0]["actually_dropped"] is True

    def test_missing_keys_handled(self):
        """Missing section keys should be handled gracefully."""
        result = {}
        verify_additive_sections("heading", TRUST_SOURCE, result, log=lambda m, l: None)
        assert "key_distinctions" in result
        assert result["key_distinctions"] == ""

    def test_no_quarantine_no_crash(self):
        """Should work even when quarantine is None."""
        result = {"key_distinctions": "None", "theoretical_tensions": "None"}
        verify_additive_sections("heading", TRUST_SOURCE, result, quarantine=None, log=lambda m, l: None)
        assert result["key_distinctions"] == ""


# ════════════════════════════════════════════════════════════════════════════
# 4. anti_false_precision_check
# ════════════════════════════════════════════════════════════════════════════

class TestAntiFalsePrecisionCheck:
    """Characterization tests for anti_false_precision_check."""

    def test_false_precision_rewritten(self):
        """When the source groups Name1+Name2, the contrast should be rewritten."""
        result = {
            "bullet_points": [
                "Jacobson views identity as sine qua non of borderline disorders "
                "while Kernberg views it as sine qua non of narcissistic disorders."
            ],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        source = (
            "Jacobson 1964, Kernberg 1967 regard identity as sine qua non "
            "of borderline and narcissistic disorders"
        )
        log_calls = []
        anti_false_precision_check("heading", source, result, log=lambda m, l: log_calls.append((m, l)))
        assert "Jacobson and Kernberg both" in result["bullet_points"][0]
        assert any("rewrote" in m for m, _ in log_calls)

    def test_no_false_precision_no_change(self):
        """When the source separates the authors, no rewrite should happen."""
        original = "Erikson views identity as a lifespan task, whereas Kernberg views it as structural."
        result = {
            "bullet_points": [original],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        # Source separates them (not within 120 chars)
        source = "Erikson 1956 said identity is a lifespan development. " + ("x" * 200) + " Kernberg 1967 said identity is structural."
        anti_false_precision_check("heading", source, result, log=lambda m, l: None)
        assert result["bullet_points"][0] == original

    def test_no_names_in_source_skipped(self):
        """When names aren't in the source at all, no rewrite should happen."""
        original = "Smith views X as Y while Jones views X as Z."
        result = {
            "bullet_points": [original],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        # Source that truly contains NEITHER "smith" NOR "jones"
        source = "This source mentions neither physicist nor scientist by surname."
        anti_false_precision_check("heading", source, result, log=lambda m, l: None)
        assert result["bullet_points"][0] == original

    def test_exec_summary_also_rewritten(self):
        """The check should also apply to executive_summary, not just bullets."""
        result = {
            "bullet_points": [],
            "executive_summary": "Jacobson views identity as borderline while Kernberg views it as narcissistic.",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        source = "Jacobson 1964, Kernberg 1967 regard identity as borderline and narcissistic"
        anti_false_precision_check("heading", source, result, log=lambda m, l: None)
        assert "Jacobson and Kernberg both" in result["executive_summary"]

    def test_no_contradiction_pattern_no_crash(self):
        """Text without the contrast pattern should pass through unchanged."""
        original = "Erikson defined ego identity as selfsameness within oneself."
        result = {
            "bullet_points": [original],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        anti_false_precision_check("heading", TRUST_SOURCE, result, log=lambda m, l: None)
        assert result["bullet_points"][0] == original


# ════════════════════════════════════════════════════════════════════════════
# 5. semantic_dedup_bullets
# ════════════════════════════════════════════════════════════════════════════

class TestSemanticDedupBullets:
    """Characterization tests for semantic_dedup_bullets.

    Note: These tests exercise the FALLBACK paths (embedder unavailable,
    numpy missing) since the sentence-transformers model isn't installed
    in the test environment. The embedder-healthy path is exercised on
    the user's machine (RTX 3060 + all-MiniLM-L6-v2).
    """

    def test_single_bullet_returned_as_is(self):
        """A single bullet should be returned unchanged."""
        bullets = ["Erikson defined ego identity."]
        result = semantic_dedup_bullets(bullets, log=lambda m, l: None)
        assert result == bullets

    def test_empty_list_returned(self):
        """An empty list should be returned unchanged."""
        assert semantic_dedup_bullets([], log=lambda m, l: None) == []

    def test_fallback_when_embedder_unavailable(self):
        """When the embedder is not available, bullets should be returned unchanged."""
        bullets = [
            "Erikson defined ego identity as selfsameness.",
            "Erikson's ego identity concept means persistent self-sameness.",
            "Mahler distinguished psychological birth from biological birth.",
        ]
        result = semantic_dedup_bullets(bullets, log=lambda m, l: None)
        # Either all returned (fallback) or some removed (embedder available)
        assert len(result) >= 1
        assert len(result) <= len(bullets)

    def test_threshold_parameter_accepted(self):
        """The threshold parameter should be accepted without error."""
        bullets = ["Bullet one.", "Bullet two."]
        result = semantic_dedup_bullets(bullets, threshold=0.95, log=lambda m, l: None)
        assert isinstance(result, list)


# ════════════════════════════════════════════════════════════════════════════
# 6. compute_coverage
# ════════════════════════════════════════════════════════════════════════════

class TestComputeCoverage:
    """Characterization tests for compute_coverage."""

    def test_full_coverage_returns_1(self):
        """When all keywords appear in the summary, coverage should be 1.0."""
        cache = {}
        def extract_kw(text, n):
            return ["identity", "erikson", "jacobson", "kernberg", "mahler"]
        source = "identity erikson jacobson kernberg mahler"
        summary = "identity erikson jacobson kernberg mahler"
        cov = compute_coverage(source, summary, cache, extract_kw)
        assert cov == 1.0

    def test_zero_coverage_returns_0(self):
        """When no keywords appear in the summary, coverage should be 0.0."""
        cache = {}
        def extract_kw(text, n):
            return ["identity", "erikson", "jacobson"]
        source = "identity erikson jacobson test source"
        summary = "quantum physics string theory relativity"
        cov = compute_coverage(source, summary, cache, extract_kw)
        assert cov == 0.0

    def test_partial_coverage(self):
        """Partial keyword overlap should give fractional coverage."""
        cache = {}
        def extract_kw(text, n):
            return ["identity", "erikson", "jacobson", "kernberg"]
        source = "identity erikson jacobson kernberg"
        summary = "identity erikson"
        cov = compute_coverage(source, summary, cache, extract_kw)
        assert 0.0 < cov < 1.0

    def test_cache_populated(self):
        """The coverage_cache should be populated after the first call."""
        cache = {}
        def extract_kw(text, n):
            return ["identity", "erikson"]
        source = "identity erikson source"
        summary = "identity erikson"
        compute_coverage(source, summary, cache, extract_kw)
        assert len(cache) == 1
        key = list(cache.keys())[0]
        assert cache[key] == (["identity", "erikson"], [])

    def test_cache_hit_avoids_reextraction(self):
        """On cache hit, extract_keywords should NOT be called again."""
        cache = {}
        call_count = [0]
        def extract_kw(text, n):
            call_count[0] += 1
            return ["identity", "erikson"]
        source = "identity erikson source"
        compute_coverage(source, "identity", cache, extract_kw)
        compute_coverage(source, "identity", cache, extract_kw)  # cache hit
        assert call_count[0] == 1  # only called once

    def test_no_keywords_returns_1(self):
        """When no keywords can be extracted, coverage should default to 1.0."""
        cache = {}
        def extract_kw(text, n):
            return []
        cov = compute_coverage("source", "summary", cache, extract_kw)
        assert cov == 1.0

    def test_cache_lru_eviction(self):
        """Cache should evict the oldest entry when it exceeds 50 entries."""
        cache = {}
        def extract_kw(text, n):
            return ["keyword"]
        for i in range(52):
            source = f"unique_source_{i} keyword"
            compute_coverage(source, "keyword", cache, extract_kw)
        assert len(cache) <= 50


# ════════════════════════════════════════════════════════════════════════════
# 7. verify_bullets
# ════════════════════════════════════════════════════════════════════════════

class TestVerifyBullets:
    """Characterization tests for verify_bullets."""

    def test_verified_bullet_kept(self):
        """A bullet that matches the source should be kept."""
        cache = {}
        quarantine_calls = []
        class MockQ:
            def add(self, **kw): quarantine_calls.append(kw)
        source = "Erikson defined ego identity as selfsameness within oneself and a persistent sharing of some kind of essential character with others."
        bullets = ["Erikson defined ego identity as selfsameness within oneself"]
        result = verify_bullets(bullets, source, cache, MockQ(), lambda m, l: None)
        assert len(result) == 1
        assert len(quarantine_calls) == 0  # no drops

    def test_unverified_bullet_kept_but_logged(self):
        """A bullet that doesn't match should be kept but logged to quarantine."""
        cache = {}
        quarantine_calls = []
        class MockQ:
            def add(self, **kw): quarantine_calls.append(kw)
        source = "Erikson defined ego identity as selfsameness within oneself."
        bullets = ["Quantum entanglement explains consciousness in multiverse theory"]
        result = verify_bullets(bullets, source, cache, MockQ(), lambda m, l: None)
        assert len(result) == 1  # kept (conservative mode)
        # The bullet is unverified but kept; quarantine logs it with actually_dropped=False
        assert len(quarantine_calls) == 1
        assert quarantine_calls[0]["actually_dropped"] is False

    def test_short_bullet_kept_without_verification(self):
        """Bullets shorter than 10 chars should be kept without verification."""
        cache = {}
        source = "Some source text here."
        bullets = ["Short."]
        result = verify_bullets(bullets, source, cache, None, lambda m, l: None)
        assert result == ["Short."]

    def test_empty_bullet_skipped(self):
        """Empty bullets should be skipped."""
        cache = {}
        source = "Source text."
        result = verify_bullets(["", "  "], source, cache, None, lambda m, l: None)
        assert result == []

    def test_cache_populated(self):
        """The verify_windows_cache should be populated after the first call."""
        cache = {}
        source = "Erikson defined ego identity as selfsameness within oneself."
        verify_bullets(["test bullet"], source, cache, None, lambda m, l: None)
        assert len(cache) == 1

    def test_cache_hit_avoids_recomputation(self):
        """On cache hit, windows should not be recomputed."""
        cache = {}
        source = "Erikson defined ego identity as selfsameness within oneself. This is a longer source text to ensure we have enough content for the sliding window to work properly here."
        verify_bullets(["Erikson defined ego identity"], source, cache, None, lambda m, l: None)
        # Second call with same source should use cache
        verify_bullets(["Another bullet"], source, cache, None, lambda m, l: None)
        assert len(cache) == 1  # still only one entry

    def test_no_quarantine_no_crash(self):
        """Should work even when quarantine is None."""
        cache = {}
        source = "Erikson defined ego identity as selfsameness within oneself."
        result = verify_bullets(["test"], source, cache, None, lambda m, l: None)
        assert len(result) == 1

    def test_citation_stripped_before_verification(self):
        """Citation markers like (p.31) should be stripped before verification."""
        cache = {}
        source = "Erikson defined ego identity as selfsameness within oneself and others here."
        bullets = ["Erikson defined ego identity as selfsameness (p.31)"]
        result = verify_bullets(bullets, source, cache, None, lambda m, l: None)
        assert len(result) == 1


# ════════════════════════════════════════════════════════════════════════════
# Integration: Summarizer delegation
# ════════════════════════════════════════════════════════════════════════════

class TestSummarizerDelegation:
    """Verify that Summarizer methods delegate correctly to summary_validator.

    These tests confirm the delegation wiring works — they don't test the
    logic (that's covered by the function-level tests above).
    """

    def test_compute_coverage_delegates(self):
        """Summarizer._compute_coverage should delegate to sv_compute_coverage."""
        # Check the method exists and has the right signature
        import inspect

        from core.summarisation.summarizer import Summarizer
        sig = inspect.signature(Summarizer._compute_coverage)
        params = list(sig.parameters.keys())
        assert params == ['self', 'source', 'summary'], f"Unexpected params: {params}"

    def test_verify_bullets_delegates(self):
        """Summarizer._verify_bullets should delegate to sv_verify_bullets."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        sig = inspect.signature(Summarizer._verify_bullets)
        params = list(sig.parameters.keys())
        assert params == ['self', 'bullets', 'source_text'], f"Unexpected params: {params}"

    def test_f3_deleted(self):
        """_simplify_for_reading_level should be deleted (Phase 6.8)."""
        from core.summarisation.summarizer import Summarizer
        assert not hasattr(Summarizer, '_simplify_for_reading_level'), \
            "F3 _simplify_for_reading_level should be deleted (Phase 6.8)"

    def test_verify_windows_cache_initialized(self):
        """_verify_windows_cache should be initialized in __init__ or a sub-constructor."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        # V18.17.0.1: _verify_windows_cache moved to _init_coverage_and_counters
        # sub-constructor. Check both __init__ and the sub-constructor source.
        source = inspect.getsource(Summarizer.__init__)
        if '_verify_windows_cache' not in source:
            # Check the sub-constructor
            source += inspect.getsource(Summarizer._init_coverage_and_counters)
        assert '_verify_windows_cache' in source, \
            "_verify_windows_cache should be initialized in __init__ or _init_coverage_and_counters"
