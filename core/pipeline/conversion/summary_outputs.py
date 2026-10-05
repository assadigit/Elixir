"""V0.4.26 (Phase 3 de-monolithization, commit 2 of 3): the
summary-outputs responsibility — extracted from converter_impl.py (evidence:
SWOT W2 + README roadmap item 12, "convert 1,055 lines"; plan: Task 3-plan).

One runner, ``run_summary_outputs``, holding the four gated-output blocks
that sat inline inside ``convert()`` (L1279-1392 + L1436-1452 of the
pre-move converter_impl.py, commit e3e7e7f), moved with exactly the same
mechanical edits as every convert()-block move (the visual_features.py /
reporting.py precedent): (a) ``self.`` -> ``converter.``; (b) dedented one
try-level out (12 -> 4 spaces); (c) the TWO bare ``self`` occurrences in
the four blocks (``getattr(self, "_judge_results", None)`` in the keypoints
build, ``hasattr(self, "temp_markdown_path")`` in the citation-graph guard)
-> ``converter``.  Everything else is byte-identical, including the
U+2011 non-breaking hyphen in the simplified-digest entry line
("jargon‑free") and the lazy ``from core.summarisation import ...`` /
``from core.outputs.citation_graph import ...`` imports (the V18.19.2.0
Debt D4 lazy-import discipline — imported at call time, never eagerly).

The four blocks, in their original internal order:

1. DOCX build (gated by ``request.generate_docx``) — builds the Word
   report via ``core.docx.builder.DocxBuilder``; produces ``docx_path``.
2. Keypoints build (gated on ``summaries``) — the KeypointsBuilder MD +
   DOCX pair and the V18.20.3.10 (W11) DEDUPED final keypoint count.
3. Simplified keypoints digest (gated by
   ``request.simplified_keypoints_enabled``) — graceful degradation: an
   unavailable model or infrastructure error skips the digest with a
   WARNING and never crashes the pipeline.
4. Citation graph (gated only on cancel) — the ``[N]``-citation graph
   written next to the run's logs.

Every convert() local the blocks read is threaded in as a keyword
parameter named EXACTLY like the local, so the body text is otherwise
unchanged: ``segments``, ``summaries``, ``book_title``.  ``_elapsed`` is
the RAW ``_elapsed()`` closure captured at the top of convert() (the DOCX
block logs ``[{_elapsed()}]``) — threaded as a parameter named exactly
like the local, the same explicit-threading discipline as
run_diagnostic_summary's ``_t_start`` / run_summarization's ``elapsed_fn``.

ORDER DEVIATION (the one, documented): in pre-move convert() the
citation-graph block ran AFTER the output-studio block (``progress(0.96)``
+ ``run_output_studio`` sat between the simplified digest and the citation
graph); inside this runner it follows the simplified digest directly, so
its log lines now precede the studio's.  There is no data dependency
either way (the graph reads only summaries/segments/temp_markdown; the
studio reads summaries/segments/paths) — the change is log interleaving
only, and the runner is called at the position of the FIRST block so the
rest of convert()'s step order is untouched.

``SummaryOutputsResult`` carries every value the blocks produce:
``docx_path`` (feeds ``ConversionResult.docx_path``), ``keypoints_md_path``
/ ``keypoints_docx_path`` (the build-log paths; convert() never read them
after the block, so they stay on the result object only), and
``kp_final_count`` (the W11 deduped count; convert() unpacks it into the
``_kp_final_count`` local for the library-tracking call).

Module-level names the moved bodies reference: ``DocxBuilder`` (moved from
converter_impl's eager import — same eager timing relative to this module,
and core.docx.builder is a leaf with no core.pipeline imports) and
``logger``.  ``logger`` binds ``get_main_logger()`` — the SAME "Elixir"
logger object the bodies reached through converter_impl's module globals
before the move (not ``logging.getLogger(__name__)``: a verbatim move must
not change the routing of the ``logger.debug`` traces).

Leaf module: no ``core.pipeline`` imports (acyclic, like every other
conversion/* module).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.docx.builder import DocxBuilder
from utils.logging import get_main_logger

logger = get_main_logger()


@dataclass
class SummaryOutputsResult:
    """The state the four summary-output blocks produce for convert().

    Fields:
        docx_path: the built Word report path, or None (gate off / cancel /
            build failed) — feeds ``ConversionResult.docx_path``.
        keypoints_md_path: the keypoints markdown path from the builder
            (None when the keypoints block did not run).
        keypoints_docx_path: the keypoints DOCX path from the builder.
        kp_final_count: the V18.20.3.10 (W11) DEDUPED keypoint count that
            shipped in the keypoints file — convert() unpacks it into
            ``_kp_final_count`` for the library-tracking call.
    """

    docx_path: Any = None
    keypoints_md_path: Any = None
    keypoints_docx_path: Any = None
    kp_final_count: int | None = None


def run_summary_outputs(
    converter: Any,
    *,
    segments: list[Any],
    summaries: list[Any],
    book_title: str,
    _elapsed: Callable[[], str],
) -> SummaryOutputsResult:
    """Build the four gated summary outputs (VERBATIM move from convert();
    see the module docstring for the parameter threading + the one
    documented order deviation).

    Returns a :class:`SummaryOutputsResult`; every path/count the blocks
    produce is on it.  Read-only over the parameters apart from the
    builders' own writes.
    """
    # ── Step 10: DOCX ────────────────────────────────────────────────
    docx_path = None
    if converter.request.generate_docx and not converter._cancel_requested("DOCX build"):
        converter._update_status("Building DOCX report…")
        converter._log(f"  ⏱️ DOCX phase starting | [{_elapsed()}]", "INFO")
        builder = DocxBuilder(converter.request, log_callback=converter._log)
        if builder.build_report(
            summaries,
            [{"heading": s.heading, "content": s.content} for s in segments],
            converter.request.input_path,
            converter.docx_path,
        ):
            docx_path = converter.docx_path

    # ── Keypoints (always when summaries exist) ───────────────────────
    keypoints_md_path = None
    keypoints_docx_path = None
    # V18.20.3.10 (W11): the DEDUPED keypoint count from the builder —
    # the library must record the number that actually shipped in
    # the keypoints file (36), not the raw bullet count (41).
    _kp_final_count = None
    if summaries and not converter._cancel_requested("keypoints build"):
        converter._update_status("Building Keypoints files…")
        # V18.19.2.0 (Debt D4): lazy import breaks the converter→core.summarisation
        # eager import cycle. KeypointsBuilder is only needed when summaries exist.
        from core.summarisation import KeypointsBuilder

        kp = KeypointsBuilder(log_callback=converter._log)
        # Pass segments + concepts for J1 ordering, K1 confidence,
        # K2 source excerpts, H2 page traceability
        all_concepts = []
        try:
            from core.summarisation.text_preprocessor import DeterministicPreprocessor

            pp = DeterministicPreprocessor()
            for seg in segments:
                all_concepts.extend(pp.extract_concepts(seg.content))
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        keypoints_md_path, keypoints_docx_path = kp.build(
            summaries,
            book_title=converter.request.input_path.stem,
            output_dir=converter.paths.keypoints_dir,
            segments=segments,
            concepts=all_concepts,
            judge_results=getattr(converter, "_judge_results", None),
        )
        # V18.20.3.10 (W11): capture the deduped count for the
        # library record (falls back to the raw sum below when the
        # builder didn't run or predates the attribute).
        _kp_final_count = getattr(kp, "final_keypoint_count", None)
        if keypoints_md_path:
            converter._log(f"📌 Keypoints MD  → {keypoints_md_path}", "SUCCESS")
        if keypoints_docx_path:
            converter._log(f"📌 Keypoints DOCX → {keypoints_docx_path}", "SUCCESS")

    # ── NEW: Sprint 2 – Simplified Keypoints Digest ──────────────────
    # Robust error handling — if simplification model fails to
    # load or any error occurs, gracefully skip simplification instead
    # of crashing the entire pipeline. The keypoints (already generated)
    # are preserved. The user gets a clear warning instead of a crash.
    if (
        converter.request.simplified_keypoints_enabled
        and summaries
        and not converter._cancel_requested("simplified keypoints")
    ):
        converter._update_status("Generating Simplified Keypoints Digest…")
        converter._log("  📌 Generating simplified keypoints (jargon‑free digest)…", "INFO")
        try:
            # V18.19.2.0 (Debt D4): lazy import breaks the eager import cycle.
            from core.summarisation import SimplifiedKeypointsBuilder

            builder = SimplifiedKeypointsBuilder(
                request=converter.request,
                log_callback=converter._log,
            )
            output_path = builder.build(
                summaries=summaries,
                book_title=book_title,
                output_dir=converter.paths.keypoints_dir,
            )
            if output_path:
                converter._log(f"  ✅ Simplified keypoints saved to: {output_path}", "SUCCESS")
        except (OSError, ConnectionError, TimeoutError) as e:
            # Model load failure, Ollama connection error, timeout
            converter._log(f"  ⚠️ Simplification skipped (model unavailable): {e}", "WARNING")
            converter._log(
                "  ℹ️ Keypoints and summaries are still available without simplification.",
                "INFO",
            )
        except Exception as e:
            # Any other error — don't crash the pipeline
            error_msg = str(e).lower()
            if any(
                kw in error_msg
                for kw in (
                    "model",
                    "load",
                    "ollama",
                    "connection",
                    "timeout",
                    "memory",
                    "vram",
                )
            ):
                converter._log(f"  ⚠️ Simplification skipped (infrastructure error): {e}", "WARNING")
                converter._log(
                    "  ℹ️ Keypoints and summaries are still available without simplification.",
                    "INFO",
                )
            else:
                converter._log(f"  ❌ Failed to generate simplified keypoints: {e}", "WARNING")

    # V10.21.0: Citation graph — extract [N] citations and build graph
    if not converter._cancel_requested("citation graph"):
        try:
            from core.outputs.citation_graph import generate_citation_graph

            if hasattr(converter, "temp_markdown_path") and converter.temp_markdown_path.exists():
                _raw_md = converter.temp_markdown_path.read_text(encoding="utf-8")
                generate_citation_graph(
                    summaries=summaries,
                    segments=segments,
                    raw_markdown=_raw_md,
                    book_title=book_title,
                    output_dir=converter.paths.logs_dir.parent,
                    log_callback=converter._log,
                )
        except Exception as e:
            converter._record_partial_failure("Citation graph", e)

    return SummaryOutputsResult(
        docx_path=docx_path,
        keypoints_md_path=keypoints_md_path,
        keypoints_docx_path=keypoints_docx_path,
        kp_final_count=_kp_final_count,
    )
