"""V18.20.3.9 — Phase 2 (rule integrity) + residuals-sweep policy tests.

Sections:
  1. RESIDUALS DENY-LIST — the runtime code (core/, utils/, ui_qt/, prompts/,
     config/, controller.py, main.py) must contain NONE of the test chapter's
     proper nouns, its distinctive concept phrases, or the other-book given
     names that previously keyed the narrative detector. This is the user's
     standing rule enforced as a test: no book/chapter-specific term, word, or
     pattern from ANY processed book may be hardcoded in the system — the
     system must generalize. THE BANNED LISTS BELOW ARE DERIVED FROM THE TEST
     CHAPTER BY DESIGN: tests are the enforcement layer and need the
     vocabulary to assert its absence from runtime code. Test fixtures and
     docs/ground_truth (user-mandated) are deliberately NOT scanned.
  2. A1 — narrative-pattern structural redesign, both directions (any-book
     catch + academic-bullet safety).
  3. A2 — concept-indicator domain-noun purge.
  4. A3 — leakage-pattern structural generalization (any-domain).
  5. A5 — crash_visibility stdlib-only (AST) + ci.yml branch-list validity.
  6. B3 — possessive-subject extraction broadened to the new noun shapes +
     the strengthened mention-only prompt ban.
  7. B1 — diagnostic provenance stamps + "Open summaries folder" wiring.
  8. C1 — per-call LLM telemetry registry + estimator call-count honesty.
"""
from __future__ import annotations

import ast
import re
import sys
import threading
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ═════════════════════════════════════════════════════════════════════════════
# 1) RESIDUALS DENY-LIST — the runtime code must stay book-agnostic forever
# ═════════════════════════════════════════════════════════════════════════════

# Proper nouns extracted from the ground-truth test chapter (the same
# inventory the V18.20.3.9 residuals sweep used — 43 names).
CHAPTER_NAMES = [
    "Jacobson", "Freud", "Erikson", "Kernberg", "Mahler", "Blos", "Winnicott",
    "Lichtenstein", "Greenacre", "Chasseguet", "Smirgel", "Fenichel", "Hartmann",
    "Searles", "Eissler", "Fromm", "Wheelis", "Lynd", "Lifton", "Lasch", "Kovel",
    "Tausk", "Glover", "Stoller", "Galenson", "Roiphe", "Kris", "Loewenstein",
    "Spitz", "Khan", "Klein", "Loewald", "Guttman", "Whitman", "Marx", "Durkheim",
    "Akhtar", "Salman", "Oedipus", "oedipal", "Jews", "Jewry", "WINNICOTT",
]
# Distinctive concept phrases from the chapter + the domain vocabulary that
# previously keyed live detectors/prompts (A1/A2/A3 + the prompt examples).
CHAPTER_CONCEPTS = [
    "false self", "true self", "identity diffusion", "ego identity",
    "identity principle", "corporeality", "sine qua non", "psychoanalytic",
    "psychoanalysis", "psychoanalysts", "metapsychological", "object relations",
    "self psychology", "Broken Structures", "IDENTITY AND ITS ORIGINS",
    "identity and its origins", "Song of Myself", "das Ich",
    "second individuation", "psychic structure", "self-object",
    "developmental basis", "three-step process",
]
# The other-book given names that keyed _NARRATIVE_PATTERNS before V18.20.3.9
# (the W3 class — "a 'Werner went to…' bullet shipped because the name wasn't
# listed"). Distinctive subset only (common names like John/Mark are pinned by
# the pattern-shape assertions below instead of the file scan).
OTHER_BOOK_NAMES = ["Ryan", "Thad", "Clive", "Tyler", "Bernard", "Georgina", "Brad"]
OTHER_BOOK_VOCAB = ["entrepreneurs", "operatives", "spies"]

_RUNTIME_PREFIXES = ("core/", "utils/", "ui_qt/", "controller.py", "main.py",
                     "config/", "prompts/", "installer/", "assets/")
_SKIP_FILES = {"CHANGELOG.md", "Project-History.md", "Readme.md",
               "NEW_SESSION_PROMPT.md", "docs/EVALUATION_FRAMEWORK.md",
               "docs/USER_OLLAMA_MODELS.md", "docs/EMBEDDERS.md"}
_SCAN_EXTS = (".py", ".json", ".md", ".txt", ".toml", ".yml", ".yaml", ".iss")


class TestResidualsDenyList:
    """V18.20.3.9 (user rule / residuals sweep): zero book traces in runtime."""

    def _runtime_files(self):
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file() or p.suffix not in _SCAN_EXTS:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if not rel.startswith(_RUNTIME_PREFIXES):
                continue
            if rel in _SKIP_FILES or rel.startswith("docs/ground_truth/"):
                continue
            # Exemption: qwen_tts_engine.py carries "Ryan" as a Qwen TTS
            # PRESET VOICE NAME — third-party product data shipped by the
            # model vendor, not book-derived vocabulary keyed by us.
            if rel == "core/tts/qwen_tts_engine.py":
                continue
            if "__pycache__" in rel or ".pytest_cache" in rel or ".ruff_cache" in rel:
                continue
            yield rel, p

    def test_runtime_contains_no_chapter_names(self):
        offenders = []
        rx = re.compile(r"\b(?:"
                        + "|".join(re.escape(n) for n in CHAPTER_NAMES + OTHER_BOOK_NAMES)
                        + r")\b")
        for rel, p in self._runtime_files():
            for i, line in enumerate(
                p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if rx.search(line):
                    offenders.append(f"{rel}:{i}")
        assert not offenders, (
            "Book-derived proper nouns found in runtime code "
            f"(the no-hardcoding rule is breached): {offenders[:10]}"
        )

    def test_runtime_contains_no_chapter_concept_phrases(self):
        offenders = []
        terms = CHAPTER_CONCEPTS + OTHER_BOOK_VOCAB
        rxs = [(t, re.compile(re.escape(t), re.IGNORECASE if t[0].islower() else 0))
               for t in terms]
        for rel, p in self._runtime_files():
            for i, line in enumerate(
                p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                for t, rx in rxs:
                    if rx.search(line):
                        offenders.append(f"{rel}:{i} [{t}]")
                        break
        assert not offenders, (
            "Book-derived concept phrases / domain vocabulary found in runtime "
            f"code: {offenders[:10]}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2) A1 — narrative detection is structural now (any book), academic-safe
# ═════════════════════════════════════════════════════════════════════════════

from core.summarisation.post_processing import (  # noqa: E402
    _CONCEPT_INDICATORS,
    _NARRATIVE_PATTERNS,
    classify_bullets,
)


def _narrative_dropped(bullet: str) -> bool:
    kept, drops = classify_bullets([bullet])
    return any("narrative" in d[1] for d in drops) and not kept


class TestNarrativeStructural:
    """V18.20.3.9 (Phase 2 / A1): _NARRATIVE_PATTERNS[0] replaced the
    book-keyed given-name alternation with the structural scene shape
    (any capitalized subject + scene verb + article object)."""

    def test_pattern_1_is_structural_no_name_alternation(self):
        pat = _NARRATIVE_PATTERNS[0].pattern
        # The structural subject: any capitalized word, guarded by the
        # common-word lookahead — NOT a name list.
        assert "[A-Z][a-z']*" in pat
        for name in OTHER_BOOK_NAMES + ["James", "Sarah", "Kate", "Anna"]:
            assert name not in pat, f"name-keyed subject survived: {name}"

    def test_any_book_narrative_bullet_dropped(self):
        """The W3 miss: a narrative bullet whose character name was never in
        the (old) name list must be caught in ANY book."""
        assert _narrative_dropped("Werner went to the party to meet the contact.")

    def test_legacy_fixture_still_dropped(self):
        """Existing regression fixture keeps its verdict (test_post_processing
        pins the same line)."""
        assert _narrative_dropped("Ryan went to a party and met Thad.")

    def test_scene_verb_variants_dropped(self):
        assert _narrative_dropped("Sarah met the agent at a quiet cafe.")
        assert _narrative_dropped("Clive bought a company with borrowed money.")
        assert _narrative_dropped("Tyler paid the informant in cash.")
        assert _narrative_dropped("Georgina arrives at a hotel in Lisbon.")

    def test_academic_attribution_verbs_are_safe(self):
        """With a book-agnostic subject, the verbs that open real academic
        bullets MUST NOT fire: 'Surname <attribution verb> …' is the most
        common nonfiction bullet shape."""
        safe = [
            "Erikson established the epigenetic principle of development.",
            "Freud said the ego is the rider of the horse, not the horse.",
            "Kernberg observed that splitting precedes integration.",
            "Mahler used longitudinal observation to derive the phases.",
            "Winnicott described the infant's spontaneous gestures.",
            "Jacobson formulated the dual-drive model of the ego.",
        ]
        for b in safe:
            assert not _narrative_dropped(b), f"false positive on: {b}"

    def test_common_initial_words_are_safe(self):
        """'They went to great lengths to argue' is academic English, not
        scene narration — the lookahead must keep it."""
        assert not _narrative_dropped("They went to great lengths to argue the point.")
        assert not _narrative_dropped("It goes to the heart of the argument.")

    def test_biographical_proper_object_is_safe(self):
        """'X met <ProperName>' (biography) is kept — scene narration
        addresses generic scene objects ('the party'), biographies address
        proper nouns. Documented trade-off of the structural redesign."""
        assert not _narrative_dropped("Erikson met Anna Freud in Vienna in 1927.")
        assert not _narrative_dropped("Werner went to Berlin to study medicine.")

    def test_label_style_bullet_safe(self):
        """Roadmap acceptance: 'Erikson's stages of psychosocial development'
        must NOT be flagged (label bullet, no citation scaffolding)."""
        assert not _narrative_dropped("Erikson's stages of psychosocial development.")

    def test_concept_rescue_still_applies(self):
        """Narrative + concept indicator → kept (the V18.20.3.2 calibration
        is unchanged)."""
        kept, drops = classify_bullets(
            ["Ryan went to a party, which illustrates the principle of social identity formation."]
        )
        assert kept and not any("narrative" in d[1] for d in drops)


# ═════════════════════════════════════════════════════════════════════════════
# 3) A2 — concept indicators are structural only
# ═════════════════════════════════════════════════════════════════════════════

class TestConceptIndicators:
    def test_domain_nouns_purged(self):
        pat = _CONCEPT_INDICATORS.pattern
        for noun in ("entrepreneurs", "businesses", "spies", "operatives",
                     "analysts", "professionals"):
            assert noun not in pat, f"domain noun survived: {noun}"

    def test_structural_indicators_kept(self):
        for phrase in ("is defined as", "the concept of", "the purpose of",
                       "studies show"):
            assert _CONCEPT_INDICATORS.search(
                f"The text {phrase} something."
            ), f"structural indicator lost: {phrase}"

    def test_domain_noun_no_longer_rescues_narrative(self):
        """A narrative bullet that carries a (purged) domain noun is no
        longer rescued — the noun was book-derived vocabulary."""
        assert _narrative_dropped("Brad went to a meeting with entrepreneurs.")


# ═════════════════════════════════════════════════════════════════════════════
# 4) A3 — the leakage pattern is the structural genre-speculation class
# ═════════════════════════════════════════════════════════════════════════════

from core.summarisation.postchecks import detect_prompt_leakage  # noqa: E402


class TestLeakagePatternGeneralized:
    def test_any_domain_genre_speculation_stripped(self):
        """The class (model speculating about the SOURCE's genre) must fire
        for ANY domain, not only the one book that produced the original
        literal."""
        for domain in ("a historical text", "a technical manual",
                       "a psychoanalytic text", "a botanical study"):
            text, _ = detect_prompt_leakage(
                f"a comprehensive summary of Chapter 1 from what appears to be {domain}.",
                "thorough",
            )
            assert "what appears to be" not in text, domain

    def test_seems_variant_also_caught(self):
        text, _ = detect_prompt_leakage(
            "Here is the summary of what seems to be a geological document.",
            "thorough",
        )
        assert "what seems to be" not in text


# ═════════════════════════════════════════════════════════════════════════════
# 5) A5 — guards: crash_visibility stdlib-only (AST) + ci.yml branches
# ═════════════════════════════════════════════════════════════════════════════

class TestCrashVisibilityStdlibOnly:
    def test_imports_are_stdlib_only(self):
        """crash_visibility must stay importable BEFORE any heavy import
        (torch/PySide6) — enforced structurally via the AST."""
        src = (ROOT / "core" / "system" / "crash_visibility.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        non_stdlib = {m for m in imported if m not in sys.stdlib_module_names}
        assert not non_stdlib, f"non-stdlib imports found: {non_stdlib}"


class TestCiBranchList:
    def test_branch_lists_valid(self):
        """The CI triggers must be the valid '[main, master]' list on both
        push and pull_request. (The V18.20.3.7 audit reported 'ain, master]'
        as a typo — hexdump verification in V18.20.3.9 showed the bytes were
        always correct and the report was a display artifact; this test
        pins the real state so any future edit that breaks it fails here.)"""
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert ci.count("branches: [main, master]") == 2, (
            "ci.yml must trigger on push + pull_request with branches "
            "[main, master] — CI never runs otherwise"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 6) B3 — possessive-subject extraction broadened + prompt ban strengthened
# ═════════════════════════════════════════════════════════════════════════════

from core.summarisation.postcheck_detectors import (  # noqa: E402
    _ATTRIBUTIVE_POSSESSIVE_RE,
    _SRC_POSSESSIVE_SUBJECT_RE,
    _SRC_PRONOUN_SUBJECT_RE,
    _parse_bullet_subject,
    detect_attribution_subject_swap,
)


class TestPossessiveSubjectBroadened:
    def test_new_noun_shapes_extract_bullet_subject(self):
        """V18.20.3.9 (B3): the possessive machinery now extracts the
        claimed subject for the noun shapes the .3.8 rig audit's F3 concern
        used (research / perspective / ideas / study …)."""
        for bullet in (
            "AuthorX's research provides the foundational mechanism for the construct.",
            "AuthorX's perspective offers a revised reading of the data.",
            "AuthorX's ideas emphasize the structural constraints.",
            "AuthorX's study establishes the correlation.",
        ):
            parsed = _parse_bullet_subject(bullet)
            assert parsed is not None, bullet
            assert parsed[0] == "AuthorX", bullet

    def test_label_possessive_still_not_extracted(self):
        """Plain possessive mentions without an attribution verb ('Name's
        six phases') must not enter the veto — unchanged contract."""
        assert _parse_bullet_subject("AuthorI's six phases of development") is None

    def test_attributive_possessive_matches_new_nouns(self):
        m = _ATTRIBUTIVE_POSSESSIVE_RE.search(
            "AuthorX's research provides the mechanism."
        )
        assert m and m.group(1) == "AuthorX" and m.group(2).lower() == "provides"

    def test_source_side_possessive_new_nouns(self):
        m = _SRC_POSSESSIVE_SUBJECT_RE.search(
            "AuthorY's perspective provided the account."
        )
        assert m and m.group(1) == "AuthorY"
        m2 = _SRC_PRONOUN_SUBJECT_RE.search("His analysis established the pattern.")
        assert m2 and m2.group(1).lower() == "established"

    def test_subject_swap_flags_possessive_misattribution(self):
        """End-to-end (synthetic): the summary credits the cited-only author
        with the real holder's claim → flagged."""
        source = (
            "Marrow provided the mechanism for the consolidation process, "
            "describing it in detail (Whitfield 1971)."
        )
        bullet = (
            "Whitfield: Provided the mechanism for the consolidation process."
        )
        _, issues = detect_attribution_subject_swap(bullet, source, "bullet[0]")
        assert any(i.detector == "attribution_swap" for i in issues)


class TestMentionOnlyPromptBan:
    def test_possessive_ban_anywhere_in_prompt(self):
        """B3: the mention-only block now bans possessive-subject attribution
        ANYWHERE in the bullet (not just the opening) and uses a fully
        synthetic few-shot example.

        V18.20.3.12 (Phase 4 / W6-O5): the gap-fill loop (with the
        mention-only prompt template) moved VERBATIM from
        ``Summarizer._summarize_inner`` to ``gap_fill_batch.batch_gap_fill``
        — re-pointed at the new module; the pinned strings are unchanged."""
        import inspect

        from core.summarisation import gap_fill_batch as gfb

        src = inspect.getsource(gfb.batch_gap_fill)
        assert "ANYWHERE in the bullet" in src
        assert "possessive construction" in src
        # the synthetic example replaced the book-derived one
        assert "Voss" in src and "Ibarra" in src

    def test_old_book_derived_example_gone(self):
        import inspect

        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        assert "integrated Klein" not in src


# ═════════════════════════════════════════════════════════════════════════════
# 7) B1 — provenance stamps in the diagnostic + open-summaries affordance
# ═════════════════════════════════════════════════════════════════════════════

class TestB1ProvenanceAndAffordance:
    def test_diagnostic_prints_stamps(self):
        """The end-of-run diagnostic block must print every summaries/*.md
        file's generated-by line (or warn about its absence)."""
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        # V18.20.3.10 (F6): the check now delegates to the canonical
        # whole-text parser instead of peeking line 2.
        assert "stamp_diagnostic" in src
        assert "Summary files (" in src
        prov = (ROOT / "core" / "system" / "provenance.py").read_text(
            encoding="utf-8"
        )
        assert "NO generated-by stamp" in prov

    def test_wizard_open_summaries_button(self):
        # V18.20.4.6 (P5 / O-b1 wizard split): the Step-9 button label
        # moved verbatim to ui_qt/views/wizard_steps/step9_logs.py with
        # the Step9Logs class; the click wiring + the
        # _open_summaries_folder handler stayed in wizard_view.py.
        # Assertions unchanged — the pin now reads the label from its
        # real home instead of wizard_view.py's module docstring.
        step9 = (ROOT / "ui_qt" / "views" / "wizard_steps" /
                 "step9_logs.py").read_text(encoding="utf-8")
        assert "Open summaries folder" in step9
        src = (ROOT / "ui_qt" / "views" / "wizard_view.py").read_text(
            encoding="utf-8"
        )
        assert "_open_summaries_folder" in src

    def test_convert_view_open_summaries_button(self):
        src = (ROOT / "ui_qt" / "views" / "convert_view.py").read_text(
            encoding="utf-8"
        )
        assert "Open Summaries Folder" in src


# ═════════════════════════════════════════════════════════════════════════════
# 8) C1 — per-call telemetry registry + estimator honesty
# ═════════════════════════════════════════════════════════════════════════════

from core.llm import call_meta  # noqa: E402


class TestCallTelemetryRegistry:
    def setup_method(self):
        call_meta.reset_call_telemetry()

    def teardown_method(self):
        call_meta.reset_call_telemetry()

    def test_round_trip_and_summary_math(self):
        call_meta.record_call_telemetry("m1", 10.0, 100, 50, "stop")
        call_meta.record_call_telemetry("m2", 2.0, 10, 5, "length")
        call_meta.record_call_telemetry("m3", 7.5, 70, 35, "stop")
        s = call_meta.call_telemetry_summary()
        assert s["calls"] == 3
        assert s["total_s"] == pytest.approx(19.5)
        assert s["truncated"] == 1
        # slowest first, top_n respected
        assert [c["model"] for c in s["slowest"]] == ["m1", "m3", "m2"]
        assert len(call_meta.call_telemetry_summary(top_n=1)["slowest"]) == 1

    def test_reset_clears(self):
        call_meta.record_call_telemetry("m", 1.0, 1, 1, "stop")
        call_meta.reset_call_telemetry()
        assert call_meta.call_telemetry_summary() == {
            "calls": 0, "total_s": 0.0, "truncated": 0, "slowest": []
        }

    def test_recording_never_raises(self):
        """Hostile input must never raise (the registry is best-effort by
        contract — a bad record is dropped, not raised)."""
        call_meta.record_call_telemetry(None, "not-a-float", None, None, None)
        call_meta.record_call_telemetry("m", 1.0, 1, 1, "stop")
        assert call_meta.call_telemetry_summary()["calls"] == 1

    def test_thread_safety(self):
        def _worker():
            for _ in range(50):
                call_meta.record_call_telemetry("t", 0.01, 1, 1, "stop")

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert call_meta.call_telemetry_summary()["calls"] == 400

    def test_provider_wires_telemetry(self):
        src = (ROOT / "core" / "llm" / "ollama_provider.py").read_text(
            encoding="utf-8"
        )
        assert "record_call_telemetry(" in src
        assert "done in {" in src  # the ⏱️ per-call INFO line

    def test_converter_wires_reset_and_summary(self):
        src = (ROOT / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        assert "reset_call_telemetry()" in src
        assert "call_telemetry_summary()" in src


class TestEstimatorCallCountHonesty:
    def test_typical_and_worst_case_bands(self, tmp_path):
        """The pre-conversion estimator reports the telemetry-recalibrated
        fan-out (~10 calls/chapter typical, ~40 worst) — V18.20.3.11 F7
        re-based on the .3.9 rig measurement (9 calls) minus the .3.11
        consolidation skip."""
        try:
            from pypdf import PdfWriter
        except ImportError:
            pytest.skip("pypdf unavailable")
        try:
            from utils.token_counter import count_tokens  # noqa: F401
        except Exception as e:
            pytest.skip(f"token-counter dependency chain unavailable: {e}")
        pdf = tmp_path / "tiny.pdf"
        w = PdfWriter()
        w.add_blank_page(width=612, height=792)
        with open(pdf, "wb") as fh:
            w.write(fh)
        # Hermetic import (conftest tiktoken-gate style): the estimator sits
        # behind core.pipeline's package __init__, which transitively imports
        # `markitdown` — installed on the rig, optional in the test sandbox.
        # Stub it if absent so the estimator's own logic is testable anywhere.
        if "markitdown" not in sys.modules:
            try:
                import markitdown  # noqa: F401
            except ImportError:
                _stub = types.ModuleType("markitdown")
                _stub.MarkItDown = object  # converter_impl imports this name
                sys.modules["markitdown"] = _stub
        try:
            from core.pipeline.token_estimator import estimate_conversion_tokens
        except Exception as e:
            pytest.skip(f"token_estimator import chain unavailable: {e}")

        req = types.SimpleNamespace(
            generate_summaries=True,
            academic_rigor=False,
            include_keypoints=False,
            output_briefing=False,
            output_podcast=False,
            output_flashcards=False,
            output_qa=False,
            output_study_guide=False,
            output_social=False,
            output_mindmap=False,
            output_packets=False,
            output_obsidian=False,
            summarisation_max_output_tokens=4096,
            selected_chapters=None,
        )
        est = estimate_conversion_tokens(pdf, req)
        assert est["chapter_count"] >= 1
        # typical band: 10/chapter + any per-output calls (none enabled here)
        assert est["llm_calls"] == est["chapter_count"] * 10
        assert est["llm_calls_worst_case"] >= est["llm_calls"]
        assert est["llm_calls_worst_case"] == pytest.approx(
            est["chapter_count"] * 40
        )
        assert "10 calls/chapter" in est["llm_calls_basis"]
