"""V18.15.3 (Phase 5 Stage 3, Batch 4.3) — grounding_check characterization tests.

Byte-for-byte stability gate for ``llm_grounding_check`` extracted from
``Summarizer._llm_grounding_check``. Mocked ``prompt_manager`` /
``call_cloud`` / ``call_llm_with_empty_retry`` so no real LLM is invoked.

Branches covered:
1. empty bullets or empty source → returns []
2. chunking — 25 bullets → 3 LLM calls (chunks of 10/10/5)
3. YES/NO verdict parsing — NO verdicts collected as ungrounded
4. cloud routing when fusion_enabled + fusion_use_for_grounding
5. local routing otherwise (call_llm_with_empty_retry)
6. empty response → chunk skipped (no bullets flagged)
7. exception per chunk → chunk skipped, others proceed
8. source truncation > 20000 chars → appended marker
9. calls_made > 0 → DEBUG log; calls_made == 0 → no log

Run: pytest tests/test_grounding_check.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.grounding_check import llm_grounding_check


class _FakePM:
    def render_template(self, name, **kw):
        return f"PROMPT[{name}] bullets={kw.get('bullet_list', '')[:40]}"


class TestLlmGroundingCheck:
    def test_empty_bullets_returns_empty(self):
        result = llm_grounding_check(
            [], "source", prompt_manager=_FakePM(), log=lambda m, l="INFO": None
        )
        assert result == []

    def test_empty_source_returns_empty(self):
        result = llm_grounding_check(
            ["b1"], "", prompt_manager=_FakePM(), log=lambda m, l="INFO": None
        )
        assert result == []

    def test_chunking_25_bullets_3_calls(self):
        """25 bullets → chunks of 10/10/5 → 3 LLM calls."""
        bullets = [f"bullet {i}" for i in range(25)]
        call_count = {"n": 0}

        def call_llm(prompt, **kw):
            call_count["n"] += 1
            return ""  # empty → skip

        llm_grounding_check(
            bullets,
            "source text",
            prompt_manager=_FakePM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": None,
        )
        assert call_count["n"] == 3

    def test_no_verdicts_collected_as_ungrounded(self):
        """Response with '1: NO' and '2: YES' → bullet[0] flagged ungrounded."""
        bullets = ["bad bullet", "good bullet"]

        def call_llm(prompt, **kw):
            return "1: NO\n2: YES\n"

        result = llm_grounding_check(
            bullets,
            "source text",
            prompt_manager=_FakePM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": None,
        )
        assert result == ["bad bullet"]

    def test_cloud_routing_when_fusion_enabled(self):
        """fusion_enabled + fusion_use_for_grounding → call_cloud used."""
        bullets = ["b1"]
        cloud_calls = {"n": 0}
        local_calls = {"n": 0}

        def call_cloud(prompt, **kw):
            cloud_calls["n"] += 1
            return "1: YES\n"

        def call_local(prompt, **kw):
            local_calls["n"] += 1
            return "1: YES\n"

        llm_grounding_check(
            bullets,
            "src",
            prompt_manager=_FakePM(),
            fusion_enabled=True,
            fusion_use_for_grounding=True,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.4,
            call_llm_with_empty_retry=call_local,
            temperature=0.7,
            log=lambda m, l="INFO": None,
        )
        assert cloud_calls["n"] == 1
        assert local_calls["n"] == 0

    def test_local_routing_when_fusion_disabled(self):
        """fusion disabled → call_llm_with_empty_retry used (not cloud)."""
        bullets = ["b1"]
        cloud_calls = {"n": 0}
        local_calls = {"n": 0}

        def call_cloud(prompt, **kw):
            cloud_calls["n"] += 1
            return "1: YES\n"

        def call_local(prompt, **kw):
            local_calls["n"] += 1
            return "1: YES\n"

        llm_grounding_check(
            bullets,
            "src",
            prompt_manager=_FakePM(),
            fusion_enabled=False,
            fusion_use_for_grounding=True,
            call_cloud=call_cloud,
            fusion_cloud_temperature=0.4,
            call_llm_with_empty_retry=call_local,
            temperature=0.7,
            log=lambda m, l="INFO": None,
        )
        assert cloud_calls["n"] == 0
        assert local_calls["n"] == 1

    def test_empty_response_skips_chunk(self):
        """Empty response → no bullets flagged, but call still counted."""
        bullets = ["b1", "b2"]

        def call_llm(prompt, **kw):
            return ""

        logs = []
        result = llm_grounding_check(
            bullets,
            "src",
            prompt_manager=_FakePM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": logs.append((m, l)),
        )
        assert result == []
        # call was made (calls_made=1) → DEBUG log present
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert len(debugs) == 1
        assert "1 call(s)" in debugs[0]
        assert "0 flagged" in debugs[0]

    def test_exception_per_chunk_continues(self):
        """First chunk raises, second succeeds → only second chunk's verdicts counted."""
        bullets = [f"b{i}" for i in range(12)]  # 2 chunks (10 + 2)
        state = {"i": 0}

        def call_llm(prompt, **kw):
            state["i"] += 1
            if state["i"] == 1:
                raise RuntimeError("transient")
            return "11: NO\n12: YES\n"  # offset = 10 (chunk 2), so bullets[10] flagged

        result = llm_grounding_check(
            bullets,
            "src",
            prompt_manager=_FakePM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": None,
        )
        # chunk 1 raised (skipped), chunk 2 returned "11: NO" → bullets[10]
        assert result == ["b10"]

    def test_source_truncation_marker(self):
        """Source > 20000 chars → truncation marker appended."""
        bullets = ["b1"]
        captured = {}

        class _PM:
            def render_template(self, name, **kw):
                captured["source"] = kw["truncated_source"]
                return "P"

        def call_llm(prompt, **kw):
            return "1: YES\n"

        long_src = "S" * 25000
        llm_grounding_check(
            bullets,
            long_src,
            prompt_manager=_PM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": None,
        )
        assert captured["source"].endswith("\n[... source truncated ...]")
        # first 20000 chars of source preserved
        assert captured["source"].startswith("S" * 20000)

    def test_no_calls_no_log(self):
        """If no LLM calls made (all raised before counting) → no DEBUG log.

        Note: in the current code calls_made is incremented AFTER the LLM call
        returns (before the empty-check), so a raised exception skips the
        increment. With every chunk raising, calls_made stays 0 → no log.
        """
        bullets = ["b1"]

        def call_llm(prompt, **kw):
            raise RuntimeError("always fails")

        logs = []
        result = llm_grounding_check(
            bullets,
            "src",
            prompt_manager=_FakePM(),
            call_llm_with_empty_retry=call_llm,
            log=lambda m, l="INFO": logs.append((m, l)),
        )
        assert result == []
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert debugs == []
