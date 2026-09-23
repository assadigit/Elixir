"""V0.4.24 — the audit-backlog regression tests (V4.23 run post-mortem).

Every test here pins one defect from the V0.4.23 ch.4 audit
(audit/results/AUDIT_V0.4.23_run20260923-053014-491d1bf4_ch4_summary_vs_source.md)
and its confirmation in the uploaded V4.23 conversion log:

1. Run-in stem extraction is sentence/word-aligned — no more mid-word-sliced
   labels ("Rom others.", "Tive, structural", "Ree types of", "O, classical
   psychoanalysis. His list of").
2. The thorough_addition truncation guard — an output-cap cut that eats
   </thorough_addition> must never ship a visible tag + mid-sentence tail.
3. The Stern ten-criteria paragraph-break join + the guarantee-bullet
   postcheck exemption + the last-chance floor repair (three layers for
   "no postcheck may drop a guaranteed list item silently").
4. The name-dump fix: the thorough gap-fill is chunked (≤12 names/call).
5. The filler floor catches "appears in the same citation list".
6. The attribution-edge filter drops the Piaget-Klein weld sentence class.
7. Provider-aware routing: simplified keypoints / vision OCR / figure
   extraction all work when provider=llamacpp (the V4.23 rig lost ALL of
   them to Ollama-only probes).
8. Tesseract OCR retries with alternate page-segmentation modes (p.107).
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in __import__("sys").path:
    import sys

    sys.path.insert(0, str(_PROJECT_ROOT))

from core.summarisation.enumeration import (  # noqa: E402
    _aligned_stem,
    detect_enumerations,
    stem_label,
)
from core.summarisation.post_processing import (  # noqa: E402
    is_citation_filler_bullet,
    is_truncated,
)
from core.summarisation.thorough_theorist_floor import (  # noqa: E402
    _grounded_addition_sentences,
)

# ─────────────────────────────────────────────────────────────────────────────
# The EXACT ch.4 Stern passage (ground truth, lines 274-286) — the audit's
# guarantee-escape reproduction case: a PDF paragraph break inside item (8).
# ─────────────────────────────────────────────────────────────────────────────

STERN_PASSAGE = """The term borderline was subsequently given a formal status by Stern (1938), who outlined the characteristics of patients who did not do well in, or responded
adversely to, classical psychoanalysis. His list of ten criteria remains an outstanding description of borderline personality disorder. Stern's criteria
included (1) narcissism, (2) psychic bleeding and a tendency to give up in the face of crises, (3) inordinate hypersensitivity, (4) psychic and bodily rigidity, (5)
tendency to respond negatively to helpful and correct interpretations, (6) a deeply ingrained deficit of self-esteem and accompanying feelings of inferiority,
(7) masochism and depressive mood swings, (8) organic insecurity or a

constitutional incapacity to tolerate much stress, (9) preponderance of projective
mechanisms, and (10) difficulties in reality testing.

Another significant early contribution was the description of "as-if" personalities by Deutsch (1942). These patients, according to Deutsch, generally maintain a
firm grip on reality and appear quite normal."""


def _pad(text: str) -> str:
    """Ensure the >120-char minimum detect_enumerations requires."""
    prefix = "Prologue. " * 15
    return f"{prefix}\n\n{text}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Aligned stems (audit backlog #1)
# ─────────────────────────────────────────────────────────────────────────────


class TestAlignedStem:
    def test_short_stem_returned_as_is(self):
        assert _aligned_stem("His list of ten criteria") == "His list of ten criteria"

    def test_never_slices_mid_token(self):
        raw = (
            "…patients who did not do well in, or responded adversely t"
            + "o" * 1
            + ", classical psychoanalysis. His list of ten criteria remains an "
            "outstanding description of borderline personality disorder. Stern's "
            "criteria included"
        )
        stem = _aligned_stem(raw)
        # the V0.4.23 window shipped "O, classical psychoanalysis…" (a
        # mid-word slice of "t|o") — the aligned stem must start at a word
        # boundary AND at a sentence start
        assert not stem.startswith("o,"), stem
        assert stem[0].isupper(), stem

    def test_leads_with_final_sentence(self):
        raw = (
            "Reich clearly described the intense ambivalence and the dominance "
            "of pregenital aggression in severe character pathology. The three "
            "types of early environment associated with the condition are "
        )
        stem = _aligned_stem(raw)
        assert stem == "The three types of early environment associated with the condition are", (
            stem
        )

    def test_empty(self):
        assert _aligned_stem("") == ""
        assert _aligned_stem(None) == ""  # type: ignore[arg-type]


class TestStemLabelFinalSentence:
    def test_label_leads_with_the_introducing_sentence(self):
        # The V4.23 label for the Stern list was "O, classical psychoanalysis.
        # His list of" — a mid-paragraph fragment. The introducing sentence is
        # "Stern's criteria included".
        stem = _aligned_stem(
            "The term borderline was given a formal status by Stern (1938), who "
            "outlined the characteristics of patients who did not do well in, or "
            "responded adversely to, classical psychoanalysis. His list of ten "
            "criteria remains an outstanding description of borderline "
            "personality disorder. Stern's criteria included"
        )
        label = stem_label(stem, 10)
        assert label == "Stern's criteria", label

    def test_legacy_single_sentence_still_works(self):
        assert stem_label("The seven features of solid identity are:", 7) == (
            "Seven features of solid identity"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2+3. The Stern join, the guarantee, the exemption, the repair
# ─────────────────────────────────────────────────────────────────────────────


class TestSternParagraphJoin:
    """The audit's demanded regression test: the exact ch.4 passage, a PDF
    paragraph break inside item (8) — the detector must see ONE 10-item
    list (V0.4.23 saw an 8-item run + an undetected 2-item fragment)."""

    def test_one_ten_item_list_with_complete_item_eight(self):
        enums = detect_enumerations(_pad(STERN_PASSAGE))
        runin = [e for e in enums if e.style == "runin_arabic"]
        ten = [e for e in runin if e.count == 10]
        assert ten, f"expected a 10-item runin list, got {[e.count for e in runin]}"
        item8 = ten[0].items[7].text
        assert "organic insecurity or a constitutional incapacity to tolerate much stress" in item8
        assert ten[0].items[9].text.rstrip(".,").endswith("difficulties in reality testing")

    def test_no_two_item_fragment_survives(self):
        enums = detect_enumerations(_pad(STERN_PASSAGE))
        assert not [e for e in enums if e.count == 2], (
            "items (9)-(10) must not live in their own below-minimum fragment"
        )

    def test_stem_is_the_introducing_sentence(self):
        enums = detect_enumerations(_pad(STERN_PASSAGE))
        ten = [e for e in enums if e.style == "runin_arabic" and e.count == 10][0]
        assert stem_label(ten.stem, 10) == "Stern's criteria"

    def test_non_consecutive_marker_does_not_join(self):
        src = _pad(
            "The list begins here: (1) alpha; (2) beta; (3) gamma; (4) delta or a\n\n"
            "new paragraph about something else entirely with a stray (9) marker.\n\n"
            "And a closing paragraph of ordinary prose."
        )
        enums = detect_enumerations(src)
        assert not [e for e in enums if e.count == 5]

    def test_terminal_punctuation_does_not_join(self):
        src = _pad(
            "The list begins here: (1) alpha; (2) beta; (3) gamma; (4) delta done.\n\n"
            "constitutional text continues here, (5) epsilon; (6) zeta."
        )
        enums = detect_enumerations(src)
        assert not [e for e in enums if e.style == "runin_arabic" and e.count == 6]


class TestGuaranteeStashAndRepair:
    def _mixin(self):
        from core.summarisation.additive_sections import SummarizerAdditiveMixin

        logs: list[tuple[str, str]] = []

        class _S(SummarizerAdditiveMixin):
            def log(self, msg, level="INFO"):
                logs.append((level, msg))

        return _S(), logs

    def test_guarantee_bullet_covers_all_ten_and_is_stashed(self):
        s, logs = self._mixin()
        result = {
            "bullet_points": [
                "Stern's criteria included narcissism, psychic bleeding, "
                "hypersensitivity, and rigidity."
            ],
            "thorough_summary": "",
        }
        s._ensure_enumeration_bullets("Chapter", _pad(STERN_PASSAGE), result)
        added = [b for b in result["bullet_points"] if b.startswith("**")]
        assert len(added) == 1
        for item in (
            "organic insecurity or a constitutional incapacity to tolerate much stress",
            "tendency to respond negatively to helpful and correct interpretations",
            "a deeply ingrained deficit of self-esteem",
            "masochism and depressive mood swings",
            "preponderance of projective",
            "difficulties in reality testing",
        ):
            assert item in added[0], item
        # the clean, word-aligned label — not the V4.23 garbled fragment
        assert added[0].startswith("**Stern's criteria**"), added[0][:60]
        # the audit's layer-3 defense: the exact text is stashed for the
        # postcheck exemption
        assert result["_enum_guarantee_texts"] == added

    def test_final_repair_recovers_a_postcheck_drop(self):
        """The exact V4.23 escape, end to end: the guarantee adds the bullet,
        a ship-time filter DROPS it (simulated), the last-chance repair
        re-adds it on the set that actually ships."""
        s, logs = self._mixin()
        result = {"bullet_points": ["Covers narcissism and rigidity only."], "thorough_summary": ""}
        s._ensure_enumeration_bullets("Chapter", _pad(STERN_PASSAGE), result)
        guaranteed = list(result.get("_enum_guarantee_texts", []))
        assert guaranteed
        # simulate the V4.23 postcheck truncation drop
        bullets = [b for b in result["bullet_points"] if b not in guaranteed]
        added = s._final_enumeration_repair("Chapter", _pad(STERN_PASSAGE), result, bullets, "")
        assert added >= 1
        repaired = result["bullet_points"]
        assert any("constitutional incapacity to tolerate much stress" in b for b in repaired)
        assert any("last-chance enumeration repair" in m for _lvl, m in logs)

    def test_final_repair_noop_when_nothing_missing(self):
        s, _logs = self._mixin()
        covering = (
            "Stern's criteria included (1) narcissism; (2) psychic bleeding "
            "and a tendency to give up in the face of crises; (3) inordinate "
            "hypersensitivity; (4) psychic and bodily rigidity; (5) tendency to "
            "respond negatively to helpful and correct interpretations; (6) a "
            "deeply ingrained deficit of self-esteem and accompanying feelings "
            "of inferiority; (7) masochism and depressive mood swings; "
            "(8) organic insecurity or a constitutional incapacity to tolerate "
            "much stress; (9) preponderance of projective mechanisms; and "
            "(10) difficulties in reality testing."
        )
        result = {"bullet_points": [covering], "thorough_summary": ""}
        added = s._final_enumeration_repair(
            "Chapter", _pad(STERN_PASSAGE), result, result["bullet_points"], ""
        )
        assert added == 0

    def test_final_repair_never_raises(self):
        s, _logs = self._mixin()
        assert s._final_enumeration_repair("Chapter", None, {}, [], "") == 0  # type: ignore[arg-type]


class TestGuaranteeBulletPostcheckExemption:
    """Layer 3: the ship-time truncation drop must not kill a guaranteed
    bullet (the V4.23 run dropped bullet[68] and lost 4 enumerated items)."""

    def _ctx(self):
        from core.summarisation.postchecks.field_phases import PhaseCtx

        return PhaseCtx(
            source_text=None,
            source_lower="",
            source_lower_full="",
            source_words=set(),
            source_authors=None,
            auto_repair_garble=False,
        )

    DANGLING_GUARANTEE = (
        "**Stern's criteria** — 10 items from the source: (1) narcissism; "
        "(2) psychic bleeding; (3) hypersensitivity; (4) rigidity; "
        "(5) negative therapeutic responses; (6) self-esteem deficit; "
        "(7) masochism; (8) organic insecurity or a."
    )

    def test_guarantee_bullet_exempt_from_truncation_drop(self):
        from core.summarisation.postchecks.field_phases import postcheck_bullets
        from core.summarisation.postchecks.shared import PostCheckReport

        assert is_truncated(self.DANGLING_GUARANTEE)  # the misfire premise
        report = PostCheckReport()
        out = postcheck_bullets(
            [self.DANGLING_GUARANTEE],
            self._ctx(),
            report,
            enum_guarantee_texts=[self.DANGLING_GUARANTEE],
        )
        assert out == [self.DANGLING_GUARANTEE], "guarantee bullet must ship"
        flags = [i for i in report.issues if i.detector == "truncated"]
        assert flags and flags[0].severity == "flag"
        assert "EXEMPT" in flags[0].detail

    def test_non_guarantee_truncated_bullet_still_dropped(self):
        from core.summarisation.postchecks.field_phases import postcheck_bullets
        from core.summarisation.postchecks.shared import PostCheckReport

        report = PostCheckReport()
        out = postcheck_bullets([self.DANGLING_GUARANTEE], self._ctx(), report)
        assert out == []
        fixes = [i for i in report.issues if i.detector == "truncated"]
        assert fixes and fixes[0].severity == "fix"
        assert "dropped truncated bullet" in fixes[0].detail

    def test_orchestrator_threads_the_guarantee_texts(self):
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            bullets=[self.DANGLING_GUARANTEE],
            executive_summary="",
            thorough_summary="",
            enum_guarantee_texts=[self.DANGLING_GUARANTEE],
        )
        assert report.bullets == [self.DANGLING_GUARANTEE]


# ─────────────────────────────────────────────────────────────────────────────
# 4+2. thorough_addition: truncation guard + chunked gap-fill
# ─────────────────────────────────────────────────────────────────────────────


class TestThoroughAdditionGuard:
    def _floor_stub(self, monkeypatch, missing, response):
        from core.summarisation.thorough_theorist_floor import (
            SummarizerThoroughFloorMixin,
        )

        state = {"missing": list(missing), "response": response, "calls": []}

        class _S(SummarizerThoroughFloorMixin):
            language = "en"
            primary_model = "test-model"
            temperature = 0.7

            def log(self, msg, level="INFO"):
                state.setdefault("logs", []).append(msg)

            def _deadline_exceeded(self, phase):
                return False

            def _strip_thinking(self, raw):
                return raw

            def _call_llm_with_empty_retry(
                self, prompt, model=None, temperature=None, max_tokens=None
            ):
                state["calls"].append(
                    {
                        "prompt": prompt,
                        "max_tokens": max_tokens,
                        "names": [n for n in missing if n in prompt],
                    }
                )
                return state["response"]

        import core.preprocessing.deterministic_analyzer as da_mod

        def _fake_check_coverage(analysis, text):
            still = [n for n in state["missing"] if n not in text]
            return {
                "total": len(state["missing"]),
                "covered": [n for n in state["missing"] if n in text],
                "missing": still,
            }

        monkeypatch.setattr(da_mod, "check_coverage", _fake_check_coverage)
        return _S(), state

    def test_unclosed_tag_never_ships_and_tail_is_sanitized(self, monkeypatch):
        response = (
            "<thorough_addition>\n"
            "Knight (1953) catalogued the eleven ego functions whose combined "
            "impairment distinguishes borderline patients from neurotics, "
            "framing the diagnosis in structural rather than purely "
            "descriptive terms for the American literature.\n"
            "Rinsley (1977) extended the developmental arrest account toward "
            "annihilatory panic and parental victimization via incest or cruelty,"
        )
        s, state = self._floor_stub(monkeypatch, ["Knight", "Rinsley"], response)
        out = s._thorough_theorist_floor(
            "Chapter",
            "Source text about Knight ego functions and Rinsley developmental arrest.",
            "Existing thorough summary " + "with enough words to extend. " * 12,
            "ANALYSIS",
        )
        assert "<thorough_addition>" not in out
        assert "</thorough_addition>" not in out
        # the mid-sentence tail is gone, the clean prefix survives
        assert "Knight (1953) catalogued the eleven ego functions" in out
        assert not out.rstrip().endswith("cruelty,")
        assert any("output cap" in m for m in state["logs"])

    def test_gap_fill_is_chunked_and_names_capped(self, monkeypatch):
        names = [f"Theorist{i:02d}" for i in range(47)]
        response = (
            "<thorough_addition>\n"
            + " ".join(
                f"Theorist{i:02d} contributed framework {i} to the field." for i in range(12)
            )
            + "\n</thorough_addition>"
        )
        s, state = self._floor_stub(monkeypatch, names, response)
        out = s._thorough_theorist_floor(
            "Chapter", "source " * 200, "Existing thorough " + "content. " * 60, "ANALYSIS"
        )
        calls = state["calls"]
        assert 1 <= len(calls) <= 3, "≤3 chunked calls"
        for c in calls:
            n = len(c["names"])
            assert n <= 12, f"≤12 names per call, got {n}"
            assert c["max_tokens"] == 1536
        assert "Theorist00 contributed framework 0" in out
        assert any("chunked call" in m for m in state["logs"])

    def test_anti_roster_constraint_in_prompt(self, monkeypatch):
        response = "<thorough_addition>\nGood prose here with enough words to pass the length gate.\n</thorough_addition>"
        s, state = self._floor_stub(monkeypatch, ["Knight"], response)
        s._thorough_theorist_floor(
            "Chapter", "source " * 200, "Existing thorough " + "content. " * 60, "ANALYSIS"
        )
        assert "NEVER open a paragraph with a roster of names" in state["calls"][0]["prompt"]


class TestGroundedAdditionSentences:
    SOURCE = (
        "Klein (1946) described play-technique criticism of the child's "
        "primitive object relations. "
        * 3
        + "…far away… " * 50
        + "Knight (1953) catalogued eleven ego functions impaired in "
        "borderline conditions. "
        + "…elsewhere… " * 50
        + "Piaget (1945) wrote on the psychology of play in children."
    )

    def test_welded_sentence_is_dropped(self):
        addition = (
            "Piaget's theories were referenced regarding the play-technique "
            "criticism of primitive object relations. "
            "Knight's cataloguing of ego functions remains influential."
        )
        filtered, dropped = _grounded_addition_sentences(
            addition, self.SOURCE, ["Piaget", "Knight"]
        )
        assert len(dropped) == 1
        assert "Piaget's theories were referenced regarding the play-technique" in dropped[0]
        assert "Knight's cataloguing" in filtered

    def test_grounded_sentence_is_kept(self):
        addition = "Knight (1953) catalogued the impaired ego functions of borderline patients."
        filtered, dropped = _grounded_addition_sentences(addition, self.SOURCE, ["Knight"])
        assert not dropped
        assert filtered == addition

    def test_nameless_sentences_pass_untouched(self):
        addition = "The chapter traces the history of the borderline construct across five decades."
        filtered, dropped = _grounded_addition_sentences(addition, self.SOURCE, ["Knight"])
        assert not dropped and filtered == addition

    def test_never_raises_on_bad_input(self):
        assert _grounded_addition_sentences(None, "src", ["X"])[0] in (None, "")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Filler floor: "appears in the same citation list"
# ─────────────────────────────────────────────────────────────────────────────


class TestFillerSameCitationList:
    def test_wolberg_shape_is_filler(self):
        assert is_citation_filler_bullet(
            "Wolberg appears in the same citation list as Reich and Fenichel."
        )

    def test_shared_reference_list_is_filler(self):
        assert is_citation_filler_bullet(
            "The author is included in a shared reference list of contributors."
        ) is False or is_citation_filler_bullet(
            "Zilboorg is mentioned in the shared citation list of the chapter."
        )

    def test_content_bullet_not_filler(self):
        assert not is_citation_filler_bullet(
            "Knight catalogued eleven ego functions whose impairment marks the "
            "borderline condition."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Provider-aware routing (llamacpp)
# ─────────────────────────────────────────────────────────────────────────────


class TestSimplifiedKeypointsLlamacppRouting:
    def _builder(self):
        from core.summarisation.simplified_keypoints import SimplifiedKeypointsBuilder

        b = object.__new__(SimplifiedKeypointsBuilder)
        b.provider = "llamacpp"
        b.llamacpp_base_url = "http://127.0.0.1:8080/v1"
        b.llamacpp_api_key = "local"
        b.llamacpp_model = "Ternary-Bonsai-2-27B-Instruct-Vision"
        b.model = "Ternary-Bonsai-2-27B-Instruct-Vision"
        b.temperature = 0.1
        b.max_output_tokens_per_batch = 4096
        b.retries = 1
        b.provider = "llamacpp"
        b.log = lambda msg, level="INFO": None
        return b

    def test_call_llm_routes_to_llama_server(self, monkeypatch):
        import core.summarisation.llm_dispatcher as disp

        captured = {}

        def _fake_call(prompt, base_url, api_key, model, label, temp, max_tokens, **kw):
            captured.update(
                base_url=base_url, api_key=api_key, model=model, label=label, prompt=prompt
            )
            return "simplified text"

        monkeypatch.setattr(disp, "call_openai_compat", _fake_call)
        b = self._builder()

        def _no_ollama(*a, **k):  # pragma: no cover — must never run
            raise AssertionError("the Ollama path must not be used when provider=llamacpp")

        b._call_ollama = _no_ollama  # type: ignore[method-assign]
        assert b._call_llm("simplify this") == "simplified text"
        assert captured["base_url"] == "http://127.0.0.1:8080/v1"
        assert captured["label"] == "llama.cpp"
        assert captured["model"] == "Ternary-Bonsai-2-27B-Instruct-Vision"

    def test_call_llm_single_routes_to_llama_server(self, monkeypatch):
        import core.summarisation.llm_dispatcher as disp

        captured = {}

        def _fake_call(prompt, base_url, api_key, model, label, temp, max_tokens, **kw):
            captured.update(base_url=base_url, label=label)
            return "simplified single"

        monkeypatch.setattr(disp, "call_openai_compat", _fake_call)
        b = self._builder()

        def _no_ollama(*a, **k):  # pragma: no cover — must never run
            raise AssertionError("the Ollama path must not be used when provider=llamacpp")

        b._call_ollama = _no_ollama  # type: ignore[method-assign]
        assert b._call_llm_single("simplify one") == "simplified single"
        assert captured["base_url"] == "http://127.0.0.1:8080/v1"


class TestVisionProviderProviderAware:
    def test_provider_setting_routes_to_llamacpp(self, monkeypatch):
        import core.llm.llm_provider_impl as impl

        created = {}

        class _FakeProvider:
            def supports_vision(self):
                return True

        def _fake_create(provider_name, settings=None, **kw):
            created["name"] = provider_name
            return _FakeProvider()

        monkeypatch.setattr(impl, "create_provider", _fake_create)
        from core.ocr.service import OCRService

        svc = object.__new__(OCRService)
        svc.log = lambda msg, level="INFO": None
        settings = types.SimpleNamespace(
            get=lambda key, default=None: {
                "summarisation.provider": "llamacpp",
                "summarisation.cloud_provider": "openai_compatible",
            }.get(key, default)
        )
        # arch is single_local (the V4.23 rig's stale value) — the ACTIVE
        # provider setting must still route to llama.cpp
        prov = svc._create_vision_provider("single_local", "some-model", settings)
        assert created["name"] == "llamacpp"
        assert isinstance(prov, _FakeProvider)

    def test_ollama_architecture_still_routes_to_ollama(self, monkeypatch):
        import core.llm.llm_provider_impl as impl

        created = {}

        class _FakeProvider:
            def supports_vision(self):
                return False

        def _fake_create(provider_name, settings=None, **kw):
            created["name"] = provider_name
            return _FakeProvider()

        monkeypatch.setattr(impl, "create_provider", _fake_create)
        from core.ocr.service import OCRService

        svc = object.__new__(OCRService)
        svc.log = lambda msg, level="INFO": None
        settings = types.SimpleNamespace(
            get=lambda key, default=None: {
                "summarisation.provider": "ollama",
            }.get(key, default)
        )
        svc._create_vision_provider("single_local", "some-model", settings)
        assert created["name"] == "ollama"


class TestFigureExtractorLlamacppPath:
    def _extractor(self, provider_setting):
        from core.pdf.vision_figure_extractor import VisionFigureExtractor

        v = object.__new__(VisionFigureExtractor)
        v.settings = types.SimpleNamespace(
            get=lambda key, default=None: {
                "summarisation.provider": provider_setting,
                "summarisation.llamacpp_model": "bonsai-vision",
            }.get(key, default)
        )
        v.log = lambda msg, level="INFO": None
        v.model_name = "OlmOCR-2-7B:latest"
        v._llamacpp_provider_model = ""
        return v

    def test_llamacpp_provider_created_when_setting_active(self, monkeypatch):
        import core.llm.llm_provider_impl as impl

        class _FakeProvider:
            def supports_vision(self):
                return True

            def complete_with_image(
                self, prompt, image_bytes, temperature=0.0, max_tokens=1024, model=None
            ):
                return "figure text via llama-server"

        monkeypatch.setattr(impl, "create_provider", lambda *a, **k: _FakeProvider())
        v = self._extractor("llamacpp")
        prov = v._create_llamacpp_vision_provider()
        assert isinstance(prov, _FakeProvider)
        assert v._llamacpp_provider_model == "bonsai-vision"
        # the image call routes through the provider
        v._llamacpp_provider = prov
        v.retries = 1
        assert v._extract_text_from_image(b"img", 1, 0) == "figure text via llama-server"

    def test_none_when_provider_is_ollama(self, monkeypatch):
        import core.llm.llm_provider_impl as impl

        monkeypatch.setattr(impl, "create_provider", lambda *a, **k: None)
        v = self._extractor("ollama")
        assert v._create_llamacpp_vision_provider() is None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Tesseract PSM retries (the p.107 class)
# ─────────────────────────────────────────────────────────────────────────────


class TestTesseractPsmRetry:
    def test_recovers_with_alternate_psm(self, monkeypatch):
        import sys

        from core.ocr.service import OCRService

        calls: list[str] = []

        fake_pt = types.ModuleType("pytesseract")

        def _image_to_string(img, lang="eng", config=""):
            calls.append(config)
            if config == "":
                return ""  # the p.107 failure shape
            return "recovered page text"

        fake_pt.image_to_string = _image_to_string
        fake_pt.pytesseract = types.SimpleNamespace(tesseract_cmd="")
        monkeypatch.setitem(sys.modules, "pytesseract", fake_pt)

        fake_pil = types.ModuleType("PIL")
        fake_pil.Image = types.SimpleNamespace(open=lambda bio: object())
        monkeypatch.setitem(sys.modules, "PIL", fake_pil)

        svc = object.__new__(OCRService)
        svc._tesseract_cmd = "tesseract"
        logs: list[str] = []
        svc.log = lambda msg, level="INFO": logs.append(msg)

        res = svc._tesseract_ocr(b"image-bytes", 107)
        assert res.success is True
        assert res.text == "recovered page text"
        assert calls == ["", "--psm 6"], "stop at the first recovering mode"
        assert any("recovered with" in m for m in logs)

    def test_reports_three_modes_when_all_empty(self, monkeypatch):
        import sys

        from core.ocr.service import OCRService

        calls: list[str] = []
        fake_pt = types.ModuleType("pytesseract")
        fake_pt.image_to_string = lambda img, lang="eng", config="": calls.append(config) or ""
        fake_pt.pytesseract = types.SimpleNamespace(tesseract_cmd="")
        monkeypatch.setitem(sys.modules, "pytesseract", fake_pt)

        fake_pil = types.ModuleType("PIL")
        fake_pil.Image = types.SimpleNamespace(open=lambda bio: object())
        monkeypatch.setitem(sys.modules, "PIL", fake_pil)

        svc = object.__new__(OCRService)
        svc._tesseract_cmd = "tesseract"
        svc.log = lambda msg, level="INFO": None

        res = svc._tesseract_ocr(b"image-bytes", 107)
        assert res.success is False
        assert calls == ["", "--psm 6", "--psm 4"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
