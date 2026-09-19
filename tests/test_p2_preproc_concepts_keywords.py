"""P2 (Test-Net Deepening): hermetic tests for concept / keyword / callout
extraction in ``core/summarisation/text_preprocessor_impl.py``.

Covers:

  - ``_is_valid_concept``            (full branch matrix)
  - ``extract_definitions``          (A5 — quoted/definitional/concept-noun)
  - ``_tokenize`` / ``extract_ngram_keywords``  (A7)
  - ``extract_callouts``             (V3.9.6 bracket + prefix callouts)
  - ``extract_academic_terms``       (V3.7.0 Phase 2.3)
  - ``_extract_proper_noun_theorists`` / ``_normalize_heading``
  - ``_extract_section_headings`` / ``_extract_conclusion_lists``
  - ``_extract_position_weighted_concepts``
  - ``_llm_assisted_concept_extraction`` (LLM mocked at the callable boundary)
  - ``_filter_concepts_by_source`` / ``extract_concepts_rich``
  - ``extract_all_concepts`` / ``extract_implicit_concepts``

Hermetic: spaCy NER is stubbed at the ``model_singletons.get_spacy_nlp``
boundary (returns None → regex fallback never even consults spaCy) or at the
``get_all_ner_entities`` boundary for controlled entity sets. No network.

Run: pytest tests/test_p2_preproc_concepts_keywords.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.summarisation.text_preprocessor_impl as tpi


@pytest.fixture(autouse=True)
def _no_spacy(monkeypatch):
    """Force the absent-machine spaCy path: get_spacy_nlp → None.

    Keeps every NER call hermetic + fast (no repeated spacy.load probes).
    """
    import core.llm.model_singletons as ms

    monkeypatch.setattr(ms, "get_spacy_nlp", lambda *a, **k: None)


@pytest.fixture()
def no_ner(monkeypatch):
    """Make get_all_ner_entities return a controlled empty entity set."""
    monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())


# ═══════════════════════════════════════════════════════════════════════════
# _is_valid_concept — full branch matrix
# ═══════════════════════════════════════════════════════════════════════════


class TestIsValidConcept:
    @pytest.mark.parametrize(
        "term",
        ["", "  ", "ab", "abc", "x" * 51],
    )
    def test_reject_length_bounds(self, term):
        assert tpi._is_valid_concept(term) is False

    def test_reject_five_words(self):
        assert tpi._is_valid_concept("One Two Three Four Five") is False

    def test_accept_all_caps_acronym(self):
        assert tpi._is_valid_concept("SADR") is True
        # CHARACTERIZATION: the docstring promises 3+ letter acronyms (CIA),
        # but the global min-length gate (len(term) < 4) rejects them first.
        assert tpi._is_valid_concept("CIA") is False

    def test_reject_single_non_acronym_word(self):
        assert tpi._is_valid_concept("Hello") is False
        assert tpi._is_valid_concept("AB") is False  # 2-letter caps < 3

    def test_reject_duplicated_words(self):
        assert tpi._is_valid_concept("Casing Casing") is False

    @pytest.mark.parametrize("term", ["Is Valid", "Do Things", "And Stuff", "When Then"])
    def test_reject_sentence_fragment_starts(self, term):
        assert tpi._is_valid_concept(term) is False

    def test_reject_sentence_punctuation(self):
        assert tpi._is_valid_concept("Term With Period.") is False
        assert tpi._is_valid_concept("Semicolon; Term") is False

    def test_reject_newlines_and_tabs(self):
        # V13.37.0: PDF table garbage "Nai\nB" must be rejected.
        assert tpi._is_valid_concept("Nai\nB") is False
        assert tpi._is_valid_concept("Tab\tTerm") is False

    def test_reject_all_common_english_words(self):
        assert tpi._is_valid_concept("The Way") is False
        assert tpi._is_valid_concept("Study Method") is False

    def test_reject_short_last_word(self):
        # V10.12.9 truncated fragment ("Locus Coe")
        assert tpi._is_valid_concept("Locus Coe") is False

    def test_reject_two_short_words(self):
        # V13.40.3: "Nai B" / "Ego Id" — average word length < 4
        assert tpi._is_valid_concept("Nai B") is False
        assert tpi._is_valid_concept("Ego Id") is False

    def test_reject_three_words_short_last(self):
        # V13.40.5: last word < 5 chars on a 3+ word concept
        assert tpi._is_valid_concept("Self Is Simp") is False

    def test_reject_all_title_case_four_words(self):
        # V13.40.5: 4+ words, all Title Case → table fragment
        assert tpi._is_valid_concept("Conquest Of The World") is False

    @pytest.mark.parametrize("term", ["Focus Base", "Locus Coeruleus", "Growth Mindset"])
    def test_accept_valid_concepts(self, term):
        assert tpi._is_valid_concept(term) is True


# ═══════════════════════════════════════════════════════════════════════════
# extract_definitions
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractDefinitions:
    def test_quoted_term_repeated(self, no_ner):
        text = 'Use the "Focus Base" idea. Use the "Focus Base" again.'
        assert tpi.extract_definitions(text) == ["Focus Base"]

    def test_frequency_filter_fallback_when_few_repeats(self, no_ner):
        # Single occurrences → <3 pass the ≥2 filter → fall back to all terms.
        text = 'The "Alpha Beta" concept. The "Gamma Delta" concept. The "Epsilon Zeta" idea.'
        out = tpi.extract_definitions(text)
        assert "Alpha Beta" in out and "Gamma Delta" in out and "Epsilon Zeta" in out

    def test_definition_verb_pattern(self, no_ner):
        text = "Alpha Delta is defined as something. Alpha Delta means stuff. Alpha Delta refers to things."
        assert tpi.extract_definitions(text) == ["Alpha Delta"]

    def test_concept_noun_pattern(self, no_ner):
        text = "The Beta Gamma principle is key. The Beta Gamma principle rocks."
        assert tpi.extract_definitions(text) == ["Beta Gamma"]

    def test_max_terms_cap(self, no_ner):
        text = " ".join(f'The "Term Number {i:02d}" idea.' for i in range(1, 8)) * 2
        assert len(tpi.extract_definitions(text, max_terms=3)) <= 3

    def test_ner_tokens_exclude_person_concepts(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: {"Marcus", "Vega"})
        text = 'Marcus Vega discussed the idea. "Marcus Vega" is a name, not a concept.'
        assert "Marcus Vega" not in tpi.extract_definitions(text)

    def test_ner_failure_is_swallowed(self, monkeypatch):
        def boom(_):
            raise RuntimeError("ner exploded")

        monkeypatch.setattr(tpi, "get_all_ner_entities", boom)
        text = 'Use the "Focus Base" idea. Use the "Focus Base" again.'
        assert tpi.extract_definitions(text) == ["Focus Base"]

    def test_all_stopword_terms_excluded(self, no_ner):
        # A quoted phrase made entirely of CONCEPT_STOPWORDS never counts.
        text = 'He said "the" loudly. He said "the" loudly again.'
        assert tpi.extract_definitions(text) == []

    def test_lowercase_quoted_jargon_caught(self, no_ner):
        # V3.2.1: lowercase quoted coinages are caught (quoted-term pattern).
        text = 'the "quiet schema" appears here and the "quiet schema" returns.'
        assert "Quiet Schema" in tpi.extract_definitions(text)


# ═══════════════════════════════════════════════════════════════════════════
# _tokenize / extract_ngram_keywords
# ═══════════════════════════════════════════════════════════════════════════


class TestNgramKeywords:
    def test_tokenize_filters(self):
        tokens = tpi._tokenize("The CAT ran quickly to a big banana; x123 was there 42 times.")
        assert "banana" in tokens
        assert "quickly" in tokens
        assert "times" in tokens
        assert "the" not in tokens  # stopword
        assert "ran" not in tokens  # < 4 chars
        assert "cat" not in tokens  # < 4 chars
        assert "x123" not in tokens  # non-pure-alpha
        assert "42" not in tokens

    def test_empty_and_stopword_only(self):
        assert tpi.extract_ngram_keywords("") == []
        assert tpi.extract_ngram_keywords("the and but was") == []

    def test_bigram_ranks_above_unigrams(self):
        text = "network protocol routing. network protocol speed. network protocol again."
        out = tpi.extract_ngram_keywords(text, n=5)
        assert out[0] == "network protocol"

    def test_trigram_present(self):
        text = ("spatial network analysis helps. " * 3).strip()
        out = tpi.extract_ngram_keywords(text, n=10)
        assert "spatial network analysis" in out

    def test_cap_and_determinism(self):
        text = " ".join(f"topic{i % 3} filler words here" for i in range(30))
        assert tpi.extract_ngram_keywords(text, n=4) == tpi.extract_ngram_keywords(text, n=4)
        assert len(tpi.extract_ngram_keywords(text, n=4)) <= 4


# ═══════════════════════════════════════════════════════════════════════════
# extract_callouts
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractCallouts:
    def test_bracket_callouts(self):
        text = (
            "[Spy Tip]: Always verify your sources before trusting them fully.\n"
            "[Key Point]: The central claim of this chapter is repetition.\n"
            "[Important]: Do not skip the exercises at each chapter end.\n"
        )
        out = tpi.extract_callouts(text)
        assert len(out) == 3
        assert out[0].startswith("Always verify")

    def test_non_bracket_callouts(self):
        text = (
            "Exercise: Write down three concrete goals for the coming week.\n"
            "Try This: Practise the technique for five minutes every day.\n"
            "Step 3: Review your notes and highlight the main ideas.\n"
        )
        out = tpi.extract_callouts(text)
        assert len(out) == 3
        assert out[0].startswith("Write down")

    def test_short_callouts_ignored(self):
        text = "[Key Point]: Too short."
        assert tpi.extract_callouts(text) == []

    def test_whitespace_collapsed(self):
        text = "[Remember]: A   callout   with\t ragged whitespace inside it."
        out = tpi.extract_callouts(text)
        assert out == ["A callout with ragged whitespace inside it."]

    def test_duplicate_callouts_deduped(self):
        # The prefix callout is captured first; the identical bracket callout
        # is then suppressed by the not-in-callouts dedup check.
        text = (
            "Takeaway: This exact same sentence appears twice here now.\n"
            "[Note]: This exact same sentence appears twice here now.\n"
        )
        out = tpi.extract_callouts(text)
        assert out == ["This exact same sentence appears twice here now."]

    def test_cap_at_fifteen(self):
        parts = [
            f"[Tip {i % 3}]: Callout number {i} with enough body text to count." for i in range(20)
        ]
        assert len(tpi.extract_callouts("\n".join(parts))) <= 15


# ═══════════════════════════════════════════════════════════════════════════
# extract_academic_terms
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractAcademicTerms:
    def test_domain_phrase_found(self, no_ner):
        text = "The hierarchy of needs matters. Maslow discussed the hierarchy of needs often."
        assert "Hierarchy Of Needs" in tpi.extract_academic_terms(text)

    def test_single_word_domain_terms_skipped(self, no_ner):
        # V3.9.2: single words from domain lists (mindfulness, agile) are skipped.
        text = "mindfulness helps. mindfulness again. agile works. agile rocks."
        assert tpi.extract_academic_terms(text) == []

    def test_parenthetical_definition_pattern(self, no_ner):
        text = (
            "Cognitive dissonance (a state of mental discomfort) drives change. "
            "Cognitive dissonance appears twice."
        )
        assert "Cognitive Dissonance" in tpi.extract_academic_terms(text)

    def test_italic_markdown_terms(self, no_ner):
        text = "He used *virtue ethics* framing. The *virtue ethics* view returns."
        assert "Virtue Ethics" in tpi.extract_academic_terms(text)

    def test_frequency_filter_requires_two(self, no_ner):
        text = "The unique phrase value proposition appears only once here."
        assert "Value Proposition" not in tpi.extract_academic_terms(text)

    def test_max_terms_cap(self, no_ner):
        text = (
            "brand positioning and customer segmentation and target market. "
            "brand positioning and customer segmentation and target market."
        )
        assert len(tpi.extract_academic_terms(text, max_terms=2)) <= 2


# ═══════════════════════════════════════════════════════════════════════════
# _extract_proper_noun_theorists / _normalize_heading
# ═══════════════════════════════════════════════════════════════════════════


class TestProperNounTheorists:
    def test_citation_pattern(self):
        text = "Erikson (1950) wrote. Erikson (1968) again. Freud (1923a) cited."
        out = tpi._extract_proper_noun_theorists(text)
        assert out[0] == "Erikson"  # most cited
        assert "Freud" in out

    def test_stop_names_excluded(self):
        text = "Chapter (1900) and Figure (1950) and See (1920) and Cf (1910) referenced."
        assert tpi._extract_proper_noun_theorists(text) == []

    def test_hyphenated_surname(self):
        text = "Authorson-Smith (1983, 1984) wrote the definitive account."
        assert "Authorson-Smith" in tpi._extract_proper_noun_theorists(text)

    def test_short_names_excluded(self):
        text = "Ab (1950) wrote something once."
        assert tpi._extract_proper_noun_theorists(text) == []

    def test_max_terms(self):
        text = " ".join(f"{chr(65 + i)}ob{chr(97 + i)}son (19{50 + i}) wrote." for i in range(20))
        assert len(tpi._extract_proper_noun_theorists(text, max_terms=5)) == 5


class TestNormalizeHeading:
    def test_collapses_whitespace(self):
        assert tpi._normalize_heading("  Foo   Bar\n\nBaz  ") == "Foo Bar Baz"


# ═══════════════════════════════════════════════════════════════════════════
# _extract_section_headings / _extract_conclusion_lists
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractSectionHeadings:
    def test_markdown_headings(self):
        text = "## First Heading\n\ntext\n\n### Second Heading\n\n#### Third Heading\n"
        out = tpi._extract_section_headings(text)
        assert out[:3] == ["First Heading", "Second Heading", "Third Heading"]

    def test_all_caps_marker_title_cased(self):
        text = "intro\n\nTHE CONCEPT OF IDENTITY\n\nbody text"
        assert "The Concept Of Identity" in tpi._extract_section_headings(text)

    def test_bold_terms(self):
        text = "Some text with **Bold Term Here** inside it."
        assert "Bold Term Here" in tpi._extract_section_headings(text)

    def test_dedup_case_insensitive(self):
        text = "## Same Heading\n\nx\n\n## SAME HEADING\n\ny"
        assert tpi._extract_section_headings(text).count("Same Heading") == 1

    def test_bounds_and_cap(self):
        text = "## ab\n\n## " + "L" * 81 + "\n\n## Valid Heading Name\n"
        out = tpi._extract_section_headings(text)
        assert out == ["Valid Heading Name"]


class TestExtractConclusionLists:
    def test_explicit_conclusion_marker(self):
        text = "Body.\n\n## CONCLUSION\n\n(1) sustained feeling of selfsameness\n(2) temporal continuity"
        out = tpi._extract_conclusion_lists(text)
        assert out == ["sustained feeling of selfsameness", "temporal continuity"]

    def test_plain_conclusion_marker(self):
        text = (
            "Body text.\n\nCONCLUSION\n\n(1) first conclusion item text\n(2) second conclusion item"
        )
        out = tpi._extract_conclusion_lists(text)
        assert out[0] == "first conclusion item text"

    def test_fallback_last_twenty_percent(self):
        tail = "(1) fallback item one appears (2) fallback item two appears"
        text = "Body filler. " * 60 + tail
        out = tpi._extract_conclusion_lists(text)
        assert "fallback item one appears" in out

    def test_trailing_punctuation_stripped(self):
        text = "Body.\n\n# CONCLUSION\n\n(1) item with comma, (2) item with semicolon;"
        out = tpi._extract_conclusion_lists(text)
        assert out == ["item with comma", "item with semicolon"]

    def test_max_terms_cap(self):
        items = " ".join(f"({i}) conclusion item number {i} here" for i in range(1, 15))
        text = "Body.\n\n## CONCLUSION\n\n" + items
        assert len(tpi._extract_conclusion_lists(text, max_terms=5)) == 5


# ═══════════════════════════════════════════════════════════════════════════
# _extract_position_weighted_concepts
# ═══════════════════════════════════════════════════════════════════════════


class TestPositionWeightedConcepts:
    def test_intro_conclusion_phrase(self):
        txt = (
            "Here we introduce Creative Personality Theory for readers. "
            + "filler content words here for padding purposes only. " * 10
            + "In sum, Creative Personality Theory explains everything."
        )
        assert tpi._extract_position_weighted_concepts(txt) == ["Creative Personality Theory"]

    def test_stopword_first_word_rejected(self):
        txt = (
            "The Creative Personality appears here. "
            + "filler words " * 10
            + " The Creative Personality again."
        )
        assert tpi._extract_position_weighted_concepts(txt) == []

    def test_single_word_phrase_rejected(self):
        # Title-pattern needs 2+ words.
        txt = "Repeatable Word appears. " * 3
        assert tpi._extract_position_weighted_concepts(txt) == []

    def test_rare_phrase_outside_positions_rejected(self):
        # Frequency gate: ≥2 in full text OR ≥1 in intro/conclusion zones.
        # The phrase sits in the middle 70% and appears only once → rejected.
        head = "Intro filler words only for padding purposes. " * 4
        tail = " End tail filler words for padding purposes here. " * 4
        body = "middle text mentions Special Phrase once only here. "
        assert tpi._extract_position_weighted_concepts(head + body + tail) == []


# ═══════════════════════════════════════════════════════════════════════════
# _llm_assisted_concept_extraction (LLM mocked at the callable boundary)
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMAssistedConceptExtraction:
    def test_none_fn_returns_empty(self):
        assert tpi._llm_assisted_concept_extraction("text", None) == []

    def test_parses_bullet_lines(self):
        raw = "- Concept One\n- Concept Two\n* Concept Three\n1. Concept Four\n"
        out = tpi._llm_assisted_concept_extraction("text", lambda p: raw)
        # CHARACTERIZATION (quirk): "1. X" lines keep a leading ". " because
        # the single-char alternation [-*\d.] eats only the "1".
        assert out == ["Concept One", "Concept Two", "Concept Three", ". Concept Four"]

    def test_short_response_returns_empty(self):
        assert tpi._llm_assisted_concept_extraction("text", lambda p: "short") == []
        assert tpi._llm_assisted_concept_extraction("text", lambda p: "  ") == []

    def test_len_filters_and_dedup(self):
        raw = "- ab\n- " + "L" * 101 + "\n- Real Concept\n- real concept\n"
        out = tpi._llm_assisted_concept_extraction("text", lambda p: raw)
        assert out == ["Real Concept"]

    def test_exception_returns_empty(self):
        def boom(_):
            raise RuntimeError("llm down")

        logs = []
        assert (
            tpi._llm_assisted_concept_extraction("text", boom, log_fn=lambda m, l: logs.append(m))
            == []
        )
        assert any("failed" in m.lower() for m in logs)

    def test_log_fn_receives_progress(self):
        logs = []

        def log(msg, level="DEBUG"):
            logs.append((msg, level))

        tpi._llm_assisted_concept_extraction(
            "text", lambda p: "- Some Longer Concept Name", log_fn=log
        )
        assert any("starting" in m for m, _ in logs)
        assert any("extracted 1 concepts" in m for m, _ in logs)

    def test_prompt_contains_source_text(self):
        seen = {}

        def fn(p):
            seen["prompt"] = p
            return "- Some Concept Name"

        tpi._llm_assisted_concept_extraction("UNIQUE-SOURCE-TOKEN", fn)
        assert "UNIQUE-SOURCE-TOKEN" in seen["prompt"]

    def test_truncates_to_8000_chars(self):
        seen = {}

        def fn(p):
            seen["prompt"] = p
            return "- Some Concept Name"

        tpi._llm_assisted_concept_extraction("x" * 20000, fn)
        assert "x" * 9000 not in seen["prompt"]  # truncated well below 20k


# ═══════════════════════════════════════════════════════════════════════════
# _filter_concepts_by_source / extract_concepts_rich
# ═══════════════════════════════════════════════════════════════════════════


class TestFilterConceptsBySource:
    def test_full_match_passes(self):
        passed, dropped = tpi._filter_concepts_by_source(
            ["Locus Coeruleus"], "The locus coeruleus is a nucleus in the brainstem."
        )
        assert passed == ["Locus Coeruleus"]
        assert dropped == []

    def test_fragment_match_passes(self):
        # First-3-words fragment ≥15 chars present in source.
        passed, dropped = tpi._filter_concepts_by_source(
            ["Sustained Feeling Of Selfsameness"],
            "the sustained feeling of selfsameness is central",
        )
        assert passed == ["Sustained Feeling Of Selfsameness"]

    def test_longest_word_match_passes(self):
        # Multi-word concept whose full phrase is absent but whose longest
        # single word (≥6 chars) appears in the source.
        passed, dropped = tpi._filter_concepts_by_source(
            ["Selfsameness Continuity Theory"], "the selfsameness concept persists over time"
        )
        assert passed == ["Selfsameness Continuity Theory"]
        assert dropped == []

    def test_ghost_concept_dropped(self):
        passed, dropped = tpi._filter_concepts_by_source(
            ["Ghost Concept Nothing"], "totally unrelated source text"
        )
        assert passed == []
        assert dropped == ["Ghost Concept Nothing"]


class TestExtractConceptsRich:
    TEXT = (
        "Erikson (1950) wrote about identity development stages.\n"
        + "Plain body filler words without special meaning here. " * 5
        + "\n## Identity Development Stages\n\nBody text.\n\n"
        + "## CONCLUSION\n\n(1) identity forms through crisis resolution\n"
    )

    def test_merges_techniques(self):
        out = tpi.extract_concepts_rich(self.TEXT)
        assert "Erikson" in out
        assert "Identity Development Stages" in out
        assert "identity forms through crisis resolution" in out

    def test_llm_concepts_included(self):
        # The LLM concept must itself be source-grounded to survive
        # Technique #6 ("Plain body filler" occurs in the source body).
        out = tpi.extract_concepts_rich(
            self.TEXT, llm_call_fn=lambda p: "- Plain Body Filler Words Here"
        )
        assert any("Plain Body Filler" in t for t in out)

    def test_llm_ghost_concept_dropped_by_grounding(self):
        logs = []
        out = tpi.extract_concepts_rich(
            self.TEXT,
            llm_call_fn=lambda p: "- Totally Invented Concept",
            log_fn=lambda m, l: logs.append(m),
        )
        assert not any("Totally Invented" in t for t in out)
        assert any("dropped" in m for m in logs)

    def test_no_llm_fn_skips_technique_five(self):
        logs = []
        tpi.extract_concepts_rich("plain text only here", log_fn=lambda m, l: logs.append(m))
        assert any("skipped (no llm_call_fn" in m for m in logs)

    def test_technique_exception_isolated(self, monkeypatch):
        def boom(text, max_terms=15):
            raise RuntimeError("technique exploded")

        monkeypatch.setattr(tpi, "_extract_proper_noun_theorists", boom)
        logs = []
        out = tpi.extract_concepts_rich(self.TEXT, log_fn=lambda m, l: logs.append(m))
        assert "Erikson" not in out
        assert any("#2 failed" in m for m in logs)

    def test_source_grounding_drops_ghosts(self):
        logs = []
        out = tpi.extract_concepts_rich(self.TEXT, log_fn=lambda m, l: logs.append(m))
        # Everything returned must be groundable in the source text.
        assert all(
            t.lower() in self.TEXT.lower() or any(w.lower() in self.TEXT.lower() for w in t.split())
            for t in out
        )
        assert any("source-grounded" in m for m in logs)

    def test_cap_max_terms(self):
        out = tpi.extract_concepts_rich(self.TEXT, max_terms=1)
        assert len(out) == 1

    def test_default_noop_log(self):
        # log_fn=None installs a no-op — must not raise.
        assert isinstance(tpi.extract_concepts_rich("text words here"), list)


# ═══════════════════════════════════════════════════════════════════════════
# extract_all_concepts / extract_implicit_concepts
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractAllConcepts:
    def test_merges_sources_dedup(self, no_ner):
        text = (
            'The "Focus Base" concept. Use the "Focus Base" again. '
            "The hierarchy of needs matters and the hierarchy of needs repeats. "
            "Delta Epsilon appears. Delta Epsilon appears. Delta Epsilon appears."
        )
        out = tpi.extract_all_concepts(text)
        assert "Focus Base" in out
        assert "Hierarchy Of Needs" in out
        assert "Delta Epsilon" in out
        # No duplicates (case-insensitive).
        lowered = [t.lower() for t in out]
        assert len(lowered) == len(set(lowered))

    def test_invalid_concepts_filtered(self, no_ner):
        text = 'The "Focus Base" concept. Use the "Focus Base" again. Plain words only here.'
        out = tpi.extract_all_concepts(text)
        assert all(tpi._is_valid_concept(t) for t in out)

    def test_cap(self, no_ner):
        text = (
            'The "Focus Base" concept. Use the "Focus Base" again. '
            "brand positioning and customer segmentation repeat brand positioning customer segmentation."
        )
        assert len(tpi.extract_all_concepts(text, max_terms=1)) == 1


class TestExtractImplicitConcepts:
    def test_frequent_title_phrase(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        text = "Delta Epsilon appears here. Delta Epsilon appears again. Delta Epsilon appears once more."
        assert tpi.extract_implicit_concepts(text) == ["Delta Epsilon"]

    def test_under_three_occurrences_filtered(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        text = "Zeta Eta appears here. Zeta Eta appears again only."
        assert tpi.extract_implicit_concepts(text) == []

    def test_stopword_first_word_skipped(self):
        text = "The Delta appears here. The Delta appears again. The Delta appears once more."
        assert tpi.extract_implicit_concepts(text) == []

    def test_ner_phrase_skipped(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: {"Vega"})
        text = "Marcus Vega appears here. Marcus Vega again. Marcus Vega once more."
        assert tpi.extract_implicit_concepts(text) == []

    def test_ner_exception_swallowed(self, monkeypatch):
        def boom(_):
            raise RuntimeError("ner down")

        monkeypatch.setattr(tpi, "get_all_ner_entities", boom)
        text = "Omega Psi appears here. Omega Psi again. Omega Psi once more."
        assert tpi.extract_implicit_concepts(text) == ["Omega Psi"]


class TestGapClosingConcepts:
    """Second-wave branch coverage for the concept-extraction family."""

    def test_definitions_all_concept_stopword_terms_skipped(self, no_ner):
        # "Remember Things" passes _is_valid_concept but every word is in
        # CONCEPT_STOPWORDS → rejected in all three pattern loops.
        text = (
            'Use "Remember Things" here. Use "Remember Things" again. '
            "Remember Things means something. Remember Things refers to stuff. "
            "The Remember Things principle is central. The Remember Things principle rocks."
        )
        assert tpi.extract_definitions(text) == []

    def test_conclusion_list_short_item_skipped(self):
        text = "Body.\n\n## CONCLUSION\n\n(1) ab\n(2) real item text here"
        out = tpi._extract_conclusion_lists(text)
        assert out == ["real item text here"]

    def test_conclusion_list_duplicate_item_skipped(self):
        text = "Body.\n\n## CONCLUSION\n\n(1) duplicate item text\n(2) duplicate item text"
        out = tpi._extract_conclusion_lists(text)
        assert out == ["duplicate item text"]

    def test_position_weighted_overlong_phrase_rejected(self):
        phrase = "Extraordinarily Complicated Institutional Obstructionism"
        assert len(phrase) > 50
        txt = phrase + " appears. " + "filler words only " * 20
        assert tpi._extract_position_weighted_concepts(txt) == []

    def test_position_weighted_newline_phrase_rejected(self):
        # The title pattern spans a newline (\s+) — the phrase is then rejected.
        txt = "Creative\nPersonality Theory appears. " + "filler words only " * 20
        assert tpi._extract_position_weighted_concepts(txt) == []

    def test_position_weighted_intro_only_phrase_accepted(self):
        # Appears once, in the intro zone, <2 times overall → intro-count path.
        txt = "Creative Personality Theory appears. " + "filler words only here for padding. " * 20
        assert "Creative Personality Theory" in tpi._extract_position_weighted_concepts(txt)

    def test_llm_assisted_short_response_logged(self):
        logs = []
        out = tpi._llm_assisted_concept_extraction(
            "text", lambda p: "short", log_fn=lambda m, l: logs.append(m)
        )
        assert out == []
        assert any("empty/short response" in m for m in logs)

    def test_rich_technique_exceptions_isolated(self, monkeypatch):
        def boom(text, max_terms=12):
            raise RuntimeError("technique exploded")

        monkeypatch.setattr(tpi, "_extract_position_weighted_concepts", boom)
        monkeypatch.setattr(tpi, "_extract_section_headings", boom)
        monkeypatch.setattr(tpi, "_extract_conclusion_lists", boom)
        logs = []
        out = tpi.extract_concepts_rich(
            "Erikson (1950) wrote about identity.", log_fn=lambda m, l: logs.append(m)
        )
        assert out == ["Erikson"]  # technique #2 still works
        assert any("#1 failed" in m for m in logs)
        assert any("#3 failed" in m for m in logs)
        assert any("#4 failed" in m for m in logs)

    def test_rich_llm_prompt_manager_failure_isolated(self, monkeypatch):
        from core.summarisation import prompt_manager as pm_mod

        def boom(self, name, **kw):
            raise RuntimeError("pm down")

        monkeypatch.setattr(pm_mod.PromptManager, "render_template", boom)
        logs = []
        out = tpi.extract_concepts_rich(
            "Erikson (1950) wrote.",
            llm_call_fn=lambda p: "- Some Concept",
            log_fn=lambda m, l: logs.append(m),
        )
        assert "Erikson" in out
        assert any("#5 failed" in m for m in logs)

    def test_rich_duplicate_terms_deduped(self):
        text = "Erikson (1950) wrote.\n\n## Erikson\n\nBody text here."
        out = tpi.extract_concepts_rich(text)
        assert out.count("Erikson") == 1

    def test_rich_filter_failure_falls_back_to_unfiltered(self, monkeypatch):
        def boom(concepts, source_text, min_overlap_chars=15):
            raise RuntimeError("filter exploded")

        monkeypatch.setattr(tpi, "_filter_concepts_by_source", boom)
        logs = []
        out = tpi.extract_concepts_rich(
            "Erikson (1950) wrote about identity.", log_fn=lambda m, l: logs.append(m)
        )
        assert "Erikson" in out  # unfiltered fallback keeps everything
        assert any("#6 failed" in m for m in logs)

    def test_all_concepts_duplicate_across_sources_deduped(self, no_ner):
        # Quoted "Focus Base" (title-cased) + implicit "Focus Base" (3x).
        text = (
            'The "Focus Base" concept. Use the "Focus Base" again. '
            "Focus Base appears. Focus Base appears. Focus Base appears."
        )
        out = tpi.extract_all_concepts(text)
        assert out.count("Focus Base") == 1

    def test_all_concepts_invalid_implicit_phrase_filtered(self, monkeypatch):
        # "Casing Casing" passes implicit extraction (no validity check there)
        # but fails _is_valid_concept in the final safety net.
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        text = "Casing Casing appears. Casing Casing appears. Casing Casing appears."
        assert "Casing Casing" not in tpi.extract_all_concepts(text)

    def test_implicit_overlong_phrase_rejected(self):
        phrase = "Extraordinarily Complicated Institutional Obstructionism Here"
        assert len(phrase) > 50
        text = f"{phrase} appears. {phrase} appears. {phrase} appears."
        assert tpi.extract_implicit_concepts(text) == []

    def test_implicit_all_stopword_phrase_rejected(self):
        text = "The Chapter appears. The Chapter appears. The Chapter appears."
        assert tpi.extract_implicit_concepts(text) == []
