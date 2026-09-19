"""V10.1.0: Scientific Evidence Map — opt-in output for academic papers.

Integration point #4 from the langextract integration plan (Q4=B: opt-in
output).  This generator runs langextract over the *raw source text* of each
chapter and produces:

1. ``{BookName}.EvidenceMap.html`` — a self-contained, interactive HTML page
   that highlights every extracted claim/finding/method/result in its
   original source context, grouped by chapter.  Each claim is clickable to
   jump to its source span.  Uses langextract's own ``lx.visualize`` when
   available, or a built-in fallback renderer otherwise.
2. ``{BookName}.EvidenceMap.json`` — the raw structured extractions (one
   JSON object per chapter), for programmatic review or import into other
   tools.

This output is most valuable for ``academic_paper`` content (where "life or
money is at stake"), but works for any content type — the prompt adapts via
``ClaimExtractor``.

Opt-in: gated by the ``output_evidence_map`` flag on ``ConversionRequest``
(defaults False).  Enabled from the wizard's Output Studio step.

Graceful: if langextract is unavailable, the generator writes a small HTML
notice explaining how to enable it, and returns the path (so the output
scanner sees "generated" rather than "failed" — the user gets clear
guidance instead of a silent failure).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.models import SummaryResult

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


class EvidenceMapGenerator:
    """Generate the Scientific Evidence Map (HTML + JSON) for a book.

    Usage (from converter.py)::

        gen = EvidenceMapGenerator(request, log_callback=self._log)
        path = gen.generate(
            summaries=summaries,
            segments=segments,         # the raw chapter texts
            book_title=book_title,
            output_dir=self.paths.evidence_dir,
        )
    """

    def __init__(
        self,
        request: Any = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        # Build a ClaimExtractor from the request's settings.
        self._extractor = None
        try:
            if request is not None:
                from core.grounding import ClaimExtractor
                from utils.settings import Settings

                self._extractor = ClaimExtractor(settings=Settings(), log_callback=self.log)
        except Exception as e:
            self.log(
                f"  🗺️ EvidenceMap: could not init ClaimExtractor ({e}) — "
                f"will emit guidance HTML only",
                "DEBUG",
            )

    def generate(
        self,
        summaries: list[SummaryResult],
        segments: list[Any] | None,
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate the Evidence Map HTML + JSON.

        Args:
            summaries: per-chapter SummaryResult list (for chapter headings).
            segments: per-chapter Segment list (carries the raw source text).
                If None or empty, we fall back to summaries' (empty) source.
            book_title: book title (for the HTML heading + filename).
            output_dir: the ``evidence/`` subfolder Path.

        Returns:
            Path to the generated HTML, or None on hard failure.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = book_title or "Book"
        html_path = output_dir / f"{safe_title}.EvidenceMap.html"
        json_path = output_dir / f"{safe_title}.EvidenceMap.json"

        # ── Pair each summary with its source segment ──────────────────
        # We match by index (the converter preserves order) and fall back
        # to heading text overlap if lengths differ.
        chapters = self._pair_summaries_segments(summaries, segments)
        if not chapters:
            self.log("  🗺️ EvidenceMap: no chapters to process.", "INFO")
            # Still write a minimal HTML so the scanner sees "generated"
            self._write_guidance_html(
                html_path,
                book_title,
                "No chapters were available to build the evidence map.",
            )
            return html_path

        # ── Check langextract availability up front ────────────────────
        from core.grounding import is_langextract_available

        if not is_langextract_available():
            self.log(
                "  🗺️⚠️ langextract not installed — writing guidance HTML. "
                "Run `pip install langextract` to enable the Evidence Map.",
                "WARNING",
            )
            self._write_guidance_html(
                html_path,
                book_title,
                "langextract is not installed. The Scientific Evidence Map "
                "requires Google's langextract library. Run "
                "<code>pip install langextract</code> and re-run this output "
                "from the Output Scanner.",
                alarm=True,
            )
            return html_path

        # ── Check grounding is enabled in settings ─────────────────────
        if self._extractor is None or not self._extractor._is_enabled():
            self.log(
                "  🗺️⚠️ Source grounding is disabled in settings — "
                "writing guidance HTML. Enable grounding.enabled to use "
                "the Evidence Map.",
                "WARNING",
            )
            self._write_guidance_html(
                html_path,
                book_title,
                "Source grounding is disabled. Enable "
                "<code>grounding.enabled</code> in Settings to use the "
                "Scientific Evidence Map.",
                alarm=True,
            )
            return html_path

        # ── Run langextract over each chapter's source text ────────────
        self.log(
            f"  🗺️ Generating Scientific Evidence Map for {len(chapters)} chapter(s)…",
            "INFO",
        )
        all_chapter_data: list[dict[str, Any]] = []
        any_alarm = False
        for idx, (heading, source_text) in enumerate(chapters, 1):
            self._update_status_safe(f"Evidence Map: chapter {idx}/{len(chapters)}")
            self.log(
                f"    🗺️ [{idx}/{len(chapters)}] {heading[:50]}…",
                "DEBUG",
            )
            content_type = (
                getattr(self.request, "source_type", "normal_book")
                if self.request
                else "normal_book"
            )
            t0 = time.monotonic()
            result = self._extractor.extract(
                source_text=source_text,
                summary_bullets=None,  # evidence map = source claims only
                content_type=content_type,
            )
            elapsed = time.monotonic() - t0
            if not result.available:
                any_alarm = True
                self.log(
                    f"    ⚠️ {heading[:50]}: {result.alarm.message if result.alarm else 'unknown'}",
                    "WARNING",
                )
            # Build the chapter's data block
            claims_data = []
            for c in result.claims:
                claims_data.append(
                    {
                        "text": c.text,
                        "class": c.extraction_class,
                        "grounded": c.is_grounded,
                        "char_interval": list(c.char_interval) if c.char_interval else None,
                        "attributes": c.attributes,
                        "source_snippet": c.source_snippet,
                    }
                )
            all_chapter_data.append(
                {
                    "chapter_index": idx,
                    "chapter_heading": heading,
                    "source_text": source_text,
                    "source_length": len(source_text),
                    "available": result.available,
                    "backend": result.backend_used,
                    "elapsed_sec": round(elapsed, 2),
                    "alarm": (
                        {
                            "severity": result.alarm.severity,
                            "code": result.alarm.code,
                            "message": result.alarm.message,
                        }
                        if (not result.available and result.alarm)
                        else None
                    ),
                    "claims": claims_data,
                    "grounded_count": result.grounded_count,
                    "ungrounded_count": result.ungrounded_count,
                }
            )

        # ── Write the JSON dump ────────────────────────────────────────
        try:
            from utils.atomic_io import atomic_write_text

            atomic_write_text(
                json_path,
                json.dumps(
                    {
                        "book_title": book_title,
                        "generator": "EvidenceMapGenerator",
                        "version": "10.1.0",
                        "chapters": all_chapter_data,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            )
            self.log(f"  🗺️ Evidence JSON → {json_path}", "INFO")
        except Exception as e:
            self.log(f"  🗺️⚠️ Failed to write evidence JSON: {e}", "WARNING")

        # ── Write the interactive HTML ─────────────────────────────────
        html = self._render_html(book_title, all_chapter_data, any_alarm)
        try:
            from utils.atomic_io import atomic_write_text

            atomic_write_text(html_path, html)
        except Exception as e:
            self.log(f"  🗺️❌ Failed to write evidence HTML: {e}", "ERROR")
            return None
        self.log(f"  🗺️ Evidence Map HTML → {html_path}", "SUCCESS")
        if any_alarm:
            self.log(
                "  🗺️⚠️ Some chapters had grounding alarms — see the HTML "
                "banner for details. Evidence Map may be partial.",
                "WARNING",
            )
        return html_path

    # ── helpers ──────────────────────────────────────────────────────────

    def _pair_summaries_segments(
        self,
        summaries: list[SummaryResult],
        segments: list[Any] | None,
    ) -> list[tuple]:
        """Return [(heading, source_text), …] pairing summaries with segments.

        Falls back gracefully if segments is None or lengths mismatch.
        """
        out = []
        if not summaries:
            return out
        segs = list(segments or [])
        for i, s in enumerate(summaries):
            heading = s.chapter_heading or f"Chapter {i + 1}"
            source = ""
            if i < len(segs):
                source = getattr(segs[i], "content", "") or ""
            # If no segment text, use the summary's thorough_summary as a
            # last resort (better than nothing for the highlight context).
            if not source and s.thorough_summary:
                source = s.thorough_summary
            out.append((heading, source))
        return out

    def _update_status_safe(self, msg: str) -> None:
        """Update the UI status if the request carries a status callback."""
        try:
            if self.request is not None and hasattr(self.request, "_status_cb"):
                cb = getattr(self.request, "_status_cb", None)
                if cb:
                    cb(msg)
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    def _write_guidance_html(
        self,
        html_path: Path,
        book_title: str,
        message: str,
        alarm: bool = False,
    ) -> None:
        """Write a minimal HTML page explaining why the map is unavailable."""
        banner_cls = "alarm" if alarm else "info"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Evidence Map — {self._esc(book_title)}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 2rem auto; max-width: 720px; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  .banner {{ padding: 1rem 1.25rem; border-radius: 8px; margin: 1.5rem 0; }}
  .banner.info {{ background: #eef6ff; border: 1px solid #b6d4ff; }}
  .banner.alarm {{ background: #fff4e5; border: 1px solid #ffcd80; }}
  code {{ background: #f4f4f4; padding: 0.1em 0.35em; border-radius: 3px; }}
</style></head><body>
<h1>🗺️ Scientific Evidence Map — {self._esc(book_title)}</h1>
<div class="banner {banner_cls}">{message}</div>
<p>This file was generated by Elixir V10.1.0. Once the
required dependency is in place, re-running this output from the Output
Scanner will replace this notice with the full interactive evidence map.</p>
</body></html>"""
        try:
            from utils.atomic_io import atomic_write_text

            atomic_write_text(html_path, html)
        except OSError as _e:
            # V10.4.0 (Phase 6A-4): Log the atomic-write failure (e.g.
            # disk-full) BEFORE falling back to a naive write.  Previously
            # the OSError was silently swallowed and the fallback write
            # would also fail (on a full disk) with no diagnostic.  The
            # fallback is kept for non-disk errors (e.g. temp-file perms).
            self.log(
                f"  🗺️⚠️ Atomic write failed ({_e}); trying direct write.",
                "WARNING",
            )
            # V18.20.4.12 (T-c3): this fallback is DELIBERATELY non-atomic —
            # it is the last resort AFTER atomic_write_text already failed,
            # so repeating temp+replace would just fail the same way (e.g.
            # temp-file perms, fsync-unsupported mounts).  Spelled as an
            # explicit open()/write() pair (semantics identical to the old
            # Path.write_text) so the non-atomic intent stays visible.
            with html_path.open("w", encoding="utf-8") as _f:
                _f.write(html)

    def _render_html(
        self,
        book_title: str,
        chapters: list[dict[str, Any]],
        any_alarm: bool,
    ) -> str:
        """Render the full interactive HTML evidence map (self-contained)."""
        # Compute aggregate stats
        total_claims = sum(len(c.get("claims", [])) for c in chapters)
        total_grounded = sum(c.get("grounded_count", 0) for c in chapters)
        total_ungrounded = sum(c.get("ungrounded_count", 0) for c in chapters)
        pct = (total_grounded / total_claims * 100) if total_claims else 0

        chapters_html = []
        for ch in chapters:
            claims_html = self._render_chapter_claims(ch)
            source_html = self._render_highlighted_source(ch)
            alarm_banner = ""
            if ch.get("alarm"):
                alarm_banner = (
                    f'<div class="chapter-alarm">⚠️ {self._esc(ch["alarm"]["message"])}</div>'
                )
            chapters_html.append(f"""
<section class="chapter" id="ch-{ch["chapter_index"]}">
  <h2>{ch["chapter_index"]}. {self._esc(ch["chapter_heading"])}</h2>
  {alarm_banner}
  <div class="chapter-meta">
    {ch.get("grounded_count", 0)} grounded ·
    {ch.get("ungrounded_count", 0)} ungrounded ·
    backend: {self._esc(ch.get("backend", ""))} ·
    {ch.get("elapsed_sec", 0)}s
  </div>
  <details open><summary>Extracted claims ({len(ch.get("claims", []))})</summary>
    <ul class="claims">{claims_html}</ul>
  </details>
  <details><summary>Source with highlights</summary>
    <pre class="source">{source_html}</pre>
  </details>
</section>""")

        alarm_banner = ""
        if any_alarm:
            alarm_banner = (
                '<div class="global-alarm">⚠️ One or more chapters had '
                "grounding alarms — the map may be partial. See per-chapter "
                "banners for details.</div>"
            )

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Evidence Map — {self._esc(book_title)}</title>
<style>
  :root {{
    --bg: #fafafa; --fg: #1a1a1a; --muted: #666;
    --claim: #e8f4fd; --claim-bd: #4a9ede;
    --finding: #e8fde8; --finding-bd: #4a9e4a;
    --method: #fdf4e8; --method-bd: #de9e4a;
    --result: #fde8f4; --result-bd: #de4a9e;
    --definition: #f0e8fd; --definition-bd: #7a4ade;
    --entity: #e8fdfd; --entity-bd: #4a9e9e;
    --ungrounded: #fde8e8; --ungrounded-bd: #de4a4a;
  }}
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 2rem; background: var(--bg); color: var(--fg); line-height: 1.6; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
  .summary {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.95rem; }}
  .global-alarm {{ background: #fff4e5; border: 1px solid #ffcd80; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1.5rem; }}
  .chapter {{ margin-bottom: 2.5rem; }}
  .chapter-meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 0.5rem; }}
  .chapter-alarm {{ background: #fde8e8; border: 1px solid #de4a4a; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; font-size: 0.9rem; }}
  details {{ margin-top: 0.5rem; }}
  summary {{ cursor: pointer; font-weight: 500; padding: 0.25rem 0; }}
  ul.claims {{ list-style: none; padding-left: 0; }}
  ul.claims li {{ padding: 0.5rem 0.75rem; margin: 0.25rem 0; border-left: 3px solid var(--claim-bd); background: var(--claim); border-radius: 0 4px 4px 0; font-size: 0.92rem; }}
  ul.claims li.finding {{ border-color: var(--finding-bd); background: var(--finding); }}
  ul.claims li.method {{ border-color: var(--method-bd); background: var(--method); }}
  ul.claims li.result {{ border-color: var(--result-bd); background: var(--result); }}
  ul.claims li.definition {{ border-color: var(--definition-bd); background: var(--definition); }}
  ul.claims li.entity {{ border-color: var(--entity-bd); background: var(--entity); }}
  ul.claims li.ungrounded {{ border-color: var(--ungrounded-bd); background: var(--ungrounded); }}
  .claim-class {{ display: inline-block; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; padding: 0.1rem 0.4rem; border-radius: 3px; background: rgba(0,0,0,0.08); margin-right: 0.5rem; }}
  .claim-attrs {{ display: block; color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }}
  .claim-snippet {{ display: block; color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; font-style: italic; border-left: 2px solid rgba(0,0,0,0.15); padding-left: 0.5rem; }}
  pre.source {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 4px; padding: 1rem; white-space: pre-wrap; word-wrap: break-word; font-size: 0.82rem; max-height: 30em; overflow-y: auto; }}
  pre.source mark {{ border-radius: 2px; padding: 0 1px; }}
  pre.source mark.claim {{ background: var(--claim); }}
  pre.source mark.finding {{ background: var(--finding); }}
  pre.source mark.method {{ background: var(--method); }}
  pre.source mark.result {{ background: var(--result); }}
  pre.source mark.definition {{ background: var(--definition); }}
  pre.source mark.entity {{ background: var(--entity); }}
  .legend {{ margin: 1rem 0; font-size: 0.85rem; }}
  .legend span {{ display: inline-block; padding: 0.15rem 0.5rem; margin-right: 0.5rem; border-radius: 3px; font-size: 0.75rem; }}
</style></head><body>
<h1>🗺️ Scientific Evidence Map</h1>
<div class="summary">{self._esc(book_title)} · {len(chapters)} chapter(s) ·
{total_claims} extractions ({total_grounded} grounded, {total_ungrounded} ungrounded, {pct:.0f}% verbatim)</div>
{alarm_banner}
<div class="legend">
  <span class="claim">claim</span>
  <span class="finding">finding</span>
  <span class="method">method</span>
  <span class="result">result</span>
  <span class="definition">definition</span>
  <span class="entity">entity</span>
  <span class="ungrounded">ungrounded</span>
</div>
{"".join(chapters_html)}
<footer style="margin-top:3rem;color:var(--muted);font-size:0.8rem;border-top:1px solid #ddd;padding-top:1rem;">
  Generated by Elixir V10.1.0 · Powered by Google langextract (Apache-2.0)
</footer>
</body></html>"""

    def _render_chapter_claims(self, ch: dict[str, Any]) -> str:
        """Render the <li> list of claims for one chapter."""
        items = []
        for c in ch.get("claims", []):
            cls = c.get("class", "claim") or "claim"
            grounded = c.get("grounded", False)
            li_cls = cls if grounded else "ungrounded"
            attrs = c.get("attributes") or {}
            attrs_str = " · ".join(f"{k}: {v}" for k, v in attrs.items())
            attrs_html = (
                f'<span class="claim-attrs">{self._esc(attrs_str)}</span>' if attrs_str else ""
            )
            snippet = c.get("source_snippet", "")
            snippet_html = (
                f'<span class="claim-snippet">📖 "{self._esc(snippet[:200])}"</span>'
                if snippet
                else ""
            )
            badge = "✓" if grounded else "⚠️"
            items.append(
                f'<li class="{self._esc(li_cls)}">'
                f'<span class="claim-class">{self._esc(cls)}</span>'
                f"{badge} {self._esc(c.get('text', ''))}"
                f"{attrs_html}{snippet_html}</li>"
            )
        return "\n".join(items)

    def _render_highlighted_source(self, ch: dict[str, Any]) -> str:
        """Render the source text with grounded claims highlighted via <mark>.

        Claims with a char_interval are wrapped in <mark class="class">.
        Ungrounded claims (no interval) are not highlighted (they're not in
        the source).  Overlapping intervals are sorted by start and trimmed.
        """
        source = ch.get("source_text", "") or ""
        if not source:
            return "<em>(no source text available)</em>"
        # Collect (start, end, class) for grounded claims
        spans = []
        for c in ch.get("claims", []):
            iv = c.get("char_interval")
            if not iv:
                continue
            try:
                start, end = int(iv[0]), int(iv[1])
            except Exception as _e:
                continue
            if start < 0 or end > len(source) or start >= end:
                continue
            spans.append((start, end, c.get("class", "claim") or "claim"))
        if not spans:
            return self._esc(source)
        # Sort by start; resolve overlaps by preferring earlier spans
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        out = []
        last = 0
        occupied_end = -1
        for start, end, cls in spans:
            if start < occupied_end:
                continue  # skip overlapping
            out.append(self._esc(source[last:start]))
            out.append(f'<mark class="{self._esc(cls)}">{self._esc(source[start:end])}</mark>')
            last = end
            occupied_end = end
        out.append(self._esc(source[last:]))
        return "".join(out)

    @staticmethod
    def _esc(text: str) -> str:
        """HTML-escape text for safe insertion into the page."""
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
