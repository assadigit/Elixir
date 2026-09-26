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
