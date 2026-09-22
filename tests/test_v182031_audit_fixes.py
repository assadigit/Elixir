"""V18.20.3.1 characterization tests — second real-rig audit fixes.

Covers the defect classes found by the V18.20.3.0 "Broken Structures"
real-rig run audit (log: ``Broken Structures Salman Akhtar.conversion.log.md``,
output: ``001_1_-_IDENTITY_AND_ITS_ORIGINS_summary.md``):

D1 — TRUNCATED KEY DISTINCTIONS LINE SHIPPED: the additive followup call was
   capped at max_tokens=2048 while the model needed ~2700 → response cut
   (done_reason=length) mid-<key_distinctions>; the unclosed-tag regex
   fallback shipped the incomplete last line ("Kernberg's distinction
   between introjection (concrete, affectively charged.") and killed the
   theoretical_tensions section entirely. Fix: 4096 budget +
   ``strip_truncated_section_tail`` at BOTH parse points +
   postcheck now DROPS truncated additive lines.

D2 — PRONOUN AUTO-FIX WAS DEAD CODE + LYING LOGS: all 3 call sites discard
   the fixed text (``_, issues = ...``) while the Issue detail claimed
   "Auto-fixed to 'his'" — and the author-extraction regex captured ordinary
   nouns ('views', 'fails', 'metapsychological') as "authors", so all 5
   pronoun flags in the run were false positives whose "fixes" would have
   CORRUPTED correct text. Fix: flag-only + source_authors gate.

D3 — SUBJECT-SWAP RECURRED VIA COLON-FORM GAP-FILL BULLETS: "Khan: Provided
   the developmental basis…" (source credits Winnicott) and "Klein:
   Formulated a three-step process…" (source credits Kernberg — Klein is
   only inside the integration list) both shipped undetected; the V18.20.3.0
   detector only sees the possessive "X's work provides" form. Fix:
   colon-form + active-subject evidence paths.

D4 — CHECKPOINT DOCX LOG SHOWED ".docx.tmp": the builder logged the temp
   path it was handed; the final path only existed after os.replace.

D5 — QUARANTINE SUMMARY LOGGED 8×: the gap-fill loop calls
   filter_thinking_bullets per added bullet; each call re-logged the
   unchanged cumulative summary.

D7 — CONSOLIDATION/SCHOLAR CAPS TOO SMALL: 2048/3000-token budgets cut
   mid-generation (consolidation "merged 11" was partly silent loss;
   scholar "could not fill them" was the truncation, not the verdict).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Stub the optional heavy deps exactly like tests/test_v18203_audit_fixes.py
# (markitdown is not installed in this sandbox; the stub keeps the eager
# postchecks→…→core.pdf import chain loadable).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════
# 1) D1 — strip_truncated_section_tail helper
# ═══════════════════════════════════════════════════════════════════════════


class TestStripTruncatedSectionTail:
    """V18.20.3.1: the shared additive-section truncation-tail sanitizer."""

    def test_real_rig_truncated_kd_line_dropped(self):
        """The EXACT truncated Key Distinctions line from the V18.20.3.0 run."""
        from core.summarisation.response_parser import strip_truncated_section_tail

        section = (
            "- Lichtenstein's distinction between ego identity (personal "
            "identity resulting from self-objectivation) and existential "
            "identity, with both acknowledged as irreducible aspects.\n"
            "- Kernberg's distinction between introjection (concrete, "
            "affectively charged."
        )
        out = strip_truncated_section_tail(section, closing_tag_present=False)
        assert "introjection (concrete" not in out
        assert "Lichtenstein's distinction" in out

    def test_closed_tag_section_untouched(self):
        from core.summarisation.response_parser import strip_truncated_section_tail

        section = "- Complete item one.\n- Complete item two with (balanced parens)."
        assert strip_truncated_section_tail(section, closing_tag_present=True) == section

    def test_complete_last_line_untouched_even_when_unclosed(self):
        """Unclosed tag but the last line is complete → byte-identical."""
        from core.summarisation.response_parser import strip_truncated_section_tail

        section = "- Complete item one.\n- Complete item two ends properly."
        assert strip_truncated_section_tail(section, closing_tag_present=False) == section

    def test_bulleted_and_plain_last_line(self):
        from core.summarisation.response_parser import strip_truncated_section_tail

        plain = "First complete line.\nSecond line cut mid (parenthetical"
        out = strip_truncated_section_tail(plain, closing_tag_present=False)
        assert "parenthetical" not in out
        assert "First complete line." in out

    def test_empty_and_none_safe(self):
        from core.summarisation.response_parser import strip_truncated_section_tail

        assert strip_truncated_section_tail("", closing_tag_present=False) == ""
        assert strip_truncated_section_tail("   ", closing_tag_present=False) == "   "

    def test_trailing_blank_lines_dont_mask_the_cut(self):
        """Trailing blanks after the cut line are skipped, not treated as
        the last content line."""
        from core.summarisation.response_parser import strip_truncated_section_tail

        section = "- Complete item.\n- Cut line (unbalanced\n\n\n"
        out = strip_truncated_section_tail(section, closing_tag_present=False)
        assert "unbalanced" not in out


# ═══════════════════════════════════════════════════════════════════════════
# 2) D1 — response_parser XML path
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseParserTruncatedAdditive:
    """The primary/chunked parse path drops truncated additive tails."""

    def _raw_truncated_kd(self) -> str:
        return (
            "<executive_summary>Exec text about identity concepts.</executive_summary>\n"
            "<bullet_points>\n- A complete bullet sentence.</bullet_points>\n"
            "<thorough_summary>Thorough text about the chapter.</thorough_summary>\n"
            "<key_distinctions>\n"
            "- Distinction one is a complete sentence.\n"
            "- Kernberg's distinction between introjection (concrete, affectively charged."
        )

    def test_unclosed_kd_tail_dropped(self):
        from core.summarisation.response_parser import parse_response

        res = parse_response(self._raw_truncated_kd(), academic_rigor=False)
        assert "Distinction one" in res["key_distinctions"]
        assert "affectively charged" not in res["key_distinctions"]

    def test_closed_kd_kept_verbatim(self):
        from core.summarisation.response_parser import parse_response

        raw = self._raw_truncated_kd() + "\n</key_distinctions>"
        res = parse_response(raw, academic_rigor=False)
        assert "affectively charged" in res["key_distinctions"]

    def test_unclosed_tensions_tail_dropped(self):
        from core.summarisation.response_parser import parse_response

        raw = (
            "<executive_summary>Exec text about identity concepts.</executive_summary>\n"
            "<bullet_points>\n- A complete bullet sentence.</bullet_points>\n"
            "<thorough_summary>Thorough text about the chapter.</thorough_summary>\n"
            "<key_distinctions>\n- Complete distinction.\n</key_distinctions>\n"
            "<theoretical_tensions>\n"
            "- Tension one is complete.\n"
            "- Tension two cut at the (open paren"
        )
        res = parse_response(raw, academic_rigor=False)
        assert "Tension one" in res["theoretical_tensions"]
        assert "open paren" not in res["theoretical_tensions"]


# ═══════════════════════════════════════════════════════════════════════════
# 3) D1 — additive followup: budget + honest parse (duck-typed self)
# ═══════════════════════════════════════════════════════════════════════════


class _FakePromptManager:
    def render_template(self, template, **kw):
        return "prompt"


class _FakeAdditiveSelf:
    """Duck-typed Summarizer for _ensure_additive_sections (unbound call)."""

    language = "en"
    temperature = 0.7

    def __init__(self, raw_response, max_ctx_tokens=12000):
        self.request = types.SimpleNamespace(summarisation_max_context_tokens=max_ctx_tokens)
        self.prompt_manager = _FakePromptManager()
        self.raw_response = raw_response
        self.calls = []
        self.logs = []

    def log(self, msg, level="INFO"):
        self.logs.append((level, msg))

    def _select_prompt(self, name):
        return name

    def _call_llm_with_empty_retry(self, prompt, **kw):
        self.calls.append(kw)
        return self.raw_response

    def _strip_thinking(self, raw):
        return raw


class TestAdditiveFollowupHardening:
    def test_budget_raised_to_4096(self):
        """The V18.20.3.0 failure came from the 2048 cap (V18.20.3.1: 4096)."""
        from core.summarisation.summarizer import Summarizer

        fake = _FakeAdditiveSelf(
            "<key_distinctions>\n- Complete distinction line here.\n</key_distinctions>\n<theoretical_tensions>\n- Complete tension line here.\n</theoretical_tensions>"
        )
        result = {"key_distinctions": "", "theoretical_tensions": ""}
        Summarizer._ensure_additive_sections(fake, "Ch 1", "source text", result)
        assert fake.calls and fake.calls[0].get("max_tokens") == 4096

    def test_truncated_kd_tail_dropped_and_reported(self):
        from core.summarisation.summarizer import Summarizer

        raw = (
            "<key_distinctions>\n"
            "- Lichtenstein's distinction between ego identity and existential identity.\n"
            "- Kernberg's distinction between introjection (concrete, affectively charged."
        )
        fake = _FakeAdditiveSelf(raw)
        result = {"key_distinctions": "", "theoretical_tensions": ""}
        Summarizer._ensure_additive_sections(fake, "Ch 1", "source text", result)
        assert "Lichtenstein's distinction" in result["key_distinctions"]
        assert "affectively charged" not in result["key_distinctions"]
        # Honest reporting: the truncation was logged
        assert any("truncated mid-key_distinctions" in m for _, m in fake.logs)

    def test_honest_per_section_reporting(self):
        from core.summarisation.summarizer import Summarizer

        raw = "<key_distinctions>\n- One complete distinction item here.\n</key_distinctions>"
        fake = _FakeAdditiveSelf(raw)
        result = {"key_distinctions": "", "theoretical_tensions": ""}
        Summarizer._ensure_additive_sections(fake, "Ch 1", "source text", result)
        # The old single "✅ populated" line hid the missing section; now the
        # log names each section's state.
        assert any(
            "key_distinctions=" in m and "theoretical_tensions=MISSING" in m for _, m in fake.logs
        )

    def test_source_scan_no_2048_budget_remains(self):
        """Guard: the additive followup must not regress to max_tokens=2048.
        (Other call sites — exec-from-thorough, thematic synthesis — keep
        their own budgets; only the additive function body is scanned.)

        V18.20.4.7 (P5 / O-a2): ``_ensure_additive_sections`` moved VERBATIM
        to core/summarisation/additive_sections.py — the scan now reads the
        new module (the method is the mixin's LAST method, so the body
        slice also ends at end-of-module). Assertions unchanged."""
        import re as _re

        src = (PROJECT_ROOT / "core" / "summarisation" / "additive_sections.py").read_text(
            encoding="utf-8"
        )
        m = _re.search(r"def _ensure_additive_sections\(.*?(?=\n    def |\Z)", src, _re.DOTALL)
        assert m, "_ensure_additive_sections not found"
        body = m.group(0)
        assert "max_tokens=4096" in body
        assert "max_tokens=2048" not in body


# ═══════════════════════════════════════════════════════════════════════════
# 4) D1 — postchecks drop truncated additive lines
# ═══════════════════════════════════════════════════════════════════════════


class TestPostcheckDropsTruncatedAdditiveLines:
    def test_truncated_kd_line_dropped_and_recorded(self):
        from core.summarisation.postchecks import run_post_checks

        rep = run_post_checks(
            bullets=["A complete bullet about concepts."],
            executive_summary="Exec summary text.",
            thorough_summary="Thorough summary text with content.",
            key_distinctions=(
                "- Complete distinction line here.\n- Truncated line without end (unbalanced paren"
            ),
            theoretical_tensions="",
            source_text="concepts bullet complete distinction summary content text.",
        )
        assert "Truncated line" not in rep.key_distinctions
        assert "Complete distinction" in rep.key_distinctions
        trunc = [
            i for i in rep.issues if i.detector == "truncated" and i.field == "key_distinctions"
        ]
        assert trunc and trunc[0].severity == "fix"
        assert "dropped truncated line" in trunc[0].detail

    def test_truncated_tt_line_dropped(self):
        from core.summarisation.postchecks import run_post_checks

        rep = run_post_checks(
            bullets=["A complete bullet about concepts."],
            executive_summary="Exec summary text.",
            thorough_summary="Thorough summary text with content.",
            key_distinctions="",
            theoretical_tensions="- Complete tension line.\n- Cut tension (open",
            source_text="concepts bullet complete tension summary content text.",
        )
        assert "Cut tension" not in rep.theoretical_tensions
        assert "Complete tension" in rep.theoretical_tensions

    def test_complete_additive_lines_kept(self):
        from core.summarisation.postchecks import run_post_checks

        kd = "- Complete distinction line.\n- Another complete line (balanced)."
        rep = run_post_checks(
            bullets=["A complete bullet about concepts."],
            executive_summary="Exec summary text.",
            thorough_summary="Thorough summary text with content.",
            key_distinctions=kd,
            theoretical_tensions="",
            source_text="concepts bullet complete distinction summary content text.",
        )
        assert rep.key_distinctions == kd


# ═══════════════════════════════════════════════════════════════════════════
# 5) D2 — pronoun detector honesty + author gate
# ═══════════════════════════════════════════════════════════════════════════


class TestPronounDetectorHonesty:
    _SOURCE = (
        "Greenacre (1958) wrote about body image. Her views on the self were "
        "foundational. Freud (1923) described the ego. His structural theory "
        "endured. Winnicott did not use the term identity specifically, his "
        "views on early development are significant."
    )

    def test_text_never_modified_even_on_mismatch(self):
        from core.summarisation.postcheck_detectors import detect_pronoun_mismatch

        # Genuine mismatch: source says "Her views" for Greenacre; summary
        # says "His continuum" right after the Greenacre citation.
        text = "Greenacre (1958) described the body image. His continuum was foundational."
        out, issues = detect_pronoun_mismatch(
            text,
            self._SOURCE,
            "bullet[0]",
            source_authors=["Greenacre", "Freud", "Winnicott"],
        )
        assert out == text  # flag-only — NEVER rewritten
        assert issues, "the genuine mismatch must still be flagged"
        assert any(i.detector == "pronoun" for i in issues)

    def test_no_auto_fixed_claim_in_messages(self):
        from core.summarisation.postcheck_detectors import detect_pronoun_mismatch

        text = "Greenacre (1958) described the body image. His continuum was foundational."
        _, issues = detect_pronoun_mismatch(
            text, self._SOURCE, "bullet[0]", source_authors=["Greenacre", "Freud"]
        )
        assert issues
        for i in issues:
            assert "Auto-fixed" not in i.detail
            assert i.severity == "flag"

    def test_author_gate_kills_noun_false_positives(self):
        """The V18.20.3.0 run flagged 'views'/'fails'/'metapsychological' as
        "authors" — the gate suppresses every non-cited candidate."""
        from core.summarisation.postcheck_detectors import detect_pronoun_mismatch

        text = (
            "Her (1983, 1984) views on ego-ideal formation and what she calls "
            "perversion matter. His metapsychological differentiation was "
            "influential, and his developmental hypothesis was combined."
        )
        _, issues = detect_pronoun_mismatch(
            text,
            self._SOURCE,
            "bullet[16]",
            source_authors=["Greenacre", "Freud", "Winnicott"],
        )
        # None of the noun "authors" are source-cited → zero flags
        assert issues == []

    def test_no_gate_keeps_legacy_behaviour(self):
        """Without source_authors the old (ungated) path still runs — a real
        mismatch is still found."""
        from core.summarisation.postcheck_detectors import detect_pronoun_mismatch

        text = "Greenacre (1958) described the body image. His continuum was foundational."
        _, issues = detect_pronoun_mismatch(text, self._SOURCE, "bullet[0]")
        assert any(i.detector == "pronoun" for i in issues)

    def test_call_sites_pass_source_authors_gate(self):
        """Guard: all three run_post_checks call sites forward the gate."""
        # V0.18 (Phase 5.2): postchecks.py moved verbatim into the
        # postchecks package as orchestrator.py.
        # V0.4.19 (de-monolithization): the bullets/exec/thorough phases
        # moved VERBATIM to field_phases.py — the call sites are counted
        # across both homes (the pins follow the moved bodies).
        _pkg = PROJECT_ROOT / "core" / "summarisation" / "postchecks"
        src = (_pkg / "orchestrator.py").read_text(encoding="utf-8")
        phases = (_pkg / "field_phases.py").read_text(encoding="utf-8")
        assert (
            src.count("detect_pronoun_mismatch(") + phases.count("detect_pronoun_mismatch(") >= 3
        )  # 3 call sites (bullets/exec/thorough)
        assert (
            src.count("source_authors=source_authors")
            + phases.count("source_authors=source_authors")
            >= 3
        )


# ═══════════════════════════════════════════════════════════════════════════
# 6) D3 — subject-swap colon form (Khan + Klein classes)
# ═══════════════════════════════════════════════════════════════════════════


class TestSubjectSwapColonForm:
    _SOURCE = (
        "Winnicott Although Winnicott did not use the term identity "
        "specifically, his views on early development are of great "
        "significance to the formation of identity. His work provides the "
        "developmental basis for (1) authenticity; (2) \u201ccorporeality\u201d "
        "(Khan 1983), or a deeply assimilated and personalized bodily "
        "foundation for one's selfexperience; and (3) the experience of "
        "temporal continuity in the self. It is, however, the development of "
        "the first of these three aspects that Winnicott's work addresses "
        "most penetratingly.\n"
        "By integrating the works of Klein (1948), Erikson (1950a,b, 1958, "
        "1962), Jacobson (1964), and Mahler (1968, 1971, 1975) with his own "
        "views, Kernberg formulated a three-step process of identity "
        "formation. The first step in the process is introjection, whereby "
        "certain affectively charged, specific attributes of others are "
        "internalized without being fully assimilated.\n"
        "Greenacre (1958a,b) described a continuum from body image through "
        "self-image to identity. She emphasized that identity always "
        "involves relation to others."
    )
    _AUTHORS = [
        "Winnicott",
        "Kernberg",
        "Khan",
        "Klein",
        "Greenacre",
        "Erikson",
        "Jacobson",
        "Mahler",
    ]

    def test_khan_colon_bullet_flagged(self):
        """The EXACT Khan gap-fill bullet from the V18.20.3.0 run (source
        credits Winnicott; Khan only cited for 'corporeality')."""
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        bullet = (
            "Khan: Provided the developmental basis for authenticity, a deeply "
            "assimilated and personalized bodily foundation for one\u2019s "
            "self-experience (\u201ccorporeality\u201d), and the experience of "
            "temporal continuity in the self."
        )
        out, issues = detect_attribution_subject_swap(
            bullet, self._SOURCE, "bullet[35]", source_authors=self._AUTHORS
        )
        assert out == bullet  # flag-only
        swaps = [i for i in issues if i.detector == "attribution_swap"]
        assert swaps, "Khan colon-form misattribution must be flagged"
        assert "colon form" in swaps[0].detail
        assert "Winnicott" in swaps[0].detail

    def test_klein_colon_bullet_flagged(self):
        """The EXACT Klein gap-fill bullet from the V18.20.3.0 run (source
        credits Kernberg; Klein is inside the integration list)."""
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        bullet = (
            "Klein: Formulated a three-step process of identity formation by "
            "integrating his own views with the works of Erikson, Jacobson, "
            "and Mahler."
        )
        _, issues = detect_attribution_subject_swap(
            bullet, self._SOURCE, "bullet[32]", source_authors=self._AUTHORS
        )
        swaps = [i for i in issues if i.detector == "attribution_swap"]
        assert swaps, "Klein colon-form misattribution must be flagged"
        assert "Kernberg" in swaps[0].detail

    def test_correctly_attributed_colon_bullet_clean(self):
        """A bullet whose claimed author genuinely holds the verb in the
        source is NEVER flagged."""
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        bullet = (
            "Greenacre: Described a continuum from body image through "
            "self-image to identity, emphasizing relations to others."
        )
        _, issues = detect_attribution_subject_swap(
            bullet, self._SOURCE, "bullet[22]", source_authors=self._AUTHORS
        )
        assert not [i for i in issues if i.detector == "attribution_swap"]

    def test_non_attribution_verb_colon_bullets_ignored(self):
        """Colon bullets with non-attribution verbs (Made/Co-authored/
        Highlighted/Contributed/His…) are out of scope — no flag."""
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        for bullet in (
            "Stoller: Made significant contributions to gender identity consolidation (1968).",
            "Loewenstein: Co-authored metapsychological work with Hartmann and Kris (1946).",
            "Loewald: Highlighted the significant role of the father in psychic structuring.",
            "Searles: Contributed to the understanding of the second force of identity.",
            "Hartmann: His (1950) differentiation between ego and self was influential.",
            "Chasseguet-Smirgel: Her (1983, 1984) views on ego-ideal formation matter.",
        ):
            _, issues = detect_attribution_subject_swap(
                bullet, self._SOURCE, "bullet[X]", source_authors=self._AUTHORS
            )
            assert not [i for i in issues if i.detector == "attribution_swap"], (
                f"FP for: {bullet[:50]}"
            )

    def test_bold_and_dashed_bullet_forms_matched(self):
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        bullet = (
            "- **Khan**: Provided the developmental basis for authenticity "
            "and a deeply assimilated and personalized bodily foundation for "
            "one's self-experience and temporal continuity."
        )
        _, issues = detect_attribution_subject_swap(
            bullet, self._SOURCE, "bullet[35]", source_authors=self._AUTHORS
        )
        assert [i for i in issues if i.detector == "attribution_swap"]

    def test_past_tense_stems_cross_match(self):
        """'Provided' (bullet) must stem-match 'provides' (source)."""
        from core.summarisation.postcheck_detectors import _verb_stems

        assert _verb_stems("provided") & _verb_stems("provides")
        assert _verb_stems("Formulated") & _verb_stems("formulated")
        assert _verb_stems("described") & _verb_stems("describes")
        assert _verb_stems("supplied") & _verb_stems("supplies")

    def test_possessive_path_still_works(self):
        """V18.20.3.0's original possessive-form detection is unregressed."""
        from core.summarisation.postcheck_detectors import detect_attribution_subject_swap

        bullet = (
            "Khan's work provides the developmental basis for authenticity "
            "and a deeply assimilated and personalized bodily foundation for "
            "one's self-experience and temporal continuity in the self."
        )
        _, issues = detect_attribution_subject_swap(
            bullet, self._SOURCE, "bullet[35]", source_authors=self._AUTHORS
        )
        swaps = [i for i in issues if i.detector == "attribution_swap"]
        assert swaps, "possessive-form Khan misattribution must still be flagged"


# ═══════════════════════════════════════════════════════════════════════════
# 7) D4 — checkpoint DOCX log shows the FINAL path
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckpointDocxLogTruthfulPath:
    def test_builder_log_line_rewritten_to_final_path(self, tmp_path):
        """The builder logs the .tmp path it was handed; the checkpoint's
        log callback must rewrite it to the final .docx path."""
        from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

        captured_logs = []

        class _StubBuilder:
            def __init__(self, request, log_callback=None):
                self._log_cb = log_callback

            def build_report(self, summaries, chapters, input_path, out_path):
                # Mimic the real builder: logs the path it was GIVEN (tmp).
                self._log_cb(f"✅ DOCX saved to {out_path}", "SUCCESS")
                out_path.write_bytes(b"PK docx bytes")
                return True

        # Patch core.docx.builder.DocxBuilder (lazy import inside the method)
        import core.docx.builder as builder_mod

        real_builder = getattr(builder_mod, "DocxBuilder", None)
        builder_mod.DocxBuilder = _StubBuilder
        try:
            fake_converter = types.SimpleNamespace(
                _log=lambda msg, level="INFO": captured_logs.append((level, msg)),
                output_dir=tmp_path,
                paths=types.SimpleNamespace(summaries_dir=tmp_path / "summaries"),
                request=types.SimpleNamespace(input_path=tmp_path),
                _sanitize_filename=lambda h: "Ch1",
                checkpoint=None,
            )
            saver = ChapterCheckpointSaver(fake_converter, build_docx=True)
            summary = MagicMock()
            summary.chapter_heading = "Chapter One"
            out = saver._build_chapter_docx(
                summary,
                {"heading": "Chapter One", "content": "text"},
                tmp_path / "chapters" / "001_Ch1" / "001_Ch1_summary.docx",
            )
            assert out is not None and out.suffix == ".docx"
            assert out.exists()
            # The ONLY DOCX log line must reference the final path, never .tmp
            docx_logs = [m for _, m in captured_logs if "DOCX saved" in m]
            assert docx_logs, "builder log must pass through the callback"
            assert ".docx.tmp" not in docx_logs[0]
            assert str(out) in docx_logs[0]
        finally:
            if real_builder is not None:
                builder_mod.DocxBuilder = real_builder
            else:
                delattr(builder_mod, "DocxBuilder")


# ═══════════════════════════════════════════════════════════════════════════
# 8) D5 — quarantine summary logged once
# ═══════════════════════════════════════════════════════════════════════════


class _FakeQuarantine:
    def __init__(self):
        self.entries = []

    def add(self, bullet, stage="", reason="", chapter="", actually_dropped=False, **kw):
        self.entries.append(
            types.SimpleNamespace(
                bullet=bullet,
                stage=stage,
                reason=reason,
                actually_dropped=actually_dropped,
            )
        )

    def summary(self):
        out = {}
        for e in self.entries:
            out[e.stage] = out.get(e.stage, 0) + 1
        return out


class TestQuarantineLogDedupe:
    def test_repeated_calls_log_once(self, monkeypatch):
        """The gap-fill loop calls filter per added bullet: 8 clean calls
        after the first dropping call → the summary logs exactly ONCE."""
        import core.summarisation.post_processing as pp
        from core.summarisation.filter_thinking import filter_thinking_bullets

        def _classify(bullets, concepts=None, source_text=""):
            kept, drops = [], []
            for b in bullets:
                if "think" in str(b).lower() or "thinking is" in str(b).lower():
                    drops.append((b, "thinking_filter.truncated", "reason", True))
                else:
                    kept.append(b)
            return kept, drops

        monkeypatch.setattr(pp, "classify_bullets", _classify)
        q = _FakeQuarantine()
        logs = []

        # First call: one thinking bullet dropped → summary logs
        filter_thinking_bullets(
            ["Let me think about this more carefully"],
            quarantine=q,
            log=lambda m, l="INFO": logs.append(m),
            set_last_quarantined=lambda entries: None,
        )
        # Eight subsequent clean calls (the gap-fill pattern) → NO re-log
        for _ in range(8):
            filter_thinking_bullets(
                ["A perfectly clean bullet sentence."],
                quarantine=q,
                log=lambda m, l="INFO": logs.append(m),
                set_last_quarantined=lambda entries: None,
            )
        summary_logs = [m for m in logs if "Quarantine:" in m]
        assert len(summary_logs) == 1, f"expected 1, got {len(summary_logs)}: {summary_logs}"

    def test_new_drop_logs_again(self, monkeypatch):
        import core.summarisation.post_processing as pp
        from core.summarisation.filter_thinking import filter_thinking_bullets

        def _classify(bullets, concepts=None, source_text=""):
            kept, drops = [], []
            for b in bullets:
                if "think" in str(b).lower() or "thinking is" in str(b).lower():
                    drops.append((b, "thinking_filter.truncated", "reason", True))
                else:
                    kept.append(b)
            return kept, drops

        monkeypatch.setattr(pp, "classify_bullets", _classify)
        q = _FakeQuarantine()
        logs = []
        common = dict(
            quarantine=q,
            log=lambda m, l="INFO": logs.append(m),
            set_last_quarantined=lambda entries: None,
        )
        filter_thinking_bullets(["Let me think about this more carefully"], **common)
        filter_thinking_bullets(["Okay the thinking is as follows"], **common)
        summary_logs = [m for m in logs if "Quarantine:" in m]
        assert len(summary_logs) == 2

    def test_clean_quarantine_never_logs(self, monkeypatch):
        import core.summarisation.post_processing as pp
        from core.summarisation.filter_thinking import filter_thinking_bullets

        monkeypatch.setattr(
            pp,
            "classify_bullets",
            lambda bullets, concepts=None, source_text="": (list(bullets), []),
        )
        q = _FakeQuarantine()
        logs = []
        filter_thinking_bullets(
            ["A clean bullet."],
            quarantine=q,
            log=lambda m, l="INFO": logs.append(m),
            set_last_quarantined=lambda entries: None,
        )
        assert not [m for m in logs if "Quarantine:" in m]


# ═══════════════════════════════════════════════════════════════════════════
# 9) D7 — followup token budgets
# ═══════════════════════════════════════════════════════════════════════════


class TestFollowupTokenBudgets:
    # V18.20.3.2 (audit D7 follow-up): budgets raised 4096 -> 6144 (the
    # V18.20.3.1 real-rig run STILL hit the 4096 cap on both paths —
    # consolidation done_reason=length at 15,214 chars, scholar at 15,297).
    # These pins were re-based from 4096 to 6144 by the V18.20.3.2 release.

    def test_consolidation_budget_6144(self):
        src = (PROJECT_ROOT / "core" / "summarisation" / "bullet_consolidation.py").read_text(
            encoding="utf-8"
        )
        assert "max_tokens=6144" in src
        assert "max_tokens=4096" not in src
        assert "max_tokens=2048" not in src

    def test_scholar_budget_6144(self):
        src = (PROJECT_ROOT / "core" / "summarisation" / "scholar_reflection.py").read_text(
            encoding="utf-8"
        )
        assert "max_tokens=6144" in src
        assert "max_tokens=4096" not in src
        assert "max_tokens=3000" not in src

    def test_scholar_gap_fill_truncation_tail_dropped(self):
        """The scholar gap-fill parse reuses the D1 sanitizer on the
        unclosed <gap_fill_bullets> fallback."""
        from core.summarisation.response_parser import strip_truncated_section_tail

        gap_text = (
            "- A complete grounded bullet with a quote.\n- A cut bullet ending mid (parenthetical"
        )
        out = strip_truncated_section_tail(gap_text, closing_tag_present=False)
        assert "complete grounded" in out
        assert "parenthetical" not in out


# ═══════════════════════════════════════════════════════════════════════════
# 10) Regression guard — checkpoint core behaviour unchanged (D-fixes must
#     not disturb the V18.20.3.0 feature)
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckpointFeatureUnchanged:
    def test_render_summary_markdown_still_byte_identical_contract(self):
        """The canonical markdown (incl. COMPLETE sentinel + year styling)
        is the V18.20.3.0 contract — unchanged by this patch."""
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        summary = MagicMock()
        summary.chapter_heading = "1 - TEST"
        summary.executive_summary = "Exec with a citation (1919) inside."
        summary.bullet_points = ["Bullet with Tausk (1919) citation."]
        summary.thorough_summary = "Thorough text."
        summary.key_distinctions = "- One distinction."
        summary.theoretical_tensions = ""
        summary.scholar_reflections = ""
        md = render_summary_markdown(summary)
        assert md.startswith("# Summary: 1 - TEST")
        assert '<em style="font-size:0.9em">1919</em>' in md
        assert md.rstrip().endswith("<!-- COMPLETE -->")
        assert "## Key Distinctions" in md
