"""Phase 2 (P2-C1): shared hermetic harness for the summarizer.py test-net.

This module contains NO tests — it is the machinery imported by the
``tests/test_p2_summarizer_*.py`` files. It adapts the PROVEN hermetic
recipe (``scripts/bench_chapter.py`` — validated by the Phase-1 golden
freeze, ``tests/test_golden_freeze.py``) for pytest use:

* ``P2Settings``         — deterministic offline Settings stand-in driven
                           through the REAL ``Settings._test_override`` DI
                           hook (every ``Settings()`` call anywhere in the
                           pipeline resolves to it; no ~/.elixir/settings.json
                           is ever read).
* ``install_hermetic_singletons`` — force the embedder/spacy singletons to
                           their absent-machine fallback (None → Jaccard /
                           no-NER), so no network/model probes fire.
* ``ScriptedLLM``        — replaces ``summarizer._call_llm`` with a
                           deterministic, per-prompt-shape responder. Every
                           LLM call in the pipeline funnels through
                           ``_call_llm`` (the structured/JSON path is
                           disabled in production — V18.20.2.0 A16 — so the
                           XML path via ``_call_llm`` is the real path).
* ``make_summarizer``    — construct a REAL Summarizer (real ``__init__``,
                           real sub-constructors) under hermetic settings,
                           with a tmp output dir.
* ``hermetic_env``       — autouse-fixture factory: snapshot/restore
                           ``Settings._test_override``, the model singletons
                           and the impl-module warning flags (the
                           test_group_b_characterization.py /
                           test_golden_freeze.py discipline).

No network, no GPU, no model files — safe to run anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Load the bench harness (scripts/ is not a package) ──────────────────────
# Same technique as tests/test_golden_freeze.py — gives us the proven
# deterministic grounded canned-response builders.
_spec = importlib.util.spec_from_file_location(
    "bench_chapter", _project_root / "scripts" / "bench_chapter.py"
)
bench = importlib.util.module_from_spec(_spec)
sys.modules["bench_chapter"] = bench
_spec.loader.exec_module(bench)

build_primary_response = bench.build_primary_response
build_aux_response = bench.build_aux_response

# Prompt-shape markers (verified against core/summarisation/prompt_assembly.py
# and the prompt bank under prompts/) used by the default responder to route a
# scripted reply to the right pipeline phase.
MARKER_DEDICATED_THOROUGH = "write ONE comprehensive thorough summary"
MARKER_EXEC_FROM_THOROUGH = "write ONE executive summary"
MARKER_BULLET_EXPANSION = "produce a comprehensive list of bullet points"
MARKER_PRIMARY_INLINE = "You are an expert book summariser"
MARKER_TIER2_GAPFILL = 'Write ONE bullet point (prefixed with "- ")'
# V0.5.16: the content-judge gap-fill reprompt (prompts/summarisation/
# gap_fill_reprompt.md). The marker check MUST precede the length-based
# primary classification — the reprompt embeds the existing bullets and
# is usually > 6000 chars, so without it the scripted gap reply never
# fires (the canned XML comes back instead and its <bullet_points> lines
# get parsed as gap-fill additions).
MARKER_JUDGE_GAPFILL = "Add 3-7 NEW bullets that cover the missed concepts below."


# ═══════════════════════════════════════════════════════════════════════════
# Hermetic Settings stand-in (drives the real Settings._test_override hook)
# ═══════════════════════════════════════════════════════════════════════════


class P2Settings:
    """Deterministic offline Settings (mirrors bench_chapter.BenchSettings)."""

    def __init__(self, values: dict[str, Any] | None = None):
        self._values = {
            "summarisation.provider": "ollama",
            "summarisation.b4_threshold_tokens": 12000,
            "summarisation.cross_chapter_context": True,
            "local.http_timeout_sec": 600,
            "local.chapter_deadline_sec": 600,
            "local.vram_recovery_delay_sec": 0,  # no GPU sleeps under test
            "local.map_phase_max_seconds": 0,  # no map-phase budget under test
            "embedding.enabled": False,
            "model_temperatures": {},
        }
        if values:
            self._values.update(values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def get_ollama_url(self) -> str:
        return "http://localhost:11434"


# ═══════════════════════════════════════════════════════════════════════════
# Singleton snapshot / restore
# ═══════════════════════════════════════════════════════════════════════════


def install_hermetic_singletons() -> list[tuple[Any, str, Any]]:
    """Force the embedder/spacy singletons to their absent-machine path.

    Verbatim from scripts/bench_chapter.py (proven in the freeze tests):
    ``get_embed_model`` and ``get_spacy_nlp`` re-probe on every call after
    a failure, so without this patch each chapter fires ~8 network/import
    probes whose wall time is environment-dependent.
    """
    import core.llm.model_singletons as ms

    undo = []
    for name in ("get_embed_model", "get_spacy_nlp"):
        orig = getattr(ms, name, None)
        if orig is not None:
            setattr(ms, name, lambda *a, **k: None)
            undo.append((ms, name, orig))
    return undo


def _impl_flag_snapshot() -> dict[str, Any]:
    """Snapshot the module-level singletons a real Summarizer run touches.

    Union of the test_group_b_characterization.py and test_golden_freeze.py
    autouse fixtures (order-dependent-failure prevention, V18.19.1.4 debt D3).
    """
    snap: dict[str, Any] = {}
    try:
        import core.summarisation.content_judge_impl as cji

        snap["cji.embedding_disabled"] = getattr(cji, "_warned_embedding_disabled", None)
        snap["cji.semantic_fallback"] = getattr(cji, "_warned_semantic_fallback", None)
        snap["cji.st_model"] = getattr(cji, "_st_model", None)
    except Exception:
        pass
    try:
        import core.summarisation.text_preprocessor_impl as tpi

        snap["tpi.warned_no_embed_model"] = getattr(tpi, "_warned_no_embed_model", None)
        snap["tpi.spacy_nlp"] = getattr(tpi, "_SPACY_NLP", None)
    except Exception:
        pass
    try:
        import core.llm.llm_provider_impl as lpi

        snap["lpi.keep_alive_cache"] = getattr(lpi, "_keep_alive_cache", None)
    except Exception:
        pass
    return snap


def _impl_flag_restore(snap: dict[str, Any]) -> None:
    try:
        import core.summarisation.content_judge_impl as cji

        cji._warned_embedding_disabled = snap.get("cji.embedding_disabled")
        cji._warned_semantic_fallback = snap.get("cji.semantic_fallback")
        cji._st_model = snap.get("cji.st_model")
    except Exception:
        pass
    try:
        import core.summarisation.text_preprocessor_impl as tpi

        tpi._warned_no_embed_model = snap.get("tpi.warned_no_embed_model")
        if hasattr(tpi, "_SPACY_NLP"):
            tpi._SPACY_NLP = snap.get("tpi.spacy_nlp")
    except Exception:
        pass
    try:
        import core.llm.llm_provider_impl as lpi

        lpi._keep_alive_cache = snap.get("lpi.keep_alive_cache")
    except Exception:
        pass


def hermetic_env():
    """Autouse fixture factory: full hermetic environment snapshot/restore.

    Usage in a test module::

        @pytest.fixture(autouse=True)
        def _hermetic():
            with hermetic_env():
                yield
    """

    class _Ctx:
        def __enter__(self):
            from utils.settings import Settings

            self._prev_override = Settings._test_override
            self._undo = install_hermetic_singletons()
            self._flags = _impl_flag_snapshot()
            return self

        def __exit__(self, *exc):
            from utils.settings import Settings

            Settings._test_override = self._prev_override
            for obj, name, orig in self._undo:
                setattr(obj, name, orig)
            _impl_flag_restore(self._flags)
            return False

    return _Ctx()


def set_settings(values: dict[str, Any] | None = None) -> None:
    """Install a P2Settings as the global Settings() for the current test."""
    from utils.settings import Settings

    Settings._test_override = P2Settings(values)  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════
# Scripted mock LLM (every call funnels through Summarizer._call_llm)
# ═══════════════════════════════════════════════════════════════════════════


class ScriptedLLM:
    """Deterministic stand-in for ``Summarizer._call_llm``.

    Routing (``responder`` takes precedence; the default mirrors the bench's
    latency-bucket classifier with zero sleep):

    * primary / chunked / map-reduce shapes (long prompt or ``max_tokens is
      None``) → ``primary_response`` (a grounded canned XML by default);
    * dedicated-thorough / exec-from-thorough / bullet-expansion prompts →
      the matching ``dedicated_thorough`` / ``exec_from_thorough`` /
      ``bullet_expansion`` scripted replies (each defaults to a grounded
      shape derived from ``primary_response``);
    * every other aux prompt (self-review, judges, consolidation, preflight,
      Tier-2 gap fill) → ``build_aux_response``-style grounded text.

    All calls are recorded (prompt, model, temperature, max_tokens).
    """

    def __init__(
        self,
        primary_response: str | None = None,
        responder: Callable[..., str | None] | None = None,
        dedicated_thorough: str | None = None,
        exec_from_thorough: str | None = None,
        bullet_expansion: str | None = None,
        aux_response: str | None = None,
        judge_gapfill: str | None = None,
    ):
        self.primary_response = primary_response
        self.dedicated_thorough = dedicated_thorough
        self.exec_from_thorough = exec_from_thorough
        self.bullet_expansion = bullet_expansion
        self.aux_response = aux_response
        self.judge_gapfill = judge_gapfill
        self.responder = responder
        self.calls: list[tuple[str, str | None, float | None, int | None]] = []

    # -- shape classification -------------------------------------------------
    def classify(self, prompt: str, max_tokens: int | None) -> str:
        if MARKER_DEDICATED_THOROUGH in prompt:
            return "dedicated_thorough"
        if MARKER_EXEC_FROM_THOROUGH in prompt:
            return "exec_from_thorough"
        if MARKER_BULLET_EXPANSION in prompt:
            return "bullet_expansion"
        # V0.5.16: BEFORE the length check (see the marker note above).
        if MARKER_JUDGE_GAPFILL in prompt:
            return "judge_gapfill"
        if len(prompt) > 6000 or max_tokens is None:
            return "primary"
        return "aux"

    def _aux_default(self, prompt: str) -> str:
        if self.aux_response is not None:
            return self.aux_response
        return build_aux_response(prompt, self.primary_response or "The chapter is covered.")

    def __call__(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        self.calls.append((prompt, model, temperature, max_tokens))
        if self.responder is not None:
            return self.responder(prompt, model, temperature, max_tokens)
        shape = self.classify(prompt, max_tokens)
        if shape == "judge_gapfill":
            # V0.5.16: the judge gap-fill reprompt. Default: no bullet
            # lines ("no additions") — the parsed gap list is empty. Pass
            # judge_gapfill="- <grounded line>" to script additions.
            if self.judge_gapfill is not None:
                return self.judge_gapfill
            return (
                "No additions are required. The existing bullets cover "
                "all the identified claims."
            )
        if shape == "dedicated_thorough":
            if self.dedicated_thorough is not None:
                return self.dedicated_thorough
            return self.primary_response  # grounded canned XML carries <thorough_summary>
        if shape == "exec_from_thorough":
            if self.exec_from_thorough is not None:
                return self.exec_from_thorough
            return self.primary_response
        if shape == "bullet_expansion":
            if self.bullet_expansion is not None:
                return self.bullet_expansion
            return self.primary_response
        if shape == "primary":
            return self.primary_response
        return self._aux_default(prompt)

    def calls_of_shape(self, shape: str) -> list[tuple[str, str | None, float | None, int | None]]:
        return [c for c in self.calls if self.classify(c[0], c[3]) == shape]

    def install(self, summarizer: Any) -> ScriptedLLM:
        summarizer._call_llm = self  # type: ignore[method-assign]
        return self


# ═══════════════════════════════════════════════════════════════════════════
# Real-Summarizer factory (hermetic)
# ═══════════════════════════════════════════════════════════════════════════


def make_summarizer(
    output_dir: Path,
    settings_values: dict[str, Any] | None = None,
    request_fields: dict[str, Any] | None = None,
    model: str = "gemma3:12b",
    log_lines: list[tuple[str, str]] | None = None,
):
    """Construct a REAL Summarizer under hermetic settings (no network/GPU).

    Mirrors ``bench_chapter.build_summarizer`` but with configurable
    settings/request fields. ``log_lines`` (if given) collects every log
    callback as (message, level) for assertions.
    """
    from core.models import ConversionRequest
    from core.summarisation.summarizer import Summarizer

    set_settings(settings_values)

    if log_lines is None:
        log_lines = []

    def _log(msg: str, level: str = "INFO") -> None:
        log_lines.append((level, msg))

    req = ConversionRequest(input_path=_project_root / "VERSION", output_dir=output_dir)
    req.generate_summaries = True
    req.summarisation_model = model
    for k, v in (request_fields or {}).items():
        setattr(req, k, v)

    s = Summarizer(request=req, log_callback=_log, language="en", claim_extractor=None)
    s.max_workers = 1
    return s


# ═══════════════════════════════════════════════════════════════════════════
# Fixture content builders
# ═══════════════════════════════════════════════════════════════════════════


def golden_chapter(name: str = "nonfiction") -> tuple[str, str]:
    """(heading, content) of a golden fixture chapter."""
    return bench.load_golden_chapter(name)


def analysis_file_text(authors: list[str]) -> str:
    """A deterministic-analysis file whose Citations section lists ``authors``.

    Parsed by ``extract_authors_from_analysis`` (``N. **Author** (...)`` lines)
    and by ``check_coverage`` (which judges summary text against those names).
    """
    lines = ["# Deterministic Analysis", "", "## Citations", ""]
    for i, a in enumerate(authors, 1):
        lines.append(f"{i}. **{a}** (3 mentions): 2001, 2004")
    lines += ["", "## Structure", "", "The chapter is well structured."]
    return "\n".join(lines) + "\n"


def write_analysis_tree(
    output_dir: Path, authors: list[str], segment_md: str | None = None
) -> Path:
    """Write ONE ``*_analysis.md`` (+ optional segment twin) under output_dir.

    A single analysis file is returned by ``find_analysis_for_heading``
    regardless of heading (legacy single-segment behavior).
    """
    seg_dir = output_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = seg_dir / "001_chapter_analysis.md"
    analysis_path.write_text(analysis_file_text(authors), encoding="utf-8")
    if segment_md is not None:
        (seg_dir / "001_chapter.md").write_text(segment_md, encoding="utf-8")
    return analysis_path


# ═══════════════════════════════════════════════════════════════════════════
# Misc helpers
# ═══════════════════════════════════════════════════════════════════════════


def armed_deadline(summarizer: Any, elapsed: float = 10_000.0) -> None:
    """Point the per-chapter deadline clock far in the past (deadline armed)."""
    summarizer._chapter_deadline_start = time.time() - elapsed


def fresh_deadline(summarizer: Any) -> None:
    """Point the per-chapter deadline clock at now (deadline not exceeded)."""
    summarizer._chapter_deadline_start = time.time()


def a_chapter(paragraphs: int = 40, seed_word: str = "chapter") -> str:
    """A deterministic multi-paragraph chapter (well above the 80-token gate).

    Each paragraph is unique so keyword extraction and coverage have signal.
    """
    out = []
    for i in range(paragraphs):
        out.append(
            f"Paragraph {i} of the {seed_word}: the observation team recorded "
            f"finding {i} about baseline patterns and casing techniques. "
            f"The analysts concluded that phase {i} required patience."
        )
    return "\n\n".join(out)


def cot_exec_text() -> str:
    """An executive summary that IS chain-of-thought (>= 3 CoT markers)."""
    return (
        "Let me organize my understanding of this chapter carefully. "
        "Let me count carefully the named contributors in the source. "
        "Let me draft each section now before writing the final answer."
    )


def assert_logged(log_lines: list[tuple[str, str]], fragment: str) -> None:
    """Assert some collected log line contains ``fragment``."""
    assert any(fragment in msg for (_lvl, msg) in log_lines), (
        f"expected a log line containing {fragment!r}; got {[m for (_l, m) in log_lines][-30:]}"
    )
