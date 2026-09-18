"""V0.05 — real-rig audit fixes (97-Things run 20260918-043932, llama.cpp +
Ternary-Bonsai-2-27B, user samples 001-006 of 10).

This batch pins the EIGHT sanctioned audit findings (F1-F8) PLUS the new
bug the user reported after reading the audit — which the audit MISSED:

  F9a (P0)  Unrequested "Thorough Summary" produced anyway. The user's
            wizard selection was `Outputs: exec_summary, keypoints, docx`
            (logged by settings_logger — the flag was correctly recorded)
            yet every shipped file contained a Thorough Summary: the
            include_* flags were logged but NEVER enforced (prompt
            building, expansion calls, re-derivation, rendering all
            ignored them).
  F9b (P0)  Thorough sections LONGER than their chapters. Measured on the
            rig: 549-940-word thorough sections for 321-441-word chapters
            (1.55x-2.76x the source). Three absolute-length engines forced
            it: the prompt's "800-1200 word" demand, the hardcoded
            800-word expansion floor (a dedicated LLM call FORCING the
            model to write more than the source contains), and the
            <30-bullets expansion. Instructing a model to exceed its
            source is hallucination-by-instruction — the rig's thorough
            sections contain invented elaborations the source never states.

GENERAL rules pinned here (the book is only the test that exposed them):
  - a summary section may never be instructed (or allowed) to exceed a
    fraction of its source — every target SCALES (length_policy);
  - the user's output-selection flags are the contract, end-to-end;
  - provider decodes pin UTF-8 (charset-less text/event-stream decodes
    latin-1 otherwise);
  - self-assessment critique is detected STRUCTURALLY, not by phrase list;
  - ONE coverage matcher everywhere; the remediation unit is the sentence;
  - run-scoped output (nothing from an old run ships beside the new one).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── hermetic tiktoken gate (house pattern) ─────────────────────────────────
if "tiktoken" not in sys.modules:
    try:
        import tiktoken  # type: ignore  # noqa: F401
    except ImportError:
        _tk = types.ModuleType("tiktoken")
        _tk.get_encoding = lambda *a, **k: None  # type: ignore[attr-defined]
        _tk.Encoding = object  # type: ignore[attr-defined]
        sys.modules["tiktoken"] = _tk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# markitdown is not installed in this sandbox; the stub keeps the eager
# core.pipeline → core.pdf import chains loadable (V0.03 house pattern).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

from core.models.models import (  # noqa: E402
    ConversionRequest,
    SummaryResult,
)


def _src(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments + inline fragments so pins assert CODE."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════
# F1 (P0) — UTF-8 pinned on every llama.cpp decode (streaming mojibake)
# ═══════════════════════════════════════════════════════════════════════════

# The rig's exact mojibake payload class: typographic characters whose UTF-8
# bytes latin-1-decode into the observed â€™ / â€” / â€œ shapes.
_NON_ASCII_PAYLOAD = (
    "The engineer’s career needs — customer’s trust “matters” more "
    "than the author’s résumé…"
)


class TestF1Utf8Pin:
    @pytest.fixture
    def nonascii_server(self):
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv = MockLlamaCppServer(
            models=["Ternary-Bonsai-2-27B-Instruct-Vision"],
            response_text=_NON_ASCII_PAYLOAD,
        ).start()
        try:
            yield srv
        finally:
            srv.stop()

    def _provider(self, srv):
        from core.llm.llamacpp_provider import LlamaCppProvider

        return LlamaCppProvider(
            model="Ternary-Bonsai-2-27B-Instruct-Vision",
            base_url=srv.base_url,
            api_key="local",
            max_tokens=256,
            context_tokens=65536,
            timeout=30,
            retries=0,
        )

    def test_streaming_roundtrips_typographic_chars(self, nonascii_server):
        """The EXACT rig failure: charset-less text/event-stream decoded as
        latin-1 turned ’ into â€™. With the pin, the streamed text is the
        payload byte-for-byte."""
        p = self._provider(nonascii_server)
        out = p.complete("summarize")
        assert out is not None
        # the mock appends one trailing space per word — compare stripped
        assert out.strip() == _NON_ASCII_PAYLOAD, (
            "streamed decode must round-trip typographic characters — "
            f"got mojibake: {out[:60]!r}"
        )
        assert "â€" not in out

    def test_nonstreaming_roundtrips_typographic_chars(self, nonascii_server):
        p = self._provider(nonascii_server)
        out = p._chat_nonstreaming({
            "model": p.model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 64,
            "temperature": 0.1,
            "stream": False,
        })
        assert out == _NON_ASCII_PAYLOAD
        assert "â€" not in out

    def test_probe_and_models_pin_utf8(self, nonascii_server):
        from core.llm.llamacpp_provider import (
            list_llamacpp_models,
            test_llamacpp_connection,
        )

        ok, msg = test_llamacpp_connection(
            nonascii_server.base_url, "local",
            "Ternary-Bonsai-2-27B-Instruct-Vision",
        )
        assert ok, msg
        # a served model id with a typographic char round-trips too
        from tests.mock_llamacpp_server import MockLlamaCppServer

        srv2 = MockLlamaCppServer(models=["Bonsai-27B-vision’"]).start()
        try:
            assert "Bonsai-27B-vision’" in list_llamacpp_models(srv2.base_url)
        finally:
            srv2.stop()

    def test_source_pin_every_decode_site(self):
        """Every response decode in the provider pins UTF-8 before text
        access (streaming, non-streaming, error body, model list)."""
        src = _strip_comments(_src("core/llm/llamacpp_provider.py"))
        assert src.count('resp.encoding = "utf-8"') >= 1
        assert "_pin_utf8" in src
        # every .json()/.text/iter_lines access site is preceded by a pin
        import re as _re

        for m in _re.finditer(r"resp\.(?:json\(\)|text\b|iter_lines\()", src):
            line_no = src[: m.start()].count("\n")
            window = "\n".join(src.splitlines()[max(0, line_no - 6): line_no])
            if m.group(0).startswith("resp.iter_lines"):
                assert "_pin_utf8(resp)" in window or "_pin_utf8" in window, (
                    f"iter_lines at line {line_no + 1} is not UTF-8 pinned"
                )


# ═══════════════════════════════════════════════════════════════════════════
# F9b (P0) — source-relative length policy
# ═══════════════════════════════════════════════════════════════════════════


class TestLengthPolicy:
    def test_thorough_target_never_exceeds_source(self):
        from core.summarisation.length_policy import thorough_target

        for w in (100, 200, 340, 430, 800, 1500, 3000, 10000):
            lo, hi = thorough_target(w)
            assert lo <= hi
            assert hi <= max(w, 120), (
                f"thorough target {hi} exceeds its {w}-word source"
            )
            assert hi <= 1200, "the historical 1200 ceiling is a hard cap"

    def test_rig_chapters_get_tiny_targets(self):
        """The measured rig chapters (321-441 words) must be targeted at a
        FRACTION of their length — not 800-1200."""
        from core.summarisation.length_policy import thorough_target

        for w in (321, 340, 430, 441):
            _lo, hi = thorough_target(w)
            assert hi <= 220, f"a {w}-word chapter must not be told to write {hi} words"

    def test_big_chapters_keep_the_documented_ceiling(self):
        from core.summarisation.length_policy import thorough_target

        lo, hi = thorough_target(3000)
        assert hi == 1200
        assert lo == 720

    def test_bullet_target_scales(self):
        """V0.07 (output-regression fix): one takeaway per ~25 words.

        At the V0.05 constant (50) a 1000-word chapter was capped at 20
        bullets where V18 delivered 30-40 (the user-reported bullet
        collapse). At 25: 340 words -> 9-14 (still bounded — no restating);
        1000 words -> 27-40 (V18 parity).
        """
        from core.summarisation.length_policy import bullet_target

        blo, bhi = bullet_target(340)
        assert 9 <= blo <= bhi <= 14, (
            f"a 340-word chapter targets 9-14 bullets, got {blo}-{bhi}"
        )
        assert bullet_target(3000)[0] >= 20
        assert bullet_target(20000)[1] == 40
        # V0.07 regression pin: a normal chapter must reach V18's 30-40
        lo_1k, hi_1k = bullet_target(1000)
        assert hi_1k == 40 and lo_1k >= 27, (
            f"a 1000-word chapter must target 27-40 bullets (V18 parity), "
            f"got {lo_1k}-{hi_1k}"
        )

    def test_exec_target_scales(self):
        from core.summarisation.length_policy import executive_target

        assert executive_target(340)[1] <= 90
        assert executive_target(3000) == (150, 250)

    def test_expansion_audit_flags_the_rig_case(self):
        """The user's own proof: 005's thorough (911w) vs its chapter
        (408w) must be flagged as expansion."""
        from core.summarisation.length_policy import expansion_audit

        findings = expansion_audit(408, 180, 911)
        assert any("2.2x" in f for f in findings), findings
        # a well-scaled thorough is silent
        assert expansion_audit(408, 60, 160) == []

    def test_budget_block_states_the_contract(self):
        from core.summarisation.length_policy import length_budget_block

        block = length_budget_block(340, True, True, True)
        assert "approximately 340 words" in block
        assert "SHORTER than the chapter itself" in block or "SHORTER" in block
        assert "NEVER pad" in block

    def test_backstop_replaces_legacy_absolutes(self):
        from core.summarisation.length_policy import apply_backstop

        out = apply_backstop(
            "An 800-1200 word detailed analysis with a 150-250 word overview "
            "and 20-40 distinct takeaways and a 1000-1500 word analysis",
            340,
        )
        assert "800-1200" not in out
        assert "1000-1500" not in out
        assert "150-250" not in out
        assert "20-40 distinct" not in out
        # no double-"word" bug in the replacement
        import re as _re

        assert not _re.search(r"word\s+word", out), out

    def test_templates_use_scaled_placeholders(self):
        for name in ("default", "academic", "technical", "creative",
                     "default_lowbit"):
            t = _src(f"prompts/{name}.md")
            assert "{{thorough_words}}" in t, f"{name}.md must scale the thorough target"
            assert "800-1200" not in t, f"{name}.md still carries the absolute demand"
        assert "{{thorough_words}}" in _src(
            "prompts/summarisation/two_pass_synthesize.md")

    def test_render_substitutes_scaled_targets(self, tmp_path, monkeypatch):
        """PromptManager.render computes the scaled numbers from the chapter
        text and substitutes them (and the backstop catches legacy copies)."""
        from contextlib import contextmanager

        @contextmanager
        def _user_dir(tmp):
            yield tmp

        from core.summarisation.prompt_manager import PromptManager

        pm = PromptManager()
        chapter = "word " * 340  # a 340-word chapter
        rendered = pm.render("default", "Ch.1", chapter, "Write in English.")
        assert rendered is not None
        assert "800-1200" not in rendered
        assert "20-40 distinct" not in rendered
        import re as _re

        assert _re.search(r"\b\d+-\d+ word detailed analysis", rendered)
        assert _re.search(r"\b\d+-\d+ distinct key takeaways", rendered)

    def test_f1_validation_caps_scale_to_source(self):
        """The F1 truncation caps scale (340-word source → ~150-190-word
        thorough cap, NOT 1500)."""
        from core.summarisation import bullet_pipeline as bp

        saw = {}

        class _S:
            def log(self, msg, level="DEBUG"):
                saw.setdefault("msgs", []).append(msg)

        class _State:
            content = "word " * 340
            exec_sum = "one " * 500   # 500 words — over any scaled exec cap
            thorough = "big " * 900   # 900 words — over any scaled thorough cap

        pipe = bp.BulletPipeline.__new__(bp.BulletPipeline)
        pipe.s = _S()
        before = _State.exec_sum, _State.thorough
        bp.BulletPipeline.apply_f1_length_validation(pipe, _State)
        assert len(_State.exec_sum.split()) < 120, "exec must be truncated at a scaled cap"
        assert len(_State.thorough.split()) < 240, "thorough must be truncated at a scaled cap"
        assert any("source=340w" in m for m in saw["msgs"]), saw["msgs"]
        assert any("ratio" in m for m in saw["msgs"]), (
            "the honest expansion-ratio line must be logged"
        )

    def test_thorough_expansion_threshold_is_source_scaled(self):
        """Source pin (V0.07 output-regression fix): regime-split — normal
        chapters (scaled thorough hi >= 800) expand below 800 words (V18's
        contract); small sources keep the source-scaled lo (the 97-Things
        anti-padding rule), never a flat 800 for everything."""
        src = _strip_comments(_src("core/summarisation/summarizer.py"))
        assert "(800 if _th_hi_lp >= 800 else _th_lo_lp)" in src, (
            "the expansion threshold must be regime-split (V18: 800 for "
            "normal chapters, source-scaled for small ones)"
        )

    def test_bullet_expansion_threshold_is_source_scaled(self):
        src = _strip_comments(_src("core/summarisation/summarizer.py"))
        assert "len(bullets) < _bp_lo_lp" in src
        assert "len(bullets) < 30" not in src

    def test_theorist_floor_budget_gate(self):
        """The 150-300-word append skips when the thorough already meets its
        scaled ceiling (source pin + behaviour)."""
        src = _strip_comments(_src("core/summarisation/thorough_theorist_floor.py"))
        assert "scaled_target_hi" in src
        assert "_tf_words >= int(scaled_target_hi)" in src


# ═══════════════════════════════════════════════════════════════════════════
# F9a (P0) — output-selection flags enforced end-to-end
# ═══════════════════════════════════════════════════════════════════════════


class TestF9aFlagEnforcement:
    def _make_summarizer(self, monkeypatch, include_thorough=True,
                         include_exec=True, include_keypoints=True):
        class _FakeSettings:
            def get(self, key, default=None):
                if key == "summarisation.provider":
                    return "ollama"
                return default

        monkeypatch.setattr(
            "core.summarisation.summarizer.Settings", lambda: _FakeSettings())
        monkeypatch.setattr("utils.settings.Settings", lambda: _FakeSettings())
        from core.summarisation.summarizer import Summarizer

        req = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        req.summarisation_model = "gemma3:12b"
        req.include_thorough_summary = include_thorough
        req.include_executive_summary = include_exec
        req.include_keypoints = include_keypoints
        return Summarizer(
            request=req, log_callback=lambda m, l="INFO": None,
            language="en", claim_extractor=None,
        )

    def test_thorough_disabled_not_in_prompt(self, monkeypatch):
        """The user's exact complaint: they unchecked Thorough summary —
        the prompt must not demand <thorough_summary>."""
        s = self._make_summarizer(monkeypatch, include_thorough=False)
        text = "A chapter about balancing technical requirements. " * 12
        prompt = s._build_prompt("Ch.1", text)
        assert "<thorough_summary>" not in prompt, (
            "the spec block for an unrequested section must be stripped"
        )
        assert "thorough_summary:" not in prompt
        assert "OUTPUT SECTIONS (OVERRIDES" in prompt

    def test_all_sections_present_when_enabled(self, monkeypatch):
        s = self._make_summarizer(monkeyparser := monkeypatch)
        text = "A chapter about balancing technical requirements. " * 12
        prompt = s._build_prompt("Ch.1", text)
        assert "<thorough_summary>" in prompt
        assert "<bullet_points>" in prompt
        assert "<executive_summary>" in prompt

    def test_keypoints_disabled_not_in_prompt(self, monkeypatch):
        s = self._make_summarizer(monkeypatch, include_keypoints=False)
        text = "A chapter about balancing technical requirements. " * 12
        prompt = s._build_prompt("Ch.1", text)
        assert "<bullet_points>" not in prompt

    def test_exec_disabled_not_in_prompt(self, monkeypatch):
        s = self._make_summarizer(monkeypatch, include_exec=False)
        text = "A chapter about balancing technical requirements. " * 12
        prompt = s._build_prompt("Ch.1", text)
        assert "<executive_summary>" not in prompt

    def test_prompt_carries_length_budget(self, monkeypatch):
        s = self._make_summarizer(monkeypatch)
        text = "A chapter about balancing technical requirements. " * 12
        prompt = s._build_prompt("Ch.1", text)
        assert "LENGTH BUDGET" in prompt

    def test_chunked_prompt_respects_flags(self, monkeypatch):
        from core.summarisation.prompt_assembly import build_chunked_prompt

        full = (
            "You MUST output exactly these XML sections:\n\n"
            "<executive_summary>\nA overview.\n</executive_summary>\n\n"
            "<bullet_points>\nBullets.\n</bullet_points>\n\n"
            "<thorough_summary>\nAnalysis.\n</thorough_summary>\n\n"
            "<key_distinctions>\nD.\n</key_distinctions>\n\n"
            "<theoretical_tensions>\nT.\n</theoretical_tensions>\n\n"
            "Chapter content:\nSome chapter text here."
        )
        out = build_chunked_prompt(
            "Ch.1", "Some chapter text here.", full, chunk=1,
            include_thorough=False,
        )
        assert "<thorough_summary>" not in out
        assert "<executive_summary>" in out
        # V0.05 fix: the chunk override must not eat the chapter content
        assert "Chapter content:" in out

    def test_chunked_prompt_never_eats_chapter_content(self):
        from core.summarisation.prompt_assembly import build_chunked_prompt

        full = (
            "You MUST output exactly these XML sections:\n\n"
            "<executive_summary>\nA overview.\n</executive_summary>\n\n"
            "<thorough_summary>\nAnalysis.\n</thorough_summary>\n\n"
            "<key_distinctions>\nD.\n</key_distinctions>\n\n"
            "<theoretical_tensions>\nT.\n</theoretical_tensions>\n\n"
            "Chapter content:\nTHE CHAPTER BODY THAT MUST SURVIVE."
        )
        out = build_chunked_prompt("Ch.1", "body", full, chunk=1)
        assert "THE CHAPTER BODY THAT MUST SURVIVE." in out, (
            "the old to-end-of-string replacement ate the chapter content"
        )

    def test_render_omits_empty_sections(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        summ = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="Exec text.",
            bullet_points=["Bullet one.", "Bullet two."],
            thorough_summary="",  # thorough disabled → empty
        )
        md = render_summary_markdown(summ)
        assert "## Executive Summary" in md
        assert "## Key Takeaways" in md
        assert "## Thorough Summary" not in md, (
            "an unrequested/empty section must not ship a heading"
        )
        assert md.rstrip().endswith("<!-- COMPLETE -->")

    def test_render_full_summary_is_legacy_identical(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        summ = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="Exec text.",
            bullet_points=["Bullet one."],
            thorough_summary="Thorough text.",
        )
        md = render_summary_markdown(summ)
        assert md.startswith("# Summary: Ch.1\n\n## Executive Summary\n\n")
        assert "## Key Takeaways\n\n- Bullet one." in md
        assert "## Thorough Summary\n\nThorough text.\n" in md

    def test_resume_parser_accepts_no_thorough_file(self, tmp_path):
        from core.pipeline.chapter_resume import parse_summary_file

        f = tmp_path / "ch.summary.md"
        f.write_text(
            "# Summary: Ch.1\n\n"
            "## Executive Summary\n\nExec text.\n\n"
            "## Key Takeaways\n\n- Bullet one.\n\n"
            "<!-- COMPLETE -->\n",
            encoding="utf-8",
        )
        r = parse_summary_file(f)
        assert r is not None and r.success
        assert r.executive_summary == "Exec text."
        assert r.thorough_summary == ""
        assert r.bullet_points == ["Bullet one."]

    def test_resume_parser_accepts_no_bullets_file(self, tmp_path):
        from core.pipeline.chapter_resume import parse_summary_file

        f = tmp_path / "ch.summary.md"
        f.write_text(
            "# Summary: Ch.1\n\n"
            "## Executive Summary\n\nExec text.\n\n"
            "## Thorough Summary\n\nThorough text.\n\n"
            "<!-- COMPLETE -->\n",
            encoding="utf-8",
        )
        r = parse_summary_file(f)
        assert r is not None, "a keypoints-disabled run must not re-summarize forever"
        assert r.bullet_points == []

    def test_resume_parser_rejects_contentless_file(self, tmp_path):
        from core.pipeline.chapter_resume import parse_summary_file

        f = tmp_path / "ch.summary.md"
        f.write_text(
            "# Summary: Ch.1\n\n<!-- COMPLETE -->\n", encoding="utf-8")
        assert parse_summary_file(f) is None

    def test_docx_builder_gates_empty_sections(self):
        """Source pin: the DOCX builder renders sections only when non-empty
        AND the output-selection flag is on (V0.06 F1-c added the flag half
        of the gate — content-presence alone shipped unrequested sections)."""
        src = _strip_comments(_src("core/docx/builder.py"))
        assert 'if _exec_text.strip() and _inc_exec_d:' in src
        assert 'if _thorough_text.strip() and _inc_th_d:' in src
        assert 'if summ.bullet_points and _inc_kp_d:' in src

    def test_wizard_labels_do_not_promise_absolute_words(self):
        """The Step-4 labels must not promise "800-1200 words" the engine no
        longer demands (honest UI)."""
        src = _strip_comments(
            _src("ui_qt/views/wizard_steps/step4_outputs.py"))
        assert "800-1200" not in src
        assert "scaled to chapter" in src


# ═══════════════════════════════════════════════════════════════════════════
# F2 (P0) — structural self-assessment detection (critique-bullet leakage)
# ═══════════════════════════════════════════════════════════════════════════

# The 11 leaked rig bullets (V0.04 audit, files 002/003/004) — verbatim
# shapes from the run.
_RIG_LEAKED_BULLETS = [
    'Author attribution: The chapter author is identified as "By Neal Ford" '
    'but this name does not appear in the summary text.',
    "The summary must identify specific emotional states—anger, frustration, "
    "annoyance—so the reader understands what to watch for.",
    "Missing explicit mechanism: the summary should explain HOW assuming the "
    "best leads to learning more.",
    "Missing specific behavioral outcome: what happens when you approach "
    "conversations with the right attitude.",
    "Missing the specific time-frame constraint attached to mutually "
    "agreed-upon goals.",
    "Missing the framing of conversation as humanity's most important "
    "innovation.",
    "Missing the distinction between familiarity and skill as separate "
    "sources of resistance.",
    "The gap fails to capture the defensive reaction triggered when someone "
    "feels attacked or criticized.",
    'It omits the distinct definition that "Clarity describes how you '
    'communicate."',
    'The summary flattens the vivid metaphor of being "pushed out" by poor '
    "communication.",
    'It lacks the explicit rhetorical distinction between working "with" and '
    '"against" developers.',
]

# Content bullets that must NEVER be flagged.
_RIG_CONTENT_BULLETS = [
    'The chapter author is identified as "By Neal Ford" — Neal Ford argues '
    "that essential complexity is inherent in the problem.",
    'Mark Richards defines clarity as "Clarity describes how you communicate."',
    "The source notes that conversation is humanity's most important "
    "innovation.",
    "It is essential to balance technical requirements with stakeholder "
    "interests.",
    "Missing requirements cause project failure when architects choose "
    "technologies to impress a resume.",
    "The author states that assuming the best helps you learn more because "
    "people become less defensive.",
    "The gap between business and engineering priorities must be managed by "
    "the architect.",
]


class TestF2StructuralSelfAssessment:
    def test_all_eleven_rig_bullets_flagged(self):
        from core.summarisation.post_processing import is_summary_self_assessment

        for b in _RIG_LEAKED_BULLETS:
            assert is_summary_self_assessment(b), f"leaked shape not caught: {b[:70]}"

    def test_content_bullets_never_flagged(self):
        from core.summarisation.post_processing import is_summary_self_assessment

        for b in _RIG_CONTENT_BULLETS:
            assert not is_summary_self_assessment(b), f"false positive: {b[:70]}"

    def test_legacy_shapes_still_caught(self):
        from core.summarisation.post_processing import is_summary_self_assessment

        assert is_summary_self_assessment(
            "The summary misses the emotional dimension of technical problems.")
        assert is_summary_self_assessment("The summary omits the second principle.")
        assert is_summary_self_assessment(
            'A topic the summary omits entirely: "This specific area."')

    def test_classify_scar_routes_the_new_class(self):
        from core.summarisation.post_processing import classify_scar

        for b in _RIG_LEAKED_BULLETS:
            assert classify_scar(b) == "summary_self_assessment", b[:60]

    def test_classify_bullets_drops_them_always(self):
        """Generation-time layer: the scholar gap-fill merge filter routes
        through classify_bullets — critique never enters bullet_points."""
        from core.summarisation.post_processing import classify_bullets

        bullets = list(_RIG_LEAKED_BULLETS) + list(_RIG_CONTENT_BULLETS)
        kept, drops = classify_bullets(bullets, concepts=None, source_text="")
        kept_set = set(kept)
        for b in _RIG_LEAKED_BULLETS:
            assert b not in kept_set, f"critique bullet survived: {b[:60]}"
        for b in _RIG_CONTENT_BULLETS:
            assert b in kept_set, f"content bullet dropped: {b[:60]}"
        assert any(s == "thinking_filter.summary_self_assessment"
                   for _b, s, _r, _a in drops)

    def test_scholar_prompt_forbids_critique_forms(self):
        t = _src("prompts/summarisation/scholar_reflection.md")
        assert "FORBIDDEN subject forms" in t
        assert "does not appear in the summary text" in t


# ═══════════════════════════════════════════════════════════════════════════
# F3 (P1) — one coverage matcher; sentence-keyed excerpts
# ═══════════════════════════════════════════════════════════════════════════


class TestF3CoverageMatcher:
    def test_kw_missing_uses_normalized_matching(self):
        from core.summarisation.coverage_guarantee import _kw_missing
        from core.summarisation.summary_validator import _normalize_for_coverage

        norm = _normalize_for_coverage(
            "The summary describes a smart and effective architect who "
            "considers ease of learning."
        )
        # the rig's exact false-"missing" cases:
        assert not _kw_missing("smart effective architect", norm), (
            "paraphrase-covered keyword must NOT be missing (was raw-substring)"
        )
        assert not _kw_missing("ease-of-learning", norm), (
            "hyphen variant must NOT be missing"
        )
        assert _kw_missing("skyscrapers aren't scalable", norm)

    def test_tier2_does_not_refire_on_paraphrase(self):
        """A keyword covered by a paraphrase must not trigger gap-fill."""
        from core.summarisation.coverage_guarantee import apply_3tier_coverage

        calls = {"gap_fill": 0, "force_insert": 0}
        result = {
            "executive_summary": "",
            "bullet_points": [
                "The summary describes a smart and effective architect who "
                "considers ease of learning."
            ],
            "thorough_summary": "",
        }
        apply_3tier_coverage(
            "Ch", "text", "content",
            result, coverage=0.5, coverage_threshold=0.85,
            extract_keywords=lambda content, n=18: [
                "smart effective architect", "ease-of-learning"],
            log=lambda m, l="DEBUG": None,
            targeted_gap_fill=lambda h, t, missing: (
                calls.__setitem__("gap_fill", calls["gap_fill"] + 1) or []),
            filter_thinking_bullets=lambda bps: bps,
            force_insert_missing=lambda t, missing, res: (
                calls.__setitem__("force_insert", calls["force_insert"] + 1)),
            compute_coverage=lambda c, s: 0.99,
        )
        assert calls["gap_fill"] == 0, "paraphrase-covered keywords must not gap-fill"
        assert calls["force_insert"] == 0

    def _summarizer(self):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.request = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        logs = []
        s.log = lambda msg, level="INFO": logs.append(msg)
        return s, logs

    def test_same_sentence_three_keywords_one_excerpt(self):
        """The rig's exact duplication: 3 overlapping keywords → the same
        sentence inserted 3× under different labels. Now: ONE excerpt, all
        keywords named in the frame."""
        s, _logs = self._summarizer()
        # one sentence carrying ALL THREE keyword groups (as the rig's
        # overlapping trigram extraction produced)
        source = (
            "Watch for these moments when otherwise flustered developers "
            "seem angry, frustrated, or annoyed, because anger creates "
            "attack opportunities and mutually agreed damage. A different "
            "sentence about architecture follows here with other content."
        )
        result = {"bullet_points": []}
        n = s._force_insert_missing(
            source,
            ["angry frustrated annoyed", "annoyed otherwise flustered",
             "attack opportunities mutually"],
            result,
        )
        assert n == 1, "three keywords on ONE sentence must yield ONE excerpt"
        ex = result["source_excerpts"][0]
        assert ex.count("verbatim from the source") == 1
        # the keywords are consolidated in the frame
        assert " / " in ex

    def test_different_sentences_still_each_insert(self):
        s, _logs = self._summarizer()
        source = (
            "The system must respond to user input in no more than 1500 "
            "milliseconds under normal operating load conditions. Response "
            "times below 500 milliseconds cannot be distinguished by users."
        )
        result = {"bullet_points": []}
        n = s._force_insert_missing(
            source, ["respond to user input", "response times"], result)
        assert n == 2
        assert len(set(result["source_excerpts"])) == 2


# ═══════════════════════════════════════════════════════════════════════════
# F4 (P1) — sentence boundary accepts digits/quotes
# ═══════════════════════════════════════════════════════════════════════════


class TestF4SentenceBoundary:
    def _summarizer(self):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.request = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        s.log = lambda msg, level="INFO": None
        return s

    def test_numbered_list_continuation_not_glued(self):
        """The rig's exact glued excerpt: '…on the attack.\n\n 3) Use
        these…' must split before the digit."""
        s = self._summarizer()
        source = (
            "Watch for these moments when developers seem to be on the "
            "attack.\n\n 3) Use these as opportunities to set mutually "
            "agreed upon goals that both parties work toward."
        )
        sent = s._find_source_sentence("mutually agreed", source)
        assert sent is not None
        assert not sent.startswith("Watch"), "the numbered item must not glue to the previous sentence"
        assert "3)" in sent
        assert "on the attack" not in sent

    def test_capital_boundary_still_works(self):
        s = self._summarizer()
        source = (
            "The first sentence stands alone. The second sentence follows "
            "with capitals and works exactly as before this change."
        )
        sent = s._find_source_sentence("second sentence follows", source)
        assert sent is not None and sent.startswith("The second")


# ═══════════════════════════════════════════════════════════════════════════
# F5 (P1) — attribution fires at >=1 byline
# ═══════════════════════════════════════════════════════════════════════════


class TestF5SingleBylineAttribution:
    def _make_summarizer(self, monkeypatch):
        class _FakeSettings:
            def get(self, key, default=None):
                if key == "summarisation.provider":
                    return "ollama"
                return default

        monkeypatch.setattr(
            "core.summarisation.summarizer.Settings", lambda: _FakeSettings())
        monkeypatch.setattr("utils.settings.Settings", lambda: _FakeSettings())
        from core.summarisation.summarizer import Summarizer

        req = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        req.summarisation_model = "gemma3:12b"
        return Summarizer(
            request=req, log_callback=lambda m, l="INFO": None,
            language="en", claim_extractor=None,
        )

    def test_single_byline_gets_attribution_block(self, monkeypatch):
        """The rig's chapter-2 case: exactly ONE byline (Neal Ford) — the
        prompt must require naming the author."""
        s = self._make_summarizer(monkeypatch)
        text = (
            "Simplify essential complexity; diminish accidental complexity.\n\n"
            "By Neal Ford\n\n"
            "Essential complexity is inherent in the problem while "
            "accidental complexity comes from the solution we build."
        )
        prompt = s._build_prompt("2. Simplify essential complexity", text)
        assert "ATTRIBUTION — This chapter is by Neal Ford" in prompt
        assert "never names its author" in prompt

    def test_multi_byline_keeps_anthology_block(self, monkeypatch):
        s = self._make_summarizer(monkeypatch)
        text = (
            "Essay one.\n\nBy Udi Dahan\n\nEssay two.\n\nBy Keith Braithwaite\n\n"
            "Requirements should be measurable with concrete thresholds."
        )
        prompt = s._build_prompt("Anthology Section", text)
        assert "ANTHOLOGY ATTRIBUTION" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# F6 (P2) — ship-time near-duplicate removal
# ═══════════════════════════════════════════════════════════════════════════


class TestF6NearDuplicateRemoval:
    def test_rig_near_dups_removed(self):
        """The rig's 003 pairs: near-identical bullets with different
        phrasings — keep the first, drop the rest."""
        from core.summarisation.postchecks import run_post_checks

        bullets = [
            "During moments of emotional tension, steer the conversation "
            "toward mutually agreed upon goals.",
            "Ask the developer to help increase participation in the "
            "conversation.",
            "In moments of emotional tension, steer the conversation toward "
            "mutually agreed-upon goals.",   # near-dup of [0]
            "Ask developers to help increase participation in the "
            "conversations.",                 # near-dup of [1]
            "Assume the best about the other person to learn more.",
        ]
        rep = run_post_checks(bullets, "", "", source_text=" ".join(bullets))
        kept = rep.bullets
        assert len(kept) == 3, f"expected 3 kept, got {len(kept)}: {kept}"
        assert kept[0].startswith("During moments")
        assert any(i.detector == "near_duplicate" for i in rep.issues)

    def test_distinct_bullets_all_kept(self):
        from core.summarisation.postchecks import run_post_checks

        bullets = [
            "Essential complexity is inherent in the problem domain itself.",
            "Accidental complexity comes from the solution we choose to build.",
            "Communication between architects and developers requires both "
            "clarity and leadership working together.",
        ]
        rep = run_post_checks(bullets, "", "", source_text=" ".join(bullets))
        assert len(rep.bullets) == 3


# ═══════════════════════════════════════════════════════════════════════════
# F7 (P2) — run-scoped output (stale artifacts archived at run start)
# ═══════════════════════════════════════════════════════════════════════════


class TestF7RunScopedOutput:
    def _converter(self, tmp_path, resume=False):
        from core.pipeline.converter_impl import Converter

        stub = types.SimpleNamespace()
        stub._log = lambda msg, level="DEBUG": stub.logs.append(msg) if hasattr(stub, "logs") else None
        stub.logs = []
        stub.settings = types.SimpleNamespace(
            get=lambda k, d=None: resume if k == "summarisation.resume_enabled" else d)
        stub.output_dir = tmp_path
        stub.paths = types.SimpleNamespace(
            summaries_dir=tmp_path / "book_summaries")
        return Converter._archive_stale_run_artifacts.__get__(
            stub, type(stub))

    def test_stale_summaries_archived(self, tmp_path):
        summ = tmp_path / "book_summaries"
        (summ / "chapters").mkdir(parents=True)
        (summ / "001_old.summary.md").write_text("old run", encoding="utf-8")
        (summ / "chapters" / "002_old.summary.md").write_text("old", encoding="utf-8")
        (tmp_path / "book.conversion.log.md").write_text("log", encoding="utf-8")
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "drops.jsonl").write_text("{}", encoding="utf-8")
        # non-artifact files must stay
        (tmp_path / "markdown").mkdir()
        (tmp_path / "markdown" / "book.md").write_text("source", encoding="utf-8")

        archive = self._converter(tmp_path)
        archive()

        assert not (summ / "001_old.summary.md").exists()
        assert not (summ / "chapters" / "002_old.summary.md").exists()
        assert not (tmp_path / "book.conversion.log.md").exists()
        assert not (tmp_path / "logs" / "drops.jsonl").exists()
        arch_dirs = list((tmp_path / "_archive").iterdir())
        assert len(arch_dirs) == 1
        moved = list(arch_dirs[0].rglob("*"))
        assert any(p.name == "001_old.summary.md" for p in moved)
        assert any(p.name == "drops.jsonl" for p in moved)
        # the extracted source markdown is untouched
        assert (tmp_path / "markdown" / "book.md").exists()

    def test_resume_skips_archiving(self, tmp_path):
        summ = tmp_path / "book_summaries"
        summ.mkdir(parents=True)
        (summ / "001_old.summary.md").write_text("resume me", encoding="utf-8")
        archive = self._converter(tmp_path, resume=True)
        archive()
        assert (summ / "001_old.summary.md").exists(), (
            "resume reuses existing summaries — never archive them"
        )

    def test_clean_folder_noop(self, tmp_path):
        archive = self._converter(tmp_path)
        archive()  # must not create _archive/ on a clean folder
        assert not (tmp_path / "_archive").exists()

    def test_convert_wires_the_archiver(self):
        src = _strip_comments(_src("core/pipeline/converter_impl.py"))
        assert "self._archive_stale_run_artifacts()" in src


# ═══════════════════════════════════════════════════════════════════════════
# F8 (P3) — verbatim quote verification
# ═══════════════════════════════════════════════════════════════════════════


class TestF8QuoteVerification:
    def test_rig_misquote_ships_as_paraphrase(self):
        """The rig's 001 bullet 31: quoted 'it should never happen…' where
        the source reads 'this should never happen…' — the quotes must be
        stripped (paraphrase), the words kept."""
        from core.summarisation.postchecks import run_post_checks

        source = (
            "Choosing a technology to pad the resume costs the customer. "
            "The customer is who we serve, so this should never happen at "
            "the cost of the customer, and the requirements come first."
        )
        bullet = (
            'The architect warns that "it should never happen at the cost of '
            'the customer" when technologies are chosen to impress.'
        )
        rep = run_post_checks([bullet], "", "", source_text=source)
        assert len(rep.bullets) == 1
        out = rep.bullets[0]
        assert '"it should never happen' not in out, "the misquote marks must be stripped"
        assert "it should never happen at the cost of the customer" in out, (
            "the words are kept as a paraphrase"
        )
        assert any(i.detector == "quote_verification" for i in rep.issues)

    def test_verbatim_quote_kept(self):
        from core.summarisation.postchecks import run_post_checks

        source = (
            "The author writes that this should never happen at the cost of "
            "the customer, and requirements come before resumes."
        )
        bullet = (
            'The author writes that "this should never happen at the cost of '
            'the customer", so requirements come first.'
        )
        rep = run_post_checks([bullet], "", "", source_text=source)
        assert '"this should never happen' in rep.bullets[0], (
            "a VERBATIM quote keeps its quotation marks"
        )
        assert not any(i.detector == "quote_verification" for i in rep.issues)

    def test_short_quotes_untouched(self):
        from core.summarisation.postchecks import run_post_checks

        source = "The author values clarity above all other communication traits."
        bullet = 'The chapter treats "clarity" as the core communication trait.'
        rep = run_post_checks([bullet], "", "", source_text=source)
        assert '"clarity"' in rep.bullets[0]


# ═══════════════════════════════════════════════════════════════════════════
# Regression guards — verified-good behaviors the audit confirmed
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifiedGoodBehaviorsKept:
    def test_excerpts_still_framed_and_excluded(self):
        """V0.03's framing contract is unchanged by the dedupe redesign."""
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.request = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        s.log = lambda msg, level="INFO": None
        source = (
            "The system must respond to user input in no more than 1500 "
            "milliseconds under normal operating load conditions."
        )
        result = {"bullet_points": ["Existing."]}
        s._force_insert_missing(source, ["respond to user input"], result)
        ex = result["source_excerpts"][0]
        assert ex.startswith('On "')
        assert "not the summarizer's advice" in ex
        assert result["bullet_points"] == ["Existing."]

    def test_structured_io_hints_scaled(self):
        from core.llm.structured_io import build_json_instruction
        from core.summarisation.length_policy import bullet_range_phrase

        instr = build_json_instruction(
            _schema(), source_words=340)
        assert "150-250" not in instr
        assert "800-1200" not in instr
        assert "20-40" not in instr
        assert bullet_range_phrase(340) in instr

    def test_structured_io_default_has_no_absolutes(self):
        from core.llm.structured_io import build_json_instruction

        instr = build_json_instruction(_schema())
        assert "150-250" not in instr
        assert "800-1200" not in instr


def _schema():
    from core.llm.structured_io import SummarySchema

    return SummarySchema
