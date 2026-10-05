"""V18.6 (Phase 4, Task 4.3) - Post-processing characterization tests.

Byte-for-byte stability gate for the 6 pure functions extracted to
post_processing.py. Each test captures a canned input -> golden output
pair. If the extraction changes the output by even one character, the
test fails.

Run: pytest tests/test_post_processing.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.post_processing import (
    classify_bullets,
    normalize_bullets,
    strip_markup_tags,
    strip_narrative_from_thorough,
    strip_thinking,
    truncate_to_sentences,
)

# == 1. strip_thinking ==


class TestStripThinking:
    def test_strips_thinking_block(self):
        """Thinking blocks are removed, content kept."""
        text = "<think>The user wants a summary.</think>Here is the summary."
        result = strip_thinking(text)
        assert "Here is the summary." in result
        assert "The user wants" not in result

    def test_no_thinking_block_unchanged(self):
        """Text without thinking blocks passes through unchanged."""
        text = "This is a clean summary with no thinking."
        assert strip_thinking(text) == text

    def test_empty_string(self):
        """Empty input returns empty."""
        assert strip_thinking("") == ""


# == 2. strip_markup_tags ==


class TestStripMarkupTags:
    def test_strips_xml_tags(self):
        """XML/markup tags are removed."""
        text = "<reference>page 5</reference>The main concept is identity."
        result = strip_markup_tags(text)
        assert "<reference>" not in result
        assert "The main concept is identity." in result

    def test_no_tags_unchanged(self):
        """Plain text passes through unchanged."""
        text = "Erikson defined ego identity in 1956."
        assert strip_markup_tags(text) == text


# == 3. strip_narrative_from_thorough ==


class TestStripNarrativeFromThorough:
    def test_strips_narrative_sentences(self):
        """Narrative/story sentences are removed from thorough summary."""
        text = (
            "The chapter discusses identity formation. "
            "Ryan went to a party and met Thad. "
            "Erikson defined ego identity as self-sameness."
        )
        result = strip_narrative_from_thorough(text)
        assert "Erikson defined ego identity" in result
        assert len(result) <= len(text)

    def test_no_narrative_unchanged(self):
        """Non-narrative text passes through largely unchanged."""
        text = "The author defines identity as a lifelong developmental process."
        result = strip_narrative_from_thorough(text)
        assert "defines identity" in result


# == 4. truncate_to_sentences ==


class TestTruncateToSentences:
    def test_truncates_to_max_sentences(self):
        """Text is truncated to at most max_sentences."""
        text = "First sentence here. Second sentence here. Third sentence here."
        result = truncate_to_sentences(text, max_sentences=2, max_words=35)
        assert "First sentence" in result
        assert "Third sentence" not in result

    def test_short_text_unchanged(self):
        """Text shorter than the limit passes through unchanged."""
        text = "One sentence only."
        result = truncate_to_sentences(text, max_sentences=2, max_words=35)
        assert "One sentence only" in result

    def test_empty_string(self):
        """Empty input returns empty."""
        assert truncate_to_sentences("", max_sentences=2) == ""


# == 5. normalize_bullets (extracted verbatim from Summarizer V16.0.2) ==


class TestNormalizeBullets:
    def test_strips_leading_bullet_markers(self):
        """Leading -, *, numbered prefixes are stripped (one pass)."""
        bullets = [
            "- Erikson defined identity.",
            "3. Kernberg proposed three steps.",
            "• Winnicott described the true self.",
        ]
        result = normalize_bullets(bullets)
        assert all(not b.startswith("-") for b in result)
        assert all(not b.startswith("•") for b in result)
        assert all(not b[0].isdigit() for b in result)
        assert len(result) == 3

    def test_strips_key_quote_prefix(self):
        """'KEY QUOTE:' prefix is stripped."""
        bullets = ["KEY QUOTE: Identity is a lifelong process."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert not result[0].startswith("KEY QUOTE")

    def test_drops_short_fragments(self):
        """Bullets < 15 chars are dropped (truncation artifacts)."""
        bullets = ["A valid bullet about identity formation.", "con", "short"]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert "valid bullet" in result[0]

    def test_strips_bold_author_prefix(self):
        """'**Author**: text' -> 'Author: text'."""
        bullets = ["**Erikson**: Defined ego identity as self-sameness."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0].startswith("Erikson:")
        assert "**" not in result[0]

    def test_cleans_trailing_ellipsis(self):
        """Trailing '...' is cleaned to '.'."""
        bullets = ["Identity formation involves multiple phases..."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0].endswith(".")
        assert "..." not in result[0]

    def test_drops_truncated_mid_sentence(self):
        """Bullets ending with trailing words (and, the, of...) are dropped."""
        bullets = [
            "This is a complete bullet about identity.",
            "The author discusses the formation of",
        ]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert "complete bullet" in result[0]

    def test_capitalizes_first_letter(self):
        """First letter is capitalized if lowercase."""
        bullets = ["erikson defined ego identity in 1956."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0][0] == "E"

    def test_empty_list(self):
        """Empty input returns empty."""
        assert normalize_bullets([]) == []

    # V18.15.3.1: double-dash stripping (gap-fill "- - Name: text" fix)

    def test_strips_double_dash_gap_fill_format(self):
        """V18.15.3.1: Gap-fill bullets arriving as '- - Name: text' have BOTH
        leading dashes stripped (was: only one stripped, leaving '- Name: text'
        which rendered as a double-dash bullet in markdown)."""
        bullets = [
            "- - Freud: According to Erikson (1958), Freud referred to identity once.",
            "- - Winnicott: His views on early development are significant.",
            "- - Blos: His 1962 work enriched Eissler's view on adolescent identity.",
        ]
        result = normalize_bullets(bullets)
        assert len(result) == 3
        for b in result:
            assert not b.startswith("-"), f"Still starts with dash: {b!r}"
            assert not b.startswith("- "), f"Still starts with '- ': {b!r}"
        assert result[0].startswith("Freud:")
        assert result[1].startswith("Winnicott:")
        assert result[2].startswith("Blos:")

    def test_strips_triple_dash(self):
        """V18.15.3.1: Even triple-dash '- - - Name' is fully stripped (loop)."""
        bullets = ["- - - Kernberg: Proposed a three-step process of identity formation."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0].startswith("Kernberg:")
        assert not result[0].startswith("-")

    def test_single_dash_still_stripped(self):
        """V18.15.3.1 regression: single-dash bullets still stripped (no change)."""
        bullets = ["- Erikson defined ego identity as persistent sameness."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0].startswith("Erikson")
        assert not result[0].startswith("-")

    def test_mixed_dash_and_numbered_prefixes(self):
        """V18.15.3.1: Mixed leading markers '- 1. Name' are all stripped."""
        bullets = ["- 1. Mahler: Distinguished psychological from biological birth."]
        result = normalize_bullets(bullets)
        assert len(result) == 1
        assert result[0].startswith("Mahler:")
        assert not result[0].startswith("-")
        assert not result[0][0].isdigit()


# == 6. classify_bullets (core of _filter_thinking_bullets) ==


class TestClassifyBullets:
    def test_drops_thinking_process_bullets(self):
        """Bullets starting with thinking verbs are dropped (always_drop=True)."""
        bullets = [
            "Analyze the chapter's key concepts.",
            "Erikson defined ego identity in 1956.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Erikson" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True  # always_drop=True

    def test_drops_prompt_leakage(self):
        """Bullets leaking prompt-template fields are dropped.

        Note: all PROMPT_LEAKAGE keywords (Source Text, Rules, Task, Format,
        etc.) also match _THINKING_STARTS, so they're caught by the
        thinking-process check first. The bullet IS dropped (always_drop=True)
        — the stage is 'thinking_process' rather than 'prompt_leakage'.
        This is a characteristic of the overlapping patterns.
        """
        bullets = [
            "Source Text: The chapter discusses identity formation in detail.",
            "A real bullet about identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "real bullet" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True  # always_drop=True (structural contamination)

    def test_drops_meta_commentary(self):
        """Model meta-commentary bullets are dropped (conservative-gated)."""
        bullets = [
            "This captures the concept of identity diffusion.",
            "Identity involves self-sameness and social sharing.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "self-sameness" in kept[0]
        meta_drops = [d for d in drops if "meta_commentary" in d[1]]
        assert len(meta_drops) == 1
        assert meta_drops[0][3] is False  # conservative-gated

    def test_drops_narrative_without_concept(self):
        """Narrative bullets with no concept indicator are dropped."""
        bullets = [
            "Ryan went to a party and met Thad.",
            "The author defines identity as a developmental process.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "developmental process" in kept[0]
        narrative_drops = [d for d in drops if "narrative" in d[1]]
        assert len(narrative_drops) == 1

    def test_keeps_narrative_with_concept(self):
        """Narrative bullets WITH concept indicators are kept."""
        bullets = [
            "Ryan went to a party, which illustrates the principle of social identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert len(drops) == 0

    def test_strips_orphaned_bold_labels(self):
        """'ConceptName**: text' prefixes are stripped from kept bullets."""
        bullets = ["Identity**: is defined as self-sameness and social sharing."]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "**:" not in kept[0]

    def test_drops_too_long_bullets(self):
        """Bullets > 500 chars are dropped (conservative-gated)."""
        long_bullet = "This is a very long bullet. " * 30
        bullets = [long_bullet, "A normal bullet about identity."]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        long_drops = [d for d in drops if "too_long" in d[1]]
        assert len(long_drops) == 1
        assert long_drops[0][3] is False

    def test_empty_list(self):
        """Empty input returns empty kept + empty drops."""
        kept, drops = classify_bullets([])
        assert kept == []
        assert drops == []

    def test_clean_bullets_all_kept(self):
        """A list of clean bullets all pass through."""
        bullets = [
            "Erikson defined ego identity as self-sameness.",
            "Mahler described five phases of separation-individuation.",
            "Kernberg proposed a three-step process of identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 3
        assert len(drops) == 0

    def test_drop_records_have_four_fields(self):
        """Each drop record is (bullet, stage, reason, always_drop)."""
        bullets = ["Analyze this chapter now."]
        kept, drops = classify_bullets(bullets)
        assert len(drops) == 1
        record = drops[0]
        assert len(record) == 4
        assert isinstance(record[0], str)
        assert isinstance(record[1], str)
        assert isinstance(record[2], str)
        assert isinstance(record[3], bool)


# == 7. V18.12.2: gap-fill prompt-leakage patterns ==


class TestClassifyBulletsGapFillPromptLeakage:
    """V18.12.2: classify_bullets drops gap-fill prompt template phrases.

    The V18.12.1 golden-master audit found the V17.8 batch gap-fill leaked
    prompt template text into the Key Takeaways (lines 65-69 of the summary):
    - 'a single bullet point summarizing what the source sentence says about'
    - 'the source sentence:'
    - 'What does this say about'
    These are the LLM's instructions to itself, not summary content. The
    _GAP_FILL_PROMPT_LEAKAGE regex in post_processing.py catches them.
    """

    def test_drops_a_single_bullet_point_summarizing(self):
        """The 'a single bullet point summarizing what the source sentence
        says about' phrase is dropped (always_drop=True)."""
        bullets = [
            'a single bullet point summarizing what the source sentence says about "infant" (or "infantile").',
            "Erikson defined ego identity in 1956.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Erikson" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True  # always_drop (structural contamination)
        assert "gap_fill_prompt_leakage" in drops[0][1]

    def test_drops_the_source_sentence_label(self):
        """The 'the source sentence:' label is dropped."""
        bullets = [
            'the source sentence: "These included the relative significance of infantile phases."',
            "Lichtenstein proposed the identity principle and metamorphosis.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Lichtenstein" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_what_does_this_say_about(self):
        """The 'What does this say about' question is dropped."""
        bullets = [
            'What does this say about "infant"',
            "Mahler distinguished psychological birth from biological birth.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Mahler" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_summarizing_what_the_source(self):
        """The 'summarizing what the source' phrase is dropped."""
        bullets = [
            "summarizing what the source sentence says about the concept",
            "Kernberg formulated a three-step process of identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Kernberg" in kept[0]
        assert len(drops) == 1

    def test_case_insensitive_match(self):
        """The gap-fill leakage patterns match case-insensitively."""
        bullets = [
            "THE SOURCE SENTENCE: some text here that leaked.",
            "A real bullet about identity.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "real bullet" in kept[0]
        assert len(drops) == 1

    def test_clean_gap_fill_bullet_kept(self):
        """A clean gap-fill bullet (no prompt-leakage) is kept."""
        bullets = [
            "Loewald: In 1951, pointed out the necessity for a growing toddler to maintain a stable relationship with the father.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Loewald" in kept[0]
        assert drops == [] or all("gap_fill_prompt_leakage" not in d[1] for d in drops)

    # V18.12.3: Tier 2 _targeted_gap_fill prompt-leakage patterns. The V18.12.2
    # audit found the Tier 2 path (prompt: "Write ONE bullet point summarizing
    # what this source sentence says about ...") leaked the template + the
    # LLM's internal monologue ("Wait - the user asks me", "Let me analyze",
    # "The user wants me to") into the Key Takeaways (lines 70-74 of the
    # V18.12.2 summary).

    def test_drops_me_to_write_one_bullet_point(self):
        """The 'me to write one bullet point' phrase (Tier 2 gap-fill leak) is dropped."""
        bullets = [
            "me to write one bullet point summarizing what the source sentence says about 'phase'.",
            "Erikson defined ego identity as persistent sameness.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Erikson" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_wait_the_user_asks(self):
        """The 'Wait - the user asks' internal monologue is dropped."""
        bullets = [
            "Wait - the user asks me to summarize what this sentence says about 'phase'.",
            "Lichtenstein proposed the identity principle and metamorphosis.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Lichtenstein" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_let_me_analyze(self):
        """The 'Let me analyze' internal monologue is dropped."""
        bullets = [
            "Let me analyze the source sentence to determine what it says about phase.",
            "Kernberg formulated a three-step process of identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Kernberg" in kept[0]
        # 'Let me analyze' is also caught by _THINKING_STARTS (Analyze/Let me),
        # so the drop stage might be 'thinking_process' or 'gap_fill_prompt_leakage'.
        # Either way, the leaked bullet is dropped.
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_the_user_wants_me_to(self):
        """The 'The user wants me to' internal monologue is dropped."""
        bullets = [
            "The user wants me to write one bullet about the concept of identity.",
            "Mahler distinguished psychological birth from biological birth.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Mahler" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True

    def test_drops_write_one_bullet_point(self):
        """The 'Write ONE bullet point' prompt-template phrase is dropped."""
        bullets = [
            "Write ONE bullet point (prefixed with '- ') summarizing what this source sentence says about 'phase'.",
            "Blos described the second individuation process of adolescence.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert "Blos" in kept[0]
        assert len(drops) == 1
        assert drops[0][3] is True
