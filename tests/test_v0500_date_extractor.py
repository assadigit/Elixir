"""V0.5.0/V0.5.1: characterization tests for the deterministic date extractor
+ the verification LAYER's coverage-targeting.

Covers the major date-format classes from the user's exhaustive list
(Parts 1-8): BC/AD/BCE/CE, plain years, approximate, ranges, centuries,
decades, millennia, full dates, scientific notation, calendar eras.
+ V0.5.1: page-reference false-positive fix + coverage-targeting.
"""

from __future__ import annotations

from core.preprocessing.date_extractor import compare_dates, extract_dates


class _MockVerifyProvider:
    """A mock LLM provider that returns a caller-supplied raw response."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls = []

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


class TestDateExtractorPart1BCADBCECE:
    """Part 1: BC, AD, BCE, CE era designations."""

    def test_bc_suffix(self):
        dms = extract_dates("The battle of 500 BC was decisive.")
        assert len(dms) == 1
        assert dms[0].year == 500 and dms[0].era == "bce"

    def test_bc_with_periods(self):
        dms = extract_dates("500 B.C. and 500 BCE are the same year.")
        assert len(dms) >= 2
        assert all(d.year == 500 and d.era == "bce" for d in dms[:2])

    def test_ad_prefix(self):
        dms = extract_dates("AD 500 marked the start.")
        assert len(dms) == 1
        assert dms[0].year == 500 and dms[0].era == "ce"

    def test_ad_suffix(self):
        dms = extract_dates("The year 500 AD was significant.")
        assert len(dms) == 1
        assert dms[0].year == 500 and dms[0].era == "ce"

    def test_ce_suffix(self):
        dms = extract_dates("500 CE is the common era.")
        assert len(dms) == 1
        assert dms[0].year == 500 and dms[0].era == "ce"


class TestDateExtractorPart2PlainYears:
    """Part 2: plain numerical years."""

    def test_plain_year(self):
        dms = extract_dates("The book was published in 1891.")
        assert len(dms) == 1
        assert dms[0].year == 1891 and dms[0].era == "ce"

    def test_multiple_plain_years(self):
        dms = extract_dates("Events in 1914 and 1939 shaped the century.")
        years = [d.year for d in dms if d.format_type == "plain_year"]
        assert 1914 in years and 1939 in years

    def test_no_false_positive_on_non_year_numbers(self):
        """3-digit numbers should not be matched as plain years."""
        dms = extract_dates("There were 500 soldiers and 42 cannons.")
        # 500 might be matched as era_suffix if no era — check it's not plain_year
        plain = [d for d in dms if d.format_type == "plain_year"]
        assert plain == [], "3-digit numbers without era should not be plain years"


class TestDateExtractorPart3Approximate:
    """Part 3: approximate, uncertain, inferred dates."""

    def test_circa(self):
        dms = extract_dates("The manuscript dates to c. 1450.")
        assert len(dms) == 1
        assert dms[0].year == 1450 and dms[0].is_approximate

    def test_ca(self):
        dms = extract_dates("ca. 1891")
        assert dms[0].year == 1891 and dms[0].is_approximate

    def test_tilde(self):
        dms = extract_dates("~1891")
        assert dms[0].year == 1891 and dms[0].is_approximate

    def test_uncertain_question_mark(self):
        dms = extract_dates("The date is 1891?")
        assert dms[0].year == 1891 and dms[0].is_uncertain

    # FIX-P3-6: the next 4 tests cover the remaining _APPROX_PREFIX variants
    # (about/around/approx./approximately) the V0.5.0 audit flagged as
    # untested. Generic dates, no book/author content (Rule 1).

    def test_about(self):
        dms = extract_dates("about 1891")
        assert len(dms) == 1
        assert dms[0].year == 1891 and dms[0].is_approximate
        assert dms[0].format_type == "circa"

    def test_around(self):
        dms = extract_dates("around 1891")
        assert len(dms) == 1
        assert dms[0].year == 1891 and dms[0].is_approximate

    def test_approx_period(self):
        dms = extract_dates("approx. 1891")
        assert len(dms) == 1
        assert dms[0].year == 1891 and dms[0].is_approximate

    def test_approximately(self):
        dms = extract_dates("approximately 1891")
        assert len(dms) == 1
        assert dms[0].year == 1891 and dms[0].is_approximate


class TestDateExtractorPart4Ranges:
    """Part 4: date ranges and intervals."""

    def test_dash_range(self):
        dms = extract_dates("The war lasted 1914–1918.")
        assert len(dms) == 1
        assert dms[0].year == 1914 and dms[0].year_end == 1918

    def test_hyphen_range(self):
        dms = extract_dates("1891-1895")
        assert dms[0].year == 1891 and dms[0].year_end == 1895

    def test_short_end_range(self):
        dms = extract_dates("1891-95")
        assert dms[0].year == 1891 and dms[0].year_end == 1895

    def test_slash_range(self):
        dms = extract_dates("The academic year 1891/92.")
        assert dms[0].year == 1891 and dms[0].year_end == 1892

    def test_from_to(self):
        dms = extract_dates("from 1891 to 1895")
        assert dms[0].year == 1891 and dms[0].year_end == 1895


class TestDateExtractorPart5CenturiesDecades:
    """Part 5: centuries, decades, millennia."""

    def test_ordinal_century(self):
        dms = extract_dates("the 19th century")
        assert dms[0].format_type == "century" and dms[0].year == 19

    def test_word_century(self):
        dms = extract_dates("the nineteenth century")
        assert dms[0].format_type == "century_word" and dms[0].year == 19

    def test_century_bc(self):
        dms = extract_dates("the 5th century BC")
        assert dms[0].year == 5 and dms[0].era == "bce"

    def test_decade(self):
        dms = extract_dates("the 1890s")
        assert dms[0].format_type == "decade" and dms[0].year == 1890

    def test_millennium(self):
        dms = extract_dates("the 2nd millennium CE")
        assert dms[0].format_type == "millennium" and dms[0].year == 2

    # FIX-P3-6: the _DECADE_SHORT pattern (e.g. "'90s") was untested.
    # Note: the regex `\b'(\d)0s\b` requires the apostrophe to be
    # immediately preceded by a word character (the `\b` boundary won't
    # match between a space and the apostrophe), so "the '90s" with a
    # space does NOT match — only "the'90s" (no space) does. The test
    # uses the no-space form to exercise the regex as designed.

    def test_decade_short(self):
        dms = extract_dates("the'90s")
        assert len(dms) == 1
        assert dms[0].format_type == "decade_short"
        assert dms[0].year == 9


class TestDateExtractorPart6FullDates:
    """Part 6: full dates (day, month, year)."""

    def test_dmy(self):
        dms = extract_dates("10 October 1891")
        assert dms[0].year == 1891 and dms[0].format_type == "full_date_dmy"

    def test_mdy(self):
        dms = extract_dates("October 10, 1891")
        assert dms[0].year == 1891 and dms[0].format_type == "full_date_mdy"

    def test_iso(self):
        dms = extract_dates("1891-10-10")
        assert dms[0].year == 1891 and dms[0].format_type == "iso_date"

    def test_numeric_dmy(self):
        dms = extract_dates("10/10/1891")
        assert dms[0].year == 1891

    # FIX-P3-6: the _NUMERIC_DATE_YMD pattern (e.g. "2020/12/25") was
    # untested. Uses a `/` (or `.`) separator so the more-specific
    # _ISO_DATE pattern (which requires `-`) doesn't claim it first.

    def test_numeric_ymd(self):
        dms = extract_dates("2020/12/25")
        assert len(dms) == 1
        assert dms[0].format_type == "numeric_date_ymd"
        assert dms[0].year == 2020


class TestDateExtractorPart7CalendarEras:
    """Part 7: historical calendar eras."""

    def test_ah(self):
        dms = extract_dates("1447 AH")
        assert dms[0].year == 1447 and dms[0].era == "ah"

    def test_auc(self):
        dms = extract_dates("754 AUC")
        assert dms[0].year == 754 and dms[0].era == "auc"

    def test_sh(self):
        dms = extract_dates("1405 SH")
        assert dms[0].year == 1405 and dms[0].era == "sh"

    def test_be(self):
        dms = extract_dates("2569 BE")
        assert dms[0].year == 2569 and dms[0].era == "be"

    # FIX-P3-6: the 4 calendar-era patterns below (AM/Saka/VS/Vikram
    # Samvat) were untested. All share the _CALENDAR_ERA regex.

    def test_am(self):
        dms = extract_dates("1447 AM")
        assert len(dms) == 1
        assert dms[0].year == 1447 and dms[0].era == "am"
        assert dms[0].format_type == "calendar_era"

    def test_saka(self):
        dms = extract_dates("1447 Saka")
        assert len(dms) == 1
        assert dms[0].year == 1447 and dms[0].era == "saka"

    def test_vs(self):
        dms = extract_dates("1447 VS")
        assert len(dms) == 1
        assert dms[0].year == 1447 and dms[0].era == "vs"

    def test_vikram_samvat(self):
        dms = extract_dates("1447 Vikram Samvat")
        assert len(dms) == 1
        assert dms[0].year == 1447 and dms[0].era == "vs"  # normalizes to vs


class TestDateExtractorPart8Scientific:
    """Part 8: scientific and archaeological date notation."""

    def test_bp(self):
        dms = extract_dates("10,000 BP")
        assert dms[0].year == 10000 and dms[0].era == "bp"

    def test_cal_bp(self):
        dms = extract_dates("5000 cal BP")
        assert dms[0].year == 5000 and dms[0].era == "bp"

    def test_ma(self):
        dms = extract_dates("65 Ma")
        assert dms[0].year == 65 and dms[0].era == "ma"

    # FIX-P3-6: the 3 patterns below (Mya / ka BP / yr BP) were untested.

    def test_mya(self):
        dms = extract_dates("65 Mya")
        assert len(dms) == 1
        assert dms[0].year == 65 and dms[0].era == "ma"  # Mya normalizes to ma

    def test_ka_bp(self):
        dms = extract_dates("5000 ka BP")
        assert len(dms) == 1
        assert dms[0].year == 5000 and dms[0].era == "bp"
        assert dms[0].format_type == "scientific_bp"

    def test_yr_bp(self):
        dms = extract_dates("5000 yr BP")
        assert len(dms) == 1
        assert dms[0].year == 5000 and dms[0].era == "bp"
        assert dms[0].format_type == "yr_bp"


class TestCompareDates:
    """The compare_dates function for the verification phase."""

    def test_matched_dates(self):
        summary = extract_dates("Smith (1891) described the theory.")
        source = extract_dates("Smith (1891) described the theory in detail.")
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] == 0
        assert result["matched_count"] >= 1

    def test_hallucinated_date_detected(self):
        """A summary date NOT in the source is flagged as a potential hallucination."""
        summary = extract_dates("Smith (1979) described the theory.")  # 1979 not in source
        source = extract_dates("Smith (1971) described the theory.")  # 1971 in source
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] >= 1
        assert any(d.year == 1979 for d in result["hallucinated"])

    def test_omitted_date_detected(self):
        """A source date NOT in the summary is flagged as a potential omission."""
        summary = extract_dates("Smith described the theory.")  # no year
        source = extract_dates("Smith (1971) described the theory.")  # 1971 in source
        result = compare_dates(summary, source)
        assert result["omitted_count"] >= 1
        assert any(d.year == 1971 for d in result["omitted"])

    def test_approximate_matches_exact(self):
        """A circa date (c. 1891) should match an exact date (1891) in the source."""
        summary = extract_dates("c. 1891")
        source = extract_dates("in 1891")
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] == 0  # c.1891 matches 1891


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.1: page-reference false-positive fix + coverage-targeting
# ═══════════════════════════════════════════════════════════════════════════


class TestV051PageRefFalsePositiveFix:
    """V0.5.1: the ~NNN page-reference false positive is fixed."""

    def test_page_ref_not_matched(self):
        """~137 in a (p. ~137) page-ref context is NOT matched as circa."""
        dms = extract_dates("The chapter discusses PPD (p. ~137) in detail.")
        approx = [d for d in dms if d.is_approximate]
        assert approx == [], "page-ref ~137 should NOT be matched as circa"

    def test_multiple_page_refs_not_matched(self):
        """Multiple (p. ~NNN) references are all excluded."""
        text = (
            "- PPD vs. phobic (p. ~137)\n"
            "- PPD vs. compulsive (p. ~141)\n"
            "- PPD vs. narcissistic (p. ~146)\n"
            "- PPD vs. antisocial (p. ~150)\n"
            "- PPD vs. schizophrenia (p. ~155)"
        )
        dms = extract_dates(text)
        approx = [d for d in dms if d.is_approximate]
        assert approx == [], "no page-ref ~NNN should be matched as circa"

    def test_real_circa_still_matched(self):
        """~1891 in a non-page-ref context IS still matched (the fix
        doesn't break real circa-date detection)."""
        dms = extract_dates("The manuscript dates to ~1891.")
        approx = [d for d in dms if d.is_approximate]
        assert len(approx) == 1
        assert approx[0].year == 1891


class TestV051CoverageTargeting:
    """V0.5.1: the verification LAYER extracts source authors, checks
    which are missing, adds them to the LLM prompt (the 10/10 coverage
    objective)."""

    def test_coverage_check_finds_missing_authors(self, monkeypatch):
        """When source has authors NOT in the summary, a verification_coverage
        flag is produced + the missing authors are added to the prompt."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = (
            "Smith (1971) described the mechanism. "
            "Jones (1980) extended the framework. "
            "Brown (1985) provided the synthesis."
        )
        summary = "Smith (1971) described the mechanism."  # Jones + Brown missing

        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        # The coverage check should flag Jones + Brown as missing.
        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert len(cov) >= 1, "missing source authors should be flagged"
        assert "Jones" in cov[0].detail or "Brown" in cov[0].detail
        # The prompt should contain the coverage note.
        assert "ADDITIONAL COVERAGE CHECK" in provider.calls[0]["prompt"]
        assert "Jones" in provider.calls[0]["prompt"]

    def test_coverage_check_no_missing_authors(self, monkeypatch):
        """When all source authors ARE in the summary, no coverage flag."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = "Smith (1971) described the mechanism."
        summary = "Smith (1971) described the mechanism."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert cov == [], "no coverage flag when all authors are covered"


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.4 (Track A): date-check FP elimination — en-dash normalization,
# range-component compare logic, + run-metadata wrapper strip.
#
# The V0.5.3 ground-truth audit confirmed the date-check produced 4 false
# "hallucination" flags + 1 false "omission" flag per run (80% FP rate).
# Three FP classes are eliminated by Track A:
#   - A1 (run-metadata): the date-check scanned the markdown wrapper
#     (<!-- generated-by --> + > Provider | 2026-09-26 + *Generated by
#     Elixir ... · 2026-09-26T...*) and flagged run-timestamps as
#     hallucinations. Fix: ``_strip_metadata_wrapper`` strips the wrapper
#     before the date-check.
#   - A2 (range-component): the date-check extracts "1887" + "1902"
#     separately from the range "1887-1902", then flags them as "not
#     found in source" even though the source has the RANGE. Fix:
#     ``_year_covered_by_range`` + ``compare_dates`` updates suppress
#     the flag when a year is covered by a range on the other side.
#   - A3 (en-dash mismatch): the summary uses "1887–1902" (en-dash
#     U+2013) but the source range uses "1887-1902" (hyphen U+002D).
#     Fix: ``_DASH_TRANSLATE`` normalizes en-dash / em-dash / minus-sign
#     to ASCII hyphen before the regex pass (offsets preserved by 1:1
#     codepoint substitution).
# All tests use generic date strings (Rule 1 ✓ — no book/author content).
# ═══════════════════════════════════════════════════════════════════════════


class TestV054TrackAEnDashNormalization:
    """V0.5.4 Track A — A3 fix: en-dash / em-dash / minus-sign in year
    ranges are normalized to ASCII hyphen before the regex pass."""

    def test_en_dash_range_captured(self):
        """A range with an en-dash (U+2013) separator is captured as a range.

        Reproduces the V0.5.3 audit's en-dash mismatch FP class — the
        summary used "1887–1902" (en-dash, common in publisher
        copy-edit pipelines) but the date-check only reliably matched the
        ASCII-hyphen source form.
        """
        dms = extract_dates("Freud (1887–1902) wrote about paranoia.")
        ranges = [d for d in dms if d.format_type == "range_dash"]
        assert len(ranges) == 1
        assert ranges[0].year == 1887 and ranges[0].year_end == 1902

    def test_em_dash_range_captured(self):
        """A range with an em-dash (U+2014) separator is captured as a range."""
        dms = extract_dates("Freud (1887—1902) wrote about paranoia.")
        ranges = [d for d in dms if d.format_type == "range_dash"]
        assert len(ranges) == 1
        assert ranges[0].year == 1887 and ranges[0].year_end == 1902

    def test_minus_sign_range_captured(self):
        """A range with a minus-sign (U+2212) separator is captured as a range.

        Bonus coverage (not in the V0.5.3 audit, but the normalization
        handles it) — minus-sign U+2212 is used by some academic
        typesetting + NLP postprocessors.
        """
        dms = extract_dates("Freud (1887−1902) wrote about paranoia.")  # U+2212
        ranges = [d for d in dms if d.format_type == "range_dash"]
        assert len(ranges) == 1
        assert ranges[0].year == 1887 and ranges[0].year_end == 1902


class TestV054TrackARangeComponentCompare:
    """V0.5.4 Track A — A2 fix: range-component compare logic.

    A summary that references the range endpoints (e.g. "1887" + "1902"
    as plain years) is NOT flagged as hallucinated when the source has
    the contiguous range "1887-1902" (and vice versa for omissions).
    """

    def test_range_component_not_flagged_as_hallucination(self):
        """Summary has plain years 1887 + 1902; source has range 1887-1902.

        Pre-A2: 2 hallucinated (the 1887 + 1902 plain years weren't in
        the source's normalized set — only the range was).
        Post-A2: 0 hallucinated (both endpoints fall within the source
        range).
        """
        summary = extract_dates("Freud 1887 and 1902 are key years.")
        source = extract_dates("Freud (1887-1902) was influential.")
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] == 0, (
            "summary plain years covered by a source range must NOT be flagged as hallucinations"
        )

    def test_range_component_not_flagged_as_omission(self):
        """Source has plain years 1887 + 1902; summary has range 1887-1902.

        Pre-A2: 2 omitted (the source's plain years weren't in the
        summary's normalized set — only the range was).
        Post-A2: 0 omitted (both endpoints fall within the summary range).
        """
        summary = extract_dates("Freud (1887-1902) was influential.")
        source = extract_dates("Freud 1887 and 1902 are key years.")
        result = compare_dates(summary, source)
        assert result["omitted_count"] == 0, (
            "source plain years covered by a summary range must NOT be flagged as omissions"
        )

    def test_real_hallucination_still_detected(self):
        """A summary year NOT in the source AND NOT covered by a source
        range is still flagged (the A2 fix doesn't suppress real
        hallucinations)."""
        summary = extract_dates("Smith (1979) described the theory.")  # 1979
        source = extract_dates("Smith (1971) described the theory.")  # 1971 only
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] >= 1
        assert any(d.year == 1979 for d in result["hallucinated"])


class TestV054TrackAMetadataWrapperStrip:
    """V0.5.4 Track A — A1 fix: the run-metadata markdown wrapper is
    stripped from the rendered summary BEFORE the date-check, so the
    wrapper's run-timestamps are no longer FP-flagged as hallucinations.
    """

    # A realistic rendered-md wrapper (V0.5.x format) around a small body
    # containing only content dates. Rule 1 ✓ — no hardcoded book/author
    # strings; uses the generic markdown markers `<!--`, `>`, `*`, `##`,
    # `---` that the real wrapper uses.
    _WRAPPED_SUMMARY = (
        "<!-- generated-by: Elixir v0.5.4 | run_id=20260926-211039-8b53ed76"
        " | started=2026-09-26T21:14:00 | bullets=4 -->\n\n"
        "# Book Summary: Sample Book\n\n"
        "> Provider: ollama | Language: en | Chapters: 1 | 2026-09-26\n\n"
        "---\n\n"
        "## Chapter-by-Chapter Executive Summaries\n\n"
        "### 1. Sample Chapter\n\n"
        "The author Freud (1887-1902) was influential in the 19th century. "
        "Key events happened in 1914 and 1939.\n\n"
        "---\n\n"
        "*Generated by Elixir v0.5.4 · run 20260926-211039-8b53ed76"
        " · 2026-09-26T21:14:00 · 4 bullets*"
    )

    def test_metadata_wrapper_stripped(self):
        """The wrapper's run-metadata dates (the ``2026-09-26`` blockquote
        date + the ``2026-09-26T21:14:00`` HTML-comment + footer
        timestamps) are NOT extracted from the body after the wrapper is
        stripped. Only the body's content dates (1887-1902 range + 1914
        + 1939 plain years + 19th century) are extracted.
        """
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        body = _strip_metadata_wrapper(self._WRAPPED_SUMMARY)
        # Sanity: the wrapper components are gone from the body.
        assert "generated-by" not in body, "HTML comment must be stripped"
        assert "Provider:" not in body, "blockquote must be stripped"
        assert "Generated by" not in body, "italic footer must be stripped"
        assert "2026-09-26" not in body, "run-metadata dates must be stripped"

        # The body content dates ARE extracted.
        dms = extract_dates(body)
        years = [d.year for d in dms if d.year is not None]
        # No 2026 (or 2027) year should be present (run-metadata is gone).
        assert not any(y >= 2026 for y in years), (
            f"no run-metadata dates should be extracted from stripped body; got years: {years}"
        )
        # The content dates ARE present (the 1887-1902 range, the 1914
        # + 1939 plain years, the 19th century).
        assert any(
            d.format_type == "range_dash" and d.year == 1887 and d.year_end == 1902 for d in dms
        ), "body range 1887-1902 must be extracted"
        assert 1914 in years and 1939 in years, "body plain years must be extracted"

    def test_wrapper_strip_failopen_on_non_conforming_input(self):
        """A plain-text summary without the wrapper markers is returned
        unchanged (the helper fails open — never breaks the date-check)."""
        from core.summarisation.verification_phase import _strip_metadata_wrapper

        plain_summary = "Smith (1971) described the mechanism in 19th century work."
        body = _strip_metadata_wrapper(plain_summary)
        # No `## ` heading → returns the input unchanged.
        assert body == plain_summary

    def test_no_hallucination_flag_for_run_metadata_dates(self, monkeypatch):
        """End-to-end: a summary with the wrapper (containing run-metadata
        dates 2026-09-26 / 2026-09-26T21:14:00) does NOT produce a
        ``verification_date_check`` flag for those dates when verified
        against a source with only the body content dates."""
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = "Freud (1887-1902) was influential in the 19th century."
        # Use the wrapped summary (with run-metadata dates 2026-09-26 etc.).
        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(
            self._WRAPPED_SUMMARY, source, settings=_MockSettings()
        )
        date_flags = [i for i in issues if i.detector == "verification_date_check"]
        # No date flag for 2026 (run-metadata gone via wrapper-strip).
        run_meta_flags = [
            i for i in date_flags if "2026" in (i.snippet or "") or "2026" in (i.detail or "")
        ]
        assert run_meta_flags == [], (
            "wrapper run-metadata dates (2026-...) must NOT produce verification_date_check flags"
        )
