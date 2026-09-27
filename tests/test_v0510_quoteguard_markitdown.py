"""V0.5.10 (gap-fill quote-guard fallback + markitdown deferred) tests.

Covers the 2 V0.5.10 sub-tasks:

PART 1 — Gap-fill quote-guard fallback for regex-confirmed authors
  (``core/summarisation/gap_fill_batch.py`` + ``chapter_phases.py``):
  The V0.5.6 loosened quote-guard fired only for GLOSSARY-sourced authors.
  But the V0.5.6→V0.5.9 audits showed the LLM glossary call STILL failed
  (the master-summary returned EMPTY 3 times → no ``<name_glossary>`` block
  parsed → the loosened override never fired → the 4 still-missing authors
  stayed missing because the strict V18.20.3.2 veto dropped their bullets).
  The V0.5.10 FALLBACK: if the glossary is NOT available OR the author is
  NOT in the glossary, check if the author is in the REGEX
  ``extract_citations`` output. If yes → ALSO loosen the veto (accept the
  bullet with a "grounded-in-regex-extraction" grounding level).

PART 2 — F3 markitdown deferred background-thread import
  (``core/system/preflight_check.py``):
  The V0.5.4 brainstorm (TRACK-F → F3) documented this as a future
  optimization. markitdown takes ~7.9s (a REQUIRED dep, can't skip —
  ``core.pdf`` imports it eagerly for text extraction). A background-thread
  import parallelised with the rest of the preflight saves ~7s off the
  preflight wall-clock (the rig's V0.5.0→V0.5.2 measured preflight total of
  18-23s drops to ~11-16s — markitdown overlaps with the other deps' eager
  imports). Conservative scope: ONLY markitdown (the slowest required dep).
  The other required deps (pypdf, pdf2image, tiktoken, rapidfuzz) stay eager
  (<1s each). Fail-open: if the thread crashes (any BaseException), fall
  back to the eager ``_is_importable`` (matching the V18.20.3.3 crash-fix #3
  contract).

Content-agnostic (Rule 1): the author names in the gap-fill tests are TEST
FIXTURES (Epsilon / Zeta / FabricatedAuthor) — they do NOT appear in
runtime code. The production loosened quote-guard uses the RUNTIME regex
``extract_citations`` output (passed as ``regex_confirmed_authors`` by
``chapter_phases.py``). The markitdown tests do not hardcode any package
names beyond the existing ``_REQUIRED_DEPS`` entry for ``markitdown``.
"""

from __future__ import annotations

import importlib
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Stub the optional heavy deps exactly like tests/test_v054_verification_layer.py
# (markitdown) and tests/test_gap_fill_batch.py (tiktoken + markitdown) —
# both modules are imported eagerly by the core.summarisation chain.
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = lambda *a, **k: None
    sys.modules["markitdown"] = _md
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")

    class _E:
        pass

    _tk.Encoding = _E
    _tk.get_encoding = lambda *a, **k: None
    sys.modules["tiktoken"] = _tk

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ─────────────────────────────────────────────────────────────────────────────
# Shared test scaffolding for the gap-fill tests (mirrors
# tests/test_v056_verification_glossary.py + tests/test_gap_fill_batch.py).
# ─────────────────────────────────────────────────────────────────────────────


class _CapturingLog:
    """Captures (msg, level) pairs — mirrors tests/test_gap_fill_batch.py."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _make_gap_fill_deps(*, responses=None, response_fn=None):
    """Build hermetic deps for batch_gap_fill (mirrors tests/test_gap_fill_batch.py)."""
    log = _CapturingLog()
    llm_calls = []

    def check_coverage(analysis, text):
        text = text or ""
        covered = [a for a in analysis["authors"] if a in text]
        missing = [a for a in analysis["authors"] if a not in text]
        total = len(analysis["authors"])
        pct = (len(covered) / total) if total else 0.0
        return {"covered": covered, "missing": missing, "total": total, "coverage_pct": pct}

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
        i = len(llm_calls)
        llm_calls.append({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})
        if response_fn is not None:
            return response_fn(prompt, i)
        if responses is not None and i < len(responses):
            return responses[i]
        return None

    def strip_thinking(text):
        return text

    def filter_thinking_bullets(bullets, concepts=None, source_text=""):
        return list(bullets)

    return {
        "log": log,
        "check_coverage": check_coverage,
        "call_fast_llm": call_fast_llm,
        "strip_thinking": strip_thinking,
        "filter_thinking_bullets": filter_thinking_bullets,
        "llm_calls": llm_calls,
    }


def _run_gap_fill(
    deps,
    *,
    content,
    bullets,
    missing,
    analysis,
    det_authors,
    heading="Chapter 1 — Test",
    source_glossary=None,
    regex_confirmed_authors=None,
):
    from core.summarisation.gap_fill_batch import batch_gap_fill

    return batch_gap_fill(
        heading,
        content,
        bullets,
        missing,
        analysis,
        det_authors,
        check_coverage=deps["check_coverage"],
        call_fast_llm=deps["call_fast_llm"],
        temperature=0.2,
        strip_thinking=deps["strip_thinking"],
        filter_thinking_bullets=deps["filter_thinking_bullets"],
        log=deps["log"],
        source_glossary=source_glossary,
        regex_confirmed_authors=regex_confirmed_authors,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PART 1 — Gap-fill quote-guard fallback for regex-confirmed authors
# ═══════════════════════════════════════════════════════════════════════════


class TestQuoteGuardRegexFallback:
    """V0.5.10: the V18.20.3.2 parenthetical-promotion veto (the
    "quote-guard") is LOOSENED for REGEX-confirmed authors when no
    glossary is available. The regex ``extract_citations`` output is the
    deterministic source-roster the LAYER already trusts as the V0.5.5
    fallback when no glossary is available — the V0.5.10 fallback uses
    the same roster to loosen the veto (accept the bullet with a
    "grounded-in-regex-extraction" grounding level).
    """

    def test_quote_guard_loosened_for_regex_confirmed_authors(self):
        """A gap-fill bullet for an author in ``extract_citations`` (the
        ``regex_confirmed_authors`` list) with NO glossary → ACCEPTED via
        the V0.5.10 loosened override. The V0.5.10 INFO log line fires;
        the V0.5.6 glossary log line does NOT fire (no glossary).
        """
        from core.summarisation.gap_fill_batch import GapFillOutcome

        # Source: Zeta established the framework, drawing on Epsilon (1948).
        # The bullet misattributes the framework to Epsilon → the
        # V18.20.3.2 parenthetical-promotion veto FIRES (correctly, per
        # the existing strict path — Zeta is the real subject).
        # NO glossary is provided → the V0.5.6 loosened override does NOT
        # fire. But Epsilon IS in the regex extract_citations output
        # (passed as regex_confirmed_authors) → the V0.5.10 fallback
        # loosens the veto + accepts the bullet anyway.
        src = (
            "Zeta established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bad = "- Epsilon: Established the unified framework of identity development."
        deps = _make_gap_fill_deps(responses=[bad])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Zeta"],
            # NO glossary → V0.5.6 doesn't fire.
            source_glossary=None,
            # Epsilon is in the regex extract_citations output → V0.5.10 fires.
            regex_confirmed_authors=["Epsilon", "Zeta"],
        )
        # The V0.5.10 loosened override ACCEPTED the bullet (was: dropped
        # by the strict V18.20.3.2 veto on the V0.5.5 path).
        assert isinstance(out, GapFillOutcome)
        assert len(bullets) == 1, (
            "V0.5.10: the loosened quote-guard should ACCEPT the bullet "
            "for the regex-confirmed author Epsilon (was: dropped by the "
            "strict V18.20.3.2 veto on the V0.5.5 path)."
        )
        assert "Epsilon" in bullets[0]
        # The V0.5.10 INFO log should fire.
        all_logs = [m for m, _ in deps["log"].calls]
        v0510_accept_logs = [
            m
            for m in all_logs
            if "✨ V0.5.10 gap-fill: accepted bullet for 'Epsilon'" in m
            and "grounded in regex extract_citations" in m
        ]
        assert v0510_accept_logs, (
            "V0.5.10: the INFO log line '✨ V0.5.10 gap-fill: accepted "
            "bullet for 'Epsilon' (grounded in regex extract_citations, "
            "not verbatim quote)' should fire when the loosened "
            "quote-guard accepts a regex-backed bullet; got logs: "
            f"{all_logs}"
        )
        # The V0.5.6 glossary log line should NOT fire (no glossary).
        v056_accept_logs = [m for m in all_logs if "✨ V0.5.6 gap-fill: accepted bullet for" in m]
        assert not v056_accept_logs, (
            "V0.5.10: the V0.5.6 loosened-override log line should NOT "
            "fire when no glossary is provided (the V0.5.10 fallback "
            "should fire instead)"
        )
        # The strict V18.20.3.2 veto WARNING should NOT fire (the
        # loosened override accepted the bullet — the veto's "continue"
        # path is skipped).
        v_veto_logs = [m for m in all_logs if "V18.20.3.2: gap-fill active-subject veto" in m]
        assert not v_veto_logs, (
            "V0.5.10: the V18.20.3.2 veto WARNING should NOT fire when "
            "the loosened override accepts the bullet"
        )

    def test_quote_guard_strict_for_unknown_authors(self):
        """A gap-fill bullet for an author NOT in
        ``regex_confirmed_authors`` AND NOT in the glossary → DROPPED
        (the strict V18.20.3.2 veto — the V0.5.5 behavior, prevents
        fabrication). No V0.5.6 / V0.5.10 loosened-override log line
        fires.

        Setup: the source DOES cite Epsilon as a parenthetical (so the
        V18.20.3.2 veto detects the parenthetical promotion + fires the
        strict path). The caller passed a ``regex_confirmed_authors``
        list that does NOT include Epsilon (simulates a caller that
        passes a partial/stale regex output — e.g., the analysis ran on
        a different segment). The V0.5.10 fallback checks membership in
        ``regex_confirmed_authors`` → Epsilon is NOT in the list → the
        fallback does NOT fire → the strict V18.20.3.2 veto DROPS the
        bullet.
        """
        from core.summarisation.gap_fill_batch import GapFillOutcome

        # Source: Zeta established the framework, drawing on Epsilon
        # (1948). The bullet misattributes the framework to Epsilon →
        # the V18.20.3.2 parenthetical-promotion veto FIRES (correctly,
        # per the existing strict path — Zeta is the real subject).
        # NO glossary is provided → the V0.5.6 loosened override does
        # NOT fire. Epsilon is NOT in regex_confirmed_authors (only
        # Zeta is) → the V0.5.10 fallback does NOT fire. The strict
        # V18.20.3.2 veto DROPS the bullet.
        src = (
            "Zeta established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bad = "- Epsilon: Established the unified framework of identity development."
        deps = _make_gap_fill_deps(responses=[bad, bad, bad])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            # det_authors is the analysis-extracted list (used by
            # detect_parenthetical_promotion for pronoun-antecedent
            # resolution) — it includes Epsilon because the source
            # cites Epsilon (1948).
            det_authors=["Epsilon", "Zeta"],
            # NO glossary → V0.5.6 doesn't fire.
            source_glossary=None,
            # Epsilon is NOT in regex_confirmed_authors (only Zeta is) →
            # V0.5.10 doesn't fire (simulates a caller that passes a
            # partial/stale regex output).
            regex_confirmed_authors=["Zeta"],
        )
        assert isinstance(out, GapFillOutcome)
        # The strict veto DROPPED the bullet (the V0.5.5 behavior).
        assert bullets == [], (
            "V0.5.10: the strict V18.20.3.2 veto should DROP the bullet "
            "for the claimed author Epsilon (NOT in regex_confirmed_"
            "authors AND not in the glossary — no loosened override fires)"
        )
        # The V0.5.6 + V0.5.10 loosened-override log lines should NOT fire.
        all_logs = [m for m, _ in deps["log"].calls]
        v056_accept_logs = [m for m in all_logs if "✨ V0.5.6 gap-fill: accepted bullet for" in m]
        v0510_accept_logs = [m for m in all_logs if "✨ V0.5.10 gap-fill: accepted bullet for" in m]
        assert not v056_accept_logs, (
            "V0.5.10: the V0.5.6 loosened-override log line should NOT "
            "fire when no glossary is provided"
        )
        assert not v0510_accept_logs, (
            "V0.5.10: the V0.5.10 loosened-override log line should NOT "
            "fire when the author is NOT in regex_confirmed_authors"
        )
        # The V18.20.3.2 veto WARNING should fire (the strict path).
        v_veto_logs = [m for m in all_logs if "V18.20.3.2: gap-fill active-subject veto" in m]
        assert v_veto_logs, (
            "V0.5.10: the V18.20.3.2 veto WARNING should fire on the "
            "strict path (claimed author not in regex_confirmed_authors)"
        )

    def test_quote_guard_glossary_takes_precedence_over_regex(self):
        """When BOTH the glossary AND the regex list contain the author,
        the V0.5.6 glossary-backed override fires FIRST (the glossary is
        the richer grounding). The V0.5.10 log line does NOT fire.
        """
        from core.summarisation.gap_fill_batch import GapFillOutcome

        # Same source as the regex-confirmed test, but WITH a glossary.
        # The V0.5.6 glossary-backed override fires FIRST (Epsilon is in
        # the glossary). The V0.5.10 regex-backed override would have
        # fired too, but it's only checked if the glossary path is
        # skipped (the elif branch).
        src = (
            "Zeta established the unified framework of identity "
            "development, drawing on Epsilon (1948)."
        )
        bad = "- Epsilon: Established the unified framework of identity development."
        glossary = {
            "names": [
                {"name": "Epsilon", "year": "1948", "context": "cited as a precursor"},
            ],
            "path": "summaries/.glossaries/ch_test.glossary.md",
        }
        deps = _make_gap_fill_deps(responses=[bad])
        bullets: list[str] = []
        out = _run_gap_fill(
            deps,
            content=src,
            bullets=bullets,
            missing=["Epsilon"],
            analysis={"authors": ["Epsilon"]},
            det_authors=["Epsilon", "Zeta"],
            source_glossary=glossary,
            regex_confirmed_authors=["Epsilon", "Zeta"],
        )
        assert isinstance(out, GapFillOutcome)
        assert len(bullets) == 1, (
            "V0.5.10: the loosened quote-guard should ACCEPT the bullet "
            "(either glossary or regex grounding)."
        )
        # The V0.5.6 glossary log line should fire (precedence).
        all_logs = [m for m, _ in deps["log"].calls]
        v056_accept_logs = [
            m for m in all_logs if "✨ V0.5.6 gap-fill: accepted bullet for 'Epsilon'" in m
        ]
        assert v056_accept_logs, (
            "V0.5.10: the V0.5.6 glossary log line should fire FIRST "
            "when the author is in BOTH the glossary + the regex list"
        )
        # The V0.5.10 regex log line should NOT fire (the glossary
        # path took precedence — the elif branch was skipped).
        v0510_accept_logs = [
            m for m in all_logs if "✨ V0.5.10 gap-fill: accepted bullet for 'Epsilon'" in m
        ]
        assert not v0510_accept_logs, (
            "V0.5.10: the V0.5.10 regex log line should NOT fire when "
            "the V0.5.6 glossary path took precedence (the elif branch "
            "was skipped)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# PART 2 — F3 markitdown deferred background-thread import
# ═══════════════════════════════════════════════════════════════════════════


class TestMarkitdownBgImport:
    """V0.5.10: the preflight starts the markitdown import in a
    background daemon thread (parallel with the rest of the preflight),
    then joins the thread before the markitdown check. If the thread
    crashes, falls back to the eager ``_is_importable`` (fail-open,
    matching the V18.20.3.3 crash-fix #3 contract).
    """

    def test_markitdown_background_import(self, monkeypatch):
        """V0.5.10: the preflight starts the markitdown import in a
        background thread + joins before the markitdown check. The thread
        pattern is verified by mocking the import (the markitdown import
        runs in a DIFFERENT thread, not the main thread; the V0.5.10
        log line fires; the preflight passes when the import succeeds).
        """
        from core.system import preflight_check as pc

        # Isolate the test: ONLY markitdown in _REQUIRED_DEPS + no
        # optional deps (so the eager _is_importable path for the other
        # deps doesn't pollute the call log).
        monkeypatch.setattr(
            pc,
            "_REQUIRED_DEPS",
            [
                (
                    "markitdown",
                    "markitdown (text extraction)",
                    "pip install markitdown",
                    lambda r: True,
                )
            ],
        )
        monkeypatch.setattr(pc, "_OPTIONAL_DEPS", [])

        main_thread_id = threading.current_thread().ident
        import_thread_ids: list[int] = []
        real_import_module = importlib.import_module

        def fake_import_module(name):
            if name == "markitdown":
                # Track which thread ran the markitdown import.
                import_thread_ids.append(threading.current_thread().ident)
                # Return a fake module (the import "succeeds" via the
                # thread — no eager fallback fires).
                return types.ModuleType("markitdown")
            # Other deps: use the real import_module (only markitdown is
            # in _REQUIRED_DEPS here, but be defensive).
            return real_import_module(name)

        logs: list[tuple[str, str]] = []

        with patch(
            "core.system.preflight_check.importlib.import_module",
            side_effect=fake_import_module,
        ):
            result = pc.run_preflight_check(
                SimpleNamespace(),
                log_callback=lambda m, l="INFO": logs.append((m, l)),
            )

        # No missing deps (markitdown imported successfully via the thread).
        assert result is None, (
            f"V0.5.10: preflight should pass when markitdown imports "
            f"successfully via the background thread; got: {result!r}"
        )

        # The markitdown import ran in a DIFFERENT thread (not the main
        # thread) — proves the background-thread pattern fires.
        assert import_thread_ids, "V0.5.10: markitdown import should have been called at least once"
        non_main_thread_ids = [tid for tid in import_thread_ids if tid != main_thread_id]
        assert non_main_thread_ids, (
            f"V0.5.10: the markitdown import should run in a BACKGROUND "
            f"thread, not the main thread; got thread ids {import_thread_ids}, "
            f"main={main_thread_id}"
        )

        # The V0.5.10 background-import-start log line should fire.
        start_logs = [
            (m, l)
            for m, l in logs
            if "V0.5.10" in m and "markitdown import started in background" in m
        ]
        assert start_logs, (
            f"V0.5.10: the 'markitdown import started in background' log "
            f"line should fire; got logs: {logs}"
        )

        # The success log line should fire (the thread succeeded, no
        # eager fallback).
        ok_logs = [m for m, _ in logs if "background import completed" in m]
        assert ok_logs, (
            f"V0.5.10: the 'background import completed' log line should "
            f"fire when the thread succeeds; got logs: {logs}"
        )

        # The fallback log line should NOT fire (the thread succeeded).
        fallback_logs = [(m, l) for m, l in logs if "V0.5.10" in m and "crashed" in m]
        assert not fallback_logs, (
            "V0.5.10: the crash/fallback log line should NOT fire when the thread succeeded"
        )

    def test_markitdown_fallback_to_eager_on_thread_crash(self, monkeypatch):
        """V0.5.10: if the background thread crashes (any BaseException),
        fall back to the eager ``_is_importable`` (fail-open). The eager
        path has the proper error handling for ImportError / Exception /
        BaseException (matching the V18.20.3.3 crash-fix #3 contract).
        """
        from core.system import preflight_check as pc

        # Isolate the test: ONLY markitdown in _REQUIRED_DEPS + no
        # optional deps.
        monkeypatch.setattr(
            pc,
            "_REQUIRED_DEPS",
            [
                (
                    "markitdown",
                    "markitdown (text extraction)",
                    "pip install markitdown",
                    lambda r: True,
                )
            ],
        )
        monkeypatch.setattr(pc, "_OPTIONAL_DEPS", [])

        main_thread_id = threading.current_thread().ident
        # Track each import attempt with the thread id that ran it.
        import_attempts: list[tuple[int, int]] = []
        attempt_counter = [0]
        real_import_module = importlib.import_module

        def fake_import_module(name):
            if name == "markitdown":
                attempt_counter[0] += 1
                import_attempts.append((attempt_counter[0], threading.current_thread().ident))
                # Simulate a crash (RuntimeError — an Exception subclass,
                # NOT ImportError or BaseException-only). The thread's
                # `except BaseException` catches it → thread.success=False.
                # The eager fallback `_is_importable` then re-raises the
                # same RuntimeError → caught by `_is_importable`'s
                # `except Exception` → returns True (with warning, the
                # V18.20.3.3 "treating as installable, error will surface
                # at use time" behavior).
                raise RuntimeError("simulated markitdown import crash")
            return real_import_module(name)

        logs: list[tuple[str, str]] = []

        with patch(
            "core.system.preflight_check.importlib.import_module",
            side_effect=fake_import_module,
        ):
            result = pc.run_preflight_check(
                SimpleNamespace(),
                log_callback=lambda m, l="INFO": logs.append((m, l)),
            )

        # The eager fallback's _is_importable catches Exception → returns
        # True (with warning — the V18.20.3.3 "treating as installable,
        # error will surface at use time" behavior). So the preflight
        # passes (no missing deps).
        assert result is None, (
            f"V0.5.10: preflight should pass via eager fallback "
            f"(Exception → True, the V18.20.3.3 behavior); got: {result!r}"
        )

        # The import was attempted TWICE: once in the background thread
        # (which crashed), once in the eager fallback. This verifies the
        # fallback path fired.
        assert len(import_attempts) == 2, (
            f"V0.5.10: the markitdown import should be attempted twice "
            f"(once in the background thread, once in the eager fallback); "
            f"got {len(import_attempts)} attempts: {import_attempts}"
        )

        # The first attempt was in a DIFFERENT thread (the background
        # thread — not the main thread).
        assert import_attempts[0][1] != main_thread_id, (
            f"V0.5.10: the first attempt (background thread) should be "
            f"in a different thread; got thread id {import_attempts[0][1]}, "
            f"main={main_thread_id}"
        )

        # The second attempt (eager fallback) was in the MAIN thread
        # (the preflight's loop runs in the main thread).
        assert import_attempts[1][1] == main_thread_id, (
            f"V0.5.10: the second attempt (eager fallback) should be "
            f"in the main thread; got thread id {import_attempts[1][1]}, "
            f"main={main_thread_id}"
        )

        # The fallback log line should fire (the thread crashed →
        # "falling back to eager import").
        crash_logs = [
            (m, l)
            for m, l in logs
            if "V0.5.10" in m and "crashed" in m and "falling back to eager" in m
        ]
        assert crash_logs, (
            f"V0.5.10: the fallback log line ('markitdown background "
            f"import crashed ... falling back to eager import') should "
            f"fire when the thread crashes; got logs: {logs}"
        )

        # The eager fallback's WARNING log line should fire (the
        # V18.20.3.3 "treating as installable, error will surface at
        # use time" warning, emitted by _is_importable's `except
        # Exception` branch).
        eager_warning_logs = [
            m
            for m, _ in logs
            if "markitdown" in m and "import raised" in m and "treating as installable" in m
        ]
        assert eager_warning_logs, (
            f"V0.5.10: the eager fallback's _is_importable WARNING log "
            f"line ('markitdown import raised RuntimeError: ... treating "
            f"as installable') should fire; got logs: {logs}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
