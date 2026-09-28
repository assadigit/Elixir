"""V0.5.19 — the deterministic-criteria continuation rules + the
inline-list paragraph-break join.

The V0.5.18 ch.9 re-run's "Reproduced Diagnostic Criteria" section was
garbled: PDF hard-wraps slice sub-item text across lines/paragraph
breaks, and the old capture glued the wrong pieces together. Four
continuation rules fix the family (all shape-based — Rule 1: the
fixtures below are synthetic mirrors of the wrap shapes, no book
content):

1. a continuation line must start LOWERCASE; an uppercase-start prose
   line after a marker CLOSES the cluster (the old code glued
   discussion prose into the letter's text);
2. a continuation after a SUB-ITEM marker appends to the LAST SUB-ITEM
   (the old code appended it to the parent letter's text);
3. multi-paragraph continuations chain (a lowercase line may continue
   when the previous non-blank line was itself a lowercase continuation);
4. an EMBEDDED sequence-extending ``(roman)`` marker mid-line splits
   the line: the pre-marker tail continues the pending sub-item, the
   post-marker text starts the next sub-item.

Plus the duplicate-tail guard (a PDF double-printed final word) and —
in ``extract_inline_lists`` — the paragraph-break join (a numbered list
item split mid-sentence across a paragraph break; the ch.9 6-ground
list captured 5/6 with item (5) truncated).

Run: pytest tests/test_v0519_criteria_continuation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.preprocessing.deterministic_analyzer import (  # noqa: E402
    _split_embedded_roman_segments,
    extract_inline_lists,
    extract_structured_criteria,
)
from core.summarisation.enumeration import detect_enumerations  # noqa: E402


def _pad(text: str) -> str:
    """Pad a short source past detect_enumerations' 120-char floor."""
    return "Intro prose that is long enough to pass the detector's minimum-length gate. " + text

# ── rule 4: the embedded-marker split helper ────────────────────────────────


class TestEmbeddedRomanSplit:
    def test_tail_plus_next_item(self):
        segs = _split_embedded_roman_segments(
            "superficially warm and charming. (ii) egocentric and inconsiderate", 1
        )
        assert segs == [("tail", 0, "superficially warm and charming."), ("item", 2, "egocentric and inconsiderate")]

    def test_requires_sequence_extension(self):
        """A random ``(iv)`` mention that does NOT extend the sequence
        never splits (no false split on discussion prose)."""
        assert _split_embedded_roman_segments("the fourth item (iv) was dropped later", 1) is None

    def test_multi_marker_chain(self):
        segs = _split_embedded_roman_segments("tail (ii) two (iii) three", 1)
        assert segs == [
            ("tail", 0, "tail"),
            ("item", 2, "two"),
            ("item", 3, "three"),
        ]

    def test_first_item_after_letter_intro(self):
        """expected=1 (no sub-items yet): an embedded (i) splits the
        letter-intro tail from the first sub-item."""
        segs = _split_embedded_roman_segments("by at least two of the following: (i) first thing", 0)
        assert segs == [
            ("tail", 0, "by at least two of the following:"),
            ("item", 1, "first thing"),
        ]


# ── rules 1-3 + the duplicate-tail guard, end-to-end ────────────────────────


_SRC_B = """The manual listed the following criteria for the disorder:

a. Behavior that is overly dramatic, as
indicated by at least three of the following:

(i) self-dramatization, exaggerated expression
(ii) incessant drawing of attention to oneself
(iii) craving for activity and excitement
(iv) overreaction to minor events
(v) irrational outbursts or tantrums

b. Characteristic disturbances in relationships as indicated by at
least two of the following:

(i) perceived by others as shallow and lacking genuineness, even if

superficially warm and charming. (ii) egocentric, self-indulgent, and inconsiderate of others
(iii) vain and demanding
(iv) dependent, helpless, seeking reassurance
(v) prone to manipulative threats or attempts

Clearly, the manual took an advanced step by recognizing the sicker

end of the continuum.
"""


class TestCriteriaContinuation:
    def test_letter_intro_continuation_still_goes_to_letter_text(self):
        """The pre-existing behavior is preserved: a lowercase line after
        a LETTER marker continues the LETTER's text (rule 2's else-arm)."""
        clusters = extract_structured_criteria(_SRC_B)
        item_a = next(it for it in clusters[0]["items"] if it["letter"] == "a")
        assert item_a["text"] == (
            "Behavior that is overly dramatic, as indicated by at least three of the following:"
        )

    def test_subitem_continuation_goes_to_last_subitem(self):
        """Rule 2: the wrapped (i) tail lands in sub-item (i) — NOT in the
        parent letter's text (the old truncation family)."""
        clusters = extract_structured_criteria(_SRC_B)
        item_b = next(it for it in clusters[0]["items"] if it["letter"] == "b")
        subs = dict(item_b["sub_items"])
        assert subs["i"] == (
            "perceived by others as shallow and lacking genuineness, even if "
            "superficially warm and charming."
        )

    def test_embedded_marker_splits_next_subitem(self):
        """Rule 4: the mid-line (ii) becomes its own sub-item."""
        clusters = extract_structured_criteria(_SRC_B)
        item_b = next(it for it in clusters[0]["items"] if it["letter"] == "b")
        subs = dict(item_b["sub_items"])
        assert subs["ii"] == "egocentric, self-indulgent, and inconsiderate of others"

    def test_uppercase_prose_closes_cluster_no_glue(self):
        """Rule 1: the uppercase discussion paragraph is NOT glued into
        the letter's text (the old 'Clearly, ...' family)."""
        clusters = extract_structured_criteria(_SRC_B)
        item_b = next(it for it in clusters[0]["items"] if it["letter"] == "b")
        assert "Clearly" not in item_b["text"]
        assert "advanced step" not in item_b["text"]
        assert item_b["text"].endswith("following:")
        for _m, t in item_b["sub_items"]:
            assert "Clearly" not in t and "advanced step" not in t

    def test_multiparagraph_continuation_chains(self):
        """Rule 3: a continuation may chain across another blank line
        when the previous non-blank line was itself a continuation."""
        src = """a. At least four of the following:

(i) magical thinking, e.g., telepathy (in children and adolescents,
bizarre fantasies or preoccupations)

(ii) ideas of reference
(iii) social isolation, e.g., no close friends

limited to essential everyday tasks

(iv) recurrent illusions, sensing a force not

actually present (e.g., a felt presence), depersonalization, not associated with
panic attacks
"""
        clusters = extract_structured_criteria(src)
        subs = dict(clusters[0]["items"][0]["sub_items"])
        assert "bizarre fantasies or preoccupations" in subs["i"]
        assert subs["iii"].endswith("essential everyday tasks")
        assert subs["iv"].endswith("panic attacks")

    def test_duplicate_tail_line_guarded(self):
        """The PDF double-print family: a repeated final word as its own
        line is NOT appended twice."""
        src = """a. At least one of the following:

(i) odd speech, e.g.,

speech that is digressive, vague, metaphorical

metaphorical
"""
        clusters = extract_structured_criteria(src)
        subs = dict(clusters[0]["items"][0]["sub_items"])
        assert subs["i"].count("metaphorical") == 1
        assert subs["i"].endswith("metaphorical")

    def test_wellformed_list_unchanged(self):
        """A well-formed criteria block (markers on their own lines, no
        wraps) parses exactly as before — no regression."""
        src = """a. Pervasive suspiciousness as indicated by at least three of the following:

(i) expectation of trickery or harm
(ii) hypervigilance

While seemingly adequate, these criteria left much to be desired.
"""
        clusters = extract_structured_criteria(src)
        item_a = clusters[0]["items"][0]
        assert item_a["text"].startswith("Pervasive suspiciousness")
        assert item_a["text"].endswith("following:")
        assert dict(item_a["sub_items"])["i"] == "expectation of trickery or harm"
        # the trailing uppercase paragraph is NOT glued (it closed the cluster)
        assert "seemingly adequate" not in item_a["text"]


# ── the inline-list paragraph-break join ────────────────────────────────────


class TestInlineListParagraphBreakJoin:
    def test_split_list_item_joined(self):
        """The 6-ground mirror: item (5)'s text continues in the next
        paragraph (lowercase) — the join captures all SIX items (the old
        capture carried 5/6 with (5) truncated)."""
        src = (
            "An earlier author (1967) distinguished one type from another on six "
            "grounds: (1) in the first type, lability is seen only in certain "
            "relationships; (2) overinvolvement occurs in selected relationships; "
            "(3) exhibitionism has an agenda; (4) the first type shows inhibition "
            "underneath; moreover, (5) the first type shows competitiveness,\n"
            "\n"
            "while the second type shows less chronic competitiveness overall; and "
            "(6) tendencies are more restricted in the first type.\n"
            "\n"
            "A new paragraph followed the list.\n"
        )
        lists = extract_inline_lists(src, [])
        assert lists, "no inline list found"
        items = lists[0]["items"]
        assert len(items) == 6
        assert "while the second type shows less chronic competitiveness" in items[4]["text"]
        assert "more restricted" in items[5]["text"]
        # the follow-on paragraph is NOT glued in
        for it in items:
            assert "new paragraph" not in it["text"]

    def test_sentence_complete_paragraph_not_joined(self):
        """A list paragraph ending with terminal punctuation does not
        swallow its successor."""
        src = (
            "The grounds were (1) first thing, (2) second thing.\n"
            "\n"
            "meanwhile, later studies showed other findings entirely.\n"
        )
        lists = extract_inline_lists(src, [])
        items = lists[0]["items"]
        assert all("meanwhile" not in it["text"] for it in items)

    def test_uppercase_successor_not_joined(self):
        src = (
            "The grounds were (1) first thing, (2) second thing\n"
            "\n"
            "Meanwhile later studies showed other findings.\n"
        )
        lists = extract_inline_lists(src, [])
        items = lists[0]["items"]
        assert all("Meanwhile" not in it["text"] for it in items)

    def test_non_list_paragraph_not_joined(self):
        """A paragraph WITHOUT numbered markers never joins its successor
        (prose paragraphs are left alone)."""
        src = (
            "A plain prose paragraph with no markers at all in it whatsoever\n"
            "\n"
            "and its lowercase continuation line stays a separate paragraph.\n"
        )
        lists = extract_inline_lists(src, [])
        assert lists == []

    def test_heading_boundary_never_joins(self):
        src = (
            "# Heading One\n\nThe grounds were (1) first thing, (2) second thing\n"
            "\n"
            "# Heading Two\n\nwhile a lowercase line under another heading.\n"
        )
        lists = extract_inline_lists(
            src, [{"line": 1, "title": "Heading One"}, {"line": 5, "title": "Heading Two"}]
        )
        assert lists == [] or all(
            "under another heading" not in it["text"] for lst in lists for it in lst["items"]
        )


# ── V0.5.19.1: the enumeration-guarantee wrapped-continuation join ──────────


class TestEnumerationWrappedContinuationJoin:
    """The V0.5.19.1 patch: ``_paragraphs_joinable`` searched only B's
    FIRST physical line for the next-sequential marker — a PDF hard-wrap
    puts the marker on a LATER line of B, so the join never fired and the
    guarantee bullet carried the list truncated at the paragraph break
    (the ch.9 six-grounds mirror below: 5/6 with item (5) cut)."""

    SIX_GROUNDS = (
        "An earlier author (1967) distinguished one type from another on six "
        "grounds: (1) in the first type, lability appears in certain "
        "relationships; (2) overinvolvement occurs in selected relationships; "
        "(3) exhibitionism has an agenda; (4) the first type shows inhibition "
        "underneath; moreover, (5) the first type shows competitiveness,\n\n"
        "while the second type shows less chronic competitiveness and overall "
        "less\ndifferentiation in behavior toward the two sexes; and (6) "
        "tendencies are more restricted in the first type.\n\n"
        "A closing paragraph of ordinary prose follows the list."
    )

    def test_wrapped_next_marker_joins(self):
        """The (6) marker sits ~2 wrapped lines into B — the full-paragraph
        search finds it, the join fires, the list detects as ONE 6-item
        run with item (5) completed."""
        enums = detect_enumerations(_pad(self.SIX_GROUNDS))
        six = [e for e in enums if e.style == "runin_arabic" and e.count == 6]
        assert six, f"expected a 6-item runin list, got {[e.count for e in enums]}"
        item5 = six[0].items[4].text
        assert "while the second type shows less chronic competitiveness" in item5
        assert six[0].items[5].text.startswith("tendencies are more restricted")

    def test_first_line_marker_still_joins(self):
        """The V0.4.24 behavior (the marker on B's FIRST line) is
        unchanged — the Stern-family shape."""
        src = _pad(
            "The list begins here: (1) alpha; (2) beta; (3) gamma; (4) delta or a\n\n"
            "constitutional continuation, (5) epsilon; (6) zeta.\n\n"
            "A closing paragraph."
        )
        enums = detect_enumerations(src)
        assert [e for e in enums if e.style == "runin_arabic" and e.count == 6]

    def test_non_sequential_wrapped_marker_still_rejected(self):
        """The sequence + pre-length guards keep rejecting a new-topic
        paragraph whose wrapped lines merely contain a stray marker."""
        src = _pad(
            "The list begins here: (1) alpha; (2) beta; (3) gamma; (4) delta or a\n\n"
            "new topic paragraph that goes on about entirely different matters "
            "and\nafter many wrapped lines of prose eventually mentions a stray "
            "(9) marker\nin passing before concluding.\n\n"
            "A closing paragraph."
        )
        enums = detect_enumerations(src)
        assert not [e for e in enums if e.style == "runin_arabic" and e.count == 5]
