"""V18.2.25 (Phase 4.1) — OpenTelemetry tracing for the LLM pipeline.

The problem
-----------
The app has local structured-JSONL logging but no distributed tracing — no
spans/trace-IDs correlating a chapter's full call chain (prompt→LLM→parse→
postcheck→grounding). It's impossible to attribute latency or cost to a
specific stage in a 50-call pipeline.

The fix (2026 standard)
-----------------------
OpenTelemetry spans: one root span per chapter, child spans per LLM call
(with ``gen_ai.*`` semantic-convention attributes: model, temperature, token
counts), plus spans for parse/postcheck/grounding. Export to OTLP (Langfuse
or Arize Phoenix as backends).

Design: opt-in, zero-overhead when disabled
-------------------------------------------
Tracing is **opt-in** via ``settings.observability.tracing_enabled`` (default
False). When disabled, the ``span()`` context manager is a no-op — zero
overhead, no imports, no exports. When enabled, it creates real OTel spans
via the global tracer.

The existing structured-JSONL logger remains as the log-correlation
side-channel. Spans give the trace; logs give the detail.

Usage::

    from core.obs.tracing import span, is_tracing_enabled

    with span("chapter.summarize", chapter=heading, model=model):
        with span("llm.exec_summary", gen_ai_model=model, gen_ai_tokens=max_tok):
            exec_text = provider.complete(prompt)
        with span("postcheck.anti_false_precision"): ...

When tracing is disabled, ``span()`` is a no-op context manager — the code
runs identically to the un-instrumented version. This makes it safe to
sprinkle spans throughout the pipeline without performance impact when
tracing is off.

Book-agnostic (Key Decision #3): tracing attributes are structural (stage
names, token counts, model names), never book content.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# ── Tracing state ──────────────────────────────────────────────────────────

_tracing_enabled: bool | None = None
_tracer: Any | None = None


def _is_tracing_enabled() -> bool:
    """Check if tracing is enabled (cached after first read)."""
    global _tracing_enabled
    if _tracing_enabled is not None:
        return _tracing_enabled
    try:
        from utils.settings import Settings
        _tracing_enabled = bool(
            Settings().get("observability.tracing_enabled", False)
        )
    except Exception:
        _tracing_enabled = False
    return _tracing_enabled


def _get_tracer() -> Any | None:
    """Get the OTel tracer (lazy, cached). Returns None if tracing disabled."""
    global _tracer
    if not _is_tracing_enabled():
        return None
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # If a global tracer provider is already set (e.g. by Langfuse/Phoenix
        # SDK initialization), use it. Otherwise, set up a console exporter
        # so spans are visible without a backend.
        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            provider = TracerProvider()
            # Console exporter — prints spans to stderr. Replace with
            # OTLPSpanExporter for Langfuse/Phoenix in production.
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
            trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer("markitdown-pro", "18.2.25")
        return _tracer
    except Exception as exc:
        logger.debug("tracing init failed: %s: %s", type(exc).__name__, exc)
        return None


def is_tracing_enabled() -> bool:
    """Public API: check if tracing is enabled."""
    return _is_tracing_enabled()


# ── Span context manager ─────────────────────────────────────────────────


@contextmanager
def span(
    name: str,
    **attributes: Any,
) -> Iterator[Any]:
    """Create a tracing span (no-op when tracing is disabled).

    Args:
        name: the span name (e.g. ``"chapter.summarize"``,
            ``"llm.exec_summary"``, ``"postcheck.anti_false_precision"``).
        **attributes: key-value attributes set on the span. Use the
            ``gen_ai.*`` semantic conventions for LLM calls:
            ``gen_ai_model``, ``gen_ai_tokens``, ``gen_ai_temperature``,
            ``gen_ai_request_model``, etc.

    Yields:
        The span object (or None when tracing is disabled). Callers can
        set additional attributes or record exceptions on it.

    Example::

        with span("llm.exec_summary", gen_ai_model=model, gen_ai_tokens=4096) as s:
            result = provider.complete(prompt)
            if s:
                s.set_attribute("gen_ai_response_tokens", estimate_tokens(result))

    When tracing is disabled, this is a no-op — zero overhead.
    """
    tracer = _get_tracer()
    if tracer is None:
        # No-op: yield None, do nothing.
        yield None
        return

    with tracer.start_as_current_span(name) as otel_span:
        # Set attributes from kwargs.
        for key, value in attributes.items():
            try:
                otel_span.set_attribute(key, value)
            except Exception:
                pass  # non-serializable value — skip
        try:
            yield otel_span
        except Exception as exc:
            # Record the exception on the span (doesn't suppress it).
            try:
                from opentelemetry.trace import Status, StatusCode
                otel_span.record_exception(exc)
                otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:
                pass
            raise


# ── Convenience: timed span (records duration as an attribute) ───────────


@contextmanager
def timed_span(
    name: str,
    **attributes: Any,
) -> Iterator[Any]:
    """Like ``span()`` but also records the wall-clock duration.

    The duration (in milliseconds) is set as the ``duration_ms`` attribute
    on the span. Useful for stages where you want to see per-stage latency
    in the tracing backend's dashboard.

    Example::

        with timed_span("postcheck.grounding", chapter=heading) as s:
            grounding_result = run_grounding_check(bullets, source)
    """
    start = time.time()
    with span(name, **attributes) as otel_span:
        yield otel_span
    elapsed_ms = (time.time() - start) * 1000
    if otel_span is not None:
        try:
            otel_span.set_attribute("duration_ms", round(elapsed_ms, 1))
        except Exception:
            pass


# ── Flush (call at end of conversion to ensure all spans are exported) ───


def flush() -> None:
    """Force-flush all pending spans to the exporter.

    Call this at the end of a conversion (or chapter) to ensure all spans
    are exported before the process exits. No-op when tracing is disabled.
    """
    if not _is_tracing_enabled():
        return
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        # BatchSpanProcessor has a force_flush method.
        if hasattr(provider, "force_flush"):
            provider.force_flush()
    except Exception as exc:
        logger.debug("tracing flush failed: %s: %s", type(exc).__name__, exc)
