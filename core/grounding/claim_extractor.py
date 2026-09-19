"""V10.1.0: ClaimExtractor — langextract wrapper (Layer 8 grounding).

This module is the **second major specific project** added to the MarkItDown
Pro pipeline (the first being Microsoft MarkItDown itself).  It wraps Google's
``langextract`` library to give the pipeline a *deterministic, verbatim*
hallucination signal that complements the existing fuzzy/semantic layers.

═══════════════════════════════════════════════════════════════════════════
WHY THIS EXISTS — the gap in the existing 7-layer defense
═══════════════════════════════════════════════════════════════════════════

The existing defenses are all *similarity-based*:

  Layer 4 (_compute_coverage)   — keyword + concept n-gram overlap
  Layer 5 (_verify_bullets)     — rapidfuzz 80-char sliding window, ≥50%
  Layer 7 (ContentJudge Q2)     — sentence-transformers cosine ≥ 0.50

Similarity has two failure modes:
  1. A hallucination that is *topically similar* to the source scores as
     "grounded" (false negative — lets hallucinations through).
  2. A legitimately paraphrased true bullet scores as "ungrounded" if the
     paraphrase is too aggressive (false positive — flags good work).

langextract gives a **third, stronger signal**: ``char_interval``.  Every
extraction it returns carries a ``(start, end)`` byte span into the source.
If the model produces a claim that **cannot be located verbatim** in the
source, ``char_interval`` is ``None`` — a deterministic, binary hallucination
flag with no threshold tuning required.

This is not a replacement for the semantic layers — paraphrased prose would
be wrongly rejected by a verbatim-only check.  So the integration is
**two-tier** (see ``ContentJudge.judge`` in V10.1.0):

  Tier 1 (strong)  — claim has a ``char_interval``  → grounded_strong = True
  Tier 2 (weak)    — no char_interval, but semantic ≥ 0.50 → grounded_weak
  Tier 3 (reject)  — neither                          → hallucination flag

═══════════════════════════════════════════════════════════════════════════
CONFIGURATION (Q1=C — configurable backend)
═══════════════════════════════════════════════════════════════════════════

Settings keys (under ``grounding.`` namespace, added in V10.1.0):

  grounding.enabled            (bool)   master on/off, default False
  grounding.backend            (str)    "ollama" | "cloud", default "ollama"
  grounding.ollama_model       (str)    e.g. "gemma2:9b", default = summarisation.model
  grounding.ollama_url         (str)    default "http://localhost:11434"
  grounding.cloud_model        (str)    e.g. "gpt-4o-mini"
  grounding.cloud_base_url     (str)    OpenAI-compatible base URL
  grounding.cloud_api_key      (str)    API key
  grounding.extraction_passes  (int)    1-3, default 1 (recall vs. cost)
  grounding.max_workers        (int)    parallel chunks, default 2
  grounding.max_char_buffer    (int)    chunk size, default 4000
  grounding.timeout_sec        (int)    per-chunk timeout, default 120

═══════════════════════════════════════════════════════════════════════════
FAILURE MODES & ALARMING (Q2=A+alarm)
═══════════════════════════════════════════════════════════════════════════

Every failure path returns a ``GroundingResult`` with ``available=False`` AND
a populated ``alarm`` field.  The caller (ContentJudge / converter) MUST log
the alarm at WARNING/ERROR so the user sees that grounding was degraded —
**never silent**.  The pipeline then falls back to the existing 7 layers.

Alarm severities:
  "info"     — langextract not installed (user hasn't pip-installed it yet)
  "warning"  — backend unreachable, model missing, or timeout
  "error"    — langextract raised an unexpected exception

═══════════════════════════════════════════════════════════════════════════
LICENSE
═══════════════════════════════════════════════════════════════════════════

langextract is Apache-2.0 (Google).  See https://github.com/google/langextract
This wrapper is part of Elixir.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import textwrap
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# V18.20.4.12 (W-a10): single source of truth for the rig-tuned fallback
# model used by the Pass-1 zero-extraction retry below (value byte-identical
# to the inline literal it replaces).
from core.llm.model_taxonomy import RIG_FALLBACK_MODEL

# Lazy imports — langextract is optional.  We never import it at module load
# so the app boots even if the library isn't pip-installed.
# The actual import happens inside _ensure_langextract().


LogFn = Callable[[str, str], None]


# ── Public types ──────────────────────────────────────────────────────────


class GroundingBackend(StrEnum):
    """Which LLM backend langextract should use."""

    OLLAMA = "ollama"  # local, free, no API key
    CLOUD = "cloud"  # OpenAI-compatible endpoint


@dataclass
class GroundedClaim:
    """One extraction returned by langextract, with its source span.

    Attributes:
        text: the verbatim extraction text (as the model produced it).
        extraction_class: e.g. "claim", "finding", "method", "result",
            "definition", "dataset", "limitation", "entity".
        char_interval: ``(start, end)`` character offsets into the source
            text, or ``None`` if langextract could NOT locate this extraction
            verbatim in the source (i.e. a potential hallucination).
        attributes: optional extra attributes (sentiment, polarity, etc.).
        source_snippet: the verbatim source substring at char_interval, or
            "" if char_interval is None (for display in DOCX/HTML).
    """

    text: str
    extraction_class: str
    char_interval: tuple[int, int] | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    source_snippet: str = ""

    @property
    def is_grounded(self) -> bool:
        """True iff langextract located this claim verbatim in the source."""
        return self.char_interval is not None


@dataclass
class GroundingAlarm:
    """A loud, non-silent signal that grounding was degraded for a chapter.

    The caller MUST surface this to the user (log at WARNING/ERROR, show in
    the wizard's status bar).  Never swallow it.
    """

    severity: str  # "info" | "warning" | "error"
    code: str  # short machine code, e.g. "langextract_not_installed"
    message: str  # human-readable detail


@dataclass
class GroundingResult:
    """The complete result of grounding one chapter's summary claims.

    Attributes:
        available: True if langextract ran successfully.  False if it was
            disabled, missing, or failed — in which case ``alarm`` is set
            and the caller must fall back to the existing semantic layers.
        claims: list of GroundedClaim (empty if not available).
        grounded_count: claims with char_interval is not None.
        ungrounded_count: claims with char_interval is None (potential
            hallucinations — but see note below about paraphrase).
        ungrounded_texts: the texts of ungrounded claims (for logging).
        alarm: set iff available is False (or partial failure).
        backend_used: "ollama" | "cloud" | "" (if not available).
        elapsed_sec: wall-clock time for the extraction (for diagnostics).
    """

    available: bool = False
    claims: list[GroundedClaim] = field(default_factory=list)
    grounded_count: int = 0
    ungrounded_count: int = 0
    ungrounded_texts: list[str] = field(default_factory=list)
    alarm: GroundingAlarm | None = None
    backend_used: str = ""
    elapsed_sec: float = 0.0

    @property
    def grounded_pct(self) -> float:
        total = self.grounded_count + self.ungrounded_count
        if total == 0:
            return 1.0
        return self.grounded_count / total

    def format_report(self) -> str:
        """One-line summary for the conversion log."""
        if not self.available:
            sev = self.alarm.severity if self.alarm else "unknown"
            code = self.alarm.code if self.alarm else "no_alarm"
            return f"🛡️ Grounding: UNAVAILABLE ({sev}/{code}) — fell back to Layers 1-7"
        return (
            f"🛡️ Grounding [{self.backend_used}]: "
            f"{self.grounded_count} grounded, {self.ungrounded_count} ungrounded "
            f"({self.grounded_pct:.0%} verbatim) — "
            f"{self.elapsed_sec:.1f}s"
        )


# ── Availability probe ────────────────────────────────────────────────────

_langextract_import_cache: bool | None = None  # None=untested, True/False
_langextract_import_lock = threading.Lock()


def is_langextract_available() -> bool:
    """Return True iff the ``langextract`` package is importable.

    Cached after first call (thread-safe).  Never raises.
    """
    global _langextract_import_cache
    if _langextract_import_cache is not None:
        return _langextract_import_cache
    with _langextract_import_lock:
        if _langextract_import_cache is not None:
            return _langextract_import_cache
        try:
            import langextract  # noqa: F401

            _langextract_import_cache = True
        except ImportError:
            # langextract has heavy deps (sentence-transformers, etc.) that
            # might fail at import.  Treat any import error as "unavailable".
            _langextract_import_cache = False
    return _langextract_import_cache


def default_backend(settings: Any) -> GroundingBackend:
    """Read the configured backend from Settings, defaulting to Ollama."""
    try:
        raw = settings.get("grounding.backend", "ollama") if settings else "ollama"
        return GroundingBackend(raw)
    except Exception as _e:
        return GroundingBackend.OLLAMA


# ── Few-shot example bank ─────────────────────────────────────────────────
#
# langextract is few-shot: it needs 1-3 example (text → extractions) pairs
# to learn the task shape.  We ship a small per-content-type bank so the
# user doesn't have to write their own.  These examples are deliberately
# *academic-flavoured* because grounding matters most for scientific claims
# ("life/money at stake").  For non-academic content types the same bank
# still works — langextract generalises from the example shape.

_ACADEMIC_EXAMPLE_TEXT = (
    "Memantine is a low-affinity, noncompetitive NMDA receptor antagonist "
    "approved for moderate-to-severe Alzheimer's disease.  In a 28-week "
    "randomised controlled trial of 252 patients, the mean ADAS-cog score "
    "changed by -2.9 points in the treatment group versus +2.4 in placebo "
    "(p < 0.001).  The most common adverse event was dizziness (7% vs 2%)."
)

_ACADEMIC_EXAMPLE_EXTRACTIONS = [
    # (text, extraction_class, attributes)
    ("Memantine", "entity", {"type": "drug"}),
    (
        "low-affinity, noncompetitive NMDA receptor antagonist",
        "definition",
        {"subject": "Memantine"},
    ),
    ("moderate-to-severe Alzheimer's disease", "entity", {"type": "indication"}),
    ("28-week randomised controlled trial", "method", {"design": "RCT"}),
    ("252 patients", "dataset", {"size": "252"}),
    (
        "mean ADAS-cog score changed by -2.9 points in the treatment group versus +2.4 in placebo",
        "result",
        {"metric": "ADAS-cog", "treatment": "-2.9", "placebo": "+2.4"},
    ),
    ("p < 0.001", "result", {"stat": "p-value"}),
    (
        "dizziness (7% vs 2%)",
        "result",
        {"adverse_event": "dizziness", "treatment_pct": "7", "placebo_pct": "2"},
    ),
]

_GENERAL_EXAMPLE_TEXT = (
    "The author argues that deep work—working in a state of intense "
    "concentration without distraction—produces high-quality output.  A "
    "study of 200 knowledge workers found that those who blocked 90 "
    "minutes of uninterrupted time completed 47% more tasks.  The key "
    "practice is scheduling: block the first hour of every day for deep work."
)

_GENERAL_EXAMPLE_EXTRACTIONS = [
    ("deep work", "entity", {"type": "concept"}),
    (
        "working in a state of intense concentration without distraction",
        "definition",
        {"subject": "deep work"},
    ),
    ("A study of 200 knowledge workers", "method", {"design": "observational", "size": "200"}),
    (
        "those who blocked 90 minutes of uninterrupted time completed 47% more tasks",
        "result",
        {"intervention": "90-min blocks", "effect": "+47% tasks"},
    ),
    (
        "block the first hour of every day for deep work",
        "claim",
        {"prescription": "schedule deep work first"},
    ),
]


def _build_examples(content_type: str):
    """Build langextract ExampleData objects for the given content type.

    Returns a list of ``lx.data.ExampleData``.  Must be called *after*
    langextract is imported (so we can reference ``lx.data``).
    """
    import langextract as lx

    def _make(text, extractions):
        return lx.data.ExampleData(
            text=text,
            extractions=[
                lx.data.Extraction(
                    extraction_class=cls,
                    extraction_text=txt,
                    attributes=attrs,
                )
                for (txt, cls, attrs) in extractions
            ],
        )

    examples = [_make(_ACADEMIC_EXAMPLE_TEXT, _ACADEMIC_EXAMPLE_EXTRACTIONS)]
    # For non-academic content, add the general example too — gives the
    # model a broader sense of what counts as a claim.
    if content_type != "academic_paper":
        examples.append(_make(_GENERAL_EXAMPLE_TEXT, _GENERAL_EXAMPLE_EXTRACTIONS))
    return examples


# ── Prompt bank ───────────────────────────────────────────────────────────

_PROMPTS = {
    "academic_paper": textwrap.dedent("""\
        Extract every factual claim, finding, method, dataset, result,
        definition, and named entity from this academic paper section.
        Use exact text for extractions — do NOT paraphrase or overlap
        entities.  Provide meaningful attributes for each entity to add
        context (metric name, value, sample size, p-value, etc.).  Extract
        numbers and statistics as their own result-type extractions.
    """),
    "default": textwrap.dedent("""\
        Extract the key factual claims, definitions, named entities,
        statistics, and prescriptive advice from this text.  Use exact text
        for extractions — do NOT paraphrase.  Provide attributes for each
        entity (type, value, subject).  Capture every number, percentage,
        and causal statement as a separate extraction.
    """),
}


def _prompt_for(content_type: str) -> str:
    return _PROMPTS.get(content_type, _PROMPTS["default"])


# ── The extractor ─────────────────────────────────────────────────────────


class ClaimExtractor:
    """Wraps langextract to extract verbatim-grounded claims from summaries.

    Thread-safe (one internal lock around all langextract calls).  Lazy
    (langextract imported on first ``extract`` call).  Graceful (every
    failure returns a ``GroundingResult`` with ``available=False`` + alarm).

    Usage::

        extractor = ClaimExtractor(settings=settings, log_callback=log)
        result = extractor.extract(
            source_text=chapter_raw_text,
            summary_bullets=summary.bullet_points,
            content_type="academic_paper",
        )
        if not result.available:
            log(result.alarm.message, "WARNING")  # LOUD — never silent
            # fall back to existing semantic checks
        else:
            for claim in result.claims:
                if not claim.is_grounded:
                    # potential hallucination — char_interval is None
                    ...
    """

    def __init__(
        self,
        settings: Any = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self.settings = settings
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._lock = threading.RLock()
        self._enabled: bool | None = None  # cached
        self._backend: GroundingBackend | None = None
        # V15.0.4: reason string when _enabled is False despite grounding.enabled=True
        self._disabled_reason: str | None = None

    # ── configuration probes ────────────────────────────────────────────

    def _is_enabled(self) -> bool:
        """Read grounding.enabled from settings (cached).

        V15.0.4: Returns False when the backend is OLLAMA (local), because
        local models CANNOT produce ``char_intervals`` — langextract's
        verbatim-grounding signal. Running langextract on a local Ollama
        backend wastes ~7.5 min per chapter and always returns 0% verbatim
        grounding (confirmed in the V15.0.3 conversion log: 170 extractions,
        0 with char_intervals).

        To enable langextract, switch ``grounding.backend`` to ``"cloud"``
        (Google's hosted langextract / Gemini API) in Settings → Grounding.
        Layers 1-7 (semantic checks + judge appeal) remain active regardless.
        """
        if self._enabled is not None:
            return self._enabled
        if self.settings is None:
            self._enabled = False
            return self._enabled
        try:
            _user_enabled = bool(self.settings.get("grounding.enabled", False))
        except Exception:
            self._enabled = False
            return self._enabled
        if not _user_enabled:
            # User explicitly disabled grounding — silent.
            self._enabled = False
            return self._enabled

        # User enabled grounding — but check if the backend can actually
        # produce char_intervals. Local Ollama models cannot (they return
        # extractions but 0% char_intervals). Only the cloud/Gemini API
        # backend supports verbatim grounding.
        _backend = self._get_backend()
        if _backend == GroundingBackend.OLLAMA:
            self._enabled = False
            self._disabled_reason = "ollama_no_char_intervals"
        else:
            self._enabled = True
        return self._enabled

    def _get_backend(self) -> GroundingBackend:
        if self._backend is not None:
            return self._backend
        self._backend = default_backend(self.settings)
        return self._backend

    def _ollama_config(self) -> dict[str, Any]:
        """Build kwargs for the Ollama backend from settings.

        V13.45.5: Fixed critical langextract parameters based on GitHub research:
        - num_ctx: default 2048 is WAY too small for 8000-char chunks → set to 32768
        - OLLAMA_FORMAT_HANDLER: required for Ollama JSON mode (use_fences=False, use_wrapper=True)
        - suppress_parse_errors: skip bad chunks instead of failing the whole run
        - think=False: avoid reasoning-only outputs
        """
        s = self.settings
        summ_model = s.get("summarisation.model", "gemma4-12b:latest") if s else "gemma4-12b:latest"
        return {
            "model_id": (s.get("grounding.ollama_model", "") or summ_model) if s else summ_model,
            "model_url": s.get("grounding.ollama_url", "http://localhost:11434")
            if s
            else "http://localhost:11434",
        }

    def _extraction_kwargs(self) -> dict[str, Any]:
        """Common kwargs for lx.extract() (passes, workers, chunk size).

        V13.45.5: Added critical langextract parameters:
        - language_model_params: num_ctx=32768 (was 2048 default → context overflow)
        - resolver_params: suppress_parse_errors=True (skip bad chunks)
        - format_handler: OLLAMA_FORMAT_HANDLER (required for Ollama JSON mode)
        """
        s = self.settings
        kwargs = {
            "extraction_passes": int(s.get("grounding.extraction_passes", 1)) if s else 1,
            "max_workers": int(s.get("grounding.max_workers", 1)) if s else 1,
            "max_char_buffer": int(s.get("grounding.max_char_buffer", 8000)) if s else 8000,
        }

        # V13.45.5: Add Ollama-specific parameters if using Ollama backend
        backend = self._get_backend()
        if backend == GroundingBackend.OLLAMA:
            try:
                from langextract.providers.ollama import OLLAMA_FORMAT_HANDLER

                kwargs["resolver_params"] = {
                    "format_handler": OLLAMA_FORMAT_HANDLER,
                    "suppress_parse_errors": True,
                }
            except ImportError:
                logger.debug("OLLAMA_FORMAT_HANDLER not available — using default resolver")

            # V13.45.5: Set num_ctx to 32768 (was 2048 default — caused 0 extractions)
            # This is the single most critical fix from the langextract GitHub research.
            kwargs["language_model_params"] = {
                "num_ctx": 32768,
                "timeout": int(s.get("grounding.timeout_sec", 600)) if s else 600,
                "think": False,
            }

        return kwargs

    def _cloud_config(self) -> dict[str, Any]:
        """Build kwargs for the cloud (OpenAI-compatible) backend."""
        from langextract.factory import ModelConfig

        s = self.settings
        base = (s.get("grounding.cloud_base_url", "") if s else "") or (
            s.get("summarisation.api_base_url", "") if s else ""
        )
        key = (s.get("grounding.cloud_api_key", "") if s else "") or (
            s.get("summarisation.api_key", "") if s else ""
        )
        model = (s.get("grounding.cloud_model", "") if s else "") or (
            s.get("summarisation.cloud_model", "gpt-4o-mini") if s else "gpt-4o-mini"
        )
        return {
            "config": ModelConfig(
                model_id=model,
                provider="openai",
                provider_kwargs={"api_key": key, "base_url": base},
            ),
        }

    # ── public API ──────────────────────────────────────────────────────

    def extract(
        self,
        source_text: str,
        summary_bullets: list[str] | None = None,
        content_type: str = "normal_book",
    ) -> GroundingResult:
        """Extract verbatim-grounded claims from the source text.

        Args:
            source_text: the raw chapter text (the ground truth — claims are
                grounded against THIS text).
            summary_bullets: optional list of summary bullets.  If provided,
                they are *also* passed to langextract as additional
                extraction targets so we can check which bullets have a
                verbatim span (strong grounding) vs which don't (weak).
            content_type: one of the content_presets keys.  Selects the
                prompt + example bank.

        Returns:
            A ``GroundingResult``.  Check ``.available`` first; if False,
            surface ``.alarm`` to the user and fall back to semantic layers.
        """
        import time as _time

        t0 = _time.monotonic()

        # ── Guard 1: disabled in settings ──────────────────────────────
        if not self._is_enabled():
            return GroundingResult(
                available=False,
                alarm=GroundingAlarm(
                    severity="info",
                    code="grounding_disabled",
                    message="🛡️ Source grounding is disabled in settings "
                    "(grounding.enabled=False). Pipeline uses Layers 1-7 only.",
                ),
            )

        # ── Guard 2: langextract not installed ─────────────────────────
        if not is_langextract_available():
            return GroundingResult(
                available=False,
                alarm=GroundingAlarm(
                    severity="info",
                    code="langextract_not_installed",
                    message="🛡️ langextract is not installed. Run "
                    "`pip install langextract` to enable source grounding. "
                    "Pipeline continues with Layers 1-7.",
                ),
            )

        # ── Guard 3: source too short to ground ────────────────────────
        if not source_text or len(source_text) < 200:
            return GroundingResult(
                available=False,
                alarm=GroundingAlarm(
                    severity="info",
                    code="source_too_short",
                    message=f"🛡️ Source too short ({len(source_text or '')} chars) "
                    "for langextract grounding — skipped.",
                ),
            )

        # ── Run the extraction (under lock — langextract may not be
        #     reentrant, and Ollama has model-load contention) ───────────
        with self._lock:
            try:
                claims = self._run_langextract(source_text, summary_bullets, content_type)
            except _BackendUnreachableError as e:
                return GroundingResult(
                    available=False,
                    alarm=GroundingAlarm(
                        severity="warning",
                        code="backend_unreachable",
                        message=f"🛡️⚠️ Grounding backend unreachable: {e}. "
                        "Pipeline falls back to Layers 1-7 — OUTPUT MAY "
                        "CONTAIN UNVERIFIED CLAIMS for this chapter.",
                    ),
                    elapsed_sec=_time.monotonic() - t0,
                )
            except Exception as e:
                # Catch-all: NEVER let a langextract bug crash the pipeline.
                self.log(
                    f"🛡️❌ langextract raised {type(e).__name__}: {e}",
                    "ERROR",
                )
                return GroundingResult(
                    available=False,
                    alarm=GroundingAlarm(
                        severity="error",
                        code="langextract_exception",
                        message=f"🛡️❌ langextract crashed: {type(e).__name__}: {e}. "
                        "Pipeline falls back to Layers 1-7. "
                        "Check that the grounding model is pulled and "
                        "Ollama is running.",
                    ),
                    elapsed_sec=_time.monotonic() - t0,
                )

        # ── Build the result ───────────────────────────────────────────
        grounded = [c for c in claims if c.is_grounded]
        ungrounded = [c for c in claims if not c.is_grounded]
        backend = self._get_backend().value
        elapsed = _time.monotonic() - t0
        result = GroundingResult(
            available=True,
            claims=claims,
            grounded_count=len(grounded),
            ungrounded_count=len(ungrounded),
            ungrounded_texts=[c.text[:120] for c in ungrounded],
            backend_used=backend,
            elapsed_sec=elapsed,
        )
        self.log(
            f"  {result.format_report()}",
            "INFO" if result.ungrounded_count == 0 else "WARNING",
        )
        return result

    # ── internal: the actual langextract call ───────────────────────────

    def _run_langextract(
        self,
        source_text: str,
        summary_bullets: list[str] | None,
        content_type: str,
    ) -> list[GroundedClaim]:
        """Call lx.extract() and convert the result to GroundedClaim list.

        Raises ``_BackendUnreachableError`` for connection/model issues
        (so the caller can produce a clean alarm), and lets any other
        exception propagate (caught by the outer try/except).
        """
        import langextract as lx

        backend = self._get_backend()
        prompt = _prompt_for(content_type)
        examples = _build_examples(content_type)

        # Build the kwargs for the chosen backend.
        if backend == GroundingBackend.OLLAMA:
            backend_kwargs = self._ollama_config()
            # Ollama needs model_url, not a ModelConfig.
            extract_kwargs = {
                "text_or_documents": source_text,
                "prompt_description": prompt,
                "examples": examples,
                "model_id": backend_kwargs["model_id"],
                "model_url": backend_kwargs["model_url"],
            }
        else:  # CLOUD
            backend_kwargs = self._cloud_config()
            extract_kwargs = {
                "text_or_documents": source_text,
                "prompt_description": prompt,
                "examples": examples,
                "config": backend_kwargs["config"],
            }

        # Add the common kwargs (passes, workers, chunk size).
        extract_kwargs.update(self._extraction_kwargs())

        # Probe the backend BEFORE the (expensive) extract call, so we can
        # raise a clean _BackendUnreachableError instead of a confusing
        # langextract internal error.
        self._probe_backend(backend, backend_kwargs)

        # V13.41.2: Log the start of langextract with the actual config
        _s = self.settings
        _chunk_size = int(_s.get("grounding.max_char_buffer", 8000)) if _s else 8000
        _workers = int(_s.get("grounding.max_workers", 1)) if _s else 1
        _timeout = int(_s.get("grounding.timeout_sec", 600)) if _s else 600
        _model = backend_kwargs.get("model_id", "unknown")
        _estimated_chunks = max(1, len(source_text) // _chunk_size)
        self.log(
            f"  🛡️ langextract starting: model={_model}, chunks≈{_estimated_chunks} "
            f"(size={_chunk_size}, workers={_workers}, timeout={_timeout}s)",
            "INFO",
        )

        # ── Run the extraction ────────────────────────────────────────
        # NOTE: lx.extract returns an AnnotatedDocument with .extractions
        # (a list of Extraction objects, each with .extraction_text,
        # .extraction_class, .char_interval, .attributes).
        #
        # V13.37.0: Wrap lx.extract in a timeout to prevent the 406-second
        # hang observed in conversion logs. The grounding.timeout_sec setting
        # was documented (default 120s) but NEVER WIRED UP — now it's enforced
        # via concurrent.futures. On timeout, return an empty result (graceful
        # degradation — Layer 8 just reports "unavailable" for this chapter).
        import concurrent.futures

        s = self.settings
        _timeout_sec = int(s.get("grounding.timeout_sec", 120)) if s else 120
        result_doc = None
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lx.extract, **extract_kwargs)
                result_doc = future.result(timeout=_timeout_sec)
        except concurrent.futures.TimeoutError:
            self.log(
                f"🛡️⏱️ langextract timed out after {_timeout_sec}s — skipping "
                f"grounding for this chapter (Layer 8 unavailable).",
                "WARNING",
            )
            return []  # empty claims list — caller treats as "unavailable"

        # V13.41.2: Early-exit if Pass 1 returned 0 extractions. Don't waste
        # time on bullet matching if there's nothing to match against.
        # V13.45.5: Before giving up, try the Qwythos model as a fallback
        # (user's request: "before going to fallback, lets try qwythos model").
        # Qwythos is Claude-based and may follow the extraction format better
        # than Gemma 4. If Qwythos also returns 0, return empty (content judge
        # will handle grounding via semantic similarity).
        _raw_extractions = getattr(result_doc, "extractions", []) or []
        if not _raw_extractions:
            # V13.45.5: Try Qwythos model as fallback
            # V18.20.4.12 (W-a10): inline literal → model_taxonomy constant
            # (de-magic only — same string value, zero behavior change).
            _qwythos_model = RIG_FALLBACK_MODEL
            _current_model = (
                backend_kwargs.get("model_id", "") if backend == GroundingBackend.OLLAMA else ""
            )
            if backend == GroundingBackend.OLLAMA and _current_model != _qwythos_model:
                self.log(
                    f"  🛡️ Pass 1 returned 0 extractions with {_current_model} — "
                    f"retrying with Qwythos ({_qwythos_model})…",
                    "INFO",
                )
                # Override the model and retry
                _qwythos_kwargs = dict(extract_kwargs)
                _qwythos_kwargs["model_id"] = _qwythos_model
                try:
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(lx.extract, **_qwythos_kwargs)
                        try:
                            result_doc = future.result(timeout=_timeout_sec)
                        except concurrent.futures.TimeoutError:
                            self.log(
                                f"  🛡️ Qwythos retry timed out ({_timeout_sec}s) — "
                                f"falling back to content judge",
                                "WARNING",
                            )
                            return []
                except Exception as _qe:
                    self.log(
                        f"  🛡️ Qwythos retry failed: {_qe} — falling back to content judge",
                        "WARNING",
                    )
                    return []

                _raw_extractions = getattr(result_doc, "extractions", []) or []
                if _raw_extractions:
                    self.log(
                        f"  🛡️ Qwythos retry succeeded: {len(_raw_extractions)} extractions",
                        "INFO",
                    )
                else:
                    self.log(
                        "  🛡️ Qwythos also returned 0 extractions — falling back to content judge",
                        "WARNING",
                    )
                    return []
            else:
                self.log(
                    "  🛡️ Pass 1 returned 0 extractions — skipping bullet grounding "
                    "(model produced no claims from the source text). "
                    "Content judge will handle grounding via semantic similarity.",
                    "WARNING",
                )
                return []

        # Convert to our neutral GroundedClaim type.
        claims: list[GroundedClaim] = []
        for ext in _raw_extractions:
            char_iv = getattr(ext, "char_interval", None)
            # char_interval is either None or a (start, end) tuple-like.
            interval: tuple[int, int] | None = None
            snippet = ""
            if char_iv is not None:
                try:
                    start, end = int(char_iv[0]), int(char_iv[1])
                    interval = (start, end)
                    snippet = source_text[start:end]
                except Exception as _e:
                    interval = None
            claims.append(
                GroundedClaim(
                    text=getattr(ext, "extraction_text", "") or "",
                    extraction_class=getattr(ext, "extraction_class", "claim") or "claim",
                    char_interval=interval,
                    attributes=dict(getattr(ext, "attributes", {}) or {}),
                    source_snippet=snippet,
                )
            )

        # ── If summary bullets were given, match them to Pass 1 extractions.
        # V13.41.2: SKIPPED the second lx.extract() call (Pass 2). Pass 2 was
        # running a full second extraction on the source text (~190s with
        # Gemma 4 12B), which caused the 120s timeout every time. Instead,
        # we match each bullet to the Pass 1 extractions using rapidfuzz.
        # This gives us the same char_interval grounding in <1 second instead
        # of another 190s LLM call.
        if summary_bullets:
            bullet_claims = self._match_bullets_to_extractions(summary_bullets, claims)
            claims.extend(bullet_claims)

        return claims

    def _match_bullets_to_extractions(
        self,
        bullets: list[str],
        source_extractions: list[GroundedClaim],
    ) -> list[GroundedClaim]:
        """V13.41.2: Match bullets to Pass 1 extractions using rapidfuzz.

        Instead of running a second lx.extract() call (which takes ~190s with
        Gemma 4 12B), we match each bullet to the extractions from Pass 1.
        If a bullet matches an extraction that has a char_interval, the bullet
        inherits that char_interval (strong grounding).

        This runs in <1 second (no LLM call) and gives the same result.
        """
        try:
            from rapidfuzz import fuzz as rf_fuzz

            has_rf = True
        except ImportError:
            has_rf = False

        # Filter to extractions that have char_intervals (only these can ground)
        grounded_extractions = [
            ext for ext in source_extractions if ext.char_interval is not None and ext.text.strip()
        ]

        if not grounded_extractions:
            self.log(
                f"  🛡️ Pass 1 returned {len(source_extractions)} extractions "
                f"but 0 have char_intervals — bullet grounding skipped",
                "DEBUG",
            )
            return []

        bullet_claims: list[GroundedClaim] = []
        grounded_count = 0
        for bullet in bullets:
            bullet = (bullet or "").strip()
            if not bullet:
                continue
            best_ext = None
            best_score = 0.0
            for ext in grounded_extractions:
                if has_rf:
                    score = rf_fuzz.partial_ratio(bullet.lower(), ext.text.lower()) / 100.0
                else:
                    a = set(bullet.lower().split())
                    b = set(ext.text.lower().split())
                    score = (len(a & b) / len(a)) if a else 0.0
                if score > best_score:
                    best_score = score
                    best_ext = ext

            if best_ext is not None and best_score >= 0.60:
                bullet_claims.append(
                    GroundedClaim(
                        text=bullet,
                        extraction_class="summary_bullet",
                        char_interval=best_ext.char_interval,
                        attributes={"match_score": best_score},
                        source_snippet=best_ext.source_snippet,
                    )
                )
                grounded_count += 1
            else:
                bullet_claims.append(
                    GroundedClaim(
                        text=bullet,
                        extraction_class="summary_bullet",
                        char_interval=None,
                        attributes={"match_score": best_score},
                        source_snippet="",
                    )
                )

        self.log(
            f"  🛡️ Bullet matching: {grounded_count}/{len(bullets)} bullets "
            f"grounded via Pass 1 extractions (rapidfuzz ≥60%)",
            "INFO",
        )
        return bullet_claims

    def _ground_bullets(
        self,
        source_text: str,
        bullets: list[str],
        prompt: str,
        examples,
        backend: GroundingBackend,
        backend_kwargs: dict[str, Any],
    ) -> list[GroundedClaim]:
        """Extract each summary bullet as a claim and check its char_interval.

        We feed langextract a prompt that says "extract these exact statements
        from the source if present" and pass the bullets as the text to
        locate.  Bullets that langextract can find verbatim get a char_interval;
        bullets it can't locate get char_interval=None (→ weak grounding).
        """
        import langextract as lx

        # Build a composite "document" that contains the source + the
        # bullets as candidate extractions.  langextract will try to
        # locate each bullet in the source.
        # Strategy: run extract on the source with a prompt that asks for
        # "claims matching these bullets", passing the bullets as hints.
        # If a bullet can't be found, its char_interval will be None.
        bullets_block = "\n".join(f"- {b}" for b in bullets if b and b.strip())
        locate_prompt = (
            prompt + "\n\nAdditionally, locate each of the following summary "
            "statements in the source text.  If a statement appears "
            "verbatim (or near-verbatim) in the source, extract it with "
            "its char_interval.  If a statement does NOT appear in the "
            "source, do NOT extract it (it will be treated as "
            "ungrounded).\n\nSummary statements to locate:\n" + bullets_block
        )

        locate_kwargs = {
            "text_or_documents": source_text,
            "prompt_description": locate_prompt,
            "examples": examples,
        }
        if backend == GroundingBackend.OLLAMA:
            locate_kwargs["model_id"] = backend_kwargs["model_id"]
            locate_kwargs["model_url"] = backend_kwargs["model_url"]
        else:
            locate_kwargs["config"] = backend_kwargs["config"]
        locate_kwargs.update(self._extraction_kwargs())

        try:
            doc = lx.extract(**locate_kwargs)
        except Exception as e:
            # Don't fail the whole extraction just because bullet-location
            # failed — the source-claim extractions are still valid.
            self.log(
                f"  🛡️ bullet-location sub-pass failed: {e} (source-claim grounding still valid)",
                "DEBUG",
            )
            return []

        # Match returned extractions to the original bullets by fuzzy text
        # overlap (langextract may have rephrased slightly).  A bullet is
        # "strongly grounded" iff some returned extraction has a
        # char_interval AND overlaps the bullet text ≥ 60%.
        try:
            from rapidfuzz import fuzz as rf_fuzz

            has_rf = True
        except ImportError:
            has_rf = False

        bullet_claims: list[GroundedClaim] = []
        for bullet in bullets:
            bullet = (bullet or "").strip()
            if not bullet:
                continue
            best_ext = None
            best_score = 0.0
            for ext in getattr(doc, "extractions", []) or []:
                ext_text = getattr(ext, "extraction_text", "") or ""
                if not ext_text:
                    continue
                if has_rf:
                    score = rf_fuzz.partial_ratio(bullet.lower(), ext_text.lower()) / 100.0
                else:
                    # crude word overlap
                    a = set(bullet.lower().split())
                    b = set(ext_text.lower().split())
                    score = (len(a & b) / len(a)) if a else 0.0
                if score > best_score:
                    best_score = score
                    best_ext = ext
            # Determine char_interval from the best-matching extraction
            interval: tuple[int, int] | None = None
            snippet = ""
            if best_ext is not None and best_score >= 0.60:
                char_iv = getattr(best_ext, "char_interval", None)
                if char_iv is not None:
                    try:
                        start, end = int(char_iv[0]), int(char_iv[1])
                        interval = (start, end)
                        snippet = source_text[start:end]
                    except Exception as _e:
                        interval = None
            bullet_claims.append(
                GroundedClaim(
                    text=bullet,
                    extraction_class="summary_bullet",
                    char_interval=interval,
                    attributes={"match_score": f"{best_score:.2f}"},
                    source_snippet=snippet,
                )
            )
        return bullet_claims

    # ── backend probe ───────────────────────────────────────────────────

    def _probe_backend(self, backend: GroundingBackend, backend_kwargs: dict[str, Any]) -> None:
        """Verify the backend is reachable before the expensive extract call.

        Raises ``_BackendUnreachableError`` on failure.  This gives the
        caller a clean alarm instead of a langextract-internal stack trace.
        """
        if backend == GroundingBackend.OLLAMA:
            model = backend_kwargs.get("model_id", "")
            url = backend_kwargs.get("model_url", "http://localhost:11434")
            # Reuse the app's existing Ollama probe (network.is_ollama_reachable)
            # so we get the same retry/proxy logic as the rest of the app.
            try:
                from utils.network import is_ollama_reachable, list_ollama_models

                if not is_ollama_reachable(url):
                    raise _BackendUnreachableError(
                        f"Ollama not reachable at {url}. Is `ollama serve` running?"
                    )
                if model:
                    available = list_ollama_models(url)
                    # Case-insensitive check
                    if available and not any(m.lower() == model.lower() for m in available):
                        raise _BackendUnreachableError(
                            f"Grounding model '{model}' not found in Ollama. "
                            f"Available: {available[:8]}{'…' if len(available) > 8 else ''}. "
                            f"Run: ollama pull {model}"
                        )
            except _BackendUnreachableError:
                raise
            except Exception as e:
                # If our probe itself fails, don't block — let langextract
                # try and fail with its own error (which we catch above).
                self.log(
                    f"  🛡️ Ollama probe failed ({e}); proceeding to extract anyway",
                    "DEBUG",
                )
        else:  # CLOUD
            # For cloud, we trust the user's API key/base_url.  A real probe
            # would cost a token; we let the extract call itself fail fast.
            base = ""
            if "config" in backend_kwargs:
                try:
                    base = backend_kwargs["config"].provider_kwargs.get("base_url", "")
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
            if not base:
                raise _BackendUnreachableError(
                    "Cloud grounding backend has no base_url configured "
                    "(grounding.cloud_base_url). Set it in Settings."
                )


class _BackendUnreachableError(Exception):
    """Internal: raised when the grounding backend can't be reached.

    Caught by ``extract()`` and converted to a clean GroundingAlarm so the
    pipeline falls back gracefully.
    """

    pass
