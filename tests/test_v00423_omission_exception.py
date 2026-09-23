"""V0.4.23 (audit V0.4.22, backlog #5): statements-about-omissions
exception in the false-"missing"-claim heuristic.

The V0.4.22 run flagged "omitted psychotic-like episodes…" as a false
missing claim because the concept words appear in the source — but they
appear INSIDE the source's own "noteworthy omission" statement, which
the summary faithfully reports. Genuine false-missing claims (concept
present with NO omission context) must still be flagged.
"""

from __future__ import annotations

from core.summarisation.postchecks.coherence import (
    _source_asserts_omission,
    detect_inconsistency,
)


class TestSourceAssertsOmission:
    def test_noteworthy_omission_sentence_detected(self):
        source = (
            "The reviewer's discussion carries the noteworthy omission of "
            "psychotic-like episodes (Cited 1989, p. 239), which earlier "
            "descriptions had included."
        )
        words = ["psychotic", "episodes"]
        assert _source_asserts_omission(source, words)

    def test_plain_presence_is_not_an_omission_claim(self):
        source = "The chapter discusses psychotic episodes and their differential diagnosis."
        words = ["psychotic", "episodes"]
        assert not _source_asserts_omission(source, words)

    def test_marker_families(self):
        for marker in (
            "the syndrome lacks stability",
            "fails to mention the follow-up studies",
            "no mention of outcome data",
            "the issue is conspicuously absent",
            "treatment response is excluded",
        ):
            assert _source_asserts_omission(
                f"Prose. {marker} in the review of psychotic episodes.",
                ["psychotic", "episodes"],
            ), marker


class TestDetectInconsistencyException:
    def test_summary_reporting_source_omission_not_flagged(self):
        source = (
            "The account carries the noteworthy omission of psychotic-like "
            "episodes (Cited 1989, p. 239), a point the reviewer emphasizes."
        )
        summary = (
            "The chapter notes the field's omitted psychotic-like episodes "
            "as a shortcoming of the earlier account."
        )
        _text, issues = detect_inconsistency(summary, source, "thorough")
        assert not [i for i in issues if "false 'missing' claim" in i.detail]

    def test_genuine_false_missing_still_flagged(self):
        source = "The chapter discusses feedback loops and their role in adaptation."
        summary = "The chapter does not discuss the role of feedback loops."
        _text, issues = detect_inconsistency(summary, source, "exec")
        flagged = [i for i in issues if "false 'missing' claim" in i.detail]
        assert flagged, "the genuine false-missing vector must still be flagged"

    def test_no_source_text_no_exception(self):
        summary = "The chapter does not discuss the role of feedback loops."
        _text, issues = detect_inconsistency(summary, "", "exec")
        assert issues == [] or not [i for i in issues if "false 'missing' claim" in i.detail]
