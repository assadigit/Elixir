"""V18.20.4.11 (P2) — TLS chapter-context + buried-log WARNINGs + model literals.

Three fix batches, one file (clearly sectioned):

FIX A (W-a1 / T-a3) — the 7 shared Summarizer chapter-context attributes
(``_source_text``, ``_current_heading``, ``_primary_thorough_cot_nuked``,
``_primary_exec_cot_nuked``, ``_thorough_is_synthetic``, ``_last_coverage``,
``_chapter_deadline_start``) are now property shims backed by a per-instance
``threading.local``. Tests: per-thread isolation for each attribute, correct
defaults on bare (``object.__new__``) instances, the parallel-path deadline
stamp moving INTO ``process_chapter`` (per-worker, still observed non-None
by ``_summarize_inner``), and 2-worker concurrent characterization.

FIX B (W-a12) — four previously DEBUG-buried honesty-machinery failures now
WARN. Tests drive the enclosing paths (the parse-time CoT gate and the
thorough-judge re-run via a stubbed ``_summarize_inner`` drive; the
checkpoint writer and the quality-report handler at their boundaries) and
assert a WARNING-level entry was captured.

FIX C (W-a7 partial) — the legacy default-model literals de-duplicated into
``core.llm.model_taxonomy`` (``LEGACY_DEFAULT_MODEL`` /
``DEFAULT_FALLBACK_OCR_MODEL``). Tests pin the constant values, the
dataclass defaults, and source-scan the 5 previously-duplicated files for
remaining bare CODE literals (docstrings allowed, comments ignored — an
ast-based scan, so only real string constants are flagged).

Hermetic: markitdown + tiktoken + utils.token_counter stubbed in sys.modules
(the tests/test_bullet_pipeline_golden.py:40-79 pattern) and restored after
this module's tests; the Summarizer is built via ``object.__new__`` with only
the attrs the tested paths need (the tests/test_summarizer.py:188 pattern) —
no Qt, no network, no __init__ (except the one full-init smoke test).

Run: ``pytest tests/test_v1820411_p2_tls_logs_literals.py -v``
"""

from __future__ import annotations

import ast
import sys
import threading
import time
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Hermetic stubs (order matters: before the summarizer import) ───────────


def _stub_module(name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


if "utils.token_counter" not in sys.modules:
    _stub_module(
        "utils.token_counter",
        count_tokens=lambda t: max(1, len(str(t).split())),
        truncate_by_tokens=lambda t, m, add_ellipsis=False: t,
    )


# V18.20.2.0 (SWOT test-infra): un-stub after this module's tests — the
# module-level stubs above replaced sys.modules entries unconditionally and
# must be restored so later test files resolve the real modules (the
# tests/test_bullet_pipeline_golden.py:64-79 pattern).
@pytest.fixture(scope="module", autouse=True)
def _unstub_modules_after_tests():
    yield
    for _name in ("tiktoken", "utils.token_counter"):
        sys.modules.pop(_name, None)
    try:
        import tiktoken  # noqa: F401 — re-import the real package

        import utils.token_counter  # noqa: F401
    except Exception:  # pragma: no cover - defensive
        pass


from core.llm.model_taxonomy import (  # noqa: E402
    DEFAULT_FALLBACK_OCR_MODEL,
    LEGACY_DEFAULT_MODEL,
)
from core.summarisation.quarantine import QuarantineLog  # noqa: E402
from core.summarisation.summarizer import Summarizer  # noqa: E402

_SUMMARIZER_SRC = (_project_root / "core" / "summarisation" / "summarizer.py").read_text(
    encoding="utf-8"
)


def _capturing_log(calls: list):
    def _log(msg: str, level: str = "INFO") -> None:
        calls.append((level, msg))

    return _log


def _warnings(calls) -> list[str]:
    return [m for lvl, m in calls if lvl == "WARNING"]


# ════════════════════════════════════════════════════════════════════════════
# FIX A — thread-local chapter context (W-a1 / T-a3)
# ════════════════════════════════════════════════════════════════════════════


class TestChapterContextTLS:
    """The 7 property shims isolate per-thread chapter context."""

    def _bare(self) -> Summarizer:
        return object.__new__(Summarizer)

    def test_bare_instance_defaults_match_reader_fallbacks(self):
        """Bare instances (object.__new__, the characterization-test pattern)
        must see the exact defaults every reader's getattr-fallback used
        pre-TLS: "" / "" / False×3 / 0.0 / None."""
        s = self._bare()
        assert s._source_text == ""
        assert s._current_heading == ""
        assert s._primary_thorough_cot_nuked is False
        assert s._primary_exec_cot_nuked is False
        assert s._thorough_is_synthetic is False
        assert s._last_coverage == 0.0
        assert s._chapter_deadline_start is None
        # The getattr-with-default reader syntax (bullet_pipeline ×6) must
        # never see a missing attribute:
        assert getattr(s, "_current_heading", "MISSING") == ""
        assert getattr(s, "_last_coverage", "MISSING") == 0.0
        assert getattr(s, "_chapter_deadline_start", "MISSING") is None

    def test_current_heading_tls_isolation(self):
        """Main sets 'A', worker sets 'B' — each thread reads its own."""
        s = self._bare()
        s._current_heading = "A"
        seen = {}

        def worker():
            s._current_heading = "B"
            seen["worker"] = s._current_heading

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert seen["worker"] == "B"
        assert s._current_heading == "A"

    def test_source_text_and_cot_flags_tls_isolation(self):
        """_source_text + the 3 per-chapter CoT/synthetic flags are isolated
        per thread (the V18.20.3.2 reset could not do this under >1 workers)."""
        s = self._bare()
        s._source_text = "main-src"
        s._primary_thorough_cot_nuked = True
        s._primary_exec_cot_nuked = True
        s._thorough_is_synthetic = False
        seen = {}

        def worker():
            s._source_text = "worker-src"
            s._primary_thorough_cot_nuked = False
            s._thorough_is_synthetic = True
            seen.update(
                source=s._source_text,
                thorough_cot=s._primary_thorough_cot_nuked,
                exec_cot=s._primary_exec_cot_nuked,
                synthetic=s._thorough_is_synthetic,
            )

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert seen == {
            "source": "worker-src",
            "thorough_cot": False,
            "exec_cot": False,  # worker never wrote it → main's True is NOT visible
            "synthetic": True,
        }
        assert s._source_text == "main-src"
        assert s._primary_thorough_cot_nuked is True
        assert s._thorough_is_synthetic is False

    def test_last_coverage_tls_isolation(self):
        """_last_coverage (self-review skip decision) is per-thread."""
        s = self._bare()
        s._last_coverage = 0.25
        seen = {}

        def worker():
            seen["before"] = s._last_coverage  # default, not main's 0.25
            s._last_coverage = 0.9
            seen["after"] = s._last_coverage

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert seen == {"before": 0.0, "after": 0.9}
        assert s._last_coverage == 0.25

    def test_deadline_start_worker_stamp_main_sees_default(self):
        """process_chapter-style flow: a worker stamps its own deadline start;
        the main thread still sees its own (default None — never the worker's
        value, and the worker NEVER sees None)."""
        s = self._bare()
        assert s._chapter_deadline_start is None
        seen = {}

        def worker():
            s._chapter_deadline_start = time.time()  # process_chapter first line
            seen["worker"] = s._chapter_deadline_start

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert isinstance(seen["worker"], float) and seen["worker"] > 0
        assert s._chapter_deadline_start is None  # main thread unaffected

    def test_two_workers_concurrent_distinct_headings(self):
        """Characterization: 2 concurrent threads each set their own
        _current_heading and both read back their OWN value (no interleaving
        corruption — the pre-TLS shared attribute could not guarantee this)."""
        s = self._bare()
        n = 8
        barrier = threading.Barrier(n)
        errors: list[str] = []
        heading_by_thread = {i: f"Chapter-{i}" for i in range(n)}

        def worker(i: int):
            barrier.wait()
            for _ in range(50):  # hammer the property to expose races
                s._current_heading = heading_by_thread[i]
                got = s._current_heading
                if got != heading_by_thread[i]:
                    errors.append(f"thread {i} read {got!r}")
                    return

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors

    def test_full_init_arms_tls_and_thermal_guard_writes_through_property(self, tmp_path):
        """A real __init__ run (the only place _chapter_tls is created
        eagerly) must survive: _init_thermal_guard writes
        _chapter_deadline_start=None through the property setter before any
        chapter runs."""
        from core.models import ConversionRequest

        req = ConversionRequest(input_path=Path("book.pdf"), output_dir=Path(tmp_path))
        s = Summarizer(req, log_callback=lambda msg, level="INFO": None)
        assert isinstance(getattr(s, "_chapter_tls", None), threading.local)
        assert s._chapter_deadline_start is None
        # A main-thread write post-init behaves exactly like pre-TLS:
        s._current_heading = "Chapter 1"
        assert s._current_heading == "Chapter 1"

    def test_parallel_path_stamps_deadline_per_worker(self):
        """summarize_chapters (parallel, max_workers=2): every worker's
        _summarize_inner must observe a FRESH non-None deadline start stamped
        by process_chapter on the worker's own thread (the V18.20.2.0 A8
        contract, now exact per-chapter), and the MAIN thread's TLS stays
        untouched (None)."""
        from core.models import SummaryResult

        s = object.__new__(Summarizer)
        s.log = lambda msg, level="INFO": None
        s.max_workers = 2
        s.is_local = True
        s.local_chapter_deadline = 2400
        observed: list = []
        lock = threading.Lock()

        def fake_inner(heading, content, concepts=None, callouts=None, book_context=""):
            with lock:
                observed.append((heading, getattr(s, "_chapter_deadline_start", None)))
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=True,
            )

        s._summarize_inner = fake_inner
        chapters = [{"heading": f"Ch {i}", "content": f"c{i}"} for i in range(4)]
        t0 = time.time()
        results = s.summarize_chapters(chapters)
        assert len(results) == 4 and all(r.success for r in results)
        assert len(observed) == 4
        for heading, start in observed:
            assert start is not None, f"{heading}: deadline start not set on worker thread"
            assert isinstance(start, float) and t0 - 1.0 <= start <= time.time() + 1.0
        # Main thread's own TLS slot was never written by the workers:
        assert s._chapter_deadline_start is None

    def test_sequential_path_deadline_same_thread(self):
        """The sequential path (max_workers=1) is unchanged: the main thread
        writes the stamp pre-call and _summarize_inner (same thread) reads
        it — TLS resolves to the same slot naturally."""
        from core.models import SummaryResult

        s = object.__new__(Summarizer)
        s.log = lambda msg, level="INFO": None
        s.max_workers = 1
        s.is_local = True
        s.local_chapter_deadline = 2400
        observed: list = []

        def fake_inner(heading, content, concepts=None, callouts=None, book_context=""):
            observed.append(getattr(s, "_chapter_deadline_start", None))
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=True,
            )

        s._summarize_inner = fake_inner
        results = s.summarize_chapters([{"heading": "H", "content": "c"}])
        assert results[0].success is True
        assert len(observed) == 1 and isinstance(observed[0], float)

    def test_bullet_pipeline_reads_resolve_through_property(self):
        """bullet_pipeline.py was NOT edited (per the fix design): its
        ``getattr(s, "_current_heading", "")`` reads must resolve through the
        property transparently — pinned by source + a live resolution check."""
        bp_src = (_project_root / "core" / "summarisation" / "bullet_pipeline.py").read_text(
            encoding="utf-8"
        )
        assert bp_src.count('getattr(s, "_current_heading", "")') >= 6
        s = self._bare()
        s._current_heading = "Live Chapter"
        assert getattr(s, "_current_heading", "") == "Live Chapter"
        assert getattr(s, "_current_heading", "") or "" == "Live Chapter"


# ════════════════════════════════════════════════════════════════════════════
# FIX B — buried DEBUG logs raised to WARNING (W-a12)
# ════════════════════════════════════════════════════════════════════════════

# A CoT-shaped primary thorough (3+ detect_cot_narrative markers, >50 chars —
# the same shape tests/test_v1820313_thorough_floor.py:142 uses).
_COT_THOROUGH = (
    "Let me organize my understanding of this chapter first. "
    "Let me count carefully how many contributors are mentioned. "
    "Let me draft each section now before writing the summary."
)

# A plain (non-CoT) thorough for the happy-path drive.
_PLAIN_THOROUGH = (
    "This chapter develops an integrative account of structure formation. "
    "The survey begins from early baseline formulations, works through the "
    "competing frameworks, and resolves them into a single layered account "
    "that retains each framework's explanatory strength. The closing pages "
    "anchor the integrative arc with longitudinal evidence and note the "
    "remaining open questions for future empirical work in this domain."
)

_CANNED_DEDICATED_THOROUGH = (
    "<thorough_summary>\n"
    "The dedicated call rebuilt the thorough summary from the final bullet "
    "set: the chapter's core claim is that structure formation proceeds in "
    "layers, each consolidating before the next emerges, with longitudinal "
    "evidence documented across the later sections of the chapter.\n"
    "</thorough_summary>"
)

# Drive source content: plain declarative sentences crafted to extract ZERO
# "key claims" (no digits, no causal/definition/comparison language, no
# Capitalized word pairs — content_judge_impl._CLAIM_PATTERNS) so the real
# ContentJudge auto-passes coverage (total_source_claims == 0), and long
# enough to clear the >=80-token empty-input gate under the stubbed
# count_tokens (= word count). The bullets below quote these sentences
# VERBATIM so the F4/grounding appeal keeps them (overlap = 1.0).
_CONTENT_SENTENCES = [
    "The passage describes layered structure formation in plain terms and reviews each stage of the process in careful order.",
    "Each layer settles into place and holds steady before the next layer begins to take shape above it.",
    "The account treats early baselines as starting points for the wider integrative picture developed later on.",
    "Careful reading shows that the timing of each stage matters more than the label attached to that stage.",
    "The closing pages collect the evidence into a single plain narrative for future reference by other readers.",
    "Readers are invited to weigh the material against their own observations of the same process in practice.",
    "The presentation favors plain description over technical vocabulary so that the stages stay easy to follow.",
    "Later sections return to the opening theme and connect it back to the evidence gathered in the middle pages.",
]
_CONTENT = " ".join(_CONTENT_SENTENCES)
# 20+ verbatim bullets (the <10000-token + >=20-bullets expansion-skip gate).
_BULLETS = [sent for sent in _CONTENT_SENTENCES for _ in (0, 1, 2)][:24]
_EXEC = _CONTENT_SENTENCES[0]


def _drive_summarizer(tmp_path, primary_thorough: str, calls: list) -> Summarizer:
    """Bare Summarizer + stubbed LLM seams, enough to drive _summarize_inner
    from the empty-input gate to the postchecks re-derivation block.

    All optional/LLM-heavy stages are gated OFF exactly like a minimal real
    conversion would: single-pass primary call (B4/B3/heavy skipped), no
    additive followup (sections pre-populated), no expansion (>=30 bullets),
    no self-consistency / academic rigor / scholar text, is_local=False
    (VRAM recovery no-op, deadline checks inert).
    """
    s = object.__new__(Summarizer)
    s.log = _capturing_log(calls)
    s.request = types.SimpleNamespace(
        output_dir=Path(tmp_path),
        input_path=Path("book.pdf"),
        summarisation_max_context_tokens=32768,
        summarisation_max_output_tokens=4096,
        source_type="normal_book",
    )
    s.language = "en"
    s.provider = "ollama"
    s.primary_model = "test-model"
    s.temperature = 0.2
    # V0.6.14 (single-model order): s.heavy_model stub REMOVED — the
    # Summarizer attribute is retired (one model does every LLM task).
    s.b3_voting_enabled = False
    s.self_consistency = False
    s.academic_rigor = False
    s.coverage_threshold = 0.0
    s._effective_target = 0.0
    s.overdeliver_enabled = False
    s.overdeliver_target = 1.0
    s.max_bullets_per_chapter = 99999
    s.conservative_drops = False
    s.quarantine = QuarantineLog(output_dir=None, log_callback=lambda msg, level="DEBUG": None)
    s._last_quarantined = []
    s._coverage_cache = {}
    s._verify_windows_cache = {}
    s._synthetic_thorough_fallback_count = 0
    s.is_local = False
    s.local_chapter_deadline = 0
    s._chapter_deadline_start = None
    s.MAP_REDUCE_THRESHOLD = 40000
    s.MAP_CHUNK_TOKENS = 4000
    s.MAP_CHUNK_OVERLAP = 0.10
    s.MAP_MINI_WORDS = 300
    s.fusion_enabled = False
    s.fusion_use_for_b3_judge = False
    s.fusion_use_for_grounding = False
    s.judge_results = []
    s._claim_extractor = None

    # ── LLM-shaped seams (instance-level stubs; the drive is deterministic) ──
    s._prepare_text = lambda text: text

    _primary_result = {
        "executive_summary": _EXEC,
        "bullet_points": list(_BULLETS),
        "thorough_summary": primary_thorough,
        "key_distinctions": "Baseline formulation vs integrative account.",
        "theoretical_tensions": "Layered timing vs simultaneous emergence.",
        "model": "test-model",
    }
    s._summarize_with_model = (
        lambda heading, text, model, temperature=None, with_cot=True, concepts=None, callouts=None: (
            dict(_primary_result)
        )
    )
    s._call_dedicated_thorough_with_fallback = (
        lambda prompt, exec_sum="", bullets=None, min_words=800: _CANNED_DEDICATED_THOROUGH
    )
    s._call_llm_with_empty_retry = lambda prompt, **kw: ""
    s._call_llm = lambda prompt, **kw: ""
    s._llm_grounding_check = lambda bullets, source_text: []
    # Minimal prompt_manager stub (the judge/reprompt stages only render
    # templates; with zero extracted claims the gap-fill stages never fire).
    s.prompt_manager = types.SimpleNamespace(
        render_template=lambda *a, **k: "", load_prompt=lambda name: True
    )
    s._recover_vram = lambda *a, **k: None
    return s


class TestBuriedLogsRaised:
    """W-a12: the four DEBUG-buried failures must now WARN."""

    def test_cot_gate_crash_now_warns(self, monkeypatch, tmp_path):
        """Site 1 (summarizer.py parse-time CoT gate): when
        detect_cot_narrative itself crashes, the chapter continues (the gate
        is non-fatal) but the crash is now VISIBLE at WARNING — pre-.4.11
        only a logger.debug trace existed and vanished."""
        import core.summarisation.postchecks as _pc_mod

        calls: list = []
        s = _drive_summarizer(tmp_path, _PLAIN_THOROUGH, calls)

        def _boom(text, field_label):
            raise RuntimeError("detector exploded")

        monkeypatch.setattr(_pc_mod, "detect_cot_narrative", _boom)
        result = s._summarize_inner("Chapter One", _CONTENT)
        # Non-fatal: the chapter still completes.
        assert result.success is True
        warned = [m for m in _warnings(calls) if "parse-time CoT gate crashed" in m]
        assert warned, f"no WARNING for the CoT-gate crash — logs: {calls}"
        assert any("V18.20.4.11" in m for m in warned)
        assert any("RuntimeError" in m and "detector exploded" in m for m in warned)

    def test_thorough_judge_rerun_crash_now_warns(self, monkeypatch, tmp_path):
        """Site 2 (summarizer.py thorough-judge re-run): the re-run fires
        when the primary thorough was CoT-nuked at parse time (the flag is
        set ORGANICALLY by the real detect_cot_narrative on a CoT-shaped
        primary thorough). A crashing analysis lookup must now WARN."""
        import core.preprocessing.deterministic_analyzer as _da_mod

        calls: list = []
        s = _drive_summarizer(tmp_path, _COT_THOROUGH, calls)

        def _boom(output_dir, heading, log_fn=None):
            raise RuntimeError("analysis lookup exploded")

        monkeypatch.setattr(_da_mod, "find_analysis_for_heading", _boom)
        result = s._summarize_inner("Chapter One", _CONTENT)
        assert result.success is True
        # The organic path proves the flag survived the whole pipeline:
        assert s._primary_thorough_cot_nuked is True
        warned = [m for m in _warnings(calls) if "thorough-judge re-run failed" in m]
        assert warned, f"no WARNING for the re-run crash — logs: {calls}"
        assert any("V18.20.4.11" in m for m in warned)
        assert any("RuntimeError" in m and "analysis lookup exploded" in m for m in warned)

    def test_checkpoint_save_failure_now_warns(self, monkeypatch, tmp_path):
        """Site 3 (_save_checkpoint): a failed checkpoint write (breaks
        crash-resume) must WARN, not DEBUG. Message text unchanged."""
        import utils.atomic_io as _ai_mod

        calls: list = []
        s = object.__new__(Summarizer)
        s.log = _capturing_log(calls)
        s.request = types.SimpleNamespace(output_dir=Path(tmp_path))

        def _boom(path, text, encoding="utf-8"):
            raise OSError("disk full")

        monkeypatch.setattr(_ai_mod, "atomic_write_text", _boom)
        s._save_checkpoint("Chapter One", {"executive_summary": "x"}, label="primary")
        ckpt_warns = [m for m in _warnings(calls) if "checkpoint save failed" in m]
        assert ckpt_warns, f"no WARNING for the checkpoint failure — logs: {calls}"
        # Message text is otherwise identical to the pre-fix DEBUG message:
        assert any(
            "V18.20.1.2: primary checkpoint save failed (non-fatal): disk full" in m
            for m in ckpt_warns
        )

    def test_quality_report_failure_now_warns_source_pin(self):
        """Site 4 (converter_impl.py quality report): the enclosing path is
        Converter.convert() (871 lines, Qt-conversion machinery — not
        headless-drivable); per the house source-pin precedent
        (test_deadline_watchdog.py:149-157) we pin the handler: the except
        after _generate_quality_report must log at WARNING and no longer at
        DEBUG."""
        src = (_project_root / "core" / "pipeline" / "converter_impl.py").read_text(
            encoding="utf-8"
        )
        anchor = src.find("self._generate_quality_report(segments, summaries)")
        assert anchor > 0, "quality-report call site must exist"
        window = src[anchor : anchor + 900]
        assert 'self._log(f"  ⚠️ Quality report generation failed: {e}", "WARNING")' in window
        assert 'self._log(f"  ⚠️ Quality report generation failed: {e}", "DEBUG")' not in window

    def test_cot_gate_and_rerun_handlers_keep_debug_trace(self):
        """The logger.debug traces are KEPT (only the visible WARNING was
        added) — pinned so a future cleanup doesn't drop the debug detail."""
        # V0.13: format-wrapped logger.debug( calls — pin message + logger call
        # V0.18 (Phase 5.1, steps 2-4): the CoT-gate and thorough-judge
        # re-run handlers moved VERBATIM to chapter_phases.py — the pins
        # follow the moved bodies.
        _phases_src = (_project_root / "core" / "summarisation" / "chapter_phases.py").read_text(
            encoding="utf-8"
        )
        assert "logger.debug(" in _SUMMARIZER_SRC
        assert '"parse-time CoT gate crashed (non-fatal): %s: %s"' in _phases_src
        assert '"thorough-judge re-run failed (non-fatal): %s: %s"' in _phases_src


# ════════════════════════════════════════════════════════════════════════════
# FIX C — model-literal single source of truth (W-a7 partial)
# ════════════════════════════════════════════════════════════════════════════


class TestModelLiterals:
    """The legacy default-model literals live in core.llm.model_taxonomy."""

    def test_constant_values_unchanged(self):
        assert LEGACY_DEFAULT_MODEL == "gemma3:12b"
        assert DEFAULT_FALLBACK_OCR_MODEL == "qwen3-vl:8b"

    def test_models_defaults_use_constants(self):
        from core.models import ConversionRequest

        r = ConversionRequest(input_path=Path("x.pdf"), output_dir=Path("y"))
        assert r.summarisation_model == LEGACY_DEFAULT_MODEL
        assert r.primary_ocr_model == DEFAULT_FALLBACK_OCR_MODEL
        assert r.fallback_ocr_model == DEFAULT_FALLBACK_OCR_MODEL
        # V0.6.14 (single-model order): the fast_model field + its
        # "shadows the LEGACY_DEFAULT_MODEL-wired field" quirk pin REMOVED
        # — the ConversionRequest field is retired (one model does every
        # LLM task). The test below this one (test_fast_llm_sentinel_
        # routes_to_primary — 1 test) was DELETED for the same reason: it
        # imported the DELETED core.summarisation.fast_llm router to pin
        # the fast/heavy sentinel routing, a retired contract.

    @staticmethod
    def _docstring_nodes(tree: ast.AST) -> set:
        """ids of ast string-constant nodes that are docstrings."""
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    docs.add(id(body[0].value))
        return docs

    def test_no_bare_gemma_literal_outside_taxonomy(self):
        """Source scan: none of the previously-duplicated files may carry a
        bare CODE string literal containing 'gemma3:12b' (docstrings and
        comments are allowed — summarizer.py's _init_quality_params
        docstring mentions it historically).

        V0.6.14 (single-model order): core/summarisation/fast_llm.py
        REMOVED from the scan list — the module is DELETED (the 4-mode
        fast/heavy router is retired)."""
        files = [
            "core/models/models.py",
            "core/summarisation/summarizer.py",
            "core/tts/normalizer.py",
            "core/pipeline/conversion/postprocess.py",
        ]
        for rel in files:
            tree = ast.parse((_project_root / rel).read_text(encoding="utf-8"))
            docs = self._docstring_nodes(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and "gemma3:12b" in node.value
                    and id(node) not in docs
                ):
                    pytest.fail(f"{rel}:{node.lineno} carries a bare gemma3:12b CODE literal")

    def test_no_bare_qwen_vl_literal_in_wired_files(self):
        """Same scan for the qwen3-vl:8b literal in the two wired files."""
        files = ["core/models/models.py", "core/pipeline/conversion/postprocess.py"]
        for rel in files:
            tree = ast.parse((_project_root / rel).read_text(encoding="utf-8"))
            docs = self._docstring_nodes(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and "qwen3-vl:8b" in node.value
                    and id(node) not in docs
                ):
                    pytest.fail(f"{rel}:{node.lineno} carries a bare qwen3-vl:8b CODE literal")

    def test_normalizer_known_bad_default_uses_constant_source_pin(self):
        """normalizer.py's known-bad-default tuple wires the constant (the
        'qwen2.5:3b' companion literal is out of scope and stays)."""
        src = (_project_root / "core" / "tts" / "normalizer.py").read_text(encoding="utf-8")
        assert 'model in ("qwen2.5:3b", LEGACY_DEFAULT_MODEL, "")' in src

    def test_taxonomy_exports_constants(self):
        import core.llm.model_taxonomy as mt

        assert "LEGACY_DEFAULT_MODEL" in mt.__all__
        assert "DEFAULT_FALLBACK_OCR_MODEL" in mt.__all__


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
