"""V0.11 (real-rig audit fixes) — regression tests for the Broken Structures
ch.1 audit findings.

The audit (see worklog AUDIT-1 / download/AUDIT-identity-and-origins-V0.10.md)
found the V0.10 rig shipped:
  * a ONE-SENTENCE "Thorough Summary" (the DOCX render salvaged exactly one
    claim whose quotes survived post-check quote-stripping, silently
    discarding ~1,050 words), because
  * the primary model returned a 25k-char claims-JSON that STRICT
    json.loads rejected (the model escaped single quotes Python-style inside
    "B'nai B'rith" — an invalid JSON escape), so the whole blob was banked
    as the thorough_summary (exec=0, bullets=0), while
  * the QA layers passed VACUOUSLY ("all 0 bullets verified ✓",
    "Self-review: all bullets confirmed" on an empty set), and
  * a domain textbook had been auto-switched to the academic_paper preset
    at 75% confidence, silently enabling Academic Rigor mode.

This file pins the V0.11 fixes:
  1. ``_repair_llm_json`` — the lenient repair pass (\\', smart quotes,
     trailing commas).
  2. ``parse_response`` claims-JSON handling — big claim lists mirror to
     bullets; the repaired blob NEVER lands in thorough.
  3. The leftover-fallback JSON guard — an unrepairable claims blob is
     salvaged to bullets, never banked as thorough.
  4. ``DocxBuilder._render_structured_summary`` — the lossy claim-hijack is
     gone (prose is never hijacked; a lossy salvage ships the full text).
  5. Vacuous-QA warnings (0-bullet fact-check; 0-bullet self-review skip).
  6. gap-fill attribution-fidelity rules in the batch prompt.
  7. The academic_paper auto-switch confidence bar.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.summarisation.response_parser import (
    _repair_llm_json,
    _salvage_json_claims,
    parse_response,
)

# ═══════════════════════════════════════════════════════════════════════════
# 1. _repair_llm_json
# ═══════════════════════════════════════════════════════════════════════════


class TestRepairLlmJson:
    def test_invalid_single_quote_escape_repaired(self):
        """THE rig failure: the model escaped ' Python-style inside
        "B'nai B'rith" — invalid strict JSON."""
        raw = '{"claim": "Freud addressed B\\\'nai B\\\'rith in 1926a."}'
        # sanity: the rig premise — strict parsing REJECTS this
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)
        repaired = _repair_llm_json(raw)
        assert "\\'" not in repaired
        assert "B'nai B'rith" in repaired
        data = json.loads(repaired)
        assert data["claim"] == "Freud addressed B'nai B'rith in 1926a."

    def test_smart_quotes_normalized(self):
        raw = '{\u201cclaim\u201d: \u201cSmart-quoted claim text.\u201d}'
        data = json.loads(_repair_llm_json(raw))
        assert data["claim"] == "Smart-quoted claim text."

    def test_trailing_commas_removed(self):
        raw = '{"executive_summary": [{"claim": "A claim."},],}'
        data = json.loads(_repair_llm_json(raw))
        assert data["executive_summary"][0]["claim"] == "A claim."

    def test_valid_json_untouched_semantics(self):
        raw = '{"executive_summary": [{"claim": "Valid claim with apostrophe: it\'s fine."}]}'
        data = json.loads(_repair_llm_json(raw))
        assert data["executive_summary"][0]["claim"].endswith("it's fine.")


# ═══════════════════════════════════════════════════════════════════════════
# 2. parse_response: the rig's claims-JSON shape
# ═══════════════════════════════════════════════════════════════════════════


def _rig_claims_blob(n_claims: int = 15, with_bad_escape: bool = True) -> str:
    """Build the rig-shaped claims JSON: one executive_summary array of
    claim/supporting_text/source_reference dicts. With ``with_bad_escape``
    one claim carries the Python-style \\' escape that broke strict parsing."""
    items = []
    for i in range(1, n_claims + 1):
        if with_bad_escape and i == 3:
            claim = (
                "Freud referred to identity only once, in his address to "
                "B\\'nai B\\'rith (1926a)."
            )
        else:
            claim = (
                f"Claim {i}: the chapter discusses psychoanalytic concept "
                f"{i} and its contribution to identity formation."
            )
        items.append(
            '{"claim": "' + claim + '", '
            '"supporting_text": "Supporting passage number ' + str(i) + '.", '
            '"source_reference": "p. ' + str(14 + i) + '"}'
        )
    return (
        '{"executive_summary": [' + ", ".join(items) + '], '
        '"key_distinctions": [], "theoretical_tensions": []}'
    )


class TestParseClaimsJsonBlob:
    def test_rig_shape_bad_escape_recovered_not_banked_as_thorough(self):
        """The exact V0.10 rig failure: strict decode fails on \\' → the
        V0.11 repair pass recovers the blob → claims become BULLETS (a
        15-claim "executive" is a takeaway list), exec is left empty for the
        exec-from-thorough derivation, and the raw JSON NEVER lands in
        thorough_summary."""
        raw = _rig_claims_blob(15, with_bad_escape=True)
        # sanity: the blob really is strict-invalid (the rig premise)
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

        r = parse_response(raw)

        # claims mirrored to bullets — all 15 survive
        assert len(r["bullet_points"]) == 15
        assert any("B'nai B'rith" in bp for bp in r["bullet_points"])
        # exec left empty (derivation produces real prose downstream)
        assert r["executive_summary"] == ""
        # THE CONTRACT: no raw JSON banked as thorough
        assert '"claim"' not in (r["thorough_summary"] or "")
        assert (r["thorough_summary"] or "").strip() == ""

    def test_small_claim_list_keeps_v13_34_1_behavior(self):
        """A SMALL claim list (the pinned academic-mode shape) still joins
        into the executive summary — no mirror, no emptying."""
        raw = (
            '{"executive_summary": ['
            '{"claim": "Identity is a key psychoanalytic concept.", '
            '"supporting_text": "...", "source_reference": "p.1"}'
            ']}'
        )
        r = parse_response(raw)
        assert "Identity is a key psychoanalytic concept" in r["executive_summary"]
        assert r["bullet_points"] == []

    def test_valid_strict_claims_blob_also_mirrors_large_lists(self):
        """The mirror rule lives in the shared extractor — a VALID strict
        JSON with a large claim list mirrors too (format-agnostic)."""
        raw = _rig_claims_blob(14, with_bad_escape=False)
        json.loads(raw)  # sanity: strict-valid
        r = parse_response(raw)
        assert len(r["bullet_points"]) == 14
        assert r["executive_summary"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# 3. The leftover-fallback JSON guard (unrepairable blob)
# ═══════════════════════════════════════════════════════════════════════════


class TestLeftoverJsonGuard:
    def _truncated_blob(self) -> str:
        """A claims blob truncated mid-string at the output cap — no closing
        brackets, unrepairable by _repair_llm_json."""
        return (
            '{"executive_summary": ['
            '{"claim": "First claim about identity diffusion in borderline patients.", '
            '"supporting_text": "The growing number of borderline patients.", '
            '"source_reference": "p. 15"}, '
            '{"claim": "Second claim about Tausk introducing identity in 1919.", '
            '"supporting_text": "The term identity was introduced", '
            '"source_reference": "p. 15"}, '
            '{"claim": "Third claim about Erikson resurrecting the term.", '
            '"supporting_text": "In the 1950s Erikson'
        )

    def test_unrepairable_blob_never_becomes_thorough(self):
        r = parse_response(self._truncated_blob())
        # THE CONTRACT (BUG-THOROUGH-LOSS): the raw JSON blob is never
        # banked as the thorough_summary.
        assert (r["thorough_summary"] or "").strip() == ""
        # the claims are salvaged to bullets instead
        assert len(r["bullet_points"]) >= 3
        assert any("Tausk" in bp for bp in r["bullet_points"])

    def test_plain_prose_leftover_still_banks_as_thorough(self):
        """Regression guard: ordinary leftover prose (no JSON smell) keeps
        the legacy leftover-thorough behaviour."""
        raw = "Just a plain paragraph of thorough-style prose. It has no tags at all."
        r = parse_response(raw)
        assert "plain paragraph" in (r["thorough_summary"] or "")

    def test_salvage_handles_quote_stripped_values(self):
        """The post-check-mangled shape: claim values whose quotes were
        stripped by quote-verification (unquoted values)."""
        mangled = (
            '{"executive_summary": [{"claim": The chapter addresses identity '
            'diffusion in borderline patients., "supporting_text": x}, '
            '{"claim": Blos proposed a biphasic resolution., "supporting_text": y}]}'
        )
        claims = _salvage_json_claims(mangled)
        assert any("identity diffusion" in c for c in claims)
        assert any("biphasic" in c.lower() for c in claims)


# ═══════════════════════════════════════════════════════════════════════════
# 4. DocxBuilder._render_structured_summary — the one-sentence collapse
# ═══════════════════════════════════════════════════════════════════════════


class TestDocxStructuredRenderGuard:
    @pytest.fixture()
    def render(self):
        from core.docx.builder import DocxBuilder

        # _render_structured_summary is self-free (static in behaviour);
        # bind it without running DocxBuilder.__init__ (which needs a request).
        return DocxBuilder._render_structured_summary.__get__(
            object.__new__(DocxBuilder)
        )

    def test_prose_containing_the_word_claim_is_not_hijacked(self):
        """Pre-fix, ANY prose containing '"claim"' was hijacked by the
        JSON-key regex and replaced by whatever claims the regex found
        (often none → empty string)."""
        text = (
            "The chapter develops a detailed claim about identity formation. "
            'Erikson\'s notion of "claim and counter-claim" in identity '
            "research is discussed across several paragraphs of flowing prose."
        )
        from core.docx.builder import DocxBuilder

        out = DocxBuilder._render_structured_summary(
            object.__new__(DocxBuilder), text
        )
        assert out == text

    def test_mangled_json_thorough_ships_full_text_not_one_claim(self):
        """THE rig collapse: pseudo-JSON where only ONE claim value kept its
        quotes (post-check quote-stripping removed the rest). Pre-fix the
        DOCX thorough rendered as that single sentence; now the full text
        ships (a lossy extraction is worse than mangled-but-complete)."""
        mangled = (
            '{"executive_summary": [{"claim": The chapter addresses identity '
            "diffusion in borderline and narcissistic patients by examining "
            "the developmental origins of personal identity across a long "
            "series of psychoanalytic frameworks and contributors., "
            '"supporting_text": "The growing number of borderline patients.", '
            '"source_reference": "p. 15"}, {"claim": '
            '"Blos proposed a biphasic resolution of the Oedipus complex."'
            ', "source_reference": "p. 31"}]}'
        )
        from core.docx.builder import DocxBuilder

        out = DocxBuilder._render_structured_summary(
            object.__new__(DocxBuilder), mangled
        )
        # NOT the one-sentence collapse
        assert out != "Blos proposed a biphasic resolution of the Oedipus complex."
        # the full mangled text ships (complete beats lossy)
        assert "developmental origins of personal identity" in out

    def test_genuine_claims_json_still_extracts(self):
        """A genuine, fully-quoted claims payload still extracts the claims
        (the salvage covers ~all of the input)."""
        payload = (
            '{"executive_summary": ['
            '{"claim": "First claim of the payload."}, '
            '{"claim": "Second claim of the payload."}, '
            '{"claim": "Third claim of the payload."}]}'
        )
        from core.docx.builder import DocxBuilder

        out = DocxBuilder._render_structured_summary(
            object.__new__(DocxBuilder), payload
        )
        assert "First claim of the payload." in out
        assert "Third claim of the payload." in out

    def test_xml_claim_tags_still_extract(self):
        text = "<claim>XML claim one.</claim>\n<claim>XML claim two.</claim>"
        from core.docx.builder import DocxBuilder

        out = DocxBuilder._render_structured_summary(
            object.__new__(DocxBuilder), text
        )
        assert "XML claim one." in out and "XML claim two." in out


# ═══════════════════════════════════════════════════════════════════════════
# 5. Vacuous-QA warnings
# ═══════════════════════════════════════════════════════════════════════════


class TestVacuousQA:
    def test_zero_bullet_fact_check_is_loud_vacuous_warning(self):
        from core.summarisation.summary_validator import verify_bullets

        logged: list[tuple[str, str]] = []

        def log(msg, level="INFO"):
            logged.append((level, msg))

        out = verify_bullets(
            bullets=[],
            source_text="some source text",
            verify_windows_cache={},
            quarantine=None,
            log=log,
            chapter="Ch 1",
        )
        assert out == []
        vacuous = [m for lvl, m in logged if "VACUOUS PASS" in m]
        assert vacuous, f"expected a VACUOUS PASS warning, got: {logged}"
        # level check (explicit): a vacuous pass must be a WARNING, not a ✓
        assert any(
            lvl == "WARNING" and "VACUOUS PASS" in m for lvl, m in logged
        )

    def test_self_review_skipped_on_zero_bullets(self):
        """The V0.10 rig burned ~4 GPU-minutes 'confirming' an empty bullet
        set. V0.11 skips the LLM call entirely and logs a WARNING."""
        from core.summarisation.bullet_pipeline import BulletPipeline

        calls: list[str] = []
        logged: list[tuple[str, str]] = []

        class _StubS:
            self_consistency = False
            provider = "llamacpp"  # != "ollama" → skips the self-consistency block
            academic_rigor = True
            temperature = 0.7
            _last_coverage = 1.0

            def log(self, msg, level="INFO"):
                logged.append((level, msg))

            def _recover_vram(self, context="", delay_sec=0.0):
                pass

            def _self_review(self, heading, text, summary):
                calls.append("_self_review")
                return None

            def _self_review_batched(self, heading, text, bullets, thorough):
                calls.append("_self_review_batched")
                return None

            def _strip_thinking(self, x):
                return x

        pipe = BulletPipeline(_StubS())
        state = type("State", (), {"__dict__": {}})()
        result = {"bullet_points": [], "executive_summary": "", "thorough_summary": ""}
        pipe.run_self_consistency_and_review(state, result, "Ch 1", "text")

        assert calls == [], "self-review LLM call must NOT fire with 0 bullets"
        assert any(
            "SKIPPED" in m and lvl == "WARNING" for lvl, m in logged
        ), f"expected skip WARNING, got: {logged}"

    def test_self_review_still_runs_with_bullets(self):
        from core.summarisation.bullet_pipeline import BulletPipeline

        calls: list[str] = []
        logged: list[tuple[str, str]] = []

        class _StubS:
            self_consistency = False
            provider = "llamacpp"
            academic_rigor = True
            temperature = 0.7
            _last_coverage = 1.0

            def log(self, msg, level="INFO"):
                logged.append((level, msg))

            def _recover_vram(self, context="", delay_sec=0.0):
                pass

            def _self_review(self, heading, text, summary):
                calls.append("_self_review")
                return None

            def _self_review_batched(self, heading, text, bullets, thorough):
                calls.append("_self_review_batched")
                return None

            def _strip_thinking(self, x):
                return x

        pipe = BulletPipeline(_StubS())
        state = type("State", (), {"__dict__": {}})()
        result = {
            "bullet_points": ["A real bullet."],
            "executive_summary": "",
            "thorough_summary": "",
        }
        pipe.run_self_consistency_and_review(state, result, "Ch 1", "text")
        assert calls == ["_self_review"], "self-review must still run with bullets"


# ═══════════════════════════════════════════════════════════════════════════
# 6. gap-fill batch prompt: attribution-fidelity rules (audit F1-F5)
# ═══════════════════════════════════════════════════════════════════════════


class TestGapFillAttributionRules:
    def test_batch_prompt_carries_attribution_rules(self):
        from core.summarisation.gap_fill_batch import batch_gap_fill

        prompts: list[str] = []
        logged: list[tuple[str, str]] = []

        def fake_call_fast_llm(prompt, max_tokens=2000, temperature=0.7):
            prompts.append(prompt)
            return (
                "- Fromm: explored the sociocultural determinants of identity.\n"
                "- Wheelis: examined sociocultural dimensions of identity."
            )

        def fake_check_coverage(analysis, text):
            covered = [a for a in ("Fromm", "Wheelis") if a in text]
            missing = [a for a in ("Fromm", "Wheelis") if a not in text]
            pct = len(covered) / 2
            return {"covered": covered, "missing": missing, "total": 2,
                    "coverage_pct": pct}

        batch_gap_fill(
            "1 - IDENTITY AND ITS ORIGINS",
            "Fromm (1955) was prominent in exploring the sociocultural "
            "determinants of personal identity. Wheelis (1958) contributed "
            "to understanding the sociocultural dimensions of identity "
            "formation in his later work on character and society.",
            [],
            ["Fromm", "Wheelis"],
            "analysis text naming Fromm and Wheelis",
            ["Fromm", "Wheelis"],
            check_coverage=fake_check_coverage,
            call_fast_llm=fake_call_fast_llm,
            temperature=0.7,
            strip_thinking=lambda x: x,
            filter_thinking_bullets=lambda bullets, concepts=None, source_text="": bullets,
            log=lambda msg, level="INFO": logged.append((level, msg)),
        )
        assert prompts, "the gap-fill LLM call must have fired"
        p = prompts[0]
        assert "Attribution rules (STRICT)" in p
        assert "ONLY what the source excerpt attributes to THAT author" in p
        assert "Never invent causal links" in p
        assert "EXACTLY as they appear in the source excerpt" in p


# ═══════════════════════════════════════════════════════════════════════════
# 7. academic_paper auto-switch confidence bar (source-pin + logic)
# ═══════════════════════════════════════════════════════════════════════════


class TestAcademicAutoSwitchGuard:
    def test_source_pins_the_confidence_bar(self):
        """House source-pin style: the 0.85 academic-switch bar + the
        keep-normal_book branch exist in postprocess.py."""
        src = Path("core/pipeline/conversion/postprocess.py").read_text(
            encoding="utf-8"
        )
        assert "_acad_min_conf = 0.85" in src
        assert re.search(
            r"detection\.content_type == \"academic_paper\"\s*\n\s*and "
            r"detection\.confidence < _acad_min_conf",
            src,
        ), "the academic_paper < 0.85 keep-normal_book branch must exist"
        assert "keeping normal_book preset" in src

    def test_rig_confidence_would_not_switch(self):
        """The rig's exact numbers (75% confidence, academic_paper) stay on
        normal_book under the V0.11 bar."""
        _acad_min_conf = 0.85
        rig_confidence = 0.75
        assert rig_confidence < _acad_min_conf

    def test_other_types_keep_recommended_bar(self):
        """Non-academic detections are NOT affected by the 0.85 bar."""
        src = Path("core/pipeline/conversion/postprocess.py").read_text(
            encoding="utf-8"
        )
        # the 0.85 bar is scoped to academic_paper only (inside the branch)
        assert 'detection.content_type == "academic_paper"' in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
