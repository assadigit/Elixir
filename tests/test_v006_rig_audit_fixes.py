"""V0.06 — real-rig audit fixes (97-Things run 20260918-142541, llama.cpp +
Ternary-Bonsai-2-27B, Elixir v0.05, user samples 001-005 + book summary +
conversion log).

The user's three observations on the shipped output, plus the audit's
findings — each pinned here as a GENERAL rule (the book is only the test
that exposed it):

  F1 (P0)  "It again created thorough summary." Outputs were
           `exec_summary, keypoints, docx` (log line 151) yet every chapter
           file shipped "## Thorough Summary" — its content a run-on concat
           of Key Distinctions + Theoretical Tensions + a literal "None".
           ROOT CAUSE: the response parser's leftover fallback assigned the
           additive-section blocks (never removed from `remaining`) to
           `thorough_summary`, and NO stage — parse, render (.md/DOCX/book)
           — checked the include flag on the content.
  F2 (P0)  "Quarantine log is not needed in docx output (keep it for your
           logs)." → pipeline bookkeeping never ships in deliverables.
  F3 (P0)  "Full chapter content is redundant, it repeated twice." →
           book .md listed every chapter's bullets TWICE (global "All Key
           Takeaways" concat + per-chapter lists); the DOCX rendered each
           chapter's text TWICE (2000-char preview + full content) and the
           takeaways twice again (per-chapter callouts + closing "Global
           Key Takeaways" page).
  F4 (P0)  Bullet-count explosion: 19/18/15/14/12 bullets against
           source-scaled targets 5-7/5-7/6-9/6-9/5-8 — the V0.05 length
           policy gated only the expansion CALL; Tier-2 gap-fill, scholar
           gap-fill (+13/+22/+8/+10) and quarantine recovery appended
           freely. → the budget is a HARD CAP at every insertion site AND
           at ship time.
  F5 (P0)  Critique bullets shipped in Key Takeaways ("Weather impact on
           schedules omitted: "…"", "The summary should clarify…",
           "…not fully enumerated in the summary: "…"" — flagged by the
           consistency checker but never dropped).
  F6 (P1)  Duplicated quotes inside single bullets (inline quote + the same
           quote appended) and byline echoes (""By Neal Ford"").
  F7 (P1)  Source Excerpts duplicating Key-Takeaway bullets (no final-state
           re-check) and excerpts opening with the chapter-heading echo
           ("Don't put your resume ahead of the
           requirements As engineers…").
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

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

if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

from core.models import ConversionRequest, SummaryResult  # noqa: E402


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
# F1 (P0) — the thorough leak: parser leftover + flag-blind render
# ═══════════════════════════════════════════════════════════════════════════

# The EXACT shape of the rig's primary response (97-Things ch.1): exec +
# bullets + additive sections, NO <thorough_summary> — the prompt stripped
# it because the user unchecked the output.
_RIG_PRIMARY_RESPONSE = """<executive_summary>
Borwankar argues engineers must prioritize customer needs over personal career goals.
</executive_summary>

<bullet_points>
- Borwankar identifies a common engineer error: recommending technologies for resume enhancement.
- He argues career success comes from customer goodwill and recommendations.
</bullet_points>

<key_distinctions>
- Customer well-being versus resume value: Borwankar contrasts using technology for client benefit against using it to enhance a professional record.
- Long-term customer needs versus short-term personal needs: The chapter distinguishes between these two motivations.
</key_distinctions>

<theoretical_tensions>
- The tension between staying abreast of trends and serving the customer's needs.
</theoretical_tensions>
"""


class TestF1ParserLeftover:
    def test_additive_sections_never_become_thorough(self):
        """THE V0.05 rig bug: with thorough stripped from the prompt, the
        model emitted kd/tt; the parser's leftover fallback removed only
        the exec/bullet blocks, so kd/tt (419 chars on ch.1) became the
        "thorough_summary" — shipped as a run-on Thorough Summary."""
        from core.summarisation.response_parser import parse_response

        r = parse_response(_RIG_PRIMARY_RESPONSE)
        assert r["executive_summary"].strip().startswith("Borwankar argues")
        assert len(r["bullet_points"]) == 2
        assert "Customer well-being versus resume value" in r["key_distinctions"]
        assert "staying abreast" in r["theoretical_tensions"]
        # THE CONTRACT: the additive content must NOT leak into thorough
        assert (r["thorough_summary"] or "").strip() == ""

    def test_real_thorough_tag_still_parses(self):
        from core.summarisation.response_parser import parse_response

        raw = (
            "<executive_summary>Exec text.</executive_summary>\n"
            "<bullet_points>\n- One bullet.\n</bullet_points>\n"
            "<thorough_summary>\nA real thorough summary paragraph.\n</thorough_summary>\n"
            "<key_distinctions>\n- A versus B.\n</key_distinctions>\n"
        )
        r = parse_response(raw)
        assert "real thorough summary" in r["thorough_summary"]
        assert "A versus B" not in r["thorough_summary"]

    def test_none_placeholder_thorough_is_empty(self):
        from core.summarisation.response_parser import parse_response

        raw = (
            "<executive_summary>Exec.</executive_summary>\n"
            "<bullet_points>\n- B.\n</bullet_points>\n"
            "<thorough_summary>\nNone\n</thorough_summary>\n"
        )
        assert (parse_response(raw)["thorough_summary"] or "").strip() == ""

    def test_trailing_standalone_none_stripped(self):
        """The rig's literal shape: '…immediate career interests. None' —
        the next section's placeholder glued after a completed sentence."""
        from core.summarisation.response_parser import parse_response

        raw = (
            "<executive_summary>Exec.</executive_summary>\n"
            "<bullet_points>\n- B.\n</bullet_points>\n"
            "<thorough_summary>\nIt instructs readers to prioritize long-term "
            "customer requirements over immediate career interests. None\n"
            "</thorough_summary>\n"
        )
        th = parse_response(raw)["thorough_summary"]
        assert "immediate career interests." in th
        assert not th.rstrip().endswith("None")


class TestF1RenderContract:
    """Content present + flag OFF = section absent. Content-presence alone
    (the V0.05 gate) shipped unrequested sections."""

    def _mk(self, **kw) -> SummaryResult:
        base = dict(
            chapter_heading="1. Don't put your resume ahead of the requirements",
            executive_summary="Exec text.",
            thorough_summary="Thorough text that leaked in.",
            bullet_points=["Bullet one.", "Bullet two."],
        )
        base.update(kw)
        return SummaryResult(**base)

    def test_thorough_flag_off_content_present_not_rendered(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        md = render_summary_markdown(self._mk(include_thorough_summary=False))
        assert "## Thorough Summary" not in md
        assert "Thorough text that leaked in." not in md
        assert "## Executive Summary" in md  # requested sections intact
        assert "## Key Takeaways" in md

    def test_exec_flag_off_content_present_not_rendered(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        md = render_summary_markdown(self._mk(include_executive_summary=False))
        assert "## Executive Summary" not in md
        assert "## Thorough Summary" in md

    def test_keypoints_flag_off_content_present_not_rendered(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        md = render_summary_markdown(self._mk(include_keypoints=False))
        assert "## Key Takeaways" not in md
        assert "Bullet one." not in md

    def test_legacy_unstamped_result_renders_everything(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        md = render_summary_markdown(self._mk())  # flags default True
        assert "## Executive Summary" in md
        assert "## Key Takeaways" in md
        assert "## Thorough Summary" in md

    def test_source_pins_contract_gates(self):
        """The gates exist at THREE layers: parse time, result construction,
        render time (defense in depth — a single-layer fix failed before)."""
        # V0.18 (Phase 5.1, steps 2-4): the parse-time gate moved to the
        # single-pass phase; the construction gate to the finalize phase
        # (both VERBATIM, chapter_phases.py).
        s_sum = _strip_comments(_src("core/summarisation/chapter_phases.py"))
        # parse-time gate
        assert 'if not bool(getattr(self.request, "include_thorough_summary", True)):' in s_sum
        assert 'result["thorough_summary"] = ""' in s_sum
        # construction gate
        assert 'thorough_summary=(thorough if _inc_thorough_lp else ""),' in s_sum
        # render gate (markdown)
        s_ck = _strip_comments(_src("core/pipeline/chapter_checkpoint.py"))
        assert 'if _inc_th_r and (thorough_formatted or "").strip():' in s_ck
        # render gate (docx)
        s_d = _strip_comments(_src("core/docx/builder.py"))
        assert "if _thorough_text.strip() and _inc_th_d:" in s_d


class TestF1BookSummaryContract:
    def _summarizer(self):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.provider = "llamacpp"
        s.language = "en"
        logs = []
        s.log = lambda msg, level="INFO": logs.append(msg)
        return s, logs

    def test_details_block_honours_thorough_flag(self):
        s, _ = self._summarizer()
        summaries = [
            SummaryResult(
                chapter_heading="Ch A",
                executive_summary="Exec A.",
                thorough_summary="Thorough A content.",
                bullet_points=["A bullet."],
                include_thorough_summary=False,
            ),
            SummaryResult(
                chapter_heading="Ch B",
                executive_summary="Exec B.",
                thorough_summary="Thorough B content.",
                bullet_points=["B bullet."],
            ),
        ]
        out = s.build_book_summary(summaries, "Book")
        assert "Thorough B content." in out
        assert "<details>" in out
        assert "Thorough A content." not in out  # flag off = absent

    def test_stats_still_count_deduped_bullets(self):
        s, _ = self._summarizer()
        summaries = [
            SummaryResult(
                chapter_heading="Ch A",
                executive_summary="E",
                thorough_summary="",
                bullet_points=[
                    "Shared bullet about architecture balance.",
                    "Only chapter A mentions this takeaway.",
                ],
            ),
            SummaryResult(
                chapter_heading="Ch B",
                executive_summary="E",
                thorough_summary="",
                bullet_points=["Shared bullet about architecture balance."],
            ),
        ]
        stats: dict = {}
        s.build_book_summary(summaries, "Book", stats=stats)
        assert stats["bullets"] == 2
        assert stats["chapters"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# F2 (P0) — quarantine record never ships in the deliverable
# ═══════════════════════════════════════════════════════════════════════════


class TestF2QuarantineNotShipped:
    def test_render_never_emits_quarantine_section(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        summ = SummaryResult(
            chapter_heading="Ch",
            executive_summary="E",
            thorough_summary="T",
            bullet_points=["B."],
            # a LEGACY result that somehow still carries an appendix
            quarantine_appendix=(
                "## Quarantine Log (quality-pipeline drops)\n\n"
                "- [thinking_filter.truncated · dropped] Bullet appears truncated"
            ),
        )
        md = render_summary_markdown(summ)
        assert "Quarantine Log" not in md
        assert "thinking_filter.truncated" not in md

    def test_summarizer_no_longer_attaches_appendix(self):
        """Source pin: the appendix builder is gone; the drop count is
        logged (logs/drops.jsonl remains the audit trail)."""
        s = _strip_comments(_src("core/summarisation/summarizer.py"))
        assert "quarantine_appendix=_quarantine_appendix_md," not in s
        # V0.18 (Phase 5.1, step 1): the quarantine-record comment moved
        # VERBATIM to the finalize phase (chapter_phases.py).
        assert (
            "NOT rendered in the delivered files"
            in _src("core/summarisation/chapter_phases.py")
        )

    def test_docx_builder_has_no_quarantine_block(self):
        s = _strip_comments(_src("core/docx/builder.py"))
        assert '"Quarantine Log (quality-pipeline drops)"' not in s


# ═══════════════════════════════════════════════════════════════════════════
# F3 (P0) — a deliverable never lists the same content block twice
# ═══════════════════════════════════════════════════════════════════════════


class TestF3NoDoubleListing:
    def _summarizer(self):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.provider = "llamacpp"
        s.language = "en"
        s.log = lambda msg, level="INFO": None
        return s

    def test_book_summary_lists_each_bullet_once(self):
        """THE V0.05 rig bug: '## 📌 All Key Takeaways' concatenated every
        chapter's bullets, then 'Chapter-by-Chapter' repeated each chapter's
        FULL list — every takeaway twice in one file."""
        s = self._summarizer()
        ch1_bullets = [f"Ch1 takeaway number {i} about resume choices." for i in range(5)]
        ch2_bullets = [f"Ch2 takeaway number {i} about complexity." for i in range(5)]
        summaries = [
            SummaryResult(
                chapter_heading="Ch 1",
                executive_summary="E1",
                thorough_summary="",
                bullet_points=ch1_bullets,
            ),
            SummaryResult(
                chapter_heading="Ch 2",
                executive_summary="E2",
                thorough_summary="",
                bullet_points=ch2_bullets,
            ),
        ]
        out = s.build_book_summary(summaries, "Book")
        assert "📌 All Key Takeaways" not in out
        for bp in ch1_bullets + ch2_bullets:
            assert out.count(bp) == 1, f"bullet listed more than once: {bp[:50]}"
        # the per-chapter structure remains (the single listing)
        assert "## 📖 Chapter-by-Chapter Executive Summaries" in out
        assert "**Key takeaways:**" in out

    def test_docx_preview_duplicate_removed(self):
        """Source pin: the 'Original Chapter Content (first 2000 chars)'
        preview (which duplicated short chapters ENTIRELY) is gone."""
        s = _strip_comments(_src("core/docx/builder.py"))
        assert "Original Chapter Content" not in s

    def test_docx_global_takeaways_page_removed(self):
        """Source pin: the closing 'Global Key Takeaways' page (every
        takeaway a second time) is no longer added to the report."""
        s = _strip_comments(_src("core/docx/builder.py"))
        assert "self._add_global_takeaways(doc, summaries)" not in s


# ═══════════════════════════════════════════════════════════════════════════
# F4 (P0) — the source-scaled bullet budget is a HARD CAP everywhere
# ═══════════════════════════════════════════════════════════════════════════


class TestF4BulletCap:
    def test_bullet_cap_matches_rig_chapter_targets(self):
        """The rig's five chapters (344/358/439/445/412 words).

        V0.07 (output-regression fix): the takeaway density moved 50 -> 25
        words/bullet (restoring V18's 30-40 bullets for normal chapters),
        so the rig chapters' caps are now 14/14/18/18/16 — still far below
        the 29-36 the rig actually shipped (one bullet per ~12 words).
        """
        from core.summarisation.length_policy import bullet_cap

        assert bullet_cap(344) == 14
        assert bullet_cap(358) == 14
        assert bullet_cap(439) == 18
        assert bullet_cap(445) == 18
        assert bullet_cap(412) == 16

    def test_ship_time_budget_enforced_source_pin(self):
        # V0.18 (Phase 5.1, step 1): the ship-time cap moved VERBATIM to the
        # postchecks phase (chapter_phases.py).
        s = _strip_comments(_src("core/summarisation/chapter_phases.py"))
        assert "if _inc_kp_lp and len(bullets) > _bp_hi_lp:" in s
        assert "bullets = list(bullets[:_bp_hi_lp])" in s


class TestF4Tier2Cap:
    def _run(self, existing_bullets, cap, missing_kws):
        from core.summarisation.coverage_guarantee import apply_3tier_coverage

        result = {"bullet_points": list(existing_bullets), "executive_summary": "E"}
        calls = {"gap_fill": 0, "force_insert": 0}
        logs = []

        def targeted_gap_fill(heading, text, missing):
            calls["gap_fill"] += 1
            calls["last_missing"] = list(missing)
            return []

        def force_insert_missing(text, still_missing, result):
            calls["force_insert"] += 1

        _cov = apply_3tier_coverage(
            "H",
            "src",
            "content",
            result,
            0.5,
            coverage_threshold=0.85,
            extract_keywords=lambda c, n=18: missing_kws,
            log=lambda m, l="INFO": logs.append(m),
            targeted_gap_fill=targeted_gap_fill,
            filter_thinking_bullets=lambda b: b,
            max_bullets_per_chapter=99999,
            compute_coverage=lambda c, t: 0.5,
            force_insert_missing=force_insert_missing,
            bullet_cap=cap,
        )
        return result, calls, logs

    def test_at_cap_tier2_skipped(self):
        """The rig's ch.1 shape: 7 bullets already (cap 7) — Tier-2 must not
        fire (was: +4 gap-fill bullets on top of a full budget)."""
        result, calls, logs = self._run([f"b{i}" for i in range(7)], 7, ["kw1", "kw2", "kw3"])
        assert calls["gap_fill"] == 0
        assert len(result["bullet_points"]) == 7
        assert any("Tier-2 gap-fill SKIPPED" in m for m in logs)

    def test_partial_room_trims_missing_list(self):
        """6 bullets, cap 7, 4 missing concepts → only 1 concept gap-filled
        (no LLM calls whose output cannot ship)."""
        result, calls, logs = self._run(
            [f"b{i}" for i in range(6)], 7, ["kw1", "kw2", "kw3", "kw4"]
        )
        assert calls["gap_fill"] == 1
        assert calls["last_missing"] == ["kw1"]
        assert any("trimmed" in m for m in logs)

    def test_no_cap_legacy_behaviour(self):
        result, calls, logs = self._run([f"b{i}" for i in range(7)], None, ["kw1", "kw2"])
        assert calls["gap_fill"] == 1  # uncapped = legacy path


class TestF4ScholarCap:
    def _deps(self, gap_bullets_md: str):
        llm_resp = (
            "<scholar_reflections>\n- One gap identified\n"
            "</scholar_reflections>\n\n<gap_fill_bullets>\n"
            f"{gap_bullets_md}\n</gap_fill_bullets>"
        )
        llm_calls, rvram_calls = [], []

        class _PM:
            def render_template(self, name, **kw):
                return "PROMPT"

        def call_fast_llm(prompt, **kw):
            llm_calls.append(prompt)
            return llm_resp

        return dict(
            prompt_manager=_PM(),
            recover_vram=lambda context="", delay_sec=0.0, **kw: rvram_calls.append(context),
            call_fast_llm=call_fast_llm,
            strip_thinking=lambda t: t,
        )

    def _run(
        self, existing, cap, source="The weather delays flights and storms divert planes every day."
    ):
        from core.summarisation.scholar_reflection import scholar_reflection

        result = {
            "executive_summary": "E",
            "bullet_points": list(existing),
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        # three DISTINCT grounded gap bullets (the merge dedup keys on the
        # first 60 normalized chars — the distinct claim must LEAD, and
        # identical strings would be deduped before the cap, conflating the
        # two mechanisms under test)
        gaps = "\n".join(
            f'- Distinct claim {i}: the source states that "{source}" '
            f"and this matters for the argument."
            for i in range(3)
        )
        logs = []
        scholar_reflection(
            "H",
            source,
            result,
            max_context_tokens=32768,
            language="en",
            temperature=0.7,
            log=lambda m, l="INFO": logs.append(m),
            bullet_cap=cap,
            **self._deps(gaps),
        )
        return result, logs

    def test_at_cap_scholar_merge_skipped(self):
        """The rig's ch.1 shape: 10 existing bullets + 13 grounded gap-fills
        against a 7-bullet cap → NOTHING merges (was: 19 shipped)."""
        result, logs = self._run([f"b{i}" for i in range(10)], cap=7)
        assert len(result["bullet_points"]) == 10
        assert any("scholar gap-fill merge SKIPPED" in m for m in logs)

    def test_partial_room_merges_only_room(self):
        result, logs = self._run([f"b{i}" for i in range(6)], cap=7)
        assert len(result["bullet_points"]) == 7  # 6 + 1 (room)
        assert any("trimmed" in m for m in logs)

    def test_no_cap_legacy_merge(self):
        result, logs = self._run([f"b{i}" for i in range(3)], cap=None)
        assert len(result["bullet_points"]) == 6  # 3 + 3 grounded


class TestF4RecoveryCap:
    def test_at_cap_nothing_resurrected(self):
        from core.summarisation.quarantine_recovery import recover_quarantined

        entry = types.SimpleNamespace(bullet="A well-grounded bullet that was dropped.")
        quarantine = types.SimpleNamespace(
            recover=lambda source_text: [entry],
            recovery_threshold=0.30,
        )
        logs = []
        bullets = [f"b{i}" for i in range(7)]
        out = recover_quarantined(
            bullets,
            "source",
            quarantine=quarantine,
            log=lambda m, l="INFO": logs.append(m),
            bullet_cap=7,
        )
        assert out == bullets
        assert any("bullet budget reached" in m for m in logs)

    def test_below_cap_resurrects(self):
        from core.summarisation.quarantine_recovery import recover_quarantined

        entry = types.SimpleNamespace(bullet="A well-grounded bullet that was dropped.")
        quarantine = types.SimpleNamespace(
            recover=lambda source_text: [entry],
            recovery_threshold=0.30,
        )
        bullets = [f"b{i}" for i in range(6)]
        out = recover_quarantined(
            bullets,
            "source",
            quarantine=quarantine,
            log=lambda m, l="INFO": None,
            bullet_cap=7,
        )
        assert len(out) == 7
        assert out[-1] == "A well-grounded bullet that was dropped."


# ═══════════════════════════════════════════════════════════════════════════
# F5 (P0) — critique bullets never ship (the exact rig leaks)
# ═══════════════════════════════════════════════════════════════════════════

# Verbatim shapes from the V0.05 rig output (files 002 and 005).
_RIG_CRITIQUE_BULLETS = [
    'Weather impact on schedules omitted: "a sever change in weather throws '
    'the entire schedule out of whack."',
    'Antiquated system age omitted: "In much of the world air traffic is '
    'guided by technology that is more than 30 years old."',
    'Update difficulty of control systems omitted: "updating it has proven '
    'to be difficult if not impossible."',
    'Puzzle solving context omitted: "Puzzle solving is fun, and developers are problem solvers."',
    'Framework origin preference missing: "Prefer frameworks derived from '
    'working code rather than ones cast down from ivory towers."',
    "The summary should clarify that quality attributes are explicitly "
    'defined in the text as "-ilities" (i.e., "quality attributes" (i.e. '
    '"-ilities") of the software being developed).',
    "The specific business and departmental priority lists are not fully "
    'enumerated in the summary: "meeting contractual obligations, generating '
    "revenue, ensuring customer referenceability, containing costs, and "
    'creating valuable technology assets."',
    "The distinct balancing interests of specific roles (CEO, operations "
    "staff, and future programming staff) are omitted from the detailed "
    'examples: "with the cost containment interests of the business\u2018s CEO."',
]

# Verbatim CONTENT bullets from the same run — none of these may be flagged.
_RIG_CONTENT_BULLETS = [
    "The chapter opens with the specific scenario that \"someone's running a "
    'failing project to build a payroll system," framing the discussion in '
    "concrete operational terms.",
    'Borwankar explicitly states that such decisions "very rarely result in '
    'happy outcomes," a direct causal claim about the failure rate of '
    "resume-driven technology choices.",
    'Ramm lists specific technology choices such as "Ruby over Java, or '
    'Python over Smalltalk" and "Postgres rather than Oracle" to illustrate '
    "how technical factors are often unfairly blamed for failure.",
    "Essential complexity is illustrated by air traffic coordination, where "
    '"Every plane\u2018s exact position (including altitude), speed, direction '
    "and destination must be tracked in real time to prevent mid air and "
    'runway collisions."',
    "The source suggests that instead of criticizing a developer for not "
    "letting others speak, you should ask them to help increase other "
    "people's participation in meetings.",
    "Staying abreast of the latest trends and technologies is important but "
    "should never come at the expense of customer needs.",
]


class TestF5CritiqueDetection:
    def test_all_rig_critique_shapes_detected(self):
        from core.summarisation.post_processing import is_summary_self_assessment

        for b in _RIG_CRITIQUE_BULLETS:
            assert is_summary_self_assessment(b), f"must be detected: {b[:60]}"

    def test_rig_content_bullets_pass(self):
        from core.summarisation.post_processing import is_summary_self_assessment

        for b in _RIG_CONTENT_BULLETS:
            assert not is_summary_self_assessment(b), f"false positive: {b[:60]}"

    def test_ship_time_postchecks_drop_critique_bullets(self):
        """The consistency checker FLAGGED these in the rig but shipped them;
        the scar-drop path (classify_scar → is_summary_self_assessment) must
        now remove them from the final bullet list."""
        from core.summarisation.postchecks import run_post_checks

        # the source carries every span the content bullets quote (so the
        # V0.05 F8 quote-verification does not strip their marks — the
        # critique-vs-content comparison must be about the critique class)
        source = (
            "Right now someone's running a failing project to build a payroll "
            "system. Such decisions very rarely result in happy outcomes. "
            "a sever change in weather throws the entire schedule out of "
            "whack. In much of the world air traffic is guided by technology "
            "that is more than 30 years old. Puzzle solving is fun, and "
            "developers are problem solvers."
        )
        report = run_post_checks(
            bullets=_RIG_CRITIQUE_BULLETS + _RIG_CONTENT_BULLETS[:2],
            executive_summary="",
            thorough_summary="",
            source_text=source,
        )
        shipped = set(report.bullets)
        for b in _RIG_CRITIQUE_BULLETS:
            assert b not in shipped, f"critique bullet shipped: {b[:60]}"
        for b in _RIG_CONTENT_BULLETS[:2]:
            assert b in shipped, f"content bullet wrongly dropped: {b[:60]}"


# ═══════════════════════════════════════════════════════════════════════════
# F6 (P1) — a bullet states its claim once (no duplicated/byline quotes)
# ═══════════════════════════════════════════════════════════════════════════


class TestF6QuoteDedupe:
    def test_rig_duplicated_quote_stripped(self):
        """The rig's exact bullet: the quote inline AND appended at the
        end. The trailing duplicate must be stripped."""
        from core.summarisation.postchecks import run_post_checks

        bullet = (
            'Borwankar explicitly states that such decisions "very rarely '
            'result in happy outcomes," a direct causal claim about the '
            'failure rate of resume-driven technology choices. "Such '
            'decisions very rarely result in happy outcomes."'
        )
        source = (
            "Such decisions very rarely result in happy outcomes. The best "
            "thing for your career is a long string of happy customers."
        )
        report = run_post_checks(
            bullets=[bullet],
            executive_summary="",
            thorough_summary="",
            source_text=source,
        )
        assert len(report.bullets) == 1
        out = report.bullets[0]
        assert out.count("very rarely result in happy outcomes") == 1
        assert out.rstrip().endswith("resume-driven technology choices.")
        assert any(i.detector == "quote_dedupe" for i in report.issues)

    def test_rig_byline_echo_stripped(self):
        from core.summarisation.postchecks import run_post_checks

        bullet = (
            "The chapter is authored by Neal Ford, who argues that essential "
            "complexity represents inherent difficulty while accidental "
            'complexity grows from mitigation efforts. "By Neal Ford"'
        )
        source = (
            "It's the duty of the architect to solve the problems inherent "
            "in essential complexity without introducing accidental "
            "complexity. By Neal Ford"
        )
        report = run_post_checks(
            bullets=[bullet],
            executive_summary="",
            thorough_summary="",
            source_text=source,
        )
        out = report.bullets[0]
        assert '"By Neal Ford"' not in out
        assert "authored by Neal Ford" in out  # the prose attribution stays

    def test_non_duplicate_trailing_quote_kept(self):
        """A bullet ending with a quote that is NOT already embedded must
        keep it (the quote is the evidence, not a duplicate)."""
        from core.summarisation.postchecks import run_post_checks

        bullet = (
            "If the current project is not challenging enough, the engineer "
            'should simply "find a more suitable project."'
        )
        source = (
            "If the project isn't cutting edge or challenging enough for "
            "your current career needs then find a more suitable project."
        )
        report = run_post_checks(
            bullets=[bullet],
            executive_summary="",
            thorough_summary="",
            source_text=source,
        )
        assert len(report.bullets) == 1
        assert '"find a more suitable project."' in report.bullets[0]


# ═══════════════════════════════════════════════════════════════════════════
# F7 (P1) — excerpts re-validated at ship time; no heading echo
# ═══════════════════════════════════════════════════════════════════════════


class TestF7Excerpts:
    def _summarizer(self):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        s.request = ConversionRequest(input_path=Path("t.pdf"), output_dir=Path("out"))
        logs = []
        s.log = lambda msg, level="INFO": logs.append(msg)
        return s, logs

    def test_covered_excerpt_pruned(self):
        """The rig's ch.3 pair: the excerpt's sentence is paraphrased by a
        shipped bullet (added AFTER the excerpt was recorded) — at ship time
        the duplicate excerpt must go."""
        s, logs = self._summarizer()
        excerpt = (
            'On "angry frustrated annoyed" — verbatim from the source '
            "(auto-inserted for coverage; not the summarizer's advice): "
            "\"If you're angry, frustrated, annoyed, or otherwise flustered "
            "its very likely that the other person will interpret you "
            "non-verbals as indicating that you're on the attack.\""
        )
        bullet = (
            "When a person is angry, frustrated, annoyed, or flustered, "
            "their non-verbal cues will be likely to be interpreted by "
            "others as aggressive or as an attack."
        )
        kept = s._prune_covered_excerpts(
            bullets=[bullet],
            exec_sum="",
            thorough="",
            excerpts=[excerpt],
        )
        assert kept == []

    def test_uncovered_excerpt_kept(self):
        s, logs = self._summarizer()
        excerpt = (
            'On "fiduciary duty" — verbatim from the source (auto-inserted '
            "for coverage; not the summarizer's advice): \"As an architect "
            "you have been entrusted with the well-being of your "
            "organization and its expected that you will avoid all "
            'conflicts of interest."'
        )
        bullet = "The chapter argues engineers must prioritize customer needs over career goals."
        kept = s._prune_covered_excerpts(
            bullets=[bullet],
            exec_sum="",
            thorough="",
            excerpts=[excerpt],
        )
        assert len(kept) == 1

    def test_heading_echo_stripped_from_excerpt(self):
        """The rig's ch.1 excerpt opened with the chapter heading glued to
        the first sentence (PDF extraction artifact). The echo must be
        stripped and the whitespace collapsed."""
        s, logs = self._summarizer()
        glued = (
            "Don't put your resume ahead of the\n\nrequirements As engineers "
            "we sometimes recommend technologies, methodologies and "
            "approaches for solving problems because deep down we want to "
            "have these on our resume and not because they are the best "
            "solution for the problem."
        )
        s._find_source_sentence = lambda kw, text: glued
        result = {"bullet_points": []}
        s._force_insert_missing(
            "src",
            ["approaches solving problems"],
            result,
            heading="1. Don't put your resume ahead of the requirements",
        )
        assert len(result["source_excerpts"]) == 1
        ex = result["source_excerpts"][0]
        assert "Don't put your resume ahead of the" not in ex
        assert ex.index("As engineers") < ex.index("recommend")
        assert "\n\n" not in ex  # whitespace collapsed inside the quote
