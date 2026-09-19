"""P2 (Test-Net Deepening): hermetic tests for the verification / scoring /
NER / fact-check half of ``core/summarisation/text_preprocessor_impl.py``.

Covers:

  - ``verify_numbers_and_quotes``   (C4)
  - ``normalize_sentence_boundaries`` (C5)
  - ``score_ocr_quality``           (E2)
  - ``score_bullet_complexity`` / ``vocabulary_overlap_score`` /
    ``should_skip_simplification``  (G1/G2)
  - ``extract_named_entities``      (I1 — regex fallback + fake-spaCy path)
  - ``_load_spacy_model`` / ``get_all_ner_entities``
  - ``_bullet_similarity`` / ``order_bullets_by_topic`` (J1)
  - ``validate_summary_length`` / ``truncate_summary`` (F1)
  - ``compute_source_overlap`` (F4) / ``compute_bullet_confidence`` (K1)
  - ``find_source_excerpt`` (K2) / ``find_source_page`` (H2)
  - ``count_syllables`` / ``flesch_kincaid_grade`` / ``assess_reading_level`` (F3)
  - ``score_chapter_difficulty`` (I2)
  - ``check_cross_section_redundancy`` (J2) — rapidfuzz present AND absent
  - ``check_exec_summary_coherence`` (J3)
  - ``classify_bullet`` (V3.6.0)
  - ``semantic_fact_check`` / ``_get_embed_model`` — embedder mocked or absent

Hermetic: spaCy stubbed at the ``model_singletons.get_spacy_nlp`` boundary,
embedder stubbed at ``_get_embed_model``; rapidfuzz-absence simulated via
``sys.modules``. No network, no GPU.

Run: pytest tests/test_p2_preproc_validation_scoring.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.summarisation.text_preprocessor_impl as tpi
from core.summarisation._runtime_state import state as runtime_state


@pytest.fixture(autouse=True)
def _no_spacy(monkeypatch):
    """Force the absent-machine spaCy path (regex NER fallback)."""
    import core.llm.model_singletons as ms

    monkeypatch.setattr(ms, "get_spacy_nlp", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _reset_runtime_singletons():
    """Snapshot/restore the shared runtime state the tests touch."""
    prev_nlp = runtime_state.spacy_nlp
    prev_lang = runtime_state.spacy_lang
    prev_warned = runtime_state.warned_no_embed_model
    yield
    runtime_state.spacy_nlp = prev_nlp
    runtime_state.spacy_lang = prev_lang
    runtime_state.warned_no_embed_model = prev_warned


# ═══════════════════════════════════════════════════════════════════════════
# C4: verify_numbers_and_quotes
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyNumbersAndQuotes:
    def test_all_numbers_present(self):
        ok, reasons = tpi.verify_numbers_and_quotes(
            "Growth was 45% in 2020.", "Growth was 45% in 2020 overall."
        )
        assert ok is True and reasons == []

    def test_small_numbers_not_skipped(self):
        # V9.0.0 P3-3: fabricated "3 steps" must be caught.
        ok, reasons = tpi.verify_numbers_and_quotes(
            "There were 3 steps.", "No steps mentioned at all here."
        )
        assert ok is False
        assert any("number '3'" in r for r in reasons)

    def test_missing_number_rejected(self):
        ok, reasons = tpi.verify_numbers_and_quotes(
            "Growth was 46% in 2020.", "Growth was 45% in 2020 overall."
        )
        assert ok is False
        assert reasons == ["number '46' not found in source"]

    def test_quote_found_passes(self):
        ok, _ = tpi.verify_numbers_and_quotes(
            'He said "this is a quoted phrase from text" loudly.',
            'Source contains "this is a quoted phrase from text".',
        )
        assert ok is True

    def test_quote_below_threshold_rejected(self):
        ok, reasons = tpi.verify_numbers_and_quotes(
            'He said "totally different words appear here now" loudly.',
            "Source contains other words entirely.",
        )
        assert ok is False
        assert any("quote" in r for r in reasons)

    def test_short_quote_skipped(self):
        # Quotes under 5 words are not fuzzy-checked.
        ok, _ = tpi.verify_numbers_and_quotes('He said "tiny quote" now.', "Unrelated source.")
        assert ok is True

    def test_no_numbers_no_quotes(self):
        assert tpi.verify_numbers_and_quotes("Plain bullet text.", "Any source.") == (True, [])


# ═══════════════════════════════════════════════════════════════════════════
# C5: normalize_sentence_boundaries
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeSentenceBoundaries:
    def test_empty_passes_through(self):
        assert tpi.normalize_sentence_boundaries("") == ""

    def test_keeps_first_two_sentences(self):
        assert tpi.normalize_sentence_boundaries("One. Two. Three.") == "One. Two."

    def test_max_sentences_one(self):
        assert tpi.normalize_sentence_boundaries("One. Two.", max_sentences=1) == "One."

    def test_word_cap_truncates_with_ellipsis(self):
        out = tpi.normalize_sentence_boundaries("word " * 50 + "end.", max_words=40)
        words = out.rstrip(".…").split()
        assert len(words) == 40
        # Ellipsis is appended, then the terminal-punctuation pass adds a
        # final period ("…" is not in ".!?").
        assert out.endswith("….")

    def test_adds_missing_terminal_punctuation(self):
        assert tpi.normalize_sentence_boundaries("no ending punct") == "no ending punct."

    def test_all_fragments_filtered_returns_original(self):
        # Fragments of ≤3 chars are dropped; if nothing survives, the
        # original bullet is returned unchanged.
        assert tpi.normalize_sentence_boundaries("ab. cd.") == "ab. cd."


# ═══════════════════════════════════════════════════════════════════════════
# E2: score_ocr_quality
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreOcrQuality:
    @pytest.mark.parametrize("text", ["", "short", "   ", "1234567890123456789"])
    def test_degenerate_inputs_score_zero(self, text):
        assert tpi.score_ocr_quality(text) == 0.0

    def test_clean_english_scores_high(self):
        good = "The quick brown fox jumps over the lazy dog and runs to the river every day."
        assert tpi.score_ocr_quality(good) >= 0.8

    def test_garbage_scores_lower_than_clean(self):
        good = "The quick brown fox jumps over the lazy dog and runs to the river every day."
        bad = "Xhqq Zzxxv Kkwp Lmmnb Qqzzx Vvcxx NNbmm Llkkj Hhggff Ddssaa"
        assert tpi.score_ocr_quality(bad) < tpi.score_ocr_quality(good)

    def test_score_bounds(self):
        assert (
            0.0
            <= tpi.score_ocr_quality("Marginal text with some words here to score maybe.")
            <= 1.0
        )


# ═══════════════════════════════════════════════════════════════════════════
# G1/G2: complexity / vocabulary overlap / skip decision
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreBulletComplexity:
    @pytest.mark.parametrize("bullet", ["", "short", "   "])
    def test_degenerate_zero(self, bullet):
        assert tpi.score_bullet_complexity(bullet) == 0.0

    def test_simple_bullet_low(self):
        assert tpi.score_bullet_complexity("He said that he would go to work.") < 0.3

    def test_jargon_bullet_higher_than_simple(self):
        simple = "He said that he would go to work."
        complex_ = (
            "Organizational stakeholders leverage multifaceted paradigms "
            "for synergistic optimization initiatives across departments."
        )
        assert tpi.score_bullet_complexity(complex_) > tpi.score_bullet_complexity(simple)

    def test_passive_voice_adds_weight(self):
        active = "The committee reviewed the document carefully before it started."
        passive = "The document was reviewed by the committee before implementation."
        assert tpi.score_bullet_complexity(passive) > tpi.score_bullet_complexity(active)


class TestVocabularyOverlapScore:
    def test_empty_is_one(self):
        assert tpi.vocabulary_overlap_score("") == 1.0

    def test_all_common(self):
        assert tpi.vocabulary_overlap_score("You can see the way out if you look.") == 1.0

    def test_partial(self):
        # 3 of 9 words common ("the", "over", "the") → 1/3.
        assert tpi.vocabulary_overlap_score(
            "The quick brown fox jumps over the lazy dog"
        ) == pytest.approx(1 / 3)


class TestShouldSkipSimplification:
    def test_too_short(self):
        assert tpi.should_skip_simplification("hi") == (True, "too short")
        assert tpi.should_skip_simplification("") == (True, "too short")

    def test_already_plain(self):
        skip, reason = tpi.should_skip_simplification("You can see the way out if you look.")
        assert skip is True
        assert "already plain" in reason

    def test_low_complexity(self):
        skip, reason = tpi.should_skip_simplification("He said that he would go to work.")
        assert skip is True
        assert "low complexity" in reason

    def test_needs_simplification(self):
        skip, reason = tpi.should_skip_simplification(
            "Organizational stakeholders leverage multifaceted paradigms for synergistic optimization."
        )
        assert skip is False
        assert "needs simplification" in reason


# ═══════════════════════════════════════════════════════════════════════════
# I1: extract_named_entities + spaCy plumbing
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractNamedEntities:
    def test_regex_fallback_persons(self):
        text = "Dr. Elena Vega arrived. Professor Marcus Webb spoke. Marcus said hello."
        out = tpi.extract_named_entities(text)
        assert "Elena Vega" in out["persons"]
        assert "Marcus Webb" in out["persons"]
        assert "Marcus" in out["persons"]

    def test_regex_fallback_organizations(self):
        text = 'She worked for a company called Acme Industries. "Northwind" firm was there.'
        out = tpi.extract_named_entities(text)
        assert "Acme Industries" in out["organizations"]
        assert "Northwind" in out["organizations"]

    def test_regex_fallback_locations(self):
        text = "He traveled to Lisbon, Portugal and later went to Copenhagen."
        out = tpi.extract_named_entities(text)
        assert "Lisbon" in out["locations"]
        assert "Copenhagen" in out["locations"]

    def test_location_suffix_filter(self):
        # Locations ending in -ing/-ed/-ly/-tion are rejected (verb/noun fragments).
        text = "They walked to Building during morning."
        out = tpi.extract_named_entities(text)
        assert "Building" not in out["locations"]

    def test_exclude_list_respected(self):
        text = "It happened in Monday near Winter according to Chapter notes."
        out = tpi.extract_named_entities(text)
        assert out["locations"] == []

    def test_spacy_model_used_when_available(self, monkeypatch):
        class _Ent:
            def __init__(self, text_, label):
                self.text = text_
                self.label_ = label

        class _Doc:
            ents = [_Ent("Barack Obama", "PERSON"), _Ent("Acme Corp", "ORG"), _Ent("Paris", "GPE")]

        import core.llm.model_singletons as ms

        seen = {}

        def fake_nlp(text_):
            seen["len"] = len(text_)
            return _Doc()

        monkeypatch.setattr(ms, "get_spacy_nlp", lambda name="en_core_web_sm": fake_nlp)
        out = tpi.extract_named_entities("Filler " * 20000)
        assert out == {
            "persons": ["Barack Obama"],
            "organizations": ["Acme Corp"],
            "locations": ["Paris"],
        }
        # Text is truncated to 50000 chars before spaCy sees it.
        assert seen["len"] == 50000

    def test_spacy_import_error_falls_back(self, monkeypatch):
        import core.llm.model_singletons as ms

        def boom(name="en_core_web_sm"):
            raise ImportError("no spacy")

        monkeypatch.setattr(ms, "get_spacy_nlp", boom)
        out = tpi.extract_named_entities("Marcus said hello to Dr. Elena Vega.")
        assert "Marcus" in out["persons"]

    def test_spacy_generic_error_falls_back(self, monkeypatch):
        import core.llm.model_singletons as ms

        def boom(name="en_core_web_sm"):
            raise RuntimeError("spacy exploded")

        monkeypatch.setattr(ms, "get_spacy_nlp", boom)
        out = tpi.extract_named_entities("Marcus said hello to Dr. Elena Vega.")
        assert "Marcus" in out["persons"]


class TestLoadSpacyModel:
    def test_cached_model_returned(self, monkeypatch):
        sentinel = object()
        runtime_state.spacy_nlp = sentinel
        runtime_state.spacy_lang = "en"
        assert tpi._load_spacy_model("en") is sentinel

    def test_load_sets_state(self, monkeypatch):
        import core.llm.model_singletons as ms

        fake = object()
        runtime_state.spacy_nlp = None
        runtime_state.spacy_lang = None
        monkeypatch.setattr(ms, "get_spacy_nlp", lambda name: fake)
        assert tpi._load_spacy_model("fa") is fake
        assert runtime_state.spacy_nlp is fake
        assert runtime_state.spacy_lang == "fa"

    def test_unknown_language_defaults_to_english(self, monkeypatch):
        import core.llm.model_singletons as ms

        seen = {}
        runtime_state.spacy_nlp = None
        runtime_state.spacy_lang = None

        def fake(name):
            seen["name"] = name
            return None

        monkeypatch.setattr(ms, "get_spacy_nlp", fake)
        assert tpi._load_spacy_model("xx") is None
        assert seen["name"] == "en_core_web_sm"

    def test_reload_on_language_change(self, monkeypatch):
        import core.llm.model_singletons as ms

        first, second = object(), object()
        runtime_state.spacy_nlp = first
        runtime_state.spacy_lang = "en"
        monkeypatch.setattr(ms, "get_spacy_nlp", lambda name: second)
        assert tpi._load_spacy_model("de") is second


class TestGetAllNerEntities:
    def test_flattens_words(self, monkeypatch):
        monkeypatch.setattr(
            tpi,
            "extract_named_entities",
            lambda text: {"persons": ["Elena Vega"], "organizations": [], "locations": ["Lisbon"]},
        )
        assert tpi.get_all_ner_entities("anything") == {"Elena Vega", "Elena", "Vega", "Lisbon"}


# ═══════════════════════════════════════════════════════════════════════════
# J1: bullet similarity + topic ordering
# ═══════════════════════════════════════════════════════════════════════════


class TestOrderBulletsByTopic:
    def test_short_lists_unchanged(self):
        assert tpi.order_bullets_by_topic([]) == []
        assert tpi.order_bullets_by_topic(["only one"]) == ["only one"]
        assert tpi.order_bullets_by_topic(["a", "b"]) == ["a", "b"]

    def test_similarity(self):
        assert tpi._bullet_similarity("", "x") == 0.0
        assert tpi._bullet_similarity("a b", "a b") == 1.0
        assert 0.0 < tpi._bullet_similarity("a b c", "a b d") < 1.0

    def test_greedy_clustering_groups_related(self):
        bullets = [
            "cats love warm sleeping spots and sunny windows",
            "quantum physics describes subatomic particle behaviour",
            "cats sleep most of the day in warm spots",
            "physics experiments measure subatomic particle states",
        ]
        out = tpi.order_bullets_by_topic(bullets)
        # The most similar bullet to bullets[0] must come second.
        assert out[0] == bullets[0]
        assert out[1] == bullets[2]


# ═══════════════════════════════════════════════════════════════════════════
# F1: summary length validation / truncation
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateSummaryLength:
    def test_empty(self):
        assert tpi.validate_summary_length("") == (False, 0, "summary: empty")

    def test_too_short(self):
        ok, count, msg = tpi.validate_summary_length(" ".join(["w"] * 50))
        assert ok is False and count == 50 and "too short" in msg

    def test_ok(self):
        ok, count, msg = tpi.validate_summary_length(" ".join(["w"] * 200))
        assert ok is True and count == 200 and "OK" in msg

    def test_too_long(self):
        ok, count, msg = tpi.validate_summary_length(" ".join(["w"] * 2000))
        assert ok is False and "too long" in msg

    def test_custom_section_label(self):
        _, _, msg = tpi.validate_summary_length("", section="exec")
        assert msg == "exec: empty"


class TestTruncateSummary:
    def test_empty(self):
        assert tpi.truncate_summary("", 5) == ""

    def test_within_limit_unchanged(self):
        text = "one two three"
        assert tpi.truncate_summary(text, 5) == text

    def test_truncates_at_sentence_boundary(self):
        assert tpi.truncate_summary("one two three four. five six", 4) == "one two three four."

    def test_truncates_with_ellipsis_when_no_boundary(self):
        out = tpi.truncate_summary("one two three four five six seven", 4)
        assert out == "one two three four…"


# ═══════════════════════════════════════════════════════════════════════════
# F4 + K1: source overlap + bullet confidence
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeSourceOverlap:
    def test_empty_inputs_zero(self):
        assert tpi.compute_source_overlap("", "src") == 0.0
        assert tpi.compute_source_overlap("bullet", "") == 0.0

    def test_no_content_words_returns_one(self):
        # Only short/common words → nothing to verify → 1.0.
        assert tpi.compute_source_overlap("the and but", "unrelated") == 1.0

    def test_exact_ratio(self):
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        # 5 content words, 4 present ("today" missing) → 0.8.
        bullet = "The quick brown fox jumps over the lazy dog near the riverbank today."
        assert tpi.compute_source_overlap(bullet, src) == pytest.approx(0.8)


class TestComputeBulletConfidence:
    def test_empty_bullet_zero(self):
        assert tpi.compute_bullet_confidence("", "src") == 0

    def test_exact_score_composition(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        bullet = "The quick brown fox jumps over the lazy dog near the riverbank today."
        # overlap 0.8 → +40; no concepts; no thinking markers +10; 13 words +10;
        # capital + period +5; no NER entities +5 → 70.
        assert tpi.compute_bullet_confidence(bullet, src) == 70

    def test_concept_bonus(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        no_concept = tpi.compute_bullet_confidence(
            "The quick brown fox jumps over the lazy dog near the riverbank today.", src
        )
        with_concept = tpi.compute_bullet_confidence(
            "The quick brown fox jumps over the lazy dog near the riverbank today.",
            src,
            concepts=["riverbank"],
        )
        assert with_concept - no_concept == 20

    def test_thinking_marker_penalised(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        clean = tpi.compute_bullet_confidence(
            "The quick brown fox jumps over the lazy dog near the riverbank today.", src
        )
        dirty = tpi.compute_bullet_confidence(
            "Analyze this: The quick brown fox jumps over the lazy dog near riverbank.", src
        )
        assert dirty < clean

    def test_ner_exception_gives_benefit_of_doubt(self, monkeypatch):
        def boom(_):
            raise RuntimeError("ner down")

        monkeypatch.setattr(tpi, "get_all_ner_entities", boom)
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        bullet = "The quick brown fox jumps over the lazy dog near the riverbank today."
        assert tpi.compute_bullet_confidence(bullet, src) == 70  # +5 despite NER failure

    def test_cap_at_hundred(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        bullet = "The quick brown fox jumps over the lazy dog near the riverbank today."
        score = tpi.compute_bullet_confidence(bullet, src, concepts=["riverbank", "fox"])
        assert score <= 100


# ═══════════════════════════════════════════════════════════════════════════
# K2 + H2: source excerpt + page traceability
# ═══════════════════════════════════════════════════════════════════════════


class TestFindSourceExcerpt:
    def test_empty_inputs_none(self):
        assert tpi.find_source_excerpt("", "src") is None
        assert tpi.find_source_excerpt("bullet", "") is None

    def test_no_content_words_none(self):
        assert tpi.find_source_excerpt("ab cd", "Some longer source sentence with words.") is None

    def test_best_match_returned(self):
        src = "The quick brown fox jumps over the lazy dog near the riverbank."
        assert tpi.find_source_excerpt("quick brown riverbank", src) == src

    def test_low_overlap_none(self):
        src = "Completely unrelated words about gardening and plants today."
        assert tpi.find_source_excerpt("quantum entanglement physics", src) is None

    def test_truncation_with_good_break(self):
        long_src = (
            "This sentence talks about the medieval castle and its fortifications. "
            + "Filler sentence with nothing relevant at all in it here. " * 3
            + "The medieval castle stood on the hill overlooking the village below."
        )
        out = tpi.find_source_excerpt(
            "medieval castle fortifications hill", long_src, max_length=40
        )
        assert out is not None
        assert out.endswith("…")
        assert len(out) <= 41

    def test_short_sentences_skipped(self):
        src = "Tiny. The relevant sentence with the matching words appears right here now today."
        assert tpi.find_source_excerpt("matching words appears", src).startswith("The relevant")


class TestFindSourcePage:
    def test_no_markers_none(self):
        assert (
            tpi.find_source_page("quick brown", "The quick brown fox.", page_markers=None) is None
        )

    def test_no_excerpt_none(self):
        assert (
            tpi.find_source_page("zzzz qqqq", "The quick brown fox.", page_markers=[(0, 1)]) is None
        )

    def test_marker_before_excerpt(self):
        src = "The quick brown fox jumps over the lazy dog."
        assert (
            tpi.find_source_page("quick brown", src, page_markers=[(0, 1), (10, 2), (30, 3)]) == 1
        )

    def test_single_marker(self):
        src = "The quick brown fox jumps over the lazy dog."
        assert tpi.find_source_page("quick brown", src, page_markers=[(0, 5)]) == 5

    def test_unsorted_markers(self):
        src = "The quick brown fox jumps over the lazy dog."
        assert (
            tpi.find_source_page("quick brown", src, page_markers=[(30, 3), (0, 1), (10, 2)]) == 1
        )


# ═══════════════════════════════════════════════════════════════════════════
# F3: reading level
# ═══════════════════════════════════════════════════════════════════════════


class TestReadingLevel:
    def test_count_syllables(self):
        assert tpi.count_syllables("") == 0
        assert tpi.count_syllables("cat") == 1
        assert tpi.count_syllables("table") == 1  # silent 'e'
        assert tpi.count_syllables("education") == 4
        assert tpi.count_syllables("queue") == 1

    def test_flesch_kincaid_short_text_zero(self):
        assert tpi.flesch_kincaid_grade("") == 0.0
        assert tpi.flesch_kincaid_grade("short text here") == 0.0

    def test_flesch_kincaid_nonnegative(self):
        simple = "The cat sat on the mat. The dog ran to the ball."
        assert tpi.flesch_kincaid_grade(simple) >= 0.0

    def test_assess_reading_level_keys(self):
        out = tpi.assess_reading_level(
            "The extraordinarily complicated terminology demonstrates considerable institutional obstructionism throughout.",
            "The cat sat on the mat.",
        )
        assert set(out) == {
            "source_grade",
            "summary_grade",
            "difference",
            "summary_is_simpler",
            "meets_threshold",
        }
        assert out["summary_is_simpler"] is True  # summary (2nd arg) is the easy text
        assert out["meets_threshold"] is True


# ═══════════════════════════════════════════════════════════════════════════
# I2: chapter difficulty
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreChapterDifficulty:
    def test_short_text_single_pass(self):
        assert tpi.score_chapter_difficulty("short") == {"score": 0.0, "strategy": "single_pass"}

    def test_simple_text_low_score(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        out = tpi.score_chapter_difficulty("Simple words are here. " * 30)
        assert out["score"] < 0.4
        assert out["strategy"] == "single_pass"
        assert set(out) == {
            "score",
            "vocab_diversity",
            "avg_sentence_length",
            "tech_density",
            "ner_density",
            "grade_level",
            "strategy",
        }

    def test_ner_exception_zero_density(self, monkeypatch):
        def boom(_):
            raise RuntimeError("ner down")

        monkeypatch.setattr(tpi, "get_all_ner_entities", boom)
        out = tpi.score_chapter_difficulty("Simple words are here. " * 30)
        assert out["ner_density"] == 0.0

    def test_hard_technical_text_uses_heavier_strategy(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        hard = (
            "The heterogeneous infrastructure virtualization orchestration platform "
            "fundamentally restructures distributed transactional paradigms. "
        ) * 20
        out = tpi.score_chapter_difficulty(hard)
        assert out["strategy"] in ("multi_sample", "section_map_reduce")
        assert out["score"] > 0.4


# ═══════════════════════════════════════════════════════════════════════════
# J2: cross-section redundancy
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckCrossSectionRedundancy:
    def test_no_rapidfuzz_returns_empty_findings(self, monkeypatch):
        # sys.modules[...] = None makes `from rapidfuzz import fuzz` raise ImportError.
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        out = tpi.check_cross_section_redundancy(
            "The system uses caching to improve latency dramatically.",
            ["The system uses caching to improve latency dramatically."],
            "The system uses caching to improve latency dramatically.",
        )
        assert out == {
            "exec_vs_bullets_redundant": [],
            "bullets_vs_thorough_redundant": [],
            "exec_vs_thorough_redundant": [],
            "total_redundant": 0,
        }

    def test_duplicates_detected(self):
        dup = "The system uses caching to improve latency dramatically."
        out = tpi.check_cross_section_redundancy(
            dup, [dup, "Unrelated content about garden plants here."], dup + " Extra words follow."
        )
        assert out["exec_vs_bullets_redundant"][0]["bullet_index"] == 0
        assert out["bullets_vs_thorough_redundant"][0]["bullet_index"] == 0
        assert out["exec_vs_thorough_redundant"][0]["similarity"] > 80
        assert out["total_redundant"] == 3

    def test_no_redundancy(self):
        out = tpi.check_cross_section_redundancy(
            "Cats sleep in warm sunny places.",
            ["Quantum physics is complicated stuff."],
            "Gardening requires patience and water.",
        )
        assert out["total_redundant"] == 0

    def test_empty_sections(self):
        out = tpi.check_cross_section_redundancy("", [], "")
        assert out["total_redundant"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# J3: exec summary coherence
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckExecSummaryCoherence:
    def test_too_short(self):
        assert tpi.check_exec_summary_coherence("short") == {
            "coherent": False,
            "score": 0,
            "reason": "too short",
        }

    def test_coherent_summary(self):
        text = (
            "However, this chapter covers the topic in great detail and depth. "
            "Furthermore, the author develops the argument with many examples. "
            "Ultimately the chapter concludes with practical advice for readers."
        )
        out = tpi.check_exec_summary_coherence(text)
        assert out["coherent"] is True
        assert out["score"] == 100
        assert out["has_topic_sentence"] is True
        assert out["has_conclusion"] is True
        assert out["is_narrative"] is True
        assert out["discourse_markers"] >= 2
        assert "however" in out["markers_found"]

    def test_plain_text_lower_score(self):
        text = "Words appear in this. More words follow here. The end comes."
        out = tpi.check_exec_summary_coherence(text)
        assert out["coherent"] is False
        assert out["discourse_markers"] == 0
        assert out["has_topic_sentence"] is False
        assert out["has_conclusion"] is False

    def test_list_is_not_narrative(self):
        text = (
            "- However, this first bullet is a list item with enough length.\n"
            "- Furthermore, the second bullet continues the list format now."
        )
        out = tpi.check_exec_summary_coherence(text)
        assert out["is_narrative"] is False


# ═══════════════════════════════════════════════════════════════════════════
# V3.6.0: classify_bullet
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyBullet:
    def test_empty_additional(self):
        assert tpi.classify_bullet("") == "additional"

    def test_concept_plus_core(self):
        assert (
            tpi.classify_bullet("The concept of focus refers to attention.", concepts=["focus"])
            == "core"
        )

    def test_core_indicator_without_supporting(self):
        assert tpi.classify_bullet("X is defined as Y.") == "core"

    def test_supporting_example(self):
        assert tpi.classify_bullet("For example, in 2020 sales rose 20%.") == "supporting"

    def test_concept_without_core_indicator_is_core(self):
        assert (
            tpi.classify_bullet("Mentions the focus topic briefly.", concepts=["focus"]) == "core"
        )

    def test_neutral_additional(self):
        assert tpi.classify_bullet("Some random neutral statement about things.") == "additional"

    def test_core_beats_supporting(self):
        # has_core and not has_supporting → core.
        assert tpi.classify_bullet("You should Establish a routine for success.") == "core"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.2: semantic_fact_check (embedder mocked / absent)
# ═══════════════════════════════════════════════════════════════════════════


class _FakeEmbedModel:
    """Deterministic embedder: direction depends on keyword presence."""

    def encode(self, texts, convert_to_numpy=True):
        vecs = []
        for t in texts:
            low = t.lower()
            if "quantum" in low:
                v = np.array([1.0, 0.0, 0.0])
            elif "gravity" in low:
                v = np.array([0.0, 1.0, 0.0])
            else:
                v = np.array([0.0, 0.0, 1.0])
            vecs.append(v)
        return np.array(vecs)


class TestSemanticFactCheck:
    SRC = (
        "Gravity pulls objects toward the earth surface area. "
        "Quantum entanglement links particles across distance and time."
    )

    def test_embed_model_unavailable_fails_closed(self, monkeypatch):
        runtime_state.warned_no_embed_model = False
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: None)
        out = tpi.semantic_fact_check("anything at all", self.SRC)
        assert out == {
            "is_grounded": False,
            "best_similarity": 0.0,
            "best_source_sentence": "",
            "reason": "embed_model_unavailable",
        }
        # The one-time warning flag is latched.
        assert runtime_state.warned_no_embed_model is True

    def test_warning_emitted_once(self, monkeypatch, caplog):
        runtime_state.warned_no_embed_model = False
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: None)
        with caplog.at_level("WARNING", logger="core.summarisation.text_preprocessor_impl"):
            tpi.semantic_fact_check("first call", self.SRC)
            tpi.semantic_fact_check("second call", self.SRC)
        warns = [r for r in caplog.records if "embed model unavailable" in r.message]
        assert len(warns) == 1

    def test_empty_input_fails_closed(self, monkeypatch):
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: _FakeEmbedModel())
        out = tpi.semantic_fact_check("", self.SRC)
        assert out["reason"] == "empty_input"
        assert out["is_grounded"] is False

    def test_no_source_sentences_fails_closed(self, monkeypatch):
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: _FakeEmbedModel())
        out = tpi.semantic_fact_check("some bullet text", "short only")
        assert out["reason"] == "no_source_sentences"

    def test_grounded_bullet_passes(self, monkeypatch):
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: _FakeEmbedModel())
        out = tpi.semantic_fact_check("quantum entanglement links particles", self.SRC)
        assert out["is_grounded"] is True
        assert out["best_similarity"] == pytest.approx(1.0)
        assert "Quantum entanglement" in out["best_source_sentence"]

    def test_threshold_controls_verdict(self, monkeypatch):
        monkeypatch.setattr(tpi, "_get_embed_model", lambda: _FakeEmbedModel())
        out = tpi.semantic_fact_check(
            "gravity pulls objects",
            "Gravity pulls objects downward. Filler sentence here.",
            threshold=1.01,
        )
        assert out["is_grounded"] is False

    def test_embedding_error_fails_closed(self, monkeypatch):
        class Boom:
            def encode(self, *a, **k):
                raise RuntimeError("boom")

        monkeypatch.setattr(tpi, "_get_embed_model", lambda: Boom())
        out = tpi.semantic_fact_check("hello world stuff", self.SRC)
        assert out["reason"] == "embedding_error"
        assert out["error"] == "boom"
        assert out["is_grounded"] is False


class TestGetEmbedModel:
    def test_exception_returns_none(self, monkeypatch):
        import core.llm.model_singletons as ms

        def boom():
            raise RuntimeError("no embedder")

        monkeypatch.setattr(ms, "get_embed_model", boom)
        assert tpi._get_embed_model() is None


class TestGapClosingValidation:
    """Second-wave branch coverage for the validation/scoring family."""

    def test_ocr_quality_spaces_only_zero(self):
        # ≥20 chars but no words at all → 0.0.
        assert tpi.score_ocr_quality(" " * 25) == 0.0

    def test_complexity_whitespace_only_zero(self):
        # ≥10 chars but zero words after split → 0.0.
        assert tpi.score_bullet_complexity(" " * 12) == 0.0

    def test_vocab_overlap_whitespace_only_one(self):
        assert tpi.vocabulary_overlap_score("   ") == 1.0

    def test_confidence_overlap_band_full(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "alpha bravo charlie delta foxtrot"
        bullet = "Alpha bravo charlie delta foxtrot."
        # overlap 1.0 → +50; no thinking +10; 5 words → +5 (5-45 band);
        # capital + period +5; no NER +5 → 75.
        assert tpi.compute_bullet_confidence(bullet, src) == 75

    def test_confidence_overlap_band_sixty(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "alpha bravo charlie delta foxtrot"
        bullet = "Alpha bravo charlie zebra yakxx."
        # content words (5+ chars): alpha bravo charlie zebra yakxx → 3/5 = 0.6
        # → +30; +10 +5 +5 +5 → 55.
        assert tpi.compute_bullet_confidence(bullet, src) == 55

    def test_confidence_overlap_band_forty(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        src = "alpha bravo charlie delta foxtrot"
        bullet = "Alpha bravo zebra yakxx quxxq."
        # 2/5 = 0.4 → +15; +10 +5 +5 +5 → 40.
        assert tpi.compute_bullet_confidence(bullet, src) == 40

    def test_find_source_excerpt_skips_wordless_sentence(self):
        src = "1 22 333 4444 55555 666666 7777777! The relevant words appear right here now."
        out = tpi.find_source_excerpt("relevant words appear", src)
        assert out is not None
        assert out.startswith("The relevant")

    def test_find_source_excerpt_hard_cut_truncation(self):
        # One very long word: no good break point within max_length → hard cut.
        src = "This " + "x" * 100 + ". Unrelated filler sentence with other words here."
        out = tpi.find_source_excerpt("this xxxxxxxxxxxx", src, max_length=40)
        assert out == "This " + "x" * 35 + "…"  # early space → hard cut, no word break

    def test_chapter_difficulty_very_hard_text(self, monkeypatch):
        monkeypatch.setattr(tpi, "get_all_ner_entities", lambda text: set())
        letters = "abcdefghij"
        words = [f"technicalterma{letters[i // 5]}{letters[i % 5]}" for i in range(40)]
        text = " ".join(words) + "."
        out = tpi.score_chapter_difficulty(text)
        assert out["strategy"] == "section_map_reduce"
        assert out["score"] > 0.6

    def test_exec_coherence_single_marker(self):
        text = (
            "However, this chapter covers its main topic in real detail here. "
            "The body continues with supporting evidence for the claims made. "
            "A short concluding sentence then wraps it all up nicely."
        )
        out = tpi.check_exec_summary_coherence(text)
        assert out["discourse_markers"] == 1
        # 15 (one marker) + 25 (topic) + 25 (conclusion) + 20 (narrative) = 85
        assert out["score"] == 85
        assert out["coherent"] is True
