"""V0.4.19 — moved VERBATIM from summarizer.py (de-monolithization step 9/10)
following the house mixin pattern.

The coverage/gap-fill wrappers + the Tier-2/Tier-3 excerpt logic moved out
of the ~2.7k-line ``summarizer.py`` monolith into this module, re-homed via
the mixin pattern — ``Summarizer`` inherits ``SummarizerCoverageMixin`` at
the END of its bases list, so every ``self.<attr>`` / ``self.<method>``
reference resolves exactly as before through the MRO and external
importers of ``Summarizer`` are unaffected (same module, same name).

VERBATIM CONTRACT (the house decomposition pattern): every method body is
byte-identical to summarizer.py immediately before this move — only this
module's imports (the re-homed module-level dependencies) and docstring
are new.

What lives here (moved VERBATIM, in the original relative order):

  - ``_compute_coverage``        — V18.7 (Phase 5.2) thin delegate to
    ``summary_validator.compute_coverage`` (coverage cache + keyword
    extractor wired from the instance).
  - ``_find_source_sentence``    — Tier-3 source-sentence locator (V0.05
    rig-audit F4 boundary lookahead incl. digits + typographic quotes).
  - ``_targeted_gap_fill``       — Tier-2 parallel focused gap-fill calls.
  - ``_prune_covered_excerpts``  — V0.06 (rig audit F7-a) ship-time excerpt
    re-validation (per-bullet containment / 75% word coverage).
  - ``_force_insert_missing``    — V0.03 (P0-2) Tier-3 complete-sentence
    excerpt insertion (framed, EXCLUDED from Key Takeaways).
  - ``_apply_3tier_coverage``    — thin wrapper delegating to
    ``coverage_guarantee.apply_3tier_coverage`` (the 8 ``self`` deps are
    passed as explicit kwargs — the proven-safe pattern).
  - ``_extract_must_have_items`` — V13.44.0 Idea #1 pre-flight extraction
    (5-7 must-have items injected into B4 section prompts).
  - ``_gap_fill_concepts``       — V3.2.0 C2 delegate to
    ``gap_filler.gap_fill_concepts`` (12 self-deps as explicit kwargs).

NOT moved (stays in summarizer.py): ``_recover_vram``,
``_scholar_reflection`` / ``_scholar_reflection_gapfill_only`` and
``_summarize_inner`` (pinned by tests/test_v182047_p5_core_decomp.py
``_NOT_MOVED_NEIGHBOURS``), plus the 7 TLS property shims.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re

# V18.15.3 (Phase 5 Stage 3, Batch 4.5): 3-Tier coverage guarantee.
from core.summarisation.coverage_guarantee import apply_3tier_coverage as cg_apply_3tier_coverage

# V18.12 (Phase 5 Stage 3, Batch 2.7): concept gap-fill (targeted LLM calls for uncovered concepts).
from core.summarisation.gap_filler import gap_fill_concepts as gf_gap_fill_concepts

# V18.7 (Phase 5.2): the compute_coverage delegate target.
from core.summarisation.summary_validator import (
    compute_coverage as sv_compute_coverage,
)
from core.system.timeouts import FAST_LLM_TIMEOUT_S

# V18.2.14 (B4): traceable error-handling helpers — replace silent
# ``except Exception: pass`` with ``log_swallow()`` so failures leave a
# permanent, searchable log trace (operation name + exc type + traceback).
from utils.error_trace import log_swallow


class SummarizerCoverageMixin:
    """Coverage/gap-fill wrappers for :class:`Summarizer` (see the module
    docstring). Method bodies are byte-identical to summarizer.py's."""

    def _compute_coverage(self, source: str, summary: str) -> float:
        """Return fraction of source keywords + concepts present in summary.

        V18.7 (Phase 5.2): extracted verbatim to ``summary_validator.compute_coverage``.
        This method is a thin delegate. The ``coverage_cache`` dict and
        ``_extract_keywords`` callable are passed by reference/callback.
        """
        return sv_compute_coverage(
            source=source,
            summary=summary,
            coverage_cache=self._coverage_cache,
            extract_keywords=self._extract_keywords,
        )

    def _find_source_sentence(self, keyword, text):
        kl = keyword.lower()
        # V0.05 (rig audit F4 — P1): the boundary lookahead now accepts
        # DIGITS and typographic quotes too. The old ``(?=[A-Z"])`` never
        # split before a numbered-list continuation ("…on the attack.\n\n 3)
        # Use these…"), so excerpts glued two numbered items into one
        # "sentence" — a verbatim excerpt must be exactly one sentence.
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c])', text)
        for sent in sentences:
            sl = sent.lower().strip()
            if not sl or len(sl) < 20:
                continue
            if " " in kl:
                parts = [p for p in kl.split() if len(p) > 2]
                if parts and all(p in sl for p in parts):
                    return sent.strip()
            elif kl in sl:
                return sent.strip()
        return None

    def _targeted_gap_fill(self, heading, text, missing_keywords):
        if not missing_keywords:
            return []
        gap_pairs = []
        for kw in missing_keywords[:12]:
            sent = self._find_source_sentence(kw, text)
            if sent:
                gap_pairs.append((kw, sent))
        if not gap_pairs:
            return []
        self.log(
            f"    \U0001f50d Tier 2: targeted gap-fill for {len(gap_pairs)} missing concepts (parallel, focused calls)\u2026",
            "INFO",
        )

        def _fill_one(pair):
            kw, sent = pair
            lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
            prompt = f'Write ONE bullet point (prefixed with "- ") summarizing what this source sentence says about "{kw}".\n\nSource sentence: "{sent}"\n\nRules:\n- One bullet only, prefixed with "- ".\n- Grounded in the source sentence.\n- Concise (1-2 sentences max).\n{lang}\n\nBullet point:'
            try:
                # V13.36.0: When fusion gap-fill is enabled (site E, opt-in),
                # use the cloud model for higher-quality paraphrases.
                # Default is OFF — the local 9B model is fine for paraphrasing.
                if self.fusion_enabled and self.fusion_use_for_gap_fill:
                    raw = self._call_cloud(
                        prompt, max_tokens=200, temperature=self.fusion_cloud_temperature
                    )
                else:
                    raw = self._call_fast_llm(prompt, max_tokens=200)
                if not raw:
                    return None
                raw = self._strip_thinking(raw).strip()
                if raw and not raw.startswith("- "):
                    raw = "- " + raw.lstrip("*-\u2022 ")
                if raw and len(raw) > 10 and "cannot" not in raw.lower()[:30]:
                    return raw
                return None
            except Exception:
                return None

        new_bullets = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_fill_one, pair): pair for pair in gap_pairs}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bp = future.result(timeout=FAST_LLM_TIMEOUT_S)
                        if bp:
                            new_bullets.append(bp)
                    except Exception as _e:
                        # V18.2.14 (B4): was silent ``pass`` — now traceable.
                        # WARNING level because a failed future means a lost
                        # gap-fill bullet — worth surfacing.
                        log_swallow("gap_fill_future_result", _e, level=logging.WARNING)
        except Exception:
            for pair in gap_pairs:
                bp = _fill_one(pair)
                if bp:
                    new_bullets.append(bp)
        if new_bullets:
            self.log(
                f"    \u2705 Tier 2: gap-filled {len(new_bullets)}/{len(gap_pairs)} concepts via focused LLM calls",
                "INFO",
            )
        return new_bullets

    def _prune_covered_excerpts(
        self,
        bullets: list[str],
        exec_sum: str,
        thorough: str,
        excerpts: list[str],
    ) -> list[str]:
        """V0.06 (rig audit F7-a): drop excerpts the FINAL summary covers.

        GENERAL RULE: a Tier-3 excerpt exists to cover a concept the summary
        text did not cover AT INSERTION TIME. Later stages (scholar
        gap-fill, Tier-2) can add bullets covering the same source
        sentence; at ship time the excerpt list is re-validated so the
        delivered "Source Excerpts" section only contains material the
        final summary genuinely does not cover. Two honest coverage
        signals, either suffices:

          * per-bullet content-token containment >= 0.55 (a bullet
            paraphrasing the excerpt's sentence), or
          * >= 75% of the quote's content words present in the combined
            summary text (exec + bullets + thorough).
        """
        if not excerpts:
            return list(excerpts or [])

        def _tokens(s: str) -> set[str]:
            out = set()
            for w in re.findall(r"[a-z0-9]+", (s or "").lower()):
                if len(w) <= 2:
                    continue
                if len(w) > 3 and w.endswith("s"):
                    out.add(w[:-1])
                out.add(w)
            return out

        combined_words = _tokens(
            " ".join(
                [
                    str(exec_sum or ""),
                    " ".join(str(b) for b in (bullets or [])),
                    str(thorough or ""),
                ]
            )
        )
        kept: list[str] = []
        for ex in excerpts:
            ex_str = str(ex)
            m = re.search(r':\s*"(.*)"\s*$', ex_str, re.DOTALL)
            if not m:
                kept.append(ex_str)  # not a framed excerpt — leave untouched
                continue
            quote_toks = _tokens(m.group(1))
            if not quote_toks:
                kept.append(ex_str)
                continue
            covered = False
            # (a) per-bullet paraphrase containment
            for b in bullets or []:
                b_toks = _tokens(str(b))
                if not b_toks:
                    continue
                inter = len(quote_toks & b_toks)
                if inter and inter / min(len(quote_toks), len(b_toks)) >= 0.55:
                    covered = True
                    break
            # (b) combined-text word coverage
            if not covered:
                hits = sum(1 for t in quote_toks if t in combined_words)
                if hits / len(quote_toks) >= 0.75:
                    covered = True
            if not covered:
                kept.append(ex_str)
        return kept

    def _force_insert_missing(self, text, still_missing, result, heading=""):
        """V16.0.3 Tier-3 → V0.03 (P0-2) REDESIGNED.

        The old implementation appended raw source slices as KEY TAKEAWAYS
        ("- **{kw}**: {sent}"). The V0.02 rig run showed the failure mode:
        a mid-quote fragment of the *anti-pattern answer* ("We do," we say
        something like, "Well, you could do without a second server…")
        shipped as the final takeaway of the book — advice-shaped garbage.

        New contract (GENERAL, not book-specific):
          - excerpts NEVER enter ``bullet_points`` (Key Takeaways) — they
            go to ``result["source_excerpts"]``, rendered as a separate,
            clearly-labelled section;
          - only COMPLETE sentences are eligible: capital-letter start,
            terminal punctuation, ≥40 chars, balanced double quotes;
          - each excerpt carries explicit framing so a skimming reader
            cannot mistake it for the model's advice.
        """
        if not still_missing:
            return 0
        inserted = 0
        # V0.05 (rig audit F3-b — P1): the dedupe key is the NORMALIZED
        # SOURCE SENTENCE, not the framed excerpt string. The old key
        # (excerpt.lower()[:80]) was keyword-dominated — the frame
        # 'On "kw" — verbatim…' STARTS with the keyword, so different
        # keywords pointing at the SAME sentence each inserted their own
        # copy (the V0.04 rig shipped 9 excerpts for 4 unique sentences in
        # one chapter). The key extracts the quoted sentence tail instead.
        _norm_ws = re.compile(r"\s+")
        existing = set()
        for x in result.get("source_excerpts", []) or []:
            _body = str(x)
            _qm = re.search(r':\s*"(.*)"\s*$', _body, re.DOTALL)
            if _qm:
                _body = _qm.group(1)
            existing.add(_norm_ws.sub(" ", _body.lower().strip()))
        # V0.05 (F3-c): remediation unit = SENTENCE, not keyword. Keywords
        # resolving to the same source sentence are consolidated into ONE
        # excerpt (the frame lists them together) — overlapping
        # bigram/trigram keywords from one sentence must not each spawn
        # their own remediation.
        _by_sentence: dict[str, list[str]] = {}
        _sent_cache: dict[str, str] = {}
        for kw in still_missing:
            sent = self._find_source_sentence(kw, text)
            if not sent:
                continue
            _skey = _norm_ws.sub(" ", sent.lower().strip())
            _sent_cache[_skey] = sent
            _by_sentence.setdefault(_skey, []).append(kw)
        for _skey, _kws in _by_sentence.items():
            sent = _sent_cache[_skey]
            # V0.06 (rig audit F7-b — GENERAL RULE: an excerpt never opens
            # with a duplicate of its own chapter heading). PDF extraction
            # frequently glues the chapter TITLE (or its numbered echo)
            # onto the first sentence of the body text — the V0.05 rig
            # shipped an excerpt reading "Don't put your resume ahead of
            # the\n\nrequirements As engineers we sometimes…" where the
            # heading echo runs straight into the real sentence. Collapse
            # internal whitespace and strip a leading heading-echo prefix
            # (whitespace-insensitive, optional leading number).
            sent = _norm_ws.sub(" ", sent).strip()
            if heading:
                _head = _norm_ws.sub(" ", str(heading).strip())
                _head_nn = re.sub(r"^\d+[.)]?\s*", "", _head).strip().lower()
                _sent_lc = sent.lower()
                if _head_nn and len(_head_nn) >= 12 and _sent_lc.startswith(_head_nn):
                    sent = sent[len(_head_nn) :].lstrip(" —–-:,.").strip()
                    _skey = _norm_ws.sub(" ", sent.lower().strip())
            kw = " / ".join(_kws[:3]) + (" …" if len(_kws) > 3 else "")
            # V0.03 (P0-2): complete-sentence gate — reject fragments.
            _s = sent.strip().strip('"')
            _starts_ok = bool(_s) and (_s[0].isupper() or _s[0] in "“\"'")
            _ends_ok = bool(_s) and (_s[-1] in ".!?…" or _s[-1] in "”\"')")
            _len_ok = len(_s) >= 40
            _quotes_ok = sent.count('"') % 2 == 0
            if not (_starts_ok and _ends_ok and _len_ok and _quotes_ok):
                self.log(
                    f"    ⛔ Tier 3: skipped non-sentence excerpt for '{kw}' "
                    f"(fragment/quote-imbalanced source slice)",
                    "DEBUG",
                )
                continue
            if _skey in existing:
                continue
            # V0.4.11: fix broken trailing "(p." — the sentence-split
            # regex at line 804 splits after ". " before a capital/digit,
            # so a sentence ending with "(p. 89)" gets truncated to
            # "(p." (the digit after the space triggers the split). Strip
            # any trailing incomplete parenthetical citation.
            _sent_clean = sent
            if _sent_clean.endswith("(p."):
                _sent_clean = _sent_clean[:-3].rstrip()
            elif _sent_clean.endswith("(p"):
                _sent_clean = _sent_clean[:-2].rstrip()
            excerpt = (
                f'On "{kw}" — verbatim from the source (auto-inserted for '
                f'coverage; not the summarizer\'s advice): "{_sent_clean}"'
            )
            result.setdefault("source_excerpts", []).append(excerpt)
            existing.add(_skey)
            inserted += 1
        if inserted > 0:
            self.log(
                f"    🔖 Tier 3: recorded {inserted} complete-sentence source "
                f"excerpt(s) into the 'Source Excerpts' section (framed, "
                f"EXCLUDED from Key Takeaways; sentence-deduped — "
                f"{len(_by_sentence)} unique source sentence(s) for "
                f"{len(still_missing)} keyword(s))",
                "INFO",
            )
        return inserted

    def _apply_3tier_coverage(self, heading, text, content, result, coverage):
        """V16.0.3 3-Tier coverage guarantee.

        V18.15.3 (Phase 5 Stage 3, Batch 4.5): logic extracted verbatim to
        ``coverage_guarantee.apply_3tier_coverage``. The 8 ``self`` deps
        (``coverage_threshold``, ``_extract_keywords``, ``log``,
        ``_targeted_gap_fill``, ``_filter_thinking_bullets``,
        ``max_bullets_per_chapter``, ``_compute_coverage``,
        ``_force_insert_missing``) are passed as explicit kwargs (the
        proven-safe pattern — NOT a context object). ``result`` is mutated
        in place exactly as the original. Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_coverage_guarantee.py``).
        """
        # V0.06 (rig audit F4-b): the source-scaled bullet budget (the SAME
        # length_policy.bullet_target every prompt uses) is passed as a HARD
        # CAP to the coverage engine — Tier-2 gap-fill stops adding bullets
        # at the cap (the V0.05 rig: 6 primary bullets + 4 Tier-2 + 9 scholar
        # = 19 shipped against a 5-7 target). F7-b: the chapter heading is
        # threaded to Tier-3 so excerpts never open with a heading echo.
        from core.summarisation.length_policy import (
            bullet_cap as _lp_bullet_cap,
        )
        from core.summarisation.length_policy import (
            count_source_words as _lp_csw,
        )

        return cg_apply_3tier_coverage(
            heading,
            text,
            content,
            result,
            coverage,
            coverage_threshold=self.coverage_threshold,
            extract_keywords=self._extract_keywords,
            log=self.log,
            targeted_gap_fill=self._targeted_gap_fill,
            filter_thinking_bullets=self._filter_thinking_bullets,
            max_bullets_per_chapter=self.max_bullets_per_chapter,
            compute_coverage=self._compute_coverage,
            force_insert_missing=(
                lambda t, sm, r: self._force_insert_missing(t, sm, r, heading=heading)
            ),
            bullet_cap=_lp_bullet_cap(_lp_csw(text)),
        )

    def _extract_must_have_items(self, heading: str, text: str) -> list[str]:
        """V13.44.0 Idea #1: Pre-flight extraction of must-have items.

        Runs 1 quick LLM call to identify 5-7 things this summary MUST include.
        These are injected into each B4 section's prompt as explicit requirements.

        Universal: works for any book — discovers enumerated lists, key definitions,
        critical conclusions, important quotes, specific mechanisms by reading the source.
        """
        self.log("    🎯 Pre-flight: extracting must-have items…", "INFO")
        # Truncate source for the pre-flight call (don't need full text)
        max_src = 12000  # ~3000 tokens — enough to identify key items
        src_text = text[:max_src]
        lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
        text_excerpt = text[:200] if len(text) > 200 else text
        prompt = self.prompt_manager.render_template(
            "summarisation/preflight_must_have",
            heading=heading,
            text_excerpt=text_excerpt,
            src_text=src_text,
            language=lang,
        )

        try:
            raw = self._call_llm_with_empty_retry(prompt, temperature=0.3, max_tokens=300)
            if not raw:
                self.log("    ⚠️ Pre-flight: empty response, skipping", "WARNING")
                return []
            raw = self._strip_thinking(raw)
            items = []
            for line in raw.strip().split("\n"):
                line = line.strip().lstrip("- •\t").strip()
                if line and len(line) > 5 and len(line) < 100:
                    items.append(line)
            self.log(
                f"    🎯 Pre-flight: identified {len(items)} must-have items: {items[:3]}…", "INFO"
            )
            return items[:7]  # cap at 7
        except Exception as e:
            self.log(f"    ⚠️ Pre-flight failed: {e}", "WARNING")
            return []

    def _gap_fill_concepts(
        self,
        heading: str,
        content: str,
        bullets: list[str],
        concepts: list[str],
        exec_summary: str = "",
        thorough_summary: str = "",
    ) -> list[str]:
        """V3.2.0 C2: Detect uncovered concepts and make a targeted LLM call.

        V18.12 (Phase 5 Stage 3, Batch 2.7): logic extracted verbatim to
        ``gap_filler.gap_fill_concepts``. The 12 self-deps are passed as
        explicit kwargs (the proven-safe pattern — NOT a context object).
        The mutable ``self._last_coverage`` is set via a ``set_last_coverage``
        callback (preserves the original side-effect). Byte-for-byte identical
        behaviour (characterization tests in ``tests/test_gap_filler.py``).
        """
        return gf_gap_fill_concepts(
            heading,
            content,
            bullets,
            concepts,
            exec_summary,
            thorough_summary,
            output_dir=self.request.output_dir,
            temperature=self.temperature,
            effective_target=self._effective_target,
            overdeliver_enabled=self.overdeliver_enabled,
            overdeliver_target=self.overdeliver_target,
            coverage_threshold=self.coverage_threshold,
            prompt_manager=self.prompt_manager,
            recover_vram=self._recover_vram,
            call_fast_llm=self._call_fast_llm,
            strip_thinking=self._strip_thinking,
            switch_to_fast_model=self._switch_to_fast_model,
            set_last_coverage=lambda pct: setattr(self, "_last_coverage", pct),
            log=self.log,
        )
